"""JCPenney mirror — Flask app (WebHarbor contributor track).

Functional mirror of https://www.jcpenney.com/ (snapshot 2026-09-22):
department taxonomy, gallery/PLP pages with facet filters and sort, product
detail pages with color/size variants and reviews, scored search, guest + user
bag, multi-step checkout, order history and guest order tracking, wish list,
JCPenney Rewards, coupons, gift cards, and the store locator backed by real
store data.

Seed data is materialized deterministically from the tracked source_data.json
by seed_data.py (see .build-generated-seed).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timedelta as _timedelta
from pathlib import Path
from typing import Any
import sys

# Running `python app.py` executes this file as __main__ while seed_data.py
# imports it again as `app`; alias the module early so both names share one
# Flask/SQLAlchemy instance.
if __name__ == "__main__":
    sys.modules.setdefault("app", sys.modules[__name__])

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup

SITE_SLUG = "jcpenney"
SITE_NAME = "JCPenney"
BENCHMARK_PASSWORD = "TestPass123!"
MIRROR_DATE = datetime(2026, 9, 22)
BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
SEED_DIR = BASE_DIR / "instance_seed"
IMAGE_DIR = BASE_DIR / "static" / "images"
RUNTIME_DB_PATH = INSTANCE_DIR / "jcpenney.db"
SEED_DB_PATH = SEED_DIR / "jcpenney.db"
# Test harness hook: point the app at a scratch DB (see tests/conftest.py).
DB_URI_OVERRIDE = os.environ.get("JCP_DB_PATH", "")
PASSWORD_NAMESPACE = "jcpenney-webharbor-demo"
CART_SESSION_KEY = "jcp_cart"
WISHLIST_SESSION_KEY = "jcp_wishlist"
PAYMENT_BRANDS = ("Visa", "Mastercard", "American Express", "JCPenney Credit Card")
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}


def _ensure_dirs() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


_ensure_dirs()

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config["SECRET_KEY"] = "jcpenney-demo-session-key"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    DB_URI_OVERRIDE if DB_URI_OVERRIDE.startswith("sqlite:///")
    else f"sqlite:///{RUNTIME_DB_PATH}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "signin"
login_manager.login_message = "Sign in to your account to continue."


def stable_password_hash(raw_password: str) -> str:
    digest = hashlib.sha256()
    digest.update(f"{PASSWORD_NAMESPACE}:{raw_password}".encode("utf-8"))
    return digest.hexdigest()


def load_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def slugify(value: str) -> str:
    cleaned: list[str] = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    return "".join(cleaned).strip("-")


def parse_price(text: str | None) -> tuple[float | None, float | None]:
    """'$41.29 - $46.19' -> (41.29, 46.19)"""
    if not text:
        return None, None
    values = [float(v) for v in re.findall(r"\d+(?:\.\d{1,2})?", text.replace(",", ""))]
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    return values[0], values[-1]


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #

class TimestampMixin:
    created_at = db.Column(db.DateTime, default=lambda: MIRROR_DATE, nullable=False)


class User(db.Model, UserMixin, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(64), nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    phone = db.Column(db.String(32), default="")
    rewards_member = db.Column(db.Boolean, default=False, nullable=False)
    rewards_points = db.Column(db.Integer, default=0, nullable=False)
    rewards_tier = db.Column(db.String(30), default="", nullable=False)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = stable_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return hmac.compare_digest(self.password_hash, stable_password_hash(raw_password))

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def rewards_status(self) -> str:
        if not self.rewards_member:
            return "Not a member"
        return self.rewards_tier or "Member"


class Address(db.Model, TimestampMixin):
    __tablename__ = "addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    label = db.Column(db.String(40), default="")
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    line1 = db.Column(db.String(120), nullable=False)
    line2 = db.Column(db.String(120), default="")
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    zip = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(32), default="")
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def one_line(self) -> str:
        parts = [self.line1]
        if self.line2:
            parts.append(self.line2)
        return ", ".join(parts + [f"{self.city}, {self.state} {self.zip}"])


class PaymentMethod(db.Model, TimestampMixin):
    __tablename__ = "payment_methods"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    card_type = db.Column(db.String(40), nullable=False)
    last4 = db.Column(db.String(4), nullable=False)
    cardholder = db.Column(db.String(80), default="")
    exp_month = db.Column(db.Integer, nullable=False)
    exp_year = db.Column(db.Integer, nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def label(self) -> str:
        return f"{self.card_type} ending in {self.last4}"


class Category(db.Model, TimestampMixin):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    department_slug = db.Column(db.String(120), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    is_department = db.Column(db.Boolean, default=False, nullable=False)
    sort = db.Column(db.Integer, default=0, nullable=False)
    hero_image = db.Column(db.String(200), default="")
    blurb = db.Column(db.String(300), default="")

    parent = db.relationship("Category", remote_side=[id], backref="children")


class Product(db.Model, TimestampMixin):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    ppid = db.Column(db.String(40), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(220), nullable=False, index=True)
    name = db.Column(db.String(220), nullable=False)
    brand = db.Column(db.String(80), nullable=False, index=True)
    brand_slug = db.Column(db.String(80), nullable=False, index=True)
    description = db.Column(db.Text, default="")
    bullets_json = db.Column(db.Text, default="[]")
    price = db.Column(db.Float, nullable=False)
    price_max = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float, nullable=False)
    original_price_max = db.Column(db.Float, nullable=False)
    coupon_code = db.Column(db.String(20), default="")
    rating = db.Column(db.Float, default=0.0, nullable=False)
    review_count = db.Column(db.Integer, default=0, nullable=False)
    question_count = db.Column(db.Integer, default=0, nullable=False)
    badges_json = db.Column(db.Text, default="[]")
    item_type = db.Column(db.String(120), default="", index=True)
    product_type = db.Column(db.String(120), default="", index=True)
    occasion = db.Column(db.String(80), default="", index=True)
    fiber_content = db.Column(db.String(120), default="")
    care = db.Column(db.String(160), default="")
    material = db.Column(db.String(120), default="")
    size_range = db.Column(db.String(60), default="")
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    is_clearance = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_new = db.Column(db.Boolean, default=False, nullable=False, index=True)
    sold_recently = db.Column(db.Integer, default=0, nullable=False)
    specifications_json = db.Column(db.Text, default="[]")
    measurements_json = db.Column(db.Text, default="[]")
    sort = db.Column(db.Integer, default=0, nullable=False)

    category = db.relationship("Category", backref=db.backref("products", lazy="dynamic"))
    images = db.relationship(
        "ProductImage", backref="product", lazy="joined",
        order_by="ProductImage.sort", cascade="all, delete-orphan")
    colors = db.relationship(
        "ProductColor", backref="product", lazy="joined",
        order_by="ProductColor.sort", cascade="all, delete-orphan")
    reviews = db.relationship(
        "Review", backref="product", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def bullets(self) -> list[dict[str, Any]]:
        return load_json(self.bullets_json, [])

    @property
    def badges(self) -> list[str]:
        return load_json(self.badges_json, [])

    @property
    def specifications(self) -> list[dict[str, Any]]:
        return load_json(self.specifications_json, [])

    @property
    def primary_image(self) -> str:
        for image in self.images:
            if image.is_primary:
                return image.url_path
        return self.images[0].url_path if self.images else ""

    @property
    def discount_percent(self) -> int:
        if self.original_price <= 0 or self.price >= self.original_price:
            return 0
        return int(round((1 - self.price / self.original_price) * 100))

    def search_blob(self) -> str:
        return " ".join(filter(None, [
            self.name, self.brand, self.item_type, self.product_type,
            self.occasion, self.material, self.category.name if self.category else "",
        ])).lower()


class ProductImage(db.Model, TimestampMixin):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    filename = db.Column(db.String(200), nullable=False)
    alt = db.Column(db.String(240), default="")
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    sort = db.Column(db.Integer, default=0, nullable=False)

    @property
    def url_path(self) -> str:
        return f"/static/images/products/{self.product.ppid}/{self.filename}"


class ProductColor(db.Model, TimestampMixin):
    __tablename__ = "product_colors"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    color = db.Column(db.String(80), nullable=False)
    color_family = db.Column(db.String(40), default="", index=True)
    swatch_file = db.Column(db.String(200), default="")
    sort = db.Column(db.Integer, default=0, nullable=False)
    sizes_json = db.Column(db.Text, default="[]")

    @property
    def swatch_url(self) -> str:
        return f"/static/images/swatches/{self.product.ppid}/{self.swatch_file}"

    @property
    def sizes(self) -> list[dict[str, Any]]:
        return load_json(self.sizes_json, [])


class Review(db.Model, TimestampMixin):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    author = db.Column(db.String(80), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    headline = db.Column(db.String(160), default="")
    body = db.Column(db.Text, default="")
    review_date = db.Column(db.DateTime, nullable=False)
    verified = db.Column(db.Boolean, default=True, nullable=False)
    location = db.Column(db.String(80), default="")


class CartItem(db.Model, TimestampMixin):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    color = db.Column(db.String(80), default="")
    size = db.Column(db.String(40), default="")
    quantity = db.Column(db.Integer, default=1, nullable=False)

    product = db.relationship("Product", lazy="joined")

    @property
    def line_total(self) -> float:
        return round(self.product.price * self.quantity, 2)


class WishlistItem(db.Model, TimestampMixin):
    __tablename__ = "wishlist_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    product = db.relationship("Product", lazy="joined")


class Order(db.Model, TimestampMixin):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(30), nullable=False)
    placed_at = db.Column(db.DateTime, nullable=False)
    delivered_at = db.Column(db.DateTime, nullable=True)
    subtotal = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0.0, nullable=False)
    shipping = db.Column(db.Float, default=0.0, nullable=False)
    tax = db.Column(db.Float, default=0.0, nullable=False)
    total = db.Column(db.Float, nullable=False)
    coupon_code = db.Column(db.String(20), default="")
    ship_name = db.Column(db.String(120), default="")
    ship_address = db.Column(db.String(240), default="")
    ship_city = db.Column(db.String(80), default="")
    ship_state = db.Column(db.String(2), default="")
    ship_zip = db.Column(db.String(10), default="")
    ship_phone = db.Column(db.String(32), default="")
    payment_type = db.Column(db.String(40), default="")
    payment_last4 = db.Column(db.String(4), default="")
    tracking_number = db.Column(db.String(30), default="")
    carrier = db.Column(db.String(40), default="")
    pickup_store = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True)
    gift_message = db.Column(db.String(300), default="")

    items = db.relationship("OrderItem", backref="order", lazy="joined",
                            cascade="all, delete-orphan")

    STATUS_FLOW = ("Processing", "Shipped", "In Transit", "Delivered")

    @property
    def status_index(self) -> int:
        try:
            return self.STATUS_FLOW.index(self.status)
        except ValueError:
            return 0

    @property
    def address_one_line(self) -> str:
        return f"{self.ship_address}, {self.ship_city}, {self.ship_state} {self.ship_zip}"


class OrderItem(db.Model, TimestampMixin):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name = db.Column(db.String(220), nullable=False)
    brand = db.Column(db.String(80), default="")
    color = db.Column(db.String(80), default="")
    size = db.Column(db.String(40), default="")
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    image_file = db.Column(db.String(200), default="")


class Store(db.Model, TimestampMixin):
    __tablename__ = "stores"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    mall = db.Column(db.String(120), nullable=False)
    street = db.Column(db.String(160), nullable=False)
    city = db.Column(db.String(80), nullable=False, index=True)
    state = db.Column(db.String(2), nullable=False, index=True)
    zip = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(32), nullable=False)
    hours_json = db.Column(db.Text, default="{}")
    departments_json = db.Column(db.Text, default="[]")
    services_json = db.Column(db.Text, default="[]")
    google_rating = db.Column(db.Float, nullable=True)
    google_reviews = db.Column(db.Integer, nullable=True)

    @property
    def hours(self) -> dict[str, str]:
        return load_json(self.hours_json, {})

    @property
    def departments(self) -> list[str]:
        return load_json(self.departments_json, [])

    @property
    def services(self) -> list[str]:
        return load_json(self.services_json, [])

    @property
    def name(self) -> str:
        return f"JCPenney {self.mall}"


class Coupon(db.Model, TimestampMixin):
    __tablename__ = "coupons"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(400), default="")
    discount_percent = db.Column(db.Integer, default=0)
    min_purchase = db.Column(db.Float, default=0.0)
    valid_through = db.Column(db.String(40), default="")
    exclusions = db.Column(db.String(300), default="")
    online_only = db.Column(db.Boolean, default=False, nullable=False)


class RewardEvent(db.Model, TimestampMixin):
    __tablename__ = "reward_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(40), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    event_date = db.Column(db.DateTime, nullable=False)


class StaticPage(db.Model, TimestampMixin):
    __tablename__ = "static_pages"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    body_html = db.Column(db.Text, nullable=False)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return User.query.get(int(user_id))


# --------------------------------------------------------------------------- #
# Template filters + globals
# --------------------------------------------------------------------------- #

@app.template_filter("currency")
def currency_filter(value: float | None) -> str:
    if value is None:
        return ""
    return f"${value:,.2f}"


@app.template_filter("stars")
def star_filter(value: float) -> str:
    full = int(value)
    half = 1 if value - full >= 0.5 else 0
    return "★" * (full + half) + "☆" * (5 - full - half)


@app.template_filter("starsmall")
def star_small_filter(value: float) -> str:
    return star_filter(value)


@app.template_filter("paragraphs")
def paragraphs_filter(value: str) -> list[str]:
    cleaned = re.sub(r"<[^>]+>", " ", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return [cleaned] if cleaned else []


@app.template_filter("desc_paragraphs")
def desc_paragraphs_filter(value: str) -> list[str]:
    parts = re.split(r"</p>\s*<p[^>]*>|</p>\s*$|^<p[^>]*>", (value or "").strip())
    out = []
    for part in parts:
        text = re.sub(r"<[^>]+>", " ", part)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out.append(text)
    return out


@app.template_filter("safehtml")
def safehtml_filter(value: str) -> Markup:
    return Markup(value or "")


@app.template_global()
def site_name() -> str:
    return SITE_NAME


@app.template_global()
def US_STATE_NAME():
    return US_STATES


@app.template_global()
def nav_subcategories_global(department):
    return nav_subcategories(department)


@app.template_global()
def timedelta(days: int = 0):
    return _timedelta(days=days)


def nav_departments() -> list[Category]:
    return Category.query.filter_by(is_department=True).order_by(Category.sort).all()


def nav_subcategories(department: Category) -> list[Category]:
    return (Category.query.filter_by(parent_id=department.id)
            .order_by(Category.sort).all())


def get_cart_items() -> list[CartItem]:
    if current_user.is_authenticated:
        return (CartItem.query.filter_by(user_id=current_user.id)
                .order_by(CartItem.created_at, CartItem.id).all())
    return _session_cart_items()


def _session_cart_items() -> list:
    rows: list[dict[str, Any]] = session.get(CART_SESSION_KEY, [])
    items = []
    for row in rows:
        product = Product.query.get(row.get("product_id"))
        if product:
            holder = type("SessionCartItem", (), {
                "id": row.get("id", 0),
                "product": product,
                "product_id": product.id,
                "color": row.get("color", ""),
                "size": row.get("size", ""),
                "quantity": row.get("quantity", 1),
                "line_total": round(product.price * row.get("quantity", 1), 2),
            })()
            items.append(holder)
    return items


def coupon_discount(coupon, subtotal):
    """Apply the archived offer's actual terms, including fixed-dollar offers."""
    if not coupon or subtotal < coupon.min_purchase:
        return 0.0
    if coupon.code == "GOSHOP15":
        return min(10.0, subtotal)
    return round(subtotal * coupon.discount_percent / 100, 2)


def cart_totals(cart_items: list) -> dict[str, float]:
    subtotal = round(sum(item.line_total for item in cart_items), 2)
    coupon = Coupon.query.filter_by(code=request.args.get("code", "")).first()
    discount = 0.0
    if coupon:
        discount = coupon_discount(coupon, subtotal)
    shipping = 0.0 if subtotal >= 75 or not cart_items else 8.95
    tax = round((subtotal - discount) * 0.0825, 2)
    total = round(subtotal - discount + shipping + tax, 2)
    return {
        "subtotal": subtotal, "discount": discount, "shipping": shipping,
        "tax": tax, "total": total,
    }


def get_wishlist_items() -> list[WishlistItem]:
    if current_user.is_authenticated:
        return (WishlistItem.query.filter_by(user_id=current_user.id)
                .order_by(WishlistItem.created_at, WishlistItem.id).all())
    rows = session.get(WISHLIST_SESSION_KEY, [])
    items = []
    for row in rows:
        product = Product.query.get(row.get("product_id"))
        if product:
            holder = type("SessionWishlistItem", (), {
                "id": row.get("id", 0), "product": product,
                "product_id": product.id,
            })()
            items.append(holder)
    return items


def csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = hashlib.sha1(os.urandom(16)).hexdigest()
    return session["_csrf"]


def validate_csrf() -> None:
    token = request.form.get("_csrf", "")
    if not token or token != session.get("_csrf"):
        abort(400, "Invalid request token.")


@app.before_request
def csrf_guard() -> None:
    if request.method == "POST":
        if request.endpoint and request.endpoint.startswith("api_"):
            return
        validate_csrf()


def form_integer(name: str, default: int = 0, minimum: int | None = None,
                 maximum: int | None = None) -> int:
    try:
        value = int(request.form.get(name, default))
    except (TypeError, ValueError):
        value = default
    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def merge_session_cart_into_user() -> None:
    if not current_user.is_authenticated:
        return
    rows = session.pop(CART_SESSION_KEY, [])
    for row in rows:
        product = Product.query.get(row.get("product_id"))
        if not product:
            continue
        existing = CartItem.query.filter_by(
            user_id=current_user.id, product_id=product.id,
            color=row.get("color", ""), size=row.get("size", "")).first()
        if existing:
            existing.quantity = min(existing.quantity + row.get("quantity", 1), 20)
        else:
            db.session.add(CartItem(
                user_id=current_user.id, product_id=product.id,
                color=row.get("color", ""), size=row.get("size", ""),
                quantity=row.get("quantity", 1)))
    db.session.commit()


def merge_session_wishlist_into_user() -> None:
    if not current_user.is_authenticated:
        return
    rows = session.pop(WISHLIST_SESSION_KEY, [])
    for row in rows:
        product_id = row.get("product_id")
        if not product_id:
            continue
        if not WishlistItem.query.filter_by(
                user_id=current_user.id, product_id=product_id).first():
            db.session.add(WishlistItem(user_id=current_user.id, product_id=product_id))
    db.session.commit()


@app.context_processor
def inject_global_context() -> dict[str, Any]:
    cart_count = 0
    wishlist_count = 0
    try:
        items = get_cart_items()
        cart_count = sum(item.quantity for item in items)
        wishlist_count = len(get_wishlist_items())
    except Exception:
        pass
    departments = nav_departments()
    return {
        "nav_departments": departments,
        "cart_count": cart_count,
        "wishlist_count": wishlist_count,
        "csrf_token": csrf_token,
        "store_name": "Alderwood Mall",
        "store_city": "Lynnwood, WA",
        "MIRROR_DATE": MIRROR_DATE,
    }


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #

STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "is",
    "it", "by", "with", "womens", "mens", "womens", "womens",
}


def tokenize(query: str) -> list[str]:
    tokens = re.split(r"[^a-z0-9']+", (query or "").lower())
    return [t for t in tokens if len(t) > 1 and t not in STOP_WORDS]


def scored_search(query: str, queryset=None, limit: int = 60) -> list[tuple[Product, int]]:
    products = list(queryset if queryset is not None else Product.query.all())
    tokens = tokenize(query)
    if not tokens:
        return [(p, 0) for p in products[:limit]]
    scored: list[tuple[Product, int]] = []
    for product in products:
        blob = product.search_blob()
        name_lower = product.name.lower()
        brand_lower = product.brand.lower()
        score = 0
        for token in tokens:
            if token in name_lower:
                score += 3
            elif token in brand_lower:
                score += 2
            elif token in blob:
                score += 1
        if score > 0:
            scored.append((product, score))
    scored.sort(key=lambda pair: (-pair[1], pair[0].sort, pair[0].id))
    return scored[:limit]


# --------------------------------------------------------------------------- #
# Homepage
# --------------------------------------------------------------------------- #

@app.route("/")
def home():
    departments = nav_departments()
    featured = (Product.query.filter_by(is_new=True)
                .order_by(Product.sort).limit(12).all())
    sale_products = (Product.query.filter(Product.original_price > Product.price)
                     .order_by(Product.sort).limit(12).all())
    clearance = (Product.query.filter_by(is_clearance=True)
                 .order_by(Product.sort).limit(12).all())
    recommended = Product.query.order_by(Product.sort).limit(12).all()
    coupons = Coupon.query.order_by(Coupon.id).all()
    return render_template(
        "index.html",
        departments=departments,
        featured=featured,
        sale_products=sale_products,
        clearance=clearance,
        recommended=recommended,
        coupons=coupons,
    )


# --------------------------------------------------------------------------- #
# Category / gallery pages
# --------------------------------------------------------------------------- #

def category_by_path(path: str) -> Category | None:
    category = Category.query.filter_by(slug=path).first()
    if category:
        return category
    # allow trailing "all-" prefixed real slugs too
    parts = path.strip("/").split("/")
    for depth in range(len(parts), 0, -1):
        candidate = "/".join(parts[:depth])
        category = Category.query.filter_by(slug=candidate).first()
        if category:
            return category
    return None


@app.route("/g/", defaults={"path": ""})
@app.route("/g/<path:path>")
def gallery(path: str):
    category = category_by_path(path)
    if not category:
        abort(404)
    if category.slug == "new-and-trending":
        # Upstream curates this page from new arrivals across departments.
        products = list(Product.query.filter_by(is_new=True).order_by(Product.sort).all())
        filter_state: dict[str, Any] = {}
        sort_key = request.args.get("sortBy", "featured")
        products = sort_products(products, sort_key)
        return render_template(
            "gallery.html",
            category=category,
            products=products,
            filter_state=filter_state,
            sort_key=sort_key,
        )
    query = Product.query.filter_by(category_id=category.id)
    products, filter_state = apply_gallery_filters(query)
    sort_key = request.args.get("sortBy", "featured")
    products = sort_products(products, sort_key)
    return render_template(
        "gallery.html",
        category=category,
        products=products,
        filter_state=filter_state,
        sort_key=sort_key,
    )


def apply_gallery_filters(query):
    state: dict[str, Any] = {
        "price_min": None, "price_max": None, "sizes": set(), "colors": set(),
        "brands": set(), "deals": set(), "rating": None,
    }
    price_min = request.args.get("minPrice", type=float)
    price_max = request.args.get("maxPrice", type=float)
    if price_min is not None:
        query = query.filter(Product.price >= price_min)
        state["price_min"] = price_min
    if price_max is not None:
        query = query.filter(Product.price <= price_max)
        state["price_max"] = price_max
    deals = request.args.get("deals", "")
    for deal in filter(None, deals.split("|")):
        state["deals"].add(deal)
        if deal == "clearance":
            query = query.filter(Product.is_clearance.is_(True))
        elif deal == "new":
            query = query.filter(Product.is_new.is_(True))
        elif deal == "sale":
            query = query.filter(Product.original_price > Product.price)
    rating = request.args.get("minRating", type=float)
    if rating:
        query = query.filter(Product.rating >= rating)
        state["rating"] = rating
    products = list(query.all())
    brands = {b.strip() for b in request.args.get("brand", "").split("|") if b.strip()}
    state["brands"] = brands
    if brands:
        products = [p for p in products if p.brand.lower() in brands]
    sizes = {s.strip().lower() for s in request.args.get("size", "").split("|") if s.strip()}
    state["sizes"] = sizes
    if sizes:
        products = [p for p in products if p.size_range and p.size_range.lower() in sizes]
    colors = {c.strip().lower() for c in request.args.get("color", "").split("|") if c.strip()}
    state["colors"] = colors
    if colors:
        kept = []
        for p in products:
            for color in p.colors:
                if color.color_family.lower() in colors:
                    kept.append(p)
                    break
        products = kept
    return products, state


def sort_products(products, sort_key):
    if sort_key == "price_low":
        return sorted(products, key=lambda p: (p.price, p.sort))
    if sort_key == "price_high":
        return sorted(products, key=lambda p: (-p.price, p.sort))
    if sort_key == "rating":
        return sorted(products, key=lambda p: (-p.rating, -p.review_count, p.sort))
    if sort_key == "newest":
        return sorted(products, key=lambda p: (not p.is_new, p.sort))
    return products


@app.route("/s/<path:query>")
def search(query):
    raw_query = request.args.get("Ntt") or query
    results = scored_search(raw_query)
    sort_key = request.args.get("sortBy", "featured")
    products = sort_products([p for p, _ in results], sort_key)
    return render_template(
        "search.html",
        query=raw_query,
        products=products,
        result_count=len(products),
        sort_key=sort_key,
    )


@app.route("/search")
def search_redirect():
    query = request.args.get("q", "").strip()
    if not query:
        return redirect(url_for("home"))
    return redirect(url_for("search", query=query))


# --------------------------------------------------------------------------- #
# Product pages
# --------------------------------------------------------------------------- #

@app.route("/p/<slug>/<ppid>")
def product_page(slug, ppid):
    product = Product.query.filter_by(ppid=ppid).first()
    if not product or product.slug != slug:
        if product:
            return redirect(url_for("product_page", slug=product.slug, ppid=ppid), code=302)
        abort(404)
    related = []
    if product.category:
        related = [p for p in product.category.products.limit(8)
                   if p.id != product.id]
    reviews = product.reviews.order_by(Review.review_date.desc(), Review.id).all()
    rating_breakdown = {n: 0 for n in range(1, 6)}
    for review in reviews:
        rating_breakdown[review.rating] += 1
    return render_template(
        "product.html",
        product=product,
        related=related,
        reviews=reviews,
        rating_breakdown=rating_breakdown,
    )


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #

@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("The email or password you entered is incorrect. Please try again.")
            return render_template("signin.html", email=email)
        login_user(user)
        merge_session_cart_into_user()
        merge_session_wishlist_into_user()
        next_url = request.args.get("next") or request.form.get("next")
        if (next_url and next_url.startswith("/") and not next_url.startswith("//")
                and "\\" not in next_url and not any(ord(c) < 32 for c in next_url)):
            return redirect(next_url)
        return redirect(url_for("account_dashboard"))
    return render_template("signin.html", email="")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        errors = []
        if len(first_name) < 2 or len(last_name) < 2:
            errors.append("Please enter your first and last name.")
        if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Please enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if not errors and User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists. Please sign in.")
        if errors:
            for error in errors:
                flash(error)
            return render_template("register.html", form=request.form)
        user = User(
            email=email, first_name=first_name, last_name=last_name,
            rewards_member=False,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        merge_session_cart_into_user()
        flash("Welcome to JCPenney! Your account has been created.")
        return redirect(url_for("account_dashboard"))
    return render_template("register.html", form={})


@app.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("home"))


# --------------------------------------------------------------------------- #
# Account
# --------------------------------------------------------------------------- #

@app.route("/account/dashboard")
@login_required
def account_dashboard():
    orders = (Order.query.filter_by(user_id=current_user.id)
              .order_by(Order.placed_at.desc()).all())
    wishlist = (WishlistItem.query.filter_by(user_id=current_user.id)
                .order_by(WishlistItem.id).all())
    return render_template("account.html", orders=orders, wishlist=wishlist)


@app.route("/account/dashboard/profile", methods=["GET", "POST"])
@login_required
def account_profile():
    if request.method == "POST":
        action = request.form.get("action", "profile")
        if action == "profile":
            current_user.first_name = request.form.get("first_name", current_user.first_name).strip()
            current_user.last_name = request.form.get("last_name", current_user.last_name).strip()
            current_user.phone = request.form.get("phone", current_user.phone).strip()
            db.session.commit()
            flash("Your profile has been updated.")
            return redirect(url_for("account_profile"))
        if action == "address_add":
            address = Address(
                user_id=current_user.id,
                label=request.form.get("label", "").strip(),
                first_name=request.form.get("first_name", "").strip(),
                last_name=request.form.get("last_name", "").strip(),
                line1=request.form.get("line1", "").strip(),
                line2=request.form.get("line2", "").strip(),
                city=request.form.get("city", "").strip(),
                state=request.form.get("state", "").strip().upper(),
                zip=request.form.get("zip", "").strip(),
                phone=request.form.get("phone", "").strip(),
                is_default=request.form.get("is_default") == "on",
            )
            if not (address.first_name and address.last_name and address.line1
                    and address.city and address.state in US_STATES
                    and re.fullmatch(r"\d{5}", address.zip)):
                flash("Please complete every address field (5-digit ZIP, valid state).")
                return redirect(url_for("account_profile"))
            if address.is_default:
                Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
            db.session.add(address)
            db.session.commit()
            flash("Address added.")
            return redirect(url_for("account_profile"))
        if action == "address_delete":
            address = Address.query.filter_by(
                id=request.form.get("address_id", type=int), user_id=current_user.id).first()
            if address:
                db.session.delete(address)
                db.session.commit()
                flash("Address removed.")
            return redirect(url_for("account_profile"))
        if action == "address_default":
            address = Address.query.filter_by(
                id=request.form.get("address_id", type=int), user_id=current_user.id).first()
            if address:
                Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
                address.is_default = True
                db.session.commit()
                flash("Default address updated.")
            return redirect(url_for("account_profile"))
        if action == "payment_add":
            last4 = request.form.get("card_number", "").replace(" ", "")[-4:]
            exp_month = request.form.get("exp_month", type=int)
            exp_year = request.form.get("exp_year", type=int)
            if not re.fullmatch(r"\d{4}", last4) or not (1 <= (exp_month or 0) <= 12) \
                    or not (2026 <= (exp_year or 0) <= 2040):
                flash("Enter a valid card number and expiration date.")
                return redirect(url_for("account_profile"))
            payment = PaymentMethod(
                user_id=current_user.id,
                card_type=request.form.get("card_type", "Visa"),
                last4=last4,
                cardholder=request.form.get("cardholder", "").strip(),
                exp_month=exp_month, exp_year=exp_year,
                is_default=request.form.get("is_default") == "on",
            )
            if payment.is_default:
                PaymentMethod.query.filter_by(user_id=current_user.id).update(
                    {"is_default": False})
            db.session.add(payment)
            db.session.commit()
            flash("Payment method saved.")
            return redirect(url_for("account_profile"))
        if action == "payment_delete":
            payment = PaymentMethod.query.filter_by(
                id=request.form.get("payment_id", type=int), user_id=current_user.id).first()
            if payment:
                db.session.delete(payment)
                db.session.commit()
                flash("Payment method removed.")
            return redirect(url_for("account_profile"))
        if action == "password":
            current = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            if not current_user.check_password(current):
                flash("Your current password is incorrect.")
            elif len(new) < 8:
                flash("New password must be at least 8 characters long.")
            else:
                current_user.set_password(new)
                db.session.commit()
                flash("Your password has been updated.")
            return redirect(url_for("account_profile"))
    addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.id).all()
    payments = PaymentMethod.query.filter_by(user_id=current_user.id).order_by(PaymentMethod.is_default.desc(), PaymentMethod.id).all()
    return render_template("account_profile.html", addresses=addresses, payments=payments)


@app.route("/account/dashboard/orders")
@login_required
def account_orders():
    orders = (Order.query.filter_by(user_id=current_user.id)
              .order_by(Order.placed_at.desc()).all())
    return render_template("account_orders.html", orders=orders)


@app.route("/orders/<order_number>")
@login_required
def order_detail(order_number):
    order = Order.query.filter_by(order_number=order_number).first()
    if not order or order.user_id != current_user.id:
        abort(404)
    return render_template("order_detail.html", order=order)


@app.route("/orders", methods=["GET", "POST"])
def order_lookup():
    order = None
    error = ""
    if request.method == "POST":
        number = request.form.get("order_number", "").strip()
        zip_code = request.form.get("zip", "").strip()
        order = Order.query.filter_by(order_number=number).first()
        if not order or order.ship_zip != zip_code:
            order = None
            error = "We could not find an order with that number and ZIP code."
    return render_template("order_lookup.html", order=order, error=error)


@app.route("/account/dashboard/wishlist")
@login_required
def account_wishlist():
    items = (WishlistItem.query.filter_by(user_id=current_user.id)
             .order_by(WishlistItem.id).all())
    return render_template("wishlist.html", items=items)


@app.route("/account/dashboard/rewards")
@login_required
def account_rewards():
    events = (RewardEvent.query.filter_by(user_id=current_user.id)
              .order_by(RewardEvent.event_date.desc()).all())
    return render_template("account_rewards.html", events=events)


# --------------------------------------------------------------------------- #
# Bag + checkout
# --------------------------------------------------------------------------- #

@app.route("/cart")
def cart_page():
    items = get_cart_items()
    totals = cart_totals(items)
    recommended = Product.query.order_by(Product.sort).limit(6).all()
    return render_template("cart.html", items=items, totals=totals,
                           recommended=recommended)


@app.route("/cart/add", methods=["POST"])
def cart_add():
    ppid = request.form.get("ppid", "")
    product = Product.query.filter_by(ppid=ppid).first()
    if not product:
        abort(404)
    color = request.form.get("color", "")
    size = request.form.get("size", "")
    quantity = form_integer("quantity", default=1, minimum=1, maximum=10)
    if product.colors:
        selected = next((c for c in product.colors if c.color == color), None)
        if selected is None:
            abort(400, "Select an available color.")
        if selected.sizes and not any(str(s["size"]) == size and s.get("available")
                                      for s in selected.sizes):
            abort(400, "Select an available size.")
    if current_user.is_authenticated:
        existing = CartItem.query.filter_by(
            user_id=current_user.id, product_id=product.id,
            color=color, size=size).first()
        if existing:
            existing.quantity = min(existing.quantity + quantity, 20)
        else:
            db.session.add(CartItem(
                user_id=current_user.id, product_id=product.id,
                color=color, size=size, quantity=quantity))
        db.session.commit()
    else:
        rows = session.get(CART_SESSION_KEY, [])
        for row in rows:
            if row.get("product_id") == product.id and row.get("color") == color \
                    and row.get("size") == size:
                row["quantity"] = min(row.get("quantity", 1) + quantity, 20)
                break
        else:
            rows.append({
                "id": len(rows) + 1, "product_id": product.id,
                "color": color, "size": size, "quantity": quantity,
            })
        session[CART_SESSION_KEY] = rows
    flash(f"{product.name} added to your bag.")
    return redirect(url_for("cart_page"))


@app.route("/cart/update/<int:item_id>", methods=["POST"])
def cart_update(item_id):
    quantity = form_integer("quantity", default=1, minimum=1, maximum=20)
    if current_user.is_authenticated:
        item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first()
        if not item:
            abort(404)
        item.quantity = quantity
        db.session.commit()
    else:
        rows = session.get(CART_SESSION_KEY, [])
        for row in rows:
            if row.get("id") == item_id:
                row["quantity"] = quantity
        session[CART_SESSION_KEY] = rows
    return redirect(url_for("cart_page"))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
def cart_remove(item_id):
    if current_user.is_authenticated:
        item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first()
        if not item:
            abort(404)
        db.session.delete(item)
        db.session.commit()
    else:
        rows = session.get(CART_SESSION_KEY, [])
        session[CART_SESSION_KEY] = [row for row in rows if row.get("id") != item_id]
    flash("Item removed from your bag.")
    return redirect(url_for("cart_page"))


def checkout_state() -> dict[str, Any]:
    state = session.get("jcp_checkout") or {}
    session["jcp_checkout"] = state  # top-level set keeps the cookie marked dirty
    return state


def touch_checkout_state() -> None:
    """Flask only re-serializes the session cookie when a top-level key is
    (re)assigned; nested mutations alone are lost between requests."""
    session["jcp_checkout"] = session.get("jcp_checkout") or {}


def clear_checkout_state() -> None:
    session.pop("jcp_checkout", None)


@app.route("/checkout")
@login_required
def checkout():
    return redirect(url_for("checkout_shipping"))


@app.route("/checkout/shipping", methods=["GET", "POST"])
@login_required
def checkout_shipping():
    items = get_cart_items()
    if not items:
        return redirect(url_for("cart_page"))
    addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.id).all()
    if request.method == "POST":
        choice = request.form.get("address_id", "new").strip()
        if choice != "new":
            try:
                address = Address.query.filter_by(
                    id=int(choice), user_id=current_user.id).first()
            except ValueError:
                address = None
            if not address:
                flash("Please choose a shipping address.")
                return redirect(url_for("checkout_shipping"))
        else:
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            line1 = request.form.get("line1", "").strip()
            city = request.form.get("city", "").strip()
            state = request.form.get("state", "").strip().upper()
            zip_code = request.form.get("zip", "").strip()
            if not (first_name and last_name and line1 and city
                    and state in US_STATES and re.fullmatch(r"\d{5}", zip_code)):
                flash("Please complete every shipping address field.")
                return redirect(url_for("checkout_shipping"))
            address = Address(user_id=current_user.id, first_name=first_name,
                              last_name=last_name, line1=line1,
                              line2=request.form.get("line2", "").strip(),
                              city=city, state=state, zip=zip_code,
                              phone=request.form.get("phone", "").strip())
        if request.form.get("method", "standard") != "standard":
            flash("Please use standard shipping for this order.")
            return redirect(url_for("checkout_shipping"))
        state = checkout_state()
        state["shipping"] = {
            "first_name": address.first_name, "last_name": address.last_name,
            "line1": address.line1, "line2": address.line2,
            "city": address.city, "state": address.state,
            "zip": address.zip, "phone": address.phone,
            "method": request.form.get("method", "standard"),
        }
        touch_checkout_state()
        return redirect(url_for("checkout_payment"))
    return render_template("checkout_shipping.html", addresses=addresses, items=items)


@app.route("/checkout/payment", methods=["GET", "POST"])
@login_required
def checkout_payment():
    items = get_cart_items()
    if not items:
        return redirect(url_for("cart_page"))
    if "shipping" not in checkout_state():
        return redirect(url_for("checkout_shipping"))
    payments = PaymentMethod.query.filter_by(user_id=current_user.id).order_by(PaymentMethod.is_default.desc(), PaymentMethod.id).all()
    if request.method == "POST":
        choice = request.form.get("payment_choice", "new").strip()
        if choice != "new":
            try:
                payment = PaymentMethod.query.filter_by(
                    id=int(choice), user_id=current_user.id).first()
            except ValueError:
                payment = None
            if not payment:
                flash("Please choose a payment method.")
                return redirect(url_for("checkout_payment"))
            card_type, last4 = payment.card_type, payment.last4
        else:
            digits = request.form.get("card_number", "").replace(" ", "")
            if not re.fullmatch(r"\d{13,19}", digits):
                flash("Please enter a valid card number.")
                return redirect(url_for("checkout_payment"))
            exp_month = request.form.get("exp_month", type=int)
            exp_year = request.form.get("exp_year", type=int)
            if not (1 <= (exp_month or 0) <= 12) or not (2026 <= (exp_year or 0) <= 2040):
                flash("Please enter a valid expiration date.")
                return redirect(url_for("checkout_payment"))
            card_type = request.form.get("card_type", "Visa")
            last4 = digits[-4:]
        state = checkout_state()
        state["payment"] = {"card_type": card_type, "last4": last4}
        touch_checkout_state()
        return redirect(url_for("checkout_review"))
    return render_template("checkout_payment.html", payments=payments, items=items)


@app.route("/checkout/review", methods=["GET", "POST"])
@login_required
def checkout_review():
    items = get_cart_items()
    if not items:
        return redirect(url_for("cart_page"))
    state = checkout_state()
    if "shipping" not in state:
        return redirect(url_for("checkout_shipping"))
    if "payment" not in state:
        return redirect(url_for("checkout_payment"))
    totals = cart_totals(items)
    if request.method == "POST":
        coupon_code = request.form.get("coupon_code", "").strip().upper()
        coupon = Coupon.query.filter_by(code=coupon_code).first() if coupon_code else None
        subtotal = totals["subtotal"]
        if coupon and subtotal >= coupon.min_purchase:
            totals["discount"] = coupon_discount(coupon, subtotal)
            # estimated tax applies to the discounted subtotal (same convention
            # as the bag page's ?code= coupon path)
            totals["tax"] = round((subtotal - totals["discount"]) * 0.0825, 2)
            totals["total"] = round(
                subtotal - totals["discount"] + totals["shipping"] + totals["tax"], 2)
        elif coupon:
            flash(f"Coupon {coupon_code} requires a minimum purchase of "
                  f"${coupon.min_purchase:.0f}.")
            return redirect(url_for("checkout_review"))
        if coupon_code and not coupon:
            flash("That coupon code is not recognized. Please correct it or leave it blank.")
            return redirect(url_for("checkout_review"))
        shipping = state["shipping"]
        payment = state["payment"]
        # Sequence avoids collisions when two checkouts occur in the same second.
        order_number = f"JCP{(db.session.query(db.func.max(Order.id)).scalar() or 0) + 1:06d}{current_user.id:03d}"
        order = Order(
            order_number=order_number,
            user_id=current_user.id,
            email=current_user.email,
            status="Processing",
            placed_at=datetime.utcnow(),
            subtotal=totals["subtotal"],
            discount=totals["discount"],
            shipping=totals["shipping"],
            tax=totals["tax"],
            total=totals["total"],
            coupon_code=coupon.code if coupon else "",
            ship_name=f"{shipping['first_name']} {shipping['last_name']}",
            ship_address=shipping["line1"] + (f", {shipping['line2']}" if shipping.get("line2") else ""),
            ship_city=shipping["city"], ship_state=shipping["state"],
            ship_zip=shipping["zip"], ship_phone=shipping.get("phone", ""),
            payment_type=payment["card_type"], payment_last4=payment["last4"],
            gift_message=request.form.get("gift_message", "").strip()[:280],
        )
        for item in items:
            order.items.append(OrderItem(
                product_id=item.product_id,
                product_name=item.product.name,
                brand=item.product.brand,
                color=item.color, size=item.size,
                quantity=item.quantity,
                unit_price=item.product.price,
                image_file=item.product.primary_image,
            ))
        db.session.add(order)
        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        clear_checkout_state()
        session["jcp_last_order"] = order.order_number
        return redirect(url_for("checkout_confirmation", order_number=order.order_number))
    return render_template("checkout_review.html", items=items,
                           totals=totals, shipping=state["shipping"],
                           payment=state["payment"])


@app.route("/checkout/confirmation/<order_number>")
@login_required
def checkout_confirmation(order_number):
    if session.get("jcp_last_order") != order_number:
        abort(404)
    order = Order.query.filter_by(order_number=order_number,
                                  user_id=current_user.id).first()
    if not order:
        abort(404)
    return render_template("checkout_confirmation.html", order=order)


# --------------------------------------------------------------------------- #
# Wishlist
# --------------------------------------------------------------------------- #

@app.route("/wishlist/toggle/<ppid>", methods=["POST"])
def wishlist_toggle(ppid):
    product = Product.query.filter_by(ppid=ppid).first()
    if not product:
        abort(404)
    if current_user.is_authenticated:
        item = WishlistItem.query.filter_by(
            user_id=current_user.id, product_id=product.id).first()
        if item:
            db.session.delete(item)
            db.session.commit()
            flash("Removed from your wish list.")
        else:
            db.session.add(WishlistItem(user_id=current_user.id, product_id=product.id))
            db.session.commit()
            flash("Saved to your wish list.")
    else:
        rows = session.get(WISHLIST_SESSION_KEY, [])
        if any(row.get("product_id") == product.id for row in rows):
            rows = [row for row in rows if row.get("product_id") != product.id]
            flash("Removed from your wish list.")
        else:
            rows.append({"id": len(rows) + 1, "product_id": product.id})
            flash("Saved to your wish list.")
        session[WISHLIST_SESSION_KEY] = rows
    target = request.form.get("next") or request.referrer
    if target and target.startswith("/"):
        return redirect(target)
    if target and request.host_url in target:
        return redirect(target)
    return redirect(url_for("product_page", slug=product.slug, ppid=product.ppid))


# --------------------------------------------------------------------------- #
# Stores
# --------------------------------------------------------------------------- #

@app.route("/stores")
def stores_page():
    query = request.args.get("q", "").strip().lower()
    state_filter = request.args.get("state", "").strip().upper()
    service = request.args.get("service", "").strip()
    stores = Store.query.order_by(Store.state, Store.city, Store.number)
    if state_filter:
        stores = stores.filter(Store.state == state_filter)
    if service:
        stores = stores.filter(Store.services_json.contains(service))
    results = stores.all()
    if query:
        results = [s for s in results if query in (
            f"{s.city} {s.state} {s.zip} {s.mall} {s.street}").lower()]
    state_counts: dict[str, int] = {}
    for store in Store.query.all():
        state_counts[store.state] = state_counts.get(store.state, 0) + 1
    return render_template(
        "stores.html",
        stores=results[:60],
        total=Store.query.count(),
        state_counts=state_counts,
        state_filter=state_filter,
        query=query,
        service=service,
    )


@app.route("/stores/<int:number>")
def store_page(number):
    store = Store.query.filter_by(number=number).first()
    if not store:
        abort(404)
    return render_template("store_detail.html", store=store)


# --------------------------------------------------------------------------- #
# Coupons / Rewards / Gift cards / Customer service
# --------------------------------------------------------------------------- #

@app.route("/m/jcpenney-coupons")
def coupons_page():
    coupons = Coupon.query.order_by(Coupon.id).all()
    return render_template("coupons.html", coupons=coupons)


@app.route("/rewards")
def rewards_page():
    member = None
    events = []
    if current_user.is_authenticated:
        member = current_user
        events = (RewardEvent.query.filter_by(user_id=current_user.id)
                  .order_by(RewardEvent.event_date.desc()).limit(10).all())
    return render_template("rewards.html", member=member, events=events)


@app.route("/gift-cards", methods=["GET", "POST"])
def giftcards_page():
    balance = None
    number = ""
    if request.method == "POST":
        number = request.form.get("card_number", "").strip()
        if re.fullmatch(r"[\d\s]{16,25}", number):
            digits = number.replace(" ", "")
            # Deterministic demo balance derived from the card number itself so
            # repeated checks of the same card always agree.
            balance = round(float(f"0.{digits[-2:]}") * 100, 2)
        else:
            flash("Please enter a valid gift card number.")
    return render_template("giftcards.html", balance=balance, number=number)


@app.route("/m/customer-service")
def customer_service_page():
    return render_template("customer_service.html")


@app.route("/m/customer-service/<slug>")
def customer_service_article(slug):
    page = StaticPage.query.filter_by(slug=f"customer-service/{slug}").first()
    if not page:
        abort(404)
    return render_template("static_page.html", page=page)


@app.route("/m/curbside-pickup")
def curbside_pickup_page():
    page = StaticPage.query.filter_by(slug="curbside-pickup").first()
    if not page:
        abort(404)
    return render_template("static_page.html", page=page)


@app.route("/health")
@app.route("/_health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"ok": db_ok, "site": SITE_SLUG, "products": Product.query.count(),
            "stores": Store.query.count()}


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #

def create_schema() -> None:
    """Create tables + indexes deterministically.

    SQLAlchemy iterates a table's indexes from a set keyed by object identity,
    so `db.create_all()` emits CREATE INDEX statements in an order that changes
    between processes and reshuffles the SQLite page allocation. Detach the
    indexes, create the tables, then create every index in a stable
    (table name, index name) order so the seed DB is byte-reproducible.
    """
    detached: list[tuple[str, object]] = []
    for table in db.metadata.sorted_tables:
        for index in list(table.indexes):
            detached.append((table.name, index))
            table.indexes.discard(index)
    try:
        db.create_all()
        from sqlalchemy import inspect
        from sqlalchemy.schema import CreateIndex
        inspector = inspect(db.engine)
        existing = {
            (table_name, index["name"])
            for table_name in inspector.get_table_names()
            for index in inspector.get_indexes(table_name)
        }
        with db.engine.begin() as connection:
            for table_name, index in sorted(detached, key=lambda pair: (pair[0], pair[1].name)):
                if (table_name, index.name) not in existing:
                    connection.execute(CreateIndex(index))
    finally:
        for table_name, index in detached:
            table = db.metadata.tables[table_name]
            if index not in table.indexes:
                table.indexes.add(index)


BOOTSTRAP = os.environ.get("WEBSYN_SKIP_BOOTSTRAP") != "1"

if BOOTSTRAP:
    with app.app_context():
        create_schema()
        try:
            from seed_data import seed_database, seed_benchmark_users
            seed_database()
            seed_benchmark_users()
        except ImportError:
            pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 43073))
    app.run(host="0.0.0.0", port=port, debug=False)
