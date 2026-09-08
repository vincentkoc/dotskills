#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).with_name("lane_snapshot.py")
SPEC = importlib.util.spec_from_file_location("lane_snapshot", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def event(timestamp, kind, payload_kind, **payload):
    return {
        "timestamp": timestamp,
        "type": kind,
        "payload": {"type": payload_kind, **payload},
    }


class LaneSnapshotTest(unittest.TestCase):
    def test_tail_read_is_bounded_and_uses_newest_turn(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            old = event("2026-09-01T00:00:00Z", "event_msg", "error", message="old failure")
            started = event("2026-09-08T00:00:00Z", "event_msg", "task_started", id="turn-2")
            done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete", message="done")
            with path.open("wb") as handle:
                for _ in range(100_000):
                    handle.write(json.dumps(old).encode() + b"\n")
                handle.write(json.dumps(started).encode() + b"\n")
                handle.write(json.dumps(done).encode())

            records, receipt = MODULE.read_log(path, 16_384, None)
            summary = MODULE.summarize_records(records)

        self.assertLessEqual(receipt["bytes_read"], 16_384)
        self.assertTrue(receipt["truncated"])
        self.assertEqual(summary["turn_id"], "turn-2")
        self.assertEqual(summary["state"], "completed")

    def test_cursor_skips_unchanged_bytes_and_handles_partial_append(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            complete = json.dumps(event("2026-09-08T00:00:00Z", "event_msg", "task_started", id="turn-1"))
            partial = '{"timestamp":"2026-09-08T00:01:00Z","type":"event_msg"'
            path.write_text(complete + "\n" + partial)

            first_records, first = MODULE.read_log(path, 4096, None)
            self.assertEqual(len(first_records), 1)
            self.assertTrue(first["partial_record"])

            path.write_text(complete + "\n" + partial + ',"payload":{"type":"task_complete"}}')
            second_records, second = MODULE.read_log(path, 4096, first)
            second_summary = MODULE.summarize_records(second_records)
            third_records, third = MODULE.read_log(path, 4096, second)

        self.assertEqual(second["mode"], "incremental")
        self.assertEqual(second_summary["state"], "completed")
        self.assertEqual(third_records, [])
        self.assertEqual(third["bytes_read"], 0)
        self.assertEqual(third["mode"], "unchanged")

    def test_large_single_record_stays_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            path.write_text(json.dumps({"type": "event_msg", "payload": {"message": "x" * 2_000_000}}))
            records, receipt = MODULE.read_log(path, 8192, None)
        self.assertEqual(records, [])
        self.assertEqual(receipt["bytes_read"], 8192)
        self.assertTrue(receipt["partial_record"])

    def test_rotation_and_unicode_tail_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            path.write_text(
                "\n".join(
                    json.dumps({"type": "event_msg", "payload": {"message": "snowman \u2603"}})
                    for _ in range(100)
                )
            )
            _records, first = MODULE.read_log(path, 512, None)
            path.replace(path.with_suffix(".old"))
            path.write_text(
                json.dumps(event("2026-09-08T00:01:00Z", "event_msg", "task_complete"))
            )
            records, rotated = MODULE.read_log(path, 512, first)
        self.assertEqual(rotated["mode"], "tail")
        self.assertLessEqual(rotated["bytes_read"], 512)
        self.assertEqual(MODULE.summarize_records(records)["state"], "completed")

    def test_process_identity_does_not_fall_back_to_cwd_or_keywords(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        processes = {
            10: (1, "zsh"),
            11: (10, f"codex resume {thread_id}"),
            20: (1, "zsh"),
            21: (20, "codex exec unrelated CI failure"),
        }
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10"}
        rows = {thread_id: {"id": thread_id, "rollout_path": "/tmp/exact.jsonl"}}
        exact = MODULE.resolve_pane_identity(pane, processes, {}, rows)
        unrelated = MODULE.resolve_pane_identity({**pane, "pid": "20"}, processes, {}, rows)
        self.assertEqual(exact["status"], "exact")
        self.assertEqual(exact["agent_pid"], 11)
        self.assertEqual(unrelated["status"], "unknown")
        self.assertEqual(unrelated["reason"], "unmatched")

    def test_conflicting_threads_are_unknown(self):
        first = "0199abcd-1234-5678-9abc-0123456789ab"
        second = "0199abcd-1234-5678-9abc-0123456789ac"
        processes = {
            10: (1, "zsh"),
            11: (10, f"codex resume {first}"),
            12: (10, f"codex resume {second}"),
        }
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10"}
        identity = MODULE.resolve_pane_identity(pane, processes, {}, {})
        self.assertEqual(identity["status"], "unknown")
        self.assertEqual(identity["reason"], "ambiguous")

    def test_explicit_thread_still_requires_one_exact_agent_pid(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10"}
        rows = {thread_id: {"id": thread_id, "rollout_path": "/tmp/exact.jsonl"}}
        missing = MODULE.resolve_pane_identity(pane, {10: (1, "zsh")}, {"L1.1": thread_id}, rows)
        exact = MODULE.resolve_pane_identity(
            pane,
            {10: (1, "zsh"), 11: (10, "codex")},
            {"L1.1": thread_id},
            rows,
        )
        self.assertEqual(missing["reason"], "agent-pid-unproven")
        self.assertEqual(exact["status"], "exact")
        self.assertEqual(exact["agent_pid"], 11)

    def test_new_progress_overrides_earlier_same_turn_error(self):
        records = [
            event("2026-09-08T00:00:00Z", "event_msg", "task_started", id="turn-1"),
            event("2026-09-08T00:00:01Z", "event_msg", "stream_error"),
            event("2026-09-08T00:00:02Z", "event_msg", "agent_message", message="recovered"),
        ]
        self.assertEqual(MODULE.summarize_records(records)["state"], "active-progress")


if __name__ == "__main__":
    unittest.main()
