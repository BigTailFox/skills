#!/usr/bin/env python3
"""Deterministic offline peer of the replay v1 wire protocol, copied as an executable by CLI tests."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def evidence(name, data):
    (output / name).write_bytes(data)
    return dict(path=name, sha256=hashlib.sha256(data).hexdigest())


def git(*args):
    return subprocess.check_output(["git", "-C", str(workspace), *args]).decode().strip()


request = json.load(sys.stdin)
workspace = Path(request["workspace"])
output = Path(request["output"])
config = json.loads(Path(request["config"]).read_bytes())
entry = Path(request["skills"]) / "canon/SKILL.md"
data = entry.read_bytes()
loaded = {"path": entry.resolve().relative_to(workspace).as_posix(),
          "blob": hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()}
observation = {k: request[k] for k in ("attempt", "workspace", "roles", "task", "stop_after")}
observation.update(suite=data.decode().strip(), skills=Path(request["skills"]).relative_to(workspace).as_posix(),
                   head=git("rev-parse", "HEAD"), pid=os.getpid(), supervisor=os.getppid(),
                   refs=git("for-each-ref", "--format=%(refname)").splitlines(), remotes=git("remote").splitlines(),
                   untracked=git("ls-files", "--others", "--exclude-standard").splitlines(),
                   fixture_executable=os.access(workspace / "dependency", os.X_OK),
                   claude_link=(workspace / ".claude/skills/canon").resolve() == entry.parent.resolve())
with open(config["settings"]["log"], "a") as stream:
    stream.write(json.dumps(observation) + "\n")
actions = config["settings"].get("actions", [])
index = len(Path(config["settings"]["log"]).read_text().splitlines()) - 1
action = actions[index] if index < len(actions) else {}
hold = config["settings"].get("hold")
if hold:
    deadline = time.monotonic() + 15
    while Path(hold).exists() and time.monotonic() < deadline:
        time.sleep(0.025)
roles = {}
for key, settings in request["roles"].items():
    text = action.get("reports", {}).get(key, "No findings.\n\nVerdict: approve\n")
    text = text.replace("{workspace}", str(workspace))
    report = None if key == "parent" else evidence(key + ".md", text.encode())
    roles[key] = dict(settings, loaded=[loaded], report=report, brief=None,
                      tokens=dict(input=11, cached_input=3, output=5, reasoning_output=2))
result = dict(schema=1, attempt=request["attempt"], config_digest=request["config_digest"], host=request["host"],
              outcome="completed", reason=None, worker_status=None, roles=roles, artifact=None, boundary_violation=None)
result.update(action.get("envelope", {}))
for key, patch in action.get("roles", {}).items():
    roles[key].update(patch)
for key in action.get("remove", []):
    roles.pop(key)
if action.get("escape"):
    ref = roles[action["escape"]]["report"]
    original = output / ref["path"]
    copy = workspace / "outside-the-output"
    original.rename(copy)
    original.symlink_to(copy)
if action.get("corrupt"):
    (output / roles[action["corrupt"]]["report"]["path"]).write_text("post-return mismatch")
if action.get("loaded_path"):
    roles["parent"]["loaded"] = [{"path": action["loaded_path"], "blob": loaded["blob"]}]
if action.get("change_loaded"):
    entry.write_bytes(b"different effective skill")
json.dump(result, sys.stdout)
sys.exit(action.get("exit", 0))
