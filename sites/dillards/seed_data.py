"""Deterministic seed builder for the Dillard's mirror.

Reads the tracked, upstream-sourced `source_data.json` (catalog, brands, stores,
homepage blocks, static page copy — with the captured review rows and per-star
snapshots embedded under `product_reviews`) and materialises
`instance_seed/dillards.db`.
Run at image build time (see the Dockerfile) so the seed is reproducible from
tracked inputs:

    WEBSYN_SKIP_BOOTSTRAP=1 PYTHONHASHSEED=0 python3 seed_data.py

Benchmark fixtures (users, orders, wish lists, card accounts, registries)
below are synthetic and reference real seeded products; every date is pinned
relative to MIRROR_DATE. Logical content is identical on every build and the
schema objects are created in a fixed order, so the seed file is byte-stable
across builds on the same environment (see the index re-creation below).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

import bcrypt as _bcrypt  # noqa: E402
from sqlalchemy import text as sa_text  # noqa: E402

from app import (  # noqa: E402
    Address, Brand, CardAccount, CardPayment, CardTransaction, CartItem,
    Category, HomeBlock, Order, OrderItem, PaymentMethod, Product,
    RatingBreak, Registry, RegistryItem, ReturnRequest, Review, StaticPage,
    Store, User, Variant, WishlistItem, app, db,
)

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data.json"
IMAGES = BASE_DIR / "static" / "images"
INSTANCE_SEED = BASE_DIR / "instance_seed"
DB_FILE = BASE_DIR / "instance" / "dillards.db"

MIRROR_DATE = datetime(2026, 9, 22)

# The seed must be byte-reproducible from tracked inputs, so the bcrypt digest
# is fixed here rather than salted per build (CONTRIBUTING.md, "Don't
# hard-code secrets" - benchmark demo credentials).
BENCHMARK_PASSWORD = "TestPass123!"
BENCHMARK_DIGEST = "$2b$12$LcyOgGlRQFL3xDICBkv5F.mETZ90roASWr9eCsTHqCUo1npPrutTG"

BENCHMARK_USERS = [
    {"email": "alice.j@test.com", "first": "Alice", "last": "Johnson", "phone": "(501) 555-0147", "cardholder": True},
    {"email": "bob.c@test.com", "first": "Bob", "last": "Chen", "phone": "(972) 555-0183", "cardholder": True},
    {"email": "carol.d@test.com", "first": "Carol", "last": "Davis", "phone": "(602) 555-0126", "cardholder": True},
    {"email": "david.k@test.com", "first": "David", "last": "Kim", "phone": "(614) 555-0198", "cardholder": True},
]


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value


def load_source() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def load_reviews(source: dict) -> dict:
    """Captured review rows ride inside the tracked source_data.json."""
    return source.get("product_reviews", {})


def image_exists(rel: str) -> bool:
    return (IMAGES / rel).is_file() and (IMAGES / rel).stat().st_size > 0


def as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def days_ago(n: int) -> datetime:
    return MIRROR_DATE - timedelta(days=n)


# ---------------------------------------------------------------------------
# Catalog seeding
# ---------------------------------------------------------------------------

def seed_catalog(data: dict, reviews_by_pid: dict) -> dict:
    """Seed categories, brands, products, variants, reviews, stores, home
    blocks, and static pages. Returns a lookup {pid: Product}."""
    for row in data["categories"]:
        db.session.add(Category(slug=row["slug"], name=row["name"],
                                nav_label=row.get("nav_label", row["name"]),
                                kind=row["kind"]))
    for row in data["subcategories"]:
        top = row["top"]
        name = row["name"]
        possessive = {
            "women": "Women's", "men": "Men's", "juniors": "Juniors'",
        }
        display = name
        if top in possessive and not name.lower().startswith(("women", "men", "junior")):
            display = f"{possessive[top]} {name}"
        elif top == "shoes" and name in ("Women's Shoes", "Men's Shoes", "Kids' Shoes"):
            display = name
        db.session.add(Category(slug=row["slug"], name=display,
                                 nav_label=name, kind="sub"))
    db.session.flush()

    brand_map = {}
    for row in data["brands"]:
        name = row["name"]
        brand = Brand(name=name, slug=slugify(name), about=row.get("about", ""),
                      exclusive=bool(row.get("exclusive")),
                      letter=(name[:1].upper() if name and name[0].isalpha() else "#"))
        db.session.add(brand)
        brand_map[name] = brand
    db.session.flush()

    top_of = {sub["slug"]: sub["top"] for sub in data["subcategories"]}
    category_name = {sub["slug"]: sub["name"] for sub in data["subcategories"]}

    product_map = {}
    per_category_position = {}
    for row in data["products"]:
        category_slug = row["category"]
        if category_slug not in top_of:
            continue
        brand = brand_map.get(row["brand"])
        if brand is None:
            continue
        pid = row["id"]
        name = row["name"]
        short_name = name
        if name.startswith(brand.name + " "):
            short_name = name[len(brand.name) + 1:]
        position = per_category_position.get(category_slug, 0)
        per_category_position[category_slug] = position + 1
        product = Product(
            pid=pid,
            slug=row["slug"],
            name=name,
            short_name=short_name,
            brand_id=brand.id,
            category_slug=category_slug,
            top_slug=top_of[category_slug],
            description=re.sub(r"\s+", " ", row.get("description") or "").strip(),
            more_details=re.sub(r"\s+", " ", row.get("more_details") or "").strip(),
            item_number=row.get("item_number") or "",
            sku_root=row.get("sku_root") or "",
            rating=float(row["rating"]) if row.get("rating") else None,
            review_count=as_int(row.get("review_count")) or 0,
            exclusive=bool(row.get("exclusive")),
            free_shipping=(float(row.get("low_price") or 0) >= 99),
            is_new_arrival=(position % 4 == 0),
            main_image="",
            position=position,
        )
        db.session.add(product)
        db.session.flush()
        product_map[pid] = product

        # variants: one row per scraped variant, but only images that exist
        seen_variants = set()
        for v in row.get("variants", []):
            key = (v.get("size") or "", v.get("color") or "")
            if key in seen_variants:
                continue
            seen_variants.add(key)
            db.session.add(Variant(
                product_id=product.id,
                sku=str(v.get("sku") or ""),
                size=v.get("size") or "",
                color=v.get("color") or "",
                nrf_color=v.get("nrf_color") or "",
                price=float(v.get("price") or 0),
                was_price=float(v["was_price"]) if v.get("was_price") else None,
                image="",
            ))
        # image assignment: one file per distinct color
        colors = []
        for v in row.get("variants", []):
            color = v.get("color") or ""
            if color and color not in [c for c, _ in colors]:
                colors.append((color, v.get("image")))
        if not colors:
            colors = [("", row.get("main_image"))]
        main_image = ""
        for variant in Variant.query.filter_by(product_id=product.id).order_by(Variant.id).all():
            color = variant.color
            idx = next((i for i, (c, _) in enumerate(colors[:5]) if c == color), 0)
            rel = f"products/{pid}_{idx}.jpg"
            if image_exists(rel):
                variant.image = rel
                if not main_image:
                    main_image = rel
        product.main_image = main_image

    db.session.flush()

    # reviews + rating snapshot
    for pid, review_data in reviews_by_pid.items():
        product = product_map.get(pid)
        if product is None:
            continue
        snapshot = review_data.get("snapshot") or {}
        for stars in (5, 4, 3, 2, 1):
            count = int(snapshot.get(str(stars), snapshot.get(stars, 0)) or 0)
            db.session.add(RatingBreak(product_id=product.id, stars=stars, count=count))
        for position, row in enumerate(review_data.get("reviews", [])):
            if not row.get("rating"):
                continue
            db.session.add(Review(
                product_id=product.id,
                author=row.get("author") or "Anonymous",
                title=row.get("title") or "",
                body=row.get("body") or "",
                rating=int(row["rating"]),
                date_label=row.get("date") or "",
                position=position,
            ))

    # stores
    for row in data["stores"]:
        db.session.add(Store(
            identifier=row["identifier"], store_name=row.get("storeName", ""),
            city=row.get("city", ""), state=row.get("state", ""), state_abrev=row.get("state_abrev", ""),
            zipcode=row.get("zipcode", ""), address1=row.get("address1", ""),
            phone=row.get("phone", ""), latitude=row.get("latitude", ""),
            longitude=row.get("longitude", ""),
        ))

    # homepage blocks
    position = 0
    for row in data["home_hero"]:
        db.session.add(HomeBlock(block_type="hero", position=position, data=json.dumps(row)))
        position += 1
    for section in data["home_tiles"]:
        db.session.add(HomeBlock(block_type="tile", position=position,
                                 data=json.dumps({"group_start": True, "heading": section["heading"],
                                                  "subtitle": section.get("subtitle")})))
        position += 1
        for tile in section["tiles"]:
            db.session.add(HomeBlock(block_type="tile", position=position,
                                     data=json.dumps({"tile": True, **tile})))
            position += 1
    # "SHOP NEW ARRIVALS" rail: curated from the seeded catalog (the newest
    # arrivals), mirroring the upstream homepage's NEW ARRIVALS THIS WEEK rail.
    db.session.add(HomeBlock(block_type="product_rail", position=position,
                             data=json.dumps({"heading": "SHOP NEW ARRIVALS"})))

    # static pages
    for slug, payload in data["static_pages"].items():
        db.session.add(StaticPage(slug=slug, title=slug.replace("_", " ").title(),
                                  body=json.dumps(payload)))

    return product_map


# ---------------------------------------------------------------------------
# Benchmark fixtures (synthetic, referencing real seeded products)
# ---------------------------------------------------------------------------

def pick(product_map, pid):
    product = product_map.get(pid)
    if product is None:
        raise KeyError(f"fixture references unknown product {pid}")
    return product


def first_variant(product, size_index=0):
    return product.variants[size_index]


def seed_benchmark_users(product_map) -> None:
    if not _bcrypt.checkpw(BENCHMARK_PASSWORD.encode("utf-8"), BENCHMARK_DIGEST.encode("ascii")):
        raise SystemExit("benchmark digest does not match the documented password")

    users = {}
    for spec in BENCHMARK_USERS:
        user = User(email=spec["email"], password_hash=BENCHMARK_DIGEST,
                    first_name=spec["first"], last_name=spec["last"],
                    phone=spec["phone"], is_cardholder=spec["cardholder"])
        db.session.add(user)
        users[spec["email"]] = user
    db.session.flush()

    # -- addresses ---------------------------------------------------------
    addresses = {}
    address_rows = [
        ("alice.j@test.com", "Home", "4120 Cantrell Road", "Apt 6B", "Little Rock", "AR", "72202", "(501) 555-0147", True),
        ("alice.j@test.com", "Office", "211 West Markham Street", "Suite 900", "Little Rock", "AR", "72201", "(501) 555-0147", False),
        ("bob.c@test.com", "Home", "5802 Legacy Drive", "", "Plano", "TX", "75024", "(972) 555-0183", True),
        ("carol.d@test.com", "Home", "2317 East Camelback Road", "", "Phoenix", "AZ", "85016", "(602) 555-0126", True),
        ("david.k@test.com", "Home", "755 North High Street", "Unit 12", "Columbus", "OH", "43215", "(614) 555-0198", True),
    ]
    for email, label, line1, line2, city, state, zipcode, phone, is_default in address_rows:
        address = Address(user_id=users[email].id, label=label, line1=line1, line2=line2,
                          city=city, state=state, zipcode=zipcode, phone=phone,
                          is_default_shipping=is_default)
        db.session.add(address)
        addresses[email] = address
    db.session.flush()

    # -- payment methods ----------------------------------------------------
    payment_rows = [
        ("alice.j@test.com", "Dillard's Credit Card", "1088", True),
        ("alice.j@test.com", "Visa", "4242", False),
        ("bob.c@test.com", "Dillard's Credit Card", "2201", True),
        ("carol.d@test.com", "Dillard's Credit Card", "7102", True),
        ("carol.d@test.com", "Mastercard", "5309", False),
        ("david.k@test.com", "Dillard's Credit Card", "6621", True),
    ]
    payments = {}
    for email, kind, last4, is_default in payment_rows:
        method = PaymentMethod(user_id=users[email].id, kind=kind, last4=last4,
                               is_default=is_default)
        db.session.add(method)
        payments[(email, last4)] = method
    db.session.flush()

    # -- card accounts + activity -------------------------------------------
    card_rows = [
        ("alice.j@test.com", "1088", 2500.0, 842.36, 3150, 35.00, days_ago(6), days_ago(8), 3850.0),
        ("bob.c@test.com", "2201", 1800.0, 214.88, 1204, 25.00, days_ago(12), days_ago(4), 1430.0),
        ("carol.d@test.com", "7102", 3500.0, 1129.40, 4415, 45.00, days_ago(9), days_ago(15), 2410.0),
        ("david.k@test.com", "6621", 1500.0, 96.15, 620, 25.00, days_ago(3), days_ago(20), 885.0),
    ]
    card_accounts = {}
    for email, last4, limit, balance, points, min_pay, stmt_date, due_date, spend in card_rows:
        account = CardAccount(user_id=users[email].id, last4=last4,
                              card_kind="Dillard's Credit Card",
                              credit_limit=limit, balance=balance, points=points,
                              minimum_payment=min_pay, statement_date=stmt_date,
                              payment_due_date=due_date)
        db.session.add(account)
        card_accounts[email] = account
    db.session.flush()

    txn_rows = [
        ("alice.j@test.com", days_ago(28), "Dillards.com order D2608250811", 208.00, 416),
        ("alice.j@test.com", days_ago(18), "Park Plaza Store - Shoes", 149.00, 298),
        ("alice.j@test.com", days_ago(11), "Dillards.com order D2609110402", 395.00, 790),
        ("alice.j@test.com", days_ago(4), "The Gateway Store - Handbags", 259.00, 518),
        ("bob.c@test.com", days_ago(24), "Stonebriar Centre Store - Mens", 187.50, 375),
        ("bob.c@test.com", days_ago(9), "Dillards.com order D2609130344", 142.44, 285),
        ("carol.d@test.com", days_ago(26), "Biltmore Fashion Park Store", 316.20, 632),
        ("carol.d@test.com", days_ago(13), "Dillards.com order D2609090873", 254.00, 508),
        ("david.k@test.com", days_ago(21), "Easton Town Center Store - Accessories", 415.00, 830),
    ]
    for email, posted, description, amount, points in txn_rows:
        db.session.add(CardTransaction(card_account_id=card_accounts[email].id,
                                       posted=posted, description=description,
                                       amount=amount, points=points))
    payment_rows_history = [
        ("alice.j@test.com", days_ago(20), 150.00, "Bank Draft", "PMT-260902-8301"),
        ("bob.c@test.com", days_ago(16), 100.00, "Bank Draft", "PMT-260906-9117"),
        ("carol.d@test.com", days_ago(19), 250.00, "Debit Card", "PMT-260903-4420"),
        ("david.k@test.com", days_ago(22), 75.00, "Bank Draft", "PMT-260831-5602"),
    ]
    for email, posted, amount, method, confirmation in payment_rows_history:
        db.session.add(CardPayment(card_account_id=card_accounts[email].id,
                                   posted=posted, amount=amount, method=method,
                                   confirmation=confirmation))
    db.session.flush()

    # -- orders ---------------------------------------------------------------
    order_specs = [
        # (email, number, days_ago, status, tracking, carrier, items[(pid, size_idx, qty)], payment kind)
        ("alice.j@test.com", "D2608250811", 28, "Delivered", "1Z999AA10123456784", "UPS",
         [("520620253", 3, 1), ("520895844", 0, 1)], "Dillard's Credit Card"),
        ("alice.j@test.com", "D2609110402", 11, "In Transit", "1Z999AA10987654321", "FedEx",
         [("507141034", 0, 1), ("504158826", 0, 1)], "Dillard's Credit Card"),
        ("alice.j@test.com", "D2609200733", 2, "Processing", "", "",
         [("504228059", 0, 1)], "Visa"),
        ("bob.c@test.com", "D2609030221", 19, "Delivered", "1Z999AA11223344556", "UPS",
         [("501116145", 1, 2), ("519099341", 0, 1)], "Dillard's Credit Card"),
        ("bob.c@test.com", "D2609150455", 7, "Cancelled", "", "",
         [("509640715", 0, 1)], "Dillard's Credit Card"),
        ("carol.d@test.com", "D2609090873", 13, "Delivered", "1Z999AA12776655443", "FedEx",
         [("522223288", 0, 1), ("517436763", 0, 1)], "Dillard's Credit Card"),
        ("carol.d@test.com", "D2609180298", 4, "In Transit", "1Z999AA13456677889", "UPS",
         [("512361758", 0, 1), ("519897303", 0, 1)], "Mastercard"),
        ("david.k@test.com", "D2609010164", 21, "Delivered", "1Z999AA14334455667", "UPS",
         [("504158826", 1, 1), ("505881070", 0, 1)], "Dillard's Credit Card"),
    ]
    orders = []
    for email, number, placed, status, tracking, carrier, items, pay_kind in order_specs:
        user = users[email]
        address = addresses[email]
        subtotal = 0.0
        for pid, size_idx, qty in items:
            product = pick(product_map, pid)
            variant = product.variants[size_idx] if len(product.variants) > size_idx else product.variants[0]
            subtotal += variant.price * qty
        shipping = 0.0 if subtotal >= 150 else 8.95
        tax = round(subtotal * 0.065, 2)
        total = round(subtotal + shipping + tax, 2)
        last4 = "1088" if email == "alice.j@test.com" else (
            "2201" if email == "bob.c@test.com" else ("7102" if email == "carol.d@test.com" else "6621"))
        order = Order(user_id=user.id, order_number=number,
                      placed_at=days_ago(placed), status=status,
                      ship_to=f"{address.line1}, {address.city}, {address.state} {address.zipcode}",
                      ship_method="Standard", payment_last4=last4,
                      payment_kind=pay_kind, subtotal=round(subtotal, 2),
                      shipping_total=shipping, tax=tax, total=total,
                      tracking_number=tracking, carrier=carrier)
        db.session.add(order)
        db.session.flush()
        for pid, size_idx, qty in items:
            product = pick(product_map, pid)
            variant = product.variants[size_idx] if len(product.variants) > size_idx else product.variants[0]
            db.session.add(OrderItem(order_id=order.id, variant_id=variant.id,
                                     product_name=product.full_name,
                                     size=variant.size, color=variant.color,
                                     quantity=qty, price=variant.price))
        orders.append(order)
    db.session.flush()

    # -- returns ---------------------------------------------------------------
    alice_second = orders[1]
    item = alice_second.items[0]
    db.session.add(ReturnRequest(
        user_id=users["alice.j@test.com"].id, order_id=alice_second.id,
        order_item_id=item.id, reason="Did not like the color or style",
        method="Return by Mail", status="In Transit",
        created=days_ago(5), credit_issued=round(item.price * item.quantity, 2)))

    # -- wish lists -------------------------------------------------------------
    wishlist_specs = {
        "alice.j@test.com": ["520912513", "504158826", "519897303", "517436763"],
        "bob.c@test.com": ["501116145", "518854263", "514471740"],
        "carol.d@test.com": ["521808927", "512361758", "519502779", "504228059", "515684884"],
        "david.k@test.com": ["504158826", "505881070"],
    }
    for email, pids in wishlist_specs.items():
        for pid in pids:
            product = pick(product_map, pid)
            db.session.add(WishlistItem(user_id=users[email].id, product_id=product.id))

    # -- cart items ---------------------------------------------------------------
    cart_specs = {
        "alice.j@test.com": [("520620253", 5, 1), ("507141034", 0, 2)],
        "bob.c@test.com": [("501116145", 2, 1)],
        "carol.d@test.com": [("517436763", 0, 1), ("519897303", 1, 1)],
        "david.k@test.com": [("504158826", 0, 1)],
    }
    for email, rows in cart_specs.items():
        for pid, size_idx, qty in rows:
            product = pick(product_map, pid)
            variant = product.variants[size_idx] if len(product.variants) > size_idx else product.variants[0]
            db.session.add(CartItem(user_id=users[email].id, variant_id=variant.id, quantity=qty))

    # -- registries ---------------------------------------------------------------
    registry_specs = [
        # (number, first, last, co_first, kind, event days ahead, email or None)
        ("114800237", "Alice", "Johnson", "Michael", "wedding", 74, "alice.j@test.com"),
        ("114802551", "Carol", "Davis", "", "baby", 38, "carol.d@test.com"),
        ("114797802", "Emma", "Walker", "Jacob", "wedding", 120, None),
        ("114810426", "Olivia", "Chen", "", "baby", 55, None),
        ("114815098", "Sophia", "Brooks", "Ethan", "wedding", 26, None),
        ("114823710", "Nathan", "Cole", "", "gift", 12, None),
    ]
    registry_item_pids = {
        "114800237": ["507141034", "517436763", "519897303", "505881070", "504158826"],
        "114802551": ["522223288", "517436763"],
        "114797802": ["507141034", "517436763", "505881070"],
        "114810426": ["522223288"],
        "114815098": ["504228059", "519897303"],
        "114823710": ["505881070"],
    }
    purchased_map = {("114800237", "517436763"): 1, ("114815098", "504228059"): 1}
    for number, first, last, co_first, kind, event_days, email in registry_specs:
        registry = Registry(registry_number=number, owner_first=first, owner_last=last,
                            co_owner_first=co_first, co_owner_last="",
                            kind=kind, event_date=MIRROR_DATE + timedelta(days=event_days),
                            user_id=users[email].id if email else None)
        db.session.add(registry)
        db.session.flush()
        for pid in registry_item_pids.get(number, []):
            product = pick(product_map, pid)
            db.session.add(RegistryItem(registry_id=registry.id, product_id=product.id,
                                        quantity=1, purchased=purchased_map.get((number, pid), 0),
                                        priority="must-have"))
    db.session.commit()


# ---------------------------------------------------------------------------
# Build the seed database
# ---------------------------------------------------------------------------

def build_seed_database() -> None:
    INSTANCE_SEED.mkdir(parents=True, exist_ok=True)
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    if DB_FILE.exists():
        DB_FILE.unlink()
    data = load_source()
    reviews = load_reviews(data)
    with app.app_context():
        db.drop_all()
        db.create_all()
        # SQLAlchemy emits CREATE INDEX for a multi-index table in
        # set-iteration order, which is not stable across processes; recreate
        # the products indexes in a fixed order so the sqlite_schema rows (and
        # the seed bytes) do not depend on the building process.
        for stmt in (
            "DROP INDEX IF EXISTS ix_products_category_slug",
            "DROP INDEX IF EXISTS ix_products_top_slug",
            "DROP INDEX IF EXISTS ix_products_pid",
            "CREATE INDEX ix_products_category_slug ON products (category_slug)",
            "CREATE INDEX ix_products_top_slug ON products (top_slug)",
            "CREATE INDEX ix_products_pid ON products (pid)",
        ):
            db.session.execute(sa_text(stmt))
        db.session.commit()
        product_map = seed_catalog(data, reviews)
        seed_benchmark_users(product_map)
        db.session.commit()
        # create_all hands the recreated indexes whatever pages the dropped
        # ones freed, and that freelist order varies per build; VACUUM rewrites
        # the whole file from the committed schema + rows so the final page
        # layout (and the file bytes) are a pure function of the content.
        db.session.execute(sa_text("VACUUM"))
        counts = {
            "categories": Category.query.count(),
            "brands": Brand.query.count(),
            "products": Product.query.count(),
            "variants": Variant.query.count(),
            "reviews": Review.query.count(),
            "rating breaks": RatingBreak.query.count(),
            "stores": Store.query.count(),
            "home blocks": HomeBlock.query.count(),
            "static pages": StaticPage.query.count(),
            "users": User.query.count(),
            "orders": Order.query.count(),
            "order items": OrderItem.query.count(),
            "registries": Registry.query.count(),
            "registry items": RegistryItem.query.count(),
            "wish list items": WishlistItem.query.count(),
            "cart items": CartItem.query.count(),
            "card accounts": CardAccount.query.count(),
            "card transactions": CardTransaction.query.count(),
            "card payments": CardPayment.query.count(),
            "return requests": ReturnRequest.query.count(),
        }
    shutil.copyfile(DB_FILE, INSTANCE_SEED / "dillards.db")
    for label, value in counts.items():
        print(f"  {label:<18} {value}")
    print(f"Seed database written to {INSTANCE_SEED / 'dillards.db'}")


if __name__ == "__main__":
    build_seed_database()
