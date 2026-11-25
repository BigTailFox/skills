"""Exercise the installed Cursor review launcher offline with a single local provider."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


SESSION = "fixture-cursor"
PREVIOUS = b"Previous report.\n"
REPORT = b"0123456789abcdef" * 16384 + b"\nreview\nVerdict: approve\n"

# The provider owns both the child that holds its output pipe and the terminal report.
PROVIDER = '''#!/usr/bin/env python3
from pathlib import Path
import json, os, subprocess, sys

with Path("provider-calls").open("a") as calls:
    print("called", file=calls)
if Path("provider-disabled").exists():
    sys.exit(97)
assert sys.stdin.buffer.read() == Path("prompt").read_bytes()
print(json.dumps(dict(type="system", subtype="init", session_id="fixture-cursor")), flush=True)
if os.environ["R007_DENIAL"] == "cleanup":
    helper = subprocess.Popen([sys.executable, "-c", """from pathlib import Path
import time
end = time.monotonic() + 15
while not Path('release-helper').exists() and time.monotonic() < end:
    time.sleep(.05)
"""], start_new_session=True)
    Path("helper-pid").write_text(str(helper.pid))
elif os.environ["R007_DENIAL"] == "native":
    with Path("help-pipe").open("wb", buffering=0) as sink:
        helper = subprocess.Popen(["./cursorsandbox", "--help"], stdin=subprocess.DEVNULL, stdout=sink, stderr=sink)
    Path("helper-pid").write_text(str(helper.pid))
print(json.dumps(dict(type="result", subtype="success", is_error=False,
                      session_id="fixture-cursor", result=Path("expected").read_text())), flush=True)
'''

# Observe the first launch at the OS boundary. The native case makes the real signal call.
FAULTS = '''
from pathlib import Path
import errno, json, os, signal, sys

if sys.argv[1:2] == ["_supervise"] and os.environ["R007_DENIAL"] in {"cleanup", "native"}:
    original_kill = os.kill
    def kill(pid, sig):
        helper = Path("helper-pid")
        if sig != signal.SIGKILL or not helper.is_file() or pid != int(helper.read_text()):
            return original_kill(pid, sig)
        try:
            if os.environ["R007_DENIAL"] == "cleanup":
                raise PermissionError(errno.EACCES, os.strerror(errno.EACCES))
            return original_kill(pid, sig)
        except PermissionError:
            Path("denied-cleanup-pid").write_text(str(pid))
            raise
    os.kill = kill

if sys.argv[1:2] == ["cursor"] and os.environ["R007_DENIAL"] == "replace":
    original_replace = os.replace
    def replace(source, destination):
        if Path(destination).resolve() == Path("cross-family.md").resolve():
            Path("denied-replace.json").write_text(json.dumps([str(source), str(destination)]))
            raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), str(source), None, str(destination))
        return original_replace(source, destination)
    os.replace = replace
'''


def run(launcher, work, case, *args):
    # PATH resolves the provider to this case's stand-in.
    env = dict(PATH=str(work), PYTHONPATH=str(work), PYTHONDONTWRITEBYTECODE="1",
               CANON_REVIEW_TIMEOUT_SECONDS="5", R007_DENIAL=case, LC_ALL="C.UTF-8")
    result = subprocess.run([sys.executable, str(launcher), *args], cwd=work, env=env,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=12)
    (work / (args[0] + ".log")).write_text(result.stdout + result.stderr)
    return result


def recover(launcher, work, case, initial, output):
    assert initial.returncode == 1 and not initial.stdout, (initial.stdout, initial.stderr)
    assert output.read_bytes() == PREVIOUS
    source, destination = map(Path, json.loads((work / "denied-replace.json").read_text()))
    assert destination == output and source.read_bytes() == REPORT
    assert f"[Errno 13] Permission denied: '{source}' -> '{output}'" in initial.stderr, initial.stderr
    binding = json.loads((source.parent / "state.json").read_text())
    assert (binding["phase"], binding["directory"], binding["report"], binding["provider"],
            binding["model"], binding["session_id"], binding["digest"]) == (
        "ready", str(work), str(output), "cursor", "fixture-model", SESSION, hashlib.sha256(REPORT).hexdigest())
    (work / "provider-disabled").touch()
    return run(launcher, work, case, "resume", output.name)


def exercise(launcher, base, case, helper=None):
    work = Path(tempfile.mkdtemp(prefix=case + ".", dir=base))
    print(f"Case files: {work}", flush=True)
    (work / "python3").symlink_to(sys.executable)
    provider = work / "agent"
    provider.write_text(PROVIDER)
    provider.chmod(0o700)
    (work / "sitecustomize.py").write_text(FAULTS)
    (work / "prompt").write_text("Review the fixture for " + case + ".\n")
    (work / "expected").write_bytes(REPORT)
    output = work / "cross-family.md"
    output.write_bytes(PREVIOUS)
    pipe = None
    try:
        if helper:
            # Keep the real helper alive on its help text until the supervisor exits.
            (work / "cursorsandbox").symlink_to(helper)
            fifo = work / "help-pipe"
            os.mkfifo(fifo, mode=0o600)
            pipe = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
            size = fcntl.fcntl(pipe, fcntl.F_GETPIPE_SZ)
            written = os.write(pipe, b"x" * size)
            assert written == size
        initial = run(launcher, work, case, "cursor", "fixture-model", "prompt", output.name)
        warnings = initial.stderr.count("review cleanup warning:")
        if case in {"cleanup", "native"}:
            assert (work / "helper-pid").is_file(), initial.stderr
            helper_pid = (work / "helper-pid").read_text()
            denied = work / "denied-cleanup-pid"
            assert denied.is_file() and denied.read_text() == helper_pid, initial.stderr
            assert initial.returncode == 0 and warnings == 1, initial.stderr
            assert f"descendant PID {helper_pid}: [Errno 13]" in initial.stderr, initial.stderr
            final = initial
        else:
            assert warnings == 0, initial.stderr
            final = recover(launcher, work, case, initial, output)
        assert final.returncode == 0, final.stderr
        assert final.stdout.splitlines() == ["session id: " + SESSION], final.stdout
        published = output.read_bytes()
        assert published == REPORT
        calls = (work / "provider-calls").read_text().splitlines()
        assert calls == ["called"], calls
        receipt = dict(case=case, initial_exit=initial.returncode, cleanup_warnings=warnings,
                       session_id=final.stdout.strip().split(": ", 1)[1], provider_calls=len(calls),
                       report_bytes=len(published), sha256=hashlib.sha256(published).hexdigest())
        if case == "replace":
            receipt["resume_exit"] = final.returncode
        print(json.dumps(receipt, sort_keys=True))
    finally:
        (work / "release-helper").touch()
        if pipe is not None:
            os.close(pipe)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scratch", type=Path, help="parent directory for fresh case files")
    parser.add_argument("--launcher", type=Path, default=Path.home() / ".config/canon/review-live.py")
    parser.add_argument("--cursor-helper", type=Path,
                        help="also exercise the machine's actual signal denial with cursorsandbox --help")
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    launcher = args.launcher.resolve(strict=True)
    for case in ("cleanup", "replace"):
        exercise(launcher, args.scratch.resolve(), case)
    if args.cursor_helper:
        exercise(launcher, args.scratch.resolve(), "native", args.cursor_helper.resolve(strict=True))
