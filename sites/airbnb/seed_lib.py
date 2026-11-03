#!/usr/bin/env python3
"""Deterministic seed builder for the airbnb mirror.

Everything materialized here comes from the tracked source_data/*.json
snapshots (captured 2026-09-30) in a fixed order; the four benchmark
accounts and their wishlists/bookings are authored fixtures following
the u_s_customs/zara/ziprecruiter precedent: every listing, experience,
review and price they reference is a real captured upstream row (real
listing id, name, city, nightly rate), and every timestamp is a frozen
constant so the SQLite output is byte-reproducible (PYTHONHASHSEED=0).
"""
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

BENCHMARK_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')

MIRROR_TS = '2026-09-30'

BENCHMARK_USERS = [
    {
        'email': 'alice.j@test.com',
        'name': 'Alice Johnson',
        'fixture': (
            'wishlist with a Lake Tahoe cabin and a Scottsdale pool home plus '
            'one Austin experience; one confirmed 5-night stay in Scottsdale '
            'and one cancelled 2-night stay in Austin'),
    },
    {
        'email': 'bob.c@test.com',
        'name': 'Bob Chen',
        'fixture': (
            'wishlist of Asheville cabins with hot tubs; one booked Austin '
            'sunset kayak experience for 2 guests'),
    },
    {
        'email': 'carol.d@test.com',
        'name': 'Carol Davis',
        'fixture': (
            'empty default wishlist; one confirmed 2-night Miami stay'),
    },
    {
        'email': 'dana.k@test.com',
        'name': 'Dana Kim',
        'fixture': (
            'two wishlists: "Winter cabins" with two Lake Tahoe listings and '
            '"NYC weekend"; no bookings'),
    },
]


def _load(name):
    with open(os.path.join(HERE, 'source_data', name), encoding='utf-8') as f:
        return json.load(f)


def _first_listing(listings, destination, predicate=lambda l: True):
    """First SERP-order listing of a destination matching predicate."""
    for lid in listings:
        l = listings[lid]
        if l.get('destination') == destination and predicate(l):
            return l
    return None


def normalize_amenity(name):
    return ' '.join(name.lower().replace(':', ' ').split())


def room_category(title, name=''):
    t = (title or '').lower()
    if t.startswith('entire'):
        return 'entire'
    if t.startswith('private room') or t.startswith('room in'):
        return 'private'
    if 'shared room' in t:
        return 'shared'
    return 'entire'


def parse_overview(items):
    """['2 guests', '1 bedroom', '1 bed', '1 bath'] -> dict."""
    out = {'guests': None, 'bedrooms': None, 'beds': None, 'baths': None}
    for it in items or []:
        m = re.match(r'(\d+(?:\.\d+)?) guests?', it)
        if m:
            out['guests'] = int(float(m.group(1)))
            continue
        m = re.match(r'(\d+(?:\.\d+)?) bedrooms?', it)
        if m:
            out['bedrooms'] = int(float(m.group(1)))
            continue
        m = re.match(r'(\d+(?:\.\d+)?) beds?', it)
        if m:
            out['beds'] = int(float(m.group(1)))
            continue
        m = re.match(r'(\d+(?:\.\d+)?) baths?', it)
        if m:
            out['baths'] = float(m.group(1))
    return out


def url_to_name(url):
    """Stable file name derived from the upstream URL path (shared by the
    image downloader; seed and download must agree on the mapping)."""
    base = url.split('?')[0]
    tail = base.rsplit('/', 1)[-1]
    stem, ext = os.path.splitext(tail)
    if not ext:
        ext = '.jpeg'
    if '/im/pictures/' in base:
        prefix = base.split('/im/pictures/')[1].split('/')[0].lower()[:24]
        prefix = ''.join(ch if ch.isalnum() else '-' for ch in prefix).strip('-')
    else:
        prefix = hashlib.sha1(base.encode()).hexdigest()[:12]
    stem = ''.join(ch if ch.isalnum() else '-' for ch in stem)[:60]
    return f"{prefix}--{stem}{ext}"


_INV_MAP = None


def local_image(url):
    """The mirror's local static path for a captured upstream image URL.

    The tracked asset_inventory.json (built by the image download step,
    which verifies the actually-served format) is the
    mapping authority; the deterministic name derivation is the fallback
    for URLs the inventory does not carry."""
    if not url:
        return None
    global _INV_MAP
    if _INV_MAP is None:
        _INV_MAP = {}
        path = os.path.join(HERE, 'asset_inventory.json')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                for row in json.load(f).get('assets', []):
                    _INV_MAP[row['source_url']] = '/' + row['path']
                    _INV_MAP.setdefault(row['source_url'].split('?')[0],
                                        '/' + row['path'])
    hit = _INV_MAP.get(url)
    if hit:
        return hit
    base = url.split('?')[0]
    hit = _INV_MAP.get(base)
    if hit:
        return hit
    return '/static/images/upstream/' + url_to_name(url)


CANONICAL_AMENITY_KEYS = [
    ('hot tub', 'hot tub'), ('pool', 'pool'), ('wifi', 'wifi'),
    ('kitchen', 'kitchen'), ('free parking', 'free parking'),
    ('air conditioning', 'air conditioning'), ('heating', 'heating'),
    ('tv', 'tv'), ('washer', 'washer'), ('dryer', 'dryer'),
    ('dedicated workspace', 'dedicated workspace'),
    ('bbq grill', 'bbq grill'), ('fireplace', 'fireplace'), ('gym', 'gym'),
    ('sauna', 'sauna'), ('ev charger', 'ev charger'), ('crib', 'crib'),
    ('patio or balcony', 'patio or balcony'), ('balcony', 'patio or balcony'),
    ('lake access', 'lake access'), ('mountain view', 'mountain view'),
    ('sea view', 'sea view'), ('beach access', 'beach access'),
    ('ski-in/ski-out', 'ski-in/ski-out'),
    ('freezer', 'freezer'), ('microwave', 'microwave'),
    ('pets allowed', 'pets allowed'),
]


def amenity_flag_map(amenities, pets_allowed=False):
    """Full captured item names PLUS deterministic canonical tokens the
    upstream amenity filter uses (documented keyword rules; declared in
    provenance.derived_fields)."""
    flags = {}
    for group in amenities:
        for item in group.get('items', []):
            key = normalize_amenity(item)
            flags[key] = True
            low = key
            for needle, canon in CANONICAL_AMENITY_KEYS:
                if needle in low and canon not in flags:
                    flags[canon] = True
    if pets_allowed:
        flags['pets allowed'] = True
    return flags


def parse_rating(raw):
    """avgRatingLocalized is '4.98 (483)' or 'New'."""
    if not raw or raw == 'New':
        return None, 0
    m = re.match(r'([0-9.]+)\s*\(([0-9,]+)\)', raw)
    if m:
        return float(m.group(1)), int(m.group(2).replace(',', ''))
    try:
        return float(raw), 0
    except (TypeError, ValueError):
        return None, 0


def seed_all(db):
    """Materialize destinations, listings, reviews and experiences from
    the tracked source snapshots. Idempotent: returns immediately when
    the destinations table is already populated."""
    from app import (Booking, Destination, Experience, Listing,
                     Review, ReviewTag, Wishlist, WishlistItem)

    dests = _load('destinations.json')
    listings = _load('listings.json')
    details = _load('listing_details.json')
    experiences = _load('experiences.json')
    exp_details = _load('experience_details.json')

    for slug in sorted(dests):
        d = dests[slug]
        row = Destination(
            slug=slug, label=d['label'], city=d['city'], region=d['region'],
            seo_title=d.get('seo_title'), seo_subtitle=d.get('seo_subtitle'),
            filter_panel=json.dumps(d.get('filter_panel') or {}),
            serp_total=(d.get('upstream_total') or {}).get('count') or 0)
        db.session.add(row)

    position = 0
    corpus = {}
    for slug in sorted(dests):
        for i, lid in enumerate(dests[slug].get('listing_ids', [])):
            card = listings.get(lid)
            det = details.get(lid)
            if not card or not det:
                continue
            overview = parse_overview(det.get('overview_items'))
            # Photo fallback chain (review B1): the captured PDP photo-tour
            # payload carries only null placeholder slots for every listing
            # (uri=null x7), so the real gallery comes from the captured
            # ld_images photo-tour URLs (the same images the upstream PDP
            # gallery renders), then the SERP card photos. Every URI is a
            # managed local asset (asset_inventory.json is the mapping
            # authority; the image download step fetched the same
            # URL set, so no listing can end up with a NULL or remote URI).
            photo_uris = [p.get('uri') for p in (det.get('photos') or [])
                          if p.get('uri')]
            if not photo_uris:
                photo_uris = [u for u in (det.get('ld_images') or []) if u]
            if not photo_uris:
                photo_uris = [u for u in (card.get('photos') or []) if u]
            photos = [{'uri': local_image(u) or u,
                       'alt': card.get('name'), 'caption': None}
                      for u in photo_uris]
            quality = det.get('quality') or {}
            rating, rev_count = parse_rating(card.get('rating'))
            if rating is None:
                rating = quality.get('rating_average')
            reviews_count = rev_count or None
            if reviews_count is None:
                reviews_count = int(quality.get('rating_count') or 0)
            price = card.get('price') or {}
            nightly = None
            if price.get('nightly'):
                m = re.match(r'\$([0-9,]+(?:\.[0-9]+)?)', price['nightly'])
                if m:
                    nightly = float(m.group(1).replace(',', ''))
            quote_total = None
            if price.get('total'):
                m = re.match(r'\$([0-9,]+(?:\.[0-9]+)?)', price['total'])
                if m:
                    quote_total = float(m.group(1).replace(',', ''))
            range2 = card.get('price_range2') or {}
            range2_total = None
            if range2.get('total'):
                m = re.match(r'\$([0-9,]+(?:\.[0-9]+)?)', range2['total'])
                if m:
                    range2_total = float(m.group(1).replace(',', ''))
            window = card.get('date_window') or ''
            checkin = checkout = None
            window = window.replace('\u2009', ' ')
            m = re.match(r'([A-Z][a-z]{2}) (\d{1,2})\s*[–—-]\s*([A-Z][a-z]{2}) (\d{1,2})', window)
            m2 = re.match(r'([A-Z][a-z]{2}) (\d{1,2})\s*[–—-]\s*(\d{1,2})$', window)
            from datetime import date
            months = {mn: i + 1 for i, mn in enumerate(
                ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                 'Sep', 'Oct', 'Nov', 'Dec'])}
            try:
                if m:
                    year = 2026
                    m1, d1, m3, d3 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
                    if months[m3] < months[m1]:
                        year_out = year + 1
                    else:
                        year_out = year
                    checkin = date(year, months[m1], d1).isoformat()
                    checkout = date(year_out, months[m3], d3).isoformat()
                elif m2:
                    m1, d1, d3 = m2.group(1), int(m2.group(2)), int(m2.group(3))
                    checkin = date(2026, months[m1], d1).isoformat()
                    checkout = date(2026, months[m1], d3).isoformat()
            except (KeyError, ValueError):
                pass
            host = det.get('host') or {}
            host_items = host.get('items') or []
            host_name = (host.get('title') or '').replace('Hosted by ', '') or None
            amenities = det.get('amenities') or []
            flags = amenity_flag_map(amenities, bool(det.get('pets_allowed')))
            host_avatar = None
            for r in (det.get('reviews') or []):
                if r.get('reviewee_img'):
                    host_avatar = local_image(r['reviewee_img'])
                    break
            row = Listing(
                id=lid,
                destination_slug=slug,
                name=det.get('ld_name') or card.get('name'),
                title=card.get('title'),
                property_type=card.get('property_type'),
                room_category=room_category(card.get('title')),
                city=(card.get('city') if card.get('property_type')
                      else dests[slug]['city']) or det.get('address_locality'),
                lat=card.get('lat'), lng=card.get('lng'),
                rating=float(rating) if rating is not None else None,
                reviews_count=int(reviews_count or 0),
                is_new=bool(card.get('is_new')),
                is_superhost=bool(card.get('is_superhost')),
                is_guest_favorite=bool(quality.get('is_guest_favorite')
                                       or card.get('is_guest_favorite')),
                instant_book=bool(det.get('instant_book')),
                pets_allowed=bool(det.get('pets_allowed')),
                max_guest_capacity=det.get('max_guest_capacity')
                or overview.get('guests'),
                free_cancellation=any(
                    'Free cancellation' in (m or '')
                    for m in (card.get('payment_messages') or [])),
                subtitle=card.get('subtitle'),
                person_capacity=overview.get('guests') or det.get('person_capacity'),
                bedrooms=overview.get('bedrooms'),
                beds=overview.get('beds'),
                baths=overview.get('baths'),
                bed_lines=json.dumps([l for l in (card.get('primary_lines') or [])
                                       if 'bed' in l.lower() or 'bath' in l.lower()
                                       or 'bedroom' in l.lower()]),
                nightly_price=nightly,
                quote_total=quote_total,
                quote_nights=price.get('nights'),
                quote_checkin=checkin,
                quote_checkout=checkout,
                range2_total=range2_total,
                range2_nights=(range2.get('nights')),
                description_html=det.get('description_html')
                or det.get('ld_description'),
                address_locality=det.get('address_locality'),
                amenity_count=det.get('amenity_count')
                or sum(len(g['items']) for g in amenities),
                photos=json.dumps(photos),
                amenities=json.dumps(amenities),
                amenity_flags=json.dumps(flags),
                highlights=json.dumps(det.get('highlights_from_sections') or []),
                house_rules=json.dumps(det.get('house_rules') or {}),
                safety=json.dumps(det.get('safety') or {}),
                sleeping=json.dumps(det.get('sleeping') or []),
                things_to_know=json.dumps(det.get('things_to_know') or []),
                quality=json.dumps(quality),
                similar=json.dumps(det.get('similar') or []),
                explore=json.dumps(det.get('explore') or []),
                calendar=json.dumps({c['date']: c['available']
                                     for c in (det.get('calendar') or [])}),
                host_name=host_name,
                host_superhost='Superhost' in ' '.join(host_items),
                host_years=next((i for i in host_items if 'hosting' in i), None),
                host_avatar=host_avatar,
                serp_position=position,
            )
            position += 1
            corpus[lid] = row
            db.session.add(row)
    db.session.flush()

    # reviews + tags, deterministic order by listing id then review order
    for lid in sorted(corpus):
        det = details.get(lid) or {}
        meta = det.get('reviews_meta') or {}
        for i, r in enumerate(det.get('reviews') or []):
            row = Review(
                listing_id=lid,
                upstream_id=str(r.get('id') or i),
                reviewer=r.get('reviewer'),
                reviewer_location=r.get('reviewer_location'),
                rating=r.get('rating'),
                text=r.get('comments'),
                localized_date=r.get('localized_date'),
                created_at=(r.get('created_at') or '')[:10],
                host_response=r.get('host_response'),
            )
            db.session.add(row)
        for i, t in enumerate(meta.get('tags') or []):
            db.session.add(ReviewTag(listing_id=lid, name=t.get('name'),
                                     count=t.get('count')))

    # experiences
    for eid in sorted(experiences):
        card = experiences[eid]
        det = exp_details.get(eid, {})
        price = card.get('price') or {}
        per_guest = None
        if price.get('price'):
            m = re.match(r'\$([0-9,]+(?:\.[0-9]+)?)', price['price'])
            if m:
                per_guest = float(m.group(1).replace(',', ''))
        offers = det.get('offerings') or []
        offer_rows = []
        for o in offers:
            offer_rows.append({
                'day': o.get('day'),
                'start_time': o.get('start_time'),
                'iso': o.get('iso'),
                'duration': o.get('duration'),
                'remaining': o.get('remaining'),
            })
        # agenda images are managed local assets (download_images.py fetches
        # the same URL set): store the local path, never the raw CDN URL —
        # the mirror must render offline (same class as the review B1 photo
        # fallback).
        agenda = [{**a, 'image': local_image(a.get('image'))}
                  if isinstance(a, dict) else a
                  for a in (det.get('agenda') or [])]
        row = Experience(
            id=eid,
            city_slug=card['city_slug'],
            name=det.get('name') or card.get('name'),
            byline=det.get('byline') or card.get('byline'),
            theme=card.get('theme'),
            rating=card.get('rating'),
            rating_count=int(card.get('rating_count') or 0),
            price_per_guest=per_guest,
            badges=json.dumps([b for b in (card.get('badges') or []) if b]),
            photos=json.dumps([local_image(u) for u in (det.get('photos') or card.get('photos') or [])]),
            description=det.get('description'),
            host_name=det.get('host_name'),
            highlights=json.dumps(det.get('highlights') or []),
            things_to_know=json.dumps(det.get('things_to_know') or []),
            accessibility=json.dumps(det.get('accessibility') or []),
            guest_requirements=json.dumps(det.get('guest_requirements') or {}),
            agenda=json.dumps(agenda),
            whats_you_doing=json.dumps(det.get('whats_you_doing') or []),
            meeting_text=json.dumps(det.get('meeting_text') or []),
            reviews=json.dumps(det.get('reviews') or []),
            offerings=json.dumps(offer_rows),
            location_city=(det.get('location') or {}).get('addressLocality'),
        )
        db.session.add(row)
    db.session.commit()
    seed_benchmark_users(db)


def seed_benchmark_users(db):
    """The four benchmark accounts with their wishlist/booking fixture
    states (frozen constants; every referenced row is a real captured
    listing/experience)."""
    from app import (Booking, Destination, Experience, Listing, Review,
                     ReviewTag, User, Wishlist, WishlistItem)
    if db.session.query(User).filter_by(email='alice.j@test.com').first():
        return
    listings = {l.id: l for l in db.session.query(Listing).all()}
    exps = {e.id: e for e in db.session.query(Experience).all()}

    def by_dest(dest):
        return [l for l in listings.values()
                if l.destination_slug == dest]

    def booking_code(n):
        return 'HMSEED%03d' % n

    users = {}
    for spec in BENCHMARK_USERS:
        u = User(email=spec['email'], name=spec['name'],
                 password_hash=BENCHMARK_HASH, joined=MIRROR_TS)
        users[spec['email']] = u
        db.session.add(u)
    db.session.flush()

    def wish(user, name, is_default, items_lids, items_eids):
        wl = Wishlist(user_id=user.id, name=name, is_default=is_default,
                       created_at=MIRROR_TS)
        db.session.add(wl)
        db.session.flush()
        for lid in items_lids:
            db.session.add(WishlistItem(wishlist_id=wl.id, listing_id=lid,
                                        added_at=MIRROR_TS))
        for eid in items_eids:
            db.session.add(WishlistItem(wishlist_id=wl.id, experience_id=eid,
                                        added_at=MIRROR_TS))
        return wl

    alice = users['alice.j@test.com']
    bob = users['bob.c@test.com']
    carol = users['carol.d@test.com']
    dana = users['dana.k@test.com']

    # Alice: default wishlist with a Tahoe cabin + Scottsdale pool home +
    # one Austin experience; one confirmed Scottsdale stay, one cancelled
    # Austin stay.
    tahoe = [l for l in by_dest('lake-tahoe')]
    scottsdale = [l for l in by_dest('scottsdale')]
    austin = [l for l in by_dest('austin')]
    austin_exps = [e for e in exps.values() if e.city_slug == 'austin']
    wish(alice, 'Saved', True,
         [tahoe[0].id if tahoe else None, scottsdale[0].id if scottsdale else None],
         [austin_exps[0].id if austin_exps else None])
    if scottsdale:
        s0 = scottsdale[0]
        nights = s0.quote_nights or 5
        subtotal = round((s0.nightly_price or 0) * nights, 2)
        db.session.add(Booking(code=booking_code(1), user_id=alice.id,
                               kind='stay', listing_id=s0.id,
                               checkin=s0.quote_checkin,
                               checkout=s0.quote_checkout,
                               adults=2, guests=2, nights=nights,
                               nightly_price=s0.nightly_price,
                               subtotal=subtotal, total=subtotal,
                               status='confirmed', created_at=MIRROR_TS))
    if austin:
        a0 = austin[0]
        nights = a0.range2_nights or 2
        subtotal = round((a0.nightly_price or 0) * nights, 2)
        db.session.add(Booking(code=booking_code(2), user_id=alice.id,
                               kind='stay', listing_id=a0.id,
                               checkin='2026-10-16', checkout='2026-10-18',
                               adults=2, guests=2, nights=nights,
                               nightly_price=a0.nightly_price,
                               subtotal=subtotal, total=subtotal,
                               status='cancelled', created_at=MIRROR_TS))

    # Bob: wishlist of Asheville listings; a booked Austin kayak experience.
    asheville = [l for l in by_dest('asheville')]
    wish(bob, 'Saved', True,
         [l.id for l in asheville[:3]][:3] if asheville else [], [])
    kayaks = [e for e in austin_exps if 'kayak' in (e.name or '').lower()] \
        or austin_exps[:1]
    if kayaks:
        k = kayaks[0]
        total = round((k.price_per_guest or 0) * 2, 2)
        db.session.add(Booking(code=booking_code(3), user_id=bob.id,
                               kind='experience', experience_id=k.id,
                               experience_date='2026-10-09',
                               adults=2, guests=2, subtotal=total, total=total,
                               status='confirmed', created_at=MIRROR_TS))

    # Carol: empty default wishlist; a confirmed 2-night Miami stay.
    wish(carol, 'Saved', True, [], [])
    miami = [l for l in by_dest('miami')]
    if miami:
        m0 = miami[0]
        nights = m0.range2_nights or 2
        subtotal = round((m0.nightly_price or 0) * nights, 2)
        db.session.add(Booking(code=booking_code(4), user_id=carol.id,
                               kind='stay', listing_id=m0.id,
                               checkin='2026-10-16', checkout='2026-10-18',
                               adults=2, guests=2, nights=nights,
                               nightly_price=m0.nightly_price,
                               subtotal=subtotal, total=subtotal,
                               status='confirmed', created_at=MIRROR_TS))

    # Dana: two wishlists ("Winter cabins" with two Tahoe listings,
    # "NYC weekend"), no bookings. The wishlist page shows items in
    # reverse insertion order (most recently saved first, like upstream),
    # so the list is inserted back-to-front: the first Winter cabins
    # entry shown is the South Tahoe Bungalow, which carries a captured
    # quote window (Oct 4-9, $1,154) and is therefore bookable for its
    # captured window (review H2: the previous first entry, "Queen
    # double", has no captured window at all).
    tahoe_order = [tahoe[1].id, tahoe[0].id] if len(tahoe) > 1 else \
        [l.id for l in tahoe]
    wish(dana, 'Winter cabins', False, tahoe_order, [])
    nyc = [l for l in by_dest('new-york')]
    wish(dana, 'NYC weekend', False, [l.id for l in nyc[:2]] if nyc else [], [])

    db.session.commit()
