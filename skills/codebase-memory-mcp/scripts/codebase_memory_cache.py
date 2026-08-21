#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import errno
import hashlib
import json
import math
import os
import pathlib
import shutil
import socket
import sqlite3
import stat
import struct
import subprocess
import sys
import time
import urllib.parse
from typing import Any


SCHEMA_VERSION = 1
LSOF_ARGV_BUDGET = 128 * 1024
LSOF_PATH = "/usr/sbin/lsof"
LSOF_TIMEOUT_SECONDS = 300
LSOF_TIMEOUT_MIN_SECONDS = 30
LSOF_TIMEOUT_MAX_SECONDS = 900
DELETE_BATCH_MAX_CANDIDATES = 8
DELETE_BATCH_TIMEOUT_SECONDS = 600
HOST_BLOCKING_REASONS = {
    "canonical_clone_not_full",
    "empty_root",
    "live_root_unmapped",
    "missing_canonical_graph",
}


class SafetyError(RuntimeError):
    pass


class DeleteBatchError(SafetyError):
    def __init__(
        self,
        message: str,
        *,
        report: dict[str, Any],
        expected_snapshot: list[dict[str, Any]],
        projects: list[dict[str, Any]],
    ):
        super().__init__(message)
        self.report = report
        self.expected_snapshot = expected_snapshot
        self.projects = projects


def run(
    command: list[str],
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise SafetyError(f"{' '.join(command[:3])}: {detail}")
    return result


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in (
        "GIT_COMMON_DIR",
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_WORK_TREE",
    ):
        env.pop(name, None)
    return env


def git(path: pathlib.Path, *args: str) -> str:
    return run(["git", "-C", str(path), *args], env=git_env()).stdout.strip()


def absolute_git_path(root: pathlib.Path, option: str) -> pathlib.Path:
    result = run(
        ["git", "-C", str(root), "rev-parse", "--path-format=absolute", option],
        check=False,
        env=git_env(),
    )
    if result.returncode == 0:
        return pathlib.Path(result.stdout.strip()).resolve()
    value = git(root, "rev-parse", option)
    path = pathlib.Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def worktree_paths(root: pathlib.Path) -> list[pathlib.Path]:
    result = run(
        ["git", "-C", str(root), "worktree", "list", "--porcelain", "-z"],
        env=git_env(),
    )
    paths: list[pathlib.Path] = []
    for field in result.stdout.split("\0"):
        if field.startswith("worktree "):
            paths.append(pathlib.Path(field.removeprefix("worktree ")).resolve())
    return paths


def clone_health(root: pathlib.Path) -> dict[str, Any]:
    shallow = git(root, "rev-parse", "--is-shallow-repository") == "true"
    promisor = (
        run(
            ["git", "-C", str(root), "config", "--bool", "--get", "remote.origin.promisor"],
            check=False,
            env=git_env(),
        ).stdout.strip()
        == "true"
    )
    partial_filter = run(
        ["git", "-C", str(root), "config", "--get", "remote.origin.partialclonefilter"],
        check=False,
        env=git_env(),
    ).stdout.strip()
    return {
        "shallow": shallow,
        "promisor": promisor,
        "partial_filter": partial_filter,
        "full": not shallow and not promisor and not partial_filter,
    }


def resolve_repository(path: str | os.PathLike[str]) -> dict[str, Any]:
    requested = pathlib.Path(path).expanduser()
    if not requested.exists() or not requested.is_dir():
        raise SafetyError(f"repository path is missing or not a directory: {requested}")
    requested = requested.resolve()
    if git(requested, "rev-parse", "--is-inside-work-tree") != "true":
        raise SafetyError(f"not a Git worktree: {requested}")
    if git(requested, "rev-parse", "--is-bare-repository") == "true":
        raise SafetyError(f"bare repositories are not indexable: {requested}")

    root = pathlib.Path(git(requested, "rev-parse", "--show-toplevel")).resolve()
    common_dir = absolute_git_path(root, "--git-common-dir")
    git_dir = absolute_git_path(root, "--git-dir")
    canonical = root

    if git_dir != common_dir:
        owners: list[pathlib.Path] = []
        for candidate in worktree_paths(root):
            if not candidate.is_dir():
                continue
            try:
                candidate_root = pathlib.Path(
                    git(candidate, "rev-parse", "--show-toplevel")
                ).resolve()
                candidate_git_dir = absolute_git_path(candidate_root, "--git-dir")
                candidate_common_dir = absolute_git_path(
                    candidate_root, "--git-common-dir"
                )
            except SafetyError:
                continue
            if candidate_git_dir == common_dir and candidate_common_dir == common_dir:
                owners.append(candidate_root)
        owners = sorted(set(owners))
        if len(owners) != 1:
            raise SafetyError(
                f"cannot identify one owning checkout for Git common dir {common_dir}"
            )
        canonical = owners[0]

    if not canonical.is_dir():
        raise SafetyError(f"owning checkout is missing: {canonical}")
    if git(canonical, "rev-parse", "--is-inside-work-tree") != "true":
        raise SafetyError(f"owning checkout is not a Git worktree: {canonical}")
    if absolute_git_path(canonical, "--git-common-dir") != common_dir:
        raise SafetyError(f"owning checkout changed Git common dir: {canonical}")
    if absolute_git_path(canonical, "--git-dir") != common_dir:
        raise SafetyError(f"owning checkout does not own Git common dir: {canonical}")

    return {
        "requested": str(requested),
        "root": str(root),
        "canonical_root": str(canonical),
        "common_dir": str(common_dir),
        "git_dir": str(git_dir),
        "linked_worktree": root != canonical,
        "clone": clone_health(canonical),
    }


def cbm_cache_dir(value: str | None) -> pathlib.Path:
    if value:
        return pathlib.Path(value).expanduser().resolve()
    if os.environ.get("CBM_CACHE_DIR"):
        return pathlib.Path(os.environ["CBM_CACHE_DIR"]).expanduser().resolve()
    base = pathlib.Path(os.environ.get("XDG_CACHE_HOME", pathlib.Path.home() / ".cache"))
    return (base / "codebase-memory-mcp").resolve()


def cbm_binary(value: str | None) -> str:
    candidate = value or shutil.which("codebase-memory-mcp")
    if not candidate:
        raise SafetyError("missing required command: codebase-memory-mcp")
    return candidate


def list_projects(binary: str) -> list[dict[str, Any]]:
    result = run([binary, "cli", "list_projects"])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SafetyError(f"list_projects returned invalid JSON: {error}") from error
    projects = payload.get("projects")
    if not isinstance(projects, list):
        raise SafetyError("list_projects response has no projects array")
    normalized: list[dict[str, Any]] = []
    names: set[str] = set()
    for project in projects:
        if not isinstance(project, dict):
            raise SafetyError("list_projects returned a non-object project")
        name = project.get("name")
        root_path = project.get("root_path")
        size_bytes = project.get("size_bytes")
        if (
            not isinstance(name, str)
            or not name
            or "/" in name
            or "\0" in name
            or not isinstance(root_path, str)
            or not isinstance(size_bytes, int)
            or size_bytes < 0
        ):
            raise SafetyError(f"invalid project record: {project!r}")
        if name in names:
            raise SafetyError(f"duplicate project name: {name}")
        names.add(name)
        normalized.append(
            {
                "name": name,
                "root_path": root_path,
                "size_bytes": size_bytes,
                "nodes": project.get("nodes"),
                "edges": project.get("edges"),
            }
        )
    return sorted(normalized, key=lambda item: item["name"])


def project_snapshot(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": project["name"],
            "root_path": project["root_path"],
            "size_bytes": project["size_bytes"],
        }
        for project in projects
    ]


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def manifest_digest(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("manifest_digest", None)
    return hashlib.sha256(canonical_json(unsigned)).hexdigest()


def normalize_prefix(
    raw: str, *, cache_dir: pathlib.Path, home: pathlib.Path
) -> pathlib.Path:
    prefix = pathlib.Path(raw).expanduser()
    if not prefix.is_absolute():
        raise SafetyError(f"ephemeral prefix must be absolute: {raw}")
    prefix = prefix.resolve()
    forbidden = {pathlib.Path("/"), home.resolve(), cache_dir.resolve()}
    if prefix in forbidden:
        raise SafetyError(f"unsafe ephemeral prefix: {prefix}")
    return prefix


def path_is_under(path: pathlib.Path, prefix: pathlib.Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(prefix.resolve(strict=False))
        return True
    except ValueError:
        return False


def declared_root(raw: str) -> pathlib.Path | None:
    path = pathlib.Path(raw).expanduser()
    if not path.is_absolute():
        return None
    return pathlib.Path(os.path.normpath(path))


def symlink_components(path: pathlib.Path) -> int:
    current = pathlib.Path(path.anchor)
    count = 0
    for part in path.parts[1:]:
        current /= part
        try:
            count += int(current.is_symlink())
        except OSError:
            return sys.maxsize
    return count


def project_for_root(
    projects: list[dict[str, Any]], root: pathlib.Path
) -> dict[str, Any] | None:
    matches = []
    for project in projects:
        raw = project["root_path"]
        if not raw:
            continue
        declared = declared_root(raw)
        if declared is None:
            continue
        try:
            if declared.resolve(strict=False) == root:
                matches.append((project, declared))
        except OSError:
            continue
    exact = [project for project, declared in matches if declared == root]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise SafetyError(f"multiple projects map to canonical root: {root}")
    if not matches:
        return None
    fewest = min(symlink_components(declared) for _, declared in matches)
    preferred = [
        project
        for project, declared in matches
        if symlink_components(declared) == fewest
    ]
    if len(preferred) > 1:
        raise SafetyError(f"multiple projects map to canonical root: {root}")
    return preferred[0]


def build_manifest(
    *,
    projects: list[dict[str, Any]],
    cache_dir: pathlib.Path,
    ephemeral_prefixes: list[pathlib.Path],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    protected: list[dict[str, Any]] = []
    for project in projects:
        raw_root = project["root_path"]
        base = {
            "name": project["name"],
            "root_path": raw_root,
            "size_bytes": project["size_bytes"],
        }
        if not raw_root:
            protected.append({**base, "reason": "empty_root"})
            continue
        root = pathlib.Path(raw_root).expanduser()
        if not root.exists():
            normalized = root.resolve(strict=False)
            matching_prefix = next(
                (
                    prefix
                    for prefix in ephemeral_prefixes
                    if path_is_under(normalized, prefix)
                ),
                None,
            )
            if matching_prefix is None:
                protected.append({**base, "reason": "missing_root_outside_prefix"})
            else:
                candidates.append(
                    {
                        **base,
                        "reason": "ephemeral_missing_root",
                        "ephemeral_prefix": str(matching_prefix),
                    }
                )
            continue
        try:
            resolved = resolve_repository(root)
        except SafetyError as error:
            protected.append(
                {**base, "reason": "live_root_unmapped", "detail": str(error)}
            )
            continue
        canonical_root = pathlib.Path(resolved["canonical_root"])
        canonical_project = project_for_root(projects, canonical_root)
        if canonical_project is None:
            protected.append(
                {
                    **base,
                    "reason": "missing_canonical_graph",
                    "canonical_root": str(canonical_root),
                }
            )
            continue
        if canonical_project["name"] == project["name"]:
            protected.append({**base, "reason": "canonical_root"})
            continue
        if pathlib.Path(resolved["root"]) == canonical_root:
            if not resolved["clone"]["full"]:
                protected.append(
                    {
                        **base,
                        "reason": "canonical_clone_not_full",
                        "canonical_root": str(canonical_root),
                        "canonical_project": canonical_project["name"],
                    }
                )
                continue
            candidates.append(
                {
                    **base,
                    "reason": "canonical_alias_duplicate",
                    "canonical_root": str(canonical_root),
                    "canonical_project": canonical_project["name"],
                    "canonical_project_root_path": canonical_project["root_path"],
                    "canonical_size_bytes": canonical_project["size_bytes"],
                    "common_dir": resolved["common_dir"],
                }
            )
            continue
        if not resolved["clone"]["full"]:
            protected.append(
                {
                    **base,
                    "reason": "canonical_clone_not_full",
                    "canonical_root": str(canonical_root),
                    "canonical_project": canonical_project["name"],
                }
            )
            continue
        candidates.append(
            {
                **base,
                "reason": "linked_worktree_duplicate",
                "canonical_root": str(canonical_root),
                "canonical_project": canonical_project["name"],
                "canonical_project_root_path": canonical_project["root_path"],
                "canonical_size_bytes": canonical_project["size_bytes"],
                "common_dir": resolved["common_dir"],
            }
        )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "cache_dir": str(cache_dir),
        "ephemeral_prefixes": [str(prefix) for prefix in ephemeral_prefixes],
        "snapshot": project_snapshot(projects),
        "project_bytes": sum(project["size_bytes"] for project in projects),
        "candidates": candidates,
        "protected": protected,
        "blockers": [
            item for item in protected if item["reason"] in HOST_BLOCKING_REASONS
        ],
    }
    payload["manifest_digest"] = manifest_digest(payload)
    return payload


def write_manifest(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def load_manifest(path: pathlib.Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise SafetyError(f"cannot read manifest {path}: {error}") from error
    if not isinstance(payload, dict):
        raise SafetyError("manifest must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SafetyError("unsupported manifest schema")
    if payload.get("manifest_digest") != manifest_digest(payload):
        raise SafetyError("manifest digest mismatch")
    if payload.get("host") != socket.gethostname():
        raise SafetyError(
            f"manifest host mismatch: {payload.get('host')} != {socket.gethostname()}"
        )
    validate_manifest_relationships(payload)
    return payload


def validate_manifest_relationships(payload: dict[str, Any]) -> None:
    collections: dict[str, list[dict[str, Any]]] = {}
    for key in ("snapshot", "candidates", "protected", "blockers"):
        value = payload.get(key)
        if not isinstance(value, list) or any(
            not isinstance(item, dict) for item in value
        ):
            raise SafetyError(f"manifest {key} must be an array of objects")
        collections[key] = value

    prefixes = payload.get("ephemeral_prefixes")
    if not isinstance(prefixes, list) or any(
        not isinstance(value, str) for value in prefixes
    ):
        raise SafetyError("manifest ephemeral_prefixes must be an array of strings")

    names: dict[str, list[str]] = {}
    for key, items in collections.items():
        item_names: list[str] = []
        for item in items:
            name = item.get("name")
            if not isinstance(name, str) or not name:
                raise SafetyError(f"manifest {key} contains an invalid project name")
            item_names.append(name)
        if len(item_names) != len(set(item_names)):
            raise SafetyError(f"manifest {key} contains duplicate project names")
        names[key] = item_names

    snapshot_by_name = {
        item["name"]: item for item in collections["snapshot"]
    }
    candidate_names = set(names["candidates"])
    protected_names = set(names["protected"])
    snapshot_names = set(names["snapshot"])
    if candidate_names & protected_names:
        raise SafetyError("manifest candidates and protected projects overlap")
    if candidate_names | protected_names != snapshot_names:
        raise SafetyError(
            "manifest candidates and protected projects do not partition the snapshot"
        )

    for key in ("candidates", "protected"):
        for item in collections[key]:
            snapshot = snapshot_by_name[item["name"]]
            for field in ("root_path", "size_bytes"):
                if item.get(field) != snapshot.get(field):
                    raise SafetyError(
                        f"manifest {key} record disagrees with snapshot: {item['name']}"
                    )

    expected_blockers = [
        item
        for item in collections["protected"]
        if item.get("reason") in HOST_BLOCKING_REASONS
    ]
    actual_blockers = collections["blockers"]
    if sorted(canonical_json(item) for item in actual_blockers) != sorted(
        canonical_json(item) for item in expected_blockers
    ):
        raise SafetyError(
            "manifest blockers must exactly match blocked protected projects"
        )


def validate_snapshot(
    expected: list[dict[str, Any]], projects: list[dict[str, Any]]
) -> None:
    if expected != project_snapshot(projects):
        raise SafetyError("project manifest drift detected")


def db_path(cache_dir: pathlib.Path, project_name: str) -> pathlib.Path:
    if (
        not project_name
        or project_name in {".", ".."}
        or "/" in project_name
        or "\0" in project_name
    ):
        raise SafetyError(f"unsafe project name: {project_name!r}")
    path = cache_dir / f"{project_name}.db"
    if path.parent.resolve() != cache_dir.resolve():
        raise SafetyError(f"project DB escapes cache root: {path}")
    return path


def cache_paths(path: pathlib.Path) -> list[pathlib.Path]:
    return [path, pathlib.Path(f"{path}-wal"), pathlib.Path(f"{path}-shm")]


def path_exists(path: pathlib.Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise SafetyError(f"cannot inspect project cache path {path}: {error}") from error
    return True


def cache_fingerprint(path: pathlib.Path) -> dict[str, dict[str, int] | None]:
    fingerprint: dict[str, dict[str, int] | None] = {}
    for candidate in cache_paths(path):
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            fingerprint[candidate.name] = None
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise SafetyError(
                f"project cache file is non-regular or symlinked: {candidate}"
            )
        fingerprint[candidate.name] = {
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "size": metadata.st_size,
            "mtime_ns": metadata.st_mtime_ns,
        }
    return fingerprint


def capture_cache_baseline(
    path: pathlib.Path, expected_size: int
) -> dict[str, dict[str, int] | None]:
    fingerprint = cache_fingerprint(path)
    database = fingerprint[path.name]
    if database is None:
        raise SafetyError(f"project DB is missing, non-regular, or symlinked: {path}")
    if database["size"] != expected_size:
        raise SafetyError(
            f"project DB size changed for {path.name}: "
            f"{database['size']} != {expected_size}"
        )

    wal_path = pathlib.Path(f"{path}-wal")
    wal = fingerprint[wal_path.name]
    if wal is not None and wal["size"] != 0:
        raise SafetyError(f"project WAL is nonzero: {wal_path}")
    return fingerprint


def require_cache_absent(path: pathlib.Path) -> None:
    residue = [
        str(candidate) for candidate in cache_paths(path) if path_exists(candidate)
    ]
    if residue:
        raise SafetyError("project cache residue remains: " + ", ".join(residue))


def validate_database(
    path: pathlib.Path,
    baseline: dict[str, dict[str, int] | None],
) -> None:
    if cache_fingerprint(path) != baseline:
        raise SafetyError(
            f"project cache fingerprint changed before validation: {path.name}"
        )
    try:
        encoded_path = urllib.parse.quote(str(path), safe="/")
        connection = sqlite3.connect(
            f"file:{encoded_path}?mode=ro&immutable=1",
            uri=True,
        )
        try:
            row = connection.execute("PRAGMA quick_check").fetchone()
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise SafetyError(f"project DB is corrupt: {path}: {error}") from error
    if not row or row[0] != "ok":
        raise SafetyError(f"project DB quick_check failed: {path}: {row}")
    if cache_fingerprint(path) != baseline:
        raise SafetyError(
            f"project cache fingerprint changed during validation: {path.name}"
        )


def lsof_argv_cost(value: str) -> int:
    return len(os.fsencode(value)) + 1 + struct.calcsize("P")


def lsof_binary() -> str:
    path = pathlib.Path(LSOF_PATH)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise SafetyError(f"lsof is missing or not executable: {path}")
    return str(path)


def lsof_command_prefix(lsof: str) -> list[str]:
    return [lsof, "-nP", "-F0pfn", "-f", "--"]


def holder_inventory(
    *,
    cache_dir: pathlib.Path,
    candidates: list[dict[str, Any]],
    fingerprints: dict[str, dict[str, dict[str, int] | None]],
) -> list[dict[str, str]]:
    inventory: list[dict[str, str]] = []
    kinds = ("db", "wal", "shm")
    for candidate in candidates:
        database = db_path(cache_dir, candidate["name"])
        baseline = fingerprints[candidate["name"]]
        for kind, path in zip(kinds, cache_paths(database), strict=True):
            if baseline[path.name] is not None:
                inventory.append(
                    {
                        "candidate": candidate["name"],
                        "kind": kind,
                        "path": str(path.resolve()),
                    }
                )
    return inventory


def chunk_holder_inventory(
    lsof: str,
    inventory: list[dict[str, str]],
    *,
    budget: int = LSOF_ARGV_BUDGET,
) -> list[list[dict[str, str]]]:
    base = lsof_command_prefix(lsof)
    base_cost = (
        sum(lsof_argv_cost(value) for value in base)
        + struct.calcsize("P")
    )
    chunks: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []
    current_cost = base_cost
    for item in inventory:
        item_cost = lsof_argv_cost(item["path"])
        if base_cost + item_cost > budget:
            raise SafetyError(
                f"project cache path exceeds lsof argv budget: {item['path']}"
            )
        if current and current_cost + item_cost > budget:
            chunks.append(current)
            current = []
            current_cost = base_cost
        current.append(item)
        current_cost += item_cost
    if current:
        chunks.append(current)
    return chunks


def parse_lsof_holders(
    output: bytes,
    inventory: list[dict[str, str]],
) -> list[dict[str, str]]:
    by_path = {item["path"]: item for item in inventory}

    current_pid: str | None = None
    current_file = False
    mapped: list[dict[str, str]] = []
    for raw in output.split(b"\0"):
        field = os.fsdecode(raw)
        if field.startswith("\n"):
            field = field[1:]
        if not field or field == "\n":
            continue
        tag, value = field[0], field[1:]
        if tag == "p" and value.isdigit():
            current_pid = value
            current_file = False
        elif tag == "f" and current_pid is not None and value:
            current_file = True
        elif (
            tag == "n"
            and current_pid is not None
            and current_file
            and value in by_path
        ):
            mapped.append({**by_path[value], "pid": current_pid})
            current_file = False
    if mapped:
        return mapped

    current_pid: str | None = None
    current_file = False
    saw_field = False
    for raw in output.split(b"\0"):
        field = os.fsdecode(raw)
        if field.startswith("\n"):
            field = field[1:]
        if not field or field == "\n":
            continue
        saw_field = True
        tag, value = field[0], field[1:]
        if tag == "p":
            if not value.isdigit():
                raise SafetyError("lsof returned malformed process output")
            current_pid = value
            current_file = False
            continue
        if tag == "f":
            if current_pid is None or not value:
                raise SafetyError("lsof returned malformed file output")
            current_file = True
            continue
        if (
            tag != "n"
            or current_pid is None
            or not current_file
            or not value
        ):
            raise SafetyError("lsof returned malformed holder output")
        item = by_path.get(value)
        if item is None:
            raise SafetyError(f"lsof returned an unmapped cache path: {value}")
        current_file = False
    if current_file:
        raise SafetyError("lsof returned an incomplete file record")
    if saw_field:
        raise SafetyError("lsof reported a holder without an attributed cache path")
    return []


def run_holder_chunk(
    lsof: str,
    inventory: list[dict[str, str]],
    *,
    timeout_seconds: int,
) -> None:
    command = [
        *lsof_command_prefix(lsof),
        *(item["path"] for item in inventory),
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise SafetyError("lsof holder sweep timed out") from error
    except OSError as error:
        if error.errno == errno.E2BIG:
            raise SafetyError(
                "lsof holder sweep exceeded the system argv limit"
            ) from error
        raise SafetyError(f"lsof holder sweep failed to start: {error}") from error

    holders = parse_lsof_holders(result.stdout, inventory)
    if holders:
        detail = ", ".join(
            f"candidate={item['candidate']} kind={item['kind']} "
            f"path={item['path']} pid={item['pid']}"
            for item in holders
        )
        raise SafetyError(f"project DB is held: {detail}")
    if result.returncode == 1 and not result.stderr:
        return
    if result.returncode == 0:
        raise SafetyError("lsof returned success without a mapped holder")
    detail = os.fsdecode(result.stderr).strip() or f"exit {result.returncode}"
    raise SafetyError(f"lsof holder sweep failed: {detail}")


def run_holder_sweep(
    lsof: str,
    chunks: list[list[dict[str, str]]],
    *,
    timeout_seconds: int,
) -> None:
    for chunk in chunks:
        run_holder_chunk(
            lsof,
            chunk,
            timeout_seconds=timeout_seconds,
        )


def require_fingerprints(
    *,
    cache_dir: pathlib.Path,
    candidates: list[dict[str, Any]],
    fingerprints: dict[str, dict[str, dict[str, int] | None]],
    phase: str,
) -> None:
    for candidate in candidates:
        path = db_path(cache_dir, candidate["name"])
        if cache_fingerprint(path) != fingerprints[candidate["name"]]:
            raise SafetyError(
                f"project cache fingerprint changed {phase}: {candidate['name']}"
            )


def revalidate_candidate(
    candidate: dict[str, Any],
    projects: list[dict[str, Any]],
    prefixes: list[pathlib.Path],
) -> None:
    current = next(
        (project for project in projects if project["name"] == candidate["name"]),
        None,
    )
    if current is None:
        raise SafetyError(f"candidate disappeared: {candidate['name']}")
    for field in ("root_path", "size_bytes"):
        if current[field] != candidate[field]:
            raise SafetyError(f"candidate {field} changed: {candidate['name']}")

    root = pathlib.Path(candidate["root_path"]).expanduser()
    reason = candidate["reason"]
    if reason == "ephemeral_missing_root":
        if root.exists():
            raise SafetyError(f"ephemeral root became live: {root}")
        expected_prefix = pathlib.Path(candidate["ephemeral_prefix"])
        if expected_prefix not in prefixes or not path_is_under(root, expected_prefix):
            raise SafetyError(f"ephemeral prefix guard failed: {root}")
        return
    if reason not in {"canonical_alias_duplicate", "linked_worktree_duplicate"}:
        raise SafetyError(f"unsupported candidate reason: {reason}")

    resolved = resolve_repository(root)
    if resolved["root"] != str(root.resolve()):
        raise SafetyError(f"candidate root changed: {root}")
    if resolved["canonical_root"] != candidate["canonical_root"]:
        raise SafetyError(f"candidate canonical root changed: {root}")
    if resolved["common_dir"] != candidate["common_dir"]:
        raise SafetyError(f"candidate Git common dir changed: {root}")
    if reason == "linked_worktree_duplicate":
        if not resolved["linked_worktree"]:
            raise SafetyError(f"candidate is no longer a linked worktree: {root}")
    else:
        if resolved["linked_worktree"]:
            raise SafetyError(f"canonical alias became a linked worktree: {root}")
        if declared_root(candidate["root_path"]) == pathlib.Path(
            candidate["canonical_root"]
        ):
            raise SafetyError(f"canonical alias became the canonical path: {root}")
    if not resolved["clone"]["full"]:
        raise SafetyError(f"candidate canonical clone is not full: {root}")
    canonical = next(
        (
            project
            for project in projects
            if project["name"] == candidate["canonical_project"]
        ),
        None,
    )
    if canonical is None:
        raise SafetyError(f"canonical graph disappeared: {candidate['canonical_project']}")
    if canonical["root_path"] != candidate["canonical_project_root_path"]:
        raise SafetyError(f"canonical graph registration changed: {candidate['canonical_project']}")
    if (
        pathlib.Path(canonical["root_path"]).expanduser().resolve()
        != pathlib.Path(candidate["canonical_root"])
    ):
        raise SafetyError(f"canonical graph root changed: {candidate['canonical_project']}")
    if canonical["size_bytes"] != candidate["canonical_size_bytes"]:
        raise SafetyError(f"canonical graph size changed: {candidate['canonical_project']}")


def delete_project_command(binary: str, project_name: str) -> list[str]:
    payload = json.dumps({"project": project_name}, separators=(",", ":"))
    return [binary, "cli", "delete_project", payload]


def outcome_record(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": candidate["name"],
        "bytes": candidate["size_bytes"],
        "reason": candidate["reason"],
    }


def outcome_report(
    candidates: list[dict[str, Any]],
    *,
    launched: set[str],
    verified_deleted: set[str],
    failed: set[str],
    ambiguous: set[str],
) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for key, names in (
        ("launched", launched),
        ("verified_deleted", verified_deleted),
        ("failed", failed),
        ("ambiguous", ambiguous),
    ):
        records = [
            outcome_record(candidate)
            for candidate in candidates
            if candidate["name"] in names
        ]
        report[key] = records
        report[f"{key}_bytes"] = sum(item["bytes"] for item in records)
    return report


def merge_outcome_reports(
    current: dict[str, Any],
    addition: dict[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in ("launched", "verified_deleted", "failed", "ambiguous"):
        records = [*current[key], *addition[key]]
        merged[key] = records
        merged[f"{key}_bytes"] = sum(item["bytes"] for item in records)
    return merged


def empty_outcome_report() -> dict[str, Any]:
    return outcome_report(
        [],
        launched=set(),
        verified_deleted=set(),
        failed=set(),
        ambiguous=set(),
    )


def deletion_candidate_batches(
    *,
    lsof: str,
    cache_dir: pathlib.Path,
    candidates: list[dict[str, Any]],
    fingerprints: dict[str, dict[str, dict[str, int] | None]],
    budget: int = LSOF_ARGV_BUDGET,
) -> list[list[dict[str, Any]]]:
    base_cost = (
        sum(lsof_argv_cost(value) for value in lsof_command_prefix(lsof))
        + struct.calcsize("P")
    )
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_cost = base_cost
    for candidate in candidates:
        inventory = holder_inventory(
            cache_dir=cache_dir,
            candidates=[candidate],
            fingerprints=fingerprints,
        )
        candidate_cost = sum(
            lsof_argv_cost(item["path"]) for item in inventory
        )
        if base_cost + candidate_cost > budget:
            raise SafetyError(
                f"candidate cache paths exceed lsof argv budget: "
                f"{candidate['name']}"
            )
        if current and (
            len(current) >= DELETE_BATCH_MAX_CANDIDATES
            or current_cost + candidate_cost > budget
        ):
            batches.append(current)
            current = []
            current_cost = base_cost
        current.append(candidate)
        current_cost += candidate_cost
    if current:
        batches.append(current)
    return batches


def terminate_owned_children(
    children: list[dict[str, Any]],
) -> set[str]:
    terminated: set[str] = set()
    for child in children:
        process = child["process"]
        if process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                continue
            terminated.add(child["candidate"]["name"])
    return terminated


def drain_delete_children(
    children: list[dict[str, Any]],
    *,
    deadline: float,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    results: dict[str, dict[str, Any]] = {}
    timed_out: set[str] = set()
    for child in children:
        candidate = child["candidate"]
        process = child["process"]
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out.update(
                item["candidate"]["name"]
                for item in children
                if item["candidate"]["name"] not in results
            )
            timed_out.update(terminate_owned_children(children))
            break
        try:
            stdout, stderr = process.communicate(timeout=remaining)
        except subprocess.TimeoutExpired:
            timed_out.update(
                item["candidate"]["name"]
                for item in children
                if item["candidate"]["name"] not in results
            )
            timed_out.update(terminate_owned_children(children))
            break
        results[candidate["name"]] = {
            "returncode": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }

    for child in children:
        candidate = child["candidate"]
        process = child["process"]
        if candidate["name"] in results:
            continue
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            timed_out.add(candidate["name"])
            stdout, stderr = process.communicate()
        results[candidate["name"]] = {
            "returncode": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    return results, timed_out


def execute_delete_batch(
    *,
    binary: str,
    lsof: str,
    lsof_timeout_seconds: int,
    cache_dir: pathlib.Path,
    candidates: list[dict[str, Any]],
    fingerprints: dict[str, dict[str, dict[str, int] | None]],
    expected_snapshot: list[dict[str, Any]],
    prefixes: list[pathlib.Path],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    deadline = time.monotonic() + DELETE_BATCH_TIMEOUT_SECONDS
    projects = list_projects(binary)
    validate_snapshot(expected_snapshot, projects)
    for candidate in candidates:
        revalidate_candidate(candidate, projects, prefixes)
    live_fingerprints = {
        candidate["name"]: cache_fingerprint(
            db_path(cache_dir, candidate["name"])
        )
        for candidate in candidates
    }
    for candidate in candidates:
        live = live_fingerprints[candidate["name"]]
        if live != fingerprints[candidate["name"]]:
            raise SafetyError(
                f"project cache fingerprint changed before deletion batch: "
                f"{candidate['name']}"
            )
        live_fingerprints[candidate["name"]] = live

    inventory = holder_inventory(
        cache_dir=cache_dir,
        candidates=candidates,
        fingerprints=live_fingerprints,
    )
    chunks = chunk_holder_inventory(lsof, inventory)
    if len(chunks) != 1:
        raise SafetyError("deletion batch exceeds one lsof invocation")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SafetyError("deletion batch deadline expired before lsof")
    run_holder_chunk(
        lsof,
        chunks[0],
        timeout_seconds=min(
            lsof_timeout_seconds,
            max(1, math.ceil(remaining)),
        ),
    )
    post_lsof_fingerprints = {
        candidate["name"]: cache_fingerprint(
            db_path(cache_dir, candidate["name"])
        )
        for candidate in candidates
    }
    for candidate in candidates:
        current = post_lsof_fingerprints[candidate["name"]]
        if (
            current != fingerprints[candidate["name"]]
            or current != live_fingerprints[candidate["name"]]
        ):
            raise SafetyError(
                f"project cache fingerprint changed during final holder sweep: "
                f"{candidate['name']}"
            )

    children: list[dict[str, Any]] = []
    launched: set[str] = set()
    failed: set[str] = set()
    ambiguous: set[str] = set()
    failure_reasons: list[str] = []
    spawn_failed = False
    for candidate in candidates:
        if deadline - time.monotonic() <= 0:
            failed.add(candidate["name"])
            ambiguous.add(candidate["name"])
            failure_reasons.append(
                f"deletion batch deadline expired before launch: "
                f"{candidate['name']}"
            )
            spawn_failed = True
            break
        try:
            process = subprocess.Popen(
                delete_project_command(binary, candidate["name"]),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as error:
            failed.add(candidate["name"])
            failure_reasons.append(
                f"delete_project spawn failed for {candidate['name']}: {error}"
            )
            spawn_failed = True
            break
        launched.add(candidate["name"])
        children.append({"candidate": candidate, "process": process})

    results, timed_out = drain_delete_children(children, deadline=deadline)
    failed.update(timed_out)
    ambiguous.update(timed_out)
    if timed_out:
        failure_reasons.append(
            "delete_project batch timed out: "
            + ", ".join(
                candidate["name"]
                for candidate in candidates
                if candidate["name"] in timed_out
            )
        )

    try:
        projects = list_projects(binary)
    except SafetyError as error:
        failed.update(launched)
        ambiguous.update(launched)
        report = outcome_report(
            candidates,
            launched=launched,
            verified_deleted=set(),
            failed=failed,
            ambiguous=ambiguous,
        )
        raise DeleteBatchError(
            f"cannot verify deletion batch: {error}",
            report=report,
            expected_snapshot=expected_snapshot,
            projects=[],
        ) from error

    registered = {project["name"] for project in projects}
    verified_deleted: set[str] = set()
    absent_from_registry: set[str] = set()
    for candidate in candidates:
        name = candidate["name"]
        path = db_path(cache_dir, name)
        try:
            cache_absent = all(
                value is None for value in cache_fingerprint(path).values()
            )
        except SafetyError as error:
            cache_absent = False
            failed.add(name)
            ambiguous.add(name)
            failure_reasons.append(str(error))
        registry_absent = name not in registered
        if registry_absent:
            absent_from_registry.add(name)
        if registry_absent and cache_absent:
            verified_deleted.add(name)
        elif registry_absent and not cache_absent:
            failed.add(name)
            ambiguous.add(name)
            failure_reasons.append(
                f"project cache residue remains: {name}"
            )
        elif not registry_absent and cache_absent:
            failed.add(name)
            ambiguous.add(name)
            failure_reasons.append(
                f"deleted project remains registered: {name}"
            )
        elif name in launched:
            failed.add(name)
            failure_reasons.append(
                f"deleted project remains registered: {name}"
            )
        elif registry_absent or cache_absent:
            failed.add(name)
            ambiguous.add(name)
            failure_reasons.append(
                f"unlaunched candidate state changed: {name}"
            )

        result = results.get(name)
        if result is None:
            if name in launched:
                failed.add(name)
                ambiguous.add(name)
                failure_reasons.append(
                    f"delete_project result is missing for {name}"
                )
            continue
        if result["returncode"] != 0:
            failed.add(name)
            detail = (
                os.fsdecode(result["stderr"]).strip()
                or os.fsdecode(result["stdout"]).strip()
                or f"exit {result['returncode']}"
            )
            failure_reasons.append(
                f"delete_project failed for {name}: {detail}"
            )
        elif name not in verified_deleted:
            failed.add(name)
            failure_reasons.append(
                f"delete_project returned success without full deletion: {name}"
            )

    next_expected_snapshot = [
        item
        for item in expected_snapshot
        if item["name"] not in absent_from_registry
    ]
    try:
        validate_snapshot(next_expected_snapshot, projects)
    except SafetyError as error:
        failed.update(launched)
        ambiguous.update(launched)
        failure_reasons.append(str(error))

    report = outcome_report(
        candidates,
        launched=launched,
        verified_deleted=verified_deleted,
        failed=failed,
        ambiguous=ambiguous,
    )
    if spawn_failed or failed or failure_reasons:
        raise DeleteBatchError(
            "; ".join(failure_reasons) or "deletion batch failed",
            report=report,
            expected_snapshot=next_expected_snapshot,
            projects=projects,
        )
    return next_expected_snapshot, projects, report


def preflight_candidates(
    *,
    binary: str,
    cache_dir: pathlib.Path,
    candidates: list[dict[str, Any]],
    expected_snapshot: list[dict[str, Any]],
    prefixes: list[pathlib.Path],
    lsof_timeout_seconds: int,
) -> tuple[
    dict[str, dict[str, dict[str, int] | None]],
    str | None,
]:
    fingerprints: dict[str, dict[str, dict[str, int] | None]] = {}
    for candidate in candidates:
        projects = list_projects(binary)
        validate_snapshot(expected_snapshot, projects)
        revalidate_candidate(candidate, projects, prefixes)
        path = db_path(cache_dir, candidate["name"])
        fingerprints[candidate["name"]] = capture_cache_baseline(
            path, candidate["size_bytes"]
        )
    if not candidates:
        return fingerprints, None

    lsof = lsof_binary()
    inventory = holder_inventory(
        cache_dir=cache_dir,
        candidates=candidates,
        fingerprints=fingerprints,
    )
    chunks = chunk_holder_inventory(lsof, inventory)

    run_holder_sweep(
        lsof,
        chunks,
        timeout_seconds=lsof_timeout_seconds,
    )
    require_fingerprints(
        cache_dir=cache_dir,
        candidates=candidates,
        fingerprints=fingerprints,
        phase="during the before-holder sweep",
    )
    for candidate in candidates:
        path = db_path(cache_dir, candidate["name"])
        validate_database(path, fingerprints[candidate["name"]])
    require_fingerprints(
        cache_dir=cache_dir,
        candidates=candidates,
        fingerprints=fingerprints,
        phase="after database validation",
    )
    run_holder_sweep(
        lsof,
        chunks,
        timeout_seconds=lsof_timeout_seconds,
    )
    require_fingerprints(
        cache_dir=cache_dir,
        candidates=candidates,
        fingerprints=fingerprints,
        phase="during the after-holder sweep",
    )
    return fingerprints, lsof


def runtime_protected_candidates(
    payload: dict[str, Any], names: list[str]
) -> list[dict[str, Any]]:
    if len(names) != len(set(names)):
        raise SafetyError("duplicate --protect-candidate name")

    snapshot_names = {item["name"] for item in payload["snapshot"]}
    candidates = {item["name"] for item in payload["candidates"]}
    for name in names:
        if name not in snapshot_names:
            raise SafetyError(f"unknown --protect-candidate name: {name}")
        if name not in candidates:
            raise SafetyError(f"project is not a manifest candidate: {name}")
    selected_names = set(names)
    return [
        item
        for item in payload["candidates"]
        if item["name"] in selected_names
    ]


def candidate_execution_summary(
    *,
    manifest_candidates: list[dict[str, Any]],
    eligible_candidates: list[dict[str, Any]],
    runtime_protected: list[dict[str, Any]],
    fingerprints: dict[str, dict[str, dict[str, int] | None]],
) -> dict[str, Any]:
    manifest_bytes = sum(item["size_bytes"] for item in manifest_candidates)
    eligible_bytes = sum(item["size_bytes"] for item in eligible_candidates)
    protected_report = [
        {
            "name": item["name"],
            "reason": item["reason"],
            "bytes": item["size_bytes"],
        }
        for item in runtime_protected
    ]
    return {
        "candidates": len(manifest_candidates),
        "candidate_bytes": manifest_bytes,
        "manifest_candidates": len(manifest_candidates),
        "manifest_candidate_bytes": manifest_bytes,
        "eligible_candidates": len(eligible_candidates),
        "eligible_candidate_bytes": eligible_bytes,
        "preflighted": len(fingerprints),
        "preflighted_bytes": sum(
            candidate["size_bytes"]
            for candidate in eligible_candidates
            if candidate["name"] in fingerprints
        ),
        "runtime_protected": protected_report,
        "runtime_protected_bytes": sum(
            item["bytes"] for item in protected_report
        ),
    }


def audit(args: argparse.Namespace) -> int:
    binary = cbm_binary(args.cbm_bin)
    cache_dir = cbm_cache_dir(args.cache_dir)
    home = pathlib.Path.home().resolve()
    prefixes = sorted(
        {
            normalize_prefix(value, cache_dir=cache_dir, home=home)
            for value in args.ephemeral_prefix
        }
    )
    projects = list_projects(binary)
    payload = build_manifest(
        projects=projects,
        cache_dir=cache_dir,
        ephemeral_prefixes=prefixes,
    )
    manifest_path = pathlib.Path(args.manifest).expanduser().resolve()
    write_manifest(manifest_path, payload)
    print(
        json.dumps(
            {
                "action": "audit",
                "manifest": str(manifest_path),
                "projects": len(projects),
                "project_bytes": payload["project_bytes"],
                "candidates": len(payload["candidates"]),
                "protected": len(payload["protected"]),
                "blockers": len(payload["blockers"]),
                "candidate_bytes": sum(
                    item["size_bytes"] for item in payload["candidates"]
                ),
                "applied": False,
            },
            sort_keys=True,
        )
    )
    return 0


def prune(args: argparse.Namespace) -> int:
    manifest_path = pathlib.Path(args.manifest).expanduser().resolve()
    payload = load_manifest(manifest_path)
    runtime_protected = runtime_protected_candidates(
        payload, args.protect_candidate
    )
    protected_names = {item["name"] for item in runtime_protected}
    eligible_candidates = [
        item
        for item in payload["candidates"]
        if item["name"] not in protected_names
    ]
    binary = cbm_binary(args.cbm_bin)
    cache_dir = cbm_cache_dir(args.cache_dir)
    if str(cache_dir) != payload.get("cache_dir"):
        raise SafetyError(
            f"cache root mismatch: {cache_dir} != {payload.get('cache_dir')}"
        )
    home = pathlib.Path.home().resolve()
    prefixes = []
    for value in payload["ephemeral_prefixes"]:
        normalized = normalize_prefix(value, cache_dir=cache_dir, home=home)
        if value != str(normalized):
            raise SafetyError(
                f"manifest ephemeral prefix is not normalized: {value}"
            )
        prefixes.append(normalized)
    projects = list_projects(binary)
    validate_snapshot(payload["snapshot"], projects)
    if payload["blockers"] and not args.allow_blocked_manifest:
        reasons = sorted({item["reason"] for item in payload["blockers"]})
        raise SafetyError(
            "host cache manifest is blocked: " + ", ".join(reasons)
        )

    expected_snapshot = list(payload["snapshot"])
    for candidate in runtime_protected:
        revalidate_candidate(candidate, projects, prefixes)
    fingerprints, lsof = preflight_candidates(
        binary=binary,
        cache_dir=cache_dir,
        candidates=eligible_candidates,
        expected_snapshot=expected_snapshot,
        prefixes=prefixes,
        lsof_timeout_seconds=args.lsof_timeout_seconds,
    )
    execution_summary = candidate_execution_summary(
        manifest_candidates=payload["candidates"],
        eligible_candidates=eligible_candidates,
        runtime_protected=runtime_protected,
        fingerprints=fingerprints,
    )

    if not args.apply:
        print(
            json.dumps(
                {
                    "action": "prune",
                    "manifest": str(manifest_path),
                    **execution_summary,
                    "projects": len(projects),
                    "project_bytes": sum(
                        project["size_bytes"] for project in projects
                    ),
                    "blocked_manifest_allowed": args.allow_blocked_manifest,
                    "lsof_timeout_seconds": args.lsof_timeout_seconds,
                    "applied": False,
                },
                sort_keys=True,
            )
        )
        return 0

    before_projects = len(projects)
    before_bytes = sum(project["size_bytes"] for project in projects)
    outcomes = empty_outcome_report()
    try:
        if eligible_candidates and lsof is None:
            raise SafetyError("lsof is required for cache pruning")
        batches = deletion_candidate_batches(
            lsof=lsof or LSOF_PATH,
            cache_dir=cache_dir,
            candidates=eligible_candidates,
            fingerprints=fingerprints,
        )
        for batch in batches:
            try:
                expected_snapshot, projects, report = execute_delete_batch(
                    binary=binary,
                    lsof=lsof or LSOF_PATH,
                    lsof_timeout_seconds=args.lsof_timeout_seconds,
                    cache_dir=cache_dir,
                    candidates=batch,
                    fingerprints=fingerprints,
                    expected_snapshot=expected_snapshot,
                    prefixes=prefixes,
                )
            except DeleteBatchError as error:
                outcomes = merge_outcome_reports(outcomes, error.report)
                expected_snapshot = error.expected_snapshot
                projects = error.projects
                raise
            outcomes = merge_outcome_reports(outcomes, report)
    except SafetyError as error:
        already_deleted = [
            item["name"] for item in outcomes["verified_deleted"]
        ]
        raise SafetyError(
            f"{error}; delete_outcomes="
            f"{json.dumps(outcomes, sort_keys=True, separators=(',', ':'))}; "
            f"already_deleted={json.dumps(already_deleted)}"
        ) from error

    deleted = outcomes["verified_deleted"]
    print(
        json.dumps(
            {
                "action": "prune",
                "manifest": str(manifest_path),
                **execution_summary,
                "applied": True,
                "deleted": deleted,
                "deleted_bytes": outcomes["verified_deleted_bytes"],
                "launched": outcomes["launched"],
                "launched_bytes": outcomes["launched_bytes"],
                "verified_deleted": outcomes["verified_deleted"],
                "verified_deleted_bytes": outcomes["verified_deleted_bytes"],
                "failed": outcomes["failed"],
                "failed_bytes": outcomes["failed_bytes"],
                "ambiguous": outcomes["ambiguous"],
                "ambiguous_bytes": outcomes["ambiguous_bytes"],
                "skipped": [],
                "blocked_manifest_allowed": args.allow_blocked_manifest,
                "lsof_timeout_seconds": args.lsof_timeout_seconds,
                "before_projects": before_projects,
                "before_bytes": before_bytes,
                "after_projects": len(projects),
                "after_bytes": sum(
                    project["size_bytes"] for project in projects
                ),
            },
            sort_keys=True,
        )
    )
    return 0


def lsof_timeout_seconds(value: str) -> int:
    try:
        timeout = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "--lsof-timeout-seconds must be an integer"
        ) from error
    if not LSOF_TIMEOUT_MIN_SECONDS <= timeout <= LSOF_TIMEOUT_MAX_SECONDS:
        raise argparse.ArgumentTypeError(
            "--lsof-timeout-seconds must be between "
            f"{LSOF_TIMEOUT_MIN_SECONDS} and {LSOF_TIMEOUT_MAX_SECONDS}"
        )
    return timeout


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    subparsers = root.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser("resolve")
    resolve.add_argument("repo")

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--manifest", required=True)
    audit_parser.add_argument("--ephemeral-prefix", action="append", default=[])
    audit_parser.add_argument("--cache-dir")
    audit_parser.add_argument("--cbm-bin")

    prune_parser = subparsers.add_parser("prune")
    prune_parser.add_argument("--manifest", required=True)
    prune_parser.add_argument("--cache-dir")
    prune_parser.add_argument("--cbm-bin")
    prune_parser.add_argument("--apply", action="store_true")
    prune_parser.add_argument("--allow-blocked-manifest", action="store_true")
    prune_parser.add_argument("--protect-candidate", action="append", default=[])
    prune_parser.add_argument(
        "--lsof-timeout-seconds",
        type=lsof_timeout_seconds,
        default=LSOF_TIMEOUT_SECONDS,
    )
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "resolve":
            print(json.dumps(resolve_repository(args.repo), sort_keys=True))
            return 0
        if args.command == "audit":
            return audit(args)
        if args.command == "prune":
            return prune(args)
    except SafetyError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
