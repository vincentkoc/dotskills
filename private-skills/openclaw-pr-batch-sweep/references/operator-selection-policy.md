# Operator Selection Policy

Use this policy for OpenClaw contributor PR batches. It reflects the operator's repeated accept/reject decisions and is stricter than generic mergeability.

## Hard Rejects

Reject before assigning an implementation lane:

- Draft PRs or maintainer-authored/labeled queue work.
- Explicitly skipped, previously handled, already rejected, or already superseded PRs.
- Security, SSRF, proxy, outbound request-policy propagation, auth, OAuth, token, secret, credential, redaction, permission, sandbox, pairing, trust-boundary, or sensitive-data changes.
- Control UI, web UI, frontend, visual, translation, native UI, or product-design changes.
- Config schema/default changes, migrations, legacy compatibility, provider/auth routing, public plugin SDK/API, protocol versioning, release, CI/workflow, dependency, or infrastructure policy.
- Service environment, dotenv loading, daemon PATH construction, executable-precedence changes, or self-update global-install-root selection.
- Session/transcript persistence, replay, deduplication, identity, recovery, or delivery semantics, including changes disguised as narrow classifier or retry fixes.
- Exact availability-risk labels or changes that alter watchdog duration, retry/fallback policy, slot occupancy, forced termination, or duplicate execution behavior.
- Features, new knobs, new integrations, broad refactors, owner-boundary moves, or changes that need a product decision.
- Docs-only, test-only, coverage-only, formatting, lint, rename, typo, generated-file, snapshot-only, or cleanup PRs.
- Dirty branches, unrelated churn, duplicated implementations, fixed-on-main work, or a weaker duplicate of an existing canonical PR.
- Bundled "fix N bugs" PRs that cross independent lifecycle, channel, or owner paths.
- PRs whose real proof requires unavailable credentials or an unbounded live environment.

## Reject Trivial And Odd Changes

Do not spend maintainer cycles on changes whose value is smaller than their review cost.

Reject by default:

- Production diffs below roughly 10 changed lines.
- Single-header, single-literal, one-condition, one-timer, or one-method-substitution patches without a linked, reproducible user-visible bug.
- Mechanical `Object.hasOwn`, cleanup, close/destroy, timeout-clear, User-Agent, spelling, or logging changes presented without concrete failure evidence.
- Diagnostic-only error wording, hint, cause-chain, or log-copy changes below 25 production lines, even when they add broad snapshot or assertion coverage.
- CI, build, live-smoke, fixture-only, and infrastructure repairs unless the operator explicitly selects them for measurable test-system value.
- Tests that merely restate existing implementation behavior or add coverage without a bug.
- Defensive branches for hypothetical malformed internal state.
- Arbitrary cache, registry, or in-memory collection caps without a measured resource failure and owner-defined eviction contract.
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
- Treat exact session-state and message-delivery merge-risk labels as hard batch exclusions, even when the underlying fix is valid and well tested.
- Missing issue context, unexplained generated changes, or repeated proof-refresh commits.

Treat GitHub `UNSTABLE` as a downgrade, not a rejection, when the hydrated latest-check rollup has no failed or pending non-routine checks. It often means the branch needs a refresh or a required check has not been requested yet; qualification may continue, but landing still requires exact-head green proof.

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
- #98994: LINE text-boundary repair accepted only after checking each field's counting unit, keeping ordinary fields UTF-16-safe, preserving the existing flex cap, and switching rich-menu fields to LINE's documented grapheme-cluster semantics.
- #101589: all-agent usage-cache fan-out qualified only after direct callee inspection corrected the unsupported SQLite explanation, one shared sibling concurrency policy replaced competing limits, a deterministic 13-agent regression proved the cap and complete aggregation, and weaker duplicates #101578/#101581 were closed after landing.
- #101795: exact frontmatter delimiter handling qualified as a linked data-preservation bug only after the canonical branch replaced copied scanners across active agent session/prompt, workspace/dev template, bundle-command, skill, hook, and workshop paths; wrapper-only tests were replaced with active metadata and body-preservation regressions, and overlapping #101797/#101803 were credited and closed after landing.
- #102753: plugin-local MIME classification qualified because one compare-only normalization fixed three active inbound decisions, preserved raw values, matched the RFC contract, included positive and negative active-path tests, and changed no config, routing, authorization, or public API surface.

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
- #101228: self-update global-root precedence crossed service PATH, version-manager, package staging, and upgrade-compatibility policy.
- #101249: clean Feishu list pagination was still a partial duplicate without required live tenant proof; the canonical repair also needs bounded `info` pagination and skill guidance.
- #99524: a likely sound fresh-tool-result recovery fix still changed model-visible session-history priority and carried the exact session-state merge-risk label.
- #100853: mechanically equivalent cron loop deletion was cleanup-only, with no linked bug, failing-before behavior, or user-visible outcome.
- #102752: a routing patch was rejected because every added test already passed on main, the reported Slack MPIM session split remained unchanged, and the diff added an unrelated network lookup.
- #102765: an arbitrary diagnostic-cache cap was rejected because it lacked a measured growth failure, degraded deduplication after the cap, and its regression test did not observe the changed behavior.

Historical one-line exceptions such as #95019 and #96801 required unusually strong package/runtime contract proof. They are not eligible for a default batch and are not precedent for future selection; the operator must name any such exception explicitly in the current request.

#101219 was completed after already entering an active batch, but its three-line diagnostic wording change is not future selection precedent. Passing hundreds of adjacent assertions does not make a copy-only micro-change worth a fresh maintainer review cycle.

The durable ledger separates `landed` selection precedents from `handledMerged` PRs that were observed or completed during prior sweeps. The latter are terminal exclusions, not evidence that their shape should qualify again. This matters for externally merged micro, docs, test, or risky work such as #98496.

The narrow lifecycle exception is #98720, not the weaker #98135. A timer/cleanup micro-fix may qualify only when a linked runtime bug has a concrete leak, hang, event-loop, or dangling-handle outcome; the production change is at least five lines; focused tests are substantial and fail without the fix; and live readiness evidence is strong. A one-file cleanup with screenshots or generic passing tests remains rejected.

Two other accepted patterns remain bounded:

- Existing provider behavior may gain model-local capability metadata when the provider contract is verified live and the change avoids new config, auth routing, protocol, or public plugin SDK surfaces. #98688 qualified only after fallback siblings and per-model limits were proved.
- Canonical parser reuse may qualify even in a file whose name contains `config` when it changes no schema/default/migration contract and closes a linked input-validation bug. #98689 is the model; generic public parser semantics remain excluded.
- Owner-local transient read retries may qualify when the error classes, retry count, delay, fail-closed behavior, and sibling paths are explicit. #98787 qualified because it completed an already-shipped pattern on two content-preserving writers; it is not precedent for global retries or availability policy.

When several PRs repeat fragments of one root cause, prefer one canonical implementation. The UTF cleanup that superseded eight small PRs is the model: land the shared fix, credit useful source work, and close the fragments.

When one contributor opens related micro-fixes for sibling channel or provider owners, consolidate them into one focused contributor PR when the shared invariant and proof are genuinely the same. Prefer an existing shared helper, keep limits and policy constants private, preserve the contributor's credit, and close the fragments only after the combined PR lands. #101650 consolidating #101662 is the model.

When several contributors address the same valid symptom with different constants or tests, choose one canonical PR only after reading the direct callee and sibling owner path. Reuse the established sibling policy, correct unsupported mechanism claims, require deterministic proof, then credit and close the weaker duplicates after the canonical change lands. #101589 superseding #101578 and #101581 is the model.

For shared parser bugs, grep for cloned scanners and verify the active loader, not just the obvious wrapper named in the issue. A landable canonical repair centralizes delimiter/tokenization behavior, preserves each caller's body-trimming contract, tests a real metadata consumer plus a real body consumer, and closes partial parser duplicates only after the complete branch lands. #101795 is the model.

For text and payload limits, "Unicode-safe" is not enough. Verify the provider's exact counting unit per field: bytes, UTF-16 code units, Unicode code points, or grapheme clusters. Treat cap expansion as a separate product decision from boundary-safe truncation, and require request-level tests for fields whose unit differs from their siblings.

## Batch Rule

`20` means at most 20 qualified work items, not 20 sampled PRs. Never pad the batch with low-signal changes. Continue the existing handled set across `next 20` requests.
