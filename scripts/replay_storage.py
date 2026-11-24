"""Durable case-local publications shared by the controller and its dispatch supervisor."""
import json
import math
import os
from pathlib import Path
import stat
import tempfile

from replay_git import ReplayError, json_bytes


def case_path(root, relative, *, directory=False):
    """Check every case-owned component, including a dangling link or an occupied future output."""
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts or root.is_symlink():
        raise ReplayError(f"invalid case path: {relative}")
    selected = root
    for i, part in enumerate(relative.parts, 1):
        selected = selected / part
        try:
            entry = selected.lstat()
        except FileNotFoundError:
            continue
        want_dir = i < len(relative.parts) or directory
        if not (stat.S_ISDIR(entry.st_mode) if want_dir else stat.S_ISREG(entry.st_mode) and entry.st_nlink == 1):
            raise ReplayError(f"invalid case path: {selected}")
    return selected


def case_layout(root):
    for name in ("private", "work", "private/jobs", "private/input/.git", "private/fixtures", "private/suites/recorded",
                 "private/suites/candidate", "private/test-tools", "private/judgments", "blind/evidence"):
        case_path(root, name, directory=True)
    for name in ("private/run.lock", "private/run.json", "private/receipt.json", "private/receipt.sha256",
                 "blind/packet.json", "blind/judgments-template.json", "result.json"):
        case_path(root, name)
    # The verified input has its own Git directory. Git commands such as write-tree may write there.
    git_dir = root / "private/input/.git"
    for current, dirs, files in os.walk(git_dir):
        if any((Path(current) / name).is_symlink() for name in dirs + files):
            raise ReplayError("invalid case path in the prepared Git repository")


def job_layout(case, ident):
    if not isinstance(ident, str) or not ident or ident in (".", "..") or "/" in ident or "\0" in ident:
        raise ReplayError("invalid case path for attempt")
    base = Path("private/jobs") / ident
    for name in (base / "evidence", Path("work") / ident / "workspace", Path("work") / ident / "output"):
        case_path(case, name, directory=True)
    for name in ("dispatch.lock", "slot.json", "request.json", "dispatch.json", "terminal.json", "stdout", "stderr",
                 "brief.diff"):
        case_path(case, base / name)
    return case / base


def sync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(path, data, *, once=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".publish-", delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            if once:
                os.link(temp, path)
            else:
                os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
    sync_directory(path.parent)


def publish_json(path, body, *, once=False):
    publish(path, json_bytes(body), once=once)


def decode(data, label):
    def unique(pairs):
        fields = dict(pairs)
        if len(fields) != len(pairs):
            raise ValueError("duplicate field")
        return fields

    def invalid(value):
        raise ValueError(value)

    def finite(raw):
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError("non-finite number")
        return number

    try:
        value = json.loads(data, object_pairs_hook=unique, parse_constant=invalid, parse_float=finite)
        if not isinstance(value, dict):
            raise ValueError("expected an object")
        return value
    except (ValueError, UnicodeError) as exc:
        raise ReplayError(f"invalid {label}: {exc}") from exc
