#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "codex-goal-report.py"
SPEC = importlib.util.spec_from_file_location("codex_goal_report", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def write_session(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for event in events:
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")


def goal_event(
    timestamp,
    objective,
    status,
    seconds,
    tokens,
    updated_at,
    created_at=1780272000,
    thread_id="thread-1",
):
    return {
        "timestamp": timestamp,
        "type": "event_msg",
        "payload": {
            "type": "thread_goal_updated",
            "threadId": thread_id,
            "goal": {
                "threadId": thread_id,
                "objective": objective,
                "status": status,
                "tokensUsed": tokens,
                "timeUsedSeconds": seconds,
                "createdAt": created_at,
                "updatedAt": updated_at,
            },
        },
    }


class CodexGoalReportTest(unittest.TestCase):
    def test_reads_generic_fleet_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = pathlib.Path(directory) / "fleet-policy.json"
            policy.write_text(json.dumps({"systems": {
                "laptop": {"ssh_target": None},
                "desktop": {"ssh_target": "desktop-alias", "wsl_target": "desktop-wsl-alias"},
            }}))
            targets = MODULE.fleet_targets(policy)
        self.assertEqual([target["machine"] for target in targets], ["laptop", "desktop", "desktop/wsl"])

    def test_collects_latest_snapshot_and_session_span(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            write_session(
                root / "first.jsonl",
                [
                    {"timestamp": "2026-06-01T00:00:00Z", "type": "session_meta", "payload": {}},
                    goal_event("2026-06-01T00:01:00Z", "Retest beta", "active", 60, 1000, 1780272060),
                    {"timestamp": "2026-06-01T00:10:00Z", "type": "event_msg", "payload": {"type": "done"}},
                ],
            )
            write_session(
                root / "resume.jsonl",
                [
                    {"timestamp": "2026-06-01T01:00:00Z", "type": "session_meta", "payload": {}},
                    goal_event("2026-06-01T01:01:00Z", "Retest beta", "complete", 180, 5000, 1780275660),
                    {"timestamp": "2026-06-01T01:05:00Z", "type": "event_msg", "payload": {"type": "done"}},
                ],
            )

            report = MODULE.collect_local_goals("test-mac", root)

        self.assertEqual(len(report["goals"]), 1)
        goal = report["goals"][0]
        self.assertEqual(goal["status"], "complete")
        self.assertEqual(goal["goal_time_seconds"], 180)
        self.assertEqual(goal["tokens_used"], 5000)
        self.assertEqual(goal["session_span_seconds"], 3900)
        self.assertEqual(len(goal["source_files"]), 2)

    def test_since_filters_old_goals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            write_session(root / "session.jsonl", [goal_event("2026-06-01T00:01:00Z", "Old goal", "complete", 10, 20, 1780272060)])
            report = MODULE.collect_local_goals("test-mac", root, MODULE.parse_since("2026-07-01"))
        self.assertEqual(report["goals"], [])

    def test_activity_window_includes_old_goal_resumed_inside_exact_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            write_session(
                root / "resume.jsonl",
                [
                    goal_event(
                        "2026-09-08T04:15:59Z",
                        "Old resumed goal",
                        "active",
                        20,
                        40,
                        1788840959,
                    ),
                    goal_event(
                        "2026-09-08T04:16:03Z",
                        "Boundary excluded",
                        "complete",
                        30,
                        50,
                        1788840963,
                        thread_id="thread-2",
                    ),
                ],
            )
            report = MODULE.collect_local_goals(
                "test-mac",
                root,
                MODULE.parse_bound("2026-09-08T04:00:00Z"),
                MODULE.parse_bound("2026-09-08T04:16:03Z"),
                True,
            )
        self.assertEqual([goal["objective"] for goal in report["goals"]], ["Old resumed goal"])
        self.assertEqual(report["selection_mode"], "activity")

    def test_sqlite_reports_child_identity_without_changing_lifetime_counters(self):
        with tempfile.TemporaryDirectory() as directory:
            codex_home = pathlib.Path(directory)
            goals = sqlite3.connect(codex_home / "goals_1.sqlite")
            goals.execute(
                "CREATE TABLE thread_goals "
                "(thread_id TEXT, goal_id TEXT, objective TEXT, status TEXT, tokens_used INTEGER, "
                "time_used_seconds INTEGER, created_at_ms INTEGER, updated_at_ms INTEGER)"
            )
            goals.execute(
                "INSERT INTO thread_goals VALUES (?,?,?,?,?,?,?,?)",
                ("child-1", "goal-1", "Child work", "complete", 100, 10, 1780272000000, 1788840900000),
            )
            goals.commit()
            goals.close()
            state = sqlite3.connect(codex_home / "state_5.sqlite")
            state.execute(
                "CREATE TABLE threads "
                "(id TEXT, rollout_path TEXT, created_at INTEGER, updated_at INTEGER, "
                "created_at_ms INTEGER, updated_at_ms INTEGER, source TEXT, thread_source TEXT)"
            )
            state.execute(
                "INSERT INTO threads VALUES (?,?,?,?,?,?,?,?)",
                (
                    "child-1",
                    "/tmp/child.jsonl",
                    0,
                    0,
                    1780272000000,
                    1788840900000,
                    '{"subagent":{"thread_spawn":{"parent_thread_id":"root-1"}}}',
                    "subagent",
                ),
            )
            state.commit()
            state.close()
            report = MODULE.collect_sqlite_goals(
                "test-mac",
                codex_home,
                MODULE.parse_bound("2026-09-08T00:00:00Z"),
                MODULE.parse_bound("2026-09-09T00:00:00Z"),
                True,
            )
        goal = report["goals"][0]
        self.assertEqual(goal["thread_role"], "child")
        self.assertEqual(goal["parent_thread_id"], "root-1")
        self.assertEqual(goal["counter_scope"], "lifetime_snapshot")

    def test_counter_cursor_reports_deltas_and_resets(self):
        with tempfile.TemporaryDirectory() as directory:
            cursor = pathlib.Path(directory) / "cursor.json"
            report = {"machines": [{"machine": "one", "goals": [{
                "machine": "one",
                "thread_id": "thread-1",
                "tokens_used": 100,
                "goal_time_seconds": 20,
            }]}]}
            MODULE.apply_counter_cursor(report, cursor, 10)
            self.assertIsNone(report["machines"][0]["goals"][0]["counter_delta"]["tokens"])

            report["machines"][0]["goals"][0].update(tokens_used=140, goal_time_seconds=5)
            MODULE.apply_counter_cursor(report, cursor, 10)
            delta = report["machines"][0]["goals"][0]["counter_delta"]
        self.assertEqual(delta["tokens"], 40)
        self.assertTrue(delta["goal_time_reset"])
        self.assertIsNone(delta["goal_time_seconds"])

    def test_partial_fleet_coverage_exits_nonzero_after_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = pathlib.Path(directory) / "policy.json"
            policy.write_text('{"systems":{}}')
            payload = {
                "generated_at": "2026-09-08T00:00:00Z",
                "machines": [{"machine": "offline", "error": "timed out", "goals": []}],
            }
            with mock.patch.object(MODULE, "collect_fleet", return_value=payload):
                with mock.patch.object(sys, "argv", [
                    "codex-goal-report.py",
                    "--fleet",
                    "--policy",
                    str(policy),
                    "--json",
                ]):
                    with mock.patch.object(sys, "stdout"):
                        status = MODULE.main()
        self.assertEqual(status, 2)

    def test_markdown_surfaces_repeated_goals_and_failures(self):
        goal = {
            "machine": "one",
            "thread_id": "thread-1",
            "objective": "Retest beta",
            "status": "complete",
            "tokens_used": 100,
            "goal_time_seconds": 60,
            "created_at": "2026-06-01T00:00:00Z",
            "session_span_seconds": 120,
        }
        report = {
            "generated_at": "2026-07-28T00:00:00Z",
            "machines": [
                {"machine": "one", "goals": [goal]},
                {"machine": "two", "goals": [{**goal, "machine": "two", "thread_id": "thread-2"}]},
                {"machine": "offline", "error": "connection timed out", "goals": []},
            ],
        }
        output = MODULE.markdown_report(report)
        self.assertIn("**2 runs** — retest beta", output)
        self.assertIn("**offline**: connection timed out", output)
        self.assertIn("Lifetime goal-time snapshots: 2m", output)


if __name__ == "__main__":
    unittest.main()
