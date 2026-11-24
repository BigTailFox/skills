"""Build an adjudicator's scoped source view from the verified, parentless replay objects."""
from pathlib import Path

from replay_artifact import file_view, read_files
from replay_git import ReplayError, git, sha256
from replay_workspace import listed, scoped_paths
from trace_records import canon
from trace_review_inputs import revision_documents


def frozen_documents(repo, receipt):
    """Resolve named inputs against the tracked target and its separately retained untracked files."""
    task = receipt["task"]
    target = task["input"]["target"]
    untracked = receipt["source"]["untracked"]
    paths = listed(repo, "ls-tree", "-rz", "--name-only", target) | untracked.keys()

    def read(path):
        if path in untracked:
            return git(repo, "cat-file", "blob", untracked[path]["blob"])
        return git(repo, "show", target + ":" + path)

    docs = revision_documents(task["docs"], paths, read, slice_inputs=receipt["kind"] == "slice")
    if docs is None:
        raise ReplayError("named document unavailable at frozen revision: " + ", ".join(task["docs"]))
    return docs


def review_input(repo, receipt, grants, neutral_files, neutral_patch):
    task = receipt["task"]
    spec = task["input"]
    docs = frozen_documents(repo, receipt)
    selected = scoped_paths(repo, task) | docs.keys()
    def view(tree, names):
        return neutral_files(file_view(read_files(repo, tree, set(), selected=names, gitlinks=True)))

    result = dict(target=view(spec["target"], selected))
    if spec["baseline"]:
        patch = git(repo, "diff", "--no-ext-diff", "--no-textconv", *spec["diff_args"],
                    spec["baseline"], spec["target"], "--", *spec["paths"])
        expected = receipt["source"]["patch_sha256"]
        if expected and sha256(patch) != expected:
            raise ReplayError("review input patch digest differs")
        result.update(patch=neutral_patch(patch.decode(errors="surrogateescape"), selected),
                      baseline=view(spec["baseline"], selected))
    files = {path: (item["mode"], git(repo, "cat-file", "blob", item["blob"]))
             for path, item in sorted(receipt["source"]["untracked"].items())}
    result["untracked"] = neutral_files(file_view(files))
    if spec["as_built"]:
        # A gate can name a separate approved code tree. Honor the original design's governed
        # paths when present and the operator's read grants even for older designs without them.
        names = listed(repo, "ls-tree", "-rz", "--name-only", spec["as_built"])
        names = {p for p in names if any(g == "." or p == g or p.startswith(g + "/") for g in grants)}
        governed = []
        for path, fields in docs.items():
            root = path.rsplit("docs/", 1)[0]
            entries = fields.get("paths", [])
            if isinstance(entries, list):
                governed.extend(canon.glob_regex(root + p.rstrip("/")) for p in entries if isinstance(p, str) and p)
        if governed:
            names = {p for p in names if any(rx.fullmatch(str(a)) for rx in governed for a in (Path(p), *Path(p).parents))}
        result["as_built"] = view(spec["as_built"], names)
    return result
