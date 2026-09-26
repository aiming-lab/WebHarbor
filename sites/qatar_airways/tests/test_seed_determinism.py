"""Seed determinism checks for the qatar_airways mirror.

The shipped seed (instance_seed/qatar_airways.db) must exist, validate as
SQLite, and match the catalog snapshot sizes; the seeder itself must be
idempotent (a re-boot against a fresh copy of the seed leaves the DB
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
SEED = SITE / "instance_seed" / "qatar_airways.db"
SOURCE = SITE / "source_data"


def test_seed_exists_and_valid():
    if not SEED.exists():
        pytest.skip("instance_seed/qatar_airways.db not built yet")
    conn = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("airports", "destinations", "flights", "flight_statuses",
                  "aircraft", "offers", "faqs", "users", "bookings",
                  "booking_legs", "passengers", "activities"):
            assert t in tables, f"table {t} missing"
        assert conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0] == 500
        assert conn.execute("SELECT COUNT(*) FROM destinations").fetchone()[0] == 253
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 4
    finally:
        conn.close()


def test_seed_matches_source_snapshot():
    if not SEED.exists():
        pytest.skip("seed not built yet")
    catalog = json.loads((SOURCE / "flight_catalog_2026-09-24.json").read_text())
    cards = json.loads((SOURCE / "destination_cards.json").read_text())
    conn = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    try:
        assert conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0] == len(catalog)
        assert conn.execute("SELECT COUNT(*) FROM destinations").fetchone()[0] == len(cards)
    finally:
        conn.close()


def test_seeder_is_idempotent(tmp_path):
    if not SEED.exists():
        pytest.skip("seed not built yet")
    digest_seed = hashlib.sha256(SEED.read_bytes()).hexdigest()
    # fresh boot against a byte-copy of the seed in a scratch checkout
    scratch = tmp_path / "site"
    shutil.copytree(SITE, scratch,
                    ignore=shutil.ignore_patterns("instance", "__pycache__",
                                                  ".pytest_cache", "scraped_data",
                                                  "static", "source_data",
                                                  "scripts_dev", "verify", "tests"))
    (scratch / "instance").mkdir()
    shutil.copyfile(SEED, scratch / "instance" / "qatar_airways.db")
    code = (
        "import app  # bootstrap runs; seeds must early-return\n"
        "import hashlib\n"
        "print(hashlib.sha256(open('instance/qatar_airways.db','rb').read()).hexdigest())\n"
    )
    env = {"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0",
           "HOME": str(tmp_path)}
    result = subprocess.run([sys.executable, "-c", code], cwd=scratch,
                            capture_output=True, text=True, env=env,
                            timeout=300)
    assert result.returncode == 0, result.stderr[-800:]
    digest_after = result.stdout.strip().splitlines()[-1]
    assert digest_after == digest_seed, (
        "re-boot mutated the seed copy — a seed function is not gated")
