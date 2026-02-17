#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_FILE="$ROOT_DIR/.claude-plugin/marketplace.json"
MARKETPLACE_NAME="${SKILLS_MARKETPLACE_NAME:-dotskills}"
MARKETPLACE_OWNER="${SKILLS_MARKETPLACE_OWNER:-vincentkoc}"

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

plugin_name_for_dir() {
  local dir="$1"
  basename "$dir"
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

collect_dirs() {
  if [[ -d "$ROOT_DIR/skills" ]]; then
    find "$ROOT_DIR/skills" -mindepth 1 -maxdepth 1 -type d -print
  fi
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

mkdir -p "$(dirname "$OUTPUT_FILE")"

tmp_rows="$(mktemp)"
trap "rm -f '$tmp_rows'" EXIT

{
  while IFS= read -r skill_dir; do
    [[ -n "$skill_dir" ]] || continue

    entry_file="$(entry_file_for_dir "$skill_dir" || true)"
    [[ -n "$entry_file" ]] || continue
    if [[ "$(is_internal_entry "$entry_file")" == "true" ]]; then
      continue
    fi

    plugin_name="$(plugin_name_for_dir "$skill_dir")"
    rel_source="./${skill_dir#"$ROOT_DIR"/}"
    description="$(description_for_entry "$entry_file")"

    printf '%s\t%s\t%s\n' "$plugin_name" "$rel_source" "$description"
  done < <(collect_dirs | sort -u)
} > "$tmp_rows"

python3 - "$OUTPUT_FILE" "$tmp_rows" "$MARKETPLACE_NAME" "$MARKETPLACE_OWNER" <<'PY'
import json
import sys

out_path = sys.argv[1]
rows_path = sys.argv[2]
marketplace_name = sys.argv[3]
marketplace_owner = sys.argv[4]
plugins = []
seen = set()

with open(rows_path, "r", encoding="utf-8") as rows:
    for line in rows:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        name, source, description = parts
        key = (name, source)
        if key in seen:
            continue
        seen.add(key)
        plugins.append(
            {
                "name": name,
                "source": source,
                "skills": "./",
                "description": description,
            }
        )

payload = {
    "name": marketplace_name,
    "owner": {"name": marketplace_owner},
    "metadata": {
        "description": "A .skills collection: prompts with resources and scripts as reusable AI runtime modules.",
        "version": "1.0.0",
    },
    "plugins": plugins,
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
    f.write("\n")
PY

echo "Wrote $OUTPUT_FILE"
