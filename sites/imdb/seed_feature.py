"""Import a sourced IMDb editorial-page snapshot into ``home_features``.

This is an explicit build-time migration. It validates that every rendered
image is already bundled locally and changes only the selected home feature.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
from urllib.parse import urlsplit


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _official_imdb_url(value):
    parsed = urlsplit(value)
    return parsed.scheme == 'https' and parsed.hostname == 'www.imdb.com'


def _validate_media(static, relative_path, expected_sha256):
    path = PurePosixPath(relative_path)
    if path.is_absolute() or '..' in path.parts or path.parts[:2] != ('images', 'home'):
        raise ValueError('Feature media must use a local images/home path')
    absolute = Path(static).joinpath(*path.parts)
    if not absolute.is_file():
        raise ValueError('Feature media is missing: ' + relative_path)
    actual = digest(absolute.read_bytes())
    if actual != expected_sha256:
        raise ValueError('Feature media hash mismatch: ' + relative_path)


def _runtime_item(item, static):
    required = {'position', 'source_id', 'title', 'source_url', 'poster_path',
                'poster_sha256', 'release_context', 'description', 'featuring'}
    missing = sorted(required - item.keys())
    if missing:
        raise ValueError('Feature item is missing: ' + ', '.join(missing))
    if not re.fullmatch(r'tt\d+', item['source_id']):
        raise ValueError('Feature item has an invalid IMDb title ID')
    if not item['title'].strip() or not item['description'].strip():
        raise ValueError('Feature item title and description are required')
    if not _official_imdb_url(item['source_url']):
        raise ValueError('Feature item source must be an official IMDb URL')
    _validate_media(static, item['poster_path'], item['poster_sha256'])
    if item.get('backdrop_path'):
        _validate_media(static, item['backdrop_path'], item['backdrop_sha256'])
    runtime = deepcopy(item)
    for key in ('poster_sha256', 'poster_source_url', 'backdrop_sha256',
                'backdrop_source_url'):
        runtime.pop(key, None)
    return runtime


def import_snapshot(snapshot_path, database, static):
    snapshot_bytes = Path(snapshot_path).read_bytes()
    snapshot = json.loads(snapshot_bytes)
    if not _official_imdb_url(snapshot.get('source_url', '')):
        raise ValueError('Expected an official IMDb editorial source URL')
    if not re.fullmatch(r'[a-z0-9-]+', snapshot.get('feature_id', '')):
        raise ValueError('Invalid feature ID')
    if not snapshot.get('page_title', '').strip() or not snapshot.get('page_subtitle', '').strip():
        raise ValueError('Feature page title and subtitle are required')
    _validate_media(static, snapshot['hero_image_path'], snapshot['hero_image_sha256'])

    items = [_runtime_item(item, static) for item in snapshot.get('items', [])]
    if not items:
        raise ValueError('Feature snapshot has no items')
    expected_positions = list(range(1, len(items) + 1))
    if [item['position'] for item in items] != expected_positions:
        raise ValueError('Feature item positions must be contiguous and source ordered')
    ids = [item['source_id'] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError('Feature item IMDb IDs must be unique')

    database = Path(database)
    with sqlite3.connect(database) as con:
        protected = {
            name: con.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall()
            for (name,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name!='home_features'"
            )
        }
        row = con.execute(
            'SELECT kind,heading,subtitle,image_path,poster_path,source_url,captured_at,payload '
            'FROM home_features WHERE id=?', (snapshot['feature_id'],)
        ).fetchone()
        if not row or row[0] != 'editorial':
            raise ValueError('Expected an existing editorial home feature')
        payload = json.loads(row[7])
        payload.update({
            'page_title': snapshot['page_title'],
            'page_subtitle': snapshot['page_subtitle'],
            'hero_image_path': snapshot['hero_image_path'],
            'observed_at': snapshot['observed_at'],
            'item_count': len(items),
            'items': items,
        })
        updated = (
            'editorial', snapshot.get('card_title', row[1]),
            snapshot.get('card_subtitle', row[2]), row[3], row[4],
            snapshot['source_url'], snapshot['observed_at'],
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')),
        )
        if updated != row:
            con.execute(
                'UPDATE home_features SET kind=?,heading=?,subtitle=?,image_path=?,poster_path=?, '
                'source_url=?,captured_at=?,payload=? WHERE id=?',
                updated + (snapshot['feature_id'],),
            )
        for name, before in protected.items():
            after = con.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall()
            if after != before:
                raise ValueError('Protected table changed: ' + name)

    return {
        'snapshot_sha256': digest(snapshot_bytes),
        'observed_at': snapshot['observed_at'],
        'feature_id': snapshot['feature_id'],
        'items': len(items),
        'protected_tables_unchanged': sorted(protected),
        'seed_sha256': digest(database.read_bytes()),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('database', type=Path)
    parser.add_argument('static', type=Path)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    result = import_snapshot(args.snapshot, args.database, args.static)
    args.manifest.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
