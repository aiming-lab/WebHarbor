"""Carnival Cruise Line mirror — Flask app.

Mirrors www.carnival.com: cruise search with filters, itinerary detail pages,
multi-step booking, fleet pages, destinations, deals, shore excursions,
account/profile, and Manage My Cruises. All catalog data (itineraries,
sailings, ports, ships, excursions) comes from the committed scrape-derived
literals (_seed_*.py) captured from the upstream site on 2026-09-22.
"""
from __future__ import annotations

import os
import re
import secrets
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Reference date pinned so seeded dates/prices never drift with wall clock.
MIRROR_REFERENCE_DATE = datetime(2026, 9, 22, 12, 0, 0)

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR}/instance/carnival_cruise.db"
app.config["SECRET_KEY"] = "webharbor-carnival-cruise-dev-key"
app.config["JSON_SORT_KEYS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# ---------------------------------------------------------------- models

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    phone = db.Column(db.String(30), default="")
    address1 = db.Column(db.String(120), default="")
    address2 = db.Column(db.String(60), default="")
    city = db.Column(db.String(60), default="")
    state = db.Column(db.String(20), default="")
    zip_code = db.Column(db.String(12), default="")
    country = db.Column(db.String(40), default="United States")
    vifp_number = db.Column(db.String(20), default="")
    rewards_points = db.Column(db.Integer, default=0)
    rewards_stars = db.Column(db.Integer, default=0)
    rewards_tier = db.Column(db.String(20), default="Blue")
    created_at = db.Column(db.DateTime, default=lambda: MIRROR_REFERENCE_DATE)

    bookings = db.relationship("Booking", backref="user", lazy=True)
    favorites = db.relationship("SavedCruise", backref="user", lazy=True)
    payments = db.relationship("PaymentMethod", backref="user", lazy=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode()

    def set_password_hash(self, hashed):
        """Set an externally precomputed hash (keeps seeding deterministic:
        bcrypt salts are random, so seed time must not hash passwords)."""
        self.password_hash = hashed

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


class PaymentMethod(db.Model):
    __tablename__ = "payment_methods"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    card_type = db.Column(db.String(20), nullable=False)   # Visa / Mastercard
    last4 = db.Column(db.String(4), nullable=False)
    holder_name = db.Column(db.String(80), default="")
    exp_month = db.Column(db.Integer, nullable=False)
    exp_year = db.Column(db.Integer, nullable=False)
    is_default = db.Column(db.Boolean, default=False)


class Ship(db.Model):
    __tablename__ = "ships"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(4), unique=True, nullable=False)
    name = db.Column(db.String(60), nullable=False)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    hero_image = db.Column(db.String(160), default="")
    intro = db.Column(db.Text, default="")
    long_desc_html = db.Column(db.Text, default="")
    sail_to = db.Column(db.Text, default="")      # csv
    sail_from = db.Column(db.Text, default="")    # csv
    durations = db.Column(db.Text, default="")    # csv

    features = db.relationship("ShipFeature", backref="ship", lazy=True,
                                order_by="ShipFeature.sort")

    @property
    def hero_images(self):
        extra = ShipHero.query.filter_by(ship_id=self.id).order_by(ShipHero.sort).all()
        urls = [self.hero_image] if self.hero_image else []
        urls += [h.url for h in extra]
        return [u for u in urls if u]

    @property
    def sail_to_list(self):
        return [x for x in (self.sail_to or "").split("|") if x]

    @property
    def sail_from_list(self):
        return [x for x in (self.sail_from or "").split("|") if x]

    @property
    def duration_list(self):
        return [x for x in (self.durations or "").split("|") if x]

    def features_of(self, kind):
        return [f for f in self.features if f.kind == kind]


class ShipHero(db.Model):
    __tablename__ = "ship_heros"
    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.Integer, db.ForeignKey("ships.id"), nullable=False)
    url = db.Column(db.String(160), nullable=False)
    sort = db.Column(db.Integer, default=0)


class ShipFeature(db.Model):
    __tablename__ = "ship_features"
    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.Integer, db.ForeignKey("ships.id"), nullable=False)
    kind = db.Column(db.String(20), nullable=False)  # zone/activity/dining/stateroom
    title = db.Column(db.String(120), nullable=False)
    cost = db.Column(db.String(20))                  # included/additional/None
    desc_html = db.Column(db.Text, default="")
    text = db.Column(db.Text, default="")
    image = db.Column(db.String(160), default="")
    sort = db.Column(db.Integer, default=0)


class Destination(db.Model):
    __tablename__ = "destinations"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(60), nullable=False)
    overview = db.Column(db.Text, default="")
    things_to_do = db.Column(db.Text, default="")    # json list
    hero_image = db.Column(db.String(160), default="")
    ships_csv = db.Column(db.Text, default="")

    @property
    def things_to_do_list(self):
        import json as _json
        try:
            return _json.loads(self.things_to_do or "[]")
        except Exception:
            return []


class Port(db.Model):
    __tablename__ = "ports"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), default="")
    is_homeport = db.Column(db.Boolean, default=False)
    desc_html = db.Column(db.Text, default="")
    image = db.Column(db.String(160), default="")


class Itinerary(db.Model):
    __tablename__ = "itineraries"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False)
    ship_id = db.Column(db.Integer, db.ForeignKey("ships.id"), nullable=False)
    departure_port_id = db.Column(db.Integer, db.ForeignKey("ports.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    url_path = db.Column(db.String(200), nullable=False)
    region_code = db.Column(db.String(10), nullable=False)
    region_name = db.Column(db.String(60), nullable=False)
    dur = db.Column(db.Integer, nullable=False)
    ports_csv = db.Column(db.Text, default="")     # portsToDisplay
    roundtrip = db.Column(db.Boolean, default=True)
    from_price = db.Column(db.Integer, default=0)
    image = db.Column(db.String(160), default="")
    has_extra_value = db.Column(db.Boolean, default=False)

    ship = db.relationship("Ship", backref="itineraries")
    departure_port = db.relationship("Port", foreign_keys=[departure_port_id])
    days = db.relationship("ItineraryDay", backref="itinerary", lazy=True,
                           order_by="ItineraryDay.day")
    sailings = db.relationship("Sailing", backref="itinerary", lazy=True,
                               order_by="Sailing.departure_date")

    __table_args__ = (db.UniqueConstraint("code", "departure_port_id", "ship_id", "dur",
                                          name="uq_itinerary"),)

    @property
    def ports_display(self):
        return [p for p in (self.ports_csv or "").split("|") if p]

    @property
    def route_display(self):
        return "Start: " + " > ".join(self.ports_display) if self.ports_display else ""

    @property
    def sailing_count(self):
        return len(self.sailings)


class ItineraryDay(db.Model):
    __tablename__ = "itinerary_days"
    id = db.Column(db.Integer, primary_key=True)
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=False)
    day = db.Column(db.Integer, nullable=False)
    port_code = db.Column(db.String(6), nullable=False)
    port_name = db.Column(db.String(80), nullable=False)
    arrive = db.Column(db.String(20), default="")
    depart = db.Column(db.String(20), default="")

    port = db.relationship("Port", primaryjoin="ItineraryDay.port_code == Port.code",
                           foreign_keys=[port_code], uselist=False, viewonly=True)


class Sailing(db.Model):
    __tablename__ = "sailings"
    id = db.Column(db.Integer, primary_key=True)
    sailing_id = db.Column(db.String(20), nullable=False)
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=False)
    departure_date = db.Column(db.String(10), nullable=False)
    arrival_date = db.Column(db.String(10), nullable=False)
    dep_arr = db.Column(db.String(30), default="")
    dep_arr_days = db.Column(db.String(30), default="")
    year = db.Column(db.String(6), default="")
    interior = db.Column(db.Float)
    oceanview = db.Column(db.Float)
    balcony = db.Column(db.Float)
    suite = db.Column(db.Float)
    lowest = db.Column(db.Float, default=0)

    __table_args__ = (db.UniqueConstraint("itinerary_id", "sailing_id",
                                          name="uq_sailing"),)

    def room_price(self, room_type):
        return getattr(self, room_type, None)

    @property
    def rooms(self):
        return {
            "interior": ("Interior", self.interior),
            "oceanview": ("Ocean View", self.oceanview),
            "balcony": ("Balcony", self.balcony),
            "suite": ("Suite", self.suite),
        }


class Excursion(db.Model):
    __tablename__ = "excursions"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    port_slug = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(200), default="")
    price = db.Column(db.Float)
    price_unit = db.Column(db.String(40), default="")
    rating = db.Column(db.Float)
    review_count = db.Column(db.Integer, default=0)
    desc_html = db.Column(db.Text, default="")
    image = db.Column(db.String(160), default="")
    duration = db.Column(db.String(30), default="")
    activity_level = db.Column(db.String(20), default="")
    min_age = db.Column(db.String(10), default="")


class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.Integer, primary_key=True)
    booking_number = db.Column(db.String(12), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    sailing_id = db.Column(db.Integer, db.ForeignKey("sailings.id"), nullable=False)
    room_type = db.Column(db.String(20), nullable=False)
    room_category = db.Column(db.String(60), default="")
    guests = db.Column(db.Integer, default=2)
    lead_guest = db.Column(db.String(80), default="")
    cabin_number = db.Column(db.String(10), default="")
    total_price = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default="confirmed")
    created_at = db.Column(db.DateTime, default=lambda: MIRROR_REFERENCE_DATE)

    sailing = db.relationship("Sailing", backref="bookings")
    excursions = db.relationship("BookingExcursion", backref="booking", lazy=True)

    @property
    def itinerary(self):
        return self.sailing.itinerary


class BookingExcursion(db.Model):
    __tablename__ = "booking_excursions"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    excursion_id = db.Column(db.Integer, db.ForeignKey("excursions.id"), nullable=False)
    guests = db.Column(db.Integer, default=2)
    price = db.Column(db.Float, default=0)

    excursion = db.relationship("Excursion")


class SavedCruise(db.Model):
    __tablename__ = "saved_cruises"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=False)
    added_at = db.Column(db.DateTime, default=lambda: MIRROR_REFERENCE_DATE)

    itinerary = db.relationship("Itinerary")

    __table_args__ = (db.UniqueConstraint("user_id", "itinerary_id",
                                          name="uq_saved"),)


# ---------------------------------------------------------------- auth

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def login_required_ajax(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"ok": False, "error": "login_required"}), 401
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------- helpers

STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
              "is", "it", "by", "with", "from", "day", "days"}


def tokenize(query):
    return [t.lower() for t in re.split(r"\W+", query or "")
            if t.lower() not in STOP_WORDS and len(t) > 1]


def scored_search(query, records, fields, limit=None):
    """Token-overlap scored search (never strict AND)."""
    tokens = tokenize(query)
    if not tokens:
        return records
    results = []
    for rec in records:
        text = " ".join(str(getattr(rec, f, "") or "") for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            results.append((score, rec))
    results.sort(key=lambda x: -x[0])
    return [r for _, r in results][:limit]


def format_money(v):
    if v is None:
        return "Sold Out"
    if float(v) == int(v):
        return f"${int(v):,}"
    return f"${v:,.2f}"


def month_name(iso_date):
    d = date.fromisoformat(iso_date)
    return d.strftime("%b")


DUR_BUCKETS = {"D1": (2, 5), "D2": (6, 9), "D3": (10, 99)}

# Upstream dest option codes select region families (e.g. dest=C returns
# Eastern/Western/Southern Caribbean and Caribbean & Panama itineraries).
DEST_FAMILIES = {
    "A": ["GL", "AJ"],          # Alaska
    "BH": ["BH"],                # The Bahamas
    "BM": ["BM"],                # Bermuda
    "NN": ["NN", "NO"],          # Canada & New England
    "C": ["CE", "CW", "CS", "CP"],  # Caribbean
    "E": ["ME", "BI", "GI", "CG", "EC", "IB", "EN", "ES"],  # Europe
    "H": ["H"],                  # Hawaii
    "M": ["MB", "MR"],           # Mexico
    "T": ["T"],                  # Panama Canal
    "S": ["S"],                  # South America
    "ET": ["ET"],                # Transatlantic
    "TP": ["TP", "XS"],          # Transpacific
    "X": ["XS"],                 # Asia
}




app.jinja_env.globals["zip"] = zip
app.jinja_env.globals["range"] = range


def merge_query(query_dict, **overrides):
    """Jinja helper: merge the current query string with overrides."""
    from urllib.parse import urlencode
    params = {k: v for k, v in query_dict.items()}
    params.update({k: str(v) for k, v in overrides.items()})
    return "?" + urlencode(params)


app.jinja_env.globals["merge_query"] = merge_query

# ---------------------------------------------------------------- context

@app.context_processor
def inject_globals():
    from _seed_footer import FOOTER_BOTTOM_LINKS, FOOTER_COLUMNS
    from _seed_home import PHONE
    return {
        "current_user": current_user,
        "phone_number": PHONE,
        "footer_columns": FOOTER_COLUMNS,
        "footer_bottom_links": FOOTER_BOTTOM_LINKS,
        "dest_options": _dest_options(),
        "port_options": _port_options(),
        "ship_options": _ship_options(),
    }


def _nav_destinations():
    return Destination.query.order_by(Destination.name).all()


# ---------------------------------------------------------------- routes: auth

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            nxt = request.args.get("next") or request.form.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            return redirect(url_for("account"))
        flash("The email or password you entered is incorrect. Please try again.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        first = request.form.get("first_name", "").strip()
        last = request.form.get("last_name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        errors = []
        if not email or not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Please enter a valid email address.")
        if not first or not last:
            errors.append("Please enter your first and last name.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if not errors and User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists. Please log in.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            user = User(email=email, first_name=first, last_name=last,
                        phone=request.form.get("phone", "").strip(),
                        vifp_number="V" + secrets.token_hex(3).upper(),
                        rewards_points=0, rewards_stars=0, rewards_tier="Blue")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome aboard! Your Carnival account is ready.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ---------------------------------------------------------------- account

@app.route("/account")
@login_required
def account():
    upcoming = [b for b in current_user.bookings if b.status == "confirmed"]
    cancelled = [b for b in current_user.bookings if b.status == "cancelled"]
    return render_template("account.html", upcoming=upcoming, cancelled=cancelled)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name", current_user.first_name).strip()
        current_user.last_name = request.form.get("last_name", current_user.last_name).strip()
        current_user.phone = request.form.get("phone", current_user.phone).strip()
        current_user.address1 = request.form.get("address1", current_user.address1).strip()
        current_user.address2 = request.form.get("address2", current_user.address2).strip()
        current_user.city = request.form.get("city", current_user.city).strip()
        current_user.state = request.form.get("state", current_user.state).strip()
        current_user.zip_code = request.form.get("zip_code", current_user.zip_code).strip()
        db.session.commit()
        flash("Your profile has been updated.", "success")
        return redirect(url_for("account"))
    states = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
              "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
              "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
              "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
              "VT", "VA", "WA", "WV", "WI", "WY"]
    return render_template("account_edit.html", states=states)


@app.route("/account/payments/add", methods=["POST"])
@login_required
def add_payment():
    card_type = request.form.get("card_type", "Visa").strip()
    number = re.sub(r"\D", "", request.form.get("card_number", ""))
    holder = request.form.get("holder_name", "").strip()
    exp_month = request.form.get("exp_month", "").strip()
    exp_year = request.form.get("exp_year", "").strip()
    errors = []
    if len(number) < 13 or len(number) > 19:
        errors.append("Please enter a valid card number (13-19 digits).")
    if not exp_month or not exp_year or not exp_month.isdigit() or not exp_year.isdigit():
        errors.append("Please enter the card expiration date.")
    else:
        m, y = int(exp_month), int(exp_year)
        if m < 1 or m > 12:
            errors.append("Expiration month must be between 1 and 12.")
        if y < 2026 or y > 2040:
            errors.append("Expiration year must be between 2026 and 2040.")
    if not holder:
        errors.append("Please enter the name on the card.")
    if errors:
        for e in errors:
            flash(e, "error")
    else:
        pm = PaymentMethod(user_id=current_user.id, card_type=card_type,
                           last4=number[-4:], holder_name=holder,
                           exp_month=int(exp_month), exp_year=int(exp_year))
        db.session.add(pm)
        db.session.commit()
        flash(f"Your {card_type} ending in {number[-4:]} has been saved.", "success")
    return redirect(url_for("account"))


@app.route("/favorites")
@login_required
def favorites():
    saved = SavedCruise.query.filter_by(user_id=current_user.id).all()
    return render_template("favorites.html", saved=saved)


@app.route("/favorites/toggle", methods=["POST"])
@login_required_ajax
def toggle_favorite():
    itin_id = request.form.get("itinerary_id", type=int)
    if not itin_id:
        return jsonify({"ok": False}), 400
    fav = SavedCruise.query.filter_by(user_id=current_user.id, itinerary_id=itin_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        return jsonify({"ok": True, "saved": False})
    db.session.add(SavedCruise(user_id=current_user.id, itinerary_id=itin_id))
    db.session.commit()
    return jsonify({"ok": True, "saved": True})


# ---------------------------------------------------------------- homepage

@app.route("/")
def index():
    from _seed_home import (DEST_SALE_TILES, FLEX_PAY_PROMO, HERO_PROMO,
                            NEW_SAILINGS_PROMO, PARADISE_BANNER, REWARDS_BANNER,
                            REWARDS_CARD_PROMO, SHIP_TILES, TOUTS,
                            VALUE_PACKAGES)
    featured_ships = [Ship.query.filter_by(slug=s["slug"]).first() for s in SHIP_TILES]
    return render_template(
        "index.html",
        hero=HERO_PROMO, rewards_card=REWARDS_CARD_PROMO,
        dest_tiles=DEST_SALE_TILES, paradise_banner=PARADISE_BANNER,
        rewards_banner=REWARDS_BANNER, value_packages=VALUE_PACKAGES,
        ship_tiles=SHIP_TILES, featured_ships=featured_ships,
        new_sailings=NEW_SAILINGS_PROMO, flex_pay=FLEX_PAY_PROMO, touts=TOUTS,
        dests=_nav_destinations())


# ---------------------------------------------------------------- cruise search

def _search_query():
    dest = request.args.get("dest", "").strip()
    port = request.args.get("port", "").strip()
    dur = request.args.get("dur", "").strip()
    dates = request.args.get("dates", "").strip()
    shipcode = request.args.get("shipcode", "").strip()
    sort = request.args.get("sort", "fromprice").strip()
    page = request.args.get("page", 1, type=int)
    numadults = request.args.get("numadults", 2, type=int)
    cruisedeals = request.args.get("cruisedeals", "").strip()
    ptport = request.args.get("ptport", "").strip()
    q = request.args.get("q", "").strip()
    return dict(dest=dest, port=port, dur=dur, dates=dates, shipcode=shipcode,
                sort=sort, page=page, numadults=numadults, cruisedeals=cruisedeals,
                ptport=ptport, q=q)


@app.route("/cruise-search")
def cruise_search():
    f = _search_query()
    query = Itinerary.query
    if f["dest"]:
        codes = [c for c in re.split(r"[,\s]+", f["dest"]) if c]
        # dest codes are region families (BH, C, M ...) or featured port codes
        # (CBK, HMD, DOP, CZM, GDT, RTB); port codes match by port name.
        port_codes = {p.code: p.name for p in Port.query.all()}
        region_codes = []
        name_matches = []
        for c in codes:
            if c in port_codes:
                base_name = re.split(r"[,(]", port_codes[c])[0].strip()
                name_matches.append(Itinerary.ports_csv.contains(base_name))
            else:
                region_codes.extend(DEST_FAMILIES.get(c, [c]))
        conditions = []
        if region_codes:
            conditions.append(Itinerary.region_code.in_(region_codes))
        conditions.extend(name_matches)
        if conditions:
            query = query.filter(or_(*conditions))
    if f["port"]:
        codes = [c for c in re.split(r"[,\s]+", f["port"]) if c]
        port_match = [Itinerary.departure_port.has(Port.code.in_(codes))]
        for c in codes:
            port_match.append(Itinerary.departure_port.has(Port.name.ilike(f"%{c}%")))
        query = query.filter(or_(*port_match))
    if f["dur"] and f["dur"] in DUR_BUCKETS:
        lo, hi = DUR_BUCKETS[f["dur"]]
        query = query.filter(Itinerary.dur.between(lo, hi))
    if f["dur"].isdigit():
        query = query.filter(Itinerary.dur == int(f["dur"]))
    if f["shipcode"]:
        codes = [c for c in re.split(r"[,\s]+", f["shipcode"]) if c]
        query = query.filter(Itinerary.ship.has(Ship.code.in_(codes)))
    if f["dates"]:
        years = {d[:4] for d in re.split(r"[,\s]+", f["dates"]) if d[:4].isdigit()}
        months = set()
        for d in re.split(r"[,\s]+", f["dates"]):
            if len(d) >= 6 and d[:6].isdigit():
                months.add(d[:6])
        if years or months:
            itin_ids = [i.id for i in query.all()]
            sail_q = Sailing.query.filter(Sailing.itinerary_id.in_(itin_ids))
            if months:
                sail_q = sail_q.filter(or_(*[Sailing.departure_date.startswith(m) for m in months]))
            elif years:
                sail_q = sail_q.filter(or_(*[Sailing.departure_date.startswith(y) for y in years]))
            ids = {s.itinerary_id for s in sail_q.all()}
            query = Itinerary.query.filter(Itinerary.id.in_(ids))
    if f["ptport"]:
        codes = [c for c in re.split(r"[,\s]+", f["ptport"]) if c]
        match = [Itinerary.ports_csv.contains(c) for c in codes]
        query = query.filter(or_(*match))
    if f["cruisedeals"] == "paradisecollection":
        paradise = ["CBK", "HMD", "DOP", "CZM", "GDT", "RTB"]
        query = query.filter(or_(*[Itinerary.ports_csv.contains(p) for p in paradise]))
    if f["cruisedeals"] == "flexpay_offer":
        eligible_ships = ["BR", "CQ", "EL", "HZ", "LI", "MC", "MI", "PO", "PA", "RD", "SP", "SN", "VA"]
        query = query.filter(Itinerary.ship.has(Ship.code.in_(eligible_ships)))
    if f["q"]:
        query = query.filter(Itinerary.title.ilike(f"%{f['q']}%"))

    all_matches = query.all()
    if f["sort"] == "-fromprice":
        all_matches.sort(key=lambda i: -(i.from_price or 0))
    elif f["sort"] == "duration":
        all_matches.sort(key=lambda i: i.dur)
    elif f["sort"] == "-duration":
        all_matches.sort(key=lambda i: -i.dur)
    else:
        all_matches.sort(key=lambda i: (i.from_price or 99999))

    total = len(all_matches)
    per_page = 8
    page = max(1, f["page"])
    page_items = all_matches[(page - 1) * per_page: page * per_page]
    saved_ids = set()
    if current_user.is_authenticated:
        saved_ids = {s.itinerary_id for s in
                     SavedCruise.query.filter_by(user_id=current_user.id).all()}
    return render_template(
        "cruise_search.html", items=page_items, total=total, page=page,
        per_page=per_page, f=f, saved_ids=saved_ids,
        dests=_nav_destinations(),
        dest_options=_dest_options(), port_options=_port_options(),
        ship_options=_ship_options())


def _dest_options():
    from _seed_catalog import DEST_LABELS
    return sorted(DEST_LABELS.items(), key=lambda kv: kv[1])


def _port_options():
    ports = Port.query.filter_by(is_homeport=True).order_by(Port.name).all()
    return [(p.code, p.name) for p in ports]


def _ship_options():
    ships = Ship.query.order_by(Ship.name).all()
    return [(s.code, s.name) for s in ships]


# ---------------------------------------------------------------- itinerary detail

@app.route("/itinerary/<path:itin_path>")
def itinerary_detail(itin_path):
    # upstream format: <slug>-cruise/<port-slug>/<ship-slug>/<n>-days/<code>
    parts = itin_path.strip("/").split("/")
    if len(parts) != 5:
        abort(404)
    code = parts[-1].upper()
    port_code = request.args.get("itinportcode", "").upper()
    itin = Itinerary.query.filter_by(code=code).all()
    if port_code:
        itin = [i for i in itin if i.departure_port.code == port_code]
    if len(itin) != 1:
        # try matching by url path
        by_path = Itinerary.query.filter_by(url_path="/itinerary/" + itin_path).first()
        if by_path:
            itin = [by_path]
        else:
            abort(404)
    itin = itin[0]
    days = itin.days
    sailings = itin.sailings
    # per-day excursions: ports that have an excursion slug
    day_excs = {}
    for d in days:
        port = Port.query.filter_by(code=d.port_code).first()
        if port and port.slug:
            excs = Excursion.query.filter_by(port_slug=port.slug).order_by(Excursion.review_count.desc()).limit(4).all()
            if excs:
                day_excs[d.id] = excs
    saved = False
    if current_user.is_authenticated:
        saved = SavedCruise.query.filter_by(user_id=current_user.id,
                                            itinerary_id=itin.id).first() is not None
    return render_template("itinerary_detail.html", itin=itin, days=days,
                           sailings=sailings, day_excs=day_excs, saved=saved,
                           dests=_nav_destinations())


# ---------------------------------------------------------------- booking flow

BOOKING_STEPS = ["stateroom", "guests", "payment", "confirmation"]


def _sailing_from_args():
    embk = request.args.get("embkCode", "").upper()
    itin_code = request.args.get("itinCode", "").upper()
    ship_code = request.args.get("shipCode", "").upper()
    sailing_id = request.args.get("sailingID", "")
    dur = request.args.get("durDays", "")
    query = Sailing.query
    if sailing_id:
        sl = query.filter_by(sailing_id=sailing_id).first()
        if sl:
            return sl, None
    itin = Itinerary.query.filter_by(code=itin_code).all()
    itin = [i for i in itin if i.departure_port.code == embk and i.ship.code == ship_code
            and str(i.dur) == str(dur)]
    if len(itin) != 1:
        return None, "no_sailing"
    if not itin[0].sailings:
        return None, "no_sailing"
    return itin[0].sailings[0], None


@app.route("/booking", methods=["GET", "POST"])
def booking():
    step = request.args.get("step", "stateroom")
    if step not in BOOKING_STEPS:
        step = "stateroom"
    sailing, err = _sailing_from_args()
    if sailing is None:
        abort(404)
    itin = sailing.itinerary
    num_guests = request.args.get("numGuests", 2, type=int)
    room_type = request.args.get("roomType", session.get("booking_room", ""))

    if step == "stateroom":
        # stateroom category list for this ship
        staterooms = itin.ship.features_of("stateroom")
        return render_template("booking_stateroom.html", sailing=sailing, itin=itin,
                               num_guests=num_guests, staterooms=staterooms,
                               dests=_nav_destinations())

    # guests/payment steps require a chosen room type
    if not room_type and step in ("guests", "payment"):
        args = request.args.to_dict()
        args["step"] = "stateroom"
        return redirect(url_for("booking", **args))
    if step == "guests":
        if request.method == "POST":
            lead = request.form.get("lead_guest", "").strip()
            guests = request.form.get("guests", num_guests, type=int)
            if not lead:
                flash("Please enter the lead guest name.", "error")
            elif guests < 1 or guests > 8:
                flash("Guests must be between 1 and 8.", "error")
            else:
                session["booking_guests"] = guests
                session["booking_lead"] = lead
                session["booking_room"] = room_type
                args = request.args.to_dict()
                args["step"] = "payment"
                return redirect(url_for("booking", **args))
        return render_template("booking_guests.html", sailing=sailing, itin=itin,
                               num_guests=num_guests, room_type=room_type,
                               dests=_nav_destinations())

    if step == "payment":
        if request.method == "POST":
            if not current_user.is_authenticated:
                flash("Please log in or create an account to complete your booking.", "error")
                return redirect(url_for("login", next=request.full_path))
            holder = request.form.get("holder_name", "").strip()
            number = re.sub(r"\D", "", request.form.get("card_number", ""))
            exp_month = request.form.get("exp_month", "").strip()
            exp_year = request.form.get("exp_year", "").strip()
            errors = []
            if not holder:
                errors.append("Please enter the name on the card.")
            if len(number) < 13 or len(number) > 19:
                errors.append("Please enter a valid card number (13-19 digits).")
            if not exp_month.isdigit() or int(exp_month) < 1 or int(exp_month) > 12:
                errors.append("Please enter a valid expiration month (1-12).")
            if not exp_year.isdigit() or int(exp_year) < 2026 or int(exp_year) > 2040:
                errors.append("Please enter a valid expiration year (2026-2040).")
            if errors:
                for e in errors:
                    flash(e, "error")
                return render_template("booking_payment.html", sailing=sailing,
                                       itin=itin, room_type=room_type,
                                       num_guests=session.get("booking_guests", num_guests),
                                       dests=_nav_destinations())
            guests = session.get("booking_guests", num_guests)
            lead = session.get("booking_lead", current_user.full_name)
            price = sailing.room_price(room_type) or sailing.lowest
            total = float(price) * guests
            booking_number = "CCL" + datetime.now().strftime("%y%m") + secrets.token_hex(2).upper()
            room_category = {
                "interior": "Interior", "oceanview": "Ocean View",
                "balcony": "Balcony", "suite": "Suite",
            }.get(room_type, room_type.title() if room_type else "")
            bk = Booking(booking_number=booking_number, user_id=current_user.id,
                         sailing_id=sailing.id, room_type=room_type,
                         room_category=room_category,
                         guests=guests, lead_guest=lead,
                         cabin_number=f"{(Booking.query.count() % 8) + 4}{secrets.choice('ABCDE')}{(Booking.query.count() % 40) + 101}",
                         total_price=total, status="confirmed")
            db.session.add(bk)
            pm = PaymentMethod(user_id=current_user.id,
                               card_type="Visa" if number[0] == "4" else "Mastercard",
                               last4=number[-4:], holder_name=holder,
                               exp_month=int(exp_month), exp_year=int(exp_year))
            db.session.add(pm)
            db.session.commit()
            session.pop("booking_room", None)
            session.pop("booking_guests", None)
            session.pop("booking_lead", None)
            return redirect(url_for("booking", step="confirmation",
                                    embkCode=itin.departure_port.code,
                                    itinCode=itin.code, durDays=itin.dur,
                                    shipCode=itin.ship.code,
                                    sailingID=sailing.sailing_id,
                                    bookingNumber=bk.booking_number))
        return render_template("booking_payment.html", sailing=sailing, itin=itin,
                               room_type=room_type,
                               num_guests=session.get("booking_guests", num_guests),
                               dests=_nav_destinations())

    if step == "confirmation":
        booking_number = request.args.get("bookingNumber", "")
        bk = Booking.query.filter_by(booking_number=booking_number).first()
        if not bk:
            abort(404)
        return render_template("booking_confirmation.html", booking=bk,
                               sailing=sailing, itin=itin,
                               dests=_nav_destinations())
    abort(404)


# ---------------------------------------------------------------- ships

@app.route("/cruise-ships")
def ships_index():
    ships = Ship.query.order_by(Ship.name).all()
    return render_template("ships_index.html", ships=ships, dests=_nav_destinations())


@app.route("/cruise-ships/<slug>")
def ship_detail(slug):
    ship = Ship.query.filter_by(slug=slug).first_or_404()
    itins = Itinerary.query.filter_by(ship_id=ship.id).order_by(Itinerary.from_price).all()
    staterooms = ship.features_of("stateroom")
    zones = ship.features_of("zone") or ship.features_of("feature")
    activities = ship.features_of("activity")
    dining = ship.features_of("dining")
    return render_template("ship_detail.html", ship=ship, itins=itins,
                           staterooms=staterooms, zones=zones,
                           activities=activities, dining=dining,
                           dests=_nav_destinations())


# ---------------------------------------------------------------- destinations

@app.route("/cruise-to/<slug>")
def destination_detail(slug):
    dest = Destination.query.filter_by(slug=slug).first_or_404()
    region_itins = Itinerary.query.filter_by(region_name=dest.name + "s").all()
    itins = Itinerary.query.filter(Itinerary.region_name.ilike(f"%{dest.name}%")).all()
    itins = sorted(itins, key=lambda i: i.from_price or 99999)
    ships_here = [s for s in dest.ships_csv.split("|") if s]
    return render_template("destination_detail.html", dest=dest, itins=itins,
                           ships_here=ships_here, dests=_nav_destinations())


# ---------------------------------------------------------------- deals

@app.route("/cruise-deals")
def cruise_deals():
    from _seed_home import (DEST_SALE_TILES, FLEX_PAY_PROMO, HERO_PROMO,
                            NEW_SAILINGS_PROMO, REWARDS_CARD_PROMO,
                            VALUE_PACKAGES)
    return render_template("cruise_deals.html", hero=HERO_PROMO,
                           rewards_card=REWARDS_CARD_PROMO,
                           dest_tiles=DEST_SALE_TILES,
                           value_packages=VALUE_PACKAGES,
                           new_sailings=NEW_SAILINGS_PROMO,
                           flex_pay=FLEX_PAY_PROMO,
                           dests=_nav_destinations())


# ---------------------------------------------------------------- shore excursions

@app.route("/shore-excursions")
def excursions_index():
    ports = db.session.query(Excursion.port_slug).distinct().all()
    port_slugs = sorted({p[0] for p in ports})
    groups = {}
    for slug in port_slugs:
        port = Port.query.filter_by(slug=slug).first()
        name = port.name if port else slug.replace("-", " ").title()
        n = Excursion.query.filter_by(port_slug=slug).count()
        groups[slug] = {"name": name, "count": n}
    return render_template("excursions_index.html", groups=groups,
                           dests=_nav_destinations())


@app.route("/shore-excursions/<port_slug>")
def excursions_port(port_slug):
    port = Port.query.filter_by(slug=port_slug).first()
    excs = Excursion.query.filter_by(port_slug=port_slug).all()
    if not excs and port is None:
        abort(404)
    port_name = port.name if port else port_slug.replace("-", " ").title()
    sort = request.args.get("sort", "recommended")
    if sort == "price":
        excs.sort(key=lambda e: (e.price is None, e.price or 0))
    elif sort == "rating":
        excs.sort(key=lambda e: -(e.rating or 0))
    else:
        excs.sort(key=lambda e: -(e.review_count or 0))
    return render_template("excursions_port.html", excs=excs, port=port,
                           port_name=port_name, port_slug=port_slug, sort=sort,
                           dests=_nav_destinations())


@app.route("/shore-excursions/<port_slug>/<exc_slug>")
def excursion_detail(port_slug, exc_slug):
    exc = Excursion.query.filter_by(port_slug=port_slug, slug=exc_slug).first()
    if not exc:
        exc = Excursion.query.filter_by(code=exc_slug.rsplit("-", 1)[-1]).first()
    if not exc:
        abort(404)
    port = Port.query.filter_by(slug=port_slug).first()
    related = Excursion.query.filter(Excursion.port_slug == port_slug,
                                    Excursion.id != exc.id).limit(4).all()
    return render_template("excursion_detail.html", exc=exc, port=port,
                           related=related, dests=_nav_destinations())


# ---------------------------------------------------------------- global search

@app.route("/search")
def global_search():
    q = request.args.get("q", "").strip()
    itins = scored_search(q, Itinerary.query.all(), ["title", "ports_csv", "region_name"])
    ships = scored_search(q, Ship.query.all(), ["name"])
    ports = scored_search(q, Port.query.all(), ["name"])
    excs = scored_search(q, Excursion.query.all(), ["title"])
    feats = scored_search(q, ShipFeature.query.all(), ["title", "desc_html"], limit=12)
    return render_template("search_results.html", q=q, itins=itins[:12],
                           ships=ships[:8], ports=ports[:8], excs=excs[:12],
                           feats=feats, dests=_nav_destinations())


# ---------------------------------------------------------------- manage bookings

@app.route("/booked/manage")
@login_required
def manage_bookings():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(
        Booking.created_at).all()
    return render_template("manage_bookings.html", bookings=bookings,
                           dests=_nav_destinations())


@app.route("/booked/manage/<booking_number>")
@login_required
def manage_booking_detail(booking_number):
    bk = Booking.query.filter_by(booking_number=booking_number,
                                  user_id=current_user.id).first_or_404()
    sailing = bk.sailing
    itin = sailing.itinerary
    # excursions offered at the ports this cruise visits
    port_slugs = set()
    for d in itin.days:
        port = Port.query.filter_by(code=d.port_code).first()
        if port and port.slug:
            port_slugs.add(port.slug)
    offered = []
    for slug in sorted(port_slugs):
        for e in Excursion.query.filter_by(port_slug=slug).limit(3).all():
            offered.append(e)
    booked_ids = {be.excursion_id for be in bk.excursions}
    return render_template("booking_detail.html", booking=bk, sailing=sailing,
                           itin=itin, offered=offered, booked_ids=booked_ids,
                           dests=_nav_destinations())


@app.route("/booked/manage/<booking_number>/cancel", methods=["POST"])
@login_required
def cancel_booking(booking_number):
    bk = Booking.query.filter_by(booking_number=booking_number,
                                 user_id=current_user.id).first_or_404()
    bk.status = "cancelled"
    db.session.commit()
    flash(f"Booking {bk.booking_number} has been cancelled.", "success")
    return redirect(url_for("manage_bookings"))


@app.route("/booked/manage/<booking_number>/add-excursion", methods=["POST"])
@login_required
def add_booking_excursion(booking_number):
    bk = Booking.query.filter_by(booking_number=booking_number,
                                 user_id=current_user.id).first_or_404()
    exc_id = request.form.get("excursion_id", type=int)
    exc = Excursion.query.get(exc_id) if exc_id else None
    if not exc:
        flash("Excursion not found.", "error")
        return redirect(url_for("manage_booking_detail", booking_number=booking_number))
    guests = request.form.get("guests", bk.guests, type=int)
    if BookingExcursion.query.filter_by(booking_id=bk.id, excursion_id=exc.id).first():
        flash(f"{exc.title} is already added to this booking.", "error")
        return redirect(url_for("manage_booking_detail", booking_number=booking_number))
    be = BookingExcursion(booking_id=bk.id, excursion_id=exc.id, guests=guests,
                          price=(exc.price or 0) * guests)
    db.session.add(be)
    bk.total_price = float(bk.total_price or 0) + float(be.price)
    db.session.commit()
    flash(f"{exc.title} has been added to booking {bk.booking_number}.", "success")
    return redirect(url_for("manage_booking_detail", booking_number=booking_number))


# ---------------------------------------------------------------- info pages

INFO_ROUTES = {}


def _info_page(slug, route=None):
    from _seed_info import INFO_PAGES, FAQ

    @app.route(f"/{route or slug}", endpoint=f"info_{slug.replace('-', '_')}")
    def info_view(slug=slug):
        data = INFO_PAGES.get(slug)
        if not data:
            abort(404)
        return render_template("info_page.html", slug=slug, data=data,
                               faq=FAQ if slug == "help" else None,
                               dests=_nav_destinations())
    INFO_ROUTES[slug] = info_view


for _slug, _route in [("drink-packages", None), ("internet-plans", None),
                     ("carnival-rewards", None), ("financing", None),
                     ("spa", None), ("help", None),
                     ("about-us", "about-carnival/about-us"),
                     ("contact-us", "about-carnival/contact-us")]:
    _info_page(_slug, _route)


# ---------------------------------------------------------------- health

@app.route("/_health")
def health():
    return {"ok": True, "site": "carnival_cruise"}


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html", dests=_nav_destinations()), 404


# ---------------------------------------------------------------- bootstrap

from seed_data import seed_benchmark_users, seed_database  # noqa: E402

with app.app_context():
    db.create_all()
    seed_database(db, Ship, ShipHero, ShipFeature, Destination, Port,
                  Itinerary, ItineraryDay, Sailing, Excursion)
    seed_benchmark_users(db, User, Booking, BookingExcursion, SavedCruise,
                         PaymentMethod, Itinerary, Sailing, Port, Excursion,
                         bcrypt)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
