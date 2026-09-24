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


def test_confirmation_requires_account_or_session(appmod):
    c = appmod.app.test_client()
    assert c.get("/checkout/confirmation?order=MC2608231112").status_code == 403
    csrf = token(c, "/account/signin")
    c.post(
        "/account/signin",
        data={
            "csrf_token": csrf,
            "email": "carol.d@test.com",
            "password": "TestPass123!",
        },
    )
    assert c.get("/checkout/confirmation?order=MC2608231112").status_code == 200
    assert c.get("/checkout/confirmation?order=MC2609071148").status_code == 403


def test_invalid_shipping_not_saved(appmod):
    c = appmod.app.test_client()
    csrf = token(c, "/account/signin")
    c.post(
        "/account/signin",
        data={
            "csrf_token": csrf,
            "email": "alice.j@test.com",
            "password": "TestPass123!",
        },
    )
    with appmod.app.app_context():
        before = appmod.Address.query.count()
    c.post(
        "/checkout/shipping",
        data={
            "csrf_token": csrf,
            "save_address": "on",
            "full_name": "Alice",
            "line1": "123 Main",
            "city": "Test",
            "state": "NY",
            "zip": "invalid",
        },
    )
    with appmod.app.app_context():
        assert appmod.Address.query.count() == before


def test_out_of_stock_pickup_rejected(appmod):
    c = appmod.app.test_client()
    csrf = token(c, "/account/signin")
    c.post(
        "/account/signin",
        data={
            "csrf_token": csrf,
            "email": "alice.j@test.com",
            "password": "TestPass123!",
        },
    )
    with appmod.app.app_context():
        before = appmod.Order.query.count()
    with c.session_transaction() as sess:
        sess["mc_checkout"] = {
            "method": "pickup",
            "store_id": "085",
            "contact_name": "Alice",
            "contact_email": "alice.j@test.com",
            "card_last4": "2111",
            "card_brand": "Visa",
        }
    response = c.post(
        "/checkout/review", data={"csrf_token": csrf}, follow_redirects=True
    )
    assert b"unavailable" in response.data
    with appmod.app.app_context():
        assert appmod.Order.query.count() == before


def test_checkout_cannot_skip_delivery(appmod):
    c = appmod.app.test_client()
    csrf = token(c, "/account/signin")
    c.post(
        "/account/signin",
        data={
            "csrf_token": csrf,
            "email": "alice.j@test.com",
            "password": "TestPass123!",
        },
    )
    with appmod.app.app_context():
        before = appmod.Order.query.count()
    with c.session_transaction() as sess:
        sess["mc_checkout"] = {"card_last4": "2111"}
    c.post("/checkout/review", data={"csrf_token": csrf})
    with appmod.app.app_context():
        assert appmod.Order.query.count() == before
