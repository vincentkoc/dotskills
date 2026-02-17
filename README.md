# agent-skills

Central source-of-truth for reusable agent skills across tools (Codex, Cursor, and others).

## Goals

- Keep authored skills versioned in one repo.
- Vendor or pin upstream skills without losing provenance.
- Sync skills into local agent runtimes from one command.
- Enforce a minimum quality bar for skill structure.

## Repository layout

```text
skills/                     # Your first-party skills
  <skill-name>/
    SKILL.md|AGENT.md|AGENTS.md
    assets/
    scripts/
vendor/                     # Third-party or mirrored skills
  <source>/<skill-name>/
    SKILL.md|AGENT.md|AGENTS.md
bin/
  agent-skills              # CLI for sync/list/validate/import
scripts/
  validate.sh               # Structural checks
  generate_marketplace.sh   # Build Claude marketplace manifest
  generate_releases_index.sh # Build release/install index for public skills
  changed_skills.sh         # Diff-aware changed skill detection
catalog.yaml                # Metadata catalog (source, version, tags)
.pre-commit-config.yaml     # Local + CI hooks
.claude-plugin/
  marketplace.json          # Claude plugin marketplace manifest
```

## Quick start

```bash
# From this repo
./bin/agent-skills list
./bin/agent-skills validate

# Dry-run sync
./bin/agent-skills sync --profile codex --dry-run

# Real sync with symlinks (best for local dev)
./bin/agent-skills sync --profile codex,cursor --mode symlink

# Dry-run import from an upstream skills repo
./bin/agent-skills import --source anthropics --repo https://github.com/anthropics/skills.git --ref main --subdir skills --skills skill-creator --dry-run
```

## Targets and profiles

The sync command uses these defaults unless overridden:

- `codex` -> `${CODEX_HOME:-$HOME/.codex}/skills`
- `cursor` -> `${CURSOR_SKILLS_DIR:-$HOME/.cursor/skills}`

Override destinations with environment variables:

```bash
CODEX_HOME="$HOME/.codex" CURSOR_SKILLS_DIR="$HOME/.cursor/skills" ./bin/agent-skills sync --profile codex,cursor
```

By default, the template skill `example-skill` is excluded from sync.

## Skill authoring conventions

Local first-party skills should include:

- `SKILL.md` file
- `## Purpose`
- `## When to use`
- `## Workflow`
- `## Inputs`
- `## Outputs`

For upstream vendor skills, `SKILL.md`, `AGENT.md`, or `AGENTS.md` are accepted as-is.

Use `./bin/agent-skills validate` to enforce these checks.

## Upstream/default skills

Track upstream skills in `vendor/<source>/<skill-name>` and record provenance in `catalog.yaml`.

Import and pin upstream skill content:

```bash
./bin/agent-skills import --source anthropics --repo https://github.com/anthropics/skills.git --ref main --subdir skills --skills skill-creator
```

The import command:

- clones the repo at a pinned ref
- copies selected skills into `vendor/<source>/`
- appends catalog metadata with pinned commit SHA + `format` (if id does not already exist)

Example entries include:

- Anthropic skills mirror
- Links to external skill pages (for reference-only skills)

## Dotfiles integration

In your dotfiles bootstrap:

1. Clone/update this repo.
2. Run `./bin/agent-skills sync --profile codex,cursor --mode symlink`.
3. Optionally run `./bin/agent-skills validate` before sync in CI.

## Development

```bash
make ci
make validate
make sync
make precommit-install
make precommit-run
make marketplace
make releases-index
```

## Claude Marketplace

Generate a marketplace manifest compatible with `.claude-plugin/marketplace.json` layouts:

```bash
make marketplace
```

This scans local and vendor skills and writes:

- `/Users/vincentkoc/GIT/_Perso/agent-skills/.claude-plugin/marketplace.json`

Only first-party non-internal skills under `skills/` are published to this manifest.

To hide a skill from publishing, set in frontmatter:

```yaml
metadata:
  internal: true
```

## CI

PR validation runs on GitHub Actions using `/Users/vincentkoc/GIT/_Perso/agent-skills/.github/workflows/validate.yml`:

- `make ci` (marketplace + release index + validate + pre-commit + generated drift check)
- changed-skill reporting against `origin/main`

Tagged releases (`v*`) run `/Users/vincentkoc/GIT/_Perso/agent-skills/.github/workflows/release.yml` and publish:

- GitHub release notes with install commands
- artifacts:
  - `/Users/vincentkoc/GIT/_Perso/agent-skills/.claude-plugin/marketplace.json`
  - `/Users/vincentkoc/GIT/_Perso/agent-skills/releases/skills.json`

## Publishing

Generate per-skill install commands:

```bash
make publish-skill SKILL=deslop
make publish-skill SKILL=technical-documentation TAG=v0.4.0
```

Create a release tag locally:

```bash
make release VERSION=v0.4.0
git push origin v0.4.0
```
