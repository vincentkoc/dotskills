# AGENTS.md

- allways read CONTRIBUTING.md when contributing to a repository including third-party and thier isssue and PR templates to ensure you match the style, link issues like "Fixes: xxx" if you have an issue link
- utilize gh (github) cli for things like PRs, opt for draft prs first and review
- prefer using worktrees and sub-agents to speed up work
- when contributing to external repos try to at least run unittests and formatters to ensure it all matches up

## Repository Purpose

This repository contains Codex skills and supporting references. Changes are scoped to skill definitions and lightweight workflow artifacts.

## Mandatory Contribution Flow

1. Read `CONTRIBUTING.md` before making changes in this repo.
2. Make targeted edits to skill files and references.
3. Run relevant formatters/test commands when scripts or code are changed.
4. Open PRs as drafts first when applicable.

## Skill Standards

- Keep changes focused and minimal to requested scope.
- Prefer deterministic commands and repeatable workflows.
- Prefer concise, evidence-backed SKILL.md guidance.
- Put operational details in `references/` when they are verbose.

## PR/Issue Hygiene

- Include issue references when available (for example `Fixes: 123`).
- Keep PR description short: what changed, why, and impact.

## Source of Truth

- `AGENTS.md`
- `CONTRIBUTING.md`
- `SKILL.md` files for each skill

## External Repo Work

- For external repos, run available unit tests and formatters before finalizing.
- Use `gh` for PR operations and status checks.
