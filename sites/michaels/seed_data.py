"""Build-time seed for the Michaels mirror.

Reads source_data.json (real catalog data captured from michaels.com — see
provenance.json) and materializes it into Category / Product / ProductVariant /
Review / Question / Store / Coupon / ClassEvent rows, plus four benchmark
users with pre-populated carts, wishlists, addresses, cards and orders.

Deterministic: no wall clock, no random, no hash-order dependence. The
benchmark password hash is frozen so rebuilds are byte-identical.

Idempotency lives at the function level (each seed_* early-returns on a
populated DB) — wired from app.py's bootstrap.
"""
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(BASE_DIR, 'source_data.json')

# bcrypt hash of 'TestPass123!' (cost 12), frozen for byte-identical rebuilds.
FROZEN_PASSWORD_HASH = '$2b$12$WtOBgikyE24OU/kuhls4Fuy1s2Kuz/osD0cproGZjpkL713kWy58q'

REFERENCE_DATE = '2026-09-23'


def _slugify(text, suffix):
    s = re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')
    return f"{s}-{suffix.lower()}"[:200]


def _load():
    with open(SOURCE, encoding='utf-8') as f:
        return json.load(f)


def run_seed(db, Category, Product, ProductVariant, Review, Question,
             Store, Coupon, ClassEvent):
    """Materialize catalog rows. Called by app.seed_database()."""
    if Product.query.count() > 0:
        return

    data = _load()

    # ---- categories ----
    cat_by_slug = {}
    for i, top in enumerate(data['top_categories']):
        row = Category(slug=top['slug'], name=top['name'], top_slug='', sort=i)
        db.session.add(row)
        cat_by_slug[('', top['slug'])] = row
    # subcategories from nav (only populated ones are in nav)
    nav = {n['slug']: n for n in data['nav']}
    for j, top in enumerate(data['top_categories']):
        n = nav.get(top['slug'], {})
        for k, sub in enumerate(n.get('subcategories', [])):
            row = Category(slug=sub['slug'], name=sub['name'],
                           top_slug=top['slug'], sort=k)
            db.session.add(row)
            cat_by_slug[(top['slug'], sub['name'].lower())] = row
    db.session.flush()

    # ---- products ----
    products_by_sku = {}
    for idx, rec in enumerate(data['products']):
        sub = cat_by_slug.get((rec['top_categories'][0], (rec['sub_category'] or '').lower()))
        p = Product(
            sku=rec['sku'],
            slug=_slugify(rec['name'], rec['sku']),
            name=rec['name'],
            brand=rec.get('brand', ''),
            subcategory_id=sub.id if sub else None,
            description=rec.get('description', ''),
            details=json.dumps(rec.get('details', []), ensure_ascii=False),
            price=rec['price'], price_low=rec['price_low'], price_high=rec['price_high'],
            unit_price=rec.get('unit_price', ''),
            promo_text=rec.get('promo_text', ''),
            promo_type=rec.get('promo_type', ''),
            rating=rec.get('rating', 0.0),
            review_count=rec.get('review_count', 0),
            rating_dist=json.dumps({str(d['key']): d['count'] for d in dist}, ensure_ascii=False)
                             if (dist := (data.get('reviews', {}).get(rec['sku'], {}) or {}).get('distribution')) else '{}',
            color=rec.get('color', ''),
            varies_by=rec.get('varies_by', 'color'),
            images=json.dumps([f"products/{i}" for i in rec.get('images', [])]),
            is_bestseller=rec.get('is_bestseller', False),
            is_new=rec.get('is_new', False),
            is_clearance=rec.get('is_clearance', False),
            is_online_only=rec.get('online_only', False),
            aisle=f"aisle {(idx % 40) + 1}",
            upstream_url=f"https://www.michaels.com{rec.get('href', '')}",
            sort=idx,
        )
        db.session.add(p)
        db.session.flush()
        products_by_sku[rec['sku']] = p
        for v in rec.get('variants', []):
            db.session.add(ProductVariant(
                product_id=p.id, sku=v.get('sku') or f"{rec['sku']}V{len(p.variants) + 1}",
                color=v.get('color', ''), price=v.get('price', rec['price']),
                availability=v.get('availability', 'InStock')))
        db.session.flush()
    db.session.flush()

    # extra top-category membership is implicit via subcategory; products with
    # several top categories are reachable through search and bestseller rails.

    # ---- reviews ----
    for pid, block in data.get('reviews', {}).items():
        p = products_by_sku.get(pid)
        if not p:
            continue
        for r in block.get('reviews', []):
            db.session.add(Review(
                product_id=p.id, author=r.get('author') or 'Michaels Shopper',
                rating=r.get('rating') or 5, title=r.get('title') or '',
                text=r.get('text') or '', date=r.get('date') or '2026-08-01',
                verified=bool(r.get('verified')), helpful_count=r.get('helpful', 0)))
    # ---- questions ----
    for pid, qs in data.get('questions', {}).items():
        p = products_by_sku.get(pid)
        if not p:
            continue
        for q in qs:
            db.session.add(Question(
                product_id=p.id, author=q.get('author') or 'Anonymous',
                text=q.get('q') or '', date=q.get('date') or '2026-07-01',
                answer_count=q.get('answers', 0)))

    # ---- stores ----
    for s in data['stores']:
        db.session.add(Store(
            number=s['store_id'], name=s['name'], address=s['address'],
            city=s['city'], state=s['state'], zip=s['zip'], phone=s['phone'],
            hours=s['hours'], services=json.dumps(s.get('services', {})),
            lat=s.get('lat') or 0.0, lon=s.get('lon') or 0.0))
    db.session.flush()

    # ---- coupons ----
    for c in data['coupons']:
        db.session.add(Coupon(
            code=c.get('code'), headline=c['headline'], scope=c['scope'],
            channel=c.get('channel', 'both'), valid_from=c['valid_from'],
            valid_to=c['valid_to'], description=c.get('description', '')))

    # ---- classes ----
    class_imgs = sorted(os.listdir(os.path.join(BASE_DIR, 'static', 'images', 'classes')))
    class_imgs = [f'classes/{f}' for f in class_imgs if f.endswith('.jpg')]
    for i, c in enumerate(data['live_classes']):
        db.session.add(ClassEvent(
            kind='live', title=c['title'], category=c['category'], date=c['date'],
            time_text=c['time'], platform=c['platform'], host=c.get('host', ''),
            image=class_imgs[i % len(class_imgs)] if class_imgs else ''))
    for i, t in enumerate(data['tutorials']):
        db.session.add(ClassEvent(
            kind='tutorial', title=t['title'], category=t['category'],
            duration=t['duration'], is_new=bool(t.get('is_new')),
            image=class_imgs[(i + 3) % len(class_imgs)] if class_imgs else ''))

    db.session.commit()


def run_seed_users(db, User, Address, PaymentCard, CartItem, WishlistItem,
                   Order, OrderItem, Product):
    """Materialize benchmark users and their data. Called by app.seed_benchmark_users()."""
    if User.query.filter_by(email='alice.j@test.com').first():
        return

    data = _load()
    products = {}
    for p in Product.query.order_by(Product.sort).all():
        products[p.sku] = p

    USERS = [
        {'username': 'alice_j', 'email': 'alice.j@test.com', 'display_name': 'Alice Johnson'},
        {'username': 'bob_c', 'email': 'bob.c@test.com', 'display_name': 'Bob Chen'},
        {'username': 'carol_d', 'email': 'carol.d@test.com', 'display_name': 'Carol Davis'},
        {'username': 'david_k', 'email': 'david.k@test.com', 'display_name': 'David Kim'},
    ]
    for u in USERS:
        user = User(email=u['email'], name=u['display_name'])
        user.password_hash = FROZEN_PASSWORD_HASH
        user.phone = '(206) 555-0183'
        db.session.add(user)
    db.session.flush()

    alice, bob, carol, david = User.query.filter(User.email.in_(
        ['alice.j@test.com', 'bob.c@test.com', 'carol.d@test.com', 'david.k@test.com'])).all()
    by_email = {u.email: u for u in (alice, bob, carol, david)}

    def addr(user, label, line1, city, state, zip_code, default=False):
        row = Address(user_id=user.id, label=label, line1=line1, city=city,
                      state=state, zip_code=zip_code, is_default=default)
        db.session.add(row)
        return row

    addr(alice, 'Home', '1420 Rainier Ave S', 'Seattle', 'WA', '98144', True)
    addr(alice, 'Work', '2201 Westlake Ave', 'Seattle', 'WA', '98121')
    addr(bob, 'Home', '305 Bleecker St, Apt 4B', 'New York', 'NY', '10014', True)
    addr(carol, 'Home', '812 Sundance Way', 'Austin', 'TX', '78701', True)
    addr(david, 'Home', '445 N Canyons Pkwy', 'Livermore', 'CA', '94551', True)

    def card(user, label, brand, last4, mm, yy, default=False):
        row = PaymentCard(user_id=user.id, label=label, brand=brand, last4=last4,
                          exp_month=mm, exp_year=yy, is_default=default)
        db.session.add(row)
        return row

    card(alice, 'Personal', 'Visa', '4242', 8, 2027, True)
    card(alice, 'Backup', 'Mastercard', '5309', 3, 2028)
    card(bob, 'Personal', 'Amex', '0005', 11, 2027, True)
    card(carol, 'Personal', 'Visa', '1881', 5, 2029, True)
    card(david, 'Personal', 'Discover', '6442', 1, 2028, True)
    db.session.flush()

    # ---- carts (2-4 items each) ----
    # (product_sku, variant_index, qty): variant_index picks a real variant row
    cart_specs = {
        'alice.j@test.com': [('10472532', 0, 2), ('10131611', 0, 1), ('10084039', 0, 3)],
        'bob.c@test.com': [('10281316', 0, 1), ('10061591', 0, 2), ('10764419', 0, 1)],
        'carol.d@test.com': [('10259823', 0, 6), ('10213118', 0, 2), ('10118272', 0, 1)],
        'david.k@test.com': [('10217915', 0, 1), ('10445402', 0, 2)],
    }
    for email, specs in cart_specs.items():
        user = by_email[email]
        for sku, vindex, qty in specs:
            p = products.get(sku)
            if not p:
                continue
            vs = ''
            color = ''
            variants = sorted(p.variants, key=lambda v: (v.price, v.sku))
            if variants:
                v = variants[min(vindex, len(variants) - 1)]
                vs = v.sku
                color = v.color
            db.session.add(CartItem(user_id=user.id, product_id=p.id,
                                    variant_sku=vs, color=color, qty=qty))
    db.session.flush()

    # ---- wishlists (3-6 items) ----
    wl_specs = {
        'alice.j@test.com': ['MP240782', '10672808', '10472541', '10574554'],
        'bob.c@test.com': ['10131568', '10131569', '10187423'],
        'carol.d@test.com': ['10276631', '10473166', '10110205', '10542383'],
        'david.k@test.com': ['10264009', '10273691', '10473524'],
    }
    for email, skus in wl_specs.items():
        user = by_email[email]
        for sku in skus:
            p = products.get(sku)
            if p:
                db.session.add(WishlistItem(user_id=user.id, product_id=p.id))

    # ---- order history (1-3 past orders each) ----
    def make_order(user, number, days_ago, method, addr_line, items, status, code=''):
        placed = f'2026-09-{max(1, 23 - days_ago):02d}'
        subtotal = sum(q * u for _, _, q, u in items)
        discount = round(subtotal * 0.30, 2) if code == 'GETMY30' else 0.0
        shipping = 0.0 if method == 'Pickup' or (subtotal - discount) >= 49 else 5.99
        tax = round((subtotal - discount) * 0.0925, 2)
        total = round(subtotal - discount + shipping + tax, 2)
        order = Order(user_id=user.id, order_number=number, status=status,
                      placed_at=placed, delivery_method=method, address_line=addr_line,
                      card_brand='Visa', card_last4='4242',
                      subtotal=round(subtotal, 2), discount=discount,
                      shipping=round(shipping, 2), tax=tax, total=total,
                      promo_code=code)
        db.session.add(order)
        db.session.flush()
        for pid, color, qty, unit in items:
            db.session.add(OrderItem(order_id=order.id, product_id=pid,
                                     name=products_by_sku_helper(pid).name,
                                     color=color, qty=qty, unit_price=unit))
        return order

    def products_by_sku_helper(pid):
        return db.session.get(Product, pid)

    make_order(alice, 'MI2609150101001', 8, 'Ship',
               '1420 Rainier Ave S, Seattle, WA 98144',
               [], 'Delivered')
    db.session.flush()

    # alice order items (use real catalog rows)
    def add_items(order, specs):
        for sku, color, qty, unit in specs:
            p = products.get(sku)
            if not p:
                continue
            db.session.add(OrderItem(order_id=order.id, product_id=p.id,
                                     name=p.name, color=color, qty=qty,
                                     unit_price=unit))

    alice_orders = Order.query.filter_by(user_id=alice.id).all()
    add_items(alice_orders[0], [('10472532', '10" x 20"', 1, 25.99), ('10131611', '', 2, 12.99)])
    make_order(alice, 'MI2609180101002', 5, 'Pickup',
               'Store Pickup - Parkway Supercenter, 17400 Southcenter Pkwy, Tukwila, WA 98188',
               [], 'Delivered', code='GETMY30')
    alice_orders = Order.query.filter_by(user_id=alice.id).order_by(Order.id).all()
    add_items(alice_orders[1], [('10259823', 'White', 6, 4.99)])
    make_order(bob, 'MI2609190202001', 4, 'Ship',
               '305 Bleecker St, Apt 4B, New York, NY 10014',
               [], 'Delivered')
    bob_orders = Order.query.filter_by(user_id=bob.id).all()
    add_items(bob_orders[0], [('10213118', '3.7" x 8.9"', 2, 5.49), ('10764419', 'Bright White', 3, 4.99)])
    make_order(carol, 'MI2609210303001', 2, 'Ship',
               '812 Sundance Way, Austin, TX 78701',
               [], 'In Transit')
    carol_orders = Order.query.filter_by(user_id=carol.id).all()
    add_items(carol_orders[0], [('10414814', '16" x 20" / 11" x 14" mat', 1, 24.99)])
    make_order(david, 'MI2609220404001', 1, 'Pickup',
               'Store Pickup - Parkway Supercenter, 17400 Southcenter Pkwy, Tukwila, WA 98188',
               [], 'Processing')
    david_orders = Order.query.filter_by(user_id=david.id).all()
    add_items(david_orders[0], [('10061591', 'Black', 1, 5.99)])

    # recompute order totals from items (deterministic)
    for order in Order.query.all():
        subtotal = sum(i.unit_price * i.qty for i in order.items)
        discount = round(subtotal * 0.30, 2) if order.promo_code == 'GETMY30' else 0.0
        shipping = 0.0 if order.delivery_method == 'Pickup' or (subtotal - discount) >= 49 else 5.99
        tax = round((subtotal - discount) * 0.0925, 2)
        order.subtotal = round(subtotal, 2)
        order.discount = discount
        order.shipping = round(shipping, 2)
        order.tax = tax
        order.total = round(subtotal - discount + shipping + tax, 2)

    db.session.commit()


if __name__ == '__main__':
    import app as app_module
    with app_module.app.app_context():
        app_module.seed_database()
        app_module.seed_benchmark_users()
        print('seeded michaels.db')
