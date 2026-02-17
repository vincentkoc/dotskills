<div align="center">

# .skills

[![CI](https://img.shields.io/github/actions/workflow/status/vincentkoc/dotskills/validate.yml?label=CI)](https://github.com/vincentkoc/dotskills/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/actions/workflow/status/vincentkoc/dotskills/release.yml?label=Release)](https://github.com/vincentkoc/dotskills/actions/workflows/release.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

![.skills banner](banner.jpg)

</div>

A personal **.skills** repository for Codex, Cursor, and agent-first tooling.

`.skills` is the dotfiles mindset applied to AI execution: instead of one-off prompts, this repo stores reusable skill units that bundle:

- prompt logic (`SKILL.md` / `AGENT.md` / `AGENTS.md`)
- references and knowledge assets
- scripts for deterministic execution
- repeatable validation + publishing workflows

## Ethos

We are moving from "prompt as text" to **skill as runtime module**.

Each skill acts like a lightweight, containerized application for AI work: a stable interface, opinionated workflow, and bundled resources that can be installed, versioned, tested, and reused across projects.

## Public skills

- `technical-deslop` — behavior-preserving cleanup of AI-style code noise.
- `technical-documentation` — brownfield + evergreen docs build/review workflows.
- `technical-integrations` — vendor/framework-agnostic API, RFC, SDK, and integration planning.

## Internal skills

Internal/private workflow skills can live in this repo with:

```yaml
metadata:
  internal: true
```

Internal skills are excluded from public marketplace/release artifacts.

## Install

Install one skill:

```bash
npx skills add vincentkoc/dotskills --skill technical-deslop -y
npx skills add vincentkoc/dotskills --skill technical-documentation -y
npx skills add vincentkoc/dotskills --skill technical-integrations -y
```

List available public skills:

```bash
npx skills add vincentkoc/dotskills --list
```

## Local development

```bash
make ci
make validate
make marketplace
make releases-index
```

Local runtime sync:

```bash
make sync
```

Default sync targets:

- Codex: `${CODEX_HOME:-$HOME/.codex}/skills`
- Cursor: `${CURSOR_SKILLS_DIR:-$HOME/.cursor/skills}`

## Repository layout

```text
skills/                      # First-party skills
  <skill-name>/
    SKILL.md|AGENT.md|AGENTS.md
    references/
    scripts/
vendor/                      # Third-party mirrored/imported skills
bin/agent-skills             # List/validate/sync/import
scripts/                     # Validation + publishing automation
catalog.yaml                 # Skill metadata catalog
.claude-plugin/marketplace.json
releases/skills.json
```

## Publishing workflow

PR checks:

- regenerate marketplace/index artifacts
- validate skill structure
- run pre-commit checks
- enforce generated-file drift checks

Release flow:

```bash
make release VERSION=v0.5.0
git push origin v0.5.0
```

Per-skill publish helper:

```bash
make publish-skill SKILL=technical-deslop TAG=v0.5.0
```

## Why .skills

Dotfiles configure machines.
`.skills` configures AI execution quality.

This repo is meant to be composable, auditable, and practical: skills should be testable artifacts, not throwaway prompt snippets.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
