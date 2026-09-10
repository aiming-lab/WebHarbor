from __future__ import annotations

import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]


def csrf(response):
    matches = re.findall(rb'name="csrf_token" value="([^"]+)"', response.data)
    assert matches
    return matches[0].decode()


def login(client, email="alice.j@test.com", password="TestPass123!", next_url=""):
    page = client.get("/login", query_string={"next": next_url} if next_url else None)
    return client.post(
        "/login" + (("?next=" + next_url) if next_url else ""),
        data={"csrf_token": csrf(page), "email": email, "password": password},
        follow_redirects=False,
    )


def database_rows(path, sql, params=()):
    connection = sqlite3.connect(path)
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


@pytest.mark.parametrize("path,required", [
    ("/", b"Local benchmark mirror"),
    ("/search?q=metformin", b"Metformin"),
    ("/metformin", b"Biguanides"),
    ("/ibuprofen/faq", b"1200 mg"),
    ("/amoxicillin/dosage", b"every 8 hours"),
    ("/lisinopril/warnings", b"FETAL TOXICITY"),
    ("/drug_information.html?letter=L", b"Lisinopril"),
    ("/conditions/diabetes", b"Metformin"),
    ("/conditions/hypertension", b"Amlodipine"),
    ("/drug-classes/statins", b"Atorvastatin"),
    ("/drug-classes/benzodiazepines", b"Alprazolam"),
    ("/pill-identifier?imprint=I-2", b"Ibuprofen"),
    ("/pill-identifier?shape=Oval&color=White", b"IP 466"),
    ("/new-drug-approvals", b"New Drug Approvals"),
    ("/news/article/1", b"Simulated article"),
    ("/pro/metformin", b"Structured fixture status"),
    ("/semaglutide/side-effects", b"Stored side-effect fixture"),
    ("/ibuprofen/reviews", b"Simulated fixture"),
    ("/semaglutide/pregnancy", b"Stored pregnancy fixture field"),
    ("/about", b"not the official Drugs.com service"),
    ("/_health", b"drugs-com-source-v2"),
])
def test_representative_routes(client, path, required):
    response = client.get(path)
    assert response.status_code == 200
    assert required.lower() in response.data.lower()


def test_security_headers(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert any(cookie.startswith("drugs_com_session=") for cookie in response.headers.getlist("Set-Cookie"))
    assert not any(cookie.startswith("session=") for cookie in response.headers.getlist("Set-Cookie"))


@pytest.mark.parametrize("path", [
    "/search?q=a&q=b",
    "/search?class=missing",
    "/search?condition=missing",
    "/search?availability=invalid",
    "/drugs-a-z?letter=INVALID",
    "/metformin/reviews?sort=invalid",
    "/conditions/diabetes?sort=invalid",
    "/drug-classes/statins?sort=invalid",
    "/pill-identifier?shape=triangle",
    "/pill-identifier?color=ultraviolet",
])
def test_invalid_public_filters_fail_closed(client, path):
    assert client.get(path).status_code == 400


def test_query_limits(client):
    assert client.get("/search?" + "x=" + "a" * 17000).status_code == 400
    assert client.get("/search?" + "&".join(f"k{i}=1" for i in range(101))).status_code == 400


def test_csrf_is_required(client):
    assert client.post("/login", data={"email": "alice.j@test.com", "password": "TestPass123!"}).status_code == 400
    assert client.post("/newsletter/subscribe", data={"email": "a@example.com", "lists": "daily_mednews"}).status_code == 400


def test_login_and_safe_next(client):
    response = login(client, next_url="/my-med-list")
    assert response.status_code == 302
    assert response.location.endswith("/my-med-list")
    with client.session_transaction() as current_session:
        current_session.clear()
    page = client.get("/login?next=https://evil.example/")
    token = csrf(page)
    response = client.post("/login?next=https://evil.example/", data={"csrf_token": token, "email": "alice.j@test.com", "password": "TestPass123!"})
    assert response.status_code == 302
    assert "evil.example" not in response.location


def test_wrong_and_oversized_login_fail(client):
    page = client.get("/login")
    response = client.post("/login", data={"csrf_token": csrf(page), "email": "alice.j@test.com", "password": "wrong"}, follow_redirects=True)
    assert b"Invalid email or password" in response.data
    page = client.get("/login")
    response = client.post("/login", data={"csrf_token": csrf(page), "email": "x" * 121, "password": "x" * 73}, follow_redirects=True)
    assert b"Invalid email or password" in response.data


def test_login_throttles_repeated_failures(client):
    for _ in range(8):
        page = client.get("/login")
        response = client.post("/login", data={"csrf_token": csrf(page), "email": "alice.j@test.com", "password": "wrong"})
        assert response.status_code == 200
    page = client.get("/login")
    response = client.post("/login", data={"csrf_token": csrf(page), "email": "alice.j@test.com", "password": "wrong"})
    assert response.status_code == 429
    assert b"Too many failed sign-in attempts" in response.data


def test_concurrent_auth_reservations_enforce_attempt_limit(drugs_app):
    keys = ("source:concurrent", "account:concurrent@example.com")
    with drugs_app._auth_failures_lock:
        drugs_app._auth_failures.clear()
        drugs_app._auth_pending.clear()
    with ThreadPoolExecutor(max_workers=16) as executor:
        admitted = list(executor.map(lambda _index: drugs_app._begin_auth_attempt(keys), range(16)))
    assert admitted.count(True) == drugs_app._AUTH_FAILURE_LIMIT
    assert admitted.count(False) == 16 - drugs_app._AUTH_FAILURE_LIMIT
    for _ in range(admitted.count(True)):
        drugs_app._finish_auth_attempt(keys, successful=False)
    assert drugs_app._auth_is_limited(keys)


def test_success_does_not_clear_source_failure_history(drugs_app):
    keys = ("source:shared", "account:known@example.com")
    with drugs_app._auth_failures_lock:
        drugs_app._auth_failures.clear()
        drugs_app._auth_pending.clear()
        drugs_app._auth_failures.update({keys[0]: [drugs_app.time.monotonic()], keys[1]: [drugs_app.time.monotonic()]})
    assert drugs_app._begin_auth_attempt(keys)
    drugs_app._finish_auth_attempt(keys, successful=True)
    with drugs_app._auth_failures_lock:
        assert keys[0] in drugs_app._auth_failures
        assert keys[1] not in drugs_app._auth_failures


def test_configured_runtime_secret_has_minimum_strength(drugs_app, monkeypatch):
    monkeypatch.setenv("DRUGS_COM_SECRET_KEY", "short")
    with pytest.raises(RuntimeError, match="at least 32 bytes"):
        drugs_app._load_runtime_secret_key()


def test_failed_login_key_storage_is_globally_bounded(drugs_app):
    now = drugs_app.time.monotonic()
    with drugs_app._auth_failures_lock:
        drugs_app._auth_failures.clear()
        drugs_app._auth_failures.update({
            f"account:fixture-{index}@example.com": [now]
            for index in range(drugs_app._AUTH_FAILURE_MAX_KEYS + 500)
        })
    drugs_app._record_auth_failure(("account:new@example.com",))
    with drugs_app._auth_failures_lock:
        assert len(drugs_app._auth_failures) <= drugs_app._AUTH_FAILURE_MAX_KEYS


def test_registration_capacity_is_bounded(client, drugs_app, monkeypatch):
    monkeypatch.setattr(drugs_app, "_MAX_RUNTIME_USERS", 12)
    password_hash_calls = []
    monkeypatch.setattr(drugs_app.User, "set_password", lambda _self, _password: password_hash_calls.append(True))
    page = client.get("/register")
    response = client.post("/register", data={
        "csrf_token": csrf(page), "username": "capacity_user", "email": "capacity@example.com",
        "password": "GoodPass123!", "confirm_password": "GoodPass123!", "agree_terms": "1",
    })
    assert response.status_code == 429
    assert b"reached its capacity" in response.data
    assert password_hash_calls == []


def test_login_performs_password_check_for_missing_and_existing_accounts(client, drugs_app, monkeypatch):
    calls = []
    real_check = drugs_app.bcrypt.check_password_hash

    def record_check(password_hash, password):
        calls.append(password_hash)
        return real_check(password_hash, password)

    monkeypatch.setattr(drugs_app.bcrypt, "check_password_hash", record_check)
    for email in ("missing@example.com", "alice.j@test.com"):
        page = client.get("/login")
        response = client.post("/login", data={"csrf_token": csrf(page), "email": email, "password": "wrong"})
        assert response.status_code == 200
    assert len(calls) == 2
    assert all(call.startswith("$2b$") for call in calls)


def test_registration_attempts_are_source_limited(client, drugs_app, monkeypatch):
    monkeypatch.setattr(drugs_app, "_MAX_RUNTIME_USERS", 12)
    for attempt in range(drugs_app._AUTH_FAILURE_LIMIT):
        page = client.get("/register")
        response = client.post("/register", data={
            "csrf_token": csrf(page), "username": f"capacity-{attempt}", "email": f"capacity-{attempt}@example.com",
            "password": "GoodPass123!", "confirm_password": "GoodPass123!", "agree_terms": "1",
        })
        assert response.status_code == 429
        assert b"reached its capacity" in response.data
    page = client.get("/register")
    response = client.post("/register", data={
        "csrf_token": csrf(page), "username": "capacity-final", "email": "capacity-final@example.com",
        "password": "GoodPass123!", "confirm_password": "GoodPass123!", "agree_terms": "1",
    })
    assert response.status_code == 429
    assert b"Too many account-creation attempts" in response.data


def test_registration_validation_and_duplicate(client):
    page = client.get("/register")
    response = client.post("/register", data={
        "csrf_token": csrf(page), "username": "invalid user", "email": "new@example.com",
        "password": "GoodPass123!", "confirm_password": "GoodPass123!", "agree_terms": "1",
    }, follow_redirects=True)
    assert b"Username may contain" in response.data
    page = client.get("/register")
    response = client.post("/register", data={
        "csrf_token": csrf(page), "username": "new_user", "email": "alice.j@test.com",
        "password": "GoodPass123!", "confirm_password": "GoodPass123!", "agree_terms": "1",
    }, follow_redirects=True)
    assert b"Unable to create an account with the supplied details" in response.data


def test_med_list_desired_state_is_idempotent(client, drugs_app):
    assert login(client).status_code == 302
    page = client.get("/acetaminophen")
    token = csrf(page)
    for desired in (True, True, False, False):
        response = client.post("/my-med-list/toggle", json={"slug": "acetaminophen", "saved": desired}, headers={"X-CSRFToken": token})
        assert response.status_code == 200
        assert response.json["saved"] is desired
    rows = database_rows(drugs_app._test_database_path, "SELECT COUNT(*) FROM saved_drug s JOIN drug d ON d.id=s.drug_id JOIN user u ON u.id=s.user_id WHERE u.email=? AND d.slug=?", ("alice.j@test.com", "acetaminophen"))
    assert rows == [(0,)]


def test_med_list_rejects_malformed_desired_state(client):
    assert login(client).status_code == 302
    page = client.get("/acetaminophen")
    token = csrf(page)
    response = client.post("/my-med-list/toggle", json={"slug": "acetaminophen", "saved": "maybe"}, headers={"X-CSRFToken": token})
    assert response.status_code == 400


def test_review_delete_is_owner_scoped(client, drugs_app):
    assert login(client, "bob.c@test.com").status_code == 302
    review_id = database_rows(drugs_app._test_database_path, "SELECT r.id FROM drug_review r JOIN user u ON u.id=r.user_id WHERE u.email='alice.j@test.com' LIMIT 1")[0][0]
    page = client.get("/account/reviews")
    response = client.post(f"/account/reviews/{review_id}/delete", data={"csrf_token": csrf(page)})
    assert response.status_code == 404


def test_helpful_votes_require_authentication_and_are_idempotent(client, drugs_app):
    review_id = database_rows(
        drugs_app._test_database_path,
        "SELECT r.id FROM drug_review r JOIN user u ON u.id=r.user_id JOIN drug d ON d.id=r.drug_id WHERE u.email!='alice.j@test.com' AND d.slug='ibuprofen' LIMIT 1",
    )[0][0]
    page = client.get("/login")
    unauthenticated = client.post(
        f"/ibuprofen/review/{review_id}/helpful",
        data={"csrf_token": csrf(page), "vote": "yes"},
    )
    assert unauthenticated.status_code == 302
    assert "/login" in unauthenticated.location
    assert login(client).status_code == 302
    page = client.get("/ibuprofen/reviews")
    token = csrf(page)
    first = client.post(
        f"/ibuprofen/review/{review_id}/helpful",
        data={"csrf_token": token, "vote": "yes"},
    )
    assert first.status_code == 200
    second = client.post(
        f"/ibuprofen/review/{review_id}/helpful",
        data={"csrf_token": token, "vote": "yes"},
    )
    assert second.status_code == 200
    assert second.json["votes"] == first.json["votes"]
    form_vote = client.post(
        f"/ibuprofen/review/{review_id}/helpful",
        data={"csrf_token": token, "vote": "no", "form_vote": "1"},
    )
    assert form_vote.status_code == 302
    assert "/ibuprofen/reviews" in form_vote.location


def test_review_validation_and_upsert(client, drugs_app):
    assert login(client).status_code == 302
    page = client.get("/metformin/reviews/new")
    token = csrf(page)
    invalid = client.post("/metformin/review", data={"csrf_token": token, "rating": "99", "title": "Title", "body": "Body", "condition_treated": "Diabetes"}, follow_redirects=True)
    assert b"Choose a rating from 1 to 10" in invalid.data
    page = client.get("/metformin/reviews/new")
    valid = client.post("/metformin/review", data={"csrf_token": csrf(page), "rating": "8", "title": "Fixture title", "body": "Fixture body", "condition_treated": "Diabetes"})
    assert valid.status_code == 302
    rows = database_rows(drugs_app._test_database_path, "SELECT rating,title,body FROM drug_review r JOIN drug d ON d.id=r.drug_id JOIN user u ON u.id=r.user_id WHERE d.slug='metformin' AND u.email='alice.j@test.com'")
    assert rows == [(8, "Fixture title", "Fixture body")]


def test_drug_detail_inline_interaction_form_works_without_javascript(client):
    page = client.get("/metformin")
    response = client.post(
        "/drug-interactions",
        data={"csrf_token": csrf(page), "drugs": ["metformin", "lisinopril"]},
    )
    assert response.status_code == 302
    assert "drugs=metformin" in response.location
    assert "drugs=lisinopril" in response.location


def test_interaction_post_redirects_to_auditable_query(client):
    page = client.get("/drug-interactions")
    response = client.post("/drug-interactions", data={"csrf_token": csrf(page), "drugs": ["ibuprofen", "warfarin"]})
    assert response.status_code == 302
    assert "drugs=ibuprofen" in response.location and "drugs=warfarin" in response.location
    result = client.get(response.location)
    assert result.status_code == 200
    assert b"1 interaction found" in result.data
    assert b"Major" in result.data


def test_interaction_input_validation(client):
    page = client.get("/drug-interactions")
    assert client.post("/drug-interactions", data={"csrf_token": csrf(page), "drugs": ["ibuprofen"]}).status_code == 400
    assert client.get("/drug-interactions?" + urlencode_pairs("drugs", [str(i) for i in range(21)])).status_code == 400
    response = client.post("/api/interaction-check", json={"drugs": ["x" * 121, "warfarin"]})
    assert response.status_code == 400


def urlencode_pairs(key, values):
    from urllib.parse import urlencode
    return urlencode([(key, value) for value in values])


def test_settings_form_and_email_validation(client, drugs_app):
    assert login(client).status_code == 302
    page = client.get("/account/settings")
    assert client.post("/account/settings/save", data={"csrf_token": csrf(page), "settings_form": "invalid"}).status_code == 400
    page = client.get("/account/settings")
    response = client.post("/account/settings/save", data={
        "csrf_token": csrf(page), "settings_form": "settings", "email": "alice.updated@example.com",
        "first_name": "Alice", "last_name": "Updated", "public_reviews": "on", "current_password": "TestPass123!",
    })
    assert response.status_code == 302
    rows = database_rows(drugs_app._test_database_path, "SELECT email,first_name,last_name FROM user WHERE username='alice_j'")
    assert rows == [("alice.updated@example.com", "Alice", "Updated")]
    assert client.get("/_health").status_code == 200


def test_newsletter_and_contact_are_bounded_session_flows(client):
    page = client.get("/newsletter")
    response = client.post("/newsletter/subscribe", data={"csrf_token": csrf(page), "email": "fixture@example.com", "lists": "daily_mednews"}, follow_redirects=True)
    assert b"demo browser session" in response.data
    page = client.get("/contact")
    response = client.post("/contact", data={"csrf_token": csrf(page), "name": "Fixture", "email": "fixture@example.com", "subject": "feedback", "message": "Test message"})
    assert response.status_code == 200
    assert b"receipt for your message" in response.data


def test_read_routes_do_not_mutate_database(client, drugs_app):
    before = hashlib.sha256(Path(drugs_app._test_database_path).read_bytes()).hexdigest()
    for path in ["/", "/search?q=antibiotics", "/ciprofloxacin", "/pill-identifier?shape=Oval&color=White", "/conditions/hypertension", "/new-drug-approvals"]:
        assert client.get(path).status_code == 200
    with drugs_app.app.app_context():
        drugs_app.db.session.remove()
        drugs_app.db.engine.dispose()
    after = hashlib.sha256(Path(drugs_app._test_database_path).read_bytes()).hexdigest()
    assert after == before


def test_database_constraints(drugs_app):
    connection = sqlite3.connect(drugs_app._test_database_path)
    connection.execute("PRAGMA foreign_keys=ON")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE drug_review SET rating=11 WHERE id=1")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE drug_interaction SET severity='unknown' WHERE id=1")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO saved_drug(user_id,drug_id,notes) VALUES(999999,1,'bad')")
    for statement in [
        "UPDATE drug SET availability=NULL WHERE id=1",
        "UPDATE drug SET avg_rating=NULL WHERE id=1",
        "UPDATE drug SET review_count=NULL WHERE id=1",
        "UPDATE drug_review SET helpful_count=NULL WHERE id=1",
        "UPDATE condition SET drug_count=NULL WHERE id=1",
    ]:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(statement)
    connection.close()


def test_partial_unversioned_database_fails_closed(tmp_path):
    database = tmp_path / "partial.db"
    shutil.copy2(SITE / "instance_seed" / "drugs_com.db", database)
    connection = sqlite3.connect(database)
    connection.execute("DELETE FROM seed_metadata")
    connection.commit()
    connection.close()
    environment = os.environ.copy()
    environment.update({
        "DRUGS_COM_SECRET_KEY": "subprocess-test-key-with-at-least-32-characters",
        "DRUGS_COM_DATABASE_PATH": str(database),
        "PYTHONPATH": str(SITE),
    })
    process = subprocess.run([sys.executable, "-c", "import app"], cwd=SITE, env=environment, capture_output=True, text=True, timeout=60)
    assert process.returncode != 0
    assert "partially populated, unversioned" in process.stderr


def test_mixed_availability_membership_filters(client):
    assert b"Ibuprofen" in client.get("/search?availability=OTC").data
    assert b"Ibuprofen" in client.get("/search?availability=Rx").data


def test_brand_autocomplete_is_independent_of_generic_prefix(client):
    response = client.get("/api/autocomplete?q=oz")
    assert response.status_code == 200
    assert any(row["name"] == "Ozempic" and row["url"] == "/semaglutide.html" for row in response.json)


def test_lifestyle_and_contraindicated_interactions_are_consistent(client):
    alprazolam = client.get("/drug-interactions?drugs=alprazolam&drugs=alcohol")
    assert alprazolam.status_code == 200
    assert b"Major" in alprazolam.data and b"respiratory depression" in alprazolam.data
    api = client.post("/api/interaction-check", json={"drugs": ["alprazolam", "alcohol"]})
    assert api.status_code == 200
    assert api.json["interactions"][0]["severity"] == "major"
    cipro = client.get("/drug-interactions?drugs=ciprofloxacin&drugs=tizanidine")
    assert cipro.status_code == 200
    assert b"Major" in cipro.data and b"contraindicated" in cipro.data


def test_broad_class_rules_do_not_create_false_lifestyle_rows(client, drugs_app):
    rows = database_rows(
        drugs_app._test_database_path,
        "SELECT d.generic_name,l.item FROM lifestyle_interaction l JOIN drug d ON d.id=l.drug_id "
        "WHERE d.generic_name IN ('apixaban','pravastatin','rosuvastatin') ORDER BY d.generic_name,l.item",
    )
    assert rows == []
    unknown = client.post("/api/interaction-check", json={"drugs": ["sildenafil", "nitroglycerin"]})
    assert unknown.status_code == 200
    assert unknown.json["interactions"] == []
    assert unknown.json["unrepresented_pairs"] == [["sildenafil", "nitroglycerin"]]
    assert unknown.json["coverage_complete"] is False
    assert "no_interaction_pairs" not in unknown.json
    missing_alcohol = client.post("/api/interaction-check", json={"drugs": ["ibuprofen", "alcohol"]})
    assert missing_alcohol.status_code == 200
    assert ["ibuprofen", "alcohol"] in missing_alcohol.json["unrepresented_pairs"]
    browser = client.get("/drug-interactions?drugs=sildenafil&drugs=nitroglycerin")
    assert browser.status_code == 200
    assert b"No stored coverage for 1 recognized pair" in browser.data
    assert b"sildenafil + nitroglycerin" in browser.data.lower()
    assert b"not a \xe2\x80\x9cno interaction\xe2\x80\x9d result" in browser.data


def test_internal_interaction_instructions_are_consistent(drugs_app):
    assert "at least 3 days" in drugs_app.DRUG_CONTENT_OVERRIDES["metronidazole"]["before_taking"]
    assert "at least 3 days" in drugs_app._ALCOHOL_BY_GENERIC["metronidazole"]["description"]
    simvastatin = drugs_app.DRUG_CONTENT_OVERRIDES["simvastatin"]["dosage"]
    assert "20 mg/day with amlodipine" in simvastatin
    assert "10 mg/day with diltiazem" in simvastatin


def test_pregnancy_routes_use_one_stored_value(client, drugs_app):
    for slug in ["semaglutide", "valproic-acid", "levothyroxine"]:
        row = database_rows(drugs_app._test_database_path, "SELECT pregnancy_risk FROM drug WHERE slug=?", (slug,))[0][0]
        response = client.get(f"/{slug}/pregnancy")
        assert response.status_code == 200
        assert row.encode() in response.data
    index = client.get("/pregnancy-safety")
    assert index.status_code == 200
    assert b"Semaglutide" in index.data and b"Levothyroxine" in index.data


def test_composite_pill_colors_match_component_filter(client, drugs_app):
    row = database_rows(drugs_app._test_database_path, "SELECT d.generic_name FROM drug_image i JOIN drug d ON d.id=i.drug_id WHERE i.color LIKE '%Pink/%' LIMIT 1")
    assert row
    response = client.get("/pill-identifier?color=Pink")
    assert response.status_code == 200
    assert row[0][0].lower().encode() in response.data.lower()


def test_every_declared_drug_interaction_is_persisted_once(drugs_app):
    source = {
        tuple(sorted((first, second))): severity
        for first, second, severity, _description in drugs_app.INTERACTIONS_DATA
    }
    rows = database_rows(drugs_app._test_database_path, "SELECT a.generic_name,b.generic_name,i.severity FROM drug_interaction i JOIN drug a ON a.id=i.drug_a_id JOIN drug b ON b.id=i.drug_b_id")
    persisted = {tuple(sorted((first, second))): severity for first, second, severity in rows}
    assert len(source) == len(drugs_app.INTERACTIONS_DATA) == 76
    assert persisted == source


def test_simulated_reviews_are_visibly_labeled(client):
    response = client.get("/ibuprofen/reviews")
    assert response.status_code == 200
    assert b"Simulated fixture" in response.data


def test_no_remote_runtime_media(client):
    response = client.get("/")
    assert not re.search(rb"(?:src|url)=[\"']https?://", response.data)


def test_brand_fallback_is_exact_and_rejects_sql_wildcards(client):
    assert client.get("/advil").status_code == 301
    assert client.get("/%25").status_code == 404
    assert client.get("/compare?drug1=%25").status_code == 400
    assert client.get("/compare?drug1=dvi").status_code == 400


def test_catalog_tamper_fails_runtime_health(client, drugs_app):
    with drugs_app.app.app_context():
        drugs_app.db.session.execute(
            drugs_app.text("UPDATE drug SET warnings='count-preserving tamper' WHERE slug='sildenafil'")
        )
        drugs_app.db.session.commit()
    response = client.get("/_health")
    assert response.status_code == 503
    assert response.json["ok"] is False


def test_registration_rolls_back_when_commit_fails(client, drugs_app, monkeypatch):
    page = client.get("/register")
    session_class = type(drugs_app.db.session())
    monkeypatch.setattr(
        session_class,
        "commit",
        lambda _session: (_ for _ in ()).throw(RuntimeError("injected commit failure")),
    )
    with pytest.raises(RuntimeError, match="injected commit failure"):
        client.post("/register", data={
            "csrf_token": csrf(page),
            "username": "atomic_user",
            "email": "atomic.user@example.com",
            "password": "GoodPass123!",
            "confirm_password": "GoodPass123!",
            "agree_terms": "1",
        })
    assert database_rows(
        drugs_app._test_database_path,
        "SELECT COUNT(*) FROM user WHERE email='atomic.user@example.com'",
    ) == [(0,)]


def test_client_cookie_omits_browsing_history_and_raw_anonymous_email(client):
    assert client.get("/metformin").status_code == 200
    page = client.get("/newsletter")
    response = client.post(
        "/newsletter/subscribe",
        data={"csrf_token": csrf(page), "email": "private.fixture@example.com", "lists": "daily_mednews"},
    )
    assert response.status_code == 302
    with client.session_transaction() as current_session:
        assert "recently_viewed" not in current_session
        subscription = current_session["newsletter_subscription"]
        assert "email" not in subscription
        assert subscription["email_receipt"]


def test_second_process_cannot_share_database_through_hardlink(drugs_app, tmp_path):
    alias = tmp_path / "database-alias.db"
    os.link(drugs_app._test_database_path, alias)
    environment = os.environ.copy()
    environment.update({
        "DRUGS_COM_SECRET_KEY": "subprocess-test-key-with-at-least-32-characters",
        "DRUGS_COM_DATABASE_PATH": str(alias),
        "PYTHONPATH": str(SITE),
    })
    process = subprocess.run(
        [sys.executable, "-c", "import app"],
        cwd=SITE,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert process.returncode != 0
    assert "database is already owned by another process" in process.stderr


def test_second_process_cannot_share_runtime_database(drugs_app):
    environment = os.environ.copy()
    environment.update({
        "DRUGS_COM_SECRET_KEY": "subprocess-test-key-with-at-least-32-characters",
        "DRUGS_COM_DATABASE_PATH": str(drugs_app._test_database_path),
        "PYTHONPATH": str(SITE),
    })
    process = subprocess.run(
        [sys.executable, "-c", "import app"],
        cwd=SITE,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert process.returncode != 0
    assert "database is already owned by another process" in process.stderr
