# Large Docs-Tree Audit Playbook

Use this playbook when a docs tree is too large for one pass. Signals: hundreds of pages, pages over 20k characters, many locales, or a navigation config nobody fully understands. It defines how to shard the work, what every shard must check, how findings are recorded, and when the audit is allowed to stop.

Read `references/review.md` first. This file adds scale rules on top of it.

## 1. Stop conditions (read this first)

The audit runs until it is finished, not until it is tired.

- Every page in scope is read in full by at least one auditor. Sampling is not coverage. If you sample, log exactly what was skipped and why.
- Coverage is reported as `pages read / pages in scope`, per directory. Anything under 100 percent is a gap, not a rounding error.
- Discovery uses loop-until-dry: keep running fresh finder passes until two consecutive passes surface nothing new.
- A completeness critic runs last and asks: which directory was not read, which check was not run, which claim was not verified? Its answer becomes the next round of work.
- Long runs are expected. Do not truncate the deliverable to fit a message. Write the ledger to disk and summarize from it.

## 2. Inventory and sharding

1. Detect the framework config first (`docs.json` or `mint.json` for Mintlify, `fern.config.json` and `docs.yml` for Fern, `conf.py` for Sphinx, `mkdocs.yml` for MkDocs). Nav is the map of what the reader can reach.
2. Enumerate pages with `git ls-files docs` (fast on huge trees) rather than a filesystem walk. Record count, total bytes, and the size distribution.
3. Build three lists:
   - Oversized pages: over 20k characters. Each is a split candidate and gets its own auditor.
   - Nav orphans: pages on disk that no nav entry references. Either link them or delete them.
   - Nav ghosts: nav entries whose file does not exist. Fix the route or the file.
4. Shard by directory, then by size. Target 15 to 25 normal pages per shard, or one oversized page per shard. Give each shard a stable id (`channels-01`) so results can be resumed and merged.
5. Discover native validators before auditing: `package.json` scripts such as `docs:check-links`, `docs:check-mdx`, `docs:spellcheck`, plus any `scripts/docs-*` files. Run them once for a baseline and again after remediation.
6. Record generated-content markers (`.generated/`, baseline hashes, "do not edit" headers). Never hand-edit generated pages. File the finding against the generator.

## 3. Per-page reader-experience rubric

Score every page on each item as `pass`, `weak`, or `fail`, with a one-line reason. A `fail` on items 1 to 4 is a blocking finding.

1. Purpose in the first screen: the first paragraph says what the page is for and who it is for.
2. Funnel present: what/why, then quickstart or first task, then next steps. Reference pages may replace the funnel with a scannable index.
3. Diataxis purity: the page is one of tutorial, how-to, reference, explanation. Mixed pages are split candidates.
4. Task completion path: a reader can finish the page's job without leaving it for a prerequisite the page did not name.
5. Heading hierarchy: one H1, no skipped levels, headings are informative and scannable. More than 40 headings on one page is a split signal.
6. Wall-of-text density: paragraphs over 6 sentences, or sections over roughly 600 words with no list, table, or code block.
7. Table monsters: tables over 12 rows with prose cells, or tables that wrap to unreadable widths. Prefer a list with sub-headings or a reference sub-page.
8. Code block accuracy: commands are copy-ready, name the shell, and match the current CLI. Placeholders are marked as placeholders.
9. Critical facts trapped in images or callouts with no text equivalent.
10. Cross-links: every referenced page and anchor exists. Related pages link both directions.
11. Terminology: one term per concept across the page, matching the glossary if one exists. Run `scripts/ste-lint.py --mode flavored` on explanation pages and `--mode strict --max-words 20` on procedure and reference pages, and record the hard-violation rate per 100 words.
12. Staleness signals: version-locked wording with no version scope, dead product names, "coming soon" older than one release, TODO markers.
13. Duplicate coverage: the same procedure or concept appears on more than one page with drift between copies.
14. Reader-journey position: the nav puts the page where a reader on that journey would look for it.

## 4. Oversized page protocol

For every page over 20k characters:

1. Map its H2 sections with word counts and the Diataxis type of each section.
2. Propose a split: one page per coherent job, plus a short parent page that is an index with one line per child.
3. Preserve every anchor: list the old `page#anchor` targets and the new destinations, and add redirects in the framework config when it supports them.
4. Check inbound links across the tree before moving content. Update them in the same change.
5. If the page is a generated reference (config schema, CLI output), do not split by hand. Record it as a generator finding.

## 5. Navigation and information architecture

- Compare the nav tree to the reader journeys the product has (install, first run, configure, integrate, operate, extend, troubleshoot). Every journey needs a start page reachable in two clicks.
- Flag groups with more than 12 siblings and groups with one child.
- Flag tabs or top-level groups whose names are internal jargon.
- Check ordering inside groups: overview first, tasks in the order a reader does them, reference last.
- Check that the landing page routes each audience in one screen.

## 6. Multilingual and i18n at scale

- Find the source-of-truth locale and the translation mechanism (per-locale directories, `.i18n/*-navigation.json`, glossary files, translation workflow docs).
- For each target locale, report: nav parity (same entries), page parity (same set), and freshness (source pages changed after the locale was last synced).
- Glossary terms are STE "one word, one meaning" anchors. Run the glossary check the repo ships if it has one, and flag source pages that use a term the glossary maps differently.
- Do not translate in an audit pass. Record the parity gap and the sync intent per `references/principles.md`.

## 7. Governance surfaces inside the docs tree

Docs trees often carry their own `AGENTS.md`, `CLAUDE.md`, `docs_map.md`, or contribution page. Audit them with `references/agent-and-contributing.md`. Check that the docs-specific commands they list exist in `package.json` and that the docs map matches the nav.

## 8. Finding ledger

Every finding is one JSON object. Append to `docs-audit-ledger.jsonl` at the repo root of the audit (or the path the user names). Workflows and sub-agents write to the same file so remediation can resume.

```json
{"id": "channels-01-007", "shard": "channels-01", "file": "docs/channels/slack.md", "line": 412,
 "rubric": 6, "severity": "blocking|major|minor", "kind": "ux|ia|accuracy|ste|link|i18n|governance|generated",
 "summary": "Section 'Advanced routing' is 1,900 words of prose with no list or table.",
 "evidence": "H2 at line 380, next H2 at line 512, 0 lists, 0 tables.",
 "fix": "Split into 'Routing rules' (list) and 'Routing examples' (code).",
 "confidence": 0.9, "status": "open|verified|refuted|fixed|wontfix", "verified_by": []}
```

Rules:
- `summary` and `fix` are written in Strict STE. One sentence each where possible.
- `evidence` cites lines or counts. A finding without evidence is refuted by default.
- Severity: blocking blocks a reader from completing the page's job. Major costs the reader time or trust. Minor is polish.
- Dedupe by `file` plus `rubric` plus overlapping line range before verification.

## 9. Verification before remediation

Each finding with severity blocking or major gets an adversarial check by a separate agent that has not seen the finder's reasoning. Its job is to refute. A finding survives with two of three votes, or one vote when only one verifier is available. Refuted findings stay in the ledger with `status: refuted` and the reason.

## 10. Remediation

- Apply fixes per file, one agent per file, in an isolated worktree when several agents edit in parallel.
- Order: blocking accuracy and link fixes first, then IA and splits, then STE prose passes, then minor polish.
- Every remediation agent re-runs the native validators and `scripts/ste-lint.py` on the files it touched. Hard violations must not increase.
- Record `status: fixed` with the commit or diff reference. Never mark fixed without a diff.
- Brownfield rule applies: match existing conventions, preserve anchors, add redirects, and keep the smallest safe change set per file.

## 11. Deliverables for a large audit

1. Coverage table: pages in scope, pages read, percent, per directory.
2. Blocking findings with file and required fix.
3. Split plan for every oversized page.
4. Nav and IA change list.
5. STE lint summary per directory (`scripts/ste-lint.py --summary`).
6. i18n parity table.
7. Ledger path and counts by status.
8. Residual risk: what was not verified and why.

## 12. Worked profile: OpenClaw docs

A representative large tree, recorded as a calibration example. Re-survey before relying on these numbers.

- Framework: Mintlify, config at `docs/docs.json`. Nav also mirrored per locale under `docs/.i18n/*-navigation.json`, with glossaries under `docs/.i18n/glossary.*.json` and a translation workflow page.
- Scale at survey time (September 2026): about 770 Markdown pages, with the `plugins/` directory alone over 200 files. More than 20 pages exceed 20k characters, and the largest (`web/control-ui.md`, `channels/slack.md`, `gateway/configuration-reference.md`, `gateway/config-agents.md`, `plugins/codex-harness.md`) run 70k to 100k characters each.
- Native validators: `pnpm docs:check-links`, `pnpm docs:check-links:anchors`, `pnpm docs:check-mdx`, `pnpm docs:spellcheck`, `pnpm docs:list`, `pnpm docs:map:gen`, plus `scripts/check-docs-i18n-glossary.mjs` and `scripts/docs-link-audit.mjs`.
- Generated content: `docs/.generated/` holds baseline hashes for the config reference, plugin SDK API, and SQLite transcript schema. Treat pages tied to those baselines as generator-owned.
- Governance inside the tree: `docs/AGENTS.md`, `docs/CLAUDE.md`, `docs/docs_map.md`, `docs/prose.md`. Audit these first. They define the style the rest of the tree is supposed to follow.
- Suggested sharding: one shard per oversized page, then directory shards of about 20 pages. Expect roughly 60 shards for a full pass. Use `references/workflows.md` to run them in parallel.
