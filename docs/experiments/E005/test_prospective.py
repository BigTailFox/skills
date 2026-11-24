"""Check the preserved Codex parent/child evidence with small redacted records."""

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
                                      "content": [{"text": "Message Type: FINAL_ANSWER\nPayload: done"}]})]
        self.child = [self.meta(self.child_id, "/root/p009_s1"),
                      self.event(4, {"type": "agent_message", "author": "/root",
                                     "content": [{"text": "Message Type: NEW_TASK\nTask name: /root/p009_s1\n"},
                                                 {"encrypted_content": "sealed-fixture"}]}),
                      self.event(6, {"role": "assistant", "phase": "final_answer"}),
                      self.event(7, {"type": "task_complete"}, "event_msg")]

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
        with patch.object(check, "slice_commit", return_value=check.utc(self.time(13))):
            check.verify_slice(self.row, self.start, trace, self.home, self.home, parent)

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


if __name__ == "__main__":
    unittest.main()
