"""Compare independently prepared cases through the four public replay commands."""
import json
import shutil
import subprocess
import sys

from test_replay_prepare import SCRIPT
from test_replay_score import ScoreFixture
from test_trace_report import GATE, UNIT, write_lines
from test_trace_reviews import reviewer


class Summaries(ScoreFixture):
    def test_partial_finding_counts_are_reported_as_lower_bounds_in_case_and_cohort(self):
        self.prepare_known_review()
        self.config["settings"]["actions"] = [dict(reports={"spec": self.reports("Unjudged claim")})]
        self.write_config()
        self.replay()
        self.score(self.packet("judgments-template.json"))
        summary = self.summary(self.out)
        for row in (summary["cases"][0], summary["cohorts"][0]):
            obs = row["metrics"]["review.false_positive"]["observed"]
            self.assertEqual(obs["recorded"], dict(measurements=2, total=0, partial_measurements=1, lower_bound=0))
            self.assertEqual(obs["candidate"], dict(measurements=3, total=0, partial_measurements=0, lower_bound=None))

    def finish(self, *prepare_options):
        self.prepare(*prepare_options)
        self.replay()
        return self.score(self.packet("judgments-template.json"))

    def copy_unit(self, unit=GATE, **opening):
        shutil.copytree(self.store / UNIT, self.store / unit)
        for ref in ("trace", "review-input"):
            target = self.git(self.store, "rev-parse", f"refs/{ref}/{UNIT}")
            self.git(self.store, "update-ref", f"refs/{ref}/{unit}", target)
        start, end = self.events[-2:]
        write_lines(self.log, self.events + [dict(start, id=unit, **opening), dict(end, id=unit)])

    def summary(self, *cases, error=None):
        response = subprocess.run([sys.executable, SCRIPT, "summarize", *cases],
                                  text=True, capture_output=True, timeout=30)
        if error:
            self.assertNotEqual(response.returncode, 0)
            self.assertIn(error, response.stderr)
            self.assertNotIn("Traceback", response.stderr)
            return
        self.assertEqual(response.returncode, 0, response.stderr)
        return json.loads(response.stdout)

    def test_unequal_pair_counts_give_each_historical_unit_one_vote(self):
        self.gate()
        self.copy_unit()
        token = dict(input=31, cached_input=3, output=5, reasoning_output=2)
        stop = dict(envelope=dict(outcome="stopped", reason="operator stop"))
        self.config["settings"]["actions"] = [{}, {"roles": {"parent": {"tokens": token}}}, stop, {}, {}, stop]
        self.write_config()
        first = self.out
        self.finish()
        self.out = self.root / "second"
        self.finish("--unit", GATE)
        summary = self.summary(first, self.out)
        cases = {case["identity"]["unit"]: case for case in summary["cases"]}
        key = "cost.tokens.parent.input"
        self.assertEqual(cases[UNIT]["complete_pairs"], [1])
        self.assertEqual(cases[UNIT]["incomplete_pairs"], [2, 3])
        self.assertTrue(cases[UNIT]["sparse_pairs"])
        self.assertEqual(cases[UNIT]["metrics"][key]["mean_difference"], 20)
        self.assertEqual(cases[GATE]["metrics"][key]["mean_difference"], 0)
        cohort, = summary["cohorts"]
        self.assertEqual(cohort["case_count"], 2)
        m = cohort["metrics"][key]
        self.assertEqual((m["case_count"], m["pair_count"], m["mean_difference"]), (2, 4, 10))

    def test_a_result_must_still_match_its_inputs_judgments_and_observed_evidence(self):
        self.gate()
        self.config["settings"]["actions"] = [{"reports": {"same-model": self.reports("A finding")}}]
        self.write_config()
        result = self.finish()
        self.project.rename(self.root / "lost-project")
        self.runner.rename(self.root / "lost-runner")
        original = self.summary(self.out)
        private = self.out / "private"
        packet = self.packet()
        with_claim = next(a for a in packet["attempts"] if a["claims"])
        claim = self.out / "blind" / with_claim["claims"][0]["evidence"]["path"]
        source = self.journal()["attempts"][0]["roles"]["same-model"]["report"]
        changed = dict(result, comparable_pairs=85)
        for path, replacement in (
            (self.out / "result.json", json.dumps(changed).encode()),
            (private / "judgments" / result["judgments_sha256"], b"{}"),
            (private / source["path"], b"Changed sealed report"),
            (claim, b"Changed blinded claim"),
            (self.out / "blind/packet.json", b"{}"),
            (private / "receipt.sha256", b"invalid"),
        ):
            with self.subTest(path=path):
                data = path.read_bytes()
                path.write_bytes(replacement)
                self.summary(self.out, error="cannot verify scored case")
                path.write_bytes(data)
        self.assertEqual(self.summary(self.out), original)

    def test_duplicate_directories_count_once_and_competing_inputs_or_judgments_are_excluded(self):
        self.gate()
        self.config["settings"]["actions"] = [{"reports": {"same-model": self.reports("A finding")}}]
        self.write_config()
        first = self.out
        result = self.finish()
        copy = self.root / "copy"
        shutil.copytree(first, copy, symlinks=True)
        unique = self.summary(copy, first, copy)
        row, = unique["cases"]
        self.assertEqual(row["case"], result["case"])
        self.assertEqual(set(row["directories"]), {str(first), str(copy)})
        self.assertEqual(unique["cohorts"][0]["case_count"], 1)
        self.assertEqual(unique["conflicts"], [])

        self.out = copy
        judgments = self.packet("judgments-template.json")
        for attempt in judgments["attempts"]:
            self.claim_groups(attempt, {"A finding": (None, "valid", "in")})
        self.score(judgments)
        conflicting = self.summary(copy, first)
        conflict, = conflicting["conflicts"]
        self.assertEqual(conflict["identity"], result["identity"])
        self.assertIn("judgments_sha256", conflict["differing"])
        self.assertEqual(conflicting["cohorts"], [])
        self.assertEqual(conflicting["cases"], [])
        self.assertEqual(self.summary(first, copy), conflicting)

        self.out = self.root / "changed-input"
        fixtures = self.root / "fixtures"
        fixtures.mkdir()
        (fixtures / "dependency").write_text("different required input")
        self.finish("--fixtures", fixtures)
        conflict, = self.summary(first, self.out)["conflicts"]
        self.assertIn("receipt_sha256", conflict["differing"])

    def test_observed_counts_times_and_separate_tokens_survive_partial_pairs_and_unknown_rates(self):
        self.prepare_known_review()
        token = dict(input=31, cached_input=3, output=5, reasoning_output=2)
        absent = dict(token, input=None, cached_input=None)
        self.config["settings"]["actions"] = [
            {}, dict(roles={"parent": {"tokens": token}}, reports={"spec": self.reports("ABI mismatch")}),
            dict(envelope=dict(outcome="stopped", reason="operator stop")), {},
            dict(roles={"parent": {"tokens": absent}}), {}]
        self.write_config()
        self.replay()
        judgments = self.packet("judgments-template.json")
        historical = self.packet()["history"]["groups"][0]["id"]
        for attempt in judgments["attempts"]:
            self.claim_groups(attempt, {"ABI mismatch": (historical, "valid", "in")})
        result = self.score(judgments)
        summary = self.summary(self.out)
        case, = summary["cases"]
        cohort, = summary["cohorts"]
        self.assertEqual(case["incomplete_pairs"], [2])
        self.assertEqual(cohort["sparse_cases"], [case["case"]])
        self.assertEqual({a["outcome"] for a in case["unpaired_attempts"]}, {"stopped", "completed"})
        for row in (case, cohort):
            m = row["metrics"]["review.recall"]
            self.assertEqual((m["pair_count"], m["mean_difference"]), (2, 0.5))
            self.assertEqual(m["observed"]["recorded"], dict(measurements=3, numerator=0, denominator=3, known_rates=3))
            self.assertEqual(m["observed"]["candidate"], dict(measurements=3, numerator=1, denominator=3, known_rates=2))
            self.assertEqual(m["paired_observed"]["candidate"], dict(measurements=2, numerator=1, denominator=2, known_rates=2))
            token = row["metrics"]["cost.tokens.parent.input"]
            self.assertEqual((token["pair_count"], token["mean_difference"]), (1, 20))
            self.assertEqual(token["observed"]["recorded"], dict(measurements=2, total=22, partial_measurements=0, lower_bound=None))
            self.assertEqual(token["observed"]["candidate"], dict(measurements=3, total=53, partial_measurements=0, lower_bound=None))
            for role in ("spec", "standards"):
                self.assertEqual(row["metrics"][f"cost.tokens.{role}.cached_input"]["observed"]["candidate"]["total"], 9)
            observed_wall = sum(a["metrics"]["cost.wall_seconds"] for a in result["attempts"] if a["arm"] == "recorded")
            self.assertAlmostEqual(row["metrics"]["cost.wall_seconds"]["observed"]["recorded"]["total"], observed_wall)
        self.assertEqual(case["metrics"]["cost.tokens.parent.input"]["unavailable_pairs"], [3])
        self.assertEqual(cohort["metrics"]["review.scope"]["excluded_cases"], [case["case"]])
        self.assertIsNone(cohort["metrics"]["review.scope"]["mean_difference"])

    def test_project_rows_precede_the_equal_case_mean_across_compatible_projects(self):
        self.gate()
        self.copy_unit()
        other = self.root / "other-project"
        shutil.copytree(self.project, other, symlinks=True)
        actions = [{} for _ in range(18)]
        for index, count in ((1, 29), (13, 38)):
            actions[index] = {"roles": {"parent": {"tokens": dict(input=count, cached_input=3, output=5, reasoning_output=2)}}}
        self.config["settings"]["actions"] = actions
        self.write_config()
        paths = []
        for n, options in enumerate(([], ["--unit", GATE], ["--project", other])):
            self.out = self.root / f"case-{n}"
            self.finish(*options)
            paths.append(self.out)
        report = self.summary(*paths)
        self.assertEqual([r["scope"] for r in report["cohorts"]], ["project", "project", "combined"])
        first, second, combined = report["cohorts"]
        m = "cost.tokens.parent.input"
        self.assertEqual({r["cohort"]["project"]: r["metrics"][m]["mean_difference"] for r in (first, second)},
                         {str(self.project): 3, str(other): 9})
        self.assertEqual(set(combined["projects"]), {str(self.project), str(other)})
        self.assertEqual((combined["case_count"], combined["complete_pair_count"], combined["metrics"][m]["mean_difference"]),
                         (3, 9, 5))
        self.assertEqual(self.summary(*reversed(paths)), report)

    def test_control_candidate_and_each_incompatible_cohort_dimension_remain_distinct(self):
        self.config["roles"]["cross-family"] = dict(model="model-b", effort="high")
        self.write_config()
        self.gate()
        paths = [self.out]
        control = self.finish()
        baseline = control["cohort"]
        self.assertEqual(baseline["suites"]["recorded"], baseline["suites"]["candidate"])
        self.different_suite()
        self.out = self.root / "candidate"
        paths.append(self.out)
        candidate = self.finish()
        self.assertEqual(candidate["identity"], control["identity"])
        self.assertNotEqual(candidate["cohort"]["suites"]["recorded"], candidate["cohort"]["suites"]["candidate"])
        self.git(self.skills, "update-ref", "HEAD", self.candidate)
        differences = {control["case"]: set(), candidate["case"]: {"suites"}}
        for n, (name, expected) in enumerate((("tier", {"tier"}), ("roles", {"roles"}), ("kind", {"kind", "roles"}),
                                              ("host", {"host", "config_sha256"}), ("config", {"config_sha256"}),
                                              ("runner", {"runner_sha256"})), 1):
            self.events = self.events[:1]
            (self.store / UNIT).rename(self.root / f"prior-archive-{n}")
            self.config["host"] = "cursor" if name == "host" else "codex"
            self.config["settings"].pop("routing_note", None)
            if name == "config":
                self.config["settings"]["routing_note"] = "second local profile"
            if name == "runner":
                with self.runner.open("a") as executable:
                    executable.write("\n# Another local runner build.\n")
            self.write_config()
            if name == "kind":
                self.code_review()
            elif name == "roles":
                self.gate(people=[reviewer("same-model", "first"), dict(reviewer("cross-family", "second"), model="model-b")])
            else:
                self.gate()
            unit = f"20260101T0000{n:02d}Z-123abc"
            self.copy_unit(unit, host=self.config["host"], tier="L2" if name == "tier" else "L1")
            self.out = self.root / name
            with self.subTest(dimension=name):
                scored = self.finish("--unit", unit)
                paths.append(self.out)
                differences[scored["case"]] = expected
        report = self.summary(*paths)
        self.assertEqual(report["conflicts"], [])
        self.assertEqual(len(report["cohorts"]), len(paths))
        self.assertEqual(len(report["cases"]), len(paths))
        for row in report["cohorts"]:
            self.assertEqual(row["scope"], "project")
            self.assertEqual((row["case_count"], row["complete_pair_count"]), (1, 3))
            case_id, = row["cases"]
            self.assertEqual({k for k in baseline if row["cohort"][k] != baseline[k]}, differences[case_id])

    def test_a_slice_with_no_complete_pair_preserves_unknowns_and_binds_its_unjudged_artifact(self):
        self.worker_slice(brief="PRIVATE historical assignment")
        self.prepare()
        stop = {"envelope": dict(outcome="stopped", reason="host stop", worker_status=None), "remove": ["worker"]}
        self.config["settings"].update(bundle={}, actions=[{}, stop, stop, {}, {}, stop])
        self.write_config()
        self.replay()
        self.score()
        report = self.summary(self.out)
        row, = report["cases"]
        self.assertEqual(row["incomplete_pairs"], [1, 2, 3])
        self.assertEqual(row["complete_pairs"], [])
        self.assertEqual(row["metrics"]["slice.worker.done"]["observed"]["recorded"]["total"], 3)
        self.assertIsNone(row["metrics"]["slice.worker.done"]["mean_difference"])
        self.assertEqual(report["cohorts"][0]["metrics"]["slice.worker.done"]["excluded_cases"], [row["case"]])
        self.assertNotIn("PRIVATE", json.dumps(report))
        # The artifact did not enter any later-group judgment. Changing it must still invalidate the old score.
        ref = next(a["artifact"] for a in self.packet()["attempts"] if a["artifact"])
        file = self.out / "blind" / ref["path"]
        original = file.read_bytes()
        file.write_bytes(b"changed exported artifact")
        self.summary(self.out, error="cannot verify scored case")
        self.score()
        self.assertEqual(self.summary(self.out)["cases"][0]["complete_pairs"], [])
        file.write_bytes(original)
        self.summary(self.out, error="cannot verify scored case")
