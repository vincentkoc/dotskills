from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import sqlite3
import subprocess
import tempfile
import unittest


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


class CacheManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = pathlib.Path(self.temporary.name)
        self.main = self.temp / "main"
        self.worktree = self.temp / "worktree"
        self.cache = self.temp / "cache"
        self.state = self.temp / "projects.json"
        self.deleted = self.temp / "deleted.jsonl"
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
import json, os, pathlib, sys
state = pathlib.Path(os.environ["FAKE_CBM_STATE"])
payload = json.loads(state.read_text())
if sys.argv[1:3] == ["cli", "list_projects"]:
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
    deleted = pathlib.Path(os.environ["FAKE_CBM_DELETED"])
    with deleted.open("a") as handle:
        handle.write(json.dumps({"project": name}) + "\\n")
    if os.environ.get("FAKE_CBM_DELETE_FAIL") == name:
        print(f"forced delete failure: {name}", file=sys.stderr)
        raise SystemExit(1)
    state.write_text(json.dumps([item for item in payload if item["name"] != name]))
    database = pathlib.Path(os.environ["CBM_CACHE_DIR"]) / f"{name}.db"
    for suffix in ("", "-wal", "-shm"):
        pathlib.Path(f"{database}{suffix}").unlink(missing_ok=True)
    for suffix in os.environ.get("FAKE_CBM_RESIDUE_SUFFIXES", "").split(","):
        if suffix:
            pathlib.Path(f"{database}-{suffix}").write_bytes(b"residue")
    if os.environ.get("FAKE_CBM_RESIDUE_DB") == "1":
        database.write_bytes(b"residue")
    raise SystemExit(0)
raise SystemExit(2)
"""
        )
        fake_cbm.chmod(0o755)
        fake_lsof = self.bin / "lsof"
        fake_lsof.write_text(
            """#!/usr/bin/env python3
import os, pathlib, sys
state = pathlib.Path(os.environ["FAKE_LSOF_STATE"])
call = int(state.read_text()) if state.exists() else 0
state.write_text(str(call + 1))
statuses = os.environ.get("FAKE_LSOF_STATUSES")
if statuses:
    values = [int(value) for value in statuses.split(",")]
    status = values[min(call, len(values) - 1)]
else:
    status = int(os.environ.get("FAKE_LSOF_STATUS", "1"))
if status == 0:
    print("p123")
raise SystemExit(status)
"""
        )
        fake_lsof.chmod(0o755)
        self.environment = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "FAKE_CBM_STATE": str(self.state),
            "FAKE_CBM_DELETED": str(self.deleted),
            "FAKE_CBM_LIST_CALLS": str(self.temp / "list-calls"),
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

    def audit(self, *extra: str) -> None:
        self.run_script(
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
        return self.run_script(
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
        result = self.run_script(
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

    def test_unchanged_manifest_applies_through_delete_project(self) -> None:
        self.audit()
        result = self.apply()
        payload = json.loads(result.stdout)
        self.assertEqual(payload["deleted"][0]["name"], self.worktree_name)
        self.assertEqual(
            json.loads(self.deleted.read_text().strip())["project"],
            self.worktree_name,
        )
        remaining = json.loads(self.state.read_text())
        self.assertEqual([item["name"] for item in remaining], [self.main_name])
        self.assertFalse((self.cache / f"{self.worktree_name}.db").exists())

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

    def test_holder_opened_after_final_revalidation_stops_before_delete(self) -> None:
        self.audit()
        environment = {
            **self.environment,
            "FAKE_LSOF_STATUSES": "1,0",
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
        self.assertIn(
            f'already_deleted=["{self.worktree_name}"]',
            result.stderr,
        )
        database = self.cache / f"{self.worktree_name}.db"
        residue = (
            database,
            pathlib.Path(f"{database}-wal"),
            pathlib.Path(f"{database}-shm"),
        )
        for path in residue:
            self.assertTrue(path.exists())

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

        unsafe = self.run_script(
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
        result = self.run_script(
            "cache-prune",
            "--manifest",
            str(self.manifest),
            "--cache-dir",
            str(self.cache),
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("host cache manifest is blocked", result.stderr)

        dry_run = self.run_script(
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
