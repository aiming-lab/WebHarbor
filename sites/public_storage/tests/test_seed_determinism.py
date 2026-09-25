"""Seed determinism checks for the public_storage mirror.

The shipped seed (instance_seed/public_storage.db) must exist, validate
as SQLite, and match the catalog snapshot; the seeder must be idempotent
(a re-boot against a fresh copy of the seed leaves the DB byte-identical)
so /reset stays byte-identical.
"""
import hashlib
import pathlib
import shutil
import sqlite3
import os
import subprocess
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent
SEED = SITE / "instance_seed" / "public_storage.db"
SOURCE = SITE / "source_data"


def test_seed_exists_and_valid():
    if not SEED.exists():
        pytest.skip("instance_seed/public_storage.db not built yet")
    conn = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for expected in ("facilities", "units", "reviews", "users",
                          "reservations", "rentals", "zip_results",
                          "blog_articles", "size_faqs", "site_copy"):
            assert expected in tables
    finally:
        conn.close()


def test_seed_matches_source_snapshot():
    if not SEED.exists():
        pytest.skip("instance_seed/public_storage.db not built yet")
    import json
    facilities = json.loads((SOURCE / "facilities.json").read_text())
    n_units = sum(len(f["units"]) for f in facilities.values())
    n_reviews = sum(len(f["reviews"]) for f in facilities.values())
    zips = json.loads((SOURCE / "zip_searches.json").read_text())
    n_zip_rows = sum(len(v["results"]) for v in zips.values())

    conn = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    try:
        assert conn.execute("SELECT COUNT(*) FROM facilities").fetchone()[0] == len(facilities)
        assert conn.execute("SELECT COUNT(*) FROM units").fetchone()[0] == n_units
        assert conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == n_reviews
        assert conn.execute("SELECT COUNT(*) FROM zip_results").fetchone()[0] == n_zip_rows
    finally:
        conn.close()


def test_seeder_is_idempotent(tmp_path):
    """A second build against a fresh copy of the seed is byte-identical."""
    if not SEED.exists():
        pytest.skip("instance_seed/public_storage.db not built yet")
    scratch = tmp_path / "public_storage.db"
    shutil.copyfile(SEED, scratch)
    before = hashlib.md5(scratch.read_bytes()).hexdigest()

    env = dict(os.environ)
    env["WEBHARBOR_MIRROR_DB"] = str(scratch)
    env["PYTHONHASHSEED"] = "0"
    result = subprocess.run(
        [sys.executable, "-c",
         "import app\n"
         "with app.app.app_context():\n"
         "    app.seed_database()\n"
         "    app.seed_benchmark_users()"],
        cwd=str(SITE), env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-800:]
    after = hashlib.md5(scratch.read_bytes()).hexdigest()
    assert before == after, "re-seeding over a populated DB must be a no-op"


def test_fresh_build_is_byte_reproducible(tmp_path):
    """Two fresh builds from the tracked source snapshot are identical."""
    digests = []
    for i in range(2):
        work = tmp_path / f"build{i}"
        shutil.copytree(SITE, work, ignore=shutil.ignore_patterns(
            "instance", "instance_seed", "__pycache__"))
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = "0"
        env.pop("WEBHARBOR_MIRROR_DB", None)
        result = subprocess.run(
            [sys.executable, "seed_data.py"],
            cwd=str(work), env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr[-800:]
        digests.append(hashlib.md5(
            (work / "instance_seed" / "public_storage.db").read_bytes()).hexdigest())
    assert digests[0] == digests[1]
