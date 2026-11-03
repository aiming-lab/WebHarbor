#!/usr/bin/env python3
"""Deterministic build-time seeder for the spothero mirror.

All catalog rows come from the tracked source_data_*.json snapshots captured
from https://spothero.com/ on 2026-09-26.
Benchmark users use a frozen bcrypt hash so the SQLite seed is byte-reproducible
on every build (PYTHONHASHSEED=0).

Seeding is idempotent: run_seed / run_seed_users each early-return when their
tables are already populated (the gates live in app.py).
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).resolve().parent

MIRROR_TODAY = datetime(2026, 9, 26)

# Venue-local time bases: upstream renders every event time in the venue's own
# timezone (its destination page and event-search banner agree). The harvest
# stores raw UTC ISO strings in `starts`/`ends`, so seed-time conversion keeps
# every displayed field on one venue-local base.
_TZ_BY_STATE = {
    'IL': 'America/Chicago', 'TX': 'America/Chicago', 'TN': 'America/Chicago',
    'WI': 'America/Chicago', 'MN': 'America/Chicago', 'LA': 'America/Chicago',
    'NY': 'America/New_York', 'PA': 'America/New_York', 'FL': 'America/New_York',
    'DC': 'America/New_York', 'MA': 'America/New_York',
    'CA': 'America/Los_Angeles', 'WA': 'America/Los_Angeles',
    'CO': 'America/Denver',
}


def _venue_tz(venue_city, venue_state, city_tz_by_name):
    tz = city_tz_by_name.get((venue_city or '').strip())
    if not tz:
        tz = _TZ_BY_STATE.get((venue_state or '').strip().upper(),
                              'America/New_York')
    return ZoneInfo(tz)


def _utc_to_local(iso, tz):
    """UTC ISO (trailing Z) -> naive venue-local ISO string."""
    if not iso:
        return ''
    dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo('UTC'))
    return _iso(dt.astimezone(tz).replace(tzinfo=None))

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

# deterministically authored demo reservations (upstream reservation format).
# Codes are stable so tasks can reference them.
USER_RESERVATIONS = [
    {'user': 0, 'code': 'SH-7K2M4Q', 'facility': '5284', 'kind': 'hourly',
     'start': '2026-09-28T12:00', 'end': '2026-09-28T17:00', 'status': 'upcoming',
     'plate': 'IL-AL7431', 'vehicle': 'Toyota Camry Hybrid'},
    {'user': 0, 'code': 'SH-9W5XN8', 'facility': '129876', 'kind': 'event',
     'start': '2026-10-02T17:30', 'end': '2026-10-02T23:30', 'status': 'upcoming',
     'plate': 'IL-AL7431', 'vehicle': 'Toyota Camry Hybrid'},
    {'user': 1, 'code': 'SH-3J8BV2', 'facility': '2175', 'kind': 'monthly',
     'start': '2026-09-15T00:00', 'end': '2026-10-15T23:59', 'status': 'active',
     'plate': 'IL-BO1180', 'vehicle': 'Honda CR-V'},
    {'user': 1, 'code': 'SH-5T2RC9', 'facility': '104341', 'kind': 'hourly',
     'start': '2026-09-20T09:00', 'end': '2026-09-20T18:00', 'status': 'past',
     'plate': 'IL-BO1180', 'vehicle': 'Honda CR-V'},
    {'user': 2, 'code': 'SH-8M4KD3', 'facility': '5283', 'kind': 'hourly',
     'start': '2026-10-04T11:00', 'end': '2026-10-04T15:00', 'status': 'upcoming',
     'plate': 'NY-CA2245', 'vehicle': 'Volkswagen Tiguan'},
    {'user': 2, 'code': 'SH-2Q6ZH7', 'facility': '16130', 'kind': 'hourly',
     'start': '2026-09-12T14:00', 'end': '2026-09-12T20:00', 'status': 'past',
     'plate': 'NY-CA2245', 'vehicle': 'Volkswagen Tiguan'},
    {'user': 3, 'code': 'SH-6N9WF4', 'facility': '12897', 'kind': 'airport',
     'start': '2026-10-08T11:00', 'end': '2026-10-12T11:00', 'status': 'upcoming',
     'plate': 'IL-DA6690', 'vehicle': 'Ford Explorer'},
    {'user': 3, 'code': 'SH-4C3YP5', 'facility': '104341', 'kind': 'hourly',
     'start': '2026-09-19T16:00', 'end': '2026-09-19T21:00', 'status': 'cancelled',
     'plate': 'IL-DA6690', 'vehicle': 'Ford Explorer'},
]

REVIEW_DURATIONS = ['1 hour', '2 hours', '3 hours', '4 hours', '5 hours',
                    '6 hours', '7 hours', '8 hours', '9 hours', '10 hours',
                    '2 hours, 30 minutes', '3 hours, 30 minutes', '45 minutes',
                    '30 minutes', '1 day']
REVIEW_VEHICLES = ['Toyota RAV4', 'Volkswagen Tiguan', 'Toyota Camry Hybrid',
                   'Nissan Rogue', 'Hyundai Santa-Fe', 'Kia Sportage Hybrid',
                   'Ford Explorer', 'Hyundai Palisade', 'Honda Accord', 'Jeep Wrangler',
                   'Subaru Outback', 'Chevrolet Malibu', 'Tesla Model 3', 'BMW 3 Series']


def _load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def _iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M')


def run_seed(db, City, Destination, Facility, Airport, Event, Faq, PromoCode,
            Review, Stadium, StaticPage):
    facilities = _load('source_data_facilities.json')
    geo = _load('source_data_geo.json')
    content = _load('source_data_content.json')

    for c in geo['cities']:
        db.session.add(City(
            slug=c['slug'], name=c['name'], display_name=c['display_name'],
            state=c['state'], lat=c['lat'], lng=c['lng'], timezone=c['timezone'],
            hero_image=c.get('hero_image', ''), phone=c.get('phone', ''),
            monthly_phone=c.get('monthly_phone', ''),
            rates=json.dumps(c['rates']),
            popular_destinations=json.dumps(c['popular_destinations']),
            neighborhoods=json.dumps(c['neighborhoods']),
            venues=json.dumps(c['venues']),
            categories=json.dumps(c['categories']),
            airports=json.dumps(c['airports']),
            event_copy=c.get('event_copy', ''),
            faqs=json.dumps(c['faqs'])))

    for d in geo['destinations']:
        db.session.add(Destination(
            slug=d['slug'], title=d['title'], city=d['city'],
            city_slug=d.get('city_slug', ''), state=d.get('state', ''),
            street=d.get('street', ''), postal=d.get('postal', ''),
            lat=d.get('lat'), lng=d.get('lng'),
            featured=json.dumps(d['featured']), rates=json.dumps(d['rates']),
            partner_heading=d.get('partner_heading', ''),
            partner_paras=json.dumps(d.get('partner_paras', [])),
            faqs=json.dumps(d['faqs']),
            popular=json.dumps(d.get('popular', []))))

    for f in facilities:
        ap = f.get('airport') or {}
        db.session.add(Facility(
            id=int(f['id']), title=f['title'], slug=f.get('slug', ''),
            city=f['city'], city_slug=f.get('city_slug', ''), state=f.get('state', ''),
            street=f.get('street', ''), postal=f.get('postal', ''),
            lat=f.get('lat'), lng=f.get('lng'), operator=f.get('operator', ''),
            facility_type=f.get('facility_type', 'unknown'),
            rating_avg=f.get('rating_avg') or 0.0,
            rating_count=f.get('rating_count') or 0,
            rating_dist=json.dumps(f.get('rating_dist') or [0, 0, 0, 0, 0]),
            prompt_counts=json.dumps(f.get('prompt_counts') or []),
            amenities=json.dumps(f.get('amenities') or []),
            restrictions=json.dumps(f.get('restrictions') or []),
            getting_there=f.get('getting_there', ''),
            redemption=json.dumps(f.get('redemption') or []),
            always_open=bool(f.get('always_open')),
            hours_text=json.dumps(f.get('hours_text') or []),
            clearance_inches=f.get('clearance_inches'),
            monthly_ok=f.get('monthly_rate') is not None,
            cancellable=bool(f.get('cancellable', True)),
            base_rate=f.get('base_rate') or 0.0,
            daily_rate=f.get('daily_rate') or 0.0,
            increment_rate=f.get('increment_rate') or 0.0,
            monthly_rate=f.get('monthly_rate'),
            images=json.dumps(f.get('images') or []),
            airport_code=ap.get('code'),
            airport_daily_rate=ap.get('daily_rate'),
            airport_facility_fee=ap.get('facility_fee') or 0.0,
            airport_shuttle=bool(ap.get('shuttle')),
            airport_distance_m=ap.get('distance_m'),
            parking_pass=ap.get('parking_pass') or ''))

    for a in geo['airports']:
        db.session.add(Airport(
            code=a['code'], title=a['title'], info_title=a.get('info_title', ''),
            city=a.get('city', ''), state=a.get('state', ''),
            street=a.get('street', ''), postal=a.get('postal', ''),
            lat=a.get('lat'), lng=a.get('lng'), url_slug=a.get('url_slug', ''),
            faqs=json.dumps(a.get('faqs') or [])))

    # events: venue harvest carries real parking windows; the destination-page
    # event lists (without windows) are merged in for venues the venue harvest
    # does not cover, with the upstream +/-1h window. All times are stored on
    # the venue's local base so the destination page, suggest labels, and the
    # event-search banner agree.
    city_tz_by_name = {c['name']: c.get('timezone')
                       for c in geo['cities'] if c.get('timezone')}
    city_tz_by_name.setdefault('The Bronx', 'America/New_York')
    city_tz_by_name.setdefault('Washington', 'America/New_York')
    seen_events = set()
    for v in geo['venues']:
        tz = _venue_tz(v.get('city'), v.get('state'), city_tz_by_name)
        for e in v['events']:
            if e['id'] in seen_events:
                continue
            seen_events.add(e['id'])
            db.session.add(Event(
                id=e['id'], title=e['title'], venue_title=v['title'],
                venue_city=v.get('city', ''), venue_slug=v.get('slug') or '',
                starts=_utc_to_local(e.get('starts'), tz),
                ends=_utc_to_local(e.get('ends'), tz),
                window_starts=e.get('window_starts') or '',
                window_ends=e.get('window_ends') or '',
                description=e.get('description') or '',
                seo_url=e.get('seo_url') or ''))
    for d in geo['destinations']:
        tz = _venue_tz(d.get('city'), d.get('state'), city_tz_by_name)
        for e in d.get('events') or []:
            if not e.get('id') or e['id'] in seen_events:
                continue
            seen_events.add(e['id'])
            ws = _utc_to_local(e.get('starts'), tz)
            we = _utc_to_local(e.get('ends'), tz)
            if ws and we:
                w_start = _iso(datetime.fromisoformat(ws) - timedelta(hours=1))
                w_end = _iso(datetime.fromisoformat(we) + timedelta(hours=1))
            else:
                w_start, w_end = '', ''
            db.session.add(Event(
                id=e['id'], title=e['title'], venue_title=d['title'],
                venue_city=d.get('city', ''), venue_slug=d['slug'],
                starts=ws, ends=we, window_starts=w_start, window_ends=w_end,
                description='', seo_url=''))

    for f in content['faqs']:
        db.session.add(Faq(category=f['category'], question=f['q'], answer=f['a']))

    # stadium directory (the /parking/stadium-parking page) — hrefs parsed to
    # (city_slug, slug) at seed time so the route never touches JSON
    for group in geo['stadiums']:
        for s in group['stadiums']:
            rest = (s.get('href') or '').strip('/').split('/destination/')[-1]
            parts = rest.split('/')
            city_slug = parts[0] if len(parts) > 1 else ''
            slug = parts[1] if len(parts) > 1 else parts[0]
            db.session.add(Stadium(league=group['league'], name=s['name'],
                                   team=s.get('team', ''), city_slug=city_slug,
                                   slug=slug))

    # static marketing pages — section lists stored once instead of being
    # re-read from JSON on every request
    for slug, sections in (content.get('pages') or {}).items():
        db.session.add(StaticPage(slug=slug, sections=json.dumps(sections)))

    promo = content['promo']
    db.session.add(PromoCode(code=promo['code'], pct=promo['pct'],
                             description=promo['restrictions']))

    # per-facility reviews: aggregate numbers are the real upstream rating
    # distribution; individual rows are deterministic, upstream-format samples
    # (anonymous rating / date / duration / vehicle + driver tags).
    fac_by_id = {str(f['id']): f for f in facilities}
    for fid, f in sorted(fac_by_id.items(), key=lambda kv: int(kv[0])):
        prompts = f.get('prompt_counts') or []
        n = 6
        for i in range(n):
            rating = 5 if i < 4 else (4 if i < 5 else 3)
            day = (i * 3 + int(fid) % 7) % 22
            review = Review(
                facility_id=int(fid), rating=rating,
                review_date=f'September {26 - day}, 2026',
                duration=REVIEW_DURATIONS[(int(fid) + i) % len(REVIEW_DURATIONS)],
                vehicle=REVIEW_VEHICLES[(int(fid) * 3 + i) % len(REVIEW_VEHICLES)],
                tags=json.dumps([p['name'] for p in prompts[:3]]))
            db.session.add(review)
    db.session.commit()


def run_seed_users(db, User, Reservation, PaymentMethod, Favorite, Facility,
                   bcrypt, PromoCode):
    facilities = {str(f['id']): f for f in _load('source_data_facilities.json')}

    users = []
    for u in BENCHMARK_USERS:
        user = User(username=u['username'], email=u['email'],
                    password_hash=BENCHMARK_PASSWORD_HASH,
                    first_name=u['first_name'], last_name=u['last_name'])
        plates = [('IL-AL7431', 'Toyota Camry Hybrid'), ('IL-BO1180', 'Honda CR-V'),
                  ('NY-CA2245', 'Volkswagen Tiguan'), ('IL-DA6690', 'Ford Explorer')]
        plate, vehicle = plates[len(users)]
        user.license_plate = plate
        user.vehicle = vehicle
        phone = ['312-555-0142', '312-555-0177', '212-555-0198', '312-555-0121'][len(users)]
        user.phone = phone
        users.append(user)
        db.session.add(user)

    db.session.flush()

    cards = [('Visa', '4242'), ('Mastercard', '5309'), ('Visa', '1881'),
             ('American Express', '1005')]
    for i, user in enumerate(users):
        brand, last4 = cards[i]
        db.session.add(PaymentMethod(user_id=user.id, brand=brand, last4=last4,
                                     exp_month=11, exp_year=2028, is_default=True,
                                     label='Personal'))
        if i in (0, 2):
            db.session.add(PaymentMethod(user_id=user.id, brand='Mastercard',
                                         last4='6742', exp_month=3, exp_year=2027,
                                         is_default=False, label='Work'))

    for r in USER_RESERVATIONS:
        f = facilities.get(str(r['facility']))
        if not f:
            continue
        user = users[r['user']]
        facility = f
        start = datetime.fromisoformat(r['start'])
        end = datetime.fromisoformat(r['end'])
        # price the seeded reservation with the mirror's own deterministic model
        if r['kind'] == 'event':
            subtotal = round(f['daily_rate'] * 1.5, 2)
            fee = round(subtotal * 0.085, 2)
            fac_fee = 0.0
        elif r['kind'] == 'airport':
            days = max(1, round((end - start).total_seconds() / 86400.0))
            subtotal = round(f['airport']['daily_rate'] * days, 2)
            fee = 4.00
            fac_fee = f['airport'].get('facility_fee') or 0.0
        elif r['kind'] == 'monthly':
            subtotal = f['monthly_rate'] or 0.0
            fee = round(max(0.99, subtotal * 0.06), 2)
            fac_fee = 0.0
        else:
            hours = max(0.25, (end - start).total_seconds() / 3600.0)
            sub = f['base_rate'] + f['increment_rate'] * (hours - 1)
            subtotal = round(min(f['daily_rate'], max(sub, f['base_rate'])), 2)
            fee = round(max(0.99, subtotal * 0.06), 2)
            fac_fee = 0.0
        db.session.add(Reservation(
            code=r['code'], user_id=user.id, email=user.email, phone=user.phone,
            facility_id=int(r['facility']), kind=r['kind'],
            starts=r['start'], ends=r['end'], subtotal=subtotal,
            service_fee=fee, facility_fee=fac_fee,
            total=round(subtotal + fee + fac_fee, 2),
            status=r['status'], license_plate=r['plate'], vehicle=r['vehicle'],
            created_at='2026-09-22T10:30',
            parking_pass=(f['airport'].get('parking_pass') if r['kind'] == 'airport'
                          else 'Scan In/Out')))

    fav_specs = [(0, ['5284', '104341', '5283']), (1, ['2175', '129876']),
                 (2, ['16130', '5283', '104341']), (3, ['12897'])]
    for user_idx, fids in fav_specs:
        for fid in fids:
            if fid in facilities:
                db.session.add(Favorite(user_id=users[user_idx].id,
                                        facility_id=int(fid)))
    db.session.commit()


if __name__ == "__main__":
    import os
    import shutil
    import sys
    # The Dockerfile seed gate wipes instance/ and instance_seed/ before
    # rerunning this script, so the instance directory must be (re)created
    # here before the app engine opens instance/spothero.db (same contract
    # as the mta / imgur / instructure build-generated seeds). Importing the
    # app module runs db.create_all() plus both idempotent seed gates.
    os.makedirs(HERE / "instance", exist_ok=True)
    sys.path.insert(0, str(HERE))
    import app  # noqa: F401  (module import performs the seeding)
    seed_dir = HERE / "instance_seed"
    seed_dir.mkdir(exist_ok=True)
    shutil.copyfile(HERE / "instance" / "spothero.db", seed_dir / "spothero.db")
    print("seed complete; copied instance/spothero.db to instance_seed/spothero.db")
