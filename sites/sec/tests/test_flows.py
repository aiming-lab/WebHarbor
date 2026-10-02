"""Flow tests: auth, watchlist, complaint/tip/question intake, email
signup, CSRF enforcement — all with CSRF protection enabled and real
tokens submitted like a browser."""
import re

from conftest import with_csrf


class TestAuth:
    def test_login_success(self, client):
        data = with_csrf(client, "/login", {"email": "alice.j@test.com",
                                            "password": "TestPass123!"})
        r = client.post("/login", data=data)
        assert r.status_code in (302, 303)

    def test_login_failure(self, client):
        data = with_csrf(client, "/login", {"email": "alice.j@test.com",
                                            "password": "WrongPass999!"})
        r = client.post("/login", data=data)
        assert r.status_code == 200
        assert b"Invalid email or password" in r.data

    def test_signup_flow(self, client):
        data = with_csrf(client, "/signup", {
            "name": "Flow Tester", "email": "flow.tester@test.com",
            "password": "LongPass123!"})
        r = client.post("/signup", data=data)
        assert r.status_code in (302, 303)

    def test_duplicate_signup_rejected(self, client):
        data = with_csrf(client, "/signup", {
            "name": "Dup", "email": "alice.j@test.com",
            "password": "LongPass123!"})
        r = client.post("/signup", data=data)
        assert b"already exists" in r.data

    def test_short_password_rejected(self, client):
        data = with_csrf(client, "/signup", {
            "name": "Short", "email": "short.pw@test.com", "password": "short"})
        r = client.post("/signup", data=data)
        assert b"at least 8" in r.data

    def test_account_requires_login(self, client):
        r = client.get("/account")
        assert r.status_code in (302, 303)

    def test_logout(self, alice_client):
        r = alice_client.get("/logout")
        assert r.status_code in (302, 303)


class TestWatchlist:
    def test_alice_fixture_state(self, alice_client):
        r = alice_client.get("/account")
        html = r.data.decode()
        assert "Apple Inc." in html and "MICROSOFT CORP" in html
        assert "2 companies on your watchlist" in html

    def test_bob_fixture_state(self, bob_client):
        r = bob_client.get("/account")
        html = r.data.decode()
        assert "Tesla" in html and "NVIDIA" in html

    def test_watchlist_toggle_add_remove(self, client):
        data = with_csrf(client, "/login", {"email": "carol.d@test.com",
                                            "password": "TestPass123!"})
        client.post("/login", data=data)
        # Carol starts with Amazon
        r = client.get("/account")
        assert "2 companies" not in r.data.decode()
        assert "1 company on your watchlist" in r.data.decode()
        # add Apple from its company page
        data = with_csrf(client, "/edgar/company/0000320193",
                         {"cik": "0000320193", "back": "/account"})
        r = client.post("/account/watchlist/toggle", data=data)
        assert r.status_code in (302, 303)
        r = client.get("/account")
        assert "2 companies on your watchlist" in r.data.decode()
        # remove Apple again
        data = with_csrf(client, "/edgar/company/0000320193",
                         {"cik": "0000320193", "back": "/account"})
        client.post("/account/watchlist/toggle", data=data)
        r = client.get("/account")
        assert "1 company on your watchlist" in r.data.decode()

    def test_watchlist_unknown_company_rejected(self, alice_client):
        data = with_csrf(alice_client, "/edgar/company/0000320193",
                         {"cik": "9999999999", "back": "/account"})
        r = alice_client.post("/account/watchlist/toggle", data=data)
        assert r.status_code == 400

    def test_watchlist_button_reflects_state(self, alice_client):
        r = alice_client.get("/edgar/company/0000320193")
        assert b"Remove from Watchlist" in r.data
        r = alice_client.get("/edgar/company/0001318605")
        assert b"Add to Watchlist" in r.data


class TestComplaintFlow:
    def test_complaint_full_flow(self, client):
        data = with_csrf(client, "/login", {"email": "alice.j@test.com",
                                            "password": "TestPass123!"})
        client.post("/login", data=data)
        data = with_csrf(
            client,
            "/submit-tip-or-complaint/report-problem-investment-account-or-financial-professional",
            {"name": "Alice Johnson", "email": "alice.j@test.com",
             "your_role": "individual investor",
             "issue_type": "unauthorized trading",
             "subject_firm": "Granite Wealth Management",
             "subject_person": "T. Brooks", "subject_ticker": "GRW",
             "address": "88 Federal Ave, Boston, MA", "phone": "617-555-0199",
             "details": "Purchases appeared in my account without my approval in July 2026."})
        r = client.post("/submit-tip-or-complaint/"
                        "report-problem-investment-account-or-financial-professional",
                        data=data)
        assert r.status_code in (302, 303)
        location = r.headers.get("Location", "")
        m = re.search(r"/complaint-confirmation/(IC-[A-Z0-9]+)", location)
        assert m, location
        r = client.get(location)
        assert r.status_code == 200
        assert m.group(1).encode() in r.data
        assert b"Granite Wealth Management" in r.data
        # shows up in the account history
        r = client.get("/account")
        assert b"Granite Wealth Management" in r.data

    def test_complaint_validation(self, client):
        data = with_csrf(
            client,
            "/submit-tip-or-complaint/report-problem-investment-account-or-financial-professional",
            {"name": "", "email": "not-an-email", "your_role": "",
             "issue_type": "", "subject_firm": ""})
        r = client.post("/submit-tip-or-complaint/"
                        "report-problem-investment-account-or-financial-professional",
                        data=data)
        assert r.status_code == 400
        assert b"Enter your full name" in r.data

    def test_alice_fixture_complaint_visible(self, alice_client):
        r = alice_client.get("/account")
        assert b"IC-8F2A91C7" in r.data
        assert b"Meridian Brokerage Services LLC" in r.data


class TestTipFlow:
    def test_tip_full_flow(self, client):
        data = with_csrf(
            client,
            "/submit-tip-or-complaint/report-possible-securities-law-violations",
            {"name": "Deep Throat", "email": "deep.throat@example.com",
             "violation_type": "market manipulation",
             "subject_firm": "Vortex Trading LLC",
             "subject_person": "K. Munn", "subject_ticker": "VRTX",
             "market": "equities",
             "details": "I watched the desk run repeated wash trades on the "
                        "close in May 2026 to move the price."})
        r = client.post("/submit-tip-or-complaint/"
                        "report-possible-securities-law-violations", data=data)
        assert r.status_code in (302, 303)
        location = r.headers.get("Location", "")
        m = re.search(r"/confirmation/(TCR-[A-Z0-9]+)", location)
        assert m, location
        r = client.get(location)
        assert r.status_code == 200
        assert m.group(1).encode() in r.data

    def test_tip_validation(self, client):
        data = with_csrf(
            client,
            "/submit-tip-or-complaint/report-possible-securities-law-violations",
            {"name": "X", "email": "x@x.io", "violation_type": "",
             "details": "short"})
        r = client.post("/submit-tip-or-complaint/"
                        "report-possible-securities-law-violations", data=data)
        assert r.status_code == 400
        assert b"Select the type of possible violation" in r.data
        assert b"at least 30" in r.data

    def test_bob_fixture_tip_visible(self, bob_client):
        r = bob_client.get("/account")
        assert b"TCR-3D61B0E5" in r.data
        assert b"Halcyon Dynamics Corp" in r.data


class TestQuestionFlow:
    def test_question_full_flow(self, client):
        data = with_csrf(
            client,
            "/submit-tip-or-complaint/report-problem-sec-or-self-regulatory-organization",
            {"name": "Curious Investor", "email": "curious@example.com",
             "topic": "mutual funds or ETFs",
             "question": "Where can I find a fund's annual report on EDGAR?"})
        r = client.post("/submit-tip-or-complaint/"
                        "report-problem-sec-or-self-regulatory-organization",
                        data=data)
        assert r.status_code in (302, 303)
        location = r.headers.get("Location", "")
        m = re.search(r"/question-confirmation/(Q-[A-Z0-9]+)", location)
        assert m, location
        r = client.get(location)
        assert r.status_code == 200
        assert m.group(1).encode() in r.data

    def test_question_validation(self, client):
        data = with_csrf(
            client,
            "/submit-tip-or-complaint/report-problem-sec-or-self-regulatory-organization",
            {"name": "", "email": "bad", "topic": "", "question": ""})
        r = client.post("/submit-tip-or-complaint/"
                        "report-problem-sec-or-self-regulatory-organization",
                        data=data)
        assert r.status_code == 400


class TestSubscribe:
    def test_subscribe_flow(self, client):
        data = with_csrf(client, "/", {"email": "news.fan@example.com",
                                       "topics": ["press releases"]})
        r = client.post("/subscribe", data=data)
        assert r.status_code == 200
        assert b"now subscribed" in r.data

    def test_subscribe_duplicate(self, client):
        data = with_csrf(client, "/", {"email": "dup.sub@example.com"})
        client.post("/subscribe", data=data)
        data = with_csrf(client, "/", {"email": "dup.sub@example.com"})
        r = client.post("/subscribe", data=data)
        assert b"already subscribed" in r.data

    def test_subscribe_bad_email(self, client):
        data = with_csrf(client, "/", {"email": "not-an-email"})
        r = client.post("/subscribe", data=data)
        assert r.status_code == 400


class TestCsrfEnforcement:
    def test_unsigned_login_post_rejected(self, client):
        r = client.post("/login", data={"email": "alice.j@test.com",
                                        "password": "TestPass123!"})
        assert r.status_code == 400

    def test_unsigned_complaint_post_rejected(self, client):
        r = client.post("/submit-tip-or-complaint/"
                        "report-problem-investment-account-or-financial-professional",
                        data={"name": "x"})
        assert r.status_code == 400

    def test_unsigned_tip_post_rejected(self, client):
        r = client.post("/submit-tip-or-complaint/"
                        "report-possible-securities-law-violations",
                        data={"name": "x"})
        assert r.status_code == 400

    def test_unsigned_watchlist_post_rejected(self, alice_client):
        r = alice_client.post("/account/watchlist/toggle",
                              data={"cik": "0000320193"})
        assert r.status_code == 400
