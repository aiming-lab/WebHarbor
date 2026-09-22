"""Upgrade the pinned seed without attributing anonymous reviews by display name.

Run during asset fetch/build, not request handling. Repeated runs are byte no-ops.
"""
import argparse
import sqlite3
from pathlib import Path


def migrate(path):
    path = Path(path).resolve()
    with sqlite3.connect(f"{path.as_uri()}?mode=rw", uri=True) as con:
        columns = {row[1] for row in con.execute('PRAGMA table_info(review)')}
        if not columns:
            raise ValueError('Expected Recreation.gov review table')
        if 'user_id' in columns:
            return False
        con.execute('ALTER TABLE review ADD COLUMN user_id INTEGER REFERENCES user(id)')
        con.commit()
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', nargs='?', type=Path,
                        default=Path(__file__).resolve().parent / 'instance_seed/recreation_gov.db')
    args = parser.parse_args()
    print('Migrated' if migrate(args.database) else 'Already current', args.database)
