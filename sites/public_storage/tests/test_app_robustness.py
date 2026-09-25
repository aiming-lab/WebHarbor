"""Route-level robustness checks for the public_storage mirror."""
import html as html_mod
import re

import pytest


def test_homepage_renders(client):
    html = client.get("/").get_data(as_text=True)
    assert "Skip the counter" in html
    assert "Find Storage" in html
    assert "800-688-8057" in html


def test_search_by_zip_redirects_to_live_slug(client):
    resp = client.get("/self-storage-search?location=98004")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/self-storage-search/bellevue-wa-98004")


def test_zip_slug_search_returns_captured_results(client):
    html = client.get("/self-storage-search/bellevue-wa-98004").get_data(as_text=True)
    assert "13640 Bel Red Road" in html
    assert "1.3 miles" in html or "1.4 miles" in html


def test_empty_search_shows_no_locations_page(client):
    html = client.get("/self-storage-search?location=").get_data(as_text=True)
    assert "No locations matched" in html or "Find a Storage Unit" in html


def test_facility_page_lists_units(client):
    html = client.get("/self-storage-wa-bellevue/81.html").get_data(as_text=True)
    assert "13640 Bel Red Road" in html
    assert "5'x5'" in html
    assert "Hold Now (No Obligation)" in html
    assert "Monthly Rent In Store" in html
    assert "Online only price" in html


def test_facility_404_for_unknown_id(client):
    assert client.get("/self-storage-wa-bellevue/999999.html").status_code == 404


def test_city_page_stats(client):
    html = client.get("/self-storage-il-chicago").get_data(as_text=True)
    assert "Self Storage Units Near You in Chicago, IL" in html
    assert "Average Cost of a Storage Unit" in html


def test_size_guide_chart(client):
    html = client.get("/size-guide").get_data(as_text=True)
    assert "Storage Closet - Reduced Height" in html
    assert "3 Bedroom home" in html
    assert "2,000" in html


def test_size_faq_page(client):
    html = client.get(
        "/size-guide/10x20-storage-unit/10x20-storage-unit.html").get_data(as_text=True)
    assert "200 square feet" in html
    assert "one-car garage" in html


def test_vehicle_faq_page(client):
    html = client.get(
        "/size-guide/vehicle-storage-unit-35-feet/vehicle-storage-unit-35-feet.html"
    ).get_data(as_text=True)
    assert "RV" in html


def test_type_pages_render(client):
    for slug, marker in [
        ("self-storage", "Self Storage"),
        ("business-storage", "Business Storage"),
        ("vehicle-car-rv-storage", "Vehicle &amp; RV Storage"),
        ("climate-controlled-storage", "Climate"),
        ("indoor-storage", "Indoor Storage"),
        ("boat-storage", "Boat Storage"),
        ("self-storage/24-hour-storage", "24 Hour"),
        ("self-storage/drive-up-storage", "Drive Up"),
    ]:
        html = client.get(f"/{slug}").get_data(as_text=True)
        assert marker in html, slug


def test_solution_pages_render(client):
    for slug in ("decluttering", "living-abroad", "military-storage",
                 "seasonal-storage", "security-features", "storage-deals",
                 "storage-faqs", "storage-for-life-transitions", "storage-lockers"):
        resp = client.get(f"/storage-solutions/{slug}")
        assert resp.status_code == 200, slug


def test_blog_index_category_article(client):
    index = client.get("/blog").get_data(as_text=True)
    assert "storage tips" in index
    cat = client.get("/blog/storage-tips").get_data(as_text=True)
    assert "Tips for Organizing a Storage Unit Like a Pro" in cat
    art = client.get(
        "/blog/storage-tips/tips-for-organizing-a-storage-unit-like-a-pro.html"
    ).get_data(as_text=True)
    assert "map it out" in art


def test_help_center(client):
    home = client.get("/help/").get_data(as_text=True)
    assert "Reservations &amp; Holds" in home
    topic = client.get("/help/reservations-and-holds").get_data(as_text=True)
    assert "seven days" in topic


def test_login_required_for_account(client):
    resp = client.get("/myaccount")
    assert resp.status_code == 302
    assert "/lease/sign-elease" in resp.headers["Location"]


def test_login_bad_credentials(client):
    resp = client.post("/lease/sign-elease", data={
        "loginEmail": "alice.j@test.com", "loginPassword": "wrong"})
    assert resp.status_code == 401


def test_account_shows_seeded_reservation(logged_in_alice):
    html = logged_in_alice.get("/myaccount").get_data(as_text=True)
    assert "PS-3184265" in html
    assert "12465 Northup Way" in html


def test_hold_flow_end_to_end(client):
    page = client.get("/reservation/hold/V_604207").get_data(as_text=True)
    assert "Hold Now (No Obligation)" in page
    resp = client.post("/reservation/hold/V_604207", data={
        "moveInDate": "10/15/2026", "holderName": "Test Walker",
        "holderEmail": "test.walker@example.com",
        "holderPhone": "(206) 555-0111"}, follow_redirects=True)
    body = resp.get_data(as_text=True)
    code = re.search(r"PS-\d{7}", body).group(0)
    assert "Your unit is on hold" in body

    # lookup succeeds with the right email, fails with a wrong one
    ok = client.post("/access-reservation", data={
        "code": code, "email": "test.walker@example.com"})
    assert code in ok.get_data(as_text=True)
    bad = client.post("/access-reservation", data={
        "code": code, "email": "someone.else@example.com"})
    assert "couldn&#39;t find a reservation" in bad.get_data(as_text=True)

    # cancel works and flips the status
    cancelled = client.post(f"/reservation/cancel/{code}", data={
        "email": "test.walker@example.com"}, follow_redirects=True)
    assert "has been cancelled" in cancelled.get_data(as_text=True)


def test_hold_form_validation(client):
    resp = client.post("/reservation/hold/V_604207", data={
        "moveInDate": "01/01/2020", "holderName": "X",
        "holderEmail": "not-an-email", "holderPhone": "123"})
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "in the past" in body
    assert "valid email" in body


def test_bill_pay_flow(logged_in_alice):
    resp = logged_in_alice.post("/simplified/bill-pay/login", data={
        "accountNumber": "483920", "email": "alice.j@test.com"},
        follow_redirects=True)
    body = resp.get_data(as_text=True)
    assert "Pay Your Bill" in body
    assert "$227.00" in body

    bad = logged_in_alice.post("/simplified/bill-pay", data={
        "cardNumber": "1111111111111111", "expiry": "12/28",
        "cvv": "12", "amount": "227.00"})
    assert bad.status_code == 400
    assert "valid card" in bad.get_data(as_text=True)

    expired = logged_in_alice.post("/simplified/bill-pay", data={
        "cardNumber": "4242424242424242", "expiry": "01/20",
        "cvv": "123", "amount": "227.00"})
    assert expired.status_code == 400
    assert "expired" in expired.get_data(as_text=True)

    ok = logged_in_alice.post("/simplified/bill-pay", data={
        "cardNumber": "4242424242424242", "expiry": "12/28",
        "cvv": "123", "amount": "227.00"}, follow_redirects=True)
    body = ok.get_data(as_text=True)
    assert "PS-PAY-" in body
    assert "$0.00" in body  # remaining balance


def test_bill_pay_requires_account_match(client):
    resp = client.post("/simplified/bill-pay/login", data={
        "accountNumber": "000000", "email": "alice.j@test.com"})
    assert resp.status_code == 401


def test_register_validation(client):
    resp = client.post("/myaccount/identity/create-account", data={
        "email": "nope", "firstName": "A", "lastName": "B",
        "phone": "1", "password": "short", "confirmPassword": "short"})
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "valid email" in body
    assert "8 characters" in body


def test_vehicle_search_filter(client):
    html = client.get(
        "/self-storage-search/denver-co-80202?type=IsVehicleUnit").get_data(as_text=True)
    assert "miles" in html
    # facilities with no vehicle spaces are filtered out of the results
    assert "2100 Blake Street" not in html
    assert "2900 Fox St" not in html
    # facilities that do carry vehicle spaces are present
    assert "6161 West 48th Ave" in html
    assert "680 Sheridan Blvd" in html


def test_health_endpoint(client):
    data = client.get("/_health").get_json()
    assert data["ok"] is True
    assert data["facilities"] >= 100
    assert data["units"] >= 1000


def test_find_storage_size_dropdown(client):
    """B-1 regression: the /find-storage form renders the full size filter
    (Select placeholder + the 7 size options), matching the upstream page."""
    html = client.get("/find-storage").get_data(as_text=True)
    select = re.search(
        r'<select id="fs-size" name="sz">(.*?)</select>', html, re.S).group(1)
    options = [html_mod.unescape(o) for o in
               re.findall(r"<option[^>]*>([^<]+)</option>", select)]
    assert options == ["Select", "All Sizes", "Small", "Medium", "Large",
                       "Up to 20'", "Up to 35'", "Up to 50'"]
    # the rendered dropdown is functional: submitting it filters results
    resp = client.get("/self-storage-search?location=Bellevue&sz=Small",
                      follow_redirects=True)
    assert resp.status_code == 200
    assert "miles" in resp.get_data(as_text=True)


def test_reservation_detail_shows_contact_phone(client):
    """C-3 regression: the reservation detail page shows the holder's phone
    alongside name and email so the full contact details are reusable."""
    resp = client.post("/access-reservation", data={
        "code": "PS-3184265", "email": "alice.j@test.com"})
    body = resp.get_data(as_text=True)
    assert "Contact phone" in body
    assert "(206) 555-0143" in body
