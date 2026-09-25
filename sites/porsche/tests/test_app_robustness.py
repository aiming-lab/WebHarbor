"""App robustness checks for the porsche mirror.

Every major surface must render (200, non-empty), filters and sorts must
actually filter and sort, the stateful flows (login, save vehicle, build
save, cart, checkout) must persist, and bad input must fail cleanly.
"""
import re
import sqlite3

SITE = __file__.rsplit("/", 2)[0]


def _db(app):
    from app import Vehicle, ModelVariant, Dealer, ShopProduct, ConfiguratorOption
    return Vehicle, ModelVariant, Dealer, ShopProduct, ConfiguratorOption


def test_health(client):
    r = client.get("/_health")
    assert r.status_code == 200
    assert r.get_json() == {"ok": True, "site": "porsche"}


def test_homepage_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Your Porsche journey starts now." in r.data
    assert b"Explore the models" in r.data


def test_models_overview_filters_and_sorts(client):
    r = client.get("/usa/models/")
    assert r.status_code == 200
    assert b"model variants" in r.data
    r = client.get("/usa/models/?range=911")
    assert r.status_code == 200
    assert b"911" in r.data
    # price-asc sort: first card cheaper than last card
    r = client.get("/usa/models/?range=911&sort=price-asc")
    prices = [int(m.replace(b",", b"")) for m in re.findall(rb"From \$ ([\d,]+)", r.data)]
    assert prices and all(prices[i] >= prices[i - 1] for i in range(1, len(prices)))
    r = client.get("/usa/models/?fuel=Electric")
    assert b"Taycan" in r.data


def test_model_detail_and_range_pages(client, app):
    from app import ModelVariant
    with app.app_context():
        m = ModelVariant.query.filter_by(detail_slug="911-carrera-gts").first()
        assert m is not None
    r = client.get(f"/usa/models/{m.range_slug}/{m.series_slug}/{m.detail_slug}/")
    assert r.status_code == 200
    assert b"911 Carrera GTS" in r.data
    assert b"Displacement" in r.data
    r = client.get("/usa/models/911/")
    assert r.status_code == 200
    r = client.get("/usa/models/not-a-range/")
    assert r.status_code == 404


def test_configurator_pages(client, app):
    r = client.get("/configurator/")
    assert r.status_code == 200
    assert b"992142" in r.data
    r = client.get("/configurator/en-US/mode/model/992142")
    assert r.status_code == 200
    assert b"Base price" in r.data
    # selecting an option changes the total
    from app import ConfiguratorOption
    with app.app_context():
        opt = (ConfiguratorOption.query
               .filter_by(model_code="992142")
               .order_by(ConfiguratorOption.price.desc()).first())
        base = 181000
    r = client.get(f"/configurator/en-US/mode/model/992142?opt={opt.option_id}")
    assert f"${base + opt.price:,}".encode() in (r.data.replace(b",", b",") or b"")
    r = client.get("/configurator/en-US/mode/model/NOTREAL")
    assert r.status_code == 404


def test_finder_search_filters(client, app):
    r = client.get("/finder/us/en-US/search")
    assert r.status_code == 200
    assert b"vehicles match" in r.data
    r = client.get("/finder/us/en-US/search?condition=new&range=911&sort=price-asc")
    assert r.status_code == 200
    assert b"New" in r.data
    r = client.get("/finder/us/en-US/search?transmission=Manual&range=911")
    assert r.status_code == 200
    data = r.data.decode()
    assert data.count("card-title") >= 5  # at least 5 manual 911s
    r = client.get("/finder/us/en-US/search?page=99")
    assert r.status_code == 200  # out-of-range page renders empty, not 500
    r = client.get("/finder/us/en-US/search?min_price=zzz&max_price=abc")
    assert r.status_code == 200  # junk numeric input ignored


def test_vehicle_detail(client, app):
    from app import Vehicle
    with app.app_context():
        v = Vehicle.query.filter_by(listing_id="9P2V7O").first()
        assert v is not None
    r = client.get(f"/finder/us/en-US/details/{v.slug}")
    assert r.status_code == 200
    assert v.vin.encode() in r.data
    assert b"Price details" in r.data
    r = client.get("/finder/us/en-US/details/no-such-vehicle")
    assert r.status_code == 404


def test_dealer_search(client, app):
    r = client.get("/usa/dealersearch/")
    assert r.status_code == 200
    assert b"Browse by state" in r.data
    r = client.get("/usa/dealersearch/?state=CA")
    assert r.status_code == 200
    assert b"Porsche" in r.data
    r = client.get("/usa/dealersearch/?q=Bellevue")
    assert r.status_code == 200
    assert b"Porsche Bellevue" in r.data
    r = client.get("/usa/dealersearch/?state=ZZ")
    assert r.status_code == 200  # unknown state: empty result, not 500


def test_shop_catalog_and_product(client, app):
    from app import ShopProduct
    r = client.get("/shop/")
    assert r.status_code == 200
    for slug in ("accessories", "clothing", "home"):
        r = client.get(f"/shop/us/en-US/c/{slug}")
        assert r.status_code == 200, slug
    with app.app_context():
        p = ShopProduct.query.filter_by(slug="classic-leather-jacket-P-P1140-590").first()
        assert p is not None
    r = client.get(f"/shop/us/en-US/p/{p.slug}")
    assert r.status_code == 200
    assert b"Classic Leather Jacket" in r.data
    r = client.get("/shop/us/en-US/c/not-a-category")
    assert r.status_code == 404


def test_auth_and_saved_vehicle_flow(client, app):
    r = client.post("/my-porsche/sign-in", data={
        "email": "casey.taylor@test.com", "password": "TestPass123!"},
        follow_redirects=True)
    assert r.status_code == 200
    assert b"Hi, Casey" in r.data
    # wrong password rejected
    r = client.post("/my-porsche/sign-in", data={
        "email": "casey.taylor@test.com", "password": "wrong"},
        follow_redirects=True)
    assert b"Invalid email or password" in r.data
    # save a vehicle
    from app import Vehicle
    with app.app_context():
        v = Vehicle.query.order_by(Vehicle.price).first()
    r = client.post(f"/finder/us/en-US/details/{v.slug}/save",
                    follow_redirects=True)
    assert b"saved to your saved vehicles" in r.data
    r = client.get("/my-porsche/saved-vehicles")
    assert v.name.encode() in r.data


def test_registration_validates(client):
    r = client.post("/my-porsche/register", data={
        "first_name": "A", "last_name": "B",
        "email": "not-an-email", "password": "short"},
        follow_redirects=True)
    assert b"valid email" in r.data
    r = client.post("/my-porsche/register", data={
        "first_name": "A", "last_name": "B",
        "email": "casey.taylor@test.com", "password": "longenough1"},
        follow_redirects=True)
    assert b"already exists" in r.data


def test_configurator_save_flow(client, app):
    client.post("/my-porsche/sign-in", data={
        "email": "jordan.morgan@test.com", "password": "TestPass123!"})
    r = client.post("/configurator/en-US/mode/model/992142/save",
                    data={"opt": ["0Q", "2T"], "build_name": "Test build"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert b"Test build" in r.data


def test_configurator_build_name_is_form_associated(client, app):
    """The 'Name this build' input must submit with the configuration form.

    Regression for the review's A-2 finding: the input previously sat
    outside <form id="cfgform"> without a form= association, so UI saves
    silently dropped the typed name (test_client POSTs never caught it).
    """
    r = client.get("/configurator/en-US/mode/model/992142")
    assert r.status_code == 200
    html = r.data.decode()
    m = re.search(r'<input id="build_name"[^>]*>', html)
    assert m, "build_name input missing from configurator page"
    assert 'form="cfgform"' in m.group(0), "build_name is not associated with cfgform"
    # the typed name survives an Update-total round trip
    r = client.get("/configurator/en-US/mode/model/992142?opt=0Q&build_name=Weekend+Taycan")
    assert 'value="Weekend Taycan"' in r.data.decode()


def test_finder_facets_use_upstream_clean_labels(client, app):
    """fuel / drivetrain must carry the live site's clean labels, never the
    raw backend enums that leaked into part of the capture (B-5)."""
    from app import Vehicle, db
    with app.app_context():
        fuels = {f for (f,) in db.session.query(Vehicle.fuel).distinct()}
        drives = {d for (d,) in db.session.query(Vehicle.drivetrain).distinct()}
    assert not fuels & {"ELECTRIC", "PETROL", "DIESEL", "MILD_HYBRID", "PLUG_IN_HYBRID"}
    assert not drives & {"AllWheelDriveConfiguration", "RearWheelDriveConfiguration"}
    assert {"Electric", "Gasoline"} <= fuels
    assert {"All-wheel-drive", "Rear-wheel-drive"} <= drives
    # the electric-Taycan total is single-anchored: every Taycan is Electric
    r = client.get("/finder/us/en-US/search?range=Taycan&fuel=Electric")
    assert r.status_code == 200


def test_model_image_paths_are_clean(app):
    """Highlights/gallery paths must be single-slash /static/ URLs (the
    seeded values previously carried a '//static' double slash)."""
    from app import ModelVariant
    with app.app_context():
        for m in ModelVariant.query.all():
            paths = ([m.highlights_image] if m.highlights_image else []) + (m.gallery_images or [])
            for p in paths:
                assert p.startswith("/static/"), f"{m.model_type}: {p!r}"


def test_cart_and_checkout_flow(client, app):
    from app import ShopProduct
    with app.app_context():
        p = ShopProduct.query.filter_by(slug="classic-leather-jacket-P-P1140-590").first()
        pid = p.id
        price = p.price_cents
    r = client.post("/shop/cart/add", data={"product_id": pid, "quantity": 2},
                    follow_redirects=True)
    assert b"Classic Leather Jacket" in r.data
    # line total 2x price
    expected = f"${price * 2 / 100:,.2f}".encode()
    assert expected in r.data
    r = client.post("/shop/checkout", data={
        "email": "shopper@example.com", "first_name": "Sam", "last_name": "Buyer",
        "street": "1 Main St", "city": "Bellevue", "state": "WA", "zip": "98005"},
        follow_redirects=True)
    assert b"order is confirmed" in r.data
    m = re.search(rb"Order number <strong>(PS[A-Z0-9]+)</strong>", r.data)
    assert m, "order number rendered"
    # invalid checkout re-renders with errors
    r = client.post("/shop/cart/add", data={"product_id": pid, "quantity": 1})
    r = client.post("/shop/checkout", data={
        "email": "bad", "first_name": "", "last_name": "",
        "street": "", "city": "", "state": "XX", "zip": "12"},
        follow_redirects=True)
    assert b"valid email" in r.data


def test_404_page(client):
    r = client.get("/no/such/page")
    assert r.status_code == 404
    assert b"404" in r.data


def test_catalog_richness_for_tasks(app):
    """The seeded catalog must support the deep-link task set."""
    from app import (ConfiguratorOption, Dealer, ModelVariant, ShopProduct,
                     Vehicle, db)
    with app.app_context():
        assert ModelVariant.query.count() == 76
        assert ConfiguratorOption.query.count() == 331
        assert Vehicle.query.count() >= 440
        assert Dealer.query.count() == 218
        assert ShopProduct.query.count() >= 180
        # every task-anchor facet has enough rows
        assert Vehicle.query.filter_by(transmission="Manual").count() >= 5
        assert Vehicle.query.filter(
            Vehicle.condition == "preowned", Vehicle.model_range == "Panamera",
            Vehicle.price < 130000, Vehicle.mileage < 30000).count() >= 1
        assert Dealer.query.filter_by(state="CA").count() == 33
        # VINs are present and unique (task answers rely on them)
        vins = [v.vin for v in Vehicle.query.all() if v.vin]
        assert len(vins) >= 400 and len(set(vins)) == len(vins)
        # --- review r2 re-anchored task surfaces -------------------------
        # T19: enough pre-owned 911s for the register-and-save task
        assert Vehicle.query.filter_by(
            condition="preowned", model_range="911").count() >= 6
        # T2: exactly two electric variants tie at the top starting price
        top = (db.session.query(db.func.max(ModelVariant.price_value))
               .filter(ModelVariant.fuel_type == "Electric").scalar())
        assert (ModelVariant.query.filter(
            ModelVariant.fuel_type == "Electric",
            ModelVariant.price_value == top).count() == 2)
        # T10: the cheapest brand-new Macan carries a delivery fee line
        macan = (Vehicle.query.filter_by(condition="new", model_range="Macan")
                 .order_by(Vehicle.price).first())
        labels = " ".join(i.get("label", "") for b in macan.breakdown
                          for i in b.get("items", []))
        assert "Delivery" in labels
        # T4: the exact-name new 911 Carrera exists (scope excludes Cabriolet)
        exact = Vehicle.query.filter(
            Vehicle.condition == "new",
            Vehicle.full_title.endswith("Porsche 911 Carrera")).all()
        assert len(exact) >= 1
        # T13: the Washington stock leader lists at least two vehicles
        wa = Dealer.query.filter_by(state="WA").all()
        counts = [d.inventory_count for d in wa]
        assert max(counts) >= 2 and counts.count(max(counts)) == 1
        # T14: the third-largest dealer state is uniquely ranked
        state_counts = [c for (_s, c) in db.session.query(
            Dealer.state, db.func.count(Dealer.id)).group_by(Dealer.state).all()]
        top3 = sorted(state_counts, reverse=True)[:3]
        assert len(top3) == 3 and len(set(top3)) == 3


def test_csrf_enforced_on_all_post_routes(client, app):
    """A POST without the session token must be rejected (400), not acted on."""
    for path in ("/my-porsche/sign-in", "/my-porsche/register",
                 "/shop/cart/add", "/shop/cart/update", "/shop/checkout",
                 "/configurator/en-US/mode/model/992142/save",
                 "/finder/us/en-US/details/porsche-911-carrera-new-W37NMD/save"):
        r = client.post(path, data={"csrf_token": "wrong-token"})
        assert r.status_code == 400, f"{path} accepted a bad CSRF token"
    # a raw client (no session token at all) must also be rejected
    with app.test_client() as raw:
        for path in ("/my-porsche/sign-in", "/shop/cart/add",
                     "/shop/checkout"):
            r = raw.post(path, data={"email": "x@y.zz", "password": "password1"})
            assert r.status_code == 400, f"{path} accepted a missing CSRF token"
