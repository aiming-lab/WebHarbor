"""Generate the deterministic seed from tracked definitions and pinned media."""
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent

def main():
    with tempfile.TemporaryDirectory(prefix='webharbor-seed-') as directory:
        db = Path(directory) / (ROOT.name + '.db')
        env = dict(os.environ, WEBSYN_DB_PATH=str(db), PYTHONHASHSEED='0')
        subprocess.run([sys.executable, '-c', 'import app'], cwd=ROOT, env=env, check=True)
        # SQLAlchemy's index set can emit DDL in different orders between processes.
        # Rebuild the SQLite file in a stable table/index order before publication.
        canonical = Path(directory) / 'canonical.db'
        with sqlite3.connect(db) as source, sqlite3.connect(canonical) as dest:
            schema = source.execute("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name").fetchall()
            for kind, name, sql in schema:
                dest.execute(sql)
                if kind == 'table':
                    rows = source.execute(f'SELECT * FROM "{name}" ORDER BY id').fetchall()
                    if rows:
                        placeholders = ','.join('?' for _ in rows[0])
                        dest.executemany(f'INSERT INTO "{name}" VALUES ({placeholders})', rows)
            dest.commit()
            dest.execute('VACUUM')
        db = canonical
        target = ROOT / 'instance_seed'
        if target.exists():
            shutil.rmtree(target)
        target.mkdir()
        shutil.copyfile(db, target / (ROOT.name + '.db'))

if __name__ == '__main__':
    main()
