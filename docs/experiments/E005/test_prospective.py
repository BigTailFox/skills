"""Check the preserved Codex parent/child evidence with small redacted records."""

import csv
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_prospective as check


class ProspectiveWorker(unittest.TestCase):
    def setUp(self):
        scratch = Path(".canon/canon/E005-tests")
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.day = self.home / "sessions/2026/11/24"
        self.day.mkdir(parents=True)
        self.parent_id = "00000000-0000-0000-0000-000000000001"
        self.child_id = "00000000-0000-0000-0000-000000000002"
        self.start = {"docs": ["P009@r1"], "id": "unit", "parent": "implement", "slice": "S1", "conversation": self.parent_id,
                      "at": self.time(0)}
        self.row = {"commit": "a" * 40, "git_commit_time": self.time(13), "child_session": self.child_id,
                    "host_dispatch": "1", "host_receipt": "2", "child_final": "3", "child_complete": "4",
                    "extra_attempts": "0", "result": "contained"}
        args = {"task_name": "p009_s1", "message": "sealed-fixture"}
        self.parent = [self.event(2, {"namespace": "collaboration", "name": "spawn_agent",
                                      "arguments": json.dumps(args)}),
                       self.event(8, {"type": "agent_message", "author": "/root/p009_s1",
                                      "content": [{"text": "Message Type: FINAL_ANSWER\nPayload:\ndone"}]})]
        self.child = [self.meta(self.child_id, "/root/p009_s1"),
                      self.event(4, {"type": "agent_message", "author": "/root",
                                     "content": [{"text": "Message Type: NEW_TASK\nTask name: /root/p009_s1\n"},
                                                 {"encrypted_content": "sealed-fixture"}]}),
                      self.event(6, {"role": "assistant", "phase": "final_answer", "content": [{"text": "done"}]}),
                      self.event(7, {"type": "task_complete", "last_agent_message": "done"}, "event_msg")]

    @staticmethod
    def time(second):
        return f"2026-11-24T08:00:{second:02d}Z"

    def event(self, second, payload, kind="response_item"):
        return {"type": kind, "timestamp": self.time(second), "payload": payload}

    def meta(self, uid, path):
        link = {"agent_path": path, "parent_thread_id": self.parent_id}
        return self.event(3, {"id": uid, "timestamp": self.time(3), "source": {"subagent": {"thread_spawn": link}}},
                          "session_meta")

    def write(self, uid, rows):
        path = self.day / ("rollout-test-" + uid + ".jsonl")
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return path

    def verify(self, trace=()):
        self.write(self.child_id, self.child)
        # The parent's session also occurs in the child's day inventory.
        parent = self.write(self.parent_id, self.parent)
        with patch.object(check, "slice_transition", return_value=check.utc(self.time(13))), patch.object(check, "git"):
            children = check.child_inventory(self.home, self.parent_id)
            check.verify_slice(self.row, self.start, [self.start, *trace], self.home, self.home, parent, children,
                               {"at": self.time(40), "line": 1000, "review_calls": []})

    def test_contained_with_matching_dispatch_envelope(self):
        self.verify()

    def test_child_completion_after_earliest_boundary(self):
        self.child[-1]["timestamp"] = self.time(15)
        with self.assertRaises(check.MissingEvidence):
            self.verify()

    def test_parent_notification_is_not_worker_completion(self):
        self.child.pop()
        with self.assertRaises(check.MissingEvidence):
            self.verify()

    def test_resumed_attempt_and_replacement_are_inventoried(self):
        resume = {"namespace": "collaboration", "name": "followup_task",
                  "arguments": json.dumps({"target": "/root/p009_s1"})}
        self.parent.append(self.event(11, resume))
        with self.assertRaises(check.MissingEvidence):
            self.verify()
        self.parent.pop()
        other = "00000000-0000-0000-0000-000000000003"
        self.write(other, [self.meta(other, "/root/another_worker")])
        with self.assertRaises(check.MissingEvidence):
            self.verify()

    def test_mismatched_delivered_brief(self):
        self.child[1]["payload"]["content"][1]["encrypted_content"] = "different"
        with self.assertRaises(check.MissingEvidence):
            self.verify()

    def test_earlier_sibling_closes_the_slice(self):
        sibling = {"type": "start", "parent": "implement", "at": self.time(5)}
        with self.assertRaises(check.MissingEvidence):
            self.verify([sibling])

    def test_outside_replacement_dispatch_is_inventoried(self):
        for stamp in ("2026-11-24T07:59:59Z", self.time(15)):
            with self.subTest(stamp=stamp):
                replacement = self.event(1, dict(self.parent[0]["payload"]))
                replacement["timestamp"] = stamp
                replacement["payload"]["arguments"] = json.dumps({"task_name": "p009_s1_replacement",
                                                                   "message": "another-brief"})
                self.parent.append(replacement)
                with self.assertRaises(check.MissingEvidence):
                    self.verify()
                self.parent.pop()

    def test_an_empty_or_unrelated_final_cannot_prove_delivery(self):
        for text in ("", "different final"):
            with self.subTest(text=text):
                self.child[-2]["payload"]["content"] = [{"text": text}]
                with self.assertRaises(check.MissingEvidence):
                    self.verify()
        self.child[-2]["payload"]["content"] = [{"text": "done"}]
        self.parent[-1]["payload"]["content"] = [{"text": "Message Type: FINAL_ANSWER\nPayload:\n"}]
        with self.assertRaises(check.MissingEvidence):
            self.verify()

    def test_sibling_in_opening_second_closes_slice_in_event_order(self):
        sibling = {"type": "start", "parent": "implement", "at": self.start["at"]}
        with self.assertRaises(check.MissingEvidence):
            self.verify([sibling])

    def test_next_two_starts_are_counted_from_selection(self):
        sample = dict(type="start", host="codex", kind="slice")
        other, one, two = [dict(sample, id=str(i), at=self.time(i)) for i in (1, 2, 3)]
        check.selected_sequence([one, two], check.utc(self.time(0)), [one, two])
        with self.assertRaises(check.MissingEvidence):
            check.selected_sequence([other, one, two], check.utc(self.time(0)), [one, two])

    def test_complete_check_inventories_an_opaque_replacement_through_observation(self):
        # The audit happens after both commits and may already have a review-start event.
        first, second = dict(self.start, id="unit-one", at=self.time(1)), dict(self.start, id="unit-two",
                             slice="S2", at=self.time(14))
        for start in (first, second):
            start.update(host="codex", kind="slice", type="start")
        second_id = "00000000-0000-0000-0000-000000000003"
        first_row = dict(self.row, unit=first["id"], slice="S1", host_dispatch="2", host_receipt="3")
        second_row = dict(self.row, unit=second["id"], slice="S2", child_session=second_id, host_dispatch="4",
                          host_receipt="5", commit="b" * 40, git_commit_time=self.time(26))
        receipt_path = self.home / "workers.tsv"
        with receipt_path.open("w", newline="") as stream:
            out = csv.DictWriter(stream, fieldnames=first_row, delimiter="\t")
            out.writeheader()
            out.writerows([first_row, second_row])
        trace = self.home / ".canon/canon/trace/events.jsonl"
        trace.parent.mkdir(parents=True)
        self.write(self.child_id, self.child)
        other = json.loads(json.dumps(self.child).replace(self.child_id, second_id).replace("p009_s1", "p009_s2"))
        for record, second_at in zip(other, (17, 18, 20, 21)):
            record["timestamp"] = self.time(second_at)
        other[0]["payload"]["timestamp"] = self.time(17)
        self.write(second_id, other)
        meta = self.event(0, {"id": self.parent_id, "timestamp": self.time(0)}, "session_meta")
        second_parent = json.loads(json.dumps(self.parent).replace("p009_s1", "p009_s2"))
        second_parent[0]["timestamp"], second_parent[1]["timestamp"] = self.time(16), self.time(22)
        normal = [meta, *self.parent, *second_parent]
        marker = "P009@r1 worker audit observation: " + " ".join(r["unit"]+"="+r["commit"]
                                                                  for r in (first_row, second_row))
        checkpoint = self.event(35, {"type": "custom_tool_call_output", "output": marker})
        observe_path = self.home / "observation.json"
        def run(extra, review_started, review_call=None, after=()):
            records = [first, second]
            if review_started:
                records.append({"id": "review-unit", "type": "start", "kind": "code-review", "parent": "implement", "at": self.time(27)})
            if review_call:
                records.append({"type": "end", "id": "review-unit", "at": self.time(34),
                                "dispositions": {"reviewers": [{"role": "spec", "id": review_call["session"]}]}})
            trace.write_text("".join(json.dumps(e) + "\n" for e in records))
            prefix = [*normal, *extra, checkpoint]
            self.write(self.parent_id, [*prefix, *after])
            observed = dict(parent=self.parent_id, line=len(prefix), at=self.time(35),
                            sha256=check.record_hash(json.dumps(checkpoint).encode()),
                            review_calls=[review_call] if review_call else [])
            observe_path.write_text(json.dumps(observed))
            def commit_at(_project, commit, _plan, _slice):
                return check.utc(self.time(13 if commit == first_row["commit"] else 26))
            with patch.object(check, "git", return_value=self.time(0)), patch.object(check, "slice_transition",
                                                                                    side_effect=commit_at):
                check.check(self.home, self.home, receipt_path, observe_path)
        for reviewed in (False, True):
            run([], reviewed)
            extra = deepcopy(second_parent[0])
            extra["timestamp"] = self.time(30)
            extra["payload"]["arguments"] = json.dumps({"task_name": "worker_retry", "message": "opaque-payload"})
            with self.assertRaisesRegex(check.MissingEvidence, "unaccounted dispatch"):
                run([extra], reviewed)
        after = deepcopy(second_parent[0])
        after["timestamp"] = self.time(37)
        after["payload"]["arguments"] = json.dumps({"task_name": "documentation", "message": "Review P009 S2."})
        run([], True, after=[after])
        reviewer = "00000000-0000-0000-0000-000000000005"
        review_meta = self.meta(reviewer, "/root/p009_spec")
        review_meta["timestamp"] = review_meta["payload"]["timestamp"] = self.time(30)
        reviewer_path = self.write(reviewer, [review_meta])
        review = deepcopy(second_parent[0])
        review["timestamp"] = self.time(29)
        review["payload"]["arguments"] = json.dumps({"task_name": "p009_spec", "message": "Review the P009 S2 evidence."})
        allowed = dict(line=len(normal) + 1, sha256=check.record_hash(json.dumps(review).encode()),
                       session=reviewer, review_unit="review-unit", axis="spec")
        run([review], True, review_call=allowed, after=[after])
        reviewer_path.rename(reviewer_path.with_suffix(".saved"))
        third_id = "00000000-0000-0000-0000-000000000004"
        third = self.meta(third_id, "/root/worker_retry")
        third["timestamp"] = third["payload"]["timestamp"] = self.time(31)
        self.write(third_id, [third])
        with self.assertRaisesRegex(check.MissingEvidence, "unaccounted linked child"):
            run([extra], True)


if __name__ == "__main__":
    unittest.main()
