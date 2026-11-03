#!/usr/bin/env python3
"""backcountry — a WebHarbor mirror of https://www.backcountry.com/

Flask + SQLite mirror of Backcountry.com (outdoor gear & clothing): the
home page with its announcement bar and category cards, six catalog
categories with their upstream facet trees / sort options and product
grids, the full shop-all-brands directory, brand landing pages, site
search (upstream snapshots for the captured terms, computed over the
snapshot otherwise), product detail pages with real upstream colors,
sizes, stock, prices, tech specs, Q&A and the community review wall,
plus the shopping flows: guest + account carts, checkout with address /
shipping / payment forms, order confirmation, order history, addresses
and wish lists. Four benchmark accounts (Alice, Bob, Carol, Dana) come
seeded with carts, wish lists, orders and reviews built on real captured
products.

Content comes from the tracked source_data/*.json snapshots captured from
backcountry.com on 2026-09-30 (see provenance.json); the
SQLite seed is materialized deterministically at image build time
(PYHASHSEED=0).
"""
import json
import os
import re
import math
from urllib.parse import urlsplit, urlencode
import uuid
from datetime import date

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("BACKCOUNTRY_SECRET_KEY") or "webharbor-backcountry-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'BACKCOUNTRY_DB_URI', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'backcountry.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to continue.'
csrf = CSRFProtect(app)

# The mirror is a frozen snapshot of the upstream site taken 2026-09-30.
MIRROR_DATE = date(2026, 9, 30)
MIRROR_TS = "2026-09-30 12:00 UTC"
SITE_NAME = "backcountry"
# bcrypt hash of 'TestPass123!' — frozen so the seed DB is byte-reproducible.
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')
SOURCE = os.path.join(BASE_DIR, 'source_data')
FREE_SHIPPING_THRESHOLD_CENTS = 6900  # "Free Shipping on orders over $69*"


def money(cents):
    if cents is None:
        return None
    return "${:,.2f}".format(cents / 100.0)


def _load(name):
    with open(os.path.join(SOURCE, name), encoding='utf-8') as f:
        return json.load(f)


def local_return(value, fallback='/'):
    value = (value or '').strip()
    parts = urlsplit(value)
    return value if value.startswith('/') and not value.startswith('//') and not parts.netloc and not parts.scheme and not any(c in value for c in ('\\', '\r', '\n')) else fallback


def integer(value, minimum=1, maximum=99):
    try:
        result = int(value)
    except (ValueError, TypeError):
        abort(400, 'Enter a valid whole number.')
    if not minimum <= result <= maximum:
        abort(400, 'Quantity or page is outside the allowed range.')
    return result


# ------------------------------------------------------------------- models --

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_benchmark = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.String(10), nullable=False, default='2026-09-01')


class Address(db.Model):
    __tablename__ = 'addresses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    label = db.Column(db.String(40))
    full_name = db.Column(db.String(120), nullable=False)
    line1 = db.Column(db.String(200), nullable=False)
    line2 = db.Column(db.String(200))
    city = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(60), nullable=False)
    zip = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(40))
    is_default = db.Column(db.Boolean, default=False)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.String(20), primary_key=True)       # e.g. SMIZ9HR
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(220), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey('brands.id'), nullable=False)
    description = db.Column(db.Text)
    bottom_line = db.Column(db.Text)
    bullets = db.Column(db.Text)          # JSON list
    features = db.Column(db.Text)         # JSON [{name, value}]
    breadcrumbs = db.Column(db.Text)      # JSON [{id,name,alias,canonicalUrl}]
    min_list = db.Column(db.Integer)
    max_list = db.Column(db.Integer)
    min_sale = db.Column(db.Integer)
    max_sale = db.Column(db.Integer)
    min_discount = db.Column(db.Integer)
    max_discount = db.Column(db.Integer)
    variations_on_sale = db.Column(db.Integer)
    total_variations = db.Column(db.Integer)
    is_gearhead_pick = db.Column(db.Boolean, default=False)
    is_past_season = db.Column(db.Boolean, default=False)
    is_exclusive = db.Column(db.Boolean, default=False)
    hsa_fsa = db.Column(db.Boolean, default=False)
    free_shipping = db.Column(db.Boolean, default=False)
    in_stock = db.Column(db.Boolean, default=True)
    availability = db.Column(db.String(40))
    review_count = db.Column(db.Integer)   # upstream aggregate
    review_avg = db.Column(db.Float)       # upstream aggregate
    review_histogram = db.Column(db.Text)   # JSON [{rating,count,percentage}]
    default_color = db.Column(db.String(60))

    brand = db.relationship('Brand')
    skus = db.relationship('ProductSku', backref='product',
                           order_by='ProductSku.size_pos, ProductSku.id',
                           cascade='all, delete-orphan')

    @property
    def item_number(self):
        return self.id

    @property
    def grid_image(self):
        """The upstream grid tile (440px) for the default color."""
        want = self.default_color
        skus = self.skus or []
        pick = None
        if want:
            pick = next((s for s in skus if s.color_key == want), None)
        pick = pick or (skus[0] if skus else None)
        if not pick or not pick.image:
            return None
        return pick.image.replace('/medium/', '/large/')

    @property
    def display_review_count(self):
        local = Review.query.filter_by(product_id=self.id, is_seed=False).count()
        return (self.review_count or 0) + local

    @property
    def display_review_avg(self):
        local = Review.query.filter_by(product_id=self.id, is_seed=False).all()
        count = (self.review_count or 0) + len(local)
        return (((self.review_avg or 0) * (self.review_count or 0) + sum(r.rating for r in local)) / count) if count else 0

    @property
    def price_from(self):
        return self.min_sale

    def skus_for_color(self, color_key):
        return [s for s in self.skus if s.color_key == color_key]

    def sku(self, sku_id):
        return next((s for s in self.skus if s.id == sku_id), None)

    @property
    def color_keys(self):
        seen = []
        for s in self.skus:
            if s.color_key not in seen:
                seen.append(s.color_key)
        return seen

    def color_name(self, color_key):
        s = next((x for x in self.skus if x.color_key == color_key), None)
        return s.color if s else None

    @property
    def on_sale(self):
        return (self.max_discount or 0) > 0

    @property
    def savings_cents(self):
        if not self.on_sale or self.min_list is None:
            return 0
        return max(0, (self.min_list or 0) - (self.min_sale or 0))

    @property
    def rating_pct(self):
        return (self.review_avg or 0) * 20


class ProductSku(db.Model):
    __tablename__ = 'product_skus'
    id = db.Column(db.String(80), primary_key=True)  # e.g. SMIZ9HR-BLA-ONESIZ
    product_id = db.Column(db.String(20), db.ForeignKey('products.id'),
                           nullable=False)
    color = db.Column(db.String(120), nullable=False)
    color_family = db.Column(db.String(40))
    color_key = db.Column(db.String(60), nullable=False)
    size = db.Column(db.String(60), nullable=False)
    size_scale = db.Column(db.String(60))
    size_pos = db.Column(db.Integer)
    list_price = db.Column(db.Integer)
    sale_price = db.Column(db.Integer)
    discount = db.Column(db.Integer)
    on_sale = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(30), nullable=False)   # InStock/OutOfStock
    stock = db.Column(db.Integer)
    image = db.Column(db.String(200))       # upstream medium image path
    is_past_season = db.Column(db.Boolean, default=False)
    season = db.Column(db.String(10))
    year = db.Column(db.String(10))

    @property
    def in_stock(self):
        return self.status == 'InStock'


class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(20), db.ForeignKey('products.id'),
                           nullable=False)
    color_key = db.Column(db.String(60), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    large = db.Column(db.String(220))    # static path, 440px grid/gallery
    full = db.Column(db.String(220))     # static path, 1200px gallery zoom
    title = db.Column(db.String(80))

    product = db.relationship('Product')


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    upstream_id = db.Column(db.String(40))
    product_id = db.Column(db.String(20), db.ForeignKey('products.id'),
                           nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200))
    text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    created = db.Column(db.String(30), nullable=False)
    familiarity = db.Column(db.String(120))
    fit = db.Column(db.String(80))
    size_purchased = db.Column(db.String(60))
    photos = db.Column(db.Text)           # JSON list of static paths
    syndicated = db.Column(db.Boolean, default=False)
    syndication_source = db.Column(db.String(120))
    author_gearhead = db.Column(db.Boolean, default=False)
    is_seed = db.Column(db.Boolean, default=False)

    product = db.relationship('Product')

    @property
    def photos_list(self):
        return json.loads(self.photos or '[]')

    @property
    def created_pretty(self):
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", self.created or '')
        if not m:
            return self.created
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November',
                  'December']
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{months[mo-1]} {d}, {y}"


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    upstream_id = db.Column(db.String(40))
    product_id = db.Column(db.String(20), db.ForeignKey('products.id'),
                           nullable=False)
    author = db.Column(db.String(120))
    text = db.Column(db.Text, nullable=False)
    created = db.Column(db.String(30))
    answers = db.relationship('QuestionAnswer', backref='question',
                              order_by='QuestionAnswer.id',
                              cascade='all, delete-orphan')

    product = db.relationship('Product')


class QuestionAnswer(db.Model):
    __tablename__ = 'question_answers'
    id = db.Column(db.Integer, primary_key=True)
    upstream_id = db.Column(db.String(40))
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'),
                            nullable=False)
    author = db.Column(db.String(120))
    author_gearhead = db.Column(db.Boolean, default=False)
    text = db.Column(db.Text, nullable=False)
    created = db.Column(db.String(30))


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    upstream_total = db.Column(db.Integer)
    facets = db.Column(db.Text)           # JSON facet tree
    sort_options = db.Column(db.Text)     # JSON [{name, value, selected}]
    subcategories = db.Column(db.Text)    # JSON [{name, slug, count}]

    products = db.relationship('CategoryProduct', backref='category',
                               order_by='CategoryProduct.position')


class CategoryProduct(db.Model):
    __tablename__ = 'category_products'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'),
                            nullable=False)
    product_id = db.Column(db.String(20), db.ForeignKey('products.id'),
                          nullable=False)
    position = db.Column(db.Integer, nullable=False)
    product = db.relationship('Product')


class Brand(db.Model):
    __tablename__ = 'brands'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    title = db.Column(db.String(220))
    description = db.Column(db.Text)
    logo = db.Column(db.String(200))
    upstream_total = db.Column(db.Integer)
    facets = db.Column(db.Text)           # JSON facet tree (categories)
    sort_options = db.Column(db.Text)     # JSON [{name, value, selected}]
    listed = db.Column(db.Boolean, default=False)   # has a landing page

    products = db.relationship('BrandProduct', backref='brand',
                               order_by='BrandProduct.position')

    @property
    def letter(self):
        c = (self.name or '#')[0].upper()
        return c if c.isalpha() else '#'

    @property
    def clean_slug(self):
        """Directory rows store the captured upstream path (/brand/<slug>)
        in the slug column; the linkable slug is its last segment."""
        return (self.slug or '').rstrip('/').split('/')[-1]

    @property
    def servable(self):
        """True when /brand/<clean_slug> renders (products or landing
        page) — only servable brands render as links (zara precedent)."""
        return bool(self.products) or bool(self.listed)


class BrandProduct(db.Model):
    __tablename__ = 'brand_products'
    id = db.Column(db.Integer, primary_key=True)
    brand_id = db.Column(db.Integer, db.ForeignKey('brands.id'), nullable=False)
    product_id = db.Column(db.String(20), db.ForeignKey('products.id'),
                          nullable=False)
    position = db.Column(db.Integer, nullable=False)
    product = db.relationship('Product')


class SearchSnapshot(db.Model):
    __tablename__ = 'search_snapshots'
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(120), unique=True, nullable=False)
    upstream_total = db.Column(db.Integer)
    sort_options = db.Column(db.Text)

    results = db.relationship('SearchResult', backref='snapshot',
                              order_by='SearchResult.position')


class SearchResult(db.Model):
    __tablename__ = 'search_results'
    id = db.Column(db.Integer, primary_key=True)
    snapshot_id = db.Column(db.Integer, db.ForeignKey('search_snapshots.id'),
                            nullable=False)
    product_id = db.Column(db.String(20), db.ForeignKey('products.id'),
                          nullable=False)
    position = db.Column(db.Integer, nullable=False)
    product = db.relationship('Product')


class CampaignCard(db.Model):
    __tablename__ = 'campaign_cards'
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(80), nullable=False)   # announcement/hero/tile/grid
    position = db.Column(db.Integer, nullable=False)
    text = db.Column(db.String(300))
    image = db.Column(db.String(300))
    alt = db.Column(db.String(200))
    link = db.Column(db.String(200))
    kind = db.Column(db.String(40))


class InfoPage(db.Model):
    __tablename__ = 'info_pages'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)              # JSON [{heading, paragraphs}]


class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    guest_token = db.Column(db.String(64))
    sku_id = db.Column(db.String(80), db.ForeignKey('product_skus.id'),
                       nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    added_at = db.Column(db.String(10), nullable=False, default='2026-09-30')

    sku = db.relationship('ProductSku')

    @property
    def unit_price(self):
        return self.sku.sale_price

    @property
    def unit_list(self):
        return self.sku.list_price

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def line_list_total(self):
        return (self.unit_list or self.unit_price) * self.quantity


class WishlistItem(db.Model):
    __tablename__ = 'wishlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.String(20), db.ForeignKey('products.id'),
                          nullable=False)
    added_at = db.Column(db.String(10), nullable=False, default='2026-09-29')
    product = db.relationship('Product')


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    guest_email = db.Column(db.String(160))
    number = db.Column(db.String(30), unique=True, nullable=False)
    status = db.Column(db.String(40), nullable=False)   # placed/shipped/delivered/cancelled
    placed_at = db.Column(db.String(10), nullable=False)
    shipping_method = db.Column(db.String(60))
    shipping_cents = db.Column(db.Integer, nullable=False, default=0)
    subtotal_cents = db.Column(db.Integer, nullable=False, default=0)
    savings_cents = db.Column(db.Integer, nullable=False, default=0)
    total_cents = db.Column(db.Integer, nullable=False, default=0)
    payment_last4 = db.Column(db.String(4))
    address_snapshot = db.Column(db.Text)   # JSON

    items = db.relationship('OrderItem', backref='order',
                            cascade='all, delete-orphan')

    user = db.relationship('User')

    @property
    def address(self):
        return json.loads(self.address_snapshot or '{}')

    @property
    def status_label(self):
        return {'placed': 'Processing', 'shipped': 'Shipped',
                'delivered': 'Delivered', 'cancelled': 'Cancelled',
                'returned': 'Returned'}.get(self.status, self.status.title())


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.String(20), db.ForeignKey('products.id'))
    product_name = db.Column(db.String(220), nullable=False)
    brand_name = db.Column(db.String(160))
    color_name = db.Column(db.String(120))
    size_name = db.Column(db.String(60))
    unit_price = db.Column(db.Integer, nullable=False)
    unit_list = db.Column(db.Integer)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    product = db.relationship('Product')


# --------------------------------------------------------------- helpers --

def img(path):
    """Map an upstream media path to the mirror's static file (None if absent)."""
    if not path:
        return None
    if path.startswith('/'):
        return '/static/images' + path
    if path.startswith('static/images/'):
        return '/' + path
    return None


def cms_img(url):
    """Map an upstream content.backcountry.com CMS URL to the mirror file."""
    if not url:
        return None
    m = re.match(r"https://content\.backcountry\.com/v3/assets/([^/]+)/([^/]+)/(.+)$", url)
    if m:
        return f"/static/images/cms/{m.group(1)}/{m.group(2)}/{m.group(3)}"
    m = re.match(r"https://content\.backcountry\.com/(images/.+)$", url)
    if m:
        return "/static/images/" + m.group(1)
    return None


def dollars(value):
    """Format a dollar float (upstream format) as $X.XX."""
    if value is None:
        return None
    return "${:,.2f}".format(float(value))


# ------------------------------------------------------------ seeding --

def to_cents(v):
    """Upstream prices are dollar floats; the mirror stores integer cents."""
    if v is None:
        return None
    return int(round(float(v) * 100))


def seed_products():
    if Product.query.count() > 0:
        return
    data = _load('products.json')['products']
    reviews = _load('reviews.json')
    for p in data:
        brand = Brand.query.filter_by(name=p['brand']).first()
        if not brand:
            # every product brand is pre-created by seed_brands; keep a
            # deterministic fallback anyway
            nxt = Brand.query.order_by(Brand.id.desc()).first().id + 1
            bslug = re.sub(r"[^a-z0-9]+", "-", p['brand'].lower()).strip('-')
            brand = Brand(id=nxt, slug=bslug, name=p['brand'], listed=False)
            db.session.add(brand)
            db.session.flush()
        if not brand.logo and p.get('brand_logo'):
            brand.logo = p['brand_logo']
        rev = (reviews.get(p['id']) or {}).get('aggregates') or {}
        hist = rev.get('ratingDetails') or []
        row = Product(
            id=p['id'], slug=p['slug'], title=p['title'], brand_id=brand.id,
            description=p.get('description'),
            bottom_line=p.get('bottom_line'),
            bullets=json.dumps(p.get('bullets') or []),
            features=json.dumps(p.get('features') or []),
            breadcrumbs=json.dumps(p.get('breadcrumbs') or []),
            min_list=to_cents(p.get('min_list')), max_list=to_cents(p.get('max_list')),
            min_sale=to_cents(p.get('min_sale')), max_sale=to_cents(p.get('max_sale')),
            min_discount=p.get('min_discount'),
            max_discount=p.get('max_discount'),
            variations_on_sale=p.get('variations_on_sale'),
            total_variations=p.get('total_variations'),
            is_gearhead_pick=p.get('is_gearhead_pick', False),
            is_past_season=p.get('is_past_season', False),
            is_exclusive=p.get('is_exclusive', False),
            hsa_fsa=p.get('hsa_fsa', False),
            free_shipping=p.get('free_shipping', True),
            in_stock=p.get('in_stock', True),
            availability=p.get('availability'),
            review_count=rev.get('totalCount') or p.get('review_count') or 0,
            review_avg=rev.get('overallRating') or p.get('review_avg') or 0,
            review_histogram=json.dumps(hist),
            default_color=p.get('default_color'),
        )
        db.session.add(row)
        db.session.flush()
        seen_colors = []
        for s in p.get('skus') or []:
            db.session.add(ProductSku(
                id=s['id'], product_id=row.id,
                color=s['color'], color_family=s.get('color_family'),
                color_key=s.get('color_id') or s['color'],
                size=s['size'], size_scale=s.get('size_scale'),
                size_pos=s.get('size_pos'),
                list_price=to_cents(s.get('list_price')),
                sale_price=to_cents(s.get('sale_price')),
                discount=s.get('discount'), on_sale=s.get('on_sale', False),
                status=s.get('status') or 'InStock',
                stock=s.get('stock'), image=s.get('image'),
                is_past_season=s.get('is_past_season', False),
                season=s.get('season'), year=s.get('year')))
            if s['color'] not in seen_colors:
                seen_colors.append(s['color'])
        # gallery: per color, up to 4 upstream detail shots
        for color_key, shots in (p.get('gallery') or {}).items():
            for i, shot in enumerate(shots[:4]):
                db.session.add(ProductImage(
                    product_id=row.id, color_key=color_key, position=i,
                    large=shot.get('large'), full=shot.get('1200'),
                    title=shot.get('title')))
    db.session.flush()


def seed_reviews():
    if Review.query.count() > 0:
        return
    reviews = _load('reviews.json')
    for pid, block in reviews.items():
        for r in block.get('reviews') or []:
            db.session.add(Review(
                upstream_id=r['id'], product_id=pid, user_id=None,
                author=r.get('author') or 'Backcountry Customer',
                title=r.get('title'), text=r.get('text') or '',
                rating=r.get('rating') or 5,
                created=r.get('created'),
                familiarity=r.get('familiarity'), fit=r.get('fit'),
                size_purchased=r.get('size_purchased'),
                photos=json.dumps(r.get('photos') or []),
                syndicated=r.get('syndicated', False),
                syndication_source=r.get('syndication_source'),
                author_gearhead=r.get('author_gearhead', False),
                is_seed=True))
        for q in block.get('questions') or []:
            qr = Question(upstream_id=q.get('id'), product_id=pid,
                          author=q.get('author', 'Anonymous'),
                          text=q.get('text') or '',
                          created=q.get('created'))
            db.session.add(qr)
            db.session.flush()
            for a in q.get('answers') or []:
                db.session.add(QuestionAnswer(
                    upstream_id=a.get('id'), question_id=qr.id,
                    author=a.get('author') or 'Gearhead',
                    author_gearhead=a.get('author_gearhead', False),
                    text=a.get('text') or '',
                    created=a.get('created')))
    db.session.flush()


def seed_brands():
    if Brand.query.count() > 0:
        return
    # deterministic id assignment: the landing-page brands first (file
    # order), then every directory brand not already present (letter-group
    # order from the captured shop-all-brands page)
    ordered = []
    seen = set()
    landing = {b['slug']: b for b in _load('brands.json')['brands']}
    for b in _load('brands.json')['brands']:
        if b['slug'] not in seen:
            seen.add(b['slug'])
            ordered.append({'slug': b['slug'], 'name': b['name'],
                            'listed': True})
    directory = _load('brand_directory.json')['groups']
    for letter in directory:
        for row in directory[letter]:
            if row['slug'] not in seen:
                seen.add(row['slug'])
                ordered.append({'slug': row['slug'], 'name': row['name'],
                                'listed': False})
    for i, b in enumerate(ordered, start=1):
        lb = landing.get(b['slug']) or {}
        db.session.add(Brand(id=i, slug=b['slug'], name=b['name'],
                            listed=b['listed'],
                            facets=json.dumps(lb.get('facets') or []),
                            sort_options=json.dumps(lb.get('sort') or [])))
    db.session.flush()
    # product brands that are missing from both lists (name mismatches):
    # create deterministic rows at the tail
    known = {b.name: b for b in Brand.query.all()}
    next_id = Brand.query.order_by(Brand.id.desc()).first().id
    for p in _load('products.json')['products']:
        if p['brand'] not in known:
            next_id += 1
            slug = re.sub(r"[^a-z0-9]+", "-", p['brand'].lower()).strip('-')
            row = Brand(id=next_id, slug=slug, name=p['brand'], listed=False)
            db.session.add(row)
            known[p['brand']] = row
    db.session.flush()


def seed_brand_products():
    if BrandProduct.query.count() > 0:
        return
    brands = _load('brands.json')['brands']
    for b in brands:
        brand = Brand.query.filter_by(slug=b['slug']).first()
        if not brand:
            continue
        brand.upstream_total = b['upstream_total']
        brand.title = brand.title or b.get('title')
        brand.description = brand.description or b.get('description')
        if not brand.facets:
            brand.facets = json.dumps(b.get('facets') or [])
        for pos, pid in enumerate(b['products']):
            if Product.query.get(pid):
                db.session.add(BrandProduct(brand_id=brand.id, product_id=pid,
                                            position=pos))
    db.session.flush()


def seed_categories():
    if Category.query.count() > 0:
        return
    cats = _load('categories.json')['categories']
    for c in cats:
        row = Category(slug=c['slug'], name=c['name'],
                       upstream_total=c['upstream_total'],
                       facets=json.dumps(c.get('facets') or []),
                       sort_options=json.dumps(c.get('sort') or []))
        db.session.add(row)
        db.session.flush()
        for pos, pid in enumerate(c['products']):
            if Product.query.get(pid):
                db.session.add(CategoryProduct(category_id=row.id,
                                               product_id=pid, position=pos))
    db.session.flush()


def seed_searches():
    if SearchSnapshot.query.count() > 0:
        return
    searches = _load('searches.json')['searches']
    for s in searches:
        row = SearchSnapshot(term=s['term'],
                             upstream_total=s['upstream_total'],
                             sort_options=json.dumps(s.get('sort') or []))
        db.session.add(row)
        db.session.flush()
        for pos, pid in enumerate(s['products']):
            if Product.query.get(pid):
                db.session.add(SearchResult(snapshot_id=row.id, product_id=pid,
                                            position=pos))
    db.session.flush()


def seed_campaigns():
    if CampaignCard.query.count() > 0:
        return
    home = _load('home.json')
    for i, a in enumerate(home.get('announcements') or []):
        db.session.add(CampaignCard(section='announcement', position=i,
                                    text=a.get('text'), link=a.get('link'),
                                    kind='text'))
    # home layout plan (trim policy): the Top Categories carousel renders
    # as the hero rail, the Ski/Snow/Bike Grid as the category tiles, and
    # the Goatworthy Brands + New Arrivals carousels as the featured rails
    plan = {0: 'hero', 3: 'grid', 5: 'carousel', 11: 'carousel'}
    for si, sec in enumerate(home.get('sections') or []):
        if si not in plan:
            continue
        for i, c in enumerate(sec.get('cards') or []):
            db.session.add(CampaignCard(
                section=plan[si], position=i, text=c.get('text'),
                image=c.get('image'), alt=c.get('alt'), link=c.get('link'),
                kind=sec['kind']))
    db.session.flush()


def seed_info_pages():
    if InfoPage.query.count() > 0:
        return
    pages = _load('info_pages.json')['pages']
    for p in pages:
        db.session.add(InfoPage(slug=p['slug'], title=p['title'],
                                body=json.dumps(p.get('sections') or [])))
    db.session.flush()


def seed_users():
    if User.query.count() > 0:
        return
    fx = _load('benchmark_users.json')

    def pid_of(slug):
        p = Product.query.filter_by(slug=slug).first()
        assert p, f"product {slug} missing"
        return p

    def sku_of(product, color, size):
        cands = [s for s in product.skus
                 if (color is None or s.color == color)
                 and (size is None or s.size == size)]
        return cands[0] if cands else product.skus[0]

    users = {}
    for u in fx['users']:
        row = User(email=u['email'], display_name=u['display_name'],
                   password_hash=BENCHMARK_PASSWORD_HASH,
                   is_benchmark=True, created_at=u.get('created_at', '2026-08-20'))
        db.session.add(row)
        db.session.flush()
        users[u['email']] = row
        for a in u.get('addresses', []):
            db.session.add(Address(user_id=row.id, **a))
        for ci in u.get('cart', []):
            prod = pid_of(ci['product'])
            sku = sku_of(prod, ci.get('color'), ci.get('size'))
            db.session.add(CartItem(user_id=row.id, sku_id=sku.id,
                                    quantity=ci.get('quantity', 1),
                                    added_at=ci.get('added_at', '2026-09-29')))
        for wi in u.get('wishlist', []):
            db.session.add(WishlistItem(user_id=row.id,
                                        product_id=pid_of(wi['product']).id,
                                        added_at=wi.get('added_at', '2026-09-28')))
        for rv in u.get('reviews', []):
            prod = pid_of(rv['product'])
            db.session.add(Review(
                product_id=prod.id, user_id=row.id, author=rv.get('author'),
                title=rv.get('title'), text=rv['text'],
                rating=rv.get('rating', 5), created=rv.get('created'),
                familiarity=rv.get('familiarity'), fit=rv.get('fit'),
                size_purchased=rv.get('size_purchased'),
                photos='[]', is_seed=False))
    db.session.flush()

    for o in fx.get('orders', []):
        user = users[o['user']]
        order = Order(user_id=user.id, guest_email=None,
                      number=o['number'], status=o['status'],
                      placed_at=o['placed_at'],
                      shipping_method=o.get('shipping_method', 'Standard'),
                      shipping_cents=o.get('shipping_cents', 0),
                      payment_last4=o.get('payment_last4'),
                      address_snapshot=json.dumps(o.get('address')))
        db.session.add(order)
        db.session.flush()
        subtotal = savings = 0
        for it in o['items']:
            prod = pid_of(it['product'])
            subtotal += it['unit_price'] * it['quantity']
            if it.get('unit_list'):
                savings += (it['unit_list'] - it['unit_price']) * it['quantity']
            db.session.add(OrderItem(order_id=order.id, product_id=prod.id,
                                     product_name=it.get('name') or prod.title,
                                     brand_name=it.get('brand'),
                                     color_name=it.get('color'),
                                     size_name=it.get('size'),
                                     unit_price=it['unit_price'],
                                     unit_list=it.get('unit_list'),
                                     quantity=it['quantity']))
        order.subtotal_cents = subtotal
        order.savings_cents = savings
        order.total_cents = subtotal + order.shipping_cents
    db.session.flush()


AUTO_SEED = os.environ.get('BACKCOUNTRY_AUTO_SEED') == '1'


def main():
    with app.app_context():
        db.create_all()
        seed_brands()
        seed_products()
        seed_reviews()
        seed_brand_products()
        seed_categories()
        seed_searches()
        seed_campaigns()
        seed_info_pages()
        seed_users()
        db.session.commit()


with app.app_context():
    db.create_all()
    if AUTO_SEED or os.environ.get('BACKCOUNTRY_NO_BOOT_SEED') != '1':
        if Product.query.count() == 0:
            main()


# ------------------------------------------------------------------ login --

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ------------------------------------------------------------------ helpers --

def mirror_link(link):
    """Campaign cards carry upstream URLs verbatim; the mirror only renders
    links it can actually serve (zara precedent — unresolvable targets
    render as plain tiles/cards, never as dead links)."""
    if not link:
        return None
    m = re.match(r'^/([a-z0-9][a-z0-9\-.]*)(?:/([^/?#]+))?', link)
    if not m:
        return None
    head, sub = m.group(1), m.group(2)
    if head == 'cat':
        if sub and (Category.query.filter_by(slug=sub).first()
                    or find_subcategory(sub)):
            return link
        return None
    if head == 'brand':
        if not sub:
            return None
        b = Brand.query.filter_by(slug=sub).first()
        if b and (b.listed or BrandProduct.query.filter_by(brand_id=b.id)
                  .first()):
            return link
        return None
    if head in ('search', 'shop-all-brands', 'cart', 'checkout', 'login',
                'register', 'wish-list', 'account', 'logout'):
        return link
    if head == 'info':
        if sub and InfoPage.query.filter_by(slug=sub).first():
            return link
        return None
    if sub is None and Product.query.filter_by(slug=head).first():
        return link
    return None


@app.context_processor
def inject_globals():
    announcements = (CampaignCard.query
                     .filter_by(section='announcement')
                     .order_by(CampaignCard.position).all())
    return dict(money=money, img=img, cms_img=cms_img, dollars=dollars,
                MIRROR_TS=MIRROR_TS, announcements=announcements,
                cart_count=len(cart_items()), nav=NAV_CATEGORIES,
                facet_url=facet_url, clear_url=clear_url, price_url=price_url,
                mirror_link=mirror_link)


NAV_CATEGORIES = [
    ('Men', [('Men\'s Clothing', 'mens-clothing'),
             ('Men\'s Outerwear', 'mens-clothing'),
             ('Men\'s Footwear', 'mens-clothing'),
             ('Shop All Men\'s', 'mens-clothing')]),
    ('Women', [('Women\'s Clothing', 'womens-clothing'),
               ('Women\'s Outerwear', 'womens-clothing'),
               ('Women\'s Footwear', 'womens-clothing'),
               ('Shop All Women\'s', 'womens-clothing')]),
    ('Ski', [('Ski Gear & Clothing', 'ski'),
             ('Alpine Skis', 'ski'),
             ('Alpine Ski Boots', 'ski'),
             ('Ski Helmets & Goggles', 'ski')]),
    ('Hike & Camp', [('Hiking & Camping Gear', 'hike-camp'),
                     ('Tents', 'hike-camp'),
                     ('Sleeping Bags', 'hike-camp'),
                     ('Camp Furniture', 'hike-camp')]),
    ('Climb', [('Climbing Gear & Clothing', 'climb'),
               ('Climbing Packs', 'climb'),
               ('Climbing Shoes', 'climb'),
               ('Belay & Rappel', 'climb')]),
    ('Bike', [('Bike Gear & Clothing', 'bike'),
              ('Bikes & Frames', 'bike'),
              ('Bike Helmets', 'bike'),
              ('Bike Components', 'bike')]),
]


def cart_items():
    """The caller's cart rows (logged-in user or guest cookie)."""
    if current_user.is_authenticated:
        return (CartItem.query.filter_by(user_id=current_user.id)
                .order_by(CartItem.id).all())
    token = session.get('bc_guest')
    if not token:
        return []
    return (CartItem.query.filter_by(guest_token=token)
            .order_by(CartItem.id).all())


def cart_subtotal(items):
    return sum(i.line_total for i in items)


def cart_savings(items):
    return sum(max(0, i.line_list_total - i.line_total) for i in items)


def cart_shipping(items, method='standard'):
    if not items:
        return 0
    if method == 'express':
        return 2500
    return 0 if cart_subtotal(items) >= FREE_SHIPPING_THRESHOLD_CENTS else 695


def sort_key(sort):
    return {
        '-relevance': ('featured',), 'price': ('price_asc',),
        '-price': ('price_desc',), '-rating': ('rating',),
        'newest': ('newest',), '-discount': ('discount',),
    }.get(sort)


def apply_grid_sort(products, sort, positions=None):
    """Sort a grid by the upstream sort token; default keeps upstream order."""
    if sort == 'price':
        return sorted(products, key=lambda p: getattr(p, "filtered_min_sale", p.min_sale) or 0)
    if sort == '-price':
        return sorted(products, key=lambda p: -(getattr(p, "filtered_min_sale", p.min_sale) or 0))
    if sort == '-rating':
        return sorted(
            products,
            key=lambda p: (-(p.review_avg or 0), -(p.review_count or 0)))
    if sort == 'newest':
        return sorted(products, key=lambda p: (not p.is_past_season,
                                               p.title))
    if sort == '-discount':
        return sorted(products, key=lambda p: -(p.max_discount or 0))
    if positions:
        return sorted(products, key=lambda p: positions.get(p.id, 10_000))
    return products


# ------------------------------------------------------------------ routes --

@app.route('/')
def home():
    hero = (CampaignCard.query.filter_by(section='hero')
            .order_by(CampaignCard.position).all())
    tiles = (CampaignCard.query.filter_by(section='grid')
              .order_by(CampaignCard.position).all())
    rails = (CampaignCard.query.filter_by(section='carousel')
             .order_by(CampaignCard.position).all())
    cats = Category.query.order_by(Category.id).all()
    hc = Category.query.filter_by(slug='hike-camp').first()
    grid_products = ([cp.product for cp in
                      (CategoryProduct.query
                       .filter_by(category_id=hc.id)
                       .order_by(CategoryProduct.position).limit(8).all())]
                     if hc else [])
    return render_template('home.html', hero=hero, tiles=tiles, rails=rails,
                           categories=cats, grid_products=grid_products,
                           nav=NAV_CATEGORIES)


@app.route('/shop-all-brands')
def shop_all_brands():
    letter = (request.args.get('letter') or '').strip()
    all_brands = Brand.query.order_by(Brand.name).all()
    brands = [b for b in all_brands if b.letter == letter] if letter else all_brands
    groups = {}
    for b in all_brands:
        groups.setdefault(b.letter, []).append(b)
    return render_template('brands.html', brands=brands, groups=groups,
                           letter=letter, total_brands=len(all_brands))


# ------------------------------------------------------- grid + facets --

DEFAULT_SORT = [
    {"name": "Featured", "value": "-relevance", "selected": True},
    {"name": "Highest Rated", "value": "-rating", "selected": False},
    {"name": "New Arrivals", "value": "newest", "selected": False},
    {"name": "Lowest Price", "value": "price", "selected": False},
    {"name": "Highest Price", "value": "-price", "selected": False},
    {"name": "Percent Off", "value": "-discount", "selected": False},
]

GENDER_MAP = {"men's": "male", "mens": "male", "women's": "female",
              "womens": "female"}


def product_gender(p):
    t = (p.title or '').lower()
    if "women's" in t:
        return 'female'
    if "men's" in t:
        return 'male'
    return 'unisex'


def product_uses(p):
    uses = []
    for a in json.loads(p.features or '[]'):
        if a.get('name') in ('Activity', 'Recommended Use') and a.get('value'):
            uses.extend([v.strip() for v in a['value'].split(',')])
    return uses


def apply_grid_filters(products, args):
    """Filter a snapshot grid by the upstream-style query params."""
    color = (args.get('color') or '').strip()
    brand = (args.get('brand') or '').strip()
    gender = (args.get('gender') or '').strip()
    sale = args.get('sale', type=int)
    pmin = args.get('price-min', type=float)
    pmax = args.get('price-max', type=float)
    use = (args.get('use') or '').strip()
    size = (args.get('size') or '').strip()

    if any(v is not None and (not math.isfinite(v) or v < 0) for v in (pmin, pmax)):
        abort(400, 'Enter a finite nonnegative price.')
    out = []
    for p in products:
        if color and not any(s.color_family == color for s in p.skus):
            continue
        if brand and p.brand.name != brand:
            continue
        if gender and product_gender(p) != gender:
            continue
        if sale is not None and (p.max_discount or 0) < sale:
            continue
        if pmin is not None and ((p.min_sale or 0) < int(pmin * 100) - 1):
            continue
        if pmax is not None and ((p.min_sale or 0) > int(pmax * 100) + 1):
            continue
        if use and use.lower() not in [u.lower() for u in product_uses(p)]:
            continue
        if size and not any(s.size == size for s in p.skus):
            continue
        out.append(p)
    return out


def facet_tree_products(grid_products):
    """Products whose upstream facet tree a value could match (the snapshot)."""
    return grid_products


def grid_facets(base_products, facet_data, cat=None):
    """Build renderable facet rows.

    facet_data: the captured upstream facet tree for this listing (may be
    None for computed search). Only values that match at least one snapshot
    product render as links (zara precedent); upstream counts are shown for
    context, so every count the agent reads is an upstream value.
    """
    rows = []
    upstream = {f['name']: f for f in (facet_data or [])}

    # Categories (subcategories of this listing, from the upstream tree)
    if 'Categories' in upstream:
        children = []
        def walk(filters, out):
            for fl in filters:
                if fl.get('children'):
                    out.append((fl['name'], fl.get('url'), fl.get('count')))
                    walk(fl['children'], out)
                else:
                    out.append((fl['name'], fl.get('url'), fl.get('count')))
        walk(upstream['Categories'].get('filters') or [], children)
        rows.append(('Categories', 'cats', children[:26]))

    def values_with_upstream(fname, field):
        tree = upstream.get(fname)
        counts = {}
        if tree:
            for fl in tree.get('filters') or []:
                counts[fl['name']] = fl.get('count')
        return counts

    # Brand
    present = sorted({p.brand.name for p in base_products})
    counts = values_with_upstream('Brand', 'brand')
    rows.append(('Brand', 'brand', [(n, n, counts.get(n)) for n in present]))

    # Color
    present = sorted({s.color_family for p in base_products for s in p.skus
                      if s.color_family})
    counts = values_with_upstream('Color', 'color')
    rows.append(('Color', 'color', [(c, c, counts.get(c)) for c in present]))

    # Gender
    present_g = [g for g in ('male', 'female', 'unisex')
                 if any(product_gender(p) == g for p in base_products)]
    gcounts = values_with_upstream('Gender', 'gender')
    rows.append(('Gender', 'gender',
                  [(g, g, gcounts.get(g)) for g in present_g]))

    # Size
    present_s = sorted({s.size for p in base_products for s in p.skus},
                       key=lambda x: (len(x), x))[:14]
    scounts = values_with_upstream('Size', 'size')
    rows.append(('Size', 'size', [(s, s, scounts.get(s)) for s in present_s]))

    # Sale buckets (upstream names, snapshot matching)
    sale_rows = []
    for pct in (10, 20, 30, 40, 50):
        if any((p.max_discount or 0) >= pct for p in base_products):
            sale_rows.append((f'{pct}% and more', pct, None))
    if sale_rows:
        rows.append(('Sale', 'sale', sale_rows))

    # Price buckets (upstream names)
    price_rows = []
    for label, lo, hi in [('$0 - $49.99', 0, 49.99), ('$50 - $99.99', 50, 99.99),
                          ('$100 - $199.99', 100, 199.99),
                          ('$200 - $499.99', 200, 499.99),
                          ('$500 - $999.99', 500, 999.99),
                          ('$1000+', 1000, 99999999)]:
        if any((p.min_sale or 0) >= lo * 100 - 1 and (p.min_sale or 0) <= hi * 100 + 1
               for p in base_products):
            price_rows.append((label, (lo, hi), None))
    if price_rows:
        rows.append(('Price', 'price', price_rows))

    # Recommended Use (from upstream Features/Recommended Use attrs)
    use_vals = []
    for p in base_products:
        for a in json.loads(p.features or '[]'):
            if a.get('name') == 'Recommended Use' and a.get('value'):
                v = a['value']
                if v not in use_vals:
                    use_vals.append(v)
    if use_vals:
        counts_u = values_with_upstream('Recommended Use', 'use')
        rows.append(('Recommended Use', 'use',
                     [(v, v, None) for v in use_vals[:12]]))
    return rows


def _facet_json(cat):
    return json.loads(cat.facets or '[]')


def _qs(base, drop=None, **updates):
    """Build a query string on a base URL, preserving existing args."""
    args = {}
    color_match = re.search(r'/color/([^/]+)$', request.path)
    if color_match:
        args['color'] = color_match.group(1)
    for k in request.args:
        args[k] = request.args.get(k)
    if drop:
        for k in (drop if isinstance(drop, list) else [drop]):
            args.pop(k, None)
    args.update({k: v for k, v in updates.items() if v is not None})
    qs = urlencode({k: v for k, v in args.items() if v not in (None, '')})
    return base + ('?' + qs if qs else '')


def facet_url(key, value):
    """URL for applying one facet value on the current listing."""
    base = request.path
    if key == 'color':
        base = re.sub(r'/color/[^/]+$', '', base)
    return _qs(base, **{key: value})


def clear_url(key):
    base = request.path
    if key == 'color':
        base = re.sub(r'/color/[^/]+$', '', base)
    if key == 'price':
        return _qs(base, drop=['price-min', 'price-max'])
    return _qs(base, drop=key)


def price_url(bucket):
    lo, hi = bucket
    args = {'price-min': ('' if lo == 0 else f'{lo:g}'),
            'price-max': ('' if hi >= 99999999 else f'{hi:g}')}
    out = _qs(request.path, drop=['price-min', 'price-max'],
              **{k: v for k, v in args.items() if v})
    return out


def _sort_options(entity):
    return json.loads((entity.sort_options or '[]') if hasattr(entity, 'sort_options') else '[]')


def scope_listing_prices(products, args):
    for p in products:
        if not args.get('color') and not args.get('size'):
            continue
        variants = [s for s in p.skus if
                    (not args.get('color') or s.color_family == args['color']) and
                    (not args.get('size') or s.size == args['size'])]
        if variants:
            p.filtered_min_sale = min(s.sale_price for s in variants)
            p.filtered_max_sale = max(s.sale_price for s in variants)


def render_listing(products, positions, context, facets_data, sort,
                   upstream_total, title, breadcrumbs, args,
                   cat=None, base_url='/'):
    """Shared grid rendering for categories / brands / searches / subcats."""
    base_products = [p for p in products]
    filtered = apply_grid_filters(base_products, args)
    scope_listing_prices(filtered, args)
    filtered = apply_grid_sort(filtered, sort, positions)
    facets = grid_facets(base_products, facets_data, cat=cat)
    raw_sort = getattr(context, 'sort_options', None)
    if raw_sort is None and isinstance(context, dict):
        raw_sort = context.get('sort_options')
    sort_options = json.loads(raw_sort or '[]')
    return render_template(
        'listing.html', products=filtered, facets=facets,
        sort=sort, sort_options=sort_options,
        upstream_total=upstream_total, snapshot_total=len(base_products),
        shown_total=len(filtered), title=title, breadcrumbs=breadcrumbs,
        args=args, base_url=base_url, cat=cat, context=context)


@app.route('/cat/<slug>')
@app.route('/cat/<slug>/color/<color>')
def category_page(slug, color=None):
    cat = Category.query.filter_by(slug=slug).first()
    if cat:
        rows = (CategoryProduct.query.filter_by(category_id=cat.id)
                .order_by(CategoryProduct.position).all())
        products = [r.product for r in rows if r.product]
        positions = {r.product_id: r.position for r in rows}
        sort = (request.args.get('sort') or '-relevance').strip()
        args = request.args.copy()
        if color and not args.get('color'):
            args = args.copy(); args['color'] = color
        return render_listing(
            products, positions, cat, _facet_json(cat), sort,
            cat.upstream_total, cat.name,
            [('Home', '/'), (cat.name, None)],
            args, cat=cat, base_url=f'/cat/{cat.slug}')
    # subcategory pages derived from the upstream facet tree
    sub = find_subcategory(slug)
    if sub:
        products, positions = subcategory_products(sub)
        sort = (request.args.get('sort') or '-relevance').strip()
        sub['sort_options'] = json.dumps(DEFAULT_SORT)
        args = request.args.copy()
        if color and not args.get('color'):
            args = args.copy(); args['color'] = color
        return render_listing(
            products, positions, sub, sub.get('facets_data'), sort,
            sub['count'], sub['name'],
            [('Home', '/'), (sub['parent'], None), (sub['name'], None)],
            args, base_url=f'/cat/{slug}')
    abort(404)


def find_subcategory(slug):
    """Look up a subcategory by slug in every captured facet tree."""
    for cat in Category.query.order_by(Category.id).all():
        tree = _facet_json(cat)
        for f in tree:
            if f['name'] != 'Categories':
                continue
            def walk(filters, parent):
                for fl in filters:
                    url = fl.get('url') or ''
                    if url.rstrip('/').split('/')[-1] == slug:
                        return {'name': fl['name'], 'slug': slug,
                                'count': fl.get('count'),
                                'parent': cat.name, 'parent_slug': cat.slug,
                                'facets_data': None, 'sort_options': []}
                    if fl.get('children'):
                        found = walk(fl['children'], parent)
                        if found:
                            return found
                return None
            found = walk(f.get('filters') or [], cat.name)
            if found:
                return found
    return None


def subcategory_products(sub):
    """Snapshot products belonging to an upstream subcategory, matched by
    the canonical breadcrumb slugs captured on each product page."""
    slug = sub['slug']
    prods, positions = [], {}
    for p in Product.query.order_by(Product.id).all():
        crumbs = json.loads(p.breadcrumbs or '[]')
        if any((c.get('canonicalUrl') or '').rstrip('/').endswith('/' + slug)
               for c in crumbs):
            prods.append(p)
    prods.sort(key=lambda p: p.id)
    positions = {p.id: i for i, p in enumerate(prods)}
    return prods, positions


@app.route('/brand/<slug>')
@app.route('/brand/<slug>/cat/<catslug>')
def brand_page(slug, catslug=None):
    brand = Brand.query.filter_by(slug=slug).first_or_404()
    rows = (BrandProduct.query.filter_by(brand_id=brand.id)
            .order_by(BrandProduct.position).all())
    if not rows and not brand.listed:
        abort(404)
    products = [r.product for r in rows if r.product]
    positions = {r.product_id: r.position for r in rows}
    cat = None
    facets_data = json.loads(brand.facets or '[]')
    if catslug:
        cat = Category.query.filter_by(slug=catslug).first()
        if cat:
            in_cat = {cp.product_id for cp in
                      CategoryProduct.query.filter_by(category_id=cat.id)}
            products = [p for p in products if p.id in in_cat]

    class _Ctx:
        pass

    _Ctx.sort_options = brand.sort_options or '[]'
    sort = (request.args.get('sort') or '-relevance').strip()
    base = f'/brand/{slug}' + (f'/cat/{catslug}' if catslug else '')
    return render_listing(
        products, positions, _Ctx(), facets_data, sort,
        brand.upstream_total, brand.name,
        [('Home', '/'), ('Brands', '/shop-all-brands'), (brand.name, None)],
        request.args, cat=cat, base_url=base)


@app.route('/search')
def search():
    term = (request.args.get('q') or '').strip()
    snap = SearchSnapshot.query.filter(
        db.func.lower(SearchSnapshot.term) == term.lower()).first() if term else None
    results, positions = [], {}
    snapshot_mode = False
    upstream_total = 0
    if term:
        like = f"%{term.lower()}%"
        matched = Product.query.filter(db.or_(
            db.func.lower(Product.title).like(like),
            db.func.lower(Product.description).like(like),
            db.func.lower(Product.bottom_line).like(like))).all()
        if snap:
            snapshot_mode = True
            upstream_total = snap.upstream_total
            for r in (SearchResult.query.filter_by(snapshot_id=snap.id)
                      .order_by(SearchResult.position).all()):
                if r.product:
                    positions[r.product_id] = r.position
            results = sorted(matched,
                             key=lambda p: positions.get(p.id, 10_000))
        else:
            upstream_total = len(matched)
            results = matched
    sort = (request.args.get('sort') or '-relevance').strip()
    results = apply_grid_filters(results, request.args)
    scope_listing_prices(results, request.args)
    results = apply_grid_sort(results, sort, positions)

    class _Ctx:
        pass

    _Ctx.sort_options = (snap.sort_options if snap
                         else json.dumps(DEFAULT_SORT))
    facets = grid_facets(results, None) if term else []
    return render_template(
        'listing.html', products=results, facets=facets, sort=sort,
        sort_options=json.loads(_Ctx.sort_options or '[]'),
        upstream_total=upstream_total, snapshot_total=len(results),
        shown_total=len(results), title=f'{term} - Search Results',
        breadcrumbs=[('Home', '/'), ('Search', None)], args=request.args,
        base_url='/search', search_term=term,
        snapshot_mode=snapshot_mode, cat=None, context=_Ctx())


@app.route('/<product_slug>')
def product_page(product_slug):
    p = Product.query.filter_by(slug=product_slug).first()
    if not p:
        abort(404)
    color_key = (request.args.get('color') or '').strip()
    if not p.skus_for_color(color_key):
        color_key = p.default_color if p.skus_for_color(p.default_color) else ''
        if not color_key and p.skus:
            color_key = p.skus[0].color_key
    skus = p.skus_for_color(color_key)
    selected = None
    want_sku = request.args.get('sku') or ''
    if want_sku:
        selected = p.sku(want_sku)
        if selected and selected.color_key != color_key:
            color_key = selected.color_key
            skus = p.skus_for_color(color_key)
    gallery = (ProductImage.query
               .filter_by(product_id=p.id, color_key=color_key)
               .order_by(ProductImage.position).all())
    if not gallery:
        first = skus[0] if skus else None
        if first and first.image:
            class _G:
                def __init__(self, path):
                    self.large = path
                    self.full = path
                    self.title = 'Main'
            gallery = [_G(first.image.replace('/medium/', '/large/'))]
    crumbs = json.loads(p.breadcrumbs or '[]')
    breadcrumbs = [('Home', '/')]
    for c in crumbs[:-1]:
        url = (c.get('canonicalUrl') or '').strip()
        breadcrumbs.append((c.get('alias') or c.get('name'),
                            url if url else None))
    breadcrumbs.append((p.title, None))
    reviews = (Review.query.filter_by(product_id=p.id)
               .order_by(Review.created.desc(), Review.id.desc()).all())
    review_sort = request.args.get('review-sort') or 'recent'
    if review_sort == 'highest':
        reviews = sorted(reviews, key=lambda r: (-r.rating, r.created or ''),
                         reverse=False)
    elif review_sort == 'lowest':
        reviews = sorted(reviews, key=lambda r: (r.rating, r.created or ''))
    else:
        reviews = sorted(reviews, key=lambda r: (r.created or '', -r.id),
                         reverse=True)
    hist = json.loads(p.review_histogram or '[]')
    for r in reviews:
        if not r.is_seed:
            for h in hist:
                if h['rating'] == r.rating:
                    h['count'] = h.get('count', 0) + 1
    hist_total = sum(h.get('count') or 0 for h in hist)
    for h in hist:
        h['percentage'] = 100 * h['count'] / hist_total if hist_total else 0
    questions = (Question.query.filter_by(product_id=p.id)
                 .order_by(Question.created.desc()).all())
    in_cart = 0
    for it in cart_items():
        if it.sku.product_id == p.id:
            in_cart += it.quantity
    wished = (current_user.is_authenticated and
              WishlistItem.query.filter_by(user_id=current_user.id,
                                           product_id=p.id).count() > 0)
    first_cp = (CategoryProduct.query.filter_by(product_id=p.id)
                .order_by(CategoryProduct.position).first())
    related = []
    if first_cp:
        related = [cp.product for cp in
                   (CategoryProduct.query
                    .filter_by(category_id=first_cp.category_id)
                    .order_by(CategoryProduct.position).limit(9).all())
                   if cp.product and cp.product.id != p.id]
    return render_template(
        'product.html', p=p, color_key=color_key, skus=skus,
        selected=selected, gallery=gallery, breadcrumbs=breadcrumbs,
        color_name=p.color_name(color_key),
        reviews=reviews, hist=hist, hist_total=hist_total,
        questions=questions, review_sort=review_sort,
        in_cart=in_cart, wished=wished, related=related,
        features=json.loads(p.features or '[]'),
        bullets=json.loads(p.bullets or '[]'),
        product_gender=product_gender(p))


@app.route('/cart')
def cart():
    items = cart_items()
    method = session.get('bc_shipping_method', 'standard')
    return render_template('cart.html', items=items,
                           subtotal=cart_subtotal(items),
                           savings=cart_savings(items),
                           shipping=cart_shipping(items, method),
                           method=method,
                           threshold=FREE_SHIPPING_THRESHOLD_CENTS)


@app.route('/cart/add', methods=['POST'])
def cart_add():
    sku_id = request.form.get('sku', '')
    sku = ProductSku.query.get(sku_id)
    if not sku or not sku.in_stock:
        abort(404)
    quantity = integer(request.form.get('quantity', 1) or 1)
    if quantity > (sku.stock or 99):
        abort(400, 'Requested quantity exceeds available stock.')
    if current_user.is_authenticated:
        row = CartItem.query.filter_by(user_id=current_user.id,
                                       sku_id=sku.id).first()
        if row:
            row.quantity = integer(row.quantity + quantity, 1, sku.stock or 99)
        else:
            row = CartItem(user_id=current_user.id, sku_id=sku.id,
                           quantity=quantity, added_at='2026-09-30')
            db.session.add(row)
    else:
        token = session.get('bc_guest') or uuid.uuid4().hex
        session['bc_guest'] = token
        row = CartItem.query.filter_by(guest_token=token,
                                       sku_id=sku.id).first()
        if row:
            row.quantity = integer(row.quantity + quantity, 1, sku.stock or 99)
        else:
            row = CartItem(guest_token=token, sku_id=sku.id,
                           quantity=quantity, added_at='2026-09-30')
            db.session.add(row)
    db.session.commit()
    dest = request.form.get('next') or url_for('cart')
    return redirect(local_return(dest))


@app.route('/cart/update', methods=['POST'])
def cart_update():
    item_id = integer(request.form.get('item'), 1, 2147483647)
    item = db.session.get(CartItem, item_id)
    if not item:
        abort(404)
    if current_user.is_authenticated and item.user_id != current_user.id:
        abort(403)
    if not current_user.is_authenticated and (not session.get('bc_guest') or
            item.guest_token != session.get('bc_guest')):
        abort(403)
    action = request.form.get('action', '')
    if action == 'remove':
        db.session.delete(item)
    else:
        q = integer(request.form.get('quantity', 1) or 1)
        if not item.sku.in_stock or q > (item.sku.stock or 99):
            abort(400, 'Requested quantity exceeds available stock.')
        item.quantity = q
    db.session.commit()
    return redirect(url_for('cart'))


STATE_CHOICES = [s.strip() for s in (
    "Alabama, Alaska, Arizona, Arkansas, California, Colorado, Connecticut, "
    "Delaware, Florida, Georgia, Hawaii, Idaho, Illinois, Indiana, Iowa, "
    "Kansas, Kentucky, Louisiana, Maine, Maryland, Massachusetts, Michigan, "
    "Minnesota, Mississippi, Missouri, Montana, Nebraska, Nevada, "
    "New Hampshire, New Jersey, New Mexico, New York, North Carolina, "
    "North Dakota, Ohio, Oklahoma, Oregon, Pennsylvania, Rhode Island, "
    "South Carolina, South Dakota, Tennessee, Texas, Utah, Vermont, "
    "Virginia, Washington, West Virginia, Wisconsin, Wyoming").split(',')]


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    items = cart_items()
    if not items:
        return redirect(url_for('cart'))
    addresses = []
    if current_user.is_authenticated:
        addresses = Address.query.filter_by(user_id=current_user.id) \
            .order_by(Address.id).all()
    error = None
    method = request.form.get('shipping_method', 'standard') if request.method == 'POST' \
        else session.get('bc_shipping_method', 'standard')

    if request.method == 'POST':
        full_name = (request.form.get('full_name') or '').strip()
        line1 = (request.form.get('line1') or '').strip()
        city = (request.form.get('city') or '').strip()
        state = (request.form.get('state') or '').strip()
        zipc = (request.form.get('zip') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        email = (request.form.get('email') or '').strip()
        address_id = request.form.get('address_id', type=int)
        card = re.sub(r"\D", "", request.form.get('card', ''))
        expiry = (request.form.get('expiry') or '').strip()
        cvc = re.sub(r"\D", "", request.form.get('cvc', ''))
        method = request.form.get('shipping_method', 'standard')
        session['bc_shipping_method'] = method

        if method not in ('standard', 'express'):
            error = 'Choose Standard or Express shipping.'
        addr = None
        if not current_user.is_authenticated:
            if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                error = 'Enter a valid email address for your order.'
        else:
            addr = next((a for a in addresses if a.id == address_id), None)

        if addr is None:
            # guest checkout or a fresh address: the posted text fields are
            # the shipping address and must all be present
            if error is None and not (full_name and line1 and city and state
                                      and zipc and phone):
                error = 'Fill in every shipping address field.'
            if error is None and state not in STATE_CHOICES:
                error = 'Choose a valid US state for shipping.'
            if error is None and not re.match(r"^\d{5}(-\d{4})?$", zipc):
                error = 'Enter a valid ZIP code (e.g. 84101).'
        if error is None and (len(card) != 16 or not card.isdigit()):
            error = 'Enter a valid 16-digit card number.'
        if error is None and not re.match(r"^(0[1-9]|1[0-2])\/([0-9]{2})$",
                                          expiry.replace('-', '/')):
            error = 'Enter the card expiry as MM/YY.'
        if error is None and not (3 <= len(cvc) <= 4):
            error = 'Enter the 3- or 4-digit card security code.'

        if error is None:
            subtotal = cart_subtotal(items)
            savings = cart_savings(items)
            shipping = cart_shipping(items, method)
            seq = Order.query.count() + 1
            number = f"{9_000_000_000 + seq * 137:010d}"
            if addr is not None:
                snapshot = {'full_name': addr.full_name, 'line1': addr.line1,
                            'line2': addr.line2 or '',
                            'city': addr.city, 'state': addr.state,
                            'zip': addr.zip, 'phone': addr.phone or ''}
            else:
                snapshot = {'full_name': full_name, 'line1': line1,
                            'line2': (request.form.get('line2') or '').strip(),
                            'city': city, 'state': state, 'zip': zipc,
                            'phone': phone}
            order = Order(
                user_id=current_user.id if current_user.is_authenticated else None,
                guest_email=None if current_user.is_authenticated else email,
                number=number, status='placed', placed_at='2026-09-30',
                shipping_method='Standard' if method == 'standard' else 'Express',
                shipping_cents=shipping, subtotal_cents=subtotal,
                savings_cents=savings, total_cents=subtotal + shipping,
                payment_last4=card[-4:],
                address_snapshot=json.dumps(snapshot))
            db.session.add(order)
            db.session.flush()
            for it in items:
                db.session.add(OrderItem(
                    order_id=order.id, product_id=it.sku.product_id,
                    product_name=it.sku.product.title,
                    brand_name=it.sku.product.brand.name,
                    color_name=it.sku.color, size_name=it.sku.size,
                    unit_price=it.unit_price, unit_list=it.unit_list,
                    quantity=it.quantity))
                db.session.delete(it)
            db.session.commit()
            session['bc_orders'] = session.get('bc_orders', []) + [number]
            return redirect(url_for('order_confirmation', number=number))

    return render_template('checkout.html', items=items,
                           addresses=addresses, error=error, method=method,
                           subtotal=cart_subtotal(items),
                           savings=cart_savings(items),
                           shipping=cart_shipping(items, method),
                           states=STATE_CHOICES)


@app.route('/order-confirmation/<number>')
def order_confirmation(number):
    order = Order.query.filter_by(number=number).first_or_404()
    if order.user_id:
        if not current_user.is_authenticated or \
                current_user.id != order.user_id:
            abort(403)
    if not order.user_id and number not in session.get('bc_orders', []):
        abort(403)
    return render_template('order_confirmation.html', order=order)


# -------------------------------------------------------------------- auth --

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    mode = request.args.get('mode') or request.form.get('mode') or 'login'
    if request.method == 'POST' and mode == 'login':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            # merge the guest cart into the account cart
            token = session.get('bc_guest')
            if token:
                for it in (CartItem.query.filter_by(guest_token=token)
                           .order_by(CartItem.id).all()):
                    row = CartItem.query.filter_by(user_id=user.id,
                                                   sku_id=it.sku_id).first()
                    if row:
                        row.quantity += it.quantity
                        db.session.delete(it)
                    else:
                        it.user_id = user.id
                        it.guest_token = None
                session.pop('bc_guest', None)
            db.session.commit()
            dest = request.args.get('next') or url_for('account')
            return redirect(local_return(dest))
        error = 'Invalid email or password.'
    return render_template('login.html', error=error, mode=mode)


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        name = (request.form.get('name') or '').strip()
        password = request.form.get('password') or ''
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            error = 'Enter a valid email address.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif User.query.filter_by(email=email).first():
            error = 'An account with this email already exists.'
        else:
            user = User(email=email, display_name=name,
                        password_hash=bcrypt.generate_password_hash(password)
                        .decode(), is_benchmark=False, created_at='2026-09-30')
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('account'))
    return render_template('login.html', error=error, mode='register')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


# ----------------------------------------------------------------- account --

@app.route('/account')
@login_required
def account():
    orders = (Order.query.filter_by(user_id=current_user.id)
              .order_by(Order.id.desc()).all())
    return render_template('account.html', orders=orders)


@app.route('/account/orders/<number>')
@login_required
def account_order(number):
    order = Order.query.filter_by(number=number,
                                   user_id=current_user.id).first_or_404()
    return render_template('order_detail.html', order=order)


@app.route('/account/addresses', methods=['GET', 'POST'])
@login_required
def addresses():
    error = None
    if request.method == 'POST':
        full_name = (request.form.get('full_name') or '').strip()
        line1 = (request.form.get('line1') or '').strip()
        city = (request.form.get('city') or '').strip()
        state = (request.form.get('state') or '').strip()
        zipc = (request.form.get('zip') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        if not (full_name and line1 and city and state and zipc and phone):
            error = 'Fill in every address field.'
        elif not re.match(r"^\d{5}(-\d{4})?$", zipc):
            error = 'Enter a valid ZIP code (e.g. 84101).'
        elif state not in STATE_CHOICES:
            error = 'Choose a valid US state.'
        else:
            make_default = request.form.get('is_default') == '1'
            if make_default:
                for a in Address.query.filter_by(user_id=current_user.id):
                    a.is_default = False
            db.session.add(Address(user_id=current_user.id,
                                   label=(request.form.get('label') or '').strip(),
                                   full_name=full_name, line1=line1,
                                   line2=(request.form.get('line2') or '').strip(),
                                   city=city, state=state, zip=zipc,
                                   phone=phone, is_default=make_default or
                                   Address.query.filter_by(user_id=current_user.id).count() == 0))
            db.session.commit()
            return redirect(url_for('addresses'))
    rows = Address.query.filter_by(user_id=current_user.id) \
        .order_by(Address.id).all()
    return render_template('addresses.html', addresses=rows, error=error,
                           states=STATE_CHOICES)


@app.route('/account/addresses/<int:addr_id>/default', methods=['POST'])
@login_required
def address_default(addr_id):
    addr = db.session.get(Address, addr_id)
    if not addr or addr.user_id != current_user.id:
        abort(404)
    for a in Address.query.filter_by(user_id=current_user.id):
        a.is_default = (a.id == addr_id)
    db.session.commit()
    return redirect(url_for('addresses'))


@app.route('/account/addresses/<int:addr_id>/delete', methods=['POST'])
@login_required
def address_delete(addr_id):
    addr = db.session.get(Address, addr_id)
    if not addr or addr.user_id != current_user.id:
        abort(404)
    was_default = addr.is_default
    db.session.delete(addr)
    db.session.flush()
    if was_default:
        # promote the first remaining address so a default always exists
        nxt = (Address.query.filter_by(user_id=current_user.id)
               .order_by(Address.id).first())
        if nxt:
            nxt.is_default = True
    db.session.commit()
    return redirect(url_for('addresses'))


@app.route('/wish-list')
@login_required
def wishlist():
    rows = (WishlistItem.query.filter_by(user_id=current_user.id)
            .order_by(WishlistItem.id.desc()).all())
    return render_template('wishlist.html', items=rows)


@app.route('/wish-list/toggle', methods=['POST'])
def wishlist_toggle():
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=request.form.get('next') or '/wish-list'))
    pid = request.form.get('product', '')
    p = Product.query.get(pid)
    if not p:
        abort(404)
    row = WishlistItem.query.filter_by(user_id=current_user.id,
                                       product_id=p.id).first()
    if row:
        db.session.delete(row)
    else:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=p.id,
                                    added_at='2026-09-30'))
    db.session.commit()
    return redirect(local_return(request.form.get('next'), '/wish-list'))


# ---------------------------------------------------------------- reviews --

@app.route('/<product_slug>/write-review', methods=['POST'])
def write_review(product_slug):
    p = Product.query.filter_by(slug=product_slug).first_or_404()
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=f'/{product_slug}'))
    rating = request.form.get('rating', type=int)
    title = (request.form.get('title') or '').strip()
    text = (request.form.get('text') or '').strip()
    familiarity = (request.form.get('familiarity') or '').strip()
    fit = (request.form.get('fit') or '').strip()
    size_purchased = (request.form.get('size_purchased') or '').strip()
    if rating not in (1, 2, 3, 4, 5):
        return redirect(f'/{product_slug}?review-error=rating#reviews')
    if len(text) < 10:
        return redirect(f'/{product_slug}?review-error=text#reviews')
    db.session.add(Review(
        product_id=p.id, user_id=current_user.id,
        author=current_user.display_name,
        title=title or 'Review', text=text, rating=rating,
        created='2026-09-30T12:00:00.000+00:00',
        familiarity=familiarity or None, fit=fit or None,
        size_purchased=size_purchased or None,
        photos='[]', is_seed=False))
    db.session.commit()
    return redirect(f'/{product_slug}?review-posted=1#reviews')


@app.route('/<product_slug>/ask-question', methods=['POST'])
def ask_question(product_slug):
    p = Product.query.filter_by(slug=product_slug).first_or_404()
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=f'/{product_slug}'))
    text = (request.form.get('text') or '').strip()
    if len(text) < 10:
        return redirect(f'/{product_slug}?question-error=text#questions')
    db.session.add(Question(product_id=p.id,
                            author=current_user.display_name,
                            text=text, created='2026-09-30T12:00:00.000+00:00'))
    db.session.commit()
    return redirect(f'/{product_slug}?question-posted=1#questions')


# ------------------------------------------------------------------- info --

@app.route('/info/<slug>')
def info_page(slug):
    page = InfoPage.query.filter_by(slug=slug).first_or_404()
    return render_template('info.html', page=page,
                           sections=json.loads(page.body or '[]'))


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404
