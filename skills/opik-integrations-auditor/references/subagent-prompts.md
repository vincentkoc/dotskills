# Sub-Agent Prompts

Use these prompts to parallelize first-pass integration analysis.

## 1) Inventory Agent

```text
Build an integration inventory for this repository.

Scope:
- Python SDK integrations
- TypeScript SDK integrations
- OTEL/API backend integration entrypoints

Output:
- Table columns: Name, Surface, Pattern, Entrypoint, Primary files, Test files, Doc files.
- Include only integrations with direct evidence from source files.
- Add file+line evidence for each row.
```

## 2) Behavior Contract Agent

```text
For the assigned integration set, extract behavior contracts.

Required fields per integration:
- capture input/output location
- streaming behavior and finalization guarantee
- error handling path
- flush/shutdown semantics
- span/trace parent-child behavior

Output format:
- One section per integration
- concise bullets
- file+line evidence for every claim
- include unresolved ambiguities as open questions
```

## 3) Data Contract Agent

```text
For the assigned integration set, extract data contracts.

Required fields per integration:
- usage/token extraction mechanism
- provider/model metadata capture
- tags/thread/custom metadata propagation
- cost-related fields passed downstream

Output:
- Matrix row per integration
- explicit "present/missing/partial" status per field
- file+line evidence for each status
```

## 4) Backend OTEL Mapping Agent

```text
Audit backend OTEL ingestion and mapping behavior.

Focus:
- OTEL ingestion endpoints and accepted content types
- trace-id mapping (OTEL -> Opik) lifecycle and stability
- mapping rule factory and integration scope detection
- root span to trace promotion behavior
- failure/edge behavior visible in code/tests

Output:
- architecture summary
- risk list (P1/P2/P3)
- missing test scenarios
- file+line evidence for all findings
```

## 5) Test Coverage Agent

```text
Assess integration test quality across Python, TypeScript, and backend OTEL.

Checklist:
- non-streaming path
- streaming success path
- streaming interruption/failure
- error capture behavior
- flush behavior under pending batches
- span hierarchy correctness
- idempotency/double-wrap protection

Output:
- coverage matrix by integration
- missing tests prioritized by risk
- recommended test names/locations
- file+line evidence
```

## 6) Docs Synthesis Agent

```text
Generate first-pass integration docs updates from evidence.

For each integration doc section include:
- overview (surface, pattern, entrypoint)
- setup and minimal example
- captured fields
- streaming/finalization behavior
- flush/shutdown guidance
- troubleshooting

Constraints:
- do not invent behavior
- mark unknowns explicitly
- include source references (file paths)
```

## 7) Consolidator Agent

```text
Consolidate outputs from all sub-agents into a single review report.

Sections:
1. Cross-surface integration matrix
2. Findings prioritized (P1/P2/P3)
3. Documentation patch plan
4. Test plan
5. Open questions

Rules:
- deduplicate overlapping findings
- keep only evidence-backed claims
- include exact file+line references
```
