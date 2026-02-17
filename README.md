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
    SKILL.md
    assets/
    scripts/
vendor/                     # Third-party or mirrored skills
  <source>/<skill-name>/
    SKILL.md
bin/
  agent-skills              # CLI for sync/list/validate
scripts/
  validate.sh               # Structural checks
catalog.yaml                # Metadata catalog (source, version, tags)
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
```

## Targets and profiles

The sync command uses these defaults unless overridden:

- `codex` -> `${CODEX_HOME:-$HOME/.codex}/skills`
- `cursor` -> `${CURSOR_SKILLS_DIR:-$HOME/.cursor/skills}`

Override destinations with environment variables:

```bash
CODEX_HOME="$HOME/.codex" CURSOR_SKILLS_DIR="$HOME/.cursor/skills" ./bin/agent-skills sync --profile codex,cursor
```

## Skill authoring conventions

Each skill should include at least:

- `SKILL.md` file
- `## Purpose`
- `## When to use`
- `## Workflow`
- `## Inputs`
- `## Outputs`

Use `./bin/agent-skills validate` to enforce these checks.

## Upstream/default skills

Track upstream skills in `vendor/<source>/<skill-name>` and record provenance in `catalog.yaml`.

Example entries:

- Anthropic skills mirror
- Links to external skill pages (for reference-only skills)

## Dotfiles integration

In your dotfiles bootstrap:

1. Clone/update this repo.
2. Run `./bin/agent-skills sync --profile codex,cursor --mode symlink`.
3. Optionally run `./bin/agent-skills validate` before sync in CI.

## Development

```bash
make validate
make sync
```

