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
- In maintainer Testbox-only lanes, all `pnpm` validation/check/test/build/format/docs-list commands must run inside Blacksmith Testbox. Non-pnpm `git`, `gh`, and file inspection can stay local.
- If `OPENCLAW_TESTBOX=1 pnpm <script>` still starts local work, interrupt it and switch to an explicit Blacksmith run such as `blacksmith testbox run --id <tbx> "env OPENCLAW_TESTBOX=1 pnpm <script>"` or the repo's explicit `pnpm testbox -- pnpm <script>` path.
- Track Testbox ids, GitHub run ids, PR/issue URLs, branch/worktree path, and exact failing shard.
- Fetch/rebase onto current `origin/main` immediately before changed gates. If Testbox pulls unrelated failures from a stale base, rebase first and rerun in the same box before blaming the patch.
- If a Testbox sync leaves remote dependencies missing, classify it as Testbox environment drift and repair inside the box; do not run `pnpm install` in the local Codex worktree or label missing packages as product failures.
- After repeated passing cheap checks on a hot `main`, switch to a tight last-mile push loop: fetch, rebase, `git diff --check origin/main..HEAD`, push `HEAD:main`, and retry a bounded number of times on non-fast-forward rejection. Do not keep rerunning slow lint between every rejected push unless the rebase touches that surface.
- If a patch supersedes an in-flight Testbox/CI run, stop or ignore the stale run with that reason recorded. Poll the exact current run instead of starting more validation lanes.
- For local sparse Codex worktrees, node dependency failures can be local setup noise. Verify inside Testbox or the canonical repo before declaring product failure.
- For CodeQL, distinguish stale analyses from current `main` analyses. Re-check `commit_sha`, `ref`, category, analysis key, and `results_count`.
- When new CodeQL runners/categories land, do not allocate implementation from the old open-alert count alone. Inspect recent analyses first:
  - if current critical/security categories show `results_count=0` and remaining alerts point at an old default-profile commit, split closeout-only dismissal buckets by category/path;
  - if an alert has a current `main` instance, allocate a fixer for that concrete file/rule family;
  - for GitHub API dismissal, use the accepted reason and a short evidence comment when "fixed" is not an accepted enum.
- For clownfish, the real queue may be local markdown/jobs, not GitHub issues. Confirm the actual queue root before mutating jobs.
- For docs lanes, require a code-change-to-doc-impact link. No-op audits are valid output when docs already match.
- For plugin lifecycle or inspector sweeps, classify findings before assigning fixes:
  - plugin-surface defects: runtime capture API mismatches, missing exported aliases, registration output polluting JSON protocols, or actual install/doctor/enable-disable failures;
  - fixture/harness debt: missing test config such as embedding settings, sparse checkout gaps, Testbox full-sync dependency drift, Docker shard silence, or local `node_modules` loss;
  - suspicious-but-unproven: one slow plugin or a retry that later passes. Keep watching, but do not file it as a product bug yet.

## Worker launch rules

When the operator asks to spin up new OpenClaw work in a lane:

- Create or verify a fresh `gwt` worktree from current `origin/main` unless the operator gives an existing worktree.
- Wait for `gwt` setup enough to verify `node_modules` is a symlink before launching Codex there.
- Create worktrees one at a time when the wrapper is slow; if `gwt` hangs after producing the tree, verify the tree instead of killing blindly.
- Use `bash` or non-special variable names for worktree creation loops; zsh's `path` array can wreck branch/path lists.
- Put the exact worktree path in the worker prompt and explicitly say not to use the main checkout.
- Tell workers not to run `pnpm install` in Codex worktrees.
- Tell workers to commit/push small slices to `main` only after scoped proof, and to use Testbox for broad validation.
- For OpenClaw PR closeout lanes, include the stricter rule up front: no direct local `pnpm` validation/check/test/build/format/docs-list. Use Blacksmith Testbox for every `pnpm` command.
- Launch in YOLO/no-sandbox mode from the target cwd with the prompt file passed as Codex's initial prompt argument; do not paste large here-docs into multiple panes or use stdin redirection for Codex TUI launches.
- After launch, press Enter/CR if the initial prompt is staged but not submitted, then verify cwd, pane title, first Codex screen, directory trust prompts, and that the worker received the intended mission.

For OpenClaw-adjacent review-only repos such as `clawbench`, do not force the `gwt` pattern unless the operator asks for implementation. Clone or pull the target repo, launch YOLO from that checkout, and keep the worker review-first with no code edits.

## Coordinator and queue rules

- For parallel CodeQL/security remediation, split by disjoint files or alert families, then appoint exactly one final coordinator to cherry-pick/integrate/rebase/push.
- For CodeQL closeout after fixes land, split API-only dismissal buckets by old category/path, forbid file edits and pushes, require per-alert stale signature proof, and re-read alert state after mutation.
- Branch-only slice workers must stop after reporting commit SHA, checks, branch HEAD, and blockers when a coordinator takes over.
- Before taking over a stuck coordinator, inspect existing Testbox ids and local processes. If a check is still running, wait or reuse it; if it is only `ready`/stale, record that and run cheap checks rather than another broad gate.
- For PR queues, keep the queue state local to the manager: pending, assigned, blocked, merged, closure-needed, done. Reassign only after checking live PR metadata.
- For clownfish or other backlog reducers, track live issue/PR counts with baseline and delta. If the queue worker stops to explain failed jobs, classify it as needs-manager and either kick it back into queue handling or ask the operator whether to inspect the failures.
- Closure workers must address unresolved review/Aisle/Greptile comments or prove they are stale, then close linked duplicate/stale issues and PRs with a short thankful reason tied to the merged PR.
- If the operator issues an urgent policy update, broadcast it to every worker, submit it with Enter/CR, verify it appears in each worker log, and collect each worker's report of any local command already started.

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
