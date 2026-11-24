"""Score sealed evidence and blinded adjudications through the operator's CLI."""
import json
import copy
import subprocess
import sys

from test_replay_prepare import SCRIPT, digest
from test_replay_slice import SliceFixture
from test_trace_report import GATE, PRIOR, start, write_lines
from test_trace_reviews import review_end, reviewer, sha, table


class ScoreFixture(SliceFixture):
    def packet(self, name="packet.json"):
        return json.loads((self.out / "blind" / name).read_bytes())

    def score(self, judgments=None, error=None):
        args = [sys.executable, SCRIPT, "score", self.out]
        if judgments is not None:
            path = self.root / "judgments.json"
            path.write_text(json.dumps(judgments))
            args += ["--judgments", path]
        run = subprocess.run(args, capture_output=True, text=True, timeout=20)
        if error:
            self.assertNotEqual(run.returncode, 0)
            self.assertIn(error, run.stderr)
            self.assertNotIn("Traceback", run.stderr)
            return
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads((self.out / "result.json").read_bytes())

    def reports(self, *titles):
        return "".join(f"### F{i} [major] {t}\n" for i, t in enumerate(titles, 1)) + "Verdict: revise\n"

    def claim_groups(self, row, decisions):
        """Act as a blinded adjudicator, using only exported text to group the claims."""
        selected = {}
        for group in row["groups"]:
            ref, = group["evidence"]
            text = (self.out / "blind" / ref["path"]).read_text()
            title, = [title for title in decisions if title in text]
            if title in selected:
                selected[title]["claims"].extend(group["claims"])
                selected[title]["evidence"].extend(group["evidence"])
            else:
                group["historical"], group["verdict"], group["scope"] = decisions[title]
                selected[title] = group
        row["groups"] = list(selected.values())


class ScoreReviews(ScoreFixture):
    def test_a_judgment_can_cite_the_original_patch_and_depends_on_its_digest(self):
        self.prepare_known_review()
        self.config["settings"]["actions"] = [dict(reports={"spec": self.reports("ABI mismatch")})]
        self.write_config()
        self.replay()
        packet = self.packet()
        ref = packet["review_input"]
        judgments = self.packet("judgments-template.json")
        for row in judgments["attempts"]:
            self.claim_groups(row, {"ABI mismatch": (packet["history"]["groups"][0]["id"], "valid", "in")})
            for group in row["groups"]:
                group["evidence"].append(ref)
        result = self.score(judgments)
        self.assertEqual(result["judgments"], judgments)
        self.assertEqual(result["attempts"][0]["metrics"]["review.recall"]["rate"], 1)
        (self.out / "blind" / ref["path"]).write_text("different input")
        self.assertIsNone(self.score(judgments)["attempts"][0]["metrics"]["review.recall"]["rate"])

    def test_two_historical_sources_and_a_completed_empty_report_score_zero_of_one(self):
        self.prepare_known_review()
        self.replay()
        judgments = self.packet("judgments-template.json")
        result = self.score(judgments)
        self.assertEqual(len(self.packet()["history"]["groups"][0]["sources"]), 2)
        self.assertEqual(len(result["attempts"]), 6)
        for attempt in result["attempts"]:
            self.assertEqual(attempt["metrics"]["review.recall"], {"numerator": 0, "denominator": 1, "rate": 0})

    def test_worked_review_counts_defects_scope_and_a_paired_difference(self):
        self.prepare_known_review(declined=True)
        reports = dict(spec=self.reports("ABI mismatch", "Wrong offset", "Withdrawn flag", "Future feature"),
                       standards=self.reports("Wrong offset"))
        self.config["settings"]["actions"] = [{}, dict(reports=reports)]
        self.write_config()
        self.replay()
        refs = {g["disposition"]: g["id"] for g in self.packet()["history"]["groups"]}
        judgments = self.packet("judgments-template.json")
        for row in judgments["attempts"]:
            self.claim_groups(row, {"ABI mismatch": (refs["accepted"], "valid", "in"),
                                    "Wrong offset": (None, "valid", "in"),
                                    "Withdrawn flag": (refs["declined"], "false_positive", "in"),
                                    "Future feature": (None, "false_positive", "out")})
        result = self.score(judgments)
        case = next(a for a in result["attempts"] if a["pair"] == 1 and a["arm"] == "candidate")
        m = case["metrics"]
        self.assertEqual(m["review.recall"], dict(numerator=1, denominator=1, rate=1))
        self.assertEqual(m["review.scope"], dict(numerator=1, denominator=4, rate=0.25))
        self.assertEqual([m["review." + name] for name in ("novel_valid", "false_positive", "unknown_verdict",
                                                           "unknown_scope")], [1, 2, 0, 0])
        pair = result["pairs"][0]["metrics"]
        self.assertEqual((pair["review.recall"]["difference"], pair["review.novel_valid"]["difference"]), (1, 1))
        self.assertIsNone(pair["review.scope"]["difference"])

    def test_missing_duplicate_foreign_and_contradictory_judgments_keep_unaffected_observations(self):
        self.prepare_known_review()
        self.config["settings"]["actions"] = [dict(reports={"spec": self.reports("ABI mismatch", "Wrong offset")}),
                                               dict(reports={"spec": "### F1 [major] Truncated"})]
        self.write_config()
        self.replay()
        baseline = self.packet("judgments-template.json")
        historical = self.packet()["history"]["groups"][0]["id"]
        inspected, truncated, empty = [a["id"] for a in self.journal()["attempts"][:3]]
        for row in baseline["attempts"]:
            self.claim_groups(row, {"ABI mismatch": (historical, "valid", "in"), "Wrong offset": (None, "valid", "in"),
                                    "Truncated": (None, "unknown", "unknown")})
        for flaw in ("missing row", "repeated row", "missing claim", "duplicate claim", "foreign claim", "unknown group",
                     "invalid verdict", "historical contradiction", "missing member", "wrong later"):
            with self.subTest(flaw=flaw):
                judgments = copy.deepcopy(baseline)
                row = next(r for r in judgments["attempts"] if r["id"] == inspected)
                group = next(g for g in row["groups"] if g["historical"])
                if flaw == "missing row":
                    judgments["attempts"].remove(row)
                elif flaw == "repeated row":
                    judgments["attempts"].append(row)
                elif flaw == "missing claim":
                    row["groups"].remove(group)
                elif flaw == "duplicate claim":
                    row["groups"].append(dict(group, id="duplicate"))
                elif flaw == "foreign claim":
                    group["claims"].append(next(r["groups"][0]["claims"][0] for r in judgments["attempts"]
                                                if r["id"] == truncated))
                elif flaw == "unknown group":
                    group["historical"] = "absent-reference"
                elif flaw == "invalid verdict":
                    group["verdict"] = "yes"
                elif flaw == "historical contradiction":
                    group["verdict"] = "false_positive"
                elif flaw == "missing member":
                    del group["historical"]
                else:
                    row["later"] = [dict(historical=historical, match="absent", evidence=[])]
                result = self.score(judgments)
                scored = {a["id"]: a for a in result["attempts"]}
                self.assertIsNone(scored[inspected]["metrics"]["review.recall"]["rate"])
                self.assertTrue(scored[inspected]["unknowns"])
                self.assertIsNone(scored[truncated]["metrics"]["review.recall"]["rate"])
                self.assertEqual(scored[empty]["metrics"]["review.recall"], dict(numerator=0, denominator=1, rate=0))
                if flaw in ("duplicate claim", "unknown group", "historical contradiction", "missing claim"):
                    self.assertEqual(scored[inspected]["metrics"]["review.novel_valid"], 1)

    def test_absent_or_contradictory_delivery_preserves_diff_decidable_contracts(self):
        self.config["settings"]["actions"] = [dict(reports={"spec": self.reports("ABI mismatch", "Future feature")})]
        self.write_config()
        for i, delivery in enumerate(({}, dict(spec="Preserve the ABI.", standards="Implement the renderer."))):
            with self.subTest(delivery=delivery):
                self.events = self.events[:1]
                self.out = self.root / f"delivery-{i}"
                self.observations.write_text("")
                self.assertIsNone(self.prepare_known_review(deliveries=delivery)["delivery"])
                self.replay()
                gid = self.packet()["history"]["groups"][0]["id"]
                judgments = self.packet("judgments-template.json")
                for row in judgments["attempts"]:
                    self.claim_groups(row, {"ABI mismatch": (gid, "valid", "in"),
                                            "Future feature": (None, "false_positive", "out")})
                m = self.score(judgments)["attempts"][0]["metrics"]
                self.assertEqual(m["review.recall"], dict(numerator=1, denominator=1, rate=1))
                self.assertEqual(m["review.scope"], dict(numerator=0, denominator=1, rate=0))
                self.assertEqual([m["review." + k] for k in ("false_positive", "unknown_verdict", "unknown_scope")],
                                 [0, 1, 1])

    def test_provisional_history_withholds_novelty_and_the_full_recall_rate(self):
        self.prepare_known_review()
        self.out = self.root / "provisional"
        self.assertTrue(self.prepare()["history"]["unknown"])
        self.config["settings"]["actions"] = [dict(reports={"spec": self.reports("Possible new defect")})]
        self.write_config()
        self.replay()
        judgments = self.packet("judgments-template.json")
        for row in judgments["attempts"]:
            self.claim_groups(row, {"Possible new defect": (None, "valid", "in")})
        result = self.score(judgments)
        first = result["attempts"][0]
        self.assertEqual(first["metrics"]["review.novel_valid"], 0)
        self.assertIsNone(first["metrics"]["review.recall"]["rate"])
        self.assertIn("historical inventory incomplete", first["unknowns"])
        self.assertIsNone(result["pairs"][0]["metrics"]["review.novel_valid"]["difference"])

    def test_score_binds_the_packet_and_validates_each_judged_evidence_reference(self):
        self.prepare_known_review()
        self.config["settings"]["actions"] = [dict(reports={"spec": self.reports("ABI mismatch")})] * 2
        self.write_config()
        self.replay()
        packet = self.packet()
        historical, = packet["history"]["groups"]
        file = self.out / "blind/packet.json"
        judgments = self.packet("judgments-template.json")
        for row in judgments["attempts"]:
            self.claim_groups(row, {"ABI mismatch": (historical["id"], "valid", "in")})
        self.score(error="judgments")
        for malformed in (dict(schema=True), dict(schema=2), dict(attempts={})):
            self.score(judgments | malformed, error="judgments")
        stale = self.score(judgments | dict(packet_sha256="f" * 64))
        self.assertTrue(all(a["metrics"]["review.recall"]["rate"] is None for a in stale["attempts"]))
        self.assertIn("packet", " ".join(stale["judgment_issues"]))
        altered = copy.deepcopy(packet)
        altered["task"]["docs"] = ["fabricated"]
        file.write_text(json.dumps(altered))
        self.score(judgments | dict(packet_sha256=digest(file.read_bytes())), error="packet")
        file.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
        first, second = [a["id"] for a in self.journal()["attempts"][:2]]
        first_row = next(a for a in judgments["attempts"] if a["id"] == first)
        second_row = next(a for a in judgments["attempts"] if a["id"] == second)
        own_ref, = first_row["groups"][0]["evidence"]
        for ref in (second_row["groups"][0]["evidence"][0], dict(own_ref, sha256="0" * 64),
                    dict(own_ref, path="../private/receipt.json"), "invalid", None):
            first_row["groups"][0]["evidence"] = [ref]
            result = self.score(judgments)
            by_id = {r["id"]: r for r in result["attempts"]}
            self.assertIsNone(by_id[first]["metrics"]["review.recall"]["rate"])
            self.assertEqual(by_id[second]["metrics"]["review.recall"]["rate"], 1)
        first_row["groups"][0]["evidence"] = [own_ref]
        exported = self.out / "blind" / own_ref["path"]
        original = exported.read_bytes()
        exported.write_bytes(b"substituted evidence")
        result = self.score(judgments)
        self.assertIsNone(result["attempts"][0]["metrics"]["review.recall"]["rate"])
        self.assertEqual(result["attempts"][1]["metrics"]["review.recall"]["rate"], 1)
        exported.write_bytes(original)
        (self.out / "blind" / historical["evidence"][0]["path"]).unlink()
        result = self.score(judgments)
        self.assertTrue(all(a["metrics"]["review.recall"]["rate"] is None for a in result["attempts"]))

    def test_costs_cohort_and_steering_survive_loss_of_the_original_inputs(self):
        self.different_suite()
        receipt = self.prepare_known_review()
        budget = dict(input=37, cached_input=3, output=11, reasoning_output=None)
        child = dict(input=9, cached_input=14, output=8, reasoning_output=10)
        boundary = dict(reason="confirmation dispatched", wall_seconds=2.0, evidence=None,
                        tokens=dict(parent=dict(input=12, cached_input=7, output=6, reasoning_output=1)))
        self.config["settings"]["actions"] = [
            dict(roles={"parent": {"tokens": budget}, "spec": {"tokens": child}}),
            dict(roles={"parent": {"tokens": dict(budget, input=47, cached_input=-2)}}),
            dict(envelope={"boundary_violation": boundary})]
        self.write_config()
        self.replay()
        judgments = self.packet("judgments-template.json")
        journal = self.journal()
        self.project.rename(self.root / "lost-project")
        self.runner.rename(self.root / "lost-runner")
        self.config_path.rename(self.root / "lost-config")
        self.skills.rename(self.root / "lost-skills")
        result = self.score(judgments)
        output = self.out / "result.json"
        first = output.read_bytes()
        self.score(judgments)
        self.assertEqual(output.read_bytes(), first)
        self.assertEqual(result["identity"], {k: receipt[k] for k in ("project", "store", "unit")})
        self.assertEqual(result["cohort"], dict(project=receipt["project"], kind=receipt["kind"], host=receipt["host"],
                         tier=receipt["task"]["tier"], roles=journal["roles"], runner_sha256=journal["runner_sha256"],
                         config_sha256=journal["config_sha256"], suites={
                             arm: {k: s[k] for k in ("tree", "manifest")} for arm, s in receipt["suites"].items()}))
        self.assertEqual(result["case"], self.packet()["case"])
        self.assertEqual(result["steered"], receipt["steered"])
        for name, path in (("receipt", "private/receipt.json"), ("run", "private/run.json"), ("packet", "blind/packet.json")):
            self.assertEqual(result[name + "_sha256"], digest((self.out / path).read_bytes()))
        self.assertEqual(result["judgments"], judgments)
        self.assertEqual(result["comparable_pairs"], 2)
        self.assertEqual(result["incomplete_pairs"], [2])
        self.assertTrue(result["sparse_pairs"])
        a, b, crossed = result["attempts"][:3]
        met = a["metrics"]
        self.assertEqual(met["cost.tokens.parent.input"], 37)
        self.assertIsNone(met["cost.tokens.parent.reasoning_output"])
        self.assertEqual([met["cost.tokens.spec." + key] for key in child], [None] * 4)
        self.assertEqual(met["cost.tokens.standards.cached_input"], 3)
        self.assertGreaterEqual(met["cost.wall_seconds"], 0)
        self.assertIsNone(b["metrics"]["cost.tokens.parent.cached_input"])
        self.assertEqual(crossed["boundary_violation"]["tokens"], boundary["tokens"])
        self.assertEqual(crossed["boundary_violation"]["wall_seconds"], 2)
        self.assertEqual(crossed["outcome"], "incompatible")
        difference = result["pairs"][0]["metrics"]
        self.assertEqual(difference["cost.tokens.parent.input"]["difference"], 10)
        self.assertIsNone(difference["cost.tokens.spec.input"]["difference"])
        self.assertIsNone(difference["cost.tokens.parent.cached_input"]["difference"])
        for secret in ("blind_key", "operator_inputs", "private-defect", "private/jobs", "historical_brief",
                       "observations.jsonl", "stdout", "stderr"):
            self.assertNotIn(secret.encode(), first)

    def test_corruption_of_one_sealed_report_including_a_malformed_report_with_claims_is_local(self):
        self.prepare_known_review()
        self.config["settings"]["actions"] = [
            dict(reports=dict(spec=self.reports("ABI mismatch"), standards=self.reports("Novel issue"))),
            dict(reports=dict(spec=self.reports("ABI mismatch"))),
            dict(reports=dict(spec="### F1 [major] ABI mismatch\n"))]
        self.write_config()
        self.replay()
        judgments = self.packet("judgments-template.json")
        hist = self.packet()["history"]["groups"][0]["id"]
        for row in judgments["attempts"]:
            self.claim_groups(row, {"ABI mismatch": (hist, "valid", "in"), "Novel issue": (None, "valid", "in")})
        ref = self.journal()["attempts"][0]["roles"]["spec"]["report"]
        (self.out / "private" / ref["path"]).write_bytes(b"changed after adjudication")
        result = self.score(judgments)
        damaged, good, malformed = result["attempts"][:3]
        for attempt in (damaged, malformed):
            self.assertEqual(attempt["metrics"]["review.recall"], dict(numerator=0, denominator=1, rate=None))
        self.assertEqual(damaged["metrics"]["review.novel_valid"], 1)
        self.assertEqual(good["metrics"]["review.recall"]["rate"], 1)

    def test_disagreements_on_one_historical_group_do_not_erase_an_independent_scope_judgment(self):
        self.prepare_known_review()
        self.config["settings"]["actions"] = [dict(reports=dict(spec=self.reports("ABI width", "Wrong constant"),
                                                               standards=self.reports("ABI mismatch")))]
        self.write_config()
        self.replay()
        judgments = self.packet("judgments-template.json")
        hist = self.packet()["history"]["groups"][0]["id"]
        for row in judgments["attempts"]:
            self.claim_groups(row, {"ABI width": (hist, "false_positive", "in"), "ABI mismatch": (hist, "valid", "in"),
                                    "Wrong constant": (None, "valid", "invalid scope")})
        first = self.score(judgments)["attempts"][0]
        self.assertIsNone(first["metrics"]["review.recall"]["rate"])
        self.assertEqual(first["metrics"]["review.novel_valid"], 1)
        self.assertEqual(first["metrics"]["review.unknown_scope"], 1)
        self.assertTrue(first["unknowns"])

    def test_unbound_receipt_or_ambiguous_completed_slot_cannot_generate_a_score(self):
        self.prepare_known_review()
        self.replay()
        judgments = self.packet("judgments-template.json")
        file = self.out / "private/run.json"
        journal = self.journal()
        for flaw, message in (("receipt", "receipt"), ("slot", "slot")):
            with self.subTest(flaw=flaw):
                changed = copy.deepcopy(journal)
                if flaw == "receipt":
                    changed["receipt_sha256"] = "1" * 64
                else:
                    changed["attempts"][0]["arm"] = changed["attempts"][1]["arm"]
                file.write_text(json.dumps(changed))
                self.score(judgments, error=message)

    def test_a_moved_v1_run_without_a_separate_packet_digest_verifies_against_its_sealed_reports(self):
        self.prepare_known_review()
        self.config["settings"]["actions"] = [dict(reports={"spec": self.reports("{workspace}/abi.h")})]
        self.write_config()
        self.replay()
        gid = self.packet()["history"]["groups"][0]["id"]
        judgments = self.packet("judgments-template.json")
        for row in judgments["attempts"]:
            self.claim_groups(row, {"abi.h": (gid, "valid", "in")})
        journal = self.journal()
        del journal["packet_sha256"]
        (self.out / "private/run.json").write_text(json.dumps(journal))
        self.out = self.out.rename(self.root / "relocated-case")
        self.runner.rename(self.root / "lost-peer")
        self.assertEqual(self.score(judgments)["attempts"][0]["metrics"]["review.recall"]["rate"], 1)

    def test_verified_empty_history_has_no_recall_rate_and_counts_a_novel_group(self):
        self.code_review()
        receipt = self.prepare()
        self.assertEqual(receipt["history"]["unknown"], [])
        self.config["settings"]["actions"] = [dict(reports={"spec": self.reports("Novel issue")})]
        self.write_config()
        self.replay()
        judgments = self.packet("judgments-template.json")
        for row in judgments["attempts"]:
            self.claim_groups(row, {"Novel issue": (None, "valid", "in")})
        result = self.score(judgments)
        self.assertEqual(result["history"]["raw_count"], 0)
        self.assertEqual(result["history"]["groups"], [])
        self.assertEqual(result["history"]["unknown"], [])
        first = result["attempts"][0]["metrics"]
        self.assertEqual(first["review.novel_valid"], 1)
        self.assertEqual(first["review.recall"], dict(numerator=0, denominator=0, rate=None))


class ScoreSlices(ScoreFixture):
    def later_review(self):
        people = [reviewer("spec", "one")]
        self.archived_review(GATE, None, None, people, {}, {"spec": "Target: archived code"})
        report = self.reports("ABI width", "Pointer escape", "Empty array")
        (self.store / GATE / "spec.md").write_text(report)
        findings = [dict(by=[f"spec:F{i}"], axis="spec", severity="major", disposition="accepted") for i in (1, 2, 3)]
        later = [start(GATE, "code-review", "2026-01-01T00:01:00Z", parent=PRIOR, docs=["P001@r2"]),
                 review_end(GATE, "code-review", people, findings)]
        write_lines(self.log, self.events[:-1] + later + self.events[-1:])
        evidence = self.root / "later.tsv"
        table(evidence, [dict(project=str(self.project), unit=GATE, raw_row=str(i), report_stem="spec",
                              finding_id=f"F{i}", defect_group=f"later-{i}", disposition="accepted",
                              end_sha256=sha(json.dumps(later[-1])), report_sha256=sha(report),
                              source_locator=f"spec.md:L{i}") for i in (1, 2, 3)])
        return evidence

    def test_slice_without_a_later_review_scores_status_tests_and_briefs_without_judgments(self):
        self.worker_slice()
        self.prepare()
        self.config["settings"]["actions"] = [
            dict(envelope=dict(worker_status="blocked")), dict(brief="PRIVATE changed worker request"),
            dict(envelope=dict(outcome="stopped", reason="PRIVATE initial worker brief", worker_status=None),
                 remove=["worker"]), dict(envelope=dict(worker_status="stuck"), brief=None)]
        self.write_config()
        self.replay()
        self.project.rename(self.root / "lost-project")
        self.runner.rename(self.root / "lost-peer")
        result = self.score()
        self.assertIsNone(result["judgments"])
        self.assertIsNone(result["judgments_sha256"])
        self.assertEqual(result["incomplete_pairs"], [2])
        self.assertEqual(result["comparable_pairs"], 2)
        blocked, done, stopped, stuck = result["attempts"][:4]
        for attempt, expected in ((blocked, [0, 1, 0]), (done, [1, 0, 0]), (stuck, [0, 0, 1]),
                                  (stopped, [None, None, None])):
            self.assertEqual([attempt["metrics"]["slice.worker." + k] for k in ("done", "blocked", "stuck")], expected)
        m = blocked["metrics"]
        self.assertEqual([m["slice.criteria." + k] for k in ("pass", "fail", "unavailable")], [0, 0, 1])
        self.assertEqual(m["slice.criteria.pass_rate"], dict(numerator=0, denominator=0, rate=None))
        self.assertEqual(m["slice.later.present_rate"], dict(numerator=0, denominator=0, rate=None))
        self.assertEqual(result["pairs"][0]["metrics"]["slice.worker.blocked"]["difference"], -1)
        self.assertEqual(result["pairs"][0]["metrics"]["slice.worker.done"]["difference"], 1)
        self.assertEqual(blocked["brief_comparison"]["status"], "identical")
        self.assertEqual(done["brief_comparison"], dict(status="changed", historical_sha256=digest(b"PRIVATE initial worker brief"),
                                                      dispatched_sha256=digest(b"PRIVATE changed worker request")))
        self.assertEqual(stuck["brief_comparison"]["status"], "unavailable")
        public = (self.out / "result.json").read_bytes()
        self.score()
        self.assertEqual(public, (self.out / "result.json").read_bytes())
        self.assertNotIn(b"PRIVATE", public)
        extra = self.packet("judgments-template.json")
        extra["notes"] = "PRIVATE adjudicator notes"
        extra["attempts"][0]["groups"].append(dict(id="PRIVATE judgment label", claims=["PRIVATE HOST LOG"],
                 historical="PRIVATE history", verdict="PRIVATE reason", scope="PRIVATE request",
                 evidence=[dict(path="../PRIVATE brief", sha256="PRIVATE hash")], transcript="PRIVATE report"))
        self.score(extra)
        self.assertNotIn(b"PRIVATE", (self.out / "result.json").read_bytes())

    def test_later_defect_matches_require_attributable_verified_evidence_and_a_common_decision(self):
        self.worker_slice()
        receipt = self.prepare("--review-evidence", self.later_review())
        self.assertEqual(len(receipt["history"]["groups"]), 3)
        self.config["settings"]["bundle"] = {}
        self.write_config()
        self.replay()
        self.score(error="judgments")
        judgments = self.packet("judgments-template.json")
        first, second = [a["id"] for a in self.journal()["attempts"][:2]]
        by_id = {r["id"]: r for r in judgments["attempts"]}
        a, b = by_id[first]["later"], by_id[second]["later"]
        for group, match in zip(a, ("present", "absent", "unknown")):
            group["match"] = match
        for group, match in zip(b, ("absent", "unknown", "present")):
            group["match"] = match
        result = self.score(judgments)
        for attempt in result["attempts"][:2]:
            self.assertEqual(attempt["metrics"]["slice.later.present_rate"], dict(numerator=1, denominator=2, rate=0.5))
        pair = result["pairs"][0]
        self.assertEqual(pair["common"]["later"], [a[0]["historical"]])
        self.assertEqual(pair["metrics"]["slice.later.present_rate"], dict(
            recorded=dict(numerator=1, denominator=1, rate=1), candidate=dict(numerator=0, denominator=1, rate=0),
            difference=-1))
        for flaw in ("foreign reference", "duplicate group", "no attempt evidence", "invalid match", "nonempty groups",
                     "stale evidence"):
            with self.subTest(flaw=flaw):
                changed = copy.deepcopy(judgments)
                row = next(r for r in changed["attempts"] if r["id"] == second)
                decision = row["later"][0]
                if flaw == "foreign reference":
                    decision["historical"] = "another-case"
                elif flaw == "duplicate group":
                    row["later"].append(decision)
                elif flaw == "no attempt evidence":
                    decision["evidence"] = a[0]["evidence"]
                elif flaw == "invalid match":
                    decision["match"] = "maybe"
                elif flaw == "nonempty groups":
                    row["groups"] = [dict(id="not-a-slice-judgment")]
                else:
                    decision["evidence"][0]["sha256"] = "0" * 64
                changed_result = self.score(changed)
                changed_pair = changed_result["pairs"][0]
                self.assertEqual(changed_pair["common"]["later"], [])
                self.assertIsNone(changed_pair["metrics"]["slice.later.present_rate"]["difference"])
                self.assertEqual(changed_pair["metrics"]["slice.worker.done"]["difference"], 0)
        undecided = next(r for r in judgments["attempts"] if all(d["match"] == "unknown" for d in r["later"]))
        undecided["later"][0]["evidence"] = [dict(path="evidence/unsealed", sha256="0" * 64)]
        inspected = next(a for a in self.score(judgments)["attempts"] if a["id"] == undecided["id"])
        self.assertIn("later-review match or evidence unavailable", inspected["unknowns"])

    def test_criterion_comparisons_use_only_the_common_decided_ids(self):
        shell, fixtures = self.dynamic_shell()
        target = self.worker_slice()
        commands = [(name, ["./" + name]) for name in ("common", "left", "right")]
        self.prepare("--criteria", self.mapping(target, commands), "--fixtures", fixtures)
        def command_success(ok):
            return ["100755", "#!" + shell + "\nexit " + ("0" if ok else "1") + "\n"]
        self.config["settings"]["actions"] = [
            dict(bundle=dict(files={"common": command_success(False), "left": command_success(True)})),
            dict(bundle=dict(files={"common": command_success(True), "right": command_success(False)}))]
        self.write_config()
        self.replay()
        result = self.score()
        for a in result["attempts"][:2]:
            self.assertEqual(a["metrics"]["slice.criteria.pass_rate"], dict(numerator=1, denominator=2, rate=0.5))
            self.assertEqual(a["metrics"]["slice.criteria.unavailable"], 1)
        first = result["pairs"][0]
        self.assertEqual(first["common"]["criteria"], ["common"])
        self.assertEqual(first["metrics"]["slice.criteria.pass_rate"], dict(
            recorded=dict(numerator=0, denominator=1, rate=0), candidate=dict(numerator=1, denominator=1, rate=1),
            difference=1))
