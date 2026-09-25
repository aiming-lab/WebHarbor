"""Shared pytest fixtures for the mta mirror test suite.

Each test module gets a scratch database (a copy of instance_seed/mta.db) via
the MTA_DB_PATH hook, so stateful tests never touch the real instance
database and never break the byte-identical reset invariant.
"""
import os
import pathlib
import shutil
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent
SEED = SITE / "instance_seed" / "mta.db"

if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))


@pytest.fixture()
def app(tmp_path):
    if not SEED.exists():
        pytest.skip("instance_seed/mta.db not built yet")
    scratch = tmp_path / "mta.db"
    shutil.copyfile(SEED, scratch)
    os.environ["MTA_DB_PATH"] = f"sqlite:///{scratch}"
    try:
        import importlib
        import app as app_module
        importlib.reload(app_module)
        yield app_module.app
    finally:
        os.environ.pop("MTA_DB_PATH", None)


@pytest.fixture()
def client(app):
    return app.test_client()
