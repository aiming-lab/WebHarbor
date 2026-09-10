from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
SEED = SITE / "instance_seed" / "walmart_careers.db"


def query(sql, params=()):
    connection = sqlite3.connect(SEED)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(sql, params)]
    finally:
        connection.close()


def test_seed_schema_counts_marker_and_foreign_keys():
    connection = sqlite3.connect(SEED)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        assert tables == {"application_drafts", "applications", "areas", "categories", "jobs", "saved_jobs", "seed_metadata", "stores", "users"}
        assert connection.execute("SELECT value FROM seed_metadata WHERE key='version'").fetchone() == ("walmart-careers-v2",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        expected = {"areas": 7, "categories": 33, "stores": 51, "jobs": 246, "users": 4, "saved_jobs": 13, "applications": 4, "application_drafts": 0}
        assert {table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in expected} == expected
    finally:
        connection.close()


def test_catalog_cross_field_invariants():
    rows = query(
        "SELECT j.*, a.slug area_slug, c.area_id category_area_id, s.state, s.lat, s.lng "
        "FROM jobs j JOIN areas a ON a.id=j.area_id JOIN categories c ON c.id=j.category_id JOIN stores s ON s.id=j.store_id"
    )
    assert len({row["job_id"] for row in rows}) == 246
    assert all(row["category_area_id"] == row["area_id"] for row in rows)
    assert all(row["population"] in {"hourly", "salaried"} for row in rows)
    assert all((row["population"] == "hourly") == (row["pay_frequency"] == "Hourly") for row in rows)
    assert all(float(row["min_pay"]) <= float(row["max_pay"]) for row in rows)
    assert all(-90 <= row["lat"] <= 90 and -180 <= row["lng"] <= 180 for row in rows)
    assert all((row["positions_available"] is not None) == (row["population"] == "hourly") for row in rows)
    assert all((row["worker_type"] is not None) == (row["population"] == "salaried") for row in rows)
    assert all((row["employment_type"] == "Intern") <= (row["area_slug"] == "students") for row in rows)
    distributions = {
        "population": Counter(row["population"] for row in rows),
        "brand": Counter(row["brand"] for row in rows),
    }
    assert distributions["population"] == {"hourly": 168, "salaried": 78}
    assert distributions["brand"] == {"Walmart": 184, "Sam's Club": 42, "Vizio": 20}
    shift_counts = Counter(shift for row in rows for shift in json.loads(row["shifts_json"]))
    assert len(shift_counts) == 7 and min(shift_counts.values()) >= 25


def test_seed_rebuild_is_byte_identical_across_process_hash_seeds(tmp_path):
    hashes = []
    for hash_seed in ("0", "1", "0"):
        environment = {**os.environ, "PYTHONHASHSEED": hash_seed, "WEBSYN_SKIP_BOOTSTRAP": "1"}
        subprocess.run([sys.executable, str(SITE / "seed_data.py")], cwd=SITE, env=environment, check=True, capture_output=True, text=True)
        hashes.append(hashlib.sha256(SEED.read_bytes()).hexdigest())
    assert len(set(hashes)) == 1


def test_partial_or_unversioned_database_fails_closed(tmp_path):
    script = f"""
import os, shutil, sys
sys.path.insert(0, {str(SITE)!r})
os.environ['WEBSYN_SKIP_BOOTSTRAP']='1'
import app
from seed_data import ensure_seed_database
with app.app.app_context():
    app.db.drop_all(); app.db.create_all()
    app.db.session.add(app.Area(slug='partial', name='Partial', display_order=0))
    app.db.session.commit()
    try:
        ensure_seed_database()
    except RuntimeError as exc:
        assert 'partial' in str(exc)
    else:
        raise AssertionError('partial database was accepted')
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env={**os.environ, "WEBSYN_SKIP_BOOTSTRAP": "1"}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    subprocess.run([sys.executable, str(SITE / "seed_data.py")], cwd=SITE, env={**os.environ, "PYTHONHASHSEED": "0"}, check=True, capture_output=True)
