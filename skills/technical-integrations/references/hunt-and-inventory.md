# Hunt and Inventory

## Goal

Build a concrete baseline of existing integration patterns before proposing changes.

## Steps

1. Identify current integration surfaces:
   - API endpoints and schemas
   - SDK client abstractions
   - background workers/webhooks/events
   - auth/credential handling
   - retries, backoff, and rate limiting
2. Capture each integration as an inventory row.
3. Classify each row by pattern family (adapter, direct API, webhook bridge, job runner, etc.).
4. Map test coverage and docs coverage for each row.
5. Highlight reusable modules and anti-patterns.

## Inventory schema

- Integration name
- Surface (API, SDK, webhook, async worker, etc.)
- Contract shape (inputs, outputs, errors)
- Reliability behavior (retry/timeout/idempotency)
- Observability behavior (logs/metrics/traces)
- Test depth (unit/integration/e2e)
- Reusability score (high/medium/low)
- Notes and evidence links
