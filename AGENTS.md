# AGENTS.md

## Repository Purpose

This repository contains Codex, OpenClaw and other agentic AI skills and supporting references. Changes are scoped to skill definitions and lightweight workflow artifacts.
Skills are managed using vercel-labs/agent-skills (skills.sh/docs).

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
