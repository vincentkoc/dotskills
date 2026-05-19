---
name: crawlkit
description: Maintain and release the crawlkit Go library, preserving downstream compatibility for gitcrawl, slacrawl, discrawl, and notcrawl.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Crawlkit

## Purpose

Maintain crawlkit, the shared Go library for crawl app archive infrastructure.
Use this skill to keep shared archive infrastructure reusable, tagged, and safe
for downstream app branches.

## When to use

- Editing or reviewing `crawlkit`.
- Moving common crawl app behavior into the library.
- Checking whether `gitcrawl`, `slacrawl`, `discrawl`, or `notcrawl` can merge
  against a released `crawlkit` tag.
- Preparing or verifying a `crawlkit` Go module release.
- Investigating shared TUI, snapshot, config, SQLite, mirror, progress, or
  control metadata behavior.

## Workflow

1. Work in `/Users/vincentkoc/GIT/_Perso/crawlkit` unless the user points at a
   different checkout.
2. Read repo-local `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, and
   `docs/publishing.md` before release or compatibility work.
3. Keep provider-specific logic out of `crawlkit`. Shared mechanics belong in
   packages such as `config`, `store`, `snapshot`, `mirror`, `state`, `output`,
   `progress`, `tui`, `cache`, and `control`.
4. Run the library gate with workspace masking disabled:

   ```bash
   GOWORK=off go mod tidy
   git diff --exit-code -- go.mod go.sum
   GOWORK=off go vet ./...
   GOWORK=off go test -count=1 ./...
   ```

5. For release checks, verify the signed tag and public Go proxy:

   ```bash
   git tag -v <version>
   GOPROXY=https://proxy.golang.org GONOSUMDB= go list -m github.com/vincentkoc/crawlkit@<version>
   ```

6. For downstream readiness, inspect app branches read-only. Confirm they are
   clean, rebased, require the released `crawlkit` version, and pass:

   ```bash
   GOWORK=off go test ./...
   <app> --help
   <app> --version
   <app> metadata --json
   <app> status --json
   <app> tui --json
   ```

7. Use temp `HOME`, `XDG_CONFIG_HOME`, and `XDG_CACHE_HOME` for CLI smokes.
   Never mutate live app archives.

## Inputs

- Target task: library edit, release verification, downstream readiness, or TUI
  backport.
- Optional version tag such as `v0.4.0`.
- Optional downstream app branch paths.

## Outputs

- A clean `crawlkit` change or readiness report.
- Validation commands and results.
- Explicit compatibility risks for downstream app branches.
- Local binary rebuild notes only when the user asks for app binaries.
