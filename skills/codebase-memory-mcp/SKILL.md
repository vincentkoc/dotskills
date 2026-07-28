---
name: codebase-memory-mcp
description: Initialize, configure, index, start, verify, troubleshoot, or refresh codebase-memory-mcp knowledge graphs and the local HTTP graph UI. Use when a user mentions codebase memory MCP, search_graph, trace_path, graph UI, index_repository, or wants graph-backed code discovery for a repository.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Codebase Memory MCP

## Purpose

Bring up `codebase-memory-mcp` for a repository and prove the graph is usable before relying on it for code discovery.

## When to use

- Initialize, re-index, refresh, or troubleshoot a repository graph.
- Start or inspect the local graph UI.
- Use `search_graph`, `trace_path`, `get_code_snippet`, or `query_graph`.
- Verify that a repository is indexed before graph-backed exploration.

## Workflow

1. Verify the repository and binary.
   - `git rev-parse --show-toplevel`
   - `git status -sb`
   - `command -v codebase-memory-mcp`
   - `codebase-memory-mcp --version`
2. Prefer exposed MCP graph tools for discovery.
   - Run `index_repository` before searching when the repository is not indexed.
   - Use `search_graph`, `trace_path`, and `get_code_snippet` before broad text scans.
3. Use the helper when CLI or UI orchestration is needed.
   - `scripts/codebase-memory-graph.sh init --repo "$(git rev-parse --show-toplevel)" --mode full`
   - Use `--mode fast` for a smoke index.
4. Verify the graph.
   - `codebase-memory-mcp cli list_projects`
   - `scripts/codebase-memory-graph.sh schema --repo "$(git rev-parse --show-toplevel)"`
   - Run one focused graph query before declaring success.
5. Verify the UI when requested.
   - Default URL: `http://127.0.0.1:9749/`.
   - The helper creates a repository-scoped tmux keepalive session.
6. Report exact proof.
   - Indexed project name.
   - Node and edge counts when available.
   - UI URL and tmux session name.
   - Missing binaries, unavailable MCP tools, or incomplete proof.

## Inputs

- Repository path.
- Index mode: `fast`, `moderate`, `full`, or `cross-repo-intelligence`.
- Optional UI port; default `9749`.

## Outputs

- Indexed and queryable repository graph.
- Verified local graph UI when requested.
- Exact status, schema, and proof summary.
