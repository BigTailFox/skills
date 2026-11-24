"""Export first-round evidence under case-local opaque IDs, independently of dispatch order."""
import base64
import hashlib
import hmac
import re

from replay_git import ReplayError, json_bytes, sha256
from replay_protocol import evidence_bytes
from replay_storage import decode, publish
from trace_review_evidence import VALID


def opaque(journal, *identity):
    key = bytes.fromhex(journal["blind_key"])
    return hmac.new(key, json_bytes(identity), hashlib.sha256).hexdigest()[:32]


class Packet:
    def __init__(self, private, receipt, journal):
        self.private = private
        self.receipt = receipt
        self.journal = journal
        self.exports = {}
        briefs = set()
        if receipt["kind"] == "slice":
            historical = receipt["historical_brief"].get("text")
            if historical and historical.strip():
                briefs.add(historical.strip())
            for row in journal["attempts"]:
                ref = row["roles"].get("worker", {}).get("brief")
                if ref:
                    text = evidence_bytes(private, ref).decode(errors="surrogateescape").strip()
                    if text:
                        briefs.add(text)
        self.briefs = sorted(briefs, key=lambda brief: (-len(brief), brief))
        models = {r["model"] for r in journal["roles"].values()}
        models.update(r["model"] for a in journal["attempts"] for r in a["roles"].values()
                      if isinstance(r.get("model"), str) and r["model"])
        versions = {v for suite in receipt["suites"].values() for v in suite.values() if isinstance(v, str)}
        labels = models | versions | {"candidate", "recorded", "old suite", "new suite"}
        self.labels = re.compile(r"(?<![a-z0-9])(?:" + "|".join(map(re.escape, sorted(labels, key=len, reverse=True)))
                                 + r")(?![a-z0-9])", re.I)
        self.workspace_prefix = re.compile(re.escape(str(private.parent / "work")) + r"/[0-9a-f]{32}/workspace/")
        private_roots = [str(private.parent), receipt["project"], receipt["store"], journal["runner"],
                         "/home", "/Users", "/tmp", "/var/tmp", "/private/var/folders"]
        self.private_paths = re.compile("(?:" + "|".join(map(re.escape, sorted(private_roots, key=len, reverse=True)))
                                        + r")(?:/[^\s`'<>\")|]*)?")

    def neutral(self, text):
        for brief in self.briefs:
            text = text.replace(brief, "[redacted]")
        text = self.workspace_prefix.sub("", text)
        text = self.private_paths.sub("[private path]", text)
        text = self.labels.sub("[redacted]", text)
        text = re.sub(r"\b(?:arm|suite)\s*[:=_-]?\s*[AB]\b", "[suite]", text, flags=re.I)
        text = re.sub(r"(?im)^\s*(?:session(?: id)?|model|raw host(?: transcript)?|tokens?|config_digest|"
                      r"wall_seconds|cached_input|reasoning_output|authorization)\s*[:=].*(?:\n|$)", "", text)
        return re.sub(r"(?im)^(?:#{1,4}\s+|\*\*)F\d+\b", "Finding", text)

    def export(self, identity, text):
        data = self.neutral(text).encode()
        return self.export_bytes(identity, data, ".txt")

    def export_bytes(self, identity, data, extension):
        digest = sha256(data)
        # A later worker brief can redact an earlier slice view. Replace that view at its existing opaque path.
        if self.receipt["kind"] != "slice":
            identity = (*identity, digest)
        path = "evidence/" + opaque(self.journal, "file", *identity) + extension
        self.exports[path] = data
        return dict(path=path, sha256=digest)

    def artifact(self, row):
        if not row.get("artifact_view"):
            return None
        evidence_bytes(self.private, row["artifact"])
        view = decode(evidence_bytes(self.private, row["artifact_view"]), "artifact view")
        for item in view["files"]:
            item["path"] = self.neutral(item["path"])
            if item["encoding"] == "base64":
                data = base64.b64decode(item["content"])
                clean = self.neutral(data.decode(errors="surrogateescape")).encode(errors="surrogateescape")
                item["content"] = base64.b64encode(clean).decode("ascii")
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
                raw = base64.b64decode(obs[key + "_base64"])
                data[key] = self.neutral(raw.decode(errors="replace"))
            ref = self.export_bytes(("criterion", row["id"], test["id"]), json_bytes(data), ".json")
            tests.append(dict(id=test["id"], outcome=obs["outcome"], evidence=ref))
        return sorted(tests, key=lambda t: t["evidence"]["path"])

    def history(self):
        original = self.receipt["history"]
        def source(value):
            return opaque(self.journal, "historical-source", value)

        groups = []
        for g in original["groups"]:
            refs = []
            for e in sorted(g["evidence"], key=lambda e: source(e["source"])):
                if sha256(e["text"].encode()) != e["sha256"]:
                    raise ReplayError("historical finding digest differs")
                refs.append(self.export(("historical", source(e["source"])), e["text"]))
            groups.append(dict(id=opaque(self.journal, "historical-group", g["id"]), disposition=g["disposition"],
                               sources=sorted(source(s) for s in g["sources"]), evidence=refs))
        unknown = []
        for entry in original["unknown"]:
            row = dict(sources=sorted(source(s) for s in entry["sources"]), reason=self.neutral(entry["reason"]))
            if "disposition" in entry:
                row["disposition"] = entry["disposition"]
            unknown.append(row)
        confirmations = [dict(source=source(entry["source"])) for entry in original["confirmation_only"]]
        return dict(groups=sorted(groups, key=lambda r: r["id"]),
                    unknown=sorted(unknown, key=lambda r: opaque(self.journal, "unknown", r)),
                    confirmation_only=sorted(confirmations, key=lambda r: r["source"]))

    def attempt(self, row):
        claims = []
        for key, role in row["roles"].items():
            if role.get("report"):
                data = evidence_bytes(self.private, role["report"])
                lines = data.decode(errors="replace").splitlines(keepends=True)
                for c in role["claims"]:
                    text = "".join(lines[c["first_line"] - 1:c["last_line"]])
                    if text != c["text"]:
                        raise ReplayError("sealed finding differs from its report lines")
                    ident = opaque(self.journal, "claim", row["id"], key, c["finding"])
                    claims.append(dict(id=ident, severity=c["severity"], evidence=self.export(("claim", ident), text)))
        return dict(id=row["id"], outcome=row["outcome"], claims=sorted(claims, key=lambda c: c["id"]),
                    artifact=self.artifact(row), tests=self.tests(row))

    def write(self):
        rows = sorted(self.journal["attempts"], key=lambda a: a["id"])
        packet = dict(schema=1, case=self.journal["case"], kind=self.receipt["kind"], task=self.receipt["task"],
                      history=self.history(), attempts=[self.attempt(row) for row in rows])
        data = json_bytes(packet)
        judgments = dict(schema=1, packet_sha256=sha256(data), attempts=[])
        for row in packet["attempts"]:
            groups = [dict(id=opaque(self.journal, "judgment", c["id"]), claims=[c["id"]], historical=None,
                           verdict="unknown", scope="unknown", evidence=[c["evidence"]]) for c in row["claims"]]
            later = []
            if self.receipt["kind"] == "slice":
                refs = [row["artifact"]] if row["artifact"] else []
                later = [dict(historical=g["id"], match="unknown", evidence=refs)
                         for g in packet["history"]["groups"] if g["disposition"] in VALID]
            judgments["attempts"].append(dict(id=row["id"], groups=groups, later=later))
        root = self.private.parent / "blind"
        for path, body in sorted(self.exports.items()):
            publish(root / path, body)
        publish(root / "judgments-template.json", json_bytes(judgments))
        publish(root / "packet.json", data)
        return root / "packet.json"
