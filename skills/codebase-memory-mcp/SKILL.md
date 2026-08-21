---
name: codebase-memory-mcp
description: Resolve canonical Git checkouts, index and verify codebase-memory-mcp graphs, operate the local graph UI, and safely audit duplicate worktree caches. Use when a user mentions codebase memory MCP, search_graph, trace_path, graph UI, index_repository, worktree indexes, or oversized graph caches.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Codebase Memory MCP

## Purpose

Bring up `codebase-memory-mcp` for the owning Git checkout and prove the graph is usable before relying on it for code discovery. Keep linked worktrees on the owner's graph instead of creating one graph per branch.

## When to use

- Initialize, re-index, refresh, or troubleshoot a repository graph.
- Start or inspect the local graph UI.
- Use `search_graph`, `trace_path`, `get_code_snippet`, or `query_graph`.
- Verify that a repository is indexed before graph-backed exploration.
- Audit or prune duplicate linked-worktree indexes without deleting cache files directly.

## Workflow

1. Verify the repository and binary.
   - `git rev-parse --show-toplevel`
   - `git status -sb`
   - `command -v codebase-memory-mcp`
   - `codebase-memory-mcp --version`
2. Resolve the canonical owning checkout.
   - `scripts/codebase-memory-graph.sh canonical --repo "$(git rev-parse --show-toplevel)"`
   - Linked worktrees resolve through their absolute Git common directory to the one checkout that owns it.
   - Separate clones remain separate projects.
   - Missing, invalid, bare, or ownerless repositories fail closed.
3. Prefer exposed MCP graph tools for discovery.
   - Run `index_repository` before searching when the repository is not indexed.
   - Use `search_graph`, `trace_path`, and `get_code_snippet` before broad text scans.
4. Use the helper when CLI or UI orchestration is needed.
   - `scripts/codebase-memory-graph.sh init --repo "$(git rev-parse --show-toplevel)" --mode full`
   - The helper always sends the canonical owning checkout to `index_repository`.
   - Use `--mode fast` for a smoke index.
5. Verify the graph.
   - `codebase-memory-mcp cli list_projects`
   - `scripts/codebase-memory-graph.sh schema --repo "$(git rev-parse --show-toplevel)"`
   - Run one focused graph query before declaring success.
6. Verify the UI when requested.
   - Default URL: `http://127.0.0.1:9749/`.
   - The helper creates a repository-scoped tmux keepalive session.
7. Audit cache cleanup before applying it.
   - Freeze a host-specific manifest:
     `scripts/codebase-memory-graph.sh cache-audit --manifest /secure/path/cbm-cache.json`
   - Missing roots are protected unless the audit names an explicit narrow `--ephemeral-prefix`.
   - Linked-worktree candidates require a mapped, indexed, healthy full canonical clone. Shallow, promisor, partial, missing, or ambiguous canonical graphs stay protected.
   - When legacy home symlinks name the same physical checkout, preserve the exact canonical graph and treat only the symlink-named graph as a duplicate. Preserve a sole symlink-named graph.
   - Review the manifest, then dry-run it:
     `scripts/codebase-memory-graph.sh cache-prune --manifest /secure/path/cbm-cache.json`
   - Manifests with host blockers fail closed by default. After reviewing every relationship, explicitly add `--allow-blocked-manifest` to preflight and prune only independent candidates while preserving all protected and blocked projects.
   - To retain an exact manifest candidate at runtime, repeat `--protect-candidate NAME` on `cache-prune`. Each named candidate must still exist in the unchanged snapshot and pass its root, prefix, classification, canonical mapping, and clone-health rules. It remains in the expected snapshot but is excluded from cache inventory, holder sweeps, DB integrity preflight, final holder probes, and deletion.
   - Runtime candidate protection does not bypass host blockers; add `--allow-blocked-manifest` independently when blockers were reviewed. Unknown, duplicate, or non-candidate names fail before preflight.
   - Apply only the unchanged manifest:
     `scripts/codebase-memory-graph.sh cache-prune --manifest /secure/path/cbm-cache.json --apply`
   - Dry-run and apply freeze regular DB/WAL/SHM fingerprints for every eligible candidate in manifest order, rejecting a missing or size-mismatched DB, nonregular files, and nonzero WAL. Existing paths are swept for holders in deterministic, NUL-parsed `lsof` batches before any SQLite open and again after every exact `mode=ro&immutable=1` `quick_check`; global fingerprint equality is required between phases. An absent or zero-byte WAL and a stable regular SHM are allowed.
   - Batch holder sweeps are point-in-time checks: a transient read-only holder between sweeps is harmless, stable fingerprints detect normal writers, and the final single-candidate holder probe is the deletion authority. Apply rechecks the snapshot, candidate rules, and inode/device/size/mtime fingerprints, then performs that final holder probe immediately before each deletion. Held databases, nonregular sidecars, nonzero WAL, corrupt databases, drift, fingerprint changes, deletion failures, or database/WAL/SHM residue stop immediately. The failure reports any projects already deleted.
   - Deletion uses `codebase-memory-mcp cli delete_project` only. Never remove project databases directly.
8. Report exact proof.
   - Indexed project name.
   - Node and edge counts when available.
   - UI URL and tmux session name.
   - For cleanup: manifest path and digest, manifest/eligible/preflighted candidate totals, runtime protected names/reasons/bytes, before/after project and byte totals, deleted project names, and any stop condition.
   - Missing binaries, unavailable MCP tools, or incomplete proof.

## Inputs

- Repository path.
- Index mode: `fast`, `moderate`, `full`, or `cross-repo-intelligence`.
- Optional UI port; default `9749`.
- For cache maintenance: a host-local manifest path, optional explicit ephemeral prefixes, and optional exact runtime protected candidate names.

## Outputs

- Indexed and queryable repository graph.
- Verified local graph UI when requested.
- A dry-run cache manifest or guarded CLI-only deletion report.
- Exact status, schema, and proof summary.
