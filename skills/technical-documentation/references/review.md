# OpenClaw Docs Review Playbook

Read `principles.md` first, then use this checklist for OpenClaw docs reviews.

## 1. Scope and classification

- Identify task mode: report-only review or apply-fixes.
- Identify page type and reader.
- Identify touched surfaces: `docs/**`, `docs/docs.json`, README, generated
  reference, AGENTS, CONTRIBUTING, CODEOWNERS, labeler, changelog, or scripts.
- For docs/user-visible work, run `pnpm docs:list`, then read relevant docs and
  source only.

## 2. Findings standard

Lead with bugs, behavioral inaccuracies, regressions, missing proof, and docs IA
failures. Each finding must include:

- failed rubric criterion: accurate, helpful, concise, complete within scope,
  maintainable, or findable
- affected file/path/section
- why it fails, backed by source, tests, current behavior, shipped behavior, or
  dependency contract evidence
- smallest fix

Accuracy is blocking. Do not downgrade inaccurate behavior, commands, flags,
config, or API contracts to a style nit.

## 3. Source-backed accuracy checks

- Verify CLI commands, flags, outputs, errors, and examples against source,
  tests, or executable probes.
- Verify API/SDK/config contracts against exported types, schemas, help output,
  generated docs, or upstream docs/types.
- Verify screenshots, UI labels, nav labels, file paths, and published URLs when
  they are part of the docs claim.
- For dependency-backed behavior, read upstream docs/source/types before making
  statements about defaults, timing, errors, or API behavior.
- Separate current behavior, shipped behavior, planned behavior, and maintainer
  intent.

## 4. Structure and page-type review

- Confirm the page type is correct for the content.
- Topic pages should follow: opening, requirements when needed, quickstart,
  configuration, major subtopics, troubleshooting, related.
- Guides should name the outcome, include prerequisites, steps, proof,
  production readiness, troubleshooting, and see-also links.
- References should be exhaustive for their stated surface.
- Troubleshooting should start from observable symptoms, not internal causes.
- Flag dense contracts or rare debugging detail that should move to reference or
  support pages.

## 5. Docs IA and findability review

- Read `docs/docs.json` for nav-related changes.
- Verify topic pages remain on the main reader path and support/reference pages
  belong under `Reference`.
- Verify generated references and redirect-only pages are not accidentally added
  to visible nav.
- Confirm titles, headings, docs-list hints, anchors, and related links match
  likely reader intent.
- For moved pages, require a keep/drop/move/destination matrix.

## 6. Preservation review for rewrites

- Identify the source material being replaced or split.
- Require destination evidence for every important claim, warning, example,
  field, command, and troubleshooting fact.
- Treat dense source sections as needing line- or claim-level mapping.
- Verify dropped sections are obsolete, duplicated, unsupported, or moved.
- If using audit artifacts, confirm the artifact is a mapped audit with non-empty
  `mappings[]`.

## 7. Governance review

Use `agent-and-contributing.md` for AGENTS/CONTRIBUTING/CODEOWNERS/labeler work.

- Confirm root policy and scoped instructions do not conflict.
- Confirm commands and PR/review gates match current repo behavior.
- Confirm user-facing docs say "plugin/plugins" and do not expose internal
  `extensions/` terminology except as paths.
- Confirm new channel/plugin/app/doc surfaces include labeler/GitHub label impact
  when required.

## 8. Validation notes

Record what was checked and what remains:

- docs-list
- MDX check
- link check
- i18n glossary check
- docs format/lint
- `git diff --check`
- generated-doc checks
- behavior tests or command probes

If a validation command is not feasible, say why and name the residual risk.

## 9. Output format

1. Blocking issues
2. Non-blocking improvements
3. Validation notes

If no issues are found, say so clearly and still list residual validation gaps.
