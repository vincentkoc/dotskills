from __future__ import annotations

import json
import os
import pathlib
import shlex
import subprocess
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills/openclaw-github-dedupe/scripts/alias.sh"


class DedupeAliasTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.calls = self.root / "calls.jsonl"
        gh = self.root / "gh"
        gh.write_text("""#!/usr/bin/env python3
import json
import os
import sys
with open(os.environ["GH_CALLS"], "a") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:3] == ["issue", "close"]:
    if sys.argv[4:] != ["--repo", "example/project", "--reason", "not planned"]:
        sys.exit(2)
sys.exit(7 if os.environ.get("GH_FAIL") == sys.argv[2] else 0)
""")
        gh.chmod(0o755)
        self.environment = {
            **os.environ,
            "PATH": f"{self.root}{os.pathsep}{os.environ['PATH']}",
            "GH_CALLS": str(self.calls),
            "ODGH_REPO": "example/project",
            "ODGH_STYLE_VARIANTS": "0",
            "ODGH_DRY_RUN": "0",
            "GH_FAIL": "",
        }

    def run_alias(self, *arguments):
        return subprocess.run(
            ["/bin/bash", str(SCRIPT), *arguments], env=self.environment,
            capture_output=True, text=True,
        )

    def recorded_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_issue_close_passes_one_reason_argument_after_comment(self):
        result = self.run_alias("close-issue-dup", "12", "34")
        self.assertEqual(result.returncode, 0, result.stderr)
        comment, close = self.recorded_calls()
        self.assertEqual(comment[:6], ["issue", "comment", "12", "--repo", "example/project", "--body"])
        self.assertIn("#34", comment[6])
        self.assertEqual(close, ["issue", "close", "12", "--repo", "example/project", "--reason", "not planned"])

    def test_comment_failure_stops_before_close(self):
        self.environment["GH_FAIL"] = "comment"
        result = self.run_alias("close-issue-dup", "12", "34")
        self.assertEqual(result.returncode, 7)
        self.assertEqual([call[:2] for call in self.recorded_calls()], [["issue", "comment"]])

    def test_dry_run_preserves_reason_argument_without_calling_gh(self):
        result = self.run_alias("--dry-run", "close-issue-dup", "12", "34")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.calls.exists())
        close = shlex.split(result.stdout.split("DRY-RUN: ")[-1])
        self.assertEqual(close, ["gh", "issue", "close", "12", "--repo", "example/project", "--reason", "not planned"])


if __name__ == "__main__":
    unittest.main()
