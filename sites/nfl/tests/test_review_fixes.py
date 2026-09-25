from flask.testing import FlaskClient
import re

def test_rejects_missing_csrf(app):
    c = FlaskClient(app)
    assert c.post("/account/signin/", data={"email":"bob.c@test.com", "password":"TestPass123!"}).status_code == 400


def test_redirect_remains_local(client):
    r = client.post("/account/signin/?next=https://example.org/", data={"email":"bob.c@test.com", "password":"TestPass123!"})
    assert r.status_code == 302
    assert r.headers["Location"].startswith("/account")

def test_expired_card_and_repeat_purchase(client):
    client.post("/account/signin/", data={"email":"bob.c@test.com", "password":"TestPass123!"})
    data={"cardholder":"Bob Chen", "card_number":"4242424242424242", "exp_month":"01", "exp_year":"2001", "cvv":"123"}
    r=client.post("/plus/subscribe/nfl_plus_premium_annual/", data=data)
    assert b"expired" in r.data and r.status_code == 200
    data.update(exp_year="2029", exp_month="12")
    first=client.post("/plus/subscribe/nfl_plus_premium_annual/",data=data)
    second=client.post("/plus/subscribe/nfl_plus_premium_annual/",data=data)
    assert first.status_code == second.status_code == 302
    assert first.headers["Location"] != second.headers["Location"]
    assert client.get(second.headers["Location"]).status_code == 200
