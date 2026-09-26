#!/usr/bin/env python3
"""Deterministic build-time seeder for the RE/MAX mirror.

All content rows come from the tracked source_data_*.json snapshots captured
from https://www.remax.com/ on 2026-09-24 (see scripts_dev/build_source_data.py,
which normalizes the Playwright captures in scraped_data/). Benchmark users use
a frozen bcrypt hash so the SQLite seed is byte-reproducible on every build
(PYTHONHASHSEED=0).

Seeding is idempotent: run_seed_content / run_seed_users each early-return when
their tables are already populated (the gates live in app.py).
"""
from __future__ import annotations

import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

MIRROR_TODAY = '2026-09-24'
SEED_STAMP = '2026-09-24 14:30'

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


def _dumps(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


def run_seed_content(db, Listing, Rental, Agent, Office, BlogPost):
    listings = _load('source_data_listings.json')['listings']
    rentals = _load('source_data_rentals.json')['rentals']
    agents = _load('source_data_agents.json')['agents']
    offices = _load('source_data_offices.json')['offices']
    content = _load('source_data_content.json')

    for l in listings:
        db.session.add(Listing(
            id=l['id'], mls=l['mls'], slug=l['slug'], price=l['price'],
            beds=l['beds'], baths=l['baths'], sqft=l['sqft'],
            home_type=l['home_type'], prop_sub_type=l.get('prop_sub_type'),
            street=l['street'], city=l['city'], state=l['state'], zip=l['zip'],
            status=l['status'], badges=_dumps(l['badges']),
            broker=l['broker'], agent=l['agent'], agent_phone=l.get('agent_phone'),
            photo=l['photo'], gallery=_dumps(l['gallery']),
            description=l.get('description'),
            quick_overview=_dumps(l.get('quick_overview') or []),
            sections=_dumps(l.get('sections') or {}),
            open_houses=_dumps(l['open_houses']),
            presented_by=_dumps(l.get('presented_by')),
            listed_by_agent=l.get('listed_by_agent'),
            listed_by_office=l.get('listed_by_office'),
            updated_label=l.get('updated_label'),
            listed_date=l['listed_date'],
            is_luxury=l['is_luxury'], has_detail=l['has_detail']))
    db.session.flush()

    for r in rentals:
        db.session.add(Rental(
            id=r['id'], slug=r['slug'], street=r['street'], city=r['city'],
            state=r['state'], zip=r['zip'], price=r['price'], beds=r['beds'],
            baths=r['baths'], sqft=r['sqft'], date_added=r.get('date_added'),
            description=r.get('description'), photo=r.get('photo'),
            gallery=_dumps(r.get('gallery') or []),
            quick_overview=_dumps(r.get('quick_overview') or []),
            presented_by=_dumps(r.get('presented_by')),
            listed_by_agent=r.get('listed_by_agent'),
            listed_by_office=r.get('listed_by_office'),
            has_detail=r['has_detail']))
    db.session.flush()

    for a in agents:
        db.session.add(Agent(
            id=a['id'], remax_id=a['remax_id'], slug=a['slug'], name=a['name'],
            title=a['title'], licensed=a.get('licensed'), city=a.get('city'),
            state=a.get('state'), office_name=a.get('office_name'),
            phone=a.get('phone'), photo=a.get('photo'), about=a.get('about'),
            hobbies=_dumps(a.get('hobbies') or []),
            civic=_dumps(a.get('civic') or []),
            years=a.get('years'),
            license_numbers=_dumps(a.get('license_numbers') or []),
            languages=_dumps(a.get('languages') or []),
            specialties=_dumps(a.get('specialties') or []),
            designations=_dumps(a.get('designations') or []),
            website=a.get('website'), office_address=a.get('office_address')))
    db.session.flush()

    for o in offices:
        db.session.add(Office(
            id=o['id'], remax_id=o['remax_id'], slug=o['slug'], name=o['name'],
            address=o.get('address'), city=o.get('city'), state=o.get('state'),
            phone=o.get('phone'), photo=o.get('photo'), about=o.get('about'),
            website=o.get('website'),
            service_areas=_dumps(o.get('service_areas') or []),
            languages=_dumps(o.get('languages') or []),
            specialties=_dumps(o.get('specialties') or []),
            has_detail=o.get('has_detail', False)))
    db.session.flush()

    for p in content['blog_posts']:
        db.session.add(BlogPost(
            slug=p['slug'], title=p['title'], image=p.get('image'),
            text=p.get('text') or ''))
    db.session.commit()


def run_seed_users(db, User, Favorite, SavedSearch, Inquiry, ListingAlert, Listing):
    for spec in BENCHMARK_USERS:
        user = User(
            username=spec['username'], email=spec['email'],
            first_name=spec['first_name'], last_name=spec['last_name'],
            display_name=f"{spec['first_name']} {spec['last_name']}",
            password_hash=BENCHMARK_PASSWORD_HASH,
            buyer_type='First time home buyer',
            created_at=SEED_STAMP)
        db.session.add(user)
    db.session.flush()

    users = {u.username: u for u in User.query.all()}

    def pick(city, n, **filters):
        q = Listing.query.filter_by(city=city, **filters)
        return q.order_by(Listing.id).limit(n).all()

    # Alice — favorites in Redmond + a saved search + one sent inquiry
    alice = users['alice_j']
    for l in pick('Redmond', 3):
        db.session.add(Favorite(user_id=alice.id, listing_id=l.id, created_at=SEED_STAMP))
    db.session.add(SavedSearch(
        user_id=alice.id, name='Redmond condos under $700k', city='Redmond',
        state='WA', home_type='Condo', min_price=None, max_price=700000,
        beds=2, created_at=SEED_STAMP))
    target = Listing.query.filter_by(city='Redmond').order_by(Listing.id).first()
    if target:
        db.session.add(Inquiry(
            user_id=alice.id, listing_id=target.id, kind='listing',
            name='Alice Johnson', email='alice.j@test.com',
            phone='(206) 555-0142',
            message='Hi, I would like more information about this property.',
            created_at=SEED_STAMP))

    # Bob — favorites in Austin + two saved searches
    bob = users['bob_c']
    for l in pick('Austin', 4):
        db.session.add(Favorite(user_id=bob.id, listing_id=l.id, created_at=SEED_STAMP))
    db.session.add(SavedSearch(
        user_id=bob.id, name='Austin houses', city='Austin', state='TX',
        home_type='House', min_price=400000, max_price=900000, beds=3,
        created_at=SEED_STAMP))
    db.session.add(SavedSearch(
        user_id=bob.id, name='Denver townhouses', city='Denver', state='CO',
        home_type='Townhouse', min_price=None, max_price=800000, beds=None,
        created_at=SEED_STAMP))

    # Carol — favorites across Miami + a listing alert
    carol = users['carol_d']
    for l in pick('Miami', 2):
        db.session.add(Favorite(user_id=carol.id, listing_id=l.id, created_at=SEED_STAMP))
    for l in pick('Naples', 2):
        db.session.add(Favorite(user_id=carol.id, listing_id=l.id, created_at=SEED_STAMP))
    db.session.add(ListingAlert(
        user_id=carol.id, email='carol.d@test.com', city='Miami', state='FL',
        created_at=SEED_STAMP))

    # David — favorites in Chicago + an open-house inquiry
    david = users['david_k']
    for l in pick('Chicago', 3):
        db.session.add(Favorite(user_id=david.id, listing_id=l.id, created_at=SEED_STAMP))
    oh = (Listing.query.filter(Listing.open_houses != '[]',
                               Listing.city == 'Chicago')
          .order_by(Listing.id).first())
    if oh:
        db.session.add(Inquiry(
            user_id=david.id, listing_id=oh.id, kind='tour',
            name='David Kim', email='david.k@test.com', phone='(312) 555-0177',
            message='I would like to tour this home.',
            preferred_date='Saturday October 3rd', created_at=SEED_STAMP))
    db.session.commit()


if __name__ == '__main__':
    # Standalone deterministic build: rebuild the seed DB from the snapshots.
    import os
    import sys

    sys.path.insert(0, str(HERE))
    db_path = HERE / 'instance' / 're_max.db'
    if db_path.exists():
        db_path.unlink()
    os.environ.setdefault('REMAX_DB_URI', f"sqlite:///{db_path}")
    from app import app, db, seed_database, seed_benchmark_users  # noqa: E402

    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_database()
        seed_benchmark_users()
        from app import Listing, Rental, Agent, Office, BlogPost, User, Favorite
        print(f"seeded: listings={Listing.query.count()} rentals={Rental.query.count()} "
              f"agents={Agent.query.count()} offices={Office.query.count()} "
              f"posts={BlogPost.query.count()} users={User.query.count()} "
              f"favorites={Favorite.query.count()}")
