from __future__ import annotations

import importlib.util
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("managed_sync", ROOT / "scripts/managed_sync.py")
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


class AgentSkillsSyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name).resolve()
        self.repo = self.root / "repo"
        for directory in ("bin", "scripts", "skills/owned", "slash-commands"):
            (self.repo / directory).mkdir(parents=True)
        for file in ("bin/agent-skills", "scripts/managed_sync.py"):
            shutil.copy2(ROOT / file, self.repo / file)
        self.skill = self.repo / "skills/owned"
        (self.skill / "SKILL.md").write_text("one\n")
        self.command = self.repo / "slash-commands/owned.md"
        self.command.write_text("command one\n")
        self.codex = self.root / "codex"
        self.destination = self.codex / "skills/owned"

    def tearDown(self):
        self.temporary.cleanup()

    def sync(self, mode="copy", check=True):
        return subprocess.run(
            [str(self.repo / "bin/agent-skills"), "sync", "--mode", mode],
            env={**os.environ, "CODEX_HOME": str(self.codex)},
            capture_output=True, text=True, check=check,
        )

    def test_wrapper_updates_owned_copies_and_both_mode_transitions(self):
        self.sync()
        markers = (self.destination / SYNC.DIRECTORY_MARKER,
                   self.codex / "prompts/.owned.md.agent-skills-managed.json")
        for marker in markers:
            self.assertEqual(stat.S_IMODE(marker.stat().st_mode), 0o600)
        (self.skill / "SKILL.md").write_text("two\n")
        self.command.write_text("command two\n")
        self.sync()
        self.assertEqual((self.destination / "SKILL.md").read_text(), "two\n")
        self.assertEqual((self.codex / "prompts/owned.md").read_text(), "command two\n")
        self.sync("symlink")
        self.assertTrue(self.destination.is_symlink())
        inode = self.destination.lstat().st_ino
        self.sync("symlink")
        self.assertEqual(self.destination.lstat().st_ino, inode)
        self.sync("copy")
        self.assertFalse(self.destination.is_symlink())
        self.assertFalse(list(self.codex.rglob(".agent-skills-stage-*")))

    def test_local_edits_extra_files_modes_and_foreign_destinations_are_preserved(self):
        for change in ("edit", "extra", "mode", "foreign-marker"):
            with self.subTest(change=change):
                if self.codex.exists():
                    shutil.rmtree(self.codex)
                self.sync()
                entry = self.destination / "SKILL.md"
                if change == "edit":
                    entry.write_text("local edit\n")
                elif change == "extra":
                    (self.destination / "decision-ledger.json").write_text("local state")
                elif change == "mode":
                    entry.chmod(0o600)
                else:
                    (self.destination / SYNC.DIRECTORY_MARKER).write_text("{}")
                before = SYNC.content_digest(self.destination)
                self.assertNotEqual(self.sync(check=False).returncode, 0)
                self.assertEqual(SYNC.content_digest(self.destination), before)

    def test_unmarked_exact_copy_can_migrate_but_different_copy_cannot(self):
        shutil.copytree(self.skill, self.destination)
        self.sync()
        self.assertTrue((self.destination / SYNC.DIRECTORY_MARKER).is_file())
        shutil.rmtree(self.destination)
        shutil.copytree(self.skill, self.destination)
        (self.destination / "private.txt").write_text("keep")
        result = self.sync(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reconcile before syncing", result.stderr)
        self.assertEqual((self.destination / "private.txt").read_text(), "keep")

    def test_foreign_symlink_and_edited_prompt_are_preserved(self):
        self.destination.parent.mkdir(parents=True)
        self.destination.symlink_to(self.root)
        self.assertNotEqual(self.sync(check=False).returncode, 0)
        self.assertEqual(self.destination.resolve(), self.root)
        self.destination.unlink()
        self.sync()
        command = self.codex / "prompts/owned.md"
        command.write_text("local command")
        self.assertNotEqual(self.sync(check=False).returncode, 0)
        self.assertEqual(command.read_text(), "local command")

    def test_staging_failure_does_not_move_the_original(self):
        self.sync()
        before = SYNC.content_digest(self.destination)
        with mock.patch.object(SYNC.shutil, "copytree", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                SYNC.install(self.skill, self.destination, kind="directory", mode="copy")
        self.assertEqual(SYNC.content_digest(self.destination), before)
        self.assertFalse(list(self.destination.parent.glob(".agent-skills-stage-*")))

    def test_destination_appearing_before_first_publish_is_preserved(self):
        original = SYNC.rename_noreplace

        def raced(source, destination):
            if source.name == "new":
                destination.mkdir()
                (destination / "foreign").write_text("keep")
            return original(source, destination)

        with mock.patch.object(SYNC, "rename_noreplace", side_effect=raced):
            with self.assertRaisesRegex(SYNC.SyncError, "destination appeared"):
                SYNC.install(self.skill, self.destination, kind="directory", mode="copy")
        self.assertEqual((self.destination / "foreign").read_text(), "keep")

    def test_publication_conflict_keeps_foreign_destination_and_old_copy(self):
        self.sync()
        (self.skill / "SKILL.md").write_text("two\n")
        original = SYNC.rename_noreplace

        def raced(source, destination):
            if source.name == "new":
                destination.mkdir()
                (destination / "foreign").write_text("keep")
            return original(source, destination)

        with mock.patch.object(SYNC, "rename_noreplace", side_effect=raced):
            with self.assertRaisesRegex(SYNC.SyncError, "recovery retained"):
                SYNC.install(self.skill, self.destination, kind="directory", mode="copy")
        self.assertEqual((self.destination / "foreign").read_text(), "keep")
        stages = list(self.destination.parent.glob(".agent-skills-stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / "previous/SKILL.md").read_text(), "one\n")

    def test_failed_restore_keeps_recovery_for_files_and_directories(self):
        self.sync()
        cases = ((self.skill, self.destination, "directory"),
                 (self.command, self.codex / "prompts/owned.md", "file"))
        for source, destination, kind in cases:
            with self.subTest(kind=kind):
                original = SYNC.rename_noreplace

                def failed(old, new):
                    if old.name in {"new", "new-marker", "previous", "previous-marker"}:
                        raise OSError("publication and recovery unavailable")
                    return original(old, new)

                with mock.patch.object(SYNC, "rename_noreplace", side_effect=failed):
                    with self.assertRaisesRegex(SYNC.SyncError, "recovery retained"):
                        SYNC.install(source, destination, kind=kind, mode="copy")
                stages = list(destination.parent.glob(".agent-skills-stage-*"))
                self.assertEqual(len(stages), 1)
                old = stages[0] / "previous"
                self.assertEqual((old / "SKILL.md").read_text() if kind == "directory"
                                 else old.read_text(), "one\n" if kind == "directory" else "command one\n")

    def test_change_after_validation_is_restored_without_clobbering(self):
        self.sync()
        original = SYNC.rename_noreplace

        def edited(source, destination):
            if destination.name == "previous":
                (source / "SKILL.md").write_text("late edit\n")
            return original(source, destination)

        with mock.patch.object(SYNC, "rename_noreplace", side_effect=edited):
            with self.assertRaises(SYNC.SyncError):
                SYNC.install(self.skill, self.destination, kind="directory", mode="copy")
        self.assertEqual((self.destination / "SKILL.md").read_text(), "late edit\n")

    def test_prompt_failure_after_marker_publish_retains_complete_recovery(self):
        self.sync()
        destination = self.codex / "prompts/owned.md"
        self.command.write_text("command two\n")
        original = SYNC.rename_noreplace

        def failed(source, target):
            if source.name == "new":
                raise OSError("data publication failed")
            return original(source, target)

        with mock.patch.object(SYNC, "rename_noreplace", side_effect=failed):
            with self.assertRaisesRegex(SYNC.SyncError, "data publication failed.*recovery retained"):
                SYNC.install(self.command, destination, kind="file", mode="copy")
        self.assertEqual(destination.read_text(), "command one\n")
        stages = list(destination.parent.glob(".agent-skills-stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertTrue((stages[0] / "previous-marker").is_file())
        self.assertEqual((stages[0] / "new").read_text(), "command two\n")
        with self.assertRaisesRegex(SYNC.SyncError, "managed marker does not match"):
            SYNC.install(self.command, destination, kind="file", mode="copy")

    def test_parent_swap_cannot_redirect_staging_or_publication(self):
        self.sync()
        old_parent = self.destination.parent
        moved_parent = old_parent.with_name("moved-skills")
        original = SYNC.stage_install

        def swap_parent(*args, **kwargs):
            result = original(*args, **kwargs)
            old_parent.rename(moved_parent)
            old_parent.mkdir()
            (old_parent / "foreign").write_text("keep")
            return result

        with mock.patch.object(SYNC, "stage_install", side_effect=swap_parent):
            with self.assertRaisesRegex(SYNC.SyncError, "parent moved"):
                SYNC.install(self.skill, self.destination, kind="directory", mode="copy")
        self.assertEqual((old_parent / "foreign").read_text(), "keep")
        self.assertEqual((moved_parent / "owned/SKILL.md").read_text(), "one\n")
        self.assertFalse(list(moved_parent.glob(".agent-skills-stage-*")))

    def test_unsupported_platform_does_not_create_destination(self):
        with mock.patch.object(SYNC.sys, "platform", "unsupported"):
            with self.assertRaisesRegex(SYNC.SyncError, "requires macOS or Linux"):
                SYNC.install(self.skill, self.destination, kind="directory", mode="copy")
        self.assertFalse(self.codex.exists())

    def test_overlapping_source_and_destination_are_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.skill.parent)
        for destination in (self.skill / "nested", self.skill.parent, alias / "owned"):
            with self.subTest(destination=destination):
                with self.assertRaisesRegex(SYNC.SyncError, "overlaps"):
                    SYNC.install(self.skill, destination, kind="directory", mode="copy")
        self.assertEqual((self.skill / "SKILL.md").read_text(), "one\n")


if __name__ == "__main__":
    unittest.main()
