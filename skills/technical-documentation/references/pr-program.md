# Turning a Finding Ledger into a PR Program

A large audit produces thousands of findings. One PR cannot carry them and one PR per finding is unreviewable. This file defines how to group a ledger into PRs, in what order to land them, and what each PR must contain.

## Grouping rule

**One PR is one logical change family in one directory.** A reviewer then reads one kind of change and approves on one mental model.

- Cap a PR at about 15 files or 40 findings. Beyond that, split into numbered parts.
- An oversized-page split is its own PR, one page per PR, because it moves content and needs redirects.
- Cross-cutting mechanical fixes (typos, redirects, titles) are one PR each, tree-wide, because they are trivial to review in bulk and awkward to split.
- A fix that belongs in another repository is its own PR there. Say so in the program.

## Change families

| Family | Covers | Rubric items |
|---|---|---|
| Hygiene and governance | Publish-tree hygiene, private paths, typos, redirects, duplicate titles | 12, 13 |
| Generator fixes | Pages a script writes: split the output, add generated banners, fix shared templates | 6, 12 |
| i18n | Locale navigation, glossaries, translation workflow docs, i18n checks | 11, 14 |
| Navigation and IA | Orphans, ghosts, oversized groups, jargon names, misplaced pages, landing and hubs | 14, 10 |
| Reader funnel | The first-run path from landing page to first working task | 2, 4 |
| Oversized-page splits | One page per PR, with redirects and inbound-link updates | 3, 5, 6 |
| Duplicate-rule consolidation | One owner page per rule, links replace copies | 13 |
| Prerequisites and missing steps | "Before you start" lists, missing commands | 4 |
| Dense prose and tables | Lists, definition lists, sub-headings | 6, 7 |
| Page structure | First screen, funnel order, heading hierarchy | 1, 2, 5 |
| Hidden content | Facts trapped in accordions, tabs, and images | 9 |
| Version scope and samples | Undated claims, samples that do not run | 12, 8 |
| Factual accuracy | Contradictions between pages and the code | 8, 13 |
| Cross-links | Anchors, Related sections, back-links | 10 |
| Simplified Technical English | Prose passes on pages over the hard-rate threshold | 11 |

## Phase order

Land in this order. Later phases inherit the structure earlier phases settle.

0. Hygiene, generators, i18n, templates. Independent of everything, and generator fixes remove pages later phases would otherwise touch by hand.
1. Navigation and the reader funnel. Sets where pages live before anything moves.
2. Oversized-page splits, largest first. Every later per-directory PR in that directory depends on these.
3. Structure: duplicate rules, prerequisites, density, page structure, hidden content.
4. Accuracy: version scope, facts, cross-links.
5. Simplified Technical English prose, last, so it runs on settled structure. Run the tree-wide term-collision PR before the per-directory prose PRs.

## Dependencies

- A directory's phase 3 to 5 PRs depend on that directory's split PRs.
- Every STE prose PR depends on the term-collision PR.
- Split PRs and nav PRs depend on the redirect-hygiene PR.
- Record dependencies in the program so PRs can land in parallel where they do not overlap.

## Drift: an audit has a shelf life

Findings cite line numbers at one commit. A fast-moving repository invalidates them quickly. Measure drift before you remediate, and re-measure if remediation stretches over days.

1. Compare the audited tree to the target branch by blob hash, not by diff text: `git ls-tree -r <commit> docs` on both sides, then join on path. You get three sets: unchanged, content-changed, and gone.
2. Map every live finding onto those sets and report the percentage on changed files. A measured example: two days and 1,352 commits after one audit, 22 percent of pages had changed. 46 percent of live findings pointed at them.
3. Route the work by set:
   - Findings on unchanged files apply as written. Edit directly.
   - Findings on changed files go through a cheap re-validation agent first. It reports still-applies, already-fixed, or needs-update per finding, reading only the cited region.
   - Findings on files that no longer exist are re-targeted or closed as `wontfix` with the reason.
4. Set the re-validated statuses in the ledger before the remediation agent runs. Never let an editor work from a stale line number.
5. Rebase the branch and re-run the drift comparison if a PR sits unmerged for more than a few days.

## Green CI is not proof

A repository can route checks by changed path. A docs-only PR may skip the lane that would have caught its defect. The break then lands on the default branch, where nobody is watching for it.

1. After CI passes, read the skipped list, not just the failed list. A high skip count on a PR that changes structure is a warning.
2. For any PR that adds pages, moves pages, or edits navigation, find the tests that read the navigation config or assert route shapes. Run them locally. Grep the test tree for the config filename.
3. Treat repeated failures on an unrelated-looking check as a signal, not as flakiness. Read the failing test name on every run. A shard that fails four times is telling you something, and the test that fails may change between runs.
4. When a merged PR breaks the default branch, fix forward immediately with a PR that names the invariant it violated and quotes the assertion.

A worked example: a PR split an oversized release page into 23 child pages and added each to the navigation. A test asserted every page in that navigation group matched a version-route pattern, which the child routes did not. The docs-only classification skipped that lane, so the failure appeared first on the default branch. The test's own comment predicted exactly this. Every docs validator had passed.

## What every PR contains

- Title: family plus scope, for example `docs(channels): consolidate duplicated group rules to one owner page`.
- Body: what changed, why, the ledger finding ids it closes, and the validator output.
- Only the listed findings. Anything else found on the way becomes a new ledger row, not a wider diff.
- Validator run: the repo's native docs checks plus `scripts/ste-lint.py` on the touched files. Hard violations must not increase.
- For splits: one redirect per moved anchor, updated inbound links, and the same change in every locale navigation file.

## Generating the program

Write a script (`prs.py`) that reads the ledger and emits both a Markdown program and a JSON file. Keep it deterministic so it regenerates after every ledger change.

1. Assign each live finding to a family by rubric, kind, file prefix, and shard.
2. Claim structural findings first with hand-defined PRs (hygiene, nav, generators, i18n, funnel, templates).
3. Group the rest by family and directory, then chunk to the file and finding caps.
4. Sort by phase, then family, then key. Number the PRs.
5. Emit per PR: id, phase, family, title, files, finding ids, severity counts, dependencies, and the top findings with their fixes.

## Tracking

- When a PR lands, set its findings to `status: fixed` with the PR number, then regenerate the report and the program.
- Report progress as findings closed over findings live, per phase, not as PRs merged. A merged PR that closed three of its twelve findings is not done.
- Keep refuted findings visible. They are the audit's own error rate.
