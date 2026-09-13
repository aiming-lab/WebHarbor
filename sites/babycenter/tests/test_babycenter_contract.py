from __future__ import annotations

import re
from datetime import date

import app as babycenter_app


def test_pregnancy_weeks_use_the_fixed_benchmark_date_and_sourced_pages() -> None:
    """Task answers must not drift with the host wall clock."""
    assert babycenter_app.REFERENCE_DATE == date(2026, 5, 29)

    with babycenter_app.app.app_context():
        assert babycenter_app.pregnancy_week_for_due_date(date(2026, 10, 30)) == 18
        assert babycenter_app.pregnancy_week_for_due_date(date(2026, 9, 18)) == 24
        assert babycenter_app.pregnancy_week_for_due_date(date(2026, 12, 18)) == 10
        assert babycenter_app.pregnancy_week_for_due_date(date(2026, 11, 30)) == 13


def test_primary_pages_render(client) -> None:
    paths = [
        "/",
        "/pregnancy/week-by-week",
        "/pregnancy/week-18",
        "/baby/month-by-month",
        "/baby/month-6",
        "/due-date-calculator",
        "/articles",
        "/articles/prenatal-screening-explained",
        "/community",
        "/community/newborn-night-wakings",
        "/search?q=sleep",
        "/login",
        "/register",
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path


def test_tests_use_an_isolated_database() -> None:
    with babycenter_app.app.app_context():
        assert "babycenter-tests-" in str(babycenter_app.db.engine.url)


def test_search_indexes_month_development_text(client) -> None:
    response = client.get("/search?q=raking+grasp")

    assert response.status_code == 200
    assert b"Month 6" in response.data


def test_due_date_rejects_non_numeric_cycle_without_server_error(client) -> None:
    response = client.post(
        "/due-date-calculator",
        data={"last_period": "2026-02-20", "cycle": "not-a-number"},
    )

    assert response.status_code == 200
    assert b"cycle length" in response.data.lower()
    assert b"Estimated due date" not in response.data


def test_due_date_rejects_implausible_cycle(client) -> None:
    response = client.post(
        "/due-date-calculator",
        data={"last_period": "2026-02-20", "cycle": "365"},
    )

    assert response.status_code == 200
    assert b"between 20 and 45 days" in response.data
    assert b"Estimated due date" not in response.data


def test_login_form_does_not_prefill_benchmark_credentials(client) -> None:
    response = client.get("/login")

    assert response.status_code == 200
    assert b'value="alice.j@test.com"' not in response.data
    assert b'value="TestPass123!"' not in response.data
    assert b"Benchmark users use password" not in response.data


def test_due_date_form_does_not_prefill_task_values(client) -> None:
    response = client.get("/due-date-calculator")

    assert response.status_code == 200
    assert b'value="2026-02-20"' not in response.data
    assert b'value="28"' not in response.data


def test_registration_is_available_and_persists_a_profile(client) -> None:
    response = client.post(
        "/register",
        data={
            "display_name": "Review Runner",
            "email": "runner@example.test",
            "password": "LongEnoughPass!",
            "due_date": "2026-12-18",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Review Runner" in response.data
    assert b"runner@example.test" in response.data


def test_login_next_url_cannot_leave_the_mirror(client) -> None:
    response = client.post(
        "/login?next=https://example.com/escape",
        data={"email": "alice.j@test.com", "password": "TestPass123!"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/account")


def test_save_referrer_cannot_leave_the_mirror(client) -> None:
    client.post(
        "/login",
        data={"email": "alice.j@test.com", "password": "TestPass123!"},
    )
    response = client.post(
        "/save/article/infant-sleep-approaches",
        headers={"Referer": "https://example.com/escape"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/account")


def test_logout_is_post_only(client) -> None:
    assert client.get("/logout").status_code == 405


def test_saved_item_can_be_removed(client) -> None:
    login = client.post(
        "/login",
        data={"email": "alice.j@test.com", "password": "TestPass123!"},
    )
    assert login.status_code == 302

    account = client.get("/account")
    match = re.search(rb'action="(/saved/\d+/remove)"', account.data)
    assert match, "account must expose a remove action for each saved item"

    removed = client.post(match.group(1).decode(), follow_redirects=True)
    assert removed.status_code == 200
    assert b"Removed from saved items" in removed.data
