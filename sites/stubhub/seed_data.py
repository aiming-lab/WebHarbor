"""Build-time / boot-time seeder for the StubHub mirror.

Everything loads from the tracked source_data/ snapshots (captured from the
live site on 2026-09-26; see provenance.json) plus the tracked
static/images/ tree — no untracked scratch directories are consulted, so the
seed is byte-reproducible from a clean checkout / Docker context (the
Dockerfile stanza and .build-generated-seed
both rebuild it with PYTHONHASHSEED=0). Performer imagery is resolved by
probing static/images/performers/<slug>.* (harvest_images.py names every
performer asset by slug, and the tracked tree is the source of truth), and
performer taxonomy nodes are derived from the performer's own events'
`sources` in events.json — the same tracked fallback the event seeder uses.

Listings for the 100 deep-harvested events are the real upstream listing
cards; remaining catalog events get deterministic derived listings built
from the real per-venue section inventories and the real per-genre
price/feature distributions captured in the same snapshots (documented in
provenance.json).

Every seed function is gated at the top (see AGENTS.md: idempotent seeding).
The instance_seed/stubhub.db ships in the HF dataset, so the boot path
normally finds a populated DB and returns immediately.

Event start instants are stored as the upstream UTC epoch (the true kickoff
instant); app.py renders them in the venue's local timezone so the displayed
date always matches the local date encoded in the upstream URL slug.
"""
from __future__ import annotations

import datetime
import glob
import json
import pathlib
import random
import re

BASE_DIR = pathlib.Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data"

# Frozen bcrypt digest for the benchmark password 'TestPass123!' (frozen so
# the seed DB is byte-identical on every rebuild).
BENCHMARK_PASSWORD_DIGEST = (
    "$2b$12$iETVtUU3JS/5lHQcX3S0zeeLPUfAXRZ/u9yoU9V5uzJGG2RnhU42q"
)

MIRROR_NOW = datetime.datetime(2026, 9, 26, 12, 0)

USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display_name": "Alice Johnson"},
    {"username": "bob_c", "email": "bob.c@test.com", "display_name": "Bob Chen"},
    {"username": "carol_d", "email": "carol.d@test.com", "display_name": "Carol Davis"},
    {"username": "david_k", "email": "david.k@test.com", "display_name": "David Kim"},
]

# Benchmark-user account fixtures. Events are referenced by upstream id and
# must exist in the catalog; listings are the real harvested cards (the order
# "occupies" that listing so it no longer shows as available).
USER_FIXTURES = {
    "alice.j@test.com": {
        "orders": [
            {"event": 160572545, "listing_index": 1, "quantity": 2,
             "delivery": "instant", "days_ago": 3, "status": "Confirmed"},
            {"event": 159662072, "listing_index": 0, "quantity": 4,
             "delivery": "mobile", "days_ago": 21, "status": "Delivered"},
        ],
        "favorites": ["metallica", "seattle-kraken", "olivia-rodrigo", "hamilton"],
        "listings": [
            {"event": 161306184, "section": "SECTION 212", "row": "12",
             "seats": "5 - 8", "quantity": 4, "price": 89, "days_ago": 6},
        ],
        "sales": [
            {"event": 161306184, "section": "SECTION 212", "row": "4",
             "quantity": 2, "payout": 118.40, "days_ago": 9},
        ],
        "cards": [
            {"brand": "Visa", "last4": "4242", "holder": "Alice Johnson",
             "exp_month": 8, "exp_year": 2028, "default": True},
            {"brand": "Mastercard", "last4": "8321", "holder": "Alice Johnson",
             "exp_month": 3, "exp_year": 2027, "default": False},
        ],
        "metro": "redmond",
    },
    "bob.c@test.com": {
        "orders": [
            {"event": 161041547, "listing_index": 0, "quantity": 2,
             "delivery": "instant", "days_ago": 12, "status": "Confirmed"},
            {"event": 159988503, "listing_index": 2, "quantity": 2,
             "delivery": "ups", "days_ago": 40, "status": "Delivered"},
            {"event": 161301917, "listing_index": 0, "quantity": 2,
             "delivery": "mobile", "days_ago": 60, "status": "Delivered"},
        ],
        "favorites": ["seattle-sounders-fc", "rush", "billy-strings"],
        "listings": [
            {"event": 159662072, "section": "108", "row": "9",
             "seats": "1 - 2", "quantity": 2, "price": 145, "days_ago": 2},
            {"event": 161041547, "section": "CLUB 107", "row": "C",
             "seats": "3 - 4", "quantity": 2, "price": 320, "days_ago": 10},
        ],
        "sales": [
            {"event": 159662072, "section": "108", "row": "2",
             "quantity": 2, "payout": 212.10, "days_ago": 15},
        ],
        "cards": [
            {"brand": "Visa", "last4": "1881", "holder": "Bob Chen",
             "exp_month": 11, "exp_year": 2027, "default": True},
            {"brand": "Amex", "last4": "1005", "holder": "Bob Chen",
             "exp_month": 6, "exp_year": 2029, "default": False},
        ],
        "metro": "redmond",
    },
    "carol.d@test.com": {
        "orders": [
            {"event": 160913642, "listing_index": 0, "quantity": 2,
             "delivery": "instant", "days_ago": 5, "status": "Confirmed"},
        ],
        "favorites": ["teddy-swims", "the-chicks", "phoebe-bridgers", "doja-cat"],
        "listings": [
            {"event": 161301917, "section": "LOGE 4", "row": "BB",
             "seats": "11 - 12", "quantity": 2, "price": 240, "days_ago": 1},
        ],
        "sales": [],
        "cards": [
            {"brand": "Mastercard", "last4": "5567", "holder": "Carol Davis",
             "exp_month": 1, "exp_year": 2028, "default": True},
        ],
        "metro": "seattle",
    },
    "david.k@test.com": {
        "orders": [
            {"event": 161137440, "listing_index": 1, "quantity": 2,
             "delivery": "mobile", "days_ago": 2, "status": "Confirmed"},
            {"event": 160343502, "listing_index": 0, "quantity": 2,
             "delivery": "instant", "days_ago": 30, "status": "Delivered"},
        ],
        "favorites": ["katseye", "luke-bryan", "gorillaz", "sting", "malcolm-todd"],
        "listings": [
            {"event": 160343502, "section": "FLR 2", "row": "G",
             "seats": "14 - 15", "quantity": 2, "price": 410, "days_ago": 4},
        ],
        "sales": [
            {"event": 160343502, "section": "FLR 2", "row": "D",
             "quantity": 2, "payout": 365.00, "days_ago": 20},
        ],
        "cards": [
            {"brand": "Visa", "last4": "7756", "holder": "David Kim",
             "exp_month": 5, "exp_year": 2028, "default": True},
            {"brand": "Discover", "last4": "4421", "holder": "David Kim",
             "exp_month": 9, "exp_year": 2027, "default": False},
        ],
        "metro": "redmond",
    },
}

METROS = [
    {"name": "Redmond", "slug": "redmond", "lat": 47.671, "lon": -122.125, "default": True},
    {"name": "Seattle", "slug": "seattle", "lat": 47.606, "lon": -122.332},
    {"name": "Tacoma", "slug": "tacoma", "lat": 47.253, "lon": -122.444},
    {"name": "New York", "slug": "new-york", "lat": 40.713, "lon": -74.006},
    {"name": "Los Angeles", "slug": "los-angeles", "lat": 34.052, "lon": -118.244},
    {"name": "Las Vegas", "slug": "las-vegas", "lat": 36.170, "lon": -115.140},
]


def _read(name):
    return json.loads((SOURCE / name).read_text())


# ---------------------------------------------------------------------------
# Reference loaders (module-level, deterministic)
# ---------------------------------------------------------------------------

def _load_all():
    events = _read("events.json")
    performers = _read("performers.json")
    venues = {v["upstream_id"]: v for v in _read("venues.json")}
    taxonomy = _read("categories.json")
    listings = {}
    listing_dir = SOURCE / "listings"
    if listing_dir.exists():
        for f in sorted(listing_dir.glob("*.json")):
            listings[int(f.stem)] = json.loads(f.read_text())
    return events, performers, venues, taxonomy, listings


def _performer_image(slug):
    """Resolve a performer's image from the tracked asset tree.

    harvest_images.py names every performer asset by slug
    (static/images/performers/<slug>.<ext>), so the tracked tree itself is
    the inventory — no upstream-URL matching and no untracked harvest
    scratch data involved. Deterministic: sorted glob, first hit wins.
    """
    directory = BASE_DIR / "static" / "images" / "performers"
    try:
        matches = sorted(directory.glob(glob.escape(slug) + ".*"))
    except OSError:
        return None
    for path in matches:
        if path.is_file():
            return "/static/images/performers/" + path.name
    return None


# Performer taxonomy nodes are derived from the performer's own events'
# `sources` (tracked events.json) — the same data the event seeder's node
# fallback uses. Mirrors the upstream search subtitles: league teams land on
# their league grouping node, teams/acts without a league land on the top
# Sports/Concerts/Theater/Festivals node so the category pages' Top
# Performers rails and the performer pages' similar-artists rails populate.
PERFORMER_NODE_SOURCES = [
    ("grouping_nfl", 121), ("grouping_mlb", 81), ("grouping_nba", 115),
    ("grouping_nhl", 144), ("grouping_mls", 142), ("grouping_college", 198988),
    ("sports", 51), ("sports_fight", 51), ("sports_rodeo", 51),
    ("comedy", 209),
    ("concerts", 1), ("rock", 1), ("metal", 1), ("pop", 1), ("hiphop", 1),
    ("country", 1), ("electronic", 1),
    ("musicals", 2), ("plays", 2), ("family", 2), ("theater", 2),
    ("classical", 2),
    ("festivals", 490277),
]


def _node_for_sources(sources):
    """First tracked source key (in the fixed order above) -> node id, or None."""
    for key, upstream_id in PERFORMER_NODE_SOURCES:
        if key in sources:
            return upstream_id
    return None


# ---------------------------------------------------------------------------
# Seed functions (each gated as a whole)
# ---------------------------------------------------------------------------

def _parse_followers(text):
    """'114K' -> 114000, '26.1K' -> 26100, '1.2M' -> 1200000."""
    if not text:
        return 0
    t = text.strip().upper()
    m = re.match(r"([\d.]+)([KM]?)", t)
    if not m:
        return 0
    val = float(m.group(1))
    mult = {"": 1, "K": 1000, "M": 1000000}[m.group(2)]
    return int(val * mult)


def seed_database():
    from app import (CategoryNode, Event, Listing, Metro, Performer, Venue,
                     db)

    if Event.query.count() > 0:
        return

    events, performers, venues, taxonomy, listings = _load_all()

    # performer slug -> ordered union of its events' tracked `sources`
    sources_by_slug = {}
    for e in events:
        sources_by_slug.setdefault(e["performer_slug"], []).extend(
            s for s in (e.get("sources") or []) if s not in
            sources_by_slug.get(e["performer_slug"], []))

    # metros
    for i, m in enumerate(METROS):
        db.session.add(Metro(id=i + 1, name=m["name"], slug=m["slug"],
                            lat=m["lat"], lon=m["lon"],
                            is_default=bool(m.get("default"))))

    # taxonomy
    def add_node(node, parent_id=None, sort=0):
        row = CategoryNode(upstream_id=node["upstream_id"], name=node["name"],
                          slug=node["slug"], kind=node["kind"],
                          parent_id=parent_id, sort=sort)
        db.session.add(row)
        db.session.flush()
        for i, child in enumerate(node.get("children") or []):
            add_node(child, row.id, i)
        return row

    node_by_upstream = {}
    for i, top in enumerate(taxonomy):
        row = add_node(top, None, i)
        node_by_upstream[top["upstream_id"]] = row
        for child in top.get("children") or []:
            node_by_upstream[child["upstream_id"]] = CategoryNode.query.filter_by(
                upstream_id=child["upstream_id"]).first()

    # venues
    for v in venues.values():
        db.session.add(Venue(upstream_id=v["upstream_id"], name=v["name"],
                            city=v["city"], state=v.get("state"),
                            country=v.get("country") or "USA",
                            seatmap_file=v.get("seatmap"),
                            sections=json.dumps(v.get("sections") or [])))
    db.session.flush()

    # performers
    perf_by_slug = {}
    for p in performers:
        slug = p["slug"]
        image_file = _performer_image(slug)
        node = None
        node_upstream = _node_for_sources(sources_by_slug.get(slug) or [])
        if node_upstream:
            node = CategoryNode.query.filter_by(upstream_id=node_upstream).first()
        row = Performer(upstream_id=p["upstream_id"], name=p["name"],
                        slug=slug, node_id=node.id if node else None,
                        image_file=image_file, hero_file=image_file,
                        bio=p.get("bio"),
                        followers=_parse_followers(p.get("followers_text")),
                        hourly_views=0, is_team=(p.get("kind") == "grouping"))
        db.session.add(row)
        perf_by_slug[slug] = row
    db.session.flush()

    # events — the node comes from the event's own tracked `sources` (the
    # authoritative per-event genre data, byte-identical to the canonical
    # build's assignment), never inherited from the performer's node.
    for e in events:
        perf = perf_by_slug.get(e["performer_slug"])
        node = None
        for src in e["sources"]:
            if src.startswith("grouping_"):
                key = src.replace("grouping_", "")
            elif src.startswith("sports_"):
                key = src.replace("sports_", "")
            else:
                key = src
            mapping = {"concerts": 1, "pop": 1502178, "rock": 209736,
                       "hiphop": 195739, "country": 1501250,
                       "metal": 1502004, "electronic": 195489,
                       "comedy": 209, "musicals": 700188,
                       "plays": 700189, "family": 5242,
                       "classical": 178, "festivals": 490277,
                       "sports": 51, "theater": 2, "dance": 176,
                       "nfl": 121, "mlb": 81, "nba": 115, "nhl": 144,
                       "mls": 142, "wwe": 131, "college": 198988,
                       "tennis": 7667, "golf": 111, "fight": 7368,
                       "rodeo": 6979}
            if key in mapping:
                node = CategoryNode.query.filter_by(
                    upstream_id=mapping[key]).first()
                break
        start = (datetime.datetime.utcfromtimestamp(e["start_epoch"])
                 if e.get("start_epoch") else MIRROR_NOW)
        db.session.add(Event(
            upstream_id=e["upstream_id"], name=e["name"],
            slug=e["url"].replace("https://www.stubhub.com/", "").split("/event/")[0],
            performer_id=perf.id if perf else None,
            venue_id=Venue.query.filter_by(upstream_id=e["venue_id"]).first().id,
            node_id=node.id if node else None,
            starts_at=start, is_time_tbd=bool(e.get("is_tbd")),
            holiday_badge=e.get("holiday_badge"),
            is_parking=bool(e.get("is_parking")),
            listing_count=0, min_price=None, max_price=None,
            availability_note=e.get("availability"),
        ))
    db.session.flush()

    # listings: real sets for deep events, derived for the rest
    _seed_real_listings(listings)
    _derive_missing_listings()

    _refresh_event_stats()

    # home curation: followers/hourly views drive Popular / Recommended rows
    curation = _read("home_curation.json")
    for i, entry in enumerate(curation["popular"]):
        perf = Performer.query.filter_by(slug=entry["slug"]).first()
        if perf:
            perf.followers = max(perf.followers, 38000 + (12 - i) * 3100)
            perf.hourly_views = max(perf.hourly_views, 900 - i * 40)
    for i, entry in enumerate(curation["recommended"]):
        perf = Performer.query.filter_by(slug=entry["slug"]).first()
        if perf and not perf.hourly_views:
            perf.hourly_views = 640 - i * 12

    db.session.commit()


def _resolve_image(url):
    """Map an upstream image URL to the static/images path via the inventory."""
    if not url:
        return None
    try:
        with open(BASE_DIR / "asset_inventory.json", encoding="utf-8") as fh:
            for asset in json.load(fh).get("assets", []):
                if asset.get("source_url") == url:
                    return "/" + asset["path"]
    except (OSError, ValueError):
        pass
    return None


def _seed_real_listings(listings):
    from app import Event, Listing, db
    for eid, rows in listings.items():
        evt = Event.query.filter_by(upstream_id=eid).first()
        if not evt:
            continue
        for r in rows:
            db.session.add(Listing(
                upstream_id=r["upstream_id"], event_id=evt.id,
                section=r["section"] or "GA",
                zone=_zone_for(r["section"]),
                row=r["row"], seats=r["seats"], quantity=r["quantity"],
                price=r["price"], original_price=r.get("original_price"),
                features=json.dumps(r["features"]),
                badges=json.dumps([b for b in r["badges"] if b.lower() != "sponsored"]),
                deal_rating=r.get("deal_rating"),
                seat_view_file=_resolve_image(r.get("seat_view_url")),
                is_sponsored=bool(r.get("sponsored")),
                created_at=MIRROR_NOW - datetime.timedelta(days=30),
            ))
    db.session.flush()


def _zone_for(section):
    s = (section or "").strip().upper()
    import re as _re
    m = _re.match(r"^(\d)\d{2}", s)
    if m:
        return f"{m.group(1)}00 Level"
    if s.startswith("SUITE"):
        return "Suites"
    if s in ("FLOOR", "PIT", "SNAKE", "MIX", "FLR") or s.startswith("FLR"):
        return "Floor"
    if s.startswith("CLUB"):
        return "Club"
    if s.startswith("LOGE") or s.startswith("BOX"):
        return "Boxes"
    if s.startswith("BALC"):
        return "Balcony"
    if s.startswith("MAIN") or s.startswith("ORCH"):
        return "Main Floor"
    if s.startswith("MEZZ") or s.startswith("CMEZZ"):
        return "Mezzanine"
    return "Other"


def _derive_missing_listings():
    """Deterministic listings for catalog events without a real harvested set.

    Built from the same snapshots: sections come from the venue's real seat
    map labels (or the closest captured venue of the same kind), prices from
    the real per-genre price distributions, and features/badges/ratings from
    the real listing-card distributions. Seeded by event id => reproducible.
    """
    from app import Event, Listing, Venue, db

    # real distributions from the harvested listing cards
    real = []
    for f in sorted((SOURCE / "listings").glob("*.json")):
        real.extend(json.loads(f.read_text()))
    qty_pool = [r["quantity"] for r in real]
    feat_pool = [r["features"] for r in real]
    badge_pool = [b for r in real for b in r["badges"] if b.lower() != "sponsored"]
    rating_pool = [r["deal_rating"] for r in real if r.get("deal_rating")]

    # per-genre price stats from real listings of that genre's events
    genre_prices = {}
    for f in sorted((SOURCE / "listings").glob("*.json")):
        eid = int(f.stem)
        rows = json.loads(f.read_text())
        evt = next((e for e in _read("events.json") if e["upstream_id"] == eid), None)
        if not evt or not rows:
            continue
        for g in evt["sources"]:
            prices = [r["price"] for r in rows if r["price"]]
            if prices:
                genre_prices.setdefault(g, []).extend(prices)
    genre_stats = {g: (min(v), max(v)) for g, v in genre_prices.items()}

    events = _read("events.json")
    covered = {int(f.stem) for f in (SOURCE / "listings").glob("*.json")}
    venue_sections = {}
    for v in _read("venues.json"):
        if v.get("sections"):
            venue_sections[v["upstream_id"]] = v["sections"]

    for e in events:
        if e["upstream_id"] in covered or e.get("no_listings"):
            continue
        evt = Event.query.filter_by(upstream_id=e["upstream_id"]).first()
        if not evt:
            continue
        rng = random.Random(900000 + e["upstream_id"])
        # sections: the venue's own map, else a similar captured venue
        sections = venue_sections.get(e["venue_id"])
        if not sections:
            similar = [vid for vid, s in venue_sections.items()
                       if len(s) >= 8]
            sections = venue_sections[similar[e["venue_id"] % len(similar)]] \
                if similar else ["101", "102", "103", "201", "202", "203"]
        n = min(len(sections), rng.randint(12, 26))
        chosen = rng.sample(sections, n)
        lo, hi = (genre_stats.get(e["sources"][0]) if e["sources"] else None) \
            or (genre_stats.get("concerts") or (40, 400))
        for section in chosen:
            price = int(rng.randint(int(lo), min(hi, int(lo * 40) + 60)))
            qty = rng.choice(qty_pool) if qty_pool else 2
            feats = list(rng.choice(feat_pool)) if feat_pool else ["Clear view"]
            badges = []
            if rng.random() < 0.22:
                badges.append(rng.choice(badge_pool) if badge_pool else "Last tickets")
            rating = rng.choice(rating_pool) if rating_pool else None
            db.session.add(Listing(
                upstream_id=None, event_id=evt.id, section=section,
                zone=_zone_for(section),
                row=str(rng.randint(1, 28)),
                seats=f"{rng.randint(1, 18)} - {rng.randint(19, 26)}"
                if rng.random() < 0.5 else None,
                quantity=qty, price=price,
                original_price=int(price * 1.18) if rng.random() < 0.14 else None,
                features=json.dumps(feats), badges=json.dumps(badges),
                deal_rating=rating, is_sponsored=False,
                created_at=MIRROR_NOW - datetime.timedelta(days=rng.randint(1, 40)),
            ))
    db.session.flush()


def _refresh_event_stats():
    from app import Event, Listing, db
    for evt in Event.query.all():
        _refresh_stats_for(evt)
    db.session.flush()


def _refresh_stats_for(evt):
    """Recompute one event's listing_count / min_price / max_price from the
    rows actually unsold right now (so fixture orders that occupy a listing
    and fixture seller listings are both reflected — the event page and the
    performer/category cards must agree on the get-in price)."""
    from app import Listing
    rows = [l for l in Listing.query.filter_by(event_id=evt.id).all()
            if not l.is_sold]
    evt.listing_count = len(rows)
    if rows:
        evt.min_price = min(l.price for l in rows)
        evt.max_price = max(l.price for l in rows)
    else:
        evt.min_price = None
        evt.max_price = None


def seed_benchmark_users():
    from app import (Favorite, GiftCardOrder, Listing, Notification, Order,
                     PaymentCard, Sale, User, db)

    if User.query.filter_by(email="alice.j@test.com").first():
        return

    from app import bcrypt  # noqa: F401  (used via generate below)

    for data in USERS:
        db.session.add(User(username=data["username"], email=data["email"],
                            display_name=data["display_name"],
                            password_hash=BENCHMARK_PASSWORD_DIGEST))
    db.session.flush()

    from app import Metro, Performer, Event
    metro_by_slug = {m.slug: m for m in Metro.query.all()}
    touched_events = set()

    for email, fixture in USER_FIXTURES.items():
        user = User.query.filter_by(email=email).first()
        user.metro_id = metro_by_slug[fixture.get("metro", "redmond")].id

        # cards
        for c in fixture["cards"]:
            db.session.add(PaymentCard(user_id=user.id, brand=c["brand"],
                                       last4=c["last4"], holder=c["holder"],
                                       exp_month=c["exp_month"],
                                       exp_year=c["exp_year"],
                                       is_default=bool(c.get("default"))))
        db.session.flush()
        default_card = PaymentCard.query.filter_by(user_id=user.id, is_default=True).first()

        # orders occupy real listings
        for i, o in enumerate(fixture["orders"]):
            evt = Event.query.filter_by(upstream_id=o["event"]).first()
            if not evt:
                continue
            touched_events.add(evt.id)
            avail = [l for l in Listing.query.filter_by(event_id=evt.id).all()
                     if not l.is_sold]
            listing = avail[o["listing_index"]] if len(avail) > o["listing_index"] else None
            qty = o["quantity"] if listing is None else min(o["quantity"], listing.quantity)
            unit = listing.price if listing else (evt.min_price or 100)
            delivery_fee = {"instant": 0.0, "mobile": 0.0, "ups": 14.95}[o["delivery"]]
            processing = 2.95
            total = unit * qty + delivery_fee + processing
            placed = MIRROR_NOW - datetime.timedelta(days=o["days_ago"])
            order_no = str(41800000 + user.id * 10000 + i * 137 + 907)
            db.session.add(Order(order_number=order_no, user_id=user.id,
                                event_id=evt.id,
                                listing_id=listing.id if listing else None,
                                quantity=qty, unit_price=unit,
                                delivery_method=o["delivery"],
                                delivery_fee=delivery_fee,
                                processing_fee=processing,
                                total=round(total, 2), status=o["status"],
                                placed_at=placed,
                                card_last4=f"{default_card.brand} ••••{default_card.last4}"))
            if listing:
                listing.is_sold = True
            db.session.add(Notification(
                user_id=user.id,
                body=f"Order {order_no} confirmed: {evt.name} "
                     f"on {evt.local_starts_at.strftime('%b %-d')}.",
                created_at=placed))

        # seller listings
        for l in fixture["listings"]:
            evt = Event.query.filter_by(upstream_id=l["event"]).first()
            if not evt:
                continue
            touched_events.add(evt.id)
            db.session.add(Listing(
                upstream_id=None, event_id=evt.id, section=l["section"],
                zone=_zone_for(l["section"]), row=l["row"], seats=l.get("seats"),
                quantity=l["quantity"], price=l["price"],
                features=json.dumps(["2 tickets together", "Clear view"]
                                    if l["quantity"] > 1 else ["Clear view"]),
                badges="[]", seller_id=user.id,
                created_at=MIRROR_NOW - datetime.timedelta(days=l["days_ago"])))

        # sales
        for s in fixture["sales"]:
            evt = Event.query.filter_by(upstream_id=s["event"]).first()
            if not evt:
                continue
            touched_events.add(evt.id)
            db.session.add(Sale(user_id=user.id, event_id=evt.id,
                                section=s["section"], row=s["row"],
                                quantity=s["quantity"], payout=s["payout"],
                                status="Paid",
                                sold_at=MIRROR_NOW - datetime.timedelta(days=s["days_ago"]),
                                order_number=str(41800000 + user.id * 10000 + 517)))

        # favorites
        for slug in fixture["favorites"]:
            perf = Performer.query.filter_by(slug=slug).first()
            if perf:
                db.session.add(Favorite(user_id=user.id, performer_id=perf.id,
                                        created_at=MIRROR_NOW - datetime.timedelta(days=17)))

        # one gift card on file
        db.session.add(GiftCardOrder(user_id=user.id, amount=100,
                                     recipient_name="Gift for you",
                                     recipient_email=email,
                                     design="classic", code="SHGC" + str(user.id * 7331),
                                     created_at=MIRROR_NOW - datetime.timedelta(days=64)))

    # Fixture orders occupy listings and fixture listings add rows, so the
    # pre-fixture stats are stale for every touched event: recompute from
    # the live rows (keeps "From $X" cards equal to the event page get-in).
    db.session.flush()
    for eid in sorted(touched_events):
        _refresh_stats_for(Event.query.get(eid))

    db.session.commit()


if __name__ == "__main__":
    import os
    import shutil
    import sys
    # The Dockerfile seed gate wipes instance/ and instance_seed/ before
    # rerunning this script, so the instance directory must be (re)created
    # here before the app engine opens instance/stubhub.db (same contract as
    # the mta / nfl build-generated seeds).
    os.makedirs(BASE_DIR / "instance", exist_ok=True)
    sys.path.insert(0, str(BASE_DIR))
    from app import app, db as app_db
    with app.app_context():
        app_db.create_all()
        seed_database()
        seed_benchmark_users()
    seed_dir = BASE_DIR / "instance_seed"
    seed_dir.mkdir(exist_ok=True)
    shutil.copyfile(BASE_DIR / "instance" / "stubhub.db",
                    seed_dir / "stubhub.db")
    print("seed complete; copied instance/stubhub.db to instance_seed/stubhub.db")
