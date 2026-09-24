"""Robustness checks for the medicare_gov mirror: every registered route
renders non-empty content, forms validate, scored search handles partial and
multi-word queries, and bad input fails gracefully.

All tests run against the conftest scratch database (a copy of
instance_seed/medicare_gov.db), never the live worktree instance.
"""
import html
import re


def text_of(response):
    return html.unescape(response.get_data(as_text=True))


def get(client, path):
    response = client.get(path)
    assert response.status_code == 200, f"{path} -> {response.status_code}"
    body = response.get_data(as_text=True)
    assert len(body) > 500, f"{path} rendered suspiciously little content"
    return body


def test_health_endpoint(client):
    response = client.get("/_health")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "site": "medicare_gov"}


def test_public_routes_render(client):
    for path in ["/", "/basics", "/basics/costs/medicare-costs",
                 "/basics/get-started-with-medicare",
                 "/basics/your-medicare-rights",
                 "/basics/your-medicare-rights/your-rights",
                 "/basics/your-medicare-rights/your-protections",
                 "/basics/reporting-medicare-fraud-and-abuse",
                 "/basics/end-stage-renal-disease",
                 "/basics/report-a-death",
                 "/coverage", "/coverage/find-alphabetically",
                 "/coverage/popular-topics",
                 "/care-compare/", "/care-compare/providers/physicians",
                 "/medical-equipment-suppliers/",
                 "/medical-equipment-suppliers/directory",
                 "/plan-compare/", "/publications", "/talk-to-someone",
                 "/account/login", "/sitemap"]:
        get(client, path)


def test_coverage_detail_pages(client, app):
    from app import CoverageItem
    with app.app_context():
        slugs = [row[0] for row in CoverageItem.query.with_entities(CoverageItem.slug).limit(20)]
    for slug in slugs:
        body = get(client, f"/coverage/{slug}")
        assert "Ask your doctor" in body


def test_scored_search_partial_and_multiword(client):
    body = get(client, "/coverage/search?q=glaucoma")
    assert "Glaucoma screenings" in body
    body = get(client, "/coverage/search?q=blood sugar monitor")
    assert "Blood sugar monitors" in body
    body = text_of(client.get("/coverage/search?q=yearly wellness visit"))
    assert 'Yearly "Wellness" visits' in body
    body = get(client, "/coverage/search?q=zzzznotathing")
    assert "couldn't find" in html.unescape(body)


def test_provider_search_and_detail(client):
    body = get(client, "/care-compare/search?type=Physician&loc=Springfield,%20IL")
    assert "doctors" in body.lower()
    body = get(client, "/care-compare/search?type=Hospital&loc=Springfield,%20IL")
    assert "Memorial Medical Center" in body
    body = get(client, "/care-compare/search?type=NursingHome&loc=Nowhere")
    assert "couldn't find" in body


def test_dme_search_and_equipment_filter(client):
    body = get(client, "/medical-equipment-suppliers/results?location=62701")
    assert "Sc Home Health Nfp" in body
    body = get(client, "/medical-equipment-suppliers/results?location=62701&equipment=Walkers")
    assert "(217) 522-2403" in body
    body = get(client, "/medical-equipment-suppliers/results?location=99999")
    assert "couldn't find" in body


def test_plan_finder_flow(client):
    body = get(client, "/plan-compare/search?zip=62701")
    assert "Aetna Medicare Premier (HMO)" in body
    body = get(client, "/plan-compare/search?zip=62701&plan_choice=drug")
    assert "Humana Walmart Value Rx (PDP)" in body
    body = get(client, "/plan-compare/search?zip=99999")
    assert "couldn't find" in body


def test_publications_search_filters(client):
    body = get(client, "/publications/search?category=Rights%20and%20protections")
    assert body.count('class="pub-card"') == 4
    body = get(client, "/publications/search?q=Choosing+a+Medigap+Policy")
    assert "02110" in body


def test_login_flow_and_stateful_actions(client, app):
    from app import PremiumBill, User

    response = client.post("/account/login", data={
        "email": "alice.j@test.com", "password": "wrong"}, follow_redirects=True)
    assert "isn't right" in text_of(response)

    response = client.post("/account/login", data={
        "email": "alice.j@test.com", "password": "TestPass123!"}, follow_redirects=True)
    assert "/my/dashboard" in response.request.path

    # premium bill appears and can be paid
    body = get(client, "/my/premiums")
    assert "202.90" in body
    with app.app_context():
        alice = User.query.filter_by(email="alice.j@test.com").first()
        bill = PremiumBill.query.filter_by(user_id=alice.id, status="Due").first()
        assert bill is not None
    response = client.post(f"/my/premiums/pay/{bill.id}",
                           data={"method": "Bank account ending 4821"},
                           follow_redirects=True)
    assert "Paid" in text_of(response)

    # paying someone else's bill must fail closed
    with app.app_context():
        bob = User.query.filter_by(email="bob.c@test.com").first()
        other_bill = PremiumBill.query.filter_by(user_id=bob.id, status="Due").first()
    response = client.post(f"/my/premiums/pay/{other_bill.id}",
                           data={"method": "Bank account ending 4821"})
    assert response.status_code == 404

    # address change validates and persists
    response = client.post("/my/account-settings/change-address", data={
        "line1": "x", "city": "", "state": "III", "zip": "12"},
        follow_redirects=True)
    text = text_of(response)
    assert "Enter a city." in text or "2-letter" in text
    response = client.post("/my/account-settings/change-address", data={
        "line1": "12 Oak Lane", "city": "Springfield", "state": "IL", "zip": "62704"},
        follow_redirects=True)
    assert "12 Oak Lane" in text_of(response)

    # replacement card requires a reason
    response = client.post("/my/account-settings/get-my-medicare-card",
                          data={"reason": ""}, follow_redirects=True)
    assert "Choose a reason" in text_of(response)


def test_404_pages(client):
    for path in ["/coverage/no-such-item", "/basics/no-such-page",
                 "/care-compare/provider/99999999",
                 "/plan-compare/plan/99999",
                 "/publication-ordering/00000"]:
        response = client.get(path)
        assert response.status_code == 404, path
