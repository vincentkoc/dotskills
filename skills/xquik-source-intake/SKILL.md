---
name: xquik-source-intake
description: Collect public X evidence with Xquik REST or MCP before drafting research, support, product, or content decisions.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Xquik Source Intake

## Purpose

Collect public X evidence with Xquik before an agent drafts research, support, product, or content decisions that depend on current social context.

## When to use

- A task asks for public X posts, user profiles, timelines, trends, media, or follower context.
- A draft needs source-backed social examples instead of unsourced assumptions.
- A workflow already has an `XQUIK_API_KEY` and can use Xquik REST or MCP.
- The user asks for an evidence packet before analysis or publishing.

## Workflow

1. Confirm the user approved public X collection for this task.
2. Pick the narrowest Xquik route:
   - REST API for deterministic scripts and repeatable jobs.
   - MCP for interactive agent sessions that need endpoint discovery.
   - The `x-twitter-scraper` skill when a full agent workflow is available.
3. Collect only the requested public fields and record the query, endpoint, time window, and collection time.
4. Normalize each item into a source packet:
   - `platform`
   - `query`
   - `endpoint`
   - `collected_at`
   - `source_url`
   - `author_or_account`
   - `text_or_summary`
   - `observed_metrics`
5. Separate observations from conclusions. Do not infer private identity, intent, or protected traits.
6. Cite source packet IDs in the final analysis, brief, ticket, or content draft.

## Inputs

- `XQUIK_API_KEY`: API key available in the runtime environment.
- `TASK`: what decision, draft, or analysis needs public X evidence.
- `QUERY`: keywords, accounts, list IDs, tweet IDs, or trend scope.
- `WINDOW`: collection time window or recency requirement.
- `LIMITS`: maximum records and fields to collect.

## Outputs

- A compact source packet table.
- Query and endpoint provenance for each packet.
- A short reliability note covering sample size, recency, and missing context.
- A decision-ready summary that cites packet IDs instead of raw assumptions.

## Public References

- Xquik docs: https://docs.xquik.com
- API reference: https://docs.xquik.com/api-reference/overview
- MCP guide: https://docs.xquik.com/mcp/overview
- Primary skill: https://skills.sh/xquik-dev/x-twitter-scraper/x-twitter-scraper
