#!/usr/bin/env python3
"""Dillard's mirror — department-store catalog, search, bag/checkout, registry,
store locator, credit-card servicing, and account area."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta

from flask import (
    Flask, abort, flash, redirect, render_template, request, session, url_for,
)
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user, logout_user,
)
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "dillards.db")

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-dillards-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log in to manage your Dillard's account."

# The mirror's reference date: seeded "today" is frozen so relative labels
# ("a day ago", "3 days ago") stay stable across runs (see seed_data.py).
MIRROR_DATE = datetime(2026, 9, 22)

STOP_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "is", "are", "be", "by", "from", "how", "what", "which", "that",
    "this", "me", "my", "your", "you", "can", "do", "does", "i", "it",
    "dillards", "dillard's", "dress", "dresses",
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(140), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(40), default="")
    preferred_store = db.Column(db.String(80), default="")
    is_cardholder = db.Column(db.Boolean, default=False)
    rewards_selection = db.Column(db.String(40), default="10% Off Shopping Pass")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def check_password(self, plain):
        return bcrypt.check_password_hash(self.password_hash, plain)


class Address(db.Model):
    __tablename__ = "addresses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    label = db.Column(db.String(40), default="Home")
    line1 = db.Column(db.String(180), nullable=False)
    line2 = db.Column(db.String(180), default="")
    city = db.Column(db.String(90), nullable=False)
    state = db.Column(db.String(20), nullable=False)
    zipcode = db.Column(db.String(12), nullable=False)
    phone = db.Column(db.String(30), default="")
    is_default_shipping = db.Column(db.Boolean, default=False)

    def one_line(self):
        parts = [self.line1]
        if self.line2:
            parts.append(self.line2)
        return ", ".join(parts)


class PaymentMethod(db.Model):
    __tablename__ = "payment_methods"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(40), default="Dillard's Credit Card")
    last4 = db.Column(db.String(4), nullable=False)
    exp_month = db.Column(db.String(2), default="09")
    exp_year = db.Column(db.String(4), default="2029")
    is_default = db.Column(db.Boolean, default=False)


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    nav_label = db.Column(db.String(120), default="")
    kind = db.Column(db.String(10), default="top")  # top / extra / sub


class Brand(db.Model):
    __tablename__ = "brands"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    about = db.Column(db.Text, default="")
    exclusive = db.Column(db.Boolean, default=False)
    letter = db.Column(db.String(2), default="A")

    @property
    def url(self):
        return url_for("brand_page", brand_name=self.slug)


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    pid = db.Column(db.String(20), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(220), nullable=False)
    name = db.Column(db.String(260), nullable=False)
    short_name = db.Column(db.String(260), default="")
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=False)
    category_slug = db.Column(db.String(90), nullable=False, index=True)
    top_slug = db.Column(db.String(40), nullable=False, index=True)
    description = db.Column(db.Text, default="")
    more_details = db.Column(db.Text, default="")
    item_number = db.Column(db.String(20), default="")
    sku_root = db.Column(db.String(30), default="")
    rating = db.Column(db.Float, default=None)
    review_count = db.Column(db.Integer, default=0)
    exclusive = db.Column(db.Boolean, default=False)
    free_shipping = db.Column(db.Boolean, default=False)
    is_new_arrival = db.Column(db.Boolean, default=False)
    main_image = db.Column(db.String(300), default="")
    position = db.Column(db.Integer, default=0)

    brand = db.relationship("Brand")
    variants = db.relationship("Variant", backref="product", order_by="Variant.id")

    @property
    def url(self):
        return f"/p/{self.slug}/{self.pid}"

    @property
    def full_name(self):
        return f"{self.brand.name} {self.short_name or self.name}"

    def colors(self):
        out = []
        seen = set()
        for v in self.variants:
            if v.color and v.color not in seen:
                seen.add(v.color)
                out.append(v)
        return out

    def sizes(self, color=None):
        out = []
        seen = set()
        for v in self.variants:
            if color and v.color != color:
                continue
            if v.size and v.size not in seen:
                seen.add(v.size)
                out.append(v.size)
        return out

    def price(self):
        prices = [v.price for v in self.variants if v.price is not None]
        return min(prices) if prices else None

    def was_price(self):
        was = [v.was_price for v in self.variants if v.was_price]
        return max(was) if was else None

    def on_sale(self):
        return any(v.was_price and v.price and v.was_price > v.price for v in self.variants)


class Variant(db.Model):
    __tablename__ = "variants"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    sku = db.Column(db.String(20), default="")
    size = db.Column(db.String(40), default="")
    color = db.Column(db.String(60), default="")
    nrf_color = db.Column(db.String(40), default="")
    price = db.Column(db.Float, nullable=False)
    was_price = db.Column(db.Float, default=None)
    image = db.Column(db.String(300), default="")


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    author = db.Column(db.String(80), default="")
    title = db.Column(db.String(120), default="")
    body = db.Column(db.Text, default="")
    rating = db.Column(db.Integer, nullable=False, default=5)
    date_label = db.Column(db.String(40), default="")
    position = db.Column(db.Integer, default=0)

    product = db.relationship("Product")


class RatingBreak(db.Model):
    __tablename__ = "rating_breaks"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    stars = db.Column(db.Integer, nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)


class CartItem(db.Model):
    __tablename__ = "cart_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("variants.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    variant = db.relationship("Variant")


class WishlistItem(db.Model):
    __tablename__ = "wishlist_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    product = db.relationship("Product")


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    order_number = db.Column(db.String(30), nullable=False, unique=True)
    placed_at = db.Column(db.DateTime, nullable=False, default=MIRROR_DATE)
    status = db.Column(db.String(40), default="Processing")
    ship_to = db.Column(db.String(300), default="")
    ship_method = db.Column(db.String(60), default="Standard")
    payment_last4 = db.Column(db.String(4), default="")
    payment_kind = db.Column(db.String(40), default="Dillard's Credit Card")
    subtotal = db.Column(db.Float, default=0)
    shipping_total = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    tracking_number = db.Column(db.String(40), default="")
    carrier = db.Column(db.String(40), default="")

    items = db.relationship("OrderItem", backref="order", order_by="OrderItem.id")

    def status_code(self):
        s = (self.status or "").lower()
        if "cancel" in s:
            return "Cancelled"
        if "deliver" in s:
            return "Delivered"
        if "transit" in s:
            return "In Transit"
        if "shipped" in s:
            return "Shipped"
        return self.status


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("variants.id"), nullable=False)
    product_name = db.Column(db.String(260), default="")
    size = db.Column(db.String(40), default="")
    color = db.Column(db.String(60), default="")
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False, default=0)

    variant = db.relationship("Variant")


class Registry(db.Model):
    __tablename__ = "registries"
    id = db.Column(db.Integer, primary_key=True)
    registry_number = db.Column(db.String(20), nullable=False, unique=True)
    owner_first = db.Column(db.String(80), nullable=False)
    owner_last = db.Column(db.String(80), nullable=False)
    co_owner_first = db.Column(db.String(80), default="")
    co_owner_last = db.Column(db.String(80), default="")
    kind = db.Column(db.String(20), default="wedding")  # wedding / baby / gift
    event_date = db.Column(db.DateTime, default=None)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), default=None, index=True)

    items = db.relationship("RegistryItem", backref="registry", order_by="RegistryItem.id")

    def title(self):
        if self.kind == "wedding" and self.co_owner_first:
            return f"{self.owner_first} & {self.co_owner_first}"
        return f"{self.owner_first} {self.owner_last}"


class RegistryItem(db.Model):
    __tablename__ = "registry_items"
    id = db.Column(db.Integer, primary_key=True)
    registry_id = db.Column(db.Integer, db.ForeignKey("registries.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    purchased = db.Column(db.Integer, nullable=False, default=0)
    priority = db.Column(db.String(20), default="must-have")

    product = db.relationship("Product")


class ReturnRequest(db.Model):
    __tablename__ = "return_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_items.id"), nullable=False)
    reason = db.Column(db.String(120), default="")
    method = db.Column(db.String(40), default="Return by Mail")
    status = db.Column(db.String(40), default="Requested")
    created = db.Column(db.DateTime, default=MIRROR_DATE)
    credit_issued = db.Column(db.Float, default=0)

    order_item = db.relationship("OrderItem")
    order = db.relationship("Order")


class CardAccount(db.Model):
    __tablename__ = "card_accounts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    last4 = db.Column(db.String(4), default="1088")
    card_kind = db.Column(db.String(40), default="Dillard's Credit Card")
    credit_limit = db.Column(db.Float, default=2500.0)
    balance = db.Column(db.Float, default=0)
    points = db.Column(db.Integer, default=0)
    minimum_payment = db.Column(db.Float, default=0)
    statement_date = db.Column(db.DateTime, default=MIRROR_DATE)
    payment_due_date = db.Column(db.DateTime, default=MIRROR_DATE)
    reward_tier = db.Column(db.String(60), default="Cardholder")

    @property
    def available_credit(self):
        return round(self.credit_limit - self.balance, 2)


class CardTransaction(db.Model):
    __tablename__ = "card_transactions"
    id = db.Column(db.Integer, primary_key=True)
    card_account_id = db.Column(db.Integer, db.ForeignKey("card_accounts.id"), nullable=False, index=True)
    posted = db.Column(db.DateTime, default=MIRROR_DATE)
    description = db.Column(db.String(180), default="")
    amount = db.Column(db.Float, default=0)
    points = db.Column(db.Integer, default=0)


class CardPayment(db.Model):
    __tablename__ = "card_payments"
    id = db.Column(db.Integer, primary_key=True)
    card_account_id = db.Column(db.Integer, db.ForeignKey("card_accounts.id"), nullable=False, index=True)
    posted = db.Column(db.DateTime, default=MIRROR_DATE)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(60), default="Bank Draft")
    confirmation = db.Column(db.String(20), default="")


class Store(db.Model):
    __tablename__ = "stores"
    id = db.Column(db.Integer, primary_key=True)
    identifier = db.Column(db.String(10), unique=True, nullable=False)
    store_name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(90), nullable=False)
    state = db.Column(db.String(40), nullable=False)
    state_abrev = db.Column(db.String(4), nullable=False)
    zipcode = db.Column(db.String(12), default="")
    address1 = db.Column(db.String(180), default="")
    phone = db.Column(db.String(20), default="")
    latitude = db.Column(db.String(20), default="")
    longitude = db.Column(db.String(20), default="")

    def phone_display(self):
        d = re.sub(r"\D", "", self.phone or "")
        if len(d) == 10:
            return f"({d[:3]}) {d[3:6]}-{d[6:]}"
        return self.phone


class HomeBlock(db.Model):
    """Ordered homepage section rows rendered by the index template."""
    __tablename__ = "home_blocks"
    id = db.Column(db.Integer, primary_key=True)
    block_type = db.Column(db.String(40), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    data = db.Column(db.Text, default="{}")

    def payload(self):
        return json.loads(self.data or "{}")


class StaticPage(db.Model):
    """Frozen copy blocks for content pages (returns, gift cards, credit card...)."""
    __tablename__ = "static_pages"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(160), default="")
    body = db.Column(db.Text, default="{}")

    def payload(self):
        return json.loads(self.body or "{}")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_size_order(sizes):
    """Dillard's lists apparel sizes in numeric order; keep the captured order."""
    return sizes


def scored_search(query, products):
    """Token-overlap scored search; never strict AND (see seed-database skill)."""
    tokens = [t.lower() for t in re.split(r"[^a-zA-Z0-9']+", query or "")
              if t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return products
    scored = []
    for product in products:
        brand = (product.brand.name or "").lower()
        text = " ".join([product.name or "", brand, product.description or "",
                         product.category_slug or "", product.top_slug or "",
                         (product.more_details or "")]).lower()
        score = 0
        for token in tokens:
            if token in brand:
                score += 3
            elif token in text:
                score += 1
        if score > 0:
            scored.append((product, score))
    scored.sort(key=lambda pair: (-pair[1], pair[0].position, pair[0].id))
    return [p for p, _ in scored]


def category_products(slug):
    return (Product.query.filter_by(category_slug=slug)
            .order_by(Product.position, Product.id).all())


def top_nav_label(top):
    category = Category.query.filter_by(slug=top).first()
    return category.nav_label if category else top.capitalize()


def top_products(top):
    return (Product.query.filter_by(top_slug=top)
            .order_by(Product.position, Product.id).all())


def subcategories_for(top):
    return (Category.query.filter_by(kind="sub")
            .filter(Category.slug.startswith(top + "-"))
            .order_by(Category.name).all())


def cart_count(user):
    if not user or not user.is_authenticated:
        return 0
    return sum(item.quantity for item in CartItem.query.filter_by(user_id=user.id))


@app.context_processor
def inject_globals():
    tops = Category.query.filter(Category.kind.in_(["top", "extra"])).order_by(
        Category.id).all()
    nav = []
    for c in Category.query.filter_by(kind="top").order_by(Category.id).all():
        nav.append({"category": c, "subs": subcategories_for(c.slug)})
    for c in Category.query.filter_by(kind="extra").order_by(Category.id).all():
        nav.append({"category": c, "subs": subcategories_for(c.slug)})
    return {
        "top_categories": [n["category"] for n in nav if n["category"].kind == "top"],
        "extra_categories": [n["category"] for n in nav if n["category"].kind == "extra"],
        "nav": nav,
        "cart_count": cart_count(current_user),
        "mirror_date": MIRROR_DATE,
    }


def stars_for(rating):
    """Split a rating into full/half/empty star icons."""
    rating = rating or 0
    full = int(rating)
    half = 1 if rating - full >= 0.5 else 0
    return {"full": full, "half": half, "empty": 5 - full - half}


app.jinja_env.filters["stars"] = stars_for


# ---------------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    blocks = HomeBlock.query.order_by(HomeBlock.position, HomeBlock.id).all()
    hero = [b for b in blocks if b.block_type == "hero"]
    tiles = [b for b in blocks if b.block_type == "tile"]
    feature_products = []
    for block in blocks:
        if block.block_type == "product_rail":
            feature_products = list(
                Product.query.filter_by(is_new_arrival=True)
                .order_by(Product.position, Product.id).limit(8))
    return render_template("index.html", hero=hero, blocks=tiles, feature_products=feature_products)


# ---------------------------------------------------------------------------
# Category / PLP
# ---------------------------------------------------------------------------

SORTS = {
    "popular": "Popular Items",
    "priceLow": "Price Low To High",
    "priceHigh": "Price High To Low",
    "topRated": "Top Rated",
    "newest": "Newest",
    "sale": "Sale",
}

PLP_PAGE_SIZE = 24


@app.route("/c/<slug>", methods=["GET", "POST"])
def category_page(slug):
    if slug == "DillardsCard":
        return render_template("creditcard.html", page=StaticPage.query.filter_by(slug="dillards_card").first())
    if slug == "returns":
        return render_template("returns.html", page=StaticPage.query.filter_by(slug="returns").first())
    if slug == "giftcard":
        return render_template("giftcards.html", page=StaticPage.query.filter_by(slug="gift_cards").first())
    if slug == "customerservice":
        # footer email / text sign-up forms post here; confirm like upstream
        if request.method == "POST":
            contact = ((request.form.get("email_signup") or "")
                       + (request.form.get("text_signup") or "")).strip()
            if contact:
                flash("Thanks for signing up! Watch for updates from Dillard's.")
            return redirect(url_for("category_page", slug="customerservice"))
        return render_template("customerservice.html", page=StaticPage.query.filter_by(slug="customer_service").first())
    if slug == "shopbybrand":
        brands = Brand.query.order_by(Brand.name).all()
        by_letter = {}
        for b in brands:
            by_letter.setdefault(b.letter, []).append(b)
        return render_template("brands_directory.html", by_letter=sorted(by_letter.items()))
    if slug == "exclusive-brands":
        brands = Brand.query.filter_by(exclusive=True).order_by(Brand.name).all()
        return render_template("exclusive_brands.html", brands=brands)
    if slug == "just-for-you":
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=request.full_path))
        products = (Product.query.filter_by(exclusive=True)
                    .order_by(Product.position).limit(24).all())
        return render_template("just_for_you.html", products=products)
    if slug == "back-in-stock":
        products = (Product.query.order_by(Product.position.desc()).limit(24).all())
        return render_template("back_in_stock.html", products=products)
    if slug == "limited-availability":
        products = (Product.query.filter(Product.review_count > 0)
                    .order_by(Product.position).limit(24).all())
        return render_template("limited_availability.html", products=products)
    if slug == "sitemap":
        return render_template("sitemap.html")
    if slug == "faqs-notices-policies":
        return render_template("faqs.html", page=StaticPage.query.filter_by(slug="customer_service").first())
    if slug == "about-dillards-company-history":
        return render_template("about.html")

    category = Category.query.filter_by(slug=slug).first()
    if category is None:
        abort(404)
    if category.kind in ("top", "extra"):
        subs = subcategories_for(slug)
        featured = (top_products(slug)[:12] if slug != "sale-clearance"
                    else _sale_products()[:12])
        return render_template(
            "category_landing.html", category=category, subs=subs, featured=featured)
    # PLP for a subcategory
    return plp_response(category, None)


def _sale_products():
    products = Product.query.order_by(Product.position, Product.id).all()
    return [p for p in products if p.on_sale()]


def parse_facet(facet):
    if not facet:
        return None
    if facet in ("sale", "new-arrivals"):
        return facet, ""
    m = re.match(r"^([a-z\-]+)[_](.+)$", facet)
    if not m:
        return None
    return m.group(1), m.group(2)


def facet_norm(value):
    """Normalize a size/color for facet URLs: spaces and slashes both map to
    '-' so a value like 'King/California King' or 'Multi/Misc' produces one
    path segment (and matches back symmetrically)."""
    return (value or "").replace(" ", "-").replace("/", "-").lower()


@app.route("/c/<slug>/<facet>")
def category_facet_page(slug, facet):
    if facet == "giftcard" or slug == "DillardsCard":
        abort(404)
    category = Category.query.filter_by(slug=slug).first()
    # 'hidden' categories (the Sale and Clearance landing) render as PLPs
    # and their facet links must resolve just like a subcategory's
    if category is None or category.kind not in ("sub", "hidden"):
        abort(404)
    return plp_response(category, facet)


def plp_response(category, facet):
    products = category_products(category.slug)
    active = {}
    if facet:
        parsed = parse_facet(facet)
        if parsed:
            name, value = parsed
            if name == "sale":
                products = [p for p in products if p.on_sale()]
                active["sale"] = "Sale"
            elif name == "new-arrivals":
                products = [p for p in products if p.is_new_arrival]
                active["new-arrivals"] = "New Arrivals"
            elif name == "brand":
                brand = Brand.query.filter_by(slug=value).first()
                if brand:
                    products = [p for p in products if p.brand_id == brand.id]
                    active["brand"] = brand.name
            elif name == "size":
                products = [p for p in products
                            if any(v.size and facet_norm(v.size) == facet_norm(value)
                                   for v in p.variants)]
                active["size"] = next(
                    (v.size for p in products for v in p.variants
                     if v.size and facet_norm(v.size) == facet_norm(value)), value)
            elif name == "color":
                products = [p for p in products
                            if any(v.nrf_color and facet_norm(v.nrf_color) == facet_norm(value)
                                   for v in p.variants)]
                active["color"] = next(
                    (v.nrf_color for p in products for v in p.variants
                     if v.nrf_color and facet_norm(v.nrf_color) == facet_norm(value)),
                    value.replace("-", " ").title())
            elif name == "exclusive":
                products = [p for p in products if p.exclusive]
                active["exclusive"] = "Dillard's Exclusive"
    sort_key = request.args.get("orderBy", "popular")
    sort_key = sort_key if sort_key in SORTS else "popular"
    if sort_key == "priceLow":
        products = sorted(products, key=lambda p: (p.price() or 1e9))
    elif sort_key == "priceHigh":
        products = sorted(products, key=lambda p: (-(p.price() or 0)))
    elif sort_key == "topRated":
        products = sorted(products, key=lambda p: (-(p.rating or 0), -(p.review_count or 0)))
    elif sort_key == "newest":
        products = sorted(products, key=lambda p: (-(1 if p.is_new_arrival else 0), p.position))
    elif sort_key == "sale":
        products = sorted(products, key=lambda p: (0 if p.on_sale() else 1, p.position))
    page = request.args.get("page", 1, type=int)
    page = max(1, page)
    total = len(products)
    pages = max(1, -(-total // PLP_PAGE_SIZE))
    products = products[(page - 1) * PLP_PAGE_SIZE: page * PLP_PAGE_SIZE]

    # facet menus
    brand_counts = {}
    brand_slugs = {}
    for p in category_products(category.slug):
        brand_counts.setdefault(p.brand.name, 0)
        brand_counts[p.brand.name] += 1
        brand_slugs[p.brand.name] = p.brand.slug
    size_list = []
    for p in category_products(category.slug):
        for s in p.sizes():
            if s not in size_list:
                size_list.append(s)
    color_list = []
    for p in category_products(category.slug):
        for v in p.variants:
            if v.nrf_color and v.nrf_color not in color_list:
                color_list.append(v.nrf_color)
    return render_template(
        "plp.html", category=category, products=products, active=active,
        sort_key=sort_key, sort_labels=SORTS, page=page, pages=pages, total=total,
        brand_facets=[(brand_slugs[name], name, count)
                      for name, count in sorted(brand_counts.items())],
        size_list=size_list,
        color_list=sorted(set(color_list)),
        subs=subcategories_for(category.slug.split("-")[0]),
        top_category=Category.query.filter_by(
            slug=category.slug.split("-")[0]).first(),
        top_nav_label=top_nav_label(category.slug.split("-")[0]))


# ---------------------------------------------------------------------------
# Product detail
# ---------------------------------------------------------------------------

@app.route("/p/<slug>/<pid>")
def product_detail(slug, pid):
    product = Product.query.filter_by(pid=pid).first_or_404()
    if product.slug != slug:
        return redirect(product.url)
    reviews = (Review.query.filter_by(product_id=product.id)
               .order_by(Review.position, Review.id).all())
    breaks = {b.stars: b.count for b in RatingBreak.query.filter_by(product_id=product.id)}
    colors = product.colors()
    sizes = product.sizes()
    selected_color_name = request.args.get("color") or (colors[0].color if colors else "")
    selected_color = next((c for c in colors if c.color == selected_color_name), None)
    if selected_color is None and colors:
        selected_color = colors[0]
        selected_color_name = colors[0].color
    selected_size = request.args.get("size") or (sizes[0] if sizes else "")
    if selected_size and selected_color is not None:
        available = product.sizes(selected_color.color)
        if available and selected_size not in available:
            selected_size = available[0]
    # Upstream renders a price range for multi-price items (CHANEL COCO
    # MADEMOISELLE shows "$154.00 - $270.00") until a variant is picked; an
    # explicit ?size=/?color= selection pins the price to that variant.
    variant_prices = sorted({v.price for v in product.variants if v.price is not None})
    price_low = variant_prices[0] if variant_prices else None
    price_high = variant_prices[-1] if len(variant_prices) > 1 else None
    explicit_price = None
    if request.args.get("size"):
        explicit_variant = next((v for v in product.variants
                                 if v.size == request.args.get("size")
                                 and (not selected_color_name or v.color in (None, selected_color_name))), None)
        explicit_price = explicit_variant.price if explicit_variant else None
    category = Category.query.filter_by(slug=product.category_slug).first()
    category_name = category.name if category else product.category_slug.replace("-", " ").title()
    also_like = [p for p in category_products(product.category_slug)
                 if p.id != product.id][:6]
    store = Store.query.first()
    return render_template(
        "product.html", product=product, reviews=reviews, breaks=breaks,
        colors=colors, sizes=sizes, selected_color=selected_color,
        selected_color_name=selected_color_name, selected_size=selected_size,
        price_low=price_low, price_high=price_high, explicit_price=explicit_price,
        category_name=category_name, also_like=also_like, store=store,
        top_label=top_nav_label(product.top_slug))


@app.route("/p/<slug>/<pid>/reviews")
def product_reviews(slug, pid):
    product = Product.query.filter_by(pid=pid).first_or_404()
    reviews = (Review.query.filter_by(product_id=product.id)
               .order_by(Review.position, Review.id).all())
    stars_filter = request.args.get("stars", type=int)
    filtered_reviews = reviews
    if stars_filter:
        filtered_reviews = [r for r in reviews if r.rating == stars_filter]
    breaks = {b.stars: b.count for b in RatingBreak.query.filter_by(product_id=product.id)}
    return render_template("product_reviews.html", product=product,
                           reviews=reviews, filtered_reviews=filtered_reviews,
                           breaks=breaks)


@app.route("/p/<slug>/<pid>/reviews/new", methods=["GET", "POST"])
def write_review(slug, pid):
    product = Product.query.filter_by(pid=pid).first_or_404()
    if request.method == "POST":
        rating = request.form.get("rating", type=int)
        title = (request.form.get("title") or "").strip()[:120]
        body = (request.form.get("body") or "").strip()[:2000]
        author = (request.form.get("author") or "").strip()[:80]
        errors = []
        if not rating or not 1 <= rating <= 5:
            errors.append("Select a star rating.")
        if len(body) < 10:
            errors.append("Write at least 10 characters in your review.")
        if errors:
            return render_template("write_review.html", product=product, errors=errors)
        next_pos = (db.session.query(db.func.max(Review.position))
                    .filter_by(product_id=product.id).scalar() or 0) + 1
        db.session.add(Review(product_id=product.id, rating=rating, title=title,
                              body=body, author=author or "Anonymous",
                              date_label="today", position=next_pos))
        product.review_count = (product.review_count or 0) + 1
        total = (product.rating or 0) * (product.review_count - 1) + rating
        product.rating = round(total / product.review_count, 4)
        db.session.commit()
        flash("Thank you! Your review has been submitted.")
        return redirect(product.url + "#reviews")
    return render_template("write_review.html", product=product, errors=[])


# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------

@app.route("/brand/<brand_name>")
def brand_page(brand_name):
    name = brand_name.replace("+", " ")
    brand = Brand.query.filter_by(slug=brand_name).first() or Brand.query.filter_by(name=name).first()
    if brand is None:
        abort(404)
    products = (Product.query.filter_by(brand_id=brand.id)
                .order_by(Product.position, Product.id).all())
    return render_template("brand.html", brand=brand, products=products)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@app.route("/search-term")
@app.route("/search-term/<path:query>")
def search(query=None):
    q = (query or request.args.get("q") or request.args.get("searchTerm") or "").strip().replace("+", " ")
    if not q:
        return redirect("/")
    products = scored_search(q, Product.query.all())
    total = len(products)
    sort_key = request.args.get("orderBy", "popular")
    if sort_key == "priceLow":
        products = sorted(products, key=lambda p: (p.price() or 1e9))
    elif sort_key == "priceHigh":
        products = sorted(products, key=lambda p: (-(p.price() or 0)))
    return render_template("search.html", q=q, products=products, total=total,
                           sort_key=sort_key, sort_labels=SORTS)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            target = request.args.get("next")
            if target and target.startswith("/"):
                return redirect(target)
            return redirect(url_for("account"))
        flash("Email or password is incorrect.")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        first = (request.form.get("first_name") or "").strip()
        last = (request.form.get("last_name") or "").strip()
        errors = []
        if User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if not email or "@" not in email:
            errors.append("Enter a valid email address.")
        if not first or not last:
            errors.append("Enter your first and last name.")
        if errors:
            return render_template("register.html", errors=errors)
        user = User(email=email, password_hash=bcrypt.generate_password_hash(password).decode(),
                    first_name=first, last_name=last)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome to Dillard's! Your account has been created.")
        return redirect(url_for("account"))
    return render_template("register.html", errors=[])


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


# ---------------------------------------------------------------------------
# Account area
# ---------------------------------------------------------------------------

@app.route("/account")
@login_required
def account():
    orders = (Order.query.filter_by(user_id=current_user.id)
              .order_by(Order.placed_at.desc()).all())
    wishlist = (WishlistItem.query.filter_by(user_id=current_user.id)
                .order_by(WishlistItem.id).all())
    card = CardAccount.query.filter_by(user_id=current_user.id).first()
    returns_ = (ReturnRequest.query.filter_by(user_id=current_user.id)
                .order_by(ReturnRequest.created.desc()).all())
    return render_template("account.html", orders=orders, wishlist=wishlist,
                           card=card, returns_=returns_)


@app.route("/account/orders")
@login_required
def account_orders():
    orders = (Order.query.filter_by(user_id=current_user.id)
              .order_by(Order.placed_at.desc()).all())
    return render_template("account_orders.html", orders=orders)


@app.route("/account/orders/<int:order_id>")
@login_required
def account_order_detail(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    return render_template("account_order_detail.html", order=order)


@app.route("/account/wishlist")
@login_required
def account_wishlist():
    items = (WishlistItem.query.filter_by(user_id=current_user.id)
             .order_by(WishlistItem.id).all())
    return render_template("account_wishlist.html", items=items)


@app.route("/account/returns")
@login_required
def account_returns():
    returns_ = (ReturnRequest.query.filter_by(user_id=current_user.id)
                .order_by(ReturnRequest.created.desc()).all())
    return render_template("account_returns.html", returns_=returns_)


@app.route("/account/returns/new/<int:order_id>", methods=["GET", "POST"])
@login_required
def new_return(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    if request.method == "POST":
        item_id = request.form.get("order_item_id", type=int)
        reason = (request.form.get("reason") or "").strip()
        method = request.form.get("method", "Return by Mail")
        item = OrderItem.query.filter_by(id=item_id, order_id=order.id).first()
        if item is None or not reason:
            return render_template("new_return.html", order=order, error="Select an item and a reason.")
        rr = ReturnRequest(user_id=current_user.id, order_id=order.id,
                           order_item_id=item.id, reason=reason, method=method,
                           status="Requested", credit_issued=round(item.price * item.quantity, 2))
        db.session.add(rr)
        db.session.commit()
        flash("Your return has been requested. Watch your email for the shipping label.")
        return redirect(url_for("account_returns"))
    return render_template("new_return.html", order=order, error=None)


@app.route("/account/paybill", methods=["GET", "POST"])
@login_required
def pay_bill():
    card = CardAccount.query.filter_by(user_id=current_user.id).first()
    if card is None:
        abort(404)
    if request.method == "POST":
        amount = request.form.get("amount", type=float)
        if amount is None or amount <= 0:
            return render_template("account_paybill.html", card=card,
                                   error="Enter a payment amount greater than $0.")
        if amount > card.balance:
            amount = card.balance
        card.balance = round(card.balance - amount, 2)
        confirmation = f"PMT-{MIRROR_DATE.strftime('%y%m%d')}-{card.id}{(CardPayment.query.count() + 1) % 10000:04d}"
        db.session.add(CardPayment(card_account_id=card.id, posted=MIRROR_DATE,
                                   amount=round(amount, 2),
                                   method=request.form.get("method", "Bank Draft"),
                                   confirmation=confirmation))
        db.session.commit()
        flash(f"Payment of ${amount:,.2f} received. Confirmation {confirmation}.")
        return redirect(url_for("pay_bill"))
    payments = (CardPayment.query.filter_by(card_account_id=card.id)
                .order_by(CardPayment.posted.desc()).all())
    transactions = (CardTransaction.query.filter_by(card_account_id=card.id)
                    .order_by(CardTransaction.posted.desc(), CardTransaction.id.desc()).all())
    return render_template("account_paybill.html", card=card, payments=payments,
                           transactions=transactions, error=None)


@app.route("/account/profile", methods=["GET", "POST"])
@login_required
def account_profile():
    if request.method == "POST":
        first = (request.form.get("first_name") or "").strip()
        last = (request.form.get("last_name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        store_id = request.form.get("preferred_store")
        store = Store.query.filter_by(identifier=store_id).first() if store_id else None
        current_user.first_name = first or current_user.first_name
        current_user.last_name = last or current_user.last_name
        current_user.phone = phone
        current_user.preferred_store = f"{store.store_name}, {store.city}, {store.state_abrev}" if store else ""
        db.session.commit()
        flash("Your profile has been updated.")
        return redirect(url_for("account_profile"))
    return render_template("account_profile.html",
                           stores=Store.query.order_by(Store.state, Store.city).all())


@app.route("/account/addresses")
@login_required
def account_addresses():
    addresses = Address.query.filter_by(user_id=current_user.id).order_by(
        Address.is_default_shipping.desc(), Address.id).all()
    return render_template("account_addresses.html", addresses=addresses)


# ---------------------------------------------------------------------------
# Wishlist / registry item actions
# ---------------------------------------------------------------------------

@app.route("/wishlist/add/<pid>", methods=["POST"])
@login_required
def wishlist_add(pid):
    product = Product.query.filter_by(pid=pid).first_or_404()
    exists = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if not exists:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=product.id))
        db.session.commit()
        flash(f"{product.full_name} was added to your Wish List.")
    else:
        flash("That item is already on your Wish List.")
    return redirect(request.form.get("next") or product.url)


@app.route("/wishlist/remove/<int:item_id>", methods=["POST"])
@login_required
def wishlist_remove(item_id):
    item = WishlistItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    name = item.product.full_name
    db.session.delete(item)
    db.session.commit()
    flash(f"{name} was removed from your Wish List.")
    return redirect(url_for("account_wishlist"))


@app.route("/registry/add/<pid>", methods=["POST"])
def registry_add(pid):
    product = Product.query.filter_by(pid=pid).first_or_404()
    registry_id = request.form.get("registry_id", type=int)
    registry = Registry.query.filter_by(id=registry_id).first()
    if registry is None and current_user.is_authenticated:
        # without an explicit target, the most recently created registry wins
        registry = (Registry.query.filter_by(user_id=current_user.id)
                    .order_by(Registry.id.desc()).first())
    if registry is None:
        flash("Log in and create a registry first to save items.")
        return redirect(url_for("registry_landing"))
    exists = RegistryItem.query.filter_by(registry_id=registry.id, product_id=product.id).first()
    if not exists:
        db.session.add(RegistryItem(registry_id=registry.id, product_id=product.id,
                                    quantity=1, priority="must-have"))
        db.session.commit()
        flash(f"{product.full_name} was added to registry {registry.registry_number}.")
    else:
        flash("That item is already on the registry.")
    return redirect(request.form.get("next") or product.url)


# ---------------------------------------------------------------------------
# Bag / checkout
# ---------------------------------------------------------------------------

@app.route("/bag")
def bag():
    items = []
    subtotal = 0
    if current_user.is_authenticated:
        rows = CartItem.query.filter_by(user_id=current_user.id).order_by(CartItem.id).all()
        for row in rows:
            items.append({"row": row, "product": row.variant.product, "variant": row.variant})
            subtotal += row.variant.price * row.quantity
    shipping = 0 if subtotal >= 150 else (8.95 if subtotal > 0 else 0)
    return render_template("bag.html", items=items, subtotal=subtotal, shipping=shipping)


@app.route("/bag/add/<pid>", methods=["POST"])
def bag_add(pid):
    product = Product.query.filter_by(pid=pid).first_or_404()
    if not current_user.is_authenticated:
        return redirect(url_for("login", next=product.url))
    size = request.form.get("size") or ""
    color = request.form.get("color") or ""
    quantity = max(1, request.form.get("quantity", 1, type=int))
    variant = None
    for v in product.variants:
        if (v.size or "") == size and (v.color or "") == color:
            variant = v
            break
    if variant is None:
        variant = product.variants[0] if product.variants else None
    if variant is None:
        abort(400)
    row = CartItem.query.filter_by(user_id=current_user.id, variant_id=variant.id).first()
    if row:
        row.quantity += quantity
    else:
        db.session.add(CartItem(user_id=current_user.id, variant_id=variant.id, quantity=quantity))
    db.session.commit()
    flash(f"{product.full_name} was added to your bag.")
    return redirect(url_for("bag"))


@app.route("/bag/update/<int:row_id>", methods=["POST"])
def bag_update(row_id):
    row = CartItem.query.filter_by(id=row_id, user_id=current_user.id).first_or_404()
    quantity = request.form.get("quantity", type=int)
    if quantity is None or quantity < 1:
        db.session.delete(row)
    else:
        row.quantity = quantity
    db.session.commit()
    return redirect(url_for("bag"))


@app.route("/bag/remove/<int:row_id>", methods=["POST"])
def bag_remove(row_id):
    row = CartItem.query.filter_by(id=row_id, user_id=current_user.id).first_or_404()
    db.session.delete(row)
    db.session.commit()
    return redirect(url_for("bag"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    rows = CartItem.query.filter_by(user_id=current_user.id).order_by(CartItem.id).all()
    if not rows:
        return redirect(url_for("bag"))
    subtotal = sum(r.variant.price * r.quantity for r in rows)
    shipping = 0 if subtotal >= 150 else 8.95
    addresses = Address.query.filter_by(user_id=current_user.id).order_by(
        Address.is_default_shipping.desc(), Address.id).all()
    payments = PaymentMethod.query.filter_by(user_id=current_user.id).order_by(
        PaymentMethod.is_default.desc(), PaymentMethod.id).all()
    # the same tax the order placement charges (6.5% of subtotal), so the
    # checkout preview matches the order confirmation total
    preview_tax = round(subtotal * 0.065, 2)
    if request.method == "POST":
        address_id = request.form.get("address_id", type=int)
        payment_id = request.form.get("payment_id", type=int)
        address = Address.query.filter_by(id=address_id, user_id=current_user.id).first()
        payment = PaymentMethod.query.filter_by(id=payment_id, user_id=current_user.id).first()
        if address is None or payment is None:
            return render_template("checkout.html", rows=rows, subtotal=subtotal,
                                   shipping=shipping, addresses=addresses, payments=payments,
                                   error="Select a shipping address and a payment method.")
        tax = round(subtotal * 0.065, 2)
        total = round(subtotal + shipping + tax, 2)
        order_number = "D" + MIRROR_DATE.strftime("%y%m%d") + f"{(Order.query.count() + 1) % 10000:04d}"
        order = Order(user_id=current_user.id, order_number=order_number,
                      placed_at=MIRROR_DATE, status="Processing",
                      ship_to=f"{address.line1}, {address.city}, {address.state} {address.zipcode}",
                      payment_last4=payment.last4, payment_kind=payment.kind,
                      subtotal=subtotal, shipping_total=shipping, tax=tax, total=total,
                      tracking_number="", carrier="")
        db.session.add(order)
        db.session.flush()
        for r in rows:
            v = r.variant
            db.session.add(OrderItem(order_id=order.id, variant_id=v.id,
                                      product_name=v.product.full_name,
                                      size=v.size, color=v.color,
                                      quantity=r.quantity, price=v.price))
            db.session.delete(r)
        # Dillard's card purchases earn 2 points per $1
        if payment.kind == "Dillard's Credit Card":
            card = CardAccount.query.filter_by(user_id=current_user.id).first()
            if card:
                card.points += int(round(subtotal * 2))
                card.balance = round(card.balance + total, 2)
                db.session.add(CardTransaction(
                    card_account_id=card.id, posted=MIRROR_DATE,
                    description=f"Dillards.com order {order_number}", amount=total,
                    points=int(round(subtotal * 2))))
        db.session.commit()
        return redirect(url_for("order_confirmation", order_id=order.id))
    return render_template("checkout.html", rows=rows, subtotal=subtotal,
                           shipping=shipping, preview_tax=preview_tax,
                           addresses=addresses, payments=payments,
                           error=None)


@app.route("/order-confirmation/<int:order_id>")
@login_required
def order_confirmation(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    return render_template("order_confirmation.html", order=order)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@app.route("/registry")
def registry_landing():
    return render_template("registry_landing.html")


@app.route("/registry/search", methods=["GET", "POST"])
def registry_search():
    registries = []
    if (request.method == "POST" or request.args.get("first_name")
            or request.args.get("last_name") or request.args.get("registry_number")):
        first = (request.values.get("first_name") or "").strip()
        last = (request.values.get("last_name") or "").strip()
        number = (request.values.get("registry_number") or "").strip()
        query = Registry.query
        if number:
            query = query.filter(Registry.registry_number.ilike(f"%{number}%"))
        if first:
            query = query.filter(Registry.owner_first.ilike(f"%{first}%"))
        if last:
            query = query.filter(Registry.owner_last.ilike(f"%{last}%"))
        if not (first or last or number):
            registries = []
        else:
            registries = query.order_by(Registry.event_date).all()
    return render_template("registry_search.html", registries=registries)


@app.route("/registry/<registry_number>")
def registry_detail(registry_number):
    registry = Registry.query.filter_by(registry_number=registry_number).first_or_404()
    return render_template("registry_detail.html", registry=registry)


@app.route("/registry/create", methods=["GET", "POST"])
@login_required
def registry_create():
    if request.method == "POST":
        kind = request.form.get("kind", "wedding")
        first = (request.form.get("first_name") or "").strip()
        last = (request.form.get("last_name") or "").strip() or current_user.last_name
        co_first = (request.form.get("co_first_name") or "").strip()
        event_date = request.form.get("event_date")
        if not first:
            return render_template("registry_create.html", error="Enter a first name.")
        number = f"{kind[:1].upper()}{MIRROR_DATE.strftime('%y%m')}{(Registry.query.count() + 101):04d}"
        parsed = None
        if event_date:
            try:
                parsed = datetime.strptime(event_date, "%Y-%m-%d")
            except ValueError:
                parsed = None
        registry = Registry(registry_number=number, owner_first=first, owner_last=last,
                            co_owner_first=co_first, co_owner_last="",
                            kind=kind, event_date=parsed, user_id=current_user.id)
        db.session.add(registry)
        db.session.commit()
        flash(f"Registry {number} created. Add items from any product page!")
        return redirect(url_for("registry_detail", registry_number=number))
    return render_template("registry_create.html", error=None)


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------

@app.route("/stores")
def stores():
    states = (db.session.query(Store.state, Store.state_abrev)
              .group_by(Store.state, Store.state_abrev).order_by(Store.state).all())
    selected = request.args.get("state")
    state_stores = []
    if selected:
        state_stores = Store.query.filter_by(state_abrev=selected).order_by(Store.city).all()
    return render_template("stores.html", states=states, selected=selected,
                           stores=state_stores)


@app.route("/stores/all")
def stores_all():
    groups = {}
    for store in Store.query.order_by(Store.state, Store.city, Store.store_name).all():
        groups.setdefault(store.state, []).append(store)
    return render_template("stores_all.html", groups=sorted(groups.items()))


@app.route("/stores/<identifier>")
def store_detail(identifier):
    store = Store.query.filter_by(identifier=identifier).first_or_404()
    nearby = Store.query.filter_by(state=store.state).filter(Store.id != store.id).limit(4).all()
    return render_template("store_detail.html", store=store, nearby=nearby)


# ---------------------------------------------------------------------------
# Credit card apply flow
# ---------------------------------------------------------------------------

@app.route("/creditcard/apply", methods=["GET", "POST"])
def creditcard_apply():
    if request.method == "POST":
        required = ["first_name", "last_name", "email", "address1", "city", "state", "zip"]
        values = {k: (request.form.get(k) or "").strip() for k in required}
        errors = [k for k, v in values.items() if not v]
        if errors:
            return render_template("creditcard_apply.html", errors=errors, values=values)
        reference = "APP-" + MIRROR_DATE.strftime("%y%m%d") + f"{(db.session.query(db.func.max(CreditApplication.id)).scalar() or 0) + 1:04d}"
        db.session.add(CreditApplication(
            first_name=values["first_name"], last_name=values["last_name"],
            email=values["email"], address1=values["address1"],
            city=values["city"], state=values["state"], zip=values["zip"],
            income=request.form.get("income", ""),
            reference=reference, status="Received",
            submitted=MIRROR_DATE))
        db.session.commit()
        return render_template("creditcard_status.html", reference=reference)
    return render_template("creditcard_apply.html", errors=[], values={})


class CreditApplication(db.Model):
    __tablename__ = "credit_applications"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), default="")
    last_name = db.Column(db.String(80), default="")
    email = db.Column(db.String(140), default="")
    address1 = db.Column(db.String(180), default="")
    city = db.Column(db.String(90), default="")
    state = db.Column(db.String(20), default="")
    zip = db.Column(db.String(12), default="")
    income = db.Column(db.String(40), default="")
    reference = db.Column(db.String(20), default="")
    status = db.Column(db.String(30), default="Received")
    submitted = db.Column(db.DateTime, default=MIRROR_DATE)


@app.route("/creditcard/status")
def creditcard_status():
    reference = request.args.get("reference", "")
    application = CreditApplication.query.filter_by(reference=reference).first()
    return render_template("creditcard_status.html", application=application, reference=reference)


# ---------------------------------------------------------------------------
# Gift cards
# ---------------------------------------------------------------------------

@app.route("/giftcards/purchase", methods=["GET", "POST"])
def giftcard_purchase():
    if request.method == "POST":
        amount = request.form.get("amount", type=float)
        recipient = (request.form.get("recipient") or "").strip()
        errors = []
        if amount is None or amount < 25 or amount > 2000:
            errors.append("Choose an amount between $25 and $2,000.")
        if not recipient:
            errors.append("Enter the recipient's name.")
        if errors:
            return render_template("giftcard_purchase.html", errors=errors)
        code = f"7334 {MIRROR_DATE.strftime('%m%d')} {int(amount):04d} {(GiftCardPurchase.query.count() + 1) % 10000:04d}"
        db.session.add(GiftCardPurchase(amount=amount, recipient=recipient,
                                        sender=(request.form.get("sender") or "").strip(),
                                        code=code, purchased=MIRROR_DATE))
        db.session.commit()
        return render_template("giftcard_confirmation.html", amount=amount,
                               recipient=recipient, code=code)
    return render_template("giftcard_purchase.html", errors=[])


class GiftCardPurchase(db.Model):
    __tablename__ = "gift_card_purchases"
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    recipient = db.Column(db.String(120), default="")
    sender = db.Column(db.String(120), default="")
    code = db.Column(db.String(30), default="")
    purchased = db.Column(db.DateTime, default=MIRROR_DATE)


# ---------------------------------------------------------------------------
# Health + errors
# ---------------------------------------------------------------------------

@app.route("/_health")
def health():
    return {
        "ok": True,
        "site": "dillards",
        "products": Product.query.count(),
        "variants": Variant.query.count(),
        "brands": Brand.query.count(),
        "reviews": Review.query.count(),
        "stores": Store.query.count(),
        "orders": Order.query.count(),
        "registries": Registry.query.count(),
        "users": User.query.count(),
    }


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(400)
def bad_request(error):
    return render_template("400.html"), 400


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

if not os.environ.get("WEBSYN_SKIP_BOOTSTRAP"):
    with app.app_context():
        db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
