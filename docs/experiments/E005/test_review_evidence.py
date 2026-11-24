import csv
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
COMMIT_TITLES = "20261120T134358Z-d5efff"
SCRATCH = HERE.parents[2] / ".canon/canon-implement/P009/S1"


class PublishedEvidence(unittest.TestCase):
    def test_commit_title_defects_each_have_both_original_sources(self):
        table = HERE / "review-evidence.tsv"
        with table.open() as stream:
            rows = {int(r["raw_row"]): (r["report_stem"], r["finding_id"],
                                        r["defect_group"], r["disposition"])
                    for r in csv.DictReader(stream, delimiter="\t")
                    if r["project"] == "Silk" and r["unit"] == COMMIT_TITLES}
        self.assertEqual(rows, {
            1: ("spec", "F1", "merge-amendment", "accepted"),
            2: ("spec", "F2", "template-comment", "accepted"),
            3: ("standards", "F1", "merge-amendment", "accepted"),
            4: ("standards", "F2", "template-comment", "accepted"),
        })
    def test_frozen_end_rows_and_phase_are_accounted_for(self):
        with (HERE / "review-evidence.tsv").open() as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
        keys = {(r["project"], r["unit"], r["raw_row"]) for r in rows if r["raw_row"]}
        self.assertEqual(len(keys), 157)
        self.assertEqual(len({key[:2] for key in keys}), 20)
        self.assertEqual(sum(not r["raw_row"] for r in rows), 20)
        self.assertEqual({(r["raw_row"], r["report_stem"]) for r in rows
                          if r["phase"] == "confirmation"},
                         {("9", "spec-confirm"), ("10", "spec-confirm"),
                          ("18", "standards-confirm")})

    def test_mixed_or_overridden_dispositions_keep_their_original_values(self):
        with (HERE / "review-evidence.tsv").open() as f:
            rows = {(r["unit"], r["report_stem"], r["finding_id"]):
                    (r["raw_disposition"], r["disposition"]) for r in csv.DictReader(f, delimiter="\t")}
        gate = "20261118T073105Z-459748"
        self.assertEqual(rows[(gate, "cross-family", "F11")], ("accepted", "declined"))
        self.assertEqual(rows[(gate, "cross-family-gemini", "F4")], ("", "unknown"))
        self.assertEqual(rows[("20261116T042358Z-20c8a5", "cross-family", "F7")],
                         ("accepted", "unknown"))


def write_table(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, rows[0], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ArchiveCheck(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.project = self.base / "project"
        self.unit = "20260101T000000Z-aaaaaa"
        self.archive = self.project / ".canon/canon/trace" / self.unit
        self.archive.mkdir(parents=True)
        self.ledger = self.base / "cases.tsv"
        self.evidence = self.base / "review-evidence.tsv"
        self.catalog = self.base / "review-adjudications.tsv"
        self.host = self.base / "review-host.tsv"
        self.cursor = self.base / "cursor"
        self.database = self.base / "state.vscdb"
        self.host.write_text("project\tunit\n")
        self.case = dict(project="Example", unit=self.unit, kind="code-review",
                         outcome="delivered", start_event=1, end_event=2, findings=4)
        write_table(self.ledger, [self.case])
        start = dict(type="start", id=self.unit, kind="code-review")
        self.end = dict(type="end", id=self.unit, kind="code-review", outcome="delivered",
                        archive="ok", dispositions={"reviewers": [], "findings": []})
        self.start_line = json.dumps(start)
        self.rows = []
        self.sources = []
        for stem in ["spec", "standards"]:
            reviewer = {"role": stem, "model": "model", "id": "session-" + stem}
            self.end["dispositions"]["reviewers"].append(reviewer)
            blob = (f"### F1 [major] Group A\nPrivate fixture {stem} A.\n"
                    f"### F2 [minor] Group B\nPrivate fixture {stem} B.\n").encode()
            (self.archive / (stem + ".md")).write_bytes(blob)
            (self.archive / (stem + "-id.txt")).write_text(reviewer["id"])
            (self.archive / (stem + "-prompt.md")).write_text("Review the fixture.")
            self.sources.append(dict(project="Example", unit=self.unit, report_stem=stem,
                                     reviewer_key=stem, role=stem, model="model",
                                     reviewer_id=reviewer["id"], phase="first", report_sha256=digest(blob),
                                     groups="F1=group-a F2=group-b", decisions=""))
            for fid, line, group in [("F1", 1, "group-a"), ("F2", 3, "group-b")]:
                self.end["dispositions"]["findings"].append(
                    {"by": [stem + ":" + fid], "disposition": "accepted"})
                self.rows.append(dict(project="Example", unit=self.unit, raw_row=len(self.rows)+1,
                                      report_stem=stem, finding_id=fid, defect_group=group,
                                      disposition="accepted", source_locator=f"{stem}.md:L{line}",
                                      end_sha256="", report_sha256=digest(blob),
                                      raw_disposition="accepted", phase="first", reviewer_key=stem))
        self.write_end()
        write_table(self.catalog, self.sources)

    def write_end(self):
        end_line = json.dumps(self.end)
        (self.archive.parent / "events.jsonl").write_text(self.start_line + "\n" + end_line + "\n")
        for r in self.rows:
            r["end_sha256"] = digest(end_line.encode())
        write_table(self.evidence, self.rows)

    def run_check(self):
        return subprocess.run([sys.executable, str(HERE / "check_reviews.py"),
                               "--project", f"Example={self.project}", "--ledger", str(self.ledger),
                               "--review-evidence", str(self.evidence), "--adjudications", str(self.catalog),
                               "--host-receipts", str(self.host), "--cursor-home", str(self.cursor),
                               "--cursor-state-db", str(self.database)],
                              capture_output=True, text=True)

    def test_two_reports_share_two_distinct_defects(self):
        before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.project.rglob("*") if p.is_file()}
        run = self.run_check()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        reviews = json.loads(run.stdout)["reviews"]
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["raw_rows"], 4)
        self.assertEqual(reviews[0]["valid_first_groups"], 2)
        self.assertEqual(reviews[0]["joint"], {"spec": 2, "standards": 2})
        self.assertEqual(reviews[0]["exclusive"], {"spec": 0, "standards": 0})
        self.assertEqual(before, {p: (p.stat().st_mtime_ns, p.read_bytes())
                                  for p in self.project.rglob("*") if p.is_file()})

    def assert_unknown(self):
        run = self.run_check()
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        row, = json.loads(run.stdout)["reviews"]
        self.assertEqual(row["status"], "unknown")
        self.assertNotIn("exclusive", row)
        self.assertNotIn("joint", row)
        self.assertNotIn("Private fixture", run.stdout + run.stderr)

    def test_crossed_pairs_cannot_receive_joint_or_exclusive_credit(self):
        self.rows[2]["defect_group"] = "group-b"
        self.rows[3]["defect_group"] = "group-a"
        write_table(self.evidence, self.rows)
        self.assert_unknown()

    def test_two_incompatible_findings_cannot_acquire_one_group(self):
        self.rows[1]["defect_group"] = "group-a"
        write_table(self.evidence, self.rows)
        self.assert_unknown()

    def test_conflicting_dispositions_within_a_group_withhold_that_group_only(self):
        self.end["dispositions"]["findings"][2]["disposition"] = "deferred"
        self.rows[2].update(disposition="deferred", raw_disposition="deferred")
        self.write_end()
        run = self.run_check()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        row, = json.loads(run.stdout)["reviews"]
        self.assertEqual(row["valid_first_groups"], 1)
        self.assertEqual(row["joint"], {"spec": 1, "standards": 1})
        self.assertEqual(row["exclusive"], {"spec": 0, "standards": 0})

    def test_report_substitution_even_with_an_updated_table_digest_is_rejected(self):
        alternate = (self.archive / "spec.md").read_bytes()
        (self.archive / "standards.md").write_bytes(alternate)
        for row in self.rows[2:]:
            row["report_sha256"] = digest(alternate)
        write_table(self.evidence, self.rows)
        self.assert_unknown()

    def test_missing_first_report(self):
        report = self.archive / "spec.md"
        report.rename(report.with_suffix(".absent"))
        self.assert_unknown()

    def test_duplicate_table_source(self):
        write_table(self.evidence, self.rows + self.rows[:1])
        self.assert_unknown()

    def test_locator_must_identify_the_numbered_finding(self):
        self.rows[0]["source_locator"] = "spec.md:L2"
        write_table(self.evidence, self.rows)
        self.assert_unknown()

    def test_source_must_match_recorded_reviewer_identity(self):
        (self.archive / "spec-id.txt").write_text("another-session")
        self.assert_unknown()

    def test_a_stale_end_digest_withholds_credit(self):
        self.rows[0]["end_sha256"] = "0" * 64
        write_table(self.evidence, self.rows)
        self.assert_unknown()

    def test_two_ends_for_the_named_unit_are_ambiguous(self):
        with (self.archive.parent / "events.jsonl").open("a") as stream:
            stream.write(json.dumps(self.end) + "\n")
        self.assert_unknown()

    def test_unaccounted_delivered_report_invalidates_exclusivity(self):
        (self.archive / "cross-family-2.md").write_text("### F1 [major] Additional finding.")
        self.assert_unknown()

    def test_handoff_exposes_partial_coverage_without_contributing_a_zero(self):
        self.case["outcome"] = self.end["outcome"] = "handoff"
        write_table(self.ledger, [self.case])
        self.write_end()
        run = self.run_check()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        row, = json.loads(run.stdout)["reviews"]
        self.assertEqual(row.get("coverage"), "partial-handoff")
        self.assertEqual(row["raw_rows"], 4)
        self.assertIsNone(row.get("valid_first_groups"))
        self.assertNotIn("exclusive", row)

    def add_supplement(self):
        conversation = "00000000-0000-4000-8000-000000000001"
        session = "00000000-0000-4000-8000-000000000002"
        topic = self.cursor / "projects/example/agent-transcripts" / conversation
        children = topic / "subagents"
        children.mkdir(parents=True)
        start = json.loads(self.start_line)
        start["conversation"] = conversation
        self.start_line = json.dumps(start)
        stem = "cross-family-extra"
        content = ["Review the fixture.", "### F1 [minor] Third defect\nPrivate fixture C.",
                   "Fixed findings: F1 (section 3).", "- **F1**: resolved.\n\nVerdict: approve"]
        receipts = []
        for action, text, file, role in zip(
                ["dispatch", "first", "fixed", "terminal"], content,
                ["-prompt.md", ".md", "-confirm-prompt.md", "-confirm.md"],
                ["user", "assistant", "user", "assistant"]):
            (self.archive / (stem + file)).write_text(text)
            line = json.dumps({"role": role, "message": {"content": [{"type": "text", "text": text}]}})
            with (children / (session + ".jsonl")).open("a") as f:
                f.write(line + "\n")
            receipts.append(dict(project="Example", unit=self.unit, report_stem=stem, evidence=action,
                                 conversation=conversation, session=session, line=len(receipts)+1,
                                 sha256=digest(line.encode())))
        parent = topic / (conversation + ".jsonl")
        for i, action in enumerate(["decision", "final"], 1):
            line = json.dumps({"role": "assistant", "message": {"content": [
                {"type": "text", "text": action + " on the additional report"}]}})
            with parent.open("a") as f:
                f.write(line + "\n")
            receipts.append(dict(project="Example", unit=self.unit, report_stem=stem, evidence=action,
                                 conversation=conversation, session=conversation, line=i, sha256=digest(line.encode())))
        (self.archive / (stem + "-id.txt")).write_text(session)
        src = dict(project="Example", unit=self.unit, report_stem=stem, reviewer_key="cross-family-2",
                   role="cross-family", model="additional-model", reviewer_id=session, phase="first",
                   report_sha256=digest(content[1].encode()), groups="F1=third", decisions="F1=accepted")
        self.sources.append(src)
        self.rows.append(dict(project="Example", unit=self.unit, raw_row="", report_stem=stem, finding_id="F1",
                              defect_group="third", disposition="accepted", source_locator=stem+".md:L1",
                              end_sha256="", report_sha256=src["report_sha256"], raw_disposition="",
                              phase="first", reviewer_key="cross-family-2"))
        self.write_end()
        write_table(self.catalog, self.sources)
        model_record = {"toolFormerData": {"name": "task_v2", "status": "completed",
                        "params": json.dumps({"model": "additional-model", "prompt": content[0]}),
                        "result": json.dumps({"agentId": session})}}
        key = "bubbleId:" + conversation + ":fixture-call"
        raw = json.dumps(model_record)
        with sqlite3.connect(self.database) as db:
            db.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value BLOB)")
            db.execute("INSERT INTO cursorDiskKV VALUES (?,?)", (key, raw))
        receipts.append(dict(project="Example", unit=self.unit, report_stem=stem, evidence="model-dispatch",
                             conversation=conversation, session=session, line=key, sha256=digest(raw.encode())))
        write_table(self.host, receipts)
        return children / (session + ".jsonl")

    def test_omitted_source_requires_its_original_dispatch_and_two_terminal_reports(self):
        child = self.add_supplement()
        self.assertEqual(self.run_check().returncode, 0)
        child.rename(child.with_suffix(".absent"))
        self.assert_unknown()

    def test_a_terminal_reply_must_resolve_the_listed_finding_to_support_acceptance(self):
        child = self.add_supplement()
        lines = child.read_text().splitlines()
        terminal = json.loads(lines[-1])
        text = "- **F1**: not resolved.\n\nVerdict: revise"
        terminal["message"]["content"][0]["text"] = text
        lines[-1] = json.dumps(terminal)
        child.write_text("\n".join(lines) + "\n")
        (self.archive / "cross-family-extra-confirm.md").write_text(text)
        with self.host.open() as stream:
            receipts = list(csv.DictReader(stream, delimiter="\t"))
        next(r for r in receipts if r["evidence"] == "terminal")["sha256"] = digest(lines[-1].encode())
        write_table(self.host, receipts)
        self.assert_unknown()

    def test_swapped_model_cannot_claim_an_independently_bound_dispatch(self):
        self.add_supplement()
        self.sources[-1]["model"] = "different-model"
        write_table(self.catalog, self.sources)
        self.assert_unknown()

    def test_disjoint_targets_withhold_single_source_exclusivity(self):
        for common in (True, False):
            with self.subTest(common=common):
                for i, src in enumerate(self.sources):
                    prompt = "Target: same" if i == 0 or common else "Target: another"
                    (self.archive / (src["report_stem"] + "-prompt.md")).write_text(prompt)
                    src.update(prompt_sha256=digest(prompt.encode()), scope_lines="1-1",
                               groups=("F1=only-spec F2=group-b" if i == 0 else "F1=only-standards F2=group-b"))
                    for row in self.rows:
                        if row["report_stem"] == src["report_stem"]:
                            row.update(prompt_sha256=src["prompt_sha256"], scope_lines="1-1")
                            if row["finding_id"] == "F1":
                                row["defect_group"] = "only-" + src["report_stem"]
                write_table(self.catalog, self.sources)
                write_table(self.evidence, self.rows)
                run = self.run_check()
                self.assertEqual(run.returncode, 0, run.stdout)
                record, = json.loads(run.stdout)["reviews"]
                self.assertEqual(record["exclusive"], {"spec": int(common), "standards": int(common)})
                self.assertEqual(sum(record["single_source_unknown"].values()), 0 if common else 2)
        (self.archive / "spec-prompt.md").write_text("Target: changed after adjudication")
        self.assert_unknown()


if __name__ == "__main__":
    unittest.main()
