#!/usr/bin/env python3
"""Audit and safely remove stale GitHub organization branches."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Iterable, Sequence


DEFAULT_REPO_EXCLUDES = (
    r"(?i)(?:^|[-_.])ghsa(?:$|[-_.])",
    r"(?i)(?:^|[-_.])state(?:$|[-_.])",
    r"(?i)archive",
)
DEFAULT_RESERVED_BRANCHES = (
    r"(?i)^(main|master|develop|development|dev|staging|production|prod|next|stable|latest)$",
    r"(?i)^(gh-pages|pages|docs)$",
    r"(?i)^(release|releases)(/|-|$)",
    r"(?i)^v[0-9]+(?:[./-]|$)",
)
GRAPHQL_QUERY = r"""
query(
  $owner: String!
  $name: String!
  $endCursor: String
  $pageSize: Int!
  $prLimit: Int!
) {
  repository(owner: $owner, name: $name) {
    name
    defaultBranchRef { name }
    refs(
      refPrefix: "refs/heads/"
      first: $pageSize
      after: $endCursor
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        branchProtectionRule { pattern }
        target {
          ... on Commit {
            oid
            committedDate
            associatedPullRequests(first: $prLimit) {
              nodes {
                number
                state
                mergedAt
                closedAt
                headRefName
                headRepository { nameWithOwner }
                baseRefName
                url
              }
            }
          }
        }
      }
    }
  }
}
"""
GRAPHQL_JQ = (
    ".data.repository as $r | $r.refs.nodes[] | "
    "{repo:$r.name,default:($r.defaultBranchRef.name // null),name:.name,"
    "protected:(.branchProtectionRule != null),"
    "protectionPattern:(.branchProtectionRule.pattern // null),"
    "oid:(.target.oid // null),committedAt:(.target.committedDate // null),"
    "prs:(.target.associatedPullRequests.nodes // [])} | @json"
)


class GhError(RuntimeError):
    def __init__(self, args: Sequence[str], result: subprocess.CompletedProcess[str]):
        self.args_run = list(args)
        self.result = result
        message = result.stderr.strip() or result.stdout.strip() or "unknown gh error"
        super().__init__(message)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def cutoff_iso(days: int, now: dt.datetime | None = None) -> str:
    anchor = now or utc_now()
    return iso_utc(anchor - dt.timedelta(days=days))


def compile_patterns(patterns: Iterable[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def matches_any(value: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(pattern.search(value) for pattern in patterns)


def branch_is_reserved(
    branch: str, extra_patterns: Sequence[re.Pattern[str]] = ()
) -> bool:
    patterns = compile_patterns(DEFAULT_RESERVED_BRANCHES)
    return matches_any(branch, [*patterns, *extra_patterns])


def same_repo_head(pr: dict[str, Any], record: dict[str, Any]) -> bool:
    head_repo = (pr.get("headRepository") or {}).get("nameWithOwner")
    expected_repo = f"{record['org']}/{record['repo']}"
    return pr.get("headRefName") == record.get("name") and head_repo == expected_repo


def classify_branch(
    record: dict[str, Any],
    merged_cutoff: str,
    closed_cutoff: str,
    extra_branch_patterns: Sequence[re.Pattern[str]] = (),
) -> tuple[str, dict[str, Any] | None]:
    branch = str(record.get("name") or "")
    if not branch or not record.get("oid"):
        return "invalid-tip", None
    if branch == record.get("default"):
        return "default", None
    if record.get("protected"):
        return "protected-graphql", None
    if branch_is_reserved(branch, extra_branch_patterns):
        return "reserved", None

    prs = [pr for pr in record.get("prs", []) if isinstance(pr, dict)]
    matching = [pr for pr in prs if same_repo_head(pr, record)]
    if any(pr.get("state") == "OPEN" for pr in matching):
        return "open-pr", None

    merged = [
        pr
        for pr in matching
        if pr.get("state") == "MERGED" and pr.get("mergedAt")
    ]
    if merged:
        evidence = max(merged, key=lambda pr: str(pr["mergedAt"]))
        if str(evidence["mergedAt"]) < merged_cutoff:
            candidate = dict(record)
            candidate["candidateReason"] = "merged"
            candidate["evidencePr"] = evidence
            return "merged-candidate", candidate
        return "recent-merged", None

    closed = [
        pr
        for pr in matching
        if pr.get("state") == "CLOSED"
        and not pr.get("mergedAt")
        and pr.get("closedAt")
    ]
    old_closed = [pr for pr in closed if str(pr["closedAt"]) < closed_cutoff]
    if old_closed:
        evidence = max(old_closed, key=lambda pr: str(pr["closedAt"]))
        candidate = dict(record)
        candidate["candidateReason"] = "closed-unmerged"
        candidate["evidencePr"] = evidence
        return "closed-unmerged-candidate", candidate

    committed_at = record.get("committedAt")
    if not prs and committed_at and str(committed_at) < closed_cutoff:
        return "stale-unassociated", None
    return "retained", None


def gh_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "NO_COLOR": "1",
            "CLICOLOR": "0",
            "CLICOLOR_FORCE": "0",
            "GH_FORCE_TTY": "0",
            "GH_PAGER": "cat",
        }
    )
    return env


def gh_call(
    gh_bin: str,
    args: Sequence[str],
    retries: int = 3,
    retry_delay: float = 1.0,
) -> subprocess.CompletedProcess[str]:
    last: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, retries + 1):
        last = subprocess.run(
            [gh_bin, *args],
            capture_output=True,
            text=True,
            env=gh_env(),
            check=False,
        )
        if last.returncode == 0:
            return last
        if attempt < retries:
            time.sleep(retry_delay * attempt)
    assert last is not None
    return last


def gh_output(gh_bin: str, args: Sequence[str], retries: int = 3) -> str:
    result = gh_call(gh_bin, args, retries=retries)
    if result.returncode != 0:
        raise GhError(args, result)
    return result.stdout


def parse_json_lines(payload: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in payload.splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        json.dump(record, handle, sort_keys=True)
        handle.write("\n")


def append_tsv(path: Path, *fields: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            "\t".join(
                str(field).replace("\t", " ").replace("\r", " ").replace("\n", " ")
                for field in fields
            )
        )
        handle.write("\n")


def reset_files(paths: Iterable[Path]) -> None:
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")


def prepare_audit_files(paths: Sequence[Path], overwrite: bool) -> None:
    existing = [path for path in paths if path.exists() and path.stat().st_size > 0]
    if existing and not overwrite:
        joined = ", ".join(str(path) for path in existing)
        raise SystemExit(
            f"audit output already exists: {joined}; choose a new directory or pass "
            "--overwrite"
        )


def list_org_repositories(gh_bin: str, org: str) -> list[dict[str, Any]]:
    payload = gh_output(
        gh_bin,
        [
            "api",
            "--paginate",
            f"orgs/{org}/repos?per_page=100&type=all",
            "--jq",
            ".[] | @json",
        ],
    )
    return parse_json_lines(payload)


def query_repository_branches(
    gh_bin: str,
    org: str,
    repo: str,
    page_size: int,
    pr_limit: int,
) -> list[dict[str, Any]]:
    payload = gh_output(
        gh_bin,
        [
            "api",
            "graphql",
            "--paginate",
            "-f",
            f"query={GRAPHQL_QUERY}",
            "-F",
            f"owner={org}",
            "-F",
            f"name={repo}",
            "-F",
            f"pageSize={page_size}",
            "-F",
            f"prLimit={pr_limit}",
            "--jq",
            GRAPHQL_JQ,
        ],
    )
    records = parse_json_lines(payload)
    for record in records:
        record["org"] = org
    return records


def repo_exclusion_reason(
    repo: dict[str, Any],
    include_archived: bool,
    include_forks: bool,
    include_patterns: Sequence[re.Pattern[str]],
    patterns: Sequence[re.Pattern[str]],
) -> str | None:
    if repo.get("archived") and not include_archived:
        return "archived"
    if repo.get("fork") and not include_forks:
        return "fork"
    name = str(repo.get("name") or "")
    if include_patterns and not matches_any(name, include_patterns):
        return "not-included"
    if matches_any(name, patterns):
        return "repo-pattern"
    return None


def run_audit(args: argparse.Namespace) -> int:
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    snapshot = output / "snapshot.jsonl"
    candidates = output / "delete-candidates.jsonl"
    closed = output / "closed-unmerged-review.jsonl"
    stale = output / "stale-unassociated.tsv"
    repos_log = output / "repositories.tsv"
    errors = output / "audit-errors.tsv"
    summary_path = output / "audit-summary.json"
    prepare_audit_files(
        [snapshot, candidates, closed, stale, repos_log, errors, summary_path],
        args.overwrite,
    )

    merged_cutoff = cutoff_iso(args.merged_retention_days)
    closed_cutoff = cutoff_iso(args.closed_retention_days)
    repo_patterns = [] if args.no_default_repo_excludes else list(DEFAULT_REPO_EXCLUDES)
    repo_patterns.extend(args.exclude_repo_regex)
    compiled_repo_patterns = compile_patterns(repo_patterns)
    compiled_include_patterns = compile_patterns(args.include_repo_regex)
    compiled_branch_patterns = compile_patterns(args.exclude_branch_regex)

    print(f"listing repositories for {args.org}")
    repositories = list_org_repositories(args.gh_bin, args.org)
    reset_files([snapshot, candidates, closed, stale, repos_log, errors, summary_path])
    counts: dict[str, int] = {
        "repositories": len(repositories),
        "repositories_scanned": 0,
        "repositories_excluded": 0,
        "branches": 0,
        "merged_candidates": 0,
        "closed_unmerged_review": 0,
        "stale_unassociated": 0,
        "errors": 0,
    }

    for index, repo in enumerate(repositories, start=1):
        name = str(repo.get("name") or "")
        exclusion = repo_exclusion_reason(
            repo,
            args.include_archived,
            args.include_forks,
            compiled_include_patterns,
            compiled_repo_patterns,
        )
        if exclusion:
            counts["repositories_excluded"] += 1
            append_tsv(repos_log, name, "excluded", exclusion)
            continue

        print(f"[{index}/{len(repositories)}] {name}", flush=True)
        try:
            records = query_repository_branches(
                args.gh_bin,
                args.org,
                name,
                args.page_size,
                args.pr_limit,
            )
        except (GhError, json.JSONDecodeError) as exc:
            counts["errors"] += 1
            append_tsv(errors, name, type(exc).__name__, str(exc))
            append_tsv(repos_log, name, "error", type(exc).__name__)
            continue

        counts["repositories_scanned"] += 1
        append_tsv(repos_log, name, "scanned", len(records))
        for record in records:
            counts["branches"] += 1
            append_jsonl(snapshot, record)
            classification, candidate = classify_branch(
                record,
                merged_cutoff,
                closed_cutoff,
                compiled_branch_patterns,
            )
            if classification == "merged-candidate" and candidate:
                counts["merged_candidates"] += 1
                append_jsonl(candidates, candidate)
            elif classification == "closed-unmerged-candidate" and candidate:
                counts["closed_unmerged_review"] += 1
                append_jsonl(closed, candidate)
            elif classification == "stale-unassociated":
                counts["stale_unassociated"] += 1
                append_tsv(
                    stale,
                    record["repo"],
                    record["name"],
                    record.get("oid") or "",
                    record.get("committedAt") or "",
                )

    summary = {
        "org": args.org,
        "generatedAt": iso_utc(utc_now()),
        "mergedRetentionDays": args.merged_retention_days,
        "mergedCutoff": merged_cutoff,
        "closedRetentionDays": args.closed_retention_days,
        "closedCutoff": closed_cutoff,
        "defaultRepoExcludesEnabled": not args.no_default_repo_excludes,
        "counts": counts,
        "files": {
            "snapshot": str(snapshot),
            "deleteCandidates": str(candidates),
            "closedUnmergedReview": str(closed),
            "staleUnassociated": str(stale),
            "repositories": str(repos_log),
            "errors": str(errors),
        },
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary["counts"], sort_keys=True))
    if counts["errors"] and not args.allow_partial:
        print(
            f"audit incomplete: {counts['errors']} repositories failed; see {errors}",
            file=sys.stderr,
        )
        return 2
    return 0


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return parse_json_lines(path.read_text(encoding="utf-8"))


def load_deleted_keys(path: Path) -> set[tuple[str, str, str]]:
    if not path.exists():
        return set()
    keys: set[tuple[str, str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 3:
            keys.add((fields[0], fields[1], fields[2]))
    return keys


def encoded_branch(branch: str) -> str:
    return urllib.parse.quote(branch, safe="")


def is_not_found(result: subprocess.CompletedProcess[str]) -> bool:
    text = f"{result.stderr}\n{result.stdout}".lower()
    return "branch not found" in text


def live_branch(
    gh_bin: str, org: str, repo: str, branch: str
) -> tuple[str, dict[str, Any] | None]:
    result = gh_call(
        gh_bin,
        ["api", f"repos/{org}/{repo}/branches/{encoded_branch(branch)}"],
    )
    if result.returncode != 0:
        return ("missing", None) if is_not_found(result) else ("error", None)
    return "present", json.loads(result.stdout)


def open_pr_count(gh_bin: str, org: str, repo: str, branch: str) -> int:
    payload = gh_output(
        gh_bin,
        [
            "api",
            "-X",
            "GET",
            f"repos/{org}/{repo}/pulls",
            "-f",
            "state=open",
            "-f",
            f"head={org}:{branch}",
            "-f",
            "per_page=1",
            "--jq",
            "length",
        ],
    )
    return int(payload.strip())


def core_rate_remaining(gh_bin: str) -> int:
    payload = gh_output(
        gh_bin,
        ["api", "rate_limit", "--jq", ".resources.core.remaining"],
    )
    return int(payload.strip())


def delete_ref(
    gh_bin: str, org: str, repo: str, branch: str
) -> tuple[str, str]:
    result = gh_call(
        gh_bin,
        [
            "api",
            "-X",
            "DELETE",
            f"repos/{org}/{repo}/git/refs/heads/{encoded_branch(branch)}",
        ],
    )
    if result.returncode == 0:
        return "deleted", ""

    status, _ = live_branch(gh_bin, org, repo, branch)
    if status == "missing":
        return "delete-confirmed-missing", result.stderr.strip()
    return "delete-failed", result.stderr.strip()


def verify_ledger(gh_bin: str, ledger: Path, output: Path) -> dict[str, int]:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("", encoding="utf-8")
    counts = {"absent": 0, "present": 0, "error": 0}
    if not ledger.exists():
        return counts

    for line in ledger.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) < 3:
            continue
        org, repo, branch = fields[:3]
        status, payload = live_branch(gh_bin, org, repo, branch)
        if status == "missing":
            counts["absent"] += 1
            append_tsv(output, "absent", org, repo, branch)
        elif status == "present":
            counts["present"] += 1
            append_tsv(
                output,
                "present",
                org,
                repo,
                branch,
                (payload or {}).get("commit", {}).get("sha", ""),
            )
        else:
            counts["error"] += 1
            append_tsv(output, "error", org, repo, branch)
    return counts


def validate_audit_context(
    candidates_path: Path,
    confirm_org: str,
    allow_unverified_candidates: bool,
    allow_partial_audit: bool,
) -> None:
    summary_path = candidates_path.parent / "audit-summary.json"
    if not summary_path.is_file():
        if allow_unverified_candidates:
            return
        raise SystemExit(
            f"missing sibling audit summary: {summary_path}; use the original audit "
            "directory or pass --allow-unverified-candidates"
        )

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid audit summary {summary_path}: {exc}") from exc
    if summary.get("org") != confirm_org:
        raise SystemExit(
            f"audit org {summary.get('org')!r} does not match "
            f"--confirm-org {confirm_org!r}"
        )
    errors = int((summary.get("counts") or {}).get("errors") or 0)
    if errors and not allow_partial_audit:
        raise SystemExit(
            f"audit summary reports {errors} repository errors; rerun the audit or "
            "pass --allow-partial-audit"
        )


def run_apply(args: argparse.Namespace) -> int:
    candidates_path = Path(args.candidates).expanduser().resolve()
    validate_audit_context(
        candidates_path,
        args.confirm_org,
        args.allow_unverified_candidates,
        args.allow_partial_audit,
    )
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    deleted = output / "deleted.tsv"
    skipped = output / "skipped.tsv"
    verification = output / "verification.tsv"
    if not deleted.exists():
        deleted.write_text("", encoding="utf-8")
    if not skipped.exists():
        skipped.write_text("", encoding="utf-8")

    candidates = read_jsonl(candidates_path)
    for candidate in candidates:
        if candidate.get("org") != args.confirm_org:
            raise SystemExit(
                f"candidate org {candidate.get('org')!r} does not match "
                f"--confirm-org {args.confirm_org!r}"
            )
        reason = candidate.get("candidateReason")
        if reason not in {"merged", "closed-unmerged"}:
            raise SystemExit(f"unsupported candidate reason: {reason!r}")
        if reason == "closed-unmerged" and not args.allow_closed_unmerged:
            raise SystemExit(
                "closed-unmerged candidates require --allow-closed-unmerged"
            )

    already_deleted = load_deleted_keys(deleted)
    pending = [
        candidate
        for candidate in candidates
        if (
            str(candidate["org"]),
            str(candidate["repo"]),
            str(candidate["name"]),
        )
        not in already_deleted
    ]
    required_calls = len(pending) * 4 + len(already_deleted) + 100
    remaining = core_rate_remaining(args.gh_bin)
    if remaining < required_calls and not args.ignore_rate_limit:
        raise SystemExit(
            f"insufficient GitHub core rate limit: remaining={remaining}, "
            f"estimated_required={required_calls}; wait for reset or pass "
            "--ignore-rate-limit"
        )

    deleted_this_run = 0
    skipped_this_run = 0
    for index, candidate in enumerate(pending, start=1):
        org = str(candidate["org"])
        repo = str(candidate["repo"])
        branch = str(candidate["name"])
        expected_sha = str(candidate["oid"])
        status, branch_payload = live_branch(args.gh_bin, org, repo, branch)
        if status != "present":
            skipped_this_run += 1
            append_tsv(skipped, status, org, repo, branch)
            continue

        current_sha = str((branch_payload or {}).get("commit", {}).get("sha") or "")
        if current_sha != expected_sha:
            skipped_this_run += 1
            append_tsv(
                skipped,
                "moved",
                org,
                repo,
                branch,
                expected_sha,
                current_sha,
            )
            continue
        if bool((branch_payload or {}).get("protected")):
            skipped_this_run += 1
            append_tsv(skipped, "protected", org, repo, branch)
            continue

        try:
            open_count = open_pr_count(args.gh_bin, org, repo, branch)
        except GhError as exc:
            skipped_this_run += 1
            append_tsv(skipped, "pr-check-failed", org, repo, branch, str(exc))
            continue
        if open_count:
            skipped_this_run += 1
            append_tsv(skipped, "open-pr", org, repo, branch)
            continue

        delete_status, delete_detail = delete_ref(
            args.gh_bin,
            org,
            repo,
            branch,
        )
        if delete_status == "delete-failed":
            skipped_this_run += 1
            append_tsv(
                skipped,
                delete_status,
                org,
                repo,
                branch,
                delete_detail,
            )
            continue

        deleted_this_run += 1
        evidence = candidate.get("evidencePr") or {}
        append_tsv(
            deleted,
            org,
            repo,
            branch,
            expected_sha,
            candidate.get("candidateReason") or "",
            evidence.get("url") or "",
            iso_utc(utc_now()),
            delete_status,
        )
        if index % args.progress_every == 0:
            print(
                f"processed={index}/{len(pending)} "
                f"deleted={deleted_this_run} skipped={skipped_this_run}",
                flush=True,
            )

    verify_counts = verify_ledger(args.gh_bin, deleted, verification)
    summary = {
        "org": args.confirm_org,
        "completedAt": iso_utc(utc_now()),
        "candidates": len(candidates),
        "alreadyDeleted": len(already_deleted),
        "pending": len(pending),
        "deletedThisRun": deleted_this_run,
        "skippedThisRun": skipped_this_run,
        "verification": verify_counts,
    }
    (output / "apply-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0 if verify_counts["present"] == 0 and verify_counts["error"] == 0 else 3


def run_verify(args: argparse.Namespace) -> int:
    ledger = Path(args.ledger).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    counts = verify_ledger(args.gh_bin, ledger, output)
    print(json.dumps(counts, sort_keys=True))
    return 0 if counts["present"] == 0 and counts["error"] == 0 else 3


def add_gh_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--gh-bin",
        default=os.environ.get("ORG_BRANCH_CLEANUP_GH", "gh"),
        help="GitHub CLI executable (default: gh)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit and safely remove stale GitHub organization branches."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Create a read-only branch snapshot")
    audit.add_argument("--org", required=True, help="GitHub organization login")
    audit.add_argument("--output", required=True, help="Audit output directory")
    audit.add_argument("--merged-retention-days", type=int, default=14)
    audit.add_argument("--closed-retention-days", type=int, default=90)
    audit.add_argument("--include-repo-regex", action="append", default=[])
    audit.add_argument("--exclude-repo-regex", action="append", default=[])
    audit.add_argument("--exclude-branch-regex", action="append", default=[])
    audit.add_argument("--no-default-repo-excludes", action="store_true")
    audit.add_argument("--include-archived", action="store_true")
    audit.add_argument("--include-forks", action="store_true")
    audit.add_argument("--overwrite", action="store_true")
    audit.add_argument("--page-size", type=int, default=50, choices=range(1, 101))
    audit.add_argument("--pr-limit", type=int, default=10, choices=range(1, 21))
    audit.add_argument("--allow-partial", action="store_true")
    add_gh_argument(audit)
    audit.set_defaults(func=run_audit)

    apply_cmd = subparsers.add_parser(
        "apply", help="Revalidate and delete an audit candidate set"
    )
    apply_cmd.add_argument("--candidates", required=True)
    apply_cmd.add_argument("--confirm-org", required=True)
    apply_cmd.add_argument("--output", required=True)
    apply_cmd.add_argument("--allow-closed-unmerged", action="store_true")
    apply_cmd.add_argument("--allow-unverified-candidates", action="store_true")
    apply_cmd.add_argument("--allow-partial-audit", action="store_true")
    apply_cmd.add_argument("--ignore-rate-limit", action="store_true")
    apply_cmd.add_argument("--progress-every", type=int, default=25)
    add_gh_argument(apply_cmd)
    apply_cmd.set_defaults(func=run_apply)

    verify = subparsers.add_parser("verify", help="Verify every deleted ref is absent")
    verify.add_argument("--ledger", required=True)
    verify.add_argument("--output", required=True)
    add_gh_argument(verify)
    verify.set_defaults(func=run_verify)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "progress_every", 1) < 1:
        parser.error("--progress-every must be >= 1")
    try:
        return int(args.func(args))
    except GhError as exc:
        print(f"GitHub CLI error: {exc}", file=sys.stderr)
        return 4
    except (json.JSONDecodeError, OSError, re.error, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
