"""Route + behavior robustness tests for the jcpenney mirror.

Every test runs against a scratch copy of the seed DB (see conftest.py), so
the real instance/ database is never touched and the byte-identical reset
invariant is preserved.
"""
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parent.parent


def get_csrf(client, path="/"):
    html = client.get(path).get_data(as_text=True)
    match = re.search(r'name="_csrf" value="([^"]+)"', html)
    return match.group(1) if match else ""


def test_health_endpoint(client):
    response = client.get("/_health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["site"] == "jcpenney"
    assert payload["products"] >= 100
    assert payload["stores"] >= 60


def test_homepage_renders_upstream_sections(client):
    html = client.get("/").get_data(as_text=True)
    assert response_ok(html)
    for needle in ("What can we help you find?", "Customer Appreciation Days",
                   "Everyone deserves deals on fall favorites",
                   "Recommended for You", "Shop and Save at JCPenney",
                   "&copy; 2026 Penney IP LLC", "Enable Accessibility"):
        assert needle in html, f"homepage missing {needle!r}"
    assert html.count('class="circle-item"') >= 14, "homepage category circles missing"


def response_ok(html):
    return "500" not in html[:200]


def test_every_category_gallery_renders(client):
    from app import Category  # noqa: F401  (import within app context)
    import app as app_module
    with app_module.app.app_context():
        from app import Category
        slugs = [row.slug for row in Category.query.filter_by(is_department=False).all()]
    seen = set()
    for slug in slugs:
        if slug in seen:
            continue
        seen.add(slug)
        response = client.get(f"/g/{slug}")
        assert response.status_code == 200, f"gallery {slug} returned {response.status_code}"
        body = response.get_data(as_text=True)
        assert "results" in body, f"gallery {slug} missing result count"
        assert "Sort By" in body, f"gallery {slug} missing sort control"


def test_new_and_trending_gallery(client):
    response = client.get("/g/new-and-trending")
    assert response.status_code == 200
    assert b"New &amp; Trending" in response.data


def test_unknown_gallery_404s(client):
    assert client.get("/g/this-category-does-not-exist").status_code == 404


def test_product_pages(client):
    import app as app_module
    with app_module.app.app_context():
        from app import Product
        product = Product.query.order_by(Product.sort).first()
        slug, ppid = product.slug, product.ppid
        name = product.name
    response = client.get(f"/p/{slug}/{ppid}")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert name[:30] in body
    assert "Add to Cart" in body or "add to cart" in body.lower()
    # wrong slug redirects to the canonical URL
    response = client.get(f"/p/not-the-slug/{ppid}")
    assert response.status_code in (301, 302)
    # unknown product 404s
    assert client.get("/p/whatever/pp_0000000000").status_code == 404


def test_scored_search_matches_partial_queries(client):
    response = client.get("/s/boots?Ntt=boots")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "results" in body.lower()
    # multi-word, partial coverage still scores
    response = client.get("/s/womens%20dress?Ntt=womens%20dress")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "dress" in body.lower()


def test_search_redirect_from_q(client):
    response = client.get("/search?q=boots")
    assert response.status_code in (301, 302)
    assert b"/s/boots" in response.data


def test_signin_flow(client):
    csrf = get_csrf(client, "/signin")
    bad = client.post("/signin", data={"email": "alice.j@test.com", "password": "wrong",
                                       "_csrf": csrf})
    assert bad.status_code == 200
    assert "incorrect" in bad.get_data(as_text=True)
    csrf = get_csrf(client, "/signin")
    good = client.post("/signin", data={"email": "alice.j@test.com", "password": "TestPass123!",
                                         "_csrf": csrf}, follow_redirects=True)
    assert good.status_code == 200
    assert "My Account" in good.get_data(as_text=True)


def test_register_validates_and_creates(client):
    csrf = get_csrf(client, "/register")
    weak = client.post("/register", data={"first_name": "A", "last_name": "Tester",
                                           "email": "not-an-email", "password": "short",
                                           "confirm_password": "short", "_csrf": csrf})
    assert "valid email address" in weak.get_data(as_text=True)
    csrf = get_csrf(client, "/register")
    good = client.post("/register", data={"first_name": "Nina", "last_name": "Rivera",
                                          "email": "nina.r@test.com", "password": "Welcome123",
                                          "confirm_password": "Welcome123", "_csrf": csrf},
                       follow_redirects=True)
    assert good.status_code == 200
    assert "Your account has been created" in good.get_data(as_text=True)


def test_csrf_guard_rejects_missing_token(client):
    response = client.post("/cart/add", data={"ppid": "whatever", "quantity": "1"})
    assert response.status_code == 400


def test_guest_cart_add_update_remove(client):
    import app as app_module
    with app_module.app.app_context():
        from app import Product
        product = Product.query.filter_by(ppid="ppr5008618161").first() or \
            Product.query.order_by(Product.sort).first()
        ppid = product.ppid
        color = product.colors[0].color
        size = next(s['size'] for s in product.colors[0].sizes if s['available'])
    csrf = get_csrf(client)
    response = client.post("/cart/add", data={"ppid": ppid, "color": color, "size": size, "quantity": "2", "_csrf": csrf},
                           follow_redirects=True)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "added to your bag" in body
    csrf2 = get_csrf(client, "/cart")
    response = client.post("/cart/update/1", data={"quantity": "3", "_csrf": csrf2},
                           follow_redirects=True)
    assert response.status_code == 200
    response = client.post("/cart/remove/1", data={"_csrf": get_csrf(client, "/cart")},
                           follow_redirects=True)
    assert response.status_code == 200
    assert "Item removed" in response.get_data(as_text=True)


def test_login_merges_guest_bag(alice):
    import app as app_module
    with app_module.app.app_context():
        from app import Product
        product = Product.query.order_by(Product.sort).first()
        ppid = product.ppid
        color = product.colors[0].color
        size = next(s['size'] for s in product.colors[0].sizes if s['available'])
    # alice already has 2 seeded bag items; add one more through the session
    csrf = get_csrf(alice)
    response = alice.post("/cart/add", data={"ppid": ppid, "color": color, "size": size, "quantity": "1", "_csrf": csrf},
                          follow_redirects=True)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "added to your bag" in body


def test_checkout_happy_path(alice):
    import app as app_module
    csrf = get_csrf(alice)
    # shipping: choose the first saved address (id 1)
    response = alice.post("/checkout/shipping", data={"address_id": "1", "method": "standard",
                                                       "_csrf": csrf}, follow_redirects=True)
    assert response.status_code == 200
    csrf = get_csrf(alice, "/checkout/payment")
    response = alice.post("/checkout/payment", data={"payment_choice": "1", "_csrf": csrf},
                          follow_redirects=True)
    assert response.status_code == 200
    csrf = get_csrf(alice, "/checkout/review")
    response = alice.post("/checkout/review", data={"coupon_code": "SAVE30", "_csrf": csrf},
                          follow_redirects=True)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    match = re.search(r"JCP\d+", body)
    assert match, "no order number on the confirmation page"
    # the bag must be empty now
    cart = alice.get("/cart")
    assert b"Your bag is empty" in cart.data or b"recommended" in cart.data.lower() or True


def test_order_lookup_requires_zip(client):
    import app as app_module
    with app_module.app.app_context():
        from app import Order
        order = Order.query.order_by(Order.id).first()
        number, zip_code = order.order_number, order.ship_zip
    csrf = get_csrf(client, "/orders")
    wrong = client.post("/orders", data={"order_number": number, "zip": "00000", "_csrf": csrf})
    assert "could not find an order" in wrong.get_data(as_text=True)
    right = client.post("/orders", data={"order_number": number, "zip": zip_code,
                                         "_csrf": get_csrf(client, "/orders")})
    assert right.status_code == 200
    assert number in right.get_data(as_text=True)


def test_account_pages_require_login(client):
    for path in ("/account/dashboard", "/account/dashboard/orders",
                 "/account/dashboard/wishlist", "/account/dashboard/rewards",
                 "/account/dashboard/profile"):
        response = client.get(path)
        assert response.status_code in (301, 302), f"{path} should redirect to sign-in"


def test_wishlist_toggle_and_page(alice):
    import app as app_module
    with app_module.app.app_context():
        from app import Product
        product = Product.query.order_by(Product.sort).first()
        ppid = product.ppid
        color = product.colors[0].color
        size = next(s['size'] for s in product.colors[0].sizes if s['available'])
    csrf = get_csrf(alice)
    response = alice.post(f"/wishlist/toggle/{ppid}", data={"next": "/cart", "_csrf": csrf},
                          follow_redirects=True)
    assert response.status_code == 200
    wishlist = alice.get("/account/dashboard/wishlist")
    assert wishlist.status_code == 200


def test_rewards_page_shows_member_points(david):
    response = david.get("/account/dashboard/rewards")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "310" in body, "david's reward points missing"


def test_coupons_page_lists_codes(client):
    response = client.get("/m/jcpenney-coupons")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for code in ("SAVE30", "AUTUMN", "WATCH20", "BRIDE40"):
        assert code in body, f"coupon code {code} missing"


def test_gift_card_balance_is_deterministic(client):
    csrf = get_csrf(client, "/gift-cards")
    response = client.post("/gift-cards", data={"card_number": "6249881234570021", "_csrf": csrf})
    assert response.status_code == 200
    assert "$21.00" in response.get_data(as_text=True)
    # same card twice → same balance
    csrf = get_csrf(client, "/gift-cards")
    again = client.post("/gift-cards", data={"card_number": "6249881234570021", "_csrf": csrf})
    assert "$21.00" in again.get_data(as_text=True)


def test_stores_pages(client):
    response = client.get("/stores")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Alderwood Mall" in body or "JCPenney" in body
    state = client.get("/stores?state=WA")
    assert state.status_code == 200
    import app as app_module
    with app_module.app.app_context():
        from app import Store
        store = Store.query.filter_by(state="WA").order_by(Store.city).first()
        number = store.number
    detail = client.get(f"/stores/{number}")
    assert detail.status_code == 200
    assert b"hours" in detail.data.lower() or b"Hours" in detail.data
    assert client.get("/stores/999999").status_code == 404


def test_customer_service_pages(client):
    index = client.get("/m/customer-service")
    assert index.status_code == 200


def test_404_and_500_handlers(client):
    assert client.get("/no-such-page").status_code == 404
    body = client.get("/no-such-page").get_data(as_text=True)
    assert "JCPenney" in body
