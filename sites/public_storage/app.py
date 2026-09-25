#!/usr/bin/env python3
"""Public Storage (publicstorage.com) mirror — Flask app.

Functional mirror of https://www.publicstorage.com/ built for the WebHarbor
offline benchmark environment: the zip/city storage search with type + size
filters and Recommended/Closest/Lowest-Price sorts, facility detail pages
(full unit lists with in-store vs online pricing, features, promotions,
urgency flags, amenities, hours, reviews), the free "Hold Now" reservation
flow (hold form → confirmation code → lookup → cancel), the account domain
(register / log in / profile / reservations), the tenant bill-pay flow, the
size guide hub + per-size FAQ pages, the storage-type landing pages, the
storage-solutions pages, the blog, and the help center.

All catalog rows (facilities, units, prices, reviews, hours, amenities)
come from the tracked source snapshot under source_data/ captured from the
live site; see provenance.json.
"""
import json
import math
import os
import random
import re
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, abort, jsonify,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user,
)
from flask_bcrypt import Bcrypt

BASE_DIR = Path(__file__).parent
INSTANCE = BASE_DIR / "instance"
INSTANCE.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "publicstorage-mirror-dev-key"
# The container always runs against instance/public_storage.db; the test
# suite points this at a scratch copy so its write paths never touch the seed.
_DB_PATH = os.environ.get("WEBHARBOR_MIRROR_DB") or str(INSTANCE / "public_storage.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{_DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "sign_elease"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "error"

# The mirror runs against a frozen catalog snapshot; availability windows and
# any relative wording are pinned to this capture date.
MIRROR_REFERENCE_DATE = date(2026, 9, 24)

PS_PHONE = "800-688-8057"

STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "it", "by", "with", "near", "me", "storage", "self",
}

SIZE_FILTERS = [
    ("", "All Sizes"),
    ("Small", "Small"),
    ("Medium", "Medium"),
    ("Large", "Large"),
    ("Up to 20'", "Up to 20'"),
    ("Up to 35'", "Up to 35'"),
    ("Up to 50'", "Up to 50'"),
]

SOLUTION_PAGES = {
    "decluttering": "Decluttering",
    "living-abroad": "Living Abroad",
    "military-storage": "Military Storage",
    "seasonal-storage": "Seasonal Storage",
    "security-features": "Security Features",
    "storage-deals": "Storage Deals",
    "storage-faqs": "Storage FAQs",
    "storage-for-life-transitions": "Life Transitions",
    "storage-lockers": "Storage Lockers",
}

STORAGE_TYPE_PAGES = [
    ("self-storage", "Self Storage"),
    ("self-storage/24-hour-storage", "24 Hour Self Storage"),
    ("business-storage", "Business Storage"),
    ("vehicle-car-rv-storage", "Vehicle & RV Storage"),
    ("boat-storage", "Boat Storage"),
    ("climate-controlled-storage", "Climate Controlled Storage"),
    ("self-storage/drive-up-storage", "Drive Up Access Storage"),
    ("indoor-storage", "Indoor Storage"),
]


# =====================================================================
# MODELS
# =====================================================================

class Facility(db.Model):
    __tablename__ = "facilities"
    id = db.Column(db.Integer, primary_key=True)          # real upstream property id
    slug_state = db.Column(db.String(4), nullable=False, index=True)
    slug_city = db.Column(db.String(64), nullable=False, index=True)
    address = db.Column(db.String(128), nullable=False)
    city = db.Column(db.String(64), nullable=False, index=True)
    state = db.Column(db.String(4), nullable=False, index=True)
    zip = db.Column(db.String(12), nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    rating = db.Column(db.Float, nullable=False)
    review_count = db.Column(db.Integer, nullable=False)
    badges = db.Column(db.Text, nullable=False, default="[]")
    office_hours = db.Column(db.Text, nullable=False, default="{}")
    access_hours = db.Column(db.Text, nullable=False, default="{}")
    amenities = db.Column(db.Text, nullable=False, default="[]")
    photos = db.Column(db.Text, nullable=False, default="[]")
    featured = db.Column(db.Boolean, nullable=False, default=False)

    units = db.relationship("Unit", backref="facility", lazy=True,
                            order_by="Unit.web_price")
    reviews = db.relationship("Review", backref="facility", lazy=True)

    @property
    def badge_list(self):
        return json.loads(self.badges)

    @property
    def amenity_list(self):
        return json.loads(self.amenities)

    @property
    def photo_list(self):
        return json.loads(self.photos)

    @property
    def office_hours_map(self):
        return json.loads(self.office_hours) if self.office_hours else {}

    @property
    def access_hours_map(self):
        return json.loads(self.access_hours) if self.access_hours else {}

    @property
    def city_slug(self):
        return f"self-storage-{self.slug_state}-{self.slug_city}"

    @property
    def detail_url(self):
        return f"/{self.city_slug}/{self.id}.html"

    @property
    def city_url(self):
        return f"/{self.city_slug}"

    def distance_miles(self, lat, lng):
        return haversine(lat, lng, self.lat, self.lng)

    def cheapest_unit(self, vehicle=None):
        units = self.units
        if vehicle is not None:
            units = [u for u in units if u.is_vehicle == vehicle]
        return min(units, key=lambda u: u.web_price) if units else None


class Unit(db.Model):
    __tablename__ = "units"
    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.String(16), unique=True, nullable=False, index=True)
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"),
                            nullable=False, index=True)
    category = db.Column(db.String(12), nullable=False)     # Small/Medium/Large/Vehicle
    dims = db.Column(db.String(16), nullable=False)          # 5'x5' / Up to 20'
    features = db.Column(db.Text, nullable=False, default="[]")
    web_price = db.Column(db.Float, nullable=False)
    list_price = db.Column(db.Float, nullable=False)
    min_price = db.Column(db.Float, nullable=False)
    promo = db.Column(db.String(40))
    urgency = db.Column(db.String(20))
    is_vehicle = db.Column(db.Boolean, nullable=False, default=False)

    @property
    def feature_list(self):
        return json.loads(self.features)

    @property
    def savings(self):
        return round(self.list_price - self.web_price, 2)


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"),
                            nullable=False, index=True)
    author = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    date = db.Column(db.String(12), nullable=False)
    body = db.Column(db.Text, nullable=False)


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    phone = db.Column(db.String(24), nullable=False, default="")
    account_number = db.Column(db.String(16), unique=True, nullable=False)

    reservations = db.relationship("Reservation", backref="user", lazy=True)
    rentals = db.relationship("Rental", backref="user", lazy=True)
    saved = db.relationship("SavedFacility", backref="user", lazy=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Reservation(db.Model):
    __tablename__ = "reservations"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"),
                            nullable=False)
    unit_row_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)
    holder_name = db.Column(db.String(120), nullable=False)
    holder_email = db.Column(db.String(120), nullable=False, index=True)
    holder_phone = db.Column(db.String(24), nullable=False, default="")
    move_in_date = db.Column(db.String(12), nullable=False)
    status = db.Column(db.String(12), nullable=False, default="held")
    created_at = db.Column(db.String(12), nullable=False)

    facility = db.relationship("Facility", lazy=True)
    unit = db.relationship("Unit", lazy=True)


class Rental(db.Model):
    """An in-force lease for the bill-pay flow."""
    __tablename__ = "rentals"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"), nullable=False)
    unit_row_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)
    started_on = db.Column(db.String(12), nullable=False)
    monthly_rate = db.Column(db.Float, nullable=False)
    balance_due = db.Column(db.Float, nullable=False)
    next_bill_date = db.Column(db.String(12), nullable=False)
    gate_code = db.Column(db.String(12), nullable=False, default="")

    facility = db.relationship("Facility", lazy=True)
    unit = db.relationship("Unit", lazy=True)


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    rental_id = db.Column(db.Integer, db.ForeignKey("rentals.id"), nullable=False)
    confirmation = db.Column(db.String(20), nullable=False, unique=True)
    amount = db.Column(db.Float, nullable=False)
    card_last4 = db.Column(db.String(4), nullable=False)
    paid_on = db.Column(db.String(12), nullable=False)

    rental = db.relationship("Rental", lazy=True)


class SavedFacility(db.Model):
    __tablename__ = "saved_facilities"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"), nullable=False)

    facility = db.relationship("Facility", lazy=True)


class BlogArticle(db.Model):
    __tablename__ = "blog_articles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    category = db.Column(db.String(40), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    published = db.Column(db.String(12), nullable=False)
    image_path = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)  # JSON list of paragraphs

    @property
    def body_list(self):
        return json.loads(self.body) if self.body else []


class HelpTopic(db.Model):
    __tablename__ = "help_topics"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    label = db.Column(db.String(120), nullable=False)
    summary = db.Column(db.Text, nullable=False, default="")
    body = db.Column(db.Text, nullable=False, default="[]")  # JSON paragraphs

    @property
    def body_list(self):
        return json.loads(self.body) if self.body else []


class SizeFaq(db.Model):
    __tablename__ = "size_faqs"
    id = db.Column(db.Integer, primary_key=True)
    page_key = db.Column(db.String(20), nullable=False, index=True)
    question = db.Column(db.String(300), nullable=False)
    answer = db.Column(db.Text, nullable=False)


class FaqEntry(db.Model):
    __tablename__ = "faq_entries"
    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(30), nullable=False, index=True)  # facility:<id> / general
    question = db.Column(db.String(300), nullable=False)
    answer = db.Column(db.Text, nullable=False)


class SiteCopy(db.Model):
    __tablename__ = "site_copy"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)  # JSON


class ZipResult(db.Model):
    """The live site's own zip-search result set: for a searched ZIP, which
    facilities it returns and at what distance (captured upstream)."""
    __tablename__ = "zip_results"
    id = db.Column(db.Integer, primary_key=True)
    zip = db.Column(db.String(8), nullable=False, index=True)
    slug = db.Column(db.String(80), nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"), nullable=False)
    distance = db.Column(db.Float, nullable=False)
    position = db.Column(db.Integer, nullable=False)

    facility = db.relationship("Facility", lazy=True)


# =====================================================================
# HELPERS
# =====================================================================

def haversine(lat1, lng1, lat2, lng2):
    r = 3958.8  # Earth radius in miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    a = min(a, 1.0)
    return 2 * r * math.asin(math.sqrt(a))


def tokenize(query):
    return [t.lower() for t in re.split(r"[^a-z0-9']+", query.lower())
            if t and t not in STOP_WORDS]


def get_copy(key, default=None):
    row = SiteCopy.query.filter_by(key=key).first()
    if row is None:
        return default
    return json.loads(row.value)


def get_copy_json(key, default=None):
    row = SiteCopy.query.filter_by(key=key).first()
    if row is None:
        return default
    return json.loads(row.value)


def format_money(value):
    return f"${value:,.0f}" if float(value).is_integer() else f"${value:,.2f}"


def valid_card(number):
    digits = re.sub(r"\D", "", number or "")
    if len(digits) < 13 or len(digits) > 19 or not digits.isdigit():
        return False
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def card_brand(number):
    digits = re.sub(r"\D", "", number or "")
    if digits.startswith("4"):
        return "Visa"
    if digits[:2] in {"34", "37"}:
        return "American Express"
    if digits[:2] in {str(n) for n in range(51, 56)} or digits[:4] == "6011":
        return "Mastercard"
    if digits.startswith("6"):
        return "Discover"
    return "Card"


def size_matches(unit, size_filter):
    if not size_filter:
        return True
    if size_filter in ("Small", "Medium", "Large"):
        return unit.category == size_filter
    # vehicle length filters: match spaces whose longest side fits the limit
    m = re.match(r"Up to (\d+)'", size_filter)
    if m:
        limit = int(m.group(1))
        if not unit.is_vehicle:
            return False
        dm = re.match(r"Up to (\d+)'", unit.dims)
        if dm:
            return int(dm.group(1)) <= limit
        sides = [float(x) for x in re.findall(r"[\d.]+", unit.dims)]
        if sides:
            return max(sides) <= limit
        return True
    return True


def facility_matches(facility, vehicle_filter, size_filter):
    """Return the facility's units matching the filters (may be empty)."""
    units = facility.units
    if vehicle_filter is not None:
        units = [u for u in units if u.is_vehicle == vehicle_filter]
    if size_filter:
        units = [u for u in units if size_matches(u, size_filter)]
    return units


_ZIP_LOOKUP = None


def zip_lookup():
    """zip -> {'slug', 'facility_ids': [...], 'distances': [...]} from the
    captured upstream zip searches (plain data only; ORM objects are never
    cached across requests), plus a facility-zip geo fallback map."""
    global _ZIP_LOOKUP
    if _ZIP_LOOKUP is None:
        table = {}
        for row in ZipResult.query.order_by(ZipResult.zip, ZipResult.position):
            entry = table.setdefault(
                row.zip, {"slug": row.slug, "facility_ids": [], "distances": {}})
            entry["facility_ids"].append(row.facility_id)
            entry["distances"][row.facility_id] = row.distance
        geo = {}
        for facility in Facility.query.order_by(Facility.id).all():
            geo.setdefault(facility.zip, (facility.lat, facility.lng))
        _ZIP_LOOKUP = {"table": table, "geo": geo}
    return _ZIP_LOOKUP


def search_facilities(location, type_param, size_param, sort):
    """Location search -> list of (facility, matching_units, distance).

    ZIP searches use the live site's own captured result sets (facility
    order + distances). Free-text queries use scored token matching over
    the address / city / state fields. """
    vehicle_filter = None
    if type_param == "IsVehicleUnit":
        vehicle_filter = True
    elif type_param == "IsStorageUnit":
        vehicle_filter = False

    raw = (location or "").strip()
    lookup = zip_lookup()
    candidates = []  # (facility, distance)

    if re.fullmatch(r"\d{5}", raw):
        entry = lookup["table"].get(raw)
        if entry:
            by_id = {f.id: f for f in Facility.query.all()
                     if f.id in set(entry["facility_ids"])}
            candidates = [(by_id[fid], entry["distances"][fid])
                          for fid in entry["facility_ids"] if fid in by_id]
        elif raw in lookup["geo"]:
            origin = lookup["geo"][raw]
            candidates = [(f, f.distance_miles(*origin))
                          for f in Facility.query.all()
                          if f.distance_miles(*origin) <= 25.0]
    else:
        tokens = tokenize(raw)
        if tokens:
            scored = []
            for facility in Facility.query.all():
                text = " ".join([
                    facility.address, facility.city, facility.state, facility.zip,
                    facility.city_slug,
                ]).lower()
                score = sum(1 for t in tokens if t in text)
                if score > 0:
                    scored.append((facility, score))
            if scored:
                # keep only the best-scoring facilities so a "city, state"
                # query does not drag in every facility of the same state
                best = max(s for _, s in scored)
                top = [f for f, s in scored if s == best]
                origin = (
                    sum(f.lat for f in top) / len(top),
                    sum(f.lng for f in top) / len(top),
                )
                candidates = [(f, f.distance_miles(*origin)) for f in top]

    results = []
    for facility, dist in candidates:
        units = facility_matches(facility, vehicle_filter, size_param)
        if not units:
            continue
        results.append((facility, units, dist))

    if sort == "closest":
        results.sort(key=lambda r: (r[2], -r[0].rating))
    elif sort == "price":
        results.sort(key=lambda r: (min(u.web_price for u in r[1]), r[2]))
    else:  # recommended
        # zip searches keep the live site's own captured ordering; text
        # searches fall back to featured, then rating, then distance
        entry = zip_lookup()["table"].get(raw) if re.fullmatch(r"\d{5}", raw) else None
        if entry:
            order = {fid: pos for pos, fid in enumerate(entry["facility_ids"])}
            results.sort(key=lambda r: (order.get(r[0].id, 999), -r[0].rating))
        else:
            results.sort(key=lambda r: (-r[0].featured, -r[0].rating, r[2]))
    return results


def make_reservation_code():
    return f"PS-{secrets.randbelow(9000000) + 1000000}"


def next_bill_date(seed_date):
    d = datetime.strptime(seed_date, "%m/%d/%Y").date()
    nxt = d.replace(day=1) + timedelta(days=32)
    return nxt.replace(day=1).strftime("%m/%d/%Y")


# =====================================================================
# AUTH
# =====================================================================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/lease/sign-elease", methods=["GET", "POST"])
def sign_elease():
    if request.method == "POST":
        email = (request.form.get("loginEmail") or "").strip().lower()
        password = request.form.get("loginPassword") or ""
        user = User.query.filter_by(email=email).first()
        if user is None or not bcrypt.check_password_hash(user.password_hash, password):
            flash("The email or password you entered is incorrect. Please try again.", "error")
            return render_template("login.html"), 401
        login_user(user)
        target = request.args.get("next")
        if target and target.startswith("/"):
            return redirect(target)
        return redirect("/myaccount")
    return render_template("login.html")


@app.route("/myaccount/identity/create-account", methods=["GET", "POST"])
def create_account():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        first = (request.form.get("firstName") or "").strip()
        last = (request.form.get("lastName") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirmPassword") or ""
        errors = []
        if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Please enter a valid email address.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists. Try logging in.")
        if len(first) < 2 or len(last) < 2:
            errors.append("Please enter your first and last name.")
        digits = re.sub(r"\D", "", phone)
        if len(digits) < 10:
            errors.append("Please enter a valid 10-digit phone number.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html"), 400
        user = User(
            username=email.split("@")[0][:40] + str(secrets.randbelow(900) + 100),
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode(),
            first_name=first, last_name=last, phone=phone,
            account_number=f"{secrets.randbelow(900000) + 100000}",
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome to Public Storage! Your account has been created.", "success")
        return redirect("/myaccount")
    return render_template("register.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect("/")


# =====================================================================
# ACCOUNT
# =====================================================================

@app.route("/myaccount")
@login_required
def my_account():
    reservations = (Reservation.query.filter_by(user_id=current_user.id)
                    .order_by(Reservation.created_at.desc()).all())
    rentals = Rental.query.filter_by(user_id=current_user.id).all()
    saved = SavedFacility.query.filter_by(user_id=current_user.id).all()
    return render_template(
        "account.html", reservations=reservations, rentals=rentals,
        saved=[s.facility for s in saved])


@app.route("/myaccount/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        first = (request.form.get("firstName") or "").strip()
        last = (request.form.get("lastName") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        if len(first) >= 2 and len(last) >= 2:
            current_user.first_name = first
            current_user.last_name = last
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 10:
            current_user.phone = phone
        db.session.commit()
        flash("Your account details have been updated.", "success")
        return redirect("/myaccount")
    return render_template("account_edit.html")


@app.route("/myaccount/saved/<int:facility_id>", methods=["POST"])
@login_required
def toggle_saved(facility_id):
    facility = db.session.get(Facility, facility_id)
    if facility is None:
        abort(404)
    row = SavedFacility.query.filter_by(
        user_id=current_user.id, facility_id=facility_id).first()
    if row:
        db.session.delete(row)
        db.session.commit()
        return redirect(request.form.get("next") or facility.detail_url)
    db.session.add(SavedFacility(user_id=current_user.id, facility_id=facility_id))
    db.session.commit()
    return redirect(request.form.get("next") or facility.detail_url)


# =====================================================================
# SEARCH + FACILITY PAGES
# =====================================================================

@app.route("/")
def index():
    nearby = Facility.query.order_by(Facility.rating.desc()).limit(6).all()
    popular_cities = get_copy_json("popular_cities", [])
    return render_template(
        "index.html", nearby=nearby, popular_cities=popular_cities,
        type_pages=STORAGE_TYPE_PAGES)


@app.route("/find-storage")
def find_storage():
    return render_template("find_storage.html", size_filters=SIZE_FILTERS)


@app.route("/self-storage-search")
@app.route("/self-storage-search/<path:slug>")
def self_storage_search(slug=None):
    type_param = request.args.get("type", "")
    size_param = request.args.get("sz", "")
    sort = request.args.get("sort", "recommended")
    if sort not in ("recommended", "closest", "price"):
        sort = "recommended"

    location = (request.args.get("location") or "").strip()
    if slug is not None:
        # live-site slug shapes: <city>-<state> or <city>-<state>-<zip>
        m = re.search(r"-(\d{5})$", slug)
        if m and m.group(1) in zip_lookup()["table"]:
            location = m.group(1)  # a captured zip search
        else:
            location = slug.rsplit("-", 1)[0].replace("-", " ") if "-" in slug else slug

    # The live site lands zip/city searches on /self-storage-search/<slug>;
    # mirror that shape by redirecting param-form searches when the query
    # resolves to a known zip or city.
    if slug is None and location:
        results_probe = search_facilities(location, type_param, size_param, sort)
        if results_probe:
            raw = location.strip()
            if re.fullmatch(r"\d{5}", raw):
                entry = zip_lookup()["table"].get(raw)
                if entry:
                    target_slug = entry["slug"]
                else:
                    head = results_probe[0][0]
                    target_slug = (f"{head.city.lower().replace(' ', '-')}-"
                                   f"{head.state.lower()}-{raw}")
            else:
                head = results_probe[0][0]
                target_slug = (f"{head.city.lower().replace(' ', '-')}-"
                               f"{head.state.lower()}")
            qs = []
            if type_param:
                qs.append(f"type={type_param}")
            if size_param:
                qs.append(f"sz={size_param}")
            if sort != "recommended":
                qs.append(f"sort={sort}")
            suffix = ("?" + "&".join(qs)) if qs else ""
            return redirect(f"/self-storage-search/{target_slug}{suffix}")

    results = search_facilities(location, type_param, size_param, sort)
    cards = []
    for facility, units, dist in results:
        shown = sorted(units, key=lambda u: u.web_price)[:3]
        cards.append({
            "facility": facility, "units": shown, "distance": dist,
            "cheapest": min(u.web_price for u in units),
        })
    return render_template(
        "search_results.html", location=location, cards=cards,
        type_param=type_param, size_param=size_param, sort=sort,
        size_filters=SIZE_FILTERS, total=len(cards))


@app.route("/self-storage-<slug_state>-<slug_city>/<int:facility_id>.html")
def facility_page(slug_state, slug_city, facility_id):
    facility = db.session.get(Facility, facility_id)
    if facility is None:
        abort(404)
    show_units = request.args.get("showUnits", "true") != "false"
    units_by_cat = {"Small": [], "Medium": [], "Large": [],
                    "Vehicle": [], "Parking": []}
    for unit in facility.units:
        units_by_cat.setdefault(unit.category, []).append(unit)
    nearby = (Facility.query
              .filter(Facility.city == facility.city, Facility.id != facility.id)
              .order_by(Facility.rating.desc()).limit(4).all())
    if len(nearby) < 2:
        nearby = (Facility.query
                  .filter(Facility.state == facility.state, Facility.id != facility.id)
                  .order_by(Facility.rating.desc()).limit(4).all())
    reviews = facility.reviews[:5]
    faqs = FaqEntry.query.filter_by(scope=f"facility:{facility.id}").all()
    if not faqs:
        faqs = FaqEntry.query.filter_by(scope="general").all()
    return render_template(
        "facility.html", facility=facility, show_units=show_units,
        units_by_cat=units_by_cat, nearby=nearby, reviews=reviews, faqs=faqs)


@app.route("/self-storage-<slug_state>-<slug_city>")
def city_page(slug_state, slug_city):
    # Werkzeug's greedy regex can mis-split multi-word city slugs
    # (e.g. "los-angeles"); rebuild the full slug and match it directly.
    full_slug = f"self-storage-{slug_state}-{slug_city}"
    groups = {}
    for facility in Facility.query.all():
        groups.setdefault(facility.city_slug, []).append(facility)
    city_rows = groups.get(full_slug, [])
    if not city_rows:
        abort(404)
    city_rows.sort(key=lambda f: f.id)
    city = city_rows[0].city
    state = city_rows[0].state
    all_units = [u for f in city_rows for u in f.units]
    prices = [u.web_price for u in all_units if not u.is_vehicle]
    avg = round(sum(prices) / len(prices)) if prices else None
    cheapest = min(prices) if prices else None
    return render_template(
        "city.html", city=city, state=state, facilities=city_rows,
        avg=avg, cheapest=cheapest, slug_state=slug_state, slug_city=slug_city)


# =====================================================================
# RESERVATION (HOLD) FLOW
# =====================================================================

@app.route("/reservation/hold/<unit_id>", methods=["GET", "POST"])
def hold_unit(unit_id):
    unit = Unit.query.filter_by(unit_id=unit_id).first_or_404()
    facility = unit.facility
    if request.method == "POST":
        name = (request.form.get("holderName") or "").strip()
        email = (request.form.get("holderEmail") or "").strip().lower()
        phone = (request.form.get("holderPhone") or "").strip()
        move_in = (request.form.get("moveInDate") or "").strip()
        errors = []
        if len(name.split()) < 2:
            errors.append("Please enter your first and last name.")
        if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Please enter a valid email address.")
        if len(re.sub(r"\D", "", phone)) < 10:
            errors.append("Please enter a valid 10-digit phone number.")
        try:
            parsed = datetime.strptime(move_in, "%m/%d/%Y").date()
            if parsed < MIRROR_REFERENCE_DATE:
                errors.append("Move-in date cannot be in the past.")
        except ValueError:
            errors.append("Please enter a valid move-in date (MM/DD/YYYY).")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("hold_form.html", unit=unit,
                                   facility=facility), 400
        code = make_reservation_code()
        while Reservation.query.filter_by(code=code).first():
            code = make_reservation_code()
        reservation = Reservation(
            code=code,
            user_id=current_user.id if current_user.is_authenticated else None,
            facility_id=facility.id, unit_row_id=unit.id,
            holder_name=name, holder_email=email, holder_phone=phone,
            move_in_date=move_in,
            status="held",
            created_at=MIRROR_REFERENCE_DATE.strftime("%m/%d/%Y"),
        )
        db.session.add(reservation)
        db.session.commit()
        return redirect(f"/reservation/confirmation/{code}")
    move_in_default = (MIRROR_REFERENCE_DATE + timedelta(days=1)).strftime("%m/%d/%Y")
    return render_template("hold_form.html", unit=unit, facility=facility,
                           move_in_default=move_in_default)


@app.route("/reservation/confirmation/<code>")
def reservation_confirmation(code):
    reservation = Reservation.query.filter_by(code=code).first_or_404()
    return render_template("reservation_confirmation.html",
                           reservation=reservation)


@app.route("/access-reservation", methods=["GET", "POST"])
def access_reservation():
    reservation = None
    code = (request.values.get("code") or "").strip().upper()
    email = (request.values.get("email") or "").strip().lower()
    if code and email:
        reservation = Reservation.query.filter_by(code=code).first()
        if reservation is None or reservation.holder_email.lower() != email:
            flash("We couldn't find a reservation with that code and email. Please check and try again.", "error")
            reservation = None
        else:
            return render_template("reservation_detail.html",
                                   reservation=reservation)
    return render_template("access_reservation.html", code=code, email=email)


@app.route("/reservation/cancel/<code>", methods=["POST"])
def cancel_reservation(code):
    reservation = Reservation.query.filter_by(code=code).first_or_404()
    email = (request.form.get("email") or "").strip().lower()
    if email and email != reservation.holder_email.lower():
        abort(403)
    reservation.status = "cancelled"
    db.session.commit()
    flash("Your reservation has been cancelled.", "success")
    if current_user.is_authenticated and reservation.user_id == current_user.id:
        return redirect("/myaccount")
    return redirect("/access-reservation")


# =====================================================================
# BILL PAY
# =====================================================================

@app.route("/simplified/bill-pay/login", methods=["GET", "POST"])
def bill_pay_login():
    if request.method == "POST":
        account = (request.form.get("accountNumber") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        rental = None
        if user and account == user.account_number:
            rental = Rental.query.filter_by(user_id=user.id).first()
        if rental is None:
            flash("We couldn't find an account with that number and email.", "error")
            return render_template("bill_pay_login.html"), 401
        session["bill_pay_user"] = user.id
        return redirect("/simplified/bill-pay")
    return render_template("bill_pay_login.html")


@app.route("/simplified/bill-pay", methods=["GET", "POST"])
def bill_pay():
    user_id = session.get("bill_pay_user")
    if not user_id:
        return redirect("/simplified/bill-pay/login")
    user = db.session.get(User, user_id)
    rental = Rental.query.filter_by(user_id=user_id).first()
    if rental is None:
        abort(404)
    if request.method == "POST":
        card = request.form.get("cardNumber") or ""
        expiry = request.form.get("expiry") or ""
        cvv = request.form.get("cvv") or ""
        amount_raw = request.form.get("amount") or ""
        errors = []
        if not valid_card(card):
            errors.append("Please enter a valid card number.")
        digits = re.sub(r"\D", "", cvv)
        if len(digits) not in (3, 4):
            errors.append("Please enter a valid 3 or 4-digit security code.")
        exp_match = re.match(r"^(\d{2})\s*/\s*(\d{2,4})$", expiry.strip())
        if not exp_match:
            errors.append("Please enter a valid expiration date (MM/YY).")
        else:
            mm = int(exp_match.group(1))
            yy = int(exp_match.group(2))
            yy = 2000 + yy if yy < 100 else yy
            if not 1 <= mm <= 12:
                errors.append("Expiration month must be between 01 and 12.")
            elif (yy, mm) < (MIRROR_REFERENCE_DATE.year, MIRROR_REFERENCE_DATE.month):
                errors.append("This card has expired.")
        try:
            amount = round(float(amount_raw.replace("$", "")), 2)
        except ValueError:
            amount = None
            errors.append("Please enter a valid payment amount.")
        if amount is not None and amount <= 0:
            errors.append("Payment amount must be greater than zero.")
        if amount is not None and amount > rental.balance_due + 0.01:
            errors.append("Payment amount cannot exceed your current balance.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("bill_pay.html", rental=rental), 400
        confirmation = f"PS-PAY-{secrets.randbelow(900000) + 100000}"
        payment = Payment(
            rental_id=rental.id, confirmation=confirmation,
            amount=amount, card_last4=re.sub(r"\D", "", card)[-4:],
            paid_on=MIRROR_REFERENCE_DATE.strftime("%m/%d/%Y"))
        db.session.add(payment)
        rental.balance_due = round(rental.balance_due - amount, 2)
        db.session.commit()
        return render_template("bill_pay_receipt.html", payment=payment,
                               rental=rental)
    return render_template("bill_pay.html", rental=rental)


# =====================================================================
# CONTENT PAGES
# =====================================================================

@app.route("/size-guide")
def size_guide():
    return render_template("size_guide.html",
                           size_cards=get_copy_json("size_cards", []),
                           chart=get_copy_json("comparison_chart", []),
                           tips=get_copy_json("size_tips", []))


SIZE_PAGE_ROUTES = {
    "locker-storage-unit": "sg_locker",
    "5x5-storage-unit": "sg_5x5",
    "5x10-storage-unit": "sg_5x10",
    "5x15-storage-unit": "sg_5x15",
    "10x10-storage-unit": "sg_10x10",
    "10x15-storage-unit": "sg_10x15",
    "10x20-storage-unit": "sg_10x20",
    "10x25-storage-unit": "sg_10x25",
    "vehicle-storage-unit-20-feet": "sg_veh20",
    "vehicle-storage-unit-35-feet": "sg_veh35",
    "vehicle-storage-unit-50-feet": "sg_veh50",
}


SIZE_PAGE_CARDS = {
    "locker-storage-unit": "lockers",
    "5x5-storage-unit": "5x5",
    "5x10-storage-unit": "5x10",
    "5x15-storage-unit": "5x15",
    "10x10-storage-unit": "10x10",
    "10x15-storage-unit": "10x15",
    "10x20-storage-unit": "10x20",
    "10x25-storage-unit": "10x25",
    "vehicle-storage-unit-20-feet": "veh20",
    "vehicle-storage-unit-35-feet": "veh35",
    "vehicle-storage-unit-50-feet": "veh50",
}


@app.route("/size-guide/<slug1>/<slug2>.html")
def size_faq_page(slug1, slug2=None):
    slug = slug1
    key = SIZE_PAGE_ROUTES.get(slug)
    if key is None:
        abort(404)
    faqs = SizeFaq.query.filter_by(page_key=key).order_by(SizeFaq.id).all()
    card_key = SIZE_PAGE_CARDS.get(slug)
    card = next((c for c in get_copy_json("size_cards", [])
                 if c.get("key") == card_key), None)
    return render_template("size_faq.html", slug=slug, faqs=faqs, card=card)


@app.route("/<path:slug>")
def storage_type_page(slug):
    if slug not in {s for s, _ in STORAGE_TYPE_PAGES}:
        abort(404)
    key_map = {
        "self-storage": "self_storage",
        "self-storage/24-hour-storage": "24hr",
        "self-storage/drive-up-storage": "driveup",
        "business-storage": "business",
        "vehicle-car-rv-storage": "vehicle",
        "boat-storage": "boat",
        "climate-controlled-storage": "climate",
        "indoor-storage": "indoor",
    }
    page = get_copy_json(f"type_page:{key_map[slug]}")
    if page is None:
        abort(404)
    return render_template("type_page.html", page=page, slug=slug)


@app.route("/storage-solutions/<slug>")
def solution_page(slug):
    key = {
        "decluttering": "decluttering",
        "living-abroad": "abroad",
        "military-storage": "military",
        "seasonal-storage": "seasonal",
        "security-features": "security",
        "storage-deals": "deals",
        "storage-faqs": "faqs",
        "storage-for-life-transitions": "transitions",
        "storage-lockers": "lockers",
    }.get(slug)
    if key is None:
        abort(404)
    page = get_copy_json(f"solution:{key}")
    if page is None:
        abort(404)
    return render_template("solution.html", page=page, slug=slug)


@app.route("/blog")
def blog_index():
    cats = db.session.query(BlogArticle.category).distinct().all()
    return render_template("blog_index.html",
                           categories=sorted(c[0] for c in cats))


@app.route("/blog/<category>")
def blog_category(category):
    articles = (BlogArticle.query.filter_by(category=category)
                .order_by(BlogArticle.published.desc()).all())
    if not articles:
        abort(404)
    return render_template("blog_category.html", category=category,
                           articles=articles)


@app.route("/blog/<category>/<slug>.html")
def blog_article(category, slug):
    article = BlogArticle.query.filter_by(slug=slug).first_or_404()
    return render_template("blog_article.html", article=article)


@app.route("/help/")
@app.route("/help")
def help_home():
    topics = HelpTopic.query.order_by(HelpTopic.id).all()
    return render_template("help_home.html", topics=topics)


@app.route("/help/<slug>")
def help_topic(slug):
    topic = HelpTopic.query.filter_by(slug=slug).first_or_404()
    return render_template("help_topic.html", topic=topic)


@app.route("/why-public-storage.html")
def why_public_storage():
    return render_template("why_ps.html")


@app.route("/our-story/our-story.html")
def our_story():
    return render_template("our_story.html")


@app.route("/contact-us/contact-us.html")
def contact_us():
    return render_template("contact_us.html")


@app.route("/_health")
def health():
    """Lightweight JSON health probe (also used by the container checks)."""
    try:
        counts = {
            "facilities": Facility.query.count(),
            "units": Unit.query.count(),
            "reviews": Review.query.count(),
            "users": User.query.count(),
            "reservations": Reservation.query.count(),
            "blog_articles": BlogArticle.query.count(),
        }
        return jsonify({"ok": True, "site": "public_storage", **counts})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)[:200]}), 500


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


# =====================================================================
# BOOTSTRAP
# =====================================================================

def seed_database():
    if Facility.query.count() > 0:
        return
    from seed_data import build_seed
    build_seed(db)


def seed_benchmark_users():
    from seed_data import build_benchmark_users
    build_benchmark_users(db, bcrypt)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "40126")))
