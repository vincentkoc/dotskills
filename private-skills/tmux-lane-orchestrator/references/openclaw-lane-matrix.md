# OpenClaw Lane Matrix

Use this reference when the lane is running OpenClaw or adjacent OpenClaw maintainer work.

## Current cockpit mapping

- `ops.1` manages `L1`.
- `ops.3` manages `L2`.
- `ops.5` manages `L3`.
- Even `ops` panes are spare shells unless the operator assigns them.

## Lane 1 missions from operator handoff

Treat the latest user-provided map as authoritative. This captured handoff is useful only as a starting point:

- `L1.1`: validate plugin refactors on `main` with Testbox, especially against `openclaw/plugin-inspector`, and surface live SDK/plugin export issues.
- `L1.2`: run `openclaw/clownfish` / `projectclownfish` dedupe and PR-cluster fix dispatch.
- `L1.3`: fix CI issues on `main` in a loop.
- `L1.4`: CodeQL fixes and current-profile CodeQL verification.
- `L1.5`: empty unless assigned.
- `L1.6`: Claude Code cron/timer lane for docs auditing and fixes.

If the operator repeats a pane id or gives conflicting assignments, preserve the raw handoff and mark the conflict in the summary.

## OpenClaw operating rules

- Respect active worker ownership. Inspect before intervening.
- Do not start duplicate heavy checks if a worker already has a Testbox, GitHub Actions run, or local heavy-check lane active.
- Prefer Testbox evidence for broad, Docker, live, E2E, release, and complex validation.
- Track Testbox ids, GitHub run ids, PR/issue URLs, branch/worktree path, and exact failing shard.
- For local sparse Codex worktrees, node dependency failures can be local setup noise. Verify inside Testbox or the canonical repo before declaring product failure.
- For CodeQL, distinguish stale analyses from current `main` analyses. Re-check `commit_sha`, category, and `results_count`.
- For clownfish, the real queue may be local markdown/jobs, not GitHub issues. Confirm the actual queue root before mutating jobs.
- For docs lanes, require a code-change-to-doc-impact link. No-op audits are valid output when docs already match.

## Worker launch rules

When the operator asks to spin up new OpenClaw work in a lane:

- Create or verify a fresh `gwt` worktree from current `origin/main` unless the operator gives an existing worktree.
- Wait for `gwt` setup enough to verify `node_modules` is a symlink before launching Codex there.
- Create worktrees one at a time when the wrapper is slow; if `gwt` hangs after producing the tree, verify the tree instead of killing blindly.
- Use `bash` or non-special variable names for worktree creation loops; zsh's `path` array can wreck branch/path lists.
- Put the exact worktree path in the worker prompt and explicitly say not to use the main checkout.
- Tell workers not to run `pnpm install` in Codex worktrees.
- Tell workers to commit/push small slices to `main` only after scoped proof, and to use Testbox for broad validation.
- Launch in YOLO/no-sandbox mode from the target cwd with the prompt file passed as Codex's initial prompt argument; do not paste large here-docs into multiple panes or use stdin redirection for Codex TUI launches.
- After launch, verify cwd, pane title, first Codex screen, directory trust prompts, and that the worker received the intended mission.

For OpenClaw-adjacent review-only repos such as `clawbench`, do not force the `gwt` pattern unless the operator asks for implementation. Clone or pull the target repo, launch YOLO from that checkout, and keep the worker review-first with no code edits.

## Coordinator and queue rules

- For parallel CodeQL/security remediation, split by disjoint files or alert families, then appoint exactly one final coordinator to cherry-pick/integrate/rebase/push.
- Branch-only slice workers must stop after reporting commit SHA, checks, branch HEAD, and blockers when a coordinator takes over.
- Before taking over a stuck coordinator, inspect existing Testbox ids and local processes. If a check is still running, wait or reuse it; if it is only `ready`/stale, record that and run cheap checks rather than another broad gate.
- For PR queues, keep the queue state local to the manager: pending, assigned, blocked, merged, closure-needed, done. Reassign only after checking live PR metadata.
- Closure workers must address unresolved review/Aisle/Greptile comments or prove they are stale, then close linked duplicate/stale issues and PRs with a short thankful reason tied to the merged PR.

## Status heuristics

- `active-progress`: commands are still producing output, workers are dispatching jobs, Testbox/GitHub run is advancing, or the agent reports a patch/test loop.
- `waiting`: watcher is polling CI/Testbox/capacity with no error yet.
- `blocked`: failed import, failed shard, auth/org missing, merge conflict, stale dependency, unavailable Testbox, or unclear duplicated work.
- `idle`: visible shell prompt plus no active mission and no fresh Codex log evidence.
- `needs-manager`: duplicated checks, stale lane map, worker asks for decision, or current action risks external mutation.

## Summary priorities

Report these first:

1. Lane-wide hazards: duplicate broad checks, unsafe external mutation, missing auth, or stuck Testbox/GitHub capacity.
2. Blocked workers with exact failure text and the least-risk next action.
3. Workers making progress with concrete counts/run ids.
4. Idle capacity that can take the next job.
