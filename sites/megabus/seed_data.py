#!/usr/bin/env python3
"""Deterministic build-time seeder for the megabus mirror.

All content rows come from the tracked source_data_*.json snapshots captured
from https://us.megabus.com/ on 2026-09-23 (see scripts_dev/build_source_data.py).
Benchmark users use a frozen bcrypt hash so the SQLite seed is byte-reproducible
on every build (PYTHONHASHSEED=0).

Seeding is idempotent: run_seed / run_seed_users each early-return when their
tables are already populated (the gates live in app.py).
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent

MIRROR_TODAY = '2026-09-23'
# frozen so the seed database is byte-identical on every build
SEED_STAMP = datetime(2026, 9, 23, 14, 30, 0)

# bcrypt hash of 'TestPass123!' (frozen so the seed DB is byte-reproducible)
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$DBQeVglqWXZOTGSQm.DtRe9DGERTLOmPaYINgAATIiJDGKsNo.mZi')

BENCHMARK_USERS = [
    {'username': 'alice_j', 'email': 'alice.j@test.com',
     'first_name': 'Alice', 'last_name': 'Johnson'},
    {'username': 'bob_c', 'email': 'bob.c@test.com',
     'first_name': 'Bob', 'last_name': 'Chen'},
    {'username': 'carol_d', 'email': 'carol.d@test.com',
     'first_name': 'Carol', 'last_name': 'Davis'},
    {'username': 'david_k', 'email': 'david.k@test.com',
     'first_name': 'David', 'last_name': 'Kim'},
]


def _load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def run_seed(db, City, Stop, Journey, JourneyLeg, TravelDate, FaqEntry,
             CityGuide, RouteGuide, ServiceAlert, PromoCode, BusStatus,
             StaticPage):
    network = _load('source_data_network.json')
    journeys_data = _load('source_data_journeys.json')
    content = _load('source_data_content.json')

    city_by_id = {}
    for c in network['cities']:
        row = City(id=c['id'], name=c['name'], state=c['state'], slug=c['slug'],
                   latitude=c['latitude'], longitude=c['longitude'])
        db.session.add(row)
        city_by_id[c['id']] = row
    db.session.flush()

    city_by_name = {c.name: c for c in city_by_id.values()}
    for s in network['stops']:
        city = city_by_name.get(s['city'])
        if not city:
            continue
        carrier = ''
        m = None
        text = s['name']
        for prefix in (' bus stop at ', ' Bus Stop at ', ' bus stop ', ' Bus Stop '):
            if prefix in text:
                m = text.split(prefix)[0]
                break
        if m:
            carrier = m.strip()
        db.session.add(Stop(city_id=city.id, carrier=carrier, name=s['name']))

    for j in journeys_data['journeys']:
        row = Journey(
            id=str(j['id']), origin_city_id=j['origin_city_id'], dest_city_id=j['dest_city_id'],
            departure_date=j['departure_date'], dep_time=j['dep_time'],
            arr_time=j['arr_time'], duration_min=j['duration_min'],
            price=j['price'], route_name=j['route_name'],
            reservable=j['reservable'], service_information=j['service_information'])
        db.session.add(row)
    db.session.flush()
    for j in journeys_data['journeys']:
        for leg in j['legs']:
            db.session.add(JourneyLeg(
                journey_id=j['id'], seq=leg['seq'], carrier=leg['carrier'],
                carrier_icon=leg['carrier_icon'], dep_datetime=leg['dep'],
                arr_datetime=leg['arr'], duration_min=j['duration_min'],
                origin_stop=leg['origin_stop'], origin_stop_id=leg['origin_stop_id'],
                dest_stop=leg['dest_stop'], dest_stop_id=leg['dest_stop_id']))

    for t in journeys_data['travel_dates']:
        db.session.add(TravelDate(origin_city_id=t['origin_city_id'],
                                  dest_city_id=t['dest_city_id'], day=t['day']))

    for f in content['faqs']:
        db.session.add(FaqEntry(topic=f['topic'], seq=f['seq'],
                                question=f['question'], answer=f['answer']))
    for g in content['city_guides']:
        db.session.add(CityGuide(slug=g['slug'], title=g['title'],
                                 page_title=g['page_title'], hero=g['hero'],
                                 is_city=g['is_city'],
                                 sections_json=json.dumps(g['sections'])))
    for g in content['route_guides']:
        db.session.add(RouteGuide(
            slug=g['slug'], seq=g['seq'], title=g['title'],
            link_title=g['link_title'], subtitle=g['subtitle'],
            origin_city_id=g['origin_id'], dest_city_id=g['dest_id'],
            banner=g['banner'], stats_json=json.dumps(g['stats']),
            details=g['details'], faqs_json=json.dumps(g['faqs']),
            related_json=json.dumps(g['related'])))
    for a in content['service_alerts']:
        db.session.add(ServiceAlert(severity=a['severity'], title=a['title'],
                                    body=a['body'], route_name=a['route_name'],
                                    published_on=a['published_on']))
    for p in content['promo_codes']:
        db.session.add(PromoCode(code=p['code'], kind=p['kind'], value=p['value'],
                                 min_spend=p['min_spend'], description=p['description'],
                                 active=p['active']))
    for slug in sorted(content['static_pages']):
        db.session.add(StaticPage(slug=slug,
                                  content=content['static_pages'][slug]))
    db.session.commit()

    # Bus tracker snapshot: mark one busy morning NY->PHL departure as delayed
    # so the tracker has a stable, verifiable state. Deterministic selection:
    # first NY(123)->PHL(127) journey on 2026-10-03 departing after 08:00.
    seed_tracker_states(db, Journey, BusStatus)


def seed_tracker_states(db, Journey, BusStatus):
    candidates = (Journey.query
                  .filter_by(origin_city_id=123, dest_city_id=127,
                             departure_date='2026-10-03')
                  .order_by(Journey.dep_time).all())
    target = None
    for j in candidates:
        if j.dep_time >= '08:00':
            target = j
            break
    if target is None and candidates:
        target = candidates[0]
    if target is not None:
        db.session.add(BusStatus(journey_id=target.id, state='Delayed',
                                 delay_min=15,
                                 current_stop='Departed New York, NY - Port Authority Bus Terminal'))
    db.session.commit()


def run_seed_users(db, User, Booking, BookingJourney, Journey, SavedPassenger):
    for u in BENCHMARK_USERS:
        db.session.add(User(email=u['email'], password_hash=BENCHMARK_PASSWORD_HASH,
                            first_name=u['first_name'], last_name=u['last_name'],
                            phone='', newsletter=False, created_at=SEED_STAMP))
    db.session.flush()

    # ---- deterministic seeded bookings -------------------------------------
    # Routes: NY=123 PHL=127 DC=142 Boston=94 Toronto=145 State College=137
    plans = [
        # email, reference, status, [(origin, dest, date, prefer_dep_after, pax)]
        ('alice.j@test.com', 'AEG7CWY', 'confirmed', [(127, 123, '2026-10-03', '05:00', 2)],
         True),
        ('alice.j@test.com', 'K4N2WZ', 'confirmed', [(123, 142, '2026-10-03', '09:00', 1)],
         False),
        ('bob.c@test.com', 'R8T3QD', 'confirmed', [(123, 94, '2026-10-03', '06:00', 1)],
         True),
        ('bob.c@test.com', 'M2V6YH', 'confirmed', [(127, 142, '2026-10-06', '06:00', 2)],
         False),
        ('carol.d@test.com', 'W9C4FJ', 'confirmed', [(123, 145, '2026-10-04', '07:00', 1)],
         True),
        ('carol.d@test.com', 'B7L2MX', 'cancelled', [(145, 123, '2026-10-04', '09:00', 1)],
         False),
        ('david.k@test.com', 'H3P8KS', 'confirmed', [(142, 123, '2026-10-10', '05:00', 3)],
         True),
        ('david.k@test.com', 'T5G6VN', 'confirmed', [(123, 137, '2026-10-03', '08:00', 1)],
         False),
    ]
    for email, ref, status, legs, sms in plans:
        total_fare = 0.0
        booking = Booking(reference=ref, email=email, status=status,
                          total=0.0, sms_updates=sms,
                          passenger_names='', created_on=MIRROR_TODAY,
                          created_at=SEED_STAMP)
        db.session.add(booking)
        db.session.flush()
        for (origin, dest, day, after, pax) in legs:
            j = (Journey.query
                 .filter_by(origin_city_id=origin, dest_city_id=dest,
                            departure_date=day)
                 .filter(Journey.dep_time >= after)
                 .order_by(Journey.dep_time).first())
            if j is None:
                j = (Journey.query
                     .filter_by(origin_city_id=origin, dest_city_id=dest,
                                departure_date=day)
                     .order_by(Journey.dep_time).first())
            if j is None:
                continue
            fare = round(j.price * pax, 2)
            total_fare += fare
            db.session.add(BookingJourney(booking_id=booking.id, journey_id=j.id,
                                          passengers=pax, price=fare))
        booking.total = round(total_fare + 3.99 + (0.25 if sms else 0.0), 2)
    db.session.commit()

    # saved passengers (upstream account area feature)
    saved = [
        ('alice.j@test.com', 'Ms', 'Alice', 'Johnson', '1991-04-12'),
        ('alice.j@test.com', 'Mr', 'Marcus', 'Johnson', '1988-09-03'),
        ('bob.c@test.com', 'Mr', 'Bob', 'Chen', '1990-01-25'),
        ('carol.d@test.com', 'Ms', 'Carol', 'Davis', '1993-11-17'),
        ('david.k@test.com', 'Mr', 'David', 'Kim', '1985-06-30'),
    ]
    users = {u.email: u for u in User.query.all()}
    for email, title, first, last, dob in saved:
        user = users.get(email)
        if user:
            db.session.add(SavedPassenger(user_id=user.id, title=title,
                                          first_name=first, last_name=last,
                                          date_of_birth=dob))
    db.session.commit()


def main() -> None:
    """Standalone entry: build instance/megabus.db from scratch (idempotent)."""
    import app as app_mod
    instance_dir = pathlib.Path(app_mod.BASE_DIR) / 'instance'
    instance_dir.mkdir(parents=True, exist_ok=True)
    with app_mod.app.app_context():
        app_mod.db.create_all()
        app_mod.seed_database()
        app_mod.seed_benchmark_users()
    print('seeded')


if __name__ == '__main__':
    main()
