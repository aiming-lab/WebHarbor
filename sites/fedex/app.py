"""FedEx local demo mirror for WebHarbor."""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import func, or_
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from rate_quote import QuoteRequest, issue_quote_token, verify_quote_token
from shipping_rules import (
    DEMO_INVOICE_DUE_DATE,
    DEMO_SHIP_DATE,
    LABEL_CREATED_STATUS,
    LABEL_CREATED_SUMMARY,
    delivery_estimate,
    initial_timeline,
    plan_account_number,
    plan_pickup_code,
    plan_shipment_identifiers,
    quote_price,
    shipment_zone,
)

BASE_DIR = Path(__file__).resolve().parent

# seed_data imports these models by module name, including when this file is
# launched as a script. Registering the alias keeps one Flask app and one
# SQLAlchemy instance instead of building a second set under the name "app".
if __name__ == "__main__":
    sys.modules["app"] = sys.modules[__name__]

INSTANCE_DIR = BASE_DIR / "instance"
DB_PATH = INSTANCE_DIR / "fedex.db"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

# Upper bound for a request body. The shipping and pickup forms are small, so a
# larger body is a client error rather than something to buffer.
MAX_CONTENT_LENGTH = 256 * 1024

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config["SECRET_KEY"] = os.environ.get("FEDEX_SECRET_KEY") or secrets.token_hex(32)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("FEDEX_DATABASE_URI", f"sqlite:///{DB_PATH}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db = SQLAlchemy(app)


@sqlalchemy_event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, _record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to use this local FedEx demo."
login_manager.login_message_category = "info"
csrf = CSRFProtect(app)

DEMO_PASSWORD = "TestPass123!"
STATE_LABELS = [
    "CA", "WA", "TX", "FL", "NY", "GA", "IL", "PA",
    "MA", "CO", "AZ", "OR", "NC", "OH", "MI", "VA", "DC",
]
PACKAGE_TYPES = ("Envelope", "Box", "Tube", "Pak", "Freight pallet")
PICKUP_MODES = (
    ("dropoff", "Drop off at staffed location"),
    ("pickup", "Schedule courier pickup"),
    ("dropbox", "Use after-hours drop box"),
)
PICKUP_MODE_VALUES = tuple(value for value, _label in PICKUP_MODES)
PICKUP_MODE_LABELS = dict(PICKUP_MODES)
DEMO_SHIPMENT_LABEL = "Local demo shipment"


# Field limits for every persisted user-supplied value. SQLite does not
# enforce declared VARCHAR lengths, so the application bounds them explicitly.
MAX_NAME = 80
MAX_TEXT = 120
MAX_CITY = 100
MAX_PHONE = 40
MAX_ZIP = 20
MAX_EMAIL = 120
MAX_QUERY = 180
MAX_TRACKING_INPUT = 400
MAX_TRACKING_NUMBERS = 30
MIN_WEIGHT_LB = 0.1
MIN_PASSWORD = 8
MAX_PASSWORD = 200
MAX_WEIGHT_LB = 1000.0
MAX_DECLARED_VALUE = 1000000.0
MAX_PACKAGE_COUNT = 20

# Upper bound on one search result list. It has to be large enough that a bounded
# catalogue is never truncated: the site seeds 18 support articles and 15
# locations, and a task may require opening a match that sorts last. A smaller
# bound would silently drop that match from the only route the task permits.
MAX_SEARCH_RESULTS = 24
PHONE_PATTERN = re.compile(r"^[0-9+().\- ]{7,40}$")
ZIP_PATTERN = re.compile(r"^[0-9]{5}(?:-[0-9]{4})?$")


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def loads_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(40), default="")
    company = db.Column(db.String(120), default="")
    city = db.Column(db.String(100), default="")
    state = db.Column(db.String(40), default="")
    zip_code = db.Column(db.String(20), default="")
    account_number = db.Column(db.String(30), unique=True, nullable=False)
    preferred_location_slug = db.Column(db.String(120), default="")
    invoicing_email = db.Column(db.String(120), default="")

    shipments = db.relationship("Shipment", backref="user", cascade="all, delete-orphan")
    tracking_records = db.relationship("TrackingRecord", backref="user", cascade="all, delete-orphan")
    invoices = db.relationship("Invoice", backref="user", cascade="all, delete-orphan")
    claims = db.relationship("Claim", backref="user", cascade="all, delete-orphan")
    pickup_requests = db.relationship("PickupRequest", backref="user", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class ServiceLevel(db.Model):
    __tablename__ = "service_levels"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    summary = db.Column(db.String(180), nullable=False)
    speed_label = db.Column(db.String(120), nullable=False)
    base_rate = db.Column(db.Float, nullable=False)
    per_lb_rate = db.Column(db.Float, nullable=False)
    zone_surcharge = db.Column(db.Float, nullable=False)
    weekend_delivery = db.Column(db.Boolean, default=False)
    money_back_label = db.Column(db.String(120), default="")
    sort_order = db.Column(db.Integer, default=0)


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    city = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(30), default="")
    location_type = db.Column(db.String(80), nullable=False)
    hours = db.Column(db.String(120), default="")
    services_json = db.Column(db.Text, default="[]")
    amenities_json = db.Column(db.Text, default="[]")
    pickup_note = db.Column(db.String(180), default="")

    pickup_slots = db.relationship("PickupSlot", backref="location", cascade="all, delete-orphan")
    pickup_requests = db.relationship("PickupRequest", backref="location", cascade="all, delete-orphan")

    @property
    def services(self) -> list[str]:
        return loads_json(self.services_json, [])

    @property
    def amenities(self) -> list[str]:
        return loads_json(self.amenities_json, [])


class TrackingRecord(db.Model):
    __tablename__ = "tracking_records"

    id = db.Column(db.Integer, primary_key=True)
    tracking_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipments.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    recipient_name = db.Column(db.String(120), nullable=False)
    sender_name = db.Column(db.String(120), nullable=False)
    origin_city = db.Column(db.String(100), nullable=False)
    origin_state = db.Column(db.String(40), nullable=False)
    destination_city = db.Column(db.String(100), nullable=False)
    destination_state = db.Column(db.String(40), nullable=False)
    service_slug = db.Column(db.String(60), nullable=False)
    package_type = db.Column(db.String(80), nullable=False)
    weight_lb = db.Column(db.Float, nullable=False)
    status_stage = db.Column(db.String(80), nullable=False)
    status_summary = db.Column(db.String(180), nullable=False)
    ship_date = db.Column(db.String(20), nullable=False)
    estimated_delivery = db.Column(db.String(40), nullable=False)
    latest_scan = db.Column(db.String(180), default="")
    package_count = db.Column(db.Integer, default=1)
    signature_required = db.Column(db.Boolean, default=False)
    dropoff_location_slug = db.Column(db.String(140), default="")

    shipment = db.relationship("Shipment", backref="tracking_record", uselist=False)
    events = db.relationship("TrackingEvent", backref="tracking_record", cascade="all, delete-orphan")

    __table_args__ = (
        # One tracking record per shipment keeps the shipment-to-record
        # relationship one-to-one in the database, not only by convention.
        db.UniqueConstraint("shipment_id", name="uq_tracking_records_shipment_id"),
    )


class TrackingEvent(db.Model):
    __tablename__ = "tracking_events"

    id = db.Column(db.Integer, primary_key=True)
    tracking_record_id = db.Column(db.Integer, db.ForeignKey("tracking_records.id"), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    event_time = db.Column(db.String(30), nullable=False)
    location_label = db.Column(db.String(160), nullable=False)
    status_label = db.Column(db.String(120), nullable=False)
    details = db.Column(db.String(220), nullable=False)


class Shipment(db.Model):
    __tablename__ = "shipments"

    id = db.Column(db.Integer, primary_key=True)
    shipment_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    tracking_number = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    service_slug = db.Column(db.String(60), nullable=False)
    package_type = db.Column(db.String(80), nullable=False)
    package_weight = db.Column(db.Float, nullable=False)
    origin_city = db.Column(db.String(100), nullable=False)
    origin_state = db.Column(db.String(40), nullable=False)
    destination_city = db.Column(db.String(100), nullable=False)
    destination_state = db.Column(db.String(40), nullable=False)
    recipient_name = db.Column(db.String(120), nullable=False)
    declared_value = db.Column(db.Float, default=0.0)
    total_cost = db.Column(db.Float, nullable=False)
    fulfillment_mode = db.Column(db.String(60), nullable=False)
    pickup_location_slug = db.Column(db.String(140), default="")
    pickup_window = db.Column(db.String(120), default="")
    status = db.Column(db.String(80), nullable=False)
    created_on = db.Column(db.String(20), nullable=False)
    invoice_number = db.Column(db.String(30), default="")
    reference_label = db.Column(db.String(160), default="")


class PickupSlot(db.Model):
    __tablename__ = "pickup_slots"

    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    slot_date = db.Column(db.String(20), nullable=False)
    time_window = db.Column(db.String(80), nullable=False)
    remaining_capacity = db.Column(db.Integer, default=0)
    cutoff_note = db.Column(db.String(120), default="")


class PickupRequest(db.Model):
    __tablename__ = "pickup_requests"

    id = db.Column(db.Integer, primary_key=True)
    confirmation_code = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    slot_date = db.Column(db.String(20), nullable=False)
    time_window = db.Column(db.String(80), nullable=False)
    package_count = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(80), nullable=False)
    created_on = db.Column(db.String(20), nullable=False)


class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipments.id"), nullable=False)
    billed_on = db.Column(db.String(20), nullable=False)
    due_date = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(80), nullable=False)

    shipment = db.relationship("Shipment")


class Claim(db.Model):
    __tablename__ = "claims"

    id = db.Column(db.Integer, primary_key=True)
    claim_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tracking_number = db.Column(db.String(30), nullable=False)
    claim_type = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(80), nullable=False)
    opened_on = db.Column(db.String(20), nullable=False)
    note = db.Column(db.Text, default="")


class SupportArticle(db.Model):
    __tablename__ = "support_articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    category = db.Column(db.String(120), nullable=False)
    summary = db.Column(db.String(240), nullable=False)
    body = db.Column(db.Text, nullable=False)
    related_topics_json = db.Column(db.Text, default="[]")

    @property
    def related_topics(self) -> list[str]:
        return loads_json(self.related_topics_json, [])


class SearchLog(db.Model):
    __tablename__ = "search_logs"

    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(180), nullable=False)
    search_type = db.Column(db.String(80), nullable=False)
    created_on = db.Column(db.String(20), nullable=False)


class SeedMetadata(db.Model):
    """Records which source built this database.

    A verifier can therefore reject a database produced by different code instead
    of grading against stale expectations.
    """

    __tablename__ = "seed_metadata"

    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(120), nullable=False)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    try:
        key = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, key)


@app.template_filter("money")
def money(value: float) -> str:
    return f"${value:,.2f}"


def location_exists(slug: str) -> bool:
    return bool(slug) and Location.query.filter_by(slug=slug).first() is not None


def bounded_text(value: Any, limit: int) -> str | None:
    """Return a stripped string within `limit`, or None when unusable."""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) > limit:
        return None
    return text


def valid_email(value: str) -> bool:
    # This site is an offline demo, so deliverability is not checked and the
    # RFC 6761 special-use names are accepted: email_validator documents
    # test_environment as the switch for application-level test environments,
    # and rejecting "@*.test" here would only surprise a demo user.
    try:
        validate_email(value, check_deliverability=False, test_environment=True)
    except EmailNotValidError:
        return False
    return len(value) <= MAX_EMAIL


def valid_state(value: str) -> bool:
    return value in STATE_LABELS


def finite_float(value: Any, minimum: float, maximum: float) -> float | None:
    """Parse a finite float within [minimum, maximum], else None."""
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < minimum or number > maximum:
        return None
    return number


def bounded_int(value: Any, minimum: int, maximum: int) -> int | None:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number < minimum or number > maximum:
        return None
    return number


def safe_redirect(value: Any, fallback: str) -> str:
    """Accept only same-origin local paths, matching the Compass convention."""
    if not value or not isinstance(value, str):
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


def column_values(model: Any, column: Any) -> list[str]:
    """Return every stored value of one identifier column."""
    return [str(value) for (value,) in db.session.query(column).all() if value is not None]


def ship_state() -> dict[str, Any]:
    return session.setdefault("ship_state", {})


def clear_ship_state() -> None:
    session.pop("ship_state", None)


def support_query(query_text: str):
    token_like = f"%{query_text}%"
    return SupportArticle.query.filter(
        or_(
            SupportArticle.title.ilike(token_like),
            SupportArticle.summary.ilike(token_like),
            SupportArticle.body.ilike(token_like),
            SupportArticle.category.ilike(token_like),
        )
    )


def normalize_tracking_inputs(raw: str) -> list[str]:
    tokens = [piece.strip().upper() for piece in raw.replace("\n", ",").split(",")]
    return [token for token in tokens if token]


def build_rate_quotes(origin_state: str, destination_state: str, weight_lb: float, package_type: str) -> list[dict[str, Any]]:
    """Build the displayed quote cards from the seeded service levels.

    The zone and price rules live in `shipping_rules` so the site and its
    verifiers compute identical values from the same seeded rate columns.
    """
    zone = shipment_zone(origin_state, destination_state)
    quotes = []
    for service in ServiceLevel.query.order_by(ServiceLevel.sort_order.asc()).all():
        price = quote_price(service.base_rate, service.per_lb_rate, service.zone_surcharge,
                            weight_lb, package_type, zone)
        quotes.append(
            {
                "service": service,
                "price": price,
                "zone": zone,
                "commitment": service.speed_label,
            }
        )
    return quotes


def validate_ship_form(form: Any, user: "User") -> tuple[dict[str, Any], list[str]]:
    """Validate the shipment-details form.

    Returns the normalized draft that is safe to keep in the session plus the
    list of user-facing errors. Only bounded, typed, reference-checked values are
    stored, so a later step can never read an unparsable draft.
    """
    errors: list[str] = []
    draft: dict[str, Any] = {}

    recipient = bounded_text(form.get("recipient_name"), MAX_NAME)
    if not recipient:
        errors.append(f"Enter a recipient name of up to {MAX_NAME} characters.")
    draft["recipient_name"] = recipient or ""

    origin_city = bounded_text(form.get("origin_city"), MAX_CITY)
    if origin_city is None:
        errors.append(f"Enter an origin city of up to {MAX_CITY} characters.")
        origin_city = ""
    if not origin_city:
        origin_city = (user.city or "").strip()[:MAX_CITY]
    if not origin_city:
        errors.append("Enter an origin city.")
    draft["origin_city"] = origin_city

    destination_city = bounded_text(form.get("destination_city"), MAX_CITY)
    if not destination_city:
        errors.append(f"Enter a destination city of up to {MAX_CITY} characters.")
    draft["destination_city"] = destination_city or ""

    origin_state = bounded_text(form.get("origin_state"), 2)
    destination_state = bounded_text(form.get("destination_state"), 2)
    if not origin_state or not valid_state(origin_state):
        errors.append("Choose a valid origin state.")
    if not destination_state or not valid_state(destination_state):
        errors.append("Choose a valid destination state.")
    draft["origin_state"] = origin_state or ""
    draft["destination_state"] = destination_state or ""

    package_type = bounded_text(form.get("package_type"), MAX_TEXT)
    if package_type not in PACKAGE_TYPES:
        errors.append("Choose one of the listed package types.")
    draft["package_type"] = package_type if package_type in PACKAGE_TYPES else "Box"

    pickup_mode = bounded_text(form.get("pickup_mode"), MAX_TEXT)
    if pickup_mode not in PICKUP_MODE_VALUES:
        errors.append("Choose one of the listed handoff modes.")
    draft["pickup_mode"] = pickup_mode if pickup_mode in PICKUP_MODE_VALUES else "dropoff"

    weight = finite_float(form.get("weight_lb"), MIN_WEIGHT_LB, MAX_WEIGHT_LB)
    if weight is None:
        errors.append(f"Enter a weight between {MIN_WEIGHT_LB:g} and {MAX_WEIGHT_LB:g} lb.")
    draft["weight_lb"] = weight if weight is not None else 0.0

    declared_value = finite_float(form.get("declared_value"), 0.0, MAX_DECLARED_VALUE)
    if declared_value is None:
        errors.append(f"Enter a declared value between 0 and {MAX_DECLARED_VALUE:,.0f}.")
    draft["declared_value"] = declared_value if declared_value is not None else 0.0

    preferred = bounded_text(user.preferred_location_slug, MAX_TEXT) or ""
    draft["pickup_location_slug"] = preferred if preferred and location_exists(preferred) else ""
    return draft, errors


def validated_ship_draft(state: Any, user: "User") -> tuple[dict[str, Any] | None, list[str]]:
    """Re-validate a stored shipment draft before a later step uses it.

    Every step re-checks the draft instead of trusting the session, so a stale or
    hand-edited session can never reach a float conversion or a database write.
    """
    restart = ["Start with shipment details again."]
    if not isinstance(state, dict) or not state:
        return None, restart
    recipient = bounded_text(state.get("recipient_name"), MAX_NAME)
    origin_city = bounded_text(state.get("origin_city"), MAX_CITY)
    destination_city = bounded_text(state.get("destination_city"), MAX_CITY)
    origin_state = bounded_text(state.get("origin_state"), 2)
    destination_state = bounded_text(state.get("destination_state"), 2)
    package_type = bounded_text(state.get("package_type"), MAX_TEXT)
    pickup_mode = bounded_text(state.get("pickup_mode"), MAX_TEXT)
    weight = state.get("weight_lb")
    declared_value = state.get("declared_value")
    if not recipient or not origin_city or not destination_city:
        return None, restart
    if not origin_state or not valid_state(origin_state):
        return None, restart
    if not destination_state or not valid_state(destination_state):
        return None, restart
    if package_type not in PACKAGE_TYPES or pickup_mode not in PICKUP_MODE_VALUES:
        return None, restart
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) \
            or not MIN_WEIGHT_LB <= float(weight) <= MAX_WEIGHT_LB:
        return None, restart
    if isinstance(declared_value, bool) or not isinstance(declared_value, (int, float)) \
            or not math.isfinite(declared_value) or not 0.0 <= float(declared_value) <= MAX_DECLARED_VALUE:
        return None, restart
    pickup_slug = bounded_text(state.get("pickup_location_slug"), MAX_TEXT) or ""
    if pickup_slug and not location_exists(pickup_slug):
        pickup_slug = ""
    if not pickup_slug:
        preferred = bounded_text(user.preferred_location_slug, MAX_TEXT) or ""
        if preferred and location_exists(preferred):
            pickup_slug = preferred
    return {
        "recipient_name": recipient,
        "origin_city": origin_city,
        "origin_state": origin_state,
        "destination_city": destination_city,
        "destination_state": destination_state,
        "package_type": package_type,
        "pickup_mode": pickup_mode,
        "weight_lb": float(weight),
        "declared_value": float(declared_value),
        "pickup_location_slug": pickup_slug,
    }, []


def current_pickups() -> list[PickupRequest]:
    if not current_user.is_authenticated:
        return []
    return (
        PickupRequest.query.filter_by(user_id=current_user.id)
        .order_by(PickupRequest.slot_date.asc(), PickupRequest.time_window.asc())
        .all()
    )


@app.context_processor
def inject_globals() -> dict[str, Any]:
    locations = Location.query.order_by(Location.city.asc()).all()
    services = ServiceLevel.query.order_by(ServiceLevel.sort_order.asc()).all()
    account_links = []
    if current_user.is_authenticated:
        account_links = current_pickups()[:2]
    return {
        "demo_password": DEMO_PASSWORD,
        "state_labels": STATE_LABELS,
        "package_types": PACKAGE_TYPES,
        "pickup_modes": PICKUP_MODES,
        "pickup_mode_labels": PICKUP_MODE_LABELS,
        "all_locations": locations,
        "nav_locations": locations[:5],
        "nav_services": services,
        "nav_pickups": account_links,
    }


@app.route("/")
@app.route("/home")
def index():
    featured_tracking = TrackingRecord.query.order_by(TrackingRecord.ship_date.desc()).limit(4).all()
    locations = Location.query.order_by(Location.city.asc()).limit(4).all()
    services = ServiceLevel.query.order_by(ServiceLevel.sort_order.asc()).all()
    articles = SupportArticle.query.order_by(SupportArticle.category.asc(), SupportArticle.title.asc()).limit(6).all()
    return render_template(
        "index.html",
        featured_tracking=featured_tracking,
        locations=locations,
        services=services,
        articles=articles,
    )


@app.route("/track", methods=["GET", "POST"])
def track():
    if request.method == "POST":
        numbers = request.form.get("tracking_numbers", "")
        numbers = numbers.strip() if isinstance(numbers, str) else ""
        if len(numbers) > MAX_TRACKING_INPUT:
            flash(f"Enter at most {MAX_TRACKING_NUMBERS} tracking numbers.", "danger")
            return render_template("track.html"), 400
        return redirect(url_for("track_results", numbers=numbers))
    return render_template("track.html")


@app.route("/track/results")
def track_results():
    raw = request.args.get("numbers", "")
    rejected = not isinstance(raw, str) or len(raw) > MAX_TRACKING_INPUT
    numbers = [] if rejected else normalize_tracking_inputs(raw)
    if len(numbers) > MAX_TRACKING_NUMBERS:
        rejected = True
        numbers = []
    records = []
    if numbers:
        found = TrackingRecord.query.filter(TrackingRecord.tracking_number.in_(numbers)).all()
        by_number = {record.tracking_number: record for record in found}
        records = [by_number[number] for number in numbers if number in by_number]
    return render_template("track_results.html", numbers=numbers, records=records,
                           query_rejected=rejected)


@app.route("/tracking/<tracking_number>")
def tracking_detail(tracking_number: str):
    if len(tracking_number) > 30:
        abort(404)
    record = TrackingRecord.query.filter_by(tracking_number=tracking_number.upper()).first_or_404()
    service = ServiceLevel.query.filter_by(slug=record.service_slug).first()
    events = TrackingEvent.query.filter_by(tracking_record_id=record.id).order_by(TrackingEvent.sequence.asc()).all()
    return render_template("tracking_detail.html", record=record, service=service, events=events)


@app.route("/rate-estimate", methods=["GET", "POST"])
def rate_estimate():
    quotes = None
    # No field arrives pre-filled. A default here would be a value the run is asked
    # to supply, and one rate task's lane, weight and package type were previously
    # carried by these defaults, which reduced that task to a single submit.
    raw_state = {
        "origin_state": request.values.get("origin_state", ""),
        "destination_state": request.values.get("destination_state", ""),
        "weight_lb": request.values.get("weight_lb", ""),
        "package_type": request.values.get("package_type", ""),
    }
    form_state = {key: (value if isinstance(value, str) else "") for key, value in raw_state.items()}
    if request.method == "GET" and request.args.get("quote"):
        quote_request = verify_quote_token(request.args["quote"])
        if quote_request is None:
            flash("That rate estimate link is invalid. Submit the form again.", "danger")
        else:
            form_state = {
                "origin_state": quote_request.origin_state,
                "destination_state": quote_request.destination_state,
                "weight_lb": f"{quote_request.weight_lb:g}",
                "package_type": quote_request.package_type,
            }
            quotes = build_rate_quotes(
                quote_request.origin_state,
                quote_request.destination_state,
                quote_request.weight_lb,
                quote_request.package_type,
            )
    elif request.method == "POST":
        weight = finite_float(form_state["weight_lb"], MIN_WEIGHT_LB, MAX_WEIGHT_LB)
        origin = bounded_text(form_state["origin_state"], 2)
        destination = bounded_text(form_state["destination_state"], 2)
        package_type = bounded_text(form_state["package_type"], MAX_TEXT)
        if weight is None:
            flash(f"Enter a weight between {MIN_WEIGHT_LB:g} and {MAX_WEIGHT_LB:g} lb.", "danger")
        elif not (origin and valid_state(origin) and destination and valid_state(destination)):
            flash("Choose a valid origin and destination state.", "danger")
        elif package_type not in PACKAGE_TYPES:
            flash("Choose one of the listed package types.", "danger")
        else:
            quote_request = QuoteRequest(
                origin_state=origin,
                destination_state=destination,
                weight_lb=weight,
                package_type=package_type,
            )
            return redirect(url_for("rate_estimate", quote=issue_quote_token(quote_request)))
        return render_template("rate_estimate.html", quotes=quotes, form_state=form_state), 400
    return render_template("rate_estimate.html", quotes=quotes, form_state=form_state)


@app.route("/ship", methods=["GET", "POST"])
@login_required
def ship():
    state = ship_state()
    if request.method == "POST":
        submitted, errors = validate_ship_form(request.form, current_user)
        if errors:
            # Keep nothing in the session: a draft that failed validation must not
            # become a later step's input. Re-rendering with the submitted values
            # still preserves what the user typed.
            state.clear()
            session.modified = True
            for message in errors:
                flash(message, "danger")
            return render_template("ship.html", state=submitted), 400
        state.clear()
        state.update(submitted)
        session.modified = True
        return redirect(url_for("ship_service"))
    return render_template("ship.html", state=state)


@app.route("/ship/service", methods=["GET", "POST"])
@login_required
def ship_service():
    state = ship_state()
    draft, errors = validated_ship_draft(state, current_user)
    if draft is None:
        state.clear()
        session.modified = True
        for message in errors:
            flash(message, "warning")
        return redirect(url_for("ship"))
    quotes = build_rate_quotes(draft["origin_state"], draft["destination_state"],
                               draft["weight_lb"], draft["package_type"])
    if request.method == "POST":
        slug = bounded_text(request.form.get("service_slug"), MAX_TEXT)
        service = ServiceLevel.query.filter_by(slug=slug).first() if slug else None
        if service is None:
            flash("Choose one of the listed service levels.", "danger")
            return render_template("ship_service.html", state=state, quotes=quotes), 400
        state["service_slug"] = service.slug
        session.modified = True
        return redirect(url_for("ship_review"))
    return render_template("ship_service.html", state=state, quotes=quotes)


@app.route("/ship/review", methods=["GET", "POST"])
@login_required
def ship_review():
    state = ship_state()
    draft, errors = validated_ship_draft(state, current_user)
    if draft is None:
        state.clear()
        session.modified = True
        for message in errors:
            flash(message, "warning")
        return redirect(url_for("ship"))
    slug = bounded_text(state.get("service_slug"), MAX_TEXT)
    service = ServiceLevel.query.filter_by(slug=slug).first() if slug else None
    if service is None:
        state.pop("service_slug", None)
        session.modified = True
        flash("Choose a service level first.", "warning")
        return redirect(url_for("ship_service"))
    quotes = build_rate_quotes(draft["origin_state"], draft["destination_state"],
                               draft["weight_lb"], draft["package_type"])
    selected_quote = next((quote for quote in quotes if quote["service"].slug == service.slug), None)
    if request.method != "POST":
        return render_template(
            "ship_review.html",
            state=state,
            service=service,
            selected_quote=selected_quote,
        )

    total_cost = selected_quote["price"] if selected_quote else 0.0
    pickup_slug = draft["pickup_location_slug"]
    for attempt in range(3):
        shipment_code, tracking_number, invoice_number = plan_shipment_identifiers(
            column_values(Shipment, Shipment.shipment_code),
            column_values(TrackingRecord, TrackingRecord.tracking_number),
            column_values(Invoice, Invoice.invoice_number),
        )
        shipment = Shipment(
            shipment_code=shipment_code,
            tracking_number=tracking_number,
            user_id=current_user.id,
            service_slug=service.slug,
            package_type=draft["package_type"],
            package_weight=draft["weight_lb"],
            origin_city=draft["origin_city"],
            origin_state=draft["origin_state"],
            destination_city=draft["destination_city"],
            destination_state=draft["destination_state"],
            recipient_name=draft["recipient_name"],
            declared_value=draft["declared_value"],
            total_cost=total_cost,
            fulfillment_mode=draft["pickup_mode"],
            pickup_location_slug=pickup_slug,
            pickup_window="",
            status=LABEL_CREATED_STATUS,
            created_on=DEMO_SHIP_DATE,
            invoice_number=invoice_number,
            reference_label=DEMO_SHIPMENT_LABEL,
        )
        db.session.add(shipment)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            continue
        tracking = TrackingRecord(
            tracking_number=tracking_number,
            shipment_id=shipment.id,
            user_id=current_user.id,
            recipient_name=shipment.recipient_name,
            sender_name=current_user.full_name,
            origin_city=shipment.origin_city,
            origin_state=shipment.origin_state,
            destination_city=shipment.destination_city,
            destination_state=shipment.destination_state,
            service_slug=shipment.service_slug,
            package_type=shipment.package_type,
            weight_lb=shipment.package_weight,
            status_stage=LABEL_CREATED_STATUS,
            status_summary=LABEL_CREATED_SUMMARY,
            ship_date=DEMO_SHIP_DATE,
            estimated_delivery=delivery_estimate(service.slug, DEMO_SHIP_DATE),
            latest_scan=LABEL_CREATED_STATUS,
            package_count=1,
            signature_required=False,
            dropoff_location_slug=pickup_slug,
        )
        db.session.add(tracking)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            continue
        db.session.add_all(
            [
                TrackingEvent(
                    tracking_record_id=tracking.id,
                    sequence=event["sequence"],
                    event_time=event["event_time"],
                    location_label=event["location_label"],
                    status_label=event["status_label"],
                    details=event["details"],
                )
                for event in initial_timeline(shipment.origin_city, shipment.origin_state, DEMO_SHIP_DATE)
            ]
        )
        db.session.add(
            Invoice(
                invoice_number=invoice_number,
                user_id=current_user.id,
                shipment_id=shipment.id,
                billed_on=DEMO_SHIP_DATE,
                due_date=DEMO_INVOICE_DUE_DATE,
                amount=total_cost,
                status="Open",
            )
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            continue
        clear_ship_state()
        session["shipment_confirmation_code"] = shipment_code
        return redirect(url_for("ship_confirmation"))
    flash("That mock shipment could not be saved. Please submit the flow again.", "danger")
    return redirect(url_for("ship_review")), 409


@app.route("/ship/confirmation")
@login_required
def ship_confirmation():
    shipment_code = session.get("shipment_confirmation_code")
    if not shipment_code:
        flash("No recent mock shipment is available.", "warning")
        return redirect(url_for("account_shipments"))
    shipment = Shipment.query.filter_by(shipment_code=shipment_code, user_id=current_user.id).first_or_404()
    return render_template("ship_confirmation.html", shipment=shipment)


@app.route("/pickup", methods=["GET", "POST"])
@login_required
def pickup():
    locations = Location.query.order_by(Location.city.asc()).all()
    # Nothing is pre-selected. The account's preferred location is the run's own
    # profile data, and defaulting to it would hand over a location a task asks the
    # run to choose; the window list likewise stays empty until a location is
    # picked, because the earliest window is itself a graded value.
    requested = bounded_text(request.values.get("location_slug"), MAX_TEXT) or ""
    location = Location.query.filter_by(slug=requested).first() if requested else None
    selected_slug = location.slug if location else ""
    slots = []
    if location:
        slots = (
            PickupSlot.query.filter_by(location_id=location.id)
            .order_by(PickupSlot.slot_date.asc(), PickupSlot.id.asc())
            .all()
        )
    if request.method != "POST":
        return render_template("pickup.html", locations=locations, selected_slug=selected_slug, slots=slots)

    package_count = bounded_int(request.form.get("package_count"), 1, MAX_PACKAGE_COUNT)
    slot_id = bounded_int(request.form.get("pickup_slot_id"), 1, 1_000_000)
    slot = PickupSlot.query.filter_by(id=slot_id).first() if slot_id else None
    if package_count is None:
        flash(f"Enter a package count between 1 and {MAX_PACKAGE_COUNT}.", "danger")
        return render_template("pickup.html", locations=locations, selected_slug=selected_slug,
                               slots=slots), 400
    if location is None:
        flash("Choose one of the listed pickup locations.", "danger")
        return render_template("pickup.html", locations=locations, selected_slug=selected_slug,
                               slots=slots), 400
    if slot is None or slot.location_id != location.id:
        flash("Choose one of the pickup slots listed for that location.", "danger")
        return render_template("pickup.html", locations=locations, selected_slug=selected_slug,
                               slots=slots), 400
    if (slot.remaining_capacity or 0) < 1:
        flash("That pickup slot is fully booked. Choose another slot.", "danger")
        return render_template("pickup.html", locations=locations, selected_slug=selected_slug,
                               slots=slots), 409

    for _attempt in range(3):
        confirmation_code = plan_pickup_code(column_values(PickupRequest, PickupRequest.confirmation_code))
        pickup_request = PickupRequest(
            confirmation_code=confirmation_code,
            user_id=current_user.id,
            location_id=slot.location_id,
            slot_date=slot.slot_date,
            time_window=slot.time_window,
            package_count=package_count,
            status="Scheduled",
            created_on=DEMO_SHIP_DATE,
        )
        slot.remaining_capacity = (slot.remaining_capacity or 0) - 1
        db.session.add(pickup_request)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            slot = PickupSlot.query.filter_by(id=slot_id).first()
            if slot is None:
                break
            continue
        flash(f"Pickup {pickup_request.confirmation_code} scheduled in this local demo.", "success")
        return redirect(url_for("account"))
    flash("That pickup could not be scheduled. Please choose another slot.", "danger")
    return redirect(url_for("pickup")), 409


@app.route("/locations")
def locations():
    raw_query = request.args.get("q", "")
    rejected = not isinstance(raw_query, str) or len(raw_query) > MAX_QUERY
    query = "" if rejected else raw_query.strip()
    locations_query = Location.query
    if query:
        token_like = f"%{query}%"
        locations_query = locations_query.filter(
            or_(
                Location.name.ilike(token_like),
                Location.city.ilike(token_like),
                Location.state.ilike(token_like),
                Location.location_type.ilike(token_like),
            )
        )
    locations_list = locations_query.order_by(Location.state.asc(), Location.city.asc()).all()
    return render_template("locations.html", locations=locations_list, query=query,
                           query_rejected=rejected)


@app.route("/locations/<location_slug>")
def location_detail(location_slug: str):
    location = Location.query.filter_by(slug=location_slug).first_or_404()
    slots = PickupSlot.query.filter_by(location_id=location.id).order_by(PickupSlot.slot_date.asc()).all()
    return render_template("location_detail.html", location=location, slots=slots)


@app.route("/support")
def support():
    raw_query = request.args.get("q", "")
    rejected = not isinstance(raw_query, str) or len(raw_query) > MAX_QUERY
    query = "" if rejected else raw_query.strip()
    articles_query = SupportArticle.query
    if query:
        articles_query = support_query(query)
    articles = articles_query.order_by(SupportArticle.category.asc(), SupportArticle.title.asc()).all()
    return render_template("support.html", articles=articles, query=query, query_rejected=rejected)


@app.route("/support/<article_slug>")
def support_article(article_slug: str):
    article = SupportArticle.query.filter_by(slug=article_slug).first_or_404()
    related = (
        SupportArticle.query.filter(
            SupportArticle.category == article.category,
            SupportArticle.slug != article.slug,
        )
        .order_by(SupportArticle.title.asc())
        .limit(4)
        .all()
    )
    return render_template("support_article.html", article=article, related=related)


@app.route("/search")
def search():
    raw_query = request.args.get("q", "")
    if not isinstance(raw_query, str) or len(raw_query) > MAX_QUERY:
        return render_template("search.html", query="", articles=[], locations=[], tracking_matches=[],
                               query_rejected=True)
    query = raw_query.strip()
    articles = []
    locations = []
    tracking_matches = []
    # A read-only route must not write: browsing and searching leave the seeded
    # database byte-identical so reset and read-only state grading stay exact.
    if query:
        token_like = f"%{query}%"
        articles = (support_query(query)
                    .order_by(SupportArticle.category.asc(), SupportArticle.title.asc())
                    .limit(MAX_SEARCH_RESULTS).all())
        # Ordered by the same content-neutral rule the /locations directory uses,
        # so a match's rank comes from its state and city rather than from the
        # order the seed happened to insert rows in. The matched fields have to be
        # the directory's fields too: a location whose type is "Ship Center" but
        # whose name is not, such as the Dallas Arts District Hub, was previously
        # invisible to global search while the directory returned it.
        locations = Location.query.filter(
            or_(
                Location.city.ilike(token_like),
                Location.state.ilike(token_like),
                Location.name.ilike(token_like),
                Location.location_type.ilike(token_like),
            )
        ).order_by(Location.state.asc(), Location.city.asc()).limit(MAX_SEARCH_RESULTS).all()
        tracking_matches = TrackingRecord.query.filter(
            or_(
                TrackingRecord.tracking_number.ilike(token_like),
                TrackingRecord.recipient_name.ilike(token_like),
                TrackingRecord.status_summary.ilike(token_like),
            )
        ).order_by(TrackingRecord.tracking_number.asc()).limit(MAX_SEARCH_RESULTS).all()
    return render_template(
        "search.html",
        query=query,
        articles=articles,
        locations=locations,
        tracking_matches=tracking_matches,
    )


@app.route("/claims")
@login_required
def claims():
    user_claims = Claim.query.filter_by(user_id=current_user.id).order_by(Claim.opened_on.desc()).all()
    return render_template("claims.html", claims=user_claims)


@app.route("/invoices")
@login_required
def invoices():
    user_invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.billed_on.desc()).all()
    return render_template("invoices.html", invoices=user_invoices)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        raw_email = request.form.get("email", "")
        email = raw_email.strip().lower() if isinstance(raw_email, str) else ""
        password = request.form.get("password", "")
        password = password if isinstance(password, str) else ""
        if len(email) > MAX_EMAIL or len(password) > MAX_PASSWORD:
            flash("That demo sign-in did not match any seeded account.", "danger")
            return render_template("login.html"), 400
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            # Drop any anonymous session data before establishing the new one.
            session.clear()
            login_user(user)
            flash("Signed in to the local FedEx demo.", "success")
            return redirect(url_for("account"))
        flash("That demo sign-in did not match any seeded account.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method != "POST":
        return render_template("register.html")

    form, errors = validate_registration_form(request.form)
    if errors:
        for message in errors:
            flash(message, "danger")
        return render_template("register.html", form=form), 400
    if User.query.filter_by(email=form["email"]).first():
        flash("That email already exists in the local demo.", "warning")
        return redirect(url_for("login"))

    for _attempt in range(3):
        account_number = plan_account_number(column_values(User, User.account_number))
        user = User(
            email=form["email"],
            first_name=form["first_name"],
            last_name=form["last_name"],
            phone=form["phone"],
            company=form["company"],
            city=form["city"],
            state=form["state"],
            zip_code=form["zip_code"],
            account_number=account_number,
            preferred_location_slug=form["preferred_location_slug"],
            invoicing_email=form["email"],
        )
        user.set_password(form["password"])
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if User.query.filter_by(email=form["email"]).first():
                flash("That email already exists in the local demo.", "warning")
                return redirect(url_for("login"))
            continue
        session.clear()
        login_user(user)
        flash("Created a new local FedEx demo account.", "success")
        return redirect(url_for("account"))
    flash("That account could not be created. Please submit the form again.", "danger")
    return render_template("register.html", form=form), 409


def validate_registration_form(form: Any) -> tuple[dict[str, str], list[str]]:
    """Validate the registration form and return normalized values plus errors."""
    errors: list[str] = []
    values: dict[str, str] = {}

    raw_email = form.get("email", "")
    email = raw_email.strip().lower() if isinstance(raw_email, str) else ""
    if not email or len(email) > MAX_EMAIL or not valid_email(email):
        errors.append("Enter a valid email address.")
    values["email"] = email

    first_name = bounded_text(form.get("first_name"), MAX_NAME)
    last_name = bounded_text(form.get("last_name"), MAX_NAME)
    if not first_name:
        errors.append(f"Enter a first name of up to {MAX_NAME} characters.")
    if not last_name:
        errors.append(f"Enter a last name of up to {MAX_NAME} characters.")
    values["first_name"] = first_name or ""
    values["last_name"] = last_name or ""

    password = form.get("password", "")
    password = password if isinstance(password, str) else ""
    if len(password) < MIN_PASSWORD or len(password) > MAX_PASSWORD:
        errors.append(f"Enter a password between {MIN_PASSWORD} and {MAX_PASSWORD} characters.")
    values["password"] = password

    phone = bounded_text(form.get("phone", ""), MAX_PHONE)
    if phone is None:
        errors.append(f"Enter a phone number of up to {MAX_PHONE} characters.")
        phone = ""
    elif phone and not PHONE_PATTERN.fullmatch(phone):
        errors.append("Enter a phone number using digits, spaces, and + ( ) - . only.")
    values["phone"] = phone or ""

    company = bounded_text(form.get("company", ""), MAX_TEXT)
    if company is None:
        errors.append(f"Enter a company of up to {MAX_TEXT} characters.")
        company = ""
    values["company"] = company or ""

    city = bounded_text(form.get("city", ""), MAX_CITY)
    if city is None:
        errors.append(f"Enter a city of up to {MAX_CITY} characters.")
        city = ""
    values["city"] = city or ""

    state = bounded_text(form.get("state", ""), 2)
    if state is None or (state and not valid_state(state)):
        errors.append("Choose a valid state.")
        state = ""
    values["state"] = state or ""

    zip_code = bounded_text(form.get("zip_code", ""), MAX_ZIP)
    if zip_code is None:
        errors.append(f"Enter a ZIP code of up to {MAX_ZIP} characters.")
        zip_code = ""
    elif zip_code and not ZIP_PATTERN.fullmatch(zip_code):
        errors.append("Enter a ZIP code as 5 digits, optionally followed by -4 digits.")
    values["zip_code"] = zip_code or ""

    slug = bounded_text(form.get("preferred_location_slug", ""), MAX_TEXT)
    if slug is None:
        errors.append("Choose one of the listed preferred locations.")
        slug = ""
    elif slug and not location_exists(slug):
        errors.append("Choose one of the listed preferred locations.")
        slug = ""
    values["preferred_location_slug"] = slug or ""
    return values, errors


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    # A session change must not be reachable with GET or HEAD: browsers,
    # prefetchers, and crawlers issue both without user intent.
    logout_user()
    session.clear()
    flash("Signed out of the FedEx demo.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    shipments = Shipment.query.filter_by(user_id=current_user.id).order_by(Shipment.created_on.desc()).limit(4).all()
    invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.billed_on.desc()).limit(4).all()
    claims = Claim.query.filter_by(user_id=current_user.id).order_by(Claim.opened_on.desc()).limit(4).all()
    pickups = current_pickups()[:3]
    return render_template(
        "account.html",
        shipments=shipments,
        invoices=invoices,
        claims=claims,
        pickups=pickups,
    )


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method != "POST":
        return render_template("account_edit.html", form=None, errors=[])
    form, errors = validate_profile_form(request.form, current_user)
    if errors:
        for message in errors:
            flash(message, "danger")
        return render_template("account_edit.html", form=form, errors=errors), 400
    current_user.first_name = form["first_name"]
    current_user.last_name = form["last_name"]
    current_user.phone = form["phone"]
    current_user.company = form["company"]
    current_user.city = form["city"]
    current_user.state = form["state"]
    current_user.zip_code = form["zip_code"]
    current_user.preferred_location_slug = form["preferred_location_slug"]
    current_user.invoicing_email = form["invoicing_email"]
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Those profile updates could not be saved. Please review the fields.", "danger")
        return render_template("account_edit.html", form=form, errors=["conflict"]), 409
    flash("Saved your local FedEx profile updates.", "success")
    return redirect(url_for("account"))


def validate_profile_form(form: Any, user: "User") -> tuple[dict[str, str], list[str]]:
    """Validate the profile form.

    SQLite does not enforce the declared VARCHAR lengths and the form's dropdowns
    are only advisory, so every persisted field is bounded and reference-checked
    here before it is written.
    """
    errors: list[str] = []
    values: dict[str, str] = {}

    first_name = bounded_text(form.get("first_name", user.first_name), MAX_NAME)
    last_name = bounded_text(form.get("last_name", user.last_name), MAX_NAME)
    if not first_name:
        errors.append(f"Enter a first name of up to {MAX_NAME} characters.")
    if not last_name:
        errors.append(f"Enter a last name of up to {MAX_NAME} characters.")
    values["first_name"] = first_name or ""
    values["last_name"] = last_name or ""

    phone = bounded_text(form.get("phone", user.phone), MAX_PHONE)
    if phone is None:
        errors.append(f"Enter a phone number of up to {MAX_PHONE} characters.")
        phone = ""
    elif phone and not PHONE_PATTERN.fullmatch(phone):
        errors.append("Enter a phone number using digits, spaces, and + ( ) - . only.")
    values["phone"] = phone or ""

    company = bounded_text(form.get("company", user.company), MAX_TEXT)
    if company is None:
        errors.append(f"Enter a company of up to {MAX_TEXT} characters.")
        company = ""
    values["company"] = company or ""

    city = bounded_text(form.get("city", user.city), MAX_CITY)
    if city is None:
        errors.append(f"Enter a city of up to {MAX_CITY} characters.")
        city = ""
    values["city"] = city or ""

    state = bounded_text(form.get("state", user.state), 2)
    if state is None or (state and not valid_state(state)):
        errors.append("Choose a valid state.")
        state = ""
    values["state"] = state or ""

    zip_code = bounded_text(form.get("zip_code", user.zip_code), MAX_ZIP)
    if zip_code is None:
        errors.append(f"Enter a ZIP code of up to {MAX_ZIP} characters.")
        zip_code = ""
    elif zip_code and not ZIP_PATTERN.fullmatch(zip_code):
        errors.append("Enter a ZIP code as 5 digits, optionally followed by -4 digits.")
    values["zip_code"] = zip_code or ""

    slug = bounded_text(form.get("preferred_location_slug", user.preferred_location_slug), MAX_TEXT)
    if slug is None:
        errors.append("Choose one of the listed preferred locations.")
        slug = ""
    elif slug and not location_exists(slug):
        errors.append("Choose one of the listed preferred locations.")
        slug = ""
    values["preferred_location_slug"] = slug or ""

    invoicing_email = bounded_text(form.get("invoicing_email", user.invoicing_email), MAX_EMAIL)
    if invoicing_email is None:
        errors.append(f"Enter a billing email of up to {MAX_EMAIL} characters.")
        invoicing_email = ""
    elif invoicing_email and not valid_email(invoicing_email):
        errors.append("Enter a valid billing email address.")
    values["invoicing_email"] = invoicing_email or ""
    return values, errors


@app.route("/account/shipments")
@login_required
def account_shipments():
    shipments = Shipment.query.filter_by(user_id=current_user.id).order_by(Shipment.created_on.desc()).all()
    return render_template("account_shipments.html", shipments=shipments)


@app.post("/account/shipments/<shipment_code>/remove")
@login_required
def account_shipment_remove(shipment_code: str):
    if len(shipment_code) > 30:
        abort(404)
    shipment = Shipment.query.filter_by(
        shipment_code=shipment_code,
        user_id=current_user.id,
        reference_label=DEMO_SHIPMENT_LABEL,
    ).first_or_404()
    tracking = TrackingRecord.query.filter_by(shipment_id=shipment.id).first()
    if tracking is not None and Claim.query.filter_by(tracking_number=tracking.tracking_number).first() is not None:
        flash("That shipment has a claim on record, so it stays in your history.", "warning")
        return redirect(url_for("account_shipments"))
    Invoice.query.filter_by(shipment_id=shipment.id).delete(synchronize_session=False)
    if tracking:
        TrackingEvent.query.filter_by(tracking_record_id=tracking.id).delete(synchronize_session=False)
        db.session.delete(tracking)
    db.session.delete(shipment)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("That shipment could not be removed. Please try again.", "danger")
        return redirect(url_for("account_shipments")), 409
    if session.get("shipment_confirmation_code") == shipment_code:
        session.pop("shipment_confirmation_code", None)
    flash(f"Removed local demo shipment {shipment_code}.", "success")
    return redirect(url_for("account_shipments"))


@app.route("/account/invoices")
@login_required
def account_invoices():
    return redirect(url_for("invoices"))


@app.route("/account/claims")
@login_required
def account_claims():
    return redirect(url_for("claims"))


@app.route("/_health")
def health():
    return jsonify(
        {
            "ok": True,
            "site": "fedex",
            "tracking_records": TrackingRecord.query.count(),
            "shipments": Shipment.query.count(),
            "locations": Location.query.count(),
        }
    )


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return render_template("404.html", message="That action is not available for this page."), 405


@app.errorhandler(413)
def request_too_large(error):
    return render_template("404.html", message="That submission is larger than this local demo accepts."), 413


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


def bootstrap_site() -> None:
    from seed_data import seed_benchmark_users, seed_database

    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()


if os.environ.get("WEBSYN_SKIP_BOOTSTRAP") != "1":
    bootstrap_site()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
