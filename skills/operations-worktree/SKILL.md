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
1. Ensure you are inside the target repository (main checkout or any linked worktree).
2. Create a new worktree with the shell wrapper:
   - `gwt new <branch>`
   - Optional explicit base: `gwt new <branch> <start-point>`
3. If shell wrappers are unavailable, use raw git safely:
   - `default=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)`
   - `base=${default#origin/}`
   - `git fetch origin "$base" --prune`
   - `git worktree add -b <branch> <path> "origin/$base"`
4. For OpenClaw PR review worktrees, prefer that repository's native PR review-init helper instead of hand-assembling refs.

## Inputs
- Branch name (required)
- Optional start-point (branch/tag/commit)
- Optional destination path (for raw git mode)

## Outputs
- New linked worktree checked out on the target branch.
- Default base anchored to a fetched remote default branch unless explicitly overridden.
