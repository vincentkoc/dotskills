from __future__ import annotations

import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (
    ROOT
    / "skills"
    / "codebase-memory-mcp"
    / "scripts"
    / "codebase-memory-gateway.py.tmpl"
)
GRAPH_SCRIPT = (
    ROOT
    / "skills"
    / "codebase-memory-mcp"
    / "scripts"
    / "codebase-memory-graph.sh"
)


class GatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = pathlib.Path(self.temporary.name)
        self.backend_log = self.temp / "backend.jsonl"
        self.resolver_log = self.temp / "resolver.jsonl"
        self.canonical = self.temp / "canonical"
        self.canonical.mkdir()
        self.backend = self.temp / "approved-backend"
        self.backend.write_text(
            f"""#!{sys.executable}
import json
import os
import pathlib
import signal
import sys

log = pathlib.Path(os.environ["FAKE_BACKEND_LOG"])
with log.open("a") as handle:
    handle.write(json.dumps({{"argv": sys.argv, "pid": os.getpid()}}) + "\\n")
print(json.dumps({{"argv": sys.argv, "pid": os.getpid()}}))
requested_signal = os.environ.get("FAKE_BACKEND_SIGNAL")
if requested_signal:
    os.kill(os.getpid(), int(requested_signal))
raise SystemExit(int(os.environ.get("FAKE_BACKEND_EXIT", "0")))
"""
        )
        self.backend.chmod(0o755)
        self.resolver = self.temp / "resolver.py"
        self.resolver.write_text(
            """import json
import os
import pathlib
import sys

log = pathlib.Path(os.environ["FAKE_RESOLVER_LOG"])
with log.open("a") as handle:
    handle.write(json.dumps(sys.argv) + "\\n")
if sys.argv[2] == "DENY":
    print("reserved repository", file=sys.stderr)
    raise SystemExit(2)
print(json.dumps({"canonical_root": os.environ["FAKE_CANONICAL"]}))
"""
        )
        self.gateway = self.temp / "codebase-memory-mcp"
        rendered = TEMPLATE.read_text()
        replacements = {
            "@@PYTHON_PATH_SHEBANG@@": sys.executable,
            "@@PYTHON_PATH_JSON@@": json.dumps(sys.executable),
            "@@BACKEND_PATH_JSON@@": json.dumps(str(self.backend)),
            "@@RESOLVER_PATH_JSON@@": json.dumps(str(self.resolver)),
        }
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)
        self.assertNotIn("@@", rendered)
        self.gateway.write_text(rendered)
        self.gateway.chmod(0o755)
        self.environment = {
            **os.environ,
            "FAKE_BACKEND_LOG": str(self.backend_log),
            "FAKE_RESOLVER_LOG": str(self.resolver_log),
            "FAKE_CANONICAL": str(self.canonical),
            "PATH": str(self.temp),
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_gateway(
        self,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.gateway), *args],
            check=False,
            capture_output=True,
            text=True,
            env=env or self.environment,
        )

    @staticmethod
    def read_json_lines(path: pathlib.Path) -> list[object]:
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text().splitlines()
            if line
        ]

    def reset_logs(self) -> None:
        self.backend_log.unlink(missing_ok=True)
        self.resolver_log.unlink(missing_ok=True)

    def test_index_payload_preserves_keys_and_types(self) -> None:
        payload = {
            "repo_path": "/requested/repository",
            "mode": "full",
            "enabled": True,
            "nothing": None,
            "count": 3,
            "ratio": 1.5,
            "nested": {"values": [1, "two", False]},
        }
        result = self.run_gateway(
            "cli",
            "index_repository",
            json.dumps(payload),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        backend = json.loads(result.stdout)
        self.assertEqual(backend["argv"][0], str(self.backend))
        forwarded = json.loads(backend["argv"][3])
        self.assertEqual(
            forwarded,
            {**payload, "repo_path": str(self.canonical)},
        )
        self.assertEqual(
            self.read_json_lines(self.resolver_log),
            [[str(self.resolver), "resolve-index", payload["repo_path"]]],
        )

    def test_index_rejects_strict_json_and_argument_errors(self) -> None:
        invalid = (
            ("duplicate", ('{"repo_path":"/one","repo_path":"/two"}',)),
            ("nan", ('{"repo_path":"/repo","value":NaN}',)),
            ("malformed", ('{"repo_path":',)),
            ("missing", ('{"mode":"full"}',)),
            ("non-string", ('{"repo_path":3}',)),
            ("nul", (json.dumps({"repo_path": "bad\0path"}),)),
            ("array", ('["/repo"]',)),
            ("missing-argument", ()),
            ("extra-argument", ('{"repo_path":"/repo"}', "extra")),
        )
        for name, arguments in invalid:
            with self.subTest(name=name):
                self.reset_logs()
                result = self.run_gateway(
                    "cli",
                    "index_repository",
                    *arguments,
                )
                self.assertEqual(result.returncode, 2)
                self.assertFalse(self.backend_log.exists())
                self.assertFalse(self.resolver_log.exists())

    def test_resolver_denial_never_reaches_backend(self) -> None:
        result = self.run_gateway(
            "cli",
            "index_repository",
            json.dumps({"repo_path": "DENY", "mode": "full"}),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("canonical resolver denied repository", result.stderr)
        self.assertEqual(
            self.read_json_lines(self.resolver_log),
            [[str(self.resolver), "resolve-index", "DENY"]],
        )
        self.assertFalse(self.backend_log.exists())

    def test_non_index_passthrough_uses_exact_exec_pid_exit_and_signal(
        self,
    ) -> None:
        process = subprocess.Popen(
            [str(self.gateway), "cli", "list_projects"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self.environment,
        )
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, stderr)
        response = json.loads(stdout)
        self.assertEqual(response["pid"], process.pid)
        self.assertEqual(
            response["argv"],
            [str(self.backend), "cli", "list_projects"],
        )

        exit_environment = {
            **self.environment,
            "FAKE_BACKEND_EXIT": "7",
        }
        exited = self.run_gateway("--version", env=exit_environment)
        self.assertEqual(exited.returncode, 7)

        signal_environment = {
            **self.environment,
            "FAKE_BACKEND_SIGNAL": str(int(signal.SIGTERM)),
        }
        signaled = self.run_gateway("--version", env=signal_environment)
        self.assertEqual(signaled.returncode, -signal.SIGTERM)

    def test_mutation_and_ui_forms_are_denied_before_backend(self) -> None:
        denied = (
            ("install",),
            ("update",),
            ("uninstall",),
            ("--ui",),
            ("--ui=true",),
            ("--ui=1",),
            ("--ui=yes",),
            ("--ui=on",),
            ("--ui", "true"),
            ("config", "reset"),
            ("config", "reset", "--yes"),
            ("config", "set", "ui", "true"),
            ("config", "set", "ui", "1"),
            ("config", "set", "auto_index", "true"),
            ("config", "set", "port", "9749"),
            ("config", "set", "ui", "false", "extra"),
        )
        for args in denied:
            with self.subTest(args=args):
                self.reset_logs()
                result = self.run_gateway(*args)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(self.backend_log.exists())
                self.assertFalse(self.resolver_log.exists())

        for args in (
            ("config", "set", "ui", "false"),
            ("config", "set", "auto_index", "false"),
        ):
            with self.subTest(args=args):
                self.reset_logs()
                result = self.run_gateway(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(self.backend_log.exists())
                self.assertFalse(self.resolver_log.exists())


class GraphUiBoundaryTests(unittest.TestCase):
    def test_ui_commands_fail_before_external_processes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            calls = temp / "calls"
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codebase-memory-mcp"
            fake.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$CALLS"\n'
            )
            fake.chmod(0o755)
            for name in ("curl", "git", "node", "python3", "tmux"):
                (bin_dir / name).symlink_to(fake)
            environment = {
                **os.environ,
                "CALLS": str(calls),
                "PATH": f"{bin_dir}:/usr/bin:/bin",
            }

            for command in ("start-ui", "keepalive"):
                with self.subTest(command=command):
                    result = subprocess.run(
                        [str(GRAPH_SCRIPT), command],
                        check=False,
                        capture_output=True,
                        text=True,
                        env=environment,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(
                        "/api/index canonicalization",
                        result.stderr,
                    )
                    self.assertFalse(calls.exists())

    def test_init_does_not_enable_or_start_ui(self) -> None:
        with tempfile.TemporaryDirectory(dir=pathlib.Path.home()) as directory:
            temp = pathlib.Path(directory)
            repo = temp / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init", "-q", "-b", "main", str(repo)],
                check=True,
            )
            calls = temp / "calls.jsonl"
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            fake_backend = bin_dir / "codebase-memory-mcp"
            fake_backend.write_text(
                f"""#!{sys.executable}
import json
import os
import pathlib
import sys

log = pathlib.Path(os.environ["CALLS"])
with log.open("a") as handle:
    handle.write(json.dumps({{"program": "codebase-memory-mcp", "args": sys.argv[1:]}}) + "\\n")
args = sys.argv[1:]
if args == ["cli", "list_projects"]:
    print(json.dumps({{"projects": [{{
        "name": "fixture",
        "root_path": os.environ["FAKE_REPO_ROOT"],
        "size_bytes": 1,
    }}]}}))
else:
    print("{{}}")
"""
            )
            fake_backend.chmod(0o755)
            generic = bin_dir / "probe"
            generic.write_text(
                """#!/bin/sh
printf '{"program":"%s","args":"%s"}\n' "$(basename "$0")" "$*" >> "$CALLS"
exit 1
"""
            )
            generic.chmod(0o755)
            for name in ("curl", "lsof", "node", "tmux"):
                (bin_dir / name).symlink_to(generic)
            (bin_dir / "python3").symlink_to(sys.executable)
            environment = {
                **os.environ,
                "CALLS": str(calls),
                "FAKE_REPO_ROOT": str(repo.resolve()),
                "PATH": f"{bin_dir}:/usr/bin:/bin",
            }
            result = subprocess.run(
                [str(GRAPH_SCRIPT), "init", "--repo", str(repo)],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            events = self.read_events(calls)
            rendered = json.dumps(events)
            self.assertNotIn('"config", "set"', rendered)
            self.assertNotIn("--ui", rendered)
            self.assertNotIn("new-session", rendered)
            self.assertFalse(
                any(event["program"] == "node" for event in events)
            )

    @staticmethod
    def read_events(path: pathlib.Path) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in path.read_text().splitlines()
            if line
        ]


if __name__ == "__main__":
    unittest.main()
