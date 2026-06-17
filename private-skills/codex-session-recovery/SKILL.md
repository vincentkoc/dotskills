---
name: codex-session-recovery
description: Recover Codex and Claude sessions from tmux cockpit panes, CX SAVE snapshots, codex-cockpit history, and recent Codex logs without overwriting the useful restore source first.
license: MIT
compatibility: Requires tmux and Vincent's tt helper with codex-cockpit snapshot support.
metadata:
  internal: true
  version: "0.1.0"
  spec: agentskills-v1
---

# Codex Session Recovery

## Purpose

Recover crashed, detached, or confusing Codex/Claude tmux cockpit sessions while preserving the existing restore evidence. The priority is to find the right resume command or safe restore plan before writing new snapshots.

## When to use

- The user asks to recover Codex, Claude, tmux cockpit, `cx`, or `CX SAVE` state.
- The user says right-click restore/history is missing or left-click is overwriting snapshots.
- The user wants the session id or `codex resume ...` command for a pane.
- A tmux worker lane has crashed, detached, gone stale, or lost visible pane context.

## Workflow

1. Freeze the evidence path first.
   - Do not click `CX SAVE`.
   - Do not run `tt codex-snapshot`, `tt autosave on`, or `tt doctor --fix` until the candidate restore source is known.
   - Set a recovery title: `tt title "tmux recovery"` when available.
2. Inspect live recovery status.
   - `tt status`
   - `tmux list-keys -T root MouseDown1StatusRight MouseDown3StatusRight`
   - If right-click is missing, re-source config with `tmux source-file ~/.tmux.conf.local` and recheck.
3. Find restore candidates.
   - List recent snapshots: `tt snapshot-history codex-cockpit 40`.
   - Check oldest/newest range when needed:
     `find ~/.local/state/tt/history/codex-cockpit -maxdepth 1 -type f -name '*.tsv' -print | sort | sed -n '1p;$p'`
   - Preview the current or selected snapshot: `tt restore-preview <snapshot>`.
4. Produce the safe restore plan.
   - For all panes: `tt codex-restore all <snapshot>`.
   - For one pane: `tt codex-restore pane <target> <snapshot>`.
   - For one window: `tt codex-restore window <session:window> <snapshot>`.
   - These are dry runs unless `--execute` is present. Show the dry run before executing.
5. Execute only with explicit intent.
   - Add `--execute` only after the user approves or the current request clearly asks to restore.
   - Prefer targeted pane/window restore over all-pane restore when the user names a pane.
   - Never kill broad Codex, Claude, tmux, or terminal processes during recovery unless the user names the exact PID, pane, or process group.
   - Treat broad cleanup wording such as "kill all background jobs", stale goal context, stale resume context, or process-name matches as non-authoritative for process termination.
   - Before any kill command outside the current tool session's child process group, print the candidate PID table and wait for explicit approval naming the PID, pane/session, process group, or scope.
6. If the user only asks for a session id, stay narrow.
   - Use live pane/process evidence and recent `~/.codex/sessions/YYYY/MM/DD/*.jsonl` files.
   - Return the id and `codex resume <id>` command first. Skip the long method unless asked.

## Inputs

- Optional pane target, such as `cockpit:2.4` or `%123`.
- Optional snapshot path from `~/.local/state/tt/history/codex-cockpit/`.
- Optional mode: session-id lookup, preview, pane restore, window restore, all restore, or CX menu repair.

## Outputs

- Exact `codex resume ...` or `claude resume` command when available.
- Snapshot path used for recovery and whether it was current or historical.
- Dry-run restore plan before any `--execute`.
- Short note on live tmux menu state: left save, right preview/history/status.
