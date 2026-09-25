#!/usr/bin/env python3
"""FlightAware (flightaware.com) mirror — live flight tracker surface:
airport activity boards, flight detail + history pages, delays and
cancellation statistics, MiseryMap, Flight Finder, fleet and aircraft-type
browsers, aviation photo community, Squawks headlines, and an authenticated
account area with flight status alerts."""
import json
import os
import re
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "flightaware.db")

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-flightaware-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to see airport activity boards and manage your alerts."

# The snapshot is pinned against the live capture date (2026-09-22).
MIRROR_REFERENCE_DATE = date(2026, 9, 22)
MIRROR_DATE_TEXT = "September 22, 2026"
MIRROR_CLOCK_TEXT = "08:41AM EDT"

STOP_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "is", "are", "be", "by", "from", "how", "what", "which", "that",
    "this", "flight", "flights", "airport", "airline",
}

BOARD_NAMES = {
    "arrivals": "Arrivals",
    "departures": "Departures",
    "enroute": "En Route/Scheduled Arrivals",
    "scheduled": "Scheduled Departures",
}


def parse_minutes(text):
    """'08:50a EDT' -> 530 (local minutes). Returns None when unparseable."""
    if not text:
        return None
    m = re.search(r"(\d{1,2}):(\d{2})\s*([ap])", text.lower())
    if not m:
        return None
    hour, minute, half = int(m.group(1)), int(m.group(2)), m.group(3)
    if hour == 12:
        hour = 0
    if half == "p":
        hour += 12
    return hour * 60 + minute


def display_ident(ident):
    """UAL123 -> UA123 (IATA-style display like upstream)."""
    m = re.match(r"^([A-Z]{3})(\d+)$", ident)
    if not m:
        return ident
    code, number = m.groups()
    iata = AIRLINE_IATA.get(code)
    if iata:
        return f"{iata}{number}"
    return ident


AIRLINE_IATA = {}  # filled at seed time via Airline rows


def refresh_airline_iata():
    AIRLINE_IATA.clear()
    for airline in Airline.query.all():
        if airline.iata:
            AIRLINE_IATA[airline.code] = airline.iata


def scored_search(query, items, fields):
    """Token-overlap scored search; never a strict AND."""
    tokens = [t.lower() for t in re.split(r"\W+", query or "")
              if t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return items
    results = []
    for item in items:
        text = " ".join(str(getattr(item, f, "") or "") for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            results.append((item, score))
    results.sort(key=lambda pair: (-pair[1], getattr(pair[0], "id", 0)))
    return [r[0] for r in results]


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(140), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), default="")

    @property
    def is_benchmark(self):
        return self.email.endswith("@test.com")


class Alert(db.Model):
    __tablename__ = "alerts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ident = db.Column(db.String(20), default="")
    origin_code = db.Column(db.String(10), default="")
    dest_code = db.Column(db.String(10), default="")
    alert_type = db.Column(db.String(40), default="basic")
    created_text = db.Column(db.String(40), default="about a week ago")
    user = db.relationship("User", backref="alerts")


class Airport(db.Model):
    __tablename__ = "airports"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False)      # ICAO e.g. KJFK
    iata = db.Column(db.String(8), default="")                       # JFK
    name = db.Column(db.String(140), nullable=False)
    city = db.Column(db.String(80), default="")
    region = db.Column(db.String(80), default="")
    country = db.Column(db.String(80), default="")
    tz_label = db.Column(db.String(20), default="")                   # EDT
    tz_offset = db.Column(db.String(20), default="")                   # UTC-04:00
    elevation_ft = db.Column(db.Integer)
    latitude = db.Column(db.String(24), default="")
    longitude = db.Column(db.String(24), default="")
    runway_info = db.Column(db.Text, default="")                      # real remarks lines
    weather_text = db.Column(db.Text, default="")                     # real METAR/weather lines
    remarks_text = db.Column(db.Text, default="")
    is_major = db.Column(db.Boolean, default=False)

    @property
    def display_code(self):
        return self.iata or self.code

    @property
    def title_label(self):
        if self.city:
            return f"{self.name} ({self.city}, {self.region or self.country})"
        return self.name


class Airline(db.Model):
    __tablename__ = "airlines"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(4), unique=True, nullable=False)   # UAL
    iata = db.Column(db.String(4), default="")                     # UA
    name = db.Column(db.String(120), nullable=False)
    country = db.Column(db.String(80), default="")
    flights_count = db.Column(db.Integer, default=0)


class AircraftType(db.Model):
    __tablename__ = "aircraft_types"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False)   # B789
    name = db.Column(db.String(120), default="")                  # Boeing 787-9 Dreamliner
    manufacturer = db.Column(db.String(60), default="")
    engines = db.Column(db.String(120), default="")               # e.g. (twin-jet)
    flights_count = db.Column(db.Integer, default=0)


class Flight(db.Model):
    """One dated flight instance (ident + date). Today's board flights carry
    flight_date == MIRROR_REFERENCE_DATE; history rows carry their real
    historical dates."""
    __tablename__ = "flights"
    id = db.Column(db.Integer, primary_key=True)
    ident = db.Column(db.String(20), nullable=False, index=True)
    airline_code = db.Column(db.String(4), default="")
    flight_date = db.Column(db.String(20), default="")             # 2026-09-22
    aircraft_type = db.Column(db.String(8), default="")
    origin_code = db.Column(db.String(8), default="")
    origin_name = db.Column(db.String(140), default="")
    dest_code = db.Column(db.String(8), default="")
    dest_name = db.Column(db.String(140), default="")
    sched_dep = db.Column(db.String(40), default="")               # as displayed upstream
    actual_dep = db.Column(db.String(40), default="")
    sched_arr = db.Column(db.String(40), default="")
    actual_arr = db.Column(db.String(40), default="")
    dep_text = db.Column(db.String(40), default="")                # board-display departure
    arr_text = db.Column(db.String(40), default="")                # board-display arrival
    gate_dep = db.Column(db.String(40), default="")
    gate_arr = db.Column(db.String(40), default="")
    dep_terminal = db.Column(db.String(40), default="")
    arr_terminal = db.Column(db.String(40), default="")
    status = db.Column(db.String(60), default="")                  # EN ROUTE AND ON TIME ...
    status_detail = db.Column(db.String(120), default="")
    elapsed_text = db.Column(db.String(20), default="")
    total_travel_text = db.Column(db.String(30), default="")
    remaining_text = db.Column(db.String(20), default="")
    flown_mi = db.Column(db.Integer)
    togo_mi = db.Column(db.Integer)
    dep_delay_min = db.Column(db.Integer)
    arr_delay_min = db.Column(db.Integer)
    duration_text = db.Column(db.String(20), default="")          # 15:42
    distance_mi = db.Column(db.Integer)
    speed_mph = db.Column(db.Integer)
    planned_speed_mph = db.Column(db.Integer)
    altitude_ft = db.Column(db.Integer)
    planned_altitude_ft = db.Column(db.Integer)
    route = db.Column(db.Text, default="")                        # waypoint string
    is_today = db.Column(db.Boolean, default=False)

    @property
    def display(self):
        return display_ident(self.ident)


class BoardRow(db.Model):
    """Exact row captured from a live airport activity board."""
    __tablename__ = "board_rows"
    id = db.Column(db.Integer, primary_key=True)
    airport_code = db.Column(db.String(8), nullable=False, index=True)
    board = db.Column(db.String(12), nullable=False)              # arrivals/departures/enroute/scheduled
    ident = db.Column(db.String(20), default="")
    aircraft_type = db.Column(db.String(8), default="")
    other_label = db.Column(db.String(140), default="")           # 'Ministro Pistarini Int'l (EZE)'
    dep_text = db.Column(db.String(40), default="")
    arr_text = db.Column(db.String(40), default="")
    sort_min = db.Column(db.Integer)                              # parsed from the relevant column
    row_index = db.Column(db.Integer, default=0)

    @property
    def display(self):
        return display_ident(self.ident)


class AirportDelay(db.Model):
    __tablename__ = "airport_delays"
    id = db.Column(db.Integer, primary_key=True)
    airport_code = db.Column(db.String(8), default="")
    airport_label = db.Column(db.String(140), default="")         # Manchester (MAN / EGCC)
    dep_delay_text = db.Column(db.String(120), default="")
    arr_delay_text = db.Column(db.String(120), default="")
    region_label = db.Column(db.String(80), default="")


class CancelStat(db.Model):
    __tablename__ = "cancel_stats"
    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(30), default="airline")           # airline/origin/dest
    label = db.Column(db.String(140), default="")
    cancelled = db.Column(db.Integer, default=0)
    cancelled_pct = db.Column(db.String(12), default="0%")
    delayed = db.Column(db.Integer, default=0)
    delayed_pct = db.Column(db.String(12), default="0%")


class DailyStat(db.Model):
    __tablename__ = "daily_stats"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(60), unique=True, nullable=False)
    value = db.Column(db.String(200), default="")
    value_int = db.Column(db.Integer)


class Photo(db.Model):
    __tablename__ = "photos"
    id = db.Column(db.Integer, primary_key=True)
    pid = db.Column(db.String(20), unique=True, nullable=False)
    view_hash = db.Column(db.String(50), default="")
    title = db.Column(db.String(160), default="")                 # Airbus A321 (G-MEDM)
    aircraft_type = db.Column(db.String(10), default="")           # A321
    registration = db.Column(db.String(16), default="")            # G-MEDM
    airline_prefix = db.Column(db.String(16), default="")         # FDX (from title)
    airport_code = db.Column(db.String(10), default="")
    photographer = db.Column(db.String(80), default="")
    description = db.Column(db.Text, default="")
    submitted_text = db.Column(db.String(40), default="")
    votes = db.Column(db.Integer, default=0)
    vote_average = db.Column(db.Float, default=0.0)
    views = db.Column(db.Integer, default=0)
    staff_pick = db.Column(db.Boolean, default=False)
    week_top = db.Column(db.Boolean, default=False)
    reg_rank = db.Column(db.Integer)                              # 'X of REG' counts
    type_rank = db.Column(db.Integer)
    image_file = db.Column(db.String(80), default="")

    @property
    def href(self):
        return f"/photos/view/{self.pid}-{self.view_hash}/all/sort/votes/page/1"


class PhotoComment(db.Model):
    __tablename__ = "photo_comments"
    id = db.Column(db.Integer, primary_key=True)
    photo_id = db.Column(db.Integer, db.ForeignKey("photos.id"), nullable=False)
    author = db.Column(db.String(80), default="")
    when_text = db.Column(db.String(40), default="")
    text = db.Column(db.Text, default="")
    photo = db.relationship("Photo", backref="comments")


class Squawk(db.Model):
    __tablename__ = "squawks"
    id = db.Column(db.Integer, primary_key=True)
    sid = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(220), default="")
    slug = db.Column(db.String(220), default="")
    source_label = db.Column(db.String(120), default="")           # (aeroxplorer.com)
    source_url = db.Column(db.String(300), default="")
    summary = db.Column(db.Text, default="")
    submitter = db.Column(db.String(80), default="")
    submitted_text = db.Column(db.String(60), default="")
    votes = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)
    staff_pick = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(40), default="general")
    lists = db.Column(db.String(120), default="")                  # popular,new,...


class SquawkComment(db.Model):
    __tablename__ = "squawk_comments"
    id = db.Column(db.Integer, primary_key=True)
    squawk_id = db.Column(db.Integer, db.ForeignKey("squawks.id"), nullable=False)
    author = db.Column(db.String(80), default="")
    when_text = db.Column(db.String(40), default="")
    text = db.Column(db.Text, default="")
    squawk = db.relationship("Squawk", backref="comments")


# ---------------------------------------------------------------------------
# Template filters
# ---------------------------------------------------------------------------

@app.template_filter("commas")
def commas(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return value


@app.template_filter("fa_date")
def fa_date(value):
    """'2026-09-22' -> 'TUESDAY 22-SEP-2026' (upstream display format)."""
    if not value:
        return ""
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
        return d.strftime("%A %d-%b-%Y").upper()
    except (ValueError, TypeError):
        return value


@app.template_filter("nl2br")
def nl2br(value):
    if not value:
        return ""
    return Markup(str(value).replace("\r\n", "\n").replace("\n", "<br>"))


# ---------------------------------------------------------------------------
# Shared context
# ---------------------------------------------------------------------------

NAV_MENU = [
    ("Products", [
        ("Data Products", [
            ("AeroAPI", "/commercial/aeroapi/"), ("FlightAware Firehose", "/commercial/firehose/"),
            ("FlightAware Foresight", "/commercial/foresight/"), ("Rapid Reports", "/commercial/reports/"),
            ("Custom Reports", "/commercial/reports/"), ("Integrated Mapping Solutions", "/commercial/integrated-maps/"),
        ]),
        ("Applications", [
            ("FlightAware Aviator", "/commercial/aviator/"), ("Premium Subscriptions", "/account/premium/"),
            ("FlightAware Global", "/commercial/global/"), ("FlightAware FBO Toolbox", "/commercial/fbo-toolbox/"),
            ("FlightAware TV", "/commercial/tv/"), ("GlobalBeacon", "/commercial/globalbeacon/"),
        ]),
    ]),
    ("Industries", [("Airports", "/industries/airports/"), ("Airlines", "/industries/airlines/"),
                    ("Business", "/industries/business/"), ("Government", "/industries/government/"),
                    ("Manufacturer", "/industries/manufacturer/"), ("Travel", "/industries/travel/")]),
    ("ADS-B", [("Statistics", "/adsb/stats/"), ("SkyAware Anywhere", "/adsb/skyaware-anywhere/"),
               ("Coverage Map", "/adsb/coverage/"), ("ADS-B Store", "/adsb/store/"),
               ("Build a PiAware ADS-B Receiver", "/adsb/piaware/"), ("FlightFeeder", "/adsb/flightfeeder/"),
               ("FAQs", "/about/faq/")]),
    ("Flight Tracking", [
        ("Delays and cancellations", [
            ("Cancellations", "/live/cancelled/"), ("Airport Delays", "/live/airport/delays/"),
            ("MiseryMap", "/miserymap/"),
        ]),
        ("Search flights", "/live/form.rvt"),
        ("Flight Finder", "/live/findflight/"),
        ("Browse by Operator", "/live/fleet/"),
        ("Browse by Airport", "/live/airport/random"),
        ("Browse by Aircraft Type", "/live/aircrafttype/"),
        ("Other", [
            ("Random Airport", "/live/airport/random"), ("Random Flight", "/live/flight/random"),
            ("IFR Route Analyzer", "/statistics/ifr-route/"),
        ]),
    ]),
    ("Community", [
        ("Photos", [("Popular Photos", "/photos/all/sort/views"), ("Newest Photos", "/photos/all/sort/date"),
                    ("Highest Ranked", "/photos/all/sort/votes"), ("Staff Picks", "/photos/staffpicks"),
                    ("Recent Comments", "/photos/recentcomments.rvt"), ("Community Tagging", "/photos/crowdsource"),
                    ("Upload Your Photos", "/photos/upload")]),
        ("Squawks", [("Current Squawks", "/squawks/"), ("New Squawks", "/squawks/new"),
                     ("Popular Squawks", "/squawks/")]),
        ("Discussions", [("All Discussions", "/discussions/")]),
    ]),
    ("Company", [("About", "/about/"), ("Careers", "/about/careers/"), ("Data Sources", "/about/data-sources/"),
                 ("History", "/about/history/"), ("Blog", "/blog/"), ("Engineering Blog", "/engineering/"),
                 ("Newsroom", "/news/"), ("Webinars", "/webinars/"),
                 ("Advertise With Us", "/commercial/advertising/"), ("FAQs", "/about/faq/"),
                 ("Contact", "/about/contact/")]),
]


# Thin landing pages for the upstream nav/footer marketing + company
# destinations (Products, Industries, ADS-B hardware, Company) — see
# _marketing_pages.py for the per-page copy. Registered below, before
# the site routes are complete, so every visible link resolves.
from _marketing_pages import MARKETING_PAGES  # noqa: E402

# JFK Terminal Area Forecast snapshot (reviewer finding #4) — see _jfk_taf.py.
from _jfk_taf import JFK_TAF_ROWS  # noqa: E402


@app.context_processor
def inject_chrome():
    return {
        "nav_menu": NAV_MENU,
        "mirror_clock": MIRROR_CLOCK_TEXT,
        "mirror_date_text": MIRROR_DATE_TEXT,
    }


def board_for(airport_code, board):
    rows = BoardRow.query.filter_by(airport_code=airport_code, board=board).order_by(BoardRow.row_index).all()
    return rows


def airport_or_404(code):
    code = code.upper().strip()
    airport = Airport.query.filter_by(code=code).first()
    if airport:
        return airport
    if code.startswith("K"):
        airport = Airport.query.filter_by(code=code[1:]).first()
    if airport:
        return airport
    iata = Airport.query.filter_by(iata=code).first()
    if iata:
        return iata
    abort(404)


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------

@app.route("/")
@app.route("/live/")
def live_home():
    airports = Airport.query.filter_by(is_major=True).order_by(Airport.code).all()
    operators = Airline.query.order_by(Airline.flights_count.desc(), Airline.name).limit(14).all()
    types = AircraftType.query.order_by(AircraftType.flights_count.desc(), AircraftType.code).limit(14).all()
    activity_airports = Airport.query.order_by(Airport.id).limit(10).all()
    return render_template("live.html", airports=airports, operators=operators,
                           types=types, activity_airports=activity_airports)


def _flight_page_idents():
    """Idents that have a flight detail page (flights table membership).

    Board rows are a snapshot and can reference private idents whose
    detail page is outside the mirrored flights table; those render as
    plain text (upstream has a page for every board ident; the mirror
    archives 1,228 detail pages — see NOTICE.md).
    """
    return {row[0] for row in db.session.query(Flight.ident).distinct()}


@app.route("/live/airport/random")
def random_airport():
    airports = Airport.query.all()
    if not airports:
        abort(404)
    import random as _random
    airport = _random.choice(airports)
    return redirect(url_for("airport_page", code=airport.code))


@app.route("/live/flight/random")
def random_flight():
    flights = Flight.query.filter_by(is_today=True).all()
    if not flights:
        abort(404)
    import random as _random
    flight = _random.choice(flights)
    return redirect(url_for("flight_page", ident=flight.ident))


@app.route("/live/airport/<code>")
@app.route("/live/airport/<code>/")
def airport_page(code):
    airport = airport_or_404(code)
    page_idents = _flight_page_idents()
    arrivals = board_for(airport.code, "arrivals")[:8]
    departures = board_for(airport.code, "departures")[:8]
    enroute = board_for(airport.code, "enroute")[:8]
    scheduled = board_for(airport.code, "scheduled")[:8]
    delays = AirportDelay.query.filter_by(airport_code=airport.code).first()
    return render_template("airport.html", airport=airport, arrivals=arrivals,
                           departures=departures, enroute=enroute, scheduled=scheduled,
                           delay=delays, board_names=BOARD_NAMES,
                           page_idents=page_idents)


@app.route("/live/airport/<code>/<board>")
def airport_board(code, board):
    if board not in BOARD_NAMES:
        abort(404)
    airport = airport_or_404(code)
    rows = board_for(airport.code, board)
    page_idents = _flight_page_idents()
    if current_user.is_authenticated:
        return render_template("board.html", airport=airport, board=board,
                               board_name=BOARD_NAMES[board], rows=rows,
                               page_idents=page_idents)
    return render_template("board_login_required.html", airport=airport, board=board,
                           board_name=BOARD_NAMES[board])


@app.route("/live/airport/delays/")
def delays_page():
    total_us = DailyStat.query.filter_by(key="us_delays_today").first()
    total_world = DailyStat.query.filter_by(key="world_delays_today").first()
    delays = AirportDelay.query.order_by(AirportDelay.id).all()
    return render_template("delays.html", delays=delays,
                           total_us=total_us.value_int if total_us else None,
                           total_world=total_world.value_int if total_world else None)


@app.route("/live/cancelled/")
def cancellations_page():
    stats_by = {s.scope: [] for s in CancelStat.query.all()}
    for s in CancelStat.query.order_by(CancelStat.cancelled.desc()).all():
        stats_by.setdefault(s.scope, []).append(s)
    totals = {s.key: s for s in DailyStat.query.all()}
    return render_template("cancelled.html", stats_by=stats_by, totals=totals)


@app.route("/miserymap/")
def miserymap_page():
    delays = AirportDelay.query.order_by(AirportDelay.id).all()
    total_us = DailyStat.query.filter_by(key="us_delays_today").first()
    return render_template("miserymap.html", delays=delays,
                           total_us=total_us.value_int if total_us else None)


@app.route("/live/flight/<ident>")
@app.route("/live/flight/<ident>/")
def flight_page(ident):
    ident = ident.upper().strip()
    flight = Flight.query.filter_by(ident=ident, is_today=True).first()
    if flight is None:
        flight = Flight.query.filter_by(ident=ident).order_by(Flight.flight_date.desc()).first()
    if flight is None:
        return render_template("flight_missing.html", ident=ident), 404
    airline = Airline.query.filter_by(code=flight.airline_code).first()
    aircraft = AircraftType.query.filter_by(code=flight.aircraft_type).first()
    top_photos = Photo.query.filter_by(aircraft_type=flight.aircraft_type) \
        .order_by(Photo.votes.desc()).limit(2).all()
    upcoming = Flight.query.filter(Flight.ident == ident, Flight.flight_date > MIRROR_REFERENCE_DATE.isoformat()) \
        .order_by(Flight.flight_date).limit(3).all()
    past = Flight.query.filter(Flight.ident == ident, Flight.flight_date < MIRROR_REFERENCE_DATE.isoformat()) \
        .order_by(Flight.flight_date.desc()).limit(8).all()
    origin = Airport.query.filter_by(code=flight.origin_code).first()
    dest = Airport.query.filter_by(code=flight.dest_code).first()
    return render_template("flight.html", flight=flight, airline=airline,
                           aircraft=aircraft, top_photos=top_photos,
                           upcoming=upcoming, past=past, origin=origin, dest=dest)


@app.route("/live/flight/<ident>/history")
def flight_history(ident):
    ident = ident.upper().strip()
    flights = Flight.query.filter_by(ident=ident).order_by(Flight.flight_date.desc()).all()
    if not flights:
        return render_template("flight_missing.html", ident=ident), 404
    airline = Airline.query.filter_by(code=flights[0].airline_code).first()
    return render_template("flight_history.html", flights=flights, ident=ident, airline=airline)


@app.route("/live/form.rvt")
def search_results():
    query = (request.args.get("query") or request.args.get("q") or "").strip()
    flight_number = (request.args.get("flight_number") or "").strip().upper()
    if flight_number:
        operator = (request.args.get("airline") or "").strip().upper()
        query = operator + flight_number if flight_number.isdigit() else flight_number
    kind = request.args.get("type", "")
    if not query:
        return redirect(url_for("live_home"))
    ql = query.lower()
    results = {"flights": [], "airports": [], "photos": [], "squawks": []}
    ident_exact = query.upper().replace(" ", "")
    flights = Flight.query.filter(Flight.ident == ident_exact, Flight.is_today == True).all()  # noqa: E712
    if flights:
        results["flights"] = flights
    else:
        text_flights = Flight.query.filter(Flight.is_today == True).all()  # noqa: E712
        results["flights"] = scored_search(query, text_flights,
                                           ["ident", "origin_name", "dest_name",
                                            "origin_code", "dest_code", "airline_code"])[:12]
    airports = Airport.query.all()
    results["airports"] = scored_search(query, airports,
                                        ["code", "iata", "name", "city", "country"])[:8]
    photos = Photo.query.all()
    results["photos"] = scored_search(query, photos,
                                       ["title", "aircraft_type", "registration",
                                        "photographer", "airport_code"])[:6]
    squawks = Squawk.query.all()
    results["squawks"] = scored_search(query, squawks,
                                       ["title", "summary", "source_label", "submitter"])[:6]
    total = sum(len(v) for v in results.values())
    return render_template("search_results.html", query=query, kind=kind, results=results, total=total)


@app.route("/live/findflight/", methods=["GET", "POST"])
def findflight():
    origin_q = (request.values.get("origin") or "").strip()
    dest_q = (request.values.get("destination") or "").strip()
    airline_q = (request.values.get("airline") or "").strip()
    flights = []
    searched = bool(origin_q or dest_q or airline_q)

    def airport_match(airport, q):
        if not airport:
            return False
        ql = q.lower()
        return (ql in (airport.code or "").lower() or ql in (airport.iata or "").lower()
                or ql in (airport.name or "").lower() or ql in (airport.city or "").lower())

    def resolve_airport(q):
        candidates = Airport.query.all()
        hits = scored_search(q, candidates, ["code", "iata", "name", "city"])
        return hits[0] if hits else None

    if searched:
        base = Flight.query.filter_by(is_today=True)
        rows = base.all()
        for f in rows:
            origin = Airport.query.filter_by(code=f.origin_code).first()
            dest = Airport.query.filter_by(code=f.dest_code).first()
            if origin_q and not airport_match(origin, origin_q):
                continue
            if dest_q and not airport_match(dest, dest_q):
                continue
            if airline_q:
                airline = Airline.query.filter_by(code=f.airline_code).first()
                if airline and airline_q.lower() not in (airline.name or "").lower() \
                        and airline_q.lower() != (airline.code or "").lower():
                    continue
            flights.append(f)
        flights.sort(key=lambda f: (f.sched_dep or f.dep_text or ""))
    airports = Airport.query.order_by(Airport.name).all()
    return render_template("findflight.html", origin_q=origin_q, dest_q=dest_q,
                           airline_q=airline_q, flights=flights, airports=airports, searched=searched)


@app.route("/live/fleet/")
def fleet_index():
    airlines = Airline.query.order_by(Airline.flights_count.desc(), Airline.name).all()
    return render_template("fleet_index.html", airlines=airlines)


@app.route("/live/fleet/<code>")
def fleet_page(code):
    code = code.upper().strip()
    airline = Airline.query.filter_by(code=code).first()
    if airline is None:
        airline = Airline.query.filter_by(iata=code).first()
    if airline is None:
        abort(404)
    flights = Flight.query.filter_by(airline_code=airline.code, is_today=True) \
        .order_by(Flight.sched_dep).all()
    return render_template("fleet.html", airline=airline, flights=flights)


@app.route("/live/aircrafttype/")
def aircrafttype_index():
    types = AircraftType.query.order_by(AircraftType.flights_count.desc(), AircraftType.code).all()
    return render_template("aircrafttype_index.html", types=types)


@app.route("/live/aircrafttype/<code>")
def aircrafttype_page(code):
    code = code.upper().strip()
    aircraft = AircraftType.query.filter_by(code=code).first()
    if aircraft is None:
        abort(404)
    flights = Flight.query.filter_by(aircraft_type=code, is_today=True).all()
    flights.sort(key=lambda f: (f.sched_dep or f.dep_text or ""))
    return render_template("aircrafttype.html", aircraft=aircraft, flights=flights)


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------

@app.route("/photos/")
def photos_featured():
    staff = Photo.query.filter_by(staff_pick=True).order_by(Photo.votes.desc()).all()
    if not staff:
        staff = Photo.query.order_by(Photo.votes.desc()).all()
    highest = Photo.query.order_by(Photo.votes.desc()).limit(6).all()
    return render_template("photos_featured.html", staff=staff[:6], highest=highest)


@app.route("/photos/all")
@app.route("/photos/all/")
@app.route("/photos/all/sort/<sort>")
@app.route("/photos/all/sort/<sort>/page/<int:page>")
def photos_all(sort="votes", page=1):
    if sort not in ("votes", "date", "views"):
        sort = "votes"
    q = (request.args.get("q") or "").strip()
    query = Photo.query
    if q:
        query = scored_search(q, query.all(),
                              ["title", "aircraft_type", "registration",
                               "photographer", "airline_prefix", "airport_code"])
        if sort == "votes":
            query.sort(key=lambda p: -p.votes)
        elif sort == "views":
            query.sort(key=lambda p: -p.views)
        else:
            query.sort(key=lambda p: -p.id)
        per_page = 18
        total = len(query)
        photos = query[(page - 1) * per_page:(page) * per_page]
        return render_template("photos_all.html", photos=photos, sort=sort, page=page,
                               per_page=per_page, total=total, q=q)
    if sort == "votes":
        query = query.order_by(Photo.votes.desc())
    elif sort == "views":
        query = query.order_by(Photo.views.desc())
    else:
        query = query.order_by(Photo.id.desc())
    per_page = 18
    total = query.count()
    photos = query.offset((page - 1) * per_page).limit(per_page).all()
    return render_template("photos_all.html", photos=photos, sort=sort, page=page,
                           per_page=per_page, total=total, q=q)


@app.route("/photos/staffpicks")
@app.route("/photos/staffpicks/")
def photos_staffpicks():
    photos = Photo.query.filter_by(staff_pick=True).order_by(Photo.votes.desc()).all()
    if not photos:
        photos = Photo.query.order_by(Photo.votes.desc()).limit(12).all()
    return render_template("photos_staffpicks.html", photos=photos)


@app.route("/photos/view/<pathref>")
@app.route("/photos/view/<pathref>/<path:rest>")
def photo_page(pathref, rest="all/sort/votes/page/1"):
    m = re.match(r"^(\d+)-([0-9a-f]+)$", pathref)
    if not m:
        abort(404)
    pid = m.group(1)
    photo = Photo.query.filter_by(pid=pid).first()
    if photo is None:
        abort(404)
    same_type = Photo.query.filter_by(aircraft_type=photo.aircraft_type) \
        .order_by(Photo.votes.desc()).all()
    return render_template("photo_detail.html", photo=photo,
                           same_type=same_type[:6])


@app.route("/photos/upload")
def photos_upload():
    return render_template("photos_upload.html")


@app.route("/photos/recentcomments.rvt")
def photos_recent_comments():
    comments = PhotoComment.query.order_by(PhotoComment.id.desc()).limit(24).all()
    return render_template("photos_recent_comments.html", comments=comments)


@app.route("/photos/crowdsource")
def photos_crowdsource():
    photos = Photo.query.order_by(Photo.id.desc()).limit(12).all()
    return render_template("photos_crowdsource.html", photos=photos)


# ---------------------------------------------------------------------------
# Squawks
# ---------------------------------------------------------------------------

@app.route("/squawks/")
@app.route("/squawks/browse/general/<period>/<order>")
def squawks_list(period="24_hours", order="popular"):
    query = Squawk.query
    if order == "new":
        squawks = query.order_by(Squawk.submitted_text.desc(), Squawk.sid.desc()).all()
    elif order == "most_discussed":
        squawks = query.order_by(Squawk.comment_count.desc(), Squawk.votes.desc()).all()
    elif order == "staff_picks":
        squawks = query.filter_by(staff_pick=True).order_by(Squawk.votes.desc()).all()
    else:
        squawks = query.order_by(Squawk.votes.desc(), Squawk.sid.desc()).all()
    return render_template("squawks_list.html", squawks=squawks,
                           period=period, order=order)


@app.route("/squawks/new")
def squawks_new():
    squawks = Squawk.query.order_by(Squawk.sid.desc()).all()
    return render_template("squawks_list.html", squawks=squawks,
                           period="24_hours", order="new")


@app.route("/squawks/view/<int:group>/<path:ref>/<int:sid>")
@app.route("/squawks/view/<int:group>/<path:ref>/<int:sid>/<slug>")
@app.route("/squawks/link/<int:group>/<path:ref>/<int:sid>")
@app.route("/squawks/link/<int:group>/<path:ref>/<int:sid>/<slug>")
def squawk_page(sid, group=1, ref="24_hours/popular", slug=""):
    squawk = Squawk.query.filter_by(sid=str(sid)).first()
    if squawk is None:
        abort(404)
    return render_template("squawk_detail.html", squawk=squawk)


@app.route("/squawks/search.rvt")
def squawk_search():
    query = (request.args.get("q") or "").strip()
    squawks = []
    if query:
        squawks = scored_search(query, Squawk.query.all(),
                                ["title", "summary", "source_label", "submitter"])
    return render_template("squawks_search.html", squawks=squawks, query=query)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

@app.route("/account/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.values.get("email") or "").strip().lower()
        password = request.values.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            target = request.args.get("next")
            if target and target.startswith("/"):
                return redirect(target)
            return redirect(url_for("account_home"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/account/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("live_home"))


@app.route("/account/join", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.values.get("username") or "").strip()
        email = (request.values.get("email") or "").strip().lower()
        password = request.values.get("password") or ""
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif not username or not email:
            flash("Username and email are required.", "error")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "error")
        elif User.query.filter_by(username=username).first():
            flash("That username is taken.", "error")
        else:
            user = User(username=username, email=email,
                        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("account_home"))
    return render_template("register.html")


@app.route("/account/")
@login_required
def account_home():
    alerts = Alert.query.filter_by(user_id=current_user.id).order_by(Alert.id).all()
    alert_idents = [a.ident for a in alerts if a.ident]
    tracked = [Flight.query.filter_by(ident=i, is_today=True).first() for i in alert_idents]
    tracked = [f for f in tracked if f]
    return render_template("account.html", alerts=alerts, tracked=tracked)


@app.route("/account/alerts/add", methods=["POST"])
@login_required
def alerts_add():
    ident = (request.values.get("ident") or "").strip().upper()
    origin_code = (request.values.get("origin") or "").strip().upper()
    dest_code = (request.values.get("destination") or "").strip().upper()
    alert_type = request.values.get("alert_type") or "basic"
    if not ident and not (origin_code or dest_code):
        flash("Enter a flight number or a route to watch.", "error")
        return redirect(url_for("account_home"))
    alert = Alert(user_id=current_user.id, ident=ident, origin_code=origin_code,
                  dest_code=dest_code, alert_type=alert_type,
                  created_text="just now")
    db.session.add(alert)
    db.session.commit()
    flash("Alert created.", "success")
    return redirect(url_for("account_home"))


@app.route("/account/alerts/<int:alert_id>/delete", methods=["POST"])
@login_required
def alerts_delete(alert_id):
    alert = Alert.query.filter_by(id=alert_id, user_id=current_user.id).first()
    if alert is None:
        abort(404)
    db.session.delete(alert)
    db.session.commit()
    flash("Alert removed.", "success")
    return redirect(url_for("account_home"))


@app.route("/account/premium/")
def premium():
    return render_template("premium.html")


# ---------------------------------------------------------------------------
# Airport resources
# ---------------------------------------------------------------------------

@app.route("/resources/airport/<code>/weather")
def airport_weather(code):
    airport = airport_or_404(code)
    taf_rows = JFK_TAF_ROWS if airport.code == "KJFK" else None
    return render_template("airport_weather.html", airport=airport, taf_rows=taf_rows)


@app.route("/resources/airport/<code>/map")
def airport_map(code):
    airport = airport_or_404(code)
    return render_template("airport_map.html", airport=airport)


@app.route("/resources/airport/<code>/remarks")
def airport_remarks(code):
    airport = airport_or_404(code)
    return render_template("airport_remarks.html", airport=airport)


# ---------------------------------------------------------------------------
# Marketing/company endpoints (thin landing pages mirroring upstream nav)
# ---------------------------------------------------------------------------

@app.route("/about/")
def about():
    return render_template("about.html")


@app.route("/adsb/stats/")
def adsb_stats():
    return render_template("adsb_stats.html")


@app.route("/statistics/ifr-route/")
def ifr_route():
    return render_template("ifr_route.html")


@app.route("/discussions/")
def discussions():
    return render_template("discussions.html")


def _marketing_view():
    meta = MARKETING_PAGES.get(request.path)
    if meta is None:
        abort(404)
    title, head, paragraphs, links = meta
    return render_template("generic.html", page_title=title, page_head=head,
                           page_body="\n\n".join(paragraphs),
                           marketing_links=links)


for _i, _path in enumerate(MARKETING_PAGES):
    app.add_url_rule(_path, f"marketing_page_{_i}", _marketing_view, methods=["GET"])


@app.route("/_health")
def health():
    try:
        flights = Flight.query.count()
        airports = Airport.query.count()
        photos = Photo.query.count()
        squawks = Squawk.query.count()
        return jsonify({"ok": True, "site": "flightaware",
                        "flights": flights, "airports": airports,
                        "photos": photos, "squawks": squawks})
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):  # pragma: no cover
    return render_template("500.html"), 500


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def seed_database():
    if Flight.query.count() > 0:
        return
    from seed_data import seed_static_data
    seed_static_data(db)


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    from seed_data import seed_users
    seed_users(db, bcrypt)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()
    refresh_airline_iata()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
