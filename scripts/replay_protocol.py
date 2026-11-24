"""Validate a runner's v1 terminal envelope and seal its referenced bytes in the case."""
import math
import os
from pathlib import Path
import re
import stat

from replay_git import ReplayError, safe_relative, sha1_object, sha256
from replay_claims import report_claims
from replay_storage import decode, publish


COMPONENTS = ("input", "cached_input", "output", "reasoning_output")


def require(condition, message):
    if not condition:
        raise ReplayError(message)


def evidence_bytes(root, ref):
    require(isinstance(ref, dict) and isinstance(ref.get("sha256"), str)
            and re.fullmatch("[0-9a-f]{64}", ref["sha256"]), "invalid evidence reference")
    parts = safe_relative(ref.get("path")).parts
    directory = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
    fd = os.open(root, directory)
    try:
        for part in parts[:-1]:
            child = os.open(part, directory, dir_fd=fd)
            os.close(fd)
            fd = child
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        with os.fdopen(os.open(parts[-1], flags, dir_fd=fd), "rb") as stream:
            mode = os.fstat(stream.fileno())
            require(stat.S_ISREG(mode.st_mode) and mode.st_nlink == 1, "evidence is not a confined regular file")
            data = stream.read()
    finally:
        os.close(fd)
    require(sha256(data) == ref["sha256"], "evidence digest differs")
    return data


def seal_evidence(job, output, ref):
    data = evidence_bytes(output, ref)
    path = job / "evidence" / ref["sha256"]
    publish(path, data)
    return dict(path=path.relative_to(job.parents[1]).as_posix(), sha256=ref["sha256"])


def token_counts(raw):
    require(isinstance(raw, dict) and all(k in raw for k in COMPONENTS), "invalid role token components")
    require(all(raw[k] is None or type(raw[k]) is int for k in COMPONENTS), "invalid role token count")
    return {k: raw[k] if type(raw[k]) is int and raw[k] >= 0 else None for k in COMPONENTS}


def result_for(job, req, spec, raw):
    result = decode(raw, "runner result")
    fields = {"schema", "attempt", "config_digest", "host", "outcome", "reason", "worker_status", "roles",
              "artifact", "boundary_violation"}
    require(fields <= result.keys() and type(result["schema"]) is int and result["schema"] == 1,
            "invalid v1 runner result")
    require(result["attempt"] == req["attempt"], "runner returned the wrong attempt ID")
    require(result["outcome"] in ("completed", "stopped", "failed", "incompatible") and
            (result["reason"] is None or isinstance(result["reason"], str)), "invalid runner outcome")
    require(isinstance(result["roles"], dict), "invalid observed roles")
    checked = dict(outcome=result["outcome"], reason=result["reason"], roles={}, boundary_violation=None,
                   worker_status=None, artifact=None)
    errors, mismatches = [], []
    for key, label in (("config_digest", "configuration"), ("host", "host")):
        if result[key] != req[key]:
            mismatches.append(f"observed {label} differs")
    if result["artifact"] is not None or result["worker_status"] is not None:
        errors.append("unexpected worker status or artifact on a review")
    output = Path(req["output"])
    workspace = Path(req["workspace"])
    verified_loads = {}
    for key, role in result["roles"].items():
        expected = req["roles"].get(key)
        if expected is None:
            mismatches.append("unrequested role observed")
            continue
        try:
            require(isinstance(role, dict) and {"model", "effort", "loaded", "tokens", "report", "brief"} <= role.keys(),
                    f"malformed observed role {key}")
            require(isinstance(role["model"], str) and isinstance(role["effort"], str), f"invalid observed identity for {key}")
            saved = dict(model=role["model"], effort=role["effort"], tokens=token_counts(role["tokens"]),
                         loaded=role["loaded"], report=None, brief=None, report_valid=None, claims=[])
            checked["roles"][key] = saved
            if any(role[k] != expected[k] for k in ("model", "effort")):
                mismatches.append(f"observed {key} model or effort differs")
            require(isinstance(role["loaded"], list), f"invalid loaded paths for {key}")
            for item in role["loaded"]:
                require(isinstance(item, dict) and isinstance(item.get("path"), str) and
                        isinstance(item.get("blob"), str), f"invalid loaded entry for {key}")
                name, blob = item["path"], item["blob"]
                if name in spec["loads"] and name not in verified_loads:
                    path = workspace / name
                    verified_loads[name] = (sha1_object(b"blob", path.read_bytes()).hex()
                                            if path.resolve() == path and path.is_file() else None)
                if spec["loads"].get(name) != blob or verified_loads.get(name) != blob:
                    mismatches.append(f"{key} loaded a path or blob outside its assigned suite")
            require(role["brief"] is None, "unexpected review brief")
            if role["report"] is not None:
                require(key != "parent", "parent supplied a terminal report")
                saved["report"] = seal_evidence(job, output, role["report"])
                saved["report_valid"], saved["claims"] = report_claims(evidence_bytes(job.parents[1], saved["report"]), key)
            elif result["outcome"] == "completed" and key != "parent":
                errors.append(f"{key} terminal report missing")
        except (OSError, ReplayError) as exc:
            errors.append(str(exc))
    if result["outcome"] == "completed" and req["roles"].keys() - checked["roles"].keys():
        errors.append("completed result is missing expected roles")
    boundary = result["boundary_violation"]
    if boundary is not None:
        try:
            require(isinstance(boundary, dict) and {"reason", "tokens", "wall_seconds", "evidence"} <= boundary.keys()
                    and isinstance(boundary["reason"], str) and boundary["reason"].strip(), "invalid boundary violation")
            seconds = boundary["wall_seconds"]
            require(seconds is None or (type(seconds) is int and seconds >= 0) or
                    (type(seconds) is float and math.isfinite(seconds) and seconds >= 0),
                    "invalid post-boundary elapsed time")
            require(isinstance(boundary["tokens"], dict), "invalid post-boundary tokens")
            costs = {k: token_counts(v) for k, v in boundary["tokens"].items()}
            ref = seal_evidence(job, output, boundary["evidence"]) if boundary["evidence"] is not None else None
            checked["boundary_violation"] = dict(reason=boundary["reason"], evidence=ref, tokens=costs, wall_seconds=seconds)
            mismatches.append("stopping boundary violated: " + boundary["reason"])
        except (OSError, ReplayError) as exc:
            errors.append(str(exc))
    if mismatches or errors:
        checked.update(outcome="incompatible" if mismatches else "failed", reason="; ".join(mismatches + errors))
    return checked
