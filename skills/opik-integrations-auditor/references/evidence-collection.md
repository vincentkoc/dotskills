# Evidence Collection

## Suggested commands
```bash
# Inventory integration files
rg --files sdks/python/src/opik/integrations sdks/typescript | head -200

# Locate integration docs and tests
rg -n "integrat|track_|OpikTracer|OpenTelemetry|otel|flush" \
  sdks/python sdks/typescript apps/opik-backend apps/opik-documentation | head -400

# OTEL backend anchors
rg -n "OpenTelemetryResource|OpenTelemetryService|OpenTelemetryMapper|MappingRuleFactory" \
  apps/opik-backend/src/main/java apps/opik-backend/src/test/java
```

## Evidence capture rules
- Every finding must cite file path and line.
- Prefer source code + tests over narrative docs for truth.
- If docs and code disagree, mark as a doc gap and trust code behavior.
