# AGENTS.md

## Repository Purpose

This repository contains Codex, OpenClaw and other agentic AI skills and supporting references. Changes are scoped to skill definitions and lightweight workflow artifacts.
Skills are managed using vercel-labs/agent-skills (skills.sh/docs).

## Mandatory Contribution Flow

1. Read `CONTRIBUTING.md` before making changes in this repo.
2. Make targeted edits to skill files and references.
3. Run validation gates before finalizing:
   - `make validate`
   - `pre-commit run --all-files`
   - `make check-generated`
   - if generated artifacts are out of date, run `make marketplace && make releases-index` and re-run `make check-generated`
4. Open PRs as drafts first when applicable.

## Skill Standards

- Keep changes focused and minimal to requested scope.
- Prefer deterministic commands and repeatable workflows.
- Prefer concise, evidence-backed SKILL.md guidance.
- Put operational details in `references/` when they are verbose.
- Public skills under `skills/` must include `license: AGPL-3.0-only` and `metadata.source: https://github.com/vincentkoc/dotskills`.
- Validators must enforce public-skill license and source metadata.

## OpenAI Metadata Defaults

Default values for `agents/openai.yaml` in public skills:

```yaml
openai_yaml_defaults:
  interface:
    icon_small: "./assets/icon.jpg"
    icon_large: "./assets/icon.jpg"
    brand_color: "#111827"
```

## New/Updated Skills Checklist

- Update `SKILL.md` to keep required sections and concise workflow guidance.
- Add or update `references/`, `scripts/`, and `assets/` only when needed for reuse.
- Public skills must include `agents/openai.yaml` with required interface fields and the defaults above.
- Store per-skill icons in `skills/<skill>/assets/icon.jpg` and reference them via `./assets/icon.jpg`.
- If a public skill is added or renamed, update `README.md` public skills and install list.
- If a public skill is added or renamed, update `catalog.yaml` entry.
- Regenerate published indexes when public skills change: `make marketplace` and `make releases-index`.

### Add/remove skill checklist

When adding or removing a public skill:

- Add public skill path: `skills/<skill-name>/`.
- Add or update `SKILL.md` required sections and `metadata.source`/`license`.
- Add `agents/openai.yaml` and `assets/icon.jpg` for public skills.
- Update `catalog.yaml` entry:
  - set `id`, `name`, `path`, and `source`.
  - remove stale entry for deleted/renamed skills.
- Update `README.md` public skills table and install examples.
- Run `make marketplace && make releases-index`.
- Run `make check-generated` and fix any sync gaps.
- On publish, include versioned tag/release flow after PR merge.

When adding or removing a private skill:

- Place or remove under `private-skills/<skill-name>/`.
- Do not update `catalog.yaml`.
- Do not update public `README.md` install list unless you intentionally expose it.
- No public-release index regeneration is required unless a public skill changed.
- Still run `make validate`, `pre-commit run --all-files`, and `make check-generated`.

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

## Technical Documentation sub-agent prompt files

- `/Users/vincentkoc/.codex/worktrees/16f3/agent-skills/skills/technical-documentation/agents/inventory-agent.md` (`fast`, Claude `haiku`)
- `/Users/vincentkoc/.codex/worktrees/16f3/agent-skills/skills/technical-documentation/agents/governance-agent.md` (`thinking`, Claude `sonnet`)
- `/Users/vincentkoc/.codex/worktrees/16f3/agent-skills/skills/technical-documentation/agents/docs-framework-agent.md` (`thinking`, Claude `sonnet`)
- `/Users/vincentkoc/.codex/worktrees/16f3/agent-skills/skills/technical-documentation/agents/synthesis-agent.md` (`long`, Claude `opus`)
