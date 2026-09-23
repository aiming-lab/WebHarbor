#!/usr/bin/env python3
"""Canonicalize the freshly built seed database.

SQLAlchemy creates model indexes by iterating a set of index objects, whose
order depends on object identity (memory addresses). The index creation
order changes the sqlite_master row order and therefore the on-disk page
layout between builds. This script rebuilds the database with DDL executed
in a fixed order (tables and indexes alphabetically) and rows copied in
rowid order, so identical source data always produces identical bytes.
"""
from __future__ import annotations

import pathlib
import sqlite3
import sys

SITE = pathlib.Path(__file__).resolve().parent
DB_PATH = SITE / "instance" / "better_business_bureau.db"


def canonicalize(path: pathlib.Path) -> None:
    src = sqlite3.connect(path)
    src.row_factory = None
    tables, indexes = [], []
    for name, sql in src.execute(
            "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL"):
        if sql.lstrip().upper().startswith("CREATE TABLE"):
            tables.append(sql)
        elif sql.lstrip().upper().startswith("CREATE INDEX"):
            indexes.append(sql)
    tables.sort(key=str.lower)
    indexes.sort(key=str.lower)

    tmp_path = path.with_suffix(".canonical.db")
    if tmp_path.exists():
        tmp_path.unlink()
    dst = sqlite3.connect(tmp_path)
    for ddl in tables + indexes:
        dst.execute(ddl)
    for (table,) in src.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        cols = [r[1] for r in src.execute(f"PRAGMA table_info({table})")]
        placeholders = ",".join("?" * len(cols))
        rows = src.execute(f"SELECT {','.join(cols)} FROM {table} ORDER BY rowid").fetchall()
        dst.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
    dst.commit()
    dst.close()
    src.close()
    path.unlink()
    tmp_path.rename(path)


if __name__ == "__main__":
    if not DB_PATH.exists():
        print(f"[canonicalize] missing {DB_PATH}", file=sys.stderr)
        sys.exit(1)
    canonicalize(DB_PATH)
    print(f"[canonicalize] {DB_PATH} rebuilt in canonical DDL/row order")
