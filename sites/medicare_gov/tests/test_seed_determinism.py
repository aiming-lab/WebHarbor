"""Seed reproducibility and byte-identity checks for the medicare_gov mirror.

Two fresh seeds built from the tracked source snapshot (PYTHONHASHSEED=0)
must produce byte-identical SQLite files, and a second boot over an already
populated database must not touch it — the two halves of the
`/reset/medicare_gov` byte-identity invariant.
"""
import hashlib
import os
import pathlib
import shutil
import subprocess
import sys

SITE = pathlib.Path(__file__).resolve().parent.parent


def _md5(path: pathlib.Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _boot(db_path: pathlib.Path) -> None:
    env = dict(os.environ)
    env["MEDICARE_GOV_DB_PATH"] = f"sqlite:///{db_path}"
    env["PYTHONHASHSEED"] = "0"
    subprocess.run(
        [sys.executable, "-c", "from app import app"],
        cwd=SITE, env=env, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_fresh_seed_is_byte_reproducible(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    _boot(a)
    _boot(b)
    assert _md5(a) == _md5(b), "two fresh seeds differ"


def test_second_boot_is_a_noop(tmp_path):
    db = tmp_path / "medicare_gov.db"
    _boot(db)
    first = _md5(db)
    _boot(db)
    assert _md5(db) == first, "second boot mutated the database"


def test_seeded_counts():
    from app import (CoverageItem, CoverageTopic, DmeSupplier, Publication,
                     Plan, Provider, User)
    from app import app
    with app.app_context():
        assert CoverageItem.query.count() == 165
        assert CoverageTopic.query.count() == 6
        assert Provider.query.count() >= 3000
        assert DmeSupplier.query.count() >= 450
        assert Publication.query.count() == 84
        assert Plan.query.count() >= 50
        assert User.query.filter_by(is_benchmark=True).count() == 4
