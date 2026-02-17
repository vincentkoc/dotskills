# Principles

Use these constraints for all integration work.

## Core principles

- Vendor-agnostic first: isolate vendor-specific details behind adapters/interfaces.
- Framework-agnostic first: avoid binding the design to a single runtime stack unless required.
- Pattern-first design: reuse proven internal patterns before inventing new abstractions.
- Compatibility first: preserve existing contracts unless migration is explicitly approved.
- Evidence first: proposals must cite observed behavior in current code/docs/tests.

## Integration boundaries

- Separate control plane from data plane when applicable.
- Keep auth, retries, rate limits, and observability explicit at boundaries.
- Model errors as stable categories, not vendor-specific strings.
- Define idempotency and timeout behavior up front.

## Decision hierarchy

1. Preserve system safety and contract stability.
2. Preserve developer ergonomics and consistency.
3. Optimize for extensibility to additional vendors.
4. Optimize for implementation speed.
