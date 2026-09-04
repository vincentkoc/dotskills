---
name: technical-documentation
description: Build, review, and audit technical docs and agent instruction files. Applies Simplified Technical English (ASD-STE100) to prose, scales to huge docs trees with sharded audits and ledgers, and runs as Claude Workflows or sub-agents when available.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Technical Documentation

## Purpose

Produce, review, and audit technical documentation that is clear, unambiguous, and maintainable for both humans and agents. Covers product docs, contributor-governance files, and agent instruction files. Prose follows Simplified Technical English so a reader or an agent cannot misread it. Audits scale to trees with hundreds of pages through sharding, adversarial checks, and parallel remediation.

## When to use

- Creating or overhauling docs in an existing product/codebase (brownfield).
- Building evergreen docs meant to stay accurate and reusable over time.
- Reviewing doc diffs for structure, clarity, and operational correctness.
- Running full-repo documentation audits across governance files and product docs surfaces (`docs/`, `README*`, `.md/.mdx/.mdc`, Fern/Sphinx/Mintlify/MkDocs sources).
- Auditing a large or messy docs tree: hundreds of pages, pages over 20k characters, confusing navigation, many locales, poor reader experience.
- Rewriting dense or ambiguous English into Simplified Technical English: procedures, reference pages, error messages, tool descriptions, AGENTS.md and CONTRIBUTING.md.
- Updating or reviewing AGENTS.md and/or CONTRIBUTING.md to keep agent and contributor workflows aligned with current repo practices.
- Designing governance documentation strategy for repos with alias instruction files (`CLAUDE.md`, `AGENT.md`, `.cursorrules`, `.cursor/rules/*`, `.agent/`, `.agents/`, `.pi/`).
- Diagnosing agent-file drift where teams had to prompt iteratively to surface missing files, broken commands, or policy conflicts.

## Workflow

1. Classify the task as `build`, `review`, `audit`, or `rewrite`, and the context as `brownfield` or `evergreen`.
2. Inventory full documentation scope early (governance + product docs). For trees over roughly 100 pages, use `git ls-files` and the sharding rules in `references/large-docs-audit.md`.
3. Detect multilingual scope and define the required parity level.
4. Read `references/agent-and-contributing.md` for agent instruction and `CONTRIBUTING.md` rules.
5. Read `references/principles.md` for the governing ruleset (Matt Palmer, OpenAI, and ASD-STE100).
6. Read `references/simplified-technical-english.md` before writing or rewriting any prose. Pick Strict or STE-flavored mode per file.
7. Pick the execution rung from `references/workflows.md`: `workflow` (user opted in and the Workflow tool exists), `sub-agent-assisted` (Agent tool exists), or `single-agent`.
8. For build tasks, follow `references/build.md`.
9. For review tasks, follow `references/review.md` and detect issues proactively.
10. For audit tasks on large trees, follow `references/large-docs-audit.md`. Shard the tree, audit every page in full, and write findings to the ledger. Run adversarial checks on blocking and major findings, then remediate. Run until coverage is complete and two discovery passes add nothing new. Never cut an audit short to fit a message.
11. For rewrite tasks, run `scripts/ste-lint.py` first, rewrite per the STE process, and re-run the lint. Hard violations must not increase. Return the rewritten text alone unless the user asks for the rule table.
12. Use `references/tooling.md` when platform/tooling choices affect recommendations.
13. Run a proactive issue sweep across governance and docs-content surfaces, and fix high-confidence defects in the same pass unless asked for report-only mode.
14. In brownfield mode, prioritize compatibility with current docs IA, tooling, and release state. In evergreen mode, prioritize timeless wording and durable structure.
15. Return deliverables plus validation notes, coverage, parity status, and remaining gaps.

## Sub-agent orchestration guidance

Prefer delegation when the repo is large or the change set is broad. Use it by default for repo-wide, multi-framework, or high-conflict work.

- `inventory-agent` -> `agents/inventory-agent.md` (`haiku`): file/config discovery, coverage map, missing-path checks.
- `ste-lint-agent` -> `agents/ste-lint-agent.md` (`haiku`): deterministic STE lint baseline per shard.
- `governance-agent` -> `agents/governance-agent.md` (`sonnet`): AGENTS/CONTRIBUTING/alias precedence, conflicts, policy drift.
- `docs-framework-agent` -> `agents/docs-framework-agent.md` (`sonnet`): framework config, relative path base, file-path vs URL-path mapping.
- `verify-agent` -> `agents/verify-agent.md` (`sonnet`): adversarial refutation of one finding.
- `docs-ux-audit-agent` -> `agents/docs-ux-audit-agent.md` (`fable`): full-read reader-experience audit of one shard, ledger output.
- `ste-rewrite-agent` -> `agents/ste-rewrite-agent.md` (`fable`): Strict or STE-flavored rewrite with meaning preserved.
- `remediation-agent` -> `agents/remediation-agent.md` (`fable`): apply verified findings to one file, re-run validators.
- `synthesis-agent` -> `agents/synthesis-agent.md` (`fable`): merge outputs into one prioritized fix plan.

With Claude Workflows (`references/workflows.md`), the audit template runs `docs-ux-audit-agent` per shard, `verify-agent` three times per blocking or major finding, then synthesis and a completeness critic. The remediation template runs `remediation-agent` per file in an isolated worktree with a reviewer behind it. Launch a Workflow only after the user opts in.

## Inputs

- Doc type (tutorial, how-to, reference, explanation) and audience.
- File scope, directory scope, or diff scope.
- Docs framework/tooling constraints (Fern, Mintlify, Sphinx, MkDocs, etc.).
- Task mode (`build`, `review`, `audit`, `rewrite`) and brownfield/evergreen intent.
- STE mode per file (`strict` or `flavored`), or let the skill infer from doc type.
- Target agent and human compatibility intent.
- Desired investigation depth (quick pass, exhaustive). Audits default to exhaustive.
- Execution rung (`workflow`, `sub-agent-assisted`, `single-agent`) and Workflow opt-in.
- Remediation mode (`apply-fixes` by default, or `report-only`).
- Ledger path for audits (default `docs-audit-ledger.jsonl` at the audit root).
- Multilingual scope: source-of-truth language, target locales, parity expectations.

## Outputs

- Updated draft, rewritten text, or review findings with clear next actions.
- Validation notes (what was checked, what remains), including STE lint before/after counts.
- Coverage statement for audits: pages read out of pages in scope, per directory.
- Finding ledger with status counts (open, verified, refuted, fixed, wontfix).
- Split plans for oversized pages and nav/IA change list.
- Governance-doc alignment summary when AGENTS/CONTRIBUTING were touched.
- Agent instruction-surface map (primary file, alias files, Codex/Claude/Cursor handling plan).
- Documentation-surface coverage map (`/docs`, README hierarchy, framework source trees).
- Delegation notes: agents or workflow run id used, scope delegated, how findings merged.
- Multilingual parity note (in-sync, partial with rationale, or intentionally divergent).
