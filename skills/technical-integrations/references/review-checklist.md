# Review Checklist

## Blocking checks

- Design reuses existing patterns unless deviation is justified.
- Public API/SDK changes include migration and compatibility notes.
- Error model and retry semantics are explicit and test-covered.
- Security/auth requirements are documented and enforced.
- Observability signals are defined for operations.

## Non-blocking quality checks

- Naming and abstractions are consistent with existing integrations.
- Vendor-specific logic is isolated behind stable interfaces.
- Documentation includes integration examples and failure behavior.
- Rollout steps include canary/rollback guidance.

## Output format

1. Blocking findings
2. Non-blocking improvements
3. Validation status (done/pending)
4. Remaining unknowns and ownership
