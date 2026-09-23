"""Shared test fixtures: every test starts from a byte-identical seed copy."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))
os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"

import app as site  # noqa: E402
import seed_data  # noqa: E402

SEED = SITE / "instance_seed" / "dillards.db"

if not SEED.exists():
    seed_data.build_seed_database()


@pytest.fixture(autouse=True)
def clean_database():
    with site.app.app_context():
        site.db.session.remove()
        site.db.engine.dispose()
    Path(site.DB_PATH).parent.mkdir(exist_ok=True)
    shutil.copy2(SEED, site.DB_PATH)
    site.app.config.update(TESTING=True)
    yield
    with site.app.app_context():
        site.db.session.remove()
        site.db.engine.dispose()
    Path(site.DB_PATH).unlink(missing_ok=True)


@pytest.fixture
def client():
    return site.app.test_client()
