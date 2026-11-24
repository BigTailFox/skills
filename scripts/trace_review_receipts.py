"""Verify adjudication receipts against their original archive, dispatch and host messages."""
import hashlib
import json
import re
import sqlite3

from trace_hosts import CursorSession, UUID, object_value, parts
from trace_records import identifier, canon, loc
from trace_sqlite import cursor_db


class EvidenceError(ValueError):
    """Only fixed diagnostics may leave the evidence reader."""


def require(condition, reason):
    if not condition:
        raise EvidenceError(reason)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def assignments(cell):
    entries = [pair.split("=") for pair in cell.split()]
    result = dict(entries)
    require(len(result) == len(entries) and all(canon.FINDING_ID_RE.fullmatch(k) for k in result),
            "ambiguous adjudicated finding")
    return result


def model_dispatch(database, receipt, conversation, session, model, prompt):
    require(database and receipt["conversation"] == conversation and receipt["session"] == session,
            "missing model dispatch evidence")
    matches = []
    try:
        with cursor_db(database) as db:
            for key, raw in db.execute("SELECT key,value FROM cursorDiskKV WHERE key GLOB ? AND json_valid(value) "
                                       "AND json_extract(value, '$.toolFormerData.name')='task_v2'",
                                       ("bubbleId:" + conversation + ":*",)):
                tool = json.loads(raw)["toolFormerData"]
                params, result = object_value(tool.get("params")), object_value(tool.get("result"))
                if (tool.get("status") == "completed" and result.get("agentId") == session and
                    (params.get("prompt") or "").strip() == prompt.strip()):
                    matches.append((key, digest(raw.encode() if isinstance(raw, str) else raw), params.get("model")))
    except sqlite3.Error:
        raise EvidenceError("model dispatch unavailable") from None
    require(len(matches) == 1 and matches[0][:2] == (receipt["line"], receipt["sha256"]) and
            identifier(matches[0][2]) and (model is None or matches[0][2] == model),
            "missing or ambiguous model dispatch")
    return f"{database}#{matches[0][0]}", matches[0][2]


def confirmed_fixed(prompt, terminal):
    fixed = set()
    for line in prompt.splitlines():
        if "Fixed findings:" in line:
            fixed.update(re.findall(r"(?:^|;\s*)\s*(F[1-9]\d*)\s*\(", line.partition("Fixed findings:")[2]))
    resolved = set()
    lines = terminal.splitlines()
    for i, line in enumerate(lines):
        bullet = re.match(r"^- \*\*(F[1-9]\d*)\*\*:\s*resolved(?=[.:]|\s*\(|\s*$)", line, re.I)
        heading = re.match(r"^### (F[1-9]\d*)\b", line)
        if bullet:
            resolved.add(bullet[1])
        elif heading and i + 1 < len(lines) and re.match(r"^Resolved(?=[.:]|\s*$)", lines[i+1]):
            resolved.add(heading[1])
    return fixed & resolved


def verified_dispatches(case, archive, first, registered, receipts, database, supplied_models):
    extra = {s["report_stem"]: s for key, s in first.items() if key not in registered}
    require({r["report_stem"] for r in receipts} == extra.keys(), "supplemental host receipt inventory mismatch")
    locations, decisions = {}, {}
    if not extra:
        return locations, decisions
    conv = case.start.get("conversation")
    require(isinstance(case.host_session, CursorSession) and conv and case.host_session.path.stem == conv,
            "supplemental conversation unavailable")
    parent = case.host_session.path
    parents = parent.read_bytes().splitlines()
    actions = ("dispatch", "first", "fixed", "terminal", "decision", "final")
    for stem, source in extra.items():
        sid = source["reviewer_id"]
        require(UUID.fullmatch(sid), "invalid supplemental session")
        subset = [r for r in receipts if r["report_stem"] == stem]
        by_action = {r["evidence"]: r for r in subset}
        require(len(subset) == len(actions)+1 and by_action.keys() == set(actions) | {"model-dispatch"},
                "missing or duplicate supplemental receipt")
        path = parent.parent / "subagents" / (sid + ".jsonl")
        children = path.read_bytes().splitlines()
        content, positions = {}, []
        places = locations[source["reviewer_key"]] = []
        for action in actions:
            r = by_action[action]
            child = action in actions[:4]
            require(r["conversation"] == conv and r["session"] == (sid if child else conv) and
                    re.fullmatch(r"[1-9]\d*", r["line"]), "supplemental host identity mismatch")
            number = int(r["line"])
            raw = (children if child else parents)[number-1]
            require(digest(raw) == r["sha256"], "stale supplemental host receipt")
            event = json.loads(raw)
            want = "user" if action in ("dispatch", "fixed") else "assistant"
            require(event.get("role") == want, "supplemental message role mismatch")
            body = "".join(p["text"] for p in parts(event) if p.get("type") == "text").strip()
            if want == "user" and "<user_query>" in body:
                body = body.partition("<user_query>")[2].partition("</user_query>")[0].strip()
            content[action] = body
            positions.append(number)
            location = loc(path if child else parent, number)
            places.extend([location, r["_location"]])
            if not child:
                decisions[r["line"], r["sha256"]] = location
        require(positions[:4] == sorted(set(positions[:4])) and positions[4] < positions[5],
                "supplemental host receipt order")
        for action, suffix in zip(actions[:4], ("-prompt", "", "-confirm-prompt", "-confirm")):
            blob = archive.read(stem + suffix + ".md")
            require(blob is not None and blob.decode().strip() == content[action], "supplemental archive differs from host")
        db_receipt = by_action["model-dispatch"]
        native, model = model_dispatch(database, db_receipt, conv, sid,
                                       source["model"] if supplied_models else None, content["dispatch"])
        source["model"] = model
        places.extend([native, db_receipt["_location"]])
        accepted = {fid for fid, d in assignments(source["decisions"]).items() if d == "accepted"}
        require(accepted <= confirmed_fixed(content["fixed"], content["terminal"]), "uncorroborated supplemental disposition")
    return locations, decisions


def decision_record(archive, source, parents):
    ref = source.get("decision_locator")
    if not ref:
        return None
    match = re.fullmatch(r"(parent|[A-Za-z0-9_-]+\.md):L([1-9]\d*)", ref)
    require(match, "invalid decision locator")
    name, number = match.groups()
    if name == "parent":
        location = parents.get((number, source.get("decision_sha256")))
        require(location, "unverified parent decision")
        return location
    blob = archive.read(name)
    require(blob is not None and digest(blob.splitlines()[int(number)-1]) == source.get("decision_sha256"),
            "stale archived decision")
    return loc(archive.files[name], int(number))
