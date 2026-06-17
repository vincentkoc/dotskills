---
name: codebase-memory-mcp
description: Initialize, configure, index, start, verify, troubleshoot, or sync codebase-memory-mcp knowledge graphs and the HTTP graph UI for local repositories. Use when the user mentions codebase memory MCP, search_graph, trace_path, graph UI, index_repository, or wants code discovery via the codebase-memory-mcp server.
license: MIT
metadata:
  internal: true
  version: "0.1.0"
  spec: agentskills-v1
---

# Codebase Memory MCP

## Purpose

Bring up `codebase-memory-mcp` for a repository, make the HTTP graph UI visible, and prove the graph is usable before relying on it for code discovery.

Requires `codebase-memory-mcp`, tmux, Node.js, and curl for the UI keepalive workflow.

## When to use

- The user asks whether codebase-memory MCP is running or indexed.
- The user wants the graph UI to show up.
- The user asks to initialize, re-index, refresh, or troubleshoot a repository graph.
- The user wants to use `search_graph`, `trace_path`, `get_code_snippet`, `query_graph`, or related MCP graph tools.
- The user asks to sync this setup to another machine.

## Workflow

1. Verify local context first.
   - `pwd`
   - `git rev-parse --show-toplevel`
   - `git status -sb`
   - `command -v codebase-memory-mcp`
   - `codebase-memory-mcp --version`
2. Prefer MCP graph tools when exposed in the current agent session.
   - If `search_graph`, `trace_path`, or `get_code_snippet` are callable, use them for code discovery.
   - If the tools are not exposed, use the CLI and UI workflow below.
3. Initialize the repository with the helper script:

```bash
private-skills/codebase-memory-mcp/scripts/codebase-memory-graph.sh init --repo "$(git rev-parse --show-toplevel)" --mode full
```

Use `--mode fast` for a quick smoke index and `--mode full` when the graph should be useful for real codebase work.

4. Open the UI.
   - The default URL is `http://127.0.0.1:9749/`.
   - The helper starts a tmux keepalive session named `cbm-<repo>-ui`.
   - The UI port only binds after the MCP server receives an `initialize` request. Starting `codebase-memory-mcp` directly can look dead.
5. Prove the graph.
   - `codebase-memory-mcp cli list_projects`
   - `private-skills/codebase-memory-mcp/scripts/codebase-memory-graph.sh schema --repo "$(git rev-parse --show-toplevel)"`
   - Run a small `search_graph` query through the MCP tool or CLI before saying the graph is ready.
6. Report exact proof.
   - Project name.
   - Node and edge counts when available.
   - UI URL.
   - tmux keepalive session name.
   - Any proof gaps, such as missing MCP tool exposure in the current Codex session.

## Commands

Run from the dotskills checkout or pass the script path explicitly.

```bash
# Configure UI, index, start UI, and run a schema smoke check.
private-skills/codebase-memory-mcp/scripts/codebase-memory-graph.sh init --repo /path/to/repo --mode full

# Start or restart only the UI keepalive.
private-skills/codebase-memory-mcp/scripts/codebase-memory-graph.sh start-ui --repo /path/to/repo

# Show config, indexed projects, and UI listener state.
private-skills/codebase-memory-mcp/scripts/codebase-memory-graph.sh status --repo /path/to/repo

# Stop the keepalive session created by this helper.
private-skills/codebase-memory-mcp/scripts/codebase-memory-graph.sh stop-ui --repo /path/to/repo
```

## Remote Sync

For Vincent's machines, resolve quickssh aliases before touching a host. Legacy quickssh aliases may live in the private `.extra/quickssh_hosts.sh` file; do not print passwords or secrets from that file.

Remote install pattern:

1. Verify target identity:

```bash
ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=3 <target> 'hostname; scutil --get ComputerName 2>/dev/null || true; uname -a'
```

2. Pull dotskills on the remote, or clone it if missing:

```bash
ssh <target> 'mkdir -p ~/GIT/_Perso && if [ -d ~/GIT/_Perso/dotskills/.git ]; then git -C ~/GIT/_Perso/dotskills pull --ff-only; else git clone https://github.com/vincentkoc/dotskills.git ~/GIT/_Perso/dotskills; fi'
```

3. Install the private skill by ensuring the local skill source is present under the remote dotskills checkout and that the user's agent config can discover that checkout. Prefer the existing machine convention if one exists; otherwise create a symlink from the agent skills dir to the dotskills private skill:

```bash
ssh <target> 'mkdir -p ~/.agents/skills && ln -sfn ~/GIT/_Perso/dotskills/private-skills/codebase-memory-mcp ~/.agents/skills/codebase-memory-mcp'
```

4. Verify remote availability:

```bash
ssh <target> 'test -f ~/GIT/_Perso/dotskills/private-skills/codebase-memory-mcp/SKILL.md && test -x ~/GIT/_Perso/dotskills/private-skills/codebase-memory-mcp/scripts/codebase-memory-graph.sh && command -v codebase-memory-mcp'
```

If `codebase-memory-mcp` is missing on the remote, stop after syncing the skill and report the missing binary. Do not invent an install method without checking the machine's package/source convention.

## Inputs

- `repo_path`: repository root to index.
- `mode`: `fast`, `moderate`, `full`, or `cross-repo-intelligence`; default to `full` for useful repo work and `fast` for smoke checks.
- `port`: UI port; default `9749`.
- `remote_aliases`: optional quickssh/SSH aliases to sync.

## Outputs

- Indexed project name and graph counts.
- UI URL and listener proof.
- tmux keepalive session name and stop command.
- Remote sync proof per machine: host identity, dotskills HEAD, symlink/install path, and `codebase-memory-mcp` binary status.
