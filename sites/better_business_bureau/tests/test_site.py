"""Better Business Bureau mirror — regression tests.

Run from the repository root:
    python3 -m pytest sites/better_business_bureau/tests/test_site.py -q
"""
import json
import pathlib
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))

from app import (Business, Complaint, Review, ScamReport, app, db,  # noqa: E402
                   seed_database, seed_benchmark_users)
import seed_data  # noqa: E402

@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_health(client):
    response = client.get("/_health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["site"] == "better_business_bureau"
    assert payload["businesses"] > 0
    assert payload["scam_reports"] > 0


def test_homepage_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "TRUST," in body
    assert "Find a business" in body
    assert "Apply for Accreditation" in body
    assert "Better Business Bureau" in body


def test_search_returns_results(client):
    response = client.get("/search?find_text=auto+repair&find_loc=Redmond%2C+WA")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "results for auto repair near Redmond, WA" in body
    assert "BBB Rating:" in body


def test_search_scored_not_strict_and(client):
    # "auto body repair shop redmond" — token overlap must match several shops
    response = client.get("/search?find_text=auto+body+shop&find_loc=Redmond%2C+WA")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert body.count("result-card") >= 3


def test_search_filters(client):
    response = client.get("/search?find_text=auto+repair&find_loc=Redmond%2C+WA&accredited=y")
    body = response.get_data(as_text=True)
    assert "BBB Rating:" in body
    # every rendered card carries the accredited seal
    assert body.count("bds-accredited-seal") == body.count("result-card")


def test_search_rating_filter(client):
    response = client.get("/search?find_text=auto+repair&find_loc=Redmond%2C+WA&ratings=F")
    assert response.status_code == 200


def test_search_pagination(client):
    response = client.get("/search?find_text=auto+repair&find_loc=Seattle%2C+WA&page=2")
    assert response.status_code == 200
    assert "pagination" in response.get_data(as_text=True) or "result-card" in response.get_data(as_text=True)


def _first_business(client):
    with app.app_context():
        biz = Business.query.filter_by(city="Redmond").order_by(Business.id).first()
        return biz


def test_business_profile_main(client):
    with app.app_context():
        biz = Business.query.order_by(Business.id).first()
        response = client.get(biz.profile_path())
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert biz.name in body
    assert "About This Business" in body
    assert "Business Details" in body


def test_business_profile_reviews_tab(client):
    with app.app_context():
        biz = (Business.query.filter(Business.reviews.any()).first())
        if not biz:
            pytest.skip("no seeded business with reviews")
        response = client.get(biz.profile_path() + "/customer-reviews")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Customer Review Ratings" in body or "This business has 0 reviews" in body


def test_business_profile_complaints_tab(client):
    with app.app_context():
        biz = (Business.query.filter(Business.complaints.any()).first())
        if not biz:
            pytest.skip("no seeded business with complaints")
        response = client.get(biz.profile_path() + "/complaints")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Customer Complaints Summary" in body
    assert "total complaints in the last 3 years" in body


def test_profile_404(client):
    response = client.get("/us/wa/redmond/profile/not-a-category/not-a-business-1296-999999")
    assert response.status_code == 404
    assert "Page not found" in response.get_data(as_text=True)


def test_scam_lookup_and_detail(client):
    response = client.get("/scamtracker/lookupscam")
    assert response.status_code == 200
    assert "Search Results" in response.get_data(as_text=True)
    with app.app_context():
        report = ScamReport.query.order_by(ScamReport.scam_id).first()
        scam_id = report.scam_id
    response = client.get(f"/scamtracker/lookupscam/{scam_id}")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Scam ID" in body
    assert str(scam_id) in body


def test_scam_lookup_filters(client):
    with app.app_context():
        report = ScamReport.query.filter(ScamReport.dollar_value > 0).first()
        if not report:
            pytest.skip("no scam with losses seeded")
        response = client.get(f"/scamtracker/lookupscam?scam_type={report.scam_type.replace(' ', '+')}")
    assert response.status_code == 200
    assert report.scam_type in response.get_data(as_text=True)


def test_scam_dashboard(client):
    response = client.get("/scamtracker/dashboard")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Heatmap" in body
    assert "Scam Reports by location" in body


def test_report_scam_flow(client):
    response = client.post("/scamtracker/reportscam", data={
        "scam_type": "Phishing",
        "description": "Fake delivery text message with a payment link, reported by the regression test.",
        "target_city": "Redmond", "target_state": "WA", "target_zip": "98052",
        "scammer_phone": "(555) 555-0111", "dollar_value": "0",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Thank you" in response.get_data(as_text=True)


def test_leave_review_flow(client):
    with app.app_context():
        biz = Business.query.order_by(Business.id).first()
        before = Review.query.filter_by(business_id=biz.id).count()
        response = client.post(f"/leave-a-review/{biz.id}", data={
            "rating": "4",
            "text": "Regression test review: the team was professional and the work finished on schedule.",
            "author": "Test User",
            "experience_date": "2026-09-01",
        }, follow_redirects=True)
        after = Review.query.filter_by(business_id=biz.id).count()
    assert response.status_code == 200
    assert after == before + 1


def test_benchmark_users_exist(client):
    with app.app_context():
        from app import User
        for email in ("alice.j@test.com", "bob.c@test.com", "carol.d@test.com", "david.k@test.com"):
            assert User.query.filter_by(email=email).first() is not None, email


def test_signin_and_account(client):
    response = client.post("/signin", data={
        "email": "alice.j@test.com", "password": "TestPass123!"}, follow_redirects=True)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Alice Johnson" in body
    response = client.get("/account")
    assert response.status_code == 200
    assert "Saved businesses" in response.get_data(as_text=True)


def test_signin_wrong_password(client):
    response = client.post("/signin", data={
        "email": "alice.j@test.com", "password": "wrong"}, follow_redirects=True)
    assert "incorrect" in response.get_data(as_text=True)


def test_seed_idempotent(client):
    with app.app_context():
        before_business = Business.query.count()
        before_scam = ScamReport.query.count()
        before_complaint = Complaint.query.count()
        seed_database()
        seed_benchmark_users()
        assert Business.query.count() == before_business
        assert ScamReport.query.count() == before_scam
        assert Complaint.query.count() == before_complaint


def test_intake_search_routes_render_results(client):
    """Regression for the tuple-unpacking 500s on the three intake flows."""
    for route in ("get-a-quote", "leave-a-review", "file-a-complaint"):
        response = client.get(f"/{route}?find_text=Car+Tender")
        assert response.status_code == 200, route
        body = response.get_data(as_text=True)
        assert "Car Tender" in body, route


def test_get_a_quote_search_only_lists_quote_offers(client):
    with app.app_context():
        quotes = [b.id for b in Business.query.filter_by(offers_quotes=True).all()]
        no_quote = Business.query.filter_by(offers_quotes=False).first()
    response = client.get("/get-a-quote?find_text=auto+repair&find_loc=Redmond%2C+WA")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    if no_quote is not None:
        assert no_quote.name not in body or no_quote.offers_quotes


def test_tasks_jsonl_schema():
    """Row schema across the contribution + reviewer grading contract.

    Contributor rows carry the 5 task-definition keys; the reviewer's grading
    pass appends verifier_path + judge_rubric (see sites/<site>/verify/).
    There is never an `answer` key (the agent reads this file; an answer key
    would leak answers).
    """
    tasks_path = SITE / "tasks.jsonl"
    if not tasks_path.exists():
        pytest.skip("tasks.jsonl not written yet")
    seen_ids = set()
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        assert set(row) == {"web_name", "id", "ques", "web", "upstream_url",
                            "verifier_path", "judge_rubric"}, row
        assert "answer" not in row
        assert row["web"] == "http://localhost:40063/"
        assert row["upstream_url"] == "https://www.bbb.org/"
        assert row["id"].startswith("Better Business Bureau--")
        assert row["id"] not in seen_ids
        # reviewer grading contract: one deterministic verifier + rule rubric
        assert row["verifier_path"].startswith("sites/better_business_bureau/verify/verify_")
        assert row["verifier_path"].endswith(".py")
        assert pathlib.Path(SITE.parent.parent, row["verifier_path"]).is_file(), row["verifier_path"]
        assert "FACT CHECKPOINTS" in row["judge_rubric"]
        assert "MUST" in row["judge_rubric"]
        seen_ids.add(row["id"])
