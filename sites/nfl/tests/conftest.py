"""Shared pytest fixtures for the nfl mirror test suite.

Each test module gets a scratch database (a copy of instance_seed/nfl.db) via
the NFL_DB_PATH hook, so stateful tests never touch the real instance
database and never break the byte-identical reset invariant.
"""
import importlib
import os
import pathlib
import shutil
import sys

import pytest
from flask.testing import FlaskClient


class FormClient(FlaskClient):
    def post(self, *args, **kwargs):
        self.get("/")
        with self.session_transaction() as sess:
            token = sess.get("csrf_token")
        kwargs["data"] = {**kwargs.get("data", {}), "csrf_token": token}
        return super().post(*args, **kwargs)


SITE = pathlib.Path(__file__).resolve().parent.parent
SEED = SITE / "instance_seed" / "nfl.db"

if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))


@pytest.fixture()
def app(tmp_path):
    if not SEED.exists():
        pytest.skip("instance_seed/nfl.db not built yet")
    scratch = tmp_path / "nfl.db"
    shutil.copyfile(SEED, scratch)
    os.environ["NFL_DB_PATH"] = f"sqlite:///{scratch}"
    try:
        import app as app_module
        importlib.reload(app_module)
        app_module.app.test_client_class = FormClient
        with app_module.app.app_context():
            pass
        yield app_module.app
    finally:
        os.environ.pop("NFL_DB_PATH", None)


@pytest.fixture()
def client(app):
    return app.test_client()


def login(app, email):
    client = app.test_client()
    response = client.post(
        "/account/signin/",
        data={"email": email, "password": "TestPass123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return client


@pytest.fixture()
def alice(app):
    return login(app, "alice.j@test.com")


@pytest.fixture()
def bob(app):
    return login(app, "bob.c@test.com")
