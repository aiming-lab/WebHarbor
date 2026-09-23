#!/usr/bin/env python3
"""Deterministic seed for the Google Shopping mirror.

`python seed_data.py` regenerates the reset seed DB (instance_seed/
google_shopping.db) from the tracked _seed_catalog.py source alone — no
scraped_data, no wall clock, no random salt (frozen bcrypt hash), so the
SQLite artifact is byte-reproducible on every build. The same seed
functions run at every container boot and early-return on a populated DB,
preserving the byte-identical reset invariant.

Content provenance: every product row is a real product card captured from
the shopping.google.com "For you" feed on 2026-09-22 (title, merchant, price,
was-price, discount, product image, merchant favicon — see
asset_inventory.json + provenance.json). Departments are the real 15
department tiles with their real gstatic imagery. Feed sections are the
real homepage shelf headings with their real "Explore" queries.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _seed_catalog import DEPARTMENTS, PRODUCTS, SECTION_META

PRODUCT_DETAILS = json.loads((Path(__file__).resolve().parent / "product_details.json").read_text())

MIRROR_DATE = "2026-09-22"
PASSWORD = "TestPass123!"
# bcrypt hash of TestPass123! — frozen so the seed DB is byte-reproducible
# (generated with bcrypt.gensalt(rounds=12) once; identical for all users).
PASSWORD_HASH = "$2b$12$D/eRvVSrDoJ8.PZPF9Q/NOMd64jKdJ82.HbfdAntTLr58aoJs6gj."

BENCHMARK_USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display_name": "Alice Johnson"},
    {"username": "bob_c", "email": "bob.c@test.com", "display_name": "Bob Chen"},
    {"username": "carol_d", "email": "carol.d@test.com", "display_name": "Carol Davis"},
    {"username": "david_k", "email": "david.k@test.com", "display_name": "David Kim"},
]

# Real per-product rating data captured from the upstream product panel
# state (see NOTICE.md): aggregate rating on Google's internal 0-10 scale
# shown here as stars, plus the public review count.
REAL_RATINGS = {
    "Imily Bela Elegant Womens Long Oversized Trench Coat Womens Windproof Long Coat":
        {"rating": 3.5, "review_count": 4},
}

# Deterministic pre-existing state per benchmark user (mirrors the signed-in
# shopping-list / price-tracking surfaces; product titles reference the
# captured catalog).
USER_SAVED = {
    "alice.j@test.com": [
        "Gap Factory Women's Modern Trench Coat",
    ],
    "bob.c@test.com": [],
    "carol.d@test.com": [],
    "david.k@test.com": [],
}
USER_TRACKED = {
    "alice.j@test.com": [],
    "bob.c@test.com": [],
    "carol.d@test.com": [],
    "david.k@test.com": [],
}


def _title_to_product_row(row):
    from app import Department, Product
    (upstream_id, title, section, merchant, price, was, discount, image,
     favicon) = row
    meta = SECTION_META.get(section, {})
    department = (Department.query
                  .filter_by(name=meta.get("department", "Apparel")).first())
    return Product(
        upstream_id=upstream_id,
        title=title,
        department_id=department.id,
        category=meta.get("category", ""),
        image=image,
        price=price,
        was_price=was,
        discount_pct=discount,
        merchant_name=merchant,
        merchant_favicon=favicon,
        rating=REAL_RATINGS.get(title, {}).get("rating"),
        review_count=REAL_RATINGS.get(title, {}).get("review_count", 0),
        description=PRODUCT_DETAILS.get(upstream_id, {}).get("description", ""),
        specs_json=json.dumps(PRODUCT_DETAILS.get(upstream_id, {}).get("specs", {}), sort_keys=True),
        feed_section=section,
    )


def seed_database():
    """Materialize the captured catalog. Idempotent: early-returns."""
    from app import Department, FeedSection, Merchant, Product, db

    if Product.query.count() > 0:
        return

    for pos, dep in enumerate(DEPARTMENTS):
        db.session.add(Department(name=dep["name"], slug=dep["slug"],
                                  image=dep["image"], position=pos))

    section_position = {}
    for pos, heading in enumerate(SECTION_META):
        meta = SECTION_META[heading]
        db.session.add(FeedSection(position=pos, heading=heading,
                                   subheading=meta.get("subheading", ""),
                                   explore_query=meta.get("query", ""),
                                   tab="for_you"))
        section_position[heading] = pos
    db.session.flush()

    for pos, row in enumerate(PRODUCTS):
        product = _title_to_product_row(row)
        product.position = pos
        db.session.add(product)
    db.session.flush()

    # seed merchants so offers stay consistent with the captured cards
    for product in Product.query.all():
        merchant = Merchant.query.filter_by(name=product.merchant_name).first()
        if not merchant:
            merchant = Merchant(name=product.merchant_name,
                                favicon=product.merchant_favicon)
            db.session.add(merchant)
            db.session.flush()
        db.session.add(_make_offer(product, merchant))
    db.session.commit()


def _make_offer(product, merchant):
    from app import Offer
    return Offer(product_id=product.id, merchant_id=merchant.id,
                 price=product.price, was_price=product.was_price,
                 shipping=None, in_stock=True, position=0)


def seed_benchmark_users():
    """4 benchmark accounts + their pre-existing list state. Idempotent."""
    from app import (SavedItem, TrackedProduct, User, db)

    if User.query.filter_by(email="alice.j@test.com").first():
        return

    for row in BENCHMARK_USERS:
        db.session.add(User(email=row["email"],
                            display_name=row["display_name"],
                            password_hash=PASSWORD_HASH))
    db.session.flush()

    from app import Product
    for email, titles in USER_SAVED.items():
        user = User.query.filter_by(email=email).first()
        for title in titles:
            product = Product.query.filter_by(title=title).first()
            if product:
                db.session.add(SavedItem(user_id=user.id,
                                        product_id=product.id,
                                        added=MIRROR_DATE))
    for email, titles in USER_TRACKED.items():
        user = User.query.filter_by(email=email).first()
        for title in titles:
            product = Product.query.filter_by(title=title).first()
            if product:
                db.session.add(TrackedProduct(user_id=user.id,
                                              product_id=product.id,
                                              created=MIRROR_DATE))
    db.session.commit()


def rebuild_seed():
    """Regenerate the reset seed DB from tracked sources (build entrypoint)."""
    import os
    from app import db
    db_path = os.path.join(db.engine.url.database)
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(db_path + suffix)
        except FileNotFoundError:
            pass
    # a brand-new file keeps the SQLite header counters deterministic
    db.engine.dispose()
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    import os as _os
    _os.environ["GOOGLE_SHOPPING_SKIP_SEED"] = "1"
    from app import app
    with app.app_context():
        rebuild_seed()
    # write the seed artifact next to instance/
    import os
    import shutil
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "instance", "google_shopping.db")
    dst_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "instance_seed")
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copy2(src, os.path.join(dst_dir, "google_shopping.db"))
    print("seed DB written to instance_seed/google_shopping.db")
