import importlib.util
import pathlib
import unittest

SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "skills"
    / "technical-documentation"
    / "scripts"
    / "ste-lint.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("ste_lint", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SteLintTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_selftest_passes(self):
        self.mod.selftest()

    def test_hedges_are_never_flagged(self):
        findings, _ = self.mod.lint("The job may have failed. It could be a timeout.")
        self.assertEqual(findings, [])

    def test_hard_violations_fail_over_baseline(self):
        findings, _ = self.mod.lint("Spin up the job; then reach out.")
        hard = [f for f in findings if f["level"] == "advisory-free"]
        self.assertGreaterEqual(len(hard), 2)

    def test_markdown_syntax_is_not_prose(self):
        doc = "---\ntitle: x; y\n---\n| a; b |\n```\nx; y\n```\nSee [docs](https://a.b/c;d).\n"
        findings, words = self.mod.lint(doc)
        self.assertEqual(findings, [])
        self.assertEqual(words, 2)


if __name__ == "__main__":
    unittest.main()
