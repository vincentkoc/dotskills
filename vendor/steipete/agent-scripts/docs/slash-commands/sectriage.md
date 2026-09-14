---
summary: "Finish security advisory triage (land fix, gates, GHSA patch, ready-to-publish)."
read_when:
  - After discussion, when asked to finish GHSA triage end-to-end.
argument-hint: "<ghsa-or-url?>"
---
# /sectriage

Use after discussion. When you say “update this on GitHub via gh” (or you type `/sectriage`), that is consent for remote writes: I will patch the GHSA via `gh api` and verify.

## Intent

Default intent: land the fix on `main` directly (commit + push; no PR), update `CHANGELOG.md`, and keep the GHSA in a “ready to publish later” state. No separate/private PR workflow unless you explicitly ask.

## Invocation Format (you paste, optional)

Prefer minimal. If you only give `ghsa` (or URL), I will derive the rest from the repo + tags and only ask if something is ambiguous.

- `repo`: `owner/name` (optional; default from `git remote`)
- `ghsa`: `GHSA-....` (or advisory URL)
- `severity`: `low|medium|high|critical`
- `cvss`: full vector string (optional; but include if we want it set/restored)
- `affected`: human range line for text (example: `<= 2026.2.13`)
- `vuln_range`: GitHub structured `vulnerable_version_range` (example: `<=2026.2.13`)
- `patched_versions`: planned fixed version (normally the version you’re about to ship next; from changelog/release prep)
- `package`: usually `openclaw` (npm)
- `credits`: reporter handle (example: `@akhmittra`)
- `fix_commits`: one or more full SHAs (required once a fix is merged)
- `summary`: 1-liner summary (no GHSA id)
- `description_md`: full Markdown for advisory description (must include an “Affected Packages / Versions” section)

## What I Do (execute, not suggest)

1. Parse inputs. Derive `repo` from `git remote -v` if omitted. Extract GHSA id from URL if needed.
2. Preflight:
   - `git status --porcelain` (must be clean or only expected files)
   - fetch advisory via `gh api …security-advisories/<GHSA>` and show current structured fields
   - existing fix PR scan (prefer re-use; avoid duplicate fixes):
     - if advisory has `private_fork.full_name`: `gh pr list -R <privateFork> --state open`
     - also search upstream: `gh pr list -R <repo> --search "<GHSA>" --state all`
     - if there’s a credible fix PR already:
       - review via `gh pr view` / `gh pr diff`
       - fetch PR head branch and cherry-pick commits (avoid local branch switching): `git fetch <remote> <headRef>` then `git cherry-pick <sha>…`
   - fetch latest published versions:
     - `npm view <pkg> version --userconfig "$(mktemp)"`
     - update `vulnerable_version_range` to include that latest version if the issue still exists on `main`
   - fixed-version rule (optimize for “press publish only”):
     - use the planned next release version from `CHANGELOG.md` (if present) or `package.json`
     - set `patched_versions` to that planned version even if npm publish hasn’t happened yet
     - this keeps the advisory ready so the only follow-up action is “Publish” after npm is out
3. Local verify (required):
   - `pnpm check`
   - `pnpm exec vitest run --config vitest.gateway.config.ts`
   - `pnpm test:fast`
4. Changelog:
   - ensure `CHANGELOG.md` has `## Unreleased` + `### Fixes` entry
   - no GHSA id mention
   - includes thanks to reporter
   - ensure wording implies it ships in the next npm release (that’s the whole point: no more ticket edits)
   - commit only if changelog needed changes
5. Git:
   - if there are local commits ahead of origin: `git pull --rebase` then `git push`
6. Similar-issue scan (read-only):
   - list other `pathToFileURL(` + dynamic `import(` callsites
   - list obvious path-join/resolve callsites
   - if I find a credible escape bug: stop and report (do not “surprise-fix” during /sectriage)
7. GHSA patch (remote write; invocation is consent):
   - write `/tmp/ghsa.desc.md` from `description_md`
   - required in `description_md`:
     - explicit versions (latest published + affected ranges)
     - “Fix Commit(s)” section with one or more full git SHAs (or “pending” if not merged yet)
     - “Release Process Note”: patched version is pre-set to the planned next release; once npm release is out, just publish the advisory
   - write `/tmp/ghsa.patch.json` with `summary`, `severity`, `description`, and `vulnerabilities[]`:
     - `vulnerable_version_range` uses latest published npm version (usually `<=<npmVersion>`)
     - `patched_versions` uses the planned next release version (from changelog/package.json)
   - `gh api -X PATCH … --input /tmp/ghsa.patch.json`
   - if `cvss` provided: patch `cvss_vector_string`
8. Verify:
   - re-fetch advisory, print `html_url`, `state`, `vulnerabilities`, `cvss`, `updated_at`
   - print GHSA link

## Implementation Notes (hard rules)

- Avoid JSON quoting footguns:
  - `description_md` goes to `/tmp/ghsa.desc.md`
  - build JSON via `jq -n --rawfile desc /tmp/ghsa.desc.md …`
- Advisory comments endpoint may not exist via REST; update via `description` + structured fields.
- State transitions (accept/publish) likely UI/Publisher-only; do not attempt unless you explicitly ask.
