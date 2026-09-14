from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/validate_spec.py"
spec = importlib.util.spec_from_file_location("validate_spec", SCRIPT)
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
CHART = "```mermaid\nstateDiagram-v2\n    [*] --> Result\n    Result --> [*]\n```\n"


class WorkflowChartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.skill = self.root / "skills" / "example"
        (self.skill / "references").mkdir(parents=True)
        override = patch.object(validator, "PUBLIC_SKILLS_ROOT", self.root / "skills")
        override.start()
        self.addCleanup(override.stop)

    def check(self, body: str, metadata=None, directory=None):
        errors = []
        directory = directory or self.skill
        validator.validate_workflow(
            directory, directory / "SKILL.md", {"metadata": metadata or {}}, body, errors,
        )
        return errors

    def test_inline_chart_is_accepted(self) -> None:
        self.assertEqual(self.check("## Flow\n\n" + CHART), [])

    def test_direct_reference_must_resolve_to_a_state_chart(self) -> None:
        body = "## Flow\n\nSee [flow](references/flow.md).\n"
        self.assertTrue(self.check(body))
        path = self.skill / "references" / "flow.md"
        path.write_text("# Empty\n")
        self.assertTrue(self.check(body))
        path.write_text(CHART)
        self.assertEqual(self.check(body), [])

    def test_fence_header_and_other_diagrams_are_not_charts(self) -> None:
        for content in ["stateDiagram-v2", "```mermaid\nstateDiagram-v2\n```\n",
                        "```mermaid\nflowchart TD\nA --> B\n```\n",
                        "```mermaid\nstateDiagram-v2\nA --> B\n"]:
            with self.subTest(content=content):
                self.assertTrue(self.check("## Flow\n\n" + content))

    def test_chart_in_another_section_does_not_satisfy_flow(self) -> None:
        self.assertTrue(self.check("## Flow\nPending\n\n## Examples\n" + CHART))

    def test_specific_exemption_is_accepted_but_empty_or_conflicting_is_not(self) -> None:
        reason = {"workflow-exemption": "Linear evidence collection and interpretation checklist."}
        self.assertEqual(self.check("## Workflow\nInspect and report.\n", reason), [])
        self.assertTrue(self.check("## Workflow\nInspect and report.\n", {"workflow-exemption": " "}))
        self.assertTrue(self.check("## Flow\n" + CHART, reason))

    def test_private_and_internal_skills_are_excluded(self) -> None:
        self.assertEqual(self.check("", {"internal": "true"}), [])
        self.assertEqual(self.check("", directory=self.root / "private-skills" / "example"), [])
        self.assertEqual(self.check("", directory=self.root / "vendor" / "example"), [])

    def test_reference_cannot_escape_skill_via_parent_or_symlink(self) -> None:
        external = self.root / "outside.md"
        external.write_text(CHART)
        (self.skill / "references" / "escape.md").symlink_to(external)
        for ref in ["references/escape.md", "references/../../../outside.md"]:
            with self.subTest(ref=ref):
                errors = self.check(f"## Flow\n[flow]({ref})\n")
                self.assertTrue(any("leaves skill directory" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
