#!/usr/bin/env python3
"""Sync the downloaded healthline seed database with the tracked source data.

Why this exists: the site's runtime data ships inside the Hugging Face asset bundle
(``instance_seed/healthline.db``), while every catalog value is also declared in
``seed_data.py``. Tracked, deterministic corrections to the source data (for example
image assignments) are applied to the downloaded database here, at build time, so a
code-only content fix never requires an asset-repository write.

Guarantees:
  * idempotent — a database that already matches performs no writes at all, so
    ``/reset/<site>`` byte-identity is preserved;
  * deterministic — rows are matched by slug/key and updated with literal values;
  * fail-fast — a missing database is reported, never silently ignored.

Usage: python3 migrate_seed.py [--db PATH] [--images-dir PATH] [--check]
       --check  verify only; exit 1 if a migration is pending
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / 'instance_seed' / 'healthline.db'
IMAGES_DIR = BASE_DIR / 'static' / 'images'

sys.path.insert(0, str(BASE_DIR))
import seed_data as SD  # noqa: E402


def _norm(value):
    return (value or '').strip()


def planned_image_edits(db_path: Path):
    """Return {table: [(row_id, slug/key, field, old, new)]} for rows that differ."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    edits: dict[str, list] = {}

    def collect(table, key_col, rows, field):
        existing = {r[key_col]: r for r in con.execute(f"SELECT * FROM {table}")}
        out = []
        for entry in rows:
            key = entry[0] if isinstance(entry, tuple) else entry['key']
            want = entry[1] if isinstance(entry, tuple) else entry['value']
            row = existing.get(key)
            if row is None:
                continue
            if _norm(row[field]) != _norm(want):
                out.append((row['id'], key, field, row[field], want))
        return out

    edits['articles'] = collect('articles', 'slug', [(a[0], a[4]) for a in SD.ARTICLES], 'image')
    edits['conditions'] = collect('conditions', 'slug', [(c[0], c[3]) for c in SD.CONDITIONS], 'image')
    edits['drugs'] = collect('drugs', 'slug', [(d[0], d[5]) for d in SD.DRUGS], 'image')
    edits['authors'] = collect('authors', 'key', [(p[0], p[4]) for p in SD.PEOPLE], 'headshot')
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ('articles', 'conditions', 'drugs', 'authors', 'users', 'sections')}
    missing = []
    referenced = set()
    for t, f in (('articles', 'image'), ('conditions', 'image'), ('drugs', 'image'), ('authors', 'headshot')):
        for r in con.execute(f"SELECT {f} AS img FROM {t} WHERE {f} IS NOT NULL AND {f} != ''"):
            referenced.add(_norm(r['img']))
    for name in sorted(referenced):
        if name and not (IMAGES_DIR / name).exists():
            missing.append(name)
    con.close()
    return edits, counts, missing


def main() -> int:
    ap = argparse.ArgumentParser()
    # scripts/fetch_assets.sh runs `migrate_seed.py <seed db>` for every site that
    # ships a migrator; accept that positional path as well as --db.
    ap.add_argument('db', nargs='?', default=os.environ.get('HEALTHLINE_SEED_DB', str(DEFAULT_DB)))
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f'[migrate] seed database not found: {db} (nothing to migrate)')
        return 0 if not args.check else 1

    edits, counts, missing = planned_image_edits(db)
    pending = sum(len(v) for v in edits.values())
    print(f'[migrate] {db}')
    print(f'[migrate] row counts: ' + ', '.join(f'{k}={v}' for k, v in counts.items()))
    for table, rows in edits.items():
        for row_id, slug, field, old, new in rows:
            print(f'  {table[:-1]} {slug}: {field} {old!r} -> {new!r}')
    if missing:
        print(f'[migrate] WARNING: {len(missing)} referenced image(s) missing on disk: {missing[:5]}')
    if pending == 0:
        print('[migrate] already in sync (no writes)')
        return 0
    print(f'[migrate] {pending} pending correction(s)')
    if args.check:
        return 1

    con = sqlite3.connect(db)
    for table, rows in edits.items():
        for row_id, slug, field, old, new in rows:
            con.execute(f'UPDATE {table} SET {field} = ? WHERE id = ?', (_norm(new), row_id))
    con.commit()
    # keep the rowid ordering stable and the file compact/deterministic
    con.execute('VACUUM')
    con.close()
    print(f'[migrate] applied {pending} correction(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
