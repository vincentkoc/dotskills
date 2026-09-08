#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any


SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent


def default_policy_path() -> pathlib.Path | None:
    configured = os.environ.get("CODEX_FLEET_POLICY")
    if configured:
        return pathlib.Path(configured).expanduser()
    candidates = [
        pathlib.Path.home() / ".config" / "codex-goal-mining" / "fleet-policy.json",
        pathlib.Path.home() / ".codex" / "fleet-policy.json",
    ]
    return next((path for path in candidates if path.exists()), None)


DEFAULT_POLICY = default_policy_path()
GOAL_EVENT_MARKER = '"type":"event_msg","payload":{"type":"thread_goal_updated"'
GOAL_EVENT_PATTERN = r'^\{"timestamp":"[^"]+","type":"event_msg","payload":\{"type":"thread_goal_updated"'
TIMESTAMP_PATTERN = re.compile(r'^\{"timestamp":"([^"]+)"')


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def format_duration(seconds: int | float | None) -> str:
    total = max(0, int(seconds or 0))
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def normalize_objective(value: str) -> str:
    return " ".join(value.lower().split())


def thread_identity(thread: sqlite3.Row | None) -> tuple[str, str | None]:
    if thread is None:
        return "unknown", None
    keys = set(thread.keys())
    thread_source = str(thread["thread_source"] or "") if "thread_source" in keys else ""
    source = thread["source"] if "source" in keys else None
    parent_thread_id = None
    if isinstance(source, str) and source.startswith("{"):
        try:
            source_value = json.loads(source)
        except json.JSONDecodeError:
            source_value = {}
        subagent = source_value.get("subagent") if isinstance(source_value, dict) else None
        if isinstance(subagent, dict):
            spawn = subagent.get("thread_spawn")
            if isinstance(spawn, dict) and spawn.get("parent_thread_id"):
                parent_thread_id = str(spawn["parent_thread_id"])
    return ("child", parent_thread_id) if thread_source == "subagent" else ("root", None)


def candidate_goal_files(sessions_root: pathlib.Path) -> list[pathlib.Path]:
    if not sessions_root.exists():
        return []
    if shutil.which("rg"):
        result = subprocess.run(
            ["rg", "-l", "--glob", "*.jsonl", GOAL_EVENT_PATTERN, str(sessions_root)],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode in (0, 1):
            return [pathlib.Path(line) for line in result.stdout.splitlines() if line]
    return list(sessions_root.rglob("*.jsonl"))


def find_database(codex_home: pathlib.Path, name: str, required_table: str) -> pathlib.Path | None:
    candidates = [codex_home / name, codex_home / "sqlite" / name]
    valid = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
            found = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (required_table,)
            ).fetchone()
            connection.close()
            if found:
                valid.append(path)
        except sqlite3.Error:
            continue
    return max(valid, key=lambda path: path.stat().st_mtime) if valid else None


def in_window(
    created_at: datetime | None,
    updated_at: datetime | None,
    since: datetime | None,
    until: datetime | None,
    activity_overlap: bool,
) -> bool:
    selected = updated_at if activity_overlap else created_at
    if since and (selected is None or selected < since):
        return False
    if until and (selected is None or selected >= until):
        return False
    return True


def collect_sqlite_goals(
    machine: str,
    codex_home: pathlib.Path,
    since: datetime | None,
    until: datetime | None = None,
    activity_overlap: bool = False,
) -> dict[str, Any] | None:
    goals_db = find_database(codex_home, "goals_1.sqlite", "thread_goals")
    if goals_db is None:
        return None
    state_db = find_database(codex_home, "state_5.sqlite", "threads")
    try:
        goals_connection = sqlite3.connect(f"file:{goals_db}?mode=ro", uri=True, timeout=4)
        goals_connection.row_factory = sqlite3.Row
        goal_columns = {
            row[1] for row in goals_connection.execute("PRAGMA table_info(thread_goals)")
        }
        selected_goal_columns = [
            name
            for name in (
                "thread_id",
                "goal_id",
                "objective",
                "status",
                "tokens_used",
                "time_used_seconds",
                "created_at_ms",
                "updated_at_ms",
            )
            if name in goal_columns
        ]
        rows = goals_connection.execute(
            f"SELECT {','.join(selected_goal_columns)} FROM thread_goals "
            "ORDER BY created_at_ms DESC"
        ).fetchall()
        goals_connection.close()
    except sqlite3.Error:
        return None

    threads: dict[str, sqlite3.Row] = {}
    if state_db:
        try:
            state_connection = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True, timeout=4)
            state_connection.row_factory = sqlite3.Row
            thread_columns = {
                row[1] for row in state_connection.execute("PRAGMA table_info(threads)")
            }
            selected_columns = [
                name
                for name in (
                    "id",
                    "rollout_path",
                    "created_at",
                    "updated_at",
                    "created_at_ms",
                    "updated_at_ms",
                    "source",
                    "thread_source",
                )
                if name in thread_columns
            ]
            thread_ids = [row["thread_id"] for row in rows]
            for offset in range(0, len(thread_ids), 400):
                batch = thread_ids[offset : offset + 400]
                placeholders = ",".join("?" for _ in batch)
                if not placeholders:
                    continue
                for row in state_connection.execute(
                    f"SELECT {','.join(selected_columns)} FROM threads "
                    f"WHERE id IN ({placeholders})",
                    batch,
                ):
                    threads[row["id"]] = row
            state_connection.close()
        except sqlite3.Error:
            threads = {}

    goals = []
    for row in rows:
        created_at = datetime.fromtimestamp(row["created_at_ms"] / 1000, timezone.utc)
        updated_at = datetime.fromtimestamp(row["updated_at_ms"] / 1000, timezone.utc)
        if not in_window(created_at, updated_at, since, until, activity_overlap):
            continue
        thread = threads.get(row["thread_id"])
        thread_role, parent_thread_id = thread_identity(thread)
        session_start = None
        session_end = None
        sources = []
        if thread:
            start_ms = thread["created_at_ms"] or int(thread["created_at"] or 0) * 1000
            end_ms = thread["updated_at_ms"] or int(thread["updated_at"] or 0) * 1000
            session_start = datetime.fromtimestamp(start_ms / 1000, timezone.utc) if start_ms else None
            session_end = datetime.fromtimestamp(end_ms / 1000, timezone.utc) if end_ms else None
            if thread["rollout_path"]:
                sources.append(str(thread["rollout_path"]))
        goals.append(
            {
                "machine": machine,
                "thread_id": row["thread_id"],
                "goal_id": row["goal_id"] if "goal_id" in row.keys() else None,
                "objective": row["objective"],
                "status": row["status"],
                "tokens_used": int(row["tokens_used"] or 0),
                "goal_time_seconds": int(row["time_used_seconds"] or 0),
                "created_at": format_timestamp(created_at),
                "updated_at": format_timestamp(updated_at),
                "session_started_at": format_timestamp(session_start),
                "session_ended_at": format_timestamp(session_end),
                "session_span_seconds": int((session_end - session_start).total_seconds()) if session_start and session_end else 0,
                "source_files": sources,
                "thread_role": thread_role,
                "parent_thread_id": parent_thread_id,
                "counter_scope": "lifetime_snapshot",
            }
        )
    return {
        "machine": machine,
        "storage": "sqlite",
        "goals_database": str(goals_db),
        "state_database": str(state_db) if state_db else None,
        "selection_mode": "activity" if activity_overlap else "created",
        "goals": goals,
    }


def event_key(goal: dict[str, Any], fallback_thread_id: str) -> tuple[str, int, str]:
    return (
        str(goal.get("threadId") or fallback_thread_id),
        int(goal.get("createdAt") or 0),
        normalize_objective(str(goal.get("objective") or "")),
    )


def collect_local_goals(
    machine: str,
    sessions_root: pathlib.Path,
    since: datetime | None = None,
    until: datetime | None = None,
    activity_overlap: bool = False,
) -> dict[str, Any]:
    database_report = collect_sqlite_goals(machine, sessions_root.parent, since, until, activity_overlap)
    if database_report is not None:
        return database_report
    goals: dict[tuple[str, int, str], dict[str, Any]] = {}
    parse_errors = 0
    files_scanned = 0

    for path in candidate_goal_files(sessions_root):
        files_scanned += 1
        file_start: datetime | None = None
        file_end: datetime | None = None
        file_keys: set[tuple[str, int, str]] = set()
        try:
            with path.open(errors="replace") as handle:
                for line in handle:
                    timestamp_match = TIMESTAMP_PATTERN.match(line)
                    timestamp = parse_timestamp(timestamp_match.group(1)) if timestamp_match else None
                    if timestamp is not None:
                        file_start = min(file_start, timestamp) if file_start else timestamp
                        file_end = max(file_end, timestamp) if file_end else timestamp
                    if GOAL_EVENT_MARKER not in line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        parse_errors += 1
                        continue
                    payload = event.get("payload") or {}
                    goal = payload.get("goal") or {}
                    objective = str(goal.get("objective") or "").strip()
                    if not objective:
                        continue
                    key = event_key(goal, str(payload.get("threadId") or ""))
                    created_at = datetime.fromtimestamp(int(goal.get("createdAt") or 0), timezone.utc) if goal.get("createdAt") else timestamp
                    updated_at = int(goal.get("updatedAt") or 0)
                    event_updated_at = datetime.fromtimestamp(updated_at, timezone.utc) if updated_at else timestamp
                    if activity_overlap:
                        if since and (event_updated_at is None or event_updated_at < since):
                            continue
                        if until and (event_updated_at is None or event_updated_at >= until):
                            continue
                    elif not in_window(created_at, event_updated_at, since, until, False):
                        continue
                    current = goals.get(key)
                    snapshot = {
                        "machine": machine,
                        "thread_id": key[0],
                        "goal_id": str(goal.get("id") or f"{key[1]}:{key[2]}"),
                        "objective": objective,
                        "status": str(goal.get("status") or "unknown"),
                        "tokens_used": int(goal.get("tokensUsed") or 0),
                        "goal_time_seconds": int(goal.get("timeUsedSeconds") or 0),
                        "created_at": format_timestamp(created_at),
                        "updated_at": format_timestamp(
                            datetime.fromtimestamp(updated_at, timezone.utc) if updated_at else timestamp
                        ),
                        "session_started_at": format_timestamp(file_start),
                        "session_ended_at": format_timestamp(file_end),
                        "session_span_seconds": 0,
                        "source_files": [str(path)],
                        "thread_role": "unknown",
                        "parent_thread_id": None,
                        "counter_scope": "lifetime_snapshot",
                        "_updated_epoch": updated_at,
                        "_session_start": file_start,
                        "_session_end": file_end,
                    }
                    if current is None or (
                        snapshot["_updated_epoch"], snapshot["goal_time_seconds"], snapshot["tokens_used"]
                    ) >= (
                        current["_updated_epoch"], current["goal_time_seconds"], current["tokens_used"]
                    ):
                        if current:
                            snapshot["source_files"] = sorted(set(current["source_files"] + snapshot["source_files"]))
                            snapshot["_session_start"] = min(
                                value for value in (current["_session_start"], file_start) if value is not None
                            )
                            snapshot["_session_end"] = max(
                                value for value in (current["_session_end"], file_end) if value is not None
                            )
                        goals[key] = snapshot
                    else:
                        current["source_files"] = sorted(set(current["source_files"] + [str(path)]))
                    file_keys.add(key)
        except OSError:
            parse_errors += 1
            continue

        for key in file_keys:
            current = goals[key]
            starts = [value for value in (current["_session_start"], file_start) if value is not None]
            ends = [value for value in (current["_session_end"], file_end) if value is not None]
            current["_session_start"] = min(starts) if starts else None
            current["_session_end"] = max(ends) if ends else None

    output = []
    for goal in goals.values():
        start = goal.pop("_session_start")
        end = goal.pop("_session_end")
        goal.pop("_updated_epoch")
        goal["session_started_at"] = format_timestamp(start)
        goal["session_ended_at"] = format_timestamp(end)
        goal["session_span_seconds"] = int((end - start).total_seconds()) if start and end else 0
        output.append(goal)
    output.sort(key=lambda item: (item.get("created_at") or "", item["machine"], item["thread_id"]), reverse=True)
    return {
        "machine": machine,
        "storage": "jsonl-fallback",
        "sessions_root": str(sessions_root),
        "files_scanned": files_scanned,
        "parse_errors": parse_errors,
        "selection_mode": "activity" if activity_overlap else "created",
        "goals": output,
    }


def fleet_targets(policy_path: pathlib.Path, selected: set[str] | None = None) -> list[dict[str, str | None]]:
    policy = json.loads(policy_path.read_text())
    targets = []
    for alias, system in policy.get("systems", {}).items():
        wsl_alias = f"{alias}/wsl"
        if selected and alias not in selected and wsl_alias not in selected:
            continue
        if not selected or alias in selected:
            targets.append(
                {
                    "machine": alias,
                    "ssh_target": system.get("ssh_target"),
                    "interpreter": system.get("python"),
                }
            )
        wsl_target = system.get("wsl_target")
        if wsl_target and (not selected or alias in selected or wsl_alias in selected):
            targets.append(
                {
                    "machine": wsl_alias,
                    "ssh_target": wsl_target,
                    "interpreter": system.get("wsl_python"),
                }
            )
    return targets


def collect_remote(
    script: bytes,
    machine: str,
    ssh_target: str,
    since: str | None,
    until: str | None,
    activity_overlap: bool,
    timeout: int,
    interpreter: str | None = None,
    one_attempt: bool = False,
) -> dict[str, Any]:
    arguments = ["--collect-local", "--machine-name", machine, "--json"]
    if since:
        arguments.extend(["--since", since])
    if until:
        arguments.extend(["--until", until])
    if activity_overlap:
        arguments.append("--activity-overlap")
    failures = []
    interpreters = [interpreter] if interpreter else ["python3", "python", "py -3"]
    if one_attempt:
        interpreters = interpreters[:1]
    for selected_interpreter in interpreters:
        command = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", f"ConnectTimeout={timeout}",
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=3",
            ssh_target,
            shlex.join([*shlex.split(selected_interpreter), "-", *arguments]),
        ]
        try:
            result = subprocess.run(command, input=script, capture_output=True, timeout=timeout + 20)
        except subprocess.TimeoutExpired:
            failures.append(f"{selected_interpreter}: timed out")
            continue
        if result.returncode == 0:
            try:
                return json.loads(result.stdout.decode())
            except json.JSONDecodeError as error:
                failures.append(f"{selected_interpreter}: invalid JSON ({error})")
                continue
        detail = result.stderr.decode(errors="replace").strip() or result.stdout.decode(errors="replace").strip()
        detail = detail.replace(ssh_target, machine)
        failures.append(f"{selected_interpreter}: {detail or f'exit {result.returncode}'}")
        if "timed out" in detail.lower() or "connection" in detail.lower():
            break
    return {"machine": machine, "error": "; ".join(failures), "goals": []}


def collect_fleet(
    policy_path: pathlib.Path,
    selected: set[str] | None,
    since: datetime | None,
    until: datetime | None,
    activity_overlap: bool,
    timeout: int,
    one_attempt: bool = False,
) -> dict[str, Any]:
    script = pathlib.Path(__file__).read_bytes()
    machines = []
    for target in fleet_targets(policy_path, selected):
        machine = str(target["machine"])
        ssh_target = target["ssh_target"]
        if ssh_target:
            machines.append(
                collect_remote(
                    script,
                    machine,
                    str(ssh_target),
                    format_timestamp(since),
                    format_timestamp(until),
                    activity_overlap,
                    timeout,
                    target.get("interpreter"),
                    one_attempt,
                )
            )
        else:
            machines.append(
                collect_local_goals(
                    machine,
                    pathlib.Path.home() / ".codex" / "sessions",
                    since,
                    until,
                    activity_overlap,
                )
            )
    failed = [machine["machine"] for machine in machines if machine.get("error")]
    reached = [machine["machine"] for machine in machines if not machine.get("error")]
    return {
        "generated_at": format_timestamp(datetime.now(timezone.utc)),
        "window": {
            "since": format_timestamp(since),
            "until": format_timestamp(until),
            "selection": "activity" if activity_overlap else "created",
        },
        "coverage": {
            "expected": [machine["machine"] for machine in machines],
            "reached": reached,
            "failed": failed,
            "complete": not failed,
        },
        "machines": machines,
    }


def apply_counter_cursor(
    report: dict[str, Any],
    cursor_path: pathlib.Path,
    max_entries: int,
) -> None:
    try:
        cursor = json.loads(cursor_path.read_text()) if cursor_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        cursor = {}
    previous_entries = cursor.get("entries") if isinstance(cursor.get("entries"), dict) else {}
    captured_at = format_timestamp(datetime.now(timezone.utc))
    next_entries: dict[str, Any] = {}
    for goal in flatten_goals(report):
        goal_identity = goal.get("goal_id") or normalize_objective(goal.get("objective") or "")
        key = f"{goal['machine']}:{goal['thread_id']}:{goal_identity}"
        previous = previous_entries.get(key)
        current_tokens = int(goal.get("tokens_used") or 0)
        current_seconds = int(goal.get("goal_time_seconds") or 0)
        token_reset = bool(previous and current_tokens < int(previous.get("tokens_used") or 0))
        time_reset = bool(previous and current_seconds < int(previous.get("goal_time_seconds") or 0))
        goal["counter_delta"] = {
            "from_capture": previous.get("captured_at") if previous else None,
            "to_capture": captured_at,
            "tokens": (
                current_tokens - int(previous.get("tokens_used") or 0)
                if previous and not token_reset
                else None
            ),
            "goal_time_seconds": (
                current_seconds - int(previous.get("goal_time_seconds") or 0)
                if previous and not time_reset
                else None
            ),
            "tokens_reset": token_reset,
            "goal_time_reset": time_reset,
        }
        next_entries[key] = {
            "machine": goal["machine"],
            "thread_id": goal["thread_id"],
            "goal_id": goal.get("goal_id"),
            "captured_at": captured_at,
            "tokens_used": current_tokens,
            "goal_time_seconds": current_seconds,
            "updated_at": goal.get("updated_at"),
        }
    combined = {**previous_entries, **next_entries}
    retained = sorted(
        combined.items(),
        key=lambda item: (item[1].get("captured_at") or "", item[0]),
        reverse=True,
    )[:max_entries]
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cursor_path.with_name(f".{cursor_path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps({"version": 1, "captured_at": captured_at, "entries": dict(retained)}, indent=2)
        + "\n"
    )
    temporary.replace(cursor_path)
    report["counter_cursor"] = {
        "path": str(cursor_path),
        "captured_at": captured_at,
        "entry_count": len(retained),
        "max_entries": max_entries,
        "basis": "delta from the previous captured lifetime snapshot",
    }


def flatten_goals(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [goal for machine in report.get("machines", []) for goal in machine.get("goals", [])]


def markdown_report(report: dict[str, Any]) -> str:
    goals = flatten_goals(report)
    reachable = [machine for machine in report.get("machines", []) if not machine.get("error")]
    unreachable = [machine for machine in report.get("machines", []) if machine.get("error")]
    total_goal_time = sum(goal.get("goal_time_seconds", 0) for goal in goals)
    total_session_span = sum(goal.get("session_span_seconds", 0) for goal in goals)
    lines = [
        "# Codex Fleet Goal Report",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Window: {report.get('window', {}).get('since') or 'unbounded'} to "
        f"{report.get('window', {}).get('until') or 'now'} "
        f"({report.get('window', {}).get('selection', 'created')})",
        "",
        "## Summary",
        "",
        f"- Goals: {len(goals)}",
        f"- Machines reached: {len(reachable)}/{len(report.get('machines', []))}",
        f"- Lifetime goal-time snapshots: {format_duration(total_goal_time)}",
        f"- Summed wall-clock thread spans: {format_duration(total_session_span)} (includes idle/resume gaps)",
        f"- Lifetime token snapshots: {sum(goal.get('tokens_used', 0) for goal in goals):,}",
    ]
    deltas = [goal.get("counter_delta") for goal in goals if goal.get("counter_delta")]
    token_deltas = [delta["tokens"] for delta in deltas if delta.get("tokens") is not None]
    time_deltas = [
        delta["goal_time_seconds"]
        for delta in deltas
        if delta.get("goal_time_seconds") is not None
    ]
    if deltas:
        lines.extend(
            [
                f"- Incremental token delta: {sum(token_deltas):,} "
                f"({len(token_deltas)}/{len(deltas)} goals had a prior baseline)",
                f"- Incremental goal-time delta: {format_duration(sum(time_deltas))} "
                f"({len(time_deltas)}/{len(deltas)} goals had a prior baseline)",
            ]
        )
    if unreachable:
        lines.extend(["", "## Unreachable", ""])
        for machine in unreachable:
            lines.append(f"- **{machine['machine']}**: {machine['error']}")

    repeated = Counter(normalize_objective(goal["objective"]) for goal in goals)
    repeated = Counter({objective: count for objective, count in repeated.items() if count > 1})
    if repeated:
        lines.extend(["", "## Repeated Goals", ""])
        for objective, count in repeated.most_common():
            lines.append(f"- **{count} runs** — {objective}")

    lines.extend(["", "## Goals", ""])
    for goal in goals:
        lines.extend(
            [
                f"### {goal['machine']} — {goal.get('created_at') or 'unknown date'}",
                "",
                goal["objective"],
                "",
                f"- Status: {goal['status']}",
                f"- Goal time snapshot: {format_duration(goal['goal_time_seconds'])}",
                f"- Wall-clock thread span: {format_duration(goal['session_span_seconds'])} (includes idle/resume gaps)",
                f"- Token snapshot: {goal['tokens_used']:,}",
                f"- Thread role: {goal.get('thread_role', 'unknown')}",
                f"- Thread: `{goal['thread_id']}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def parse_bound(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


parse_since = parse_bound


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect structured Codex /goal history locally or across a configured fleet.")
    parser.add_argument("--policy", type=pathlib.Path, default=DEFAULT_POLICY, help="Fleet policy JSON; omit for local collection.")
    parser.add_argument("--machine", action="append", help="Fleet alias to include; repeat to select several.")
    parser.add_argument("--since", help="Only include goals created on or after this ISO date/time.")
    parser.add_argument("--until", help="Exclusive ISO date/time upper bound.")
    parser.add_argument(
        "--activity-overlap",
        action="store_true",
        help="Select goals updated in the window instead of changing the existing creation-time semantics.",
    )
    parser.add_argument("--ssh-timeout", type=int, default=8)
    parser.add_argument(
        "--one-attempt",
        action="store_true",
        help="Try only the configured or first remote interpreter for each fleet target.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    parser.add_argument("--output", type=pathlib.Path, help="Write the report to a file instead of stdout.")
    parser.add_argument("--local", action="store_true", help="Collect only this machine instead of the configured fleet.")
    parser.add_argument(
        "--fleet",
        action="store_true",
        help="Require configured fleet collection; fail if no fleet policy is available.",
    )
    parser.add_argument(
        "--cursor-file",
        type=pathlib.Path,
        help="Optional bounded counter snapshot for reset-safe deltas. No cursor is written by default.",
    )
    parser.add_argument("--cursor-max-entries", type=int, default=10_000)
    parser.add_argument("--collect-local", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--machine-name", default=os.environ.get("HOSTNAME") or "local", help=argparse.SUPPRESS)
    parser.add_argument("--sessions-root", type=pathlib.Path, default=pathlib.Path.home() / ".codex" / "sessions", help=argparse.SUPPRESS)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    since = parse_bound(args.since)
    until = parse_bound(args.until)
    if since and until and until <= since:
        parser.error("--until must be later than --since")
    if args.cursor_max_entries < 1:
        parser.error("--cursor-max-entries must be positive")
    if args.fleet and args.local:
        parser.error("--fleet and --local conflict")
    if args.fleet and args.policy is None:
        parser.error("fleet policy is required; pass --policy or set CODEX_FLEET_POLICY")
    if args.collect_local:
        payload: dict[str, Any] = collect_local_goals(
            args.machine_name,
            args.sessions_root,
            since,
            until,
            args.activity_overlap,
        )
    elif args.local or args.policy is None:
        local_report = collect_local_goals(
            args.machine_name,
            args.sessions_root,
            since,
            until,
            args.activity_overlap,
        )
        payload = {
            "generated_at": format_timestamp(datetime.now(timezone.utc)),
            "window": {
                "since": format_timestamp(since),
                "until": format_timestamp(until),
                "selection": "activity" if args.activity_overlap else "created",
            },
            "coverage": {
                "expected": [local_report["machine"]],
                "reached": [local_report["machine"]],
                "failed": [],
                "complete": True,
            },
            "machines": [local_report],
        }
    else:
        if not args.policy.exists():
            parser.error(f"fleet policy not found: {args.policy}")
        payload = collect_fleet(
            args.policy,
            set(args.machine or []) or None,
            since,
            until,
            args.activity_overlap,
            args.ssh_timeout,
            args.one_attempt,
        )
    if args.cursor_file:
        apply_counter_cursor(payload, args.cursor_file, args.cursor_max_entries)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n" if args.json else markdown_report(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        sys.stdout.write(rendered)
    return 2 if any(machine.get("error") for machine in payload.get("machines", [])) else 0


if __name__ == "__main__":
    raise SystemExit(main())
