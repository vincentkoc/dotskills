---
name: org-branch-cleanup
description: Audit and safely prune stale branches across a GitHub organization with immutable snapshots, conservative merged-PR classification, live SHA/protection/open-PR revalidation, resumable deletion ledgers, and post-delete verification. Use when a maintainer asks to clean up old, dead, merged, bot-created, or abandoned organization branches without risking default, protected, release, security-advisory, state, or active pull-request refs.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Org Branch Cleanup

## Purpose
Remove organization branch clutter without guessing which refs are safe to delete.

The bundled `scripts/org_branch_cleanup.py` separates the work into read-only audit, explicit apply, and full verification phases. Dry-run evidence is the default; deletion requires an exact organization confirmation.

## When to use
- A GitHub organization has accumulated old or merged development branches.
- Bot, agent, migration, or dependency branches remain after pull requests merge.
- A maintainer wants an evidence-backed cleanup ledger rather than broad `git push --delete`.
- Branch-heavy security, state, archive, or generated-data repositories need to be separated from ordinary development repos.
- A previous cleanup stopped midway and must resume without repeating completed deletions.

## Workflow
1. Read the target repository or organization instructions before mutation.
2. Confirm GitHub authentication and rate-limit headroom:
   - `gh auth status`
   - `gh api rate_limit --jq '.resources | {core,graphql}'`
3. Run a read-only audit:
   ```bash
   python3 scripts/org_branch_cleanup.py audit \
     --org example-org \
     --output /tmp/example-org-branch-audit
   ```
   Start with `--include-repo-regex '^one-repo$'` when proving access or policy.
   Audit output is immutable by default; use a new directory rather than `--overwrite`.
4. Inspect `audit-summary.json`, `audit-errors.tsv`, and `delete-candidates.jsonl`.
   - Do not apply a partial audit. Fix failed repository queries or explicitly justify `--allow-partial`.
   - Default candidates are same-repository PR heads merged at least 14 days ago.
   - Closed-unmerged branches and unassociated stale branches are report-only.
   - Default, fork, archived, protected, and release-like refs are excluded.
   - Repositories matching GHSA, state, or archive patterns are excluded by default. Audit them separately under an explicit retention policy.
5. Apply only after the candidate set is reviewed:
   ```bash
   python3 scripts/org_branch_cleanup.py apply \
     --candidates /tmp/example-org-branch-audit/delete-candidates.jsonl \
     --confirm-org example-org \
     --output /tmp/example-org-branch-apply
   ```
   `apply` requires the clean sibling `audit-summary.json`. Do not bypass this with `--allow-unverified-candidates` or `--allow-partial-audit` without an explicit operator decision.
6. Treat each preflight skip as a safety result, not a failure.
   - `moved`: branch SHA changed after the snapshot.
   - `protected`: REST or ruleset protection blocked deletion.
   - `open-pr`: a live pull request now uses the branch.
   - `missing`: GitHub or another operator already removed it.
7. Verify every deletion:
   ```bash
   python3 scripts/org_branch_cleanup.py verify \
     --ledger /tmp/example-org-branch-apply/deleted.tsv \
     --output /tmp/example-org-branch-apply/verification-rerun.tsv
   ```
8. Report exact deleted, skipped, retained, excluded-repository, and verification counts. Preserve the ledger until the cleanup is accepted.

## Safety rules
- Never delete default, protected, release, pages, stable, or active-PR branches.
- Never infer safety from branch age or naming alone.
- Require a same-repository PR whose head name matches the current branch tip.
- Re-read the live SHA, protection status, and open PRs immediately before deletion.
- Refuse organization mismatch between the candidate ledger and `--confirm-org`.
- Keep closed-unmerged deletion disabled unless the operator explicitly passes `--allow-closed-unmerged`.
- Stop broad scans when generated or security repos contain thousands of refs; define retention policy first.
- If a proxy or wrapper stalls, preserve ledgers and resume with the real GitHub CLI. Do not restart shared daemons owned by other sessions.

## Inputs
- GitHub organization login.
- Authenticated `gh` CLI with repository administration permission.
- Output directory for snapshots and ledgers.
- Optional retention windows and repository or branch exclusion regexes.
- Optional `--gh-bin` override for a compatible GitHub CLI wrapper.

## Outputs
- `snapshot.jsonl`: immutable branch and PR-tip evidence.
- `delete-candidates.jsonl`: old merged branches eligible for live preflight.
- `closed-unmerged-review.jsonl`: abandoned PR heads requiring explicit approval.
- `stale-unassociated.tsv`: old branches with insufficient deletion proof.
- `deleted.tsv` and `skipped.tsv`: resumable mutation ledger.
- `verification.tsv`: post-delete ref state.
- JSON audit and apply summaries with exact counts and timestamps.
