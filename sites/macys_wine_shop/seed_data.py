"""macys_wine_shop — deterministic build-time/boot-time seeder.

Every content row comes from the tracked source_data.json snapshot of
https://macyswineshop.com/ (captured 2026-09-22). The seeder is idempotent at
the function level: each seed_* function early-returns when its table is
already populated, so container boots and /reset keep the SQLite database
byte-identical to instance_seed/macys_wine_shop.db.

Deterministic: no wall clock, no randomness, no unordered iteration. Run with
PYTHONHASHSEED=0 for byte-reproducible builds.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta

# When seed_data drives the build (python seed_data.py), the app module must
# not bootstrap its own pass first: this script wipes instance/ and rebuilds
# it deterministically. At normal container boot the env var is unset and the
# app's import-time bootstrap runs with its idempotent gates.
os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

from app import (Address, BlogArticle, CaseBottle, CartItem, Collection,
                 CollectionProduct, HomeSection, NewsletterSubscriber, Order,
                 OrderItem, PaymentMethod, Product, ProductImage,
                 ProductVariant, Review, SiteText, StateDisclosure, StaticPage,
                 User, app, db, stable_password_hash)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_PATH = os.path.join(BASE_DIR, "source_data.json")

MIRROR_DATE = datetime(2026, 9, 22, 12, 0, 0)

BENCHMARK_USERS = [
    {"username": "alice_j", "email": "alice.j@test.com",
     "display_name": "Alice Johnson", "first_name": "Alice", "last_name": "Johnson",
     "phone": "(415) 555-0165"},
    {"username": "bob_c", "email": "bob.c@test.com",
     "display_name": "Bob Chen", "first_name": "Bob", "last_name": "Chen",
     "phone": "(206) 555-0142"},
    {"username": "carol_d", "email": "carol.d@test.com",
     "display_name": "Carol Davis", "first_name": "Carol", "last_name": "Davis",
     "phone": "(312) 555-0188"},
    {"username": "david_k", "email": "david.k@test.com",
     "display_name": "David Kim", "first_name": "David", "last_name": "Kim",
     "phone": "(646) 555-0117"},
]
PASSWORD = "TestPass123!"

USER_PROFILES = {
    "alice.j@test.com": {
        "addresses": [
            {"label": "Home", "full_name": "Alice Johnson", "line1": "460 King St",
             "line2": "Apt 5B", "city": "San Francisco", "state": "CA",
             "zip_code": "94107", "phone": "(415) 555-0165", "is_default": True},
            {"label": "Office", "full_name": "Alice Johnson",
             "line1": "680 Folsom St", "city": "San Francisco", "state": "CA",
             "zip_code": "94107", "phone": "(415) 555-0165", "is_default": False},
        ],
        "payments": [
            {"brand": "Visa", "last4": "4242", "exp_month": 8, "exp_year": 2029,
             "holder": "Alice Johnson", "is_default": True},
            {"brand": "Mastercard", "last4": "5309", "exp_month": 11, "exp_year": 2028,
             "holder": "Alice Johnson", "is_default": False},
        ],
    },
    "bob.c@test.com": {
        "addresses": [
            {"label": "Home", "full_name": "Bob Chen", "line1": "1201 3rd Ave",
             "line2": "Unit 19", "city": "Seattle", "state": "WA",
             "zip_code": "98101", "phone": "(206) 555-0142", "is_default": True},
        ],
        "payments": [
            {"brand": "Visa", "last4": "1881", "exp_month": 3, "exp_year": 2028,
             "holder": "Bob Chen", "is_default": True},
        ],
    },
    "carol.d@test.com": {
        "addresses": [
            {"label": "Home", "full_name": "Carol Davis", "line1": "820 N Michigan Ave",
             "city": "Chicago", "state": "IL", "zip_code": "60611",
             "phone": "(312) 555-0188", "is_default": True},
        ],
        "payments": [
            {"brand": "American Express", "last4": "1005", "exp_month": 6,
             "exp_year": 2027, "holder": "Carol Davis", "is_default": True},
        ],
    },
    "david.k@test.com": {
        "addresses": [
            {"label": "Home", "full_name": "David Kim", "line1": "350 5th Ave",
             "line2": "Floor 22", "city": "New York", "state": "NY",
             "zip_code": "10118", "phone": "(646) 555-0117", "is_default": True},
        ],
        "payments": [
            {"brand": "Visa", "last4": "7321", "exp_month": 1, "exp_year": 2030,
             "holder": "David Kim", "is_default": True},
        ],
    },
}

# seeded cart contents: (user email, product handle, variant offset, quantity)
CART_SEED = [
    ("alice.j@test.com", "2021-free-flight-pinot-noir", 0, 2),
    ("alice.j@test.com", "golden-state-essentials-case", 0, 1),
    ("bob.c@test.com", "cabs-for-grabs-trio", 0, 1),
    ("bob.c@test.com", "2021-valanda-tempranillo", 0, 3),
    ("carol.d@test.com", "2023-closed-window-pinot-noir-willamette-valley", 0, 2),
    ("carol.d@test.com", "marthas-chardonnay-collection", 0, 1),
    ("david.k@test.com", "oh-so-sweet-case", 0, 1),
    ("david.k@test.com", "2022-della-flora-organic-cabernet-sauvignon", 0, 2),
]

# seeded order history: (email, handle, variant offset, qty, days ago, status)
ORDER_SEED = [
    ("alice.j@test.com", "2020-hayton-family-reserve-pinot-noir", 0, 3, 41, "Delivered"),
    ("alice.j@test.com", "oh-so-sweet-case", 0, 1, 12, "Shipped"),
    ("bob.c@test.com", "golden-state-essentials-case", 0, 1, 8, "Shipped"),
    ("bob.c@test.com", "2022-della-flora-organic-cabernet-sauvignon", 0, 6, 63, "Delivered"),
    ("carol.d@test.com", "cabs-for-grabs-trio", 0, 2, 27, "Delivered"),
    ("carol.d@test.com", "marthas-chardonnay-collection", 0, 1, 74, "Delivered"),
    ("david.k@test.com", "california-red-wine-odyssey", 0, 1, 5, "Processing"),
    ("david.k@test.com", "festive-vines-pumpkin-spice-chardonnay-6-pack", 0, 1, 38, "Delivered"),
]

SITE_TEXTS = {
    "free_shipping_rule": "Get FREE SHIPPING on orders with 6+ bottles",
    "wine_club_promo": "Wine Club: Enjoy 12 expertly-curated wines for just $99.99",
    "age_prompt_title": "Welcome!",
    "age_prompt_primary": ("We make it easy to discover new and exciting wines at "
                            "a great price, shipped directly to your door."),
    "age_prompt_secondary": "But first, please confirm a few things for us:",
    "age_prompt_age_question": "Are you 21 years of age or older?",
    "state_product_enforcement": "Some products cannot be delivered to your state.",
    "volume_limit_error": ("You have exceeded the wine volume limit imposed by your "
                            "state. %%state_agency%% allows wineries to sell "
                            "%%state_limit_amount%% bottles (750ml each) %%rule_frequency%%."),
    "dry_zip_code": "Your zip code is ineligible for delivery.",
    "state_not_permitted": "This merchant is not authorized to ship wine to this state.",
    "unknown_compliance_error": "Unknown compliance rule failed.",
    "age_prompt_error": "You must be over 21 or older to enter.",
}

HOME_SECTION_ORDER = [
    "hero", "benefits", "category_tiles", "featured", "wine_club_banner",
    "premium_tiles", "free_shipping_band", "martha_banner", "blog_cards",
    "shop_by_price",
]


def _load_source() -> dict:
    with open(SOURCE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def seed_collections(source: dict) -> None:
    if Collection.query.count() > 0:
        return
    for row in source["collections"]:
        db.session.add(Collection(
            handle=row["handle"],
            title=row["title"],
            description_html=row.get("description_html") or "",
            sort_order=row.get("sort_order") or "best-selling",
            position=row.get("position") or 0,
            in_nav=bool(row.get("in_nav")),
        ))
    db.session.commit()


def seed_products(source: dict) -> None:
    if Product.query.count() > 0:
        return
    for row in source["products"]:
        states = sorted({s for v in row["variants"] for s in (v.get("available_states") or [])})
        product = Product(
            handle=row["handle"],
            title=row["title"],
            product_type=row["product_type"],
            vendor=row.get("vendor") or "MacysWine Shop",
            description_html=row.get("description_html") or "",
            subheading=row.get("subheading") or "",
            color=row.get("color") or "",
            sweetness=row.get("sweetness") or "",
            country=row.get("country") or "",
            varietal=row.get("varietal") or "",
            vintage=row.get("vintage") or "",
            wine_category=row.get("wine_category") or "",
            region=row.get("region") or "",
            winery=row.get("winery") or "",
            abv=row.get("abv") or "",
            specs_html_rows=json.dumps(row.get("specs_html_rows") or []),
            awards=json.dumps(row.get("awards") or []),
            price=row.get("price") or 0.0,
            compare_at_price=row.get("compare_at_price") or 0.0,
            on_sale=bool(row.get("on_sale")),
            available=bool(row.get("available")),
            published_at=row.get("published_at") or "2026-09-22",
            rating_average=row.get("rating_average") or 0.0,
            rating_count=row.get("rating_count") or 0,
            rating_distribution=json.dumps(row.get("rating_distribution") or {}),
            recommended_percentage=row.get("recommended_percentage") or 0.0,
            available_states=json.dumps(states),
            nav_ribbon="SALE" if row.get("on_sale") else "",
            bestseller_rank=row.get("bestseller_rank") or 0,
            related_handles=json.dumps(row.get("related") or []),
        )
        db.session.add(product)
        db.session.flush()

        for pos, img in enumerate(row.get("images") or []):
            db.session.add(ProductImage(
                product_id=product.id,
                path="/static/images/" + img["path"],
                alt=img.get("alt") or row["title"],
                position=pos,
            ))

        for vrow in row["variants"]:
            variant = ProductVariant(
                product_id=product.id,
                upstream_id=str(vrow.get("upstream_id") or ""),
                title=vrow.get("title") or "Default Title",
                label=vrow.get("label") or vrow.get("title") or "Default Title",
                price=vrow.get("price") or 0.0,
                compare_at_price=vrow.get("compare_at_price") or 0.0,
                sku=vrow.get("sku") or "",
                available=bool(vrow.get("available")),
                bottle_count=0 if product.product_type == "Gift Card" else (vrow.get("bottle_count") or 1),
                position=vrow.get("position") or 0,
                available_states=json.dumps(vrow.get("available_states") or []),
                gift_amount=vrow.get("gift_amount") or 0.0,
                case_split="",
            )
            db.session.add(variant)
            db.session.flush()

            case = (row.get("case_contents") or {}).get(str(vrow.get("upstream_id")), {})
            if case:
                variant.case_split = case.get("split") or ""
                for num, b in enumerate(case.get("bottles") or [], start=1):
                    db.session.add(CaseBottle(
                        variant_id=variant.id,
                        number=num,
                        title=b.get("title") or "",
                        image_path="/static/images/" + (b.get("image_path") or ""),
                        winery=b.get("winery") or "",
                        varietal=b.get("varietal") or "",
                        year=b.get("year") or "",
                        type=b.get("type") or "Bottle",
                        abv=b.get("abv") or "",
                        country=b.get("country") or "",
                        region=b.get("region") or "",
                        price=b.get("price") or 0.0,
                    ))

        for rrow in row.get("reviews") or []:
            created = rrow.get("created_at") or ""
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                created_dt = MIRROR_DATE
            db.session.add(Review(
                product_id=product.id,
                rating=rrow.get("rating") or 5,
                title=rrow.get("title") or "",
                body=rrow.get("body") or "",
                customer_name=rrow.get("customer_name") or "Verified buyer",
                verified_buyer=bool(rrow.get("verified_buyer")),
                would_recommend=bool(rrow.get("would_recommend")),
                created_at=created_dt,
            ))
    db.session.commit()


def seed_collection_products(source: dict) -> None:
    if CollectionProduct.query.count() > 0:
        return
    by_handle = {p.handle: p.id for p in Product.query.all()}
    col_by_handle = {c.handle: c.id for c in Collection.query.all()}
    for row in source["collections"]:
        col_id = col_by_handle.get(row["handle"])
        if not col_id:
            continue
        for pos, handle in enumerate(row.get("products") or []):
            pid = by_handle.get(handle)
            if pid:
                db.session.add(CollectionProduct(
                    collection_id=col_id, product_id=pid, position=pos))
    db.session.commit()


def seed_blog(source: dict) -> None:
    if BlogArticle.query.count() > 0:
        return
    for row in source["blog_articles"]:
        db.session.add(BlogArticle(
            handle=row["handle"],
            title=row["title"],
            excerpt=row.get("excerpt") or "",
            author=row.get("author") or "Macy's Wine Shop",
            published_at=row.get("published_at") or "2026-09-22",
            image_path=row.get("image_path") or "",
            content_html=row.get("content_html") or "",
            reading_minutes=max(2, len(row.get("content_html") or "") // 2400 + 2),
        ))
    db.session.commit()


def seed_pages(source: dict) -> None:
    if StaticPage.query.count() > 0:
        return
    for row in source["pages"]:
        handle = row["handle"]
        for prefix in ("pages_", "products_"):
            if handle.startswith(prefix):
                handle = handle[len(prefix):]
                break
        db.session.add(StaticPage(
            handle=handle,
            title=row["title"],
            content_html=row.get("content_html") or "",
        ))
    db.session.commit()


def seed_state_disclosures(source: dict) -> None:
    if StateDisclosure.query.count() > 0:
        return
    for row in source.get("state_disclosures") or []:
        if not row.get("isActive", True):
            continue
        db.session.add(StateDisclosure(
            state=row.get("stateAbbr") or "",
            name=row.get("name") or "",
            body_html=row.get("bodyHtml") or row.get("body") or "",
            display_priority=row.get("displayPriority") or 0,
        ))
    db.session.commit()


def seed_home_sections(source: dict) -> None:
    if HomeSection.query.count() > 0:
        return
    home = source.get("home") or {}
    position = 0

    def add(kind, data):
        nonlocal position
        db.session.add(HomeSection(position=position, kind=kind,
                                    data_json=json.dumps(data, ensure_ascii=False)))
        position += 1

    # hero
    hero_slides = []
    for slide in (home.get("hero") or [])[:2]:
        texts = " ".join(slide.get("subheading") or [])
        heading = " ".join(slide.get("heading") or [])
        images = slide.get("images") or []
        hero_slides.append({
            "heading": heading,
            "subheading": texts.replace("  ", " "),
            "image": f"/static/images/home/hero-{len(hero_slides) + 1}.jpg" if images else "",
            "button_label": "Shop now" if "NEW30" in (slide.get("button_link") or "") else "Explore Clubs",
            "button_link": ("/collections/new-arrivals" if "NEW30" in (slide.get("button_link") or "")
                            else "/pages/wine-club"),
        })
    add("hero", {"kind": "hero", "slides": hero_slides})

    # benefits
    benefits = (home.get("benefits") or [])
    add("benefits", {"kind": "benefits", "items": [
        {"icon": f"/static/icons/benefit-{i + 1}.svg", "title": b.get("title") or "",
         "sub": b.get("sub") or ""}
        for i, b in enumerate(benefits)]})

    # category tiles
    tiles = (home.get("category_tiles") or [])
    add("category_tiles", {"kind": "category_tiles", "tiles": [
        {"label": t.get("label") or "", "link": t.get("link") or "#",
         "image": f"/static/images/home/tile-{i + 1}.png"}
        for i, t in enumerate(tiles)]})

    # featured tabs
    featured = home.get("featured") or {}
    tab_labels = [(slug, label) for slug, label in
                  zip(["popular-sets", "sommeliers-choice", "customer-favorites"],
                      featured.get("tabs") or ["Popular Sets", "Sommelier's Choice",
                                               "Customer Favorites"])]
    add("featured", {"kind": "featured", "title": "What we’re loving right now",
                     "tab_labels": tab_labels,
                     "tab_products": featured.get("tab_products") or {}})

    # wine club banner
    add("wine_club_banner", {
        "kind": "wine_club_banner",
        "heading": "Wine Club: Join Free & Get Exclusive Member Benefits",
        "body_1": "Get your first 12 bottles for $99.99 with free shipping!",
        "body_2": "No commitment or fees. Skip or cancel anytime.",
        "image": "/static/images/home/wine-club-box.jpg",
    })

    # premium tiles
    premium_texts = (home.get("premium_tiles") or {}).get("texts") or []
    premium_links = (home.get("premium_tiles") or {}).get("links") or []
    premium_labels = [t for t in premium_texts if t and t not in ("Shop Now",)][:3]
    add("premium_tiles", {
        "kind": "premium_tiles",
        "heading": "Premium wines at great prices",
        "tiles": [
            {"label": premium_labels[i] if i < len(premium_labels) else "",
             "link": premium_links[i] if i < len(premium_links) else "#",
             "image": f"/static/images/home/premium-{i + 1}.jpg"}
            for i in range(3)]})

    # free shipping band
    add("free_shipping_band", {"kind": "free_shipping_band"})

    # martha banner
    add("martha_banner", {
        "kind": "martha_banner",
        "heading": "Martha Stewart Wine Collection for Macy’s",
        "body_1": "Discover Martha Stewart's handpicked wine collection, exclusively at Macy's Wine Shop.",
        "body_2": "Winter Getaways, Wedding Worthy Wines or Best of Brunch. Quality bottles for any moment, from casual dinners to special celebrations.",
        "image": "/static/images/home/martha-stewart.jpg",
    })

    # blog cards
    add("blog_cards", {"kind": "blog_cards", "articles": [
        {"handle": b.get("link", "").rstrip("/").split("/")[-1],
         "title": b.get("title") or "",
         "excerpt": b.get("excerpt") or "",
         "image": ""}
        for b in (home.get("blog_cards") or [])[:3]]})

    # shop by price
    add("shop_by_price", {"kind": "shop_by_price", "tiles": [
        {"label": t.get("label") or "", "link": t.get("link") or "#"}
        for t in (home.get("shop_by_price") or [])]})

    db.session.commit()


def seed_site_texts() -> None:
    if SiteText.query.count() > 0:
        return
    for key, value in sorted(SITE_TEXTS.items()):
        db.session.add(SiteText(key=key, value=value))
    db.session.commit()


def seed_benchmark_users() -> None:
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    users = {}
    for row in BENCHMARK_USERS:
        user = User(
            email=row["email"],
            username=row["username"],
            display_name=row["display_name"],
            password_hash=stable_password_hash(PASSWORD),
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone=row["phone"],
            created_at=MIRROR_DATE - timedelta(days=210),
        )
        db.session.add(user)
        users[row["email"]] = user
    db.session.flush()

    for email, profile in USER_PROFILES.items():
        user = users[email]
        for addr in profile["addresses"]:
            db.session.add(Address(user_id=user.id, **addr,
                                   created_at=MIRROR_DATE - timedelta(days=200)))
        for pay in profile["payments"]:
            db.session.add(PaymentMethod(user_id=user.id, **pay,
                                         created_at=MIRROR_DATE - timedelta(days=200)))
    db.session.commit()
    seed_user_activity()
    seed_carts()
    seed_newsletter()


def seed_user_activity() -> None:
    if Order.query.count() > 0:
        return
    by_email = {u.email: u for u in User.query.all()}
    handle_index = {}
    for p in Product.query.order_by(Product.id).all():
        handle_index[p.handle] = p
    order_seq = 1042
    for email, handle, voff, qty, days_ago, status in ORDER_SEED:
        user = by_email.get(email)
        product = handle_index.get(handle)
        if not user or not product:
            continue
        variants = sorted(product.variants, key=lambda v: v.position)
        variant = variants[min(voff, len(variants) - 1)]
        address = next((a for a in user.addresses if a.is_default), None)
        if not address:
            continue
        bottles = variant.bottle_count * qty
        subtotal = round(variant.price * qty, 2)
        shipping = 0.0 if bottles >= 6 else 14.95
        total = round(subtotal + shipping + 2.95, 2)
        order = Order(
            order_number=f"MWS{order_seq}",
            user_id=user.id,
            email=email,
            status=status,
            ship_to_name=address.full_name,
            address_line1=address.line1,
            address_line2=address.line2 or "",
            city=address.city,
            state=address.state,
            zip_code=address.zip_code,
            phone=address.phone or "",
            payment_label=(user.payment_methods[0].brand + " ending in "
                           + user.payment_methods[0].last4)
            if user.payment_methods else "Visa ending in 4242",
            subtotal=subtotal,
            shipping=shipping,
            processing=2.95,
            total=total,
            bottle_count=bottles,
            created_at=MIRROR_DATE - timedelta(days=days_ago),
        )
        db.session.add(order)
        db.session.add(OrderItem(
            order=order,
            variant_id=variant.id,
            product_handle=product.handle,
            product_title=product.title,
            variant_title=variant.title,
            unit_price=variant.price,
            quantity=qty,
            bottle_count=variant.bottle_count,
        ))
        order_seq += 1
    db.session.commit()


def seed_carts() -> None:
    if CartItem.query.count() > 0:
        return
    by_email = {u.email: u for u in User.query.all()}
    handle_index = {p.handle: p for p in Product.query.all()}
    for email, handle, voff, qty in CART_SEED:
        user = by_email.get(email)
        product = handle_index.get(handle)
        if not user or not product:
            continue
        variants = sorted(product.variants, key=lambda v: v.position)
        variant = variants[min(voff, len(variants) - 1)]
        if not variant.shippable_to(user.addresses[0].state if user.addresses else ""):
            continue
        db.session.add(CartItem(user_id=user.id, variant_id=variant.id, quantity=qty))
    db.session.commit()


def seed_newsletter() -> None:
    if NewsletterSubscriber.query.count() > 0:
        return
    for email in ["wine.lover@example.com", "cellar.notes@example.org"]:
        db.session.add(NewsletterSubscriber(email=email))
    db.session.commit()


def seed_database() -> None:
    """Materialize the whole catalog. Idempotent at the table level."""
    source = _load_source()
    seed_site_texts()
    seed_collections(source)
    seed_products(source)
    seed_collection_products(source)
    seed_blog(source)
    seed_pages(source)
    seed_state_disclosures(source)
    seed_home_sections(source)


def build_seed_database() -> str:
    """Regenerate instance_seed/macys_wine_shop.db deterministically."""
    import shutil

    base = os.path.dirname(os.path.abspath(__file__))
    instance_dir = os.path.join(base, "instance")
    seed_dir = os.path.join(base, "instance_seed")
    shutil.rmtree(instance_dir, ignore_errors=True)
    os.makedirs(instance_dir, exist_ok=True)
    os.makedirs(seed_dir, exist_ok=True)

    from app import app as flask_app, db

    with flask_app.app_context():
        db.session.remove()
        db.engine.dispose()
        db.create_all()
        source = _load_source()
        seed_site_texts()
        seed_collections(source)
        seed_products(source)
        seed_collection_products(source)
        seed_blog(source)
        seed_pages(source)
        seed_state_disclosures(source)
        seed_home_sections(source)
        seed_benchmark_users()
    seed_path = os.path.join(seed_dir, "macys_wine_shop.db")
    if os.path.exists(seed_path):
        os.unlink(seed_path)
    shutil.copyfile(os.path.join(instance_dir, "macys_wine_shop.db"), seed_path)
    return seed_path


def main() -> None:
    import sqlite3

    seed_path = build_seed_database()
    connection = sqlite3.connect(f"file:{seed_path}?mode=ro", uri=True)
    try:
        counts = {}
        for table in ("products", "product_variants", "collections",
                      "collection_products", "case_bottles", "reviews",
                      "blog_articles", "static_pages", "users", "orders",
                      "cart_items", "state_disclosures", "home_sections",
                      "product_images"):
            counts[table] = connection.execute(
                f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        connection.close()
    print(f"[seed] database generated: {seed_path}")
    print("[seed] " + " ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
