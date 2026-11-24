"""Public regression cases from the D012 implementation review."""
import json

from test_replay_prepare import PLAN, PLAN_BODY, digest
from test_replay_score import ScoreFixture
from test_trace_report import CONV, PRIOR, SECOND, UNIT, write_lines
from test_trace_reviews import reviewer, table
import test_trace_report


class ReviewFindings(ScoreFixture):
    def test_completed_and_truncated_empty_historical_reports(self):
        self.gate()
        forms = [("Questions: None.\n\nVerdict: approve\n", True),
                 ("No findings for D001@r3.\n\n## Questions\nNone.\n\n**Verdict:** approve\n", True),
                 ("No findings.", True),  # Independently corroborated by the archived closing dispositions.
                 ("There were no findings in the preliminary walk. Still checking.\n", False),
                 ("No findings.\n```text\nVerdict: approve\n", False),
                 ("Questions: None.\n", False)]
        for i, (body, verified) in enumerate(forms):
            with self.subTest(body=body):
                (self.store / UNIT / "same-model.md").write_text(body)
                history = self.prepare(out=self.root / f"historical-{i}")["history"]
                self.assertEqual(history["raw_count"], 0)
                self.assertEqual(not history["unknown"], verified)

    def test_standard_empty_replay_scores_zero_of_one_and_standalone_shorthand_stays_unknown(self):
        self.prepare_known_review()
        canonical = "Questions: None.\n\nVerdict: approve\n"
        self.config["settings"]["actions"] = [dict(reports={"spec": canonical, "standards": canonical}),
                                             dict(reports={"spec": "No findings.", "standards": canonical})]
        self.write_config()
        self.replay()
        first, second = self.journal()["attempts"][:2]
        results = {a["id"]: a for a in self.score(self.packet("judgments-template.json"))["attempts"]}
        self.assertEqual(results[first["id"]]["metrics"]["review.recall"], dict(numerator=0, denominator=1, rate=0))
        self.assertIsNone(results[second["id"]]["metrics"]["review.recall"]["rate"])

    def test_historical_and_replay_finding_share_the_fence_aware_section_boundary(self):
        body = ("### F1 [major] ABI return\nProblem: Wrong return width.\n"
                "Assessment of the existing ABI is incomplete.\nEvidence: The example prints\n"
                "```text\nVerdict: approve\n### F2 [minor] Example, not a finding.\n```\n"
                "Suggestion: Change the width.\n")
        full = body + "\n## Questions\nNone.\n\nVerdict: revise\n"
        self.gate()
        role = "same-model"
        (self.store / UNIT / (role + ".md")).write_text(full)
        self.events[-1]["dispositions"]["findings"] = [dict(by=[role + ":F1"], severity="major", disposition="accepted")]
        write_lines(self.log, self.events)
        evidence = self.root / "history.tsv"
        table(evidence, [dict(project=str(self.project), unit=UNIT, raw_row="1", report_stem=role,
                              finding_id="F1", defect_group="width", disposition="accepted",
                              end_sha256=digest(json.dumps(self.events[-1]).encode()), report_sha256=digest(full.encode()),
                              source_locator=role + ".md:L1")])
        receipt = self.prepare("--review-evidence", evidence)
        historical, = receipt["history"]["groups"]
        self.assertEqual(historical["evidence"][0]["text"], body)
        self.config["settings"]["actions"] = [dict(reports={role: full})]
        self.write_config()
        self.replay()
        observed = self.journal()["attempts"][0]["roles"][role]
        self.assertTrue(observed["report_valid"])
        claim, = observed["claims"]
        self.assertEqual((claim["first_line"], claim["last_line"], claim["text"]), (1, len(body.splitlines()), body))

    def test_worker_model_context_after_start_belongs_only_to_that_dispatch_interval(self):
        self.worker_slice()
        host = test_trace_report.TraceReport()
        host.project, host.codex = self.project, self.codex
        rows = host.worker_turn(10, 17, 1, 2)
        settings = host.native(12, "turn_context", model="worker-model", effort="high")
        later = [host.native(22, "turn_context", model="replacement", effort="low"), *host.worker_turn(24, 32, 2, 3)]
        for label, after_start in (("known", [settings]), ("conflict", [settings, host.native(
                13, "turn_context", model="other-worker", effort="high")])):
            host.rollout(SECOND, rows[:2] + after_start + rows[2:] + later, parent=CONV, key="p001_s1")
            receipt = self.prepare(out=self.root / label)
            if label == "known":
                self.assertEqual(receipt["roles"]["worker"], dict(model="worker-model", effort="high"))
                self.assertEqual(receipt["incompatibilities"], [])
            else:
                self.assertIsNone(receipt["roles"]["worker"]["model"])
                self.assertTrue(receipt["incompatibilities"])

    def test_command_reviewers_recover_their_codex_settings_under_other_parent_hosts(self):
        self.gate(people=[reviewer("cross-family", SECOND)])
        host = test_trace_report.TraceReport()
        host.project, host.codex = self.project, self.codex
        for i, (parent_host, model) in enumerate((("cursor", "model-a"), ("claude-code", "model-b"))):
            self.events[-2].update(host=parent_host, conversation=CONV)
            write_lines(self.log, self.events)
            host.rollout(SECOND, [host.native(8, "event_msg", type="task_started"),
                                  host.native(9, "turn_context", model=model, effort="high"),
                                  host.native(12, "event_msg", type="task_complete", last_agent_message="No findings."),
                                  host.native(20, "event_msg", type="task_started"),
                                  host.native(21, "turn_context", model="later", effort="low"),
                                  host.native(24, "event_msg", type="task_complete", last_agent_message="fixed")])
            receipt = self.prepare(out=self.root / f"command-{i}")
            self.assertEqual(receipt["roles"]["cross-family"], dict(model=model, effort="high"))
            self.assertEqual(bool(receipt["incompatibilities"]), model != "model-a")

    def test_cursor_worker_inherit_uses_only_the_concrete_historical_parent_model(self):
        self.worker_slice()
        for index in (1, 2):
            self.events[index].update(host="cursor", conversation=CONV)
        transcript = self.cursor / "projects/example/agent-transcripts" / CONV / (CONV + ".jsonl")
        child = transcript.parent / "subagents" / (SECOND + ".jsonl")
        brief = "Implement P001 S1"
        def record(role, part):
            return {"role": role, "message": {"content": [part]}}
        def shell(cmd):
            return record("assistant", dict(type="tool_use", name="Shell", input=dict(command=cmd)))
        write_lines(transcript, [shell("python3 .agents/skills/canon/scripts/canon.py trace start slice P001 --slice S1 --parent " + PRIOR),
                    record("assistant", dict(type="tool_use", name="Task", input=dict(prompt=brief, model="inherit", run_in_background=False))),
                    shell("git commit -q -m fixture")])
        write_lines(child, [record("user", dict(type="text", text=brief)),
                            record("assistant", dict(type="text", text="Status: done")),
                            dict(type="turn_ended", status="success")])
        for i, (parent, model) in enumerate((("model-a", "model-a"), (None, None), ("inherit", None))):
            self.events[2]["model"] = parent
            write_lines(self.log, self.events)
            receipt = self.prepare(out=self.root / f"inherit-{i}")
            self.assertEqual(receipt["historical_brief"]["text"], brief)
            self.assertEqual(receipt["roles"]["worker"]["model"], model)

    def test_preparation_pins_workflow_entry_from_the_review_or_implement_parent(self):
        self.gate()
        self.events[-2]["skill"] = ".agents/skills/canon-blind-review"
        write_lines(self.log, self.events)
        self.assertEqual(self.prepare()["workflow_skill"], "canon-blind-review")
        self.events = self.events[:1]
        self.slice()
        self.events[1]["skill"] = "/installed/skills/canon-implement"
        write_lines(self.log, self.events)
        self.assertEqual(self.prepare(out=self.root / "slice")["workflow_skill"], "canon-implement")
        self.events[1]["skill"] = "/unexpected/folder"
        write_lines(self.log, self.events)
        self.assertIsNone(self.prepare(out=self.root / "unknown")["workflow_skill"])

    def test_duplicate_and_nonfinite_fields_in_criteria_or_case_receipt_are_rejected(self):
        target = self.slice()
        mapping = self.mapping(target, [("check", ["test"])])
        criteria = mapping.read_bytes()
        for field in (b'"criteria": [],', b'"extra": NaN,', b'"extra": 1e999,'):
            with self.subTest(criteria_field=field):
                mapping.write_bytes(b"{" + field + criteria[1:])
                self.prepare("--criteria", mapping, out=self.root / "bad-criteria", error="invalid criteria")
        self.prepare()
        path = self.out / "private/receipt.json"
        original = path.read_bytes()
        for field in (b'"schema": 2,', b'"extra": Infinity,', b'"extra": 1e999,'):
            with self.subTest(receipt_field=field):
                data = b"{" + field + original[1:]
                path.write_bytes(data)
                (path.parent / "receipt.sha256").write_text(digest(data))
                self.replay(error="invalid private receipt")

    def test_criteria_cannot_select_a_nonexistent_line_after_the_last_slice(self):
        body = PLAN_BODY.split("### S2:")[0].rstrip() + "\n"
        target = self.slice({PLAN: body})
        receipt = self.prepare()
        last = len(body.splitlines())
        self.assertEqual(receipt["slice_plan"]["last_line"], last)
        mapping = self.mapping(target, [("check", ["test"])])
        spec = json.loads(mapping.read_bytes())
        spec["criteria"][0]["last_line"] = last + 1
        mapping.write_text(json.dumps(spec))
        self.prepare("--criteria", mapping, out=self.root / "overrun", error="range")

    def test_plan_ranges_and_suffixed_revisions_require_evidence_for_the_selected_delivery(self):
        path = PLAN.replace("P001", "P001A")
        text = PLAN_BODY.replace("## Log", "### S3: Third\n\nVerify a version.\n\n## Log")
        base = self.pin(self.store, self.tree(self.store, {path: text, "rule": "old"}))
        entries = {path: text, "rule": "new"}
        target = self.pin(self.store, self.tree(self.store, entries), base)
        scope = f"Target: `git diff {base} {target} -- rule`\n"
        self.review("code-review", entries, baseline=base, docs=["P001A@r2"], prompts={"spec": scope})
        cases = [("implement P001A@r2, S1 through S3, for D002@r1", ["S1", "S2", "S3"]),
                 ("Implement the whole plan, including S2.", ["S1", "S2", "S3"]),
                 ("P001A@r2 S1–S3", ["S1", "S2", "S3"]), ("S2-S3", ["S2", "S3"]),
                 ("S3 to S1", None), ("S1 through S8", None), ("P001A@r2, a few slices", None),
                 ("S1 through S3 except S2", None), ("P001A@r1, S1", None), ("P002@r2, S2", None),
                 ("S1 through", None), (None, None)]
        for i, (phrase, expected) in enumerate(cases):
            with self.subTest(phrase=phrase):
                (self.store / UNIT / "spec-prompt.md").write_text(scope + (f"Requested delivery: {phrase}" if phrase else ""))
                receipt = self.prepare(out=self.root / f"delivery-{i}")
                delivery = receipt["delivery"]
                if expected is None:
                    self.assertIsNone(delivery)
                else:
                    self.assertIsInstance(delivery["source"][0], dict)
                    self.assertEqual([s["slice"] for s in delivery["source"]], expected)
                    self.assertIn("Add a renderer.", delivery["text"])
