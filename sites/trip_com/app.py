#!/usr/bin/env python3
"""Trip.com mirror — Flask application.

Mirrors https://us.trip.com/ (US market, USD): hotel search with filters and
sorting, hotel detail with room rates, hotel booking chain with price breakdown,
Trip Coins and promo codes; flight search with airline/stop filters, outbound +
return selection, passenger booking; attractions & tours listing with package
booking; account area (profile, my bookings, wishlist, coupons, coins); deals
page with promo codes; travel guides and site-wide scored search.

Data comes from the tracked source_data_*.json snapshots captured on
2026-09-27; the SQLite seed is materialized
deterministically at image build time.
"""
import json
import math
import os
import re
import secrets
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from markupsafe import Markup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("TRIP_COM_SECRET_KEY") or "webharbor-trip_com-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'TRIP_COM_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'trip_com.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'sign_in'
login_manager.login_message = 'Please sign in to access your account.'
csrf = CSRFProtect(app)

# The mirror is a snapshot of the upstream site taken on 2026-09-27.
MIRROR_TODAY = date(2026, 9, 27)
# bcrypt hash of 'TestPass123!' (frozen so the SQLite seed is byte-reproducible
# on every build; PYTHONHASHSEED=0 keeps the rest deterministic)
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$LV/cxTF9BjJ3r0X0yoIqne1gRSOzJYWD.44ZgGwnMcEk/Lww.M/0W')
# Search window: bookable dates (matches the captured snapshot window).
DATE_MIN = date(2026, 10, 1)
DATE_MAX = date(2026, 11, 30)
TRIP_COINS_PCT = 0.01          # upstream: ~1% of prepay total in Trip Coins
DEFAULT_CHECKIN = date(2026, 10, 4)
DEFAULT_CHECKOUT = date(2026, 10, 5)

STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
              'or', 'is', 'it', 'by', 'with', 'my', 'me', 'us', 'we'}


def parse_date(value, fallback):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return fallback


def parse_guests(*values, default=2):
    """First valid guest count in 1..12 across the given sources."""
    for value in values:
        try:
            guests = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= guests <= 12:
            return guests
    return default


# ------------------------------------------------------------------ models --

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30), default='')
    coins = db.Column(db.Integer, default=0)
    created_at = db.Column(db.Date, default=MIRROR_TODAY)

    @property
    def first_name(self):
        return self.name.split()[0] if self.name else ''


class City(db.Model):
    __tablename__ = 'cities'
    id = db.Column(db.Integer, primary_key=True)       # real upstream cityId
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), nullable=False, unique=True)
    state = db.Column(db.String(40), default='')
    country = db.Column(db.String(40), default='United States')
    image = db.Column(db.String(200), default='')
    blurb = db.Column(db.Text, default='')

    @property
    def display(self):
        return f"{self.name}, {self.state}" if self.state else self.name


class Hotel(db.Model):
    __tablename__ = 'hotels'
    id = db.Column(db.Integer, primary_key=True)       # real upstream hotelId
    city_id = db.Column(db.Integer, db.ForeignKey('cities.id'), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    stars = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=0.0)          # /10 guest score
    reviews_count = db.Column(db.Integer, default=0)
    address = db.Column(db.String(200), default='')
    district = db.Column(db.String(80), default='')
    near = db.Column(db.String(120), default='')
    price = db.Column(db.Float, default=0.0)           # per night, before tax
    total = db.Column(db.Float, default=0.0)           # per night, incl. tax
    img = db.Column(db.String(250), default='')
    amenities = db.Column(db.Text, default='')          # JSON list
    tags = db.Column(db.Text, default='')              # JSON list of review tags
    impression = db.Column(db.String(200), default='')  # top review quote
    bookable = db.Column(db.Boolean, default=False)
    checkin_from = db.Column(db.String(20), default='15:00')
    checkout_by = db.Column(db.String(20), default='11:00')
    description = db.Column(db.Text, default='')

    @property
    def amenity_list(self):
        try:
            return json.loads(self.amenities or '[]')
        except ValueError:
            return []

    @property
    def tag_list(self):
        try:
            return json.loads(self.tags or '[]')
        except ValueError:
            return []

    @property
    def rating_label(self):
        if self.rating >= 9.0:
            return 'Exceptional'
        if self.rating >= 8.5:
            return 'Excellent'
        if self.rating >= 8.0:
            return 'Very good'
        if self.rating >= 7.0:
            return 'Good'
        return 'Pleasant'


class HotelPhoto(db.Model):
    __tablename__ = 'hotel_photos'
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    path = db.Column(db.String(250), nullable=False)


class RoomRate(db.Model):
    __tablename__ = 'room_rates'
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    bed = db.Column(db.String(80), default='')
    view = db.Column(db.String(80), default='')
    size_sqft = db.Column(db.Integer, default=0)
    capacity = db.Column(db.Integer, default=2)
    price = db.Column(db.Float, nullable=False)        # per night before tax
    total = db.Column(db.Float, nullable=False)        # per night incl. tax
    breakfast = db.Column(db.Boolean, default=False)
    free_cancel = db.Column(db.Boolean, default=True)
    prepay = db.Column(db.Boolean, default=True)
    note = db.Column(db.String(160), default='')


class HotelReview(db.Model):
    __tablename__ = 'hotel_reviews'
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    rating = db.Column(db.Float, default=8.0)
    text = db.Column(db.Text, default='')
    traveller = db.Column(db.String(40), default='Traveller')
    review_date = db.Column(db.String(20), default='Sep 2026')


class HotelBooking(db.Model):
    __tablename__ = 'hotel_bookings'
    ref = db.Column(db.String(14), primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room_rates.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    guest_first = db.Column(db.String(60), default='')
    guest_last = db.Column(db.String(60), default='')
    email = db.Column(db.String(120), default='')
    phone = db.Column(db.String(30), default='')
    checkin = db.Column(db.Date, nullable=False)
    checkout = db.Column(db.Date, nullable=False)
    rooms = db.Column(db.Integer, default=1)
    adults = db.Column(db.Integer, default=2)
    children = db.Column(db.Integer, default=0)
    nightly = db.Column(db.Float, default=0.0)
    taxes = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    coins = db.Column(db.Integer, default=0)
    promo_code = db.Column(db.String(20), default='')
    status = db.Column(db.String(20), default='confirmed')
    created_at = db.Column(db.Date, default=MIRROR_TODAY)


class Airport(db.Model):
    __tablename__ = 'airports'
    code = db.Column(db.String(8), primary_key=True)
    name = db.Column(db.String(90), nullable=False)
    city = db.Column(db.String(60), nullable=False)


class FlightRoute(db.Model):
    __tablename__ = 'flight_routes'
    id = db.Column(db.Integer, primary_key=True)
    origin_code = db.Column(db.String(8), db.ForeignKey('airports.code'), nullable=False)
    dest_code = db.Column(db.String(8), db.ForeignKey('airports.code'), nullable=False)
    origin_city = db.Column(db.String(60), default='')
    dest_city = db.Column(db.String(60), default='')

    @property
    def origin(self):
        return db.session.get(Airport, self.origin_code)

    @property
    def dest(self):
        return db.session.get(Airport, self.dest_code)


class Flight(db.Model):
    __tablename__ = 'flights'
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('flight_routes.id'), nullable=False)
    leg = db.Column(db.String(4), default='out')        # out | ret
    airline = db.Column(db.String(60), nullable=False)
    flight_no = db.Column(db.String(10), default='')
    dep_time = db.Column(db.String(10), nullable=False)
    dep_terminal = db.Column(db.String(6), default='')
    arr_time = db.Column(db.String(10), nullable=False)
    arr_terminal = db.Column(db.String(6), default='')
    plus1 = db.Column(db.Boolean, default=False)
    duration_min = db.Column(db.Integer, nullable=False)
    stops = db.Column(db.Integer, default=0)
    stopover = db.Column(db.String(60), default='')
    price = db.Column(db.Float, nullable=False)        # one-way incl. taxes
    cabin = db.Column(db.String(20), default='Economy')
    baggage = db.Column(db.String(60), default='Carry-on baggage included')

    @property
    def route(self):
        return db.session.get(FlightRoute, self.route_id)

    @property
    def duration_label(self):
        return f"{self.duration_min // 60}h {self.duration_min % 60:02d}m"

    @property
    def dep_slot(self):
        hour = int(self.dep_time.split(':')[0])
        if hour < 6:
            return 'early'
        if hour < 12:
            return 'morning'
        if hour < 18:
            return 'afternoon'
        return 'evening'


class FlightBooking(db.Model):
    __tablename__ = 'flight_bookings'
    ref = db.Column(db.String(14), primary_key=True)
    outbound_id = db.Column(db.Integer, db.ForeignKey('flights.id'), nullable=False)
    return_id = db.Column(db.Integer, db.ForeignKey('flights.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    passenger_first = db.Column(db.String(60), default='')
    passenger_last = db.Column(db.String(60), default='')
    email = db.Column(db.String(120), default='')
    phone = db.Column(db.String(30), default='')
    cabin = db.Column(db.String(20), default='Economy')
    trip_type = db.Column(db.String(10), default='rt')
    total = db.Column(db.Float, default=0.0)
    promo_code = db.Column(db.String(20), default='')
    status = db.Column(db.String(20), default='confirmed')
    created_at = db.Column(db.Date, default=MIRROR_TODAY)
    departure_date = db.Column(db.Date, nullable=True)
    return_date = db.Column(db.Date, nullable=True)

    @property
    def outbound(self):
        return db.session.get(Flight, self.outbound_id)

    @property
    def inbound(self):
        return db.session.get(Flight, self.return_id) if self.return_id else None

    @property
    def route_label(self):
        out = self.outbound
        if out is None:
            return ''
        route = db.session.get(FlightRoute, out.route_id)
        return f"{route.origin_code} \u2192 {route.dest_code}" if route else ''


class Attraction(db.Model):
    __tablename__ = 'attractions'
    id = db.Column(db.Integer, primary_key=True)       # real upstream product id
    city_slug = db.Column(db.String(60), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(60), default='')
    rating = db.Column(db.Float, default=0.0)
    reviews_count = db.Column(db.Integer, default=0)
    booked_count = db.Column(db.Integer, default=0)
    price_from = db.Column(db.Float, default=0.0)
    price_unit = db.Column(db.String(80), default='per person')
    cancellation = db.Column(db.Text, default='')
    img = db.Column(db.String(250), default='')
    description = db.Column(db.Text, default='')
    highlights = db.Column(db.Text, default='')


class AttractionPackage(db.Model):
    __tablename__ = 'attraction_packages'
    id = db.Column(db.Integer, primary_key=True)
    attraction_id = db.Column(db.Integer, db.ForeignKey('attractions.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    validity = db.Column(db.String(80), default='')


class AttractionBooking(db.Model):
    __tablename__ = 'attraction_bookings'
    ref = db.Column(db.String(14), primary_key=True)
    attraction_id = db.Column(db.Integer, db.ForeignKey('attractions.id'), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('attraction_packages.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    visit_date = db.Column(db.Date, nullable=False)
    guests = db.Column(db.Integer, default=1)
    lead_first = db.Column(db.String(60), default='')
    lead_last = db.Column(db.String(60), default='')
    email = db.Column(db.String(120), default='')
    total = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='confirmed')
    created_at = db.Column(db.Date, default=MIRROR_TODAY)


class WishlistItem(db.Model):
    __tablename__ = 'wishlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)


class Coupon(db.Model):
    __tablename__ = 'coupons'
    code = db.Column(db.String(20), primary_key=True)
    kind = db.Column(db.String(10), nullable=False)    # percent | amount
    value = db.Column(db.Float, nullable=False)
    scope = db.Column(db.String(20), default='all')    # hotels|flights|attractions|all
    min_spend = db.Column(db.Float, default=0.0)
    description = db.Column(db.String(200), default='')
    active = db.Column(db.Boolean, default=True)


class Guide(db.Model):
    __tablename__ = 'guides'
    slug = db.Column(db.String(120), primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(60), default='')
    img = db.Column(db.String(250), default='')
    body = db.Column(db.Text, default='')


# ------------------------------------------------------------------ helpers --

def scored_search(query, rows, fields):
    """Token-overlap scored search (never strict AND)."""
    tokens = [t.lower() for t in re.split(r'\W+', query or '')
              if t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return rows
    results = []
    for row in rows:
        text = ' '.join(getattr(row, f, '') or '' for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            results.append((row, score))
    results.sort(key=lambda pair: (-pair[1], getattr(pair[0], 'id', 0)))
    return [r[0] for r in results]


def new_ref(prefix):
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return prefix + ''.join(secrets.choice(alphabet) for _ in range(8))


def apply_promo(code, base, scope):
    """Return (discount, coupon) for a promo code against a base amount."""
    coupon = Coupon.query.filter_by(code=(code or '').strip().upper()).first()
    if not coupon or not coupon.active:
        return 0.0, None
    if coupon.scope != 'all' and coupon.scope != scope:
        return 0.0, None
    if base < coupon.min_spend:
        return 0.0, coupon
    if coupon.kind == 'percent':
        return round(base * coupon.value / 100.0, 2), coupon
    return min(coupon.value, base), coupon


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    def db_get(kind, row_id):
        model = {'hotel': Hotel, 'attraction': Attraction,
                 'room': RoomRate, 'flight': Flight}.get(kind)
        if model is None:
            return ''
        row = db.session.get(model, row_id)
        return row.name if row is not None and hasattr(row, 'name') else ''

    def keep_args(**overrides):
        """Query string of the current request with some keys overridden."""
        from urllib.parse import urlencode
        args = {k: v for k, v in request.args.items(multi=True)
                if k not in overrides}
        for key, value in overrides.items():
            if value not in (None, ''):
                args[key] = value
        return urlencode(args, doseq=True)

    def db_get_city(city_id):
        row = db.session.get(City, city_id)
        return row.name if row is not None else ''

    return {
        'MIRROR_TODAY': MIRROR_TODAY,
        'DEFAULT_CHECKIN': DEFAULT_CHECKIN,
        'DEFAULT_CHECKOUT': DEFAULT_CHECKOUT,
        'db_get': db_get,
        'keep_args': keep_args,
        'db_get_city': db_get_city,
    }


def stars_display(n):
    return Markup('★' * int(n or 0))


app.jinja_env.filters['stars'] = stars_display


def money(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    if v == int(v):
        return f"${int(v):,}"
    return f"${v:,.2f}"


app.jinja_env.filters['money'] = money


def dmy(d):
    return d.strftime('%a, %b %-d, %Y') if hasattr(d, 'strftime') else str(d)


app.jinja_env.filters['dmy'] = dmy


# ------------------------------------------------------------------- routes --

@app.route('/')
def index():
    cities = City.query.order_by(City.id).all()
    featured_hotels = Hotel.query.filter(Hotel.rating >= 8.6) \
        .order_by(-Hotel.rating, Hotel.id).limit(8).all()
    attractions = Attraction.query.order_by(-Attraction.rating, Attraction.id).limit(8).all()
    guides = Guide.query.order_by(Guide.slug).limit(6).all()
    return render_template('index.html', cities=cities, featured_hotels=featured_hotels,
                           attractions=attractions, guides=guides)


@app.route('/hotels/')
def hotels_home():
    cities = City.query.order_by(City.id).all()
    return render_template('hotels_home.html', cities=cities)


@app.route('/hotels/list')
def hotel_list():
    city_ids = {c.name: c for c in City.query.all()}
    city_name = request.args.get('city', 'Las Vegas')
    city = None
    key = (city_name or '').strip().lower()
    for c in city_ids.values():
        if c.name.lower() == key or c.slug == key:
            city = c
            break
    if city is None:                                   # scored fallback
        matches = scored_search(city_name, list(city_ids.values()), ['name', 'state'])
        city = matches[0] if matches else City.query.filter_by(slug='las_vegas').first()
    if city is None:
        abort(404)

    checkin = parse_date(request.args.get('checkin'), DEFAULT_CHECKIN)
    checkout = parse_date(request.args.get('checkout'), DEFAULT_CHECKOUT)
    if checkout <= checkin:
        checkout = checkin + timedelta(days=1)
    adults = int(request.args.get('adults', 2) or 2)
    children = int(request.args.get('children', 0) or 0)

    query = Hotel.query.filter_by(city_id=city.id)

    # --- filters ---
    price_min = request.args.get('minprice', type=float)
    price_max = request.args.get('maxprice', type=float)
    stars = request.args.getlist('star', type=int)
    rating_min = request.args.get('rating', type=float)
    district = request.args.get('district', '').strip()
    free_cancel = request.args.get('freecancel')
    breakfast = request.args.get('breakfast')
    pool = request.args.get('pool')
    parking = request.args.get('parking')
    if price_min is not None:
        query = query.filter(Hotel.price >= price_min)
    if price_max is not None:
        query = query.filter(Hotel.price <= price_max)
    if stars:
        query = query.filter(Hotel.stars.in_(stars))
    if rating_min:
        query = query.filter(Hotel.rating >= rating_min)
    if district:
        query = query.filter(Hotel.district == district)
    if free_cancel:
        query = query.join(RoomRate).filter(RoomRate.free_cancel.is_(True))
    if breakfast:
        query = query.join(RoomRate).filter(RoomRate.breakfast.is_(True))
    if pool:
        query = query.filter(Hotel.amenities.contains('swimming pool') |
                             Hotel.amenities.contains('"Pool"'))
    if parking:
        query = query.filter(Hotel.amenities.contains('parking'))

    sort = request.args.get('sort', 'recommended')
    if sort == 'price':
        hotels = query.order_by(Hotel.price, -Hotel.rating).all()
    elif sort == 'rating':
        hotels = query.order_by(-Hotel.rating, -Hotel.reviews_count).all()
    elif sort == 'stars':
        hotels = query.order_by(-Hotel.stars, -Hotel.rating).all()
    elif sort == 'reviews':
        hotels = query.order_by(-Hotel.reviews_count).all()
    else:
        # recommended: available properties first (upstream behavior), then
        # rating-weighted; one sponsored card floats to the top of the available set
        hotels = query.order_by(Hotel.bookable.desc(), Hotel.rating.desc(),
                                Hotel.price).all()
        if hotels:
            avail = [h for h in hotels if h.bookable]
            sponsored = [h for h in avail if h.id % 10 == 0][:1]
            rest = [h for h in hotels if h not in sponsored]
            hotels = sponsored + rest

    districts = sorted({h.district for h in
                        Hotel.query.filter_by(city_id=city.id).all()
                        if h.district})
    all_stars = sorted({h.stars for h in
                        Hotel.query.filter_by(city_id=city.id).all()}, reverse=True)
    return render_template(
        'hotel_list.html', city=city, hotels=hotels, checkin=checkin,
        checkout=checkout, adults=adults, children=children, sort=sort,
        nights=(checkout - checkin).days,
        districts=districts, all_stars=all_stars,
        filters={k: request.args.get(k, '') for k in
                 ('minprice', 'maxprice', 'star', 'rating', 'district',
                  'freecancel', 'breakfast', 'pool', 'parking')})


@app.route('/hotels/detail/<int:hotel_id>')
def hotel_detail(hotel_id):
    hotel = db.session.get(Hotel, hotel_id)
    if hotel is None:
        abort(404)
    checkin = parse_date(request.args.get('checkin'), DEFAULT_CHECKIN)
    checkout = parse_date(request.args.get('checkout'), DEFAULT_CHECKOUT)
    if checkout <= checkin:
        checkout = checkin + timedelta(days=1)
    adults = int(request.args.get('adults', 2) or 2)
    children = int(request.args.get('children', 0) or 0)
    rooms = RoomRate.query.filter_by(hotel_id=hotel.id) \
        .order_by(RoomRate.price, RoomRate.id).all()
    photos = HotelPhoto.query.filter_by(hotel_id=hotel.id) \
        .order_by(HotelPhoto.id).limit(8).all()
    reviews = HotelReview.query.filter_by(hotel_id=hotel.id) \
        .order_by(HotelReview.id).limit(6).all()
    city = db.session.get(City, hotel.city_id)
    nearby = Hotel.query.filter(Hotel.city_id == hotel.city_id,
                                Hotel.id != hotel.id) \
        .order_by(-Hotel.rating).limit(4).all()
    in_wishlist = False
    if current_user.is_authenticated:
        in_wishlist = WishlistItem.query.filter_by(
            user_id=current_user.id, hotel_id=hotel.id).first() is not None
    return render_template('hotel_detail.html', hotel=hotel, city=city,
                           rooms=rooms, photos=photos, reviews=reviews,
                           checkin=checkin, checkout=checkout,
                           nights=(checkout - checkin).days,
                           adults=adults, children=children,
                           nearby=nearby, in_wishlist=in_wishlist)


@app.route('/hotels/book/<int:room_id>', methods=['GET', 'POST'])
def hotel_book(room_id):
    room = db.session.get(RoomRate, room_id)
    if room is None:
        abort(404)
    hotel = db.session.get(Hotel, room.hotel_id)
    if hotel is None:
        abort(404)
    checkin = parse_date(request.args.get('checkin'), DEFAULT_CHECKIN)
    checkout = parse_date(request.args.get('checkout'), DEFAULT_CHECKOUT)
    if checkout <= checkin:
        checkout = checkin + timedelta(days=1)
    adults = int(request.args.get('adults', 2) or 2)
    children = int(request.args.get('children', 0) or 0)
    nights = (checkout - checkin).days
    subtotal = room.price * nights
    taxes = (room.total - room.price) * nights
    base = subtotal + taxes

    if request.method == 'POST':
        first = request.form.get('first_name', '').strip()
        last = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        promo = request.form.get('promo_code', '').strip()
        card_no = request.form.get('card_no', '').strip().replace(' ', '')
        card_name = request.form.get('card_name', '').strip()
        errors = []
        if not first or not last:
            errors.append('Please enter the guest name (first and last).')
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errors.append('Please enter a valid email address.')
        if not re.match(r'^\+?[\d\s-]{7,18}$', phone):
            errors.append('Please enter a valid phone number.')
        if not re.match(r'^\d{13,19}$', card_no):
            errors.append('Please enter a valid card number (13-19 digits).')
        if len(card_name) < 3:
            errors.append('Please enter the cardholder name.')
        if errors:
            for e in errors:
                flash(e)
            return render_template('hotel_book.html', hotel=hotel, room=room,
                                   checkin=checkin, checkout=checkout,
                                   nights=nights, subtotal=subtotal,
                                   taxes=taxes, base=base, adults=adults,
                                   children=children,
                                   form=request.form), 400

        discount, coupon = apply_promo(promo, base, 'hotels')
        total = round(base - discount, 2)
        coins = int(total * TRIP_COINS_PCT)
        ref = new_ref('TH')
        booking = HotelBooking(
            ref=ref, hotel_id=hotel.id, room_id=room.id,
            user_id=current_user.id if current_user.is_authenticated else None,
            guest_first=first, guest_last=last, email=email, phone=phone,
            checkin=checkin, checkout=checkout,
            adults=adults, children=children,
            nightly=room.price, taxes=taxes, total=total, coins=coins,
            promo_code=coupon.code if coupon else '')
        db.session.add(booking)
        db.session.commit()
        return redirect(url_for('hotel_confirmation', ref=ref))

    return render_template('hotel_book.html', hotel=hotel, room=room,
                           checkin=checkin, checkout=checkout,
                           nights=nights, subtotal=subtotal, taxes=taxes,
                           base=base, adults=adults, children=children,
                           form={})


@app.route('/hotels/confirmation/<ref>')
def hotel_confirmation(ref):
    booking = db.session.get(HotelBooking, ref)
    if booking is None:
        abort(404)
    hotel = db.session.get(Hotel, booking.hotel_id)
    room = db.session.get(RoomRate, booking.room_id)
    city = db.session.get(City, hotel.city_id)
    return render_template('hotel_confirmation.html', booking=booking,
                           hotel=hotel, room=room, city=city)


@app.route('/flights/')
def flights_home():
    airports = Airport.query.order_by(Airport.code).all()
    routes = FlightRoute.query.order_by(FlightRoute.id).all()
    return render_template('flights_home.html', airports=airports, routes=routes)


def resolve_airports(value):
    """Resolve one search side (airport code, city name, or a mix of both)
    to the set of candidate airport codes. Upstream's search accepts 'MIA',
    'Miami' or anything in between per side."""
    v = (value or '').strip()
    if not v:
        return set()
    vu = v.upper()
    exact = {a.code for a in Airport.query
             if vu == a.code.upper() or vu == a.city.upper()
             or vu == a.name.upper()}
    if exact:
        return exact
    return {a.code for a in Airport.query
            if vu.startswith(a.code.upper()) or a.code.upper() in vu
            or a.city.upper().startswith(vu) or vu in a.city.upper()
            or vu in a.name.upper()}


@app.route('/flights/list')
def flight_list():
    dcity = (request.args.get('dcity') or '').strip().upper()
    acity = (request.args.get('acity') or '').strip().upper()
    trip_type = request.args.get('triptype', 'rt')
    ddate = parse_date(request.args.get('ddate'), date(2026, 10, 20))
    rdate = parse_date(request.args.get('rdate'), ddate + timedelta(days=7))
    cabin = request.args.get('cabin', 'Economy')
    adults = int(request.args.get('adults', 1) or 1)

    # Each side resolves independently (code and/or city name), so mixed input
    # like dcity='MIA' + acity='New York' finds the route.
    origins = resolve_airports(dcity)
    dests = resolve_airports(acity)
    route = None
    if origins and dests:
        route = FlightRoute.query.filter(
            db.func.upper(FlightRoute.origin_code).in_(origins),
            db.func.upper(FlightRoute.dest_code).in_(dests)) \
            .order_by(FlightRoute.id).first()
    if route is None:
        # try full city-name lookup on the route rows themselves
        for r in FlightRoute.query.order_by(FlightRoute.id).all():
            if r.origin_city.upper() == dcity and r.dest_city.upper() == acity:
                route = r
                break
    if route is None:
        flash('No flights found for that route yet. Try one of our popular routes.')
        return redirect(url_for('flights_home'))

    query = Flight.query.filter_by(route_id=route.id, leg='out')
    airline = request.args.get('airline', '').strip()
    stops = request.args.get('stops', '')
    dep_slot = request.args.get('dep', '')
    if airline:
        query = query.filter(Flight.airline == airline)
    if stops == 'nonstop':
        query = query.filter(Flight.stops == 0)
    elif stops == 'direct1':
        query = query.filter(Flight.stops <= 1)
    if dep_slot:
        if dep_slot == 'early':
            query = query.filter(Flight.dep_time < '06:00')
        elif dep_slot == 'morning':
            query = query.filter(Flight.dep_time >= '06:00', Flight.dep_time < '12:00')
        elif dep_slot == 'afternoon':
            query = query.filter(Flight.dep_time >= '12:00', Flight.dep_time < '18:00')
        elif dep_slot == 'evening':
            query = query.filter(Flight.dep_time >= '18:00')
    sort = request.args.get('sort', 'recommended')
    if sort == 'price':
        flights = query.order_by(Flight.price, Flight.dep_time).all()
    elif sort == 'duration':
        flights = query.order_by(Flight.duration_min).all()
    elif sort == 'depart':
        flights = query.order_by(Flight.dep_time).all()
    else:
        flights = query.order_by(Flight.price, Flight.duration_min).all()

    airlines = sorted({f.airline for f in
                       Flight.query.filter_by(route_id=route.id, leg='out').all()})
    arg_str = f"dcity={route.origin_code}&acity={route.dest_code}&ddate={ddate}&rdate={rdate}&triptype={trip_type}"
    return render_template('flight_list.html', route=route, flights=flights,
                           airlines=airlines, ddate=ddate, rdate=rdate,
                           cabin=cabin, adults=adults, trip_type=trip_type,
                           sort=sort, arg_str=arg_str,
                           filters={k: request.args.get(k, '')
                                     for k in ('airline', 'stops', 'dep')})


@app.route('/flights/select/<int:out_id>')
def flight_select_return(out_id):
    outbound = db.session.get(Flight, out_id)
    if outbound is None:
        abort(404)
    route = db.session.get(FlightRoute, outbound.route_id)
    ddate = parse_date(request.args.get('ddate'), date(2026, 10, 20))
    rdate = parse_date(request.args.get('rdate'), ddate + timedelta(days=7))
    cabin = request.args.get('cabin', 'Economy')
    adults = int(request.args.get('adults', 1) or 1)
    query = Flight.query.filter_by(route_id=route.id, leg='ret')
    airline = request.args.get('airline', '').strip()
    stops = request.args.get('stops', '')
    if airline:
        query = query.filter(Flight.airline == airline)
    if stops == 'nonstop':
        query = query.filter(Flight.stops == 0)
    returns = query.order_by(Flight.price, Flight.dep_time).all()
    airlines = sorted({f.airline for f in
                       Flight.query.filter_by(route_id=route.id, leg='ret').all()})
    return render_template('flight_return.html', route=route, outbound=outbound,
                           returns=returns, ddate=ddate, rdate=rdate,
                           cabin=cabin, adults=adults,
                           airlines=airlines, airline=airline, stops=stops)


@app.route('/flights/book', methods=['GET', 'POST'])
def flight_book():
    out_id = request.values.get('out', type=int)
    ret_id = request.values.get('ret', type=int)
    outbound = db.session.get(Flight, out_id) if out_id else None
    if outbound is None:
        abort(404)
    inbound = db.session.get(Flight, ret_id) if ret_id else None
    route = db.session.get(FlightRoute, outbound.route_id)
    cabin = request.values.get('cabin', 'Economy') or 'Economy'
    total = outbound.price + (inbound.price if inbound else 0)
    ddate = parse_date(request.values.get('ddate'), DEFAULT_CHECKIN)
    rdate = parse_date(request.values.get('rdate'), ddate + timedelta(days=7)) if inbound else None
    if rdate and rdate <= ddate:
        abort(400, 'Return date must be after departure')

    if request.method == 'POST':
        first = request.form.get('first_name', '').strip()
        last = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        promo = request.form.get('promo_code', '').strip()
        card_no = request.form.get('card_no', '').strip().replace(' ', '')
        errors = []
        if not first or not last:
            errors.append('Please enter the passenger name (first and last).')
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errors.append('Please enter a valid email address.')
        if not re.match(r'^\+?[\d\s-]{7,18}$', phone):
            errors.append('Please enter a valid phone number.')
        if not re.match(r'^\d{13,19}$', card_no):
            errors.append('Please enter a valid card number (13-19 digits).')
        if errors:
            for e in errors:
                flash(e)
            return render_template('flight_book.html', route=route,
                                   outbound=outbound, inbound=inbound,
                                   cabin=cabin, total=total, ddate=ddate, rdate=rdate,
                                   form=request.form), 400
        discount, coupon = apply_promo(promo, total, 'flights')
        paid = round(total - discount, 2)
        ref = new_ref('TF')
        booking = FlightBooking(
            ref=ref, outbound_id=outbound.id,
            return_id=inbound.id if inbound else None,
            user_id=current_user.id if current_user.is_authenticated else None,
            passenger_first=first, passenger_last=last, email=email,
            phone=phone, cabin=cabin,
            trip_type='rt' if inbound else 'ow',
            total=paid, promo_code=coupon.code if coupon else '',
            departure_date=ddate, return_date=rdate)
        db.session.add(booking)
        db.session.commit()
        return redirect(url_for('flight_confirmation', ref=ref))

    return render_template('flight_book.html', route=route, outbound=outbound,
                           inbound=inbound, cabin=cabin, total=total, ddate=ddate, rdate=rdate, form={})


@app.route('/flights/confirmation/<ref>')
def flight_confirmation(ref):
    booking = db.session.get(FlightBooking, ref)
    if booking is None:
        abort(404)
    outbound = db.session.get(Flight, booking.outbound_id)
    inbound = db.session.get(Flight, booking.return_id) if booking.return_id else None
    route = db.session.get(FlightRoute, outbound.route_id)
    return render_template('flight_confirmation.html', booking=booking,
                           outbound=outbound, inbound=inbound, route=route)


@app.route('/things-to-do/')
def things_to_do_home():
    attractions = Attraction.query.order_by(-Attraction.rating).limit(12).all()
    cities = City.query.order_by(City.id).all()
    return render_template('things_to_do.html', attractions=attractions, cities=cities)


@app.route('/things-to-do/experiences/<city_slug>')
def attraction_list(city_slug):
    city = City.query.filter_by(slug=city_slug).first()
    if city is None:
        abort(404)
    category = request.args.get('category', '').strip()
    query = Attraction.query.filter_by(city_slug=city_slug)
    if category:
        query = query.filter(Attraction.category == category)
    sort = request.args.get('sort', 'recommended')
    if sort == 'price':
        attractions = query.order_by(Attraction.price_from).all()
    elif sort == 'rating':
        attractions = query.order_by(-Attraction.rating).all()
    else:
        attractions = query.order_by(-Attraction.booked_count).all()
    categories = sorted({a.category for a in
                         Attraction.query.filter_by(city_slug=city_slug).all()
                         if a.category})
    return render_template('attraction_list.html', city=city,
                           attractions=attractions, categories=categories,
                           category=category, sort=sort)


@app.route('/things-to-do/detail/<int:attraction_id>')
def attraction_detail(attraction_id):
    attraction = db.session.get(Attraction, attraction_id)
    if attraction is None:
        abort(404)
    packages = AttractionPackage.query.filter_by(attraction_id=attraction.id) \
        .order_by(AttractionPackage.price).all()
    similar = Attraction.query.filter(
        Attraction.city_slug == attraction.city_slug,
        Attraction.id != attraction.id).limit(4).all()
    return render_template('attraction_detail.html', attraction=attraction,
                           packages=packages, similar=similar)


@app.route('/things-to-do/book/<int:package_id>', methods=['GET', 'POST'])
def attraction_book(package_id):
    package = db.session.get(AttractionPackage, package_id)
    if package is None:
        abort(404)
    attraction = db.session.get(Attraction, package.attraction_id)

    if request.method == 'POST':
        # The Book-now link seeds the form via the query string, but once the
        # traveller edits the date/guests inputs and submits, the FORM values
        # are authoritative (request.values would let the query string
        # silently override the submitted values).
        visit_date = parse_date(request.form.get('date'),
                                parse_date(request.args.get('date'),
                                           DEFAULT_CHECKIN))
        guests = parse_guests(request.form.get('guests'),
                              request.args.get('guests'))
        # Store the same value the confirmation page displays (16.09 x 3
        # otherwise lands as 48.269999... in the DB; review r2 deviation #4).
        total = round(package.price * guests, 2)

        first = request.form.get('first_name', '').strip()
        last = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        errors = []
        if not first or not last:
            errors.append('Please enter the lead traveller name.')
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errors.append('Please enter a valid email address.')
        if errors:
            for e in errors:
                flash(e)
            return render_template('attraction_book.html', attraction=attraction,
                                   package=package, visit_date=visit_date,
                                   guests=guests, total=total,
                                   form=request.form), 400
        ref = new_ref('TA')
        booking = AttractionBooking(
            ref=ref, attraction_id=attraction.id, package_id=package.id,
            user_id=current_user.id if current_user.is_authenticated else None,
            visit_date=visit_date, guests=guests,
            lead_first=first, lead_last=last, email=email, total=total)
        db.session.add(booking)
        db.session.commit()
        return redirect(url_for('attraction_confirmation', ref=ref))

    # GET: prefill from the Book-now link's query-string defaults.
    visit_date = parse_date(request.args.get('date'), DEFAULT_CHECKIN)
    guests = parse_guests(request.args.get('guests'))
    total = round(package.price * guests, 2)
    return render_template('attraction_book.html', attraction=attraction,
                           package=package, visit_date=visit_date,
                           guests=guests, total=total, form={})


@app.route('/things-to-do/confirmation/<ref>')
def attraction_confirmation(ref):
    booking = db.session.get(AttractionBooking, ref)
    if booking is None:
        abort(404)
    attraction = db.session.get(Attraction, booking.attraction_id)
    package = db.session.get(AttractionPackage, booking.package_id)
    return render_template('attraction_confirmation.html', booking=booking,
                           attraction=attraction, package=package)


# ------------------------------------------------------------------- account --

@app.route('/sign-in/', methods=['GET', 'POST'])
def sign_in():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user is None or not bcrypt.check_password_hash(user.password_hash, password):
            flash('Email or password is incorrect.')
            return render_template('sign_in.html', form=request.form), 401
        login_user(user)
        return redirect(request.args.get('next') or url_for('account'))
    return render_template('sign_in.html', form={})


@app.route('/register/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        errors = []
        if len(name) < 2:
            errors.append('Please enter your name.')
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errors.append('Please enter a valid email address.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if User.query.filter_by(email=email).first():
            errors.append('An account with this email already exists.')
        if errors:
            for e in errors:
                flash(e)
            return render_template('register.html', form=request.form), 400
        user = User(email=email, name=name,
                    password_hash=bcrypt.generate_password_hash(password).decode())
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('account'))
    return render_template('register.html', form={})


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/account/')
@login_required
def account():
    hotel_bookings = HotelBooking.query.filter_by(user_id=current_user.id) \
        .order_by(-HotelBooking.created_at).all()
    flight_bookings = FlightBooking.query.filter_by(user_id=current_user.id) \
        .order_by(-FlightBooking.created_at).all()
    attraction_bookings = AttractionBooking.query.filter_by(user_id=current_user.id) \
        .order_by(-AttractionBooking.created_at).all()
    return render_template('account.html', hotel_bookings=hotel_bookings,
                           flight_bookings=flight_bookings,
                           attraction_bookings=attraction_bookings)


@app.route('/account/bookings')
@login_required
def account_bookings():
    hotel_bookings = HotelBooking.query.filter_by(user_id=current_user.id) \
        .order_by(-HotelBooking.created_at).all()
    flight_bookings = FlightBooking.query.filter_by(user_id=current_user.id) \
        .order_by(-FlightBooking.created_at).all()
    attraction_bookings = AttractionBooking.query.filter_by(user_id=current_user.id) \
        .order_by(-AttractionBooking.created_at).all()
    return render_template('account_bookings.html',
                           hotel_bookings=hotel_bookings,
                           flight_bookings=flight_bookings,
                           attraction_bookings=attraction_bookings)


@app.route('/account/wishlist')
@login_required
def account_wishlist():
    items = WishlistItem.query.filter_by(user_id=current_user.id).all()
    hotels = [db.session.get(Hotel, i.hotel_id) for i in items]
    return render_template('wishlist.html', hotels=hotels)


@app.route('/account/coupons')
@login_required
def account_coupons():
    coupons = Coupon.query.filter_by(active=True).order_by(Coupon.code).all()
    return render_template('coupons.html', coupons=coupons)


@app.route('/wishlist/toggle/<int:hotel_id>', methods=['POST'])
def wishlist_toggle(hotel_id):
    if not current_user.is_authenticated:
        flash('Sign in to save hotels to your wishlist.')
        return redirect(url_for('sign_in'))
    item = WishlistItem.query.filter_by(user_id=current_user.id,
                                        hotel_id=hotel_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash('Removed from wishlist.')
    else:
        db.session.add(WishlistItem(user_id=current_user.id, hotel_id=hotel_id))
        db.session.commit()
        flash('Saved to your wishlist.')
    return redirect(request.referrer or url_for('hotel_detail', hotel_id=hotel_id))


@app.route('/bookings/cancel/<kind>/<ref>', methods=['POST'])
@login_required
def booking_cancel(kind, ref):
    model = {'hotel': HotelBooking, 'flight': FlightBooking,
             'attraction': AttractionBooking}.get(kind)
    if model is None:
        abort(404)
    booking = db.session.get(model, ref)
    if booking is None or booking.user_id != current_user.id:
        abort(404)
    booking.status = 'cancelled'
    db.session.commit()
    flash(f'Booking {ref} has been cancelled.')
    return redirect(url_for('account_bookings'))


# ------------------------------------------------------------- content pages --

@app.route('/deals/')
def deals():
    coupons = Coupon.query.filter_by(active=True).order_by(Coupon.code).all()
    cheap_flights = []
    for route in FlightRoute.query.order_by(FlightRoute.id).all():
        best = Flight.query.filter_by(route_id=route.id, leg='out') \
            .order_by(Flight.price).first()
        if best:
            cheap_flights.append((route, best))
    return render_template('deals.html', coupons=coupons,
                           cheap_flights=cheap_flights)


@app.route('/guide/')
def guide_index():
    guides = Guide.query.order_by(Guide.slug).all()
    return render_template('guide_index.html', guides=guides)


@app.route('/guide/<slug>')
def guide_article(slug):
    article = Guide.query.filter_by(slug=slug).first()
    if article is None:
        abort(404)
    return render_template('guide_article.html', article=article)


@app.route('/search')
def site_search():
    q = request.args.get('q', '').strip()
    hotels = scored_search(q, Hotel.query.all(), ['name', 'district', 'near'])
    attractions = scored_search(q, Attraction.query.all(), ['name', 'category', 'description'])
    guides = scored_search(q, Guide.query.all(), ['title', 'body'])
    return render_template('search_results.html', q=q, hotels=hotels[:12],
                           attractions=attractions[:8], guides=guides[:6],
                           hotel_total=len(hotels), attraction_total=len(attractions),
                           guide_total=len(guides))


# ------------------------------------------------------------------ misc --

@app.route('/_health')
def health_probe():
    """Health probe used by the control plane after /reset."""
    import _health
    result = _health.health()
    return jsonify(result), (200 if result.get('ok') else 500)


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


# ------------------------------------------------------------------ bootstrap --

def seed_database():
    if City.query.count() > 0:
        return
    from seed_data import build_seed
    build_seed(db)


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    from seed_data import build_benchmark_users
    build_benchmark_users(db, bcrypt, BENCHMARK_PASSWORD_HASH)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 40111)), debug=False)
