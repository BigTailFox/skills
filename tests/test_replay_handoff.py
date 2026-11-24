"""Inspect only the published handoff, as a blind adjudicator would."""
import base64
import json
import shutil

from test_replay_prepare import DESIGN, digest
from test_replay_run import RunnerFixture
from test_replay_slice import SliceFixture


class ReviewHandoff(RunnerFixture):
    def handoff(self):
        blind = self.root / "adjudicator"
        shutil.copytree(self.out / "blind", blind)
        self.out.rename(self.root / "archived-case")
        packet = json.loads((blind / "packet.json").read_bytes())
        ref = packet["review_input"]
        data = (blind / ref["path"]).read_bytes()
        self.assertEqual(digest(data), ref["sha256"])
        return packet, json.loads(data)

    def test_scoped_diff_untracked_modes_and_delivery_can_be_checked_from_blind_alone(self):
        base = self.pin(self.store, self.tree(self.store, {"src/abi.h": "int f(void);\n", "outside": "unrelated old"}))
        entries = {"src/abi.h": "short f(void);\n", "outside": "unrelated new", "src/test": ("100755", "assert_width\n")}
        prompt = (f"Target: `git diff --binary --full-index {base} -- src`\nUntracked files: src/test\n"
                  f"Requested delivery: Preserve ABI for model-a in {self.project}/private-note.")
        self.review("code-review", entries, baseline=base, prompts={"spec": prompt})
        self.prepare()
        self.replay()
        packet, view = self.handoff()
        self.assertIn("-int f(void);", view["patch"])
        self.assertIn("+short f(void);", view["patch"])
        self.assertNotIn("unrelated", json.dumps(view))
        self.assertEqual(view["untracked"]["files"], [
            dict(path="src/test", mode="100755", encoding="utf-8", content="assert_width\n")])
        self.assertIn("Preserve ABI", packet["task"]["delivery"])
        for secret in (str(self.project), "model-a"):
            self.assertNotIn(secret, json.dumps(packet))

    def test_gate_handoff_contains_document_body(self):
        body = "---\nrevision: 3\n---\nThe return value must fit in 32 bits.\n"
        self.gate({DESIGN: body})
        self.prepare()
        self.replay()
        _, view = self.handoff()
        self.assertEqual(view["target"]["files"], [dict(path=DESIGN, mode="100644", encoding="utf-8", content=body)])

    def test_review_handoff_preserves_gitlinks_without_opening_a_submodule(self):
        old, new = "1" * 40, "2" * 40
        base = self.pin(self.store, self.tree(self.store, {"library": ("160000", old)}))
        entries = {"library": ("160000", new)}
        target = self.pin(self.store, self.tree(self.store, entries), base)
        self.review("code-review", entries, baseline=base, prompts={"spec": f"Target: `git diff {base} {target} -- library`"})
        self.prepare()
        self.replay()
        _, view = self.handoff()
        for side, oid in (("baseline", old), ("target", new)):
            self.assertEqual(view[side]["files"], [dict(path="library", mode="160000", encoding="gitlink", content=oid)])

    def test_a_fenced_host_log_is_redacted_and_evidence_code_remains_readable(self):
        self.code_review()
        self.prepare()
        log = ("### F1 [major] Wrong model selection\nEvidence:\n```text\nraw host transcript: PRIVATE MESSAGE\n"
               "wall_seconds: 19\n/home/operator/.codex/session\n```\n```python\nmodel = make_decision()\n"
               "```\nRaw host transcript:\n```text\noperator: PRIVATE DISCUSSION\n```\n"
               "````text\nraw host transcript: example\nPRIVATE PREAMBLE\n```python\nprint('PRIVATE REPLY')\n"
               "```\nPRIVATE TAIL\n````\n```python\nmodel = after_log()\n```\n"
               "Raw host transcript: omitted\n\nEvidence: refund() returns 0 for negative amounts.\n"
               "Suggestion: preserve the sign.\nRaw host transcript: private reviewer reply follows\n"
               "> Evidence: PRIVATE original host message\n> ```text\n> PRIVATE QUOTED LOG\n> ```\n"
               "> Suggestion: PRIVATE original host suggestion\nEvidence: PRIVATE lazy continuation\n"
               "\nPRIVATE unlabelled continuation\nEvidence: PRIVATE continuation detail\n"
               "\nEvidence: refund() returns 0.\n"
               "Suggestion: check the signed result.\nRaw host transcript: reviewer reply follows\n"
               "> ```text\n> PRIVATE fenced host message\n> ```\n"
               "Evidence: rounding loses the sign.\nSuggestion: fix the sign.\nVerdict: revise\n")
        self.config["settings"]["actions"] = [dict(reports={"spec": log})]
        self.write_config()
        self.replay()
        blind = self.out / "blind"
        all_bytes = b"".join(p.read_bytes() for p in blind.rglob("*") if p.is_file())
        for private in (b"PRIVATE", b"wall_seconds:", b"/home/operator"):
            self.assertNotIn(private, all_bytes)
        self.assertIn(b"model = make_decision()", all_bytes)
        self.assertIn(b"model = after_log()", all_bytes)
        self.assertIn(b"refund() returns 0 for negative amounts.", all_bytes)
        self.assertIn(b"preserve the sign.", all_bytes)
        self.assertIn(b"Evidence: refund() returns 0.\n", all_bytes)
        self.assertIn(b"check the signed result.", all_bytes)
        self.assertIn(b"Evidence: rounding loses the sign.", all_bytes)
        self.assertIn(b"Suggestion: fix the sign.", all_bytes)

    def test_gate_handoff_binds_separate_as_built_code_to_the_design_scope(self):
        self.repo(self.project)
        tree = self.tree(self.store, {"rule": "approved\n", "irrelevant": "unrelated"})
        # A reviewed as-built pin must match the original project tree exactly.
        self.git(self.project, "update-ref", "HEAD", self.pin(self.project, self.tree(self.project, {
            "rule": "approved\n", "irrelevant": "unrelated"})))
        approved = self.git(self.project, "rev-parse", "HEAD")
        code = self.pin(self.store, tree)
        entries = {DESIGN: f"---\nrevision: 3\npaths: [rule]\nas_built: {approved}\n---\nContract\n"}
        base = self.pin(self.store, self.tree(self.store, {DESIGN: "Old contract\n"}))
        opening = self.pin(self.store, self.tree(self.store, entries), base, code)
        self.review("gate", entries, opening=opening, baseline=base, docs=["D001@r3"],
                    prompts={"same-model": f"Target: {DESIGN}\nChanges since: {base}\nAs-built: approved {approved}\n"})
        self.prepare()
        self.replay()
        _, view = self.handoff()
        self.assertEqual([(r["path"], r["content"]) for r in view["as_built"]["files"]], [("rule", "approved\n")])

    def test_copy_and_retry_normalize_each_original_workspace_and_replace_stale_evidence(self):
        self.code_review()
        self.prepare()
        late = "unanticipated-engine"
        claim = f"### F1 [major] {{workspace}}/abi.h\nEvidence: {late}\n```python\nmodel = make_decision()\n```\nVerdict: revise\n"
        self.config["settings"]["actions"] = [
            dict(reports={"spec": claim}), dict(envelope={"outcome": "stopped", "reason": "retry"}), {}, {}, {}, {},
            dict(roles={"spec": {"model": late}}, reports={"spec": claim})]
        self.write_config()
        self.replay()
        first_dir = self.out
        self.out = self.root / "copy"
        shutil.copytree(first_dir, self.out, symlinks=True)
        self.replay()
        blind = self.out / "blind"
        packet = json.loads((blind / "packet.json").read_bytes())
        for row in packet["attempts"]:
            for finding in row["claims"]:
                excerpt = (blind / finding["evidence"]["path"]).read_text()
                self.assertIn("abi.h", excerpt)
                self.assertNotIn("[private path]", excerpt)
                self.assertIn("model = make_decision()", excerpt)
        self.assertFalse(any(late.encode() in p.read_bytes() for p in blind.rglob("*") if p.is_file()))
        packet_bytes = (blind / "packet.json").read_bytes()
        self.out = self.root / "moved"
        blind.parent.rename(self.out)
        self.replay()
        self.assertEqual((self.out / "blind/packet.json").read_bytes(), packet_bytes)


class SliceHandoff(SliceFixture):
    def test_paths_code_and_criterion_identity_survive_blinding(self):
        target = self.worker_slice()
        secret = "worker-model-criterion"
        self.prepare("--criteria", self.mapping(target, [(secret, ["/bin/false"])]))
        binary = base64.b64encode(b"\xffcandidate_reviews\x00").decode()
        self.config["settings"]["bundle"] = dict(files={"asset.bin": {"base64": binary}, "src/recorded.py": "model = first()\n",
                "src/candidate.py": "model = second()\nrecorded_model = 1\n"})
        self.write_config()
        self.replay()
        blind = self.out / "blind"
        packet = json.loads((blind / "packet.json").read_bytes())
        cid = packet["task"]["criteria"][0]["id"]
        self.assertNotEqual(cid, secret)
        for row in packet["attempts"]:
            self.assertEqual([t["id"] for t in row["tests"]], [cid])
            view = json.loads((blind / row["artifact"]["path"]).read_bytes())
            files = {f["path"]: f["content"] for f in view["files"]}
            self.assertEqual(files["src/recorded.py"], "model = first()\n")
            self.assertEqual(files["src/candidate.py"], "model = second()\nrecorded_model = 1\n")
            self.assertEqual(files["asset.bin"], binary)
        self.assertFalse(any(secret.encode() in p.read_bytes() for p in blind.rglob("*") if p.is_file()))
