"""Craigslist mirror - Flask app."""

import hashlib
import json
import os
import re
import secrets
import shutil
from pathlib import Path
from urllib.parse import urlsplit
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    Response,
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

from seed_data import CATEGORY_GROUPS, REGIONS, SNAPSHOT_NOW


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INSTANCE_DIR = os.environ.get("CRAIGSLIST_INSTANCE", os.path.join(BASE_DIR, "instance"))
app = Flask(__name__, instance_path=INSTANCE_DIR)
app.config["SECRET_KEY"] = "webharbor-craigslist-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{os.path.join(INSTANCE_DIR, 'craigslist.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(INSTANCE_DIR, exist_ok=True)
if not os.environ.get("CRAIGSLIST_BUILD_SEED"):
    seed = Path(BASE_DIR, "instance_seed", "craigslist.db")
    if not seed.is_file():
        raise RuntimeError(
            "Missing reviewed Craigslist seed; fetch its HF assets first."
        )
    expected = "d983cbf885a6c5d89207ee2cc37e133fe2d1015662ff3aa69a72c6933e3687b5"
    if hashlib.sha256(seed.read_bytes()).hexdigest() != expected:
        raise RuntimeError(
            "Craigslist assets do not match this reviewed snapshot. Install the matching asset bundle; do not reuse HF PR #72's old seed."
        )
    if not Path(INSTANCE_DIR, "craigslist.db").exists():
        shutil.copyfile(seed, Path(INSTANCE_DIR, "craigslist.db"))

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(140), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    area = db.Column(db.String(80), default="san francisco")
    phone = db.Column(db.String(40), default="")
    password_hash = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    listings = db.relationship("Listing", backref="owner", lazy=True)
    saved_listings = db.relationship(
        "SavedListing", backref="user", cascade="all, delete-orphan"
    )
    saved_searches = db.relationship(
        "SavedSearch", backref="user", cascade="all, delete-orphan"
    )
    messages = db.relationship("Message", backref="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    abbrev = db.Column(db.String(20), default="")
    group_slug = db.Column(db.String(50), index=True)
    group_name = db.Column(db.String(80), default="")
    display_order = db.Column(db.Integer, default=0)

    listings = db.relationship("Listing", backref="category", lazy=True)


class Listing(db.Model):
    __tablename__ = "listings"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False, index=True)
    slug = db.Column(db.String(240), unique=True, nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    category_slug = db.Column(db.String(80), index=True)
    category_group = db.Column(db.String(50), index=True)
    area = db.Column(db.String(80), index=True)
    neighborhood = db.Column(db.String(120), default="")
    price = db.Column(db.Integer, nullable=True, index=True)
    bedrooms = db.Column(db.Integer, nullable=True)
    sqft = db.Column(db.Integer, nullable=True)
    condition = db.Column(db.String(60), default="")
    compensation = db.Column(db.String(120), default="")
    company = db.Column(db.String(140), default="")
    employment_type = db.Column(db.String(80), default="")
    description = db.Column(db.Text, default="")
    details_json = db.Column(db.Text, default="{}")
    image = db.Column(db.String(260), default="")
    seller_name = db.Column(db.String(120), default="craigslist user")
    seller_email = db.Column(db.String(160), default="")
    reply_phone = db.Column(db.String(40), default="")
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(40), default="active")
    view_count = db.Column(db.Integer, default=0)
    flag_count = db.Column(db.Integer, default=0)

    saved_by = db.relationship(
        "SavedListing", backref="listing", cascade="all, delete-orphan"
    )
    messages = db.relationship(
        "Message", backref="listing", cascade="all, delete-orphan"
    )

    def details(self):
        try:
            return json.loads(self.details_json or "{}")
        except json.JSONDecodeError:
            return {}

    @property
    def display_price(self):
        if self.price is None:
            return self.compensation or ""
        if self.price == 0:
            return "free"
        return f"${self.price:,}"

    @property
    def age_label(self):
        delta = SNAPSHOT_NOW - self.posted_at
        hours = max(1, int(delta.total_seconds() // 3600))
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"


class SavedListing(db.Model):
    __tablename__ = "saved_listings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False)
    note = db.Column(db.String(240), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedSearch(db.Model):
    __tablename__ = "saved_searches"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    query_text = db.Column(db.String(180), default="")
    category_slug = db.Column(db.String(80), default="")
    area = db.Column(db.String(80), default="")
    min_price = db.Column(db.Integer, nullable=True)
    max_price = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class HiddenListing(db.Model):
    __tablename__ = "hidden_listings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False)
    sender_name = db.Column(db.String(120), default="")
    sender_email = db.Column(db.String(160), default="")
    body = db.Column(db.Text, default="")
    direction = db.Column(db.String(20), default="outbound")
    is_read = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "listing"


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(24)
    return session["csrf_token"]


@app.before_request
def protect_forms():
    if request.method == "POST":
        supplied = request.form.get("csrf_token", "")
        if not supplied or not secrets.compare_digest(
            supplied, session.get("csrf_token", "")
        ):
            abort(400, "Invalid or missing form token")


def local_redirect(value, fallback):
    value = (value or "").strip()
    parsed = urlsplit(value)
    if (
        value.startswith("/")
        and not value.startswith("//")
        and not parsed.netloc
        and not parsed.scheme
        and "\\" not in value
        and not any(ord(c) < 32 for c in value)
    ):
        return redirect(value)
    return redirect(fallback)


def parse_int(value):
    if value in (None, ""):
        return None
    value = str(value).strip().replace(",", "").removeprefix("$")
    if not re.fullmatch(r"[0-9]+", value):
        abort(400, "Enter a nonnegative whole number")
    result = int(value)
    if result > 100000000:
        abort(400, "Number is too large")
    return result


def category_groups():
    cats = {c.slug: c for c in Category.query.order_by(Category.display_order).all()}
    return [
        {
            "slug": g["slug"],
            "name": g["name"],
            "categories": [cats[c[0]] for c in g["columns"] if c[0] in cats],
        }
        for g in CATEGORY_GROUPS
    ]


def hidden_listing_ids():
    if not current_user.is_authenticated:
        return set(session.get("hidden_listing_ids", []))
    return {
        h.listing_id for h in HiddenListing.query.filter_by(user_id=current_user.id)
    }


def is_saved(listing_id):
    return (
        current_user.is_authenticated
        and SavedListing.query.filter_by(
            user_id=current_user.id, listing_id=listing_id
        ).first()
        is not None
    )


def listing_images(listing):
    return list(
        dict.fromkeys(
            ([listing.image] if listing.image else [])
            + listing.details().get("images", [])
        )
    )


def listing_public_details(listing):
    return [
        (k, v)
        for k, v in listing.details().items()
        if not k.startswith("_")
        and k not in {"images", "condition", "employment type", "company"}
    ]


def search_url(**overrides):
    values = request.args.to_dict()
    values.update(overrides)
    category_slug = values.pop("category", "") or (request.view_args or {}).get(
        "category_slug", ""
    )
    values = {k: v for k, v in values.items() if v not in ("", None)}
    return (
        url_for("category_search", category_slug=category_slug, **values)
        if category_slug
        else url_for("search", **values)
    )


@app.context_processor
def inject_globals():
    return dict(
        category_groups=category_groups,
        is_saved=is_saved,
        saved_count=lambda: (
            SavedListing.query.filter_by(user_id=current_user.id).count()
            if current_user.is_authenticated
            else 0
        ),
        listing_images=listing_images,
        listing_public_details=listing_public_details,
        csrf_token=csrf_token,
        search_url=search_url,
        regions=REGIONS,
        snapshot_date=SNAPSHOT_NOW.strftime("%Y-%m-%d"),
    )


@app.route("/")
def index():
    counts = {
        c.slug: Listing.query.filter_by(category_slug=c.slug, status="active").count()
        for c in Category.query.all()
    }
    return render_template("index.html", counts=counts)


@app.route("/favicon.ico")
def favicon():
    return Response(status=204)


def filtered_listings(category_slug=None):
    query = Listing.query.filter_by(status="active")
    if category_slug:
        Category.query.filter_by(slug=category_slug).first_or_404()
        query = query.filter_by(category_slug=category_slug)
    group = request.args.get("section", "")
    if group:
        if group not in {g["slug"] for g in CATEGORY_GROUPS}:
            abort(400)
        query = query.filter_by(category_group=group)
    area = request.args.get("area", "")
    if area:
        if area not in REGIONS:
            abort(400, "Unknown area")
        query = query.filter_by(area=area)
    low, high = (
        parse_int(request.args.get("min_price")),
        parse_int(request.args.get("max_price")),
    )
    if low is not None and high is not None and low > high:
        abort(400, "Minimum exceeds maximum")
    if low is not None:
        query = query.filter(Listing.price >= low)
    if high is not None:
        query = query.filter(Listing.price <= high)
    if request.args.get("free") == "1":
        query = query.filter(Listing.price == 0)
    if request.args.get("has_image") == "1":
        query = query.filter(Listing.image != "")
    if request.args.get("posted_today") == "1":
        query = query.filter(
            Listing.posted_at >= SNAPSHOT_NOW.replace(hour=0, minute=0, second=0)
        )
    rows = [x for x in query.all() if x.id not in hidden_listing_ids()]
    words = re.findall(r"[\w]+", request.args.get("q", "").casefold())

    def score(row):
        title = row.title.casefold()
        hay = (
            title
            if request.args.get("title_only") == "1"
            else " ".join(
                [
                    title,
                    row.description.casefold(),
                    row.neighborhood.casefold(),
                    json.dumps(dict(listing_public_details(row))).casefold(),
                ]
            )
        )
        return (
            sum(5 if w in title else 1 for w in words)
            if all(w in hay for w in words)
            else 0
        )

    if words:
        rows = [x for x in rows if score(x)]
    sort = request.args.get("sort", "relevance")
    if sort == "price_asc":
        rows.sort(key=lambda x: (x.price is None, x.price or 0, x.id))
    elif sort == "price_desc":
        rows.sort(key=lambda x: (x.price is None, -(x.price or 0), x.id))
    elif sort == "oldest":
        rows.sort(key=lambda x: (x.posted_at, x.id))
    elif sort == "newest":
        rows.sort(key=lambda x: (x.posted_at, x.id), reverse=True)
    else:
        rows.sort(key=lambda x: (score(x), x.posted_at, x.id), reverse=True)
    return rows


@app.route("/search")
@app.route("/search/<category_slug>", endpoint="category_search")
def search(category_slug=None):
    chosen = request.args.get("category", "")
    if chosen:
        Category.query.filter_by(slug=chosen).first_or_404()
        args = request.args.to_dict()
        args.pop("category")
        args.pop("section", None)
        return redirect(url_for("category_search", category_slug=chosen, **args))
    category = (
        Category.query.filter_by(slug=category_slug).first_or_404()
        if category_slug
        else None
    )
    return render_template(
        "search.html",
        listings=filtered_listings(category_slug),
        category=category,
        query=request.args.get("q", ""),
        areas=REGIONS,
    )


@app.route("/d/<slug>/<int:listing_id>.html")
def listing_detail(slug, listing_id):
    listing = Listing.query.filter_by(id=listing_id, status="active").first_or_404()
    if slug != listing.slug:
        return redirect(
            url_for("listing_detail", slug=listing.slug, listing_id=listing.id),
            code=301,
        )
    nearby = (
        Listing.query.filter(
            Listing.id != listing.id,
            Listing.category_slug == listing.category_slug,
            Listing.status == "active",
        )
        .order_by(Listing.id)
        .limit(6)
        .all()
    )
    return render_template("listing_detail.html", listing=listing, nearby=nearby)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(
            email=request.form.get("email", "").strip().lower()
        ).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user)
            flash("logged in", "success")
            return local_redirect(request.args.get("next"), url_for("account"))
        flash("invalid email or password", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if (
            not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
            or not username
            or len(password) < 8
        ):
            flash(
                "Enter a valid email, username and password of at least 8 characters.",
                "error",
            )
        elif User.query.filter(
            or_(User.email == email, User.username == username)
        ).first():
            flash("that account already exists", "error")
        else:
            area = request.form.get("area", REGIONS[0])
            if area not in REGIONS:
                abort(400)
            user = User(
                email=email,
                username=username,
                name=request.form.get("name", "").strip() or username,
                area=area,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    return render_template(
        "account.html",
        posts=Listing.query.filter_by(owner_id=current_user.id)
        .order_by(Listing.id.desc())
        .all(),
        searches=SavedSearch.query.filter_by(user_id=current_user.id)
        .order_by(SavedSearch.id.desc())
        .all(),
        messages=Message.query.filter_by(user_id=current_user.id)
        .order_by(Message.id.desc())
        .limit(5)
        .all(),
        hidden=Listing.query.join(HiddenListing, HiddenListing.listing_id == Listing.id)
        .filter(HiddenListing.user_id == current_user.id)
        .all(),
    )


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        area = request.form.get("area", current_user.area)
        phone = request.form.get("phone", "").strip()
        if area not in REGIONS or not re.fullmatch(r"[0-9()+ .-]{7,24}", phone):
            flash("Enter a supported area and valid phone number.", "error")
        else:
            current_user.name = request.form.get("name", current_user.name).strip()
            current_user.area = area
            current_user.phone = phone
            db.session.commit()
            flash("account updated", "success")
            return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/saved")
@login_required
def saved():
    rows = (
        SavedListing.query.filter_by(user_id=current_user.id)
        .order_by(SavedListing.id.desc())
        .all()
    )
    return render_template("saved.html", rows=rows)


@app.route("/save-search", methods=["POST"])
@login_required
def save_search():
    category = request.form.get("category_slug", "")
    area = request.form.get("area", "")
    if category and not Category.query.filter_by(slug=category).first():
        abort(400)
    if area and area not in REGIONS:
        abort(400)
    low, high = (
        parse_int(request.form.get("min_price")),
        parse_int(request.form.get("max_price")),
    )
    if low is not None and high is not None and low > high:
        abort(400)
    row = SavedSearch(
        user_id=current_user.id,
        name=request.form.get("name", "").strip()[:120] or "saved search",
        query_text=request.form.get("q", "").strip()[:180],
        category_slug=category,
        area=area,
        min_price=low,
        max_price=high,
    )
    db.session.add(row)
    db.session.commit()
    flash("search saved", "success")
    return redirect(url_for("account"))


@app.route("/listing/<int:listing_id>/save", methods=["POST"])
@login_required
def save_listing(listing_id):
    listing = Listing.query.filter_by(id=listing_id, status="active").first_or_404()
    if not SavedListing.query.filter_by(
        user_id=current_user.id, listing_id=listing.id
    ).first():
        db.session.add(SavedListing(user_id=current_user.id, listing_id=listing.id))
        db.session.commit()
    flash("listing saved", "success")
    return local_redirect(
        request.form.get("next"),
        url_for("listing_detail", slug=listing.slug, listing_id=listing.id),
    )


@app.route("/listing/<int:listing_id>/unsave", methods=["POST"])
@login_required
def unsave_listing(listing_id):
    row = SavedListing.query.filter_by(
        user_id=current_user.id, listing_id=listing_id
    ).first()
    if row:
        db.session.delete(row)
        db.session.commit()
    flash("listing removed", "info")
    return local_redirect(request.form.get("next"), url_for("saved"))


@app.route("/listing/<int:listing_id>/hide", methods=["POST"])
def hide_listing(listing_id):
    Listing.query.filter_by(id=listing_id, status="active").first_or_404()
    if current_user.is_authenticated:
        if not HiddenListing.query.filter_by(
            user_id=current_user.id, listing_id=listing_id
        ).first():
            db.session.add(
                HiddenListing(user_id=current_user.id, listing_id=listing_id)
            )
            db.session.commit()
    else:
        session["hidden_listing_ids"] = sorted(
            set(session.get("hidden_listing_ids", [])) | {listing_id}
        )
    flash("listing hidden", "info")
    return local_redirect(request.form.get("next"), url_for("search"))


@app.route("/listing/<int:listing_id>/unhide", methods=["POST"])
def unhide_listing(listing_id):
    if current_user.is_authenticated:
        row = HiddenListing.query.filter_by(
            user_id=current_user.id, listing_id=listing_id
        ).first()
        if row:
            db.session.delete(row)
            db.session.commit()
    else:
        session["hidden_listing_ids"] = [
            i for i in session.get("hidden_listing_ids", []) if i != listing_id
        ]
    return local_redirect(request.form.get("next"), url_for("hidden"))


@app.route("/hidden")
def hidden():
    rows = Listing.query.filter(Listing.id.in_(hidden_listing_ids())).all()
    return render_template("hidden.html", rows=rows)


@app.route("/reply/<int:listing_id>", methods=["GET", "POST"])
def reply(listing_id):
    listing = Listing.query.filter_by(id=listing_id, status="active").first_or_404()
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not body or len(body) > 5000:
            flash("Enter a message of 1–5000 characters.", "error")
        else:
            db.session.add(
                Message(
                    user_id=current_user.id if current_user.is_authenticated else None,
                    listing_id=listing.id,
                    sender_name=current_user.name
                    if current_user.is_authenticated
                    else request.form.get("name", "").strip(),
                    sender_email=current_user.email
                    if current_user.is_authenticated
                    else request.form.get("email", "").strip(),
                    body=body,
                    direction="outbound",
                    is_read=True,
                )
            )
            db.session.commit()
            flash("reply saved locally — no external message sent", "success")
            return redirect(
                url_for("listing_detail", slug=listing.slug, listing_id=listing.id)
            )
    return render_template("reply.html", listing=listing)


@app.route("/messages")
@login_required
def messages():
    rows = (
        Message.query.filter_by(user_id=current_user.id)
        .order_by(Message.id.desc())
        .all()
    )
    # Reading messages is deliberately side-effect free for snapshot grading.
    return render_template("messages.html", rows=rows)


@app.route("/post", methods=["GET", "POST"])
@login_required
def post_listing():
    categories = Category.query.order_by(Category.display_order).all()
    if request.method == "POST":
        category = Category.query.filter_by(
            slug=request.form.get("category_slug", "")
        ).first()
        title, body = (
            request.form.get("title", "").strip(),
            request.form.get("description", "").strip(),
        )
        area = request.form.get("area", current_user.area)
        if (
            not category
            or not title
            or not body
            or len(title) > 220
            or len(body) > 10000
            or area not in REGIONS
        ):
            flash(
                "Choose a category/area and provide a title and description.", "error"
            )
        else:
            listing = Listing(
                title=title,
                slug=slugify(title) + "-" + secrets.token_hex(6),
                category_id=category.id,
                category_slug=category.slug,
                category_group=category.group_slug,
                area=area,
                neighborhood=request.form.get("neighborhood", "").strip(),
                price=parse_int(request.form.get("price"))
                if category.group_slug in {"for_sale", "housing"}
                else None,
                bedrooms=parse_int(request.form.get("bedrooms"))
                if category.group_slug == "housing"
                else None,
                sqft=parse_int(request.form.get("sqft"))
                if category.group_slug == "housing"
                else None,
                condition=request.form.get("condition", "")
                if category.group_slug == "for_sale"
                else "",
                compensation=request.form.get("compensation", "")
                if category.group_slug == "jobs"
                else "",
                company=request.form.get("company", "")
                if category.group_slug == "jobs"
                else "",
                employment_type=request.form.get("employment_type", "")
                if category.group_slug == "jobs"
                else "",
                description=body,
                details_json="{}",
                image="",
                seller_name=current_user.name,
                seller_email=current_user.email,
                reply_phone=current_user.phone,
                owner_id=current_user.id,
                status="active",
            )
            db.session.add(listing)
            db.session.commit()
            flash("posting published locally", "success")
            return redirect(
                url_for("listing_detail", slug=listing.slug, listing_id=listing.id)
            )
    return render_template("post.html", categories=categories)


@app.route("/posting/<int:listing_id>/delete", methods=["POST"])
@login_required
def delete_posting(listing_id):
    listing = db.get_or_404(Listing, listing_id)
    if listing.owner_id != current_user.id:
        abort(403)
    listing.status = "deleted"
    db.session.commit()
    return redirect(url_for("account"))


@app.route("/about/<page>")
def information(page):
    if page not in {"help", "safety", "privacy", "terms", "about"}:
        abort(404)
    return render_template("information.html", page=page)


@app.route("/_health")
def health():
    return {"ok": True, "site": "craigslist", "listings": Listing.query.count()}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 40041)), debug=False)
