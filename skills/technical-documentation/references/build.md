# Build Docs Playbook

Read `principles.md` first, then follow this execution flow.

## 1. Define intent and success

- Audience, prerequisites, and job-to-be-done.
- Expected reader outcome immediately after completion.
- Doc type: tutorial, how-to, reference, explanation.
- Success criteria: what must be true after publish.

## 2. Build structure before prose

- Follow the funnel: what/why, quickstart, next steps.
- Keep headings informative and scannable.
- Open each section with the takeaway sentence.
- Add decision points with concrete branch guidance.

## 3. Brownfield build mode

- Match existing terminology, navigation, and component patterns.
- Preserve existing IA unless there is a documented migration plan.
- For rewrites, include a migration note from old to new paths.
- Prefer smallest safe change set that improves utility.

## 4. Evergreen build mode

- Prefer stable concepts over release-tied narrative.
- Isolate volatile details under clearly marked version sections.
- Include maintenance signals: owners, refresh triggers, stale criteria.
- Include lifecycle notes: deprecation and replacement paths.

## 5. Writing constraints

- Use precise language and short, imperative instructions.
- Keep code examples copy-ready and self-contained.
- Include common failure modes and safe defaults.
- Avoid placeholder guidance that cannot be executed.

## 6. Agent and automation readiness

- Keep key facts in text (not image-only).
- Prefer structured lists/tables when choices matter.
- Add links and anchors that allow deterministic navigation.
- Document what can be checked automatically in CI.

## 7. Build validation

- Validate commands and snippets where possible.
- Verify links and references in changed sections.
- Record unresolved checks explicitly in handoff.
