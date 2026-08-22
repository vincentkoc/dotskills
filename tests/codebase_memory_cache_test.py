from __future__ import annotations

import errno
import hashlib
import importlib.util
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "skills"
    / "codebase-memory-mcp"
    / "scripts"
    / "codebase_memory_cache.py"
)
SCRIPT = (
    ROOT
    / "skills"
    / "codebase-memory-mcp"
    / "scripts"
    / "codebase-memory-graph.sh"
)

SPEC = importlib.util.spec_from_file_location("codebase_memory_cache", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
CBM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CBM)


def command(*args: str, cwd: pathlib.Path | None = None) -> str:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def init_repo(path: pathlib.Path) -> None:
    path.mkdir()
    command("git", "init", "-q", "-b", "main", str(path))
    command("git", "-C", str(path), "config", "user.name", "Test User")
    command("git", "-C", str(path), "config", "user.email", "test@example.test")
    (path / "README.md").write_text("fixture\n")
    command("git", "-C", str(path), "add", "README.md")
    command("git", "-C", str(path), "commit", "-qm", "test: fixture")


def sqlite_file(path: pathlib.Path) -> int:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE proof (value TEXT)")
    connection.commit()
    connection.close()
    return path.stat().st_size


class ResolverTests(unittest.TestCase):
    def test_main_and_linked_worktree_resolve_to_same_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            main = temp / "main"
            worktree = temp / "branch"
            init_repo(main)
            command(
                "git",
                "-C",
                str(main),
                "worktree",
                "add",
                "-q",
                "-b",
                "feature",
                str(worktree),
            )
            main_result = CBM.resolve_repository(main)
            worktree_result = CBM.resolve_repository(worktree)
            self.assertEqual(main_result["canonical_root"], str(main.resolve()))
            self.assertEqual(worktree_result["canonical_root"], str(main.resolve()))
            self.assertFalse(main_result["linked_worktree"])
            self.assertTrue(worktree_result["linked_worktree"])

    def test_separate_clones_remain_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            first = temp / "first"
            second = temp / "second"
            init_repo(first)
            command("git", "clone", "-q", str(first), str(second))
            self.assertNotEqual(
                CBM.resolve_repository(first)["canonical_root"],
                CBM.resolve_repository(second)["canonical_root"],
            )

    def test_symlink_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            repo = temp / "repo"
            alias = temp / "alias"
            init_repo(repo)
            alias.symlink_to(repo, target_is_directory=True)
            self.assertEqual(
                CBM.resolve_repository(alias)["canonical_root"], str(repo.resolve())
            )

    def test_missing_bare_and_invalid_paths_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            bare = temp / "bare.git"
            invalid = temp / "invalid"
            invalid.mkdir()
            command("git", "init", "-q", "--bare", str(bare))
            for path in (temp / "missing", bare, invalid):
                with self.subTest(path=path):
                    with self.assertRaises(CBM.SafetyError):
                        CBM.resolve_repository(path)


class DatabaseValidationTests(unittest.TestCase):
    def test_uses_exact_immutable_read_only_uri(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "project.db"
            size = sqlite_file(database)
            baseline = CBM.capture_cache_baseline(database, size)
            with mock.patch.object(
                CBM.sqlite3,
                "connect",
                wraps=sqlite3.connect,
            ) as connect:
                CBM.validate_database(database, baseline)

            encoded = urllib.parse.quote(str(database), safe="/")
            connect.assert_called_once_with(
                f"file:{encoded}?mode=ro&immutable=1",
                uri=True,
            )
            self.assertEqual(CBM.cache_fingerprint(database), baseline)

    def test_validation_core_does_not_probe_holders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "project.db"
            size = sqlite_file(database)
            baseline = CBM.capture_cache_baseline(database, size)
            with (
                mock.patch.object(CBM, "run_holder_chunk") as holder_probe,
                mock.patch.object(
                    CBM.sqlite3,
                    "connect",
                    wraps=sqlite3.connect,
                ),
            ):
                CBM.validate_database(database, baseline)
            holder_probe.assert_not_called()

    def test_database_and_sidecar_mutation_during_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            for suffix in ("", "-wal", "-shm"):
                with self.subTest(suffix=suffix):
                    database = temp / f"project{suffix or '-db'}.db"
                    size = sqlite_file(database)
                    target = pathlib.Path(f"{database}{suffix}")
                    if suffix == "-wal":
                        target.write_bytes(b"")
                    elif suffix == "-shm":
                        target.write_bytes(b"\0" * 32768)

                    real_connect = sqlite3.connect

                    def mutating_connect(*args, **kwargs):
                        connection = real_connect(*args, **kwargs)
                        real_execute = connection.execute

                        class Connection:
                            def execute(self, statement):
                                cursor = real_execute(statement)
                                metadata = target.stat()
                                os.utime(
                                    target,
                                    ns=(
                                        metadata.st_atime_ns,
                                        metadata.st_mtime_ns + 1_000_000_000,
                                    ),
                                )
                                return cursor

                            def close(self):
                                connection.close()

                        return Connection()

                    with (
                        mock.patch.object(
                            CBM.sqlite3,
                            "connect",
                            side_effect=mutating_connect,
                        ),
                        self.assertRaisesRegex(
                            CBM.SafetyError,
                            "fingerprint changed during validation",
                        ),
                    ):
                        baseline = CBM.capture_cache_baseline(database, size)
                        CBM.validate_database(database, baseline)


class HolderSweepTests(unittest.TestCase):
    def test_inventory_and_chunks_preserve_candidate_path_and_unicode_order(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = pathlib.Path(directory)
            candidates = [
                {"name": "fixture-z"},
                {"name": "fixture-é"},
            ]
            fingerprints = {}
            for candidate in candidates:
                database = cache / f"{candidate['name']}.db"
                fingerprints[candidate["name"]] = {
                    database.name: {"size": 1},
                    f"{database.name}-wal": {"size": 0},
                    f"{database.name}-shm": {"size": 1},
                }

            inventory = CBM.holder_inventory(
                cache_dir=cache,
                candidates=candidates,
                fingerprints=fingerprints,
            )
            self.assertEqual(
                [
                    (item["candidate"], item["kind"])
                    for item in inventory
                ],
                [
                    ("fixture-z", "db"),
                    ("fixture-z", "wal"),
                    ("fixture-z", "shm"),
                    ("fixture-é", "db"),
                    ("fixture-é", "wal"),
                    ("fixture-é", "shm"),
                ],
            )
            self.assertEqual(
                CBM.lsof_argv_cost(inventory[3]["path"]),
                len(os.fsencode(inventory[3]["path"]))
                + 1
                + CBM.struct.calcsize("P"),
            )

            base_cost = sum(
                CBM.lsof_argv_cost(value)
                for value in (
                    "/usr/sbin/lsof",
                    "-nP",
                    "-F0pfn",
                    "-f",
                    "--",
                )
            ) + CBM.struct.calcsize("P")
            budget = (
                base_cost
                + CBM.lsof_argv_cost(inventory[0]["path"])
                + CBM.lsof_argv_cost(inventory[1]["path"])
            )
            chunks = CBM.chunk_holder_inventory(
                "/usr/sbin/lsof",
                inventory,
                budget=budget,
            )
            self.assertEqual(
                [
                    (item["candidate"], item["kind"])
                    for chunk in chunks
                    for item in chunk
                ],
                [
                    ("fixture-z", "db"),
                    ("fixture-z", "wal"),
                    ("fixture-z", "shm"),
                    ("fixture-é", "db"),
                    ("fixture-é", "wal"),
                    ("fixture-é", "shm"),
                ],
            )
            self.assertEqual(
                [
                    (item["candidate"], item["kind"])
                    for item in chunks[0]
                ],
                [("fixture-z", "db"), ("fixture-z", "wal")],
            )

    def test_cache_path_count_mismatch_fails_before_external_operations(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = pathlib.Path(directory)
            database = cache / "fixture.db"
            candidate = {"name": "fixture", "size_bytes": 1}
            baseline = {
                database.name: {"size": 1},
                f"{database.name}-wal": None,
                f"{database.name}-shm": None,
            }
            path_counts = {
                "shorter": [database, pathlib.Path(f"{database}-wal")],
                "longer": [
                    database,
                    pathlib.Path(f"{database}-wal"),
                    pathlib.Path(f"{database}-shm"),
                    pathlib.Path(f"{database}-extra"),
                ],
            }
            for name, paths in path_counts.items():
                with (
                    self.subTest(name=name),
                    mock.patch.object(CBM, "list_projects", return_value=[]),
                    mock.patch.object(CBM, "validate_snapshot"),
                    mock.patch.object(CBM, "revalidate_candidate"),
                    mock.patch.object(
                        CBM,
                        "capture_cache_baseline",
                        return_value=baseline,
                    ),
                    mock.patch.object(CBM, "cache_paths", return_value=paths),
                    mock.patch.object(
                        CBM,
                        "lsof_binary",
                        return_value="/usr/sbin/lsof",
                    ),
                    mock.patch.object(CBM, "run_holder_sweep") as holder_sweep,
                    mock.patch.object(CBM, "validate_database") as sqlite_check,
                    mock.patch.object(CBM.subprocess, "Popen") as delete_process,
                    self.assertRaisesRegex(
                        CBM.SafetyError,
                        f"expected 3 paths, got {len(paths)}",
                    ),
                ):
                    CBM.preflight_candidates(
                        binary="codebase-memory-mcp",
                        cache_dir=cache,
                        candidates=[candidate],
                        expected_snapshot=[],
                        prefixes=[],
                        lsof_timeout_seconds=300,
                    )
                holder_sweep.assert_not_called()
                sqlite_check.assert_not_called()
                delete_process.assert_not_called()

    def test_nul_lsof_output_attributes_multiple_paths_and_pids(self) -> None:
        inventory = [
            {"candidate": "first", "kind": "db", "path": "/cache/first.db"},
            {"candidate": "second", "kind": "shm", "path": "/cache/second.db-shm"},
        ]
        holders = CBM.parse_lsof_holders(
            (
                b"p12\0\nf3\0n/cache/first.db\0\n"
                b"p34\0\nf7\0n/cache/second.db-shm\0\n"
            ),
            inventory,
        )
        self.assertEqual(
            holders,
            [
                {**inventory[0], "pid": "12"},
                {**inventory[1], "pid": "34"},
            ],
        )
        with (
            mock.patch.object(
                CBM.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    ["lsof"],
                    0,
                    stdout=(
                        b"p12\0f3\0n/cache/first.db\0\n"
                        b"p34\0f7\0n/cache/second.db-shm\0"
                    ),
                    stderr=b"",
                ),
            ),
            self.assertRaises(CBM.SafetyError) as raised,
        ):
            CBM.run_holder_chunk(
                "/usr/sbin/lsof",
                inventory,
                timeout_seconds=300,
            )
        message = str(raised.exception)
        self.assertIn("candidate=first kind=db path=/cache/first.db pid=12", message)
        self.assertIn(
            "candidate=second kind=shm path=/cache/second.db-shm pid=34",
            message,
        )

    def test_lsof_failures_are_closed_without_retry(self) -> None:
        inventory = [
            {"candidate": "first", "kind": "db", "path": "/cache/first.db"}
        ]
        cases = {
            "other-exit": (
                subprocess.CompletedProcess(
                    ["lsof"], 2, stdout=b"", stderr=b"failed"
                ),
                "holder sweep failed",
            ),
            "signal": (
                subprocess.CompletedProcess(
                    ["lsof"], -9, stdout=b"", stderr=b""
                ),
                "exit -9",
            ),
            "success-without-rows": (
                subprocess.CompletedProcess(
                    ["lsof"], 0, stdout=b"", stderr=b""
                ),
                "success without a mapped holder",
            ),
            "incomplete": (
                subprocess.CompletedProcess(
                    ["lsof"], 0, stdout=b"p12\0f3\0", stderr=b""
                ),
                "incomplete file record",
            ),
            "unmapped": (
                subprocess.CompletedProcess(
                    ["lsof"],
                    0,
                    stdout=b"p12\0f3\0n/cache/other.db\0",
                    stderr=b"",
                ),
                "unmapped cache path",
            ),
            "no-match-stdout": (
                subprocess.CompletedProcess(
                    ["lsof"], 1, stdout=b"unexpected", stderr=b""
                ),
                "malformed holder output",
            ),
            "no-match-stderr": (
                subprocess.CompletedProcess(
                    ["lsof"], 1, stdout=b"", stderr=b"warning"
                ),
                "holder sweep failed",
            ),
        }
        for name, (result, message) in cases.items():
            with self.subTest(name=name):
                with (
                    mock.patch.object(
                        CBM.subprocess,
                        "run",
                        return_value=result,
                    ) as run_lsof,
                    self.assertRaisesRegex(CBM.SafetyError, message),
                ):
                    CBM.run_holder_chunk(
                        "/usr/sbin/lsof",
                        inventory,
                        timeout_seconds=300,
                    )
                run_lsof.assert_called_once()

        clean = subprocess.CompletedProcess(
            ["lsof"], 1, stdout=b"", stderr=b""
        )
        with mock.patch.object(
            CBM.subprocess,
            "run",
            return_value=clean,
        ) as run_lsof:
            CBM.run_holder_chunk(
                "/usr/sbin/lsof",
                inventory,
                timeout_seconds=300,
            )
        run_lsof.assert_called_once_with(
            [
                "/usr/sbin/lsof",
                "-nP",
                "-F0pfn",
                "-f",
                "--",
                "/cache/first.db",
            ],
            check=False,
            capture_output=True,
            timeout=300,
        )

    def test_lsof_binary_ignores_environment_override(self) -> None:
        inventory = [
            {"candidate": "first", "kind": "db", "path": "/cache/first.db"}
        ]
        clean = subprocess.CompletedProcess(
            ["lsof"], 1, stdout=b"", stderr=b""
        )
        with (
            mock.patch.dict(
                os.environ,
                {"CBM_LSOF_BIN": "/tmp/malicious-lsof"},
            ),
            mock.patch.object(
                CBM.pathlib.Path,
                "is_file",
                return_value=True,
            ),
            mock.patch.object(CBM.os, "access", return_value=True),
            mock.patch.object(
                CBM.subprocess,
                "run",
                return_value=clean,
            ) as run_lsof,
        ):
            lsof = CBM.lsof_binary()
            CBM.run_holder_chunk(
                lsof,
                inventory,
                timeout_seconds=300,
            )

        self.assertEqual(lsof, "/usr/sbin/lsof")
        self.assertEqual(
            run_lsof.call_args.args[0][0],
            "/usr/sbin/lsof",
        )

        holder_on_rc1 = subprocess.CompletedProcess(
            ["lsof"],
            1,
            stdout=b"p12\0f3\0n/cache/first.db\0",
            stderr=b"warning",
        )
        with (
            mock.patch.object(
                CBM.subprocess,
                "run",
                return_value=holder_on_rc1,
            ),
            self.assertRaisesRegex(CBM.SafetyError, "project DB is held"),
        ):
            CBM.run_holder_chunk(
                "/usr/sbin/lsof",
                inventory,
                timeout_seconds=300,
            )

        exceptional = {
            "timeout": (
                subprocess.TimeoutExpired("lsof", 300),
                "timed out",
            ),
            "e2big": (
                OSError(errno.E2BIG, "argument list too long"),
                "argv limit",
            ),
        }
        for name, (error, message) in exceptional.items():
            with self.subTest(name=name):
                with (
                    mock.patch.object(
                        CBM.subprocess,
                        "run",
                        side_effect=error,
                    ) as run_lsof,
                    self.assertRaisesRegex(CBM.SafetyError, message),
                ):
                    CBM.run_holder_chunk(
                        "/usr/sbin/lsof",
                        inventory,
                        timeout_seconds=300,
                    )
                run_lsof.assert_called_once()

    def test_all_before_chunks_precede_sqlite_and_after_chunks_follow_close(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = pathlib.Path(directory)
            candidates = []
            for name in ("first", "second"):
                path = cache / f"{name}.db"
                size = sqlite_file(path)
                candidates.append(
                    {
                        "name": name,
                        "root_path": f"/missing/{name}",
                        "size_bytes": size,
                    }
                )
            chunks = [
                [{"candidate": "first", "kind": "db", "path": "/first"}],
                [{"candidate": "second", "kind": "db", "path": "/second"}],
            ]
            events = []

            def holder(chunk_lsof, chunk, *, timeout_seconds):
                self.assertEqual(chunk_lsof, "/usr/sbin/lsof")
                self.assertEqual(timeout_seconds, 300)
                events.append(f"lsof:{chunk[0]['candidate']}")

            def validate(path, baseline):
                self.assertEqual(
                    CBM.cache_fingerprint(path),
                    baseline,
                )
                events.append(f"sqlite:{path.stem}")

            with (
                mock.patch.object(CBM, "list_projects", return_value=[]),
                mock.patch.object(CBM, "validate_snapshot"),
                mock.patch.object(CBM, "revalidate_candidate"),
                mock.patch.object(
                    CBM,
                    "lsof_binary",
                    return_value="/usr/sbin/lsof",
                ),
                mock.patch.object(
                    CBM,
                    "chunk_holder_inventory",
                    return_value=chunks,
                ),
                mock.patch.object(CBM, "run_holder_chunk", side_effect=holder),
                mock.patch.object(CBM, "validate_database", side_effect=validate),
            ):
                CBM.preflight_candidates(
                    binary="codebase-memory-mcp",
                    cache_dir=cache,
                    candidates=candidates,
                    expected_snapshot=[],
                    prefixes=[],
                    lsof_timeout_seconds=300,
                )

            self.assertEqual(
                events,
                [
                    "lsof:first",
                    "lsof:second",
                    "sqlite:first",
                    "sqlite:second",
                    "lsof:first",
                    "lsof:second",
                ],
            )

    def test_later_before_holder_prevents_all_sqlite_opens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = pathlib.Path(directory)
            database = cache / "first.db"
            candidate = {
                "name": "first",
                "root_path": "/missing/first",
                "size_bytes": sqlite_file(database),
            }
            chunks = [
                [{"candidate": "first", "kind": "db", "path": "/first"}],
                [{"candidate": "first", "kind": "shm", "path": "/first-shm"}],
            ]
            with (
                mock.patch.object(CBM, "list_projects", return_value=[]),
                mock.patch.object(CBM, "validate_snapshot"),
                mock.patch.object(CBM, "revalidate_candidate"),
                mock.patch.object(
                    CBM,
                    "lsof_binary",
                    return_value="/usr/sbin/lsof",
                ),
                mock.patch.object(
                    CBM,
                    "chunk_holder_inventory",
                    return_value=chunks,
                ),
                mock.patch.object(
                    CBM,
                    "run_holder_chunk",
                    side_effect=[
                        None,
                        CBM.SafetyError("project DB is held"),
                    ],
                ),
                mock.patch.object(CBM, "validate_database") as validate,
                self.assertRaisesRegex(CBM.SafetyError, "project DB is held"),
            ):
                CBM.preflight_candidates(
                    binary="codebase-memory-mcp",
                    cache_dir=cache,
                    candidates=[candidate],
                    expected_snapshot=[],
                    prefixes=[],
                    lsof_timeout_seconds=300,
                )
            validate.assert_not_called()


class DeletionBatchTests(unittest.TestCase):
    def test_batches_preserve_manifest_order_max_eight_and_argv_budget(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = pathlib.Path(directory)
            candidates = []
            fingerprints = {}
            for index in range(17):
                name = f"fixture-{index:02d}"
                path = cache / f"{name}.db"
                size = sqlite_file(path)
                candidate = {
                    "name": name,
                    "size_bytes": size,
                    "reason": "ephemeral_missing_root",
                }
                candidates.append(candidate)
                fingerprints[name] = CBM.capture_cache_baseline(path, size)

            batches = CBM.deletion_candidate_batches(
                lsof="/usr/sbin/lsof",
                cache_dir=cache,
                candidates=candidates,
                fingerprints=fingerprints,
            )
            self.assertEqual([len(batch) for batch in batches], [8, 8, 1])
            self.assertEqual(
                [
                    candidate["name"]
                    for batch in batches
                    for candidate in batch
                ],
                [candidate["name"] for candidate in candidates],
            )

            first_inventory = CBM.holder_inventory(
                cache_dir=cache,
                candidates=[candidates[0]],
                fingerprints=fingerprints,
            )
            one_candidate_budget = (
                sum(
                    CBM.lsof_argv_cost(value)
                    for value in CBM.lsof_command_prefix("/usr/sbin/lsof")
                )
                + CBM.struct.calcsize("P")
                + sum(
                    CBM.lsof_argv_cost(item["path"])
                    for item in first_inventory
                )
            )
            budget_batches = CBM.deletion_candidate_batches(
                lsof="/usr/sbin/lsof",
                cache_dir=cache,
                candidates=candidates[:2],
                fingerprints=fingerprints,
                budget=one_candidate_budget,
            )
            self.assertEqual([len(batch) for batch in budget_batches], [1, 1])

    def test_spawn_failure_drains_launched_child_and_reports_partial_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = pathlib.Path(directory)
            candidates = []
            fingerprints = {}
            for name in ("first", "second"):
                path = cache / f"{name}.db"
                size = sqlite_file(path)
                candidate = {
                    "name": name,
                    "root_path": f"/missing/{name}",
                    "size_bytes": size,
                    "reason": "ephemeral_missing_root",
                }
                candidates.append(candidate)
                fingerprints[name] = CBM.capture_cache_baseline(path, size)

            class Process:
                returncode = 0

                def __init__(self):
                    self.communicated = False

                def poll(self):
                    return self.returncode if self.communicated else None

                def communicate(self, timeout=None):
                    self.communicated = True
                    (cache / "first.db").unlink()
                    return b"", b""

                def terminate(self):
                    self.returncode = -15

                def kill(self):
                    self.returncode = -9

            process = Process()
            second_registered = {
                "name": "second",
                "root_path": "/missing/second",
                "size_bytes": candidates[1]["size_bytes"],
            }
            with (
                mock.patch.object(
                    CBM,
                    "list_projects",
                    side_effect=[[], [second_registered]],
                ) as list_projects,
                mock.patch.object(CBM, "validate_snapshot"),
                mock.patch.object(CBM, "revalidate_candidate"),
                mock.patch.object(CBM, "run_holder_chunk"),
                mock.patch.object(
                    CBM.subprocess,
                    "Popen",
                    side_effect=[
                        process,
                        OSError(errno.EMFILE, "too many open files"),
                    ],
                ) as popen,
                self.assertRaises(CBM.DeleteBatchError) as raised,
            ):
                CBM.execute_delete_batch(
                    binary="codebase-memory-mcp",
                    lsof="/usr/sbin/lsof",
                    lsof_timeout_seconds=300,
                    cache_dir=cache,
                    candidates=candidates,
                    fingerprints=fingerprints,
                    expected_snapshot=[],
                    prefixes=[],
                )

            report = raised.exception.report
            self.assertTrue(process.communicated)
            self.assertEqual(list_projects.call_count, 2)
            self.assertEqual(
                [
                    json.loads(call.args[0][3])["project"]
                    for call in popen.call_args_list
                ],
                ["first", "second"],
            )
            self.assertEqual(
                [item["name"] for item in report["launched"]],
                ["first"],
            )
            self.assertEqual(
                [item["name"] for item in report["verified_deleted"]],
                ["first"],
            )
            self.assertEqual(
                [item["name"] for item in report["failed"]],
                ["second"],
            )

    def test_batch_timeout_terminates_only_owned_child_and_reports_ambiguous(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = pathlib.Path(directory)
            path = cache / "first.db"
            size = sqlite_file(path)
            candidate = {
                "name": "first",
                "root_path": "/missing/first",
                "size_bytes": size,
                "reason": "ephemeral_missing_root",
            }
            fingerprint = CBM.capture_cache_baseline(path, size)

            class Process:
                returncode = None

                def __init__(self):
                    self.calls = 0
                    self.terminated = False
                    self.killed = False

                def poll(self):
                    return self.returncode

                def communicate(self, timeout=None):
                    self.calls += 1
                    if self.calls == 1:
                        raise subprocess.TimeoutExpired("delete", timeout)
                    self.returncode = -15
                    return b"", b""

                def terminate(self):
                    self.terminated = True

                def kill(self):
                    self.killed = True
                    self.returncode = -9

            process = Process()
            registered = {
                "name": "first",
                "root_path": "/missing/first",
                "size_bytes": size,
            }
            with (
                mock.patch.object(
                    CBM,
                    "list_projects",
                    side_effect=[[], [registered]],
                ),
                mock.patch.object(CBM, "validate_snapshot"),
                mock.patch.object(CBM, "revalidate_candidate"),
                mock.patch.object(CBM, "run_holder_chunk"),
                mock.patch.object(
                    CBM.subprocess,
                    "Popen",
                    return_value=process,
                ),
                mock.patch.object(
                    CBM.time,
                    "monotonic",
                    side_effect=[0, 0, 0, 0, 700, 700],
                ),
                self.assertRaises(CBM.DeleteBatchError) as raised,
            ):
                CBM.execute_delete_batch(
                    binary="codebase-memory-mcp",
                    lsof="/usr/sbin/lsof",
                    lsof_timeout_seconds=300,
                    cache_dir=cache,
                    candidates=[candidate],
                    fingerprints={"first": fingerprint},
                    expected_snapshot=[],
                    prefixes=[],
                )

            report = raised.exception.report
            self.assertTrue(process.terminated)
            self.assertFalse(process.killed)
            self.assertEqual(
                [item["name"] for item in report["ambiguous"]],
                ["first"],
            )


class CacheManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = pathlib.Path(self.temporary.name)
        self.main = self.temp / "main"
        self.worktree = self.temp / "worktree"
        self.cache = self.temp / "cache"
        self.state = self.temp / "projects.json"
        self.deleted = self.temp / "deleted.jsonl"
        self.events = self.temp / "events"
        self.lsof_calls = self.temp / "lsof-calls.jsonl"
        self.manifest = self.temp / "manifest.json"
        self.bin = self.temp / "bin"
        self.bin.mkdir()
        self.cache.mkdir()
        init_repo(self.main)
        command(
            "git",
            "-C",
            str(self.main),
            "worktree",
            "add",
            "-q",
            "-b",
            "feature",
            str(self.worktree),
        )
        self.main_name = "fixture-main"
        self.worktree_name = "fixture-worktree"
        main_size = sqlite_file(self.cache / f"{self.main_name}.db")
        worktree_size = sqlite_file(self.cache / f"{self.worktree_name}.db")
        self.projects = [
            {
                "name": self.main_name,
                "root_path": str(self.main),
                "size_bytes": main_size,
                "nodes": 1,
                "edges": 1,
            },
            {
                "name": self.worktree_name,
                "root_path": str(self.worktree),
                "size_bytes": worktree_size,
                "nodes": 1,
                "edges": 1,
            },
        ]
        self.write_projects(self.projects)
        fake_cbm = self.bin / "codebase-memory-mcp"
        fake_cbm.write_text(
            """#!/usr/bin/env python3
import fcntl, json, os, pathlib, sys, time
state = pathlib.Path(os.environ["FAKE_CBM_STATE"])
events = pathlib.Path(os.environ["FAKE_EVENTS"])
def event(value):
    with events.open("a") as handle:
        handle.write(value + "\\n")
def update_active(delta):
    active_path = pathlib.Path(os.environ["FAKE_CBM_ACTIVE"])
    maximum_path = pathlib.Path(os.environ["FAKE_CBM_MAX_ACTIVE"])
    lock_path = pathlib.Path(f"{active_path}.lock")
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        active = int(active_path.read_text()) if active_path.exists() else 0
        active += delta
        active_path.write_text(str(active))
        maximum = int(maximum_path.read_text()) if maximum_path.exists() else 0
        maximum_path.write_text(str(max(maximum, active)))
        return active
def current_maximum():
    active_path = pathlib.Path(os.environ["FAKE_CBM_ACTIVE"])
    maximum_path = pathlib.Path(os.environ["FAKE_CBM_MAX_ACTIVE"])
    lock_path = pathlib.Path(f"{active_path}.lock")
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return int(maximum_path.read_text()) if maximum_path.exists() else 0
if sys.argv[1:3] == ["cli", "list_projects"]:
    payload = json.loads(state.read_text())
    event("list_projects")
    calls = pathlib.Path(os.environ["FAKE_CBM_LIST_CALLS"])
    call = int(calls.read_text()) if calls.exists() else 0
    calls.write_text(str(call + 1))
    if os.environ.get("FAKE_CBM_MUTATE_ON_LIST_CALL") == str(call + 1):
        with pathlib.Path(os.environ["FAKE_CBM_MUTATE_PATH"]).open("ab") as handle:
            handle.write(b"x")
    print(json.dumps({"projects": payload}))
    raise SystemExit(0)
if sys.argv[1:3] == ["cli", "delete_project"]:
    name = json.loads(sys.argv[3])["project"]
    event(f"delete-start:{name}")
    deleted = pathlib.Path(os.environ["FAKE_CBM_DELETED"])
    with deleted.open("a") as handle:
        handle.write(json.dumps({"project": name}) + "\\n")
    update_active(1)
    try:
        target = int(os.environ.get("FAKE_CBM_WAIT_FOR_ACTIVE", "0"))
        wait_deadline = time.monotonic() + 20
        while target:
            maximum = current_maximum()
            if maximum >= target:
                break
            if time.monotonic() >= wait_deadline:
                print("active barrier timed out", file=sys.stderr)
                raise SystemExit(3)
            time.sleep(0.01)
        if os.environ.get("FAKE_CBM_DELETE_TIMEOUT") == name:
            time.sleep(30)
        delay = float(os.environ.get("FAKE_CBM_DELETE_SLEEP", "0"))
        if delay:
            time.sleep(delay)
        if os.environ.get("FAKE_CBM_DELETE_FAIL") == name:
            print(f"forced delete failure: {name}", file=sys.stderr)
            raise SystemExit(1)
        lock_path = pathlib.Path(f"{state}.lock")
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            current = json.loads(state.read_text())
            if os.environ.get("FAKE_CBM_RETAIN_NAME") != name:
                state.write_text(
                    json.dumps([item for item in current if item["name"] != name])
                )
        database = pathlib.Path(os.environ["CBM_CACHE_DIR"]) / f"{name}.db"
        for suffix in ("", "-wal", "-shm"):
            pathlib.Path(f"{database}{suffix}").unlink(missing_ok=True)
        residue_name = os.environ.get("FAKE_CBM_RESIDUE_NAME")
        if not residue_name or residue_name == name:
            for suffix in os.environ.get("FAKE_CBM_RESIDUE_SUFFIXES", "").split(","):
                if suffix:
                    pathlib.Path(f"{database}-{suffix}").write_bytes(b"residue")
            if os.environ.get("FAKE_CBM_RESIDUE_DB") == "1":
                database.write_bytes(b"residue")
        raise SystemExit(0)
    finally:
        update_active(-1)
        event(f"delete-end:{name}")
raise SystemExit(2)
"""
        )
        fake_cbm.chmod(0o755)
        fake_lsof = self.bin / "lsof"
        fake_lsof.write_text(
            """#!/usr/bin/env python3
import json, os, pathlib, sys
state = pathlib.Path(os.environ["FAKE_LSOF_STATE"])
call = int(state.read_text()) if state.exists() else 0
state.write_text(str(call + 1))
with pathlib.Path(os.environ["FAKE_EVENTS"]).open("a") as handle:
    handle.write("lsof\\n")
paths = sys.argv[sys.argv.index("--") + 1:]
calls = pathlib.Path(os.environ["FAKE_LSOF_CALLS"])
with calls.open("a") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\\n")
if os.environ.get("FAKE_LSOF_MUTATE_ON_CALL") == str(call + 1):
    target = pathlib.Path(os.environ["FAKE_LSOF_MUTATE_PATH"])
    action = os.environ.get("FAKE_LSOF_MUTATE_ACTION", "append")
    if action == "create":
        target.write_bytes(b"")
    elif action == "remove":
        target.unlink()
    elif action == "touch":
        metadata = target.stat()
        os.utime(
            target,
            ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 1_000_000_000),
        )
    else:
        with target.open("ab") as handle:
            handle.write(b"x")
statuses = os.environ.get("FAKE_LSOF_STATUSES")
if statuses:
    values = [int(value) for value in statuses.split(",")]
    status = values[min(call, len(values) - 1)]
else:
    status = int(os.environ.get("FAKE_LSOF_STATUS", "1"))
holder_call = os.environ.get("FAKE_LSOF_HOLDER_ON_CALL")
if (
    status == 0
    or os.environ.get("FAKE_LSOF_EMIT_HOLDER") == "1"
    or holder_call == str(call + 1)
):
    holders = json.loads(os.environ.get("FAKE_LSOF_HOLDERS", "null"))
    if holders is None:
        holders = [{"pid": "123", "path": paths[0]}]
    output = bytearray()
    for descriptor, holder in enumerate(holders, start=3):
        output.extend(
            f"p{holder['pid']}\\0f{descriptor}\\0n{holder['path']}\\0".encode()
        )
    sys.stdout.buffer.write(output)
raise SystemExit(status)
"""
        )
        fake_lsof.chmod(0o755)
        self.helper_harness = self.temp / "cache-helper-harness.py"
        self.helper_harness.write_text(
            """#!/usr/bin/env python3
import importlib.util
import pathlib
import sys

module_path = pathlib.Path(sys.argv[1])
lsof_path = sys.argv[2]
spec = importlib.util.spec_from_file_location("cache_helper_under_test", module_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {module_path}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.LSOF_PATH = lsof_path
sys.argv = [str(module_path), *sys.argv[3:]]
raise SystemExit(module.main())
"""
        )
        self.environment = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "FAKE_CBM_STATE": str(self.state),
            "FAKE_CBM_DELETED": str(self.deleted),
            "FAKE_CBM_ACTIVE": str(self.temp / "active"),
            "FAKE_CBM_MAX_ACTIVE": str(self.temp / "max-active"),
            "FAKE_EVENTS": str(self.events),
            "FAKE_CBM_LIST_CALLS": str(self.temp / "list-calls"),
            "FAKE_LSOF_CALLS": str(self.lsof_calls),
            "FAKE_LSOF_STATE": str(self.temp / "lsof-state"),
            "CBM_CACHE_DIR": str(self.cache),
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_projects(self, projects: list[dict[str, object]]) -> None:
        self.state.write_text(json.dumps(projects))

    def run_script(
        self, *args: str, check: bool = True, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SCRIPT), *args],
            check=check,
            capture_output=True,
            text=True,
            env=env or self.environment,
        )

    def run_helper(
        self, *args: str, check: bool = True, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        command_name = {"cache-audit": "audit", "cache-prune": "prune"}[args[0]]
        return subprocess.run(
            [
                sys.executable,
                str(self.helper_harness),
                str(MODULE_PATH),
                str(self.bin / "lsof"),
                command_name,
                *args[1:],
            ],
            check=check,
            capture_output=True,
            text=True,
            env=env or self.environment,
        )

    def audit(self, *extra: str) -> None:
        self.run_helper(
            "cache-audit",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
            *extra,
        )

    def apply(
        self,
        *,
        check: bool = True,
        env: dict[str, str] | None = None,
        allow_blocked: bool = False,
        protect: tuple[str, ...] = (),
        lsof_timeout: int | None = None,
    ):
        args = [
            "cache-prune",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
            "--apply",
        ]
        if allow_blocked:
            args.append("--allow-blocked-manifest")
        if lsof_timeout is not None:
            args.extend(("--lsof-timeout-seconds", str(lsof_timeout)))
        for name in protect:
            args.extend(("--protect-candidate", name))
        return self.run_helper(
            *args,
            check=check,
            env=env,
        )

    def rewrite_manifest(self, payload: dict[str, object]) -> None:
        payload["manifest_digest"] = CBM.manifest_digest(payload)
        self.manifest.write_text(json.dumps(payload))

    def add_ephemeral_candidate(self, name: str) -> pathlib.Path:
        missing = self.temp / "ephemeral" / name
        self.projects.append(
            {
                "name": name,
                "root_path": str(missing),
                "size_bytes": sqlite_file(self.cache / f"{name}.db"),
                "nodes": 1,
                "edges": 1,
            }
        )
        self.write_projects(self.projects)
        return missing

    def test_prune_is_dry_run_by_default(self) -> None:
        self.audit()
        result = self.run_helper(
            "cache-prune",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
        )
        self.assertFalse(self.deleted.exists())
        payload = json.loads(result.stdout)
        self.assertFalse(payload["applied"])
        self.assertEqual(payload["preflighted"], 1)
        self.assertEqual(payload["lsof_timeout_seconds"], 300)

    def test_prune_lsof_timeout_override_and_range(self) -> None:
        self.audit()
        result = self.run_helper(
            "cache-prune",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
            "--lsof-timeout-seconds",
            "45",
        )
        self.assertEqual(
            json.loads(result.stdout)["lsof_timeout_seconds"],
            45,
        )
        for value in ("29", "901", "not-a-number"):
            with self.subTest(value=value):
                invalid = self.run_helper(
                    "cache-prune",
                    "--manifest",
                    str(self.manifest),
                    "--cache-dir",
                    str(self.cache),
                    "--lsof-timeout-seconds",
                    value,
                    check=False,
                )
                self.assertEqual(invalid.returncode, 2)
                self.assertIn("--lsof-timeout-seconds", invalid.stderr)

    def test_unchanged_manifest_applies_through_delete_project(self) -> None:
        self.audit()
        result = self.apply()
        payload = json.loads(result.stdout)
        self.assertEqual(payload["deleted"][0]["name"], self.worktree_name)
        self.assertEqual(
            [item["name"] for item in payload["launched"]],
            [self.worktree_name],
        )
        self.assertEqual(
            [item["name"] for item in payload["verified_deleted"]],
            [self.worktree_name],
        )
        self.assertEqual(payload["failed"], [])
        self.assertEqual(payload["ambiguous"], [])
        self.assertEqual(payload["lsof_timeout_seconds"], 300)
        self.assertEqual(
            json.loads(self.deleted.read_text().strip())["project"],
            self.worktree_name,
        )
        remaining = json.loads(self.state.read_text())
        self.assertEqual([item["name"] for item in remaining], [self.main_name])
        self.assertFalse((self.cache / f"{self.worktree_name}.db").exists())
        events = self.events.read_text().splitlines()
        delete_index = events.index(f"delete-start:{self.worktree_name}")
        self.assertEqual(events[delete_index - 1], "lsof")

    def test_successful_holder_call_counts_match_batch_contract(self) -> None:
        self.audit()
        dry_run = self.run_helper(
            "cache-prune",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
        )
        self.assertEqual(json.loads(dry_run.stdout)["preflighted"], 1)
        self.assertEqual(
            int(pathlib.Path(self.environment["FAKE_LSOF_STATE"]).read_text()),
            2,
        )
        calls = [
            json.loads(line)
            for line in self.lsof_calls.read_text().splitlines()
        ]
        self.assertTrue(
            all(
                call[:4] == ["-nP", "-F0pfn", "-f", "--"]
                for call in calls
            )
        )
        self.assertEqual(
            calls[0][4:],
            [
                str(
                    self.cache.resolve()
                    / f"{self.worktree_name}.db"
                )
            ],
        )

        pathlib.Path(self.environment["FAKE_LSOF_STATE"]).unlink()
        self.lsof_calls.unlink()
        applied = self.apply()
        self.assertEqual(
            [item["name"] for item in json.loads(applied.stdout)["deleted"]],
            [self.worktree_name],
        )
        self.assertEqual(
            int(pathlib.Path(self.environment["FAKE_LSOF_STATE"]).read_text()),
            3,
        )

    def test_apply_uses_two_batch_sweeps_plus_one_probe_per_candidate(self) -> None:
        name = "fixture-z-ephemeral"
        self.add_ephemeral_candidate(name)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        result = self.apply()
        self.assertEqual(
            [item["name"] for item in json.loads(result.stdout)["deleted"]],
            [self.worktree_name, name],
        )
        self.assertEqual(
            int(pathlib.Path(self.environment["FAKE_LSOF_STATE"]).read_text()),
            3,
        )

    def test_eight_candidates_launch_before_wait_with_max_eight_active(
        self,
    ) -> None:
        for index in range(7):
            self.add_ephemeral_candidate(f"fixture-a-{index}")
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        manifest = json.loads(self.manifest.read_text())
        expected_names = [
            item["name"] for item in manifest["candidates"]
        ]
        environment = {
            **self.environment,
            "FAKE_CBM_WAIT_FOR_ACTIVE": "8",
        }

        result = self.apply(check=False, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            [item["name"] for item in payload["launched"]],
            expected_names,
        )
        self.assertEqual(
            int(
                pathlib.Path(
                    self.environment["FAKE_CBM_MAX_ACTIVE"]
                ).read_text()
            ),
            8,
        )
        events = self.events.read_text().splitlines()
        starts = [
            index
            for index, event in enumerate(events)
            if event.startswith("delete-start:")
        ]
        ends = [
            index
            for index, event in enumerate(events)
            if event.startswith("delete-end:")
        ]
        self.assertEqual(len(starts), 8)
        self.assertLess(max(starts), min(ends))

    def test_next_batch_waits_for_previous_verification(self) -> None:
        for index in range(8):
            self.add_ephemeral_candidate(f"fixture-a-{index}")
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        manifest = json.loads(self.manifest.read_text())
        expected_names = [
            item["name"] for item in manifest["candidates"]
        ]
        environment = {
            **self.environment,
            "FAKE_CBM_WAIT_FOR_ACTIVE": "8",
        }

        result = self.apply(check=False, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            [item["name"] for item in payload["verified_deleted"]],
            expected_names,
        )
        events = self.events.read_text().splitlines()
        next_start = events.index(f"delete-start:{expected_names[8]}")
        prior_end = max(
            index
            for index, event in enumerate(events[:next_start])
            if event.startswith("delete-end:")
        )
        self.assertIn(
            "list_projects",
            events[prior_end + 1 : next_start],
        )
        self.assertEqual(events[next_start - 1], "lsof")

    def test_sidecar_holder_blocks_final_batch_before_any_launch(self) -> None:
        name = "fixture-z-ephemeral"
        self.add_ephemeral_candidate(name)
        database = self.cache / f"{name}.db"
        sidecar = pathlib.Path(f"{database}-shm")
        sidecar.write_bytes(b"\0" * 32768)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        environment = {
            **self.environment,
            "FAKE_LSOF_HOLDER_ON_CALL": "3",
            "FAKE_LSOF_HOLDERS": json.dumps(
                [{"pid": "321", "path": str(sidecar.resolve())}]
            ),
        }

        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"candidate={name} kind=shm", result.stderr)
        self.assertFalse(self.deleted.exists())
        self.assertFalse(
            any(
                event.startswith("delete-start:")
                for event in self.events.read_text().splitlines()
            )
        )

    def test_sidecar_drift_during_final_lsof_blocks_all_launches(self) -> None:
        name = "fixture-z-ephemeral"
        self.add_ephemeral_candidate(name)
        database = self.cache / f"{name}.db"
        sidecar = pathlib.Path(f"{database}-shm")
        sidecar.write_bytes(b"\0" * 32768)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        environment = {
            **self.environment,
            "FAKE_LSOF_MUTATE_ON_CALL": "3",
            "FAKE_LSOF_MUTATE_PATH": str(sidecar),
            "FAKE_LSOF_MUTATE_ACTION": "touch",
        }

        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("during final holder sweep", result.stderr)
        self.assertFalse(self.deleted.exists())
        self.assertFalse(
            any(
                event.startswith("delete-start:")
                for event in self.events.read_text().splitlines()
            )
        )

    def test_nonzero_in_first_batch_drains_and_stops_future_batches(self) -> None:
        for index in range(8):
            self.add_ephemeral_candidate(f"fixture-a-{index}")
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        manifest = json.loads(self.manifest.read_text())
        names = [item["name"] for item in manifest["candidates"]]
        failed_name = names[0]
        future_name = names[8]
        environment = {
            **self.environment,
            "FAKE_CBM_DELETE_FAIL": failed_name,
            "FAKE_CBM_WAIT_FOR_ACTIVE": "8",
        }

        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"delete_project failed for {failed_name}", result.stderr)
        launched = [
            json.loads(line)["project"]
            for line in self.deleted.read_text().splitlines()
        ]
        self.assertEqual(set(launched), set(names[:8]))
        self.assertNotIn(future_name, launched)
        remaining = {
            item["name"] for item in json.loads(self.state.read_text())
        }
        self.assertIn(failed_name, remaining)
        self.assertIn(future_name, remaining)
        self.assertTrue(
            set(names[1:8]).isdisjoint(remaining)
        )

    def test_symlink_named_graph_is_a_guarded_alias_duplicate(self) -> None:
        alias = self.temp / "legacy-home" / "repo"
        alias.parent.mkdir()
        alias.symlink_to(self.main, target_is_directory=True)
        alias_name = "fixture-legacy-alias"
        alias_size = sqlite_file(self.cache / f"{alias_name}.db")
        self.projects.append(
            {
                "name": alias_name,
                "root_path": str(alias),
                "size_bytes": alias_size,
                "nodes": 1,
                "edges": 1,
            }
        )
        self.write_projects(self.projects)

        self.audit()
        payload = json.loads(self.manifest.read_text())
        alias_candidate = next(
            item
            for item in payload["candidates"]
            if item["name"] == alias_name
        )
        self.assertEqual(alias_candidate["reason"], "canonical_alias_duplicate")
        self.assertEqual(alias_candidate["canonical_project"], self.main_name)

        result = self.apply()
        deleted = json.loads(result.stdout)["deleted"]
        self.assertIn(alias_name, [item["name"] for item in deleted])
        self.assertIn(
            self.main_name,
            [item["name"] for item in json.loads(self.state.read_text())],
        )

    def test_only_symlink_named_graph_is_preserved(self) -> None:
        alias = self.temp / "legacy-home" / "repo"
        alias.parent.mkdir()
        alias.symlink_to(self.main, target_is_directory=True)
        alias_name = "fixture-legacy-alias"
        self.projects = [
            {
                "name": alias_name,
                "root_path": str(alias),
                "size_bytes": sqlite_file(self.cache / f"{alias_name}.db"),
                "nodes": 1,
                "edges": 1,
            }
        ]
        self.write_projects(self.projects)
        self.audit()
        payload = json.loads(self.manifest.read_text())
        self.assertFalse(payload["candidates"])
        self.assertEqual(payload["protected"][0]["reason"], "canonical_root")

    def test_modified_manifest_is_rejected(self) -> None:
        self.audit()
        payload = json.loads(self.manifest.read_text())
        payload["candidates"][0]["size_bytes"] += 1
        self.manifest.write_text(json.dumps(payload))
        result = self.apply(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest digest mismatch", result.stderr)

    def test_held_database_stops_preflight_without_delete(self) -> None:
        self.audit()
        environment = {**self.environment, "FAKE_LSOF_STATUS": "0"}
        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project DB is held", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_holder_after_validation_stops_preflight_without_delete(self) -> None:
        self.audit()
        environment = {
            **self.environment,
            "FAKE_LSOF_STATUSES": "1,0",
        }
        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project DB is held", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_clean_wal_mode_database_passes_repeatedly_without_sidecars(self) -> None:
        database = self.cache / f"{self.worktree_name}.db"
        connection = sqlite3.connect(database)
        try:
            mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()
        finally:
            connection.close()
        self.assertEqual(mode, ("wal",))
        sidecars = (
            pathlib.Path(f"{database}-wal"),
            pathlib.Path(f"{database}-shm"),
        )
        self.assertFalse(any(path.exists() for path in sidecars))
        self.projects[1]["size_bytes"] = database.stat().st_size
        self.write_projects(self.projects)
        self.audit()

        for _ in range(2):
            result = self.run_helper(
                "cache-prune",
                "--manifest",
                str(self.manifest),
                "--cache-dir",
                str(self.cache),
            )
            self.assertEqual(json.loads(result.stdout)["preflighted"], 1)
            self.assertFalse(any(path.exists() for path in sidecars))
        self.assertFalse(self.deleted.exists())

    def test_zero_wal_and_stable_shm_pass_unchanged(self) -> None:
        database = self.cache / f"{self.worktree_name}.db"
        pathlib.Path(f"{database}-wal").write_bytes(b"")
        pathlib.Path(f"{database}-shm").write_bytes(b"\0" * 32768)
        before = CBM.cache_fingerprint(database)
        self.audit()

        for _ in range(2):
            result = self.run_helper(
                "cache-prune",
                "--manifest",
                str(self.manifest),
                "--cache-dir",
                str(self.cache),
            )
            self.assertEqual(json.loads(result.stdout)["preflighted"], 1)
            self.assertEqual(CBM.cache_fingerprint(database), before)
        first_call = json.loads(self.lsof_calls.read_text().splitlines()[0])
        self.assertEqual(
            first_call[4:],
            [
                str(database.resolve()),
                str(pathlib.Path(f"{database}-wal").resolve()),
                str(pathlib.Path(f"{database}-shm").resolve()),
            ],
        )
        self.assertFalse(self.deleted.exists())

    def test_absent_sidecar_created_during_before_sweep_fails(self) -> None:
        database = self.cache / f"{self.worktree_name}.db"
        sidecar = pathlib.Path(f"{database}-shm")
        self.audit()
        environment = {
            **self.environment,
            "FAKE_LSOF_MUTATE_ON_CALL": "1",
            "FAKE_LSOF_MUTATE_PATH": str(sidecar),
            "FAKE_LSOF_MUTATE_ACTION": "create",
        }
        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("during the before-holder sweep", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_existing_sidecar_metadata_drift_during_before_sweep_fails(
        self,
    ) -> None:
        database = self.cache / f"{self.worktree_name}.db"
        sidecar = pathlib.Path(f"{database}-shm")
        sidecar.write_bytes(b"\0" * 32768)
        self.audit()
        environment = {
            **self.environment,
            "FAKE_LSOF_MUTATE_ON_CALL": "1",
            "FAKE_LSOF_MUTATE_PATH": str(sidecar),
            "FAKE_LSOF_MUTATE_ACTION": "touch",
        }
        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("during the before-holder sweep", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_existing_sidecar_removed_during_after_sweep_fails(self) -> None:
        database = self.cache / f"{self.worktree_name}.db"
        sidecar = pathlib.Path(f"{database}-shm")
        sidecar.write_bytes(b"\0" * 32768)
        self.audit()
        environment = {
            **self.environment,
            "FAKE_LSOF_MUTATE_ON_CALL": "2",
            "FAKE_LSOF_MUTATE_PATH": str(sidecar),
            "FAKE_LSOF_MUTATE_ACTION": "remove",
        }
        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("during the after-holder sweep", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_nonzero_orphan_wal_stops_before_delete(self) -> None:
        database = self.cache / f"{self.worktree_name}.db"
        pathlib.Path(f"{database}-wal").write_bytes(b"orphan")
        self.audit()
        result = self.apply(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project WAL is nonzero", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_sidecar_symlink_or_nonregular_file_stops_before_delete(self) -> None:
        database = self.cache / f"{self.worktree_name}.db"
        target = self.temp / "sidecar-target"
        target.write_bytes(b"target")
        self.audit()

        for suffix in ("-wal", "-shm"):
            sidecar = pathlib.Path(f"{database}{suffix}")
            with self.subTest(suffix=suffix, kind="symlink"):
                sidecar.symlink_to(target)
                result = self.apply(check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("non-regular or symlinked", result.stderr)
                self.assertFalse(self.deleted.exists())
                sidecar.unlink()
            with self.subTest(suffix=suffix, kind="directory"):
                sidecar.mkdir()
                result = self.apply(check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("non-regular or symlinked", result.stderr)
                self.assertFalse(self.deleted.exists())
                sidecar.rmdir()

    def test_corrupt_later_candidate_stops_preflight_without_delete(self) -> None:
        name = "fixture-z-corrupt"
        self.add_ephemeral_candidate(name)
        corrupt = self.cache / f"{name}.db"
        size = corrupt.stat().st_size
        corrupt.write_bytes(b"x" * size)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        result = self.apply(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("corrupt", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_protect_candidate_rejects_duplicate_unknown_and_non_candidate(self) -> None:
        self.audit()
        cases = {
            "duplicate": (
                (self.worktree_name, self.worktree_name),
                "duplicate --protect-candidate",
            ),
            "unknown": (("fixture-missing",), "unknown --protect-candidate"),
            "non-candidate": (
                (self.main_name,),
                "not a manifest candidate",
            ),
        }
        for name, (protected, message) in cases.items():
            with self.subTest(name=name):
                result = self.apply(
                    check=False,
                    protect=protected,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(self.deleted.exists())

    def test_protected_candidates_follow_manifest_order(self) -> None:
        first_name = "fixture-a-protected"
        last_name = "fixture-z-protected"
        first_root = self.add_ephemeral_candidate(first_name)
        last_root = self.add_ephemeral_candidate(last_name)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))

        dry_run = self.run_helper(
            "cache-prune",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
            "--protect-candidate",
            last_name,
            "--protect-candidate",
            first_name,
        )
        payload = json.loads(dry_run.stdout)
        self.assertEqual(
            [item["name"] for item in payload["runtime_protected"]],
            [first_name, last_name],
        )

        first_root.mkdir(parents=True)
        last_root.mkdir(parents=True)
        applied = self.apply(
            check=False,
            protect=(last_name, first_name),
        )
        self.assertNotEqual(applied.returncode, 0)
        self.assertIn(first_name, applied.stderr)
        self.assertNotIn(last_name, applied.stderr)
        self.assertFalse(self.deleted.exists())

    def test_all_candidates_can_be_protected_on_apply(self) -> None:
        self.audit()
        before_projects = self.state.read_text()
        database = self.cache / f"{self.worktree_name}.db"
        before_cache = CBM.cache_fingerprint(database)

        applied = self.apply(protect=(self.worktree_name,))
        payload = json.loads(applied.stdout)

        self.assertTrue(payload["applied"])
        self.assertEqual(payload["eligible_candidates"], 0)
        self.assertEqual(payload["eligible_candidate_bytes"], 0)
        self.assertEqual(payload["preflighted"], 0)
        self.assertEqual(payload["preflighted_bytes"], 0)
        self.assertEqual(payload["deleted"], [])
        self.assertEqual(payload["deleted_bytes"], 0)
        self.assertEqual(
            [item["name"] for item in payload["runtime_protected"]],
            [self.worktree_name],
        )
        self.assertEqual(self.state.read_text(), before_projects)
        self.assertEqual(CBM.cache_fingerprint(database), before_cache)
        self.assertFalse(self.deleted.exists())
        self.assertFalse(
            pathlib.Path(self.environment["FAKE_LSOF_STATE"]).exists()
        )
        self.assertFalse(self.lsof_calls.exists())

    def test_protected_corrupt_candidate_leaves_exact_data_untouched(self) -> None:
        corrupt_name = "fixture-a-corrupt"
        clean_name = "fixture-z-clean"
        self.add_ephemeral_candidate(corrupt_name)
        self.add_ephemeral_candidate(clean_name)
        corrupt_database = self.cache / f"{corrupt_name}.db"
        corrupt_database.write_bytes(b"x" * corrupt_database.stat().st_size)
        pathlib.Path(f"{corrupt_database}-wal").write_bytes(b"orphan")
        pathlib.Path(f"{corrupt_database}-shm").write_bytes(b"\0" * 32768)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        manifest = json.loads(self.manifest.read_text())
        corrupt_candidate = next(
            item
            for item in manifest["candidates"]
            if item["name"] == corrupt_name
        )
        eligible = [
            item
            for item in manifest["candidates"]
            if item["name"] != corrupt_name
        ]
        before = CBM.cache_fingerprint(corrupt_database)
        expected_summary = {
            "candidates": len(manifest["candidates"]),
            "candidate_bytes": sum(
                item["size_bytes"] for item in manifest["candidates"]
            ),
            "manifest_candidates": len(manifest["candidates"]),
            "manifest_candidate_bytes": sum(
                item["size_bytes"] for item in manifest["candidates"]
            ),
            "eligible_candidates": len(eligible),
            "eligible_candidate_bytes": sum(
                item["size_bytes"] for item in eligible
            ),
            "preflighted": len(eligible),
            "preflighted_bytes": sum(item["size_bytes"] for item in eligible),
            "runtime_protected": [
                {
                    "name": corrupt_name,
                    "reason": corrupt_candidate["reason"],
                    "bytes": corrupt_candidate["size_bytes"],
                }
            ],
            "runtime_protected_bytes": corrupt_candidate["size_bytes"],
        }

        dry_run = self.run_helper(
            "cache-prune",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
            "--protect-candidate",
            corrupt_name,
        )
        dry_payload = json.loads(dry_run.stdout)
        for key, value in expected_summary.items():
            self.assertEqual(dry_payload[key], value)
        self.assertFalse(self.deleted.exists())
        self.assertEqual(CBM.cache_fingerprint(corrupt_database), before)

        applied = self.apply(protect=(corrupt_name,))
        applied_payload = json.loads(applied.stdout)
        for key, value in expected_summary.items():
            self.assertEqual(applied_payload[key], value)
        self.assertEqual(
            [item["name"] for item in applied_payload["deleted"]],
            [self.worktree_name, clean_name],
        )
        remaining = {
            item["name"] for item in json.loads(self.state.read_text())
        }
        self.assertEqual(remaining, {self.main_name, corrupt_name})
        self.assertEqual(CBM.cache_fingerprint(corrupt_database), before)
        lsof_argv = [
            argument
            for line in self.lsof_calls.read_text().splitlines()
            for argument in json.loads(line)
        ]
        self.assertFalse(
            any(corrupt_name in argument for argument in lsof_argv)
        )

    def test_protected_ephemeral_root_reappearing_fails(self) -> None:
        name = "fixture-protected-ephemeral"
        missing = self.add_ephemeral_candidate(name)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        missing.mkdir(parents=True)
        result = self.apply(check=False, protect=(name,))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ephemeral root became live", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_protected_candidate_classification_drift_fails(self) -> None:
        self.audit()
        command(
            "git",
            "-C",
            str(self.main),
            "worktree",
            "remove",
            "--force",
            str(self.worktree),
        )
        command("git", "clone", "-q", str(self.main), str(self.worktree))
        result = self.apply(
            check=False,
            protect=(self.worktree_name,),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("candidate canonical root changed", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_project_snapshot_change_stops_apply(self) -> None:
        self.audit()
        changed = json.loads(self.state.read_text())
        changed[1]["size_bytes"] += 1
        self.write_projects(changed)
        result = self.apply(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest drift", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_reappeared_ephemeral_root_stops_preflight_without_delete(self) -> None:
        missing = self.add_ephemeral_candidate("fixture-z-ephemeral")
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        missing.mkdir(parents=True)
        result = self.apply(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ephemeral root became live", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_missing_live_root_and_canonical_root_stop_apply(self) -> None:
        for removed in ("worktree", "main"):
            with self.subTest(removed=removed):
                self.audit()
                target = self.worktree if removed == "worktree" else self.main
                renamed = target.with_name(f"{target.name}.moved")
                target.rename(renamed)
                try:
                    result = self.apply(check=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(self.deleted.exists())
                finally:
                    renamed.rename(target)

    def test_clone_health_change_stops_preflight_without_delete(self) -> None:
        self.audit()
        command(
            "git",
            "-C",
            str(self.main),
            "config",
            "remote.origin.promisor",
            "true",
        )
        try:
            result = self.apply(check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical clone is not full", result.stderr)
            self.assertFalse(self.deleted.exists())
        finally:
            command(
                "git",
                "-C",
                str(self.main),
                "config",
                "--unset",
                "remote.origin.promisor",
            )

    def test_protection_does_not_bypass_eligible_holder(self) -> None:
        protected = "fixture-protected"
        self.add_ephemeral_candidate(protected)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        environment = {**self.environment, "FAKE_LSOF_STATUS": "0"}
        result = self.apply(
            check=False,
            env=environment,
            protect=(protected,),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project DB is held", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_protection_does_not_bypass_eligible_wal(self) -> None:
        protected = "fixture-protected"
        self.add_ephemeral_candidate(protected)
        database = self.cache / f"{self.worktree_name}.db"
        pathlib.Path(f"{database}-wal").write_bytes(b"orphan")
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        result = self.apply(check=False, protect=(protected,))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project WAL is nonzero", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_protection_does_not_bypass_eligible_clone_health(self) -> None:
        protected = "fixture-protected"
        self.add_ephemeral_candidate(protected)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        command(
            "git",
            "-C",
            str(self.main),
            "config",
            "remote.origin.promisor",
            "true",
        )
        try:
            result = self.apply(check=False, protect=(protected,))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical clone is not full", result.stderr)
            self.assertFalse(self.deleted.exists())
        finally:
            command(
                "git",
                "-C",
                str(self.main),
                "config",
                "--unset",
                "remote.origin.promisor",
            )

    def test_protection_does_not_bypass_eligible_canonical_mapping(self) -> None:
        protected = "fixture-protected"
        self.add_ephemeral_candidate(protected)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        command(
            "git",
            "-C",
            str(self.main),
            "worktree",
            "remove",
            "--force",
            str(self.worktree),
        )
        command("git", "clone", "-q", str(self.main), str(self.worktree))
        result = self.apply(check=False, protect=(protected,))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("candidate canonical root changed", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_protection_does_not_bypass_snapshot_drift(self) -> None:
        protected = "fixture-protected"
        self.add_ephemeral_candidate(protected)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        changed = json.loads(self.state.read_text())
        next(
            item for item in changed if item["name"] == self.worktree_name
        )["size_bytes"] += 1
        self.write_projects(changed)
        result = self.apply(check=False, protect=(protected,))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest drift", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_holder_opened_after_final_revalidation_stops_before_delete(self) -> None:
        self.audit()
        environment = {
            **self.environment,
            "FAKE_LSOF_STATUSES": "1,1,0",
        }
        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project DB is held", result.stderr)
        self.assertIn("already_deleted=[]", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_fingerprint_change_after_preflight_stops_before_delete(self) -> None:
        self.audit()
        list_calls = pathlib.Path(self.environment["FAKE_CBM_LIST_CALLS"])
        list_calls.write_text("0")
        environment = {
            **self.environment,
            "FAKE_CBM_MUTATE_ON_LIST_CALL": "3",
            "FAKE_CBM_MUTATE_PATH": str(
                self.cache / f"{self.worktree_name}.db"
            ),
        }
        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fingerprint changed", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_sidecar_change_after_preflight_stops_before_delete(self) -> None:
        database = self.cache / f"{self.worktree_name}.db"
        sidecar = pathlib.Path(f"{database}-shm")
        sidecar.write_bytes(b"\0" * 32768)
        self.audit()
        list_calls = pathlib.Path(self.environment["FAKE_CBM_LIST_CALLS"])
        list_calls.write_text("0")
        environment = {
            **self.environment,
            "FAKE_CBM_MUTATE_ON_LIST_CALL": "3",
            "FAKE_CBM_MUTATE_PATH": str(sidecar),
        }
        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fingerprint changed", result.stderr)
        self.assertFalse(self.deleted.exists())

    def test_delete_failure_reports_prior_deletion(self) -> None:
        failing = "fixture-z-delete-fail"
        self.add_ephemeral_candidate(failing)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        environment = {
            **self.environment,
            "FAKE_CBM_DELETE_FAIL": failing,
        }
        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("delete_project failed", result.stderr)
        self.assertIn(
            f'already_deleted=["{self.worktree_name}"]',
            result.stderr,
        )

    def test_database_and_sidecar_residue_stop_apply(self) -> None:
        self.audit()
        environment = {
            **self.environment,
            "FAKE_CBM_RESIDUE_DB": "1",
            "FAKE_CBM_RESIDUE_SUFFIXES": "wal,shm",
        }
        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project cache residue remains", result.stderr)
        self.assertIn('"verified_deleted":[]', result.stderr)
        database = self.cache / f"{self.worktree_name}.db"
        residue = (
            database,
            pathlib.Path(f"{database}-wal"),
            pathlib.Path(f"{database}-shm"),
        )
        for path in residue:
            self.assertTrue(path.exists())

    def test_retained_registration_drains_batch_and_reports_failure(self) -> None:
        name = "fixture-z-clean"
        self.add_ephemeral_candidate(name)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        environment = {
            **self.environment,
            "FAKE_CBM_RETAIN_NAME": self.worktree_name,
            "FAKE_CBM_WAIT_FOR_ACTIVE": "2",
        }

        result = self.apply(check=False, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            f"deleted project remains registered: {self.worktree_name}",
            result.stderr,
        )
        self.assertIn('"verified_deleted":[', result.stderr)
        remaining = {
            item["name"] for item in json.loads(self.state.read_text())
        }
        self.assertIn(self.worktree_name, remaining)
        self.assertNotIn(name, remaining)
        events = self.events.read_text().splitlines()
        self.assertIn(f"delete-end:{self.worktree_name}", events)
        self.assertIn(f"delete-end:{name}", events)

    def test_ephemeral_prefix_guards_missing_roots(self) -> None:
        missing = self.temp / "ephemeral" / "gone"
        name = "fixture-ephemeral"
        size = sqlite_file(self.cache / f"{name}.db")
        self.projects.append(
            {
                "name": name,
                "root_path": str(missing),
                "size_bytes": size,
                "nodes": 1,
                "edges": 1,
            }
        )
        self.write_projects(self.projects)
        self.audit("--ephemeral-prefix", str(self.temp / "ephemeral"))
        payload = json.loads(self.manifest.read_text())
        self.assertIn(name, [item["name"] for item in payload["candidates"]])

        unsafe = self.run_helper(
            "cache-audit",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
            "--ephemeral-prefix",
            "/",
            check=False,
        )
        self.assertNotEqual(unsafe.returncode, 0)
        self.assertIn("unsafe ephemeral prefix", unsafe.stderr)

    def test_prune_rejects_unsafe_or_non_normalized_manifest_prefixes(self) -> None:
        prefix = self.temp / "ephemeral"
        self.add_ephemeral_candidate("fixture-ephemeral")
        self.audit("--ephemeral-prefix", str(prefix))
        unsafe_prefixes = {
            "root": "/",
            "home": str(pathlib.Path.home()),
            "cache": str(self.cache),
            "relative": "relative/path",
            "non-normalized": str(prefix / ".." / "other"),
            "unexpanded-home": "~/ephemeral",
        }
        for name, unsafe_prefix in unsafe_prefixes.items():
            with self.subTest(name=name):
                payload = json.loads(self.manifest.read_text())
                payload["ephemeral_prefixes"] = [unsafe_prefix]
                self.rewrite_manifest(payload)
                result = self.apply(check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ephemeral prefix", result.stderr)
                self.assertFalse(self.deleted.exists())

    def test_allow_blocked_manifest_is_rejected_outside_cache_prune(self) -> None:
        commands = (
            "init",
            "index",
            "canonical",
            "start-ui",
            "stop-ui",
            "status",
            "schema",
            "cache-audit",
            "keepalive",
        )
        for command_name in commands:
            with self.subTest(command=command_name):
                result = self.run_script(
                    command_name,
                    "--allow-blocked-manifest",
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(
                    "--allow-blocked-manifest is valid only with cache-prune",
                    result.stderr,
                )

    def test_protect_candidate_is_rejected_outside_cache_prune(self) -> None:
        commands = (
            "init",
            "index",
            "canonical",
            "start-ui",
            "stop-ui",
            "status",
            "schema",
            "cache-audit",
            "keepalive",
        )
        for command_name in commands:
            with self.subTest(command=command_name):
                result = self.run_script(
                    command_name,
                    "--protect-candidate",
                    self.worktree_name,
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(
                    "--protect-candidate is valid only with cache-prune",
                    result.stderr,
                )

    def test_lsof_timeout_is_rejected_outside_cache_prune(self) -> None:
        commands = (
            "init",
            "index",
            "canonical",
            "start-ui",
            "stop-ui",
            "status",
            "schema",
            "cache-audit",
            "keepalive",
        )
        for command_name in commands:
            with self.subTest(command=command_name):
                result = self.run_script(
                    command_name,
                    "--lsof-timeout-seconds",
                    "45",
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(
                    "--lsof-timeout-seconds is valid only with cache-prune",
                    result.stderr,
                )

    def test_shell_forwards_repeated_protected_candidates_exactly(self) -> None:
        argv_bin = self.temp / "argv-bin"
        argv_bin.mkdir()
        argv_file = self.temp / "python-argv"
        fake_python = argv_bin / "python3"
        fake_python.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$@" > "$FAKE_PYTHON_ARGV"\n'
        )
        fake_python.chmod(0o755)
        environment = {
            **self.environment,
            "PATH": f"{argv_bin}:{self.bin}:{os.environ['PATH']}",
            "FAKE_PYTHON_ARGV": str(argv_file),
        }
        result = self.run_script(
            "cache-prune",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
            "--apply",
            "--allow-blocked-manifest",
            "--lsof-timeout-seconds",
            "45",
            "--protect-candidate",
            "fixture-first",
            "--protect-candidate",
            "fixture-second",
            env=environment,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            argv_file.read_text().splitlines(),
            [
                str(
                    ROOT
                    / "skills"
                    / "codebase-memory-mcp"
                    / "scripts"
                    / "codebase_memory_cache.py"
                ),
                "prune",
                "--manifest",
                str(self.manifest),
                "--cache-dir",
                str(self.cache),
                "--apply",
                "--allow-blocked-manifest",
                "--lsof-timeout-seconds",
                "45",
                "--protect-candidate",
                "fixture-first",
                "--protect-candidate",
                "fixture-second",
            ],
        )

    def test_unmapped_live_root_blocks_the_host(self) -> None:
        invalid_root = self.temp / "invalid-live-root"
        invalid_root.mkdir()
        name = "fixture-invalid"
        size = sqlite_file(self.cache / f"{name}.db")
        self.projects.append(
            {
                "name": name,
                "root_path": str(invalid_root),
                "size_bytes": size,
                "nodes": 1,
                "edges": 1,
            }
        )
        self.write_projects(self.projects)
        self.audit()
        result = self.run_helper(
            "cache-prune",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("host cache manifest is blocked", result.stderr)

        dry_run = self.run_helper(
            "cache-prune",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
            "--allow-blocked-manifest",
        )
        dry_payload = json.loads(dry_run.stdout)
        self.assertFalse(dry_payload["applied"])
        self.assertEqual(dry_payload["preflighted"], 1)
        self.assertFalse(self.deleted.exists())

        applied = self.apply(allow_blocked=True)
        applied_payload = json.loads(applied.stdout)
        self.assertEqual(
            [item["name"] for item in applied_payload["deleted"]],
            [self.worktree_name],
        )
        remaining = {
            item["name"] for item in json.loads(self.state.read_text())
        }
        self.assertEqual(remaining, {self.main_name, name})
        self.assertTrue((self.cache / f"{name}.db").exists())

    def test_protected_candidate_does_not_bypass_manifest_blockers(self) -> None:
        invalid_root = self.temp / "invalid-live-root"
        invalid_root.mkdir()
        name = "fixture-invalid"
        self.projects.append(
            {
                "name": name,
                "root_path": str(invalid_root),
                "size_bytes": sqlite_file(self.cache / f"{name}.db"),
                "nodes": 1,
                "edges": 1,
            }
        )
        self.write_projects(self.projects)
        self.audit()

        blocked = self.apply(
            check=False,
            protect=(self.worktree_name,),
        )
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("host cache manifest is blocked", blocked.stderr)
        self.assertFalse(self.deleted.exists())

        allowed = self.run_helper(
            "cache-prune",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
            "--allow-blocked-manifest",
            "--protect-candidate",
            self.worktree_name,
        )
        payload = json.loads(allowed.stdout)
        self.assertEqual(payload["eligible_candidates"], 0)
        self.assertEqual(
            [item["name"] for item in payload["runtime_protected"]],
            [self.worktree_name],
        )

    def test_malformed_manifest_relationships_are_rejected(self) -> None:
        mutations = {
            "blockers": lambda payload: payload["blockers"].append(
                payload["protected"][0]
            ),
            "overlap": lambda payload: payload["candidates"].append(
                payload["protected"][0]
            ),
            "partition": lambda payload: payload["protected"].pop(0),
            "duplicates": lambda payload: payload["candidates"].append(
                payload["candidates"][0]
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                self.audit()
                payload = json.loads(self.manifest.read_text())
                mutate(payload)
                self.rewrite_manifest(payload)
                result = self.apply(check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("manifest", result.stderr)
                self.assertFalse(self.deleted.exists())

    def test_manifest_digest_is_stable_for_payload(self) -> None:
        self.audit()
        payload = json.loads(self.manifest.read_text())
        digest = payload.pop("manifest_digest")
        expected = hashlib.sha256(CBM.canonical_json(payload)).hexdigest()
        self.assertEqual(digest, expected)


if __name__ == "__main__":
    unittest.main()
