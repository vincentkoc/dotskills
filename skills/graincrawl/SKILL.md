---
name: graincrawl
description: Maintain, verify, and release graincrawl, the local-first Granola archive CLI, including SQLite archive behavior, read-only Granola source boundaries, Homebrew tap packaging, and crawlkit-powered TUI/snapshot surfaces.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Graincrawl

## Purpose

Maintain `graincrawl`, the Go CLI that archives Granola notes, transcripts,
panels, people, workspaces, and sync metadata into a private local SQLite store.
Keep it read-only against Granola, SQLite-first for browsing/export, and aligned
with the other crawl apps.

## When to use

- Editing or reviewing `/Users/vincentkoc/GIT/_Perso/graincrawl`.
- Investigating Granola source adapters: `private-api`, `desktop-cache`,
  `encrypted-json`, `opfs`, `public-api`, or `companion-cli`.
- Verifying note, transcript, panel, source object, search, Markdown export, or
  TUI behavior.
- Preparing a `graincrawl` release, Homebrew formula, or local binary refresh.
- Checking crawlkit control metadata, snapshots, or TUI integration from the app
  side.

## Workflow

1. Work in `/Users/vincentkoc/GIT/_Perso/graincrawl` unless the user points at a
   different checkout. Read repo-local `AGENTS.md`, `README.md`, `SPEC.md`, and
   `docs/security.md` before release, source-adapter, or unlock work.
2. Keep Granola boundaries explicit. Ordinary `doctor`, `status`, `notes`,
   `export`, and `tui` commands must not prompt Keychain, unwrap safeStorage, or
   mutate Granola profile files.
3. Use temp `HOME`, temp XDG dirs, temp config, and temp SQLite databases for
   tests and smoke checks. Do not mutate live `~/.config/graincrawl` archives or
   Granola app data unless the user explicitly asks.
4. Prefer archived SQLite reads for UI/export behavior. If Markdown export has
   the data, TUI detail should read that same archived source, not re-query
   Granola.
5. Run the normal local gate with workspace masking disabled:

   ```bash
   GOWORK=off go mod tidy
   git diff --exit-code -- go.mod go.sum
   GOWORK=off go vet ./...
   GOWORK=off go test -count=1 ./...
   make smoke
   goreleaser check
   ```

6. For release work, use semver tags and verify the tap path:

   ```bash
   git tag -a v0.1.0 -m "graincrawl v0.1.0"
   git push origin main v0.1.0
   HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source vincentkoc/tap/graincrawl
   HOMEBREW_NO_AUTO_UPDATE=1 brew test vincentkoc/tap/graincrawl
   ```

7. After app changes, refresh the local binary when requested or when handing
   off a testable CLI:

   ```bash
   GOWORK=off go build -trimpath -o ~/.local/bin/graincrawl ./cmd/graincrawl
   graincrawl version --json
   ```

## Inputs

- Target task: app edit, source-adapter investigation, local archive/TUI fix,
  release verification, tap update, or binary refresh.
- Optional version tag such as `v0.1.0`.
- Optional temp fixture paths or a copied Granola profile for encrypted/OPFS
  investigation.

## Outputs

- A focused graincrawl change or readiness report.
- Validation commands and results.
- Explicit notes about any private API, Keychain, safeStorage, OPFS, or live
  profile boundary crossed.
- Tap/release status and local binary path when release or install work is in
  scope.
