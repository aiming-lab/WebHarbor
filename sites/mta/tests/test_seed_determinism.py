"""Seed reproducibility and byte-identity checks for the mta mirror.

Two fresh seeds built from the tracked source snapshot (PYTHONHASHSEED=0)
must produce byte-identical SQLite files, and a second boot over an already
populated database must not touch it — the two halves of the
`/reset/mta` byte-identity invariant.

The full mta seed takes ~20 seconds per build (1.55M stop-time rows), so the
fresh-seed reproducibility check is marked slow and skipped unless the
MTA_SLOW_TESTS environment variable is set; the no-op boot check runs
against the already-built instance_seed and is always executed.
"""
import hashlib
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent
SEED = SITE / "instance_seed" / "mta.db"


def _md5(path: pathlib.Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _boot(db_path: pathlib.Path) -> None:
    env = dict(os.environ)
    env["MTA_DB_PATH"] = f"sqlite:///{db_path}"
    env["PYTHONHASHSEED"] = "0"
    subprocess.run(
        [sys.executable, "-c", "from app import app"],
        cwd=SITE, env=env, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_seed_exists_and_is_populated():
    if not SEED.exists():
        pytest.skip("instance_seed/mta.db not built yet")
    import sqlite3
    con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    try:
        counts = dict(con.execute(
            "SELECT 'stations', COUNT(*) FROM stations "
            "UNION ALL SELECT 'trips', COUNT(*) FROM trips "
            "UNION ALL SELECT 'stop_times', COUNT(*) FROM stop_times "
            "UNION ALL SELECT 'users', COUNT(*) FROM users").fetchall())
        assert counts["stations"] >= 700
        assert counts["trips"] >= 80000
        assert counts["stop_times"] >= 1000000
        assert counts["users"] == 4
    finally:
        con.close()


def test_second_boot_is_a_noop(tmp_path):
    if not SEED.exists():
        pytest.skip("instance_seed/mta.db not built yet")
    db = tmp_path / "mta.db"
    shutil.copyfile(SEED, db)
    _boot(db)                       # boot over a populated DB
    first = _md5(db)
    _boot(db)                       # boot again
    assert _md5(db) == first, "second boot mutated the database"


@pytest.mark.skipif(not os.environ.get("MTA_SLOW_TESTS"),
                    reason="full seed build takes ~20s; set MTA_SLOW_TESTS=1")
def test_fresh_seed_is_byte_reproducible(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    _boot(a)
    _boot(b)
    assert _md5(a) == _md5(b), "two fresh seeds differ"
    if SEED.exists():
        assert _md5(a) == _md5(SEED), \
            "freshly built seed differs from the shipped instance_seed"
