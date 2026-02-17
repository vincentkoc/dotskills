#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_FILE="$ROOT_DIR/releases/skills.json"
REPO_SLUG="${SKILLS_REPO:-vincentkoc/dotskills}"

entry_file_for_dir() {
  local dir="$1"
  for entry in SKILL.md AGENT.md AGENTS.md; do
    if [[ -f "$dir/$entry" ]]; then
      echo "$dir/$entry"
      return 0
    fi
  done
  return 1
}

is_internal_entry() {
  local entry_file="$1"
  awk '
    BEGIN { in_frontmatter = 0; found = 0 }
    NR == 1 && /^[[:space:]]*---[[:space:]]*$/ { in_frontmatter = 1; next }
    in_frontmatter == 1 {
      if ($0 ~ /^[[:space:]]*---[[:space:]]*$/) { exit }
      if ($0 ~ /^[[:space:]]*internal:[[:space:]]*true([[:space:]]|$)/) { print "true"; found = 1; exit }
    }
    END {
      if (!found) {
        print "false"
      }
    }
  ' "$entry_file"
}

description_for_entry() {
  local entry_file="$1"
  awk '
    BEGIN { found = 0; in_frontmatter = 0 }
    NR == 1 && /^[[:space:]]*---[[:space:]]*$/ { in_frontmatter = 1; next }
    in_frontmatter == 1 {
      if ($0 ~ /^[[:space:]]*---[[:space:]]*$/) {
        in_frontmatter = 0
      }
      next
    }
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    {
      print $0
      found = 1
      exit
    }
    END {
      if (!found) {
        print "No description provided."
      }
    }
  ' "$entry_file"
}

mkdir -p "$(dirname "$OUTPUT_FILE")"

tmp_rows="$(mktemp)"
trap "rm -f '$tmp_rows'" EXIT

if [[ -d "$ROOT_DIR/skills" ]]; then
  while IFS= read -r skill_dir; do
    entry_file="$(entry_file_for_dir "$skill_dir" || true)"
    [[ -n "$entry_file" ]] || continue

    internal="$(is_internal_entry "$entry_file")"
    if [[ "$internal" == "true" ]]; then
      continue
    fi

    skill_name="$(basename "$skill_dir")"
    rel_source="./${skill_dir#"$ROOT_DIR"/}"
    description="$(description_for_entry "$entry_file")"

    printf '%s\t%s\t%s\n' "$skill_name" "$rel_source" "$description"
  done < <(find "$ROOT_DIR/skills" -mindepth 1 -maxdepth 1 -type d -print | sort)
fi > "$tmp_rows"

python3 - "$OUTPUT_FILE" "$tmp_rows" "$REPO_SLUG" <<'PY'
import json
import sys

out_path = sys.argv[1]
rows_path = sys.argv[2]
repo_slug = sys.argv[3]
skills = []

with open(rows_path, "r", encoding="utf-8") as rows:
    for line in rows:
        line = line.rstrip("\n")
        if not line:
            continue
        name, source, description = line.split("\t", 2)
        skills.append(
            {
                "name": name,
                "source": source,
                "description": description,
                "install": f"npx skills add {repo_slug} --skill {name} -y",
            }
        )

payload = {
    "repo": repo_slug,
    "skills": skills,
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
    f.write("\n")
PY

echo "Wrote $OUTPUT_FILE"
