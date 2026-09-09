from __future__ import annotations

import importlib
import os
import shutil
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def drugs_app(tmp_path_factory):
    seed = SITE / "instance_seed" / "drugs_com.db"
    assert seed.is_file()
    database = tmp_path_factory.mktemp("drugs-app") / "drugs_com.db"
    shutil.copy2(seed, database)
    os.environ["DRUGS_COM_SECRET_KEY"] = "pytest-secret-key-with-at-least-32-characters"
    os.environ["DRUGS_COM_DATABASE_PATH"] = str(database)
    sys.path.insert(0, str(SITE))
    module = importlib.import_module("app")
    module.app.config.update(TESTING=True, WTF_CSRF_TIME_LIMIT=None)
    module._test_database_path = database
    return module


@pytest.fixture
def client(drugs_app):
    with drugs_app.app.app_context():
        drugs_app.db.session.remove()
        drugs_app.db.engine.dispose()
    shutil.copy2(SITE / "instance_seed" / "drugs_com.db", drugs_app._test_database_path)
    with drugs_app._auth_failures_lock:
        drugs_app._auth_failures.clear()
    with drugs_app.app.test_client() as test_client:
        yield test_client
    with drugs_app.app.app_context():
        drugs_app.db.session.remove()
        drugs_app.db.engine.dispose()
