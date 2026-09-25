"""Route + behavior robustness tests for the nfl mirror.

Every test runs against a scratch copy of the seed DB (see conftest.py), so
the real instance/ database is never touched and the byte-identical reset
invariant is preserved.
"""
import json
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parent.parent


def test_health_endpoint(client):
    response = client.get("/_health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["site"] == "nfl"
    assert payload["teams"] == 32
    assert payload["players"] > 2000
    assert payload["games"] == 272
    assert payload["news"] >= 80


def test_homepage_renders_upstream_chrome(client):
    html = client.get("/").get_data(as_text=True)
    for needle in (
        "GET MORE FOOTBALL WITH NFL+ PREMIUM",
        "Subscribe Now",
        "WEEK 3 SCOREBOARD",
        "NFL Football - Official Site",
        "© 2026 NFL Enterprises LLC",
        "Reject Optional Tracking",
    ):
        assert needle in html, f"homepage missing {needle!r}"
    assert html.count("/static/images/logos/") >= 32, "team logos missing from ribbon"


def test_scores_weeks(client):
    for week in (1, 2, 3, 18):
        response = client.get(f"/scores/2026/REG{week}/")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "2026 NFL SCORES" in body
    assert client.get("/scores/2026/REG19/").status_code == 404
    assert client.get("/scores/2026/REG0/").status_code == 404


def test_final_game_center_shows_quarters(client):
    response = client.get("/games/49ers-at-rams-2026-reg-1/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "SCORE BY QUARTER" in body
    assert "100021" in body, "international game attendance missing"
    assert "Melbourne Cricket Ground" in body


def test_upcoming_game_center_shows_preview(client):
    response = client.get("/games/falcons-at-packers-2026-reg-3/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "REGULAR SEASON AT A GLANCE" in body
    assert "INJURY REPORT" in body
    assert "Samson Ebukam" in body


def test_standings_all_divisions(client):
    response = client.get("/standings/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for division in ("AFC EAST", "AFC NORTH", "AFC SOUTH", "AFC WEST",
                     "NFC EAST", "NFC NORTH", "NFC SOUTH", "NFC WEST"):
        assert division in body, f"{division} table missing"


def test_every_team_page_and_roster(client):
    import app as app_module
    with app_module.app.app_context():
        from app import Team
        teams = Team.query.all()
    assert len(teams) == 32
    for team in teams:
        response = client.get(f"/teams/{team.slug}/")
        assert response.status_code == 200, team.slug
        body = response.get_data(as_text=True)
        assert team.full_name in body
        roster = client.get(f"/teams/{team.slug}/roster/")
        assert roster.status_code == 200
        assert "Apply Filters" in roster.get_data(as_text=True)


def test_roster_position_filter(client):
    response = client.get("/teams/green-bay-packers/roster/?position=WR")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Jayden Reed" in body
    assert "Jordan Love" not in body, "QB leaked into WR filter"


def test_player_directory_search_and_filters(client):
    response = client.get("/players/?query=mahomes")
    assert response.status_code == 200
    assert "Patrick Mahomes" in response.get_data(as_text=True)

    response = client.get("/players/?position=QB&team=KC")
    body = response.get_data(as_text=True)
    assert "Patrick Mahomes" in body
    assert "Travis Kelce" not in body, "TE leaked into QB filter"


def test_player_page_bio_and_stats(client):
    response = client.get("/players/patrick-mahomes/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for needle in ("Patrick Mahomes", "Texas Tech", "Kansas City Chiefs",
                   "Career Stats", "36505"):
        assert needle in body, f"player page missing {needle!r}"


def test_news_index_pagination_and_article(client):
    response = client.get("/news/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "NFL NEWS" in body
    assert "Page 1 of" in body
    page2 = client.get("/news/?page=2")
    assert page2.status_code == 200
    import app as app_module
    with app_module.app.app_context():
        from app import NewsArticle
        article = NewsArticle.query.order_by(NewsArticle.published.desc()).first()
    detail = client.get(f"/news/{article.slug}/")
    assert detail.status_code == 200
    assert article.title in detail.get_data(as_text=True)


def test_video_hub_channels_and_detail(client):
    for channel in ("latest-buzz", "game-highlights", "the-insiders", "good-morning-football"):
        response = client.get(f"/videos/channel/{channel}/")
        assert response.status_code == 200, channel
    assert client.get("/videos/channel/nope/").status_code == 404
    detail = client.get("/videos/falcons-vs-packers-week-3-tnf-preview-nfl-daily/")
    assert detail.status_code == 200
    assert "Falcons vs. Packers Week 3 TNF Preview" in detail.get_data(as_text=True)


def test_stats_categories(client):
    for slug, label in (
        ("passing", "PASSING"), ("rushing", "RUSHING"), ("receiving", "RECEIVING"),
        ("tackles", "TACKLES"), ("interceptions", "INTERCEPTIONS"),
        ("fumbles", "FUMBLES"), ("kickoffs", "KICKOFFS"),
        ("kickoff_returns", "KICKOFF RETURNS"), ("punting", "PUNTING"),
        ("punt_returns", "PUNT RETURNS"), ("field_goals", "FIELD GOALS"),
    ):
        response = client.get(f"/stats/{slug}/")
        assert response.status_code == 200, slug
        body = response.get_data(as_text=True)
        assert f"{label} LEADERS" in body
    assert client.get("/stats/not-a-stat/").status_code == 404


def test_injuries_and_transactions(client):
    response = client.get("/injuries/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "2026 NFL INJURY REPORT" in body
    assert "THURSDAY, SEPTEMBER 24TH" in body
    for cat in ("Signings", "Reserve List", "Waivers", "Terminations", "Other", "Trades"):
        response = client.get(f"/transactions/?category={cat}")
        assert response.status_code == 200, cat


def test_scored_search_not_strict_and(client):
    response = client.get("/search?q=Mahomes")
    body = response.get_data(as_text=True)
    assert "Patrick Mahomes" in body
    # multi-word, partial-token query must still return results
    response = client.get("/search?q=Chiefs Miami")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Kansas City Chiefs" in body or "Miami Dolphins" in body
    # garbage query renders empty state, not a crash
    response = client.get("/search?q=zzzznothing")
    assert response.status_code == 200
    assert "No results found" in response.get_data(as_text=True)


def test_plus_page_plans(client):
    response = client.get("/plus/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for price in ("$6.99", "$49.99", "$14.99", "$99.99"):
        assert price in body, f"missing plan price {price}"


def test_subscribe_requires_signin(client):
    response = client.get("/plus/subscribe/nfl_plus_premium_monthly/")
    assert response.status_code == 200
    assert "SIGN IN OR CREATE AN ACCOUNT" in response.get_data(as_text=True)
    posting = client.post(
        "/plus/subscribe/nfl_plus_premium_monthly/",
        data={"cardholder": "x", "card_number": "4242424242424242",
              "exp_month": "12", "exp_year": "2029", "cvv": "123"},
        follow_redirects=True,
    )
    assert "sign in or create an account" in posting.get_data(as_text=True).lower()


def test_subscribe_chain_happy_path(app):
    client = app.test_client()
    client.post("/account/signup/", data={
        "display_name": "Chain Tester", "email": "chain.t@example.com",
        "password": "Password123", "favorite_team": "KC",
    }, follow_redirects=True)
    response = client.post("/plus/subscribe/nfl_plus_premium_monthly/", data={
        "cardholder": "Chain Tester", "card_number": "4242424242424242",
        "exp_month": "12", "exp_year": "2029", "cvv": "123",
    }, follow_redirects=True)
    body = response.get_data(as_text=True)
    assert "THANK YOU FOR SUBSCRIBING" in body
    ref = re.search(r"NFL-[A-Z0-9]{6}", body)
    assert ref, "order reference missing"
    account = client.get("/account/").get_data(as_text=True)
    assert "NFL+ Premium Monthly" in account
    assert ref.group(0) in account, "order not in history"


def test_subscribe_rejects_bad_cards(app):
    client = app.test_client()
    client.post("/account/signup/", data={
        "display_name": "Bad Card", "email": "bad.card@example.com",
        "password": "Password123", "favorite_team": "",
    }, follow_redirects=True)
    for bad in (
        {"card_number": "1234567890123456"},  # luhn fail
        {"card_number": "424242424242424"},   # too short
        {"card_number": ""},                   # empty
    ):
        payload = {"cardholder": "Bad Card", "exp_month": "12",
                   "exp_year": "2029", "cvv": "123"}
        payload.update(bad)
        response = client.post(
            "/plus/subscribe/nfl_plus_annual/", data=payload, follow_redirects=True)
        body = response.get_data(as_text=True)
        assert "CHECKOUT" in body, "bad card should stay on checkout"
        assert "Enter a valid" in body or "failed validation" in body
    # bad expiry / cvv
    response = client.post("/plus/subscribe/nfl_plus_annual/", data={
        "cardholder": "Bad Card", "card_number": "4242424242424242",
        "exp_month": "13", "exp_year": "2029", "cvv": "12",
    }, follow_redirects=True)
    body = response.get_data(as_text=True)
    assert "valid expiration month" in body
    assert "3- or 4-digit" in body


def test_register_validation(app):
    duplicate = client = app.test_client()
    response = client.post("/account/signup/", data={
        "display_name": "Dup", "email": "alice.j@test.com", "password": "Password123",
    }, follow_redirects=True)
    assert "already exists" in response.get_data(as_text=True)
    response = client.post("/account/signup/", data={
        "display_name": "Short", "email": "short.pw@example.com", "password": "short",
    }, follow_redirects=True)
    assert "at least 8 characters" in response.get_data(as_text=True)


def test_login_bad_credentials(client):
    response = client.post("/account/signin/", data={
        "email": "alice.j@test.com", "password": "WrongPassword1",
    }, follow_redirects=True)
    assert "Email or password is incorrect" in response.get_data(as_text=True)


def test_account_requires_auth(client):
    response = client.get("/account/", follow_redirects=False)
    assert response.status_code == 302
    response = client.get("/account/", follow_redirects=True)
    assert "SIGN IN" in response.get_data(as_text=True)


def test_favorite_team_personalization(app):
    client = app.test_client()
    client.post("/account/signin/", data={
        "email": "alice.j@test.com", "password": "TestPass123!"}, follow_redirects=True)
    home_before = client.get("/").get_data(as_text=True)
    assert "MY TEAM" in home_before, "alice (KC fan) should see My Team module"
    client.post("/account/edit/", data={
        "display_name": "Alice Johnson", "favorite_team": "MIA", "newsletter": "on",
    }, follow_redirects=True)
    home_after = client.get("/").get_data(as_text=True)
    assert "Miami Dolphins" in home_after
    account = client.get("/account/").get_data(as_text=True)
    assert "Miami Dolphins" in account


def test_benchmark_user_fixture_state(bob):
    account = bob.get("/account/").get_data(as_text=True)
    assert "NFL+ Premium Monthly" in account
    assert "$14.99" in account
    assert "Renews" in account
    # bob's fixture has an active subscription but no prior order row
    assert "No NFL+ orders yet." in account


def test_benchmark_user_fixture_with_order(app):
    client = app.test_client()
    client.post("/account/signin/", data={
        "email": "carol.d@test.com", "password": "TestPass123!"}, follow_redirects=True)
    account = client.get("/account/").get_data(as_text=True)
    assert "NFL+ Annual" in account
    assert "NFL-03NUAL" in account, "carol's seeded order reference missing"


def test_newsletter_signup(client):
    response = client.post("/newsletter/", data={
        "email": "news.fan@example.com", "team": "KC",
    }, follow_redirects=True)
    assert "signed up for the NFL newsletter" in response.get_data(as_text=True)
    bad = client.post("/newsletter/", data={"email": "not-an-email"}, follow_redirects=True)
    assert "Enter a valid email" in bad.get_data(as_text=True)


def test_404_page(client):
    response = client.get("/games/no-such-game/")
    assert response.status_code == 404
    assert "404 - FLAG ON THE PLAY" in response.get_data(as_text=True)
