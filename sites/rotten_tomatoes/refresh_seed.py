#!/usr/bin/env python3
"""Explicit offline refresh into a NEW database; the source is never modified."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from seed_data import CATALOG_PATH, catalog_rows, load_catalog, load_content_documents, CONTENT_NAMES

STATE_TABLES = ('users', 'watchlist_items', 'user_ratings')
EXTRA_COLUMNS = {'watch_offers': 'TEXT', 'watch_description': 'TEXT', 'available_at_home': 'BOOLEAN'}


@contextmanager
def sqlite_connection(*args, **kwargs):
    connection = sqlite3.connect(*args, **kwargs)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state_rows(connection, table):
    if table not in (*STATE_TABLES, 'audience_reviews'):
        raise ValueError('Not a benchmark state table')
    return connection.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()


def state_hash(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def duplicate_review_ids(connection, allowed):
    """Use the reviewed selection: review_date DESC, then id DESC, retaining latest."""
    groups = connection.execute('''SELECT movie_id, user_id, COUNT(*) FROM audience_reviews
                                   GROUP BY movie_id, user_id HAVING COUNT(*) > 1''').fetchall()
    if groups and not allowed:
        raise ValueError('Duplicate audience reviews require --deduplicate-benchmark-reviews')
    for _, user_id, _ in groups:
        owner = connection.execute('SELECT email FROM users WHERE id = ?', (user_id,)).fetchone()
        if owner != ('alice.j@test.com',):
            raise ValueError('Only the explicitly synthetic Alice review duplicates may be reconciled')
    removed = [row[0] for row in connection.execute('''
        SELECT id FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY movie_id, user_id
                ORDER BY review_date DESC, id DESC
            ) AS duplicate_rank FROM audience_reviews
        ) WHERE duplicate_rank > 1 ORDER BY id
    ''')]
    return groups, removed


def insert_rows(connection, table, rows):
    if not rows:
        return
    columns = tuple(rows[0])
    placeholders = ','.join('?' for _ in columns)
    connection.executemany(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({placeholders})',
                           [tuple(row[key] for key in columns) for row in rows])


def update_movie_facts(connection, rows):
    for row in rows:
        columns = [key for key in row if key not in ('id', 'slug')]
        result = connection.execute(
            'UPDATE movies SET ' + ','.join(f'{key} = ?' for key in columns) + ' WHERE id = ? AND slug = ?',
            [row[key] for key in columns] + [row['id'], row['slug']])
        if result.rowcount != 1:
            raise ValueError('Movie identity changed while applying catalog')


def apply_catalog(connection, catalog, deduplicate=False, allow_additions=False):
    """Run inside one transaction in an isolated copied database."""
    rows = catalog_rows(catalog)
    expected = sorted((row['id'], row['slug']) for row in rows['movies'])
    actual = connection.execute('SELECT id, slug FROM movies ORDER BY id').fetchall()
    if (actual != expected and not allow_additions) or not set(actual).issubset(expected):
        raise ValueError('Catalog must match every existing movie ID and slug exactly')
    existing_ids = {movie_id for movie_id, _ in actual}
    additions = [row for row in rows['movies'] if row['id'] not in existing_ids]
    groups, removed = duplicate_review_ids(connection, deduplicate)
    before = {table: state_rows(connection, table) for table in STATE_TABLES}
    audience_before = state_rows(connection, 'audience_reviews')
    columns = {row[1]: row[2] for row in connection.execute('PRAGMA table_info(movies)')}
    for name, column_type in EXTRA_COLUMNS.items():
        if name not in columns:
            connection.execute(f'ALTER TABLE movies ADD COLUMN {name} {column_type}')
        elif columns[name].upper() != column_type:
            raise ValueError(f'Existing {name} column has an incompatible type')

    for table in ('movie_cast', 'movie_genres', 'critic_reviews', 'persons', 'genres'):
        connection.execute(f'DELETE FROM {table}')
    update_movie_facts(connection, [row for row in rows['movies'] if row['id'] in existing_ids])
    insert_rows(connection, 'movies', additions)
    for table in ('persons', 'genres', 'movie_genres', 'movie_cast'):
        insert_rows(connection, table, rows[table])
    connection.executemany('DELETE FROM audience_reviews WHERE id = ?', [(value,) for value in removed])
    connection.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_user_movie_review ON audience_reviews(movie_id, user_id)')
    index_columns = [row[2] for row in connection.execute('PRAGMA index_info(uq_user_movie_review)')]
    index_unique = next(row[2] for row in connection.execute('PRAGMA index_list(audience_reviews)')
                        if row[1] == 'uq_user_movie_review')
    if index_columns != ['movie_id', 'user_id'] or not index_unique:
        raise ValueError('Existing audience review index has a different contract')
    after = {table: state_rows(connection, table) for table in STATE_TABLES}
    if before != after:
        raise ValueError('Benchmark user/watchlist/rating fields changed')
    expected_audience = [row for row in audience_before if row[0] not in set(removed)]
    if state_rows(connection, 'audience_reviews') != expected_audience:
        raise ValueError('Audience changes exceeded the approved duplicate removals')
    if connection.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('Foreign key check failed')
    return {'counts': {key: len(value) for key, value in rows.items()},
            'state_hashes_before': {key: state_hash(value) for key, value in before.items()},
            'state_hashes_after': {key: state_hash(value) for key, value in after.items()},
            'audience_reviews_before': len(audience_before), 'audience_reviews_after': len(expected_audience),
            'duplicate_pairs': len(groups), 'removed_review_ids': removed,
            'added_movie_ids': [row['id'] for row in additions],
            'duplicate_selection': 'review_date DESC, id DESC', 'critic_reviews_after': 0}


def migrate_copy(source, output, catalog_path=CATALOG_PATH, deduplicate=False, allow_additions=False, content_dir=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output:
        raise ValueError('Source and output must be different files')
    source_hash, catalog_hash = sha256(source), sha256(catalog_path)
    documents = load_content_documents(content_dir) if content_dir is not None else None
    content_hashes = ({name: sha256(Path(content_dir) / (name + '.json')) for name in CONTENT_NAMES}
                      if documents is not None else {})
    receipt_path = output.with_name(output.name + '.migration.json')
    pending_path = output.with_name(output.name + '.migration.pending.json')
    if output.exists():
        evidence_path = receipt_path if receipt_path.exists() else pending_path
        if not evidence_path.exists():
            raise ValueError('Refusing to overwrite an existing output without a receipt')
        receipt = json.loads(evidence_path.read_text())
        if (receipt['source_sha256'] != source_hash or receipt['catalog_sha256'] != catalog_hash
                or receipt['output_sha256'] != sha256(output)
                or receipt['deduplicate_benchmark_reviews'] != deduplicate
                or receipt.get('allow_catalog_additions', False) != allow_additions
                or receipt.get('content_sha256', {}) != content_hashes):
            raise ValueError('Existing output does not match source, catalog, and migration receipt')
        if evidence_path == pending_path:
            os.replace(pending_path, receipt_path)
        return {**receipt, 'status': 'already_migrated'}
    if receipt_path.exists():
        raise ValueError('Receipt exists without its output; inspect before retrying')
    if pending_path.exists():
        pending_path.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rotten-catalog-', dir=output.parent) as directory:
        candidate = Path(directory) / 'rotten_tomatoes.db'
        with sqlite_connection(source.as_uri() + '?mode=ro', uri=True) as original:
            with sqlite_connection(candidate) as connection:
                original.backup(connection)
                connection.execute('PRAGMA foreign_keys = ON')
                connection.execute('BEGIN IMMEDIATE')
                result = apply_catalog(connection, load_catalog(catalog_path), deduplicate, allow_additions)
                if documents is not None:
                    connection.execute('CREATE TABLE IF NOT EXISTS content_snapshots '
                                       '(name VARCHAR(32) PRIMARY KEY, document JSON NOT NULL)')
                    connection.execute('DELETE FROM content_snapshots')
                    insert_rows(connection, 'content_snapshots', [
                        {'name': name, 'document': json.dumps(document, ensure_ascii=False)}
                        for name, document in documents.items()])
                connection.commit()
                if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ValueError('SQLite integrity check failed')
        if sha256(source) != source_hash:
            raise ValueError('Source changed during migration; candidate not published')
        receipt = {'source_sha256': source_hash, 'catalog_sha256': catalog_hash,
                   'output_sha256': sha256(candidate), 'deduplicate_benchmark_reviews': deduplicate,
                   'allow_catalog_additions': allow_additions, 'content_sha256': content_hashes,
                   'status': 'migrated', **result}
        # Stage and fsync the receipt before publishing the no-overwrite output
        # link. A crash between the two final operations is recovered above.
        with pending_path.open('x') as handle:
            json.dump(receipt, handle, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.link(candidate, output)
        os.replace(pending_path, receipt_path)
        return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--catalog', type=Path, default=CATALOG_PATH)
    parser.add_argument('--deduplicate-benchmark-reviews', action='store_true')
    parser.add_argument('--allow-catalog-additions', action='store_true',
                        help='Explicitly allow new sourced movie identities while retaining every existing ID/slug')
    parser.add_argument('--content-dir', type=Path, help='Explicitly replace the three build-time content snapshots')
    args = parser.parse_args()
    print(json.dumps(migrate_copy(args.source, args.output, args.catalog,
                                 args.deduplicate_benchmark_reviews, args.allow_catalog_additions, args.content_dir), indent=2))
