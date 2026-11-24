"""Run eligible historical cases with only their named frozen document inputs granted."""
import json
from pathlib import Path
import shutil

from test_replay_prepare import DESIGN, PLAN, PLAN_BODY, digest
from test_replay_run import RunnerFixture
from test_replay_slice import SliceFixture
from test_trace_report import CONV, write_lines


class LiveReviewDocuments(RunnerFixture):
    def test_untracked_plan_and_design_survive_source_loss_and_reach_the_blind_handoff(self):
        source = "src/abi.h"
        sibling = "docs/designs/D002-unrelated.md"
        design_text = "---\nrevision: 3\n---\nPreserve the exact byte count.\n"
        base_files = {source: "old ABI\n", sibling: "irrelevant private file\n",
                      DESIGN: "---\nrevision: 1\n---\nOld requirement.\n"}
        baseline = self.pin(self.store, self.tree(self.store, base_files))
        target = base_files | {source: "new ABI\n", DESIGN: design_text, PLAN: PLAN_BODY}
        prompt = (f"Target: `git diff --full-index {baseline} -- src`\n"
                  f"Untracked files: {DESIGN}, {PLAN}\nRequested delivery: P001@r2, S1.")
        self.review("code-review", target, baseline=baseline, docs=["D001@r3", "P001@r2"], prompts={"spec": prompt})
        receipt = self.prepare()
        self.assertIn("Preserve the ABI.", receipt["task"]["delivery"])
        checkout = self.out / "private/input"
        self.assertEqual(set(self.git(checkout, "ls-files", "--others").splitlines()), {DESIGN, PLAN})
        self.assertEqual(self.git(checkout, "ls-tree", "--name-only", "-r", "HEAD", "--", DESIGN, PLAN), "")
        self.project.rename(self.root / "retired-project")
        self.skills.rename(self.root / "retired-skills")
        self.config["read_paths"] = [".agents/skills", source, DESIGN, PLAN]
        self.write_config()
        self.replay()
        self.assertEqual(self.journal()["comparable_pairs"], 3)

        handoff = self.root / "adjudicator"
        shutil.copytree(self.out / "blind", handoff)
        self.out.rename(self.root / "retired-case")
        packet = json.loads((handoff / "packet.json").read_bytes())
        ref = packet["review_input"]
        data = (handoff / ref["path"]).read_bytes()
        self.assertEqual(digest(data), ref["sha256"])
        view = json.loads(data)
        self.assertEqual({f["path"]: f["content"] for f in view["untracked"]["files"]},
                         {DESIGN: design_text, PLAN: PLAN_BODY})
        self.assertEqual([f["path"] for f in view["target"]["files"]], [source])
        self.assertEqual({f["path"]: f["content"] for f in view["baseline"]["files"]},
                         {source: base_files[source], DESIGN: base_files[DESIGN]})
        self.assertIn("Preserve the ABI.", packet["task"]["delivery"])
        self.assertNotIn(sibling, json.dumps(view))


class SliceDocuments(SliceFixture):
    def source_docs(self, refs):
        previous = self.events[2]["docs"]
        self.events[2]["docs"] = refs
        write_lines(self.log, self.events)
        # Keep the independently archived host invocation consistent with the trace receipt.
        rollout = next(self.codex.rglob(f"rollout-*-{CONV}.jsonl"))

        def command(names):
            return "start slice " + " ".join(r.split("@")[0] for r in names) + " --slice"

        contents = rollout.read_text()
        self.assertEqual(contents.count(command(previous)), 1)
        rollout.write_text(contents.replace(command(previous), command(refs)))

    def test_mixed_reference_types_run_with_exact_file_grants_after_source_loss(self):
        paths = {"I002": "lib/docs/archived/investigations/I002-wrong-width.md",
                 "C003": "docs/concepts/C003-contract.md",
                 "E004A": "docs/experiments/E004A-width.md",
                 "R005@r4": "docs/reviews/R005-changes.md",
                 "D006": "lib/docs/designs/D006-design.md"}
        entries = {p: ref + " source.\n" for ref, p in paths.items()}
        entries[paths["R005@r4"]] = "---\nrevision: 4\n---\nReviewed changes.\n"
        self.worker_slice(entries | {"unrelated.txt": "unrelated input"})
        refs = ["P001@r2", *paths]
        self.source_docs(refs)
        self.assertEqual(self.prepare()["task"]["docs"], refs)
        self.project.rename(self.root / "retired-project")
        self.codex.rename(self.root / "retired-host")
        self.config["read_paths"] = [".agents/skills", PLAN, *paths.values()]
        missing = paths["I002"]
        self.config["read_paths"].remove(missing)
        self.write_config()
        self.replay(error=missing)
        self.assertEqual(self.calls(), [])
        self.config["read_paths"].append(missing)
        self.write_config()
        self.replay()
        self.assertEqual(self.journal()["comparable_pairs"], 3)
        for call in self.calls():
            workspace = Path(call["workspace"])
            self.assertEqual({p: (workspace / p).read_text() for p in entries}, entries)

    def test_missing_ambiguous_and_wrong_revision_refs_stop_before_dispatch_even_with_full_grants(self):
        self.worker_slice({"docs/reviews/R003-abi.md": "---\nrevision: 3\n---\nExact contract\n",
                           "docs/experiments/E004-first.md": "First experiment\n",
                           "lib/docs/archived/experiments/E004-second.md": "Second experiment\n"})
        for ref in ("I002", "D009@r1", "R003@r2", "E004"):
            with self.subTest(ref=ref):
                self.source_docs(["P001@r2", ref])
                out = self.root / ref
                self.prepare(out=out)
                self.replay(out=out, error="named document unavailable")
                self.assertEqual(self.calls(), [])
