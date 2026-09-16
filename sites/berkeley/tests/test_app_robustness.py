"""App-robustness regression tests (Appendix A §1 forms, §6 hardening).

Every test here was written after the corresponding probe failed on the
pre-fix tree, and each detector was mutation-checked by re-introducing the
defect and confirming the test then fails.

Covers: POST-only logout, session-cookie forgery and malformed user ids,
bookmark-form validation (empty/invalid -> 400, unknown row -> 404, another
user's row -> 404), bounded query/form integers, same-origin redirects,
SQLite foreign-key enforcement, read-only GETs, the 404/500 handlers, form
preselection, and the accessibility chrome the maintainers require.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
SEED = SITE / "instance_seed" / "berkeley.db"
RUNTIME = SITE / "instance" / "berkeley.db"

os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"
sys.path.insert(0, str(SITE))


@pytest.fixture(scope="module")
def app_module():
    import app

    return app


@pytest.fixture()
def client(app_module):
    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    with app_module.app.test_client() as test_client:
        yield test_client
    app_module.app.config["WTF_CSRF_ENABLED"] = True


def _login(client, email="alice@berkeley.edu", password="test1234"):
    return client.post("/login", data={"email": email, "password": password},
                       follow_redirects=False)


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# §6 — auth and session hardening
# --------------------------------------------------------------------------- #
def test_logout_is_post_only(client):
    assert _login(client).status_code == 302
    assert client.get("/account").status_code == 200
    # a prefetcher's GET/HEAD must not end the session
    assert client.get("/logout").status_code == 405
    assert client.head("/logout").status_code == 405
    assert client.get("/account").status_code == 200
    # the real POST logs out
    assert client.post("/logout").status_code == 302
    assert client.get("/account").status_code == 302  # bounced to /login


def test_secret_key_is_not_a_committed_literal(app_module):
    source = (SITE / "app.py").read_text()
    assert "berkeley-mirror-secret-key" not in source
    assert "os.environ.get('BERKELEY_SECRET_KEY') or secrets.token_hex(32)" in source
    assert app_module.app.config["SECRET_KEY"] != "berkeley-mirror-secret-key-2024"


def test_wrong_key_session_cookie_is_rejected(app_module):
    from flask.json.tag import TaggedJSONSerializer
    from itsdangerous import URLSafeTimedSerializer

    serializer = URLSafeTimedSerializer(
        "wrong-key-not-the-site-key", salt="cookie-session",
        serializer=TaggedJSONSerializer(),
        signer_kwargs={"key_derivation": "hmac"})
    cookie = serializer.dumps({"_user_id": "1", "_fresh": True})
    with app_module.app.test_client() as test_client:
        response = test_client.get("/account", headers={"Cookie": f"session={cookie}"})
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


def test_malformed_user_id_fails_closed(app_module):
    """A signed cookie with a non-numeric / huge id must be anonymous, not a 500."""
    signer = app_module.app.session_interface.get_signing_serializer(app_module.app)
    for bad in ("not-a-number", "9" * 20):
        cookie = signer.dumps({"_user_id": bad, "_fresh": True})
        with app_module.app.test_client() as test_client:
            response = test_client.get("/account", headers={"Cookie": f"session={cookie}"})
            assert response.status_code == 302, f"{bad!r} -> {response.status_code}"


def test_csrf_is_enforced_and_unexempted(app_module):
    app_module.app.config["WTF_CSRF_ENABLED"] = True
    try:
        with app_module.app.test_client() as test_client:
            assert test_client.post("/login", data={"email": "a@b.co", "password": "x"}
                                    ).status_code == 400
            assert test_client.post("/bookmark/add", data={"item_type": "research",
                                                           "item_id": "1"}).status_code == 400
    finally:
        app_module.app.config["WTF_CSRF_ENABLED"] = False


# --------------------------------------------------------------------------- #
# §1 — bookmark form: empty/invalid submissions fail loudly
# --------------------------------------------------------------------------- #
def test_bookmark_add_rejects_invalid_submissions(client):
    assert _login(client).status_code == 302
    assert client.post("/bookmark/add", data={}).status_code == 400
    assert client.post("/bookmark/add", data={"item_type": "bogus", "item_id": "1"}).status_code == 400
    assert client.post("/bookmark/add", data={"item_type": "research", "item_id": "999999"}).status_code == 404
    assert client.post("/bookmark/add", data={"item_type": "research", "item_id": "9" * 20}).status_code == 400
    # valid submission still works
    assert client.post("/bookmark/add", data={"item_type": "research", "item_id": "1"}
                       ).status_code == 302


def test_bookmark_remove_is_owner_scoped(app_module):
    import sqlite3

    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    try:
        alice = app_module.app.test_client()
        assert _login(alice, "alice@berkeley.edu").status_code == 302
        alice.post("/bookmark/add", data={"item_type": "research", "item_id": "1"})
        con = sqlite3.connect(RUNTIME)
        row = con.execute("SELECT b.id FROM bookmarks b JOIN users u ON u.id=b.user_id "
                          "WHERE u.email='alice@berkeley.edu' ORDER BY b.id DESC LIMIT 1").fetchone()
        con.close()
        bookmark_id = row[0]

        bob = app_module.app.test_client()
        assert _login(bob, "bob@berkeley.edu").status_code == 302
        # bob cannot delete alice's row (and a malformed id is a 400)
        assert bob.post("/bookmark/remove",
                        data={"bookmark_id": str(bookmark_id)}).status_code == 404
        assert bob.post("/bookmark/remove", data={"bookmark_id": "x"}).status_code == 400
        # alice's row survived
        con = sqlite3.connect(RUNTIME)
        still = con.execute("SELECT count(*) FROM bookmarks WHERE id=?", (bookmark_id,)).fetchone()[0]
        con.close()
        assert still == 1
    finally:
        app_module.app.config["WTF_CSRF_ENABLED"] = True


# --------------------------------------------------------------------------- #
# §6 — bounds, redirects, foreign keys, read-only, error pages
# --------------------------------------------------------------------------- #
def test_huge_ints_are_not_500s(client):
    for path in ("/events/99999999999999999999", "/news?page=99999999999999999999",
                 "/programs?page=99999999999999999999", "/faculty?page=99999999999999999999",
                 "/events?page=99999999999999999999"):
        response = client.get(path)
        assert response.status_code in (200, 404), f"{path} -> {response.status_code}"


def test_redirect_targets_stay_same_origin(client):
    response = client.post("/login?next=https://evil.example/",
                           data={"email": "alice@berkeley.edu", "password": "test1234"})
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/")
    assert "evil.example" not in response.headers["Location"]
    assert _login(client).status_code == 302
    response = client.post("/bookmark/add", data={"item_type": "research", "item_id": "1",
                                                  "next": "https://evil.example/"})
    assert response.status_code == 302
    assert not response.headers["Location"].startswith("http")


def test_sqlite_foreign_keys_enforced(app_module):
    from sqlalchemy.exc import IntegrityError

    with app_module.app.app_context():
        with app_module.db.engine.begin() as conn:
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        with pytest.raises(IntegrityError):
            with app_module.db.engine.begin() as conn:
                conn.exec_driver_sql(
                    "INSERT INTO bookmarks (user_id, item_type, item_id, note, created_at) "
                    "VALUES (999999, 'research', 1, 'orphan', '2026-05-12 00:00:00')")


def test_read_only_gets_do_not_write(client):
    before = _md5(RUNTIME)
    for path in ("/", "/news?q=climate", "/programs?q=MBA", "/events?category=Lecture",
                 "/research", "/research/bair", "/departments", "/departments/eecs",
                 "/academics", "/admissions", "/about", "/search?q=climate",
                 "/faculty?dept=eecs", "/faculty/stuart-russell", "/login", "/register",
                 "/news/crispr-pioneer-jennifer-doudna-receives-national-medal-of-science"):
        assert client.get(path).status_code == 200, path
    assert _md5(RUNTIME) == before


def test_error_handlers_render_their_templates(client, app_module):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert "Page Not Found" in response.get_data(as_text=True)
    with app_module.app.test_request_context("/x"):
        body, status = app_module.server_error(RuntimeError("boom"))
    assert status == 500 and "Something Went Wrong" in body


# --------------------------------------------------------------------------- #
# §1 — no answer-bearing form defaults; §9 — accessibility chrome
# --------------------------------------------------------------------------- #
FORM_PAGES = ("/login", "/register", "/search", "/programs", "/news", "/events", "/faculty",
              "/programs/business-administration-mba", "/research/bair",
              "/news/crispr-pioneer-jennifer-doudna-receives-national-medal-of-science")
ALLOW_NONEMPTY = {"csrf_token", "item_type", "item_id", "next", "bookmark_id"}


def test_forms_arrive_empty_and_unchecked(client):
    for path in FORM_PAGES:
        body = client.get(path).get_data(as_text=True)
        for tag in re.findall(r"<input\b[^>]*>", body, re.I):
            name = re.search(r'name="([^"]*)"', tag)
            value = re.search(r'value="([^"]*)"', tag)
            if name and value and value.group(1) and name.group(1) not in ALLOW_NONEMPTY:
                raise AssertionError(f"{path}: {name.group(1)} arrives as {value.group(1)!r}")
            assert "checked" not in tag.lower(), f"{path}: a checkbox arrives checked"
        for match in re.finditer(r'<select\b[^>]*name="([^"]*)"[^>]*>(.*?)</select>', body, re.I | re.S):
            name, inner = match.group(1), match.group(2)
            for opt in re.finditer(r"<option\b([^>]*)>", inner, re.I):
                if "selected" in opt.group(1).lower():
                    value = re.search(r'value="([^"]*)"', opt.group(1))
                    # the /events date filter defaults to the site's own
                    # "Upcoming" view; every task-relevant filter is empty-first
                    assert value and value.group(1) == "upcoming" and name == "date", (
                        f"{path}: select {name} preselects {opt.group(0)!r}")


def test_accessibility_chrome_present(client):
    body = client.get("/").get_data(as_text=True)
    assert 'class="skip-link"' in body and 'id="main"' in body
    assert "mirror-notice" in body and "Unofficial offline benchmark mirror" in body
    assert "focus-visible" in body, "focus-visible styles missing"
    assert 'role="alert"' in body or 'role="note"' in body
    # the sign-out control is a POST form, not a GET link
    _login(client)
    body = client.get("/").get_data(as_text=True)
    assert 'action="/logout"' in body and "Sign Out" in body
