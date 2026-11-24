"""Evaluate a worker's sealed evidence in the private case after its terminal report."""
import base64
import difflib

from replay_artifact import file_view, import_artifact
from replay_git import ReplayError, json_bytes, sha256
from replay_protocol import evidence_bytes, save_evidence
from replay_sandbox import CriterionSandbox
from replay_storage import decode, publish


def compare_briefs(job, historical, ref):
    actual = evidence_bytes(job.parents[1], ref) if ref else None
    comparison = dict(status="unavailable", historical_sha256=historical["sha256"],
                      dispatched_sha256=ref["sha256"] if ref else None)
    if historical["status"] != "available" or not actual or not actual.strip():
        return comparison
    try:
        dispatched = actual.decode()
    except UnicodeDecodeError:
        return comparison
    initial = historical["text"]
    comparison["status"] = "identical" if initial == dispatched else "changed"
    if initial != dispatched:
        diff = difflib.unified_diff(initial.splitlines(keepends=True), dispatched.splitlines(keepends=True),
                                    fromfile="historical brief", tofile="dispatched brief")
        lines = (line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in diff)
        publish(job / "brief.diff", "".join(lines).encode())
    return comparison


def evaluate_slice(job, spec, result):
    raw = (job.parents[1] / "receipt.json").read_bytes()
    if sha256(raw) != spec["receipt_sha256"]:
        raise ReplayError("prepared receipt changed during dispatch")
    receipt = decode(raw, "prepared receipt")
    brief = result["roles"].get("worker", {}).get("brief")
    result["brief_comparison"] = compare_briefs(job, receipt["historical_brief"], brief)
    files = None
    if result["artifact"] is not None and result["worker_status"] is None:
        result.update(partial_artifact=result["artifact"], artifact=None, artifact_reason="worker terminal report unavailable")
    if result["artifact"] is not None:
        try:
            tree, files = import_artifact(job, result["artifact"], receipt["source"]["object_format"], spec["injected"])
            result["artifact_tree"] = tree
            result["artifact_view"] = save_evidence(job, json_bytes(file_view(files)))
        except (OSError, ReplayError) as exc:
            result.update(partial_artifact=result["artifact"], artifact=None, artifact_reason=str(exc))
    sandbox, unavailable = None, result.get("artifact_reason", "worker artifact unavailable")
    if files is not None and any(c["argv"] for c in receipt["criteria"]):
        try:
            sandbox = CriterionSandbox(job, spec["test_grants"], files, receipt["fixtures"])
        except (OSError, ReplayError) as exc:
            unavailable = str(exc)
    result["tests"] = []
    for criterion in receipt["criteria"]:
        argv = criterion["argv"]
        code, stdout, stderr = None, b"", b""
        if argv is None:
            reason = "no pinned command"
        elif sandbox is None:
            reason = unavailable
        else:
            try:
                code, stdout, stderr, reason = sandbox.run(argv)
            except (OSError, ReplayError) as exc:
                reason = str(exc)
        outcome = "unavailable" if code is None or reason else "pass" if code == 0 else "fail"
        observation = dict(id=criterion["id"], argv=argv, outcome=outcome, reason=reason, exit_code=code,
                           stdout_base64=base64.b64encode(stdout).decode(), stderr_base64=base64.b64encode(stderr).decode())
        ref = save_evidence(job, json_bytes(observation))
        result["tests"].append(dict(id=criterion["id"], argv=argv, outcome=observation["outcome"], reason=reason,
                                    evidence=ref))
