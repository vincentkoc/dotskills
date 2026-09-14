#!/usr/bin/env python3
"""Snapshot one tmux lane using exact process/thread identity and bounded log I/O."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any


THREAD_ID_RE = re.compile(
    r"(?<![0-9a-f])([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?![0-9a-f])",
    re.IGNORECASE,
)
SECRET_PATTERNS = (
    re.compile(r"\b(?:gh[opusr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s]+"),
)
PRIVATE_IP_PATTERN = re.compile(
    r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])"
    r"(?:\.\d{1,3}){2}|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2})\b"
)


def run_command(args: list[str], timeout: int = 5) -> str:
    try:
        result = subprocess.run(
            args,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.rstrip("\n") if result.returncode == 0 else ""


def run_tmux(args: list[str], timeout: int = 5) -> str:
    return run_command(["tmux", *args], timeout)


def infer_lane() -> tuple[int | None, str]:
    current = run_tmux(["display", "-p", "#{session_name}\t#{window_name}\t#{pane_index}"])
    if not current:
        return None, "not running inside tmux or tmux unavailable"
    session, window, pane = (current.split("\t") + ["", "", ""])[:3]
    match = re.fullmatch(r"L(\d+)", window, re.IGNORECASE)
    if match:
        return int(match.group(1)), f"inferred from {session}:{window}.{pane}"
    return None, f"current window {session}:{window}.{pane} is not named L<number>"


def list_lane_panes(session: str, lane: int) -> list[dict[str, str]]:
    fmt = (
        "#{pane_id}\t#{pane_index}\t#{pane_title}\t#{pane_current_path}\t"
        "#{pane_current_command}\t#{pane_pid}\t#{pane_active}"
    )
    output = run_tmux(["list-panes", "-t", f"{session}:L{lane}", "-F", fmt])
    panes: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = (line.split("\t") + [""] * 7)[:7]
        panes.append(
            {
                "pane_id": parts[0],
                "pane": f"L{lane}.{parts[1]}",
                "title": parts[2],
                "cwd": parts[3],
                "command": parts[4],
                "pid": parts[5],
                "active": "yes" if parts[6] == "1" else "no",
            }
        )
    return panes


def capture_pane(session: str, lane: int, pane: str, lines: int) -> str:
    target = f"{session}:L{lane}.{pane}"
    output = run_tmux(["capture-pane", "-p", "-J", "-S", f"-{lines}", "-t", target])
    return "\n".join(line.rstrip() for line in output.splitlines()).strip()


def process_table() -> dict[int, tuple[int, str]]:
    output = run_command(["ps", "-axo", "pid=,ppid=,command="])
    processes: dict[int, tuple[int, str]] = {}
    for line in output.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        processes[pid] = (ppid, parts[2] if len(parts) == 3 else "")
    return processes


def descendant_processes(root_pid: int, processes: dict[int, tuple[int, str]]) -> list[tuple[int, str]]:
    children: dict[int, list[int]] = {}
    for pid, (ppid, _command) in processes.items():
        children.setdefault(ppid, []).append(pid)
    pending = list(children.get(root_pid, []))
    descendants: list[tuple[int, str]] = []
    while pending:
        pid = pending.pop(0)
        descendants.append((pid, processes.get(pid, (0, ""))[1]))
        pending.extend(children.get(pid, []))
    return descendants


def thread_candidates(root_pid: int, processes: dict[int, tuple[int, str]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for pid, command in descendant_processes(root_pid, processes):
        if "codex" not in command.lower():
            continue
        for thread_id in sorted({match.lower() for match in THREAD_ID_RE.findall(command)}):
            candidates.append({"pid": pid, "thread_id": thread_id, "command": command})
    return candidates


def codex_descendants(root_pid: int, processes: dict[int, tuple[int, str]]) -> list[tuple[int, str]]:
    return [
        (pid, command)
        for pid, command in descendant_processes(root_pid, processes)
        if "codex" in command.lower()
    ]


def find_state_database(codex_home: Path) -> Path | None:
    for path in (codex_home / "state_5.sqlite", codex_home / "sqlite" / "state_5.sqlite"):
        if path.exists():
            return path
    return None


def lookup_threads(database: Path | None, thread_ids: set[str]) -> dict[str, dict[str, Any]]:
    if database is None or not thread_ids:
        return {}
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        columns = {row[1] for row in connection.execute("PRAGMA table_info(threads)")}
        wanted = [
            name
            for name in (
                "id",
                "rollout_path",
                "cwd",
                "source",
                "parent_thread_id",
                "forked_from_id",
                "updated_at",
                "updated_at_ms",
            )
            if name in columns
        ]
        if "id" not in wanted or "rollout_path" not in wanted:
            connection.close()
            return {}
        placeholders = ",".join("?" for _ in thread_ids)
        rows = connection.execute(
            f"SELECT {','.join(wanted)} FROM threads WHERE id IN ({placeholders})",
            sorted(thread_ids),
        ).fetchall()
        connection.close()
    except sqlite3.Error:
        return {}
    return {str(row["id"]).lower(): dict(row) for row in rows}


def compact(text: str, max_len: int = 220) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized if len(normalized) <= max_len else normalized[: max_len - 3].rstrip() + "..."


def redact(text: str) -> str:
    redacted = text.replace(str(Path.home()), "~")
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("<redacted-secret>", redacted)
    return PRIVATE_IP_PATTERN.sub("<private-ip>", redacted)


def parse_assignment(value: str) -> tuple[str, str]:
    pane, separator, assigned = value.partition("=")
    if not separator or not pane or not assigned:
        raise argparse.ArgumentTypeError("expected PANE=VALUE")
    return pane, assigned


def load_cursor(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"version": 1, "files": {}}
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "files": {}}
    if value.get("version") == 1 and isinstance(value.get("files"), dict):
        return value
    return {"version": 1, "files": {}}


def save_cursor(path: Path | None, cursor: dict[str, Any], max_files: int) -> None:
    if path is None:
        return
    files = cursor.get("files", {})
    retained = sorted(
        files.items(),
        key=lambda item: (item[1].get("last_seen") or "", item[0]),
        reverse=True,
    )[:max_files]
    cursor["files"] = dict(retained)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(cursor, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _json_records(data: bytes, absolute_start: int, at_eof: bool) -> tuple[list[dict[str, Any]], int, bool]:
    records: list[dict[str, Any]] = []
    consumed = 0
    offset = 0
    for raw in data.splitlines(keepends=True):
        has_newline = raw.endswith((b"\n", b"\r"))
        body = raw.rstrip(b"\r\n")
        try:
            item = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            if has_newline:
                consumed = offset + len(raw)
            elif not at_eof:
                break
            offset += len(raw)
            continue
        if isinstance(item, dict):
            records.append(item)
        consumed = offset + len(raw)
        offset += len(raw)
    partial = consumed < len(data)
    return records, absolute_start + consumed, partial


def read_log(
    path: Path,
    byte_limit: int,
    cursor_entry: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        stat = path.stat()
    except OSError as error:
        return [], {"path": str(path), "error": str(error), "bytes_read": 0, "truncated": False}

    previous = cursor_entry or {}
    same_file = previous.get("device") == stat.st_dev and previous.get("inode") == stat.st_ino
    previous_offset = int(previous.get("offset") or 0)
    incremental = same_file and 0 <= previous_offset <= stat.st_size
    if incremental:
        start = previous_offset
        requested = min(byte_limit, stat.st_size - start)
        mode = "unchanged" if requested == 0 else "incremental"
    else:
        requested = min(byte_limit, stat.st_size)
        start = stat.st_size - requested
        mode = "tail"

    try:
        with path.open("rb") as handle:
            handle.seek(start)
            data = handle.read(requested)
    except OSError as error:
        return [], {"path": str(path), "error": str(error), "bytes_read": 0, "truncated": False}

    discarded_prefix = False
    parse_start = start
    if mode == "tail" and start > 0 and data:
        newline = data.find(b"\n")
        if newline < 0:
            return [], {
                "path": str(path),
                "bytes_read": len(data),
                "file_size": stat.st_size,
                "mode": mode,
                "truncated": True,
                "partial_record": True,
                "device": stat.st_dev,
                "inode": stat.st_ino,
                "offset": stat.st_size,
            }
        parse_start += newline + 1
        data = data[newline + 1 :]
        discarded_prefix = True

    records, next_offset, partial = _json_records(data, parse_start, parse_start + len(data) == stat.st_size)
    if mode == "unchanged":
        next_offset = stat.st_size
    truncated = discarded_prefix or start + requested < stat.st_size or partial
    return records, {
        "path": str(path),
        "bytes_read": requested,
        "file_size": stat.st_size,
        "mode": mode,
        "truncated": truncated,
        "partial_record": partial,
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "offset": next_offset,
        "bytes_appended": (
            max(0, stat.st_size - int(previous.get("file_size") or 0))
            if same_file
            else stat.st_size
        ),
        "last_seen": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def payload_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    chunks: list[str] = []
    for key in ("message", "output", "text"):
        value = payload.get(key)
        if isinstance(value, str):
            chunks.append(value)
    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("input_text") or item.get("output_text")
                if isinstance(value, str):
                    chunks.append(value)
    return "\n".join(chunks)


def summarize_records(records: list[dict[str, Any]], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    if not records and previous:
        return {**previous, "changed": False}
    defaults: dict[str, Any] = {
        "state": "unknown",
        "turn_id": None,
        "latest_timestamp": None,
        "latest": "",
        "events": 0,
        "tool_calls": 0,
        "tool_outputs": 0,
        "token_updates": 0,
        "changed": False,
    }
    summary = {**defaults, **(previous or {}), "changed": bool(records)}
    for item in records:
        kind = str(item.get("type") or "")
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if item.get("timestamp"):
            summary["latest_timestamp"] = item["timestamp"]
        payload_kind = str(payload.get("type") or "")
        turn_id = payload.get("turn_id") or payload.get("turnId") or payload.get("id")
        is_boundary = kind == "turn_context" or (kind == "event_msg" and payload_kind == "task_started")
        if is_boundary and turn_id and turn_id != summary.get("turn_id"):
            summary.update(
                {
                    "state": "active-progress",
                    "turn_id": turn_id,
                    "latest": "",
                    "events": 0,
                    "tool_calls": 0,
                    "tool_outputs": 0,
                    "token_updates": 0,
                }
            )
        summary["events"] += 1
        if kind == "event_msg":
            if payload_kind == "task_complete":
                summary["state"] = "completed"
            elif payload_kind in {"turn_aborted", "stream_error", "error"}:
                summary["state"] = "failed"
            elif payload_kind == "token_count":
                summary["token_updates"] += 1
            elif payload_kind in {"agent_message", "agent_reasoning"}:
                summary["state"] = "active-progress"
        elif kind == "response_item":
            if payload_kind in {"function_call", "custom_tool_call"}:
                summary["tool_calls"] += 1
                summary["state"] = (
                    "waiting"
                    if payload.get("name") in {"wait_agent", "write_stdin"}
                    else "active-progress"
                )
            elif payload_kind in {"function_call_output", "custom_tool_call_output"}:
                summary["tool_outputs"] += 1
                summary["state"] = "active-progress"
        text = payload_text(payload)
        if text:
            summary["latest"] = compact(text)
    return summary


def project_activity(summary: dict[str, Any], show_content: bool) -> dict[str, Any]:
    projected = dict(summary)
    latest = projected.get("latest")
    if isinstance(latest, str) and not show_content:
        projected["latest"] = redact(latest)
    return projected


def resolve_pane_identity(
    pane: dict[str, str],
    processes: dict[int, tuple[int, str]],
    explicit_threads: dict[str, str],
    thread_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    keys = (pane["pane"], pane["pane_id"])
    explicit = next((explicit_threads[key].lower() for key in keys if key in explicit_threads), None)
    try:
        root_pid = int(pane["pid"])
    except ValueError:
        root_pid = 0
    candidates = thread_candidates(root_pid, processes) if root_pid else []
    if explicit:
        agents = codex_descendants(root_pid, processes) if root_pid else []
        matching = [candidate for candidate in candidates if candidate["thread_id"] == explicit]
        agent_pids = sorted({pid for pid, _command in agents})
        agent_pid = matching[0]["pid"] if len(matching) == 1 else agent_pids[0] if len(agent_pids) == 1 else None
        source = (
            "explicit"
            if agent_pid and (not candidates or len(matching) == 1)
            else "conflict"
            if candidates
            else "agent-pid-ambiguous"
            if agent_pids
            else "agent-pid-unproven"
        )
        thread_ids = [explicit]
    else:
        unique = sorted({candidate["thread_id"] for candidate in candidates})
        matching = [candidate for candidate in candidates if len(unique) == 1]
        agent_pid = matching[0]["pid"] if matching else None
        source = "process-lineage" if len(unique) == 1 else "ambiguous" if unique else "unmatched"
        thread_ids = unique
    if source in {
        "conflict",
        "ambiguous",
        "unmatched",
        "agent-pid-ambiguous",
        "agent-pid-unproven",
    }:
        return {
            "status": "unknown",
            "reason": source,
            "agent_pid": agent_pid,
            "thread_ids": thread_ids,
        }
    thread_id = thread_ids[0]
    row = thread_rows.get(thread_id)
    rollout_path = str(row.get("rollout_path") or "") if row else ""
    if not rollout_path:
        return {
            "status": "unknown",
            "reason": "thread-not-in-state-database",
            "agent_pid": agent_pid,
            "thread_ids": [thread_id],
        }
    return {
        "status": "exact",
        "reason": source,
        "agent_pid": agent_pid,
        "thread_id": thread_id,
        "rollout_path": rollout_path,
        "thread": row,
    }


def build_snapshot(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    session = args.session or run_tmux(["display", "-p", "#{session_name}"]) or os.environ.get("TMUX_SESSION") or ""
    if not session:
        raise RuntimeError("cannot determine tmux session")
    lane = args.lane
    infer_reason = None
    if lane is None:
        lane, infer_reason = infer_lane()
    if lane is None:
        raise RuntimeError("pass --lane explicitly")
    panes = list_lane_panes(session, lane)
    if not panes:
        raise RuntimeError(f"no panes found for {session}:L{lane}")

    explicit_threads = dict(args.thread or [])
    processes = process_table()
    candidate_ids = set(explicit_threads.values())
    for pane in panes:
        try:
            candidate_ids.update(candidate["thread_id"] for candidate in thread_candidates(int(pane["pid"]), processes))
        except ValueError:
            pass
    state_database = find_state_database(args.codex_home)
    thread_rows = lookup_threads(state_database, {value.lower() for value in candidate_ids})
    cursor = load_cursor(args.cursor_file)
    remaining = args.total_log_bytes
    output_panes = []
    total_bytes = 0
    for pane in panes:
        identity = resolve_pane_identity(pane, processes, explicit_threads, thread_rows)
        capture = capture_pane(session, lane, pane["pane"].split(".")[-1], args.capture_lines)
        last_line = compact(capture.splitlines()[-1] if capture.splitlines() else "")
        if not args.show_content:
            last_line = redact(last_line)
        public_pane = {
            **pane,
            "cwd": pane["cwd"] if args.show_content else redact(pane["cwd"]),
            "title": pane["title"] if args.show_content else redact(pane["title"]),
        }
        public_identity = {key: value for key, value in identity.items() if key != "thread"}
        if not args.show_content and public_identity.get("rollout_path"):
            public_identity["rollout_path"] = redact(public_identity["rollout_path"])
        result = {
            **public_pane,
            "last": last_line,
            "identity": public_identity,
            "state": "unknown",
        }
        if identity["status"] == "exact":
            path = Path(identity["rollout_path"])
            previous_entry = cursor["files"].get(str(path), {})
            byte_limit = min(args.log_bytes, remaining)
            records, io = read_log(path, byte_limit, previous_entry if args.cursor_file else None)
            remaining -= io["bytes_read"]
            total_bytes += io["bytes_read"]
            summary = summarize_records(records, previous_entry.get("summary"))
            io["summary"] = project_activity(summary, False)
            cursor["files"][str(path)] = io
            result["log"] = {
                key: redact(value)
                if key == "path" and isinstance(value, str) and not args.show_content
                else value
                for key, value in io.items()
                if key not in {"device", "inode", "offset", "summary", "last_seen"}
            }
            result["activity"] = project_activity(summary, args.show_content)
            result["state"] = summary["state"]
        output_panes.append(result)

    snapshot = {
        "session": session,
        "lane": lane,
        "inference": infer_reason,
        "state_database": (
            str(state_database)
            if args.show_content and state_database
            else redact(str(state_database))
            if state_database
            else None
        ),
        "io": {
            "bytes_read": total_bytes,
            "per_file_limit": args.log_bytes,
            "total_limit": args.total_log_bytes,
            "budget_exhausted": remaining == 0,
        },
        "panes": output_panes,
    }
    return snapshot, cursor


def render_text(snapshot: dict[str, Any], show_content: bool) -> str:
    lines = [f"lane L{snapshot['lane']} snapshot", f"session: {snapshot['session']}", "", "panes:"]
    for pane in snapshot["panes"]:
        identity = pane["identity"]
        cwd = pane["cwd"] if show_content else redact(pane["cwd"])
        title = pane["title"] if show_content else redact(pane["title"])
        lines.append(
            f"- {pane['pane']} pane_id={pane['pane_id']} state={pane['state']} active={pane['active']} "
            f"cmd={pane['command']} shell_pid={pane['pid']} agent_pid={identity.get('agent_pid') or '-'} "
            f"identity={identity['status']} cwd={cwd} title={title!r}"
        )
        if identity["status"] == "exact":
            rollout = identity["rollout_path"] if show_content else redact(identity["rollout_path"])
            lines.append(f"  thread={identity['thread_id']} rollout={rollout}")
            log = pane.get("log", {})
            lines.append(
                f"  log bytes={log.get('bytes_read', 0)} mode={log.get('mode', 'none')} "
                f"truncated={str(bool(log.get('truncated'))).lower()}"
            )
        else:
            lines.append(f"  identity_reason={identity['reason']}")
        if pane["last"]:
            lines.append(f"  last: {pane['last']}")
    io = snapshot["io"]
    lines.extend(
        [
            "",
            f"log I/O: bytes={io['bytes_read']} per_file_limit={io['per_file_limit']} "
            f"total_limit={io['total_limit']} budget_exhausted={str(io['budget_exhausted']).lower()}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", type=int, help="Lane number, e.g. 1 for L1.")
    parser.add_argument("--session", help="tmux session name. Defaults to current session.")
    parser.add_argument("--capture-lines", type=int, default=80)
    parser.add_argument("--log-bytes", type=int, default=262_144, help="Maximum bytes read from one exact rollout.")
    parser.add_argument("--total-log-bytes", type=int, default=1_048_576, help="Maximum rollout bytes read per snapshot.")
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex", help=argparse.SUPPRESS)
    parser.add_argument(
        "--thread",
        action="append",
        type=parse_assignment,
        metavar="PANE=THREAD_ID",
        help="Declare exact pane/thread identity when the descendant command does not contain the thread id.",
    )
    parser.add_argument(
        "--cursor-file",
        type=Path,
        help="Optional bounded incremental cursor. No persistent state is written unless this is set.",
    )
    parser.add_argument("--cursor-max-files", type=int, default=64, help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--show-content",
        action="store_true",
        help="Print raw pane, path, and log content instead of privacy-redacted output.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.log_bytes < 1 or args.total_log_bytes < 1 or args.cursor_max_files < 1:
        parser.error("log and cursor limits must be positive")
    try:
        snapshot, cursor = build_snapshot(args)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    save_cursor(args.cursor_file, cursor, args.cursor_max_files)
    if args.json:
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render_text(snapshot, args.show_content))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
