#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_REF="${1:-origin/main}"
HEAD_REF="${2:-HEAD}"

if ! git -C "$ROOT_DIR" rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
  BASE_REF="$(git -C "$ROOT_DIR" merge-base origin/main "$HEAD_REF")"
fi

if ! git -C "$ROOT_DIR" rev-parse --verify "$HEAD_REF" >/dev/null 2>&1; then
  echo "Invalid head ref: $HEAD_REF" >&2
  exit 1
fi

git -C "$ROOT_DIR" diff --name-only "$BASE_REF...$HEAD_REF" \
  | awk -F/ '
      $1 == "skills" && NF >= 2 { print "skills/" $2 }
      $1 == "vendor" && NF >= 3 { print "vendor/" $2 "/" $3 }
    ' \
  | sort -u
