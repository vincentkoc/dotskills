---
name: ghcrawl-cluster-operator
description: "Use when inspecting a ghcrawl SQLite store, pulling GitHub issue/PR data, refreshing summaries, embeddings, and clusters, or extracting one cluster and its evidence through the ghcrawl CLI."
license: AGPL-3.0-only
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# ghcrawl Cluster Operator

## Purpose

Operate ghcrawl as a local-first GitHub issue and pull request crawler: inspect the SQLite store, pull GitHub data, refresh summaries and embeddings, build clusters, and extract cluster evidence through deterministic CLI commands.

The default stance is conservative and cost-aware. Inspect first, then run mutating or API-spend commands only when the operator asked for fresh data or enrichment.

## When to use

- Inspecting ghcrawl repository state, local runs, thread counts, clusters, or durable cluster decisions.
- Pulling GitHub issue/PR data into a local ghcrawl store.
- Running OpenAI-backed summaries, structured key summaries, embeddings, and clustering.
- Explaining a cluster with members, events, canonical selections, exclusions, and local evidence.
- Operating maintainer edits such as excluding a member from a durable cluster or setting a canonical item.

## Workflow

1. Start with read-only checks: `doctor`, `configure`, `runs`, `clusters`, `cluster-explain`, and `threads`.
2. Confirm the target repo as `owner/repo` and prefer `--json` for agent-readable output.
3. Use `sync` or `refresh` only when fresh GitHub data is needed.
4. Use `--include-code` only when file overlap matters; it hydrates PR file metadata and can increase DB size.
5. Run structured key summaries before embedding when LLM summaries should influence vectors.
6. Run `embed`, then `cluster`, after summary or configuration changes.
7. Pull one cluster with `cluster-explain` before making durable maintainer edits.
8. After durable edits, rerun `cluster` and explain the affected cluster to verify the decision stuck.

## Inputs

- `repo` (required): GitHub repository in `owner/repo` format.
- `db_path` (optional): explicit SQLite database path when not using the configured default.
- `cluster_id` (optional): durable or run cluster identifier to explain or edit.
- `thread_numbers` (optional): comma-separated GitHub issue/PR numbers to inspect.
- `include_code` (optional): whether PR file metadata should be hydrated and used as clustering evidence.
- `summary_model` (optional): LLM model for structured summaries, usually `gpt-5.4`.
- `embedding_basis` (optional): vector source such as `title_original` or `llm_key_summary`.
- `limit` (optional): item cap for sync, summaries, or listing commands.

## Outputs

- Local health and configuration status.
- Run history and current cluster counts.
- Cluster lists with size, names, titles, states, and member evidence.
- Cluster explain output with members, events, exclusions, canonical picks, summaries, and top touched files when available.
- Thread snapshots for selected issue/PR numbers.
- Verification notes after refresh, embedding, clustering, or durable maintainer actions.

## Ground Rules

- Prefer read-only inspection commands first: `doctor`, `runs`, `clusters`, `cluster-explain`, `threads`.
- Treat `refresh`, `sync`, `summarize`, `key-summaries`, and `embed` as remote/API-spend commands.
- `cluster` is local-only but can be CPU-heavy on huge repos.
- Always pass `--json` for agent-readable output unless opening the TUI.
- Use `--include-code` only when file overlap matters.

## Setup Check

```bash
ghcrawl doctor --json
ghcrawl configure --json
ghcrawl runs owner/repo --limit 10 --json
```

If the local store is empty or stale, pull current open GitHub data:

```bash
ghcrawl sync owner/repo --limit 200 --json
ghcrawl sync owner/repo --include-code --limit 200 --json
```

For a normal end-to-end update:

```bash
ghcrawl refresh owner/repo --json
```

Use code hydration when file evidence should affect clustering:

```bash
ghcrawl refresh owner/repo --include-code --json
```

## LLM And Embedding Pipeline

Default clustering can run without LLM summaries. LLM summaries and embeddings enrich the cluster graph.

Useful configurations:

```bash
ghcrawl configure --summary-model gpt-5.4 --embedding-basis title_original --json
ghcrawl configure --summary-model gpt-5.4 --embedding-basis llm_key_summary --json
```

For structured key summaries:

```bash
ghcrawl key-summaries owner/repo --limit 200 --json
ghcrawl key-summaries owner/repo --number 12345 --json
```

Then refresh vectors and clusters:

```bash
ghcrawl embed owner/repo --json
ghcrawl cluster owner/repo --json
```

## Pull A Cluster And Its Info

List clusters:

```bash
ghcrawl clusters owner/repo --min-size 2 --limit 20 --sort size --json
ghcrawl clusters owner/repo --search "cron timeout" --limit 10 --json
```

Explain one durable cluster:

```bash
ghcrawl cluster-explain owner/repo --id 123 --member-limit 50 --event-limit 50 --json
```

Inspect current durable clusters with members:

```bash
ghcrawl durable-clusters owner/repo --member-limit 25 --json
ghcrawl durable-clusters owner/repo --include-inactive --member-limit 25 --json
```

Pull specific issues/PRs from the local store:

```bash
ghcrawl threads owner/repo --numbers 123,456,789 --json
```

Open the TUI:

```bash
ghcrawl tui owner/repo
```

## Local Maintainer Actions

Use these only when the operator asks for durable cluster edits:

```bash
ghcrawl exclude-cluster-member owner/repo --id 123 --number 456 --reason "not same root cause" --json
ghcrawl include-cluster-member owner/repo --id 123 --number 456 --reason "same root cause" --json
ghcrawl set-cluster-canonical owner/repo --id 123 --number 456 --reason "clearest report" --json
ghcrawl merge-clusters owner/repo --source 123 --target 456 --reason "same issue family" --json
```

After edits, re-run:

```bash
ghcrawl cluster owner/repo --json
ghcrawl cluster-explain owner/repo --id 123 --member-limit 50 --event-limit 50 --json
```
