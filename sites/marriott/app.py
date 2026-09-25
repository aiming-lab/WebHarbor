#!/usr/bin/env python3
"""Marriott Bonvoy (marriott.com) mirror — Flask app.

Functional mirror of https://www.marriott.com/ built for the WebHarbor
offline benchmark environment: destination & hotel search, hotel detail
pages (overview / rooms / reviews / photos), the reservation flow, the
Marriott Bonvoy account domain (auth, profile, trips, saved hotels,
payment methods) and the marketing pages (offers, brands, destinations).

All catalog rows (hotels, destinations, brands, room types, guest
reviews) come from the tracked source snapshot under source_data/ which
was captured from the live site; see provenance.json.
"""
import os
import json
import re
import secrets
import string
from datetime import datetime, date, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlencode

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    jsonify, session, abort,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user,
)
from flask_bcrypt import Bcrypt
from sqlalchemy import or_, and_, func

BASE_DIR = Path(__file__).resolve().parent
INSTANCE = BASE_DIR / "instance"
INSTANCE.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# The container always runs against instance/marriott.db; the test suite
# points this at a scratch copy so its write paths never touch the seed.
_DB_PATH = os.environ.get("WEBHARBOR_MIRROR_DB") or str(INSTANCE / "marriott.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{_DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "sign_in"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "error"

# The mirror runs against a frozen catalog snapshot; the rates the live
# site quoted for its own SSR snapshot dates are pinned to this date.
MIRROR_REFERENCE_DATE = date(2026, 9, 23)

MARRIOTT_NAV = [
    {"label": "Find & Reserve", "href": "/search/findHotels.mi"},
    {"label": "Special Offers", "href": "/offers.mi"},
    {"label": "Our Brands", "href": "/brands.mi"},
    {"label": "Our Credit Cards", "href": "/credit-cards.mi"},
    {"label": "About Marriott Bonvoy", "href": "/loyalty.mi"},
    {"label": "Careers at Marriott", "href": "/careers.mi"},
]


# =====================================================================
# MODELS
# =====================================================================

class SiteContent(db.Model):
    __tablename__ = "site_content"
    key = db.Column(db.String(80), primary_key=True)
    content = db.Column(db.Text, nullable=False)


class Brand(db.Model):
    __tablename__ = "brands"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(30), nullable=False)  # luxury / distinctive / premium / select / longer_stays / collections
    blurb = db.Column(db.Text, nullable=False)
    site_order = db.Column(db.Integer, nullable=False)

    hotels = db.relationship("Hotel", backref="brand", lazy=True)

    @property
    def category_label(self):
        return {
            "luxury": "Luxury",
            "distinctive": "Distinctive Luxury",
            "premium": "Premium",
            "select": "Select",
            "longer_stays": "Longer Stays",
            "collections": "Collections",
        }.get(self.category, self.category)


class Destination(db.Model):
    __tablename__ = "destinations"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100))
    country = db.Column(db.String(100), nullable=False)
    country_code = db.Column(db.String(4))
    region_path = db.Column(db.String(200), nullable=False)  # e.g. united-states/new-york/new-york-city
    destination_name = db.Column(db.String(160))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    hero_image = db.Column(db.String(300))
    hotel_count = db.Column(db.Integer, default=0)
    intro = db.Column(db.Text)                   # live page's own intro copy
    explore = db.Column(db.Text, default="[]")  # JSON [{label, paragraphs[]}]

    hotels = db.relationship("Hotel", backref="destination", lazy=True)

    @property
    def explore_sections(self):
        try:
            return json.loads(self.explore or "[]")
        except ValueError:
            return []

    # the live destination pages title themselves "Hotels in <City>, <ABBR>"
    _STATE_ABBR = {
        "New York": "NY", "California": "CA", "Florida": "FL",
        "Georgia": "GA", "Texas": "TX", "Illinois": "IL",
        "Colorado": "CO", "Massachusetts": "MA", "Tennessee": "TN",
        "Nevada": "NV", "Washington": "WA", "District of Columbia": "DC",
    }

    @property
    def state_abbr(self):
        return self._STATE_ABBR.get(self.state or "")

    @property
    def page_path(self):
        return f"/en-us/destinations/{self.region_path}.mi"

    @property
    def display_name(self):
        if self.state and self.state != self.city:
            return f"{self.city}, {self.state}"
        return f"{self.city}, {self.country}"


class Hotel(db.Model):
    __tablename__ = "hotels"
    id = db.Column(db.Integer, primary_key=True)
    marsha = db.Column(db.String(8), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey("destinations.id"), nullable=False)
    address_line = db.Column(db.String(250), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100))
    country = db.Column(db.String(100), nullable=False)
    country_code = db.Column(db.String(4))
    postal_code = db.Column(db.String(16))
    phone = db.Column(db.String(40))
    fax = db.Column(db.String(40))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    description = db.Column(db.Text, nullable=False)
    short_description = db.Column(db.Text)       # properties-list card copy
    checkin_time = db.Column(db.String(10), default="16:00")
    checkout_time = db.Column(db.String(10), default="11:00")
    amenities = db.Column(db.Text, default="[]")  # JSON list of amenity labels
    base_rate = db.Column(db.Integer)             # USD/night captured on the live site
    points_rate = db.Column(db.Integer)           # Bonvoy points/night
    rating_avg = db.Column(db.Float)               # BazaarVoice average
    review_count = db.Column(db.Integer)
    rating_distribution = db.Column(db.Text)      # JSON {5: n, 4: n, ...}
    sub_ratings = db.Column(db.Text)              # JSON {label: {avg, count}}
    hero_image = db.Column(db.String(300))
    distance_text = db.Column(db.String(60))      # "0.1 mi from destination"
    is_bookable = db.Column(db.Boolean, default=True)

    room_types = db.relationship("RoomType", backref="hotel", lazy=True,
                                 cascade="all, delete-orphan", order_by="RoomType.base_rate")
    images = db.relationship("HotelImage", backref="hotel", lazy=True,
                             cascade="all, delete-orphan", order_by="HotelImage.sort_order")
    reviews = db.relationship("Review", backref="hotel", lazy=True,
                             cascade="all, delete-orphan", order_by="Review.reviewed_on.desc()")

    @property
    def detail_path(self):
        return f"/en-us/hotels/{self.marsha.lower()}-{self.slug}/overview/"

    def path_for(self, page):
        return f"/en-us/hotels/{self.marsha.lower()}-{self.slug}/{page}/"

    @property
    def amenity_list(self):
        try:
            return json.loads(self.amenities or "[]")
        except ValueError:
            return []

    @property
    def rating_stars(self):
        return round((self.rating_avg or 0))

    @property
    def distance_miles(self):
        m = re.match(r"([0-9.]+) mi", self.distance_text or "")
        return float(m.group(1)) if m else None

    def average_for(self, nights=1):
        return (self.base_rate or 0) * nights


class HotelImage(db.Model):
    __tablename__ = "hotel_images"
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey("hotels.id"), nullable=False, index=True)
    path = db.Column(db.String(300), nullable=False)      # /static/images/...
    alt = db.Column(db.String(200), default="")
    category = db.Column(db.String(40), default="gallery")  # gallery / room / dining / fitness / pool / exterior
    sort_order = db.Column(db.Integer, default=0)


class RoomType(db.Model):
    __tablename__ = "room_types"
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey("hotels.id"), nullable=False, index=True)
    code = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    bed_description = db.Column(db.String(120), nullable=False)
    max_occupancy = db.Column(db.Integer, nullable=False, default=2)
    size_sqft = db.Column(db.Integer)
    view = db.Column(db.String(80))
    features = db.Column(db.Text, default="[]")   # JSON list
    description = db.Column(db.Text, nullable=False)
    base_rate = db.Column(db.Integer, nullable=False)  # USD/night
    points_rate = db.Column(db.Integer)
    image_path = db.Column(db.String(300))
    sort_order = db.Column(db.Integer, default=0)

    @property
    def feature_list(self):
        try:
            return json.loads(self.features or "[]")
        except ValueError:
            return []


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey("hotels.id"), nullable=False, index=True)
    author = db.Column(db.String(80), nullable=False)
    author_location = db.Column(db.String(120))
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    trip_type = db.Column(db.String(40))            # Business / Leisure / Other
    reviewed_on = db.Column(db.Date, nullable=False)
    management_response = db.Column(db.Text)


class Offer(db.Model):
    __tablename__ = "offers"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    blurb = db.Column(db.Text, nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"))
    cta_label = db.Column(db.String(80), default="View Details")
    cta_href = db.Column(db.String(200))
    image_path = db.Column(db.String(300))
    book_by = db.Column(db.String(40))
    stay_dates = db.Column(db.String(80))
    site_order = db.Column(db.Integer, default=0)

    brand = db.relationship("Brand")


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30))
    member_number = db.Column(db.String(20), unique=True, nullable=False)
    member_tier = db.Column(db.String(30), default="Member")  # Member / Silver / Gold / Platinum / Titanium
    points = db.Column(db.Integer, default=0)
    joined_on = db.Column(db.Date)
    street_address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    country = db.Column(db.String(80))
    postal_code = db.Column(db.String(16))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reservations = db.relationship("Reservation", backref="user", lazy=True,
                                   cascade="all, delete-orphan",
                                   order_by="Reservation.checkin.desc()")
    favorites = db.relationship("Favorite", backref="user", lazy=True,
                                cascade="all, delete-orphan")
    payment_methods = db.relationship("PaymentMethod", backref="user", lazy=True,
                                      cascade="all, delete-orphan")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def points_formatted(self):
        return f"{self.points:,}"


class PaymentMethod(db.Model):
    __tablename__ = "payment_methods"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    card_type = db.Column(db.String(20), nullable=False)  # Visa / Mastercard / Amex
    last_four = db.Column(db.String(4), nullable=False)
    holder_name = db.Column(db.String(120), nullable=False)
    exp_month = db.Column(db.Integer, nullable=False)
    exp_year = db.Column(db.Integer, nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    added_on = db.Column(db.Date)


class Favorite(db.Model):
    __tablename__ = "favorites"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey("hotels.id"), nullable=False)
    saved_on = db.Column(db.Date)

    hotel = db.relationship("Hotel")
    __table_args__ = (db.UniqueConstraint("user_id", "hotel_id", name="uq_favorite"),)


class Reservation(db.Model):
    __tablename__ = "reservations"
    id = db.Column(db.Integer, primary_key=True)
    confirmation_number = db.Column(db.String(12), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    hotel_id = db.Column(db.Integer, db.ForeignKey("hotels.id"), nullable=False)
    room_type_id = db.Column(db.Integer, db.ForeignKey("room_types.id"), nullable=False)
    guest_first_name = db.Column(db.String(80), nullable=False)
    guest_last_name = db.Column(db.String(80), nullable=False)
    guest_email = db.Column(db.String(120), nullable=False)
    checkin = db.Column(db.Date, nullable=False)
    checkout = db.Column(db.Date, nullable=False)
    adults = db.Column(db.Integer, nullable=False, default=1)
    children = db.Column(db.Integer, nullable=False, default=0)
    rooms = db.Column(db.Integer, nullable=False, default=1)
    nightly_rate = db.Column(db.Integer, nullable=False)
    total_rate = db.Column(db.Integer, nullable=False)
    points_redeemed = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="confirmed")  # confirmed / canceled
    special_requests = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    hotel = db.relationship("Hotel")
    room_type = db.relationship("RoomType")

    @property
    def nights(self):
        return (self.checkout - self.checkin).days

    @property
    def room_description(self):
        return f"{self.rooms} Room(s), {self.adults} Adult(s), {self.children} Child(ren)"


# =====================================================================
# HELPERS
# =====================================================================

STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "it", "by", "with", "near", "hotel", "hotels", "in", "new",
}


def tokenize(text):
    tokens = [t.lower() for t in re.split(r"[^a-zA-Z0-9]+", text or "")
              if len(t) > 1]
    return tokens


def scored_hotel_search(query, hotels_qs, limit=None):
    """Token-overlap scored search across hotel name, city, brand, description."""
    tokens = [t for t in tokenize(query) if t not in STOP_WORDS]
    if not tokens:
        return hotels_qs.order_by(Hotel.name).all()
    results = []
    for hotel in hotels_qs.all():
        brand = Brand.query.get(hotel.brand_id)
        text = " ".join([
            hotel.name, hotel.city, hotel.state or "", hotel.country,
            brand.name if brand else "", hotel.description,
        ]).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            results.append((hotel, score))
    results.sort(key=lambda pair: (-pair[1], pair[0].name))
    return [h for h, _ in results] if limit is None else [h for h, _ in results][:limit]


def parse_date(value, fallback=None):
    if not value:
        return fallback
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return fallback


def fmt_date(d):
    return d.strftime("%m/%d/%Y") if d else ""


def default_dates():
    """Search results default to the mirror reference window (mirrors the live
    site defaulting to today + 1); keeps catalog rates consistent."""
    return MIRROR_REFERENCE_DATE, MIRROR_REFERENCE_DATE + timedelta(days=1)


def _rating_distribution(hotel):
    """Distribution JSON with integer star keys (the snapshot stores strings)."""
    raw = json.loads(hotel.rating_distribution or "{}")
    return {int(k): v for k, v in raw.items()}


def confirmation_number():
    alphabet = string.ascii_uppercase + string.digits
    rnd = secrets.SystemRandom()
    return "".join(rnd.choice(alphabet) for _ in range(10))


def parse_int(value, default=None):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def amenity_groups(hotel):
    groups = {
        "Hotel Features": [],
        "Rooms": [],
        "Dining & Entertainment": [],
        "Fitness & Recreation": [],
        "Services": [],
    }
    dining_kw = ("restaurant", "bar", "lounge", "dining", "coffee", "breakfast", "room service", "snack")
    fit_kw = ("fitness", "pool", "spa", "gym", "whirlpool", "tennis", "golf", "beach", "ski", "yoga", "sauna", "bicycle")
    room_kw = ("room", "suite", "wi-fi", "wifi", "internet", "tv", "air", "balcony", "kitchen", "laundry", "linens", "crib", "accessib")
    service_kw = ("service", "front desk", "concierge", "parking", "valet", "shuttle", "laundry", "dry clean", "safe", "key", "24")
    for amenity in hotel.amenity_list:
        label = amenity.strip()
        low = label.lower()
        if any(k in low for k in dining_kw):
            groups["Dining & Entertainment"].append(label)
        elif any(k in low for k in fit_kw):
            groups["Fitness & Recreation"].append(label)
        elif any(k in low for k in room_kw):
            groups["Rooms"].append(label)
        elif any(k in low for k in service_kw):
            groups["Services"].append(label)
        else:
            groups["Hotel Features"].append(label)
    return {k: v for k, v in groups.items() if v}


def safe_return(target, fallback):
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        parsed = urlsplit(target)
        if not parsed.netloc and not parsed.scheme and not any(ord(c) < 32 for c in target):
            return target
    return fallback


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


@app.before_request
def protect_forms():
    if request.method == "POST":
        expected = session.get("csrf_token", "")
        observed = request.form.get("csrf_token", "")
        if not expected or not secrets.compare_digest(expected, observed):
            abort(400, "This form has expired. Reload the page and try again.")


def stay_url(path):
    args = request.args
    params = {
        "fromDate": args.get("fromDate"), "toDate": args.get("toDate"),
        "rooms": args.get("rooms") or args.get("roomCount") or args.get("numberOfRooms"),
        "adults": args.get("adults") or args.get("numAdultsPerRoom") or args.get("numberOfAdults"),
        "useRewardsPoints": args.get("useRewardsPoints"),
    }
    query = urlencode({k: v for k, v in params.items() if v})
    return path + (("&" if "?" in path else "?") + query if query else "")


@app.context_processor
def inject_globals():
    footer_destinations = Destination.query.order_by(
        Destination.hotel_count.desc(), Destination.city).limit(14).all()
    return {
        "nav": MARRIOTT_NAV,
        "csrf_token": csrf_token,
        "stay_url": stay_url,
        "stay_from_date": parse_date(request.args.get("fromDate")) or default_dates()[0],
        "stay_to_date": parse_date(request.args.get("toDate")) or default_dates()[1],
        "reference_date": MIRROR_REFERENCE_DATE,
        "footer_destinations": footer_destinations,
        "timedelta": timedelta,
    }


@app.template_filter("fmttime")
def fmttime_filter(value):
    """'16:00' -> '4:00 pm', matching the live pages' check-in copy."""
    if not value:
        return ""
    m = re.match(r"(\d{1,2}):(\d{2})", str(value))
    if not m:
        return str(value)
    hour = int(m.group(1))
    mins = m.group(2)
    suffix = "am" if 0 <= hour < 12 else "pm"
    hour12 = hour % 12 or 12
    return f"{hour12}:{mins} {suffix}"


@app.template_filter("usd")
def usd_filter(value):
    return f"${value:,.0f}"


@app.template_filter("fmtdate")
def fmtdate_filter(value):
    return fmt_date(value)


# =====================================================================
# AUTH
# =====================================================================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/sign-in.mi", methods=["GET", "POST"])
def sign_in():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(func.lower(User.email) == email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            target = request.args.get("next")
            if target:
                return redirect(safe_return(target, url_for("account")))
            return redirect(url_for("account"))
        flash("The email or password you entered is incorrect. Please try again.", "error")
    return render_template("sign_in.html")


@app.route("/loyalty/createAccount/createAccountPage1.mi", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        errors = []
        if not (first_name and last_name):
            errors.append("Please enter your first and last name.")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append("Please enter a valid email address.")
        if len(password) < 8:
            errors.append("Your password must be at least 8 characters long.")
        elif password != confirm:
            errors.append("Your passwords do not match.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            if User.query.filter(func.lower(User.email) == email).first():
                flash("An account with that email already exists. Please sign in.", "error")
            else:
                member_number = "".join(secrets.choice(string.digits) for _ in range(9))
                user = User(
                    email=email,
                    password_hash=bcrypt.generate_password_hash(password).decode(),
                    first_name=first_name,
                    last_name=last_name,
                    member_number=member_number,
                    points=42000,
                    joined_on=date(2026, 8, 1),
                )
                db.session.add(user)
                db.session.commit()
                login_user(user)
                flash("Welcome to Marriott Bonvoy! Your member account is ready.", "success")
                return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logoff", methods=["POST"])
@login_required
def logoff():
    logout_user()
    return redirect(url_for("index"))


@app.route("/loyalty/myAccount.mi")
@app.route("/account")
@login_required
def account():
    upcoming = [r for r in current_user.reservations
                if r.status == "confirmed" and r.checkin >= MIRROR_REFERENCE_DATE]
    past = [r for r in current_user.reservations
            if r.status != "confirmed" or r.checkin < MIRROR_REFERENCE_DATE]
    return render_template("account.html", upcoming=upcoming, past=past)


@app.route("/loyalty/myAccount/profile.mi", methods=["GET", "POST"])
@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name", "").strip() or current_user.first_name
        current_user.last_name = request.form.get("last_name", "").strip() or current_user.last_name
        phone = request.form.get("phone", "").strip()
        current_user.phone = phone
        current_user.street_address = request.form.get("street_address", "").strip()
        current_user.city = request.form.get("city", "").strip()
        current_user.state = request.form.get("state", "").strip()
        current_user.country = request.form.get("country", "").strip()
        current_user.postal_code = request.form.get("postal_code", "").strip()
        db.session.commit()
        flash("Your profile has been updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/loyalty/myAccount/paymentMethods.mi", methods=["GET", "POST"])
@app.route("/account/payments", methods=["GET", "POST"])
@login_required
def account_payments():
    if request.method == "POST":
        card_type = request.form.get("card_type", "Visa")
        number = re.sub(r"\D", "", request.form.get("card_number", ""))
        if len(number) < 15 or len(number) > 16:
            flash("Please enter a valid card number (15 or 16 digits).", "error")
        else:
            holder = request.form.get("holder_name", "").strip()
            exp_month = parse_int(request.form.get("exp_month"))
            exp_year = parse_int(request.form.get("exp_year"))
            if (not holder or not exp_month or not exp_year or not 1 <= exp_month <= 12
                    or (exp_year, exp_month) < (MIRROR_REFERENCE_DATE.year, MIRROR_REFERENCE_DATE.month)
                    or exp_year > MIRROR_REFERENCE_DATE.year + 20):
                flash("Please complete the cardholder name and expiration date.", "error")
            else:
                db.session.add(PaymentMethod(
                    user_id=current_user.id,
                    card_type=card_type,
                    last_four=number[-4:],
                    holder_name=holder,
                    exp_month=exp_month,
                    exp_year=exp_year,
                    is_default=not current_user.payment_methods,
                    added_on=date(2026, 9, 20),
                ))
                db.session.commit()
                flash(f"Your {card_type} ending in {number[-4:]} has been added.", "success")
                return redirect(url_for("account_payments"))
    return render_template("account_payments.html")


@app.route("/loyalty/myAccount/paymentMethods/remove/<int:pm_id>", methods=["POST"])
@app.route("/account/payments/<int:pm_id>/delete", methods=["POST"])
@login_required
def payment_delete(pm_id):
    pm = PaymentMethod.query.filter_by(id=pm_id, user_id=current_user.id).first_or_404()
    was_default = pm.is_default
    db.session.delete(pm)
    db.session.flush()
    if was_default:
        replacement = PaymentMethod.query.filter_by(user_id=current_user.id).order_by(PaymentMethod.id).first()
        if replacement:
            replacement.is_default = True
    db.session.commit()
    flash("Payment method removed.", "success")
    return redirect(url_for("account_payments"))


@app.route("/loyalty/myAccount/savedHotels.mi")
@app.route("/account/saved")
@login_required
def account_saved():
    favs = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.saved_on.desc(), Favorite.id).all()
    return render_template("account_saved.html", favorites=favs)


@app.route("/saved/add/<int:hotel_id>", methods=["POST"])
@login_required
def saved_add(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    existing = Favorite.query.filter_by(user_id=current_user.id, hotel_id=hotel.id).first()
    if not existing:
        db.session.add(Favorite(user_id=current_user.id, hotel_id=hotel.id, saved_on=date(2026, 9, 21)))
        db.session.commit()
        flash(f"{hotel.name} has been saved to your list.", "success")
    return redirect(safe_return(request.form.get("next") or request.referrer, url_for("account_saved")))


@app.route("/saved/remove/<int:hotel_id>", methods=["POST"])
@login_required
def saved_remove(hotel_id):
    fav = Favorite.query.filter_by(user_id=current_user.id, hotel_id=hotel_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash("Hotel removed from your saved list.", "success")
    return redirect(safe_return(request.form.get("next") or request.referrer, url_for("account_saved")))


# =====================================================================
# MARKETING PAGES
# =====================================================================

@app.route("/")
@app.route("/default.mi")
def index():
    destinations = Destination.query.order_by(Destination.hotel_count.desc()).limit(12).all()
    offers = Offer.query.order_by(Offer.site_order).limit(6).all()
    return render_template("index.html", destinations=destinations, offers=offers)


@app.route("/offers.mi")
def offers():
    all_offers = Offer.query.order_by(Offer.site_order).all()
    return render_template("offers.html", offers=all_offers)


@app.route("/brands.mi")
def brands():
    categories = ["luxury", "distinctive", "premium", "select", "longer_stays", "collections"]
    by_cat = []
    for cat in categories:
        members = Brand.query.filter_by(category=cat).order_by(Brand.site_order).all()
        if members:
            by_cat.append((cat, members))
    return render_template("brands.html", groups=by_cat)


@app.route("/loyalty.mi")
def loyalty():
    return render_template("loyalty.html")


@app.route("/credit-cards.mi")
def credit_cards():
    return render_template("credit_cards.html")


@app.route("/careers.mi")
def careers():
    return render_template("careers.html")


@app.route("/about/privacy.mi")
def privacy():
    return render_template("privacy.html")


@app.route("/about/terms-of-use.mi")
def terms_of_use():
    return render_template("terms.html")


@app.route("/help/global-phone-reservation-numbers.mi")
def global_reservation_numbers():
    help_doc = json.loads(db.session.get(SiteContent, "help_numbers").content)
    return render_template("help_numbers.html",
                           brand_lines=help_doc["brand_lines"],
                           country_rows=help_doc["country_rows"])


@app.route("/en-us/resorts.mi")
def resorts():
    """Resort, beach and island escapes in the catalog (name-matched, the
    upstream resorts page's route shape)."""
    keywords = ("Resort", "Beach", "Oceanside", "Island")
    resorts = (Hotel.query.filter(Hotel.is_bookable.is_(True))
               .filter(or_(*[Hotel.name.ilike(f"%{k}%") for k in keywords]))
               .order_by(Hotel.city, Hotel.name).all())
    groups = []
    by_city = {}
    for h in resorts:
        by_city.setdefault(h.city, []).append(h)
    for city in sorted(by_city):
        groups.append({"city": city, "hotels": by_city[city]})
    return render_template("resorts.html", groups=groups,
                           reference_date=MIRROR_REFERENCE_DATE)


@app.route("/en-us/destinations/united-states.mi")
def united_states_destinations():
    """US destinations index: every United States destination guide grouped by
    state (the utility-bar 'English' link lands here)."""
    dests = (Destination.query.filter_by(country_code="US")
             .order_by(Destination.state, Destination.city).all())
    by_state = []
    seen = {}
    for d in dests:
        seen.setdefault(d.state or d.country, []).append(d)
    for state in sorted(seen):
        by_state.append((state, seen[state]))
    return render_template("us_destinations.html", states=by_state)


@app.route("/en-us/destinations/<path:region>.mi")
def destination_page(region):
    dest = Destination.query.filter_by(region_path=region).first_or_404()
    hotels = Hotel.query.filter_by(destination_id=dest.id).order_by(Hotel.marsha).all()
    return render_template("destination.html", destination=dest, hotels=hotels)


# =====================================================================
# SEARCH
# =====================================================================

@app.route("/search/findHotels.mi")
def search_results():
    destination = request.args.get("destinationAddress", "") or request.args.get("destination", "")
    destination = destination.strip() or request.args.get("destinationAddress.city", "")
    from_date = parse_date(request.args.get("fromDate")) or default_dates()[0]
    to_date = parse_date(request.args.get("toDate")) or default_dates()[1]
    nights = max((to_date - from_date).days, 1)
    adults = parse_int(request.args.get("numAdultsPerRoom"), 1) or 1
    rooms = parse_int(request.args.get("roomCount"), 1) or 1
    use_points = str(request.args.get("useRewardsPoints", "false")).lower() == "true"

    # filter params
    brand_code = request.args.get("brand")
    max_price = parse_int(request.args.get("maxPrice"))
    min_rating = request.args.get("minRating")
    amenity = request.args.get("amenity")
    sort = request.args.get("sortBy", "recommended")

    hotels = Hotel.query
    matched_dest = None
    if destination:
        dest_candidates = []
        stripped = destination.strip()
        # the hero form's own datalist suggests "<City>, <State>" — try the
        # exact string, then the city-only part, so the suggested formats and
        # bare city names all resolve to the destination page's hotels.
        parts = [p.strip() for p in stripped.split(",") if p.strip()]
        for candidate in ([stripped] + parts[:1] + parts):
            matched_dest = Destination.query.filter(
                or_(func.lower(Destination.city) == candidate.lower(),
                    func.lower(Destination.destination_name) == candidate.lower(),
                    func.lower(Destination.slug) == candidate.lower().replace(" ", "-"))
            ).first()
            if matched_dest and matched_dest not in dest_candidates:
                dest_candidates.append(matched_dest)
            if matched_dest:
                break
        if matched_dest:
            hotels = hotels.filter_by(destination_id=matched_dest.id)
        else:
            candidates = scored_hotel_search(destination, Hotel.query)
            if not candidates:
                return render_template("search_results.html",
                                       destination=destination, results=[],
                                       matched_destination=None, total=0,
                                       from_date=from_date, to_date=to_date,
                                       nights=nights, adults=adults, rooms=rooms,
                                       use_points=use_points, brand_code=None,
                                       max_price=None, min_rating=None,
                                       amenity=None, sort="recommended",
                                       all_brands=Brand.query.order_by(Brand.site_order).all())
            hotels = hotels.filter(Hotel.id.in_([h.id for h in candidates]))
    hotels = hotels.filter(Hotel.is_bookable.is_(True))

    if brand_code:
        brand = Brand.query.filter_by(code=brand_code.upper()).first()
        hotels = hotels.filter(Hotel.brand_id == brand.id) if brand else hotels.filter(Hotel.id == -1)
    if max_price:
        if use_points:
            hotels = hotels.filter(Hotel.points_rate <= max_price)
        else:
            hotels = hotels.filter(Hotel.base_rate <= max_price)
    if min_rating:
        try:
            hotels = hotels.filter(Hotel.rating_avg >= float(min_rating))
        except ValueError:
            pass
    rows = hotels.all()
    if amenity:
        # Match amenity words, not substrings such as Spa inside Meeting Space.
        pattern = re.compile(r"\b" + re.escape(amenity) + r"\b", re.IGNORECASE)
        rows = [hotel for hotel in rows if any(pattern.search(value) for value in hotel.amenity_list)]

    if sort == "price":
        rows = sorted(rows, key=lambda h: ((h.points_rate if use_points else h.base_rate) or 10 ** 9, h.name))
    elif sort == "rating":
        rows = sorted(rows, key=lambda h: (-(h.rating_avg or 0), h.name))
    elif sort == "distance":
        rows = sorted(rows, key=lambda h: (h.distance_miles if h.distance_miles is not None else 999, h.name))
    else:
        rows = sorted(rows, key=lambda h: h.name)

    all_brands = Brand.query.order_by(Brand.site_order).all()
    return render_template("search_results.html",
                           destination=destination, results=rows,
                           matched_destination=matched_dest,
                           total=len(rows), from_date=from_date, to_date=to_date,
                           nights=nights, adults=adults, rooms=rooms,
                           use_points=use_points, brand_code=brand_code,
                           max_price=max_price, min_rating=min_rating,
                           amenity=amenity, sort=sort, all_brands=all_brands)


@app.route("/search/availabilityCalendar.mi")
@app.route("/search/destinationFinder.mi")
def search_redirect_stub():
    return redirect(url_for("search_results"))


# =====================================================================
# HOTEL DETAIL
# =====================================================================

def _hotel_or_404(ident):
    """Resolve a '<marsha>-<slug>' hotel identifier (the marsha code is the
    first 5 characters before the first dash, matching the live URL scheme)."""
    parts = ident.split("-", 1)
    if len(parts) != 2:
        abort(404)
    marsha, slug = parts
    hotel = Hotel.query.filter(func.lower(Hotel.marsha) == marsha.lower()).first()
    if hotel is None or hotel.slug != slug:
        abort(404)
    return hotel


@app.route("/en-us/hotels/<hotel_ident>/overview/", endpoint="hotel_overview")
@app.route("/en-us/hotels/<hotel_ident>/", endpoint="hotel_overview")
def hotel_overview(hotel_ident):
    hotel = _hotel_or_404(hotel_ident)
    rooms = hotel.room_types
    dist = _rating_distribution(hotel)
    return render_template("hotel_overview.html", hotel=hotel,
                           rooms=rooms, dist=dist,
                           amenity_groups=amenity_groups(hotel))


@app.route("/en-us/hotels/<hotel_ident>/rooms/")
def hotel_rooms(hotel_ident):
    hotel = _hotel_or_404(hotel_ident)
    from_date = parse_date(request.args.get("fromDate")) or default_dates()[0]
    to_date = parse_date(request.args.get("toDate")) or default_dates()[1]
    nights = max((to_date - from_date).days, 1)
    rooms_count = parse_int(request.args.get("rooms"), 1) or 1
    adults = parse_int(request.args.get("adults"), 1) or 1
    return render_template("hotel_rooms.html", hotel=hotel,
                           rooms=hotel.room_types,
                           from_date=from_date, to_date=to_date, nights=nights,
                           rooms_count=rooms_count, adults=adults)


@app.route("/en-us/hotels/<hotel_ident>/reviews/")
def hotel_reviews(hotel_ident):
    hotel = _hotel_or_404(hotel_ident)
    dist = _rating_distribution(hotel)
    subs = json.loads(hotel.sub_ratings or "{}")
    stars = parse_int(request.args.get("stars"))
    page = max(parse_int(request.args.get("page"), 1) or 1, 1)
    reviews = hotel.reviews
    if stars:
        reviews = [r for r in reviews if r.rating == stars]
    per_page = 10
    total = len(reviews)
    reviews = reviews[(page - 1) * per_page: page * per_page]
    return render_template("hotel_reviews.html", hotel=hotel, dist=dist,
                           subs=subs, reviews=reviews, stars=stars,
                           page=page, total=total, per_page=per_page)


@app.route("/en-us/hotels/<hotel_ident>/photos/")
def hotel_photos(hotel_ident):
    hotel = _hotel_or_404(hotel_ident)
    return render_template("hotel_photos.html", hotel=hotel, images=hotel.images)


# =====================================================================
# RESERVATION FLOW
# =====================================================================

@app.route("/reservation/availabilitySearch.mi")
def availability_search():
    code = request.args.get("propertyCode", "")
    hotel = Hotel.query.filter(func.lower(Hotel.marsha) == code.lower()).first_or_404()
    from_date = parse_date(request.args.get("fromDate")) or default_dates()[0]
    to_date = parse_date(request.args.get("toDate")) or default_dates()[1]
    nights = max((to_date - from_date).days, 1)
    adults = parse_int(request.args.get("numberOfAdults"), 1) or 1
    rooms = parse_int(request.args.get("numberOfRooms"), 1) or 1
    return render_template("availability.html", hotel=hotel, rooms=hotel.room_types,
                           from_date=from_date, to_date=to_date, nights=nights,
                           adults=adults, rooms_count=rooms)


@app.route("/reservation/reservationGateway.mi", methods=["GET", "POST"])
def reservation_gateway():
    code = request.args.get("propertyCode") or request.form.get("propertyCode")
    room_id = parse_int(request.args.get("roomId") or request.form.get("roomId"))
    hotel = Hotel.query.filter(func.lower(Hotel.marsha) == (code or "").lower()).first_or_404()
    room = RoomType.query.filter_by(id=room_id, hotel_id=hotel.id).first_or_404()
    from_date = parse_date(request.args.get("fromDate") or request.form.get("fromDate")) or default_dates()[0]
    to_date = parse_date(request.args.get("toDate") or request.form.get("toDate")) or default_dates()[1]
    nights = max((to_date - from_date).days, 1)
    rooms_count = parse_int(request.args.get("rooms") or request.form.get("rooms"), 1) or 1
    adults = parse_int(request.args.get("adults") or request.form.get("adults"), 1) or 1
    rate_option = request.form.get("rate_option") or request.args.get("rateOption") or "cash"
    if rate_option not in ("cash", "points"):
        rate_option = "cash"
    total_cash = room.base_rate * nights * rooms_count
    total_points = (room.points_rate or 0) * nights * rooms_count
    total = total_cash
    member_points = current_user.points if current_user.is_authenticated else 0

    if request.method == "POST":
        guest_first = request.form.get("guest_first_name", "").strip()
        guest_last = request.form.get("guest_last_name", "").strip()
        guest_email = request.form.get("guest_email", "").strip()
        errors = []
        if not (guest_first and guest_last):
            errors.append("Please enter the guest's first and last name.")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", guest_email):
            errors.append("Please enter a valid email address.")
        if not hotel.is_bookable:
            errors.append("This hotel is not available for reservations.")
        if not 1 <= rooms_count <= 3 or not 1 <= adults <= room.max_occupancy:
            errors.append("Choose 1 to 3 rooms and a guest count within the room capacity.")
        if from_date < MIRROR_REFERENCE_DATE:
            errors.append("Choose a check-in date on or after the catalog date.")
        if any(not parse_date(request.form.get(k)) for k in ("fromDate", "toDate")):
            errors.append("Enter valid check-in and check-out dates.")
        if rate_option == "points":
            if not room.points_rate or room.points_rate <= 0:
                errors.append("This room does not offer a points rate.")
            if not current_user.is_authenticated:
                errors.append("Please sign in to your Marriott Bonvoy account to redeem points.")
            elif member_points < total_points:
                errors.append(f"This redemption needs {total_points:,} points, but your account "
                              f"has {member_points:,}. Choose the cash rate or a shorter stay.")
        else:
            card_number = re.sub(r"\D", "", request.form.get("card_number", ""))
            if len(card_number) < 15 or len(card_number) > 16:
                errors.append("Please enter a valid credit card number (15 or 16 digits).")
            exp_month = parse_int(request.form.get("exp_month"))
            exp_year = parse_int(request.form.get("exp_year"))
            if (not exp_month or not exp_year or not 1 <= exp_month <= 12
                    or (exp_year, exp_month) < (MIRROR_REFERENCE_DATE.year, MIRROR_REFERENCE_DATE.month)
                    or exp_year > MIRROR_REFERENCE_DATE.year + 20):
                errors.append("Please enter the card's expiration date.")
        if (to_date - from_date).days <= 0:
            errors.append("Your check-out date must be after your check-in date.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            conf = confirmation_number()
            redeem = total_points if rate_option == "points" else 0
            resv = Reservation(
                confirmation_number=conf,
                user_id=current_user.id if current_user.is_authenticated else None,
                hotel_id=hotel.id,
                room_type_id=room.id,
                guest_first_name=guest_first,
                guest_last_name=guest_last,
                guest_email=guest_email,
                checkin=from_date,
                checkout=to_date,
                adults=adults,
                rooms=rooms_count,
                nightly_rate=room.base_rate,
                total_rate=total_points if rate_option == "points" else total_cash,
                points_redeemed=redeem,
                status="confirmed",
                special_requests=request.form.get("special_requests", "").strip(),
            )
            db.session.add(resv)
            if rate_option == "points":
                debited = User.query.filter(User.id == current_user.id, User.points >= redeem).update(
                    {"points": User.points - redeem}, synchronize_session=False)
                if not debited:
                    db.session.rollback()
                    flash("Your points balance changed. Please choose another rate.", "error")
                    return redirect(request.url)
            db.session.commit()
            session["reservation_access"] = list(dict.fromkeys(session.get("reservation_access", []) + [conf]))[-30:]
            return redirect(url_for("reservation_confirmation", confirmation_number=conf))

    return render_template("reservation_gateway.html", hotel=hotel, room=room,
                           from_date=from_date, to_date=to_date, nights=nights,
                           adults=adults, rooms_count=rooms_count, total=total,
                           total_cash=total_cash, total_points=total_points,
                           rate_option=rate_option, member_points=member_points)


@app.route("/reservation/confirmation.mi")
def reservation_confirmation():
    conf = (request.args.get("confirmationNumber")
            or request.args.get("confirmation_number", ""))
    resv = Reservation.query.filter_by(confirmation_number=conf).first_or_404()
    if not ((current_user.is_authenticated and resv.user_id == current_user.id)
            or conf in session.get("reservation_access", [])):
        abort(404)
    return render_template("reservation_confirmation.html", reservation=resv)


@app.route("/reservation/lookupReservation.mi", methods=["GET", "POST"])
def lookup_reservation():
    reservation = None
    if request.method == "GET":
        conf = (request.args.get("confirmationNumber")
                or request.args.get("confirmation_number", "")).strip().upper()
        last_name = (request.args.get("lastName")
                     or request.args.get("last_name", "")).strip()
    else:
        conf = request.form.get("confirmationNumber", "").strip().upper()
        last_name = request.form.get("lastName", "").strip()
    if conf and last_name:
        reservation = Reservation.query.filter(
            func.upper(Reservation.confirmation_number) == conf).first()
        if reservation is None or reservation.guest_last_name.lower() != last_name.lower():
            reservation = None
            flash("We couldn't find a reservation with that confirmation number and last name.", "error")
    return render_template("lookup_reservation.html", reservation=reservation)


@app.route("/reservation/cancel.mi", methods=["POST"])
def cancel_reservation():
    conf = request.form.get("confirmationNumber", "").strip().upper()
    last_name = request.form.get("lastName", "").strip().lower()
    resv = Reservation.query.filter(
        func.upper(Reservation.confirmation_number) == conf).first()
    if resv is None or resv.guest_last_name.lower() != last_name:
        flash("We couldn't find a reservation with that confirmation number and last name.", "error")
        return redirect(url_for("lookup_reservation"))
    # Atomically claim the transition so repeated or concurrent submissions
    # cannot refund a redemption more than once.
    changed = Reservation.query.filter_by(id=resv.id, status="confirmed").update(
        {"status": "canceled"}, synchronize_session=False)
    if changed and resv.points_redeemed and resv.user_id:
        owner = db.session.get(User, resv.user_id)
        if owner:
            User.query.filter_by(id=owner.id).update(
                {"points": User.points + resv.points_redeemed}, synchronize_session=False)
    db.session.commit()
    flash(f"Reservation {resv.confirmation_number} has been canceled.", "success")
    return redirect(url_for("lookup_reservation",
                            confirmationNumber=resv.confirmation_number,
                            lastName=resv.guest_last_name))


@app.route("/loyalty/myAccount/trips")
@login_required
def account_trips():
    return redirect(url_for("account"))


# =====================================================================
# MISC / HEALTH
# =====================================================================

@app.route("/_health")
def health():
    return {"ok": True, "site": "marriott",
            "hotels": Hotel.query.count(),
            "destinations": Destination.query.count(),
            "reviews": Review.query.count()}


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# =====================================================================
# BOOTSTRAP
# =====================================================================

def seed_database():
    if Hotel.query.count() > 0:
        return
    from seed_data import build_seed
    build_seed(db)


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    from seed_data import build_benchmark_users
    build_benchmark_users(db, bcrypt)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
