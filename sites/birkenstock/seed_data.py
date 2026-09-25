"""Deterministic BIRKENSTOCK seed data.

Runs at every container boot and every /reset/birkenstock. Each seed function
early-returns on a populated DB so re-seeding is a no-op and the byte-identical
reset invariant holds.

Content sourcing: the catalog (products, prices, colors, categories, stores,
policy copy, VIP program terms) mirrors the upstream birkenstock.com US
storefront via the committed scrape-derived literals in _seed_catalog.py,
_seed_categories.py, _seed_stores.py and _seed_materials.py. Review prose and
benchmark users are original fixtures written for this mirror.
"""
import json
from datetime import datetime, timedelta

# Mirrors app.REFERENCE_DATE; defined locally so seed_data never imports app at
# module load time (app imports seed_data at its bootstrap, a top-level
# cross-import would be circular).
REFERENCE_DATE = datetime(2026, 9, 21, 12, 0, 0)

from _seed_catalog import PRODUCTS
from _seed_categories import CATEGORIES
from _seed_stores import STORES
from _seed_materials import MATERIALS

PASSWORD = "TestPass123!"

USERS = [
    {"first_name": "Alice", "last_name": "Johnson", "email": "alice.j@test.com"},
    {"first_name": "Bob", "last_name": "Chen", "email": "bob.c@test.com"},
    {"first_name": "Carol", "last_name": "Davis", "email": "carol.d@test.com"},
    {"first_name": "David", "last_name": "Kim", "email": "david.k@test.com"},
]

PROFILES = [
    {"phone": "212-555-0143", "address1": "48 Sheridan Square", "address2": "Apt 4B",
     "city": "New York", "state": "NY", "zip_code": "10014"},
    {"phone": "312-555-0187", "address1": "1645 N Damen Ave", "address2": "Unit 2",
     "city": "Chicago", "state": "IL", "zip_code": "60647"},
    {"phone": "415-555-0122", "address1": "733 Hayes St", "address2": "",
     "city": "San Francisco", "state": "CA", "zip_code": "94117"},
    {"phone": "206-555-0168", "address1": "1100 Bellevue Way NE", "address2": "Apt 1208",
     "city": "Bellevue", "state": "WA", "zip_code": "98004"},
]

PAYMENT_METHODS = [
    {"label": "Visa", "last_four": "4242", "exp_month": 8, "exp_year": 2029},
    {"label": "Mastercard", "last_four": "5309", "exp_month": 3, "exp_year": 2027},
    {"label": "Visa", "last_four": "1881", "exp_month": 11, "exp_year": 2028},
    {"label": "Amex", "last_four": "3007", "exp_month": 5, "exp_year": 2030},
]

# Original review fixtures. Personas are fictional; prose is written for this
# mirror in the register of real Birkenstock customer reviews.
REVIEW_POOL = [
    ("Second pair, same comfort", "This is my second pair of the same model and they feel exactly like the first: the cork footbed molds to your foot after a few days and then it is hard to wear anything else."),
    ("True to size for me", "I used the size chart on the fitting guide page and the EU conversion was spot on. I ordered my usual US size and the fit is perfect with room for my toes."),
    ("Break them in slowly", "Day one felt firm, day five felt custom made. I would give them a week of short wears before a full day on your feet."),
    ("The footbed is the reason", "I keep trying other sandals and coming back. Nothing else supports my arch like the cork footbed. This color goes with everything too."),
    ("Worth every penny", "Yes they cost more than drugstore sandals. They also last years, and my posture on long walks is noticeably better."),
    ("Buckle detail is beautiful", "The hardware feels solid and the strap adjusts enough for my narrow feet. Medium/Narrow width was the right call for me."),
    ("Great for long days", "I wear these for nine hour shifts on concrete. My feet still hurt a little by the end, but far less than in any other shoe I have tried."),
    ("Beautiful leather", "The upper is clearly real leather and smells like it. It scuffs a little but that just makes them look better in my opinion."),
    ("Easy order, quick delivery", "Ground shipping took three days for me. Order status page showed the tracking number the same evening."),
    ("Gift for my husband, big hit", "He has worn them every day since. I sized up half a size based on the reviews and that worked for him."),
    ("Perfect garden shoe", "I wanted something I could hose off. These take water, dry fast, and still have the contoured footbed. Exactly what I hoped."),
    ("Narrow feet approved", "Regular widths always flop on my heels. The Medium/Narrow fit grips properly and the strap lets me fine tune."),
    ("The color is stunning", "Photos do not oversell this colorway. It is deep and even and has not faded after a summer of sun."),
    ("Arch support that actually works", "My podiatrist told me to stop wearing flat flip flops. These were the compromise and my plantar fasciitis has been quiet since."),
    ("Runs slightly roomy", "I have a high instep and these are roomy even in my normal size. If you are between sizes consider the narrower width instead of sizing down."),
    ("Two years and counting", "Updating my old review: two years of near daily wear, one resole, still going. These are the last sandals I will need for a while."),
    ("So comfortable out of the box", "No break in needed for me with the soft footbed version. Wore them to a street fair the first day, eight hours, zero regrets."),
    ("Classy enough for the office", "I wear these with trousers to work in the summer. Nobody blinks and my feet are happy all day."),
    ("Sturdy buckles", "The buckles hold their position. My previous pair from another brand kept slipping. These stay where you set them."),
    ("Great with socks", "Clogs plus wool socks is my winter uniform now. Yes I got looks. Yes it was worth it."),
]

REVIEW_NAMES = [
    "Marta L.", "Jonas K.", "Priya S.", "Diego R.", "Emma W.", "Tomas B.",
    "Ingrid F.", "Malik J.", "Sofia P.", "Hannah T.", "Ravi N.", "Clara M.",
    "Owen D.", "Lena V.", "Andre G.", "Nora H.", "Felix A.", "Maya C.",
    "Simon E.", "Alma R.",
]


def _rating_for(product, index):
    """Deterministic per-review rating that averages near the real product rating."""
    base = product.rating or 4.5
    options = [5, 4, 5, 5, 4, 3, 5, 4, 5, 2]
    r = options[(index * 7 + product.id) % len(options)]
    if base >= 4.6 and r < 4:
        r = 5 if (index + product.id) % 2 else 4
    if base <= 3.2 and r > 3:
        r = 3 if (index + product.id) % 2 else 2
    return r


def _reviews_for(product, Review):
    """2-4 visible reviews per reviewed product, deterministic from product id.
    Products whose upstream PDP shows no review count get no fixture reviews."""
    if not product.review_count:
        return []
    count = 2 + (product.id % 3)
    rows = []
    for i in range(count):
        title, body = REVIEW_POOL[(product.id * 3 + i) % len(REVIEW_POOL)]
        days_ago = 11 * (i + 1) + (product.id % 27)
        rows.append(Review(
            product_id=product.id,
            author=REVIEW_NAMES[(product.id + i * 5) % len(REVIEW_NAMES)],
            rating=_rating_for(product, i),
            title=title,
            body=body,
            created_at=REFERENCE_DATE - timedelta(days=days_ago),
            verified=(i + product.id) % 4 != 3,
        ))
    return rows


def seed_database(db, Category, Product, ProductCategory, Review, Store):
    if Product.query.count() > 0:
        return

    categories = {}
    for sort, (slug, name, parent, blurb) in enumerate(CATEGORIES):
        category = Category(slug=slug, name=name, parent_slug=parent,
                            blurb=blurb, sort=sort)
        db.session.add(category)
        categories[slug] = category
    db.session.flush()

    for row in PRODUCTS:
        (pid, master, slug, name, model, material, color, color_id, price,
         list_price, badge, gender, style_type, collection, art_no, item_no,
         description, rating, review_count, size_group, categories_slugs,
         images) = row
        material_blocks = MATERIALS.get(material, [])
        one_size = set(categories_slugs) <= {"foot-care"}
        product = Product(
            pid=pid, master_pid=master, slug=slug, name=name, model=model,
            material=material, color=color, color_id=color_id,
            price=price, list_price=list_price or 0.0, badge=badge or "",
            gender=gender, style_type=style_type, collection=collection,
            art_no=art_no, item_no=item_no, description=description,
            material_details=json.dumps(material_blocks),
            images_json=json.dumps(images),
            rating=rating or 0.0, review_count=review_count or 0,
            size_group=size_group, stock=24, one_size=one_size,
            homepage=(badge in ("Bestseller", "") and price >= 100),
        )
        db.session.add(product)
        db.session.flush()
        for cslug in categories_slugs:
            if cslug in categories:
                db.session.add(ProductCategory(
                    product_id=product.id, category_id=categories[cslug].id))
        for review in _reviews_for(product, Review):
            db.session.add(review)

    for city, address in STORES:
        db.session.add(Store(city=city, address=address))

    db.session.commit()


def seed_benchmark_users(db, User, CartItem, WishlistItem, Order, OrderItem,
                         PaymentMethod, Product, bcrypt):
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    users = []
    for i, spec in enumerate(USERS):
        user = User(
            email=spec["email"],
            first_name=spec["first_name"],
            last_name=spec["last_name"],
            phone=PROFILES[i]["phone"],
            address1=PROFILES[i]["address1"],
            address2=PROFILES[i]["address2"],
            city=PROFILES[i]["city"],
            state=PROFILES[i]["state"],
            zip_code=PROFILES[i]["zip_code"],
            vip_points=25,  # welcome points; purchase points added below
            lifetime_spend=0.0,
        )
        user.password_hash = bcrypt.generate_password_hash(PASSWORD).decode("utf-8")
        db.session.add(user)
        users.append(user)
    db.session.flush()

    all_products = Product.query.order_by(Product.id).all()
    assert all_products, "catalog must be seeded before benchmark users"

    for i, user in enumerate(users):
        # payment method
        pm = PAYMENT_METHODS[i]
        db.session.add(PaymentMethod(
            user_id=user.id, label=pm["label"], last_four=pm["last_four"],
            holder=user.first_name + " " + user.last_name,
            exp_month=pm["exp_month"], exp_year=pm["exp_year"], is_default=True))

        # cart: 2-3 items
        for k in range(2 + i % 2):
            product = all_products[(i * 97 + k * 41) % len(all_products)]
            size = "One size" if product.one_size else next(
                s for s in product.sizes if product.size_available(s))
            db.session.add(CartItem(
                user_id=user.id, product_id=product.id, size=size,
                width="Regular/Wide", quantity=1 + k % 2))

        # wishlist: 3-5 items
        for k in range(3 + i % 3):
            product = all_products[(i * 53 + k * 89) % len(all_products)]
            exists = WishlistItem.query.filter_by(
                user_id=user.id, product_id=product.id).first()
            if not exists:
                db.session.add(WishlistItem(user_id=user.id, product_id=product.id))

        # order history: 1-2 past orders
        for order_index in range(1 + i % 2):
            created = REFERENCE_DATE - timedelta(days=12 * (order_index + 1) + i)
            picks = [
                all_products[(i * 31 + order_index * 17) % len(all_products)],
                all_products[(i * 67 + order_index * 29 + 3) % len(all_products)],
            ]
            subtotal = 0.0
            items = []
            for j, product in enumerate(picks):
                size = "One size" if product.one_size else next(
                    s for s in product.sizes if product.size_available(s))
                qty = 1 if j else 2
                subtotal += product.price * qty
                items.append((product, size, qty))
            subtotal = round(subtotal, 2)
            shipping = 0.0 if subtotal >= 200 else 7.95
            tax = round(subtotal * 0.08875, 2)
            total = round(subtotal + shipping + tax, 2)
            order = Order(
                order_no=f"US-{created.strftime('%Y%m%d')}-{i * 10 + order_index + 1:05d}",
                user_id=user.id,
                status="Delivered" if order_index == 0 else "Shipped",
                email=user.email,
                ship_name=f"{user.first_name} {user.last_name}",
                ship_address1=user.address1,
                ship_address2=user.address2,
                ship_city=user.city,
                ship_state=user.state,
                ship_zip=user.zip_code,
                payment_label=PAYMENT_METHODS[i]["label"],
                payment_last_four=PAYMENT_METHODS[i]["last_four"],
                shipping_method="Ground Shipping",
                shipping_cost=shipping,
                subtotal=subtotal,
                tax=tax,
                total=total,
                points_earned=int(subtotal),
                tracking_no=f"1Z{900000000 + i * 12345 + order_index * 7}BIRK{100 + i}",
                created_at=created,
            )
            for product, size, qty in items:
                order.items.append(OrderItem(
                    product_id=product.id, name=product.name,
                    model=product.model, color=product.color, size=size,
                    width="Regular/Wide" if (product.id + i) % 2 else "Medium/Narrow",
                    price=product.price, quantity=qty,
                    image=product.main_image))
            db.session.add(order)

    # VIP accrual: 1 point per $1 of seeded lifetime spend, plus 25 for joining.
    for user in users:
        spend = round(sum(o.subtotal for o in user.orders), 2)
        user.lifetime_spend = spend
        user.vip_points = 25 + int(spend)

    db.session.commit()
