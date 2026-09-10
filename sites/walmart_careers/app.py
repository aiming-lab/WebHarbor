"""Walmart Careers local mirror for WebHarbor."""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlencode, urlsplit

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
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

import _content as content

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DB_PATH = INSTANCE_DIR / "walmart_careers.db"

INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config.update(
    SECRET_KEY=os.environ.get("WALMART_CAREERS_SECRET_KEY") or os.urandom(32),
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{DB_PATH}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    WTF_CSRF_TIME_LIMIT=7200,
    MAX_CONTENT_LENGTH=256 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("WALMART_CAREERS_SECURE_COOKIE") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, _record) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to continue."
login_manager.login_message_category = "info"

DEMO_PASSWORD = "TestPass123!"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PAGE_SIZE = 10
MAX_QUERY_LENGTH = 160
MAX_LOCATION_LENGTH = 80
MAX_PASSWORD_LENGTH = 256
SEED_VERSION = "walmart-careers-v2"

SHIFT_VALUES = [
    "Weekday Day",
    "Weekday Evening",
    "Weekday Overnight",
    "Weekend Day",
    "Weekend Evening",
    "Weekend Overnight",
    "Flex",
]
BRAND_VALUES = ["Vizio", "Walmart", "Sam's Club"]
EMPLOYMENT_TYPE_VALUES = ["Full time", "Part time", "Intern"]
RATE_VALUES = ["Salaried", "Hourly"]
RADIUS_VALUES = [5, 15, 25, 60]
SORT_VALUES = ["relevance", "most_recent"]

STOPWORDS = {
    "a", "an", "and", "at", "for", "in", "of", "on", "or", "the", "to", "with",
    "jobs", "job", "roles", "role", "near", "me", "all",
}


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class SeedMetadata(db.Model):
    __tablename__ = "seed_metadata"
    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(160), nullable=False)


class Area(db.Model):
    __tablename__ = "areas"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    blurb = db.Column(db.Text, nullable=False, default="")
    hero_image = db.Column(db.String(120), nullable=False, default="")
    has_index_page = db.Column(db.Boolean, nullable=False, default=True)
    is_filterable = db.Column(db.Boolean, nullable=False, default=True)

    categories = db.relationship(
        "Category", backref="area", lazy="select",
        order_by="Category.display_order",
    )

    @property
    def url(self) -> str:
        return url_for("career_area", slug=self.slug)

    @property
    def nav_url(self) -> str:
        """Where the "Career areas" menu points: the area page when there is one,
        otherwise straight to that area's open roles."""
        if self.has_index_page:
            return url_for("career_area", slug=self.slug)
        return url_for("results", area=self.slug)


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    area_id = db.Column(db.Integer, db.ForeignKey("areas.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint("area_id", "slug", name="uq_category_area_slug"),
    )


class Store(db.Model):
    __tablename__ = "stores"
    id = db.Column(db.Integer, primary_key=True)
    store_number = db.Column(db.String(16), unique=True, nullable=False)
    banner = db.Column(db.String(64), nullable=False)
    location_name = db.Column(db.String(120), nullable=False)
    street = db.Column(db.String(160), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    zip = db.Column(db.String(12), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    is_hub = db.Column(db.Boolean, nullable=False, default=False)
    is_office = db.Column(db.Boolean, nullable=False, default=False)
    hub_name = db.Column(db.String(80), nullable=True)
    hub_blurb = db.Column(db.Text, nullable=True)
    hub_image = db.Column(db.String(80), nullable=True)

    @property
    def banner_line(self) -> str:
        return f"{self.banner} #{self.store_number}"

    @property
    def city_state(self) -> str:
        return f"{self.city}, {self.state}"


class Job(db.Model):
    __tablename__ = "jobs"
    job_id = db.Column(db.String(32), primary_key=True)
    population = db.Column(db.String(16), nullable=False)  # salaried | hourly
    title = db.Column(db.String(160), nullable=False)
    brand = db.Column(db.String(24), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    area_id = db.Column(db.Integer, db.ForeignKey("areas.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    shifts_json = db.Column(db.Text, nullable=False, default="[]")
    employment_type = db.Column(db.String(16), nullable=False)
    pay_frequency = db.Column(db.String(8), nullable=False)  # Hourly | Annual
    min_pay = db.Column(db.Numeric(10, 2), nullable=False)
    max_pay = db.Column(db.Numeric(10, 2), nullable=False)
    posted_date = db.Column(db.Date, nullable=False)
    sort_rank = db.Column(db.Integer, nullable=False, default=0)
    is_trending = db.Column(db.Boolean, nullable=False, default=False)
    summary = db.Column(db.Text, nullable=False, default="")
    description = db.Column(db.Text, nullable=False, default="")
    about_team = db.Column(db.Text, nullable=True)  # salaried only
    additional_description_json = db.Column(db.Text, nullable=True)
    hashtag = db.Column(db.String(48), nullable=True)
    shift_time = db.Column(db.String(120), nullable=True)
    positions_available = db.Column(db.Integer, nullable=True)
    min_age_note = db.Column(db.Boolean, nullable=False, default=False)
    worker_type = db.Column(db.String(48), nullable=True)
    job_posting_id = db.Column(db.String(48), nullable=True)
    min_qualifications_json = db.Column(db.Text, nullable=True)
    preferred_qualifications = db.Column(db.Text, nullable=True)
    hero_images_json = db.Column(db.Text, nullable=False, default="[]")

    __table_args__ = (
        db.CheckConstraint("population IN ('salaried', 'hourly')", name="ck_jobs_population"),
        db.CheckConstraint("brand IN ('Vizio', 'Walmart', 'Sam''s Club')", name="ck_jobs_brand"),
        db.CheckConstraint("employment_type IN ('Full time', 'Part time', 'Intern')", name="ck_jobs_employment_type"),
        db.CheckConstraint("pay_frequency IN ('Hourly', 'Annual')", name="ck_jobs_pay_frequency"),
        db.CheckConstraint("min_pay >= 0 AND max_pay >= min_pay", name="ck_jobs_pay_range"),
        db.CheckConstraint("positions_available IS NULL OR positions_available > 0", name="ck_jobs_positions"),
    )

    store = db.relationship("Store", lazy="joined")
    area = db.relationship("Area", lazy="joined")
    category = db.relationship("Category", lazy="joined")

    # -- derived display helpers ------------------------------------------- #
    @property
    def shifts(self) -> list[str]:
        return json.loads(self.shifts_json or "[]")

    @property
    def shift_label(self) -> str:
        values = self.shifts
        if len(values) == 1:
            return values[0]
        return "Multiple shifts"

    @property
    def is_salaried(self) -> bool:
        return self.population == "salaried"

    @property
    def rate_label(self) -> str:
        return "Salaried" if self.is_salaried else "Hourly"

    @property
    def pay_suffix(self) -> str:
        return "/yr" if self.pay_frequency == "Annual" else "/hr"

    @property
    def pay_range(self) -> str:
        if self.pay_frequency == "Annual":
            return f"${int(self.min_pay):,} - ${int(self.max_pay):,}/yr"
        return f"${float(self.min_pay):,.2f} - ${float(self.max_pay):,.2f}/hr"

    @property
    def additional_description(self) -> list[str]:
        return json.loads(self.additional_description_json or "[]")

    @property
    def min_qualifications(self) -> list[str]:
        return json.loads(self.min_qualifications_json or "[]")

    @property
    def hero_images(self) -> list[str]:
        return json.loads(self.hero_images_json or "[]")

    @property
    def url(self) -> str:
        return url_for("job_detail", job_id=self.job_id)

    @property
    def search_blob(self) -> str:
        """Fields the scored search reads. Description is deliberately excluded."""
        return " ".join(
            [
                self.title,
                self.category.name if self.category else "",
                self.area.name if self.area else "",
                self.store.banner if self.store else "",
                self.store.city if self.store else "",
                self.store.state if self.store else "",
                self.brand,
                self.hashtag or "",
            ]
        )


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160, collation="NOCASE"), unique=True, nullable=False)
    username = db.Column(db.String(80, collation="NOCASE"), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False, default="")
    first_name = db.Column(db.String(80), nullable=False, default="")
    last_name = db.Column(db.String(80), nullable=False, default="")
    phone = db.Column(db.String(32), nullable=False, default="")
    city = db.Column(db.String(80), nullable=False, default="")
    state = db.Column(db.String(2), nullable=False, default="")
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)


class SavedJob(db.Model):
    __tablename__ = "saved_jobs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    job_id = db.Column(db.String(32), db.ForeignKey("jobs.job_id"), nullable=False)
    saved_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "job_id", name="uq_saved_user_job"),
    )

    job = db.relationship("Job", lazy="joined")


class ApplicationDraft(db.Model):
    __tablename__ = "application_drafts"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    job_id = db.Column(db.String(32), db.ForeignKey("jobs.job_id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    email = db.Column(db.String(160), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)


class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(32), db.ForeignKey("jobs.job_id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    email = db.Column(db.String(160), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="Submitted")
    confirmation_no = db.Column(db.String(32), unique=True, nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.CheckConstraint("status IN ('Submitted')", name="ck_applications_status"),
    )

    job = db.relationship("Job", lazy="joined")


@login_manager.user_loader
def load_user(user_id: str):
    if not str(user_id).isdigit():
        return None
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def dumps_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=False, separators=(",", ":"))


def confirmation_for(application_id: int) -> str:
    return f"WMC-{application_id:06d}"


def tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9']+", (text or "").lower()) if t and t not in STOPWORDS]


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def safe_next(raw: str | None) -> str | None:
    """Return a canonical same-origin path/query target or ``None``."""
    if not raw or len(raw) > 2048 or any(ord(char) < 32 for char in raw):
        return None
    decoded = raw
    for _ in range(3):
        expanded = unquote(decoded)
        if expanded == decoded:
            break
        decoded = expanded
    if decoded.startswith("//"):
        return None
    parsed = urlsplit(decoded)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return None
    if parsed.path.startswith("//") or "\\" in decoded:
        return None
    return parsed.path + (("?" + parsed.query) if parsed.query else "")


def bounded_text(value: str | None, field: str, maximum: int, *, required: bool = False) -> tuple[str, str | None]:
    text = (value or "").strip()
    if required and not text:
        return text, f"Enter your {field}."
    if len(text) > maximum:
        return text, f"{field.capitalize()} must be {maximum} characters or fewer."
    if any(ord(char) < 32 for char in text):
        return text, f"{field.capitalize()} contains unsupported control characters."
    return text, None


def single_query_arg(name: str, default: str = "") -> str:
    values = request.args.getlist(name)
    if len(values) > 1:
        abort(400, description=f"duplicate query parameter: {name}")
    return values[0] if values else default


def resolve_location(raw: str) -> dict | None:
    """Resolve free text typed into the location box.

    Returns ``None`` when nothing matches, otherwise a scope dict:

    * ``{"kind": "state", "state": "PR", "label": "Puerto Rico"}``
      when the text names a whole state or territory — the result set is then
      every role in that state, with no radius applied.
    * ``{"kind": "store", "store": <Store>, "label": "Rochester, NY"}`` when the
      text names a city, a "City, ST" pair or a ZIP — the radius then applies.
    """
    text = (raw or "").strip()
    if not text:
        return None
    stores = Store.query.order_by(Store.store_number).all()

    def state_scope(code: str) -> dict | None:
        if code not in content.STATE_NAMES:
            return None
        return {
            "kind": "state",
            "state": code,
            "label": content.STATE_NAMES[code],
        }

    # Whole-state searches: "PR", "Puerto Rico", "Ohio".
    upper = text.upper()
    if len(upper) == 2 and upper in content.STATE_NAMES:
        scope = state_scope(upper)
        if scope:
            return scope
    code = content.STATE_CODES_BY_NAME.get(text.lower())
    if code:
        scope = state_scope(code)
        if scope:
            return scope

    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 5:
        for store in stores:
            if store.zip.replace("-", "").startswith(digits[:5]):
                return {"kind": "store", "store": store, "label": store.city_state}
    parts = [p.strip() for p in text.split(",") if p.strip()]
    city = parts[0].lower() if parts else ""
    state = parts[1].upper()[:2] if len(parts) > 1 else ""
    if state:
        for store in stores:
            if store.city.lower() == city and store.state == state:
                return {"kind": "store", "store": store, "label": store.city_state}
    for store in stores:
        if store.city.lower() == city:
            return {"kind": "store", "store": store, "label": store.city_state}
    return None


def current_filters() -> dict:
    """Read and strictly validate the results-page query string."""
    q_value = single_query_arg("q")
    search_value = single_query_arg("searchQuery")
    if q_value and search_value:
        abort(400, description="use q or searchQuery, not both")
    query = (q_value or search_value).strip()
    location = single_query_arg("loc").strip()
    if len(query) > MAX_QUERY_LENGTH or len(location) > MAX_LOCATION_LENGTH:
        abort(400, description="query text is too long")
    if any(ord(char) < 32 for char in query + location):
        abort(400, description="query contains unsupported control characters")
    if query.casefold() == "all":
        query = ""
    if len(tokenize(query)) > 12:
        abort(400, description="search contains too many terms")

    page_text = single_query_arg("page", "1")
    radius_text = single_query_arg("radius", "25")
    sort = single_query_arg("sort", "relevance")
    tab = single_query_arg("tab", "jobs")
    if not page_text.isdigit() or not 1 <= int(page_text) <= 10000:
        abort(400, description="invalid page")
    if not radius_text.isdigit() or int(radius_text) not in RADIUS_VALUES:
        abort(400, description="invalid radius")
    if sort not in SORT_VALUES or tab not in {"jobs", "future", "content"}:
        abort(400, description="invalid sort or tab")

    area_values = {row.slug for row in Area.query.filter_by(is_filterable=True).all()}
    category_values = {row.slug for row in Category.query.all()}
    allowed = {
        "area": area_values,
        "category": category_values,
        "brand": set(BRAND_VALUES),
        "shift": set(SHIFT_VALUES),
        "type": set(EMPLOYMENT_TYPE_VALUES),
        "rate": set(RATE_VALUES),
    }
    facets: dict[str, list[str]] = {}
    for name, choices in allowed.items():
        values = [value for value in request.args.getlist(name) if value]
        if len(values) != len(set(values)) or any(value not in choices for value in values):
            abort(400, description=f"invalid {name} filter")
        facets[name] = values
    return {
        "q": query,
        **facets,
        "loc": location,
        "radius": int(radius_text),
        "sort": sort,
        "page": int(page_text),
        "tab": tab,
    }


def filters_query(filters: dict, **overrides) -> str:
    merged = dict(filters)
    merged.update(overrides)
    pairs: list[tuple[str, str]] = []
    if merged.get("q"):
        pairs.append(("q", merged["q"]))
    for key in ("area", "category", "brand", "shift", "type", "rate"):
        for value in merged.get(key) or []:
            pairs.append((key, value))
    if merged.get("loc"):
        pairs.append(("loc", merged["loc"]))
        pairs.append(("radius", str(merged.get("radius", 25))))
    if merged.get("sort") and merged["sort"] != "relevance":
        pairs.append(("sort", merged["sort"]))
    if merged.get("tab") and merged["tab"] != "jobs":
        pairs.append(("tab", merged["tab"]))
    if merged.get("page", 1) and int(merged.get("page", 1)) > 1:
        pairs.append(("page", str(merged["page"])))
    return urlencode(pairs)


def _stem_match(token: str, blob_tokens: set[str]) -> bool:
    """Loose prefix match for closely related words such as ``drivers`` and ``driver``.

    Two words match when they share a prefix of at least six characters and
    their lengths are within three of each other. A five-letter prefix was
    too loose: 'technician' matched 'Technology' and pulled half the catalog
    into a title search. The search is scored, never a strict AND, so this
    tier only widens a result set.
    """
    if len(token) < 6:
        return False
    for other in blob_tokens:
        if len(other) < 6 or abs(len(other) - len(token)) > 3:
            continue
        limit = min(len(token), len(other))
        shared = 0
        while shared < limit and token[shared] == other[shared]:
            shared += 1
        if shared >= 6:
            return True
    return False


def score_job(job: Job, tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    blob = job.search_blob.lower()
    blob_tokens = {t for t in re.split(r"[^a-z0-9']+", blob) if t}
    score = 0.0
    for token in tokens:
        if token in blob_tokens:
            score += 2.0
        elif len(token) >= 3 and any(other.startswith(token) for other in blob_tokens):
            # word-prefix tier: 'cashi' -> cashier, 'hand' -> handler. A raw
            # substring test let 'care' light up every Healthcare posting.
            score += 1.0
        elif _stem_match(token, blob_tokens):
            score += 0.5
    title_tokens = {t for t in re.split(r"[^a-z0-9']+", job.title.lower()) if t}
    for token in tokens:
        if token in title_tokens:
            score += 1.5
    return score


def search_jobs(filters: dict) -> tuple[list[Job], dict | None, bool]:
    """Return (ordered jobs, resolved location scope, location_failed)."""
    jobs = Job.query.order_by(Job.job_id).all()
    location = None
    location_failed = False
    if filters["loc"]:
        location = resolve_location(filters["loc"])
        location_failed = location is None
        if location_failed:
            jobs = []

    if filters["brand"]:
        jobs = [j for j in jobs if j.brand in filters["brand"]]
    if filters["type"]:
        jobs = [j for j in jobs if j.employment_type in filters["type"]]
    if filters["rate"]:
        wanted = {"Salaried": "salaried", "Hourly": "hourly"}
        allowed = {wanted[r] for r in filters["rate"]}
        jobs = [j for j in jobs if j.population in allowed]
    if filters["shift"]:
        wanted_shifts = set(filters["shift"])
        jobs = [j for j in jobs if wanted_shifts & set(j.shifts)]
    if filters["area"]:
        wanted_areas = {a.lower() for a in filters["area"]}
        jobs = [
            j for j in jobs
            if j.area and (j.area.slug.lower() in wanted_areas or j.area.name.lower() in wanted_areas)
        ]
    if filters["category"]:
        wanted_cats = {c.lower() for c in filters["category"]}
        jobs = [
            j for j in jobs
            if j.category and (j.category.slug.lower() in wanted_cats or j.category.name.lower() in wanted_cats)
        ]
    if location is not None:
        if location["kind"] == "state":
            jobs = [j for j in jobs if j.store.state == location["state"]]
        else:
            anchor = location["store"]
            radius = filters["radius"]
            jobs = [
                j for j in jobs
                if haversine_miles(anchor.lat, anchor.lng, j.store.lat, j.store.lng) <= radius
            ]

    tokens = tokenize(filters["q"])
    if tokens:
        scored = [(score_job(j, tokens), j) for j in jobs]
        scored = [(s, j) for s, j in scored if s > 0]
        if filters["sort"] == "most_recent":
            scored.sort(key=lambda pair: (-pair[1].posted_date.toordinal(), pair[1].sort_rank))
        else:
            scored.sort(key=lambda pair: (-pair[0], pair[1].sort_rank, pair[1].job_id))
        jobs = [j for _, j in scored]
    else:
        if filters["sort"] == "most_recent":
            jobs.sort(key=lambda j: (-j.posted_date.toordinal(), j.sort_rank))
        else:
            jobs.sort(key=lambda j: (j.sort_rank, j.job_id))
    return jobs, location, location_failed


def cluster_map_svg(jobs: list[Job], width: int = 520, height: int = 620) -> str:
    """Deterministic server-rendered cluster map (no third-party map tiles).

    Equirectangular with a cos(mean latitude) correction so the outline keeps a
    believable shape, then centred vertically in the panel.
    """
    lon_min, lon_max = -125.0, -65.0
    lat_min, lat_max = 17.0, 50.0
    pad = 12
    scale = (width - 2 * pad) / (lon_max - lon_min)
    lat_scale = scale / math.cos(math.radians((lat_min + lat_max) / 2))
    y_offset = (height - (lat_max - lat_min) * lat_scale) / 2

    def project(lat: float, lng: float) -> tuple[float, float]:
        x = pad + (lng - lon_min) * scale
        y = y_offset + (lat_max - lat) * lat_scale
        return round(x, 1), round(y, 1)

    def path_for(points: list[tuple[float, float]]) -> str:
        coords = [project(lat, lng) for lng, lat in points]
        head = f"M {coords[0][0]} {coords[0][1]}"
        rest = " ".join(f"L {x} {y}" for x, y in coords[1:])
        return f"{head} {rest} Z"

    counts: dict[int, int] = {}
    for job in jobs:
        counts[job.store_id] = counts.get(job.store_id, 0) + 1
    bubbles = []
    for store_id, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        store = db.session.get(Store, store_id)
        if store is None:
            continue
        x, y = project(store.lat, store.lng)
        radius = 12 + min(14, count * 2)
        bubbles.append((x, y, radius, count, f"{store.city}, {store.state}"))

    parts = [
        f'<svg class="cluster-map" viewBox="0 0 {width} {height}" width="100%" '
        f'role="img" aria-label="Map of open roles by location" '
        f'xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#9CD9EA"/>',
        f'<path d="{path_for(content.US_OUTLINE)}" fill="#D8EFD3" stroke="#B7CFB1" stroke-width="1.2"/>',
        f'<path d="{path_for(content.PR_OUTLINE)}" fill="#D8EFD3" stroke="#B7CFB1" stroke-width="1.2"/>',
    ]
    for x, y, radius, count, label in bubbles:
        parts.append(
            f'<g><title>{label}: {count} open roles</title>'
            f'<circle cx="{x}" cy="{y}" r="{radius}" fill="#0053E2" fill-opacity="0.85" '
            f'stroke="#FFFFFF" stroke-width="2"/>'
            f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-size="12" '
            f'fill="#FFFFFF" font-weight="600">{count}</text></g>'
        )
    parts.append(
        f'<text x="{width - pad}" y="{height - 6}" text-anchor="end" font-size="10" '
        f'fill="#74767C">Map data ©2026 Walmart Careers mirror</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def pin_card_svg(store: Store, width: int = 490, height: int = 230) -> str:
    """Small deterministic SVG map card used beside the address on the detail page.

    Stands in for the Google Maps thumbnail on the live page: same palette, a road
    grid seeded from the store's own coordinates, and a pin over the location.
    """
    seed = int(abs(store.lat * 1000) + abs(store.lng * 1000)) % 97
    vx = 40 + (seed % 7) * 22
    vy = 60 + (seed % 5) * 18
    parts = [
        f'<svg class="pin-card" viewBox="0 0 {width} {height}" width="100%" '
        f'role="img" aria-label="Map of {store.city}, {store.state}" '
        f'xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#D8EFD3"/>',
        # water
        f'<path d="M0 {vy} C {width * 0.25} {vy - 26}, {width * 0.45} {vy + 34}, '
        f'{width} {vy - 12} L {width} {vy + 22} C {width * 0.45} {vy + 62}, '
        f'{width * 0.25} {vy + 4}, 0 {vy + 28} Z" fill="#AEDBF2"/>',
        # roads
        f'<path d="M{vx} 0 L{vx - 18} {height}" stroke="#FFFFFF" stroke-width="9" fill="none"/>',
        f'<path d="M{vx + 150} 0 L{vx + 176} {height}" stroke="#FFFFFF" stroke-width="6" fill="none"/>',
        f'<path d="M0 {height * 0.72} L{width} {height * 0.62}" stroke="#FFFFFF" stroke-width="7" fill="none"/>',
        f'<path d="M0 {height * 0.28} L{width} {height * 0.34}" stroke="#F3D28C" stroke-width="5" fill="none"/>',
    ]
    px, py = width / 2, height / 2 - 18
    parts.append(
        f'<g transform="translate({px - 13} {py - 30})">'
        f'<path d="M13 0 C5.8 0 0 5.9 0 13.2 C0 23 13 40 13 40 S26 23 26 13.2 C26 5.9 20.2 0 13 0 Z" '
        f'fill="#0053E2"/>'
        f'<circle cx="13" cy="13" r="5" fill="#FFC220"/>'
        f'</g>'
    )
    parts.append(
        f'<text x="{px + 22}" y="{py - 4}" font-size="13" fill="#001E60" font-weight="700">'
        f'{store.city}</text>'
    )
    parts.append(
        f'<text x="{width - 8}" y="{height - 7}" text-anchor="end" font-size="9" fill="#4A5A6A">'
        f'Map data ©2026 Walmart Careers mirror</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def trending_jobs() -> list[Job]:
    return Job.query.filter_by(is_trending=True).order_by(Job.job_id).all()


def related_jobs(job: Job, limit: int = 3) -> list[Job]:
    rows = (
        Job.query.filter(
            Job.category_id == job.category_id,
            Job.job_id != job.job_id,
            Job.store_id != job.store_id,
        )
        .order_by(Job.sort_rank, Job.job_id)
        .limit(limit)
        .all()
    )
    if len(rows) < limit:
        extra = (
            Job.query.filter(
                Job.area_id == job.area_id,
                Job.job_id != job.job_id,
                Job.store_id != job.store_id,
                ~Job.job_id.in_([r.job_id for r in rows]),
            )
            .order_by(Job.sort_rank, Job.job_id)
            .limit(limit - len(rows))
            .all()
        )
        rows = rows + extra
    return rows


def saved_job_ids() -> set[str]:
    if not current_user.is_authenticated:
        return set()
    return {
        row.job_id
        for row in SavedJob.query.filter_by(user_id=current_user.id).all()
    }


def discard_application_draft() -> None:
    token = session.pop("apply_draft_token", None)
    if not token:
        return
    draft = ApplicationDraft.query.filter_by(token=token).first()
    if draft is not None:
        db.session.delete(draft)
        db.session.commit()


@app.context_processor
def inject_globals():
    return {
        # the six career areas listed in the header "Career areas" menu
        "nav_areas": (
            Area.query.filter_by(is_filterable=True)
            .order_by(Area.display_order)
            .all()
        ),
        "content": content,
        "current_year": content.MIRROR_REFERENCE_DATE.year,
        "search_q": (request.args.get("q") or request.args.get("searchQuery") or ""),
    }


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route("/home")
@app.route("/")
def index():
    areas = (
        Area.query.filter_by(has_index_page=True, is_filterable=True)
        .order_by(Area.display_order)
        .all()
    )
    return render_template(
        "index.html",
        trending=trending_jobs(),
        ribbon_areas=areas,
        saved_ids=saved_job_ids(),
    )


FACET_KEYS = ("area", "category", "brand", "shift", "type", "rate")


def active_filter_count(filters: dict) -> int:
    """How many facet selections are active — the number on the Filters button."""
    return sum(len(filters[key]) for key in FACET_KEYS)


def active_filter_chips(filters: dict) -> list[dict]:
    """One removable chip per active selection, so the current filter state stays
    readable without leaving the Filters popover hanging open over the results."""
    names = {a.slug: a.name for a in Area.query.all()}
    names.update({c.slug: c.name for c in Category.query.all()})
    chips: list[dict] = []
    for key in FACET_KEYS:
        for value in filters[key]:
            remaining = [v for v in filters[key] if v != value]
            chips.append(
                {
                    "label": names.get(value, value),
                    "remove": url_for("results")
                    + "?"
                    + filters_query(filters, page=1, **{key: remaining}),
                }
            )
    if filters["loc"]:
        chips.append(
            {
                "label": f"{filters['loc']} · within {filters['radius']} miles",
                "remove": url_for("results") + "?" + filters_query(filters, loc="", page=1),
            }
        )
    return chips


@app.route("/results")
def results():
    filters = current_filters()
    jobs, location, location_failed = search_jobs(filters)
    total = len(jobs)
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(filters["page"], pages)
    filters["page"] = page
    start = (page - 1) * PAGE_SIZE
    page_jobs = jobs[start:start + PAGE_SIZE]

    areas = Area.query.filter_by(is_filterable=True).order_by(Area.display_order).all()
    return render_template(
        "results.html",
        filters=filters,
        jobs=page_jobs,
        total=total,
        page=page,
        pages=pages,
        areas=areas,
        shift_values=SHIFT_VALUES,
        brand_values=BRAND_VALUES,
        employment_type_values=EMPLOYMENT_TYPE_VALUES,
        rate_values=RATE_VALUES,
        radius_values=RADIUS_VALUES,
        location=location,
        location_failed=location_failed,
        map_svg=cluster_map_svg(jobs),
        saved_ids=saved_job_ids(),
        qs=filters_query,
        filter_count=active_filter_count(filters),
        filter_chips=active_filter_chips(filters),
    )


@app.route("/jobs/<job_id>")
def job_detail(job_id: str):
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404)
    return render_template(
        "job_detail.html",
        job=job,
        related=related_jobs(job),
        is_saved=job.job_id in saved_job_ids(),
        map_svg=pin_card_svg(job.store),
        benefit_tiles=content.benefit_tiles_for(job.brand, job.population),
        saved_ids=saved_job_ids(),
    )


@app.route("/jobs/<job_id>/save", methods=["POST"])
def save_job(job_id: str):
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404)
    if not current_user.is_authenticated:
        return redirect(url_for("login", next=url_for("job_detail", job_id=job_id)))
    existing = SavedJob.query.filter_by(user_id=current_user.id, job_id=job_id).first()
    if existing is None:
        db.session.add(
            SavedJob(user_id=current_user.id, job_id=job_id, saved_at=datetime.now())
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        else:
            flash(f"Saved {job.title} to your saved roles.", "success")
    target = safe_next(request.form.get("next")) or url_for("job_detail", job_id=job_id)
    return redirect(target)


@app.route("/jobs/<job_id>/unsave", methods=["POST"])
def unsave_job(job_id: str):
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404)
    if not current_user.is_authenticated:
        return redirect(url_for("login", next=url_for("saved_roles")))
    existing = SavedJob.query.filter_by(user_id=current_user.id, job_id=job_id).first()
    if existing is not None:
        db.session.delete(existing)
        db.session.commit()
        flash(f"Removed {job.title} from your saved roles.", "success")
    target = safe_next(request.form.get("next")) or url_for("saved_roles")
    return redirect(target)


@app.route("/jobs/<job_id>/apply", methods=["GET", "POST"])
def apply_contact(job_id: str):
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404)
    errors: list[str] = []
    form = {
        "email": "",
        "first_name": "",
        "last_name": "",
        "phone": "",
    }
    if current_user.is_authenticated:
        form.update(
            {
                "email": current_user.email,
                "first_name": current_user.first_name,
                "last_name": current_user.last_name,
                "phone": current_user.phone,
            }
        )
    if request.method == "POST":
        limits = {"email": 160, "first_name": 80, "last_name": 80, "phone": 32}
        for key, maximum in limits.items():
            form[key], error = bounded_text(request.form.get(key), key.replace("_", " "), maximum, required=True)
            if error:
                errors.append(error)
        form["email"] = form["email"].lower()
        agreed = request.form.get("terms") == "on"
        if form["email"] and (not EMAIL_PATTERN.fullmatch(form["email"])
                              or len(form["email"].split("@", 1)[0]) > 64):
            errors.append("Enter a valid email address.")
        phone_digits = re.sub(r"[^0-9]", "", form["phone"])
        if form["phone"] and not 10 <= len(phone_digits) <= 15:
            errors.append("Enter a phone number with 10 to 15 digits.")
        if not agreed:
            errors.append("You must accept the Terms & Conditions to continue.")
        if not errors:
            discard_application_draft()
            draft = ApplicationDraft(
                token=secrets.token_urlsafe(32),
                job_id=job_id,
                user_id=current_user.id if current_user.is_authenticated else None,
                email=form["email"],
                first_name=form["first_name"],
                last_name=form["last_name"],
                phone=form["phone"],
                created_at=datetime.now(),
            )
            db.session.add(draft)
            db.session.commit()
            session["apply_draft_token"] = draft.token
            return redirect(url_for("apply_confirm", job_id=job_id))
    return render_template("apply_contact.html", job=job, form=form, errors=errors)


@app.route("/jobs/<job_id>/apply/confirm", methods=["GET", "POST"])
def apply_confirm(job_id: str):
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404)
    token = session.get("apply_draft_token")
    draft = ApplicationDraft.query.filter_by(token=token, job_id=job_id).first() if token else None
    expected_user_id = current_user.id if current_user.is_authenticated else None
    if draft is None or draft.user_id != expected_user_id:
        discard_application_draft()
        flash("Start your application by entering your contact details.", "warning")
        return redirect(url_for("apply_contact", job_id=job_id))
    if request.method == "POST":
        application = Application(
            job_id=job_id,
            user_id=current_user.id if current_user.is_authenticated else None,
            email=draft.email,
            first_name=draft.first_name,
            last_name=draft.last_name,
            phone=draft.phone,
            status="Submitted",
            confirmation_no="pending",
            submitted_at=datetime.now(),
        )
        db.session.add(application)
        db.session.delete(draft)
        try:
            db.session.flush()
            application.confirmation_no = confirmation_for(application.id)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, description="application could not be submitted")
        session.pop("apply_draft_token", None)
        session["apply_submitted_id"] = application.id
        return redirect(url_for("apply_submitted", job_id=job_id))
    return render_template("apply_confirm.html", job=job, draft=draft)


@app.route("/jobs/<job_id>/apply/submitted")
def apply_submitted(job_id: str):
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404)
    application_id = session.get("apply_submitted_id")
    application = db.session.get(Application, application_id) if application_id else None
    expected_user_id = current_user.id if current_user.is_authenticated else None
    if application is None or application.job_id != job_id or application.user_id != expected_user_id:
        flash("We couldn't find that application. Please apply again.", "warning")
        return redirect(url_for("apply_contact", job_id=job_id))
    return render_template("apply_submitted.html", job=job, application=application)


@app.route("/careers-areas/<slug>")
def career_area(slug: str):
    area = Area.query.filter(db.func.lower(Area.slug) == slug.lower()).first()
    if area is None:
        abort(404)
    if not area.has_index_page:
        # Students has no index page upstream either; send it to its open roles.
        return redirect(url_for("results", area=area.slug))
    categories = (
        Category.query.filter_by(area_id=area.id)
        .order_by(Category.display_order)
        .all()
    )
    return render_template(
        "area.html",
        area=area,
        categories=categories,
        hubs=Store.query.filter_by(is_hub=True).order_by(Store.id).all(),
    )


@app.route("/resources/location")
def resources_location():
    hubs = Store.query.filter_by(is_hub=True).order_by(Store.id).all()
    return render_template("locations.html", hubs=hubs)


@app.route("/resources/hiring-process")
def resources_hiring():
    return render_template("hiring_process.html", trending=trending_jobs(), saved_ids=saved_job_ids())


@app.route("/resources/terms-and-conditions")
def resources_terms():
    return render_template("terms.html")


@app.route("/about-us")
def about_us():
    return render_template(
        "about.html",
        areas=Area.query.filter_by(is_filterable=True).order_by(Area.display_order).all(),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = safe_next(request.args.get("next"))
    errors: list[str] = []
    email = ""
    if request.method == "POST":
        email, email_error = bounded_text(request.form.get("email"), "email", 160, required=True)
        email = email.lower()
        password = request.form.get("password") or ""
        next_url = safe_next(request.form.get("next")) or next_url
        if email_error or len(password) > MAX_PASSWORD_LENGTH:
            errors.append("We couldn't sign you in with that email and password.")
            user = None
        else:
            user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            if not errors:
                errors.append("We couldn't sign you in with that email and password.")
        else:
            discard_application_draft()
            session.pop("apply_submitted_id", None)
            login_user(user)
            flash(f"Signed in as {user.display_name}.", "success")
            return redirect(next_url or url_for("index"))
    return render_template("login.html", errors=errors, email=email, next_url=next_url)


@app.route("/register", methods=["GET", "POST"])
def register():
    next_url = safe_next(request.args.get("next"))
    errors: list[str] = []
    form = {"email": "", "first_name": "", "last_name": ""}
    if request.method == "POST":
        limits = {"email": 160, "first_name": 80, "last_name": 80}
        for key, maximum in limits.items():
            form[key], error = bounded_text(request.form.get(key), key.replace("_", " "), maximum, required=True)
            if error:
                errors.append(error)
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        next_url = safe_next(request.form.get("next")) or next_url
        email = form["email"].lower()
        if form["email"] and (not EMAIL_PATTERN.fullmatch(email)
                              or len(email.split("@", 1)[0]) > 64):
            errors.append("Enter a valid email address.")
        elif User.query.filter_by(email=email).first():
            errors.append("An account already exists for that email address.")
        if not 8 <= len(password) <= MAX_PASSWORD_LENGTH:
            errors.append(f"Choose a password with 8 to {MAX_PASSWORD_LENGTH} characters.")
        if password != confirm:
            errors.append("The two passwords don't match.")
        if not form["first_name"]:
            errors.append("Enter your first name.")
        if not form["last_name"]:
            errors.append("Enter your last name.")
        if not errors:
            display = f"{form['first_name']} {form['last_name']}".strip()
            base_username = email.split("@")[0]
            username = base_username
            suffix = 2
            while User.query.filter_by(username=username).first():
                username = f"{base_username}.{suffix}"
                suffix += 1
            user = User(
                email=email,
                username=username,
                display_name=display,
                first_name=form["first_name"],
                last_name=form["last_name"],
                phone="",
                city="",
                state="",
                password_hash=generate_password_hash(password),
                created_at=datetime.now(),
            )
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                errors.append("That account identifier is already in use.")
                return render_template("register.html", errors=errors, form=form, next_url=next_url), 409
            discard_application_draft()
            session.pop("apply_submitted_id", None)
            login_user(user)
            flash("Your candidate account is ready.", "success")
            return redirect(next_url or url_for("saved_roles"))
    return render_template("register.html", errors=errors, form=form, next_url=next_url)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    discard_application_draft()
    logout_user()
    session.pop("apply_submitted_id", None)
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    return render_template(
        "account.html",
        saved_count=SavedJob.query.filter_by(user_id=current_user.id).count(),
        application_count=Application.query.filter_by(user_id=current_user.id).count(),
    )


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    errors: list[str] = []
    form = {
        "display_name": current_user.display_name,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "phone": current_user.phone,
        "city": current_user.city,
        "state": current_user.state,
    }
    if request.method == "POST":
        limits = {"display_name": 120, "first_name": 80, "last_name": 80,
                  "phone": 32, "city": 80, "state": 2}
        for key, maximum in limits.items():
            form[key], error = bounded_text(request.form.get(key), key.replace("_", " "), maximum,
                                            required=key in {"display_name", "first_name", "last_name"})
            if error:
                errors.append(error)
        form["state"] = form["state"].upper()
        phone_digits = re.sub(r"[^0-9]", "", form["phone"])
        if form["phone"] and not 10 <= len(phone_digits) <= 15:
            errors.append("Enter a phone number with 10 to 15 digits.")
        if form["state"] and form["state"] not in content.STATE_NAMES:
            errors.append("Use a valid two-letter state or territory code.")
        if not errors:
            for key, value in form.items():
                setattr(current_user, key, value)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                errors.append("Your profile could not be updated.")
                return render_template("account_edit.html", form=form, errors=errors), 409
            flash("Your profile has been updated.", "success")
            return redirect(url_for("account"))
    return render_template("account_edit.html", form=form, errors=errors)


@app.route("/candidate-home/saved-roles")
def saved_roles():
    rows: list[SavedJob] = []
    if current_user.is_authenticated:
        rows = (
            SavedJob.query.filter_by(user_id=current_user.id)
            .order_by(SavedJob.saved_at.desc(), SavedJob.id.desc())
            .all()
        )
    return render_template(
        "saved_roles.html",
        rows=rows,
        trending=trending_jobs(),
        saved_ids=saved_job_ids(),
    )


@app.route("/candidate-home/applications")
@login_required
def applications():
    rows = (
        Application.query.filter_by(user_id=current_user.id)
        .order_by(Application.submitted_at.desc(), Application.id.desc())
        .all()
    )
    return render_template("applications.html", rows=rows)


@app.route("/_health")
def health():
    counts = {
        "jobs": Job.query.count(),
        "stores": Store.query.count(),
        "areas": Area.query.count(),
        "categories": Category.query.count(),
        "users": User.query.count(),
    }
    marker = db.session.get(SeedMetadata, "version")
    core_ready = {key: counts[key] for key in ("jobs", "stores", "areas", "categories")} == {
        "jobs": 246, "stores": 51, "areas": 7, "categories": 33
    }
    benchmark_users = {"alice.j@test.com", "bob.c@test.com", "carol.d@test.com", "david.k@test.com"}
    present_users = {row.email for row in User.query.filter(User.email.in_(benchmark_users)).all()}
    ready = core_ready and present_users == benchmark_users and marker is not None and marker.value == SEED_VERSION
    return jsonify({"ok": ready, "site": "walmart_careers", "seed_version": marker.value if marker else None, **counts}), (200 if ready else 503)


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_error):  # pragma: no cover - defensive
    db.session.rollback()
    return render_template("500.html"), 500


def bootstrap_site() -> None:
    from seed_data import ensure_seed_database

    with app.app_context():
        db.create_all()
        ensure_seed_database()


# `python app.py` loads this file as __main__; register it under its import
# name too so seed_data's `from app import ...` reuses this module instead of
# building a second Flask app + SQLAlchemy instance.
sys.modules.setdefault("app", sys.modules[__name__])

if os.environ.get("WEBSYN_SKIP_BOOTSTRAP") != "1":
    bootstrap_site()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
