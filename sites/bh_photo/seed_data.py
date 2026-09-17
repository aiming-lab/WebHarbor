"""Build the B&H Photo mirror database.

Two kinds of data live in this seed and they are kept strictly apart.

**Sourced catalog.** Departments, brands, products, prices, availability,
conditions, descriptions and every specification row come from
`source_catalog.json`, which `sources/build_manifest.py` writes from dated
Internet Archive captures of bhphotovideo.com. Each product carries the capture
URL and timestamp it was read from. A value the source does not state is stored
empty, never invented.

**Declared benchmark state.** Accounts, reviews, questions, answers, bundles,
deals, store inventory, carts, wishlists, comparisons, orders and reservations
are generated here. They are the state a web-agent benchmark needs and they do
not claim to mirror anything upstream. Every generated value is derived from a
hash of the product SKU, so the database is byte-reproducible from this file
plus the manifest.

Reproducibility rules that this module must keep:

* every ``seed_*`` entry point early-returns on a populated database
* no clock reads, no ``random`` without a fixed derivation, no network
* benchmark passwords hash with a fixed salt so a rebuild matches byte for byte
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

MIRROR_REFERENCE_DATE = datetime(2026, 4, 18, 10, 0, 0)
BENCHMARK_PASSWORD = "TestPass123!"
MANIFEST_NAME = "source_catalog.json"

# The one real B&H retail counter, read from the upstream page footer
# ("B&H Photo Video. 420 9th Ave, New York, NY, 10001"). B&H operates a single
# store, so the mirror ships one pickup location rather than inventing a chain.
STORE = {
    "name": "B&H SuperStore",
    "slug": "bh-superstore-nyc",
    "city": "New York",
    "state": "NY",
    "address": "420 9th Ave, New York, NY 10001",
    "pickup_hours": "Mon-Thu 9:30am-7pm, Fri 9:30am-1pm, Sun 10am-6pm",
    "contact_phone": "800-606-6969",
    "inventory_note": "Counter stock shown on this mirror is test data, not live inventory.",
}

USER_DEFS = [
    {"email": "alice.j@test.com", "username": "alicej", "display_name": "Alice Johnson",
     "company": "Northlight Weddings", "role": "Photographer"},
    {"email": "bob.c@test.com", "username": "bobc", "display_name": "Bob Chen",
     "company": "Chen Motion", "role": "Cinematographer"},
    {"email": "carol.d@test.com", "username": "carold", "display_name": "Carol Davis",
     "company": "Davis Audio Post", "role": "Audio Engineer"},
    {"email": "david.k@test.com", "username": "davidk", "display_name": "David Kim",
     "company": "Kim Studio Systems", "role": "Systems Integrator"},
]

REVIEW_AUTHORS = ["Jordan P.", "Riley M.", "Sam O.", "Avery L.", "Casey T.", "Drew B."]
REVIEW_HEADLINES = [
    "Holds up on long shoots", "Exactly what the spec sheet promises",
    "Solid build, predictable results", "Worth the upgrade",
    "Good value for the feature set", "Does one job and does it well",
]
REVIEW_BODIES = [
    "Picked this up after comparing the spec sheets and it has matched them so far. "
    "Build quality is what I expected at this price.",
    "Used it on back-to-back jobs last month with no surprises. Setup was quick and "
    "it behaved the same way every time.",
    "Does what the listing says. Nothing flashy, but it has not let me down and the "
    "handling is comfortable over a long day.",
    "Upgraded from an older unit. The improvement is noticeable in daily use, "
    "though the older one still works fine for lighter work.",
    "Good fit for my workflow. Read the specification table before ordering and "
    "check the ports match what you already own.",
    "Solid for the money. It is not the top of the range, but for regular use it "
    "covers everything I needed.",
]
QUESTION_TEMPLATES = [
    "Is this covered by the standard return window?",
    "Does this ship with the manufacturer warranty?",
    "Can this item be collected at the store counter?",
    "What is in the box besides the item itself?",
]
ANSWER_TEMPLATES = [
    "Yes. The return window shown on this page applies to this item.",
    "Yes, the warranty stated in the product details is included.",
    "Store pickup is offered wherever this page shows counter stock.",
    "The box contents follow the manufacturer's standard packaging.",
]


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (text or "").lower())
    return re.sub(r"-{2,}", "-", text).strip("-")[:200]


def digest(*parts: object) -> int:
    """Stable integer derived from the given parts, for benchmark-state choices."""
    joined = "|".join(str(part) for part in parts)
    return int(hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12], 16)


def pick(options: list, *parts: object):
    return options[digest(*parts) % len(options)]


def deterministic_password_hash(password: str, salt_seed: str) -> str:
    """PBKDF2 hash with a derived, fixed salt, in Werkzeug's storage format.

    Flask-Bcrypt salts randomly, which made the shipped seed impossible to
    regenerate byte for byte from source. Benchmark accounts therefore use a
    salt derived from the account itself; live registrations still use bcrypt.
    """
    iterations = 260000
    salt = hashlib.sha256(f"bh_photo:{salt_seed}".encode("utf-8")).hexdigest()[:16]
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2:sha256:{iterations}${salt}${derived.hex()}"


def load_manifest(base_dir: str) -> dict:
    path = Path(base_dir) / MANIFEST_NAME
    if not path.is_file():
        raise RuntimeError(f"missing source manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def focal_bucket(focal_length: str | None) -> str:
    """Group a published focal length so the listing facet has usable buckets."""
    if not focal_length:
        return ""
    numbers = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)\s*mm", focal_length)]
    if not numbers:
        return ""
    widest = min(numbers)
    if widest < 24:
        return "Ultra Wide"
    if widest < 45:
        return "Wide"
    if widest < 85:
        return "Standard"
    return "Telephoto"


def search_blob(product: dict) -> str:
    """Text the site's search matches against, built only from sourced fields."""
    parts = [product["name"], product["brand"], product["product_type"],
             product.get("mpn") or "", product.get("bh_sku") or "",
             product.get("mount_type") or "", product.get("sensor_size") or "",
             product.get("focal_length") or "", product.get("connectivity") or ""]
    parts += [f"{row['label']} {row['value']}" for row in product["specs"][:12]]
    return " ".join(part for part in parts if part)[:2000]


def short_description(product: dict) -> str:
    text = (product.get("description") or "").strip()
    if not text:
        return f"{product['brand']} {product['product_type'].lower()} listed in the B&H catalog."
    sentence = re.split(r"(?<=[.!?])\s", text)[0]
    return sentence[:210]


def benchmark_condition(product: dict, index: int) -> tuple[str, float | None]:
    """Assign the used / open-box shelf.

    B&H used stock turns over constantly and is not meaningfully archivable, so
    condition here is declared benchmark state derived from the SKU, applied on
    top of real products. The price discount is generated, not sourced.
    """
    sourced = product.get("condition") or "New"
    if sourced != "New":
        return sourced, None
    bucket = digest("condition", product["bh_sku"] or product["slug"]) % 12
    price = product.get("price_usd")
    if bucket == 0 and price:
        return "Used", round(price * 0.72, 2)
    if bucket == 1 and price:
        return "Open-Box", round(price * 0.86, 2)
    return "New", None


SUBCATEGORY_TITLES = {
    "mirrorless-cameras": "Mirrorless", "dslr-cameras": "DSLR", "camera-lenses": "Lens",
    "tripods-supports": "Support", "memory-cards-storage": "Storage",
    "cinema-cameras": "Cinema", "monitors-recorders": "Monitoring",
    "microphones": "Audio", "headphones": "Listening", "laptops": "Computing",
    "monitors": "Display", "printers-scanners": "Print", "lighting-kits": "Lighting",
    "drones": "Aerial",
}


def build_kits(members: list[tuple], wanted: int) -> list[tuple[str, list]]:
    """Assemble kits from fixed themes rather than arbitrary groupings.

    A shop sells a body with storage and support, or a microphone with
    monitoring headphones. Each theme names the shelves it draws from, so a kit
    is coherent instead of a laptop bundled with a softbox.
    """
    themes = [
        ("Mirrorless Creator Kit", ["mirrorless-cameras", "memory-cards-storage", "tripods-supports"]),
        ("DSLR Starter Kit", ["dslr-cameras", "camera-lenses", "memory-cards-storage"]),
        ("Cinema Rig Kit", ["cinema-cameras", "monitors-recorders", "memory-cards-storage"]),
        ("Podcast Kit", ["microphones", "headphones"]),
        ("Studio Desk Kit", ["laptops", "monitors"]),
        ("Office Kit", ["laptops", "printers-scanners"]),
        ("Aerial Kit", ["drones", "memory-cards-storage"]),
        ("Lighting Kit", ["lighting-kits", "tripods-supports"]),
        ("Prime Lens Kit", ["camera-lenses", "tripods-supports"]),
        ("Field Audio Kit", ["microphones", "memory-cards-storage"]),
    ]
    by_shelf: dict[str, list] = {}
    entries = {product.id: entry for product, entry in members}

    def compatible_storage(anchor, candidate):
        slots = " ".join(row['value'] for row in entries[anchor.id]['specs']
                         if row['label'] == 'Media/Memory Card Slot').lower()
        name = candidate.name.lower()
        if 'cfexpress type b' in slots:
            return bool(re.search(r'cfexpress(?:\s+\d+(?:\.\d+)?)?\s+type b', name))
        if 'cfexpress type a' in slots:
            return bool(re.search(r'cfexpress(?:\s+\d+(?:\.\d+)?)?\s+type a', name))
        if 'microsd' in slots:
            return 'microsd' in name
        if 'sd/' in slots or 'sdxc' in slots or 'sdhc' in slots:
            return ('sdxc' in name or 'sdhc' in name) and 'microsd' not in name
        return False
    for product, entry in sorted(members, key=lambda item: -item[0].price):
        by_shelf.setdefault(entry["subcategory_slug"], []).append(product)

    used: set[int] = set()
    kits: list[tuple[str, list]] = []
    for title, shelves in themes:
        if len(kits) >= wanted:
            break
        for variant in range(2):
            kit, prefixes = [], set()
            for shelf in shelves:
                for product in by_shelf.get(shelf, []):
                    prefix = " ".join(product.name.split()[:4]).lower()
                    if (product.id in used and shelf != "memory-cards-storage") or prefix in prefixes:
                        continue
                    if shelf == 'memory-cards-storage' and kit and not compatible_storage(kit[0], product):
                        continue
                    kit.append(product)
                    prefixes.add(prefix)
                    used.add(product.id)
                    break
            if len(kit) == len(shelves):
                suffix = "" if variant == 0 else f" {variant + 1}"
                kits.append((f"{kit[0].name.split()[0]} {title}{suffix}", kit))
            else:
                for product in kit:
                    used.discard(product.id)
                break
    return kits


def seed_database(db, models, base_dir: str):
    Product = models["Product"]
    if Product.query.count() > 0:
        return

    Category = models["Category"]
    Brand = models["Brand"]
    ProductImage = models["ProductImage"]
    ProductSpecGroup = models["ProductSpecGroup"]
    ProductSpec = models["ProductSpec"]
    ProductReview = models["ProductReview"]
    ProductQuestion = models["ProductQuestion"]
    ProductAnswer = models["ProductAnswer"]
    Bundle = models["Bundle"]
    BundleItem = models["BundleItem"]
    StoreLocation = models["StoreLocation"]
    StoreInventory = models["StoreInventory"]
    Deal = models["Deal"]

    manifest = load_manifest(base_dir)
    departments = manifest["departments"]
    subcategory_names = manifest["subcategory_names"]

    category_by_slug = {}
    for slug, spec in sorted(departments.items(), key=lambda item: item[1]["nav_order"]):
        category = Category(
            name=spec["name"], slug=slug,
            description=f"{spec['name']} gear carried by B&H.",
            hero_copy=f"Shop {spec['name']} at B&H.",
            icon_label=spec["name"][:4], nav_order=spec["nav_order"],
        )
        db.session.add(category)
        category_by_slug[slug] = category
    db.session.flush()

    order = 1
    for slug, spec in sorted(departments.items(), key=lambda item: item[1]["nav_order"]):
        for child in spec["children"]:
            if child == slug:
                # a department with a single same-named shelf (Drones) keeps one row
                continue
            category = Category(
                name=subcategory_names[child], slug=child,
                description=f"{subcategory_names[child]} in the {spec['name']} department.",
                hero_copy=f"{subcategory_names[child]} at B&H.",
                icon_label=subcategory_names[child][:4],
                nav_order=order, parent_id=category_by_slug[slug].id,
            )
            db.session.add(category)
            category_by_slug[child] = category
            order += 1
    db.session.flush()

    brand_by_name = {}
    for name in sorted({product["brand"] for product in manifest["products"]}):
        brand = Brand(
            name=name, slug=slugify(name),
            origin="", badge_color=f"#{digest('brand', name) % 0xFFFFFF:06x}",
            blurb=f"{name} products carried by B&H.",
        )
        db.session.add(brand)
        brand_by_name[name] = brand
    db.session.flush()

    store = StoreLocation(**STORE)
    db.session.add(store)
    db.session.flush()

    created = []
    for index, entry in enumerate(manifest["products"]):
        condition, adjusted_price = benchmark_condition(entry, index)
        sourced_price = entry.get("price_usd")
        price = adjusted_price if adjusted_price is not None else sourced_price
        list_price = sourced_price if adjusted_price is not None else None
        seed_key = entry.get("bh_sku") or entry["slug"]

        product = Product(
            category_id=category_by_slug[entry["subcategory_slug"]].id,
            brand_id=brand_by_name[entry["brand"]].id,
            name=entry["name"], slug=entry["slug"],
            sku=entry.get("bh_sku") or f"BH{index:05d}",
            mpn=entry.get("mpn") or "",
            short_description=short_description(entry),
            description=entry.get("description") or "",
            search_blob=search_blob(entry),
            price=price if price is not None else 0.0,
            list_price=list_price,
            rating=0.0, review_count=0, qa_count=0,   # set from the rows actually created
            condition=condition,
            availability=entry.get("availability") or "In Stock",
            stock_level=4 + digest("stock", seed_key) % 18,
            pickup_available=digest("pickup", seed_key) % 4 != 0,
            pickup_message="Ready in 2 hours" if digest("pickup", seed_key) % 4 != 0 else "Pickup unavailable",
            shipping_message="Free Expedited Shipping",
            return_window="30-Day Return Window",
            warranty="Manufacturer warranty as stated by B&H",
            best_seller_rank=index + 1,
            sort_newness=len(manifest["products"]) - index,
            top_category_slug=entry["department_slug"],
            subcategory_slug=entry["subcategory_slug"],
            product_family=entry["subcategory_slug"],
            product_type=entry["product_type"],
            sensor_size=entry.get("sensor_size") or "",
            mount_type=entry.get("mount_type") or "",
            focal_length=entry.get("focal_length") or "",
            focal_length_bucket=focal_bucket(entry.get("focal_length")),
            megapixels=entry.get("megapixels") or 0,
            capacity_gb=entry.get("capacity_gb") or 0,
            connectivity=entry.get("connectivity") or "",
            pickup_store_count=1 if digest("pickup", seed_key) % 4 != 0 else 0,
            # products whose photo the archive does not hold fall back to a
            # placeholder committed to the repo, so the page never shows a broken
            # image and the gap stays visible to a reviewer
            image_path=entry.get("image_path") or "icons/product-placeholder.svg",
            accent_color=f"#{digest('accent', seed_key) % 0xFFFFFF:06x}",
            release_label="",
            is_featured=index % 9 == 0,
            is_bundle_anchor=index % 11 == 0,
            is_used_highlight=condition != "New",
        )
        db.session.add(product)
        created.append((product, entry))
    db.session.flush()

    for product, entry in created:
        if entry.get("image_path"):
            db.session.add(ProductImage(product_id=product.id, path=entry["image_path"],
                                        label=f"{product.name} main image", sort_order=0))

        groups = {}
        seen_specs: set[tuple[str, str, str]] = set()
        for row in entry["specs"]:
            title = row["group"] or "Specifications"
            fingerprint = (title, row["label"], row["value"])
            if fingerprint in seen_specs:
                continue  # some captured pages list the same row twice
            seen_specs.add(fingerprint)
            if title not in groups:
                group = ProductSpecGroup(product_id=product.id, title=title, sort_order=len(groups))
                db.session.add(group)
                db.session.flush()
                groups[title] = (group, 0)
            group, position = groups[title]
            db.session.add(ProductSpec(group_id=group.id, name=row["label"],
                                       value=row["value"], sort_order=position))
            groups[title] = (group, position + 1)

        seed_key = entry.get("bh_sku") or entry["slug"]
        review_total = 1 + digest("reviews", seed_key) % 4
        if product.slug == "canon-eos-r1-mirrorless-camera-with-essentials-kit":
            review_total = max(2, review_total)
        ratings = []
        for number in range(review_total):
            rating = 3 + digest("rating", seed_key, number) % 3
            if product.slug == "canon-eos-r1-mirrorless-camera-with-essentials-kit" and number == 1:
                rating = 5 if ratings[0] != 5 else 4
            ratings.append(rating)
            db.session.add(ProductReview(
                product_id=product.id,
                author_name=pick(REVIEW_AUTHORS, "author", seed_key, number),
                headline=pick(REVIEW_HEADLINES, "headline", seed_key, number),
                body=pick(REVIEW_BODIES, "body", seed_key, number),
                rating=rating, verified_purchase=digest("verified", seed_key, number) % 3 != 0,
                created_at=MIRROR_REFERENCE_DATE - timedelta(days=30 + number * 17),
            ))
        # the badge must equal the rows a shopper can actually open
        product.review_count = review_total
        product.rating = round(sum(ratings) / len(ratings), 1)

        question_total = 1 + digest("questions", seed_key) % 3
        asked: set[int] = set()
        for number in range(question_total):
            # the answer must be the one written for this question, so both are
            # taken from the same index rather than drawn independently
            index = digest("question", seed_key, number) % len(QUESTION_TEMPLATES)
            while index in asked:
                index = (index + 1) % len(QUESTION_TEMPLATES)
            asked.add(index)
            question = ProductQuestion(
                product_id=product.id,
                question=QUESTION_TEMPLATES[index],
                asker_name=pick(REVIEW_AUTHORS, "asker", seed_key, number),
                created_at=MIRROR_REFERENCE_DATE - timedelta(days=20 + number * 9),
            )
            db.session.add(question)
            db.session.flush()
            db.session.add(ProductAnswer(
                question_id=question.id, responder_name="B&H Support",
                answer=ANSWER_TEMPLATES[index],
                created_at=question.created_at + timedelta(days=1),
            ))
        product.qa_count = question_total

        if product.pickup_available:
            db.session.add(StoreInventory(
                store_id=store.id, product_id=product.id,
                quantity=1 + digest("counter", seed_key) % 6,
                pickup_eta="Ready in 2 hours",
            ))

        if product.list_price and product.price and product.list_price > product.price:
            db.session.add(Deal(
                product_id=product.id,
                label="Open-Box Savings" if product.condition == "Open-Box" else "Used Savings",
                sale_price=product.price, deal_type="condition", is_active=True,
            ))

    db.session.flush()

    # Bundles group real products that share a department. The grouping, the
    # bundle names and the bundle price are benchmark state, not B&H offers.
    # Kits are built across the whole catalog, the way a shop pairs a body with
    # storage and support, rather than inside one department where small
    # departments cannot fill three different shelves.
    ordered_members = sorted(created, key=lambda item: item[0].id)
    for number, (title, chosen) in enumerate(build_kits(ordered_members, wanted=14)):
            total = sum(item.price for item in chosen)
            if total <= 0:
                continue
            shelf_label = SUBCATEGORY_TITLES.get(chosen[0].subcategory_slug, "Gear")
            bundle = Bundle(
                title=title, slug=slugify(title),
                description=("A package of items sold together at a kit price. "
                             "Each item in the kit is listed below."),
                image_path=chosen[0].image_path,
                bundle_price=round(total * 0.93, 2), list_price=round(total, 2),
                badge="Kit price", audience=shelf_label,
                featured=number == 0,
            )
            db.session.add(bundle)
            db.session.flush()
            for item in chosen:
                db.session.add(BundleItem(bundle_id=bundle.id, product_id=item.id, quantity=1))

    db.session.commit()


def distinct_picks(shelf: list, purpose: str, key: str, count: int) -> list:
    """Choose `count` products that a shopper would plausibly have saved together.

    Two colour or kit variants of the same product share a name prefix; picking
    them into one cart or wishlist looks like a data bug, so the prefix must be
    new each time.
    """
    chosen, prefixes = [], set()
    if not shelf:
        return chosen
    for offset in range(len(shelf)):
        product = shelf[(digest(purpose, key, offset)) % len(shelf)]
        prefix = " ".join(product.name.split()[:4]).lower()
        if prefix in prefixes or any(product.id == item.id for item in chosen):
            continue
        prefixes.add(prefix)
        chosen.append(product)
        if len(chosen) == count:
            break
    return chosen


def seed_benchmark_users(db, models):
    User = models["User"]
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    Address = models["Address"]
    CartItem = models["CartItem"]
    WishlistItem = models["WishlistItem"]
    CompareItem = models["CompareItem"]
    Order = models["Order"]
    OrderItem = models["OrderItem"]
    StoreReservation = models["StoreReservation"]
    StoreLocation = models["StoreLocation"]
    Product = models["Product"]

    store = StoreLocation.query.order_by(StoreLocation.id).first()
    products = Product.query.order_by(Product.id).all()
    if not products:
        return

    # Each account is anchored on one department so its saved state is coherent.
    departments = sorted({product.top_category_slug for product in products})
    created_users = []
    for index, entry in enumerate(USER_DEFS):
        user = User(
            email=entry["email"], username=entry["username"], display_name=entry["display_name"],
            phone=f"(555) 200-01{index + 1:02d}", company=entry["company"], role=entry["role"],
            preferred_store_id=store.id if store else None,
            newsletter_opt_in=index % 2 == 0, sms_opt_in=index in (1, 3),
            created_at=MIRROR_REFERENCE_DATE - timedelta(days=120 - index * 11),
        )
        user.password_hash = deterministic_password_hash(BENCHMARK_PASSWORD, entry["email"])
        db.session.add(user)
        db.session.flush()
        created_users.append(user)
        db.session.add(Address(
            user_id=user.id, label="Studio", recipient=user.display_name,
            line1=f"{100 + index * 11} Benchmark Ave",
            city=["New York", "Brooklyn", "Austin", "Los Angeles"][index],
            state=["NY", "NY", "TX", "CA"][index],
            zip_code=["10001", "11217", "78701", "90013"][index],
            phone=user.phone, is_default=True,
        ))
    db.session.flush()

    for index, user in enumerate(created_users):
        department = departments[index % len(departments)]
        shelf = [p for p in products if p.top_category_slug == department]
        # a small department (Drones carries three variants of one camera) cannot
        # fill a distinct cart and wishlist, so widen to the whole catalog
        if len(shelf) < 8:
            shelf = products
        shelf = sorted(shelf, key=lambda p: p.id)

        wished = distinct_picks(shelf, "wish", user.email, 3)
        for offset, product in enumerate(wished):
            db.session.add(WishlistItem(user_id=user.id, product_id=product.id,
                                        created_at=MIRROR_REFERENCE_DATE - timedelta(days=9 + offset)))

        for offset, product in enumerate(distinct_picks(shelf, "compare", user.email, 3)):
            db.session.add(CompareItem(user_id=user.id, product_id=product.id,
                                       created_at=MIRROR_REFERENCE_DATE - timedelta(days=5 + offset)))

        for offset, product in enumerate(distinct_picks(shelf, "cart", user.email, 2)):
            db.session.add(CartItem(user_id=user.id, product_id=product.id,
                                    quantity=1 + (digest("qty", user.email, offset) % 2),
                                    variant_label="", bundle_label="",
                                    added_at=MIRROR_REFERENCE_DATE - timedelta(days=3 + offset)))
        db.session.flush()

        # one delivered order and, for half the accounts, one still processing
        statuses = [("Delivered", "Ship to address", 40 + index * 3)]
        if index % 2 == 1:
            statuses.append(("Processing", "Store pickup", 5 + index))
        for number, (status, fulfillment, days_ago) in enumerate(statuses):
            items = distinct_picks(shelf, f"order{number}", user.email, 2)
            subtotal = round(sum(item.price for item in items), 2)
            if subtotal <= 0:
                continue
            placed = MIRROR_REFERENCE_DATE - timedelta(days=days_ago)
            order = Order(
                user_id=user.id,
                order_number=f"BH-{placed.strftime('%Y%m%d')}-{user.id:02d}{number:02d}",
                status=status, subtotal=subtotal, shipping=0.0,
                tax=round(subtotal * 0.08875, 2), total=round(subtotal * 1.08875, 2),
                fulfillment=fulfillment, payment_label="Demo Visa ending in 4242",
                note="", created_at=placed,
            )
            db.session.add(order)
            db.session.flush()
            for item in items:
                db.session.add(OrderItem(
                    order_id=order.id, product_id=item.id, product_name=item.name,
                    image_path=item.image_path, quantity=1, price=item.price, variant_label="",
                ))

        if store and index % 2 == 0:
            product = shelf[(digest("reserve", user.email)) % len(shelf)]
            db.session.add(StoreReservation(
                user_id=user.id, store_id=store.id, product_id=product.id, quantity=1,
                status="Reserved", pickup_window="Ready in 2 hours",
                created_at=MIRROR_REFERENCE_DATE - timedelta(days=2 + index),
            ))

    db.session.commit()

    canonicalize(db)


def canonicalize(db):
    """Make a fresh build byte-comparable with the previous one.

    Two effects are normalised here. SQLAlchemy emits index DDL in set order, so
    `sqlite_master` can list the same indexes in a different sequence between
    runs, and identical rows can land in a different page layout. Recreating the
    indexes by name and then rewriting the file with VACUUM removes both, which
    is what lets a maintainer regenerate the shipped database and compare it.

    This runs only on a build that actually seeded. Both seed entry points
    early-return on a populated database, so a container boot or a `/reset`
    (which copies the already-populated seed file) never reaches here and never
    rewrites the runtime database.
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
