"""IKEA local demo mirror for WebHarbor."""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DB_PATH = INSTANCE_DIR / "ikea.db"

INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config["SECRET_KEY"] = "webharbor-ikea-demo-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to continue in this local IKEA demo."
login_manager.login_message_category = "info"

DEMO_PASSWORD = "TestPass123!"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SEARCH_RESULT_FLOOR = 8
SEARCH_INTENT_GROUPS = (
    {"sofa", "sectional", "chaise", "loveseat", "armchair", "seat"},
    {"chair", "stool", "seat"},
    {"table", "coffee table", "side table"},
    {"desk", "workstation"},
    {"lamp", "light", "lighting"},
    {"curtain", "curtains", "drape", "drapes"},
    {"mirror"},
    {"rug", "mat"},
    {"bed", "bedframe"},
    {"storage", "shelf", "cabinet", "dresser"},
)
TASK_PRODUCT_SKUS = {
    "IK-10001",
    "IK-10002",
    "IK-10005",
    "IK-10006",
    "IK-10007",
    "IK-10010",
    "IK-10020",
    "IK-10023",
}
ROOM_LABELS = {
    "living-room": "Living room",
    "bedroom": "Bedroom",
    "kitchen": "Kitchen & dining",
    "office": "Home office",
    "lighting": "Lighting",
    "bathroom": "Bathroom",
    "kids": "Children's room",
    "outdoor": "Outdoor",
    "entryway": "Entryway",
    "textiles": "Textiles",
    "storage": "Storage",
    "decor": "Decor",
}


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def loads_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(40), default="")
    city = db.Column(db.String(100), default="")
    state = db.Column(db.String(40), default="")
    zip_code = db.Column(db.String(20), default="")
    preferred_store_slug = db.Column(db.String(120), default="")
    family_tier = db.Column(db.String(40), default="IKEA Family")
    rewards_points = db.Column(db.Integer, default=0)
    newsletter_opt_in = db.Column(db.Boolean, default=True)

    cart_items = db.relationship("CartItem", backref="user", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", backref="user", cascade="all, delete-orphan")
    compare_items = db.relationship("CompareItem", backref="user", cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="user", cascade="all, delete-orphan")
    reward_activities = db.relationship(
        "RewardActivity", backref="user", cascade="all, delete-orphan"
    )
    support_tickets = db.relationship(
        "SupportTicket", backref="user", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    room_slug = db.Column(db.String(80), nullable=False, index=True)
    description = db.Column(db.Text, default="")
    hero_caption = db.Column(db.String(140), default="")
    icon_name = db.Column(db.String(80), default="")


class Store(db.Model):
    __tablename__ = "stores"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    city = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(30), default="")
    hours = db.Column(db.String(120), default="")
    amenities_json = db.Column(db.Text, default="[]")
    services_json = db.Column(db.Text, default="[]")
    image_path = db.Column(db.String(255), default="")
    pickup_note = db.Column(db.String(200), default="")

    inventories = db.relationship("StoreInventory", backref="store", cascade="all, delete-orphan")
    pickup_slots = db.relationship("PickupSlot", backref="store", cascade="all, delete-orphan")

    @property
    def amenities(self) -> list[str]:
        return loads_json(self.amenities_json, [])

    @property
    def services(self) -> list[str]:
        return loads_json(self.services_json, [])


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False)
    series = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    category_slug = db.Column(db.String(120), nullable=False, index=True)
    room_slug = db.Column(db.String(80), nullable=False, index=True)
    description = db.Column(db.Text, default="")
    material = db.Column(db.String(120), default="")
    color = db.Column(db.String(80), default="")
    dimensions = db.Column(db.String(120), default="")
    assembly_level = db.Column(db.String(80), default="Weekend setup")
    price = db.Column(db.Float, nullable=False)
    list_price = db.Column(db.Float, nullable=False)
    rating = db.Column(db.Float, default=4.4)
    review_count = db.Column(db.Integer, default=0)
    availability_bucket = db.Column(db.String(80), default="Ready for pickup")
    delivery_note = db.Column(db.String(160), default="")
    pickup_badge = db.Column(db.String(160), default="")
    image_path = db.Column(db.String(255), default="")
    gallery_json = db.Column(db.Text, default="[]")
    features_json = db.Column(db.Text, default="[]")
    specs_json = db.Column(db.Text, default="{}")
    tags_json = db.Column(db.Text, default="[]")
    is_featured = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=False)
    is_deal = db.Column(db.Boolean, default=False)
    is_bestseller = db.Column(db.Boolean, default=False)
    compare_group = db.Column(db.String(120), default="")

    reviews = db.relationship("Review", backref="product", cascade="all, delete-orphan")
    cart_items = db.relationship("CartItem", backref="product", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", backref="product", cascade="all, delete-orphan")
    compare_items = db.relationship("CompareItem", backref="product", cascade="all, delete-orphan")
    protection_plans = db.relationship(
        "ProtectionPlan", backref="product", cascade="all, delete-orphan"
    )
    inventories = db.relationship("StoreInventory", backref="product", cascade="all, delete-orphan")

    @property
    def gallery(self) -> list[str]:
        return loads_json(self.gallery_json, [])

    @property
    def features(self) -> list[str]:
        return loads_json(self.features_json, [])

    @property
    def tags(self) -> list[str]:
        return loads_json(self.tags_json, [])

    @property
    def specs(self) -> dict[str, str]:
        return loads_json(self.specs_json, {})

    @property
    def savings(self) -> float:
        return max(self.list_price - self.price, 0.0)

    @property
    def card_name(self) -> str:
        """Return a concise listing name without detail-only measurements."""
        if not self.dimensions:
            return self.name
        for suffix in (f", {self.dimensions}", f" {self.dimensions}"):
            if self.name.endswith(suffix):
                return self.name[: -len(suffix)]
        return self.name


class StoreInventory(db.Model):
    __tablename__ = "store_inventory"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    aisle = db.Column(db.String(40), default="")
    pickup_available = db.Column(db.Boolean, default=True)
    delivery_available = db.Column(db.Boolean, default=True)


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    author_name = db.Column(db.String(120), nullable=False)
    headline = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    helpful_count = db.Column(db.Integer, default=0)
    created_on = db.Column(db.String(20), default="")


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)


class WishlistItem(db.Model):
    __tablename__ = "wishlist_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    created_on = db.Column(db.String(20), default="")


class CompareItem(db.Model):
    __tablename__ = "compare_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    created_on = db.Column(db.String(20), default="")


class DeliveryOption(db.Model):
    __tablename__ = "delivery_options"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    fee = db.Column(db.Float, nullable=False)
    window_label = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(200), default="")
    carbon_note = db.Column(db.String(120), default="")


class PickupSlot(db.Model):
    __tablename__ = "pickup_slots"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    slot_date = db.Column(db.String(20), nullable=False)
    time_window = db.Column(db.String(80), nullable=False)
    remaining_capacity = db.Column(db.Integer, default=0)


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"))
    fulfillment_method = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(80), nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    shipping_fee = db.Column(db.Float, nullable=False)
    tax = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    placed_on = db.Column(db.String(20), nullable=False)
    delivery_window = db.Column(db.String(120), default="")
    pickup_window = db.Column(db.String(120), default="")
    contact_name = db.Column(db.String(120), default="")
    payment_summary = db.Column(db.String(120), default="")

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")
    payment = db.relationship(
        "PaymentMock", backref="order", uselist=False, cascade="all, delete-orphan"
    )
    store = db.relationship("Store")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)

    product = db.relationship("Product")


class PaymentMock(db.Model):
    __tablename__ = "payment_mocks"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    method_label = db.Column(db.String(80), nullable=False)
    last_four = db.Column(db.String(4), nullable=False)
    billing_name = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(40), default="Authorized")


class RewardActivity(db.Model):
    __tablename__ = "reward_activities"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    label = db.Column(db.String(160), nullable=False)
    points_delta = db.Column(db.Integer, nullable=False)
    activity_type = db.Column(db.String(80), nullable=False)
    occurred_on = db.Column(db.String(20), nullable=False)


class SupportArticle(db.Model):
    __tablename__ = "support_articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    category = db.Column(db.String(120), nullable=False)
    summary = db.Column(db.String(240), nullable=False)
    body = db.Column(db.Text, nullable=False)
    related_topics_json = db.Column(db.Text, default="[]")

    @property
    def related_topics(self) -> list[str]:
        return loads_json(self.related_topics_json, [])


class SupportTicket(db.Model):
    __tablename__ = "support_tickets"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(80), nullable=False)
    article_slug = db.Column(db.String(180), default="")
    opened_on = db.Column(db.String(20), nullable=False)
    note = db.Column(db.Text, default="")


class Deal(db.Model):
    __tablename__ = "deals"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    category_slug = db.Column(db.String(120), nullable=False)
    badge = db.Column(db.String(80), default="")
    summary = db.Column(db.String(240), nullable=False)
    discount_text = db.Column(db.String(80), nullable=False)
    product_sku = db.Column(db.String(40), default="")


class ProtectionPlan(db.Model):
    __tablename__ = "protection_plans"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    name = db.Column(db.String(140), nullable=False)
    years = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), default="")
    benefits_json = db.Column(db.Text, default="[]")

    @property
    def benefits(self) -> list[str]:
        return loads_json(self.benefits_json, [])


class RoomBundle(db.Model):
    __tablename__ = "room_bundles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    room_slug = db.Column(db.String(80), nullable=False)
    summary = db.Column(db.String(240), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    item_skus_json = db.Column(db.Text, default="[]")
    hero_note = db.Column(db.String(160), default="")

    @property
    def item_skus(self) -> list[str]:
        return loads_json(self.item_skus_json, [])


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


@app.template_filter("money")
def money(value: float) -> str:
    return f"${value:,.2f}"


@app.template_filter("stars")
def stars(value: float) -> str:
    return f"{value:.1f}"


def cart_items_for_user(user: User | None = None) -> list[CartItem]:
    if not user or not user.is_authenticated:
        return []
    return (
        CartItem.query.filter_by(user_id=user.id)
        .join(Product)
        .order_by(Product.name.asc())
        .all()
    )


def cart_summary(user: User | None = None) -> dict[str, Any]:
    items = cart_items_for_user(user or current_user)
    subtotal = sum(item.product.price * item.quantity for item in items)
    return {
        "items": items,
        "count": sum(item.quantity for item in items),
        "subtotal": subtotal,
        "estimated_tax": round(subtotal * 0.085, 2),
    }


def compare_products() -> list[Product]:
    if not current_user.is_authenticated:
        return []
    items = CompareItem.query.filter_by(user_id=current_user.id).all()
    return [item.product for item in items]


def selected_store() -> Store | None:
    preferred_slug = session.get("checkout_store")
    if not preferred_slug and current_user.is_authenticated:
        preferred_slug = current_user.preferred_store_slug
    if not preferred_slug:
        return Store.query.order_by(Store.name.asc()).first()
    return Store.query.filter_by(slug=preferred_slug).first()


def inventory_for_store(product: Product, store_slug: str | None = None) -> StoreInventory | None:
    slug = store_slug or (selected_store().slug if selected_store() else "")
    if not slug:
        return None
    return (
        StoreInventory.query.join(Store)
        .filter(Store.slug == slug, StoreInventory.product_id == product.id)
        .first()
    )


def query_products_from_request(category_slug: str | None = None, apply_search: bool = True):
    query = Product.query
    if category_slug:
        query = query.filter_by(category_slug=category_slug)

    search = request.args.get("q", "").strip()
    if search and apply_search:
        for token in search.split():
            token_like = f"%{token}%"
            query = query.filter(
                or_(
                    Product.name.ilike(token_like),
                    Product.series.ilike(token_like),
                    Product.description.ilike(token_like),
                    Product.tags_json.ilike(token_like),
                    Product.room_slug.ilike(token_like),
                )
            )

    room = request.args.get("room", "").strip()
    if room:
        query = query.filter_by(room_slug=room)

    series = request.args.get("series", "").strip()
    if series:
        query = query.filter_by(series=series)

    if request.args.get("deal") == "1":
        query = query.filter_by(is_deal=True)

    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    if min_price:
        query = query.filter(Product.price >= float(min_price))
    if max_price:
        query = query.filter(Product.price <= float(max_price))

    min_rating = request.args.get("min_rating", "").strip()
    if min_rating:
        query = query.filter(Product.rating >= float(min_rating))

    availability = request.args.get("availability", "").strip()
    if availability:
        query = query.filter(Product.availability_bucket.ilike(f"%{availability}%"))

    pickup_only = request.args.get("pickup", "").strip() == "1"
    if pickup_only:
        store_slug = request.args.get("store", "").strip() or (selected_store().slug if selected_store() else "")
        if store_slug:
            query = query.join(StoreInventory).join(Store).filter(
                Store.slug == store_slug,
                StoreInventory.pickup_available.is_(True),
                StoreInventory.quantity > 0,
            )

    sort = request.args.get("sort", "featured")
    if sort == "price-asc":
        query = query.order_by(Product.price.asc(), Product.rating.desc())
    elif sort == "price-desc":
        query = query.order_by(Product.price.desc(), Product.rating.desc())
    elif sort == "rating":
        query = query.order_by(Product.rating.desc(), Product.review_count.desc())
    elif sort == "newest":
        query = query.order_by(Product.is_new.desc(), Product.series.asc())
    elif sort == "popular":
        query = query.order_by(Product.review_count.desc(), Product.rating.desc())
    else:
        query = query.order_by(
            Product.is_featured.desc(),
            Product.is_deal.desc(),
            Product.rating.desc(),
            Product.review_count.desc(),
        )
    return query.distinct()


def normalize_search_text(value: str) -> str:
    """Fold accents and punctuation so common typed variants still match."""
    folded = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", without_accents))


def ranked_search_results(search_text: str) -> tuple[list[Product], bool]:
    """Return relevant matches plus deterministic near-miss products for sparse searches."""
    candidates = query_products_from_request(apply_search=False).all()
    normalized_query = normalize_search_text(search_text)
    tokens = normalized_query.split()
    if not tokens:
        return candidates, False

    ranked: list[tuple[int, int, Product]] = []
    partial: list[tuple[int, int, Product]] = []
    candidate_order = {product.id: index for index, product in enumerate(candidates)}
    for product in candidates:
        title = normalize_search_text(product.name)
        searchable = normalize_search_text(
            f"{product.name} {product.series} {product.description} "
            f"{product.tags_json} {product.room_slug} {product.category_slug}"
        )
        token_hits = sum(token in searchable for token in tokens)
        if not token_hits:
            continue
        score = token_hits * 20
        score += sum(12 for token in tokens if token in title)
        if normalized_query in title:
            score += 40
        if all(token in searchable for token in tokens):
            score += 30
        item = (score, -candidate_order[product.id], product)
        if token_hits == len(tokens):
            ranked.append(item)
        else:
            partial.append(item)

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if not ranked and partial:
        best_score = max(item[0] for item in partial)
        ranked = [item for item in partial if item[0] == best_score]
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    results = [item[2] for item in ranked]
    direct_ids = {product.id for product in results}
    expanded = False

    if len(results) < SEARCH_RESULT_FLOOR and results:
        leading_categories = {product.category_slug for product in results[:3]}
        leading_title = normalize_search_text(results[0].name)
        intent_terms = next(
            (terms for terms in SEARCH_INTENT_GROUPS if any(term in leading_title for term in terms)),
            set(),
        )
        related = [
            product
            for product in candidates
            if product.id not in direct_ids and product.category_slug in leading_categories
        ]
        related.sort(
            key=lambda product: (
                sum(
                    term in normalize_search_text(f"{product.name} {product.description}")
                    for term in intent_terms
                ),
                -candidate_order[product.id],
            ),
            reverse=True,
        )
        selected_related = related[: SEARCH_RESULT_FLOOR - len(results)]
        if selected_related:
            lead_count = min(2, len(selected_related))
            results = selected_related[:lead_count] + results + selected_related[lead_count:]
            expanded = True

    return results, expanded


def category_image_products(categories: list[Category]) -> dict[str, Product]:
    images: dict[str, Product] = {}
    for category in categories:
        product = (
            Product.query.filter(
                Product.category_slug == category.slug,
                ~Product.sku.in_(TASK_PRODUCT_SKUS),
            )
            .order_by(Product.is_featured.desc(), Product.rating.desc())
            .first()
        )
        if product:
            images[category.slug] = product
    return images


def products_for_bundle(bundle: RoomBundle) -> list[Product]:
    products_by_sku = {
        product.sku: product
        for product in Product.query.filter(Product.sku.in_(bundle.item_skus)).all()
    }
    return [products_by_sku[sku] for sku in bundle.item_skus if sku in products_by_sku]


def pickup_slot_date(slot: PickupSlot) -> date | None:
    """Keep seeded weekday availability current without changing the reset seed."""
    try:
        slot_day = date.fromisoformat(slot.slot_date)
    except ValueError:
        return None
    today = datetime.now(ZoneInfo("America/New_York")).date()
    while slot_day < today:
        slot_day += timedelta(days=7)
    return slot_day


def pickup_slot_label(slot: PickupSlot, include_capacity: bool = True) -> str:
    slot_day = pickup_slot_date(slot)
    date_label = slot.slot_date
    if slot_day:
        date_label = f"{slot_day.strftime('%a, %b')} {slot_day.day}"
    label = f"{date_label} · {slot.time_window}"
    if include_capacity:
        label += f" ({slot.remaining_capacity} left)"
    return label


@app.template_filter("pickup_slot_label")
def pickup_slot_label_filter(slot: PickupSlot) -> str:
    return pickup_slot_label(slot)


def checkout_state() -> dict[str, Any]:
    state = session.setdefault("checkout_state", {})
    return state


def clear_checkout_state() -> None:
    session.pop("checkout_state", None)
    session.pop("confirmation_order_number", None)


def ensure_checkout_ready() -> tuple[dict[str, Any], dict[str, Any]]:
    summary = cart_summary()
    if not summary["items"]:
        flash("Your cart is empty in this local demo.", "warning")
        return {}, summary
    return checkout_state(), summary


@app.context_processor
def inject_globals() -> dict[str, Any]:
    categories = Category.query.order_by(Category.name.asc()).all()
    stores = Store.query.order_by(Store.name.asc()).all()
    compare_count = len(compare_products()) if current_user.is_authenticated else 0
    summary = cart_summary() if current_user.is_authenticated else {"count": 0, "subtotal": 0.0}
    wishlist_product_ids = set()
    compare_product_ids = set()
    if current_user.is_authenticated:
        wishlist_product_ids = {
            product_id
            for (product_id,) in (
                WishlistItem.query.with_entities(WishlistItem.product_id)
                .filter_by(user_id=current_user.id)
                .all()
            )
        }
        compare_product_ids = {
            product_id
            for (product_id,) in (
                CompareItem.query.with_entities(CompareItem.product_id)
                .filter_by(user_id=current_user.id)
                .all()
            )
        }
    return {
        "nav_categories": categories[:8],
        "room_labels": ROOM_LABELS,
        "store_options": stores,
        "cart_count": summary["count"],
        "compare_count": compare_count,
        "wishlist_product_ids": wishlist_product_ids,
        "compare_product_ids": compare_product_ids,
    }


@app.route("/")
@app.route("/home")
def index():
    hero_product = (
        Product.query.filter(
            Product.category_slug == "living-room-seating",
            ~Product.sku.in_(TASK_PRODUCT_SKUS),
        )
        .order_by(Product.is_featured.desc(), Product.rating.desc())
        .first()
    )
    featured_products = (
        Product.query.filter(
            Product.is_featured.is_(True),
            ~Product.sku.in_(TASK_PRODUCT_SKUS),
        )
        .order_by(Product.rating.desc())
        .limit(8)
        .all()
    )
    deals = (
        Deal.query.filter(~Deal.product_sku.in_(TASK_PRODUCT_SKUS))
        .order_by(Deal.title.asc())
        .limit(6)
        .all()
    )
    categories = Category.query.order_by(Category.name.asc()).all()
    bundles = RoomBundle.query.order_by(RoomBundle.room_slug.asc()).limit(6).all()
    support_articles = SupportArticle.query.order_by(SupportArticle.category.asc(), SupportArticle.title.asc()).limit(6).all()
    stores = Store.query.order_by(Store.name.asc()).limit(4).all()
    return render_template(
        "index.html",
        hero_product=hero_product,
        featured_products=featured_products,
        deals=deals,
        categories=categories,
        bundles=bundles,
        support_articles=support_articles,
        stores=stores,
        category_images=category_image_products(categories),
    )


@app.route("/categories")
def categories():
    categories_list = Category.query.order_by(Category.room_slug.asc(), Category.name.asc()).all()
    bundles = RoomBundle.query.order_by(RoomBundle.total_price.asc()).all()
    return render_template(
        "categories.html",
        categories=categories_list,
        bundles=bundles,
        category_images=category_image_products(categories_list),
    )


@app.route("/category/<category_slug>")
def category_view(category_slug: str):
    category = Category.query.filter_by(slug=category_slug).first_or_404()
    products = query_products_from_request(category_slug=category_slug).all()
    return render_template(
        "products.html",
        title=category.name,
        description=category.description,
        products=products,
        category=category,
        series_options=sorted({product.series for product in products}),
    )


@app.route("/products")
def products():
    results = query_products_from_request().all()
    return render_template(
        "products.html",
        title="Products",
        description="Search, filter, and compare local IKEA demo products.",
        products=results,
        category=None,
        series_options=sorted({product.series for product in Product.query.all()}),
    )


@app.route("/search")
def search():
    search_text = request.args.get("q", "").strip()
    results, related_results_added = ranked_search_results(search_text)
    return render_template(
        "products.html",
        title=f"Search results for “{search_text}”",
        description="Products matching your search, ordered by relevance.",
        products=results,
        category=None,
        series_options=sorted({product.series for product in Product.query.all()}),
        related_results_added=related_results_added,
    )


@app.route("/deals")
def deals():
    deal_rows = Deal.query.order_by(Deal.badge.asc(), Deal.title.asc()).all()
    highlighted = {
        deal.product_sku: Product.query.filter_by(sku=deal.product_sku).first()
        for deal in deal_rows
        if deal.product_sku
    }
    return render_template("deals.html", deals=deal_rows, highlighted=highlighted)


@app.route("/product/<sku>")
def product_detail(sku: str):
    product = Product.query.filter_by(sku=sku).first_or_404()
    related = (
        Product.query.filter(
            Product.category_slug == product.category_slug,
            Product.sku != product.sku,
        )
        .order_by(Product.rating.desc())
        .limit(4)
        .all()
    )
    category = Category.query.filter_by(slug=product.category_slug).first()
    store_records = (
        StoreInventory.query.filter_by(product_id=product.id)
        .join(Store)
        .order_by(StoreInventory.quantity.desc(), Store.city.asc())
        .limit(4)
        .all()
    )
    return render_template(
        "product_detail.html",
        product=product,
        category=category,
        related=related,
        store_records=store_records,
    )


@app.route("/compare")
@login_required
def compare():
    products_to_compare = compare_products()
    shared_keys = []
    if products_to_compare:
        shared_keys = sorted({key for product in products_to_compare for key in product.specs})
    return render_template(
        "compare.html",
        products=products_to_compare,
        shared_keys=shared_keys,
    )


@app.post("/compare/toggle/<sku>")
@login_required
def compare_toggle(sku: str):
    product = Product.query.filter_by(sku=sku).first_or_404()
    item = CompareItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if item:
        db.session.delete(item)
        flash(f"Removed {product.name} from compare.", "info")
    else:
        if CompareItem.query.filter_by(user_id=current_user.id).count() >= 4:
            flash(
                "Compare is full (4/4). Remove a product from Compare before adding another.",
                "warning",
            )
        else:
            db.session.add(
                CompareItem(
                    user_id=current_user.id,
                    product_id=product.id,
                    created_on="2026-06-04",
                )
            )
            flash(f"Added {product.name} to compare.", "success")
    db.session.commit()
    return redirect(request.referrer or url_for("compare"))


@app.route("/room-planner")
def room_planner():
    room = request.args.get("room", "").strip()
    bundles_query = RoomBundle.query
    if room:
        bundles_query = bundles_query.filter_by(room_slug=room)
    bundles = bundles_query.order_by(RoomBundle.total_price.asc()).all()
    bundle_products = {bundle.id: products_for_bundle(bundle) for bundle in bundles}
    return render_template(
        "room_planner.html",
        bundles=bundles,
        bundle_products=bundle_products,
        selected_room=room,
    )


@app.post("/room-planner/add/<bundle_slug>")
@login_required
def add_bundle(bundle_slug: str):
    bundle = RoomBundle.query.filter_by(slug=bundle_slug).first_or_404()
    skus = bundle.item_skus
    for sku in skus:
        product = Product.query.filter_by(sku=sku).first()
        if not product:
            continue
        item = CartItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
        if item:
            item.quantity += 1
        else:
            db.session.add(CartItem(user_id=current_user.id, product_id=product.id, quantity=1))
    db.session.commit()
    flash(f"Added the {bundle.name} bundle to your cart.", "success")
    return redirect(url_for("cart"))


@app.route("/stores")
def stores():
    search_text = request.args.get("q", "").strip()
    query = Store.query
    if search_text:
        token_like = f"%{search_text}%"
        query = query.filter(
            or_(Store.name.ilike(token_like), Store.city.ilike(token_like), Store.state.ilike(token_like))
        )
    stores_list = query.order_by(Store.state.asc(), Store.city.asc()).all()
    return render_template("stores.html", stores=stores_list, search_text=search_text)


@app.route("/stores/<store_slug>")
def store_detail(store_slug: str):
    store = Store.query.filter_by(slug=store_slug).first_or_404()
    slots = PickupSlot.query.filter_by(store_id=store.id).order_by(PickupSlot.slot_date.asc()).all()
    featured_products = (
        Product.query.join(StoreInventory)
        .filter(StoreInventory.store_id == store.id, StoreInventory.quantity > 0)
        .order_by(Product.rating.desc())
        .limit(8)
        .all()
    )
    return render_template(
        "store_detail.html",
        store=store,
        slots=slots,
        featured_products=featured_products,
    )


@app.route("/support")
def support():
    query_text = request.args.get("q", "").strip()
    articles_query = SupportArticle.query
    if query_text:
        token_like = f"%{query_text}%"
        articles_query = articles_query.filter(
            or_(
                SupportArticle.title.ilike(token_like),
                SupportArticle.summary.ilike(token_like),
                SupportArticle.body.ilike(token_like),
                SupportArticle.category.ilike(token_like),
            )
        )
    articles = articles_query.order_by(SupportArticle.category.asc(), SupportArticle.title.asc()).all()
    return render_template("support.html", articles=articles, query_text=query_text)


@app.route("/support/<article_slug>")
def support_article(article_slug: str):
    article = SupportArticle.query.filter_by(slug=article_slug).first_or_404()
    related = (
        SupportArticle.query.filter(
            SupportArticle.category == article.category,
            SupportArticle.slug != article.slug,
        )
        .order_by(SupportArticle.title.asc())
        .limit(4)
        .all()
    )
    return render_template("support_article.html", article=article, related=related)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Signed in to the IKEA demo account.", "success")
            return redirect(url_for("account"))
        flash("That demo sign-in did not match our seeded users.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not EMAIL_PATTERN.fullmatch(email):
            flash("Enter a valid email address.", "danger")
            return render_template("register.html"), 400
        if not password:
            flash("Enter a password for the new account.", "danger")
            return render_template("register.html"), 400
        if User.query.filter_by(email=email).first():
            flash("That email is already present in this local demo.", "warning")
            return redirect(url_for("login"))
        user = User(
            email=email,
            first_name=request.form.get("first_name", "Demo").strip() or "Demo",
            last_name=request.form.get("last_name", "Guest").strip() or "Guest",
            city=request.form.get("city", "").strip(),
            state=request.form.get("state", "").strip(),
            zip_code=request.form.get("zip_code", "").strip(),
            phone=request.form.get("phone", "").strip(),
            preferred_store_slug=request.form.get("preferred_store_slug", "").strip(),
            rewards_points=250,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Created a new local demo account.", "success")
        return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out of the IKEA demo.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    open_orders = (
        Order.query.filter_by(user_id=current_user.id)
        .order_by(Order.placed_on.desc(), Order.order_number.desc())
        .limit(4)
        .all()
    )
    tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(SupportTicket.opened_on.desc()).all()
    return render_template("account.html", open_orders=open_orders, tickets=tickets)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name", current_user.first_name).strip()
        current_user.last_name = request.form.get("last_name", current_user.last_name).strip()
        current_user.phone = request.form.get("phone", current_user.phone).strip()
        current_user.city = request.form.get("city", current_user.city).strip()
        current_user.state = request.form.get("state", current_user.state).strip()
        current_user.zip_code = request.form.get("zip_code", current_user.zip_code).strip()
        current_user.preferred_store_slug = request.form.get(
            "preferred_store_slug", current_user.preferred_store_slug
        ).strip()
        current_user.newsletter_opt_in = request.form.get("newsletter_opt_in") == "on"
        db.session.commit()
        flash("Saved your local profile updates.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/account/orders")
@login_required
def account_orders():
    orders = (
        Order.query.filter_by(user_id=current_user.id)
        .order_by(Order.placed_on.desc(), Order.order_number.desc())
        .all()
    )
    return render_template("account_orders.html", orders=orders)


@app.route("/account/rewards")
@login_required
def account_rewards():
    activities = (
        RewardActivity.query.filter_by(user_id=current_user.id)
        .order_by(RewardActivity.occurred_on.desc())
        .all()
    )
    return render_template("account_rewards.html", activities=activities)


@app.route("/account/wishlist")
@login_required
def account_wishlist():
    items = (
        WishlistItem.query.filter_by(user_id=current_user.id)
        .join(Product)
        .order_by(Product.name.asc())
        .all()
    )
    return render_template("account_wishlist.html", items=items)


@app.post("/wishlist/toggle/<sku>")
@login_required
def wishlist_toggle(sku: str):
    product = Product.query.filter_by(sku=sku).first_or_404()
    item = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if item:
        db.session.delete(item)
        flash(f"Removed {product.name} from wishlist.", "info")
    else:
        db.session.add(
            WishlistItem(
                user_id=current_user.id,
                product_id=product.id,
                created_on="2026-06-04",
            )
        )
        flash(f"Saved {product.name} to wishlist.", "success")
    db.session.commit()
    return redirect(request.referrer or url_for("account_wishlist"))


@app.route("/cart")
@login_required
def cart():
    summary = cart_summary()
    return render_template("cart.html", summary=summary)


@app.post("/cart/add")
@login_required
def cart_add():
    product = Product.query.filter_by(sku=request.form.get("sku", "").strip()).first_or_404()
    quantity = max(int(request.form.get("quantity", 1)), 1)
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if item:
        item.quantity += quantity
    else:
        db.session.add(CartItem(user_id=current_user.id, product_id=product.id, quantity=quantity))
    db.session.commit()
    flash(f"Added {product.name} to your cart.", "success")
    return redirect(request.referrer or url_for("cart"))


@app.post("/cart/update/<int:item_id>")
@login_required
def cart_update(item_id: int):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    quantity = max(int(request.form.get("quantity", item.quantity)), 1)
    item.quantity = quantity
    db.session.commit()
    flash("Updated cart quantity.", "success")
    return redirect(url_for("cart"))


@app.post("/cart/remove/<int:item_id>")
@login_required
def cart_remove(item_id: int):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Removed item from cart.", "info")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout_start():
    state, summary = ensure_checkout_ready()
    if not summary["items"]:
        return redirect(url_for("cart"))
    if request.method == "POST":
        method = request.form.get("method", "delivery")
        state["method"] = method
        if method == "pickup":
            state.pop("delivery_option", None)
            state.pop("delivery_name", None)
            state.pop("delivery_zip", None)
        else:
            state.pop("store_slug", None)
            state.pop("pickup_slot_id", None)
        session.modified = True
        if method == "pickup":
            return redirect(url_for("checkout_pickup"))
        return redirect(url_for("checkout_shipping"))
    return render_template("checkout_start.html", summary=summary, state=state)


@app.route("/checkout/shipping", methods=["GET", "POST"])
@login_required
def checkout_shipping():
    state, summary = ensure_checkout_ready()
    if not summary["items"]:
        return redirect(url_for("cart"))
    delivery_options = DeliveryOption.query.order_by(DeliveryOption.fee.asc()).all()
    if request.method == "POST":
        state["method"] = "delivery"
        state.pop("store_slug", None)
        state.pop("pickup_slot_id", None)
        state["delivery_option"] = request.form.get("delivery_option", "parcel")
        state["delivery_name"] = request.form.get("delivery_name", current_user.full_name).strip()
        state["delivery_zip"] = request.form.get("delivery_zip", current_user.zip_code).strip()
        session.modified = True
        return redirect(url_for("checkout_payment"))
    return render_template(
        "checkout_shipping.html",
        summary=summary,
        state=state,
        delivery_options=delivery_options,
    )


@app.route("/checkout/pickup", methods=["GET", "POST"])
@login_required
def checkout_pickup():
    state, summary = ensure_checkout_ready()
    if not summary["items"]:
        return redirect(url_for("cart"))
    stores = Store.query.order_by(Store.state.asc(), Store.city.asc()).all()
    if request.method == "POST":
        store_slug = request.form.get("store_slug", "").strip()
        slot_value = request.form.get("pickup_slot_id", "").strip()
        store = Store.query.filter_by(slug=store_slug).first()
        try:
            slot_id = int(slot_value)
        except ValueError:
            slot_id = 0
        slot = PickupSlot.query.filter_by(id=slot_id, store_id=store.id).first() if store else None
        if not store or not slot:
            flash("Choose an available pickup slot for the selected store.", "danger")
            return redirect(url_for("checkout_pickup", store_slug=store_slug))
        state["method"] = "pickup"
        state.pop("delivery_option", None)
        state.pop("delivery_name", None)
        state.pop("delivery_zip", None)
        state["store_slug"] = store.slug
        state["pickup_slot_id"] = str(slot.id)
        session["checkout_store"] = state["store_slug"]
        session.modified = True
        return redirect(url_for("checkout_payment"))
    preferred_store = selected_store()
    selected_slug = (
        request.args.get("store_slug", "").strip()
        or state.get("store_slug")
        or (preferred_store.slug if preferred_store else "")
    )
    slots = []
    if selected_slug:
        store = Store.query.filter_by(slug=selected_slug).first()
        if store:
            slots = PickupSlot.query.filter_by(store_id=store.id).order_by(PickupSlot.slot_date.asc()).all()
    return render_template(
        "checkout_pickup.html",
        summary=summary,
        state=state,
        stores=stores,
        slots=slots,
        selected_slug=selected_slug,
    )


@app.get("/api/pickup-slots")
@login_required
def pickup_slots_api():
    store = Store.query.filter_by(slug=request.args.get("store_slug", "").strip()).first_or_404()
    slots = PickupSlot.query.filter_by(store_id=store.id).order_by(PickupSlot.slot_date.asc()).all()
    return jsonify(
        {
            "slots": [
                {
                    "id": slot.id,
                    "label": pickup_slot_label(slot),
                }
                for slot in slots
            ]
        }
    )


@app.route("/checkout/payment", methods=["GET", "POST"])
@login_required
def checkout_payment():
    state, summary = ensure_checkout_ready()
    if not summary["items"]:
        return redirect(url_for("cart"))
    if request.method == "POST":
        state["payment_method"] = request.form.get("payment_method", "IKEA Family Visa")
        state["payment_last4"] = request.form.get("payment_last4", "4242").strip()[-4:]
        state["billing_name"] = request.form.get("billing_name", current_user.full_name).strip()
        session.modified = True
        return redirect(url_for("checkout_review"))
    return render_template("checkout_payment.html", summary=summary, state=state)


@app.route("/checkout/review", methods=["GET", "POST"])
@login_required
def checkout_review():
    state, summary = ensure_checkout_ready()
    if not summary["items"]:
        return redirect(url_for("cart"))
    delivery_option = None
    pickup_store = None
    pickup_slot = None
    method = state.get("method", "delivery")
    if method == "delivery" and state.get("delivery_option"):
        delivery_option = DeliveryOption.query.filter_by(slug=state["delivery_option"]).first()
    if method == "pickup" and state.get("store_slug"):
        pickup_store = Store.query.filter_by(slug=state["store_slug"]).first()
    if method == "pickup" and state.get("pickup_slot_id"):
        try:
            pickup_slot_id = int(state["pickup_slot_id"])
        except (TypeError, ValueError):
            pickup_slot_id = 0
        pickup_slot = PickupSlot.query.filter_by(id=pickup_slot_id).first()
    if method == "pickup" and (
        not pickup_store or not pickup_slot or pickup_slot.store_id != pickup_store.id
    ):
        flash("Your pickup selection changed. Choose a current store and time slot.", "warning")
        return redirect(url_for("checkout_pickup"))

    if request.method == "POST":
        next_index = (db.session.query(db.func.count(Order.id)).scalar() or 0) + 1
        order_number = f"IK-26{next_index:04d}"
        shipping_fee = delivery_option.fee if delivery_option else 0.0
        total = round(summary["subtotal"] + summary["estimated_tax"] + shipping_fee, 2)
        order = Order(
            order_number=order_number,
            user_id=current_user.id,
            store_id=pickup_store.id if pickup_store else None,
            fulfillment_method=state.get("method", "delivery"),
            status="Ready for processing",
            subtotal=summary["subtotal"],
            shipping_fee=shipping_fee,
            tax=summary["estimated_tax"],
            total=total,
            placed_on="2026-06-04",
            delivery_window=delivery_option.window_label if delivery_option else "",
            pickup_window=pickup_slot_label(pickup_slot, include_capacity=False) if pickup_slot else "",
            contact_name=state.get("delivery_name") or current_user.full_name,
            payment_summary=f"{state.get('payment_method', 'Demo Card')} •••• {state.get('payment_last4', '4242')}",
        )
        db.session.add(order)
        db.session.flush()
        for item in summary["items"]:
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=item.product.price,
                )
            )
            db.session.delete(item)
        db.session.add(
            PaymentMock(
                order_id=order.id,
                method_label=state.get("payment_method", "Demo Card"),
                last_four=state.get("payment_last4", "4242"),
                billing_name=state.get("billing_name", current_user.full_name),
                status="Authorized in local demo",
            )
        )
        db.session.add(
            RewardActivity(
                user_id=current_user.id,
                label=f"Order {order_number}",
                points_delta=int(summary["subtotal"] // 10),
                activity_type="purchase",
                occurred_on="2026-06-04",
            )
        )
        current_user.rewards_points += int(summary["subtotal"] // 10)
        db.session.commit()
        session["confirmation_order_number"] = order_number
        clear_checkout_state()
        session["confirmation_order_number"] = order_number
        return redirect(url_for("checkout_confirmation"))

    return render_template(
        "checkout_review.html",
        summary=summary,
        state=state,
        delivery_option=delivery_option,
        pickup_store=pickup_store,
        pickup_slot=pickup_slot,
    )


@app.route("/checkout/confirmation")
@login_required
def checkout_confirmation():
    order_number = session.get("confirmation_order_number")
    if not order_number:
        flash("There is no recent checkout confirmation to show.", "warning")
        return redirect(url_for("account_orders"))
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    return render_template("checkout_confirmation.html", order=order)


@app.route("/order-lookup", methods=["GET", "POST"])
def order_lookup():
    order = None
    looked_up = False
    if request.method == "POST":
        looked_up = True
        session.pop("lookup_order_number", None)
        order_number = request.form.get("order_number", "").strip().upper()
        email = request.form.get("email", "").strip().lower()
        if order_number and EMAIL_PATTERN.fullmatch(email):
            order = (
                Order.query.join(User)
                .filter(Order.order_number == order_number, User.email == email)
                .first()
            )
        if order:
            session["lookup_order_number"] = order.order_number
        else:
            flash("No order matched that order number and email address.", "warning")
    return render_template("order_lookup.html", order=order, looked_up=looked_up)


@app.route("/order/<order_number>")
def order_detail(order_number: str):
    order = Order.query.filter_by(order_number=order_number.upper()).first_or_404()
    account_access = current_user.is_authenticated and order.user_id == current_user.id
    lookup_access = session.get("lookup_order_number") == order.order_number
    if not account_access and not lookup_access:
        abort(404)
    return render_template("order_detail.html", order=order)


@app.route("/_health")
def health():
    return jsonify(
        {
            "ok": True,
            "site": "ikea",
            "products": Product.query.count(),
            "stores": Store.query.count(),
        }
    )


def bootstrap_site() -> None:
    from seed_data import seed_benchmark_users, seed_database

    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()


if os.environ.get("WEBSYN_SKIP_BOOTSTRAP") != "1":
    bootstrap_site()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
