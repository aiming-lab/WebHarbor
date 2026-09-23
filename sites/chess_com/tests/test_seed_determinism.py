"""Seed determinism gate: the seed rebuild must be byte-identical.

seed_data.py materialises instance/chess_com.db and copies it to
instance_seed/chess_com.db. Re-running the build (PYTHONHASHSEED=0) must
produce the same database bytes — the property the WebHarbor reset flow
depends on (websyn_start.sh copies instance_seed -> instance at boot).

Runs the real seed_data.main() in a subprocess exactly like the Dockerfile,
hashes instance_seed/chess_com.db, and compares against the current build.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
SEED = SITE / "instance_seed" / "chess_com.db"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.skipif(not SEED.exists(), reason="seed not built yet")
def test_seed_rebuild_is_byte_identical():
    before = _sha256(SEED)
    env = dict(os.environ, PYTHONHASHSEED="0", WEBSYN_SKIP_BOOTSTRAP="1")
    result = subprocess.run(
        [sys.executable, str(SITE / "seed_data.py")],
        cwd=SITE, env=env, capture_output=True, text=True, timeout=600)
    assert result.returncode == 0, result.stderr[-800:]
    after = _sha256(SEED)
    assert before == after, (
        "seed rebuild changed bytes — determinism broken "
        f"(before={before[:16]}… after={after[:16]}…)")


@pytest.mark.skipif(not SEED.exists(), reason="seed not built yet")
def test_seed_contains_expected_row_families():
    import sqlite3
    con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    try:
        counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("users", "leaderboard_entries", "news_articles",
                            "openings", "lesson_courses", "puzzles", "clubs",
                            "master_players", "master_games", "chess_events",
                            "bots", "puzzle_attempts")}
    finally:
        con.close()
    assert counts["users"] >= 1176
    assert counts["leaderboard_entries"] == 1300
    assert counts["news_articles"] >= 160
    assert counts["puzzles"] == 625
    assert counts["openings"] >= 32
    assert counts["master_games"] >= 300
    assert counts["clubs"] == 38
    assert counts["bots"] >= 200
    assert counts["chess_events"] >= 20


@pytest.mark.skipif(not SEED.exists(), reason="seed not built yet")
def test_exactly_one_daily_puzzle_and_no_future_daily():
    import sqlite3
    con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT daily_date FROM puzzles WHERE is_daily = 1").fetchall()
    finally:
        con.close()
    assert len(rows) == 1, f"expected one daily puzzle, got {len(rows)}"
    assert rows[0][0] <= "2026-09-22", "daily puzzle must not be future-scheduled"
