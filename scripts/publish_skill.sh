#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL="${1:-}"
TAG="${2:-}"
REPO="${3:-}"

if [[ -z "$SKILL" ]]; then
  echo "Usage: $0 <skill-name> [tag] [owner/repo]" >&2
  exit 1
fi

if [[ ! -d "$ROOT_DIR/skills/$SKILL" ]]; then
  echo "Skill not found: skills/$SKILL" >&2
  exit 1
fi

if [[ -z "$REPO" ]]; then
  remote_url="$(git -C "$ROOT_DIR" config --get remote.origin.url || true)"
  REPO="$(echo "$remote_url" | sed -E 's#^https://github.com/##; s#^git@github.com:##; s#\.git$##')"
fi

if [[ -z "$REPO" ]]; then
  echo "Could not infer owner/repo. Pass it explicitly as argument 3." >&2
  exit 1
fi

ref_repo="$REPO"
if [[ -n "$TAG" ]]; then
  ref_repo="$REPO#$TAG"
fi

echo "Install command:"
echo "npx skills add $ref_repo --skill $SKILL -y"
echo
echo "List command:"
echo "npx skills add $ref_repo --list"
