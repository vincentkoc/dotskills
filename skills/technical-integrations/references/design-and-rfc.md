# Design and RFC

Use this to draft integration RFCs and architecture proposals.

## RFC structure

1. Problem statement and constraints
2. Current-state evidence
3. Goals and non-goals
4. Options considered
5. Chosen design and rationale
6. API design implications
7. SDK design implications
8. Backward compatibility and migration
9. Testing strategy
10. Rollout and observability plan
11. Risks and open questions

## Option analysis rules

- Provide at least two viable options when feasible.
- Include explicit tradeoffs: complexity, risk, latency, cost, operability.
- State why rejected options fail constraints.
- Tie decision to principles in `principles.md`.

## API and SDK guidance

- Keep API contract vendor-neutral where possible.
- Use stable abstractions in SDK surface; keep vendor-specific config scoped.
- Define pagination, retries, and error translation behavior explicitly.
- Document deprecation/migration when changing public surfaces.
