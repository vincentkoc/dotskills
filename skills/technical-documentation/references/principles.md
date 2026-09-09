# Documentation Principles

This reference consolidates the core rules used by this skill.

## Matt Palmer: 8 rules for better docs

Source: https://mattpalmer.io/posts/2025/10/8-rules-for-better-docs/

Use these as default operating principles:

1. Write for humans, optimize for agents.
2. Start with a funnel: what/why, quickstart, next steps.
3. Use Diataxis to scaffold content.
4. Write with AI, but structure for agents.
5. Offload routine docs operations to background agents.
6. Automate quality with CI.
7. Automate scaffolding and repetitive workflow tasks.
8. Make contribution easy and visible.

## OpenAI cookbook: what makes documentation good

Source: https://cookbook.openai.com/articles/what_makes_documentation_good

Key quality constraints:

- Prefer specific and accurate terminology over niche jargon.
- Keep examples self-contained and minimize dependencies.
- Prioritize high-value topics over edge-case depth.
- Do not teach unsafe patterns (for example, exposed secrets).
- Open with context that helps readers orient quickly.
- Apply empathy and override rigid rules when it clearly improves outcomes.

## ASD-STE100: controlled language for prose

Source: `references/simplified-technical-english.md` (adapted from https://github.com/danyuchn/asd-ste100-skill, MIT)

Sentence-level rules for every doc this skill writes or reviews:

- Active voice, one instruction per sentence, no semicolons, no phrasal verbs, no noun clusters over 3 words.
- 20 words or fewer per instruction sentence, 25 or fewer per descriptive sentence, 6 sentences or fewer per paragraph.
- One word, one meaning within a file. Verbs, not nominalizations. No marketing adjectives.
- Keep every hedge and every scope qualifier. A rewrite never adds a fact or upgrades a "may" to an "is".
- Strict mode for procedures, reference, error text, and agent instruction files. STE-flavored mode for explanation and README prose.

## Practical merge policy

When these rules conflict:

1. Preserve reader task success first.
2. Preserve meaning, including hedges and safety conditions, second. STE never wins over modality.
3. Preserve structural clarity third.
4. Preserve long-term maintainability fourth.
5. Add agent optimization only if it does not reduce human clarity.

For agent-instructions and contributor-governance specifics (AGENTS/aliases/CONTRIBUTING), use `references/agent-and-contributing.md` as the detailed additional source of truth.

## Execution policy for this skill

- Long-running and extensive investigations are allowed for both build and review work when needed to resolve ambiguity or cross-file drift.
- Audits run until requested coverage is complete. Do not cut an audit short to fit a message. Report gaps explicitly.
- Keep routine scoped findings in chat or stdout. Require a requested deliverable or a concrete large-audit, resumption, or handoff consumer before creating durable evidence.
- Follow [Evidence and artifacts](../SKILL.md#evidence-and-artifacts) for persistence. Keep the ledger and recovery contracts when using `references/large-docs-audit.md`.
- Use sub-agents when available for bounded parallel discovery, verification, or cross-source comparison. Use Claude Workflows when the user opted in and the tree is large (`references/workflows.md`).
- Keep one merged outcome: sub-agent outputs must be normalized into a single consistent recommendation/fix set.

## Multilingual parity rule

When docs exist in multiple languages, target cross-locale parity for task-critical content (steps, warnings, prerequisites, and limits). If full parity is not possible, publish explicit parity status and sync intent.
