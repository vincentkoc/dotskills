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
