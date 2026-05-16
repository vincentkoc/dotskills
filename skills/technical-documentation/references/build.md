# OpenClaw Docs Build Playbook

Read `principles.md` first, then follow this execution flow for writing,
refactoring, or changing OpenClaw docs IA.

## 1. Establish scope and source of truth

- Classify the task: new page, page edit, docs refactor, nav/IA change,
  generated-reference change, troubleshooting addition, maintainer note, or
  governance update.
- For docs/user-visible work, run `pnpm docs:list` before drafting and use it
  to find current docs surfaces.
- Read only the relevant current docs, source files, tests, command output,
  upstream docs/types, specs, or prior pages needed to support the change.
- If the request is a maintainer/internal flow or spec, route it to the
  configured memory/spec location when that is the established OpenClaw pattern.

## 2. Choose page type and reader

- Reader: user, operator, plugin author, contributor, maintainer, or release
  owner.
- Page type: overview, quickstart, topic page, guide, API/SDK/CLI reference,
  testing guide, troubleshooting page, maintainer note, or governance file.
- Use topic pages for major product surfaces. Main docs should cover the 80/20
  path; reference/support pages carry exhaustive contracts and rare detail.
- State intentional scope limits up front when a page is partial.

## 3. Build structure before prose

- Put the first useful action early unless conceptual setup is required to pick
  the right path.
- Use verb-led headings for guides and task-oriented headings for topic pages.
- Keep task-critical configuration inline; link exhaustive defaults, enums,
  schemas, and generated references.
- Attach caveats and warnings to the step where they matter.
- Use "plugin/plugins" in user-facing docs and reserve `extensions/` for paths
  or internal repository instructions.

## 4. OpenClaw docs IA and navigation

- Read `docs/docs.json` before nav changes.
- Classify by page type before placement:
  - topic pages and 80/20 workflows stay on the main reader path.
  - reference/support pages belong under `Reference`.
  - generated `plugins/reference/*` children and redirect-only pages stay out of
    visible nav unless explicitly required.
- For plugin-docs IA, keep install/manage flows on the main reader path and move
  SDK/API/maintainer/reference surfaces to `Reference`.
- For new channel/plugin/app/doc surfaces, check whether `.github/labeler.yml`
  and GitHub labels also need updates.
- For moved pages, include a keep/drop/move/destination matrix in the handoff.

## 5. Preserve source coverage during refactors

- Identify source units before rewriting: headings, paragraphs, tables,
  examples, CLI/API contracts, warnings, and troubleshooting facts.
- Map each retained unit to a destination page or section.
- Do not treat a broad "covered" row as proof for dense source material; use
  line- or claim-level evidence when the source unit is dense.
- For dropped content, state whether it is obsolete, duplicated elsewhere,
  unsupported, or moved to a reference/support page.
- When a docs-audit artifact is used, verify it is mapped audit data with
  non-empty `mappings[]`, not only inventory or reindexed JSON.

## 6. Source-backed content requirements

- CLI docs must match current flags, output, errors, and examples.
- API/SDK docs must include fields, defaults, enum values, constraints,
  nullable behavior, lifecycle states, errors, and recovery guidance.
- Config docs must align exported types, schema/help, metadata, baselines, and
  current docs.
- Dependency-backed behavior must be verified from upstream docs, source, or
  types before documenting defaults, timing, errors, or API behavior.
- Security-sensitive docs must avoid real secrets, live config, phone numbers,
  private videos, or credentials.

## 7. Governance docs

- For root/scoped `AGENTS.md`, `CONTRIBUTING.md`, `CODEOWNERS`, labeler, or
  changelog work, use `agent-and-contributing.md`.
- Keep root governance concise and route detailed runbooks to scoped docs or
  memory/spec notes where appropriate.
- Do not introduce generic agent-file conventions that conflict with OpenClaw
  root policy.

## 8. Validation

Choose the narrowest validation that proves the touched surface:

- `pnpm docs:list`
- `pnpm docs:check-mdx`
- `pnpm docs:check-links`
- `pnpm docs:check-i18n-glossary`
- `pnpm format:docs:check` or `pnpm lint:docs`
- `git diff --check`
- generated-doc or inventory checks when generated references, plugin catalogs,
  labeler, or docs scripts changed
- behavior tests or command probes when docs claim runtime behavior

If proof is blocked, say exactly which command was not run and why.
