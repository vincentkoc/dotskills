#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import socket
import sqlite3
import subprocess
import sys
import urllib.parse
from typing import Any


SCHEMA_VERSION = 1
HOST_BLOCKING_REASONS = {
    "canonical_clone_not_full",
    "empty_root",
    "live_root_unmapped",
    "missing_canonical_graph",
}


class SafetyError(RuntimeError):
    pass


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
    return payload


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


def db_is_held(path: pathlib.Path) -> bool:
    lsof = shutil.which("lsof")
    if not lsof:
        raise SafetyError("lsof is required for cache pruning")
    paths = [path, pathlib.Path(f"{path}-wal"), pathlib.Path(f"{path}-shm")]
    existing = [str(candidate) for candidate in paths if candidate.exists()]
    if not existing:
        return False
    result = run([lsof, "-F", "p", "--", *existing], check=False)
    if result.returncode not in (0, 1):
        raise SafetyError(f"lsof failed for {path}: {result.stderr.strip()}")
    return bool(result.stdout.strip())


def validate_database(path: pathlib.Path, expected_size: int) -> None:
    if not path.is_file() or path.is_symlink():
        raise SafetyError(f"project DB is missing, non-regular, or symlinked: {path}")
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        raise SafetyError(
            f"project DB size changed for {path.name}: {actual_size} != {expected_size}"
        )
    try:
        encoded_path = urllib.parse.quote(str(path), safe="/")
        connection = sqlite3.connect(f"file:{encoded_path}?mode=ro", uri=True)
        try:
            row = connection.execute("PRAGMA quick_check").fetchone()
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise SafetyError(f"project DB is corrupt: {path}: {error}") from error
    if not row or row[0] != "ok":
        raise SafetyError(f"project DB quick_check failed: {path}: {row}")


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


def delete_project(binary: str, project_name: str) -> None:
    payload = json.dumps({"project": project_name}, separators=(",", ":"))
    result = run([binary, "cli", "delete_project", payload], check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown failure"
        raise SafetyError(f"delete_project failed for {project_name}: {detail}")


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
    binary = cbm_binary(args.cbm_bin)
    cache_dir = cbm_cache_dir(args.cache_dir)
    if str(cache_dir) != payload.get("cache_dir"):
        raise SafetyError(
            f"cache root mismatch: {cache_dir} != {payload.get('cache_dir')}"
        )
    prefixes = [pathlib.Path(value) for value in payload["ephemeral_prefixes"]]
    projects = list_projects(binary)
    validate_snapshot(payload["snapshot"], projects)
    if payload.get("blockers"):
        reasons = sorted({item["reason"] for item in payload["blockers"]})
        raise SafetyError(
            "host cache manifest is blocked: " + ", ".join(reasons)
        )

    if not args.apply:
        print(
            json.dumps(
                {
                    "action": "prune",
                    "manifest": str(manifest_path),
                    "candidates": len(payload["candidates"]),
                    "candidate_bytes": sum(
                        item["size_bytes"] for item in payload["candidates"]
                    ),
                    "projects": len(projects),
                    "project_bytes": sum(
                        project["size_bytes"] for project in projects
                    ),
                    "applied": False,
                },
                sort_keys=True,
            )
        )
        return 0

    expected_snapshot = list(payload["snapshot"])
    before_projects = len(projects)
    before_bytes = sum(project["size_bytes"] for project in projects)
    deleted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for candidate in payload["candidates"]:
        projects = list_projects(binary)
        validate_snapshot(expected_snapshot, projects)
        revalidate_candidate(candidate, projects, prefixes)
        path = db_path(cache_dir, candidate["name"])
        if db_is_held(path):
            skipped.append({"name": candidate["name"], "reason": "held"})
            continue
        validate_database(path, candidate["size_bytes"])
        delete_project(binary, candidate["name"])
        projects = list_projects(binary)
        expected_snapshot = [
            item
            for item in expected_snapshot
            if item["name"] != candidate["name"]
        ]
        validate_snapshot(expected_snapshot, projects)
        deleted.append(
            {
                "name": candidate["name"],
                "bytes": candidate["size_bytes"],
                "reason": candidate["reason"],
            }
        )

    print(
        json.dumps(
            {
                "action": "prune",
                "manifest": str(manifest_path),
                "applied": True,
                "deleted": deleted,
                "deleted_bytes": sum(item["bytes"] for item in deleted),
                "skipped": skipped,
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
