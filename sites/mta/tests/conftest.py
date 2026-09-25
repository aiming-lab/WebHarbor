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
from flask.testing import FlaskClient


class FormClient(FlaskClient):
    def post(self, *args, **kwargs):
        self.get("/account/login")
        with self.session_transaction() as sess:
            token = sess.get("csrf_token")
        kwargs["data"] = {**kwargs.get("data", {}), "csrf_token": token}
        return super().post(*args, **kwargs)


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
        app_module.app.test_client_class = FormClient
        yield app_module.app
    finally:
        os.environ.pop("MTA_DB_PATH", None)


@pytest.fixture()
def client(app):
    return app.test_client()
