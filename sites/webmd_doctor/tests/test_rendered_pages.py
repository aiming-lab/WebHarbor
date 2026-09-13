"""Rendered-page sweep for the WebMD Doctor mirror.

Renders every content route (all 226 doctor profiles, hospitals, practices,
specialty hubs, awards, auth and account pages) through the Flask test client
and asserts: HTTP 200, the sitewide mirror notice, no unrendered Jinja syntax,
no internal build vocabulary leaks, and the progressive-enhancement hooks.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
SEED = SITE / "instance_seed" / "webmd_doctor.db"

FORBIDDEN_MARKERS = (
    "{{", "{%", "lorem", "TODO:", "VERIFIED_NPIS", "PYTHONHASHSEED",
    "instance_seed", "webmd_doctor.db", "seed_data",
)


@pytest.fixture(scope="module")
def client():
    sys.path.insert(0, str(SITE))
    try:
        import app as app_module

        app_module.app.config["TESTING"] = True
        app_module.app.config["WTF_CSRF_ENABLED"] = False
        with app_module.app.test_client() as test_client:
            yield test_client
    finally:
        sys.path.pop(0)


def _slugs(table: str) -> list[str]:
    connection = sqlite3.connect(SEED)
    try:
        return [row[0] for row in connection.execute(f"SELECT slug FROM {table} ORDER BY id")]
    finally:
        connection.close()


def _assert_clean(response, path: str) -> str:
    assert response.status_code == 200, f"{path} -> {response.status_code}"
    body = response.get_data(as_text=True)
    assert "mirror-notice" in body, f"{path} lacks the mirror notice"
    lowered = body.lower()
    for marker in FORBIDDEN_MARKERS:
        assert marker.lower() not in lowered, f"{path} leaks internal marker {marker!r}"
    return body


def test_every_content_route_renders_clean(client):
    paths = [
        "/", "/results?q=Dermatologist&sids=29244", "/providers/specialty",
        "/hospitals", "/hospitals/delaware", "/hospitals/maryland",
        "/grouppractices", "/grouppractices/delaware", "/grouppractices/maryland",
        "/choice-awards", "/choice-awards/awardrecipients?award-class=elite",
        "/choice-awards/awardrecipients?award-class=patient",
        "/choice-awards/awardrecipients?award-class=provider",
        "/reviews-guidelines", "/login", "/signup",
    ]
    for spec in _slugs("specialties"):
        paths.append(f"/providers/specialty/{spec}")
        paths.append(f"/providers/specialty/{spec}/delaware")
    for slug in _slugs("doctors"):
        paths.append(f"/doctor/{slug}-overview")
    for slug in _slugs("hospitals"):
        paths.append(f"/hospital/{slug}")
    for slug in _slugs("practices"):
        paths.append(f"/practice/{slug}")
    for path in paths:
        _assert_clean(client.get(path), path)
    # Health endpoints answer JSON, not chrome.
    for path in ("/_health", "/health"):
        response = client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}"
        assert response.get_json()["ok"] is True


def test_account_pages_render_clean_when_signed_in(client):
    response = client.post("/login", data={
        "email": "alice.j@test.com", "password": "TestPass123!", "csrf_token": ""})
    assert response.status_code == 302
    for path in ("/account/saved", "/account/appointments"):
        _assert_clean(client.get(path), path)


def test_progressive_enhancement_hooks_present(client):
    body = _assert_clean(client.get("/"), "/")
    assert 'classList.add("js")' in body, "html.js bootstrapping script missing"
    assert "skip-link" in body, "skip link missing"
    # Select-driven forms expose a noscript submit fallback.
    slug = _slugs("hospitals")[0]
    hospital_body = _assert_clean(client.get(f"/hospital/{slug}"), f"/hospital/{slug}")
    assert "<noscript>" in hospital_body, "no-JS submit fallback missing on hospital page"
    recipients = _assert_clean(
        client.get("/choice-awards/awardrecipients?award-class=elite"), "awardrecipients")
    assert "<noscript>" in recipients, "no-JS submit fallback missing on recipients page"


def test_booking_pages_render_for_enhanced_profiles_only(client):
    client.post("/logout", data={"csrf_token": ""})  # isolate from the signed-in test above
    connection = sqlite3.connect(SEED)
    try:
        enhanced = [row[0] for row in connection.execute(
            "SELECT slug FROM doctors WHERE profile_type='Enhanced' ORDER BY id LIMIT 5")]
        standard = [row[0] for row in connection.execute(
            "SELECT slug FROM doctors WHERE profile_type!='Enhanced' ORDER BY id LIMIT 5")]
    finally:
        connection.close()
    for slug in enhanced:
        response = client.get(f"/doctor/{slug}/bookappointment")
        assert response.status_code == 302, f"enhanced {slug} should redirect to login"
    for slug in standard:
        response = client.get(f"/doctor/{slug}/bookappointment")
        assert response.status_code == 404, f"standard {slug} must not expose booking"
