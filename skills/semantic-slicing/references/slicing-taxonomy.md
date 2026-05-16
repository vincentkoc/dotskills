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

## Visual review map

Map each bucket with:
- feature count,
- deepsec candidate count,
- top slugs,
- top files,
- gitcrawl cluster count,
- discrawl hit count,
- contamination count.

Recommended ranking:

```text
score = entrypoint_weight + threat_density + issue_signal + support_signal + churn_signal - contamination_penalty
```

The score is a review queue, not a bug claim.
