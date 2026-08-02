#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("org_branch_cleanup.py")
SPEC = importlib.util.spec_from_file_location("org_branch_cleanup", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def pr(
    state: str,
    *,
    branch: str = "fix/example",
    merged_at: str | None = None,
    closed_at: str | None = None,
) -> dict:
    return {
        "number": 42,
        "state": state,
        "mergedAt": merged_at,
        "closedAt": closed_at,
        "headRefName": branch,
        "headRepository": {"nameWithOwner": "acme/widget"},
        "baseRefName": "main",
        "url": "https://github.com/acme/widget/pull/42",
    }


def record(**overrides: object) -> dict:
    value = {
        "org": "acme",
        "repo": "widget",
        "default": "main",
        "name": "fix/example",
        "protected": False,
        "oid": "abc123",
        "committedAt": "2026-01-01T00:00:00Z",
        "prs": [],
    }
    value.update(overrides)
    return value


class ClassifyBranchTests(unittest.TestCase):
    merged_cutoff = "2026-07-19T00:00:00Z"
    closed_cutoff = "2026-05-04T00:00:00Z"

    def classify(self, value: dict) -> tuple[str, dict | None]:
        return MODULE.classify_branch(
            value,
            self.merged_cutoff,
            self.closed_cutoff,
        )

    def test_old_merged_tip_is_delete_candidate(self) -> None:
        status, candidate = self.classify(
            record(
                prs=[
                    pr(
                        "MERGED",
                        merged_at="2026-06-01T00:00:00Z",
                        closed_at="2026-06-01T00:00:00Z",
                    )
                ]
            )
        )
        self.assertEqual(status, "merged-candidate")
        self.assertEqual(candidate["candidateReason"], "merged")

    def test_recent_merged_tip_is_retained(self) -> None:
        status, candidate = self.classify(
            record(
                prs=[
                    pr(
                        "MERGED",
                        merged_at="2026-07-25T00:00:00Z",
                        closed_at="2026-07-25T00:00:00Z",
                    )
                ]
            )
        )
        self.assertEqual(status, "recent-merged")
        self.assertIsNone(candidate)

    def test_open_pr_wins_over_merged_history(self) -> None:
        status, candidate = self.classify(
            record(
                prs=[
                    pr(
                        "MERGED",
                        merged_at="2026-06-01T00:00:00Z",
                        closed_at="2026-06-01T00:00:00Z",
                    ),
                    pr("OPEN"),
                ]
            )
        )
        self.assertEqual(status, "open-pr")
        self.assertIsNone(candidate)

    def test_old_closed_unmerged_tip_is_review_only(self) -> None:
        status, candidate = self.classify(
            record(prs=[pr("CLOSED", closed_at="2026-04-01T00:00:00Z")])
        )
        self.assertEqual(status, "closed-unmerged-candidate")
        self.assertEqual(candidate["candidateReason"], "closed-unmerged")

    def test_unassociated_old_tip_is_report_only(self) -> None:
        status, candidate = self.classify(record())
        self.assertEqual(status, "stale-unassociated")
        self.assertIsNone(candidate)

    def test_protected_default_and_release_branches_are_retained(self) -> None:
        self.assertEqual(self.classify(record(protected=True))[0], "protected-graphql")
        self.assertEqual(self.classify(record(name="main"))[0], "default")
        self.assertEqual(self.classify(record(name="release/v2"))[0], "reserved")

    def test_fork_pr_does_not_prove_same_repo_branch(self) -> None:
        fork_pr = pr(
            "MERGED",
            merged_at="2026-06-01T00:00:00Z",
            closed_at="2026-06-01T00:00:00Z",
        )
        fork_pr["headRepository"] = {"nameWithOwner": "contributor/widget"}
        status, candidate = self.classify(record(prs=[fork_pr]))
        self.assertEqual(status, "retained")
        self.assertIsNone(candidate)


class UtilityTests(unittest.TestCase):
    def test_default_repo_patterns_exclude_generated_state_repos(self) -> None:
        patterns = MODULE.compile_patterns(MODULE.DEFAULT_REPO_EXCLUDES)
        self.assertTrue(MODULE.matches_any("widget-ghsa-abcd", patterns))
        self.assertTrue(MODULE.matches_any("worker-state", patterns))
        self.assertTrue(MODULE.matches_any("state-archive-2026", patterns))
        self.assertFalse(MODULE.matches_any("widget", patterns))

    def test_branch_encoding_escapes_slashes(self) -> None:
        self.assertEqual(MODULE.encoded_branch("fix/a b"), "fix%2Fa%20b")

    def test_include_pattern_limits_repository_scan(self) -> None:
        reason = MODULE.repo_exclusion_reason(
            {"name": "other", "archived": False, "fork": False},
            False,
            False,
            MODULE.compile_patterns([r"^widget$"]),
            [],
        )
        self.assertEqual(reason, "not-included")

    def test_cutoff_is_utc_and_stable(self) -> None:
        import datetime as dt

        now = dt.datetime(2026, 8, 2, tzinfo=dt.timezone.utc)
        self.assertEqual(MODULE.cutoff_iso(14, now), "2026-07-19T00:00:00Z")

    def test_delete_lost_response_is_confirmed_by_missing_ref(self) -> None:
        failed = subprocess.CompletedProcess(
            ["gh"],
            1,
            stdout="",
            stderr="connection closed",
        )
        with (
            mock.patch.object(MODULE, "gh_call", return_value=failed),
            mock.patch.object(MODULE, "live_branch", return_value=("missing", None)),
        ):
            status, detail = MODULE.delete_ref("gh", "acme", "widget", "fix/example")
        self.assertEqual(status, "delete-confirmed-missing")
        self.assertEqual(detail, "connection closed")

    def test_generic_404_is_not_treated_as_branch_absence(self) -> None:
        result = subprocess.CompletedProcess(
            ["gh"],
            1,
            stdout="",
            stderr="gh: Not Found (HTTP 404)",
        )
        self.assertFalse(MODULE.is_not_found(result))

    def test_apply_requires_clean_audit_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            candidates = Path(temp_dir) / "delete-candidates.jsonl"
            candidates.write_text("", encoding="utf-8")
            with self.assertRaises(SystemExit):
                MODULE.validate_audit_context(candidates, "acme", False, False)

            summary = {
                "org": "acme",
                "counts": {"errors": 1},
            }
            (Path(temp_dir) / "audit-summary.json").write_text(
                __import__("json").dumps(summary),
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit):
                MODULE.validate_audit_context(candidates, "acme", False, False)
            MODULE.validate_audit_context(candidates, "acme", False, True)

    def test_prepare_audit_does_not_create_files_before_live_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "snapshot.jsonl"
            MODULE.prepare_audit_files([target], False)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
