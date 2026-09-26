#!/usr/bin/env python3
"""Qatar Airways (qatarairways.com) mirror — Flask app.

Functional mirror of https://www.qatarairways.com/ built for the
WebHarbor offline benchmark environment: flight search & booking across
the real DOH-hub network, manage booking (seats / extra baggage /
Avios upgrades / cancellation), online check-in with boarding passes,
flight status, the destination guide (253 cities, 172 full guides),
offers with promo codes, the Privilege Club loyalty domain (join, sign
in, dashboard, Avios calculator, tier benefits), fleet pages with seat
maps, baggage allowance tables + calculator and the help hub.

All catalog rows (airports, flights, flight statuses, destinations,
offers copy, fleet facts) come from the tracked source snapshot under
source_data/ captured from the live site (via Wayback replays); see
provenance.json.
"""
import json
import math
import os
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
INSTANCE = BASE_DIR / "instance"
INSTANCE.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or "webharbor-qatar-airways-dev-key"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# The container always runs against instance/qatar_airways.db; the test
# suite points this at a scratch copy so its write paths never touch the seed.
_DB_PATH = os.environ.get("WEBHARBOR_MIRROR_DB") or str(INSTANCE / "qatar_airways.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{_DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# The mirror runs against a frozen schedule snapshot; flight status rows and
# the seeded bookings are pinned to this date.
MIRROR_REFERENCE_DATE = date(2026, 9, 24)

QR_NAV = [
    {"label": "Explore", "href": "/en/destinations.html"},
    {"label": "Plan your trip", "href": "/en/offers.html"},
    {"label": "Experience", "href": "/en/baggage.html"},
    {"label": "Privilege Club", "href": "/en/Privilege-Club/membership-tiers.html"},
    {"label": "Help", "href": "/en/help.html"},
]

# ---------------------------------------------------------------------------
# Domain constants (single source of truth for fares, Avios, seat fees)
# ---------------------------------------------------------------------------

CABINS = ["Economy", "Business", "First"]

# fare code -> (cabin, display name, price multiplier, order)
FARE_TYPES = {
    "ECO_LITE": ("Economy", "Economy Lite", 1.00, 1),
    "ECO_CLASSIC": ("Economy", "Economy Classic", 1.18, 2),
    "ECO_CONVENIENCE": ("Economy", "Economy Convenience", 1.35, 3),
    "ECO_COMFORT": ("Economy", "Economy Comfort", 1.55, 4),
    "BUS_LITE": ("Business", "Business Lite", 3.20, 1),
    "BUS_CLASSIC": ("Business", "Business Classic", 3.50, 2),
    "BUS_COMFORT": ("Business", "Business Comfort", 3.80, 3),
    "BUS_ELITE": ("Business", "Business Elite", 4.10, 4),
    "FIR_ELITE": ("First", "First Elite", 6.50, 1),
}

TIER_BONUS = {"Burgundy": 0.0, "Silver": 0.25, "Gold": 0.75, "Platinum": 1.00}
TIER_ORDER = ["Burgundy", "Silver", "Gold", "Platinum"]
TIER_QPOINTS = {"Silver": 150, "Gold": 300, "Platinum": 600}
TIER_RETAIN = {
    "Silver": "135 Qpoints within the last 12 months or 270 Qpoints within the last 24 months",
    "Gold": "270 Qpoints within the last 12 months or 540 Qpoints within the last 24 months",
    "Platinum": "540 Qpoints within the last 12 months or 1080 Qpoints within the last 24 months",
}

EQUIPMENT_NAMES = {
    "320": "Airbus A320",
    "332": "Airbus A330-200",
    "333": "Airbus A330-300",
    "359": "Airbus A350-900",
    "351": "Airbus A350-1000",
    "388": "Airbus A380-800",
    "77L": "Boeing 777-200LR",
    "77W": "Boeing 777-300ER",
    "788": "Boeing 787-8",
    "789": "Boeing 787-9",
}

STATUS_TEXT = {
    "ARVD": "Arrived",
    "ENRT": "En route",
    "PDEP": "Boarding",
    "PDEP_RSCH": "Rescheduled",
    "PDEP_DLYD": "Delayed",
    "CNLD": "Cancelled",
    "LAND": "Landed",
    "OFBL": "Departed",
    "DVTA": "Departed",
    "SCHD": "Scheduled",
}

# Extra baggage price per additional 23kg piece, by route distance band.
EXTRA_BAG_RATES = [
    (3000, 60, "USD 60"),
    (8000, 100, "USD 100"),
    (99999, 140, "USD 140"),
]

# Preferred-seat fee (exit rows / front economy rows) per leg.
PREFERRED_SEAT_FEE = 30


def fare_base_economy(distance_km: int, flight_number: int) -> int:
    """Deterministic one-way Economy Lite base fare in USD.

    Distance band + a stable per-flight offset keep fares realistic and
    stable across resets; the agent can always recompute the winner.
    """
    raw = 90 + distance_km * 0.11 + (flight_number % 7) * 8
    return int(round(raw / 5.0) * 5)


def fare_amount(flight, fare_code: str) -> int:
    cabin, _name, mult, _order = FARE_TYPES[fare_code]
    base = fare_base_economy(flight.distance_km, flight.number)
    if cabin == "Business":
        base = int(round((base * 3.1 + 150) / 5.0) * 5)
    elif cabin == "First":
        base = int(round((base * 6.2 + 300) / 5.0) * 5)
    return int(round(base * mult / 5.0) * 5)


def fare_options_for_cabin(cabin: str) -> list[str]:
    return [code for code, (c, _n, _m, _o) in FARE_TYPES.items() if c == cabin]


def taxes_for(amount: int) -> int:
    return int(round(amount * 0.12))


def avios_for_distance(distance_km: int, cabin: str, tier: str) -> int:
    mult = {"Economy": 1.0, "Business": 2.0, "First": 3.0}[cabin]
    base = max(1, int(round(distance_km / 10.0)))
    return int(round(base * mult * (1.0 + TIER_BONUS.get(tier, 0.0))))


def qpoints_for_distance(distance_km: int, cabin: str) -> int:
    div = {"Economy": 50, "Business": 25, "First": 15}[cabin]
    return max(1, int(round(distance_km / div)))


def extra_bag_fee(distance_km: int) -> int:
    for cap, fee, _label in EXTRA_BAG_RATES:
        if distance_km <= cap:
            return fee
    return 140


def upgrade_avios_cost(flight, fare_code: str) -> int:
    """Avios needed to move an Economy booking up to Business on its flight."""
    return int(round(fare_amount(flight, "BUS_CLASSIC") * 0.25))


def parse_date(value, fallback=None):
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except Exception:  # noqa: BLE001
        return fallback


def fmt_date(d) -> str:
    if isinstance(d, str):
        d = parse_date(d)
    return d.strftime("%a, %d %b %Y") if d else ""


def parse_hhmm(value: str):
    m = re.match(r"^(\d{1,2}):(\d{2})", value or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def minutes_between(dep: str, arr: str) -> int:
    d = parse_hhmm(dep)
    a = parse_hhmm(arr)
    if not d or not a:
        return 0
    mins = (a[0] * 60 + a[1]) - (d[0] * 60 + d[1])
    if mins <= 0:
        mins += 24 * 60
    return mins


def fmt_duration(mins: int) -> str:
    return f"{mins // 60}h {mins % 60:02d}m"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Airport(db.Model):
    __tablename__ = "airports"
    code = db.Column(db.String(3), primary_key=True)
    city = db.Column(db.String(120), nullable=False)
    airport_name = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(120), nullable=False)
    country_code = db.Column(db.String(2))
    region = db.Column(db.String(40))

    def label(self):
        return f"{self.city}, {self.country} ({self.code})"


class Destination(db.Model):
    __tablename__ = "destinations"
    iata = db.Column(db.String(10), primary_key=True)
    city = db.Column(db.String(120), nullable=False)
    country = db.Column(db.String(120), nullable=False)
    region = db.Column(db.String(40), nullable=False)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    card_image = db.Column(db.String(200))
    has_guide = db.Column(db.Boolean, default=False)
    title_h1 = db.Column(db.String(200))
    intro = db.Column(db.Text)
    overview_heading = db.Column(db.String(200))
    overview_text = db.Column(db.Text)
    attractions_heading = db.Column(db.String(200))
    attractions_text = db.Column(db.Text)
    activities_heading = db.Column(db.String(200))
    activities_text = db.Column(db.Text)
    dining_heading = db.Column(db.String(200))
    dining_text = db.Column(db.Text)
    shopping_heading = db.Column(db.String(200))
    shopping_text = db.Column(db.Text)
    hero_image = db.Column(db.String(200))
    overview_image = db.Column(db.String(200))
    attractions_image = db.Column(db.String(200))
    activities_image = db.Column(db.String(200))
    dining_image = db.Column(db.String(200))
    shopping_image = db.Column(db.String(200))
    h1_image = db.Column(db.String(200))
    h2_image = db.Column(db.String(200))
    square_image = db.Column(db.String(200))
    latitude = db.Column(db.String(40))
    longitude = db.Column(db.String(40))

    def detail_path(self):
        return f"/en/destinations/{self.slug}.html"


class Flight(db.Model):
    __tablename__ = "flights"
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    # route-lookup indexes are created by seed_data.py in a fixed order so the
    # generated database is byte-reproducible (create_all iterates a set)
    origin_code = db.Column(db.String(3), nullable=False)
    dest_code = db.Column(db.String(3), nullable=False)
    equipment = db.Column(db.String(3), nullable=False)
    dep_time = db.Column(db.String(5), nullable=False)
    arr_time = db.Column(db.String(5), nullable=False)
    distance_km = db.Column(db.Integer, nullable=False)

    @property
    def code(self):
        return f"QR{self.number:03d}"

    @property
    def equipment_name(self):
        return EQUIPMENT_NAMES.get(self.equipment, self.equipment)

    @property
    def duration_min(self):
        return minutes_between(self.dep_time, self.arr_time)

    def departure_at(self, day: date):
        h, m = parse_hhmm(self.dep_time)
        return datetime.combine(day, datetime.min.time()).replace(hour=h, minute=m)

    def arrival_at(self, day: date):
        h, m = parse_hhmm(self.arr_time)
        base = datetime.combine(day, datetime.min.time()).replace(hour=h, minute=m)
        if (h, m) < parse_hhmm(self.dep_time):
            base += timedelta(days=1)
        return base

    def cabins_available(self):
        if self.equipment == "388":
            return ["Economy", "Business", "First"]
        return ["Economy", "Business"]


class FlightStatus(db.Model):
    __tablename__ = "flight_statuses"
    id = db.Column(db.Integer, primary_key=True)
    flight_id = db.Column(db.Integer, db.ForeignKey("flights.id"), nullable=False)
    status_code = db.Column(db.String(12), nullable=False)
    dep_est = db.Column(db.String(30))
    arr_est = db.Column(db.String(30))
    dep_act = db.Column(db.String(30))
    arr_act = db.Column(db.String(30))

    flight = db.relationship("Flight")

    @property
    def status_text(self):
        return STATUS_TEXT.get(self.status_code, self.status_code)


class Aircraft(db.Model):
    __tablename__ = "aircraft"
    code = db.Column(db.String(20), primary_key=True)
    family = db.Column(db.String(10), nullable=False)
    description = db.Column(db.Text)
    seat_capacity = db.Column(db.String(60))
    qsuite = db.Column(db.Boolean, default=False)
    first_class = db.Column(db.Boolean, default=False)
    image = db.Column(db.String(200))
    seatmap = db.Column(db.Text)  # JSON layout spec

    def seatmap_spec(self):
        return json.loads(self.seatmap) if self.seatmap else {}

    def layout_rows(self):
        spec = self.seatmap_spec()
        rows = []
        for cab, block in (("First", spec.get("first")),
                           ("Business", spec.get("business")),
                           ("Economy", spec.get("economy"))):
            if not block:
                continue
            for r in range(block["rows"][0], block["rows"][1] + 1):
                rows.append({"row": r, "cabin": cab,
                             "cols": block["cols"],
                             "preferred": r in block.get("preferred_rows", [])})
        return rows


class Offer(db.Model):
    __tablename__ = "offers"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), nullable=False, unique=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(60))
    summary = db.Column(db.Text)
    description = db.Column(db.Text)
    image = db.Column(db.String(200))
    promo_code = db.Column(db.String(20))
    discount_line = db.Column(db.String(120))
    terms = db.Column(db.Text)
    valid_until = db.Column(db.String(30))
    featured = db.Column(db.Boolean, default=False)

    def detail_path(self):
        return f"/en/offers/{self.slug}.html"


class FAQ(db.Model):
    __tablename__ = "faqs"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(60), nullable=False)
    question = db.Column(db.String(300), nullable=False)
    answer = db.Column(db.Text, nullable=False)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=False)
    title = db.Column(db.String(10), default="Mr")
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    tier = db.Column(db.String(20), default="Burgundy")
    avios = db.Column(db.Integer, default=0)
    qpoints = db.Column(db.Integer, default=0)
    qcredits = db.Column(db.Integer, default=0)
    membership_no = db.Column(db.String(20), unique=True)
    country = db.Column(db.String(80))
    mobile = db.Column(db.String(40))
    joined = db.Column(db.String(20))

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def next_tier(self):
        idx = TIER_ORDER.index(self.tier) if self.tier in TIER_ORDER else 0
        if idx + 1 < len(TIER_ORDER):
            return TIER_ORDER[idx + 1]
        return None

    def qpoints_to_next(self):
        nxt = self.next_tier()
        if not nxt:
            return None
        return max(0, TIER_QPOINTS[nxt] - self.qpoints)


class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.Integer, primary_key=True)
    pnr = db.Column(db.String(6), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    pc_number = db.Column(db.String(20))
    contact_email = db.Column(db.String(200), nullable=False)
    contact_last_name = db.Column(db.String(80), nullable=False)
    cabin = db.Column(db.String(20), nullable=False)
    fare_type = db.Column(db.String(20), nullable=False)
    adults = db.Column(db.Integer, default=1)
    children = db.Column(db.Integer, default=0)
    extra_bags = db.Column(db.Integer, default=0)
    total_paid = db.Column(db.Integer, nullable=False)
    avios_redeemed = db.Column(db.Integer, default=0)
    promo_code = db.Column(db.String(20))
    card_last4 = db.Column(db.String(4))
    status = db.Column(db.String(20), default="confirmed")
    checked_in = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.String(30))

    legs = db.relationship("BookingLeg", backref="booking", cascade="all, delete-orphan")
    passengers = db.relationship("Passenger", backref="booking", cascade="all, delete-orphan")

    # ---- pricing -------------------------------------------------------
    def fare_subtotal(self):
        return sum(leg.fare_price for leg in self.legs)

    def seat_fees(self):
        return sum(leg.seat_fee for leg in self.legs)

    def bag_fees(self):
        if not self.extra_bags:
            return 0
        dist = max(leg.distance_km for leg in self.legs)
        return self.extra_bags * extra_bag_fee(dist)

    def promo_discount(self):
        if not self.promo_code:
            return 0
        offer = Offer.query.filter_by(promo_code=self.promo_code).first()
        if not offer or not offer.promo_code:
            return 0
        return int(round(self.fare_subtotal() * 0.10))

    def summary_line(self):
        first = self.legs[0] if self.legs else None
        if len(self.legs) > 1:
            return f"{first.origin_code} → {first.dest_code} (return)"
        return f"{first.origin_code} → {first.dest_code}" if first else ""


class BookingLeg(db.Model):
    __tablename__ = "booking_legs"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    flight_number = db.Column(db.Integer, nullable=False)
    origin_code = db.Column(db.String(3), nullable=False)
    dest_code = db.Column(db.String(3), nullable=False)
    leg_date = db.Column(db.String(10), nullable=False)
    dep_time = db.Column(db.String(5))
    arr_time = db.Column(db.String(5))
    equipment = db.Column(db.String(3))
    distance_km = db.Column(db.Integer, default=0)
    fare_price = db.Column(db.Integer, default=0)
    seat_fee = db.Column(db.Integer, default=0)
    gate = db.Column(db.String(6))

    @property
    def flight_code(self):
        return f"QR{self.flight_number:03d}"


class Passenger(db.Model):
    __tablename__ = "passengers"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    title = db.Column(db.String(10), default="Mr")
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    pax_type = db.Column(db.String(10), default="adult")
    seat_out = db.Column(db.String(6))
    seat_ret = db.Column(db.String(6))
    ticket_number = db.Column(db.String(20))


class Activity(db.Model):
    __tablename__ = "activities"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    avios = db.Column(db.Integer, default=0)
    qpoints = db.Column(db.Integer, default=0)
    description = db.Column(db.String(300), nullable=False)
    occurred_at = db.Column(db.String(20), nullable=False)


class Subscription(db.Model):
    __tablename__ = "subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), nullable=False)
    departure_city = db.Column(db.String(80))
    created_at = db.Column(db.String(20))


# ---------------------------------------------------------------------------
# Helpers: search, CSRF, template globals
# ---------------------------------------------------------------------------

STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
              "is", "it", "by", "with", "my", "do", "i", "can", "how"}


def tokenize(text):
    return [t for t in re.split(r"\W+", (text or "").lower())
            if t not in STOP_WORDS and len(t) > 1]


def scored_search(query, items, fields, limit=None):
    tokens = tokenize(query)
    if not tokens:
        return items
    scored = []
    for item in items:
        text = " ".join(str(getattr(item, f) or "") for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], str(getattr(pair[1], "city", ""))))
    out = [i for _s, i in scored]
    return out[:limit] if limit else out


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = os.urandom(16).hex()
    return session["csrf_token"]


@app.before_request
def protect_forms():
    if request.method == "POST":
        token = session.get("csrf_token")
        if not token or request.form.get("csrf_token") != token:
            abort(400, description="Invalid or missing CSRF token.")


def current_pc_user():
    uid = session.get("pc_user_id")
    return db.session.get(User, uid) if uid else None


@app.context_processor
def inject_globals():
    from datetime import timedelta as _td
    return {
        "csrf_token": csrf_token,
        "pc_user": current_pc_user(),
        "qr_nav": QR_NAV,
        "reference_date": MIRROR_REFERENCE_DATE,
        "now_str": MIRROR_REFERENCE_DATE.strftime("%d %b %Y"),
        "timedelta": _td,
    }


@app.template_filter("city_display")
def city_display_filter(value):
    """Airport picker-feed city strings ('London*heathrow*England*great
    britain*Gatwick*LGW') display as the primary city name, matching the
    live site's results header ('London (LHR)'); the full feed string stays
    in the data layer for search matching."""
    return str(value or "").split("*")[0].strip()


@app.template_filter("usd")
def usd_filter(value):
    try:
        return f"USD {int(value):,}"
    except Exception:  # noqa: BLE001
        return str(value)


@app.template_filter("fmtdate")
def fmtdate_filter(value):
    return fmt_date(value)


def flash_error(msg):
    flash(msg, "error")


def flash_ok(msg):
    flash(msg, "ok")


def generate_pnr():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        pnr = "".join(random.choice(alphabet) for _ in range(6))
        if not Booking.query.filter_by(pnr=pnr).first():
            return pnr


def gate_for(flight_number: int) -> str:
    return f"{chr(65 + flight_number % 6)}{flight_number % 40 + 1:02d}"


def find_flights(origin: str, dest: str):
    return (Flight.query.filter_by(origin_code=origin, dest_code=dest)
            .order_by(Flight.dep_time).all())


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.route("/_health")
def health():
    try:
        counts = {t: db.session.execute(db.select(db.func.count()).select_from(m)).scalar()
                  for t, m in (("airports", Airport), ("destinations", Destination),
                               ("flights", Flight), ("offers", Offer), ("users", User),
                               ("bookings", Booking))}
        return jsonify({"ok": True, "site": "qatar_airways", **counts})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)[:200]}), 500


# ---------------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------------


@app.route("/")
@app.route("/en/homepage.html")
def home():
    featured_dests = (Destination.query.filter_by(has_guide=True)
                      .order_by(Destination.city).limit(24).all())
    # a stable, city-diverse strip for the homepage carousel
    strip_codes = ["LHR", "CDG", "JFK", "SYD", "HND", "BKK", "CPT", "DXB",
                   "IST", "BCN", "MLE", "SIN"]
    strip = [d for c in strip_codes
             if (d := Destination.query.get(c)) is not None]
    offers = Offer.query.filter_by(featured=True).limit(3).all()
    # served-airport picker feed for the booking widget's city/airport
    # typeahead (the live widget's "Start typing to choose a city or airport")
    served = set()
    for origin, dest in db.session.query(Flight.origin_code, Flight.dest_code).distinct():
        served.update((origin, dest))
    airport_options = (Airport.query.filter(Airport.code.in_(sorted(served)))
                       .order_by(Airport.airport_name).all()) if served else []
    return render_template("index.html", featured_dests=featured_dests,
                           strip=strip, offers=offers,
                           airport_options=airport_options)


# ---------------------------------------------------------------------------
# Flight search & booking
# ---------------------------------------------------------------------------


@app.route("/en/search-results.html")
def search_results():
    origin = (request.args.get("from") or "").strip().upper()[:3]
    dest = (request.args.get("to") or "").strip().upper()[:3]
    depart = parse_date(request.args.get("depart"), MIRROR_REFERENCE_DATE + timedelta(days=14))
    ret = parse_date(request.args.get("return"))
    adults = max(1, min(9, int(request.args.get("adults") or 1)))
    children = max(0, min(6, int(request.args.get("children") or 0)))
    cabin = request.args.get("cabin") or "Economy"
    promo = (request.args.get("promo") or "").strip().upper()
    pax = adults + children

    origin_ap = Airport.query.get(origin)
    dest_ap = Airport.query.get(dest)
    if not origin_ap or not dest_ap:
        return render_template("search_results.html", error="route",
                               origin=origin, dest=dest), 400

    outbound = find_flights(origin, dest)
    inbound = find_flights(dest, origin) if ret else []

    promo_offer = None
    if promo:
        promo_offer = Offer.query.filter(
            Offer.promo_code == promo, Offer.promo_code != "").first()  # type: ignore[arg-type]

    def flight_view(flight, day):
        fares = {}
        for fc in fare_options_for_cabin(cabin):
            if cabin not in flight.cabins_available():
                continue
            per_pax = fare_amount(flight, fc)
            fares[fc] = {"per_pax": per_pax, "total": per_pax * pax}
        return {"flight": flight, "day": day, "fares": fares}

    ob_views = [flight_view(f, depart) for f in outbound]
    ib_views = [flight_view(f, ret) for f in inbound]
    return render_template(
        "search_results.html", origin=origin, dest=dest,
        origin_ap=origin_ap, dest_ap=dest_ap,
        depart=depart, ret=ret, adults=adults, children=children,
        cabin=cabin, pax=pax, promo=promo,
        promo_offer=promo_offer, outbound=ob_views, inbound=ib_views,
        fare_types=FARE_TYPES)


@app.route("/en/booking/select-return.html")
def select_return():
    """Round-trip step 2: pick the inbound flight after choosing the outbound."""
    q = request.args
    required = ("from", "to", "depart", "ret", "adults", "children", "cabin", "fare", "flight")
    if not all(q.get(k) for k in required):
        return redirect("/en/search-results.html")
    outbound = Flight.query.get(int(q["flight"]))
    if not outbound:
        abort(404)
    ret = parse_date(q["ret"])
    inbound = find_flights(q["to"], q["from"])
    return render_template("select_return.html", q=q, outbound=outbound,
                           inbound=inbound, ret=ret)


@app.route("/en/booking/passenger-details.html", methods=["GET", "POST"])
def passenger_details():
    if request.method == "GET":
        q = request.args
        required = ("from", "to", "depart", "adults", "children", "cabin", "fare", "flight")
        if not all(q.get(k) for k in required):
            return redirect("/en/search-results.html")
        flight = Flight.query.get(int(q["flight"]))
        if not flight:
            abort(404)
        ret_flight = Flight.query.get(int(q["ret_flight"])) if q.get("ret_flight") else None
        return render_template("passenger_details.html", q=q, flight=flight,
                               ret_flight=ret_flight)
    # POST: validate passenger details, stash, move to payment
    form = request.form
    adults = int(form.get("adults") or 1)
    children = int(form.get("children") or 0)
    errors = []
    pax = []
    for i in range(adults + children):
        first = (form.get(f"first_{i}") or "").strip()
        last = (form.get(f"last_{i}") or "").strip()
        if not first or not last:
            errors.append(f"Passenger {i + 1}: first and last name are required.")
        pax.append({"title": form.get(f"title_{i}") or "Mr",
                    "first": first, "last": last,
                    "type": "child" if i >= adults else "adult"})
    email = (form.get("email") or "").strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors.append("A valid contact email address is required.")
    mobile = (form.get("mobile") or "").strip()
    if not re.match(r"^\+?[0-9][0-9 ()-]{5,19}$", mobile):
        errors.append("A valid contact mobile number is required.")
    pc_number = (form.get("pc_number") or "").strip()
    if errors:
        flight = Flight.query.get(int(form.get("flight") or 0))
        return render_template("passenger_details.html", q=form, flight=flight,
                               errors=errors), 400
    session["booking_draft"] = {
        "from": form.get("from"), "to": form.get("to"),
        "depart": form.get("depart"), "ret": form.get("ret") or None,
        "adults": adults, "children": children,
        "cabin": form.get("cabin"), "fare": form.get("fare"),
        "flight": form.get("flight"), "ret_flight": form.get("ret_flight") or None,
        "email": email, "mobile": mobile, "pc_number": pc_number,
        "passengers": pax, "promo": form.get("promo") or None,
    }
    return redirect(url_for("payment"))


@app.route("/en/booking/payment.html", methods=["GET", "POST"])
def payment():
    draft = session.get("booking_draft")
    if not draft:
        return redirect("/en/search-results.html")
    flight = Flight.query.get(int(draft["flight"]))
    ret_flight = Flight.query.get(int(draft["ret_flight"])) if draft.get("ret_flight") else None
    pax = draft["adults"] + draft["children"]
    fare_code = draft["fare"]

    def leg_total(fl):
        return fare_amount(fl, fare_code) * pax

    subtotal = leg_total(flight) + (leg_total(ret_flight) if ret_flight else 0)
    promo_offer = None
    discount = 0
    if draft.get("promo"):
        promo_offer = Offer.query.filter_by(promo_code=draft["promo"]).first()
        if promo_offer and promo_offer.promo_code:
            discount = int(round(subtotal * 0.10))
    taxes = taxes_for(subtotal - discount)
    total = subtotal - discount + taxes

    if request.method == "GET":
        return render_template("payment.html", draft=draft, flight=flight,
                               ret_flight=ret_flight, pax=pax,
                               fare_name=FARE_TYPES[fare_code][1],
                               subtotal=subtotal, discount=discount, taxes=taxes,
                               total=total, promo_offer=promo_offer)
    # POST: validate card
    form = request.form
    card = re.sub(r"[ -]", "", form.get("card_number") or "")
    name = (form.get("card_name") or "").strip()
    errors = []
    if not re.match(r"^\d{15,16}$", card):
        errors.append("Card number must be 15 or 16 digits.")
    if not name:
        errors.append("Cardholder name is required.")
    exp = form.get("card_expiry") or ""
    try:
        exp_date = datetime.strptime(exp, "%m/%Y")
        if exp_date.date() < MIRROR_REFERENCE_DATE:
            errors.append("Card expiry must be in the future.")
    except ValueError:
        errors.append("Card expiry must be in MM/YYYY format.")
    if not re.match(r"^\d{3,4}$", form.get("card_cvv") or ""):
        errors.append("CVV must be 3 or 4 digits.")
    if errors:
        return render_template("payment.html", draft=draft, flight=flight,
                               ret_flight=ret_flight, pax=pax,
                               fare_name=FARE_TYPES[fare_code][1],
                               subtotal=subtotal, discount=discount,
                               taxes=taxes, total=total,
                               promo_offer=promo_offer, errors=errors), 400

    # persist the booking
    booking = Booking(
        pnr=generate_pnr(),
        contact_email=draft["email"],
        contact_last_name=draft["passengers"][0]["last"],
        cabin=draft["cabin"], fare_type=fare_code,
        adults=draft["adults"], children=draft["children"],
        total_paid=total, promo_code=draft.get("promo") or None,
        card_last4=card[-4:], created_at=MIRROR_REFERENCE_DATE.isoformat())
    member = None
    if draft.get("pc_number"):
        member = User.query.filter_by(membership_no=draft["pc_number"]).first()
        if member:
            booking.user_id = member.id
            booking.pc_number = member.membership_no
    elif current_pc_user():
        member = current_pc_user()
        booking.user_id = member.id
        booking.pc_number = member.membership_no

    def make_leg(fl, day):
        return BookingLeg(flight_number=fl.number,
                          origin_code=fl.origin_code, dest_code=fl.dest_code,
                          leg_date=day.isoformat(), dep_time=fl.dep_time,
                          arr_time=fl.arr_time, equipment=fl.equipment,
                          distance_km=fl.distance_km,
                          fare_price=fare_amount(fl, fare_code) * pax,
                          gate=gate_for(fl.number))

    booking.legs.append(make_leg(flight, parse_date(draft["depart"], MIRROR_REFERENCE_DATE)))
    if ret_flight and draft.get("ret"):
        booking.legs.append(make_leg(ret_flight, parse_date(draft["ret"])))
    for p in draft["passengers"]:
        booking.passengers.append(Passenger(title=p["title"], first_name=p["first"],
                                            last_name=p["last"], pax_type=p["type"],
                                            ticket_number=f"157-{random.randint(10**9, 10**10 - 1)}"))
    db.session.add(booking)

    # credit Avios + Qpoints when a Privilege Club number was recognised
    if member:
        avios = 0
        qpoints = 0
        for leg in booking.legs:
            avios += avios_for_distance(leg.distance_km, booking.cabin, member.tier)
            qpoints += qpoints_for_distance(leg.distance_km, booking.cabin)
        member.avios += avios
        member.qpoints += qpoints
        db.session.add(Activity(user_id=member.id, kind="earn",
                                avios=avios, qpoints=qpoints,
                                description=(f"Flight {booking.legs[0].flight_code} "
                                              f"{booking.legs[0].origin_code}→{booking.legs[0].dest_code} "
                                              f"({FARE_TYPES[fare_code][1]})"),
                                occurred_at=MIRROR_REFERENCE_DATE.isoformat()))
    db.session.commit()
    session.pop("booking_draft", None)
    return redirect(url_for("confirmation", pnr=booking.pnr))


@app.route("/en/booking/confirmation.html")
def confirmation():
    pnr = request.args.get("pnr")
    booking = Booking.query.filter_by(pnr=pnr).first()
    if not booking:
        abort(404)
    return render_template("confirmation.html", booking=booking)


# ---------------------------------------------------------------------------
# Manage booking
# ---------------------------------------------------------------------------


@app.route("/en/manage-booking.html", methods=["GET", "POST"])
def manage_booking():
    if request.method == "POST":
        pnr = (request.form.get("pnr") or "").strip().upper()
        last = (request.form.get("last_name") or "").strip().lower()
        booking = Booking.query.filter_by(pnr=pnr).first()
        if not booking or booking.contact_last_name.lower() != last:
            return render_template("manage_booking.html",
                                   error="No booking found for that reference and last name."), 404
        return redirect(f"/en/manage-booking/{pnr}.html")
    return render_template("manage_booking.html")


@app.route("/en/manage-booking/<pnr>.html", methods=["GET", "POST"])
def manage_booking_detail(pnr):
    booking = Booking.query.filter_by(pnr=pnr.upper()).first_or_404()
    leg = booking.legs[0]
    flight = Flight.query.filter_by(number=leg.flight_number).first()
    member = current_pc_user()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_bags":
            count = max(1, min(4, int(request.form.get("bags") or 1)))
            fee = count * extra_bag_fee(leg.distance_km)
            promo = (booking.promo_code or "").upper()
            if promo == "BAG15":
                fee = int(round(fee * 0.85))
            booking.extra_bags += count
            booking.total_paid += fee
            db.session.commit()
            flash_ok(f"{count} extra baggage piece(s) added. Fee charged: USD {fee}.")
        elif action == "cancel":
            if booking.status == "cancelled":
                flash_error("This booking is already cancelled.")
            else:
                booking.status = "cancelled"
                db.session.commit()
                flash_ok(f"Booking {booking.pnr} has been cancelled. Any refund is "
                         "processed to the original payment method.")
        elif action == "upgrade_avios":
            if not member or not booking.pc_number or booking.pc_number != member.membership_no:
                flash_error("Sign in with the Privilege Club account on this booking "
                            "to upgrade with Avios.")
            elif booking.cabin != "Economy":
                flash_error("Only Economy bookings can be upgraded with Avios.")
            else:
                cost = upgrade_avios_cost(flight, booking.fare_type)
                if member.avios < cost:
                    flash_error(f"This upgrade needs {cost:,} Avios; your balance is "
                                f"{member.avios:,}.")
                else:
                    member.avios -= cost
                    booking.cabin = "Business"
                    booking.avios_redeemed += cost
                    db.session.add(Activity(user_id=member.id, kind="redeem",
                                            avios=-cost, qpoints=0,
                                            description=(f"Upgrade to Business Class on "
                                                         f"{leg.flight_code} "
                                                         f"({leg.origin_code}→{leg.dest_code})"),
                                            occurred_at=MIRROR_REFERENCE_DATE.isoformat()))
                    db.session.commit()
                    flash_ok(f"Upgraded to Business Class using {cost:,} Avios.")
        elif action == "seats":
            return redirect(f"/en/check-in/{booking.pnr}.html")
        return redirect(f"/en/manage-booking/{booking.pnr}.html")

    upgrade_cost = upgrade_avios_cost(flight, booking.fare_type) if flight else None
    return render_template("manage_booking_detail.html", booking=booking,
                           flight=flight, member=member,
                           upgrade_cost=upgrade_cost,
                           bag_fee=extra_bag_fee(leg.distance_km))


# ---------------------------------------------------------------------------
# Check-in & boarding pass
# ---------------------------------------------------------------------------


@app.route("/en/check-in.html", methods=["GET", "POST"])
def checkin():
    if request.method == "POST":
        pnr = (request.form.get("pnr") or "").strip().upper()
        last = (request.form.get("last_name") or "").strip().lower()
        booking = Booking.query.filter_by(pnr=pnr).first()
        if not booking or booking.contact_last_name.lower() != last:
            return render_template("checkin.html",
                                   error="No booking found for that reference and last name."), 404
        if booking.status == "cancelled":
            return render_template("checkin.html",
                                   error="Cancelled bookings cannot be checked in."), 404
        return redirect(f"/en/check-in/{pnr}.html")
    return render_template("checkin.html")


def _seatmap_for_leg(leg, booking):
    flight = Flight.query.filter_by(number=leg.flight_number).first()
    aircraft = Aircraft.query.filter_by(code=EQUIPMENT_NAMES.get(flight.equipment, "")).first() \
        if flight else None
    if not aircraft:
        aircraft = Aircraft.query.filter_by(code="Airbus A350-900").first()
    rows = aircraft.layout_rows()
    taken = set()
    for b in Booking.query.filter(Booking.status == "confirmed").all():
        for other_leg in b.legs:
            if (other_leg.flight_number == leg.flight_number
                    and other_leg.leg_date == leg.leg_date):
                for p in b.passengers:
                    seat = p.seat_out if len(b.legs) == 1 else p.seat_out
                    if seat:
                        taken.add(seat)
    for p in booking.passengers:
        seat = p.seat_out or p.seat_ret
        if seat:
            taken.discard(seat)
    return aircraft, rows, taken


@app.route("/en/check-in/<pnr>.html", methods=["GET", "POST"])
def checkin_seats(pnr):
    booking = Booking.query.filter_by(pnr=pnr.upper()).first_or_404()
    if booking.status == "cancelled":
        return redirect("/en/check-in.html")
    leg = booking.legs[0]
    ret_leg = booking.legs[1] if len(booking.legs) > 1 else None
    aircraft, rows, taken = _seatmap_for_leg(leg, booking)

    if request.method == "POST":
        fee_total = 0
        for p in booking.passengers:
            seat = (request.form.get(f"seat_{p.id}") or "").strip().upper()
            if not re.match(r"^\d{1,2}[A-K]$", seat):
                flash_error(f"Select a valid seat for {p.first_name} {p.last_name}.")
                return redirect(f"/en/check-in/{booking.pnr}.html")
            row_num = int(re.match(r"^(\d+)", seat).group(1))  # type: ignore[union-attr]
            spec_row = next((r for r in rows if r["row"] == row_num), None)
            if not spec_row or seat[-1] not in spec_row["cols"]:
                flash_error(f"Seat {seat} does not exist on this aircraft.")
                return redirect(f"/en/check-in/{booking.pnr}.html")
            if seat in taken:
                flash_error(f"Seat {seat} is already taken.")
                return redirect(f"/en/check-in/{booking.pnr}.html")
            if spec_row["preferred"] and booking.cabin != "Business":
                fee_total += PREFERRED_SEAT_FEE
            p.seat_out = seat
            if ret_leg:
                seat_ret = (request.form.get(f"seat_ret_{p.id}") or "").strip().upper()
                if seat_ret:
                    p.seat_ret = seat_ret
        leg.seat_fee += fee_total
        booking.total_paid += fee_total
        booking.checked_in = True
        db.session.commit()
        flash_ok(f"Check-in complete for booking {booking.pnr}. "
                 f"Seat fees charged: USD {fee_total}.")
        return redirect(f"/en/check-in/{booking.pnr}/boarding-pass.html")

    return render_template("checkin_seats.html", booking=booking, leg=leg,
                           ret_leg=ret_leg, aircraft=aircraft, rows=rows,
                           taken=taken, seat_fee=PREFERRED_SEAT_FEE)


@app.route("/en/check-in/<pnr>/boarding-pass.html")
def boarding_pass(pnr):
    booking = Booking.query.filter_by(pnr=pnr.upper()).first_or_404()
    if not booking.checked_in:
        return redirect(f"/en/check-in/{booking.pnr}.html")
    leg = booking.legs[0]
    dep = leg.dep_time[:5] if leg.dep_time else ""
    # boarding opens 40 minutes before departure, matching the upstream
    # boarding-pass convention
    if dep:
        minutes = (int(dep[:2]) * 60 + int(dep[3:5]) - 40) % (24 * 60)
        boarding = f"{minutes // 60:02d}:{minutes % 60:02d}"
    else:
        boarding = ""
    return render_template("boarding_pass.html", booking=booking, leg=leg,
                           boarding_time=boarding)


# ---------------------------------------------------------------------------
# Flight status
# ---------------------------------------------------------------------------


@app.route("/en/flight-status.html")
def flight_status():
    mode = request.args.get("mode")
    results = []
    query = {}
    if mode == "number":
        num = request.args.get("number", "").strip()
        m = re.match(r"^(?:QR)?(\d{1,4})$", num, re.I)
        day = parse_date(request.args.get("date"), MIRROR_REFERENCE_DATE)
        if m:
            query = {"number": num, "date": day}
            flights = Flight.query.filter_by(number=int(m.group(1))).all()
            results = _status_rows(flights, day)
    elif mode == "route":
        origin = (request.args.get("from") or "").strip().upper()
        dest = (request.args.get("to") or "").strip().upper()
        day = parse_date(request.args.get("date"), MIRROR_REFERENCE_DATE)
        query = {"from": origin, "to": dest, "date": day}
        flights = Flight.query.filter_by(origin_code=origin, dest_code=dest).all()
        results = _status_rows(flights, day)
    return render_template("flight_status.html", mode=mode, results=results,
                           query=query, status_text=STATUS_TEXT)


def _status_rows(flights, day):
    rows = []
    for f in flights:
        status = None
        if day == MIRROR_REFERENCE_DATE:
            status = FlightStatus.query.filter_by(flight_id=f.id).first()
        rows.append({
            "flight": f, "date": day,
            "status": status,
            "status_text": (status.status_text if status else
                            ("Scheduled" if day >= MIRROR_REFERENCE_DATE else "Scheduled")),
        })
    rows.sort(key=lambda r: r["flight"].dep_time)
    return rows


# ---------------------------------------------------------------------------
# Destinations
# ---------------------------------------------------------------------------

REGION_LABELS = [
    ("africa", "Africa"),
    ("asia", "Asia and the Pacific"),
    ("europe", "Europe"),
    ("themiddleeast", "Middle East"),
    ("theamericas", "The Americas"),
]


@app.route("/en/destinations.html")
def destinations():
    region = request.args.get("region", "").strip()
    q = request.args.get("q", "").strip()
    page = max(1, int(request.args.get("page") or 1))
    per_page = 24
    query = Destination.query
    if region:
        query = query.filter_by(region=region)
    items = query.order_by(Destination.city).all()
    if q:
        items = scored_search(q, items, ["city", "country", "iata"])
    total = len(items)
    items = items[(page - 1) * per_page: page * per_page]
    pages = max(1, math.ceil(total / per_page))
    return render_template("destinations.html", items=items, region=region,
                           q=q, page=page, pages=pages, total=total,
                           regions=REGION_LABELS)


@app.route("/en/destinations/<slug>.html")
def destination_detail(slug):
    dest = Destination.query.filter_by(slug=slug).first_or_404()
    if not dest.has_guide:
        # cards without a guide page behave like the live site: land on the
        # flight search for that city
        return redirect(f"/en/search-results.html?from=DOH&to={dest.iata}")
    related = (Destination.query.filter(Destination.region == dest.region,
                                        Destination.iata != dest.iata,
                                        Destination.has_guide)
               .order_by(Destination.city).limit(6).all())
    # The guide payload's IATA can differ from the picker feed's code for the
    # same city (Alexandria: repository says HBE, the schedule feed uses ALY).
    # Resolve the guide's flight-search button to the city's served airport so
    # the link never dead-ends on the route-error page.
    search_code = dest.iata
    if not Airport.query.get(search_code) and dest.country:
        for ap in Airport.query.filter_by(country=dest.country):
            if ap.city.split("*")[0].strip().lower() == (dest.city or "").strip().lower():
                search_code = ap.code
                break
    return render_template("destination_detail.html", dest=dest, related=related,
                           search_code=search_code)


# ---------------------------------------------------------------------------
# Offers
# ---------------------------------------------------------------------------


@app.route("/en/offers.html")
def offers():
    items = Offer.query.order_by(Offer.id).all()
    return render_template("offers.html", items=items)


@app.route("/en/offers/<slug>.html")
def offer_detail(slug):
    offer = Offer.query.filter_by(slug=slug).first_or_404()
    others = Offer.query.filter(Offer.id != offer.id).limit(3).all()
    return render_template("offer_detail.html", offer=offer, others=others)


# ---------------------------------------------------------------------------
# Privilege Club
# ---------------------------------------------------------------------------


@app.route("/en/Privilege-Club/login.html", methods=["GET", "POST"])
def pc_login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            return render_template("pc_login.html",
                                   error="Incorrect email or password. Please try again."), 401
        session["pc_user_id"] = user.id
        return redirect(url_for("pc_dashboard"))
    return render_template("pc_login.html")


@app.route("/en/Privilege-Club/join.html", methods=["GET", "POST"])
def pc_join():
    if request.method == "POST":
        form = request.form
        email = (form.get("email") or "").strip().lower()
        errors = []
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors.append("Please provide a valid email address.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists. Please log in instead.")
        password = form.get("password") or ""
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        first = (form.get("first_name") or "").strip()
        last = (form.get("last_name") or "").strip()
        if not first or not last:
            errors.append("First and last name are required.")
        if errors:
            return render_template("pc_join.html", errors=errors), 400
        user = User(email=email, password_hash=generate_password_hash(password),
                    title=form.get("title") or "Mr", first_name=first, last_name=last,
                    tier="Burgundy", avios=0, qpoints=0, qcredits=0,
                    country=(form.get("country") or "").strip(),
                    mobile=(form.get("mobile") or "").strip(),
                    joined=MIRROR_REFERENCE_DATE.isoformat())
        db.session.add(user)
        db.session.flush()
        user.membership_no = f"QRPC{user.id:07d}"
        db.session.commit()
        session["pc_user_id"] = user.id
        flash_ok(f"Welcome to Privilege Club! Your membership number is {user.membership_no}.")
        return redirect(url_for("pc_dashboard"))
    return render_template("pc_join.html")


@app.route("/en/Privilege-Club/logout.html", methods=["POST"])
def pc_logout():
    session.pop("pc_user_id", None)
    return redirect(url_for("home"))


@app.route("/en/Privilege-Club/membership-tiers.html")
def pc_tiers():
    return render_template("pc_tiers.html", tiers=TIER_ORDER,
                            tier_bonuses=TIER_BONUS, tier_qpoints=TIER_QPOINTS,
                            tier_retain=TIER_RETAIN)


def _require_member():
    user = current_pc_user()
    if not user:
        return None
    return user


@app.route("/en/Privilege-Club/dashboard.html")
def pc_dashboard():
    user = current_pc_user()
    if not user:
        return redirect(url_for("pc_login"))
    bookings = (Booking.query.filter_by(pc_number=user.membership_no)
                .order_by(Booking.id).all())
    activities = (Activity.query.filter_by(user_id=user.id)
                  .order_by(Activity.id.desc()).limit(12).all())
    return render_template("pc_dashboard.html", user=user, bookings=bookings,
                           activities=activities, tier_qpoints=TIER_QPOINTS,
                           tier_retain=TIER_RETAIN)


@app.route("/en/Privilege-Club/dashboard/my-profile.html", methods=["GET", "POST"])
def pc_profile():
    user = current_pc_user()
    if not user:
        return redirect(url_for("pc_login"))
    if request.method == "POST":
        form = request.form
        first = (form.get("first_name") or "").strip()
        last = (form.get("last_name") or "").strip()
        email = (form.get("email") or "").strip().lower()
        if not first or not last:
            flash_error("First and last name are required.")
        elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            flash_error("Please provide a valid email address.")
        elif User.query.filter(User.email == email, User.id != user.id).first():
            flash_error("That email is already used by another account.")
        else:
            user.first_name = first
            user.last_name = last
            user.email = email
            user.title = form.get("title") or user.title
            user.country = (form.get("country") or "").strip()
            user.mobile = (form.get("mobile") or "").strip()
            db.session.commit()
            flash_ok("Your profile has been updated.")
        return redirect(url_for("pc_profile"))
    return render_template("pc_profile.html", user=user)


@app.route("/en/Privilege-Club/dashboard/my-activities.html")
def pc_activities():
    user = current_pc_user()
    if not user:
        return redirect(url_for("pc_login"))
    activities = (Activity.query.filter_by(user_id=user.id)
                  .order_by(Activity.id.desc()).all())
    return render_template("pc_activities.html", user=user, activities=activities)


@app.route("/en/Privilege-Club/avios-calculator.html", methods=["GET", "POST"])
def pc_calculator():
    result = None
    origin = dest = cabin = tier = None
    if request.method == "POST":
        origin = (request.form.get("from") or "").strip().upper()[:3]
        dest = (request.form.get("to") or "").strip().upper()[:3]
        cabin = request.form.get("cabin") or "Economy"
        tier = request.form.get("tier") or "Burgundy"
        fl = (Flight.query.filter_by(origin_code=origin, dest_code=dest)
              .order_by(Flight.number).first())
        if not fl:
            return render_template("pc_calculator.html", error="route",
                                   origin=origin, dest=dest), 400
        avios = avios_for_distance(fl.distance_km, cabin, tier)
        qpoints = qpoints_for_distance(fl.distance_km, cabin)
        result = {"flight": fl, "avios": avios, "qpoints": qpoints,
                  "bonus_pct": int(TIER_BONUS.get(tier, 0) * 100)}
    return render_template("pc_calculator.html", result=result,
                           origin=origin, dest=dest, cabin=cabin, tier=tier,
                           tiers=TIER_ORDER)


# ---------------------------------------------------------------------------
# Baggage
# ---------------------------------------------------------------------------

BAGGAGE_TABLE = [
    ("Economy Lite", "1 piece up to 23kg (50lb)", "20kg (44lb)"),
    ("Economy Classic", "2 pieces up to 23kg (50lb) each", "25kg (55lb)"),
    ("Economy Convenience", "2 pieces up to 23kg (50lb) each", "30kg (66lb)"),
    ("Economy Comfort", "2 pieces up to 23kg (50lb) each", "35kg (77lb)"),
    ("Business Lite", "2 pieces up to 32kg (70lb) each", "40kg (88lb)"),
    ("Business Classic", "2 pieces up to 32kg (70lb) each", "40kg (88lb)"),
    ("Business Comfort", "2 pieces up to 32kg (70lb) each", "40kg (88lb)"),
    ("Business Elite", "2 pieces up to 32kg (70lb) each", "40kg (88lb)"),
    ("First Elite", "2 pieces up to 32kg (70lb) each", "50kg (110lb)"),
]


@app.route("/en/baggage.html")
def baggage():
    fare = request.args.get("fare", "").strip()
    route_type = request.args.get("route", "").strip()
    lookup = None
    if fare and route_type:
        for name, pieces, weight in BAGGAGE_TABLE:
            if name == fare:
                lookup = {"fare": name,
                          "allowance": pieces if route_type == "americas" else weight}
                break
    return render_template("baggage.html", table=BAGGAGE_TABLE, lookup=lookup,
                           fare=fare, route_type=route_type,
                           extra_bag_rates=EXTRA_BAG_RATES)


# ---------------------------------------------------------------------------
# Fleet
# ---------------------------------------------------------------------------


@app.route("/en/our-fleet.html")
def fleet():
    aircraft = Aircraft.query.order_by(Aircraft.family, Aircraft.code).all()
    return render_template("fleet.html", aircraft=aircraft)


@app.route("/en/our-fleet/<slug>.html")
def fleet_detail(slug):
    # slugs swap only the first hyphen: Airbus-A350-900 -> Airbus A350-900
    aircraft = Aircraft.query.filter_by(code=slug.replace("-", " ", 1)).first()
    if not aircraft:
        aircraft = Aircraft.query.filter(
            Aircraft.code == slug.replace("_", " ", 1)).first()
    if not aircraft:
        abort(404)
    return render_template("fleet_detail.html", a=aircraft)


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


@app.route("/en/help.html")
def help_hub():
    q = request.args.get("q", "").strip()
    cat = request.args.get("cat", "").strip()
    items = FAQ.query.order_by(FAQ.category, FAQ.id).all()
    if cat:
        items = [i for i in items if i.category == cat]
    if q:
        items = scored_search(q, items, ["question", "answer", "category"])
    categories = sorted({f.category for f in FAQ.query.all()})
    return render_template("help.html", items=items, q=q, cat=cat,
                           categories=categories)


# ---------------------------------------------------------------------------
# Newsletter subscribe (homepage footer form)
# ---------------------------------------------------------------------------


@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = (request.form.get("email") or "").strip().lower()
    city = (request.form.get("departure_city") or "").strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        flash_error("Please provide a valid email address.")
    elif Subscription.query.filter_by(email=email).first():
        flash_error("This email address is already subscribed.")
    else:
        db.session.add(Subscription(email=email, departure_city=city,
                                    created_at=MIRROR_REFERENCE_DATE.isoformat()))
        db.session.commit()
        flash_ok("Thank you for subscribing. Our latest offers are on their way.")
    return redirect(request.form.get("next") or url_for("home"))


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


@app.errorhandler(404)
def not_found(_err):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()
    from seed_data import seed_database, seed_benchmark_users  # noqa: E402

    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
