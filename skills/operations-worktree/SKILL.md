---
name: operations-worktree
description: Create managed Git worktrees from a verified healthy owner, verify dependency reuse, and report explicit retained, blocked, or removed closeout.
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
6. Create the worktree with the installed shell wrapper:
   - `gwt new <branch>`
   - Optional explicit base: `gwt new <branch> <start-point>`
   Stop creation if the wrapper is unavailable or still refuses the repaired owner.
   Do not substitute an unrestricted raw-Git creation route.
7. Verify the returned path, managed root, registration, owner, branch, and HEAD.
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
Give each task checkout one outcome:

- `retained`: keep the checkout, with its reason and next owner or action.
- `blocked`: name the missing proof or permission and the exact unblock action.
- `removed`: report only after an authorized removal verifies both path and registration absence.

Task completion alone is not owner release or removal authorization.
Removal requires the existing authorized scope, fresh ownership and recovery proof, and the repository's approved non-force procedure.
Where installed, `gwt finish` records per-job sign-off under its own lifecycle contract.
Owner release, merge and dependency proof, and qualified holder checks remain separate requirements.
An unqualified holder backend retains the worktree; do not bypass that result.
Dirty state, active owners, unknown commits, locks, or incomplete proof require retention.
Do not start broad maintenance, clear locks, or remove other sessions' checkouts during closeout.
If a native helper reports incomplete cleanup, preserve that result and report the retained path.

## Inputs
- Branch name (required)
- Optional start-point (branch/tag/commit)
- Canonical owner and configured managed root

## Outputs
- New linked worktree on the target branch.
- Verified owner, managed path, registration, branch, and exact base.
- Remote freshness status and dependency compatibility evidence.
- Explicit `retained`, `blocked`, or verified `removed` closeout outcome.
