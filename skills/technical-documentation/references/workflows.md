# Running Audits and Remediation as Claude Workflows

Claude Code's Workflow tool runs a JavaScript script that spawns many sub-agents with deterministic control flow. Use it for docs work that one context cannot hold: full-tree audits, mass STE passes, and parallel remediation. This file gives the execution ladder, the token rules, the resume rules, and three script templates.

## Execution ladder

Pick the highest rung the session supports and the user has opted into.

1. `workflow`: the Workflow tool is available and the user opted in. Opt-in phrases: "use a workflow", "ultracode", "fan out agents", or a skill that says to. Use the templates below.
2. `sub-agent-assisted`: the Agent tool is available. Use the prompt files in `agents/` with the Agent tool, one agent per shard, and merge by hand into the ledger.
3. `single-agent`: no delegation available. Work shard by shard in one context, write the ledger after each shard, and report coverage honestly.

Do not launch a Workflow without the opt-in. Say in one line what a workflow would do and roughly how many agents it would spawn, and ask. If the user already opted in, do not ask again.

## Token rules

A full-tree audit costs millions of subagent tokens. These rules decide whether it finishes in one session or four.

- **Do the mechanical work in Python first.** Nav walks, size distributions, title collisions, heading counts, link resolution, and lint baselines are scripts. Agents get their output as context.
- **Run the repo's native validators before the agents.** Findings a checker can decide never reach an agent.
- **Batch verification per shard.** One verifier for a shard's findings, not one per finding. Per-finding fan-out multiplies agent count by ten and is the single largest waste.
- **Scope verifier reads.** Cited line range plus context with `sed -n`, `grep` for a heading, `test -f` for a link target. Never a whole file.
- **Tier the models.** `haiku` for inventory and lint, `sonnet` at `low` effort for verification, the session model at `high` for audit reads, `xhigh` only for synthesis, rewrites, and remediation.
- **Keep arguments small.** Write shard file lists to `.audit/shards/<id>.txt` and pass ids. Large inline arrays bloat every resume and invalidate the cache when they change.
- **Cap what returns.** Ask for structured findings, not prose. A schema keeps a chatty agent from returning an essay.
- **Split giant pages across lens-scoped agents** rather than asking one agent for fourteen rubric items on 100k characters.
- Budget roughly 6 to 8M subagent tokens per session window. Plan the round so a natural boundary falls near that.

## Resume rules

Interruption is normal. Design for it.

- The journal at `<transcriptDir>/journal.jsonl` holds one result line per completed agent. It is the source of truth, not the tool result, which truncates.
- Rebuild the ledger from the journal after every run: read result lines, take the newest per shard, write `ledger.jsonl`, re-render the report.
- Resume with `Workflow({scriptPath, resumeFromRunId})`. Agents whose prompt and options are unchanged replay from cache instantly.
- **Never edit an audit agent's prompt or the repository root path when resuming.** Both are part of the cache key. Edit only the stages that failed.
- If the working clone disappears between sessions, re-create it at the same absolute path and at the same commit. The path is in the cache key.
- Cross-check a re-created clone. Regenerate the shard lists and check that the ids and file lists match what the cached results read.

## Shared schemas

```js
const FINDING_PROPS = {
  file: { type: 'string' }, line: { type: 'integer' }, rubric: { type: 'integer' },
  severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
  kind: { type: 'string', enum: ['ux', 'ia', 'accuracy', 'ste', 'link', 'i18n', 'governance', 'generated', 'split'] },
  summary: { type: 'string' }, evidence: { type: 'string' }, fix: { type: 'string' }, confidence: { type: 'number' },
}
const FINDINGS = {
  type: 'object',
  properties: {
    shard: { type: 'string' },
    pages_read: { type: 'array', items: { type: 'string' } },
    pages_skipped: { type: 'array', items: { type: 'string' } },
    page_scores: { type: 'array', items: { type: 'object', properties: {
      file: { type: 'string' }, fails: { type: 'array', items: { type: 'integer' } },
      weaks: { type: 'array', items: { type: 'integer' } }, note: { type: 'string' } },
      required: ['file', 'fails', 'weaks'] } },
    findings: { type: 'array', items: { type: 'object', properties: FINDING_PROPS,
      required: ['file', 'rubric', 'severity', 'kind', 'summary', 'evidence', 'fix', 'confidence'] } },
    split_plans: { type: 'array', items: { type: 'object', properties: {
      file: { type: 'string' }, chars: { type: 'integer' },
      proposed_pages: { type: 'array', items: { type: 'string' } }, rationale: { type: 'string' } },
      required: ['file', 'proposed_pages', 'rationale'] } },
    notes: { type: 'string' },
  },
  required: ['shard', 'pages_read', 'pages_skipped', 'findings'],
}
// One verdict object per shard, not per finding.
const VERDICTS = {
  type: 'object',
  properties: { file: { type: 'string' }, verdicts: { type: 'array', items: { type: 'object', properties: {
    index: { type: 'integer' }, refuted: { type: 'boolean' }, reason: { type: 'string' },
    severity_adjustment: { type: 'string', enum: ['keep', 'raise', 'lower'] } },
    required: ['index', 'refuted', 'reason', 'severity_adjustment'] } } },
  required: ['file', 'verdicts'],
}
const EDIT_RESULT = {
  type: 'object',
  properties: {
    file: { type: 'string' }, status: { type: 'string', enum: ['fixed', 'skipped', 'blocked'] },
    diff_summary: { type: 'string' }, lint_before: { type: 'integer' }, lint_after: { type: 'integer' },
    validators_passed: { type: 'boolean' }, notes: { type: 'string' },
  },
  required: ['file', 'status', 'diff_summary', 'validators_passed'],
}
```

## Template 1: full-tree audit with batched verification

Scout inline first: run round 0 from `references/large-docs-audit.md`, write the shard lists to disk, then pass only ids. `args` carries `root`, `commit`, `shardIds`, and the paths to the rubric, the STE policy, and the linter.

```js
export const meta = {
  name: 'docs-tree-audit',
  description: 'Audit every docs shard in full, verify blocking and major findings per shard, synthesize',
  phases: [{ title: 'Audit' }, { title: 'Verify' }, { title: 'Synthesize' }],
}
// FINDINGS and VERDICTS schemas from above go here.
const COMMON = `Repository root: ${args.root} at commit ${args.commit}. Rubric: ${args.rubricPath} section 5. ` +
  `STE policy: ${args.stePolicyPath}. Linter: ${args.stePath}. Round-0 scans already ran, so do not re-derive ` +
  `nav, sizes, or lint totals. Cite evidence as line numbers or counts. Write summary and fix in Strict STE. Do not edit files.`

const audited = await pipeline(
  args.shardIds,
  id => agent(`${COMMON}\n\nShard "${id}". Your file list is ${args.root}/.audit/shards/${id}.txt. ` +
    `Read every listed file in full. Score all rubric items per page, add a split plan for pages over 20k chars, ` +
    `and return page_scores for every page.`,
    { label: `audit:${id}`, phase: 'Audit', effort: 'high', schema: FINDINGS }),
  (r, id) => {
    if (!r) { log(`shard ${id} returned nothing - re-run`); return null }
    const items = r.findings.filter(f => f.severity !== 'minor')
    if (!items.length) return { shard: id, result: r, verified: [] }
    const listing = items.map((f, i) => `[${i}] ${f.file} line ${f.line || '?'} r${f.rubric} ${f.severity}: ${f.summary} | evidence: ${f.evidence}`).join('\n')
    // ONE verifier per shard. Range-scoped reads only.
    return agent(`${COMMON}\n\nAdversarial verifier for shard "${id}". You did not see the finder's reasoning. ` +
      `Check each finding cheaply: print only the cited line range plus 20 lines with sed -n, grep for cited headings, ` +
      `test -f for link targets. Do not read whole files. Refute when the evidence does not hold, when the cited location ` +
      `does not match, when the fix would change a stated fact or hedge, or when ${args.root}/.audit/ledger.jsonl already ` +
      `records the same defect. Set file to the shard id.\n\nFindings:\n${listing}`,
      { label: `verify:${id}`, phase: 'Verify', model: 'sonnet', effort: 'low', schema: VERDICTS })
      .then(v => ({ shard: id, result: r, verified: items.map((f, i) => {
        const x = v && (v.verdicts || []).find(y => y.index === i)
        return { ...f, shard: id, status: !x ? 'unverified' : (x.refuted ? 'refuted' : 'verified'),
                 verified_by: x ? [`${x.refuted ? 'REFUTE' : 'HOLD'}(${x.severity_adjustment}): ${x.reason}`] : [] }
      }) }))
  },
)
const done = audited.filter(Boolean)
const missing = args.shardIds.filter(id => !done.some(s => s.shard === id))
if (missing.length) log(`${missing.length} shard(s) missing: ${missing.join(', ')}`)

phase('Synthesize')
const live = done.flatMap(s => s.verified).filter(f => f.status !== 'refuted')
const compact = live.map(f => ({ file: f.file, line: f.line, rubric: f.rubric, severity: f.severity, summary: f.summary, fix: f.fix }))
const plan = await agent(`${COMMON}\n\nMerge these verified findings into one prioritized plan. Findings:\n${JSON.stringify(compact)}`,
  { label: 'synthesis', phase: 'Synthesize', effort: 'xhigh' })
const critic = await agent(`${COMMON}\n\nCompleteness critic. Shards planned ${args.shardIds.length}, with results ${done.length}. ` +
  `Name concretely what is missing: unread directories, unverified claims, checks not run, rubric items no finding cites. Plan:\n${plan}`,
  { label: 'critic', phase: 'Synthesize', effort: 'xhigh' })
return { coverage: { shards: `${done.length}/${args.shardIds.length}`, missing },
         findings: done.flatMap(s => s.verified.concat(s.result.findings.filter(f => f.severity === 'minor').map(f => ({ ...f, shard: s.shard, status: 'open' })))),
         split_plans: done.flatMap(s => s.result.split_plans || []),
         page_scores: done.flatMap(s => s.result.page_scores || []), plan, critic }
```

After the run: rebuild the ledger from the journal, re-render the report, read the critic, and run round 2 for what it names.

## Template 2: round-2 targeted finder pass

Same shape, different targets. Build the target lists with a script from the round-1 page scores:

- pages that scored all-pass
- the largest pages, one lens at a time
- pages classified by sampling
- accordion-heavy pages
- uncovered reader journeys
- locale parity

Each finder gets the ledger path, greps it, and skips anything already recorded. Batch verification per finder, exactly as in template 1.

## Template 3: parallel remediation

Input: `args.items`, one entry per file with its verified findings (`{file, findings, mode, validators}`), plus the linter and policy paths.

```js
export const meta = {
  name: 'docs-remediation',
  description: 'Apply verified docs fixes one file per agent, lint and validate each, then review',
  phases: [{ title: 'Fix' }, { title: 'Review' }],
}
// EDIT_RESULT and VERDICTS schemas from above go here.
const fixed = await pipeline(
  args.items,
  it => agent(
    `You are the remediation agent for ${it.file}. Apply ONLY these verified findings, smallest safe change per finding, ` +
    `preserving anchors and existing conventions: ${JSON.stringify(it.findings)}. ` +
    `Prose rules: ${args.stePolicyPath}, mode ${it.mode}. Before and after editing run ` +
    `python3 ${args.stePath} --mode ${it.mode} ${it.file} and report hard counts. Then run: ${it.validators.join(' && ')}. ` +
    `Hard violations must not increase. If a fix needs a decision you cannot make, set status=blocked and explain.`,
    { label: `fix:${it.file}`, phase: 'Fix', effort: 'xhigh', isolation: 'worktree', schema: EDIT_RESULT }),
  (r, it) => r && agent(
    `Review the diff for ${it.file}. Confirm every listed finding is addressed, no fact or hedge changed meaning, ` +
    `no anchor was lost, and the validators pass. Refute if any of those fail. Result: ${JSON.stringify(r)}`,
    { label: `review:${it.file}`, phase: 'Review', model: 'sonnet', effort: 'low', schema: VERDICTS })
    .then(v => ({ ...r, review: v })),
)
const out = fixed.filter(Boolean)
log(`${out.length}/${args.items.length} files completed`)
return out
```

Use `isolation: 'worktree'` only when agents in the same run edit the same tree. One PR's files usually go to one agent, so a shared branch is simpler and cheaper.

## Reporting after a workflow

Report per `references/large-docs-audit.md` section 12. Name the run id so the user can inspect `/workflows` and the journal. State coverage as a fraction and the finding count this round added. If any shard returned null, say which ones and that they were re-queued, not silently dropped.
