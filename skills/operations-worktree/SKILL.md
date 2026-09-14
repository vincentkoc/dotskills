---
name: operations-worktree
description: Create managed Git worktrees from a verified healthy owner, verify dependency reuse, and report explicit checkout and recovery outcomes.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Operations Worktree

## Purpose
Create and manage worktrees safely and consistently across projects while avoiding stale branch bases.

## When to use
- You need a new task branch in a new worktree.
- You are juggling many concurrent worktrees.
- You need to avoid branching from stale local `main` or local `HEAD`.

## Workflow
1. Resolve the repository identity, canonical owning checkout, Git common directory, and existing worktree registrations.
   Preserve dirty owner state.
   Read the repository's worktree and dependency rules.
2. Inspect existing worktrees before creating another checkout.
   Reuse an existing task-owned worktree only when its identity, branch, and ownership match.
   Do not adopt another session's checkout.
3. Use a healthy owning checkout accepted by the installed wrapper.
   An unsafe, shallow, or promisor source is not permission to create an ad hoc clone.
   Do not bypass worktree creation with raw Git, copied repositories, or temporary clones.
   A refusal stops creation, not diagnosis. Repair that same verified owner within existing task authorization, then let the wrapper recheck it.
   Report the concrete blocker if no qualified owner is available.
4. Use `gwt help` for discovery and `gwt root` to resolve the configured managed root.
   Keep new worktrees under that root or a repository-native managed root.
   Do not place new checkouts in arbitrary sibling or temporary directories.
5. Verify the download policy before any fetch.
   Task-required additive fetch or unshallow is not GC, repacking, pruning, or owner consolidation.
   Recheck current state; do not repeat completed repair or ask again for an already authorized step.
   Respect contention, suppress automatic maintenance/pruning, and preserve local branches, HEAD/index, patches, and registrations.
   Distinguish a verified current remote base from a cached local ref.
   Cached refs do not prove the latest head.
   When freshness cannot be verified, report that gap rather than silently substituting a stale base.
6. Choose the creation command for the intended completion lifecycle:
   - For new personal GWT task worktrees, use finish tracking when `gwt help`
     advertises `--finish-managed`: `gwt new <branch> <start-point> --finish-managed`.
     The start-point is optional. Keep the runtime `CODEX_THREAD_ID`; outside Codex,
     set a stable task-specific `GWT_OWNER_ID` before creation.
   - Other or repository-native wrappers use their documented creation and closeout commands.
   Enrollment is creation-only. It records ownership and does not authorize removal.
   Stop creation if the wrapper is unavailable or still refuses the repaired owner.
   Do not substitute an unrestricted raw-Git creation route.
7. Verify the returned path, managed root, registration, owner, branch, and HEAD.
   For personal finish, confirm enrollment with `gwt finish-status` before starting work.
8. Verify dependency reuse under [Dependency Ownership](#dependency-ownership).
9. Read `references/task-artifacts.md` before work that retains evidence,
   publishes expensive artifacts, or needs a resumable phase/blocker receipt.
10. For OpenClaw, use its current `AGENTS.md` and native review/release lifecycle
    helpers. Do not override their exact-head or evidence rules here.
11. Finish with the explicit [Closeout](#closeout) result.

## Dependency Ownership

Inspect the source pin and actual installed package-manager metadata separately.
Verify lockfile compatibility, workspace dependency graph, patches, platform, linker layout, and resolved dependency paths before reuse.
A matching store path or package-manager major version does not prove compatibility.
Do not assume a root dependency symlink supplies every workspace package.

APFS copy-on-write package imports can share storage without sharing a Git checkout.
They are not Git snapshots, worktree creation, or cleanup.
Do not infer physical reclaim from logical dependency sizes.
Inspect the installed package manager's contract before applying an APFS optimization.

Follow the repository and user dependency rules, existing authorization, and shared-symlink guards.
If the install is incompatible or missing, use the repository's approved proof route.
Do not add a new approval requirement for dependency work already authorized by that route.

## Closeout

Report the exact task-owned path, branch, HEAD, owner, and remaining work.
Give each task checkout an explicit outcome:

- `retained`: keep the checkout, with its reason and next owner or action.
- `blocked`: name the missing proof or permission and the exact unblock action.
- `removed`: report only after authorized removal verifies path and registration absence.
- `unknown`: preserve an incomplete removal result; reconcile its exact intent read-only before recovery.

Task completion alone is not owner release or removal authorization.
Ordinary and repository-native checkouts keep their existing authorized lifecycle:
removal requires fresh ownership and recovery proof and the repository's approved non-force procedure.

Personal GWT completion applies only to explicitly enrolled `--finish-managed`
worktrees. Record the current owner's completed work promptly with
`gwt finish --pr <full URL>`, even if the PR has not merged.
Plain finish grants no new release and does not cancel an earlier sign-off.
Treat generic Codex Stop as turn-scoped attention only, never completion or release.

When the installed wrapper advertises `finish --release` and this new enrollment
supports release, use `gwt finish --pr <full URL> --release` once this owner's
job is complete and it relinquishes future checkout use. Use `gwt release`
for an already completed owner. This is explicit local job sign-off.
Every enrolled owner, including the creator, must complete and release against
the same proof. A finished fix or feature can be removed as soon as its exact
PR head has merged into the final target and native admission passes; age adds no delay.

For stacks, first record an owner-scoped `gwt finish-pin --reason <reason>`
while upper work or recovery still needs the checkout. Then record completion
with `--target <final branch>` when needed and repeat `--wait-for <full PR URL>`
for every dependent PR. Each declared PR must target that same final branch;
they need not be merged to record completion. Only the pin's owner clears it
with `gwt finish-unpin --reason <reason>` once resolved; owners must release
afresh afterwards. All declared PRs must merge at their recorded heads before
removal; open or closed-unmerged PRs retain the checkout.

If an upper PR targets another stack branch, keep its dependency and pin,
and report the checkout retained until the stack is retargeted or restacked
to the actual final branch. Do not fake `--target` or omit `--wait-for` to pass finish.

Resume before further use. `gwt resume`, `gwt cd`, reuse through `gwt new`,
and sparse-profile changes invalidate prior completion and releases.
Head, target or dependency changes require fresh completion and release;
adding a pin reactivates ownership and any pin change invalidates releases.
Never sign off for another owner.

`gwt finish-status` reads recorded state; `gwt finish-check` refreshes proof
without removal. On an explicitly activated, natively qualified host, the same
`gwt finish-check --all --apply --policy <absolute path>` consumer can revisit
pending merges and departure. Installing source or reporting release capability
does not activate deletion or prove removal readiness.
The wrapper parks only its own shell; checkout/admin CWD, FD or mapped holders
still block removal. Preserve native guard failures and their exact reasons.

If finish reports `not-enrolled`, retain the checkout; enrollment was required
at creation. Existing report-only enrollments remain report-only. Do not retrofit
enrollment, recreate a checkout to obtain release capability, or bypass a refusal.

Dirty state, active owners, unknown commits, locks, pins, ignored recovery content
or incomplete proof require retention. Native non-force removal preserves branches.
Do not start broad maintenance, clear locks, or remove other sessions' checkouts.
Never retry an uncertain removal automatically or label an unknown result retained.

## Inputs
- Branch name (required)
- Optional start-point (branch/tag/commit)
- Canonical owner and configured managed root

## Outputs
- New linked worktree on the target branch.
- Verified owner, managed path, registration, branch, and exact base.
- Remote freshness status and dependency compatibility evidence.
- Explicit `retained`, `blocked`, verified `removed`, or unresolved `unknown` outcome.

## Flow

```mermaid
stateDiagram-v2
    [*] --> ResolveOwnerAndRegistrations
    ResolveOwnerAndRegistrations --> ReuseOwnedCheckout: exact task ownership matches
    ResolveOwnerAndRegistrations --> QualifyOwner: new checkout needed
    QualifyOwner --> RepairSameOwner: authorized repair needed
    RepairSameOwner --> QualifyOwner: repair changes evidence
    QualifyOwner --> ReportBlocked: no qualified owner or unresolved refusal
    QualifyOwner --> ChooseLifecycle: healthy owner and verified base
    ChooseLifecycle --> CreateEnrolledWorktree: new personal GWT and finish supported
    ChooseLifecycle --> CreateWithWrapper: other or repository-native lifecycle
    CreateEnrolledWorktree --> VerifyCheckoutAndDependencies: enrollment recorded
    CreateEnrolledWorktree --> ReportBlocked: creation or enrollment refuses
    CreateWithWrapper --> VerifyCheckoutAndDependencies
    CreateWithWrapper --> ReportBlocked: wrapper refuses
    ReuseOwnedCheckout --> VerifyCheckoutAndDependencies
    VerifyCheckoutAndDependencies --> DoTask: qualified
    VerifyCheckoutAndDependencies --> ReportBlocked: missing proof
    DoTask --> RecordFinish: enrolled managed checkout and owner work complete
    RecordFinish --> ReportRetained: no release or report-only enrollment
    RecordFinish --> SignOffOwner: release supported and no future owner use
    RecordFinish --> EvaluateRelease: existing release remains valid
    SignOffOwner --> EvaluateRelease: finish --release or release
    EvaluateRelease --> ReportRetained: pending proof, owners, pins or native guard
    EvaluateRelease --> ReportRemoved: qualified native removal verified
    EvaluateRelease --> ReportUnknown: incomplete removal or missing readback
    DoTask --> ReportRetained: personal finish reports not-enrolled
    DoTask --> NativeCloseout: ordinary or repository-native checkout
    NativeCloseout --> ReportCheckout: existing authorized lifecycle and fresh proof
    ReportBlocked --> [*]
    ReportRetained --> [*]
    ReportCheckout --> [*]
    ReportRemoved --> [*]
    ReportUnknown --> [*]
```
