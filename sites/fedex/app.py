"""FedEx local demo mirror for WebHarbor."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from flask import (
    Flask,
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
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DB_PATH = INSTANCE_DIR / "fedex.db"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config["SECRET_KEY"] = "webharbor-fedex-demo-key"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("FEDEX_DATABASE_URI", f"sqlite:///{DB_PATH}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to use this local FedEx demo."
login_manager.login_message_category = "info"

DEMO_PASSWORD = "TestPass123!"
STATE_LABELS = [
    "CA", "WA", "TX", "FL", "NY", "GA", "IL", "PA",
    "MA", "CO", "AZ", "OR", "NC", "OH", "MI", "VA", "DC",
]


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
    icon_path = db.Column(db.String(255), default="")
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
    image_path = db.Column(db.String(255), default="")
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


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


@app.template_filter("money")
def money(value: float) -> str:
    return f"${value:,.2f}"


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


def shipment_zone(origin_state: str, destination_state: str) -> int:
    if origin_state == destination_state:
        return 1
    west = {"CA", "WA", "OR", "AZ", "CO"}
    east = {"NY", "MA", "PA", "FL", "GA", "NC", "VA"}
    central = {"TX", "IL", "OH", "MI"}
    if origin_state in west and destination_state in west:
        return 2
    if origin_state in east and destination_state in east:
        return 2
    if origin_state in central and destination_state in central:
        return 2
    return 4


def build_rate_quotes(origin_state: str, destination_state: str, weight_lb: float, package_type: str) -> list[dict[str, Any]]:
    zone = shipment_zone(origin_state, destination_state)
    package_fee = {"Envelope": 0, "Box": 8, "Tube": 10, "Freight pallet": 48}.get(package_type, 6)
    quotes = []
    for service in ServiceLevel.query.order_by(ServiceLevel.sort_order.asc()).all():
        price = round(service.base_rate + service.per_lb_rate * weight_lb + service.zone_surcharge * zone + package_fee, 2)
        quotes.append(
            {
                "service": service,
                "price": price,
                "zone": zone,
                "commitment": service.speed_label,
            }
        )
    return quotes


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
        numbers = request.form.get("tracking_numbers", "").strip()
        return redirect(url_for("track_results", numbers=numbers))
    return render_template("track.html")


@app.route("/track/results")
def track_results():
    numbers = normalize_tracking_inputs(request.args.get("numbers", ""))
    records = []
    if numbers:
        records = TrackingRecord.query.filter(TrackingRecord.tracking_number.in_(numbers)).all()
        records.sort(key=lambda record: numbers.index(record.tracking_number))
    return render_template("track_results.html", numbers=numbers, records=records)


@app.route("/tracking/<tracking_number>")
def tracking_detail(tracking_number: str):
    record = TrackingRecord.query.filter_by(tracking_number=tracking_number.upper()).first_or_404()
    service = ServiceLevel.query.filter_by(slug=record.service_slug).first()
    events = TrackingEvent.query.filter_by(tracking_record_id=record.id).order_by(TrackingEvent.sequence.asc()).all()
    return render_template("tracking_detail.html", record=record, service=service, events=events)


@app.route("/rate-estimate", methods=["GET", "POST"])
def rate_estimate():
    quotes = None
    form_state = {
        "origin_state": request.values.get("origin_state", "CA"),
        "destination_state": request.values.get("destination_state", "TX"),
        "weight_lb": request.values.get("weight_lb", "8"),
        "package_type": request.values.get("package_type", "Box"),
    }
    if request.method == "POST":
        try:
            weight = float(form_state["weight_lb"])
            if weight <= 0:
                raise ValueError
        except (TypeError, ValueError):
            flash("Enter a weight greater than 0.", "danger")
        else:
            quotes = build_rate_quotes(
                form_state["origin_state"],
                form_state["destination_state"],
                weight,
                form_state["package_type"],
            )
    return render_template("rate_estimate.html", quotes=quotes, form_state=form_state)


@app.route("/ship", methods=["GET", "POST"])
@login_required
def ship():
    state = ship_state()
    if request.method == "POST":
        state["recipient_name"] = request.form.get("recipient_name", "").strip()
        state["origin_city"] = request.form.get("origin_city", current_user.city).strip()
        state["origin_state"] = request.form.get("origin_state", current_user.state).strip()
        state["destination_city"] = request.form.get("destination_city", "").strip()
        state["destination_state"] = request.form.get("destination_state", "").strip()
        state["package_type"] = request.form.get("package_type", "Box")
        state["weight_lb"] = request.form.get("weight_lb", "8").strip()
        state["declared_value"] = request.form.get("declared_value", "150").strip()
        state["pickup_mode"] = request.form.get("pickup_mode", "dropoff")
        session.modified = True
        valid_numbers = True
        try:
            if float(state["weight_lb"]) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            flash("Enter a weight greater than 0.", "danger")
            valid_numbers = False
        try:
            if float(state["declared_value"]) < 0:
                raise ValueError
        except (TypeError, ValueError):
            flash("Enter a declared value of at least 0.", "danger")
            valid_numbers = False
        if not valid_numbers:
            return render_template("ship.html", state=state)
        return redirect(url_for("ship_service"))
    return render_template("ship.html", state=state)


@app.route("/ship/service", methods=["GET", "POST"])
@login_required
def ship_service():
    state = ship_state()
    if not state.get("recipient_name"):
        flash("Start with shipment details first.", "warning")
        return redirect(url_for("ship"))
    quotes = build_rate_quotes(
        state.get("origin_state", current_user.state or "CA"),
        state.get("destination_state", "TX"),
        float(state.get("weight_lb", "8")),
        state.get("package_type", "Box"),
    )
    if request.method == "POST":
        state["service_slug"] = request.form.get("service_slug", "priority-overnight")
        session.modified = True
        return redirect(url_for("ship_review"))
    return render_template("ship_service.html", state=state, quotes=quotes)


@app.route("/ship/review", methods=["GET", "POST"])
@login_required
def ship_review():
    state = ship_state()
    if not state.get("service_slug"):
        flash("Choose a service level first.", "warning")
        return redirect(url_for("ship_service"))
    service = ServiceLevel.query.filter_by(slug=state["service_slug"]).first_or_404()
    quotes = build_rate_quotes(
        state.get("origin_state", current_user.state or "CA"),
        state.get("destination_state", "TX"),
        float(state.get("weight_lb", "8")),
        state.get("package_type", "Box"),
    )
    selected_quote = next((quote for quote in quotes if quote["service"].slug == service.slug), None)
    if request.method == "POST":
        next_index = (db.session.query(db.func.count(Shipment.id)).scalar() or 0) + 1
        shipment_code = f"SH-{260000 + next_index}"
        tracking_number = f"FDX{260000000 + next_index:09d}"
        invoice_number = f"INV-{260000 + next_index}"
        total_cost = selected_quote["price"] if selected_quote else 0.0
        shipment = Shipment(
            shipment_code=shipment_code,
            tracking_number=tracking_number,
            user_id=current_user.id,
            service_slug=service.slug,
            package_type=state.get("package_type", "Box"),
            package_weight=float(state.get("weight_lb", "8")),
            origin_city=state.get("origin_city", current_user.city),
            origin_state=state.get("origin_state", current_user.state),
            destination_city=state.get("destination_city", "Dallas"),
            destination_state=state.get("destination_state", "TX"),
            recipient_name=state.get("recipient_name", "Demo Recipient"),
            declared_value=float(state.get("declared_value", "150")),
            total_cost=total_cost,
            fulfillment_mode=state.get("pickup_mode", "dropoff"),
            pickup_location_slug=state.get("pickup_location_slug", current_user.preferred_location_slug),
            pickup_window=state.get("pickup_window", ""),
            status="Label created",
            created_on="2026-06-04",
            invoice_number=invoice_number,
            reference_label="Local demo shipment",
        )
        db.session.add(shipment)
        db.session.flush()
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
            status_stage="Label created",
            status_summary="Shipment information sent to local FedEx demo systems.",
            ship_date="2026-06-04",
            estimated_delivery="2026-06-06 by 8:00 PM",
            latest_scan="Label created",
            package_count=1,
            signature_required=False,
            dropoff_location_slug=shipment.pickup_location_slug,
        )
        db.session.add(tracking)
        db.session.flush()
        db.session.add_all(
            [
                TrackingEvent(
                    tracking_record_id=tracking.id,
                    sequence=1,
                    event_time="2026-06-04 09:00",
                    location_label=f"{shipment.origin_city}, {shipment.origin_state}",
                    status_label="Label created",
                    details="Shipment information sent to local demo systems.",
                ),
                TrackingEvent(
                    tracking_record_id=tracking.id,
                    sequence=2,
                    event_time="2026-06-04 11:30",
                    location_label=f"{shipment.origin_city}, {shipment.origin_state}",
                    status_label="Picked up",
                    details="Package picked up in the demo handoff flow.",
                ),
            ]
        )
        invoice = Invoice(
            invoice_number=invoice_number,
            user_id=current_user.id,
            shipment_id=shipment.id,
            billed_on="2026-06-04",
            due_date="2026-06-18",
            amount=total_cost,
            status="Open",
        )
        db.session.add(invoice)
        db.session.commit()
        session["shipment_confirmation_code"] = shipment_code
        clear_ship_state()
        session["shipment_confirmation_code"] = shipment_code
        return redirect(url_for("ship_confirmation"))
    return render_template(
        "ship_review.html",
        state=state,
        service=service,
        selected_quote=selected_quote,
    )


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
    selected_slug = request.values.get("location_slug", current_user.preferred_location_slug or locations[0].slug)
    location = Location.query.filter_by(slug=selected_slug).first()
    slots = []
    if location:
        slots = PickupSlot.query.filter_by(location_id=location.id).order_by(PickupSlot.slot_date.asc()).all()
    if request.method == "POST":
        try:
            package_count = int(request.form.get("package_count", "1"))
            if package_count < 1:
                raise ValueError
        except (TypeError, ValueError):
            flash("Enter a package count of at least 1.", "danger")
            return render_template("pickup.html", locations=locations, selected_slug=selected_slug, slots=slots)

        request_id = (db.session.query(db.func.count(PickupRequest.id)).scalar() or 0) + 1
        slot = PickupSlot.query.filter_by(id=int(request.form.get("pickup_slot_id", "0"))).first_or_404()
        pickup_request = PickupRequest(
            confirmation_code=f"PU-{2600 + request_id:04d}",
            user_id=current_user.id,
            location_id=slot.location_id,
            slot_date=slot.slot_date,
            time_window=slot.time_window,
            package_count=package_count,
            status="Scheduled",
            created_on="2026-06-04",
        )
        db.session.add(pickup_request)
        db.session.commit()
        flash(f"Pickup {pickup_request.confirmation_code} scheduled in this local demo.", "success")
        return redirect(url_for("account"))
    return render_template("pickup.html", locations=locations, selected_slug=selected_slug, slots=slots)


@app.route("/locations")
def locations():
    query = request.args.get("q", "").strip()
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
    return render_template("locations.html", locations=locations_list, query=query)


@app.route("/locations/<location_slug>")
def location_detail(location_slug: str):
    location = Location.query.filter_by(slug=location_slug).first_or_404()
    slots = PickupSlot.query.filter_by(location_id=location.id).order_by(PickupSlot.slot_date.asc()).all()
    return render_template("location_detail.html", location=location, slots=slots)


@app.route("/support")
def support():
    query = request.args.get("q", "").strip()
    articles_query = SupportArticle.query
    if query:
        articles_query = support_query(query)
    articles = articles_query.order_by(SupportArticle.category.asc(), SupportArticle.title.asc()).all()
    return render_template("support.html", articles=articles, query=query)


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
    query = request.args.get("q", "").strip()
    articles = []
    locations = []
    tracking_matches = []
    if query:
        db.session.add(SearchLog(query=query, search_type="global", created_on="2026-06-04"))
        db.session.commit()
        token_like = f"%{query}%"
        articles = support_query(query).limit(8).all()
        locations = Location.query.filter(
            or_(Location.city.ilike(token_like), Location.state.ilike(token_like), Location.name.ilike(token_like))
        ).limit(8).all()
        tracking_matches = TrackingRecord.query.filter(
            or_(
                TrackingRecord.tracking_number.ilike(token_like),
                TrackingRecord.recipient_name.ilike(token_like),
                TrackingRecord.status_summary.ilike(token_like),
            )
        ).limit(8).all()
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
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Signed in to the local FedEx demo.", "success")
            return redirect(url_for("account"))
        flash("That demo sign-in did not match any seeded account.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if User.query.filter_by(email=email).first():
            flash("That email already exists in the local demo.", "warning")
            return redirect(url_for("login"))
        next_index = (db.session.query(db.func.count(User.id)).scalar() or 0) + 1
        user = User(
            email=email,
            first_name=request.form.get("first_name", "Demo").strip() or "Demo",
            last_name=request.form.get("last_name", "User").strip() or "User",
            phone=request.form.get("phone", "").strip(),
            company=request.form.get("company", "").strip(),
            city=request.form.get("city", "").strip(),
            state=request.form.get("state", "").strip(),
            zip_code=request.form.get("zip_code", "").strip(),
            account_number=f"5100{next_index:05d}",
            preferred_location_slug=request.form.get("preferred_location_slug", "").strip(),
            invoicing_email=email,
        )
        user.set_password(request.form.get("password", DEMO_PASSWORD))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Created a new local FedEx demo account.", "success")
        return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
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
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name", current_user.first_name).strip()
        current_user.last_name = request.form.get("last_name", current_user.last_name).strip()
        current_user.phone = request.form.get("phone", current_user.phone).strip()
        current_user.company = request.form.get("company", current_user.company).strip()
        current_user.city = request.form.get("city", current_user.city).strip()
        current_user.state = request.form.get("state", current_user.state).strip()
        current_user.zip_code = request.form.get("zip_code", current_user.zip_code).strip()
        current_user.preferred_location_slug = request.form.get(
            "preferred_location_slug", current_user.preferred_location_slug
        ).strip()
        current_user.invoicing_email = request.form.get("invoicing_email", current_user.invoicing_email).strip()
        db.session.commit()
        flash("Saved your local FedEx profile updates.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/account/shipments")
@login_required
def account_shipments():
    shipments = Shipment.query.filter_by(user_id=current_user.id).order_by(Shipment.created_on.desc()).all()
    return render_template("account_shipments.html", shipments=shipments)


@app.post("/account/shipments/<shipment_code>/remove")
@login_required
def account_shipment_remove(shipment_code: str):
    shipment = Shipment.query.filter_by(
        shipment_code=shipment_code,
        user_id=current_user.id,
        reference_label="Local demo shipment",
    ).first_or_404()
    tracking = TrackingRecord.query.filter_by(shipment_id=shipment.id).first()
    Invoice.query.filter_by(shipment_id=shipment.id).delete(synchronize_session=False)
    if tracking:
        TrackingEvent.query.filter_by(tracking_record_id=tracking.id).delete(synchronize_session=False)
        db.session.delete(tracking)
    db.session.delete(shipment)
    db.session.commit()
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
