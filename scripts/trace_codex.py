"""Read Codex rollout receipts, cumulative counters, and native agent lifecycle evidence."""
import ast
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
import re

from trace_hosts import UUID, commands, object_value, records
from trace_records import UNKNOWN, loc, stamp


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


def shell_commands(part):
    raw = part.get("input") or part.get("arguments") or ""
    if part.get("name") == "exec_command":
        cmd = object_value(raw).get("cmd")
        return [cmd] if isinstance(cmd, str) else []
    if part.get("name") != "exec" or not isinstance(raw, str) or "exec_command" not in raw:
        return []
    # Mask literals first. Inspect only cmd arguments passed to the shell tool,
    # including its common batched form: jobs.map(([label, cmd]) => ...).
    literals = []
    def mark(match):
        literals.append(match[0])
        return "@" + str(len(literals) - 1) + "@"
    code = JS_LITERAL.sub(mark, raw)
    code = re.sub(r"/\*.*?\*/|//[^\n]*", " ", code, flags=re.S)
    arguments = list(re.finditer(r"\btools\.exec_command\s*\(\s*\{([^{}]*)\}", code))
    ids = []
    for call in arguments:
        field = re.search(r"(?:^|,)\s*cmd\s*(?::\s*(@\d+@|[a-zA-Z_$]\w*))?\s*(?:,|$)", call[1])
        spread = re.search(r"(?:^|,)\s*\.\.\.(\w+)\s*(?:,|$)", call[1])
        if not field and not spread:
            continue
        value = (field[1] or "cmd") if field else spread[1]
        if value.startswith("@"):
            ids.append(int(value[1:-1]))
            continue
        before = code[:call.start()]
        bound = re.findall(r"\b(?:const|let)\s+" + re.escape(value) + r"\s*=\s*@(\d+)@\s*[;,]", before)
        if bound and field:
            ids.append(int(bound[-1]))
            continue
        maps = re.finditer(r"(\w+|\])\.map\s*(\()\s*(?:async\s*)?\(?\s*(?:\[([^\]]+)\]|(\w+))", before)
        for m in maps:
            if len(bracketed(code, m.start(2), "(", ")")) <= call.start() - m.start(2):
                continue
            names = [n.strip() for n in m[3].split(",")] if m[3] else [m[4]]
            if value not in names:
                continue
            if m[1] == "]":
                reverse = before[:m.start(1) + 1][::-1]
                array = bracketed(reverse, 0, "]", "[")[::-1]
            else:
                assignment = re.search(r"\b(?:const|let)\s+" + re.escape(m[1]) + r"\s*=\s*(\[)", before[:m.start()])
                if not assignment:
                    continue
                array = bracketed(code, assignment.start(1), "[", "]")
            idx = names.index(value)
            for row in array_items(array):
                fields = array_items(row) if m[3] else [row]
                if idx >= len(fields):
                    continue
                arg = fields[idx]
                if spread:
                    opt = re.search(r"(?:^\{|,)\s*cmd\s*:\s*(@\d+@)(?=\s*[,}+])", arg)
                    arg = opt[1] if opt else ""
                if re.fullmatch(r"@\d+@", arg):
                    ids.append(int(arg[1:-1]))
    result = []
    for i in ids:
        literal = literals[i]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                warnings.simplefilter("ignore", DeprecationWarning)
                value = literal[1:-1] if literal.startswith(chr(96)) else ast.literal_eval(literal)
        except (SyntaxError, ValueError):
            continue
        if isinstance(value, str):
            result.append(value)
    return result


def reply_texts(value):
    """Only stdout / native text items can be receipts. Never inspect a quoted prompt or arbitrary fields."""
    if isinstance(value, str):
        stripped = value.lstrip()
        if stripped.startswith(("{", "[")):
            try:
                decoded = json.loads(value)
            except ValueError:
                pass
            else:
                yield from reply_texts(decoded)
                return
        if not re.search(r"Process exited with code (?!0\b)\d+", value):
            yield value
    elif isinstance(value, dict):
        if value.get("type") == "text":
            yield from reply_texts(value.get("text"))
        elif value.get("exit_code", value.get("exit", 0)) == 0:
            yield from reply_texts(value.get("output", value.get("text")))
    elif isinstance(value, list):
        if len(value) in (2, 3) and isinstance(value[0], str):
            if len(value) == 2 or value[1] == 0:
                yield from reply_texts(value[-1])
        else:
            for v in value:
                yield from reply_texts(v)


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
                self.contexts.append((line, part.get("model"), part.get("effort")))
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
                shells = shell_commands(part)
                self.commands.extend((p.line, digest(s)) for s in shells)
                invocations = [inv for s in shells for inv in commands(s)]
                if invocations:
                    self.calls[cid].append(Shell(p, invocations, []))
            if part.get("namespace") == "collaboration" and part.get("name") in {"spawn_agent", "followup_task", "resume_agent"}:
                args = object_value(part.get("arguments"))
                target = args.get("task_name") or args.get("target") or args.get("id")
                if isinstance(target, str):
                    # Only explicit plan/slice identifiers may escape the private dispatch.
                    label = " ".join(str(args.get(k, "")) for k in ("task_name", "message"))
                    plan_slice = re.search(r"\b(P\d{3,})(?:@r\d+)?[\s_:/-]+(S\d+)\b", label, re.I)
                    tag = "/".join(plan_slice.groups()).upper() if plan_slice else ""
                    self.dispatches[cid] = Dispatch(p, part["name"], target, tag, [])
        elif typ in {"function_call_output", "custom_tool_call_output"}:
            if cid in self.calls:
                result = [s for chunk in reply_texts(part.get("output")) for s in chunk.splitlines() if s.startswith("trace ")]
                for call in self.calls[cid]:
                    call.replies.append((p, result))
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
            if len(entries) != 1:
                continue
            call = entries[0]
            match = (lambda w: w[:1] == [e["kind"]]) if verb == "start" else (
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
                any(current[k] < previous[k] for k in previous)):
                return result
        initial, final = samples[0][1], samples[-1][1]
        result["tokens"] = {k: final[k] - v for k, v in initial.items()}
        return result

    def model(self, first, last):
        before = [r for r in self.contexts if r[0] <= first]
        rows = before[-1:] + [r for r in self.contexts if first < r[0] <= (last or first)]
        def agreed(index):
            values = {r[index] for r in rows}
            return values.pop() if len(values) == 1 else None
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
                        if header.get("type") != "session_meta" or not isinstance(uid, str) or uid not in path.name:
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
            model, effort = session.model(*span)
            before = [n for n, _, _ in session.contexts if n <= span[0]]
            context_lines = before[-1:] + [n for n, _, _ in session.contexts if span[0] < n <= (span[1] or span[0])]
            case.data.update(model=model or (UNKNOWN if context_lines else case.data["recorded_model"]),
                             host_model=model or UNKNOWN, effort=effort or UNKNOWN)
            if context_lines:
                case.data["model_locations"] = [loc(session.path, n) for n in context_lines]
            case.data["parent_cost"].update(session.cost(*span))
    return catalog
