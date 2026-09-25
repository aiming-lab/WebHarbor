"""MTA (new.mta.info) mirror — Flask application.

Mirrors https://new.mta.info/ as served on 2026-09-23: the service status
board (subway/bus/rail with per-line alert dialogs), planned service changes
browser, elevator & escalator status, real GTFS timetables for the subway,
LIRR and Metro-North, the railroad fare tables (parsed from the official
fare PDFs), station finder, guides/projects/press content, the lost & found
and feedback intake flows, Access-A-Ride booking, OMNY tap history, and the
account domain (register/login, favorites, service-alert subscriptions).

All runtime data lives in instance/mta.db (see seed_data.py); heavy imagery
lives under static/images/ and static/external_cache/ (HF-managed).
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import os
import re
from datetime import datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index, text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
# Tests point the app at a scratch copy of the seed via MTA_DB_PATH so
# stateful checks never touch the live worktree database.
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "MTA_DB_PATH", f"sqlite:///{BASE_DIR}/instance/mta.db")
app.config["SECRET_KEY"] = "webharbor-mta-dev-key"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "account_login"
login_manager.login_message = ""

# The mirror pins "now" to the snapshot date so every relative statement
# ("current status", "this weekend") is deterministic.
MIRROR_NOW = datetime(2026, 9, 23, 19, 0)


# ---------------------------------------------------------------------------
# Asset resolution (see scripts_dev/harvest_assets.py)
# ---------------------------------------------------------------------------
# Content blocks carry the upstream image URLs verbatim (query strings like
# ?itok=... included), while the downloaded files land in static/images/
# under the inventory names (content_<page>__<name>_<hash>.<ext>). This map
# resolves an upstream URL to its inventoried filename so page templates
# never emit a broken <img> src; unresolvable references render nothing.
def _build_asset_url_map():
    mapping = {}
    try:
        with open(os.path.join(BASE_DIR, "asset_inventory.json"),
                  encoding="utf-8") as fh:
            for asset in json.load(fh).get("assets", []):
                source_url = asset.get("source_url") or ""
                local = asset.get("path") or ""
                if source_url and local:
                    mapping[source_url] = local.rsplit("/", 1)[-1]
    except (OSError, ValueError):
        pass
    return mapping


ASSET_URL_MAP = _build_asset_url_map()


def resolve_asset(src):
    """Map an upstream image URL to its static/images filename (or None).

    Applies the same normalizations the harvest used when it downloaded the
    asset: /sites/... and images/... prefixes become absolute new.mta.info /
    ibx.mta.info URLs, and &amp;-escaped query strings are unescaped.
    """
    if not src:
        return None
    s = str(src)
    for variant in (s, _html.unescape(s)):
        if variant.startswith("/sites/"):
            variant = "https://new.mta.info" + variant
        if variant.startswith("images/"):
            variant = "https://ibx.mta.info/" + variant
        variant = variant.replace(
            "https://new.mta.info/project/interborough-express/images/",
            "https://ibx.mta.info/images/")
        for candidate in (variant, _html.unescape(variant)):
            if candidate in ASSET_URL_MAP:
                return ASSET_URL_MAP[candidate]
    return None


app.jinja_env.globals["resolve_asset"] = resolve_asset


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    omny_serial = db.Column(db.String(40), unique=True)

    favorites = db.relationship("Favorite", backref="user", cascade="all, delete-orphan")
    subscriptions = db.relationship("AlertSubscription", backref="user", cascade="all, delete-orphan")
    taps = db.relationship("OmnyTap", backref="user", cascade="all, delete-orphan",
                           order_by="OmnyTap.tapped_at")
    claims = db.relationship("LostClaim", backref="user", cascade="all, delete-orphan")
    cases = db.relationship("FeedbackCase", backref="user", cascade="all, delete-orphan")
    aar_trips = db.relationship("AarTrip", backref="user", cascade="all, delete-orphan")

    def check_password(self, raw: str) -> bool:
        try:
            return bcrypt.check_password_hash(self.password_hash, raw)
        except Exception:  # noqa: BLE001
            return False

    # flask-login protocol
    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    @property
    def omny_week(self):
        """OMNY fare-cap progress for the pinned week (Mon 2026-09-21 .. Sun 2026-09-27)."""
        start = datetime(2026, 9, 21, 4, 0)
        end = start + timedelta(days=7)
        week_taps = [t for t in self.taps if start <= t.tapped_at < end]
        local = [t for t in week_taps if not t.express]
        express = [t for t in week_taps if t.express]
        return {"taps": week_taps, "local": local, "express": express,
                "local_total": sum(t.fare for t in local),
                "express_total": sum(t.fare for t in express),
                "local_cap": 35.0, "express_cap": 67.0}


class Favorite(db.Model):
    __tablename__ = "favorites"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    service_type = db.Column(db.String(20), nullable=False)   # subway | bus | rail
    service_id = db.Column(db.String(80), nullable=False)     # e.g. 2, Q58, Babylon Branch
    created_at = db.Column(db.DateTime, default=MIRROR_NOW)
    __table_args__ = (db.UniqueConstraint("user_id", "service_type", "service_id"),)


class AlertSubscription(db.Model):
    __tablename__ = "alert_subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    service_type = db.Column(db.String(20), nullable=False)
    service_id = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_NOW)
    __table_args__ = (db.UniqueConstraint("user_id", "service_type", "service_id"),)


class OmnyTap(db.Model):
    __tablename__ = "omny_taps"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tapped_at = db.Column(db.DateTime, nullable=False)
    route = db.Column(db.String(20), nullable=False)   # e.g. "Subway 2", "Bus M15"
    fare = db.Column(db.Float, nullable=False)
    express = db.Column(db.Boolean, default=False)
    device = db.Column(db.String(60), default="OMNY Card")


class LostClaim(db.Model):
    __tablename__ = "lost_claims"
    id = db.Column(db.Integer, primary_key=True)
    claim_ref = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    agency = db.Column(db.String(40), nullable=False)   # nyct | lirr | mnr
    date_lost = db.Column(db.String(20), nullable=False)
    line_route = db.Column(db.String(80), nullable=False)
    station = db.Column(db.String(120), nullable=False)
    item_type = db.Column(db.String(40), nullable=False)
    item_description = db.Column(db.String(400), nullable=False)
    contact_name = db.Column(db.String(120), nullable=False)
    contact_email = db.Column(db.String(200), nullable=False)
    contact_phone = db.Column(db.String(40), default="")
    status = db.Column(db.String(30), default="Received")
    created_at = db.Column(db.DateTime, default=MIRROR_NOW)


class FeedbackCase(db.Model):
    __tablename__ = "feedback_cases"
    id = db.Column(db.Integer, primary_key=True)
    case_ref = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    category = db.Column(db.String(40), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="Open")
    created_at = db.Column(db.DateTime, default=MIRROR_NOW)


class AarTrip(db.Model):
    __tablename__ = "aar_trips"
    id = db.Column(db.Integer, primary_key=True)
    trip_ref = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    pickup_address = db.Column(db.String(200), nullable=False)
    destination_address = db.Column(db.String(200), nullable=False)
    trip_date = db.Column(db.String(20), nullable=False)
    pickup_time = db.Column(db.String(10), nullable=False)
    passengers = db.Column(db.Integer, default=1)
    mobility_aid = db.Column(db.String(60), default="")
    purpose = db.Column(db.String(60), default="")
    status = db.Column(db.String(30), default="Scheduled")
    created_at = db.Column(db.DateTime, default=MIRROR_NOW)


# --- transit reference data -------------------------------------------------

class SubwayRoute(db.Model):
    __tablename__ = "subway_routes"
    id = db.Column(db.String(10), primary_key=True)      # 1..7, A..SI, GS/FS/H
    name = db.Column(db.String(120), nullable=False)
    desc = db.Column(db.Text, default="")
    color = db.Column(db.String(10), default="#000000")
    text_color = db.Column(db.String(10), default="#FFFFFF")
    slug = db.Column(db.String(40), nullable=False)


class Station(db.Model):
    __tablename__ = "stations"
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    agency = db.Column(db.String(10), nullable=False)     # subway | lirr | mnr
    gtfs_stop_id = db.Column(db.String(20), default="")
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    borough = db.Column(db.String(30), default="")
    wheelchair = db.Column(db.Boolean, default=False)
    access_note = db.Column(db.Text, default="")          # partial-accessibility note
    lines = db.Column(db.Text, default="[]")               # JSON list for subway
    zone = db.Column(db.String(10))                        # LIRR / MNR fare zone
    url_slug = db.Column(db.String(200), default="")


class Transfer(db.Model):
    __tablename__ = "transfers"
    id = db.Column(db.Integer, primary_key=True)
    from_station = db.Column(db.String(20), nullable=False)
    to_station = db.Column(db.String(20), nullable=False)


class ServiceAlert(db.Model):
    __tablename__ = "service_alerts"
    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.String(60), unique=True, nullable=False)
    alert_type = db.Column(db.String(60), nullable=False)
    mode = db.Column(db.String(10), nullable=False)       # subway | bus | lirr | mnr
    routes = db.Column(db.Text, default="[]")              # JSON [{agency, route_id}]
    stops = db.Column(db.Text, default="[]")
    start_ts = db.Column(db.Integer)
    end_ts = db.Column(db.Integer)
    header_html = db.Column(db.Text, default="")
    desc_html = db.Column(db.Text, default="")
    header_text = db.Column(db.Text, default="")
    desc_text = db.Column(db.Text, default="")
    created_ts = db.Column(db.Integer)
    updated_ts = db.Column(db.Integer)
    planned = db.Column(db.Boolean, default=False)


class Equipment(db.Model):
    __tablename__ = "equipment"
    id = db.Column(db.Integer, primary_key=True)
    equipmentno = db.Column(db.String(20), nullable=False)
    station = db.Column(db.String(120), nullable=False)
    trainno = db.Column(db.String(40), default="")
    equipmenttype = db.Column(db.String(4), default="EL")  # EL | ES
    serving = db.Column(db.String(200), default="")
    ada = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    short_desc = db.Column(db.String(200), default="")
    lines = db.Column(db.String(60), default="")
    gtfs_stop_id = db.Column(db.String(20), default="")
    alternative_route = db.Column(db.Text, default="")


class Outage(db.Model):
    __tablename__ = "outages"
    id = db.Column(db.Integer, primary_key=True)
    equipmentno = db.Column(db.String(20), nullable=False)
    station = db.Column(db.String(120), nullable=False)
    trainno = db.Column(db.String(40), default="")
    equipmenttype = db.Column(db.String(4), default="EL")
    serving = db.Column(db.String(240), default="")
    ada = db.Column(db.Boolean, default=False)
    outage_date = db.Column(db.String(30), default="")
    estimated_return = db.Column(db.String(30), default="")
    reason = db.Column(db.String(80), default="")
    is_active = db.Column(db.Boolean, default=True)
    is_upcoming = db.Column(db.Boolean, default=False)


class RailFare(db.Model):
    """LIRR zone-pair price matrix (from the official fare chart PDF)."""
    __tablename__ = "rail_fares"
    id = db.Column(db.Integer, primary_key=True)
    origin_zone = db.Column(db.String(10), nullable=False)
    dest_zone = db.Column(db.String(10), nullable=False)
    ticket_type = db.Column(db.String(60), nullable=False)
    price = db.Column(db.Float, nullable=False)


class MnrFare(db.Model):
    """Metro-North zone fares to Grand Central (Harlem/Hudson + New Haven)."""
    __tablename__ = "mnr_fares"
    id = db.Column(db.Integer, primary_key=True)
    line = db.Column(db.String(40), nullable=False)       # harlem_hudson | new_haven
    zone = db.Column(db.String(10), nullable=False)
    ticket_type = db.Column(db.String(60), nullable=False)
    price = db.Column(db.Float)
    price_peak = db.Column(db.Float)
    price_offpeak = db.Column(db.Float)


class PortJervisFare(db.Model):
    __tablename__ = "port_jervis_fares"
    id = db.Column(db.Integer, primary_key=True)
    station = db.Column(db.String(80), nullable=False)
    ticket_type = db.Column(db.String(60), nullable=False)
    price_hoboken = db.Column(db.Float)
    price_penn = db.Column(db.Float)


class ContentPage(db.Model):
    __tablename__ = "content_pages"
    path = db.Column(db.String(120), primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    label = db.Column(db.String(120), default="")
    hero = db.Column(db.String(400), default="")
    updated = db.Column(db.String(40), default="")
    blocks = db.Column(db.Text, nullable=False)            # JSON block list


class Project(db.Model):
    __tablename__ = "projects"
    slug = db.Column(db.String(80), primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    blocks = db.Column(db.Text, nullable=False)


class PressRelease(db.Model):
    __tablename__ = "press_releases"
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    date = db.Column(db.String(60), default="")
    blocks = db.Column(db.Text, nullable=False)


class Trip(db.Model):
    __tablename__ = "trips"
    id = db.Column(db.Integer, primary_key=True)
    gtfs_trip_id = db.Column(db.String(80), unique=True, nullable=False)
    agency = db.Column(db.String(10), nullable=False)
    route_id = db.Column(db.String(10), nullable=False)
    headsign = db.Column(db.String(120), default="")
    direction_id = db.Column(db.Integer, default=0)
    day_type = db.Column(db.String(10), nullable=False)   # weekday | saturday | sunday
    peak = db.Column(db.Boolean, default=False)


class StopTime(db.Model):
    __tablename__ = "stop_times"
    id = db.Column(db.Integer, primary_key=True)
    trip_pk = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    stop_id = db.Column(db.String(20), nullable=False)
    stop_sequence = db.Column(db.Integer, nullable=False)
    arrival = db.Column(db.Integer, nullable=False)
    departure = db.Column(db.Integer, nullable=False)


# NOTE: the two stop_times indexes are deliberately NOT declared here.
# SQLAlchemy keeps table.indexes in a set, so create_all() would emit them in
# per-process (memory-address) order and the sqlite_master rows — and with
# them the physical file layout — would differ between otherwise identical
# builds. seed_data.py creates both in a fixed order after the bulk load
# (CREATE INDEX IF NOT EXISTS ix_stop_times_stop_departure, then
# ix_stop_times_trip), which keeps the seed byte-reproducible.
Index("ix_trips_route_day", Trip.agency, Trip.route_id, Trip.day_type, Trip.direction_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(raw: str, default=None):
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return default if default is not None else []


SUBWAY_LINE_ORDER = ["1", "2", "3", "4", "5", "6", "7", "A", "C", "E", "B",
                     "D", "F", "M", "G", "J", "Z", "L", "N", "Q", "R", "W",
                     "GS", "FS", "H", "SI"]

RAIL_BRANCHES = {
    "lirr": ["Babylon Branch", "City Terminal Zone", "Far Rockaway Branch",
             "Hempstead Branch", "Long Beach Branch", "Montauk Branch",
             "Oyster Bay Branch", "Port Jefferson Branch", "Port Washington Branch",
             "Ronkonkoma Branch", "West Hempstead Branch", "Greenport Service"],
    "mnr": ["Harlem", "Wassaic", "Hudson", "New Haven", "Danbury", "New Canaan",
            "Waterbury", "Pascack Valley", "Port Jervis"],
}


def _line_sort_key(line: str):
    try:
        return (0, int(line))
    except ValueError:
        return (1, line)


def active_alerts(mode: str, route_id: str | None = None):
    """Alerts active at the pinned reference time for a mode (and route)."""
    ref = int(MIRROR_NOW.timestamp())
    q = ServiceAlert.query.filter(ServiceAlert.mode == mode)
    if route_id:
        q = q.filter(ServiceAlert.routes.contains(f'"route_id": "{route_id}"'))
    out = []
    for a in q.all():
        if a.start_ts and a.start_ts > ref:
            continue
        if a.end_ts and a.end_ts < ref:
            continue
        out.append(a)
    return out


def group_status(alerts):
    """Group alert type names into the status-board buckets the live site uses.

    Accepts either ServiceAlert rows or (type, None) tuples.
    """
    groups: dict[str, list] = {}
    for a in alerts:
        atype = a.alert_type if hasattr(a, "alert_type") else a[0]
        groups.setdefault(atype, []).append(a)
    order = ["Suspended", "Part Suspended", "Delays", "Expect Delays", "Some Delays",
             "Station Notice", "Boarding Change", "Reduced Service", "Cancellations",
             "Special Schedule", "Special Notice", "Extra Service",
             "Planned - Suspended", "Planned - Part Suspended", "Planned - Reroute",
             "Planned - Detour", "Planned - Stops Skipped", "Planned - Express to Local",
             "Planned - Substitute Buses", "Detour"]
    def key(item):
        atype, _ = item
        return (order.index(atype) if atype in order else len(order), atype)
    return sorted(groups.items(), key=key)


def next_ref(prefix: str) -> str:
    """Deterministic, collision-free reference number for claims/cases/trips.

    The daily base is fixed (so a verifier can predict the first reference
    issued on the pinned day) and the per-prefix row count keeps successive
    submissions distinct even when several are filed in one session.
    """
    base = int(hashlib.sha256(f"{prefix}-{MIRROR_NOW:%Y%m%d}".encode()).hexdigest()[:6], 16) % 9000 + 1000
    model = {"LF": LostClaim, "CS": FeedbackCase, "AAR": AarTrip}[prefix]
    issued = db.session.query(model).count()
    return f"{prefix}-{MIRROR_NOW:%y%m}{base + issued}"


def image_for(url_or_path: str) -> str:
    """Map a captured upstream image URL to the local static path."""
    if not url_or_path:
        return ""
    if url_or_path.startswith("/static/"):
        return url_or_path
    return "/static/images/" + url_or_path.rsplit("/", 1)[-1]


def fmt_time(seconds: int) -> str:
    seconds = int(seconds) % 86400
    h, m = seconds // 3600, (seconds % 3600) // 60
    suffix = "a.m." if 0 <= h < 12 else ("p.m." if 12 <= h < 24 else "a.m.")
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def fmt_time_short(seconds: int) -> str:
    seconds = int(seconds) % 86400
    h, m = seconds // 3600, (seconds % 3600) // 60
    return f"{h:02d}:{m:02d}"


SUBWAY_SLUGS = {
    "1": "1-train", "2": "2-train", "3": "3-train", "4": "4-train", "5": "5-train",
    "6": "6-train", "7": "7-train", "A": "a-train", "C": "c-train", "E": "e-train",
    "B": "b-train", "D": "d-train", "F": "f-train", "M": "m-train", "G": "g-train",
    "J": "j-train", "L": "l-train", "N": "n-train", "Q": "q-train", "R": "r-train",
    "W": "w-train", "GS": "42-st-shuttle", "FS": "franklin-avenue-shuttle",
    "H": "rockaway-park-shuttle", "SI": "staten-island-railway",
}

app.jinja_env.filters["fmttime"] = fmt_time
app.jinja_env.filters["fmttimeshort"] = fmt_time_short
app.jinja_env.globals["MIRROR_NOW"] = MIRROR_NOW
app.jinja_env.globals["SUBWAY_SLUGS"] = SUBWAY_SLUGS

import json as _json


@app.template_filter("fromjson")
def _fromjson(value):
    try:
        return _json.loads(value)
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# Context shared by all templates
# ---------------------------------------------------------------------------

@app.context_processor
def base_context():
    return {
        "nav_sections": [
            ("Schedules", url_for("schedules_hub")),
            ("Maps", url_for("maps_page")),
            ("Fares and tolls", url_for("fares_hub")),
            ("Planned Service Changes", url_for("planned_changes")),
            ("Elevator & Escalator Status", url_for("elevator_status")),
            ("Accessibility", url_for("accessibility_page")),
            ("Guides", url_for("guides_index")),
            ("Access-A-Ride Paratransit", url_for("aar_page")),
            ("About the MTA", url_for("about_page")),
            ("Transparency", url_for("transparency_page")),
            ("Projects", url_for("projects_index")),
            ("Safety and Security", url_for("safety_page")),
            ("Careers", url_for("careers_page")),
        ],
        "nav_agencies": [
            ("New York City Transit", url_for("agency_page", slug="new-york-city-transit")),
            ("Bridges & Tunnels", url_for("agency_page", slug="bridges-and-tunnels")),
            ("Long Island Rail Road", url_for("agency_page", slug="long-island-rail-road")),
            ("Metro-North Railroad", url_for("agency_page", slug="metro-north-railroad")),
            ("Other agencies and departments", url_for("agency_index")),
        ],
        "nav_contact": [
            ("Give feedback", url_for("feedback_form")),
            ("Contact the MTA", url_for("contact_page")),
            ("Media Relations", url_for("content_page", path="agency/media-relations")),
            ("Procurement and solicitations", url_for("content_page", path="doing-business-with-us/procurement")),
        ],
    }


# ---------------------------------------------------------------------------
# Home + service status
# ---------------------------------------------------------------------------

def subway_status_board():
    alerts = active_alerts("subway")
    by_line: dict[str, list[ServiceAlert]] = {}
    for a in alerts:
        for r in load_json(a.routes):
            rid = r.get("route_id", "")
            if r.get("agency") == "MTASBWY" or r.get("agency") == "MTA NYCT":
                by_line.setdefault(rid, []).append(a)
    # status per line: pick the highest-severity alert type
    severity = ["Suspended", "Part Suspended", "Planned - Suspended", "Planned - Part Suspended",
                "Delays", "Some Delays", "Expect Delays", "Planned - Reroute", "Planned - Detour",
                "Planned - Stops Skipped", "Planned - Express to Local", "Planned - Substitute Buses",
                "Boarding Change", "Station Notice", "Reduced Service", "Detour",
                "Special Schedule", "Extra Service", "Special Notice", "Cancellations"]
    line_status = {}
    for line, alist in by_line.items():
        best = min((severity.index(a.alert_type) if a.alert_type in severity else 99, a.alert_type)
                   for a in alist)
        line_status[line] = {"status": best[1], "alerts": alist}
    groups: dict[str, list[str]] = {}
    for line, info in line_status.items():
        groups.setdefault(info["status"], []).append(line)
    out = []
    for status, lines in group_status([(k, None) for k in groups]):
        out.append((status, sorted(groups[status], key=_line_sort_key)))
    good = [l for l in SUBWAY_LINE_ORDER if l not in line_status]
    if good:
        out.append(("No Active Alerts", good))
    return out, line_status


def rail_status_board():
    alerts = active_alerts("rail")
    by_branch: dict[str, list[ServiceAlert]] = {}
    for a in alerts:
        for r in load_json(a.routes):
            if r.get("agency") in ("LI", "MNR"):
                by_branch.setdefault(r.get("route_id", ""), []).append(a)
    branch_status = {}
    for branch, alist in by_branch.items():
        best = min((a.alert_type, 0) for a in alist)
        branch_status[branch] = {"status": best[0], "alerts": alist}
    seen = set()
    out = []
    for status, _ in group_status([(b["status"], None) for b in branch_status.values()]):
        if status in seen:
            continue
        seen.add(status)
        branches = sorted(b for b, v in branch_status.items() if v["status"] == status)
        out.append((status, branches))
    good = [b for b in RAIL_BRANCHES["lirr"] + RAIL_BRANCHES["mnr"] if b not in branch_status]
    if good:
        out.append(("On or Close", good))
    return out, branch_status


@app.route("/")
def home():
    subway_groups, line_status = subway_status_board()
    rail_groups, branch_status = rail_status_board()
    press = PressRelease.query.order_by(PressRelease.id.desc()).limit(3).all()
    featured = [("interborough-express", "Interborough Express"),
                ("penn-station-access", "Penn Station Access"),
                ("station-accessibility-upgrades", "Station accessibility projects")]
    guide_cards = [("bikes", "Taking your bike on public transit"),
                   ("airports", "Getting to New York-area airports on public transit"),
                   ("stadiums", "Getting to NYC-area stadiums and arenas on transit"),
                   ("service-alerts", "Sign up for service alerts")]
    fav_lines = []
    if current_user.is_authenticated:
        for f in current_user.favorites:
            fav_lines.append(f)
    return render_template("home.html", subway_groups=subway_groups,
                           line_status=line_status, rail_groups=rail_groups,
                           branch_status=branch_status, press=press,
                           featured=featured, guide_cards=guide_cards,
                           fav_lines=fav_lines)


@app.route("/alerts/line/<line>")
def line_alerts(line):
    """Per-line service alert dialog content (the live site opens a modal)."""
    line = line.upper()
    alerts = []
    for a in active_alerts("subway", route_id=line):
        alerts.append(a)
    if not alerts:
        alerts = ServiceAlert.query.filter(
            ServiceAlert.mode == "subway",
            ServiceAlert.routes.contains(f'"route_id": "{line}"')).all()
    route = SubwayRoute.query.get(line)
    stations = Station.query.filter(Station.agency == "subway",
                                    Station.lines.contains(f'"{line}"')).order_by(Station.id).all()
    fav = None
    if current_user.is_authenticated:
        fav = Favorite.query.filter_by(user_id=current_user.id, service_type="subway",
                                       service_id=line).first()
    return render_template("line_alerts.html", line=line, route=route,
                           alerts=alerts, stations=stations, fav=fav,
                           line_status={line: {"status": ""}})


@app.route("/alerts/branch/<branch>")
def branch_alerts(branch):
    """Per-branch rail alert page (LIRR / Metro-North)."""
    pretty = branch.replace("-", " ")
    for name in RAIL_BRANCHES["lirr"] + RAIL_BRANCHES["mnr"]:
        if name.lower().replace(" ", "-") == branch:
            pretty = name
            break
    mode = "lirr" if pretty in RAIL_BRANCHES["lirr"] else "mnr"
    alerts = [a for a in active_alerts(mode)
              if any(r.get("route_id") == pretty for r in load_json(a.routes))]
    if not alerts:
        alerts = [a for a in ServiceAlert.query.filter_by(mode=mode).all()
                  if any(r.get("route_id") == pretty for r in load_json(a.routes))]
    fav = None
    if current_user.is_authenticated:
        fav = Favorite.query.filter_by(user_id=current_user.id, service_type="rail",
                                       service_id=pretty).first()
    return render_template("line_alerts.html", line=pretty, branch=pretty,
                           route=None, alerts=alerts, stations=[], fav=fav,
                           line_status={})


@app.route("/alerts")
def planned_work():
    """The 'Planned Work' page: planned service changes, grouped by mode."""
    ref = int(MIRROR_NOW.timestamp())
    planned = ServiceAlert.query.filter_by(planned=True).order_by(ServiceAlert.start_ts).all()
    modes = {"subway": [], "bus": [], "lirr": [], "mnr": []}
    for a in planned:
        modes.setdefault(a.mode, []).append(a)
    return render_template("planned_work.html", modes=modes, ref=ref)


@app.route("/planned-service-changes")
def planned_changes():
    """Filterable planned service changes browser."""
    mode = request.args.get("mode", "subway")
    when = request.args.get("when", "now")
    route = request.args.get("route", "")
    ref = int(MIRROR_NOW.timestamp())

    windows = {
        "now": (ref - 3600, ref + 3600),
        "tonight": (int(datetime(2026, 9, 23, 17, 0).timestamp()),
                    int(datetime(2026, 9, 24, 2, 0).timestamp())),
        "tomorrow": (int(datetime(2026, 9, 24, 2, 0).timestamp()),
                     int(datetime(2026, 9, 24, 17, 0).timestamp())),
        "weekend": (int(datetime(2026, 9, 25, 17, 0).timestamp()),
                    int(datetime(2026, 9, 28, 2, 0).timestamp())),
    }
    lo, hi = windows.get(when, windows["now"])

    q = ServiceAlert.query.filter_by(planned=True)
    if mode == "subway":
        q = q.filter(ServiceAlert.routes.contains("MTASBWY"))
    elif mode == "bus":
        q = q.filter((ServiceAlert.routes.contains("MTABC")) |
                     (ServiceAlert.routes.contains("MTA NYCT")))
    elif mode == "lirr":
        q = q.filter(ServiceAlert.routes.contains('"agency": "LI"'))
    elif mode == "mnr":
        q = q.filter(ServiceAlert.routes.contains('"agency": "MNR"'))
    results = [a for a in q.all()
               if (a.start_ts is None or a.start_ts <= hi) and
                  (a.end_ts is None or a.end_ts >= lo)]
    if route:
        results = [a for a in results
                   if any(r.get("route_id") == route for r in load_json(a.routes))]
    results.sort(key=lambda a: (a.start_ts or 0))
    return render_template("planned_changes.html", mode=mode, when=when,
                           route=route, results=results, ref=ref)


# ---------------------------------------------------------------------------
# Elevator & escalator status
# ---------------------------------------------------------------------------

@app.route("/elevator-escalator-status")
def elevator_status():
    show = request.args.get("show", "elevators")     # elevators | escalators | all
    station_q = request.args.get("station", "").strip()
    ada_only = request.args.get("ada") == "1"
    upcoming = request.args.get("upcoming") == "1"

    q = Outage.query
    if show == "elevators":
        q = q.filter(Outage.equipmenttype == "EL")
    elif show == "escalators":
        q = q.filter(Outage.equipmenttype == "ES")
    if station_q:
        q = q.filter(Outage.station.contains(station_q))
    if ada_only:
        q = q.filter(Outage.ada.is_(True))
    q = q.filter(Outage.is_upcoming.is_(upcoming))
    outages = q.order_by(Outage.station).all()

    # alternative-route guidance from the equipment registry, shown with the
    # outage row the way the upstream status page expands an outage entry
    alt = {e.equipmentno: e.alternative_route for e in Equipment.query.all()
           if e.alternative_route}

    stations = sorted({o.station for o in Outage.query.filter(Outage.is_upcoming.is_(False)).all()})
    return render_template("elevator_status.html", outages=outages, show=show,
                           station_q=station_q, ada_only=ada_only, upcoming=upcoming,
                           stations=stations, alt=alt)


@app.route("/elevator-escalator-status/api")
def elevator_api():
    outages = Outage.query.filter(Outage.is_upcoming.is_(False)).all()
    return jsonify([{
        "station": o.station, "equipment": o.equipmentno, "type": o.equipmenttype,
        "serving": o.serving, "ada": o.ada, "outage_date": o.outage_date,
        "estimated_return": o.estimated_return, "reason": o.reason,
    } for o in outages])


# ---------------------------------------------------------------------------
# Schedules + timetables (real GTFS data)
# ---------------------------------------------------------------------------

RAIL_ROUTE_IDS = {
    "lirr": {"Babylon Branch": "1", "Hempstead Branch": "2", "Oyster Bay Branch": "3",
             "Ronkonkoma Branch": "4", "Montauk Branch": "5", "Long Beach Branch": "6",
             "Far Rockaway Branch": "7", "West Hempstead Branch": "8",
             "Port Washington Branch": "9", "Port Jefferson Branch": "10",
             "City Terminal Zone": "12", "Greenport Service": "13",
             "Belmont Park": "11"},
    "mnr": {"Hudson": "1", "Harlem": "2", "New Haven": "3", "New Canaan": "4",
            "Danbury": "5", "Waterbury": "6"},
}

# Upstream timetable URLs for the City Terminal Zone split Manhattan and
# Brooklyn service into two pages; both map onto the same LIRR route id.
LIRR_CITY_ZONE_ALIASES = {
    "city-zone-manhattan": ("City Terminal Zone", "Manhattan"),
    "city-zone-brooklyn": ("City Terminal Zone", "Brooklyn"),
}


def gtfs_to_seconds(t: str) -> int:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


@app.route("/schedules")
def schedules_hub():
    routes = SubwayRoute.query.order_by(SubwayRoute.id).all()
    ordered = sorted(routes, key=lambda r: _line_sort_key(r.id))
    return render_template("schedules.html", routes=ordered)


def _timetable_page(agency, route_id, label, day, direction, page_title,
                    pdf_name, pdf_url, extra=None):
    day = day if day in ("weekday", "saturday", "sunday") else "weekday"
    trips = (Trip.query.filter_by(agency=agency, route_id=route_id, day_type=day)
             .order_by(Trip.gtfs_trip_id).all())
    directions = sorted({t.direction_id for t in
                         Trip.query.filter_by(agency=agency, route_id=route_id).all()})
    if direction not in directions:
        direction = directions[0] if directions else 0
    trips = [t for t in trips if t.direction_id == direction]

    # build the station axis from the first trip, then a time matrix
    rows = {}
    station_order = []
    for t in trips[:1]:
        sts = StopTime.query.filter_by(trip_pk=t.id).order_by(StopTime.stop_sequence).all()
        for st in sts:
            rows[st.stop_id] = {}
            station_order.append(st.stop_id)
    for t in trips:
        sts = StopTime.query.filter_by(trip_pk=t.id).order_by(StopTime.stop_sequence).all()
        if not sts:
            continue
        first, last = sts[0], sts[-1]
        if first.arrival == last.arrival and len(sts) == 1:
            continue
        for st in sts:
            rows.setdefault(st.stop_id, {})[t.id] = st.departure
    station_names = {}
    for sid in rows:
        s = Station.query.filter_by(agency=agency, gtfs_stop_id=sid).first()
        if s is None and agency == "subway":
            s = Station.query.get(sid[:-1] if sid[-1] in "NS" else sid)
        if s is not None:
            station_names[sid] = s.name
        else:
            station_names[sid] = sid
    ordered_rows = [(station_names.get(sid, sid), rows[sid], sid) for sid in station_order if sid in rows]
    return render_template("timetable.html", day=day, direction=direction,
                           directions=directions, trips=trips, rows=ordered_rows,
                           page_title=page_title, label=label,
                           pdf_name=pdf_name, pdf_url=pdf_url,
                           agency=agency, route_id=route_id,
                           extra=extra or {})


@app.route("/schedules/subway/<line>")
def subway_schedule(line):
    raw = line
    line = line.upper()
    # accept both the line id (1, A, GS) and the site's slug forms (1-train,
    # 42-st-shuttle, staten-island-railway)
    if line.endswith("-TRAIN"):
        line = line[:-6]
    if line not in SUBWAY_LINE_ORDER:
        for lid, slug in SUBWAY_SLUGS.items():
            if slug.upper() == raw.upper():
                line = lid
                break
    route = SubwayRoute.query.get(line)
    if route is None:
        abort(404)
    day = request.args.get("day", "weekday")
    direction = request.args.get("direction", "0", type=int)
    # the cached PDF files are keyed by the harvest names (subway_1.pdf,
    # subway_42_st_shuttle.pdf, ...), not the site slugs
    pdf_key = {"GS": "42_st_shuttle", "FS": "franklin_av_shuttle",
               "H": "rockaway_park_shuttle", "SI": "sir"}.get(line, line)
    pdf_name = f"subway_{pdf_key}.pdf"
    stations = (Station.query.filter(Station.agency == "subway",
                                     Station.lines.contains(f'"{line}"'))
                .order_by(Station.id).all())
    return _timetable_page("subway", line, f"{line} train",
                           day, direction, f"{line} train schedule",
                           pdf_name, url_for("timetable_pdf", name=pdf_name.removesuffix(".pdf")),
                           extra={"route": route, "stations": stations})


@app.route("/schedules/lirr/<branch>")
def lirr_schedule(branch):
    route_id = None
    city_zone = LIRR_CITY_ZONE_ALIASES.get(branch)
    probe = branch.replace(" ", "-").lower()
    for name, rid in RAIL_ROUTE_IDS["lirr"].items():
        slug = name.lower().replace(" ", "-")
        # upstream links use the short form ('babylon'); the full form with
        # the 'branch' suffix ('babylon-branch') is accepted as well.
        short = slug.removesuffix("-branch")
        if probe in (slug, short):
            route_id = rid
            branch = name
            break
    if route_id is None and city_zone:
        route_id = RAIL_ROUTE_IDS["lirr"][city_zone[0]]
        branch = city_zone[0]
    if route_id is None:
        abort(404)
    day = request.args.get("day", "weekday")
    direction = request.args.get("direction", "0", type=int)
    pdf_slug = branch.lower().replace(" ", "-")
    pdf_name = f"lirr_{pdf_slug}.pdf" if f"lirr_{pdf_slug}" in [
        "lirr_babylon", "lirr_far_rockaway", "lirr_hempstead", "lirr_long_beach",
        "lirr_montauk", "lirr_oyster_bay", "lirr_port_jefferson", "lirr_port_washington",
        "lirr_ronkonkoma", "lirr_west_hempstead", "lirr_city_zone_manhattan",
        "lirr_city_zone_brooklyn"] else None
    return _timetable_page("lirr", route_id, branch, day, direction,
                           f"{branch} schedule",
                           pdf_name, url_for("timetable_pdf", name=pdf_name.removesuffix(".pdf")) if pdf_name else None,
                           extra={"rail": "lirr", "branch": branch})


@app.route("/schedules/metro-north/<line>")
def mnr_schedule(line):
    pretty = line.replace("-", " ").title()
    route_id = None
    for name, rid in RAIL_ROUTE_IDS["mnr"].items():
        if name.lower().replace(" ", "-") == line:
            route_id = rid
            pretty = name
            break
    if route_id is None:
        abort(404)
    day = request.args.get("day", "weekday")
    direction = request.args.get("direction", "0", type=int)
    pdf_name = f"mnr_{line.replace('-', '_')}.pdf"
    return _timetable_page("mnr", route_id, pretty, day, direction,
                           f"{pretty} Line schedule", pdf_name,
                           url_for("timetable_pdf", name=pdf_name.removesuffix(".pdf")),
                           extra={"rail": "mnr", "branch": pretty})


@app.route("/schedules/metro-north/port-jervis")
@app.route("/schedules/metro-north/pascack-valley")
def mnr_west_of_hudson(line=None):
    line = line or request.path.rsplit("/", 1)[-1]
    if line == "port-jervis":
        stations = [s for s in ["Sloatsburg", "Tuxedo", "Harriman", "Salisbury Mills",
                                "Campbell Hall", "Middletown", "Otisville", "Port Jervis"]]
        fares = PortJervisFare.query.filter_by(station="Port Jervis").all()
    else:
        stations = ["Pearl River", "Nanuet", "Spring Valley"]
        fares = PortJervisFare.query.filter_by(station="Pearl River").all()
    all_fares = {}
    for s in stations:
        all_fares[s] = {f.ticket_type: (f.price_hoboken, f.price_penn)
                        for f in PortJervisFare.query.filter_by(station=s).all()}
    pdf_name = f"mnr_{line.replace('-', '_')}.pdf"
    return render_template("west_of_hudson.html", line=line,
                           stations=stations, fares=all_fares,
                           pdf_name=pdf_name,
                           pdf_url=url_for("timetable_pdf", name=pdf_name.removesuffix(".pdf")))


@app.route("/schedules/bus/<borough>")
def bus_schedule(borough):
    known = {"bronx": "Bronx", "Brooklyn": "Brooklyn", "manhattan": "Manhattan",
             "queens": "Queens", "si": "Staten Island"}
    pretty = known.get(borough, borough.title())
    page = ContentPage.query.get(f"/schedules/bus/{borough}")
    return render_template("bus_schedule.html", page=page, borough=pretty,
                           borough_slug=borough)


@app.route("/timetable/<name>.pdf")
def timetable_pdf(name):
    path = os.path.join(BASE_DIR, "static", "external_cache", "timetables", name + ".pdf")
    if not os.path.exists(path):
        abort(404)
    from flask import send_file
    return send_file(path, mimetype="application/pdf", as_attachment=False,
                     download_name=name + ".pdf")


@app.route("/map/<map_id>")
def map_pdf(map_id):
    """Printable map PDFs (the maps page links to /map/<id> downloads)."""
    if not re.fullmatch(r"[0-9]+", map_id):
        abort(404)
    path = os.path.join(BASE_DIR, "static", "external_cache", "maps", f"map_{map_id}.pdf")
    if not os.path.exists(path):
        abort(404)
    from flask import send_file
    return send_file(path, mimetype="application/pdf", as_attachment=False,
                     download_name=f"mta-map-{map_id}.pdf")


@app.route("/document/<doc_id>")
def document_pdf(doc_id):
    """Official MTA document downloads (budget books, plans, bond resolutions,
    reports) cached from new.mta.info /document/ endpoints."""
    if not re.fullmatch(r"[0-9]+", doc_id):
        abort(404)
    path = os.path.join(BASE_DIR, "static", "external_cache", "documents",
                        f"document_{doc_id}.pdf")
    if not os.path.exists(path):
        abort(404)
    from flask import send_file
    return send_file(path, mimetype="application/pdf", as_attachment=False,
                     download_name=f"mta-document-{doc_id}.pdf")


def next_departures(agency: str, route_id: str, stop_id: str, day: str,
                    after_seconds: int, limit: int = 6):
    """Next departures for a stop on a route (pinned 'now' by default)."""
    trips = (Trip.query.filter_by(agency=agency, route_id=route_id, day_type=day).all())
    pks = [t.id for t in trips]
    if not pks:
        return []
    sts = (StopTime.query.filter(StopTime.stop_id == stop_id,
                                 StopTime.trip_pk.in_(pks),
                                 StopTime.departure >= after_seconds)
           .order_by(StopTime.departure).limit(limit * 3).all())
    out = []
    for st in sts[:limit]:
        t = Trip.query.get(st.trip_pk)
        out.append({"time": st.departure, "headsign": t.headsign, "trip": t})
    return out


@app.route("/station/<sid>")
def station_page(sid):
    s = Station.query.get(sid)
    if s is None and sid[-1] in "NS":
        s = Station.query.get(sid[:-1])
    if s is None:
        s = Station.query.filter_by(agency="lirr", gtfs_stop_id=sid).first()
    if s is None:
        s = Station.query.filter_by(agency="mnr", gtfs_stop_id=sid).first()
    if s is None:
        abort(404)
    # equipment rows carry composite gtfs ids when a single elevator or
    # escalator serves a multi-platform station complex (e.g. 'L03/R20' at
    # 14 St-Union Sq), so match the station id on either side of the slash
    elevators = Equipment.query.filter(
        (Equipment.gtfs_stop_id == s.id) |
        (Equipment.gtfs_stop_id.endswith("/" + s.id)) |
        (Equipment.gtfs_stop_id.startswith(s.id + "/"))).all()
    outages = Outage.query.filter(Outage.station == s.name).all() if s.agency == "subway" else []
    alerts = []
    if s.agency == "subway":
        for line in load_json(s.lines):
            for a in active_alerts("subway", route_id=line):
                if a not in alerts:
                    alerts.append(a)
    transfers = []
    if s.agency == "subway":
        for t in Transfer.query.filter((Transfer.from_station == s.id) |
                                       (Transfer.to_station == s.id)).all():
            other = t.to_station if t.from_station == s.id else t.from_station
            o = Station.query.get(other)
            if o:
                transfers.append(o)
    return render_template("station.html", station=s, elevators=elevators,
                           outages=outages, alerts=alerts, transfers=transfers)


@app.route("/nearby")
def nearby():
    q = request.args.get("q", "").strip()
    borough = request.args.get("borough", "")
    line = request.args.get("line", "")
    subway = Station.query.filter_by(agency="subway")
    if q:
        subway = subway.filter(Station.name.contains(q))
    if borough:
        subway = subway.filter_by(borough=borough)
    if line:
        subway = subway.filter(Station.lines.contains(f'"{line}"'))
    stations = subway.order_by(Station.name).limit(80).all()
    boroughs = ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"]
    return render_template("nearby.html", stations=stations, q=q,
                           borough=borough, line=line, boroughs=boroughs)


# ---------------------------------------------------------------------------
# Fares & tolls
# ---------------------------------------------------------------------------

FARE_PAGES = {
    "": "Fares and tolls",
    "subway-bus": "Subway and bus fares",
    "subway-bus/reduced-fare": "Reduced fares",
    "subway-bus/tap-and-ride": "Tap and ride to pay your fare",
    "lirr-metro-north": "LIRR and Metro-North fares",
    "tolls": "Bridges and Tunnels tolls",
    "tolls/congestion-relief-zone": "Congestion Relief Zone tolling information",
    "how-to-save-money": "How to save money on fares",
    "pre-tax-benefits": "Pre-tax transit benefit information",
    "2025-changes": "Changes to MTA fares and tolls in 2025",
    "lirr-metro-north/ticket-refunds": "Refunds on LIRR and Metro-North tickets",
}


@app.route("/fares-tolls")
@app.route("/fares-tolls/<path:sub>")
def fares_hub(sub=""):
    if sub in ("lirr-metro-north", "lirr-metro-north/ticket-refunds"):
        return render_template("fares_rail.html", sub=sub,
                               page=ContentPage.query.get(f"/fares-tolls/{sub}"),
                               zones=sorted({int(z) for z in
                                             db.session.query(RailFare.origin_zone).distinct()} if False else []))
    page = ContentPage.query.get(f"/fares-tolls/{sub}" if sub else "/fares-tolls")
    if page is None:
        abort(404)
    return render_template("content_page.html", page=page,
                           active_nav="/fares-tolls" + ("/" + sub if sub else ""))


@app.route("/tolls/vehicle-types")
def tolls_vehicle_types():
    page = ContentPage.query.get("/tolls/vehicle-types")
    return render_template("content_page.html", page=page,
                           active_nav="/fares-tolls/tolls")


@app.route("/fares-tolls/lirr-metro-north/fare-finder")
def rail_fare_finder():
    """Interactive fare tables: pick origin + destination stations."""
    lirr = Station.query.filter_by(agency="lirr").order_by(Station.name).all()
    mnr = Station.query.filter_by(agency="mnr").order_by(Station.name).all()
    origin = request.args.get("from", "")
    dest = request.args.get("to", "")
    ticket = request.args.get("ticket", "One-Way Peak")
    result = None
    if origin and dest:
        o = Station.query.filter_by(name=origin, agency="lirr").first()
        d = Station.query.filter_by(name=dest, agency="lirr").first()
        if o is None or d is None:
            o = Station.query.filter_by(name=origin, agency="mnr").first()
            d = Station.query.filter_by(name=dest, agency="mnr").first()
        if o is not None and d is not None and o.zone and d.zone:
            if o.agency == "lirr":
                fare = RailFare.query.filter_by(origin_zone=o.zone, dest_zone=d.zone,
                                                ticket_type=ticket).first()
                if fare:
                    result = {"origin": o, "dest": d, "ticket": ticket,
                              "price": fare.price, "railroad": "Long Island Rail Road"}
            else:
                line = ("harlem_hudson" if
                        MnrFare.query.filter_by(line="harlem_hudson", zone=o.zone).first()
                        else "new_haven")
                # the fare finder's ticket list uses the LIRR ticket names;
                # Metro-North's fare tables carry their own ticket names with
                # separate peak / off-peak prices, so translate here
                mnr_type, mnr_leg = MNR_TICKET_MAP.get(ticket, (None, None))
                fare = (MnrFare.query.filter_by(line=line, zone=o.zone,
                                                ticket_type=mnr_type).first()
                        if mnr_type else None)
                if fare:
                    price = fare.price
                    if mnr_leg == "peak" and fare.price_peak is not None:
                        price = fare.price_peak
                    elif mnr_leg == "offpeak" and fare.price_offpeak is not None:
                        price = fare.price_offpeak
                    result = {"origin": o, "dest": d, "ticket": mnr_type,
                              "price": price, "railroad": "Metro-North Railroad"}
    return render_template("fare_finder.html", lirr=lirr, mnr=mnr, origin=origin,
                           dest=dest, ticket=ticket, result=result,
                           tickets=["One-Way Peak", "One-Way Off-Peak", "Weekly",
                                    "Monthly", "One-Way Senior/Disabled/Medicare",
                                    "Day Pass - Weekday", "Day Pass - Weekend"])


# Metro-North's official fare tables name their ticket types differently
# from the LIRR's (and publish peak / off-peak one-way prices as a pair), so
# the finder's LIRR-style ticket names map onto them as follows.
MNR_TICKET_MAP = {
    "One-Way Peak": ("One-Way (adult)", "peak"),
    "One-Way Off-Peak": ("One-Way (adult)", "offpeak"),
    "One-Way Senior/Disabled/Medicare": ("One-Way (senior)", "base"),
    "Weekly": ("Weekly", "base"),
    "Monthly": ("Monthly", "base"),
    "Day Pass - Weekday": ("Day Pass", "peak"),
    "Day Pass - Weekend": ("Day Pass", "offpeak"),
}


# The official railroad fare charts parsed into the seed (see
# source_data/fare_docs/ and NOTICE.md) are served as PDFs so the LIRR /
# Metro-North fares page can link the fare tables the way upstream does.
FARE_CHARTS = {
    "lirr_fares": "Long Island Rail Road fares",
    "mnr_harlem_hudson_gct": "Metro-North Harlem and Hudson Line fares to GCT",
    "mnr_newhaven_gct": "Metro-North New Haven Line fares to GCT",
    "mnr_harlem_hudson_intermediate": "Metro-North Harlem and Hudson intermediate fares",
    "mnr_newhaven_intermediate": "Metro-North New Haven Line intermediate fares",
    "port_jervis_pascack": "Port Jervis and Pascack Valley Line fares",
}


@app.route("/fares-tolls/lirr-metro-north/fare-chart/<name>.pdf")
def fare_chart_pdf(name):
    """Official LIRR / Metro-North fare chart PDFs (tracked source data)."""
    if name not in FARE_CHARTS:
        abort(404)
    path = os.path.join(BASE_DIR, "source_data", "fare_docs", name + ".pdf")
    if not os.path.exists(path):
        abort(404)
    from flask import send_file
    return send_file(path, mimetype="application/pdf", as_attachment=False,
                     download_name=name + ".pdf")


# ---------------------------------------------------------------------------
# Content pages (about, guides, projects, press, accessibility, agency...)
# ---------------------------------------------------------------------------

@app.route("/maps")
def maps_page():
    page = ContentPage.query.get("/maps")
    return render_template("content_page.html", page=page, active_nav="/maps")


@app.route("/accessibility")
def accessibility_page():
    page = ContentPage.query.get("/accessibility")
    return render_template("content_page.html", page=page, active_nav="/accessibility")


@app.route("/accessibility/access-a-ride")
def aar_page():
    page = ContentPage.query.get("/accessibility/access-a-ride")
    return render_template("content_page.html", page=page, active_nav="/accessibility")


@app.route("/accessibility/access-a-ride/book", methods=["GET", "POST"])
@login_required
def aar_book():
    if request.method == "POST":
        pickup = request.form.get("pickup", "").strip()
        destination = request.form.get("destination", "").strip()
        trip_date = request.form.get("date", "").strip()
        pickup_time = request.form.get("time", "").strip()
        passengers = request.form.get("passengers", "1", type=int)
        mobility = request.form.get("mobility_aid", "").strip()
        purpose = request.form.get("purpose", "").strip()
        errors = []
        if not pickup:
            errors.append("Enter a pickup address.")
        if not destination:
            errors.append("Enter a destination address.")
        if not trip_date:
            errors.append("Choose a trip date.")
        if not pickup_time:
            errors.append("Choose a pickup time.")
        if errors:
            return render_template("aar_book.html", errors=errors, form=request.form), 400
        trip = AarTrip(trip_ref=next_ref("AAR"), user_id=current_user.id,
                       pickup_address=pickup, destination_address=destination,
                       trip_date=trip_date, pickup_time=pickup_time,
                       passengers=passengers, mobility_aid=mobility, purpose=purpose)
        db.session.add(trip)
        db.session.commit()
        return redirect(url_for("account_aar"))
    return render_template("aar_book.html", errors=[], form={})


@app.route("/guides")
def guides_index():
    page = ContentPage.query.get("/guides")
    guides = [("service-alerts", "Sign up for service alerts"),
              ("riding-the-subway", "Riding the subway"),
              ("riding-the-bus", "Riding the bus"),
              ("airports", "Getting to and from New York-area airports"),
              ("bikes", "Taking your bike with you"),
              ("pets", "Taking your pet with you"),
              ("weather-service-guide", "Extreme weather travel guide"),
              ("stadiums", "Getting to NYC-area stadiums and arenas on transit")]
    return render_template("guides.html", page=page, guides=guides)


@app.route("/guides/<slug>")
def guide_page(slug):
    page = ContentPage.query.get(f"/guides/{slug}")
    if page is None:
        abort(404)
    return render_template("content_page.html", page=page, active_nav="/guides")


@app.route("/guides/service-alerts", methods=["GET", "POST"])
def service_alerts_guide():
    page = ContentPage.query.get("/guides/service-alerts")
    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Sign in to manage your service alert subscriptions.")
            return redirect(url_for("account.login"))
        service_type = request.form.get("service_type", "subway")
        service_id = request.form.get("service_id", "").strip()
        if not service_id:
            flash("Choose a service to subscribe to.")
        else:
            sub = AlertSubscription.query.filter_by(
                user_id=current_user.id, service_type=service_type,
                service_id=service_id).first()
            if sub is None:
                db.session.add(AlertSubscription(user_id=current_user.id,
                                                 email=current_user.email,
                                                 service_type=service_type,
                                                 service_id=service_id))
                db.session.commit()
                flash(f"You are now subscribed to {service_id} alerts.")
            else:
                flash(f"You already receive {service_id} alerts.")
        return redirect(url_for("service_alerts_guide"))
    return render_template("service_alerts.html", page=page,
                           subway_ids=SUBWAY_LINE_ORDER,
                           rail_ids=RAIL_BRANCHES["lirr"] + RAIL_BRANCHES["mnr"])


@app.route("/about")
def about_page():
    page = ContentPage.query.get("/about")
    return render_template("content_page.html", page=page, active_nav="/about")


@app.route("/transparency")
def transparency_page():
    page = ContentPage.query.get("/transparency")
    return render_template("content_page.html", page=page, active_nav="/transparency")


@app.route("/transparency/board-and-committee-meetings")
def board_meetings():
    page = ContentPage.query.get("/transparency/board-and-committee-meetings")
    return render_template("content_page.html", page=page, active_nav="/transparency")


@app.route("/transparency/leadership/executive-leadership")
def executive_leadership():
    page = ContentPage.query.get("/transparency/leadership/executive-leadership")
    return render_template("content_page.html", page=page, active_nav="/transparency")


@app.route("/transparency/leadership/board-members")
def board_members():
    page = ContentPage.query.get("/transparency/leadership/board-members")
    return render_template("content_page.html", page=page, active_nav="/transparency")


@app.route("/safety-and-security")
def safety_page():
    page = ContentPage.query.get("/safety-and-security")
    return render_template("content_page.html", page=page, active_nav="/safety-and-security")


@app.route("/careers")
def careers_page():
    page = ContentPage.query.get("/careers")
    return render_template("content_page.html", page=page, active_nav="/careers")


@app.route("/climate")
def climate_page():
    page = ContentPage.query.get("/climate")
    return render_template("content_page.html", page=page, active_nav="/careers")


@app.route("/agency")
def agency_index():
    page = ContentPage.query.get("/agency")
    return render_template("content_page.html", page=page, active_nav="/about")


@app.route("/agency/<slug>")
def agency_page(slug):
    if slug == "long-island-rail-road":
        page = ContentPage.query.get("/agency/long-island-rail-road")
        return render_template("agency_lirr.html", page=page)
    if slug == "metro-north-railroad":
        page = ContentPage.query.get("/agency/metro-north-railroad")
        return render_template("agency_mnr.html", page=page)
    page = ContentPage.query.get(f"/agency/{slug}")
    if page is None:
        abort(404)
    return render_template("content_page.html", page=page, active_nav="/about")


@app.route("/doing-business-with-us")
@app.route("/doing-business-with-us/procurement")
def doing_business():
    path = request.path
    page = ContentPage.query.get(path)
    if page is None:
        abort(404)
    return render_template("content_page.html", page=page, active_nav="/about")


@app.route("/project")
def projects_index():
    return render_template("projects.html",
                           projects=Project.query.order_by(Project.slug).all())


@app.route("/project/<slug>")
def project_page(slug):
    p = Project.query.get(slug)
    if p is None:
        abort(404)
    return render_template("project.html", project=p)


@app.route("/press-release")
def press_index():
    releases = PressRelease.query.order_by(PressRelease.id.desc()).all()
    return render_template("press.html", releases=releases)


@app.route("/press-release/<slug>")
def press_article(slug):
    art = PressRelease.query.filter(PressRelease.path.endswith(slug)).first()
    if art is None:
        abort(404)
    others = PressRelease.query.order_by(PressRelease.id.desc()).limit(5).all()
    return render_template("press_article.html", art=art, others=others)


@app.route("/article/<slug>")
def article_page(slug):
    art = PressRelease.query.filter(PressRelease.path == f"/article/{slug}").first()
    if art is None:
        # the G-line service changes article is stored under /article/
        art = PressRelease.query.filter(PressRelease.path.endswith(slug)).first()
    if art is None:
        # some /article/ links point at Drupal content pages (e.g. the
        # Disability Pride Month article) rather than press releases
        page = ContentPage.query.get(f"/article/{slug}")
        if page is not None:
            return render_template("content_page.html", page=page, active_nav="")
        abort(404)
        return
    return render_template("press_article.html", art=art, others=[])


@app.route("/terms-and-conditions")
@app.route("/privacy-policy")
def legal_page():
    page = ContentPage.query.get(request.path)
    if page is None:
        abort(404)
    return render_template("content_page.html", page=page, active_nav="")


@app.route("/<path:path>")
def content_page(path):
    if not path:
        abort(404)
    page = ContentPage.query.get("/" + path)
    if page is None:
        abort(404)
    return render_template("content_page.html", page=page, active_nav="/" + path)


# ---------------------------------------------------------------------------
# Lost & found + feedback
# ---------------------------------------------------------------------------

LOST_AGENCIES = {
    "subway-bus-and-staten-island-railway": ("nyct", "Subway, Bus and Staten Island Railway"),
    "long-island-rail-road": ("lirr", "Long Island Rail Road"),
    "metro-north-railroad": ("mnr", "Metro-North Railroad"),
}


@app.route("/lost-and-found")
def lost_found():
    page = ContentPage.query.get("/lost-and-found")
    return render_template("lost_found.html", page=page)


@app.route("/lost-and-found/<agency>")
def lost_found_agency(agency):
    if agency not in LOST_AGENCIES:
        abort(404)
    code, label = LOST_AGENCIES[agency]
    page = ContentPage.query.get(f"/lost-and-found/{agency}")
    return render_template("lost_found_agency.html", page=page, code=code,
                           label=label, agency_slug=agency)


@app.route("/lost-and-found/<agency>/claim", methods=["GET", "POST"])
def lost_claim_form(agency):
    if agency not in LOST_AGENCIES:
        abort(404)
    code, label = LOST_AGENCIES[agency]
    if request.method == "POST":
        required = ["date_lost", "line_route", "station", "item_type",
                    "item_description", "contact_name", "contact_email"]
        errors = []
        form = {k: request.form.get(k, "").strip() for k in
                required + ["contact_phone"]}
        for k in required:
            if not form[k]:
                errors.append(f"Enter {k.replace('_', ' ')}.")
        if form["contact_email"] and "@" not in form["contact_email"]:
            errors.append("Enter a valid email address.")
        if errors:
            return render_template("lost_claim_form.html", agency_slug=agency,
                                   code=code, label=label, errors=errors,
                                   form=form), 400
        claim = LostClaim(
            claim_ref=next_ref("LF"),
            user_id=current_user.id if current_user.is_authenticated else None,
            agency=code,
            date_lost=form["date_lost"], line_route=form["line_route"],
            station=form["station"], item_type=form["item_type"],
            item_description=form["item_description"],
            contact_name=form["contact_name"], contact_email=form["contact_email"],
            contact_phone=form["contact_phone"])
        db.session.add(claim)
        db.session.commit()
        return redirect(url_for("lost_claim_status", ref=claim.claim_ref))
    return render_template("lost_claim_form.html", agency_slug=agency, code=code,
                           label=label, errors=[], form={})


@app.route("/lost-and-found/claim/<ref>")
def lost_claim_status(ref):
    claim = LostClaim.query.filter_by(claim_ref=ref).first()
    if claim is None:
        abort(404)
    return render_template("lost_claim_status.html", claim=claim)


@app.route("/contact-us")
def contact_page():
    page = ContentPage.query.get("/contact-us")
    return render_template("contact.html", page=page)


@app.route("/contact-us/feedback", methods=["GET", "POST"])
def feedback_form():
    if request.method == "POST":
        required = ["category", "subject", "message", "contact_name", "contact_email"]
        errors = []
        form = {k: request.form.get(k, "").strip() for k in required}
        for k in required:
            if not form[k]:
                errors.append(f"Enter {k.replace('_', ' ')}.")
        if form["contact_email"] and "@" not in form["contact_email"]:
            errors.append("Enter a valid email address.")
        if errors:
            return render_template("feedback_form.html", errors=errors, form=form), 400
        case = FeedbackCase(
            case_ref=next_ref("CS"),
            user_id=current_user.id if current_user.is_authenticated else None,
            category=form["category"], subject=form["subject"],
            message=form["message"])
        db.session.add(case)
        db.session.commit()
        return redirect(url_for("case_status", ref=case.case_ref))
    return render_template("feedback_form.html", errors=[], form={})


@app.route("/contact-us/case/<ref>")
def case_status(ref):
    case = FeedbackCase.query.filter_by(case_ref=ref).first()
    if case is None:
        abort(404)
    return render_template("case_status.html", case=case)


@app.route("/lost-and-found/claim")
def lost_claim_lookup():
    ref = request.args.get("ref", "").strip()
    if ref:
        claim = LostClaim.query.filter_by(claim_ref=ref).first()
        if claim:
            return redirect(url_for("lost_claim_status", ref=ref))
        flash("No claim found with that reference number.")
    return render_template("claim_lookup.html", kind="claim",
                           action=url_for("lost_claim_lookup"), ref=ref)


@app.route("/contact-us/case")
def case_lookup():
    ref = request.args.get("ref", "").strip()
    if ref:
        case = FeedbackCase.query.filter_by(case_ref=ref).first()
        if case:
            return redirect(url_for("case_status", ref=ref))
        flash("No case found with that number.")
    return render_template("claim_lookup.html", kind="case",
                           action=url_for("case_lookup"), ref=ref)


# ---------------------------------------------------------------------------
# Account domain
# ---------------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/account/register", methods=["GET", "POST"])
def account_register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        display = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        errors = []
        if not email or "@" not in email:
            errors.append("Enter a valid email address.")
        if not username:
            errors.append("Choose a username.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with that email already exists.")
        if User.query.filter_by(username=username).first():
            errors.append("That username is taken.")
        if errors:
            return render_template("register.html", errors=errors, form=request.form), 400
        user = User(email=email, username=username, display_name=display or username,
                    password_hash=bcrypt.generate_password_hash(password).decode(),
                    omny_serial="OMNY-" + hashlib.sha1(email.encode()).hexdigest()[:8].upper())
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("account_home"))
    return render_template("register.html", errors=[], form={})


@app.route("/account/login", methods=["GET", "POST"])
def account_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            return render_template("login.html", error="Invalid email or password.",
                                   form=request.form), 401
        login_user(user)
        return redirect(request.args.get("next") or url_for("account_home"))
    return render_template("login.html", error=None, form={})


@app.route("/account/logout")
@login_required
def account_logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/account")
@login_required
def account_home():
    return render_template("account/home.html", user=current_user)


@app.route("/account/favorites", methods=["GET", "POST"])
@login_required
def account_favorites():
    if request.method == "POST":
        action = request.form.get("action", "add")
        service_type = request.form.get("service_type", "subway")
        service_id = request.form.get("service_id", "").strip()
        if not service_id:
            flash("Choose a service.")
        elif action == "remove":
            f = Favorite.query.filter_by(user_id=current_user.id,
                                        service_type=service_type,
                                        service_id=service_id).first()
            if f:
                db.session.delete(f)
                db.session.commit()
                flash(f"Removed {service_id} from your favorites.")
        else:
            if Favorite.query.filter_by(user_id=current_user.id,
                                        service_type=service_type,
                                        service_id=service_id).first() is None:
                db.session.add(Favorite(user_id=current_user.id,
                                       service_type=service_type, service_id=service_id))
                db.session.commit()
                flash(f"{service_id} added to your favorites.")
        return redirect(url_for("account_favorites"))
    return render_template("account/favorites.html", user=current_user,
                           subway_ids=SUBWAY_LINE_ORDER,
                           rail_ids=RAIL_BRANCHES["lirr"] + RAIL_BRANCHES["mnr"])


@app.route("/favorites/toggle", methods=["POST"])
@login_required
def favorites_toggle():
    service_type = request.form.get("service_type", "subway")
    service_id = request.form.get("service_id", "").strip()
    back = request.form.get("back") or url_for("home")
    if service_id:
        f = Favorite.query.filter_by(user_id=current_user.id,
                                     service_type=service_type,
                                     service_id=service_id).first()
        if f:
            db.session.delete(f)
        else:
            db.session.add(Favorite(user_id=current_user.id, service_type=service_type,
                                    service_id=service_id))
        db.session.commit()
    return redirect(back)


@app.route("/account/subscriptions", methods=["GET", "POST"])
@login_required
def account_subscriptions():
    if request.method == "POST":
        action = request.form.get("action", "add")
        service_type = request.form.get("service_type", "subway")
        service_id = request.form.get("service_id", "").strip()
        if not service_id:
            flash("Choose a service.")
        elif action == "remove":
            s = AlertSubscription.query.filter_by(user_id=current_user.id,
                                                 service_type=service_type,
                                                 service_id=service_id).first()
            if s:
                db.session.delete(s)
                db.session.commit()
                flash(f"Unsubscribed from {service_id} alerts.")
        else:
            if AlertSubscription.query.filter_by(user_id=current_user.id,
                                                service_type=service_type,
                                                service_id=service_id).first() is None:
                db.session.add(AlertSubscription(user_id=current_user.id,
                                                 email=current_user.email,
                                                 service_type=service_type,
                                                 service_id=service_id))
                db.session.commit()
                flash(f"You are now subscribed to {service_id} alerts.")
        return redirect(url_for("account_subscriptions"))
    return render_template("account/subscriptions.html", user=current_user,
                           subway_ids=SUBWAY_LINE_ORDER,
                           rail_ids=RAIL_BRANCHES["lirr"] + RAIL_BRANCHES["mnr"])


@app.route("/account/omny")
@login_required
def account_omny():
    week = current_user.omny_week
    return render_template("account/omny.html", user=current_user, week=week)


@app.route("/account/claims")
@login_required
def account_claims():
    return render_template("account/claims.html", user=current_user)


@app.route("/account/aar")
@login_required
def account_aar():
    return render_template("account/aar.html", user=current_user)


@app.route("/account/cases")
@login_required
def account_cases():
    return render_template("account/cases.html", user=current_user)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.route("/_health")
def health():
    try:
        counts = {
            "stations": Station.query.count(),
            "alerts": ServiceAlert.query.count(),
            "trips": Trip.query.count(),
            "users": User.query.count(),
        }
        return jsonify({"ok": all(v >= 0 for v in counts.values()), **counts})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)[:200]}), 500


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()
    from seed_data import seed_benchmark_users, seed_database  # noqa: E402
    seed_database()
    seed_benchmark_users()
