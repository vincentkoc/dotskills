#!/usr/bin/env python3
"""Snapshot a tmux lane and recent Codex logs for lane-manager cold starts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
from collections import deque
from pathlib import Path
from typing import Any


OPS_TO_LANE = {1: 1, 3: 2, 5: 3}


def run_tmux(args: list[str], timeout: int = 5) -> str:
    try:
        result = subprocess.run(
            ["tmux", *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.rstrip("\n")


def infer_lane() -> tuple[int | None, str]:
    current = run_tmux(["display", "-p", "#{session_name}\t#{window_name}\t#{pane_index}"])
    if not current:
        return None, "not running inside tmux or tmux unavailable"
    session, window, pane_raw = (current.split("\t") + ["", "", ""])[:3]
    try:
        pane = int(pane_raw)
    except ValueError:
        return None, f"cannot parse current pane index from {current!r}"
    if window == "ops" and pane in OPS_TO_LANE:
        return OPS_TO_LANE[pane], f"inferred from {session}:ops.{pane}"
    return None, f"no manager mapping for {session}:{window}.{pane}"


def list_lane_panes(session: str, lane: int) -> list[dict[str, str]]:
    fmt = "#{pane_index}\t#{pane_title}\t#{pane_current_path}\t#{pane_current_command}\t#{pane_pid}\t#{pane_active}"
    output = run_tmux(["list-panes", "-t", f"{session}:L{lane}", "-F", fmt])
    panes: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = (line.split("\t") + [""] * 6)[:6]
        panes.append(
            {
                "pane": f"L{lane}.{parts[0]}",
                "title": parts[1],
                "cwd": parts[2],
                "command": parts[3],
                "pid": parts[4],
                "active": "yes" if parts[5] == "1" else "no",
            }
        )
    return panes


def capture_pane(session: str, lane: int, pane: str, lines: int) -> str:
    target = f"{session}:L{lane}.{pane}"
    output = run_tmux(["capture-pane", "-p", "-J", "-S", f"-{lines}", "-t", target])
    cleaned = "\n".join(line.rstrip() for line in output.splitlines())
    return cleaned.strip()


def recent_session_dirs(root: Path, max_days: int = 7) -> list[Path]:
    try:
        dirs = [path for path in root.glob("20[0-9][0-9]/*/*") if path.is_dir()]
    except OSError:
        return []
    return sorted(dirs, key=lambda path: path.stat().st_mtime, reverse=True)[:max_days]


def recent_codex_logs(limit: int) -> list[Path]:
    root = Path.home() / ".codex" / "sessions"
    if not root.exists():
        return []
    today = dt.datetime.now().strftime("%Y/%m/%d")
    today_dir = root / today
    candidates = list(today_dir.glob("*.jsonl")) if today_dir.exists() else []
    if len(candidates) < limit:
        for day_dir in recent_session_dirs(root):
            if day_dir == today_dir:
                continue
            candidates.extend(day_dir.glob("*.jsonl"))
            if len(candidates) >= limit * 3:
                break
    unique = {path.resolve(): path for path in candidates}
    return sorted(unique.values(), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]


def text_from_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        chunks: list[str] = []
        for key in ("message", "output", "cmd", "arguments", "text"):
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
    return ""


def compact(text: str, max_len: int = 220) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3].rstrip() + "..."


def recent_lines(path: Path, max_lines: int = 600) -> list[str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return list(deque(handle, maxlen=max_lines))
    except OSError:
        return []


def scan_log_meta(path: Path) -> tuple[str, str]:
    session_id = ""
    cwd = ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, raw in enumerate(handle, start=1):
                if line_number > 40:
                    break
                try:
                    item = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                payload = item.get("payload", {})
                if item.get("type") == "session_meta":
                    session_id = str(payload.get("id", session_id))
                    cwd = str(payload.get("cwd", cwd))
                elif item.get("type") == "turn_context":
                    cwd = str(payload.get("cwd", cwd))
    except OSError:
        return "", ""
    return session_id, cwd


def extract_log_hints(paths: list[Path], pane_cwds: set[str], keywords: list[str]) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    keyword_re = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE) if keywords else None
    for path in paths:
        session_id, cwd = scan_log_meta(path)
        seen: list[str] = []
        for raw in recent_lines(path):
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            payload = item.get("payload", {})
            if item.get("type") == "session_meta":
                session_id = str(payload.get("id", session_id))
                cwd = str(payload.get("cwd", cwd))
            elif item.get("type") == "turn_context":
                cwd = str(payload.get("cwd", cwd))
                continue
            elif item.get("type") == "event_msg":
                if payload.get("type") not in {"agent_message", "user_message"}:
                    continue
            elif item.get("type") == "response_item":
                if payload.get("type") != "message":
                    continue
                if payload.get("role") not in {"user", "assistant"}:
                    continue
            else:
                continue
            text = text_from_payload(payload)
            if not text:
                continue
            cwd_hit = cwd in pane_cwds if cwd else False
            keyword_hit = bool(keyword_re.search(text)) if keyword_re else False
            if cwd_hit or keyword_hit:
                seen.append(compact(text))
        if seen:
            hints.append(
                {
                    "file": str(path),
                    "session_id": session_id or "(unknown)",
                    "cwd": cwd or "(unknown)",
                    "mtime": dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                    "latest": seen[-1],
                }
            )
    return hints[:12]


def guess_state(command: str, capture: str) -> str:
    lowered = capture.lower()
    if command in {"zsh", "bash", "sh"} and re.search(r"\n[^ \n].*[>%$#]\s*$", capture):
        return "idle?"
    if any(token in lowered for token in ("error:", "failed", "cannot find package", "err_package_path_not_exported")):
        return "blocked?"
    if any(token in lowered for token in ("waiting", "watch", "in_progress", "capacity", "running")):
        return "waiting/progress?"
    if command and command not in {"zsh", "bash", "sh"}:
        return "active?"
    return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", type=int, help="Lane number, e.g. 1 for L1.")
    parser.add_argument("--session", help="tmux session name. Defaults to current session.")
    parser.add_argument("--capture-lines", type=int, default=80)
    parser.add_argument("--log-limit", type=int, default=12)
    parser.add_argument(
        "--keywords",
        default="openclaw,plugin-inspector,clownfish,CodeQL,codeql,Testbox,blacksmith,check:changed,Claude,docs,CI",
    )
    args = parser.parse_args()

    session = args.session or run_tmux(["display", "-p", "#{session_name}"]) or os.environ.get("TMUX_SESSION") or ""
    if not session:
        print("error: cannot determine tmux session")
        return 1

    lane = args.lane
    if lane is None:
        lane, reason = infer_lane()
        print(f"infer: {reason}")
    if lane is None:
        print("error: pass --lane explicitly")
        return 1

    panes = list_lane_panes(session, lane)
    if not panes:
        print(f"error: no panes found for {session}:L{lane}")
        return 1

    home = str(Path.home())
    pane_cwds = {pane["cwd"] for pane in panes if pane["cwd"] and pane["cwd"] != home}
    keywords = [part.strip() for part in args.keywords.split(",") if part.strip()]
    log_hints = extract_log_hints(recent_codex_logs(args.log_limit), pane_cwds, keywords)

    print(f"lane L{lane} snapshot")
    print(f"session: {session}")
    print()
    print("panes:")
    for pane in panes:
        pane_index = pane["pane"].split(".")[-1]
        capture = capture_pane(session, lane, pane_index, args.capture_lines)
        last_line = compact(capture.splitlines()[-1] if capture.splitlines() else "")
        state = guess_state(pane["command"], capture)
        print(
            f"- {pane['pane']} state={state} active={pane['active']} cmd={pane['command']} "
            f"pid={pane['pid']} cwd={pane['cwd']} title={pane['title']!r}"
        )
        if last_line:
            print(f"  last: {last_line}")
    print()
    print("codex log hints:")
    if not log_hints:
        print("- none found from recent logs")
    for hint in log_hints:
        print(f"- {hint['session_id']} cwd={hint['cwd']} mtime={hint['mtime']}")
        print(f"  latest: {hint['latest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
