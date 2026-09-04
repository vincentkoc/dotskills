# Running Audits and Remediation as Claude Workflows

Claude Code's Workflow tool runs a JavaScript script that spawns many sub-agents with deterministic control flow. Use it for docs work that one context cannot hold: full-tree audits, mass STE passes, and parallel remediation. This file gives the execution ladder, the rules a script must follow, and two script templates.

## Execution ladder

Pick the highest rung the session supports and the user has opted into.

1. `workflow`: the Workflow tool is available and the user opted in. Opt-in phrases: "use a workflow", "ultracode", "fan out agents", or a skill that says to. Use the templates below.
2. `sub-agent-assisted`: the Agent tool is available. Use the prompt files in `agents/` with the Agent tool, one agent per shard or finding, and merge by hand into the ledger.
3. `single-agent`: no delegation available. Work shard by shard in one context, write the ledger after each shard, and report coverage honestly.

Do not launch a Workflow without the opt-in. Say in one line what a workflow would do and roughly how many agents it would spawn, and ask. If the user already opted in, do not ask again.

## Script rules (from the workflow-authoring reference)

- Load the `workflow-authoring` skill before writing a script. The rules below are the ones this skill depends on.
- Open the script with `export const meta = { name, description, phases }` as a pure literal.
- Default to `pipeline()` so shards flow through stages independently. Use `parallel()` only where a stage needs every prior result at once (dedupe across shards, early exit).
- Give every `agent()` a `schema` so results are validated objects, not prose to parse.
- Omit `model` so agents inherit the session model. Set `effort` per stage: `low` for inventory and lint, `high` for audit and verification, `xhigh` for rewrites, remediation, and synthesis.
- Use `isolation: 'worktree'` only for agents that edit files in parallel.
- No `Date.now()`, `Math.random()`, or Node APIs. Pass timestamps and paths through `args`.
- `log()` anything dropped, sampled, or capped. Silent truncation reads as full coverage.
- Filter `null` results (`.filter(Boolean)`): a skipped or failed agent returns null.
- Keep the agent count under the session's guideline unless the user asked for scale. A full-tree audit of 60 shards with verification is above the default guideline. Say so and get the go-ahead.

## Shared schemas

```js
const FINDINGS = {
  type: 'object',
  properties: {
    shard: { type: 'string' },
    pages_read: { type: 'array', items: { type: 'string' } },
    pages_skipped: { type: 'array', items: { type: 'string' } },
    findings: { type: 'array', items: { type: 'object', properties: {
      file: { type: 'string' }, line: { type: 'integer' }, rubric: { type: 'integer' },
      severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
      kind: { type: 'string' }, summary: { type: 'string' }, evidence: { type: 'string' },
      fix: { type: 'string' }, confidence: { type: 'number' } },
      required: ['file', 'rubric', 'severity', 'kind', 'summary', 'evidence', 'fix'] } },
  },
  required: ['shard', 'pages_read', 'pages_skipped', 'findings'],
}
const VERDICT = {
  type: 'object',
  properties: { refuted: { type: 'boolean' }, reason: { type: 'string' } },
  required: ['refuted', 'reason'],
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

## Template 1: full-tree audit

Scout inline first: run the inventory from `references/large-docs-audit.md` section 2 and build the shard list. Pass it in as `args.shards` (array of `{id, files}`), together with `args.ledgerPath`, `args.rubricPath` (this skill's `references/large-docs-audit.md`), and `args.stePath` (this skill's `scripts/ste-lint.py`).

```js
export const meta = {
  name: 'docs-tree-audit',
  description: 'Audit every docs shard, verify blocking and major findings, synthesize a fix plan',
  phases: [{ title: 'Audit' }, { title: 'Verify' }, { title: 'Synthesize' }],
}
// FINDINGS and VERDICT schemas from references/workflows.md go here.
const shards = args.shards
log(`${shards.length} shards, ${shards.reduce((n, s) => n + s.files.length, 0)} pages in scope`)

const audited = await pipeline(
  shards,
  s => agent(
    `You are the docs-ux-audit agent. Read the rubric at ${args.rubricPath} section 3 and apply it to EVERY file below in full. ` +
    `Run python3 ${args.stePath} --summary on the files and include the hard-violation rate in evidence for rubric 11. ` +
    `Do not sample. List any file you could not read under pages_skipped with the reason. ` +
    `Write summary and fix in Strict Simplified Technical English. Files:\n${s.files.join('\n')}`,
    { label: `audit:${s.id}`, phase: 'Audit', effort: 'high', schema: FINDINGS }),
  r => r && r.findings.filter(f => f.severity !== 'minor').map(f => ({ ...f, shard: r.shard })),
  fs => parallel((fs || []).map(f => () =>
    parallel([0, 1, 2].map(i => () => agent(
      `Verifier ${i}. Try to REFUTE this docs finding by reading ${f.file} around line ${f.line}. ` +
      `Finding: ${f.summary}. Evidence claimed: ${f.evidence}. Default to refuted=true if the evidence does not hold.`,
      { label: `verify:${f.shard}`, phase: 'Verify', effort: 'high', schema: VERDICT })))
      .then(vs => ({ ...f, status: vs.filter(Boolean).filter(v => !v.refuted).length >= 2 ? 'verified' : 'refuted',
                     verified_by: vs.filter(Boolean).map(v => v.reason) })))),
)

const coverage = audited.filter(Boolean).length
const results = audited.flat().filter(Boolean)
const skipped = shards.length - coverage
if (skipped) log(`${skipped} shard(s) returned nothing and must be re-run`)

phase('Synthesize')
const plan = await agent(
  `Merge these verified docs findings into one prioritized plan: blocking first, then major. ` +
  `Group by file, dedupe overlapping line ranges, and list oversized-page split plans separately. ` +
  `Write in Strict Simplified Technical English. Findings JSON:\n${JSON.stringify(results)}`,
  { label: 'synthesis', phase: 'Synthesize', effort: 'xhigh' })
const critic = await agent(
  `Completeness critic. Shards planned: ${shards.length}. Shards with results: ${coverage}. ` +
  `Given this plan, name what is missing: unread directories, unverified claims, checks not run. Plan:\n${plan}`,
  { label: 'critic', phase: 'Synthesize', effort: 'xhigh' })
return { results, plan, critic, coverage: `${coverage}/${shards.length} shards` }
```

After the run, append `results` to the ledger file, read the critic's answer, and run another round for whatever it names. Repeat until two rounds add nothing. Resume with `resumeFromRunId` if a run is interrupted.

## Template 2: parallel remediation

Input: `args.items`, one entry per file with its verified findings (`{file, findings:[...], mode: 'strict'|'flavored', validators: ['pnpm docs:check-mdx', ...]}`), plus `args.stePath` and `args.stePolicyPath` (this skill's `references/simplified-technical-english.md`).

```js
export const meta = {
  name: 'docs-remediation',
  description: 'Apply verified docs fixes one file per agent, lint and validate each, then review',
  phases: [{ title: 'Fix' }, { title: 'Review' }],
}
// EDIT_RESULT and VERDICT schemas from references/workflows.md go here.
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
    { label: `review:${it.file}`, phase: 'Review', effort: 'high', schema: VERDICT })
    .then(v => ({ ...r, review: v })),
)
const out = fixed.filter(Boolean)
log(`${out.length}/${args.items.length} files completed`)
return out
```

Worktree isolation means each agent's edits land in its own worktree. After the run, merge the worktrees the reviewer accepted, then run the native validators once more on the merged tree before opening a PR.

## Reporting after a workflow

Report per `references/large-docs-audit.md` section 11. Name the run id so the user can inspect `/workflows` and the journal. State coverage as a fraction. If any shard returned null, say which ones and that they were re-queued, not silently dropped.
