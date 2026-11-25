from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/x-release-post/scripts/x-post-length"
loader = importlib.machinery.SourceFileLoader("x_post_length", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
counter = importlib.util.module_from_spec(spec)
loader.exec_module(counter)


class XPostLengthTests(unittest.TestCase):
    def run_counter(self, draft: str, *args: str):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], input=draft,
            capture_output=True, text=True, check=False,
        )

    def test_weights_follow_x_rules(self) -> None:
        self.assertEqual(counter.post_weight("abc\n"), 4)
        self.assertEqual(counter.post_weight("tokenjuice 🧃"), 13)
        self.assertEqual(counter.post_weight("⚙️"), 2)
        self.assertEqual(counter.post_weight("👩‍💻"), 2)
        self.assertEqual(counter.post_weight("中文"), 4)
        self.assertEqual(counter.post_weight("Get it https://github.com/vincentkoc/tokenjuice"), 30)

    def test_real_release_post_fits(self) -> None:
        post = (
            "tokenjuice beta (v0.4) is out! 🧃\n\n"
            "🥧 Native pi and Claude extensions\n"
            "🚪 Escape hatch for harnesses when failing\n"
            "🐧 Linux binaries\n"
            "😃 Unicode emoji and CJK support\n"
            "⚙️ Improved rules for npm, yarn, bun and pnpm\n\n"
            "Grab here: https://github.com/vincentkoc/tokenjuice"
        )
        self.assertEqual(counter.post_weight(post), 245)

    def test_thread_reports_each_post_and_fails_when_over(self) -> None:
        result = self.run_counter("first post\n---\n" + "x" * 281 + "\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "post 1: 10/280 ok\npost 2: 281/280 OVER\n")

        result = self.run_counter("x" * 281, "--limit", "25000")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_empty_draft_and_file_input(self) -> None:
        self.assertEqual(self.run_counter("\n---\n").returncode, 2)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8") as draft:
            draft.write("hello")
            draft.flush()
            result = subprocess.run(
                [sys.executable, str(SCRIPT), draft.name],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.stdout, "post 1: 5/280 ok\n")


if __name__ == "__main__":
    unittest.main()
