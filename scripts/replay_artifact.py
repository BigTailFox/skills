"""Read a terminal bundle using only objects imported into a new private repository."""
import base64
import io
import os
from pathlib import Path
import subprocess
import tempfile

from replay_git import ReplayError, git, git_command, git_environment, init_repo, oid, safe_relative, write_blob


RESULT = "refs/replay/result"


def verify_header(bundle, object_format):
    with bundle.open("rb") as stream:
        if stream.readline() != b"# v3 git bundle\n":
            raise ReplayError("artifact requires Git bundle v3")
        capabilities = []
        for line in stream:
            if line == b"\n":
                break
            if line.startswith(b"-"):
                raise ReplayError("artifact bundle has a prerequisite")
            if line.startswith(b"@"):
                capabilities.append(line.rstrip(b"\n"))
        else:
            raise ReplayError("incomplete artifact bundle header")
    # SHA-1 is the bundle format's default when no capability is advertised.
    if (capabilities or [b"@object-format=sha1"]) != [b"@object-format=" + object_format.encode()]:
        raise ReplayError("incompatible artifact object format or capability")


def read_files(repo, tree, injected, *, selected=None):
    files, blobs = {}, {}
    for raw in git(repo, "ls-tree", "-rz", tree).split(b"\0"):
        if not raw:
            continue
        meta, raw_name = raw.split(b"\t", 1)
        mode, kind, blob = meta.decode("ascii").split()
        name = os.fsdecode(raw_name)
        if selected is not None and name not in selected:
            continue
        path = safe_relative(name)
        if kind != "blob" or mode not in ("100644", "100755", "120000"):
            raise ReplayError(f"unsupported artifact mode for {name}")
        if name in injected or any(parent.as_posix() in injected for parent in path.parents):
            raise ReplayError(f"artifact contains an injected path: {name}")
        files[name] = mode, blob
        blobs[blob] = None
    batch = io.BytesIO(git(repo, "cat-file", "--batch", data="".join(b + "\n" for b in blobs).encode()))
    for blob in blobs:
        actual, kind, size = batch.readline().split()
        if actual.decode() != blob or kind != b"blob":
            raise ReplayError("artifact blob unavailable")
        blobs[blob] = batch.read(int(size))
        if batch.read(1) != b"\n":
            raise ReplayError("incomplete artifact blob")
    for name, (mode, blob) in files.items():
        if mode == "120000" and (not blobs[blob] or b"\0" in blobs[blob]):
            raise ReplayError(f"invalid artifact symlink: {name}")
    return {name: (mode, blobs[blob]) for name, (mode, blob) in files.items()}


def check_new_paths(repo, tracked, files):
    added = files.keys() - tracked
    if not added:
        return
    # Git reads per-directory ignore files from the work tree. Only materialize those regular blobs.
    for name, (mode, data) in files.items():
        if Path(name).name == ".gitignore" and mode != "120000":
            write_blob(repo, name, mode, data)
    checked = subprocess.run(git_command(repo, "check-ignore", "--no-index", "--stdin", "-z"),
                             input=b"".join(os.fsencode(n) + b"\0" for n in sorted(added)), capture_output=True,
                             env=git_environment())
    if checked.returncode not in (0, 1):
        raise ReplayError("could not check artifact ignore rules")
    if checked.stdout:
        raise ReplayError("artifact contains a new ignored project path")


def import_artifact(job, ref, object_format, injected):
    bundle = job.parents[1] / ref["path"]
    verify_header(bundle, object_format)
    with tempfile.TemporaryDirectory(dir=job, prefix="import-") as area:
        repo = Path(area) / "objects"
        init_repo(repo, object_format)
        git(repo, "bundle", "verify", str(bundle))
        heads = git(repo, "bundle", "unbundle", str(bundle)).splitlines()
        if len(heads) != 1 or heads[0].split()[1:] != [RESULT.encode()]:
            raise ReplayError("artifact must advertise only refs/replay/result")
        commit = heads[0].split()[0].decode("ascii")
        if oid(repo, "cat-file", "-t", commit) != "commit":
            raise ReplayError("result ref does not point to a commit")
        git(repo, "update-ref", RESULT, commit)
        git(repo, "fsck", "--strict", "--full", "--no-dangling", "--no-reflogs")
        ancestry = oid(repo, "show", "-s", "--format=%T %P", "--no-show-signature", commit).split()
        if len(ancestry) != 1:
            raise ReplayError("artifact must have a parentless result commit")
        tracked = {os.fsdecode(p) for p in git(job.parents[1] / "input", "ls-files", "-z").split(b"\0") if p}
        def skill_roots(names):
            return {"/".join(n.split("/")[:3]) for n in names if n.startswith((".agents/skills/", ".claude/skills/"))}
        protected = set(injected) | (skill_roots(injected) - skill_roots(tracked))
        files = read_files(repo, ancestry[0], protected)
        check_new_paths(repo, tracked, files)
        return ancestry[0], files


def file_view(files):
    rows = []
    for path, (mode, data) in files.items():
        try:
            content = data.decode()
        except UnicodeDecodeError:
            content = None
        if content is None or "\0" in content:
            content = base64.b64encode(data).decode("ascii")
            encoding = "base64"
        else:
            encoding = "utf-8"
        rows.append(dict(path=path, mode=mode, encoding=encoding, content=content))
    return dict(files=rows)
