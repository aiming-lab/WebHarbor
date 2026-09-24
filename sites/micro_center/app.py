"""Micro Center mirror — Flask application.

Offline mirror of www.microcenter.com for the WebHarbor benchmark: catalog
browsing, scored search with upstream-style facets (N= category codes and
fq= filter chains), per-store inventory, open box offers, compare, cart,
pickup/shipping checkout, and an account area with orders, build lists,
addresses and payment methods.

Runtime data comes from instance/micro_center.db (restored from
instance_seed/micro_center.db at boot). No JSON is read at request time.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

SITE_SLUG = "micro_center"
SITE_NAME = "Micro Center"
SITE_PORT = 40112
BENCHMARK_PASSWORD = "TestPass123!"
BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
SEED_DIR = BASE_DIR / "instance_seed"
IMAGE_DIR = BASE_DIR / "static" / "images"
RUNTIME_DB_PATH = INSTANCE_DIR / "micro_center.db"
SEED_DB_PATH = SEED_DIR / "micro_center.db"
PASSWORD_NAMESPACE = "microcenter-webharbor-demo"
CART_SESSION_KEY = "mc_cart"          # guest cart: {product_id: qty}
COMPARE_SESSION_KEY = "mc_compare"   # compare ids: [product_id, ...]
STORE_SESSION_KEY = "mc_store"
CHECKOUT_SESSION_KEY = "mc_checkout"
# Tax rate applied at checkout (mirror fixture; TX stores apply sales tax).
TAX_RATE = 0.0725

if __name__ == "__main__":
    sys.modules.setdefault("app", sys.modules[__name__])


def _ensure_dirs() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


_ensure_dirs()

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config["SECRET_KEY"] = "micro-center-demo-session-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{RUNTIME_DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "signin"
login_manager.login_message = "Sign in to your Micro Center Insider account to continue."


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

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


STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
              "is", "it", "by", "with", "from", "your", "you", "new"}


def tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower())
            if t and t not in STOP_WORDS]


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin, TimestampMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    username = db.Column(db.String(80), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(64), nullable=False)
    phone = db.Column(db.String(40), default="")
    is_benchmark = db.Column(db.Boolean, default=False)
    addresses = db.relationship("Address", backref="user", lazy=True,
                                order_by="Address.id")
    cards = db.relationship("PaymentCard", backref="user", lazy=True,
                            order_by="PaymentCard.id")

    def set_password(self, raw: str) -> None:
        self.password_hash = stable_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return self.password_hash == stable_password_hash(raw)

    def default_address(self) -> "Address | None":
        for address in self.addresses:
            if address.is_default:
                return address
        return self.addresses[0] if self.addresses else None

    def default_card(self) -> "PaymentCard | None":
        for card in self.cards:
            if card.is_default:
                return card
        return self.cards[0] if self.cards else None


class Address(db.Model):
    __tablename__ = "addresses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    label = db.Column(db.String(60), default="")
    full_name = db.Column(db.String(120), nullable=False)
    line1 = db.Column(db.String(200), nullable=False)
    line2 = db.Column(db.String(200), default="")
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(20), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(40), default="")
    is_default = db.Column(db.Boolean, default=False)

    def one_line(self) -> str:
        parts = [self.line1]
        if self.line2:
            parts.append(self.line2)
        return ", ".join(parts)


class PaymentCard(db.Model):
    __tablename__ = "payment_cards"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    brand = db.Column(db.String(40), nullable=False)     # Visa / Mastercard
    last4 = db.Column(db.String(4), nullable=False)
    exp_month = db.Column(db.String(2), nullable=False)
    exp_year = db.Column(db.String(4), nullable=False)
    is_default = db.Column(db.Boolean, default=False)

    def display(self) -> str:
        return f"{self.brand} ending in {self.last4}"


class Store(db.Model):
    __tablename__ = "stores"
    id = db.Column(db.String(3), primary_key=True)   # upstream store number
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(220), nullable=False)
    phone = db.Column(db.String(40), default="")
    hours = db.Column(db.Text, default="")           # JSON list of day rows
    map_ref = db.Column(db.String(40), default="")    # optional image filename

    def label(self) -> str:
        return f"{self.state} - {self.city}"

    def hours_rows(self) -> list[dict[str, str]]:
        return load_json(self.hours, [])


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(160), nullable=False, unique=True)
    fq_id = db.Column(db.Integer, nullable=True)      # upstream fq category id
    n_code = db.Column(db.String(40), nullable=True)  # upstream N= code
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    is_dept = db.Column(db.Boolean, default=False)     # dept page /site/products/
    blurb = db.Column(db.Text, default="")
    children = db.relationship("Category", backref=db.backref("parent", remote_side=[id]),
                               lazy=True, order_by="Category.name")

    def fq_name(self) -> str:
        return self.name.replace(" ", "+").replace("&", "%26").replace("/", "%2F")


class Brand(db.Model):
    __tablename__ = "brands"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)


class Product(db.Model):
    __tablename__ = "products"
    product_id = db.Column(db.Integer, primary_key=True)   # upstream product id
    sku = db.Column(db.Integer, nullable=False)           # upstream SKU number
    name = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(300), nullable=False)
    brand = db.Column(db.String(120), nullable=False, default="")
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    category = db.relationship("Category", backref="products", lazy=True)
    subcategory = db.Column(db.String(160), default="")
    price = db.Column(db.Float, nullable=False, default=0.0)
    original_price = db.Column(db.Float, nullable=True)
    description = db.Column(db.Text, default="")
    key_features = db.Column(db.Text, default="[]")       # JSON list[str]
    specs = db.Column(db.Text, default="[]")               # JSON [{group, pairs}]
    images = db.Column(db.Text, default="[]")              # JSON list[filename]
    rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    in_store_only = db.Column(db.Boolean, default=False)
    open_box = db.Column(db.Text, default="[]")            # JSON [{condition, price}]
    closeout = db.Column(db.Boolean, default=False)
    top_deal = db.Column(db.Boolean, default=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ---- helpers -----------------------------------------------------------
    def pid7(self) -> str:
        return str(self.product_id).zfill(7)

    def url_slug(self) -> str:
        return self.slug or slugify(self.name)

    def detail_url(self) -> str:
        return f"/product/{self.pid7()}/{self.url_slug()}"

    def image_files(self) -> list[str]:
        return load_json(self.images, [])

    def primary_image(self) -> str:
        files = self.image_files()
        return files[0] if files else ""

    def gallery(self) -> list[str]:
        files = self.image_files()
        if files:
            return files[1:]
        return []

    def spec_groups(self) -> list[dict[str, Any]]:
        return load_json(self.specs, [])

    def features(self) -> list[str]:
        return load_json(self.key_features, [])

    def open_box_offers(self) -> list[dict[str, Any]]:
        return load_json(self.open_box, [])

    def spec_value(self, key: str) -> str | None:
        for group in self.spec_groups():
            for k, v in group.get("pairs", []):
                if k.lower() == key.lower():
                    return v
        return None

    def searchable_text(self) -> str:
        spec_words: list[str] = []
        for group in self.spec_groups():
            spec_words.extend(str(v) for _, v in group.get("pairs", []))
        return " ".join([
            self.name, self.brand, self.subcategory or "",
            self.category.name if self.category else "",
            " ".join(self.features()), " ".join(spec_words),
        ]).lower()

    def stock_at(self, store_id: str) -> "StoreStock | None":
        return StoreStock.query.filter_by(product_id=self.product_id,
                                          store_id=store_id).first()


class StoreStock(db.Model):
    __tablename__ = "store_stock"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    store_id = db.Column(db.String(3), db.ForeignKey("stores.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="out of stock")
    qty = db.Column(db.Integer, default=0)
    product = db.relationship("Product", backref="stock_rows", lazy=True)
    store = db.relationship("Store", backref="stock_rows", lazy=True)


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), default="")
    body = db.Column(db.Text, default="")
    verified = db.Column(db.Boolean, default=True)
    product = db.relationship("Product", backref="reviews", lazy=True)


class CartItem(db.Model, TimestampMixin):
    __tablename__ = "cart_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    qty = db.Column(db.Integer, nullable=False, default=1)
    product = db.relationship("Product", lazy=True)


class ListItem(db.Model, TimestampMixin):
    """Micro Center 'My List' (wishlist)."""
    __tablename__ = "list_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    note = db.Column(db.String(300), default="")
    product = db.relationship("Product", lazy=True)


class Order(db.Model, TimestampMixin):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Processing")
    method = db.Column(db.String(20), nullable=False, default="pickup")
    store_id = db.Column(db.String(3), db.ForeignKey("stores.id"), nullable=True)
    store = db.relationship("Store", lazy=True)
    ship_to = db.Column(db.Text, default="")           # JSON address snapshot
    payment = db.Column(db.String(120), default="")
    placed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    subtotal = db.Column(db.Float, nullable=False, default=0.0)
    tax = db.Column(db.Float, nullable=False, default=0.0)
    shipping_fee = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)
    items_json = db.Column(db.Text, default="[]")
    user = db.relationship("User", backref="orders", lazy=True)

    def items(self) -> list[dict[str, Any]]:
        return load_json(self.items_json, [])

    def item_count(self) -> int:
        return sum(int(item.get("qty", 1)) for item in self.items())

    def address_text(self) -> str:
        addr = load_json(self.ship_to, {})
        if not addr:
            return ""
        return (f"{addr.get('full_name','')}, {addr.get('line1','')}, "
                f"{addr.get('city','')}, {addr.get('state','')} {addr.get('zip','')}")


class CompareItem(db.Model, TimestampMixin):
    __tablename__ = "compare_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    product = db.relationship("Product", lazy=True)


class SearchLog(db.Model):
    __tablename__ = "search_log"
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(200), nullable=False)
    scope = db.Column(db.String(40), default="search")
    result_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------------------------------------------------------------------
# login / template globals
# ---------------------------------------------------------------------------

def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


login_manager.user_loader(load_user)


@app.template_filter("money")
def money_filter(value: float) -> str:
    try:
        return f"${value:,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


@app.template_filter("stars")
def stars_filter(value: float) -> str:
    full = int(value)
    half = (value - full) >= 0.5
    return "★" * full + ("½" if half else "")


@app.template_filter("stock_label")
def stock_label_filter(product: Product, store: Store | None) -> str:
    return stock_label(product, store)


def nav_departments() -> list[Category]:
    return Category.query.filter_by(is_dept=True).order_by(Category.id).all()


def selected_store() -> Store | None:
    store_id = session.get(STORE_SESSION_KEY)
    if not store_id:
        return None
    return db.session.get(Store, store_id)


def cart_rows() -> list[tuple[Product, int]]:
    """Cart as (product, qty) rows — session cart for guests, DB cart for users."""
    if current_user.is_authenticated:
        rows = (CartItem.query.filter_by(user_id=current_user.id)
                .order_by(CartItem.id).all())
        return [(row.product, row.qty) for row in rows if row.product]
    cart = session.get(CART_SESSION_KEY, {})
    rows = []
    for pid_str, qty in cart.items():
        product = db.session.get(Product, int(pid_str))
        if product and qty > 0:
            rows.append((product, qty))
    return rows


def cart_count() -> int:
    return sum(qty for _, qty in cart_rows())


def cart_totals(rows: list[tuple[Product, int]]) -> dict[str, float]:
    subtotal = sum(product.price * qty for product, qty in rows)
    tax = round(subtotal * TAX_RATE, 2)
    return {"subtotal": round(subtotal, 2), "tax": tax,
            "total": round(subtotal + tax, 2)}


def compare_ids() -> list[int]:
    if current_user.is_authenticated:
        return [row.product_id for row in
                CompareItem.query.filter_by(user_id=current_user.id)
                .order_by(CompareItem.id).all()]
    return [int(pid) for pid in session.get(COMPARE_SESSION_KEY, [])]


def compare_products() -> list[Product]:
    products = []
    for pid in compare_ids()[:4]:
        product = db.session.get(Product, pid)
        if product:
            products.append(product)
    return products


def checkout_state() -> dict[str, Any]:
    return session.get(CHECKOUT_SESSION_KEY, {})


def save_checkout_state(state: dict[str, Any]) -> None:
    session[CHECKOUT_SESSION_KEY] = state
    session.modified = True


def clear_checkout_state() -> None:
    session.pop(CHECKOUT_SESSION_KEY, None)
    session.modified = True


def csrf_token() -> str:
    token = session.get("_csrf")
    if not token:
        token = secrets.token_hex(16)
        session["_csrf"] = token
    return token


def validate_csrf() -> None:
    token = request.form.get("csrf_token", "")
    if not token or token != session.get("_csrf"):
        abort(400, "Invalid or missing CSRF token.")


def safe_redirect_target(candidate: str | None, fallback: str) -> str:
    if candidate and candidate.startswith("/") and not candidate.startswith("//"):
        return candidate
    return fallback


def form_str(name: str, default: str = "") -> str:
    return (request.form.get(name) or default).strip()


def form_int(name: str, default: int = 0) -> int:
    raw = request.form.get(name, "")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def flash_message(message: str, category: str = "info") -> None:
    flash(message, category)


@app.context_processor
def inject_globals() -> dict[str, Any]:
    store = selected_store()
    return {
        "site_name": SITE_NAME,
        "nav_departments": nav_departments(),
        "selected_store": store,
        "cart_count": cart_count(),
        "compare_count": len(compare_ids()),
        "csrf_token": csrf_token,
    }


# ---------------------------------------------------------------------------
# search & listing engine
# ---------------------------------------------------------------------------

def scored_products(query: str) -> list[tuple[Product, int]]:
    """Token-overlap scored search (never strict AND).

    Name/brand/category matches dominate; spec values and key features
    only nudge ranking, so a query like "27 inch monitor" ranks actual
    monitors above unrelated items whose specs merely contain the number.
    """
    tokens = tokenize(query)
    if not tokens:
        return []
    # Pure-numeric tokens must match on word boundaries so "5" does not hit
    # "1.75mm" and "27" does not hit "P2722DC".
    def term_in(token: str, text: str) -> bool:
        if token.isdigit():
            return re.search(r"(?<![0-9a-z])" + re.escape(token) + r"(?![0-9a-z])", text) is not None
        return token in text

    results: list[tuple[Product, int]] = []
    for product in Product.query.all():
        head = " ".join([product.name, product.brand,
                         product.subcategory or "",
                         product.category.name if product.category else ""]).lower()
        head_score = sum(1 for t in tokens if term_in(t, head))
        tail_score = 0
        if head_score:
            tail = " ".join(product.features())
            tail += " ".join(str(v) for group in product.spec_groups()
                            for _, v in group.get("pairs", []))
            tail = tail.lower()
            tail_score = sum(1 for t in tokens if term_in(t, tail))
        score = 4 * head_score + (1 if tail_score else 0)
        if score > 0:
            results.append((product, score))
    results.sort(key=lambda pair: (-pair[1], pair[0].name.lower()))
    return results


def parse_fq(raw: str) -> dict[str, list[str]]:
    """Parse upstream fq= filter chains like
    `category:Graphics+Cards+%26+Accessories|137,brand:ASUS,price:0-100`."""
    filters: dict[str, list[str]] = {}
    if not raw:
        return filters
    raw = raw.replace("%2C", ",").replace("%7C", "|").replace("%26", "&")
    raw = raw.replace("%2F", "/").replace("%3A", ":").replace("+", " ")
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        filters.setdefault(key.strip().lower(), []).append(value.strip())
    return filters


def fq_category_name(filters: dict[str, list[str]]) -> str | None:
    """Category name from a `category:Name|id` filter (strip the |id part)."""
    for value in filters.get("category", []) + filters.get("category_flat", []):
        name = value.split("|")[0].strip()
        if name:
            return name
    return None


def filters_to_products(filters: dict[str, list[str]],
                       base: list[Product] | None = None) -> list[Product]:
    """Apply fq facets to a product set (each facet value is an OR within the
    facet; facets AND across)."""
    products = base if base is not None else Product.query.all()
    for key, values in filters.items():
        matched: list[Product] = []
        for product in products:
            hit = False
            for value in values:
                if key in ("category", "category_flat", "subcategory"):
                    cat_name = (product.category.name if product.category else "")
                    target = cat_name if key != "subcategory" else (product.subcategory or "")
                    lhs = value.split("|")[0].strip().lower()
                    if lhs in target.lower():
                        hit = True
                elif key == "brand":
                    if value.strip().lower() in product.brand.lower():
                        hit = True
                elif key == "price":
                    try:
                        low, high = value.split("-")
                        low_f, high_f = float(low), float(high)
                        if low_f <= product.price <= high_f:
                            hit = True
                    except ValueError:
                        pass
                elif key in ("average_rating", "rating"):
                    try:
                        stars = float(re.search(r"([\d.]+)", value).group(1))
                        if product.rating >= stars:
                            hit = True
                    except (AttributeError, ValueError):
                        pass
                elif key == "valuable_links":
                    label = value.strip().lower()
                    if label == "open box" and product.open_box_offers():
                        hit = True
                    elif label == "closeout" and product.closeout:
                        hit = True
                elif key == "micro_center_deals":
                    if value.strip().lower() in ("top deals", "specials") and product.top_deal:
                        hit = True
                else:
                    # generic spec facet: match against spec values
                    needle = value.strip().lower()
                    if any(needle in str(v).lower()
                           for group in product.spec_groups()
                           for _, v in group.get("pairs", [])):
                        hit = True
            if hit:
                matched.append(product)
        products = matched
        if not products:
            break
    return products


SORTS = {
    "pricelow": lambda p: (p.price, p.name.lower()),
    "pricehigh": lambda p: (-p.price, p.name.lower()),
    "rating": lambda p: (-p.rating, -p.review_count, p.name.lower()),
    "newest": lambda p: (-p.product_id, p.name.lower()),
    "numreviews": lambda p: (-p.review_count, p.name.lower()),
}


def apply_sort(products: list[Product], sortby: str) -> list[Product]:
    key = SORTS.get(sortby)
    if key:
        return sorted(products, key=key)
    return products  # match: caller keeps score order


def facet_options(products: list[Product]) -> dict[str, list[tuple[str, int]]]:
    """Compute sidebar facet counts over a result set."""
    cats: dict[str, int] = {}
    brands: dict[str, int] = {}
    subcats: dict[str, int] = {}
    for product in products:
        cat_name = product.category.name if product.category else "Other"
        cats[cat_name] = cats.get(cat_name, 0) + 1
        if product.brand:
            brands[product.brand] = brands.get(product.brand, 0) + 1
        if product.subcategory:
            subcats[product.subcategory] = subcats.get(product.subcategory, 0) + 1
    return {
        "categories": sorted(cats.items(), key=lambda kv: (-kv[1], kv[0])),
        "brands": sorted(brands.items(), key=lambda kv: (-kv[1], kv[0]))[:24],
        "subcategories": sorted(subcats.items(), key=lambda kv: (-kv[1], kv[0]))[:16],
    }


def stock_label(product: Product, store: Store | None) -> str:
    """Stock text shown on listing rows / PDP for the selected store."""
    if store:
        row = product.stock_at(store.id)
        if row:
            if row.status == "in stock":
                return "In Stock" if row.qty is None or row.qty > 3 else f"Only {row.qty} Left In Stock"
            return "Out of Stock"
    if product.in_store_only:
        return "In Store Only"
    return "Usually ships in 5-7 business days."


# ---------------------------------------------------------------------------
# static-ish content pages
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    top_deals = (Product.query.filter_by(top_deal=True)
                 .order_by(Product.price).limit(12).all())
    open_box = (Product.query.filter(Product.open_box != "[]")
                .order_by(Product.product_id).limit(8).all())
    return render_template("home.html", top_deals=top_deals, open_box=open_box)


@app.route("/site/products/<slug>.aspx")
def dept_page(slug: str):
    # Upstream serves both department and subcategory listing pages on this
    # URL shape (e.g. /site/products/laptops-notebooks.aspx), so serve any
    # catalog category by slug; the mega menu, home tiles and footer all link
    # here.
    dept = Category.query.filter_by(slug=slug).first()
    if not dept:
        abort(404)
    children = dept.children
    products = (Product.query.join(Category, Product.category_id == Category.id)
                .filter(or_(Category.id == dept.id, Category.parent_id == dept.id))
                .order_by(Product.rating.desc(), Product.review_count.desc())
                .limit(24).all())
    return render_template("dept.html", dept=dept, children=children,
                           products=products)


@app.route("/site/content/top-deals.aspx")
def top_deals_page():
    deals = (Product.query.filter_by(top_deal=True)
             .order_by(Product.price).all())
    return render_template("deals.html", heading="Top Deals",
                           blurb="Save on this week's hottest tech from Micro Center.",
                           products=deals)


@app.route("/site/products/open-box.aspx")
def open_box_page():
    products = [p for p in Product.query.order_by(Product.product_id).all()
                if p.open_box_offers()]
    return render_template("deals.html", heading="Open Box",
                           blurb="Store returns and cancelled orders, inspected and "
                                 "discounted. Quantities are limited and condition varies.",
                           products=products, open_box=True)


@app.route("/site/products/clearance.aspx")
def clearance_page():
    products = Product.query.filter_by(closeout=True).order_by(Product.price).all()
    return render_template("deals.html", heading="Clearance & Closeouts",
                           blurb="Overstock and discontinued products at deep discounts.",
                           products=products)


# ---------------------------------------------------------------------------
# the search/listing page (upstream URL: /search/search_results.aspx)
# ---------------------------------------------------------------------------

@app.route("/search/search_results.aspx")
def search_results():
    query = (request.args.get("Ntt") or request.args.get("q") or "").strip()
    raw_fq = request.args.get("fq", "")
    n_code = (request.args.get("N") or "").strip()
    sortby = (request.args.get("sortby") or "match").strip()
    page_no = max(1, form_int_from_args("page", 1))
    rpp = min(96, max(12, form_int_from_args("rpp", 24)))
    my_store = request.args.get("myStore") in ("true", "1", "True")
    store = selected_store()

    filters = parse_fq(raw_fq)
    fq_cat = fq_category_name(filters)

    heading = None
    results: list[Product] = []
    search_order: list[tuple[Product, int]] = []

    if query:
        search_order = scored_products(query)
        results = [p for p, _ in search_order]
        if fq_cat:
            results = [p for p in results
                       if fq_cat.lower() in ((p.category.name if p.category else "").lower())]
        heading = f'Search results for "{query}"'
    elif fq_cat:
        category = Category.query.filter(
            func_lower(Category.name) == fq_cat.lower()).first()
        if category:
            results = (Product.query.filter_by(category_id=category.id)
                       .order_by(Product.name).all())
            heading = category.name
        else:
            results = [p for p in Product.query.all()
                       if fq_cat.lower() in (p.category.name if p.category else "").lower()]
            heading = fq_cat
    elif n_code:
        category = Category.query.filter_by(n_code=n_code.split()[0]).first()
        if category:
            results = (Product.query.filter_by(category_id=category.id)
                       .order_by(Product.name).all())
            heading = category.name
        else:
            results = list(Product.query.order_by(Product.name).all())
            heading = "All Products"
    else:
        results = list(Product.query.order_by(Product.name).all())
        heading = "All Products"

    if filters:
        base = results
        rest = {k: v for k, v in filters.items()
                if k not in ("category", "category_flat")}
        if rest:
            results = filters_to_products(rest, base=base)

    if my_store and store:
        keep = []
        for product in results:
            row = product.stock_at(store.id)
            if row and row.status == "in stock":
                keep.append(product)
        results = keep

    if sortby != "match" or not query:
        results = apply_sort(list(results), sortby)
    elif search_order:
        order_map = {p.product_id: i for i, (p, _) in enumerate(search_order)}
        results = sorted(results, key=lambda p: order_map.get(p.product_id, 10**9))

    total = len(results)
    start = (page_no - 1) * rpp
    page_rows = results[start:start + rpp]
    pages = max(1, (total + rpp - 1) // rpp)

    facets = facet_options(results)

    log = SearchLog(query=query or (fq_cat or n_code or "browse"),
                    scope="search" if query else "listing", result_count=total)
    db.session.add(log)
    db.session.commit()

    return render_template(
        "search_results.html", heading=heading, query=query, results=page_rows,
        total=total, page=page_no, pages=pages, rpp=rpp, sortby=sortby,
        facets=facets, raw_fq=raw_fq, n_code=n_code, my_store=my_store,
        store=store, fq_cat=fq_cat)


def form_int_from_args(name: str, default: int) -> int:
    raw = request.args.get(name, "")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def func_lower(column):
    from sqlalchemy import func
    return func.lower(column)


# ---------------------------------------------------------------------------
# product detail
# ---------------------------------------------------------------------------

@app.route("/product/<pid>/<slug>")
@app.route("/product/<pid>/<slug>/<rest>")
def product_page(pid: str, slug: str = "", rest: str = ""):
    try:
        product_id = int(pid)
    except ValueError:
        abort(404)
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    store_param = request.args.get("storeid", "").strip()
    if store_param:
        session[STORE_SESSION_KEY] = store_param
        session.modified = True
    store = selected_store()
    stock_rows = []
    if store:
        stock_rows = (StoreStock.query
                      .filter_by(product_id=product.product_id)
                      .order_by(StoreStock.store_id).all())
    else:
        all_rows = (StoreStock.query
                    .filter_by(product_id=product.product_id)
                    .order_by(StoreStock.store_id).all())
        stock_rows = all_rows

    stores_instock = [row for row in stock_rows if row.status == "in stock"]
    open_offers = product.open_box_offers()
    reviews = (Review.query.filter_by(product_id=product.product_id)
               .order_by(Review.date.desc(), Review.id.desc()).all())
    related = (Product.query.filter(Product.category_id == product.category_id,
                                    Product.product_id != product.product_id)
               .order_by(Product.rating.desc()).limit(6).all())
    return render_template("product.html", product=product, store=store,
                           stock_rows=stock_rows, stores_instock=stores_instock,
                           open_offers=open_offers, reviews=reviews,
                           related=related)

# ---------------------------------------------------------------------------
# stores
# ---------------------------------------------------------------------------

@app.route("/site/stores/default.aspx")
@app.route("/stores")
def stores_page():
    stores = Store.query.order_by(Store.state, Store.city).all()
    by_state: dict[str, list[Store]] = {}
    for store in stores:
        by_state.setdefault(store.state, []).append(store)
    return render_template("stores.html", by_state=by_state)


@app.route("/store/<store_id>")
def store_page(store_id: str):
    store = db.session.get(Store, store_id)
    if not store:
        abort(404)
    low = (StoreStock.query.filter_by(store_id=store.id, status="in stock")
           .order_by(StoreStock.product_id.desc()).limit(12).all())
    return render_template("store.html", store=store, featured=low)


@app.route("/store/select", methods=["POST"])
def store_select():
    validate_csrf()
    store_id = form_str("store_id")
    if db.session.get(Store, store_id):
        session[STORE_SESSION_KEY] = store_id
        session.modified = True
        flash_message(f"Your store is now set to {db.session.get(Store, store_id).name}.")
    return redirect(safe_redirect_target(request.form.get("next"), "/"))


# ---------------------------------------------------------------------------
# compare (upstream: /endeca/CompareV2.aspx)
# ---------------------------------------------------------------------------

@app.route("/endeca/CompareV2.aspx")
def compare_page():
    products = compare_products()
    spec_keys: list[str] = []
    seen = set()
    for product in products:
        for group in product.spec_groups():
            for key, _ in group.get("pairs", []):
                if key.lower() not in seen:
                    seen.add(key.lower())
                    spec_keys.append(key)
    table: dict[int, dict[str, str]] = {}
    for product in products:
        table[product.product_id] = {
            key: (product.spec_value(key) or "—") for key in spec_keys}
    return render_template("compare.html", products=products,
                           spec_keys=spec_keys, table=table)


@app.route("/compare/add/<int:product_id>", methods=["POST"])
def compare_add(product_id: int):
    validate_csrf()
    if not db.session.get(Product, product_id):
        abort(404)
    ids = compare_ids()
    if product_id not in ids:
        if len(ids) >= 4:
            flash_message("You may compare a maximum of 4 items at a time.", "error")
        elif current_user.is_authenticated:
            db.session.add(CompareItem(user_id=current_user.id,
                                       product_id=product_id))
            db.session.commit()
        else:
            ids.append(product_id)
            session[COMPARE_SESSION_KEY] = ids
            session.modified = True
    return redirect(safe_redirect_target(request.form.get("next"),
                                         "/endeca/CompareV2.aspx"))


@app.route("/compare/remove/<int:product_id>", methods=["POST"])
def compare_remove(product_id: int):
    validate_csrf()
    if current_user.is_authenticated:
        CompareItem.query.filter_by(user_id=current_user.id,
                                   product_id=product_id).delete()
        db.session.commit()
    else:
        ids = session.get(COMPARE_SESSION_KEY, [])
        if product_id in ids:
            ids.remove(product_id)
            session[COMPARE_SESSION_KEY] = ids
            session.modified = True
    return redirect(safe_redirect_target(request.form.get("next"),
                                         "/endeca/CompareV2.aspx"))


# ---------------------------------------------------------------------------
# cart
# ---------------------------------------------------------------------------

def merge_session_cart_into_user() -> None:
    cart = session.get(CART_SESSION_KEY, {})
    if not cart:
        return
    for pid_str, qty in cart.items():
        product = db.session.get(Product, int(pid_str))
        if not product:
            continue
        row = CartItem.query.filter_by(user_id=current_user.id,
                                        product_id=product.product_id).first()
        if row:
            row.qty = min(10, row.qty + qty)
        else:
            db.session.add(CartItem(user_id=current_user.id,
                                    product_id=product.product_id, qty=qty))
    session.pop(CART_SESSION_KEY, None)
    session.modified = True
    db.session.commit()


@app.route("/cart")
def cart():
    rows = cart_rows()
    totals = cart_totals(rows)
    store = selected_store()
    stock_warnings = []
    for product, _ in rows:
        label = stock_label(product, store)
        if "Out of Stock" in label:
            stock_warnings.append(product.name)
    return render_template("cart.html", rows=rows, totals=totals,
                           store=store, stock_warnings=stock_warnings)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def cart_add(product_id: int):
    validate_csrf()
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    qty = max(1, min(10, form_int("qty", 1)))
    if product.in_store_only and not selected_store():
        flash_message("This item is in-store only. Select your store to continue.",
                      "error")
        return redirect(safe_redirect_target(request.form.get("next"),
                                             product.detail_url()))
    if current_user.is_authenticated:
        row = CartItem.query.filter_by(user_id=current_user.id,
                                       product_id=product_id).first()
        if row:
            row.qty = min(10, row.qty + qty)
        else:
            db.session.add(CartItem(user_id=current_user.id,
                                    product_id=product_id, qty=qty))
        db.session.commit()
    else:
        cart = session.get(CART_SESSION_KEY, {})
        pid_str = str(product_id)
        cart[pid_str] = min(10, cart.get(pid_str, 0) + qty)
        session[CART_SESSION_KEY] = cart
        session.modified = True
    flash_message(f"Added {product.name} to your cart.")
    return redirect(safe_redirect_target(request.form.get("next"), "/cart"))


@app.route("/cart/update/<int:product_id>", methods=["POST"])
def cart_update(product_id: int):
    # The cart template posts the product id for both guest and logged-in
    # carts, so resolve the row by (user, product) — CartItem rows are unique
    # per (user_id, product_id) because cart_add merges quantities.
    validate_csrf()
    qty = max(0, min(10, form_int("qty", 1)))
    if current_user.is_authenticated:
        row = CartItem.query.filter_by(user_id=current_user.id,
                                       product_id=product_id).first()
        if not row:
            abort(404)
        if qty == 0:
            db.session.delete(row)
        else:
            row.qty = qty
        db.session.commit()
    else:
        cart = session.get(CART_SESSION_KEY, {})
        pid_str = str(product_id)
        if pid_str in cart:
            if qty == 0:
                del cart[pid_str]
            else:
                cart[pid_str] = qty
            session[CART_SESSION_KEY] = cart
            session.modified = True
    return redirect("/cart")


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
def cart_remove(product_id: int):
    validate_csrf()
    if current_user.is_authenticated:
        CartItem.query.filter_by(user_id=current_user.id,
                                 product_id=product_id).delete()
        db.session.commit()
    else:
        cart = session.get(CART_SESSION_KEY, {})
        cart.pop(str(product_id), None)
        session[CART_SESSION_KEY] = cart
        session.modified = True
    return redirect("/cart")


# ---------------------------------------------------------------------------
# checkout
# ---------------------------------------------------------------------------

def checkout_summary(rows: list[tuple[Product, int]],
                     state: dict[str, Any]) -> dict[str, Any]:
    totals = cart_totals(rows)
    method = state.get("method", "pickup")
    summary = {"rows": rows, "method": method, **totals,
               "store": None, "address": None, "payment": None,
               "contact_name": state.get("contact_name", ""),
               "contact_email": state.get("contact_email", ""),
               "contact_phone": state.get("contact_phone", "")}
    if method == "pickup":
        store = db.session.get(Store, state.get("store_id", ""))
        summary["store"] = store
    else:
        summary["address"] = state.get("address")
        summary["shipping_fee"] = state.get("shipping_fee", 0.0)
        summary["total"] = round(totals["total"] + summary["shipping_fee"], 2)
    if current_user.is_authenticated:
        card = db.session.get(PaymentCard, int(state.get("card_id", 0) or 0))
        summary["payment"] = card.display() if card else state.get("payment", "")
    else:
        summary["payment"] = state.get("payment", "")
    return summary


@app.route("/checkout")
def checkout():
    rows = cart_rows()
    if not rows:
        flash_message("Your cart is empty.")
        return redirect("/")
    return redirect("/checkout/mode")


@app.route("/checkout/mode")
def checkout_mode():
    rows = cart_rows()
    if not rows:
        return redirect("/")
    state = checkout_state()
    return render_template("checkout_mode.html", rows=rows,
                           totals=cart_totals(rows), state=state)


@app.route("/checkout/mode", methods=["POST"])
def checkout_mode_post():
    validate_csrf()
    method = form_str("method", "pickup")
    if method not in ("pickup", "shipping"):
        method = "pickup"
    state = checkout_state()
    state["method"] = method
    save_checkout_state(state)
    if method == "pickup":
        return redirect("/checkout/pickup")
    return redirect("/checkout/shipping")


@app.route("/checkout/pickup", methods=["GET", "POST"])
def checkout_pickup():
    rows = cart_rows()
    if not rows:
        return redirect("/")
    state = checkout_state()
    if request.method == "POST":
        validate_csrf()
        store = db.session.get(Store, form_str("store_id"))
        if not store:
            flash_message("Choose a pickup store to continue.", "error")
            return redirect("/checkout/pickup")
        contact_name = form_str("contact_name")
        contact_email = form_str("contact_email")
        contact_phone = form_str("contact_phone")
        if len(contact_phone) and not re.fullmatch(r"[\d\-\(\)\s\.]{7,20}", contact_phone):
            flash_message("Enter a valid phone number (10 digits).", "error")
            return redirect("/checkout/pickup")
        if not contact_name or "@" not in contact_email:
            flash_message("Enter your full name and a valid email for pickup "
                          "notifications.", "error")
            return redirect("/checkout/pickup")
        state.update({"store_id": store.id, "contact_name": contact_name,
                      "contact_email": contact_email,
                      "contact_phone": contact_phone})
        save_checkout_state(state)
        return redirect("/checkout/payment")
    return render_template("checkout_pickup.html", rows=rows,
                           stores=Store.query.order_by(Store.state, Store.city).all(),
                           state=state, selected_store=selected_store())


@app.route("/checkout/shipping", methods=["GET", "POST"])
def checkout_shipping():
    rows = cart_rows()
    if not rows:
        return redirect("/")
    state = checkout_state()
    if request.method == "POST":
        validate_csrf()
        address = {
            "full_name": form_str("full_name"),
            "line1": form_str("line1"),
            "line2": form_str("line2"),
            "city": form_str("city"),
            "state": form_str("state"),
            "zip": form_str("zip"),
        }
        if current_user.is_authenticated and form_str("save_address") == "on":
            row = Address(user_id=current_user.id, label="Shipping",
                          full_name=address["full_name"], line1=address["line1"],
                          line2=address["line2"], city=address["city"],
                          state=address["state"], zip_code=address["zip"],
                          phone=form_str("phone"))
            db.session.add(row)
            db.session.commit()
        if not all([address["full_name"], address["line1"], address["city"],
                    address["state"], address["zip"]]):
            flash_message("Fill in all required address fields.", "error")
            return redirect("/checkout/shipping")
        if not re.fullmatch(r"\d{5}(-\d{4})?", address["zip"]):
            flash_message("Enter a valid 5-digit ZIP code.", "error")
            return redirect("/checkout/shipping")
        speed = form_str("speed", "standard")
        shipping_fee = {"standard": 0.0, "twoday": 12.99, "nextday": 24.99}.get(speed, 0.0)
        state.update({"address": address, "shipping_speed": speed,
                      "shipping_fee": shipping_fee})
        save_checkout_state(state)
        return redirect("/checkout/payment")
    address = None
    if current_user.is_authenticated:
        address = current_user.default_address()
    return render_template("checkout_shipping.html", rows=rows, state=state,
                           default_address=address)


@app.route("/checkout/payment", methods=["GET", "POST"])
def checkout_payment():
    rows = cart_rows()
    if not rows:
        return redirect("/")
    state = checkout_state()
    if state.get("method") == "pickup" and not state.get("store_id"):
        return redirect("/checkout/pickup")
    if state.get("method") == "shipping" and not state.get("address"):
        return redirect("/checkout/shipping")
    if request.method == "POST":
        validate_csrf()
        selected_card = None
        if current_user.is_authenticated:
            card_id = form_int("card_id", 0)
            if card_id:
                selected_card = PaymentCard.query.filter_by(
                    id=card_id, user_id=current_user.id).first()
                if not selected_card:
                    flash_message("That saved card could not be found.", "error")
                    return redirect("/checkout/payment")
        if selected_card:
            # Pay with a saved card: no manual card entry is required and the
            # order records the saved card's brand and last four digits.
            state.update({
                "card_brand": selected_card.brand,
                "card_last4": selected_card.last4,
                "card_exp": f"{selected_card.exp_month}/{selected_card.exp_year}",
                "card_id": selected_card.id,
            })
            save_checkout_state(state)
            return redirect("/checkout/review")
        card_number = re.sub(r"\D", "", form_str("card_number"))
        if len(card_number) != 16:
            flash_message("Enter a valid 16-digit card number.", "error")
            return redirect("/checkout/payment")
        exp_month = form_str("exp_month")
        exp_year = form_str("exp_year")
        if not (exp_month.isdigit() and 1 <= int(exp_month) <= 12
                and exp_year.isdigit() and len(exp_year) == 4):
            flash_message("Enter a valid card expiration date.", "error")
            return redirect("/checkout/payment")
        cvv = form_str("cvv")
        if not (cvv.isdigit() and len(cvv) in (3, 4)):
            flash_message("Enter a valid 3 or 4 digit security code.", "error")
            return redirect("/checkout/payment")
        state.update({
            "card_brand": form_str("card_brand", "Visa"),
            "card_last4": card_number[-4:],
            "card_exp": f"{exp_month}/{exp_year}",
        })
        if current_user.is_authenticated and form_str("save_card") == "on":
            card = PaymentCard(user_id=current_user.id,
                               brand=form_str("card_brand", "Visa"),
                               last4=card_number[-4:], exp_month=exp_month,
                               exp_year=exp_year)
            db.session.add(card)
            db.session.commit()
            state["card_id"] = card.id
        elif "card_id" in state:
            # A newly entered card replaces any previously selected saved card.
            del state["card_id"]
        save_checkout_state(state)
        return redirect("/checkout/review")
    cards = current_user.cards if current_user.is_authenticated else []
    return render_template("checkout_payment.html", rows=rows, state=state,
                           cards=cards, totals=cart_totals(rows))


@app.route("/checkout/review", methods=["GET", "POST"])
def checkout_review():
    rows = cart_rows()
    if not rows:
        return redirect("/")
    state = checkout_state()
    if not state.get("card_last4"):
        return redirect("/checkout/payment")
    if request.method == "POST":
        validate_csrf()
        order = place_order(rows, state)
        if order:
            clear_checkout_state()
            return redirect(f"/checkout/confirmation?order={order.order_number}")
        flash_message("Could not place the order. Please review your cart.",
                      "error")
        return redirect("/cart")
    summary = checkout_summary(rows, state)
    return render_template("checkout_review.html", summary=summary,
                           state=state)


def place_order(rows: list[tuple[Product, int]],
                state: dict[str, Any]) -> Order | None:
    if not rows:
        return None
    user_id = current_user.id if current_user.is_authenticated else 0
    totals = cart_totals(rows)
    shipping_fee = float(state.get("shipping_fee", 0.0) or 0.0)
    items = [{"product_id": product.product_id, "name": product.name,
              "sku": product.sku, "price": round(product.price, 2), "qty": qty,
              "brand": product.brand}
             for product, qty in rows]
    order_number = "MC" + datetime.utcnow().strftime("%y%m%d") + \
        str(secrets.randbelow(9000) + 1000)
    order = Order(
        order_number=order_number, user_id=user_id,
        status="Processing" if state.get("method") == "pickup" else "Preparing to Ship",
        method=state.get("method", "pickup"),
        store_id=state.get("store_id") if state.get("method") == "pickup" else None,
        ship_to=dump_json(state.get("address", {})),
        payment=f'{state.get("card_brand", "Visa")} ending in {state.get("card_last4", "")}',
        subtotal=totals["subtotal"], tax=totals["tax"],
        shipping_fee=shipping_fee, total=round(totals["total"] + shipping_fee, 2),
        items_json=dump_json(items))
    db.session.add(order)
    # clear the cart
    if user_id:
        CartItem.query.filter_by(user_id=user_id).delete()
    else:
        session.pop(CART_SESSION_KEY, None)
        session.modified = True
    db.session.commit()
    return order


@app.route("/checkout/confirmation")
def checkout_confirmation():
    order_number = request.args.get("order", "")
    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        abort(404)
    return render_template("checkout_confirmation.html", order=order)

# ---------------------------------------------------------------------------
# account / auth
# ---------------------------------------------------------------------------

@app.route("/account/signin", methods=["GET", "POST"])
def signin():
    if current_user.is_authenticated:
        return redirect("/account")
    if request.method == "POST":
        validate_csrf()
        email = form_str("email").lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash_message("Invalid email or password.", "error")
            return redirect("/account/signin")
        login_user(user)
        merge_session_cart_into_user()
        flash_message(f"Welcome back, {user.display_name}!")
        return redirect(safe_redirect_target(request.form.get("next"), "/account"))
    return render_template("signin.html", next=request.args.get("next", ""))


@app.route("/account/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect("/account")
    if request.method == "POST":
        validate_csrf()
        email = form_str("email").lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        display_name = form_str("display_name")
        phone = form_str("phone")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email, re.I):
            flash_message("Enter a valid email address.", "error")
            return redirect("/account/register")
        if len(password) < 8:
            flash_message("Password must be at least 8 characters.", "error")
            return redirect("/account/register")
        if password != confirm:
            flash_message("Passwords do not match.", "error")
            return redirect("/account/register")
        if User.query.filter_by(email=email).first():
            flash_message("An account with that email already exists.", "error")
            return redirect("/account/register")
        user = User(email=email, username=email.split("@")[0],
                    display_name=display_name or email.split("@")[0],
                    phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        merge_session_cart_into_user()
        flash_message("Your Micro Center Insider account is ready.")
        return redirect("/account")
    return render_template("register.html")


@app.route("/account/logout", methods=["POST"])
def logout():
    validate_csrf()
    logout_user()
    return redirect("/")


@app.route("/account")
@login_required
def account_home():
    recent_orders = (Order.query.filter_by(user_id=current_user.id)
                     .order_by(Order.placed_at.desc()).limit(3).all())
    list_count = ListItem.query.filter_by(user_id=current_user.id).count()
    return render_template("account.html", orders=recent_orders,
                           list_count=list_count)


@app.route("/account/profile", methods=["GET", "POST"])
@login_required
def account_profile():
    if request.method == "POST":
        validate_csrf()
        display_name = form_str("display_name")
        phone = form_str("phone")
        if not display_name:
            flash_message("Display name cannot be empty.", "error")
            return redirect("/account/profile")
        if phone and not re.fullmatch(r"[\d\-\(\)\s\.]{7,20}", phone):
            flash_message("Enter a valid phone number.", "error")
            return redirect("/account/profile")
        current_user.display_name = display_name
        current_user.phone = phone
        db.session.commit()
        flash_message("Profile updated.")
        return redirect("/account/profile")
    return render_template("account_profile.html")


@app.route("/account/addresses", methods=["GET", "POST"])
@login_required
def account_addresses():
    if request.method == "POST" and request.form.get("action") == "add":
        validate_csrf()
        full_name = form_str("full_name")
        line1 = form_str("line1")
        city = form_str("city")
        state = form_str("state")
        zip_code = form_str("zip_code")
        if not all([full_name, line1, city, state, zip_code]):
            flash_message("Fill in all required address fields.", "error")
            return redirect("/account/addresses")
        if not re.fullmatch(r"\d{5}(-\d{4})?", zip_code):
            flash_message("Enter a valid 5-digit ZIP code.", "error")
            return redirect("/account/addresses")
        address = Address(user_id=current_user.id, label=form_str("label"),
                           full_name=full_name, line1=line1,
                           line2=form_str("line2"), city=city, state=state,
                           zip_code=zip_code, phone=form_str("phone"))
        db.session.add(address)
        db.session.commit()
        flash_message("Address added.")
        return redirect("/account/addresses")
    return render_template("account_addresses.html",
                           addresses=current_user.addresses)


@app.route("/account/addresses/<int:address_id>/default", methods=["POST"])
@login_required
def address_default(address_id: int):
    validate_csrf()
    for address in current_user.addresses:
        address.is_default = address.id == address_id
    db.session.commit()
    flash_message("Default address updated.")
    return redirect("/account/addresses")


@app.route("/account/addresses/<int:address_id>/delete", methods=["POST"])
@login_required
def address_delete(address_id: int):
    validate_csrf()
    address = next((a for a in current_user.addresses if a.id == address_id), None)
    if address:
        db.session.delete(address)
        db.session.commit()
        flash_message("Address removed.")
    return redirect("/account/addresses")


@app.route("/account/payments", methods=["GET", "POST"])
@login_required
def account_payments():
    if request.method == "POST" and request.form.get("action") == "add":
        validate_csrf()
        card_number = re.sub(r"\D", "", form_str("card_number"))
        exp_month = form_str("exp_month")
        exp_year = form_str("exp_year")
        if len(card_number) != 16:
            flash_message("Enter a valid 16-digit card number.", "error")
            return redirect("/account/payments")
        if not (exp_month.isdigit() and 1 <= int(exp_month) <= 12
                and exp_year.isdigit() and len(exp_year) == 4):
            flash_message("Enter a valid expiration date.", "error")
            return redirect("/account/payments")
        card = PaymentCard(user_id=current_user.id,
                           brand=form_str("card_brand", "Visa"),
                           last4=card_number[-4:], exp_month=exp_month,
                           exp_year=exp_year)
        db.session.add(card)
        db.session.commit()
        flash_message("Payment method added.")
        return redirect("/account/payments")
    return render_template("account_payments.html", cards=current_user.cards)


@app.route("/account/payments/<int:card_id>/default", methods=["POST"])
@login_required
def payment_default(card_id: int):
    validate_csrf()
    for card in current_user.cards:
        card.is_default = card.id == card_id
    db.session.commit()
    flash_message("Default payment method updated.")
    return redirect("/account/payments")


@app.route("/account/payments/<int:card_id>/delete", methods=["POST"])
@login_required
def payment_delete(card_id: int):
    validate_csrf()
    card = next((c for c in current_user.cards if c.id == card_id), None)
    if card:
        db.session.delete(card)
        db.session.commit()
        flash_message("Payment method removed.")
    return redirect("/account/payments")


@app.route("/account/orders")
@login_required
def account_orders():
    orders = (Order.query.filter_by(user_id=current_user.id)
             .order_by(Order.placed_at.desc()).all())
    return render_template("account_orders.html", orders=orders)


@app.route("/account/orders/<order_number>")
@login_required
def account_order_detail(order_number: str):
    order = Order.query.filter_by(order_number=order_number,
                                  user_id=current_user.id).first()
    if not order:
        abort(404)
    return render_template("account_order_detail.html", order=order)


@app.route("/account/orders/<order_number>/cancel", methods=["POST"])
@login_required
def account_order_cancel(order_number: str):
    validate_csrf()
    order = Order.query.filter_by(order_number=order_number,
                                  user_id=current_user.id).first()
    if not order:
        abort(404)
    if order.status in ("Delivered", "Picked Up", "Cancelled"):
        flash_message("This order can no longer be cancelled online.", "error")
        return redirect(f"/account/orders/{order.order_number}")
    order.status = "Cancelled"
    db.session.commit()
    flash_message(f"Order {order.order_number} has been cancelled.")
    return redirect(f"/account/orders/{order.order_number}")


# ---------------------------------------------------------------------------
# lists (wishlist)
# ---------------------------------------------------------------------------

@app.route("/account/lists")
@login_required
def account_lists():
    items = (ListItem.query.filter_by(user_id=current_user.id)
             .order_by(ListItem.id.desc()).all())
    return render_template("account_lists.html", items=items)


@app.route("/list/add/<int:product_id>", methods=["POST"])
def list_add(product_id: int):
    validate_csrf()
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    if not current_user.is_authenticated:
        flash_message("Sign in to add items to your list.", "error")
        return redirect("/account/signin?next=" + product.detail_url())
    existing = ListItem.query.filter_by(user_id=current_user.id,
                                        product_id=product_id).first()
    if existing:
        flash_message("That item is already on your list.", "error")
    else:
        db.session.add(ListItem(user_id=current_user.id, product_id=product_id))
        db.session.commit()
        flash_message(f"Added {product.name} to your list.")
    return redirect(safe_redirect_target(request.form.get("next"),
                                         "/account/lists"))


@app.route("/list/remove/<int:item_id>", methods=["POST"])
@login_required
def list_remove(item_id: int):
    validate_csrf()
    item = ListItem.query.filter_by(id=item_id,
                                    user_id=current_user.id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash_message("Item removed from your list.")
    return redirect("/account/lists")


# ---------------------------------------------------------------------------
# reviews (product page submission)
# ---------------------------------------------------------------------------

@app.route("/product/<int:product_id>/review", methods=["POST"])
def review_add(product_id: int):
    validate_csrf()
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    rating = form_int("rating", 0)
    title = form_str("title")[:200]
    body = form_str("body")[:4000]
    author = (current_user.display_name if current_user.is_authenticated
              else form_str("author") or "Anonymous")
    if not 1 <= rating <= 5:
        flash_message("Select a star rating for your review.", "error")
        return redirect(product.detail_url() + "#tab-reviews")
    if len(body) < 10:
        flash_message("Reviews need at least a couple of sentences.", "error")
        return redirect(product.detail_url() + "#tab-reviews")
    review = Review(product_id=product_id, author=author, rating=rating,
                    title=title, body=body, verified=current_user.is_authenticated,
                    date=datetime.utcnow().strftime("%Y-%m-%d"))
    db.session.add(review)
    product.review_count = (product.review_count or 0) + 1
    ratings = [r.rating for r in
               Review.query.filter_by(product_id=product_id).all()] + [rating]
    product.rating = round(sum(ratings) / len(ratings), 1)
    db.session.commit()
    flash_message("Thanks! Your review has been posted.")
    return redirect(product.detail_url() + "#tab-reviews")


# ---------------------------------------------------------------------------
# health & bootstrap
# ---------------------------------------------------------------------------

@app.route("/site/service/service.aspx")
def service_page():
    return render_template("service.html")


@app.route("/site/content/about_microcenter.aspx")
def about_page():
    return render_template("about.html")


@app.route("/_health")
def health():
    return jsonify({
        "ok": True,
        "site": SITE_SLUG,
        "products": Product.query.count(),
        "stores": Store.query.count(),
        "categories": Category.query.count(),
        "orders": Order.query.count(),
        "users": User.query.count(),
    })


def initialize_database() -> None:
    seed_exists = SEED_DB_PATH.exists()
    runtime_exists = RUNTIME_DB_PATH.exists()

    if not runtime_exists and seed_exists:
        shutil.copy2(SEED_DB_PATH, RUNTIME_DB_PATH)

    db.create_all()

    from seed_data import ensure_seed_data

    ensure_seed_data(force=not seed_exists,
                     runtime_db_path=RUNTIME_DB_PATH,
                     seed_db_path=SEED_DB_PATH,
                     image_root=IMAGE_DIR)


with app.app_context():
    initialize_database()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", SITE_PORT))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False,
            threaded=True)
