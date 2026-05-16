# Local Semantic Workflow

## Scratch layout

Use a run directory outside the target checkout:

```bash
RUN_ROOT="$HOME/.semantic-slicing/openclaw/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN_ROOT"
```

Recommended layout:

```text
<run>/
  clawpatch/
  deepsec/
  semantic-map.html
  semantic-map.json
```

## Clawpatch

Setup from source:

```bash
git clone https://github.com/openclaw/clawpatch.git ~/GIT/_Perso/clawpatch
cd ~/GIT/_Perso/clawpatch
pnpm install
pnpm build
```

Run against a target repo:

```bash
node ~/GIT/_Perso/clawpatch/dist/cli.js \
  --root ~/GIT/_Perso/openclaw \
  --state-dir "$RUN_ROOT/clawpatch" \
  init --json

node ~/GIT/_Perso/clawpatch/dist/cli.js \
  --root ~/GIT/_Perso/openclaw \
  --state-dir "$RUN_ROOT/clawpatch" \
  map --json

node ~/GIT/_Perso/clawpatch/dist/cli.js \
  --root ~/GIT/_Perso/openclaw \
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
git clone https://github.com/vercel-labs/deepsec.git ~/GIT/_Perso/deepsec
cd ~/GIT/_Perso/deepsec
pnpm install
pnpm -r build
pnpm bundle
```

Create a scratch workspace and link the local build:

```bash
node ~/GIT/_Perso/deepsec/packages/deepsec/dist/cli.mjs \
  init "$RUN_ROOT/deepsec" ~/GIT/_Perso/openclaw --id openclaw --force

cd "$RUN_ROOT/deepsec"
pnpm add -w "deepsec@file:$HOME/GIT/_Perso/deepsec/packages/deepsec"
```

Run deterministic scan:

```bash
node ~/GIT/_Perso/deepsec/packages/deepsec/dist/cli.mjs scan --project-id openclaw
node ~/GIT/_Perso/deepsec/packages/deepsec/dist/cli.mjs status --project-id openclaw
node ~/GIT/_Perso/deepsec/packages/deepsec/dist/cli.mjs metrics --project-id openclaw
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

## Visual map

Generate the local review map:

```bash
node /path/to/semantic-slicing/scripts/semantic-map.mjs \
  --clawpatch "$RUN_ROOT/clawpatch" \
  --deepsec "$RUN_ROOT/deepsec/data/openclaw" \
  --out "$RUN_ROOT/semantic-map.html"
```

The script writes both HTML and JSON. Use the HTML for review and the JSON for follow-up automation.
