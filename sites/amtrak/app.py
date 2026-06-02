import json
import os
import re
import string
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace

from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask import Flask

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "amtrak.db"
MIRROR_REFERENCE_DATE = datetime(2026, 4, 18, 8, 0, 0)
SERVICE_START_DATE = date(2026, 4, 14)
SERVICE_END_DATE = date(2026, 4, 25)
STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
FLOW_KEY = "amtrak_booking_flow"
SEARCH_KEY = "amtrak_search_state"
MULTI_KEY = "amtrak_multi_city_state"
LOOKUP_KEY = "amtrak_lookup_codes"
BENCHMARK_PASSWORD = "TestPass123!"

app = Flask(__name__, instance_path=str(BASE_DIR / "instance"))
app.config["SECRET_KEY"] = "webharbor-amtrak-demo-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to continue with this Amtrak demo mirror."


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(120), default="")
    first_name = db.Column(db.String(80), default="")
    last_name = db.Column(db.String(80), default="")
    phone = db.Column(db.String(40), default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(40), default="")
    preferred_station_code = db.Column(db.String(8), db.ForeignKey("stations.code"))
    rewards_member_no = db.Column(db.String(24), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship("Booking", backref="user", lazy=True, cascade="all, delete-orphan")
    passengers = db.relationship("Passenger", backref="user", lazy=True, cascade="all, delete-orphan")
    reward_account = db.relationship(
        "RewardAccount",
        backref="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    searches = db.relationship("SearchLog", backref="user", lazy=True, cascade="all, delete-orphan")
    preferred_station = db.relationship("Station", foreign_keys=[preferred_station_code])

    def set_password(self, raw_password):
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password):
        return bcrypt.check_password_hash(self.password_hash, raw_password)

    @property
    def full_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        if full:
            return full
        return self.display_name or self.email.split("@")[0]


class City(db.Model):
    __tablename__ = "cities"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(40), default="")
    region = db.Column(db.String(40), default="")
    hero_image = db.Column(db.String(240), default="")
    blurb = db.Column(db.Text, default="")
    highlight_fact = db.Column(db.String(240), default="")
    featured = db.Column(db.Boolean, default=False)

    stations = db.relationship("Station", backref="city", lazy=True)
    deals = db.relationship("Deal", backref="city", lazy=True)

    @property
    def display_name(self):
        return f"{self.name}, {self.state}" if self.state else self.name


class Station(db.Model):
    __tablename__ = "stations"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False, index=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=False)
    name = db.Column(db.String(140), nullable=False)
    city_name = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(40), nullable=False)
    region = db.Column(db.String(40), default="")
    address = db.Column(db.String(220), default="")
    platform_note = db.Column(db.String(140), default="")
    parking_note = db.Column(db.String(140), default="")
    amenities_json = db.Column(db.Text, default="[]")
    icon_path = db.Column(db.String(240), default="")
    hero_image = db.Column(db.String(240), default="")
    hours_text = db.Column(db.String(160), default="")
    baggage_text = db.Column(db.String(160), default="")
    accessibility_text = db.Column(db.String(160), default="")
    map_blurb = db.Column(db.Text, default="")
    is_hub = db.Column(db.Boolean, default=False)
    has_lounge = db.Column(db.Boolean, default=False)
    has_checked_baggage = db.Column(db.Boolean, default=False)

    @property
    def amenities(self):
        try:
            return json.loads(self.amenities_json or "[]")
        except Exception:
            return []

    @property
    def label(self):
        return f"{self.city_name} - {self.name} ({self.code})"


class Route(db.Model):
    __tablename__ = "routes"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    tagline = db.Column(db.String(180), default="")
    description = db.Column(db.Text, default="")
    route_type = db.Column(db.String(40), default="")
    service_level = db.Column(db.String(40), default="")
    total_duration_minutes = db.Column(db.Integer, default=0)
    origin_code = db.Column(db.String(8), db.ForeignKey("stations.code"), nullable=False)
    destination_code = db.Column(db.String(8), db.ForeignKey("stations.code"), nullable=False)
    overnight = db.Column(db.Boolean, default=False)
    featured = db.Column(db.Boolean, default=False)
    frequency_note = db.Column(db.String(160), default="")
    hero_image = db.Column(db.String(240), default="")
    map_image = db.Column(db.String(240), default="")
    onboard_features_json = db.Column(db.Text, default="[]")

    stops = db.relationship(
        "RouteStop",
        backref="route",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="RouteStop.stop_order",
    )
    trains = db.relationship("Train", backref="route", lazy=True, cascade="all, delete-orphan")
    trips = db.relationship("Trip", backref="route", lazy=True, cascade="all, delete-orphan")
    alerts = db.relationship("ServiceAlert", backref="route", lazy=True)
    deals = db.relationship("Deal", backref="route", lazy=True)
    origin_station = db.relationship("Station", foreign_keys=[origin_code])
    destination_station = db.relationship("Station", foreign_keys=[destination_code])

    @property
    def onboard_features(self):
        try:
            return json.loads(self.onboard_features_json or "[]")
        except Exception:
            return []


class RouteStop(db.Model):
    __tablename__ = "route_stops"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"), nullable=False)
    station_code = db.Column(db.String(8), db.ForeignKey("stations.code"), nullable=False)
    stop_order = db.Column(db.Integer, default=0)
    arrival_offset_minutes = db.Column(db.Integer, default=0)
    departure_offset_minutes = db.Column(db.Integer, default=0)
    dwell_minutes = db.Column(db.Integer, default=0)

    station = db.relationship("Station", foreign_keys=[station_code])


class Train(db.Model):
    __tablename__ = "trains"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"), nullable=False)
    number = db.Column(db.String(12), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    direction = db.Column(db.String(40), default="outbound")
    departure_slot = db.Column(db.String(20), default="")
    equipment = db.Column(db.String(120), default="")
    has_wifi = db.Column(db.Boolean, default=True)
    has_cafe = db.Column(db.Boolean, default=True)
    has_dining = db.Column(db.Boolean, default=False)
    has_sleepers = db.Column(db.Boolean, default=False)
    has_quiet_car = db.Column(db.Boolean, default=False)
    image_path = db.Column(db.String(240), default="")

    trips = db.relationship("Trip", backref="train", lazy=True)


class Trip(db.Model):
    __tablename__ = "trips"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"), nullable=False)
    train_id = db.Column(db.Integer, db.ForeignKey("trains.id"), nullable=False)
    service_date = db.Column(db.Date, nullable=False, index=True)
    direction = db.Column(db.String(40), default="outbound")
    start_station_code = db.Column(db.String(8), db.ForeignKey("stations.code"), nullable=False)
    end_station_code = db.Column(db.String(8), db.ForeignKey("stations.code"), nullable=False)
    departure_dt = db.Column(db.DateTime, nullable=False)
    arrival_dt = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=0)
    base_fare = db.Column(db.Float, default=0.0)
    status_label = db.Column(db.String(60), default="Scheduled")
    delay_minutes = db.Column(db.Integer, default=0)
    boarding_track = db.Column(db.String(20), default="")
    service_note = db.Column(db.String(180), default="")
    is_featured = db.Column(db.Boolean, default=False)
    has_sleepers = db.Column(db.Boolean, default=False)

    start_station = db.relationship("Station", foreign_keys=[start_station_code])
    end_station = db.relationship("Station", foreign_keys=[end_station_code])
    segments = db.relationship(
        "TripSegment",
        backref="trip",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="TripSegment.leg_order",
    )
    fare_options = db.relationship(
        "FareOption",
        backref="trip",
        lazy=True,
        cascade="all, delete-orphan",
    )
    sleeper_rooms = db.relationship(
        "SleeperRoom",
        backref="trip",
        lazy=True,
        cascade="all, delete-orphan",
    )

    @property
    def overnight_label(self):
        return "Overnight" if self.has_sleepers or self.route.overnight else "Day trip"


class TripSegment(db.Model):
    __tablename__ = "trip_segments"

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    leg_order = db.Column(db.Integer, default=0)
    from_station_code = db.Column(db.String(8), db.ForeignKey("stations.code"), nullable=False)
    to_station_code = db.Column(db.String(8), db.ForeignKey("stations.code"), nullable=False)
    depart_dt = db.Column(db.DateTime, nullable=False)
    arrive_dt = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=0)

    from_station = db.relationship("Station", foreign_keys=[from_station_code])
    to_station = db.relationship("Station", foreign_keys=[to_station_code])


class FareClass(db.Model):
    __tablename__ = "fare_classes"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
    description = db.Column(db.Text, default="")
    rules_change = db.Column(db.String(180), default="")
    rules_refund = db.Column(db.String(180), default="")
    seat_type = db.Column(db.String(80), default="")
    points_multiplier = db.Column(db.Float, default=1.0)
    color = db.Column(db.String(20), default="slate")
    sort_order = db.Column(db.Integer, default=0)

    fare_options = db.relationship("FareOption", backref="fare_class", lazy=True)


class FareOption(db.Model):
    __tablename__ = "fare_options"

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    fare_class_id = db.Column(db.Integer, db.ForeignKey("fare_classes.id"), nullable=False)
    multiplier = db.Column(db.Float, default=1.0)
    availability = db.Column(db.Integer, default=0)
    accessible_available = db.Column(db.Boolean, default=False)
    reward_points_base = db.Column(db.Integer, default=0)
    summary = db.Column(db.String(180), default="")


class SleeperRoom(db.Model):
    __tablename__ = "sleeper_rooms"

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    room_type = db.Column(db.String(40), default="roomette")
    name = db.Column(db.String(80), nullable=False)
    occupancy = db.Column(db.Integer, default=2)
    price_delta = db.Column(db.Float, default=0.0)
    availability = db.Column(db.Integer, default=0)
    meals_included = db.Column(db.Boolean, default=True)
    accessible = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text, default="")
    image_path = db.Column(db.String(240), default="")


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    booking_code = db.Column(db.String(12), unique=True, nullable=False, index=True)
    trip_type = db.Column(db.String(30), default="one-way")
    status = db.Column(db.String(30), default="Confirmed")
    total_amount = db.Column(db.Float, default=0.0)
    reward_points_earned = db.Column(db.Integer, default=0)
    contact_email = db.Column(db.String(120), default="")
    contact_phone = db.Column(db.String(40), default="")
    origin_code = db.Column(db.String(8), default="")
    destination_code = db.Column(db.String(8), default="")
    departure_date = db.Column(db.Date)
    return_date = db.Column(db.Date)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    passengers = db.relationship("Passenger", backref="booking", lazy=True, cascade="all, delete-orphan")
    tickets = db.relationship("Ticket", backref="booking", lazy=True, cascade="all, delete-orphan")
    segments = db.relationship("BookingSegment", backref="booking", lazy=True, cascade="all, delete-orphan")
    payment = db.relationship("PaymentMock", backref="booking", uselist=False, cascade="all, delete-orphan")

    @property
    def is_upcoming(self):
        if not self.departure_date:
            return False
        return self.departure_date >= MIRROR_REFERENCE_DATE.date() and self.status not in {"Cancelled", "Completed"}


class Passenger(db.Model):
    __tablename__ = "passengers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"))
    first_name = db.Column(db.String(80), default="")
    last_name = db.Column(db.String(80), default="")
    passenger_type = db.Column(db.String(40), default="Adult")
    age_band = db.Column(db.String(40), default="18+")
    accessibility_need = db.Column(db.String(120), default="")
    seat_preference = db.Column(db.String(40), default="")
    rewards_number = db.Column(db.String(24), default="")
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    is_saved_profile = db.Column(db.Boolean, default=False)

    tickets = db.relationship("Ticket", backref="passenger", lazy=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    passenger_id = db.Column(db.Integer, db.ForeignKey("passengers.id"), nullable=False)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    fare_class_id = db.Column(db.Integer, db.ForeignKey("fare_classes.id"), nullable=False)
    accommodation_type = db.Column(db.String(80), default="Coach Seat")
    seat_or_room = db.Column(db.String(80), default="")
    qr_token = db.Column(db.String(60), default="")
    status = db.Column(db.String(40), default="Issued")

    trip = db.relationship("Trip")
    fare_class = db.relationship("FareClass")


class BookingSegment(db.Model):
    __tablename__ = "booking_segments"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    leg_order = db.Column(db.Integer, default=0)
    route_name = db.Column(db.String(140), default="")
    train_number = db.Column(db.String(20), default="")
    origin_code = db.Column(db.String(8), default="")
    destination_code = db.Column(db.String(8), default="")
    depart_dt = db.Column(db.DateTime, nullable=False)
    arrive_dt = db.Column(db.DateTime, nullable=False)
    fare_class_name = db.Column(db.String(80), default="")
    accommodation_type = db.Column(db.String(80), default="")

    trip = db.relationship("Trip")


class PaymentMock(db.Model):
    __tablename__ = "payment_mocks"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False, unique=True)
    payment_label = db.Column(db.String(120), default="")
    amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(40), default="Approved")
    approval_code = db.Column(db.String(20), default="")
    charged_at = db.Column(db.DateTime, default=datetime.utcnow)


class RewardAccount(db.Model):
    __tablename__ = "reward_accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    member_number = db.Column(db.String(24), unique=True, nullable=False, index=True)
    tier = db.Column(db.String(40), default="Member")
    points_balance = db.Column(db.Integer, default=0)
    points_ytd = db.Column(db.Integer, default=0)
    status_credits = db.Column(db.Integer, default=0)
    preferred_station_code = db.Column(db.String(8), db.ForeignKey("stations.code"))

    activities = db.relationship(
        "RewardActivity",
        backref="reward_account",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="desc(RewardActivity.posted_at)",
    )
    preferred_station = db.relationship("Station", foreign_keys=[preferred_station_code])


class RewardActivity(db.Model):
    __tablename__ = "reward_activities"

    id = db.Column(db.Integer, primary_key=True)
    reward_account_id = db.Column(db.Integer, db.ForeignKey("reward_accounts.id"), nullable=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(180), default="")
    points_delta = db.Column(db.Integer, default=0)
    balance_after = db.Column(db.Integer, default=0)
    booking_code = db.Column(db.String(12), default="")
    category = db.Column(db.String(40), default="Travel")


class ServiceAlert(db.Model):
    __tablename__ = "service_alerts"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    severity = db.Column(db.String(40), default="Advisory")
    scope_type = db.Column(db.String(40), default="route")
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"))
    station_code = db.Column(db.String(8), db.ForeignKey("stations.code"))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    message = db.Column(db.Text, default="")
    next_step = db.Column(db.String(180), default="")
    badge_icon = db.Column(db.String(120), default="")
    active = db.Column(db.Boolean, default=True)

    station = db.relationship("Station", foreign_keys=[station_code])


class Deal(db.Model):
    __tablename__ = "deals"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"))
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"))
    description = db.Column(db.Text, default="")
    price_from = db.Column(db.Float, default=0.0)
    booking_window = db.Column(db.String(160), default="")
    travel_window = db.Column(db.String(160), default="")
    terms = db.Column(db.String(200), default="")
    hero_image = db.Column(db.String(240), default="")
    featured = db.Column(db.Boolean, default=False)


class HelpArticle(db.Model):
    __tablename__ = "help_articles"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80), default="")
    summary = db.Column(db.String(240), default="")
    body = db.Column(db.Text, default="")
    icon = db.Column(db.String(120), default="")
    popular = db.Column(db.Boolean, default=False)


class SearchLog(db.Model):
    __tablename__ = "search_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    query = db.Column(db.String(240), default="")
    category = db.Column(db.String(80), default="")
    result_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def currency(value):
    return f"${value:,.2f}"


def iso_date(value):
    if not value:
        return ""
    return value.strftime("%Y-%m-%d")


def display_date(value):
    if not value:
        return ""
    return value.strftime("%b %d, %Y")


def display_dt(value):
    if not value:
        return ""
    return value.strftime("%b %d, %Y %I:%M %p")


def display_time(value):
    if not value:
        return ""
    return value.strftime("%I:%M %p").lstrip("0")


def duration_label(minutes):
    hours = minutes // 60
    mins = minutes % 60
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def tokenize(text):
    parts = re.split(r"[^A-Za-z0-9]+", (text or "").lower())
    return [part for part in parts if part and part not in STOP_WORDS and len(part) > 1]


def scored_search(query, items, attr_names):
    tokens = tokenize(query)
    if not tokens:
        return list(items)
    scored = []
    for item in items:
        haystack = " ".join(str(getattr(item, attr, "") or "") for attr in attr_names).lower()
        score = sum(1 for token in tokens if token in haystack)
        if score > 0:
            scored.append((item, score))
    scored.sort(key=lambda pair: (-pair[1], str(getattr(pair[0], "name", getattr(pair[0], "title", "")))))
    return [item for item, _score in scored]


def parse_date_input(value):
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_int(value, default=1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def fare_class_by_slug(slug):
    return FareClass.query.filter_by(slug=slug).first()


def fare_option_for_trip(trip, fare_slug):
    for option in trip.fare_options:
        if option.fare_class.slug == fare_slug:
            return option
    return None


def sleeper_room_for_trip(trip, room_type):
    for room in trip.sleeper_rooms:
        if room.room_type == room_type:
            return room
    return None


def station_lookup(value):
    raw = (value or "").strip()
    if not raw:
        return None
    direct = Station.query.filter_by(code=raw.upper()).first()
    if direct:
        return direct
    match = re.search(r"\(([A-Z0-9]{3,4})\)", raw.upper())
    if match:
        station = Station.query.filter_by(code=match.group(1)).first()
        if station:
            return station
    like = f"%{raw}%"
    return (
        Station.query.filter(
            db.or_(
                Station.name.ilike(like),
                Station.city_name.ilike(like),
                Station.code.ilike(like),
            )
        )
        .order_by(Station.is_hub.desc(), Station.city_name, Station.name)
        .first()
    )


def trip_segments_ordered(trip):
    return sorted(trip.segments, key=lambda segment: segment.leg_order)


def slice_trip_segments(trip, origin_code, destination_code):
    segments = trip_segments_ordered(trip)
    if not segments:
        return []
    codes = [segments[0].from_station_code] + [segment.to_station_code for segment in segments]
    if origin_code not in codes or destination_code not in codes:
        return []
    origin_index = codes.index(origin_code)
    destination_index = codes.index(destination_code)
    if origin_index >= destination_index:
        return []
    return segments[origin_index:destination_index]


def option_alerts_for_trips(trips, origin_code, destination_code, via_code=None):
    travel_codes = {origin_code, destination_code}
    if via_code:
        travel_codes.add(via_code)
    for trip in trips:
        travel_codes.update([trip.start_station_code, trip.end_station_code])
        for segment in trip_segments_ordered(trip):
            travel_codes.add(segment.from_station_code)
            travel_codes.add(segment.to_station_code)

    alerts = []
    for alert in ServiceAlert.query.filter_by(active=True).order_by(ServiceAlert.severity.desc()).all():
        if alert.route_id and any(trip.route_id == alert.route_id for trip in trips):
            alerts.append(alert)
            continue
        if alert.station_code and alert.station_code in travel_codes:
            alerts.append(alert)
    unique = []
    seen = set()
    for alert in alerts:
        if alert.id not in seen:
            unique.append(
                {
                    "title": alert.title,
                    "severity": alert.severity,
                    "message": alert.message,
                    "next_step": alert.next_step,
                    "station_code": alert.station_code,
                }
            )
            seen.add(alert.id)
    return unique


def per_trip_base_price(trip, segments, fare_slug):
    fare_option = fare_option_for_trip(trip, fare_slug)
    if not fare_option:
        return None
    slice_minutes = sum(segment.duration_minutes for segment in segments)
    trip_minutes = max(trip.duration_minutes, 1)
    ratio = max(0.28, min(1.0, slice_minutes / trip_minutes))
    return round(trip.base_fare * ratio * fare_option.multiplier, 2)


def per_traveler_price_for_option(option, fare_slug):
    price = 0.0
    for trip, segments in zip(option["trips"], option["segment_groups"]):
        amount = per_trip_base_price(trip, segments, fare_slug)
        if amount is None:
            return None
        price += amount
    return round(price, 2)


def availability_for_option(option, fare_slug):
    counts = []
    for trip in option["trips"]:
        fare_option = fare_option_for_trip(trip, fare_slug)
        if fare_option:
            counts.append(fare_option.availability)
    return min(counts) if counts else 0


def room_availability_for_option(option):
    total = 0
    for trip in option["trips"]:
        total += sum(room.availability for room in trip.sleeper_rooms)
    return total


def build_option(trips, origin_code, destination_code, via_code=None):
    segment_groups = []
    if len(trips) == 1:
        segment_groups = [slice_trip_segments(trips[0], origin_code, destination_code)]
    elif len(trips) == 2 and via_code:
        segment_groups = [
            slice_trip_segments(trips[0], origin_code, via_code),
            slice_trip_segments(trips[1], via_code, destination_code),
        ]
    if any(not group for group in segment_groups):
        return None

    departure_dt = segment_groups[0][0].depart_dt
    arrival_dt = segment_groups[-1][-1].arrive_dt
    duration_minutes = int((arrival_dt - departure_dt).total_seconds() // 60)
    direct_price = per_traveler_price_for_option(
        {"trips": trips, "segment_groups": segment_groups},
        "saver",
    )
    business_price = per_traveler_price_for_option(
        {"trips": trips, "segment_groups": segment_groups},
        "business",
    )
    alerts = option_alerts_for_trips(trips, origin_code, destination_code, via_code=via_code)
    route_names = []
    train_numbers = []
    segment_details = []
    for trip, group in zip(trips, segment_groups):
        route_names.append(trip.route.name)
        train_numbers.append(f"{trip.train.name} {trip.train.number}")
        segment_details.append(
            {
                "route_name": trip.route.name,
                "train_number": trip.train.number,
                "origin_code": group[0].from_station_code,
                "destination_code": group[-1].to_station_code,
                "origin_name": group[0].from_station.city_name,
                "destination_name": group[-1].to_station.city_name,
                "departure_dt": group[0].depart_dt,
                "arrival_dt": group[-1].arrive_dt,
                "duration_label": duration_label(sum(segment.duration_minutes for segment in group)),
                "service_level": trip.route.service_level,
            }
        )
    has_sleepers = any(trip.has_sleepers and room_availability_for_option({"trips": [trip], "segment_groups": [group]}) > 0 for trip, group in zip(trips, segment_groups))

    option = {
        "trip_ids": [trip.id for trip in trips],
        "trips": trips,
        "origin_code": origin_code,
        "destination_code": destination_code,
        "via_code": via_code,
        "segment_groups": segment_groups,
        "departure_dt": departure_dt,
        "arrival_dt": arrival_dt,
        "departure_label": display_time(departure_dt),
        "arrival_label": display_time(arrival_dt),
        "duration_minutes": duration_minutes,
        "duration_label": duration_label(duration_minutes),
        "transfer_count": max(0, len(trips) - 1),
        "starting_price": direct_price or 0.0,
        "business_price": business_price or 0.0,
        "alerts": alerts,
        "route_names": route_names,
        "route_label": " / ".join(route_names),
        "train_label": " + ".join(train_numbers),
        "segment_details": segment_details,
        "has_sleepers": has_sleepers,
        "direct_only": len(trips) == 1,
        "trip_status": "Delayed" if any(trip.delay_minutes for trip in trips) else "On time",
        "saver_availability": availability_for_option({"trips": trips, "segment_groups": segment_groups}, "saver"),
        "business_availability": availability_for_option({"trips": trips, "segment_groups": segment_groups}, "business"),
    }
    return option


def serialize_option(option):
    return {
        "trip_ids": option["trip_ids"],
        "origin_code": option["origin_code"],
        "destination_code": option["destination_code"],
        "via_code": option.get("via_code"),
    }


def deserialize_option(serialized):
    trip_lookup = {trip.id: trip for trip in Trip.query.filter(Trip.id.in_(serialized["trip_ids"])).all()}
    trips = [trip_lookup[trip_id] for trip_id in serialized["trip_ids"] if trip_id in trip_lookup]
    if not trips:
        return None
    return build_option(
        trips,
        serialized["origin_code"],
        serialized["destination_code"],
        via_code=serialized.get("via_code"),
    )


def filter_time_window(options, time_window):
    if time_window not in {"morning", "afternoon", "evening"}:
        return options
    filtered = []
    for option in options:
        hour = option["departure_dt"].hour
        if time_window == "morning" and 5 <= hour < 12:
            filtered.append(option)
        elif time_window == "afternoon" and 12 <= hour < 17:
            filtered.append(option)
        elif time_window == "evening" and (17 <= hour or hour < 5):
            filtered.append(option)
    return filtered


def sort_options(options, sort_key, fare_slug):
    def price_value(option):
        return per_traveler_price_for_option(option, fare_slug) or option["starting_price"]

    if sort_key == "price_desc":
        options.sort(key=price_value, reverse=True)
    elif sort_key == "duration":
        options.sort(key=lambda option: (option["duration_minutes"], option["departure_dt"]))
    elif sort_key == "departure":
        options.sort(key=lambda option: option["departure_dt"])
    else:
        options.sort(key=lambda option: (price_value(option), option["duration_minutes"], option["departure_dt"]))
    return options


def build_search_results(origin_code, destination_code, service_date, fare_slug="saver", direct_only=False, time_window="", sort_key="price"):
    all_trips = Trip.query.filter_by(service_date=service_date).all()
    direct_options = []
    for trip in all_trips:
        segments = slice_trip_segments(trip, origin_code, destination_code)
        if segments:
            option = build_option([trip], origin_code, destination_code)
            if option:
                direct_options.append(option)

    transfer_options = []
    if not direct_only:
        hubs = [station.code for station in Station.query.filter_by(is_hub=True).all() if station.code not in {origin_code, destination_code}]
        partials_from_origin = defaultdict(list)
        partials_to_destination = defaultdict(list)
        for trip in all_trips:
            for hub in hubs:
                part_out = slice_trip_segments(trip, origin_code, hub)
                if part_out:
                    partials_from_origin[hub].append((trip, part_out))
                part_in = slice_trip_segments(trip, hub, destination_code)
                if part_in:
                    partials_to_destination[hub].append((trip, part_in))

        seen = set()
        for hub in hubs:
            for first_trip, first_segments in partials_from_origin.get(hub, [])[:4]:
                first_arrival = first_segments[-1].arrive_dt
                for second_trip, second_segments in partials_to_destination.get(hub, [])[:4]:
                    if first_trip.id == second_trip.id:
                        continue
                    if second_segments[0].depart_dt < first_arrival + timedelta(minutes=45):
                        continue
                    if second_segments[0].depart_dt > first_arrival + timedelta(hours=6):
                        continue
                    signature = (first_trip.id, second_trip.id, hub)
                    if signature in seen:
                        continue
                    option = build_option([first_trip, second_trip], origin_code, destination_code, via_code=hub)
                    if option:
                        transfer_options.append(option)
                        seen.add(signature)

    results = direct_options + transfer_options
    results = filter_time_window(results, time_window)
    if fare_slug:
        results = [option for option in results if availability_for_option(option, fare_slug) > 0]
    for option in results:
        option["display_price"] = per_traveler_price_for_option(option, fare_slug or "saver") or option["starting_price"]
    sort_options(results, sort_key, fare_slug or "saver")
    return results[:18]


def booking_defaults():
    return {
        "trip_type": "one-way",
        "origin": "NYP",
        "destination": "WAS",
        "departure_date": iso_date(MIRROR_REFERENCE_DATE.date()),
        "return_date": iso_date(MIRROR_REFERENCE_DATE.date() + timedelta(days=2)),
        "passengers": 1,
        "fare_class": "saver",
        "time_window": "",
        "sort": "price",
        "direct_only": False,
    }


def get_flow():
    return session.get(FLOW_KEY, {})


def save_flow(flow):
    session[FLOW_KEY] = flow
    session.modified = True


def clear_flow():
    session.pop(FLOW_KEY, None)
    session.modified = True


def current_selected_options():
    flow = get_flow()
    options = []
    for serialized in flow.get("selected_options", []):
        option = deserialize_option(serialized)
        if option:
            options.append(option)
    return options


def flow_passenger_count():
    return parse_int(get_flow().get("passengers", 1), 1)


def flow_has_sleepers():
    for option in current_selected_options():
        for trip in option["trips"]:
            if trip.has_sleepers and trip.sleeper_rooms:
                return True
    return False


def build_fare_quotes(options):
    quotes = []
    for fare_class in FareClass.query.order_by(FareClass.sort_order).all():
        per_traveler = 0.0
        counts = []
        for option in options:
            price = per_traveler_price_for_option(option, fare_class.slug)
            if price is None:
                per_traveler = None
                break
            per_traveler += price
            counts.append(availability_for_option(option, fare_class.slug))
        if per_traveler is None:
            continue
        quotes.append(
            {
                "slug": fare_class.slug,
                "name": fare_class.name,
                "description": fare_class.description,
                "seat_type": fare_class.seat_type,
                "rules_change": fare_class.rules_change,
                "rules_refund": fare_class.rules_refund,
                "per_traveler": round(per_traveler, 2),
                "availability": min(counts) if counts else 0,
                "points_earned": round(per_traveler * fare_class.points_multiplier * flow_passenger_count()),
                "recommended": fare_class.slug == "value",
                "color": fare_class.color,
            }
        )
    return quotes


def build_room_choices(options):
    room_sets = []
    for option in options:
        for trip in option["trips"]:
            if not trip.has_sleepers or not trip.sleeper_rooms:
                continue
            room_sets.append(
                {
                    "trip_id": trip.id,
                    "train_label": f"{trip.train.name} {trip.train.number}",
                    "route_name": trip.route.name,
                    "rooms": sorted(trip.sleeper_rooms, key=lambda room: room.price_delta),
                }
            )
    return room_sets


def booking_summary(flow=None):
    flow = flow or get_flow()
    options = current_selected_options()
    if not options:
        return None
    fare_slug = flow.get("fare_slug", "value")
    passenger_count = parse_int(flow.get("passengers", 1), 1)
    room_choices = flow.get("room_choices", {})
    passengers = flow.get("passenger_entries", [])

    per_traveler_total = 0.0
    room_total = 0.0
    points_total = 0
    for option in options:
        for trip, segments in zip(option["trips"], option["segment_groups"]):
            room_type = room_choices.get(str(trip.id), "coach")
            effective_fare_slug = "flexible" if room_type != "coach" else fare_slug
            part_price = per_trip_base_price(trip, segments, effective_fare_slug) or 0.0
            per_traveler_total += part_price
            fare_class = fare_class_by_slug(effective_fare_slug)
            if fare_class:
                points_total += round(part_price * passenger_count * fare_class.points_multiplier)
            if room_type != "coach":
                room = sleeper_room_for_trip(trip, room_type)
                if room:
                    room_total += room.price_delta
    traveler_subtotal = round(per_traveler_total * passenger_count, 2)
    service_fee = round(12.0 + max(0, len(options) - 1) * 6.5, 2)
    total = round(traveler_subtotal + room_total + service_fee, 2)
    return {
        "options": options,
        "passenger_count": passenger_count,
        "passengers": passengers,
        "fare_slug": fare_slug,
        "room_choices": room_choices,
        "per_traveler_total": round(per_traveler_total, 2),
        "traveler_subtotal": traveler_subtotal,
        "room_total": round(room_total, 2),
        "service_fee": service_fee,
        "total": total,
        "reward_points": points_total,
        "trip_type": flow.get("trip_type", "one-way"),
    }


def next_booking_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    seed_value = Booking.query.count() + 91
    out = []
    for _ in range(6):
        out.append(alphabet[seed_value % len(alphabet)])
        seed_value = (seed_value * 17 + 11) // len(alphabet)
    return "".join(out)[-6:]


def next_approval_code():
    alphabet = string.ascii_uppercase + string.digits
    seed_value = PaymentMock.query.count() + 700
    chars = []
    for _ in range(8):
        chars.append(alphabet[seed_value % len(alphabet)])
        seed_value = (seed_value * 13 + 9) // len(alphabet)
    return "".join(chars)[-8:]


def allocate_seat_or_room(trip, passenger_index, fare_slug, room_type):
    if room_type and room_type != "coach":
        room = sleeper_room_for_trip(trip, room_type)
        if not room:
            return "Room pending"
        return f"{room.name} {1 + passenger_index}"
    row = 4 + (trip.id + passenger_index) % 18
    col = "ABCD"[(trip.id + passenger_index) % 4]
    if fare_slug == "business":
        return f"Business {row}{col}"
    return f"Coach {row}{col}"


def log_search(query, category, result_count):
    if not query:
        return
    entry = SearchLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        query=query[:240],
        category=category[:80],
        result_count=result_count,
    )
    db.session.add(entry)
    db.session.commit()


def dashboard_upcoming_trip(user_id):
    return (
        Booking.query.filter_by(user_id=user_id)
        .order_by(Booking.departure_date.asc(), Booking.created_at.desc())
        .first()
    )


def departures_for_station(station_code, target_date=None, limit=10):
    target_date = target_date or MIRROR_REFERENCE_DATE.date()
    rows = []
    segments = (
        TripSegment.query.join(Trip)
        .filter(Trip.service_date == target_date, TripSegment.from_station_code == station_code)
        .order_by(TripSegment.depart_dt.asc())
        .all()
    )
    for segment in segments[:limit]:
        rows.append(
            {
                "departure_dt": segment.depart_dt,
                "arrival_dt": segment.arrive_dt,
                "route_name": segment.trip.route.name,
                "train_number": segment.trip.train.number,
                "destination_code": segment.to_station_code,
                "destination_name": segment.to_station.city_name,
                "status_label": segment.trip.status_label,
                "delay_minutes": segment.trip.delay_minutes,
            }
        )
    return rows


def routes_for_station(station_code):
    seen = {}
    for stop in RouteStop.query.filter_by(station_code=station_code).all():
        seen[stop.route.slug] = stop.route
    return sorted(seen.values(), key=lambda route: route.name)


def help_search(query):
    return scored_search(query, HelpArticle.query.all(), ["title", "summary", "body", "category"])


@app.template_filter("currency")
def currency_filter(value):
    return currency(float(value))


@app.template_filter("date_label")
def date_filter(value):
    return display_date(value)


@app.template_filter("dt_label")
def dt_filter(value):
    return display_dt(value)


@app.template_filter("time_label")
def time_filter(value):
    return display_time(value)


@app.template_filter("duration_label")
def duration_filter(value):
    return duration_label(int(value or 0))


@app.context_processor
def inject_globals():
    top_routes = Route.query.filter_by(featured=True).order_by(Route.name).limit(6).all()
    severe_alerts = ServiceAlert.query.filter(ServiceAlert.active.is_(True), ServiceAlert.severity.in_(["Service Alert", "Major Advisory"])).all()
    stations = Station.query.order_by(Station.city_name, Station.name).all()
    return {
        "mirror_reference_date": MIRROR_REFERENCE_DATE,
        "service_start_date": SERVICE_START_DATE,
        "service_end_date": SERVICE_END_DATE,
        "top_routes": top_routes,
        "station_directory": stations,
        "top_alerts": severe_alerts[:3],
        "benchmark_password": BENCHMARK_PASSWORD,
        "demo_banner": "Demo mirror only: all bookings, passenger details, payments, and trip records use deterministic local benchmark data.",
    }


@app.route("/")
@app.route("/home")
def index():
    featured_routes = Route.query.filter_by(featured=True).order_by(Route.name).limit(6).all()
    featured_deals = Deal.query.order_by(Deal.featured.desc(), Deal.price_from.asc()).limit(4).all()
    service_alerts = ServiceAlert.query.filter_by(active=True).order_by(ServiceAlert.severity.desc()).limit(4).all()
    destinations = City.query.filter_by(featured=True).order_by(City.name).limit(6).all()
    popular_departures = []
    for code in ["NYP", "WAS", "CHI", "SEA", "LAX"]:
        station = Station.query.filter_by(code=code).first()
        if station:
            popular_departures.append({"station": station, "departures": departures_for_station(code, MIRROR_REFERENCE_DATE.date(), 3)})
    return render_template(
        "index.html",
        featured_routes=featured_routes,
        featured_deals=featured_deals,
        service_alerts=service_alerts,
        destinations=destinations,
        popular_departures=popular_departures,
        booking_defaults=booking_defaults(),
    )


@app.route("/routes")
def routes_page():
    query = request.args.get("q", "").strip()
    routes = Route.query.order_by(Route.name).all()
    if query:
        routes = scored_search(query, routes, ["name", "tagline", "description", "route_type", "service_level"])
    return render_template("routes.html", routes=routes, query=query)


@app.route("/routes/<route_slug>")
def route_detail(route_slug):
    route = Route.query.filter_by(slug=route_slug).first_or_404()
    next_trips = (
        Trip.query.filter(Trip.route_id == route.id, Trip.service_date >= MIRROR_REFERENCE_DATE.date())
        .order_by(Trip.departure_dt.asc())
        .limit(6)
        .all()
    )
    related_alerts = ServiceAlert.query.filter_by(route_id=route.id, active=True).all()
    related_deals = Deal.query.filter_by(route_id=route.id).order_by(Deal.price_from.asc()).all()
    return render_template(
        "route_detail.html",
        route=route,
        next_trips=next_trips,
        related_alerts=related_alerts,
        related_deals=related_deals,
    )


@app.route("/stations")
def stations_page():
    query = request.args.get("q", "").strip()
    region = request.args.get("region", "").strip()
    stations = Station.query.order_by(Station.city_name, Station.name).all()
    if region:
        stations = [station for station in stations if station.region == region]
    if query:
        stations = scored_search(query, stations, ["code", "name", "city_name", "state", "region", "map_blurb"])
    regions = sorted({station.region for station in Station.query.all() if station.region})
    return render_template("stations.html", stations=stations, query=query, region=region, regions=regions)


@app.route("/stations/<station_code>")
def station_detail(station_code):
    station = Station.query.filter_by(code=station_code.upper()).first_or_404()
    departures = departures_for_station(station.code, MIRROR_REFERENCE_DATE.date(), 8)
    station_routes = routes_for_station(station.code)
    station_alerts = ServiceAlert.query.filter_by(station_code=station.code, active=True).all()
    return render_template(
        "station_detail.html",
        station=station,
        departures=departures,
        station_routes=station_routes,
        station_alerts=station_alerts,
    )


@app.route("/destinations")
def destinations_page():
    destinations = City.query.order_by(City.featured.desc(), City.name).all()
    return render_template("destinations.html", destinations=destinations)


@app.route("/destinations/<city_slug>")
def destination_detail(city_slug):
    city = City.query.filter_by(slug=city_slug).first_or_404()
    city_routes = []
    seen = set()
    for station in city.stations:
        for route in routes_for_station(station.code):
            if route.slug not in seen:
                city_routes.append(route)
                seen.add(route.slug)
    city_deals = Deal.query.filter_by(city_id=city.id).order_by(Deal.price_from.asc()).all()
    return render_template("destination_detail.html", city=city, city_routes=city_routes, city_deals=city_deals)


@app.route("/deals")
def deals_page():
    deals = Deal.query.order_by(Deal.featured.desc(), Deal.price_from.asc()).all()
    return render_template("deals.html", deals=deals)


@app.route("/schedules")
def schedules_page():
    station_code = request.args.get("station_code", "NYP").upper()
    schedule_date = parse_date_input(request.args.get("date")) or MIRROR_REFERENCE_DATE.date()
    station = Station.query.filter_by(code=station_code).first()
    departures = departures_for_station(station_code, schedule_date, 16) if station else []
    return render_template(
        "schedules.html",
        station=station,
        departures=departures,
        schedule_date=schedule_date,
    )


@app.route("/status")
def status_page():
    station_code = request.args.get("station_code", "").upper()
    route_slug = request.args.get("route", "").strip()
    trips = Trip.query.filter_by(service_date=MIRROR_REFERENCE_DATE.date()).order_by(Trip.departure_dt.asc()).all()
    if station_code:
        trips = [
            trip
            for trip in trips
            if station_code in {trip.start_station_code, trip.end_station_code}
            or any(station_code in {segment.from_station_code, segment.to_station_code} for segment in trip_segments_ordered(trip))
        ]
    if route_slug:
        trips = [trip for trip in trips if trip.route.slug == route_slug]
    return render_template(
        "status.html",
        trips=trips[:24],
        station_code=station_code,
        route_slug=route_slug,
        routes=Route.query.order_by(Route.name).all(),
    )


@app.route("/service-alerts")
def service_alerts_page():
    severity = request.args.get("severity", "")
    alerts = ServiceAlert.query.filter_by(active=True).order_by(ServiceAlert.severity.desc(), ServiceAlert.start_date.desc()).all()
    if severity:
        alerts = [alert for alert in alerts if alert.severity == severity]
    severities = sorted({alert.severity for alert in ServiceAlert.query.all()})
    return render_template("service_alerts.html", alerts=alerts, severity=severity, severities=severities)


@app.route("/help")
def help_page():
    query = request.args.get("q", "").strip()
    articles = HelpArticle.query.order_by(HelpArticle.popular.desc(), HelpArticle.title).all()
    if query:
        articles = help_search(query)
        log_search(query, "help", len(articles))
    return render_template("help.html", articles=articles, query=query)


@app.route("/help/<slug>")
def help_detail(slug):
    article = HelpArticle.query.filter_by(slug=slug).first_or_404()
    related = HelpArticle.query.filter(HelpArticle.id != article.id, HelpArticle.category == article.category).limit(3).all()
    return render_template("help_detail.html", article=article, related=related)


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    route_results = scored_search(query, Route.query.all(), ["name", "tagline", "description"]) if query else []
    station_results = scored_search(query, Station.query.all(), ["code", "name", "city_name", "state", "map_blurb"]) if query else []
    destination_results = scored_search(query, City.query.all(), ["name", "state", "region", "blurb", "highlight_fact"]) if query else []
    deal_results = scored_search(query, Deal.query.all(), ["title", "description", "terms"]) if query else []
    alert_results = scored_search(query, ServiceAlert.query.all(), ["title", "message", "next_step", "severity"]) if query else []
    help_results = help_search(query) if query else []
    total = sum(len(bucket) for bucket in [route_results, station_results, destination_results, deal_results, alert_results, help_results])
    if query:
        log_search(query, "global", total)
    return render_template(
        "search.html",
        query=query,
        route_results=route_results,
        station_results=station_results,
        destination_results=destination_results,
        deal_results=deal_results,
        alert_results=alert_results,
        help_results=help_results,
        total=total,
    )


@app.route("/booking/search")
def booking_search():
    return render_template("booking_search.html", booking_defaults=booking_defaults())


@app.route("/booking/results")
def booking_results():
    params = booking_defaults()
    params.update(
        {
            "trip_type": request.args.get("trip_type", params["trip_type"]),
            "origin": request.args.get("origin", params["origin"]).upper(),
            "destination": request.args.get("destination", params["destination"]).upper(),
            "departure_date": request.args.get("departure_date", params["departure_date"]),
            "return_date": request.args.get("return_date", params["return_date"]),
            "passengers": parse_int(request.args.get("passengers"), 1),
            "fare_class": request.args.get("fare_class", params["fare_class"]),
            "time_window": request.args.get("time_window", ""),
            "sort": request.args.get("sort", "price"),
            "direct_only": request.args.get("direct_only", "") in {"1", "true", "on"},
        }
    )
    if params["trip_type"] == "multi-city":
        return redirect(url_for("booking_multi_city"))

    leg = request.args.get("leg", "outbound")
    departure_date = parse_date_input(params["departure_date"])
    return_date = parse_date_input(params["return_date"])
    if not departure_date:
        departure_date = MIRROR_REFERENCE_DATE.date()
        params["departure_date"] = iso_date(departure_date)
    if not return_date:
        return_date = departure_date + timedelta(days=2)
        params["return_date"] = iso_date(return_date)

    if leg == "return" and params["trip_type"] == "round-trip":
        origin_code = params["destination"]
        destination_code = params["origin"]
        service_date = return_date
        leg_title = "Choose your return train"
    else:
        origin_code = params["origin"]
        destination_code = params["destination"]
        service_date = departure_date
        leg_title = "Choose your outbound train"

    origin_station = station_lookup(origin_code)
    destination_station = station_lookup(destination_code)
    results = []
    if origin_station and destination_station:
        results = build_search_results(
            origin_station.code,
            destination_station.code,
            service_date,
            fare_slug=params["fare_class"],
            direct_only=params["direct_only"],
            time_window=params["time_window"],
            sort_key=params["sort"],
        )
        log_search(f"{origin_station.code} {destination_station.code}", "booking", len(results))

    option_map = {}
    for index, option in enumerate(results):
        option_map[f"{leg}_{index}"] = serialize_option(option)

    search_state = session.get(SEARCH_KEY, {})
    search_state.update(
        {
            "params": params,
            "leg": leg,
            "options": option_map,
            "selected_outbound": search_state.get("selected_outbound"),
        }
    )
    session[SEARCH_KEY] = search_state
    session.modified = True

    return render_template(
        "booking_results.html",
        params=params,
        leg=leg,
        leg_title=leg_title,
        results=results,
        origin_station=origin_station,
        destination_station=destination_station,
        service_date=service_date,
        selected_outbound=deserialize_option(search_state.get("selected_outbound")) if search_state.get("selected_outbound") else None,
    )


@app.route("/booking/select-trip", methods=["GET", "POST"])
def booking_select_trip():
    if request.method == "POST":
        search_state = session.get(SEARCH_KEY, {})
        token = request.form.get("option_token", "")
        selected = search_state.get("options", {}).get(token)
        if not selected:
            flash("Choose a train option before continuing.", "warning")
            return redirect(request.referrer or url_for("booking_search"))

        params = search_state.get("params", booking_defaults())
        leg = search_state.get("leg", "outbound")
        if params.get("trip_type") == "round-trip" and leg == "outbound":
            search_state["selected_outbound"] = selected
            session[SEARCH_KEY] = search_state
            session.modified = True
            return redirect(
                url_for(
                    "booking_results",
                    trip_type="round-trip",
                    origin=params["origin"],
                    destination=params["destination"],
                    departure_date=params["departure_date"],
                    return_date=params["return_date"],
                    passengers=params["passengers"],
                    fare_class=params["fare_class"],
                    time_window=params["time_window"],
                    sort=params["sort"],
                    direct_only="1" if params.get("direct_only") else "0",
                    leg="return",
                )
            )

        selected_options = [selected]
        if params.get("trip_type") == "round-trip":
            outbound = search_state.get("selected_outbound")
            if outbound:
                selected_options = [outbound, selected]

        flow = {
            "trip_type": params.get("trip_type", "one-way"),
            "selected_options": selected_options,
            "search_params": params,
            "passengers": params.get("passengers", 1),
            "fare_slug": "value",
            "room_choices": {},
            "passenger_entries": [],
        }
        save_flow(flow)
        flash("Trip option saved. Review the itinerary and continue to fares.", "success")
        return redirect(url_for("booking_select_trip"))

    flow = get_flow()
    options = current_selected_options()
    if not options:
        return redirect(url_for("booking_search"))
    return render_template("booking_select_trip.html", flow=flow, options=options)


@app.route("/booking/select-fare", methods=["GET", "POST"])
def booking_select_fare():
    options = current_selected_options()
    if not options:
        return redirect(url_for("booking_search"))
    flow = get_flow()
    if request.method == "POST":
        flow["fare_slug"] = request.form.get("fare_slug", "value")
        save_flow(flow)
        if flow_has_sleepers():
            return redirect(url_for("booking_rooms"))
        return redirect(url_for("booking_passengers"))

    quotes = build_fare_quotes(options)
    return render_template("booking_select_fare.html", flow=flow, options=options, quotes=quotes)


@app.route("/booking/rooms", methods=["GET", "POST"])
def booking_rooms():
    options = current_selected_options()
    if not options:
        return redirect(url_for("booking_search"))
    flow = get_flow()
    room_sets = build_room_choices(options)
    if request.method == "POST":
        room_choices = {}
        for room_set in room_sets:
            room_choices[str(room_set["trip_id"])] = request.form.get(f"room_{room_set['trip_id']}", "coach")
        flow["room_choices"] = room_choices
        save_flow(flow)
        return redirect(url_for("booking_passengers"))
    return render_template("booking_rooms.html", flow=flow, room_sets=room_sets)


@app.route("/booking/passengers", methods=["GET", "POST"])
@login_required
def booking_passengers():
    options = current_selected_options()
    if not options:
        return redirect(url_for("booking_search"))
    flow = get_flow()
    saved_profiles = Passenger.query.filter_by(user_id=current_user.id, is_saved_profile=True).order_by(Passenger.id).all()
    if request.method == "POST":
        entries = []
        count = parse_int(flow.get("passengers", 1), 1)
        for index in range(count):
            entries.append(
                {
                    "first_name": request.form.get(f"first_name_{index}", "").strip(),
                    "last_name": request.form.get(f"last_name_{index}", "").strip(),
                    "passenger_type": request.form.get(f"passenger_type_{index}", "Adult"),
                    "age_band": request.form.get(f"age_band_{index}", "18+"),
                    "accessibility_need": request.form.get(f"accessibility_need_{index}", "").strip(),
                    "seat_preference": request.form.get(f"seat_preference_{index}", "Window"),
                }
            )
        if not all(entry["first_name"] and entry["last_name"] for entry in entries):
            flash("Please complete every synthetic passenger name field.", "danger")
        else:
            flow["passenger_entries"] = entries
            save_flow(flow)
            return redirect(url_for("booking_review"))
    return render_template(
        "booking_passengers.html",
        flow=flow,
        saved_profiles=saved_profiles,
        passenger_count=parse_int(flow.get("passengers", 1), 1),
    )


@app.route("/booking/review")
@login_required
def booking_review():
    summary = booking_summary()
    if not summary:
        return redirect(url_for("booking_search"))
    return render_template("booking_review.html", summary=summary, flow=get_flow())


@app.route("/booking/checkout", methods=["GET", "POST"])
@login_required
def booking_checkout():
    flow = get_flow()
    summary = booking_summary(flow)
    if not summary:
        return redirect(url_for("booking_search"))

    if request.method == "POST":
        booking_code = next_booking_code()
        booking = Booking(
            user_id=current_user.id,
            booking_code=booking_code,
            trip_type=summary["trip_type"],
            status="Confirmed",
            total_amount=summary["total"],
            reward_points_earned=summary["reward_points"],
            contact_email=current_user.email,
            contact_phone=request.form.get("contact_phone", "").strip() or current_user.phone,
            origin_code=summary["options"][0]["origin_code"],
            destination_code=summary["options"][-1]["destination_code"],
            departure_date=summary["options"][0]["departure_dt"].date(),
            return_date=summary["options"][-1]["departure_dt"].date() if summary["trip_type"] == "round-trip" else None,
            notes=request.form.get("notes", "").strip(),
            created_at=MIRROR_REFERENCE_DATE + timedelta(minutes=Booking.query.count() * 9),
        )
        db.session.add(booking)
        db.session.flush()

        flow_passengers = summary["passengers"] or [
            {
                "first_name": current_user.first_name or current_user.full_name.split()[0],
                "last_name": current_user.last_name or "Traveler",
                "passenger_type": "Adult",
                "age_band": "18+",
                "accessibility_need": "",
                "seat_preference": "Window",
            }
        ]

        passenger_rows = []
        for entry in flow_passengers:
            passenger = Passenger(
                user_id=current_user.id,
                booking_id=booking.id,
                first_name=entry["first_name"],
                last_name=entry["last_name"],
                passenger_type=entry["passenger_type"],
                age_band=entry["age_band"],
                accessibility_need=entry.get("accessibility_need", ""),
                seat_preference=entry.get("seat_preference", ""),
                rewards_number=current_user.rewards_member_no,
                email=current_user.email,
                phone=current_user.phone,
                is_saved_profile=False,
            )
            db.session.add(passenger)
            passenger_rows.append(passenger)
        db.session.flush()

        order_index = 0
        room_choices = flow.get("room_choices", {})
        for option in summary["options"]:
            for trip, segments in zip(option["trips"], option["segment_groups"]):
                room_type = room_choices.get(str(trip.id), "coach")
                effective_fare_slug = "flexible" if room_type != "coach" else flow.get("fare_slug", "value")
                fare_class = fare_class_by_slug(effective_fare_slug)
                accommodation = (
                    sleeper_room_for_trip(trip, room_type).name
                    if room_type != "coach" and sleeper_room_for_trip(trip, room_type)
                    else ("Business Seat" if effective_fare_slug == "business" else "Coach Seat")
                )
                booking_segment = BookingSegment(
                    booking_id=booking.id,
                    trip_id=trip.id,
                    leg_order=order_index,
                    route_name=trip.route.name,
                    train_number=trip.train.number,
                    origin_code=segments[0].from_station_code,
                    destination_code=segments[-1].to_station_code,
                    depart_dt=segments[0].depart_dt,
                    arrive_dt=segments[-1].arrive_dt,
                    fare_class_name=fare_class.name if fare_class else effective_fare_slug.title(),
                    accommodation_type=accommodation,
                )
                db.session.add(booking_segment)
                part_price = per_trip_base_price(trip, segments, effective_fare_slug) or 0.0
                for passenger_index, passenger in enumerate(passenger_rows):
                    ticket = Ticket(
                        booking_id=booking.id,
                        passenger_id=passenger.id,
                        trip_id=trip.id,
                        fare_class_id=fare_class.id if fare_class else FareClass.query.first().id,
                        accommodation_type=accommodation,
                        seat_or_room=allocate_seat_or_room(trip, passenger_index, effective_fare_slug, room_type),
                        qr_token=f"{booking_code}-{order_index + 1}-{passenger_index + 1}",
                        status="Issued",
                    )
                    db.session.add(ticket)
                order_index += 1

        payment = PaymentMock(
            booking_id=booking.id,
            payment_label=request.form.get("payment_label", "Demo Visa ending in 4242"),
            amount=summary["total"],
            status="Approved",
            approval_code=next_approval_code(),
            charged_at=MIRROR_REFERENCE_DATE + timedelta(minutes=PaymentMock.query.count() * 4),
        )
        db.session.add(payment)

        reward_account = current_user.reward_account
        if reward_account:
            reward_account.points_balance += summary["reward_points"]
            reward_account.points_ytd += summary["reward_points"]
            reward_account.status_credits += max(1, summary["total"] // 150)
            activity = RewardActivity(
                reward_account_id=reward_account.id,
                posted_at=MIRROR_REFERENCE_DATE + timedelta(minutes=RewardActivity.query.count() * 7),
                description=f"Booking {booking_code} - {summary['options'][0]['route_label']}",
                points_delta=summary["reward_points"],
                balance_after=reward_account.points_balance,
                booking_code=booking_code,
                category="Travel",
            )
            db.session.add(activity)

        db.session.commit()
        session["last_booking_code"] = booking_code
        clear_flow()
        flash("Demo trip confirmed. No real ticketing or payment was processed.", "success")
        return redirect(url_for("booking_confirmation", code=booking_code))

    return render_template("booking_checkout.html", summary=summary, flow=flow)


@app.route("/booking/confirmation")
@login_required
def booking_confirmation():
    booking_code = request.args.get("code") or session.get("last_booking_code")
    if not booking_code:
        return redirect(url_for("account_trips"))
    booking = Booking.query.filter_by(booking_code=booking_code, user_id=current_user.id).first_or_404()
    return render_template("booking_confirmation.html", booking=booking)


@app.route("/booking/multi-city", methods=["GET", "POST"])
def booking_multi_city():
    state = session.get(MULTI_KEY, {})
    if request.method == "POST":
        phase = request.form.get("phase", "search")
        if phase == "search":
            legs = []
            for index in range(3):
                origin = request.form.get(f"origin_{index}", "").upper().strip()
                destination = request.form.get(f"destination_{index}", "").upper().strip()
                depart_date = parse_date_input(request.form.get(f"date_{index}"))
                if origin and destination and depart_date:
                    legs.append({"origin": origin, "destination": destination, "date": iso_date(depart_date)})
            passengers = parse_int(request.form.get("passengers"), 1)
            options_by_leg = []
            for leg in legs:
                options = build_search_results(leg["origin"], leg["destination"], parse_date_input(leg["date"]), fare_slug="value", direct_only=False, sort_key="price")
                serialized = {f"leg{len(options_by_leg)}_{idx}": serialize_option(option) for idx, option in enumerate(options[:4])}
                options_by_leg.append({"leg": leg, "options": options[:4], "serialized": serialized})
            state = {"legs": legs, "passengers": passengers, "options": [entry["serialized"] for entry in options_by_leg]}
            session[MULTI_KEY] = state
            session.modified = True
            return render_template("booking_multi_city.html", state=state, options_by_leg=options_by_leg)

        selected_options = []
        option_groups = state.get("options", [])
        for index, serialized_group in enumerate(option_groups):
            token = request.form.get(f"choice_{index}")
            if token and token in serialized_group:
                selected_options.append(serialized_group[token])
        if len(selected_options) != len(option_groups):
            flash("Choose one itinerary for each leg of the multi-city trip.", "warning")
        else:
            save_flow(
                {
                    "trip_type": "multi-city",
                    "selected_options": selected_options,
                    "search_params": {"trip_type": "multi-city"},
                    "passengers": state.get("passengers", 1),
                    "fare_slug": "value",
                    "room_choices": {},
                    "passenger_entries": [],
                }
            )
            flash("Multi-city itinerary saved. Continue to fare selection.", "success")
            return redirect(url_for("booking_select_trip"))

    return render_template("booking_multi_city.html", state=state, options_by_leg=[])


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
            flash("Signed in to the Amtrak demo mirror.", "success")
            return redirect(request.args.get("next") or url_for("account"))
        flash("That demo email and password did not match.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not email or not password:
            flash("Please complete the required fields.", "danger")
        elif password != confirm_password:
            flash("Passwords must match.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("That demo account already exists.", "warning")
        else:
            display_name = request.form.get("display_name", "").strip() or email.split("@")[0]
            first_name = request.form.get("first_name", "").strip() or display_name.split()[0]
            last_name = request.form.get("last_name", "").strip() or "Traveler"
            user = User(
                email=email,
                display_name=display_name,
                first_name=first_name,
                last_name=last_name,
                phone=request.form.get("phone", "").strip(),
                city=request.form.get("city", "").strip(),
                state=request.form.get("state", "").strip(),
                preferred_station_code=request.form.get("preferred_station_code", "").strip().upper() or None,
                rewards_member_no=f"AGR-{44000 + User.query.count() + 1}",
                created_at=MIRROR_REFERENCE_DATE + timedelta(minutes=User.query.count() * 5),
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            reward_account = RewardAccount(
                user_id=user.id,
                member_number=user.rewards_member_no,
                tier="Member",
                points_balance=800,
                points_ytd=800,
                status_credits=1,
                preferred_station_code=user.preferred_station_code,
            )
            db.session.add(reward_account)
            saved_profile = Passenger(
                user_id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                passenger_type="Adult",
                age_band="18+",
                accessibility_need="",
                seat_preference="Window",
                rewards_number=user.rewards_member_no,
                email=user.email,
                phone=user.phone,
                is_saved_profile=True,
            )
            db.session.add(saved_profile)
            db.session.commit()
            login_user(user)
            flash("Your local Amtrak demo account is ready.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("Signed out of the Amtrak demo mirror.", "success")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    upcoming = (
        Booking.query.filter_by(user_id=current_user.id)
        .order_by(Booking.departure_date.asc(), Booking.created_at.desc())
        .limit(6)
        .all()
    )
    saved_profile = Passenger.query.filter_by(user_id=current_user.id, is_saved_profile=True).first()
    return render_template("account.html", upcoming=upcoming, saved_profile=saved_profile)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    stations = Station.query.order_by(Station.city_name, Station.name).all()
    if request.method == "POST":
        current_user.display_name = request.form.get("display_name", "").strip() or current_user.display_name
        current_user.first_name = request.form.get("first_name", "").strip() or current_user.first_name
        current_user.last_name = request.form.get("last_name", "").strip() or current_user.last_name
        current_user.phone = request.form.get("phone", "").strip()
        current_user.city = request.form.get("city", "").strip()
        current_user.state = request.form.get("state", "").strip()
        current_user.preferred_station_code = request.form.get("preferred_station_code", "").strip().upper() or None
        if current_user.reward_account:
            current_user.reward_account.preferred_station_code = current_user.preferred_station_code
        db.session.commit()
        flash("Your Amtrak demo account preferences were updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html", stations=stations)


@app.route("/account/trips")
@login_required
def account_trips():
    bookings = (
        Booking.query.filter_by(user_id=current_user.id)
        .order_by(Booking.departure_date.asc(), Booking.created_at.desc())
        .all()
    )
    upcoming = [booking for booking in bookings if booking.is_upcoming]
    past = [booking for booking in bookings if not booking.is_upcoming]
    return render_template("account_trips.html", bookings=bookings, upcoming=upcoming, past=past)


@app.route("/account/rewards")
@login_required
def account_rewards():
    reward_account = current_user.reward_account
    return render_template("account_rewards.html", reward_account=reward_account)


@app.route("/trip-lookup", methods=["GET", "POST"])
def trip_lookup():
    booking = None
    if request.method == "POST":
        booking_code = request.form.get("booking_code", "").strip().upper()
        email = request.form.get("email", "").strip().lower()
        last_name = request.form.get("last_name", "").strip().lower()
        booking = Booking.query.filter_by(booking_code=booking_code).first()
        if booking:
            passenger_last_names = {passenger.last_name.lower() for passenger in booking.passengers}
            if (email and booking.contact_email.lower() == email) or (last_name and last_name in passenger_last_names):
                lookup_codes = session.get(LOOKUP_KEY, [])
                if booking_code not in lookup_codes:
                    lookup_codes.append(booking_code)
                session[LOOKUP_KEY] = lookup_codes
                session.modified = True
                return redirect(url_for("trip_detail", booking_code=booking_code))
        flash("No demo trip matched that lookup combination.", "danger")
    return render_template("trip_lookup.html", booking=booking)


def user_can_view_booking(booking):
    if current_user.is_authenticated and booking.user_id == current_user.id:
        return True
    return booking.booking_code in session.get(LOOKUP_KEY, [])


@app.route("/trip/<booking_code>")
def trip_detail(booking_code):
    booking = Booking.query.filter_by(booking_code=booking_code.upper()).first_or_404()
    if not user_can_view_booking(booking):
        abort(403)
    return render_template("trip_detail.html", booking=booking)


@app.route("/trip/<booking_code>/cancel", methods=["POST"])
def trip_cancel(booking_code):
    booking = Booking.query.filter_by(booking_code=booking_code.upper()).first_or_404()
    if not user_can_view_booking(booking):
        abort(403)
    booking.status = "Cancelled"
    db.session.commit()
    flash("This demo trip has been marked as cancelled locally.", "success")
    return redirect(url_for("trip_detail", booking_code=booking.booking_code))


@app.route("/trip/<booking_code>/change", methods=["POST"])
def trip_change(booking_code):
    booking = Booking.query.filter_by(booking_code=booking_code.upper()).first_or_404()
    if not user_can_view_booking(booking):
        abort(403)
    booking.notes = (booking.notes or "") + " Demo change request noted."
    db.session.commit()
    flash("Change request recorded as a local demo note only.", "success")
    return redirect(url_for("trip_detail", booking_code=booking.booking_code))


@app.route("/_health")
def health():
    return jsonify({"ok": True, "site": "amtrak", "db": DB_PATH.exists()})


with app.app_context():
    db.create_all()
    from seed_data import seed_benchmark_users, seed_database

    models = SimpleNamespace(
        Booking=Booking,
        BookingSegment=BookingSegment,
        City=City,
        Deal=Deal,
        FareClass=FareClass,
        FareOption=FareOption,
        HelpArticle=HelpArticle,
        Passenger=Passenger,
        PaymentMock=PaymentMock,
        RewardAccount=RewardAccount,
        RewardActivity=RewardActivity,
        Route=Route,
        RouteStop=RouteStop,
        SearchLog=SearchLog,
        ServiceAlert=ServiceAlert,
        SleeperRoom=SleeperRoom,
        Station=Station,
        Ticket=Ticket,
        Train=Train,
        Trip=Trip,
        TripSegment=TripSegment,
        User=User,
    )
    seed_database(db, models, BASE_DIR)
    seed_benchmark_users(db, models, BASE_DIR)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
