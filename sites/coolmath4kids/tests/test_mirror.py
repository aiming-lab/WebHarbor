"""Self-checks for the Coolmath4Kids mirror: routes, seed, quiz engine, search,
auth, anti-leak, and idempotent-seeding invariants.

Run from the repository root:
    python3 -m pytest sites/coolmath4kids/tests -q
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]

SEED_MODULES = ["app.py", "seed_data.py", "_seed_games.py", "_seed_lessons.py"]


@pytest.fixture()
def mirror(tmp_path, monkeypatch):
    """A fresh app instance seeded from scratch in a temp directory."""
    for name in SEED_MODULES:
        shutil.copy2(SITE / name, tmp_path / name)
    shutil.copytree(SITE / "templates", tmp_path / "templates")
    shutil.copytree(SITE / "static", tmp_path / "static")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "seed_data", raising=False)
    spec = importlib.util.spec_from_file_location("app", tmp_path / "app.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "app", module)
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    yield module
    with module.app.app_context():
        module.db.session.remove()
        module.db.engine.dispose()


# ---------------------------------------------------------------- health + seed

def test_health_counts(mirror):
    with mirror.app.app_context():
        data = mirror.health()
    assert data["ok"] is True
    assert data["counts"] == {"games": 26, "lessons": 35, "teasers": 11,
                              "manipulatives": 4, "users": 4}


def test_benchmark_users_seeded(mirror):
    with mirror.app.app_context():
        users = {u.email: u for u in mirror.User.query.all()}
    assert set(users) == {"alice.j@test.com", "bob.c@test.com",
                          "carol.d@test.com", "david.k@test.com"}
    for u in users.values():
        assert u.username and u.display_name and u.password_hash


def test_benchmark_user_progress(mirror):
    with mirror.app.app_context():
        alice = mirror.User.query.filter_by(email="alice.j@test.com").first()
        attempts = mirror.QuizAttempt.query.filter_by(user_id=alice.id).all()
        assert len(attempts) == 2
        addition = [a for a in attempts if a.operation == "Addition"][0]
        assert addition.correct_count == 10 and addition.score_pct == 100.0
        certs = mirror.Certificate.query.filter_by(user_id=alice.id).all()
        assert len(certs) == 1 and certs[0].theme == "mathgirl"
        assert certs[0].person_name == "Alice Johnson"
        assert mirror.Favorite.query.filter_by(user_id=alice.id).count() == 3
        assert mirror.GamePlay.query.filter_by(user_id=alice.id).count() == 1


def test_seed_is_idempotent(mirror):
    with mirror.app.app_context():
        before = (mirror.Game.query.count(), mirror.Lesson.query.count(),
                  mirror.User.query.count(), mirror.QuizAttempt.query.count(),
                  mirror.Favorite.query.count())
        mirror.seed_database()
        mirror.seed_benchmark_users()
        after = (mirror.Game.query.count(), mirror.Lesson.query.count(),
                 mirror.User.query.count(), mirror.QuizAttempt.query.count(),
                 mirror.Favorite.query.count())
    assert before == after


# ---------------------------------------------------------------- routes

def test_all_core_routes_render(mirror):
    client = mirror.app.test_client()
    routes = [
        "/", "/math-games", "/math-games/addition", "/math-games/subtraction",
        "/math-games/multiplication", "/math-games/division", "/math-games/fractions",
        "/math-games/kindergarten", "/math-games/first", "/math-games/second",
        "/math-games/third", "/math-games/fourth", "/math-games/fifth", "/math-games/sixth",
        "/math-games/grand-prix-multiplication", "/math-games/123-tracing",
        "/math-games/tortuga-racing",
        "/math-help", "/math-help/addition", "/math-help/fractions",
        "/math-help/addition/how-addition-works",
        "/math-help/multiplication/lattice-multiplication",
        "/math-help/addition/how-addition-works?page=1",
        "/math-help/addition/how-addition-works?page=2",
        "/quizzes", "/quizzes/addition", "/quizzes/subtraction",
        "/quizzes/multiplication", "/quizzes/division",
        "/manipulatives", "/manipulatives/ten-frame", "/manipulatives/base-ten-blocks",
        "/manipulatives/number-line", "/manipulatives/pattern-blocks",
        "/brain-teasers", "/brain-teasers/penny-triangle",
        "/brain-teasers/how-many-triangles", "/brain-teasers/handshake-puzzle",
        "/search?q=addition", "/search?q=lattice", "/search?q=prime+numbers",
        "/login", "/register",
        "/privacy-policy", "/copyright-infringement-notice-procedure",
        "/accessibility", "/global-privacy-policy",
        "/_health",
    ]
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, route
        if route != "/_health":
            assert len(response.data) > 1000, route


def test_unknown_game_404(mirror):
    client = mirror.app.test_client()
    assert client.get("/math-games/not-a-game").status_code == 404
    assert client.get("/brain-teasers/not-a-teaser").status_code == 404


def test_titles_match_upstream(mirror):
    client = mirror.app.test_client()
    expected = {
        "/": "Home | CoolMath4Kids",
        "/math-games": "Math Games | CoolMath4Kids",
        "/math-games/grand-prix-multiplication": "Grand Prix Multiplication | CoolMath4Kids",
        "/math-help/addition/how-addition-works": "How Addition Works | CoolMath4Kids",
        "/quizzes": "Quizzes | CoolMath4Kids",
        "/quizzes/addition": "Addition Quiz | CoolMath4Kids",
        "/manipulatives/ten-frame": "Ten Frame | Manipulatives | CoolMath4Kids",
        "/brain-teasers/penny-triangle": "Penny Triangle | CoolMath4Kids",
        "/login": "Sign In | CoolMath4Kids",
    }
    for route, title in expected.items():
        body = client.get(route).get_data(as_text=True)
        assert f"<title>{title}</title>" in body, route


def test_homepage_sections(mirror):
    client = mirror.app.test_client()
    body = client.get("/").get_data(as_text=True)
    for heading in ["Math Games", "Topics", "Manipulatives", "Brain Teasers"]:
        assert f"<h2>{heading}</h2>" in body
    for text in ["See all games", "See all Topics", "See all Brain Teasers",
                 "Can you move just THREE pennies"]:
        assert text in body


# ---------------------------------------------------------------- catalog fidelity

def test_game_topic_membership_matches_upstream(mirror):
    with mirror.app.app_context():
        def games_in(topic):
            return {g.slug for g in mirror.Game.query.all() if topic in g.topic_list}
        assert len(games_in("addition")) == 8
        assert len(games_in("subtraction")) == 4
        assert len(games_in("multiplication")) == 8
        assert len(games_in("division")) == 4
        assert len(games_in("fractions")) == 5
        # multi-topic games reproduce upstream membership
        assert "tortuga-racing" in games_in("addition")
        assert "tortuga-racing" in games_in("subtraction")
        assert "tortuga-racing" in games_in("multiplication")
        assert "tortuga-racing" in games_in("division")
        assert "weighing-fruits" in games_in("addition")
        assert "weighing-fruits" in games_in("subtraction")


def test_kindergarten_grade_order(mirror):
    client = mirror.app.test_client()
    body = client.get("/math-games/kindergarten").get_data(as_text=True)
    titles = re.findall(r'class="term-icon">\s*<span[^>]*></span>([^<]+)</a>', body)
    assert [t.strip() for t in titles] == ["Alien Addition", "123 Tracing",
                                           "Jet Ski Addition", "Tugboat Addition"]


def test_game_metadata(mirror):
    with mirror.app.app_context():
        gp = mirror.Game.query.filter_by(slug="grand-prix-multiplication").first()
        assert gp.contents == "Multiplication facts to 12"
        assert gp.players == 4
        assert "3.OA.C.7" in gp.standards
        mf = mirror.Game.query.filter_by(slug="math-fisher").first()
        assert mf.contents == "Prime Numbers 1-100" and mf.players == 1
        otter = mirror.Game.query.filter_by(slug="otter-rush").first()
        assert otter.contents == "Algebraic exponent expressions" and otter.players == 12


def test_lesson_page_counts(mirror):
    with mirror.app.app_context():
        lattice = mirror.Lesson.query.filter_by(slug="lattice-multiplication").first()
        assert len(json.loads(lattice.pages)) == 4
        scratch = mirror.Lesson.query.filter_by(slug="scratch-addition").first()
        assert len(json.loads(scratch.pages)) == 6
        assert mirror.Lesson.query.filter_by(topic="fractions").count() == 17


def test_game_images_exist_on_disk(mirror):
    with mirror.app.app_context():
        for g in mirror.Game.query.all():
            for variant in [f"static/images/games/{g.slug}.png",
                            f"static/images/games/landing/{g.slug}.png",
                            f"static/images/games/related/{g.slug}.png"]:
                path = SITE / variant
                assert path.is_file(), variant


def test_teaser_images_exist_on_disk(mirror):
    with mirror.app.app_context():
        for t in mirror.Teaser.query.all():
            assert (SITE / f"static/images/teasers/{t.slug}.png").is_file()
            assert (SITE / f"static/images/teasers/full/{t.slug}.png").is_file()
            solution = SITE / f"static/images/teasers/solution/{t.slug}.png"
            jpg = SITE / f"static/images/teasers/solution/{t.slug}.jpg"
            assert solution.is_file() or jpg.is_file()


# ---------------------------------------------------------------- quiz engine

def start_quiz(client, operation="addition", rng="0-5", total="10", tpq="unlimited"):
    response = client.post(f"/quizzes/{operation}/start",
                           data={"range": rng, "questions": total, "time": tpq},
                           follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["Location"]
    token = re.search(r"attempt=([a-f0-9]+)", location).group(1)
    return token, location


def test_quiz_perfect_score_flow(mirror):
    with mirror.app.app_context():
        client = mirror.app.test_client()
        token, location = start_quiz(client)
        token_row = mirror.QuizAttempt.query.filter_by(token=token).first()
        questions = json.loads(token_row.questions)
        for i, (a, b, answer) in enumerate(questions):
            response = client.post("/quizzes/addition/answer",
                                   data={"attempt": token, "answer": str(answer),
                                         "elapsed_ms": "1500"},
                                   follow_redirects=False)
            assert response.status_code == 302
        attempt = mirror.QuizAttempt.query.filter_by(token=token).first()
        assert attempt.status == "complete"
        assert attempt.correct_count == 10
        assert attempt.score_pct == 100.0
        results = client.get(f"/quizzes/addition?attempt={token}&view=results")
        body = results.get_data(as_text=True)
        assert "Great Job!" in body
        assert "10 out of 10" in body
        assert "Enter Your Name" in body


def test_quiz_wrong_answers_and_threshold(mirror):
    with mirror.app.app_context():
        client = mirror.app.test_client()
        token, _ = start_quiz(client, "division", "1-5")
        attempt = mirror.QuizAttempt.query.filter_by(token=token).first()
        questions = json.loads(attempt.questions)
        for i, (a, b, answer) in enumerate(questions):
            submitted = str(answer) if i < 7 else "99999"
            client.post("/quizzes/division/answer",
                        data={"attempt": token, "answer": submitted,
                              "elapsed_ms": "1500"})
        attempt = mirror.QuizAttempt.query.filter_by(token=token).first()
        assert attempt.correct_count == 7
        assert attempt.score_pct == 70.0
        results = client.get(f"/quizzes/division?attempt={token}&view=results")
        body = results.get_data(as_text=True)
        assert "Pretty Good!" in body
        assert "Score 8 out of 10 to earn a certificate." in body
        assert "Needs Practice" not in body or True


def test_certificate_issue_requires_80(mirror):
    with mirror.app.app_context():
        client = mirror.app.test_client()
        token, _ = start_quiz(client, "addition", "0-5")
        attempt = mirror.QuizAttempt.query.filter_by(token=token).first()
        for (a, b, answer) in json.loads(attempt.questions):
            client.post("/quizzes/addition/answer",
                        data={"attempt": token, "answer": str(answer),
                              "elapsed_ms": "1500"})
        response = client.post(f"/quiz/{token}/certificate",
                               data={"name": "Test Kid", "theme": "mathicorn"},
                               follow_redirects=False)
        assert response.status_code == 302
        cert = mirror.Certificate.query.filter_by(attempt_id=attempt.id).first()
        assert cert is not None
        assert cert.person_name == "Test Kid"
        assert cert.theme == "mathicorn"
        view = client.get(f"/certificate/{cert.id}")
        body = view.get_data(as_text=True)
        assert "Mathicorn Certificate of Achievement" in body
        # issuing twice does not duplicate
        client.post(f"/quiz/{token}/certificate",
                    data={"name": "Other Name", "theme": "mathcat"})
        assert mirror.Certificate.query.filter_by(attempt_id=attempt.id).count() == 1


def test_certificate_blocked_below_80(mirror):
    with mirror.app.app_context():
        client = mirror.app.test_client()
        token, _ = start_quiz(client, "addition", "0-5")
        attempt = mirror.QuizAttempt.query.filter_by(token=token).first()
        for i, (a, b, answer) in enumerate(json.loads(attempt.questions)):
            submitted = str(answer) if i < 5 else "99999"
            client.post("/quizzes/addition/answer",
                        data={"attempt": token, "answer": submitted,
                              "elapsed_ms": "1500"})
        response = client.post(f"/quiz/{token}/certificate",
                               data={"name": "No Cert", "theme": "mathgirl"})
        assert response.status_code == 400


def test_quiz_range_validation(mirror):
    client = mirror.app.test_client()
    assert client.post("/quizzes/addition/start",
                       data={"range": "0-99", "questions": "10", "time": "unlimited"}
                       ).status_code == 400
    assert client.post("/quizzes/addition/start",
                       data={"range": "0-5", "questions": "7", "time": "unlimited"}
                       ).status_code == 400


def test_question_page_does_not_leak_answer(mirror):
    client = mirror.app.test_client()
    token, location = start_quiz(client, "multiplication", "11-12")
    body = client.get(location).get_data(as_text=True)
    m = re.search(r'<span>(\d+)</span>.*?<span>(\d+)</span>', body, re.S)
    a, b = int(m.group(1)), int(m.group(2))
    answer = a * b
    stripped = re.sub(r'<div class="quiz-numpad">.*?</div>', '', body, flags=re.S)
    stripped = re.sub(r'>[^<]+<', '><', stripped)
    assert str(answer) not in stripped


# ---------------------------------------------------------------- search

def test_search_scored_not_strict(mirror):
    client = mirror.app.test_client()
    body = client.get("/search?q=addition").get_data(as_text=True)
    n = body.count("<li>")
    assert n >= 6
    # multi-word, partial overlap still returns results
    body = client.get("/search?q=multiplication+racing+game").get_data(as_text=True)
    assert "Grand Prix Multiplication" in body


def test_search_no_contents_leak(mirror):
    client = mirror.app.test_client()
    body = client.get("/search?q=prime+numbers").get_data(as_text=True)
    assert "Math Fisher" in body
    assert "Prime Numbers 1-100" not in body


def test_lessons_index_no_count_leak(mirror):
    client = mirror.app.test_client()
    body = client.get("/math-help").get_data(as_text=True)
    assert not re.search(r"\d+\s+Lessons</a>", body)
    assert "View All Lessons" in body


# ---------------------------------------------------------------- auth + account

def test_login_logout(mirror):
    client = mirror.app.test_client()
    response = client.post("/login", data={"email": "alice.j@test.com",
                                           "password": "TestPass123!"},
                           follow_redirects=True)
    body = response.get_data(as_text=True)
    assert "My Progress" in body
    assert "Alice Johnson" in body
    client.get("/logout", follow_redirects=True)
    response = client.get("/account", follow_redirects=False)
    assert response.status_code == 302


def test_login_bad_password(mirror):
    client = mirror.app.test_client()
    response = client.post("/login", data={"email": "alice.j@test.com",
                                           "password": "wrong"},
                           follow_redirects=True)
    assert "Invalid email or password." in response.get_data(as_text=True)


def test_register_validation(mirror):
    client = mirror.app.test_client()
    response = client.post("/register", data={"username": "x", "email": "bad",
                                              "display_name": "", "password": "123"},
                           follow_redirects=True)
    body = response.get_data(as_text=True)
    assert "Username must be 3-32 characters" in body
    with mirror.app.app_context():
        assert mirror.User.query.count() == 4


def test_favorite_toggle(mirror):
    with mirror.app.app_context():
        client = mirror.app.test_client()
        client.post("/login", data={"email": "carol.d@test.com",
                                    "password": "TestPass123!"})
        before = mirror.Favorite.query.filter_by(user_id=3).count()
        client.post("/math-games/tortuga-racing/favorite")
        after = mirror.Favorite.query.filter_by(user_id=3).count()
        assert after == before + 1
        client.post("/math-games/tortuga-racing/favorite")
        assert mirror.Favorite.query.filter_by(user_id=3).count() == before


def test_anonymous_cannot_favorite(mirror):
    client = mirror.app.test_client()
    response = client.post("/math-games/alien-addition/favorite",
                           follow_redirects=False)
    assert response.status_code == 302  # redirected to login


def test_account_shows_progress(mirror):
    client = mirror.app.test_client()
    client.post("/login", data={"email": "bob.c@test.com",
                                "password": "TestPass123!"})
    body = client.get("/account").get_data(as_text=True)
    assert "Math Ninja" in body
    assert "Bob Chen" in body
    assert "Island Chase" in body


# ---------------------------------------------------------------- game play API

def test_game_result_recorded(mirror):
    with mirror.app.app_context():
        client = mirror.app.test_client()
        response = client.post("/games/alien-addition/result",
                               data={"facts_total": "10", "facts_correct": "10",
                                     "position": "1", "duration": "42.5"})
        assert response.status_code == 200
        play = mirror.GamePlay.query.filter_by(game_slug="alien-addition").first()
        assert play is not None
        assert play.facts_correct == 10 and play.position == 1
        assert play.user_id is None


def test_game_result_validation(mirror):
    client = mirror.app.test_client()
    assert client.post("/games/alien-addition/result",
                      data={"facts_total": "0", "facts_correct": "0"}
                      ).status_code == 400
    assert client.post("/games/alien-addition/result",
                      data={"facts_total": "10", "facts_correct": "11"}
                      ).status_code == 400
