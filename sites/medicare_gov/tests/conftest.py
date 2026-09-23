"""Shared pytest fixtures for the medicare_gov mirror test suite.

Each test module gets a scratch database (a copy of instance_seed/medicare_gov.db)
via the MEDICARE_GOV_DB_PATH hook, so stateful tests never touch the real
instance database and never break the byte-identical reset invariant.
"""
import os
import pathlib
import shutil
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent
SEED = SITE / "instance_seed" / "medicare_gov.db"

if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))


@pytest.fixture()
def app(tmp_path):
    if not SEED.exists():
        pytest.skip("instance_seed/medicare_gov.db not built yet")
    scratch = tmp_path / "medicare_gov.db"
    shutil.copyfile(SEED, scratch)
    os.environ["MEDICARE_GOV_DB_PATH"] = f"sqlite:///{scratch}"
    try:
        import importlib
        import app as app_module
        importlib.reload(app_module)
        yield app_module.app
    finally:
        os.environ.pop("MEDICARE_GOV_DB_PATH", None)


@pytest.fixture()
def client(app):
    return app.test_client()
