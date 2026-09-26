"""App robustness checks for the qatar_airways mirror.

Every major surface must render (200, non-empty), forms must validate,
the booking / manage / check-in / upgrade flows must persist, and the
seeded catalog must be rich enough to support search and comparison tasks.
"""
import json
import pathlib
import re

TASKS = pathlib.Path(__file__).resolve().parent.parent / "tasks.jsonl"


# ---------------------------------------------------------------- health & surfaces

def test_health(client):
    r = client.get("/_health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["airports"] >= 2000
    assert data["destinations"] == 253
    assert data["flights"] == 500
    assert data["offers"] >= 8
    assert data["users"] == 4
    assert data["bookings"] >= 7


def test_public_surfaces_render(client):
    for path in ("/", "/en/homepage.html", "/en/destinations.html",
                 "/en/offers.html", "/en/baggage.html", "/en/our-fleet.html",
                 "/en/help.html", "/en/flight-status.html",
                 "/en/manage-booking.html", "/en/check-in.html",
                 "/en/Privilege-Club/login.html", "/en/Privilege-Club/join.html",
                 "/en/Privilege-Club/membership-tiers.html"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert len(r.data) > 2000, f"{path} rendered suspiciously small"


def test_search_results_show_clean_city_names(client):
    """The picker-feed city strings (asterisk-joined search tokens) must not
    be rendered to users, and must not create unbreakable 490px tokens."""
    html = client.get("/en/search-results.html?from=DOH&to=LHR&depart=2026-10-08"
                      "&adults=1&cabin=Economy").get_data(as_text=True)
    assert "London (LHR)" in html
    assert "*heathrow*" not in html
    assert "*quatar*" not in html


def test_destination_guide_search_button_resolvable(client):
    """Every guide's 'Search flights to <city>' button must point at an
    airport code the picker feed knows (Alexandria's guide payload says
    HBE while the schedule feed serves the city as ALY)."""
    import re as _re
    from app import Airport
    for slug in ("flights-to-alexandria", "flights-to-london", "flights-to-doha"):
        html = client.get(f"/en/destinations/{slug}.html").get_data(as_text=True)
        m = _re.search(r"search-results\.html\?from=DOH&amp;to=([A-Z]{3})", html)
        assert m, f"{slug}: search button missing"
        assert Airport.query.get(m.group(1)) is not None, \
            f"{slug}: button points at unknown airport {m.group(1)}"


def test_homepage_widget_has_promo_field_and_airport_picker(client):
    """The Offers page tells users to enter a promo code in the booking
    widget, and the widget's To field promises city/airport typeahead — both
    affordances must actually exist on the homepage."""
    html = client.get("/en/homepage.html").get_data(as_text=True)
    assert 'id="promo" name="promo"' in html, "booking widget promo field missing"
    assert 'id="airport-picker"' in html, "airport typeahead datalist missing"
    assert 'list="airport-picker"' in html, "To input not wired to the picker"
    assert '<option value="LHR">' in html, "served airports missing from the picker"


def test_destination_guide_and_fleet_detail_render(client):
    r = client.get("/en/destinations/flights-to-london.html")
    assert r.status_code == 200
    assert b"London" in r.data
    r = client.get("/en/destinations/flights-to-tokyo-narita.html")
    assert r.status_code == 200
    r = client.get("/en/our-fleet/Airbus-A350-900.html")
    assert r.status_code == 200
    assert b"Qsuite" in r.data


def test_404_page(client):
    r = client.get("/en/definitely-not-a-page.html")
    assert r.status_code == 404


# ---------------------------------------------------------------- search

def test_flight_search_results(client):
    r = client.get("/en/search-results.html?from=DOH&to=LHR&depart=2026-10-08&adults=2&children=0&cabin=Economy")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "QR001" in html
    assert "Economy Lite" in html
    assert "Economy Comfort" in html


def test_flight_search_bad_route(client):
    r = client.get("/en/search-results.html?from=ZZZ&to=YYY")
    assert r.status_code == 400


def test_destination_search_is_scored(client):
    r = client.get("/en/destinations.html?q=london")
    assert r.status_code == 200
    assert "London" in r.get_data(as_text=True)
    r = client.get("/en/destinations.html?region=themiddleeast")
    assert "Doha" in r.get_data(as_text=True)


def test_help_search_is_scored(client):
    r = client.get("/en/help.html?q=hard of hearing")
    assert r.status_code == 200
    assert "833 607 2675" in r.get_data(as_text=True)


def test_flight_status_pages(client):
    r = client.get("/en/flight-status.html?mode=number&number=QR004&date=2026-09-24")
    assert r.status_code == 200
    assert "En route" in r.get_data(as_text=True)
    r = client.get("/en/flight-status.html?mode=route&from=DOH&to=SYD&date=2026-09-24")
    assert "QR908" in r.get_data(as_text=True)


# ---------------------------------------------------------------- booking flow

def _book(client, from_code="DOH", to_code="LHR", depart="2026-10-08",
          adults=2, children=0, cabin="Economy", fare="ECO_LITE",
          email="booker@example.com", last="Tester", pc_number=""):
    r = client.get(f"/en/search-results.html?from={from_code}&to={to_code}"
                   f"&depart={depart}&adults={adults}&children={children}&cabin={cabin}")
    html = r.get_data(as_text=True)
    m = re.search(rf"passenger-details\.html\?from={from_code}&amp;to={to_code}&amp;depart={depart}"
                  rf"&amp;adults={adults}&amp;children={children}&amp;cabin={cabin}"
                  rf"&amp;fare={fare}&amp;flight=(\d+)", html)
    assert m, "no matching fare select link on search results"
    flight_id = m.group(1)
    r = client.get(f"/en/booking/passenger-details.html?from={from_code}&to={to_code}"
                   f"&depart={depart}&adults={adults}&children={children}&cabin={cabin}"
                   f"&fare={fare}&flight={flight_id}")
    assert r.status_code == 200
    data = {
        "from": from_code, "to": to_code, "depart": depart, "ret": "", "ret_flight": "",
        "adults": adults, "children": children, "cabin": cabin, "fare": fare,
        "flight": flight_id, "email": email, "mobile": "+974 1234 5678",
        "pc_number": pc_number,
    }
    for i in range(adults + children):
        data.update({f"title_{i}": "Mr", f"first_{i}": f"Pax{i}",
                     f"last_{i}": last})
    r = client.post("/en/booking/passenger-details.html", data=data)
    assert r.status_code == 302, r.get_data(as_text=True)[:500]
    r = client.get("/en/booking/payment.html")
    assert r.status_code == 200
    r = client.post("/en/booking/payment.html", data={
        "card_number": "4000123456789010", "card_name": "PAX TESTER",
        "card_expiry": "12/2029", "card_cvv": "123"})
    assert r.status_code == 302
    pnr = r.headers["Location"].split("pnr=")[1]
    r = client.get(f"/en/booking/confirmation.html?pnr={pnr}")
    assert r.status_code == 200
    assert pnr.encode() in r.data
    return pnr


def test_full_booking_flow_persists(client, db):
    from app import Booking, Passenger
    pnr = _book(client)
    with db.session.no_autoflush:
        booking = Booking.query.filter_by(pnr=pnr).first()
    assert booking is not None
    assert booking.cabin == "Economy"
    assert booking.fare_type == "ECO_LITE"
    assert booking.adults == 2
    assert len(booking.passengers) == 2
    assert booking.status == "confirmed"
    assert booking.total_paid > 0
    assert Passenger.query.filter_by(booking_id=booking.id).count() == 2


def test_booking_validation_rejects_bad_input(client):
    r = client.get("/en/search-results.html?from=DOH&to=LHR&depart=2026-10-08&adults=1&children=0&cabin=Economy")
    html = r.get_data(as_text=True)
    flight_id = re.search(r"fare=ECO_LITE&amp;flight=(\d+)", html).group(1)
    r = client.post("/en/booking/passenger-details.html", data={
        "from": "DOH", "to": "LHR", "depart": "2026-10-08", "ret": "", "ret_flight": "",
        "adults": "1", "children": "0", "cabin": "Economy", "fare": "ECO_LITE",
        "flight": flight_id, "email": "not-an-email", "mobile": "x",
        "pc_number": "", "title_0": "Mr", "first_0": "", "last_0": ""})
    assert r.status_code == 400
    assert b"first and last name are required" in r.data


def test_payment_rejects_expired_card(client):
    r = client.get("/en/search-results.html?from=DOH&to=LHR&depart=2026-10-08&adults=1&children=0&cabin=Economy")
    html = r.get_data(as_text=True)
    flight_id = re.search(r"fare=ECO_LITE&amp;flight=(\d+)", html).group(1)
    client.post("/en/booking/passenger-details.html", data={
        "from": "DOH", "to": "LHR", "depart": "2026-10-08", "ret": "", "ret_flight": "",
        "adults": "1", "children": "0", "cabin": "Economy", "fare": "ECO_LITE",
        "flight": flight_id, "email": "x@example.com", "mobile": "+974 1234 5678",
        "pc_number": "", "title_0": "Mr", "first_0": "A", "last_0": "B"})
    r = client.post("/en/booking/payment.html", data={
        "card_number": "4000123456789010", "card_name": "A B",
        "card_expiry": "01/2020", "card_cvv": "123"})
    assert r.status_code == 400
    assert b"expiry must be in the future" in r.data


def test_booking_with_pc_number_credits_avios(client, db):
    from app import User
    pnr = _book(client, adults=1, fare="BUS_CLASSIC", cabin="Business",
                email="alice.j@test.com", pc_number="QRPC0004217")
    from app import Booking
    booking = Booking.query.filter_by(pnr=pnr).first()
    assert booking.pc_number == "QRPC0004217"
    alice = User.query.filter_by(email="alice.j@test.com").first()
    assert alice.avios > 48250  # earned Avios credited


def test_promo_discount_applied(client):
    r = client.get("/en/search-results.html?from=DOH&to=LHR&depart=2026-10-08&adults=1&children=0&cabin=Economy&promo=MOTOGP26")
    html = r.get_data(as_text=True)
    assert "MOTOGP26" in html
    client.post("/en/booking/passenger-details.html", data={
        "from": "DOH", "to": "LHR", "depart": "2026-10-08", "ret": "", "ret_flight": "",
        "adults": "1", "children": "0", "cabin": "Economy", "fare": "ECO_CLASSIC",
        "flight": re.search(r"fare=ECO_CLASSIC&amp;flight=(\d+)&amp;promo=MOTOGP26", html).group(1),
        "promo": "MOTOGP26", "email": "x@example.com", "mobile": "+974 1234 5678",
        "pc_number": "", "title_0": "Mr", "first_0": "A", "last_0": "B"})
    html = client.get("/en/booking/payment.html").get_data(as_text=True)
    assert "Promo MOTOGP26 discount" in html


# ---------------------------------------------------------------- manage booking

def test_manage_booking_lookup_and_cancel(client, db):
    from app import Booking
    r = client.post("/en/manage-booking.html", data={"pnr": "QR92XN", "last_name": "Johnson"})
    assert r.status_code == 302
    r = client.get("/en/manage-booking/QR92XN.html")
    assert r.status_code == 200
    r = client.post("/en/manage-booking/QR92XN.html", data={"action": "cancel"})
    assert r.status_code == 302
    booking = Booking.query.filter_by(pnr="QR92XN").first()
    assert booking.status == "cancelled"
    # wrong last name is rejected
    r = client.post("/en/manage-booking.html", data={"pnr": "QK17TP", "last_name": "Wrong"})
    assert r.status_code == 404


def test_manage_booking_adds_extra_bags(client, db):
    from app import Booking
    before = Booking.query.filter_by(pnr="QD77LW").first().total_paid
    client.post("/en/manage-booking/QD77LW.html", data={"action": "add_bags", "bags": "2"})
    booking = Booking.query.filter_by(pnr="QD77LW").first()
    assert booking.extra_bags == 2
    assert booking.total_paid == before + 280  # 2 x USD 140 on the SYD route


def test_upgrade_with_avios(client, db):
    from app import User
    r = client.post("/en/Privilege-Club/login.html",
                    data={"email": "bob.c@test.com", "password": "TestPass123!"})
    assert r.status_code == 302
    r = client.post("/en/manage-booking/QB55MD.html", data={"action": "upgrade_avios"})
    assert r.status_code == 302
    from app import Booking
    booking = Booking.query.filter_by(pnr="QB55MD").first()
    assert booking.cabin == "Business"
    assert booking.avios_redeemed == 1948
    bob = User.query.filter_by(email="bob.c@test.com").first()
    assert bob.avios == 15300 - 1948


# ---------------------------------------------------------------- check-in

def test_checkin_flow_assigns_seats_and_boards(client, db):
    r = client.post("/en/check-in.html", data={"pnr": "QC08BV", "last_name": "Davis"})
    assert r.status_code == 302
    r = client.get("/en/check-in/QC08BV.html")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    seat_fields = re.findall(r'name="seat_(\d+)"', html)
    assert len(seat_fields) == 2
    data = {f"seat_{seat_fields[0]}": "30A", f"seat_{seat_fields[1]}": "30B"}
    r = client.post("/en/check-in/QC08BV.html", data=data)
    assert r.status_code == 302
    assert "/boarding-pass" in r.headers["Location"]
    r = client.get("/en/check-in/QC08BV/boarding-pass.html")
    assert r.status_code == 200
    assert b"30A" in r.data
    from app import Booking
    booking = Booking.query.filter_by(pnr="QC08BV").first()
    assert booking.checked_in is True
    assert booking.total_paid == 6787 + 60  # two preferred seats


def test_checkin_rejects_nonexistent_seat(client):
    client.post("/en/check-in.html", data={"pnr": "QC08BV", "last_name": "Davis"})
    r = client.get("/en/check-in/QC08BV.html")
    html = r.get_data(as_text=True)
    seat_fields = re.findall(r'name="seat_(\d+)"', html)
    r = client.post("/en/check-in/QC08BV.html",
                    data={f"seat_{seat_fields[0]}": "99Z", f"seat_{seat_fields[1]}": "30B"})
    assert r.status_code == 302
    assert "/boarding-pass" not in r.headers["Location"]


# ---------------------------------------------------------------- Privilege Club

def test_pc_login_success_and_failure(client):
    r = client.post("/en/Privilege-Club/login.html",
                    data={"email": "alice.j@test.com", "password": "TestPass123!"})
    assert r.status_code == 302
    r = client.get("/en/Privilege-Club/dashboard.html")
    assert r.status_code == 200
    assert b"QK17TP" in r.data
    client.post("/en/Privilege-Club/logout.html")
    r = client.post("/en/Privilege-Club/login.html",
                    data={"email": "alice.j@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_pc_join_creates_burgundy_member(client, db):
    from app import User
    r = client.post("/en/Privilege-Club/join.html", data={
        "title": "Ms", "first_name": "Nina", "last_name": "Reyes",
        "email": "nina.reyes@example.com", "password": "Passw0rd!",
        "country": "Spain", "mobile": "+34 600 111 222"})
    assert r.status_code == 302
    user = User.query.filter_by(email="nina.reyes@example.com").first()
    assert user is not None
    assert user.tier == "Burgundy"
    assert user.membership_no.startswith("QRPC")


def test_pc_join_rejects_duplicate_email(client):
    r = client.post("/en/Privilege-Club/join.html", data={
        "title": "Ms", "first_name": "Dup", "last_name": "Dup",
        "email": "alice.j@test.com", "password": "Passw0rd!",
        "country": "Qatar", "mobile": "+974 1"})
    assert r.status_code == 400


def test_pc_dashboard_requires_login(client):
    r = client.get("/en/Privilege-Club/dashboard.html")
    assert r.status_code == 302


def test_avios_calculator(client):
    client.post("/en/Privilege-Club/login.html",
                data={"email": "alice.j@test.com", "password": "TestPass123!"})
    r = client.post("/en/Privilege-Club/avios-calculator.html",
                    data={"from": "DOH", "to": "JFK", "cabin": "Business", "tier": "Gold"})
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "3,766" in html
    assert "431" in html


def test_pc_profile_update(client, db):
    from app import User
    client.post("/en/Privilege-Club/login.html",
                data={"email": "carol.d@test.com", "password": "TestPass123!"})
    r = client.post("/en/Privilege-Club/dashboard/my-profile.html", data={
        "title": "Mrs", "first_name": "Carol", "last_name": "Davis",
        "email": "carol.d@test.com", "country": "Brazil",
        "mobile": "+55 11 98765 4321"})
    assert r.status_code == 302
    carol = User.query.filter_by(email="carol.d@test.com").first()
    assert carol.country == "Brazil"
    assert carol.mobile == "+55 11 98765 4321"


def test_csrf_required_on_post(client):
    raw = client.get("/en/manage-booking.html")
    token = re.search(r'name="csrf_token" value="([^"]+)"',
                      raw.get_data(as_text=True)).group(1)
    r = client.post("/en/manage-booking.html",
                    data={"pnr": "QR92XN", "last_name": "Johnson"},
                    environ_base={}, follow_redirects=False) if False else None
    # a fresh client without a fetched token is rejected by the CSRF guard
    with client.application.test_client() as bare:
        r = bare.post("/en/manage-booking.html",
                      data={"pnr": "QR92XN", "last_name": "Johnson",
                            "csrf_token": "bogus"})
        assert r.status_code == 400


# ---------------------------------------------------------------- baggage & fleet

def test_baggage_allowance_lookup(client):
    r = client.get("/en/baggage.html?fare=Economy Comfort&route=americas")
    assert r.status_code == 200
    assert b"2 pieces up to 23kg" in r.data
    r = client.get("/en/baggage.html?fare=Business Elite&route=weight")
    assert b"40kg" in r.data


def test_fleet_pages_show_seat_maps(client):
    r = client.get("/en/our-fleet.html")
    assert r.status_code == 200
    assert b"A350-900" in r.data and b"Qsuite" in r.data
    r = client.get("/en/our-fleet/Airbus-A380-800.html")
    assert b"First" in r.data


# ---------------------------------------------------------------- newsletter

def test_newsletter_subscribe(client, db):
    from app import Subscription
    r = client.post("/subscribe", data={
        "email": "news@example.com", "departure_city": "Doha (DOH)",
        "next": "/"})
    assert r.status_code == 302
    assert Subscription.query.filter_by(email="news@example.com").first() is not None
    r = client.post("/subscribe", data={
        "email": "news@example.com", "departure_city": "Doha (DOH)", "next": "/"})
    assert b"already subscribed" in client.get("/").data


# ---------------------------------------------------------------- task grounding

def test_seeded_bookings_match_task_references(client, db):
    """The PNRs the tasks reference must exist with the expected shape.

    Earlier tests in this suite legitimately mutate state on the shared
    scratch DB (QR92XN gets cancelled, QB55MD upgraded to Business), so
    this asserts the stable identity fields: PNR, fare type and — except
    for the upgrade candidate — cabin.
    """
    from app import Booking
    for pnr, cabin, fare in (("QK17TP", "Economy", "ECO_CLASSIC"),
                              ("QR92XN", "Business", "BUS_CLASSIC"),
                              ("QB55MD", "Economy", "ECO_LITE"),
                              ("QC08BV", "Economy", "ECO_CLASSIC"),
                              ("QD77LW", "First", "FIR_ELITE")):
        b = Booking.query.filter_by(pnr=pnr).first()
        assert b is not None, f"seeded booking {pnr} missing"
        assert b.fare_type == fare, (pnr, b.fare_type)
        if pnr != "QB55MD":  # QB55MD may have been upgraded by test_upgrade_with_avios
            assert b.cabin == cabin, (pnr, b.cabin)


def test_task_airports_and_flights_exist(client, db):
    from app import Airport, Flight
    for code in ("DOH", "LHR", "BKK", "CDG", "JFK", "SYD", "DXB", "GRU"):
        assert Airport.query.get(code) is not None, code
    for origin, dest in (("DOH", "LHR"), ("DOH", "BKK"), ("BKK", "DOH"),
                         ("DOH", "CDG"), ("DOH", "JFK"), ("DOH", "SYD"),
                         ("DOH", "DXB"), ("DOH", "GRU")):
        assert Flight.query.filter_by(origin_code=origin, dest_code=dest).first() is not None
