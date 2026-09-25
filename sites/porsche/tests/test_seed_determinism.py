"""Seed determinism checks for the porsche mirror.

The shipped seed (instance_seed/porsche.db) must exist, validate as
SQLite, and match the catalog snapshot sizes; the seeder itself must be
idempotent (a re-import against a fresh copy leaves the DB
byte-identical) so /reset stays byte-identical.
"""
import hashlib
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent
SEED = SITE / "instance_seed" / "porsche.db"
SOURCE = SITE / "source_data"


def test_seed_exists_and_valid():
    if not SEED.exists():
        pytest.skip("instance_seed/porsche.db not built yet")
    conn = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("model_variants", "configurator_options", "vehicles",
                  "dealers", "shop_products", "users", "site_content"):
            assert t in tables, f"table {t} missing"
        assert conn.execute("SELECT COUNT(*) FROM model_variants").fetchone()[0] == 76
        assert conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] >= 400
        assert conn.execute("SELECT COUNT(*) FROM dealers").fetchone()[0] == 218
        assert conn.execute("SELECT COUNT(*) FROM shop_products").fetchone()[0] >= 180
    finally:
        conn.close()


def test_seed_matches_source_snapshot():
    if not SEED.exists():
        pytest.skip("seed not built yet")
    models = json.loads((SOURCE / "models.json").read_text())
    vehicles = json.loads((SOURCE / "vehicles.json").read_text())
    dealers = json.loads((SOURCE / "dealers.json").read_text())
    products = json.loads((SOURCE / "shop_products.json").read_text())
    conn = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    try:
        assert conn.execute("SELECT COUNT(*) FROM model_variants").fetchone()[0] == len(models)
        assert conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == len(vehicles)
        assert conn.execute("SELECT COUNT(*) FROM dealers").fetchone()[0] == len(dealers)
        assert conn.execute("SELECT COUNT(*) FROM shop_products").fetchone()[0] == len(products)
    finally:
        conn.close()


def test_seeder_is_idempotent(tmp_path):
    if not SEED.exists():
        pytest.skip("seed not built yet")
    digest_seed = hashlib.sha256(SEED.read_bytes()).hexdigest()
    # fresh boot against a byte-copy of the seed in a scratch checkout
    scratch = tmp_path / "site"
    shutil.copytree(SITE, scratch, ignore=shutil.ignore_patterns(
        "instance", "scraped_data", "__pycache__", ".pytest_cache"))
    (scratch / "instance").mkdir(exist_ok=True)
    shutil.copyfile(SEED, scratch / "instance" / "porsche.db")
    env = {"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0",
           "WEBHARBOR_MIRROR_DB": str(scratch / "instance" / "porsche.db")}
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "from app import app, db\n"
        "from app import seed_database, seed_benchmark_users\n"
        "with app.app_context():\n"
        "    db.create_all()\n"
        "    seed_database()\n"
        "    seed_benchmark_users()\n" % str(scratch)
    )
    subprocess.run([sys.executable, "-c", code], check=True, env=env,
                   capture_output=True)
    after = hashlib.sha256((scratch / "instance" / "porsche.db").read_bytes()).hexdigest()
    assert after == digest_seed, "re-import against the seed mutated the DB"


def test_seed_rebuild_is_byte_reproducible(tmp_path):
    if not SEED.exists():
        pytest.skip("seed not built yet")
    if not (SOURCE / "models.json").exists():
        pytest.skip("source snapshot not present")
    scratch = tmp_path / "site"
    shutil.copytree(SITE, scratch, ignore=shutil.ignore_patterns(
        "instance", "instance_seed", "scraped_data", "__pycache__", ".pytest_cache"))
    (scratch / "instance").mkdir(exist_ok=True)
    env = {"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0",
           "WEBHARBOR_MIRROR_DB": str(scratch / "instance" / "porsche.db")}
    # the real build path: seed_data.py __main__ (canonicalizes the file)
    subprocess.run([sys.executable, str(scratch / "seed_data.py")],
                   check=True, env=env, capture_output=True, cwd=str(scratch))
    rebuilt = hashlib.sha256((scratch / "instance_seed" / "porsche.db").read_bytes()).hexdigest()
    shipped = hashlib.sha256(SEED.read_bytes()).hexdigest()
    assert rebuilt == shipped, "seed rebuild is not byte-reproducible"
