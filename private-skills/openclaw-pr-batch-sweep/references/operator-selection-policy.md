# Operator Selection Policy

Use this policy for OpenClaw contributor PR batches. It reflects the operator's repeated accept/reject decisions and is stricter than generic mergeability.

## Hard Rejects

Reject before assigning an implementation lane:

- Draft PRs or maintainer-authored/labeled queue work.
- Explicitly skipped, previously handled, already rejected, or already superseded PRs.
- Security, SSRF, proxy, auth, OAuth, token, secret, credential, redaction, permission, sandbox, pairing, trust-boundary, or sensitive-data changes.
- Control UI, web UI, frontend, visual, translation, native UI, or product-design changes.
- Config schema/default changes, migrations, legacy compatibility, provider/auth routing, public plugin SDK/API, protocol versioning, release, CI/workflow, dependency, or infrastructure policy.
- Features, new knobs, new integrations, broad refactors, owner-boundary moves, or changes that need a product decision.
- Docs-only, test-only, coverage-only, formatting, lint, rename, typo, generated-file, snapshot-only, or cleanup PRs.
- Dirty branches, unrelated churn, duplicated implementations, fixed-on-main work, or a weaker duplicate of an existing canonical PR.
- PRs whose real proof requires unavailable credentials or an unbounded live environment.

## Reject Trivial And Odd Changes

Do not spend maintainer cycles on changes whose value is smaller than their review cost.

Reject by default:

- Production diffs below roughly 10 changed lines.
- Single-header, single-literal, one-condition, one-timer, or one-method-substitution patches without a linked, reproducible user-visible bug.
- Mechanical `Object.hasOwn`, cleanup, close/destroy, timeout-clear, User-Agent, spelling, or logging changes presented without concrete failure evidence.
- Tests that merely restate existing implementation behavior or add coverage without a bug.
- Defensive branches for hypothetical malformed internal state.
- Patch shapes that add fallback stacks, aliases, or compatibility solely to reduce diff size.

Before qualification, require a short value case:

- Name the user or operator-visible failure.
- Name the owner path and the concrete bad outcome.
- Show failing-before proof or a dependency/source contract that makes the failure unavoidable.
- Explain why the change is not merely cleanup, defensive hardening, or coverage.
- Explain why the review and long-term maintenance cost is justified.

If any answer is vague, reject the PR from the batch. An explicit operator decision may override this gate when the impact is clear and the proof is unusually strong. ClawSweeper rank alone is not an override.

## Preferred Shape

Prefer candidates with:

- A concrete user-visible bug or operational failure.
- Roughly 20-500 changed production lines, normally 2-10 files.
- A focused regression test or deterministic behavior proof.
- A single clear owner path and no cross-subsystem policy change.
- Current-main reproducibility or strong source/dependency-contract evidence.
- A clean fix that removes or replaces the faulty path rather than adding a parallel path.
- A contributor branch maintainers can edit, or a clean path to a credited replacement.

Tests may be larger than production code when they prove the failure economically. Reject production diffs above 500 lines or more than 12 files unless the operator explicitly selects the PR after review.

## Readiness Signals

Use these as ranking signals, not verdicts:

1. ClawSweeper diamond.
2. ClawSweeper platinum.
3. `proof: sufficient`.
4. `ready for maintainer look`.
5. Live mergeable state and relevant green checks.
6. Small, focused changed-file surface.

Downgrade or reject:

- `needs proof`, `waiting on author`, dirty/conflicting, or stale head.
- Compatibility, session-state, auth-provider, security-boundary, message-delivery, or other merge-risk labels.
- Missing issue context, unexplained generated changes, or repeated proof-refresh commits.

## Vision Wash

Prefer bug fixes, stability, setup reliability, first-run reliability, provider correctness, channel correctness, and performance/test infrastructure that proves real behavior.

Reject optional core expansion, bundled skills, duplicate MCP/agent infrastructure, wrapper channels, commercial integrations, heavy orchestration, or work better owned by a plugin/ClawHub.

## Historical Pattern

The operator consistently accepted:

- Narrow runtime bugs with real regression tests.
- Canonical fixes that replaced weaker duplicates.
- Contributor PRs repaired in place when editable.
- Direct landings only when contributor branches were uneditable, dirty, or required a materially different canonical diff.
- Wider canonical cleanup when many tiny PRs addressed fragments of the same root cause.

The operator consistently rejected or skipped:

- Junk/test-only PRs and one-line mechanical changes.
- Dirty overlapping PR pairs instead of untangling both.
- Drafts, maintainer work, UI/control work, security/SSRF/auth/proxy work, and risky config migrations.
- PRs already superseded by a canonical main fix.
- Tiny duplicate variants where one complete implementation should survive.

Representative accepted work:

- #98125: malformed cache recovery with production and regression-test coverage.
- #98163: conservative classifier change with a negative control.
- #97954: linked user-facing memory-wiki bug with a meaningful focused diff.
- #96702: built-in command plugin-load avoidance after validating callers and siblings.
- #95602: test infrastructure accepted only after proving material CI savings, fixture safety, hundreds of focused tests, and exact-head CI.
- #90030: QMD zero-hit stalls fixed only for the long-lived manager path while preserving the one-shot bootstrap retry.
- #98497: empty npm failure output repaired through the canonical process result, with exit, signal, and termination coverage; the broader ACPX issue stayed open.

Representative rejects:

- #97906: comment-only churn.
- #98136: warning plus formatting churn without enough product value.
- #98018 and #96750: platinum-rated test-only work without a sufficient product need.
- #94081: permission-contract regression risk.
- #96993: invalid size-limit contract.
- #96924: unsafe process identification.
- #98572: broader duplicate that removed retries from every memory backend and added a non-cancelling timeout.
- #98481: changed a documented inline command contract without a product decision.
- #96219: increased stuck cron-slot occupancy and therefore required an availability-policy decision.
- #98514: archive provenance and session-state behavior disguised as a one-line classifier fix.
- #98545 and #98372: compatibility/default and availability behavior that exceeded a low-risk batch.

Historical one-line exceptions such as #95019 and #96801 required unusually strong package/runtime contract proof. They are not eligible for a default batch and are not precedent for future selection; the operator must name any such exception explicitly in the current request.

When several PRs repeat fragments of one root cause, prefer one canonical implementation. The UTF cleanup that superseded eight small PRs is the model: land the shared fix, credit useful source work, and close the fragments.

## Batch Rule

`20` means at most 20 qualified work items, not 20 sampled PRs. Never pad the batch with low-signal changes. Continue the existing handled set across `next 20` requests.
