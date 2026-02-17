<div align="center">

  ![.skills banner](banner.jpg)

# dotskills (.skills)

[![CI](https://img.shields.io/github/actions/workflow/status/vincentkoc/dotskills/validate.yml?label=CI)](https://github.com/vincentkoc/dotskills/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/actions/workflow/status/vincentkoc/dotskills/release.yml?label=Release)](https://github.com/vincentkoc/dotskills/actions/workflows/release.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

</div>

We are moving from "prompt as text" to **skill as runtime module**. Each skill acts like a lightweight, containerized application for AI work: a stable interface, opinionated workflow, and bundled resources that can be installed, versioned, tested, and reused across projects.

## How this repo works

This is my personal **.skills** repository for Codex, Cursor, OpenClaw and agent-first tooling. `.skills` is the dotfiles mindset applied to AI execution: instead of one-off prompts, this repo stores reusable skill units that bundle:

- prompt logic (`SKILL.md` / `AGENT.md` / `AGENTS.md`)
- references and knowledge assets
- scripts for deterministic execution
- repeatable validation + publishing workflows
- support external skills through submodules
- git managed personal registry and github action hooks

## Public skills

| Skill | What it does | Install |
|---|---|---|
| `technical-deslop` | Behavior-preserving cleanup of AI-style code noise. | `npx skills add vincentkoc/dotskills --skill technical-deslop -y` |
| `technical-documentation` | Brownfield + evergreen docs build/review workflows. | `npx skills add vincentkoc/dotskills --skill technical-documentation -y` |
| `technical-integrations` | Vendor/framework-agnostic API, RFC, SDK, and integration planning. | `npx skills add vincentkoc/dotskills --skill technical-integrations -y` |

Internal/private workflow skills can live in this repo and are marked in the metadata as `internal: true` and excluded from public marketplace/release artifacts.

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

Default sync targets are managed automatically by vercel skills.

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

## Why .skills

Dotfiles configure machines.
`.skills` configures AI execution quality.

This repo is meant to be composable, auditable, and practical: skills should be testable artifacts, not throwaway prompt snippets.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
