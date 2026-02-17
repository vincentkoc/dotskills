# Slop Patterns

Use this checklist during cleanup.

## Remove

- Comments that narrate obvious code actions or repeat function names.
- Defensive checks and try/catch wrappers that are abnormal for trusted codepaths.
- `any`/unsafe casts added only to bypass type issues.
- Boilerplate guard logic that is inconsistent with nearby files.
- Verbose variable naming or control flow not used elsewhere in the module.

## Preserve

- Required error handling used consistently in that subsystem.
- Security and validation boundaries that are intentionally present.
- Existing project conventions even when they differ from personal preference.

## Scope discipline

- Edit only changed hunks unless a nearby fix is required for coherence.
- Avoid refactors unrelated to the requested cleanup.
- If uncertain whether a pattern is intentional, ask before changing behavior.
