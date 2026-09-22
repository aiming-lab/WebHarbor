#!/usr/bin/env python3
"""Better Business Bureau mirror — business search, profiles, reviews, complaints,
Scam Tracker, quote/complaint/review intake flows, and consumer accounts."""
import json
import math
import os
import re
from datetime import datetime

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "better_business_bureau.db")

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-better_business_bureau-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "signin"
login_manager.login_message = "Sign in to manage your BBB account."

MIRROR_REFERENCE_DATE = datetime(2026, 9, 21)

RATING_ORDER = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F", "NR"]

STOP_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "is", "are", "be", "by", "from", "near", "me", "my", "business",
    "businesses", "company", "companies", "service", "services",
}

COMPLAINT_STATUS_HELP = {
    "Resolved": "The complainant verified the issue was resolved to their satisfaction.",
    "Unresolved": "The business responded to the dispute but failed to make a good faith effort to resolve it.",
    "Answered": "The business addressed the issues within the complaint, but the consumer either a) did not accept the response, OR b) did not notify BBB as to their satisfaction.",
    "Unanswered": "The business failed to respond to the dispute.",
    "Unpursuable": "BBB is unable to locate the business.",
}

PROFILE_DISCLAIMER = (
    "BBB Business Profiles are provided solely to assist you in exercising your own best judgment. "
    "BBB does not verify the accuracy of information provided by third parties, and does not guarantee "
    "the accuracy of any information in Business Profiles. As a matter of policy, BBB does not endorse "
    "any product, service, or business. Businesses are under no obligation to seek BBB accreditation, "
    "and some businesses are not accredited because they have not sought BBB accreditation."
)

COMPLAINT_DISCLAIMER = (
    "When considering complaint information, please consider the company's size and volume of transactions. "
    "Note that the nature of complaints and a company's responses to them are often more important than "
    "the number of complaints. BBB Business Profiles generally cover a three-year reporting period."
)

# Approximate coordinates for the seeded cities, used for "near <city>" ranking.
CITY_COORDS = {
    ("Redmond", "WA"): (47.67, -122.12), ("Bellevue", "WA"): (47.61, -122.20),
    ("Kirkland", "WA"): (47.68, -122.21), ("Issaquah", "WA"): (47.54, -122.43),
    ("Seattle", "WA"): (47.61, -122.33), ("Lynnwood", "WA"): (47.82, -122.31),
    ("Renton", "WA"): (47.48, -122.22), ("Everett", "WA"): (47.98, -122.20),
    ("Bothell", "WA"): (47.79, -122.18), ("Kent", "WA"): (47.38, -122.23),
    ("Woodinville", "WA"): (47.75, -122.16), ("Shoreline", "WA"): (47.76, -122.34),
    ("Edmonds", "WA"): (47.81, -122.38), ("Auburn", "WA"): (47.31, -122.23),
    ("Vancouver", "WA"): (45.63, -122.67), ("Tumwater", "WA"): (47.00, -122.91),
    ("Bremerton", "WA"): (47.57, -122.63), ("Olympia", "WA"): (47.04, -122.90),
    ("Tacoma", "WA"): (47.25, -122.44), ("Puyallup", "WA"): (47.19, -122.29),
    ("Portland", "OR"): (45.52, -122.68), ("Denver", "CO"): (39.74, -104.99),
    ("Austin", "TX"): (30.27, -97.74), ("Chicago", "IL"): (41.88, -87.63),
    ("New York", "NY"): (40.71, -74.01), ("San Francisco", "CA"): (37.77, -122.42),
    ("Phoenix", "AZ"): (33.45, -112.07), ("Boston", "MA"): (42.36, -71.06),
}

# Rough state centroids as a fallback for cities without coordinates.
STATE_CENTER = {
    "WA": (47.4, -120.5), "OR": (44.0, -120.5), "CO": (39.0, -105.5),
    "TX": (31.0, -99.0), "IL": (40.0, -89.0), "NY": (43.0, -75.0),
    "CA": (37.0, -120.0), "AZ": (34.3, -111.7), "MA": (42.3, -71.8),
}


def city_distance_miles(city_a, state_a, city_b, state_b):
    import math
    point_a = CITY_COORDS.get((city_a, state_a)) or STATE_CENTER.get(state_a) or (39.5, -98.35)
    point_b = CITY_COORDS.get((city_b, state_b)) or STATE_CENTER.get(state_b) or (39.5, -98.35)
    lat1, lon1 = point_a
    lat2, lon2 = point_b
    return math.hypot((lat1 - lat2) * 69.0, (lon1 - lon2) * 54.6)


def slugify(text):
    text = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return text or "x"


# --------------------------------------------------------------------------- models

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(140), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(90), default="")
    state = db.Column(db.String(60), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    favorites = db.relationship("Favorite", backref="user", lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship("Review", backref="user", lazy=True, cascade="all, delete-orphan")
    complaints = db.relationship("Complaint", backref="user", lazy=True, cascade="all, delete-orphan")
    scam_submissions = db.relationship("ScamSubmission", backref="user", lazy=True, cascade="all, delete-orphan")
    quote_requests = db.relationship("QuoteRequest", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode("utf-8")

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Business(db.Model):
    __tablename__ = "businesses"
    id = db.Column(db.Integer, primary_key=True)  # upstream BBB business id
    name = db.Column(db.String(200), nullable=False, index=True)
    slug_key = db.Column(db.String(220), unique=True, nullable=False)  # autosys-inc-1296-506207
    primary_category = db.Column(db.String(120), nullable=False)
    primary_category_slug = db.Column(db.String(140), nullable=False)
    categories = db.Column(db.Text, default="")  # JSON list
    address = db.Column(db.String(200), default="")
    city = db.Column(db.String(90), nullable=False, index=True)
    city_slug = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(4), nullable=False, index=True)
    state_slug = db.Column(db.String(4), nullable=False)
    zip = db.Column(db.String(12), default="")
    phone = db.Column(db.String(30), default="")
    phones_extra = db.Column(db.Text, default="[]")  # JSON list
    fax = db.Column(db.String(30), default="")
    website = db.Column(db.String(240), default="")
    websites_extra = db.Column(db.Text, default="[]")  # JSON list
    social = db.Column(db.Text, default="[]")  # JSON list of platform names
    about = db.Column(db.Text, default="")
    products_services = db.Column(db.Text, default="[]")  # JSON list
    local_bbb = db.Column(db.String(120), default="BBB Great West + Pacific")
    file_opened = db.Column(db.String(20), default="")
    started = db.Column(db.String(20), default="")
    started_locally = db.Column(db.String(20), default="")
    incorporated = db.Column(db.String(20), default="")
    entity_type = db.Column(db.String(80), default="")
    alternate_names = db.Column(db.Text, default="[]")  # JSON list
    management = db.Column(db.Text, default="[]")  # JSON list
    employees = db.Column(db.String(40), default="")
    principal_contacts = db.Column(db.Text, default="[]")  # JSON list
    customer_contacts = db.Column(db.Text, default="[]")  # JSON list
    payment_methods = db.Column(db.String(300), default="")
    refund_policy = db.Column(db.Text, default="")
    rating = db.Column(db.String(4), default="NR", index=True)
    rating_reason = db.Column(db.Text, default="")
    accredited = db.Column(db.Boolean, default=False, index=True)
    accredited_since = db.Column(db.String(20), default="")
    years_in_business = db.Column(db.Integer, default=0)
    service_area = db.Column(db.Boolean, default=False)
    offers_quotes = db.Column(db.Boolean, default=False)
    logo = db.Column(db.String(240), default="")
    photos = db.Column(db.Text, default="[]")  # JSON list of paths
    industry_tip = db.Column(db.Text, default="")
    hours = db.Column(db.Text, default="")  # JSON {days: hours}
    bureau_id = db.Column(db.Integer, default=1296)
    reviews_total = db.Column(db.Integer, default=0)  # upstream lifetime count
    complaints_total = db.Column(db.Integer, default=0)  # upstream last-3-years count
    complaints_closed_12m = db.Column(db.Integer, default=0)

    reviews = db.relationship("Review", backref="business", lazy=True, cascade="all, delete-orphan")
    complaints = db.relationship("Complaint", backref="business", lazy=True, cascade="all, delete-orphan")

    def cat_list(self):
        try:
            return json.loads(self.categories or "[]")
        except ValueError:
            return []

    def _jlist(self, field):
        try:
            value = json.loads(getattr(self, field) or "[]")
            return value if isinstance(value, list) else []
        except ValueError:
            return []

    def products_services_list(self):
        return self._jlist("products_services")

    def alternate_names_list(self):
        return self._jlist("alternate_names")

    def management_list(self):
        return self._jlist("management")

    def principal_contacts_list(self):
        return self._jlist("principal_contacts")

    def customer_contacts_list(self):
        return self._jlist("customer_contacts")

    def phones_extra_list(self):
        return self._jlist("phones_extra")

    def websites_extra_list(self):
        return self._jlist("websites_extra")

    def social_list(self):
        return self._jlist("social")

    def photos_list(self):
        try:
            return json.loads(self.photos or "[]")
        except ValueError:
            return []

    def review_count(self):
        return len(self.reviews)

    def avg_rating(self):
        if not self.reviews:
            return None
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)

    def profile_path(self):
        return f"/us/{self.state_slug}/{self.city_slug}/profile/{self.primary_category_slug}/{self.slug_key}"


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    author_name = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    text = db.Column(db.Text, nullable=False)
    review_date = db.Column(db.String(20), nullable=False)  # MM/DD/YYYY
    sort_date = db.Column(db.String(20), default="", index=True)  # YYYY-MM-DD


class Complaint(db.Model):
    __tablename__ = "complaints"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    author_name = db.Column(db.String(120), default="")
    complaint_type = db.Column(db.String(80), nullable=False)  # e.g. Service or Repair Issues
    status = db.Column(db.String(40), nullable=False, index=True)  # Resolved/Answered/...
    complaint_date = db.Column(db.String(20), nullable=False)  # MM/DD/YYYY
    sort_date = db.Column(db.String(20), default="", index=True)  # YYYY-MM-DD
    amount = db.Column(db.String(40), default="")
    text = db.Column(db.Text, nullable=False)
    business_response = db.Column(db.Text, default="")
    business_response_date = db.Column(db.String(20), default="")
    customer_answer = db.Column(db.Text, default="")
    customer_answer_date = db.Column(db.String(20), default="")


class AdPlacement(db.Model):
    __tablename__ = "ad_placements"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    business = db.relationship("Business")
    find_text = db.Column(db.String(120), index=True, nullable=False)
    find_loc = db.Column(db.String(120), index=True, nullable=False, default="")


class ScamReport(db.Model):
    __tablename__ = "scam_reports"
    id = db.Column(db.Integer, primary_key=True)
    scam_id = db.Column(db.Integer, unique=True, nullable=False)
    scam_type = db.Column(db.String(80), nullable=False, index=True)
    description = db.Column(db.Text, default="")
    target_city = db.Column(db.String(90), default="")
    target_state = db.Column(db.String(4), default="", index=True)
    target_zip = db.Column(db.String(12), default="")
    target_country = db.Column(db.String(20), default="USA")
    scammer_address = db.Column(db.String(200), default="")
    scammer_city = db.Column(db.String(90), default="")
    scammer_state = db.Column(db.String(4), default="")
    scammer_zip = db.Column(db.String(12), default="")
    scammer_phone = db.Column(db.String(30), default="")
    scammer_email = db.Column(db.String(160), default="")
    scammer_url = db.Column(db.String(240), default="")
    scammer_business_name = db.Column(db.String(160), default="")
    dollar_value = db.Column(db.Integer, default=0)
    date_reported = db.Column(db.String(20), nullable=False, index=True)  # YYYY-MM-DD


class ScamSubmission(db.Model):
    __tablename__ = "scam_submissions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    scam_type = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    target_city = db.Column(db.String(90), default="")
    target_state = db.Column(db.String(4), default="")
    target_zip = db.Column(db.String(12), default="")
    scammer_phone = db.Column(db.String(30), default="")
    scammer_email = db.Column(db.String(160), default="")
    scammer_url = db.Column(db.String(240), default="")
    scammer_business_name = db.Column(db.String(160), default="")
    dollar_value = db.Column(db.Integer, default=0)
    date_reported = db.Column(db.String(20), nullable=False)


class Favorite(db.Model):
    __tablename__ = "favorites"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    business = db.relationship("Business")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class QuoteRequest(db.Model):
    __tablename__ = "quote_requests"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    business = db.relationship("Business")
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(30), default="")
    service_needed = db.Column(db.String(200), default="")
    message = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Article(db.Model):
    __tablename__ = "articles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    title = db.Column(db.String(240), nullable=False)
    category = db.Column(db.String(80), default="News")
    published = db.Column(db.String(20), nullable=False)  # YYYY-MM-DD
    excerpt = db.Column(db.String(400), default="")
    body = db.Column(db.Text, default="")
    image = db.Column(db.String(240), default="")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------------- helpers

def parse_loc(value):
    """'Redmond, WA' -> ('Redmond', 'WA'); '98052' -> zip lookup."""
    value = (value or "").strip()
    if not value:
        return None, None, None
    m = re.match(r"^(.*?)[,\s]+([A-Za-z]{2})$", value)
    if m:
        return m.group(1).strip(), m.group(2).upper(), None
    return value, None, None


def tokenize(query):
    return [t.lower() for t in re.split(r"[^a-z0-9]+", (query or "").lower())
            if t and t not in STOP_WORDS and len(t) > 1]


def scored_businesses(query):
    """Token-overlap scored search across name, categories, about, products.
    Returns a list of (business, score) sorted by descending score."""
    tokens = tokenize(query)
    if not tokens:
        return []
    results = []
    for biz in Business.query.all():
        hay_parts = [biz.name, biz.primary_category, biz.about or "",
                     " ".join(biz.cat_list()),
                     " ".join(json.loads(biz.products_services or "[]"))]
        hay = " ".join(hay_parts).lower()
        score = sum(1 for t in tokens if t in hay)
        if score > 0:
            results.append((biz, score))
    results.sort(key=lambda pair: (-pair[1], pair[0].name.lower()))
    return results


def rating_rank(rating):
    try:
        return RATING_ORDER.index(rating)
    except ValueError:
        return len(RATING_ORDER)


def search_businesses(find_text, find_loc, page=1, accredited=None, ratings=None,
                      category=None, service_area=None, quotes=None, sort="best"):
    """Mirror of the upstream /search pipeline. Returns (rows, total, pages)."""
    city, state, _ = parse_loc(find_loc)
    if find_text:
        scored = scored_businesses(find_text)
        score_map = {b.id: s for b, s in scored}
        base = [b for b, _ in scored]
    else:
        score_map = {}
        base = list(Business.query.order_by(Business.name).all())
    # Location scoping: businesses in the same state (or ~80 miles of the
    # requested city, which keeps border-metro businesses in scope).
    if city and state:
        base = [b for b in base
                if b.state == state
                or city_distance_miles(city, state, b.city, b.state) <= 80]
        base.sort(key=lambda b: (city_distance_miles(city, state, b.city, b.state), b.name.lower()))
    # Filters
    if accredited:
        base = [b for b in base if b.accredited]
    if ratings:
        base = [b for b in base if b.rating in ratings]
    if category:
        base = [b for b in base if any(category.lower() == c.lower() for c in b.cat_list())]
    if service_area:
        base = [b for b in base if b.service_area]
    if quotes:
        base = [b for b in base if b.offers_quotes]
    # Sorting
    if sort == "distance" and city and state:
        base.sort(key=lambda b: (city_distance_miles(city, state, b.city, b.state), -int(b.accredited), b.name.lower()))
    elif sort == "rating":
        base.sort(key=lambda b: (rating_rank(b.rating), -int(b.accredited), b.name.lower()))
    else:  # best match: accredited first, then relevance score, then name
        base.sort(key=lambda b: (-int(b.accredited), -score_map.get(b.id, 0), b.name.lower()))
    total = len(base)
    per_page = 15
    pages = max(1, math.ceil(total / per_page))
    page = min(max(1, page), pages)
    start = (page - 1) * per_page
    return base[start:start + per_page], total, pages


def related_categories(find_text):
    cats = {}
    tokens = tokenize(find_text)
    for biz in Business.query.all():
        for c in biz.cat_list():
            cats.setdefault(c, 0)
    out = []
    for c in sorted(cats):
        low = c.lower()
        if any(t in low for t in tokens):
            out.append(c)
    for c in sorted(cats):
        if c not in out:
            out.append(c)
    return out[:8]


def business_or_404(state, city, category, slug_key):
    biz = Business.query.filter_by(
        state_slug=state, city_slug=city, primary_category_slug=category,
        slug_key=slug_key).first()
    if not biz:
        abort(404)
    return biz


def parse_date_text(text):
    """MM/DD/YYYY or YYYY-MM-DD -> YYYY-MM-DD"""
    text = (text or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return "1970-01-01"


def parse_user_date(text):
    """Strict user-input date: YYYY-MM-DD or None."""
    text = (text or "").strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None


def flash_errors_if_any(*pairs):
    for label, value in pairs:
        if not value or not str(value).strip():
            flash(f"{label} is required.", "error")
            return False
    return True


# --------------------------------------------------------------------------- routes

@app.route("/")
def index():
    hero_stats = {
        "businesses": Business.query.count(),
        "scam_reports": ScamReport.query.count(),
    }
    return render_template("index.html", hero_stats=hero_stats)


@app.route("/search")
def search():
    find_text = request.args.get("find_text", "").strip()
    find_loc = request.args.get("find_loc", "Redmond, WA").strip() or "Redmond, WA"
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    accredited = request.args.get("accredited") in ("y", "1", "on")
    ratings = [r for r in request.args.getlist("ratings") if r in RATING_ORDER]
    category = request.args.get("category", "").strip()
    service_area = request.args.get("service_area") in ("y", "1", "on")
    quotes = request.args.get("quotes") in ("y", "1", "on")
    sort = request.args.get("sort", "best")
    if sort not in ("best", "distance", "rating"):
        sort = "best"
    rows, total, pages = search_businesses(
        find_text, find_loc, page, accredited, ratings, category,
        service_area, quotes, sort)
    ad_rows = []
    if page == 1 and not (accredited or ratings or category or service_area or quotes):
        ad_rows = [a.business for a in AdPlacement.query.filter_by(
            find_text=find_text, find_loc=find_loc).limit(2).all()]
    city, state, _ = parse_loc(find_loc)
    return render_template(
        "search.html", find_text=find_text, find_loc=find_loc, rows=rows,
        ads=ad_rows,
        total=total, pages=pages, page=page, accredited=accredited,
        ratings=ratings, category=category, service_area=service_area,
        quotes=quotes, sort=sort, related=related_categories(find_text),
        city=city, state=state)


@app.route("/us/<state>/<city>/profile/<category>/<slug_key>")
def profile_main(state, city, category, slug_key):
    biz = business_or_404(state, city, category, slug_key)
    latest = sorted(biz.reviews, key=lambda r: r.sort_date, reverse=True)[:3]
    return render_template("profile_main.html", biz=biz, latest_reviews=latest,
                          profile_disclaimer=PROFILE_DISCLAIMER,
                          complaint_disclaimer=COMPLAINT_DISCLAIMER)


@app.route("/us/<state>/<city>/profile/<category>/<slug_key>/customer-reviews")
def profile_reviews(state, city, category, slug_key):
    biz = business_or_404(state, city, category, slug_key)
    sort = request.args.get("sort", "recent")
    reviews = list(biz.reviews)
    if sort == "highest":
        reviews.sort(key=lambda r: (-r.rating, r.sort_date))
    elif sort == "lowest":
        reviews.sort(key=lambda r: (r.rating, r.sort_date))
    else:
        reviews.sort(key=lambda r: r.sort_date, reverse=True)
        sort = "recent"
    avg = biz.avg_rating()
    dist = {n: len([r for r in biz.reviews if r.rating == n]) for n in range(1, 6)}
    return render_template("profile_reviews.html", biz=biz, reviews=reviews,
                           sort=sort, avg=avg, dist=dist,
                           profile_disclaimer=PROFILE_DISCLAIMER,
                           complaint_disclaimer=COMPLAINT_DISCLAIMER)


@app.route("/us/<state>/<city>/profile/<category>/<slug_key>/complaints")
def profile_complaints(state, city, category, slug_key):
    biz = business_or_404(state, city, category, slug_key)
    status = request.args.get("status", "")
    ctype = request.args.get("type", "")
    complaints = list(biz.complaints)
    if status:
        complaints = [c for c in complaints if c.status == status]
    if ctype:
        complaints = [c for c in complaints if c.complaint_type == ctype]
    complaints.sort(key=lambda c: c.sort_date, reverse=True)
    status_counts = {}
    for c in biz.complaints:
        status_counts[c.status] = status_counts.get(c.status, 0) + 1
    type_counts = {}
    for c in biz.complaints:
        type_counts[c.complaint_type] = type_counts.get(c.complaint_type, 0) + 1
    last12 = 0
    for c in biz.complaints:
        if c.sort_date >= "2025-09-21":
            last12 += 1
    return render_template("profile_complaints.html", biz=biz,
                           complaints=complaints, status_counts=status_counts,
                           type_counts=type_counts, last12=last12,
                           status_filter=status, type_filter=ctype,
                           status_help=COMPLAINT_STATUS_HELP,
                           profile_disclaimer=PROFILE_DISCLAIMER,
                           complaint_disclaimer=COMPLAINT_DISCLAIMER)


# --------------------------------------------------------------- intake flows

@app.route("/leave-a-review")
def leave_a_review():
    find_text = request.args.get("find_text", "").strip()
    rows = []
    if find_text:
        rows = [b for b, _score in scored_businesses(find_text)][:10]
    return render_template("leave_review.html", find_text=find_text, rows=rows)


@app.route("/leave-a-review/<int:biz_id>", methods=["GET", "POST"])
def leave_a_review_form(biz_id):
    biz = db.session.get(Business, biz_id) or abort(404)
    if request.method == "POST":
        rating = request.form.get("rating", "")
        text = request.form.get("text", "").strip()
        author = request.form.get("author", "").strip()
        date = request.form.get("experience_date", "").strip()
        ok = True
        if rating not in {"1", "2", "3", "4", "5"}:
            flash("Select a star rating.", "error")
            ok = False
        if len(text) < 30:
            flash("Please describe your experience (at least 30 characters).", "error")
            ok = False
        if not author:
            flash("Your name is required.", "error")
            ok = False
        if not date:
            flash("The date of your experience is required.", "error")
            ok = False
        when = parse_user_date(date) if date else None
        if when is None:
            flash("Enter the date in YYYY-MM-DD format.", "error")
            ok = False
        if ok:
            review = Review(
                business_id=biz.id,
                user_id=current_user.id if current_user.is_authenticated else None,
                author_name=author, rating=int(rating), text=text,
                review_date=when.strftime("%m/%d/%Y"),
                sort_date=date)
            db.session.add(review)
            db.session.commit()
            flash("Thank you! Your customer review has been submitted.", "success")
            return redirect(biz.profile_path() + "/customer-reviews")
    return render_template("review_form.html", biz=biz)


@app.route("/file-a-complaint", methods=["GET", "POST"])
def file_a_complaint():
    if request.method == "POST":
        goal = request.form.get("goal", "")
        if goal == "review":
            return redirect(url_for("leave_a_review"))
        if goal == "scam":
            return redirect(url_for("scam_report"))
    find_text = request.args.get("find_text", "").strip()
    rows = []
    if find_text:
        rows = [b for b, _score in scored_businesses(find_text)][:10]
    return render_template("file_complaint.html", find_text=find_text, rows=rows)


@app.route("/file-a-complaint/<int:biz_id>", methods=["GET", "POST"])
def file_complaint_form(biz_id):
    biz = db.session.get(Business, biz_id) or abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        ctype = request.form.get("type", "").strip()
        date = request.form.get("date", "").strip()
        amount = request.form.get("amount", "").strip()
        text = request.form.get("text", "").strip()
        ok = True
        if not name:
            flash("Your name is required.", "error"); ok = False
        if not email or "@" not in email:
            flash("A valid email address is required.", "error"); ok = False
        if not ctype:
            flash("Select the complaint type.", "error"); ok = False
        if not date:
            flash("The date of the issue is required.", "error"); ok = False
        elif parse_user_date(date) is None:
            flash("Enter the date in YYYY-MM-DD format.", "error"); ok = False
        if len(text) < 30:
            flash("Describe your complaint (at least 30 characters).", "error"); ok = False
        if ok:
            complaint = Complaint(
                business_id=biz.id,
                user_id=current_user.id if current_user.is_authenticated else None,
                author_name=name, complaint_type=ctype, status="Unanswered",
                complaint_date=parse_user_date(date).strftime("%m/%d/%Y") if parse_user_date(date) else "",
                sort_date=date, amount=amount, text=text)
            db.session.add(complaint)
            db.session.commit()
            flash("Your complaint has been submitted to BBB.", "success")
            return redirect(biz.profile_path() + "/complaints")
    return render_template("complaint_form.html", biz=biz,
                           complaint_types=["Advertising or Sales Issues",
                                            "Billing or Collection Issues",
                                            "Problems with Product or Service",
                                            "Delivery Issues",
                                            "Guarantee or Warranty Issues",
                                            "Service or Repair Issues"])


@app.route("/get-a-quote")
def get_a_quote():
    find_text = request.args.get("find_text", "").strip()
    rows = []
    if find_text:
        rows = [b for b, _score in scored_businesses(find_text)
                if b.offers_quotes][:10]
    return render_template("get_quote.html", find_text=find_text, rows=rows)


@app.route("/get-a-quote/<int:biz_id>", methods=["GET", "POST"])
def get_quote_form(biz_id):
    biz = db.session.get(Business, biz_id) or abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        service_needed = request.form.get("service_needed", "").strip()
        message = request.form.get("message", "").strip()
        ok = True
        if not name:
            flash("Your name is required.", "error"); ok = False
        if not email or "@" not in email:
            flash("A valid email address is required.", "error"); ok = False
        if not phone:
            flash("A phone number is required so the business can reach you.", "error"); ok = False
        if not service_needed:
            flash("Select the service you need.", "error"); ok = False
        if ok:
            qr = QuoteRequest(
                business_id=biz.id,
                user_id=current_user.id if current_user.is_authenticated else None,
                name=name, email=email, phone=phone,
                service_needed=service_needed, message=message)
            db.session.add(qr)
            db.session.commit()
            flash("Your quote request has been sent to the business.", "success")
            return redirect(biz.profile_path())
    return render_template("quote_form.html", biz=biz)


# --------------------------------------------------------------- scam tracker

@app.route("/scamtracker")
def scamtracker_home():
    total = ScamReport.query.count()
    states = db.session.query(ScamReport.target_state).distinct().count()
    recent = ScamReport.query.order_by(ScamReport.date_reported.desc()).limit(5).all()
    top_types = db.session.query(
        ScamReport.scam_type, db.func.count(ScamReport.id)).group_by(
        ScamReport.scam_type).order_by(db.func.count(ScamReport.id).desc()).limit(6).all()
    return render_template("scamtracker_home.html", total=total,
                           states=states, recent=recent, top_types=top_types)


@app.route("/scamtracker/lookupscam")
def scam_lookup():
    q = request.args.get("q", "").strip()
    scam_type = request.args.get("scam_type", "").strip()
    state = request.args.get("state", "").strip()
    min_dollars = request.args.get("min_dollars", "").strip()
    max_dollars = request.args.get("max_dollars", "").strip()
    from_date = request.args.get("from_date", "").strip()
    to_date = request.args.get("to_date", "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    # Upstream packs a mini query language into q, e.g. q=scam_type=Charity&from=0
    if "=" in q:
        keyword = ""
        for part in q.split("&"):
            if "=" not in part:
                keyword = part.strip()
                continue
            key, _, value = part.partition("=")
            key, value = key.strip(), value.strip()
            if key == "scam_type":
                scam_type = value
            elif key == "from" and value.isdigit():
                page = int(value) // 10 + 1
            elif key == "location":
                state = value
            elif key == "keyword":
                keyword = value
        q = keyword
    rows = ScamReport.query
    if q:
        like = f"%{q}%"
        rows = rows.filter(db.or_(
            ScamReport.description.like(like),
            ScamReport.scammer_phone.like(like),
            ScamReport.scammer_email.like(like),
            ScamReport.scammer_url.like(like),
            ScamReport.scammer_business_name.like(like),
            db.cast(ScamReport.scam_id, db.String) == q))
    if scam_type:
        rows = rows.filter(ScamReport.scam_type == scam_type)
    if state:
        rows = rows.filter(ScamReport.target_state == state.upper())
    if from_date:
        rows = rows.filter(ScamReport.date_reported >= from_date)
    if to_date:
        rows = rows.filter(ScamReport.date_reported <= to_date)
    if min_dollars.isdigit():
        rows = rows.filter(ScamReport.dollar_value >= int(min_dollars))
    if max_dollars.isdigit():
        rows = rows.filter(ScamReport.dollar_value <= int(max_dollars))
    total = rows.count()
    per_page = 10
    pages = max(1, math.ceil(total / per_page))
    page = min(page, pages)
    rows = (rows.order_by(ScamReport.date_reported.desc(), ScamReport.scam_id.desc())
            .offset((page - 1) * per_page).limit(per_page).all())
    types = [t[0] for t in db.session.query(ScamReport.scam_type).distinct().order_by(ScamReport.scam_type)]
    states_list = [s[0] for s in db.session.query(ScamReport.target_state).distinct()
                   .order_by(ScamReport.target_state) if s[0]]
    return render_template("scam_lookup.html", rows=rows, total=total, pages=pages,
                           page=page, q=q, scam_type=scam_type, state=state,
                           min_dollars=min_dollars, max_dollars=max_dollars,
                           from_date=from_date, to_date=to_date, types=types,
                           states_list=states_list)


@app.route("/scamtracker/lookupscam/<int:scam_id>")
def scam_detail(scam_id):
    report = ScamReport.query.filter_by(scam_id=scam_id).first() or abort(404)
    similar = ScamReport.query.filter(
        ScamReport.scam_type == report.scam_type,
        ScamReport.scam_id != report.scam_id).order_by(
        ScamReport.date_reported.desc()).limit(3).all()
    return render_template("scam_detail.html", report=report, similar=similar)


@app.route("/scamtracker/reportscam", methods=["GET", "POST"])
def scam_report():
    if request.method == "POST":
        scam_type = request.form.get("scam_type", "").strip()
        description = request.form.get("description", "").strip()
        target_city = request.form.get("target_city", "").strip()
        target_state = request.form.get("target_state", "").strip().upper()
        target_zip = request.form.get("target_zip", "").strip()
        scammer_phone = request.form.get("scammer_phone", "").strip()
        scammer_email = request.form.get("scammer_email", "").strip()
        scammer_url = request.form.get("scammer_url", "").strip()
        business_name = request.form.get("business_name", "").strip()
        dollar_value = request.form.get("dollar_value", "0").strip()
        ok = True
        if not scam_type:
            flash("Select the scam type.", "error"); ok = False
        if len(description) < 30:
            flash("Describe what happened (at least 30 characters).", "error"); ok = False
        if not target_city or not target_state:
            flash("Your city and state are required.", "error"); ok = False
        if ok:
            value = int(dollar_value.replace(",", "").replace("$", "") or 0)
            sub = ScamSubmission(
                user_id=current_user.id if current_user.is_authenticated else None,
                scam_type=scam_type, description=description,
                target_city=target_city, target_state=target_state,
                target_zip=target_zip, scammer_phone=scammer_phone,
                scammer_email=scammer_email, scammer_url=scammer_url,
                scammer_business_name=business_name, dollar_value=value,
                date_reported=MIRROR_REFERENCE_DATE.strftime("%Y-%m-%d"))
            db.session.add(sub)
            db.session.commit()
            flash("Thank you. Your scam report helps others avoid this scam.", "success")
            return redirect(url_for("scam_lookup"))
    types = [t[0] for t in db.session.query(ScamReport.scam_type).distinct().order_by(ScamReport.scam_type)]
    return render_template("scam_report.html", types=types)


def _load_us_state_paths():
    """Parse per-state path geometry from the bundled US states SVG (chart element)."""
    import re as _re
    svg_path = os.path.join(BASE_DIR, "static", "icons", "us_states.svg")
    try:
        svg = pathlib_like_read(svg_path)
    except OSError:
        return {}
    paths = {}
    for match in _re.finditer(r'id="([a-z]{2})"[^>]*aria-label="([^"]+)"[^>]*d="([^"]+)"', svg, _re.S):
        paths[match.group(1).upper()] = match.group(3)
    return paths


def pathlib_like_read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


US_STATE_PATHS = _load_us_state_paths()


@app.route("/scamtracker/dashboard")
def scam_dashboard():
    period = request.args.get("period", "12m")
    if period not in ("30d", "90d", "12m", "all"):
        period = "12m"
    metric = request.args.get("metric", "losses")
    if metric not in ("losses", "reports", "median"):
        metric = "losses"
    cutoffs = {"30d": "2026-08-21", "90d": "2026-06-23", "12m": "2025-09-21", "all": "1970-01-01"}
    cutoff = cutoffs[period]
    rows = ScamReport.query.filter(ScamReport.date_reported >= cutoff).all()
    by_state = {}
    for r in rows:
        st = r.target_state or "--"
        rec = by_state.setdefault(st, {"reports": 0, "losses": 0.0, "lost_reports": 0})
        rec["reports"] += 1
        rec["losses"] += (r.dollar_value or 0)
        if (r.dollar_value or 0) > 0:
            rec["lost_reports"] += 1
    losses = [r.dollar_value for r in rows if (r.dollar_value or 0) > 0]
    losses.sort()
    median = 0
    if losses:
        median = losses[len(losses) // 2]
    stats = {
        "reports": len(rows),
        "median_loss": median,
        "pct_loss": round(100.0 * len(losses) / len(rows), 1) if rows else 0,
        "locations": len(by_state),
    }
    top_types = {}
    for r in rows:
        top_types[r.scam_type] = top_types.get(r.scam_type, 0) + 1
    top_types = sorted(top_types.items(), key=lambda kv: -kv[1])[:8]
    # choropleth fills: color each state by the selected metric's intensity
    if metric == "losses":
        values = {st: rec["losses"] for st, rec in by_state.items()}
    elif metric == "median":
        values = {}
        for st, rec in by_state.items():
            values[st] = (rec["losses"] / rec["lost_reports"]) if rec["lost_reports"] else 0
    else:
        values = {st: rec["reports"] for st, rec in by_state.items()}
    max_value = max(values.values()) if values else 1
    fills = {}
    labels = {}
    for st, value in values.items():
        intensity = min(1.0, value / max_value) if max_value else 0
        lightness = int(88 - intensity * 55)
        fills[st] = f"hsl(38, 85%, {lightness}%)"
        if metric == "losses":
            labels[st] = "${:,}".format(int(value))
        elif metric == "median":
            labels[st] = "${:,}".format(int(value))
        else:
            labels[st] = "{:,}".format(int(value))
    return render_template("scam_dashboard.html", stats=stats,
                           by_state=by_state, period=period, metric=metric,
                           top_types=top_types, us_paths=US_STATE_PATHS,
                           fills=fills, labels=labels)


# --------------------------------------------------------------- about / news

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/about/find-your-local-bbb")
def local_bbb():
    rows = (db.session.query(Business.local_bbb, db.func.count(Business.id))
            .group_by(Business.local_bbb)
            .order_by(Business.local_bbb).all())
    return render_template("local_bbbs.html", locals_=rows)


@app.route("/about/our-impact")
def our_impact():
    return render_template("our_impact.html",
                           businesses=Business.query.count(),
                           scam_reports=ScamReport.query.count(),
                           complaints=Complaint.query.count(),
                           reviews=Review.query.count())


@app.route("/get-accredited")
def get_accredited():
    return render_template("get_accredited.html")


@app.route("/get-listed")
def get_listed():
    return render_template("get_listed.html")


@app.route("/us/news")
def news():
    articles = Article.query.order_by(Article.published.desc()).all()
    return render_template("news.html", articles=articles)


@app.route("/us/news/<slug>")
def article(slug):
    a = Article.query.filter_by(slug=slug).first() or abort(404)
    return render_template("article.html", a=a)


# --------------------------------------------------------------- auth / account

@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("You are signed in to your BBB account.", "success")
            nxt = request.args.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            return redirect(url_for("account"))
        flash("The email or password you entered is incorrect.", "error")
    return render_template("signin.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = email.split("@")[0]
        display = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        if not display or not email or "@" not in email:
            flash("A name and a valid email address are required.", "error")
        elif len(password) < 8:
            flash("Choose a password of at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(username=username, email=email, display_name=display,
                        city=city, state=state)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome! Your BBB account is ready.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You are signed out.", "success")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    favorites = Favorite.query.filter_by(user_id=current_user.id).all()
    reviews = Review.query.filter_by(user_id=current_user.id).order_by(Review.sort_date.desc()).all()
    complaints = Complaint.query.filter_by(user_id=current_user.id).order_by(Complaint.sort_date.desc()).all()
    scam_subs = ScamSubmission.query.filter_by(user_id=current_user.id).order_by(ScamSubmission.id.desc()).all()
    return render_template("account.html", favorites=favorites, reviews=reviews,
                           complaints=complaints, scam_subs=scam_subs)


@app.route("/account/favorites/toggle/<int:biz_id>", methods=["POST"])
@login_required
def toggle_favorite(biz_id):
    biz = db.session.get(Business, biz_id)
    if not biz:
        abort(404)
    fav = Favorite.query.filter_by(user_id=current_user.id, business_id=biz_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash(f"{biz.name} removed from your saved businesses.", "success")
    else:
        db.session.add(Favorite(user_id=current_user.id, business_id=biz_id))
        db.session.commit()
        flash(f"{biz.name} saved to your list.", "success")
    return redirect(request.referrer or url_for("account"))


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.context_processor
def inject_favorite_ids():
    if current_user.is_authenticated:
        ids = [f.business_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]
        return {"favorite_ids": ids}
    return {"favorite_ids": []}


@app.route("/_health")
def health():
    return {
        "ok": True,
        "site": "better_business_bureau",
        "businesses": Business.query.count(),
        "reviews": Review.query.count(),
        "complaints": Complaint.query.count(),
        "scam_reports": ScamReport.query.count(),
        "users": User.query.count(),
    }


with app.app_context():
    db.create_all()
    from seed_data import seed_benchmark_users, seed_database
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
