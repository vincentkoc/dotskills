from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LaneSnapshotPrivacyTests(unittest.TestCase):
    def test_redacts_home_secrets_and_private_ips(self) -> None:
        module = load_module(
            "skills/tmux-agent-lane-orchestrator/scripts/lane_snapshot.py"
        )
        text = f"{Path.home()}/repo token=secret-value host=100.64.1.2"
        redacted = module.redact(text)
        self.assertEqual(redacted, "~/repo <redacted-secret> host=<private-ip>")


class CodebaseMemoryGraphTests(unittest.TestCase):
    def test_rejects_invalid_port_before_startup(self) -> None:
        script = ROOT / "skills/codebase-memory-mcp/scripts/codebase-memory-graph.sh"
        result = subprocess.run(
            [str(script), "status", "--port", "70000"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid port", result.stderr)


if __name__ == "__main__":
    unittest.main()
