#!/usr/bin/env python3
"""Michaels mirror — Flask application.

Mirrors michaels.com (arts & crafts retail): catalog browsing with filters,
product detail with variants and reviews, cart, coupon application,
checkout, account/order management, savings (coupons), store locator,
classes and rewards. All catalog data is real, captured from the upstream
site (see source_data.json provenance).
"""
import json
import os
import re
from datetime import datetime, date

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_bcrypt import Bcrypt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'michaels-mirror-dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'michaels.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to access your account.'
login_manager.login_message_category = 'info'

app.jinja_env.filters['from_json'] = json.loads

# Deterministic reference date: upstream data was captured 2026-09-23 and all
# seeded dates (coupons, classes, orders) are pinned relative to it.
MIRROR_REFERENCE_DATE = date(2026, 9, 23)

STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or',
              'is', 'it', 'by', 'with', 'my', 'your'}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), default='')
    rewards_member = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime(2026, 1, 15))

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

    def cart_count(self):
        from flask import current_app
        return sum(i.qty for i in CartItem.query.filter_by(user_id=self.id).all())


class Address(db.Model):
    __tablename__ = 'addresses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    label = db.Column(db.String(60), default='Home')
    line1 = db.Column(db.String(200), nullable=False)
    line2 = db.Column(db.String(200), default='')
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    is_default = db.Column(db.Boolean, default=False)


class PaymentCard(db.Model):
    __tablename__ = 'payment_cards'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    label = db.Column(db.String(60), default='Personal')
    brand = db.Column(db.String(30), nullable=False)
    last4 = db.Column(db.String(4), nullable=False)
    exp_month = db.Column(db.Integer, nullable=False)
    exp_year = db.Column(db.Integer, nullable=False)
    is_default = db.Column(db.Boolean, default=False)


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(90), nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    top_slug = db.Column(db.String(60), nullable=False, index=True)  # '' for top-level
    sort = db.Column(db.Integer, default=0)

    products = db.relationship('Product', backref='subcategory', lazy=True)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(40), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    brand = db.Column(db.String(120), default='')
    subcategory_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    description = db.Column(db.Text, default='')
    details = db.Column(db.Text, default='[]')          # JSON list of bullets
    price = db.Column(db.Float, nullable=False, default=0.0)   # representative price
    price_low = db.Column(db.Float, nullable=False, default=0.0)
    price_high = db.Column(db.Float, nullable=False, default=0.0)
    unit_price = db.Column(db.String(60), default='')    # e.g. "$0.59 ea."
    promo_text = db.Column(db.String(300), default='')
    promo_type = db.Column(db.String(30), default='')    # pct_off_cart | b1g1_50 | ''
    rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    rating_dist = db.Column(db.Text, default='{}')   # real upstream star distribution
    color = db.Column(db.String(80), default='')
    varies_by = db.Column(db.String(20), default='color')  # color | size
    images = db.Column(db.Text, default='[]')            # JSON list, relative to /static/images/
    is_bestseller = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=False)
    is_clearance = db.Column(db.Boolean, default=False)
    is_online_only = db.Column(db.Boolean, default=False)
    aisle = db.Column(db.String(20), default='')
    upstream_url = db.Column(db.String(400), default='')
    sort = db.Column(db.Integer, default=0)

    variants = db.relationship('ProductVariant', backref='product', lazy=True,
                               order_by='ProductVariant.sku', cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='product', lazy=True,
                              order_by='Review.date.desc()', cascade='all, delete-orphan')
    questions = db.relationship('Question', backref='product', lazy=True,
                                 order_by='Question.date.desc()', cascade='all, delete-orphan')

    def image_list(self):
        return json.loads(self.images or '[]')

    def colors(self):
        seen = []
        for v in self.variants:
            if v.color and v.color not in seen:
                seen.append(v.color)
        return seen

    def variants_sorted(self):
        return sorted(self.variants, key=lambda v: (v.price, v.sku))

    def variant_label(self):
        return 'Size' if self.varies_by == 'size' else 'Color'

    def dist(self):
        try:
            return {int(k): int(v) for k, v in json.loads(self.rating_dist or '{}').items()}
        except Exception:
            return {}

    def price_for(self, variant_sku):
        if variant_sku:
            for v in self.variants:
                if v.sku == variant_sku:
                    return v.price
        return self.price

    def pickup_store(self):
        store = Store.query.filter_by(number=8847).first()
        return store


class ProductVariant(db.Model):
    __tablename__ = 'product_variants'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    sku = db.Column(db.String(60), nullable=False)
    color = db.Column(db.String(80), default='')
    price = db.Column(db.Float, nullable=False, default=0.0)
    availability = db.Column(db.String(30), default='InStock')


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    author = db.Column(db.String(80), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), default='')
    text = db.Column(db.Text, default='')
    date = db.Column(db.String(10), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    helpful_count = db.Column(db.Integer, default=0)


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    author = db.Column(db.String(80), nullable=False)
    text = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(10), nullable=False)
    answer_count = db.Column(db.Integer, default=0)


class Store(db.Model):
    __tablename__ = 'stores'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(140), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    zip = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    hours = db.Column(db.Text, default='')               # '|' separated Mon..Sun
    services = db.Column(db.Text, default='{}')          # JSON map
    lat = db.Column(db.Float, default=0.0)
    lon = db.Column(db.Float, default=0.0)

    def service_list(self):
        return json.loads(self.services or '{}')

    def hours_list(self):
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        raw = (self.hours or '').split('|')
        return list(zip(days, raw)) if raw else []


class Coupon(db.Model):
    __tablename__ = 'coupons'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30))                     # nullable for in-store coupons
    headline = db.Column(db.String(80), nullable=False)
    scope = db.Column(db.String(200), nullable=False)
    channel = db.Column(db.String(20), default='both')  # online | instore | both
    valid_from = db.Column(db.String(10), nullable=False)
    valid_to = db.Column(db.String(10), nullable=False)
    description = db.Column(db.Text, default='')


class ClassEvent(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False)     # live | tutorial
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(60), default='')
    date = db.Column(db.String(10), default='')         # live classes only
    time_text = db.Column(db.String(80), default='')
    platform = db.Column(db.String(120), default='')
    host = db.Column(db.String(120), default='')
    duration = db.Column(db.String(30), default='')    # tutorials only
    is_new = db.Column(db.Boolean, default=False)
    image = db.Column(db.String(200), default='')


class ClassRegistration(db.Model):
    __tablename__ = 'class_registrations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    class_event_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    registered_at = db.Column(db.String(10), nullable=False)
    attendee_name = db.Column(db.String(120), default='')

    class_event = db.relationship('ClassEvent', lazy=True)


class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    variant_sku = db.Column(db.String(60), default='')
    color = db.Column(db.String(80), default='')
    qty = db.Column(db.Integer, nullable=False, default=1)
    added_at = db.Column(db.DateTime, default=datetime(2026, 9, 20))

    product = db.relationship('Product', lazy=True)


class WishlistItem(db.Model):
    __tablename__ = 'wishlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime(2026, 9, 18))

    product = db.relationship('Product', lazy=True)


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False)
    status = db.Column(db.String(40), nullable=False, default='Processing')
    placed_at = db.Column(db.String(10), nullable=False)
    delivery_method = db.Column(db.String(20), nullable=False, default='Ship')  # Ship | Pickup
    address_line = db.Column(db.String(300), default='')
    card_brand = db.Column(db.String(30), default='')
    card_last4 = db.Column(db.String(4), default='')
    subtotal = db.Column(db.Float, nullable=False, default=0.0)
    discount = db.Column(db.Float, nullable=False, default=0.0)
    shipping = db.Column(db.Float, nullable=False, default=0.0)
    tax = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)
    promo_code = db.Column(db.String(30), default='')

    items = db.relationship('OrderItem', backref='order', lazy=True,
                            cascade='all, delete-orphan')

    def item_count(self):
        return sum(i.qty for i in self.items)


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    variant_sku = db.Column(db.String(60), default='')
    color = db.Column(db.String(80), default='')
    qty = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False, default=0.0)

    product = db.relationship('Product', lazy=True)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokens(query):
    return [t.lower() for t in re.split(r'\W+', query)
            if t.lower() not in STOP_WORDS and len(t) > 1]


def scored_search(query, products, fields=('name', 'brand', 'description', 'color')):
    tokens = _tokens(query)
    if not tokens:
        return products
    phrase = re.sub(r'\s+', ' ', query.strip().lower())
    results = []
    for p in products:
        name = (p.name or '').lower()
        text = ' '.join((getattr(p, f) or '') for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            if phrase and phrase in name:
                score += 3          # exact-name matches dominate
            elif tokens and all(t in name for t in tokens):
                score += 1          # all tokens in the name: strong match
            results.append((p, score))
    results.sort(key=lambda x: (-x[1], -x[0].review_count))
    return [r[0] for r in results]


def apply_sort(products, sort):
    if sort == 'price_low':
        return sorted(products, key=lambda p: p.price_low)
    if sort == 'price_high':
        return sorted(products, key=lambda p: -p.price_low)
    if sort == 'rating':
        return sorted(products, key=lambda p: (-p.rating, -p.review_count))
    if sort == 'newest':
        return sorted(products, key=lambda p: (not p.is_new, p.sort))
    # default: Best Sellers (rating*review volume), mirroring upstream default
    return sorted(products, key=lambda p: (-p.review_count * (p.rating or 1), p.sort))


def _cart_summary_pinned(user, reference_date):
    """Cart summary honoring BOGO item promos and coupon validity (pinned date)."""
    items = CartItem.query.filter_by(user_id=user.id).order_by(CartItem.id).all()
    subtotal = sum(i.product.price_for(i.variant_sku) * i.qty for i in items)

    # --- Buy One Get One item-level promos (mix & match) ---
    bogo_free_units = []   # (item, unit_price) for b1g1_free products
    bogo_50_units = []
    for i in items:
        unit = i.product.price_for(i.variant_sku)
        if i.product.promo_type == 'b1g1_free':
            bogo_free_units.extend([unit] * i.qty)
        elif i.product.promo_type == 'b1g1_50':
            bogo_50_units.extend([unit] * i.qty)
    bogo_discount = 0.0
    bogo_free_units.sort(reverse=True)
    for idx in range(1, len(bogo_free_units), 2):
        bogo_discount += bogo_free_units[idx]
    bogo_50_units.sort(reverse=True)
    for idx in range(1, len(bogo_50_units), 2):
        bogo_discount += bogo_50_units[idx] * 0.5
    bogo_discount = round(bogo_discount, 2)

    # --- promo code: applies to items without an item-level BOGO promo ---
    code = session.get('promo_code', '')
    discount = bogo_discount
    coupon = None
    code_discount = 0.0
    if code:
        coupon = Coupon.query.filter_by(code=code).first()
        if coupon and coupon.channel != 'instore' and coupon.valid_from <= reference_date.isoformat() <= coupon.valid_to:
            if '30% OFF' in coupon.headline:
                regular = sum(i.product.price_for(i.variant_sku) * i.qty for i in items
                              if i.product.promo_type not in ('b1g1_free', 'b1g1_50'))
                code_discount = round(regular * 0.30, 2)
                discount += code_discount
    shipping = 0.0 if (subtotal - discount) >= 49 or subtotal == 0 else 5.99
    tax = round((subtotal - discount) * 0.0925, 2)
    total = max(0.0, subtotal - discount + shipping + tax)
    return {
        'rows': items, 'subtotal': round(subtotal, 2), 'discount': round(discount, 2),
        'bogo_discount': bogo_discount, 'code_discount': code_discount,
        'shipping': round(shipping, 2), 'tax': round(tax, 2), 'total': round(total, 2),
        'coupon': coupon, 'code': code,
    }


def _active_classes():
    return ClassEvent.query.filter_by(kind='live').order_by(ClassEvent.date).all()


def _nav_categories():
    top = Category.query.filter_by(top_slug='').order_by(Category.sort).all()
    out = []
    for c in top:
        subs = Category.query.filter_by(top_slug=c.slug).order_by(Category.sort).all()
        out.append({'slug': c.slug, 'name': c.name,
                    'subcategories': [{'slug': s.slug, 'name': s.name} for s in subs]})
    return out


@app.context_processor
def inject_globals():
    return {
        'nav_categories': _nav_categories,
        'cart_count': (current_user.cart_count() if current_user.is_authenticated else 0),
        'home_store': Store.query.filter_by(number=8847).first(),
        'reference_date': MIRROR_REFERENCE_DATE,
    }


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    banners = sorted(os.listdir(os.path.join(BASE_DIR, 'static', 'images', 'banners')))
    banners = [f'banners/{b}' for b in banners if b.endswith('.jpg')]
    bestsellers = Product.query.filter_by(is_bestseller=True).order_by(Product.sort).limit(12).all()
    new_arrivals = Product.query.filter_by(is_new=True).order_by(Product.sort).limit(12).all()
    clearance = Product.query.filter_by(is_clearance=True).order_by(Product.sort).limit(12).all()
    coupons = Coupon.query.order_by(Coupon.id).all()
    live_classes = _active_classes()[:4]
    tutorials = ClassEvent.query.filter_by(kind='tutorial', is_new=True).order_by(ClassEvent.id).limit(6).all()
    return render_template('index.html', banners=banners, bestsellers=bestsellers,
                           new_arrivals=new_arrivals, clearance=clearance,
                           coupons=coupons, live_classes=live_classes,
                           tutorials=tutorials)


@app.route('/shop/<slug>')
def shop(slug):
    top = Category.query.filter_by(top_slug='', slug=slug).first_or_404()
    sub = request.args.get('sub', '')
    subcat = None
    if sub:
        subcat = Category.query.filter_by(top_slug=slug, slug=sub).first_or_404()
    products = _category_products(slug, subcat)
    return _render_listing(slug, top.name, products, f'/shop/{slug}',
                           subcategories=Category.query.filter_by(top_slug=slug).order_by(Category.sort).all(),
                           sub_slug=sub)


@app.route('/search')
def search():
    query = (request.args.get('q') or '').strip()
    all_products = Product.query.all()
    products = scored_search(query, all_products) if query else all_products
    return _render_listing(slug='search', name=f'Search results for "{query}"' if query else 'Search',
                           products=products, base_url='/search', subcategories=[], sub_slug='',
                           query=query)


def _category_products(top_slug, subcat=None):
    if subcat is not None:
        return list(subcat.products)
    out = []
    for sub in Category.query.filter_by(top_slug=top_slug).order_by(Category.sort).all():
        out.extend(sub.products)
    return out


PRICE_FILTERS = {
    'under10': ('Under $10', lambda p: p.price_high < 10),
    '10-25': ('$10 - $25', lambda p: p.price_low >= 10 and p.price_high <= 25),
    '25-50': ('$25 - $50', lambda p: p.price_low >= 25 and p.price_high <= 50),
    '50-100': ('$50 - $100', lambda p: p.price_low >= 50 and p.price_high <= 100),
    'over100': ('$100+', lambda p: p.price_low >= 100),
}


def _render_listing(slug, name, products, base_url, subcategories, sub_slug, query=''):
    # filters
    f_price = request.args.get('price', '')
    f_brand = request.args.get('brand', '')
    f_rating = request.args.get('rating', '')
    f_color = request.args.get('color', '')
    f_avail = request.args.get('availability', '')
    ways = request.args.get('ways', '')
    sort = request.args.get('sort', 'best')
    page = max(1, int(request.args.get('page', 1) or 1))
    per_page = 24

    if ways == 'sale':
        products = [p for p in products if p.is_clearance or p.promo_type]
    elif ways == 'clearance':
        products = [p for p in products if p.is_clearance]
    elif ways == 'new-arrivals':
        products = [p for p in products if p.is_new]

    # facet sources (computed pre-filter for stable facet lists)
    brands = sorted({p.brand for p in products if p.brand})
    colors = sorted({c for p in products for c in p.colors()})

    if f_price in PRICE_FILTERS:
        products = [p for p in products if PRICE_FILTERS[f_price][1](p)]
    if f_brand:
        products = [p for p in products if p.brand == f_brand]
    if f_rating:
        products = [p for p in products if p.rating >= float(f_rating)]
    if f_color:
        products = [p for p in products if f_color.lower() in [c.lower() for c in p.colors()]]
    if f_avail == 'pickup':
        products = [p for p in products if not p.is_online_only]
    elif f_avail == 'online':
        products = [p for p in products if p.is_online_only]

    if slug == 'search' and sort == 'best':
        pass  # keep scored relevance order for searches (upstream default)
    else:
        products = apply_sort(products, sort)
    total = len(products)
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    shown = products[(page - 1) * per_page: page * per_page]

    def url_for_page(p, **overrides):
        from urllib.parse import urlencode
        args = {k: v for k, v in request.args.items() if k != 'page'}
        args['page'] = p
        args.update({k: v for k, v in overrides.items() if v})
        for k, v in list(args.items()):
            if not v:
                del args[k]
        # base_url carries no query string: urlencode(args) already holds the
        # complete query, so the separator is always '?' (a '&' here produced
        # /search&category=... 404s on every filtered/paginated listing page)
        return base_url + '?' + urlencode(args)

    return render_template('listing.html', slug=slug, name=name, products=shown,
                           total=total, page=page, pages=pages, base_url=base_url,
                           subcategories=subcategories, sub_slug=sub_slug,
                           brands=brands, colors=colors, price_filters=PRICE_FILTERS,
                           query=query, url_for_page=url_for_page,
                           ways=ways, sort=sort,
                           f_price=f_price, f_brand=f_brand, f_rating=f_rating,
                           f_color=f_color, f_avail=f_avail)


@app.route('/product/<slug>')
def product_detail(slug):
    p = Product.query.filter_by(slug=slug).first_or_404()
    rel = Product.query.filter(Product.subcategory_id == p.subcategory_id,
                               Product.id != p.id).limit(8).all()
    if len(rel) < 4:
        more = Product.query.filter(Product.id != p.id,
                                     Product.brand == p.brand).limit(8).all()
        for m in more:
            if m not in rel:
                rel.append(m)
            if len(rel) >= 8:
                break
    top = p.subcategory.top_slug if p.subcategory else ''
    return render_template('product.html', p=p, related=rel[:8], top_slug=top)


@app.route('/product/<slug>/reviews')
def product_reviews(slug):
    p = Product.query.filter_by(slug=slug).first_or_404()
    rating_filter = request.args.get('rating', '')
    reviews = p.reviews
    if rating_filter:
        reviews = [r for r in reviews if r.rating == int(rating_filter)]
    dist = {i: 0 for i in range(1, 6)}
    for r in p.reviews:
        dist[r.rating] += 1
    return render_template('reviews.html', p=p, reviews=reviews, dist=dist,
                           rating_filter=rating_filter)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            _apply_pending_cart_add()
            next_url = request.args.get('next') or request.form.get('next') or url_for('index')
            return redirect(next_url)
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not name or not email or len(password) < 8:
            flash('Please fill all fields; password must be at least 8 characters.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
        else:
            user = User(email=email, name=name)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('promo_code', None)
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

@app.route('/cart')
def cart():
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=url_for('cart')))
    summary = _cart_summary_pinned(current_user, MIRROR_REFERENCE_DATE)
    return render_template('cart.html', s=summary)


@app.route('/cart/add', methods=['POST'])
def cart_add():
    if not current_user.is_authenticated:
        # remember the intended add so it lands in the cart right after login;
        # keep a LIST so consecutive anonymous adds all survive until sign-in
        # (no single-slot overwrite) — capped to keep the session cookie small
        pending = session.get('pending_cart_adds', [])
        pending.append({
            'slug': request.form.get('slug', ''),
            'variant_sku': request.form.get('variant_sku', ''),
            'qty': max(1, min(99, int(request.form.get('qty', 1) or 1))),
            'color': request.form.get('color', ''),
        })
        session['pending_cart_adds'] = pending[-10:]
        return redirect(url_for('login', next=request.form.get('next', url_for('cart'))))
    slug = request.form.get('slug', '')
    p = Product.query.filter_by(slug=slug).first_or_404()
    variant_sku = request.form.get('variant_sku', '')
    qty = max(1, min(99, int(request.form.get('qty', 1) or 1)))
    color = request.form.get('color', '')
    if not color and variant_sku:
        for v in p.variants:
            if v.sku == variant_sku:
                color = v.color
    existing = CartItem.query.filter_by(user_id=current_user.id, product_id=p.id,
                                        variant_sku=variant_sku).first()
    if existing:
        existing.qty = min(99, existing.qty + qty)
    else:
        db.session.add(CartItem(user_id=current_user.id, product_id=p.id,
                                variant_sku=variant_sku, color=color, qty=qty))
    db.session.commit()
    flash(f'Added to cart: {p.name}', 'success')
    return redirect(request.form.get('next') or url_for('cart'))


def _apply_pending_cart_add():
    """After login, apply remembered add-to-cart intents, oldest first.
    The intents are stored as a list, so several consecutive anonymous
    adds all land in the cart instead of only the most recent one."""
    pending = session.pop('pending_cart_adds', None) or []
    added_names = []
    for pend in pending:
        p = Product.query.filter_by(slug=pend.get('slug', '')).first()
        if not p:
            continue
        variant_sku = pend.get('variant_sku', '')
        qty = max(1, min(99, int(pend.get('qty', 1) or 1)))
        color = pend.get('color', '')
        if not color and variant_sku:
            for v in p.variants:
                if v.sku == variant_sku:
                    color = v.color
        existing = CartItem.query.filter_by(user_id=current_user.id, product_id=p.id,
                                            variant_sku=variant_sku).first()
        if existing:
            existing.qty = min(99, existing.qty + qty)
        else:
            db.session.add(CartItem(user_id=current_user.id, product_id=p.id,
                                    variant_sku=variant_sku, color=color, qty=qty))
        if p.name not in added_names:
            added_names.append(p.name)
    if added_names:
        db.session.commit()
        flash('Added to cart: ' + ', '.join(added_names), 'success')


@app.route('/cart/update', methods=['POST'])
def cart_update():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    item_id = int(request.form.get('item_id', 0) or 0)
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    qty = int(request.form.get('qty', 1) or 1)
    if qty <= 0:
        db.session.delete(item)
    else:
        item.qty = min(99, qty)
    db.session.commit()
    return redirect(url_for('cart'))


@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    item_id = int(request.form.get('item_id', 0) or 0)
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash('Item removed from cart.', 'success')
    return redirect(url_for('cart'))


@app.route('/cart/coupon', methods=['POST'])
def cart_coupon():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    code = (request.form.get('code', '') or '').strip().upper()
    action = request.form.get('action', 'apply')
    if action == 'remove':
        session.pop('promo_code', None)
        flash('Promo code removed.', 'info')
        return redirect(url_for('cart'))
    coupon = Coupon.query.filter(db.func.upper(Coupon.code) == code).first() if code else None
    if not coupon:
        flash('That promo code is not recognized.', 'error')
        return redirect(url_for('cart'))
    if coupon.channel == 'instore':
        flash('This coupon is valid in store only and cannot be applied online.', 'error')
        return redirect(url_for('cart'))
    if not (coupon.valid_from <= MIRROR_REFERENCE_DATE.isoformat() <= coupon.valid_to):
        flash('This promo code has expired.', 'error')
        return redirect(url_for('cart'))
    session['promo_code'] = coupon.code
    flash(f'Promo code {coupon.code} applied: {coupon.headline} {coupon.scope}.', 'success')
    return redirect(url_for('cart'))


# ---------------------------------------------------------------------------
# Checkout & orders
# ---------------------------------------------------------------------------

SHIPPING_FREE_THRESHOLD = 49.0
TAX_RATE = 0.0925


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    summary = _cart_summary_pinned(current_user, MIRROR_REFERENCE_DATE)
    if not summary['rows']:
        flash('Your cart is empty.', 'info')
        return redirect(url_for('index'))
    addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.id).all()
    cards = PaymentCard.query.filter_by(user_id=current_user.id).order_by(PaymentCard.id).all()
    if request.method == 'POST':
        step = request.form.get('step', '')
        if step == 'details':
            method = request.form.get('delivery_method', 'Ship')
            session['checkout_method'] = method
            session['checkout_address'] = request.form.get('address_id', '')
            session['checkout_card'] = request.form.get('card_id', '')
            errors = []
            if method == 'Ship' and not session['checkout_address']:
                errors.append('Please choose a shipping address.')
            if not session['checkout_card']:
                errors.append('Please choose a payment method.')
            if errors:
                for e in errors:
                    flash(e, 'error')
            else:
                return redirect(url_for('checkout'))
        else:
            # place order
            method = session.get('checkout_method', 'Ship')
            address_id = session.get('checkout_address', '')
            card_id = session.get('checkout_card', '')
            address = Address.query.filter_by(id=int(address_id or 0), user_id=current_user.id).first() if address_id else None
            card = PaymentCard.query.filter_by(id=int(card_id or 0), user_id=current_user.id).first() if card_id else None
            if not card:
                flash('Please choose a payment method.', 'error')
                return redirect(url_for('checkout'))
            subtotal = summary['subtotal']
            discount = summary['discount']
            shipping = 0.0
            if method == 'Ship' and (subtotal - discount) < SHIPPING_FREE_THRESHOLD:
                shipping = 5.99
            tax = round((subtotal - discount) * TAX_RATE, 2)
            total = max(0.0, subtotal - discount + shipping + tax)
            order_number = f"MI{MIRROR_REFERENCE_DATE.strftime('%y%m%d')}{current_user.id:02d}{len(current_user_orders(current_user)) + 1:03d}"
            order = Order(user_id=current_user.id, order_number=order_number,
                          status='Processing', placed_at=MIRROR_REFERENCE_DATE.isoformat(),
                          delivery_method=method,
                          address_line=(f'{address.line1}, {address.city}, {address.state} {address.zip_code}' if address else
                                        'Store Pickup - Parkway Supercenter, 17400 Southcenter Pkwy, Tukwila, WA 98188'),
                          card_brand=card.brand, card_last4=card.last4,
                          subtotal=round(subtotal, 2), discount=round(discount, 2),
                          shipping=round(shipping, 2), tax=tax, total=round(total, 2),
                          promo_code=summary['code'])
            db.session.add(order)
            db.session.flush()
            for item in summary['rows']:
                db.session.add(OrderItem(order_id=order.id, product_id=item.product_id,
                                         name=item.product.name, variant_sku=item.variant_sku,
                                         color=item.color, qty=item.qty,
                                         unit_price=item.product.price_for(item.variant_sku)))
                db.session.delete(item)
            db.session.commit()
            session.pop('promo_code', None)
            session.pop('checkout_method', None)
            session.pop('checkout_address', None)
            session.pop('checkout_card', None)
            return redirect(url_for('order_confirmation', order_number=order.order_number))
    method = session.get('checkout_method', '')
    return render_template('checkout.html', s=summary, addresses=addresses,
                           cards=cards, method=method)


def current_user_orders(user):
    return Order.query.filter_by(user_id=user.id).order_by(Order.id.desc()).all()


@app.route('/order/confirmation/<order_number>')
@login_required
def order_confirmation(order_number):
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    return render_template('order_confirmation.html', order=order)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

@app.route('/account')
@login_required
def account():
    orders = current_user_orders(current_user)
    return render_template('account.html', orders=orders)


@app.route('/account/order/<order_number>')
@login_required
def account_order(order_number):
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    return render_template('order_detail.html', order=order)


@app.route('/account/profile', methods=['GET', 'POST'])
@login_required
def account_profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name).strip() or current_user.name
        current_user.phone = request.form.get('phone', '').strip()
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('account_profile'))
    return render_template('edit_profile.html')


@app.route('/account/addresses', methods=['GET', 'POST'])
@login_required
def account_addresses():
    if request.method == 'POST':
        action = request.form.get('action', 'add')
        if action == 'add':
            line1 = request.form.get('line1', '').strip()
            city = request.form.get('city', '').strip()
            state = request.form.get('state', '').strip()
            zip_code = request.form.get('zip_code', '').strip()
            if not (line1 and city and state and zip_code):
                flash('Please fill in street, city, state and ZIP.', 'error')
            else:
                db.session.add(Address(user_id=current_user.id,
                                        label=request.form.get('label', 'Home'),
                                        line1=line1, line2=request.form.get('line2', '').strip(),
                                        city=city, state=state, zip_code=zip_code))
                db.session.commit()
                flash('Address added.', 'success')
        elif action == 'delete':
            addr = Address.query.filter_by(id=int(request.form.get('id', 0) or 0),
                                           user_id=current_user.id).first()
            if addr:
                db.session.delete(addr)
                db.session.commit()
                flash('Address removed.', 'success')
        return redirect(url_for('account_addresses'))
    addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.id).all()
    return render_template('addresses.html', addresses=addresses)


@app.route('/account/payment', methods=['GET', 'POST'])
@login_required
def account_payment():
    if request.method == 'POST':
        action = request.form.get('action', 'add')
        if action == 'add':
            brand = request.form.get('brand', '').strip()
            number = re.sub(r'\D', '', request.form.get('number', ''))
            if not brand or len(number) < 13 or len(number) > 19:
                flash('Please choose a card brand and enter a valid card number.', 'error')
            else:
                exp_month = int(request.form.get('exp_month', 1) or 1)
                exp_year = int(request.form.get('exp_year', 2027) or 2027)
                db.session.add(PaymentCard(user_id=current_user.id,
                                           label=request.form.get('label', 'Personal'),
                                           brand=brand, last4=number[-4:],
                                           exp_month=exp_month, exp_year=exp_year))
                db.session.commit()
                flash('Card added.', 'success')
        elif action == 'delete':
            card = PaymentCard.query.filter_by(id=int(request.form.get('id', 0) or 0),
                                               user_id=current_user.id).first()
            if card:
                db.session.delete(card)
                db.session.commit()
                flash('Card removed.', 'success')
        return redirect(url_for('account_payment'))
    cards = PaymentCard.query.filter_by(user_id=current_user.id).order_by(PaymentCard.id).all()
    return render_template('payment.html', cards=cards)


@app.route('/wishlist')
@login_required
def wishlist():
    items = WishlistItem.query.filter_by(user_id=current_user.id).order_by(WishlistItem.id).all()
    return render_template('wishlist.html', items=items)


@app.route('/wishlist/add', methods=['POST'])
def wishlist_add():
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=request.form.get('next', url_for('index'))))
    p = Product.query.filter_by(slug=request.form.get('slug', '')).first_or_404()
    existing = WishlistItem.query.filter_by(user_id=current_user.id, product_id=p.id).first()
    if not existing:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=p.id))
        db.session.commit()
        flash(f'Saved to wishlist: {p.name}', 'success')
    else:
        flash('That item is already on your wishlist.', 'info')
    return redirect(request.form.get('next') or url_for('wishlist'))


@app.route('/wishlist/remove', methods=['POST'])
@login_required
def wishlist_remove():
    item = WishlistItem.query.filter_by(id=int(request.form.get('item_id', 0) or 0),
                                        user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash('Removed from wishlist.', 'success')
    return redirect(url_for('wishlist'))


# ---------------------------------------------------------------------------
# Savings / coupons
# ---------------------------------------------------------------------------

@app.route('/savings')
def savings():
    coupons = Coupon.query.order_by(Coupon.id).all()
    featured = Product.query.filter(Product.promo_type != '').order_by(Product.review_count.desc()).limit(12).all()
    return render_template('savings.html', coupons=coupons, featured=featured)


@app.route('/rewards')
def rewards():
    return render_template('rewards.html')


@app.route('/coupon-policy-and-price-guarantee')
def coupon_policy():
    return render_template('coupon_policy.html')


# ---------------------------------------------------------------------------
# Informational pages (service nav + footer targets; short honest pages so
# the navigation chain has no dead links)
# ---------------------------------------------------------------------------

INFO_PAGES = {
    '/custom-framing': {
        'title': 'Custom Framing', 'heading': 'Custom Framing',
        'paragraphs': [
            'Bring your art, photos, and memorabilia to participating Michaels stores and our certified framers will help you choose the frame styles, mats, and glazing that fit your piece and your budget.',
            'Custom framing and frame &amp; print services are offered at many Michaels locations. Use the Store Locator to find a store near you and see the services it offers.',
        ],
        'links': [('Shop Frames', '/shop/frames'), ('Find a Store', '/store-locator')],
    },
    '/marketplace': {
        'title': 'MakerPlace', 'heading': 'MakerPlace by Michaels',
        'paragraphs': [
            'MakerPlace by Michaels is our marketplace for one-of-a-kind creations from independent makers, alongside the craft supplies you know.',
            'Explore the full Michaels assortment right here in the shop.',
        ],
        'links': [('Shop All Categories', '/shop/art-supplies')],
    },
    '/digital-downloads': {
        'title': 'Digital Downloads', 'heading': 'Digital Downloads',
        'paragraphs': [
            'Download digital designs for craft machines — SVGs, fonts, and project files that let you start creating the moment you check out.',
            'Craft machines and materials are available in the Craft Machines category.',
        ],
        'links': [('Shop Craft Machines', '/shop/craft-machines')],
    },
    '/enterprise': {
        'title': 'Enterprise', 'heading': 'Michaels Enterprise',
        'paragraphs': [
            'Michaels Enterprise brings creativity to teams, events, and organizations — from bulk craft supplies to team-building classes.',
            'Ask about group experiences through the classes and events program.',
        ],
        'links': [('Classes & Events', '/classes')],
    },
    '/education': {
        'title': 'Education', 'heading': 'Michaels Education',
        'paragraphs': [
            'Michaels Education offers classes, events, and live learning for every age and skill level — from Kids Club sessions to advanced maker workshops.',
            'Browse the current class schedule to find a session that fits you.',
        ],
        'links': [('Classes & Events', '/classes')],
    },
    '/customer-care': {
        'title': 'Customer Care', 'heading': 'Customer Care',
        'paragraphs': [
            'How can we help? For order help, price adjustments, and general questions, contact Michaels.com Customer Service at 1-800-642-4235.',
            'The Coupon Policy and Price Guarantee page explains how promotions, coupon limits, and price matching work.',
        ],
        'links': [('Coupon Policy &amp; Price Guarantee', '/coupon-policy-and-price-guarantee'),
                   ('Track My Order', '/account'), ('Find a Store', '/store-locator')],
    },
    '/return-policy': {
        'title': 'Return Policy', 'heading': 'Return Policy',
        'paragraphs': [
            'Returns are accepted within 60 days with receipt; custom-cut material and seasonal items may be excluded.',
            'Need help with a return? Contact Michaels.com Customer Service at 1-800-642-4235.',
        ],
        'links': [('Customer Care', '/customer-care')],
    },
    '/shipping-policy': {
        'title': 'Shipping Policy', 'heading': 'Shipping Policy',
        'paragraphs': [
            'Free shipping on orders $49+. Most orders ship within 2 business days.',
            'Store Pickup is available on eligible items at most Michaels stores — choose Pickup at checkout and your order will be waiting at the store.',
        ],
        'links': [('Find a Store', '/store-locator'), ('Shop', '/shop/art-supplies')],
    },
    '/privacy-policy': {
        'title': 'Privacy Policy', 'heading': 'Privacy Policy',
        'paragraphs': [
            'Michaels is committed to protecting your privacy. This notice applies to information collected when you shop on Michaels.com.',
            'For questions about your privacy, contact Michaels.com Customer Service at 1-800-642-4235.',
        ],
        'links': [('Terms &amp; Conditions', '/terms-and-conditions'), ('Customer Care', '/customer-care')],
    },
    '/product-policy': {
        'title': 'Product Policy', 'heading': 'Product Policy',
        'paragraphs': [
            'Product information, pricing, and availability on Michaels.com are subject to change.',
            'Sale and clearance exclusions apply to select brands and categories — see the Coupon Policy for the full exclusions list.',
        ],
        'links': [('Coupon Policy &amp; Price Guarantee', '/coupon-policy-and-price-guarantee')],
    },
    '/terms-and-conditions': {
        'title': 'Terms & Conditions', 'heading': 'Terms &amp; Conditions',
        'paragraphs': [
            'By using Michaels.com you agree to our terms of service, including the Coupon Policy and Price Guarantee rules that govern promotions and pricing.',
            'Coupons are limited to stock on hand and void where prohibited.',
        ],
        'links': [('Coupon Policy &amp; Price Guarantee', '/coupon-policy-and-price-guarantee'),
                   ('Privacy Policy', '/privacy-policy')],
    },
    '/michaels-gives-back': {
        'title': 'Michaels Gives Back', 'heading': 'Michaels Gives Back',
        'paragraphs': [
            'Michaels Gives Back supports teachers, schools, and local communities through craft supply donations and community programs.',
            'Visit your local store to learn about programs in your community.',
        ],
        'links': [('Find a Store', '/store-locator')],
    },
    '/sustainability': {
        'title': 'Sustainability', 'heading': 'Sustainability at Michaels',
        'paragraphs': [
            'We are working to reduce waste, recycle materials, and offer eco-friendly craft supplies so makers can create responsibly.',
        ],
        'links': [('Shop', '/shop/art-supplies')],
    },
    '/supplier-portal': {
        'title': 'Supplier Portal', 'heading': 'Supplier Portal',
        'paragraphs': [
            'Current and prospective suppliers can find resources for doing business with Michaels, from onboarding to product programs.',
        ],
        'links': [('Product Policy', '/product-policy')],
    },
    '/download-app': {
        'title': 'Download App', 'heading': 'Get the Michaels App',
        'paragraphs': [
            'Get the Michaels app to browse savings, clip coupons, and check your local store info on the go.',
            'The same savings are available right here on the web — see the Savings page for current coupons.',
        ],
        'links': [('Savings', '/savings'), ('Michaels Rewards', '/rewards')],
    },
}


@app.route('/custom-framing')
@app.route('/marketplace')
@app.route('/digital-downloads')
@app.route('/enterprise')
@app.route('/education')
@app.route('/customer-care')
@app.route('/return-policy')
@app.route('/shipping-policy')
@app.route('/privacy-policy')
@app.route('/product-policy')
@app.route('/terms-and-conditions')
@app.route('/michaels-gives-back')
@app.route('/sustainability')
@app.route('/supplier-portal')
@app.route('/download-app')
def info_page():
    page = INFO_PAGES.get(request.path)
    if page is None:
        abort(404)
    return render_template('info_page.html', page=page)


# ---------------------------------------------------------------------------
# Store locator
# ---------------------------------------------------------------------------

@app.route('/store-locator')
def store_locator():
    q = (request.args.get('q') or '').strip()
    stores = []
    if q:
        ql = q.lower()
        for s in Store.query.order_by(Store.id).all():
            hay = f"{s.name} {s.address} {s.city} {s.state} {s.zip}".lower()
            if ql in hay:
                stores.append(s)
    return render_template('store_locator.html', stores=stores, q=q)


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

@app.route('/classes')
def classes():
    category = request.args.get('category', '')
    live = _active_classes()
    if category:
        live = [c for c in live if c.category == category]
        tutorials = ClassEvent.query.filter_by(kind='tutorial', category=category).order_by(ClassEvent.id).all()
    else:
        tutorials = ClassEvent.query.filter_by(kind='tutorial').order_by(ClassEvent.id).all()
    categories = [c.category for c in ClassEvent.query.filter_by(kind='tutorial').order_by(ClassEvent.id).all()]
    seen = set(); uniq_cats = [c for c in categories if not (c in seen or seen.add(c))]
    return render_template('classes.html', live=live, tutorials=tutorials,
                           categories=uniq_cats, category=category)


@app.route('/classes/register', methods=['POST'])
def class_register():
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=request.form.get('next', url_for('classes'))))
    cid = int(request.form.get('class_id', 0) or 0)
    evt = ClassEvent.query.filter_by(kind='live', id=cid).first_or_404()
    existing = ClassRegistration.query.filter_by(user_id=current_user.id, class_event_id=cid).first()
    if existing:
        flash('You are already registered for that class.', 'info')
    else:
        db.session.add(ClassRegistration(user_id=current_user.id, class_event_id=cid,
                                         registered_at=MIRROR_REFERENCE_DATE.isoformat(),
                                         attendee_name=request.form.get('attendee_name', current_user.name)))
        db.session.commit()
        flash(f'Registered for "{evt.title}" on {evt.date} at {evt.time_text} ({evt.platform}).', 'success')
    return redirect(url_for('classes'))


@app.route('/account/registrations')
@login_required
def account_registrations():
    regs = ClassRegistration.query.filter_by(user_id=current_user.id).order_by(ClassRegistration.id).all()
    return render_template('registrations.html', regs=regs)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.route('/_health')
def health():
    from _health import health
    return health()


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def seed_database():
    if Product.query.count() > 0:
        return
    from seed_data import run_seed
    run_seed(db, Category, Product, ProductVariant, Review, Question,
             Store, Coupon, ClassEvent)


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    from seed_data import run_seed_users
    run_seed_users(db, User, Address, PaymentCard, CartItem, WishlistItem,
                   Order, OrderItem, Product)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
