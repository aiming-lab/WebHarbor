"""Shared pytest fixtures for the macys_wine_shop mirror test suite.

Each test module gets a scratch database, seeded from the tracked
source_data.json via the MWS_DB_URI hook, so stateful tests never touch the
real instance database and never break the byte-identical reset invariant.
"""
import importlib
import os
import pathlib
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent

if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))


@pytest.fixture()
def app(tmp_path):
    scratch = tmp_path / "macys_wine_shop.db"
    os.environ["MWS_DB_URI"] = f"sqlite:///{scratch}"
    try:
        import app as app_module
        importlib.reload(app_module)
        import seed_data
        importlib.reload(seed_data)
        with app_module.app.app_context():
            app_module.db.create_all()
            seed_data.seed_database()
            seed_data.seed_benchmark_users()
        yield app_module.app
    finally:
        os.environ.pop("MWS_DB_URI", None)


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(app, email):
    client = app.test_client()
    html = client.get("/login").get_data(as_text=True)
    import re
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    token = match.group(1) if match else ""
    response = client.post("/login", data={
        "email": email, "password": "TestPass123!", "csrf_token": token},
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


def csrf_post(client, path, **kwargs):
    """Submit a functional test request with the same token a browser receives."""
    import re
    html = client.get('/').get_data(as_text=True)
    token = re.search(r'<meta name="csrf-token" content="([^"]+)"', html).group(1)
    kwargs['headers'] = {**kwargs.get('headers', {}), 'X-CSRF-Token': token}
    return client.post(path, **kwargs)
