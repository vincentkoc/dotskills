#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
required_sections=("## Purpose" "## When to use" "## Workflow" "## Inputs" "## Outputs")

failures=0
checked=0
strict_checked=0
flex_checked=0

local_skill_dirs() {
  for base in "$ROOT_DIR/skills" "$ROOT_DIR/private-skills"; do
    [[ -d "$base" ]] || continue
    find "$base" -mindepth 1 -maxdepth 1 -type d -print
  done | sort
}

entry_file_for_dir() {
  local dir="$1"
  for entry in SKILL.md AGENT.md AGENTS.md; do
    if [[ -f "$dir/$entry" ]]; then
      echo "$entry"
      return 0
    fi
  done
  return 1
}

while IFS= read -r skill_dir; do
  local_entry="$(entry_file_for_dir "$skill_dir" || true)"
  if [[ -z "$local_entry" ]]; then
    echo "[FAIL] $skill_dir has no entry file (SKILL.md/AGENT.md/AGENTS.md)"
    failures=$((failures + 1))
    continue
  fi

  checked=$((checked + 1))

  if [[ "$local_entry" == "SKILL.md" ]]; then
    strict_checked=$((strict_checked + 1))
    skill_file="$skill_dir/$local_entry"
    for section in "${required_sections[@]}"; do
      if ! rg -q "^${section}$" "$skill_file"; then
        echo "[FAIL] $skill_file missing section: $section"
        failures=$((failures + 1))
      fi
    done
  else
    flex_checked=$((flex_checked + 1))
    if [[ ! -s "$skill_dir/$local_entry" ]]; then
      echo "[FAIL] $skill_dir/$local_entry is empty"
      failures=$((failures + 1))
    fi
  fi
done < <(local_skill_dirs)

while IFS= read -r entry_file; do
  checked=$((checked + 1))
  flex_checked=$((flex_checked + 1))

  if [[ ! -s "$entry_file" ]]; then
    echo "[FAIL] $entry_file is empty"
    failures=$((failures + 1))
  fi
done < <(find "$ROOT_DIR/vendor" -type f \( -name SKILL.md -o -name AGENT.md -o -name AGENTS.md \) 2>/dev/null | sort)

if [[ $checked -eq 0 ]]; then
  echo "[WARN] No skill entry files found under skills/, private-skills/, or vendor/."
fi

if [[ $failures -gt 0 ]]; then
  echo "Validation failed with $failures issue(s)."
  exit 1
fi

echo "Validation passed. Checked $checked skill(s) ($strict_checked strict, $flex_checked flexible)."

"$ROOT_DIR/scripts/validate_spec.py"
