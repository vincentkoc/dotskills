---
name: codex-session-recovery
description: Recover Codex or Claude sessions from tmux panes, saved cockpit snapshots, session history, and recent agent logs without overwriting useful restore evidence. Use when a pane crashes, detaches, loses visible context, needs a resume command, or requires a safe targeted restore plan.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Codex Session Recovery

## Purpose

Recover crashed, detached, or confusing agent sessions while preserving the best restore source.

## When to use

- Recover a Codex, Claude, or tmux cockpit session.
- Find an exact `codex resume <id>` command.
- Preview or restore saved pane/window/session state.
- Repair missing snapshot history or tmux menu bindings.

## Workflow

1. Preserve evidence before writing state.
   - Do not create a new snapshot until the restore candidate is known.
   - Do not run repair commands that overwrite history.
   - Set a recovery pane title when possible.
2. Inspect live tmux state.
   - `tmux display-message -p '#S:#I.#P #{pane_current_command} #{pane_current_path}'`
   - `tmux list-panes -a -F '#S:#I.#P #{pane_pid} #{pane_current_command} #{pane_current_path}'`
   - Inspect relevant key bindings before re-sourcing tmux configuration.
3. Inspect available recovery sources.
   - Prefer the operator's snapshot/history helper when installed.
   - Inspect recent `~/.codex/sessions/YYYY/MM/DD/*.jsonl` metadata for session IDs and working directories.
   - Cross-check pane PIDs, cwd, and recent logs before selecting a session.
4. Produce a dry-run plan first.
   - Prefer one-pane or one-window restore over whole-session restore.
   - Show the snapshot or session ID, target pane, and exact command.
5. Execute only with clear intent.
   - Require explicit intent before restore commands that mutate tmux state.
   - Never kill broad Codex, Claude, tmux, or terminal processes from name matches alone.
   - Restrict cleanup to the exact pane, PID, process group, or current-task resource.
6. Stay narrow for session-ID requests.
   - Return the concrete ID and `codex resume <id>` first.
   - Add the broader recovery method only when requested.

## Inputs

- Optional tmux pane or window target.
- Optional saved snapshot path.
- Optional mode: session-ID lookup, preview, targeted restore, or menu repair.
- Optional local snapshot helper such as `tt`.

## Outputs

- Exact resume command when available.
- Selected restore source and target.
- Dry-run restore plan before execution.
- Concise blocker when evidence is insufficient.
