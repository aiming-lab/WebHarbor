"""Build the frozen SQLite asset reproducibly; never run at HTTP request time.

Usage: python sites/gov_uk/build_seed.py [--output /path/to/gov_uk.db]
SQLAlchemy creates named indexes from sets, whose order can vary between
processes. Rebuild from a logical dump with named indexes sorted by name.
"""
import argparse
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def canonical_copy(source, target):
    with sqlite3.connect(source) as connection:
        statements = list(connection.iterdump())
    indexes = [s for s in statements if s.startswith(('CREATE INDEX ', 'CREATE UNIQUE INDEX '))]
    statements = [s for s in statements if s not in indexes and s != 'COMMIT;']
    with sqlite3.connect(target) as connection:
        connection.executescript('\n'.join(statements + sorted(indexes) + ['COMMIT;']))


def build(output):
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='govuk-seed-') as directory:
        runtime = Path(directory) / 'site'
        shutil.copytree(BASE_DIR, runtime, ignore=shutil.ignore_patterns(
            'instance', 'instance_seed', 'static', '__pycache__', 'tests', 'verify'))
        subprocess.run([sys.executable, '-c', 'import app'], cwd=runtime, check=True)
        canonical = Path(directory) / 'gov_uk.db'
        canonical_copy(runtime / 'instance/gov_uk.db', canonical)
        shutil.copy2(canonical, output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BASE_DIR/'instance_seed/gov_uk.db')
    build(parser.parse_args().output)
