from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import import_skills as IMPORT  # noqa: E402


class AgentSkillsImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.consumer = self.root / 'consumer'
        for directory in ('bin', 'scripts'):
            (self.consumer / directory).mkdir(parents=True)
        for name in ('bin/agent-skills', 'scripts/import_skills.py', 'scripts/managed_sync.py'):
            shutil.copy2(ROOT / name, self.consumer / name)
        self.catalog = self.consumer / 'catalog.yaml'
        self.catalog.write_text('version: 1\nskills:\n')
        self.upstream = self.root / 'upstream'
        self.upstream.mkdir()
        self.environment = {**os.environ, 'HOME': str(self.root), 'GIT_CONFIG_NOSYSTEM': '1',
                            'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_TERMINAL_PROMPT': '0'}
        self.git('init', '-b', 'main')
        self.skill = self.upstream / 'skills/demo'
        self.skill.mkdir(parents=True)
        self.first = self.commit('one\n')
        self.target = self.consumer / 'vendor/fixture/demo'

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args):
        return subprocess.check_output(
            ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
             '-c', 'commit.gpgsign=false', '-C', str(self.upstream), *args],
            env=self.environment, stderr=subprocess.DEVNULL, text=True,
        ).strip()

    def commit(self, text):
        (self.skill / 'SKILL.md').write_text(text)
        self.git('add', '.')
        self.git('commit', '-m', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def cli(self, *arguments, check=True):
        return subprocess.run([str(self.consumer / 'bin/agent-skills'), *arguments],
                              env=self.environment, capture_output=True, text=True, check=check)

    def import_cli(self, *extra, check=True):
        return self.cli('import', '--source', 'fixture', '--repo', str(self.upstream),
                        '--ref', 'main', '--subdir', 'skills', '--skills', 'demo',
                        *extra, check=check)

    def import_direct(self, **kwargs):
        IMPORT.import_selected(self.consumer, 'fixture', 'https://example.invalid/skills.git',
                               'main', self.git('rev-parse', 'HEAD'), [self.skill], checkout=self.upstream, **kwargs)

    def test_reimport_moving_ref_updates_files_and_commit(self):
        self.import_cli()
        second = self.commit('two\n')
        self.import_cli()
        self.assertEqual((self.target / 'SKILL.md').read_text(), 'two\n')
        catalog = self.catalog.read_text()
        self.assertIn(f'commit: "{second}"', catalog)
        self.assertNotIn(self.first, catalog)
        self.assertEqual(catalog.count('  - id: fixture-demo\n'), 1)
        self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())
        self.import_cli()
        self.assertEqual(self.catalog.read_text(), catalog)

    def test_reimport_preserves_annotations_and_updates_repo_ref_format(self):
        self.import_cli()
        original = self.catalog.read_text()
        annotated = original.replace('name: "fixture/demo"', 'name: "Custom name" # keep name')
        annotated = annotated.replace('type: git', 'type: "git" # keep type')
        annotated = annotated.replace('ref: "main"', "ref: 'main' # keep ref")
        annotated = annotated.replace('    tags:', '    notes: "Retain: this # annotation"\n    tags:')
        unrelated = '\n  - id: local\n    name: Local\n    source: local\n    tags: [custom]\n'
        self.catalog.write_text(annotated + unrelated)
        (self.skill / 'SKILL.md').unlink()
        (self.skill / 'AGENT.md').write_text('new format\n')
        IMPORT.import_selected(self.consumer, 'fixture', 'https://example.invalid/new:repo.git',
                               'release/#1', self.first, [self.skill], checkout=self.upstream)
        result = self.catalog.read_text()
        self.assertIn('name: "Custom name" # keep name', result)
        self.assertIn('type: "git" # keep type', result)
        self.assertIn('ref: "release/#1" # keep ref', result)
        self.assertIn('repo: "https://example.invalid/new:repo.git"', result)
        self.assertIn('format: "agent_md"', result)
        self.assertIn('notes: "Retain: this # annotation"', result)
        self.assertIn('tags: [upstream, imported]', result)
        self.assertTrue(result.endswith(unrelated))
        self.assertFalse((self.target / 'SKILL.md').exists())
        self.assertEqual((self.target / 'AGENT.md').read_text(), 'new format\n')

    def test_existing_catalog_without_format_is_updated(self):
        self.import_cli()
        note = '    notes: "literal    upstream: label"\n'
        self.catalog.write_text(self.catalog.read_text().replace('    format: skill_md\n', note))
        self.import_cli()
        self.assertIn('    format: skill_md\n', self.catalog.read_text())
        self.assertIn(note, self.catalog.read_text())

    def test_dry_run_does_not_create_vendor_or_change_catalog(self):
        before = IMPORT.snapshot(self.catalog)
        self.import_cli('--dry-run')
        self.assertEqual(IMPORT.snapshot(self.catalog), before)
        self.assertFalse((self.consumer / 'vendor').exists())
        self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())

    def test_invalid_source_and_subdir_stop_before_clone(self):
        for option, value in (('--source', '../escape'), ('--source', 'source.*'),
                              ('--subdir', '../outside'), ('--subdir', '/absolute')):
            with self.subTest(value=value):
                result = self.import_cli(option, value, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Cloning ', result.stdout)
        self.assertFalse((self.consumer / 'vendor').exists())

    def test_duplicate_selected_names_and_catalog_ids_are_rejected(self):
        with self.assertRaisesRegex(IMPORT.sync.SyncError, 'duplicate imported skill'):
            IMPORT.import_selected(self.consumer, 'fixture', 'repo', 'main', self.first,
                                   [self.skill, self.skill], checkout=self.upstream)
        self.import_cli()
        self.catalog.write_text(self.catalog.read_text() + '\n  - id: fixture-demo\n')
        before = IMPORT.snapshot(self.target)
        result = self.import_cli(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('duplicate catalog id', result.stderr)
        self.assertEqual(IMPORT.snapshot(self.target), before)

    def test_ambiguous_skill_selection_stops_before_publication(self):
        duplicate = self.upstream / 'skills/nested/demo'
        duplicate.mkdir(parents=True)
        (duplicate / 'SKILL.md').write_text('duplicate\n')
        self.commit('two\n')
        result = self.import_cli(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ambiguous', result.stderr)
        self.assertFalse((self.consumer / 'vendor').exists())

    def test_batch_failure_restores_earlier_skill_and_subset_preserves_unselected(self):
        self.import_cli()
        other = self.upstream / 'skills/other'
        other.mkdir()
        (other / 'AGENT.md').write_text('other\n')
        second = self.commit('two\n')
        before = (IMPORT.snapshot(self.catalog), IMPORT.snapshot(self.target))
        original = IMPORT.sync.rename_noreplace

        def fail_second(source, destination):
            if source.name == 'new-1':
                raise OSError('second skill failed')
            return original(source, destination)

        with mock.patch.object(IMPORT.sync, 'rename_noreplace', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'second skill failed'):
                IMPORT.import_selected(self.consumer, 'fixture', 'repo', 'main', second,
                                       [self.skill, other], checkout=self.upstream)
        self.assertEqual((IMPORT.snapshot(self.catalog), IMPORT.snapshot(self.target)), before)
        self.assertFalse((self.target.parent / 'other').exists())
        self.import_cli('--skills', 'demo,other')
        other_before = IMPORT.snapshot(self.target.parent / 'other')
        third = self.commit('three\n')
        self.import_cli()
        self.assertEqual(IMPORT.snapshot(self.target.parent / 'other'), other_before)
        self.assertIn(f'commit: "{second}"', self.catalog.read_text())
        self.assertIn(f'commit: "{third}"', self.catalog.read_text())

    def test_unsupported_or_conflicting_catalog_never_changes_target(self):
        self.import_cli()
        original = self.catalog.read_text()
        for changed in (original.replace('  - id: fixture-demo', '  - id: "fixture-demo"'),
                        original.replace('source: upstream', 'source: local'),
                        original.replace('type: git', 'type: webpage'),
                        original.replace('vendor/fixture/demo', 'skills/demo'),
                        original.replace('ref: "main"', 'ref: |\n        main')):
            with self.subTest(catalog=changed):
                self.catalog.write_text(changed)
                before = IMPORT.snapshot(self.target)
                self.assertNotEqual(self.import_cli(check=False).returncode, 0)
                self.assertEqual(IMPORT.snapshot(self.target), before)
                self.assertEqual(self.catalog.read_text(), changed)

    def test_catalog_failure_restores_both_existing_and_new_imports(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    self.import_cli()
                before = (IMPORT.snapshot(self.catalog), IMPORT.snapshot(self.target))
                original = IMPORT.sync.rename_noreplace

                def fail_catalog(source, destination):
                    if source.name == 'new-catalog':
                        raise OSError('catalog publication failed')
                    return original(source, destination)

                self.commit('two\n' if existing else 'first attempt\n')
                with mock.patch.object(IMPORT.sync, 'rename_noreplace', side_effect=fail_catalog):
                    with self.assertRaisesRegex(OSError, 'catalog publication failed'):
                        self.import_direct()
                self.assertEqual((IMPORT.snapshot(self.catalog), IMPORT.snapshot(self.target)), before)
                self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())
                if not existing:
                    self.assertFalse((self.consumer / 'vendor').exists())

    def test_trailing_top_level_catalog_content_stops_before_publication(self):
        self.import_cli()
        self.catalog.write_text(self.catalog.read_text() + '\nmetadata:\n  note: keep\n')
        self.commit('two\n')
        before = (IMPORT.snapshot(self.catalog), IMPORT.snapshot(self.consumer / 'vendor'))
        for source in ('new-source', 'fixture'):
            with self.subTest(source=source):
                result = self.import_cli('--source', source, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('unsupported top-level catalog content after skills', result.stderr)
                self.assertEqual((IMPORT.snapshot(self.catalog),
                                  IMPORT.snapshot(self.consumer / 'vendor')), before)
                self.assertFalse((self.consumer / 'vendor/new-source').exists())
                self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())

    def test_copy_failure_precedes_all_publication(self):
        self.import_cli()
        before = (IMPORT.snapshot(self.catalog), IMPORT.snapshot(self.target))
        with mock.patch.object(IMPORT.shutil, 'copytree', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.import_direct()
        self.assertEqual((IMPORT.snapshot(self.catalog), IMPORT.snapshot(self.target)), before)
        self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())

    def test_catalog_race_preserves_new_writer_and_retains_recovery(self):
        self.import_cli()
        original_catalog = self.catalog.read_bytes()
        self.commit('two\n')
        original = IMPORT.sync.rename_noreplace

        def race_catalog(source, destination):
            if source.name == 'new-catalog':
                self.catalog.write_text('another writer\n')
            return original(source, destination)

        with mock.patch.object(IMPORT.sync, 'rename_noreplace', side_effect=race_catalog):
            with self.assertRaisesRegex(IMPORT.sync.SyncError, 'recovery retained'):
                self.import_direct()
        self.assertEqual(self.catalog.read_text(), 'another writer\n')
        recovery = self.consumer / IMPORT.RECOVERY
        self.assertEqual((recovery / 'old-1').read_bytes(), original_catalog)
        self.assertEqual((recovery / 'old-0/SKILL.md').read_text(), 'one\n')
        self.assertEqual((self.target / 'SKILL.md').read_text(), 'two\n')
        for arguments in (('list',), ('sync', '--dry-run'), ('validate',),
                          ('import', '--source', 'fixture', '--repo', 'unused')):
            result = self.cli(*arguments, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('recovery retained', result.stderr)
        self.assertEqual(json.loads((recovery / 'recovery.json').read_text())['targets'],
                         ['vendor/fixture/demo', 'catalog.yaml'])

    def test_changed_vendor_afterimage_is_not_rolled_back(self):
        self.import_cli()
        self.commit('two\n')
        original = IMPORT.sync.rename_noreplace

        def late_edit(source, destination):
            if source.name == 'new-catalog':
                (self.target / 'SKILL.md').write_text('later local edit\n')
                raise OSError('catalog failure')
            return original(source, destination)

        with mock.patch.object(IMPORT.sync, 'rename_noreplace', side_effect=late_edit):
            with self.assertRaisesRegex(IMPORT.sync.SyncError, 'recovery retained'):
                self.import_direct()
        self.assertEqual((self.target / 'SKILL.md').read_text(), 'later local edit\n')
        self.assertEqual((self.consumer / IMPORT.RECOVERY / 'old-0/SKILL.md').read_text(), 'one\n')

    def test_symlinked_vendor_parent_is_rejected_without_touching_outside(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.consumer / 'vendor').symlink_to(outside, target_is_directory=True)
        before = IMPORT.snapshot(outside)
        with self.assertRaisesRegex(IMPORT.sync.SyncError, 'parents must be real'):
            self.import_direct()
        self.assertEqual(IMPORT.snapshot(outside), before)
        self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())

    def test_changed_backup_is_retained_without_removing_published_skill(self):
        self.import_cli()
        self.commit('two\n')
        original = IMPORT.sync.rename_noreplace

        def edit_backup(source, destination):
            result = original(source, destination)
            if source.name == 'new-catalog':
                (self.consumer / IMPORT.RECOVERY / 'old-0/SKILL.md').write_text('edited backup\n')
            return result

        with mock.patch.object(IMPORT.sync, 'rename_noreplace', side_effect=edit_backup):
            with self.assertRaisesRegex(IMPORT.sync.SyncError, 'recovery retained'):
                self.import_direct()
        self.assertEqual((self.consumer / IMPORT.RECOVERY / 'old-0/SKILL.md').read_text(), 'edited backup\n')
        self.assertEqual((self.target / 'SKILL.md').read_text(), 'two\n')

    def test_existing_regular_skill_target_is_preserved(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_text('unrelated file\n')
        before = IMPORT.snapshot(self.target)
        with self.assertRaisesRegex(IMPORT.sync.SyncError, 'targets must be real directories'):
            self.import_direct()
        self.assertEqual(IMPORT.snapshot(self.target), before)
        self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())

    def test_intermediate_subdir_symlink_cannot_import_outside_clone(self):
        outside = self.root / 'outside'
        skill = outside / 'subdir/demo'
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('outside fixture\n')
        (self.upstream / 'link').symlink_to(outside, target_is_directory=True)
        self.commit('two\n')
        before = (IMPORT.snapshot(outside), IMPORT.snapshot(self.catalog))
        fake_bin = self.root / 'fake-bin'
        fake_bin.mkdir()
        find = fake_bin / 'find'
        find.write_text('#!/bin/sh\necho discovery-ran >&2\nexit 99\n')
        find.chmod(0o755)
        with mock.patch.dict(self.environment, {'PATH': str(fake_bin) + os.pathsep + self.environment['PATH']}):
            result = self.import_cli('--subdir', 'link/subdir', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('outside the cloned checkout', result.stderr)
        self.assertNotIn('discovery-ran', result.stderr)
        self.assertEqual((IMPORT.snapshot(outside), IMPORT.snapshot(self.catalog)), before)
        self.assertFalse((self.consumer / 'vendor').exists())

    def test_publication_rejects_external_candidate_even_with_valid_base(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'SKILL.md').write_text('outside fixture\n')
        with self.assertRaisesRegex(IMPORT.sync.SyncError, 'outside the cloned checkout'):
            IMPORT.import_selected(self.consumer, 'fixture', 'repo', 'main', self.first,
                                   [outside], checkout=self.upstream)
        self.assertFalse((self.consumer / 'vendor').exists())
        self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())

    def test_root_skill_import_excludes_clone_metadata_and_preserves_nested_skills(self):
        (self.upstream / 'SKILL.md').write_text('root skill\n')
        (self.upstream / '.github').mkdir()
        (self.upstream / '.github/config.yml').write_text('tracked: yes\n')
        (self.upstream / '.gitignore').write_text('ignored-fixture\n')
        commit = self.commit('nested skill\n')
        self.cli('import', '--source', 'fixture', '--repo', str(self.upstream), '--ref', 'main')
        root_target = self.consumer / 'vendor/fixture/repo'
        self.assertEqual((root_target / 'SKILL.md').read_text(), 'root skill\n')
        self.assertEqual((root_target / '.github/config.yml').read_text(), 'tracked: yes\n')
        self.assertEqual((root_target / '.gitignore').read_text(), 'ignored-fixture\n')
        self.assertEqual((root_target / 'skills/demo/SKILL.md').read_text(), 'nested skill\n')
        self.assertEqual((self.target / 'SKILL.md').read_text(), 'nested skill\n')
        self.assertFalse(os.path.lexists(root_target / '.git'))
        self.assertEqual(self.catalog.read_text().count(f'commit: "{commit}"'), 2)
        self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())
        template = self.root / 'git-template'
        template.mkdir()
        (template / 'SKILL.md').write_text('clone metadata fixture\n')
        self.environment['GIT_TEMPLATE_DIR'] = str(template)
        (self.upstream / 'SKILL.md').write_text('updated root skill\n')
        second = self.commit('updated nested skill\n')
        self.cli('import', '--source', 'fixture', '--repo', str(self.upstream), '--ref', 'main')
        self.assertEqual((root_target / 'SKILL.md').read_text(), 'updated root skill\n')
        self.assertEqual((root_target / 'skills/demo/SKILL.md').read_text(), 'updated nested skill\n')
        self.assertEqual((self.target / 'SKILL.md').read_text(), 'updated nested skill\n')
        self.assertFalse(os.path.lexists(root_target / '.git'))
        self.assertEqual(self.catalog.read_text().count(f'commit: "{second}"'), 2)
        self.assertNotIn(commit, self.catalog.read_text())
        self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())

    def test_git_metadata_exclusion_cannot_hide_unexpected_staged_content(self):
        (self.skill / '.git').write_text('gitdir: fixture\n')
        (self.skill / '.gitmodules').write_text('# tracked source fixture\n')
        self.import_direct()
        self.assertFalse(os.path.lexists(self.target / '.git'))
        self.assertEqual((self.target / '.gitmodules').read_text(), '# tracked source fixture\n')
        before = (IMPORT.snapshot(self.catalog), IMPORT.snapshot(self.target))
        original = IMPORT.shutil.copytree

        def leak_metadata(source, destination, **kwargs):
            result = original(source, destination, **kwargs)
            (destination / '.git').write_text('unexpected staged metadata\n')
            return result

        with mock.patch.object(IMPORT.shutil, 'copytree', side_effect=leak_metadata):
            with self.assertRaisesRegex(IMPORT.sync.SyncError, 'source changed during staging'):
                self.import_direct()
        self.assertEqual((IMPORT.snapshot(self.catalog), IMPORT.snapshot(self.target)), before)
        self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())

    def test_explicit_metadata_candidate_is_rejected_before_staging(self):
        candidate = self.upstream / '.git/metadata-skill'
        candidate.mkdir()
        (candidate / 'SKILL.md').write_text('metadata fixture\n')
        with self.assertRaisesRegex(IMPORT.sync.SyncError, 'import source is Git metadata'):
            IMPORT.import_selected(self.consumer, 'fixture', 'repo', 'main', self.first,
                                   [candidate], checkout=self.upstream)
        self.assertFalse((self.consumer / 'vendor').exists())
        self.assertFalse((self.consumer / IMPORT.RECOVERY).exists())


if __name__ == '__main__':
    unittest.main()
