"""
Google Flights mirror — Flask application.

Data model adapted for flight booking:
  - Airport/City = taxonomy (from -> to)
  - Flight = entity (route, airline, price, dates, stops)
  - Cart/Bag -> "Trip Cart" (selected flights pending checkout)
  - Order -> Booking (confirmed flight purchase with PNR)
  - Wishlist -> "Tracked Flights" (price tracking)
  - Review -> Flight Review (rating + comment after flight)
  - Plus: PriceAlert (notify when price drops), SavedSearch (flexible explore)
"""
import os
import json
import random
import re
import string
from datetime import datetime, date, timedelta
from pathlib import Path

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         current_user, login_required)
from flask_wtf import CSRFProtect
from flask_bcrypt import Bcrypt
from sqlalchemy import or_, and_
from werkzeug.exceptions import HTTPException

BASE_DIR = Path(__file__).parent

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'google-flights-dev-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{BASE_DIR}/instance/google_flights.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to continue.'
csrf = CSRFProtect(app)


# ============================================================
# MODELS
# ============================================================

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(60), default='')
    last_name = db.Column(db.String(60), default='')
    phone = db.Column(db.String(30), default='')
    address = db.Column(db.String(200), default='')
    city = db.Column(db.String(60), default='')
    country = db.Column(db.String(60), default='')
    passport_number = db.Column(db.String(30), default='')
    frequent_flyer = db.Column(db.String(30), default='')
    date_of_birth = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cart_items = db.relationship('CartItem', backref='user', lazy='dynamic',
                                 cascade='all, delete-orphan')
    bookings = db.relationship('Booking', backref='user', lazy='dynamic',
                               cascade='all, delete-orphan')
    tracked = db.relationship('TrackedFlight', backref='user', lazy='dynamic',
                              cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='user', lazy='dynamic',
                              cascade='all, delete-orphan')
    alerts = db.relationship('PriceAlert', backref='user', lazy='dynamic',
                             cascade='all, delete-orphan')
    saved_searches = db.relationship('SavedSearch', backref='user', lazy='dynamic',
                                     cascade='all, delete-orphan')
    payment_methods = db.relationship('PaymentMethod', backref='user', lazy='dynamic',
                                      cascade='all, delete-orphan')

    @property
    def full_name(self):
        n = f"{self.first_name} {self.last_name}".strip()
        return n or self.email.split('@')[0]


class Airport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    iata = db.Column(db.String(4), unique=True, nullable=False, index=True)
    city_slug = db.Column(db.String(60), index=True)
    city = db.Column(db.String(80), nullable=False)
    country = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(120), default='')  # Full airport name
    region = db.Column(db.String(40), default='')
    is_popular = db.Column(db.Boolean, default=False)
    image = db.Column(db.String(300), default='')
    gallery_json = db.Column(db.Text, default='[]')
    description = db.Column(db.Text, default='')

    def get_gallery(self):
        try:
            return json.loads(self.gallery_json) if self.gallery_json else []
        except Exception:
            return []


class Flight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flight_number = db.Column(db.String(10), nullable=False, index=True)
    airline = db.Column(db.String(80), nullable=False)
    airline_code = db.Column(db.String(4), default='')
    airline_logo = db.Column(db.String(200), default='')

    origin_id = db.Column(db.Integer, db.ForeignKey('airport.id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('airport.id'), nullable=False)

    departure_date = db.Column(db.Date, nullable=False)
    departure_time = db.Column(db.String(8), default='08:00')  # HH:MM
    arrival_date = db.Column(db.Date, nullable=False)
    arrival_time = db.Column(db.String(8), default='12:00')
    duration_minutes = db.Column(db.Integer, default=180)

    stops = db.Column(db.Integer, default=0)
    stop_cities = db.Column(db.String(200), default='')  # comma-separated IATA codes

    aircraft = db.Column(db.String(60), default='Boeing 737')
    cabin_class = db.Column(db.String(20), default='Economy')
    price = db.Column(db.Float, nullable=False)  # base economy
    price_premium = db.Column(db.Float, default=0.0)
    price_business = db.Column(db.Float, default=0.0)
    price_first = db.Column(db.Float, default=0.0)

    co2_emissions_kg = db.Column(db.Integer, default=200)
    co2_vs_typical = db.Column(db.Integer, default=0)  # % diff vs typical

    baggage_free = db.Column(db.Integer, default=1)  # free checked bags
    baggage_included = db.Column(db.Boolean, default=True)
    return_date = db.Column(db.Date)  # used when row represents a round-trip leg pairing
    legroom_inches = db.Column(db.Integer, default=31)
    wifi = db.Column(db.Boolean, default=True)
    power = db.Column(db.Boolean, default=True)
    entertainment = db.Column(db.Boolean, default=True)
    meal_service = db.Column(db.String(120), default='')     # e.g. "Full meal service", "Snack box"
    seat_type = db.Column(db.String(80), default='')         # e.g. "Lie-flat seat", "Recliner", "Standard"
    seat_pitch = db.Column(db.String(40), default='')        # e.g. "78 in", "32 in"

    rating = db.Column(db.Float, default=4.2)
    is_best = db.Column(db.Boolean, default=False)  # top recommendation
    is_cheapest = db.Column(db.Boolean, default=False)
    is_fastest = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    origin = db.relationship('Airport', foreign_keys=[origin_id])
    destination = db.relationship('Airport', foreign_keys=[destination_id])

    @property
    def duration_str(self):
        h = self.duration_minutes // 60
        m = self.duration_minutes % 60
        return f"{h}h {m}m" if m else f"{h}h"

    @property
    def stops_str(self):
        if self.stops == 0:
            return "Nonstop"
        elif self.stops == 1:
            return "1 stop"
        return f"{self.stops} stops"

    @property
    def route_label(self):
        return f"{self.origin.iata} - {self.destination.iata}"


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    flight_id = db.Column(db.Integer, db.ForeignKey('flight.id'), nullable=False)
    return_flight_id = db.Column(db.Integer, db.ForeignKey('flight.id'))
    passengers = db.Column(db.Integer, default=1)
    cabin_class = db.Column(db.String(20), default='Economy')
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    flight = db.relationship('Flight', foreign_keys=[flight_id])
    return_flight = db.relationship('Flight', foreign_keys=[return_flight_id])

    @property
    def line_total(self):
        base = self.flight.price if self.flight else 0
        if self.return_flight:
            base += self.return_flight.price
        return round(base * self.passengers, 2)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pnr = db.Column(db.String(10), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), default='confirmed')  # confirmed, ticketed, flown, cancelled
    trip_type = db.Column(db.String(20), default='one-way')

    total_amount = db.Column(db.Float, default=0.0)
    taxes_fees = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(4), default='USD')

    passenger_names_json = db.Column(db.Text, default='[]')
    contact_email = db.Column(db.String(120), default='')
    contact_phone = db.Column(db.String(30), default='')

    payment_last4 = db.Column(db.String(4), default='')
    payment_brand = db.Column(db.String(20), default='Visa')

    booked_at = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled_at = db.Column(db.DateTime)

    items = db.relationship('BookingItem', backref='booking', lazy='dynamic',
                            cascade='all, delete-orphan')

    def get_passengers(self):
        try:
            return json.loads(self.passenger_names_json) if self.passenger_names_json else []
        except Exception:
            return []

    @property
    def item_count(self):
        return self.items.count()


class BookingItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    flight_id = db.Column(db.Integer, db.ForeignKey('flight.id'), nullable=False)
    leg = db.Column(db.String(12), default='outbound')  # outbound, return
    passengers = db.Column(db.Integer, default=1)
    cabin_class = db.Column(db.String(20), default='Economy')
    seat = db.Column(db.String(8), default='')
    price = db.Column(db.Float, default=0.0)

    flight = db.relationship('Flight')


class TrackedFlight(db.Model):
    """Price-tracking wishlist item."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    flight_id = db.Column(db.Integer, db.ForeignKey('flight.id'), nullable=False)
    target_price = db.Column(db.Float, default=0.0)
    starting_price = db.Column(db.Float, default=0.0)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    flight = db.relationship('Flight')


class PriceAlert(db.Model):
    """Email alert for a route price drop."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    origin_iata = db.Column(db.String(4), nullable=False)
    destination_iata = db.Column(db.String(4), nullable=False)
    threshold_price = db.Column(db.Float, default=0.0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedSearch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    label = db.Column(db.String(120), default='')
    origin_iata = db.Column(db.String(4), default='')
    destination_iata = db.Column(db.String(4), default='')
    departure_date = db.Column(db.Date)
    return_date = db.Column(db.Date)
    passengers = db.Column(db.Integer, default=1)
    cabin_class = db.Column(db.String(20), default='Economy')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    flight_id = db.Column(db.Integer, db.ForeignKey('flight.id'), nullable=False)
    rating = db.Column(db.Integer, default=5)  # 1-5
    title = db.Column(db.String(200), default='')
    body = db.Column(db.Text, default='')
    punctuality = db.Column(db.Integer, default=5)
    comfort = db.Column(db.Integer, default=5)
    service = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    flight = db.relationship('Flight')


class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    card_type = db.Column(db.String(20), nullable=False)  # Visa, Mastercard, Amex
    last4 = db.Column(db.String(4), nullable=False)
    exp_month = db.Column(db.Integer, nullable=False)
    exp_year = db.Column(db.Integer, nullable=False)
    cardholder_name = db.Column(db.String(120), default='')
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def display(self):
        return f"{self.card_type} ending {self.last4} (exp {self.exp_month:02d}/{self.exp_year})"


# ============================================================
# LOGIN + HELPERS
# ============================================================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def make_pnr():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


# Airline logos. Seeded rows still store /static/images/airlines/<slug>.svg
# (letter-tile placeholders in the published HF bundle). Real Google Flights
# 70px gstatic PNGs are committed under static/icons/airlines/{IATA}.png so
# this site does not depend on merging a logos-only google_flights.tar.gz.
# If a later asset bundle ships the named PNG/SVG, that file is used first.

def static_exists(relpath: str) -> bool:
    """True when relpath exists under this app's static/ directory."""
    if not relpath or relpath.startswith('/') or '\\' in relpath:
        return False
    parts = relpath.split('/')
    if any(p in ('', '.', '..') for p in parts):
        return False
    full = os.path.normpath(os.path.join(app.static_folder, *parts))
    root = os.path.abspath(app.static_folder)
    if full != root and not full.startswith(root + os.sep):
        return False
    return os.path.isfile(full)


def _safe_airline_code(value) -> str:
    text = (value or '').strip().upper()
    if not text or not re.fullmatch(r'[A-Z0-9]{2,3}', text):
        return ''
    return text


def _rel_from_public_path(path: str) -> str:
    """Map a stored /static/... URL onto a path relative to static/."""
    text = (path or '').strip()
    prefix = '/static/'
    if text.startswith(prefix):
        return text[len(prefix):]
    return ''


def airline_logo_relpath(flight) -> str:
    """Relative static path for an airline mark that exists on disk."""
    db_rel = _rel_from_public_path(getattr(flight, 'airline_logo', '') or '')
    code = _safe_airline_code(getattr(flight, 'airline_code', ''))
    if not code and db_rel:
        from seed_data import AIRLINES
        slug = Path(db_rel).stem.lower()
        code = next((c.upper() for _name, c, s in AIRLINES if s == slug), '')
        if not code:
            code = _safe_airline_code(slug)
    if code:
        icon_rel = f'icons/airlines/{code}.png'
        if static_exists(icon_rel):
            return icon_rel
        png_rel = f'images/airlines/{code}.png'
        if static_exists(png_rel):
            return png_rel
    if db_rel and static_exists(db_rel):
        return db_rel
    return ''


def airline_logo_url(flight) -> str:
    """Public URL for a real on-disk airline logo; empty if none exists."""
    rel = airline_logo_relpath(flight)
    if rel:
        return url_for('static', filename=rel)
    return ''


@app.context_processor
def inject_globals():
    cart_count = 0
    if current_user.is_authenticated:
        cart_count = current_user.cart_items.count()
    from flask_wtf.csrf import generate_csrf
    return {
        'cart_count': cart_count,
        'now': datetime.utcnow(),
        'current_year': datetime.utcnow().year,
        'csrf_token_value': generate_csrf(),
        'airline_logo_url': airline_logo_url,
    }


@app.template_filter('money')
def money(value):
    try:
        return f"${value:,.0f}" if value == int(value) else f"${value:,.2f}"
    except Exception:
        return f"${value}"


@app.template_filter('datefmt')
def datefmt(value, fmt='%b %d, %Y'):
    if not value:
        return ''
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d').date()
        except Exception:
            return value
    return value.strftime(fmt)


@app.context_processor
def _inject_airport_groups():
    """Surface multi-airport cities (New York → JFK/LGA/EWR, London → LHR/LGW,
    Tokyo → HND/NRT, …) as their own datalist entries so users can search by
    city name without picking one specific airport."""
    from collections import defaultdict
    by_city = defaultdict(list)
    for a in Airport.query.all():
        by_city[a.city].append(a.iata)
    multi = sorted(
        [(city, sorted(iatas)) for city, iatas in by_city.items() if len(iatas) > 1]
    )
    return {'multi_city_groups': multi}


# ============================================================
# ROUTES — Static
# ============================================================

@app.route('/')
def index():
    # Popular departure cities
    popular_origins = Airport.query.filter_by(is_popular=True, country='United States').limit(8).all()
    # Featured deals: one is_best flight per destination CITY so multi-airport
    # cities (London = LHR + LGW, Tokyo = HND + NRT) and per-date duplication
    # (every JFK→LHR date carries an is_best flag) don't fill the grid with
    # the same city image. Pick the lowest-id is_best per city via SQL so we
    # don't have to scan thousands of rows in Python.
    first_id_per_city = (
        db.session.query(db.func.min(Flight.id))
        .join(Airport, Airport.id == Flight.destination_id)
        .filter(Flight.is_best == True)
        .group_by(Airport.city)
        .subquery()
    )
    featured = (
        Flight.query
        .filter(Flight.id.in_(db.session.query(first_id_per_city)))
        .order_by(Flight.price)
        .limit(12).all()
    )
    if len(featured) < 12:
        seen_cities = {f.destination.city for f in featured}
        for f in (Flight.query.filter_by(is_cheapest=True)
                  .order_by(Flight.id).limit(800).all()):
            city = f.destination.city
            if city in seen_cities:
                continue
            seen_cities.add(city)
            featured.append(f)
            if len(featured) >= 12:
                break

    # Popular destinations — pick one airport per CITY so multi-airport cities
    # (London = LHR + LGW, Tokyo = HND + NRT) don't render twice.
    first_airport_per_city = (
        db.session.query(db.func.min(Airport.id))
        .filter(Airport.is_popular == True)
        .filter(Airport.country != 'United States')
        .group_by(Airport.city)
        .subquery()
    )
    popular_dests = (
        Airport.query
        .filter(Airport.id.in_(db.session.query(first_airport_per_city)))
        .order_by(Airport.city)
        .limit(8).all()
    )
    all_airports = Airport.query.order_by(Airport.is_popular.desc(), Airport.city).all()

    return render_template('index.html',
                           popular_origins=popular_origins,
                           popular_dests=popular_dests,
                           all_airports=all_airports,
                           featured=featured)


@app.route('/explore')
def explore():
    origin = request.args.get('origin', 'SEA').upper()
    origin_airport = Airport.query.filter_by(iata=origin).first()
    all_dests = Airport.query.filter_by(is_popular=True).all()
    flights_by_dest = {}
    if origin_airport:
        # Get cheapest flight FROM this origin to each destination
        dests_with_flights = db.session.query(Flight.destination_id).filter(
            Flight.origin_id == origin_airport.id
        ).distinct().all()
        dest_ids_reachable = {d[0] for d in dests_with_flights}
        # Group destinations by whether origin has flights to them
        reachable_dests = []
        for dest in all_dests:
            if dest.id in dest_ids_reachable and dest.id != origin_airport.id:
                f = Flight.query.filter_by(
                    origin_id=origin_airport.id,
                    destination_id=dest.id,
                ).order_by(Flight.price).first()
                if f:
                    flights_by_dest[dest.iata] = f
                    reachable_dests.append(dest)
        # Filter visible list to reachable destinations only, preserving popularity sort
        all_dests = reachable_dests
    else:
        # No matching origin: fall back to showing all popular destinations with global
        # cheapest flight, but mark the origin as unknown.
        for dest in all_dests:
            f = Flight.query.filter_by(destination_id=dest.id).order_by(Flight.price).first()
            if f:
                flights_by_dest[dest.iata] = f

    all_airports = Airport.query.filter_by(is_popular=True).order_by(Airport.city).all()
    return render_template('explore.html',
                           origin=origin,
                           origin_airport=origin_airport,
                           destinations=all_dests,
                           flights_by_dest=flights_by_dest,
                           all_airports=all_airports)


# Landmarks / place names that WebVoyager users sometimes type instead of an
# airport. Map lowercase substring -> IATA code of the nearest / primary airport.
# The substring is matched case-insensitively against the full query.
_LANDMARK_TO_IATA = {
    'glacier national park': 'FCA',
    'glacier park': 'FCA',
    'kalispell': 'FCA',
    'flathead': 'FCA',
    'montana': 'FCA',
}

# Multi-word city / airport phrases that the loose token matcher would
# otherwise resolve to the wrong airport. Maps lower-case phrase -> IATA.
_PHRASE_TO_IATA = {
    'tokyo narita': 'NRT',
    'narita': 'NRT',
    'tokyo haneda': 'HND',
    'haneda': 'HND',
    'new york jfk': 'JFK',
    'jfk': 'JFK',
    'newark': 'EWR',
    'laguardia': 'LGA',
    'london heathrow': 'LHR',
    'heathrow': 'LHR',
    'london gatwick': 'LGW',
    'gatwick': 'LGW',
    'paris cdg': 'CDG',
    'charles de gaulle': 'CDG',
    'athens greece': 'ATH',
    'hong kong': 'HKG',
    'los angeles': 'LAX',
    'san francisco': 'SFO',
    'las vegas': 'LAS',
    'mexico city': 'MEX',
    'sao paulo': 'GRU',
    'rio de janeiro': 'GIG',
    'buenos aires': 'EZE',
    'cape town': 'CPT',
    'abu dhabi': 'AUH',
    'tel aviv': 'TLV',
    'kuala lumpur': 'KUL',
    'osaka kansai': 'KIX',
    'punta cana': 'PUJ',
    'san juan': 'SJU',
}


def _resolve_airport_ids(query_str):
    """Resolve a query (IATA, city, city_slug, landmark, or free-form phrase)
    to a list of Airport ids.

    Handles multi-word inputs like "Tokyo Narita", "Athens Greece",
    "Lisbon LIS", "Hong Kong", and landmarks like "Glacier National Park".

    Returns (primary_airport_or_None, [ids]) — primary is first popular hit for display.
    """
    if not query_str:
        return None, []
    q = query_str.strip()
    if not q:
        return None, []
    q_lower = q.lower()

    # 1) Try IATA exact match first (case-insensitive, ignoring surrounding words)
    iata_exact = Airport.query.filter(Airport.iata == q.upper()).first()
    if iata_exact:
        return iata_exact, [iata_exact.id]

    # 2) Landmark / named-place aliases (e.g. "Glacier National Park" -> FCA)
    for phrase, iata in _LANDMARK_TO_IATA.items():
        if phrase in q_lower:
            a = Airport.query.filter_by(iata=iata).first()
            if a:
                return a, [a.id]

    # 3) Phrase aliases for well-known multi-word cities / airports.
    for phrase, iata in _PHRASE_TO_IATA.items():
        if phrase in q_lower:
            a = Airport.query.filter_by(iata=iata).first()
            if a:
                # If the phrase matches a city-level slug (Tokyo, New York),
                # return every airport in that city so user gets full inventory.
                siblings = Airport.query.filter_by(city_slug=a.city_slug).all()
                ids = [s.id for s in siblings] if siblings else [a.id]
                return a, ids

    # 4) Any 3-letter token in the query matching an IATA (e.g. "Lisbon LIS")
    import re
    tokens = [t for t in re.split(r'[\s,()/\-]+', q) if t]
    for t in tokens:
        if len(t) == 3 and t.isalpha():
            a = Airport.query.filter(Airport.iata == t.upper()).first()
            if a:
                siblings = Airport.query.filter_by(city_slug=a.city_slug).all()
                ids = [s.id for s in siblings] if siblings else [a.id]
                return a, ids

    # 5) Full-string contains match on city / slug / name.
    ql = f"%{q}%"
    hits = Airport.query.filter(
        or_(
            Airport.iata.ilike(q.upper()),
            Airport.city.ilike(ql),
            Airport.city_slug.ilike(f"%{q.lower().replace(' ', '-')}%"),
            Airport.name.ilike(ql),
        )
    ).all()

    # 6) Multi-token fallback: gather airports that match ANY meaningful token
    # in city/name/slug/country. Rank by number of tokens matched so that
    # "Tokyo Narita" prefers NRT over HND.
    if not hits and tokens:
        score_map = {}  # airport_id -> (score, airport)
        for t in tokens:
            if len(t) < 3:
                continue
            tl = f"%{t.lower()}%"
            tok_hits = Airport.query.filter(
                or_(
                    Airport.city.ilike(tl),
                    Airport.city_slug.ilike(tl),
                    Airport.name.ilike(tl),
                    Airport.country.ilike(tl),
                )
            ).all()
            for h in tok_hits:
                prev_score, _ = score_map.get(h.id, (0, h))
                score_map[h.id] = (prev_score + 1, h)
        if score_map:
            ranked = sorted(score_map.values(),
                            key=lambda x: (-x[0], 0 if x[1].is_popular else 1))
            max_score = ranked[0][0]
            hits = [h for s, h in ranked if s == max_score]

    if not hits:
        return None, []
    # Prefer popular airport as display primary
    primary = next((h for h in hits if h.is_popular), hits[0])
    return primary, [h.id for h in hits]


def _replace_year(d, target_year):
    if d is None or target_year is None:
        return d
    try:
        return d.replace(year=target_year)
    except ValueError:
        # Feb 29 in a non-leap target year
        return d.replace(year=target_year, month=2, day=28)


def _shift_flight_year(flight, dep_target, ret_target):
    """Overlay flight dates so a search for an arbitrary year displays with that
    year while the underlying inventory stays canonical. Mutates in place; the
    GET request never commits, so changes don't persist."""
    if dep_target is not None and flight.departure_date is not None:
        offset = (flight.arrival_date - flight.departure_date).days if flight.arrival_date else 0
        flight.departure_date = dep_target
        if flight.arrival_date is not None:
            flight.arrival_date = dep_target + timedelta(days=offset)
    if flight.return_date is not None:
        # Same-day round-trips (return_date == departure_date stored): keep them
        # same-day in the requested year. Otherwise carry the return year through.
        target = ret_target if ret_target is not None else dep_target
        flight.return_date = _replace_year(flight.return_date, target.year if target else None)


@app.route('/flights')
def flights_list():
    origin_query = request.args.get('from', '')
    dest_query = request.args.get('to', '')
    depart = request.args.get('depart', '')
    ret = request.args.get('return', '')
    passengers_raw = request.args.get('passengers', '1')
    try:
        passengers = int(passengers_raw or 1)
    except (TypeError, ValueError):
        passengers = 1
    if passengers < 1:
        passengers = 1
    elif passengers > 9:
        passengers = 9
    cabin = request.args.get('class', '') or request.args.get('cabin', '')
    trip_type = request.args.get('trip', 'round')
    sort = request.args.get('sort', 'best')
    max_stops = request.args.get('max_stops', '')
    max_price = request.args.get('max_price', '')
    min_price = request.args.get('min_price', '')
    airline = request.args.get('airline', '').strip()

    origin, origin_ids = _resolve_airport_ids(origin_query)
    dest, dest_ids = _resolve_airport_ids(dest_query)
    origin_iata = (origin.iata if origin else origin_query.upper() if origin_query else '')
    dest_iata = (dest.iata if dest else dest_query.upper() if dest_query else '')

    # ---- Input validation: collect human-readable errors so we never silently
    # return data for nonsense queries (return < depart, same airport, etc).
    validation_errors = []

    # Parse dates up-front so subsequent checks can compare them.
    dep_d = None
    if depart:
        try:
            dep_d = datetime.strptime(depart, '%Y-%m-%d').date()
        except ValueError:
            validation_errors.append(
                f"Invalid departure date '{depart}'. Use the format YYYY-MM-DD."
            )
    ret_d = None
    if ret:
        try:
            ret_d = datetime.strptime(ret, '%Y-%m-%d').date()
        except ValueError:
            validation_errors.append(
                f"Invalid return date '{ret}'. Use the format YYYY-MM-DD."
            )

    if dep_d and ret_d and ret_d < dep_d:
        validation_errors.append(
            f"Return date ({ret_d.isoformat()}) must be on or after the departure date "
            f"({dep_d.isoformat()})."
        )

    if origin_iata and dest_iata and origin_iata == dest_iata:
        validation_errors.append(
            f"Origin and destination cannot be the same airport ({origin_iata})."
        )

    if origin_query and not origin_ids:
        validation_errors.append(f"We don't recognize the origin '{origin_query}'.")
    if dest_query and not dest_ids:
        validation_errors.append(f"We don't recognize the destination '{dest_query}'.")

    try:
        mn_val = float(min_price) if min_price else None
    except ValueError:
        mn_val = None
        validation_errors.append(f"Invalid minimum price '{min_price}'.")
    try:
        mx_val = float(max_price) if max_price else None
    except ValueError:
        mx_val = None
        validation_errors.append(f"Invalid maximum price '{max_price}'.")
    if mn_val is not None and mx_val is not None and mn_val > mx_val:
        validation_errors.append(
            f"Minimum price (${mn_val:g}) cannot exceed maximum price (${mx_val:g})."
        )

    if max_stops != '':
        try:
            ms_val = int(max_stops)
            if ms_val < 0 or ms_val > 3:
                validation_errors.append(
                    f"Stops filter must be between 0 and 3 (got {max_stops})."
                )
        except ValueError:
            validation_errors.append(f"Invalid stops filter '{max_stops}'.")

    valid_cabins = {'', 'economy', 'coach', 'premium', 'premium economy',
                    'premium-economy', 'business', 'first'}
    if cabin and cabin.strip().lower() not in valid_cabins:
        validation_errors.append(
            f"Unknown cabin class '{cabin}'. Valid: Economy, Premium, Business, First."
        )

    # If validation failed, short-circuit: render empty results with the errors so
    # the user sees the problem rather than getting unrelated rows.
    if validation_errors:
        all_airports = Airport.query.order_by(Airport.is_popular.desc(), Airport.city).all()
        return render_template('flights.html',
                               flights=[],
                               origin=origin,
                               destination=dest,
                               origin_iata=origin_iata,
                               dest_iata=dest_iata,
                               depart=depart,
                               return_date=ret,
                               passengers=passengers,
                               cabin=cabin,
                               trip_type=trip_type,
                               sort=sort,
                               max_stops=max_stops,
                               min_price=min_price,
                               max_price=max_price,
                               airline=airline,
                               airline_options=[],
                               all_airports=all_airports,
                               not_found_hint='',
                               validation_errors=validation_errors,
                               origin_input=origin_query,
                               dest_input=dest_query)

    q = Flight.query
    if origin_query:
        q = q.filter(Flight.origin_id.in_(origin_ids))
    if dest_query:
        q = q.filter(Flight.destination_id.in_(dest_ids))

    # Date filtering: match by (month, day) across any year so the same
    # underlying inventory serves searches for any future year.
    if dep_d is not None:
        q = q.filter(
            db.func.strftime('%m-%d', Flight.departure_date)
            == f'{dep_d.month:02d}-{dep_d.day:02d}'
        )
    # Note: `ret` (return date) is displayed back in the form / price label, but
    # we do NOT filter rows by `Flight.return_date` — the return date is satisfied
    # by separately looking up a reciprocal flight on the return date (see
    # flight_detail). Filtering outbound inventory on the exact return_date
    # would incorrectly hide valid outbound flights when the user requests a
    # return date different from the seeded pairing.

    # Cabin class: match either the row's own cabin_class OR allow rows where the
    # class has a valid price set (price_business>0 etc.) so the same row can represent
    # different cabins for the user. Here we treat cabin_class as the requested filter
    # and keep rows whose cabin_class matches (case-insensitive) OR whose alternative
    # price field is populated.
    if cabin:
        cl = cabin.strip().lower()
        if cl in ('economy', 'coach'):
            pass  # every row has economy price
        elif cl in ('premium', 'premium economy', 'premium-economy'):
            q = q.filter(Flight.price_premium > 0)
        elif cl == 'business':
            q = q.filter(Flight.price_business > 0)
        elif cl == 'first':
            q = q.filter(Flight.price_first > 0)

    if max_stops != '':
        try:
            q = q.filter(Flight.stops <= int(max_stops))
        except ValueError:
            pass

    # Price filtering — interpret against the cabin's price column
    def _price_col():
        cl = (cabin or '').strip().lower()
        if cl == 'business':
            return Flight.price_business
        if cl == 'first':
            return Flight.price_first
        if cl in ('premium', 'premium economy', 'premium-economy'):
            return Flight.price_premium
        return Flight.price
    pc = _price_col()
    if max_price:
        try:
            q = q.filter(pc <= float(max_price))
        except ValueError:
            pass
    if min_price:
        try:
            q = q.filter(pc >= float(min_price))
        except ValueError:
            pass
    if airline:
        q = q.filter(Flight.airline.ilike(f'%{airline}%'))

    # Sort options mirror real Google Flights: Top / Price / Duration /
    # Departure time / Arrival time / Emissions. Stops sorts (asc/desc) don't
    # exist upstream; they fall through to "Top flights".
    if sort == 'price' or sort == 'price_asc':
        q = q.order_by(pc.asc())
    elif sort == 'duration':
        q = q.order_by(Flight.duration_minutes.asc())
    elif sort == 'departure':
        q = q.order_by(Flight.departure_time.asc())
    elif sort == 'arrival':
        q = q.order_by(Flight.arrival_time.asc())
    elif sort in ('emissions', 'co2'):
        q = q.order_by(Flight.co2_emissions_kg.asc())
    else:  # best — composite of price, duration, stops (mirrors real Google
        # Flights "Top flights" sort: balances cost and convenience, NOT
        # cheapest-first). is_best DESC keeps a curated top pick; everything
        # else falls through to the heuristic so cheap-but-painful flights
        # don't win.
        best_score = pc + Flight.duration_minutes * 0.4 + Flight.stops * 80
        q = q.order_by(Flight.is_best.desc(), best_score.asc())

    flights = q.limit(50).all()

    # If user provided route inputs but they resolved to nothing (bad IATA / unknown city),
    # show an empty state rather than falling back to all flights.
    # If NOTHING was provided at all, show top featured so /flights bare works.
    not_found_hint = ''
    if not flights:
        if origin_query and dest_query and (origin_ids and dest_ids):
            # route resolved but date / filters removed everything — suggest alt date
            any_route = Flight.query.filter(
                Flight.origin_id.in_(origin_ids),
                Flight.destination_id.in_(dest_ids),
            ).order_by(Flight.departure_date).first()
            if any_route:
                not_found_hint = f"This route has flights on {any_route.departure_date.strftime('%b %d')} (and other days) — try a different date or clearing filters."
        if not origin_query and not dest_query:
            flights = Flight.query.order_by(Flight.is_best.desc(), Flight.price).limit(30).all()

    # Year-shift displayed dates so searches for any year render with the
    # requested year (canonical inventory stays year-2024 etc).
    if dep_d is not None and flights:
        with db.session.no_autoflush:
            for f in flights:
                _shift_flight_year(f, dep_d, ret_d)

    # Unique airline list for the filter dropdown (scoped to this route if set)
    airline_q = db.session.query(Flight.airline).distinct()
    if origin_ids:
        airline_q = airline_q.filter(Flight.origin_id.in_(origin_ids))
    if dest_ids:
        airline_q = airline_q.filter(Flight.destination_id.in_(dest_ids))
    airline_options = sorted({row[0] for row in airline_q.limit(100).all()})

    all_airports = Airport.query.order_by(Airport.is_popular.desc(), Airport.city).all()

    return render_template('flights.html',
                           flights=flights,
                           origin=origin,
                           destination=dest,
                           origin_iata=origin_iata,
                           dest_iata=dest_iata,
                           depart=depart,
                           return_date=ret,
                           passengers=passengers,
                           cabin=cabin,
                           trip_type=trip_type,
                           sort=sort,
                           max_stops=max_stops,
                           min_price=min_price,
                           max_price=max_price,
                           airline=airline,
                           airline_options=airline_options,
                           all_airports=all_airports,
                           not_found_hint=not_found_hint,
                           validation_errors=[],
                           origin_input=origin_query,
                           dest_input=dest_query)


def _booking_sites_for_flight(flight):
    """Return a deterministic list of 'Booking sites' offering this flight,
    with synthetic prices per site. Used on the flight detail page so users
    can compare which third-party agency is cheapest.

    Prices are anchored to the flight's own economy price with site-specific
    multipliers so ordering is stable across requests.
    """
    # site label, multiplier vs economy price
    sites = [
        ('Expedia', 1.00),
        ('Kiwi.com', 0.96),
        ('Booking.com', 1.04),
        ('Kayak', 0.98),
        ('Priceline', 1.02),
    ]
    # Prefer the airline's own direct channel (slight discount) when plausible
    airline_site = {
        'KLM': ('KLM.com', 0.94),
        'Delta': ('Delta.com', 0.95),
        'United': ('United.com', 0.95),
        'British Airways': ('BritishAirways.com', 0.95),
        'Lufthansa': ('Lufthansa.com', 0.95),
        'Air France': ('AirFrance.com', 0.95),
        'American Airlines': ('AA.com', 0.95),
        'Japan Airlines': ('JAL.com', 0.95),
        'ANA': ('ANA.co.jp', 0.95),
        'Emirates': ('Emirates.com', 0.95),
        'Qatar Airways': ('QatarAirways.com', 0.95),
        'Etihad': ('EtihadAirways.com', 0.95),
        'Singapore Airlines': ('SingaporeAir.com', 0.94),
        'Cathay Pacific': ('CathayPacific.com', 0.95),
        'Turkish Airlines': ('TurkishAirlines.com', 0.95),
    }.get(flight.airline)
    entries = []
    base = flight.price_business if flight.price_business and flight.cabin_class.lower() == 'business' else flight.price
    for name, mult in sites:
        entries.append({
            'site': name,
            'economy_price': round(flight.price * mult, 0),
            'business_price': round(flight.price_business * mult, 0) if flight.price_business else None,
            'label': 'Third-party agency',
        })
    if airline_site:
        name, mult = airline_site
        entries.append({
            'site': name,
            'economy_price': round(flight.price * mult, 0),
            'business_price': round(flight.price_business * mult, 0) if flight.price_business else None,
            'label': 'Airline direct',
        })
    # Sort by economy price ascending so cheapest is first
    entries.sort(key=lambda e: e['economy_price'])
    return entries


@app.route('/flight/<int:flight_id>')
def flight_detail(flight_id):
    flight = db.session.get(Flight, flight_id) or abort(404)
    reviews = Review.query.filter_by(flight_id=flight_id).order_by(Review.created_at.desc()).all()
    avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else flight.rating
    booking_sites = _booking_sites_for_flight(flight)
    # Related flights on same route
    related = Flight.query.filter(
        Flight.id != flight_id,
        Flight.origin_id == flight.origin_id,
        Flight.destination_id == flight.destination_id,
    ).limit(6).all()

    # Parse the requested departure year (used for date overlay) up front so we
    # can validate return >= depart before resolving a return flight.
    dep_str = request.args.get('dep', '') or request.args.get('depart', '')
    dep_target = None
    if dep_str:
        try:
            dep_target = datetime.strptime(dep_str, '%Y-%m-%d').date()
        except ValueError:
            dep_target = None

    # Resolve return flight:
    # 1) explicit ?return_flight_id= wins
    # 2) else if ?return=YYYY-MM-DD on the query string, pick cheapest inventory
    #    on the reciprocal route (dest -> origin) for that date (year-agnostic)
    # 3) else if flight.return_date is set, pick cheapest reciprocal on that date
    # If the requested return is earlier than the departure, refuse to pair —
    # an inverted-date itinerary is not valid.
    return_flight = None
    rf_id = request.args.get('return_flight_id', type=int)
    ret_d = None
    ret_invalid = False
    if rf_id:
        return_flight = db.session.get(Flight, rf_id)
    else:
        ret_str = request.args.get('return', '')
        if ret_str:
            try:
                ret_d = datetime.strptime(ret_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if dep_target and ret_d and ret_d < dep_target:
            ret_invalid = True
            ret_d = None
        if ret_d is None and flight.return_date and not ret_invalid:
            ret_d = flight.return_date
        if ret_d:
            return_flight = Flight.query.filter(
                Flight.origin_id == flight.destination_id,
                Flight.destination_id == flight.origin_id,
                db.func.strftime('%m-%d', Flight.departure_date)
                == f'{ret_d.month:02d}-{ret_d.day:02d}',
            ).order_by(Flight.price).first()

    if dep_target is not None:
        with db.session.no_autoflush:
            _shift_flight_year(flight, dep_target, ret_d)
    if return_flight is not None and ret_d is not None:
        with db.session.no_autoflush:
            _shift_flight_year(return_flight, ret_d, dep_target)

    return render_template('flight_detail.html',
                           flight=flight,
                           reviews=reviews,
                           avg_rating=avg_rating,
                           related=related,
                           booking_sites=booking_sites,
                           return_flight=return_flight)


@app.route('/destination/<slug>')
def destination(slug):
    airport = Airport.query.filter_by(city_slug=slug).first() or abort(404)
    # Flights arriving to this airport
    inbound = Flight.query.filter_by(destination_id=airport.id).order_by(Flight.price).limit(16).all()
    # Flights departing from this airport
    outbound = Flight.query.filter_by(origin_id=airport.id).order_by(Flight.price).limit(16).all()
    return render_template('destination.html',
                           airport=airport,
                           inbound=inbound,
                           outbound=outbound)


@app.route('/hotels')
def hotels():
    dests = Airport.query.filter_by(is_popular=True).all()
    return render_template('hotels.html', destinations=dests)


@app.route('/vacation-rentals')
def vacation_rentals():
    dests = Airport.query.filter_by(is_popular=True).all()
    return render_template('vacation_rentals.html', destinations=dests)


@app.route('/deals')
def deals():
    cheap = Flight.query.filter_by(is_cheapest=True).order_by(Flight.price).limit(24).all()
    if len(cheap) < 24:
        more = Flight.query.order_by(Flight.price).limit(24 - len(cheap)).all()
        cheap.extend(more)
    return render_template('deals.html', flights=cheap)


@app.route('/tools')
def tools():
    return render_template('tools.html')


@app.route('/tools/date-grid')
def date_grid():
    return render_template('date_grid.html')


@app.route('/tools/price-graph')
def price_graph():
    origin_query = request.args.get('from', '')
    dest_query = request.args.get('to', '')
    depart_str = request.args.get('depart', '')
    try:
        months = max(1, min(6, int(request.args.get('months', 2))))
    except ValueError:
        months = 2

    origin, origin_ids = _resolve_airport_ids(origin_query)
    dest, dest_ids = _resolve_airport_ids(dest_query)

    # If no route specified, default to a sensible demo
    if not origin_ids:
        origin = Airport.query.filter_by(iata='JFK').first()
        if origin:
            origin_ids = [origin.id]
    if not dest_ids:
        dest = Airport.query.filter_by(iata='LAX').first()
        if dest:
            dest_ids = [dest.id]

    # Anchor the graph window to the user's intended departure date so the
    # rendered dates match what they searched. Inventory is queried
    # year-agnostically (by month-day) since the canonical seed year may be
    # different from what the user is browsing.
    today = datetime.utcnow().date()
    anchor = None
    if depart_str:
        try:
            anchor = datetime.strptime(depart_str, '%Y-%m-%d').date()
        except ValueError:
            anchor = None
    if anchor is None:
        anchor = today

    series = []
    md_min = {}        # (month, day) -> min price across all years for this route
    observed_avg = None
    if origin_ids and dest_ids:
        rows = Flight.query.filter(
            Flight.origin_id.in_(origin_ids),
            Flight.destination_id.in_(dest_ids),
        ).all()
        if rows:
            observed_avg = sum(r.price for r in rows) / len(rows)
            for r in rows:
                key = (r.departure_date.month, r.departure_date.day)
                md_min[key] = min(md_min.get(key, r.price), r.price)

    # Build the daily series in the user's requested year. For days with no
    # seeded inventory on the same month-day, synthesize a deterministic trend
    # anchored on the observed average so the chart still shows ~60+ points.
    if observed_avg is not None:
        total_days = months * 30
        import math
        seed_base = hash((origin_ids[0], dest_ids[0])) & 0xFFFF
        for i in range(total_days):
            current = anchor + timedelta(days=i)
            md = (current.month, current.day)
            if md in md_min:
                series.append({'date': current, 'price': round(md_min[md], 0)})
                continue
            phase = (i + seed_base) % 30
            swing = math.sin(phase / 30.0 * 2 * math.pi) * 0.18
            micro = ((i * 37 + seed_base) % 11) / 100.0 - 0.05  # -5%..+5%
            weekend_boost = 0.06 if current.weekday() in (4, 5) else 0.0
            price = observed_avg * (1.0 + swing + micro + weekend_boost)
            series.append({'date': current, 'price': round(max(40.0, price), 0)})

    if series:
        prices_only = [s['price'] for s in series]
        lowest = min(prices_only)
        highest = max(prices_only)
        average = round(sum(prices_only) / len(prices_only), 0)
    else:
        lowest = highest = average = 0

    return render_template('price_graph.html',
                           origin=origin,
                           destination=dest,
                           origin_iata=origin.iata if origin else origin_query.upper(),
                           dest_iata=dest.iata if dest else dest_query.upper(),
                           depart=anchor.isoformat(),
                           months=months,
                           series=series,
                           lowest=lowest,
                           highest=highest,
                           average=average)


@app.route('/tools/price-insights')
def price_insights():
    origin_query = request.args.get('from', '')
    dest_query = request.args.get('to', '')
    origin, origin_ids = _resolve_airport_ids(origin_query)
    dest, dest_ids = _resolve_airport_ids(dest_query)
    insight = None
    if origin_ids and dest_ids:
        rows = Flight.query.filter(
            Flight.origin_id.in_(origin_ids),
            Flight.destination_id.in_(dest_ids),
        ).all()
        if rows:
            prices = [r.price for r in rows]
            insight = {
                'count': len(rows),
                'low': round(min(prices), 0),
                'avg': round(sum(prices)/len(prices), 0),
                'high': round(max(prices), 0),
            }
    return render_template('price_insights.html',
                           origin=origin,
                           destination=dest,
                           origin_iata=origin.iata if origin else origin_query.upper(),
                           dest_iata=dest.iata if dest else dest_query.upper(),
                           insight=insight)


@app.route('/tools/price-tracking')
def price_tracking():
    return render_template('price_tracking.html')


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    results_flights = []
    results_airports = []

    if q:
        # Try to parse "origin to destination" patterns
        import re as _re
        route_match = _re.split(r'\s+to\s+|\s*->\s*|\s*→\s*|\s*–\s+', q, maxsplit=1, flags=_re.IGNORECASE)

        if len(route_match) == 2:
            # Route search: e.g. "SFO to London", "Chicago -> Barcelona"
            origin_q = route_match[0].strip()
            dest_q = route_match[1].strip()
            origin_ql = f"%{origin_q}%"
            dest_ql = f"%{dest_q}%"

            origin_airports = Airport.query.filter(
                or_(
                    Airport.city.ilike(origin_ql),
                    Airport.iata.ilike(origin_ql),
                    Airport.country.ilike(origin_ql),
                    Airport.name.ilike(origin_ql),
                )
            ).all()
            dest_airports = Airport.query.filter(
                or_(
                    Airport.city.ilike(dest_ql),
                    Airport.iata.ilike(dest_ql),
                    Airport.country.ilike(dest_ql),
                    Airport.name.ilike(dest_ql),
                )
            ).all()

            results_airports = list({a.id: a for a in origin_airports + dest_airports}.values())

            origin_ids = [a.id for a in origin_airports]
            dest_ids = [a.id for a in dest_airports]

            if origin_ids and dest_ids:
                # Best case: match flights from origin to destination
                results_flights = Flight.query.filter(
                    Flight.origin_id.in_(origin_ids),
                    Flight.destination_id.in_(dest_ids),
                ).limit(30).all()
                # If no exact route matches, also try reverse and individual
                if not results_flights:
                    results_flights = Flight.query.filter(
                        or_(
                            Flight.origin_id.in_(origin_ids),
                            Flight.destination_id.in_(dest_ids),
                        )
                    ).limit(20).all()
            elif origin_ids:
                results_flights = Flight.query.filter(
                    Flight.origin_id.in_(origin_ids)
                ).limit(20).all()
            elif dest_ids:
                results_flights = Flight.query.filter(
                    Flight.destination_id.in_(dest_ids)
                ).limit(20).all()
        else:
            # Single-term search (original behaviour)
            ql = f"%{q}%"
            results_airports = Airport.query.filter(
                or_(
                    Airport.city.ilike(ql),
                    Airport.iata.ilike(ql),
                    Airport.country.ilike(ql),
                    Airport.name.ilike(ql),
                )
            ).limit(20).all()
            airport_ids = [a.id for a in results_airports]
            if airport_ids:
                results_flights = Flight.query.filter(
                    or_(
                        Flight.origin_id.in_(airport_ids),
                        Flight.destination_id.in_(airport_ids),
                    )
                ).limit(20).all()
            else:
                results_flights = Flight.query.filter(
                    or_(
                        Flight.airline.ilike(ql),
                        Flight.flight_number.ilike(ql),
                    )
                ).limit(20).all()

    return render_template('search.html',
                           q=q,
                           airports=results_airports,
                           flights=results_flights)


# ============================================================
# AUTH
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            flash('Welcome back!', 'success')
            return redirect(request.args.get('next') or url_for('account'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()

        if not email or not password or len(password) < 6:
            flash('Email and a password of at least 6 characters are required.', 'error')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return render_template('register.html')

        user = User(
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
            first_name=first_name,
            last_name=last_name,
        )
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        flash('Your Google Flights account is ready. Happy travels!', 'success')
        return redirect(url_for('account'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('index'))


# ============================================================
# ACCOUNT
# ============================================================

@app.route('/account')
@login_required
def account():
    bookings = current_user.bookings.order_by(Booking.booked_at.desc()).all()
    tracked = current_user.tracked.order_by(TrackedFlight.added_at.desc()).all()
    alerts = current_user.alerts.order_by(PriceAlert.created_at.desc()).all()
    saved = current_user.saved_searches.order_by(SavedSearch.created_at.desc()).all()
    return render_template('account.html',
                           bookings=bookings,
                           tracked=tracked,
                           alerts=alerts,
                           saved_searches=saved)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', '').strip()
        current_user.last_name = request.form.get('last_name', '').strip()
        current_user.phone = request.form.get('phone', '').strip()
        current_user.address = request.form.get('address', '').strip()
        current_user.city = request.form.get('city', '').strip()
        current_user.country = request.form.get('country', '').strip()
        current_user.passport_number = request.form.get('passport_number', '').strip()
        current_user.frequent_flyer = request.form.get('frequent_flyer', '').strip()
        dob = request.form.get('date_of_birth', '').strip()
        if dob:
            try:
                current_user.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
            except ValueError:
                pass
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('account'))
    return render_template('account_edit.html')


@app.route('/account/password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if not bcrypt.check_password_hash(current_user.password_hash, current):
            flash('Current password incorrect.', 'error')
        elif len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'error')
        elif new_pw != confirm:
            flash('New password confirmation does not match.', 'error')
        else:
            current_user.password_hash = bcrypt.generate_password_hash(new_pw).decode('utf-8')
            db.session.commit()
            flash('Password changed.', 'success')
            return redirect(url_for('account'))
    return render_template('change_password.html')


@app.route('/account/delete', methods=['POST'])
@login_required
def delete_account():
    u = db.session.get(User, current_user.id)
    logout_user()
    db.session.delete(u)
    db.session.commit()
    flash('Your account has been deleted.', 'info')
    return redirect(url_for('index'))


# ============================================================
# CART (BAG) + CHECKOUT
# ============================================================

@app.route('/bag')
@login_required
def bag():
    items = current_user.cart_items.order_by(CartItem.added_at.desc()).all()
    subtotal = sum(i.line_total for i in items)
    taxes = round(subtotal * 0.14, 2)
    total = round(subtotal + taxes, 2)
    return render_template('bag.html',
                           items=items,
                           subtotal=subtotal,
                           taxes=taxes,
                           total=total)


@app.route('/api/cart/add', methods=['POST'])
@csrf.exempt
@login_required
def api_cart_add():
    data = request.get_json(silent=True) or {}
    flight_id = int(data.get('flight_id', 0))
    passengers = int(data.get('passengers', 1))
    cabin = data.get('cabin_class', 'Economy')
    return_id = data.get('return_flight_id')

    flight = db.session.get(Flight, flight_id)
    if not flight:
        return jsonify({'success': False, 'message': 'Flight not found'}), 404

    existing = current_user.cart_items.filter_by(flight_id=flight_id).first()
    if existing:
        existing.passengers = passengers
        existing.cabin_class = cabin
    else:
        item = CartItem(
            user_id=current_user.id,
            flight_id=flight_id,
            passengers=passengers,
            cabin_class=cabin,
            return_flight_id=int(return_id) if return_id else None,
        )
        db.session.add(item)
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Added {flight.airline} {flight.flight_number} to your bag',
        'cart_count': current_user.cart_items.count(),
    })


@app.route('/api/cart/update', methods=['POST'])
@csrf.exempt
@login_required
def api_cart_update():
    data = request.get_json(silent=True) or {}
    item_id = int(data.get('item_id', 0))
    passengers = int(data.get('passengers', 1))
    item = db.session.get(CartItem, item_id)
    if not item or item.user_id != current_user.id:
        return jsonify({'success': False}), 404
    item.passengers = max(1, passengers)
    db.session.commit()
    return jsonify({'success': True,
                    'line_total': item.line_total,
                    'cart_count': current_user.cart_items.count()})


@app.route('/api/cart/remove', methods=['POST'])
@csrf.exempt
@login_required
def api_cart_remove():
    data = request.get_json(silent=True) or {}
    item_id = int(data.get('item_id', 0))
    item = db.session.get(CartItem, item_id)
    if not item or item.user_id != current_user.id:
        return jsonify({'success': False}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True, 'cart_count': current_user.cart_items.count()})


# ------ Form-based cart routes (for browser agents) ------

@app.route('/cart/add/<int:flight_id>', methods=['POST'])
@login_required
def cart_add_form(flight_id):
    flight = db.session.get(Flight, flight_id) or abort(404)
    passengers = int(request.form.get('passengers', 1) or 1)
    cabin = request.form.get('cabin_class', 'Economy')
    return_id = request.form.get('return_flight_id')
    existing = current_user.cart_items.filter_by(flight_id=flight_id).first()
    if existing:
        existing.passengers = passengers
        existing.cabin_class = cabin
    else:
        item = CartItem(
            user_id=current_user.id,
            flight_id=flight_id,
            passengers=passengers,
            cabin_class=cabin,
            return_flight_id=int(return_id) if return_id else None,
        )
        db.session.add(item)
    db.session.commit()
    flash(f'{flight.airline} {flight.flight_number} added to your bag.', 'success')
    return redirect(url_for('bag'))


@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def cart_remove_form(item_id):
    item = db.session.get(CartItem, item_id)
    if item and item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Flight removed from bag.', 'info')
    return redirect(url_for('bag'))


@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def cart_update_form(item_id):
    item = db.session.get(CartItem, item_id)
    if not item or item.user_id != current_user.id:
        abort(404)
    passengers = int(request.form.get('passengers', item.passengers) or item.passengers)
    cabin = request.form.get('cabin_class', item.cabin_class)
    item.passengers = max(1, passengers)
    item.cabin_class = cabin
    db.session.commit()
    flash('Bag updated.', 'success')
    return redirect(url_for('bag'))


# ------ Form-based track route ------

@app.route('/track/add/<int:flight_id>', methods=['POST'])
@login_required
def track_add_form(flight_id):
    flight = db.session.get(Flight, flight_id) or abort(404)
    existing = current_user.tracked.filter_by(flight_id=flight_id).first()
    if not existing:
        target = float(request.form.get('target_price', flight.price * 0.9) or flight.price * 0.9)
        db.session.add(TrackedFlight(
            user_id=current_user.id,
            flight_id=flight_id,
            starting_price=flight.price,
            target_price=target,
        ))
        db.session.commit()
        flash(f'{flight.airline} {flight.flight_number} is now being tracked.', 'success')
    else:
        flash('Flight already tracked.', 'info')
    return redirect(url_for('flight_detail', flight_id=flight_id))


@app.route('/track/remove/<int:flight_id>', methods=['POST'])
@login_required
def track_remove_form(flight_id):
    existing = current_user.tracked.filter_by(flight_id=flight_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Stopped tracking flight.', 'info')
    return redirect(url_for('tracked_flights'))


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    items = current_user.cart_items.all()
    if not items:
        flash('Your bag is empty.', 'info')
        return redirect(url_for('bag'))

    subtotal = sum(i.line_total for i in items)
    taxes = round(subtotal * 0.14, 2)
    total = round(subtotal + taxes, 2)

    if request.method == 'POST':
        contact_email = request.form.get('contact_email', current_user.email)
        contact_phone = request.form.get('contact_phone', '')
        passengers_json = []
        for i, ci in enumerate(items):
            for p in range(ci.passengers):
                passengers_json.append({
                    'first_name': request.form.get(f'pax_first_{i}_{p}', current_user.first_name or 'Guest'),
                    'last_name': request.form.get(f'pax_last_{i}_{p}', current_user.last_name or 'Traveler'),
                })

        # Support saved payment method selection
        saved_pm_id = request.form.get('saved_payment_id')
        if saved_pm_id:
            pm = db.session.get(PaymentMethod, int(saved_pm_id))
            if pm and pm.user_id == current_user.id:
                card_last4 = pm.last4
                card_brand = pm.card_type
            else:
                card_last4 = request.form.get('card_number', '0000')[-4:] or '0000'
                card_brand = 'Visa'
        else:
            card_last4 = request.form.get('card_number', '0000')[-4:] or '0000'
            card_brand = 'Visa'

        booking = Booking(
            user_id=current_user.id,
            pnr=make_pnr(),
            status='confirmed',
            trip_type='round' if any(i.return_flight_id for i in items) else 'one-way',
            total_amount=total,
            taxes_fees=taxes,
            currency='USD',
            passenger_names_json=json.dumps(passengers_json),
            contact_email=contact_email,
            contact_phone=contact_phone,
            payment_last4=card_last4,
            payment_brand=card_brand,
        )
        db.session.add(booking)
        db.session.flush()

        for ci in items:
            bi = BookingItem(
                booking_id=booking.id,
                flight_id=ci.flight_id,
                leg='outbound',
                passengers=ci.passengers,
                cabin_class=ci.cabin_class,
                price=ci.flight.price if ci.flight else 0,
                seat=random.choice(['12A', '14C', '22F', '9D', '31B']),
            )
            db.session.add(bi)
            if ci.return_flight_id:
                bi2 = BookingItem(
                    booking_id=booking.id,
                    flight_id=ci.return_flight_id,
                    leg='return',
                    passengers=ci.passengers,
                    cabin_class=ci.cabin_class,
                    price=ci.return_flight.price if ci.return_flight else 0,
                    seat=random.choice(['12A', '14C', '22F', '9D', '31B']),
                )
                db.session.add(bi2)
            db.session.delete(ci)
        db.session.commit()
        flash(f'Booking confirmed — PNR {booking.pnr}', 'success')
        return redirect(url_for('booking_confirmation', booking_id=booking.id))

    saved_payments = current_user.payment_methods.order_by(
        PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc()).all()
    return render_template('checkout.html',
                           items=items,
                           subtotal=subtotal,
                           taxes=taxes,
                           total=total,
                           saved_payments=saved_payments)


@app.route('/booking/<int:booking_id>')
@login_required
def booking_detail(booking_id):
    b = db.session.get(Booking, booking_id) or abort(404)
    if b.user_id != current_user.id:
        abort(403)
    return render_template('booking_detail.html', booking=b)


@app.route('/booking/<int:booking_id>/confirmation')
@login_required
def booking_confirmation(booking_id):
    b = db.session.get(Booking, booking_id) or abort(404)
    if b.user_id != current_user.id:
        abort(403)
    return render_template('booking_confirmation.html', booking=b)


@app.route('/booking/<int:booking_id>/cancel', methods=['POST'])
@login_required
def booking_cancel(booking_id):
    b = db.session.get(Booking, booking_id) or abort(404)
    if b.user_id != current_user.id:
        abort(403)
    if b.status == 'confirmed':
        b.status = 'cancelled'
        b.cancelled_at = datetime.utcnow()
        db.session.commit()
        flash(f'Booking {b.pnr} cancelled.', 'info')
    return redirect(url_for('account'))


@app.route('/booking/<int:booking_id>/rebook', methods=['POST'])
@login_required
def booking_rebook(booking_id):
    b = db.session.get(Booking, booking_id) or abort(404)
    if b.user_id != current_user.id:
        abort(403)
    for bi in b.items:
        existing = current_user.cart_items.filter_by(flight_id=bi.flight_id).first()
        if not existing:
            db.session.add(CartItem(
                user_id=current_user.id,
                flight_id=bi.flight_id,
                passengers=bi.passengers,
                cabin_class=bi.cabin_class,
            ))
    db.session.commit()
    flash('Flights added back to your bag.', 'success')
    return redirect(url_for('bag'))


# ============================================================
# TRACKED FLIGHTS / WISHLIST
# ============================================================

@app.route('/api/track/toggle', methods=['POST'])
@csrf.exempt
@login_required
def api_track_toggle():
    data = request.get_json(silent=True) or {}
    flight_id = int(data.get('flight_id', 0))
    existing = current_user.tracked.filter_by(flight_id=flight_id).first()
    if existing:
        db.session.delete(existing)
        tracked = False
    else:
        flight = db.session.get(Flight, flight_id)
        if not flight:
            return jsonify({'success': False}), 404
        db.session.add(TrackedFlight(
            user_id=current_user.id,
            flight_id=flight_id,
            starting_price=flight.price,
            target_price=flight.price * 0.9,
        ))
        tracked = True
    db.session.commit()
    return jsonify({
        'success': True,
        'tracked': tracked,
        'tracked_count': current_user.tracked.count(),
    })


@app.route('/tracked')
@login_required
def tracked_flights():
    items = current_user.tracked.order_by(TrackedFlight.added_at.desc()).all()
    return render_template('tracked.html', items=items)


@app.route('/tracked/remove/<int:item_id>', methods=['POST'])
@login_required
def tracked_remove(item_id):
    item = db.session.get(TrackedFlight, item_id)
    if item and item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Removed from tracked flights.', 'info')
    return redirect(url_for('tracked_flights'))


# ============================================================
# PRICE ALERTS
# ============================================================

@app.route('/alerts', methods=['GET', 'POST'])
@login_required
def price_alerts():
    if request.method == 'POST':
        origin_iata = request.form.get('origin_iata', '').upper().strip()
        dest_iata = request.form.get('destination_iata', '').upper().strip()
        threshold = float(request.form.get('threshold_price', 0) or 0)
        if origin_iata and dest_iata:
            db.session.add(PriceAlert(
                user_id=current_user.id,
                origin_iata=origin_iata,
                destination_iata=dest_iata,
                threshold_price=threshold,
            ))
            db.session.commit()
            flash(f'Alert created for {origin_iata} - {dest_iata}', 'success')
        return redirect(url_for('price_alerts'))
    items = current_user.alerts.order_by(PriceAlert.created_at.desc()).all()
    return render_template('alerts.html', alerts=items)


@app.route('/alerts/<int:alert_id>/delete', methods=['POST'])
@login_required
def alert_delete(alert_id):
    a = db.session.get(PriceAlert, alert_id)
    if a and a.user_id == current_user.id:
        db.session.delete(a)
        db.session.commit()
        flash('Alert removed.', 'info')
    return redirect(url_for('price_alerts'))


# ============================================================
# SAVED SEARCHES
# ============================================================

@app.route('/saved-searches', methods=['GET', 'POST'])
@login_required
def saved_searches():
    if request.method == 'POST':
        label = request.form.get('label', 'My search')
        db.session.add(SavedSearch(
            user_id=current_user.id,
            label=label,
            origin_iata=request.form.get('origin_iata', '').upper(),
            destination_iata=request.form.get('destination_iata', '').upper(),
            passengers=int(request.form.get('passengers', 1) or 1),
            cabin_class=request.form.get('cabin_class', 'Economy'),
        ))
        db.session.commit()
        flash('Search saved.', 'success')
        return redirect(url_for('saved_searches'))
    items = current_user.saved_searches.order_by(SavedSearch.created_at.desc()).all()
    return render_template('saved_searches.html', searches=items)


@app.route('/saved-searches/<int:search_id>/delete', methods=['POST'])
@login_required
def saved_search_delete(search_id):
    s = db.session.get(SavedSearch, search_id)
    if s and s.user_id == current_user.id:
        db.session.delete(s)
        db.session.commit()
        flash('Saved search removed.', 'info')
    return redirect(url_for('saved_searches'))


# ============================================================
# PAYMENT METHODS
# ============================================================

@app.route('/payment-methods')
@login_required
def payment_methods():
    methods = current_user.payment_methods.order_by(
        PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc()).all()
    return render_template('payment_methods.html', methods=methods)


@app.route('/payment-methods/add', methods=['GET', 'POST'])
@login_required
def payment_method_add():
    if request.method == 'POST':
        card_type = request.form.get('card_type', 'Visa').strip()
        card_number = request.form.get('card_number', '').replace(' ', '')
        last4 = card_number[-4:] if len(card_number) >= 4 else '0000'
        exp_month = int(request.form.get('exp_month', 12) or 12)
        exp_year = int(request.form.get('exp_year', 2028) or 2028)
        cardholder_name = request.form.get('cardholder_name', current_user.full_name).strip()
        is_default = bool(request.form.get('is_default'))
        if is_default:
            # un-default others
            for m in current_user.payment_methods:
                m.is_default = False
        elif current_user.payment_methods.count() == 0:
            is_default = True
        pm = PaymentMethod(
            user_id=current_user.id,
            card_type=card_type,
            last4=last4,
            exp_month=exp_month,
            exp_year=exp_year,
            cardholder_name=cardholder_name,
            is_default=is_default,
        )
        db.session.add(pm)
        db.session.commit()
        flash(f'{card_type} ending {last4} added.', 'success')
        return redirect(url_for('payment_methods'))
    return render_template('payment_method_add.html')


@app.route('/payment-methods/<int:pm_id>/delete', methods=['POST'])
@login_required
def payment_method_delete(pm_id):
    pm = db.session.get(PaymentMethod, pm_id)
    if pm and pm.user_id == current_user.id:
        db.session.delete(pm)
        db.session.commit()
        flash('Card removed.', 'info')
    return redirect(url_for('payment_methods'))


@app.route('/payment-methods/<int:pm_id>/set-default', methods=['POST'])
@login_required
def payment_method_set_default(pm_id):
    pm = db.session.get(PaymentMethod, pm_id)
    if pm and pm.user_id == current_user.id:
        for m in current_user.payment_methods:
            m.is_default = False
        pm.is_default = True
        db.session.commit()
        flash(f'{pm.card_type} ending {pm.last4} set as default.', 'success')
    return redirect(url_for('payment_methods'))


# ============================================================
# REVIEWS
# ============================================================

@app.route('/flight/<int:flight_id>/review', methods=['POST'])
@login_required
def review_submit(flight_id):
    flight = db.session.get(Flight, flight_id) or abort(404)
    rating = int(request.form.get('rating', 5))
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()
    punctuality = int(request.form.get('punctuality', 5))
    comfort = int(request.form.get('comfort', 5))
    service = int(request.form.get('service', 5))
    r = Review(
        user_id=current_user.id,
        flight_id=flight_id,
        rating=max(1, min(5, rating)),
        title=title,
        body=body,
        punctuality=punctuality,
        comfort=comfort,
        service=service,
    )
    db.session.add(r)
    db.session.commit()
    flash('Thanks for your review!', 'success')
    return redirect(url_for('flight_detail', flight_id=flight_id))


@app.route('/review/<int:review_id>/delete', methods=['POST'])
@login_required
def review_delete(review_id):
    r = db.session.get(Review, review_id)
    if r and r.user_id == current_user.id:
        fid = r.flight_id
        db.session.delete(r)
        db.session.commit()
        flash('Review removed.', 'info')
        return redirect(url_for('flight_detail', flight_id=fid))
    return redirect(url_for('index'))


# ============================================================
# JSON API
# ============================================================

@app.route('/api/airports')
def api_airports():
    q = request.args.get('q', '').strip()
    query = Airport.query
    if q:
        ql = f"%{q}%"
        query = query.filter(or_(
            Airport.city.ilike(ql),
            Airport.iata.ilike(ql),
            Airport.name.ilike(ql),
        ))
    items = query.limit(20).all()
    return jsonify([{
        'iata': a.iata,
        'city': a.city,
        'country': a.country,
        'name': a.name,
    } for a in items])


@app.route('/api/flights/<origin>/<destination>')
def api_flights_route(origin, destination):
    o = Airport.query.filter_by(iata=origin.upper()).first()
    d = Airport.query.filter_by(iata=destination.upper()).first()
    if not o or not d:
        return jsonify([])
    flights = Flight.query.filter_by(origin_id=o.id, destination_id=d.id).order_by(Flight.price).limit(20).all()
    return jsonify([{
        'id': f.id,
        'airline': f.airline,
        'flight_number': f.flight_number,
        'price': f.price,
        'duration': f.duration_str,
        'stops': f.stops_str,
        'departure_time': f.departure_time,
        'arrival_time': f.arrival_time,
    } for f in flights])


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ============================================================
# SEED DATA
# ============================================================

def seed_database():
    from seed_data import seed_all
    seed_all(db, Airport, Flight)


def seed_benchmark_users():
    """Seed 4 benchmark users with payment methods, bookings, tracked flights and alerts.
    Idempotent — checks if alice already exists before creating."""
    if User.query.filter_by(email='alice.j@test.com').first():
        return  # already seeded

    def _make_user(email, pw, first, last, phone, passport, ff, dob_str):
        u = User(
            email=email,
            password_hash=bcrypt.generate_password_hash(pw).decode('utf-8'),
            first_name=first,
            last_name=last,
            phone=phone,
            passport_number=passport,
            frequent_flyer=ff,
        )
        if dob_str:
            u.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
        db.session.add(u)
        db.session.flush()
        return u

    def _add_pm(user, card_type, last4, exp_m, exp_y, name, is_default=False):
        pm = PaymentMethod(
            user_id=user.id,
            card_type=card_type,
            last4=last4,
            exp_month=exp_m,
            exp_year=exp_y,
            cardholder_name=name,
            is_default=is_default,
        )
        db.session.add(pm)
        return pm

    def _get_flight(origin_iata, dest_iata, stops_filter=None, prefer_nonstop=True):
        o = Airport.query.filter_by(iata=origin_iata).first()
        d = Airport.query.filter_by(iata=dest_iata).first()
        if not o or not d:
            return None
        q = Flight.query.filter_by(origin_id=o.id, destination_id=d.id)
        if stops_filter is not None:
            q = q.filter(Flight.stops == stops_filter)
        elif prefer_nonstop:
            nonstop = q.filter(Flight.stops == 0).first()
            if nonstop:
                return nonstop
        return q.order_by(Flight.price).first()

    def _make_booking(user, flight, cabin='Economy', passengers=1,
                      status='confirmed', card_last4='4242', card_brand='Visa'):
        if not flight:
            return None
        pnr = make_pnr()
        price = flight.price * passengers
        taxes = round(price * 0.14, 2)
        total = round(price + taxes, 2)
        pax = [{'first_name': user.first_name, 'last_name': user.last_name}
               for _ in range(passengers)]
        b = Booking(
            user_id=user.id,
            pnr=pnr,
            status=status,
            trip_type='one-way',
            total_amount=total,
            taxes_fees=taxes,
            currency='USD',
            passenger_names_json=json.dumps(pax),
            contact_email=user.email,
            contact_phone=user.phone or '',
            payment_last4=card_last4,
            payment_brand=card_brand,
        )
        if status == 'cancelled':
            b.cancelled_at = datetime.utcnow() - timedelta(days=random.randint(1, 10))
        db.session.add(b)
        db.session.flush()
        bi = BookingItem(
            booking_id=b.id,
            flight_id=flight.id,
            leg='outbound',
            passengers=passengers,
            cabin_class=cabin,
            price=flight.price,
            seat=random.choice(['12A', '14C', '22F', '9D', '31B']),
        )
        db.session.add(bi)
        return b

    # ---- Alice Johnson — frequent flyer, prefers nonstop, Business when possible ----
    alice = _make_user(
        'alice.j@test.com', 'TestPass123!',
        'Alice', 'Johnson', '+1-212-555-0101',
        'US123456789', 'AA-FF-987654321', '1985-03-15')
    _add_pm(alice, 'Visa', '4321', 12, 2028, 'Alice Johnson', is_default=True)
    _add_pm(alice, 'Amex', '7890', 6, 2027, 'Alice Johnson')

    f1 = _get_flight('JFK', 'LHR', prefer_nonstop=True)
    f2 = _get_flight('JFK', 'CDG', prefer_nonstop=True)
    f3 = _get_flight('JFK', 'HND', prefer_nonstop=True)
    _make_booking(alice, f1, 'Business', 1, 'confirmed', '4321', 'Visa')
    _make_booking(alice, f2, 'Economy', 1, 'confirmed', '4321', 'Visa')
    _make_booking(alice, f3, 'Business', 1, 'cancelled', '7890', 'Amex')

    # tracked flights
    if f1:
        db.session.add(TrackedFlight(user_id=alice.id, flight_id=f1.id,
                                      starting_price=f1.price, target_price=round(f1.price * 0.85, 2)))
    # Add JFK->LAX tracked flight for T08 task (Alice should have 2 tracked flights: LHR to keep, LAX to remove)
    f_lax = _get_flight('JFK', 'LAX')
    if f_lax:
        db.session.add(TrackedFlight(user_id=alice.id, flight_id=f_lax.id,
                                      starting_price=f_lax.price, target_price=round(f_lax.price * 0.85, 2)))
    # price alerts
    db.session.add(PriceAlert(user_id=alice.id, origin_iata='JFK', destination_iata='LHR',
                               threshold_price=400.0, active=True))
    db.session.add(PriceAlert(user_id=alice.id, origin_iata='JFK', destination_iata='CDG',
                               threshold_price=420.0, active=True))

    # ---- Bob Chen — budget traveller, accepts 1-stop, Economy ----
    bob = _make_user(
        'bob.c@test.com', 'TestPass123!',
        'Bob', 'Chen', '+1-415-555-0202',
        'CN987654321', '', '1990-07-22')
    _add_pm(bob, 'Mastercard', '5678', 9, 2026, 'Bob Chen', is_default=True)
    _add_pm(bob, 'Visa', '1234', 3, 2029, 'Bob Chen')
    _add_pm(bob, 'Visa', '9999', 11, 2027, 'Bob Chen')

    f4 = _get_flight('SFO', 'LHR')
    f5 = _get_flight('LAX', 'HND')
    f6 = _get_flight('SFO', 'CDG')
    _make_booking(bob, f4, 'Economy', 1, 'confirmed', '5678', 'Mastercard')
    _make_booking(bob, f5, 'Economy', 1, 'confirmed', '1234', 'Visa')
    _make_booking(bob, f6, 'Economy', 1, 'cancelled', '5678', 'Mastercard')

    if f4:
        db.session.add(TrackedFlight(user_id=bob.id, flight_id=f4.id,
                                      starting_price=f4.price, target_price=round(f4.price * 0.80, 2)))
    db.session.add(PriceAlert(user_id=bob.id, origin_iata='SFO', destination_iata='LHR',
                               threshold_price=500.0, active=True))

    # ---- Carol Davis — family traveller, multi-pax, Economy/Premium ----
    carol = _make_user(
        'carol.d@test.com', 'TestPass123!',
        'Carol', 'Davis', '+1-312-555-0303',
        'US998877665', 'UA-FF-112233445', '1978-11-04')
    _add_pm(carol, 'Visa', '2468', 5, 2028, 'Carol Davis', is_default=True)
    _add_pm(carol, 'Mastercard', '1357', 8, 2026, 'Carol Davis')

    f7 = _get_flight('ORD', 'FCO')
    f8 = _get_flight('ORD', 'LHR')
    f9 = _get_flight('ORD', 'CDG')
    _make_booking(carol, f7, 'Economy', 3, 'confirmed', '2468', 'Visa')
    _make_booking(carol, f8, 'Economy', 4, 'confirmed', '2468', 'Visa')
    _make_booking(carol, f9, 'Economy', 2, 'cancelled', '1357', 'Mastercard')

    if f7:
        db.session.add(TrackedFlight(user_id=carol.id, flight_id=f7.id,
                                      starting_price=f7.price, target_price=round(f7.price * 0.88, 2)))
    if f8:
        db.session.add(TrackedFlight(user_id=carol.id, flight_id=f8.id,
                                      starting_price=f8.price, target_price=round(f8.price * 0.90, 2)))
    db.session.add(PriceAlert(user_id=carol.id, origin_iata='ORD', destination_iata='FCO',
                               threshold_price=450.0, active=True))

    # ---- David Kim — business traveller, Business/First, short booking windows ----
    david = _make_user(
        'david.k@test.com', 'TestPass123!',
        'David', 'Kim', '+1-202-555-0404',
        'KR112233445', 'DL-FF-556677889', '1982-05-30')
    _add_pm(david, 'Amex', '6543', 2, 2030, 'David Kim', is_default=True)
    _add_pm(david, 'Visa', '8765', 7, 2028, 'David Kim')
    _add_pm(david, 'Mastercard', '3210', 10, 2029, 'David Kim')

    f10 = _get_flight('JFK', 'DXB', prefer_nonstop=True)
    f11 = _get_flight('JFK', 'CDG', prefer_nonstop=True)
    f12 = _get_flight('BOS', 'BCN')
    _make_booking(david, f10, 'Business', 1, 'confirmed', '6543', 'Amex')
    _make_booking(david, f11, 'Business', 1, 'confirmed', '6543', 'Amex')
    _make_booking(david, f12, 'Economy', 1, 'cancelled', '8765', 'Visa')

    if f10:
        db.session.add(TrackedFlight(user_id=david.id, flight_id=f10.id,
                                      starting_price=f10.price, target_price=round(f10.price * 0.85, 2)))
    db.session.add(PriceAlert(user_id=david.id, origin_iata='JFK', destination_iata='DXB',
                               threshold_price=400.0, active=True))
    db.session.add(PriceAlert(user_id=david.id, origin_iata='JFK', destination_iata='CDG',
                               threshold_price=450.0, active=True))

    db.session.commit()
    print('Benchmark users seeded: alice, bob, carol, david')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if Airport.query.count() == 0:
            seed_database()
        seed_benchmark_users()
    port = int(os.environ.get('PORT', 28849))
    app.run(host='0.0.0.0', port=port, debug=False)
