#!/usr/bin/env python3
"""Rebuild the Compass seed from tracked, source-backed records after asset fetch.

This only replaces instance_seed/compass.db, never a live user's runtime DB.
The original asset contains generated external facts and an older schema.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile

SITE=Path(__file__).resolve().parent


def canonical_copy(source, destination):
    """Write tables and indexes in stable order, independent of ORM object hashes."""
    with sqlite3.connect(source) as original, sqlite3.connect(destination) as output:
        tables = original.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for name, ddl in tables:
            output.execute(ddl)
            quoted = '"' + name.replace('"', '""') + '"'
            rows = original.execute(f"SELECT * FROM {quoted} ORDER BY rowid")
            placeholders = ','.join('?' for _ in rows.description)
            output.executemany(f"INSERT INTO {quoted} VALUES ({placeholders})", rows)
        for (ddl,) in original.execute(
            "SELECT sql FROM sqlite_master WHERE type IN ('index','trigger','view') AND sql IS NOT NULL ORDER BY type,name"
        ):
            output.execute(ddl)
        violations = output.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValueError(f"Seed contains broken references: {violations}")


def rebuild(destination):
    destination=Path(destination).resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='compass-seed-') as directory:
        temporary=Path(directory)/'compass.db'
        env={**os.environ,'COMPASS_DATABASE_PATH':str(temporary),'COMPASS_SKIP_SEED':'0'}
        subprocess.run([sys.executable,'-c','import app'],cwd=SITE,env=env,check=True)
        # Atomic replacement prevents a failed rebuild from destroying a valid seed.
        staged=destination.with_suffix('.db.tmp')
        staged.unlink(missing_ok=True)
        canonical_copy(temporary, staged)
        staged.replace(destination)
    print(f'Compass seed rebuilt: {destination.name}')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database',nargs='?',default=str(SITE/'instance_seed/compass.db'))
    rebuild(parser.parse_args().database)
