"""Shared pytest fixtures for the LandWatch mirror test suite.

Each test module gets a scratch database (a copy of instance_seed/landwatch.db)
via the LW_DB_PATH hook, so stateful tests never touch the real instance
database and never break the byte-identical reset invariant.
"""
import importlib
import os
import pathlib
import shutil
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent
SEED = SITE / "instance_seed" / "landwatch.db"

if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))


@pytest.fixture()
def app(tmp_path):
    if not SEED.exists():
        pytest.skip("instance_seed/landwatch.db not built yet")
    scratch = tmp_path / "landwatch.db"
    shutil.copyfile(SEED, scratch)
    os.environ["LW_DB_PATH"] = f"sqlite:///{scratch}"
    os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"
    try:
        import app as app_module
        importlib.reload(app_module)
        yield app_module.app
    finally:
        os.environ.pop("LW_DB_PATH", None)


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(app, email):
    client = app.test_client()
    response = csrf_post(client, "/log-in", data={"email": email, "password": "TestPass123!"},
                          follow_redirects=True)
    assert response.status_code == 200
    return client


@pytest.fixture()
def alice(app):
    """A test client signed in as alice.j@test.com."""
    return _login(app, "alice.j@test.com")


def csrf_post(client, path, **kwargs):
    """Submit a functional test request with the same token a browser receives."""
    import re
    html = client.get('/').get_data(as_text=True)
    token = re.search(r'<meta name="csrf-token" content="([^"]+)"', html).group(1)
    kwargs['headers'] = {**kwargs.get('headers', {}), 'X-CSRF-Token': token}
    return client.post(path, **kwargs)
