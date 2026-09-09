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

## Evidence and artifacts

- Keep routine scoped review and audit findings in chat or stdout. Do not create report files, ledgers, or shard directories by default.
- Create durable evidence only for a requested deliverable or a concrete large-audit, resumption, or handoff requirement. State its consumer and purpose before writing files.
- Reuse one task-owned location for required evidence. Preserve coverage, deduplication, journal, and recovery contracts when a large or resumable workflow needs them.
- Report coverage and gaps whether findings stay inline or in files. Less persistence never means less investigation.

## Workflow

1. Classify the task as `build`, `review`, `audit`, or `rewrite`, and the context as `brownfield` or `evergreen`.
2. Inventory the requested file, directory, or diff scope early. Include governance and product docs for documentation-wide work. Repository size alone does not expand a scoped review.
3. Detect multilingual scope and define the required parity level.
4. Read `references/agent-and-contributing.md` for agent instruction and `CONTRIBUTING.md` rules.
5. Read `references/principles.md` for the governing ruleset (Matt Palmer, OpenAI, and ASD-STE100).
6. Read `references/simplified-technical-english.md` before writing or rewriting any prose. Pick Strict or STE-flavored mode per file.
7. Use `sub-agent-assisted` when delegation helps and the Agent tool exists, otherwise use `single-agent`. Read `references/workflows.md` when the scope needs sharding or the user requests a Workflow. Use `workflow` only with user opt-in and an available Workflow tool.
8. For build tasks, follow `references/build.md`.
9. For review tasks, follow `references/review.md` and detect issues proactively.
10. When the requested audit scope needs sharding, follow `references/large-docs-audit.md`. Run the round-0 mechanical scans and the repo's native validators first, then shard by character budget and audit every page in scope in full. Batch adversarial checks per shard. Run further rounds until two add nothing new, and report the count each round added rather than claiming convergence. Never cut an audit short to fit a message.
11. For rewrite tasks, run `scripts/ste-lint.py` first, rewrite per the STE process, and re-run the lint. Hard violations must not increase. Return the rewritten text alone unless the user asks for the rule table.
12. For remediation at scale, group the ledger into PRs with `references/pr-program.md` before editing anything, then land them in phase order.
13. Use `references/tooling.md` when platform/tooling choices affect recommendations.
14. Run a proactive issue sweep within the requested scope. Fix high-confidence defects in the same pass unless asked for report-only mode.
15. In brownfield mode, prioritize compatibility with current docs IA, tooling, and release state. In evergreen mode, prioritize timeless wording and durable structure.
16. Return deliverables plus validation notes, coverage, parity status, and remaining gaps.

## Sub-agent orchestration guidance

Prefer delegation when the requested work is broad. Use it by default for repo-wide, multi-framework, or high-conflict work.

- `inventory-agent` -> `agents/inventory-agent.md` (`haiku`): file/config discovery, coverage map, missing-path checks.
- `ste-lint-agent` -> `agents/ste-lint-agent.md` (`haiku`): deterministic STE lint baseline per shard.
- `governance-agent` -> `agents/governance-agent.md` (`sonnet`): AGENTS/CONTRIBUTING/alias precedence, conflicts, policy drift.
- `docs-framework-agent` -> `agents/docs-framework-agent.md` (`sonnet`): framework config, relative path base, file-path vs URL-path mapping.
- `verify-agent` -> `agents/verify-agent.md` (`sonnet`): adversarial refutation of one finding.
- `docs-ux-audit-agent` -> `agents/docs-ux-audit-agent.md` (`fable`): full-read reader-experience audit of one shard, ledger output.
- `ste-rewrite-agent` -> `agents/ste-rewrite-agent.md` (`fable`): Strict or STE-flavored rewrite with meaning preserved.
- `remediation-agent` -> `agents/remediation-agent.md` (`fable`): apply verified findings to one file, re-run validators.
- `synthesis-agent` -> `agents/synthesis-agent.md` (`fable`): merge outputs into one prioritized fix plan.

With Claude Workflows (`references/workflows.md`), the audit template runs `docs-ux-audit-agent` per shard and one batched `verify-agent` per shard, then synthesis and a completeness critic. Per-finding verifier fan-out is the main way these runs exhaust a session, so keep verification batched and range-scoped. The remediation template runs `remediation-agent` per file with a reviewer behind it. Launch a Workflow only after the user opts in.

## Inputs

- Doc type (tutorial, how-to, reference, explanation) and audience.
- File scope, directory scope, or diff scope.
- Docs framework/tooling constraints (Fern, Mintlify, Sphinx, MkDocs, etc.).
- Task mode (`build`, `review`, `audit`, `rewrite`) and brownfield/evergreen intent.
- STE mode per file (`strict` or `flavored`), or let the skill infer from doc type.
- Target agent and human compatibility intent.
- Desired investigation depth (quick pass, exhaustive). Audits default to exhaustive within the requested scope.
- Execution rung (`workflow`, `sub-agent-assisted`, `single-agent`) and Workflow opt-in.
- Remediation mode (`apply-fixes` by default, or `report-only`).
- Durable evidence purpose and path, only when required under [Evidence and artifacts](#evidence-and-artifacts). Use `.audit/ledger.jsonl` at the audit root when a large-audit ledger is required.
- Multilingual scope: source-of-truth language, target locales, parity expectations.

## Outputs

- Updated draft, rewritten text, or review findings with clear next actions.
- Validation notes (what was checked, what remains), including STE lint before/after counts.
- Coverage statement for audits: pages read out of pages in scope, per directory.
- Findings with status counts (open, verified, refuted, fixed, wontfix), inline by default or in the required ledger.
- Split plans for oversized pages and nav/IA change list.
- Governance-doc alignment summary when AGENTS/CONTRIBUTING were touched.
- Agent instruction-surface map (primary file, alias files, Codex/Claude/Cursor handling plan).
- Documentation-surface coverage map within the requested scope (`/docs`, README hierarchy, framework source trees).
- Delegation notes: agents or workflow run id used, scope delegated, how findings merged.
- Round-by-round finding counts and a convergence statement.
- PR program when the task is remediation at scale.
- Multilingual parity note (in-sync, partial with rationale, or intentionally divergent).
