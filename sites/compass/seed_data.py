"""Seed data builder for the compass mirror.

Reads listings_clean.json (committed alongside the rest of the
mirror) and constructs Listing, Agent, City rows. Adds benchmark users with
saved homes, tours, inquiries, saved searches, and collections so tasks can
reference any of them.

Idempotent: every seed_*() function early-returns if its rows are already
populated.
"""
import hashlib
import json
import os
import random
import re
from datetime import date, datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LISTINGS_JSON = os.path.join(BASE_DIR, "listings_clean.json")


# ─── Deterministic helpers ────────────────────────────────────────────────────


def _h(*parts) -> int:
    """Stable integer hash so seeding produces the same output each boot."""
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest(), 16)


def _pick(seq, *parts):
    return seq[_h(*parts) % len(seq)] if seq else None


def _slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", (s or "").strip().lower()).strip("-")
    return s or "x"


# ─── Vocabulary ───────────────────────────────────────────────────────────────


CITY_BLURBS = {
    "New York":      "Iconic skyline, walkable neighborhoods, and the country's deepest co-op and condo market.",
    "Los Angeles":   "Architectural homes from Hollywood Hills to the Pacific, with year-round outdoor living.",
    "Miami":         "Waterfront condos, palm-lined streets, and an international design scene.",
    "San Francisco": "Victorian charm meets Pacific views across the city's distinctive hills and neighborhoods.",
    "Chicago":       "Lake Michigan views, historic brick lofts, and the country's most distinctive architecture.",
    "Boston":        "Brownstones, river views, and walkable historic neighborhoods with elite universities.",
    "Austin":        "Hill country sunsets, lakefront retreats, and a thriving tech-fueled market.",
    "Seattle":       "Floating homes, midcentury treasures, and water-and-mountain views in equal measure.",
    "Denver":        "Mile-high mountain access, modernist new builds, and walkable urban core.",
    "Aspen":         "Mountain estates, ski-in residences, and trophy properties in one of the most exclusive markets in America.",
    "Washington":    "Federal-style row houses, leafy embassy quarters, and a tightly-held historic market.",
}

CITY_HERO_DEFAULT = "/static/images/hero-compass.svg"

PROPERTY_TYPES = ["Single Family", "Condo", "Co-op", "Townhouse",
                  "Multi-Family", "Land", "Apartment"]

FEATURE_POOL = {
    "Single Family": ["Hardwood floors", "Renovated kitchen", "Primary suite",
                      "Finished basement", "Two-car garage", "Backyard",
                      "Central air", "Mudroom", "Bonus room", "Vaulted ceilings"],
    "Condo":         ["Floor-to-ceiling windows", "Open kitchen",
                      "In-unit laundry", "Building gym", "Concierge",
                      "Roof deck", "Pet friendly", "Storage unit",
                      "Walk-in closet", "Smart thermostat"],
    "Co-op":         ["Pre-war detail", "Doorman building", "Sun-filled rooms",
                      "Storage", "Bike room", "Roof access",
                      "Restored moldings", "Eat-in kitchen"],
    "Townhouse":     ["Stoop entrance", "Garden", "Original details",
                      "Updated systems", "Private outdoor space",
                      "Garage parking", "South-facing rear"],
    "Multi-Family":  ["Separate utilities", "Owner's unit",
                      "Tenant-paying-rent", "Off-street parking",
                      "Updated roof", "Vinyl siding"],
    "Land":          ["Buildable lot", "Mountain views", "Utility access",
                      "Water rights", "Conservation easement",
                      "Wooded acreage"],
    "Apartment":     ["Hardwood floors", "Renovated kitchen",
                      "Stainless appliances", "Closet space",
                      "Pet friendly", "On-site laundry", "Roof access"],
}

DESCRIPTIONS = [
    "Sun-soaked rooms, generous ceiling heights, and a layout designed for both quiet mornings and effortless entertaining.",
    "A turnkey home in a landmark setting — every system updated, every finish considered, with a private outdoor escape rare for the neighborhood.",
    "Light pours through oversized windows in this thoughtfully renovated home, where classic details meet a modern open-plan layout.",
    "Tucked on a quiet block, this residence pairs a chef's kitchen with a primary suite that feels like a true retreat.",
    "Polished concrete floors and gallery walls give this property a serene, gallery-like quality. Owner-occupied; meticulously maintained.",
    "Behind a brick facade, oak floors and a south-facing garden create one of the most-loved homes on the block.",
    "Open kitchen with island, walk-in pantry, and a primary suite with double walk-in closets and a spa-style bath.",
    "Soaring ceilings, recently updated mechanicals, and a back-of-house layout that the current owners use as a media room.",
    "Quiet, sun-filled, and steps to transit. Renovated systems, refinished hardwoods, and pristine condition throughout.",
    "Architect-renovated with custom millwork, a vented chef's kitchen, and a primary suite that overlooks the rear garden.",
]

AGENT_FIRST = [
    "Olivia", "Marcus", "Priya", "Diego", "Hana", "Theo", "Sofia",
    "Jamal", "Anya", "Caleb", "Mei", "Naomi", "Felix", "Greta",
    "Yusuf", "Riley", "Camila", "Joon", "Sasha", "Quincy",
    "Lena", "Omar", "Ines", "Ravi", "Cleo", "Dante", "Tomas",
    "Aiko", "Talia", "Sven", "Magnus", "Halima", "Kiran", "Beatriz",
    "Liev", "Soraya", "Ezra", "Mara", "Niko", "Renata",
]
AGENT_LAST = [
    "Thornton", "Velasquez", "Park", "Greenfield", "Ashbury", "Whitmore",
    "Caldwell", "Okafor", "Nakamura", "Esposito", "Trevino", "Hadid",
    "Bjornson", "Chevalier", "Harrington", "Yoon", "Pellegrini", "Marchetti",
    "Sutherland", "Devereaux", "Mendelsohn", "Saint-Clair", "Rosado",
    "Holloway", "Vanderkamp", "Eliasson", "Khouri", "Ostrowski",
    "Lindquist", "Pemberton", "Galindo", "Vasquez-Lim", "Brennan",
]

# Compass specialty language — keep generic to avoid leak-via-tag
AGENT_SPECIALTIES = [
    ["Luxury Listings", "Waterfront"],
    ["Condos & Co-ops", "First-Time Buyers"],
    ["Investment Properties", "Multi-Family"],
    ["New Development", "Compass Concierge"],
    ["Townhouses", "Historic Properties"],
    ["Relocation", "Corporate Buyers"],
    ["Ski-in / Ski-out", "Mountain Estates"],
    ["International Buyers", "Off-Market Listings"],
]

LANGUAGE_OPTIONS = [
    ["English"], ["English", "Spanish"], ["English", "Mandarin"],
    ["English", "French"], ["English", "Portuguese"],
    ["English", "Korean"], ["English", "Italian"], ["English", "Russian"],
]


# ─── Seed: cities ──────────────────────────────────────────────────────────────


def _city_slug(name: str, state: str) -> str:
    return f"{_slug(name)}-{state.lower()}"


def seed_cities():
    from app import City, db
    if City.query.count() > 0:
        return
    data = json.load(open(LISTINGS_JSON))
    seen = {}
    for L in data:
        key = (L["city"], L["state"])
        seen.setdefault(key, []).append(L)
    featured = {"New York", "Los Angeles", "Miami", "San Francisco",
                "Boston", "Austin", "Aspen", "Denver"}
    for (city, state), Ls in sorted(seen.items()):
        # Pick a hero photo from one of the listings in this city.
        hero = ""
        for L in Ls:
            uuid = (L.get("hero_uuid") or "").split("/")[-1]
            lid = L.get("listing_id")
            cand = f"/static/images/listings/{lid}/hero.webp"
            full = os.path.join(BASE_DIR, cand.lstrip("/"))
            if os.path.exists(full):
                hero = cand
                break
        c = City(
            slug=_city_slug(city, state),
            name=city, state=state,
            hero_image=hero or CITY_HERO_DEFAULT,
            blurb=CITY_BLURBS.get(city, f"Find homes for sale in {city}, {state}."),
            is_featured=(city in featured),
        )
        db.session.add(c)
    db.session.commit()


# ─── Seed: agents ──────────────────────────────────────────────────────────────


def _build_agent(i: int, city: str, state: str):
    from app import Agent
    first = AGENT_FIRST[_h("af", i) % len(AGENT_FIRST)]
    last = AGENT_LAST[_h("al", i) % len(AGENT_LAST)]
    name = f"{first} {last}"
    slug = f"{_slug(name)}-{i:03d}"
    specialties = AGENT_SPECIALTIES[_h("as", i) % len(AGENT_SPECIALTIES)]
    languages = LANGUAGE_OPTIONS[_h("ag", i) % len(LANGUAGE_OPTIONS)]
    years = 3 + (_h("ay", i) % 28)
    transactions = 20 + (_h("at", i) % 380)
    avg_price = 800_000 + (_h("av", i) % 7_500_000)
    volume = transactions * avg_price
    is_top = volume > 200_000_000
    return Agent(
        slug=slug, name=name,
        title="Real Estate Agent" if not is_top else "Senior Real Estate Agent",
        photo="",  # no agent headshots in the asset pack — keep blank, render initials
        bio=(f"{first} has spent {years} years guiding buyers and sellers across the "
             f"{city} market, with a focus on {specialties[0].lower()} and a reputation "
             f"for steady negotiation and discreet service."),
        email=f"{_slug(name)}@compass.com",
        phone=f"({200 + (i % 700):03d}) {100 + (i % 900):03d}-{1000 + (i % 9000):04d}",
        license_number=f"RE{state}{1_000_000 + i}",
        city=city, state=state,
        years_experience=years,
        sales_volume_usd=int(volume),
        transactions_count=transactions,
        languages=json.dumps(languages),
        specialties=json.dumps(specialties),
        is_top_agent=is_top,
    )


def seed_agents():
    from app import Agent, db
    if Agent.query.count() > 0:
        return
    data = json.load(open(LISTINGS_JSON))
    city_pairs = sorted({(L["city"], L["state"]) for L in data
                         if L.get("city") and L.get("state")})
    # 3 agents per city -> ~33 agents across 11 cities.
    agents = []
    for ci, (city, state) in enumerate(city_pairs):
        for j in range(3):
            i = ci * 3 + j
            agents.append(_build_agent(i, city, state))
    for a in agents:
        db.session.add(a)
    db.session.commit()


# ─── Seed: listings ───────────────────────────────────────────────────────────


def _derive_property_type(L) -> str:
    """Use deterministic heuristics: zip-shape + city + status to map a type."""
    city = L.get("city")
    if L.get("is_rent"):
        return "Apartment"
    # Co-ops are NY-only in this seed. Townhouses are common in DC/Boston/Brooklyn.
    if city == "New York" and _h("pt", L["listing_id"]) % 5 == 0:
        return "Co-op"
    if city in {"Boston", "Washington"} and _h("pt", L["listing_id"]) % 4 == 0:
        return "Townhouse"
    if L.get("beds") and L["beds"] >= 4 and _h("pt", L["listing_id"]) % 3 == 0:
        return "Single Family"
    if (L.get("beds") or 0) <= 3:
        return "Condo"
    return "Single Family"


def _derive_year_built(L) -> int:
    h = _h("yr", L["listing_id"])
    city = L.get("city")
    if city in {"Boston", "New York", "Washington"}:
        return 1880 + (h % 145)
    if city == "Aspen":
        return 1985 + (h % 40)
    if city in {"Miami", "Austin"}:
        return 1960 + (h % 65)
    return 1925 + (h % 100)


def _derive_lot_sqft(L, property_type) -> int:
    h = _h("lot", L["listing_id"])
    if property_type in {"Condo", "Co-op", "Apartment"}:
        return 0
    if property_type == "Townhouse":
        return 1200 + (h % 2200)
    if property_type == "Land":
        return 40_000 + (h % 500_000)
    if property_type == "Multi-Family":
        return 2400 + (h % 4800)
    return 3000 + (h % 18000)


def _derive_open_house(L):
    h = _h("oh", L["listing_id"])
    if h % 4 != 0:
        return False, "", ""
    # next-Saturday relative to a fixed reference (deterministic per listing)
    # but we want stable dates that don't change across reseeds — pick fixed offsets
    base = date(2026, 5, 16)  # reference Saturday
    offset_weeks = (h // 4) % 6
    d = base + timedelta(days=offset_weeks * 7)
    time_slots = ["11am-1pm", "1pm-3pm", "2pm-4pm", "3pm-5pm"]
    return True, d.isoformat(), time_slots[h % 4]


def _features_for(property_type, L) -> list:
    pool = FEATURE_POOL.get(property_type, FEATURE_POOL["Single Family"])
    h = _h("f", L["listing_id"])
    n = 4 + (h % 4)
    return [pool[(h + i) % len(pool)] for i in range(n)]


def _gallery_paths(listing_id: str, count: int) -> list:
    """Return list of /static/images/listings/<id>/{hero,gallery_N}.webp that exist."""
    site = BASE_DIR
    rel_root = os.path.join("static", "images", "listings", listing_id)
    abs_root = os.path.join(site, rel_root)
    out = []
    for i in range(count):
        fn = "hero.webp" if i == 0 else f"gallery_{i}.webp"
        if os.path.exists(os.path.join(abs_root, fn)):
            out.append(f"/{rel_root}/{fn}")
    return out


def _round_price(p):
    if not p:
        return 0
    if p >= 1_000_000:
        # round to nearest $5k
        return int(round(p / 5000) * 5000)
    return int(round(p / 1000) * 1000)


def _backfill_coop_thin_data(listing_id, beds, baths_full, sqft):
    """Compass's listing feed omits beds/baths/sqft for many Co-op listings,
    leaving the filter pool too thin to make tasks like "find a 2BR Co-op
    under X" meaningfully challenging. For Co-ops only, deterministically
    backfill any zero field with a plausible value so the pool is usable.
    Only applied to Co-ops — other property types keep the scrape's own
    values so tasks tuned to existing distributions don't shift."""
    if not beds:
        beds = 2 + (_h("co_beds", listing_id) % 4)  # 2-5
    if not baths_full:
        # Scale with beds so we don't get a 4BR 1-bath: ceil(beds/2) plus a
        # small variation. Yields 2BR→1-2, 3BR→2-3, 4BR→2-3, 5BR→3-4.
        baths_full = max(1, (beds + 1) // 2 + (_h("co_baths", listing_id) % 2))
    if not sqft:
        # 700-1500 sqft per bedroom, deterministic
        sqft = beds * (700 + (_h("co_sqft", listing_id) % 800))
    return beds, baths_full, sqft


def seed_database():
    from app import Agent, Listing, db
    # Function-level gate.
    if Listing.query.count() > 0:
        return

    seed_cities()
    seed_agents()

    data = json.load(open(LISTINGS_JSON))

    # Distribute agents round-robin by city
    agents = Agent.query.all()
    agents_by_city = {}
    for a in agents:
        agents_by_city.setdefault(a.city, []).append(a)

    # MLS counter
    mls_seed = 100000
    listing_count = 0

    for idx, L in enumerate(data):
        if not L.get("city") or not L.get("price"):
            continue

        gallery = _gallery_paths(L["listing_id"], 4)
        if not gallery:
            continue
        hero = gallery[0]

        property_type = _derive_property_type(L)
        year_built = _derive_year_built(L)
        lot_sqft = _derive_lot_sqft(L, property_type)
        feats = _features_for(property_type, L)
        is_open, oh_date, oh_time = _derive_open_house(L)

        # Boolean features derived deterministically
        h = _h("bool", L["listing_id"])
        is_compass_exclusive = (h % 11) == 0
        is_new = (h % 7) == 0
        is_pending = (h % 23) == 0
        is_luxury = (L.get("price") or 0) >= 5_000_000

        has_parking = property_type != "Apartment" and (h >> 2) % 3 != 0
        has_pool = (h >> 3) % 9 == 0
        has_doorman = property_type in {"Condo", "Co-op", "Apartment"} and (h >> 4) % 4 == 0
        has_elevator = property_type in {"Condo", "Co-op", "Apartment", "Townhouse"} and (h >> 5) % 3 != 0
        has_garage = property_type in {"Single Family", "Townhouse"} and (h >> 6) % 2 == 0
        has_waterfront = (h >> 7) % 17 == 0
        pets_allowed = (h >> 8) % 5 != 0
        furnished = L.get("is_rent") and (h >> 9) % 4 == 0

        # Description: pick one from the pool by hash, no city/price leaks
        desc = DESCRIPTIONS[h % len(DESCRIPTIONS)]

        # Compose slug & address
        street = L.get("street") or "Address withheld"
        unit_match = re.search(r"(?:unit|apt|#)\s*([A-Z0-9\-]+)", street, re.I)
        unit = unit_match.group(1) if unit_match else ""
        slug_base = _slug(f"{street}-{L.get('city')}-{L.get('state')}-{L.get('listing_id')[-8:]}")
        slug = slug_base[:180]

        # Avoid slug collisions
        existing = Listing.query.filter_by(slug=slug).first()
        if existing:
            slug = f"{slug}-{idx}"

        # Pick an agent in this city; fall back to any agent
        agent_pool = agents_by_city.get(L["city"]) or agents
        agent = agent_pool[_h("ag", L["listing_id"]) % len(agent_pool)]

        days = 1 + (_h("d", L["listing_id"]) % 240)
        mls = f"MLS{mls_seed + idx:06d}"
        # Round price to realistic step
        price = _round_price(L.get("price"))

        beds_val = L.get("beds") or 0
        baths_full_val = L.get("baths_full") or int(L.get("baths") or 0)
        sqft_val = L.get("sqft") or 0
        if property_type == "Co-op":
            beds_val, baths_full_val, sqft_val = _backfill_coop_thin_data(
                L["listing_id"], beds_val, baths_full_val, sqft_val,
            )

        listing = Listing(
            listing_id_sha=L.get("listing_id"),
            slug=slug,
            address=street,
            unit=unit,
            neighborhood=L.get("neighborhood") or "",
            city=L.get("city"),
            state=L.get("state"),
            zip=L.get("zip") or "",
            latitude=L.get("latitude"),
            longitude=L.get("longitude"),
            status="for-rent" if L.get("is_rent") else "for-sale",
            price=price,
            beds=beds_val,
            baths_full=baths_full_val,
            baths_half=L.get("baths_half") or 0,
            sqft=sqft_val,
            lot_sqft=lot_sqft,
            year_built=year_built,
            property_type=property_type,
            description=desc,
            features=json.dumps(feats),
            hero_image=hero,
            gallery_images=json.dumps(gallery),
            mls_number=mls,
            hoa_fee_usd_month=(150 + (h % 1850)) if property_type in {"Condo", "Co-op", "Townhouse", "Apartment"} else 0,
            days_on_compass=days,
            listed_at=datetime(2026, 1, 1) + timedelta(days=days % 120),
            is_open_house=is_open,
            open_house_date=oh_date,
            open_house_time=oh_time,
            is_new=is_new,
            is_compass_exclusive=is_compass_exclusive,
            is_luxury=is_luxury,
            is_pending=is_pending,
            has_parking=has_parking,
            has_pool=has_pool,
            has_doorman=has_doorman,
            has_elevator=has_elevator,
            has_garage=has_garage,
            has_waterfront=has_waterfront,
            pets_allowed=pets_allowed,
            furnished=furnished,
            agent_id=agent.id,
        )
        db.session.add(listing)
        listing_count += 1

    db.session.commit()


# ─── Seed: benchmark users + their data ───────────────────────────────────────


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
                      .filter_by(city=cfg["tour_city"], status="for-sale")
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
                      .filter_by(city=c_cfg["filter_city"], status="for-sale")
                      .order_by(Listing.price).limit(20).all())
        pick = [candidates[(_h("col", user.email, i)) % len(candidates)].id
                for i in range(3)] if candidates else []
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
                 .filter_by(city=cfg["tour_city"], status="for-sale")
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
