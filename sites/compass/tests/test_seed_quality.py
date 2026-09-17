"""Current generated-seed integrity and task-grounding tests."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
VERIFY = SITE / "verify"
sys.path.insert(0, str(VERIFY))
import verify_lib as v
from test_support import ensure_seed


def test_seed_generation_is_byte_deterministic(tmp_path):
    hashes = []
    for name in ("a.db", "b.db"):
        output = tmp_path / name
        subprocess.run([sys.executable, str(SITE / "migrate_seed.py"), str(output)],
                       cwd=SITE, check=True, capture_output=True, text=True,
                       env={**__import__('os').environ, 'PYTHONHASHSEED': '0'})
        hashes.append(hashlib.sha256(output.read_bytes()).hexdigest())
    assert hashes[0] == hashes[1]


def test_current_seed_counts_foreign_keys_and_marker():
    seed = ensure_seed()
    expected = {
        "agents": 255, "cities": 11, "collections": 4, "inquiries": 0,
        "listings": 505, "neighborhood_guides": 24, "saved_homes": 12,
        "saved_searches": 4, "seed_metadata": 1, "seller_inquiries": 0,
        "tours": 7, "users": 4,
    }
    with sqlite3.connect(seed) as connection:
        assert {table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                for table in expected} == expected
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT version FROM seed_metadata WHERE id=1").fetchone() == ("compass-source-v3",)
        assert connection.execute("SELECT count(*) FROM listings WHERE is_open_house=1").fetchone() == (19,)


def test_refreshed_source_prices_missing_from_cards_are_retained_at_stable_appended_ids():
    raw = json.loads((SITE / "listings_clean.json").read_text())
    source = json.loads((SITE / "source_data.json").read_text())["listings"]
    recovered = {row["listing_id"] for row in raw if not row.get("price") and source.get(row["listing_id"], {}).get("price")}
    assert len(recovered) == 8
    with sqlite3.connect(ensure_seed()) as connection:
        actual = {row[0] for row in connection.execute("SELECT listing_id_sha FROM listings WHERE id>497")}
    assert actual == recovered


def test_every_task_target_is_unique_and_derived_from_current_seed():
    snapshot = v.snapshot(ensure_seed())
    for task in (0, 1, 3, 4, 6, 11, 12, 13, 14, 15, 16, 17):
        target = v.task_target(task, snapshot)
        assert target["id"] in snapshot["listings"]
        assert target["address"] and target["slug"]
    carol = v.user_id(snapshot, "carol.lee@test.com")
    eligible = [tour for tour in snapshot["tours"].values() if tour["user_id"] == carol and tour["status"] != "cancelled"]
    assert len(eligible) >= 2
    assert len({tour["requested_date"] for tour in eligible}) == len(eligible)
    bob = v.user_id(snapshot, "bob.smith@test.com")
    collection = [row for row in snapshot["collections"].values() if row["user_id"] == bob and row["name"] == "Bob — NY shortlist"]
    assert len(collection) == 1 and len(json.loads(collection[0]["listing_ids_json"])) == 3


def test_partial_unversioned_seed_fails_closed(tmp_path):
    database = tmp_path / "partial.db"
    script = f"""
import os
os.environ['COMPASS_DATABASE_PATH']={str(database)!r}
os.environ['COMPASS_SKIP_SEED']='1'
import app
with app.app.app_context():
    app.db.create_all()
    app.db.session.add(app.User(email='partial@example.com',name='Partial',password_hash='x'))
    app.db.session.commit()
    try:
        app.seed_all()
    except RuntimeError:
        raise SystemExit(0)
    raise SystemExit(1)
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=SITE,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
