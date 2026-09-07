"""Behavioral regressions for the standalone Compass environment."""
import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))
TEST_DIR = tempfile.TemporaryDirectory(prefix="compass-tests-")
os.environ["COMPASS_DATABASE_PATH"] = str(Path(TEST_DIR.name) / "compass.db")
os.environ["COMPASS_SKIP_SEED"] = "1"
m = importlib.import_module("app")


@pytest.fixture()
def client():
    m.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with m.app.app_context():
        m.db.drop_all()
        m.db.create_all()
        for name in ("Alice", "Bob"):
            user = m.User(name=name, email=name.lower()+"@example.com", budget_min=100, budget_max=200, beds_min=1)
            user.set_password("test-pass-123")
            m.db.session.add(user)
        m.db.session.add_all([
            m.Listing(id=1, slug="san-francisco", address="1 Sample Street", city="San Francisco", status="for-sale", price=100, beds=2, baths_full=1, baths_half=1, days_on_compass=0),
            m.Listing(id=2, slug="new-york", address="2 Sample Street", city="New York", status="for-sale", price=200, beds=3, baths_full=2, baths_half=0, days_on_compass=2),
        ])
        m.db.session.commit()
    yield m.app.test_client()


def login(client, next_url="/account"):
    return client.post("/login", query_string={"next":next_url}, data={"email":"alice@example.com", "password":"test-pass-123"})


def test_listing_title_does_not_contain_share_dialog_markup(client):
    import re
    html = client.get("/listing/san-francisco").get_data(as_text=True)
    assert re.search(r"<title>(.*?)</title>", html, re.S).group(1).strip() == "1 Sample Street | Compass"
    assert html.count('id="share-property"') == 1


@pytest.mark.parametrize("route", ["/login", "/register", "/account/edit", "/account/preferences",
                                   "/account/change-password", "/tour/1", "/inquiry/1",
                                   "/collections/new", "/saved-searches"])
def test_form_labels_identify_their_controls(client, route):
    from html.parser import HTMLParser

    class Labels(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = set()
            self.labels = []
            self.active = None

        def handle_starttag(self, tag, attributes):
            attrs = dict(attributes)
            if attrs.get("id"):
                assert attrs["id"] not in self.ids, "duplicate control id"
                self.ids.add(attrs["id"])
            if tag == "label":
                self.active = {"for": attrs.get("for"), "wrapped": False}
            if tag in {"input", "select", "textarea"} and self.active is not None:
                self.active["wrapped"] = True

        def handle_endtag(self, tag):
            if tag == "label" and self.active is not None:
                self.labels.append(self.active)
                self.active = None

    if route not in {"/login", "/register"}:
        login(client)
    parser = Labels()
    response = client.get(route)
    assert response.status_code == 200
    parser.feed(response.get_data(as_text=True))
    assert parser.labels
    assert all(label["wrapped"] or label["for"] in parser.ids for label in parser.labels)


@pytest.mark.parametrize("target", ["https://foreign.example/", "//foreign.example/", "/\\foreign.example/", "https://localhost.evil.example/"])
def test_login_never_redirects_outside_mirror(client, target):
    assert login(client, target).location == "/account"


def test_local_return_path_survives_login(client):
    assert login(client, "/saved?tab=homes").location == "/saved?tab=homes"


def test_mutation_referrer_is_same_origin(client):
    login(client)
    response=client.post("/save/1", headers={"Referer":"https://foreign.example/"})
    assert response.location == "/listing/san-francisco"


def test_logout_requires_csrf_protected_post(client):
    login(client)
    assert client.get("/logout").status_code == 405
    m.app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/logout").status_code == 400
    assert client.get("/account").status_code == 200


@pytest.mark.parametrize("email,password", [("bad-address","valid-pass"),("ok@example.com","a"),("ok@example.com","é"*40)])
def test_invalid_registration_does_not_write(client, email, password):
    client.post("/register",data={"name":"Example", "email":email,"password":password,"confirm":password})
    with m.app.app_context(): assert m.User.query.count()==2


def test_saved_city_and_half_bath_filters(client):
    with m.app.app_context():
        assert [x.id for x in m.filter_listings(m.Listing.query,{"city":"San Francisco"}).all()]==[1]
        assert [x.id for x in m.filter_listings(m.Listing.query,{"baths":"2"}).all()]==[2]
        assert [x.id for x in m.filter_listings(m.Listing.query,{"baths":"1.5"}).all()]==[1,2]
        assert [x.id for x in m.sort_listings(m.Listing.query.all(),"newest")]==[1,2]


@pytest.mark.parametrize("changes", [{"budget_min":"999","budget_max":"bad","beds_min":"3"},{"budget_min":"500","budget_max":"100","beds_min":"2"},{"budget_min":"-1","budget_max":"100","beds_min":"2"},{"property_types":"Spaceship"}])
def test_invalid_preferences_are_atomic(client, changes):
    login(client)
    before=None
    with m.app.app_context():
        u=m.User.query.filter_by(email="alice@example.com").one()
        before=(u.budget_min,u.budget_max,u.beds_min,u.preferred_property_types)
    client.post("/account/preferences",data=changes)
    with m.app.app_context():
        u=m.User.query.filter_by(email="alice@example.com").one()
        assert (u.budget_min,u.budget_max,u.beds_min,u.preferred_property_types)==before


@pytest.mark.parametrize("date,time,kind", [("","11:00 AM","in-person"),("2026-02-30","11:00 AM","in-person"),("2026-07-12","midnight","video"),("2026-07-12","11:00 AM","teleport")])
def test_invalid_tour_does_not_write(client,date,time,kind):
    login(client)
    client.post("/tour/1",data={"date":date,"time":time,"tour_type":kind})
    with m.app.app_context(): assert m.Tour.query.count()==0


def test_fixed_benchmark_tour_is_valid_independent_of_wall_clock(client):
    login(client)
    assert client.post("/tour/1",data={"date":"2026-07-12","time":"11:00 AM","tour_type":"in-person"}).status_code==302
    with m.app.app_context(): assert m.Tour.query.count()==1


@pytest.mark.parametrize("fields", [{},{"name":"Guest","email":"invalid","message":"Question"},{"name":"Guest","email":"guest@example.com","message":"  "}])
def test_invalid_inquiry_does_not_write(client,fields):
    client.post("/inquiry/1",data=fields)
    with m.app.app_context(): assert m.Inquiry.query.count()==0


def test_foreign_objects_cannot_be_modified(client):
    with m.app.app_context():
        m.db.session.add(m.Collection(id=1,user_id=2,name="Private",share_token="test-token",listing_ids_json="[2]"))
        m.db.session.add(m.Tour(id=1,user_id=2,listing_id=2,status="requested"))
        m.db.session.commit()
    login(client)
    for path in ("/collections/1/add/1","/collections/1/remove/2","/collections/1/delete","/tour/1/cancel"):
        assert client.post(path).status_code==404
    with m.app.app_context():
        assert m.Collection.query.get(1).get_listing_ids()==[2]
        assert m.Tour.query.get(1).status=="requested"


def test_collection_can_be_populated_from_listing_ui(client):
    login(client)
    with m.app.app_context():
        m.db.session.add(m.Collection(id=1,user_id=1,name='My picks',share_token='mine',listing_ids_json='[]'))
        m.db.session.add(m.Collection(id=2,user_id=2,name='Other picks',share_token='theirs',listing_ids_json='[]'))
        m.db.session.commit()
    page=client.get('/listing/san-francisco')
    assert b'name="collection_id"' in page.data
    assert client.post('/listing/1/add-to-collection',data={'collection_id':'2'}).status_code==404
    assert client.post('/listing/1/add-to-collection',data={'collection_id':'1'}).status_code==302
    with m.app.app_context():
        assert m.db.session.get(m.Collection,1).get_listing_ids()==[1]
        assert m.db.session.get(m.Collection,2).get_listing_ids()==[]


def test_saved_search_preserves_filters_and_can_be_reopened(client):
    login(client)
    criteria={'q':'Sample','city':'New York','status':'for-sale','property_type':'Single Family','price_min':'50','price_max':'500','beds':'2','baths':'2','sqft_min':'100','year_built_min':'1900','pool':'on'}
    client.post('/saved-searches',data={'name':'My precise search',**criteria})
    with m.app.app_context():
        saved=m.SavedSearch.query.one()
        assert all(saved.get_criteria().get(k)==v for k,v in criteria.items())
    response=client.get('/saved-searches')
    assert b'href="/search?' in response.data and b'My precise search' in response.data


def test_unknown_price_and_rented_listing_are_not_sale_quotes(client):
    unknown=m.Listing(address="Price withheld", price=None)
    rented=m.Listing(address="Archived rental",status="rented",is_rental=True,price=10000,sqft=1000)
    assert unknown.price_display()=="Price upon request"
    assert rented.price_display()=="$10,000/mo"
    assert rented.price_per_sqft()==0


def test_price_per_sqft_uses_exact_ranking_and_half_up_display(client):
    higher=m.Listing(price=1008,sqft=2,status="for-sale")
    lower=m.Listing(price=1007,sqft=2,status="for-sale")
    assert lower.price_per_sqft()==504
    assert higher.price_per_sqft()==504
    assert m.sort_listings([higher,lower],"ppsf_asc")==[lower,higher]


def test_seed_bytes_do_not_depend_on_index_creation_order(tmp_path):
    import hashlib
    import sqlite3
    from migrate_seed import canonical_copy
    hashes=[]
    for indexes in [("a","b"),("b","a")]:
        source=tmp_path/(indexes[0]+".db")
        output=tmp_path/(indexes[0]+"-stable.db")
        with sqlite3.connect(source) as con:
            con.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, a TEXT, b INTEGER)")
            for name in indexes:con.execute(f"CREATE INDEX sample_{name} ON sample({name})")
            con.execute("INSERT INTO sample VALUES(1,'value',7)")
        canonical_copy(source,output)
        hashes.append(hashlib.sha256(output.read_bytes()).hexdigest())
    assert hashes[0]==hashes[1]


def test_marketing_status_routes_use_source_status_not_new_flag(client):
    with m.app.app_context():
        first = m.db.session.get(m.Listing, 1)
        first.is_new = True
        first.is_compass_exclusive = True
        first.property_facts_json = json.dumps({"Status": "Active"})
        second = m.db.session.get(m.Listing, 2)
        second.is_new = False
        second.property_facts_json = json.dumps({"Status": "Coming Soon"})
        m.db.session.commit()
    coming = client.get('/coming-soon/listings/').get_data(as_text=True)
    assert '/listing/new-york' in coming
    assert '/listing/san-francisco' not in coming
    assert '/listing/san-francisco' not in client.get('/private-exclusives/').get_data(as_text=True)
    with m.app.app_context():
        m.db.session.get(m.Listing, 1).property_facts_json = json.dumps({"Status": "Active (Private)"})
        m.db.session.commit()
    private = client.get('/private-exclusives/').get_data(as_text=True)
    assert '/listing/san-francisco' in private
    assert '/listing/new-york' not in private


def test_marketing_routes_do_not_modify_catalog_or_user_state(client):
    with m.app.app_context():
        before = [(row.id, row.property_facts_json) for row in m.Listing.query.order_by(m.Listing.id)]
        users = m.User.query.count()
    for route in ['/concierge/', '/neighborhood-guides/', '/neighborhood-guides/hamptons/',
                  '/neighborhood-guides/nyc/', '/sitemap/ca/', '/coming-soon/', '/private-exclusives/']:
        assert client.get(route).status_code == 200
    assert client.get('/neighborhood-guides/invalid/').status_code == 404
    assert client.get('/sitemap/not-a-state/').status_code == 404
    with m.app.app_context():
        assert before == [(row.id, row.property_facts_json) for row in m.Listing.query.order_by(m.Listing.id)]
        assert m.User.query.count() == users
        assert m.SavedHome.query.count() == m.Tour.query.count() == m.Inquiry.query.count() == 0
