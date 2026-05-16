---
name: technical-documentation
description: Build and review OpenClaw documentation, docs IA, source-backed docs diffs, and repo governance docs.
license: AGPL-3.0-only
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# OpenClaw Technical Documentation

## Purpose

Produce and review OpenClaw documentation that is accurate, helpful, concise,
maintainable, and source-backed. Use this skill for product docs, docs IA,
docs preservation audits, OpenClaw governance docs, and docs-as-code
validation.

## When to use

- Writing or reviewing OpenClaw docs under `docs/**`, including plugin,
  provider, channel, CLI, SDK, Gateway, migration, setup, troubleshooting, and
  reference pages.
- Reviewing docs navigation and routing in `docs/docs.json`, redirects,
  generated references, and published docs URLs.
- Refactoring docs while preserving source coverage from older pages, PRs,
  code comments, specs, or current implementation.
- Reviewing docs diffs for the OpenClaw rubric: accurate, helpful, concise,
  complete within scope, maintainable, and findable.
- Updating OpenClaw repository governance docs such as root or scoped
  `AGENTS.md`, `CONTRIBUTING.md`, `CODEOWNERS`, docs-related
  `.github/labeler.yml`, or docs-facing changelog entries.
- Aligning docs with current behavior, shipped behavior, tests, source
  contracts, or upstream dependency docs.
- Producing a report-only docs review, or applying high-confidence
  documentation fixes when the user asks for implementation.

## Workflow

1. Classify the task: `write`, `review`, `refactor`, `ia`, `audit`, or
   `governance`.
2. Read scoped OpenClaw instructions before subtree work. For docs/user-visible
   work, run `pnpm docs:list`, then read only the relevant docs and source
   surfaces.
3. Identify the reader and page type before writing: overview, quickstart, topic
   page, guide, API/SDK/CLI reference, testing guide, troubleshooting page,
   maintainer note, or governance file.
4. Read `references/principles.md` for OpenClaw docs principles and page-type
   rules.
5. For build/refactor/IA tasks, follow `references/build.md`.
6. For review tasks, follow `references/review.md`.
7. For AGENTS/CONTRIBUTING/governance work, follow
   `references/agent-and-contributing.md`.
8. Use `references/tooling.md` when docs platform, Mintlify routing, generated
   references, or validation commands affect the outcome.
9. Verify claims against source, tests, current behavior, shipped behavior, or
   upstream dependency contracts. Accuracy is a hard gate.
10. For moved or rewritten docs, run a preservation-minded audit: identify
    source units, destination ownership, moved sections, dropped sections, and
    any missing coverage.
11. Apply high-confidence fixes only when the user asked for implementation. For
    report-only requests, return findings and validation gaps without editing.
12. Return the changed draft or review findings with exact validation notes and
    any relevant `https://docs.openclaw.ai/...` URL(s).

## Sub-agent orchestration guidance

Use sub-agents only when explicitly available and the docs task is broad enough
to benefit from parallel discovery. Merge all outputs into one OpenClaw-specific
recommendation or patch plan.

- `inventory-agent` -> `agents/inventory-agent.md`: map OpenClaw docs files,
  `docs/docs.json`, generated references, redirects, and missing paths.
- `governance-agent` -> `agents/governance-agent.md`: review OpenClaw
  `AGENTS.md`, `CONTRIBUTING.md`, `CODEOWNERS`, labeler, changelog, and
  scoped-instruction alignment.
- `docs-framework-agent` -> `agents/docs-framework-agent.md`: verify
  Mintlify/file/URL routing, main-reader-path versus `Reference` placement, and
  generated-doc visibility.
- `synthesis-agent` -> `agents/synthesis-agent.md`: merge findings into one
  prioritized OpenClaw docs fix plan.

## Inputs

- Task class and desired mode (`apply-fixes` or `report-only`).
- OpenClaw reader: user, operator, plugin author, contributor, maintainer, or
  release owner.
- Page type and docs surface (`docs/**`, `docs/docs.json`, README, generated
  reference, AGENTS, CONTRIBUTING, labeler, changelog).
- File scope or diff scope.
- Source-of-truth contracts: code path, command output, tests, shipped behavior,
  upstream docs/types, spec, or prior page.
- Validation expectations: docs-list, MDX, links, glossary, formatting,
  diff check, generated-doc checks, or behavior tests.
- Preservation requirements for rewrites: source ref, destination pages,
  keep/drop/move matrix, and audit depth.

## Outputs

- Updated OpenClaw draft or source-backed review findings.
- For reviews: blocking findings first, then non-blocking improvements, then
  validation notes.
- For docs IA/refactors: page-type classification plus
  keep/drop/move/destination matrix.
- For preservation audits: source coverage summary, mapped destinations, gaps,
  and any unsupported drops.
- For governance work: scoped-instruction and contributor-flow alignment summary.
- Validation notes with exact commands run, commands not run, and why.
