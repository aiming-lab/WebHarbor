"""LandWatch mirror — Flask app.

A functional mirror of https://www.landwatch.com/ built for the WebHarbor
offline benchmark environment. All listing, agent, and location content is
seeded from the tracked source_data.json snapshot captured upstream (see
NOTICE.md); every seed function early-returns on a populated DB so
/reset/landwatch stays byte-identical.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime
from typing import Any

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                  request, url_for)
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)
RUNTIME_DB_PATH = os.path.join(INSTANCE_DIR, "landwatch.db")
DB_URI_OVERRIDE = os.environ.get("LW_DB_PATH", "")

PASSWORD_NAMESPACE = "landwatch-webharbor-demo"

# The upstream snapshot date. Every displayed date and the "recently viewed"
# ordering derive from it so pages are deterministic run to run.
MIRROR_DATE = datetime(2026, 9, 22)

app = Flask(__name__, instance_path=INSTANCE_DIR)
app.config["SECRET_KEY"] = "landwatch-demo-session-key"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    DB_URI_OVERRIDE if DB_URI_OVERRIDE.startswith("sqlite:///")
    else f"sqlite:///{RUNTIME_DB_PATH}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


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


def money(value) -> str:
    if value is None:
        return "Contact Agent"
    return f"${value:,.0f}"


def short_money(value) -> str:
    if value is None:
        return ""
    if value >= 1_000_000:
        v = value / 1_000_000
        return f"${v:.1f}M" if v < 10 else f"${v:.0f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"


def acres_label(value) -> str:
    if value is None:
        return ""
    text = f"{value:,.10f}".rstrip("0").rstrip(".")
    return f"{text} Acres"


def now_iso() -> str:
    """Deterministic 'now' for runtime writes (account-anchored ordering)."""
    return datetime.now().replace(microsecond=0).isoformat()


STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
              "or", "is", "it", "by", "with", "near"}


def token_scores(query: str, texts: list[str]) -> list[int]:
    tokens = [t.lower() for t in re.split(r"[^a-zA-Z0-9]+", query.lower())
              if t.lower() not in STOP_WORDS and len(t) > 1]
    return [sum(1 for t in tokens if re.search(rf"\b{re.escape(t)}\b", text.lower()))
            for text in texts]


def agent_portrait(broker_id):
    """Portrait path for a listing's broker (used by the card template)."""
    if not broker_id:
        return ""
    agent = Agent.query.get(broker_id)
    return agent.portrait_path() if agent else ""


app.jinja_env.globals["agent_portrait"] = agent_portrait
app.jinja_env.filters["money"] = money
app.jinja_env.filters["acres"] = acres_label
app.jinja_env.filters["short_money"] = short_money


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

class Listing(db.Model):
    __tablename__ = "listings"
    pid = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    canonical_slug = db.Column(db.String(300))
    price = db.Column(db.Integer)
    short_price = db.Column(db.String(30))
    price_per_acre = db.Column(db.Float)
    price_change_amount = db.Column(db.Integer)
    price_change_date = db.Column(db.String(30))
    acres = db.Column(db.Float)
    beds = db.Column(db.Integer)
    baths = db.Column(db.Float)
    half_baths = db.Column(db.Integer)
    sqft = db.Column(db.Integer)
    sqft_display = db.Column(db.String(40))
    street = db.Column(db.String(160))
    city = db.Column(db.String(90))
    city_slug = db.Column(db.String(100))
    county = db.Column(db.String(90))
    county_slug = db.Column(db.String(100))
    county_id = db.Column(db.Integer)
    state = db.Column(db.String(40))
    state_slug = db.Column(db.String(60))
    state_code = db.Column(db.String(2))
    zip = db.Column(db.String(10))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20))
    is_auction = db.Column(db.Boolean, default=False)
    auction_start = db.Column(db.String(30))
    property_types = db.Column(db.String(300))
    property_types_label = db.Column(db.String(300))
    category_slugs = db.Column(db.String(300))
    description_short = db.Column(db.Text)
    description_full = db.Column(db.Text)
    highlights = db.Column(db.Text)
    activities = db.Column(db.Text)
    proposed_use = db.Column(db.Text)
    image_ids = db.Column(db.Text)
    image_count = db.Column(db.Integer)
    has_video = db.Column(db.Boolean, default=False)
    has_house = db.Column(db.Boolean, default=False)
    has_custom_map = db.Column(db.Boolean, default=False)
    video_url = db.Column(db.String(200))
    listing_level_title = db.Column(db.String(60))
    is_diamond = db.Column(db.Boolean, default=False)
    owner_financing = db.Column(db.Boolean, default=False)
    broker_id = db.Column(db.Integer)
    broker_name = db.Column(db.String(120))
    broker_company = db.Column(db.String(160))
    broker_phone = db.Column(db.String(30))
    insert_date = db.Column(db.String(30))
    last_updated = db.Column(db.String(30))
    property_website = db.Column(db.String(200))
    sort_rank = db.Column(db.Integer, default=0)

    def types_list(self) -> list[str]:
        return [t for t in (self.property_types or "").split(",") if t]

    def categories_list(self) -> list[str]:
        return [c for c in (self.category_slugs or "").split(",") if c]

    def highlights_list(self) -> list[str]:
        return load_json(self.highlights, [])

    def activities_list(self) -> list[str]:
        return load_json(self.activities, [])

    def proposed_use_list(self) -> list[str]:
        return load_json(self.proposed_use, [])

    def image_ids_list(self) -> list[int]:
        return load_json(self.image_ids, [])

    def photo_path(self, image_id: int) -> str:
        return f"/static/images/listings/{self.pid}/{image_id}.webp"

    def card_photo(self) -> str:
        ids = self.image_ids_list()
        return self.photo_path(ids[0]) if ids else ""

    @property
    def price_display(self) -> str:
        return money(self.price)

    @property
    def acres_display(self) -> str:
        return acres_label(self.acres)

    @property
    def location_line(self) -> str:
        return f"{self.city}, {self.state_code}, {self.zip}, {self.county}"

    def full_address_line(self) -> str:
        return f"{self.street}, {self.city}, {self.state_code}, {self.zip}, {self.county}"

    def detail_path(self) -> str:
        return f"/{self.canonical_slug}/pid/{self.pid}"


class Agent(db.Model):
    __tablename__ = "agents"
    account_id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160))
    name = db.Column(db.String(140))
    company = db.Column(db.String(180))
    phone = db.Column(db.String(30))
    city = db.Column(db.String(90))
    state_code = db.Column(db.String(2))
    about = db.Column(db.Text)
    portrait_id = db.Column(db.Integer)
    total_listings = db.Column(db.Integer)
    price_min = db.Column(db.Integer)
    price_max = db.Column(db.Integer)
    acre_min = db.Column(db.Float)
    acre_max = db.Column(db.Float)
    website = db.Column(db.String(200))
    is_sponsored = db.Column(db.Boolean, default=False)

    def profile_path(self) -> str:
        return f"/profile/{self.slug}/{self.account_id}"

    def portrait_path(self) -> str:
        if self.portait_id if False else self.portrait_id:
            return f"/static/images/agents/{self.portrait_id}.webp"
        return ""

    @property
    def price_range_display(self) -> str:
        if self.price_min is None or self.price_max is None:
            return ""
        return f"{short_money(self.price_min)} - {short_money(self.price_max)}"

    @property
    def acre_range_display(self) -> str:
        if self.acre_min is None or self.acre_max is None:
            return ""

        def fmt(v):
            return f"{v:,.2f}".rstrip("0").rstrip(".") if v < 100 else f"{v:,.0f}"
        return f"{fmt(self.acre_min)} - {fmt(self.acre_max)} ac"


class Region(db.Model):
    __tablename__ = "regions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(90))
    slug = db.Column(db.String(100))
    counties = db.Column(db.Text)                      # JSON list of county names
    state_slug = db.Column(db.String(60))


class County(db.Model):
    __tablename__ = "counties"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(90))
    slug = db.Column(db.String(100))
    state = db.Column(db.String(40))
    state_code = db.Column(db.String(2))
    state_slug = db.Column(db.String(60))


class City(db.Model):
    __tablename__ = "cities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(90))
    slug = db.Column(db.String(100))
    state = db.Column(db.String(40))
    state_code = db.Column(db.String(2))
    state_slug = db.Column(db.String(60))


class PropertyType(db.Model):
    __tablename__ = "property_types"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(60))
    slug = db.Column(db.String(60))
    type_slug = db.Column(db.String(60))               # per-listing type slug (homesites, homes, ...)
    listing_count = db.Column(db.Integer, default=0)


class HomeFeatured(db.Model):
    __tablename__ = "home_featured"
    id = db.Column(db.Integer, primary_key=True)
    pid = db.Column(db.Integer)
    position = db.Column(db.Integer)


class CategoryTile(db.Model):
    __tablename__ = "category_tiles"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(60))
    slug = db.Column(db.String(60))                          # category slug
    image = db.Column(db.String(120))
    position = db.Column(db.Integer)


class StaticPage(db.Model):
    __tablename__ = "static_pages"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True)
    title = db.Column(db.String(200))
    body = db.Column(db.Text)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    created_at = db.Column(db.String(30))
    is_benchmark = db.Column(db.Boolean, default=False)

    def check_password(self, raw: str) -> bool:
        return hmac.compare_digest(self.password_hash, stable_password_hash(raw))

    @property
    def short_name(self) -> str:
        return (self.name or self.email).split(" ")[0]


class Favorite(db.Model):
    __tablename__ = "favorites"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    pid = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.String(30))


class SavedSearch(db.Model):
    __tablename__ = "saved_searches"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(200))
    url = db.Column(db.String(300))
    alerts = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.String(30))


class Inquiry(db.Model):
    __tablename__ = "inquiries"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    pid = db.Column(db.Integer)
    name = db.Column(db.String(120))
    email = db.Column(db.String(160))
    phone = db.Column(db.String(30))
    message = db.Column(db.Text)
    created_at = db.Column(db.String(30))


class Session(db.Model):
    __tablename__ = "sessions"
    token = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.String(30))


# ---------------------------------------------------------------------------
# session plumbing
# ---------------------------------------------------------------------------

def create_session(user_id: int) -> str:
    user = User.query.get(user_id)
    token = hashlib.sha256(
        f"{PASSWORD_NAMESPACE}:session:{user_id}:{user.email}".encode("utf-8")).hexdigest()
    if Session.query.get(token) is None:
        db.session.add(Session(token=token, user_id=user_id, created_at=now_iso()))
        db.session.commit()
    return token


def destroy_session(token: str) -> None:
    row = Session.query.get(token)
    if row is not None:
        db.session.delete(row)
        db.session.commit()


def current_user():
    token = request.cookies.get("lw_session")
    if not token:
        return None
    row = Session.query.get(token)
    if row is None:
        return None
    return User.query.get(row.user_id)


@app.context_processor
def inject_globals():
    user = current_user()
    states = (Listing.query.with_entities(Listing.state, Listing.state_slug)
              .distinct().order_by(Listing.state).all())
    top_states = (Listing.query.with_entities(Listing.state, Listing.state_slug)
                  .distinct().order_by(Listing.state)
                  .limit(10).all())
    return {
        "current_user": user,
        "MIRROR_DATE": MIRROR_DATE,
        "states_menu": states,
        "footer_states": top_states,
    }


# ---------------------------------------------------------------------------
# filter taxonomy (upstream URL shapes)
# ---------------------------------------------------------------------------

PRICE_BUCKETS = [
    ("price-under-49999", "$0 - $49,999", 0, 49999),
    ("price-50000-99999", "$50,000 - $99,999", 50000, 99999),
    ("price-100000-249999", "$100,000 - $249,999", 100000, 249999),
    ("price-250000-499999", "$250,000 - $499,999", 250000, 499999),
    ("price-500000-749999", "$500,000 - $749,999", 500000, 749999),
    ("price-750000-999999", "$750,000 - $999,999", 750000, 999999),
    ("price-over-1000000", "$1,000,000 and up", 1000000, None),
]

ACRES_BUCKETS = [
    ("acres-under-10", "0 - 10 Acres", None, 10.0),
    ("acres-11-50", "11 - 50 Acres", 10.0, 50.0),
    ("acres-51-100", "51 - 100 Acres", 50.0, 100.0),
    ("acres-101-200", "101 - 200 Acres", 100.0, 200.0),
    ("acres-201-500", "201 - 500 Acres", 200.0, 500.0),
    ("acres-501-1000", "501 - 1,000 Acres", 500.0, 1000.0),
    ("acres-over-1000", "Over 1,000 Acres", 1000.0, None),
]

BEDS_OPTIONS = [("beds-over-1", "1+ Bedrooms", 1), ("beds-over-2", "2+ Bedrooms", 2),
                ("beds-over-3", "3+ Bedrooms", 3), ("beds-over-4", "4+ Bedrooms", 4)]
BATHS_OPTIONS = [("baths-over-1", "1+ Bathrooms", 1), ("baths-over-2", "2+ Bathrooms", 2),
                 ("baths-over-3", "3+ Bathrooms", 3), ("baths-over-4", "4+ Bathrooms", 4)]

SORTS: dict[str, tuple[str, str | None]] = {
    "default": ("Default", None),
    "acres-low": ("Acres: Small to Large", "acres_asc"),
    "acres-high": ("Acres: Large to Small", "acres_desc"),
    "newest": ("Newest", "newest"),
    "price-low": ("Price: Low to High", "price_asc"),
    "price-high": ("Price: High to Low", "price_desc"),
}

ACTIVE_STATUSES = ("Available", "Under Contract")

CATEGORY_SLUGS = ("land", "hunting-property", "farms-ranches", "homes",
                  "timberland-property", "commercial-property", "homesites",
                  "recreational-property", "horse-property",
                  "undeveloped-land", "waterfront-property")

# Category display names used in page h1s (upstream forms, verified live:
# /hunting-property -> "Hunting Land for Sale", /waterfront-property ->
# "Waterfront Properties for Sale", /land -> "Land for Sale", ...).
CATEGORY_H1_NAMES = {
    "land": "Land",
    "hunting-property": "Hunting Land",
    "farms-ranches": "Farms and Ranches",
    "homes": "Houses",
    "homesites": "Homesites",
    "timberland-property": "Timberland Properties",
    "commercial-property": "Commercial Properties",
    "recreational-property": "Recreational Land",
    "horse-property": "Horse Properties",
    "undeveloped-land": "Undeveloped Land",
    "waterfront-property": "Waterfront Properties",
}

# USPS state codes keyed by the state page slug ("texas-land-for-sale" -> "TX").
STATE_CODES = {
    "alabama-land-for-sale": "AL", "alaska-land-for-sale": "AK",
    "arizona-land-for-sale": "AZ", "arkansas-land-for-sale": "AR",
    "california-land-for-sale": "CA", "colorado-land-for-sale": "CO",
    "connecticut-land-for-sale": "CT", "delaware-land-for-sale": "DE",
    "florida-land-for-sale": "FL", "georgia-land-for-sale": "GA",
    "hawaii-land-for-sale": "HI", "idaho-land-for-sale": "ID",
    "illinois-land-for-sale": "IL", "indiana-land-for-sale": "IN",
    "iowa-land-for-sale": "IA", "kansas-land-for-sale": "KS",
    "kentucky-land-for-sale": "KY", "louisiana-land-for-sale": "LA",
    "maine-land-for-sale": "ME", "maryland-land-for-sale": "MD",
    "massachusetts-land-for-sale": "MA", "michigan-land-for-sale": "MI",
    "minnesota-land-for-sale": "MN", "mississippi-land-for-sale": "MS",
    "missouri-land-for-sale": "MO", "montana-land-for-sale": "MT",
    "nebraska-land-for-sale": "NE", "nevada-land-for-sale": "NV",
    "new-hampshire-land-for-sale": "NH", "new-jersey-land-for-sale": "NJ",
    "new-mexico-land-for-sale": "NM", "new-york-land-for-sale": "NY",
    "north-carolina-land-for-sale": "NC", "north-dakota-land-for-sale": "ND",
    "ohio-land-for-sale": "OH", "oklahoma-land-for-sale": "OK",
    "oregon-land-for-sale": "OR", "pennsylvania-land-for-sale": "PA",
    "rhode-island-land-for-sale": "RI", "south-carolina-land-for-sale": "SC",
    "south-dakota-land-for-sale": "SD", "tennessee-land-for-sale": "TN",
    "texas-land-for-sale": "TX", "utah-land-for-sale": "UT",
    "vermont-land-for-sale": "VT", "virginia-land-for-sale": "VA",
    "washington-land-for-sale": "WA", "west-virginia-land-for-sale": "WV",
    "wisconsin-land-for-sale": "WI", "wyoming-land-for-sale": "WY",
    "district-of-columbia-land-for-sale": "DC",
}

STATE_SLUGS = {
    "alabama": "Alabama", "alaska": "Alaska", "arizona": "Arizona",
    "arkansas": "Arkansas", "california": "California", "colorado": "Colorado",
    "connecticut": "Connecticut", "delaware": "Delaware", "florida": "Florida",
    "georgia": "Georgia", "hawaii": "Hawaii", "idaho": "Idaho",
    "illinois": "Illinois", "indiana": "Indiana", "iowa": "Iowa",
    "kansas": "Kansas", "kentucky": "Kentucky", "louisiana": "Louisiana",
    "maine": "Maine", "maryland": "Maryland", "massachusetts": "Massachusetts",
    "michigan": "Michigan", "minnesota": "Minnesota", "mississippi": "Mississippi",
    "missouri": "Missouri", "montana": "Montana", "nebraska": "Nebraska",
    "nevada": "Nevada", "new-hampshire": "New Hampshire", "new-jersey": "New Jersey",
    "new-mexico": "New Mexico", "new-york": "New York",
    "north-carolina": "North Carolina", "north-dakota": "North Dakota",
    "ohio": "Ohio", "oklahoma": "Oklahoma", "oregon": "Oregon",
    "pennsylvania": "Pennsylvania", "rhode-island": "Rhode Island",
    "south-carolina": "South Carolina", "south-dakota": "South Dakota",
    "tennessee": "Tennessee", "texas": "Texas", "utah": "Utah",
    "vermont": "Vermont", "virginia": "Virginia", "washington": "Washington",
    "west-virginia": "West Virginia", "wisconsin": "Wisconsin",
    "wyoming": "Wyoming", "district-of-columbia": "District of Columbia",
}


class SearchContext:
    """Filters resolved for one listing-results page."""

    def __init__(self):
        self.state_slug = None
        self.state_name = None
        self.category_slug = None
        self.category_label = None
        self.county = None
        self.city = None
        self.region = None
        self.price_bucket = None          # (slug, label, lo, hi)
        self.acres_bucket = None
        self.beds_min = None
        self.baths_min = None
        self.residence = None             # True/False for with-/no-residence
        self.activity = None
        self.sale_type = None              # "auctions"
        self.owner_financing = False
        self.has_video = False
        self.sort = "default"
        self.page = 1

    # -- filter resolution -------------------------------------------------
    def apply_segment(self, segment: str) -> bool:
        if self.state_slug is None and self.category_slug is None:
            return False
        if segment == "auctions":
            self.sale_type = "auctions"
            return True
        county = County.query.filter_by(slug=segment,
                                         state_slug=self.state_slug).first()
        if county is not None:
            self.county = county
            return True
        if segment.endswith("-region"):
            region = Region.query.filter_by(slug=segment,
                                             state_slug=self.state_slug).first()
            self.region = region
            return region is not None
        for slug, label, lo, hi in PRICE_BUCKETS:
            if segment == slug:
                self.price_bucket = (slug, label, lo, hi)
                return True
        for slug, label, lo, hi in ACRES_BUCKETS:
            if segment == slug:
                self.acres_bucket = (slug, label, lo, hi)
                return True
        for slug, label, n in BEDS_OPTIONS:
            if segment == slug:
                self.beds_min = n
                return True
        for slug, label, n in BATHS_OPTIONS:
            if segment == slug:
                self.baths_min = n
                return True
        if segment == "with-residence":
            self.residence = True
            return True
        if segment == "no-residence":
            self.residence = False
            return True
        if segment == "owner-financing":
            self.owner_financing = True
            return True
        city = City.query.filter_by(slug=segment, state_slug=self.state_slug).first()
        if city is not None:
            self.city = city
            return True
        ptype = PropertyType.query.filter_by(type_slug=segment).first()
        if ptype is not None:
            self.category_slug = ptype.slug
            self.category_label = ptype.label
            return True
        return False

    def apply_query(self, args) -> None:
        def num(name):
            raw = (args.get(name) or "").replace(",", "").replace("$", "").strip()
            if not raw:
                return None
            try:
                value = float(raw)
            except ValueError:
                return None
            return int(value) if name.startswith("price") else value

        price_min, price_max = num("priceMin"), num("priceMax")
        if price_min is not None or price_max is not None:
            self.price_bucket = ("custom", "Custom Price", price_min, price_max)
        acres_min, acres_max = num("acresMin"), num("acresMax")
        if acres_min is not None or acres_max is not None:
            self.acres_bucket = ("custom", "Custom Size (Acres)", acres_min, acres_max)
        if args.get("ownerFinancing") is not None:
            self.owner_financing = args.get("ownerFinancing") in ("1", "on", "true")
        if args.get("hasVideo") is not None:
            self.has_video = args.get("hasVideo") in ("1", "on", "true")
        if args.get("sort") in SORTS:
            self.sort = args["sort"]

    # -- query building ----------------------------------------------------
    def filtered(self):
        query = Listing.query.filter(Listing.status.in_(ACTIVE_STATUSES))
        if self.state_slug:
            query = query.filter(Listing.state_slug == self.state_slug)
        if self.category_slug:
            query = query.filter(Listing.category_slugs.like(f"%{self.category_slug}%"))
        if self.county is not None:
            query = query.filter(Listing.county_slug == self.county.slug)
        if self.city is not None:
            query = query.filter(Listing.city_slug == self.city.slug)
        if self.region is not None:
            counties = load_json(self.region.counties, [])
            query = query.filter(Listing.county.in_(counties),
                                  Listing.state_slug == self.region.state_slug)
        if self.price_bucket:
            _, _, lo, hi = self.price_bucket
            if lo is not None:
                query = query.filter(Listing.price >= lo)
            if hi is not None:
                query = query.filter(Listing.price <= hi)
        if self.acres_bucket:
            _, _, lo, hi = self.acres_bucket
            if lo is not None:
                query = query.filter(Listing.acres >= lo)
            if hi is not None:
                query = query.filter(Listing.acres <= hi)
        if self.beds_min:
            query = query.filter(Listing.beds >= self.beds_min)
        if self.baths_min:
            query = query.filter(Listing.baths >= self.baths_min)
        if self.residence is True:
            query = query.filter(Listing.has_house.is_(True))
        if self.residence is False:
            query = query.filter(Listing.has_house.is_(False))
        if self.activity:
            query = query.filter(Listing.activities.like(f"%{self.activity}%"))
        if self.sale_type == "auctions":
            query = query.filter(Listing.is_auction.is_(True))
        elif self.sale_type is None and not self.allow_mixed_sale():
            pass
        if self.owner_financing:
            query = query.filter(Listing.owner_financing.is_(True))
        if self.has_video:
            query = query.filter(Listing.has_video.is_(True))
        return query

    def allow_mixed_sale(self):
        return True

    def sorted(self, query):
        order = SORTS[self.sort][1]
        if order == "acres_asc":
            return query.order_by(Listing.acres.asc(), Listing.pid.asc())
        if order == "acres_desc":
            return query.order_by(Listing.acres.desc(), Listing.pid.asc())
        if order == "newest":
            return query.order_by(Listing.insert_date.desc(), Listing.pid.asc())
        if order == "price_asc":
            return query.order_by(Listing.price.asc(), Listing.pid.asc())
        if order == "price_desc":
            return query.order_by(Listing.price.desc(), Listing.pid.asc())
        return query.order_by(Listing.sort_rank.asc(), Listing.pid.asc())

    # -- display helpers ----------------------------------------------------
    def h1(self) -> str:
        if self.county is not None:
            head = f"{self.county.name}, {self.county.state_code}"
        elif self.city is not None:
            head = f"{self.city.name}, {self.city.state_code}"
        elif self.region is not None:
            code = STATE_CODES.get(self.region.state_slug)
            head = f"{self.region.name}, {code}" if code else self.region.name
        elif self.state_name:
            head = self.state_name
        else:
            head = ""
        display = CATEGORY_H1_NAMES.get(self.category_slug) or self.category_label
        if self.owner_financing and self.category_slug in (None, "land"):
            display = "Owner Financing Land"
        noun = display or "Land"
        verb = "for Auction" if self.sale_type == "auctions" else "for Sale"
        return f"{head} {noun} {verb}".strip()

    def chips(self) -> list[dict]:
        chips = []
        if self.state_name:
            chips.append({"label": self.state_name, "field": "state"})
        if self.category_label:
            chips.append({"label": self.category_label, "field": "category"})
        if self.county is not None:
            chips.append({"label": self.county.name, "field": "county"})
        if self.city is not None:
            chips.append({"label": f"City: {self.city.name}", "field": "city"})
        if self.price_bucket:
            chips.append({"label": self.price_bucket[1], "field": "price"})
        if self.acres_bucket:
            chips.append({"label": self.acres_bucket[1], "field": "acres"})
        if self.sale_type == "auctions":
            chips.append({"label": "Auction", "field": "sale_type"})
        for chip in chips:
            chip["href"] = self.chip_removal_path(chip["field"])
        return chips

    def chip_removal_path(self, field: str) -> str:
        """Path with exactly one filter dimension removed (upstream chip ×)."""
        clone = SearchContext()
        clone.__dict__.update(self.__dict__)
        clone.page = 1
        if field == "state":
            clone.state_slug = None
            clone.state_name = ""
            clone.county = None
            clone.city = None
            clone.region = None
        elif field == "category":
            clone.category_slug = None
            clone.category_label = ""
        elif field == "county":
            clone.county = None
        elif field == "city":
            clone.city = None
        elif field == "price":
            clone.price_bucket = None
        elif field == "acres":
            clone.acres_bucket = None
        elif field == "sale_type":
            clone.sale_type = None
        return clone.path_for()

    def base_path(self) -> str:
        if self.state_slug:
            path = f"/{self.state_slug}"
        elif self.category_slug:
            path = f"/{self.category_slug}"
        else:
            path = "/land"
        if self.sale_type == "auctions":
            path += "/auctions"
        return path

    def segments(self) -> list[str]:
        """Canonical upstream segment order: location, category, filter."""
        segs = []
        if self.county is not None:
            segs.append(self.county.slug)
        if self.city is not None:
            segs.append(self.city.slug)
        if self.region is not None:
            segs.append(self.region.slug)
        if self.category_slug and self.state_slug:
            # on a state base the category rides as a segment
            # (/<state>-land-for-sale/<type>/...); on a category base the
            # category already is the path root
            segs.append(self.category_slug)
        if self.price_bucket and self.price_bucket[0] != "custom":
            segs.append(self.price_bucket[0])
        if self.acres_bucket and self.acres_bucket[0] != "custom":
            segs.append(self.acres_bucket[0])
        if self.beds_min:
            segs.append(f"beds-over-{self.beds_min}")
        if self.baths_min:
            segs.append(f"baths-over-{self.baths_min}")
        if self.residence is True:
            segs.append("with-residence")
        if self.residence is False:
            segs.append("no-residence")
        return segs

    def path_for(self, page: int = 1, **overrides) -> str:
        clone = SearchContext()
        clone.__dict__.update(self.__dict__)
        for key, value in overrides.items():
            setattr(clone, key, value)
        path = clone.base_path()
        for seg in clone.segments():
            path += f"/{seg}"
        if page > 1:
            path += f"/page-{page}"
        params = {}
        if clone.price_bucket and clone.price_bucket[0] == "custom":
            if clone.price_bucket[2] is not None:
                params["priceMin"] = clone.price_bucket[2]
            if clone.price_bucket[3] is not None:
                params["priceMax"] = clone.price_bucket[3]
        if clone.acres_bucket and clone.acres_bucket[0] == "custom":
            if clone.acres_bucket[2] is not None:
                params["acresMin"] = clone.acres_bucket[2]
            if clone.acres_bucket[3] is not None:
                params["acresMax"] = clone.acres_bucket[3]
        if clone.sort != "default":
            params["sort"] = clone.sort
        if clone.has_video:
            params["hasVideo"] = "1"
        if clone.owner_financing:
            params["ownerFinancing"] = "1"
        if params:
            path += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        return path

    def clone_without(self, field: str) -> "SearchContext":
        clone = SearchContext()
        clone.__dict__.update(self.__dict__)
        setattr(clone, field, None)
        if field == "owner_financing":
            clone.owner_financing = False
        if field == "has_video":
            clone.has_video = False
        return clone

    def facet_path(self, kind: str, slug: str, label: str = "", page: int = 1) -> str:
        """Path with one facet dimension replaced (upstream-style sub-path)."""
        clone = SearchContext()
        clone.__dict__.update(self.__dict__)
        clone.page = page
        if kind == "county":
            clone.county = County.query.filter_by(slug=slug,
                                                  state_slug=self.state_slug).first()
            clone.city = None
            clone.region = None
        elif kind == "city":
            clone.city = City.query.filter_by(slug=slug, state_slug=self.state_slug).first()
            clone.county = None
            clone.region = None
        elif kind == "region":
            clone.region = Region.query.filter_by(slug=slug,
                                                  state_slug=self.state_slug).first()
            clone.county = None
            clone.city = None
        elif kind == "price":
            for s, l, lo, hi in PRICE_BUCKETS:
                if s == slug:
                    clone.price_bucket = (s, l, lo, hi)
            clone.acres_bucket = None
        elif kind == "acres":
            for s, l, lo, hi in ACRES_BUCKETS:
                if s == slug:
                    clone.acres_bucket = (s, l, lo, hi)
            clone.price_bucket = None
        elif kind == "beds":
            clone.beds_min = int(slug.removeprefix("beds-over-"))
        elif kind == "baths":
            clone.baths_min = int(slug.removeprefix("baths-over-"))
        elif kind == "residence":
            clone.residence = (slug == "with-residence")
        elif kind == "sale":
            clone.sale_type = "auctions" if slug == "auctions" else None
        elif kind == "category":
            # Upstream keeps the whole location context on property-type
            # facet clicks: state page -> /florida-land-for-sale/
            # waterfront-property, Parker County -> /texas-land-for-sale/
            # parker-county/waterfront-property (both verified live).
            ptype = PropertyType.query.filter_by(slug=slug).first()
            clone.category_slug = slug
            clone.category_label = ptype.label if ptype else slug
        return clone.path_for(page=page)


PAGE_SIZE = 25


def facet_data(ctx: SearchContext) -> dict:
    """Sidebar facet groups computed from the current filtered query."""
    def scoped(dimension: str):
        return ctx.clone_without(dimension).filtered()

    facets: dict[str, Any] = {}

    facets["price"] = [
        {"slug": slug, "label": label,
         "count": scoped("price_bucket").filter(
             Listing.price >= lo if lo is not None else True_expr(),
             Listing.price <= hi if hi is not None else True_expr()).count()}
        for slug, label, lo, hi in PRICE_BUCKETS
    ]
    facets["acres"] = [
        {"slug": slug, "label": label,
         "count": scoped("acres_bucket").filter(
             Listing.acres >= lo if lo is not None else True_expr(),
             Listing.acres <= hi if hi is not None else True_expr()).count()}
        for slug, label, lo, hi in ACRES_BUCKETS
    ]
    facets["beds"] = [
        {"slug": slug, "label": label,
         "count": scoped("beds_min").filter(Listing.beds >= n).count()}
        for slug, label, n in BEDS_OPTIONS
    ]
    facets["baths"] = [
        {"slug": slug, "label": label,
         "count": scoped("baths_min").filter(Listing.baths >= n).count()}
        for slug, label, n in BATHS_OPTIONS
    ]
    facets["residence"] = {
        "yes": scoped("residence").filter(Listing.has_house.is_(True)).count(),
        "no": scoped("residence").filter(Listing.has_house.is_(False)).count(),
    }
    type_rows = []
    for ptype in PropertyType.query.order_by(PropertyType.listing_count.desc()).all():
        if ptype.slug == "land":
            continue
        count = scoped("category_slug").filter(
            Listing.category_slugs.like(f"%{ptype.slug}%")).count()
        if count:
            type_rows.append({"slug": ptype.slug, "label": ptype.label,
                              "count": count})
    facets["types"] = type_rows
    county_rows = []
    if ctx.state_slug and ctx.county is None:
        rows = (scoped("county").with_entities(Listing.county, Listing.county_slug,
                                               db.func.count(Listing.pid))
                .group_by(Listing.county, Listing.county_slug)
                .order_by(db.func.count(Listing.pid).desc()).limit(10).all())
        county_rows = [{"slug": slug, "label": name, "count": cnt}
                       for name, slug, cnt in rows]
    facets["counties"] = county_rows
    city_rows = []
    if ctx.state_slug and ctx.city is None:
        rows = (scoped("city").with_entities(Listing.city, Listing.city_slug,
                                             db.func.count(Listing.pid))
                .group_by(Listing.city, Listing.city_slug)
                .order_by(db.func.count(Listing.pid).desc()).limit(10).all())
        city_rows = [{"slug": slug, "label": name, "count": cnt}
                     for name, slug, cnt in rows]
    facets["cities"] = city_rows
    region_rows = []
    if ctx.state_slug and ctx.region is None:
        for region in Region.query.filter_by(state_slug=ctx.state_slug).all():
            count = scoped("region").filter(
                Listing.county.in_(load_json(region.counties, []))).count()
            if count:
                region_rows.append({"slug": region.slug, "label": region.name,
                                    "count": count})
    facets["regions"] = region_rows
    base = ctx.filtered()
    facets["sale"] = {
        "for_sale": base.filter(Listing.is_auction.is_(False)).count(),
        "auction": base.filter(Listing.is_auction.is_(True)).count(),
        "total": base.count(),
    }
    return facets


def True_expr():
    return db.true()


# ---------------------------------------------------------------------------
# routes — home & static
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    featured_pids = [row.pid for row in
                     HomeFeatured.query.order_by(HomeFeatured.position).all()]
    featured = [lp for pid in featured_pids if (lp := Listing.query.get(pid))]
    tiles = CategoryTile.query.order_by(CategoryTile.position).all()
    for tile in tiles:
        count = Listing.query.filter(
            Listing.status.in_(ACTIVE_STATUSES),
            Listing.category_slugs.like(f"%{tile.slug}%")).count()
        noun = "Land Properties" if tile.slug == "land" else f"{tile.label} Properties"
        tile.count_line = f"{count:,} {noun}"
    top_states = (Listing.query.with_entities(Listing.state, Listing.state_slug,
                                              db.func.count(Listing.pid))
                  .filter(Listing.status.in_(ACTIVE_STATUSES))
                  .group_by(Listing.state, Listing.state_slug)
                  .order_by(db.func.count(Listing.pid).desc()).limit(10).all())
    return render_template("index.html", featured=featured, tiles=tiles,
                           top_states=top_states)


@app.route("/_health")
def health():
    return {
        "ok": True, "site": "landwatch",
        "listings": Listing.query.count(),
        "agents": Agent.query.count(),
        "counties": County.query.count(),
        "cities": City.query.count(),
    }


@app.route("/terms-conditions")
def terms():
    page = StaticPage.query.filter_by(slug="terms-conditions").first()
    if page is None:
        abort(404)
    return render_template("static_page.html", page=page)


@app.route("/sitemap")
def sitemap():
    links = []
    for state, slug in (Listing.query.with_entities(Listing.state, Listing.state_slug)
                         .distinct().order_by(Listing.state).all()):
        links.append({"href": f"/{slug}", "text": f"{state} Land for Sale"})
    for ptype in PropertyType.query.order_by(PropertyType.id).all():
        links.append({"href": f"/{ptype.slug}", "text": f"{ptype.label} for Sale"})
    return render_template("sitemap.html", links=links)


# ---------------------------------------------------------------------------
# routes — search pages
# ---------------------------------------------------------------------------

def render_search(ctx: SearchContext):
    query = ctx.sorted(ctx.filtered())
    total = query.count()
    listings = query.offset((ctx.page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    facets = facet_data(ctx)
    return render_template(
        "search.html", ctx=ctx, listings=listings, total=total, facets=facets,
        page=ctx.page, pages=pages,
        from_n=(ctx.page - 1) * PAGE_SIZE + 1 if total else 0,
        to_n=min(ctx.page * PAGE_SIZE, total),
        sort_label=SORTS[ctx.sort][0])


def build_search_ctx(state_slug=None, category_slug=None, segments=None):
    ctx = SearchContext()
    if state_slug:
        ctx.state_slug = state_slug
        ctx.state_name = STATE_SLUGS.get(state_slug[:-len("-land-for-sale")])
        if ctx.state_name is None:
            return None
    if category_slug:
        ptype = PropertyType.query.filter_by(slug=category_slug).first()
        if ptype is None:
            return None
        ctx.category_slug = category_slug
        ctx.category_label = ptype.label
    if segments:
        for segment in segments:
            if not ctx.apply_segment(segment):
                return None
    ctx.apply_query(request.args)
    page_raw = request.args.get("page", "1")
    try:
        ctx.page = max(1, int(page_raw))
    except ValueError:
        ctx.page = 1
    return ctx


def state_view(state_slug, path=""):
    segments = [s for s in path.split("/") if s]
    page = 1
    if segments and (m := re.fullmatch(r"page-(\d+)", segments[-1])):
        page = max(1, int(m.group(1)))
        segments = segments[:-1]
    ctx = build_search_ctx(state_slug=state_slug, segments=segments)
    if ctx is None:
        abort(404)
    ctx.page = page
    return render_search(ctx)


def category_view(category_slug, path=""):
    segments = [s for s in path.split("/") if s]
    page = 1
    if segments and (m := re.fullmatch(r"page-(\d+)", segments[-1])):
        page = max(1, int(m.group(1)))
        segments = segments[:-1]
    ctx = build_search_ctx(category_slug=category_slug, segments=segments)
    if ctx is None:
        abort(404)
    ctx.page = page
    return render_search(ctx)


for _state in STATE_SLUGS:
    _slug = f"{_state}-land-for-sale"
    app.add_url_rule(f"/{_slug}", f"state_{_state}", state_view,
                     defaults={"state_slug": _slug, "path": ""})
    app.add_url_rule(f"/{_slug}/<path:path>", f"state_{_state}_path", state_view,
                     defaults={"state_slug": _slug})
for _category in CATEGORY_SLUGS:
    app.add_url_rule(f"/{_category}", f"category_{_category}", category_view,
                     defaults={"category_slug": _category, "path": ""})
    app.add_url_rule(f"/{_category}/<path:path>", f"category_{_category}_path",
                     category_view, defaults={"category_slug": _category})


# ---------------------------------------------------------------------------
# routes — listing detail
# ---------------------------------------------------------------------------

@app.route("/<slug>/pid/<int:pid>")
def listing_detail(slug, pid):
    listing = Listing.query.get(pid)
    if listing is None:
        abort(404)
    if slug != listing.canonical_slug:
        return redirect(listing.detail_path(), code=301)
    agent = Agent.query.get(listing.broker_id) if listing.broker_id else None
    more = (Listing.query.filter(Listing.broker_id == listing.broker_id,
                                 Listing.pid != listing.pid,
                                 Listing.status.in_(ACTIVE_STATUSES))
            .order_by(Listing.sort_rank).limit(3).all())
    recent = (Listing.query.filter(Listing.pid != listing.pid,
                                   Listing.status.in_(ACTIVE_STATUSES))
              .order_by(Listing.sort_rank).limit(4).all())
    sponsored = (Agent.query.filter(Agent.is_sponsored.is_(True))
                 .order_by(Agent.account_id).first())
    return render_template("listing_detail.html", listing=listing, agent=agent,
                           more=more, recent=recent, sponsored=sponsored)


@app.route("/pid/<int:pid>")
def listing_detail_short(pid):
    listing = Listing.query.get(pid)
    if listing is None:
        abort(404)
    return redirect(listing.detail_path(), code=301)


# ---------------------------------------------------------------------------
# routes — agents
# ---------------------------------------------------------------------------

@app.route("/find-agent")
def find_agent():
    state = (request.args.get("state") or "").strip().upper()
    agents = Agent.query.order_by(Agent.total_listings.desc(),
                                   Agent.account_id).all()
    if state:
        agents = [a for a in agents if a.state_code == state]
    states = [row[0] for row in (Agent.query.with_entities(Agent.state_code)
                                .distinct().order_by(Agent.state_code).all()
                                if Agent.query.count() else [])]
    return render_template("find_agent.html", agents=agents, states=states,
                           current_state=state)


@app.route("/profile/<slug>/<int:account_id>")
def agent_profile(slug, account_id):
    agent = Agent.query.get(account_id)
    if agent is None:
        abort(404)
    if agent.slug != slug:
        return redirect(agent.profile_path(), code=301)
    listings = (Listing.query.filter_by(broker_id=agent.account_id)
                .order_by(Listing.sort_rank).all())
    return render_template("agent_profile.html", agent=agent, listings=listings)


# ---------------------------------------------------------------------------
# routes — location search
# ---------------------------------------------------------------------------

@app.route("/search")
def search():
    query = (request.args.get("q") or request.args.get("location") or "").strip()
    if not query:
        return redirect("/")
    candidates = []
    for county in County.query.all():
        candidates.append({"label": f"{county.name}, {county.state_code}",
                           "url": f"/{county.state_slug}/{county.slug}"})
    for city in City.query.all():
        candidates.append({"label": f"{city.name}, {city.state_code}",
                           "url": f"/{city.state_slug}/{city.slug}"})
    for state, slug in (Listing.query.with_entities(Listing.state, Listing.state_slug)
                        .distinct().all()):
        candidates.append({"label": state, "url": f"/{slug}"})
    scored = token_scores(query, [c["label"] for c in candidates])
    best = None
    best_score = 0
    for cand, score in zip(candidates, scored):
        if score > best_score:
            best, best_score = cand, score
    if best is not None:
        return redirect(best["url"])
    # no location matched: fall back to scored listing search (upstream's
    # keywordQuery path) and open the best-matching listing detail page
    listings = Listing.query.filter(Listing.status.in_(ACTIVE_STATUSES)).all()
    rows = [(l.title or l.street, l) for l in listings]
    scored = token_scores(query, [f"{r[0]} {r[1].description_short or ''} {r[1].county} "
                                  f"{r[1].city} {r[1].state}" for r in rows])
    best_listing, best_score = None, 0
    for (label, listing), score in zip(rows, scored):
        if score > best_score:
            best_listing, best_score = listing, score
    if best_listing is not None and best_score >= 2:
        return redirect(best_listing.detail_path())
    flash(f"No locations matched “{query}”. Try a city, county, or state.", "error")
    return redirect("/")
    return redirect(best["url"])


@app.route("/api/suggest")
def suggest():
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({"results": []})
    rows = []
    for county in County.query.filter(County.name.ilike(f"%{query}%")).limit(6):
        rows.append({"label": f"{county.name}, {county.state_code}", "type": "County",
                     "url": f"/{county.state_slug}/{county.slug}"})
    for city in City.query.filter(City.name.ilike(f"{query}%")).limit(6):
        rows.append({"label": f"{city.name}, {city.state_code}", "type": "City",
                     "url": f"/{city.state_slug}/{city.slug}"})
    for state, slug in (Listing.query.with_entities(Listing.state, Listing.state_slug)
                        .distinct().all()):
        if query.lower() in state.lower():
            rows.append({"label": state, "type": "State", "url": f"/{slug}"})
    return jsonify({"results": rows[:8]})


# ---------------------------------------------------------------------------
# routes — auth
# ---------------------------------------------------------------------------

@app.route("/log-in", methods=["GET", "POST"])
def log_in():
    if request.method == "GET":
        return render_template("log_in.html")
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        flash("Invalid email or password.", "error")
        return render_template("log_in.html"), 401
    response = redirect(url_for("account"))
    response.set_cookie("lw_session", create_session(user.id), httponly=True)
    return response


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    name = (request.form.get("name") or "").strip()
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        flash("Enter a valid email address.", "error")
        return render_template("register.html"), 400
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return render_template("register.html"), 400
    if User.query.filter_by(email=email).first() is not None:
        flash("An account with that email already exists.", "error")
        return render_template("register.html"), 409
    user = User(email=email, password_hash=stable_password_hash(password), name=name,
                created_at=now_iso())
    db.session.add(user)
    db.session.commit()
    response = redirect(url_for("account"))
    response.set_cookie("lw_session", create_session(user.id), httponly=True)
    return response


@app.route("/log-out")
def log_out():
    token = request.cookies.get("lw_session")
    if token:
        destroy_session(token)
    response = redirect("/")
    response.delete_cookie("lw_session")
    return response


@app.route("/account")
def account():
    user = current_user()
    if user is None:
        return redirect(url_for("log_in"))
    favorites = (Favorite.query.filter_by(user_id=user.id)
                 .order_by(Favorite.created_at.desc()).all())
    listings = [Listing.query.get(f.pid) for f in favorites]
    listings = [l for l in listings if l is not None]
    searches = (SavedSearch.query.filter_by(user_id=user.id)
                .order_by(SavedSearch.created_at.desc()).all())
    inquiries = (Inquiry.query.filter_by(user_id=user.id)
                 .order_by(Inquiry.created_at.desc()).all())
    return render_template("account.html", user=user, listings=listings,
                          searches=searches, inquiries=inquiries)


@app.route("/account/edit", methods=["GET", "POST"])
def account_edit():
    user = current_user()
    if user is None:
        return redirect(url_for("log_in"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        if phone and not re.match(r"^[\d\s()+.-]{7,20}$", phone):
            flash("Enter a valid phone number.", "error")
            return render_template("account_edit.html", user=user), 400
        if name:
            user.name = name
        user.phone = phone
        db.session.commit()
        flash("Profile updated.", "ok")
        return redirect(url_for("account"))
    return render_template("account_edit.html", user=user)


# ---------------------------------------------------------------------------
# routes — favorites, saved searches, contact
# ---------------------------------------------------------------------------

@app.route("/favorite/<int:pid>", methods=["POST"])
def favorite(pid):
    user = current_user()
    if user is None:
        return jsonify({"ok": False, "reason": "log-in-required"}), 401
    listing = Listing.query.get(pid)
    if listing is None:
        abort(404)
    row = Favorite.query.filter_by(user_id=user.id, pid=pid).first()
    if row is not None:
        db.session.delete(row)
        db.session.commit()
        return jsonify({"ok": True, "saved": False})
    db.session.add(Favorite(user_id=user.id, pid=pid, created_at=now_iso()))
    db.session.commit()
    return jsonify({"ok": True, "saved": True})


@app.route("/save-search", methods=["POST"])
def save_search():
    user = current_user()
    if user is None:
        return jsonify({"ok": False, "reason": "log-in-required"}), 401
    payload = request.get_json(silent=True) or request.form
    url = (payload.get("url") or "").strip()
    name = (payload.get("name") or "").strip()
    if not url or not url.startswith("/") or len(url) > 300:
        return jsonify({"ok": False, "reason": "invalid-url"}), 400
    db.session.add(SavedSearch(user_id=user.id, name=name or "Land search", url=url,
                               created_at=now_iso()))
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/remove-saved-search/<int:search_id>", methods=["POST"])
def remove_saved_search(search_id):
    user = current_user()
    if user is None:
        return redirect(url_for("log_in"))
    row = SavedSearch.query.get(search_id)
    if row is not None and row.user_id == user.id:
        db.session.delete(row)
        db.session.commit()
    return redirect(url_for("account"))


@app.route("/remove-favorite/<int:pid>", methods=["POST"])
def remove_favorite(pid):
    user = current_user()
    if user is None:
        return redirect(url_for("log_in"))
    row = Favorite.query.filter_by(user_id=user.id, pid=pid).first()
    if row is not None:
        db.session.delete(row)
        db.session.commit()
    return redirect(url_for("account"))


@app.route("/contact-agent/<int:account_id>", methods=["POST"])
def contact_agent(account_id):
    agent = Agent.query.get(account_id)
    if agent is None:
        abort(404)
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    message = (request.form.get("message") or "").strip()
    user = current_user()
    errors = []
    if not message:
        errors.append("Message is required.")
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""):
        errors.append("A valid email address is required.")
    if errors:
        return render_template("contact_error.html", listing=agent, errors=errors), 400
    db.session.add(Inquiry(user_id=user.id if user else None, pid=None, name=name or agent.name,
                           email=email, message=message, created_at=now_iso()))
    db.session.commit()
    flash("Your message has been sent to the agent.", "ok")
    return redirect(agent.profile_path())


@app.route("/contact/<int:pid>", methods=["POST"])
def contact(pid):
    listing = Listing.query.get(pid)
    if listing is None:
        abort(404)
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    message = (request.form.get("message") or "").strip()
    user = current_user()
    errors = []
    if not name:
        errors.append("Name is required.")
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""):
        errors.append("A valid email address is required.")
    if message and len(message) > 2000:
        errors.append("Message must be 2,000 characters or fewer.")
    if errors:
        return render_template("contact_error.html", listing=listing,
                               errors=errors), 400
    db.session.add(Inquiry(user_id=user.id if user else None, pid=pid, name=name,
                           email=email, phone=phone, message=message,
                           created_at=now_iso()))
    db.session.commit()
    flash("Your message has been sent to the listing agent.", "ok")
    return redirect(listing.detail_path())


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("500.html"), 500


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------

BOOTSTRAP = os.environ.get("WEBSYN_SKIP_BOOTSTRAP") != "1"

if BOOTSTRAP:
    with app.app_context():
        db.create_all()
        try:
            from seed_data import seed_database, seed_benchmark_users
            seed_database()
            seed_benchmark_users()
        except ImportError:
            pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 43074))
    app.run(host="0.0.0.0", port=port, debug=False)
