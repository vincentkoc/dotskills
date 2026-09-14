# Slicing Taxonomy

Use multiple slice layers. One lens is too easy to game.

## Feature slices

Source: clawpatch feature records.

Best for:
- package/API/plugin boundaries,
- route or command entrypoints,
- test ownership,
- review units for targeted agent passes.

Watch for:
- hidden worktrees,
- generated output,
- overly broad source-group slices,
- missing framework-specific entrypoints.

## Threat slices

Source: deepsec file records and candidates.

Best for:
- path traversal, SSRF, RCE, auth bypass, secret/log surfaces,
- high-density files,
- framework mismatch gaps where default matchers are weak.

Watch for:
- noisy slug families like generic crypto usage,
- candidate count without exploitability,
- processing cost.

## Issue slices

Source: gitcrawl clusters, threads, summaries, live GitHub checks.

Best for:
- repeated user-visible failures,
- closed-but-recurring regressions,
- duplicate PR/issue clusters,
- maintainer narrative and shipped history.

Watch for:
- stale local crawl state,
- title similarity without root-cause match,
- closed clusters that should only inform risk, not current truth.

## Support slices

Source: discrawl search, digest, analytics.

Best for:
- Discord/support symptom clusters,
- community vocabulary that differs from GitHub titles,
- production pain not yet filed as issues.

Watch for:
- private chatter leakage,
- stale share sync,
- unstructured complaints without repro.

## Diff slices

Source: `git diff`, PR file lists, changed-lines metadata.

Best for:
- PR review,
- regression-focused scans,
- verifying whether a fix touches the real symptom path.

Watch for:
- tests/docs-only changes that should not expand into a full security scan,
- moved files that break naive path matching.

## Development slices

Source: target repo git metadata from `--repo`.

Best for:
- high-churn buckets,
- code/test/doc shape,
- refactor planning,
- unstable areas that are expensive to review manually.

Watch for:
- long history windows dominating the board,
- generated or deleted files in churn history,
- test ratios that say "look closer", not "coverage is good".

## Ownership slices

Source: CODEOWNERS from `--repo`.

Best for:
- routing review to the right internal team,
- spotting security or release-manager owned buckets,
- pairing churn with ownership before delegating agents.

Watch for:
- broad fallback owners,
- last-match-wins CODEOWNERS semantics,
- ownership rules that are policy signals, not implementation boundaries.

## Runtime/import slices

Source: import graph, startup profiles, package manifests, plugin manifests.

Best for:
- hot-path performance,
- lazy-loading regressions,
- plugin/core boundary leakage,
- package/dependency ownership.

Watch for:
- circular imports,
- static+dynamic imports of the same heavy module,
- core/plugin boundary violations.

## Semantic review board

Design the output for two readers: a human maintainer choosing the next slice,
and an agent that needs a small handoff payload. Start with code shape, then add
overlays. Do not collapse every lens into a single security-looking queue.

The board should expose:
- review lanes: semantic shape, ownership routing, development pressure, security pressure, issue pressure, support pressure,
- focus controls for lens and system filters without duplicating slice rows,
- one overall lens matrix with comparable bars and routing actions as the primary slice table,
- a compact agent handoff packet,
- collapsible evidence tables for audit.

Default maps should be sparse and core-focused: omit dotfile/config trees, docs,
changelog files, and mobile app trees unless the user is explicitly reviewing
those surfaces. Keep the sparse setting configurable so the same workflow can
produce a whole-repo board or a targeted board with selected paths re-included.

Map each semantic bucket with:
- feature count,
- owned file count,
- entrypoint count,
- test count,
- representative features.

Add overlays separately:
- CODEOWNERS rule and owner counts,
- git tracked-file shape and churn,
- deepsec candidate count,
- top slugs,
- top files,
- gitcrawl cluster count,
- discrawl hit count,
- contamination count.

Recommended combined ranking:

```text
score = entrypoint_weight + threat_density + issue_signal + support_signal + churn_signal - contamination_penalty
```

The combined score is a review queue, not a bug claim. Also keep separate
`semantic`, `security`, `issues`, and `support` queues so the reviewer can pick
the right lens for the job.
