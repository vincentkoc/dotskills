---
name: codex-goal-mining
description: Mine structured Codex /goal history locally or across a configured machine fleet, measure active goal time and resumed thread spans, identify unfinished and recurring semantic runs, and turn them into stable copy-paste rerun suites. Use when the user asks to inspect goal history, summarize goal commands, find repeated goals, recover large beta campaigns, compare goal duration or token usage, or prepare reusable /goal prompts and privacy-scrubbed reports.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Codex Goal Mining

## Purpose
Recover structured Codex goal history and convert free-form runs into evidence-backed, repeatable suites.

## When to use
- The user asks what `/goal` commands ran locally or across the fleet.
- Large QA, beta, release, localization, model, cleanup, or PR campaigns need retesting.
- The user wants active, paused, blocked, or long-running goals ranked.
- Repeated semantic runs need stable suite names and copy-paste prompts.
- Goal time, thread span, tokens, dates, machines, or reachability matter.

## Workflow
1. Collect structured data with `scripts/codex-goal-report.py`.
   - Fleet report: `scripts/codex-goal-report.py --policy ~/.config/codex-goal-mining/fleet-policy.json --json --output ~/.codex/reports/codex-fleet-goals.json`
   - Local only: `scripts/codex-goal-report.py --local --json`
   - Recent window: add `--since YYYY-MM-DD`.
   - Exact activity window: add `--activity-overlap --since <ISO> --until <ISO>`.
     Existing `--since` semantics remain creation-time based without that flag.
   - Bounded repeat snapshots: add `--cursor-file <path>` to compute reset-safe
     deltas. No cursor or report directory is created by default.
   - Selected machines: repeat `--machine <fleet-alias>`.
   - Require fleet coverage with `--fleet`; any unreachable source is rendered
     and returns nonzero instead of silently reporting success.
   - Use `--one-attempt` for a single configured/first interpreter attempt per
     host. Policy entries may declare `python` and `wsl_python`.
   - Start fleet configuration from `references/fleet-policy.example.json`; never commit a real private inventory.
2. Treat the data sources correctly.
   - Prefer `goals_1.sqlite` for objective, status, tokens, and Codex-recorded active goal time.
   - Join `state_5.sqlite` for thread timestamps and rollout paths.
   - Use JSONL only as a fallback for older installations.
   - Wall-clock thread span includes idle and resume gaps; never describe it as active labor.
   - Goal database counters are lifetime snapshots. Only cursor deltas have an
     observation interval, and a reset is unknown rather than zero.
   - Preserve root/child identity where the state database supplies it. JSONL
     fallback reports unknown rather than guessing.
3. Report collection coverage first.
   - List reached and unreachable machines.
   - Give the date range, goal count, statuses, total active goal time, and median goal time.
   - Preserve exact transport blockers instead of silently shrinking the fleet.
4. Mine patterns semantically.
   - Exact duplicate text is weak evidence because operators rephrase goals.
   - Cluster by intended test surface, matrix, exit criteria, and repeated operating contract.
   - Prioritize unfinished goals and recurring high-time campaigns.
   - Separate product beta suites from operational queues such as contributor PR sweeps.
5. Produce reusable reruns.
   - Use `[suite:<name>] [baseline:<sha-or-date>] [matrix:<targets>] [exit:<criteria>]`.
   - Include a fixed matrix, evidence requirements, blocker rules, and definition of done.
   - Start from `references/goal-suite-patterns.md`, then adapt to current evidence.
6. Keep reports private.
   - Default to terminal/JSON delivery. Use `--output` only when retained output
     was requested or required.
   - Scrub secrets, private hosts, personal absolute paths, and credentials before creating a gist or sharing externally.
   - Use a secret gist unless the user explicitly requests public visibility.
7. For retained output or resumable collection state, apply the task artifact
   contract from `$operations-worktree`. Reuse identity-matched canonical
   inventories instead of copying large payloads.

## Inputs
- Local Codex stores under `~/.codex/`.
- Optional fleet policy supplied with `--policy` or `CODEX_FLEET_POLICY`.
- Optional date window, machine aliases, suite focus, or output path.

## Outputs
- Markdown or JSON fleet goal report.
- Ranked active, paused, blocked, and long-running goals.
- Semantic campaign summary with timing and reachability caveats.
- Stable copy-paste `/goal` suite prompts and rerun priority order.
