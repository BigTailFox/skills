"""Bind case-local slot assignments and measurements to the evidence each supervisor published."""
from pathlib import Path

from replay_git import ReplayError, json_bytes, sha1_object, sha256
from replay_storage import decode, job_layout, publish_json


def check(condition, detail):
    if not condition:
        raise ReplayError("sealed attempt " + detail)


def new_attempt(ident, pair, arm):
    return dict(id=ident, pair=pair, arm=arm, outcome="pending", reason=None, roles={}, wall_seconds=None,
                worker_status=None, boundary_violation=None)


def dispatch_digests(job):
    names = ("request.json", "dispatch.json")
    return {name: sha256((job / name).read_bytes()) if (job / name).is_file() else None for name in names}


def slot_record(journal, receipt, row, job):
    profile = {k: journal.get(k) for k in ("case", "blind_key", "runner", "runner_sha256", "config_sha256",
                                           "receipt_sha256", "config", "roles", "test_grants")}
    return dict(schema=1, id=row["id"], pair=row["pair"], arm=row["arm"], suite=receipt["suites"][row["arm"]],
                profile_sha256=sha256(json_bytes(profile)), dispatch=dispatch_digests(job))


def write_terminal(job, record):
    body = dict(record, slot_sha256=sha256((job / "slot.json").read_bytes()))
    publish_json(job / "terminal.json", dict(body, seal_sha256=sha256(json_bytes(body))), once=True)


def terminal_observation(job):
    record = decode((job / "terminal.json").read_bytes(), "terminal record")
    if (job / "slot.json").exists():
        seal = record.pop("seal_sha256", None)
        check(seal == sha256(json_bytes(record)) and
              record.get("slot_sha256") == sha256((job / "slot.json").read_bytes()), "terminal or slot digest differs")
    else:
        check("slot_sha256" not in record and "seal_sha256" not in record, "slot binding missing")
    if "preflight" in record:
        return dict(outcome="incompatible", reason=record["preflight"])
    observed = {k: record.get(k) for k in ("started", "ended", "wall_seconds", "returncode")}
    if "result" in record:
        check(sha256((job / "stdout").read_bytes()) == record.get("stdout_sha256"), "terminal result digest differs")
        observed.update(record["result"])
    code = record.get("returncode")
    if code and observed.get("outcome") != "incompatible":
        detail = observed.get("reason") or record.get("error")
        reason = f"observed runner termination ({code})"
        stopped = code < 0 or observed.get("outcome") == "stopped"
        observed.update(outcome="stopped" if stopped else "failed", reason=reason + (": " + detail if detail else ""))
    elif record.get("error"):
        observed.update(outcome="failed", reason=record["error"])
    check(observed.get("outcome") in ("completed", "stopped", "failed", "incompatible"), "terminal outcome unavailable")
    return observed


def verify_legacy(private, receipt, journal, records):
    """The original controller dispatched the first pass serially in alternating order.

    With a retry or a missing boundary, the old files may not identify the paid slot.
    Check both the dispatch order and its installation before accepting that assignment.
    """
    by_start = []
    suites = {}
    for arm in ("candidate", "recorded"):
        root = private / "suites" / arm
        suite = {}
        for p in root.rglob("*"):
            if p.is_file():
                logical = Path(".agents/skills") / p.relative_to(root)
                resolved = (private / "input" / logical).resolve()
                check(resolved.is_relative_to(private / "input"), "legacy suite path escapes the frozen input")
                suite[resolved.relative_to(private / "input").as_posix()] = sha1_object(b"blob", p.read_bytes()).hex()
        suites[arm] = suite
    for row, job, observed in records:
        check(observed and observed.get("started") and observed.get("ended"), "legacy slot has no verified dispatch interval")
        check(all((job / n).is_file() for n in ("dispatch.json", "request.json")), "legacy slot has no retained dispatch")
        spec = decode((job / "dispatch.json").read_bytes(), "legacy dispatch")
        req = decode((job / "request.json").read_bytes(), "legacy request")
        workspace = Path(req.get("workspace", ""))
        skills = ".claude/skills" if receipt["host"] == "claude-code" else ".agents/skills"
        check(workspace.is_absolute() and workspace.parts[-3:] == ("work", row["id"], "workspace") and
              req.get("output") == str(workspace.parent / "output") and req.get("skills") == str(workspace / skills),
              "legacy workspace or output differs from dispatch")
        check(req.get("attempt") == row["id"] and req.get("roles") == journal["roles"] and
              req.get("task") == receipt["task"] and req.get("host") == receipt["host"] and
              req.get("kind") == receipt["kind"] and req.get("config_digest") == journal["config_sha256"] and
              spec.get("runner") == journal["runner"] and spec.get("runner_sha256") == journal["runner_sha256"],
              "legacy dispatch identity differs")
        loads = spec.get("loads", {})
        expected = suites[row["arm"]]
        check(all(loads.get(k) == v for k, v in expected.items()), "legacy installation differs")
        by_start.append((observed["started"], observed["ended"], row))
    previous_end = None
    for i, (started, ended, row) in enumerate(sorted(by_start, key=lambda v: v[0])):
        pair = i // 2 + 1
        arms = ("recorded", "candidate") if pair % 2 else ("candidate", "recorded")
        check((previous_end is None or previous_end < started) and started <= ended and
              row["pair"] == pair and row["arm"] == arms[i % 2], "legacy slot order cannot be independently verified")
        # On a restart an earlier unsuccessful slot may be retried before the next pair.
        # Older records did not bind that retry to a slot.
        check(i == len(by_start) - 1 or row["outcome"] in ("completed", "incompatible"), "legacy retries are ambiguous")
        previous_end = ended


def verify_attempts(private, receipt, journal, *, resuming=False):
    legacy = []
    seen = set()
    check(isinstance(journal.get("attempts"), list) and type(journal.get("repetitions")) is int,
          "journal has invalid paired slots")
    for row in journal["attempts"]:
        check(isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"] not in seen and
              type(row.get("pair")) is int and 1 <= row["pair"] <= journal["repetitions"] and
              row.get("arm") in ("recorded", "candidate"), "journal has invalid paired slots")
        seen.add(row["id"])
        job = job_layout(private.parent, row["id"])
        initial = new_attempt(row["id"], row["pair"], row["arm"])
        slot = job / "slot.json"
        if slot.is_file():
            check(decode(slot.read_bytes(), "sealed attempt slot") == slot_record(journal, receipt, row, job),
                  "slot or profile differs from dispatch")
        terminal = (job / "terminal.json").is_file()
        observed = terminal_observation(job) if terminal else None
        if not slot.is_file():
            legacy.append((row, job, observed))
        if resuming and row["outcome"] in ("pending", "uncertain"):
            # The supervisor can finish after the last journal publication. finalize reattaches.
            continue
        if observed is not None:
            initial.update(observed)
        elif row["outcome"] == "uncertain":
            initial.update(outcome="uncertain", reason="dispatch has no verified terminal record")
        check(json_bytes(row) == json_bytes(initial), "observations differ from terminal evidence")
    if legacy:
        verify_legacy(private, receipt, journal, legacy)
