"""Regression suite for the healthline mirror (PR #105 remediation).

Run with:  pytest sites/healthline/tests -q
The suite works on an isolated copy of the site directory, so it never mutates the
tracked tree or the runtime instance/ database.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def site_copy(tmp_path_factory):
    dst = tmp_path_factory.mktemp("healthline")
    for item in ("app.py", "seed_data.py", "migrate_seed.py", "prune_unreferenced_images.py",
                 "asset_provenance.json", "image_assignments.json", "requirements.txt"):
        shutil.copy2(SITE / item, dst / item)
    for d in ("templates", "static", "instance_seed"):
        shutil.copytree(SITE / d, dst / d, symlinks=True)
    return dst


@pytest.fixture(scope="session")
def app_module(site_copy):
    sys.path.insert(0, str(site_copy))
    spec = importlib.util.spec_from_file_location("healthline_app_under_test", site_copy / "app.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    sys.path.remove(str(site_copy))

    # a route that always raises, registered before the first request so the 500
    # handler can be exercised through the test client
    @mod.app.route("/__boom__")
    def _boom():
        raise RuntimeError("intentional failure for the error-handler test")

    yield mod


@pytest.fixture()
def client(app_module):
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def db_hash(app_module):
    return hashlib.sha256((app_module.DB_DIR / "healthline.db").read_bytes()).hexdigest()


def csrf(client, path):
    html = client.get(path).get_data(as_text=True)
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else ""


def sign_in(client, email="alice.j@test.com", password="TestPass123!"):
    token = csrf(client, "/login")
    return client.post("/login", data={"csrf_token": token, "email": email, "password": password})


# ---------------------------------------------------------------- seeding and assets
def test_seed_is_idempotent_and_migration_is_in_sync(site_copy):
    """Importing the app must not rewrite an already populated seed DB, and migrate_seed
    must report that the downloaded database already matches the tracked source."""
    before = hashlib.sha256((site_copy / "instance_seed" / "healthline.db").read_bytes()).hexdigest()
    r = subprocess.run([sys.executable, str(site_copy / "migrate_seed.py"), "--check"],
                       cwd=site_copy, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "already in sync" in r.stdout
    r2 = subprocess.run([sys.executable, str(site_copy / "migrate_seed.py")],
                        cwd=site_copy, capture_output=True, text=True)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    after = hashlib.sha256((site_copy / "instance_seed" / "healthline.db").read_bytes()).hexdigest()
    assert before == after, "an in-sync migration must not touch the database bytes"


def test_no_unreferenced_images_remain(site_copy):
    r = subprocess.run([sys.executable, str(site_copy / "prune_unreferenced_images.py")],
                       cwd=site_copy, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "nothing to remove" in r.stdout


def test_asset_provenance_hashes_match(site_copy):
    manifest = json.loads((site_copy / "asset_provenance.json").read_text())
    bad = []
    for name, meta in manifest["assets"].items():
        p = site_copy / "static" / "images" / name
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != meta["sha256"]:
            bad.append(name)
    assert bad == []


# ---------------------------------------------------------------- leakage
def test_forms_arrive_empty(client):
    for path in ("/login", "/register"):
        html = client.get(path).get_data(as_text=True)
        assert not re.search(r'<input[^>]+type="(?:email|text|password)"[^>]+value="[^"]+"', html), path


def test_header_does_not_render_the_saved_count(client):
    sign_in(client)
    for path in ("/", "/saved", "/account"):
        html = client.get(path).get_data(as_text=True)
        assert not re.search(r"Saved\s*\(\d+\)", html), f"saved count leaked on {path}"


def test_drug_class_is_not_on_listing_cards(client):
    html = client.get("/drugs?category=Heart+Medications").get_data(as_text=True)
    kickers = re.findall(r'<div class="cat">(.*?)</div>', html, re.S)
    assert kickers and all(k.strip() == "Heart Medications" for k in kickers), kickers[:5]
    detail = client.get("/drug/lisinopril").get_data(as_text=True)
    assert "Drug class: ACE inhibitor" in detail


# ---------------------------------------------------------------- read-only invariants
def test_article_get_is_side_effect_free(app_module, client):
    before = db_hash(app_module)
    client.get("/article/vitamin-d-101")
    client.get("/article/benefits-of-walking")
    assert db_hash(app_module) == before


def test_explicit_view_post_records_the_view(app_module, client):
    before = db_hash(app_module)
    token = csrf(client, "/article/vitamin-d-101")
    r = client.post("/article/vitamin-d-101/view", data={"csrf_token": token})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert db_hash(app_module) != before


# ---------------------------------------------------------------- input handling
@pytest.mark.parametrize("path", [
    "/section/health-conditions?sub=__nope__",
    "/drugs?category=__nope__",
    "/drugs?letter=ZZ",
    "/conditions?category=__nope__",
    "/search?q=diabetes&type=__nope__",
    "/section/health-conditions?page=0",
    "/section/health-conditions?page=99999",
    "/section/health-conditions?sort=__nope__",
])
def test_invalid_filters_are_rejected(client, path):
    assert client.get(path).status_code == 400, path


@pytest.mark.parametrize("path,needle", [
    ("/section/nutrition?sub=Diets", "Mediterranean"),
    ("/drugs?letter=L", "Lisinopril"),
    ("/conditions?category=Heart+Health", "High Blood Pressure"),
    ("/search?q=diabetes&type=conditions", "Diabetes"),
])
def test_valid_filters_still_work(client, path, needle):
    r = client.get(path)
    assert r.status_code == 200 and needle in r.get_data(as_text=True)


def test_register_validation(client):
    token = csrf(client, "/register")
    base = {"csrf_token": token, "username": "tester1", "email": "bad-email",
            "password": "Wellness99!", "confirm_password": "Wellness99!"}
    assert client.post("/register", data=base).status_code == 400
    long_user = dict(base, email="tester1@example.com", username="u" * 300)
    assert client.post("/register", data=long_user).status_code == 400
    ok = dict(base, email="tester1@example.com", username="tester1")
    assert client.post("/register", data=ok).status_code in (200, 302)


def test_session_user_id_is_validated(app_module):
    with app_module.app.app_context():
        assert app_module.load_user("abc") is None
        assert app_module.load_user("inf") is None
        assert app_module.load_user("") is None
        assert app_module.load_user("-1") is None
        assert app_module.load_user("999999") is None
        assert app_module.load_user(None) is None
        assert app_module.load_user("1") is not None


def test_body_limit_and_csrf(app_module, client):
    assert app_module.app.config["MAX_CONTENT_LENGTH"] == 64 * 1024
    assert client.post("/login", data=b"X" * (70 * 1024),
                       content_type="application/x-www-form-urlencoded").status_code == 413
    assert client.post("/save/1", data={}).status_code == 400


def test_logout_is_post_only(client):
    sign_in(client)
    assert client.get("/logout").status_code == 405
    assert client.head("/logout").status_code == 405
    token = csrf(client, "/article/vitamin-d-101")
    r = client.post("/logout", data={"csrf_token": token})
    assert r.status_code in (302, 200)


def test_error_pages_are_branded_and_leak_nothing(app_module, client):
    r = client.get("/article/__none__")
    assert r.status_code == 404
    body = r.get_data(as_text=True)
    assert "Page not found" in body and "Traceback" not in body

    # TESTING mode re-raises exceptions; the production configuration must render the
    # branded 500 page instead
    app_module.app.config["TESTING"] = False
    try:
        r = client.get("/__boom__")
    finally:
        app_module.app.config["TESTING"] = True
    assert r.status_code == 500
    body = r.get_data(as_text=True)
    assert "Something went wrong" in body and "Traceback" not in body and "RuntimeError" not in body


# ---------------------------------------------------------------- accessibility tokens
def test_contrast_tokens_meet_wcag(app_module):
    css = (SITE / "static" / "css" / "main.css").read_text()

    def lum(rgb):
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = (f(c / 255) for c in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def ratio(a, b):
        la, lb = lum(a), lum(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    def token(name):
        m = re.search(rf"--{name}:\s*#([0-9a-fA-F]{{6}})", css)
        assert m, f"missing --{name}"
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    assert ratio((255, 255, 255), token("hl-action")) >= 4.5
    assert ratio(token("hl-link"), (255, 255, 255)) >= 4.5
    assert ratio(token("hl-link"), (0xF4, 0xF6, 0xF8)) >= 4.5
    assert ratio(token("hl-focus"), (255, 255, 255)) >= 3
    assert ratio(token("hl-ink"), (255, 255, 255)) >= 4.5


def test_header_wraps_on_small_screens(app_module):
    css = (SITE / "static" / "css" / "main.css").read_text()
    assert "flex-wrap: wrap" in css.split(".header-top {")[1].split("}")[0]
    assert "@media (max-width: 560px)" in css
