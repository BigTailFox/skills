"""Review and tier questions at the offline report's public CLI."""
import csv
import hashlib
import json
import shutil
import sqlite3

from test_trace_report import CONV, GATE, PRIOR, UNIT, ReportFixture, end, start, write_lines


def reviewer(role, session=None, **extra):
    return dict(role=role, model="model-a", id=session, **extra)


def review_end(unit, kind, reviewers, findings, blockers=0, **extra):
    return end(unit, kind, dispositions=dict(reviewers=reviewers, findings=findings, new_blockers=blockers),
               archive="ok", **extra)


def sha(content):
    return hashlib.sha256(content.encode()).hexdigest()


def table(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, rows[0], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class ReviewReport(ReportFixture):
    def archive_report(self, unit, key, content, sid="", prompt="Target: fixture"):
        archive = self.log.parent / unit
        archive.mkdir(parents=True, exist_ok=True)
        (archive / (key + ".md")).write_text(content)
        (archive / (key + "-prompt.md")).write_text(prompt)
        (archive / (key + "-id.txt")).write_text(sid)

    def paired_review(self):
        people = [reviewer("spec", "one"), reviewer("standards", "two")]
        findings, rows, catalog = [], [], []
        for person in people:
            stem = person["role"]
            body = f"### F1 [major] PRIVATE {stem}\n### F2 [minor] PRIVATE {stem}"
            prompt = "Targets: alpha.py and beta.py"
            self.archive_report(UNIT, stem, body, person["id"], prompt)
            common = dict(project="Example", unit=UNIT, report_stem=stem, reviewer_key=stem,
                          phase="first", report_sha256=sha(body), prompt_sha256=sha(prompt), scope_lines="1-1")
            catalog.append(dict(common, role=stem, reviewer_id=person["id"], model=person["model"],
                                groups="F1=merge-amendment F2=template-comment", decisions="",
                                decision_locator="", decision_sha256=""))
            for i, (group, severity) in enumerate([("merge-amendment", "major"), ("template-comment", "minor")], 1):
                findings.append(dict(by=[stem + ":F" + str(i)], axis=stem, disposition="accepted", severity=severity))
                rows.append(dict(common, raw_row=str(len(findings)), finding_id="F"+str(i), defect_group=group,
                                 disposition="accepted", raw_disposition="accepted", end_sha256="",
                                 source_locator=f"{stem}.md:L{i}"))
        end_event = review_end(UNIT, "code-review", people, findings)
        write_lines(self.log, [start(kind="code-review", tier="L0"), end_event])
        for row in rows:
            row["end_sha256"] = sha(json.dumps(end_event))
        self.evidence = self.root / "review-evidence.tsv"
        self.catalog = self.root / "review-adjudications.tsv"
        table(self.evidence, rows)
        table(self.catalog, catalog)
        return rows, catalog, end_event

    def test_four_raw_axis_rows_resolve_to_two_joint_defects(self):
        self.paired_review()
        report = self.cli("--review-evidence", self.evidence)
        self.assertIn("3", report["questions"].keys())
        review = report["cases"][0]["review"]
        self.assertEqual((review["raw_rows"], review["adjudicated_valid_groups"], review["valid_first_groups"]), (4, 2, 2))
        self.assertEqual(review["joint"], {"spec": 2, "standards": 2})
        self.assertEqual(review["exclusive"], {"spec": 0, "standards": 0})
        self.assertTrue(review["comparable_scope"])
        self.assertEqual({r["group"] for r in review["groups"]}, {"merge-amendment", "template-comment"})
        stats, = report["questions"]["3"]["groups"]
        self.assertEqual(stats["tier"], "L0")
        for axis in ("spec", "standards"):
            joint = stats["axes"][axis]["joint"]
            self.assertEqual((joint["numerator"], joint["denominator"]), (2, 1))
            self.assertIn(str(self.evidence) + "#L", str(joint["cases"]))
            self.assertIn(str(self.catalog) + "#L", str(joint["cases"]))
        self.assertIn("merge-amendment", self.cli("--review-evidence", self.evidence, text=True))

    def test_minimal_table_can_use_the_separate_catalogs_scope_receipts(self):
        rows, _, _ = self.paired_review()
        fields = {"project", "unit", "raw_row", "report_stem", "finding_id", "defect_group", "disposition",
                  "source_locator", "end_sha256", "report_sha256"}
        table(self.evidence, [{k: v for k, v in row.items() if k in fields} for row in rows])
        review = self.cli("--review-evidence", self.evidence)["cases"][0]["review"]
        self.assertEqual(review["valid_first_groups"], 2)
        self.assertTrue(review["comparable_scope"])

    def test_pinned_first_heading_may_follow_a_flattened_host_preamble(self):
        rows, catalog, _ = self.paired_review()
        path = self.log.parent / UNIT / "spec.md"
        body = "PRIVATE host preamble mentions F2 without a heading. " + path.read_text()
        path.write_text(body)
        catalog[0]["report_sha256"] = sha(body)
        for r in rows[:2]:
            r["report_sha256"] = sha(body)
        table(self.evidence, rows)
        table(self.catalog, catalog)
        self.assertEqual(self.cli("--review-evidence", self.evidence)["cases"][0]["review"]["valid_first_groups"], 2)

    def test_crossed_stale_or_incomplete_corrections_do_not_supply_independent_credit(self):
        rows, _, _ = self.paired_review()
        def result():
            return self.cli("--review-evidence", self.evidence)["cases"][0]["review"]
        crossed = [dict(r) for r in rows]
        crossed[2]["defect_group"], crossed[3]["defect_group"] = crossed[3]["defect_group"], crossed[2]["defect_group"]
        table(self.evidence, crossed)
        self.assertEqual({g["attribution"] for g in result()["groups"]}, {"unverified"})
        for patch in [dict(finding_id="F9"), dict(end_sha256="f"*64), dict(report_sha256="f"*64),
                      dict(raw_row="2"), dict(source_locator="spec.md:L2"), dict(project="other-project")]:
            with self.subTest(patch=patch):
                table(self.evidence, [dict(rows[0], **patch), *rows[1:]])
                self.assertEqual(result()["raw_rows"], 4)
                self.assertEqual(result()["valid_first_groups"], "unknown")
        for mapping in [rows[:-1], [*rows, rows[0]]]:
            table(self.evidence, mapping)
            self.assertEqual(result()["valid_first_groups"], "unknown")
        table(self.evidence, rows)
        archive = self.log.parent / UNIT
        (archive / "cross-family-2-prompt.md").write_text("Target: additional dispatch")
        self.assertEqual(result()["valid_first_groups"], "unknown")

    def test_identical_receipts_in_two_selected_projects_require_a_project_binding(self):
        rows, catalog, _ = self.paired_review()
        mirror = self.root / "mirror" / "project"
        shutil.copytree(self.project, mirror)
        def result():
            return self.cli("--project", self.project, "--project", mirror, "--review-evidence", self.evidence)["cases"]
        copies = result()
        self.assertEqual([c["review"]["valid_first_groups"] for c in copies], ["unknown", "unknown"])
        for r in rows + catalog:
            r["project"] = str(mirror)
        table(self.evidence, rows)
        table(self.catalog, catalog)
        left, right = result()
        self.assertEqual((left["review"]["valid_first_groups"], right["review"]["valid_first_groups"]), ("unknown", 2))

    def test_repeated_reviewer_session_does_not_let_two_report_keys_exchange_source_files(self):
        rows, catalog, event = self.paired_review()
        for reviewer in event["dispositions"]["reviewers"]:
            reviewer["id"] = "same-session"
            (self.log.parent / UNIT / (reviewer["role"] + "-id.txt")).write_text("same-session")
        for r in catalog:
            r["reviewer_id"] = "same-session"
            r["role"] = r["reviewer_key"] = "standards" if r["role"] == "spec" else "spec"
        for r in rows:
            r["reviewer_key"] = "standards" if r["report_stem"] == "spec" else "spec"
            r["raw_row"] = str(int(r["raw_row"]) + (2 if r["report_stem"] == "spec" else -2))
            r["end_sha256"] = sha(json.dumps(event))
        write_lines(self.log, [start(kind="code-review"), event])
        table(self.catalog, catalog)
        table(self.evidence, rows)
        review = self.cli("--review-evidence", self.evidence)["cases"][0]["review"]
        self.assertEqual(review["valid_first_groups"], "unknown")
        self.assertEqual(review["raw_rows"], 4)

    def test_a_report_finding_omitted_at_close_needs_separate_disposition_evidence(self):
        rows, catalog, event = self.paired_review()
        event["dispositions"]["findings"].pop()
        rows[-1].update(raw_row="", raw_disposition="")
        catalog[-1]["decisions"] = "F2=accepted"
        for row in rows:
            row["end_sha256"] = sha(json.dumps(event))
        write_lines(self.log, [start(kind="code-review"), event])
        table(self.evidence, rows)
        table(self.catalog, catalog)
        self.assertEqual(self.cli("--review-evidence", self.evidence)["cases"][0]["review"]["valid_first_groups"], "unknown")
        note = "PRIVATE parent accepted the omitted standards finding"
        (self.log.parent / UNIT / "merge-notes.md").write_text(note)
        catalog[-1].update(decision_locator="merge-notes.md:L1", decision_sha256=sha(note))
        table(self.catalog, catalog)
        self.assertEqual(self.cli("--review-evidence", self.evidence)["cases"][0]["review"]["valid_first_groups"], 2)

    def test_splitting_a_raw_major_does_not_transfer_its_severity_to_a_minor_cross_family_finding(self):
        rows, catalog, event = self.paired_review()
        archive = self.log.parent / UNIT
        for suffix in (".md", "-id.txt", "-prompt.md"):
            (archive / ("standards"+suffix)).rename(archive / ("cross-family"+suffix))
        path = archive / "cross-family.md"
        text = path.read_text().replace("[major]", "[minor]")
        path.write_text(text)
        event["dispositions"]["reviewers"][1]["role"] = "cross-family"
        findings = event["dispositions"]["findings"]
        findings[0]["by"].append("cross-family:F1")
        findings.pop(2)
        findings[2]["by"] = ["cross-family:F2"]
        catalog[0]["groups"] = "F1=spec-group F2=template-comment"
        catalog[1].update(role="cross-family", reviewer_key="cross-family", report_stem="cross-family",
                          report_sha256=sha(text), groups="F1=cross-only F2=template-comment")
        rows[0]["defect_group"] = "spec-group"
        rows[2].update(raw_row="1", defect_group="cross-only")
        rows[3]["raw_row"] = "3"
        for i, r in enumerate(rows):
            r["end_sha256"] = sha(json.dumps(event))
            if i >= 2:
                r.update(report_stem="cross-family", reviewer_key="cross-family", report_sha256=sha(text),
                         source_locator=r["source_locator"].replace("standards", "cross-family"))
        write_lines(self.log, [start(kind="code-review"), event])
        table(self.evidence, rows)
        table(self.catalog, catalog)
        q1, = self.cli("--review-evidence", self.evidence)["questions"]["1"]["groups"]
        self.assertEqual((q1["verified"]["numerator"], q1["verified"]["denominator"]), (0, 1))

    def test_common_scope_is_required_for_single_source_exclusivity(self):
        rows, catalog, _ = self.paired_review()
        for r in rows:
            if r["finding_id"] == "F1":
                r["defect_group"] = r["report_stem"] + "-only"
        for s in catalog:
            s["groups"] = f"F1={s['report_stem']}-only F2=template-comment"
        table(self.evidence, rows)
        table(self.catalog, catalog)
        def review():
            return self.cli("--review-evidence", self.evidence)["cases"][0]["review"]
        self.assertEqual(review()["exclusive"], {"spec": 1, "standards": 1})
        for r in rows + catalog:
            if r["report_stem"] == "spec":
                r["scope_lines"] = ""
        table(self.evidence, rows)
        table(self.catalog, catalog)
        record = review()
        self.assertEqual(record["joint"], {"spec": 1, "standards": 1})
        self.assertEqual(record["single_source_unknown"], {"spec": 1, "standards": 1})
        self.assertEqual(record["exclusive"], {"spec": 0, "standards": 0})
        (self.log.parent / UNIT / "spec-prompt.md").write_text("Different target.")
        self.assertEqual(review()["valid_first_groups"], "unknown")

    def test_partial_prompt_range_and_disputed_accepted_sources(self):
        rows, catalog, _ = self.paired_review()
        for r in rows + catalog:
            stem = r["report_stem"]
            prompt = "Target: primary.py\nFollow-on targets: " + stem + ".py"
            (self.log.parent / UNIT / (stem + "-prompt.md")).write_text(prompt)
            r["prompt_sha256"] = sha(prompt)
            if "groups" in r:
                r["groups"] = "F1=unknown F2=" + stem
            else:
                r["defect_group"] = "unknown" if r["finding_id"] == "F1" else stem
        table(self.evidence, rows)
        table(self.catalog, catalog)
        result = self.cli("--review-evidence", self.evidence)
        review = result["cases"][0]["review"]
        self.assertEqual((review["attribution"], review["comparable_scope"]), ("partial", False))
        axes = result["questions"]["3"]["groups"][0]["axes"]
        for axis in ("spec", "standards"):
            self.assertEqual(review["exclusive"][axis], 0)
            self.assertEqual(axes[axis]["verified"]["known_numerator"], 1)
            self.assertIn(axis + ":F1", str(axes[axis]["verified"]["unknown_cases"]))

    def test_rates_use_starting_tier_and_distinct_eligible_units(self):
        skill = "a" * 64
        manifest = sha(json.dumps({"canon": skill}, separators=(",", ":")))
        common = dict(tier="L0", model="m", host="other", manifest=manifest, skill="/skills/canon")
        events = [dict(v=1, type="manifest", skills={"canon":skill}, digest=manifest)]
        for i, uid in enumerate((UNIT, PRIOR)):
            events.append(start(uid, **common))
            if not i:
                events.append(start(GATE, "gate", parent=uid, **dict(common, tier="L1")))
            events.append(end(uid, manifest=manifest))
        person = reviewer("cross-family", "/root/reviewer")
        for i in range(22):
            uid = f"20260101T010000Z-{i:06x}"
            claim = dict(by=["cross-family:F1"], severity="major", disposition="accepted", confirmed="resolved")
            events.extend([start(uid, "gate", conversation=f"session-{i}", **common),
                           review_end(uid, "gate", [person], [claim] if not i else [], manifest=manifest)])
            self.archive_report(uid, "cross-family", "### F1 [major]" if not i else "No findings.", "/root/reviewer")
        write_lines(self.log, events)
        q = self.cli()["questions"]
        rate = q["5"]["groups"][0]["targets"]["L1"]
        self.assertEqual((rate["numerator"], rate["denominator"]), (1, 2))
        self.assertEqual(q["2"]["groups"][0]["new_blockers"]["sample"], "few units")
        group = q["1"]["groups"][0]
        self.assertEqual(len(group["reviewer_cost"]["sessions"]), 22)

    def test_prompt_range_covers_each_bulleted_target_and_follow_on(self):
        rows, catalog, _ = self.paired_review()
        for heading, entry in (("Target: review the files below", "- {}"), ("**Targets:**", "- {}"),
                               ("Targets: nested list", "- {}"), ("Target: review the files below", "-\t{}"),
                               ("Target: review the files below", "```text\n{}\n```"),
                               ("Target: common.py\n## Paths", "- {}"), ("Target: common.py\n__Paths:__", "- {}")):
            for source in rows + catalog:
                stem = source["report_stem"]
                prompt = heading + "\n\n" + entry.format(stem + ".py")
                (self.log.parent / UNIT / (stem + "-prompt.md")).write_text(prompt)
                source["prompt_sha256"] = sha(prompt)
            table(self.evidence, rows)
            table(self.catalog, catalog)
            result = self.cli("--review-evidence", self.evidence)["cases"][0]["review"]
            self.assertIs(result["comparable_scope"], False, heading)

    def test_same_agent_path_in_handoff_and_delivery_keeps_both_parent_sessions(self):
        first, second = reviewer("cross-family", "/root/reviewer"), reviewer("cross-family", "/root/reviewer", key="cross-family-2")
        self.archive_report(UNIT, "cross-family", "No findings.", "/root/reviewer")
        self.archive_report(GATE, "cross-family-2", "No findings.", "/root/reviewer")
        write_lines(self.log, [start(UNIT, "gate", conversation=CONV), review_end(UNIT, "gate", [first], [], outcome="handoff"),
                               start(GATE, "gate", conversation="different-parent", continues=UNIT),
                               review_end(GATE, "gate", [first, second], [])])
        group = self.cli()["questions"]["1"]["groups"][0]
        self.assertEqual(group["reviewer_cost"]["distinct_known_sessions"], 2)
        self.assertEqual(len(group["cross_family_cost"]["sessions"]), 2)
        for suffix in (".md", "-id.txt", "-prompt.md"):
            shutil.copyfile(self.log.parent / UNIT / ("cross-family" + suffix), self.log.parent / GATE / ("cross-family" + suffix))
        group = self.cli()["questions"]["1"]["groups"][0]
        self.assertEqual(group["reviewer_cost"]["distinct_known_sessions"], 2)
        self.assertEqual(len(group["cross_family_cost"]["sessions"]), 2)
        from test_trace_report import TraceReport
        fixtures = TraceReport()
        fixtures.project, fixtures.codex = self.project, self.codex
        ids = ["10000000-0000-4000-8000-000000000001", "10000000-0000-4000-8000-000000000002"]
        for sid, parent in zip(ids, [CONV, "different-parent"]):
            fixtures.rollout(sid, [], parent=parent, key="reviewer")
        group = self.cli()["questions"]["1"]["groups"][0]
        self.assertEqual({s["session"] for s in group["reviewer_cost"]["sessions"]}, set(ids))

    def test_replay_with_a_standalone_disputed_decision_preserves_recorded_credit(self):
        rows, _, _ = self.paired_review()
        self.catalog.rename(self.catalog.with_suffix(".disabled"))
        rows[0]["disposition"] = "declined"
        table(self.evidence, rows)
        score = self.cli("--review-evidence", self.evidence)["questions"]["9"]["units"][0]["score"]
        assigned = {ref: f["disposition"] for f in score["dispositions"] for ref in f["by"]}
        self.assertNotEqual(assigned.get("spec:F1"), "declined")
        self.assertIn("spec:F1", str(score["unverified_sources"]))

    def test_confirmation_only_blockers_and_documented_partial_decisions_stay_out_of_first_round_credit(self):
        rows, catalog, event = self.paired_review()
        archive = self.log.parent / UNIT
        note = "PRIVATE F1 was partly accepted and partly declined"
        (archive / "merge-notes.md").write_text(note)
        catalog[0].update(decisions="F1=unknown", decision_locator="merge-notes.md:L1", decision_sha256=sha(note))
        rows[0]["disposition"] = "unknown"
        spec = catalog[0]
        text = "- **F3.** PRIVATE new blocker."
        (archive / "spec-confirm.md").write_text(text)
        confirmation = dict(spec, report_stem="spec-confirm", phase="confirmation", report_sha256=sha(text),
                            groups="F3=new-blocker", decisions="", decision_locator="", decision_sha256="", scope_lines="", prompt_sha256="")
        catalog.append(confirmation)
        rows.append(dict(rows[0], raw_row="5", report_stem="spec-confirm", finding_id="F3", defect_group="new-blocker",
                         disposition="accepted", phase="confirmation", source_locator="spec-confirm.md:L1", report_sha256=sha(text),
                         scope_lines="", prompt_sha256=""))
        event["dispositions"]["findings"].append(dict(axis="spec", by=["spec:F3"], disposition="accepted", severity="blocker"))
        event["dispositions"]["findings"][0]["confirmed"] = "resolved"
        event["dispositions"]["new_blockers"] = 1
        write_lines(self.log, [start(kind="code-review"), event])
        for r in rows:
            r["end_sha256"] = sha(json.dumps(event))
        table(self.evidence, rows)
        table(self.catalog, catalog)
        def result():
            return self.cli("--review-evidence", self.evidence)
        output = result()
        review = output["cases"][0]["review"]
        self.assertEqual((review["raw_rows"], review["first_findings"], review["confirmation_only"], review["valid_first_groups"]),
                         (5, 4, 1, 1))
        first = next(r for r in review["source_findings"] if r["source"] == "spec:F1")
        self.assertEqual((first["raw_disposition"], first["disposition"]), ("accepted", "unknown"))
        self.assertIn("merge-notes.md#L1", first["decision_location"])
        self.assertEqual(review.get("raw_dispositions"), {"accepted": 5})
        self.assertEqual({g["group"] for g in review["groups"]}, {"merge-amendment", "template-comment"})
        score = result()["questions"]["9"]["units"][0]["score"]
        self.assertEqual(len(score["confirmation_only"]), 1)
        confirmation = score["confirmation_only"][0]["source"]
        self.assertNotIn(confirmation, [key for row in score["dispositions"] for key in row["by"]])
        write_lines(self.log, [start(kind="code-review"), event, dict(v=1, type="blocker", id=UNIT, kind="code-review",
                                                                     reviewer="spec", report="spec-confirm",
                                                                     label="F3", snapshot=None)])
        for registered in (result(), self.cli()):
            registered_score = registered["questions"]["9"]["units"][0]["score"]
            later, = registered_score["confirmation_only"]
            self.assertEqual((later["source"], later["raw_row"]), ("blocker:spec-confirm:F3", 5))
            self.assertNotIn("spec:F3", str(registered_score["unverified_sources"]))
        self.assertEqual(result()["questions"]["9"]["units"][0]["score"]["dispositions"], score["dispositions"])
        (archive / "merge-notes.md").write_text("PRIVATE different decision")
        self.assertEqual(result()["cases"][0]["review"]["valid_first_groups"], "unknown")

    def test_missing_adjudication_reports_raw_axis_rate_and_unknown_joint_credit(self):
        self.paired_review()
        output = self.cli()
        group, = output["questions"]["3"]["groups"]
        for axis in ("spec", "standards"):
            row = group["axes"][axis]
            self.assertEqual(row["recorded"]["numerator"], 2)
            self.assertEqual(row["joint"]["numerator"], "unknown")
            self.assertEqual(row["joint"]["denominator"], 1)
        # A surviving confirmation report is evidence of a round even when its finding and blocker counts are zero.
        (self.log.parent / UNIT / "spec-confirm.md").write_text("No new blockers.")
        q2, = self.cli()["questions"]["2"]["groups"]
        self.assertEqual((q2["new_blockers"]["numerator"], q2["new_blockers"]["denominator"]), (0, 1))

    def test_raw_human_and_verified_axis_counts_remain_distinct_in_rates(self):
        self.paired_review()
        self.catalog.rename(self.catalog.with_suffix(".standalone"))
        group, = self.cli("--review-evidence", self.evidence)["questions"]["3"]["groups"]
        spec = group["axes"]["spec"]
        self.assertIn("adjudicated", spec.keys())
        self.assertEqual(spec["adjudicated"]["numerator"], 2)
        self.assertEqual(spec["unverified"]["numerator"], 2)
        self.assertEqual(spec["verified"]["numerator"], "unknown")
        self.assertEqual(spec["verified"]["known_numerator"], 0)

    def test_standalone_table_retains_human_groups_and_only_corroborates_recorded_membership(self):
        rows, _, event = self.paired_review()
        self.catalog.rename(self.catalog.with_suffix(".absent"))
        review = self.cli("--review-evidence", self.evidence)["cases"][0]["review"]
        self.assertEqual(review.get("adjudicated_valid_groups"), 2)
        self.assertEqual(review["raw_rows"], 4)
        self.assertEqual({g["attribution"] for g in review["groups"]}, {"unverified"})
        self.assertEqual(review["joint"], {"spec": 0, "standards": 0})
        # A raw merged row supplies a second record of this group's exact membership.
        findings = event["dispositions"]["findings"]
        findings[0]["by"].append("standards:F1")
        findings.pop(2)
        rows[2]["raw_row"], rows[3]["raw_row"] = "1", "3"
        for row in rows:
            row["end_sha256"] = sha(json.dumps(event))
        write_lines(self.log, [start(kind="code-review"), event])
        table(self.evidence, rows)
        review = self.cli("--review-evidence", self.evidence)["cases"][0]["review"]
        self.assertEqual(review["joint"], {"spec": 1, "standards": 1})
        self.assertEqual(review["attribution"], "partial")
        self.assertIn("source_findings", review)

    def test_two_recovered_dispatches_and_a_partly_accepted_finding_keep_their_own_evidence(self):
        rows, catalog, event = self.paired_review()
        write_lines(self.log, [start(kind="code-review", tier="L0", conversation=CONV, host="cursor"), event])
        topic = self.cursor / "projects/example/agent-transcripts" / CONV
        parent, receipts, dispatches = [], [], []
        for n, decision in enumerate(("accepted", "unknown"), 2):
            stem, key, model = f"cross-family-author{n}", f"cross-family-{n}", f"model-{n}"
            sid = f"10000000-0000-4000-8000-00000000000{n}"
            body = f"### F1 [major] PRIVATE source {n}"
            prompt = "Targets: alpha.py and beta.py"
            fixed, terminal = "Fixed findings: F1 (section 1).", "- **F1**: resolved. PRIVATE"
            self.archive_report(UNIT, stem, body, sid, prompt)
            (self.log.parent / UNIT / (stem + "-confirm-prompt.md")).write_text(fixed)
            (self.log.parent / UNIT / (stem + "-confirm.md")).write_text(terminal)
            child = []
            for action, text, role in [("dispatch", prompt, "user"), ("first", body, "assistant"),
                                       ("fixed", fixed, "user"), ("terminal", terminal, "assistant"),
                                       ("decision", f"PRIVATE parent decision {n}", "assistant"),
                                       ("final", "PRIVATE terminal decision", "assistant")]:
                stream = parent if action in ("decision", "final") else child
                raw = json.dumps(dict(role=role, message=dict(content=[dict(type="text", text=text)])))
                stream.append(raw)
                receipts.append(dict(project="Example", unit=UNIT, report_stem=stem, evidence=action, conversation=CONV,
                                     session=CONV if stream is parent else sid, line=str(len(stream)), sha256=sha(raw)))
            write_lines(topic / "subagents" / (sid + ".jsonl"), child)
            ref = dict(project="Example", unit=UNIT, report_stem=stem, reviewer_key=key, phase="first",
                       report_sha256=sha(body), prompt_sha256=sha(prompt), scope_lines="1-1")
            decision_record = receipts[-2]
            catalog.append(dict(ref, role="cross-family", model=model, reviewer_id=sid, groups=f"F1=extra{n}",
                                decisions="F1="+decision, decision_locator="parent:L"+decision_record["line"],
                                decision_sha256=decision_record["sha256"]))
            rows.append(dict(ref, raw_row="", finding_id="F1", defect_group=f"extra{n}", disposition=decision,
                             raw_disposition="", end_sha256=rows[0]["end_sha256"], source_locator=stem+".md:L1"))
            db_key = "bubbleId:" + CONV + ":fixture-" + str(n)
            data = json.dumps(dict(toolFormerData=dict(name="task_v2", status="completed",
                              params=json.dumps(dict(model=model, prompt=prompt)), result=json.dumps(dict(agentId=sid)))))
            dispatches.append((db_key, data))
            receipts.append(dict(project="Example", unit=UNIT, report_stem=stem, evidence="model-dispatch",
                                 conversation=CONV, session=sid, line=db_key, sha256=sha(data)))
        write_lines(topic / (CONV + ".jsonl"), parent)
        table(self.evidence, rows)
        table(self.catalog, catalog)
        table(self.root / "review-host.tsv", receipts)
        database = self.root / "state.vscdb"
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE cursorDiskKV(key TEXT PRIMARY KEY, value BLOB)")
            db.executemany("INSERT INTO cursorDiskKV VALUES (?, ?)", dispatches)
        def result():
            return self.cli("--review-evidence", self.evidence, "--cursor-state-db", database)
        output = result()
        review = output["cases"][0]["review"]
        self.assertEqual(review.get("attribution"), "partial")
        self.assertEqual({r["key"] for r in review["reports"]}, {"spec", "standards", "cross-family-2", "cross-family-3"})
        self.assertEqual(review["omitted"], 2)
        self.assertEqual(review["first_dispositions"], {"accepted": 5, "unknown": 1})
        self.assertEqual(review["exclusive"]["cross-family-2"], 1)
        self.assertEqual(review["exclusive"]["cross-family-3"], 0)
        self.assertIn(str(database), str(review["reports"]))
        cross, = output["questions"]["1"]["groups"]
        self.assertEqual((cross["verified"]["numerator"], cross["verified"]["denominator"]), (1, 1))
        with sqlite3.connect(database) as db:
            db.execute("DELETE FROM cursorDiskKV WHERE key=?", (dispatches[-1][0],))
        self.assertEqual(result()["cases"][0]["review"]["valid_first_groups"], "unknown")
        with sqlite3.connect(database) as db:
            db.execute("INSERT INTO cursorDiskKV VALUES (?,?)", dispatches[-1])
        self.catalog.rename(self.catalog.with_suffix(".standalone"))
        invalid = json.loads(dispatches[-1][1])
        tool = invalid["toolFormerData"]
        tool["params"] = json.dumps(dict(json.loads(tool["params"]), model="PRIVATE sentence in recovered model"))
        value = json.dumps(invalid)
        with sqlite3.connect(database) as db:
            db.execute("UPDATE cursorDiskKV SET value=? WHERE key=?", (value, dispatches[-1][0]))
        receipts[-1]["sha256"] = sha(value)
        table(self.root / "review-host.tsv", receipts)
        self.assertEqual(result()["cases"][0]["review"]["valid_first_groups"], "unknown")
        self.catalog.with_suffix(".standalone").rename(self.catalog)
        with sqlite3.connect(database) as db:
            db.execute("DELETE FROM cursorDiskKV WHERE key=?", (dispatches[-1][0],))
        # Standalone receipts can still describe both recovered authors without granting them credit.
        self.catalog.rename(self.catalog.with_suffix(".absent"))
        # The surviving host companion must still be checked against the selected database.
        host_only = result()["cases"][0]["review"]
        self.assertEqual(host_only["valid_first_groups"], "unknown")
        self.assertEqual(host_only.get("adjudicated_valid_groups"), 3)
        (self.root / "review-host.tsv").rename(self.root / "elsewhere.tsv")
        standalone = result()["cases"][0]["review"]
        self.assertEqual(standalone["adjudicated_valid_groups"], 3)
        self.assertEqual(standalone["exclusive"]["cross-family-2"], 0)

    def test_recorded_groups_and_zero_finding_reports_survive_without_an_adjudication(self):
        people = [reviewer("same-model", "original"), reviewer("cross-family", "repeat"),
                  reviewer("cross-family", "repeat", key="cross-family-2")]
        findings = [dict(by=["cross-family:F1"], severity="major", disposition="deferred"),
                    dict(by=["cross-family:F2", "same-model:F1"], severity="blocker", disposition="accepted"),
                    dict(by=["cross-family:F3"], severity="minor", disposition="accepted"),
                    dict(by=["cross-family:F4"], severity="blocker", disposition="declined")]
        self.archive_report(UNIT, "same-model", "### F1 [blocker] PRIVATE", "original")
        self.archive_report(UNIT, "cross-family", "\n".join(
            f"### F{i} [{s}] PRIVATE" for i, s in enumerate(["major", "blocker", "minor", "blocker"], 1)), "repeat")
        self.archive_report(GATE, "cross-family-2", "No findings.", "repeat")
        write_lines(self.log, [start(UNIT, "gate"), review_end(UNIT, "gate", people[:2], findings, outcome="handoff"),
                               start(GATE, "gate", continues=UNIT), review_end(GATE, "gate", people, findings),
                               start(PRIOR, "gate"), review_end(PRIOR, "gate", [reviewer("same-model")], [])])
        output = self.cli()
        self.assertIn("1", output["questions"].keys())
        eligible = [g for g in output["questions"]["1"]["groups"] if g["recorded"]["denominator"]]
        self.assertEqual(len(eligible), 1)
        group, = eligible
        self.assertEqual((group["recorded"]["numerator"], group["recorded"]["denominator"]), (1, 1))
        self.assertEqual(group["verified"]["numerator"], "unknown")
        review = output["cases"][1]["review"]
        self.assertEqual(review["attribution"], "recorded")
        self.assertEqual([r["by"] for r in review["raw_findings"]], [f["by"] for f in findings])
        self.assertEqual({r["key"] for r in review["reports"]}, {"same-model", "cross-family", "cross-family-2"})
        self.assertIn(str(self.log.parent / UNIT / "cross-family.md"), str(review["reports"]))
        self.assertEqual({r["session"] for r in review["session_costs"]}, {"original", "repeat"})
        repeated = next(r for r in review["session_costs"] if r["session"] == "repeat")
        self.assertEqual(repeated["keys"], ["cross-family", "cross-family-2"])
        self.assertEqual(repeated["tokens"], "unknown")
        self.assertEqual(next(r for r in review["reports"] if r["key"] == "cross-family-2")["first_findings"], 0)

    def test_confirmation_preserves_the_first_round_and_the_order_and_uncertainty_of_later_checks(self):
        people = [reviewer("same-model"), reviewer("cross-family")]
        group = dict(by=["same-model:F1", "cross-family:F2"], severity="major", disposition="accepted",
                     confirmed="not-resolved", confirmations=[
                         dict(reviewer="same-model", result="resolved", snapshot=None),
                         dict(reviewer="cross-family", result="not-resolved", snapshot="c" * 40)])
        second = dict(by=["same-model:F3"], severity="minor", disposition="deferred", confirmed="resolved")
        check = dict(v=1, type="recheck", id=GATE, kind="gate", finding="cross-family:F2",
                     reviewer="cross-family", model="model-a", snapshot="b" * 40, result="resolved")
        history = [start(UNIT, "gate"), review_end(UNIT, "gate", people, [group], outcome="handoff"),
                   start(GATE, "gate", continues=UNIT), review_end(GATE, "gate", people, [group, second], blockers=2),
                   dict(check, order=2, report="cross-family-recheck2"),
                   dict(check, order=1, report="cross-family-recheck1", result="not-resolved"),
                   start(PRIOR, "gate"), review_end(PRIOR, "gate", people, [second], outcome="handoff")]
        write_lines(self.log, history)
        output = self.cli()
        self.assertIn("2", output["questions"].keys())
        summaries = output["questions"]["2"]["groups"]
        self.assertEqual(len(summaries), 1)
        stats = summaries[0]
        self.assertEqual((stats["initial_not_resolved"]["numerator"], stats["initial_not_resolved"]["denominator"]), (1, 2))
        self.assertEqual((stats["new_blockers"]["numerator"], stats["new_blockers"]["denominator"]), (2, 1))
        cases = {c["unit"]: c["review"] for c in output["cases"]}
        self.assertEqual((cases[UNIT]["coverage"], cases[PRIOR]["coverage"]), ("partial-handoff", "partial-handoff"))
        self.assertEqual(cases[UNIT]["raw_rows"], 1)
        initial, legacy = cases[GATE]["confirmations"]
        self.assertEqual((initial["initial"], initial["latest"]), ("not-resolved", "resolved"))
        self.assertEqual(initial["individual"], group["confirmations"])
        self.assertEqual(legacy["individual"], "unknown")
        self.assertEqual([c["order"] for c in initial["ordered"]], [1, 2])
        self.assertIn("#L5", initial["ordered"][-1]["location"])
        history += [dict(check, order=None, report="later"), dict(check, order=1, report="other", result="resolved")]
        write_lines(self.log, history)
        history.append(dict(check, model="other", order=3, report="incompatible"))
        write_lines(self.log, history)
        report = self.cli()
        self.assertIn({"reason": "recheck identity mismatch", "location": str(self.log) + "#L11"},
                      report["population"]["skipped"])
        updated = report["cases"][1]["review"]["confirmations"][0]
        self.assertEqual(updated["latest"], "unknown")
        self.assertEqual(len(updated["unordered"]), 1)
        self.assertEqual({r["report"] for r in updated["conflicting"]}, {"other", "cross-family-recheck1"})
        self.assertEqual(updated["highest_verified"]["order"], 2)

    def test_registered_blockers_keep_their_origins_and_rechecks_out_of_first_round_scores(self):
        source = "cross-family:F12"
        introduced = "blocker:cross-family-confirm:F12"
        first = dict(by=[source], severity="major", disposition="accepted", confirmed="resolved",
                     confirmations=[dict(reviewer="cross-family", result="resolved", snapshot=None)])
        self.archive_report(UNIT, "cross-family", "### F12 [major] PRIVATE original claim\n", "reader")
        history = [start(kind="gate"), review_end(UNIT, "gate", [reviewer("cross-family", "reader")], [first], blockers=2)]
        write_lines(self.log, history)
        baseline = self.cli()
        judgment, = baseline["questions"]["9"]["units"][0]["score"]["dispositions"]
        counts = baseline["questions"]["1"]["groups"][0]["recorded"]
        self.archive_report(UNIT, "cross-family-confirm", "- **F12.** PRIVATE new blocker.\n")
        self.archive_report(UNIT, "targeted", "### F12 [blocker] PRIVATE later claim\n")
        registration = dict(v=1, type="blocker", id=UNIT, kind="gate", reviewer="cross-family",
                            report="cross-family-confirm", label="F12", snapshot=None)
        check = dict(v=1, type="recheck", id=UNIT, kind="gate", reviewer="cross-family", model="model-a",
                     snapshot="a" * 40, result="resolved", order=1)
        write_lines(self.log, [*history, registration, dict(check, finding=source, report="original-again", result="not-resolved"),
                               dict(check, finding=introduced, report="targeted"), dict(registration, report="targeted",
                                    label="N1", snapshot="a" * 40, **{"from": introduced}),
                               dict(check, finding=introduced, report="undated", order=None)])
        output = self.cli()
        self.assertEqual(output["population"]["orphans"], [])
        self.assertEqual(output["population"]["skipped"], [])
        review = output["cases"][0]["review"]
        self.assertEqual(review["unidentified_blockers"], 1)
        self.assertEqual([r["stem"] for r in review["reports"]], ["cross-family"])
        original, = review["confirmations"]
        self.assertEqual((original["initial"], original["latest"]), ("resolved", "not-resolved"))
        one, two = review["introduced_blockers"]
        self.assertEqual((one["finding"], one["origin"], one["archive"], one["snapshot"], one["latest"]),
                         (introduced, "confirmation", "present", None, "unknown"))
        self.assertEqual([e["report"] for e in one["ordered"]], ["targeted"])
        self.assertEqual([e["report"] for e in one["unordered"]], ["undated"])
        self.assertEqual((two["finding"], two["origin"], two["archive"]), ("blocker:targeted:N1", introduced, "present"))
        score = output["questions"]["9"]["units"][0]["score"]
        self.assertEqual(score["dispositions"], [judgment])
        self.assertEqual(score["unverified_sources"], [])
        self.assertEqual({e["source"] for e in score["confirmation_only"]}, {introduced, "blocker:targeted:N1"})
        self.assertEqual(output["questions"]["1"]["groups"][0]["recorded"], counts)

    def test_adjudicated_confirmation_label_cannot_claim_the_first_round_evidence_row(self):
        rows, catalog, event = self.paired_review()
        event["dispositions"]["findings"][0].update(confirmed="resolved", confirmations=[
            dict(reviewer="spec", snapshot=None, result="resolved")])
        event["dispositions"]["new_blockers"] = 2
        confirmation = "- **New blocker — F1.** PRIVATE confirmation issue.\n- **B2.** PRIVATE second issue."
        (self.log.parent / UNIT / "spec-confirm.md").write_text(confirmation)
        catalog.append(dict(catalog[0], report_stem="spec-confirm", phase="confirmation", scope_lines="",
                            prompt_sha256="", report_sha256=sha(confirmation), decisions="", groups="F1=new-issue B2=other-issue"))
        rows.append(dict(rows[0], raw_row="", raw_disposition="", report_stem="spec-confirm", phase="confirmation",
                         scope_lines="", prompt_sha256="", report_sha256=sha(confirmation), disposition="unknown",
                         defect_group="new-issue", source_locator="spec-confirm.md:L1"))
        rows.append(dict(rows[-1], finding_id="B2", defect_group="other-issue", source_locator="spec-confirm.md:L2"))
        for row in rows:
            row["end_sha256"] = sha(json.dumps(event))
        table(self.evidence, rows)
        table(self.catalog, catalog)
        registration = dict(v=1, type="blocker", id=UNIT, kind="code-review", reviewer="spec", report="spec-confirm", snapshot=None)
        write_lines(self.log, [start(kind="code-review"), event, dict(registration, label="F1"), dict(registration, label="B2")])
        for mode in ("catalog", "standalone"):
            with self.subTest(mode=mode):
                if mode == "standalone":
                    self.catalog.rename(self.catalog.with_suffix(".unused"))
                output = self.cli("--review-evidence", self.evidence)
                review = output["cases"][0]["review"]
                self.assertIsNone(review.get("evidence_issue"))
                original, = [c for c in review["source_findings"] if c["source"] == "spec:F1"]
                later = [c for c in review["source_findings"] if c["phase"] == "confirmation"]
                self.assertEqual((original["phase"], original["raw_row"], original["disposition"]), ("first", 1, "accepted"))
                self.assertEqual([(c["source"], c["raw_row"]) for c in later],
                                 [("blocker:spec-confirm:F1", None), ("blocker:spec-confirm:B2", None)])
                score = output["questions"]["9"]["units"][0]["score"]
                self.assertIn("spec:F1", [ref for row in score["dispositions"] for ref in row["by"]])
                self.assertNotIn("spec:F1", [c["source"] for c in score["confirmation_only"]])

    def test_nested_gates_and_direct_escalations_keep_each_target_once(self):
        nested = "20260101T000026Z-aaaaaa"
        repeat = "20260101T000027Z-bbbbbb"
        design = "20260101T000028Z-cccccc"
        higher = "20260101T000029Z-dddddd"
        write_lines(self.log, [
            start(tier="L0"), start(GATE, "plan", parent=UNIT),
            start(nested, "gate", parent=GATE, tier="L1"),
            start(repeat, "follow-up", parent=GATE, tier="L1"),
            end(outcome="escalated", to="L2"), start(PRIOR, tier="L1"), end(PRIOR, outcome="escalated", to="plan"),
            start(design, "design", tier="L1"), start(higher, "gate", parent=design, tier="L2"),
        ])
        output = self.cli()
        self.assertIn("5", output["questions"])
        cases = {c["unit"]: c for c in output["cases"]}
        self.assertEqual(cases[UNIT]["effective_tier"], "L1")
        self.assertEqual(cases[design]["effective_tier"], "L2")
        groups = output["questions"]["5"]["groups"]
        l0 = next(g for g in groups if g["starting_tier"] == "L0")
        self.assertEqual({t: r["numerator"] for t, r in l0["targets"].items()}, {"L1": 1, "L2": 1, "plan": 0})
        self.assertEqual(l0["targets"]["L1"]["denominator"], 1)
        self.assertIn(str(self.log) + "#L3", str(l0["targets"]["L1"]["cases"]))
        self.assertEqual(l0["targets"]["L2"]["sample"], "few units")
        self.assertEqual(next(g for g in groups if g["starting_tier"] == "L1" and g["kind"] == "implement")
                         ["targets"]["plan"]["numerator"], 1)
        self.assertEqual(next(g for g in groups if g["kind"] == "design")["targets"]["L2"]["numerator"], 1)
