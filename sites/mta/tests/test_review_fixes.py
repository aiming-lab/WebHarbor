from flask.testing import FlaskClient
import re

def test_rejects_missing_csrf(app):
    c = FlaskClient(app)
    assert c.post("/account/login", data={"email":"bob.c@test.com", "password":"TestPass123!"}).status_code == 400


def test_redirect_remains_local(client):
    r = client.post("/account/login?next=https://example.org/", data={"email":"bob.c@test.com", "password":"TestPass123!"})
    assert r.status_code == 302
    assert r.headers["Location"].startswith("/account")

def test_invalid_trip_cannot_be_saved(client):
    client.post("/account/login",data={"email":"carol.d@test.com","password":"TestPass123!"})
    r=client.post("/accessibility/access-a-ride/book",data={"pickup":"Home","destination":"Hospital","date":"bad","time":"99:99","passengers":"-1","mobility_aid":"spaceship"})
    assert r.status_code == 400
    assert b"valid trip date" in r.data
    assert b"valid pickup time" in r.data


def test_omny_combined_cap_includes_local_rides(client):
    client.post("/account/login",data={"email":"bob.c@test.com","password":"TestPass123!"})
    r=client.get("/account/omny")
    assert b"$31.25 of $67.00" in r.data


def test_invalid_favorite_rejected(client):
    client.post("/account/login",data={"email":"bob.c@test.com","password":"TestPass123!"})
    r=client.post("/account/favorites",data={"service_type":"rail","service_id":"Imaginary line"})
    assert r.status_code == 400


def test_related_guides_are_reachable(client):
    assert b'href="/guides/bikes/bike-regulations-lirr"' in client.get('/guides/bikes').data
    assert b'href="/transparency/leadership/board-members"' in client.get('/transparency').data
