"""Verify digest-less v1 handoffs against the evidence retained by their original controllers."""
import base64
from pathlib import Path
import re

from replay_git import ReplayError, json_bytes, sha256
from replay_packet import Packet, opaque
from replay_protocol import evidence_bytes
from replay_storage import decode


class HistoricalDigest:
    """The 2c56338 and ba56b11 wire formats. No historical projection is written to the handoff."""
    def __init__(self, private, receipt, journal, original_root, redact_costs):
        self.private = private
        self.receipt = receipt
        self.journal = journal
        briefs = set()
        if receipt["kind"] == "slice":
            briefs.add((receipt["historical_brief"].get("text") or "").strip())
            for row in journal["attempts"]:
                ref = row["roles"].get("worker", {}).get("brief")
                if ref:
                    briefs.add(evidence_bytes(private, ref).decode(errors="surrogateescape").strip())
        self.briefs = sorted(briefs - {""}, key=lambda b: (-len(b), b))
        models = {r["model"] for r in journal["roles"].values()}
        models.update(r["model"] for a in journal["attempts"] for r in a["roles"].values()
                      if isinstance(r.get("model"), str) and r["model"])
        versions = {v for suite in receipt["suites"].values() for v in suite.values() if isinstance(v, str)}
        labels = models | versions | {"candidate", "recorded", "old suite", "new suite"}
        self.labels = re.compile(r"(?<![a-z0-9])(?:" + "|".join(map(re.escape, sorted(labels, key=len, reverse=True)))
                                 + r")(?![a-z0-9])", re.I)
        self.workspaces = re.compile(re.escape(str(original_root / "work")) + r"/[0-9a-f]{32}/workspace/")
        roots = [str(original_root), receipt["project"], receipt["store"], journal["runner"],
                 "/home", "/Users", "/tmp", "/var/tmp", "/private/var/folders"]
        self.paths = re.compile("(?:" + "|".join(map(re.escape, sorted(roots, key=len, reverse=True)))
                                + r")(?:/[^\s`'<>\")|]*)?")
        # The first review release preceded the slice release's additional metadata keys.
        cost_keys = "wall_seconds|cached_input|reasoning_output|" if redact_costs else ""
        self.metadata = re.compile(r"(?im)^\s*(?:session(?: id)?|model|raw host(?: transcript)?|tokens?|config_digest|"
                                   + cost_keys + r"authorization)\s*[:=].*(?:\n|$)")

    def neutral(self, text):
        for brief in self.briefs:
            text = text.replace(brief, "[redacted]")
        text = self.labels.sub("[redacted]", self.paths.sub("[private path]", self.workspaces.sub("", text)))
        text = re.sub(r"\b(?:arm|suite)\s*[:=_-]?\s*[AB]\b", "[suite]", text, flags=re.I)
        text = self.metadata.sub("", text)
        return re.sub(r"(?im)^(?:#{1,4}\s+|\*\*)F\d+\b", "Finding", text)

    def export_bytes(self, identity, data, extension):
        digest = sha256(data)
        if self.receipt["kind"] != "slice":
            identity = (*identity, digest)
        return dict(path="evidence/" + opaque(self.journal, "file", *identity) + extension, sha256=digest)

    def export(self, identity, text):
        return self.export_bytes(identity, self.neutral(text).encode(), ".txt")

    def artifact(self, row):
        if not row.get("artifact_view"):
            return None
        evidence_bytes(self.private, row["artifact"])
        view = decode(evidence_bytes(self.private, row["artifact_view"]), "artifact view")
        for item in view["files"]:
            item["path"] = self.neutral(item["path"])
            if item["encoding"] == "base64":
                raw = base64.b64decode(item["content"]).decode(errors="surrogateescape")
                item["content"] = base64.b64encode(self.neutral(raw).encode(errors="surrogateescape")).decode("ascii")
            else:
                item["content"] = self.neutral(item["content"])
        return self.export_bytes(("artifact", row["id"]), json_bytes(view), ".json")

    def tests(self, row):
        tests = []
        for test in row.get("tests", []):
            obs = decode(evidence_bytes(self.private, test["evidence"]), "criterion evidence")
            if any(test[key] != obs[key] for key in ("id", "argv", "outcome", "reason")):
                raise ReplayError("criterion outcome differs from its sealed evidence")
            data = dict(outcome=obs["outcome"], exit_code=obs["exit_code"], reason=self.neutral(obs["reason"] or ""),
                        argv=[self.neutral(a) for a in obs["argv"]] if obs["argv"] else None)
            for key in ("stdout", "stderr"):
                data[key] = self.neutral(base64.b64decode(obs[key + "_base64"]).decode(errors="replace"))
            ref = self.export_bytes(("criterion", row["id"], test["id"]), json_bytes(data), ".json")
            tests.append(dict(id=test["id"], outcome=obs["outcome"], evidence=ref))
        return sorted(tests, key=lambda t: t["evidence"]["path"])

    def digest(self):
        rows = sorted(self.journal["attempts"], key=lambda a: a["id"])
        # Both formats use the same source/group identities and exact sealed first-round finding ranges.
        document = dict(schema=1, case=self.journal["case"], kind=self.receipt["kind"], task=self.receipt["task"],
                        history=Packet.history(self), attempts=[Packet.attempt(self, row) for row in rows])
        return sha256(json_bytes(document))


def legacy_packet_matches(private, receipt, journal, digest):
    # A current handoff with a missing journal digest must still bind its current review input and criteria.
    jobs = [private / "jobs" / row["id"] for row in journal["attempts"]]
    sealed = {(job / "slot.json").is_file() for job in jobs}
    if sealed == {True}:
        return sha256(json_bytes(Packet(private, receipt, journal).document())) == digest
    if not jobs or len(sealed) != 1:
        raise ReplayError("ambiguous legacy packet format: no consistent dispatch generation")
    formats = set()
    completion_roots = {}
    for job in jobs:
        request, dispatch = job / "request.json", job / "dispatch.json"
        if not (request.is_file() and dispatch.is_file()):
            raise ReplayError("legacy slot has no retained dispatch")
        path = Path(decode(request.read_bytes(), "sealed request")["workspace"])
        if not path.is_absolute() or path.parts[-3:] != ("work", job.name, "workspace"):
            raise ReplayError("invalid original workspace in the legacy request")
        spec = decode(dispatch.read_bytes(), "legacy dispatch")
        # The slice-capable controller introduced both receipt-bound dispatches and cost redaction.
        redact_costs = "receipt_sha256" in spec
        if redact_costs and spec["receipt_sha256"] != journal["receipt_sha256"]:
            raise ReplayError("legacy dispatch receipt differs from the case")
        if not redact_costs and receipt["kind"] == "slice":
            raise ReplayError("legacy dispatch format cannot publish a slice")
        formats.add(redact_costs)
        terminal = job / "terminal.json"
        ended = decode(terminal.read_bytes(), "legacy terminal record").get("ended") if terminal.is_file() else None
        if not isinstance(ended, str) or not ended:
            raise ReplayError("legacy slot has no verified dispatch interval")
        completion_roots.setdefault(ended, set()).add(path.parents[2])
    if len(formats) != 1:
        raise ReplayError("ambiguous legacy packet format across dispatches")
    # The historical controller serially dispatched the slots, then published from that invocation's directory.
    # The independently retained UTC completion times survive another move or a reordered journal.
    last_roots = completion_roots[max(completion_roots)]
    if len(last_roots) != 1:
        raise ReplayError("ambiguous final legacy dispatch location")
    return HistoricalDigest(private, receipt, journal, last_roots.pop(), formats.pop()).digest() == digest
