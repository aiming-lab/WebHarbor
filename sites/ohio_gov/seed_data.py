"""Build-time seed for the Ohio.gov mirror.

Reads the tracked data/*.json files (real ohio.gov content captured from the
live site) and materializes them into the seed DB. Every entry point below is
gated at the whole-function level so re-running the boot path on a populated
DB is a byte-identical no-op.

The Docker build invokes this module directly (python3 seed_data.py) to
materialize instance_seed/ohio_gov.db from the tracked data snapshot;
websyn_start.sh then copies it into instance/ at boot.
"""
import json
import os
import re
import shutil
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE_DIR, "data")
RUNTIME_DB = Path(BASE_DIR) / "instance" / "ohio_gov.db"
SEED_DB = Path(BASE_DIR) / "instance_seed" / "ohio_gov.db"

USERS = [
    {"username": "alice_j", "email": "alice.j@test.com",
     "display_name": "Alice Johnson", "first_name": "Alice", "last_name": "Johnson",
     "phone": "(614) 555-0142", "address_line1": "88 Scioto Trail",
     "city": "Columbus", "state": "Ohio", "zip": "43215"},
    {"username": "bob_c", "email": "bob.c@test.com",
     "display_name": "Bob Chen", "first_name": "Bob", "last_name": "Chen",
     "phone": "(216) 555-0177", "address_line1": "1400 Edgewater Dr",
     "city": "Cleveland", "state": "Ohio", "zip": "44114"},
    {"username": "carol_d", "email": "carol.d@test.com",
     "display_name": "Carol Davis", "first_name": "Carol", "last_name": "Davis",
     "phone": "(513) 555-0193", "address_line1": "512 Vine St",
     "city": "Cincinnati", "state": "Ohio", "zip": "45202"},
    {"username": "david_k", "email": "david.k@test.com",
     "display_name": "David Kim", "first_name": "David", "last_name": "Kim",
     "phone": "(330) 555-0128", "address_line1": "77 Market Ave",
     "city": "Akron", "state": "Ohio", "zip": "44308"},
]
PASSWORD = "TestPass123!"
# Frozen scrypt hash of PASSWORD (seed-time hashing uses a random salt, which
# would make the SQLite seed differ on every build; pinning the hash keeps the
# build byte-reproducible — same approach as the medicare_gov mirror).
PASSWORD_HASH = ("scrypt:32768:8:1$Hu0mfb7iqIWVzg9p$"
                 "9df42802aa09b518700c5c1a53635aeab"
                 "f68996a0055d9e38533c3833a8591c0f4e14be62f0bbd9acb472c33dae6cbe37e"
                 "ce11e2e90a42e02483ebf8d84367a5")


def _load(name):
    with open(os.path.join(DATA, name)) as fh:
        return json.load(fh)


def seed_content(db):
    """Seed all site content. Called from app.py only when the DB is empty."""
    from models import (Agency, AlertItem, FAQ, FAQCategory, License,
                        NewsArticle, PhoneEntry, Resource, TopicHub)

    # -- topic hubs --------------------------------------------------------
    for hub in _load("topic_hubs.json"):
        db.session.add(TopicHub(slug=hub["slug"], title=hub["title"],
                                audience=hub["audience"],
                                parent_title=hub.get("parent")))

    # -- resources ---------------------------------------------------------
    for r in _load("resources.json"):
        db.session.add(Resource(
            title=r["title"], slug=r["slug"], audience=r["audience"],
            summary=r["summary"], body_html=r["body_html"],
            body_text=r["body_text"], launch_url=r["launch_url"],
            published=r["published"],
            related_agencies_json=json.dumps(r["related_agencies"]),
            image=r["image"], search_summary=r["search_summary"],
            search_date=r["search_date"],
            categories_json=json.dumps(r["categories"])))

    # -- news --------------------------------------------------------------
    for i, n in enumerate(_load("news.json")):
        db.session.add(NewsArticle(
            title=n["title"], slug=n["slug"], published=n["published"],
            source=n["source"], body_html=n["body_html"], image=n["image"],
            summary=n["summary"], position=i))

    # -- licenses ----------------------------------------------------------
    for l in _load("licenses.json"):
        db.session.add(License(
            name=l["name"], slug=l["slug"], url=l["url"], agency=l["agency"],
            agency_url=l["agency_url"], contact_label=l["contact_label"],
            contact_url=l["contact_url"]))

    # -- agencies ----------------------------------------------------------
    for a in _load("agencies.json"):
        db.session.add(Agency(
            name=a["name"], slug=a["slug"], url=a["url"],
            contact_method=a["contact_method"], contact_url=a["contact_url"],
            socials_json=json.dumps(a["socials"])))

    # -- phone directory ---------------------------------------------------
    for p in _load("phones.json"):
        db.session.add(PhoneEntry(name=p["name"], phone=p["phone"],
                                  agency=p["agency"]))

    # -- FAQs --------------------------------------------------------------
    for c in _load("faq_categories.json"):
        db.session.add(FAQCategory(slug=c["slug"], title=c["title"]))
    for f in _load("faqs.json"):
        db.session.add(FAQ(category_slug=f["category"], position=f["position"],
                           question=f["question"],
                           answer_html=f["answer_html"]))

    # -- alerts ------------------------------------------------------------
    ALERTS = [
        {"title": "Ohio Benefits self-service portal maintenance",
         "body_html": ("The Ohio Benefits self-service portal will be unavailable "
                       "Sunday, September 20 from 2:00 AM to 6:00 AM for scheduled "
                       "maintenance. Applications submitted during the window are "
                       "queued and processed after the upgrade."),
         "severity": "warning", "published": "September 15, 2026"},
        {"title": "BMV Online Services: scheduled outage",
         "body_html": ("Bureau of Motor Vehicles online services, including "
                       "vehicle registration renewals and driver license renewals, "
                       "will be offline Saturday, September 19 from 8:00 PM to "
                       "midnight while a legacy payment gateway is replaced."),
         "severity": "warning", "published": "September 14, 2026"},
        {"title": "Ohio Business Gateway tax filing extension",
         "body_html": ("The Ohio Business Gateway now supports the September 2026 "
                       "school district withholding tables. Employers should "
                       "download the updated tables before the next filing "
                       "deadline on October 31, 2026."),
         "severity": "information", "published": "September 11, 2026"},
        {"title": "Statewide severe weather awareness",
         "body_html": ("The Ohio Emergency Management Agency reminds Ohioans that "
                       "September is Ohio Preparedness Month. Review your "
                       "household emergency plan and sign up for county-level "
                       "alerts at ready.ohio.gov."),
         "severity": "information", "published": "September 1, 2026"},
    ]
    for i, a in enumerate(ALERTS):
        db.session.add(AlertItem(title=a["title"], body_html=a["body_html"],
                                 severity=a["severity"],
                                 published=a["published"], position=i))

    db.session.commit()


def seed_users(db):
    """Seed the 4 benchmark users with saved resources and subscriptions."""
    from models import (AlertSubscription, Resource, SavedResource, ScamReport,
                        TravelGuideRequest, User)

    users = []
    for spec in USERS:
        u = User(**spec)
        u.password_hash = PASSWORD_HASH
        db.session.add(u)
        users.append(u)
    db.session.commit()

    def res(slug):
        return Resource.query.filter_by(slug=slug).first()

    # Alice: benefits + education focus
    for slug in ["food-assistance", "home-energy-assistance-program",
                 "dolly-partons-imagination-library-of-ohio", "college-credit-plus",
                 "child-care-assistance"]:
        r = res(slug)
        if r:
            db.session.add(SavedResource(user_id=users[0].id, resource_id=r.id))
    db.session.add(AlertSubscription(user_id=users[0].id,
                                     email=users[0].email,
                                     alert_type="Outage notifications"))
    db.session.add(AlertSubscription(user_id=users[0].id,
                                     email=users[0].email,
                                     alert_type="Weather safety"))

    # Bob: business owner
    for slug in ["vendors-license", "sales-and-use-tax", "ohio-business-gateway",
                 "minority-business-assistance"]:
        r = res(slug)
        if r:
            db.session.add(SavedResource(user_id=users[1].id, resource_id=r.id))
    db.session.add(AlertSubscription(user_id=users[1].id,
                                     email=users[1].email,
                                     alert_type="Ohio Business Gateway"))
    db.session.add(TravelGuideRequest(
        user_id=users[1].id, full_name="Bob Chen", email="bob.c@test.com",
        address_line1="1400 Edgewater Dr", city="Cleveland", state="Ohio",
        zip="44114", format="Standard print"))

    # Carol: new resident
    for slug in ["change-your-mailing-address", "driver-licenses",
                 "ohio-housing-locator", "unclaimed-funds", "hunting-and-fishing-licenses"]:
        r = res(slug)
        if r:
            db.session.add(SavedResource(user_id=users[2].id, resource_id=r.id))
    db.session.add(AlertSubscription(user_id=users[2].id,
                                     email=users[2].email,
                                     alert_type="All alerts"))

    # David: jobs + one scam report filed
    for slug in ["ohiomeansjobs", "unemployment-benefits", "prevailing-wage"]:
        r = res(slug)
        if r:
            db.session.add(SavedResource(user_id=users[3].id, resource_id=r.id))
    db.session.add(ScamReport(
        user_id=users[3].id, full_name="David Kim", email="david.k@test.com",
        phone="(330) 555-0128", scam_type="Romance scam",
        description=("A caller pretending to be an online acquaintance asked for "
                     "gift card payments for a family emergency."),
        amount="450", occurred_on="August 2, 2026"))

    db.session.commit()


def materialize_seed() -> None:
    """Copy the freshly seeded runtime DB into instance_seed/ (build-time)."""
    SEED_DB.parent.mkdir(parents=True, exist_ok=True)
    if SEED_DB.exists():
        SEED_DB.unlink()
    shutil.copyfile(RUNTIME_DB, SEED_DB)


def seed_landing_content():
    from models import SiteContent, db
    if SiteContent.query.count():
        return
    for name in ('home_sections.json', 'landing_sections.json'):
        db.session.add(SiteContent(name=name, payload=json.dumps(_load(name), sort_keys=True)))
    db.session.commit()


def main() -> None:
    # Importing app runs its bootstrap (create_all + the gated seed functions),
    # which populates instance/ohio_gov.db from the tracked data snapshot when
    # the database is empty. The gates make re-imports a no-op, so the seed
    # stays byte-reproducible on every build.
    from app import Resource, User, app  # noqa: F401

    with app.app_context():
        seed_landing_content()
        counts = {
            "resources": Resource.query.count(),
            "users": User.query.count(),
        }
        print(f"[seed] ohio_gov {counts}")
    materialize_seed()


if __name__ == "__main__":
    main()
