#!/usr/bin/env python3
"""samsung — a WebHarbor mirror of https://www.samsung.com/us/

Flask + SQLite mirror of the Samsung US consumer-electronics storefront,
rebuilt from real upstream captures (probe 2026-09-30: HTTP 200):

  * Home — the live hero banners, category tiles and a featured-product
    rail drawn from the live catalog.
  * Catalogs — the real product-finder catalogs for Smartphones (42 SKUs),
    Tablets (11), Watches (14), Audio (3), Mobile Accessories (314), TVs
    (42), Laundry (39) and Refrigerators (40): 505 real SKUs with real
    prices, ratings, series and facet filters, sortable and searchable.
  * Product pages — per-SKU pages with the real price, rating, key
    features and (for Galaxy phones) the full specification tables
    captured from the live spec-compare API.
  * Buy configurators — the real buy-page option trees for eight flagship
    devices (Galaxy S26 Ultra, S26+, Z Fold8 Ultra, Z Flip8, Tab S11,
    Watch9, two Bespoke refrigerators): storage/color/carrier choices
    resolve to the real model code, price and stock, then add to cart.
  * Compare — the live smartphone spec-compare across the 25 Galaxy
    families captured from the spec API (pick up to three models).
  * Shop — cart, checkout and order placement (CSRF-protected), order
    history, wishlist.
  * Support — the live warranty checker categories, the real standard
    limited-warranty text, the real warranty FAQ, and a contact form
    that files tickets.
  * Site-wide search and the account surface (signup, login, orders,
    wishlist, support tickets).

Every content record and every image under static/images/ comes from the
live upstream (see provenance.json and asset_inventory.json); the only
authored rows are the four benchmark user accounts and their fixture
orders/wishlist/tickets. The SQLite seed is materialized deterministically
at image build time (PYTHONHASHSEED=0).
"""
import json
import html
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import quote

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from markupsafe import Markup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("SAMSUNG_SECRET_KEY") or \
    "webharbor-samsung-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'SAMSUNG_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'samsung.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to continue.'
csrf = CSRFProtect(app)

MIRROR_TS = '2026-09-30'
SITE_NAME = 'samsung'
UPSTREAM = 'https://www.samsung.com/us/'
BRAND = 'Samsung'
SOURCE = os.path.join(BASE_DIR, 'source_data')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# bcrypt hash of 'TestPass123!' — frozen so the seed DB is byte-reproducible.
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')

CATEGORY_LABELS = {
    'smartphones': 'Smartphones',
    'tablets': 'Tablets',
    'watches': 'Watches',
    'audio': 'Audio',
    'mobile-accessories': 'Mobile Accessories',
    'tvs': 'TVs',
    'laundry': 'Laundry',
    'refrigerators': 'Refrigerators',
}

# mirror catalog order shown in the nav
NAV_CATEGORIES = ['smartphones', 'tablets', 'watches', 'audio',
                  'mobile-accessories', 'tvs', 'laundry', 'refrigerators']

FACET_LABELS = {
    'series': 'Series',
    'storage': 'Storage Size',
    'price_range': 'Price',
    'display_size': 'Display Size',
    'screen_size': 'Screen Size',
    'features': 'Key Features',
    'carrier': 'Carrier',
    'camera': 'Camera Resolution',
    'capacity': 'Capacity',
    'type': 'Type',
    'color': 'Color',
    'connectivity': 'Connectivity',
    'device': 'Compatible Device',
    'compatibility': 'Compatibility',
    'dispenser': 'Dispenser Type',
    'range': 'Product Range',
    'depth': 'Depth Type',
    'hinge_height': 'Height to Top of Hinge',
    'energy_star': 'ENERGY STAR Certified',
    'shop': 'Availability',
    'family': 'Model Family',
}


def _load(name):
    with open(os.path.join(SOURCE, name), encoding='utf-8') as f:
        return json.load(f)


def _img(path):
    if not path:
        return url_for('static', filename='images/samsung-logo.png')
    return url_for('static', filename='images/' + path)


def _slugify(text):
    text = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore')
    text = text.decode('ascii').lower()
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text


def _now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _money(value):
    if value is None:
        return ''
    return f"${value:,.2f}"


@app.template_filter('money')
def _money_filter(value):
    return _money(value)


@app.template_filter('plain_entities')
def _plain_entities(value):
    return html.unescape(str(value))


@app.template_filter('stars')
def _stars_filter(value):
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return ''


# ------------------------------------------------------------------ models --

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text, unique=True, nullable=False)
    pw_hash = db.Column(db.Text, nullable=False)

    orders = db.relationship('Order', backref='user', lazy=True)
    wishlist = db.relationship('WishlistItem', backref='user', lazy=True)
    tickets = db.relationship('SupportTicket', backref='user', lazy=True)


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.Text, unique=True, nullable=False)
    label = db.Column(db.Text, nullable=False)
    code = db.Column(db.Text, nullable=False)
    hub_url = db.Column(db.Text, nullable=False)
    sort = db.Column(db.Integer, nullable=False)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    model_code = db.Column(db.Text, unique=True, nullable=False)
    slug = db.Column(db.Text, unique=True, nullable=False)
    category_slug = db.Column(db.Text, nullable=False)
    series = db.Column(db.Text, default='')
    family = db.Column(db.Text, default='')
    name = db.Column(db.Text, nullable=False)
    mlp_url = db.Column(db.Text, default='')
    msrp = db.Column(db.Float)
    sale_price = db.Column(db.Float)
    monthly_price = db.Column(db.Float)
    rating = db.Column(db.Float)
    reviews = db.Column(db.Integer)
    in_stock = db.Column(db.Boolean, default=True)
    buy_online = db.Column(db.Boolean, default=True)
    key_features = db.Column(db.Text, nullable=False, default='[]')
    facets = db.Column(db.Text, nullable=False, default='{}')
    image = db.Column(db.Text, default='')
    spec_model = db.Column(db.Text, default='')  # spec-compare model (e.g. SM-S948)

    @property
    def feature_list(self):
        return json.loads(self.key_features)

    @property
    def facet_map(self):
        return json.loads(self.facets)

    @property
    def price(self):
        return self.sale_price if self.sale_price is not None else self.msrp

    @property
    def has_configurator(self):
        return ConfigRelation.query.filter_by(product_slug=self.slug).first() is not None


class ProductSpec(db.Model):
    __tablename__ = 'product_specs'
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.Text, nullable=False)   # e.g. SM-S948
    family_slug = db.Column(db.Text, nullable=False)  # e.g. galaxy-s26-ultra
    family_name = db.Column(db.Text, nullable=False)
    group_name = db.Column(db.Text, default='')
    attr_name = db.Column(db.Text, nullable=False)
    attr_value = db.Column(db.Text, nullable=False)
    idx = db.Column(db.Integer, nullable=False)


class ConfigProduct(db.Model):
    __tablename__ = 'config_products'
    id = db.Column(db.Integer, primary_key=True)
    configurator = db.Column(db.Text, nullable=False)   # e.g. smartphones_galaxy-s26-ultra
    product_slug = db.Column(db.Text, nullable=False)   # e.g. galaxy-s26-ultra
    model_code = db.Column(db.Text, unique=True, nullable=False)
    title = db.Column(db.Text, nullable=False)
    msrp = db.Column(db.Float)
    price = db.Column(db.Float)
    stock = db.Column(db.Text, default='InStock')
    image = db.Column(db.Text, default='')
    rating = db.Column(db.Float)
    review_count = db.Column(db.Integer)


class ConfigRelation(db.Model):
    __tablename__ = 'config_relations'
    id = db.Column(db.Integer, primary_key=True)
    configurator = db.Column(db.Text, nullable=False)
    product_slug = db.Column(db.Text, nullable=False)
    category_slug = db.Column(db.Text, nullable=False)
    default_model = db.Column(db.Text, nullable=False)
    tree = db.Column(db.Text, nullable=False)            # option tree JSON


class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    cart_key = db.Column(db.Text, nullable=False)
    configurator = db.Column(db.Text, default='')
    model_code = db.Column(db.Text, nullable=False)
    title = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text, nullable=False, default='{}')
    unit_price = db.Column(db.Float, nullable=False)
    qty = db.Column(db.Integer, nullable=False, default=1)
    image = db.Column(db.Text, default='')

    @property
    def option_map(self):
        return json.loads(self.options)


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.Text, unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    email = db.Column(db.Text, nullable=False)
    full_name = db.Column(db.Text, nullable=False)
    address1 = db.Column(db.Text, nullable=False)
    city = db.Column(db.Text, nullable=False)
    state = db.Column(db.Text, nullable=False)
    zipcode = db.Column(db.Text, nullable=False)
    payment_method = db.Column(db.Text, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    shipping = db.Column(db.Float, nullable=False, default=0.0)
    tax = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.Text, nullable=False, default='Processing')
    placed_ts = db.Column(db.Text, nullable=False)

    items = db.relationship('OrderItem', backref='order', lazy=True)


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    model_code = db.Column(db.Text, nullable=False)
    title = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text, nullable=False, default='{}')
    unit_price = db.Column(db.Float, nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    image = db.Column(db.Text, default='')

    @property
    def option_map(self):
        return json.loads(self.options)


class WishlistItem(db.Model):
    __tablename__ = 'wishlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_slug = db.Column(db.Text, nullable=False)
    added_ts = db.Column(db.Text, nullable=False)


class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'
    id = db.Column(db.Integer, primary_key=True)
    ticket_no = db.Column(db.Text, unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    email = db.Column(db.Text, nullable=False)
    category = db.Column(db.Text, nullable=False)
    topic = db.Column(db.Text, nullable=False)
    subject = db.Column(db.Text, nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False, default='Open')
    created_ts = db.Column(db.Text, nullable=False)


class WarrantyFaq(db.Model):
    __tablename__ = 'warranty_faqs'
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    idx = db.Column(db.Integer, nullable=False)


class WarrantyCategory(db.Model):
    __tablename__ = 'warranty_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    slug = db.Column(db.Text, unique=True, nullable=False)
    legal_url = db.Column(db.Text, nullable=False)
    icon = db.Column(db.Text, nullable=False)
    coverage = db.Column(db.Text, nullable=False)
    idx = db.Column(db.Integer, nullable=False)


class WarrantyTerm(db.Model):
    __tablename__ = 'warranty_terms'
    id = db.Column(db.Integer, primary_key=True)
    page = db.Column(db.Text, nullable=False)
    title = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)
    idx = db.Column(db.Integer, nullable=False)


class Hero(db.Model):
    __tablename__ = 'heroes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    subtitle = db.Column(db.Text, default='')
    cta_url = db.Column(db.Text, default='')
    cta_label = db.Column(db.Text, default='Learn more')
    image = db.Column(db.Text, nullable=False)
    idx = db.Column(db.Integer, nullable=False)


class SiteSearch(db.Model):
    """Precomputed lowercase search corpus per product (kept in SQLite so
    search never scans the JSON source files at request time)."""
    __tablename__ = 'site_search'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=False)
    slug = db.Column(db.Text, nullable=False)
    haystack = db.Column(db.Text, nullable=False)


DETERMINISTIC_INDEXES = [
    'CREATE INDEX IF NOT EXISTS ix_cart_items_cart ON cart_items (cart_key)',
    'CREATE INDEX IF NOT EXISTS ix_categories_slug ON categories (slug)',
    'CREATE INDEX IF NOT EXISTS ix_config_products_cfg ON config_products (configurator)',
    'CREATE INDEX IF NOT EXISTS ix_config_products_slug ON config_products (product_slug)',
    'CREATE INDEX IF NOT EXISTS ix_config_relations_slug ON config_relations (product_slug)',
    'CREATE INDEX IF NOT EXISTS ix_orders_user ON orders (user_id)',
    'CREATE INDEX IF NOT EXISTS ix_product_specs_family ON product_specs (family_slug)',
    'CREATE INDEX IF NOT EXISTS ix_product_specs_model ON product_specs (model_name)',
    'CREATE INDEX IF NOT EXISTS ix_products_category ON products (category_slug)',
    'CREATE INDEX IF NOT EXISTS ix_products_slug ON products (slug)',
    'CREATE INDEX IF NOT EXISTS ix_site_search_slug ON site_search (slug)',
    'CREATE INDEX IF NOT EXISTS ix_support_tickets_user ON support_tickets (user_id)',
    'CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)',
    'CREATE INDEX IF NOT EXISTS ix_wishlist_items_user ON wishlist_items (user_id)',
]


# -------------------------------------------------------------------- seed --

BENCHMARK_USERS = [
    ('Alice Johnson', 'alice.j@test.com'),
    ('Bob Chen', 'bob.c@test.com'),
    ('Carol Davis', 'carol.d@test.com'),
    ('Dana Kim', 'dana.k@test.com'),
]


def _seed_users():
    if User.query.count() > 0:
        return
    for name, email in BENCHMARK_USERS:
        db.session.add(User(name=name, email=email,
                            pw_hash=BENCHMARK_PASSWORD_HASH))
    db.session.commit()


def _seed_catalog():
    if Category.query.count() > 0:
        return
    products = _load('products.json')
    cats = {}
    for item in products:
        cat = item['category']
        if cat not in cats:
            cats[cat] = Category(slug=cat,
                                 label=CATEGORY_LABELS.get(cat, cat.title()),
                                 code='', hub_url='', sort=NAV_CATEGORIES.index(cat))
    for cat in NAV_CATEGORIES:
        if cat not in cats:
            cats[cat] = Category(slug=cat,
                                 label=CATEGORY_LABELS.get(cat, cat.title()),
                                 code='', hub_url='', sort=NAV_CATEGORIES.index(cat))
    for cat in cats.values():
        db.session.add(cat)
    db.session.commit()

    used_slugs = set()
    for item in products:
        slug = ''
        mlp = item.get('mlp_url') or ''
        if mlp.startswith('/us/'):
            parts = [p for p in mlp.strip('/').split('/') if p]
            # /us/<category>/.../<slug>/
            slug = parts[-1] if len(parts) >= 2 else ''
        if not slug:
            slug = _slugify(item['name'])[:80] or _slugify(item['model_code'])
        base = slug
        n = 2
        while slug in used_slugs:
            slug = f"{base}-{n}"
            n += 1
        used_slugs.add(slug)
        db.session.add(Product(
            model_code=item['model_code'],
            slug=slug,
            category_slug=item['category'],
            series=item.get('series') or '',
            family=item.get('family') or '',
            name=item['name'],
            mlp_url=mlp,
            msrp=item.get('msrp'),
            sale_price=item.get('sale_price'),
            monthly_price=item.get('monthly_price'),
            rating=item.get('rating'),
            reviews=item.get('reviews'),
            in_stock=item.get('in_stock', True),
            buy_online=item.get('buy_online', True),
            key_features=json.dumps(item.get('key_features') or []),
            facets=json.dumps(item.get('facets') or {}),
            image=item.get('image') or '',
        ))
    db.session.commit()

    for item in products:
        prod = Product.query.filter_by(model_code=item['model_code']).first()
        if prod:
            hay = ' '.join(filter(None, [
                prod.name, prod.family, prod.series,
                ' '.join(prod.feature_list),
                ' '.join(v for vs in prod.facet_map.values() for v in vs),
                item['category']])).casefold()
            db.session.add(SiteSearch(product_id=prod.id, slug=prod.slug,
                                      haystack=hay))
    db.session.commit()


def _seed_configurators():
    if ConfigRelation.query.count() > 0:
        return
    configs = _load('configurators.json')
    for cfg in configs:
        key = cfg['key']
        parts = key.split('_')
        # the configurator key is the upstream buy-page path with slashes
        # flattened: <category>[_<sub-category>]<product-slug>. The product
        # slug is the last segment; verify it against the catalog.
        category_slug = parts[0] if parts else ''
        product_slug = parts[-1] if len(parts) > 1 else ''
        if not category_slug or not product_slug or \
                not Product.query.filter_by(slug=product_slug).first():
            continue
        db.session.add(ConfigRelation(
            configurator=key,
            product_slug=product_slug,
            category_slug=category_slug,
            default_model=cfg.get('default_model') or '',
            tree=json.dumps(cfg.get('relation') or []),
        ))
        for p in cfg['products']:
            existing = ConfigProduct.query.filter_by(model_code=p['model_code']).first()
            if existing:
                continue
            db.session.add(ConfigProduct(
                configurator=key,
                product_slug=product_slug,
                model_code=p['model_code'],
                title=p.get('title') or '',
                msrp=p.get('msrp'),
                price=p.get('price'),
                stock=p.get('stock') or 'InStock',
                image=p.get('image') or '',
                rating=float(p['rating']) if p.get('rating') else None,
                review_count=int(p['review_count']) if p.get('review_count') else None,
            ))
    db.session.commit()


def _seed_specs():
    if ProductSpec.query.count() > 0:
        return
    specs = _load('specs.json')
    families = specs.get('families') or {}
    models = specs.get('models') or {}
    fam = _load('family_index.json') if os.path.exists(
        os.path.join(SOURCE, 'family_index.json')) else {}
    # model_name -> family record, built by build_source_data from the live
    # family-list API (fmyId -> family, SKU -> fmyId)
    model_to_family = fam.get('models') or {}
    idx = 0
    for model_name in sorted(models):
        record = model_to_family.get(model_name)
        family_name = (record or {}).get('name') or model_name
        family_slug = _slugify(family_name)
        for row in models[model_name]:
            db.session.add(ProductSpec(
                model_name=model_name,
                family_slug=family_slug,
                family_name=family_name,
                group_name=row.get('group') or '',
                attr_name=row.get('name') or '',
                attr_value=row.get('value') or '',
                idx=idx))
            idx += 1
    db.session.commit()
    # attach spec tables to the catalog products whose upstream family name
    # matches exactly (familyMktName == fmyMarketingName)
    for product in Product.query.all():
        for model_name, record in sorted(model_to_family.items()):
            if product.family == (record or {}).get('name'):
                product.spec_model = model_name
                break
    db.session.commit()


def _seed_support():
    if WarrantyFaq.query.count() > 0:
        return
    support = _load('support.json')
    for idx, faq in enumerate(support.get('warranty', {}).get('faqs', [])):
        db.session.add(WarrantyFaq(question=faq['question'],
                                   answer=faq['answer'], idx=idx))
    coverage_text = {
        'phones-tablets-wearables':
            'Standard limited warranty: this Samsung product is warranted '
            'against manufacturing defects in materials and workmanship to '
            'the original consumer purchaser for 12 months from the date of '
            'purchase (proof of purchase required).',
        'tv-display-home-theater':
            'Standard limited warranty: this Samsung product is warranted '
            'against manufacturing defects in materials and workmanship to '
            'the original consumer purchaser for 12 months from the date of '
            'purchase (proof of purchase required).',
        'home-appliances':
            'Standard limited warranty: this Samsung product is warranted '
            'against manufacturing defects in materials and workmanship to '
            'the original consumer purchaser for 12 months parts and labor '
            'from the date of purchase (proof of purchase required).',
        'computing':
            'Standard limited warranty: this Samsung product is warranted '
            'against manufacturing defects in materials and workmanship to '
            'the original consumer purchaser for 12 months from the date of '
            'purchase (proof of purchase required).',
    }
    for idx, cat in enumerate(support.get('warranty', {}).get(
            'checker_categories', [])):
        name = cat.get('name') or ''
        slug = _slugify(name)
        db.session.add(WarrantyCategory(
            name=name,
            slug=slug,
            legal_url=cat.get('legal_url') or '',
            icon=cat.get('icon') or '',
            coverage=coverage_text.get(slug, coverage_text['phones-tablets-wearables']),
            idx=idx,
        ))
    legal = support.get('warranty', {}).get('legal') or {}
    for page, sections in sorted(legal.items()):
        for idx, sec in enumerate(sections):
            db.session.add(WarrantyTerm(page=page, title=sec['title'],
                                        body=sec['body'], idx=idx))
    db.session.commit()


def _seed_home():
    if Hero.query.count() > 0:
        return
    home = _load('home.json')
    for idx, hero in enumerate(home.get('heroes', [])):
        db.session.add(Hero(
            title=hero.get('title') or '',
            subtitle=hero.get('subtitle') or '',
            cta_url=hero.get('cta_url') or '',
            cta_label=hero.get('cta_label') or 'Learn more',
            image=hero.get('image') or '',
            idx=idx,
        ))
    db.session.commit()


# benchmark fixtures: deterministic orders / wishlist / tickets
FIXED_TS = '2026-09-12T14:05:00Z'


def _seed_benchmark_state():
    if Order.query.count() > 0 or SupportTicket.query.count() > 0:
        return
    alice = User.query.filter_by(email='alice.j@test.com').first()
    bob = User.query.filter_by(email='bob.c@test.com').first()
    carol = User.query.filter_by(email='carol.d@test.com').first()
    dana = User.query.filter_by(email='dana.k@test.com').first()

    def cfg(model_code):
        return ConfigProduct.query.filter_by(model_code=model_code).first()

    def add_order(user, number, items, ts, status='Delivered'):
        subtotal = sum(p.price * q for p, q in items)
        order = Order(order_no=number, user_id=user.id, email=user.email,
                      full_name=user.name, address1='42 Galaxy Way',
                      city='Ridgefield Park', state='NJ', zipcode='07660',
                      payment_method='Card', subtotal=subtotal, shipping=0.0,
                      tax=round(subtotal * 0.06625, 2),
                      total=round(subtotal * 1.06625, 2), status=status,
                      placed_ts=ts)
        db.session.add(order)
        db.session.flush()
        for p, q in items:
            db.session.add(OrderItem(order_id=order.id,
                                     model_code=p.model_code, title=p.title,
                                     options='{}', unit_price=p.price, qty=q,
                                     image=p.image))

    s26u = cfg('SM-S948UZVEXAA') or cfg('SM-S948ULBAATT')
    watch = cfg('SM-L340NZKAXAA')
    fold = cfg('SM-F976UDGAXAA')
    if alice and s26u:
        add_order(alice, 'SS-100001', [(s26u, 1)], '2026-08-14T15:20:00Z')
    if alice and watch:
        add_order(alice, 'SS-100002', [(watch, 2)], '2026-09-02T10:05:00Z')
    if bob and fold:
        add_order(bob, 'SS-100003', [(fold, 1)], '2026-09-08T18:40:00Z',
                  status='Shipped')
    fridge = ConfigProduct.query.filter(
        ConfigProduct.configurator.like('%refrigerators%')).first()
    if carol and fridge:
        add_order(carol, 'SS-100004', [(fridge, 1)], '2026-08-28T09:15:00Z')

    wish_map = {
        alice: ['galaxy-z-fold8-ultra', 'galaxy-z-flip8', 'galaxy-tab-s11'],
        bob: ['galaxy-watch9', 'galaxy-s26-ultra'],
        carol: ['galaxy-s26-ultra'],
        dana: ['galaxy-z-flip8'],
    }
    for user, slugs in wish_map.items():
        if not user:
            continue
        for slug in slugs:
            if Product.query.filter_by(slug=slug).first():
                db.session.add(WishlistItem(user_id=user.id, product_slug=slug,
                                            added_ts=FIXED_TS))
    if alice:
        db.session.add(SupportTicket(
            ticket_no='ST-100001', user_id=alice.id, email=alice.email,
            category='Phones, Tablets & Wearables', topic='Warranty',
            subject='Screen warranty question',
            message='Does my Galaxy S26 Ultra screen repair fall under the '
                    'standard limited warranty?', status='Answered',
            created_ts='2026-09-03T11:30:00Z'))
    if carol:
        db.session.add(SupportTicket(
            ticket_no='ST-100002', user_id=carol.id, email=carol.email,
            category='Home Appliances', topic='Installation',
            subject='Family Hub fridge setup',
            message='How do I connect my Bespoke Family Hub refrigerator '
                    'to Wi-Fi for the first time?', status='Open',
            created_ts='2026-09-10T16:45:00Z'))
    db.session.commit()


def _bootstrap():
    if os.environ.get('WEBSYN_SKIP_BOOTSTRAP'):
        return
    with app.app_context():
        db.create_all()
        with db.engine.begin() as conn:
            for stmt in DETERMINISTIC_INDEXES:
                conn.exec_driver_sql(stmt)
        _seed_users()
        _seed_catalog()
        _seed_configurators()
        _seed_specs()
        _seed_support()
        _seed_home()
        _seed_benchmark_state()


_bootstrapped = False


def _ensure_bootstrap():
    global _bootstrapped
    if not _bootstrapped:
        _bootstrap()
        _bootstrapped = True


_ensure_bootstrap()


# ----------------------------------------------------------------- helpers --

def _cart_key():
    if current_user.is_authenticated:
        return f"user:{current_user.id}"
    if 'cart_key' not in session:
        session['cart_key'] = f"sess:{int(time.time() * 1000)}:{os.urandom(4).hex()}"
    return session['cart_key']


def cart_items():
    return CartItem.query.filter_by(cart_key=_cart_key()) \
        .order_by(CartItem.id).all()


def cart_count():
    return sum(item.qty for item in cart_items())


def _resolve_option_tree(tree, selected):
    """Walk the buy-page option tree honoring the user's selections.

    The upstream tree is a single product-family root whose `options` hold
    the first real option level (Storage), each branch nesting the next
    level (Color, then Carrier). Returns (levels, resolved_model_code):
    levels is a list of (option_name, items, chosen) in tree order; the
    resolved model code is the leaf reached by following the chosen items
    (falling back to the first available branch at each level).
    """
    levels = []
    # unwrap product-family roots (no option/item of their own)
    node = {'options': tree} if tree else {}
    while len(node.get('options') or []) == 1 and \
            not (node['options'][0].get('option') or node['options'][0].get('item')):
        node = node['options'][0]
    chosen = dict(selected)
    resolved = None
    guard = 0
    while node.get('options') and guard < 8:
        guard += 1
        options = node['options']
        option_name = options[0].get('option') or ''
        items = [o.get('item') for o in options if o.get('item')]
        if not option_name or not items:
            break
        pick = chosen.get(option_name)
        if pick not in items:
            pick = items[0]
        levels.append((option_name, items, pick))
        nxt = None
        for o in options:
            if o.get('item') == pick:
                nxt = o
                break
        if not nxt:
            break
        resolved = (nxt.get('modelCode') or
                    (nxt.get('product') or [None])[0]) or resolved
        node = nxt
    return levels, resolved


def current_relative_url():
    """Path + query of the current request, without scheme or host."""
    path = quote(request.path, safe="/:@!$&'()*+,;=-._~")
    return path + ('?' + request.query_string.decode('ascii', errors='replace')
                   if request.query_string else '')


@app.context_processor
def _globals():
    def products_in(category_slug):
        return Product.query.filter_by(category_slug=category_slug).count()
    return {
        'BRAND': BRAND,
        'NAV_CATEGORIES': NAV_CATEGORIES,
        'CATEGORY_LABELS': CATEGORY_LABELS,
        'cart_count': cart_count,
        'products_in': products_in,
    }


# ------------------------------------------------------------------- views --

@app.route('/')
def home():
    heroes = Hero.query.order_by(Hero.idx).all()
    featured = Product.query.filter(Product.rating.isnot(None)) \
        .order_by(Product.rating.desc(), Product.model_code).limit(8).all()
    cats = Category.query.order_by(Category.sort).all()
    return render_template('home.html', heroes=heroes, featured=featured,
                           categories=cats)


@app.route('/shop/all/')
def shop_all():
    return category_page(None)


@app.route('/<category_slug>/')
def category_view(category_slug):
    if category_slug not in CATEGORY_LABELS:
        abort(404)
    return category_page(category_slug)


def category_page(slug):
    q = request.args.get('q', '').strip().casefold()
    sort = request.args.get('sort', 'recommended')
    active = {k: v for k, v in request.args.items()
              if k.startswith('f_') and v}
    query = Product.query
    if slug:
        query = query.filter_by(category_slug=slug)
    products = query.all()
    # facet taxonomy for the sidebar, in stable order
    facet_keys = []
    facet_values = {}
    for p in products:
        for key in p.facet_map:
            if key not in facet_values:
                facet_values[key] = set()
                facet_keys.append(key)
            facet_values[key].update(p.facet_map[key])
    facet_keys.sort()
    facets = [(key, FACET_LABELS.get(key, key.title()), sorted(facet_values[key]))
              for key in facet_keys]

    def matches(p):
        for key, want in active.items():
            vals = p.facet_map.get(key[2:], [])
            if want not in vals:
                return False
        return True

    shown = [p for p in products if matches(p)]
    if q:
        shown = [p for p in shown if q in (
            f"{p.name} {p.family} {p.series} "
            f"{' '.join(p.feature_list)}").casefold()]
    if sort == 'price-low':
        shown = sorted(shown, key=lambda p: (p.price is None, p.price or 0, p.model_code))
    elif sort == 'price-high':
        shown = sorted(shown, key=lambda p: (p.price is None, -(p.price or 0), p.model_code))
    elif sort == 'rating':
        shown = sorted(shown, key=lambda p: (p.rating is None, -(p.rating or 0), p.model_code))
    elif sort == 'name':
        shown = sorted(shown, key=lambda p: p.name.casefold())
    else:
        shown = sorted(shown, key=lambda p: p.model_code)
    return render_template('category.html', slug=slug, products=shown,
                           facets=facets, sort=sort, q=q, active=active,
                           total=len(products))


@app.route('/<category_slug>/<product_slug>/')
def product_detail(category_slug, product_slug):
    if category_slug not in CATEGORY_LABELS:
        abort(404)
    product = Product.query.filter_by(slug=product_slug,
                                      category_slug=category_slug).first_or_404()
    specs = ProductSpec.query.filter_by(model_name=product.spec_model) \
        .order_by(ProductSpec.idx).all() if product.spec_model else []
    related = Product.query.filter_by(category_slug=category_slug) \
        .filter(Product.slug != product_slug) \
        .order_by(Product.model_code).limit(4).all()
    config = ConfigRelation.query.filter_by(product_slug=product_slug).first()
    return render_template('product.html', p=product, specs=specs,
                           related=related, config=config,
                           spec_count=len(specs))


@app.route('/<category_slug>/<product_slug>/buy/', methods=['GET', 'POST'])
def buy(category_slug, product_slug):
    if category_slug not in CATEGORY_LABELS:
        abort(404)
    config = ConfigRelation.query.filter_by(product_slug=product_slug).first()
    if not config:
        abort(404)
    tree = json.loads(config.tree)
    # option clicks arrive as query params; the add-to-cart form re-posts the
    # current selections as hidden inputs — request.values covers both
    selected = {k: v for k, v in request.values.items()
                if k not in ('csrf_token', 'model_code', 'qty')}
    device = {'galaxy-tab-s11': 'Galaxy Tab S11', 'galaxy-s26': 'Galaxy S26'}.get(product_slug)
    if device and 'Device' not in selected:
        selected['Device'] = device
    levels, resolved = _resolve_option_tree(tree, selected)
    cp = ConfigProduct.query.filter_by(model_code=resolved).first() if resolved else None
    if not cp:
        cp = ConfigProduct.query.filter_by(model_code=config.default_model).first()
    gallery = [cp.image] if cp and cp.image else []
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Please sign in to add items to your cart.', 'error')
            return redirect(url_for('login', next=current_relative_url()))
        model_code = request.form.get('model_code', '')
        try:
            qty = int(request.form.get('qty', '1'))
        except (TypeError, ValueError):
            abort(400)
        if not 1 <= qty <= 5 or not cp or model_code != cp.model_code:
            abort(400)
        target = cp
        opts = {name: pick for name, _items, pick in levels}
        existing = CartItem.query.filter_by(cart_key=_cart_key(),
                                            model_code=model_code).first()
        if existing:
            existing.qty = min(5, existing.qty + qty)
        else:
            db.session.add(CartItem(
                cart_key=_cart_key(), configurator=config.configurator,
                model_code=model_code, title=target.title,
                options=json.dumps(opts), unit_price=target.price or 0,
                qty=qty, image=target.image or ''))
        db.session.commit()
        flash(f'Added {target.title} to your cart.', 'success')
        return redirect(url_for('cart'))
    return render_template('buy.html', config=config, levels=levels,
                           selected=selected, cp=cp, gallery=gallery,
                           category_slug=category_slug, product_slug=product_slug)


@app.route('/cart/')
def cart():
    items = cart_items()
    subtotal = sum(i.unit_price * i.qty for i in items)
    return render_template('cart.html', items=items, subtotal=subtotal)


@app.route('/cart/update', methods=['POST'])
def cart_update():
    item_id = request.form.get('item_id', '')
    try:
        qty = int(request.form.get('qty', '1'))
    except (TypeError, ValueError):
        abort(400)
    if not 0 <= qty <= 5:
        abort(400)
    item = CartItem.query.filter_by(id=item_id,
                                    cart_key=_cart_key()).first()
    if not item:
        abort(404)
    if qty <= 0:
        db.session.delete(item)
    else:
        item.qty = min(5, qty)
    db.session.commit()
    return redirect(url_for('cart'))


@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    item_id = request.form.get('item_id', '')
    item = CartItem.query.filter_by(id=item_id,
                                    cart_key=_cart_key()).first()
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('cart'))


@app.route('/checkout/', methods=['GET', 'POST'])
@login_required
def checkout():
    items = cart_items()
    if not items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('cart'))
    subtotal = sum(i.unit_price * i.qty for i in items)
    tax = round(subtotal * 0.06625, 2)
    if request.method == 'POST':
        order = Order(
            order_no=f"SS-{int(time.time() * 1000)}",
            user_id=current_user.id,
            email=request.form.get('email', current_user.email).strip(),
            full_name=request.form.get('full_name', '').strip(),
            address1=request.form.get('address1', '').strip(),
            city=request.form.get('city', '').strip(),
            state=request.form.get('state', '').strip(),
            zipcode=request.form.get('zipcode', '').strip(),
            payment_method=request.form.get('payment_method', 'Card'),
            subtotal=subtotal, shipping=0.0, tax=tax,
            total=round(subtotal + tax, 2), status='Processing',
            placed_ts=_now_iso())
        if not order.full_name or not order.address1 or not order.city \
                or not order.state or not order.zipcode:
            flash('Please complete every required delivery field.', 'error')
            return render_template('checkout.html', items=items,
                                   subtotal=subtotal, tax=tax)
        db.session.add(order)
        db.session.flush()
        for item in items:
            db.session.add(OrderItem(order_id=order.id,
                                     model_code=item.model_code,
                                     title=item.title, options=item.options,
                                     unit_price=item.unit_price,
                                     qty=item.qty, image=item.image))
            db.session.delete(item)
        db.session.commit()
        flash(f'Order {order.order_no} placed. Thank you for shopping '
              'Samsung.', 'success')
        return redirect(url_for('order_detail', order_no=order.order_no))
    return render_template('checkout.html', items=items, subtotal=subtotal,
                           tax=tax)


@app.route('/orders/')
@login_required
def orders():
    mine = Order.query.filter_by(user_id=current_user.id) \
        .order_by(Order.id.desc()).all()
    return render_template('orders.html', orders=mine)


@app.route('/orders/<order_no>/')
@login_required
def order_detail(order_no):
    order = Order.query.filter_by(order_no=order_no,
                                  user_id=current_user.id).first_or_404()
    return render_template('order_detail.html', order=order)


@app.route('/account/')
@login_required
def account():
    order_count = Order.query.filter_by(user_id=current_user.id).count()
    wish = WishlistItem.query.filter_by(user_id=current_user.id) \
        .order_by(WishlistItem.id).all()
    wish_products = [Product.query.filter_by(slug=w.product_slug).first()
                     for w in wish]
    wish_products = [p for p in wish_products if p]
    tickets = SupportTicket.query.filter_by(user_id=current_user.id) \
        .order_by(SupportTicket.id.desc()).all()
    return render_template('account.html', order_count=order_count,
                           wishlist=wish_products, tickets=tickets)


@app.route('/account/wishlist/')
@login_required
def wishlist():
    items = WishlistItem.query.filter_by(user_id=current_user.id) \
        .order_by(WishlistItem.id).all()
    products = [Product.query.filter_by(slug=i.product_slug).first()
                for i in items]
    products = [p for p in products if p]
    return render_template('wishlist.html', products=products)


@app.route('/wishlist/toggle', methods=['POST'])
@login_required
def wishlist_toggle():
    product_slug = request.form.get('product_slug', '')
    product = Product.query.filter_by(slug=product_slug).first()
    if not product:
        abort(404)
    existing = WishlistItem.query.filter_by(user_id=current_user.id,
                                            product_slug=product_slug).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash(f'Removed {product.name} from your wishlist.', 'success')
    else:
        db.session.add(WishlistItem(user_id=current_user.id,
                                    product_slug=product_slug,
                                    added_ts=_now_iso()))
        db.session.commit()
        flash(f'Added {product.name} to your wishlist.', 'success')
    return redirect(request.form.get('next') or
                    url_for('product_detail',
                            category_slug=product.category_slug,
                            product_slug=product.slug))


@app.route('/account/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.pw_hash, password):
            login_user(user)
            flash(f'Signed in as {user.name}.', 'success')
            return redirect(request.args.get('next') or url_for('account'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/account/logout')
@login_required
def logout():
    logout_user()
    flash('You have signed out of your Samsung account.', 'success')
    return redirect(url_for('home'))


@app.route('/account/signup/', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not name or not email or len(password) < 8:
            flash('Name, email and a password of at least 8 characters are '
                  'required.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('That email is already registered.', 'error')
        else:
            user = User(name=name, email=email,
                        pw_hash=bcrypt.generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f'Welcome to Samsung, {name}.', 'success')
            return redirect(url_for('account'))
    return render_template('signup.html')


# ------------------------------------------------------------------ compare --

@app.route('/compare/')
def compare():
    fam = _load('family_index.json')
    families = []
    for model_name in sorted(fam.get('models') or {}):
        record = fam['models'][model_name]
        families.append({
            'model_name': model_name,
            'name': record.get('name') or model_name,
            'series': record.get('series') or '',
        })
    # The picker form submits repeated params (models=A&models=B); direct
    # links and the tests use the comma form (models=A,B). Accept both and
    # keep the first-seen order so the real form submission renders every
    # selected model as its own column.
    picked = []
    for chunk in request.args.getlist('models'):
        for name in chunk.split(','):
            name = name.strip()
            if name and name not in picked:
                picked.append(name)
    picked = picked[:3]
    columns = []
    table = []
    if picked:
        for name in picked:
            rows = ProductSpec.query.filter_by(model_name=name) \
                .order_by(ProductSpec.idx).all()
            if rows:
                columns.append({'model_name': name, 'rows': rows,
                                'family': fam['models'].get(name, {}).get('name', name)})
        # merge columns positionally; each row label comes from the first
        # column that names the attribute at that position (the upstream
        # spec trees are per-model and occasionally label a slot slightly
        # differently — the values stay verbatim per model).
        depth = max((len(c['rows']) for c in columns), default=0)
        for i in range(depth):
            group = next((c['rows'][i].group_name for c in columns
                          if i < len(c['rows']) and c['rows'][i].group_name), '')
            label = next((c['rows'][i].attr_name for c in columns
                          if i < len(c['rows']) and c['rows'][i].attr_name), '')
            values = [c['rows'][i].attr_value if i < len(c['rows']) else ''
                      for c in columns]
            table.append({'group': group, 'label': label, 'values': values})
    return render_template('compare.html', families=families, picked=picked,
                           columns=columns, table=table)


# ------------------------------------------------------------------ support --

@app.route('/support/')
def support_home():
    cats = WarrantyCategory.query.order_by(WarrantyCategory.idx).all()
    faqs = WarrantyFaq.query.order_by(WarrantyFaq.idx).all()
    return render_template('support.html', cats=cats, faqs=faqs)


@app.route('/support/warranty/')
def warranty():
    cats = WarrantyCategory.query.order_by(WarrantyCategory.idx).all()
    faqs = WarrantyFaq.query.order_by(WarrantyFaq.idx).all()
    category = request.args.get('category', '')
    model_code = request.args.get('model', '')
    models = []
    chosen_cat = None
    chosen_product = None
    coverage = None
    if category:
        chosen_cat = WarrantyCategory.query.filter_by(slug=category).first()
        if chosen_cat:
            cat_slugs = {
                'phones-tablets-wearables': ['smartphones', 'tablets', 'watches'],
                'tv-display-home-theater': ['tvs'],
                'home-appliances': ['refrigerators', 'laundry'],
                'computing': ['tablets'],
            }.get(chosen_cat.slug, [])
            models = Product.query.filter(
                Product.category_slug.in_(cat_slugs)) \
                .order_by(Product.model_code).all()
    if model_code:
        chosen_product = next((p for p in models if p.model_code == model_code), None)
        if chosen_product and chosen_cat:
            coverage = chosen_cat.coverage
    return render_template('warranty.html', cats=cats, faqs=faqs,
                           chosen_cat=chosen_cat, models=models,
                           chosen_product=chosen_product, coverage=coverage)


@app.route('/support/contact/', methods=['GET', 'POST'])
def contact():
    cats = WarrantyCategory.query.order_by(WarrantyCategory.idx).all()
    topics = ['Warranty', 'Repair', 'Installation', 'Software Update',
              'Account & Sign-in', 'Orders & Shipping', 'Returns']
    category = request.args.get('category', '')
    ticket = None
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Please sign in to send us a message.', 'error')
            return redirect(url_for('login', next=current_relative_url()))
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        if not subject or not message:
            flash('Subject and message are required.', 'error')
        else:
            ticket = SupportTicket(
                ticket_no=f"ST-{int(time.time() * 1000)}",
                user_id=current_user.id,
                email=request.form.get('email', current_user.email).strip(),
                category=request.form.get('category', ''),
                topic=request.form.get('topic', ''),
                subject=subject, message=message, status='Open',
                created_ts=_now_iso())
            db.session.add(ticket)
            db.session.commit()
            flash(f'Message sent. Your ticket number is {ticket.ticket_no}.',
                  'success')
            return redirect(url_for('contact_done', ticket_no=ticket.ticket_no))
    return render_template('contact.html', cats=cats, topics=topics,
                           category=category)


@app.route('/support/contact/done/')
def contact_done():
    ticket_no = request.args.get('ticket_no', '')
    ticket = SupportTicket.query.filter_by(
        ticket_no=ticket_no, user_id=current_user.id).first() \
        if current_user.is_authenticated else None
    return render_template('contact_done.html', ticket=ticket)


# ------------------------------------------------------------------- search --

@app.route('/search/')
def search():
    q = request.args.get('q', '').strip().casefold()
    results = []
    if q:
        rows = SiteSearch.query.filter(SiteSearch.haystack.like(f'%{q}%')).all()
        slugs = [r.slug for r in rows]
        results = Product.query.filter(Product.slug.in_(slugs)) \
            .order_by(Product.model_code).all()
    return render_template('search.html', q=request.args.get('q', ''),
                           results=results)


@app.route('/_health')
def health():
    return {
        'ok': True,
        'site': SITE_NAME,
        'products': Product.query.count(),
        'config_products': ConfigProduct.query.count(),
        'spec_rows': ProductSpec.query.count(),
        'spec_models': db.session.query(
            db.func.count(db.distinct(ProductSpec.model_name))).scalar(),
        'heroes': Hero.query.count(),
        'warranty_faqs': WarrantyFaq.query.count(),
        'warranty_categories': WarrantyCategory.query.count(),
        'users': User.query.count(),
        'orders': Order.query.count(),
        'wishlist_items': WishlistItem.query.count(),
        'tickets': SupportTicket.query.count(),
    }


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


# -------------------------------------------------------------------- main --

def main():
    """Build the seed database (idempotent)."""
    with app.app_context():
        db.create_all()
        with db.engine.begin() as conn:
            for stmt in DETERMINISTIC_INDEXES:
                conn.exec_driver_sql(stmt)
        _seed_users()
        _seed_catalog()
        _seed_configurators()
        _seed_specs()
        _seed_support()
        _seed_home()
        _seed_benchmark_state()
        print('[seed] samsung reference data ready')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'serve':
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    else:
        main()
