"""macys_wine_shop mirror — Flask app.

A functional mirror of https://macyswineshop.com/ (Macy's Wine Shop, the
Drinks-powered Shopify storefront) for the WebHarbor offline benchmark.

Mirrors the upstream surfaces: the age/state gate, the announcement carousel,
the header with search + Ship-to + account + cart, the mega nav, the homepage
section stack, collection listings with the Color/Type/Sweetness/Country/
Varietal/Vintage facet filters and the upstream sort menu, metafield-style
filtered collection URLs, product detail pages (bottles and pack case
contents), Junip-style ratings and reviews, scored search, the cart with the
6+ bottle free-shipping rule and the 3-bottle checkout minimum, the multi-step
checkout with state disclosures, account management with order history, the
Wine Club page, the Wine 101 blog, the gift-card product, the storefront
pages, and the newsletter signup.

All runtime data lives in the SQLite seed DB materialized by seed_data.py
from the tracked source_data.json snapshot. Seed functions are idempotent at
the function level so /reset keeps the DB byte-identical.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import secrets
import sys
from datetime import datetime, timezone

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   session, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup
from sqlalchemy import or_

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_URI_OVERRIDE = os.environ.get("MWS_DB_URI", "")
RUNTIME_DB_PATH = os.path.join(BASE_DIR, "instance", "macys_wine_shop.db")
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
IMAGE_DIR = os.path.join(BASE_DIR, "static", "images")

MIRROR_DATE = "2026-09-22"
PASSWORD_NAMESPACE = "macys_wine_shop.benchmark"
FREE_SHIPPING_BOTTLES = 6
MIN_CHECKOUT_BOTTLES = 3
SHIPPING_FEE = 14.95
PROCESSING_FEE = 2.95

US_STATES = [
    ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"),
    ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"),
    ("DC", "District of Columbia"), ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"),
    ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"),
    ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"),
    ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"),
    ("MS", "Mississippi"), ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"),
    ("NV", "Nevada"), ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"),
    ("NY", "New York"), ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"),
    ("OK", "Oklahoma"), ("OR", "Oregon"), ("PA", "Pennsylvania"), ("RI", "Rhode Island"),
    ("SC", "South Carolina"), ("SD", "South Dakota"), ("TN", "Tennessee"), ("TX", "Texas"),
    ("UT", "Utah"), ("VT", "Vermont"), ("VA", "Virginia"), ("WA", "Washington"),
    ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming"),
]

BOTTLE_STATES = set(s for s, _ in US_STATES)
# Source: https://macyswineshop.com/pages/shipping-policy (2026-09-23).
EXCLUDED_WINE_STATES = {"AK", "AR", "DE", "HI", "MS", "RI", "SD", "UT"}


def _ensure_dirs() -> None:
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)


_ensure_dirs()

app = Flask(__name__, instance_path=INSTANCE_DIR)
app.config["SECRET_KEY"] = "macys-wine-shop-demo-session-key"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    DB_URI_OVERRIDE if DB_URI_OVERRIDE.startswith("sqlite:///")
    else f"sqlite:///{RUNTIME_DB_PATH}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to your account to continue."


def stable_password_hash(raw_password: str) -> str:
    digest = hashlib.sha256()
    digest.update(f"{PASSWORD_NAMESPACE}:{raw_password}".encode("utf-8"))
    return digest.hexdigest()


def load_json(raw, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def dump_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------

class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime(2026, 9, 22, 12, 0, 0))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime(2026, 9, 22, 12, 0, 0),
                           onupdate=lambda: datetime(2026, 9, 22, 12, 0, 0))


class User(db.Model, UserMixin, TimestampMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    username = db.Column(db.String(80), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(64), nullable=False)
    first_name = db.Column(db.String(80), default="")
    last_name = db.Column(db.String(80), default="")
    phone = db.Column(db.String(30), default="")

    addresses = db.relationship("Address", backref="user", lazy=True,
                                order_by="Address.id")
    payment_methods = db.relationship("PaymentMethod", backref="user", lazy=True,
                                      order_by="PaymentMethod.id")
    orders = db.relationship("Order", backref="user", lazy=True,
                             order_by="Order.created_at.desc(), Order.id.desc()")


class Address(db.Model, TimestampMixin):
    __tablename__ = "addresses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    label = db.Column(db.String(60), default="")
    full_name = db.Column(db.String(120), nullable=False)
    line1 = db.Column(db.String(200), nullable=False)
    line2 = db.Column(db.String(200), default="")
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(30), default="")
    is_default = db.Column(db.Boolean, default=False)


class PaymentMethod(db.Model, TimestampMixin):
    __tablename__ = "payment_methods"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    brand = db.Column(db.String(30), nullable=False)
    last4 = db.Column(db.String(4), nullable=False)
    exp_month = db.Column(db.Integer, nullable=False)
    exp_year = db.Column(db.Integer, nullable=False)
    holder = db.Column(db.String(120), nullable=False)
    is_default = db.Column(db.Boolean, default=False)


class Collection(db.Model, TimestampMixin):
    __tablename__ = "collections"
    id = db.Column(db.Integer, primary_key=True)
    handle = db.Column(db.String(190), nullable=False, unique=True, index=True)
    title = db.Column(db.String(190), nullable=False)
    description_html = db.Column(db.Text, default="")
    sort_order = db.Column(db.String(30), default="best-selling")
    position = db.Column(db.Integer, nullable=False, default=0)
    in_nav = db.Column(db.Boolean, default=False)

    products = db.relationship("Product", secondary="collection_products",
                               lazy="dynamic",
                               order_by="CollectionProduct.position")


class Product(db.Model, TimestampMixin):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    handle = db.Column(db.String(190), nullable=False, unique=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    product_type = db.Column(db.String(30), nullable=False)  # Bottle | Pack | Gift Card
    vendor = db.Column(db.String(120), default="MacysWine Shop")
    description_html = db.Column(db.Text, default="")
    subheading = db.Column(db.String(255), default="")
    color = db.Column(db.String(40), default="")
    sweetness = db.Column(db.String(40), default="")
    country = db.Column(db.String(60), default="")
    varietal = db.Column(db.String(80), default="")
    vintage = db.Column(db.String(10), default="")
    wine_category = db.Column(db.String(80), default="")
    region = db.Column(db.String(80), default="")
    winery = db.Column(db.String(120), default="")
    abv = db.Column(db.String(10), default="")
    specs_html_rows = db.Column(db.Text, default="")  # json list of [key, value]
    awards = db.Column(db.Text, default="")            # json list of award dicts
    price = db.Column(db.Float, nullable=False, default=0.0)
    compare_at_price = db.Column(db.Float, default=0.0)
    on_sale = db.Column(db.Boolean, default=False)
    available = db.Column(db.Boolean, default=True)
    published_at = db.Column(db.String(30), default=MIRROR_DATE)
    rating_average = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    rating_distribution = db.Column(db.Text, default="")  # json {"1": n, ...}
    recommended_percentage = db.Column(db.Float, default=0.0)
    available_states = db.Column(db.Text, default="")      # json list (union of variants)
    nav_ribbon = db.Column(db.String(40), default="")      # e.g. "SALE" / "17% off"
    bestseller_rank = db.Column(db.Integer, default=0)
    related_handles = db.Column(db.Text, default="")       # json list of handles

    variants = db.relationship("ProductVariant", backref="product", lazy=True,
                               order_by="ProductVariant.position")
    images = db.relationship("ProductImage", backref="product", lazy=True,
                             order_by="ProductImage.position")
    reviews = db.relationship("Review", backref="product", lazy=True,
                              order_by="Review.created_at.desc()")

    @property
    def first_image(self):
        return self.images[0] if self.images else None

    @property
    def first_variant(self):
        return self.variants[0] if self.variants else None

    @property
    def bottle_count(self):
        v = self.first_variant
        return v.bottle_count if v else 1

    @property
    def is_pack(self):
        return self.product_type == "Pack"

    @property
    def pct_off(self):
        if self.compare_at_price and self.compare_at_price > self.price:
            return round((self.compare_at_price - self.price)
                          / self.compare_at_price * 100)
        return 0

    @property
    def spec_rows(self):
        return load_json(self.specs_html_rows, [])

    @property
    def award_list(self):
        return load_json(self.awards, [])

    def shippable_to(self, state: str) -> bool:
        if self.product_type == "Gift Card":
            return True
        if state in EXCLUDED_WINE_STATES:
            return False
        if not state:
            return True
        states = load_json(self.available_states, [])
        return not states or state in states


class ProductVariant(db.Model, TimestampMixin):
    __tablename__ = "product_variants"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    upstream_id = db.Column(db.String(30), default="")
    title = db.Column(db.String(120), nullable=False)  # e.g. "6-pack", "Default Title"
    label = db.Column(db.String(120), default="")     # display label: "6 Pack"
    price = db.Column(db.Float, nullable=False, default=0.0)
    compare_at_price = db.Column(db.Float, default=0.0)
    sku = db.Column(db.String(60), default="")
    available = db.Column(db.Boolean, default=True)
    bottle_count = db.Column(db.Integer, nullable=False, default=1)
    position = db.Column(db.Integer, nullable=False, default=0)
    available_states = db.Column(db.Text, default="")  # json list
    gift_amount = db.Column(db.Float, default=0.0)
    case_split = db.Column(db.String(80), default="")  # e.g. "3 Red, 3 White"

    @property
    def pct_off(self):
        if self.compare_at_price and self.compare_at_price > self.price:
            return round((self.compare_at_price - self.price)
                          / self.compare_at_price * 100)
        return 0

    case_bottles = db.relationship("CaseBottle", backref="variant", lazy=True,
                                   order_by="CaseBottle.number")

    def shippable_to(self, state: str) -> bool:
        if self.product.product_type == "Gift Card":
            return True
        if state in EXCLUDED_WINE_STATES:
            return False
        states = load_json(self.available_states, [])
        return not state or not states or state in states



class ProductImage(db.Model, TimestampMixin):
    __tablename__ = "product_images"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    path = db.Column(db.String(255), nullable=False)  # /static/images/...
    alt = db.Column(db.String(255), default="")
    position = db.Column(db.Integer, nullable=False, default=0)


class CaseBottle(db.Model, TimestampMixin):
    __tablename__ = "case_bottles"
    id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=False)
    number = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(255), default="")
    winery = db.Column(db.String(120), default="")
    varietal = db.Column(db.String(80), default="")
    year = db.Column(db.String(10), default="")
    type = db.Column(db.String(20), default="Bottle")
    abv = db.Column(db.String(10), default="")
    country = db.Column(db.String(60), default="")
    region = db.Column(db.String(80), default="")
    price = db.Column(db.Float, default=0.0)


class CollectionProduct(db.Model):
    __tablename__ = "collection_products"
    collection_id = db.Column(db.Integer, db.ForeignKey("collections.id"), primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), primary_key=True)
    position = db.Column(db.Integer, nullable=False, default=0)


class Review(db.Model, TimestampMixin):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), default="")
    body = db.Column(db.Text, default="")
    customer_name = db.Column(db.String(120), default="")
    verified_buyer = db.Column(db.Boolean, default=False)
    would_recommend = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime(2026, 6, 18, 1, 49, 5))


class CartItem(db.Model, TimestampMixin):
    __tablename__ = "cart_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    session_key = db.Column(db.String(64), default="")
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    variant = db.relationship("ProductVariant", backref="cart_items", lazy=True)


class Order(db.Model, TimestampMixin):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    email = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Processing")
    ship_to_name = db.Column(db.String(120), nullable=False)
    address_line1 = db.Column(db.String(200), nullable=False)
    address_line2 = db.Column(db.String(200), default="")
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(30), default="")
    payment_label = db.Column(db.String(80), default="")
    subtotal = db.Column(db.Float, nullable=False, default=0.0)
    shipping = db.Column(db.Float, nullable=False, default=0.0)
    processing = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)
    bottle_count = db.Column(db.Integer, nullable=False, default=0)
    club_member = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime(2026, 9, 22, 12, 0, 0))

    items = db.relationship("OrderItem", backref="order", lazy=True,
                            order_by="OrderItem.id")


class OrderItem(db.Model, TimestampMixin):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"))
    product_handle = db.Column(db.String(190), nullable=False)
    product_title = db.Column(db.String(255), nullable=False)
    variant_title = db.Column(db.String(120), default="")
    unit_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    bottle_count = db.Column(db.Integer, nullable=False, default=1)


class BlogArticle(db.Model, TimestampMixin):
    __tablename__ = "blog_articles"
    id = db.Column(db.Integer, primary_key=True)
    handle = db.Column(db.String(190), nullable=False, unique=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    excerpt = db.Column(db.Text, default="")
    author = db.Column(db.String(120), default="Macy's Wine Shop")
    published_at = db.Column(db.String(30), default=MIRROR_DATE)
    image_path = db.Column(db.String(255), default="")
    content_html = db.Column(db.Text, default="")
    reading_minutes = db.Column(db.Integer, default=4)


class StaticPage(db.Model, TimestampMixin):
    __tablename__ = "static_pages"
    id = db.Column(db.Integer, primary_key=True)
    handle = db.Column(db.String(190), nullable=False, unique=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    content_html = db.Column(db.Text, default="")


class StateDisclosure(db.Model, TimestampMixin):
    __tablename__ = "state_disclosures"
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(2), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    body_html = db.Column(db.Text, default="")
    display_priority = db.Column(db.Integer, default=0)


class NewsletterSubscriber(db.Model, TimestampMixin):
    __tablename__ = "newsletter_subscribers"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    source = db.Column(db.String(40), default="footer")


class SiteText(db.Model, TimestampMixin):
    __tablename__ = "site_texts"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), nullable=False, unique=True)
    value = db.Column(db.Text, nullable=False)


class HomeSection(db.Model, TimestampMixin):
    __tablename__ = "home_sections"
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    kind = db.Column(db.String(40), nullable=False)
    data_json = db.Column(db.Text, nullable=False)


# --------------------------------------------------------------------------
# Template filters / globals
# --------------------------------------------------------------------------

@app.template_filter("money")
def money_filter(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


@app.template_filter("stars")
def stars_filter(value):
    try:
        filled = int(round(float(value)))
    except (TypeError, ValueError):
        filled = 0
    return "★★★★★"[:filled] + "☆☆☆☆☆"[:5 - filled] if 0 <= filled <= 5 else ""


@app.template_filter("paragraphs")
def paragraphs_filter(value):
    if not value:
        return []
    parts = re.split(r"</p>\s*<p[^>]*>", value.strip().removeprefix("<p>").removesuffix("</p>"))
    return [re.sub(r"<[^>]+>", " ", p).strip() for p in parts if p.strip()]


@app.template_filter("articlehtml")
def articlehtml_filter(value):
    from article_html import article_html
    return Markup(article_html(value))


@app.template_filter("safehtml")
def safehtml_filter(value):
    return Markup(value or "")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(16)
        session["csrf_token"] = token
    return token


def validate_csrf():
    token = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
    if not token or token != session.get("csrf_token"):
        abort(400, "Invalid or missing CSRF token.")


@app.before_request
def csrf_guard():
    if request.method == "POST":
        validate_csrf()


def get_session_key():
    key = session.get("cart_key")
    if not key:
        key = secrets.token_hex(16)
        session["cart_key"] = key
    return key


def current_state():
    return session.get("ship_state", "")


def cart_items():
    if current_user.is_authenticated:
        return (CartItem.query.filter_by(user_id=current_user.id)
                .order_by(CartItem.id).all())
    return (CartItem.query.filter_by(session_key=get_session_key(), user_id=None)
            .order_by(CartItem.id).all())


def cart_summary():
    items = cart_items()
    bottles = sum(i.quantity * i.variant.bottle_count for i in items)
    subtotal = sum(i.quantity * i.variant.price for i in items)
    shipping = 0.0 if (bottles >= FREE_SHIPPING_BOTTLES or not bottles) else SHIPPING_FEE
    processing = PROCESSING_FEE if bottles else 0.0
    return {
        "items": items,
        "count": len(items),
        "bottles": bottles,
        "subtotal": subtotal,
        "shipping": shipping,
        "processing": processing,
        "total": subtotal + shipping + processing,
        "bottles_short": max(0, FREE_SHIPPING_BOTTLES - bottles),
        "meets_minimum": bool(items) and (bottles == 0 or bottles >= MIN_CHECKOUT_BOTTLES),
    }


def merge_session_cart():
    """On login, move session cart rows onto the user."""
    key = get_session_key()
    rows = CartItem.query.filter_by(session_key=key, user_id=None).all()
    for row in rows:
        existing = CartItem.query.filter_by(
            user_id=current_user.id, variant_id=row.variant_id).first()
        if existing:
            existing.quantity += row.quantity
            db.session.delete(row)
        else:
            row.user_id = current_user.id
            row.session_key = ""
    db.session.commit()


def tokenize(query):
    return [t for t in re.split(r"[^a-z0-9é']+", (query or "").lower()) if len(t) > 1]


def scored_search(query, limit=48):
    tokens = tokenize(query)
    if not tokens:
        return []
    products = Product.query.filter(Product.product_type != "Hidden").all()
    scored = []
    for p in products:
        text = " ".join([p.title, p.subheading, p.varietal, p.country, p.wine_category,
                         p.color, p.winery, p.sweetness, p.vintage]).lower()
        score = sum(1 for t in tokens if t in text)
        title_bonus = sum(2 for t in tokens if t in p.title.lower())
        if score + title_bonus > 0:
            scored.append((p, score + title_bonus))
    scored.sort(key=lambda pair: (-pair[1], pair[0].bestseller_rank, pair[0].title))
    return [p for p, _ in scored[:limit]]


SORT_OPTIONS = [
    ("manual", "Featured"),
    ("most-relevant", "Most relevant"),
    ("best-selling", "Best selling"),
    ("title-ascending", "Alphabetically, A-Z"),
    ("title-descending", "Alphabetically, Z-A"),
    ("price-ascending", "Price, low to high"),
    ("price-descending", "Price, high to low"),
    ("created-ascending", "Date, old to new"),
    ("created-descending", "Date, new to old"),
]

FACET_KEYS = {
    "color": "color",
    "type": "product_type",
    "sweetness": "sweetness",
    "country": "country",
    "varietal": "varietal",
    "vintage": "vintage",
}


@app.context_processor
def inject_global_context():
    summary = cart_summary()
    return {
        "csrf_token": csrf_token,
        "cart_summary": summary,
        "cart_count": sum(i.quantity for i in summary["items"]),
        "ship_state": current_state(),
        "us_states": US_STATES,
        "age_confirmed": request.cookies.get("age_confirmed") == "true" or session.get("age_confirmed"),
        "site_texts": {t.key: t.value for t in SiteText.query.all()},
        "nav_collections": Collection.query.filter_by(in_nav=True).order_by(Collection.position).all(),
        "current_year": 2026,
    }


def age_gate_needed():
    return not (request.cookies.get("age_confirmed") == "true" or session.get("age_confirmed"))


# Upstream's premium-tiles home section carries three labeled tiles under the
# "Premium wines at great prices" heading: Award Winners, 6-Bottle Wine Sets
# and 12-Bottle Wine Sets. The scraped source snapshot captured a leading HTML
# fragment ("id=\"shopify-section-...\"") that the seeder stored as the first
# tile's label, shifting the other labels off their tiles (audit finding A4).
# The seed stays byte-frozen for the grading contract, so the upstream labels
# are restored at render time, keyed by the tile's own link.
PREMIUM_TILE_LABELS = {
    "/collections/award-winners": "Award Winners",
    "/collections/6-bottle-wine-sets": "6-Bottle Wine Sets",
    "/collections/12-bottle-wine-sets": "12-Bottle Wine Sets",
}


def _restore_premium_tile_labels(block):
    for tile in block.get("tiles") or []:
        if not isinstance(tile, dict):
            continue
        upstream_label = PREMIUM_TILE_LABELS.get(tile.get("link"))
        if upstream_label:
            tile["label"] = upstream_label


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.route("/")
def home():
    sections = HomeSection.query.order_by(HomeSection.position).all()
    blocks = [load_json(s.data_json, {}) for s in sections]
    for block in blocks:
        if block.get("kind") == "featured":
            tab_products = {}
            for slug, handles in (block.get("tab_products") or {}).items():
                found = [Product.query.filter_by(handle=h).first() for h in handles]
                tab_products[slug] = [p for p in found if p]
            block["resolved"] = tab_products
            slugs = list((block.get("tab_products") or {}).keys())
            labels = block.get("tab_labels") or []
            block["tab_labels"] = [(slugs[i], labels[i][1] if i < len(labels) else slugs[i])
                                    for i in range(len(slugs))]
        if block.get("kind") == "blog_cards":
            resolved_articles = []
            for entry in block.get("articles") or []:
                article = BlogArticle.query.filter_by(handle=entry.get("handle")).first()
                if article:
                    resolved_articles.append({
                        "handle": article.handle,
                        "title": article.title,
                        "excerpt": article.excerpt or "",
                        "image": ("/static/images/" + article.image_path) if article.image_path else "",
                    })
            block["articles"] = resolved_articles
        if block.get("kind") == "premium_tiles":
            _restore_premium_tile_labels(block)
    return render_template("index.html", sections=blocks,
                           show_age_gate=age_gate_needed())


@app.route("/age/confirm", methods=["POST"])
def age_confirm():
    state = request.form.get("state", "").upper()
    answer = request.form.get("answer", "")
    if answer != "yes":
        return render_template("age_rejected.html"), 200
    if state not in BOTTLE_STATES:
        return jsonify({"ok": False, "error": "Please select your state."}), 400
    session["age_confirmed"] = True
    session["ship_state"] = state
    response = jsonify({"ok": True, "state": state})
    response.set_cookie("age_confirmed", "true", max_age=60 * 60 * 24 * 180)
    return response


@app.route("/ship-state", methods=["POST"])
def ship_state():
    state = request.form.get("state", "").upper()
    if state not in BOTTLE_STATES:
        abort(400)
    session["ship_state"] = state
    return jsonify({"ok": True, "state": state})


@app.route("/collections/<handle>")
def collection(handle):
    col = Collection.query.filter_by(handle=handle).first_or_404()
    per_page = 36
    page = max(1, request.args.get("page", 1, type=int))
    query = col.products

    # metafield-style filters, mirroring upstream URL params
    active = {}
    for facet, column in FACET_KEYS.items():
        param = f"filter.p.m.drinks.{facet}"
        values = request.args.getlist(param)
        if values:
            active[facet] = values
            clauses = [getattr(Product, column) == v for v in values]
            query = query.filter(or_(*clauses))

    # Explicit sorts must actually reorder: the dynamic relationship query
    # carries an built-in ORDER BY collection_products.position, and appending
    # .order_by() to it only adds secondary keys (reviewer finding F1). Clear
    # it first; the default (best-selling / collection default) keeps the
    # upstream position order so the default merchandising stays faithful.
    sort = request.args.get("sort_by", col.sort_order or "best-selling")
    explicit_sort = sort in {"price-ascending", "price-descending",
                             "title-ascending", "title-descending",
                             "created-ascending", "created-descending"}
    base = query.order_by(None) if explicit_sort else query
    total = base.count()

    order = Product.bestseller_rank
    if sort == "price-ascending":
        order = Product.price
    elif sort == "price-descending":
        order = Product.price.desc()
    elif sort == "title-ascending":
        order = Product.title
    elif sort == "title-descending":
        order = Product.title.desc()
    elif sort == "created-descending":
        order = Product.id.desc()
    elif sort == "created-ascending":
        order = Product.id
    items = (base.order_by(order, Product.id)
             .offset((page - 1) * per_page).limit(per_page).all())

    # facet value counts across the collection (unfiltered), upstream-style
    facets = {}
    all_products = col.products.all()
    for facet, column in FACET_KEYS.items():
        counts = {}
        for p in all_products:
            value = getattr(p, column)
            if value:
                counts[value] = counts.get(value, 0) + 1
        facets[facet] = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    pages = max(1, (total + per_page - 1) // per_page)
    return render_template("collection.html", collection=col, products=items,
                           total=total, page=page, pages=pages, facets=facets,
                           active=active, sort=sort, sort_options=SORT_OPTIONS)


@app.route("/products/<handle>")
def product(handle):
    p = Product.query.filter_by(handle=handle).first_or_404()
    related = [Product.query.filter_by(handle=h).first()
               for h in load_json(p.related_handles, [])]
    related = [r for r in related if r][:8]
    if not related:
        related = (Product.query.filter(Product.product_type == p.product_type,
                                        Product.id != p.id)
                   .order_by(Product.bestseller_rank).limit(8).all())
    return render_template("product_pack.html" if p.is_pack else "product.html",
                           product=p, related=related,
                           show_age_gate=age_gate_needed())


@app.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    sort = request.args.get("sort_by", "relevance")
    results = scored_search(q)
    if sort == "price-ascending":
        results = sorted(results, key=lambda p: (p.price, p.title))
    elif sort == "price-descending":
        results = sorted(results, key=lambda p: (-p.price, p.title))
    elif sort == "title-ascending":
        results = sorted(results, key=lambda p: p.title)
    elif sort == "title-descending":
        results = sorted(results, key=lambda p: p.title, reverse=True)
    elif sort == "created-ascending":
        results = sorted(results, key=lambda p: p.id)
    elif sort == "created-descending":
        results = sorted(results, key=lambda p: -p.id)
    elif sort == "best-selling":
        results = sorted(results, key=lambda p: (p.bestseller_rank, p.title))
    return render_template("search.html", q=q, results=results, sort=sort,
                           sort_options=SORT_OPTIONS,
                           show_age_gate=age_gate_needed())


@app.route("/cart")
def cart_page():
    return render_template("cart.html", summary=cart_summary(),
                           show_age_gate=age_gate_needed())


@app.route("/cart/add", methods=["POST"])
def cart_add():
    variant_id = request.form.get("variant_id", type=int)
    quantity = max(1, min(24, request.form.get("quantity", 1, type=int)))
    variant = db.session.get(ProductVariant, variant_id) if variant_id else None
    if not variant:
        return jsonify({"ok": False, "error": "Variant not found"}), 404
    state = current_state()
    if state and not variant.shippable_to(state):
        return jsonify({"ok": False, "error": "Item cannot ship to your state"}), 403
    if not variant.available:
        return jsonify({"ok": False, "error": "This item is currently unavailable"}), 403
    if current_user.is_authenticated:
        row = CartItem.query.filter_by(user_id=current_user.id,
                                        variant_id=variant.id).first()
        if row:
            row.quantity = min(24, row.quantity + quantity)
        else:
            row = CartItem(user_id=current_user.id, variant_id=variant.id,
                           quantity=quantity)
            db.session.add(row)
    else:
        key = get_session_key()
        row = CartItem.query.filter_by(session_key=key, user_id=None,
                                       variant_id=variant.id).first()
        if row:
            row.quantity = min(24, row.quantity + quantity)
        else:
            row = CartItem(session_key=key, variant_id=variant.id, quantity=quantity)
            db.session.add(row)
    db.session.commit()
    return jsonify({"ok": True, "cart_count": sum(i.quantity for i in cart_items())})


@app.route("/cart/update/<int:item_id>", methods=["POST"])
def cart_update(item_id):
    row = db.session.get(CartItem, item_id)
    if not row:
        abort(404)
    if current_user.is_authenticated and row.user_id != current_user.id:
        abort(403)
    if not current_user.is_authenticated and (row.user_id or row.session_key != get_session_key()):
        abort(403)
    quantity = request.form.get("quantity", 1, type=int)
    if quantity <= 0:
        db.session.delete(row)
    else:
        row.quantity = min(24, quantity)
    db.session.commit()
    return redirect(url_for("cart_page"))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
def cart_remove(item_id):
    return cart_update(item_id) if request.form.get("quantity") == "0" else cart_update(item_id)


@app.route("/checkout")
def checkout():
    summary = cart_summary()
    if not summary["items"]:
        return redirect(url_for("cart_page"))
    return redirect(url_for("checkout_information"))


def _checkout_guard():
    summary = cart_summary()
    if not summary["items"]:
        return None, redirect(url_for("cart_page"))
    if not summary["meets_minimum"]:
        return None, redirect(url_for("cart_page"))
    return summary, None


@app.route("/checkout/information", methods=["GET", "POST"])
def checkout_information():
    summary, bounce = _checkout_guard()
    if bounce:
        return bounce
    errors = {}
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in
                ("email", "ship_to_name", "address_line1", "address_line2",
                 "city", "state", "zip_code", "phone")}
        if current_user.is_authenticated and request.form.get("address_id"):
            addr = db.session.get(Address, int(request.form["address_id"]))
            if addr and addr.user_id == current_user.id:
                form = {"email": current_user.email, "ship_to_name": addr.full_name,
                        "address_line1": addr.line1, "address_line2": addr.line2,
                        "city": addr.city, "state": addr.state,
                        "zip_code": addr.zip_code, "phone": addr.phone}
        if not form.get("email") or "@" not in form.get("email", ""):
            errors["email"] = "Enter a valid email address."
        if not form.get("ship_to_name"):
            errors["ship_to_name"] = "Enter the recipient's name."
        if not form.get("address_line1"):
            errors["address_line1"] = "Enter a street address."
        if not form.get("city"):
            errors["city"] = "Enter a city."
        if form.get("state") not in BOTTLE_STATES:
            errors["state"] = "Select a state we can ship to."
        if not re.match(r"^\d{5}(-\d{4})?$", form.get("zip_code", "")):
            errors["zip_code"] = "Enter a valid ZIP code."
        if any(not item.variant.shippable_to(form.get("state", ""))
               for item in summary["items"]):
            errors["state"] = "Wine in your cart cannot ship to this state. Choose an eligible delivery address."
        if not errors:
            session["checkout_info"] = form
            return redirect(url_for("checkout_payment"))
    elif current_user.is_authenticated:
        addr = next((a for a in current_user.addresses if a.is_default),
                    current_user.addresses[0] if current_user.addresses else None)
        if addr:
            form = {"email": current_user.email, "ship_to_name": addr.full_name,
                    "address_line1": addr.line1, "address_line2": addr.line2,
                    "city": addr.city, "state": addr.state,
                    "zip_code": addr.zip_code, "phone": addr.phone}
    return render_template("checkout_information.html", summary=summary,
                           form=form, errors=errors,
                           show_age_gate=age_gate_needed())


@app.route("/checkout/payment", methods=["GET", "POST"])
def checkout_payment():
    summary, bounce = _checkout_guard()
    if bounce:
        return bounce
    info = session.get("checkout_info")
    if not info:
        return redirect(url_for("checkout_information"))
    errors = {}
    if request.method == "POST":
        if current_user.is_authenticated and request.form.get("payment_id"):
            method = db.session.get(PaymentMethod, int(request.form["payment_id"]))
            if method and method.user_id == current_user.id:
                session["checkout_payment"] = f"{method.brand} ending in {method.last4}"
                return redirect(url_for("checkout_review"))
        number = re.sub(r"\D", "", request.form.get("card_number", ""))
        holder = request.form.get("card_holder", "").strip()
        exp_month = request.form.get("exp_month", "").strip()
        exp_year = request.form.get("exp_year", "").strip()
        cvc = re.sub(r"\D", "", request.form.get("card_cvc", ""))
        if len(number) < 13 or len(number) > 19:
            errors["card_number"] = "Enter a valid card number."
        if not holder:
            errors["card_holder"] = "Enter the name on the card."
        if exp_month not in [f"{i:02d}" for i in range(1, 13)]:
            errors["exp_month"] = "Select the expiration month."
        if not re.match(r"^\d{4}$", exp_year or ""):
            errors["exp_year"] = "Select the expiration year."
        if len(cvc) < 3 or len(cvc) > 4:
            errors["card_cvc"] = "Enter the security code."
        if not errors:
            brand = "Visa" if number.startswith("4") else (
                "Mastercard" if number[:1] in "5" else (
                    "American Express" if number[:1] == "3" else "Card"))
            session["checkout_payment"] = f"{brand} ending in {number[-4:]}"
            return redirect(url_for("checkout_review"))
    return render_template("checkout_payment.html", summary=summary,
                           info=info, errors=errors,
                           show_age_gate=age_gate_needed())


@app.route("/checkout/review", methods=["GET", "POST"])
def checkout_review():
    summary, bounce = _checkout_guard()
    if bounce:
        return bounce
    info = session.get("checkout_info")
    payment = session.get("checkout_payment")
    if not info or not payment:
        return redirect(url_for("checkout_information"))
    state = info.get("state", "")
    disclosures = StateDisclosure.query.filter_by(state=state) \
        .order_by(StateDisclosure.display_priority).all()
    errors = {}
    if any(not item.variant.available or not item.variant.shippable_to(state)
           for item in summary["items"]):
        errors["shipping"] = "An item is unavailable or cannot ship to your delivery state. Return to your cart or update your address."
    if request.method == "POST":
        if request.form.get("age_confirmed") != "on":
            errors["age"] = "Please confirm you are 21 years of age or older."
        if not errors:
            order = _place_order(summary, info, payment)
            return redirect(url_for("checkout_confirmation",
                                    order_number=order.order_number))
    return render_template("checkout_review.html", summary=summary, info=info,
                           payment=payment, disclosures=disclosures, errors=errors,
                           show_age_gate=age_gate_needed())


def _place_order(summary, info, payment):
    seq = Order.query.count() + 1042
    order = Order(
        order_number=f"MWS{seq}",
        user_id=current_user.id if current_user.is_authenticated else None,
        email=info.get("email", ""),
        status="Processing",
        ship_to_name=info.get("ship_to_name", ""),
        address_line1=info.get("address_line1", ""),
        address_line2=info.get("address_line2", ""),
        city=info.get("city", ""),
        state=info.get("state", ""),
        zip_code=info.get("zip_code", ""),
        phone=info.get("phone", ""),
        payment_label=payment,
        subtotal=summary["subtotal"],
        shipping=summary["shipping"],
        processing=summary["processing"],
        total=summary["total"],
        bottle_count=summary["bottles"],
    )
    db.session.add(order)
    for item in summary["items"]:
        db.session.add(OrderItem(
            order=order,
            variant_id=item.variant_id,
            product_handle=item.variant.product.handle,
            product_title=item.variant.product.title,
            variant_title=item.variant.title,
            unit_price=item.variant.price,
            quantity=item.quantity,
            bottle_count=item.variant.bottle_count,
        ))
        CartItem.query.filter_by(id=item.id).delete()
    db.session.commit()
    session.pop("checkout_info", None)
    session.pop("checkout_payment", None)
    session["last_order"] = order.order_number
    return order


@app.route("/checkout/confirmation/<order_number>")
def checkout_confirmation(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    if not ((current_user.is_authenticated and order.user_id == current_user.id)
            or session.get("last_order") == order_number):
        abort(404)
    return render_template("confirmation.html", order=order,
                           show_age_gate=False)


@app.route("/order-status", methods=["GET", "POST"])
def order_status():
    order = None
    error = ""
    if request.method == "POST":
        number = request.form.get("order_number", "").strip().lstrip("#")
        email = request.form.get("email", "").strip().lower()
        order = Order.query.filter(
            db.func.replace(Order.order_number, "#", "") == number).first()
        if not order or order.email.lower() != email:
            order = None
            error = ("We couldn't find an order with that number and email "
                     "combination. Check the details and try again.")
    return render_template("order_status.html", order=order, error=error,
                           show_age_gate=age_gate_needed())


@app.route("/login", methods=["GET", "POST"])
def login():
    errors = {}
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and user.password_hash == stable_password_hash(password):
            login_user(user)
            merge_session_cart()
            target = request.args.get("next", "")
            if not (target.startswith("/") and not target.startswith("//")
                    and "\\" not in target and not any(ord(c) < 32 for c in target)):
                target = url_for("account")
            return redirect(target)
        errors["form"] = "Incorrect email or password. Please try again."
    return render_template("login.html", errors=errors,
                           show_age_gate=age_gate_needed())


@app.route("/register", methods=["GET", "POST"])
def register():
    errors = {}
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        first = request.form.get("first_name", "").strip()
        last = request.form.get("last_name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if "@" not in email:
            errors["email"] = "Enter a valid email address."
        if User.query.filter(db.func.lower(User.email) == email).first():
            errors["email"] = "An account with this email already exists."
        if not first or not last:
            errors["name"] = "Enter your first and last name."
        if len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."
        if password != confirm:
            errors["confirm"] = "Passwords do not match."
        if not errors:
            user = User(email=email, username=email.split("@")[0],
                        display_name=f"{first} {last}".strip(),
                        password_hash=stable_password_hash(password),
                        first_name=first, last_name=last)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            merge_session_cart()
            return redirect(url_for("account"))
    return render_template("register.html", errors=errors,
                           show_age_gate=age_gate_needed())


@app.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/account")
@login_required
def account():
    return render_template("account.html", user=current_user,
                           show_age_gate=age_gate_needed())


@app.route("/account/profile", methods=["GET", "POST"])
@login_required
def account_profile():
    saved = False
    errors = {}
    if request.method == "POST":
        first = request.form.get("first_name", "").strip()
        last = request.form.get("last_name", "").strip()
        phone = request.form.get("phone", "").strip()
        if not first or not last:
            errors["name"] = "First and last name are required."
        else:
            current_user.first_name = first
            current_user.last_name = last
            current_user.display_name = f"{first} {last}".strip()
            current_user.phone = phone
            db.session.commit()
            saved = True
    return render_template("account_profile.html", user=current_user,
                           saved=saved, errors=errors,
                           show_age_gate=age_gate_needed())


@app.route("/account/password", methods=["GET", "POST"])
@login_required
def account_password():
    errors = {}
    changed = False
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if current_user.password_hash != stable_password_hash(current):
            errors["current"] = "Your current password is incorrect."
        elif len(new) < 8:
            errors["new"] = "New password must be at least 8 characters."
        elif new != confirm:
            errors["confirm"] = "Passwords do not match."
        else:
            current_user.password_hash = stable_password_hash(new)
            db.session.commit()
            changed = True
    return render_template("account_password.html", user=current_user,
                           changed=changed, errors=errors,
                           show_age_gate=age_gate_needed())


@app.route("/account/addresses", methods=["GET", "POST"])
@login_required
def account_addresses():
    errors = {}
    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "delete":
            addr = db.session.get(Address, int(request.form.get("address_id", 0)))
            if addr and addr.user_id == current_user.id:
                db.session.delete(addr)
                db.session.commit()
            return redirect(url_for("account_addresses"))
        form = {k: request.form.get(k, "").strip() for k in
                ("label", "full_name", "line1", "line2", "city", "state",
                 "zip_code", "phone")}
        if not form["full_name"] or not form["line1"] or not form["city"]:
            errors["form"] = "Name, street address, and city are required."
        elif form["state"] not in BOTTLE_STATES:
            errors["form"] = "Select a valid state."
        elif not re.match(r"^\d{5}(-\d{4})?$", form["zip_code"]):
            errors["form"] = "Enter a valid ZIP code."
        else:
            is_default = request.form.get("is_default") == "on" or not current_user.addresses
            if is_default:
                for a in current_user.addresses:
                    a.is_default = False
            db.session.add(Address(user_id=current_user.id, is_default=is_default, **form))
            db.session.commit()
            return redirect(url_for("account_addresses"))
    return render_template("account_addresses.html", user=current_user,
                           errors=errors, show_age_gate=age_gate_needed())


@app.route("/account/payment", methods=["GET", "POST"])
@login_required
def account_payment():
    errors = {}
    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "delete":
            method = db.session.get(PaymentMethod, int(request.form.get("payment_id", 0)))
            if method and method.user_id == current_user.id:
                db.session.delete(method)
                db.session.commit()
            return redirect(url_for("account_payment"))
        number = re.sub(r"\D", "", request.form.get("card_number", ""))
        holder = request.form.get("card_holder", "").strip()
        exp_month = request.form.get("exp_month", "").strip()
        exp_year = request.form.get("exp_year", "").strip()
        if len(number) < 13:
            errors["number"] = "Enter a valid card number."
        elif not holder:
            errors["holder"] = "Enter the name on the card."
        elif exp_month not in [f"{i:02d}" for i in range(1, 13)]:
            errors["exp"] = "Select the expiration month."
        elif not re.match(r"^\d{4}$", exp_year or ""):
            errors["exp"] = "Select the expiration year."
        else:
            brand = "Visa" if number.startswith("4") else (
                "Mastercard" if number[:1] == "5" else (
                    "American Express" if number[:1] == "3" else "Card"))
            is_default = request.form.get("is_default") == "on" or not current_user.payment_methods
            if is_default:
                for m in current_user.payment_methods:
                    m.is_default = False
            db.session.add(PaymentMethod(user_id=current_user.id, brand=brand,
                                         last4=number[-4:], exp_month=int(exp_month),
                                         exp_year=int(exp_year), holder=holder,
                                         is_default=is_default))
            db.session.commit()
            return redirect(url_for("account_payment"))
    return render_template("account_payment.html", user=current_user,
                           errors=errors, show_age_gate=age_gate_needed())


@app.route("/account/orders")
@login_required
def account_orders():
    return render_template("account_orders.html", user=current_user,
                           show_age_gate=age_gate_needed())


@app.route("/account/orders/<order_number>")
@login_required
def account_order_detail(order_number):
    order = Order.query.filter_by(order_number=order_number,
                                   user_id=current_user.id).first_or_404()
    return render_template("order_detail.html", order=order,
                           show_age_gate=age_gate_needed())


@app.route("/pages/<handle>")
def static_page(handle):
    page = StaticPage.query.filter_by(handle=handle).first_or_404()
    if handle == "wine-club":
        return render_template("wine_club.html", show_age_gate=age_gate_needed())
    return render_template("static_page.html", page=page,
                           show_age_gate=age_gate_needed())


@app.route("/blogs/wine-101")
def blog_index():
    articles = BlogArticle.query.order_by(BlogArticle.id.desc()).all()
    return render_template("blog_index.html", articles=articles,
                           show_age_gate=age_gate_needed())


@app.route("/blogs/wine-101/<handle>")
def blog_article(handle):
    article = BlogArticle.query.filter_by(handle=handle).first_or_404()
    related = BlogArticle.query.filter(BlogArticle.id != article.id) \
        .order_by(BlogArticle.id.desc()).limit(3).all()
    return render_template("blog_article.html", article=article,
                           related=related, show_age_gate=age_gate_needed())


@app.route("/newsletter/subscribe", methods=["POST"])
def newsletter_signup():
    email = request.form.get("email", "").strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"ok": False, "error": "Enter a valid email address."}), 400
    if not NewsletterSubscriber.query.filter_by(email=email).first():
        db.session.add(NewsletterSubscriber(email=email))
        db.session.commit()
    return jsonify({"ok": True, "message": "Thanks for signing up!"})


@app.route("/products/quickview/<int:variant_id>")
def quickview(variant_id):
    variant = db.session.get(ProductVariant, variant_id)
    if not variant:
        abort(404)
    p = variant.product
    return jsonify({
        "id": p.id,
        "title": p.title,
        "subheading": p.subheading,
        "price": f"${variant.price:,.2f}",
        "compare_at_price": f"${variant.compare_at_price:,.2f}",
        "on_sale": p.on_sale,
        "url": f"/products/{p.handle}",
        "winery": p.winery,
        "varietal": p.varietal,
        "year": p.vintage,
        "type": p.product_type,
        "abv": p.abv,
        "country": p.country,
        "region": p.region,
        "first_available_variant_id": variant.id,
        "available": variant.available and variant.shippable_to(current_state()),
        "image_url": p.first_image.path if p.first_image else "",
    })


@app.route("/health")
@app.route("/_health")
def health():
    try:
        product_count = Product.query.count()
        collection_count = Collection.query.count()
        user_count = User.query.count()
        ok = product_count > 0 and collection_count > 0 and user_count >= 4
        return jsonify({"ok": ok, "site": "macys_wine_shop",
                        "products": product_count,
                        "collections": collection_count,
                        "users": user_count})
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("500.html"), 500


# --------------------------------------------------------------------------
# Bootstrap
# --------------------------------------------------------------------------

# `python app.py` loads this file as __main__; register it under its import
# name BEFORE importing seed_data so seed_data's `from app import ...` reuses
# this module instead of building a second Flask app + SQLAlchemy instance.
sys.modules.setdefault("app", sys.modules[__name__])

# Capture the bootstrap decision BEFORE importing seed_data: seed_data's
# module top level does `os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")`,
# so reading the flag after the import would always see "1" and a clean
# tree (no instance/ copy) would never build its DB (reviewer finding F7).
_BOOTSTRAP = os.environ.get("WEBSYN_SKIP_BOOTSTRAP") != "1"

from seed_data import seed_benchmark_users, seed_database  # noqa: E402


def bootstrap_site():
    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()


if _BOOTSTRAP:
    bootstrap_site()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 40089))
    app.run(host="0.0.0.0", port=port, debug=False)
