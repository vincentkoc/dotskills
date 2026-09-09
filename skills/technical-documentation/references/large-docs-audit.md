# Large Docs-Tree Audit Playbook

Use this playbook when a docs tree is too large for one pass. Signals: hundreds of pages, pages over 20k characters, many locales, or a navigation config nobody fully understands.

It defines the round structure and the sharding rule. It also defines what every shard checks, how findings are recorded, and when the audit may stop.

Read `references/review.md` first. This file adds scale rules on top of it.

## 1. Stop conditions and honest convergence

The audit runs until it is finished, not until it is tired.

- Every page in scope is read in full by at least one auditor. Sampling is not coverage. If you sample, log exactly what was skipped and why.
- Coverage is reported as `pages read / pages in scope`, per directory. Anything under 100 percent is a gap, not a rounding error.
- Discovery uses loop-until-dry: keep running fresh finder rounds until two consecutive rounds surface nothing new.
- Convergence is a measurement, not a claim. Report the finding count each round added. If the last round still added findings, say so and state what a further round would cost. A measured miss rate beats a false "complete".
- A completeness critic runs last and asks: which directory was not read, which check was not run, which claim was not verified? Its answer becomes the next round of work.
- Long runs are expected. Do not truncate the deliverable to fit a message. Write the ledger to disk and summarize from it.

## 2. Round plan

Each round has a different job. Do not merge them.

| Round | Job | Cost profile |
|---|---|---|
| 0 | Mechanical scans and native validators. No agents. | Minutes of scripting |
| 1 | Full read of every reader-facing page, one agent per shard, plus inventory agents for nav, journeys, generated content, and i18n | Largest round |
| 2 | Targeted fresh lenses: pages round 1 scored all-pass, the largest pages, pages classified by sampling, hidden content, more reader journeys, locale parity | Roughly a quarter of round 1 |
| 3+ | Sampled convergence check on already-audited pages with new lenses, until two rounds add nothing | Small |

Verification runs inside each round, not as a separate phase, so a finding never sits unverified across a session boundary.

## 3. Round 0: mechanical scans before any agent runs

Never spend agent tokens on what a script decides deterministically. Run these first and feed the results into every later prompt.

1. Detect the framework config (`docs.json` or `mint.json` for Mintlify, `fern.config.json` and `docs.yml` for Fern, `conf.py` for Sphinx, `mkdocs.yml` for MkDocs). Nav is the map of what the reader can reach.
2. Enumerate pages with `git ls-files docs` rather than a filesystem walk. Record count, total bytes, and the size distribution.
3. Walk the nav config in a script and emit five lists:
   - nav ghosts: an entry with no file
   - nav orphans: a file with no entry
   - groups over 12 siblings
   - groups with one child
   - duplicate entries
4. Scan frontmatter titles for collisions, count headings and accordion or tab blocks per page, and list pages over 20k characters.
5. Run `scripts/ste-lint.py --summary --json` three times: default, `--mode flavored`, and `--max-words 20`. Store all three baselines.
6. **Run the repo's native validators. They are the authority for links, anchors, MDX, config samples, and spelling.** Find them in `package.json` and `scripts/docs-*`. Typical names: `docs:check-links`, `docs:check-mdx`, `docs:spellcheck`, `docs:check-config-examples`. Install dependencies if that is what it takes. An audit that files link findings a native checker disproves burns reviewer trust.
7. Record generated-content markers (`.generated/`, baseline hashes, "do not edit" headers) and the generator script for each. Never hand-edit generated pages. File the finding against the generator.
8. **Read the publish pipeline before judging the tree.** A docs directory is not always what ships. A sync script may inject pages from another repository, exclude internal files, drop a nav tab per locale, or rewrite routes. Find the publish or sync script and read its exclusion and injection rules. See section 13, lesson 1.

## 4. Sharding

- Shard by character budget, not page count. Target about 150k characters per shard, which one agent reads comfortably. Pages over 60k characters get their own shard.
- Sort each directory's pages largest first when filling shards so one giant page does not straggle behind twenty small ones.
- Set aside generated-content directories before sharding. Classify them with one sampling agent, then read the hand-written ones in full in round 2.
- Give each shard a stable id (`channels-01`). Write its file list to `.audit/shards/<id>.txt` and pass only the id to the agent. Inline file lists bloat workflow arguments and invalidate the resume cache when they change.
- Expect roughly one shard per 150k characters: a 10M-character reader-facing tree is about 90 shards.

## 5. Per-page reader-experience rubric

Score every page on each item as `pass`, `weak`, or `fail`, with a one-line reason. A `fail` on items 1 to 4 is a blocking finding.

1. Purpose in the first screen: the first paragraph says what the page is for and who it is for.
2. Funnel present: what/why, then quickstart or first task, then next steps. Reference pages may replace the funnel with a scannable index.
3. Diataxis purity: the page is one of tutorial, how-to, reference, explanation. Mixed pages are split candidates.
4. Task completion path: a reader can finish the page's job without leaving it for a prerequisite the page did not name.
5. Heading hierarchy: one H1, no skipped levels, headings are informative and scannable. More than 40 headings on one page is a split signal.
6. Wall-of-text density: paragraphs over 6 sentences, or sections over roughly 600 words with no list, table, or code block.
7. Table monsters: tables over 12 rows with prose cells, or tables that wrap to unreadable widths. Prefer a list with sub-headings or a reference sub-page.
8. Code block accuracy: commands are copy-ready, name the shell, and match the current CLI. Placeholders are marked as placeholders.
9. Critical facts trapped in images, callouts, accordions, or tabs with no text equivalent. Collapsed blocks hide prerequisites and defaults, so grep for `<Accordion` and `<Tab` and read what is inside.
10. Cross-links: every referenced page and anchor exists. Related pages link both directions.
11. Terminology: one term per concept across the page, matching the glossary if one exists. Use the round-0 STE baselines and flag pages over 1.5 hard violations per 100 words.
12. Staleness signals: version-locked wording with no version scope, dead product names, "coming soon" older than one release, TODO markers.
13. Duplicate coverage: the same procedure or concept appears on more than one page with drift between copies.
14. Reader-journey position: the nav puts the page where a reader on that journey would look for it.

## 6. Round 2 lenses

Round 1 misses things in predictable places. Target round 2 at them:

- Pages round 1 scored all-pass. A second lens on a clean page finds real defects, so an all-pass score is a lead, not a result.
- The largest pages. A 100k-character page with twelve findings was skimmed, not read. Re-run it with narrow lenses (hidden content, staleness, links, duplication, heading structure) one lens set at a time.
- Pages classified by sampling in round 1. Read the hand-written ones in full.
- Accordion-heavy and tab-heavy pages, for rubric 9 only.
- Reader journeys beyond the first-run path: configure, integrate, operate, extend, troubleshoot.
- Locale parity measured against the published site, not the source tree, when locale pages are generated at publish time.

## 7. Oversized page protocol

For every page over 20k characters:

1. Map its H2 sections with word counts and the Diataxis type of each section.
2. Propose a split: one page per coherent job, plus a short parent page that is an index with one line per child.
3. Preserve every anchor: list the old `page#anchor` targets and the new destinations, and add redirects in the framework config when it supports them.
4. Generate the inbound-link and linked-anchor table with a script, not an agent. Agent counts of "47 inbound files" drift. A script is exact.
5. If the page is a generated reference (config schema, CLI output), do not split by hand. Record it as a generator finding.

## 8. Navigation, i18n, and governance

- Compare the nav tree to the reader journeys the product has. Every journey needs a start page reachable in two clicks.
- Flag groups with more than 12 siblings, groups with one child, jargon group names, and ordering that is not overview-tasks-reference.
- For each locale, report nav parity, page parity, and freshness. When locale trees are publish-only, measure against the published sitemap.
- Glossary terms are STE "one word, one meaning" anchors. Diff the key sets across locale glossaries with a script.
- Audit `AGENTS.md`, `CLAUDE.md`, `docs_map.md`, and any contribution page inside the tree with `references/agent-and-contributing.md`. Check that the commands they name exist in `package.json`.

## 9. Finding ledger

Every finding is one JSON object, one per line, in `.audit/ledger.jsonl` (or the path the user names).

```json
{"id": "r1-0007", "shard": "channels-01", "file": "docs/channels/slack.md", "line": 412,
 "rubric": 6, "severity": "blocking|major|minor", "kind": "ux|ia|accuracy|ste|link|i18n|governance|generated|split",
 "summary": "Section 'Advanced routing' is 1,900 words of prose with no list or table.",
 "evidence": "H2 at line 380, next H2 at line 512, 0 lists, 0 tables.",
 "fix": "Split into 'Routing rules' (list) and 'Routing examples' (code).",
 "confidence": 0.9, "status": "open|verified|refuted|fixed|wontfix", "verified_by": [], "pr": null}
```

Rules:
- `summary` and `fix` are written in Strict STE. One sentence each where possible.
- `evidence` cites lines or counts. A finding without evidence is refuted by default.
- Severity: blocking blocks a reader from completing the page's job. Major costs the reader time or trust. Minor is polish.
- Dedupe by `file` plus `rubric` plus overlapping line range before verification.
- **Rebuild the ledger from the workflow journal. Never hand-edit it during a run.** The journal holds one result line per completed agent and survives session restarts.
- Keep the rendering scripts next to the ledger (`report.py`, `prs.py`) so every artifact regenerates from it after any status change.

## 10. Verification

Each finding with severity blocking or major gets an adversarial check by an agent that has not seen the finder's reasoning. Its job is to refute.

- **Batch verifiers per shard, not per finding.** One verifier handles a shard's forty findings for a fraction of the cost of forty verifiers. It reaches the same verdicts. Per-finding fan-out is what exhausts a session.
- A verifier reads only the cited line range plus about twenty lines of context with `sed -n`. It greps for cited headings and tests link targets on disk. It never reads a whole file.
- Run verifiers on a cheaper model at low effort. Verification is checking arithmetic, not judgment.
- Blocking findings get a second verifier with a different lens. Major findings get one.
- A verifier also refutes a finding the ledger already records, so rounds do not duplicate each other.
- Refuted findings stay in the ledger with `status: refuted` and the reason. Never delete a finding.

## 11. Remediation

- Apply fixes per file, one agent per file, in an isolated worktree when several agents edit in parallel.
- Group the work into PRs with `references/pr-program.md` before editing anything.
- Every remediation agent re-runs the native validators and `scripts/ste-lint.py` on the files it touched. Hard violations must not increase.
- Record `status: fixed` and the PR number. Never mark fixed without a diff.
- Brownfield rule applies: match existing conventions, preserve anchors, add redirects, and keep the smallest safe change set per file.

## 12. Deliverables

1. Coverage table: pages in scope, pages read, percent, per directory.
2. Blocking findings with file and required fix.
3. Split plan for every oversized page, with script-generated inbound and anchor tables.
4. Nav and IA change list.
5. STE lint summary per directory, in all three modes.
6. i18n parity table.
7. Native validator results, named and quoted.
8. Ledger path and counts by status.
9. Round-by-round finding counts, so convergence is visible.
10. Residual risk: what was not verified and why.
11. The PR program (`references/pr-program.md`).

## 13. Lessons that change verdicts

1. **Check external content sources before calling a link dead.** In one audit, twelve nav entries and thirteen inbound links looked like 404s. A publish-time sync mirrored those pages in from a second repository, so every published link resolved. The real defect was one governance note, not a blocking outage. Clone the source repo and read the sync script. Then run the native link audit with the external source supplied.
2. **Native validators outrank agent scans.** An approximate heading slugger reports anchors the real publishing parser resolves. Run the repo's checker and file only what it proves.
3. **A page that scores all-pass has not been proven clean.** Round 2 found real defects on every batch of all-pass pages.
4. **A giant page needs one pass per lens.** One agent asked for fourteen rubric items on a 100k-character page returns a skim.
5. **Word and inbound-link counts from agents drift.** Recompute anything numeric with a script before publishing it.
6. **Set aside generated content early. Then come back for the hand-written parts.** Some pages inside a generated directory carry manual blocks and deserve a full read.

## 14. Worked profile: OpenClaw docs (completed audit, September 2026)

Calibration numbers from a full run. Re-survey before relying on them.

- Framework: Mintlify, `docs/docs.json`, 592 nav entries, 279 redirects. Locale nav is mirrored under `docs/.i18n/*-navigation.json` with 20 glossaries. Locale pages are generated at publish time and are not in the repo.
- Scale: 749 pages, 15.2M characters. 575 reader-facing pages (10.7M chars) and 174 generated-candidate pages (4.5M chars). 171 pages over 20k characters. The largest generated page was 2.1M characters.
- Sharding: 91 reader shards at 150k characters each, plus 4 inventory agents.
- Cost: about 20M subagent tokens across three resumed audit runs and one round-2 run, roughly 470 agents. Session usage limits interrupted the work three times at 6 to 8M subagent tokens per window. Each resume replayed completed agents from cache.
- Yield: 2,873 findings, 2,810 live after refutation (47 blocking, 952 major, 1,811 minor). 972 were adversarially verified. Round 2 still added 271 live findings, so convergence was reported as not reached.
- Native validators: MDX passed on 753 files. The link audit passed on 8,076 links once the external ClawHub repository was supplied. The anchor audit found 2 broken fragments and spellcheck found 6 typos.
- Remediation: 303 PRs in six phases, generated from the ledger by `prs.py`.
