"""Robustness tests for the macys_wine_shop mirror app.

Runs against a scratch SQLite DB (see conftest.py) so the shipped seed is
never touched.
"""
import re


def _csrf(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else ""


def test_home_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"macy" in r.data.lower()
    assert b"What we" in r.data  # featured section heading


def test_health(client):
    r = client.get("/_health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["products"] >= 300
    assert data["users"] >= 4


def test_collection_filters_and_sort(client):
    r = client.get("/collections/all-wine")
    assert r.status_code == 200
    assert b"Shop All Wine" in r.data
    r = client.get("/collections/all-wine?filter.p.m.drinks.varietal=Cabernet+Sauvignon")
    assert r.status_code == 200
    assert b"Cabernet Sauvignon" in r.data
    r = client.get("/collections/all-wine?sort_by=price-ascending")
    assert r.status_code == 200


def test_product_pages(client):
    for handle in ("2021-free-flight-pinot-noir", "golden-state-essentials-case", "giftcard"):
        r = client.get(f"/products/{handle}")
        assert r.status_code == 200
    r = client.get("/products/does-not-exist")
    assert r.status_code == 404


def test_case_contents(client):
    r = client.get("/products/golden-state-essentials-case")
    assert r.status_code == 200
    assert b"Bottles In This Case" in r.data
    assert b"per bottle" in r.data


def test_search_scored(client):
    r = client.get("/search?q=pinot")
    assert r.status_code == 200
    assert b"results found" in r.data
    # token search, not strict AND
    r2 = client.get("/search?q=chardonnay california")
    assert r2.status_code == 200
    # empty query
    r3 = client.get("/search")
    assert r3.status_code == 200


def test_age_gate_flow(client):
    r = client.get("/")
    assert b"Welcome!" in r.data  # age gate shown on first visit
    # YES without state -> error
    r = client.post("/age/confirm", data={"state": "", "answer": "yes"})
    assert r.status_code == 400
    # NO -> rejected page
    r = client.post("/age/confirm", data={"state": "CA", "answer": "no"})
    assert b"Sorry, you cannot proceed." in r.data
    # proper confirmation
    r = client.post("/age/confirm", data={"state": "CA", "answer": "yes"})
    assert r.get_json()["ok"] is True
    with client.session_transaction() as sess:
        sess["age_confirmed"] = True
        sess["ship_state"] = "CA"
    r = client.get("/")
    assert b"Welcome!" not in r.data


def test_cart_and_state_compliance(client):
    with client.session_transaction() as sess:
        sess["age_confirmed"] = True
        sess["ship_state"] = "UT"
    # Time & Tide Chardonnay cannot ship to UT
    r = client.get("/products/2023-time-tide-chardonnay-monterey-county")
    assert b"Item cannot ship to your state" in r.data
    # find a UT-shippable variant via the quickview API and add it
    import json as jsonlib
    from app import Product, ProductVariant
    with client.application.app_context():
        variant = (ProductVariant.query.join(Product, Product.id == ProductVariant.product_id)
                   .filter(Product.product_type == "Bottle")
                   .filter(ProductVariant.available_states.like('%\"UT\"%')).first())
        vid = variant.id
    r = client.post("/cart/add", data={"variant_id": vid, "quantity": "2"})
    assert r.get_json()["ok"] is True
    r = client.get("/cart")
    assert b"Order Summary" in r.data


def test_blocked_state_add_to_cart(client):
    with client.session_transaction() as sess:
        sess["age_confirmed"] = True
        sess["ship_state"] = "UT"
    from app import Product, ProductVariant
    with client.application.app_context():
        variant = (ProductVariant.query.join(Product, Product.id == ProductVariant.product_id)
                   .filter(Product.handle == "2023-time-tide-chardonnay-monterey-county")
                   .first())
        vid = variant.id
    r = client.post("/cart/add", data={"variant_id": vid, "quantity": "1"})
    assert r.status_code == 403
    assert r.get_json()["error"] == "Item cannot ship to your state"


def test_cart_minimum_and_checkout_guard(client):
    with client.session_transaction() as sess:
        sess["age_confirmed"] = True
    from app import Product, ProductVariant
    with client.application.app_context():
        variant = (ProductVariant.query.join(Product, Product.id == ProductVariant.product_id)
                   .filter(Product.product_type == "Bottle").first())
        vid = variant.id
    client.post("/cart/add", data={"variant_id": vid, "quantity": "1"})
    r = client.get("/cart")
    assert b"Minimum" in r.data  # 1 bottle < 3 minimum
    r = client.get("/checkout")
    assert r.status_code == 302  # bounces back to cart


def test_auth_and_account(alice):
    r = alice.get("/account")
    assert r.status_code == 200
    assert b"Alice" in r.data
    r = alice.get("/account/orders")
    assert r.status_code == 200
    assert b"MWS" in r.data  # seeded order numbers


def test_wrong_password_error(client):
    r = client.post("/login", data={"email": "alice.j@test.com", "password": "wrong",
                                    "csrf_token": _csrf(client)})
    assert b"Incorrect email or password" in r.data


def test_registration_validation(client):
    token = _csrf(client, "/register")
    r = client.post("/register", data={"email": "bad", "first_name": "A", "last_name": "B",
                                       "password": "short", "confirm": "short",
                                       "csrf_token": token})
    assert b"valid email" in r.data or b"at least 8" in r.data
    token = _csrf(client, "/register")
    r = client.post("/register", data={"email": "new.user@example.com", "first_name": "New",
                                       "last_name": "User", "password": "Password9!",
                                       "confirm": "Password9!", "csrf_token": token},
                    follow_redirects=True)
    assert r.status_code == 200


def test_order_status_lookup(client):
    token = _csrf(client, "/order-status")
    r = client.post("/order-status", data={"order_number": "MWS1042",
                                           "email": "alice.j@test.com",
                                           "csrf_token": token})
    assert r.status_code == 200
    assert b"MWS1042" in r.data
    token = _csrf(client, "/order-status")
    r = client.post("/order-status", data={"order_number": "MWS1042",
                                           "email": "wrong@example.com",
                                           "csrf_token": token})
    assert b"find an order" in r.data


def test_newsletter(client):
    r = client.post("/newsletter/subscribe", data={"email": "fan@example.com"})
    assert r.get_json()["ok"] is True
    r = client.post("/newsletter/subscribe", data={"email": "not-an-email"})
    assert r.status_code == 400


def test_static_pages_and_blog(client):
    for path in ("/pages/wine-club", "/pages/faq", "/pages/shipping-policy",
                 "/blogs/wine-101", "/blogs/wine-101/what-is-chenin-blanc-wine"):
        r = client.get(path)
        assert r.status_code == 200, path


def test_csrf_guard(client):
    # POST without CSRF token on guarded endpoints -> 400
    r = client.post("/login", data={"email": "x@y.com", "password": "z"})
    assert r.status_code == 400
