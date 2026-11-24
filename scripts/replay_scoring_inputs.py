"""Bind scoring to the sealed receipts, packet and confined evidence of one case."""
from pathlib import Path

from replay_attempts import verify_attempts
from replay_case import load_case
from replay_git import ReplayError, json_bytes, safe_relative, sha256
from replay_packet import Packet, opaque
from replay_protocol import evidence_bytes, require
from replay_storage import case_layout, decode, job_layout


def verified(root, ref):
    try:
        evidence_bytes(root, ref)
        return True
    except (OSError, ReplayError):
        return False


def reference_key(ref):
    if isinstance(ref, dict) and isinstance(ref.get("path"), str) and isinstance(ref.get("sha256"), str):
        return ref["path"], ref["sha256"]
    return None


def evidence_in(refs, allowed):
    return isinstance(refs, list) and all(reference_key(ref) in allowed for ref in refs)


def private_evidence(attempts):
    for attempt in attempts:
        for role in attempt["roles"].values():
            yield role.get("report")
            yield role.get("brief")
        for key in ("artifact", "artifact_view", "partial_artifact"):
            yield attempt.get(key)
        for test in attempt.get("tests", []):
            yield test["evidence"]
        if attempt["boundary_violation"]:
            yield attempt["boundary_violation"]["evidence"]


def blind_evidence(packet):
    yield packet.get("review_input")
    for group in packet["history"]["groups"]:
        yield from group["evidence"]
    for row in packet["attempts"]:
        yield row["artifact"]
        for entry in row["claims"] + row["tests"]:
            yield entry["evidence"]


def evidence_inventory(root, references):
    declared = {reference_key(ref) for ref in references if ref is not None}
    require(None not in declared, "invalid sealed evidence reference")
    valid = {(path, digest) for path, digest in declared if verified(root, dict(path=path, sha256=digest))}
    return valid, sorted(declared - valid)


def legacy_packet_matches(private, receipt, journal, digest):
    # Earlier v1 runs only bound the packet through its reproducible private evidence.
    # After a move the original workspace prefix is still needed to reproduce its redactions.
    roots = [private.parent]
    for a in journal["attempts"]:
        name = safe_relative(a["id"])
        require(len(name.parts) == 1, "invalid sealed attempt ID")
        request = private / "jobs" / name / "request.json"
        if request.is_file():
            workspace = Path(decode(request.read_bytes(), "sealed request")["workspace"])
            if workspace.parts[-3:] == ("work", a["id"], "workspace") and workspace.parents[2] not in roots:
                roots.append(workspace.parents[2])
    for root in roots:
        document = Packet(private, receipt, journal, case_path=root).document()
        if sha256(json_bytes(document)) == digest:
            return True
    return False


class ScoreInputs:
    def __init__(self, directory):
        case_layout(directory)
        private = directory / "private"
        blind = directory / "blind"
        require(not blind.is_symlink(), "invalid blind directory")
        self.private = private
        self.receipt = load_case(directory)
        self.receipt_sha256 = sha256((private / "receipt.json").read_bytes())
        run_bytes = (private / "run.json").read_bytes()
        self.run_sha256 = sha256(run_bytes)
        self.journal = decode(run_bytes, "run journal")
        for row in self.journal["attempts"]:
            job_layout(directory, row["id"])
        require(type(self.journal.get("schema")) is int and self.journal["schema"] == 1
                and self.journal.get("receipt_sha256") == self.receipt_sha256, "run receipt does not match case")
        packet_bytes = (blind / "packet.json").read_bytes()
        self.packet_sha256 = sha256(packet_bytes)
        expected = self.journal.get("packet_sha256")
        bound = (legacy_packet_matches(private, self.receipt, self.journal, self.packet_sha256)
                 if expected is None else expected == self.packet_sha256)
        require(bound, "packet digest differs from sealed run")
        self.packet = decode(packet_bytes, "scorer packet")
        require(type(self.packet.get("schema")) is int and self.packet["schema"] == 1 and
                self.packet.get("case") == self.journal["case"] and self.packet.get("kind") == self.receipt["kind"],
                "packet identity differs from case")
        self.rows = {a["id"]: a for a in self.packet["attempts"]}
        attempts = self.journal["attempts"]
        require(len(self.rows) == len(self.packet["attempts"]) == len(attempts) and
                {a["id"]: a["outcome"] for a in attempts} == {a["id"]: a["outcome"] for a in self.rows.values()},
                "packet attempts differ from sealed run")
        repetitions = self.journal.get("repetitions")
        require(type(repetitions) is int and repetitions >= 3, "invalid paired slot count")
        completed = set()
        for a in attempts:
            require(type(a.get("pair")) is int and 1 <= a["pair"] <= repetitions and
                    a.get("arm") in ("recorded", "candidate"), "invalid paired slot")
            if a["outcome"] == "completed":
                slot = a["pair"], a["arm"]
                require(slot not in completed and a["boundary_violation"] is None, "ambiguous or incompatible completed slot")
                completed.add(slot)
        verify_attempts(private, self.receipt, self.journal)
        self.private_files, missing_private = evidence_inventory(private, private_evidence(attempts))
        blind_files, missing_blind = evidence_inventory(blind, blind_evidence(self.packet))
        self.review_input = reference_key(self.packet.get("review_input"))
        self.review_input_available = self.review_input is None or self.review_input in blind_files
        ids = {c["id"] for c in self.packet["task"]["criteria"]}
        self.criteria = {}
        for item in self.receipt["criteria"]:
            name = item["id"]
            public = opaque(self.journal, "criterion", name)
            self.criteria[public if public in ids else name] = name
        require(self.criteria.keys() == ids, "packet criteria differ from the frozen task")
        # Only the digest leaves the case. An unjudged artifact can change without altering a single metric.
        self.unavailable_evidence = (sha256(json_bytes([missing_private, missing_blind]))
                                     if missing_private or missing_blind else None)
        self.history_refs = set()
        self.history = dict(self.packet["history"], groups=[], unknown=list(self.packet["history"]["unknown"]))
        for group in self.packet["history"]["groups"]:
            refs = group["evidence"]
            if refs and evidence_in(refs, blind_files):
                self.history["groups"].append(group)
                self.history_refs.update(reference_key(ref) for ref in refs)
            else:
                self.history["unknown"].append(dict(sources=group["sources"], reason="historical evidence unavailable"))
        self.verified_refs = {}
        self.verified_reports = {}
        for attempt in attempts:
            row = self.rows[attempt["id"]]
            reports = {k for k, r in attempt["roles"].items() if r.get("report_valid")
                       and reference_key(r.get("report")) in self.private_files}
            self.verified_reports[row["id"]] = reports
            unreadable = {opaque(self.journal, "claim", row["id"], k, c["finding"])
                          for k, r in attempt["roles"].items() if k not in reports for c in r.get("claims", [])}
            refs = [c["evidence"] for c in row["claims"] if c["id"] not in unreadable]
            sealed_tests = {t["id"]: t for t in attempt.get("tests", [])}
            refs.extend(t["evidence"] for t in row["tests"] if self.criteria.get(t["id"]) in sealed_tests and
                        reference_key(sealed_tests[self.criteria[t["id"]]]["evidence"]) in self.private_files)
            if row["artifact"] and all(reference_key(attempt.get(k)) in self.private_files for k in ("artifact", "artifact_view")):
                refs.append(row["artifact"])
            self.verified_refs[row["id"]] = {reference_key(ref) for ref in refs} & blind_files
