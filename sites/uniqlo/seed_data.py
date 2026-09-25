"""Build-time seed for the UNIQLO mirror.

Reads scraped_data/products_raw.jsonl (real product data captured from
uniqlo.com via Playwright — see scraped_data/scrape.py) and materializes
it into Category / Product / ProductVariant / Review rows. Copies the
real product photos captured alongside it into static/images/.

Idempotency lives in app.py (seed_database / seed_benchmark_users each
early-return on a populated table) — this module just does the work.
"""
import json
import os
import random
import re
import shutil
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPED_JSONL = os.path.join(BASE_DIR, 'scraped_data', 'products_raw.jsonl')
SCRAPED_IMG_DIR = os.path.join(BASE_DIR, 'scraped_data', 'images')
STATIC_IMG_DIR = os.path.join(BASE_DIR, 'static', 'images')


def _slugify(text, suffix):
    s = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return f"{s}-{suffix.lower()}"[:200]


def _load_records():
    with open(SCRAPED_JSONL) as f:
        return [json.loads(line) for line in f if line.strip()]


def _copy_images(pgid, slug):
    """Copy scraped_data/images/<pgid>/*.jpg into static/images/<slug>/, return relative paths."""
    src_dir = os.path.join(SCRAPED_IMG_DIR, pgid)
    if not os.path.isdir(src_dir):
        return []
    dest_dir = os.path.join(STATIC_IMG_DIR, slug)
    os.makedirs(dest_dir, exist_ok=True)
    rel_paths = []
    for fname in sorted(os.listdir(src_dir)):
        if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        src = os.path.join(src_dir, fname)
        dest = os.path.join(dest_dir, fname)
        if not os.path.exists(dest):
            shutil.copyfile(src, dest)
        rel_paths.append(f'images/{slug}/{fname}')
    return rel_paths


def run_seed(db, Category, Product, ProductVariant, Review):
    records = _load_records()

    # ---- categories ----
    seen_cats = {}
    for r in records:
        key = (r['department'], r['category_slug'])
        if key not in seen_cats:
            seen_cats[key] = r['category_name']
    for (dept, slug), name in seen_cats.items():
        db.session.add(Category(department=dept, slug=slug, name=name))
    db.session.flush()

    # ---- products / variants / reviews ----
    used_slugs = set()
    for r in records:
        base_slug = _slugify(r['name'] or r['product_group_id'], r['product_group_id'])
        slug = base_slug
        n = 2
        while slug in used_slugs:
            slug = f"{base_slug}-{n}"
            n += 1
        used_slugs.add(slug)

        images = _copy_images(r['product_group_id'], slug)
        rating_info = r.get('rating') or {}

        variants_raw = r.get('variants') or []
        prices = [float(v['offers']['price']) for v in variants_raw if v.get('offers', {}).get('price')]
        min_price = min(prices) if prices else 0.0
        max_price = max(prices) if prices else 0.0

        product = Product(
            product_group_id=r['product_group_id'],
            name=r['name'] or r['product_group_id'],
            slug=slug,
            department=r['department'],
            category_slug=r['category_slug'],
            category_name=r['category_name'],
            description=r.get('description') or '',
            material=r.get('material') or '',
            image=images[0] if images else '',
            gallery_images=json.dumps(images),
            min_price=min_price,
            max_price=max_price,
            rating=float(rating_info.get('ratingValue') or 0.0),
            review_count=int(rating_info.get('reviewCount') or 0),
            upstream_url=r.get('url') or '',
        )
        db.session.add(product)
        db.session.flush()

        seen_skus = set()
        for v in variants_raw:
            sku = v.get('sku')
            if not sku or sku in seen_skus:
                continue
            seen_skus.add(sku)
            offer = v.get('offers') or {}
            price = float(offer.get('price') or min_price or 0.0)
            db.session.add(ProductVariant(
                product_id=product.id,
                sku=sku,
                color=v.get('color') or '',
                size=v.get('size') or '',
                price=price,
                in_stock=(offer.get('availability', '').endswith('InStock')),
            ))
        # Guarantee at least one purchasable variant even if scrape found none.
        if not seen_skus:
            db.session.add(ProductVariant(
                product_id=product.id, sku=f"{r['product_group_id']}-DEFAULT",
                color='Default', size='ONE SIZE', price=min_price or 19.9, in_stock=True,
            ))

        for i, rv in enumerate(r.get('reviews') or []):
            author = (rv.get('author') or {}).get('name') or 'UNIQLO Customer'
            rating_val = (rv.get('reviewRating') or {}).get('ratingValue') or 5
            try:
                created = datetime.strptime(rv.get('datePublished', ''), '%Y-%m-%d')
            except ValueError:
                created = datetime.utcnow() - timedelta(days=random.randint(1, 400))
            db.session.add(Review(
                product_id=product.id,
                author_name=author,
                rating=int(rating_val),
                title=rv.get('name') or '',
                body=rv.get('reviewBody') or '',
                created_at=created,
            ))

    db.session.commit()


BENCHMARK_USERS = [
    {'name': 'Alice Johnson', 'email': 'alice.j@test.com', 'password': 'TestPass123!',
     'phone': '415-555-0101', 'city': 'San Francisco', 'state': 'CA', 'zip_code': '94102',
     'address_line1': '456 Oak Ave'},
    {'name': 'Bob Chen', 'email': 'bob.c@test.com', 'password': 'TestPass123!',
     'phone': '512-555-0202', 'city': 'Austin', 'state': 'TX', 'zip_code': '78701',
     'address_line1': '789 Pine St'},
    {'name': 'Carol Davis', 'email': 'carol.d@test.com', 'password': 'TestPass123!',
     'phone': '212-555-0303', 'city': 'New York', 'state': 'NY', 'zip_code': '10001',
     'address_line1': '321 Broadway'},
    {'name': 'David Kim', 'email': 'david.k@test.com', 'password': 'TestPass123!',
     'phone': '312-555-0404', 'city': 'Chicago', 'state': 'IL', 'zip_code': '60601',
     'address_line1': '555 Michigan Ave'},
]


def run_seed_users(db, User, CartItem, WishlistItem, Order, OrderItem, ProductVariant, Product):
    created = []
    for u in BENCHMARK_USERS:
        user = User(
            name=u['name'], email=u['email'], phone=u['phone'], city=u['city'],
            state=u['state'], zip_code=u['zip_code'], address_line1=u['address_line1'],
        )
        user.set_password(u['password'])
        db.session.add(user)
        created.append(user)
    db.session.flush()
    alice, bob, carol, david = created

    variants = ProductVariant.query.order_by(ProductVariant.id).limit(400).all()
    if not variants:
        db.session.commit()
        return

    def _order(user, status, picks, days_ago):
        items = []
        subtotal = 0.0
        for variant, qty in picks:
            items.append((variant, qty))
            subtotal += variant.price * qty
        order = Order(
            user_id=user.id, order_number=f'UQ{random.randint(10**9, 10**10 - 1)}',
            status=status, subtotal=round(subtotal, 2), shipping=0.0 if subtotal >= 99 else 4.99,
            tax=round(subtotal * 0.08, 2),
            total=round(subtotal * 1.08 + (0.0 if subtotal >= 99 else 4.99), 2),
            ship_name=user.name, ship_address=user.address_line1, ship_city=user.city,
            ship_state=user.state, ship_zip=user.zip_code,
            created_at=datetime.utcnow() - timedelta(days=days_ago),
        )
        db.session.add(order)
        db.session.flush()
        for variant, qty in items:
            db.session.add(OrderItem(
                order_id=order.id, product_id=variant.product_id,
                product_name=variant.product.name, product_image=variant.product.image,
                color=variant.color, size=variant.size, quantity=qty, price=variant.price,
            ))
        return order

    rng = random.Random(42)
    v1, v2, v3, v4, v5, v6 = rng.sample(variants, 6)
    _order(alice, 'delivered', [(v1, 1), (v2, 2)], days_ago=20)
    _order(alice, 'shipped', [(v3, 1)], days_ago=3)
    _order(bob, 'delivered', [(v4, 1)], days_ago=45)
    _order(carol, 'processing', [(v5, 2)], days_ago=1)
    _order(david, 'cancelled', [(v6, 1)], days_ago=10)

    # Pre-seeded cart + wishlist for Alice, for cart-modification tasks.
    cart_variants = rng.sample(variants, 2)
    for v in cart_variants:
        db.session.add(CartItem(user_id=alice.id, variant_id=v.id, quantity=1))
    wishlist_products = Product.query.order_by(Product.id).limit(20).all()
    for p in rng.sample(wishlist_products, 3):
        db.session.add(WishlistItem(user_id=alice.id, product_id=p.id))

    db.session.commit()
