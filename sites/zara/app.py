#!/usr/bin/env python3
"""zara — a WebHarbor mirror of https://www.zara.com/us/

Flask + SQLite mirror of ZARA United States: the home campaign slider, the
WOMAN / MAN / KIDS / BEAUTY catalog categories with their upstream filter
panels, product detail pages with the real upstream colors, sizes,
availability, prices and image galleries, the site search (upstream search
API snapshots for the nine captured terms, computed over the catalog
otherwise), the US store locator (25 real stores with addresses, phones and
opening hours across 20 states) and the authenticated shopping flows: bag
with guest carts, checkout with address + payment forms, orders, wishlist
and account addresses. Four benchmark accounts (Alice, Bob, Carol, Dana)
come seeded with bags, wishlists, orders and addresses built on real
captured products.

Content comes from the tracked source_data/*.json snapshots captured from
zara.com/us on 2026-09-29 (see provenance.json); the SQLite
seed is materialized deterministically at image build time
(PYTHONHASHSEED=0).
"""
import json
import os
import re
import uuid
from datetime import date

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from urllib.parse import urlsplit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("ZARA_SECRET_KEY") or "webharbor-zara-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'ZARA_DB_URI', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'zara.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'logon'
login_manager.login_message = 'Please log in to continue.'
csrf = CSRFProtect(app)

# The mirror is a frozen snapshot of the upstream site taken 2026-09-29.
MIRROR_DATE = date(2026, 9, 29)
MIRROR_TS = "2026-09-29 12:00"
SITE_NAME = "zara"
STORE_ID = 11719
# bcrypt hash of 'TestPass123!' — frozen so the seed DB is byte-reproducible.
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')
SOURCE = os.path.join(BASE_DIR, 'source_data')

USD = "${:,.2f}"


def money(cents):
    if cents is None:
        return None
    return "USD " + USD.format(cents / 100.0)[1:]


def _load(name):
    with open(os.path.join(SOURCE, name), encoding='utf-8') as f:
        return json.load(f)


# --------------------------------------------------------- asset resolution --

_INVENTORY = None


def _inventory():
    global _INVENTORY
    if _INVENTORY is None:
        _INVENTORY = {}
        path = os.path.join(BASE_DIR, 'asset_inventory.json')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                for row in json.load(f).get('assets', []):
                    fname = os.path.basename(row['path'])
                    _INVENTORY[fname.rsplit('.', 1)[0]] = row['path']
    return _INVENTORY


def img(name):
    """URL for a managed upstream asset by logical name (None if absent)."""
    inv = _inventory()
    rel = inv.get(name) or inv.get(name.rsplit('.', 1)[0])
    if not rel:
        return None
    return '/' + rel


# ------------------------------------------------------------------- models --

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_benchmark = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.String(10), nullable=False, default='2026-09-01')


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)          # upstream product id
    seo_id = db.Column(db.String(40), unique=True, nullable=False)  # e.g. 08100038
    reference = db.Column(db.String(60), nullable=False)
    display_reference = db.Column(db.String(60))
    name = db.Column(db.String(200), nullable=False)
    kind = db.Column(db.String(40))
    section = db.Column(db.String(20))
    family = db.Column(db.String(80))
    subfamily = db.Column(db.String(80))
    seo_keyword = db.Column(db.String(160))
    first_visible_date = db.Column(db.String(30))
    is_on_sale = db.Column(db.Boolean, default=False)
    old_price = db.Column(db.Integer)
    price = db.Column(db.Integer, nullable=False)         # cents

    colors = db.relationship('Color', backref='product', order_by='Color.id',
                             cascade='all, delete-orphan')

    def color(self, color_id):
        for c in self.colors:
            if str(c.upstream_id) == str(color_id):
                return c
        return None

    @property
    def main_color(self):
        return self.colors[0] if self.colors else None

    @property
    def pdp_path(self):
        return f"/us/en/{self.seo_keyword}-p{self.seo_id}.html"


class Color(db.Model):
    __tablename__ = 'colors'
    id = db.Column(db.Integer, primary_key=True)
    upstream_id = db.Column(db.String(40))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    hex = db.Column(db.String(20))
    reference = db.Column(db.String(80))
    price = db.Column(db.Integer)
    description = db.Column(db.Text)
    tags = db.Column(db.Text)          # JSON list
    gallery = db.Column(db.Text)       # JSON list of logical image names
    thumb = db.Column(db.String(120))

    sizes = db.relationship('Size', backref='color', order_by='Size.id',
                            cascade='all, delete-orphan')

    @property
    def gallery_list(self):
        return json.loads(self.gallery or '[]')

    @property
    def tags_list(self):
        return json.loads(self.tags or '[]')


class Size(db.Model):
    __tablename__ = 'sizes'
    id = db.Column(db.Integer, primary_key=True)
    color_id = db.Column(db.Integer, db.ForeignKey('colors.id'), nullable=False)
    upstream_id = db.Column(db.Integer)
    name = db.Column(db.String(40), nullable=False)
    availability = db.Column(db.String(30), nullable=False)   # in_stock / back_soon / coming_soon / edit_me
    price = db.Column(db.Integer)
    sku = db.Column(db.Integer)
    equivalent_size_id = db.Column(db.Integer)
    reference = db.Column(db.String(80))


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    upstream_id = db.Column(db.Integer, unique=True, nullable=False)
    seo_id = db.Column(db.Integer, unique=True, nullable=False)
    section = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), nullable=False)
    upstream_grid_count = db.Column(db.Integer)
    filters = db.Column(db.Text)       # JSON {colors,sizes,sort_options}

    products = db.relationship('CategoryProduct', backref='category',
                               order_by='CategoryProduct.position')

    @property
    def path(self):
        return f"/us/en/{self.section.lower()}-{self.slug}-l{self.seo_id}.html"


class CategoryProduct(db.Model):
    __tablename__ = 'category_products'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    product = db.relationship('Product')


class Store(db.Model):
    __tablename__ = 'stores'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    commercial_name = db.Column(db.String(200))
    address = db.Column(db.String(300), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    province = db.Column(db.String(120), nullable=False)
    zip = db.Column(db.String(20))
    phone = db.Column(db.String(40))
    type = db.Column(db.String(40))
    status = db.Column(db.String(40))
    timezone = db.Column(db.String(60))
    hours = db.Column(db.Text)          # JSON {weekday: {open, hours:[o,c]}}
    upcoming = db.Column(db.Text)       # JSON [{date, week_day, open, intervals}]
    url = db.Column(db.String(300))

    @property
    def slug(self):
        return re.sub(r"[^a-z0-9]+", "-",
                      (self.name or 'store').lower()).strip('-')

    @property
    def path(self):
        return f"/us/en/stores-locator/zara-{self.city.lower().replace(' ', '-')}-{self.province.lower().replace(' ', '-')}-{self.slug}-s{self.id}"

    def hours_for(self, weekday):
        h = json.loads(self.hours or '{}')
        return h.get(str(weekday)) or {'open': False, 'hours': []}

    @property
    def upcoming_list(self):
        return json.loads(self.upcoming or '[]')

    def hours_today(self):
        # zara week days: 1=Monday..7=Sunday. The mirror is frozen at
        # 2026-09-29, a Tuesday.
        return self.hours_for(MIRROR_DATE.isoweekday())


class SearchSnapshot(db.Model):
    __tablename__ = 'search_snapshots'
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(120), unique=True, nullable=False)
    total_results = db.Column(db.Integer)
    facets = db.Column(db.Text)        # JSON
    price_range = db.Column(db.Text)    # JSON
    sortings = db.Column(db.Text)      # JSON
    results = db.Column(db.Text)       # JSON [seo ids in upstream order]


class Campaign(db.Model):
    __tablename__ = 'campaigns'
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(40), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(160))


class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    guest_token = db.Column(db.String(64), index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    color_id = db.Column(db.Integer, db.ForeignKey('colors.id'), nullable=False)
    size_id = db.Column(db.Integer, db.ForeignKey('sizes.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    added_at = db.Column(db.String(20), nullable=False, default='2026-09-29')
    product = db.relationship('Product')
    color = db.relationship('Color')
    size = db.relationship('Size')

    @property
    def unit_price(self):
        return self.size.price or self.color.price or self.product.price


class WishlistItem(db.Model):
    __tablename__ = 'wishlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    color_id = db.Column(db.Integer, db.ForeignKey('colors.id'))
    added_at = db.Column(db.String(20), nullable=False, default='2026-09-29')
    product = db.relationship('Product')
    color = db.relationship('Color')


class Address(db.Model):
    __tablename__ = 'addresses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    label = db.Column(db.String(60), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    line1 = db.Column(db.String(200), nullable=False)
    line2 = db.Column(db.String(200))
    city = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(60), nullable=False)
    zip = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    is_default = db.Column(db.Boolean, default=False)


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    number = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(40), nullable=False)
    placed_at = db.Column(db.String(20), nullable=False)
    shipping_cents = db.Column(db.Integer, nullable=False, default=0)
    subtotal_cents = db.Column(db.Integer, nullable=False)
    total_cents = db.Column(db.Integer, nullable=False)
    payment_last4 = db.Column(db.String(8))
    address_snapshot = db.Column(db.Text)     # JSON
    items = db.relationship('OrderItem', backref='order',
                            cascade='all, delete-orphan')

    @property
    def status_label(self):
        return {'placed': 'Order placed',
                'in_progress': 'In progress',
                'shipped': 'Shipped',
                'delivered': 'Delivered',
                'returned': 'Returned'}.get(self.status, self.status.title())

    @property
    def address_dict(self):
        return json.loads(self.address_snapshot or '{}')


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    color_name = db.Column(db.String(80), nullable=False)
    size_name = db.Column(db.String(40), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product = db.relationship('Product')


class NewsletterSignup(db.Model):
    __tablename__ = 'newsletter_signups'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), nullable=False)
    section = db.Column(db.String(40))
    created_at = db.Column(db.String(20), nullable=False, default='2026-09-29')


# ------------------------------------------------------------------ seeding --

def _imgname(pid, kind, idx):
    return f"p{pid}-{kind}{idx}.jpg"


def seed_catalog():
    if Product.query.count() > 0:
        return
    products = _load('products.json')['products']
    for p in products:
        price = p['colors'][0]['price'] if p.get('colors') else p.get('price')
        old_price = None
        row = Product(id=p['id'], seo_id=p['seo_product_id'],
                      reference=p['reference'],
                      display_reference=p.get('display_reference'),
                      name=p['name'], kind=p.get('kind'),
                      section=p.get('section_name'),
                      family=p.get('family'), subfamily=p.get('subfamily'),
                      seo_keyword=p.get('seo_keyword'),
                      first_visible_date=p.get('first_visible_date'),
                      price=price or 0, old_price=old_price,
                      is_on_sale=bool(old_price))
        db.session.add(row)
        for color_index, c in enumerate(p.get('colors') or []):
            col = Color(upstream_id=str(c['id']), product_id=row.id,
                        name=c['name'], hex=c.get('hex'),
                        reference=c.get('reference'), price=c.get('price'),
                        description=c.get('description'),
                        tags=json.dumps(c.get('tags') or []),
                        gallery=json.dumps([(_imgname(p['seo_product_id'], 'gal', i) if color_index == 0 else f"p{p['seo_product_id']}-c{c['id']}-gal{i}.jpg")
                                            for i in range(len(c.get('gallery') or []))]),
                        thumb=(f"p{p['seo_product_id']}-c{c['id']}-thumb.jpg"
                               if len(p.get('colors') or []) > 1 else None))
            db.session.add(col)
            db.session.flush()
            for s in c.get('sizes') or []:
                db.session.add(Size(color_id=col.id,
                                    upstream_id=s.get('id'), name=s['name'],
                                    availability=s.get('availability') or 'in_stock',
                                    price=s.get('price'), sku=s.get('sku'),
                                    equivalent_size_id=s.get('equivalent_size_id'),
                                    reference=s.get('reference')))
    db.session.flush()


def seed_categories():
    if Category.query.count() > 0:
        return
    filters = _load('category_filters.json')['filters']
    for c in _load('category_products.json')['categories']:
        row = Category(upstream_id=c['id'], seo_id=c['seo_id'],
                      section=c['section'], name=c['name'], slug=c['slug'],
                      upstream_grid_count=c['upstream_grid_count'],
                      filters=json.dumps(filters.get(str(c['seo_id']))))
        db.session.add(row)
        db.session.flush()
        for pos, pid in enumerate(c['products']):
            prod = Product.query.filter_by(seo_id=pid).first()
            if prod:
                db.session.add(CategoryProduct(category_id=row.id,
                                               product_id=prod.id,
                                               position=pos))


def seed_stores():
    if Store.query.count() > 0:
        return
    d = _load('stores.json')
    for s in d['stores']:
        db.session.add(Store(id=int(s['id']), name=s['name'],
                            commercial_name=s.get('commercial_name'),
                            address=s['address'], city=s['city'],
                            province=s['province'], zip=s.get('zip'),
                            phone=s.get('phone'), type=s.get('type'),
                            status=s.get('status'), timezone=s.get('timezone'),
                            hours=json.dumps(s['hours']),
                            upcoming=json.dumps(s['upcoming']),
                            url=s.get('url')))


def seed_searches():
    if SearchSnapshot.query.count() > 0:
        return
    d = _load('searches.json')
    for s in d['searches']:
        db.session.add(SearchSnapshot(term=s['term'],
                                      total_results=s['total_results'],
                                      facets=json.dumps(s['facets']),
                                      price_range=json.dumps(s.get('price_range')),
                                      sortings=json.dumps(s.get('sortings')),
                                      results=json.dumps(s['results'])))


def seed_campaigns():
    if Campaign.query.count() > 0:
        return
    d = _load('home.json')
    for block in d.get('campaigns', []):
        for i, s in enumerate(block.get('slides', [])):
            nm = re.sub(r"[^a-z0-9]+", "-",
                        (block.get('title') or 'camp').lower()).strip('-')
            db.session.add(Campaign(section=block['title'], position=i,
                                    image=f"home-{nm}-{i}.jpg"))


def seed_users():
    if User.query.count() > 0:
        return
    fx = _load('benchmark_users.json')

    def pid_of(seo):
        p = Product.query.filter_by(seo_id=seo).first()
        assert p, f"product {seo} missing"
        return p

    def cis(product, color_name, size_name):
        col = next((c for c in product.colors if c.name.lower() == color_name.lower()),
                   product.colors[0])
        size = next((s for s in col.sizes if s.name == size_name), col.sizes[0])
        return col, size

    users = {}
    for u in fx['users']:
        row = User(email=u['email'], display_name=u['display_name'],
                   password_hash=BENCHMARK_PASSWORD_HASH,
                   is_benchmark=True, created_at=u.get('created_at', '2026-08-15'))
        db.session.add(row)
        db.session.flush()
        users[u['email']] = row
        for a in u.get('addresses', []):
            db.session.add(Address(user_id=row.id, **a))
        for ci in u.get('cart', []):
            prod = pid_of(ci['product'])
            col, size = cis(prod, ci['color'], ci['size'])
            db.session.add(CartItem(user_id=row.id, product_id=prod.id,
                                   color_id=col.id, size_id=size.id,
                                   quantity=ci['quantity'],
                                   added_at=ci.get('added_at', '2026-09-28')))
        for wi in u.get('wishlist', []):
            prod = pid_of(wi['product'])
            col = prod.color(wi.get('color')) or prod.main_color
            db.session.add(WishlistItem(user_id=row.id, product_id=prod.id,
                                        color_id=col.id,
                                        added_at=wi.get('added_at', '2026-09-26')))
    db.session.flush()

    for o in fx.get('orders', []):
        user = users[o['user']]
        subtotal = 0
        order = Order(user_id=user.id, number=o['number'],
                      status=o['status'], placed_at=o['placed_at'],
                      shipping_cents=o.get('shipping_cents', 0),
                      subtotal_cents=0, total_cents=0,
                      payment_last4=o.get('payment_last4'),
                      address_snapshot=json.dumps(o.get('address')))
        db.session.add(order)
        db.session.flush()
        for it in o['items']:
            prod = pid_of(it['product'])
            subtotal += it['unit_price'] * it['quantity']
            db.session.add(OrderItem(order_id=order.id, product_id=prod.id,
                                     color_name=it['color'], size_name=it['size'],
                                     product_name=prod.name,
                                     unit_price=it['unit_price'],
                                     quantity=it['quantity']))
        order.subtotal_cents = subtotal
        order.total_cents = subtotal + order.shipping_cents


def main():
    with app.app_context():
        db.create_all()
        if all(model.query.first() is not None for model in (Product, Category, Store, SearchSnapshot, Campaign, User)):
            return
        seed_catalog()
        seed_categories()
        seed_stores()
        seed_searches()
        seed_campaigns()
        seed_users()
        db.session.commit()


# ------------------------------------------------------------------- login --

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    return dict(money=money, MIRROR_TS=MIRROR_TS,
                cart_count=len(bag_items()), img=img,
                categories_nav=categories_nav)


def categories_nav():
    """Section name -> [(category, count)] for the header nav."""
    cats = Category.query.order_by(Category.section, Category.seo_id).all()
    out = {}
    for c in cats:
        out.setdefault(c.section, []).append((c, len(c.products)))
    return sorted(out.items())


# ------------------------------------------------------------------ helpers --

def local_target(value, fallback):
    target = urlsplit(value or '')
    return value if target.path.startswith('/') and not target.netloc and not target.scheme and not value.startswith('//') and '\\' not in value else fallback


def positive_form_int(name, default=None, maximum=None):
    value = request.form.get(name, default)
    try:
        value = int(value)
    except (TypeError, ValueError):
        abort(400, description=f'Enter a valid {name}.')
    if value < 1 or (maximum is not None and value > maximum):
        abort(400, description=f'Enter a valid {name}.')
    return value


def adopt_guest_bag(user):
    token = session.pop('zara_guest', None)
    if not token:
        return
    for item in CartItem.query.filter_by(user_id=None, guest_token=token).all():
        existing = CartItem.query.filter_by(user_id=user.id, product_id=item.product_id,
                                            color_id=item.color_id, size_id=item.size_id).first()
        if existing:
            existing.quantity += item.quantity
            db.session.delete(item)
        else:
            item.user_id, item.guest_token = user.id, None
    db.session.commit()


def bag_items():
    """The caller's bag rows (logged-in user or guest cookie)."""
    if current_user.is_authenticated:
        return (CartItem.query.filter_by(user_id=current_user.id)
                .order_by(CartItem.id).all())
    token = session.get('zara_guest')
    if not token:
        return []
    return (CartItem.query.filter_by(guest_token=token)
            .order_by(CartItem.id).all())


def bag_subtotal(items):
    return sum(i.unit_price * i.quantity for i in items)


def bag_shipping(items):
    return 0 if not items else 495  # zara standard shipping $4.95 under $50... keep flat


def store_for_path(store_id):
    return db.session.get(Store, int(store_id))


WEEKDAYS = {1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday',
            5: 'Friday', 6: 'Saturday', 7: 'Sunday'}


def _fmt_hours(h):
    if not h or not h.get('open'):
        return 'Closed'
    pairs = h.get('hours') or []
    if len(pairs) >= 2:
        return f"{pairs[0]} - {pairs[1]}"
    return 'Open'


# -------------------------------------------------------------------- routes --

@app.route('/')
def home():
    campaigns = (Campaign.query.order_by(Campaign.section, Campaign.position).all())
    by_section = {}
    for c in campaigns:
        by_section.setdefault(c.section, []).append(c)
    cats = Category.query.order_by(Category.section, Category.seo_id).all()
    return render_template('home.html', campaigns=by_section, categories=cats)


CAT_RE = re.compile(r"^(?P<slug>.+)-l(?P<seo>\d+)\.html$")


@app.route('/us/en/<path:page>')
def upstream_page(page):
    m = CAT_RE.match(page)
    if m:
        cat = Category.query.filter_by(seo_id=int(m.group('seo'))).first()
        if not cat:
            abort(404)
        return render_category(cat)
    m = re.match(r"^(?P<kw>.+)-p(?P<seo>[0-9]+)\.html$", page)
    if m:
        prod = Product.query.filter_by(seo_id=m.group('seo')).first()
        if not prod:
            abort(404)
        return render_product(prod)
    m = re.match(r"^stores-locator/(.+)-s(?P<sid>\d+)$", page)
    if m:
        store = store_for_path(m.group('sid'))
        if not store:
            abort(404)
        return render_template('store_detail.html', store=store,
                                weekdays=WEEKDAYS, fmt_hours=_fmt_hours)
    abort(404)


def render_category(cat):
    f = json.loads(cat.filters or '{}') or {}
    selected_color = request.args.get('color', '').strip()
    selected_size = request.args.get('size', '').strip()
    sort = request.args.get('sort', '').strip()
    price_min = request.args.get('price-min', type=int)
    price_max = request.args.get('price-max', type=int)

    rows = (CategoryProduct.query.filter_by(category_id=cat.id)
            .order_by(CategoryProduct.position).all())
    prods = [r.product for r in rows]

    # Only render filter options that match at least one catalog product:
    # upstream facet counts are preserved, but every clickable filter works.
    cat_colors = {c.name.lower() for p in prods for c in p.colors}
    cat_sizes = {s.name for p in prods for c in p.colors for s in c.sizes}
    if f.get('colors'):
        f['colors'] = [c for c in f['colors']
                       if c['value'].lower() in cat_colors]
    if f.get('sizes'):
        f['sizes'] = [s for s in f['sizes'] if s['value'] in cat_sizes]

    def keep(p):
        variants = [c for c in p.colors if not selected_color or c.name.lower() == selected_color.lower()]
        if not variants:
            return False
        if selected_size and not any(s.name == selected_size and s.availability in ('in_stock', 'low_on_stock')
                                     for c in variants for s in c.sizes):
            return False
        if price_min is not None and p.price < price_min:
            return False
        if price_max is not None and p.price > price_max:
            return False
        return True

    shown = [p for p in prods if keep(p)]
    if sort == 'price-asc':
        shown.sort(key=lambda p: p.price)
    elif sort == 'price-desc':
        shown.sort(key=lambda p: -p.price)

    return render_template(
        'category.html', cat=cat, products=shown, total=len(prods),
        filters=f, selected_color=selected_color, selected_size=selected_size,
        sort=sort, price_min=price_min, price_max=price_max)


def render_product(prod):
    color_id = request.args.get('v1', '')
    color = prod.color(color_id) if color_id else None
    if color is None:
        color = prod.main_color
    others = [c for c in prod.colors if c.id != color.id]
    in_bag = False
    wish = False
    if current_user.is_authenticated:
        wish = WishlistItem.query.filter_by(user_id=current_user.id,
                                            product_id=prod.id).count() > 0
    cat = (Category.query.join(CategoryProduct)
           .filter(CategoryProduct.product_id == prod.id).first())
    return render_template('product.html', product=prod, color=color,
                           others=others, in_bag=in_bag, wish=wish,
                           weekdays=WEEKDAYS, cat=cat)


@app.route('/us/en/search')
def search():
    term = (request.args.get('searchTerm') or '').strip()
    snap = SearchSnapshot.query.filter(
        SearchSnapshot.term == term.lower()).first() if term else None
    results = []
    facets = price_range = sortings = None
    total = 0
    snapshot_mode = False
    if term:
        # The visible grid is computed over the captured catalog; for the
        # nine captured terms the upstream total + facet counts (from the
        # real search API snapshots) are displayed as context.
        like = f"%{term.lower()}%"
        matched = (Product.query.filter(db.or_(
            db.func.lower(Product.name).like(like),
            db.func.lower(Product.family).like(like),
            db.func.lower(Product.subfamily).like(like),
            db.func.lower(Product.section).like(like))).all())
        if snap:
            snapshot_mode = True
            total = snap.total_results
            facets = json.loads(snap.facets or '[]')
            price_range = json.loads(snap.price_range or 'null')
            sortings = json.loads(snap.sortings or '[]')
            # upstream result order first for products that appear in it
            pos = {seo: i for i, seo in enumerate(json.loads(snap.results or '[]'))}
            results = sorted(matched, key=lambda p: pos.get(p.seo_id, 10_000))
        else:
            total = len(matched)
            results = matched
    return render_template('search.html', term=term, results=results,
                           total=total, facets=facets,
                           price_range=price_range, sortings=sortings,
                           snapshot_mode=snapshot_mode,
                           categories=Category.query.order_by(Category.seo_id).all())


@app.route('/us/en/z-stores-st1404.html')
def stores():
    q = (request.args.get('q') or '').strip()
    state = (request.args.get('state') or '').strip()
    all_stores = Store.query.order_by(Store.province, Store.city, Store.name).all()
    shown = all_stores
    if q:
        ql = q.lower()
        shown = [s for s in shown if ql in s.name.lower()
                 or ql in s.city.lower() or ql in s.province.lower()
                 or ql in (s.zip or '').lower() or ql in s.address.lower()]
    if state:
        shown = [s for s in shown if s.province == state]
    states = sorted({s.province for s in all_stores})
    return render_template('stores.html', stores=shown, all_count=len(all_stores),
                           q=q, state=state, states=states,
                           fmt_hours=_fmt_hours)


# ----------------------------------------------------------------- auth ----

@app.route('/us/en/logon', methods=['GET', 'POST'])
def logon():
    mode = request.args.get('mode', 'login')
    if request.method == 'POST':
        mode = request.form.get('mode', 'login')
        if mode == 'register':
            email = request.form.get('email', '').strip().lower()
            name = request.form.get('name', '').strip()
            password = request.form.get('password', '')
            if not email or '@' not in email:
                return render_template('logon.html', mode='register',
                                       error='Enter a valid email address.'), 400
            if not name:
                return render_template('logon.html', mode='register',
                                       error='Enter your name.'), 400
            if len(password) < 8:
                return render_template('logon.html', mode='register',
                                       error='Password must be at least 8 characters.'), 400
            if User.query.filter_by(email=email).first():
                return render_template('logon.html', mode='register',
                                       error='An account with this email already exists.'), 400
            user = User(email=email, display_name=name,
                        password_hash=bcrypt.generate_password_hash(password).decode(),
                        created_at='2026-09-29')
            db.session.add(user)
            db.session.commit()
            login_user(user)
            adopt_guest_bag(user)
            return redirect(url_for('home'))
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user or not bcrypt.check_password_hash(user.password_hash, password):
            return render_template('logon.html', mode='login',
                                   error='Incorrect email or password.'), 401
        login_user(user)
        adopt_guest_bag(user)
        target = local_target(request.args.get('next'), url_for('home'))
        return redirect(target)
    return render_template('logon.html', mode=mode, error=None)


@app.route('/us/en/logon/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


# ------------------------------------------------------------------- bag ----

@app.route('/us/en/shop')
def shop():
    items = bag_items()
    return render_template('shop.html', items=items,
                           subtotal=bag_subtotal(items),
                           shipping=bag_shipping(items))


@app.route('/us/en/shop/add', methods=['POST'])
def shop_add():
    product = Product.query.filter_by(seo_id=request.form.get('product', '')).first()
    color = db.session.get(Color, positive_form_int('color'))
    size = db.session.get(Size, positive_form_int('size'))
    if not (product and color and size) or color.product_id != product.id \
            or size.color_id != color.id:
        abort(404)
    if size.availability not in ('in_stock', 'low_on_stock'):
        abort(400, description='This size is not available.')
    quantity = positive_form_int('quantity', 1, 99)
    if current_user.is_authenticated:
        row = CartItem.query.filter_by(user_id=current_user.id,
                                       product_id=product.id,
                                       color_id=color.id, size_id=size.id).first()
    else:
        token = session.get('zara_guest') or uuid.uuid4().hex
        session['zara_guest'] = token
        row = CartItem.query.filter_by(guest_token=token,
                                       product_id=product.id,
                                       color_id=color.id, size_id=size.id).first()
    if row:
        row.quantity += quantity
    else:
        row = CartItem(user_id=current_user.id if current_user.is_authenticated else None,
                       guest_token=None if current_user.is_authenticated else session['zara_guest'],
                       product_id=product.id, color_id=color.id, size_id=size.id,
                       quantity=quantity)
        db.session.add(row)
    db.session.commit()
    return redirect(url_for('shop'))


@app.route('/us/en/shop/update', methods=['POST'])
def shop_update():
    item_id = positive_form_int('item')
    item = db.session.get(CartItem, item_id)
    if not item:
        abort(404)
    if current_user.is_authenticated and item.user_id != current_user.id:
        abort(403)
    if not current_user.is_authenticated and (not session.get('zara_guest') or
            item.user_id is not None or item.guest_token != session.get('zara_guest')):
        abort(403)
    action = request.form.get('action', '')
    if action == 'remove':
        db.session.delete(item)
    else:
        item.quantity = positive_form_int('quantity', 1, 99)
    db.session.commit()
    return redirect(url_for('shop'))


@app.route('/us/en/shop/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    items = bag_items()
    if not items:
        return redirect(url_for('shop'))
    addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.id).all()
    error = None
    if request.method == 'POST':
        address_id = request.form.get('address_id', type=int)
        use_new = request.form.get('address_id') == 'new' or request.form.get('new_address') == '1'
        line1 = request.form.get('line1', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        zipc = request.form.get('zip', '').strip()
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        card = re.sub(r"\D", "", request.form.get('card', ''))
        expiry = request.form.get('expiry', '').strip()
        if use_new:
            if not (line1 and city and state and full_name and phone and re.fullmatch(r'\d{5}(?:-\d{4})?', zipc)):
                error = 'Fill in every address field.'
            addr = Address(user_id=current_user.id, label='NEW',
                           full_name=full_name, line1=line1, city=city,
                           state=state, zip=zipc, phone=phone)
        else:
            addr = next((a for a in addresses if a.id == address_id), None)
            if not addr:
                error = 'Choose a delivery address.'
        if not error and (len(card) != 16 or not card.isdigit()):
            error = 'Enter a valid 16-digit card number.'
        if not error and not re.match(r"^(0[1-9]|1[0-2])\/?([0-9]{2})$", expiry.replace('-', '/')):
            error = 'Enter the card expiry as MM/YY.'
        if not error:
            subtotal = bag_subtotal(items)
            number = f"80{current_user.id:02d}{len(Order.query.all()) + 1:07d}"
            order = Order(user_id=current_user.id, number=number,
                          status='placed', placed_at='2026-09-29',
                          shipping_cents=bag_shipping(items),
                          subtotal_cents=subtotal,
                          total_cents=subtotal + bag_shipping(items),
                          payment_last4=card[-4:],
                          address_snapshot=json.dumps({
                              'full_name': addr.full_name, 'line1': addr.line1,
                              'city': addr.city, 'state': addr.state,
                              'zip': addr.zip, 'phone': addr.phone}))
            db.session.add(order)
            db.session.flush()
            for it in items:
                db.session.add(OrderItem(order_id=order.id,
                                         product_id=it.product_id,
                                         color_name=it.color.name,
                                         size_name=it.size.name,
                                         product_name=it.product.name,
                                         unit_price=it.unit_price,
                                         quantity=it.quantity))
                db.session.delete(it)
            db.session.commit()
            return redirect(url_for('order_confirm', number=number))
    return render_template('checkout.html', items=items, addresses=addresses,
                           subtotal=bag_subtotal(items),
                           shipping=bag_shipping(items), error=error)


@app.route('/us/en/shop/confirm/<number>')
@login_required
def order_confirm(number):
    order = Order.query.filter_by(number=number,
                                   user_id=current_user.id).first_or_404()
    return render_template('order_confirm.html', order=order)


@app.route('/us/en/account/orders')
@login_required
def orders():
    rows = (Order.query.filter_by(user_id=current_user.id)
            .order_by(Order.placed_at.desc(), Order.id).all())
    return render_template('orders.html', orders=rows)


@app.route('/us/en/account/orders/<number>')
@login_required
def order_detail(number):
    order = Order.query.filter_by(number=number,
                                  user_id=current_user.id).first_or_404()
    return render_template('order_detail.html', order=order)


# --------------------------------------------------------------- wishlist ----

@app.route('/us/en/wishlist')
@login_required
def wishlist():
    rows = (WishlistItem.query.filter_by(user_id=current_user.id)
            .order_by(WishlistItem.id).all())
    return render_template('wishlist.html', items=rows)


@app.route('/us/en/wishlist/toggle', methods=['POST'])
@login_required
def wishlist_toggle():
    product = Product.query.filter_by(seo_id=request.form.get('product', '')).first()
    if not product:
        abort(404)
    color = product.color(request.form.get('color', '')) or product.main_color
    row = WishlistItem.query.filter_by(user_id=current_user.id,
                                       product_id=product.id).first()
    if row:
        db.session.delete(row)
    else:
        db.session.add(WishlistItem(user_id=current_user.id,
                                    product_id=product.id, color_id=color.id))
    db.session.commit()
    return redirect(local_target(request.form.get('back'), url_for('wishlist')))


# --------------------------------------------------------------- addresses ----

@app.route('/us/en/account/addresses')
@login_required
def addresses():
    rows = Address.query.filter_by(user_id=current_user.id).order_by(
        Address.id).all()
    return render_template('addresses.html', addresses=rows)


@app.route('/us/en/account/addresses/add', methods=['POST'])
@login_required
def address_add():
    label = request.form.get('label', '').strip() or 'HOME'
    full_name = request.form.get('full_name', '').strip()
    line1 = request.form.get('line1', '').strip()
    line2 = request.form.get('line2', '').strip() or None
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip()
    zipc = request.form.get('zip', '').strip()
    phone = request.form.get('phone', '').strip()
    if not (full_name and line1 and city and state and phone and re.fullmatch(r'\d{5}(?:-\d{4})?', zipc)):
        return render_template('addresses.html',
                               addresses=Address.query.filter_by(
                                   user_id=current_user.id).all(),
                               error='Fill in every address field.'), 400
    db.session.add(Address(user_id=current_user.id, label=label,
                           full_name=full_name, line1=line1, line2=line2,
                           city=city, state=state, zip=zipc, phone=phone))
    db.session.commit()
    return redirect(url_for('addresses'))


@app.route('/us/en/account/addresses/<int:addr_id>/default', methods=['POST'])
@login_required
def address_default(addr_id):
    addr = db.session.get(Address, addr_id)
    if not addr or addr.user_id != current_user.id:
        abort(404)
    for a in Address.query.filter_by(user_id=current_user.id).all():
        a.is_default = (a.id == addr_id)
    db.session.commit()
    return redirect(url_for('addresses'))


@app.route('/us/en/account/addresses/<int:addr_id>/delete', methods=['POST'])
@login_required
def address_delete(addr_id):
    addr = db.session.get(Address, addr_id)
    if not addr or addr.user_id != current_user.id:
        abort(404)
    db.session.delete(addr)
    db.session.commit()
    return redirect(url_for('addresses'))


# ---------------------------------------------------------------- account ----

@app.route('/us/en/account')
@login_required
def account():
    return render_template('account.html',
                           addresses=Address.query.filter_by(
                               user_id=current_user.id).count(),
                           orders=Order.query.filter_by(
                               user_id=current_user.id).count(),
                           wishlist=WishlistItem.query.filter_by(
                               user_id=current_user.id).count())


# ------------------------------------------------------------- newsletter ----

@app.route('/newsletter', methods=['POST'])
def newsletter():
    email = request.form.get('email', '').strip().lower()
    if not email or '@' not in email:
        return render_template('newsletter_error.html'), 400
    db.session.add(NewsletterSignup(email=email,
                                    section=request.form.get('section', 'WOMAN')))
    db.session.commit()
    return render_template('newsletter_done.html', email=email)


# ------------------------------------------------------------------ health --

@app.route('/_health')
def health():
    return jsonify(ok=True,
                   products=Product.query.count(),
                   colors=Color.query.count(),
                   sizes=Size.query.count(),
                   categories=Category.query.count(),
                   stores=Store.query.count(),
                   searches=SearchSnapshot.query.count(),
                   campaigns=Campaign.query.count(),
                   users=User.query.count(),
                   orders=Order.query.count(),
                   cart_items=CartItem.query.count(),
                   wishlist_items=WishlistItem.query.count())


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


# -------------------------------------------------------------- seed on boot --

if os.environ.get('ZARA_AUTO_SEED', '1') != '0':
    main()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 40128)), debug=False)
