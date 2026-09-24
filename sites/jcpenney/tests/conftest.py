"""Shared pytest fixtures for the jcpenney mirror test suite.

Each test module gets a scratch database (a copy of instance_seed/jcpenney.db)
via the JCP_DB_PATH hook, so stateful tests never touch the real instance
database and never break the byte-identical reset invariant.
"""
import importlib
import os
import pathlib
import shutil
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent
SEED = SITE / "instance_seed" / "jcpenney.db"

if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))


@pytest.fixture()
def app(tmp_path):
    if not SEED.exists():
        pytest.skip("instance_seed/jcpenney.db not built yet")
    scratch = tmp_path / "jcpenney.db"
    shutil.copyfile(SEED, scratch)
    os.environ["JCP_DB_PATH"] = f"sqlite:///{scratch}"
    try:
        import app as app_module
        importlib.reload(app_module)
        with app_module.app.test_request_context():
            pass
        yield app_module.app
    finally:
        os.environ.pop("JCP_DB_PATH", None)


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(app, email):
    client = app.test_client()
    html = client.get("/signin").get_data(as_text=True)
    import re
    match = re.search(r'name="_csrf" value="([^"]+)"', html)
    token = match.group(1) if match else ""
    response = client.post("/signin", data={"email": email, "password": "TestPass123!",
                                             "_csrf": token},
                          follow_redirects=True)
    assert response.status_code == 200
    return client


@pytest.fixture()
def alice(app):
    """A test client signed in as alice.j@test.com."""
    return _login(app, "alice.j@test.com")


@pytest.fixture()
def bob(app):
    """A test client signed in as bob.c@test.com."""
    return _login(app, "bob.c@test.com")


@pytest.fixture()
def carol(app):
    """A test client signed in as carol.d@test.com."""
    return _login(app, "carol.d@test.com")


@pytest.fixture()
def david(app):
    """A test client signed in as david.k@test.com."""
    return _login(app, "david.k@test.com")
