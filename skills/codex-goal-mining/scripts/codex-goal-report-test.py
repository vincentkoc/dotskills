#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import tempfile
import unittest


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


def goal_event(timestamp, objective, status, seconds, tokens, updated_at):
    return {
        "timestamp": timestamp,
        "type": "event_msg",
        "payload": {
            "type": "thread_goal_updated",
            "threadId": "thread-1",
            "goal": {
                "threadId": "thread-1",
                "objective": objective,
                "status": status,
                "tokensUsed": tokens,
                "timeUsedSeconds": seconds,
                "createdAt": 1780272000,
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
        self.assertIn("Total Codex goal time: 2m", output)


if __name__ == "__main__":
    unittest.main()
