from __future__ import annotations

import os
import re
from datetime import date, timedelta
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

CONFIG = {'name': 'Petfinder', 'url': 'https://www.petfinder.com/', 'tagline': 'Find adoptable pets, shelters, and application steps.', 'entity': 'Pet', 'theme': '#2563eb', 'accent': '#f97316', 'categories': ['Dogs', 'Cats', 'Small & Furry', 'Senior Pets', 'Special Needs'], 'filters': ['Distance', 'Age', 'Size', 'Good with kids'], 'actions': ['Save Pet', 'Start Adoption Inquiry', 'Contact Shelter'], 'items': ['Milo Labrador Mix', 'Luna Domestic Shorthair', 'Pepper Terrier', 'Nori Rabbit', 'Maple Senior Beagle', 'Cleo Tuxedo Cat', 'Atlas German Shepherd', 'Sunny Guinea Pig', 'Poppy Tabby', 'Rex Boxer Mix', 'Ivy Calico', 'Scout Border Collie', 'Hazel Chihuahua', 'Ollie Poodle Mix', 'Ruby Pit Bull Terrier', 'Finn Siamese', 'Mocha Dachshund', 'Willow Maine Coon', 'Theo Corgi Mix', 'Nova Husky'], 'article_topics': ['Preparing your home for adoption', 'Questions to ask a shelter', 'Introducing a rescue pet', 'Adoption fees explained', 'Post-adoption vet checklist'], 'slug': 'petfinder'}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFERENCE_DATE = date(2026, 5, 29)

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = f"webharbor-{CONFIG['slug']}-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', CONFIG['slug'] + '.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
STOP_WORDS = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with"}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    home_region = db.Column(db.String(80), default="New York")
    preference = db.Column(db.String(120), default="Balanced")


class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    name = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    region = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(80), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    detail = db.Column(db.Text, nullable=False)

    @property
    def search_blob(self) -> str:
        return f"{self.name} {self.category} {self.region} {self.status} score {self.score} price {self.price} {self.summary} {self.detail}"


class Guide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    read_minutes = db.Column(db.Integer, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)


class SavedItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    note = db.Column(db.String(240), default="")
    listing = db.relationship("Listing")


def current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


@app.context_processor
def inject_common():
    return {"current_user": current_user(), "config": CONFIG, "reference_date": REFERENCE_DATE}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Sign in to save and manage items.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text or "item"


def tokenize(query: str):
    return [t for t in re.split(r"\W+", query.lower()) if len(t) > 1 and t not in STOP_WORDS]


def scored_search(query: str, rows, fields):
    parts = tokenize(query)
    if not parts:
        return list(rows)
    scored = []
    for row in rows:
        haystack = " ".join(str(getattr(row, field, "") or "") for field in fields).lower()
        score = sum(1 for part in parts if part in haystack)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], -getattr(item[1], "score", 0), getattr(item[1], "name", "")))
    return [row for _, row in scored]


@app.route("/")
def index():
    featured = Listing.query.order_by(Listing.score.desc()).limit(6).all()
    guides = Guide.query.order_by(Guide.id.desc()).limit(4).all()
    return render_template("index.html", featured=featured, guides=guides)


@app.route("/listings")
def listings():
    category = request.args.get("category", "")
    region = request.args.get("region", "")
    max_price = request.args.get("max_price", type=int)
    rows = Listing.query.order_by(Listing.score.desc()).all()
    if category:
        rows = [row for row in rows if row.category == category]
    if region:
        rows = [row for row in rows if row.region == region]
    if max_price:
        rows = [row for row in rows if row.price <= max_price]
    categories = [r[0] for r in db.session.query(Listing.category).distinct().order_by(Listing.category)]
    regions = [r[0] for r in db.session.query(Listing.region).distinct().order_by(Listing.region)]
    return render_template("listings.html", rows=rows, categories=categories, regions=regions, category=category, region=region, max_price=max_price)


@app.route("/listings/<slug>")
def listing_detail(slug):
    listing = Listing.query.filter_by(slug=slug).first_or_404()
    related = Listing.query.filter(Listing.category == listing.category, Listing.slug != listing.slug).order_by(Listing.score.desc()).limit(4).all()
    return render_template("listing_detail.html", listing=listing, related=related)


@app.route("/listings/<slug>/save", methods=["POST"])
@login_required
def save_listing(slug):
    listing = Listing.query.filter_by(slug=slug).first_or_404()
    user = current_user()
    existing = SavedItem.query.filter_by(user_id=user.id, listing_id=listing.id).first()
    if not existing:
        db.session.add(SavedItem(user_id=user.id, listing_id=listing.id, note=request.form.get("note", "")))
        db.session.commit()
        flash(f"Saved {listing.name}.", "success")
    return redirect(url_for("account"))


@app.route("/tools", methods=["GET", "POST"])
def tools():
    result = None
    if request.method == "POST":
        need = request.form.get("need", CONFIG["actions"][0])
        region = request.form.get("region", "New York")
        matches = scored_search(need + " " + region, Listing.query.all(), ["search_blob"])[:5]
        if not matches:
            matches = Listing.query.order_by(Listing.score.desc()).limit(5).all()
        result = {"need": need, "region": region, "matches": matches}
    return render_template("tools.html", result=result)


@app.route("/guides")
def guides():
    topic = request.args.get("topic", "")
    rows = Guide.query.order_by(Guide.title).all()
    if topic:
        rows = [row for row in rows if row.topic == topic]
    topics = [r[0] for r in db.session.query(Guide.topic).distinct().order_by(Guide.topic)]
    return render_template("guides.html", rows=rows, topics=topics, topic=topic)


@app.route("/guides/<slug>")
def guide_detail(slug):
    guide = Guide.query.filter_by(slug=slug).first_or_404()
    return render_template("guide_detail.html", guide=guide)


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    listing_results = scored_search(query, Listing.query.all(), ["search_blob"])[:10] if query else []
    guide_results = scored_search(query, Guide.query.all(), ["title", "topic", "summary", "body"])[:8] if query else []
    return render_template("search.html", query=query, listing_results=listing_results, guide_results=guide_results)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            flash(f"Welcome back, {user.display_name}.", "success")
            return redirect(request.args.get("next") or url_for("account"))
        flash("Email or password did not match.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    saved = SavedItem.query.filter_by(user_id=current_user().id).all()
    return render_template("account.html", saved=saved)


@app.route("/account/preferences", methods=["POST"])
@login_required
def update_preferences():
    user = current_user()
    user.home_region = request.form.get("home_region", user.home_region)
    user.preference = request.form.get("preference", user.preference)
    db.session.commit()
    flash("Preferences updated.", "success")
    return redirect(url_for("account"))


@app.route("/art/<slug>.svg")
def art(slug):
    label = slug.replace("-", " ").title()
    hue = abs(hash(CONFIG["slug"] + slug)) % 360
    initials = "".join(part[0] for part in CONFIG["name"].split()[:2]).upper()
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 480" role="img" aria-label="{label}">
<rect width="720" height="480" fill="hsl({hue}, 70%, 95%)"/>
<circle cx="140" cy="110" r="180" fill="{CONFIG['theme']}" opacity=".18"/>
<circle cx="585" cy="390" r="220" fill="{CONFIG['accent']}" opacity=".18"/>
<rect x="185" y="125" width="350" height="230" rx="36" fill="white" opacity=".92"/>
<text x="360" y="236" text-anchor="middle" font-family="Arial, sans-serif" font-size="68" font-weight="800" fill="{CONFIG['theme']}">{initials}</text>
<text x="360" y="302" text-anchor="middle" font-family="Arial, sans-serif" font-size="25" font-weight="700" fill="#1f2937">{label[:34]}</text>
</svg>"""
    return app.response_class(svg, mimetype="image/svg+xml")


@app.route("/_health")
def health():
    return {"ok": True, "site": CONFIG["slug"]}


def seed_database():
    if Listing.query.count() > 0:
        return
    regions = ["New York", "Chicago", "Los Angeles", "Seattle", "Austin", "Boston"]
    statuses = ["Available", "Recommended", "Popular", "New", "Limited"]
    for i, name in enumerate(CONFIG["items"]):
        category = CONFIG["categories"][i % len(CONFIG["categories"])]
        region = regions[i % len(regions)]
        score = 96 - (i * 3 % 29)
        price = 20 + (i * 17 % 180)
        status = statuses[i % len(statuses)]
        db.session.add(Listing(
            slug=slugify(name),
            name=name,
            category=category,
            region=region,
            score=score,
            price=price,
            status=status,
            summary=f"{name} is a {category.lower()} result for {CONFIG['name']} users in {region}, rated {score}/100.",
            detail=f"{CONFIG['tagline']} This seeded page exposes filters, status text, pricing, regions, and action steps for benchmark agents.",
        ))
    for i, topic in enumerate(CONFIG["article_topics"]):
        db.session.add(Guide(
            slug=slugify(topic),
            title=topic,
            topic=CONFIG["categories"][i % len(CONFIG["categories"])],
            read_minutes=4 + i,
            summary=f"Guide for {topic.lower()} on {CONFIG['name']}.",
            body=f"{topic} explains practical steps, visible form fields, comparison cues, and account workflows in this deterministic mirror.",
        ))
    db.session.commit()


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    users = [
        ("alice_j", "alice.j@test.com", "Alice Johnson", "New York", "Fastest option"),
        ("bob_c", "bob.c@test.com", "Bob Chen", "Chicago", "Lowest price"),
        ("carol_d", "carol.d@test.com", "Carol Davis", "Seattle", "Highest score"),
        ("david_k", "david.k@test.com", "David Kim", "Austin", "Nearby"),
    ]
    for username, email, display_name, region, preference in users:
        user = User(username=username, email=email, display_name=display_name, home_region=region, preference=preference, password_hash=generate_password_hash("TestPass123!"))
        db.session.add(user)
        db.session.flush()
        for listing in Listing.query.order_by(Listing.score.desc()).limit(2).all():
            db.session.add(SavedItem(user_id=user.id, listing_id=listing.id, note="Benchmark saved item"))
    db.session.commit()


with app.app_context():
    os.makedirs(app.instance_path, exist_ok=True)
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
