"""Seed-quality gates for the WebMD Doctor mirror.

Run with the repository venv (needs Flask/SQLAlchemy for the app import used by
the deterministic-rebuild test). The frozen seed at ``instance_seed/`` is built
on demand when missing, mirroring ``verify/tests/_support.py``.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
SEED = SITE / "instance_seed" / "webmd_doctor.db"


def _ensure_seed() -> None:
    if SEED.exists():
        return
    proc = subprocess.run([sys.executable, str(SITE / "seed_data.py")], cwd=SITE,
                          env={**os.environ, "PYTHONHASHSEED": "0"},
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, (
        f"seed build failed rc={proc.returncode}\nstdout: {proc.stdout[-2000:]}\nstderr: {proc.stderr[-2000:]}")


def _query(sql: str, params: tuple = ()) -> list:
    _ensure_seed()
    connection = sqlite3.connect(SEED)
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def _luhn_valid(npi: str) -> bool:
    digits = [int(c) for c in "80840" + npi]
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def test_seed_schema_version_counts_and_foreign_keys():
    sys.path.insert(0, str(SITE))
    try:
        import seed_data
    finally:
        sys.path.pop(0)
    tables = {row[0] for row in _query(
        "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert "seed_metadata" in tables
    assert _query("SELECT value FROM seed_metadata WHERE key='version'") == [("webmd-doctor-v1",)]
    for table, expected in seed_data.EXPECTED_COUNTS.items():
        actual = _query(f"SELECT COUNT(*) FROM {table}")[0][0]
        assert actual == expected, f"{table}: expected {expected}, got {actual}"
    assert _query("PRAGMA foreign_key_check") == []


def test_every_npi_is_checksum_valid_unique_and_synthetic_range():
    npis = [row[0] for row in _query("SELECT npi FROM doctors")]
    assert len(npis) == 226
    assert len(set(npis)) == 226, "duplicate NPIs in seed"
    for npi in npis:
        assert npi.isdigit() and len(npi) == 10 and npi[0] == "1", f"malformed NPI {npi!r}"
        assert _luhn_valid(npi), f"NPI {npi} fails the CMS Luhn check digit"
    # The registry-verified list embedded in seed_data.py must agree with the DB.
    sys.path.insert(0, str(SITE))
    try:
        import seed_data
    finally:
        sys.path.pop(0)
    assert set(npis) == set(seed_data.VERIFIED_NPIS), "seed NPIs drifted from VERIFIED_NPIS"


def test_saved_provider_breadth_for_task_8():
    # Task 8 needs Alice to hold at least six saved providers with exactly one
    # dermatologist so the removal target is unambiguous.
    rows = _query(
        "SELECT sp.doctor_id, d.primary_specialty_id, s.name "
        "FROM saved_providers sp JOIN doctors d ON d.id = sp.doctor_id "
        "JOIN specialties s ON s.id = d.primary_specialty_id "
        "JOIN users u ON u.id = sp.user_id WHERE u.email = 'alice.j@test.com'")
    assert len(rows) >= 6, f"alice has {len(rows)} saved providers, need >= 6"
    derm = [row for row in rows if row[2] == "Dermatology"]
    assert len(derm) == 1, f"alice must hold exactly one dermatologist, got {len(derm)}"
    total = _query("SELECT COUNT(*) FROM saved_providers")[0][0]
    assert total == 7, f"seeded saved_providers total changed: {total}"


def test_seed_rebuild_is_deterministic():
    environment = {**os.environ, "PYTHONHASHSEED": "0"}
    hashes = []
    for _ in range(2):
        proc = subprocess.run([sys.executable, str(SITE / "seed_data.py")], cwd=SITE,
                              env=environment, capture_output=True, text=True, timeout=600)
        assert proc.returncode == 0, (
            f"seed rebuild failed rc={proc.returncode}\nstdout: {proc.stdout[-2000:]}\nstderr: {proc.stderr[-2000:]}")
        hashes.append(hashlib.sha256(SEED.read_bytes()).hexdigest())
    assert len(set(hashes)) == 1, f"non-deterministic seed builds: {hashes}"
