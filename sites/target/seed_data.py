"""Seed the Target mirror from REAL scraped target.com data.

Everything an agent sees is materialised into instance_seed/target.db at build
time from scraped_data/catalog.json — real product names, real prices, real
guest ratings and real detail-page facts — plus the real target.com product
photography that ships under static/images/products/.

Determinism (the byte-identical /reset invariant):
  * every seed_* function early-returns when the DB is already populated
  * every created_at / placed_at is derived from the fixed SEED_TIMESTAMP.
    The models default those columns to datetime.utcnow, which would make the
    seed unreproducible, so the seed always sets them explicitly.
  * no RNG anywhere: all variation is index arithmetic.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import sys


def _app_module():
    """Return the already-loaded app module without re-executing app.py.

    app.py seeds at import time, so a plain `from app import ...` here would be
    circular: running `python app.py` loads it as "__main__", and the import
    would execute the file a second time under the name "app", re-entering
    initialize_database() before this module finished loading. Three entry
    points have to work:
      site_runner  -> `from app import app`   (module name "app")
      python app.py                           (module name "__main__")
      python seed_data.py                     (app not loaded yet)
    """
    mod = sys.modules.get("app")
    if mod is not None:
        return mod
    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "db") and hasattr(main, "Product"):
        return main                      # we were imported from app.py itself
    import app as mod                    # standalone build: safe to load it
    return mod


_app = _app_module()

BENCHMARK_PASSWORD = _app.BENCHMARK_PASSWORD
Brand = _app.Brand
CartItem = _app.CartItem
Category = _app.Category
CompareItem = _app.CompareItem
Deal = _app.Deal
DeliveryOption = _app.DeliveryOption
Order = _app.Order
OrderItem = _app.OrderItem
PaymentMock = _app.PaymentMock
PickupSlot = _app.PickupSlot
Product = _app.Product
ProtectionPlan = _app.ProtectionPlan
Review = _app.Review
RewardAccount = _app.RewardAccount
RewardActivity = _app.RewardActivity
Store = _app.Store
StoreInventory = _app.StoreInventory
SupportArticle = _app.SupportArticle
SupportTicket = _app.SupportTicket
User = _app.User
WishlistItem = _app.WishlistItem
db = _app.db
dump_json = _app.dump_json
slugify = _app.slugify

BASE_DIR = Path(__file__).resolve().parent
SCRAPED = BASE_DIR / "scraped_data"
CATALOG = SCRAPED / "catalog.json"
SCRAPED_IMAGES = SCRAPED / "images"
PRODUCT_IMAGE_DIR = BASE_DIR / "static" / "images" / "products"

SEED_TIMESTAMP = datetime(2026, 3, 18, 10, 0, 0)

# Real Target store locations.
STORES = [
    ("Atlanta Buckhead", "Atlanta", "GA", "3535 Peachtree Rd NE"),
    ("Austin Domain", "Austin", "TX", "11500 Rock Rose Ave"),
    ("Bellevue Square", "Bellevue", "WA", "103 Bellevue Square"),
    ("Boston Fenway", "Boston", "MA", "1341 Boylston St"),
    ("Chicago State Street", "Chicago", "IL", "1 S State St"),
    ("Denver Stapleton", "Denver", "CO", "7400 E 29th Ave"),
    ("Houston Midtown", "Houston", "TX", "3908 Main St"),
    ("Los Angeles Westwood", "Los Angeles", "CA", "10861 Weyburn Ave"),
    ("Miami Midtown", "Miami", "FL", "3401 N Miami Ave"),
    ("Minneapolis Nicollet", "Minneapolis", "MN", "900 Nicollet Mall"),
    ("New York Herald Square", "New York", "NY", "112 W 34th St"),
    ("Philadelphia Center City", "Philadelphia", "PA", "1900 Chestnut St"),
    ("Phoenix Uptown", "Phoenix", "AZ", "100 E Camelback Rd"),
    ("Portland Galleria", "Portland", "OR", "939 SW Morrison St"),
    ("Seattle Pike Place", "Seattle", "WA", "1401 2nd Ave"),
]

STORE_SERVICES = [
    ["Order Pickup", "Drive Up", "Starbucks", "CVS pharmacy"],
    ["Order Pickup", "Drive Up", "Target Optical", "Wine & Beer"],
    ["Order Pickup", "Drive Up", "Starbucks", "Apple shop at Target"],
    ["Order Pickup", "Same Day Delivery", "Ulta Beauty at Target", "Starbucks"],
]

STORE_AMENITIES = [
    ["Curbside pickup", "Order lockers", "Target Circle desk"],
    ["Curbside pickup", "Gift wrapping", "Mobile checkout"],
    ["Curbside pickup", "Self checkout", "Fitting rooms"],
    ["Curbside pickup", "Cafe seating", "Accessible parking"],
]

STORE_HOURS = ["Mon-Sat 8am-10pm", "Sun 8am-9pm"]

BENCHMARK_USERS = [
    ("alice.j@test.com", "Alice Johnson", "Seattle", "WA", "seattle-pike-place"),
    ("bob.c@test.com", "Bob Chen", "Austin", "TX", "austin-domain"),
    ("carol.d@test.com", "Carol Diaz", "Chicago", "IL", "chicago-state-street"),
    ("david.k@test.com", "David Kim", "Atlanta", "GA", "atlanta-buckhead"),
]

# NOTE: there is deliberately no templated review copy here. Reviews come
# only from scraped_data/reviews.json — see seed_reviews() for why.

SUPPORT_ARTICLES = [
    ("order-pickup-and-drive-up", "Order Pickup and Drive Up", "Pickup & Delivery",
     "Order Pickup and Drive Up are free with any order. After you place an order, wait for "
     "the 'Ready for pickup' notification, then head to the store. For Drive Up, park in a "
     "designated Drive Up space and tap 'I'm on my way' in the app. For demo pickup you should "
     "bring a photo ID and the barcode from your order confirmation."),
    ("same-day-delivery", "Same Day Delivery", "Pickup & Delivery",
     "Same Day Delivery brings eligible items to your door in as little as one hour. Oversized "
     "and bulky items may fall back to standard shipping instead of same-day delivery. Target "
     "Circle 360 members get unlimited same-day delivery on orders over $35."),
    ("returns-and-exchanges", "Returns and Exchanges", "Orders",
     "Most items can be returned within 90 days. Target owned brands carry a one-year return "
     "window with a receipt. Opened beauty items can be returned within 60 days."),
    ("target-circle-rewards", "Target Circle Rewards", "Rewards",
     "Target Circle members earn 1% back on every eligible purchase. Your rewards dashboard "
     "shows the current points balance, recent earnings and redemptions. The dashboard can also "
     "reflect certificate-style savings redemptions applied at checkout."),
    ("protection-plans", "Protection Plans", "Orders",
     "Protection plans can be added at checkout on eligible items. Two-year plans cover "
     "mechanical and electrical failure. Three-year plans additionally include accidental "
     "handling coverage such as drops and spills."),
    ("price-match-guarantee", "Price Match Guarantee", "Orders",
     "If you buy a qualifying item at Target and find it cheaper at a qualifying competitor "
     "within 14 days, Target will match the lower price once per item."),
    ("registry-and-wish-list", "Registry and Wish List", "Account",
     "Create a registry or wish list from any product page. Saved items stay in your account "
     "and can be moved into your cart at any time."),
    ("payment-options", "Payment Options", "Orders",
     "Target accepts major cards, the Target Circle Card and gift cards. Demo checkout in this "
     "environment never charges a real card; only the last four digits are recorded."),
]

DELIVERY_OPTIONS = [
    ("standard-delivery", "Standard delivery", "Free on orders over $35", 0.0, "Arrives in 3-5 days"),
    ("express-delivery", "Express delivery", "Faster hand-off from the nearest store", 9.99, "Arrives in 2 days"),
    ("same-day-delivery", "Same Day Delivery", "Delivered by a shopper today", 12.99, "Arrives today"),
]

PICKUP_WINDOWS = [
    ("today-morning", "Today", "10:00 AM - 12:00 PM"),
    ("today-afternoon", "Today", "2:00 PM - 4:00 PM"),
    ("today-evening", "Today", "6:00 PM - 8:00 PM"),
    ("tomorrow-morning", "Tomorrow", "9:00 AM - 11:00 AM"),
    ("tomorrow-evening", "Tomorrow", "5:00 PM - 7:00 PM"),
]

ORDER_STATUSES = ["Delivered", "Shipped", "Ready for pickup", "Processing"]


# --------------------------------------------------------------------------- helpers
def _catalog() -> dict:
    if not CATALOG.exists():
        raise SystemExit(
            f"missing {CATALOG} — run scraped_data/scrape_target.py, scrape_details.py "
            "and build_catalog.py first."
        )
    return json.loads(CATALOG.read_text())


def _ts(days: int = 0, minutes: int = 0) -> datetime:
    """Deterministic timestamp. Never wall-clock — that breaks reproducibility."""
    return SEED_TIMESTAMP - timedelta(days=days, minutes=minutes)


def _copy_product_images(products: list[dict]) -> int:
    PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in products:
        src_name = item.get("image_file")
        if not src_name:
            continue
        src = SCRAPED_IMAGES / src_name
        dest = PRODUCT_IMAGE_DIR / f"{item['sku']}.webp"
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)
            copied += 1
    return copied


def _counts_ok() -> bool:
    return (
        Product.query.count() >= 500
        and Category.query.count() >= 12
        and User.query.count() >= 4
        and Store.query.count() >= 15
    )


# --------------------------------------------------------------------------- seeds
def seed_catalog() -> None:
    """Brands, real Target departments, and the real product catalog."""
    if Product.query.count() > 0:
        return
    data = _catalog()

    brands: dict[str, Brand] = {}
    for entry in data["brands"]:
        brand = Brand(name=entry["name"], slug=entry["slug"], accent_color="#cc0000")
        db.session.add(brand)
        brands[entry["name"]] = brand

    categories: dict[str, Category] = {}
    for entry in data["categories"]:
        category = Category(
            name=entry["name"],
            slug=entry["slug"],
            section=entry["section"],
            description=entry["description"],
            hero_title=entry["description"],
            image_path=f"images/categories/{entry['slug']}.webp",
        )
        db.session.add(category)
        categories[entry["slug"]] = category
    db.session.flush()

    for index, item in enumerate(data["products"]):
        category = categories[item["category"]]
        brand = brands[item["brand"]]
        price = float(item["price"])
        list_price = float(item.get("list_price") or price)
        rating = float(item["rating"]) if item.get("rating") else round(4.0 + (index % 9) / 10, 1)
        highlights = item.get("highlights") or []
        specs = item.get("specs") or []
        description = item.get("description") or ""
        if not description and highlights:
            description = highlights[0]

        db.session.add(
            Product(
                sku=item["sku"],
                slug=item["slug"],
                name=item["name"],
                short_description=description[:200],
                long_description=description,
                price=price,
                list_price=list_price,
                rating=rating,
                # Real guest-rating count when the PDP exposed one, otherwise a
                # deterministic stand-in.
                review_count=int(item["rating_count"]) if item.get("rating_count")
                             else 120 + (index * 7) % 880,
                secondary_ratings_json=dump_json(item.get("secondary_ratings") or {}),
                percent_recommended=item.get("percent_recommended"),
                availability_status="In stock" if index % 17 else "Limited stock",
                pickup_eligible=index % 5 != 0,
                delivery_eligible=index % 11 != 0,
                featured=index % 37 == 0,
                deal_badge="Sale" if list_price > price else "",
                image_path=f"images/products/{item['sku']}.webp",
                highlights_json=dump_json(highlights),
                specs_json=dump_json(specs),
                tags_json=dump_json([category.name, brand.name, category.section]),
                search_keywords=" ".join(
                    [item["name"], brand.name, category.name, item["category"].replace("-", " ")]
                ).lower(),
                stock_count=6 + (index * 13) % 90,
                category_id=category.id,
                brand_id=brand.id,
            )
        )
    db.session.flush()


def seed_stores() -> None:
    if Store.query.count() > 0:
        return
    for index, (name, city, state, address) in enumerate(STORES):
        db.session.add(
            Store(
                slug=slugify(name),
                name=name,
                city=city,
                state=state,
                address=address,
                phone=f"(555) 0{index:02d}-{1000 + index * 7}",
                hours_json=dump_json(STORE_HOURS),
                amenities_json=dump_json(STORE_AMENITIES[index % len(STORE_AMENITIES)]),
                services_json=dump_json(STORE_SERVICES[index % len(STORE_SERVICES)]),
                hero_copy=f"{name} — shop, pick up and Drive Up in {city}, {state}.",
                # No store photography is scraped, and the guide forbids placeholder
                # imagery, so store pages simply render without a hero image.
                image_path="",
            )
        )
    db.session.flush()


def seed_fulfillment() -> None:
    if DeliveryOption.query.count() > 0:
        return
    for slug, title, description, fee, eta in DELIVERY_OPTIONS:
        db.session.add(
            DeliveryOption(slug=slug, title=title, description=description, fee=fee, eta_label=eta)
        )
    for store in Store.query.order_by(Store.id).all():
        for index, (code, day, window) in enumerate(PICKUP_WINDOWS):
            db.session.add(
                PickupSlot(
                    store_id=store.id,
                    slot_code=f"{store.slug}-{code}",
                    day_label=day,
                    time_window=window,
                    available_capacity=4 + (store.id + index) % 9,
                )
            )
    db.session.flush()


def seed_inventory() -> None:
    if StoreInventory.query.count() > 0:
        return
    stores = Store.query.order_by(Store.id).all()
    products = Product.query.order_by(Product.id).all()
    for p_index, product in enumerate(products):
        for offset in range(3):
            store = stores[(p_index + offset * 5) % len(stores)]
            db.session.add(
                StoreInventory(
                    store_id=store.id,
                    product_id=product.id,
                    quantity=4 + (p_index + offset * 3) % 25,
                    pickup_window="Ready within 2 hours" if offset == 0 else "Ready today",
                    aisle=f"{chr(65 + (p_index + offset) % 12)}{10 + (p_index % 40)}",
                )
            )
    db.session.flush()


def seed_reviews() -> None:
    """ONLY real scraped guest reviews. Products without them get none.

    There used to be a templated fallback for the ~590 products whose live PDP
    exposed no reviews. It produced text that was category-blind: a bag of
    ground coffee ended up with "Does what I needed without any fuss. Easy to
    clean, too." Wrong-for-the-product copy is worse than an empty section —
    it reads as fake to anyone skimming, and tasks that quote reviews would be
    grounded in invented text.

    A product can legitimately show a star-rating count with no written
    reviews; that is how target.com behaves too ("ratings" != "reviews").
    """
    if Review.query.count() > 0:
        return
    by_sku = {item["sku"]: item for item in _catalog()["products"]}

    for index, product in enumerate(Product.query.order_by(Product.id).all()):
        for slot, r in enumerate((by_sku.get(product.sku) or {}).get("reviews") or []):
            rating = r.get("rating")
            db.session.add(
                Review(
                    product_id=product.id,
                    author_name=r["author"] or "Target guest",
                    title=r["title"] or "Guest review",
                    body=r["body"],
                    rating=min(5, max(1, int(round(float(rating))))) if rating
                           else min(5, max(3, int(round(product.rating)))),
                    verified=r["verified"],
                    created_at=_ts(days=(index * 7 + slot * 11) % 240),
                )
            )
    db.session.flush()


def seed_protection_plans() -> None:
    if ProtectionPlan.query.count() > 0:
        return
    for product in Product.query.filter(Product.price >= 60).order_by(Product.id).all():
        db.session.add(
            ProtectionPlan(
                product_id=product.id,
                name="2-Year Protection Plan",
                years=2,
                price=round(max(3.0, product.price * 0.08), 2),
                coverage_summary="Covers mechanical and electrical failure once the "
                                 "manufacturer warranty ends.",
                accidental=False,
                priority_support=False,
            )
        )
        db.session.add(
            ProtectionPlan(
                product_id=product.id,
                name="3-Year Protection Plan",
                years=3,
                price=round(max(5.0, product.price * 0.13), 2),
                coverage_summary="Everything in the 2-year plan plus accidental handling "
                                 "coverage for drops, spills and cracked screens.",
                accidental=True,
                priority_support=True,
            )
        )
    db.session.flush()


def seed_deals() -> None:
    if Deal.query.count() > 0:
        return
    # Products are inserted grouped by category, so taking the first N by id
    # would fill the deals page with one department. Round-robin across
    # categories instead — deterministic, and it mirrors how target.com spreads
    # its weekly deals over the whole store.
    discounted = Product.query.filter(Product.list_price > Product.price).order_by(Product.id).all()
    by_category: dict[int, list] = {}
    for product in discounted:
        by_category.setdefault(product.category_id, []).append(product)

    ordered: list = []
    for rank in range(max((len(v) for v in by_category.values()), default=0)):
        for category_id in sorted(by_category):
            bucket = by_category[category_id]
            if rank < len(bucket):
                ordered.append(bucket[rank])
        if len(ordered) >= 48:
            break

    for index, product in enumerate(ordered[:48]):
        pct = int(round((product.list_price - product.price) / product.list_price * 100))
        db.session.add(
            Deal(
                slug=f"deal-{product.sku.lower()}",
                title=product.name,
                subtitle=f"Save {pct}% on this {product.category.name.lower()} pick.",
                badge="Member Deal" if index % 3 else "Top Deal",
                discount_percent=pct,
                ends_label=f"Ends Mar {24 + index % 7}",
                category_slug=product.category.slug,
                product_id=product.id,
            )
        )
    db.session.flush()


def seed_support() -> None:
    if SupportArticle.query.count() > 0:
        return
    for slug, title, topic, body in SUPPORT_ARTICLES:
        db.session.add(
            SupportArticle(
                slug=slug,
                title=title,
                topic=topic,
                summary=body.split(". ")[0] + ".",
                body=body,
                upstream_url=f"https://help.target.com/help/subcategoryarticle?childcat={slug}",
                keywords_json=dump_json(title.lower().split()),
            )
        )
    db.session.flush()


def seed_users() -> None:
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    for index, (email, name, city, state, store_slug) in enumerate(BENCHMARK_USERS):
        user = User(
            email=email,
            full_name=name,
            phone=f"(555) 1{index:02d}-2{index}00",
            city=city,
            state=state,
            preferred_store_slug=store_slug,
            member_tier="Target Circle 360" if index % 2 == 0 else "Target Circle",
            rewards_member_id=f"TC-{4400 + index * 37}",
            created_at=_ts(days=420 - index * 30),
        )
        user.set_password(BENCHMARK_PASSWORD)
        db.session.add(user)
    db.session.flush()

    for index, user in enumerate(User.query.order_by(User.id).all()):
        db.session.add(
            RewardAccount(
                user_id=user.id,
                member_id=user.rewards_member_id,
                points_balance=1240 + index * 315,
                tier=user.member_tier,
                available_certificates=index % 3,
            )
        )
    db.session.flush()


def seed_reward_activity() -> None:
    if RewardActivity.query.count() > 0:
        return
    entries = [
        ("Earned on purchase", 120), ("Earned on purchase", 85),
        ("Certificate redeemed", -250), ("Target Circle Week bonus", 300),
        ("Earned on purchase", 64),
    ]
    for u_index, user in enumerate(User.query.order_by(User.id).all()):
        for a_index, (title, delta) in enumerate(entries):
            db.session.add(
                RewardActivity(
                    user_id=user.id,
                    points_delta=delta + u_index * 5,
                    title=title,
                    note="Applied to your Target Circle dashboard.",
                    created_at=_ts(days=a_index * 21 + u_index),
                )
            )
    db.session.flush()


def seed_account_state() -> None:
    if CartItem.query.count() > 0 or WishlistItem.query.count() > 0:
        return
    users = User.query.order_by(User.id).all()
    products = Product.query.order_by(Product.id).all()
    stores = Store.query.order_by(Store.id).all()
    for u_index, user in enumerate(users):
        for slot in range(2):
            product = products[(u_index * 97 + slot * 41) % len(products)]
            db.session.add(
                CartItem(
                    user_id=user.id,
                    product_id=product.id,
                    quantity=1 + slot,
                    fulfillment_method="delivery" if slot % 2 == 0 else "pickup",
                    store_id=stores[(u_index + slot) % len(stores)].id,
                    created_at=_ts(days=2, minutes=slot * 30),
                )
            )
        for slot in range(4):
            product = products[(u_index * 53 + slot * 29) % len(products)]
            db.session.add(
                WishlistItem(user_id=user.id, product_id=product.id, created_at=_ts(days=9 + slot))
            )
        for slot in range(3):
            product = products[(u_index * 71 + slot * 17) % len(products)]
            db.session.add(
                CompareItem(user_id=user.id, product_id=product.id, created_at=_ts(days=4 + slot))
            )
    db.session.flush()


def seed_orders() -> None:
    if Order.query.count() > 0:
        return
    users = User.query.order_by(User.id).all()
    products = Product.query.order_by(Product.id).all()
    stores = Store.query.order_by(Store.id).all()
    options = {o.slug: o for o in DeliveryOption.query.all()}
    counter = 0
    for u_index, user in enumerate(users):
        for o_index in range(4):
            counter += 1
            pickup = o_index % 2 == 1
            store = stores[(u_index + o_index) % len(stores)]
            picked = [products[(counter * 131 + s * 37) % len(products)]
                      for s in range(1 + o_index % 2)]
            subtotal = round(sum(p.price for p in picked), 2)
            tax = round(subtotal * 0.0875, 2)
            fee = 0.0 if pickup else options["standard-delivery"].fee
            order = Order(
                user_id=user.id,
                order_number=f"TGT-{240000 + counter}",
                email=user.email,
                status=ORDER_STATUSES[(u_index + o_index) % len(ORDER_STATUSES)],
                subtotal=subtotal,
                tax=tax,
                total=round(subtotal + tax + fee, 2),
                fulfillment_method="pickup" if pickup else "delivery",
                store_id=store.id if pickup else None,
                delivery_option_id=None if pickup else options["standard-delivery"].id,
                shipping_name=user.full_name,
                shipping_city=user.city,
                shipping_state=user.state,
                shipping_zip=f"9{8000 + u_index * 11}",
                payment_brand="Target Circle Card" if u_index % 2 == 0 else "Demo Visa",
                payment_last4=f"{4000 + counter}"[-4:],
                confirmation_note="Synthetic demo order — no real payment was processed.",
                pickup_slot_label=f"{store.name} · Today 2:00 PM - 4:00 PM" if pickup else "",
                placed_at=_ts(days=6 * counter),
            )
            db.session.add(order)
            db.session.flush()
            for product in picked:
                db.session.add(
                    OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        item_name=product.name,
                        quantity=1,
                        unit_price=product.price,
                        protection_plan_name="",
                    )
                )
            db.session.add(
                PaymentMock(
                    order_id=order.id,
                    amount=order.total,
                    card_label=f"{order.payment_brand} ending in {order.payment_last4}",
                    auth_status="Approved",
                    approval_code=f"AP{700000 + counter * 13}",
                    created_at=order.placed_at,
                )
            )
    db.session.flush()


def seed_support_tickets() -> None:
    if SupportTicket.query.count() > 0:
        return
    subjects = [
        ("Where is my Drive Up order?", "Order Pickup"),
        ("Return window question", "Returns"),
    ]
    for u_index, user in enumerate(User.query.order_by(User.id).all()):
        subject, topic = subjects[u_index % len(subjects)]
        db.session.add(
            SupportTicket(
                user_id=user.id,
                subject=subject,
                status="Open" if u_index % 2 == 0 else "Resolved",
                channel="Demo contact form",
                summary=f"{topic} — submitted from the demo support form.",
                created_at=_ts(days=12 + u_index * 3),
            )
        )
    db.session.flush()


# --------------------------------------------------------------------------- entry point
def ensure_seed_data(force: bool, runtime_db_path: Path, seed_db_path: Path) -> None:
    if not (force or not _counts_ok()):
        return
    data = _catalog()
    copied = _copy_product_images(data["products"])
    db.drop_all()
    db.create_all()
    seed_catalog()
    seed_stores()
    seed_fulfillment()
    seed_inventory()
    seed_reviews()
    seed_protection_plans()
    seed_deals()
    seed_support()
    seed_users()
    seed_reward_activity()
    seed_account_state()
    seed_orders()
    seed_support_tickets()
    db.session.commit()
    print(
        f"seeded {Product.query.count()} products / {Category.query.count()} categories / "
        f"{Brand.query.count()} brands / {Review.query.count()} reviews "
        f"({copied} product images copied)"
    )
    db.session.remove()
    if runtime_db_path.exists():
        seed_db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(runtime_db_path, seed_db_path)


if __name__ == "__main__":
    from app import app

    with app.app_context():
        ensure_seed_data(
            force=True,
            runtime_db_path=BASE_DIR / "instance" / "target.db",
            seed_db_path=BASE_DIR / "instance_seed" / "target.db",
        )
