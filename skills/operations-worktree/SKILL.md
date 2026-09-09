---
name: operations-worktree
description: Safe git worktree creation and hygiene workflow that defaults new branches to an up-to-date remote default branch instead of local HEAD.
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
1. Resolve the repository identity, canonical owning checkout, Git common
   directory, and existing worktree registrations. Preserve dirty owner state.
2. Verify the owner is healthy and the intended remote base is current. A
   cached ref is not proof of the latest remote head.
3. Discover the installed wrapper with `gwt help` and its managed root with
   `gwt root`.
4. Create a new worktree with the shell wrapper:
   - `gwt new <branch>`
   - Optional explicit base: `gwt new <branch> <start-point>`
   Stop if the wrapper is unavailable or refuses the owner. Do not replace it
   with a raw-Git worktree, copied repository, or ad hoc clone.
5. Verify the returned path, managed root, registration, branch, exact base,
   and dependency ownership before editing.
6. Read `references/task-artifacts.md` before work that retains evidence,
   publishes expensive artifacts, or needs a resumable phase/blocker receipt.
7. For OpenClaw, use its current `AGENTS.md` and native review/release lifecycle
   helpers. Do not override their exact-head or evidence rules here.
8. Finish with an explicit checkout outcome: `retained`, `blocked`, or verified
   `removed`. Completion alone does not authorize cleanup.

## Inputs
- Branch name (required)
- Optional start-point (branch/tag/commit)
- Canonical owner and configured managed root

## Outputs
- New linked worktree checked out on the target branch.
- Verified owner, managed path, registration, branch, and exact base.
- Explicit retained, blocked, or verified removed checkout outcome.
