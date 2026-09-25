#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock


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

    def test_incremental_cursor_reaches_completion_after_oversized_record(self):
        limit = 262_144
        started = event("2026-09-08T00:00:00Z", "event_msg", "task_started", id="turn-1")
        done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete")
        oversized = {"type": "compacted", "payload": {"message": "x" * (limit * 3)}}
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            path.write_text(json.dumps(started) + "\n")
            records, receipt = MODULE.read_log(path, limit, None)
            summary = MODULE.summarize_records(records)
            with path.open("a") as handle:
                handle.write(json.dumps(oversized) + "\n" + json.dumps(done) + "\n")

            discarded = False
            for _ in range(5):
                previous_offset = receipt["offset"]
                records, receipt = MODULE.read_log(path, limit, receipt)
                self.assertLessEqual(receipt["bytes_read"], limit)
                self.assertGreater(receipt["offset"], previous_offset)
                discarded |= receipt["discarding_record"]
                summary = MODULE.summarize_records(records, summary)
                if receipt["offset"] == path.stat().st_size:
                    break

        self.assertTrue(discarded)
        self.assertFalse(receipt["discarding_record"])
        self.assertEqual(summary["state"], "completed")
        self.assertEqual(summary["turn_id"], "turn-1")
        self.assertEqual(summary["events"], 2)

    def test_discarded_tail_waits_for_newline_across_saved_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            cursor_path = pathlib.Path(directory) / "cursor.json"
            path.write_text('{"message":"' + "x" * 4096)
            records, receipt = MODULE.read_log(path, 512, None)
            MODULE.save_cursor(cursor_path, {"version": 1, "files": {str(path): receipt}}, 1)
            receipt = MODULE.load_cursor(cursor_path)["files"][str(path)]
            self.assertEqual(records, [])
            self.assertTrue(receipt["discarding_record"])

            records, receipt = MODULE.read_log(path, 512, receipt)
            self.assertEqual(records, [])
            self.assertEqual(receipt["bytes_read"], 0)
            self.assertTrue(receipt["discarding_record"])
            with path.open("a") as handle:
                handle.write('more text"}')
            records, receipt = MODULE.read_log(path, 512, receipt)
            self.assertEqual(records, [])
            self.assertTrue(receipt["discarding_record"])

            done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete")
            with path.open("a") as handle:
                handle.write("\n" + json.dumps(done) + "\n")
            records, receipt = MODULE.read_log(path, 512, receipt)
        self.assertEqual(records, [done])
        self.assertFalse(receipt["discarding_record"])

    def test_incremental_partial_utf8_record_is_retried_without_loss(self):
        prefix = event("2026-09-08T00:00:00Z", "event_msg", "token_count")
        message = event("2026-09-08T00:01:00Z", "event_msg", "agent_message", message="snowman ☃")
        prefix_bytes = json.dumps(prefix).encode() + b"\n"
        message_bytes = json.dumps(message, ensure_ascii=False).encode() + b"\n"
        limit = len(prefix_bytes) + message_bytes.index("☃".encode()) + 1
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            path.write_bytes(b"")
            _, receipt = MODULE.read_log(path, limit, None)
            path.write_bytes(prefix_bytes + message_bytes)
            first, receipt = MODULE.read_log(path, limit, receipt)
            self.assertEqual(first, [prefix])
            self.assertTrue(receipt["partial_record"])
            self.assertFalse(receipt["discarding_record"])
            second, receipt = MODULE.read_log(path, limit, receipt)
        self.assertEqual(second, [message])
        self.assertFalse(receipt["partial_record"])

    def test_complete_record_at_budget_boundary_is_not_discarded(self):
        done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete")
        data = json.dumps(done).encode()
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            path.write_bytes(b"")
            _, receipt = MODULE.read_log(path, len(data), None)
            path.write_bytes(data + b"\n")
            records, receipt = MODULE.read_log(path, len(data), receipt)
        self.assertEqual(records, [done])
        self.assertFalse(receipt["discarding_record"])

    def test_exhausted_budget_preserves_incremental_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            path.write_bytes(b"")
            _, receipt = MODULE.read_log(path, 512, None)
            done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete")
            path.write_text(json.dumps(done) + "\n")
            _, empty = MODULE.read_log(path, 0, None)
            records, first = MODULE.read_log(path, 512, empty)
            self.assertEqual(records, [done])
            self.assertEqual(first["mode"], "tail")
            records, receipt = MODULE.read_log(path, 0, receipt)
            self.assertEqual(records, [])
            self.assertEqual(receipt["offset"], 0)
            records, receipt = MODULE.read_log(path, 512, receipt)
        self.assertEqual(records, [done])

    def test_shared_budget_preserves_records_and_bounds_oversized_records(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [pathlib.Path(directory) / f"rollout-{index}.jsonl" for index in range(2)]
            cursor_path = pathlib.Path(directory) / "cursor.json"
            cursor = {"version": 1, "files": {}}
            panes = []
            identities = {}
            for index, path in enumerate(paths):
                path.write_bytes(b"")
                _, cursor["files"][str(path)] = MODULE.read_log(path, 512, None)
                pane = f"L1.{index}"
                panes.append({"pane": pane, "pane_id": f"%{index}", "pid": "0", "cwd": "", "title": ""})
                identities[pane] = {"status": "exact", "rollout_path": str(path)}
            MODULE.save_cursor(cursor_path, cursor, 2)
            first_data = json.dumps(event("2026-09-08T00:00:00Z", "event_msg", "token_count")) + "\n"
            paths[0].write_text(first_data)
            paths[1].write_text(json.dumps(event("2026-09-08T00:01:00Z", "event_msg", "task_complete")) + "\n")
            args = MODULE.build_parser().parse_args([
                "--session", "test", "--lane", "1", "--cursor-file", str(cursor_path),
                "--log-bytes", "512", "--total-log-bytes", str(len(first_data.encode()) + 10),
            ])
            with (
                mock.patch.object(MODULE, "list_lane_panes", return_value=panes),
                mock.patch.object(MODULE, "process_table", return_value={}),
                mock.patch.object(MODULE, "find_state_database", return_value=None),
                mock.patch.object(MODULE, "capture_pane", return_value=""),
                mock.patch.object(MODULE, "resolve_pane_identity", side_effect=lambda pane, *_: identities[pane["pane"]]),
            ):
                first, cursor = MODULE.build_snapshot(args)
                self.assertEqual(first["panes"][1]["log"]["bytes_read"], 10)
                self.assertFalse(first["panes"][1]["log"]["discarding_record"])
                self.assertEqual(cursor["files"][str(paths[1])]["offset"], 0)
                MODULE.save_cursor(cursor_path, cursor, 2)
                second, cursor = MODULE.build_snapshot(args)
                self.assertEqual(second["panes"][1]["state"], "completed")
                self.assertLess(args.total_log_bytes, args.log_bytes)
                with paths[1].open("a") as handle:
                    handle.write(json.dumps({"type": "compacted", "payload": {"message": "x" * 300}}) + "\n")
                    handle.write(json.dumps(event("2026-09-08T00:02:00Z", "event_msg", "task_complete")) + "\n")
                for _ in range(5):
                    previous_offset = cursor["files"][str(paths[1])]["offset"]
                    MODULE.save_cursor(cursor_path, cursor, 2)
                    second, cursor = MODULE.build_snapshot(args)
                    self.assertGreater(cursor["files"][str(paths[1])]["offset"], previous_offset)
                    if cursor["files"][str(paths[1])]["offset"] == paths[1].stat().st_size:
                        break
        self.assertEqual(second["panes"][1]["state"], "completed")
        self.assertEqual(second["panes"][1]["activity"]["events"], 2)

    def test_discarded_record_newline_at_budget_boundary(self):
        limit = 256
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            path.write_bytes(b"")
            _, receipt = MODULE.read_log(path, limit, None)
            done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete")
            path.write_bytes(b"x" * (limit * 2 - 1) + b"\n" + json.dumps(done).encode())
            _, receipt = MODULE.read_log(path, limit, receipt)
            self.assertTrue(receipt["discarding_record"])
            records, receipt = MODULE.read_log(path, limit, receipt)
            self.assertEqual(records, [])
            self.assertFalse(receipt["discarding_record"])
            records, receipt = MODULE.read_log(path, limit, receipt)
        self.assertEqual(records, [done])

    def test_rotation_and_truncation_reset_discard_state(self):
        for rotate in (True, False):
            with self.subTest(rotate=rotate), tempfile.TemporaryDirectory() as directory:
                path = pathlib.Path(directory) / "rollout.jsonl"
                path.write_bytes(b"x" * 1024)
                _, receipt = MODULE.read_log(path, 256, None)
                self.assertTrue(receipt["discarding_record"])
                if rotate:
                    path.replace(path.with_suffix(".old"))
                done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete")
                path.write_text(json.dumps(done))
                records, receipt = MODULE.read_log(path, 256, receipt)
                self.assertEqual(records, [done])
                self.assertFalse(receipt["discarding_record"])

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

    def test_incremental_token_event_preserves_previous_turn_summary(self):
        previous = {
            "state": "active-progress",
            "turn_id": "turn-1",
            "latest_timestamp": "2026-09-08T00:00:01Z",
            "latest": "still working",
            "events": 4,
            "tool_calls": 1,
            "tool_outputs": 1,
            "token_updates": 1,
            "changed": True,
        }
        records = [event("2026-09-08T00:00:02Z", "event_msg", "token_count")]
        summary = MODULE.summarize_records(records, previous)
        self.assertEqual(summary["state"], "active-progress")
        self.assertEqual(summary["turn_id"], "turn-1")
        self.assertEqual(summary["latest"], "still working")
        self.assertEqual(summary["events"], 5)
        self.assertEqual(summary["token_updates"], 2)

    def test_default_activity_projection_redacts_latest_message(self):
        latest = f"path={pathlib.Path.home()}/private token=secret-value"
        projected = MODULE.project_activity({"state": "active-progress", "latest": latest}, False)
        self.assertNotIn(str(pathlib.Path.home()), projected["latest"])
        self.assertNotIn("secret-value", projected["latest"])
        self.assertIn("<redacted-secret>", projected["latest"])


if __name__ == "__main__":
    unittest.main()
