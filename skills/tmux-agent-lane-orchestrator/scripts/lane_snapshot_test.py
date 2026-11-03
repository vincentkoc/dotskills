#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock


def load_helper(skill):
    script = pathlib.Path(__file__).parents[2] / skill / "scripts" / "lane_snapshot.py"
    spec = importlib.util.spec_from_file_location(skill.replace("-", "_"), script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def process(parent, *argv, executable=None):
    return parent, executable or f"/bin/{argv[0]}", list(argv)


def event(timestamp, kind, payload_kind, **payload):
    return {
        "timestamp": timestamp,
        "type": kind,
        "payload": {"type": payload_kind, **payload},
    }


class LaneSnapshotChecks:
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

            records, receipt = self.module.read_log(path, 16_384, None)
            summary = self.module.summarize_records(records)

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

            first_records, first = self.module.read_log(path, 4096, None)
            self.assertEqual(len(first_records), 1)
            self.assertTrue(first["partial_record"])

            path.write_text(complete + "\n" + partial + ',"payload":{"type":"task_complete"}}')
            second_records, second = self.module.read_log(path, 4096, first)
            second_summary = self.module.summarize_records(second_records)
            third_records, third = self.module.read_log(path, 4096, second)

        self.assertEqual(second["mode"], "incremental")
        self.assertEqual(second_summary["state"], "completed")
        self.assertEqual(third_records, [])
        self.assertEqual(third["bytes_read"], 0)
        self.assertEqual(third["mode"], "unchanged")

    def test_large_single_record_stays_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            path.write_text(json.dumps({"type": "event_msg", "payload": {"message": "x" * 2_000_000}}))
            records, receipt = self.module.read_log(path, 8192, None)
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
            records, receipt = self.module.read_log(path, limit, None)
            summary = self.module.summarize_records(records)
            with path.open("a") as handle:
                handle.write(json.dumps(oversized) + "\n" + json.dumps(done) + "\n")

            discarded = False
            for _ in range(5):
                previous_offset = receipt["offset"]
                records, receipt = self.module.read_log(path, limit, receipt)
                self.assertLessEqual(receipt["bytes_read"], limit)
                self.assertGreater(receipt["offset"], previous_offset)
                discarded |= receipt["discarding_record"]
                summary = self.module.summarize_records(records, summary)
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
            records, receipt = self.module.read_log(path, 512, None)
            self.module.save_cursor(cursor_path, {"version": 1, "files": {str(path): receipt}}, 1)
            receipt = self.module.load_cursor(cursor_path)["files"][str(path)]
            self.assertEqual(records, [])
            self.assertTrue(receipt["discarding_record"])

            records, receipt = self.module.read_log(path, 512, receipt)
            self.assertEqual(records, [])
            self.assertEqual(receipt["bytes_read"], 0)
            self.assertTrue(receipt["discarding_record"])
            with path.open("a") as handle:
                handle.write('more text"}')
            records, receipt = self.module.read_log(path, 512, receipt)
            self.assertEqual(records, [])
            self.assertTrue(receipt["discarding_record"])

            done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete")
            with path.open("a") as handle:
                handle.write("\n" + json.dumps(done) + "\n")
            records, receipt = self.module.read_log(path, 512, receipt)
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
            _, receipt = self.module.read_log(path, limit, None)
            path.write_bytes(prefix_bytes + message_bytes)
            first, receipt = self.module.read_log(path, limit, receipt)
            self.assertEqual(first, [prefix])
            self.assertTrue(receipt["partial_record"])
            self.assertFalse(receipt["discarding_record"])
            second, receipt = self.module.read_log(path, limit, receipt)
        self.assertEqual(second, [message])
        self.assertFalse(receipt["partial_record"])

    def test_complete_record_at_budget_boundary_is_not_discarded(self):
        done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete")
        data = json.dumps(done).encode()
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            path.write_bytes(b"")
            _, receipt = self.module.read_log(path, len(data), None)
            path.write_bytes(data + b"\n")
            records, receipt = self.module.read_log(path, len(data), receipt)
        self.assertEqual(records, [done])
        self.assertFalse(receipt["discarding_record"])

    def test_exhausted_budget_preserves_incremental_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rollout.jsonl"
            path.write_bytes(b"")
            _, receipt = self.module.read_log(path, 512, None)
            done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete")
            path.write_text(json.dumps(done) + "\n")
            _, empty = self.module.read_log(path, 0, None)
            records, first = self.module.read_log(path, 512, empty)
            self.assertEqual(records, [done])
            self.assertEqual(first["mode"], "tail")
            records, receipt = self.module.read_log(path, 0, receipt)
            self.assertEqual(records, [])
            self.assertEqual(receipt["offset"], 0)
            records, receipt = self.module.read_log(path, 512, receipt)
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
                _, cursor["files"][str(path)] = self.module.read_log(path, 512, None)
                pane = f"L1.{index}"
                panes.append({"pane": pane, "pane_id": f"%{index}", "pid": "0", "cwd": "", "title": ""})
                identities[pane] = {"status": "exact", "rollout_path": str(path)}
            self.module.save_cursor(cursor_path, cursor, 2)
            first_data = json.dumps(event("2026-09-08T00:00:00Z", "event_msg", "token_count")) + "\n"
            paths[0].write_text(first_data)
            paths[1].write_text(json.dumps(event("2026-09-08T00:01:00Z", "event_msg", "task_complete")) + "\n")
            args = self.module.build_parser().parse_args([
                "--session", "test", "--lane", "1", "--cursor-file", str(cursor_path),
                "--log-bytes", "512", "--total-log-bytes", str(len(first_data.encode()) + 10),
            ])
            with (
                mock.patch.object(self.module, "list_lane_panes", return_value=panes),
                mock.patch.object(self.module, "process_table", return_value={}),
                mock.patch.object(self.module, "find_state_database", return_value=None),
                mock.patch.object(self.module, "capture_pane", return_value=""),
                mock.patch.object(self.module, "resolve_pane_identity", side_effect=lambda pane, *_: identities[pane["pane"]]),
            ):
                first, cursor = self.module.build_snapshot(args)
                self.assertEqual(first["panes"][1]["log"]["bytes_read"], 10)
                self.assertFalse(first["panes"][1]["log"]["discarding_record"])
                self.assertEqual(cursor["files"][str(paths[1])]["offset"], 0)
                self.module.save_cursor(cursor_path, cursor, 2)
                second, cursor = self.module.build_snapshot(args)
                self.assertEqual(second["panes"][1]["state"], "completed")
                self.assertLess(args.total_log_bytes, args.log_bytes)
                with paths[1].open("a") as handle:
                    handle.write(json.dumps({"type": "compacted", "payload": {"message": "x" * 300}}) + "\n")
                    handle.write(json.dumps(event("2026-09-08T00:02:00Z", "event_msg", "task_complete")) + "\n")
                for _ in range(5):
                    previous_offset = cursor["files"][str(paths[1])]["offset"]
                    self.module.save_cursor(cursor_path, cursor, 2)
                    second, cursor = self.module.build_snapshot(args)
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
            _, receipt = self.module.read_log(path, limit, None)
            done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete")
            path.write_bytes(b"x" * (limit * 2 - 1) + b"\n" + json.dumps(done).encode())
            _, receipt = self.module.read_log(path, limit, receipt)
            self.assertTrue(receipt["discarding_record"])
            records, receipt = self.module.read_log(path, limit, receipt)
            self.assertEqual(records, [])
            self.assertFalse(receipt["discarding_record"])
            records, receipt = self.module.read_log(path, limit, receipt)
        self.assertEqual(records, [done])

    def test_rotation_and_truncation_reset_discard_state(self):
        for rotate in (True, False):
            with self.subTest(rotate=rotate), tempfile.TemporaryDirectory() as directory:
                path = pathlib.Path(directory) / "rollout.jsonl"
                path.write_bytes(b"x" * 1024)
                _, receipt = self.module.read_log(path, 256, None)
                self.assertTrue(receipt["discarding_record"])
                if rotate:
                    path.replace(path.with_suffix(".old"))
                done = event("2026-09-08T00:01:00Z", "event_msg", "task_complete")
                path.write_text(json.dumps(done))
                records, receipt = self.module.read_log(path, 256, receipt)
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
            _records, first = self.module.read_log(path, 512, None)
            path.replace(path.with_suffix(".old"))
            path.write_text(
                json.dumps(event("2026-09-08T00:01:00Z", "event_msg", "task_complete"))
            )
            records, rotated = self.module.read_log(path, 512, first)
        self.assertEqual(rotated["mode"], "tail")
        self.assertLessEqual(rotated["bytes_read"], 512)
        self.assertEqual(self.module.summarize_records(records)["state"], "completed")

    def test_process_identity_does_not_fall_back_to_cwd_or_keywords(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        processes = {
            10: process(1, "zsh"),
            11: process(10, "codex", "resume", thread_id),
            20: process(1, "zsh"),
            21: process(20, "codex", "exec", "unrelated CI failure"),
        }
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10"}
        rows = {thread_id: {"id": thread_id, "rollout_path": "/tmp/exact.jsonl"}}
        exact = self.module.resolve_pane_identity(pane, processes, {}, rows)
        unrelated = self.module.resolve_pane_identity({**pane, "pid": "20"}, processes, {}, rows)
        self.assertEqual(exact["status"], "exact")
        self.assertEqual(exact["agent_pid"], 11)
        self.assertEqual(unrelated["status"], "unknown")
        self.assertEqual(unrelated["reason"], "thread-binding-required")

    def test_conflicting_threads_are_unknown(self):
        first = "0199abcd-1234-5678-9abc-0123456789ab"
        second = "0199abcd-1234-5678-9abc-0123456789ac"
        processes = {
            10: process(1, "zsh"),
            11: process(10, "codex", "resume", first),
            12: process(10, "codex", "resume", second),
        }
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10"}
        identity = self.module.resolve_pane_identity(pane, processes, {}, {})
        self.assertEqual(identity["status"], "unknown")
        self.assertEqual(identity["reason"], "ambiguous")

    def test_explicit_thread_still_requires_one_exact_agent_pid(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10"}
        rows = {thread_id: {"id": thread_id, "rollout_path": "/tmp/exact.jsonl"}}
        missing = self.module.resolve_pane_identity(pane, {10: process(1, "zsh")}, {"L1.1": thread_id}, rows)
        exact = self.module.resolve_pane_identity(
            pane,
            {10: process(1, "zsh"), 11: process(10, "codex")},
            {"L1.1": thread_id},
            rows,
        )
        self.assertEqual(missing["reason"], "agent-pid-unproven")
        self.assertEqual(exact["status"], "exact")
        self.assertEqual(exact["agent_pid"], 11)

    def test_flat_command_collision_preserves_structured_argument_boundaries(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        fresh = ["codex", f"resume {thread_id}"]
        resume = ["codex", "resume", thread_id]
        self.assertEqual(" ".join(fresh), " ".join(resume))
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10"}
        rows = {thread_id: {"rollout_path": "/tmp/exact.jsonl"}}
        for argv, state in ((fresh, "unknown"), (resume, "exact")):
            with self.subTest(argv=argv):
                processes = {10: process(1, "zsh"), 11: process(10, *argv)}
                self.assertEqual(self.module.resolve_pane_identity(pane, processes, {}, rows)["status"], state)

    def test_only_minimal_structured_resume_forms_infer_thread(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        cases = [
            (["codex", "resume", thread_id], "/bin/codex", True),
            (["codex", "exec", "resume", thread_id], "/bin/codex", True),
            (["codex", "please inspect", thread_id], "/bin/codex", False),
            (["codex", "fork", thread_id], "/bin/codex", False),
            (["codex", "exec", thread_id], "/bin/codex", False),
            (["codex", "resume", "--last", thread_id], "/bin/codex", False),
            (["codex", "exec", "resume", "--last", thread_id], "/bin/codex", False),
            (["codex", "resume", thread_id, "--last"], "/bin/codex", False),
            (["codex", "resume", thread_id, "a prompt"], "/bin/codex", False),
            (["codex", "resume", thread_id], "/bin/python", False),
            (["python", "script.py", "codex", "resume", thread_id], "/bin/python", False),
            (["codex", "resume", thread_id], "", False),
            (["codex", "resume", thread_id], "/bin/my-codex-wrapper", False),
            ([], "/bin/codex", False),
        ]
        for argv, executable, matches in cases:
            with self.subTest(argv=argv, executable=executable):
                processes = {10: process(1, "zsh"), 11: (10, executable, argv)}
                candidates = self.module.thread_candidates(10, processes)
                self.assertEqual(bool(candidates), matches)
                if matches:
                    self.assertEqual(candidates, [{"pid": 11, "thread_id": thread_id}])

    def test_path_only_process_requires_verified_binding(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10"}
        rows = {thread_id: {"rollout_path": "/tmp/exact.jsonl"}}
        processes = {10: process(1, "zsh"), 11: (10, "/bin/codex", None)}
        unknown = self.module.resolve_pane_identity(pane, processes, {}, rows)
        self.assertEqual(unknown["status"], "unknown")
        self.assertEqual(unknown["agent_pid"], 11)
        self.assertIn("--thread L1.1=THREAD_ID", unknown["next_action"])
        exact = self.module.resolve_pane_identity(pane, processes, {"L1.1": thread_id}, rows)
        self.assertEqual(exact["status"], "exact")
        self.assertEqual(exact["reason"], "explicit")

    def test_explicit_binding_cannot_select_unproven_or_conflicting_process(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        other = "0199abcd-1234-5678-9abc-0123456789ac"
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10"}
        rows = {thread_id: {"rollout_path": "/tmp/exact.jsonl"}}
        for child in (process(10, "python", "codex", thread_id), process(10, "codex", "resume", other)):
            processes = {10: process(1, "zsh"), 11: child}
            self.assertEqual(self.module.resolve_pane_identity(pane, processes, {"L1.1": thread_id}, rows)["status"], "unknown")

    def test_additional_unresolved_codex_process_prevents_inference(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10"}
        rows = {thread_id: {"rollout_path": "/tmp/exact.jsonl"}}
        processes = {10: process(1, "zsh"), 11: process(10, "codex", "resume", thread_id), 12: process(10, "codex")}
        self.assertEqual(self.module.resolve_pane_identity(pane, processes, {}, rows)["status"], "unknown")

    def test_explicit_pane_thread_binding_never_selects_between_agent_pids(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10", "cwd": "/tmp/shared", "title": "", "active": "no", "command": "codex"}
        args = self.module.build_parser().parse_args(["--session", "test", "--lane", "1", "--thread", f"L1.1={thread_id}"])
        rows = {thread_id: {"rollout_path": "/tmp/exact.jsonl"}}
        for second in ((10, "/bin/codex", None), process(10, "codex", "resume", thread_id)):
            processes = {10: process(1, "zsh"), 11: process(10, "codex", "resume", thread_id), 12: second}
            with self.subTest(second=second):
                identity = self.module.resolve_pane_identity(pane, processes, {"L1.1": thread_id}, rows)
                self.assertEqual(identity["status"], "unknown")
                self.assertEqual(identity["reason"], "agent-pid-ambiguous")
                self.assertIsNone(identity["agent_pid"])
                with (
                    mock.patch.object(self.module, "list_lane_panes", return_value=[pane]),
                    mock.patch.object(self.module, "process_table", return_value=processes),
                    mock.patch.object(self.module, "capture_pane", return_value=""),
                    mock.patch.object(self.module, "find_state_database", return_value=None),
                    mock.patch.object(self.module, "lookup_threads", return_value=rows),
                    mock.patch.object(self.module, "read_log") as read,
                ):
                    snapshot, _cursor = self.module.build_snapshot(args)
                read.assert_not_called()
                self.assertEqual(snapshot["panes"][0]["state"], "unknown")
                self.assertEqual(snapshot["io"]["bytes_read"], 0)

    def test_process_observation_scopes_native_reads_and_never_scans_flat_argv(self):
        with (
            mock.patch.object(self.module, "run_command", return_value="10 1\n11 10\n12 10\n20 1\n21 20") as ps,
            mock.patch.object(self.module, "process_executable", side_effect=lambda pid: {11: "/bin/codex", 12: "/bin/python"}[pid]) as executable,
            mock.patch.object(self.module, "process_argv", return_value=["codex"]) as argv,
        ):
            processes = self.module.process_table([10])
        ps.assert_called_once_with(["ps", "-axo", "pid=,ppid="])
        self.assertEqual({call.args[0] for call in executable.call_args_list}, {11, 12})
        argv.assert_called_once_with(11)
        self.assertEqual(processes[21], (20, "", None))

    def test_linux_argv_read_is_nul_delimited_and_bounded(self):
        for data, expected in ((b"codex\0resume\0thread\0", ["codex", "resume", "thread"]), (b"", None), (b"codex", None), (b"x" * 65_536, None)):
            with self.subTest(size=len(data)), mock.patch.object(self.module.sys, "platform", "linux"):
                handle = mock.mock_open(read_data=data)
                with mock.patch.object(self.module.Path, "open", handle):
                    self.assertEqual(self.module.process_argv(11), expected)
                handle().read.assert_called_once_with(65_536)
        with mock.patch.object(self.module.sys, "platform", "linux"), mock.patch.object(self.module.Path, "open", side_effect=PermissionError):
            self.assertIsNone(self.module.process_argv(11))

    def test_unknown_thread_never_reads_an_unrelated_rollout(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10", "cwd": "/tmp/shared", "title": "failed", "active": "no", "command": "codex"}
        processes = {10: process(1, "zsh"), 11: process(10, "codex", thread_id)}
        args = self.module.build_parser().parse_args(["--session", "test", "--lane", "1"])
        with (
            mock.patch.object(self.module, "list_lane_panes", return_value=[pane]),
            mock.patch.object(self.module, "process_table", return_value=processes),
            mock.patch.object(self.module, "capture_pane", return_value="old error"),
            mock.patch.object(self.module, "find_state_database", return_value=None),
            mock.patch.object(self.module, "lookup_threads", return_value={thread_id: {"rollout_path": "/tmp/unrelated.jsonl"}}),
            mock.patch.object(self.module, "read_log") as read,
        ):
            snapshot, _cursor = self.module.build_snapshot(args)
        read.assert_not_called()
        self.assertEqual(snapshot["panes"][0]["state"], "unknown")
        self.assertEqual(snapshot["io"]["bytes_read"], 0)
        self.assertIn("--thread L1.1=THREAD_ID", self.module.render_text(snapshot, False))

    def test_darwin_never_reads_argv_or_environment(self):
        with mock.patch.object(self.module.sys, "platform", "darwin"), mock.patch.object(self.module.Path, "open") as opened:
            self.assertIsNone(self.module.process_argv(11))
        opened.assert_not_called()

    def test_darwin_executable_api_is_path_only_and_bounded(self):
        def pidpath(pid, buffer, size):
            self.assertEqual(pid, 11)
            self.assertEqual(size, 4096)
            buffer.value = b"/bin/codex"
            return len(buffer.value)
        library = mock.Mock()
        library.proc_pidpath.side_effect = pidpath
        with mock.patch.object(self.module.sys, "platform", "darwin"), mock.patch.object(self.module.ctypes, "CDLL", return_value=library) as loaded:
            self.assertEqual(self.module.process_executable(11), "/bin/codex")
            loaded.assert_called_once_with("/usr/lib/libproc.dylib")
            library.proc_pidpath.side_effect = None
            for length in (0, 4096):
                library.proc_pidpath.return_value = length
                self.assertEqual(self.module.process_executable(11), "")
        with mock.patch.object(self.module.sys, "platform", "darwin"), mock.patch.object(self.module.ctypes, "CDLL", side_effect=OSError):
            self.assertEqual(self.module.process_executable(11), "")

    def test_current_fixture_process_executable_matches_python(self):
        import os
        import sys

        if sys.platform not in {"darwin", "linux"}:
            self.skipTest("native executable API unavailable")
        executable = self.module.process_executable(os.getpid())
        self.assertTrue(executable)
        expected = (
            self.module.run_command(["ps", "-ww", "-p", str(os.getpid()), "-o", "comm="])
            if sys.platform == "darwin" else sys.executable
        )
        self.assertTrue(os.path.samefile(executable, expected))

    def test_new_progress_overrides_earlier_same_turn_error(self):
        records = [
            event("2026-09-08T00:00:00Z", "event_msg", "task_started", id="turn-1"),
            event("2026-09-08T00:00:01Z", "event_msg", "stream_error"),
            event("2026-09-08T00:00:02Z", "event_msg", "agent_message", message="recovered"),
        ]
        self.assertEqual(self.module.summarize_records(records)["state"], "active-progress")

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
        summary = self.module.summarize_records(records, previous)
        self.assertEqual(summary["state"], "active-progress")
        self.assertEqual(summary["turn_id"], "turn-1")
        self.assertEqual(summary["latest"], "still working")
        self.assertEqual(summary["events"], 5)
        self.assertEqual(summary["token_updates"], 2)

    def test_same_thread_in_two_processes_is_unknown(self):
        thread_id = "0199abcd-1234-5678-9abc-0123456789ab"
        pane = {"pane": "L1.1", "pane_id": "%1", "pid": "10"}
        processes = {
            10: process(1, "zsh"),
            11: process(10, "codex", "resume", thread_id),
            12: process(10, "codex", "resume", thread_id),
        }
        rows = {thread_id: {"rollout_path": "/tmp/exact.jsonl"}}
        identity = self.module.resolve_pane_identity(pane, processes, {}, rows)
        self.assertEqual(identity["status"], "unknown")
        self.assertIsNone(identity["agent_pid"])

    def test_new_turn_resets_previous_failure_and_counters(self):
        records = [
            event("2026-09-08T00:00:00Z", "event_msg", "task_started", turn_id="old"),
            event("2026-09-08T00:00:01Z", "response_item", "function_call", name="exec_command"),
            event("2026-09-08T00:00:02Z", "event_msg", "turn_aborted", turn_id="old"),
            event("2026-09-08T00:00:03Z", "event_msg", "task_started", turn_id="new"),
            event("2026-09-08T00:00:04Z", "event_msg", "task_complete", turn_id="new"),
        ]
        summary = self.module.summarize_records(records)
        self.assertEqual(summary["state"], "completed")
        self.assertEqual(summary["turn_id"], "new")
        self.assertEqual(summary["tool_calls"], 0)
        self.assertEqual(summary["events"], 2)

    def test_packaged_helper_runs_without_sibling_skill(self):
        import shutil
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as directory:
            script = pathlib.Path(directory) / "scripts" / "lane_snapshot.py"
            script.parent.mkdir()
            shutil.copyfile(self.module.__file__, script)
            result = subprocess.run(
                [sys.executable, str(script), "--help"], cwd=directory,
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--total-log-bytes", result.stdout)
        self.assertNotIn("--keywords", result.stdout)

    def test_default_activity_projection_redacts_latest_message(self):
        latest = f"path={pathlib.Path.home()}/private token=secret-value"
        projected = self.module.project_activity({"state": "active-progress", "latest": latest}, False)
        self.assertNotIn(str(pathlib.Path.home()), projected["latest"])
        self.assertNotIn("secret-value", projected["latest"])
        self.assertIn("<redacted-secret>", projected["latest"])


class ObserverLaneSnapshotTest(LaneSnapshotChecks, unittest.TestCase):
    module = load_helper("tmux-agent-lane-orchestrator")

    def test_infers_worker_lane(self):
        with mock.patch.object(self.module, "run_tmux", return_value="test\tL2\t1"):
            self.assertEqual(self.module.infer_lane()[0], 2)
        with mock.patch.object(self.module, "run_tmux", return_value="test\tops\t3"):
            self.assertIsNone(self.module.infer_lane()[0])


class ManagerLaneSnapshotTest(LaneSnapshotChecks, unittest.TestCase):
    module = load_helper("tmux-lane-orchestrator")

    def test_infers_only_assigned_odd_ops_panes(self):
        for pane, expected in (("1", 1), ("3", 2), ("5", 3), ("2", None), ("7", None)):
            with self.subTest(pane=pane), mock.patch.object(
                self.module, "run_tmux", return_value=f"test\tops\t{pane}"
            ):
                self.assertEqual(self.module.infer_lane()[0], expected)
        with mock.patch.object(self.module, "run_tmux", return_value="test\tL2\t1"):
            self.assertIsNone(self.module.infer_lane()[0])


if __name__ == "__main__":
    unittest.main()
