#!/usr/bin/env bash

set -euo pipefail

REPO="${ODGH_REPO:-openclaw/openclaw}"
DRY_RUN="${ODGH_DRY_RUN:-0}"
STYLE_VARIANTS="${ODGH_STYLE_VARIANTS:-1}"

usage() {
  cat <<'EOF'
Usage:
  ./alias.sh [--dry-run] inspect <cluster-ref>
  ./alias.sh [--dry-run] run-cluster <cluster-file>
  ./alias.sh [--dry-run] close-pr-dup <pr-ref> <canonical-pr-ref>
  ./alias.sh [--dry-run] close-issue-dup <issue-ref> <canonical-issue-ref>

Environment:
  ODGH_REPO      GitHub repo (default: openclaw/openclaw)
  ODGH_DRY_RUN   if set to 1, print actions without mutating state
  ODGH_STYLE_VARIANTS if set to 0, use fixed legacy comment texts

Flags:
  --dry-run      preview command intent without mutating GitHub state

Cluster file format (one item per line, use # for comments):
  <type>:<id>|<action>|<target>

Actions:
  inspect               - fetch read-only context (view + checks if PR)
  close-pr-duplicate    - close PR as duplicate of target PR
  close-issue-duplicate - comment + close issue as duplicate of target issue
  noop                  - no action

Examples:
  pr:xxxxx|inspect|
  pr:yyyyy|close-pr-duplicate|xxxxx
  issue:zzzzz|close-issue-duplicate|aaaaa
  issue:bbbbb|noop|
EOF
}

parse_ref() {
  local ref="$1"
  case "$ref" in
    *"/pull/"*)
      ref="${ref##*/pull/}"
      echo "pr:$ref"
      ;;
    *"/issues/"*)
      ref="${ref##*/issues/}"
      echo "issue:$ref"
      ;;
    pr:*|issue:*)
      echo "$ref"
      ;;
    *)
      if [[ "$ref" =~ ^[0-9]+$ ]]; then
        echo "issue:$ref"
      else
        echo "$ref"
      fi
      ;;
  esac
}

gh_pr_view() {
  local id="$1"
  gh pr view "$id" --repo "$REPO" --json number,title,body,state,author,labels,createdAt,updatedAt,mergedAt,closedAt,mergeable,mergeStateStatus,isDraft,changedFiles,additions,deletions,statusCheckRollup,commits,url
}

gh_issue_view() {
  local id="$1"
  gh issue view "$id" --repo "$REPO" --json number,title,body,state,labels,author,createdAt,updatedAt,url,comments
}

gh_pr_checks() {
  local id="$1"
  gh pr checks "$id" --repo "$REPO"
}

gh_pr_files() {
  local id="$1"
  gh pr diff --name-only "$id" --repo "$REPO"
}

variant_index() {
  local key="$1"
  local max="$2"
  local total=0
  local i ch
  for ((i = 0; i < ${#key}; i++)); do
    ch=$(printf '%d' "'${key:i:1}")
    total=$((total + ch))
  done
  echo $((total % max))
}

issue_close_body() {
  local canonical="$1"
  local item_id="$2"
  local idx
  local opener trail
  idx="$(variant_index "${item_id}-${canonical}-issue" 4)"
  case "$idx" in
    0)
      opener='Thanks for the report.'
      trail='I can reroute this if I missed the right cluster alignment.'
      ;;
    1)
      opener='Good catch, thank you.'
      trail='If you see a mismatch, I can reopen this right away.'
      ;;
    2)
      opener='Great call reporting this.'
      trail='Please flag the exact shared failure step if you want me to re-check it now.'
      ;;
    *)
      opener='I appreciate the report.'
      trail='If this is a miss, tell me and I can reopen review right away.'
      ;;
  esac

  cat <<EOF
${opener}

I'm closing this as duplicate of #${canonical}. The same failure pattern and behavior map to the canonical fix path there.

${trail}
EOF
}

pr_close_body() {
  local canonical="$1"
  local item_id="$2"
  local idx
  local opener trail
  idx="$(variant_index "${item_id}-${canonical}-pr" 4)"
  case "$idx" in
    0)
      opener='Thanks for the earlier contribution.'
      trail='Your work is preserved in the canonical attribution trail.'
      ;;
    1)
      opener='Thanks for taking a pass on this.'
      trail='Your contribution is still part of the attribution trail.'
      ;;
    2)
      opener='Thanks for tackling this quickly.'
      trail='Credit is retained in the canonical outcome.'
      ;;
    *)
      opener='Thanks for pushing this forward.'
      trail='Your contribution is preserved with the canonical summary.'
      ;;
  esac

  cat <<EOF
${opener}

I'm going to close this as a duplicate of #${canonical}. Great attempt here, but this PR is stale and a newer, stable PR is handling the same root-cause path.
${trail}

If this is a mistake, tell me and I can reopen review right away.
EOF
}

close_issue_duplicate() {
  local id="$1"
  local canonical="$2"
  local body
  if [[ "$STYLE_VARIANTS" -eq 0 ]]; then
    body=$'Thanks for the report.\n\nI\'m closing this as duplicate of #'"${canonical}"$'.\nThe same failure pattern and behavior map to the canonical fix path there.\n\nIf this is a mistake, tell me and I can reopen review right away.'
  else
    body="$(issue_close_body "$canonical" "$id")"
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'DRY-RUN: gh issue comment %s --repo "%s" --body "%s"\n' "$id" "$REPO" "$body"
    printf 'DRY-RUN: gh issue close %s --repo "%s" --reason not planned\n' "$id" "$REPO"
    return 0
  fi
  gh issue comment "$id" --repo "$REPO" --body "$body"
  gh issue close "$id" --repo "$REPO" --reason not planned
}

close_pr_duplicate() {
  local id="$1"
  local canonical="$2"
  local body
  if [[ "$STYLE_VARIANTS" -eq 0 ]]; then
    body=$'Thanks for the earlier contribution.\n\nI\'m going to close this as a duplicate of #'"${canonical}"$'. Great attempt here, but this PR is stale and a newer, stable PR is handling the same root-cause path.\nYour work is preserved in the canonical attribution trail.\n\nIf this is a mistake, tell me and I can reopen review right away.'
  else
    body="$(pr_close_body "$canonical" "$id")"
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'DRY-RUN: gh pr close %s --repo "%s" --comment "%s"\n' "$id" "$REPO" "$body"
    return 0
  fi
  gh pr close "$id" --repo "$REPO" --comment "$body"
}

inspect_ref() {
  local item="$1"
  local kind="${item%%:*}"
  local id="${item#*:}"

  if [[ "$kind" == "pr" ]]; then
    gh_pr_view "$id"
    gh_pr_files "$id"
    gh_pr_checks "$id"
  else
    gh_issue_view "$id"
  fi
}

run_cluster() {
  local file="$1"
  while IFS='|' read -r item action target; do
    item="$(echo "${item:-}" | sed 's/^ *//;s/ *$//')"
    action="$(echo "${action:-inspect}" | sed 's/^ *//;s/ *$//')"
    target="$(echo "${target:-}" | sed 's/^ *//;s/ *$//')"
    [[ -z "$item" || "${item:0:1}" == "#" ]] && continue

    item="$(parse_ref "$item")"
    local id="${item#*:}"

    case "$action" in
      inspect|"")
        inspect_ref "$item"
        ;;
      close-pr-duplicate)
        if [[ -z "$target" ]]; then
          echo "Skipping ${item}: close-pr-duplicate requires target canonical PR" >&2
          continue
        fi
        close_pr_duplicate "$id" "$target"
        ;;
      close-issue-duplicate)
        if [[ -z "$target" ]]; then
          echo "Skipping ${item}: close-issue-duplicate requires target canonical issue" >&2
          continue
        fi
        close_issue_duplicate "$id" "$target"
        ;;
      noop)
        echo "noop: ${item}"
        ;;
      *)
        echo "Unsupported action '${action}' for '${item}', skipping" >&2
        ;;
    esac
  done < "$file"
}

main() {
  if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=1
    shift
  fi

  case "${1:-}" in
    inspect)
      if [[ -z "${2:-}" ]]; then
        usage
        exit 1
      fi
      inspect_ref "$(parse_ref "$2")"
      ;;
    run-cluster)
      if [[ -z "${2:-}" ]]; then
        usage
        exit 1
      fi
      run_cluster "$2"
      ;;
    close-pr-duplicate|close-pr-dup)
      if [[ -z "${2:-}" || -z "${3:-}" ]]; then
        usage
        exit 1
      fi
      close_pr_duplicate "$2" "$3"
      ;;
    close-issue-duplicate|close-issue-dup)
      if [[ -z "${2:-}" || -z "${3:-}" ]]; then
        usage
        exit 1
      fi
      close_issue_duplicate "$2" "$3"
      ;;
    -h|--help|"")
      usage
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
