#!/usr/bin/env python3
"""Remove image files that no page can reference.

Why this exists: the pinned asset archive bundles images that the tracked catalog
never references (74 of 160 files, 57% of the image bytes). They are copied into the
image by ``COPY sites/`` even though no template, stylesheet or database row points at
them. This build-time step prunes exactly those files and reports what it removed.

The referenced set is derived from:
  * every image/headshot column of instance_seed/<site>.db (the runtime source), and
  * every image-looking filename mentioned in templates, CSS and JS.

Usage: python3 prune_unreferenced_images.py [--apply] [--report PATH]
       (without --apply it only reports; exit code 1 when files would be removed)
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB = BASE_DIR / 'instance_seed' / 'healthline.db'
IMAGES = BASE_DIR / 'static' / 'images'
NAME_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.\-]*\.(?:jpg|jpeg|png|gif|svg|webp)')
TEXT_GLOBS = ('templates/*.html', 'static/css/*.css', 'static/js/*.js')


def referenced_names() -> set[str]:
    names: set[str] = set()
    if DB.exists():
        con = sqlite3.connect(DB)
        for table, field in (('articles', 'image'), ('conditions', 'image'),
                             ('drugs', 'image'), ('authors', 'headshot')):
            for (value,) in con.execute(f"SELECT {field} FROM {table}"):
                if value and value.strip():
                    names.add(Path(value.strip()).name)
        con.close()
    for pattern in TEXT_GLOBS:
        for path in BASE_DIR.glob(pattern):
            names.update(NAME_RE.findall(path.read_text(errors='replace')))
    return names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--report', default=None)
    args = ap.parse_args()

    if not IMAGES.is_dir():
        print(f'[prune] image directory not found: {IMAGES}')
        return 0

    referenced = referenced_names()
    files = sorted(p for p in IMAGES.iterdir() if p.is_file())
    orphans = [p for p in files if p.name not in referenced]
    bytes_removed = sum(p.stat().st_size for p in orphans)
    report = {
        'image_dir': str(IMAGES),
        'files_total': len(files),
        'referenced': len(referenced & {p.name for p in files}),
        'orphans': len(orphans),
        'orphan_bytes': bytes_removed,
        'total_bytes': sum(p.stat().st_size for p in files),
        'orphan_files': [p.name for p in orphans],
    }
    print(f'[prune] {len(files)} image files, {len(orphans)} unreferenced '
          f'({bytes_removed} bytes of {report["total_bytes"]})')
    for name in report['orphan_files']:
        print(f'  unreferenced: {name}')
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2) + '\n')
        print(f'[prune] report written to {args.report}')

    if not orphans:
        print('[prune] nothing to remove')
        return 0
    if not args.apply:
        print('[prune] dry run (pass --apply to remove)')
        return 1
    for p in orphans:
        p.unlink()
    print(f'[prune] removed {len(orphans)} file(s), {bytes_removed} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
