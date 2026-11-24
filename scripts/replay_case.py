"""Open and recheck a prepared receipt without consulting the original project or host."""
import json
import os
from pathlib import Path
import stat

from replay_git import ReplayError, git, oid, safe_relative, sha256, suite_identity


def fixture_identity(directory):
    files = {}
    for path in directory.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            files[path.relative_to(directory).as_posix()] = dict(mode="100755" if mode & stat.S_IXUSR else "100644",
                                                                sha256=sha256(path.read_bytes()))
        elif not stat.S_ISDIR(mode):
            raise ReplayError("unexpected link or special file in saved fixtures")
    return files


def verify_input(root, receipt):
    spec, source = receipt["task"]["input"], receipt["source"]
    original = source["original"]
    if root.is_symlink() or (root / ".git/objects/info/alternates").exists() or (
            Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel").rstrip(b"\n"))).resolve() != root.resolve()):
        raise ReplayError("prepared input is not an independent checkout")
    if oid(root, "rev-parse", "--show-object-format") != source["object_format"]:
        raise ReplayError("prepared input object format differs")
    git(root, "fsck", "--full", "--no-reflogs", "--no-progress")
    expected = [(spec["target"], original["tracked_tree"], [spec["baseline"]] if spec["baseline"] else [])]
    if spec["baseline"]:
        expected.append((spec["baseline"], original["baseline_tree"], []))
    if spec["as_built"]:
        expected.append((spec["as_built"], original["as_built_tree"], []))
        if oid(root, "rev-parse", "refs/replay/as-built") != spec["as_built"]:
            raise ReplayError("prepared as-built ref differs")
    for commit, tree, parents in expected:
        actual = oid(root, "show", "-s", "--no-show-signature", "--no-notes", "--format=%T %P", commit).split()
        if actual != [tree, *parents]:
            raise ReplayError("prepared input commit differs")
    if (oid(root, "rev-parse", "HEAD") != spec["target"] or oid(root, "write-tree") != original["tracked_tree"] or
            git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD", "--")):
        raise ReplayError("prepared input tree differs")
    names = {os.fsdecode(p) for p in git(root, "ls-files", "--others", "-z").split(b"\0") if p}
    if names != set(source["untracked"]):
        raise ReplayError("prepared input untracked paths differ")
    for name, expected_file in source["untracked"].items():
        path = root / safe_relative(name)
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            data, file_mode = os.fsencode(os.readlink(path)), "120000"
        elif stat.S_ISREG(mode):
            data, file_mode = path.read_bytes(), "100755" if mode & stat.S_IXUSR else "100644"
        else:
            raise ReplayError("invalid untracked file in prepared input")
        if dict(mode=file_mode, blob=oid(root, "hash-object", "--stdin", data=data)) != expected_file:
            raise ReplayError("prepared input untracked file differs")
    if source["patch_sha256"]:
        patch = git(root, "diff", "--no-ext-diff", "--no-textconv", *spec["diff_args"],
                    spec["baseline"], spec["target"], "--", *spec["paths"])
        if sha256(patch) != source["patch_sha256"]:
            raise ReplayError("prepared input patch digest differs")


def load_case(directory):
    private = directory / "private"
    if private.is_symlink():
        raise ReplayError("invalid private case directory")
    encoded = (private / "receipt.json").read_bytes()
    if sha256(encoded) != (private / "receipt.sha256").read_text().strip():
        raise ReplayError("private receipt digest differs")
    try:
        receipt = json.loads(encoded)
        if type(receipt.get("schema")) is not int or receipt["schema"] != 1:
            raise ReplayError("unsupported case schema")
        for arm in ("recorded", "candidate"):
            root = private / "suites" / arm
            if root.is_symlink() or suite_identity(root) != {k: receipt["suites"][arm][k] for k in ("tree", "manifest")}:
                raise ReplayError(f"{arm} suite digest differs")
        fixtures = private / "fixtures"
        if not fixtures.is_dir() or fixtures.is_symlink() or fixture_identity(fixtures) != receipt["fixtures"]:
            raise ReplayError("prepared fixture modes or bytes differ")
        verify_input(private / "input", receipt)
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        raise ReplayError("invalid private receipt") from exc
    return receipt
