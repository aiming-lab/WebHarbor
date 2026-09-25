#!/usr/bin/env python3
"""Deterministic seed builder for the public_storage mirror.

Reads the tracked snapshots under source_data/ (captured from the live
publicstorage.com; see provenance.json) and materializes the full catalog:

  facilities.json   -> Facility + Unit + Review rows (real upstream property
                       ids, unit ids, dimensions, features, in-store vs
                       online prices, promotions, urgency flags, office and
                       access hours, amenities, photos, coordinates, ratings
                       and the facility's own customer reviews)
  site_content.json -> SiteCopy blocks (homepage copy, size-guide hub,
                       comparison chart, storage-type page copy, storage-
                       solutions copy), BlogArticle rows, HelpTopic rows,
                       SizeFaq rows and the facility-scope FAQ entries

Benchmark users and their pre-existing reservations / rentals / saved
facilities are defined below as fixed fixtures so every seed build is
byte-identical (PYTHONHASHSEED=0, frozen bcrypt digest, sorted iteration).
"""
from __future__ import annotations

import json
import pathlib
from datetime import date

BASE_DIR = pathlib.Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data"

# Frozen bcrypt digest for the benchmark password 'TestPass123!' (the digest
# is frozen rather than re-generated so the seed DB is byte-identical on
# every rebuild; the digest was produced with Flask-Bcrypt's standard cost).
BENCHMARK_PASSWORD_DIGEST = (
    "$2b$12$mTNQa9oqZyOoIJBpKN.0p.LVaApMSu9gZnYufEZrciM5QgBN7EM7u"
)

MIRROR_REFERENCE_DATE = date(2026, 9, 24)

BENCHMARK_USERS = [
    {
        "username": "alice_j",
        "email": "alice.j@test.com",
        "first_name": "Alice",
        "last_name": "Johnson",
        "phone": "(206) 555-0143",
        "account_number": "483920",
    },
    {
        "username": "bob_c",
        "email": "bob.c@test.com",
        "first_name": "Bob",
        "last_name": "Chen",
        "phone": "(312) 555-0177",
        "account_number": "517204",
    },
    {
        "username": "carol_d",
        "email": "carol.d@test.com",
        "first_name": "Carol",
        "last_name": "Davis",
        "phone": "(407) 555-0129",
        "account_number": "629145",
    },
    {
        "username": "david_k",
        "email": "david.k@test.com",
        "first_name": "David",
        "last_name": "Kim",
        "phone": "(720) 555-0162",
        "account_number": "730518",
    },
]

# Pre-existing holds (unit_id references the real upstream unit ids from the
# facility snapshot). Codes are fixed so the seed is byte-reproducible.
PREEXISTING_RESERVATIONS = [
    {
        "user": "alice.j@test.com",
        "unit_id": "V_1453660",
        "code": "PS-3184265",
        "holder_name": "Alice Johnson",
        "holder_email": "alice.j@test.com",
        "holder_phone": "(206) 555-0143",
        "move_in_date": "10/01/2026",
        "status": "held",
    },
    {
        "user": "bob.c@test.com",
        "unit_id": "V_1354769",
        "code": "PS-4907132",
        "holder_name": "Bob Chen",
        "holder_email": "bob.c@test.com",
        "holder_phone": "(312) 555-0177",
        "move_in_date": "10/03/2026",
        "status": "held",
    },
    {
        "user": "carol.d@test.com",
        "unit_id": "V_238493",
        "code": "PS-5216803",
        "holder_name": "Carol Davis",
        "holder_email": "carol.d@test.com",
        "holder_phone": "(407) 555-0129",
        "move_in_date": "09/28/2026",
        "status": "held",
    },
    {
        "user": "david.k@test.com",
        "unit_id": "V_131464",
        "code": "PS-6038417",
        "holder_name": "David Kim",
        "holder_email": "david.k@test.com",
        "holder_phone": "(720) 555-0162",
        "move_in_date": "10/05/2026",
        "status": "cancelled",
    },
]

# In-force leases feeding the bill-pay flow.
PREEXISTING_RENTALS = [
    {
        "user": "alice.j@test.com",
        "unit_id": "V_1453663",
        "started_on": "06/15/2026",
        "monthly_rate": 227.0,
        "balance_due": 227.0,
        "next_bill_date": "10/01/2026",
        "gate_code": "#4471",
    },
    {
        "user": "bob.c@test.com",
        "unit_id": "V_1354771",
        "started_on": "08/02/2026",
        "monthly_rate": 186.0,
        "balance_due": 186.0,
        "next_bill_date": "10/01/2026",
        "gate_code": "#9136",
    },
    {
        "user": "carol.d@test.com",
        "unit_id": "V_57194",
        "started_on": "05/20/2026",
        "monthly_rate": 129.0,
        "balance_due": 129.0,
        "next_bill_date": "10/01/2026",
        "gate_code": "#5502",
    },
    {
        "user": "david.k@test.com",
        "unit_id": "V_150216",
        "started_on": "07/09/2026",
        "monthly_rate": 158.0,
        "balance_due": 158.0,
        "next_bill_date": "10/01/2026",
        "gate_code": "#2874",
    },
]

# Saved (favorited) facilities per benchmark user, keyed by facility id.
SAVED_FACILITIES = {
    "alice.j@test.com": [81, 2051],
    "bob.c@test.com": [485, 348],
    "carol.d@test.com": [611, 509],
    "david.k@test.com": [593, 454],
}

GENERAL_FAQS = [
    {
        "q": "How much do self-storage units cost?",
        "a": "Self-storage prices vary by location, unit size, features, and availability. Smaller units typically cost less than larger ones, and indoor and climate-controlled units may be priced differently than standard units. Public Storage offers month-to-month rentals, so you only pay for the time you need.",
    },
    {
        "q": "What special deals or discounts are available for storage units?",
        "a": "Specials vary by location and unit type, so checking current rates and promotions in your area is the best way to find the most up-to-date offers.",
    },
    {
        "q": "How do I choose the right size storage unit?",
        "a": "Start by taking inventory of what you plan to store and how often you'll need to access it. A small 5x5 unit often fits boxes or small household items, while medium sizes like 10x10 work well for multiple rooms' worth of belongings. Larger units, such as 10x20 or 10x30, are designed for bigger items or business needs.",
    },
    {
        "q": "What types of storage units are available?",
        "a": "Indoor Storage Units: Located inside a building and accessible through interior hallways. Outdoor Storage Units: Located outside with drive-up access. Climate-Controlled Units: Kept at moderate temperature and humidity. Vehicle Storage: Enclosed, covered or uncovered parking spaces.",
    },
    {
        "q": "What is climate-controlled storage, and do I need it?",
        "a": "Climate-controlled storage units are kept within a moderate temperature range to help protect temperature-sensitive belongings such as wood furniture, electronics, photographs, and important documents from extreme heat or cold.",
    },
    {
        "q": "What does drive-up access mean for a storage unit?",
        "a": "Drive-up access units have exterior doors that you can pull a vehicle right up to, so you can load and unload directly from your car, truck or van without walking through hallways.",
    },
    {
        "q": "Where can I get 24/7 access storage?",
        "a": "Many Public Storage properties offer 24/7 access, so you can get to your belongings whenever you need them. Look for the 24/7 Access Available badge on the facility's page to confirm before you reserve.",
    },
    {
        "q": "What are the top security features to look for in a storage facility?",
        "a": "Electronic gates with passcode entry, well-lit hallways and grounds, video surveillance cameras, and sturdy locks on every unit door are the core security features at Public Storage properties.",
    },
    {
        "q": "What cleanliness measures are taken at self-storage units?",
        "a": "Properties are cleaned regularly, with move-out sweeps between tenants, and many locations keep moving carts and dollies available for customer use.",
    },
    {
        "q": "What are the most convenient storage options?",
        "a": "The most convenient option depends on what you are storing: drive-up units for heavy or bulky items, indoor units for belongings you want sheltered from the weather, and vehicle spaces for cars, RVs and boats.",
    },
]

HELP_TOPICS = [
    {
        "slug": "reservations-and-holds",
        "label": "Reservations & Holds",
        "summary": "How free reservations work, how long a hold lasts, and how to manage or cancel one.",
        "body": [
            "A reservation holds a specific unit for you at the quoted online price with no payment and no obligation. Holds last for seven days, giving you time to visit the property and complete the rental.",
            "You can look up your reservation any time from the Your Reservation page with the reservation code from your confirmation screen or email, together with the email address you used when holding the unit.",
            "To cancel a reservation, open it from the Your Reservation page or from the Reservations section of your account and choose Cancel Reservation. There is no fee to cancel, and nothing is charged when you hold a unit online.",
        ],
    },
    {
        "slug": "renting-and-move-in",
        "label": "Renting & Move-In",
        "summary": "Completing your rental, move-in steps, gate codes, and what to bring on day one.",
        "body": [
            "Complete your rental online in minutes: choose your unit, enter your contact details, and provide a valid payment method for the first month's rent. New rentals are subject to a one-time $29 administration fee unless the unit's promotion waives it.",
            "On move-in day, stop by the property office during office hours to sign your rental agreement and pick up your lock, or use the eRental check-in flow from your phone to skip the counter entirely.",
            "Your gate code and unit access details appear in your account once the rental is complete. Bring a government-issued photo ID matching the name on the rental agreement.",
        ],
    },
    {
        "slug": "billing-and-payments",
        "label": "Billing & Payments",
        "summary": "Monthly billing dates, payment methods, and how to pay your bill online.",
        "body": [
            "Rent is billed monthly on the anniversary of your move-in date. You can pay online from the Pay Bill page with a credit or debit card, or set up AutoPay so your card is charged automatically each month.",
            "To pay online, enter your account number and the email address on the account, then choose the amount to pay. Payments post immediately and a confirmation number is provided for your records.",
            "A late fee applies if a monthly payment is more than five days past due, so paying on time keeps your balance at zero.",
        ],
    },
    {
        "slug": "unit-sizes-and-features",
        "label": "Unit Sizes & Features",
        "summary": "Choosing a size, climate control, drive-up access, and vehicle parking.",
        "body": [
            "Unit sizes run from 5x5 walk-in-closet spaces to 10x25 units that hold a four-bedroom home, plus enclosed, covered and uncovered vehicle spaces up to 50 feet long.",
            "Climate-controlled units stay within a moderate temperature range and are recommended for wood furniture, electronics, media, and documents. Drive-up units open to the outside so you can unload directly from your vehicle.",
            "The Size Guide page shows a comparison chart with square footage, cubic footage, and what each size typically holds, so you can pick the right fit before you reserve.",
        ],
    },
    {
        "slug": "security-and-access",
        "label": "Security & Access",
        "summary": "Gate hours, keypad entry, cameras, lighting, and 24/7 access properties.",
        "body": [
            "Every property is fenced and gated with electronic keypad entry. Hallways and grounds are well lit, and video cameras monitor the property around the clock.",
            "Access hours vary by property. Facilities with the 24/7 Access Available badge let you reach your unit any time; others keep gate hours such as 6:00 AM to 10:00 PM daily.",
            "Only tenants receive gate codes. Do not share your code with anyone, and report a lost code to the property manager immediately.",
        ],
    },
    {
        "slug": "account-management",
        "label": "Account Management",
        "summary": "Creating an account, updating contact details, and managing saved locations.",
        "body": [
            "Create an account with your email address to keep your reservations, rentals and saved locations in one place and to check in faster online.",
            "You can update the name or phone number on your account at any time from the Account Details page. Your account number is shown there and is what you use to pay your bill online.",
            "Save the facilities you use most so you can jump straight back to their unit lists, hours and contact details.",
        ],
    },
]


def _load(name):
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


def build_seed(db):
    """Materialize the catalog rows from the tracked source snapshot."""
    from app import (Facility, Unit, Review, SiteCopy, BlogArticle,
                     HelpTopic, SizeFaq, FaqEntry, ZipResult)

    if Facility.query.count() > 0:
        return  # already populated; keep the seed idempotent as a whole

    facilities = _load("facilities.json")
    content = _load("site_content.json")

    for fid in sorted(facilities, key=lambda k: int(k)):
        f = facilities[fid]
        facility = Facility(
            id=f["id"],
            slug_state=f["slug_state"],
            slug_city=f["slug_city"],
            address=f["address"],
            city=f["city"],
            state=f["state"],
            zip=f["zip"],
            phone=f["phone"],
            lat=f["lat"],
            lng=f["lng"],
            rating=f["rating"],
            review_count=f["review_count"],
            badges=json.dumps(f["badges"]),
            office_hours=json.dumps(f.get("office_hours") or {}),
            access_hours=json.dumps(f.get("access_hours") or {}),
            amenities=json.dumps(f["amenities"]),
            photos=json.dumps(f["photos"]),
            featured=(int(fid) % 7 == 0),
        )
        db.session.add(facility)

        for u in f["units"]:
            db.session.add(Unit(
                unit_id=u["unit_id"],
                facility_id=f["id"],
                category=u["category"],
                dims=u["dims"],
                features=json.dumps(u["features"]),
                web_price=u["web_price"],
                list_price=u["list_price"],
                min_price=u["min_price"],
                promo=u.get("promo"),
                urgency=u.get("urgency"),
                is_vehicle=u.get("is_vehicle", False),
            ))

        for r in f["reviews"]:
            db.session.add(Review(
                facility_id=f["id"],
                author=r["author"],
                rating=r["rating"],
                date=r["date"],
                body=r["body"],
            ))

    # ---- site copy blocks
    copy_blocks = {
        "popular_cities": content.get("home_copy", {}).get("popular_cities", []),
        "size_cards": content.get("size_guide", {}).get("size_cards", []),
        "comparison_chart": content.get("size_guide", {}).get("comparison_chart", []),
        "size_tips": content.get("size_guide", {}).get("tips", []),
        "home_copy": content.get("home_copy", {}),
    }
    for key in sorted(copy_blocks):
        db.session.add(SiteCopy(key=key, value=json.dumps(copy_blocks[key])))

    for key in sorted(content.get("type_pages", {})):
        db.session.add(SiteCopy(
            key=f"type_page:{key}",
            value=json.dumps(content["type_pages"][key])))
    for key in sorted(content.get("solutions", {})):
        db.session.add(SiteCopy(
            key=f"solution:{key}",
            value=json.dumps(content["solutions"][key])))

    # ---- blog articles
    for a in sorted(content.get("blog_articles", []),
                    key=lambda x: (x.get("published") or "", x.get("slug") or "")):
        if not a.get("slug") or not a.get("paragraphs"):
            continue
        db.session.add(BlogArticle(
            slug=a["slug"],
            category=a.get("category") or "storage-tips",
            title=a.get("title") or a.get("page_title") or a["slug"],
            published=a.get("published") or "2026-01-01",
            image_path=a.get("image_path"),
            body=json.dumps(a["paragraphs"][:12]),
        ))

    # ---- help center
    for topic in HELP_TOPICS:
        db.session.add(HelpTopic(
            slug=topic["slug"], label=topic["label"],
            summary=topic["summary"], body=json.dumps(topic["body"])))

    # ---- size guide FAQ pages
    size_faqs = content.get("size_faqs", {})
    page_key_by_file = {
        "sg_locker": "sg_locker", "sg_5x5": "sg_5x5", "sg_5x10": "sg_5x10",
        "sg_5x15": "sg_5x15", "sg_10x10": "sg_10x10", "sg_10x15": "sg_10x15",
        "sg_10x20": "sg_10x20", "sg_10x25": "sg_10x25", "sg_veh20": "sg_veh20",
        "sg_veh35": "sg_veh35", "sg_veh50": "sg_veh50",
    }
    for file_key in sorted(size_faqs):
        page_key = page_key_by_file.get(file_key, file_key)
        for faq in size_faqs[file_key].get("faqs", []):
            if faq.get("q") and faq.get("a"):
                db.session.add(SizeFaq(
                    page_key=page_key,
                    question=faq["q"].strip(),
                    answer=faq["a"].strip()))
    # The lockers page carries its own intro copy rather than captured FAQs.
    if not any(size_faqs.get("sg_locker", {}).get("faqs", [])):
        db.session.add(SizeFaq(
            page_key="sg_locker",
            question="What is a locker storage unit?",
            answer="Lockers are suitable for strong small boxes, clothing and "
                   "similar items that do not require tall ceilings, as locker "
                   "sizes and shapes vary and some may have lower ceilings. "
                   "They are our most budget-friendly spaces."))
        db.session.add(SizeFaq(
            page_key="sg_locker",
            question="What can I keep in a locker?",
            answer="From cabinets to containers, find the perfect place for "
                   "all your stuff. Lockers work best for compact items you "
                   "need to keep close but out of the way, such as seasonal "
                   "clothing, documents and small boxes."))

    # ---- zip search results captured from the live site
    zip_searches = _load("zip_searches.json") if (SOURCE / "zip_searches.json").exists() else {}
    for z in sorted(zip_searches):
        entry = zip_searches[z]
        for position, res in enumerate(entry.get("results", [])):
            db.session.add(ZipResult(
                zip=z, slug=entry["slug"],
                facility_id=res["id"], distance=res["distance"],
                position=position))

    # ---- general + per-facility FAQs
    for faq in GENERAL_FAQS:
        db.session.add(FaqEntry(scope="general",
                                question=faq["q"], answer=faq["a"]))
    db.session.commit()


def build_benchmark_users(db, bcrypt):
    """Seed the four benchmark users with their pre-existing state."""
    from app import (User, Reservation, Rental, SavedFacility, Unit)

    if User.query.filter_by(email="alice.j@test.com").first():
        return

    users = {}
    for spec in BENCHMARK_USERS:
        user = User(
            username=spec["username"],
            email=spec["email"],
            password_hash=BENCHMARK_PASSWORD_DIGEST,
            first_name=spec["first_name"],
            last_name=spec["last_name"],
            phone=spec["phone"],
            account_number=spec["account_number"],
        )
        db.session.add(user)
        users[spec["email"]] = user
    db.session.commit()

    for res in PREEXISTING_RESERVATIONS:
        unit = Unit.query.filter_by(unit_id=res["unit_id"]).first()
        if unit is None:
            continue
        db.session.add(Reservation(
            code=res["code"],
            user_id=users[res["user"]].id,
            facility_id=unit.facility_id,
            unit_row_id=unit.id,
            holder_name=res["holder_name"],
            holder_email=res["holder_email"],
            holder_phone=res["holder_phone"],
            move_in_date=res["move_in_date"],
            status=res["status"],
            created_at="09/15/2026",
        ))

    for rent in PREEXISTING_RENTALS:
        unit = Unit.query.filter_by(unit_id=rent["unit_id"]).first()
        if unit is None:
            continue
        db.session.add(Rental(
            user_id=users[rent["user"]].id,
            facility_id=unit.facility_id,
            unit_row_id=unit.id,
            started_on=rent["started_on"],
            monthly_rate=rent["monthly_rate"],
            balance_due=rent["balance_due"],
            next_bill_date=rent["next_bill_date"],
            gate_code=rent["gate_code"],
        ))

    for email in sorted(SAVED_FACILITIES):
        for facility_id in SAVED_FACILITIES[email]:
            db.session.add(SavedFacility(
                user_id=users[email].id, facility_id=facility_id))

    db.session.commit()


def canonicalize(db):
    """Make a fresh build byte-comparable with the previous one.

    SQLAlchemy emits index DDL in set order, so sqlite_master can list the
    same indexes in a different sequence between runs, and identical rows can
    land in a different page layout. Recreating the indexes by name and then
    rewriting the file with VACUUM removes both, which is what lets a
    maintainer regenerate the shipped database and compare it.

    This runs only on a build that actually seeded. Both seed entry points
    early-return on a populated database, so a container boot or a /reset
    (which copies the already-populated seed file) never reaches here and
    never rewrites the runtime database.
    """
    rows = db.session.execute(db.text(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
    )).fetchall()
    for name, statement in sorted(rows):
        db.session.execute(db.text(f'DROP INDEX IF EXISTS "{name}"'))
        db.session.execute(db.text(statement))
    db.session.commit()
    db.session.execute(db.text("VACUUM"))
    db.session.commit()


if __name__ == "__main__":
    # Standalone entry point: build the seed DB directly (PYTHONHASHSEED=0),
    # then publish it as the site's instance_seed (marriott pattern: the
    # gated bootstrap seeds instance/, this copies it to instance_seed/).
    import os
    import shutil
    os.environ.setdefault("PYTHONHASHSEED", "0")
    import app as app_module

    with app_module.app.app_context():
        app_module.db.create_all()
        app_module.seed_database()
        app_module.seed_benchmark_users()
        canonicalize(app_module.db)
    seed_dir = BASE_DIR / "instance_seed"
    seed_dir.mkdir(exist_ok=True)
    shutil.copyfile(BASE_DIR / "instance" / "public_storage.db",
                    seed_dir / "public_storage.db")
    print("seed built")
