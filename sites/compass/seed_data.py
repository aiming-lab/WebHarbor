"""Build the offline catalog from contributor snapshots and verified source facts.

External facts are never generated. Unknown values stay absent. Only benchmark
accounts and their saved homes, collections and tours are synthetic.
"""
import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LISTINGS_JSON = os.path.join(BASE_DIR, "listings_clean.json")
SOURCES_JSON = os.path.join(BASE_DIR, "source_data.json")


def _h(*parts):
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest(), 16)


def _slug(value):
    return re.sub(r"[^A-Za-z0-9]+", "-", (value or "").strip().lower()).strip("-") or "x"


def _city_slug(name, state):
    return f"{_slug(name)}-{state.lower()}"


def _gallery_paths(listing_id, count=4):
    root = f"static/images/listings/{listing_id}"
    paths = [f"/{root}/" + ("hero.webp" if i == 0 else f"gallery_{i}.webp") for i in range(count)]
    paths += [f"/static/external_cache/listings/{listing_id}/gallery_{i}.jpg" for i in range(4, 8)]
    return [p for p in paths if os.path.isfile(os.path.join(BASE_DIR, p.lstrip("/")))]


def seed_database():
    from app import Agent, City, Listing, db
    if Listing.query.count():
        return
    with open(LISTINGS_JSON) as file:
        data = json.load(file)
    with open(SOURCES_JSON) as file:
        sources = json.load(file)["listings"]
    agents = {}
    cities = {}
    featured = {"New York", "Los Angeles", "Miami", "San Francisco", "Boston", "Austin", "Aspen", "Denver"}
    for raw in data:
        gallery = _gallery_paths(raw["listing_id"])
        if not gallery or not raw.get("city") or not raw.get("price"):
            continue
        source = sources.get(raw["listing_id"], {})
        market = raw["city"]
        city = source.get("city") or market
        state = source.get("state") or raw["state"]
        city_key = (market, state)
        if city_key not in cities:
            c = City(slug=_city_slug(market, state), name=market, state=state,
                     hero_image=gallery[0], blurb=f"Explore homes in the {market} area.", is_featured=market in featured)
            db.session.add(c)
            cities[city_key] = c
        source_agent = source.get("agent")
        agent = None
        if source_agent:
            key = (source_agent["name"], source_agent.get("email", ""))
            if key not in agents:
                token = hashlib.sha256("|".join(key).encode()).hexdigest()[:8]
                agent = Agent(slug=f"{_slug(key[0])}-{token}", name=key[0], title="Listing agent",
                              email=source_agent.get("email", ""), phone=source_agent.get("telephone", ""),
                              city=city, state=state)
                db.session.add(agent)
                agents[key] = agent
            agent = agents[key]
        address = source.get("address") or raw.get("street") or "Address withheld"
        # Preserve contributor slugs so existing links and review references survive.
        slug = _slug(f"{raw.get('street')}-{market}-{raw.get('state')}-{raw['listing_id'][-8:]}")[:180]
        features = source.get("features", [])
        facts = source.get("property_facts", {})
        regional = source.get("regional_facts", {})
        status_text = source.get("status_text", "")
        status = "for-rent" if raw.get("is_rent") else "for-sale"
        normalized_status = status_text.lower()
        if normalized_status.startswith("sold"):
            status = "sold"
        elif normalized_status in {"rented", "closed", "expired", "canceled", "cancelled", "withdrawn"}:
            status = normalized_status
        badges = raw.get("badges") or []
        listed_at = source.get("listed_at_ms")
        beds = source.get("beds") if source else (raw.get("beds") or None)
        baths_full = source.get("baths_full") if source else (raw.get("baths_full") or None)
        baths_half = source.get("baths_half") if source else raw.get("baths_half")
        baths_total = source.get("baths_total") if source else (raw.get("baths") or None)
        price = source.get("price") if source else raw["price"]
        active = status in {"for-sale", "for-rent"}
        exclusive = ("coming soon" in normalized_status or "private" in normalized_status) if source else "Compass Coming Soon" in badges
        new = source.get("days_on_market") is not None and 0 <= source["days_on_market"] <= 7 if source else "New" in badges
        garage = regional.get("Garage", "").lower()
        listing = Listing(
            listing_id_sha=raw["listing_id"], slug=slug, address=address,
            unit=source.get("unit") or "", market_city=market,
            city=city, state=state, zip=source.get("zip") or raw.get("zip") or "",
            neighborhood=source.get("neighborhood") or raw.get("neighborhood") or "",
            latitude=source.get("latitude", raw.get("latitude")), longitude=source.get("longitude", raw.get("longitude")),
            status=status, is_rental=bool(raw.get("is_rent")), price=price, beds=beds, baths_full=baths_full, baths_half=baths_half, baths_total=baths_total,
            sqft=source.get("sqft") if source else (raw.get("sqft") or None),
            year_built=source.get("year_built"), property_type={"Multi Family": "Multi-Family"}.get(source.get("property_type"), source.get("property_type", "")),
            description=source.get("description", ""), features=json.dumps(features),
            hero_image=gallery[0], gallery_images=json.dumps(gallery),
            mls_number=source.get("mls_number", ""), days_on_compass=source.get("days_on_market"),
            listed_at=datetime.fromtimestamp(listed_at/1000, tz=timezone.utc).replace(tzinfo=None) if listed_at else None,
            is_compass_exclusive=active and exclusive,
            is_new=active and new, is_luxury=bool(price and price >= 5000000),
            is_pending="pending" in status_text.lower() or "contract" in status_text.lower(),
            has_pool=True if "Pool" in features else None,
            has_doorman=True if "Doorman" in features else None,
            has_elevator=True if "Elevator" in features else None,
            has_parking=True if "Parking Included" in features else None,
            has_garage=True if garage == "yes" or "Garage" in features else (False if garage == "no" else None),
            has_waterfront=True if "Waterfront" in features else None,
            pets_allowed=True if "Pet Friendly" in features else None,
            furnished=True if "Fully Furnished" in features else None,
            source_url=raw["detail_url"], source_retrieved_at=source.get("retrieved_at", ""),
            source_html_sha256=source.get("html_sha256", ""), property_facts_json=json.dumps(facts), regional_facts_json=json.dumps(regional),
            agent=agent,
        )
        db.session.add(listing)
    db.session.commit()


BENCHMARK_USERS = [
    {
        "email": "alice.j@test.com", "name": "Alice Johnson",
        "phone": "(415) 555-0144", "city": "San Francisco", "state": "CA",
        "budget_min": 900_000, "budget_max": 1_600_000, "beds_min": 2,
        "property_types": ["Condo", "Co-op"], "move_timeline": "3-6mo",
        "saved_search": {"name": "SF condos 2BR under $1.6M",
                         "criteria": {"city": "San Francisco", "price_max": "1600000",
                                      "beds": "2", "property_type": "Condo"}},
        "collection": {"name": "Alice — SF favorites", "filter_city": "San Francisco"},
        "tour_city": "San Francisco",
    },
    {
        "email": "bob.smith@test.com", "name": "Bob Smith",
        "phone": "(212) 555-0177", "city": "New York", "state": "NY",
        "budget_min": 1_200_000, "budget_max": 3_500_000, "beds_min": 3,
        "property_types": ["Townhouse", "Single Family"], "move_timeline": "0-3mo",
        "saved_search": {"name": "Brooklyn 3BR townhouses",
                         "criteria": {"city": "New York", "price_max": "3500000",
                                      "beds": "3", "property_type": "Townhouse"}},
        "collection": {"name": "Bob — NY shortlist", "filter_city": "New York"},
        "tour_city": "New York",
    },
    {
        "email": "carol.lee@test.com", "name": "Carol Lee",
        "phone": "(305) 555-0188", "city": "Miami", "state": "FL",
        "budget_min": 600_000, "budget_max": 1_400_000, "beds_min": 2,
        "property_types": ["Condo"], "move_timeline": "6-12mo",
        "saved_search": {"name": "Miami waterfront condos",
                         "criteria": {"city": "Miami", "price_max": "1400000",
                                      "beds": "2", "property_type": "Condo"}},
        "collection": {"name": "Carol — Miami picks", "filter_city": "Miami"},
        "tour_city": "Miami",
    },
    {
        "email": "david.kim@test.com", "name": "David Kim",
        "phone": "(737) 555-0166", "city": "Austin", "state": "TX",
        "budget_min": 700_000, "budget_max": 1_800_000, "beds_min": 3,
        "property_types": ["Single Family"], "move_timeline": "3-6mo",
        "saved_search": {"name": "Austin SFH 3BR",
                         "criteria": {"city": "Austin", "price_max": "1800000",
                                      "beds": "3", "property_type": "Single Family"}},
        "collection": {"name": "David — Austin top picks", "filter_city": "Austin"},
        "tour_city": "Austin",
    },
]


def seed_benchmark_users():
    from app import (Collection, Inquiry, Listing, SavedHome, SavedSearch,
                     Tour, User, db)
    # Function-level gate.
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    USER_BASE_TS = datetime(2026, 1, 5, 12, 0, 0)
    users = []
    for idx, u in enumerate(BENCHMARK_USERS):
        user = User(
            email=u["email"], name=u["name"], phone=u["phone"],
            city=u["city"], state=u["state"],
            budget_min=u["budget_min"], budget_max=u["budget_max"],
            beds_min=u["beds_min"],
            preferred_property_types=json.dumps(u["property_types"]),
            move_timeline=u["move_timeline"], has_agent=False,
            receive_alerts=True,
            created_at=USER_BASE_TS + timedelta(hours=idx),
        )
        # Deterministic password hash: bcrypt uses a random salt, so we
        # replace bcrypt with a stable PBKDF2 (Werkzeug) hash for seed users
        # so the seeded DB is byte-identical across reseeds.
        from werkzeug.security import generate_password_hash
        user.password_hash = generate_password_hash(
            "webharbor123",
            method="pbkdf2:sha256:1000",
            salt_length=8,
        )
        # Force a fixed salt so the hash is byte-deterministic.
        import hashlib as _hl
        fixed_salt = _hl.sha1(("salt-" + u["email"]).encode()).hexdigest()[:8]
        derived = _hl.pbkdf2_hmac(
            "sha256", b"webharbor123", fixed_salt.encode(), 1000, dklen=32
        ).hex()
        user.password_hash = f"pbkdf2:sha256:1000${fixed_salt}${derived}"
        db.session.add(user)
        users.append((u, user))
    db.session.commit()

    SAVED_BASE = datetime(2026, 2, 1, 9, 0, 0)
    # Saved homes — 3 per user, deterministically chosen from listings in the
    # user's city. We pick 3 DISTINCT listings (hash-derived indices into the
    # candidate list, with collision-avoidance) so every benchmark user has a
    # uniform shortlist size — tasks reference "alice's 3 saved homes" etc.
    for u_idx, (cfg, user) in enumerate(users):
        candidates = (Listing.query
                      .filter_by(market_city=cfg["tour_city"], status="for-sale")
                      .order_by(Listing.id).all())
        if not candidates:
            continue
        picked_idx = []
        attempt = 0
        while len(picked_idx) < 3 and attempt < 30:
            idx = _h("save", user.email, len(picked_idx), attempt) % len(candidates)
            if idx not in picked_idx:
                picked_idx.append(idx)
            attempt += 1
        for i, idx in enumerate(picked_idx):
            L = candidates[idx]
            existing = SavedHome.query.filter_by(user_id=user.id, listing_id=L.id).first()
            if not existing:
                db.session.add(SavedHome(
                    user_id=user.id, listing_id=L.id, note="",
                    saved_at=SAVED_BASE + timedelta(days=u_idx, hours=i),
                ))
    db.session.commit()

    SEARCH_BASE = datetime(2026, 2, 10, 9, 0, 0)
    # Saved searches
    for u_idx, (cfg, user) in enumerate(users):
        ss = cfg["saved_search"]
        existing = SavedSearch.query.filter_by(user_id=user.id, name=ss["name"]).first()
        if not existing:
            db.session.add(SavedSearch(
                user_id=user.id, name=ss["name"],
                criteria_json=json.dumps(ss["criteria"]), notify=True,
                created_at=SEARCH_BASE + timedelta(hours=u_idx),
            ))
    db.session.commit()

    COL_BASE = datetime(2026, 3, 1, 10, 0, 0)
    # Collections (each user gets one with 3 listings from their city)
    for u_idx, (cfg, user) in enumerate(users):
        c_cfg = cfg["collection"]
        if Collection.query.filter_by(user_id=user.id, name=c_cfg["name"]).first():
            continue
        candidates = (Listing.query
                      .filter_by(market_city=c_cfg["filter_city"], status="for-sale")
                      .order_by(Listing.price).limit(20).all())
        pick = [listing.id for listing in sorted(candidates, key=lambda listing: _h("col", user.email, listing.id))[:3]]
        # Make share token deterministic via hash so reseed produces same bytes
        token = hashlib.sha1(("col" + user.email).encode()).hexdigest()[:12]
        c = Collection(
            user_id=user.id, name=c_cfg["name"],
            description="Curated picks", share_token=token,
            listing_ids_json=json.dumps(pick),
            created_at=COL_BASE + timedelta(hours=u_idx),
        )
        db.session.add(c)
    db.session.commit()

    # Tours — 1-2 per user, deterministic dates
    for cfg, user in users:
        existing = Tour.query.filter_by(user_id=user.id).first()
        if existing:
            continue
        cands = (Listing.query
                 .filter_by(market_city=cfg["tour_city"], status="for-sale")
                 .filter(Listing.agent_id.isnot(None))
                 .order_by(Listing.id).all())
        if not cands:
            continue
        # First tour
        L1 = cands[(_h("t1", user.email)) % len(cands)]
        d1 = date(2026, 6, 1) + timedelta(days=_h("td1", user.email) % 14)
        db.session.add(Tour(
            user_id=user.id, listing_id=L1.id,
            requested_date=d1.isoformat(),
            requested_time="2:00 PM",
            tour_type="in-person",
            contact_phone=user.phone,
            status="requested",
            requested_at=datetime(2026, 5, 1) + timedelta(hours=_h("ta1", user.email) % 96),
        ))
        # Second tour for some
        if _h("t2", user.email) % 2 == 0:
            L2 = cands[(_h("t2lid", user.email)) % len(cands)]
            d2 = date(2026, 6, 15) + timedelta(days=_h("td2", user.email) % 10)
            db.session.add(Tour(
                user_id=user.id, listing_id=L2.id,
                requested_date=d2.isoformat(),
                requested_time="11:00 AM",
                tour_type="video",
                contact_phone=user.phone,
                status="confirmed",
                requested_at=datetime(2026, 5, 3) + timedelta(hours=_h("ta2", user.email) % 96),
            ))
    db.session.commit()
