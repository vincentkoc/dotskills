from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/session-done/scripts/session-done"
loader = importlib.machinery.SourceFileLoader("session_done", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
writer = importlib.util.module_from_spec(spec)
loader.exec_module(writer)


class SessionDoneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def run_writer(self, *args: str, env: dict[str, str] | None = None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], cwd=self.root,
            env=env, capture_output=True, text=True, check=False,
        )

    def test_stdout_ignores_legacy_write_configuration(self) -> None:
        env = dict(os.environ, DONE_NOTES_DIR=str(self.root / "notes"),
                   DONE_OBSIDIAN_VAULT=str(self.root / "vault"),
                   DONE_MEMORY_FILE="memory.md")
        for _ in range(2):
            result = self.run_writer("--summary", "Finished", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Summary\n\nFinished", result.stdout)
            self.assertIn("session_id: unknown", result.stdout)
            self.assertEqual(result.stderr, "")
            self.assertEqual(list(self.root.iterdir()), [])

    def test_empty_and_invalid_arguments_never_write(self) -> None:
        for args in [(), ("--summary", "  "), ("--summary",), ("--memory-file", "memory.md")]:
            with self.subTest(args=args):
                result = self.run_writer(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertEqual(list(self.root.iterdir()), [])

    def test_explicit_output_preserves_unicode_and_literal_content(self) -> None:
        content = "Résumé 🦊\n$(touch unwanted) `touch another`"
        output = self.root / "handoff with spaces.md"
        result = self.run_writer("--summary", content, "--session-id", "known-id",
                                 "--branch", "fix/example", "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        text = output.read_text()
        self.assertIn(content, text)
        self.assertIn("session_id: known-id", text)
        self.assertIn("branch: fix/example", text)
        self.assertNotIn("## Flashcards", text)
        self.assertEqual(list(self.root.iterdir()), [output])
        if os.name == "posix":
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_existing_note_is_never_overwritten(self) -> None:
        output = self.root / "handoff.md"
        output.write_bytes(b"keep original")
        result = self.run_writer("--summary", "New", "--output", str(output))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(output.read_bytes(), b"keep original")
        self.assertEqual(list(self.root.iterdir()), [output])

    def test_symlink_destination_is_never_followed(self) -> None:
        target = self.root / "original.md"
        target.write_text("keep original")
        output = self.root / "handoff.md"
        output.symlink_to(target)
        result = self.run_writer("--summary", "New", "--output", str(output))
        self.assertEqual(result.returncode, 1)
        self.assertTrue(output.is_symlink())
        self.assertEqual(target.read_text(), "keep original")
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_missing_parent_is_not_created(self) -> None:
        result = self.run_writer("--summary", "New", "--output", "missing/handoff.md")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_write_or_publication_failure_leaves_no_partial_note(self) -> None:
        for operation in ["fsync", "link"]:
            with self.subTest(operation=operation):
                with patch.object(writer.os, operation, side_effect=OSError("injected failure")):
                    with self.assertRaisesRegex(OSError, "injected failure"):
                        writer.retain(self.root / "handoff.md", "complete handoff")
                self.assertEqual(list(self.root.iterdir()), [])

    def test_concurrent_same_destination_has_one_complete_winner(self) -> None:
        output = self.root / "handoff.md"
        def write(summary: str):
            return self.run_writer("--summary", summary, "--output", str(output))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, ["First", "Second"]))
        self.assertEqual(sorted(r.returncode for r in results), [0, 1])
        text = output.read_text()
        self.assertTrue(text.endswith("\nFirst\n") or text.endswith("\nSecond\n"))
        self.assertEqual(text.count("# Session handoff"), 1)
        self.assertEqual(list(self.root.iterdir()), [output])


if __name__ == "__main__":
    unittest.main()
