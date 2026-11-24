"""Score the original host-free v1 handoffs after their case directories move.

Each archive contains outputs of its named commit's public prepare and run commands,
including the original judgments template. The peer was that commit's offline fixture.
The original project, runner and per-dispatch workspaces are absent from the archive.
"""
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

from test_replay_prepare import SCRIPT, digest


GOLDENS = {
    "2c56338-review": ("d126de98aeebc880e3a169f692136c4d733df218f6f109129bde40818ce75ffe",
                       "058d3c8d7f651a5149272cb4063c336be49066770cc30c84f800e45739d0a8f8"),
    "2c56338-review-resumed": ("2bf16d6d98ca79fb615cbdf3d961b24dcfb3360a1d193f7174f84b7da19ecab4",
                               "e9cefef388ddb36d84f2a2976a1e44ba3b3309ce133b93e0a3ae26266507f0fd"),
    "ba56b11-slice": ("54704aefbfb561702407163b109ffd6b2d118e077b2cb3ad2b9822dba6d0b661",
                      "f164739ff31de9f0da143de2113a63abc21b82e03fed93983a2f491645ad0b28"),
    "46ec1ee-review": ("eb1134314dae9bc0ec481ea64920bf800d74bdee7c7c756c48abae1c03fcfebf",
                       "4cc8dca518e47fcc80ba3b4cc723f465052a834b03d46c80844a21c95aa6196e"),
}


class HistoricalScore(unittest.TestCase):
    def restore(self, name):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "relocated case"
        archive = Path(__file__).parent / "fixtures/replay_v1" / (name + ".tar.gz")
        with tarfile.open(archive) as tar:
            for member in tar:
                path = root / member.name
                self.assertTrue(path.is_relative_to(root) and ".." not in path.parts)
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    self.assertTrue(member.isfile())
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(tar.extractfile(member).read())
                    path.chmod(member.mode)
        self.packet = root / "blind/packet.json"
        self.judgments = root / "blind/judgments-template.json"
        self.run = root / "private/run.json"
        self.original = self.run.read_bytes()
        self.journal = json.loads(self.original)
        self.assertEqual((digest(self.packet.read_bytes()), digest(self.judgments.read_bytes())), GOLDENS[name])
        self.assertFalse(any((root / "private/jobs").glob("*/slot.json")))
        self.assertFalse((root / "work").exists())
        self.assertFalse(Path(self.journal["runner"]).exists())
        self.assertFalse(Path(json.loads((root / "private/receipt.json").read_bytes())["project"]).exists())
        self.assertEqual(self.journal.get("packet_sha256"), GOLDENS[name][0] if name.startswith("46ec1ee") else None)
        return root

    def score(self, root, error=None):
        result = subprocess.run([sys.executable, SCRIPT, "score", root, "--judgments", self.judgments],
                                capture_output=True, text=True)
        if error:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(error, result.stderr)
            return
        self.assertEqual(result.returncode, 0, result.stderr)
        scored = json.loads((root / "result.json").read_bytes())
        self.assertEqual(scored["judgment_issues"], [])
        self.assertEqual(scored["packet_sha256"], digest(self.packet.read_bytes()))
        self.assertEqual(scored["judgments_sha256"], digest(self.judgments.read_bytes()))
        self.assertEqual(self.run.read_bytes(), self.original)
        return scored

    def test_original_review_handoff_still_scores_and_cannot_be_rebound_by_editing_the_judgments(self):
        root = self.restore("2c56338-review")
        packet = json.loads(self.packet.read_bytes())
        self.assertNotIn("review_input", packet)
        claim, = [c for a in packet["attempts"] for c in a["claims"]]
        excerpt = (root / "blind" / claim["evidence"]["path"]).read_text()
        self.assertIn("ABI in abi.h", excerpt)
        self.assertIn("wall_seconds: 3", excerpt)
        self.assertEqual(self.score(root)["comparable_pairs"], 3)
        packet["task"]["delivery"] = "A different task"
        self.packet.write_text(json.dumps(packet, sort_keys=True, indent=2) + "\n")
        judgments = json.loads(self.judgments.read_bytes())
        judgments["packet_sha256"] = digest(self.packet.read_bytes())
        self.judgments.write_text(json.dumps(judgments))
        self.score(root, error="packet digest differs")

    def test_a_2c56338_review_cannot_be_replaced_by_the_unpublished_ba56b11_encoding(self):
        root = self.restore("2c56338-review")
        packet = json.loads(self.packet.read_bytes())
        claim, = [c for a in packet["attempts"] for c in a["claims"]]
        original = (root / "blind" / claim["evidence"]["path"]).read_bytes()
        # The later controller strips this line and gives the excerpt a different content-bound name.
        alternative = dict(path="evidence/c16e6872a42453fc5ca245a4f35f818a.txt",
                           sha256="5968bddeb0e7a1383dac06242808bb1d440efc5240cb6daec51a7d86803d5717")
        excerpt = original.replace(b"wall_seconds: 3\n", b"")
        self.assertEqual(digest(excerpt), alternative["sha256"])
        (root / "blind" / alternative["path"]).write_bytes(excerpt)
        claim["evidence"] = alternative
        self.packet.write_text(json.dumps(packet, sort_keys=True, indent=2) + "\n")
        unpublished = digest(self.packet.read_bytes())
        self.assertEqual(unpublished, "dc88d7381543c6d707e3f460207d4c4471c615a118857854f5cb4d751d2ccd49")
        judgments = json.loads(self.judgments.read_bytes())
        group, = [g for a in judgments["attempts"] for g in a["groups"]]
        group.update(evidence=[alternative], verdict="valid", scope="in", historical=packet["history"]["groups"][0]["id"])
        judgments["packet_sha256"] = unpublished
        self.judgments.write_text(json.dumps(judgments))
        self.score(root, error="packet digest differs")

    def test_a_digestless_packet_requires_consistent_format_and_authentic_final_dispatch(self):
        errors = {"mixed formats": "ambiguous legacy packet", "changed last root": "packet digest differs",
                  "missing dispatch evidence": "no retained dispatch"}
        for change, error in errors.items():
            with self.subTest(change=change):
                root = self.restore("2c56338-review")
                job = root / "private/jobs" / self.journal["attempts"][-1]["id"]
                if change == "mixed formats":
                    path = job / "dispatch.json"
                    dispatch = json.loads(path.read_bytes())
                    dispatch["receipt_sha256"] = self.journal["receipt_sha256"]
                    path.write_text(json.dumps(dispatch))
                elif change == "changed last root":
                    path = job / "request.json"
                    request = json.loads(path.read_bytes())
                    for name in ("workspace", "output", "skills"):
                        request[name] = "/moved-again/work/" + request[name].split("/work/", 1)[1]
                    path.write_text(json.dumps(request))
                else:
                    for path in (root / "private/jobs").glob("*/dispatch.json"):
                        path.rename(path.with_suffix(".absent"))
                self.score(root, error=error)

    def test_a_fourth_pair_after_relocation_verifies_only_the_handoff_from_the_final_dispatch_root(self):
        root = self.restore("2c56338-review-resumed")
        roots = []
        for row in self.journal["attempts"]:
            request = root / "private/jobs" / row["id"] / "request.json"
            roots.append(Path(json.loads(request.read_bytes())["workspace"]).parents[2])
        self.assertEqual(roots, [roots[0]] * 6 + [roots[-1]] * 2)
        self.assertNotEqual(roots[0], roots[-1])
        # Only the supervisor records identify the last dispatch independently of the editable journal order.
        self.journal["attempts"].reverse()
        self.original = json.dumps(self.journal).encode()
        self.run.write_bytes(self.original)
        self.assertEqual(self.score(root)["comparable_pairs"], 4)

        # The original controller retained the first publication's content-addressed excerpt in blind/evidence.
        # Its own renderer at the earlier root gives a different packet over the same eight terminal results.
        old = dict(path="evidence/0b060bf586b6dc3f4adc590d49a7b53e.txt",
                   sha256="b2562de9037106f453090f5e1ae5dbe0ca335f3487f2fb2811ff674616d3fd0a")
        self.assertEqual(digest((root / "blind" / old["path"]).read_bytes()), old["sha256"])
        packet = json.loads(self.packet.read_bytes())
        claim, = [c for a in packet["attempts"] for c in a["claims"]]
        self.assertNotEqual(claim["evidence"], old)
        claim["evidence"] = old
        self.packet.write_text(json.dumps(packet, sort_keys=True, indent=2) + "\n")
        prior_root_digest = digest(self.packet.read_bytes())
        self.assertEqual(prior_root_digest, "75a6f087f789d4550676fc6f15331a35b664b45e0df702f4438fdfa10d31f719")
        judgments = json.loads(self.judgments.read_bytes())
        group, = [g for a in judgments["attempts"] for g in a["groups"]]
        group["evidence"] = [old]
        judgments["packet_sha256"] = prior_root_digest
        self.judgments.write_text(json.dumps(judgments))
        self.score(root, error="packet digest differs")

    def test_original_slice_artifact_and_criterion_are_readable_from_the_moved_handoff(self):
        root = self.restore("ba56b11-slice")
        row = json.loads(self.packet.read_bytes())["attempts"][0]
        test, = row["tests"]
        self.assertEqual(test["id"], "S1")
        files = json.loads((root / "blind" / row["artifact"]["path"]).read_bytes())["files"]
        self.assertIn("src/[redacted].py", {f["path"] for f in files})
        result = self.score(root)
        self.assertEqual(len(result["attempts"]), 6)
        self.assertTrue(all(a["criteria"] == {"S1": "unavailable"} for a in result["attempts"]))

    def test_worker_status_contradiction_in_a_genuine_old_terminal_excludes_its_pair_but_retains_cost(self):
        root = self.restore("ba56b11-slice")
        attempt = self.journal["attempts"][0]
        job = root / "private/jobs" / attempt["id"]
        terminal = json.loads((job / "terminal.json").read_bytes())["result"]
        report = root / "private" / terminal["roles"]["worker"]["report"]["path"]
        self.assertEqual((terminal["worker_status"], report.read_bytes()), ("done", b"Status: blocked\n"))
        result = self.score(root)
        matching = next(a for a in result["attempts"] if a["id"] == attempt["id"])
        self.assertIsNone(matching["worker_status"])
        self.assertTrue(all(matching["metrics"]["slice.worker." + s] is None for s in ("done", "blocked", "stuck")))
        self.assertEqual(matching["metrics"]["cost.tokens.worker.input"], 11)
        self.assertEqual(matching["metrics"]["cost.wall_seconds"], attempt["wall_seconds"])
        self.assertGreater(attempt["wall_seconds"], 0)
        self.assertEqual(result["incomplete_pairs"], [1])
        self.assertEqual(result["comparable_pairs"], 2)
        self.assertEqual(report.read_bytes(), b"Status: blocked\n")

    def test_reclassify_verified_legacy_review_reports_without_changing_their_claims_or_handoff(self):
        for name in ("2c56338-review", "46ec1ee-review"):
            with self.subTest(case=name):
                root = self.restore(name)
                finding, canonical, shorthand = self.journal["attempts"][:3]
                self.assertTrue(finding["roles"]["spec"]["claims"])
                self.assertFalse(canonical["roles"]["spec"]["report_valid"])
                self.assertTrue(shorthand["roles"]["spec"]["report_valid"])
                rows = {a["id"]: a["metrics"] for a in self.score(root)["attempts"]}
                self.assertEqual(rows[canonical["id"]]["review.recall"], {"numerator": 0, "denominator": 1, "rate": 0})
                self.assertIsNone(rows[shorthand["id"]]["review.recall"]["rate"])
                self.assertEqual(rows[finding["id"]]["review.unknown_verdict"], 1)

    def test_unavailable_report_or_changed_finding_interval_cannot_recover_review_credit(self):
        root = self.restore("46ec1ee-review")
        finding, canonical = self.journal["attempts"][:2]
        judgments = json.loads(self.judgments.read_bytes())
        group, = next(j["groups"] for j in judgments["attempts"] if j["id"] == finding["id"])
        group.update(verdict="valid", scope="in", historical=json.loads(self.packet.read_bytes())["history"]["groups"][0]["id"])
        self.judgments.write_text(json.dumps(judgments))
        prior = self.score(root)["attempts"]
        self.assertEqual([r["metrics"]["review.recall"]["rate"] for r in prior[:2]], [1, 0])
        # This old controller stored claim intervals separately from its surviving original report.
        terminal_file = root / "private/jobs" / finding["id"] / "terminal.json"
        terminal = json.loads(terminal_file.read_bytes())
        for row in (terminal["result"], finding):
            row["roles"]["spec"]["claims"][0]["first_line"] += 1
        terminal_file.write_text(json.dumps(terminal))
        self.original = json.dumps(self.journal).encode()
        self.run.write_bytes(self.original)
        report = root / "private" / canonical["roles"]["spec"]["report"]["path"]
        report.rename(report.with_suffix(".missing"))
        after = self.score(root)["attempts"]
        self.assertEqual([r["metrics"]["review.recall"]["rate"] for r in after[:2]], [None, None])
        self.assertEqual(after[-1]["metrics"]["review.recall"]["rate"], 0)

    def test_old_measurements_need_the_surviving_dispatch_and_original_runner_observations(self):
        root = self.restore("2c56338-review")
        row = self.journal["attempts"][0]
        job = root / "private/jobs" / row["id"]
        request = job / "request.json"
        hidden = request.rename(job / "absent-request")
        self.score(root, error="no retained dispatch")
        hidden.rename(request)
        terminal_file = job / "terminal.json"
        terminal = json.loads(terminal_file.read_bytes())
        for observation in (row, terminal["result"]):
            observation["roles"]["spec"]["tokens"]["input"] += 1
        terminal_file.write_text(json.dumps(terminal))
        self.run.write_text(json.dumps(self.journal))
        self.score(root, error="legacy role measurement differs")
