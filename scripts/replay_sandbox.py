"""Run pinned criteria in a Linux filesystem containing only case-selected inputs."""
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import time

from replay_git import ReplayError, paths_overlap, safe_relative, sha256, write_blob
from replay_protocol import evidence_bytes
from replay_storage import publish


WORK = "/work"
PROBE = "/.replay-probe"
WITNESS_LOG = "/.replay-prerequisite-use"
CONTROL_SECONDS = 15
MAX_DIAGNOSTIC_PATHS = 16
MAX_CONTROL_RUNS = 40
SHELLS = {"sh", "bash", "dash", "ksh"}
# Leave ordinary quoted strings, escaped characters and comments intact. A matched
# exit contributes evidence only if the unmodified-grants control actually takes it.
NORMALIZER = re.compile(r"""'[^']*'|"(?:\\.|[^"\\])*"|\\.|(?<!\S)\#[^\n]*|
                        (?P<op>\|\|\s*)(?P<exit>(?:exit|return)[ \t]+[0-9]{1,3})(?=[ \t]*(?:$|[\n;&)]))""", re.X | re.S)


def shell_hint_words(text):
    """Keep command-ending newlines while shlex decodes the words on each logical line."""
    lines, line = [], []
    quote, word_start = None, True
    i = 0
    while i < len(text):
        char = text[i]
        i += 1
        if char == "\\" and quote != "'":
            escaped = text[i:i + 1]
            i += len(escaped)
            if escaped != "\n":
                line.append(char + escaped)
                word_start = False
        elif char == "#" and not quote and word_start:
            i = text.find("\n", i)
            if i == -1:
                break
        elif char == "\n" and not quote:
            lines.append("".join(line))
            line.clear()
            word_start = True
        else:
            line.append(char)
            if quote == char:
                quote = None
            elif not quote and char in ("'", '"'):
                quote = char
            word_start = not quote and char in " \t\r;&|()<>"
    lines.append("".join(line))
    tokens = []
    for logical in lines:
        lexer = shlex.shlex(logical, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        words = list(lexer)
        if words:
            if tokens and tokens[-1] not in ("&&", "||", "|", ";", "&", "("):
                tokens.append(";")
            tokens.extend(words)
    return tokens


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
    reserved = {WORK, PROBE, WITNESS_LOG, "/proc", "/dev", "/sys", str(private.parent)}

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

    def invoke(self, root, argv, *, writable, witnesses=(), witness_log=None, deadline=None):
        command = [self.bwrap, "--unshare-all", "--unshare-user", "--unshare-pid", "--unshare-net",
                   "--disable-userns", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
                   "--clearenv", "--setenv", "PATH", self.path, "--setenv", "LC_ALL", "C",
                   "--bind" if writable else "--ro-bind", str(root), WORK]
        for target, source in self.mounts.items():
            command.extend(["--ro-bind", str(source), target])
        for target, witness in witnesses:
            command.extend(["--ro-bind", str(witness), target])
        if witness_log is not None:
            src, target = witness_log
            command.extend(["--bind", str(src), target])
        with tempfile.TemporaryFile(dir=self.job) as status:
            command.extend(["--remount-ro", "/", "--chdir", WORK, "--json-status-fd", str(status.fileno()), "--", *argv])
            timeout = max(0, deadline - time.monotonic()) if deadline is not None else None
            try:
                run = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, pass_fds=(status.fileno(),),
                                     env={"PATH": os.defpath, "LC_ALL": "C"}, timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                raise ReplayError("missing-grant diagnostic exceeded its time limit") from exc
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

    def check_runtime(self, root, path, chain=(), *, deadline=None):
        path, data = self.executable(path)
        if path in chain or len(chain) >= 40:
            raise ReplayError("test runtime has a cyclic or excessive interpreter chain")
        if data.startswith(b"#!"):
            words = data.partition(b"\n")[0][2:].split(None, 1)
            if not words:
                raise ReplayError("test runtime script interpreter missing")
            interpreter = os.fsdecode(words[0])
            self.check_runtime(root, interpreter, (*chain, path), deadline=deadline)
            if interpreter in ("/usr/bin/env", "/bin/env") and len(words) == 2:
                argument = os.fsdecode(words[1]).strip()
                try:
                    names = shlex.split(argument[2:]) if argument.startswith("-S") else [argument]
                except ValueError as exc:
                    raise ReplayError("test runtime env interpreter cannot be determined") from exc
                if not names or names[0].startswith("-") or "=" in names[0]:
                    raise ReplayError("test runtime env interpreter cannot be determined")
                self.check_runtime(root, self.entry(names[0]), (*chain, path), deadline=deadline)
            return
        loader = elf_interpreter(data)
        if loader:
            self.executable(loader)
            result, events = self.invoke(root, [loader, "--list", path], writable=False, deadline=deadline)
            missing = re.search(rb"^\s*\S+\s+=>\s+not found\s*$", result.stdout, re.M)
            if missing or result.returncode or [e["exit-code"] for e in events if "exit-code" in e] != [0]:
                detail = (missing.group() if missing else result.stderr).decode(errors="replace").strip()
                raise ReplayError("test runtime dependencies unavailable" + (": " + detail if detail else ""))

    def materialize(self, root, edits=None):
        for source in (self.files, self.fixtures):
            for name, (mode, data) in source.items():
                write_blob(root, name, mode, edits.get(name, data) if edits else data)

    def normalization_probe(self, argv, destination, prefix):
        """Keep the wrapper's literal exit and observe its incoming shell status in a diagnostic copy."""
        sites = 0

        def instrument(text):
            def insert(match):
                nonlocal sites
                if not match["op"] or sites == MAX_DIAGNOSTIC_PATHS:
                    return match[0]
                sites += 1
                record = f"""printf '{prefix}-{sites} %s\\n' "$?" >> {destination}"""
                return f"{match['op']}{{ {record}; {match['exit']}; }}"
            return NORMALIZER.sub(insert, text)

        command, edits = list(argv), {}
        remaining = 65536
        if Path(self.entry(argv[0])).name in SHELLS:
            for i, arg in enumerate(argv[1:-1], 1):
                if not arg.startswith("-"):
                    break
                if "c" in arg[1:]:
                    text = argv[i + 1]
                    if len(text) <= remaining:
                        command[i + 1] = instrument(text)
                        remaining -= len(text)
                    break
        for arg in argv[:128]:
            path = os.path.normpath(os.path.join(WORK, arg))
            if not path.startswith(WORK + "/"):
                continue
            name = path[len(WORK) + 1:]
            entry = self.files.get(name)
            if not entry or name in edits or entry[0] == "120000" or len(entry[1]) > remaining:
                continue
            data = entry[1]
            head = data.partition(b"\n")[0]
            if not re.match(rb"^#!\s*(?:\S*/)?(?:env\s+)?(?:sh|bash|dash|ksh)(?:\s|$)", head):
                continue
            remaining -= len(data)
            updated = os.fsencode(instrument(os.fsdecode(data)))
            if updated != data:
                edits[name] = updated
        return (command, edits) if sites else None

    def possible_outputs(self, argv, called):
        """Propose paths across possible working directories. Only executions confirm a hint."""
        scripts = list(argv[:128])
        existing = self.files.keys() | self.fixtures.keys()
        directories = {str(parent) for name in existing for parent in Path(name).parents}
        preferred = [WORK]
        hints, guarded, unresolved = {}, {}, set()
        by_name = {name: target for target in called for name in (target, Path(target).name)}
        variable = re.compile(r"\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))")
        expansion = re.compile(r"[$*?`]|\[[^]]+\]")

        def resolve(word, bindings):
            return variable.sub(lambda m: bindings.get(m[1] or m[2], m[0]), word)

        def command_operand(tokens, index):
            # command -p executes its operand. A lookup (-v/-V) or invalid option executes none.
            while index < len(tokens) and tokens[index].startswith("-"):
                option = tokens[index]
                index += 1
                if option == "--":
                    break
                if not re.fullmatch(r"-p+", option):
                    return None
            return index

        for arg in argv[:128]:
            entry = self.contents.get(os.path.normpath(os.path.join(WORK, arg)))
            if entry and entry[0] != "120000" and len(entry[1]) <= 65536 and b"\0" not in entry[1]:
                scripts.append(os.fsdecode(entry[1]))
        remaining = 65536
        for script in scripts:
            if remaining <= 0:
                break
            text = script[:remaining]
            remaining -= len(text)
            try:
                tokens = shell_hint_words(text)
            except ValueError:
                continue
            bindings, segment, lookup = {}, set(), False
            for i, word in enumerate(tokens):
                after = tokens[i + 1] if i + 1 < len(tokens) else None
                if word in ("&&", "||", ";", "(", ")", "|", "&"):
                    # Only an unresolved downstream command can leave a tool's role uncertain.
                    # Variables used later as assertion operands say nothing about this guard.
                    index = len(tokens)
                    if after == "then":
                        index = i + 2
                        if tokens[index:index + 1] == [";"]:
                            index += 1
                    elif word == "&&":
                        index = i + 1
                    while index is not None and index < len(tokens) and tokens[index] == "command":
                        index = command_operand(tokens, index + 1)
                    if segment and index is not None and index < len(tokens):
                        dependent = resolve(tokens[index], bindings)
                        if expansion.search(dependent):
                            unresolved.update(segment)
                        elif "/" in dependent and (not dependent.startswith("/") or dependent.startswith(WORK + "/")):
                            guarded.setdefault(dependent, set()).update(segment)
                    segment.clear()
                    lookup = False
                    continue
                if word == "command" and command_operand(tokens, i + 1) is None:
                    lookup = True
                if not lookup and word in by_name and (not i or tokens[i - 1] not in ("-v", "-V")):
                    segment.add(by_name[word])
                word = resolve(word, bindings)
                assignment = re.fullmatch(r"([A-Za-z_]\w*)=(.*)", word, re.S)
                if assignment:
                    word = bindings[assignment[1]] = assignment[2]
                if i and tokens[i - 1] == "cd" and word in directories:
                    preferred.append(os.path.join(WORK, word))
                if not expansion.search(word) and "/" in word and (not word.startswith("/") or word.startswith(WORK + "/")):
                    hints[word] = None

        bases = dict.fromkeys([*preferred, *(os.path.join(WORK, d) for d in sorted(directories))])
        paths = set()
        inspected = 0
        # Try guarded executable words first. Exhausting a limit on unrelated hints
        # cannot make a tool uncertain once all locations for its own command were checked.
        for word in dict.fromkeys((*guarded, *hints)):
            for base in bases:
                inspected += 1
                if inspected > MAX_DIAGNOSTIC_PATHS ** 2:
                    return sorted(paths), unresolved.union(*guarded.values())
                path = os.path.normpath(os.path.join(base, word))
                if not path.startswith(WORK + "/") or path in paths:
                    continue
                name = path[len(WORK) + 1:]
                if name in existing or name in directories:
                    continue
                try:
                    local = safe_relative(name)
                except ReplayError:
                    unresolved.update(guarded.get(word, ()))
                    continue
                if (len(os.fsencode(name)) > 4095 or any(len(os.fsencode(p)) > 255 for p in local.parts)
                        or any(str(p) in existing for p in local.parents) or any(paths_overlap(path, p) for p in paths)):
                    unresolved.update(guarded.get(word, ()))
                    continue
                if len(paths) == MAX_DIAGNOSTIC_PATHS:
                    return sorted(paths), unresolved.union(*guarded.values())
                paths.add(path)
            guarded.pop(word, None)
        return sorted(paths), unresolved

    def check_missing_grants(self, directory, argv, original, elapsed):
        if not self.tools:
            return None
        exit_code = original.returncode
        deadline = time.monotonic() + CONTROL_SECONDS
        control_runs = 0
        root = directory / "repeat"
        root.mkdir()
        self.materialize(root)
        missing = {}
        for path, digest in self.tools.items():
            if digest is None:
                missing[path] = f"granted child executable unavailable: {path}"
            else:
                try:
                    self.check_runtime(root, path, deadline=deadline)
                except ReplayError as exc:
                    missing[path] = f"granted child runtime unavailable for {path}: {exc}"
        if not missing:
            return None
        # Reproduce the failing command in a clean disposable copy. Only its missing
        # grants get substitutes. They acknowledge actual launches to a dedicated
        # scratch file, independently of the child’s stderr or exception handling.
        # Both the recorded exit status and output come from the original run.
        interpreter = None
        for path in sorted(self.mounts.keys() - missing.keys()):
            program = Path(path).name
            if program in SHELLS:
                interpreter = path, "shell"
                break
            if re.fullmatch(r"python(?:[23](?:\.\d+)?)?", program):
                interpreter = path, "python"
        if interpreter is None:
            return None
        exe, family = interpreter
        log = directory / "uses"
        log.touch(mode=0o600)
        destination = WITNESS_LOG + "/" + secrets.token_hex(16)
        tags = {}

        def witnesses(targets, status):
            pairs = []
            for target in targets:
                if target not in tags:
                    tags[target] = secrets.token_hex(16)
                tag = tags[target]
                witness = directory / f"tool-{tag}-{status}"
                pairs.append((target, witness))
                if witness.exists():
                    continue
                if family == "shell":
                    body = f"printf '%s\\n' {tag} >> {destination}\nexit {status}\n"
                else:
                    body = (f"with open('{destination}', 'a') as record:\n    record.write('{tag}\\n')\n"
                            f"raise SystemExit({status})\n")
                witness.write_text(f"#!{exe}\n" + body)
                witness.chmod(0o555)
            return pairs

        def observe(work, pairs, products=(), command=argv):
            nonlocal control_runs, deadline
            if control_runs == MAX_CONTROL_RUNS:
                raise ReplayError("missing-grant diagnostic exceeded its repeat limit")
            control_runs += 1
            # Share one setup/overhead budget, but let each repeat run the measured work.
            deadline += 1.5 * elapsed
            for target, witness in products:
                write_blob(work, target[len(WORK) + 1:], "100755", witness.read_bytes())
            log.write_bytes(b"")
            observed, events = self.invoke(work, command, writable=True, witnesses=pairs, witness_log=(log, destination),
                                           deadline=deadline)
            if [e["exit-code"] for e in events if "exit-code" in e] != [observed.returncode]:
                raise ReplayError("missing granted tools could not be checked in the isolated repeat")
            with log.open("rb") as stream:
                markers = set(stream.read(16384).splitlines())
            return observed, {t for t, tag in tags.items() if tag.encode() in markers}

        def control(pairs, products=(), probe=None):
            command, edits = probe if probe else (argv, None)
            with tempfile.TemporaryDirectory(dir=directory, prefix="control-") as scratch:
                work = Path(scratch)
                self.materialize(work, edits)
                return observe(work, pairs, products, command)

        failures = dict(witnesses(missing, 127))
        self.invoke(root, [PROBE], writable=False, witnesses=witnesses([PROBE], 127), witness_log=(log, destination),
                    deadline=deadline)
        if log.read_bytes() != (tags[PROBE] + "\n").encode():
            return None
        failed, called = observe(root, failures.items())
        if failed.returncode != exit_code or not called:
            return None

        def change_one(tools, invoked, products=(), downstream=()):
            causes = []
            for target in sorted(invoked.intersection(missing))[:MAX_DIAGNOSTIC_PATHS]:
                restored = tools | {target: failures[target]}
                observed, reached = control(restored.items(), products)
                if observed.returncode == exit_code and target in reached and (not downstream or downstream - reached):
                    causes.append(missing[target])
            return ", ".join(causes) or None

        # Keep optional tools equally discoverable across controls. A changed
        # failure status exposes an unavailable prerequisite even when a success
        # substitute cannot generate the artifact that the next command needs.
        # A successful control also detects callers that translate every error.
        for status in (73 if exit_code != 73 else 75, 0):
            tools = dict(witnesses(missing, status))
            observed, invoked = control(tools.items())
            required = called & invoked
            if required and (observed.returncode != exit_code if status else observed.returncode == 0):
                if len(missing) == 1:
                    return missing[next(iter(required))]
                return change_one(tools, invoked) or "criterion outcome depends on a combination of unavailable grants"
        prefix = secrets.token_hex(16)
        probe = self.normalization_probe(argv, destination, prefix)
        if probe:
            def incoming(pairs):
                run, reached = control(pairs, probe=probe)
                if (run.returncode, run.stdout, run.stderr) != (exit_code, original.stdout, original.stderr):
                    return [], set()
                with log.open("rb") as stream:
                    records = stream.read(16385)
                if len(records) > 16384:
                    return [], set()
                statuses = re.findall(rb"^(" + prefix.encode() + rb"-\d+) (\d+)$", records, re.M)
                return statuses, reached

            # The actual missing-tool branch must be reached while its grant is still absent.
            # Then vary only one tool and require its distinctive status at that same exit.
            absent, _ = incoming(())
            present, reached = incoming(failures.items())
            if absent and absent == present:
                for target in sorted(called & reached)[:MAX_DIAGNOSTIC_PATHS]:
                    alternate = failures | dict(witnesses([target], 73))
                    varied, invoked = incoming(alternate.items())
                    if (target in invoked and [s for s, _ in varied] == [s for s, _ in absent] and
                            any(before == b"127" and after == b"73"
                                for (_, before), (_, after) in zip(absent, varied))):
                        return missing[target]
        # A successful substitute cannot build the program that the wrapper then attempts to run.
        # Vary the putative output and each invoked tool independently, keeping all paths discoverable.
        outputs, unresolved = self.possible_outputs(argv, called)
        uncertainty = ("could not verify the downstream executable of a possibly required unavailable grant: "
                       + ", ".join(sorted(unresolved))) if unresolved else None
        if not outputs:
            return uncertainty
        successful_tools = dict(witnesses(missing, 0))
        products = witnesses(outputs, 0)
        observed, invoked = control(successful_tools.items(), products)
        executed = invoked.intersection(outputs)
        if executed and observed.returncode == exit_code:
            return None
        if observed.returncode != 0 or not executed:
            return uncertainty
        observed, rejected = control(successful_tools.items(), witnesses(outputs, 73))
        if observed.returncode == 0 or not executed.intersection(rejected):
            return None
        return change_one(successful_tools, invoked, products, executed.intersection(rejected))

    def run(self, argv):
        entry = self.entry(argv[0])
        with tempfile.TemporaryDirectory(dir=self.job, prefix="criterion-") as directory:
            root = Path(directory) / "work"
            root.mkdir()
            self.materialize(root)
            self.probe(root)
            self.check_runtime(root, entry)
            started = time.monotonic()
            result, events = self.invoke(root, argv, writable=True)
            elapsed = time.monotonic() - started
            exits = [e["exit-code"] for e in events if "exit-code" in e]
            if exits != [result.returncode]:
                return None, result.stdout, result.stderr, "test sandbox or executable could not start"
            if result.returncode:
                try:
                    reason = self.check_missing_grants(Path(directory), argv, result, elapsed)
                except (OSError, ReplayError):
                    # The primary process already produced a verified result. A failed optional
                    # diagnostic supplies no evidence that an unavailable grant caused it.
                    reason = None
                if reason:
                    return result.returncode, result.stdout, result.stderr, reason
            return result.returncode, result.stdout, result.stderr, None
