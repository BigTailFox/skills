"""Identify unit boundaries in host-native records without emitting private record content."""
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shlex
import sqlite3

from trace_records import UNKNOWN, canon, loc, stamp
from trace_sqlite import cursor_db

UUID = re.compile(r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}")
SCRIPT = re.compile(r"(?:.*/)?(?:\.agents/skills/canon|\.claude/skills/canon|skills/governance/canon)/scripts/canon\.py")
SPLIT = re.compile(r"[;&|()\n]+")
MISSING = {"source": UNKNOWN, "location": UNKNOWN}


def records(path):
    with path.open("rb") as stream:
        for n, data in enumerate(stream, 1):
            try:
                entry = json.loads(data)
            except (ValueError, RecursionError):
                entry = None
            yield n, entry if isinstance(entry, dict) else {}


def object_value(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return {}
    return value if isinstance(value, dict) else {}


def parts(record):
    message = object_value(record.get("message"))
    return [p for p in message.get("content", []) if isinstance(p, dict)] if isinstance(message.get("content"), list) else []


def shell_lines(command):
    """Shell lines outside heredocs, paired with the literal input consumed by their command."""
    lines = iter(command.splitlines(keepends=True))
    for line in lines:
        match = re.search(r"""(?<!<)<<-?\s*['"]?([A-Za-z_][A-Za-z_0-9]*)['"]?""", line)
        body = None
        if match:
            body = []
            for part in lines:
                if part.rstrip("\r\n").lstrip("\t") == match[1]:
                    break
                body.append(part)
        yield line, body


def commands(command):
    """Yield actual canon shell invocations, including the locally bound shorthand used in older exports."""
    if not isinstance(command, str) or "trace " not in command:
        return
    lines = [line for line, _ in shell_lines(command)]
    lexer = shlex.shlex("".join(lines).replace("\\\n", ""), posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        words = list(lexer)
    except ValueError:
        return
    for i in range(1, len(words) - 1):
        if words[i] != "trace" or words[i + 1] not in {"start", "end"}:
            continue
        if words[i - 1] == "c" and any(re.search(r'c\(\)\s*\{\s*python3\s+' + re.escape(s) + r'\s+"\$@"', command)
                                       for s in words if SCRIPT.fullmatch(s)):
            first = i - 1
        elif i >= 2 and words[i - 2] in {"python", "python3"}:
            script = words[i - 1]
            if not SCRIPT.fullmatch(script) and not (script == "$P" and any(
                    s.startswith("P=") and SCRIPT.fullmatch(s[2:]) for s in words[:i])):
                continue
            first = i - 2
        else:
            continue
        if first and not SPLIT.fullmatch(words[first - 1]):
            continue
        after = next((n for n in range(i + 2, len(words)) if SPLIT.fullmatch(words[n])), len(words))
        args = words[i + 2:after]
        if "$base" in args and "base=$(git rev-parse --short HEAD)" in command:
            args = ["HEAD" if w == "$base" else w for w in args]
        yield words[i + 1], args


def matching_start(words, event, cwd):
    if not words or words[0] != event["kind"]:
        return False
    flags, targets = {}, []
    i = 1
    while i < len(words):
        word = words[i]
        if word.startswith("--"):
            if i + 1 == len(words) or word in flags:
                return False
            flags[word] = words[i + 1]
            i += 2
        else:
            targets.append(word)
            i += 1
    if targets != [doc.partition("@")[0] for doc in event.get("docs", [])]:
        return False
    for key in ("slice", "parent", "continues", "tier", "model"):
        arg = flags.pop("--" + key, None)
        value = event.get(key)
        if arg is None and (key == "tier" and event.get("parent") or key == "model" and event["kind"] == "slice"):
            continue
        if key == "model" and arg:
            arg = arg.lower()
        if arg != value:
            return False
    skill = flags.pop("--skill", None)
    if skill:
        recorded = event.get("skill")
        if not isinstance(recorded, str):
            return False
        if cwd or Path(skill).is_absolute():
            if Path(cwd or "") / skill != Path(recorded):
                return False
        elif not recorded.endswith("/" + skill):
            return False
    elif event.get("skill") and event["kind"] != "slice":
        return False
    base = flags.pop("--base", None)
    if base == "HEAD":
        base = event.get("head") or ""
    if base is not None:
        if not re.fullmatch("[a-fA-F0-9]{4,64}", base) or not (event.get("base") or "").startswith(base):
            return False
    elif event.get("base"):
        return False
    return not flags


@dataclass
class Call:
    line: int
    index: int
    verb: str
    words: list
    cwd: str

    @property
    def place(self):
        return self.line, self.index


class CursorSession:
    def __init__(self, path):
        self.path = path
        self.calls = []
        self.shells = []
        self.dispatches = []
        self.users = []
        for line, record in records(path):
            if record.get("role") == "user":
                self.users.append(line)
            if record.get("role") != "assistant":
                continue
            index = 0
            for part in parts(record):
                if part.get("type") != "tool_use":
                    continue
                args = object_value(part.get("input"))
                if part.get("name") == "Shell":
                    command = args.get("command", "")
                    if not isinstance(command, str):
                        continue
                    self.shells.append((line, command))
                    for verb, words in commands(command):
                        self.calls.append(Call(line, index, verb, words, args.get("working_directory")))
                        index += 1
                elif part.get("name") == "CallDynamicTool" and args.get("toolName") == "Task":
                    self.dispatches.append((line, object_value(args.get("arguments"))))
                elif part.get("name") == "Task":
                    self.dispatches.append((line, args))


def cursor_hits(case, session, verb):
    e = case.start if verb == "start" else case.end
    if not e:
        return []
    return [c for c in session.calls if c.verb == verb and
            (matching_start(c.words, e, c.cwd) if verb == "start" else
             c.words[:2] == [e["id"], e.get("outcome")])]


def ms(value):
    when = stamp(value)
    return round(when.timestamp() * 1000) if when else None


def db_result(tool, uid):
    r = object_value(tool.get("result"))
    if (tool.get("status") != "completed" or r.get("rejected") is not False or
        set(r) - {"output", "rejected", "exitCode", "exit_code"} or
        r.get("exit_code", 0) != 0 or r.get("exitCode", 0) != 0 or not isinstance(r.get("output"), str)):
        return False
    return [s for s in r["output"].splitlines() if s.startswith("trace ")] == ["trace " + uid]


def db_start(path, case, peers):
    if not path or not case.history.started:
        return None
    event = case.start
    at = ms(event["at"])
    others = [ms(e["at"]) for c in peers for e in (c.start, c.end) if e and canon.event_time(e)]
    before = max((t for t in others if t < at), default=0)
    after = min((t for t in others if t > at), default=float("inf"))
    prefix = "bubbleId:" + event["conversation"] + ":"
    hits = []
    try:
        with cursor_db(path) as db:
            for key, value in db.execute("SELECT key,value FROM cursorDiskKV WHERE key GLOB ?", (prefix + "*/t:*",)):
                b = object_value(value.decode() if isinstance(value, bytes) else value)
                t = object_value(b.get("toolFormerData"))
                bubble = b.get("bubbleId", "")
                if (b.get("type") != 2 or t.get("name") != "run_terminal_command_v2" or
                    not re.fullmatch(UUID.pattern + r"/t:toolu_[A-Za-z0-9]{1,64}", bubble) or
                    key != prefix + bubble or bubble.rsplit("/t:", 1)[1] != t.get("toolCallId")):
                    continue
                raw, params = object_value(t.get("rawArgs")), object_value(t.get("params"))
                cmd, cwd = params.get("command"), params.get("cwd")
                if (not isinstance(cmd, str) or not isinstance(cwd, str) or raw.get("command") != cmd or
                    raw.get("conversationId") != event["conversation"] or cwd != raw.get("workingDirectory")):
                    continue
                execs = object_value(params.get("parsingResult")).get("executableCommands") or []
                if not execs or not isinstance(execs[0], dict):
                    continue
                shell = execs[0]
                full = shell.get("fullText") or ""
                argv = shell.get("args") or []
                if (shell.get("name") != "python3" or not all(isinstance(a, dict) and a.get("type") == "word" for a in argv)
                    or shlex.split(full) != ["python3", *[a.get("value") for a in argv]] or
                    not (cmd == full or cmd.startswith(full + " && ")) or cmd.count(" trace start ") != 1):
                    continue
                inv = list(commands(full))
                if len(inv) != 1 or inv[0][0] != "start" or not matching_start(inv[0][1], event, cwd):
                    continue
                a, z = b.get("startedAtMs"), b.get("completedAtMs")
                if type(a) is not int or type(z) is not int or ms(b.get("createdAt")) != a:
                    hits.append(None)
                    continue
                if not (before <= a < at + 1000 and a <= z < after and z >= at):
                    continue
                possible = [c for c in peers if c.history.started and a < ms(c.start["at"]) + 1000 and
                            z >= ms(c.start["at"]) and matching_start(inv[0][1], c.start, cwd)]
                hits.append(key if possible == [case] and db_result(t, event["id"]) else None)
    except (OSError, ValueError, TypeError, sqlite3.Error):
        return None
    return {"source": "cursor-db", "location": f"{path}#{hits[0]}"} if len(hits) == 1 and hits[0] else None


def cursor_boundaries(cases, session, database):
    # End commands name their unit; earlier/later fixed calls then disambiguate repeated starts.
    candidates = {}
    order = {}
    for case in cases:
        for verb, e in (("start", case.start), ("end", case.end)):
            if e:
                key = (case, verb)
                candidates[key] = cursor_hits(case, session, verb) if session else []
                order[key] = (canon.event_time(e), str(case.store), e["_line"])
    fixed = {}
    while True:
        claimed = {call.place for call in fixed.values()}
        remaining = {}
        for key, hits in candidates.items():
            if key in fixed:
                continue
            hits = [h for h in hits if h.place not in claimed]
            for k, anchor in fixed.items():
                if order[key][0] and order[k][0] and (key[0].store == k[0].store or order[key][0] != order[k][0]):
                    if order[k] < order[key]:
                        hits = [h for h in hits if h.place > anchor.place]
                    elif order[k] > order[key]:
                        hits = [h for h in hits if h.place < anchor.place]
            remaining[key] = hits
        used = defaultdict(int)
        for hits in remaining.values():
            for c in hits:
                used[c.place] += 1
        new = {k: h[0] for k, h in remaining.items() if len(h) == 1 and used[h[0].place] == 1}
        if not new:
            break
        fixed.update(new)
    for case in cases:
        case.host_session = session
        for verb in ("start", "end"):
            c = fixed.get((case, verb))
            if c:
                case.data["host_" + verb] = {"source": "export", "location": loc(session.path, c.line)}
            elif verb == "start" and not remaining.get((case, verb)):
                receipt = db_start(database, case, cases)
                if receipt:
                    case.data["host_start"] = receipt
        case.host_span = tuple(fixed[(case, v)].line if (case, v) in fixed else None for v in ("start", "end"))


def attach_hosts(cases, args):
    cursors = defaultdict(list)
    for case in cases:
        case.data.update(host_start=MISSING, host_end=MISSING, worker_attempts=[],
                         fresh_subagents=UNKNOWN, parent_cost={"wall_seconds": case.data["wall_seconds"],
                                                              "tokens": UNKNOWN, "locations": []})
        conv = case.start.get("conversation")
        if case.start.get("host") == "cursor" and isinstance(conv, str) and UUID.fullmatch(conv):
            cursors[conv].append(case)
    for conv, group in cursors.items():
        matches = list((args.cursor_home / "projects").glob(f"*/agent-transcripts/{conv}/{conv}.jsonl"))
        try:
            session = CursorSession(matches[0]) if len(matches) == 1 else None
        except OSError:
            session = None
        cursor_boundaries(group, session, args.cursor_state_db)

    from trace_codex import codex_boundaries
    return codex_boundaries([c for c in cases if c.start.get("host") == "codex"], args.codex_home)
