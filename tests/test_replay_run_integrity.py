"""Dispatch and scoring corrections at the public replay CLI boundary."""
import json
import shutil
import copy

from test_replay_prepare import DESIGN, PLAN, PLAN_BODY
from test_replay_score import ScoreFixture
from test_trace_report import write_lines


class RunIntegrity(ScoreFixture):
    def test_old_v1_dispatches_verify_after_a_move_without_trusting_the_order_in_run_json(self):
        self.different_suite()
        self.gate()
        self.prepare()
        self.replay()
        judgments = self.packet("judgments-template.json")
        journal = self.journal()
        for row in journal["attempts"]:
            job = self.out / "private/jobs" / row["id"]
            (job / "slot.json").unlink()
            path = job / "terminal.json"
            terminal = json.loads(path.read_bytes())
            terminal.pop("slot_sha256")
            terminal.pop("seal_sha256")
            path.write_text(json.dumps(terminal))
        self.out = self.out.rename(self.root / "moved-v1")
        self.project.rename(self.root / "removed-project")
        self.runner.rename(self.root / "removed-runner")
        journal["attempts"].reverse()
        path = self.out / "private/run.json"
        path.write_text(json.dumps(journal))
        self.assertEqual(self.score(judgments)["comparable_pairs"], 3)
        first = journal["attempts"][0]
        later = next(a for a in journal["attempts"] if a["arm"] == first["arm"] and a["pair"] != first["pair"])
        first["pair"], later["pair"] = later["pair"], first["pair"]
        path.write_text(json.dumps(journal))
        self.score(judgments, error="legacy slot order")

    def test_reattachment_refuses_linked_private_job_files_and_work_outputs(self):
        self.gate()
        self.prepare()
        self.replay()
        judgments = self.packet("judgments-template.json")
        ident = self.journal()["attempts"][0]["id"]
        for i, name in enumerate((f"private/jobs/{ident}/request.json", f"private/jobs/{ident}/dispatch.lock",
                                  f"private/jobs/{ident}/evidence", f"work/{ident}/output", f"private/jobs/{ident}")):
            with self.subTest(name=name):
                link = self.out / name
                moved = link.rename(self.root / f"outside-{i}")
                link.symlink_to(moved, target_is_directory=moved.is_dir())
                self.replay(error="case path")
                self.score(judgments, error="case path")
                link.unlink()
                moved.rename(link)
        self.assertEqual(len(self.calls()), 6)

    def test_score_verifies_measurements_and_slot_bindings_after_move_and_reordering(self):
        self.different_suite()
        self.gate()
        self.prepare()
        self.replay()
        judgments = self.packet("judgments-template.json")
        self.out = self.out.rename(self.root / "relocated")
        self.project.rename(self.root / "source-removed")
        self.runner.rename(self.root / "runner-removed")
        self.config_path.rename(self.root / "profile-removed")
        original = self.journal()
        original["attempts"].reverse()
        path = self.out / "private/run.json"
        path.write_text(json.dumps(original))
        self.assertEqual(self.score(judgments)["comparable_pairs"], 3)
        for change in ("tokens", "wall", "arms", "pairs", "ids"):
            with self.subTest(change=change):
                journal = copy.deepcopy(original)
                a, b = journal["attempts"][:2]
                if change == "tokens":
                    a["roles"]["parent"]["tokens"]["input"] += 10
                elif change == "wall":
                    a["wall_seconds"] += 10
                elif change == "pairs":
                    b = next(x for x in journal["attempts"] if x["arm"] == a["arm"] and x["pair"] != a["pair"])
                    a["pair"], b["pair"] = b["pair"], a["pair"]
                else:
                    key = "arm" if change == "arms" else "id"
                    a[key], b[key] = b[key], a[key]
                path.write_text(json.dumps(journal))
                self.score(judgments, error="sealed attempt")
        path.write_text(json.dumps(original))
        job = self.out / "private/jobs" / original["attempts"][0]["id"]
        for filename in ("request.json", "dispatch.json", "terminal.json"):
            with self.subTest(filename=filename):
                file = job / filename
                previous = file.read_bytes()
                altered = json.loads(previous)
                altered["roles" if filename == "request.json" else "wall_seconds"] = {}
                file.write_text(json.dumps(altered))
                self.score(judgments, error="sealed attempt")
                file.write_bytes(previous)

    def test_symlinked_case_directories_stop_before_locking_or_dispatch(self):
        self.gate()
        self.prepare()
        baseline = self.out
        for i, path in enumerate(("work", "private/jobs", "blind", "blind/evidence", "private/suites")):
            with self.subTest(path=path):
                self.out = self.root / f"unsafe-{i}"
                shutil.copytree(baseline, self.out, symlinks=True)
                dest = self.out / path
                outside = self.root / f"outside-{i}"
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    dest.rename(outside)
                else:
                    outside.mkdir()
                sentinel = outside / "sentinel"
                sentinel.write_text("unchanged")
                before = sorted(outside.rglob("*"))
                dest.symlink_to(outside, target_is_directory=True)
                self.replay(error="case path")
                self.assertEqual(sorted(outside.rglob("*")), before)
                self.assertEqual(sentinel.read_text(), "unchanged")
                self.assertFalse((self.out / "private/run.lock").exists())
                self.assertEqual(self.calls(), [])

    def test_default_resume_retries_outstanding_slots_in_the_original_five_pairs(self):
        self.gate()
        self.prepare()
        self.config["settings"]["actions"] = [{}] * 8 + [dict(envelope={"outcome": "stopped", "reason": "cancelled"})]
        self.write_config()
        self.replay("--repetitions", 5)
        self.assertEqual(self.journal()["incomplete_pairs"], [5])
        self.replay()
        self.assertEqual(self.journal()["comparable_pairs"], 5)
        self.assertEqual(len(self.calls()), 11)

    def test_contradictory_worker_status_is_sealed_without_credit_and_stopped_exits_remain_stopped(self):
        self.worker_slice()
        self.prepare()
        stopped = dict(envelope={"outcome": "stopped", "worker_status": None, "reason": "operator stopped"},
                       remove=["worker"])
        self.config["settings"]["actions"] = [dict(reports={"worker": "Status: blocked\n"}),
                                               dict(stopped, exit=130), dict(stopped, exit=143)]
        self.write_config()
        self.replay()
        first = self.journal()["attempts"][0]
        self.assertEqual((self.out / "private" / first["roles"]["worker"]["report"]["path"]).read_text(), "Status: blocked\n")
        self.assertIsNone(first["worker_status"])
        result = self.score()
        self.assertEqual([a["outcome"] for a in result["attempts"][:3]], ["failed", "stopped", "stopped"])
        self.assertIsNone(result["attempts"][0]["metrics"]["slice.worker.done"])
        self.assertEqual(result["incomplete_pairs"], [1, 2])

    def test_unchanged_named_plan_and_design_must_be_granted_before_dispatch(self):
        old = {"abi.h": "old", DESIGN: "---\nrevision: 3\n---\n", PLAN: PLAN_BODY}
        base = self.pin(self.store, self.tree(self.store, old))
        self.review("code-review", old | {"abi.h": "new"}, baseline=base, docs=["P001@r2", "D001@r3"],
                    prompts={"spec": f"Target: `git diff {base} -- abi.h`\nUntracked files: none"})
        self.prepare()
        for missing, other in ((DESIGN, PLAN), (PLAN, DESIGN)):
            self.config["read_paths"] = [".agents/skills", "abi.h", other]
            self.write_config()
            self.replay(error=missing)
            self.assertEqual(self.calls(), [])
        self.config["read_paths"].append(PLAN)
        self.write_config()
        self.replay()
        self.assertEqual(len(self.calls()), 6)

    def test_slice_cannot_dispatch_with_only_its_plan_granted_when_it_names_a_design(self):
        self.worker_slice({DESIGN: "---\nrevision: 3\n---\n"})
        self.events[2]["docs"] = ["P001@r2", "D001@r3"]
        write_lines(self.log, self.events)
        self.prepare()
        self.config["read_paths"] = [".agents/skills", PLAN]
        self.write_config()
        self.replay(error=DESIGN)
        self.assertEqual(self.calls(), [])

    def test_missing_historical_workflow_is_incompatible_even_with_the_canonical_tool(self):
        self.gate()
        self.events[1]["skill"] = "canon-code-review"
        write_lines(self.log, self.events)
        # The gate explicitly ran a different workflow from the legacy gate default.
        files = {k: v for k, v in self.files.items() if k != "canon-code-review/SKILL.md"}
        self.git(self.skills, "update-ref", "HEAD", self.pin(self.skills, self.tree(self.skills, {
            "skills/execution/" + k: v for k, v in files.items()})))
        self.config["settings"].update(workflow="canon-code-review", actions=[dict(roles={"same-model": {"loaded": []}})])
        self.write_config()
        receipt = self.prepare()
        self.assertEqual(receipt["workflow_skill"], "canon-code-review")
        self.replay()
        rows = self.journal()["attempts"]
        self.assertEqual([r["outcome"] for r in rows if r["arm"] == "recorded"], ["completed"] * 3)
        self.assertEqual([r["outcome"] for r in rows if r["arm"] == "candidate"], ["incompatible"] * 3)
        self.assertEqual(len(self.calls()), 3)
