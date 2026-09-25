"""Regressions for the independent review's booking and security findings."""
import shutil
import re
from pathlib import Path
import pytest


@pytest.fixture
def fresh(app, db):
    # Each test starts from the reviewed immutable fixture.
    from app import _DB_PATH
    db.session.remove()
    db.engine.dispose()
    shutil.copy2(Path(__file__).parents[1] / 'instance_seed/marriott.db', _DB_PATH)
    with app.test_client() as c:
        yield c
    db.session.remove()


def post(c, url, data):
    c.get('/sign-in.mi')
    with c.session_transaction() as state:
        token = state['csrf_token']
    return c.post(url, data={**data, 'csrf_token': token})


def test_csrf_is_required_and_logout_is_post(fresh):
    assert fresh.post('/sign-in.mi', data={'email': 'alice.j@test.com', 'password': 'TestPass123!'}).status_code == 400
    assert fresh.get('/logoff').status_code == 405


@pytest.mark.parametrize('target', ['//example.org', '/\\example.org', 'https://example.org'])
def test_signin_external_redirect_rejected(fresh, target):
    r = post(fresh, '/sign-in.mi?next=' + target, {'email': 'alice.j@test.com', 'password': 'TestPass123!'})
    assert r.location in {'/account', '/loyalty/myAccount.mi'}


def test_confirmation_access_is_scoped(fresh, app):
    url = '/reservation/confirmation.mi?confirmationNumber=ACCEDGHDDR'
    assert fresh.get(url).status_code == 404
    post(fresh, '/sign-in.mi', {'email': 'bob.c@test.com', 'password': 'TestPass123!'})
    assert fresh.get(url).status_code == 404
    post(fresh, '/sign-in.mi', {'email': 'alice.j@test.com', 'password': 'TestPass123!'})
    assert fresh.get(url).status_code == 200


def test_cancel_refunds_exactly_once(fresh, db):
    from app import Reservation, User
    r = Reservation.query.filter_by(confirmation_number='ACCEDGHDDR').one()
    r.points_redeemed = 19000
    user = db.session.get(User, r.user_id)
    initial = user.points
    db.session.commit()
    for _ in range(2):
        assert post(fresh, '/reservation/cancel.mi', {'confirmationNumber': 'ACCEDGHDDR', 'lastName': 'Johnson'}).status_code == 302
    db.session.expire_all()
    assert user.points == initial + 19000
    assert r.status == 'canceled'


@pytest.mark.parametrize('changes', [{'rooms': '-1'}, {'adults': '4'}, {'fromDate': 'garbage'}, {'exp_year': '2020'}])
def test_invalid_booking_does_not_write(fresh, db, changes):
    from app import Reservation, Hotel
    hotel = Hotel.query.filter_by(marsha='SFOFU').one()
    data = dict(propertyCode='SFOFU', roomId=str(hotel.room_types[0].id), fromDate='11/06/2026', toDate='11/08/2026', rooms='1', adults='2', guest_first_name='Jordan', guest_last_name='Ellis', guest_email='jordan.ellis@example.com', card_number='4012888888881881', exp_month='11', exp_year='2029', rate_option='cash')
    before = Reservation.query.count()
    r = post(fresh, '/reservation/reservationGateway.mi', {**data, **changes})
    assert r.status_code == 200
    assert Reservation.query.count() == before


def test_guest_can_see_own_new_confirmation(fresh, db):
    from app import Hotel
    hotel = Hotel.query.filter_by(marsha='SFOFU').one()
    data = dict(propertyCode='SFOFU', roomId=str(hotel.room_types[0].id), fromDate='11/06/2026', toDate='11/08/2026', rooms='1', adults='2', guest_first_name='Jordan', guest_last_name='Ellis', guest_email='jordan.ellis@example.com', card_number='4012888888881881', exp_month='11', exp_year='2029', rate_option='cash')
    r = post(fresh, '/reservation/reservationGateway.mi', data)
    assert r.status_code == 302
    assert fresh.get(r.location).status_code == 200


def test_help_page_uses_seed_content(fresh, monkeypatch):
    original = Path.read_text
    def guarded(path, *args, **kwargs):
        assert path.name != 'help_content.json', 'runtime must use the DB'
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded)
    assert fresh.get('/help/global-phone-reservation-numbers.mi').status_code == 200


def test_card_replacement_preserves_default(fresh, db):
    from app import PaymentMethod
    post(fresh, '/sign-in.mi', {'email': 'carol.d@test.com', 'password': 'TestPass123!'})
    old = PaymentMethod.query.filter_by(user_id=3).one().id
    post(fresh, '/account/payments', {'card_type': 'Visa', 'card_number': '4242424242424444', 'holder_name': 'Carol Davis', 'exp_month': '9', 'exp_year': '2029'})
    post(fresh, f'/account/payments/{old}/delete', {})
    db.session.expire_all()
    remaining = PaymentMethod.query.filter_by(user_id=3).one()
    assert remaining.last_four == '4444' and remaining.is_default


def test_search_context_survives_overview_and_room_tabs(fresh):
    from bs4 import BeautifulSoup
    r = fresh.get('/search/findHotels.mi?destinationAddress=Chicago&fromDate=10/30/2026&toDate=10/31/2026&numAdultsPerRoom=2&maxPrice=300')
    soup = BeautifulSoup(r.data, 'html.parser')
    assert soup.select_one('[name=maxPrice]')['value'] == '300'
    link = soup.select_one('.card-title a')['href']
    assert 'fromDate=10%2F30%2F2026' in link and 'adults=2' in link
    soup = BeautifulSoup(fresh.get(link).data, 'html.parser')
    rooms = next(a['href'] for a in soup.select('.hotel-nav a') if 'rooms/' in a['href'])
    assert 'fromDate=10%2F30%2F2026' in rooms and 'adults=2' in rooms


def test_spa_filter_does_not_match_meeting_space(fresh):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(fresh.get('/search/findHotels.mi?destinationAddress=Chicago&amenity=Spa').data, 'html.parser')
    names = [a.get_text(strip=True) for a in soup.select('.card-title a')]
    assert names == ['JW Marriott Chicago']
