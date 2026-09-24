"""Self-check suite for the megabus mirror.

Run from sites/megabus/:  python3 -m pytest tests/ -q

The suite runs against a temporary copy of the seeded database (pointed to
via MEGABUS_DB_URI before importing the app) so it never mutates the seed.
"""
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SITE = HERE.parent
sys.path.insert(0, str(SITE))

TMP = tempfile.mkdtemp(prefix='megabus-tests-')
DB_PATH = os.path.join(TMP, 'megabus.db')
shutil.copyfile(os.path.join(SITE, 'instance_seed', 'megabus.db'), DB_PATH)
os.environ['MEGABUS_DB_URI'] = f'sqlite:///{DB_PATH}'

from app import app, db, Journey, Booking, User, BasketItem  # noqa: E402

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False
client = app.test_client()


def get(path, **kw):
    return client.get(path, **kw)


def clear_basket():
    """Tests share one client session; start each basket test from an empty basket."""
    with app.app_context():
        BasketItem.query.delete()
        db.session.commit()
    with client.session_transaction() as sess:
        sess.pop('promo_code', None)
        sess.pop('sms_updates', None)


def test_health():
    r = get('/_health')
    assert r.status_code == 200
    assert r.get_json() == {'ok': True, 'site': 'megabus'}


def test_home_and_registry_routes():
    for path in ['/', '/fare-finder', '/route-guides', '/city-guides', '/stops',
                 '/help', '/service-alerts', '/about-us', '/terms', '/privacy-policy',
                 '/contact-us', '/megabus-app', '/journey-planner/manage-booking',
                 '/journey-planner/track', '/journey-planner/map',
                 '/account-management/login', '/account-management/register']:
        assert get(path).status_code == 200, path


def test_api_cities():
    r = get('/journey-planner/api/origin-cities')
    assert r.status_code == 200
    data = r.get_json()
    assert len(data['cities']) == 753
    names = {c['name'] for c in data['cities']}
    assert 'New York, NY' in names and 'Toronto, ON' in names


def test_destination_cities_depend_on_origin():
    r = get('/journey-planner/api/destination-cities?originCityId=127')
    assert r.status_code == 200
    names = {c['name'] for c in r.get_json()['cities']}
    assert 'New York, NY' in names
    assert 'Philadelphia, PA' not in names


def test_journey_results_page():
    r = get('/journey-planner/journeys?originId=127&destinationId=123'
            '&departureDate=2026-10-03&totalPassengers=1')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Showing 19 results' in body
    assert '25.99' in body
    assert 'Add to basket' in body


def test_journey_date_ribbon_links():
    body = get('/journey-planner/journeys?originId=127&destinationId=123'
               '&departureDate=2026-10-03&totalPassengers=1').get_data(as_text=True)
    assert 'departureDate=2026-10-04' in body
    assert 'departureDate=2026-09-30' in body


def test_unbookable_date_is_graceful():
    r = get('/journey-planner/journeys?originId=127&destinationId=123'
            '&departureDate=2026-11-30&totalPassengers=1')
    assert r.status_code == 200
    assert 'No journeys found' in r.get_data(as_text=True)


def test_invalid_route_rejected():
    assert get('/journey-planner/journeys?originId=127&destinationId=99999&departureDate=2026-10-03').status_code == 404
    assert get('/journey-planner/journeys?departureDate=2026-10-03').status_code == 404


def test_basket_add_and_promo():
    clear_basket()
    with app.app_context():
        j = Journey.query.filter_by(origin_city_id=143, dest_city_id=123,
                                    departure_date='2026-10-03').filter(
                                        Journey.dep_time == '08:35').first()
        assert j is not None and j.price == 43.99
        jid = j.id
    r = client.post('/journey-planner/basket/add',
                    data={'journey_id': jid, 'passengers': '2'})
    assert r.status_code == 302
    body = get('/journey-planner/basket').get_data(as_text=True)
    assert '87.98' in body and 'Booking fee' in body
    # invalid code rejected
    client.post('/journey-planner/basket/promo', data={'code': 'SAVE20'})
    assert 'not valid' in get('/journey-planner/basket').get_data(as_text=True)
    # advertised code works: 87.98 - 5.00 + 3.99 = 86.97
    client.post('/journey-planner/basket/promo', data={'code': 'EMAIL5'})
    assert '86.97' in get('/journey-planner/basket').get_data(as_text=True)


def test_full_guest_checkout_creates_booking():
    clear_basket()
    with app.app_context():
        j = Journey.query.filter_by(origin_city_id=145, dest_city_id=279,
                                    departure_date='2026-10-03').filter(
                                        Journey.price == 71.99).first()
        jid = j.id
    client.post('/journey-planner/basket/add', data={'journey_id': jid, 'passengers': '1'})
    client.post('/journey-planner/basket/pay',
                data={'checkbox-terms': 'on', 'sms_updates': 'on'})
    client.post('/journey-planner/login', data={'action': 'guest'})
    r = client.post('/journey-planner/passenger-details',
                    data={'first_name_1': 'Yuki', 'last_name_1': 'Tanaka',
                          'email': 'yuki.tanaka@example.com', 'phone': ''})
    assert r.status_code == 302
    r = client.post('/journey-planner/payment',
                    data={'card_name': 'Yuki Tanaka', 'card_number': '4242424242424242',
                          'expiry': '08/28', 'cvv': '123', 'zip': 'M5V 2T6'})
    assert r.status_code == 302
    # 71.99 + 3.99 booking fee + 0.25 SMS = 76.23
    with app.app_context():
        b = Booking.query.filter_by(email='yuki.tanaka@example.com').first()
    assert b is not None
    assert abs(b.total - 76.23) < 0.001
    assert b.reference


def test_invalid_card_rejected():
    clear_basket()
    with app.app_context():
        j = Journey.query.filter_by(origin_city_id=123, dest_city_id=127,
                                    departure_date='2026-10-03').first()
        jid = j.id
    client.post('/journey-planner/basket/add', data={'journey_id': jid, 'passengers': '1'})
    client.post('/journey-planner/basket/pay', data={'checkbox-terms': 'on'})
    client.post('/journey-planner/login', data={'action': 'guest'})
    client.post('/journey-planner/passenger-details',
                data={'first_name_1': 'T', 'last_name_1': 'W',
                      'email': 'tw@example.com', 'phone': ''})
    r = client.post('/journey-planner/payment',
                    data={'card_name': 'T W', 'card_number': '12',
                          'expiry': '13/99', 'cvv': '1', 'zip': '10001'})
    assert r.status_code == 200
    assert 'Enter a valid card number' in r.get_data(as_text=True)


def test_manage_booking_lookup_and_guard():
    r = client.post('/journey-planner/manage-booking',
                    data={'reference': 'H3P8KS', 'email': 'david.k@test.com'})
    body = r.get_data(as_text=True)
    assert 'H3P8KS' in body and 'Washington' in body
    # wrong email must not reveal the booking
    r = client.post('/journey-planner/manage-booking',
                    data={'reference': 'H3P8KS', 'email': 'someone@example.com'})
    assert 'could not find a booking' in r.get_data(as_text=True)


def test_manage_booking_cancel():
    client.post('/journey-planner/manage-booking', data={'reference':'B7L2MX','email':'carol.d@test.com'})
    r = client.post('/journey-planner/manage-booking/cancel',
                    data={'reference': 'B7L2MX'})
    assert r.status_code == 409  # already cancelled in the seed
    body = get('/journey-planner/manage-booking?ref=B7L2MX').get_data(as_text=True)
    assert 'cancelled' in body


def test_manage_booking_change_guard():
    client.post('/journey-planner/manage-booking', data={'reference':'M2V6YH','email':'bob.c@test.com'})
    r = client.post('/journey-planner/manage-booking/change',
                    data={'reference': 'M2V6YH', 'bj': '4',
                          'new_journey_id': 'x-bogus'})
    assert 'Choose a departure' in r.get_data(as_text=True)


def test_benchmark_users_exist():
    with app.app_context():
        for email in ('alice.j@test.com', 'bob.c@test.com',
                      'carol.d@test.com', 'david.k@test.com'):
            u = User.query.filter_by(email=email).first()
            assert u is not None, email
            assert u.check_password('TestPass123!')
        refs = {b.reference for b in Booking.query.all()}
    assert {'AEG7CWY', 'K4N2WZ', 'R8T3QD', 'M2V6YH', 'W9C4FJ',
            'B7L2MX', 'H3P8KS', 'T5G6VN'} <= refs


def test_account_login_and_profile_update():
    r = client.post('/account-management/login',
                    data={'email': 'carol.d@test.com', 'password': 'TestPass123!'})
    assert r.status_code == 302
    r = client.post('/account-management/profile',
                    data={'first_name': 'Carol', 'last_name': 'Davies',
                          'phone': '555-202-7788'})
    assert r.status_code == 302
    body = get('/account-management').get_data(as_text=True)
    assert 'Davies' in body and '555-202-7788' in body


def test_fare_finder_lists_destinations():
    body = get('/fare-finder/search?originId=127').get_data(as_text=True)
    assert 'Baltimore, MD' in body and '15.99' in body
    assert 'New York, NY' in body and '19.99' in body
    assert 'EMAIL5' in body  # the advertised promotion


def test_help_search_scored():
    assert 'luggage' in get('/help/search?q=luggage').get_data(as_text=True).lower()
    assert get('/search?q=luggage').status_code == 200


def test_service_alerts_and_tracker():
    body = get('/service-alerts').get_data(as_text=True)
    assert 'Philadelphia stop temporarily moved' in body
    r = client.post('/journey-planner/track',
                    data={'originId': '123', 'destinationId': '127',
                          'departureDate': '2026-10-03'})
    body = r.get_data(as_text=True)
    assert 'Delayed' in body and '15 min' in body


def test_guides_and_stops():
    body = get('/route-guides/boston-to-new-york-bus').get_data(as_text=True)
    assert '4 hours 20 minutes' in body
    assert 'Up to 37 services per day' in body
    body = get('/city-guides/toronto').get_data(as_text=True)
    assert 'CN Tower' in body
    body = get('/stops/albany').get_data(as_text=True)
    assert 'Adirondack Trailways' in body
    assert '66 Green Street' in body


def test_404_pages():
    assert get('/route-guides/nope').status_code == 404
    assert get('/city-guides/nope').status_code == 404
    assert get('/stops/nope').status_code == 404


def test_reference_only_access_is_rejected():
    anonymous=app.test_client()
    assert anonymous.get('/journey-planner/manage-booking?ref=M2V6YH').status_code==403
    assert anonymous.get('/journey-planner/confirmation/M2V6YH').status_code==403
    assert anonymous.post('/journey-planner/manage-booking/cancel',data={'reference':'M2V6YH'}).status_code==403
    assert anonymous.get('/journey-planner/manage-booking/change?ref=M2V6YH&bj=4').status_code==403


def test_owner_of_seeded_guest_booking_has_access():
    owner=app.test_client()
    owner.post('/account-management/login',data={'email':'alice.j@test.com','password':'TestPass123!'})
    assert owner.get('/journey-planner/manage-booking?ref=AEG7CWY').status_code==200
    assert owner.get('/journey-planner/manage-booking?ref=M2V6YH').status_code==403


def test_logout_and_login_redirect_guard():
    owner=app.test_client()
    response=owner.post('/account-management/login?next=//example.org',data={'email':'alice.j@test.com','password':'TestPass123!'})
    assert response.headers['Location']=='/account-management'
    assert owner.get('/account-management/logout').status_code==405


def test_double_cancellation_does_not_issue_another_refund():
    owner=app.test_client()
    owner.post('/journey-planner/manage-booking',data={'reference':'W9C4FJ','email':'carol.d@test.com'})
    assert owner.post('/journey-planner/manage-booking/cancel',data={'reference':'W9C4FJ'}).status_code==302
    assert owner.post('/journey-planner/manage-booking/cancel',data={'reference':'W9C4FJ'}).status_code==409
