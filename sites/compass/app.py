"""Compass.com mirror — Flask app with real-estate browse + account features."""
import json
import math
import os
import re
import secrets
import sys
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import func, or_
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# seed_data imports these models by module name, including when launched as a script.
if __name__ == "__main__":
    sys.modules["app"] = sys.modules[__name__]

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = os.environ.get("COMPASS_SECRET_KEY") or secrets.token_hex(32)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + os.environ.get("COMPASS_DATABASE_PATH", os.path.join(BASE_DIR, "instance", "compass.db"))
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)


@sqlalchemy_event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, _record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to save homes, schedule tours, or contact an agent."
login_manager.login_message_category = "info"
csrf = CSRFProtect(app)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── Models ────────────────────────────────────────────────────────────────────


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(40), default="")
    budget_min = db.Column(db.Integer, default=0)
    budget_max = db.Column(db.Integer, default=0)
    beds_min = db.Column(db.Integer, default=0)
    preferred_property_types = db.Column(db.Text, default="[]")
    move_timeline = db.Column(db.String(40), default="")
    has_agent = db.Column(db.Boolean, default=False)
    receive_alerts = db.Column(db.Boolean, default=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"))
    created_at = db.Column(db.DateTime, default=utcnow)

    saved_homes = db.relationship("SavedHome", backref="user", lazy=True,
                                  cascade="all, delete-orphan")
    saved_searches = db.relationship("SavedSearch", backref="user", lazy=True,
                                     cascade="all, delete-orphan")
    tours = db.relationship("Tour", backref="user", lazy=True,
                            cascade="all, delete-orphan")
    inquiries = db.relationship("Inquiry", backref="user", lazy=True,
                                cascade="all, delete-orphan")
    collections = db.relationship("Collection", backref="user", lazy=True,
                                  cascade="all, delete-orphan")

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode("utf-8")

    def check_password(self, pw):
        # Support both bcrypt hashes (live registrations) and the
        # deterministic pbkdf2 hashes used for benchmark-seed users so the
        # seed DB stays byte-identical.
        from werkzeug.security import check_password_hash as wz_check
        try:
            if (self.password_hash or "").startswith("pbkdf2:"):
                return wz_check(self.password_hash, pw)
            return bcrypt.check_password_hash(self.password_hash, pw)
        except Exception:
            return False

    def get_property_types(self):
        try:
            return json.loads(self.preferred_property_types or "[]")
        except Exception:
            return []


class SeedMetadata(db.Model):
    __tablename__ = "seed_metadata"
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(64), unique=True, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=False)


class NeighborhoodGuide(db.Model):
    __tablename__ = "neighborhood_guides"
    slug = db.Column(db.String(80), primary_key=True)
    position = db.Column(db.Integer, nullable=False)
    directory_json = db.Column(db.Text, nullable=False)
    content_json = db.Column(db.Text, nullable=False)


class SellerInquiry(db.Model):
    __tablename__ = "seller_inquiries"
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class Agent(db.Model):
    __tablename__ = "agents"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(120), default="Real Estate Agent")
    photo = db.Column(db.String(250), default="")
    bio = db.Column(db.Text, default="")
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    license_number = db.Column(db.String(60), default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(40), default="")
    years_experience = db.Column(db.Integer)
    sales_volume_usd = db.Column(db.BigInteger)
    transactions_count = db.Column(db.Integer)
    languages = db.Column(db.Text, default="[]")
    specialties = db.Column(db.Text, default="[]")
    is_top_agent = db.Column(db.Boolean, default=False)

    listings = db.relationship("Listing", backref="agent", lazy=True)

    def get_languages(self):
        try:
            return json.loads(self.languages or "[]")
        except Exception:
            return []

    def get_specialties(self):
        try:
            return json.loads(self.specialties or "[]")
        except Exception:
            return []

    def sales_volume_display(self):
        if self.sales_volume_usd is None:
            return "Not available"
        v = self.sales_volume_usd or 0
        if v >= 1_000_000_000:
            return f"${v/1_000_000_000:.1f}B"
        if v >= 1_000_000:
            return f"${v/1_000_000:.0f}M"
        if v >= 1_000:
            return f"${v/1_000:.0f}K"
        return f"${v}"


class City(db.Model):
    __tablename__ = "cities"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(40), nullable=False)
    hero_image = db.Column(db.String(250), default="")
    blurb = db.Column(db.Text, default="")
    is_featured = db.Column(db.Boolean, default=False)


class Listing(db.Model):
    __tablename__ = "listings"
    id = db.Column(db.Integer, primary_key=True)
    listing_id_sha = db.Column(db.String(40), unique=True, index=True)
    market_city = db.Column(db.String(80), index=True)
    source_url = db.Column(db.Text, default="")
    source_retrieved_at = db.Column(db.String(40), default="")
    source_html_sha256 = db.Column(db.String(64), default="")
    property_facts_json = db.Column(db.Text, default="{}")
    regional_facts_json = db.Column(db.Text, default="{}")
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    address = db.Column(db.String(200), nullable=False)
    unit = db.Column(db.String(60), default="")
    neighborhood = db.Column(db.String(80), default="")
    city = db.Column(db.String(80), index=True)
    state = db.Column(db.String(40), index=True)
    zip = db.Column(db.String(20), default="")
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    status = db.Column(db.String(20), default="for-sale", index=True)
    is_rental = db.Column(db.Boolean, default=False)
    price = db.Column(db.Integer)
    beds = db.Column(db.Integer)
    baths_full = db.Column(db.Integer)
    baths_half = db.Column(db.Integer)
    baths_total = db.Column(db.Float)
    sqft = db.Column(db.Integer)
    lot_sqft = db.Column(db.Integer)
    year_built = db.Column(db.Integer)
    property_type = db.Column(db.String(40), default="", index=True)

    description = db.Column(db.Text, default="")
    features = db.Column(db.Text, default="[]")
    hero_image = db.Column(db.String(250), default="")
    gallery_images = db.Column(db.Text, default="[]")

    mls_number = db.Column(db.String(40), default="")
    hoa_fee_usd_month = db.Column(db.Integer)
    days_on_compass = db.Column(db.Integer)
    listed_at = db.Column(db.DateTime)

    is_open_house = db.Column(db.Boolean, default=False, index=True)
    open_house_date = db.Column(db.String(20), default="")
    open_house_time = db.Column(db.String(40), default="")

    is_new = db.Column(db.Boolean, default=False)
    is_compass_exclusive = db.Column(db.Boolean, default=False)
    is_luxury = db.Column(db.Boolean, default=False)
    is_pending = db.Column(db.Boolean, default=False)

    # Missing source evidence is unknown, not a negative amenity assertion.
    has_parking = db.Column(db.Boolean)
    has_pool = db.Column(db.Boolean)
    has_doorman = db.Column(db.Boolean)
    has_elevator = db.Column(db.Boolean)
    has_garage = db.Column(db.Boolean)
    has_waterfront = db.Column(db.Boolean)
    pets_allowed = db.Column(db.Boolean)
    furnished = db.Column(db.Boolean)

    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"))

    saved_by = db.relationship("SavedHome", backref="listing", lazy=True,
                               cascade="all, delete-orphan")
    tours = db.relationship("Tour", backref="listing", lazy=True,
                            cascade="all, delete-orphan")
    inquiries = db.relationship("Inquiry", backref="listing", lazy=True,
                                cascade="all, delete-orphan")

    def get_features(self):
        try:
            return json.loads(self.features or "[]")
        except Exception:
            return []

    def get_gallery(self):
        try:
            g = json.loads(self.gallery_images or "[]")
            return g if isinstance(g, list) else []
        except Exception:
            return []

    @property
    def baths(self):
        if self.baths_total is not None:
            return self.baths_total
        if self.baths_full is None and self.baths_half is None:
            return None
        return (self.baths_full or 0) + 0.5 * (self.baths_half or 0)

    def get_property_facts(self):
        return json.loads(self.property_facts_json or "{}")

    def get_regional_facts(self):
        return json.loads(self.regional_facts_json or "{}")

    def price_display(self):
        if not self.price:
            return "Price upon request"
        if self.is_rental or self.status == "for-rent":
            return f"${self.price:,}/mo"
        return f"${self.price:,}"

    def price_per_sqft(self):
        if not self.sqft or not self.price or self.is_rental or self.status == "for-rent":
            return 0
        return math.floor(self.price / self.sqft + 0.5)


class SavedHome(db.Model):
    __tablename__ = "saved_homes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False)
    note = db.Column(db.Text, default="")
    saved_at = db.Column(db.DateTime, default=utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "listing_id"),)


class SavedSearch(db.Model):
    __tablename__ = "saved_searches"
    __table_args__ = (db.UniqueConstraint("user_id", "name", name="uq_saved_search_user_name"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    criteria_json = db.Column(db.Text, nullable=False, default="{}")
    notify = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    def get_criteria(self):
        try:
            return json.loads(self.criteria_json or "{}")
        except Exception:
            return {}


class Tour(db.Model):
    __tablename__ = "tours"
    __table_args__ = (db.CheckConstraint("status IN ('requested','confirmed','cancelled')", name="ck_tour_status"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False)
    requested_date = db.Column(db.String(20), default="")
    requested_time = db.Column(db.String(40), default="")
    tour_type = db.Column(db.String(40), default="in-person")
    contact_phone = db.Column(db.String(40), default="")
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="requested")
    requested_at = db.Column(db.DateTime, default=utcnow)


class Inquiry(db.Model):
    __tablename__ = "inquiries"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"))
    name = db.Column(db.String(120), default="")
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    subject = db.Column(db.String(160), default="")
    message = db.Column(db.Text, default="")
    sent_at = db.Column(db.DateTime, default=utcnow)


class Collection(db.Model):
    __tablename__ = "collections"
    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_collection_user_name"),
        db.UniqueConstraint("share_token", name="uq_collection_share_token"),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    listing_ids_json = db.Column(db.Text, default="[]")
    share_token = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    def get_listing_ids(self):
        try:
            values = json.loads(self.listing_ids_json or "[]")
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid collection membership JSON") from error
        if (not isinstance(values, list) or len(values) > 200
                or not all(isinstance(value, int) and value > 0 for value in values)
                or len(values) != len(set(values))):
            raise ValueError("Invalid collection membership list")
        return values

    def set_listing_ids(self, ids):
        values = list(ids)
        if (len(values) > 200 or not all(isinstance(value, int) and value > 0 for value in values)
                or len(values) != len(set(values))):
            raise ValueError("Invalid collection membership list")
        self.listing_ids_json = json.dumps(values)

    def get_listings(self):
        ids = self.get_listing_ids()
        if not ids:
            return []
        rows = Listing.query.filter(Listing.id.in_(ids)).all()
        by_id = {r.id: r for r in rows}
        return [by_id[i] for i in ids if i in by_id]


# ─── Login loader ──────────────────────────────────────────────────────────────


@login_manager.user_loader
def load_user(uid):
    try:
        return db.session.get(User, int(uid))
    except (TypeError, ValueError):
        return None


@app.context_processor
def inject_globals():
    saved_count = 0
    if current_user.is_authenticated:
        saved_count = SavedHome.query.filter_by(user_id=current_user.id).count()
    return {
        "now": datetime.now(timezone.utc).replace(tzinfo=None),
        "csrf_token": generate_csrf,
        "FEATURED_CITIES": _featured_cities(),
        "saved_count": saved_count,
    }


def _featured_cities():
    return City.query.filter_by(is_featured=True).order_by(City.name).all()


# ─── Helpers ───────────────────────────────────────────────────────────────────

PROPERTY_TYPES = {"Single Family", "Condo", "Co-op", "Townhouse", "Multi-Family", "Apartment", "Land"}
SEARCH_FIELDS = ("q", "city", "status", "property_type", "price_min", "price_max", "beds", "baths", "sqft_min", "year_built_min", "pool", "garage", "waterfront", "doorman", "open_house", "new", "compass_exclusive", "sort")
SEARCH_SORTS = {"", "price_asc", "price_desc", "newest", "sqft_desc", "beds_desc", "ppsf_asc", "ppsf_desc"}
TOUR_TIMES = ["9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM"]


def local_return_url(value, fallback):
    """Only return to a path on this mirror after an account action."""
    if not value or "\\" in value or any(ord(c) < 32 for c in value):
        return fallback
    try:
        target = urlsplit(value)
        origin = urlsplit(request.host_url)
        if target.scheme or target.netloc:
            if (target.scheme, target.netloc) != (origin.scheme, origin.netloc):
                return fallback
        if not target.path.startswith("/") or target.path.startswith("//"):
            return fallback
        return target.path + ("?" + target.query if target.query else "")
    except ValueError:
        return fallback


def valid_email(value):
    try:
        validate_email(value, check_deliverability=False)
        return len(value) <= 120
    except EmailNotValidError:
        return False


def valid_password(value):
    return len(value) >= 6 and len(value.encode("utf-8")) <= 72


def valid_phone(value, allow_empty=True):
    value = (value or "").strip()
    if not value:
        return allow_empty
    digits = re.sub(r"\D", "", value)
    return (len(value) <= 40 and re.fullmatch(r"[+\d() .-]+", value) is not None
            and 7 <= len(digits) <= 15)


def valid_search_criteria(criteria):
    if set(criteria) - set(SEARCH_FIELDS):
        return False
    if len(json.dumps(criteria).encode("utf-8")) > 4096:
        return False
    if criteria.get("status", "") not in {"", "for-sale", "for-rent"}:
        return False
    if criteria.get("property_type", "") not in PROPERTY_TYPES | {""}:
        return False
    if criteria.get("sort", "") not in SEARCH_SORTS:
        return False
    for key, maximum in {"price_min": 10**12, "price_max": 10**12,
                         "beds": 100, "sqft_min": 10**9,
                         "year_built_min": 2100}.items():
        value = criteria.get(key, "")
        if value and (not value.isdigit() or int(value) > maximum):
            return False
    baths = criteria.get("baths", "")
    if baths and (not re.fullmatch(r"\d+(?:\.\d+)?", baths) or float(baths) > 100):
        return False
    for key in ("pool", "garage", "waterfront", "doorman", "open_house", "new", "compass_exclusive"):
        if criteria.get(key, "") not in {"", "1", "true", "on"}:
            return False
    return len(criteria.get("q", "")) <= 200 and len(criteria.get("city", "")) <= 80


def _tokens(s: str):
    if not s:
        return []
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t and len(t) > 1]


def _listing_corpus(L) -> str:
    parts = [
        L.address, L.unit or "", L.neighborhood or "", L.city or "", L.state or "",
        L.zip or "", L.property_type or "", L.status or "",
        L.description or "", " ".join(L.get_features()),
    ]
    if L.agent:
        parts.append(L.agent.name)
        parts.append(" ".join(L.agent.get_specialties()))
    return " ".join(parts).lower()


def search_listings(query: str, base_query=None):
    """Token-overlap scored search. Returns list of (Listing, score)."""
    q = (query or "").strip()
    if base_query is None:
        base_query = Listing.query
    if q and City.query.filter(func.lower(City.name) == q.lower()).first():
        return [(listing, 0) for listing in base_query.filter(or_(func.lower(Listing.city) == q.lower(), func.lower(Listing.market_city) == q.lower())).all()]
    listings = base_query.all()
    if not q:
        return [(L, 0) for L in listings]
    qtoks = _tokens(q)
    if not qtoks:
        return [(L, 0) for L in listings]
    qset = set(qtoks)
    scored = []
    for L in listings:
        corpus = _listing_corpus(L)
        ctoks = _tokens(corpus)
        cset = set(ctoks)
        overlap = qset & cset
        if not overlap:
            continue
        tf = sum(ctoks.count(t) for t in overlap)
        boost = 0
        ql = q.lower()
        if L.city and L.city.lower() in ql: boost += 5
        if L.state and L.state.lower() in ql: boost += 5
        if L.neighborhood and L.neighborhood.lower() in ql: boost += 4
        if L.zip and L.zip in q: boost += 5
        score = len(overlap) * 3 + tf + boost
        scored.append((L, score))
    scored.sort(key=lambda x: (-x[1], -(x[0].price or 0), x[0].id))
    return scored


def strict_city_argument():
    if len(request.args.getlist("city")) > 1:
        abort(400)
    city = (request.args.get("city") or "").strip()
    if len(city) > 80 or any(char in city for char in ("%", "_")):
        abort(400)
    return city


def filter_flag(args, key):
    value = (args.get(key) or "").strip().casefold()
    if value not in {"", "1", "true", "on"}:
        abort(400)
    return bool(value)


def filter_listings(qs, args):
    if hasattr(args, "getlist"):
        for key in SEARCH_FIELDS + ("type",):
            if len(args.getlist(key)) > 1:
                abort(400)
    city = (args.get("city") or "").strip()
    if len(city) > 80:
        abort(400)
    if city:
        qs = qs.filter(or_(func.lower(Listing.city) == city.lower(), func.lower(Listing.market_city) == city.lower()))
    status = (args.get("status") or "").strip()
    if status not in {"", "for-sale", "for-rent", "sold", "closed", "rented", "expired", "canceled", "cancelled", "withdrawn"}:
        abort(400)
    if status:
        qs = qs.filter(Listing.status == status)
    pt = (args.get("type") or args.get("property_type") or "").strip()
    if pt not in PROPERTY_TYPES | {"", "Rental", "Office", "Mixed Use", "Other"}:
        abort(400)
    if pt:
        qs = qs.filter(Listing.property_type == pt)
    pmin = args.get("price_min")
    pmax = args.get("price_max")
    for value, maximum in ((pmin, 10**12), (pmax, 10**12)):
        if value and (not value.isdigit() or int(value) > maximum):
            abort(400)
    if pmin:
        qs = qs.filter(Listing.price >= int(pmin))
    if pmax:
        qs = qs.filter(Listing.price <= int(pmax))
    beds = args.get("beds") or ""
    if beds and (not beds.isdigit() or int(beds) > 100):
        abort(400)
    if beds:
        qs = qs.filter(Listing.beds >= int(beds))
    baths = args.get("baths") or ""
    if baths and (not re.fullmatch(r"\d+(?:\.\d+)?", baths) or float(baths) > 100):
        abort(400)
    if baths:
        qs = qs.filter(func.coalesce(Listing.baths_total, func.coalesce(Listing.baths_full, 0) + 0.5 * func.coalesce(Listing.baths_half, 0)) >= float(baths))
    sqft_min = args.get("sqft_min") or ""
    if sqft_min and (not sqft_min.isdigit() or int(sqft_min) > 10**9):
        abort(400)
    if sqft_min:
        qs = qs.filter(Listing.sqft >= int(sqft_min))
    year_built = args.get("year_built_min") or ""
    if year_built and (not year_built.isdigit() or not 1600 <= int(year_built) <= 2100):
        abort(400)
    if year_built:
        qs = qs.filter(Listing.year_built >= int(year_built))
    if filter_flag(args, "pool"):
        qs = qs.filter(Listing.has_pool == True)
    if filter_flag(args, "garage"):
        qs = qs.filter(Listing.has_garage == True)
    if filter_flag(args, "waterfront"):
        qs = qs.filter(Listing.has_waterfront == True)
    if filter_flag(args, "doorman"):
        qs = qs.filter(Listing.has_doorman == True)
    if filter_flag(args, "open_house"):
        qs = qs.filter(Listing.is_open_house == True)
    if filter_flag(args, "new"):
        qs = qs.filter(Listing.is_new == True)
    if filter_flag(args, "compass_exclusive"):
        qs = qs.filter(Listing.is_compass_exclusive == True)
    return qs


def sort_listings(items, key: str):
    if key not in SEARCH_SORTS:
        abort(400)
    is_pair = items and isinstance(items[0], tuple)

    def L(x): return x[0] if is_pair else x

    def sale_ratio(x):
        listing = L(x)
        if not listing.price or not listing.sqft or listing.is_rental or listing.status == "for-rent":
            return None
        return listing.price / listing.sqft

    if key == "price_asc":
        items.sort(key=lambda x: (L(x).price is None, L(x).price or 0))
    elif key == "price_desc":
        items.sort(key=lambda x: -(L(x).price or 0))
    elif key == "newest":
        items.sort(key=lambda x: L(x).days_on_compass if L(x).days_on_compass is not None else 9999)
    elif key == "sqft_desc":
        items.sort(key=lambda x: -(L(x).sqft or 0))
    elif key == "beds_desc":
        items.sort(key=lambda x: -(L(x).beds or 0))
    elif key == "ppsf_asc":
        items.sort(key=lambda x: (sale_ratio(x) is None, sale_ratio(x) or 0, L(x).id))
    elif key == "ppsf_desc":
        items.sort(key=lambda x: (sale_ratio(x) is None, -(sale_ratio(x) or 0), L(x).id))
    return items


def city_state_slug(slug: str):
    m = re.match(r"^(.*)-([a-z]{2})$", slug.lower())
    if not m:
        return None, None
    city = m.group(1).replace("-", " ").title()
    state = m.group(2).upper()
    return city, state


# ─── Public browse ─────────────────────────────────────────────────────────────


@app.route("/")
def index():
    # Curated mixes — explicitly NOT sorted by price/recency so the homepage
    # doesn't trivially surface the top luxury / cheapest listing / freshest
    # listing of any market (those should require navigating into the
    # relevant section).
    featured = (Listing.query.filter_by(is_compass_exclusive=True)
                .order_by(Listing.id).limit(6).all())
    return render_template("index.html", featured=featured)


@app.route("/private-exclusives/")
def private_exclusives():
    normalized_status = func.lower(func.replace(
        func.json_extract(Listing.property_facts_json, "$.Status"), " ", ""))
    listings = Listing.query.filter(normalized_status.in_(
        ["active(private)", "contingent(private)", "pending(private)"])
    ).order_by(Listing.id).all()
    return render_template("listing_collection.html", title="Compass Private Exclusives",
                           intro="Homes with a private marketing status in our fixed listing snapshot.",
                           listings=listings)


@app.route("/coming-soon/")
@app.route("/coming-soon/listings/")
def coming_soon():
    listings = Listing.query.filter(
        func.json_extract(Listing.property_facts_json, "$.Status") == "Coming Soon"
    ).order_by(Listing.id).all()
    return render_template("listing_collection.html", title="Compass Coming Soon",
                           intro="Homes recorded as Coming Soon in our fixed listing snapshot.",
                           listings=listings)


@app.route("/sitemap/<state>/")
def market(state):
    state = state.upper()
    if not re.fullmatch(r"[A-Z]{2}", state):
        abort(404)
    listings = Listing.query.filter_by(state=state, status="for-sale").order_by(Listing.id).all()
    return render_template("listing_collection.html", title=f"{state} Real Estate",
                           intro="Browse homes for sale from our fixed listing snapshot.",
                           listings=listings)


@app.route("/neighborhood-guides/")
@app.route("/neighborhood-guides/<region>/")
def neighborhoods(region=None):
    if region is None:
        directory = [json.loads(guide.directory_json) for guide in
                     NeighborhoodGuide.query.order_by(NeighborhoodGuide.position).all()]
        return render_template("neighborhoods.html", directory=directory)
    guide = db.session.get(NeighborhoodGuide, region)
    if guide is None:
        abort(404)
    return render_template("neighborhood_region.html", guide=json.loads(guide.content_json))


@app.route("/concierge/")
def concierge():
    return render_template("concierge.html")


@app.route("/sell/", methods=["GET", "POST"])
def sell():
    values = {}
    errors = []
    if request.method == "POST":
        values = {field: request.form.get(field, "").strip()
                  for field in ("name", "email", "phone", "zip_code")}
        if not 1 <= len(values["name"]) <= 120:
            errors.append("Enter a name of up to 120 characters.")
        try:
            values["email"] = validate_email(values["email"], check_deliverability=False).normalized
            if len(values["email"]) > 254:
                raise EmailNotValidError("Address exceeds storage limit")
        except EmailNotValidError:
            errors.append("Enter a valid email address.")
        if not valid_phone(values["phone"], allow_empty=False):
            errors.append("Enter a valid phone number.")
        if not re.fullmatch(r"[0-9]{5}(?:-[0-9]{4})?", values["zip_code"]):
            errors.append("Enter a five-digit ZIP code or ZIP+4.")
        if not errors:
            inquiry = SellerInquiry(reference=secrets.token_hex(12), **values)
            db.session.add(inquiry)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                abort(500)
            session["seller_inquiry_reference"] = inquiry.reference
            return redirect(url_for("sell", _anchor="lead-form"))
    reference = session.pop("seller_inquiry_reference", None)
    confirmation = SellerInquiry.query.filter_by(reference=reference).first() if reference else None
    return render_template("sell.html", seller_values=values, seller_errors=errors,
                           seller_confirmation=confirmation), 422 if errors else 200


@app.route("/homes-for-sale")
def homes_for_sale_index():
    cities = City.query.order_by(City.name).all()
    return render_template("homes_for_sale.html", cities=cities,
                           status_label="For Sale", status="for-sale")


@app.route("/homes-for-rent")
def homes_for_rent_index():
    cities = City.query.order_by(City.name).all()
    return render_template("homes_for_sale.html", cities=cities,
                           status_label="For Rent", status="for-rent")


@app.route("/homes-for-sale/<city_state>/")
def city_for_sale(city_state):
    return _city_listing_page(city_state, status="for-sale")


@app.route("/homes-for-rent/<city_state>/")
def city_for_rent(city_state):
    return _city_listing_page(city_state, status="for-rent")


def _city_listing_page(city_state, status):
    city, state = city_state_slug(city_state)
    if not city:
        abort(404)
    qs = Listing.query.filter_by(state=state, status=status).filter(or_(Listing.city == city, Listing.market_city == city))
    refinements = {key: request.args.get(key, "") for key in request.args if key not in {"city", "status"}}
    qs = filter_listings(qs, refinements)
    listings = qs.all()
    sort = request.args.get("sort", "newest")
    if sort not in SEARCH_SORTS - {""}:
        abort(400)
    sort_listings(listings, sort)
    city_row = City.query.filter_by(slug=city_state).first()
    return render_template(
        "city.html",
        city_name=city, state=state,
        city_slug=city_state,
        city_row=city_row,
        status=status,
        status_label="For Sale" if status == "for-sale" else "For Rent",
        listings=listings,
        sort=sort,
        active_filters=refinements,
        page_title=f"{city} {state} {('Homes For Sale' if status=='for-sale' else 'Homes For Rent')}",
    )


@app.route("/listing/<slug>")
def listing_detail(slug):
    L = Listing.query.filter_by(slug=slug).first()
    if not L:
        abort(404)
    similar = (Listing.query
               .filter(Listing.id != L.id, Listing.city == L.city,
                       Listing.status == L.status)
               .order_by(func.abs(Listing.price - L.price)).limit(4).all())
    is_saved = False
    if current_user.is_authenticated:
        is_saved = (SavedHome.query
                    .filter_by(user_id=current_user.id, listing_id=L.id).first()
                    is not None)
    return render_template("listing_detail.html", listing=L, similar=similar,
                           is_saved=is_saved, collections=Collection.query.filter_by(user_id=current_user.id).order_by(Collection.name).all() if current_user.is_authenticated else [])


@app.route("/agents")
def agents_index():
    city = strict_city_argument()
    qs = Agent.query
    if city:
        qs = qs.filter(func.lower(Agent.city) == city.casefold())
    agents = qs.order_by(Agent.name).all()
    return render_template("agents.html", agents=agents, filter_city=city,
                           all_cities=sorted(set(a.city for a in Agent.query.all() if a.city)))


@app.route("/agents/<slug>")
def agent_detail(slug):
    a = Agent.query.filter_by(slug=slug).first()
    if not a:
        abort(404)
    listings = (Listing.query.filter_by(agent_id=a.id)
                .order_by(Listing.price.desc()).all())
    return render_template("agent_detail.html", agent=a, listings=listings)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if len(q) > 200:
        abort(400)
    base = Listing.query
    base = filter_listings(base, request.args)
    results = search_listings(q, base_query=base)
    sort = request.args.get("sort", "")
    if sort not in SEARCH_SORTS:
        abort(400)
    if sort:
        sort_listings(results, sort)
    elif not q:
        results.sort(key=lambda item: item[0].id)
    listings = [L for L, _ in results]
    return render_template("search.html", q=q, listings=listings,
                           result_count=len(listings),
                           active_filters=dict(request.args),
                           sort=sort)


@app.route("/open-houses")
def open_houses():
    city = strict_city_argument()
    qs = Listing.query.filter(Listing.is_open_house == True)
    if city:
        qs = qs.filter(func.lower(Listing.city) == city.casefold())
    listings = qs.order_by(Listing.open_house_date).all()
    all_cities = sorted(set(c[0] for c in db.session.query(Listing.city)
                            .filter(Listing.is_open_house == True).distinct()))
    return render_template("open_houses.html", listings=listings,
                           filter_city=city, all_cities=all_cities)


@app.route("/new-listings")
def new_listings():
    listings = (Listing.query.filter_by(is_new=True)
                .order_by(Listing.days_on_compass.asc()).all())
    return render_template("new_listings.html", listings=listings)


@app.route("/luxury")
def luxury():
    listings = (Listing.query.filter_by(is_luxury=True, status="for-sale")
                .order_by(Listing.price.desc()).all())
    return render_template("luxury.html", listings=listings)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/help")
def help_page():
    return render_template("help.html")


# ─── Auth ─────────────────────────────────────────────────────────────────────


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        u = User.query.filter_by(email=email).first()
        if not u or not u.check_password(pw):
            error = "Invalid email or password."
        else:
            remember = bool(request.form.get("remember"))
            session.clear()
            login_user(u, remember=remember)
            return redirect(local_return_url(request.args.get("next"), url_for("account")))
    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    error = None
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        pw2 = request.form.get("confirm") or ""
        if not name or not email or not pw:
            error = "Name, email and password are required."
        elif len(name) > 120 or not valid_email(email):
            error = "Enter a valid name and email address."
        elif not valid_password(pw):
            error = "Password must contain at least 6 characters and at most 72 UTF-8 bytes."
        elif pw != pw2:
            error = "Passwords do not match."
        elif User.query.filter_by(email=email).first():
            error = "An account with this email already exists."
        else:
            u = User(name=name, email=email)
            u.set_password(pw)
            db.session.add(u)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = "An account with this email already exists."
            else:
                session.clear()
                login_user(u)
                return redirect(url_for("account"))
    return render_template("register.html", error=error)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ─── Account ───────────────────────────────────────────────────────────────────


@app.route("/account")
@login_required
def account():
    saved = (SavedHome.query.filter_by(user_id=current_user.id)
             .order_by(SavedHome.saved_at.desc()).limit(4).all())
    tours = (Tour.query.filter_by(user_id=current_user.id)
             .order_by(Tour.requested_at.desc()).limit(3).all())
    inquiries = (Inquiry.query.filter_by(user_id=current_user.id)
                 .order_by(Inquiry.sent_at.desc()).limit(3).all())
    return render_template("account.html", user=current_user,
                           saved=saved, tours=tours, inquiries=inquiries)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        city = (request.form.get("city") or "").strip()
        state = (request.form.get("state") or "").strip().upper()
        if (not 1 <= len(name) <= 120 or not valid_phone(phone)
                or len(city) > 80 or (state and not re.fullmatch(r"[A-Z]{2}", state))):
            flash("Enter a valid name, phone, city, and two-letter state code.", "warning")
            return render_template("account_edit.html", user=current_user), 400
        current_user.name = name
        current_user.phone = phone
        current_user.city = city
        current_user.state = state
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html", user=current_user)


@app.route("/account/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    error = None
    if request.method == "POST":
        cur = request.form.get("current") or ""
        new = request.form.get("new") or ""
        new2 = request.form.get("confirm") or ""
        if not current_user.check_password(cur):
            error = "Current password is incorrect."
        elif new != new2:
            error = "New passwords do not match."
        elif not valid_password(new):
            error = "Password must contain at least 6 characters and at most 72 UTF-8 bytes."
        else:
            user = current_user._get_current_object()
            user.set_password(new)
            db.session.commit()
            session.clear()
            login_user(user)
            flash("Password updated.", "success")
            return redirect(url_for("account"))
    return render_template("change_password.html", error=error)


@app.route("/account/preferences", methods=["GET", "POST"])
@login_required
def preferences():
    if request.method == "POST":
        try:
            budget_min = int(request.form.get("budget_min") or 0)
            budget_max = int(request.form.get("budget_max") or 0)
            beds_min = int(request.form.get("beds_min") or 0)
            if min(budget_min, budget_max, beds_min) < 0 or max(budget_min, budget_max) > 10**12 or beds_min > 100:
                raise ValueError
            if budget_max and budget_max < budget_min:
                raise ValueError
        except ValueError:
            flash("Enter valid nonnegative budgets and bedrooms; maximum budget must be at least the minimum.", "warning")
            return render_template("preferences.html", user=current_user), 400
        types = request.form.getlist("property_types")
        timeline = request.form.get("move_timeline") or ""
        if not set(types) <= PROPERTY_TYPES or timeline not in {"", "0-3mo", "3-6mo", "6-12mo", "12mo+"}:
            flash("Choose one of the available property types and move timelines.", "warning")
            return render_template("preferences.html", user=current_user), 400
        current_user.budget_min = budget_min
        current_user.budget_max = budget_max
        current_user.beds_min = beds_min
        current_user.preferred_property_types = json.dumps(types)
        current_user.move_timeline = timeline
        current_user.has_agent = bool(request.form.get("has_agent"))
        current_user.receive_alerts = bool(request.form.get("receive_alerts"))
        db.session.commit()
        flash("Preferences updated.", "success")
        return redirect(url_for("preferences"))
    return render_template("preferences.html", user=current_user)


# ─── Saved homes / searches / collections / tours / inquiries ──────────────────


@app.route("/saved")
@login_required
def saved_list():
    rows = (SavedHome.query.filter_by(user_id=current_user.id)
            .order_by(SavedHome.saved_at.desc()).all())
    return render_template("saved.html", saved=rows)


@app.route("/save/<int:listing_id>", methods=["POST"])
@login_required
def save_home(listing_id):
    L = db.get_or_404(Listing, listing_id)
    existing = SavedHome.query.filter_by(user_id=current_user.id,
                                         listing_id=L.id).first()
    if not existing:
        db.session.add(SavedHome(user_id=current_user.id, listing_id=L.id))
        try:
            db.session.commit()
            flash(f"Saved {L.address}.", "success")
        except IntegrityError:
            db.session.rollback()
    return redirect(local_return_url(request.referrer, url_for("listing_detail", slug=L.slug)))


@app.route("/unsave/<int:listing_id>", methods=["POST"])
@login_required
def unsave_home(listing_id):
    row = SavedHome.query.filter_by(user_id=current_user.id,
                                    listing_id=listing_id).first()
    if row:
        db.session.delete(row)
        db.session.commit()
        flash("Removed from saved homes.", "info")
    return redirect(local_return_url(request.referrer, url_for("saved_list")))


@app.route("/saved-searches", methods=["GET", "POST"])
@login_required
def saved_searches():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        criteria = {key: request.form.get(key, "").strip() for key in SEARCH_FIELDS if request.form.get(key, "").strip()}
        if not 1 <= len(name) <= 120 or not valid_search_criteria(criteria):
            flash("Enter a valid saved-search name and filters.", "warning")
            rows = (SavedSearch.query.filter_by(user_id=current_user.id)
                    .order_by(SavedSearch.created_at.desc()).all())
            return render_template("saved_searches.html", searches=rows), 400
        ss = SavedSearch(user_id=current_user.id, name=name,
                         criteria_json=json.dumps(criteria))
        db.session.add(ss)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A saved search with this name already exists.", "warning")
            return redirect(url_for("saved_searches"))
        flash(f'Saved search "{name}".', "success")
        return redirect(url_for("saved_searches"))
    rows = (SavedSearch.query.filter_by(user_id=current_user.id)
            .order_by(SavedSearch.created_at.desc()).all())
    return render_template("saved_searches.html", searches=rows)


@app.route("/saved-searches/<int:ssid>/delete", methods=["POST"])
@login_required
def delete_saved_search(ssid):
    row = SavedSearch.query.filter_by(id=ssid, user_id=current_user.id).first_or_404()
    db.session.delete(row)
    db.session.commit()
    flash("Saved search deleted.", "info")
    return redirect(url_for("saved_searches"))


@app.route("/collections")
@login_required
def collections_index():
    rows = (Collection.query.filter_by(user_id=current_user.id)
            .order_by(Collection.created_at.desc()).all())
    return render_template("collections.html", collections=rows)


@app.route("/collections/new", methods=["GET", "POST"])
@login_required
def collection_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip()
        if not 1 <= len(name) <= 120 or len(description) > 2000:
            flash("Enter a collection name of up to 120 characters and a description of up to 2,000 characters.", "warning")
            return render_template("collection_new.html"), 400
        c = Collection(user_id=current_user.id, name=name,
                       description=description,
                       share_token=secrets.token_urlsafe(12))
        db.session.add(c)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A collection with this name already exists.", "warning")
            return redirect(url_for("collection_new"))
        return redirect(url_for("collection_detail", cid=c.id))
    return render_template("collection_new.html")


@app.route("/collections/<int:cid>")
@login_required
def collection_detail(cid):
    c = Collection.query.filter_by(id=cid, user_id=current_user.id).first_or_404()
    return render_template("collection_detail.html", collection=c,
                           listings=c.get_listings())


@app.route("/collections/<int:cid>/add/<int:listing_id>", methods=["POST"])
@login_required
def collection_add(cid, listing_id):
    c = Collection.query.filter_by(id=cid, user_id=current_user.id).first_or_404()
    L = db.get_or_404(Listing, listing_id)
    ids = c.get_listing_ids()
    if not isinstance(ids, list) or not all(isinstance(item, int) for item in ids):
        abort(500)
    if L.id not in ids:
        if len(ids) >= 200:
            abort(400)
        ids.append(L.id)
        c.set_listing_ids(ids)
        db.session.commit()
        flash(f'Added {L.address} to "{c.name}".', "success")
    return redirect(local_return_url(request.referrer, url_for("collection_detail", cid=c.id)))


@app.route("/listing/<int:listing_id>/add-to-collection", methods=["POST"])
@login_required
def listing_add_to_collection(listing_id):
    cid = request.form.get("collection_id", type=int)
    if cid is None:
        abort(400)
    return collection_add(cid, listing_id)


@app.route("/collections/<int:cid>/remove/<int:listing_id>", methods=["POST"])
@login_required
def collection_remove(cid, listing_id):
    c = Collection.query.filter_by(id=cid, user_id=current_user.id).first_or_404()
    ids = c.get_listing_ids()
    if listing_id in ids:
        ids.remove(listing_id)
        c.set_listing_ids(ids)
        db.session.commit()
    return redirect(url_for("collection_detail", cid=c.id))


@app.route("/collections/<int:cid>/delete", methods=["POST"])
@login_required
def collection_delete(cid):
    c = Collection.query.filter_by(id=cid, user_id=current_user.id).first_or_404()
    db.session.delete(c)
    db.session.commit()
    flash("Collection deleted.", "info")
    return redirect(url_for("collections_index"))


@app.route("/collections/share/<token>")
def collection_share(token):
    c = Collection.query.filter_by(share_token=token).first_or_404()
    return render_template("collection_share.html", collection=c,
                           listings=c.get_listings())


@app.route("/tours", methods=["GET"])
@login_required
def tours_list():
    rows = (Tour.query.filter_by(user_id=current_user.id)
            .order_by(Tour.requested_at.desc()).all())
    return render_template("tours.html", tours=rows)


@app.route("/tour/<int:listing_id>", methods=["GET", "POST"])
@login_required
def tour_request(listing_id):
    L = db.get_or_404(Listing, listing_id)
    if request.method == "POST":
        tour_date = (request.form.get("date") or "").strip()
        tour_time = (request.form.get("time") or "").strip()
        tour_type = (request.form.get("tour_type") or "in-person").strip()
        phone = (request.form.get("phone") or current_user.phone or "").strip()
        notes = (request.form.get("notes") or "").strip()
        try:
            parsed_date = date.fromisoformat(tour_date)
            if parsed_date.isoformat() != tour_date or not 2000 <= parsed_date.year <= 2100:
                raise ValueError
            if tour_time not in TOUR_TIMES or tour_type not in {"in-person", "video"}:
                raise ValueError
            if not valid_phone(phone) or len(notes) > 2000:
                raise ValueError
        except ValueError:
            flash("Choose a valid date, time, tour type, phone, and notes of up to 2,000 characters.", "warning")
            return render_template("tour_request.html", listing=L), 400
        t = Tour(
            user_id=current_user.id, listing_id=L.id,
            requested_date=tour_date,
            requested_time=tour_time,
            tour_type=tour_type,
            contact_phone=phone,
            notes=notes,
            status="requested",
        )
        db.session.add(t)
        db.session.commit()
        flash(f"Tour requested for {L.address} on {t.requested_date}.", "success")
        return redirect(url_for("tours_list"))
    return render_template("tour_request.html", listing=L)


@app.route("/tour/<int:tour_id>/cancel", methods=["POST"])
@login_required
def tour_cancel(tour_id):
    t = Tour.query.filter_by(id=tour_id, user_id=current_user.id).first_or_404()
    t.status = "cancelled"
    db.session.commit()
    flash("Tour cancelled.", "info")
    return redirect(url_for("tours_list"))


@app.route("/inquiries", methods=["GET"])
@login_required
def inquiries_list():
    rows = (Inquiry.query.filter_by(user_id=current_user.id)
            .order_by(Inquiry.sent_at.desc()).all())
    return render_template("inquiries.html", inquiries=rows)


@app.route("/inquiry/<int:listing_id>", methods=["GET", "POST"])
def inquiry_send(listing_id):
    L = db.get_or_404(Listing, listing_id)
    if request.method == "POST":
        uid = current_user.id if current_user.is_authenticated else None
        name = (request.form.get("name") or (current_user.name if uid else "")).strip()
        email = (request.form.get("email") or (current_user.email if uid else "")).strip().lower()
        phone = (request.form.get("phone") or "").strip()
        subject = (request.form.get("subject") or f"Inquiry about {L.address}").strip()
        message = (request.form.get("message") or "").strip()
        if (not name or len(name) > 120 or not valid_email(email)
                or not valid_phone(phone) or not 1 <= len(subject) <= 160
                or not message or len(message) > 10000):
            flash("Enter valid contact details, a subject of up to 160 characters, and a message of up to 10,000 characters.", "warning")
            return render_template("inquiry_send.html", listing=L), 400
        i = Inquiry(
            user_id=uid, listing_id=L.id, agent_id=L.agent_id,
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message,
        )
        db.session.add(i)
        db.session.commit()
        flash("Your message has been sent.",
              "success")
        if uid:
            return redirect(url_for("inquiries_list"))
        return redirect(url_for("listing_detail", slug=L.slug))
    return render_template("inquiry_send.html", listing=L)


# ─── Misc ──────────────────────────────────────────────────────────────────────


@app.route("/_health")
def health():
    return {"ok": True, "site": "compass",
            "listings": Listing.query.count(),
            "users": User.query.count()}


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# ─── Boot ──────────────────────────────────────────────────────────────────────


from seed_data import seed_all, seed_neighborhood_guides  # noqa: E402,F401

with app.app_context():
    db.create_all()
    if os.environ.get("COMPASS_SKIP_SEED") != "1":
        seed_all()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
