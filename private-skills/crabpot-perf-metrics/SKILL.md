---
name: crabpot-perf-metrics
description: Interpret Crabpot and OpenClaw performance dashboard metrics, import-loop profiles, runtime profiles, and branch-to-branch perf deltas without over-reading noisy samples.
---

## Purpose
Turn Crabpot/OpenClaw perf artifacts into a clear read: what changed, what is real signal, what is stale/noisy, and what action is worth taking.

## When to use
- Comparing `openclaw/crabpot` branches such as `main`, `crab-beta`, or `crab-development`.
- Reading `reports/crabpot-dashboard-data.json`, `reports/crabpot-import-loop-profile.json`, `reports/crabpot-runtime-profile.json`, README dashboard metrics, or GitHub Actions report artifacts.
- The user asks about perf, runtime, CPU, RSS, import loop, OpenClaw import/activate, dashboard deltas, or whether a Crabpot performance change is meaningful.

## Inputs
- Target repo or local checkout, usually `openclaw/crabpot`.
- Branches, refs, PRs, or artifact URLs to compare.
- Optional target OpenClaw labels/SHAs if the comparison crosses `openclaw@latest`, beta, or `openclaw/openclaw@main`.

## Workflow
1. Establish freshness before interpreting numbers.
   - Resolve branch heads and report timestamps.
   - Compare dashboard JSON with raw profile JSON on the same branch.
   - If one branch is stale, say so first and avoid strong conclusions.
   - Prefer raw JSON over README snippets when they disagree.
2. Separate the metric families.
   - `import-loop-profile`: cheap cold capture loop against a tiny fixture. Good for harness/import drift, weak for production runtime claims.
   - `runtime-profile`: macro command timings across Crabpot analysis commands. Better trend signal for real suite cost.
   - `OpenClaw lifecycle`: import plus activate phases. If `openClawLifecycleCount` is `0`, the branch dashboard does not include this signal.
3. Interpret import-loop metrics conservatively.
   - Use `p50WallMs`, `p95WallMs`, `p50PluginWallDeltaMs`, `p95PluginWallDeltaMs`, `maxPluginPeakRssDeltaMb`, and `maxPluginCpuDeltaMsEstimate`.
   - Treat 3-run p95 as "worst of three", not a stable tail latency estimate.
   - A small wall-time bump with flat plugin RSS/CPU usually means jitter or module-resolution overhead, not a memory/CPU regression.
   - Baseline-adjusted plugin deltas are more useful than raw wall/RSS/CPU values.
4. Interpret runtime profile metrics as the stronger trend.
   - Use `summary.p50WallMs`, `summary.p95WallMs`, `summary.maxPeakRssMb`, `summary.maxCpuMsEstimate`, and `summary.maxHarnessHeapDeltaMb`.
   - Inspect per-command medians for the source of change: `fixture-inspection`, `compat-report-registry`, `contract-capture`, `synthetic-probe-plan`, `cold-import-readiness`, `workspace-plan`, `platform-probes`, and `import-loop-profile`.
   - Broadly uniform slowdowns across target-aware commands usually point at target OpenClaw surface parsing or registry work, not one plugin fixture.
   - If RSS is flat and CPU moves only slightly, call it a wall-clock/runtime overhead change, not a memory leak.
5. Account for surface changes.
   - Different fixture counts, entrypoint counts, OpenClaw labels, or commit SHAs make the comparison partly apples-to-oranges.
   - New fixtures can raise issue/probe counts while leaving perf healthy.
   - OpenClaw `main` vs npm `latest` can improve compatibility while adding modest analysis overhead.
6. Give the user a direct read.
   - Start with the conclusion.
   - Prefer bullets and a short summary over tables unless the user asks for a table.
   - Include exact deltas and classify them: `real regression`, `modest slowdown`, `noise`, `stale data`, or `missing signal`.
   - Recommend one next action: refresh dashboard, add a dedicated lifecycle lane, investigate a specific command, or ignore as noise.

## Useful Commands
Use `gh` if `ghx` is unavailable.

Fetch current branch artifacts from GitHub:

```bash
gh api /repos/openclaw/crabpot/contents/reports/crabpot-dashboard-data.json?ref=crab-development
```

Prefer a small Node or `jq` extraction over manual README scraping. Pull these files when available:

- `reports/crabpot-dashboard-data.json`
- `reports/crabpot-import-loop-profile.json`
- `reports/crabpot-runtime-profile.json`
- `reports/crabpot-ci-summary.json`

## Outputs
- Concise perf summary in bullets.
- Freshness caveats when needed.
- Important deltas with interpretation.
- Clear owner/action recommendation, especially when lifecycle import+activate is missing from dashboard artifacts.
