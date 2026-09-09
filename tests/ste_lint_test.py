import contextlib
import errno
import importlib.util
import io
import json
import pathlib
import unittest
from unittest import mock

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

    def test_multiline_comments_preserve_visible_text_and_line_numbers(self):
        doc = "Plain text. <!--\nSpin up the seamless job;\n--> Visible text;\n"
        findings, words = self.mod.lint(doc)
        self.assertEqual([(f["rule"], f["line"]) for f in findings], [("semicolon", 3)])
        self.assertEqual(words, 4)

    def test_same_line_comments_and_inline_code_literals(self):
        doc = "Before <!-- seamless; --> after.\nUse `<!--` and ``<!-- ` -->`` here.\nVisible text;\n"
        findings, words = self.mod.lint(doc)
        self.assertEqual([(f["rule"], f["line"]) for f in findings], [("semicolon", 3)])
        self.assertEqual(words, 7)

    def test_comment_markers_in_fences_do_not_hide_following_prose(self):
        for opening in ("```html", "```html <!--"):
            with self.subTest(opening=opening):
                doc = f"{opening}\n<!--\n```\nVisible text;\n"
                findings, words = self.mod.lint(doc)
                self.assertEqual([(f["rule"], f["line"]) for f in findings], [("semicolon", 4)])
                self.assertEqual(words, 2)

    def test_fences_and_backticks_inside_comments_do_not_hide_visible_text(self):
        doc = "<!--\n```\nseamless;\n```\n`--> Visible text;\n"
        findings, words = self.mod.lint(doc)
        self.assertEqual([(f["rule"], f["line"]) for f in findings], [("semicolon", 5)])
        self.assertEqual(words, 2)

    def run_main(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = self.mod.main(args)
        return status, stdout.getvalue(), stderr.getvalue()

    def assert_incomplete_input(self, args, missing_path, readable_files=0):
        for output in ([], ["--json"], ["--summary"], ["--summary", "--json"]):
            for mode in ("strict", "flavored"):
                for baseline in ("0", "999"):
                    with self.subTest(args=args, output=output, mode=mode, baseline=baseline):
                        status, stdout, stderr = self.run_main([
                            *output, "--mode", mode, "--baseline", baseline, *args,
                        ])
                        self.assertEqual(status, 2)
                        self.assertIn(missing_path, stderr)
                        self.assertIn("cannot read", stderr)
                        if "--json" in output:
                            result = json.loads(stdout)
                            self.assertEqual(result["hard_count"], 0)
                            if "--summary" in output:
                                self.assertEqual(result["file_count"], readable_files)
                            else:
                                self.assertEqual(result["words"], readable_files * 2)
                        else:
                            self.assertIn("0 hard", stdout)

    def test_missing_unreadable_and_mixed_inputs_fail_in_every_output_mode(self):
        for error_type, code in (
            (FileNotFoundError, errno.ENOENT), (PermissionError, errno.EACCES),
        ):
            def read_input(filename, **kwargs):
                if filename == "readable.md":
                    return io.StringIO("Plain sentence.")
                raise error_type(code, "unavailable", filename)

            with self.subTest(error_type=error_type):
                with mock.patch("builtins.open", side_effect=read_input):
                    with mock.patch.object(self.mod.os.path, "isdir", return_value=False):
                        self.assert_incomplete_input(["unavailable.md"], "unavailable.md")
                        self.assert_incomplete_input(
                            ["readable.md", "unavailable.md"], "unavailable.md", readable_files=1,
                        )

    def test_directory_traversal_errors_fail_without_losing_readable_results(self):
        def walk(directory, onerror):
            onerror(PermissionError(errno.EACCES, "unavailable", "docs/private"))
            yield "docs", [], ["readable.md"]

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(self.mod.os, "walk", side_effect=walk))
            stack.enter_context(mock.patch.object(self.mod.os.path, "isdir", return_value=True))
            stack.enter_context(mock.patch(
                "builtins.open", side_effect=lambda *args, **kwargs: io.StringIO("Plain sentence."),
            ))
            self.assert_incomplete_input(["docs"], "docs/private", readable_files=1)
            with self.assertRaises(PermissionError):
                self.mod.expand_paths(["docs"])

    def test_input_error_takes_priority_over_lint_findings(self):
        def read_input(filename, **kwargs):
            if filename == "readable.md":
                return io.StringIO("Spin up the job;")
            raise FileNotFoundError(errno.ENOENT, "unavailable", filename)

        with mock.patch("builtins.open", side_effect=read_input):
            with mock.patch.object(self.mod.os.path, "isdir", return_value=False):
                status, stdout, stderr = self.run_main(["--json", "readable.md", "missing.md"])
        self.assertEqual(status, 2)
        self.assertGreater(json.loads(stdout)["hard_count"], 0)
        self.assertIn("missing.md", stderr)

    def test_stdin_read_error_is_not_a_clean_lint(self):
        with mock.patch.object(self.mod.sys, "stdin") as stdin:
            stdin.read.side_effect = OSError(errno.EIO, "input failed")
            status, stdout, stderr = self.run_main(["--json", "--baseline", "999"])
        self.assertEqual(status, 2)
        self.assertIn("<stdin>: cannot read", stderr)
        self.assertEqual(json.loads(stdout)["hard_count"], 0)


if __name__ == "__main__":
    unittest.main()
