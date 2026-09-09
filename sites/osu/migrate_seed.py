#!/usr/bin/env python3
"""Build a byte-stable OSU seed without modifying the live instance database."""
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

SITE = Path(__file__).resolve().parent


def rebuild(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="osu-seed-") as directory:
        root = Path(directory)
        for name in ("app.py", "seed_data.py", "image_sources.json"):
            shutil.copy2(SITE / name, root / name)
        subprocess.run([sys.executable, "-c", "import app"], cwd=root, check=True)
        canonical = root / "canonical.db"
        with sqlite3.connect(root / "instance/osu.db") as source, sqlite3.connect(canonical) as output:
            # SQLAlchemy stores indexes in sets; creation order may vary by process.
            for name, ddl in source.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
                output.execute(ddl)
                quoted = '"' + name.replace('"', '""') + '"'
                rows = source.execute(f"SELECT * FROM {quoted} ORDER BY rowid")
                placeholders = ','.join('?' for _ in rows.description)
                output.executemany(f"INSERT INTO {quoted} VALUES ({placeholders})", rows)
            for (ddl,) in source.execute("SELECT sql FROM sqlite_master WHERE type IN ('index','trigger','view') AND sql IS NOT NULL ORDER BY type,name"):
                output.execute(ddl)
            if output.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("OSU seed contains broken references")
        staged = destination.with_suffix(".db.tmp")
        shutil.copy2(canonical, staged)
        staged.replace(destination)
    print(f"OSU seed rebuilt: {destination.name}")


if __name__ == "__main__":
    rebuild(SITE / "instance_seed/osu.db")
