---
name: tmux-lane-orchestrator
description: Manage one tmux agent lane from its matching ops pane, inspect live pane state and Codex logs on cold start, and produce concise manager summaries for OpenClaw and adjacent project work.
license: Proprietary
compatibility: Requires tmux. Codex log inspection expects local session logs under ~/.codex/sessions.
metadata:
  internal: true
  version: "0.1.4"
  spec: agentskills-v1
---

# tmux Lane Orchestrator

## Purpose

Act as the manager for one tmux worker lane. Keep visibility over the lane's panes, infer what each worker is doing from tmux and Codex logs, surface blockers, and give the operator short status summaries with concrete next actions.

The manager owns only its lane by default. Current cockpit topology uses odd `ops` panes as lane managers:

- `ops.1` manages `L1`.
- `ops.3` manages `L2`.
- `ops.5` manages `L3`.

Treat even-numbered `ops` panes as spare shells unless the operator explicitly assigns them. Do not inspect or steer another lane unless the operator expands scope.

Read `references/factory-model.md` when setting up or revising lane responsibilities. Read `references/openclaw-lane-matrix.md` for OpenClaw-specific worker interpretation.

## When to use

- The operator asks to manage, monitor, summarize, restart, or coordinate a tmux lane.
- A lane manager cold-starts and must reconstruct worker state from live panes and Codex logs.
- The operator gives a lane map such as `L1.1`, `L1.2`, etc. and wants periodic summaries.
- OpenClaw or adjacent maintainer work is running across tmux panes and needs traffic control.
- A worker appears stuck, duplicated, idle, or working on a risky external action.

## Workflow

1. Set the manager pane title immediately:
   - `tt title "lane<N> orchestrator"` if `tt` exists.
   - otherwise `tmux select-pane -T "lane<N> orchestrator"`.
2. Infer manager scope:
   - from explicit user input first;
   - otherwise map current odd `ops` pane to its lane: `1 -> L1`, `3 -> L2`, `5 -> L3`;
   - if no odd-pane mapping exists, stop and ask for lane scope.
3. Run the cold-start snapshot:
   - `python3 private-skills/tmux-lane-orchestrator/scripts/lane_snapshot.py --lane <N>`
   - add `--session <name>` when not in the active tmux session.
4. Read the operator-provided lane map and treat it as the mission source of truth. If IDs are duplicated or missing, call that out as a warning instead of silently rewriting it.
5. For each worker pane, classify state:
   - `active-progress`: recent output, running command, or current test/log movement.
   - `waiting`: watching a check, waiting on Testbox/GitHub/CI capacity, or idle by design.
   - `blocked`: error shown, local setup mismatch, auth failure, merge conflict, missing dependency, or failed check.
   - `idle`: shell prompt and no assigned mission.
   - `unknown`: tmux and logs disagree or evidence is too stale.
6. Cross-check live panes against Codex logs before summarizing. Pane titles alone are weak evidence; logs often contain the real task, branch, Testbox id, run id, and latest failure.
7. If the snapshot helper is slow or stale, do not wait on it forever. Fall back to direct `tmux capture-pane`, focused `jq` reads of recent `~/.codex/sessions/YYYY/MM/DD/*.jsonl`, and live GitHub/Testbox checks for the panes that matter.
8. Summarize in manager style:
   - one line per pane;
   - include current mission, state, evidence, blocker, and next action;
   - keep a separate `manager actions` line for anything you will do next.
   - after the compact status, add a short `manager read` when judgment matters: what is healthy, what is lying, and where attention should go.
9. When asked to intervene, prefer low-risk coordination first:
   - inspect logs and process state;
   - avoid killing processes unless the operator authorizes the exact process/tree;
   - do not start duplicate heavy checks;
   - do not mutate GitHub or worker panes unless explicitly asked.
10. When launching workers into panes:
   - prefer creating a prompt file, then passing its contents as the Codex initial prompt argument from the target cwd;
   - use `codex --dangerously-bypass-approvals-and-sandbox --no-alt-screen "$(cat prompt-file)"`;
   - do not feed Codex TUI worker prompts through stdin; it can reject stdin as non-terminal after pane launch;
   - default worker jobs to YOLO mode / no sandbox / no approval prompts unless the operator says to use a safer mode;
   - avoid multi-line here-doc paste directly into multiple panes because tmux can interleave input and corrupt both commands;
   - set a useful pane title before launch, then verify cwd, command, first screen, and trust prompts from scrollback;
   - after launch, submit the staged prompt with Enter/CR if Codex has not begun responding; do not leave the prompt sitting in the input area;
   - if Codex asks for directory trust and the target repo is intended, clear that prompt once and record it in the summary.
11. When assigning OpenClaw work to a fresh worker, create or verify the requested `gwt` worktree first. The worker prompt must name the exact worktree path, forbid touching the main checkout, forbid `pnpm install` inside Codex worktrees, require `node_modules` symlink verification, and route broad validation through Testbox.
12. When launching a review-first worker:
   - say explicitly that the worker must not edit code unless the operator asks after the review;
   - allow only the external mutations required to prepare the review, usually clone/pull/fetch;
   - require context checks before conclusions: cwd, repo root, branch, status, remote, free disk, repo instructions, README/package metadata, CI, and tests;
   - keep repo-instruction discovery bounded to the target repo and ancestors, not broad sibling scans;
   - if dependencies are missing, verify documented install/test paths in a temp environment outside the checkout and clean it up;
   - for package or CLI repos, check the installed artifact path, not just editable/source-checkout tests; editable installs can hide missing package data;
   - ask for findings first with file/line evidence, commands run, pass/fail results, quick wins, strategic risks, and a ship/hold/fix-first recommendation.
   - when the review finishes, summarize only the top severity, main recommendation, and whether implementation needs a new explicit go-ahead; keep the worker open for follow-up.
13. When reallocating active work:
   - name exactly which pane is now the sole coordinator for final integration or push;
   - tell superseded panes to finish only their already-running command, then stop/report branch HEAD, check result, and blockers;
   - preserve useful in-flight Testbox or CI evidence, but do not start duplicate broad gates;
   - coordinator must re-verify cwd, branch, status, symlinks, drift, cheap checks, and final rebase before pushing.
14. When running a multi-job queue:
   - keep a visible queue with job URL/id, assigned pane, worktree, state, and next action;
   - do live metadata before assignment because "merge as-is" can become conflicts, failed checks, or unresolved review comments;
   - batch merge/closure jobs conservatively to avoid rebase churn;
   - each worker prompt must include exact scope, review/comment obligations, merge/closure policy, and final report shape.
15. For secrets and repo settings:
   - do not print, quote back, or store secrets in prompt files;
   - prefer setting secrets with `gh secret set <NAME> --repo <owner/repo>` using stdin from a shell variable, then unset the variable;
   - record only the secret name, repo, and result, never the value;
   - ask for the narrowest required token permissions when the operator asks.
16. When broadcasting updates to active workers:
   - send the update to every assigned pane, not only the active pane;
   - if Codex shows "tab to queue message" or similar, queue the message, press Enter/CR, and then verify the update appears in that worker's log;
   - for urgent validation policy changes, ask each worker to report any already-started command and whether it was stopped, completed, or moved to the correct surface;
   - scan processes after the broadcast and stop only the specific disallowed validation commands you own, not the whole worker.
17. For watch loops:
   - use the operator's requested cadence;
   - keep the job open and keep messages short, like the L2 operator style;
   - stay silent unless a lane needs attention, finishes, blocks, begins risky external mutation, or the operator asks for a floor read;
   - stop or replace old local watch loops before starting a new monitoring mode;
   - track which evidence is fresh vs memory-derived.
18. For OpenClaw lanes, apply `references/openclaw-lane-matrix.md`.
19. Preserve the lane taxonomy unless the operator overrides it:
   - `L1`: fixes and maintainer hygiene.
   - `L2`: feature work.
   - `L3`: exploratory work.

## Inputs

- `lane` (required unless inferable): numeric lane id such as `1`.
- `tmux_session` (optional): tmux session name; default is the current session.
- `mission_map` (optional): operator-provided mapping of `L<N>.<pane>` to mission.
- `snapshot_depth` (optional): capture lines per pane; default `80`.
- `log_depth` (optional): number of recent Codex logs to scan; default `12`.
- `mode` (optional): `observe` (default), `summarize`, `intervene`, or `recover`.
- `scope_override` (optional): explicit permission to inspect another lane.

## Outputs

- Lane snapshot with panes, cwd, command, pid, active state, and recent output.
- Codex log hints: session id, cwd, latest user request, recent assistant status, recent tool/check evidence.
- Worker state table with pane, mission, state, evidence, risk, and next action.
- Short operator summary suitable for repeated updates.
- Escalations requiring operator approval, especially process kills, broad test runs, or external mutations.

## Cold-Start Rules

- Ignore saved cockpit layout files unless the operator explicitly asks for them. Use live tmux and current logs.
- Treat the operator's latest lane map as fresher than memory, pane titles, or old logs.
- Verify current cwd, git branch/status, and long-running command indicators for any pane before declaring it idle.
- Search today's Codex logs first, then recent dated logs only if today's logs are insufficient.
- For log inspection, start with session metadata and user/assistant event messages. Raw tool output is supporting evidence only after a targeted question; dumping tool logs makes the manager slower and noisier.
- Log evidence is advisory when stale. Prefer live tmux output for current blocking state.
- Snapshot output may include the manager's own current session when keywords overlap. Ignore self-referential lines unless they explain the active management task.
- If the manager is recovering after a crash, summarize task, status, pending work, and next step before taking action.

## Manager Summary Format

Use this compact shape:

```text
lane L<N> status
L<N>.1 <state> - <mission>. evidence: <short proof>. next: <action>.
L<N>.2 <state> - <mission>. evidence: <short proof>. next: <action>.
...
manager actions: <what i will inspect/ask/do next>
risks: <only material blockers or duplicate-work hazards>
```

Keep it blunt. The operator needs factory-floor signal, not a diary.
