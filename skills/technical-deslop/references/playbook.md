# Technical Deslop Playbook

Use this execution order for behavior-preserving cleanup.

## 1. Capture diff scope

- `git diff --cached`
- `git diff $(git merge-base origin/main HEAD)..HEAD`
- If `FILES` is provided, restrict work to those paths.

## 2. Establish local style baseline

- Read nearby unchanged code in the same module.
- Read repo conventions (`AGENTS.md`, lint configs, style guides).
- Identify idioms to preserve (error handling style, logging style, naming style).

## 3. Remove slop patterns

- Apply `slop-patterns.md` and edit only relevant hunks.
- Prefer deletion over replacement where safe.
- Avoid introducing broad refactors while cleaning.

## 4. Re-check behavioral boundaries

- No business logic changes unless explicitly requested.
- Preserve validated security/permission checks.
- Preserve intentional metrics/tracing hooks.

## 5. Final review pass

- Compare with surrounding style and remove outliers.
- Confirm there are no accidental API/contract changes.
- Provide concise 1-3 sentence cleanup summary.
