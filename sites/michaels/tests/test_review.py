"""Independent regressions for review findings, using isolated application copies."""

import importlib.util
import re
import shutil
import sys
from pathlib import Path
import pytest


@pytest.fixture
def appmod(tmp_path):
    source = Path(__file__).resolve().parents[1]
    target = tmp_path / source.name
    shutil.copytree(
        source, target, ignore=shutil.ignore_patterns("instance", "__pycache__")
    )
    (target / "instance").mkdir()
    shutil.copy2(
        target / "instance_seed" / f"{source.name}.db",
        target / "instance" / f"{source.name}.db",
    )
    sys.path.insert(0, str(target))
    spec = importlib.util.spec_from_file_location(
        source.name + "_review_app", target / "app.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.app.config.update(TESTING=True)
    yield mod
    with mod.app.app_context():
        mod.db.engine.dispose()
    sys.path.remove(str(target))


def token(client, path):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def login(c):
    csrf = token(c, "/login")
    c.post(
        "/login",
        data={
            "csrf_token": csrf,
            "email": "alice.j@test.com",
            "password": "TestPass123!",
        },
    )
    return csrf


def test_csrf_and_local_redirect(appmod):
    c = appmod.app.test_client()
    assert (
        c.post(
            "/login", data={"email": "alice.j@test.com", "password": "TestPass123!"}
        ).status_code
        == 400
    )
    csrf = token(c, "/login")
    r = c.post(
        "/login?next=https://example.org",
        data={
            "csrf_token": csrf,
            "email": "alice.j@test.com",
            "password": "TestPass123!",
        },
    )
    assert r.headers["Location"] == "/"
    assert c.get("/logout").status_code == 405


def test_checkout_invalid_address_cannot_be_placed(appmod):
    c = appmod.app.test_client()
    csrf = login(c)
    with appmod.app.app_context():
        before = appmod.Order.query.count()
    with c.session_transaction() as sess:
        sess.update(checkout_method="Ship", checkout_address="9999", checkout_card="1")
    c.post("/checkout", data={"csrf_token": csrf, "step": "place"})
    with appmod.app.app_context():
        assert appmod.Order.query.count() == before


def test_checkout_foreign_card_rejected(appmod):
    c = appmod.app.test_client()
    csrf = login(c)
    with appmod.app.app_context():
        before = appmod.Order.query.count()
        foreign = (
            appmod.PaymentCard.query.filter(appmod.PaymentCard.user_id != 1).first().id
        )
    with c.session_transaction() as sess:
        sess.update(checkout_method="Pickup", checkout_card=str(foreign))
    c.post("/checkout", data={"csrf_token": csrf, "step": "place"})
    with appmod.app.app_context():
        assert appmod.Order.query.count() == before
