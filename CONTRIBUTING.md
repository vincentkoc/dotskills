# Contributing

Thanks for contributing to `.skills`.

## Code of Conduct

Participation in this project is governed by `CODE_OF_CONDUCT.md`.

## Contribution workflow

1. Create a branch for your change.
2. Keep commits semantic (`feat:`, `fix:`, `docs:`, `chore:`).
3. Run local checks before pushing.
4. Open a **draft PR** first, then request review.

## Local checks

Run:

```bash
make validate
pre-commit run --all-files
```

If pre-commit is not installed:

```bash
make precommit-install
```

## Skill authoring requirements

Each skill directory must include `SKILL.md` with these sections:

- `## Purpose`
- `## When to use`
- `## Workflow`
- `## Inputs`
- `## Outputs`

### Workflow charts

Public skills must make their action paths inspectable. Use a concise Mermaid
`stateDiagram-v2` block under `## Flow`, or a direct Markdown link from that
section to a chart in the skill's `references/` directory.

Chart meaningful mode choices, authorization gates, failures, and exits. Every
supported mode needs a path to an outcome, including plans, no-ops, and blockers.
Keep the prose workflow authoritative; a diagram must not add execution,
retention, retry, or cleanup authority. Update both when behavior changes.

For a linear analysis/checklist or a skill that defers its lifecycle entirely to
the target repository, use `metadata.workflow-exemption` with a specific reason
instead of a redundant diagram. Do not exempt a branching workflow merely to
avoid describing its guards. Internal examples and vendored skills are excluded.

`make validate` checks chart presence or the exemption. It does not prove Mermaid
syntax or workflow semantics: render changed charts and walk their permitted,
blocked, and non-mutating paths against the instructions before review. Use the
existing validator and generators; do not add a parallel chart registry or tool.

## Upstream skill imports

Use the import workflow to vendor third-party skills and pin provenance:

```bash
make import-anthropic-dry
make import-anthropic
```

This records pinned metadata in `catalog.yaml`.

## Pull requests

PRs should include:

- What changed and why.
- Validation notes (`make validate`, `pre-commit run --all-files`).
- Any follow-up items or known limitations.

If your PR addresses an issue, link it in the description (for example: `Fixes: #123`).
