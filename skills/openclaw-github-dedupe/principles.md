# Principles for GitHub Cluster Dedupe

## Purpose

These are hard constraints for every execution of this skill. If a step conflicts with a higher-priority instruction, that instruction wins.

## Principles

- Evidence over narrative.
- Dedup decisions must map failure semantics, not just title similarity.
- Preserve contributor credit and avoid erasing historical context.
- Keep visible credit bounded:
  - default: one credited contributor on canonical outcomes (target 95%+ of cases),
  - exception only: two credited contributors when the first PR is not mergeable/merged and an unmerged later PR is a direct, conflict-free continuation that passes checks.
- Keep actions reversible when possible; prefer dry-run first for large cluster changes.
- Never infer intent from metadata alone; verify body, diff, and failure path.
- Treat risk and quality gates as non-negotiable before closure.
- Prefer one canonical resolution per cluster, with explicit rationale for every non-canonical item.
- If uncertainty exceeds one unresolved hard stop, return `manual-review-required` instead of closing.
- Maintain transparent provenance: always leave a comment trail and explicit labels.
- Keep output scannable and command-oriented for operators.
- Prefer minimal edits and deterministic commands.
- Keep communication constructive and contributor-safe, especially on closures.
- Keep communication adaptive and human: treat examples as prompts, not scripts, and vary phrasing so output never reads as templated.
- Keep comms warm and practical: prioritize what the maintainer needs next over polished copy.
