#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
required_sections=("## Purpose" "## When to use" "## Workflow" "## Inputs" "## Outputs")

failures=0
checked=0

while IFS= read -r skill_file; do
  checked=$((checked + 1))

  for section in "${required_sections[@]}"; do
    if ! rg -q "^${section}$" "$skill_file"; then
      echo "[FAIL] $skill_file missing section: $section"
      failures=$((failures + 1))
    fi
  done
done < <(find "$ROOT_DIR/skills" "$ROOT_DIR/vendor" -type f -name SKILL.md 2>/dev/null | sort)

if [[ $checked -eq 0 ]]; then
  echo "[WARN] No SKILL.md files found under skills/ or vendor/."
fi

if [[ $failures -gt 0 ]]; then
  echo "Validation failed with $failures issue(s)."
  exit 1
fi

echo "Validation passed. Checked $checked skill(s)."
