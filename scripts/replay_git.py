"""Private Git objects and file identities used to restore replay workspaces."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

from trace_records import canon
from trace_versions import suite_entries


class ReplayError(ValueError):
    """An input cannot be verified or used for this replay."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def git_environment():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return dict(env, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM="1",
                GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="", GIT_NO_REPLACE_OBJECTS="1",
                GIT_AUTHOR_NAME="Canon replay", GIT_AUTHOR_EMAIL="replay@localhost",
                GIT_COMMITTER_NAME="Canon replay", GIT_COMMITTER_EMAIL="replay@localhost",
                GIT_AUTHOR_DATE="2000-01-01T00:00:00Z", GIT_COMMITTER_DATE="2000-01-01T00:00:00Z")


def git_command(root, *args):
    return ["git", "-C", str(root), "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false", *args]


def git(root, *args, data=None):
    result = subprocess.run(git_command(root, *args), input=data, capture_output=True, env=git_environment())
    if result.returncode:
        raise ReplayError(f"git {args[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def oid(root, *args, data=None):
    return git(root, *args, data=data).decode("ascii").strip()


def init_repo(root, object_format):
    root.mkdir(parents=True)
    git(root, "init", "--quiet", "--template=", "--object-format=" + object_format)


def transfer_objects(source, destination, objects):
    """Import only the closure of explicit tree or synthetic commit IDs, without alternates."""
    roots = "".join(oid + "\n" for oid in sorted(set(objects))).encode("ascii")
    env = git_environment()
    with tempfile.TemporaryFile(dir=destination) as errors, subprocess.Popen(
            git_command(source, "pack-objects", "--stdout", "--revs"), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=errors, env=env) as pack:
        try:
            pack.stdin.write(roots)
            pack.stdin.close()
            imported = subprocess.run(git_command(destination, "index-pack", "--stdin"), stdin=pack.stdout,
                                      capture_output=True, env=env)
        finally:
            pack.stdout.close()
        if pack.wait() or imported.returncode:
            errors.seek(0)
            detail = (errors.read() + imported.stderr).decode(errors="replace").strip()
            raise ReplayError(f"cannot transfer verified input trees: {detail}")


def safe_relative(name):
    if not isinstance(name, str) or not name or "\0" in name or any(
            p in {"", ".", ".."} or p.lower() == ".git" for p in name.split("/")):
        raise ReplayError(f"unsafe relative path {name!r}")
    return Path(name)


def write_blob(root, name, mode, data):
    path = root / safe_relative(name)
    if not path.parent.resolve().is_relative_to(root.resolve()) or any(
            p.is_symlink() for p in path.parents if p.is_relative_to(root)):
        raise ReplayError(f"unsafe path through a symlink: {name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        raise ReplayError(f"path already occupied: {name}")
    if mode == "120000":
        path.symlink_to(os.fsdecode(data))
    elif mode in ("100644", "100755"):
        path.write_bytes(data)
        path.chmod(int(mode, 8) & 0o777)
    else:
        raise ReplayError(f"unsupported Git mode {mode} for {name}")


def sha1_object(kind, body):
    header = kind + b" " + str(len(body)).encode("ascii") + b"\0"
    return hashlib.sha1(header + body).digest()


def suite_identity(root):
    """Compute Git's canonical SHA-1 tree and D001's content-only manifest from installed bytes."""
    manifests = {}

    def tree(directory):
        entries = []
        for path in directory.iterdir():
            name = os.fsencode(path.name)
            file_mode = path.lstat().st_mode
            if stat.S_ISDIR(file_mode):
                entries.append((name + b"/", b"40000 " + name + b"\0" + tree(path)))
            elif stat.S_ISREG(file_mode):
                blob = sha1_object(b"blob", path.read_bytes())
                mode = b"100755" if file_mode & stat.S_IXUSR else b"100644"
                entries.append((name, mode + b" " + name + b"\0" + blob))
                skill, *rest = path.relative_to(root).parts
                manifests.setdefault(skill, []).append(["/".join(rest), blob.hex()])
            else:
                raise ReplayError(f"invalid file in installed suite: {path.name}")
        return sha1_object(b"tree", b"".join(body for _, body in sorted(entries)))

    tree_id = tree(root).hex()
    manifest = {name: canon.sha256_json(sorted(entries)) for name, entries in manifests.items()}
    return dict(tree=tree_id, manifest=canon.sha256_json(manifest, sort_keys=True))


def save_suite(root, source, commit, *, recorded=False):
    entries = suite_entries(source, commit, recorded=recorded)
    if not entries:
        raise ReplayError("suite files unavailable")
    for name, files in entries.items():
        for path, (mode, blob) in files.items():
            write_blob(root, name + "/" + path, mode, git(source, "cat-file", "blob", blob))
    return dict(suite_identity(root), commit=commit)


def save_fixtures(destination, supplied, root, source):
    destination.mkdir()
    if supplied is None:
        return {}
    supplied = supplied.resolve(strict=True)
    if not supplied.is_dir() or destination.resolve().is_relative_to(supplied):
        raise ReplayError("fixture directory must be outside the case being prepared")
    reserved = {".agents/skills", ".claude/skills", ".git", *source["untracked"]}
    for tree in (source["original"]["target_tree"], source["original"]["baseline_tree"]):
        if tree:
            reserved.update(os.fsdecode(p) for p in git(root, "ls-tree", "-rz", "--name-only", tree).split(b"\0") if p)
    manifest = {}

    def copy(directory, relative, seen):
        for entry in sorted(directory.iterdir()):
            name = (relative / entry.name).as_posix()
            resolved = entry.resolve(strict=True)
            if not resolved.is_relative_to(supplied) or resolved in seen:
                raise ReplayError(f"escaping or cyclic fixture: {name}")
            if any(p.lower() == ".git" for p in Path(name).parts) or any(
                    name == r or name.startswith(r + "/") for r in reserved):
                raise ReplayError(f"fixture overlap: {name}")
            mode = resolved.stat().st_mode
            if stat.S_ISDIR(mode):
                copy(resolved, Path(name), seen | {resolved})
            elif stat.S_ISREG(mode):
                if any(r.startswith(name + "/") for r in reserved):
                    raise ReplayError(f"fixture overlap: {name}")
                executable = "100755" if mode & stat.S_IXUSR else "100644"
                data = resolved.read_bytes()
                write_blob(destination, name, executable, data)
                manifest[name] = dict(mode=executable, sha256=sha256(data))
            else:
                raise ReplayError(f"invalid fixture type: {name}")

    copy(supplied, Path(), {supplied})
    return manifest


def synthetic_commit(root, tree, label, parent=None):
    return oid(root, "commit-tree", tree, *(("-p", parent) if parent else ()), "-m", label)


def import_input(root, case, row, scope):
    pair = row.get("review_input", {})
    target = pair.get("target_tree", row["opening"]["tree"])
    base = pair.get("baseline_tree")
    base = None if base == "none" else base
    as_built = scope.get("as_built_tree")
    object_format = oid(case.store, "rev-parse", "--show-object-format")
    init_repo(root, object_format)
    transfer_objects(case.store, root, [t for t in (target, base, as_built) if t])
    baseline = synthetic_commit(root, base, "Replay baseline") if base else None
    code = synthetic_commit(root, as_built, "Replay as-built code") if as_built else None
    if code:
        git(root, "update-ref", "refs/replay/as-built", code)
    git(root, "read-tree", target)
    untracked = {}
    for item in scope.get("untracked_files", []):
        prefix = f"{case.store}@{pair['target']}:"
        if not item["location"].startswith(prefix):
            raise ReplayError("untracked source does not match the retained target")
        name = item["location"][len(prefix):]
        safe_relative(name)
        untracked[name] = dict(mode=item["mode"], blob=item["blob"])
    if untracked:
        git(root, "update-index", "--force-remove", "-z", "--stdin",
            data=b"".join(os.fsencode(name) + b"\0" for name in untracked))
    tracked = oid(root, "write-tree")
    head = synthetic_commit(root, tracked, "Replay target", baseline)
    git(root, "update-ref", "HEAD", head)
    git(root, "checkout-index", "--all")
    for name, file in untracked.items():
        write_blob(root, name, file["mode"], git(root, "cat-file", "blob", file["blob"]))
    spec = dict(form=scope["form"], paths=scope.get("paths", []), target=head, baseline=baseline,
                as_built=code, diff_args=scope.get("options", []), untracked=sorted(untracked))
    patch = scope.get("patch_sha256")
    if patch:
        restored = git(root, "diff", "--no-ext-diff", "--no-textconv", *spec["diff_args"],
                       baseline, head, "--", *spec["paths"])
        if sha256(restored) != patch:
            raise ReplayError("restored patch digest differs from Q9")
    original = dict(opening=row["opening"]["commit"], target=pair.get("target_pin", row["opening"]["commit"]),
                    target_tree=target, baseline=pair.get("baseline_pin"), baseline_tree=base,
                    as_built=scope.get("as_built_commit"), as_built_tree=as_built,
                    retained=pair.get("target"), tracked_tree=tracked)
    return spec, dict(object_format=object_format, original=original, patch_sha256=patch, untracked=untracked)
