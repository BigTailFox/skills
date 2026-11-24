"""Claim slots, reattach to case-owned jobs and publish paired replay evidence."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import uuid

from replay_case import load_case
from replay_git import ReplayError, sha256
from replay_profile import profile
from replay_packet import Packet
from replay_sandbox import sandbox_grants
from replay_storage import decode, publish_json, sync_directory
from replay_workspace import workspace_for


try:
    import fcntl
except ImportError:
    fcntl = None


def save_journal(private, journal):
    slots = {(a["pair"], a["arm"]) for a in journal["attempts"] if a["outcome"] == "completed"}
    missing = [i for i in range(1, journal["repetitions"] + 1)
               if (i, "recorded") not in slots or (i, "candidate") not in slots]
    count = journal["repetitions"] - len(missing)
    journal.update(comparable_pairs=count, incomplete_pairs=missing, sparse_pairs=count < 3)
    publish_json(private / "run.json", journal)


def finalize(job, row):
    terminal = job / "terminal.json"
    if not job.is_dir():
        row.update(outcome="uncertain", reason="dispatch has no verified terminal record")
        return
    if not terminal.exists():
        with (job / "dispatch.lock").open("ab") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not terminal.exists():
                row.update(outcome="uncertain", reason="dispatch has no verified terminal record")
                return
    record = decode(terminal.read_bytes(), "terminal record")
    row.update({k: record.get(k) for k in ("started", "ended", "wall_seconds", "returncode")})
    if "result" in record:
        try:
            raw = (job / "stdout").read_bytes()
            if sha256(raw) != record["stdout_sha256"]:
                raise ReplayError("terminal result digest differs")
            row.update(record["result"])
        except (OSError, ReplayError, KeyError) as exc:
            row.update(outcome="failed", reason=str(exc))
            return
    code = record.get("returncode")
    if code and row["outcome"] != "incompatible":
        detail = row.get("reason") or record.get("error")
        reason = f"observed runner termination ({code})"
        row.update(outcome="stopped" if code < 0 else "failed", reason=reason + (": " + detail if detail else ""))
    elif record.get("error"):
        row.update(outcome="failed", reason=record["error"])


def dispatch(private, receipt, journal, config_path, pair, arm):
    ident = uuid.uuid4().hex
    area = private.parent / "work" / ident
    workspace = area / "workspace"
    job = private / "jobs" / ident
    job.mkdir(parents=True)
    sync_directory(job.parent)
    row = dict(id=ident, pair=pair, arm=arm, outcome="pending", reason=None, roles={}, wall_seconds=None,
               worker_status=None, boundary_violation=None)
    journal["attempts"].append(row)
    try:
        installed, loads, injected = workspace_for(private, workspace, receipt, arm)
    except (ReplayError, OSError) as exc:
        row.update(outcome="incompatible", reason=str(exc))
        save_journal(private, journal)
        return
    output = area / "output"
    output.mkdir()
    request = dict(schema=1, attempt=ident, config_digest=journal["config_sha256"], workspace=str(workspace),
                   skills=str(installed), output=str(output), config=str(config_path), host=receipt["host"],
                   kind=receipt["kind"], roles=journal["roles"], task=receipt["task"],
                   stop_after="worker_report" if receipt["kind"] == "slice" else "first_round_reports")
    publish_json(job / "request.json", request)
    spec = dict(runner=journal["runner"], runner_sha256=journal["runner_sha256"],
                receipt_sha256=journal["receipt_sha256"], loads=loads, injected=injected)
    if receipt["kind"] == "slice":
        spec["test_grants"] = journal["test_grants"]
    publish_json(job / "dispatch.json", spec)
    with (job / "dispatch.lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        save_journal(private, journal)
        try:
            child = subprocess.Popen([sys.executable, Path(__file__).with_name("replay_supervisor.py"), job,
                                      str(lock.fileno())], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True, pass_fds=(lock.fileno(),))
        except OSError as exc:
            publish_json(job / "terminal.json", dict(error=f"cannot start supervisor: {exc}"))
            child = None
    if child is not None:
        child.wait()
    finalize(job, row)
    save_journal(private, journal)


def paired_run(private, receipt, config, config_path, identity, repetitions):
    path = private / "run.json"
    if path.exists():
        journal = decode(path.read_bytes(), "run journal")
        for key, val in identity.items():
            if journal.get(key) != val:
                raise ReplayError(f"pinned {key} changed; cannot resume this run")
    else:
        roles = profile(config, private, receipt)
        journal = dict(schema=1, case=uuid.uuid4().hex, blind_key=secrets.token_hex(32), **identity, roles=roles,
                       config=config, attempts=[])
        if receipt["kind"] == "slice":
            journal["test_grants"] = sandbox_grants(config, private, receipt)
    journal["repetitions"] = max(repetitions, journal.get("repetitions", 0))
    save_journal(private, journal)
    (private.parent / "work").mkdir(mode=0o700, exist_ok=True)
    for row in journal["attempts"]:
        if row["outcome"] in ("pending", "uncertain"):
            finalize(private / "jobs" / row["id"], row)
            save_journal(private, journal)
    for pair in range(1, repetitions + 1):
        arms = ("recorded", "candidate") if pair % 2 else ("candidate", "recorded")
        for arm in arms:
            if any(a["pair"] == pair and a["arm"] == arm and a["outcome"] not in ("failed", "stopped")
                   for a in journal["attempts"]):
                continue
            dispatch(private, receipt, journal, config_path, pair, arm)
    save_journal(private, journal)
    return journal


def run(args):
    if args.repetitions < 3:
        raise ReplayError("at least three paired repetitions are required")
    directory = args.directory.resolve(strict=True)
    private = directory / "private"
    if private.is_symlink() or not private.is_dir():
        raise ReplayError("invalid private case directory")
    if fcntl is None:
        raise ReplayError("this host cannot lock paired dispatches")
    with (private / "run.lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipt = load_case(directory)
        if receipt["kind"] not in ("gate", "code-review", "slice"):
            raise ReplayError("unsupported prepared case kind")
        runner = args.runner.resolve(strict=True)
        if not runner.is_file() or not os.access(runner, os.X_OK):
            raise ReplayError("runner must be an executable regular file")
        config_path = args.runner_config.resolve(strict=True)
        data = config_path.read_bytes()
        identity = dict(runner=str(runner), runner_sha256=sha256(runner.read_bytes()), config_sha256=sha256(data),
                        receipt_sha256=sha256((private / "receipt.json").read_bytes()))
        journal = paired_run(private, receipt, decode(data, "runner configuration"), config_path, identity, args.repetitions)
        packet = Packet(private, receipt, journal).write()
        journal["packet_sha256"] = sha256(packet.read_bytes())
        save_journal(private, journal)
        print(packet)
