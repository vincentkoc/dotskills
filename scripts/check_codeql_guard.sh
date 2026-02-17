#!/usr/bin/env bash
set -euo pipefail

WORKFLOW_FILE=".github/workflows/codeql.yml"

if [[ ! -f "$WORKFLOW_FILE" ]]; then
  echo "Missing $WORKFLOW_FILE" >&2
  echo "Add CodeQL workflow to keep code scanning enforced." >&2
  exit 1
fi

if command -v rg >/dev/null 2>&1; then
  search_cmd=(rg -q)
else
  search_cmd=(grep -Eq)
fi

if ! "${search_cmd[@]}" "github/codeql-action/init@" "$WORKFLOW_FILE"; then
  echo "CodeQL workflow missing init step." >&2
  exit 1
fi

if ! "${search_cmd[@]}" "github/codeql-action/analyze@" "$WORKFLOW_FILE"; then
  echo "CodeQL workflow missing analyze step." >&2
  exit 1
fi

echo "CodeQL workflow guard passed."
