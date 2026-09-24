"""Shared fixtures for the marriott mirror test suite.

Tests run against a scratch copy of the shipped seed so write paths
(booking / cancel / account edits) never mutate the real instance DB.
"""
import os
import pathlib
import shutil
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SITE))

os.environ.setdefault("FLASK_SECRET_KEY", "marriott-mirror-test")


@pytest.fixture(scope="session")
def _scratch_db(tmp_path_factory):
    seed = SITE / "instance_seed" / "marriott.db"
    scratch = tmp_path_factory.mktemp("wh-mirror-db") / "marriott.db"
    if seed.exists():
        shutil.copyfile(seed, scratch)
    else:  # pre-seed bootstrap builds it in place
        scratch.touch()
    os.environ["WEBHARBOR_MIRROR_DB"] = str(scratch)
    return scratch


@pytest.fixture(scope="session")
def app(_scratch_db):
    import importlib
    import app as app_module
    importlib.reload(app_module)
    return app_module.app


@pytest.fixture()
def client(app):
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture()
def db(app):
    from app import db as _db
    with app.app_context():
        yield _db
