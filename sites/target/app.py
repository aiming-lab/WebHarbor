"""Target demo mirror for WebHarbor."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

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
from sqlalchemy import or_


SITE_SLUG = "target"
SITE_NAME = "Target"
SITE_PORT = 40016
BENCHMARK_PASSWORD = "TestPass123!"
BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
SEED_DIR = BASE_DIR / "instance_seed"
STATIC_DIR = BASE_DIR / "static"
IMAGE_DIR = STATIC_DIR / "images"
RUNTIME_DB_PATH = INSTANCE_DIR / "target.db"
SEED_DB_PATH = SEED_DIR / "target.db"
PASSWORD_NAMESPACE = "target-webharbor-demo"


def _ensure_dirs() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


_ensure_dirs()


app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config["SECRET_KEY"] = "target-demo-session-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{RUNTIME_DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in with a benchmark account to use carts, orders, and rewards."


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
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    return "".join(cleaned).strip("-")


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class User(db.Model, UserMixin, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(64), nullable=False)
    phone = db.Column(db.String(32), default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(40), default="")
    preferred_store_slug = db.Column(db.String(80), default="")
    member_tier = db.Column(db.String(32), default="Target Circle 360")
    rewards_member_id = db.Column(db.String(40), default="")

    cart_items = db.relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="user", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", back_populates="user", cascade="all, delete-orphan")
    compare_items = db.relationship("CompareItem", back_populates="user", cascade="all, delete-orphan")
    support_tickets = db.relationship("SupportTicket", back_populates="user", cascade="all, delete-orphan")
    reward_account = db.relationship("RewardAccount", back_populates="user", uselist=False, cascade="all, delete-orphan")
    reward_activities = db.relationship("RewardActivity", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, raw_password: str) -> None:
        self.password_hash = stable_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return self.password_hash == stable_password_hash(raw_password)


class Brand(db.Model):
    __tablename__ = "brands"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    accent_color = db.Column(db.String(16), default="#cc0000")  # Target red

    products = db.relationship("Product", back_populates="brand")


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    section = db.Column(db.String(80), default="")
    description = db.Column(db.Text, default="")
    hero_title = db.Column(db.String(160), default="")
    image_path = db.Column(db.String(255), default="")

    products = db.relationship("Product", back_populates="category")


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(24), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    short_description = db.Column(db.Text, default="")
    long_description = db.Column(db.Text, default="")
    price = db.Column(db.Float, nullable=False)
    list_price = db.Column(db.Float, nullable=False, default=0.0)
    rating = db.Column(db.Float, default=4.5)
    review_count = db.Column(db.Integer, default=0)
    # Real per-attribute guest ratings (comfort, quality, value, ...) and the
    # "% would recommend" figure, both scraped from the live PDP. They only
    # appear on the detail page, never on a search card.
    secondary_ratings_json = db.Column(db.Text, default="{}")
    percent_recommended = db.Column(db.Integer)
    availability_status = db.Column(db.String(40), default="In stock")
    pickup_eligible = db.Column(db.Boolean, default=True)
    delivery_eligible = db.Column(db.Boolean, default=True)
    featured = db.Column(db.Boolean, default=False)
    deal_badge = db.Column(db.String(80), default="")
    image_path = db.Column(db.String(255), default="")
    highlights_json = db.Column(db.Text, default="[]")
    specs_json = db.Column(db.Text, default="[]")
    tags_json = db.Column(db.Text, default="[]")
    search_keywords = db.Column(db.Text, default="")
    stock_count = db.Column(db.Integer, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=False)

    category = db.relationship("Category", back_populates="products")
    brand = db.relationship("Brand", back_populates="products")
    reviews = db.relationship("Review", back_populates="product", cascade="all, delete-orphan")
    inventory_rows = db.relationship("StoreInventory", back_populates="product", cascade="all, delete-orphan")
    cart_items = db.relationship("CartItem", back_populates="product", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", back_populates="product", cascade="all, delete-orphan")
    compare_items = db.relationship("CompareItem", back_populates="product", cascade="all, delete-orphan")
    protection_plans = db.relationship("ProtectionPlan", back_populates="product", cascade="all, delete-orphan")
    order_items = db.relationship("OrderItem", back_populates="product")
    deals = db.relationship("Deal", back_populates="product")

    def highlights(self) -> list[str]:
        return load_json(self.highlights_json, [])

    def specs(self) -> list[dict[str, Any]]:
        return load_json(self.specs_json, [])

    def tags(self) -> list[str]:
        return load_json(self.tags_json, [])

    def secondary_ratings(self) -> dict[str, float]:
        return load_json(self.secondary_ratings_json, {})

    def discount_percent(self) -> int:
        if self.list_price > self.price > 0:
            return int(round((self.list_price - self.price) / self.list_price * 100))
        return 0

    def support_search_blob(self) -> str:
        parts = [self.name, self.short_description, self.long_description, self.search_keywords]
        parts.extend(self.tags())
        parts.extend(self.highlights())
        return " ".join(part for part in parts if part).lower()


class Store(db.Model):
    __tablename__ = "stores"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(40), nullable=False)
    address = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(24), default="")
    hours_json = db.Column(db.Text, default="[]")
    amenities_json = db.Column(db.Text, default="[]")
    services_json = db.Column(db.Text, default="[]")
    hero_copy = db.Column(db.Text, default="")
    image_path = db.Column(db.String(255), default="")

    inventory_rows = db.relationship("StoreInventory", back_populates="store", cascade="all, delete-orphan")
    pickup_slots = db.relationship("PickupSlot", back_populates="store", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="store")

    def hours(self) -> list[str]:
        return load_json(self.hours_json, [])

    def amenities(self) -> list[str]:
        return load_json(self.amenities_json, [])

    def services(self) -> list[str]:
        return load_json(self.services_json, [])


class StoreInventory(db.Model):
    __tablename__ = "store_inventory"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    pickup_window = db.Column(db.String(120), default="")
    aisle = db.Column(db.String(40), default="")

    store = db.relationship("Store", back_populates="inventory_rows")
    product = db.relationship("Product", back_populates="inventory_rows")


class Review(db.Model, TimestampMixin):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    author_name = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    body = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    verified = db.Column(db.Boolean, default=True)

    product = db.relationship("Product", back_populates="reviews")


class CartItem(db.Model, TimestampMixin):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    fulfillment_method = db.Column(db.String(24), default="delivery")
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"))
    delivery_option_id = db.Column(db.Integer, db.ForeignKey("delivery_options.id"))
    protection_plan_id = db.Column(db.Integer, db.ForeignKey("protection_plans.id"))

    user = db.relationship("User", back_populates="cart_items")
    product = db.relationship("Product", back_populates="cart_items")
    store = db.relationship("Store")
    delivery_option = db.relationship("DeliveryOption")
    protection_plan = db.relationship("ProtectionPlan")


class WishlistItem(db.Model, TimestampMixin):
    __tablename__ = "wishlist_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    user = db.relationship("User", back_populates="wishlist_items")
    product = db.relationship("Product", back_populates="wishlist_items")


class CompareItem(db.Model, TimestampMixin):
    __tablename__ = "compare_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    user = db.relationship("User", back_populates="compare_items")
    product = db.relationship("Product", back_populates="compare_items")


class ProtectionPlan(db.Model):
    __tablename__ = "protection_plans"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    years = db.Column(db.Integer, default=2)
    price = db.Column(db.Float, nullable=False)
    coverage_summary = db.Column(db.Text, default="")
    accidental = db.Column(db.Boolean, default=False)
    priority_support = db.Column(db.Boolean, default=True)

    product = db.relationship("Product", back_populates="protection_plans")


class SupportArticle(db.Model):
    __tablename__ = "support_articles"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    topic = db.Column(db.String(80), default="")
    summary = db.Column(db.Text, default="")
    body = db.Column(db.Text, default="")
    upstream_url = db.Column(db.String(255), default="")
    keywords_json = db.Column(db.Text, default="[]")

    def keywords(self) -> list[str]:
        return load_json(self.keywords_json, [])


class SupportTicket(db.Model, TimestampMixin):
    __tablename__ = "support_tickets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject = db.Column(db.String(180), nullable=False)
    status = db.Column(db.String(40), default="Resolved")
    channel = db.Column(db.String(40), default="Chat")
    summary = db.Column(db.Text, default="")

    user = db.relationship("User", back_populates="support_tickets")


class Deal(db.Model):
    __tablename__ = "deals"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    subtitle = db.Column(db.Text, default="")
    badge = db.Column(db.String(80), default="Member Deal")
    discount_percent = db.Column(db.Integer, default=0)
    ends_label = db.Column(db.String(80), default="")
    category_slug = db.Column(db.String(80), default="")
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))

    product = db.relationship("Product", back_populates="deals")


class RewardAccount(db.Model):
    __tablename__ = "reward_accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    member_id = db.Column(db.String(40), nullable=False)
    points_balance = db.Column(db.Integer, default=0)
    tier = db.Column(db.String(40), default="Target Circle 360")
    available_certificates = db.Column(db.Integer, default=0)

    user = db.relationship("User", back_populates="reward_account")


class RewardActivity(db.Model):
    __tablename__ = "reward_activities"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    points_delta = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(140), nullable=False)
    note = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="reward_activities")


class DeliveryOption(db.Model):
    __tablename__ = "delivery_options"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    fee = db.Column(db.Float, default=0.0)
    eta_label = db.Column(db.String(120), default="")


class PickupSlot(db.Model):
    __tablename__ = "pickup_slots"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    slot_code = db.Column(db.String(40), unique=True, nullable=False)
    day_label = db.Column(db.String(80), nullable=False)
    time_window = db.Column(db.String(80), nullable=False)
    available_capacity = db.Column(db.Integer, default=0)

    store = db.relationship("Store", back_populates="pickup_slots")


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    order_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(60), default="Preparing")
    subtotal = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    fulfillment_method = db.Column(db.String(32), default="delivery")
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"))
    delivery_option_id = db.Column(db.Integer, db.ForeignKey("delivery_options.id"))
    shipping_name = db.Column(db.String(120), default="")
    shipping_street = db.Column(db.String(160), default="")
    shipping_city = db.Column(db.String(80), default="")
    shipping_state = db.Column(db.String(40), default="")
    shipping_zip = db.Column(db.String(20), default="")
    payment_brand = db.Column(db.String(40), default="Demo Visa")
    payment_last4 = db.Column(db.String(4), default="1111")
    confirmation_note = db.Column(db.Text, default="")
    pickup_slot_label = db.Column(db.String(120), default="")
    placed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="orders")
    store = db.relationship("Store", back_populates="orders")
    delivery_option = db.relationship("DeliveryOption")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = db.relationship("PaymentMock", back_populates="order", uselist=False, cascade="all, delete-orphan")

    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    item_name = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0.0)
    protection_plan_name = db.Column(db.String(140), default="")

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")


class PaymentMock(db.Model):
    __tablename__ = "payment_mocks"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    card_label = db.Column(db.String(80), default="Demo Visa")
    auth_status = db.Column(db.String(40), default="Approved")
    approval_code = db.Column(db.String(20), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    order = db.relationship("Order", back_populates="payment")


class SearchLog(db.Model):
    __tablename__ = "search_logs"

    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(255), nullable=False)
    scope = db.Column(db.String(40), default="products")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    result_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


@app.template_filter("currency")
def currency_filter(value: float) -> str:
    return f"${value:,.2f}"


@app.template_filter("stars")
def star_filter(value: float) -> str:
    return f"{value:.1f}"


@app.template_filter("paragraphs")
def paragraphs_filter(value: str) -> list[str]:
    return [chunk.strip() for chunk in value.split("\n") if chunk.strip()]


# Order of the mega-menu's top level, mirroring target.com's own ordering.
# Sections not listed here fall to the end, alphabetically.
SECTION_ORDER = [
    "Clothing, Shoes & Accessories",
    "Home & Decor",
    "Kitchen & Dining",
    "Grocery",
    "Household Essentials",
    "Baby",
    "Beauty & Personal Care",
    "Toys & Video Games",
    "Sports & Outdoors",
    "Electronics",
    "Pets",
]


def nav_categories() -> list[Category]:
    return Category.query.order_by(Category.name.asc()).limit(8).all()


def nav_sections() -> list[tuple[str, list[Category]]]:
    """Departments grouped under their mega-menu section.

    target.com nests departments two levels deep (Clothing, Shoes &
    Accessories > Women's Clothing), so a flat department list would
    misrepresent the real navigation.
    """
    grouped: dict[str, list[Category]] = {}
    for category in Category.query.order_by(Category.name.asc()).all():
        grouped.setdefault(category.section, []).append(category)

    def rank(section: str) -> tuple[int, str]:
        try:
            return (SECTION_ORDER.index(section), "")
        except ValueError:
            return (len(SECTION_ORDER), section)

    return [(name, grouped[name]) for name in sorted(grouped, key=rank)]


def get_preferred_store() -> Store | None:
    if current_user.is_authenticated and current_user.preferred_store_slug:
        return Store.query.filter_by(slug=current_user.preferred_store_slug).first()
    return Store.query.order_by(Store.city.asc()).first()


def get_compare_products() -> list[Product]:
    if current_user.is_authenticated:
        return [item.product for item in current_user.compare_items[:4]]
    compare_skus = session.get("compare_skus", [])
    if not compare_skus:
        return []
    products = Product.query.filter(Product.sku.in_(compare_skus[:4])).all()
    order = {sku: index for index, sku in enumerate(compare_skus[:4])}
    return sorted(products, key=lambda product: order.get(product.sku, 999))


def get_cart_items() -> list[CartItem]:
    if not current_user.is_authenticated:
        return []
    return (
        CartItem.query.filter_by(user_id=current_user.id)
        .order_by(CartItem.created_at.desc())
        .all()
    )


def cart_totals(cart_items: list[CartItem]) -> dict[str, float]:
    subtotal = 0.0
    for item in cart_items:
        plan_price = item.protection_plan.price if item.protection_plan else 0.0
        subtotal += (item.product.price + plan_price) * item.quantity
    return {"subtotal": round(subtotal, 2), "count": sum(item.quantity for item in cart_items)}


def pickup_windows() -> list[str]:
    """The distinct pickup windows, e.g. "Tomorrow 9:00 AM - 11:00 AM".

    Every store keeps its own PickupSlot rows but they all offer the same
    times, so the picker shows each window once instead of once per store.
    Ordered so Today's slots come before Tomorrow's.
    """
    seen: list[str] = []
    for slot in PickupSlot.query.order_by(PickupSlot.id.asc()).all():
        label = f"{slot.day_label} {slot.time_window}"
        if label not in seen:
            seen.append(label)
    return sorted(seen, key=lambda w: (0 if w.startswith("Today") else 1, w))


def resolve_pickup_slot(store_id: int, window: str) -> "PickupSlot | None":
    """Map a shared window label back to that store's own slot row."""
    for slot in PickupSlot.query.filter_by(store_id=store_id).all():
        if f"{slot.day_label} {slot.time_window}" == window:
            return slot
    return None


def get_checkout_state() -> dict[str, Any]:
    checkout = session.get("target_checkout", {})
    if not isinstance(checkout, dict):
        checkout = {}
    return checkout


def save_checkout_state(checkout: dict[str, Any]) -> None:
    session["target_checkout"] = checkout
    session.modified = True


def clear_checkout_state() -> None:
    session.pop("target_checkout", None)
    session.modified = True


def merge_compare_session_into_user() -> None:
    compare_skus = session.pop("compare_skus", [])
    if not compare_skus or not current_user.is_authenticated:
        return
    existing = {item.product.sku for item in current_user.compare_items}
    for sku in compare_skus[:4]:
        if sku in existing:
            continue
        product = Product.query.filter_by(sku=sku).first()
        if product:
            db.session.add(CompareItem(user_id=current_user.id, product_id=product.id))
    db.session.commit()


@app.context_processor
def inject_global_context() -> dict[str, Any]:
    cart_items = get_cart_items()
    compare_products = get_compare_products()
    reward_points = 0
    if current_user.is_authenticated and current_user.reward_account:
        reward_points = current_user.reward_account.points_balance
    return {
        "site_name": SITE_NAME,
        "benchmark_password": BENCHMARK_PASSWORD,
        "nav_categories": nav_categories(),
        "nav_sections": nav_sections(),
        "cart_item_count": cart_totals(cart_items)["count"],
        "compare_count": len(compare_products),
        "preferred_store": get_preferred_store(),
        "reward_points": reward_points,
    }


def log_search(query: str, scope: str, result_count: int) -> None:
    if not query:
        return
    db.session.add(
        SearchLog(
            query=query,
            scope=scope,
            user_id=current_user.id if current_user.is_authenticated else None,
            result_count=result_count,
        )
    )
    db.session.commit()


def search_tokens(q: str) -> list[str]:
    """Split a query into lowercase tokens (drops 1-char noise)."""
    return [t for t in re.split(r"[^a-z0-9]+", q.lower()) if len(t) > 1]


def token_match(tokens: list[str]):
    """Token-overlap search per the WebHarbor guide: scored relevance, NOT strict AND.

    Returns (filter_condition, score_expression). A product qualifies when ANY
    token matches (score > 0); the score counts how many tokens matched so the
    best overlaps rank first. This is what makes multi-word queries like
    "dell laptop" or "sony headphones" work instead of returning nothing.
    """
    conds, score_terms = [], []
    for tok in tokens:
        like = f"%{tok}%"
        cond = or_(
            db.func.lower(Product.name).like(like),
            db.func.lower(Product.search_keywords).like(like),
            db.func.lower(Brand.name).like(like),
            db.func.lower(Category.name).like(like),
        )
        conds.append(cond)
        score_terms.append(db.case((cond, 1), else_=0))
    score = score_terms[0]
    for extra in score_terms[1:]:
        score = score + extra
    return or_(*conds), score


PRODUCTS_PER_PAGE = 24
CART_MAX_QTY = 5


def paginate_products(products_query):
    """Page a product listing the way target.com does — 24 tiles per page.

    The catalog holds ~1.3k products, so rendering a listing unpaged produced a
    single multi-megabyte page that no agent could work with.
    """
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    return products_query.paginate(page=page, per_page=PRODUCTS_PER_PAGE, error_out=False)


def apply_product_filters(query, exclude: str | None = None):
    """Apply the facet rail (brand / price / rating / fulfilment) to a query.

    `exclude` skips one facet, which is how each facet's own option list is
    built — see facet_options(). Split out of product_query_from_filters so
    /search can offer the same facets a department listing does.
    """
    category_slug = request.args.get("category", "").strip()
    if category_slug and exclude != "category":
        query = query.filter(Category.slug == category_slug)

    brand_slug = "" if exclude == "brand" else request.args.get("brand", "").strip()
    if brand_slug:
        query = query.filter(Brand.slug == brand_slug)

    try:
        min_price = float(request.args.get("min_price", "") or 0)
        if min_price:
            query = query.filter(Product.price >= min_price)
    except ValueError:
        min_price = None

    try:
        max_price = float(request.args.get("max_price", "") or 0)
        if max_price:
            query = query.filter(Product.price <= max_price)
    except ValueError:
        max_price = None

    rating_filter = request.args.get("rating", "").strip()
    if rating_filter:
        try:
            rating_value = float(rating_filter)
            query = query.filter(Product.rating >= rating_value)
        except ValueError:
            pass

    availability = request.args.get("availability", "").strip()
    if availability == "in-stock":
        query = query.filter(Product.stock_count > 0)
    elif availability == "pickup":
        query = query.filter(Product.pickup_eligible.is_(True))

    if request.args.get("pickup") == "1":
        query = query.filter(Product.pickup_eligible.is_(True))
    if request.args.get("delivery") == "1":
        query = query.filter(Product.delivery_eligible.is_(True))
    # target.com's rail carries a "Deals" facet; ours is derived from the real
    # list_price > price data rather than a flag.
    if request.args.get("deals") == "1":
        query = query.filter(Product.list_price > Product.price)

    return query


def facet_options(model, search_cond, exclude: str):
    """Distinct `model` rows still reachable once every facet EXCEPT `exclude`
    is applied to the current search.

    Returning options that would yield zero results is the bug this exists to
    prevent: with the brand list built from the unfiltered match set, picking
    Furniture still offered Ninja, and that pair matches nothing.
    """
    reachable = Product.query.join(Brand).join(Category).filter(search_cond)
    reachable = apply_product_filters(reachable, exclude=exclude)
    return (model.query.join(Product)
            .filter(Product.id.in_(reachable.with_entities(Product.id)))
            .order_by(model.name.asc()).distinct().all())


def apply_product_sort(query, sort: str):
    if sort == "price-asc":
        return query.order_by(Product.price.asc(), Product.rating.desc())
    if sort == "price-desc":
        return query.order_by(Product.price.desc(), Product.rating.desc())
    if sort == "rating":
        return query.order_by(Product.rating.desc(), Product.review_count.desc())
    if sort == "newest":
        return query.order_by(Product.id.desc())
    return query.order_by(Product.featured.desc(), Product.rating.desc(),
                          Product.review_count.desc())


def product_query_from_filters(category_slug: str | None = None):
    query = Product.query.join(Brand).join(Category)
    if category_slug:
        query = query.filter(Category.slug == category_slug)

    q = request.args.get("q", "").strip()
    if q:
        tokens = search_tokens(q)
        if tokens:
            cond, score = token_match(tokens)
            query = query.filter(cond).order_by(score.desc())

    query = apply_product_filters(query)
    query = apply_product_sort(query, request.args.get("sort", "featured"))
    return query, q


def order_accessible(order: Order) -> bool:
    if current_user.is_authenticated and order.user_id == current_user.id:
        return True
    return session.get("target_lookup_order") == order.order_number


def build_checkout_summary(cart_items: list[CartItem], checkout: dict[str, Any]) -> dict[str, Any]:
    totals = cart_totals(cart_items)
    subtotal = totals["subtotal"]
    mode = checkout.get("mode", "delivery")
    delivery_option = None
    store = None
    pickup_slot = None
    shipping_fee = 0.0

    if mode == "pickup":
        if checkout.get("store_id"):
            store = db.session.get(Store, int(checkout["store_id"]))
        if checkout.get("slot_id"):
            pickup_slot = db.session.get(PickupSlot, int(checkout["slot_id"]))
    else:
        mode = "delivery"
        if checkout.get("delivery_option_id"):
            delivery_option = db.session.get(DeliveryOption, int(checkout["delivery_option_id"]))
            shipping_fee = delivery_option.fee if delivery_option else 0.0

    tax = round((subtotal + shipping_fee) * 0.086, 2)
    total = round(subtotal + shipping_fee + tax, 2)

    return {
        "subtotal": subtotal,
        "shipping_fee": shipping_fee,
        "tax": tax,
        "total": total,
        "mode": mode,
        "delivery_option": delivery_option,
        "store": store,
        "pickup_slot": pickup_slot,
    }


def require_cart_items() -> list[CartItem]:
    cart_items = get_cart_items()
    if not cart_items:
        flash("Your cart is empty. Add a demo product before checkout.", "warning")
        raise RuntimeError("empty-cart")
    return cart_items


@app.route("/")
@app.route("/home")
def home():
    featured_products = Product.query.filter_by(featured=True).order_by(Product.rating.desc()).limit(8).all()
    deal_cards = Deal.query.order_by(Deal.discount_percent.desc(), Deal.title.asc()).limit(6).all()
    stores = Store.query.order_by(Store.city.asc()).limit(4).all()
    support_articles = SupportArticle.query.order_by(SupportArticle.id.asc()).limit(4).all()
    return render_template(
        "home.html",
        featured_products=featured_products,
        deal_cards=deal_cards,
        stores=stores,
        support_articles=support_articles,
        categories=Category.query.order_by(Category.name.asc()).all(),
    )


@app.route("/categories")
def categories_page():
    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template("categories.html", categories=categories)


@app.route("/category/<category_slug>")
def category_page(category_slug: str):
    category = Category.query.filter_by(slug=category_slug).first_or_404()
    products_query, q = product_query_from_filters(category_slug)
    pagination = paginate_products(products_query)
    brands = Brand.query.join(Product).filter(Product.category_id == category.id).order_by(Brand.name.asc()).distinct().all()
    return render_template(
        "products.html",
        page_title=category.name,
        page_description=category.description,
        category=category,
        products=pagination.items,
        pagination=pagination,
        brands=brands,
        active_query=q,
    )


@app.route("/products")
def products_page():
    products_query, q = product_query_from_filters()
    pagination = paginate_products(products_query)
    log_search(q, "products", pagination.total)
    return render_template(
        "products.html",
        page_title="Shop all products",
        page_description="Synthetic products, deterministic stock, and fully local browsing for benchmark tasks.",
        category=None,
        products=pagination.items,
        pagination=pagination,
        brands=Brand.query.order_by(Brand.name.asc()).all(),
        active_query=q,
    )


@app.route("/product/<sku>")
def product_page(sku: str):
    product = Product.query.filter_by(sku=sku).first_or_404()
    inventory_rows = (
        StoreInventory.query.filter_by(product_id=product.id)
        .join(Store)
        .order_by(StoreInventory.quantity.desc(), Store.city.asc())
        .limit(6)
        .all()
    )
    related_products = (
        Product.query.filter(
            Product.category_id == product.category_id,
            Product.id != product.id,
        )
        .order_by(Product.rating.desc(), Product.review_count.desc())
        .limit(4)
        .all()
    )
    compare_skus = {item.sku for item in get_compare_products()}
    wishlist_product_ids = set()
    if current_user.is_authenticated:
        wishlist_product_ids = {item.product_id for item in current_user.wishlist_items}
    return render_template(
        "product_detail.html",
        product=product,
        inventory_rows=inventory_rows,
        related_products=related_products,
        compare_skus=compare_skus,
        wishlist_product_ids=wishlist_product_ids,
    )


@app.route("/compare")
def compare_page():
    products = get_compare_products()
    spec_rows: list[tuple[str, list[str]]] = []
    if products:
        labels: list[str] = []
        for product in products:
            for section in product.specs():
                for spec in section.get("items", []):
                    label = spec.get("label", "")
                    if label and label not in labels:
                        labels.append(label)
        for label in labels:
            values = []
            for product in products:
                value = "-"
                for section in product.specs():
                    for spec in section.get("items", []):
                        if spec.get("label") == label:
                            value = spec.get("value", "-")
                values.append(value)
            # A row only one product can fill is not a comparison — it is a
            # column of dashes. Comparing a cookware set against three TVs
            # produced ~30 such rows and buried the handful that mattered.
            if sum(1 for v in values if v != "-") >= 2:
                spec_rows.append((label, values))

        # Protection plans are a real, scraped, per-product attribute and the
        # thing shoppers most often weigh between similar items — but they live
        # on their own table, so the spec loop above never sees them.
        plan_labels: list[str] = []
        for product in products:
            for plan in sorted(product.protection_plans, key=lambda p: p.years):
                if plan.name not in plan_labels:
                    plan_labels.append(plan.name)
        for plan_label in plan_labels:
            values = []
            for product in products:
                match = next((p for p in product.protection_plans
                              if p.name == plan_label), None)
                values.append(f"${match.price:.2f}" if match else "-")
            if sum(1 for v in values if v != "-") >= 2:
                spec_rows.append((plan_label, values))

    # Products from different departments legitimately share almost nothing;
    # say so instead of rendering an empty table.
    compared_categories = sorted({p.category.name for p in products})
    return render_template("compare.html", products=products, spec_rows=spec_rows,
                           compared_categories=compared_categories)


@app.route("/deals")
def deals_page():
    deals = Deal.query.order_by(Deal.discount_percent.desc(), Deal.title.asc()).all()
    return render_template("deals.html", deals=deals)


@app.route("/stores")
def stores_page():
    q = request.args.get("q", "").strip().lower()
    query = Store.query
    if q:
        q_like = f"%{q}%"
        query = query.filter(
            or_(
                db.func.lower(Store.name).like(q_like),
                db.func.lower(Store.city).like(q_like),
                db.func.lower(Store.state).like(q_like),
                db.func.lower(Store.address).like(q_like),
            )
        )
    stores = query.order_by(Store.state.asc(), Store.city.asc()).all()
    return render_template("stores.html", stores=stores, active_query=q)


@app.route("/stores/<store_slug>")
def store_page(store_slug: str):
    store = Store.query.filter_by(slug=store_slug).first_or_404()
    inventory_rows = (
        StoreInventory.query.filter_by(store_id=store.id)
        .join(Product)
        .order_by(StoreInventory.quantity.desc(), Product.rating.desc())
        .limit(10)
        .all()
    )
    return render_template("store_detail.html", store=store, inventory_rows=inventory_rows)


@app.route("/support")
@app.route("/help")
def support_page():
    q = request.args.get("q", "").strip().lower()
    topic = request.args.get("topic", "").strip()
    query = SupportArticle.query
    if q:
        q_like = f"%{q}%"
        query = query.filter(
            or_(
                db.func.lower(SupportArticle.title).like(q_like),
                db.func.lower(SupportArticle.summary).like(q_like),
                db.func.lower(SupportArticle.body).like(q_like),
                db.func.lower(SupportArticle.keywords_json).like(q_like),
            )
        )
    if topic:
        query = query.filter(SupportArticle.topic == topic)
    articles = query.order_by(SupportArticle.title.asc()).all()
    if q:
        log_search(q, "support", len(articles))
    topics = sorted({article.topic for article in SupportArticle.query.all()})
    return render_template("support.html", articles=articles, active_query=q, topics=topics, active_topic=topic)


@app.route("/support/<article_slug>")
def support_article_page(article_slug: str):
    article = SupportArticle.query.filter_by(slug=article_slug).first_or_404()
    related_articles = (
        SupportArticle.query.filter(
            SupportArticle.topic == article.topic,
            SupportArticle.id != article.id,
        )
        .order_by(SupportArticle.title.asc())
        .limit(4)
        .all()
    )
    return render_template("support_article.html", article=article, related_articles=related_articles)


@app.route("/search")
def search_page():
    q = request.args.get("q", "").strip()
    product_results = []
    store_results = []
    article_results = []
    pagination = None
    facet_brands: list[Brand] = []
    facet_categories: list[Category] = []
    if q:
        q_like = f"%{q.lower()}%"
        tokens = search_tokens(q)
        if tokens:
            cond, score = token_match(tokens)
            # Same filter surface as a department listing — target.com's search
            # results carry a facet rail, and without one a query can only be
            # narrowed by retyping it.
            products_query = Product.query.join(Brand).join(Category).filter(cond)
            products_query = apply_product_filters(products_query)
            sort = request.args.get("sort", "").strip()
            if sort:
                products_query = apply_product_sort(products_query, sort)
            else:
                products_query = products_query.order_by(
                    score.desc(), Product.featured.desc(), Product.rating.desc()
                )
            pagination = paginate_products(products_query)
            product_results = pagination.items

            # Facet options: each facet is computed with every OTHER facet
            # applied, but not with itself. That is what makes the rail behave:
            #   * excluding itself  -> after picking Keurig you can still switch
            #     to Ninja, instead of the dropdown collapsing to one option
            #   * applying the rest -> picking Furniture drops Ninja from the
            #     brand list, so the rail can no longer offer a combination
            #     that returns nothing
            facet_brands = facet_options(Brand, cond, exclude="brand")
            facet_categories = facet_options(Category, cond, exclude="category")
        else:
            product_results = []
        store_results = (
            Store.query.filter(
                or_(
                    db.func.lower(Store.name).like(q_like),
                    db.func.lower(Store.city).like(q_like),
                    db.func.lower(Store.state).like(q_like),
                )
            )
            .order_by(Store.city.asc())
            .limit(8)
            .all()
        )
        article_results = (
            SupportArticle.query.filter(
                or_(
                    db.func.lower(SupportArticle.title).like(q_like),
                    db.func.lower(SupportArticle.summary).like(q_like),
                    db.func.lower(SupportArticle.body).like(q_like),
                )
            )
            .order_by(SupportArticle.title.asc())
            .limit(8)
            .all()
        )
        log_search(q, "global", len(product_results) + len(store_results) + len(article_results))
    return render_template(
        "search.html",
        active_query=q,
        product_results=product_results,
        store_results=store_results,
        article_results=article_results,
        pagination=pagination,
        # Facets are drawn from the matches themselves, so the rail never
        # offers a brand or department that would return nothing.
        facet_brands=facet_brands,
        facet_categories=facet_categories,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("That demo account/password combination was not recognized.", "danger")
        else:
            login_user(user)
            merge_compare_session_into_user()
            flash(f"Welcome back, {user.full_name}.", "success")
            next_url = request.args.get("next") or url_for("account")
            return redirect(next_url)
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))

    stores = Store.query.order_by(Store.city.asc()).all()
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        preferred_store_slug = request.form.get("preferred_store_slug", "").strip()

        if not email or not full_name or not password:
            flash("Please fill in your name, email, and password.", "warning")
        elif password != confirm_password:
            flash("The passwords did not match.", "warning")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered in this demo mirror.", "warning")
        else:
            user = User(
                email=email,
                full_name=full_name,
                phone=request.form.get("phone", "").strip(),
                city=request.form.get("city", "").strip(),
                state=request.form.get("state", "").strip(),
                preferred_store_slug=preferred_store_slug,
                member_tier="Target Circle",
                rewards_member_id=f"TGTC-{100000 + User.query.count() + 1}",
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            db.session.add(
                RewardAccount(
                    user_id=user.id,
                    member_id=user.rewards_member_id,
                    points_balance=120,
                    tier=user.member_tier,
                    available_certificates=0,
                )
            )
            db.session.commit()
            login_user(user)
            flash("Your local demo account is ready.", "success")
            return redirect(url_for("account"))

    return render_template("register.html", stores=stores)


@app.route("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("You have been signed out of the demo account.", "info")
    return redirect(url_for("home"))


@app.route("/account")
@login_required
def account():
    recent_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.placed_at.desc()).limit(3).all()
    recent_tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(SupportTicket.created_at.desc()).limit(3).all()
    wishlist_preview = current_user.wishlist_items[:4]
    return render_template(
        "account.html",
        recent_orders=recent_orders,
        recent_tickets=recent_tickets,
        wishlist_preview=wishlist_preview,
        reward_account=current_user.reward_account,
    )


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    """Profile editing — required by the mirror's route contract.

    Validates server-side rather than trusting the form: an agent submitting a
    blank name or a malformed email must see the error, not a silent success.
    """
    stores = Store.query.order_by(Store.city.asc()).all()
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        store_slug = request.form.get("preferred_store_slug", "").strip()

        errors = []
        if not full_name:
            errors.append("Enter your name.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Enter a valid email address.")
        else:
            clash = User.query.filter(User.email == email, User.id != current_user.id).first()
            if clash:
                errors.append("That email is already used by another account.")
        if store_slug and not any(s.slug == store_slug for s in stores):
            errors.append("Choose a store from the list.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("account_edit.html", stores=stores), 400

        current_user.full_name = full_name
        current_user.email = email
        current_user.phone = phone
        current_user.city = city
        current_user.state = state
        current_user.preferred_store_slug = store_slug
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account"))

    return render_template("account_edit.html", stores=stores)


@app.route("/account/support")
@login_required
def account_support():
    """Support tickets got their own page — they were buried at the bottom of
    the account overview with no nav entry, so nothing linked to them."""
    tickets = (SupportTicket.query.filter_by(user_id=current_user.id)
               .order_by(SupportTicket.created_at.desc()).all())
    return render_template("account_support.html", tickets=tickets)


@app.route("/support/contact", methods=["GET", "POST"])
@login_required
def support_new_ticket():
    """Open a support request. The SupportTicket table previously had no way
    to gain a row from the UI — it was seed-only."""
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        summary = request.form.get("summary", "").strip()
        channel = request.form.get("channel", "Chat").strip() or "Chat"

        errors = []
        if len(subject) < 4:
            errors.append("Give your request a subject.")
        if len(summary) < 10:
            errors.append("Describe the issue in a little more detail.")
        if channel not in {"Chat", "Email", "Phone"}:
            errors.append("Choose a contact method.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("support_contact.html"), 400

        db.session.add(
            SupportTicket(
                user_id=current_user.id,
                subject=subject[:180],
                summary=summary,
                channel=channel,
                status="Open",
            )
        )
        db.session.commit()
        flash("Your request was submitted.", "success")
        return redirect(url_for("account_support"))

    return render_template("support_contact.html")


@app.route("/product/<sku>/review", methods=["POST"])
@login_required
def submit_review(sku: str):
    """Write a guest review. Server-side validated and persisted, so a task
    like 'leave a 4-star review on X' has a real DB after-state to verify."""
    product = Product.query.filter_by(sku=sku).first_or_404()
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    raw_rating = request.form.get("rating", "").strip()

    errors = []
    try:
        rating = int(raw_rating)
        if not 1 <= rating <= 5:
            raise ValueError
    except ValueError:
        rating = 0
        errors.append("Choose a star rating from 1 to 5.")
    if len(title) < 3:
        errors.append("Add a short headline for your review.")
    if len(body) < 15:
        errors.append("Tell us a bit more — reviews need at least 15 characters.")

    if errors:
        for message in errors:
            flash(message, "error")
        return redirect(url_for("product_page", sku=sku))

    db.session.add(
        Review(
            product_id=product.id,
            author_name=current_user.full_name or "Target guest",
            title=title[:140],
            body=body,
            rating=rating,
            verified=False,
        )
    )
    db.session.commit()
    flash("Thanks — your review was posted.", "success")
    return redirect(url_for("product_page", sku=sku))


@app.route("/account/orders")
@login_required
def account_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.placed_at.desc()).all()
    return render_template("account_orders.html", orders=orders)


@app.route("/account/rewards")
@login_required
def account_rewards():
    activities = RewardActivity.query.filter_by(user_id=current_user.id).order_by(RewardActivity.created_at.desc()).all()
    return render_template("account_rewards.html", activities=activities, reward_account=current_user.reward_account)


@app.route("/account/wishlist")
@login_required
def account_wishlist():
    wishlist_items = WishlistItem.query.filter_by(user_id=current_user.id).order_by(WishlistItem.created_at.desc()).all()
    return render_template("wishlist.html", wishlist_items=wishlist_items)


@app.route("/account/wishlist/toggle/<sku>", methods=["POST"])
@login_required
def toggle_wishlist(sku: str):
    product = Product.query.filter_by(sku=sku).first_or_404()
    item = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if item:
        db.session.delete(item)
        flash(f"Removed {product.name} from your wishlist.", "info")
    else:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=product.id))
        flash(f"Saved {product.name} to your wishlist.", "success")
    db.session.commit()
    return redirect(request.form.get("next") or request.referrer or url_for("product_page", sku=sku))


@app.route("/compare/toggle/<sku>", methods=["POST"])
def toggle_compare(sku: str):
    product = Product.query.filter_by(sku=sku).first_or_404()
    if current_user.is_authenticated:
        item = CompareItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
        if item:
            db.session.delete(item)
            flash(f"Removed {product.name} from compare.", "info")
        else:
            if CompareItem.query.filter_by(user_id=current_user.id).count() >= 4:
                oldest = CompareItem.query.filter_by(user_id=current_user.id).order_by(CompareItem.created_at.asc()).first()
                if oldest:
                    db.session.delete(oldest)
            db.session.add(CompareItem(user_id=current_user.id, product_id=product.id))
            flash(f"Added {product.name} to compare.", "success")
        db.session.commit()
    else:
        compare_skus = session.get("compare_skus", [])
        if sku in compare_skus:
            compare_skus = [value for value in compare_skus if value != sku]
            flash(f"Removed {product.name} from compare.", "info")
        else:
            compare_skus = (compare_skus + [sku])[-4:]
            flash(f"Added {product.name} to compare.", "success")
        session["compare_skus"] = compare_skus
        session.modified = True
    return redirect(request.form.get("next") or request.referrer or url_for("compare_page"))


@app.route("/cart")
def cart_page():
    if not current_user.is_authenticated:
        return render_template("cart.html", cart_items=[], totals={"subtotal": 0.0, "count": 0}, requires_login=True)
    cart_items = get_cart_items()
    totals = cart_totals(cart_items)
    return render_template("cart.html", cart_items=cart_items, totals=totals, requires_login=False)


@app.route("/cart/add", methods=["POST"])
@login_required
def add_to_cart():
    product = Product.query.filter_by(sku=request.form.get("sku", "").strip()).first_or_404()
    try:
        quantity = max(1, min(CART_MAX_QTY, int(request.form.get("quantity", "1") or 1)))
    except ValueError:
        quantity = 1
    fulfillment_method = request.form.get("fulfillment_method", "delivery")
    store_id = request.form.get("store_id")
    delivery_option_id = request.form.get("delivery_option_id")
    protection_plan_id = request.form.get("protection_plan_id")

    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if cart_item:
        # Adding something already in the cart ACCUMULATES. This used to
        # overwrite, so pressing "Add to cart" twice left the quantity at 1 and
        # the second click silently did nothing.
        cart_item.quantity = min(CART_MAX_QTY, cart_item.quantity + quantity)
    else:
        cart_item = CartItem(user_id=current_user.id, product_id=product.id)
        cart_item.quantity = quantity
        db.session.add(cart_item)
    cart_item.fulfillment_method = fulfillment_method
    cart_item.store_id = int(store_id) if store_id else None
    cart_item.delivery_option_id = int(delivery_option_id) if delivery_option_id else None
    cart_item.protection_plan_id = int(protection_plan_id) if protection_plan_id else None
    db.session.commit()
    flash(f"Added {product.name} to your cart.", "success")
    return redirect(request.form.get("next") or url_for("cart_page"))


@app.route("/cart/update/<int:item_id>", methods=["POST"])
@login_required
def update_cart(item_id: int):
    cart_item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    quantity = int(request.form.get("quantity", cart_item.quantity) or cart_item.quantity)
    if quantity <= 0:
        db.session.delete(cart_item)
        flash(f"Removed {cart_item.product.name} from your cart.", "info")
    else:
        cart_item.quantity = min(quantity, 5)
        db.session.add(cart_item)
        flash(f"Updated {cart_item.product.name} in your cart.", "success")
    db.session.commit()
    return redirect(url_for("cart_page"))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_cart_item(item_id: int):
    cart_item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    product_name = cart_item.product.name
    db.session.delete(cart_item)
    db.session.commit()
    flash(f"Removed {product_name} from your cart.", "info")
    return redirect(url_for("cart_page"))


@app.route("/checkout")
def checkout():
    if not current_user.is_authenticated:
        return render_template("checkout_mode.html", cart_items=[], checkout={}, requires_login=True)
    try:
        cart_items = require_cart_items()
    except RuntimeError:
        return redirect(url_for("cart_page"))
    return render_template("checkout_mode.html", cart_items=cart_items, checkout=get_checkout_state(), requires_login=False)


@app.route("/checkout/shipping", methods=["GET", "POST"])
@login_required
def checkout_shipping():
    try:
        cart_items = require_cart_items()
    except RuntimeError:
        return redirect(url_for("cart_page"))

    delivery_options = DeliveryOption.query.order_by(DeliveryOption.fee.asc()).all()
    checkout = get_checkout_state()
    if request.method == "POST":
        checkout.update(
            {
                "mode": "delivery",
                "delivery_option_id": request.form.get("delivery_option_id"),
                "shipping_name": request.form.get("shipping_name", "").strip(),
                "shipping_street": request.form.get("shipping_street", "").strip(),
                "shipping_city": request.form.get("shipping_city", "").strip(),
                "shipping_state": request.form.get("shipping_state", "").strip(),
                "shipping_zip": request.form.get("shipping_zip", "").strip(),
            }
        )
        save_checkout_state(checkout)
        flash("Delivery details saved.", "success")
        return redirect(url_for("checkout_payment"))
    return render_template(
        "checkout_shipping.html",
        cart_items=cart_items,
        delivery_options=delivery_options,
        checkout=checkout,
    )


@app.route("/checkout/pickup", methods=["GET", "POST"])
@login_required
def checkout_pickup():
    try:
        cart_items = require_cart_items()
    except RuntimeError:
        return redirect(url_for("cart_page"))

    stores = Store.query.order_by(Store.city.asc()).all()
    checkout = get_checkout_state()
    # Pickup windows are the same at every store, so the picker offers the five
    # distinct times once and the store is chosen separately. Listing each
    # store's rows produced 75 options that all read alike.
    windows = pickup_windows()

    if request.method == "POST":
        store_id = request.form.get("store_id")
        slot_window = request.form.get("slot_window", "").strip()

        errors = []
        store = db.session.get(Store, int(store_id)) if (store_id or "").isdigit() else None
        if store is None:
            errors.append("Choose a store for pickup.")
        if slot_window not in windows:
            errors.append("Choose a pickup time.")

        if errors:
            for message in errors:
                flash(message, "error")
        else:
            # Resolve the chosen window to that store's own slot row, so the
            # order records a slot that genuinely belongs to the pickup store.
            slot = resolve_pickup_slot(store.id, slot_window)
            checkout.update({"mode": "pickup", "store_id": store_id,
                             "slot_window": slot_window,
                             "slot_id": slot.id if slot else None})
            save_checkout_state(checkout)
            flash("Store pickup details saved.", "success")
            return redirect(url_for("checkout_payment"))

    return render_template(
        "checkout_pickup.html",
        cart_items=cart_items,
        stores=stores,
        pickup_windows=windows,
        checkout=checkout,
    )


@app.route("/checkout/payment", methods=["GET", "POST"])
@login_required
def checkout_payment():
    try:
        cart_items = require_cart_items()
    except RuntimeError:
        return redirect(url_for("cart_page"))

    checkout = get_checkout_state()
    if request.method == "POST":
        # Server-side validation: never silently default a missing/!4-digit card.
        # (A direct POST used to be accepted because payment_last4 fell back to "1111".)
        raw_last4 = (request.form.get("payment_last4") or "").strip()
        payment_brand = (request.form.get("payment_brand") or "").strip()
        errors = []
        if not raw_last4:
            errors.append("Enter the last 4 digits of your demo card.")
        elif not re.fullmatch(r"\d{4}", raw_last4):
            errors.append("Card digits must be exactly 4 numbers.")
        if not payment_brand:
            errors.append("Choose a demo card brand.")
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "checkout_payment.html", cart_items=cart_items, checkout=checkout, errors=errors
            )

        checkout.update({"payment_brand": payment_brand, "payment_last4": raw_last4})
        save_checkout_state(checkout)
        flash("Demo payment details saved.", "success")
        return redirect(url_for("checkout_review"))
    return render_template("checkout_payment.html", cart_items=cart_items, checkout=checkout)


@app.route("/checkout/review", methods=["GET", "POST"])
@login_required
def checkout_review():
    try:
        cart_items = require_cart_items()
    except RuntimeError:
        return redirect(url_for("cart_page"))

    checkout = get_checkout_state()
    summary = build_checkout_summary(cart_items, checkout)
    if request.method == "POST":
        if summary["mode"] == "delivery" and not checkout.get("delivery_option_id"):
            flash("Choose a delivery option before placing the order.", "warning")
            return redirect(url_for("checkout_shipping"))
        if summary["mode"] == "pickup" and not checkout.get("store_id"):
            flash("Choose a pickup store before placing the order.", "warning")
            return redirect(url_for("checkout_pickup"))
        if not checkout.get("payment_last4"):
            flash("Enter demo payment details before placing the order.", "warning")
            return redirect(url_for("checkout_payment"))

        order_number = f"TGT-{240000 + Order.query.count() + 1}"
        order = Order(
            user_id=current_user.id,
            order_number=order_number,
            email=current_user.email,
            status="Ready for pickup" if summary["mode"] == "pickup" else "Preparing shipment",
            subtotal=summary["subtotal"],
            tax=summary["tax"],
            total=summary["total"],
            fulfillment_method=summary["mode"],
            store_id=summary["store"].id if summary["store"] else None,
            delivery_option_id=summary["delivery_option"].id if summary["delivery_option"] else None,
            shipping_name=checkout.get("shipping_name", current_user.full_name),
            shipping_street=checkout.get("shipping_street", ""),
            shipping_city=checkout.get("shipping_city", current_user.city),
            shipping_state=checkout.get("shipping_state", current_user.state),
            shipping_zip=checkout.get("shipping_zip", "00000"),
            payment_brand=checkout.get("payment_brand", "Demo Visa"),
            payment_last4=checkout.get("payment_last4", "1111"),
            confirmation_note=(
                "Synthetic demo order only. No real payment or fulfillment occurred."
            ),
            pickup_slot_label=summary["pickup_slot"].time_window if summary["pickup_slot"] else "",
        )
        db.session.add(order)
        db.session.flush()

        for item in cart_items:
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=item.product_id,
                    item_name=item.product.name,
                    quantity=item.quantity,
                    unit_price=item.product.price,
                    protection_plan_name=item.protection_plan.name if item.protection_plan else "",
                )
            )

        db.session.add(
            PaymentMock(
                order_id=order.id,
                amount=summary["total"],
                card_label=checkout.get("payment_brand", "Demo Visa"),
                approval_code=f"TGTOK{order.id:04d}",
            )
        )

        earned_points = int(summary["subtotal"])
        if current_user.reward_account:
            current_user.reward_account.points_balance += earned_points
            db.session.add(
                RewardActivity(
                    user_id=current_user.id,
                    points_delta=earned_points,
                    title=f"Points from order {order.order_number}",
                    note="Synthetic demo checkout reward credit.",
                )
            )

        for item in cart_items:
            db.session.delete(item)

        db.session.commit()
        session["target_last_order"] = order.order_number
        session["target_lookup_order"] = order.order_number
        clear_checkout_state()
        flash("Demo checkout completed.", "success")
        return redirect(url_for("checkout_confirmation"))

    return render_template("checkout_review.html", cart_items=cart_items, checkout=checkout, summary=summary)


@app.route("/checkout/confirmation")
@login_required
def checkout_confirmation():
    order_number = request.args.get("order_number") or session.get("target_last_order")
    if not order_number:
        flash("There is no recent checkout to confirm.", "info")
        return redirect(url_for("account_orders"))
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    if order.user_id != current_user.id:
        abort(403)
    return render_template("checkout_confirmation.html", order=order)


@app.route("/order-lookup", methods=["GET", "POST"])
def order_lookup():
    order = None
    if request.method == "POST":
        order_number = request.form.get("order_number", "").strip().upper()
        email = request.form.get("email", "").strip().lower()
        order = Order.query.filter_by(order_number=order_number, email=email).first()
        if order:
            session["target_lookup_order"] = order.order_number
            session.modified = True
            flash("Demo order located.", "success")
            return redirect(url_for("order_detail", order_number=order.order_number))
        flash("We could not match that synthetic order number and email.", "warning")
    return render_template("order_lookup.html", order=order)


@app.route("/order/<order_number>")
def order_detail(order_number: str):
    order = Order.query.filter_by(order_number=order_number.upper()).first_or_404()
    if not order_accessible(order):
        flash("Use order lookup or sign in to view that order.", "warning")
        return redirect(url_for("order_lookup"))
    return render_template("order_detail.html", order=order)


@app.route("/_health")
def health():
    return jsonify(
        {
            "ok": True,
            "site": SITE_SLUG,
            "products": Product.query.count(),
            "stores": Store.query.count(),
            "orders": Order.query.count(),
        }
    )


def initialize_database() -> None:
    seed_exists = SEED_DB_PATH.exists()
    runtime_exists = RUNTIME_DB_PATH.exists()

    if not runtime_exists and seed_exists:
        shutil.copy2(SEED_DB_PATH, RUNTIME_DB_PATH)
        runtime_exists = True

    # Avoid touching a freshly copied runtime DB. SQLite file metadata can
    # change even on a no-op schema call, which breaks reset md5 identity.
    if not runtime_exists:
        db.create_all()

    from seed_data import ensure_seed_data

    ensure_seed_data(
        force=not seed_exists,
        runtime_db_path=RUNTIME_DB_PATH,
        seed_db_path=SEED_DB_PATH,
    )


with app.app_context():
    initialize_database()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", SITE_PORT))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)

