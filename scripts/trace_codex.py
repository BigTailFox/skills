"""Read Codex rollout receipts, cumulative counters, and native agent lifecycle evidence."""
import ast
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
import re

from trace_hosts import UUID, commands, matching_start, object_value, observed_lines, records
from trace_records import UNKNOWN, identifier, loc, stamp


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


JS_LITERAL = re.compile(r"""'(?:(?:\\.)|[^'\\])*'|"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`""", re.S)


def bracketed(code, offset, left, right):
    depth = 0
    for pos in range(offset, len(code)):
        depth += (code[pos] == left) - (code[pos] == right)
        if depth == 0:
            return code[offset:pos + 1]
    return ""


def array_items(value):
    if not value.startswith("[") or not value.endswith("]"):
        return []
    inside = value[1:-1]
    level, start, items = 0, 0, []
    for i, ch in enumerate(inside):
        if ch == "," and level == 0:
            items.append(inside[start:i].strip())
            start = i + 1
        level += (ch in "[{(") - (ch in "]})")
    return [*items, inside[start:].strip()]


@dataclass
class ShellCommand:
    command: str
    slot: int | None = None
    label: str | None = None
    repeated: tuple | None = None


def native_items(result):
    """Keep each text() emission separate, including empty non-shell results."""
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except ValueError:
            return [result]
        if not isinstance(parsed, list):
            return [parsed]
        result = parsed
    items = []
    for entry in result if isinstance(result, list) else [result]:
        if isinstance(entry, dict) and entry.get("type") in {"input_text", "text"}:
            entry = entry.get("text")
            if not items and isinstance(entry, str) and re.fullmatch(
                    r"Script completed\nWall time[^\n]*\nOutput:\s*", entry):
                continue
            if isinstance(entry, str):
                try:
                    entry = json.loads(entry)
                except ValueError:
                    pass
        items.append(entry)
    return items


def receipt_lines(entry):
    if isinstance(entry, list) and len(entry) in (2, 3) and isinstance(entry[0], str):
        if len(entry) == 3 and entry[1] != 0:
            return []
        entry = entry[-1]
    if isinstance(entry, dict):
        if entry.get("exit_code", entry.get("exit")) != 0:
            return []
        entry = entry.get("output", entry.get("text"))
    if not isinstance(entry, str) or re.search(r"Process exited with code (?!0\b)-?\d+", entry):
        return []
    return [line for line in entry.splitlines() if line.startswith("trace ")]


def output_slots(code, call):
    prints = list(re.finditer(r"\btext\s*(\()", code))
    owner = next((i for i, m in enumerate(prints)
                  if m.start(1) < call < m.start(1) + len(bracketed(code, m.start(1), "(", ")"))), None)
    direct = False
    if owner is not None:
        prefix = code[prints[owner].end():call]
        opening = code.index("(", call)
        tail = opening + len(bracketed(code, opening, "(", ")"))
        end = prints[owner].start(1) + len(bracketed(code, prints[owner].start(1), "(", ")"))
        direct = bool(re.fullmatch(r"\s*\(?\s*await\s*", prefix)
                      and re.fullmatch(r"\s*\)?(?:\.output)?\s*\)", code[tail:end]))
    else:
        bound = re.search(r"\b(?:const|let)\s+(\w+)\s*=\s*await\s*$", code[:call])
        if bound:
            name = bound[1]
            owner = next((i for i, m in enumerate(prints) if m.start() > call and
                          re.match(r"\s*" + re.escape(name) + r"(?:\.output)?\s*\)", code[m.end():])), None)
            if owner is not None:
                direct = not re.search(r"\b" + re.escape(name) + r"\s*=(?!=)", code[call:prints[owner].start()])
    if not direct:
        return None, None
    # Earlier emissions inside variable-size loops cannot establish a later ordinal.
    earlier = code[:prints[owner].start()]
    if re.search(r"\bif\s*\([^;{}]*\)\s*\{?[^;{}]*\btext\s*\(|(?:&&|\?|:)\s*text\s*\(", earlier):
        return None, None
    loops = list(re.finditer(r"\bfor\s*\(", earlier))
    if loops:
        loop = loops[0]
        match = re.match(r"for\s*\(\s*const\s*\[[^\]]+\]\s+of\s*(\[)", code[loop.start():])
        if len(loops) != 1 or not match:
            return None, None
        offset = loop.start() + match.start(1)
        array = bracketed(code, offset, "[", "]")
        body = re.match(r"\s*\)\s*(\{)", code[offset + len(array):])
        if not body:
            return None, None
        start = offset + len(array) + body.start(1)
        stop = start + len(bracketed(code, start, "{", "}"))
        inside = [i for i, m in enumerate(prints) if start < m.start() < stop]
        if owner not in inside or not inside:
            return None, None
        return owner, (len(inside), len(array_items(array)), inside[0])
    if re.search(r"(?:\.forEach|\.map)\s*\([^;]*?\btext\s*\(", earlier):
        return None, None
    return owner, None


# A source listing proves execution counts only for unconditional, straight-line
# calls. For callbacks, loops and other JavaScript, individual paired receipts
# can still identify a boundary without proving how often a command ran.
SHELL_EXPRESSION = r"await\s+tools\.exec_command\s*\(\s*\{[^{}()]*\}\s*\)"
SIMPLE_STATEMENT = (r"(?:(?:const|let)\s+\w+\s*=\s*(?:@\d+@|" + SHELL_EXPRESSION + r")|" +
                    SHELL_EXPRESSION + r"|text\(\s*(?:" + SHELL_EXPRESSION + r"|\w+(?:\.output)?)\s*\))")
SIMPLE_SEQUENCE = re.compile(r"\s*(?:" + SIMPLE_STATEMENT + r"\s*;\s*)*(?:" + SIMPLE_STATEMENT + r"\s*;?)?\s*")


def shell_commands(part):
    raw = part.get("input") or part.get("arguments") or ""
    if part.get("name") == "exec_command":
        cmd = object_value(raw).get("cmd")
        return ([ShellCommand(cmd, 0)], True) if isinstance(cmd, str) else ([], False)
    if not isinstance(raw, str):
        return [], False
    if "exec_command" not in raw:
        return [], not re.search(r"\b(?:eval|Function)\s*\(|\btools\s*\[", JS_LITERAL.sub("literal", raw))
    literals = []
    def mark(match):
        literals.append(match[0])
        return "@" + str(len(literals) - 1) + "@"
    code = JS_LITERAL.sub(mark, raw)
    code = re.sub(r"/\*.*?\*/|//[^\n]*", " ", code, flags=re.S)
    def literal(token):
        if not re.fullmatch(r"@\d+@", token):
            return None
        raw = literals[int(token[1:-1])]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return raw[1:-1] if raw.startswith(chr(96)) else ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return None

    calls = list(re.finditer(r"\btools\.exec_command\s*\(", code))
    entries, decoded = [], 0
    for call in calls:
        args = re.match(r"\s*\{([^{}]*)\}", code[call.end():])
        if not args:
            continue
        field = re.search(r"(?:^|,)\s*cmd\s*(?::\s*(@\d+@|[a-zA-Z_$]\w*))?\s*(?:,|$)", args[1])
        spread = re.search(r"(?:^|,)\s*\.\.\.(\w+)\s*(?:,|$)", args[1])
        if not field and not spread:
            continue
        value = (field[1] or "cmd") if field else spread[1]
        before = code[:call.start()]
        bound = re.findall(r"\b(?:const|let)\s+" + re.escape(value) + r"\s*=\s*(@\d+@)\s*[;,]", before)
        cmd = literal(bound[-1] if bound and field else value)
        if cmd is not None:
            slot, repeat = output_slots(code, call.start())
            entries.append(ShellCommand(cmd, slot, repeated=repeat))
            decoded += 1
            continue
        maps = re.finditer(r"(\w+|\])\.map\s*(\()\s*(?:async\s*)?\(?\s*(?:\[([^\]]+)\]|(\w+))", before)
        for m in maps:
            closing = m.start(2) + len(bracketed(code, m.start(2), "(", ")"))
            if closing <= call.start():
                continue
            names = [n.strip() for n in m[3].split(",")] if m[3] else [m[4]]
            if value not in names:
                continue
            if m[1] == "]":
                array = bracketed(before[:m.start(1)+1][::-1], 0, "]", "[")[::-1]
            else:
                assign = re.search(r"\b(?:const|let)\s+" + re.escape(m[1]) + r"\s*=\s*(\[)", before[:m.start()])
                array = bracketed(code, assign.start(1), "[", "]") if assign else ""
            rows = array_items(array)
            simple = re.search(r"\bconst\s+(\w+)\s*=\s*await\s+Promise\.all(?:Settled)?\(\s*$", before[:m.start()])
            prior_print = re.search(r"\btext\s*\(", before[:m.start()])
            ordered = bool(simple and not prior_print and re.fullmatch(
                r"\s*\)*;?\s*for\s*\(\s*const\s+(\w+)\s+of\s+" + re.escape(simple[1]) +
                r"\s*\)\s*\{?\s*text\(\1(?:\.value)?(?:\.output)?\)\s*;?\s*\}?\s*;?\s*", code[closing:]))
            idx = names.index(value)
            # A tagged emission binds its key to the actual call result, even
            # when Promise callbacks finish out of order.
            callback = code[m.end():closing]
            tagged = False
            if m[3] and idx:
                tag = re.escape(names[0])
                immediate = re.search(r"\[\s*" + tag + r"\s*,\s*\(?\s*await\s+tools\.exec_command\(", callback)
                returned = re.search(r"const\s+(\w+)\s*=\s*await\s+tools\.exec_command\([^;]*;\s*return\s*"
                                     r"\[\s*" + tag + r"\s*,\s*\1\s*\]", callback)
                tagged = bool(immediate or returned)
            echo_cmd = bool(simple and re.search(
                r"const\s+(\w+)\s*=\s*" + re.escape(simple[1]) +
                r"\[(\w+)\]\.value\s*;\s*text\(\{\s*c\s*:\s*" + re.escape(m[1]) +
                r"\[\2\],\s*exit\s*:\s*\1\??\.exit_code,\s*text\s*:\s*\1\??\.output\b", code[closing:]))
            found = 0
            for pos, row in enumerate(rows):
                fields = array_items(row) if m[3] else [row]
                if idx >= len(fields):
                    continue
                arg = fields[idx]
                suffix = ""
                if spread:
                    opt = re.search(r"(?:^\{|,)\s*cmd\s*:\s*(@\d+@)\s*([,+}])", arg)
                    arg = opt[1] if opt else ""
                    suffix = "${dynamic}" if opt and opt[2] == "+" else ""
                command = literal(arg)
                if command is None:
                    continue
                slot = pos if ordered else None
                label = literal(fields[0]) if tagged else command if echo_cmd else None
                entries.append(ShellCommand(command + suffix, slot, label))
                found += 1
            decoded += int(bool(rows) and found == len(rows))
            break
    references = list(re.finditer(r"\bexec_command\b", code))
    direct_only = len(references) == len(calls)
    if calls or references:
        return entries, bool(direct_only and decoded == len(calls) and SIMPLE_SEQUENCE.fullmatch(code))
    indirect = re.search(r"\b(?:eval|Function)\s*\(|\btools\s*\[", code)
    return entries, not indirect


def command_replies(command, output):
    if command.label is not None:
        matches = [e for e in output if (isinstance(e, list) and e and e[0] == command.label) or
                   (isinstance(e, dict) and e.get("c") == command.label)]
        return receipt_lines(matches[0]) if len(matches) == 1 else []
    slot = command.slot
    if slot is None:
        return []
    if command.repeated:
        width, count, start = command.repeated
        if len(output) < start or (len(output) - start) % width or len(output) > start + count * width:
            return []
        return [line for e in output[slot::width] for line in receipt_lines(e)]
    return receipt_lines(output[slot]) if slot < len(output) else []


def worker_status(body):
    if not isinstance(body, str):
        return UNKNOWN
    statuses = set(re.findall(r"(?im)^\s*(?:[-#*\s]*status\s*[*:–—-]*\s*|[\s#*]*)(done|stuck|blocked|paused)\b", body))
    return statuses.pop().lower() if len(statuses) == 1 else UNKNOWN


@dataclass
class Point:
    line: int
    at: object


@dataclass
class Shell:
    point: Point
    invocations: list
    replies: list
    command: ShellCommand


@dataclass
class Dispatch:
    point: Point
    verb: str
    target: str
    tag: str
    receipts: list


@dataclass
class Terminal:
    point: Point
    kind: str
    body: str
    status: str


def token_fields(raw):
    if not isinstance(raw, dict) or not raw:
        return None
    if not all(isinstance(k, str) and re.fullmatch(r"[a-z][a-z0-9_]*tokens", k) and
               type(v) is int and v >= 0 for k, v in raw.items()):
        return None
    if ("cached_input_tokens" in raw and raw.get("input_tokens", 0) < raw["cached_input_tokens"] or
        "reasoning_output_tokens" in raw and raw.get("output_tokens", 0) < raw["reasoning_output_tokens"]):
        return None
    if "total_tokens" in raw:
        components = [raw[k] for k in ("input_tokens", "output_tokens") if k in raw]
        if raw["total_tokens"] < sum(components) or (len(components) == 2 and raw["total_tokens"] != sum(components)):
            return None
    return raw


class CodexSession:
    def __init__(self, path, meta):
        self.path, self.meta = path, meta
        self.session_id = meta["id"]
        self.calls = defaultdict(list)
        self.dispatches = {}
        self.notices = []
        self.terminals = []
        self.starts = []
        self.contexts = []
        self.tokens = []
        self.users = []
        self.commands = []
        self.undecoded = []
        self.holes = []
        self.times = []
        for line, record in records(path):
            part = object_value(record.get("payload"))
            p = Point(line, stamp(record.get("timestamp")))
            if p.at:
                self.times.append(p)
            rtype, typ = record.get("type"), part.get("type")
            if not record:
                self.holes.append(line)
            if rtype == "response_item":
                self.response(part, typ, p)
            elif rtype == "turn_context":
                self.contexts.append((line, identifier(part.get("model")), identifier(part.get("effort"))))
            elif rtype == "event_msg":
                if typ == "token_count":
                    usage = object_value(part.get("info")).get("total_token_usage")
                    self.tokens.append((line, token_fields(usage)))
                elif typ in {"task_started", "turn_started"}:
                    self.starts.append(p)
                elif typ in {"task_complete", "turn_complete", "turn_aborted", "task_aborted", "task_failed"}:
                    body = part.get("last_agent_message") or ""
                    self.terminals.append(Terminal(p, typ, digest(body) if isinstance(body, str) and body else "",
                                                   worker_status(body)))

    def response(self, part, typ, p):
        cid = part.get("call_id")
        if typ in {"function_call", "custom_tool_call"}:
            if part.get("name") in {"exec", "exec_command"}:
                shells, complete = shell_commands(part)
                complete = complete and all("${" not in s.command and not s.repeated for s in shells)
                if not complete:
                    self.undecoded.append(p.line)
                for shell in shells:
                    if complete:
                        self.commands.append((p.line, digest(shell.command)))
                    invocations = list(commands(re.sub(r"\$\{[^{}]*\}", "${dynamic}", shell.command), require_status=True))
                    if invocations:
                        self.calls[cid].append(Shell(p, invocations, [], shell))
            if part.get("namespace") == "collaboration" and part.get("name") in {"spawn_agent", "followup_task", "resume_agent"}:
                args = object_value(part.get("arguments"))
                target = args.get("task_name") or args.get("target") or args.get("id")
                if isinstance(target, str):
                    # Only explicit plan/slice identifiers may escape the private dispatch.
                    label = " ".join(str(args.get(k, "")) for k in ("task_name", "target", "message"))
                    plan_slice = re.search(r"(?<![A-Za-z0-9])(P\d{3,})(?:@r\d+)?[\s_:/-]+(S\d+)(?![A-Za-z0-9])", label, re.I)
                    tag = "/".join(plan_slice.groups()).upper() if plan_slice else ""
                    self.dispatches[cid] = Dispatch(p, part["name"], target, tag, [])
        elif typ in {"function_call_output", "custom_tool_call_output"}:
            if cid in self.calls:
                items = native_items(part.get("output"))
                for call in self.calls[cid]:
                    call.replies.append((p, command_replies(call.command, items)))
            if cid in self.dispatches:
                # Some hosts return a structured agent_id, some return the canonical task name as a message.
                body = json.dumps(part.get("output"), ensure_ascii=False)
                self.dispatches[cid].receipts.append((p, set(UUID.findall(body)), body))
        elif part.get("role") == "user":
            self.users.append(p.line)
        elif part.get("role") == "assistant" and part.get("phase") == "final_answer":
            body = "".join(x.get("text", "") for x in part.get("content", []) if isinstance(x, dict)).strip()
            self.terminals.append(Terminal(p, "final", digest(body) if body else "", worker_status(body)))
        elif typ == "agent_message" and part.get("author"):
            body = "".join(x.get("text", "") for x in part.get("content", []) if isinstance(x, dict))
            if body.startswith("Message Type: FINAL_ANSWER\n") and "Payload:\n" in body:
                self.notices.append((p, part["author"], digest(body.partition("Payload:\n")[2].strip())))

    def boundary(self, case, verb):
        e = case.start if verb == "start" else case.end
        when = stamp(e.get("at")) if e else None
        if not when:
            return None
        wanted = "trace " + e["id"] + (" ended" if verb == "end" else "")
        hits = []
        for entries in self.calls.values():
            for call in entries:
                match = (lambda w: matching_start(w, e, None, case.project, paired=True)) if verb == "start" else (
                    lambda w: w[:2] == [e["id"], e.get("outcome")])
                if sum(v == verb and match(w) for v, w in call.invocations) != 1 or len(call.replies) != 1:
                    continue
                reply, lines = call.replies[0]
                if (lines.count(wanted) == 1 and call.point.at and reply.at and call.point.line < reply.line and
                    call.point.at <= reply.at and call.point.at < when + timedelta(seconds=1) and reply.at >= when):
                    hits.append((call.point, reply))
        return hits[0] if len(hits) == 1 else None

    def cost(self, first, last):
        result = {"tokens": UNKNOWN, "locations": []}
        if first is None or last is None or first >= last:
            return result
        before = [i for i, (line, _) in enumerate(self.tokens) if line <= first]
        if not before:
            return result
        samples = [(n, v) for n, v in self.tokens[before[-1]:] if n <= last]
        if len(samples) < 2:
            return result
        result["locations"] = [loc(self.path, samples[0][0]), loc(self.path, samples[-1][0])]
        if any(first <= n <= last for n in self.holes):
            return result
        for (_, previous), (_, current) in zip(samples, samples[1:]):
            if (not current or not previous or previous.keys() != current.keys() or
                not token_fields({k: current[k] - previous[k] for k in previous})):
                return result
        initial, final = samples[0][1], samples[-1][1]
        result["tokens"] = {k: final[k] - v for k, v in initial.items()}
        return result

    def model(self, first, last):
        before = [r for r in self.contexts if r[0] <= first]
        rows = before[-1:] + [r for r in self.contexts if first < r[0] <= (last or first)]
        def agreed(index):
            values = {r[index] for r in rows}
            return values.pop() if before and len(values) == 1 else None
        return agreed(1), agreed(2)


class Catalog:
    """Index just the metadata of other rollouts. Read bodies only for selected sessions and receipt lookup."""
    def __init__(self, homes):
        self.entries, self.children, self.loaded = defaultdict(list), defaultdict(list), {}
        seen = set()
        for home in homes:
            for area in ("sessions", "archived_sessions"):
                for path in (home / area).glob("**/rollout-*.jsonl"):
                    try:
                        st = path.stat()
                        identity = (st.st_dev, st.st_ino)
                        if identity in seen:
                            continue
                        seen.add(identity)
                        with path.open("rb") as stream:
                            header = json.loads(stream.readline())
                        meta = header.get("payload", {})
                        uid = meta.get("id")
                        if header.get("type") != "session_meta" or not isinstance(uid, str) or not UUID.fullmatch(uid) or uid not in path.name:
                            continue
                        meta["_at"] = header.get("timestamp")
                        self.entries[uid].append((path, meta))
                        subagent = object_value(object_value(meta.get("source")).get("subagent"))
                        link = object_value(subagent.get("thread_spawn"))
                        # Other native services can also name a parent thread. Only a
                        # thread spawn, or its older flat agent path, describes a launched child.
                        if "thread_spawn" in subagent or (not subagent and meta.get("agent_path")):
                            parent = link.get("parent_thread_id") or meta.get("parent_thread_id")
                            if parent:
                                self.children[parent].append((uid, link.get("agent_path") or meta.get("agent_path") or ""))
                    except (OSError, ValueError, TypeError, AttributeError):
                        continue

    def session(self, uid):
        if uid not in self.loaded:
            entries = self.entries.get(uid, [])
            try:
                self.loaded[uid] = CodexSession(*entries[0]) if len(entries) == 1 else None
            except OSError:
                self.loaded[uid] = None
        return self.loaded[uid]

    def discover(self, case):
        uid = case.start.get("conversation")
        if uid:
            return self.session(uid)
        needle = ("trace " + case.start["id"]).encode()
        hits = []
        for uid, entries in self.entries.items():
            if len(entries) != 1:
                continue
            path, _ = entries[0]
            try:
                with path.open("rb") as f:
                    if not any(needle in line for line in f):
                        continue
            except OSError:
                continue
            session = self.session(uid)
            if session and session.boundary(case, "start"):
                hits.append(session)
        return hits[0] if len(hits) == 1 else None


def report_model(case, session, first, last, complete=True):
    model, effort = session.model(first, last)
    before = [n for n, _, _ in session.contexts if n <= first]
    lines = before[-1:] + [n for n, _, _ in session.contexts if first < n <= (last or first)]
    case.data["model_locations"] = [loc(session.path, n) for n in lines] or case.data["model_locations"]
    case.data.update(model=(model or (UNKNOWN if lines else case.data["recorded_model"])) if complete else UNKNOWN,
                     host_model=(model or UNKNOWN) if complete else UNKNOWN, effort=(effort or UNKNOWN) if complete else UNKNOWN)


def codex_boundaries(cases, homes):
    if not cases:
        return None
    catalog = Catalog(homes)
    for case in cases:
        session = case.host_session = catalog.discover(case)
        if not session:
            continue
        case.data["conversation"] = session.session_id
        span = []
        for verb in ("start", "end"):
            hit = session.boundary(case, verb)
            if hit:
                point, receipt = hit
                case.data["host_" + verb] = dict(source="export", location=loc(session.path, point.line),
                                                 receipt_location=loc(session.path, receipt.line))
            span.append(hit[0].line if hit else None)
        case.host_span = tuple(span)
        if span[0]:
            report_model(case, session, *span, complete=observed_lines(case, [n for n, _, _ in session.contexts])[1])
            case.data["parent_cost"].update(session.cost(*span))
    return catalog
