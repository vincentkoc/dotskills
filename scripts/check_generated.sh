#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! git -C "$ROOT_DIR" diff --quiet -- .claude-plugin/marketplace.json releases/skills.json; then
  echo "Generated artifacts are out of date." >&2
  echo "Run: make marketplace && make releases-index" >&2
  git -C "$ROOT_DIR" --no-pager diff -- .claude-plugin/marketplace.json releases/skills.json
  exit 1
fi

echo "Generated artifacts are in sync."
