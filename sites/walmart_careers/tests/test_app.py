from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))
os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"

import app as site  # noqa: E402
import seed_data  # noqa: E402

SEED = SITE / "instance_seed" / "walmart_careers.db"

if not SEED.exists():
    seed_data.build_seed_database()


@pytest.fixture(autouse=True)
def clean_database():
    with site.app.app_context():
        site.db.session.remove()
        site.db.engine.dispose()
    site.INSTANCE_DIR.mkdir(exist_ok=True)
    shutil.copy2(SEED, site.DB_PATH)
    site.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    yield
    with site.app.app_context():
        site.db.session.remove()
        site.db.engine.dispose()
    site.DB_PATH.unlink(missing_ok=True)


@pytest.fixture
def client():
    return site.app.test_client()


def login(client, email="alice.j@test.com"):
    response = client.post("/login", data={"email": email, "password": "TestPass123!"})
    assert response.status_code == 302
    return response


def job_id(title: str, city: str) -> str:
    with site.app.app_context():
        return (
            site.Job.query.join(site.Store)
            .filter(site.Job.title == title, site.Store.city == city)
            .one()
            .job_id
        )


def test_security_configuration_and_malformed_session_identity():
    assert site.app.config["SECRET_KEY"] != "webharbor-walmart-careers-demo-key"
    assert site.app.config["MAX_CONTENT_LENGTH"] == 256 * 1024
    assert site.app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert site.app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    with site.app.app_context():
        assert site.load_user("not-an-integer") is None


def test_navigation_controller_is_packaged(client):
    page = client.get("/")
    assert page.status_code == 200
    assert b'/static/js/navigation.js' in page.data
    script = client.get("/static/js/navigation.js")
    assert script.status_code == 200
    assert b'addEventListener("pointerdown"' in script.data
    assert b'addEventListener("keydown"' in script.data
    assert b'closeMenus(menu)' in script.data


def test_health_and_seed_contract(client):
    response = client.get("/_health")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "site": "walmart_careers",
        "seed_version": "walmart-careers-v2",
        "jobs": 246,
        "stores": 51,
        "areas": 7,
        "categories": 33,
        "users": 4,
    }
    with site.app.app_context():
        assert site.db.session.get(site.SeedMetadata, "version").value == site.SEED_VERSION
        assert site.db.session.execute(site.db.text("PRAGMA foreign_key_check")).all() == []


def test_all_public_pages_render(client):
    paths = [
        "/", "/home", "/results", "/resources/location",
        "/resources/hiring-process", "/resources/terms-and-conditions", "/about-us",
        "/login", "/register", "/candidate-home/saved-roles",
    ]
    with site.app.app_context():
        paths += [f"/careers-areas/{row.slug}" for row in site.Area.query.all()]
        paths += [f"/jobs/{row.job_id}" for row in site.Job.query.order_by(site.Job.job_id).limit(6)]
    for path in paths:
        response = client.get(path, follow_redirects=True)
        assert response.status_code == 200, path
        assert b"Traceback" not in response.data


@pytest.mark.parametrize("query", [
    "page=x", "page=0", "page=10001", "page=1&page=2", "radius=10",
    "sort=unknown", "tab=unknown", "q=a&searchQuery=b", "q=x&q=y",
    "brand=Target", "brand=Walmart&brand=Walmart", "shift=Night",
    "type=Contract", "rate=Daily", "area=unknown", "category=unknown",
])
def test_invalid_results_queries_fail_closed(client, query):
    assert client.get(f"/results?{query}").status_code == 400


def test_bounded_results_query_and_valid_filters(client):
    assert client.get("/results?q=" + "x" * 161).status_code == 400
    assert client.get("/results?loc=" + "x" * 81).status_code == 400
    assert client.get("/results?q=" + "+".join(f"term{n}" for n in range(13))).status_code == 400
    response = client.get(
        "/results?q=cashier&loc=Puerto+Rico&radius=25&shift=Weekday+Day&"
        "type=Full+time&rate=Hourly&brand=Walmart&area=stores-and-clubs"
    )
    assert response.status_code == 200
    assert b"open role" in response.data


def test_unknown_and_unseeded_locations_never_broaden_results(client):
    for location in ("NoSuchPlace", "Alabama"):
        response = client.get("/results", query_string={"loc": location})
        assert response.status_code == 200
        assert b"0 open roles" in response.data
        assert b"No roles matched" in response.data
    response = client.get("/results", query_string={"loc": "Puerto Rico", "radius": "25"})
    assert response.status_code == 200
    assert b"Showing roles in Puerto Rico (PR)" in response.data


def test_displayed_hashtag_returns_its_job_family(client):
    response = client.get("/results", query_string={"q": "#freighthandlerjobs"})
    assert response.status_code == 200
    assert b"Freight Handler" in response.data
    assert b"No roles matched" not in response.data


def test_safe_next_rejects_external_and_encoded_network_paths(client):
    for target in ["https://example.com/", "//example.com/", "/%2f%2fexample.com/", "/\\example.com"]:
        response = client.post(
            "/login", data={"email": "alice.j@test.com", "password": "TestPass123!", "next": target}
        )
        assert response.status_code == 302
        assert response.headers["Location"] == "/"
        client.post("/logout")
    response = client.post(
        "/login",
        data={"email": "alice.j@test.com", "password": "TestPass123!", "next": "/account?from=test"},
    )
    assert response.headers["Location"] == "/account?from=test"


def test_login_and_authenticated_ownership(client):
    target = job_id("Yard Driver-Off Property", "Williamsburg")
    response = client.post(f"/jobs/{target}/save")
    assert response.status_code == 302 and response.headers["Location"].startswith("/login")
    login(client)
    assert client.post(f"/jobs/{target}/save").status_code == 302
    with site.app.app_context():
        alice = site.User.query.filter_by(email="alice.j@test.com").one()
        bob = site.User.query.filter_by(email="bob.c@test.com").one()
        assert site.SavedJob.query.filter_by(user_id=alice.id, job_id=target).count() == 1
        assert site.SavedJob.query.filter_by(user_id=bob.id, job_id=target).count() == 0
    assert client.post(f"/jobs/{target}/save").status_code == 302
    with site.app.app_context():
        alice = site.User.query.filter_by(email="alice.j@test.com").one()
        assert site.SavedJob.query.filter_by(user_id=alice.id, job_id=target).count() == 1


def test_runtime_state_remains_restartable_and_healthy(client):
    login(client)
    target = job_id("Yard Driver-Off Property", "Williamsburg")
    client.post(f"/jobs/{target}/save")
    client.post("/logout")
    registration = {"first_name": "Runtime", "last_name": "User", "email": "runtime.user@example.com",
                    "password": "long-password", "confirm_password": "long-password"}
    assert client.post("/register", data=registration).status_code == 302
    with site.app.app_context():
        seed_data.ensure_seed_database()
        assert site.Job.query.count() == 246
        assert site.User.query.count() == 5
        assert site.SavedJob.query.count() == 14
    health = client.get("/_health")
    assert health.status_code == 200 and health.get_json()["ok"] is True


def test_registration_validation_and_case_insensitive_uniqueness(client):
    base = {"first_name": "Taylor", "last_name": "Reed", "password": "long-password", "confirm_password": "long-password"}
    response = client.post("/register", data={**base, "email": "ALICE.J@TEST.COM"})
    assert response.status_code == 200
    assert b"already exists" in response.data
    response = client.post("/register", data={**base, "email": "t@example.com", "first_name": "x" * 81})
    assert response.status_code == 200
    assert b"80 characters or fewer" in response.data
    response = client.post("/register", data={**base, "email": "taylor.reed+pr86@example.com"})
    assert response.status_code == 302
    with site.app.app_context():
        assert site.User.query.filter_by(email="taylor.reed+pr86@example.com").count() == 1


def test_profile_rejects_truncation_and_unbounded_values(client):
    login(client, "david.k@test.com")
    form = {"display_name": "David Kim", "first_name": "David", "last_name": "Kim", "phone": "214-555-0166", "city": "Rogers"}
    response = client.post("/account/edit", data={**form, "state": "ARK"})
    assert response.status_code == 200
    assert b"2 characters or fewer" in response.data
    response = client.post("/account/edit", data={**form, "state": "ZZ"})
    assert response.status_code == 200
    assert b"valid two-letter" in response.data
    response = client.post("/account/edit", data={**form, "state": "AR", "city": "x" * 81})
    assert response.status_code == 200
    assert b"80 characters or fewer" in response.data
    assert client.post("/account/edit", data={**form, "state": "AR"}).status_code == 302
    with site.app.app_context():
        david = site.User.query.filter_by(email="david.k@test.com").one()
        assert (david.city, david.state) == ("Rogers", "AR")


def test_application_validation_and_submission(client):
    login(client, "carol.d@test.com")
    target = job_id("Pharmacy Technician", "Tacoma")
    response = client.post(
        f"/jobs/{target}/apply",
        data={"email": "carol.d@test.com", "first_name": "Carol", "last_name": "Davis",
              "phone": "1" * 16, "terms": "on"},
    )
    assert response.status_code == 200
    assert b"10 to 15 digits" in response.data
    response = client.post(
        f"/jobs/{target}/apply",
        data={"email": "carol.d@test.com", "first_name": "Carol", "last_name": "Davis",
              "phone": "253-555-0142", "terms": "on"},
    )
    assert response.status_code == 302 and response.headers["Location"].endswith("/apply/confirm")
    response = client.post(response.headers["Location"])
    assert response.status_code == 302 and response.headers["Location"].endswith("/apply/submitted")
    submitted = client.get(response.headers["Location"])
    assert submitted.status_code == 200 and b"WMC-000005" in submitted.data
    with site.app.app_context():
        carol = site.User.query.filter_by(email="carol.d@test.com").one()
        row = site.Application.query.filter_by(user_id=carol.id, job_id=target).one()
        assert re.sub(r"\D", "", row.phone) == "2535550142"


def test_application_draft_cookie_is_opaque_and_replay_is_idempotent(client):
    login(client, "carol.d@test.com")
    target = job_id("Pharmacy Technician", "Tacoma")
    response = client.post(
        f"/jobs/{target}/apply",
        data={"email": "carol.d@test.com", "first_name": "Carol", "last_name": "Davis",
              "phone": "253-555-0142", "terms": "on"},
    )
    assert response.status_code == 302
    with client.session_transaction() as browser_session:
        assert set(browser_session) <= {"_flashes", "_fresh", "_id", "_user_id", "apply_draft_token"}
        assert "carol.d@test.com" not in repr(dict(browser_session))
    old_cookie = client.get_cookie("session").value
    confirm = response.headers["Location"]
    assert client.post(confirm).status_code == 302
    replay = site.app.test_client()
    replay.set_cookie("session", old_cookie)
    assert replay.post(confirm).status_code == 302
    with site.app.app_context():
        assert site.Application.query.filter_by(user_id=3, job_id=target).count() == 1
        assert site.ApplicationDraft.query.count() == 0


def test_identity_change_invalidates_application_workflow(client):
    login(client, "alice.j@test.com")
    target = job_id("Pharmacy Technician", "Tacoma")
    response = client.post(
        f"/jobs/{target}/apply",
        data={"email": "alice.j@test.com", "first_name": "Alice", "last_name": "Johnson",
              "phone": "479-555-0134", "terms": "on"},
    )
    assert response.status_code == 302
    assert client.post("/login", data={"email": "bob.c@test.com", "password": "TestPass123!"}).status_code == 302
    assert client.get(response.headers["Location"]).headers["Location"].endswith(f"/jobs/{target}/apply")
    with site.app.app_context():
        assert site.ApplicationDraft.query.count() == 0


def test_submitted_application_requires_matching_owner(client):
    login(client, "alice.j@test.com")
    with client.session_transaction() as browser_session:
        browser_session["apply_submitted_id"] = 2
    response = client.get("/jobs/CP-6014-11937/apply/submitted")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/jobs/CP-6014-11937/apply")


def test_csrf_is_required_for_mutations(client):
    site.app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/login", data={"email": "alice.j@test.com", "password": "TestPass123!"}).status_code == 400
    page = client.get("/login")
    token = re.search(rb'name="csrf_token"[^>]+value="([^"]+)"', page.data).group(1).decode()
    response = client.post(
        "/login", data={"csrf_token": token, "email": "alice.j@test.com", "password": "TestPass123!"}
    )
    assert response.status_code == 302


def test_request_body_limit(client):
    response = client.post("/login", data={"email": "x" * (257 * 1024), "password": "x"})
    assert response.status_code == 413
