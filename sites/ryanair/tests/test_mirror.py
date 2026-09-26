"""Self-check suite for the ryanair mirror.

Run from sites/ryanair/:  python3 -m pytest tests/ -q

The suite runs against a temporary database seeded from scratch (pointed to
via RYANAIR_DB_URI before importing the app) so it never mutates the seed.
"""
import os
import pathlib
import re
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SITE = HERE.parent
sys.path.insert(0, str(SITE))

TMP = tempfile.mkdtemp(prefix='ryanair-tests-')
DB_PATH = os.path.join(TMP, 'ryanair.db')
os.environ['RYANAIR_DB_URI'] = f'sqlite:///{DB_PATH}'

from app import (app, db, Airport, Route, FlightSchedule, User, Booking,  # noqa: E402
                  BookingPassenger, HelpTopic, PromoCode, flight_price,
                  seat_price, MIRROR_TODAY)

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False
client = app.test_client()

SELECT_URL = ('/gb/en/trip/flights/select?originIata=STN&destinationIata=DUB'
              '&dateOut=2026-10-13&dateIn=2026-10-20&adults=2&isReturn=true')


def _csrf(path):
    r = client.get(path)
    m = re.search(rb'name="csrf_token" value="([^"]+)"', r.data)
    return m.group(1).decode() if m else ''


def _walk_booking(fare='basic', seats=None, bags=None, extras=None,
                  contact='guest@example.com'):
    """Drive the whole booking chain; returns the confirmation response."""
    r = client.get(SELECT_URL)
    out = re.findall(r'FR (\d+).*?name="schedule_id" value="(\d+)"',
                     r.data.decode(), re.S)
    out_id = dict((f, i) for f, i in out).get('271')
    in_id = dict((f, i) for f, i in out).get('30')
    client.post('/gb/en/trip/flights/select',
                data={'action': 'select_outbound', 'schedule_id': out_id})
    client.post('/gb/en/trip/flights/select',
                data={'action': 'select_inbound', 'schedule_id': in_id})
    client.post('/gb/en/trip/flights/select',
                data={'action': 'choose_fare', 'fare': fare})
    client.post('/gb/en/trip/flights/select', data={
        'action': 'save_passengers', 'title_0': 'Mr', 'first_0': 'John',
        'last_0': 'Smith', 'title_1': 'Mrs', 'first_1': 'Jane',
        'last_1': 'Doe'})
    if seats == 'skip':
        client.post('/gb/en/trip/flights/seats', data={'action': 'random'})
    elif seats:
        data = {'action': 'pick'}
        for i, seat in enumerate(seats.get('out', [])):
            data[f'seat_out_{i}'] = seat
        for i, seat in enumerate(seats.get('in', [])):
            data[f'seat_in_{i}'] = seat
        client.post('/gb/en/trip/flights/seats', data=data)
    bag_data = {'action': 'save', 'cabin_default': 'small-bag',
                'same_both_flights': 'on'}
    if bags:
        bag_data.update(bags)
    client.post('/gb/en/trip/flights/bags', data=bag_data)
    client.post('/gb/en/trip/flights/extras',
                data={'action': 'save', **(extras or {})})
    return client.post('/gb/en/payment', data={
        'action': 'pay', 'contactEmail': contact,
        'contactEmail2': contact, 'contactPhone': '+44 7700 900999',
        'cardNumber': '4242424242424242', 'cardName': 'John Smith',
        'cardExpiry': '09/29', 'cardCvv': '123', 'address1': '1 Test Street',
        'city': 'London', 'postcode': 'E1 6AN'}, follow_redirects=True)


def _reach_payment():
    """Walk the chain up to (not including) the payment submit."""
    client.get(SELECT_URL)
    r = client.get(SELECT_URL)
    out = re.findall(r'FR (\d+).*?name="schedule_id" value="(\d+)"',
                     r.data.decode(), re.S)
    out_id = dict((f, i) for f, i in out).get('271')
    in_id = dict((f, i) for f, i in out).get('30')
    client.post('/gb/en/trip/flights/select',
                data={'action': 'select_outbound', 'schedule_id': out_id})
    client.post('/gb/en/trip/flights/select',
                data={'action': 'select_inbound', 'schedule_id': in_id})
    client.post('/gb/en/trip/flights/select',
                data={'action': 'choose_fare', 'fare': 'basic'})
    client.post('/gb/en/trip/flights/select', data={
        'action': 'save_passengers', 'title_0': 'Mr', 'first_0': 'John',
        'last_0': 'Smith'})
    client.post('/gb/en/trip/flights/seats', data={'action': 'random'})
    client.post('/gb/en/trip/flights/bags',
                data={'action': 'save', 'cabin_default': 'small-bag'})
    client.post('/gb/en/trip/flights/extras', data={'action': 'save'})
    return client.get('/gb/en/payment')


# ------------------------------------------------------------- smoke tests --

def test_health():
    r = client.get('/_health')
    assert r.status_code == 200
    body = r.get_json()
    assert body['ok'] is True and body['site'] == 'ryanair'


def test_seed_volume():
    with app.app_context():
        assert Airport.query.count() >= 160
        assert Route.query.count() >= 1500
        assert FlightSchedule.query.count() >= 3000
        assert User.query.count() == 4
        assert HelpTopic.query.count() >= 15
        assert Booking.query.count() >= 6


def test_real_stn_dub_schedule():
    with app.app_context():
        sched = FlightSchedule.query.filter_by(flight_number='FR 271').first()
        assert sched is not None
        assert sched.departure == '06:30' and sched.arrival == '07:50'
        assert sched.route.origin_code == 'STN'
        assert sched.route.destination_code == 'DUB'


def test_price_determinism():
    with app.app_context():
        s = FlightSchedule.query.filter_by(flight_number='FR 271').first()
        d = MIRROR_TODAY.replace(month=10, day=13)
        assert flight_price(s, d) == flight_price(s, d)
        # fare multipliers are ordered
        basic = flight_price(s, d, 'basic')
        assert flight_price(s, d, 'regular') > basic
        assert flight_price(s, d, 'plus') > flight_price(s, d, 'regular')
        assert flight_price(s, d, 'flexi_plus') > flight_price(s, d, 'plus')


def test_seat_pricing_bands():
    assert seat_price(1) == 21.50
    assert seat_price(3) == 14.00
    assert seat_price(7) == 13.50
    assert seat_price(15) == 9.50
    assert seat_price(16) == 14.50
    assert seat_price(33) == 9.50


def test_homepage_renders():
    r = client.get('/gb/en')
    assert r.status_code == 200
    assert b'search-widget' in r.data
    assert b'RYANAIR10' in r.data


def test_static_pages():
    for path in ['/gb/en/route-map', '/gb/en/r/help', '/gb/en/lp/check-in',
                 '/gb/en/lp/gift-cards', '/gb/en/my-bookings']:
        assert client.get(path).status_code == 200, path


def test_flights_to_pages():
    for slug in ['dublin', 'malaga', 'barcelona', 'paris', 'alicante']:
        r = client.get(f'/flights/gb/en/flights-to-{slug}')
        assert r.status_code == 200, slug
        assert b'Book flights to' in r.data


def test_help_search():
    r = client.get('/gb/en/r/help?q=bags')
    assert r.status_code == 200
    assert b'Cabin Bag Policy' in r.data


def test_fees_table_page():
    r = client.get('/gb/en/r/help/fees')
    assert b'20kg Check-in Bag' in r.data
    assert b'\xc2\xa325.49' in r.data      # £25.49 online
    assert b'\xc2\xa350.00' in r.data      # £50.00 airport


def test_timetable():
    r = client.get('/gb/en/trip/flights/timetable?originIata=STN&destinationIata=DUB')
    assert r.status_code == 200
    assert b'FR 271' in r.data and b'06:30' in r.data


def test_fare_finder_filters():
    r = client.get('/gb/en/cheap-flight-destinations?originIata=STN')
    cards_all = r.data.count(b'ff-card__name')
    r = client.get('/gb/en/cheap-flight-destinations?originIata=STN&maxPrice=15')
    cards_15 = r.data.count(b'ff-card__name')
    assert cards_all > 20
    assert 0 < cards_15 < cards_all


# ------------------------------------------------------------ booking flow --

def test_full_booking_chain_basic():
    r = _walk_booking(seats='skip')
    assert r.status_code == 200
    assert b'Your trip is booked' in r.data
    ref = re.search(rb'confirm-ref">([A-Z0-9]+)<', r.data).group(1).decode()
    with app.app_context():
        b = Booking.query.filter_by(booking_ref=ref).first()
        assert b.fare_type == 'basic'
        assert b.total == round(b.flights_total + b.seats_total + b.bags_total
                                + b.extras_total + b.card_fee, 2)
        assert b.card_fee == round((b.total - b.card_fee) * 0.02, 2)
        assert len(b.passengers) == 2
        assert all(p.seat_out == '' for p in b.passengers)


def test_booking_with_seats_bags_extras():
    # find guaranteed-free seats for the outbound/inbound legs
    with app.app_context():
        out_sched = FlightSchedule.query.filter_by(flight_number='FR 271').first()
        in_sched = FlightSchedule.query.filter_by(flight_number='FR 30').first()
        out_day = MIRROR_TODAY.replace(month=10, day=13)
        in_day = MIRROR_TODAY.replace(month=10, day=20)
        occ_out = out_sched.occupied_seats(out_day)
        occ_in = in_sched.occupied_seats(in_day)
        free_out, free_in = [], []
        for row in (18, 19, 20, 21, 22):
            for letter in 'ABCDEF':
                seat = f'{row}{letter}'
                if seat not in occ_out and len(free_out) < 2:
                    free_out.append(seat)
                if seat not in occ_in and len(free_in) < 2:
                    free_in.append(seat)
    r = _walk_booking(
        fare='plus', seats={'out': free_out, 'in': free_in},
        bags={'cabin_default': 'priority', 'bag_20kg_out_0': '1'},
        extras={'fast_track_STN': 'on', 'fast_track_DUB': 'on',
                'insurance': 'plus'})
    assert r.status_code == 200
    ref = re.search(rb'confirm-ref">([A-Z0-9]+)<', r.data).group(1).decode()
    with app.app_context():
        b = Booking.query.filter_by(booking_ref=ref).first()
        assert b.fare_type == 'plus'
        assert b.seats_total == round(seat_price(18) * 4, 2)
        # priority x2 pax x2 flights + 20kg x2 flights
        assert b.bags_total == round(16.0 * 2 * 2 + 25.49 * 1 * 2, 2)
        # fast track both airports x2 pax + insurance plus (8 days x2 pax)
        assert b.extras_total == round(8.49 * 2 + 12.03 * 2 + 1.90 * 8 * 2, 2)
        assert b.passengers[0].seat_out == free_out[0]
        assert b.passengers[0].cabin_out == 'priority'


# -------------------------------------------- one-way pricing regressions --
# Review diff #1 (HIGH): a one-way trip has no return leg, so bags/priority
# must be charged for the outbound flight only. The old code mirrored the
# outbound selection onto a phantom inbound leg and priced both directions.

OW_SELECT_URL = ('/gb/en/trip/flights/select?originIata=STN&destinationIata=DUB'
                 '&dateOut=2026-10-14&adults=1&isReturn=false')


def _walk_one_way_booking(bags=None, contact='ow@example.com'):
    """Drive a one-way STN-DUB 14 Oct booking chain (1 adult, Basic)."""
    r = client.get(OW_SELECT_URL)
    out = re.findall(r'FR (\d+).*?name="schedule_id" value="(\d+)"',
                     r.data.decode(), re.S)
    out_id = dict((f, i) for f, i in out).get('291')   # FR 291: cheapest that day
    assert out_id, 'FR 291 must operate STN-DUB on 14 Oct'
    client.post('/gb/en/trip/flights/select',
                data={'action': 'select_outbound', 'schedule_id': out_id})
    client.post('/gb/en/trip/flights/select',
                data={'action': 'choose_fare', 'fare': 'basic'})
    client.post('/gb/en/trip/flights/select', data={
        'action': 'save_passengers', 'title_0': 'Ms', 'first_0': 'Kim',
        'last_0': 'Lee'})
    client.post('/gb/en/trip/flights/seats', data={'action': 'random'})
    bag_data = {'action': 'save', 'cabin_default': 'small-bag'}
    if bags:
        bag_data.update(bags)
    client.post('/gb/en/trip/flights/bags', data=bag_data)
    client.post('/gb/en/trip/flights/extras', data={'action': 'save'})
    return client.post('/gb/en/payment', data={
        'action': 'pay', 'contactEmail': contact,
        'contactEmail2': contact, 'contactPhone': '+44 7700 900999',
        'cardNumber': '4242424242424242', 'cardName': 'Kim Lee',
        'cardExpiry': '09/29', 'cardCvv': '123', 'address1': '1 Test Street',
        'city': 'London', 'postcode': 'E1 6AN'}, follow_redirects=True)


def test_one_way_bag_charged_once():
    # even a stale "same both flights" flag must not mirror bags onto the
    # non-existent return leg of a one-way trip
    r = _walk_one_way_booking(bags={'bag_20kg_out_0': '1',
                                    'same_both_flights': 'on'})
    assert r.status_code == 200
    ref = re.search(rb'confirm-ref">([A-Z0-9]+)<', r.data).group(1).decode()
    with app.app_context():
        b = Booking.query.filter_by(booking_ref=ref).first()
        assert b.inbound_schedule_id is None
        assert b.fare_type == 'basic' and b.adults == 1
        # the 20kg bag is charged for the single outbound leg only
        assert b.bags_total == 25.49
        assert b.total == round(b.flights_total + b.bags_total
                                + b.card_fee, 2)
        assert b.total == 45.36      # frozen re-review contract value
        p = b.passengers[0]
        assert p.checkin_20kg_out == 1 and p.checkin_20kg_in == 0
        assert p.cabin_in == 'small-bag'


def test_one_way_priority_charged_once():
    r = _walk_one_way_booking(bags={'cabin_default': 'priority'})
    assert r.status_code == 200
    ref = re.search(rb'confirm-ref">([A-Z0-9]+)<', r.data).group(1).decode()
    with app.app_context():
        b = Booking.query.filter_by(booking_ref=ref).first()
        assert b.bags_total == 16.00          # priority once, not twice
        p = b.passengers[0]
        assert p.cabin_out == 'priority' and p.cabin_in == 'small-bag'


def test_promo_code_discount():
    url = (SELECT_URL + '&promoCode=RYANAIR10')
    r = client.get(url)
    assert b'RYANAIR10' in r.data
    with app.app_context():
        promo = db.session.get(PromoCode, 'RYANAIR10')
        assert promo.discount_pct == 10
        s = FlightSchedule.query.filter_by(flight_number='FR 271').first()
        d = MIRROR_TODAY.replace(month=10, day=13)
        assert flight_price(s, d, 'basic', 10) < flight_price(s, d, 'basic')


def test_payment_validation():
    _reach_payment()
    r = client.post('/gb/en/payment', data={
        'action': 'pay', 'contactEmail': 'bad', 'contactEmail2': 'other',
        'contactPhone': '', 'cardNumber': '12', 'cardName': '',
        'cardExpiry': '99/99', 'cardCvv': 'x', 'address1': '', 'city': '',
        'postcode': ''}, follow_redirects=True)
    assert b'valid email' in r.data
    assert b'valid card number' in r.data
    assert b'valid expiry' in r.data
    assert b'billing address' in r.data


# ------------------------------------------------------------------ account --

def _login(email='alice.j@test.com', password='TestPass123!'):
    return client.post('/gb/en/myryanair/login',
                       data={'email': email, 'password': password},
                       follow_redirects=True)


def test_auth_account_and_bookings():
    r = _login()
    assert b'welcome back' in r.data
    r = client.get('/gb/en/myryanair/account')
    assert b'Payment methods' in r.data
    assert b'P4H2KQ' in r.data          # seeded past booking
    assert b'T7W3ND' in r.data          # seeded upcoming booking


def test_profile_and_card_update():
    _login()
    r = client.post('/gb/en/myryanair/account', data={
        'action': 'profile', 'first': 'Alice', 'last': 'Johnson',
        'phone': '+44 7700 900777', 'address1': '12 Kingsland Road',
        'address2': '', 'city': 'London', 'postcode': 'E2 8AA'},
        follow_redirects=True)
    assert b'Your details have been updated' in r.data
    r = client.post('/gb/en/myryanair/account', data={
        'action': 'add_card', 'cardNumber': '5555555555554444',
        'cardName': 'Alice Johnson', 'cardExpiry': '05/28'},
        follow_redirects=True)
    assert b'Payment method added' in r.data
    assert b'ending 4444' in r.data


def test_remove_default_card_promotes_remaining():
    # Review diff #3 (LOW): upstream promotes a remaining card to default
    # when the default card is removed, so "which is the default" stays
    # answerable on the account page.
    _login()
    client.post('/gb/en/myryanair/account', data={
        'action': 'add_card', 'cardNumber': '5500000000005559',
        'cardName': 'Alice Johnson', 'cardExpiry': '07/29'})
    with app.app_context():
        alice = User.query.filter_by(email='alice.j@test.com').first()
        default = next(c for c in alice.payment_methods if c.is_default)
        assert default.last4 == '4242'          # the seeded Visa is default
        remove_id = default.id
        n_before = len(alice.payment_methods)
    r = client.post('/gb/en/myryanair/account', data={
        'action': 'remove_card', 'card_id': str(remove_id)},
        follow_redirects=True)
    assert b'Payment method removed' in r.data
    with app.app_context():
        alice = User.query.filter_by(email='alice.j@test.com').first()
        cards = alice.payment_methods
        assert len(cards) == n_before - 1
        defaults = [c for c in cards if c.is_default]
        assert len(defaults) == 1
        assert defaults[0].id == max(c.id for c in cards)
        assert defaults[0].last4 == '5559'
    r = client.get('/gb/en/myryanair/account')
    assert b'badge--confirmed">default' in r.data


def test_guest_booking_lookup():
    client.get('/gb/en/myryanair/logout')
    r = client.post('/gb/en/my-bookings', data={
        'ref': 'T7W3ND', 'email': 'alice.j@test.com'}, follow_redirects=True)
    assert b'T7W3ND' in r.data
    r = client.post('/gb/en/my-bookings', data={
        'ref': 'T7W3ND', 'email': 'wrong@example.com'}, follow_redirects=True)
    assert b'could not find' in r.data


# ------------------------------------------------------------------- check-in --

def test_checkin_flow_open_and_boarding_pass():
    _login('david.k@test.com')
    r = client.get('/gb/en/check-in/R2M6YB')
    assert b'Check in now' in r.data        # assigned seats: 60-day window
    r = client.post('/gb/en/check-in/R2M6YB', data={'action': 'checkin'},
                    follow_redirects=True)
    assert b'BOARDING PASS' in r.data
    with app.app_context():
        b = Booking.query.filter_by(booking_ref='R2M6YB').first()
        assert b.checked_in is True
        assert b.passengers[0].seat_out == '1A'


def test_checkin_not_open_for_random_seats():
    _login('bob.c@test.com')
    r = client.get('/gb/en/check-in/M9D2XV')
    assert b'Online check-in opens 24 hours' in r.data
    r = client.post('/gb/en/check-in/M9D2XV', data={'action': 'checkin'},
                    follow_redirects=True)
    assert b'please come back later' in r.data
    with app.app_context():
        b = Booking.query.filter_by(booking_ref='M9D2XV').first()
        assert b.checked_in is False


# ---------------------------------------------------------------- idempotence --

def test_seed_idempotence():
    """Re-running the seed functions on a populated DB must be a no-op."""
    import app as app_mod
    with app_mod.app.app_context():
        before = db.session.query(db.func.count(Booking.id)).scalar()
        app_mod.seed_database()
        app_mod.seed_benchmark_users()
        after = db.session.query(db.func.count(Booking.id)).scalar()
    assert before == after
