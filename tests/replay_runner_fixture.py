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


def result_bundle(spec):
    for name in spec.get("delete", []):
        (workspace / name).unlink()
    for name, entry in spec.get("files", {}).items():
        dest = workspace / name
        mode, content = entry if isinstance(entry, list) else ("100644", entry)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        if mode == "120000":
            dest.symlink_to(content)
        else:
            dest.write_bytes(content.encode())
            dest.chmod(int(mode, 8) & 0o777)
    git("add", "-A", "--", ".")
    if spec.get("force"):
        git("add", "-f", "--", spec["force"])
    if spec.get("gitlink"):
        git("update-index", "--add", "--cacheinfo", "160000," + git("rev-parse", "HEAD") + ",module")
    for name, target in spec.get("links", {}).items():
        blob = subprocess.check_output(["git", "-C", workspace, "hash-object", "-w", "--stdin"], input=target.encode())
        git("update-index", "--add", "--cacheinfo", "120000," + blob.decode().strip() + "," + name)
    parents = ["-p", "HEAD"] if spec.get("history") or spec.get("prerequisite") else []
    commit = git("-c", "user.name=Peer", "-c", "user.email=peer@localhost", "commit-tree", git("write-tree"),
                 *parents, "-m", "Sealed terminal tree")
    ref = spec.get("ref", "refs/replay/result")
    git("update-ref", ref, commit)
    path = output / "result.bundle"
    refs = [ref]
    if spec.get("extra"):
        git("update-ref", "refs/heads/extra", commit)
        refs.append("refs/heads/extra")
    if spec.get("prerequisite"):
        refs.append("^HEAD")
    git("bundle", "create", "--version=" + str(spec.get("version", 3)), str(path), *refs)
    if spec.get("wrong_format"):
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b"@object-format=sha1\n", b"@object-format=sha256\n", 1))
    if spec.get("corrupt"):
        return dict(path=path.name, sha256="1" * 64)
    return dict(path=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


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
    default = "No findings.\n\nVerdict: approve\n"
    if key == "worker":
        default = "Status: " + str(action.get("envelope", {}).get("worker_status", "done")) + "\n"
    text = action.get("reports", {}).get(key, default)
    text = text.replace("{workspace}", str(workspace))
    report = None if key == "parent" else evidence(key + ".md", text.encode())
    roles[key] = dict(settings, loaded=[loaded], report=report, brief=None,
                      tokens=dict(input=11, cached_input=3, output=5, reasoning_output=2))
result = dict(schema=1, attempt=request["attempt"], config_digest=request["config_digest"], host=request["host"],
              outcome="completed", reason=None, worker_status=None, roles=roles, artifact=None, boundary_violation=None)
if request["kind"] == "slice":
    result["worker_status"] = "done"
    brief = action.get("brief", "PRIVATE initial worker brief")
    roles["worker"]["brief"] = evidence("worker-brief.txt", brief.encode()) if brief is not None else None
    bundle = action.get("bundle", config["settings"].get("bundle"))
    if bundle is not None:
        result["artifact"] = result_bundle(bundle)
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
