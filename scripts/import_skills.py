#!/usr/bin/env python3
"""Publish selected vendor trees and their catalog provenance as one import."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat

import managed_sync as sync


NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
FORMATS = {"SKILL.md": "skill_md", "AGENT.md": "agent_md", "AGENTS.md": "agents_md"}
RECOVERY = ".agent-skills-import"
GIT_METADATA = frozenset({'.git'})


def require(condition, message):
    if not condition:
        raise sync.SyncError(message)


def inside_checkout(checkout, path):
    path = path.resolve(strict=True)
    require(path == checkout or checkout in path.parents, 'import source resolves outside the cloned checkout')
    require(not GIT_METADATA.intersection(path.relative_to(checkout).parts), 'import source is Git metadata')
    require(path.is_dir(), 'import source must be a directory')
    return path


def scalar(raw):
    """Read only the single-line scalar fields owned by this catalog writer."""
    raw = raw.strip()
    if raw.startswith('"'):
        value, end = json.JSONDecoder().raw_decode(raw)
        suffix = raw[end:].strip()
        require(isinstance(value, str) and (not suffix or suffix.startswith('#')),
                "unsupported catalog scalar")
    elif raw.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'\s*(#.*)?", raw)
        require(match is not None, "unsupported catalog scalar")
        value, suffix = match[1].replace("''", "'"), match[2] or ""
    else:
        parts = re.split(r"\s+#", raw, maxsplit=1)
        value, suffix = parts[0], "#" + parts[1] if len(parts) == 2 else ""
        require(bool(value) and value[0] not in "|>&*![{", "unsupported catalog scalar")
    return value, " " + suffix if suffix else ""


def field(block, key, indent, value=None):
    pattern = re.compile(rf"(?m)^{' ' * indent}{key}:([^\n]*)$")
    matches = list(pattern.finditer(block))
    require(len(matches) == 1, f"catalog requires one {key} field")
    match = matches[0]
    current, comment = scalar(match[1])
    if value is None:
        return current
    return block[:match.start()] + ' ' * indent + key + ': ' + json.dumps(value) + comment + block[match.end():]


def update_catalog(text, entries, repo, ref, commit):
    # Preserve all unowned bytes, including annotations, tags, and comments.
    # Unsupported catalog layouts stop before any vendor tree is published.
    headings = list(re.finditer(r"(?m)^skills:[ \t]*$", text))
    require(re.search(r"(?m)^version: 1\s*$", text) is not None
            and len(headings) == 1,
            "unsupported catalog header")
    require(re.search(r"(?m)^[^\s#]", text[headings[0].end():]) is None,
            "unsupported top-level catalog content after skills")
    starts = list(re.finditer(r"(?m)^  - id: ([a-z0-9]+(?:-[a-z0-9]+)*)[ \t]*(?:#.*)?$", text))
    require(len(starts) == len(re.findall(r"(?m)^  - ", text)), "unsupported catalog id layout")
    blocks = {}
    for index, start in enumerate(starts):
        require(start[1] not in blocks, "duplicate catalog id")
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        blocks[start[1]] = text[start.start():end]
    prefix = text[:starts[0].start()] if starts else text
    for entry in entries:
        identifier, path, format_name = entry
        if identifier not in blocks:
            blocks[identifier] = (
                f"\n  - id: {identifier}\n"
                f"    name: {json.dumps(path.removeprefix('vendor/'))}\n"
                f"    path: {json.dumps(path)}\n"
                f"    format: {format_name}\n"
                "    source: upstream\n    upstream:\n      type: git\n"
                f"      repo: {json.dumps(repo)}\n      ref: {json.dumps(ref)}\n"
                f"      commit: {json.dumps(commit)}\n    tags: [upstream, imported]\n\n"
            )
            continue
        block = blocks[identifier]
        require(field(block, 'path', 4) == path and field(block, 'source', 4) == 'upstream',
                f"catalog id belongs to another source: {identifier}")
        require(len(re.findall(r"(?m)^    upstream:", block)) == 1, 'catalog requires one upstream field')
        upstream = re.search(r"(?m)^    upstream:[ \t]*(?:#.*)?\n(?:^(?: {6}.*|[ \t]*)\n?)*", block)
        require(upstream is not None and field(upstream[0], 'type', 6) == 'git',
                f"catalog id is not a Git import: {identifier}")
        updated = upstream[0]
        for key, value in (('repo', repo), ('ref', ref), ('commit', commit)):
            updated = field(updated, key, 6, value)
        block = block[:upstream.start()] + updated + block[upstream.end():]
        if re.search(r"(?m)^    format:", block):
            block = field(block, 'format', 4, format_name)
        else:
            block = block[:upstream.start()] + f'    format: {format_name}\n' + block[upstream.start():]
        blocks[identifier] = block
    return prefix + ''.join(blocks.values())


def snapshot(path):
    if not os.path.lexists(path):
        return None
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), f"unsupported import target: {path}")
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_mtime_ns, sync.content_digest(path))


def publish(items, stage, check):
    """Catalog is last; reverse only our exact afterimages on a caught failure."""
    try:
        for index, item in enumerate(items):
            target, staged, expected = item['target'], item['staged'], item['before']
            check()
            require(snapshot(target) == expected, f"import target changed: {target}")
            if expected is not None:
                backup = stage / f'old-{index}'
                sync.rename_noreplace(target, backup)
                item['backup'] = backup
                require(snapshot(backup) == expected, f"import target changed during rename: {target}")
            check()
            sync.rename_noreplace(staged, target)
            item['published'] = True
            require(snapshot(target) == item['after'], f"published import changed: {target}")
        check()
        for item in items:
            require(snapshot(item['target']) == item['after'], 'import changed before completion')
            if item.get('backup'):
                require(snapshot(item['backup']) == item['before'], 'import backup changed before completion')
    except BaseException:
        for index, item in reversed(list(enumerate(items))):
            try:
                check()
                target = item['target']
                if item.get('backup'):
                    require(snapshot(item['backup']) == item['before'], f"recovery preimage changed: {target}")
                if item.get('published'):
                    require(snapshot(target) == item['after'], f"refusing changed afterimage: {target}")
                    sync.rename_noreplace(target, stage / f'rejected-{index}')
                if item.get('backup'):
                    sync.rename_noreplace(item['backup'], target)
                require(snapshot(target) == item['before'], f"recovery incomplete: {target}")
            except (OSError, sync.SyncError):
                # A retained lock blocks later list/sync/import until the exact
                # catalog and vendor pair can be reconciled without clobbering.
                break
        raise


def import_selected(root, source, repo, ref, commit, selected, *, checkout, dry_run=False):
    require(NAME.fullmatch(source) is not None, 'invalid import source name')
    require(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit) is not None, 'invalid import commit')
    require(bool(selected), 'no selected skills')
    root = root.resolve(strict=True)
    checkout = checkout.resolve(strict=True)
    entries, names, sources = [], set(), []
    for candidate in selected:
        candidate = inside_checkout(checkout, candidate)
        name = candidate.name
        require(NAME.fullmatch(name) is not None and name not in names, 'invalid or duplicate imported skill name')
        names.add(name)
        entry = next((key for key in FORMATS if (candidate / key).is_file()), None)
        require(entry is not None, 'selected skill has no entry file')
        entries.append((f'{source}-{name}', f'vendor/{source}/{name}', FORMATS[entry]))
        sources.append(candidate)
    with sync.pinned_parent(root) as check_root:
        stage = Path(RECOVERY)
        require(not os.path.lexists(stage), f'import in progress or recovery retained: {root / stage}')
        catalog = Path('catalog.yaml')
        catalog_before = snapshot(catalog)
        require(catalog_before is not None and stat.S_ISREG(catalog_before[2]), 'catalog must be a regular file')
        descriptor = os.open(catalog, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, 'r', encoding='utf-8') as handle:
            info = os.fstat(handle.fileno())
            require((info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                     info.st_mtime_ns) == catalog_before[:-1], 'catalog changed while opening')
            updated = update_catalog(handle.read(), entries, repo, ref, commit)
        require(snapshot(catalog) == catalog_before, 'catalog changed during preparation')
        targets = [Path(entry[1]) for entry in entries]
        parents = {path: sync.identity(path) if os.path.lexists(path) else None
                   for path in (Path('vendor'), Path('vendor') / source)}
        require(all(value is None or stat.S_ISDIR(value[2]) for value in parents.values()),
                'vendor parents must be real directories')
        before = [snapshot(target) for target in targets]
        require(all(value is None or stat.S_ISDIR(value[2]) for value in before),
                'existing skill targets must be real directories')
        if dry_run:
            print(f'[dry-run] import {len(entries)} skill(s) and update catalog provenance')
            return
        stage.mkdir(mode=0o700)
        stage_identity = sync.identity(stage)

        def check():
            check_root()
            require(sync.identity(stage) == stage_identity, 'import staging directory changed')
            for path, expected in parents.items():
                require((sync.identity(path) if os.path.lexists(path) else None) == expected,
                        'vendor parent changed during import')

        items, created = [], []
        try:
            for index, (candidate, target, expected) in enumerate(zip(sources, targets, before)):
                inside_checkout(checkout, candidate)
                staged = stage / f'new-{index}'
                # Root skills include clone metadata that is not upstream content.
                # Hash staged bytes unfiltered so an unexpected copy cannot hide.
                digest = sync.content_digest(candidate, exclude_names=GIT_METADATA)
                shutil.copytree(candidate, staged, symlinks=True, ignore=shutil.ignore_patterns(*GIT_METADATA))
                require(sync.content_digest(staged) == digest
                        == sync.content_digest(candidate, exclude_names=GIT_METADATA),
                        'import source changed during staging')
                items.append(dict(target=target, staged=staged, before=expected, after=snapshot(staged)))
            staged_catalog = stage / 'new-catalog'
            with staged_catalog.open('x', encoding='utf-8') as handle:
                os.fchmod(handle.fileno(), stat.S_IMODE(catalog_before[2]))
                handle.write(updated)
                handle.flush()
                os.fsync(handle.fileno())
            items.append(dict(target=catalog, staged=staged_catalog, before=catalog_before, after=snapshot(staged_catalog)))
            (stage / 'recovery.json').write_text(json.dumps({
                'version': 1, 'targets': [str(item['target']) for item in items],
                'before': [item['before'] for item in items], 'after': [item['after'] for item in items],
            }, indent=2) + '\n')
            check()
            for path, expected in parents.items():
                if expected is None:
                    path.mkdir()
                    parents[path] = sync.identity(path)
                    created.append(path)
            publish(items, stage, check)
        except BaseException as error:
            try:
                restored = all(snapshot(item['target']) == item['before'] for item in items)
            except (OSError, sync.SyncError):
                restored = False
            if not restored or any(stage.glob('old-*')):
                raise sync.SyncError(f'{error}; recovery retained at {root / stage}') from error
            check()
            for path in reversed(created):
                path.rmdir()
                parents[path] = None
            shutil.rmtree(stage)
            raise
        else:
            check()
            shutil.rmtree(stage)
    print(f'imported {len(entries)} skill(s); catalog provenance updated to {commit}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    base = commands.add_parser('resolve-base')
    base.add_argument('--checkout', required=True, type=Path)
    base.add_argument('--subdir', default='')
    publish_parser = commands.add_parser('publish')
    publish_parser.add_argument('--checkout', required=True, type=Path)
    for option in ('root', 'source', 'repo', 'ref', 'commit'):
        publish_parser.add_argument('--' + option, required=True)
    publish_parser.add_argument('--dry-run', action='store_true')
    publish_parser.add_argument('selected', nargs='+', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'resolve-base':
            checkout = args.checkout.resolve(strict=True)
            print(inside_checkout(checkout, checkout / args.subdir))
        else:
            import_selected(Path(args.root), args.source, args.repo, args.ref, args.commit,
                            args.selected, checkout=args.checkout, dry_run=args.dry_run)
    except (OSError, ValueError, sync.SyncError) as error:
        parser.exit(1, f'agent-skills: {error}\n')


if __name__ == '__main__':
    main()
