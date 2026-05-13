"""Craigslist mirror - Flask app."""
import hashlib
import json
import os
import re
from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, request, Response, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

from seed_data import CATEGORY_GROUPS, deterministic_password, seed_benchmark_users, seed_database


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-craigslist-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'craigslist.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

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
    saved_listings = db.relationship("SavedListing", backref="user", cascade="all, delete-orphan")
    saved_searches = db.relationship("SavedSearch", backref="user", cascade="all, delete-orphan")
    messages = db.relationship("Message", backref="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = deterministic_password(self.email, password)

    def check_password(self, password):
        return self.password_hash == deterministic_password(self.email, password)


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

    saved_by = db.relationship("SavedListing", backref="listing", cascade="all, delete-orphan")
    messages = db.relationship("Message", backref="listing", cascade="all, delete-orphan")

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
        delta = datetime(2026, 5, 12, 15, 0, 0) - self.posted_at
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
    return db.session.get(User, int(user_id))


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "listing"


def tokenize(value):
    return [t for t in re.split(r"[^a-z0-9]+", (value or "").lower()) if len(t) > 1]


def normalize_phrase(value):
    return " ".join(t for t in re.split(r"[^a-z0-9]+", (value or "").lower()) if t)


def parse_int(value):
    if value is None or value == "":
        return None
    try:
        return int(re.sub(r"[^0-9]", "", str(value)))
    except ValueError:
        return None


def listing_score(listing, query):
    tokens = tokenize(query)
    if not tokens:
        return 1
    category = listing.category.name if listing.category else ""
    details = " ".join(f"{k} {v}" for k, v in listing.details().items())
    haystacks = {
        "title": listing.title.lower(),
        "category": category.lower(),
        "area": f"{listing.area} {listing.neighborhood}".lower(),
        "body": f"{listing.description} {details} {listing.condition} {listing.compensation} {listing.company}".lower(),
    }
    score = 0
    phrase = normalize_phrase(query)
    normalized = {key: normalize_phrase(value) for key, value in haystacks.items()}
    if phrase:
        if phrase in normalized["title"]:
            score += 25
        if phrase in normalized["body"]:
            score += 10
    for token in tokens:
        if token in haystacks["title"]:
            score += 5
        if token in haystacks["category"]:
            score += 3
        if token in haystacks["area"]:
            score += 2
        if token in haystacks["body"]:
            score += 1
    return score


def category_groups():
    cats = {c.slug: c for c in Category.query.order_by(Category.display_order).all()}
    groups = []
    for group in CATEGORY_GROUPS:
        rows = []
        for slug, _name, _abbrev in group["columns"]:
            if slug in cats:
                rows.append(cats[slug])
        groups.append({"slug": group["slug"], "name": group["name"], "categories": rows})
    return groups


def hidden_listing_ids():
    if not current_user.is_authenticated:
        return set(session.get("hidden_listing_ids", []))
    return {h.listing_id for h in HiddenListing.query.filter_by(user_id=current_user.id).all()}


def is_saved(listing_id):
    if not current_user.is_authenticated:
        return False
    return SavedListing.query.filter_by(user_id=current_user.id, listing_id=listing_id).first() is not None


def listing_images(listing):
    details = listing.details()
    values = details.get("images", [])
    if isinstance(values, str):
        values = [values]
    images = []
    if listing.image:
        images.append(listing.image)
    for value in values:
        if value and value not in images:
            images.append(value)
    return images


def listing_map_point(listing):
    details = listing.details()
    try:
        x = float(details.get("map_x", 50))
        y = float(details.get("map_y", 50))
        lat = float(details.get("map_lat", 37.7749))
        lng = float(details.get("map_lng", -122.4194))
    except (TypeError, ValueError):
        digest = hashlib.md5(f"{listing.id}:{listing.neighborhood}".encode()).hexdigest()
        x = 18 + (int(digest[:2], 16) % 64)
        y = 16 + (int(digest[2:4], 16) % 58)
        lat = 37.7749
        lng = -122.4194
    return {
        "x": max(6, min(94, x)),
        "y": max(8, min(92, y)),
        "lat": lat,
        "lng": lng,
    }


def listing_public_details(listing):
    hidden = {"images", "map_x", "map_y", "map_lat", "map_lng"}
    return [
        (key, value)
        for key, value in listing.details().items()
        if key not in hidden
    ]


def base_listing_query(category_slug=None):
    query = Listing.query.filter_by(status="active")
    if category_slug:
        category = Category.query.filter_by(slug=category_slug).first_or_404()
        query = query.filter(Listing.category_slug == category.slug)
    return query


def filter_listings(category_slug=None):
    q = request.args.get("q", "").strip()
    area = request.args.get("area", "").strip()
    min_price = parse_int(request.args.get("min_price"))
    max_price = parse_int(request.args.get("max_price"))
    has_image = request.args.get("has_image") == "1"
    sort = request.args.get("sort", "relevance")
    include_hidden = request.args.get("include_hidden") == "1"

    query = base_listing_query(category_slug)
    if area:
        query = query.filter(or_(Listing.area == area, Listing.neighborhood.ilike(f"%{area}%")))
    if min_price is not None:
        query = query.filter(or_(Listing.price == None, Listing.price >= min_price))  # noqa: E711
    if max_price is not None:
        query = query.filter(or_(Listing.price == None, Listing.price <= max_price))  # noqa: E711
    if has_image:
        query = query.filter(Listing.image != "")

    listings = query.all()
    hidden_ids = hidden_listing_ids()
    if not include_hidden:
        listings = [listing for listing in listings if listing.id not in hidden_ids]

    if q:
        scored = [(listing_score(listing, q), listing) for listing in listings]
        listings = [listing for score, listing in scored if score > 0]
        listings.sort(key=lambda pair: (listing_score(pair, q), pair.posted_at), reverse=True)
    elif sort == "price_asc":
        listings.sort(key=lambda listing: (listing.price is None, listing.price or 0, -listing.posted_at.timestamp()))
    elif sort == "price_desc":
        listings.sort(key=lambda listing: (listing.price is None, -(listing.price or 0), -listing.posted_at.timestamp()))
    elif sort == "oldest":
        listings.sort(key=lambda listing: listing.posted_at)
    else:
        listings.sort(key=lambda listing: listing.posted_at, reverse=True)

    return listings


@app.context_processor
def inject_globals():
    def saved_count():
        if not current_user.is_authenticated:
            return 0
        return SavedListing.query.filter_by(user_id=current_user.id).count()

    return {
        "category_groups": category_groups,
        "is_saved": is_saved,
        "saved_count": saved_count,
        "listing_images": listing_images,
        "listing_map_point": listing_map_point,
        "listing_public_details": listing_public_details,
    }


@app.route("/")
def index():
    featured = Listing.query.filter(Listing.image != "", Listing.status == "active").order_by(Listing.posted_at.desc()).limit(8).all()
    recent = Listing.query.filter_by(status="active").order_by(Listing.posted_at.desc()).limit(12).all()
    counts = {
        category.slug: Listing.query.filter_by(category_slug=category.slug, status="active").count()
        for category in Category.query.all()
    }
    return render_template("index.html", featured=featured, recent=recent, counts=counts)


@app.route("/favicon.ico")
def favicon():
    return Response(status=204)


@app.route("/search")
def search():
    listings = filter_listings()
    return render_template(
        "search.html",
        listings=listings,
        category=None,
        query=request.args.get("q", "").strip(),
        areas=["san francisco", "east bay", "south bay", "peninsula", "north bay", "santa cruz"],
    )


@app.route("/search/<category_slug>")
def category_search(category_slug):
    category = Category.query.filter_by(slug=category_slug).first_or_404()
    listings = filter_listings(category_slug)
    return render_template(
        "search.html",
        listings=listings,
        category=category,
        query=request.args.get("q", "").strip(),
        areas=["san francisco", "east bay", "south bay", "peninsula", "north bay", "santa cruz"],
    )


@app.route("/d/<slug>/<int:listing_id>.html")
def listing_detail(slug, listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.slug != slug:
        return redirect(url_for("listing_detail", slug=listing.slug, listing_id=listing.id), code=301)
    listing.view_count += 1
    db.session.commit()
    nearby = Listing.query.filter(
        Listing.id != listing.id,
        Listing.category_slug == listing.category_slug,
        Listing.status == "active",
    ).order_by(Listing.posted_at.desc()).limit(6).all()
    return render_template("listing_detail.html", listing=listing, nearby=nearby)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("logged in", "success")
            return redirect(request.args.get("next") or url_for("account"))
        flash("invalid email or password", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip().lower()
        name = request.form.get("name", "").strip() or username
        password = request.form.get("password", "")
        if not email or not username or not password:
            flash("email, username, and password are required", "error")
        elif User.query.filter(or_(User.email == email, User.username == username)).first():
            flash("that account already exists", "error")
        else:
            user = User(email=email, username=username, name=name, area=request.form.get("area", "san francisco"))
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("account created", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("logged out", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    posts = Listing.query.filter_by(owner_id=current_user.id).order_by(Listing.posted_at.desc()).all()
    searches = SavedSearch.query.filter_by(user_id=current_user.id).order_by(SavedSearch.created_at.desc()).all()
    messages = Message.query.filter_by(user_id=current_user.id).order_by(Message.created_at.desc()).limit(5).all()
    return render_template("account.html", posts=posts, searches=searches, messages=messages)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        current_user.name = request.form.get("name", current_user.name).strip()
        current_user.area = request.form.get("area", current_user.area).strip()
        current_user.phone = request.form.get("phone", current_user.phone).strip()
        db.session.commit()
        flash("account updated", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/saved")
@login_required
def saved():
    rows = SavedListing.query.filter_by(user_id=current_user.id).order_by(SavedListing.created_at.desc()).all()
    return render_template("saved.html", rows=rows)


@app.route("/save-search", methods=["POST"])
@login_required
def save_search():
    name = request.form.get("name", "").strip() or "saved craigslist search"
    saved_search = SavedSearch(
        user_id=current_user.id,
        name=name,
        query_text=request.form.get("q", "").strip(),
        category_slug=request.form.get("category_slug", "").strip(),
        area=request.form.get("area", "").strip(),
        min_price=parse_int(request.form.get("min_price")),
        max_price=parse_int(request.form.get("max_price")),
    )
    db.session.add(saved_search)
    db.session.commit()
    flash("search saved", "success")
    return redirect(url_for("account"))


@app.route("/listing/<int:listing_id>/save", methods=["POST"])
@login_required
def save_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    existing = SavedListing.query.filter_by(user_id=current_user.id, listing_id=listing.id).first()
    if not existing:
        db.session.add(SavedListing(
            user_id=current_user.id,
            listing_id=listing.id,
            note=request.form.get("note", "").strip(),
        ))
        db.session.commit()
        flash("listing saved", "success")
    return redirect(request.form.get("next") or url_for("listing_detail", slug=listing.slug, listing_id=listing.id))


@app.route("/listing/<int:listing_id>/unsave", methods=["POST"])
@login_required
def unsave_listing(listing_id):
    saved_row = SavedListing.query.filter_by(user_id=current_user.id, listing_id=listing_id).first()
    if saved_row:
        db.session.delete(saved_row)
        db.session.commit()
        flash("listing removed", "info")
    return redirect(request.form.get("next") or url_for("saved"))


@app.route("/listing/<int:listing_id>/hide", methods=["POST"])
def hide_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if current_user.is_authenticated:
        existing = HiddenListing.query.filter_by(user_id=current_user.id, listing_id=listing.id).first()
        if not existing:
            db.session.add(HiddenListing(user_id=current_user.id, listing_id=listing.id))
            db.session.commit()
    else:
        ids = set(session.get("hidden_listing_ids", []))
        ids.add(listing.id)
        session["hidden_listing_ids"] = sorted(ids)
    flash("listing hidden", "info")
    return redirect(request.form.get("next") or url_for("search"))


@app.route("/listing/<int:listing_id>/flag", methods=["POST"])
def flag_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    listing.flag_count += 1
    db.session.commit()
    flash("thanks for flagging", "info")
    return redirect(url_for("listing_detail", slug=listing.slug, listing_id=listing.id))


@app.route("/reply/<int:listing_id>", methods=["GET", "POST"])
def reply(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip() or (current_user.name if current_user.is_authenticated else "craigslist user")
        email = request.form.get("email", "").strip() or (current_user.email if current_user.is_authenticated else "anonymous@example.test")
        body = request.form.get("body", "").strip()
        if not body:
            flash("message body is required", "error")
        else:
            db.session.add(Message(
                user_id=current_user.id if current_user.is_authenticated else None,
                listing_id=listing.id,
                sender_name=name,
                sender_email=email,
                body=body,
                direction="outbound",
                is_read=True,
            ))
            db.session.commit()
            flash("reply sent", "success")
            return redirect(url_for("listing_detail", slug=listing.slug, listing_id=listing.id))
    return render_template("reply.html", listing=listing)


@app.route("/messages")
@login_required
def messages():
    rows = Message.query.filter_by(user_id=current_user.id).order_by(Message.created_at.desc()).all()
    unread = Message.query.filter_by(user_id=current_user.id, is_read=False).all()
    for row in unread:
        row.is_read = True
    db.session.commit()
    return render_template("messages.html", rows=rows)


@app.route("/post", methods=["GET", "POST"])
@login_required
def post_listing():
    categories = Category.query.order_by(Category.group_slug, Category.display_order).all()
    if request.method == "POST":
        category = Category.query.filter_by(slug=request.form.get("category_slug", "")).first()
        if not category:
            flash("choose a valid category", "error")
            return render_template("post.html", categories=categories)
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        if not title or not description:
            flash("title and description are required", "error")
            return render_template("post.html", categories=categories)
        details = {
            "posted_by": "owner",
            "availability": request.form.get("availability", "available now").strip(),
            "contact_preference": request.form.get("contact_preference", "email").strip(),
        }
        listing = Listing(
            title=title,
            slug=f"{slugify(title)}-{hashlib.md5((title + current_user.email).encode()).hexdigest()[:6]}",
            category_id=category.id,
            category_slug=category.slug,
            category_group=category.group_slug,
            area=request.form.get("area", current_user.area).strip(),
            neighborhood=request.form.get("neighborhood", "").strip(),
            price=parse_int(request.form.get("price")),
            bedrooms=parse_int(request.form.get("bedrooms")),
            sqft=parse_int(request.form.get("sqft")),
            condition=request.form.get("condition", "").strip(),
            compensation=request.form.get("compensation", "").strip(),
            company=request.form.get("company", "").strip(),
            employment_type=request.form.get("employment_type", "").strip(),
            description=description,
            details_json=json.dumps(details, sort_keys=True),
            seller_name=current_user.name,
            seller_email=current_user.email,
            reply_phone=current_user.phone,
            owner_id=current_user.id,
            status="active",
        )
        db.session.add(listing)
        db.session.commit()
        flash("posting published", "success")
        return redirect(url_for("listing_detail", slug=listing.slug, listing_id=listing.id))
    return render_template("post.html", categories=categories)


@app.route("/posting/<int:listing_id>/delete", methods=["POST"])
@login_required
def delete_posting(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.owner_id != current_user.id:
        abort(403)
    listing.status = "deleted"
    db.session.commit()
    flash("posting deleted", "info")
    return redirect(url_for("account"))


@app.route("/_health")
def health():
    return {"ok": True, "site": "craigslist", "listings": Listing.query.count()}


with app.app_context():
    db.create_all()
    seed_database(BASE_DIR, db, Category, Listing)
    seed_benchmark_users(db, User, Listing, SavedListing, SavedSearch, Message)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
