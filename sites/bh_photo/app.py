import os
import re
from collections import defaultdict
from datetime import datetime

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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
SITE_DB = os.path.join(INSTANCE_DIR, "bh_photo.db")
os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__, instance_path=INSTANCE_DIR)
app.config["SECRET_KEY"] = "webharbor-bh-photo-demo-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{SITE_DB}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to access saved shopping tools."
login_manager.login_message_category = "info"

STOP_WORDS = {
    "the",
    "a",
    "an",
    "for",
    "to",
    "of",
    "and",
    "or",
    "in",
    "on",
    "with",
    "by",
    "from",
    "new",
}


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(140), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), default="")
    company = db.Column(db.String(120), default="")
    role = db.Column(db.String(80), default="Creator")
    preferred_store_id = db.Column(db.Integer, db.ForeignKey("store_locations.id"))
    newsletter_opt_in = db.Column(db.Boolean, default=True)
    sms_opt_in = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    addresses = db.relationship("Address", backref="user", lazy=True, cascade="all, delete-orphan")
    cart_items = db.relationship("CartItem", backref="user", lazy=True, cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", backref="user", lazy=True, cascade="all, delete-orphan")
    compare_items = db.relationship("CompareItem", backref="user", lazy=True, cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="user", lazy=True, cascade="all, delete-orphan")
    reservations = db.relationship("StoreReservation", backref="user", lazy=True, cascade="all, delete-orphan")
    search_logs = db.relationship("SearchLog", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)


class Address(db.Model):
    __tablename__ = "addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    label = db.Column(db.String(40), default="Studio")
    recipient = db.Column(db.String(120), nullable=False)
    line1 = db.Column(db.String(200), nullable=False)
    line2 = db.Column(db.String(200), default="")
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(40), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(60), default="United States")
    phone = db.Column(db.String(40), default="")
    is_default = db.Column(db.Boolean, default=False)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    hero_copy = db.Column(db.Text, default="")
    icon_label = db.Column(db.String(32), default="")
    nav_order = db.Column(db.Integer, default=0)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"))

    parent = db.relationship("Category", remote_side=[id], backref="children")
    products = db.relationship("Product", backref="category", lazy=True)


class Brand(db.Model):
    __tablename__ = "brands"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    blurb = db.Column(db.Text, default="")
    origin = db.Column(db.String(80), default="")
    badge_color = db.Column(db.String(16), default="#24423f")

    products = db.relationship("Product", backref="brand", lazy=True)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    sku = db.Column(db.String(32), unique=True, nullable=False)
    short_description = db.Column(db.String(220), default="")
    description = db.Column(db.Text, default="")
    search_blob = db.Column(db.Text, default="")
    price = db.Column(db.Float, nullable=False)
    list_price = db.Column(db.Float, default=0)
    rating = db.Column(db.Float, default=4.5)
    review_count = db.Column(db.Integer, default=0)
    qa_count = db.Column(db.Integer, default=0)
    condition = db.Column(db.String(40), default="New")
    availability = db.Column(db.String(40), default="In Stock")
    stock_level = db.Column(db.Integer, default=0)
    pickup_available = db.Column(db.Boolean, default=True)
    pickup_message = db.Column(db.String(120), default="")
    shipping_message = db.Column(db.String(120), default="")
    return_window = db.Column(db.String(80), default="30-Day Return Window")
    warranty = db.Column(db.String(120), default="1-Year Demo Warranty")
    best_seller_rank = db.Column(db.Integer, default=999)
    sort_newness = db.Column(db.Integer, default=0)
    top_category_slug = db.Column(db.String(80), default="")
    subcategory_slug = db.Column(db.String(80), default="")
    product_family = db.Column(db.String(80), default="")
    product_type = db.Column(db.String(80), default="")
    sensor_size = db.Column(db.String(80), default="")
    mount_type = db.Column(db.String(80), default="")
    focal_length = db.Column(db.String(80), default="")
    focal_length_bucket = db.Column(db.String(40), default="")
    megapixels = db.Column(db.Float, default=0)
    capacity_gb = db.Column(db.Integer, default=0)
    connectivity = db.Column(db.String(120), default="")
    pickup_store_count = db.Column(db.Integer, default=0)
    image_path = db.Column(db.String(220), default="")
    accent_color = db.Column(db.String(16), default="#24504d")
    release_label = db.Column(db.String(60), default="")
    is_featured = db.Column(db.Boolean, default=False)
    is_bundle_anchor = db.Column(db.Boolean, default=False)
    is_used_highlight = db.Column(db.Boolean, default=False)

    images = db.relationship("ProductImage", backref="product", lazy=True, cascade="all, delete-orphan")
    spec_groups = db.relationship("ProductSpecGroup", backref="product", lazy=True, cascade="all, delete-orphan")
    variants = db.relationship("ProductVariant", backref="product", lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship("ProductReview", backref="product", lazy=True, cascade="all, delete-orphan")
    questions = db.relationship("ProductQuestion", backref="product", lazy=True, cascade="all, delete-orphan")
    store_inventory = db.relationship("StoreInventory", backref="product", lazy=True, cascade="all, delete-orphan")
    deals = db.relationship("Deal", backref="product", lazy=True, cascade="all, delete-orphan")

    def active_deal(self):
        return next((deal for deal in self.deals if deal.is_active), None)

    @property
    def display_price(self) -> float:
        deal = self.active_deal()
        return deal.sale_price if deal else self.price

    @property
    def savings_amount(self) -> float:
        return max((self.list_price or self.price) - self.display_price, 0)

    @property
    def savings_percent(self) -> int:
        base = self.list_price or self.price
        if not base or self.display_price >= base:
            return 0
        return int(round((base - self.display_price) / base * 100))

    @property
    def main_image(self) -> str:
        if self.image_path:
            return self.image_path
        if self.images:
            return self.images[0].path
        return "images/bh-photo-fallback.svg"

    @property
    def top_spec_map(self) -> dict:
        spec_map = {}
        for group in self.spec_groups:
            for spec in group.specs:
                spec_map[spec.name] = spec.value
        return spec_map

    @property
    def average_review_label(self) -> str:
        return f"{self.rating:.1f}"


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    path = db.Column(db.String(220), nullable=False)
    label = db.Column(db.String(80), default="Primary")
    sort_order = db.Column(db.Integer, default=0)


class ProductSpecGroup(db.Model):
    __tablename__ = "product_spec_groups"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    specs = db.relationship("ProductSpec", backref="group", lazy=True, cascade="all, delete-orphan")


class ProductSpec(db.Model):
    __tablename__ = "product_specs"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("product_spec_groups.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    value = db.Column(db.String(240), nullable=False)
    sort_order = db.Column(db.Integer, default=0)


class ProductVariant(db.Model):
    __tablename__ = "product_variants"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    label = db.Column(db.String(120), nullable=False)
    variant_type = db.Column(db.String(40), default="Kit")
    value = db.Column(db.String(120), nullable=False)
    price_delta = db.Column(db.Float, default=0)


class ProductReview(db.Model):
    __tablename__ = "product_reviews"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    author_name = db.Column(db.String(120), nullable=False)
    headline = db.Column(db.String(180), nullable=False)
    body = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    verified_purchase = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProductQuestion(db.Model):
    __tablename__ = "product_questions"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    asker_name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    answers = db.relationship("ProductAnswer", backref="question_ref", lazy=True, cascade="all, delete-orphan")


class ProductAnswer(db.Model):
    __tablename__ = "product_answers"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("product_questions.id"), nullable=False)
    responder_name = db.Column(db.String(120), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Bundle(db.Model):
    __tablename__ = "bundles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    image_path = db.Column(db.String(220), default="")
    bundle_price = db.Column(db.Float, nullable=False)
    list_price = db.Column(db.Float, nullable=False)
    badge = db.Column(db.String(60), default="Bundle")
    audience = db.Column(db.String(120), default="")
    featured = db.Column(db.Boolean, default=False)

    items = db.relationship("BundleItem", backref="bundle", lazy=True, cascade="all, delete-orphan")

    @property
    def savings(self) -> float:
        return max(self.list_price - self.bundle_price, 0)


class BundleItem(db.Model):
    __tablename__ = "bundle_items"

    id = db.Column(db.Integer, primary_key=True)
    bundle_id = db.Column(db.Integer, db.ForeignKey("bundles.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    product = db.relationship("Product")


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    variant_label = db.Column(db.String(120), default="")
    bundle_label = db.Column(db.String(160), default="")
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product")

    @property
    def unit_price(self) -> float:
        return self.product.display_price if self.product else 0

    @property
    def line_total(self) -> float:
        return self.unit_price * self.quantity


class WishlistItem(db.Model):
    __tablename__ = "wishlist_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product")


class CompareItem(db.Model):
    __tablename__ = "compare_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product")


class StoreLocation(db.Model):
    __tablename__ = "store_locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(40), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pickup_hours = db.Column(db.String(120), default="")
    contact_phone = db.Column(db.String(40), default="")
    inventory_note = db.Column(db.String(120), default="")

    inventory = db.relationship("StoreInventory", backref="store_location", lazy=True, cascade="all, delete-orphan")
    reservations = db.relationship("StoreReservation", backref="store_location", lazy=True, cascade="all, delete-orphan")


class StoreInventory(db.Model):
    __tablename__ = "store_inventory"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store_locations.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    pickup_eta = db.Column(db.String(120), default="")


class StoreReservation(db.Model):
    __tablename__ = "store_reservations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("store_locations.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    status = db.Column(db.String(40), default="Reserved")
    pickup_window = db.Column(db.String(120), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product")


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    order_number = db.Column(db.String(40), unique=True, nullable=False)
    status = db.Column(db.String(40), default="Processing")
    subtotal = db.Column(db.Float, default=0)
    shipping = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    fulfillment = db.Column(db.String(80), default="Ship to address")
    payment_label = db.Column(db.String(120), default="Demo Visa ending in 4242")
    note = db.Column(db.String(240), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    image_path = db.Column(db.String(220), default="")
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0)
    variant_label = db.Column(db.String(120), default="")

    product = db.relationship("Product")


class Deal(db.Model):
    __tablename__ = "deals"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    label = db.Column(db.String(80), default="Deal")
    sale_price = db.Column(db.Float, nullable=False)
    deal_type = db.Column(db.String(40), default="sale")
    is_active = db.Column(db.Boolean, default=True)


class SearchLog(db.Model):
    __tablename__ = "search_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    query = db.Column(db.String(220), nullable=False)
    scope = db.Column(db.String(80), default="all")
    result_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))


def tokenized(text: str) -> list[str]:
    return [
        token
        for token in re.split(r"[^a-zA-Z0-9]+", (text or "").lower())
        if token and token not in STOP_WORDS and len(token) > 1
    ]


def currency(value: float) -> str:
    return f"${value:,.2f}"


def descendant_category_ids(category: Category) -> set[int]:
    ids = {category.id}
    for child in category.children:
        ids.update(descendant_category_ids(child))
    return ids


def all_products() -> list[Product]:
    return Product.query.options(
        db.joinedload(Product.brand),
        db.joinedload(Product.category),
        db.joinedload(Product.deals),
        db.joinedload(Product.images),
        db.joinedload(Product.spec_groups).joinedload(ProductSpecGroup.specs),
    ).all()


def product_search_score(product: Product, query: str) -> int:
    tokens = tokenized(query)
    if not tokens:
        return 0
    text = " ".join(
        [
            product.name,
            product.short_description,
            product.description,
            product.search_blob,
            product.brand.name if product.brand else "",
            product.category.name if product.category else "",
        ]
    ).lower()
    return sum(1 for token in tokens if token in text)


def apply_product_filters(products: list[Product], args, *, query_text: str = "") -> list[Product]:
    filtered = list(products)

    if query_text:
        scored = []
        for product in filtered:
            score = product_search_score(product, query_text)
            if score > 0:
                scored.append((product, score))
        filtered = [product for product, _score in sorted(scored, key=lambda item: (-item[1], item[0].best_seller_rank, item[0].name))]

    brand_slug = args.get("brand", "").strip()
    if brand_slug:
        filtered = [product for product in filtered if product.brand and product.brand.slug == brand_slug]

    min_price = args.get("min_price", "").strip()
    if min_price:
        try:
            threshold = float(min_price)
            filtered = [product for product in filtered if product.display_price >= threshold]
        except ValueError:
            pass

    max_price = args.get("max_price", "").strip()
    if max_price:
        try:
            threshold = float(max_price)
            filtered = [product for product in filtered if product.display_price <= threshold]
        except ValueError:
            pass

    rating_filter = args.get("rating", "").strip()
    if rating_filter:
        try:
            threshold = float(rating_filter)
            filtered = [product for product in filtered if product.rating >= threshold]
        except ValueError:
            pass

    availability = args.get("availability", "").strip()
    if availability == "in-stock":
        filtered = [product for product in filtered if product.availability == "In Stock"]
    elif availability == "preorder":
        filtered = [product for product in filtered if "Pre-Order" in product.availability]
    elif availability == "pickup":
        filtered = [product for product in filtered if product.pickup_available and product.pickup_store_count > 0]

    condition = args.get("condition", "").strip()
    if condition:
        filtered = [product for product in filtered if product.condition.lower() == condition.lower()]

    sensor_size = args.get("sensor_size", "").strip()
    if sensor_size:
        filtered = [product for product in filtered if product.sensor_size == sensor_size]

    mount = args.get("mount", "").strip()
    if mount:
        filtered = [product for product in filtered if product.mount_type == mount]

    focal_length = args.get("focal_length", "").strip()
    if focal_length:
        filtered = [product for product in filtered if product.focal_length_bucket == focal_length]

    megapixels = args.get("megapixels", "").strip()
    if megapixels:
        try:
            threshold = float(megapixels)
            filtered = [product for product in filtered if product.megapixels >= threshold]
        except ValueError:
            pass

    capacity = args.get("capacity", "").strip()
    if capacity == "256gb":
        filtered = [product for product in filtered if product.capacity_gb >= 256]
    elif capacity == "1tb":
        filtered = [product for product in filtered if product.capacity_gb >= 1024]

    connectivity = args.get("connectivity", "").strip()
    if connectivity:
        filtered = [product for product in filtered if connectivity.lower() in (product.connectivity or "").lower()]

    pickup = args.get("pickup", "").strip()
    if pickup == "yes":
        filtered = [product for product in filtered if product.pickup_available and product.pickup_store_count > 0]

    sort_key = args.get("sort", "relevance")
    if sort_key == "price_asc":
        filtered.sort(key=lambda product: (product.display_price, product.best_seller_rank, product.name))
    elif sort_key == "price_desc":
        filtered.sort(key=lambda product: (-product.display_price, product.best_seller_rank, product.name))
    elif sort_key == "newest":
        filtered.sort(key=lambda product: (-product.sort_newness, product.name))
    elif sort_key == "rating":
        filtered.sort(key=lambda product: (-product.rating, -product.review_count, product.name))
    elif sort_key == "bestsellers":
        filtered.sort(key=lambda product: (product.best_seller_rank, product.name))
    elif sort_key == "name":
        filtered.sort(key=lambda product: product.name)
    elif not query_text:
        filtered.sort(key=lambda product: (product.best_seller_rank, product.name))

    return filtered


def filters_for(products: list[Product]) -> dict:
    return {
        "brands": sorted({product.brand.slug: product.brand.name for product in products if product.brand}.items(), key=lambda item: item[1]),
        "sensor_sizes": sorted({product.sensor_size for product in products if product.sensor_size}),
        "mounts": sorted({product.mount_type for product in products if product.mount_type}),
        "focal_lengths": sorted({product.focal_length_bucket for product in products if product.focal_length_bucket}),
        "connectivity": sorted({product.connectivity for product in products if product.connectivity}),
    }


def current_compare_products() -> list[Product]:
    compare_ids = []
    if current_user.is_authenticated:
        compare_ids = [item.product_id for item in current_user.compare_items]
    else:
        compare_ids = session.get("compare_ids", [])
    if not compare_ids:
        return []
    products = Product.query.filter(Product.id.in_(compare_ids[:4])).all()
    products.sort(key=lambda product: compare_ids.index(product.id))
    return products


def cart_metrics():
    if not current_user.is_authenticated:
        return {"count": 0, "subtotal": 0.0}
    items = current_user.cart_items
    return {
        "count": sum(item.quantity for item in items),
        "subtotal": round(sum(item.line_total for item in items), 2),
    }


def order_totals_for(items: list[CartItem]) -> dict:
    subtotal = round(sum(item.line_total for item in items), 2)
    shipping = 0 if subtotal >= 99 else 14.95
    tax = round(subtotal * 0.08875, 2)
    total = round(subtotal + shipping + tax, 2)
    return {"subtotal": subtotal, "shipping": shipping, "tax": tax, "total": total}


def store_options_for(product: Product) -> list[StoreInventory]:
    inventory = sorted(product.store_inventory, key=lambda item: (-item.quantity, item.store_location.city))
    return [item for item in inventory if item.quantity > 0]


def merge_compare_into_session(product_id: int) -> None:
    compare_ids = session.get("compare_ids", [])
    if product_id not in compare_ids:
        compare_ids.append(product_id)
    session["compare_ids"] = compare_ids[:4]
    session.modified = True


def compare_cell_map(products: list[Product]) -> dict:
    grouped = defaultdict(list)
    all_names = defaultdict(list)
    for product in products:
        for group in sorted(product.spec_groups, key=lambda item: item.sort_order):
            for spec in sorted(group.specs, key=lambda item: item.sort_order):
                grouped[group.title].append((product.id, spec.name, spec.value))
                all_names[group.title].append(spec.name)

    result = {}
    for group_name, rows in grouped.items():
        names = []
        seen = set()
        for name in all_names[group_name]:
            if name not in seen:
                names.append(name)
                seen.add(name)
        group_rows = []
        for spec_name in names:
            values = {}
            for product in products:
                values[product.id] = product.top_spec_map.get(spec_name, "—")
            differences = len(set(values.values())) > 1
            group_rows.append({"name": spec_name, "values": values, "different": differences})
        result[group_name] = group_rows
    return result


def build_compare_rows(products: list[Product]) -> dict:
    grouped_names = defaultdict(list)
    spec_lookup = {}

    for product in products:
        per_product_specs = {}
        for group in sorted(product.spec_groups, key=lambda item: item.sort_order):
            grouped_names[group.title]
            for spec in sorted(group.specs, key=lambda item: item.sort_order):
                grouped_names[group.title].append(spec.name)
                per_product_specs[spec.name] = spec.value
        spec_lookup[product.id] = per_product_specs

    compare_rows = {}
    for group_name, spec_names in grouped_names.items():
        ordered_names = []
        seen = set()
        for spec_name in spec_names:
            if spec_name not in seen:
                ordered_names.append(spec_name)
                seen.add(spec_name)
        rows = []
        for spec_name in ordered_names:
            cells = {
                product.id: spec_lookup.get(product.id, {}).get(spec_name, "--")
                for product in products
            }
            rows.append(
                {
                    "name": spec_name,
                    "cells": cells,
                    "different": len(set(cells.values())) > 1,
                }
            )
        compare_rows[group_name] = rows
    return compare_rows


def log_search(query: str, scope: str, result_count: int) -> None:
    if not query:
        return
    entry = SearchLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        query=query[:220],
        scope=scope[:80],
        result_count=result_count,
    )
    db.session.add(entry)
    db.session.commit()


@app.template_filter("currency")
def currency_filter(value: float) -> str:
    return currency(value)


@app.context_processor
def inject_globals():
    top_categories = (
        Category.query.filter_by(parent_id=None).order_by(Category.nav_order, Category.name).all()
    )
    featured_brands = Brand.query.order_by(Brand.name).limit(10).all()
    metrics = cart_metrics()
    return {
        "top_categories": top_categories,
        "featured_brands": featured_brands,
        "cart_count": metrics["count"],
        "compare_count": len(current_compare_products()),
        "wishlist_count": len(current_user.wishlist_items) if current_user.is_authenticated else 0,
        "demo_notice": "Local benchmark mirror with deterministic demo inventory, users, orders, and checkout flows.",
    }


@app.route("/")
def index():
    featured = Product.query.filter_by(is_featured=True).order_by(Product.best_seller_rank).limit(8).all()
    deals = Product.query.join(Deal).filter(Deal.is_active.is_(True)).order_by(Product.best_seller_rank).limit(6).all()
    used_highlights = Product.query.filter(Product.condition != "New").order_by(Product.rating.desc()).limit(6).all()
    bundles = Bundle.query.order_by(Bundle.featured.desc(), Bundle.title).limit(4).all()
    categories = Category.query.filter_by(parent_id=None).order_by(Category.nav_order).all()
    spotlight = Product.query.filter_by(is_bundle_anchor=True).order_by(Product.best_seller_rank).limit(4).all()
    return render_template(
        "index.html",
        featured=featured,
        deals=deals,
        used_highlights=used_highlights,
        bundles=bundles,
        categories=categories,
        spotlight=spotlight,
    )


@app.route("/categories")
def categories():
    top_categories = Category.query.filter_by(parent_id=None).order_by(Category.nav_order).all()
    return render_template("categories.html", categories=top_categories)


@app.route("/c/<slug>")
def category_view(slug: str):
    category = Category.query.filter_by(slug=slug).first_or_404()
    ids = descendant_category_ids(category)
    products = [product for product in all_products() if product.category_id in ids]
    results = apply_product_filters(products, request.args)
    return render_template(
        "category_listing.html",
        page_title=category.name,
        page_heading=category.name,
        page_description=category.hero_copy or category.description,
        category=category,
        products=results,
        filters=filters_for(products),
        base_products=products,
        active_tab=category.slug,
    )


@app.route("/search")
def search():
    query_text = request.args.get("q", "").strip()
    products = all_products()
    results = apply_product_filters(products, request.args, query_text=query_text)
    log_search(query_text, "search", len(results))
    return render_template(
        "category_listing.html",
        page_title="Search",
        page_heading=f"Search results for “{query_text}”" if query_text else "Search the catalog",
        page_description="Find cameras, lenses, lighting, audio, and pro workstation gear across the local benchmark catalog.",
        category=None,
        products=results,
        filters=filters_for(products),
        base_products=products,
        active_tab="search",
        search_query=query_text,
    )


@app.route("/brand/<brand_slug>")
def brand_view(brand_slug: str):
    brand = Brand.query.filter_by(slug=brand_slug).first_or_404()
    products = [product for product in all_products() if product.brand_id == brand.id]
    results = apply_product_filters(products, request.args)
    return render_template(
        "category_listing.html",
        page_title=brand.name,
        page_heading=brand.name,
        page_description=brand.blurb,
        category=None,
        brand=brand,
        products=results,
        filters=filters_for(products),
        base_products=products,
        active_tab="brand",
    )


def render_product_tab(product_slug: str, active_tab: str):
    product = Product.query.filter_by(slug=product_slug).first_or_404()
    related = Product.query.filter(
        Product.id != product.id,
        Product.subcategory_slug == product.subcategory_slug,
    ).order_by(Product.best_seller_rank).limit(4).all()
    return render_template(
        "product_detail.html",
        product=product,
        active_tab=active_tab,
        related=related,
        top_specs=list(product.top_spec_map.items())[:6],
        inventory=store_options_for(product),
        compare_ids=[item.id for item in current_compare_products()],
    )


@app.route("/product/<product_slug>")
def product_detail(product_slug: str):
    return render_product_tab(product_slug, "overview")


@app.route("/product/<product_slug>/specs")
def product_specs(product_slug: str):
    return render_product_tab(product_slug, "specs")


@app.route("/product/<product_slug>/reviews")
def product_reviews(product_slug: str):
    return render_product_tab(product_slug, "reviews")


@app.route("/product/<product_slug>/qa")
def product_qa(product_slug: str):
    return render_product_tab(product_slug, "qa")


@app.route("/compare")
def compare():
    products = current_compare_products()
    if not products and request.args.get("slugs"):
        slugs = [slug.strip() for slug in request.args.get("slugs", "").split(",") if slug.strip()]
        products = Product.query.filter(Product.slug.in_(slugs[:4])).all()
        products.sort(key=lambda product: slugs.index(product.slug))
    return render_template(
        "compare.html",
        products=products,
        compare_rows=build_compare_rows(products),
    )


@app.route("/deals")
def deals():
    products = Product.query.join(Deal).filter(Deal.is_active.is_(True)).all()
    results = apply_product_filters(products, request.args)
    return render_template(
        "category_listing.html",
        page_title="Deals",
        page_heading="Deals and daily savings",
        page_description="Current sale pricing, open-box spotlights, and editor-picked specials across photo, video, and creator tech.",
        category=None,
        products=results,
        filters=filters_for(products),
        base_products=products,
        active_tab="deals",
    )


@app.route("/used")
def used():
    products = Product.query.filter(Product.condition != "New").all()
    results = apply_product_filters(products, request.args)
    return render_template(
        "category_listing.html",
        page_title="Used",
        page_heading="Used and open-box",
        page_description="Deterministic demo inventory for pre-owned, open-box, and pro-verified creator gear.",
        category=None,
        products=results,
        filters=filters_for(products),
        base_products=products,
        active_tab="used",
    )


@app.route("/bundles")
def bundles():
    bundles_list = Bundle.query.order_by(Bundle.featured.desc(), Bundle.title).all()
    return render_template("bundles.html", bundles=bundles_list)


@app.route("/bundle/<bundle_slug>/add", methods=["POST"])
@login_required
def add_bundle_to_cart(bundle_slug: str):
    bundle = Bundle.query.filter_by(slug=bundle_slug).first_or_404()
    for item in bundle.items:
        existing = CartItem.query.filter_by(
            user_id=current_user.id,
            product_id=item.product_id,
            bundle_label=bundle.title,
        ).first()
        if existing:
            existing.quantity += item.quantity
        else:
            db.session.add(
                CartItem(
                    user_id=current_user.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    bundle_label=bundle.title,
                )
            )
    db.session.commit()
    flash(f"{bundle.title} was added to your cart.", "success")
    return redirect(url_for("cart"))


@app.route("/store-pickup")
def store_pickup():
    stores = StoreLocation.query.order_by(StoreLocation.city).all()
    featured = Product.query.filter_by(pickup_available=True).order_by(Product.best_seller_rank).limit(10).all()
    product = None
    inventory = []
    if request.args.get("product"):
        product = Product.query.filter_by(slug=request.args["product"]).first()
        if product:
            inventory = store_options_for(product)
    reservations = current_user.reservations if current_user.is_authenticated else []
    return render_template(
        "store_pickup.html",
        stores=stores,
        featured=featured,
        product=product,
        inventory=inventory,
        reservations=reservations,
    )


@app.route("/help")
def help_page():
    featured_products = Product.query.order_by(Product.best_seller_rank).limit(3).all()
    help_cards = [
        {
            "title": "Returns and exchanges",
            "copy": "Demo orders carry a clear 30-day return window with synthetic RMA language that mirrors a pro retailer workflow.",
        },
        {
            "title": "Shipping and pickup",
            "copy": "Every shipping timeline and pickup ETA on this mirror is deterministic and local-only. Nothing reaches live couriers or stores.",
        },
        {
            "title": "Trade-in and used gear",
            "copy": "Used and open-box catalog pages include condition grading, accessory notes, and limited stock badges for benchmark tasks.",
        },
    ]
    return render_template("help.html", help_cards=help_cards, featured_products=featured_products)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    submitted = False
    if request.method == "POST":
        submitted = True
        flash("Your demo support request was saved locally for benchmark flow testing.", "success")
    return render_template("contact.html", submitted=submitted)


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
            flash("Signed in to your B&H demo account.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("account"))
        flash("That demo email/password combination did not match.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not display_name or not username or not email or not password:
            flash("Please complete every required registration field.", "danger")
        elif password != confirm:
            flash("Passwords must match.", "danger")
        elif User.query.filter((User.email == email) | (User.username == username)).first():
            flash("That demo account already exists.", "warning")
        else:
            user = User(
                display_name=display_name,
                username=username,
                email=email,
                phone=request.form.get("phone", "").strip(),
                company=request.form.get("company", "").strip(),
                role=request.form.get("role", "").strip() or "Creator",
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            db.session.add(
                Address(
                    user_id=user.id,
                    label="Studio",
                    recipient=display_name,
                    line1=request.form.get("line1", "").strip() or "100 Demo Plaza",
                    city=request.form.get("city", "").strip() or "New York",
                    state=request.form.get("state", "").strip() or "NY",
                    zip_code=request.form.get("zip_code", "").strip() or "10001",
                    phone=user.phone,
                    is_default=True,
                )
            )
            db.session.commit()
            login_user(user)
            flash("Your B&H demo account is ready.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
    flash("You have been signed out of the demo mirror.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    reservations = current_user.reservations[:4]
    return render_template("account.html", reservations=reservations)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        current_user.display_name = request.form.get("display_name", "").strip() or current_user.display_name
        current_user.phone = request.form.get("phone", "").strip()
        current_user.company = request.form.get("company", "").strip()
        current_user.role = request.form.get("role", "").strip() or current_user.role
        current_user.newsletter_opt_in = request.form.get("newsletter_opt_in") == "on"
        current_user.sms_opt_in = request.form.get("sms_opt_in") == "on"
        preferred_store = request.form.get("preferred_store_id", "").strip()
        if preferred_store.isdigit():
            current_user.preferred_store_id = int(preferred_store)
        db.session.commit()
        flash("Your demo account preferences were updated.", "success")
        return redirect(url_for("account"))
    stores = StoreLocation.query.order_by(StoreLocation.city).all()
    return render_template("account_edit.html", stores=stores)


@app.route("/account/orders")
@login_required
def account_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("orders.html", orders=orders)


@app.route("/account/wishlist")
@login_required
def account_wishlist():
    items = WishlistItem.query.filter_by(user_id=current_user.id).order_by(WishlistItem.created_at.desc()).all()
    return render_template("wishlist.html", items=items)


@app.route("/account/compare")
@login_required
def account_compare():
    products = [item.product for item in CompareItem.query.filter_by(user_id=current_user.id).all()]
    return render_template("compare.html", products=products, compare_rows=build_compare_rows(products), account_mode=True)


@app.route("/account/addresses")
@login_required
def account_addresses():
    return render_template("addresses.html", addresses=current_user.addresses)


@app.route("/wishlist/toggle/<product_slug>", methods=["POST"])
@login_required
def toggle_wishlist(product_slug: str):
    product = Product.query.filter_by(slug=product_slug).first_or_404()
    existing = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if existing:
        db.session.delete(existing)
        flash(f"{product.name} was removed from your wishlist.", "info")
    else:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=product.id))
        flash(f"{product.name} was saved to your wishlist.", "success")
    db.session.commit()
    return redirect(request.referrer or url_for("product_detail", product_slug=product.slug))


@app.route("/compare/add/<product_slug>", methods=["POST"])
def add_compare(product_slug: str):
    product = Product.query.filter_by(slug=product_slug).first_or_404()
    if current_user.is_authenticated:
        existing = CompareItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
        if not existing:
            if CompareItem.query.filter_by(user_id=current_user.id).count() >= 4:
                oldest = CompareItem.query.filter_by(user_id=current_user.id).order_by(CompareItem.created_at).first()
                if oldest:
                    db.session.delete(oldest)
            db.session.add(CompareItem(user_id=current_user.id, product_id=product.id))
            db.session.commit()
    else:
        merge_compare_into_session(product.id)
    flash(f"{product.name} was added to compare.", "success")
    return redirect(request.referrer or url_for("compare"))


@app.route("/compare/remove/<product_slug>", methods=["POST"])
def remove_compare(product_slug: str):
    product = Product.query.filter_by(slug=product_slug).first_or_404()
    if current_user.is_authenticated:
        existing = CompareItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
    else:
        compare_ids = session.get("compare_ids", [])
        session["compare_ids"] = [pid for pid in compare_ids if pid != product.id]
        session.modified = True
    flash(f"{product.name} was removed from compare.", "info")
    return redirect(request.referrer or url_for("compare"))


@app.route("/cart")
@login_required
def cart():
    items = CartItem.query.filter_by(user_id=current_user.id).order_by(CartItem.added_at.desc()).all()
    totals = order_totals_for(items)
    return render_template("cart.html", items=items, totals=totals)


@app.route("/cart/add/<product_slug>", methods=["POST"])
@login_required
def add_to_cart(product_slug: str):
    product = Product.query.filter_by(slug=product_slug).first_or_404()
    quantity = max(int(request.form.get("quantity", 1) or 1), 1)
    variant_label = request.form.get("variant_label", "").strip()
    existing = CartItem.query.filter_by(
        user_id=current_user.id,
        product_id=product.id,
        variant_label=variant_label,
        bundle_label="",
    ).first()
    if existing:
        existing.quantity += quantity
    else:
        db.session.add(
            CartItem(
                user_id=current_user.id,
                product_id=product.id,
                quantity=quantity,
                variant_label=variant_label,
            )
        )
    db.session.commit()
    flash(f"{product.name} was added to your cart.", "success")
    return redirect(request.referrer or url_for("cart"))


@app.route("/cart/update/<int:item_id>", methods=["POST"])
@login_required
def update_cart(item_id: int):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    quantity = max(int(request.form.get("quantity", 1) or 1), 1)
    item.quantity = quantity
    db.session.commit()
    flash("Your cart quantity was updated.", "success")
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_cart_item(item_id: int):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("That item was removed from your cart.", "info")
    return redirect(url_for("cart"))


@app.route("/reserve/<product_slug>", methods=["POST"])
@login_required
def reserve_store_pickup(product_slug: str):
    product = Product.query.filter_by(slug=product_slug).first_or_404()
    store_id = int(request.form.get("store_id", 0) or 0)
    quantity = max(int(request.form.get("quantity", 1) or 1), 1)
    inventory = StoreInventory.query.filter_by(product_id=product.id, store_id=store_id).first()
    if not inventory or inventory.quantity < quantity:
        flash("That pickup slot is no longer available in this demo inventory.", "danger")
        return redirect(url_for("store_pickup", product=product.slug))

    reservation = StoreReservation(
        user_id=current_user.id,
        store_id=store_id,
        product_id=product.id,
        quantity=quantity,
        status="Reserved",
        pickup_window=inventory.pickup_eta,
    )
    db.session.add(reservation)
    db.session.commit()
    flash(f"{product.name} is reserved for in-store pickup.", "success")
    return redirect(url_for("store_pickup", product=product.slug))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).order_by(CartItem.added_at.desc()).all()
    if not items:
        flash("Your cart is empty. Add something before starting checkout.", "warning")
        return redirect(url_for("cart"))
    totals = order_totals_for(items)
    addresses = current_user.addresses
    if request.method == "POST":
        fulfillment = request.form.get("fulfillment", "Ship to address").strip() or "Ship to address"
        payment_label = request.form.get("payment_label", "Demo Visa ending in 4242").strip() or "Demo Visa ending in 4242"
        note = request.form.get("note", "").strip()
        order_number = f"BH-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{current_user.id:02d}"
        order = Order(
            user_id=current_user.id,
            order_number=order_number,
            status="Confirmed",
            subtotal=totals["subtotal"],
            shipping=totals["shipping"],
            tax=totals["tax"],
            total=totals["total"],
            fulfillment=fulfillment,
            payment_label=payment_label,
            note=note,
        )
        db.session.add(order)
        db.session.flush()
        for item in items:
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=item.product_id,
                    product_name=item.product.name,
                    image_path=item.product.main_image,
                    quantity=item.quantity,
                    price=item.unit_price,
                    variant_label=item.variant_label or item.bundle_label,
                )
            )
            db.session.delete(item)
        db.session.commit()
        flash("Your demo checkout was completed locally.", "success")
        return redirect(url_for("order_receipt", order_number=order.order_number))
    return render_template("checkout.html", items=items, totals=totals, addresses=addresses)


@app.route("/order/<order_number>")
@login_required
def order_receipt(order_number: str):
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    return render_template("order_receipt.html", order=order)


@app.route("/contact-support")
def contact_support_redirect():
    return redirect(url_for("contact"))


@app.route("/_health")
def health():
    return {"ok": True, "site": "bh_photo"}


MODEL_REGISTRY = {
    "User": User,
    "Address": Address,
    "Category": Category,
    "Brand": Brand,
    "Product": Product,
    "ProductImage": ProductImage,
    "ProductSpecGroup": ProductSpecGroup,
    "ProductSpec": ProductSpec,
    "ProductVariant": ProductVariant,
    "ProductReview": ProductReview,
    "ProductQuestion": ProductQuestion,
    "ProductAnswer": ProductAnswer,
    "Bundle": Bundle,
    "BundleItem": BundleItem,
    "CartItem": CartItem,
    "WishlistItem": WishlistItem,
    "CompareItem": CompareItem,
    "StoreLocation": StoreLocation,
    "StoreInventory": StoreInventory,
    "StoreReservation": StoreReservation,
    "Order": Order,
    "OrderItem": OrderItem,
    "Deal": Deal,
    "SearchLog": SearchLog,
}


with app.app_context():
    db.create_all()
    from seed_data import seed_benchmark_users, seed_database

    seed_database(db, MODEL_REGISTRY, BASE_DIR)
    seed_benchmark_users(db, MODEL_REGISTRY)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
