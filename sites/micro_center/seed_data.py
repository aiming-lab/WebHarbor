"""Build-time seed for the Micro Center mirror.

Reads source_catalog.json (real product data captured from
www.microcenter.com via the Wayback Machine — see scraped_data/ pipeline in
the contribution history) and materializes it into Category / Brand / Product
/ Store / StoreStock / Review rows plus benchmark users, carts, lists, and
orders. Content rows are deterministic (a fixed RNG seed and reference date
keep catalog, stock and review rows stable across rebuilds); the bookkeeping
timestamps on users / cart_items / list_items / orders record build time, so a
rebuild is not byte-identical to the shipped prebuilt seed — the pinned
artifact in instance_seed/ is the contract, and app.py never rebuilds it when
it is present.

Idempotency: app.py gates seeding (the seed DB ships prebuilt in
instance_seed/; ensure_seed_data rebuilds only when it is missing).
"""

from __future__ import annotations

import json
import random
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = BASE_DIR / "source_catalog.json"
IMAGE_ROOT = BASE_DIR / "static" / "images"

SEED_REFERENCE_DATE = datetime(2026, 9, 21, 10, 0, 0)
RNG = random.Random(20260921)

BENCHMARK_PASSWORD = "TestPass123!"
BENCHMARK_USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display_name": "Alice Johnson"},
    {"username": "bob_c", "email": "bob.c@test.com", "display_name": "Bob Chen"},
    {"username": "carol_d", "email": "carol.d@test.com", "display_name": "Carol Davis"},
    {"username": "david_k", "email": "david.k@test.com", "display_name": "David Kim"},
]

# Store records not covered by the captured store pages fall back to the real
# Micro Center store list (id/state/city) captured from product pages; the
# address is synthesized for benchmark purposes when the archived store page
# was unavailable.
STORE_FALLBACK = {
    "205": ("Phoenix", "AZ", "1925 W. Baseline Rd", "85042"),
    "215": ("Austin", "TX", "12707 N. Mopac Expy", "78727"),
    "195": ("Santa Clara", "CA", "2600 Mission College Blvd", "95054"),
    "101": ("Tustin", "CA", "2962 El Camino Real", "92782"),
    "181": ("Denver", "CO", "8500 E. Arapahoe Rd", "80112"),
    "185": ("Miami", "FL", "1395 S. Dixie Hwy", "33156"),
    "065": ("Duluth", "GA", "2340 Pleasant Hill Rd", "30096"),
    "041": ("Marietta", "GA", "1275 Powers Ferry Rd SE", "30067"),
    "151": ("Chicago", "IL", "2645 N. Elston Ave", "60647"),
    "025": ("Westmont", "IL", "617 E. Roosevelt Rd", "60559"),
    "165": ("Indianapolis", "IN", "5702 E 86th St", "46250"),
    "191": ("Overland Park", "KS", "11955 W. 87th St Pkwy", "66214"),
    "121": ("Cambridge", "MA", "730 Memorial Dr", "02139"),
    "085": ("Rockville", "MD", "1776 E Jefferson St", "20852"),
    "125": ("Parkville", "MD", "9509 Dulaney Valley Rd", "21234"),
    "055": ("Madison Heights", "MI", "32800 Concord Dr", "48071"),
    "045": ("St. Louis Park", "MN", "1155 Wayzata Blvd", "55403"),
    "095": ("Brentwood", "MO", "87 Brentwood Promenade Ct", "63144"),
    "175": ("Charlotte", "NC", "4744 South Blvd", "28217"),
    "075": ("North Jersey", "NJ", "475 Rt 17 S", "07652"),
    "171": ("Westbury", "NY", "900 Gates Ave", "11590"),
    "115": ("Brooklyn", "NY", "850 3rd Ave", "11232"),
    "145": ("Flushing", "NY", "71-43 Kissena Blvd", "11367"),
    "105": ("Yonkers", "NY", "1271 Central Park Ave", "10704"),
    "141": ("Columbus", "OH", "747 Bethel Rd", "43214"),
    "071": ("Sharonville", "OH", "9701 Convention Center Dr", "45241"),
    "061": ("St. Davids", "PA", "301 Lancaster Ave", "19087"),
    "155": ("Houston", "TX", "5305 S Rice Ave", "77081"),
    "131": ("Dallas", "TX", "13929 N Central Expy", "75243"),
    "081": ("Fairfax", "VA", "3089 Nutley St", "22031"),
}

STORE_HOURS_TEMPLATE = [
    ("Mon - Fri", "10:00 AM - 9:00 PM"),
    ("Saturday", "10:00 AM - 9:00 PM"),
    ("Sunday", "11:00 AM - 6:00 PM"),
]

REVIEW_AUTHORS = [
    "BuildBob", "TechTina", "PCPartPickerPro", "SiliconSam", "GamerGrace",
    "DevDad", "NvidiaNate", "AMDAnn", "CoolingCarl", "MonicaBuilds",
    "FrameTimeFrank", "SarahCodes", "OverclockOllie", "JaneTheReviewer",
    "MacroMike", "LambdaLou", "Kbuilds", "TheRealReviewer", "PascalPete",
    "RigRunner", "MiniITXMax", "CaseModChris", "AIOAllie", "FiberFiona",
]
REVIEW_TEMPLATES = [
    ("Great value for the price", "Picked this up at my local store and it has been rock solid. "
     "Would recommend to anyone building on a budget."),
    ("Exactly as described", "Installation was painless and it works exactly as advertised. "
     "No complaints so far after a few weeks of daily use."),
    ("Solid purchase", "Compared a few options in store before choosing this one. "
     "The associate was helpful and the price beat online listings."),
    ("Works great", "Running it hard every day with zero issues. Build quality feels premium "
     "and it arrived well packaged."),
    ("Good, with one caveat", "Performs well overall. Took off a star because the included "
     "manual was thin, but support helped me out in minutes."),
    ("Would buy again", "Upgraded from my old part and the difference is night and day. "
     "In stock at my store which saved me shipping time."),
    ("Impressed", "Was skeptical about the brand but this exceeded expectations. "
     "Temperatures and noise are both better than my previous model."),
    ("Great for the money", "You get a lot for what you pay. Not the absolute fastest but "
     "reliability has been perfect for months."),
]
OPEN_BOX_CONDITIONS = ["Excellent", "Satisfactory", "Good"]


def slugify(text: str) -> str:
    cleaned = []
    for char in text.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    return "".join(cleaned).strip("-")


def _load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _counts_ok() -> bool:
    from app import (CartItem, Category, ListItem, Order, Product, Review,
                     Store, StoreStock, User)
    try:
        return (Product.query.count() > 0 and Store.query.count() > 0
                and User.query.filter_by(email="alice.j@test.com").first()
                is not None)
    except Exception:
        return False


def _add_categories(catalog: dict) -> dict[str, int]:
    from app import Category, db
    by_slug: dict[str, int] = {}
    for row in catalog["categories"]:
        cat = Category(name=row["name"], slug=row["slug"],
                       fq_id=row.get("fq_id"), is_dept=row.get("is_dept", False),
                       blurb=row.get("blurb", ""))
        db.session.add(cat)
        db.session.flush()
        by_slug[row["slug"]] = cat.id
    for row in catalog["categories"]:
        parent = row.get("parent")
        if parent and parent in by_slug:
            cat = db.session.get(Category, by_slug[row["slug"]])
            cat.parent_id = by_slug[parent]
    db.session.flush()
    # name-based lookup for product assignment
    by_name = {row["name"]: by_slug[row["slug"]] for row in catalog["categories"]}
    return by_name


def _add_stores(catalog: dict) -> None:
    from app import Store, db
    captured = {row["name"].replace("Micro Center - ", ""): row
                for row in catalog.get("stores_staging", {}).values()
                if row.get("name")}
    for sid, (city, state, street, zipcode) in STORE_FALLBACK.items():
        captured_row = captured.get(city)
        if captured_row and captured_row.get("street"):
            street = captured_row["street"]
            zipcode = captured_row.get("zip") or zipcode
        hours = [{"day": d, "hours": h} for d, h in STORE_HOURS_TEMPLATE]
        store = Store(id=sid, name=f"Micro Center - {city}", city=city,
                      state=state, address=street, phone=f"({800 + int(sid) % 100}) 555-{1000 + int(sid)}",
                      hours=json.dumps(hours))
        db.session.add(store)
    db.session.flush()


def _add_products(catalog: dict, by_name: dict[str, int]) -> list:
    from app import Product, db
    products = []
    for row in catalog["products"]:
        category_id = by_name.get(row.get("category"))
        if category_id is None:
            category_id = by_name.get("Electronics")
        if category_id is None:
            continue
        sku = row.get("sku") or 0
        price = float(row["price"])
        original = row.get("original_price")
        rating = row.get("rating")
        if not rating:
            rating = round(RNG.uniform(3.6, 4.9), 1)
        review_count = row.get("review_count")
        if not review_count:
            review_count = RNG.randint(2, 240)
        in_store_only = row.get("in_store_only", False)
        # Deterministic deal/flag assignment
        top_deal = bool(original and float(original) > price) or RNG.random() < 0.07
        open_box = []
        if row.get("category") in ("Laptops/Notebooks", "Desktop Computers",
                                  "Computer Monitors", "Televisions",
                                  "Graphics Cards", "iPads & Tablets",
                                  "Headphones & Earbuds") and RNG.random() < 0.30:
            for condition in OPEN_BOX_CONDITIONS[:RNG.randint(1, 3)]:
                open_box.append({"condition": condition,
                                 "price": round(price * RNG.uniform(0.72, 0.92), 2)})
        closeout = RNG.random() < 0.05
        # Ship only the images that were actually captured (the inventory
        # is the shipped asset set; upstream lists extra zoom/comping
        # variants that are not mirrored).
        shipped_images = [name for name in row.get("images", [])
                          if (IMAGE_ROOT / "products" / name).is_file()]
        product = Product(
            product_id=int(row["product_id"]),
            sku=int(sku),
            name=row["name"],
            slug=slugify(row["name"])[:290],
            brand=row.get("brand") or "",
            category_id=category_id,
            subcategory="",
            price=price,
            original_price=float(original) if original else None,
            description=row.get("description") or "",
            key_features=json.dumps(row.get("key_features", []), ensure_ascii=False),
            specs=json.dumps(row.get("specs", []), ensure_ascii=False),
            images=json.dumps(shipped_images, ensure_ascii=False),
            rating=float(rating),
            review_count=int(review_count),
            in_store_only=in_store_only,
            open_box=json.dumps(open_box, ensure_ascii=False),
            closeout=closeout,
            top_deal=top_deal,
            added_at=SEED_REFERENCE_DATE - timedelta(days=RNG.randint(1, 700)),
        )
        db.session.add(product)
        products.append(product)
    db.session.flush()
    return products


def _add_store_stock(catalog: dict, products: list) -> None:
    """Per-store inventory. Real captured stock wins; otherwise a
    deterministic distribution keeps most items in stock with realistic
    gaps per store."""
    from app import Store, StoreStock, db
    store_ids = [s.id for s in Store.query.order_by(Store.id).all()]
    captured = {}
    for row in catalog["products"]:
        stock = row.get("store_stock")
        if stock:
            captured[int(row["product_id"])] = stock
    for product in products:
        rng = random.Random(90000 + product.product_id)
        real = captured.get(product.product_id, {})
        for sid in store_ids:
            if sid in real:
                status = real[sid]
                qty = rng.randint(2, 18) if status == "in stock" else 0
            else:
                roll = rng.random()
                if roll < 0.62:
                    status, qty = "in stock", rng.randint(2, 18)
                elif roll < 0.82:
                    status, qty = "in stock", rng.randint(1, 3)   # low stock
                else:
                    status, qty = "out of stock", 0
            db.session.add(StoreStock(product_id=product.product_id, store_id=sid,
                                      status=status, qty=qty))
    db.session.flush()


def _add_reviews(catalog: dict, products: list) -> None:
    from app import Review, db
    captured = {int(row["product_id"]): row.get("reviews") or []
                for row in catalog["products"]}
    for product in products:
        for rev in captured.get(product.product_id, [])[:10]:
            try:
                rating = float(rev.get("rating") or 4.5)
            except (TypeError, ValueError):
                rating = 4.5
            if not 1 <= rating <= 5:
                rating = min(5.0, max(1.0, rating / 100 if rating > 5 else rating))
            db.session.add(Review(product_id=product.product_id,
                                  author=(rev.get("author") or "Anonymous")[:100],
                                  rating=round(rating, 1),
                                  date=str(rev.get("date") or "2026-01-15"),
                                  title=(rev.get("title") or "")[:200],
                                  body=(rev.get("body") or "")[:2000],
                                  verified=True))
        db.session.flush()
        have = Review.query.filter_by(product_id=product.product_id).count()
        target = max(1, min(6, int(product.review_count / 12) + 1))
        while have < target:
            title, body = RNG.choice(REVIEW_TEMPLATES)
            author = RNG.choice(REVIEW_AUTHORS)
            days_ago = RNG.randint(5, 500)
            date = (SEED_REFERENCE_DATE - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            rating = RNG.choices([5, 4, 3, 2], weights=[62, 27, 8, 3])[0]
            db.session.add(Review(product_id=product.product_id, author=author,
                                  rating=rating, date=date, title=title, body=body,
                                  verified=RNG.random() < 0.8))
            have += 1
    db.session.flush()


def _add_users() -> dict:
    from app import Address, PaymentCard, User, db
    users = {}
    for spec in BENCHMARK_USERS:
        user = User(email=spec["email"], username=spec["username"],
                    display_name=spec["display_name"], phone="555-555-1234",
                    is_benchmark=True)
        user.set_password(BENCHMARK_PASSWORD)
        db.session.add(user)
        db.session.flush()
        users[spec["username"]] = user
        city, state, line1, zipc = RNG.choice([
            ("Chapel Hill", "NC", "101 Columbia St", "27514"),
            ("Seattle", "WA", "2600 Alaskan Way", "98121"),
            ("Austin", "TX", "500 W 2nd St", "78701"),
            ("Cambridge", "MA", "77 Massachusetts Ave", "02139"),
        ])
        address = Address(user_id=user.id, label="Home", full_name=spec["display_name"],
                          line1=line1, line2="Apt 4", city=city, state=state,
                          zip_code=zipc, phone="555-555-1234", is_default=True)
        db.session.add(address)
        db.session.flush()
        card = PaymentCard(user_id=user.id, brand="Visa", last4=f"{1000 + user.id * 1111}"[-4:],
                           exp_month="09", exp_year="2029", is_default=True)
        db.session.add(card)
        db.session.flush()
        card2 = PaymentCard(user_id=user.id, brand="Mastercard", last4=f"{2000 + user.id * 777}"[-4:],
                            exp_month="01", exp_year="2028", is_default=False)
        db.session.add(card2)
    db.session.flush()
    return users


def _add_carts_lists_orders(users: dict, products: list) -> None:
    from app import CartItem, ListItem, Order, db
    rng = random.Random(20260922)
    ordered = sorted(products, key=lambda p: p.product_id)
    usernames = ["alice_j", "bob_c", "carol_d", "david_k"]
    for idx, username in enumerate(usernames):
        user = users[username]
        pool = ordered[idx * 7::28] or ordered[:7]
        # cart: 2-3 items
        for product in pool[:rng.randint(2, 3)]:
            db.session.add(CartItem(user_id=user.id, product_id=product.product_id,
                                    qty=rng.randint(1, 2)))
        # list: 3-5 items
        for product in pool[3:3 + rng.randint(3, 5)]:
            db.session.add(ListItem(user_id=user.id, product_id=product.product_id))
        # orders: 1-2 past orders
        for order_idx in range(rng.randint(1, 2)):
            picks = pool[8 + order_idx * 2: 10 + order_idx * 2] or pool[:2]
            items = []
            subtotal = 0.0
            for product in picks:
                qty = 1
                items.append({"product_id": product.product_id, "name": product.name,
                              "sku": product.sku, "price": round(product.price, 2),
                              "qty": qty, "brand": product.brand})
                subtotal += product.price * qty
            tax = round(subtotal * 0.0725, 2)
            placed = SEED_REFERENCE_DATE - timedelta(days=rng.randint(3, 60))
            method = rng.choice(["pickup", "shipping"])
            if method == "pickup":
                status = rng.choice(["Picked Up", "Processing", "Ready for Pickup"])
            else:
                status = rng.choice(["Delivered", "Shipped", "Preparing to Ship"])
            order = Order(
                order_number=f"MC{placed.strftime('%y%m%d')}{1000 + user.id * 37 + order_idx}",
                user_id=user.id,
                status=status,
                method=method,
                store_id=rng.choice(["101", "141", "075", "115"]),
                payment=f"Visa ending in {1000 + user.id * 1111}"[-4:].rjust(4, "0"),
                placed_at=placed,
                subtotal=round(subtotal, 2), tax=tax,
                shipping_fee=0.0 if method == "pickup" else 12.99,
                total=round(subtotal + tax + (0.0 if method == "pickup" else 12.99), 2),
                items_json=json.dumps(items, ensure_ascii=False))
            db.session.add(order)
    db.session.flush()


def _populate_all() -> None:
    from app import db
    catalog = _load_catalog()
    by_name = _add_categories(catalog)
    _add_stores(catalog)
    products = _add_products(catalog, by_name)
    _add_store_stock(catalog, products)
    _add_reviews(catalog, products)
    users = _add_users()
    _add_carts_lists_orders(users, products)
    db.session.commit()


def ensure_seed_data(force: bool, runtime_db_path: Path, seed_db_path: Path,
                     image_root: Path) -> None:
    from app import app as flask_app

    with flask_app.app_context():
        image_root.mkdir(parents=True, exist_ok=True)

        if force or not _counts_ok():
            from app import db
            db.drop_all()
            db.create_all()
            _populate_all()
            db.session.commit()
            db.session.remove()
            if runtime_db_path.exists():
                seed_db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(runtime_db_path, seed_db_path)
            return

        if runtime_db_path.exists() and not seed_db_path.exists():
            seed_db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(runtime_db_path, seed_db_path)


if __name__ == "__main__":
    import sys
    sys.modules.setdefault("seed_data", sys.modules[__name__])
    ensure_seed_data(force=not Path("instance_seed/micro_center.db").exists(),
                     runtime_db_path=Path("instance/micro_center.db"),
                     seed_db_path=Path("instance_seed/micro_center.db"),
                     image_root=Path("static/images"))
