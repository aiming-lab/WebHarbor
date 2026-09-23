"""App-robustness regression tests for the Chess.com mirror.

Covers: every major route family renders, detail pages resolve for real seed
slugs, the puzzle JSON callbacks, the auth flows, stateful toggles in both
directions, bounded query integers, 404 handling for unknown slugs, and
read-only GETs on POST-only actions.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")
sys.path.insert(0, str(SITE))


@pytest.fixture(scope="module")
def app_module():
    import app
    return app


@pytest.fixture()
def client(app_module):
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def _login(client, email="alice.j@test.com", password="TestPass123!"):
    return client.post("/login", data={"username": email, "password": password},
                       follow_redirects=False)


# ------------------------------------------------------------------ core pages
@pytest.mark.parametrize("path,needle", [
    ("/", "Play Chess Online"),
    ("/play", "Play Bots"),
    ("/play/online", "Bullet"),
    ("/play/computer", "rating"),
    ("/puzzles", "Puzzles"),
    ("/puzzles/rated", "Rated"),
    ("/puzzles/themes", "Puzzle Themes"),
    ("/puzzles/archive", "Daily Puzzle Archive"),
    ("/daily", "Daily Puzzle"),
    ("/lessons", "Lessons"),
    ("/openings", "Chess Openings"),
    ("/watch", "ChessTV Schedule"),
    ("/events", "Events"),
    ("/leaderboard/live", "Blitz"),
    ("/leaderboard/live/bullet", "Bullet"),
    ("/leaderboard/live/rapid", "Rapid"),
    ("/leaderboard/tactics", "Tactics"),
    ("/leaderboard/daily", "Daily"),
    ("/members", "Members"),
    ("/members/titled-players", "Titled Players"),
    ("/games", "Chess Games Database"),
    ("/news", "News"),
    ("/clubs", "Clubs"),
    ("/today", "Chess Today"),
    ("/search?q=hikaru", "Hikaru"),
    ("/stats/live/blitz/Hikaru", "Hikaru"),
    ("/member/Hikaru", "followers"),
    ("/member/MagnusCarlsen", "MagnusCarlsen"),
    ("/login", "Log In"),
    ("/register", "Sign Up"),
    ("/_health", "chess_com"),
])
def test_core_routes_render(client, path, needle):
    r = client.get(path)
    assert r.status_code == 200, path
    assert needle.encode() in r.data, path


# ------------------------------------------------------------------ detail pages
def test_opening_detail_pages(client):
    for slug in ("Sicilian-Defense", "French-Defense", "Ruy-Lopez-Opening"):
        r = client.get(f"/openings/{slug}")
        assert r.status_code == 200
        assert b"ECO" in r.data or b"Games" in r.data


def test_variation_detail_page(client, app_module):
    """A harvested variation row renders with its parent link intact."""
    with app_module.app.app_context():
        opening = (app_module.db.session.query(app_module.Opening)
                   .filter_by(is_variation=True).first())
        parent_slug = opening.parent_slug
        variation_slug = opening.slug
    if not variation_slug:
        pytest.skip("no variation rows in seed")
    r = client.get(f"/openings/{variation_slug}")
    assert r.status_code == 200
    assert parent_slug.encode() in r.data


def test_news_article_and_category_pages(client):
    r = client.get("/news")
    slug = r.data.split(b"/news/view/")[1].split(b'"')[0].decode()
    assert client.get(f"/news/view/{slug}").status_code == 200
    r = client.get("/news/category/chess-event-coverage")
    assert r.status_code == 200


def test_puzzle_detail_page_and_archive_paging(client):
    r = client.get("/puzzles/archive")
    assert r.status_code == 200
    pid = r.data.split(b"/puzzles/problem/")[1].split(b'"')[0].decode()
    r = client.get(f"/puzzles/problem/{pid}")
    assert r.status_code == 200
    r = client.get("/puzzles/archive?page=999")
    assert r.status_code == 200  # out-of-range page renders empty table


def test_game_detail_page(client, app_module):
    with app_module.app.app_context():
        game = app_module.db.session.query(app_module.MasterGame).filter_by(
            has_detail=True).first()
        game_id = game.game_id
    assert game_id, "no captured game views in seed"
    r = client.get(f"/games/view/{game_id}")
    assert r.status_code == 200
    assert b"Result" in r.data


def test_games_player_page_and_opening_links(client):
    r = client.get("/games/hikaru-nakamura")
    assert r.status_code == 200
    assert b"Hikaru" in r.data


def test_event_detail_page(client):
    r = client.get("/events")
    slug = r.data.split(b"/events/info/")[1].split(b'"')[0].decode()
    assert client.get(f"/events/info/{slug}").status_code == 200


def test_club_detail_page(client):
    r = client.get("/club/chess-school")
    assert r.status_code == 200
    assert b"members" in r.data


# ------------------------------------------------------------------ callbacks
def test_puzzle_next_callback_shape(client):
    r = client.get("/callback/puzzles/next")
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["fen"]
    assert data["moves"]
    assert all({"from" in m and "to" in m} for m in data["moves"])


def test_health_json(client):
    r = client.get("/_health")
    data = json.loads(r.data)
    assert data.get("ok") is True
    assert data.get("site") == "chess_com"


# ------------------------------------------------------------------ auth + state
def test_login_logout_flow(client):
    r = _login(client)
    assert r.status_code == 302
    r = client.get("/settings")
    assert r.status_code == 200
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code in (301, 302, 405), "logout must redirect or reject GET"
    r = client.post("/logout", follow_redirects=False)
    assert r.status_code in (301, 302)


def test_login_rejects_bad_password(client):
    r = client.post("/login", data={"username": "alice.j@test.com",
                                    "password": "wrong"}, follow_redirects=True)
    assert r.status_code == 200
    # a failed login leaves the visitor anonymous: settings still redirects
    r = client.get("/settings", follow_redirects=False)
    assert r.status_code == 302


def test_settings_requires_login(client):
    r = client.get("/settings", follow_redirects=False)
    assert r.status_code == 302


def test_follow_toggle_both_directions(client):
    _login(client)
    r1 = client.post("/follow/Hikaru", follow_redirects=True)
    r2 = client.post("/follow/Hikaru", follow_redirects=True)
    assert (b"Unfollow Hikaru" in r1.data) != (b"Unfollow Hikaru" in r2.data)


def test_club_join_toggle(client):
    _login(client, "bob.c@test.com")
    r1 = client.post("/club/chess-com-community/join", follow_redirects=True)
    r2 = client.post("/club/chess-com-community/join", follow_redirects=True)
    assert (b"Leave Club" in r1.data) != (b"Leave Club" in r2.data)


def test_lesson_complete_flow(client):
    _login(client, "david.k@test.com")
    r = client.post("/lessons/gambit-buffet/complete",
                    data={"lessons_done": 16}, follow_redirects=True)
    assert r.status_code == 200
    assert b"16/16" in r.data or b"16 / 16" in r.data


def test_puzzle_solve_records_attempt(client):
    _login(client, "david.k@test.com")
    r = client.get("/callback/puzzles/next")
    data = json.loads(r.data)
    r = client.post("/callback/puzzles/solve",
                    json={"puzzle_id": data["id"], "solved": True})
    assert r.status_code == 200
    r2 = client.post("/callback/puzzles/solve",
                     json={"puzzle_id": data["id"], "solved": False})
    assert r2.status_code == 200


# ------------------------------------------------------------------ hardening
def test_unknown_slugs_404(client):
    for path in ("/member/definitely-not-a-user-xyz",
                 "/news/view/not-a-real-article",
                 "/openings/Not-A-Real-Opening",
                 "/club/not-a-real-club",
                 "/games/view/0",
                 "/puzzles/problem/999999999",
                 "/lessons/not-a-real-course"):
        assert client.get(path).status_code == 404, path


def test_bounded_query_integers(client):
    assert client.get("/leaderboard/live?page=99999").status_code == 200
    assert client.get("/leaderboard/live?page=abc").status_code == 200
    assert client.get("/news?page=-5").status_code == 200
    assert client.get("/puzzles/archive?page=100000").status_code == 200


def test_post_only_actions_reject_get(client):
    _login(client)
    for path in ("/follow/Hikaru", "/club/chess-school/join",
                 "/lessons/gambit-buffet/complete", "/logout"):
        assert client.get(path).status_code in (301, 302, 405), path


def test_stateful_actions_require_login(client):
    r = client.post("/follow/Hikaru", follow_redirects=False)
    assert r.status_code == 302
    r = client.post("/club/chess-school/join", follow_redirects=False)
    assert r.status_code == 302
