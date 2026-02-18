---
name: technical-documentation
description: Build and review high-quality technical docs as well as agent instruction files in your repository.
license: AGPL-3.0-only
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Technical Documentation

## Purpose

Produce and review technical documentation that is clear, actionable, and maintainable for both humans and agents, including contributor-governance files and agent instruction files.

## When to use

- Creating or overhauling docs in an existing product/codebase (brownfield).
- Building evergreen docs meant to stay accurate and reusable over time.
- Reviewing doc diffs for structure, clarity, and operational correctness.
- Updating or reviewing AGENTS.md and/or CONTRIBUTING.md to keep agent and contributor workflows aligned with current repo practices.
- Improving repository onboarding/docs that include contribution instructions, issue templates, PR flow, and review gates.
- Designing governance documentation strategy for repos with alias instruction files (for example `CLAUDE.md`, `AGENT.md`, `.cursorrules`, `.cursor/rules/*`, `.agent/`, `.agents/`, `.pi/`) where `CLAUDE.md` is treated as a canonical policy source and `AGENTS.md` should be kept as compatibility alias if present.

## Workflow

1. Classify task: `build` or `review`; context: `brownfield` or `evergreen`.
2. Read `references/agent-and-contributing.md` for agent instruction and `CONTRIBUTING.md` workflow rules (inventory, canonical/alias mapping, dual-mode balance, deliverable standards, and precedence/conflict handling).
3. Read `references/principles.md` for the governing ruleset (Matt Palmer & OpenAI).
4. For build tasks, follow `references/build.md`.
5. For review tasks, follow `references/review.md`.
6. Use `references/tooling.md` when platform/tooling choices affect recommendations.
7. In brownfield mode, prioritize compatibility with current docs IA, tooling, and release state.
8. In evergreen mode, prioritize timeless wording, update strategy, and durable structure.
9. Return deliverables plus validation notes and remaining gaps.

## Inputs

- Doc type (tutorial, how-to, reference, explanation) and audience.
- File scope or diff scope.
- Docs framework/tooling constraints (Fern, Mintlify, Sphinx, etc.).
- Build/review mode and brownfield/evergreen intent.
- Target agent and human compatibility intent.

## Outputs

- Updated draft or review findings with clear next actions.
- Validation notes (what was checked, what remains).
- Navigation/maintenance recommendations for long-term quality.
- Governance-doc alignment summary when AGENTS/CONTRIBUTING were touched.
- Agent instruction-surface map (primary file, alias files, Codex/Claude/Cursor handling plan).
