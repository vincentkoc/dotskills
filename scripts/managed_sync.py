#!/usr/bin/env python3
"""Publish complete skills without overwriting local content or failed recovery."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import errno
import hashlib
import json
import os
import pathlib
import shutil
import stat
import sys
import tempfile


DIRECTORY_MARKER = ".agent-skills-managed.json"


class SyncError(RuntimeError):
    pass


def rename_noreplace(source: pathlib.Path, destination: pathlib.Path) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function = library.renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        arguments = (os.fsencode(source), os.fsencode(destination), 4)  # RENAME_EXCL
    elif sys.platform.startswith("linux"):
        function = getattr(library, "renameat2", None)
        if function is None:
            raise SyncError("atomic no-replace rename is unavailable")
        function.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
        ]
        arguments = (-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    else:
        raise SyncError("managed sync requires macOS or Linux no-replace rename")
    function.restype = ctypes.c_int
    if function(*arguments) != 0:
        error = ctypes.get_errno()
        if error in {errno.EEXIST, errno.ENOTEMPTY}:
            raise SyncError(f"destination appeared during sync: {destination}")
        raise OSError(error, os.strerror(error), str(destination))


def identity(path: pathlib.Path) -> tuple[int, int, int]:
    info = path.lstat()
    return info.st_dev, info.st_ino, info.st_mode


def file_state(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns, info.st_uid, info.st_gid, info.st_nlink)


def content_digest(path: pathlib.Path, *, ignore_marker: bool = False,
                   exclude_names: frozenset[str] = frozenset()) -> str:
    digest = hashlib.sha256()

    def field(value: bytes) -> None:
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)

    def visit(current: pathlib.Path, relative: pathlib.Path) -> None:
        before = current.lstat()
        field(os.fsencode(relative))
        field(str(before.st_mode).encode())
        if stat.S_ISLNK(before.st_mode):
            field(os.fsencode(os.readlink(current)))
        elif stat.S_ISDIR(before.st_mode):
            for child in sorted(current.iterdir(), key=lambda item: os.fsencode(item.name)):
                if child.name in exclude_names:
                    continue
                if ignore_marker and current == path and child.name == DIRECTORY_MARKER:
                    continue
                visit(child, relative / child.name)
        elif stat.S_ISREG(before.st_mode):
            # A swapped symlink must not redirect hashing into another file.
            # Frame payload bytes too: file contents must not impersonate the
            # following entry's header and hide an extra local file.
            digest.update(before.st_size.to_bytes(8, "big"))
            descriptor = os.open(current, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as handle:
                if file_state(os.fstat(handle.fileno())) != file_state(before):
                    raise SyncError(f"content changed during sync: {current}")
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
        else:
            raise SyncError(f"unsupported managed content: {current}")
        if file_state(current.lstat()) != file_state(before):
            raise SyncError(f"content changed during sync: {current}")

    visit(path, pathlib.Path("."))
    return digest.hexdigest()


def marker_for(destination: pathlib.Path, kind: str) -> pathlib.Path:
    if kind == "directory":
        return destination / DIRECTORY_MARKER
    return destination.with_name(f".{destination.name}.agent-skills-managed.json")


def read_marker(path: pathlib.Path) -> dict:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
            raise SyncError(f"unsafe managed marker: {path}")
        try:
            payload = json.load(handle)
        except (ValueError, UnicodeDecodeError) as error:
            raise SyncError(f"malformed managed marker: {path}") from error
    if not isinstance(payload, dict):
        raise SyncError(f"malformed managed marker: {path}")
    return payload


def metadata(source: pathlib.Path, kind: str, digest: str) -> dict:
    return {"version": 1, "source": str(source), "kind": kind, "digest": digest}


def validate_existing(
    source: pathlib.Path, destination: pathlib.Path, *, kind: str,
    marker_path: pathlib.Path | None = None,
) -> dict:
    marker = marker_path or marker_for(destination, kind)
    has_marker = os.path.lexists(marker) if kind == "file" else False
    if not os.path.lexists(destination):
        if has_marker:
            raise SyncError(f"orphaned managed marker blocks sync: {marker}")
        return {"state": "absent"}
    before = identity(destination)
    if destination.is_symlink():
        if has_marker or os.readlink(destination) != str(source):
            raise SyncError(f"refusing to replace foreign symlink: {destination}")
        return {"state": "symlink", "identity": before}
    expected_type = stat.S_ISDIR if kind == "directory" else stat.S_ISREG
    if not expected_type(before[2]):
        raise SyncError(f"refusing to replace foreign destination: {destination}")
    digest = content_digest(destination, ignore_marker=kind == "directory")
    if os.path.lexists(marker):
        marker_identity = identity(marker)
        if read_marker(marker) != metadata(source, kind, digest):
            raise SyncError(f"managed marker does not match installed content: {destination}")
    else:
        # Older copies had no marker. Adopt only an exact source copy; a name
        # match never establishes ownership of a different or locally edited tree.
        if digest != content_digest(source):
            raise SyncError(f"unmanaged or edited copy; reconcile before syncing: {destination}")
        marker_identity = None
    if identity(destination) != before:
        raise SyncError(f"destination changed during validation: {destination}")
    return {"state": "copy", "identity": before, "digest": digest, "marker": marker_identity}


@contextlib.contextmanager
def pinned_parent(parent: pathlib.Path):
    """This CLI is single-threaded: pin relative operations to one directory inode."""
    parent.mkdir(parents=True, exist_ok=True)
    parent = parent.resolve(strict=True)
    descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    previous = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
    expected = os.fstat(descriptor)

    def check() -> None:
        actual = parent.stat()
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise SyncError(f"destination parent moved during sync: {parent}")

    try:
        os.fchdir(descriptor)
        check()
        yield check
    finally:
        os.fchdir(previous)
        os.close(previous)
        os.close(descriptor)


def stage_install(source: pathlib.Path, stage: pathlib.Path, *, kind: str, mode: str):
    staged = stage / "new"
    marker = None
    if mode == "symlink":
        staged.symlink_to(source, target_is_directory=kind == "directory")
    else:
        before = content_digest(source)
        if kind == "directory":
            shutil.copytree(source, staged, symlinks=True)
            if os.path.lexists(staged / DIRECTORY_MARKER):
                raise SyncError("source contains the reserved managed marker")
        else:
            shutil.copy2(source, staged)
        digest = content_digest(staged)
        if digest != before or content_digest(source) != before:
            raise SyncError("source changed during staging")
        marker = staged / DIRECTORY_MARKER if kind == "directory" else stage / "new-marker"
        with marker.open("x", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(metadata(source, kind, digest), handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if kind == "directory":
            marker = None  # The directory and its marker publish together.
    return staged, marker


def publish(
    source: pathlib.Path, destination: pathlib.Path, stage: pathlib.Path,
    staged: pathlib.Path, staged_marker: pathlib.Path | None,
    expected: dict, *, kind: str, check_parent,
) -> None:
    marker = marker_for(destination, kind)
    previous = stage / "previous"
    previous_marker = stage / "previous-marker"
    moved = []
    try:
        check_parent()
        if validate_existing(source, destination, kind=kind) != expected:
            raise SyncError("destination changed before publication")
        if expected["state"] != "absent":
            rename_noreplace(destination, previous)
            moved.append((previous, destination))
        if kind == "file" and expected.get("marker") is not None:
            rename_noreplace(marker, previous_marker)
            moved.append((previous_marker, marker))
        if moved and validate_existing(
            source, previous, kind=kind, marker_path=previous_marker if kind == "file" else None,
        ) != expected:
            raise SyncError("destination changed after validation")
        check_parent()
        # Publish the prompt marker first. A failed second rename leaves a
        # visible refusal on the next sync; rollback never deletes a raced path.
        if staged_marker is not None:
            rename_noreplace(staged_marker, marker)
        rename_noreplace(staged, destination)
        check_parent()
        if moved and validate_existing(
            source, previous, kind=kind, marker_path=previous_marker if kind == "file" else None,
        ) != expected:
            raise SyncError("previous content changed; recovery retained")
    except BaseException:
        # Only an empty destination can receive recovery. Any intervening path,
        # including a newly published result, stays untouched for manual review.
        for backup, target in moved:
            if os.path.lexists(backup):
                try:
                    rename_noreplace(backup, target)
                except (OSError, SyncError):
                    pass
        raise


def install(source: pathlib.Path, destination: pathlib.Path, *, kind: str, mode: str) -> None:
    if sys.platform != "darwin" and not sys.platform.startswith("linux"):
        raise SyncError("managed sync requires macOS or Linux no-replace rename")
    source = source.resolve(strict=True)
    destination = pathlib.Path(os.path.abspath(destination))
    destination = destination.parent.resolve() / destination.name
    if not (source.is_dir() if kind == "directory" else source.is_file()):
        raise SyncError(f"invalid {kind} source: {source}")
    if (destination == source or destination in source.parents
            or source in destination.parents):
        raise SyncError("destination overlaps the source")
    with pinned_parent(destination.parent) as check_parent:
        target = pathlib.Path(destination.name)
        expected = validate_existing(source, target, kind=kind)
        if expected["state"] == "symlink" and mode == "symlink":
            return
        # Python 3.12 returns an absolute mkdtemp path even for dir=".".
        # Keep every later operation relative to the pinned directory inode.
        stage = pathlib.Path(pathlib.Path(tempfile.mkdtemp(
            prefix=".agent-skills-stage-", dir=".",
        )).name)
        stage_identity = identity(stage)

        def cleanup() -> None:
            if identity(stage) != stage_identity:
                raise SyncError("staging directory changed; refusing cleanup")
            shutil.rmtree(stage)

        def check_boundaries() -> None:
            check_parent()
            if identity(stage) != stage_identity:
                raise SyncError("staging directory changed; refusing publication")

        staged_marker = None
        try:
            staged, staged_marker = stage_install(source, stage, kind=kind, mode=mode)
            publish(source, target, stage, staged, staged_marker, expected,
                    kind=kind, check_parent=check_boundaries)
        except BaseException as error:
            # A backup's presence is custody, regardless of exception type.
            # Never let an ordinary filesystem failure erase failed recovery.
            marker_published = staged_marker is not None and not os.path.lexists(staged_marker)
            if any(stage.glob("previous*")) or marker_published:
                raise SyncError(
                    f"{error}; recovery retained in {destination.parent / stage}"
                ) from error
            try:
                cleanup()
            except (OSError, SyncError) as cleanup_error:
                raise SyncError(
                    f"{error}; cleanup failed at {destination.parent / stage}: {cleanup_error}"
                ) from error
            raise
        else:
            cleanup()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("install-directory", "install-file"))
    parser.add_argument("--source", required=True, type=pathlib.Path)
    parser.add_argument("--destination", required=True, type=pathlib.Path)
    parser.add_argument("--mode", choices=("copy", "symlink"), required=True)
    args = parser.parse_args()
    try:
        install(args.source, args.destination,
                kind="directory" if args.command == "install-directory" else "file",
                mode=args.mode)
    except (OSError, SyncError) as error:
        parser.exit(1, f"agent-skills: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
