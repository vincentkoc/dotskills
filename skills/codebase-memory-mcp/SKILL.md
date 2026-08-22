---
name: codebase-memory-mcp
description: Resolve canonical Git checkouts, index and verify codebase-memory-mcp graphs through the guarded CLI, and safely audit duplicate worktree caches. Use when a user mentions codebase memory MCP, search_graph, trace_path, index_repository, worktree indexes, or oversized graph caches.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Codebase Memory MCP

## Purpose

Bring up `codebase-memory-mcp` for the owning Git checkout and prove the graph is usable before relying on it for code discovery. Keep linked worktrees on the owner's graph instead of creating one graph per branch.

## When to use

- Initialize, re-index, refresh, or troubleshoot a repository graph.
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
   - Independent roots under `~/.codex/worktrees`, `~/GIT/_Worktrees`, any `.worktrees` component, `/tmp`, or `/private/tmp` are never indexed. Linked worktrees under those paths may only rewrite to one existing nonreserved owner.
   - Missing, invalid, bare, ambiguous, ownerless, reserved-owner, or NUL-containing repositories fail closed.
3. Prefer exposed MCP graph tools for discovery.
   - The MCP `index_repository` tool is intentionally disabled because it cannot enforce the canonical indexing boundary.
   - When a graph is missing, run `scripts/codebase-memory-graph.sh index --repo "$(git rev-parse --show-toplevel)" --mode full`.
   - Use `search_graph`, `trace_path`, and `get_code_snippet` before broad text scans.
4. Use the helper for CLI indexing.
   - `scripts/codebase-memory-graph.sh init --repo "$(git rev-parse --show-toplevel)" --mode full`
   - The helper always sends the canonical owning checkout to `index_repository`.
   - Use `--mode fast` for a smoke index.
   - Installer integrations render `scripts/codebase-memory-gateway.py.tmpl` with an approved pinned backend path. Replace `@@PYTHON_PATH_SHEBANG@@` with the raw absolute interpreter path and replace `@@PYTHON_PATH_JSON@@`, `@@BACKEND_PATH_JSON@@`, and `@@RESOLVER_PATH_JSON@@` with JSON string literals containing the exact absolute interpreter, backend, and `codebase_memory_cache.py` paths. The rendered gateway has no upgrade logic and uses `execve` for pass-through.
5. Verify the graph.
   - `codebase-memory-mcp cli list_projects`
   - `scripts/codebase-memory-graph.sh schema --repo "$(git rev-parse --show-toplevel)"`
   - Run one focused graph query before declaring success.
6. Treat the UI as unavailable.
   - `start-ui` and `keepalive` fail closed before configuration or process mutation.
   - UI startup remains disabled until upstream `/api/index` canonicalization can enforce the same boundary. `status` may report an already-running grandfathered listener.
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
   - Dry-run and apply freeze regular DB/WAL/SHM fingerprints for every eligible candidate in manifest order, rejecting a missing or size-mismatched DB, nonregular files, and nonzero WAL. Existing absolute paths are swept with `/usr/sbin/lsof -nP -F0pfn -f --` in deterministic, NUL-parsed batches before any SQLite open and again after every exact `mode=ro&immutable=1` `quick_check`; global fingerprint equality is required between phases. An absent or zero-byte WAL and a stable regular SHM are allowed. Use prune-only `--lsof-timeout-seconds SECONDS` to override the 300-second holder timeout within the guarded 30-900 range.
   - Batch holder sweeps are point-in-time checks: a transient read-only holder between sweeps is harmless and stable fingerprints detect normal writers. Unprivileged `lsof` may not see root-owned or other-user holders, so pruning trusts the point-in-time visibility available to the cache owner; running as root provides stronger holder visibility. Apply processes eligible candidates in manifest order, at most eight per deletion batch and within the same 128 KiB path budget. Each batch revalidates the snapshot, candidate relationships, and live fingerprints, performs one holder sweep, immediately proves post-sweep equality to both live and frozen fingerprints, then launches only `codebase-memory-mcp cli delete_project` children before draining them. The batch verifies registrations and DB/WAL/SHM absence once before continuing; spawn errors, timeouts, nonzero exits, retained registrations, residue, drift, or ambiguous state stop future batches and report launched, verified-deleted, failed, and ambiguous names and bytes.
   - Deletion uses `codebase-memory-mcp cli delete_project` only. Never remove project databases directly.
8. Report exact proof.
   - Indexed project name.
   - Node and edge counts when available.
   - Any grandfathered UI listener reported by `status`.
   - For cleanup: manifest path and digest, manifest/eligible/preflighted candidate totals, runtime protected names/reasons/bytes, before/after project and byte totals, deleted project names, and any stop condition.
   - Missing binaries, unavailable MCP tools, or incomplete proof.

## Inputs

- Repository path.
- Index mode: `fast`, `moderate`, `full`, or `cross-repo-intelligence`.
- Optional status listener port; default `9749`.
- For cache maintenance: a host-local manifest path, optional explicit ephemeral prefixes, and optional exact runtime protected candidate names.

## Outputs

- Indexed and queryable repository graph.
- A dry-run cache manifest or guarded CLI-only deletion report.
- Exact status, schema, and proof summary.
