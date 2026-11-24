"""Run pinned criteria in a Linux filesystem containing only case-selected inputs."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile

from replay_git import ReplayError, paths_overlap, safe_relative, sha256, write_blob
from replay_protocol import evidence_bytes
from replay_storage import publish


WORK = "/work"
PROBE = "/.replay-probe"


def elf_interpreter(data):
    """Read PT_INTERP without executing project code or running host ldd on it."""
    if not data.startswith(b"\x7fELF"):
        return None
    try:
        endian = {1: "<", 2: ">"}[data[5]]
        word, phoff, phsizes, fileoff, filesize = {
            1: ("I", 28, 42, 4, 16), 2: ("Q", 32, 54, 8, 32)
        }[data[4]]
        start, = struct.unpack_from(endian + word, data, phoff)
        stride, count = struct.unpack_from(endian + "HH", data, phsizes)
        if stride < filesize + struct.calcsize(word) or start + count * stride > len(data):
            raise ValueError
        for offset in range(start, start + count * stride, stride):
            if struct.unpack_from(endian + "I", data, offset)[0] == 3:
                first, = struct.unpack_from(endian + word, data, offset + fileoff)
                size, = struct.unpack_from(endian + word, data, offset + filesize)
                path = data[first:first + size]
                if len(path) != size or not path.startswith(b"/") or not path.endswith(b"\0") or b"\0" in path[:-1]:
                    raise ValueError
                return os.fsdecode(path[:-1])
    except (KeyError, IndexError, struct.error, ValueError) as exc:
        raise ReplayError("test runtime has an invalid ELF header") from exc
    return None


def sandbox_grants(config, private, receipt):
    tools, runtime = {}, {}
    reserved = {WORK, PROBE, "/proc", "/dev", "/sys", str(private.parent)}

    def reserve(target):
        if (not isinstance(target, str) or not target.startswith("/") or "\0" in target or
                any(p in ("", ".", "..") or p.lower() == ".git" for p in target[1:].split("/"))):
            raise ReplayError("grant requires a normalized absolute target file")
        if any(paths_overlap(target, p) for p in reserved):
            raise ReplayError(f"overlapping or reserved test grant: {target}")
        reserved.add(target)

    for name in config["test_tools"]:
        if "\0" in name or name in (".", "..") or ("/" in name and not name.startswith("/")):
            raise ReplayError("test tool grant must use a command name or absolute path")
        target = name if "/" in name else shutil.which(name) or "/usr/bin/" + name
        reserve(target)
        try:
            source = Path(target).resolve()
        except (OSError, RuntimeError) as exc:
            raise ReplayError("cannot resolve test tool grant") from exc
        if source.is_relative_to(private.parent):
            raise ReplayError("test tool grant points inside the private case")
        if source.exists() and not source.is_file():
            raise ReplayError("test tool grant must be a regular executable file")
        tools[target] = source if source.is_file() and os.access(source, os.X_OK) else None

    mappings = config["settings"].get("test_runtime_files", [])
    if not isinstance(mappings, list):
        raise ReplayError("runtime grants must be an array")
    for mapping in mappings:
        if (not isinstance(mapping, dict) or mapping.keys() != {"fixture", "target"} or
                not isinstance(mapping["fixture"], str) or mapping["fixture"] not in receipt["fixtures"]):
            raise ReplayError("runtime grant must name a prepared fixture file")
        reserve(mapping["target"])
        runtime[mapping["target"]] = mapping["fixture"]

    # Pin executable bytes once for both arms, even if the operator later repairs a host tool.
    pinned = {}
    for target, source in tools.items():
        pinned[target] = None
        if source is not None:
            data = source.read_bytes()
            digest = sha256(data)
            saved = private / "test-tools" / digest
            publish(saved, data)
            saved.chmod(0o500)
            pinned[target] = digest
    return dict(tools=pinned, runtime=runtime)


class CriterionSandbox:
    def __init__(self, job, grants, files, fixtures):
        self.job = job
        self.files = files
        self.fixtures = {}
        self.tools = grants["tools"]
        self.mounts = {}
        self.contents = {WORK + "/" + name: entry for name, entry in files.items()}
        private = job.parents[1]
        for target, digest in self.tools.items():
            if digest is not None:
                name = "test-tools/" + digest
                data = evidence_bytes(private, dict(path=name, sha256=digest))
                self.mounts[target] = private / name
                self.contents[target] = "100755", data
        for name, spec in fixtures.items():
            safe_relative(name)
            if any(paths_overlap(name, path) for path in files):
                raise ReplayError(f"worker tree obstructs a fixture destination: {name}")
            data = evidence_bytes(private / "fixtures", dict(path=name, sha256=spec["sha256"]))
            self.fixtures[name] = spec["mode"], data
            self.contents[WORK + "/" + name] = self.fixtures[name]
        for target, fixture in grants["runtime"].items():
            self.mounts[target] = private / "fixtures" / fixture
            self.contents[target] = self.fixtures[fixture]
        executable = shutil.which("bwrap") if sys.platform == "linux" else None
        if not executable or Path(executable).resolve().is_relative_to(private.parent):
            raise ReplayError("Linux test sandbox unavailable: no Bubblewrap outside the case")
        self.bwrap = str(Path(executable).resolve())
        self.path = ":".join(dict.fromkeys(str(Path(t).parent) for t in self.tools))

    def invoke(self, root, argv, *, writable):
        command = [self.bwrap, "--unshare-all", "--unshare-user", "--unshare-pid", "--unshare-net",
                   "--disable-userns", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
                   "--clearenv", "--setenv", "PATH", self.path, "--setenv", "LC_ALL", "C",
                   "--bind" if writable else "--ro-bind", str(root), WORK]
        for target, source in self.mounts.items():
            command.extend(["--ro-bind", str(source), target])
        with tempfile.TemporaryFile(dir=self.job) as status:
            command.extend(["--remount-ro", "/", "--chdir", WORK, "--json-status-fd", str(status.fileno()), "--", *argv])
            run = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, pass_fds=(status.fileno(),),
                                 env={"PATH": os.defpath, "LC_ALL": "C"})
            status.seek(0)
            try:
                events = [json.loads(line) for line in status if line.strip()]
            except ValueError as exc:
                raise ReplayError("unreadable test sandbox status") from exc
        return run, events

    def probe(self, root):
        # A deliberately absent program verifies the empty-root boundary without granting a probe binary.
        result, events = self.invoke(root, [PROBE], writable=False)
        info = events[0] if events else {}
        if (result.returncode == 0 or PROBE.encode() not in result.stderr or
                any("exit-code" in event for event in events) or
                any(type(info.get(ns + "-namespace")) is not int or
                    info[ns + "-namespace"] == os.stat("/proc/self/ns/" + ns).st_ino for ns in ("pid", "net"))):
            detail = result.stderr.decode(errors="replace").strip()
            raise ReplayError("test sandbox unavailable" + (": " + detail if detail else ""))

    def entry(self, name):
        if "/" not in name:
            matches = [target for target in self.tools if Path(target).name == name]
            if len(matches) != 1:
                raise ReplayError(f"test executable missing or ambiguous in grants: {name}")
            name = matches[0]
        path = os.path.normpath(os.path.join(WORK, name))
        if not path.startswith(WORK + "/") and (path not in self.tools or self.tools[path] is None):
            raise ReplayError(f"test executable unavailable in grants: {name}")
        return path

    def executable(self, path):
        # Resolve links in the sandbox's file map. An absolute worker link has no meaning on the host.
        pending = path.split("/")[::-1]
        parts, links = [], 0
        while pending:
            component = pending.pop()
            if component in ("", "."):
                continue
            if component == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(component)
            mode, data = self.contents.get("/" + "/".join(parts), (None, None))
            if mode == "120000":
                links += 1
                if links > 40:
                    raise ReplayError("test runtime has a cyclic executable link")
                parts.pop()
                target = os.fsdecode(data)
                if target.startswith("/"):
                    parts.clear()
                pending.extend(reversed(target.split("/")))
        resolved = "/" + "/".join(parts)
        mode, data = self.contents.get(resolved, (None, None))
        if mode != "100755":
            raise ReplayError(f"test runtime executable missing: {path}")
        return resolved, data

    def check_runtime(self, root, path, chain=()):
        path, data = self.executable(path)
        if path in chain or len(chain) >= 40:
            raise ReplayError("test runtime has a cyclic or excessive interpreter chain")
        if data.startswith(b"#!"):
            words = data.partition(b"\n")[0][2:].split(None, 1)
            if not words:
                raise ReplayError("test runtime script interpreter missing")
            interpreter = os.fsdecode(words[0])
            self.check_runtime(root, interpreter, (*chain, path))
            if interpreter in ("/usr/bin/env", "/bin/env") and len(words) == 2:
                argument = os.fsdecode(words[1]).strip()
                try:
                    names = shlex.split(argument[2:]) if argument.startswith("-S") else [argument]
                except ValueError as exc:
                    raise ReplayError("test runtime env interpreter cannot be determined") from exc
                if not names or names[0].startswith("-") or "=" in names[0]:
                    raise ReplayError("test runtime env interpreter cannot be determined")
                self.check_runtime(root, self.entry(names[0]), (*chain, path))
            return
        loader = elf_interpreter(data)
        if loader:
            self.executable(loader)
            result, events = self.invoke(root, [loader, "--list", path], writable=False)
            missing = re.search(rb"^\s*\S+\s+=>\s+not found\s*$", result.stdout, re.M)
            if missing or result.returncode or [e["exit-code"] for e in events if "exit-code" in e] != [0]:
                detail = (missing.group() if missing else result.stderr).decode(errors="replace").strip()
                raise ReplayError("test runtime dependencies unavailable" + (": " + detail if detail else ""))

    def missing_child(self, root, stderr):
        # A nonzero test exit alone says nothing about its prerequisites. Corroborate
        # the child-launch diagnostic from the C locale with the pinned filesystem.
        diagnostic = stderr.decode(errors="replace")
        for path, digest in self.tools.items():
            names = (path, Path(path).name)
            command = "(?:" + "|".join(map(re.escape, names)) + ")"
            if not re.search(r"(?:^|:\s+)[\x27\x22]?" + command + r"[\x27\x22]?:\s+"
                             r"(?:command not found|not found|No such file or directory)\s*$|"
                             r"No such file or directory:\s+[\x27\x22]" + command + r"[\x27\x22]\s*$", diagnostic, re.M):
                continue
            if digest is None:
                return f"granted child executable unavailable: {path}"
            try:
                self.check_runtime(root, path)
            except ReplayError as exc:
                return str(exc)
        return None

    def run(self, argv):
        entry = self.entry(argv[0])
        with tempfile.TemporaryDirectory(dir=self.job, prefix="criterion-") as directory:
            root = Path(directory)
            for source in (self.files, self.fixtures):
                for name, (mode, data) in source.items():
                    write_blob(root, name, mode, data)
            self.probe(root)
            self.check_runtime(root, entry)
            result, events = self.invoke(root, argv, writable=True)
            exits = [e["exit-code"] for e in events if "exit-code" in e]
            if exits != [result.returncode]:
                return None, result.stdout, result.stderr, "test sandbox or executable could not start"
            if result.returncode:
                reason = self.missing_child(root, result.stderr)
                if reason:
                    return None, result.stdout, result.stderr, reason
            return result.returncode, result.stdout, result.stderr, None
