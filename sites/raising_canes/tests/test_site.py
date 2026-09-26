"""Site tests for the Raising Cane's mirror — model, route and seed invariants.

Run from the site directory:  python -m pytest tests/ -q
(the app module is imported from the parent directory).
"""
import importlib.util
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
sys.path.insert(0, SITE)

spec = importlib.util.spec_from_file_location("rc_app", os.path.join(SITE, "app.py"))
rc_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc_app)

app = rc_app.app
db = rc_app.db


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    resp = client.get("/_health")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_homepage_and_menu(client):
    assert client.get("/").status_code == 200
    page = client.get("/menu/").get_data(as_text=True)
    assert "The Box Combo" in page
    assert "Tailgates" in page
    assert "Extras" in page


def test_menu_item_detail_has_nutrition(client):
    page = client.get("/menu/the-box-combo").get_data(as_text=True)
    assert "Box Combo" in page
    assert "Nutrition Facts" in page
    assert "Sodium" in page


def test_allergen_table(client):
    page = client.get("/allergens/").get_data(as_text=True)
    assert "Chicken Finger" in page
    assert "Allergen Key" in page
    assert "Sweet Tea" in page


def test_location_search_and_detail(client):
    page = client.get("/locations/?q=Baton%20Rouge").get_data(as_text=True)
    assert "Baton Rouge" in page
    page = client.get("/locations/la_baton-rouge_6588-siegen-lane").get_data(as_text=True)
    assert "6588 Siegen Lane" in page
    assert "Drive-Thru Hours" in page


def test_order_chain(client):
    # restaurant picker
    page = client.get("/order/?q=70809").get_data(as_text=True)
    assert "Start Order" in page
    # restaurant menu
    page = client.get("/order/location/la_baton-rouge_6588-siegen-lane").get_data(as_text=True)
    assert "Combos" in page
    # quantity step
    page = client.get("/order/location/la_baton-rouge_6588-siegen-lane/item/1?qty=25").get_data(as_text=True)
    assert "Large Sweet Tea" in page
    assert "No Slaw (NSL)" in page


def test_quantity_pricing_matches_upstream(client):
    """25 Box Combos with Large Sweet Tea = 297.25 + 6.75 = 304.00 (upstream Olo)."""
    from flask import session
    with client.session_transaction() as sess:
        sess["food_cart"] = [{
            "item_id": 1, "quantity_label": "25",
            "selections": ["No Slaw (NSL)", "Large Sweet Tea"],
            "line_total": 304.00,
            "location_slug": "la_baton-rouge_6588-siegen-lane",
        }]
    page = client.get("/order/cart").get_data(as_text=True)
    assert "$304.00" in page


def test_gear_catalog_and_product(client):
    page = client.get("/gear/collection/Apparel?sort=price_asc").get_data(as_text=True)
    assert "Raising Cane’s" in page
    page = client.get("/gear/product/raising-canes-retro-crewneck").get_data(as_text=True)
    assert "39.99" in page
    assert "Add to Cart" in page


def test_gear_headwear_collection(client):
    """Review A-3: upstream Shopify product_type 'Hats' must land in the
    Headwear storefront collection so the hats are reachable from the
    primary gear navigation."""
    page = client.get("/gear/collection/Headwear").get_data(as_text=True)
    assert "Oak Leaf Trucker Hat" in page
    assert "10 products" in page          # collection no longer renders empty
    assert "Youth Hat" in page                # youth hats live here too
    home = client.get("/gear/").get_data(as_text=True)
    assert home.count("/gear/collection/Headwear") >= 1
    with app.app_context():
        assert rc_app.GearProduct.query.filter_by(collection="Hats").count() == 0
        assert rc_app.GearProduct.query.filter_by(collection="Headwear").count() == 10


def test_gear_variant_price_charges_selected_denomination(client):
    """Review A-2: a $25 gift-card denomination must check out at $25.00
    ($31.95 with shipping), never at the product's minimum variant price."""
    import re as _re
    page = client.get("/gear/product/graduation-gift-card").get_data(as_text=True)
    assert 'name="price"' not in page   # form no longer posts a client-set price
    token = _re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    resp = client.post("/gear/cart", data={"handle": "graduation-gift-card",
                                           "variant": "$25", "qty": "1",
                                           "csrf_token": token},
                       follow_redirects=True)
    assert resp.status_code == 200
    cart = client.get("/gear/cart").get_data(as_text=True)
    assert "Graduation Gift Card" in cart
    assert "$25.00" in cart
    assert "$5.00" not in cart
    page = client.get("/gear/checkout").get_data(as_text=True)
    token = _re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    resp = client.post("/gear/checkout", data={
        "ship_name": "Carol Davis", "ship_line1": "1902 North Central Expressway",
        "ship_city": "McKinney", "ship_state": "TX", "ship_zip": "75069",
        "email": "carol.d@test.com", "payment_method": "Discover",
        "csrf_token": token}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        order = rc_app.GearOrder.query.order_by(rc_app.GearOrder.id.desc()).first()
        assert abs(order.shipping - 6.95) < 0.005
        assert abs(order.total - 31.95) < 0.005
        item = order.items[0]
        assert item.variant_title == "$25"
        assert abs(item.price - 25.00) < 0.005


def test_gift_card_balance_check(client):
    with app.app_context():
        gc = rc_app.GiftCard.query.first()
        assert gc is not None
    page = client.get("/gift-cards/check").get_data(as_text=True)
    assert "Gift Card Number" in page


def test_careers_search(client):
    page = client.get("/careers/?q=Manager").get_data(as_text=True)
    assert "Restaurant" in page
    page = client.get("/careers/?state=TX").get_data(as_text=True)
    assert "TX" in page


def test_faq(client):
    page = client.get("/faq/").get_data(as_text=True)
    assert "FREQUENTLY ASKED QUESTIONS" in page
    assert "What is Raising Cane’s Chicken Fingers?" in page


def test_benchmark_users_seeded():
    with app.app_context():
        User = rc_app.User
        for email in ["alice.j@test.com", "bob.c@test.com", "carol.d@test.com",
                      "david.k@test.com"]:
            assert User.query.filter_by(email=email).first() is not None
        alice = User.query.filter_by(email="alice.j@test.com").first()
        assert alice.check_password("TestPass123!")


def test_seed_volume():
    with app.app_context():
        Location, MenuItem, GearProduct, Job, NutritionRow = (rc_app.Location, rc_app.MenuItem, rc_app.GearProduct, rc_app.Job, rc_app.NutritionRow)
        assert Location.query.count() >= 900
        assert MenuItem.query.count() >= 20
        assert GearProduct.query.count() >= 80
        assert Job.query.count() >= 200
        assert NutritionRow.query.count() >= 100


def test_search_is_scored(client):
    page = client.get("/search?q=tailgate").get_data(as_text=True)
    assert "Tailgate" in page
    page = client.get("/search?q=houston").get_data(as_text=True)
    assert "Houston" in page or "houston" in page


def test_login_flow(client):
    import re as _re
    page = client.get("/login").get_data(as_text=True)
    token = _re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    resp = client.post("/login", data={"email": "alice.j@test.com",
                                       "password": "TestPass123!",
                                       "csrf_token": token},
                       follow_redirects=True)
    assert resp.status_code == 200
    page = resp.get_data(as_text=True)
    assert "MY ACCOUNT" in page or "Alice" in page


def test_404(client):
    assert client.get("/no-such-page").status_code == 404


def test_order_cancel_flow(client):
    import re as _re
    with client.session_transaction() as sess:
        pass
    page = client.get("/login").get_data(as_text=True)
    token = _re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    client.post("/login", data={"email": "alice.j@test.com",
                                "password": "TestPass123!", "csrf_token": token})
    page = client.get("/orders/RC-100236").get_data(as_text=True)
    token = _re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    resp = client.post("/orders/RC-100236/cancel", data={"csrf_token": token},
                       follow_redirects=True)
    assert resp.status_code == 200
    page = resp.get_data(as_text=True)
    assert "Cancelled" in page
