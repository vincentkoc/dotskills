#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import sqlite3
import subprocess
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

    def test_activity_window_excludes_goal_updated_at_upper_bound(self):
        created = MODULE.parse_bound("2026-09-01T00:00:00Z")
        updated = MODULE.parse_bound("2026-09-08T04:16:03Z")
        since = MODULE.parse_bound("2026-09-08T04:00:00Z")
        until = MODULE.parse_bound("2026-09-08T04:16:03Z")
        self.assertFalse(MODULE.in_window(created, updated, since, until, True))

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


class TransportTest(unittest.TestCase):
    def setUp(self):
        self.helper = "/fixture/bin/fleet-credentials"
        self.which = mock.patch.object(MODULE.shutil, "which", return_value=self.helper).start()
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(MODULE, "UNREAPED_HELPERS", []).start()

    def reply(self, registered=False):
        return subprocess.CompletedProcess([], 0, json.dumps({"version": 1, "registered": registered}).encode(), b"")

    def payload(self, machine="desktop"):
        return json.dumps({"machine": machine, "goals": []}).encode()

    def collect(self, **kwargs):
        return MODULE.collect_remote(b"fixture script", "desktop", "desktop-alias", None, None, False, 8, **kwargs)

    def child(self, status=0, data=None):
        child = mock.Mock(pid=12345, returncode=status)
        child.communicate.return_value = (self.payload() if data is None else data, b"private diagnostic")
        return child

    def test_registered_legacy_ssh_uses_helper_once_and_preserves_argv(self):
        child = self.child()
        with mock.patch.object(MODULE.subprocess, "run", return_value=self.reply(True)) as run, \
                mock.patch.object(MODULE.subprocess, "Popen", return_value=child) as spawn:
            result = self.collect(interpreter="'/fixture/Python Runtime/python3' -I")
        self.assertEqual(result["machine"], "desktop")
        run.assert_called_once_with([self.helper, "ssh-target", "desktop-alias"],
                                    stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
        self.assertEqual(spawn.call_args.args[0], [self.helper, "ssh", "desktop-alias", "--",
                         "/fixture/Python Runtime/python3", "-I", "-", "--collect-local", "--machine-name", "desktop", "--json"])
        child.communicate.assert_called_once_with(input=b"fixture script", timeout=180)

    def test_registered_refusal_and_bad_payload_never_fall_back(self):
        for child in (self.child(9), self.child(data=b"not JSON"), self.child(data=b"[]"),
                      self.child(data=b'{"machine":"other","goals":[]}')):
            with self.subTest(child=child), \
                    mock.patch.object(MODULE.subprocess, "run", return_value=self.reply(True)) as run, \
                    mock.patch.object(MODULE.subprocess, "Popen", return_value=child) as spawn:
                result = self.collect()
            self.assertIn("error", result)
            self.assertNotIn("private diagnostic", json.dumps(result))
            self.assertEqual(run.call_count, 1)
            self.assertEqual(spawn.call_count, 1)

    def test_unknown_registration_never_starts_any_transport(self):
        invalid = [
            subprocess.CompletedProcess([], 2, b"", b"unsupported command"),
            subprocess.CompletedProcess([], 0, b'{"version":1,"registered":false}', b"private warning"),
            subprocess.CompletedProcess([], 0, b"x" * 1025, b""),
        ]
        for raw in (b"[]", b"{}", b'{"version":true,"registered":false}',
                    b'{"version":2,"registered":false}', b'{"version":1,"registered":0}',
                    b'{"version":1,"registered":false,"extra":0}',
                    b'{"version":1,"registered":true,"registered":false}', b"\xff"):
            invalid.append(subprocess.CompletedProcess([], 0, raw, b""))
        for reply in invalid:
            with self.subTest(reply=reply), mock.patch.object(MODULE.subprocess, "run", return_value=reply) as run, \
                    mock.patch.object(MODULE.subprocess, "Popen") as spawn:
                result = self.collect()
                self.assertIn("route_lookup", result["error"])
                self.assertNotIn("private warning", json.dumps(result))
                run.assert_called_once()
                spawn.assert_not_called()
        self.which.return_value = None
        with mock.patch.object(MODULE.subprocess, "run") as run:
            self.assertEqual(self.collect()["error"], "route_lookup_unavailable")
            run.assert_not_called()

    def test_lookup_timeout_cancel_and_os_error_never_connect(self):
        for error in (subprocess.TimeoutExpired("query", 5), KeyboardInterrupt(), FileNotFoundError()):
            with self.subTest(error=error), mock.patch.object(MODULE.subprocess, "run", side_effect=error) as run, \
                    mock.patch.object(MODULE.subprocess, "Popen") as spawn:
                result = self.collect()
                self.assertIn("route_lookup", result["error"])
                self.assertEqual(result["stop_fleet"], not isinstance(error, OSError))
                run.assert_called_once()
                spawn.assert_not_called()

    def test_registration_reply_byte_boundary(self):
        raw = self.reply(True).stdout
        for size in (1024, 1025):
            reply = subprocess.CompletedProcess([], 0, raw.ljust(size), b"")
            with self.subTest(size=size), mock.patch.object(MODULE.subprocess, "run", return_value=reply), \
                    mock.patch.object(MODULE.subprocess, "Popen", return_value=self.child()) as spawn:
                result = self.collect()
            if size == 1024:
                self.assertNotIn("error", result)
                spawn.assert_called_once()
            else:
                self.assertEqual(result["error"], "route_lookup_failed")
                spawn.assert_not_called()

    def test_unregistered_native_rechecks_before_each_interpreter(self):
        replies = [self.reply(), subprocess.CompletedProcess([], 127, b"", b"missing interpreter"),
                   self.reply(), subprocess.CompletedProcess([], 0, self.payload(), b"")]
        with mock.patch.object(MODULE.subprocess, "run", side_effect=replies) as run, \
                mock.patch.object(MODULE.subprocess, "Popen") as spawn:
            self.assertEqual(self.collect()["machine"], "desktop")
        self.assertEqual([call.args[0][0] for call in run.call_args_list], [self.helper, "ssh", self.helper, "ssh"])
        self.assertIn("python3 -", run.call_args_list[1].args[0][-1])
        self.assertIn("python -", run.call_args_list[3].args[0][-1])
        spawn.assert_not_called()

    def test_registration_change_switches_to_helper_without_further_native_attempt(self):
        replies = [self.reply(), subprocess.CompletedProcess([], 127, b"", b"missing interpreter"), self.reply(True)]
        with mock.patch.object(MODULE.subprocess, "run", side_effect=replies) as run, \
                mock.patch.object(MODULE.subprocess, "Popen", return_value=self.child()) as spawn:
            self.collect()
        self.assertEqual([call.args[0][0] for call in run.call_args_list], [self.helper, "ssh", self.helper])
        self.assertEqual(spawn.call_args.args[0][4], "python3")

    def test_recheck_failure_stops_before_native_retry(self):
        replies = [self.reply(), subprocess.CompletedProcess([], 127, b"", b"missing interpreter"),
                   subprocess.CompletedProcess([], 1, b"", b"private refusal")]
        with mock.patch.object(MODULE.subprocess, "run", side_effect=replies) as run:
            self.assertEqual(self.collect()["error"], "route_lookup_failed")
        self.assertEqual(run.call_count, 3)

    def test_explicit_helper_ownership_survives_removed_or_renamed_registration(self):
        for reply in (self.reply(False), subprocess.CompletedProcess([], 1, b"", b"private refusal"),
                      subprocess.CompletedProcess([], 0, b"{}", b"")):
            with self.subTest(reply=reply), mock.patch.object(MODULE.subprocess, "run", return_value=reply) as run, \
                    mock.patch.object(MODULE.subprocess, "Popen") as spawn:
                result = self.collect(transport="fleet-credentials")
            self.assertIn("error", result)
            run.assert_called_once()
            spawn.assert_not_called()
        self.which.return_value = None
        with mock.patch.object(MODULE.subprocess, "run") as run:
            self.assertEqual(self.collect(transport="fleet-credentials")["error"], "route_lookup_unavailable")
            run.assert_not_called()

    def test_policy_preserves_independent_required_helper_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = pathlib.Path(directory) / "policy.json"
            policy.write_text(json.dumps({"systems": {"desktop": {
                "ssh_target": "native", "transport": "ssh", "wsl_target": "registered", "wsl_transport": "fleet-credentials",
            }, "server": {"ssh_target": "server", "transport": "fleet-credentials"}}}))
            targets = MODULE.fleet_targets(policy)
        self.assertEqual([item["transport"] for item in targets], ["ssh", "fleet-credentials", "fleet-credentials"])

    def test_helper_timeout_cancel_or_io_error_cleans_up_only_owned_helper(self):
        for error in (subprocess.TimeoutExpired("helper", 180), KeyboardInterrupt(),
                      BrokenPipeError("private diagnostic")):
            for reaped in (True, False):
                with self.subTest(error=error, reaped=reaped):
                    child = self.child()
                    child.poll.return_value = None
                    child.communicate.side_effect = [error, (b"", b"") if reaped else subprocess.TimeoutExpired("helper", 10)]
                    with mock.patch.object(MODULE.subprocess, "run", return_value=self.reply(True)), \
                            mock.patch.object(MODULE.subprocess, "Popen", return_value=child):
                        result = self.collect()
                    child.terminate.assert_called_once()
                    child.kill.assert_not_called()
                    self.assertEqual(child.communicate.call_args.kwargs, {"timeout": 10})
                    self.assertTrue(result["stop_fleet"])
                    self.assertEqual(result["local_helper_custody"], "reaped" if reaped else "unknown")
                    self.assertEqual(result["remote_collector_custody"], "unknown")
                    self.assertNotIn("private diagnostic", json.dumps(result))
                    if isinstance(error, OSError):
                        self.assertEqual(result["error"], "registered_transport_io_error")

    def test_invalid_fleet_routes_never_become_local_collection(self):
        systems = {"missing": {"transport": "fleet-credentials"},
                   "null": {"transport": "fleet-credentials", "ssh_target": None},
                   "empty": {"transport": "fleet-credentials", "ssh_target": ""},
                   "unsupported": {"transport": "unknown", "ssh_target": None},
                   "local": {"ssh_target": None}}
        with tempfile.TemporaryDirectory() as directory:
            policy = pathlib.Path(directory) / "policy.json"
            policy.write_text(json.dumps({"systems": systems}))
            with mock.patch.object(MODULE, "collect_local_goals", return_value={"machine": "local", "goals": []}) as local, \
                    mock.patch.object(MODULE, "collect_remote") as remote:
                result = MODULE.collect_fleet(policy, None, None, None, False, 8)
        local.assert_called_once()
        self.assertEqual(local.call_args.args[0], "local")
        remote.assert_not_called()
        self.assertEqual(result["coverage"]["failed"], ["missing", "null", "empty", "unsupported"])
        self.assertEqual(result["coverage"]["reached"], ["local"])
        self.assertFalse(result["coverage"]["complete"])

    def test_native_timeout_does_not_retry(self):
        with mock.patch.object(MODULE.subprocess, "run", side_effect=[self.reply(), subprocess.TimeoutExpired("ssh", 28)]) as run:
            self.assertTrue(self.collect()["stop_fleet"])
        self.assertEqual(run.call_count, 2)

    def test_timeout_stops_fleet_with_unattempted_coverage(self):
        targets = [{"machine": name, "ssh_target": name, "transport": "ssh"} for name in ("first", "second")]
        stopped = MODULE.remote_failure("first", "registered_transport_timeout", stop_fleet=True)
        with mock.patch.object(MODULE, "fleet_targets", return_value=targets), \
                mock.patch.object(MODULE, "collect_remote", return_value=stopped) as remote:
            result = MODULE.collect_fleet(pathlib.Path("unused"), None, None, None, False, 8)
        remote.assert_called_once()
        self.assertEqual(result["coverage"]["failed"], ["first", "second"])
        self.assertEqual(result["machines"][1]["error"], "not_attempted_after_transport_stop")

    def test_windows_and_wsl_are_classified_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = pathlib.Path(directory) / "policy.json"
            policy.write_text(json.dumps({"version": 2, "systems": {"desktop": {
                "transport": "ssh", "ssh_target": "windows-alias", "python": "py -3",
                "wsl_target": "wsl-alias", "wsl_python": "/usr/bin/python3",
            }}}))
            child = self.child(data=self.payload("desktop/wsl"))
            replies = [self.reply(), subprocess.CompletedProcess([], 0, self.payload(), b""), self.reply(True)]
            with mock.patch.object(MODULE.subprocess, "run", side_effect=replies) as run, \
                    mock.patch.object(MODULE.subprocess, "Popen", return_value=child) as spawn:
                result = MODULE.collect_fleet(policy, None, None, None, False, 8)
        self.assertTrue(result["coverage"]["complete"])
        self.assertEqual(run.call_args_list[0].args[0][-1], "windows-alias")
        self.assertIn("py -3 -", run.call_args_list[1].args[0][-1])
        self.assertEqual(run.call_args_list[2].args[0][-1], "wsl-alias")
        self.assertEqual(spawn.call_args.args[0][2:5], ["wsl-alias", "--", "/usr/bin/python3"])

    def test_local_only_never_queries_helper(self):
        with mock.patch.object(sys, "argv", ["reporter", "--local", "--json"]), \
                mock.patch.object(sys, "stdout"), \
                mock.patch.object(MODULE, "collect_local_goals", return_value={"machine": "local", "goals": []}), \
                mock.patch.object(MODULE.subprocess, "run") as run:
            self.assertEqual(MODULE.main(), 0)
        run.assert_not_called()
        self.which.assert_not_called()


if __name__ == "__main__":
    unittest.main()
