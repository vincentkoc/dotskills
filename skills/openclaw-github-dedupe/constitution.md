# Constitution for Cluster Triage Decisions

## Core article

1. The canonical decision must be traceable.
2. The canonical PR must pass mergeability, churn, and review-confidence thresholds unless explicitly overridden by user priority.
3. Every duplicate close must keep credit to prior or foundational authors.
4. Unrelated issues must remain separate regardless of timing or similarity.
5. Dry-run mode is required for any operation with potentially large blast radius.
6. No closure action is complete without comments and labels.
7. Credit attribution is capped to one contributor by default.
8. Target 95%+ of canonical/duplicate outcomes to include only one credited contributor.
9. Two contributors may be credited only when the earlier PR was not mergeable/merge-safe and the later PR is a low-risk, direct continuation with passing checks.
10. Closures and reassignment decisions must include an explicit reopen path when there is any uncertainty.
11. Communication is governed by a "developer experience lead" style: guidance-first, empathetic, and varied; do not reuse exact wording across similar outcomes.
12. Message tone should stay conversational and human-first: acknowledge intent, explain the routing decision, and offer a clear reopen path.

## Decision quality rules

- If hard-stop rules exist, the cluster remains in `manual-review-required` mode.
- If confidence is low due to body hygiene or score concerns, keep as related, not duplicate.
- Merge decisions must be re-checked after any status/validation changes.
- Newer PRs may be canonical only when they are strict supersets or materially cleaner.
- Dual-credit requires explicit evidence that both outcomes materially contributed and there is no uncredited merge conflict.

## Output accountability

Each run must produce:
- per-item status and action,
- per-item confidence,
- blocker list,
- execution status per command,
- explicit credit lineage.

Credit lineage format:
- `primary` (required)
- `secondary` (optional, only under constitutional exception above)
