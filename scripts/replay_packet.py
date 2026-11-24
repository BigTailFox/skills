"""Export first-round evidence under case-local opaque IDs, independently of dispatch order."""
import base64
import hashlib
import hmac
from pathlib import Path
import posixpath
import re

from replay_git import ReplayError, json_bytes, sha256
from replay_protocol import evidence_bytes
from replay_review_input import review_input
from replay_storage import decode, publish
from trace_records import canon
from trace_review_evidence import VALID


TRANSCRIPT_LABEL = re.compile(r"(?i)^\s*(?:[-*]\s+)?(?:\*\*)?raw host(?: transcript)?(?:\*\*)?\s*[:=]\s*(.*)")
FINDING_FIELD = re.compile(r"(?i)^\s*(?:[-*]\s+)?(?:\*\*)?(?:location|problem|evidence|suggestion|fix|recommendation)(?:\*\*)?\s*:")


def opaque(journal, *identity):
    key = bytes.fromhex(journal["blind_key"])
    return hmac.new(key, json_bytes(identity), hashlib.sha256).hexdigest()[:32]


def fence_delimiter(line, opened):
    match = canon.FENCE_RE.match(line)
    if not match:
        return None
    marker, tail = match["fence"], line[match.end():].strip()
    if opened:
        return marker if not tail and not match["list"] and marker.startswith(opened) else None
    return marker if marker[0] == "~" or "`" not in tail else None


class Packet:
    def __init__(self, private, receipt, journal, *, case_path=None):
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
        labels = models | versions
        self.labels = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, sorted(labels, key=len, reverse=True)))
                                 + r")(?!\w)", re.I)
        roots = {case_path or private.parent, private.parent}
        for row in journal["attempts"]:
            ident = row["id"]
            if not re.fullmatch("[0-9a-f]{32}", ident):
                raise ReplayError("invalid sealed attempt ID")
            request = private / "jobs" / ident / "request.json"
            if request.is_file():
                w = Path(decode(request.read_bytes(), "sealed request")["workspace"])
                if w.is_absolute() and w.parts[-3:] == ("work", ident, "workspace"):
                    roots.add(w.parents[2])
        pattern = "|".join(re.escape(str(r / "work")) for r in sorted(roots))
        self.workspace_prefix = re.compile("(?:" + pattern + r")/[0-9a-f]{32}/workspace/")
        paths = {str(p) for p in roots} | {receipt["project"], receipt["store"], journal["runner"]}
        self.private_paths = re.compile("(?:" + "|".join(map(re.escape, sorted(paths, key=len, reverse=True)))
                                        + r")(?=$|[/\s`'\"<>|)])(?:/[^\s`'<>\"|)]*)?")

    def source(self, text):
        for brief in self.briefs:
            text = text.replace(brief, "[redacted]")
        text = self.workspace_prefix.sub("", text)
        text = self.private_paths.sub("[private path]", text)
        text = self.labels.sub("[redacted]", text)
        return re.sub(r"\b(?:(?:candidate|recorded|old|new)\s+(?:arm|suite)|(?:arm|suite)\s*[:=_-]?\s*"
                      r"(?:[AB]|candidate|recorded))\b", "[suite]", text, flags=re.I)

    def neutral(self, text):
        text = self.private_locations(self.source(text))
        return re.sub(r"(?<![\w./-])(?:candidate|recorded)(?![\w./-])", "[suite]", text, flags=re.I)

    @staticmethod
    def private_locations(text):
        return re.sub(r"(?:/home|/Users|/private/var/folders|/var/tmp|/tmp)/[^\s`'<>\")|]+", "[private path]", text)

    def name(self, path):
        clean = self.source(path)
        # Keep legitimate source names such as src/candidate.py. Alias provenance-bearing
        # components independently, so two redactions cannot merge distinct file identities.
        if clean.count("/") != path.count("/"):
            return "file-" + opaque(self.journal, "path", path)
        components = []
        for orig, new in zip(path.split("/"), clean.split("/")):
            if new != orig or re.match(r"(?i)^(?:candidate|recorded)[-_]", orig):
                new = "file-" + opaque(self.journal, "component", orig)
            components.append(new)
        return "/".join(components)

    def excerpt(self, text):
        lines = self.private_locations(self.source(text)).splitlines(keepends=True)
        public = []
        fence = None
        fence_depth = 0
        quote_fence = None
        quote_depth = 0
        transcript = None
        for line in lines:
            quotation = re.match(r"^[ \t]*>[ \t]?(?:[ \t]*>[ \t]?)*", line)
            depth = quotation[0].count(">") if quotation else 0
            body = (line[quotation.end():] if quotation else line).expandtabs(4)
            if fence and depth < fence_depth:
                fence = None
                if transcript:
                    transcript = "quoted"
            if transcript and fence is None and depth:
                # Only a paragraph can continue lazily outside its explicit quote.
                # Track the quoted fence separately so literal fields inside it stay private.
                if depth < quote_depth:
                    quote_fence = None
                marker = fence_delimiter(body, quote_fence) if not quote_fence or depth == quote_depth else None
                if marker:
                    quote_fence = None if quote_fence else marker
                    quote_depth = depth
                transcript = "quote-break" if marker or quote_fence or not body.strip() else "quoted"
                continue
            quote_fence = None
            if transcript in ("quoted", "quote-break"):
                if not body.strip():
                    transcript = "quote-break"
                    continue
                if transcript == "quoted" or not FINDING_FIELD.match(line):
                    transcript = "quoted"
                    continue
                transcript = None
            marker = fence_delimiter(body, fence) if fence is None or depth == fence_depth else None
            if marker:
                if fence:
                    fence = None
                    transcript = None
                    public.append(line)
                else:
                    fence = marker
                    fence_depth = depth
                    public.append(fence + "\n" if transcript else line)
                    if transcript:
                        transcript = "block"
                continue
            if transcript == "inline" and body.strip():
                # After an explicit omission, an unquoted finding field resumes the
                # report. Quoted fields can themselves be part of a host message.
                transcript = None if FINDING_FIELD.match(line) else "block"
            label = TRANSCRIPT_LABEL.match(body)
            if label:
                omitted = label[1].strip(" \t\n*_`[].()").casefold() in {"omitted", "redacted", "withheld", "none"}
                if depth and fence is None:
                    transcript = "quoted"
                else:
                    transcript = "inline" if omitted and fence is None and not transcript else "block"
            if transcript or re.match(r"(?i)^\s*(?:(?:session(?: id)?|tokens?|config_digest|wall_seconds|"
                                      r"cached_input|reasoning_output|authorization)\s*[:=]|model\s*:)", body):
                continue
            if fence is None:
                line = self.neutral(re.sub(r"(?i)^(?:#{1,4}\s+|\*\*)F\d+\b", "Finding", line))
            public.append(line)
        return "".join(public)

    def export(self, identity, text):
        data = self.excerpt(text).encode()
        return self.export_bytes(identity, data, ".txt")

    def export_bytes(self, identity, data, extension):
        digest = sha256(data)
        path = "evidence/" + opaque(self.journal, "file", *identity) + extension
        self.exports[path] = data
        return dict(path=path, sha256=digest)

    def files(self, view):
        for item in view["files"]:
            original = item["path"]
            item["path"] = self.name(original)
            if item["encoding"] == "utf-8":
                if item["mode"] == "120000":
                    dest = posixpath.normpath(posixpath.join(posixpath.dirname(original), item["content"]))
                    if dest.startswith(("/", "../")) or dest == "..":
                        item["content"] = "[external link]"
                    elif self.name(dest) != dest or original != item["path"]:
                        item["content"] = posixpath.relpath(self.name(dest), posixpath.dirname(item["path"]) or ".")
                    else:
                        item["content"] = self.source(item["content"])
                else:
                    item["content"] = self.source(item["content"])
            elif item["encoding"] == "base64":
                data = base64.b64decode(item["content"])
                decoded = data.decode(errors="surrogateescape")
                if self.source(decoded) != decoded or item["mode"] == "120000" and data.startswith(b"/"):
                    item.update(encoding="withheld", content=None)
        return view

    def artifact(self, row):
        if not row.get("artifact_view"):
            return None
        evidence_bytes(self.private, row["artifact"])
        view = self.files(decode(evidence_bytes(self.private, row["artifact_view"]), "artifact view"))
        return self.export_bytes(("artifact", row["id"]), json_bytes(view), ".json")

    def patch(self, text, names):
        aliases = [(p, self.name(p)) for p in sorted(names, key=len, reverse=True)]
        aliases = [(p, alias) for p, alias in aliases if p != alias]
        lines = text.splitlines(keepends=True)
        headers = ("diff --git ", "--- ", "+++ ", "rename from ", "rename to ", "copy from ", "copy to ", "Binary files ")
        for i, line in enumerate(lines):
            if line.startswith(headers):
                for path, alias in aliases:
                    line = line.replace(path, alias)
                lines[i] = line
        return self.source("".join(lines))

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
            tests.append(dict(id=opaque(self.journal, "criterion", test["id"]), outcome=obs["outcome"], evidence=ref))
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

    def document(self):
        rows = sorted(self.journal["attempts"], key=lambda a: a["id"])
        task = self.receipt["task"].copy()
        task["input"] = dict(task["input"])
        for key in ("paths", "untracked"):
            task["input"][key] = [self.name(p) for p in task["input"][key]]
        if task["delivery"]:
            task["delivery"] = self.neutral(task["delivery"])
        task["criteria"] = [dict(id=opaque(self.journal, "criterion", c["id"]), text=self.neutral(c["text"]))
                            for c in task["criteria"]]
        packet = dict(schema=1, case=self.journal["case"], kind=self.receipt["kind"], task=task,
                      history=self.history(), attempts=[self.attempt(row) for row in rows])
        if self.receipt["kind"] != "slice":
            view = review_input(self.private / "input", self.receipt, self.journal["config"]["read_paths"],
                                self.files, self.patch)
            packet["review_input"] = self.export_bytes(("review-input",), json_bytes(view), ".json")
        return packet

    def write(self):
        packet = self.document()
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
        for directory in (root, root / "evidence"):
            if directory.is_symlink() or directory.exists() and not directory.is_dir():
                raise ReplayError("invalid blind evidence directory")
        # Read the previous manifest before publishing; migrate older digest-derived names
        # only when that packet is the one the controller sealed.
        previous = root / "packet.json"
        obsolete = set()
        if previous.is_file() and not previous.is_symlink():
            old = previous.read_bytes()
            if sha256(old) == self.journal.get("packet_sha256"):
                obsolete.update(re.findall(r'"path": "(evidence/[0-9a-f]{32}\.(?:txt|json))"', old.decode()))
        for path, body in sorted(self.exports.items()):
            publish(root / path, body)
        publish(root / "judgments-template.json", json_bytes(judgments))
        publish(root / "packet.json", data)
        for path in obsolete - self.exports.keys():
            (root / path).unlink(missing_ok=True)
        return root / "packet.json"
