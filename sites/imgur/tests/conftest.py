"""Shared pytest fixtures for the imgur mirror test suite.

Each test module gets a scratch database (a copy of instance_seed/imgur.db)
via the IMGUR_DB_PATH hook, so stateful tests never touch the real instance
database and never break the byte-identical reset invariant.
"""
import os
import pathlib
import shutil
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent
SEED = SITE / "instance_seed" / "imgur.db"

if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))


@pytest.fixture()
def app(tmp_path):
    if not SEED.exists():
        pytest.skip("instance_seed/imgur.db not built yet")
    scratch = tmp_path / "imgur.db"
    shutil.copyfile(SEED, scratch)
    os.environ["IMGUR_DB_PATH"] = f"sqlite:///{scratch}"
    try:
        import importlib
        import app as app_module
        importlib.reload(app_module)
        yield app_module.app
    finally:
        os.environ.pop("IMGUR_DB_PATH", None)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def logged_in(app):
    """A test client signed in as alice_j."""
    client = app.test_client()
    response = client.post("/signin", data={"username": "alice.j@test.com",
                                            "password": "TestPass123!"},
                           follow_redirects=True)
    assert response.status_code == 200
    return client
