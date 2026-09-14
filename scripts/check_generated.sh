#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# This comparison is intentionally against the index. Contributors can stage a
# regenerated artifact, then use this check to catch later generator drift.
if ! git -C "$ROOT_DIR" diff --quiet -- .claude-plugin/marketplace.json releases/skills.json; then
  echo "Generated artifacts differ from the staged versions." >&2
  echo "Run: make marketplace && make releases-index" >&2
  git -C "$ROOT_DIR" --no-pager diff -- .claude-plugin/marketplace.json releases/skills.json
  exit 1
fi

echo "Generated artifacts match the index (staged updates are allowed)."
