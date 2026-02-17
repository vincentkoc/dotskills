#!/usr/bin/env bash
set -euo pipefail

WORKFLOW_FILE=".github/workflows/codeql.yml"

if [[ ! -f "$WORKFLOW_FILE" ]]; then
  echo "Missing $WORKFLOW_FILE" >&2
  echo "Add CodeQL workflow to keep code scanning enforced." >&2
  exit 1
fi

if ! rg -q "github/codeql-action/init@" "$WORKFLOW_FILE"; then
  echo "CodeQL workflow missing init step." >&2
  exit 1
fi

if ! rg -q "github/codeql-action/analyze@" "$WORKFLOW_FILE"; then
  echo "CodeQL workflow missing analyze step." >&2
  exit 1
fi

echo "CodeQL workflow guard passed."
