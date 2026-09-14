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
   - Findings on changed files go through a cheap re-check agent first. It reports still-applies, already-fixed, or needs-update per finding, reading only the cited region.
   - Findings on files that no longer exist are re-targeted or closed as `wontfix` with the reason.
4. Set the re-checked statuses in the ledger before the remediation agent runs. Never let an editor work from a stale line number.
5. Rebase the branch and re-run the drift comparison if a PR sits unmerged for more than a few days.

## Green CI is not proof

A repository can route its checks by changed path. A docs-only PR may skip the lane that would have caught its defect. The break then lands on the default branch, where nobody is watching for it.

1. After CI passes, read the skipped list, not just the failed list. A high skip count on a PR that changes structure is a warning sign.
2. For any PR that adds pages, moves pages, or edits navigation, find the tests that read the navigation config or assert route shapes. Run them locally. Grep the test tree for the config filename.
3. **Make sure the command you run actually runs the test.** A test runner with per-shard configs can accept a file path and match nothing. It then prints "No test files found" and exits 0. That is a false green, and it is worse than no check, because it buys false confidence. Read the reported test count before you trust a pass.
4. **A validator that walks tracked files cannot see the files you just created.** Run the formatter and the doc checks *after* `git add`, not before. In one split, the formatter reported "clean" while five new child pages sat untracked; staging them made it flag every one. Any check whose file count you can read is worth reading twice — once before staging and once after — because the number moving is the tell.
5. **Search for a pinned path the way the code writes it, not the way you write it.** A test that composes `path.join(DOCS_ROOT, "plugins", "x.md")` contains neither the full path nor the route, so a grep for either reports the page clean. Match on the bare filename too. This produced a false negative on a page that a test really did read.
6. Treat repeated failures on an unrelated-looking check as a signal, not as flakiness. Read the failing test name on every run. A shard that fails four times is telling you something, and the test that fails may change between runs.
7. When a merged PR breaks the default branch, fix forward immediately with a PR that names the invariant it violated and quotes the assertion.

A worked example: a PR split an oversized release page into 23 child pages and added each to the navigation. A test asserted every page in that navigation group matched a version-route pattern, which the child routes did not. The docs-only classification skipped that lane, so the failure appeared first on the default branch. The test's own comment predicted exactly this. Every docs validator had passed.

A test runner with per-project configs turns this into a trap with two doors. One config matched no files at all and exited 0. A second matched *some*: passing two paths to it ran the one it recognised, silently ignored the directory it did not, and printed a pass. The invocation looked thorough and covered an eighth of what it named.

And it has a mirror image. A third config *excluded* the path it was handed, printed "No test files found" and exited **1** — so the one test gating an entire PR's shape looked like a failure when it had simply never run. An agent nearly redesigned its split around that.

There is a third variant, and it is the one that wastes the most time: a run that is silently **over**-scoped. Passing a directory to a project config that does not recognise it as a filter ran 516 files and 15,847 tests instead of the two files intended — noticed only because it blew a ten-minute timeout, and it returned 76 failures that had nothing to do with the change. An over-scoped run does not just cost wall time; it hands you a failure set you must now explain, and the temptation is to wave it away rather than baseline it.

The check that catches all three: **read the file count the runner prints and compare it to the number of files you meant to run.** A green with a count of 1 where you expected 8 is a failure report, not a pass; a red with a count of 0 is not a failure at all. Neither colour means anything until the count is right.

Two more of the same shape, both found in a program's own instructions rather than its code:

- **A linter invoked with your glob instead of its config's.** The CI script passed no glob, because the config already carried one covering `.md` *and* `.mdx`. The brief's version passed `'docs/**/*.md'` — quietly skipping every `.mdx` page, including one that was in the work list. Invoke a linter the way its CI job does, not the way its manual says you can.
- **A baseline measured where the tools cannot run.** "Reproduce the failure at the base sha in a detached worktree" is right in spirit, but a detached worktree has no installed dependencies, so every validator exits on a dependency error — which reads as zero findings to anyone checking for output rather than exit status. The step meant to establish ground truth becomes the one most likely to invent it. Symlink the dependencies in, or measure in place.

## What every PR contains

- Title: family plus scope, for example `docs(channels): consolidate duplicated group rules to one owner page`.
- Body: what changed, why, the ledger finding ids it closes, and the validator output.
- Only the listed findings. Anything else found on the way becomes a new ledger row, not a wider diff.
- Validator run: the repo's native docs checks plus `scripts/ste-lint.py` on the touched files. Hard violations must not increase.
- **Enumerate the CI docs job's steps and run every one.** Read the `check-docs` (or equivalent) job and the `package.json` scripts it calls. A docs job usually runs more than the obvious link and format checks: a markdown linter with a repo-specific config is easy to miss, and its rules bite structural work. One split preserved original heading levels to keep anchors stable, which left two child pages opening at H3; the linter's heading-increment rule rejected them and the PR failed on a check no one had run locally. Run the linter with the repo's own `--config`, not defaults — default rules report line-length noise the repo has disabled.
- **Run the formatter the CI job runs, not a formatter.** A repository often has more than one. Read the `format:check` script in `package.json` and run exactly that. In one repository a docs-specific formatter reported clean while the repo-wide formatter flagged the same file. Three PRs failed CI on it in a row.
- For splits: every original anchor still resolving, updated inbound links, and the same change in every locale navigation file. See "A path is not a fragment" below for what preserving an anchor actually requires.

## Cite the default branch, not your own open PRs

When a program lands many PRs, it is easy to describe earlier work as done when it is still in review. Two briefs in one program told an agent to follow a sibling split as precedent; in both cases that split was an unmerged PR, so the structure it named did not exist in the tree the agent was working in.

Both agents caught it and substituted a real precedent, which is the outcome you want — but they spent effort discovering that the instruction was wrong, and a less careful one would have invented a shape or stalled.

1. **Before naming a precedent, check it is on the default branch.** `test -d docs/<page>/` costs nothing. A merged PR number in your own notes is not evidence the merge happened.
2. **Say which commit or branch the precedent lives on.** "Follow `docs/gateway/security/`, which is on main" is checkable; "follow the security split" is not.
3. **Expect the agent to correct you, and make that easy.** Ask for a report line naming any premise in the brief that did not hold. That line is where you learn your instructions have drifted from the repository.

The same failure appears in ledger findings written against an older commit: the fix field describes a structure that has since changed. Treat both the same way — as a hypothesis to verify against the current tree before acting.

## A finding cites coordinates that have already moved

Every finding in a large audit carries `file:line`, and by the third round those coordinates are fiction — pages get split, sections move, files get deleted. An agent that reads whatever now sits at the cited line will "fix" something that was never broken, carefully and with evidence.

Resolve the row against its recorded audit SHA first. Read the cited text at that exact commit, then locate it in the current tree. A nearby date is not a substitute for the audited revision; if the SHA is missing, mark the coordinates unverified until the source snapshot is recovered. One agent found rows citing line 553 of a file that is now 243 lines long, and an index page that no longer holds any of the content the row described.

Two adjacent shapes to name explicitly, because they are neither "fixed" nor "refuted" and agents stall on them:

- **Out-of-repo.** A row can name a file this repository does not contain — docs mirrored in at publish time from another repository, for instance. Not fixable here, not wrong. Report and move on.
- **False premise.** A row can ask you to change a generator that does not exist, or to reconcile a conflict between one page and nothing. Confirm the thing a row describes is real before acting on it. In one batch, two of four refutations were this shape.

## Dating a claim: which release shipped this?

Docs full of "currently", "not yet", and "recently removed" are the most common accuracy defect in a mature repository, and every fix needs a release number. Getting that number is archaeology, and there are three methods with different failure modes.

0. **Verify the tag corpus first.** A containment loop over an incomplete local tag set returns the earliest tag *you happen to have*. The query is correct and the input is not, which is the worst combination — the answer looks derived and checkable. This shipped a wrong beta number on a PR that had already been corrected once for a different dating error in the same sentence. Check the configured download guard and reuse local objects. Fetch only the relevant authorized tag range when the corpus is incomplete; if that proof is unavailable, mark the release claim unverified.
1. **Tag containment is the answer.** `git merge-base --is-ancestor <sha> v<X>` against successive tags; the first tag that contains the commit is the release that shipped it. It is the only method that is right by construction.
2. **The version in `package.json` at that commit is a cheap first guess.** Usually correct, and one agent validated it against a known-good datum before relying on it — a page already stated a removal landed in 2026.4.22, and the commit's manifest read `2026.4.22`. That check is worth doing. But it validates the method on a *mainline* commit, which is exactly where every method works.
3. **A `git log --grep=release` walk on the default branch is wrong often enough to avoid.** Release-prep commits for some versions live on release branches never merged back, so the walk skips them entirely and lands you one release late. One agent derived `2026.5.30` this way where containment gave `2026.5.28`.

Two traps sit inside method 1, and both have shipped a wrong version number:

- **The first containing tag can be a prerelease, and stripping the suffix invents a release.** A commit first contained by `v2026.5.30-beta.2` looks like it shipped in `2026.5.30` — but no stable tag with that prefix was ever published; the first suffix-free tag containing it was `v2026.6.1`. Match `^v\d+\.\d+\.\d+$` rather than filtering for `-beta`, or an `-alpha` tag walks straight through. Where a change shipped in a beta well before its stable release, name both: "in `v2026.5.30-beta.2`, stable from `v2026.6.1`". Look for an existing page that already does this and copy its form.
- **Check for a revert before dating anything.** One commit moved runtime state to SQLite; a later one reverted it; both are on the default branch. The effective landing is a third commit, months after the one a `-S` search surfaces first.

Two further traps:

- **The changelog does not go back far enough.** In one repository `CHANGELOG.md` began nine months after the docs did, and the release-notes directory three months before that. For anything older, the tag is the only citable record — and an agent that cannot find a changelog entry will quietly conclude the change never happened.
- **Not every claim should become a release number.** When the source of truth is date-keyed — a compatibility registry storing `deprecated:` and `removeAfter:` as dates — rewriting those notes as release numbers contradicts the source. One agent refuted two suggested fixes on exactly that ground, citing the registry constants. Check what unit the code uses before converting.

Where no record exists at all, restating the claim as a present-tense limit ("they are not placement-bound") is a legitimate fix. It is better than inventing a version, and better than leaving "not yet", which promises a future the repository has not committed to.

## The reference no checker can see

A split moves content. Any sentence that pointed at that content by direction — "described below", "the table above", "at the top of this page" — is now wrong, and **nothing in a normal docs toolchain detects it**. It contains no link, so the link audit sees nothing. It is well-formed prose, so the formatter and the markdown linter see nothing. It reads correctly to a reviewer skimming for structure.

In one program this class shipped three times, each found by a reader and never by tooling, including once on a page that had passed a full gate run and a bot review.

1. **Grep for directional phrasing after every split, and again after every rebase.** A rebase that re-extracts sections from the default branch restores the pre-split wording, so a repair you already made comes back undone. The link half of that revert is caught by the anchor audit; the prose half is not.
2. **Check each hit by finding its target, not by reading the sentence.** The sentence will look fine. Confirm the thing it refers to is on the same page.
3. **Tune the pattern for recall, not precision.** A first attempt matching a fixed noun list ("the section below", "the table above") missed three real orphans on one page, because the noun was "contract", "policy" and "drain". Match any short noun phrase ending in the directional word instead. That roughly triples the candidate count, which is the right trade: a missed orphan ships silently, a false positive costs seconds.
4. **Do not try to gate on this.** Tree-wide the pattern is far too noisy — one repository reported 184 candidates across its docs, nearly all legitimate ("patch `33` or above", "values above the limit"). Scoped to the pages a split touched it reported 8, of which one was a real defect. Precision comes from scope, not from a cleverer regex.
5. Numeric and comparative uses ("at or above", "below the threshold") are not cross-references. Exclude them or you will train yourself to ignore the output.

A worked example: a testing guide's last line read "prefer narrowing live tests via the allowlist env vars described below". The page ended on the next line; the env vars had moved to a sibling page during the split. Every validator passed.

## "Must not be split" has a middle case

A contract test that reads a page as a single file and asserts literal strings against it is a real constraint, but "refuse" and "proceed" are not the only options. Two shapes behave differently:

- A **whole-document set assertion** — every token matching a pattern anywhere in the file must equal some catalog — cannot be satisfied by any partial split. Refuse it.
- A **section-scoped assertion** — `toContain` on strings from named sections, or a slice taken between two headings — is satisfiable. Keep exactly the pinned sections on the index, at their original level and order, split everything else, and leave the test file untouched.
- A **forward per-reference check over a hard-coded file list** is the dangerous one, because it neither fails nor blocks. It validates every reference it *finds* without asserting how many exist, so a split silently shrinks its reach to whatever stayed on the index — one page went from 25 references guarded to 2, with CI green throughout. Extend the file list to the children (it is a path allowlist, the same species as a labeler glob) and report the coverage count before and after.

The middle case and the third case have opposite tells, which is why the reason matters more than the rule: for the section-scoped pin, a red test is the signal you cut wrong; for the forward check, **a green test is the signal you cut wrong**.

One agent found the second shape where its brief predicted the first, took the partial split, left the pinned test unmodified and green, said so in both the commit message and the PR body, and offered the revert. That is better than either refusing on a technicality or editing the test to fit.

The judgment to encode: a rule of the form "if X, refuse" should name the *reason* X matters, so an agent meeting a weaker version of X can recognise it. Here the reason is that the assertion's scope must survive the split — not that tests are untouchable.

## Some pages must not be split

A size trigger is a signal, not an order. Before splitting, check whether anything treats the page as a single artefact — and be willing to come back with "this one stays whole".

The clearest case: a contract test that reads the file and asserts a set of names appears in it. One repository had a guardrail reading a single SDK reference page and requiring every plugin-owned entrypoint to appear there as a literal string. All of them sat inside the tables a split would move, so any split emptied the set and failed the test. Splitting unevenly did not rescue it either — only 17% of the body was movable without touching pinned rows, the parent stayed over the threshold anyway, and the cut line would have been "which rows a test pins" rather than any reader job.

1. **Prove the blocker, do not infer it.** Simulate the split, run the test, then restore the file and verify the restore by hash. A code reading argues; a failing test and a byte-identical revert settle it.
2. **Say what the split would cost, in numbers.** Movable bytes, which sections get severed from the prose explaining them, what the parent still weighs afterwards. That turns "I decided not to" into a reviewable position.
3. **Name the change that would unblock it, and who owns it.** Here it was widening the guardrail from one file to a directory — a contract change belonging to the SDK maintainers, not a side effect of a documentation reshuffle.
4. **Record the affected findings as refuted, with the evidence.** Several ledger entries proposed exactly the restructure the guardrail forbids; leaving them open invites the next agent to retry it.

The related judgement is a child that lands slightly over the threshold. Leaving one at 24 KB was right when the only cut that fit would have separated a table from the sentence referring to it. Prefer a page a little too long over a cross-reference pointing at nothing.

## A path is not a fragment

When a page is split, the deep links people already hold are `/page#anchor`. Preserving them is the split's hardest requirement and the easiest to get wrong.

1. **A server-side pathname rule cannot choose a child by the incoming fragment.** The fragment is not sent in the HTTP request. A redirect destination can contain a fragment, and a destination without one inherits the original fragment ([RFC 9110, section 10.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.2)). But one parent path cannot use those rules to route different anchors to different children. `/page/anchor` and `/page#anchor` remain different addresses. Read the redirect resolver before designing the strategy.
2. **The fix is to keep the anchors on the parent.** Turn the parent into an index that carries an authored `<a id="...">` stub for every section anchor the children now expose, each linking to the child that holds the content. The old fragment resolves, and the reader lands one click from the text.
3. **Compute every id with the repository's own publishing parser, never a hand-rolled slug.** Parsers percent-encode punctuation and de-duplicate collisions in ways a naive slugifier does not. A slug that is wrong by one character produces a link that silently goes nowhere.
4. **Do not stub an id the parent already exposes.** That raises a duplicate-ID error at build time.
5. **The link checker cannot see this defect.** A split rewrites the repository's own links, so the checker reports clean while every external link and bookmark is broken. Prove preservation directly: enumerate the pre-split anchor ids, parse the post-split parent, and assert each one resolves. A passing link audit is not evidence.

This class of defect is invisible to every automated gate and to most human review, because the only broken links live outside the repository. Assume it is present until an explicit assertion says otherwise.

## Three agents measured the same suite and got three different numbers

Asked whether a failure set was pre-existing, one program produced: 76 failures, then 187, then 72 — same command, same branch, same default-branch commit. The spread was entirely the *clone*, and it took a deliberate measurement to find that out:

- The clone was a **sparse checkout** missing eight top-level directories, so every test reading them died with `ENOENT` — 21 files' worth.
- Its `node_modules` was **four days behind the lockfile**: 17 exact-pinned mismatches and one package missing outright, which is what produced the "cannot find package" and missing-export errors several agents had been reporting as pre-existing.
- And the recipe for sharing dependencies into a worktree — symlink `node_modules` — has a hole: a workspace package symlinked as `node_modules/@scope/pkg -> ../../packages/pkg` resolves through the **real** path, so the worktree compiles the *base clone's* source at whatever commit that is, not its own.

On a correct checkout the honest number was 72, of which 11 were timeouts caused by over-scoping the run and 61 were host-environment failures (`python` vs `python3`, no `corepack`, BSD vs GNU userland, `/var` vs `/private/var`) in tests that CI only ever runs on Linux — via explicit per-shard file lists, never the invocation being measured. So the true answer to "is the default branch red?" was: the question was about a command nobody runs, in a clone that could not answer it.

The rule this yields: **before attributing a failure to a change, establish that the environment can produce a trustworthy answer.** Check the checkout is complete, the dependencies match the lockfile, and the invocation is one CI actually makes. A number measured in a broken environment is not a weak signal — it is a different measurement wearing the same units, and three of them will disagree.

## A shallow clone makes every history question return a confident wrong answer

For most of one program's life its working clone was shallow — roughly 550 commits, all from the preceding two days. Nothing announced this. `git log -S'<string>'` returned no commits; `git log --follow` on a file returned four; `--diff-filter=A` found nothing. Each looks exactly like the truthful answer "this never happened", and agent after agent reached it independently and reported it as fact: the introducing commit is unreachable, the release cannot be named, the history is squashed. About twenty findings were deferred as unanswerable on that basis, and several correct-looking write-ups rest on it.

One agent finally treated the impossibility as suspicious rather than informative, checked, and ran `git fetch --unshallow`: 550 commits became 90,948, reaching back ten months.

The general rule is about a *class* of tool answer. A search that returns nothing is evidence only if the search could have found something, and depth limits, sparse checkouts, path filters and truncated output all degrade a search silently into a smaller one. When several careful people independently hit the same wall, suspect the terrain rather than concluding it is the edge of the map — and verify the corpus before trusting a negative result about it. `git rev-list --count HEAD` and the presence of `.git/shallow` cost nothing to check.

## Your own checker is the thing most likely to be wrong

A program like this accretes small scripts: find the tests that pin a page, find cross-references a split will orphan. They are worth writing. They are also, in practice, the least reliable artefact in the loop, because nothing checks them.

In one program a pin finder had **ten** separate blind spots and an orphan checker three. Every one was found by an agent or a reviewer *using* the tool on real work, never by its author. The pattern is consistent enough to plan around.

The ten, as a checklist of what such a script tends to miss:

1. Trees excluded from the search roots (`qa/`, `extensions/`).
2. Route-form references with no file extension — `"reference/test"`.
3. Paths composed at runtime — `path.join(DOCS_ROOT, "plugins", "x.md")`.
4. Rooted routes — a pattern requiring a leading letter never matches `/plugins/hooks`.
5. Full URLs in comments — `https://docs.example.com/plugins/x#anchor`.
6. Trees hidden by a sparse checkout, invisible on disk though present in git.
7. Reading only `argv[1]`, so a multi-page call reports one page and silently drops the rest.
8. Looking only for *tests*. CI also pins paths in plain allowlists — a release-metadata lane failed because a constant naming the old single page did not name its new children, and no test mentioned the page at all. Search the build scripts for the path, not just the test tree.
9. A regex escape that silently changes meaning between dialects. One scanner built a pattern as a Python string containing `\x27` — correct in a Python regex — and passed it to `grep -E`, whose ERE has no `\xNN` escape and read it as the four literal characters `\`, `x`, `2`, `7` inside a negated class. The effect: every docs path containing an **x**, a **2** or a **7** was invisible. `docs/channels/matrix.md` matched nothing; one page found 1 of its 6 pins and looked clean. Nothing failed; the count was simply wrong, quietly, for weeks.
10. Calling every hit a "test" when the hits are a changelog line, a URL constant and a YAML list. The label is part of the tool: an over-strong word invites over-caution, and an agent that trusts it may refuse a safe split. Report what a hit *is*, and have the agent classify each one by reading it.

That last one deserves emphasis beyond its place in a list: **a tool whose only failure mode is returning too few results will never tell you it is broken.** Every other bug on this list announces itself eventually — a crash, a nonsense path, a count that jumps. A silently narrowed search returns a confident, plausible, wrong answer forever. Test such a script against a case whose answer you already know by hand, and re-test it whenever you touch the pattern.

Three rules follow:

- **Brief agents to treat a zero result as unproven** and to grep independently. Say which misses have already happened. This costs a paragraph and has caught real breakages every time.
- **Ask for the tool's output *and* the agent's own search** in the report, as separate items. When they disagree you learn something; when you only ask for one, you learn nothing.
- **Fix the tool the same day, and verify the fix against the specific case that exposed it** — the count should move, and you should say which hit is new. A fix you cannot demonstrate is a guess.

The companion orphan-reference checker has now had four blind spots, and the fourth is the most instructive: a **length cap**. Its "see … below" pattern allowed 40 characters between the verb and the direction, which is plenty for `see the table below` and far too little for `see "Is all data used with OpenClaw saved locally?" below` — a quoted section title. The script reported the page clean; a reviewer found the reference. An arbitrary numeric bound inside a pattern is a silent recall limit, and unlike a missing pattern it looks like the tool is working.

Tune such a tool for recall and accept the false positives, then get precision by scoping the run to the pages a change actually touches. A directional-reference scan over a whole docs tree returned about 500 candidates; the same scan over one split's files returned six, of which one was a real defect.

## Read the verdict marker, not the last sha

An automated reviewer that keeps its verdict in one durable comment, edited in place, will also append progress markers to that same comment. When a re-review starts, a `review-status:started … sha=<new head>` marker is written while the three verdict markers still carry the **old** sha.

A checker that takes "the last `sha=` anywhere in the bot's comments" therefore prints *the new head* next to *the old verdict* and calls it current. The output is byte-identical to the output it produces when the review has genuinely finished. One agent hit this and caught it only by reading the raw markers: half an hour earlier the same line had asserted "current" for a verdict that was still `blocked`.

Extract the sha from the verdict marker itself — the one that carries the state you are about to act on — and treat any in-flight re-review marker whose sha differs as a separate, loud warning. Two states that a merge decision distinguishes must never render the same.

This is the same failure as the rate-limit-versus-absent one that motivated the script in the first place, in a new guise. The general rule: **a status tool must be unable to express one verdict for two different situations.**

The rule generalises past your own scripts, to the repo's checkers. A link audit reported 39 "route/file not found" errors against routes mirrored from a second repository that CI checks out and a local worktree does not. The links were correct; the checker simply could not see their target and said *missing* when it meant *unverified*. That cost real attention — three separate agents reported the count as pre-existing drift, and one nearly repointed valid links. The fix belonged in the checker: resolve what can be resolved without the dependency, report the rest as explicitly unverified, and print whether the dependency was present so reduced coverage is visible rather than silent.

When a validator's output surprises you, suspect the validator before the content — especially when it disagrees with a second mode of itself, as this one did with its own non-anchor mode.

**Expect to fix this bug more than once.** In one session the same verdict reader was wrong four times, in four different ways, all the same shape: it took the last `sha=` anywhere rather than the verdict marker's; it matched one spelling of the queued-re-review marker (`…-command:`) but not the other (`…-command-status:`); it reported a pre-review refusal as "in progress", a state that never terminates; and then, once taught that refusal, it kept reporting it after a rebase had queued a fresh review, because the refusal text lives in a durable comment that is never deleted.

Each fix was correct and each left the next instance intact, because every new state was added by asking "what does this marker say?" instead of "which head does this describe?". The durable fix is structural: make head-freshness a property of the *reader*, applied uniformly to every state it can report, so a new state cannot be added without dating it. Any state that outlives the commit it describes will eventually be read as current.

## Ownership is not implied by subject

A page about security, sandboxing or secrets is not necessarily owned by the security team. CODEOWNERS files commonly name pages one at a time, so a directory can have four owned siblings and one page nobody matches. A brief that says "this is almost certainly owned" primes an agent to find ownership that is not there.

There is a sharper version of this that a docs split creates rather than reveals. Ownership rules are often **file-exact** — `/docs/area/page.md`, not `/docs/area/`. Split that page into `docs/area/page/` and the children match no rule at all: the content is now unowned, and the review gate that covered it is gone. Nothing fails, no validator objects, and the PR looks like pure reorganisation.

That is a governance regression, and the fix belongs in the same PR that causes it: add a directory rule for the new children beside the existing file-exact one, and say in the PR body that you did and why. The opposite error is just as real — a child whose name merely *sounds* covered (`…/cloud-workers/security-model.md` against a `/docs/gateway/security/` rule) is not covered, because that rule is anchored at its own directory.

So: simulate last-match-wins over the actual file, with working controls — paths you *know* resolve to the team, and one you know resolves to a different rule. Assert the controls before believing the result. Then, if the page is unowned where its siblings are owned, **report the gap and change nothing**. Extending ownership is the owning team's decision; quietly acquiring it as a side effect of a docs split is how a review gate disappears.

A labeler config with file-exact globs needs a sharper distinction, and getting it wrong costs a review round. If **no glob names the page at all**, it was never labelled: that is a pre-existing gap, report it and leave it. But if a glob names the page and your split creates a directory the glob cannot match, **the change broke it and the fix belongs in the same PR** — one line, gated by the repo's own labeler tests, with sibling entries already carrying both forms as precedent. A blanket "CI changes go in their own PR" rule reads as principled and is wrong here; an automated reviewer blocked on exactly this, and the rebuttal deserved to lose.

## Measure the thing the rubric is a proxy for

A size threshold stands in for "this page has too many jobs in it". Raw byte count is a poor proxy, and one specific distortion dominates: markdown table alignment padding, which a formatter *requires*, and which is pure whitespace. Across one program's remaining oversized pages the inflation ran 34%, 36% and **46%** — three of them were already under the threshold once padding was removed, and the worst offender was less than half its apparent size.

A page whose bulk is one wide table is not a page with too many reader jobs. It is one lookup table, and splitting a lookup table is the thing the rubric exists to prevent.

The agent that found this did the comparison that settles it: measured de-padded, that index was 14% larger in words than its biggest child, against the 68% that raw characters suggested — i.e. exactly where an index carrying a shared spine belongs. It declined the split.

Generalise it: when a rubric fires, check whether the metric is measuring the property the rubric cares about, or an artefact sitting on top of it. Whitespace a formatter inserts, generated blocks, license headers, embedded data — all inflate a size signal without adding anything a reader has to navigate.

## A size rubric is not a rule

A threshold like "no child over 20k" is a heuristic for when a page has stopped being readable. It is not a constraint to satisfy by cutting.

If a child lands slightly over and the alternative is halving a lookup table or splitting an ordered rule chain, keep it whole and say why — especially on a page whose sentences state precedence or strictness *in order*, where restructuring can silently reorder semantics. Cite a page from the same program that already shipped larger as precedent. Extract only genuinely distinct jobs.

The rubric exists to serve the reader. A 21k page that answers one question beats two 11k pages that each answer half of it.

## The compactor can hide the deciding line

Long tool output gets truncated, and the elision is not random with respect to what you need: the parts that get dropped are the dense, repetitive blocks — a CODEOWNERS section, a reviewer's findings body — which is exactly where a blocking fact lives.

In one round the same agent lost 61 lines of CODEOWNERS and then 164 lines of review findings, on the two reads its entire task turned on. Both were recovered by routing the command's output to a scratch file and reading the slice.

Prefer scoped stdout, pipes, or targeted reads when output may be long. If truncation hides deciding evidence, read the missing region. Create scratch only for a concrete debugging or audit need, state its purpose, and reuse one task-owned location. Do not save routine reads by habit.

## Name the repository in every brief, because a plausible wrong one exists

An agent was asked to rebase and push a branch that was already built. It reported back that the branch, the commit, the source file, three of the toolkit's scripts and the prerequisite PR all did not exist — with evidence for each. Every claim was true of the trees it looked in, and every one was false of the tree the work lived in.

The brief had omitted the clone path. It was the one brief in the series that did, and the environment offered two confident-looking wrong answers: the session's primary working directory was a different repository entirely, and a stale partial clone of the right project sat in the additional working directories, parked at a detached HEAD with an older copy of the same toolkit. Searching either produces a coherent story in which the task is impossible.

The agent behaved correctly — it stopped and reported instead of inventing work. The failure was upstream, and it is cheap to prevent: **state the absolute path in every brief, every time**, even when the previous nine said it. Context that "everyone knows" is exactly what a fresh agent does not have, and a near-miss repository is worse than no repository, because it answers.

If a stale clone must exist, make it obviously stale — or say in the brief what it is and that it is not the target.

## Rounds: brief once, in a file

Running many agents in parallel makes the brief the dominant token cost, and copying a 4,000-word procedure into each prompt is both expensive and a source of drift — the copies diverge, and a lesson learned in round 3 reaches only the agents launched after it.

Keep one brief in the repo (`.audit/split-brief.md`) holding everything invariant: the anchor rules, the losslessness proofs, which validators to run and which are false greens, how to resolve the shared-file conflicts, how to read the verdict. Each agent's prompt then carries only what is genuinely per-page — the path, the slug, the sibling to match, the specific pin to be careful of, the ledger filter — and a pointer to the brief plus this document.

Two properties make it work:

- **Every lesson lands in the file, once.** The next round inherits it without you remembering to paste it.
- **Your own constraints are premises too.** One brief said "this PR must not touch the translation glossary" — correct for a split, and impossible for a back-link PR, because the repo's own checker requires every newly introduced link label to exist as a glossary source first. The agent honored the constraint and dropped ten verified fixes rather than break it quietly, which was the right call and cost a whole round. When you forbid touching a file, say what the constraint is *for*, so an agent that finds the exception can recognise it as one.
- **Ask every agent for "premises in the brief that did not hold."** This is the highest-yield line in the whole prompt. It has produced, among others: a page that was not owned after the brief said it likely was; a checker that reports non-tests as tests; a size threshold contradicted by the program's own precedent; and the verdict-sha bug above. Agents will not volunteer a contradiction of their instructions unless you ask for one — and the instruction being wrong is common enough to plan for.

## The stash is a shared global, and it eats work

Git's stash stack belongs to the repository, not the worktree. A dozen agents working in a dozen worktrees share one stack. The failure is quiet and specific: `git stash push` on an already-clean tree creates **no entry**, so the `git stash pop` that follows consumes whatever was on top — another agent's work — and drops it.

This happened twice in one program, to two different agents, both while doing something entirely reasonable: setting changes aside to measure a baseline. Both recoveries worked only because the victim's entry could be re-stashed under a labelled name and handed back.

The rule is not "stash carefully". It is **never stash in a shared clone**. Set work aside with a temporary commit, which is per-branch and cannot be taken by anyone else. Measure baselines in a detached worktree at the merge-base rather than by moving your own changes out of the way. And if a tool's contract is "push then pop", check that the push actually created an entry before popping — the pairing is not guaranteed.

The general shape is worth naming, because it recurs wherever agents share infrastructure: **a per-repository resource used as if it were per-workspace**. The scratchpad directory in the same program had the identical defect, with the identical symptom — files silently replaced by a sibling's, results computed against someone else's data.

## Parallelism is bought with rebases

Running a dozen content PRs at once against the same tree does not give you a dozen merges. Every split touches the same two shared files — a navigation manifest and a translation glossary — so each merge invalidates the rest, and each rebase invalidates the automated reviewer's verdict. Two PRs finished, ready, verdict-current, thirty seconds apart: the first merged and the second came back `CONFLICTING`.

That is the cost, and it is worth paying — but pay it deliberately:

- **Automate the resolution you will do fifty times.** The glossary conflict has exactly one correct resolution: the union. Write a script that reads the three merge *stages* (`git show :1:`, `:2:`, `:3:`) rather than trusting ours/theirs labels, which git swaps during a rebase, and have it refuse to write if any source would be lost. Make it stop for anything else — taking a side on the nav manifest silently deletes the other branch's work.
- **Place additions where they belong, not at the end of the file.** Most of this conflict is self-inflicted. A shared list file that every PR appends to collides on one line every single time; the same file merges cleanly when each change lands in a different region. Insert a new entry beside the existing entry it relates to — next to its parent page's term, in its own section — and concurrent PRs stop fighting. This one habit removed the majority of a program's rebases; the navigation manifest, whose entries are naturally grouped by section, auto-merged throughout while the flat append-only glossary conflicted on every rebase.
- **Preserve file order, not just content.** Resolving the glossary by sorting it produced a correct union with a 3,000-line diff, burying the six real additions. Keep the incumbent order and append; the diff should be the additions and nothing else.
- **Tell agents to expect two or three rebases**, so a conflict reads as routine rather than as a signal something went wrong.
- **Do not chain the merges by hand one at a time** if the platform offers a merge queue. Where it does not, merge the ready ones in a batch and rebase the losers immediately, rather than letting each discover the conflict on its own schedule.

## If you commit to an agent's branch, tell it

An orchestrator that fixes something on a running agent's branch — even a one-line fix the agent was blocked on — creates a commit the agent did not write and cannot explain. One agent found exactly that, checked its reflog, confirmed the four sibling branches had nothing similar, and reported it as an unexplained third-party push onto its branch that had also flipped its reviewer verdict from *blocked* to *ready*. It declined to revert or to claim the verdict, which is precisely right.

The report was correct and the surprise was avoidable. Either send the agent a message when you touch its branch, or leave the fix to it. An agent that cannot account for its own head sha will either absorb someone else's change silently — the dangerous outcome — or spend a round investigating.

## A moved secret-shaped placeholder is still an addition

Content-preserving splits hit a review gate that content changes rarely do: a diff-based input-safety scanner sees a section that moved to a new file as *added lines*. If those lines include credential-shaped documentation placeholders — `<PROVIDER_API_KEY>` inside a connection URL, a `user:pass@host` Basic-auth example — the reviewer can refuse the revision before reviewing it, producing no findings to answer.

Before treating it as a refusal, find out which failure it is. One reviewer emits the same user-facing sentence for a content refusal and for a **timeout while hydrating the diff** — distinguishable only by a reason code in the run log. An agent spent a round escalating a "refusal" that was a deadline, and one it had caused itself: editing the PR description while a review is in flight cancels that review and starts a fresh one, which then ran out of time. Make the push the last event, and read the log before believing the message.

For a genuine refusal, there is no fix inside the PR that keeps its central promise. Editing those lines breaks the byte-identity the split is built on. What works is evidence and escalation: cite the identical lines at their blob on the default branch, report the scanner's scope, thresholds, match count, and limits, and verify placeholder provenance without exposing candidate values. An entropy maximum cannot prove that no secret exists. State what the alternative shape would cost — keeping the affected section on the index leaves it as unchanged context, at the price of not splitting it.

Then escalate, because re-review is typically maintainer-only. Worth planning for: it is one of the few states an agent cannot clear on its own, and a program of splits will hit it on any page documenting third-party service setup.

## A link's description is a new claim

Adding a "Related" link looks like link work. It is not: the text beside the link asserts what the target is for, and that assertion is unverified unless you read the target. An agent adding ~100 Related entries wrote each gloss from the link text and its own sense of the page. A reviewer found eight wrong across four rounds; the agent then audited the rest against each target's own summary and found **nineteen more**.

Two of them inverted a security boundary — describing a prompt tool as a credential path when its own page says never to answer it with one, and implying a sandbox covered an execution path that the target page explicitly excludes. A reader who trusts the index and never opens the target is exactly the reader a Related section is for, so a wrong gloss is worse than no link.

The rule: **write each description from the target page's own opening lines, not from its title.** And when a reviewer finds one instance of a systematic error, audit the whole class before pushing again — the second-round sweep found more than twice what the reviewer had caught.

## A repo grep cannot see who links to you

Renaming a heading changes its anchor, which breaks every link to the old one. The natural check — grep the repo for inbound references, find none, proceed — is the wrong check, because the links that matter mostly live outside the repo: bookmarks, search results, other people's documentation, a chat message from last year. An agent ran exactly that check, renamed a heading, and was blocked by a reviewer citing the project's own rule to keep existing named anchors when reorganizing.

So treat a heading rename like a split: leave an authored stub for the old id. The cost is one line; the alternative is silent breakage you will never be told about.

The same blind spot has a second face. A link checker validates links *inside* the docs tree, so a URL to your own documentation written anywhere else — a script, a CLI error message, an issue template — is unchecked. One program found an automated support reply that had been closing issues with a link to an anchor that no longer existed, moved by an earlier split and renamed in the same stroke. Nothing failed; the reader just landed on a page that scrolled nowhere. Grep the non-docs trees for your own documentation domain before you believe an anchor is unreferenced.

## Some anchors were never anchors

A publishing pipeline can mint element ids that look stable and are not. One mints ids for component titles containing inline code by appending a **document-wide occurrence index** — the third such marker on the page becomes `…verbatim531end`, where the number counts markers earlier in that file. Move the component to a child page and it becomes `…verbatim17end`, because the count restarts. Edit anything above it and the number shifts again.

Two consequences, and the second is the one worth carrying:

- For the split itself: a stub that reuses the original id points at nothing. Stub the pre-split id on the index and target the child's *newly computed* id — which means computing both, with the real parser, on both sides.
- For the project: any inbound link using such an id was already fragile, and would have broken on an unrelated edit above it. The split did not create that; it revealed it. Report it as a defect in the id scheme rather than quietly routing around it.

The general habit: when a checker or generator produces identifiers, ask what they are a function of. An id derived from the heading text alone is stable under unrelated edits. An id derived from position, count, or file context is a moving target wearing the costume of a permalink.

## State anchor rules by what they protect, not by what they forbid

"Do not change headings" is the natural way to write the anchor constraint into a batch brief, and it is too broad. It protects *published anchors*, so the precise rule is: renaming, removing, or re-levelling a heading breaks an anchor and needs a stub; **appending a brand-new section to a page that has none breaks nothing** — it mints an id, it does not move one.

The over-broad form is expensive in a way that is easy to miss, because it fails silently and in your favour: three separate agents correctly refused actionable rows, reported the refusal, and moved on. Nothing looked wrong. The work simply did not happen, and the rows came back next round.

Watch for this shape in any constraint you hand an agent. A prohibition stated one level more general than its reason will be obeyed exactly, and the excess is invisible unless the agent is asked to report what the constraint stopped it from doing. Ask for that line.

## Component-to-heading conversions are not id-preserving

Restructuring often means promoting an `<Accordion>` or `<Tab>` title into a real heading. It looks like a pure structural move, and the component and the heading usually slugify to the same id — which is exactly what makes the exceptions expensive.

A pipe is the sharpest case found: a component titled `tasks retry | dismiss` publishes `tasks-retry-dismiss`, while the same text as a heading mints `tasks-retry-%7C-dismiss` plus a cleaned alias, and **loses the original id outright**. The two slugifiers disagree, so the old permalink resolves to nothing and no validator notices, because the new ids are all perfectly valid.

Treat every punctuated title as suspect and run the parser's own before/after id diff across the conversion. The same check catches a much cruder failure: one agent's edit silently ate an entire `##` heading during a splice, and the id diff was the only thing that saw it.

## The proof that passes for the wrong reason

A content-preserving split rests on one assertion: reassemble the children and you get the original bytes. It is a strong proof and it is worth the effort. It also has a blind spot that no amount of rigour inside it will close.

Authored anchor stubs — `<a id="section-name"></a>` on its own line — conventionally sit *above* the heading they name. A splitter cutting on heading boundaries takes everything up to the next `## ` and therefore sweeps such a stub into the section **above** it. The stub lands at the tail of the wrong child page. Every byte is still present exactly once, so the reassembly is byte-identical and the proof passes. The link checker is satisfied too: the anchor resolves, because it exists — just on a page that has nothing to do with it. A reader following that link lands in the wrong place, and nothing in the pipeline objects.

The general lesson: **a proof about the multiset of bytes cannot detect a defect in their attachment.** Byte-identity says nothing was lost or invented; it says nothing about whether each piece ended up where it belongs. Any transformation whose correctness includes *association* — an anchor to its heading, a caption to its figure, a footnote to its reference — needs a second check aimed squarely at the association, because the first one will pass either way.

Concretely: cut so that an anchor travels with the heading *below* it, then scan the result for stubs that are not immediately followed by a heading, ignoring the ones that legitimately anchor a component or a generated row. Check the changed pages and their authorized dependent surfaces. If the evidence suggests earlier rounds share the defect, record that follow-up; extend the scan only within the approved audit scope.

## Sometimes the split is blocked by the page's shape, and the ledger already says so

A page can be too large to leave and impossible to split, because a split cuts on headings and the page has none where it needs them. One 67k reference page kept **85% of its body under a single heading**, whose content was one component wrapping fifteen sub-blocks with no headings of their own. Every heading-boundary cut — including the flat-sibling fallback that avoids a nesting-depth problem — left a 57k child. Getting real children meant minting headings and wrappers, which is authored structure, not preserved content, and therefore not a split.

The agent stopped without writing anything, and found that the ledger had already recorded the answer: the row for that page prescribed *two* fixes — split the page, **and** give each family its own heading — of which only the first had been done. The prerequisite was sitting in the ledger marked verified-but-unfixed.

Two things worth carrying:

- **Check whether a blocked task's prerequisite is already written down.** A finding that names two changes is easy to half-close; the remaining half then looks like a fresh obstacle rather than a known task.
- **Sequence matters, and the wrong order manufactures dilemmas.** Doing the structural fix first makes the split trivial *and* keeps it inside the tree's existing depth. Doing the split first forces a choice between an unhelpful cut and a new precedent. When a task feels like it needs an exception, check whether a different order removes the need for one.

## Arguing with a secret scanner without feeding it

When an automated reviewer refuses a diff on a secret-scanning pre-check rather than reviewing it, the instinct is to prove there is no secret. Do that — but note what the scanner actually reads. On one pull request it reads the diff, the body, **and the comments**.

So the natural rebuttal is a trap. I wrote "no match for any of these patterns" and listed the literal vendor key prefixes I had grepped for. The next scan refused a revision whose entire diff was eight lines of ordinary prose. The evidence I posted became the finding.

The reviewer had already modelled the correct behaviour: its own block message says it reproduces no detected value, path, or scanner output. That line reads as boilerplate and is actually the rule.

How to argue the case without poisoning it:

- **Describe patterns, never spell them.** "The common vendor key prefixes, a PEM block header, an inline password assignment" carries the same information to a human and matches nothing.
- **Report entropy as a number.** Maximum bits per character over every candidate token in the diff, with the top few token *names* if they are ordinary identifiers. That is a measurement, not an assertion, and it is safe to publish.
- **Show that nothing was introduced**, when true: if every high-entropy token appears on both sides of the diff, the material is unchanged from the default branch and the finding is about content that already lives there.
- **Distinguish the two failure modes first.** A hydration timeout and a real refusal produce the same user-facing message and are told apart only by a reason code in the run log. A timeout clears on any fresh revision; a refusal does not, and the reviewer will not retry an unchanged one.

And when you do get a retry, spend it on a hypothesis. Splitting the suspect file out of the pull request localises the trigger; pushing the same content again tells you nothing.

## The check that refuses to be a judgement call

The best outcome for a contested finding is not a well-argued refutation — it is a machine that refuses it. In one round, a row asking to add a hidden channel page to the navigation was **rejected by a check job**: the channel's manifest set an exposure flag false, and the catalog check gates navigation membership in *both* directions, so the nav entry failed the build. Two earlier rounds had argued that row on judgement and left it open; the check settled it in seconds.

Two lessons. **Find out what each check actually asserts, not what its name suggests** — this one was documented internally as "regenerates a summary block", and its second, stricter assertion was discovered only by tripping it. And when a row can be settled mechanically, say so in the PR body: "machine-refuted, here is the failing check" ends a conversation that "I judged this out of scope" reopens every round.

## Small environment traps that cost whole runs

Worth writing into a brief verbatim, because each cost an agent real time and none is guessable:

- **A repo formatter script may take no path argument** and format the entire tree. In a worktree shared between agents that is destructive. Find the single-file invocation and publish it.
- **`git log -S` over a large unshallowed clone times out** unless scoped with `-- <path>`. Agents read the timeout as "no results" and conclude the change never happened.
- **Backticks inside a double-quoted shell argument are command-substituted.** A PR comment posted with `--body "…\`main\`…"` silently loses words — it does not error, it just publishes a sentence with a hole. Always write bodies to a file with a quoted heredoc and pass `--body-file`.

That last one is worth generalising: any content you compose in a shell string will be mangled by the shell in ways that look like your own writing errors. Route generated prose through a file.

## A quoted baseline rots; a measured one cannot

A brief that says "expect 3 known-failing checks" is trying to save each agent a measurement, and it buys a slow-acting bug instead. Those three got fixed. The brief kept saying three for weeks, three separate agents were primed with it, and one nearly reported a clean tree as regressed against a number that no longer existed. The brief even carried the warning "measure your own, this figure has been wrong twice" — and the figure was wrong a third time, because a number on the page outweighs a caution next to it.

Do not put the number in the brief. Put the procedure: **measure the baseline in your own worktree at the merge-base before you edit, and compare after.** Then a stale expectation is impossible rather than merely discouraged.

Two related traps in the same family:

- **Informational output is not an error.** One checker prints a line saying certain routes' fragments were not verified. An agent read it as a failure. If your tooling mixes notices into a failure stream, say so explicitly, because agents calibrate on shape rather than on exit codes.
- **Verify the checker itself when a fix depends on it.** One agent, before trusting that a new anchor resolved, temporarily broke it and confirmed the auditor reported it — then restored the file byte-for-byte. That negative control turns "the check passed" into "the check would have caught this", which is a different and much stronger claim.

## Salvaging an agent that stopped before it reported

An agent that dies mid-run leaves a worktree full of edits and no verdict table. The work is often good; what is missing is the attribution that makes it reviewable. Two failures to avoid: throwing it away, and landing it as though it had been reported.

What salvage actually requires:

1. **Verify the original worktree, HEAD, and ownership before salvaging edits.** Confirm the agent is inactive and which files it exclusively owned. One stopped agent had edited 213 files where its 61 rows named 47. Preserve that original tree and derive a scoped patch in a separate managed worktree: include verified cited pages and their split children, and retain unknown or sibling edits for their owners. An unexplained path is not permission to revert it.
2. **Re-derive the measurement yourself.** If the batch had a metric, compute the before from the default branch and the after from the tree. And check a control number alongside it: for a readability pass, word count moving 0.06% is what separates "split the sentences" from "deleted the caveats".
3. **Verify every factual claim the agent added.** A stopped agent's version numbers, in particular, have no evidence behind them. One had added two release citations to precisely the row an earlier triage had flagged as weakest, on a page carrying a standing hold that said not to guess versions. Both tags existed; neither claim could be reconstructed. Dropped that file and landed the rest.
4. **Say in the PR body that it is a salvage**, and that the id list is reconstructed from the diff rather than reported by the agent. A reviewer reading "these rows' pages are in this diff" will calibrate correctly; one reading "these rows are closed" will not.

The general point: a lost report is not a lost run, but the report was doing real work. Reconstruct what it would have asserted, verify the parts you cannot reconstruct, and drop what survives neither test.

## The shared brief is read once, at startup

A brief that accumulates lessons across a programme is the right artefact, and it has a concurrency bug: each agent reads it when it starts, so appending to it mid-round means siblings in the same batch are working from different instructions, and an agent may report a premise mismatch against a file it never saw change. One did exactly that.

Batch the edits between rounds. If you must write mid-round, stamp a revision line at the top and ask agents to quote it in their report — then a mismatch is legible instead of mysterious.

## Hand agents the ledger, not an extract of it

Partitioning a large finding set across agents invites you to generate a per-agent worklist — id, path, summary, suggested fix — because that is the tidy input. It also strips the three fields that decide how a row should be treated: the quoted evidence from the tree the finding was written against, the note recording what earlier rounds concluded, and the current status.

One agent working from such an extract nearly overturned a **standing hold** from a previous round ("naming a wrong version is worse than naming none") because the hold lived in a note field the extract dropped. The same extract showed eleven rows as open that the ledger had already closed.

Use the extract to *scope* a batch — it is the right shape for saying "these 189 are yours". Point the agent at the ledger to *judge* each row. And whatever a decision cost to reach, write it where the next agent will look, or you will pay for it again.

## Measure an unworked bucket before committing a round to it

When you find a large bucket of work nobody has touched, the instinct is to dispatch agents at it. Sample it first. One stratified 120-row sample across a 840-row bucket, classified against the current tree, cost a fraction of a fixing round and changed what every subsequent round did.

Classify each sampled row into: **gone** (the file no longer exists), **moved** (restructuring relocated the defect), **already-fixed** (name the commit), **class-refutable** (still present, but the remedy is one your programme refuses), and **live**. List the live ones individually — that list *is* the next round's brief.

What the numbers bought, concretely:

- **The residue hypothesis was wrong.** Gone + moved + already-fixed came to 16%. The bucket was not stale; it was **out of policy** — 55% class-refutable. That is a completely different remedy: a recorded bulk re-triage, not a fixing round.
- **The live rate varied 6% to 100% by category**, so a single "about a quarter is live" number would have been useless for planning. Fixing rounds went to the categories at 67–100%; bulk re-triage went to the ones at 6–17%.
- **Two small categories were worth censusing exactly** rather than estimating from three or four sampled rows. Both changed a decision: one was entirely decided already, the other was the highest-yield seam in the bucket.

Two things to insist on in the sampling brief. **Report the uncertainty honestly and per category** — the interval on the dominant category is what the total inherits, and a headline built on it is noise past the first digit. And **fix the yardstick centrally before the classifiers run**: six agents independently invented six different thresholds for "this page is too long", producing ten live calls that had to be overturned against the programme's actual rule. Any judgement your classifiers share must be stated as a number in the brief, not left to each of them.

## Count the whole backlog before you believe your burn-down

Seven rounds into one programme, the ledger read 372 open and looked nearly finished. It also held **840 rows in a status called `verified`** — meaning a second auditor had independently re-confirmed each finding was real — and not one of them carried a pull request number. They had never been worked. The real remainder was around 1,200, not 372, and every progress report until then had been measuring the wrong denominator.

Nothing was hidden. The status was in the schema from the start and its meaning was written down. The failure was that the working query filtered `status == "open"`, that query became the definition of "left to do", and no one re-derived the total from the whole file.

Two habits close this:

- **Enumerate every distinct status at the start of a programme and write next to each whether it means done or not done.** If any status is ambiguous, split it before you build on it. In this ledger `verified` had already absorbed a second meaning — "already correct when we arrived" — which had to be pulled out into its own status first.
- **Report progress as a partition of the total, never as movement in one bucket.** `fixed + refuted + satisfied + open + verified = 2899` on every report makes an untouched bucket impossible to overlook. A burn-down of `open` alone conceals one indefinitely.

There is a corollary about how you clear such a bucket. Rows already double-confirmed cannot be cleared the way fresh ones can — this programme dismissed roughly 80% of its open rows by class ("we do not add intro paragraphs"), but a row somebody re-verified deserves either a row-by-row argument or a deliberate, recorded decision to lift the holds. Measure the bucket first: sample it, classify against the current tree, and find out how much is live before committing a round to it.

## Reconciling a ledger against the PRs that closed it

After each round, the ledger has to absorb what the round's pull requests actually did. This is the step where a program quietly loses its grip on what is left, and three failures recur.

**A PR body's section heading is a claim, not a verdict.** Reconcile against the tree. In one round, five rows had a PR and the ledger asserting opposite outcomes, and one row was listed as fixed that had been *un*-fixed hours later by a different PR reverting exactly that line — with a package manifest flag making the absence machine-enforced. Section attribution alone would have closed it.

**The usual cause is a two-halved row.** A finding with an accuracy half and a structural half gets filed under whichever heading its author found more salient, so the same id appears as both Fixed and Refuted. A partial stays open — a wrongly-closed row loses work, a wrongly-open one costs a rediscovery.

**Trust the enumerated ids, never the header count**, and never pattern-match id-shaped strings out of prose: one reconciliation did that and swept ids from the *refuted* list into the fixed set. Parse by section, attribute each id to the section it sits under, and report any id appearing twice instead of picking one.

Two smaller rules that pay for themselves:

- **A refutation with no recorded evidence is not a refutation.** One row was closed with the bullet "see batch notes" — notes that were not in the PR. Reopen those. Evidence belongs in the PR body, not in a report that evaporates.
- **Do not overload a status.** "An auditor confirmed this finding is real" and "this was already correct on main when we got there" are opposite states; if both land in a status named `verified`, you will read done work as outstanding. Give the second its own name, and reserve `fixed` for rows where you can name the commit.

## A ledger holds decisions, not only findings

An audit ledger accumulates two different kinds of row, and they demand opposite responses. Most rows are *findings*: a hypothesis about a defect, to be verified and then fixed or refuted. But some rows are *decisions already taken* — "this page was deliberately left at 48k; revisit only if a child passes 60k", recorded when an earlier PR measured the tradeoff and chose.

Dispatching work by querying the ledger for a page will return both, and a brief that says "here are the findings for this page" quietly reframes a decision as a task. That is how a program re-opens a question it already settled: an agent is sent to split a page that a previous round explicitly held, does the work impeccably, and only discovers the HOLD while writing up.

Two habits prevent it:

- **Check for a standing decision on a target before assigning it**, not as part of the work. A row whose status is "verified" with a keep/hold note is a stop sign, not an input.
- **Give the agent authority to stop**, and expect it to. The one that found the hold escalated rather than manufacturing a green — and the automated reviewer, reasoning independently, reached the same recommendation. Two independent parties agreeing to defer is a strong signal; a program that cannot hear it will burn rounds re-litigating settled calls.

The corollary for structure: some content cannot be divided without breaking the guarantee that makes the division safe. An accordion group is one unit to the renderer; splitting it across files means inventing a wrapper, which ends byte-identity. When the largest indivisible unit is most of the page, there is no split worth having, and saying so is the deliverable.

## Generating the program

Write a script (`prs.py`) that reads the ledger and emits both a Markdown program and a JSON file. Keep it deterministic so it regenerates after every ledger change.

1. Assign each live finding to a family by rubric, kind, file prefix, and shard.
2. Claim structural findings first with hand-defined PRs (hygiene, nav, generators, i18n, funnel, templates).
3. Group the rest by family and directory, then chunk to the file and finding caps.
4. Sort by phase, then family, then key. Number the PRs.
5. Emit per PR: id, phase, family, title, files, finding ids, severity counts, dependencies, and the top findings with their fixes.

## Make the PR say which findings it closed, by id

A program's PRs will happily report "75 of 88 fixed" and then itemise only the ones they refused. The refusals are interesting, so they get written up; the successes feel self-evident, so they get a number. That number is unrecoverable afterwards: a reconciliation pass over 97 merged PRs found 77 citing finding ids and 678 distinct ids in play, yet the largest PRs' actual closures could not be reconstructed from their own bodies at all.

The cost lands later, on whoever asks "what is left?" — findings sit marked open, and a future round redoes work that shipped weeks ago. Six findings in one program were demonstrably fixed on the default branch with **no PR body claiming them**, found only by walking `git log --diff-filter=A` over the directories the fixes created.

So require the id list, and require it to be per-outcome: closed, refuted, deferred, partially done. Then reconcile from those lists rather than from prose.

Two ways the requirement gets met in form but not in substance. **A table of the pages you corrected is not an id list** — one PR's 22 claimed fixes had to be recorded as still-open because nothing tied them to rows, the single largest deliberate under-record in that program. And **a promised list can simply be absent**: another PR's body referred to "the table at the bottom" listing 70 already-satisfied findings, and no such table existed anywhere — body, comments, or commits. The reconciler recovered that set only by deriving it (the PR's scope was exactly 96 rows; minus its 26 named ids leaves 70) and recorded the derivation in each row.

Once agents do that, a third discrepancy surfaces: **the headline and the list disagree.** In one round a PR's "Findings closed (34)" heading sat over 26 named ids; another's "Missing reciprocal links (19)" sat over 21 bullets. The counts are written early and the lists edited later. Reconcile from the list, and treat a header count as a hint that something is missing rather than as a total.

The other half of the discipline is knowing what *not* to close. A finding that a PR fixed one half of stays open, with the progress recorded — closing it loses the remainder silently. In one reconciliation that rule kept 36 rows open that the PR bodies' own summaries would have closed, and the reconciler's closure count came out deliberately lower than every PR header.

And reconcile conservatively, because a PR body is adversarial terrain for pattern matching. Real examples from one pass:

- A table captioned **"Dropped, with the glossary source each would need"** listed eight ids. A regex over that body marks all eight fixed; they were removed from the PR and are correctly still open.
- Findings appear in bodies as context, as duplicates, as findings against *other* pages, and as the half of a two-clause fix that was explicitly declined.
- One id appeared in the same PR under both "Fixed" and "Refuted" — different halves of it, and the refutation was the correct reading.

**Under-recording is much cheaper than a wrong "fixed".** A missing record costs someone a re-check; a false one silently deletes work from the queue.

## Simulate CODEOWNERS; do not grep it

Deciding which files in a batch are owned looks like a grep problem and is not. A prefix match over the CODEOWNERS paths is wrong in **both** directions at once:

- **It over-matches.** Many entries are file-exact (`/docs/gateway/authentication.md`, not `/docs/gateway/authentication/`). Treated as a prefix, an owned parent drags in child pages that are genuinely unowned — and after a split program those children are numerous.
- **It under-matches.** A prefix list assembled by hand quietly omits entries. One such list missed two owned paths outright, yielding 31 rows where the real answer was 33.

Write a last-match-wins simulator — it is twenty lines — and run **positive and negative controls through it in the same pass**: assert that known-owned paths fire, and that specifically named unowned siblings do not. The negative controls are the half people skip and the half that catches over-matching. An agent that did this found both error directions before it edited anything.

Two follow-ons worth stating in the brief: a file-exact owned parent does not imply its split children are owned, and ownership is a property of the *current* path, so re-check it after any rebase that lands a sibling's split.

## The test that pins the docs may not run on docs changes

A repository with a fast path for documentation pull requests classifies a diff as docs-only and skips the test lanes. That is the right optimisation and it has one bad interaction: any test that *asserts on documentation content* now lives in a lane that documentation changes cannot select. The test that pins the navigation file cannot be failed by a change to the navigation file. Every break it is meant to catch lands on the default branch instead.

We hit this twice in a week on the same test, both times discovering it from a red default branch rather than a red PR. The test's own comment described the failure mode — and the comment was about a different assertion in the same file, so someone had already seen it happen and fixed only the instance in front of them.

Two habits:

- **Ask which lane owns each test that reads your files, and whether your change selects it.** If it does not, run that test locally before merging and say so in the PR. This is cheap and it is the only thing standing between you and a red default branch.
- **When you find the gap, report it separately rather than fixing it inside a repair PR.** Moving a test between CI jobs is a maintainer's call about cost, and burying it in a "fix main" PR makes both changes harder to review. Say precisely where the gap is, give the two options, and let them choose.

The general shape: **a check that guards a file must run in a lane that the file's own changes select.** Audit for that directly — do not assume a green PR means the guards ran.

## Localized navigation is derived, and it degrades silently

If translated docs get their structure from the default-language navigation and their labels from a hand-maintained overlay, then renaming or moving anything in the source navigation degrades every locale — quietly. The overlay is matched against the cloned English tree; an overlay entry that matches nothing is skipped, so the affected tabs and groups keep their **English labels** in a sidebar that is otherwise translated.

One tab rename shipped this with every documentation validator green. Link checkers see the pages, the pages are unchanged, and the overlay file is still valid JSON — nothing in the pipeline is looking at whether a label survived.

Treat the overlay as part of the navigation, not as translation memory: **any change to tab or group shape lands its mirror in the same pull request.** When reviewing one, compose the localized config and read the labels back; that is the only check that notices.

## Do not infer a blast radius from a failing assertion

Investigating that same break, I had a test telling me two group names were absent from the composed localized navigation, and I reported that 57 pages had been dropped from it. They had not. The overlay only assigns labels — the routes were all present, under English names. The assertion said *a name is missing*; I supplied *therefore the content is gone* without opening the function that builds the object, and it reached a pull request body before a reviewer corrected it.

The generalisation is uncomfortable but worth keeping: **a failing assertion tells you a predicate is false, not why, and never how much is affected.** The gap between those is where confident wrong claims live, and they are expensive precisely because the evidence is real — there *was* a genuine regression underneath, which is what made the overstatement plausible to me.

Before you write an impact claim into a PR body, an issue, or a brief, read the code that produces the value the assertion checked. It is usually one function, and it is the difference between "this rename drops 57 pages" and "this rename leaves two groups untranslated".


## A page can be generated without looking generated

"Don't hand-edit the generated tree" is the rule everyone writes, and it fails twice.

- **Generated pages are not all under a `reference/` directory.** One repository's plugin inventory page sat beside hand-written siblings; an agent edited it, broke the generator's check job, and correctly moved the fix into the generator.
- **A page can be *partly* generated, from *other* pages.** A channels index was hand-written except for a marked block that a script rebuilt from every channel page's `summary` frontmatter. Editing a channel page's summary silently invalidated a different file, gated by a check job nobody had connected to the edit.

The second one is the dangerous shape, because the file you edited is not the file that breaks. Two habits close it: grep the scripts directory for the basename of every page you touch **and** for pages that summarise it, and treat frontmatter as generator input rather than page metadata. Publish the known generator list in the brief and say explicitly that it is probably incomplete — that framing is what makes an agent check rather than trust it.

## Sub-agents that share one worktree

A phase agent with more rows than it can hold will partition them across children. If those children share the parent's worktree — the natural setup, since it is already prepared — then every child's `git diff` shows every sibling's edits, and none of them can tell which changes are their own.

This mostly works, and the reports come back clean, because a careful child notices the foreign paths and says so. The failure mode is the helpful one: a child that sees a sibling's half-finished edit and tidies it, or reverts it as damage.

- **Give every child an explicit file list**, and say that files outside it belong to a sibling.
- **Ask for `git diff --stat -- <its own files>`**, never a bare diffstat.
- **Ask it to name foreign paths it saw** rather than acting on them. That line is also how you detect two children assigned the same file.
- **Let only the parent commit.** Children that cannot run `git` write commands cannot interleave commits mid-edit.

Related merge evidence, which alone grants no worktree cleanup authority: **`git merge-base --is-ancestor <branch> <default>` cannot answer "has this branch merged?" in a squash-merge program.** It fails in both directions at once. It returns *true* for a fresh branch whose agent has not committed yet, because the tip still **is** the default branch — prune on that and you delete a live agent's tree. And it returns *false* for every branch that actually landed, because a squash merge writes a new commit and never makes the branch an ancestor of anything. Run it against a dozen worktrees and it will confidently invert the answer for all of them.

Read the exact repository and PR from the forge and verify the merged head, final target, and local HEAD. A branch-name lookup is discovery only. Cleanup also requires task sign-off, explicit owner release, no unfinished stack dependencies, and fresh holder, lock, dirty-state, and recovery checks. Use the repository's approved non-force removal path; retain the worktree if any proof is missing.

## Tracking

- When a PR lands, set its findings to `status: fixed` with the PR number, then regenerate the report and the program.
- Report progress as findings closed over findings live, per phase, not as PRs merged. A merged PR that closed three of its twelve findings is not done.
- Keep refuted findings visible. They are the audit's own error rate.
