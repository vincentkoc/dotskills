# Testing Checklist

## Minimum checks per integration
- Non-streaming success path
- Streaming success path
- Streaming interruption/failure path
- Error propagation and captured error metadata
- Flush behavior under pending batches
- Parent/child hierarchy correctness
- Usage/token extraction correctness
- Idempotency (double-wrapping or repeated setup)

## Backend OTEL checks
- Protobuf payload ingestion
- JSON payload ingestion
- Stable trace mapping across batches
- Root-span trace creation behavior
- Mapping-rule transformations for key attributes

## Exit criteria
- Required paths covered by automated tests or explicitly documented gaps.
- No P1 open issues for release-ready integration docs.
