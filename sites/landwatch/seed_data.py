"""Deterministic seed builder for the LandWatch mirror.

Reads the tracked, upstream-sourced source_data.json (listings, agents,
counties, cities, regions, taxonomy, homepage fixtures, static page text)
and materialises the runtime DB. Called at image build time (see the
Dockerfile) and defensively at boot; every seed function early-returns when
its data already exists so /reset/landwatch stays byte-identical.

    WEBSYN_SKIP_BOOTSTRAP=1 PYTHONHASHSEED=0 python3 seed_data.py

Benchmark fixtures (users, favorites, saved searches, inquiries) are
synthetic and reference real seeded listings; every date is pinned relative
to MIRROR_DATE so the seed is byte-stable across builds.
"""
from __future__ import annotations

import os

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

MIRROR_DATE = datetime(2026, 9, 22)

from app import (  # noqa: E402
    ACTIVE_STATUSES,
    Agent,
    CategoryTile,
    City,
    County,
    Favorite,
    HomeFeatured,
    Inquiry,
    Listing,
    PropertyType,
    Region,
    SavedSearch,
    StaticPage,
    User,
    app,
    db,
    dump_json,
    slugify,
    stable_password_hash,
)

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data.json"
INSTANCE_SEED = BASE_DIR / "instance_seed"

BENCHMARK_PASSWORD = "TestPass123!"
BENCHMARK_USERS = [
    {"email": "alice.j@test.com", "name": "Alice Johnson", "phone": "(919) 555-0147"},
    {"email": "bob.c@test.com", "name": "Bob Chen", "phone": "(512) 555-0183"},
    {"email": "carol.d@test.com", "name": "Carol Davis", "phone": "(303) 555-0126"},
    {"email": "david.k@test.com", "name": "David Kim", "phone": "(206) 555-0198"},
]


def load_source() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def clean_description(text: str) -> str:
    """Normalize upstream ld+json description artifacts into paragraphs.

    The live site's structured data stores the rendered page's paragraphs
    joined by ',,' runs (its renderer splits them into <p> elements) and,
    on a few listings, a ',DESCRIPTION:' separator before a second block.
    Split on the same markers so the mirror shows paragraphs like the
    upstream page; ',LABEL:,value' field pairs are left untouched because
    the live page renders them verbatim.
    """
    if not text:
        return text
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^\s*DESCRIPTION:\s*,\s*", "", text)
    text = re.sub(r",\s*DESCRIPTION:\s*,?\s*", "\n\n", text)
    text = re.sub(r"(?:\s*,){2,}", "\n\n", text)
    text = re.sub(r"(?<=\n),\s*", "", text)
    text = re.sub(r",\s*(?=\n)", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def iso(days_offset: int) -> str:
    return (MIRROR_DATE - timedelta(days=days_offset)).replace(
        microsecond=0).isoformat()


def seed_database() -> None:
    if Listing.query.count() > 0 or PropertyType.query.count() > 0:
        return
    source = load_source()

    for row in source.get("categories", []):
        db.session.add(PropertyType(label=row["label"], slug=row["slug"],
                                    type_slug=row["slug"],
                                    listing_count=row.get("listing_count", 0)))

    for row in source.get("counties", []):
        db.session.add(County(id=row["id"], name=row["name"], slug=row["slug"],
                              state=row["state"], state_code=row["state_code"],
                              state_slug=row["state_slug"]))
    for row in source.get("cities", []):
        db.session.add(City(name=row["name"], slug=row["slug"],
                            state=row["state"], state_code=row["state_code"],
                            state_slug=row["state_slug"]))
    for row in source.get("regions", []):
        db.session.add(Region(name=re.sub(r"\s+\d[\d,]*$", "", row["name"]),
                              slug=row["slug"],
                              counties=dump_json(row.get("counties", [])),
                              state_slug="texas-land-for-sale"))

    for row in source.get("agents", []):
        db.session.add(Agent(
            account_id=row["account_id"], slug=row["slug"] or slugify(
                f"{row['name']}-{row['account_id']}"),
            name=row["name"] or "", company=row["company"] or "",
            phone=row["phone"] or "", city=row.get("city"),
            state_code=row.get("state_code"), about=row.get("about"),
            portrait_id=row.get("portrait_id") or None, total_listings=0,
            website=row.get("website")))

    for row in source.get("listings", []):
        db.session.add(Listing(
            pid=row["pid"],
            title=row.get("title") or "",
            canonical_slug=row["canonical_slug"],
            price=row.get("price"),
            short_price=row.get("short_price") or "",
            price_per_acre=row.get("price_per_acre"),
            price_change_amount=row.get("price_change_amount"),
            price_change_date=row.get("price_change_date"),
            acres=row.get("acres"),
            beds=row.get("beds"),
            baths=row.get("baths"),
            half_baths=row.get("half_baths"),
            sqft=row.get("sqft"),
            sqft_display=row.get("sqft_display"),
            street=row.get("street") or "",
            city=row.get("city") or "",
            city_slug=row.get("city_slug") or "",
            county=row.get("county") or "",
            county_slug=row.get("county_slug") or "",
            county_id=row.get("county_id"),
            state=row.get("state") or "",
            state_slug=f"{slugify(row.get('state') or '')}-land-for-sale",
            state_code=row.get("state_code") or "",
            zip=row.get("zip") or "",
            latitude=row.get("latitude"),
            longitude=row.get("longitude"),
            status=row.get("status") or "Available",
            is_auction=bool(row.get("is_auction")),
            auction_start=row.get("auction_start"),
            property_types=",".join(row.get("types") or []),
            property_types_label=row.get("types_label") or "",
            category_slugs=",".join(row.get("category_slugs") or []),
            description_short=row.get("description_short") or "",
            description_full=clean_description(row.get("description_full") or ""),
            highlights=dump_json(row.get("highlights") or []),
            activities=dump_json(row.get("activities") or []),
            proposed_use=dump_json(row.get("proposed_use") or []),
            image_ids=dump_json(row.get("image_ids") or []),
            image_count=row.get("image_count") or 0,
            has_video=bool(row.get("has_video")),
            has_house=bool(row.get("has_house")),
            has_custom_map=bool(row.get("has_custom_map")),
            video_url=row.get("video_url"),
            listing_level_title=row.get("listing_level_title") or "",
            is_diamond=bool(row.get("is_diamond")),
            owner_financing=bool(row.get("owner_financing")),
            broker_id=(row.get("broker") or {}).get("account_id"),
            broker_name=(row.get("broker") or {}).get("name") or "",
            broker_company=(row.get("broker") or {}).get("company") or "",
            broker_phone=(row.get("broker") or {}).get("phone") or "",
            insert_date=row.get("insert_date"),
            last_updated=row.get("last_updated"),
            property_website=row.get("property_website"),
            sort_rank=row.get("sort_rank") or 0,
        ))

    for position, pid in enumerate(source.get("home_featured_pids", [])):
        db.session.add(HomeFeatured(pid=pid, position=position))
    for position, cat in enumerate(source.get("categories", [])):
        if not cat.get("tile_image"):
            continue
        db.session.add(CategoryTile(label=cat["label"], slug=cat["slug"],
                                    image=f"{cat['tile_image']}.webp",
                                    position=position))
    terms = source.get("terms_conditions") or {}
    if terms.get("body"):
        db.session.add(StaticPage(slug="terms-conditions",
                                  title=terms.get("title", "Terms and Conditions"),
                                  body=terms["body"]))
    db.session.commit()

    # agent aggregates from the seeded listings (mirror-consistent stats)
    for agent in Agent.query.all():
        rows = Listing.query.filter_by(broker_id=agent.account_id).all()
        prices = [l.price for l in rows if l.price]
        acres = [l.acres for l in rows if l.acres]
        agent.total_listings = len(rows)
        agent.price_min = min(prices) if prices else None
        agent.price_max = max(prices) if prices else None
        agent.acre_min = min(acres) if acres else None
        agent.acre_max = max(acres) if acres else None
        if not agent.state_code and rows:
            agent.state_code = rows[0].state_code
    db.session.commit()


def seed_benchmark_users() -> None:
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    users = {}
    for row in BENCHMARK_USERS:
        user = User(email=row["email"], name=row["name"], phone=row["phone"],
                    password_hash=stable_password_hash(BENCHMARK_PASSWORD),
                    created_at=iso(200), is_benchmark=True)
        db.session.add(user)
        users[row["email"]] = user
    db.session.commit()

    active = (Listing.query.filter(Listing.status.in_(ACTIVE_STATUSES))
              .order_by(Listing.sort_rank).all())
    if not active:
        return

    def take(offset, count):
        return [active[(offset + i) % len(active)] for i in range(count)]

    plan = {
        "alice.j@test.com": {
            "favorites": take(2, 5),
            "searches": [("Texas Land for Sale", "/texas-land-for-sale"),
                         ("Hunting Land under $250K",
                          "/hunting-property/price-100000-249999"),
                         ("Boerne, TX Land for Sale",
                          "/texas-land-for-sale/boerne")],
            "inquiries": [(take(2, 1)[0],
                           "Hello, I'd like more information about access "
                           "roads and water on this property. Thank you.")],
        },
        "bob.c@test.com": {
            "favorites": take(10, 4),
            "searches": [("Colorado Ranches over 100 Acres",
                          "/colorado-land-for-sale/acres-101-200")],
            "inquiries": [(take(10, 1)[0],
                           "Is owner financing available on this listing?")],
        },
        "carol.d@test.com": {
            "favorites": take(20, 3),
            "searches": [("Montana Land for Sale", "/montana-land-for-sale"),
                         ("Farms and Ranches in Tennessee",
                          "/tennessee-land-for-sale/farms-ranches")],
            "inquiries": [],
        },
        "david.k@test.com": {
            "favorites": take(30, 6),
            "searches": [("Waterfront Land in Florida",
                          "/florida-land-for-sale/waterfront-property")],
            "inquiries": [(take(30, 1)[0],
                           "Please send the plat map and any soil reports "
                           "you have for this tract.")],
        },
    }
    for email, spec in plan.items():
        user = users[email]
        for i, listing in enumerate(spec["favorites"]):
            db.session.add(Favorite(user_id=user.id, pid=listing.pid,
                                    created_at=iso(30 - i)))
        for i, (name, url) in enumerate(spec["searches"]):
            db.session.add(SavedSearch(user_id=user.id, name=name, url=url,
                                       alerts=(i == 0), created_at=iso(25 - i)))
        for i, (listing, message) in enumerate(spec["inquiries"]):
            db.session.add(Inquiry(user_id=user.id, pid=listing.pid,
                                   name=listing.broker_name,
                                   email=email, phone=user.phone,
                                   message=message, created_at=iso(12 - i)))
    db.session.commit()


def materialize_seed() -> None:
    """Copy the freshly built runtime DB into instance_seed/landwatch.db.

    The Dockerfile build step deletes instance/ after this pass; the final
    check_seed_databases.py gate and websyn_start.sh's boot-time
    `cp -a instance_seed instance` both need instance_seed/landwatch.db to
    exist (chase/youtube follow the same build-generated-seed pattern).
    """
    from app import RUNTIME_DB_PATH
    if INSTANCE_SEED.exists():
        shutil.rmtree(INSTANCE_SEED)
    INSTANCE_SEED.mkdir(parents=True)
    shutil.copyfile(RUNTIME_DB_PATH, INSTANCE_SEED / "landwatch.db")


def main() -> None:
    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()
        counts = {
            "listings": Listing.query.count(),
            "agents": Agent.query.count(),
            "counties": County.query.count(),
            "cities": City.query.count(),
            "regions": Region.query.count(),
            "users": User.query.count(),
        }
        print(f"[seed] {counts}")
    materialize_seed()


if __name__ == "__main__":
    main()
