#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
skill_file="$skill_dir/SKILL.md"

if [[ ! -f "$skill_file" ]]; then
  echo "SKILL.md not found in $skill_dir" >&2
  exit 1
fi

if ! rg -q "^---$" "$skill_file"; then
  echo "Frontmatter delimiter is missing in $skill_file" >&2
  exit 1
fi

echo "example-skill preflight passed: $skill_file"
