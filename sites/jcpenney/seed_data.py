"""Deterministic seed builder for the JCPenney mirror.

Reads the tracked, upstream-sourced source_data.json (catalog, categories,
stores, coupons, customer-service pages) and materialises the runtime DB.
Called at image build time (see the Dockerfile) and defensively at boot;
every seed function early-returns when its data already exists so
/reset/<jcpenney> stays byte-identical.

    WEBSYN_SKIP_BOOTSTRAP=1 PYTHONHASHSEED=0 python3 seed_data.py

Benchmark fixtures (users, addresses, cards, orders, carts, wish lists,
reward events) are synthetic and reference real seeded products; every date
is pinned relative to MIRROR_DATE so the seed is byte-stable across builds.
"""
from __future__ import annotations

import os

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

import json  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402

# Determinism pin: every date written into the seed derives from this single
# constant (the upstream snapshot date), so seed_data.py never depends on
# runtime drift in app.py to stay byte-stable across builds.
MIRROR_DATE = datetime(2026, 9, 22)

from app import (  # noqa: E402
    Address,
    CartItem,
    Category,
    Coupon,
    Order,
    OrderItem,
    PaymentMethod,
    Product,
    ProductColor,
    ProductImage,
    Review,
    RewardEvent,
    StaticPage,
    Store,
    User,
    WishlistItem,
    app,
    db,
    slugify,
    stable_password_hash,
)

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data.json"
INSTANCE_SEED = BASE_DIR / "instance_seed"

BENCHMARK_PASSWORD = "TestPass123!"
BENCHMARK_USERS = [
    {"email": "alice.j@test.com", "first": "Alice", "last": "Johnson",
     "phone": "(206) 555-0147", "rewards_member": True, "rewards_points": 1840,
     "rewards_tier": "Rewards Access"},
    {"email": "bob.c@test.com", "first": "Bob", "last": "Chen",
     "phone": "(415) 555-0183", "rewards_member": True, "rewards_points": 920,
     "rewards_tier": "Rewards Access"},
    {"email": "carol.d@test.com", "first": "Carol", "last": "Davis",
     "phone": "(312) 555-0126", "rewards_member": False, "rewards_points": 0,
     "rewards_tier": ""},
    {"email": "david.k@test.com", "first": "David", "last": "Kim",
     "phone": "(614) 555-0198", "rewards_member": True, "rewards_points": 310,
     "rewards_tier": "Member"},
]


def load_source() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def seed_database() -> None:
    if Category.query.count() > 0 or Product.query.count() > 0:
        return
    source = load_source()

    # ---- categories -------------------------------------------------- #
    category_rows: dict[str, Category] = {}
    for row in source.get("categories", []):
        parent = None
        if row["slug"] != row["department_slug"]:
            parent = category_rows.get(row["department_slug"])
        category = Category(
            slug=row["slug"], name=row["name"],
            department_slug=row["department_slug"],
            parent_id=parent.id if parent else None,
            is_department=row["is_department"],
            sort=row["sort"], hero_image=row.get("hero_image", ""),
        )
        db.session.add(category)
        # flush per row so children can link to their department's assigned id
        db.session.flush()
        category_rows[row["slug"]] = category

    # ---- products ---------------------------------------------------- #
    sort_index = 0
    for row in source.get("products", []):
        category = category_rows.get(row["category_slug"])
        product = Product(
            ppid=row["ppid"], slug=row["slug"] or slugify(row["name"]),
            name=row["name"], brand=row["brand"],
            brand_slug=slugify(row["brand"]),
            description=row.get("description", ""),
            bullets_json=json.dumps([{"description": b} for b in row.get("bullets", [])],
                                    ensure_ascii=False),
            price=row["price"], price_max=row.get("price_max") or row["price"],
            original_price=row["original_price"],
            original_price_max=row.get("original_price_max") or row["original_price"],
            coupon_code=row.get("coupon_code", ""),
            rating=row.get("rating", 0.0), review_count=row.get("review_count", 0),
            question_count=row.get("question_count", 0),
            badges_json=json.dumps(row.get("badges", []), ensure_ascii=False),
            item_type=row.get("item_type", ""), product_type=row.get("product_type", ""),
            occasion=row.get("occasion", ""), fiber_content=row.get("fiber_content", ""),
            care=row.get("care", ""), material=row.get("material", ""),
            size_range=row.get("size_range", ""),
            category_id=category.id if category else None,
            is_clearance=row.get("is_clearance", False),
            is_new=row.get("is_new", False),
            sold_recently=row.get("sold_recently", 0),
            specifications_json=json.dumps(row.get("specifications", []), ensure_ascii=False),
            sort=sort_index,
        )
        db.session.add(product)
        db.session.flush()
        for index, image in enumerate(row.get("images", [])[:6]):
            db.session.add(ProductImage(
                product_id=product.id, filename=image["filename"],
                alt=image.get("alt", row["name"]),
                is_primary=index == 0, sort=index))
        for index, color in enumerate(row.get("colors", [])):
            sizes = [
                {"size": s["size"], "available": bool(s.get("available"))}
                for s in color.get("sizes", []) if s.get("size")
            ]
            db.session.add(ProductColor(
                product_id=product.id, color=color["color"],
                color_family=color.get("color_family", color["color"]),
                swatch_file=color.get("swatch_file", ""), sort=index,
                sizes_json=json.dumps(sizes, ensure_ascii=False)))
        for review in row.get("reviews", []):
            date_text = review.get("date") or ""
            try:
                review_date = datetime.fromisoformat(date_text.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                review_date = MIRROR_DATE - timedelta(days=14)
            db.session.add(Review(
                product_id=product.id,
                author=review.get("author", "Anonymous")[:78],
                rating=review.get("rating", 5), headline=(review.get("headline") or "")[:158],
                body=review.get("body") or "", review_date=review_date,
                verified=True))
        sort_index += 1
    db.session.flush()

    # ---- stores -------------------------------------------------------- #
    for row in source.get("stores", []):
        if not row.get("number"):
            continue
        db.session.add(Store(
            number=int(row["number"]), mall=row.get("mall", ""),
            street=row.get("street", ""), city=row.get("city", ""),
            state=row.get("state", ""), zip=row.get("zip", ""),
            phone=row.get("phone", ""),
            hours_json=json.dumps(row.get("hours", {}), ensure_ascii=False),
            departments_json=json.dumps(row.get("departments", []), ensure_ascii=False),
            services_json=json.dumps(row.get("services", []), ensure_ascii=False),
            google_rating=row.get("google_rating"), google_reviews=row.get("google_reviews"),
        ))

    # ---- coupons --------------------------------------------------------- #
    for row in source.get("coupons", []):
        db.session.add(Coupon(
            code=row["code"], title=row["title"], description=row.get("description", ""),
            discount_percent=row.get("discount_percent", 0),
            min_purchase=row.get("min_purchase", 0.0),
            valid_through=row.get("valid_through", ""),
            exclusions=row.get("exclusions", ""),
            online_only=row.get("online_only", False)))

    # ---- static pages ---------------------------------------------------- #
    for row in source.get("customer_service", []):
        db.session.add(StaticPage(slug=row["slug"], title=row["title"],
                                  body_html=row["body_html"]))
    db.session.commit()


def seed_benchmark_users() -> None:
    if User.query.filter_by(email=BENCHMARK_USERS[0]["email"]).first():
        return
    digest = stable_password_hash(BENCHMARK_PASSWORD)
    users = []
    for index, row in enumerate(BENCHMARK_USERS):
        user = User(
            email=row["email"], password_hash=digest,
            first_name=row["first"], last_name=row["last"], phone=row["phone"],
            rewards_member=row["rewards_member"], rewards_points=row["rewards_points"],
            rewards_tier=row["rewards_tier"],
        )
        db.session.add(user)
        users.append(user)
    db.session.flush()

    addresses = {
        "alice.j@test.com": [
            ("Home", "1460 Alderwood Mall Blvd", "Lynnwood", "WA", "98037"),
            ("Sister", "88 Pine St", "Seattle", "WA", "98101"),
        ],
        "bob.c@test.com": [
            ("Home", "2401 Mission St", "San Francisco", "CA", "94110"),
        ],
        "carol.d@test.com": [
            ("Home", "515 N State St", "Chicago", "IL", "60654"),
        ],
        "david.k@test.com": [
            ("Home", "77 E Nationwide Blvd", "Columbus", "OH", "43215"),
            ("Parents", "390 W 5th Ave", "Columbus", "OH", "43201"),
        ],
    }
    payments = {
        "alice.j@test.com": [("Visa", "4242", 9, 2028), ("JCPenney Credit Card", "8817", 4, 2029)],
        "bob.c@test.com": [("Mastercard", "5309", 12, 2027)],
        "carol.d@test.com": [("American Express", "1005", 7, 2028)],
        "david.k@test.com": [("Visa", "0679", 3, 2027)],
    }
    for user in users:
        for index, (label, line1, city, state, zipc) in enumerate(addresses[user.email]):
            db.session.add(Address(
                user_id=user.id, label=label, first_name=user.first_name,
                last_name=user.last_name, line1=line1, city=city, state=state,
                zip=zipc, phone=user.phone, is_default=index == 0))
        for index, (card_type, last4, month, year) in enumerate(payments[user.email]):
            db.session.add(PaymentMethod(
                user_id=user.id, card_type=card_type, last4=last4,
                cardholder=f"{user.first_name} {user.last_name}",
                exp_month=month, exp_year=year, is_default=index == 0))
    db.session.flush()

    products = Product.query.order_by(Product.sort).all()
    assert products, "seed_database() must run before seed_benchmark_users()"

    def pick(offset: int) -> Product:
        return products[offset % len(products)]

    # ---- order history ------------------------------------------------ #
    order_specs = [
        # (user index, days ago, [product offsets], status, tracking, delivered_days_ago)
        (0, 12, [4, 40], "Delivered", "1Z5R892W0392841756", 4),
        (0, 31, [100], "Delivered", "1Z5R892W0388471203", 24),
        (0, 3, [12, 61, 130], "Shipped", "1Z5R892W0402311887", None),
        (1, 9, [15], "Delivered", "9400111899560008213442", 3),
        (1, 20, [55, 77], "In Transit", "9400111899560008214553", None),
        (2, 6, [200], "Delivered", "1Z5R892W0401120054", 2),
        (3, 15, [8, 23, 311], "Delivered", "4203189102309482716031", 9),
        (3, 2, [301], "Processing", "", None),
    ]
    for user_index, days_ago, offsets, status, tracking, delivered_days_ago in order_specs:
        user = users[user_index]
        address = Address.query.filter_by(user_id=user.id, is_default=True).first()
        payment = PaymentMethod.query.filter_by(user_id=user.id, is_default=True).first()
        chosen = [pick(offset) for offset in offsets]
        subtotal = round(sum(p.price for p in chosen), 2)
        discount = round(subtotal * 0.25, 2) if user_index % 2 == 0 else 0.0
        shipping = 0.0 if subtotal - discount >= 75 else 8.95
        tax = round((subtotal - discount) * 0.0825, 2)
        total = round(subtotal - discount + shipping + tax, 2)
        placed_at = MIRROR_DATE - timedelta(days=days_ago)
        order = Order(
            order_number=f"JCP{placed_at.strftime('%y%m%d')}{user_index}{order_specs.index((user_index, days_ago, offsets, status, tracking, delivered_days_ago)) + 1:03d}",
            user_id=user.id, email=user.email, status=status, placed_at=placed_at,
            delivered_at=(MIRROR_DATE - timedelta(days=delivered_days_ago))
            if delivered_days_ago is not None else None,
            subtotal=subtotal, discount=discount, shipping=shipping, tax=tax,
            total=total, coupon_code="AUTUMN" if discount else "",
            ship_name=f"{address.first_name} {address.last_name}",
            ship_address=address.line1, ship_city=address.city,
            ship_state=address.state, ship_zip=address.zip, ship_phone=address.phone,
            payment_type=payment.card_type, payment_last4=payment.last4,
            tracking_number=tracking,
            carrier=("UPS" if tracking.startswith("1Z") else "USPS") if tracking else "",
        )
        for product in chosen:
            color = product.colors[0].color if product.colors else ""
            sizes = product.colors[0].sizes if product.colors else []
            size = sizes[0]["size"] if sizes else ""
            order.items.append(OrderItem(
                product_id=product.id, product_name=product.name,
                brand=product.brand, color=color, size=size, quantity=1,
                unit_price=product.price, image_file=product.primary_image))
        db.session.add(order)
    db.session.flush()

    # ---- bag contents -------------------------------------------------- #
    bag_specs = [
        (0, [60, 200]),
        (1, [130, 201, 44]),
        (2, [2]),
        (3, [85, 320]),
    ]
    for user_index, offsets in bag_specs:
        user = users[user_index]
        for offset in offsets:
            product = pick(offset)
            color = product.colors[0].color if product.colors else ""
            sizes = product.colors[0].sizes if product.colors else []
            available_sizes = [s for s in sizes if s.get("available")]
            size = (available_sizes or sizes or [{"size": ""}])[0]["size"]
            db.session.add(CartItem(
                user_id=user.id, product_id=product.id, color=color, size=size,
                quantity=1 + (offset % 2)))
    db.session.flush()

    # ---- wish lists ----------------------------------------------------- #
    wishlist_specs = [
        (0, [10, 33, 55, 300]),
        (1, [4, 91, 210]),
        (2, [7, 12, 128, 333, 41, 90]),
        (3, [0, 15, 22]),
    ]
    for user_index, offsets in wishlist_specs:
        user = users[user_index]
        for offset in offsets:
            product = pick(offset)
            if not WishlistItem.query.filter_by(user_id=user.id,
                                                product_id=product.id).first():
                db.session.add(WishlistItem(user_id=user.id, product_id=product.id))
    db.session.flush()

    # ---- rewards activity ------------------------------------------------ #
    reward_specs = [
        (0, [("Purchase at jcp.com", 184, 12), ("Bonus points on shoes", 120, 31),
             ("Welcome bonus", 100, 60)]),
        (1, [("Purchase at jcp.com", 92, 9), ("Welcome bonus", 100, 45)]),
        (2, []),
        (3, [("Purchase at jcp.com", 210, 15), ("Welcome bonus", 100, 58)]),
    ]
    for user_index, events in reward_specs:
        user = users[user_index]
        if not user.rewards_member:
            continue
        for description, points, days_ago in events:
            db.session.add(RewardEvent(
                user_id=user.id, kind="points", points=points, description=description,
                event_date=MIRROR_DATE - timedelta(days=days_ago)))
    db.session.commit()


def build_seed_file() -> None:
    """Materialise instance_seed/jcpenney.db from a fresh runtime build."""
    import shutil

    from app import create_schema

    INSTANCE_DIR = BASE_DIR / "instance"
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    db_path = INSTANCE_DIR / "jcpenney.db"
    if db_path.exists():
        db_path.unlink()
    with app.app_context():
        create_schema()
        seed_database()
        seed_benchmark_users()
        INSTANCE_SEED.mkdir(parents=True, exist_ok=True)
        seed_path = INSTANCE_SEED / "jcpenney.db"
        for stale in INSTANCE_SEED.glob("*.db"):
            stale.unlink()
        shutil.copy2(db_path, seed_path)
        size = seed_path.stat().st_size
    print(f"[seed] instance_seed/jcpenney.db written ({size} bytes)")


if __name__ == "__main__":
    build_seed_file()
