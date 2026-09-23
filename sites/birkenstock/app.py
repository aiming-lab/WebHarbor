#!/usr/bin/env python3
"""BIRKENSTOCK United States mirror - Flask application.

Mirrors www.birkenstock.com/us (US storefront): homepage, category PLPs with
filters, PDPs with color/size/width selection, search, cart, checkout, orders,
wishlist, account, VIP program, store locator, and customer-service pages.

Product catalog, prices, colors, sizes, images, store list and policy copy are
sourced from the upstream site (see scraped_data/, build-time only); review
prose and benchmark users are original fixtures.
"""
import json
import math
import os
import re
from datetime import datetime, timedelta

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Pinned reference date: the mirror presents a stable snapshot. Relative dates
# in seeded orders/reviews are computed against this moment.
REFERENCE_DATE = datetime(2026, 9, 21, 12, 0, 0)

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-birkenstock-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'birkenstock.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."

STOP_WORDS = {
    "the", "a", "an", "and", "or", "for", "of", "in", "on", "to",
    "with", "sandal", "sandals", "shoe", "shoes", "clog", "clogs",
}

# Real US->BIRKENSTOCK (EU) size conversion chart from the upstream
# FIT AND SIZE GUIDE (https://www.birkenstock.com/us/us-service-fittingguide.html).
US_EU_WOMEN = {
    "4-4.5": 35, "5-5.5": 36, "6-6.5": 37, "7-7.5": 38, "8-8.5": 39,
    "9-9.5": 40, "10-10.5": 41, "11-11.5": 42, "12-12.5": 43,
}
US_EU_MEN = {
    "6-6.5": 39, "7-7.5": 40, "8-8.5": 41, "9-9.5": 42, "10-10.5": 43,
    "11-11.5": 44, "12-12.5": 45, "13-13.5": 46, "14-14.5": 47,
    "15-15.5": 48, "16-16.5": 49, "17-17.5": 50,
}
US_EU_KIDS = {
    "1-1.5": 32, "2-2.5": 33, "3-3.5": 34, "4-4.5": 35, "5-5.5": 36,
    "6-6.5": 24, "7-7.5": 25, "8-8.5": 26, "9-9.5": 27, "10-10.5": 28,
    "11-11.5": 29, "12-12.5": 30, "13-13.5": 31,
}
WIDTHS = ["Regular/Wide", "Medium/Narrow"]

WOMEN_SIZES = list(US_EU_WOMEN)
MEN_SIZES = list(US_EU_MEN)
KIDS_SIZES = list(US_EU_KIDS)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), default="")
    last_name = db.Column(db.String(80), default="")
    phone = db.Column(db.String(30), default="")
    address1 = db.Column(db.String(180), default="")
    address2 = db.Column(db.String(180), default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(40), default="")
    zip_code = db.Column(db.String(20), default="")
    vip_points = db.Column(db.Integer, default=25)
    lifetime_spend = db.Column(db.Float, default=0.0)
    email_opt_in = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: REFERENCE_DATE)

    cart_items = db.relationship("CartItem", backref="user", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", backref="user", cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="user", cascade="all, delete-orphan")
    payment_methods = db.relationship("PaymentMethod", backref="user", cascade="all, delete-orphan")
    reviews = db.relationship("Review", backref="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def vip_tier(self):
        # Upstream VIP tiers (birkenstock.com/us/birkenstock-vip): Essential
        # (sign up - $199), Classic ($200-$699), Premium ($700-$1,499),
        # Icon ($1,500+); 1 point per $1; 25 points for joining.
        if self.lifetime_spend >= 1500:
            return "Icon"
        if self.lifetime_spend >= 700:
            return "Premium"
        if self.lifetime_spend >= 200:
            return "Classic"
        return "Essential"


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    parent_slug = db.Column(db.String(120), default="", index=True)
    blurb = db.Column(db.String(400), default="")
    sort = db.Column(db.Integer, default=0)

    products = db.relationship(
        "ProductCategory", backref="category", cascade="all, delete-orphan")


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    pid = db.Column(db.String(220), unique=True, nullable=False, index=True)
    master_pid = db.Column(db.String(200), index=True)
    slug = db.Column(db.String(200), nullable=False)  # URL name part
    name = db.Column(db.String(220), nullable=False)  # full variant name
    model = db.Column(db.String(160), index=True)     # silhouette, e.g. Arizona
    material = db.Column(db.String(120), index=True)
    color = db.Column(db.String(120), index=True)
    color_id = db.Column(db.String(40), default="")
    price = db.Column(db.Float, nullable=False)
    list_price = db.Column(db.Float, default=0.0)     # pre-sale price when on sale
    badge = db.Column(db.String(60), default="")
    gender = db.Column(db.String(40), index=True)
    style_type = db.Column(db.String(80), default="")
    collection = db.Column(db.String(80), default="")
    art_no = db.Column(db.String(60), default="")
    item_no = db.Column(db.String(60), default="")
    description = db.Column(db.Text, default="")
    material_details = db.Column(db.Text, default="")  # JSON blocks from upstream
    images_json = db.Column(db.Text, default="[]")
    rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    size_group = db.Column(db.String(20), default="women")
    stock = db.Column(db.Integer, default=24)
    one_size = db.Column(db.Boolean, default=False)
    homepage = db.Column(db.Boolean, default=False)

    categories = db.relationship(
        "ProductCategory", backref="product", cascade="all, delete-orphan")
    reviews = db.relationship("Review", backref="product", cascade="all, delete-orphan")
    cart_items = db.relationship("CartItem", backref="product", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", backref="product", cascade="all, delete-orphan")

    @property
    def images(self):
        try:
            return json.loads(self.images_json or "[]")
        except ValueError:
            return []

    @property
    def material_blocks(self):
        try:
            return json.loads(self.material_details or "[]")
        except ValueError:
            return []

    @property
    def main_image(self):
        imgs = self.images
        return imgs[0] if imgs else ""

    @property
    def on_sale(self):
        return self.list_price and self.list_price > self.price

    @property
    def sale_percent(self):
        if self.on_sale:
            return int(round((1 - self.price / self.list_price) * 100))
        return 0

    @property
    def size_groups(self):
        group = self.size_group or "women"
        if group == "unisex":
            return [("Women", WOMEN_SIZES), ("Men", MEN_SIZES), ("Kids", KIDS_SIZES)]
        if group == "men":
            return [("Men", MEN_SIZES)]
        if group == "kids":
            return [("Kids", KIDS_SIZES)]
        return [("Women", WOMEN_SIZES)]

    @property
    def sizes(self):
        seen = []
        for _, group in self.size_groups:
            for s in group:
                if s not in seen:
                    seen.append(s)
        return seen

    @property
    def sibling_colorways(self):
        return (Product.query.filter(Product.master_pid == self.master_pid)
                .order_by(Product.id).all())

    def size_available(self, size):
        # Deterministic fixture stock: ~1 in 6 sizes marked sold out.
        h = sum(ord(c) for c in f"{self.pid}:{size}")
        return h % 6 != 0

    def eu_size(self, size):
        if size in US_EU_WOMEN:
            return US_EU_WOMEN[size]
        if size in US_EU_MEN:
            return US_EU_MEN[size]
        return US_EU_KIDS.get(size, "")

    @property
    def sizes_json(self):
        return [
            {"us": s, "eu": self.eu_size(s), "available": self.size_available(s)}
            for s in self.sizes
        ]


class ProductCategory(db.Model):
    __tablename__ = "product_categories"
    __table_args__ = (db.UniqueConstraint("product_id", "category_id"),)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(160), default="")
    body = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: REFERENCE_DATE)
    verified = db.Column(db.Boolean, default=True)


class CartItem(db.Model):
    __tablename__ = "cart_items"
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", "size", "width"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    width = db.Column(db.String(40), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=lambda: REFERENCE_DATE)

    @property
    def line_total(self):
        return round(self.product.price * self.quantity, 2)


class WishlistItem(db.Model):
    __tablename__ = "wishlist_items"
    __table_args__ = (db.UniqueConstraint("user_id", "product_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    added_at = db.Column(db.DateTime, default=lambda: REFERENCE_DATE)


class PaymentMethod(db.Model):
    __tablename__ = "payment_methods"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    label = db.Column(db.String(80), nullable=False)   # e.g. Visa
    last_four = db.Column(db.String(8), nullable=False)
    holder = db.Column(db.String(120), default="")
    exp_month = db.Column(db.Integer, default=12)
    exp_year = db.Column(db.Integer, default=2028)
    is_default = db.Column(db.Boolean, default=False)


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(40), default="Processing")
    email = db.Column(db.String(160), default="")
    ship_name = db.Column(db.String(160), default="")
    ship_address1 = db.Column(db.String(180), default="")
    ship_address2 = db.Column(db.String(180), default="")
    ship_city = db.Column(db.String(80), default="")
    ship_state = db.Column(db.String(40), default="")
    ship_zip = db.Column(db.String(20), default="")
    payment_label = db.Column(db.String(80), default="")
    payment_last_four = db.Column(db.String(8), default="")
    shipping_method = db.Column(db.String(60), default="Ground Shipping")
    shipping_cost = db.Column(db.Float, default=0.0)
    subtotal = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    points_earned = db.Column(db.Integer, default=0)
    tracking_no = db.Column(db.String(60), default="")
    created_at = db.Column(db.DateTime, default=lambda: REFERENCE_DATE)

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")

    @property
    def status_display(self):
        return self.status


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    name = db.Column(db.String(220), nullable=False)
    model = db.Column(db.String(160), default="")
    color = db.Column(db.String(120), default="")
    size = db.Column(db.String(20), default="")
    width = db.Column(db.String(40), default="")
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    image = db.Column(db.String(260), default="")


class Store(db.Model):
    __tablename__ = "stores"

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(120), nullable=False, index=True)
    address = db.Column(db.String(220), nullable=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(value):
    value = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return value


def tokens_for(query):
    return [
        t for t in re.split(r"\W+", (query or "").lower())
        if t and t not in STOP_WORDS and len(t) > 1
    ]


def scored_search(query, base_query=None):
    """Keyword search over the product's core catalog fields.

    All tokens must match (standard e-commerce AND semantics) against the
    name / model / material / color / style_type / gender text only. The free
    text description is deliberately excluded: it is marketing prose that
    mentions many other products (e.g. the socks whose copy references the
    Arizona sandal) and would pollute multi-word queries like "arizona eva"
    with unrelated cheaper items.
    """
    tokens = tokens_for(query)
    q = base_query if base_query is not None else Product.query
    if not tokens:
        return q.order_by(Product.id), 0
    rows = []
    for product in q.all():
        text = " ".join([
            product.name or "", product.model or "", product.material or "",
            product.color or "", product.style_type or "", product.gender or "",
        ]).lower()
        if all(t in text for t in tokens):
            rows.append(product)
    rows.sort(key=lambda p: p.id)
    return rows, len(rows)


PRICE_FILTERS = {
    "under-100": ("Under $100", 0, 100),
    "100-150": ("$100 - $150", 100, 150),
    "150-200": ("$150 - $200", 150, 200),
    "200-plus": ("$200 & above", 200, 10000),
}

SORTS = {
    "featured": "Featured",
    "price-asc": "Price: Low to High",
    "price-desc": "Price: High to Low",
    "newest": "Newest",
    "name-asc": "Name: A to Z",
}


def category_products(category, page=1, per_page=24, filters=None, sort="featured"):
    q = (Product.query
         .join(ProductCategory, ProductCategory.product_id == Product.id)
         .filter(ProductCategory.category_id == category.id))
    q = apply_filters(q, filters)
    if sort == "price-asc":
        q = q.order_by(Product.price, Product.id)
    elif sort == "price-desc":
        q = q.order_by(Product.price.desc(), Product.id)
    elif sort == "name-asc":
        q = q.order_by(Product.name)
    elif sort == "newest":
        q = q.order_by(Product.id.desc())
    else:
        q = q.order_by(Product.id)
    return q


def apply_filters(q, filters):
    if not filters:
        return q
    if filters.get("colors"):
        q = q.filter(Product.color.in_(filters["colors"]))
    if filters.get("materials"):
        q = q.filter(Product.material.in_(filters["materials"]))
    if filters.get("gender"):
        q = q.filter(Product.gender.in_(filters["gender"]))
    if filters.get("max_price"):
        q = q.filter(Product.price <= float(filters["max_price"]))
    if filters.get("min_price"):
        q = q.filter(Product.price >= float(filters["min_price"]))
    return q


def filter_facets(category):
    """Color/material facets with counts for one category (driven from DB)."""
    base = (Product.query
            .join(ProductCategory, ProductCategory.product_id == Product.id)
            .filter(ProductCategory.category_id == category.id))
    colors, materials = {}, {}
    for p in base:
        colors[p.color] = colors.get(p.color, 0) + 1
        materials[p.material] = materials.get(p.material, 0) + 1
    return colors, materials


def cart_summary(user):
    items = user.cart_items
    subtotal = round(sum(i.line_total for i in items), 2)
    full_price_count = sum(
        i.quantity for i in items if not i.product.on_sale)
    if subtotal >= 200 or full_price_count >= 2:
        shipping = 0.0
        shipping_note = "FREE"
    else:
        shipping = 7.95
        shipping_note = "$7.95"
    tax = round(subtotal * 0.08875, 2)
    total = round(subtotal + shipping + tax, 2)
    return {
        "cart_items": items, "subtotal": subtotal, "shipping": shipping,
        "shipping_note": shipping_note, "tax": tax, "total": total,
        "count": sum(i.quantity for i in items),
    }


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    return {
        "wishlist_count": (len(current_user.wishlist_items) if current_user.is_authenticated else 0),
        "cart_count": (sum(i.quantity for i in current_user.cart_items) if current_user.is_authenticated else 0),
    }


def _pdp_url(product):
    return url_for("product_detail", name_slug=product.slug, pid=product.pid)


def _rebuild_query(exclude_color=None, exclude_material=None, clear_price=False):
    args = request.args.to_dict(flat=False)
    colors = [c for c in args.get("color", []) if c != exclude_color]
    materials = [m for m in args.get("material", []) if m != exclude_material]
    parts = []
    for c in colors:
        parts.append(f"color={c.replace(' ', '+')}")
    for m in materials:
        parts.append(f"material={m.replace(' ', '+')}")
    if not clear_price and args.get("max_price"):
        parts.append(f"max_price={args['max_price']}")
    if args.get("sort"):
        parts.append(f"sort={args['sort']}")
    return "&".join(parts)


def _query_string(page=None):
    args = request.args.to_dict(flat=False)
    parts = []
    for c in args.get("color", []):
        parts.append(f"color={c.replace(' ', '+')}")
    for m in args.get("material", []):
        parts.append(f"material={m.replace(' ', '+')}")
    if args.get("max_price"):
        parts.append(f"max_price={args['max_price']}")
    if args.get("sort"):
        parts.append(f"sort={args['sort']}")
    if page:
        parts.append(f"page={page}")
    return "&".join(parts)


app.jinja_env.globals.update(
    _pdp_url=_pdp_url, rebuild_query=_rebuild_query, query_string=_query_string)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
@app.route("/us/")
def index():
    recommended = (Product.query.filter_by(homepage=True)
                   .order_by(Product.id).limit(12).all())
    if len(recommended) < 12:
        recommended = Product.query.order_by(Product.id).limit(12).all()
    fan_favorites = (Product.query.filter(Product.rating >= 4.0)
                     .order_by(Product.review_count.desc())
                     .limit(12).all())
    sale = Product.query.filter(Product.list_price > Product.price).limit(12).all()
    return render_template(
        "index.html", recommended=recommended, fan_favorites=fan_favorites, sale=sale)


@app.route("/us/search/")
def search():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "featured")
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 24
    results, total = scored_search(q) if q else ([], 0)
    if sort == "price-asc":
        results = sorted(results, key=lambda p: p.price)
    elif sort == "price-desc":
        results = sorted(results, key=lambda p: -p.price)
    elif sort == "name-asc":
        results = sorted(results, key=lambda p: p.name)
    shown = results[(page - 1) * per_page: page * per_page]
    return render_template(
        "search.html", query=q, results=shown, total=total,
        page=page, per_page=per_page, sort=sort, sorts=SORTS,
        pages=max(1, math.ceil(total / per_page)) if total else 1)


def _render_plp(category, title, breadcrumbs, filters=None, sort="featured",
                page=1, per_page=24, style_tiles=None, blurb=""):
    pq = category_products(category, filters=filters, sort=sort)
    total = pq.count()
    items = pq.offset((page - 1) * per_page).limit(per_page).all()
    colors, materials = filter_facets(category)
    genders = {}
    for p in Product.query.join(
            ProductCategory, ProductCategory.product_id == Product.id).filter(
            ProductCategory.category_id == category.id):
        genders[p.gender] = genders.get(p.gender, 0) + 1
    return render_template(
        "category.html", category=category, title=title, breadcrumbs=breadcrumbs,
        items=items, total=total, page=page, per_page=per_page,
        sort=sort, colors=colors, materials=materials, genders=genders,
        active=filters or {}, style_tiles=style_tiles or [], blurb=blurb,
        sorts=SORTS)


def _category_or_404(slug):
    category = Category.query.filter_by(slug=slug).first()
    if not category:
        abort(404)
    return category


@app.route("/us/women/")
@app.route("/us/men/")
@app.route("/us/kids/")
@app.route("/us/kids-teens/")
@app.route("/us/sale/")
@app.route("/us/new-arrivals/")
@app.route("/us/whats-new/")
@app.route("/us/clogs-edit/")
@app.route("/us/the-clogs-edit/")
@app.route("/us/professional/")
@app.route("/us/eva-sandals/")
@app.route("/us/big-buckle-collection/")
@app.route("/us/foot-care/")
@app.route("/us/foot-care/all-products/")
@app.route("/us/campaign/best-sellers/")
@app.route("/us/best-sellers/")
def top_level_plp():
    slug = request.path.rstrip("/").rsplit("/", 1)[-1]
    aliases = {
        "kids-teens": "kids", "whats-new": "new-arrivals",
        "clogs-edit": "clogs", "the-clogs-edit": "clogs",
        "best-sellers": "best-sellers",
    }
    slug = aliases.get(slug, slug)
    if slug == "foot-care":
        slug = "foot-care"
    category = _category_or_404(slug)
    page = max(1, request.args.get("page", 1, type=int))
    sort = request.args.get("sort", "featured")
    filters = _collect_filters()
    crumbs = [("Home", url_for("index")), (category.name, None)]
    return _render_plp(category, category.name.upper(), crumbs, filters,
                       sort, page)


def _collect_filters():
    colors = request.args.getlist("color")
    materials = request.args.getlist("material")
    genders = request.args.getlist("gender")
    max_price = request.args.get("max_price", type=float)
    return {
        "colors": [c for c in colors if c],
        "materials": [m for m in materials if m],
        "gender": [g for g in genders if g],
        "max_price": max_price,
    }


@app.route("/us/women/<path:sub>/")
@app.route("/us/men/<path:sub>/")
@app.route("/us/kids/<path:sub>/")
def gender_sub_plp(sub):
    parts = request.path.rstrip("/").split("/")
    gender = parts[2]  # women | men | kids
    category = _category_or_404(f"{gender}-{sub.replace('/', '-')}")
    page = max(1, request.args.get("page", 1, type=int))
    sort = request.args.get("sort", "featured")
    filters = _collect_filters()
    short = re.sub(r"^Women's \|^Men's \|^Boys \|^Girls ", "", category.name)
    crumbs = [
        ("Home", url_for("index")),
        (gender.title(), f"/us/{gender}/"),
        (short, None),
    ]
    return _render_plp(category, category.name.upper(), crumbs, filters,
                       sort, page)


@app.route("/us/styles/<silhouette>/")
def style_plp(silhouette):
    category = _category_or_404(f"style-{silhouette}")
    page = max(1, request.args.get("page", 1, type=int))
    sort = request.args.get("sort", "featured")
    filters = _collect_filters()
    model = category.name
    crumbs = [("Home", url_for("index")), ("Styles", None), (model, None)]
    return _render_plp(category, model.upper(), crumbs, filters, sort, page)


@app.route("/us/<name_slug>/<pid>.html")
def product_detail(name_slug, pid):
    product = Product.query.filter_by(pid=pid).first_or_404()
    siblings = product.sibling_colorways
    reviews = (Review.query.filter_by(product_id=product.id)
               .order_by(Review.created_at.desc()).all())
    similar = (Product.query
               .join(ProductCategory, ProductCategory.product_id == Product.id)
               .filter(ProductCategory.category_id.in_(
                   [c.category_id for c in product.categories]),
                   Product.id != product.id)
               .distinct().limit(8).all())
    breadcrumbs = [("Home", url_for("index"))]
    if product.categories:
        parent = product.categories[0].category
        parent_name = re.sub(r"^Women's \|^Men's ", "", parent.name)
        parent_href = None
        if parent.parent_slug in ("women", "men"):
            parent_href = f"/us/{parent.parent_slug}/{parent.slug.split(parent.parent_slug + '-', 1)[-1]}/"
        elif parent.parent_slug == "kids":
            parent_href = f"/us/kids/{parent.slug.split('kids-', 1)[-1]}/"
        else:
            parent_href = f"/us/{parent.slug}/"
        breadcrumbs.append((parent_name, parent_href))
    breadcrumbs.append((product.model, None))
    return render_template(
        "product.html", product=product, siblings=siblings,
        reviews=reviews, similar=similar, breadcrumbs=breadcrumbs,
        widths=WIDTHS)


@app.route("/us/cart/")
def cart():
    if not current_user.is_authenticated:
        return render_template("cart.html", summary=None)
    summary = cart_summary(current_user)
    return render_template("cart.html", summary=summary)


@app.route("/us/cart/update/<int:item_id>", methods=["POST"])
@login_required
def cart_update(item_id):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    action = request.form.get("action")
    if action == "remove":
        db.session.delete(item)
    elif action == "inc":
        item.quantity = min(item.quantity + 1, 10)
    elif action == "dec":
        item.quantity -= 1
        if item.quantity <= 0:
            db.session.delete(item)
    db.session.commit()
    return redirect(url_for("cart"))


@app.route("/us/cart/add/<pid>", methods=["POST"])
def cart_add(pid):
    product = Product.query.filter_by(pid=pid).first_or_404()
    if not current_user.is_authenticated:
        flash("Please log in to add items to your cart.", "info")
        return redirect(url_for("login", next=request.form.get("next") or request.referrer or "/"))
    if product.one_size:
        size, width = "One size", "One size"
    else:
        size = request.form.get("size", "")
        width = request.form.get("width", WIDTHS[0])
        if not size:
            flash("Please select a size.", "error")
            return redirect(request.referrer or "/")
    if product.badge == "VIP Access" and not current_user.is_authenticated:
        flash("Join BIRKENSTOCK VIP to buy this style.", "info")
        return redirect(url_for("vip"))
    item = CartItem.query.filter_by(
        user_id=current_user.id, product_id=product.id, size=size, width=width).first()
    if item:
        item.quantity += 1
    else:
        db.session.add(CartItem(user_id=current_user.id, product_id=product.id,
                                size=size, width=width))
    db.session.commit()
    flash(f"Added {product.model} to your cart.", "success")
    return redirect(url_for("cart"))


@app.route("/us/wishlist/add/<pid>", methods=["POST"])
def wishlist_add(pid):
    product = Product.query.filter_by(pid=pid).first_or_404()
    if not current_user.is_authenticated:
        flash("Please log in to use your wish list.", "info")
        return redirect(url_for("login", next=request.form.get("next") or "/"))
    existing = WishlistItem.query.filter_by(
        user_id=current_user.id, product_id=product.id).first()
    if not existing:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=product.id))
        db.session.commit()
        flash(f"Added {product.model} to your wish list.", "success")
    else:
        flash("That item is already on your wish list.", "info")
    return redirect(request.form.get("next") or url_for("wishlist"))


@app.route("/us/wishlist/")
@login_required
def wishlist():
    return render_template("wishlist.html", items=current_user.wishlist_items)


@app.route("/us/wishlist/remove/<int:item_id>", methods=["POST"])
@login_required
def wishlist_remove(item_id):
    item = WishlistItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Removed from your wish list.", "info")
    return redirect(url_for("wishlist"))


@app.route("/us/login/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Welcome back.", "success")
            dest = request.args.get("next") or request.form.get("next")
            return redirect(dest or url_for("account"))
        flash("Email or password is incorrect.", "error")
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/us/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not (first_name and email and password):
            flash("Please fill in all required fields.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(email=email, first_name=first_name, last_name=last_name)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to BIRKENSTOCK VIP. You start with 25 points.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/us/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/us/account/")
@login_required
def account():
    return render_template("account.html", orders=current_user.orders)


@app.route("/us/account/profile", methods=["GET", "POST"])
@login_required
def account_profile():
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name", "").strip()
        current_user.last_name = request.form.get("last_name", "").strip()
        current_user.phone = request.form.get("phone", "").strip()
        current_user.address1 = request.form.get("address1", "").strip()
        current_user.address2 = request.form.get("address2", "").strip()
        current_user.city = request.form.get("city", "").strip()
        current_user.state = request.form.get("state", "").strip()
        current_user.zip_code = request.form.get("zip_code", "").strip()
        if request.form.get("email_opt_in"):
            current_user.email_opt_in = True
        db.session.commit()
        flash("Your profile has been updated.", "success")
        return redirect(url_for("account_profile"))
    return render_template("account_profile.html")


@app.route("/us/account/payment", methods=["GET", "POST"])
@login_required
def account_payment():
    if request.method == "POST":
        label = request.form.get("label", "").strip()
        last_four = re.sub(r"\D", "", request.form.get("card_number", ""))[-4:]
        if not (label and last_four):
            flash("Please provide a card label and number.", "error")
        else:
            db.session.add(PaymentMethod(
                user_id=current_user.id, label=label, last_four=last_four,
                holder=request.form.get("holder", "").strip(),
                exp_month=int(request.form.get("exp_month", 12) or 12),
                exp_year=int(request.form.get("exp_year", 2028) or 2028)))
            db.session.commit()
            flash(f"{label} ending in {last_four} was added.", "success")
        return redirect(url_for("account_payment"))
    return render_template("account_payment.html")


@app.route("/us/checkout/", methods=["GET", "POST"])
@login_required
def checkout():
    summary = cart_summary(current_user)
    if not summary["cart_items"]:
        flash("Your cart is empty.", "info")
        return redirect(url_for("cart"))
    if request.method == "POST":
        step = request.form.get("step")
        if step == "address":
            required = ["ship_name", "address1", "city", "state", "zip_code"]
            if not all(request.form.get(f) for f in required):
                flash("Please fill in all required address fields.", "error")
            else:
                current_user.first_name = request.form.get("first_name", current_user.first_name)
                current_user.address1 = request.form.get("address1", "").strip()
                current_user.address2 = request.form.get("address2", "").strip()
                current_user.city = request.form.get("city", "").strip()
                current_user.state = request.form.get("state", "").strip()
                current_user.zip_code = request.form.get("zip_code", "").strip()
                db.session.commit()
                return redirect(url_for("checkout", step="payment"))
        elif step == "payment":
            choice = (request.form.get("payment_method_id") or "").strip()
            card_label = request.form.get("card_label", "").strip()
            last_four = re.sub(r"\D", "", request.form.get("card_number", ""))[-4:]
            pm = None
            if choice == "new":
                # "Use a new card" selected: label + 4+ digit number required
                if not (card_label and len(last_four) == 4):
                    flash("Please enter a valid card (label and 4+ digit number).", "error")
                else:
                    pm = PaymentMethod(user_id=current_user.id, label=card_label,
                                       last_four=last_four,
                                       holder=request.form.get("holder", ""))
                    db.session.add(pm)
                    db.session.commit()
            elif choice.isdigit():
                pm = PaymentMethod.query.get(int(choice))
                if pm is not None and pm.user_id != current_user.id:
                    pm = None
            if pm is None:
                if choice != "new":
                    flash("Please select a payment method.", "error")
                return redirect(url_for("checkout", step="payment"))
            session["checkout_pm_id"] = pm.id
            return redirect(url_for("checkout", step="review"))
        elif step == "place":
            pm_id = (request.form.get("payment_method_id") or "").strip()
            if not pm_id:
                pm_id = str(session.get("checkout_pm_id") or "")
            pm = PaymentMethod.query.get(int(pm_id)) if pm_id.isdigit() else None
            if pm is None or pm.user_id != current_user.id:
                flash("Please select a payment method.", "error")
                return redirect(url_for("checkout", step="payment"))
            summary = cart_summary(current_user)
            order = Order(
                order_no=_new_order_no(),
                user_id=current_user.id,
                status="Processing",
                email=current_user.email,
                ship_name=request.form.get("ship_name", current_user.name),
                ship_address1=current_user.address1,
                ship_address2=current_user.address2,
                ship_city=current_user.city,
                ship_state=current_user.state,
                ship_zip=current_user.zip_code,
                payment_label=pm.label,
                payment_last_four=pm.last_four,
                shipping_method="Ground Shipping",
                shipping_cost=summary["shipping"],
                subtotal=summary["subtotal"],
                tax=summary["tax"],
                total=summary["total"],
                points_earned=int(summary["subtotal"]),
                tracking_no=_new_tracking_no(),
            )
            for item in summary["cart_items"]:
                order.items.append(OrderItem(
                    product_id=item.product_id, name=item.product.name,
                    model=item.product.model, color=item.product.color,
                    size=item.size, width=item.width,
                    price=item.product.price, quantity=item.quantity,
                    image=item.product.main_image))
            db.session.add(order)
            for item in summary["cart_items"]:
                db.session.delete(item)
            current_user.vip_points += order.points_earned
            current_user.lifetime_spend += order.subtotal
            db.session.commit()
            session.pop("checkout_pm_id", None)
            return redirect(url_for("order_detail", order_no=order.order_no))
        return redirect(url_for("checkout"))
    step = request.args.get("step", "address")
    chosen_pm = None
    if step == "review":
        pm_id = session.get("checkout_pm_id")
        if pm_id:
            pm = PaymentMethod.query.get(pm_id)
            if pm is not None and pm.user_id == current_user.id:
                chosen_pm = pm
        if chosen_pm is None and current_user.payment_methods:
            chosen_pm = current_user.payment_methods[-1]
    return render_template("checkout.html", summary=summary, step=step,
                           chosen_pm=chosen_pm)


def _new_order_no():
    seq = Order.query.count() + 1
    return f"US-{REFERENCE_DATE.strftime('%Y%m%d')}-{seq:05d}"


def _new_tracking_no():
    import random
    rng = random.Random(int(REFERENCE_DATE.timestamp()) + Order.query.count())
    return f"1Z{rng.randrange(10**9, 10**10)}BIRK{rng.randrange(100, 999)}"


@app.route("/us/orders/")
@login_required
def orders():
    return render_template("orders.html", orders=current_user.orders)


@app.route("/us/orders/<order_no>/")
@login_required
def order_detail(order_no):
    order = Order.query.filter_by(order_no=order_no, user_id=current_user.id).first_or_404()
    return render_template("order_detail.html", order=order)


@app.route("/us/order-status/")
def order_status():
    return render_template("order_status.html")


@app.route("/us/track-order/", methods=["POST"])
def track_order():
    order_no = request.form.get("order_no", "").strip()
    email = request.form.get("email", "").strip().lower()
    order = Order.query.filter_by(order_no=order_no).first()
    if not order:
        return render_template("order_status.html", error="We could not find an order with that number.", order_no=order_no)
    if order.email.lower() != email:
        return render_template("order_status.html", error="That email does not match the order.", order_no=order_no)
    return render_template("order_status.html", order=order)


@app.route("/us/vip-access/")
@app.route("/us/birkenstock-vip/")
def vip():
    return render_template("vip.html")


@app.route("/us/storelocator/")
def storelocator():
    q = request.args.get("q", "").strip()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 50
    base = Store.query
    if q:
        like = f"%{q}%"
        base = base.filter(or_(Store.city.like(like), Store.address.like(like)))
    total = base.count()
    stores = base.order_by(Store.city, Store.id).offset((page - 1) * per_page).limit(per_page).all()
    return render_template("storelocator.html", stores=stores, q=q, total=total,
                            page=page, per_page=per_page)


@app.route("/us/storelist/")
def storelist():
    return redirect(url_for("storelocator", **request.args))


@app.route("/us/faq/")
@app.route("/us/faq.html")
def faq():
    return render_template("faq.html")


@app.route("/us/policies/shipping/")
def shipping_policy():
    return render_template("policies/shipping.html")


@app.route("/us/policies/returns/")
def return_policy():
    return render_template("policies/returns.html")


@app.route("/us/returns/")
def returns_start():
    return redirect(url_for("return_policy"))


@app.route("/us/service/")
@app.route("/us/contact-customer-service/")
def customer_service():
    return render_template("service.html")


@app.route("/us/service/fitting-guide/")
def fitting_guide():
    return render_template("fitting_guide.html")


@app.route("/us/education/footbed/")
def footbed():
    return render_template("footbed.html")


@app.route("/us/journal/")
def journal():
    return render_template("journal.html")


@app.route("/us/journal/heritage/")
def journal_heritage():
    return render_template("journal_heritage.html")


@app.route("/us/1774/")
def page_1774():
    return render_template("1774.html")


@app.route("/us/newsletter/", methods=["POST"])
def newsletter():
    email = request.form.get("email", "").strip()
    if not email or "@" not in email:
        flash("Please enter a valid email address.", "error")
    else:
        flash("Thank you for subscribing to the BIRKENSTOCK newsletter.", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/us/policies/privacy/")
def privacy_policy():
    return render_template("policies/privacy.html")


@app.route("/us/policies/terms/")
def terms_policy():
    return render_template("policies/terms.html")


@app.route("/us/policies/counterfeits/")
def counterfeits_policy():
    return render_template("policies/counterfeits.html")


@app.route("/us/policies/rewards/")
def rewards_policy():
    return redirect(url_for("vip"))


@app.route("/us/accessibility/")
def accessibility():
    return render_template("accessibility.html")


@app.route("/us/idme/")
def idme():
    return render_template("idme.html")


@app.route("/us/idme/<group>/")
def idme_group(group):
    return render_template("idme.html", group=group.replace("-", " ").title())


@app.route("/us/giftcertificate/")
def giftcertificate():
    return render_template("giftcertificate.html")


@app.route("/us/giftcertificate/check-balance/")
def giftcertificate_balance():
    return render_template("giftcertificate.html")


@app.route("/us/sandals-edit/")
def sandals_edit():
    return redirect("/us/women/sandals/")


@app.route("/_health")
def health():
    return {
        "ok": True,
        "site": "birkenstock",
        "products": Product.query.count(),
        "categories": Category.query.count(),
        "stores": Store.query.count(),
        "users": User.query.count(),
    }


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


from seed_data import seed_benchmark_users, seed_database  # noqa: E402

with app.app_context():
    db.create_all()
    seed_database(db, Category, Product, ProductCategory, Review, Store)
    seed_benchmark_users(db, User, CartItem, WishlistItem, Order, OrderItem,
                         PaymentMethod, Product, bcrypt)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
