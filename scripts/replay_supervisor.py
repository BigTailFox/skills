"""A case-owned process that retains the dispatch lock through a durable terminal record."""
import datetime
import os
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True

from replay_git import ReplayError, sha256
from replay_protocol import result_for
from replay_slice import evaluate_slice
from replay_storage import decode, publish_json


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def supervise(job):
    spec = decode((job / "dispatch.json").read_bytes(), "dispatch")
    request_bytes = (job / "request.json").read_bytes()
    req = decode(request_bytes, "request")
    terminal = dict(started=None, ended=None, wall_seconds=None, returncode=None, error=None)
    try:
        runner = Path(spec["runner"])
        if (sha256(runner.read_bytes()) != spec["runner_sha256"] or
                sha256(Path(req["config"]).read_bytes()) != req["config_digest"]):
            raise ReplayError("pinned runner or config changed before dispatch")
        with (job / "stdout").open("wb") as out, (job / "stderr").open("wb") as err:
            terminal["started"] = timestamp()
            start = time.monotonic()
            try:
                child = subprocess.run([runner], input=request_bytes, cwd=req["workspace"], stdout=out, stderr=err)
            finally:
                terminal.update(ended=timestamp(), wall_seconds=time.monotonic() - start)
            terminal["returncode"] = child.returncode
            out.flush()
            os.fsync(out.fileno())
        raw = (job / "stdout").read_bytes()
        terminal["stdout_sha256"] = sha256(raw)
        if raw or child.returncode == 0:
            terminal["result"] = result_for(job, req, spec, raw)
            if req["kind"] == "slice":
                evaluate_slice(job, spec, terminal["result"])
    except (ReplayError, OSError) as exc:
        terminal["error"] = str(exc)
    publish_json(job / "terminal.json", terminal)


if __name__ == "__main__":
    # The inherited descriptor is locked before the controller publishes the slot claim.
    # Keep it open until terminal.json and its directory entry have reached storage.
    with os.fdopen(int(sys.argv[2]), "rb") as dispatch_lock:
        supervise(Path(sys.argv[1]))
