# OpenClaw Agent and Contributor Docs

Use this reference for OpenClaw `AGENTS.md`, `CONTRIBUTING.md`, CODEOWNERS,
labeler, changelog, and adjacent governance documentation.

## Required discovery

Before editing governance docs, discover the relevant instruction scope:

```bash
rg --files -g 'AGENTS.md' -g 'CLAUDE.md' -g 'CONTRIBUTING.md' -g 'CODEOWNERS' -g '.github/labeler.yml'
```

Then read:

1. root `AGENTS.md`
2. nearest scoped `AGENTS.md` for the files being edited
3. `CONTRIBUTING.md` when contributor workflow is affected
4. `CODEOWNERS`, labeler, changelog, or workflow docs when the change touches
   ownership, labels, PR flow, releases, channels, plugins, apps, or docs
   surfaces

## OpenClaw source of truth

- `AGENTS.md` is canonical for Codex repository instructions.
- Scoped `AGENTS.md` files narrow or add rules for their subtree.
- When creating a new `AGENTS.md`, add a sibling `CLAUDE.md` symlink and edit
  `AGENTS.md` only.
- Do not treat `CLAUDE.md`, `.cursor`, `.cursorrules`, or other generic
  agent-file conventions as canonical unless the active OpenClaw instructions
  explicitly say so.
- Do not add `.cursor -> .agents` compatibility symlinks as a default OpenClaw
  docs operation.

## Governance writing rules

- Telegraph style for root policy: short, concrete, repo-specific.
- Keep long runbooks out of root policy; route them to scoped repo docs or
  dedicated bundled references.
- Include real commands and real repo paths.
- Prefer boundaries over broad advice: what is allowed, what needs owner review,
  and what is never allowed.
- Keep product/docs/UI wording aligned with OpenClaw root policy: use
  "plugin/plugins"; `extensions/` is internal except in file paths.
- Never print secrets, credentials, live config, real phone numbers, or private
  artifacts.

## Contributor workflow checks

For `CONTRIBUTING.md` or contributor-facing guidance:

- Verify setup, install, build, test, lint, docs, and PR commands match current
  repo wrappers.
- Keep issue triage, PR expectations, review gates, and validation commands
  actionable.
- Link to deeper docs instead of embedding every domain runbook in the root
  contributor guide.
- Do not contradict scoped `AGENTS.md`, CODEOWNERS, or release/security policy.

## Labeler, ownership, and changelog impact

- New channel/plugin/app/doc surfaces may require `.github/labeler.yml` and
  GitHub label updates.
- Larger behavior/product/security/ownership changes need owner review.
- Docs changes tied to behavior/API/CLI/config changes should align with the
  changelog policy for that change.
- Contributor PR authors should not add OpenClaw changelog entries unless the
  maintainer workflow explicitly asks for it.

## Conflict handling

When governance sources disagree:

1. Prefer the active root `AGENTS.md`.
2. Apply nearest scoped `AGENTS.md` rules for files under that scope.
3. Prefer current repo commands and source behavior over stale prose.
4. If a rule would cause unsafe git mutation, credential exposure, broad cleanup,
   or owner-boundary violations, stop and ask.
5. Record the conflict and the smallest proposed fix.

## Deliverables

- State which governance files were read.
- Summarize any policy conflicts and the selected precedence.
- For edits, include exact validation commands run or skipped.
- For report-only reviews, list blocking policy drift first, then cleanup items.
