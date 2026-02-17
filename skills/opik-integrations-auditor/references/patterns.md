# Integration Patterns

## Pattern catalog
- Method patching: wraps SDK/client methods directly.
- Callback handler: receives framework lifecycle events.
- Hybrid: callback + patching or callback + OTEL interception.
- Proxy wrapper: JS/TS `Proxy` over SDK surface.
- OTel exporter: translates OTel spans to Opik traces/spans.
- OTEL ingestion endpoint: backend receives and maps OTLP payloads.

## Classification rules
1. If integration wraps methods without framework callback contracts, classify as method patching/proxy.
2. If integration implements framework callback interfaces, classify as callback.
3. If it mixes multiple capture paths, classify as hybrid.
4. If it receives OTel spans and emits to Opik client, classify as OTel exporter.
5. If it is backend HTTP ingestion, classify as OTEL ingestion endpoint.

## Minimum behavior contract per pattern
- Capture: where input/output are extracted.
- Streaming: how final output is accumulated/finalized.
- Errors: what exceptions/events are captured.
- Flush: explicit shutdown contract.
- Hierarchy: parent/child span relationship behavior.
