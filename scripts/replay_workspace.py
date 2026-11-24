"""Build one disposable checkout and identify its effective suite paths before dispatch."""
import os
import re
import shutil
import stat

from replay_case import verify_input
from replay_git import ReplayError, git, init_repo, safe_relative, sha1_object, transfer_objects, write_blob
from trace_versions import NAME, manifest_path


def listed(workspace, *args):
    return {os.fsdecode(p) for p in git(workspace, *args).split(b"\0") if p}


def contained(root, path):
    try:
        resolved = path.resolve()
        rel = resolved.relative_to(root).as_posix()
        safe_relative(rel)
        return resolved
    except (OSError, ValueError, RuntimeError) as exc:
        raise ReplayError(f"installation escapes the checkout: {path.relative_to(root)}") from exc


def file_matches(path, source):
    return (path.is_file() and path.read_bytes() == source.read_bytes() and
            bool(path.stat().st_mode & stat.S_IXUSR) == bool(source.stat().st_mode & stat.S_IXUSR))


def skills_path(host):
    return ".claude/skills" if host == "claude-code" else ".agents/skills"


def scoped_paths(workspace, task):
    spec = task["input"]
    if spec["baseline"]:
        names = listed(workspace, "diff", "--name-only", "--no-renames", "-z", spec["baseline"], spec["target"],
                       "--", *spec["paths"])
    else:
        names = set(spec["paths"])
    if spec["form"] == "document diff":
        names.update(spec["paths"])
    return names.union(spec["untracked"])


def project_instructions(workspace, task):
    instructions = {workspace / "AGENTS.md"}
    for name in scoped_paths(workspace, task):
        path = workspace / safe_relative(name)
        instructions.update(p / "AGENTS.md" for p in path.parents if p.is_relative_to(workspace))
    return sorted(p for p in instructions if p.is_file())


def tool_paths(workspace, task):
    """Interpret concrete canon.py invocations and the project's generated Tool declaration."""
    paths = set()
    for file in project_instructions(workspace, task):
        for line in contained(workspace, file).read_text().splitlines():
            if re.match(r"^\s*[-*]?\s*Tool:", line):
                words = re.findall(r"`(?:python3?\s+)?([\w./-]*canon\.py)`", line)
                if "of the `canon` skill" in line and len(words) > 1:
                    words = [p for p in words if p != "scripts/canon.py"]
                paths.update(words)
            elif re.search(r"\b(?:agents?|reviewers?|run|use|execute)\b", line, re.I):
                paths.update(re.findall(r"`python3?\s+([\w./-]*canon\.py)(?=[\s`])", line))
    return paths


def restore_workspace(source, workspace, receipt):
    spec = receipt["task"]["input"]
    init_repo(workspace, receipt["source"]["object_format"])
    transfer_objects(source, workspace, [c for c in (spec["target"], spec["as_built"]) if c])
    git(workspace, "update-ref", "HEAD", spec["target"])
    if spec["as_built"]:
        git(workspace, "update-ref", "refs/replay/as-built", spec["as_built"])
    git(workspace, "read-tree", "--reset", "-u", spec["target"])
    for name, file in receipt["source"]["untracked"].items():
        write_blob(workspace, name, file["mode"], git(source, "cat-file", "blob", file["blob"]))


def workspace_for(private, workspace, receipt, arm):
    restore_workspace(private / "input", workspace, receipt)
    visible = listed(workspace, "ls-files", "--others", "--exclude-standard", "-z")
    suite = private / "suites" / arm
    installed = workspace / ".agents/skills"
    claude = workspace / ".claude/skills"
    injected, loads = set(), {}
    tracked = listed(workspace, "ls-files", "-z")
    for source in sorted(suite.rglob("*")):
        if not source.is_file():
            continue
        dest = installed / source.relative_to(suite)
        resolved = contained(workspace, dest)
        name = resolved.relative_to(workspace).as_posix()
        if dest.exists() or dest.is_symlink():
            if name not in tracked or not file_matches(resolved, source):
                raise ReplayError(f"conflicting installed suite path: {dest.relative_to(workspace)}")
        else:
            if resolved != dest:
                raise ReplayError(f"incomplete tracked installation: {dest.relative_to(workspace)}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            injected.add(name)
        loads[name] = sha1_object(b"blob", source.read_bytes()).hex()
    contained(workspace, claude).mkdir(parents=True, exist_ok=True)
    for skill in sorted(suite.iterdir()):
        link = claude / skill.name
        name = link.relative_to(workspace).as_posix()
        target = installed / skill.name
        if link.is_symlink():
            if contained(workspace, link) != target.resolve() or name not in tracked:
                raise ReplayError(f"conflicting Claude skill link: {name}")
        elif link.exists() or link.parent.resolve() != link.parent:
            raise ReplayError(f"conflicting Claude skill path: {name}")
        else:
            link.symlink_to(os.path.relpath(target, link.parent))
            injected.add(name)
        actual = target.resolve()
        for file in actual.rglob("*"):
            relative = file.relative_to(actual)
            if manifest_path(relative.parts) and (file.is_symlink() or file.is_file()) and not (skill / relative).is_file():
                raise ReplayError(f"unassigned installed suite file: {skill.name}/{relative}")
    for base in (installed, claude):
        for entry in base.iterdir():
            if NAME.fullmatch(entry.name) and not (suite / entry.name).is_dir() and (
                    entry.is_symlink() or (entry / "SKILL.md").is_file()):
                raise ReplayError(f"unassigned installed skill: {entry.name}")
    for path in tool_paths(workspace, receipt["task"]):
        resolved = contained(workspace, workspace / safe_relative(path.removeprefix("./")))
        source = suite / "canon/scripts/canon.py"
        if not source.is_file() or not file_matches(resolved, source):
            raise ReplayError(f"prescribed tool does not match the assigned suite: {path}")
        loads[resolved.relative_to(workspace).as_posix()] = sha1_object(b"blob", source.read_bytes()).hex()
    for name, spec in receipt["fixtures"].items():
        write_blob(workspace, name, spec["mode"], (private / "fixtures" / name).read_bytes())
        injected.add(name)
    exclude = workspace / ".git/info/exclude"
    exclude.parent.mkdir(exist_ok=True)
    with exclude.open("a") as stream:
        for name in sorted(injected):
            stream.write("/" + re.sub(r"([\\*?\[\] #!])", r"\\\1", name) + "\n")
    verify_input(workspace, receipt, injected)
    if listed(workspace, "ls-files", "--others", "--exclude-standard", "-z") != visible:
        raise ReplayError("project ignore rules expose an injected path")
    return workspace / skills_path(receipt["host"]), loads, sorted(injected)
