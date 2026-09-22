"""Correct media attribution in the downloaded seed without rewriting its archive."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def migrate(path: Path) -> int:
    if not path.is_file():
        raise FileNotFoundError(path)
    with sqlite3.connect(path) as db:
        # Only the original curated fixture rows; never strip user-selected media.
        rows = db.execute("SELECT id FROM post WHERE id BETWEEN 11 AND 80 "
                          "AND source_id LIKE 'seed%' AND (image != '' OR post_type != 'Text')").fetchall()
        if not rows:
            return 0
        db.executemany("UPDATE post SET image = '', post_type = 'Text' WHERE id = ?", rows)
    return len(rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', nargs='?', type=Path,
                        default=Path(__file__).resolve().parent / 'instance_seed' / '9gag.db')
    args = parser.parse_args()
    print(f'9GAG: corrected {migrate(args.database)} curated text posts')
