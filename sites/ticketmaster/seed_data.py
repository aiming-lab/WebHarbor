#!/usr/bin/env python3
"""Deterministic build-time seeder for the Ticketmaster mirror.

Reads the tracked source_data_*.json snapshots (captured from the live site) and materializes artists, venues, events,
ticket listings, presales, benchmark users and their orders / cards /
favorites. Run with PYTHONHASHSEED=0 during the image build so the SQLite
output is byte-reproducible on every build.

Ticket listings follow the real upstream pattern captured on the event pages:
"Sec MC • Row O — Standard Admission — $40.60" where the displayed price is
face value plus a 37.6% service fee (calibrated from the captured Reno
breakdown: $29.50 face + $11.10 fee = $40.60 incl. fees). Section inventories
per venue type mirror the captured manifests (ORCH/MEZZ/BALC for theaters,
numbered sections for arenas, GA for clubs). Faces are quantized to $0.50 as
upstream, so a minimum-price tie between two listings of the same event and
ticket type is possible; _detie_minimums() breaks such ties (+$0.01 face on
the later listing) so "cheapest" questions always have exactly one answer,
while keeping the first-displayed cheapest listing (and the benchmark users'
orders, which are built from the cheapest listing) byte-stable.

The benchmark users' saved favorites are pinned to explicit event / artist
IDs so the demo fixtures do not drift when the event catalog is extended.
"""
import hashlib
import json
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MIRROR_DATE = datetime(2026, 9, 27)
SERVICE_FEE_RATE = 0.376
# bcrypt hash of 'TestPass123!' — frozen so the seed DB is byte-reproducible
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')

USERS = [
    {'username': 'alice_j', 'email': 'alice.j@test.com',
     'display_name': 'Alice Johnson', 'first': 'Alice', 'last': 'Johnson',
     'phone': '(212) 555-0143', 'zip': '10001'},
    {'username': 'bob_c', 'email': 'bob.c@test.com',
     'display_name': 'Bob Chen', 'first': 'Bob', 'last': 'Chen',
     'phone': '(617) 555-0182', 'zip': '02116'},
    {'username': 'carol_d', 'email': 'carol.d@test.com',
     'display_name': 'Carol Davis', 'first': 'Carol', 'last': 'Davis',
     'phone': '(312) 555-0117', 'zip': '60601'},
    {'username': 'david_k', 'email': 'david.k@test.com',
     'display_name': 'David Kim', 'first': 'David', 'last': 'Kim',
     'phone': '(206) 555-0159', 'zip': '98101'},
]

# Section inventories per venue type, mirroring the seat manifests captured on
# the real event pages (Grand Sierra Theatre: MC/ML/MR/OC/OLT/ORT/BALC...;
# National Theatre: LBALC/RBALC/RMEZZ...) and standard arena maps.
THEATER_SECTIONS = [
    ('OC', 'Orchestra Center', 1.0), ('OLT', 'Orchestra Left', 0.85),
    ('ORT', 'Orchestra Right', 0.85), ('MC', 'Mezzanine Center', 0.62),
    ('ML', 'Mezzanine Left', 0.5), ('MR', 'Mezzanine Right', 0.5),
    ('BALCL', 'Balcony Left', 0.42), ('BALCC', 'Balcony Center', 0.48),
    ('BALCR', 'Balcony Right', 0.42),
]
ARENA_SECTIONS = [
    ('FLR A', 'Floor A', 1.5), ('FLR B', 'Floor B', 1.25), ('FLR C', 'Floor C', 1.05),
    ('101', 'Lower Level 101', 0.95), ('102', 'Lower Level 102', 0.9),
    ('103', 'Lower Level 103', 0.9), ('110', 'Lower Level 110', 1.0),
    ('111', 'Lower Level 111', 1.0), ('118', 'Lower Level 118', 0.95),
    ('201', 'Upper Level 201', 0.55), ('202', 'Upper Level 202', 0.5),
    ('203', 'Upper Level 203', 0.5), ('210', 'Upper Level 210', 0.58),
    ('211', 'Upper Level 211', 0.58), ('218', 'Upper Level 218', 0.55),
    ('CLUB', 'Club Level', 1.15),
]
CLUB_SECTIONS = [
    ('GA', 'General Admission Floor', 1.0), ('BALC', 'Balcony', 0.7),
    ('LOGE', 'Loge', 0.85),
]
STADIUM_SECTIONS = [
    ('FLD', 'Field Level', 1.6), ('100', '100 Level', 1.0),
    ('200', '200 Level', 0.7), ('300', '300 Level', 0.5),
    ('400', '400 Level', 0.4), ('SUITE', 'Suite Level', 2.2),
]

CATEGORY_BASE = {
    'Music': (45.0, 260.0),
    'Sports': (38.0, 240.0),
    'Arts & Theater': (32.0, 195.0),
    'Family': (24.0, 110.0),
}

PRESALE_TEMPLATES = [
    ('Citi® Cardmember Presale',
     'To access the sale, use the first 6 digits of your eligible Citi® credit '
     'card or Citibank Debit Card as your presale code. You will also need to '
     'use your Citi® card to successfully complete your purchase.'),
    ('Artist Fan Club Presale',
     'Registered fan club members receive a presale code by email before the '
     'general public on-sale. Join the artist mailing list to receive codes '
     'for future presales.'),
    ('Venue Presale',
     'Sign up for the venue newsletter to receive the presale code. Availability '
     'during the presale is limited and not guaranteed.'),
    ('VIP Package Presale',
     'The artist is offering VIP Packages, which include a ticket and exclusive '
     'perks. To purchase, look for the gold star on the seat map or at the top '
     'of the list of ticket options when the sale starts.'),
]


def _h(*parts):
    return hashlib.sha1('|'.join(str(p) for p in parts).encode()).hexdigest()


def _rand(*parts, lo=0.0, hi=1.0):
    return lo + (int(_h(*parts)[:8], 16) / 0xFFFFFFFF) * (hi - lo)


def venue_type(venue):
    name = (venue['name'] or '').lower()
    if any(k in name for k in ('theatre', 'theater', 'playhouse', 'opera')):
        return 'theater'
    if any(k in name for k in ('stadium', 'speedway', 'field', 'coliseum')):
        return 'stadium'
    if any(k in name for k in ('arena', 'center', 'centre', 'dome', 'pavilion',
                               'hall', 'amphitheatre', 'amphitheater', 'ballpark',
                               'park')):
        return 'arena'
    return 'club'


def section_layout(venue):
    return {
        'theater': THEATER_SECTIONS,
        'arena': ARENA_SECTIONS,
        'stadium': STADIUM_SECTIONS,
        'club': CLUB_SECTIONS,
    }[venue_type(venue)]


def _listing_price(face):
    """All-in price exactly as the TicketListing.price property computes it."""
    return round(face + round(face * SERVICE_FEE_RATE, 2), 2)


def _detie_minimums(rows):
    """Keep every 'cheapest <ticket type>' question uniquely answerable.

    Ticket faces are quantized to $0.50 (the captured upstream pattern), so two
    listings of one event and ticket type can land on the same all-in price.
    Within each ticket type, when several listings share the minimum all-in
    price — across all listings of that type, or among the ones with 4+ seats
    together (the two cuts the 'cheapest available / cheapest with N seats'
    questions actually use) — nudge every tied listing after the first in
    generation order by +$0.01 face value. The first listing keeps its price,
    so the cheapest option an event page displays first (and every benchmark
    order, which is built from the cheapest listing) is unchanged; only the
    price ties that would make a 'cheapest' answer ambiguous are broken.
    """
    by_type = {}
    for row in rows:
        by_type.setdefault(row['ticket_type'], []).append(row)
    for type_rows in by_type.values():
        for subset in (type_rows,
                       [r for r in type_rows if r['qty_available'] >= 4]):
            if not subset:
                continue
            min_price = min(_listing_price(r['face_value']) for r in subset)
            tied = [r for r in subset
                    if _listing_price(r['face_value']) == min_price]
            for row in tied[1:]:
                row['face_value'] = round(row['face_value'] + 0.01, 2)


def build_listings(event, venue):
    """Deterministic ticket inventory for one event."""
    rows = []
    lo, hi = CATEGORY_BASE.get(event['category'], (35.0, 180.0))
    base_face = lo + _rand(event['id'], 'face') * (hi - lo)
    layout = section_layout(venue)
    for section, desc, tier in layout:
        n_rows = 4 + int(_rand(event['id'], section, 'rows') * 5)
        start_row = chr(65 + int(_rand(event['id'], section, 'start') * 6))
        start_idx = ord(start_row)
        for i in range(n_rows):
            row = chr(start_idx + i) if start_idx + i <= 90 else 'Z'
            # earlier rows in premium sections cost more
            row_bonus = (12 - i) / 40.0 * tier
            face = base_face * (tier * 0.85 + row_bonus + 0.35)
            face = max(19.5, round(face * 2) / 2 - 0.01 + 0.01)
            face = round(face, 2)
            qty = 2 + int(_rand(event['id'], section, row, 'qty') * 5)
            rows.append({
                'event_id': event['id'],
                'section': section,
                'section_desc': desc,
                'row': row,
                'qty_available': qty,
                'face_value': face,
                'ticket_type': 'Standard Admission',
                'accessible': False,
            })
    # VIP package listings on premium sections for ~45% of primary events
    if _rand(event['id'], 'vip') < 0.45 and not event.get('is_add_on'):
        vip_sections = [s for s in layout if s[2] >= 1.0][:2]
        for section, desc, tier in vip_sections:
            face = round(base_face * (2.1 + tier * 0.4), 2)
            rows.append({
                'event_id': event['id'],
                'section': section,
                'section_desc': desc,
                'row': 'A',
                'qty_available': 2 + int(_rand(event['id'], section, 'vipqty') * 3),
                'face_value': face,
                'ticket_type': 'VIP Package',
                'accessible': False,
            })
    # Accessible listings (one or two per event, mirroring the ADA filter)
    if _rand(event['id'], 'ada') < 0.7 and not event.get('is_add_on'):
        section, desc, tier = layout[len(layout) // 2]
        rows.append({
            'event_id': event['id'],
            'section': section,
            'section_desc': desc,
            'row': 'W',
            'qty_available': 2,
            'face_value': round(base_face * tier * 0.9, 2),
            'ticket_type': 'Accessible',
            'accessible': True,
        })
    _detie_minimums(rows)
    return rows


def build_presales(event):
    """Deterministic presale timeline before the public on-sale."""
    if event.get('is_add_on'):
        return []
    if _rand(event['id'], 'presale') > 0.35:
        return []
    start = datetime.strptime(event['date'], '%Y-%m-%d')
    out = []
    n = 1 + int(_rand(event['id'], 'presalen') * 2)
    for i in range(n):
        title, body = PRESALE_TEMPLATES[int(_rand(event['id'], 'pt', i) * len(PRESALE_TEMPLATES))]
        presale_end = start - timedelta(days=60 + i * 5)
        presale_start = presale_end - timedelta(days=2 + int(_rand(event['id'], 'pw', i) * 3))
        out.append({
            'event_id': event['id'],
            'title': title,
            'description': body,
            'start': presale_start.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'end': presale_end.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'code': 'CITI' + _h(event['id'], 'code', i)[:4].upper() if 'Citi' in title else None,
        })
    return out


def load_json(name):
    with open(os.path.join(BASE_DIR, name), encoding='utf-8') as fh:
        return json.load(fh)


def build_seed(db):
    """Materialize the tracked source snapshots into the DB (idempotent, gated by app.py)."""
    from app import (Artist, Event, Favorite, Order, PaymentMethod, Presale,
                     TicketListing, Venue)

    artists = load_json('source_data_artists.json')
    venues = load_json('source_data_venues.json')
    events = load_json('source_data_events.json')

    for a in artists:
        db.session.add(Artist(id=str(a['id']), name=a['name'], slug=a['slug'],
                              image=a.get('image'), rating=a.get('rating'),
                              rating_count=a.get('rating_count'),
                              category=None))
    for v in venues:
        db.session.add(Venue(id=str(v['id']), name=v['name'], slug=v['slug'],
                             city=v['city'], state=v.get('state'),
                             address=v.get('address'), image=v.get('image'),
                             capacity=v.get('capacity')))
    db.session.commit()

    venue_by_id = {str(v['id']): v for v in venues}
    for e in events:
        venue = venue_by_id.get(str(e['venue_id']))
        listings = build_listings(e, venue) if venue else []
        prices = [round(l['face_value'] * (1 + SERVICE_FEE_RATE), 2) for l in listings]
        db.session.add(Event(
            id=e['id'], name=e['name'], slug=e['slug'],
            artist_id=str(e['artist_id']) if e.get('artist_id') else None,
            venue_id=str(e['venue_id']),
            date=e['date'], time=e.get('time'), weekday=e.get('weekday'),
            category=e['category'], subcategory=e.get('subcategory'),
            status=e.get('status', 'onsale'), image=e.get('image'),
            important_info=e.get('important_info'),
            ticket_limit=8 if e['category'] in ('Music', 'Arts & Theater') else 12,
            multi_date=bool(e.get('multi_date')), partner=bool(e.get('partner')),
            is_add_on=bool(e.get('is_add_on')),
            price_min=min(prices) if prices else None,
            price_max=max(prices) if prices else None,
        ))
        for l in listings:
            db.session.add(TicketListing(**l))
        for p in build_presales(e):
            db.session.add(Presale(**p))
    db.session.commit()


def build_benchmark_users(db):
    """4 benchmark users with pre-existing orders, cards and favorites (gated)."""
    from app import (Event, Favorite, Order, PaymentMethod,
                     TicketListing, User)

    users = {}
    for spec in USERS:
        user = User(email=spec['email'], password_hash=BENCHMARK_PASSWORD_HASH,
                    first_name=spec['first'], last_name=spec['last'],
                    phone=spec['phone'], zip=spec['zip'])
        db.session.add(user)
        users[spec['username']] = user
    db.session.commit()

    cards = [
        ('alice_j', 'Visa', '4242', 8, 2029, 'Alice Johnson'),
        ('alice_j', 'Mastercard', '5309', 11, 2027, 'Alice Johnson'),
        ('bob_c', 'Visa', '1881', 3, 2028, 'Bob Chen'),
        ('bob_c', 'Amex', '1004', 7, 2028, 'Bob Chen'),
        ('carol_d', 'Visa', '0341', 5, 2029, 'Carol Davis'),
        ('david_k', 'Mastercard', '6771', 12, 2027, 'David Kim'),
    ]
    for uname, brand, last4, month, year, holder in cards:
        db.session.add(PaymentMethod(user_id=users[uname].id, brand=brand,
                                     last4=last4, exp_month=month,
                                     exp_year=year, holder=holder))
    db.session.commit()

    # past orders: 1-3 per user, deterministic picks from the catalog
    all_events = Event.query.filter_by(is_add_on=False).order_by(Event.date).all()
    order_specs = [
        ('alice_j', 0), ('alice_j', 40), ('bob_c', 7),
        ('bob_c', 61), ('carol_d', 13), ('david_k', 5),
    ]
    for i, (uname, ev_idx) in enumerate(order_specs):
        if not all_events:
            break
        event = all_events[ev_idx % len(all_events)]
        listing = (TicketListing.query
                   .filter_by(event_id=event.id, ticket_type='Standard Admission')
                   .order_by(TicketListing.face_value).first())
        if not listing:
            continue
        qty = 2 if i % 2 == 0 else 3
        unit = round(listing.face_value * (1 + SERVICE_FEE_RATE), 2)
        user = users[uname]
        card = user.payment_methods[0]
        order = Order(
            order_no=f'TM{MIRROR_DATE.strftime("%y%m%d")}{4100 + i}',
            user_id=user.id, event_id=event.id, listing_id=listing.id,
            section=listing.section, section_desc=listing.section_desc,
            row=listing.row, qty=qty, unit_price=unit,
            face_total=round(listing.face_value * qty, 2),
            fee_total=round(listing.fee * qty, 2),
            total=round(unit * qty, 2),
            delivery='mobile', card_brand=card.brand, card_last4=card.last4,
            status='confirmed',
            created_at=(MIRROR_DATE - timedelta(days=6 + i)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            placed_at=(MIRROR_DATE - timedelta(days=6 + i)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        )
        db.session.add(order)

    # favorites: explicit per-user fixtures (event / artist IDs pinned so the
    # demo accounts' saved items do not drift when the catalog grows - the
    # IDs below are the exact entities of the original fixture build; e.g.
    # Bob's saved events are the Gorillaz and Teddy Swims tours and David's
    # saved event is the Rod Wave tour, as the tasks describe)
    fav_specs = [
        ('alice_j', [('event', '1B00647FC26CB897'), ('artist', '805921'),
                     ('event', '0B0064AFEE8274CF'), ('artist', '805966')]),
        ('bob_c', [('event', '02006459D94912C9'), ('artist', '2431961'),
                   ('event', '3000648A98213802')]),
        ('carol_d', [('event', '1D00651B0545B1AC'), ('artist', '1542376'),
                     ('event', '0500648EE29215A3'), ('artist', '2230445'),
                     ('event', '030064AEEB4818A5')]),
        ('david_k', [('event', '0C0064D2AAFF8050'), ('artist', '1732682'),
                     ('event', '17006455FF50D564')]),
    ]
    for uname, refs in fav_specs:
        user = users[uname]
        for kind, ref in refs:
            db.session.add(Favorite(user_id=user.id,
                                    event_id=ref if kind == 'event' else None,
                                    artist_id=ref if kind == 'artist' else None,
                                    created_at=MIRROR_DATE.strftime('%Y-%m-%dT%H:%M:%SZ')))
    db.session.commit()


if __name__ == '__main__':
    # Build instance/ticketmaster.db from scratch (idempotent). Importing app
    # runs the same gated bootstrap the container boot path uses.
    from app import main
    main()
