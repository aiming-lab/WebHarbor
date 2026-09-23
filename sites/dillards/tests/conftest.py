"""Shared test fixtures: every test starts from a byte-identical seed copy."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))
os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"

import app as site  # noqa: E402
import seed_data  # noqa: E402

SEED = SITE / "instance_seed" / "dillards.db"

if not SEED.exists():
    seed_data.build_seed_database()


@pytest.fixture(autouse=True)
def clean_database(tmp_path, monkeypatch):
    # SQLAlchemy caches its engine at initialization; changing only the config
    # URI would still send test writes to the running preview's database.
    database = tmp_path / "dillards.db"
    shutil.copy2(SEED, database)
    engine = create_engine(f"sqlite:///{database}")
    monkeypatch.setattr(site, "DB_PATH", str(database))
    monkeypatch.setitem(site.app.config, "TESTING", True)
    with site.app.app_context():
        site.db.session.remove()
        original_engine = site.db.engines[None]
        site.db.engines[None] = engine
    try:
        yield
    finally:
        with site.app.app_context():
            site.db.session.remove()
            engine.dispose()
            site.db.engines[None] = original_engine


@pytest.fixture
def client():
    return site.app.test_client()
