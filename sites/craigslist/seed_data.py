"""Build a deterministic, source-backed Craigslist seed. Never runs at server startup.

python seed_data.py --source captured/listings.json --output instance_seed/craigslist.db
Source JSON/HTML is a build input; runtime handlers read SQLite only.
"""

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re

SNAPSHOT_NOW = datetime(2026, 9, 18, 23, 59, 59)
REGIONS = [
    "san francisco",
    "east bay",
    "south bay",
    "peninsula",
    "north bay",
    "santa cruz",
]
CATEGORY_GROUPS = [
    {
        "slug": "community",
        "name": "community",
        "columns": [("events", "events", "eve"), ("volunteers", "volunteers", "vol")],
    },
    {
        "slug": "housing",
        "name": "housing",
        "columns": [("apartments", "apts / housing", "apa")],
    },
    {"slug": "jobs", "name": "jobs", "columns": [("healthcare", "healthcare", "hea")]},
    {
        "slug": "for_sale",
        "name": "for sale",
        "columns": [
            ("furniture", "furniture", "fua"),
            ("electronics", "electronics", "ela"),
            ("bikes", "bikes", "bia"),
            ("cars_trucks", "cars+trucks", "cta"),
            ("free", "free stuff", "zip"),
        ],
    },
    {
        "slug": "services",
        "name": "services",
        "columns": [
            ("lessons", "lessons / tutoring", "lss"),
            ("labor_move", "labor / move", "lbs"),
        ],
    },
]


def password_hash(email):
    salt = hashlib.sha256(email.encode()).hexdigest()[:16]
    digest = hashlib.pbkdf2_hmac("sha256", b"TestPass123!", salt.encode(), 600000).hex()
    return f"pbkdf2:sha256:600000$" + salt + "$" + digest


def source_date(value):
    if not value:
        raise ValueError("Source posting date is missing")
    return datetime.fromisoformat(value).replace(tzinfo=None)


def build(source, output):
    if output.exists():
        raise ValueError("Refusing to overwrite an existing seed")
    output.parent.mkdir(parents=True, exist_ok=True)
    os.environ["CRAIGSLIST_BUILD_SEED"] = "1"
    os.environ["CRAIGSLIST_INSTANCE"] = str(output.parent.resolve())
    import app as site

    if output.name != "craigslist.db":
        raise ValueError("Output filename must be craigslist.db")
    captures = json.loads(source.read_text())
    # Excluded after manual content review: opaque/personal event and vacation promotion.
    excluded = {
        68: "No intelligible public event details",
        74: "Vacation promotion, not a local community event",
    }
    inventory = []
    with site.app.app_context():
        # SQLAlchemy stores indexes in sets; explicit ordering makes independent
        # builds byte-identical, not merely logically equivalent.
        from sqlalchemy.schema import CreateTable, CreateIndex

        with site.db.engine.begin() as connection:
            for table in site.db.metadata.sorted_tables:
                connection.execute(CreateTable(table))
                for index in sorted(table.indexes, key=lambda item: item.name):
                    connection.execute(CreateIndex(index))
        categories = {}
        for group in CATEGORY_GROUPS:
            for slug, name, abbrev in group["columns"]:
                cat = site.Category(
                    slug=slug,
                    name=name,
                    abbrev=abbrev,
                    group_slug=group["slug"],
                    group_name=group["name"],
                    display_order=len(categories),
                )
                site.db.session.add(cat)
                categories[slug] = cat
        site.db.session.flush()
        seen = set()
        for i, record in enumerate(captures, 1):
            if i in excluded:
                continue
            if "error" in record or record["source_id"] in seen:
                raise ValueError(f"Invalid/duplicate source row {i}")
            seen.add(record["source_id"])
            if record["area"] not in REGIONS:
                raise ValueError(f"Unknown source area for {i}")
            attrs = dict(record["attributes"])
            attrs.pop("additional attributes", None) if attrs.get(
                "additional attributes"
            ) == "more ads by this seller" else None
            if attrs.get("additional attributes"):
                attrs["additional attributes"] = attrs["additional attributes"].replace(
                    "; more ads by this seller", ""
                )
            sqft = re.search(r"(\d+)\s*ft\s*2", attrs.get("additional attributes", ""))
            beds = re.search(r"(\d+)BR", attrs.get("additional attributes", ""))
            details = dict(
                attrs,
                images=[p["path"] for p in record["photos"]],
                _source_url=record["source_url"],
                _source_id=record["source_id"],
                _source_sha256=record["source_sha256"],
                _captured_at=record["captured_at"],
            )
            cat = categories[record["category_slug"]]
            row = site.Listing(
                id=i,
                title=record["title"],
                slug=site.slugify(record["title"]) + "-" + str(i),
                category_id=cat.id,
                category_slug=cat.slug,
                category_group=cat.group_slug,
                area=record["area"],
                neighborhood=record["neighborhood"],
                price=record["price"],
                sqft=int(sqft.group(1)) if sqft else None,
                bedrooms=int(beds.group(1)) if beds else None,
                condition=attrs.get("condition", ""),
                compensation=attrs.get("compensation", ""),
                employment_type=attrs.get("employment type", ""),
                company=attrs.get("company", ""),
                description=record["description"],
                details_json=json.dumps(details, ensure_ascii=False, sort_keys=True),
                image=record["photos"][0]["path"] if record["photos"] else "",
                seller_name="listing author",
                seller_email="",
                reply_phone="",
                posted_at=source_date(record["posted_at"]),
                updated_at=source_date(record["updated_at"]),
                status="active",
                view_count=0,
                flag_count=0,
            )
            site.db.session.add(row)
            inventory.append(
                dict(
                    id=i,
                    title=row.title,
                    source_url=record["source_url"],
                    source_id=record["source_id"],
                    source_sha256=record["source_sha256"],
                    captured_at=record["captured_at"],
                    images=record["photos"],
                    no_photo_in_source=not record["photos"],
                )
            )
        users = []
        for email, name, username, area in [
            ("alice.j@test.com", "Alice Johnson", "alice", "san francisco"),
            ("ben.k@test.com", "Ben Kim", "ben", "east bay"),
            ("carla.m@test.com", "Carla Martinez", "carla", "south bay"),
            ("david.p@test.com", "David Patel", "david", "peninsula"),
        ]:
            user = site.User(
                email=email,
                name=name,
                username=username,
                area=area,
                phone="(415) 555-0100",
                password_hash=password_hash(email),
                created_at=SNAPSHOT_NOW - timedelta(days=45),
            )
            site.db.session.add(user)
            users.append(user)
        site.db.session.flush()
        for lid in [1, 34, 35]:
            site.db.session.add(
                site.SavedListing(
                    user_id=users[0].id,
                    listing_id=lid,
                    note="compare before contacting",
                    created_at=SNAPSHOT_NOW - timedelta(days=2),
                )
            )
        site.db.session.add(
            site.SavedListing(
                user_id=users[1].id,
                listing_id=49,
                note="Ben's saved monitor",
                created_at=SNAPSHOT_NOW - timedelta(days=1),
            )
        )
        site.db.session.add(
            site.SavedSearch(
                user_id=users[0].id,
                name="East Bay furniture",
                query_text="chair",
                category_slug="furniture",
                area="east bay",
                max_price=100,
                created_at=SNAPSHOT_NOW - timedelta(days=3),
            )
        )
        site.db.session.add(
            site.Message(
                user_id=users[0].id,
                listing_id=35,
                sender_name="Demo leasing office",
                sender_email="leasing@example.test",
                body="We can show the Snell Avenue studio Wednesday at 5:30pm or Thursday at noon. Please tell us which works for you.",
                direction="inbound",
                is_read=False,
                created_at=SNAPSHOT_NOW - timedelta(hours=18),
            )
        )
        site.db.session.add(
            site.Message(
                user_id=users[1].id,
                listing_id=49,
                sender_name="Ben Kim",
                sender_email=users[1].email,
                body="Is this monitor available?",
                direction="outbound",
                is_read=True,
                created_at=SNAPSHOT_NOW - timedelta(hours=10),
            )
        )
        site.db.session.commit()
        site.db.engine.dispose()
    manifest = {
        "snapshot_date": SNAPSHOT_NOW.isoformat(),
        "listing_count": len(inventory),
        "benchmark_state": "Demo accounts, saved rows and mailbox messages are synthetic; listing facts/photos are sourced.",
        "excluded_capture_rows": excluded,
        "listings": inventory,
    }
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(args.source, args.output)
    args.inventory.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"Built {manifest['listing_count']} listings at {args.output}")
