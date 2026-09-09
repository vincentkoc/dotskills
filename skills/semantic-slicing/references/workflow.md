# Local Semantic Workflow

## Scratch layout

Reuse suitable existing tool state. Map inspection alone does not need a new directory.
If Clawpatch or Deepsec requires physical state, create one task-owned temporary directory:

```bash
TOOLS_ROOT="${TOOLS_ROOT:-$HOME/src}"
TARGET_REPO="${TARGET_REPO:-$HOME/src/openclaw}"
RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/semantic-slicing.XXXXXX")"
```

Keep only necessary tool state and file inputs there:

```text
<run>/
  clawpatch/
  deepsec/
  gitcrawl-evidence.json
  discrawl-evidence.json
```

Create evidence JSON inputs only when the map needs those overlays.
Do not retain each command's output or intermediate summaries.
Remove only this task's disposable scratch after its consumers finish.
Preserve active state, named deliverables, and evidence needed for recovery.
Report any retained path and its purpose in chat.

## Clawpatch

Setup from source:

```bash
git clone https://github.com/openclaw/clawpatch.git "$TOOLS_ROOT/clawpatch"
cd "$TOOLS_ROOT/clawpatch"
pnpm install
pnpm build
```

Run against a target repo:

```bash
node "$TOOLS_ROOT/clawpatch/dist/cli.js" \
  --root "$TARGET_REPO" \
  --state-dir "$RUN_ROOT/clawpatch" \
  init --json

node "$TOOLS_ROOT/clawpatch/dist/cli.js" \
  --root "$TARGET_REPO" \
  --state-dir "$RUN_ROOT/clawpatch" \
  map --json

node "$TOOLS_ROOT/clawpatch/dist/cli.js" \
  --root "$TARGET_REPO" \
  --state-dir "$RUN_ROOT/clawpatch" \
  status --json
```

After mapping, check contamination:

```bash
find "$RUN_ROOT/clawpatch/features" -type f -print0 |
  xargs -0 jq -r '.ownedFiles[].path, .entrypoints[].path, .contextFiles[].path' |
  rg '^\.(claude|codex|agents|deepsec|semantic-slicing)/' | wc -l
```

If contamination is non-zero, post-filter before ranking. Current clawpatch may still seed hidden local worktree paths even when config excludes are present.

## Deepsec

Setup from source:

```bash
git clone https://github.com/vercel-labs/deepsec.git "$TOOLS_ROOT/deepsec"
cd "$TOOLS_ROOT/deepsec"
pnpm install
pnpm -r build
pnpm bundle
```

Create a scratch workspace and link the local build:

```bash
node "$TOOLS_ROOT/deepsec/packages/deepsec/dist/cli.mjs" \
  init "$RUN_ROOT/deepsec" "$TARGET_REPO" --id openclaw --force

cd "$RUN_ROOT/deepsec"
pnpm add -w "deepsec@file:$TOOLS_ROOT/deepsec/packages/deepsec"
```

Run deterministic scan:

```bash
node "$TOOLS_ROOT/deepsec/packages/deepsec/dist/cli.mjs" scan --project-id openclaw
node "$TOOLS_ROOT/deepsec/packages/deepsec/dist/cli.mjs" status --project-id openclaw
node "$TOOLS_ROOT/deepsec/packages/deepsec/dist/cli.mjs" metrics --project-id openclaw
```

Do not run `process` blindly on large candidate sets. Size the run first:

| Size | Use when | Shape |
| --- | --- | --- |
| `low` | You need a review map or queue only. | `clawpatch map`, `deepsec scan`, `semantic-map.mjs`; no AI processing. |
| `medium` | A slice has strong threat + feature overlap. | 1-3 files/features, high-risk slugs only, `--batch-size 1`, `--concurrency 1`, capped turns. |
| `high` | The user explicitly wants broad AI review and accepts cost/time. | Multiple features or wider filters; record budget, run IDs, and stopping condition first. |

Prefer file-explicit processing after ranking:

```bash
pnpm deepsec process --project-id openclaw \
  --files src/agents/pi-tools.read.ts,src/agents/sandbox/ssh-backend.ts \
  --only-slugs path-traversal,rce,ssrf,auth-bypass,missing-auth,secret-in-log \
  --batch-size 1 \
  --concurrency 1 \
  --max-turns 40
```

If you only need matcher-level narrowing:

```bash
pnpm deepsec scan --project-id openclaw --matchers path-traversal,rce,ssrf
```

## Gitcrawl

Use gitcrawl as issue/PR memory, not live truth:

```bash
gitcrawl doctor --json
gitcrawl clusters openclaw/openclaw --min-size 2 --limit 20 --sort size --json
gitcrawl threads openclaw/openclaw --numbers 123,456 --include-closed --json
```

For freshness, re-check decisive open/closed/merged state with `gh` before mutation.

## Discrawl

Use discrawl for support/channel evidence when user reports mention Discord, support chatter, or community symptoms:

```bash
discrawl doctor --json
discrawl status --json
discrawl search "gateway auth" --limit 25 --json
discrawl digest --help
```

Avoid pulling personal or unrelated message content into reports. Summarize only the symptom evidence needed to rank the slice.

## Map output

The default is JSON on stdout, with no output files or directories.
Use Bash or Zsh for the pipelines below. `pipefail` preserves upstream command failures.
Do not treat output from a failed pipeline as successful evidence.
For routine inspection, select bounded fields before sending data to an agent:

```bash
set -o pipefail
node /path/to/semantic-slicing/scripts/semantic-map.mjs \
  --repo "$TARGET_REPO" |
  jq '{totals, inputs: {sparse: .inputs.sparse, sparseExcludes: .inputs.sparseExcludes, sparseIncludes: .inputs.sparseIncludes}, top: [.buckets[:8][] | {name, impactScore, action}]}'
```

Use `--out` only for a requested deliverable or required evidence.
Set `MAP_PATH` to that destination, outside disposable scratch.
Generate a requested visual map and its JSON data:

```bash
node /path/to/semantic-slicing/scripts/semantic-map.mjs \
  --repo "$TARGET_REPO" \
  --churn-since 90.days \
  --clawpatch "$RUN_ROOT/clawpatch" \
  --deepsec "$RUN_ROOT/deepsec/data/openclaw" \
  --gitcrawl "$RUN_ROOT/gitcrawl-evidence.json" \
  --discrawl "$RUN_ROOT/discrawl-evidence.json" \
  --out "$MAP_PATH"
```

Omit `--gitcrawl` or `--discrawl` when that evidence file is not needed.

| Options | Result |
| --- | --- |
| No `--out` or `--format` | JSON on stdout, no files. |
| `--format html` without `--out` | HTML on stdout, no files. |
| `--out map.html` | HTML at `map.html` and JSON at `map.json`, as before. |
| `--format json --out result.json` | JSON at exactly `result.json`, no HTML. |
| `--format html --out map.html` | HTML at exactly `map.html`, no JSON. |
| `--format both` | Requires `--out`. |

Use one stable destination per deliverable. Do not create timestamped report copies for repeated inspection.
File-write notices go to stderr, so stdout contains only the selected payload.

Sparse mode is enabled by default. It omits dotfile/config trees, docs,
changelog files, and mobile app trees so the first board focuses on core review
surfaces. Disable it for a whole-repo inspection:

```bash
set -o pipefail
node /path/to/semantic-slicing/scripts/semantic-map.mjs \
  --repo "$TARGET_REPO" \
  --clawpatch "$RUN_ROOT/clawpatch" \
  --deepsec "$RUN_ROOT/deepsec/data/openclaw" \
  --no-sparse |
  jq '{totals, top: [.buckets[:8][] | {name, impactScore, action}]}'
```

Tune sparse mode with comma-separated path rules. `--sparse-exclude` replaces
the default exclude list; `--sparse-include` re-includes matching paths:

```bash
set -o pipefail
node /path/to/semantic-slicing/scripts/semantic-map.mjs \
  --repo "$TARGET_REPO" \
  --clawpatch "$RUN_ROOT/clawpatch" \
  --deepsec "$RUN_ROOT/deepsec/data/openclaw" \
  --sparse-exclude ".github/,.vscode/,.devcontainer/,docs/,CHANGELOG.md,apps/android/,apps/ios/" \
  --sparse-include "apps/android/" |
  jq '{totals, inputs: {sparseIncludes: .inputs.sparseIncludes}, top: [.buckets[:8][] | {name, impactScore, action}]}'
```

The `--repo`, `--gitcrawl`, and `--discrawl` inputs are optional. Use `--repo`
when you want ownership routing from CODEOWNERS plus development pressure from
tracked file shape and recent git churn. Use `--gitcrawl` and `--discrawl` when
you want issue/support overlays; omit them for a code-only map.

Use `--churn-since` to size the development lens. `30.days` is good for a fast
current-sprint view; `90.days` is better for planning refactors or ownership
reviews.

HTML output is a semantic review board:
review lanes for humans first, focus controls for lens and system filtering
second, an overall lens matrix as the single slice-row table third, a compact
agent handoff packet fourth, and collapsible evidence tables last. The JSON contains
`semanticBuckets`, `ownershipOverlay`, `developmentOverlay`, `securityOverlay`,
`issueOverlay`, `supportOverlay`, `normalizedQueues`, and combined `buckets`
for follow-up automation. It also records `inputs.sparse`,
`inputs.sparseExcludes`, and `inputs.sparseIncludes` so agents can tell whether
the board is core-focused or whole-repo.

Read the board in this order:

1. Use the review lanes to pick the type of work: architecture, ownership
   routing, development cleanup, security, issue triage, or support triage.
2. Use the focus controls to narrow by lens or top-level system without
   duplicating the matrix rows.
3. Use the overall lens matrix to compare buckets without letting one lens own
   the whole queue.
4. Give the agent handoff packet to follow-up agents when delegating a slice.
5. Open evidence tables only when auditing why a bucket ranked where it did.
