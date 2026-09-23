"""Google Shopping mirror — Flask app.

A faithful functional mirror of https://shopping.google.com/ (which serves
https://www.google.com/shopping?udm=28) for the WebHarbor offline benchmark.

Surfaces mirrored (see NOTICE.md for provenance):
- "For you" homepage feed: curated sections with real product cards
- Departments grid (15 real departments with their real tile imagery)
- Search results with scored token-overlap matching, filters and sorting
- Product detail pages with merchant offers, "Visit site", Save/Track price
- Deals page (discounted products)
- Shopping list (/saved) and price tracking behind demo accounts
- Sign in / register mirroring the Google account surface

Deterministic seeding lives in seed_data.py (build-time) — no wall clock,
no random salts; the reset seed is byte-reproducible.
"""
import json
import os
import re
from urllib.parse import urlsplit
from datetime import datetime

from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# The runtime database lives in instance/, which the container recreates on
# boot; make sure the directory exists before SQLAlchemy opens the file.
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'google_shopping.db')}")
app.config["SECRET_KEY"] = "webharbor-google-shopping-dev-key"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created = db.Column(db.String(20), nullable=False, default="2026-09-22")

    saved_items = db.relationship("SavedItem", back_populates="user",
                                  cascade="all, delete-orphan")
    tracked = db.relationship("TrackedProduct", back_populates="user",
                              cascade="all, delete-orphan")

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    def get_id(self):
        return str(self.id)


class Department(db.Model):
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    image = db.Column(db.String(160), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    products = db.relationship("Product", back_populates="department")


class Merchant(db.Model):
    __tablename__ = "merchants"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    favicon = db.Column(db.String(200), nullable=True)

    offers = db.relationship("Offer", back_populates="merchant")


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    upstream_id = db.Column(db.String(40), unique=True, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"),
                              nullable=False)
    category = db.Column(db.String(120), nullable=False, default="")
    image = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    was_price = db.Column(db.Float, nullable=True)
    discount_pct = db.Column(db.Integer, nullable=True)
    merchant_name = db.Column(db.String(120), nullable=False)
    merchant_favicon = db.Column(db.String(200), nullable=True)
    rating = db.Column(db.Float, nullable=True)          # 0-5 stars
    review_count = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text, nullable=False, default="")
    specs_json = db.Column(db.Text, nullable=False, default="{}")
    feed_section = db.Column(db.String(120), nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)

    department = db.relationship("Department", back_populates="products")
    offers = db.relationship("Offer", back_populates="product",
                             order_by="Offer.price")
    reviews = db.relationship("Review", back_populates="product",
                              order_by="Review.position")

    @property
    def specs(self):
        try:
            return json.loads(self.specs_json)
        except (ValueError, TypeError):
            return {}

    @property
    def price_display(self):
        """Upstream renders whole-dollar prices without cents ('$130') and keeps two
        decimals for cents values ('$129.90', '$11.00') — same rule as was_display."""
        if self.price == int(self.price):
            return f"${int(self.price):,}"
        return f"${self.price:,.2f}"

    @property
    def was_display(self):
        if self.was_price is None:
            return None
        if self.was_price == int(self.was_price):
            return f"${int(self.was_price):,}"
        return f"${self.was_price:,.2f}"


class Offer(db.Model):
    __tablename__ = "offers"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"),
                           nullable=False)
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"),
                           nullable=False)
    price = db.Column(db.Float, nullable=False)
    was_price = db.Column(db.Float, nullable=True)
    shipping = db.Column(db.String(120), nullable=True)
    in_stock = db.Column(db.Boolean, nullable=False, default=True)
    position = db.Column(db.Integer, nullable=False, default=0)

    product = db.relationship("Product", back_populates="offers")
    merchant = db.relationship("Merchant", back_populates="offers")


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"),
                           nullable=False)
    author = db.Column(db.String(80), nullable=False)
    rating = db.Column(db.Integer, nullable=False)       # 1-5 stars
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    review_date = db.Column(db.String(30), nullable=False)
    helpful = db.Column(db.Integer, nullable=False, default=0)
    position = db.Column(db.Integer, nullable=False, default=0)

    product = db.relationship("Product", back_populates="reviews")


class FeedSection(db.Model):
    __tablename__ = "feed_sections"
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    heading = db.Column(db.String(120), nullable=False)
    subheading = db.Column(db.String(120), nullable=False, default="")
    explore_query = db.Column(db.String(120), nullable=False, default="")
    tab = db.Column(db.String(20), nullable=False, default="for_you")


class SavedItem(db.Model):
    __tablename__ = "saved_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"),
                           nullable=False)
    added = db.Column(db.String(30), nullable=False, default="")

    user = db.relationship("User", back_populates="saved_items")
    product = db.relationship("Product")


class TrackedProduct(db.Model):
    __tablename__ = "tracked_products"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"),
                           nullable=False)
    created = db.Column(db.String(30), nullable=False, default="")

    user = db.relationship("User", back_populates="tracked")
    product = db.relationship("Product")


# --------------------------------------------------------------------------
# Auth plumbing
# --------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
              "or", "is", "it", "by", "with", "from", "s", "womens", "womens",
              "men's", "for"}


def tokenize(query):
    tokens = [t.lower() for t in re.split(r"\W+", query)
              if t.lower() not in STOP_WORDS and len(t) > 1]
    return tokens or [q.lower() for q in query.split() if q.strip()]


def scored_search(query, products, fields=("title", "merchant_name", "category")):
    """Token-overlap scored search (never strict AND)."""
    tokens = tokenize(query)
    if not tokens:
        return products
    scored = []
    for product in products:
        text = " ".join(getattr(product, f, "") or "" for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            scored.append((product, score))
    scored.sort(key=lambda pair: (-pair[1], pair[0].position))
    return [p for p, _ in scored]


def star_rating(value):
    """Render Google-style star characters for a 0-5 rating."""
    if value is None:
        return None
    full = int(value)
    half = 1 if (value - full) >= 0.5 else 0
    return "★" * full + ("⯨" if half else "") + "☆" * (5 - full - half)


app.jinja_env.globals.update(star_rating=star_rating)


def parse_price(text):
    try:
        return float(text.replace("$", "").replace(",", ""))
    except (ValueError, TypeError):
        return None


def local_redirect(target, fallback="/"):
    """Accept only site-relative return paths supplied by the UI."""
    target = str(target or "")
    parsed = urlsplit(target)
    return target if target.startswith("/") and not target.startswith("//") and not parsed.netloc and not parsed.scheme and "\\" not in target else fallback


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    sections = (FeedSection.query.filter_by(tab="for_you")
                .order_by(FeedSection.position).all())
    section_cards = []
    for section in sections:
        products = (Product.query
                    .filter(Product.feed_section == section.heading)
                    .order_by(Product.position).all())
        if products:
            section_cards.append((section, products))
    return render_template("index.html", sections=section_cards)


@app.route("/departments")
def departments():
    deps = Department.query.order_by(Department.position).all()
    return render_template("departments.html", departments=deps)


@app.route("/search")
def search():
    query = (request.args.get("q") or "").strip()
    department = request.args.get("department", "").strip()
    store = request.args.get("store", "").strip()
    price_min = parse_price(request.args.get("price_min", "") or "")
    price_max = parse_price(request.args.get("price_max", "") or "")
    min_rating = request.args.get("rating", "").strip()
    sort = request.args.get("sort", "relevance").strip()
    source = request.args.get("source", "").strip()

    products = Product.query.order_by(Product.position).all()
    if query:
        products = scored_search(query, products)
    else:
        products = list(products)

    if department:
        products = [p for p in products
                    if p.department and p.department.name == department]
    if store:
        products = [p for p in products if p.merchant_name == store]
    if price_min is not None:
        products = [p for p in products if p.price >= price_min]
    if price_max is not None:
        products = [p for p in products if p.price <= price_max]
    if min_rating:
        try:
            threshold = float(min_rating)
            products = [p for p in products
                        if (p.rating or 0) >= threshold]
        except ValueError:
            pass

    if sort == "price_asc":
        products = sorted(products, key=lambda p: p.price)
    elif sort == "price_desc":
        products = sorted(products, key=lambda p: -p.price)
    elif sort == "discount":
        products = sorted(products,
                          key=lambda p: -(p.discount_pct or 0))

    all_departments = Department.query.order_by(Department.position).all()
    all_merchants = sorted({p.merchant_name for p in
                            Product.query.order_by(Product.position)})
    return render_template("search.html", products=products, query=query,
                           department=department, store=store,
                           price_min=request.args.get("price_min", ""),
                           price_max=request.args.get("price_max", ""),
                           min_rating=min_rating, sort=sort, source=source,
                           all_departments=all_departments,
                           all_merchants=all_merchants)


@app.route("/product/<upstream_id>")
def product(upstream_id):
    item = Product.query.filter_by(upstream_id=upstream_id).first_or_404()
    similar = list(Product.query.filter(
        Product.category == item.category, Product.id != item.id)
        .order_by(Product.position).limit(8).all())
    if len(similar) < 4:
        dept_sims = [p for p in Product.query.filter(
            Product.department_id == item.department_id,
            Product.id != item.id).order_by(Product.position).limit(8).all()
            if p.id not in {s.id for s in similar}]
        similar.extend(dept_sims[:8 - len(similar)])
    saved = tracked = False
    if current_user.is_authenticated:
        saved = any(s.product_id == item.id for s in current_user.saved_items)
        tracked = any(t.product_id == item.id for t in current_user.tracked)
    return render_template("product.html", product=item, similar=similar,
                           saved=saved, tracked=tracked)


@app.route("/deals")
def deals():
    products = [p for p in Product.query.order_by(Product.position)
                if p.discount_pct]
    products = sorted(products, key=lambda p: -(p.discount_pct or 0))
    return render_template("deals.html", products=products)


@app.route("/nearby")
def nearby():
    """Upstream serves local-inventory search through the search surface; the
    datacenter session sees the real 'Nothing to see here' empty state, so
    the mirror reproduces exactly that captured upstream response."""
    return render_template("empty_state.html",
                           heading="Nothing to see here",
                           subheading="Browse the rest of Google Shopping",
                           button="Go to Shopping home", button_url="/")


@app.route("/saved")
@login_required
def saved():
    items = (SavedItem.query.filter_by(user_id=current_user.id)
             .order_by(SavedItem.id.desc()).all())
    products = [i.product for i in items]
    return render_template("saved.html", products=products)


@app.route("/tracked")
@login_required
def tracked():
    items = (TrackedProduct.query.filter_by(user_id=current_user.id)
             .order_by(TrackedProduct.id.desc()).all())
    return render_template("tracked.html", items=items)


@app.route("/save/<int:product_id>", methods=["POST"])
@login_required
def save_product(product_id):
    product = Product.query.get_or_404(product_id)
    exists = SavedItem.query.filter_by(user_id=current_user.id,
                                       product_id=product_id).first()
    if not exists:
        db.session.add(SavedItem(user_id=current_user.id,
                                 product_id=product_id,
                                 added="2026-09-22"))
        db.session.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return {"ok": True, "saved": True}
    return redirect(request.referrer or url_for("index"))


@app.route("/unsave/<int:product_id>", methods=["POST"])
@login_required
def unsave_product(product_id):
    SavedItem.query.filter_by(user_id=current_user.id,
                              product_id=product_id).delete()
    db.session.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return {"ok": True, "saved": False}
    return redirect(request.referrer or url_for("index"))


@app.route("/track/<int:product_id>", methods=["POST"])
@login_required
def track_product(product_id):
    product = Product.query.get_or_404(product_id)
    exists = TrackedProduct.query.filter_by(user_id=current_user.id,
                                            product_id=product_id).first()
    if not exists:
        db.session.add(TrackedProduct(user_id=current_user.id,
                                      product_id=product_id,
                                      created="2026-09-22"))
        db.session.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return {"ok": True, "tracked": True}
    return redirect(request.referrer or url_for("product",
                                                upstream_id=product.upstream_id))


@app.route("/untrack/<int:product_id>", methods=["POST"])
@login_required
def untrack_product(product_id):
    TrackedProduct.query.filter_by(user_id=current_user.id,
                                    product_id=product_id).delete()
    db.session.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return {"ok": True, "tracked": False}
    return redirect(request.referrer or url_for("tracked"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(local_redirect(request.args.get("next")))
        return render_template("login.html", error=True, email=email)
    return render_template("login.html", error=False, email="")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or not password:
            return render_template("register.html", error="missing")
        if User.query.filter_by(email=email).first():
            return render_template("register.html", error="exists")
        user = User(email=email, display_name=name,
                    password_hash=bcrypt.generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("index"))
    return render_template("register.html", error=None)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    saved_count = SavedItem.query.filter_by(user_id=current_user.id).count()
    tracked_count = TrackedProduct.query.filter_by(
        user_id=current_user.id).count()
    return render_template("account.html", saved_count=saved_count,
                           tracked_count=tracked_count)


@app.route("/_health")
def health():
    return {"ok": True, "site": "google_shopping"}


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


# --------------------------------------------------------------------------
# Bootstrap
# --------------------------------------------------------------------------
with app.app_context():
    db.create_all()
    if os.environ.get("GOOGLE_SHOPPING_SKIP_SEED") != "1":
        from seed_data import seed_database, seed_benchmark_users
        seed_database()
        seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
