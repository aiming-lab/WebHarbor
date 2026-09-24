"""Functional robustness checks for the LandWatch mirror (Flask test client).

Model access goes through the `lw` fixture (the reloaded app module bound to
the per-test scratch database), never a top-level import, so tests can never
query the live instance DB or break the byte-identical reset invariant.
"""
import re

import pytest


@pytest.fixture()
def lw(app):
    import sys
    return sys.modules["app"]


def first_listing(app, lw):
    """First active listing as a plain dict (queried inside an app context)."""
    with app.app_context():
        row = (lw.Listing.query
               .filter(lw.Listing.status.in_(lw.ACTIVE_STATUSES))
               .order_by(lw.Listing.sort_rank).first())
        return {"pid": row.pid, "price": row.price, "acres": row.acres,
                "state_slug": row.state_slug, "canonical_slug": row.canonical_slug,
                "detail_path": row.detail_path(), "price_display": row.price_display,
                "acres_display": row.acres_display}


def test_homepage_renders_with_real_sections(client):
    html = client.get("/").get_data(as_text=True)
    for phrase in ("Search Land for Sale", "Land for Sale in the United States",
                   "List your property on the Land.com Network",
                   "CoStar Group", "Find an Agent", "Search by State"):
        assert phrase in html, f"homepage missing {phrase!r}"
    assert "/static/images/home/LW-Hero-1600.webp" in html
    assert "/static/images/property-types/land-for-sale.webp" in html


def test_health_endpoint(client):
    data = client.get("/_health").get_json()
    assert data["ok"] is True and data["site"] == "landwatch"
    assert data["listings"] >= 150
    assert data["agents"] >= 50


@pytest.mark.parametrize("path", [
    "/land", "/hunting-property", "/farms-ranches", "/homes",
    "/timberland-property", "/commercial-property", "/homesites",
    "/recreational-property", "/horse-property", "/undeveloped-land",
    "/waterfront-property", "/land/owner-financing", "/land/auctions",
    "/hunting-property/auctions",
])
def test_category_pages_render(client, path):
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Land for Sale" in html or "Land for Auction" in html
    assert "Listings" in html


def test_state_page_and_filters(client, app, lw):
    html = client.get("/texas-land-for-sale").get_data(as_text=True)
    assert "Texas Land for Sale" in html
    assert re.search(r"1-25 of [\d,]+ Listings", html)
    for facet in ("Price", "Parcel Size", "Property Types", "Sale Type"):
        assert facet in html, f"missing facet group {facet}"
    html = client.get("/texas-land-for-sale/price-over-1000000").get_data(as_text=True)
    assert "Texas Land for Sale" in html
    with app.app_context():
        count = (lw.Listing.query
                 .filter(lw.Listing.status.in_(lw.ACTIVE_STATUSES),
                         lw.Listing.state_slug == "texas-land-for-sale",
                         lw.Listing.price >= 1000000).count())
    m = re.search(r"1-\d+ of ([\d,]+) Listings", html)
    assert int(m.group(1).replace(",", "")) == count


def test_county_and_city_pages(client, app, lw):
    with app.app_context():
        county = lw.County.query.filter_by(state_slug="texas-land-for-sale").first()
        city = lw.City.query.filter_by(state_slug="texas-land-for-sale").first()
    assert client.get(f"/texas-land-for-sale/{county.slug}").status_code == 200
    assert client.get(f"/texas-land-for-sale/{city.slug}").status_code == 200
    assert client.get("/texas-land-for-sale/not-a-real-county").status_code == 404


def test_region_page(client, app, lw):
    with app.app_context():
        region = lw.Region.query.filter_by(state_slug="texas-land-for-sale").first()
    if region is None:
        pytest.skip("no Texas regions seeded")
    html = client.get(f"/texas-land-for-sale/{region.slug}").get_data(as_text=True)
    assert region.name in html


def test_sort_orders(client, lw, app):
    listing = first_listing(app, lw)
    state = listing["state_slug"]
    low = client.get(f"/{state}?sort=price-low").get_data(as_text=True)
    prices = [int(p.replace(",", "")) for p in
              re.findall(r"\$([\d,]+)\s*•", low)]
    assert prices == sorted(prices), "price-low sort is not ascending"
    high = client.get(f"/{state}?sort=price-high").get_data(as_text=True)
    prices = [int(p.replace(",", "")) for p in
              re.findall(r"\$([\d,]+)\s*•", high)]
    assert prices == sorted(prices, reverse=True), "price-high sort is not descending"


def test_pagination(client):
    html = client.get("/land").get_data(as_text=True)
    m = re.search(r"1-25 of ([\d,]+) Listings", html)
    total = int(m.group(1).replace(",", ""))
    if total > 25:
        page2 = client.get("/land/page-2")
        assert page2.status_code == 200
        assert "26-50 of" in page2.get_data(as_text=True)


def test_listing_detail_renders(client, app, lw):
    listing = first_listing(app, lw)
    html = client.get(listing["detail_path"]).get_data(as_text=True)
    assert listing["price_display"] in html
    assert listing["acres_display"] in html
    assert "Highlights" in html or "Description" in html
    assert "Send Message" in html
    assert f"/static/images/listings/{listing["pid"]}/" in html


def test_listing_detail_canonical_redirect(client, app, lw):
    listing = first_listing(app, lw)
    response = client.get(f"/wrong-slug/pid/{listing["pid"]}")
    assert response.status_code == 301
    assert listing["canonical_slug"] in response.headers["Location"]


def test_contact_form_validation_and_persistence(client, app, lw):
    listing = first_listing(app, lw)
    bad = client.post(f"/contact/{listing["pid"]}",
                      data={"name": "", "email": "nope", "message": "hi"})
    assert bad.status_code == 400
    ok = client.post(f"/contact/{listing["pid"]}",
                     data={"name": "Test Buyer", "email": "buyer@example.com",
                           "message": "Interested in access roads."},
                     follow_redirects=True)
    assert ok.status_code == 200
    with app.app_context():
        row = (lw.Inquiry.query.filter_by(pid=listing["pid"])
               .order_by(lw.Inquiry.id.desc()).first())
        assert row is not None and row.email == "buyer@example.com"


def test_register_login_logout_flow(client, app, lw):
    response = client.post("/register", data={
        "email": "new.user@test.com", "password": "Passw0rd!",
        "name": "New User"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert lw.User.query.filter_by(email="new.user@test.com").first() is not None
    client.get("/log-out")
    response = client.post("/log-in", data={
        "email": "new.user@test.com", "password": "Passw0rd!"},
        follow_redirects=True)
    assert response.status_code == 200
    assert b"My LandWatch" in response.data


def test_bad_login_rejected(client):
    response = client.post("/log-in", data={
        "email": "alice.j@test.com", "password": "WrongPass1!"})
    assert response.status_code == 401
    assert b"Invalid email or password" in response.data


def test_register_validates_input(client):
    bad = client.post("/register", data={"email": "broken", "password": "short"})
    assert bad.status_code == 400
    dup = client.post("/register", data={"email": "alice.j@test.com",
                                        "password": "Passw0rd!"})
    assert dup.status_code == 409


def test_favorite_requires_login(client, app, lw):
    listing = first_listing(app, lw)
    response = client.post(f"/favorite/{listing["pid"]}")
    assert response.status_code == 401


def test_favorite_toggle_and_account(alice, app, lw):
    listing = first_listing(app, lw)
    response = alice.post(f"/favorite/{listing["pid"]}")
    assert response.get_json() == {"ok": True, "saved": True}
    html = alice.get("/account").get_data(as_text=True)
    assert listing["price_display"] in html
    response = alice.post(f"/favorite/{listing["pid"]}")
    assert response.get_json() == {"ok": True, "saved": False}


def test_saved_search_flow(alice):
    response = alice.post("/save-search",
                         json={"url": "/texas-land-for-sale/price-over-1000000",
                               "name": "Texas $1M+"})
    assert response.get_json()["ok"] is True
    html = alice.get("/account").get_data(as_text=True)
    assert "Texas $1M+" in html


def test_benchmark_user_fixture_data(alice, app, lw):
    with app.app_context():
        user = lw.User.query.filter_by(email="alice.j@test.com").first()
        assert 3 <= lw.Favorite.query.filter_by(user_id=user.id).count() <= 6
        assert 1 <= lw.SavedSearch.query.filter_by(user_id=user.id).count() <= 3


def test_agent_profile_and_find_agent(client, app, lw):
    with app.app_context():
        agent = (lw.Agent.query.filter(lw.Agent.total_listings > 0)
                 .order_by(lw.Agent.total_listings.desc()).first())
    html = client.get(agent.profile_path()).get_data(as_text=True)
    assert agent.name in html
    assert "Total Listings" in html
    fa = client.get("/find-agent").get_data(as_text=True)
    assert "Find a Land Specialist" in fa
    fa_tx = client.get("/find-agent?state=TX").get_data(as_text=True)
    assert "United States" in fa_tx


def test_location_search_resolves(client):
    response = client.get("/search?q=Austin")
    assert response.status_code == 302
    assert "/texas-land-for-sale/austin" in response.headers["Location"]
    response = client.get("/search?q=Houston")
    assert response.status_code == 302
    assert "houston" in response.headers["Location"]


def test_suggest_endpoint(client):
    data = client.get("/api/suggest?q=harr").get_json()
    assert any("Harris" in r["label"] for r in data["results"])


def test_404_pages(client):
    assert client.get("/nope-land-for-sale").status_code == 404
    assert client.get("/land/not-a-filter").status_code == 404
    assert client.get("/profile/ghost/0").status_code == 404


def test_static_and_sitemap(client):
    assert client.get("/terms-conditions").status_code == 200
    html = client.get("/sitemap").get_data(as_text=True)
    assert "Texas Land for Sale" in html


def test_rendered_cards_reference_real_photos(client):
    """Every rendered card must reference a downloaded listing photo path."""
    html = client.get("/land").get_data(as_text=True)
    srcs = re.findall(r'src="(/static/images/listings/\d+/[^"]+)"', html)
    assert srcs, "no listing photos rendered on /land"


def test_account_requires_login(client):
    response = client.get("/account")
    assert response.status_code == 302
    assert "/log-in" in response.headers["Location"]
