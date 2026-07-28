---
name: tmux-agent-lane-orchestrator
description: Monitor and coordinate one tmux agent lane, reconstruct worker state from panes and recent Codex logs, classify progress and blockers, and produce concise manager summaries. Use when multiple coding-agent workers run in tmux windows named L1, L2, and similar lane identifiers.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# tmux Agent Lane Orchestrator

## Purpose

Turn a tmux window of coding-agent workers into a visible, auditable lane with clear state and next actions.

## When to use

- Monitor or summarize a tmux worker lane.
- Reconstruct worker state after a manager cold start.
- Detect duplicated, idle, waiting, blocked, or risky work.
- Coordinate several coding-agent panes without mutating them blindly.

## Workflow

1. Establish lane scope.
   - Prefer an explicit lane number.
   - Otherwise infer it from a current tmux window named `L<number>`.
   - Do not inspect other lanes unless the operator expands scope.
2. Capture lane state.
   - `python3 scripts/lane_snapshot.py --lane <number>`
   - Add `--session <name>` outside the active tmux session.
   - Override `--keywords` for repository-specific log matching.
3. Cross-check panes and logs.
   - Pane titles alone are weak evidence.
   - Compare command, PID, cwd, recent output, and matching `~/.codex/sessions` records.
4. Classify each pane.
   - `active-progress`, `waiting`, `blocked`, `idle`, or `unknown`.
   - Include the evidence and next action, not only the label.
5. Intervene conservatively.
   - Inspect before steering.
   - Avoid duplicate heavy checks.
   - Do not kill or mutate another pane without explicit scope.
   - Prefer reversible actions and targeted commands.
6. Summarize in manager style.
   - One line per pane: mission, state, evidence, blocker, next action.
   - Add one short manager judgment about where attention belongs.

Read `references/factory-model.md` when designing lane responsibilities or escalation policy.

## Inputs

- tmux session name.
- Lane number or `L<number>` window.
- Optional log keywords and capture depth.
- Optional operator-provided worker mission map.

## Outputs

- Current pane and agent-session snapshot.
- Per-pane state classification with evidence.
- Concise manager summary and safe next actions.
