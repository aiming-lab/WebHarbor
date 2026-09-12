"""Apply the sourced IMDb corrections once, before packaging the HF seed.

This is an offline asset migration, never a runtime/reset hook. It preserves
identifiers, relationships and user state. Only explicitly hashed source seeds
can be changed; a fully corrected seed is an exact byte-preserving no-op.
"""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from seed_data import _parse_release_date

BASE_DIR = Path(__file__).resolve().parent
MANIFEST = BASE_DIR / 'seed_corrections.json'
PERSON_FIELDS = ('name', 'birth_year', 'death_year', 'birth_place', 'bio',
                 'primary_profession', 'photo_path', 'known_for_json')


def _hash(value):
    encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()


def _snapshot(connection):
    """Keep row values in memory; exported reports contain only their hashes."""
    schema = connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
    tables = {}
    for (name,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        cursor = connection.execute(f'SELECT * FROM {quoted} ORDER BY rowid')
        tables[name] = {'columns': [column[0] for column in cursor.description],
                        'rows': cursor.fetchall()}
    return {'schema': schema, 'tables': tables}


def _person_values(record):
    def year(value):
        return None if value == '\\N' else int(value)
    professions = record['primaryProfession']
    known_for = record['knownForTitles']
    return dict(zip(PERSON_FIELDS, (
        record['primaryName'], year(record['birthYear']), year(record['deathYear']),
        '', '', '' if professions == '\\N' else ', '.join(
            part.replace('_', ' ').title() for part in professions.split(',')),
        '', json.dumps([] if known_for == '\\N' else known_for.split(',')))))


def _prepare_updates(connection, manifest):
    updates = []
    seen = set()
    groups = ((manifest['people'], _person_values),
              (manifest['birth_year_corrections'],
               lambda row: {'birth_year': int(row['birthYear'])}))
    for records, values_for in groups:
        for record in records:
            nm_id = record['nconst']
            if not re.fullmatch(r'nm\d+', nm_id) or nm_id in seen:
                raise ValueError('Invalid or duplicate correction identity')
            seen.add(nm_id)
            row = connection.execute('SELECT * FROM persons WHERE nm_id=?', (nm_id,))
            columns = [column[0] for column in row.description]
            original = row.fetchone()
            if original is None:
                raise ValueError(f'Correction identity missing from source seed: {nm_id}')
            current = dict(zip(columns, original))
            changes = {field: value for field, value in values_for(record).items()
                       if current[field] != value}
            if changes:
                updates.append(('persons', current['id'], nm_id, changes))
    title_years = {}
    for record in manifest.get('title_year_corrections', []):
        tt_id = record['tconst']
        if (not re.fullmatch(r'tt\d+', tt_id) or tt_id in title_years
                or type(record['before']) is not int or type(record['after']) is not int):
            raise ValueError('Invalid or duplicate title-year correction')
        title_years[tt_id] = record
    for row_id, tt_id, original, year in connection.execute('SELECT id,tt_id,release_date,year FROM titles'):
        changes = {}
        parsed = _parse_release_date(original)
        if parsed and parsed != original:
            changes['release_date'] = parsed
        correction = title_years.pop(tt_id, None)
        if correction:
            if year not in (correction['before'], correction['after']):
                raise ValueError(f'Unexpected title year for correction: {tt_id}')
            if year != correction['after']:
                changes['year'] = correction['after']
        if changes:
            updates.append(('titles', row_id, tt_id, changes))
    if title_years:
        raise ValueError('Correction title missing from source seed')
    return updates


def _verify_logical_diff(before, after, updates):
    if before['schema'] != after['schema'] or before['tables'].keys() != after['tables'].keys():
        raise ValueError('Migration changed database schema')
    expected = {(table, row_id): (key, values) for table, row_id, key, values in updates}
    changes = []
    for table, original in before['tables'].items():
        current = after['tables'][table]
        if original['columns'] != current['columns'] or len(original['rows']) != len(current['rows']):
            raise ValueError(f'Migration changed row/column structure: {table}')
        columns = original['columns']
        for old, new in zip(original['rows'], current['rows']):
            if old == new:
                continue
            row_id = old[columns.index('id')]
            key, permitted = expected.pop((table, row_id), (None, {}))
            actual = {field: value for field, previous, value in zip(columns, old, new)
                      if previous != value}
            if actual != permitted:
                raise ValueError(f'Unexpected field changes in {table} row {row_id}')
            changes.append({'table': table, 'row_id': row_id, 'key': key,
                            'fields': sorted(actual), 'before_row_sha256': _hash(old),
                            'after_row_sha256': _hash(new)})
    if expected:
        raise ValueError('Expected updates missing from logical diff')
    return changes


def migrate_seed(database, manifest_path=MANIFEST):
    database = Path(database).resolve()
    manifest = json.loads(Path(manifest_path).read_text())
    if manifest.get('schema_version') != 1:
        raise ValueError('Unsupported correction manifest schema')
    before_bytes = hashlib.sha256(database.read_bytes()).hexdigest()
    with closing(sqlite3.connect(database.as_uri() + '?mode=rw', uri=True)) as connection:
        before = _snapshot(connection)
        updates = _prepare_updates(connection, manifest)
        accepted_sources = {manifest['source_seed']['sha256']}
        accepted_sources.update(source['sha256'] for source in manifest.get('additional_source_seeds', []))
        if updates and before_bytes not in accepted_sources:
            raise ValueError('Refusing to change an unexpected source seed')
        if updates:
            try:
                connection.execute('BEGIN IMMEDIATE')
                for table, row_id, _, values in updates:
                    columns = ', '.join(f'{field}=?' for field in values)
                    connection.execute(f'UPDATE {table} SET {columns} WHERE id=?',
                                       (*values.values(), row_id))
                after = _snapshot(connection)
                changes = _verify_logical_diff(before, after, updates)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        else:
            after, changes = before, []
    return {
        'before_sha256': before_bytes,
        'after_sha256': hashlib.sha256(database.read_bytes()).hexdigest(),
        'manifest_sha256': hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest(),
        'changed_rows': dict(Counter(change['table'] for change in changes)),
        'changed_fields': dict(Counter(f"{change['table']}.{field}"
                                      for change in changes for field in change['fields'])),
        'logical_diff': changes,
        'tables': {table: {'row_count': len(snapshot['rows']),
                          'before_sha256': _hash(snapshot),
                          'after_sha256': _hash(after['tables'][table])}
                   for table, snapshot in before['tables'].items()},
        'protected_tables_unchanged': [table for table in before['tables']
                                       if table not in ('persons', 'titles')],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', nargs='?', type=Path,
                        default=BASE_DIR / 'instance_seed' / 'imdb.db')
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = migrate_seed(args.database, args.manifest)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in
                      ('before_sha256', 'after_sha256', 'changed_rows', 'changed_fields')}))


if __name__ == '__main__':
    main()
