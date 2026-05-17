# OpenClaw Documentation Principles

Use these rules as the governing model for OpenClaw docs work.

## Reader model

1. Lead with the OpenClaw task the reader is trying to complete.
2. Give one recommended path before alternatives.
3. Keep main docs focused on the 80/20 scenario.
4. Move dense contracts, exhaustive fields, rare debugging paths, generated
   material, and maintainer-only detail to linked reference/support pages.
5. Put production risks exactly where the reader can make the mistake.
6. Link concepts, guides, references, CLI pages, SDK docs, testing, and
   troubleshooting so readers can continue without rereading.

## Page types

Choose a page type before writing:

- Overview: route readers to the right product area, integration path, or guide.
- Quickstart: get a new user to a working result with the fewest safe steps.
- Topic page: explain a major OpenClaw entity or surface end to end.
- Guide: walk through one workflow from prerequisites to production readiness.
- API/SDK/CLI reference: define every object, method, command, option, response,
  error, enum, default, and version rule in scope.
- Testing guide: show sandbox setup, fixtures, simulated failures, and live-mode
  differences.
- Troubleshooting guide: map observable symptoms to checks, causes, and fixes.
- Maintainer note: capture repo-relevant internal flow, proof, rollout, or
  release behavior in scoped repo docs or bundled references when it belongs in
  this skill. Do not route repo-wide docs to personal or local-only paths.
- Governance file: keep agent/contributor policy concrete, scoped, and aligned
  with current OpenClaw repo behavior.

## Topic page default

Use this shape for major-entity pages:

1. Title naming the entity or surface.
2. Unheaded opening that says what it is, what it owns, and what it does not
   own.
3. Requirements, only when setup needs accounts, versions, permissions, plugins,
   operating systems, or credentials.
4. Quickstart with the recommended path and smallest reliable verification.
5. Configuration with task-critical options inline and exhaustive details linked
   to reference docs.
6. Major subtopics organized by reader intent, not under a generic
   "Subtopics" heading.
7. Troubleshooting with observable failures and concrete checks.
8. Related links to guides, references, commands, concepts, and adjacent topics.

## OpenClaw terminology

- Use **OpenClaw** for the product and `openclaw` for CLI/package/path/config.
- Use **plugin/plugins** in product docs and user-facing text.
- Treat `extensions/` as an internal repository layout term; use it only when
  a file path or internal contributor instruction requires it.
- Prefer concrete OpenClaw nouns: agent profile, Gateway webhook, plugin
  manifest, channel, provider, session state, capability, migration plan.
- Define OpenClaw-specific jargon before first use.

## Writing style

- Use present tense, active voice, and direct instructions.
- Address the reader as "you" for procedural steps.
- Use short paragraphs and scannable lists.
- Use sentence case headings unless a product name, command, or identifier
  requires capitalization.
- Use descriptive link text; avoid "this page" and "click here."
- Avoid marketing language, hype, generic benefits, and vague claims.
- Avoid culturally specific idioms, jokes, and image/color-only instructions.
- Use "must" for requirements, "can" for optional capability, "recommended" for
  the default path, and "avoid" for known footguns.
- Explain "why" only when it changes a developer decision.

## Examples

- Prefer complete copy-pasteable commands and snippets.
- Use realistic variable names and values.
- Mark placeholders with angle-bracket names such as `<API_KEY>` or
  `<CUSTOMER_ID>`.
- Show expected success output after commands when it helps verification.
- Keep one conceptual unit per code block and use language-specific fences.
- Avoid examples that hide setup, auth, error handling, or cleanup.

## Review rubric

Use this rubric for every docs review:

- `accurate`: source, tests, current behavior, shipped behavior, and dependency
  contracts support the statement.
- `helpful`: the page answers the reader's task without making them infer key
  steps.
- `concise`: the main path is not buried under rare details or repeated prose.
- `complete within scope`: the page covers what it claims and names intentional
  limits.
- `maintainable`: source of truth, generated content, ownership, and refresh
  triggers are clear.
- `findable`: title, headings, docs-list hints, nav placement, and related links
  match likely reader intent.

Accuracy is a hard gate. A concise page that is wrong or unverified is not
acceptable.
