"""Seed determinism checks for the imgur mirror.

The seed must be (a) idempotent — a second run against the populated DB is a
no-op, and (b) complete — the seeded row counts match the tracked
source_data.json snapshot.
"""
import json
import pathlib
import sqlite3

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent
SOURCE = SITE / "source_data.json"
SEED = SITE / "instance_seed" / "imgur.db"


def test_seed_exists_and_matches_source_counts():
    if not SEED.exists():
        pytest.skip("instance_seed/imgur.db not built yet")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    conn = sqlite3.connect(SEED)
    counts = {
        "posts": conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
        "comments": conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "tags": conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0],
        "media": conn.execute("SELECT COUNT(*) FROM media").fetchone()[0],
        "trophies": conn.execute("SELECT COUNT(*) FROM trophies").fetchone()[0],
    }
    conn.close()
    assert counts["posts"] == len(source["posts"]) + 0
    assert counts["comments"] == len(source["comments"]) + sum(
        len(u["comments"]) for u in source["benchmark_state"])
    assert counts["users"] == len(source["users"]) + len(source["benchmark_users"])
    assert counts["tags"] == len(source["tags"])
    assert counts["media"] == sum(len(p["media"]) for p in source["posts"])
    assert counts["trophies"] == len(source["trophies"])
    assert counts["posts"] >= 200
    assert counts["comments"] >= 1000


def test_seed_is_idempotent(app):
    with app.app_context():
        import seed_data
        from app import Post
        before = Post.query.count()
        # second invocation must early-return without touching the DB
        seed_data.seed_database()
        after = Post.query.count()
    assert before == after


def test_reference_date_is_frozen():
    import sys
    if str(SITE) not in sys.path:
        sys.path.insert(0, str(SITE))
    from app import MIRROR_REFERENCE_DATE
    assert MIRROR_REFERENCE_DATE.year == 2026
    assert MIRROR_REFERENCE_DATE.month == 9
    assert MIRROR_REFERENCE_DATE.day == 22


def test_benchmark_users_exist_with_state():
    if not SEED.exists():
        pytest.skip("instance_seed/imgur.db not built yet")
    conn = sqlite3.connect(SEED)
    users = dict(conn.execute(
        "SELECT username, id FROM users WHERE is_benchmark = 1").fetchall())
    conn.close()
    assert set(users) == {"alice_j", "bob_c", "carol_d", "david_k"}
    for username, uid in users.items():
        assert uid >= 990000001
