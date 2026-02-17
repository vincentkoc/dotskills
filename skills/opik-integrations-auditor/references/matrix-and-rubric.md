# Matrix And Rubric

## Matrix schema
| Name | Surface | Pattern | Entrypoint | Streaming | Flush | Usage extraction | Span hierarchy | Tests | Docs | Risks | Action |
|------|---------|---------|------------|-----------|-------|------------------|----------------|-------|------|-------|--------|

## Required values
- Surface: `python-sdk` | `typescript-sdk` | `otel-api`
- Pattern: `method-patching` | `callback` | `hybrid` | `proxy-wrapper` | `otel-exporter` | `otel-ingestion`

## Review rubric (0-3)
- Correctness
- Reliability/failure handling
- Streaming completeness
- Span/trace hierarchy correctness
- Usage/cost data quality
- Test depth
- Documentation quality
- Operational readiness

## Severity mapping
- P1: data loss, broken tracing, incorrect hierarchy, or API incompatibility.
- P2: partial capture, weak retries/finalization, substantial doc/test gaps.
- P3: consistency/readability/maintainability gaps.
