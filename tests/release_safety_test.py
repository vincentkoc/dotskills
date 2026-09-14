from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(
    *args: str,
    cwd: pathlib.Path,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        env=env,
        capture_output=True,
        text=True,
    )


class ReleaseSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.temporary.name) / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        (self.repo / ".claude-plugin").mkdir()
        (self.repo / "releases").mkdir()
        shutil.copy2(ROOT / "Makefile", self.repo / "Makefile")
        shutil.copy2(
            ROOT / "scripts" / "check_generated.sh",
            self.repo / "scripts" / "check_generated.sh",
        )
        (self.repo / ".claude-plugin" / "marketplace.json").write_text("{}\n")
        (self.repo / "releases" / "skills.json").write_text("{}\n")
        run("git", "init", "-q", "-b", "main", str(self.repo), cwd=self.repo.parent)
        run("git", "config", "user.name", "Test User", cwd=self.repo)
        run("git", "config", "user.email", "test@example.test", cwd=self.repo)
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-qm", "test: fixture", cwd=self.repo)
        self.fake_make = self.repo.parent / "fake-make"
        self.fake_make.write_text(
            """#!/bin/sh
set -eu
case "${FAKE_MAKE_ACTION:-pass}" in
  pass) ;;
  dirty) printf 'changed\\n' >> releases/skills.json ;;
  move-head) git commit --allow-empty -qm 'test: move head' ;;
  *) exit 64 ;;
esac
"""
        )
        self.fake_make.chmod(0o755)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def release(
        self,
        version: str,
        *,
        action: str = "pass",
    ) -> subprocess.CompletedProcess[str]:
        environment = {**os.environ, "FAKE_MAKE_ACTION": action}
        return run(
            "make",
            f"MAKE={self.fake_make}",
            "release",
            f"VERSION={version}",
            cwd=self.repo,
            check=False,
            env=environment,
        )

    def test_release_rejects_staged_and_untracked_content(self) -> None:
        tracked = self.repo / "releases" / "skills.json"
        tracked.write_text('{"changed": true}\n')
        run("git", "add", str(tracked), cwd=self.repo)
        staged = self.release("v-staged")
        self.assertNotEqual(staged.returncode, 0)
        self.assertIn("exactly match HEAD", staged.stderr)
        self.assertNotIn("v-staged", run("git", "tag", cwd=self.repo).stdout)

        run("git", "reset", "-q", "HEAD", str(tracked), cwd=self.repo)
        run("git", "checkout", "-q", "--", str(tracked), cwd=self.repo)
        (self.repo / "untracked.txt").write_text("untracked\n")
        untracked = self.release("v-untracked")
        self.assertNotEqual(untracked.returncode, 0)
        self.assertIn("?? untracked.txt", untracked.stderr)

    def test_release_tags_the_frozen_clean_head(self) -> None:
        expected = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        result = self.release("v-clean")
        self.assertEqual(result.returncode, 0, result.stderr)
        tagged = run("git", "rev-parse", "v-clean^{}", cwd=self.repo).stdout.strip()
        self.assertEqual(tagged, expected)

    def test_release_rejects_ci_drift_and_head_movement(self) -> None:
        dirty = self.release("v-dirty", action="dirty")
        self.assertNotEqual(dirty.returncode, 0)
        self.assertIn("changed the index or working tree", dirty.stderr)
        run(
            "git",
            "checkout",
            "-q",
            "--",
            "releases/skills.json",
            cwd=self.repo,
        )

        moved = self.release("v-moved", action="move-head")
        self.assertNotEqual(moved.returncode, 0)
        self.assertIn("HEAD changed during release checks", moved.stderr)
        self.assertNotIn("v-moved", run("git", "tag", cwd=self.repo).stdout)

    def test_generated_check_allows_staged_contributions_only(self) -> None:
        marketplace = self.repo / ".claude-plugin" / "marketplace.json"
        releases = self.repo / "releases" / "skills.json"
        marketplace.write_text('{"staged": true}\n')
        releases.write_text('{"staged": true}\n')
        run("git", "add", str(marketplace), str(releases), cwd=self.repo)

        staged = run(
            str(self.repo / "scripts" / "check_generated.sh"),
            cwd=self.repo,
            check=False,
        )
        self.assertEqual(staged.returncode, 0, staged.stderr)
        self.assertIn("staged updates are allowed", staged.stdout)

        releases.write_text('{"later": "drift"}\n')
        drift = run(
            str(self.repo / "scripts" / "check_generated.sh"),
            cwd=self.repo,
            check=False,
        )
        self.assertNotEqual(drift.returncode, 0)
        self.assertIn("differ from the staged versions", drift.stderr)


if __name__ == "__main__":
    unittest.main()
