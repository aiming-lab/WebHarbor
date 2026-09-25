#!/usr/bin/env python3
"""Validate every site's single runtime SQLite seed database."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def validate_database(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("missing or empty database")
    uri = f"file:{path.resolve()}?mode=ro"
    connection = None
    try:
        connection = sqlite3.connect(uri, uri=True)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise ValueError(f"integrity_check={integrity!r}")
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise ValueError(f"foreign_key_check={foreign_keys[:3]!r}")
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        if not tables:
            raise ValueError("database has no application tables")
    except sqlite3.DatabaseError as error:
        raise ValueError(f"invalid SQLite database: {error}") from error
    finally:
        if connection is not None:
            connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sites", type=Path)
    parser.add_argument("--allow-build-generated", action="store_true")
    args = parser.parse_args()
    failures = []
    checked = 0
    skipped = 0
    for site_dir in sorted(path for path in args.sites.iterdir() if path.is_dir() and not path.name.startswith(".")):
        if args.allow_build_generated and (site_dir / ".build-generated-seed").is_file():
            skipped += 1
            continue
        seed_dir = site_dir / "instance_seed"
        entries = sorted(seed_dir.iterdir()) if seed_dir.is_dir() else []
        invalid_entries = [entry.name for entry in entries if entry.is_symlink() or not entry.is_file() or entry.suffix != ".db"]
        if invalid_entries:
            failures.append(f"{seed_dir}: unexpected seed entries {invalid_entries}")
            continue
        databases = [entry for entry in entries if entry.suffix == ".db"]
        if len(databases) != 1:
            failures.append(f"{seed_dir}: expected exactly one *.db seed, found {[path.name for path in databases]}")
            continue
        database = databases[0]
        try:
            validate_database(database)
            checked += 1
        except (OSError, sqlite3.DatabaseError, ValueError) as error:
            failures.append(f"{database}: {type(error).__name__}: {error}")
    if failures:
        raise SystemExit("seed validation failed:\n" + "\n".join(failures))
    print(f"[check] validated {checked} SQLite seed databases; skipped {skipped} build-generated sites")


if __name__ == "__main__":
    main()
