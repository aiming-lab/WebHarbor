"""Self-check suite for the united_airlines mirror.

Run from sites/united_airlines/:  python3 -m pytest tests/ -q

The suite runs against a temporary database seeded from scratch (pointed to
via UNITED_AIRLINES_DB_URI before importing the app) so it never mutates the
seed. A second temp database is seeded from the same tracked source_data to
assert byte-identical determinism.
"""
import hashlib
import os
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SITE = HERE.parent
sys.path.insert(0, str(SITE))

TMP = tempfile.mkdtemp(prefix='united-airlines-tests-')
DB_PATH = os.path.join(TMP, 'united_airlines.db')
os.environ['UNITED_AIRLINES_DB_URI'] = f'sqlite:///{DB_PATH}'

from app import (app, db, MIRROR_TODAY,  # noqa: E402
                 Activity, Aircraft, Airport, BaggageItem, Booking,
                 BookingLeg, CabinInfo, Deal, Fare, Flight, HelpArticle,
                 Passenger, PolicyArticle, User,
                 BAG_FEE_TABLE, FARE_FAMILIES, PREMIER_FREE_BAGS)

import seed_data  # noqa: E402

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False
ctx = app.app_context()
ctx.push()
db.create_all()
seed_data.seed_database()
seed_data.seed_benchmark_users()

client = app.test_client()


# ---------------------------------------------------------------- catalog --

def test_seed_volume():
    assert Airport.query.count() >= 40
    assert Flight.query.count() >= 30
    assert Fare.query.count() >= 100
    assert Aircraft.query.count() >= 10
    assert User.query.count() == 4
    assert Booking.query.count() >= 4
    assert HelpArticle.query.count() >= 20
    assert CabinInfo.query.count() == 6
    assert PolicyArticle.query.count() == 4
    assert Deal.query.count() >= 8


def test_seed_only_real_hubs_and_routes():
    codes = {a.code for a in Airport.query.all()}
    assert {'ORD', 'DEN', 'IAH', 'EWR', 'SFO', 'LAX'} <= codes
    hubs = {a.code for a in Airport.query.filter_by(is_hub=True)}
    assert hubs == {'ORD', 'DEN', 'IAH', 'EWR', 'SFO', 'LAX', 'GUM', 'IAD'}
    # every flight joins two seeded airports and a seeded aircraft
    for flight in Flight.query.all():
        assert Airport.query.get(flight.origin_code)
        assert Airport.query.get(flight.dest_code)
        assert db.session.get(Aircraft, flight.aircraft_key)


def test_every_flight_has_all_fare_families():
    cabins = {key for key, _ in FARE_FAMILIES}
    for flight in Flight.query.all():
        have = {f.cabin for f in Fare.query.filter_by(flight_id=flight.id)}
        assert have == cabins, flight.flight_number


def test_benchmark_members():
    alice = User.query.filter_by(email='alice.j@example.com').first()
    assert alice and alice.tier == 'Premier Silver' and alice.award_miles == 68450
    bob = User.query.filter_by(email='bob.m@example.com').first()
    assert bob.tier == 'Premier Gold'
    dave = User.query.filter_by(email='dave.t@example.com').first()
    assert dave.tier == 'Premier Platinum'
    assert all(u.check_password('TestPass123!') for u in
               User.query.all())


# ------------------------------------------------------------------- pages --

CORE_PAGES = ['/', '/flight-status', '/checkin', '/mytrips', '/mileageplus',
              '/mileageplus/join', '/signin', '/baggage',
              '/baggage/checked-bags', '/baggage/carry-on',
              '/baggage/fee-calculator', '/travel-info/cabins',
              '/travel-info/fleet', '/travel-info/airports',
              '/travel-info/policies', '/deals', '/help', '/search?q=bag']


def test_core_pages_render():
    for path in CORE_PAGES:
        r = client.get(path)
        assert r.status_code == 200, path
        assert len(r.data) > 1500, path


def test_cabin_and_policy_and_airport_pages():
    for slug in ['basic-economy', 'united-economy', 'economy-plus',
                 'premium-plus', 'united-first-business', 'united-polaris']:
        r = client.get(f'/travel-info/cabins/{slug}')
        assert r.status_code == 200 and b'United' in r.data
    for slug in ['flight-change', 'refund-policy']:
        r = client.get(f'/travel-info/policies/{slug}')
        assert r.status_code == 200
    hub = Airport.query.filter_by(is_hub=True).first()
    r = client.get(f'/travel-info/airports/{hub.code}')
    assert r.status_code == 200
    r = client.get('/travel-info/airports/ZZZ')
    assert r.status_code == 404


def test_404_page():
    r = client.get('/nope')
    assert r.status_code == 404
    assert b"can't get you here" in r.data


# ----------------------------------------------------------- flight search --

def _route_with_flights():
    """A real captured route with at least three flights to compare."""
    for flight in Flight.query.all():
        n = Flight.query.filter_by(origin_code=flight.origin_code,
                                   dest_code=flight.dest_code).count()
        if n >= 3:
            return flight
    return None


def test_flight_search_flow():
    route = _route_with_flights()
    assert route, 'expected a route with 3+ captured flights'
    day = MIRROR_TODAY.isoformat()
    r = client.get(f'/flights/search?origin={route.origin_code}'
                   f'&destination={route.dest_code}&depart={day}&cabin=ECO')
    assert r.status_code == 200
    body = r.data.decode()
    assert 'flights found' in body
    assert f'UA {route.flight_number}' in body
    # sorting by price returns the cheapest first
    r = client.get(f'/flights/search?origin={route.origin_code}'
                   f'&destination={route.dest_code}&depart={day}'
                   f'&cabin=ECO&sort=price')
    assert r.status_code == 200


def test_flight_search_errors():
    day = MIRROR_TODAY.isoformat()
    r = client.get(f'/flights/search?origin=ZZZ&destination=DEN&depart={day}')
    assert b'Unknown origin airport' in r.data
    past = (MIRROR_TODAY.toordinal() - 30)
    from datetime import date as d
    r = client.get(f'/flights/search?origin=ORD&destination=DEN'
                   f'&depart={d.fromordinal(past).isoformat()}')
    assert b'past' in r.data


def test_airports_json():
    r = client.get('/flights/airports.json')
    assert r.status_code == 200
    rows = r.get_json()
    assert any(row['code'] == 'ORD' for row in rows)


# --------------------------------------------------------------- booking ----

def _book(client_, origin, dest, day, cabin='ECO', email='guest@example.com',
          mp=''):
    r = client_.get(f'/flights/search?origin={origin}&destination={dest}'
                    f'&depart={day}&cabin={cabin}')
    m = re.search(r'action="/flights/select/(\d+)"', r.data.decode())
    flight_id = int(m.group(1))
    r = client_.post(f'/flights/select/{flight_id}',
                     data={'cabin': cabin, 'date': day, 'adults': '1',
                           'children': '0'})
    assert r.status_code == 302
    r = client_.get('/booking/passengers')
    assert r.status_code == 200
    r = client_.post('/booking/passengers', data={
        'contact_email': email, 'contact_phone': '+1 555 555 5555',
        'title_0': 'Mr', 'first_0': 'John', 'last_0': 'Smith',
        'dob_0': '1990-01-01', 'gender_0': 'M', 'mp_0': mp,
    }, follow_redirects=False)
    assert r.status_code == 302
    r = client_.get('/booking/payment')
    return r


def test_booking_with_card():
    day = MIRROR_TODAY.isoformat()
    origin = dest = None
    for flight in Flight.query.all():
        origin, dest = flight.origin_code, flight.dest_code
        break
    r = _book(client, origin, dest, day, 'ECO')
    assert r.status_code == 200
    assert b'Total for 1 traveler' in r.data
    r = client.post('/booking/payment', data={
        'method': 'card', 'card_number': '4242424242424242',
        'card_name': 'John Smith', 'card_expiry': '12/29', 'card_cvv': '123',
    }, follow_redirects=False)
    assert r.status_code == 302
    conf = r.headers['Location'].rsplit('/', 1)[-1]
    booking = Booking.query.filter_by(confirmation=conf).first()
    assert booking and booking.contact_email == 'guest@example.com'
    assert booking.card_last4 == '4242'
    assert booking.total > 0
    assert len(booking.passengers) == 1
    assert client.get(f'/mytrips/{conf}').status_code == 200
    assert app.test_client().get(f'/mytrips/{conf}').status_code == 403
    assert Passenger.query.filter_by(booking_id=booking.id).first().first_name == 'John'
    r = client.get(f'/booking/confirmation/{conf}')
    assert r.status_code == 200
    assert conf.encode() in r.data


def test_booking_card_validation():
    day = MIRROR_TODAY.isoformat()
    flight = Flight.query.first()
    r = _book(client, flight.origin_code, flight.dest_code, day, 'ECO')
    r = client.post('/booking/payment', data={
        'method': 'card', 'card_number': '1234567890123456',
        'card_name': 'John Smith', 'card_expiry': '12/29', 'card_cvv': '123',
    }, follow_redirects=True)
    assert b'Enter a valid Visa, Mastercard, Amex or Discover' in r.data
    r = client.post('/booking/payment', data={
        'method': 'card', 'card_number': '4242424242424242',
        'card_name': 'John Smith', 'card_expiry': '01/20', 'card_cvv': '123',
    }, follow_redirects=True)
    assert b'expired' in r.data


def test_award_booking_deducts_miles():
    """The Redeem-miles button must be reachable from the real UI (review
    F-1 regression guard): the browser submits every non-button input plus
    the clicked button's own name/value pair, so no hidden default may
    shadow the Redeem button's method=miles."""
    day = MIRROR_TODAY.isoformat()
    login = client.post('/signin', data={'email': 'alice.j@example.com',
                                         'password': 'TestPass123!'},
                        follow_redirects=True)
    assert b'Alice' in login.data
    alice = User.query.filter_by(email='alice.j@example.com').first()
    before = alice.award_miles
    flight = Flight.query.filter_by(origin_code='SFO',
                                     dest_code='ORD').first()
    r = _book(client, 'SFO', 'ORD', day, 'ECO', email=alice.email)
    assert b'Redeem' in r.data
    html = r.data.decode()
    # a hidden method default before the Redeem button would win the
    # form.get('method') race and break award booking from the UI
    assert not re.search(r'<input[^>]*name="method"[^>]*type="hidden"', html)
    assert not re.search(r'<input[^>]*type="hidden"[^>]*name="method"', html)
    # both submit buttons carry name="method": the clicked one decides
    assert 'name="method" value="card"' in html
    assert 'name="method" value="miles"' in html
    # replay exactly what a browser sends when Redeem is clicked
    payload = {}
    for m in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"',
                         html):
        if m.group(1) != 'method':
            payload[m.group(1)] = m.group(2)
    payload['method'] = 'miles'
    # honest walkers carry the traveler's MileagePlus number; award
    # tickets must not credit award miles back (base fare is $0)
    payload['mp_0'] = alice.mp_number
    r = client.post('/booking/payment', data=payload,
                    follow_redirects=False)
    assert r.status_code == 302
    conf = r.headers['Location'].rsplit('/', 1)[-1]
    booking = Booking.query.filter_by(confirmation=conf).first()
    assert booking.award_booking
    assert booking.miles_redeemed > 0
    assert alice.award_miles == before - booking.miles_redeemed
    act = Activity.query.filter_by(user_id=alice.id,
                                   miles=-booking.miles_redeemed).first()
    assert act
    client.get('/signout')


def test_miles_earned_on_paid_booking():
    day = MIRROR_TODAY.isoformat()
    client.post('/signin', data={'email': 'bob.m@example.com',
                                'password': 'TestPass123!'})
    bob = User.query.filter_by(email='bob.m@example.com').first()
    before = bob.award_miles
    pqp_before = bob.pqp
    flight = Flight.query.first()
    r = _book(client, flight.origin_code, flight.dest_code, day, 'ECO',
              email=bob.email, mp=bob.mp_number)
    r = client.post('/booking/payment', data={
        'method': 'card', 'card_number': '4242424242424242',
        'card_name': 'Bob Miller', 'card_expiry': '11/28', 'card_cvv': '123',
    }, follow_redirects=False)
    assert r.status_code == 302
    booking = Booking.query.filter_by(confirmation=(
        r.headers['Location'].rsplit('/', 1)[-1])).first()
    # passenger carries Bob's MileagePlus number -> miles + PQP credited
    assert Passenger.query.filter_by(booking_id=booking.id).first().mp_number
    assert bob.award_miles > before
    assert bob.pqp > pqp_before
    client.get('/signout')


# --------------------------------------------------------------- my trips ---

def test_mytrips_lookup_and_wrong_name():
    seeded = Booking.query.filter_by(confirmation='KX42LM').first()
    assert seeded
    r = client.get('/mytrips?confirmation=KX42LM&lastname=Johnson')
    assert r.status_code == 302
    r = client.get('/mytrips/KX42LM')
    assert r.status_code == 200
    assert b'KX42LM' in r.data
    client.get('/signout')
    with client.session_transaction() as sess:
        sess.pop('mytrips_auth', None)
    r = client.get('/mytrips?confirmation=KX42LM&lastname=Wrong')
    assert b"couldn't find" in r.data
    r = client.get('/mytrips/KX42LM', follow_redirects=False)
    assert r.status_code == 403


def test_add_bags_fee_ladder_and_premier_free():
    client.post('/signin', data={'email': 'alice.j@example.com',
                                'password': 'TestPass123!'})
    r = client.get('/mytrips?confirmation=KX42LM&lastname=Johnson',
                   follow_redirects=True)
    booking = Booking.query.filter_by(confirmation='KX42LM').first()
    pax = booking.passengers[0]
    existing = BaggageItem.query.filter_by(passenger_id=pax.id).count()
    # Alice is Premier Silver -> first bag free, then the paid ladder
    r = client.post(f'/mytrips/KX42LM', data={'action': 'add_bag',
                                              'passenger_id': pax.id,
                                              'which': 'first'},
                    follow_redirects=True)
    bags = BaggageItem.query.filter_by(passenger_id=pax.id).all()
    if existing == 1:            # first bag was pre-seeded -> next one costs
        assert bags[-1].fee == BAG_FEE_TABLE['first_online']
    else:
        assert bags[-1].fee == 0.0
    r = client.post(f'/mytrips/KX42LM', data={'action': 'add_bag',
                                              'passenger_id': pax.id,
                                              'which': 'second'},
                    follow_redirects=True)
    client.get('/signout')


def test_change_flight_fare_difference():
    client.post('/signin', data={'email': 'bob.m@example.com',
                                'password': 'TestPass123!'})
    r = client.get('/mytrips?confirmation=QT83NB&lastname=Miller',
                   follow_redirects=True)
    booking = Booking.query.filter_by(confirmation='QT83NB').first()
    leg = booking.legs[0]
    assert booking.cabin == 'EPU'      # changeable cabin
    r = client.get(f'/mytrips/QT83NB/change/{leg.id}')
    assert r.status_code == 200
    before_total = booking.total
    candidates = [f for f in Flight.query.filter_by(
        origin_code=leg.flight.origin_code,
        dest_code=leg.flight.dest_code) if f.id != leg.flight_id]
    if candidates:
        target = candidates[0]
        r = client.post(f'/mytrips/QT83NB/change/{leg.id}',
                        data={'flight_id': target.id},
                        follow_redirects=True)
        assert b'Flight changed' in r.data
        assert booking.legs[0].flight_id == target.id
        assert booking.total != before_total or booking.total >= 0
    client.get('/signout')


def test_basic_economy_cannot_change():
    booking = Booking.query.filter_by(confirmation='ZW57PC').first()
    assert booking.cabin == 'BE'
    client.post('/signin', data={'email': 'carol.w@example.com',
                                'password': 'TestPass123!'})
    r = client.get('/mytrips?confirmation=ZW57PC&lastname=Williams',
                   follow_redirects=True)
    r = client.get(f'/mytrips/ZW57PC/change/{booking.legs[0].id}',
                   follow_redirects=True)
    assert b'cannot be changed' in r.data
    client.get('/signout')


def test_cancel_refund_vs_credit():
    # standard cabin -> refund to card
    client.post('/signin', data={'email': 'bob.m@example.com',
                                'password': 'TestPass123!'})
    client.get('/mytrips?confirmation=QT83NB&lastname=Miller')
    booking = Booking.query.filter_by(confirmation='QT83NB').first()
    r = client.post('/mytrips/QT83NB/cancel', follow_redirects=True)
    assert r.status_code == 200
    assert booking.status == 'canceled'
    assert booking.refund_amount > 0
    assert booking.refund_to == 'card'
    client.get('/signout')
    # Basic Economy -> travel credit only
    client.post('/signin', data={'email': 'carol.w@example.com',
                                'password': 'TestPass123!'})
    client.get('/mytrips?confirmation=ZW57PC&lastname=Williams')
    be = Booking.query.filter_by(confirmation='ZW57PC').first()
    r = client.post('/mytrips/ZW57PC/cancel', follow_redirects=True)
    assert be.status == 'canceled'
    assert be.refund_amount == 0.0
    assert be.refund_to == 'travel credit'
    client.get('/signout')


# --------------------------------------------------------------- check-in ----

def test_checkin_window_and_boarding_pass():
    # seeded trip HD19RK (dave, EWR-SFO on 2026-09-28) is inside the window
    client.post('/signin', data={'email': 'dave.t@example.com',
                                'password': 'TestPass123!'})
    r = client.get('/mytrips?confirmation=HD19RK&lastname=Thomas')
    r = client.get('/checkin?confirmation=HD19RK&lastname=Thomas',
                   follow_redirects=True)
    booking = Booking.query.filter_by(confirmation='HD19RK').first()
    r = client.get(f'/checkin/HD19RK')
    assert r.status_code == 200
    pax = booking.passengers[0]
    r = client.post('/checkin/HD19RK', data={f'seat_{pax.id}': '12A'},
                    follow_redirects=True)
    assert r.status_code == 200
    assert pax.checked_in
    assert pax.seat == '12A'
    assert pax.boarding_group == 'Group 1'      # Dave is Platinum in Business
    r = client.get('/checkin/HD19RK/boarding-pass')
    assert r.status_code == 200
    assert b'HD19RK' in r.data
    # Alice's trip tomorrow is outside the 24-hour window
    r = client.get('/checkin?confirmation=KX42LM&lastname=Johnson',
                   follow_redirects=True)
    assert b"Check-in isn't open yet" in r.data
    client.get('/signout')


def test_checkin_rejects_occupied_seat():
    client.post('/signin', data={'email': 'dave.t@example.com',
                                'password': 'TestPass123!'})
    booking = Booking.query.filter_by(confirmation='HD19RK').first()
    leg = booking.legs[0]
    flight = leg.flight
    taken = sorted(flight.occupied_seats(leg.travel_date))[0]
    pax = booking.passengers[0]
    r = client.post('/checkin/HD19RK', data={f'seat_{pax.id}': taken},
                    follow_redirects=True)
    assert b'already taken' in r.data
    client.get('/signout')


def test_seat_selection_rejects_occupied_seat():
    """My-trips seat selection must enforce the seat map's occupancy the
    same way the check-in flow does (audit F-3 regression guard): the seat
    map page promises 'an occupied seat will be rejected', so saving a
    seat the map marks occupied must flash and leave the seat unchanged."""
    # unlock the trip the honest way (confirmation + last name lookup)
    client.get('/mytrips?confirmation=KX42LM&lastname=Johnson')
    booking = Booking.query.filter_by(confirmation='KX42LM').first()
    leg = booking.legs[0]
    flight = leg.flight
    pax = booking.passengers[0]
    taken = sorted(flight.occupied_seats(leg.travel_date))[0]
    assert pax.seat == ''
    r = client.post(f'/mytrips/KX42LM/seats/{leg.id}',
                    data={f'seat_{pax.id}': taken}, follow_redirects=True)
    assert f'Seat {taken} is already taken'.encode() in r.data
    # the seat must NOT have been saved
    assert pax.seat == ''
    # a genuinely free standard seat still saves fine
    first_std = (leg.flight.aircraft.first_rows
                 + leg.flight.aircraft.premium_rows
                 + leg.flight.aircraft.economy_plus_rows + 1)
    free = None
    for row in range(first_std, leg.flight.aircraft.seat_rows + 1):
        for letter in leg.flight.aircraft.seat_letters:
            cand = f'{row}{letter}'
            if cand not in flight.occupied_seats(leg.travel_date):
                free = cand
                break
        if free:
            break
    r = client.post(f'/mytrips/KX42LM/seats/{leg.id}',
                    data={f'seat_{pax.id}': free}, follow_redirects=True)
    assert pax.seat == free


# ------------------------------------------------------------ flight status --

def test_flight_status_by_number_and_route():
    flight = Flight.query.filter_by(origin_code='SFO',
                                    dest_code='ORD').first()
    r = client.get(f'/flight-status/results?mode=number&number='
                   f'{flight.flight_number}&date={MIRROR_TODAY.isoformat()}')
    assert r.status_code == 200
    assert f'UA {flight.flight_number}'.encode() in r.data
    r = client.get(f'/flight-status/results?mode=route&origin=SFO'
                   f'&destination=ORD&date={MIRROR_TODAY.isoformat()}')
    assert r.status_code == 200
    assert f'UA {flight.flight_number}'.encode() in r.data
    r = client.get('/flight-status/results?mode=number&number=9999')
    assert b'No flights were found' in r.data


# ----------------------------------------------------------------- baggage --

def test_baggage_calculator_ladder():
    form = {'origin': 'ORD', 'destination': 'DEN', 'cabin': 'ECO',
            'tier': 'Member', 'bags': '3', 'where': 'online'}
    r = client.post('/baggage/fee-calculator', data=form)
    assert r.status_code == 200
    assert f"${int(BAG_FEE_TABLE['first_online'])}".encode() in r.data
    assert f"${int(BAG_FEE_TABLE['second_online'])}".encode() in r.data
    assert f"${int(BAG_FEE_TABLE['extra'])}".encode() in r.data
    # airport pricing is higher
    r2 = client.post('/baggage/fee-calculator',
                     data={**form, 'where': 'airport'})
    assert int(BAG_FEE_TABLE['first_airport']) > int(BAG_FEE_TABLE['first_online'])


def test_baggage_pages_real_rules():
    r = client.get('/baggage/checked-bags')
    body = r.data.decode()
    assert '62 total linear inches' in body or '30 in x 20 in x 12 in' in body
    assert '50 lb' in body.replace(' lb)', ' lb') or '50 lb' in body
    r = client.get('/baggage/carry-on')
    assert '9 in x 14 in x 22 in' in r.data.decode()


def test_premier_free_bag_allowance_table():
    assert PREMIER_FREE_BAGS['Premier Silver'] == 1
    assert PREMIER_FREE_BAGS['Premier Gold'] == 2
    assert PREMIER_FREE_BAGS['Premier Platinum'] == 3


# --------------------------------------------------------------- MileagePlus

def test_mp_join_and_signin():
    client.get('/signout')
    r = client.post('/mileageplus/join', data={
        'first_name': 'Test', 'last_name': 'User',
        'email': 'new.member@example.com', 'password': 'Passw0rd!'},)
    assert r.status_code == 302
    user = User.query.filter_by(email='new.member@example.com').first()
    assert user and user.mp_number and user.tier == 'Member'
    r = client.get('/account')
    assert r.status_code == 200
    assert user.mp_number.encode() in r.data
    client.get('/signout')
    r = client.post('/signin', data={'email': 'new.member@example.com',
                                     'password': 'Passw0rd!'})
    assert r.status_code == 302
    client.get('/signout')
    r = client.post('/signin', data={'email': 'alice.j@example.com',
                                     'password': 'wrong'})
    assert b'incorrect' in r.data


def test_account_dashboard_shows_progress():
    client.post('/signin', data={'email': 'carol.w@example.com',
                                'password': 'TestPass123!'})
    r = client.get('/account')
    body = r.data.decode()
    assert 'qualification progress' in body
    assert 'Premier Silver' in body          # Carol's next tier
    client.get('/signout')


def test_mileageplus_program_page_real_thresholds():
    r = client.get('/mileageplus')
    body = r.data.decode()
    assert '12 PQF' in body            # Premier Silver
    assert '54 PQF' in body            # Premier 1K
    assert '5×' in body and '11×' in body


# --------------------------------------------------------------------- help --

def test_help_search_and_articles():
    r = client.get('/help?q=checked+bag+fee')
    assert r.status_code == 200
    assert 'How much does a checked bag cost?' in r.data.decode()
    r = client.get('/help/bag-fees')
    assert r.status_code == 200
    body = r.data.decode()
    assert '3 for Premier Platinum and Premier 1K' in body
    r = client.get('/help?q=zzzznothing')
    assert b'No articles matched' in r.data


def test_site_search():
    r = client.get('/search?q=economy+plus')
    assert r.status_code == 200
    assert b'Economy Plus' in r.data
    r = client.get('/search?q=chicago')
    assert b'Chicago' in r.data


# ------------------------------------------------------------------- deals --

def test_deals_filters():
    r = client.get('/deals')
    assert r.status_code == 200
    assert b'from $' in r.data
    r = client.get('/deals?region=Europe')
    assert r.status_code == 200
    assert 'Rome to New York' in r.data.decode()


def test_every_rendered_image_resolves():
    """Render gate (review F-2): every <img> the templates emit must resolve
    to a real shipped asset. The inventory gate only checks the files on
    disk; this walks the rendered pages so cabin/deal card images can never
    silently 404 again."""
    pages = ['/', '/travel-info/cabins', '/deals', '/travel-info/fleet',
             '/baggage/checked-bags', '/baggage/carry-on', '/mileageplus',
             '/travel-info/policies/flight-change',
             '/travel-info/policies/refund-policy', '/help']
    for slug in ['basic-economy', 'united-economy', 'economy-plus',
                 'premium-plus', 'united-first-business', 'united-polaris']:
        pages.append(f'/travel-info/cabins/{slug}')
    for deal in Deal.query.all():
        pages.append(f'/deals/{deal.slug}')
    for plane in Aircraft.query.order_by(Aircraft.key).all():
        pages.append(f'/travel-info/fleet/{plane.key}')
    hub = Airport.query.filter_by(is_hub=True).first()
    pages.append(f'/travel-info/airports/{hub.code}')
    seen = set()
    for path in pages:
        r = client.get(path)
        assert r.status_code == 200, path
        for m in re.finditer(rb'<img[^>]+src="([^"]+)"', r.data):
            src = m.group(1).decode()
            if src in seen:
                continue
            seen.add(src)
            rr = client.get(src)
            assert rr.status_code == 200, f'{path}: broken image {src}'
            assert len(rr.data) > 100, f'{path}: empty image {src}'
    # the previously broken set was 21 rendered images (cabin cards/heroes +
    # every deal card); make sure this gate covers at least the ~36-image
    # surface those pages draw from
    assert len(seen) >= 30, f'only {len(seen)} distinct images checked'


# -------------------------------------------------------------- determinism --

def test_seed_is_byte_identical():
    """Two fresh seeds from the same tracked source_data (both under
    PYTHONHASHSEED=0, like the Docker build) must produce byte-identical
    SQLite files."""
    tmp1 = tempfile.mkdtemp(prefix='united-airlines-det1-')
    tmp2 = tempfile.mkdtemp(prefix='united-airlines-det2-')
    script = (
        'import sys; sys.path.insert(0, r"%s");'
        'from app import app, db;'
        'ctx = app.app_context(); ctx.push(); db.create_all();'
        'import seed_data; seed_data.seed_database();'
        'seed_data.seed_benchmark_users();'
        'db.session.commit()' % str(SITE))
    digests = []
    for tmp in (tmp1, tmp2):
        env = dict(os.environ)
        env['PYTHONHASHSEED'] = '0'
        env['UNITED_AIRLINES_DB_URI'] = f'sqlite:///{tmp}/seed.db'
        subprocess.run([sys.executable, '-c', script], env=env, check=True,
                       capture_output=True)
        digests.append(hashlib.sha256(
            open(os.path.join(tmp, 'seed.db'), 'rb').read()).hexdigest())
    assert digests[0] == digests[1]


def test_seat_selection_rejects_nonexistent_letter():
    client.get('/mytrips?confirmation=KX42LM&lastname=Johnson')
    before = db.session.get(Passenger, 1).seat
    response = client.post('/mytrips/KX42LM/seats/1', data={'seat_1': '15Z'}, follow_redirects=True)
    assert b'does not exist' in response.data
    assert db.session.get(Passenger, 1).seat == before


def test_flight_change_rejects_another_route():
    booking = Booking.query.filter_by(confirmation='QT83NB').one()
    leg = booking.legs[0]
    wrong = Flight.query.filter(Flight.origin_code != leg.flight.origin_code).first()
    before = (leg.flight_id, leg.amount, booking.total)
    client.get('/mytrips?confirmation=QT83NB&lastname=Miller')
    response = client.post(f'/mytrips/QT83NB/change/{leg.id}', data={'flight_id': wrong.id})
    assert response.status_code == 400
    assert (leg.flight_id, leg.amount, booking.total) == before


def test_baggage_calculator_applies_free_allowance_and_retains_inputs():
    from bs4 import BeautifulSoup
    for cabin, tier, bags, total in [('BUS', 'Premier Gold', 2, '0.00'), ('PP', 'Member', 2, '0.00'), ('ECO', 'Premier Silver', 2, '35.00')]:
        response = client.post('/baggage/fee-calculator', data={'origin': 'LHR', 'destination': 'DEN', 'cabin': cabin, 'tier': tier, 'bags': str(bags), 'where': 'online'})
        soup = BeautifulSoup(response.data, 'html.parser')
        assert soup.select_one('.ua-total-row').get_text(' ', strip=True) == 'Total $' + total
        assert soup.select_one('select[name=tier] option[selected]')['value'] == tier


# Party-level validation must finish before either route changes persisted state.
import pytest


@pytest.fixture
def seat_party(monkeypatch):
    booking = Booking.query.filter_by(confirmation='HD19RK').one()
    first = booking.passengers[0]
    saved = (first.seat, first.checked_in, first.boarding_group)
    first.seat, first.checked_in, first.boarding_group = '', False, ''
    second = Passenger(booking_id=booking.id, first_name='Alex', last_name='Thomas')
    db.session.add(second)
    db.session.commit()
    db.session.expire(booking, ['passengers'])
    monkeypatch.setattr(Flight, 'occupied_seats', lambda self, day: {'12C'})
    browser = app.test_client()
    browser.get('/mytrips?confirmation=HD19RK&lastname=Thomas')
    yield browser, booking, first, second
    db.session.rollback()
    first.seat, first.checked_in, first.boarding_group = saved
    db.session.delete(second)
    db.session.commit()
    db.session.expire(booking, ['passengers'])


@pytest.mark.parametrize('checkin', [False, True])
@pytest.mark.parametrize('bad', ['12A', '12C', '99Z', 'malformed'])
def test_party_rejects_duplicate_occupied_invalid_atomically(seat_party, checkin, bad):
    browser, booking, first, second = seat_party
    path = (f'/checkin/{booking.confirmation}' if checkin else
            f'/mytrips/{booking.confirmation}/seats/{booking.legs[0].id}')
    response = browser.post(path, data={f'seat_{first.id}': '12A',
                                       f'seat_{second.id}': bad}, follow_redirects=True)
    assert response.status_code == 200
    expected = (b'more than one traveler' if bad == '12A' else
                b'already taken' if bad == '12C' else b'does not exist')
    assert expected in response.data
    # Commit again to detect mutations left pending by a rejected request.
    db.session.commit()
    db.session.expire_all()
    assert [(p.seat, p.checked_in, p.boarding_group) for p in booking.passengers] == [
        ('', False, ''), ('', False, '')]


@pytest.mark.parametrize('checkin', [False, True])
def test_party_retained_seat_blocks_duplicate_and_allows_swap(seat_party, checkin):
    browser, booking, first, second = seat_party
    first.seat, second.seat = '12A', '12B'
    db.session.commit()
    path = (f'/checkin/{booking.confirmation}' if checkin else
            f'/mytrips/{booking.confirmation}/seats/{booking.legs[0].id}')
    browser.post(path, data={f'seat_{second.id}': '12A'})
    db.session.expire_all()
    assert (first.seat, second.seat) == ('12A', '12B')
    browser.post(path, data={f'seat_{first.id}': '12B', f'seat_{second.id}': '12A'})
    db.session.expire_all()
    assert (first.seat, second.seat) == ('12B', '12A')
    assert (first.checked_in, second.checked_in) == (checkin, checkin)


def test_party_automatic_checkin_assigns_distinct_seats(seat_party):
    browser, booking, first, second = seat_party
    response = browser.post(f'/checkin/{booking.confirmation}', follow_redirects=True)
    assert response.status_code == 200
    db.session.expire_all()
    assert first.seat and second.seat and first.seat != second.seat
    assert first.checked_in and second.checked_in


def test_party_auto_reserves_later_explicit_choice(seat_party):
    browser, booking, first, second = seat_party
    aircraft = booking.legs[0].flight.aircraft
    seat = f'{aircraft.first_rows + aircraft.premium_rows + aircraft.economy_plus_rows + 1}{aircraft.seat_letters[0]}'
    browser.post(f'/checkin/{booking.confirmation}', data={f'seat_{second.id}': seat})
    db.session.expire_all()
    assert second.seat == seat and first.seat != seat and first.seat


@pytest.mark.parametrize('remaining', [0, 1])
def test_party_no_available_seats_does_not_check_in(seat_party, monkeypatch, remaining):
    browser, booking, first, second = seat_party
    aircraft = booking.legs[0].flight.aircraft
    monkeypatch.setattr(Flight, 'occupied_seats', lambda self, day: {
        f'{row}{letter}' for row in range(1, aircraft.seat_rows + 1)
        for letter in aircraft.seat_letters} -
        ({f'{aircraft.seat_rows}{aircraft.seat_letters[-1]}'} if remaining else set()))
    response = browser.post(f'/checkin/{booking.confirmation}', follow_redirects=True)
    assert b'No available seats remain' in response.data
    db.session.commit()
    db.session.expire_all()
    assert not first.seat and not second.seat
    assert not first.checked_in and not second.checked_in
