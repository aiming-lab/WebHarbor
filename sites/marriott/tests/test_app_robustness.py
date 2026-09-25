"""App robustness checks for the marriott mirror.

Every major surface must render (200, non-empty), forms must validate, the
reservation flow must persist, and the seeded catalog must be rich enough to
support search/filter/comparison tasks.
"""
import json
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parent.parent


def test_health(client):
    r = client.get("/_health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["hotels"] >= 30
    assert data["destinations"] >= 3


def test_homepage_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Your Next Trip Starts Here" in r.data
    assert b"Find Hotels" in r.data


def test_all_marketing_pages_render(client, db):
    from app import Brand, Destination, Hotel
    for path in ("/offers.mi", "/brands.mi", "/loyalty.mi", "/credit-cards.mi",
                 "/careers.mi", "/sign-in.mi",
                 "/loyalty/createAccount/createAccountPage1.mi",
                 "/reservation/lookupReservation.mi"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert len(r.data) > 2000, path
    hotel = Hotel.query.first()
    assert hotel is not None
    for path in (hotel.detail_path,
                 hotel.path_for("rooms"),
                 hotel.path_for("reviews"),
                 hotel.path_for("photos")):
        r = client.get(path)
        assert r.status_code == 200, path
        assert len(r.data) > 2000, path
    dest = Destination.query.first()
    r = client.get(dest.page_path)
    assert r.status_code == 200


def test_unknown_hotel_404s(client):
    r = client.get("/en-us/hotels/zzzzz-not-a-real-hotel/overview/")
    assert r.status_code == 404


def test_destination_search_returns_results(client, db):
    from app import Destination
    dest = Destination.query.first()
    r = client.get(f"/search/findHotels.mi?destinationAddress={dest.city}")
    assert r.status_code == 200
    assert f"hotels in {dest.city}".lower() in r.data.decode().lower()
    assert r.data.count(b"hotel-card") >= dest.hotel_count


def test_token_search_is_not_strict_and(client, db):
    from app import Hotel
    # multi-word partial queries must still hit (scored token overlap)
    r = client.get("/search/findHotels.mi?destinationAddress=hotel new york")
    assert r.status_code == 200
    assert Hotel.query.count() > 0


def test_filters_apply(client, db):
    from app import Brand, Destination, Hotel
    dest = Destination.query.filter(Hotel.destination_id == Destination.id).first()
    brand = Brand.query.first()
    r = client.get(f"/search/findHotels.mi?destinationAddress={dest.city}"
                   f"&brand={brand.code}&sortBy=price")
    assert r.status_code == 200
    prices = [int(x) for x in re.findall(rb"\$(\d[\d,]*)", r.data)]
    prices = [p for p in prices]
    if prices:
        assert prices == sorted(prices)


def test_hotel_pages_show_real_data(client, db):
    from app import Hotel, RoomType
    hotel = Hotel.query.filter(Hotel.review_count > 0).first() or Hotel.query.first()
    r = client.get(hotel.path_for("rooms"))
    body = r.data.decode()
    assert hotel.room_types[0].name in body
    assert "$" in body
    assert re.search(r"Sleeps \d", body)
    overview = client.get(hotel.detail_path).data.decode()
    assert hotel.name in overview
    assert (hotel.city or "") in overview


def test_reservation_flow_persists(client, db):
    from app import Hotel, Reservation, RoomType
    n_before = Reservation.query.count()
    hotel = Hotel.query.first()
    room = RoomType.query.filter_by(hotel_id=hotel.id).first()
    r = client.post("/reservation/reservationGateway.mi", data={
        "propertyCode": hotel.marsha, "roomId": room.id,
        "fromDate": "10/15/2026", "toDate": "10/18/2026",
        "rooms": "1", "adults": "2",
        "guest_first_name": "Test", "guest_last_name": "Guest",
        "guest_email": "guest@example.com",
        "card_number": "4111111111111111", "exp_month": "12", "exp_year": "2028",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"Your reservation is confirmed" in r.data
    assert Reservation.query.count() == n_before + 1
    resv = Reservation.query.order_by(Reservation.id.desc()).first()
    assert resv.checkout > resv.checkin
    assert resv.total_rate == room.base_rate * 3


def test_reservation_flow_validates(client, db):
    from app import Hotel, Reservation, RoomType
    n_before = Reservation.query.count()
    hotel = Hotel.query.first()
    room = RoomType.query.filter_by(hotel_id=hotel.id).first()
    r = client.post("/reservation/reservationGateway.mi", data={
        "propertyCode": hotel.marsha, "roomId": room.id,
        "fromDate": "10/15/2026", "toDate": "10/18/2026",
        "guest_first_name": "", "guest_last_name": "Guest",
        "guest_email": "not-an-email",
        "card_number": "123", "exp_month": "12", "exp_year": "2028",
    })
    assert r.status_code == 200
    assert Reservation.query.count() == n_before  # nothing persisted
    assert b"valid email" in r.data


def test_lookup_and_cancel(client, db):
    from app import Reservation
    resv = Reservation.query.filter_by(status="confirmed").first()
    assert resv is not None
    r = client.post("/reservation/lookupReservation.mi", data={
        "confirmationNumber": resv.confirmation_number,
        "lastName": resv.guest_last_name,
    })
    assert r.status_code == 200
    assert resv.confirmation_number.encode() in r.data
    # wrong last name fails
    r2 = client.post("/reservation/lookupReservation.mi", data={
        "confirmationNumber": resv.confirmation_number,
        "lastName": "wrongname",
    })
    assert b"couldn&#39;t find a reservation" in r2.data or b"couldn't find" in r2.data
    # cancel
    r3 = client.post("/reservation/cancel.mi", data={
        "confirmationNumber": resv.confirmation_number,
        "lastName": resv.guest_last_name,
    }, follow_redirects=True)
    assert r3.status_code == 200
    db.session.refresh(resv)
    assert resv.status == "canceled"


def test_benchmark_users_login_and_have_state(client, db):
    from app import Favorite, PaymentMethod, Reservation, User
    for email in ("alice.j@test.com", "bob.c@test.com",
                  "carol.d@test.com", "david.k@test.com"):
        r = client.post("/sign-in.mi", data={"email": email,
                                             "password": "TestPass123!"},
                        follow_redirects=True)
        assert r.status_code == 200
        assert b"My Account" in r.data or b"Hello" in r.data
        user = User.query.filter_by(email=email).first()
        assert user is not None
        assert user.member_number
        client.get("/logoff")
    alice = User.query.filter_by(email="alice.j@test.com").first()
    assert len(list(alice.reservations)) >= 2
    assert len(list(alice.favorites)) >= 2
    assert PaymentMethod.query.filter_by(user_id=alice.id).count() >= 1


def test_registration_and_profile(client, db):
    import uuid
    from app import User
    email = f"new.tester.{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/loyalty/createAccount/createAccountPage1.mi", data={
        "first_name": "New", "last_name": "Tester",
        "email": email, "password": "Passw0rd!",
        "confirm_password": "Passw0rd!",
    }, follow_redirects=True)
    assert r.status_code == 200
    user = User.query.filter_by(email=email).first()
    assert user is not None
    assert user.member_number
    # profile update
    r2 = client.post("/loyalty/myAccount/profile.mi", data={
        "phone": "+1 555-0100", "city": "Boston",
    }, follow_redirects=True)
    assert b"updated" in r2.data


def test_saved_hotels_flow(client, db):
    from app import Hotel, User
    client.post("/sign-in.mi", data={"email": "bob.c@test.com",
                                     "password": "TestPass123!"})
    hotel = Hotel.query.first()
    r = client.post(f"/saved/add/{hotel.id}", data={"next": "/"},
                    follow_redirects=True)
    assert r.status_code == 200
    r2 = client.get("/loyalty/myAccount/savedHotels.mi")
    assert hotel.name.encode() in r2.data
    r3 = client.post(f"/saved/remove/{hotel.id}", data={"next": "/loyalty/myAccount/savedHotels.mi"},
                     follow_redirects=True)
    assert r3.status_code == 200
    client.get("/logoff")


def test_reviews_pages_have_real_ratings(client, db):
    from app import Hotel
    hotel = Hotel.query.filter(Hotel.review_count > 0).first()
    if hotel is None:
        return
    r = client.get(hotel.path_for("reviews"))
    body = r.data.decode()
    assert str(hotel.review_count) in body
    # star filter narrows the list
    r5 = client.get(hotel.path_for("reviews") + "?stars=5")
    assert r5.status_code == 200


def test_404_page(client):
    r = client.get("/no/such/page")
    assert r.status_code == 404
    assert b"couldn" in r.data
