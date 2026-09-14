# OpenClaw Profile

Target repo: `openclaw/openclaw`.

## High-signal buckets

- `src/agents/**`: agent tools, shell/process/file access, sandbox policy, session reuse.
- `src/gateway/**`: protocol, auth, WebSocket, delivery, live runtime.
- `src/plugins/**`: plugin discovery, registry, activation, manifest/public-surface loaders.
- `extensions/*`: bundled plugin runtime boundaries, channel/provider behavior.
- `packages/memory-host-sdk/**`: storage, embeddings, remote HTTP, SSRF and proxy controls.
- `scripts/**`: release, CI, Docker, package, generated contract checks.
- `ui/**` and apps: local app/browser boundary, WebView and bridge surfaces.

## Default excludes

Treat these as contamination unless explicitly requested:

```text
.git/
.claude/
.codex/
.agents/
.deepsec/
.semantic-slicing/
node_modules/
dist/
build/
coverage/
.next/
.turbo/
```

## Local probe on 2026-05-16

Observed setup results on `openclaw/openclaw`:

- `clawpatch` built locally and mapped 1,099 feature records.
- The map included hundreds of `.claude`/`.codex`/`.agents` path references even with a config exclude. Post-filtering is required before review queue ranking.
- `deepsec` built locally and scanned OpenClaw in 53.7 seconds.
- Deepsec scan run ID: `20260516011830-96433ac3b3b6762a`.
- Deepsec found 4,055 pending candidate files and 9,628 total matcher hits.
- Highest-volume slugs were `insecure-crypto`, `agent-tool-definition`, `process-env-access`, `secret-in-log`, and `spread-operator-injection`.
- `gitcrawl doctor --json` showed local OpenClaw data but the last sync was older than the current date, so use it as shortlist context and verify live state with `gh` before mutating.
- `discrawl doctor --json` was healthy in git-share mode; `discrawl status --json` showed share update needed.

Hydrated follow-up on the same day:

- Hydrated `deepsec` with OpenClaw-specific `INFO.md` and priority/ignore config.
- Fresh scan run ID: `20260516014350-082402b74eb441df`.
- Fresh scan found 4,050 candidate files and 9,579 total matcher hits.
- One targeted AI process pass on `src/agents/pi-embedded-runner/run/attempt.ts` produced 0 findings, cost `$4.794546`, and used 236,258 input tokens plus 6,065,152 cache-read tokens.
- That file mapped to clawpatch feature `feat_library_997fa9c066`; dry-run review returned `wouldReview: 1`.

Operational implication: default to `low` cost sizing for maps and queue building. Use `medium` only for file-explicit high-risk slices. Treat broad `deepsec process` as `high` cost unless the user has set a clear budget.

## OpenClaw verification rule

Mapping is not validation. If a slice leads to a code change, follow OpenClaw repo rules for targeted tests and Testbox/Crabbox proof before handoff.
