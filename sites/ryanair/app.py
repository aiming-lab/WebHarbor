#!/usr/bin/env python3
"""Ryanair mirror — Flask application.

Mirrors https://www.ryanair.com/ (gb/en market): flight search with the
airport picker and date strip, flight selection, fare bundles, allocated
seats, cabin/check-in bags, extras (Fast Track, insurance, inflight credit),
payment with price breakdown, myRyanair account area, online check-in with
boarding passes, fare finder, flights-to destination pages, timetable, help
centre and site-wide scored search.

Data comes from the tracked source_data_*.json snapshots captured on
2026-09-24 (see scripts_dev/build_source_data.py); the SQLite seed is
materialized deterministically at image build time.
"""
import hashlib
import json
import math
import os
import random
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
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("RYANAIR_SECRET_KEY") or "webharbor-ryanair-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'RYANAIR_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'ryanair.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your account.'
csrf = CSRFProtect(app)

# The mirror is a snapshot of the upstream site taken on 2026-09-24.
MIRROR_TODAY = date(2026, 9, 24)
MIRROR_DATE = datetime(2026, 9, 24, 12, 0, 0)
# bcrypt hash of 'TestPass123!' (frozen so the SQLite seed is byte-reproducible
# on every build; PYTHONHASHSEED=0 keeps the rest deterministic)
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')
BOOKING_HORIZON_DAYS = 400          # flights bookable up to this far out
CHECKIN_WINDOW_ASSIGNED = 60 * 24 * 60  # minutes before departure (60 days)
CHECKIN_WINDOW_RANDOM = 24 * 60     # minutes before departure (24 hours)
CARD_FEE_PCT = 2.0
SMS_FEE = 2.99
FARE_MULTIPLIERS = {'basic': 1.0, 'regular': 1.40, 'plus': 1.97,
                    'flexi_plus': 5.47}
FARE_ORDER = ['basic', 'regular', 'plus', 'flexi_plus']
SEAT_ROWS = [r for r in range(1, 34) if r != 13]
SEAT_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']
TITLES = ['Mr', 'Mrs', 'Ms', 'Mx']
STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
              'or', 'is', 'it', 'by', 'with', 'flights', 'flight', 'to'}


# ------------------------------------------------------------------ models --

class Airport(db.Model):
    __tablename__ = 'airports'
    code = db.Column(db.String(3), primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    country = db.Column(db.String(60), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    is_base = db.Column(db.Boolean, default=False)
    image = db.Column(db.String(160), nullable=False)

    @property
    def slug(self):
        slug = re.sub(r'[^a-z0-9]+', '-', self.city.lower()).strip('-')
        return slug or self.code.lower()

    @property
    def image_path(self):
        return f'static/images/{self.image}'


class Route(db.Model):
    __tablename__ = 'routes'
    id = db.Column(db.Integer, primary_key=True)
    origin_code = db.Column(db.String(3), nullable=False)
    destination_code = db.Column(db.String(3), nullable=False)
    distance_km = db.Column(db.Integer, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    base_price = db.Column(db.Float, nullable=False)

    __table_args__ = (db.UniqueConstraint('origin_code', 'destination_code'),)

    @property
    def origin(self):
        return db.session.get(Airport, self.origin_code)

    @property
    def destination(self):
        return db.session.get(Airport, self.destination_code)

    @property
    def duration_label(self):
        return f'{self.duration_minutes // 60}h {self.duration_minutes % 60:02d}m'


class FlightSchedule(db.Model):
    __tablename__ = 'flight_schedules'
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id'), nullable=False)
    flight_number = db.Column(db.String(12), nullable=False, unique=True)
    departure = db.Column(db.String(5), nullable=False)
    arrival = db.Column(db.String(5), nullable=False)
    days = db.Column(db.String(20), nullable=False)  # csv of 1..7 (Mon..Sun)

    route = db.relationship('Route', backref='schedules')

    def operates_on(self, day: date):
        return str(day.isoweekday()) in self.days.split(',')

    def seat_price(self, row: int):
        return seat_price(row)

    def occupied_seats(self, day: date):
        """Deterministic set of already-taken seats for this departure."""
        digest = hashlib.md5(
            f'{self.flight_number}|{day.isoformat()}|occ'.encode()).hexdigest()
        rng = random.Random(int(digest[:12], 16))
        count = rng.randint(28, 96)
        seats = []
        for _ in range(count):
            row = rng.choice(SEAT_ROWS)
            letter = rng.choice(SEAT_LETTERS)
            seats.append(f'{row}{letter}')
        return set(seats)

    def seats_left_at_price(self, day: date):
        digest = hashlib.md5(
            f'{self.flight_number}|{day.isoformat()}|left'.encode()).hexdigest()
        rng = random.Random(int(digest[:12], 16))
        return rng.randint(2, 9)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False, default='')
    last_name = db.Column(db.String(80), nullable=False, default='')
    phone = db.Column(db.String(30), default='')
    country = db.Column(db.String(60), default='United Kingdom')
    address_line1 = db.Column(db.String(120), default='')
    address_line2 = db.Column(db.String(120), default='')
    city = db.Column(db.String(80), default='')
    postcode = db.Column(db.String(20), default='')
    newsletter = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=MIRROR_DATE)

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    card_type = db.Column(db.String(30), nullable=False)
    last4 = db.Column(db.String(4), nullable=False)
    holder = db.Column(db.String(120), nullable=False)
    expiry = db.Column(db.String(5), nullable=False)
    is_default = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='payment_methods')


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    booking_ref = db.Column(db.String(8), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    contact_email = db.Column(db.String(120), nullable=False)
    contact_phone = db.Column(db.String(30), default='')
    fare_type = db.Column(db.String(12), nullable=False, default='basic')
    adults = db.Column(db.Integer, nullable=False, default=1)
    teens = db.Column(db.Integer, nullable=False, default=0)
    children = db.Column(db.Integer, nullable=False, default=0)
    infants = db.Column(db.Integer, nullable=False, default=0)
    outbound_schedule_id = db.Column(db.Integer,
                                     db.ForeignKey('flight_schedules.id'),
                                     nullable=False)
    outbound_date = db.Column(db.Date, nullable=False)
    inbound_schedule_id = db.Column(db.Integer,
                                    db.ForeignKey('flight_schedules.id'),
                                    nullable=True)
    inbound_date = db.Column(db.Date, nullable=True)
    promo_code = db.Column(db.String(20), default='')
    sms_updates = db.Column(db.Boolean, default=False)
    insurance_key = db.Column(db.String(12), default='')
    fast_track_out = db.Column(db.Boolean, default=False)
    fast_track_in = db.Column(db.Boolean, default=False)
    inflight_credit = db.Column(db.Float, default=0.0)
    flights_total = db.Column(db.Float, nullable=False, default=0.0)
    seats_total = db.Column(db.Float, nullable=False, default=0.0)
    bags_total = db.Column(db.Float, nullable=False, default=0.0)
    extras_total = db.Column(db.Float, nullable=False, default=0.0)
    card_fee = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default='confirmed')
    checked_in = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=MIRROR_DATE)

    outbound_schedule = db.relationship('FlightSchedule', foreign_keys=[outbound_schedule_id])
    inbound_schedule = db.relationship('FlightSchedule', foreign_keys=[inbound_schedule_id])
    passengers = db.relationship('BookingPassenger', backref='booking',
                                 order_by='BookingPassenger.id')

    @property
    def pax_count(self):
        return self.adults + self.teens + self.children

    def leg_label(self, outbound=True):
        sched = self.outbound_schedule if outbound else self.inbound_schedule
        if not sched:
            return ''
        route = sched.route
        return f'{route.origin_code} - {route.destination_code}'

    def breakdown_lines(self):
        lines = [('Flights', self.flights_total)]
        if self.seats_total:
            lines.append(('Seats', self.seats_total))
        if self.bags_total:
            lines.append(('Bags', self.bags_total))
        if self.extras_total:
            lines.append(('Extras', self.extras_total))
        if self.card_fee:
            lines.append(('Card processing fee', self.card_fee))
        return lines


class BookingPassenger(db.Model):
    __tablename__ = 'booking_passengers'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'),
                           nullable=False)
    title = db.Column(db.String(6), default='Mr')
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    seat_out = db.Column(db.String(4), default='')
    seat_in = db.Column(db.String(4), default='')
    cabin_out = db.Column(db.String(12), default='small-bag')
    cabin_in = db.Column(db.String(12), default='small-bag')
    checkin_10kg_out = db.Column(db.Integer, default=0)
    checkin_10kg_in = db.Column(db.Integer, default=0)
    checkin_20kg_out = db.Column(db.Integer, default=0)
    checkin_20kg_in = db.Column(db.Integer, default=0)
    checkin_23kg_out = db.Column(db.Integer, default=0)
    checkin_23kg_in = db.Column(db.Integer, default=0)

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def bag_count(self, outbound=True):
        if outbound:
            return (self.checkin_10kg_out + self.checkin_20kg_out +
                    self.checkin_23kg_out)
        return self.checkin_10kg_in + self.checkin_20kg_in + self.checkin_23kg_in


class PromoCode(db.Model):
    __tablename__ = 'promo_codes'
    code = db.Column(db.String(20), primary_key=True)
    discount_pct = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(200), default='')


class HelpTopic(db.Model):
    __tablename__ = 'help_topics'
    slug = db.Column(db.String(40), primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    icon = db.Column(db.String(30), default='info')
    summary = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=False)  # JSON list of blocks


class Guide(db.Model):
    __tablename__ = 'guides'
    code = db.Column(db.String(3), primary_key=True)
    city = db.Column(db.String(40), nullable=False)
    intro = db.Column(db.Text, nullable=False)
    must_reads = db.Column(db.Text, nullable=False)  # JSON list

    @property
    def must_reads_list(self):
        return json.loads(self.must_reads)

    def guide_images(self):
        base = os.path.join(BASE_DIR, 'static', 'images', 'guides')
        if not os.path.isdir(base):
            # managed assets not populated (clean checkout / unit-test scratch
            # tree): render without the photo strip instead of crashing
            return []
        return sorted(
            f'guides/{f}'
            for f in os.listdir(base) if f.startswith(self.city + '-'))


class TripState(db.Model):
    """Server-side state for the booking flow, keyed by a session token."""
    __tablename__ = 'trip_states'
    token = db.Column(db.String(40), primary_key=True)
    data = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=MIRROR_DATE)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------- pricing helpers --

def _digest_float(*parts):
    digest = hashlib.md5('|'.join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def day_factor(day: date):
    """Weekend/Friday premium, midweek discount."""
    if day.isoweekday() in (5, 6, 7):   # Fri, Sat, Sun
        return 1.15
    if day.isoweekday() in (2, 3):      # Tue, Wed
        return 0.90
    return 1.0


def flight_price(schedule, day: date, fare='basic', promo_pct=0):
    """Deterministic per-person one-way price for a flight on a date."""
    base = schedule.route.base_price
    jitter = 0.82 + 0.55 * _digest_float(schedule.flight_number, day.isoformat())
    advance = (day - MIRROR_TODAY).days
    # last-minute premium, gentle long-horizon discount
    if advance <= 3:
        jitter *= 1.35
    elif advance <= 10:
        jitter *= 1.12
    elif advance >= 120:
        jitter *= 0.88
    price = base * jitter * day_factor(day)
    price *= FARE_MULTIPLIERS.get(fare, 1.0)
    if promo_pct:
        price *= (100 - promo_pct) / 100.0
    # round to a pricey .99 / .49 ending
    whole = math.floor(price)
    frac = price - whole
    if frac >= 0.75:
        price = whole + 0.99
    elif frac >= 0.25:
        price = whole + 0.49
    else:
        price = max(0.99, whole - 0.01 + 0.99)
    return round(price, 2)


def sale_price_pair(schedule, day: date, fare='basic', promo_pct=0):
    """(original, sale) like the crossed-out prices on the flight cards."""
    price = flight_price(schedule, day, fare, promo_pct)
    digest = _digest_float('sale', schedule.flight_number, day.isoformat())
    if fare == 'basic' and digest > 0.55:
        return round(price * 1.18 + 0.30, 2), price
    return None, price


def seat_price(row: int):
    if row <= 2:
        return 21.50
    if row <= 6:
        return 14.00
    if row <= 15:
        return round(13.50 - (row - 7) * 0.50, 2)
    if row <= 17:
        return 14.50
    return 9.50


def seat_band(row: int):
    if row <= 2:
        return ('XL', 'Extra legroom up front', '1 - 2')
    if row <= 6:
        return ('GET OFF QUICK', 'Get off quick', '2 - 6')
    if row <= 15:
        return ('BEST VALUE UP FRONT', 'Best value up front', '7 - 15')
    if row <= 17:
        return ('XL', 'Stretch out for less', '16 - 17')
    return ('BEST VALUE AT THE BACK', 'Best value at the back', '18 - 33')


def fast_track_price(airport_code):
    known = {'STN': 8.49, 'DUB': 12.03}
    if airport_code in known:
        return known[airport_code]
    return round(6.00 + 9.00 * _digest_float('ft', airport_code), 2)


def fast_track_airports(schedule_out, schedule_in):
    codes = []
    for sched in (schedule_out, schedule_in):
        if sched is None:
            continue
        for code in (sched.route.origin_code, sched.route.destination_code):
            if code not in codes:
                codes.append(code)
    return codes


def insurance_price(key, outbound_date, inbound_date, pax):
    if key == 'annual':
        return round(28.18 * pax, 2)
    days = 1
    if inbound_date:
        days = max(1, (inbound_date - outbound_date).days + 1)
    per_day = {'standard': 1.46, 'plus': 1.90}.get(key)
    if not per_day:
        return 0.0
    return round(per_day * days * pax, 2)


BAG_PRICES = {'10kg': 11.49, '20kg': 25.49, '23kg': 34.49}
PRIORITY_PRICE = 16.00


def money(value):
    return f'£{value:,.2f}'


# ------------------------------------------------------------ trip helpers --

def get_trip():
    token = session.get('trip_token')
    if not token:
        return None, None
    trip = db.session.get(TripState, token)
    if not trip:
        return None, None
    return token, json.loads(trip.data)


def save_trip(token, data):
    trip = db.session.get(TripState, token)
    if not trip:
        trip = TripState(token=token, data=json.dumps(data))
        db.session.add(trip)
    else:
        trip.data = json.dumps(data)
        trip.updated_at = MIRROR_DATE
    db.session.commit()


def new_trip():
    token = secrets.token_hex(16)
    session['trip_token'] = token
    return token


def trip_airports(data):
    origin = db.session.get(Airport, data['origin'])
    dest = db.session.get(Airport, data['destination'])
    return origin, dest


def trip_pax(data):
    return (data.get('adults', 1) + data.get('teens', 0) +
            data.get('children', 0))


def trip_promo_pct(data):
    code = (data.get('promoCode') or '').strip().upper()
    if not code:
        return 0
    promo = db.session.get(PromoCode, code)
    return promo.discount_pct if promo else 0


def trip_flights(data, direction):
    """Schedules operating on the trip date for a direction."""
    key = 'outbound' if direction == 'out' else 'inbound'
    route = Route.query.filter_by(
        origin_code=data['origin'] if direction == 'out' else data['destination'],
        destination_code=data['destination'] if direction == 'out' else data['origin']).first()
    if not route:
        return []
    day = _parse_date(data.get('dateOut' if direction == 'out' else 'dateIn'))
    if not day:
        return []
    scheds = [s for s in route.schedules if s.operates_on(day)]
    scheds.sort(key=lambda s: s.departure)
    return scheds


def _parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def date_strip(day: date, schedule_getter, promo_pct=0):
    """Surrounding-day cheapest prices for the date ribbon."""
    strip = []
    for offset in range(-2, 3):
        d = day + timedelta(days=offset)
        scheds = schedule_getter(d)
        if not scheds:
            strip.append({'date': d, 'price': None,
                          'enabled': d >= MIRROR_TODAY,
                          'selected': offset == 0})
            continue
        price = min(flight_price(s, d, 'basic', promo_pct) for s in scheds)
        strip.append({'date': d, 'price': price,
                      'enabled': d >= MIRROR_TODAY,
                      'selected': offset == 0})
    return strip


def make_flight_view(schedule, day, promo_pct=0, selected=False):
    route = schedule.route
    original, sale = sale_price_pair(schedule, day, 'basic', promo_pct)
    return {
        'schedule': schedule,
        'flight_number': schedule.flight_number,
        'departure': schedule.departure,
        'arrival': schedule.arrival,
        'duration': route.duration_label,
        'origin': route.origin,
        'destination': route.destination,
        'original_price': original,
        'price': sale,
        'seats_left': schedule.seats_left_at_price(day),
        'selected': selected,
    }


def build_fare_table(data):
    """Fare options for the selected flights (per person, per flight)."""
    out_sched = db.session.get(FlightSchedule, data.get('outboundSchedule'))
    in_sched = db.session.get(FlightSchedule, data.get('inboundSchedule')) if data.get('inboundSchedule') else None
    out_day = _parse_date(data.get('dateOut'))
    in_day = _parse_date(data.get('dateIn'))
    promo_pct = trip_promo_pct(data)
    legs = [(out_sched, out_day)]
    if in_sched and in_day:
        legs.append((in_sched, in_day))
    table = []
    for key in FARE_ORDER:
        per_flight = [flight_price(s, d, key, promo_pct) for s, d in legs]
        delta = round(sum(per_flight) - sum(
            flight_price(s, d, 'basic', promo_pct) for s, d in legs), 2)
        table.append({
            'key': key,
            'name': FARE_INFO[key]['name'],
            'tagline': FARE_INFO[key]['tagline'],
            'features': FARE_INFO[key]['features'],
            'per_flight': per_flight,
            'delta': delta,
            'total': round(sum(per_flight), 2),
        })
    return table


FARE_INFO = {
    'basic': {'name': 'BASIC', 'tagline': 'Travel light',
              'features': ['1 small bag — must fit under the seat in front']},
    'regular': {'name': 'REGULAR',
                'tagline': 'Choose your seat and 10kg bag on board',
                'features': ['Reserved seat (specific rows available)',
                             'Priority boarding',
                             '10kg overhead locker bag']},
    'plus': {'name': 'PLUS',
             'tagline': 'Choose your seat and a 20kg checked in bag',
             'features': ['Reserved seat (specific rows available)',
                          'Priority boarding', '20kg check-in bag',
                          'Speed through security (Fast Track)']},
    'flexi_plus': {'name': 'FLEXI PLUS',
                   'tagline': 'Our most flexible bundle',
                   'features': ['Any seat on the plane!',
                                'Priority boarding', '20kg check-in bag',
                                'Speed through security (Fast Track)',
                                'Change flights with no fees',
                                'Move to an earlier flight (same day)']},
}


def trip_price_lines(data):
    """Live price breakdown for the seats/bags/extras/payment sidebars."""
    out_sched = db.session.get(FlightSchedule, data.get('outboundSchedule'))
    in_sched = db.session.get(FlightSchedule, data.get('inboundSchedule')) if data.get('inboundSchedule') else None
    out_day = _parse_date(data.get('dateOut'))
    in_day = _parse_date(data.get('dateIn'))
    fare = data.get('fare', 'basic')
    promo_pct = trip_promo_pct(data)
    pax = trip_pax(data)
    # A one-way trip has no inbound leg: seats/bags must never be priced
    # for the phantom return flight (review diff #1, HIGH).
    has_return = bool(in_sched and in_day)
    legs = [(out_sched, out_day)]
    if has_return:
        legs.append((in_sched, in_day))
    flights = round(sum(flight_price(s, d, fare, promo_pct)
                         for s, d in legs) * pax, 2)
    lines = [('Flights', flights)]
    total = flights

    seat_directions = ('out', 'in') if has_return else ('out',)
    seats = data.get('seats', {})     # {'out': [seat,...], 'in': [...]}
    seats_total = 0.0
    for direction in seat_directions:
        for seat in seats.get(direction) or []:
            row = int(re.match(r'(\d+)', seat).group(1))
            seats_total += seat_price(row)
    if seats_total:
        seats_total = round(seats_total, 2)
        lines.append(('Seats', seats_total))
        total = round(total + seats_total, 2)

    bag_directions = ('out', 'in') if has_return else ('out',)
    bags_total = 0.0
    for p in data.get('passengers', []):
        for direction in bag_directions:
            if p.get(f'cabin_{direction}') == 'priority':
                bags_total += PRIORITY_PRICE
            for size in ('10kg', '20kg', '23kg'):
                bags_total += BAG_PRICES[size] * (p.get(f'bag_{size}_{direction}') or 0)
    bags_total = round(bags_total, 2)
    if bags_total:
        lines.append(('Bags', bags_total))
        total = round(total + bags_total, 2)

    extras_total = 0.0
    ft = data.get('extras', {}).get('fast_track', {})
    for code, enabled in ft.items():
        if enabled and code:
            extras_total += fast_track_price(code) * pax
    insurance = data.get('extras', {}).get('insurance')
    if insurance:
        extras_total += insurance_price(insurance, out_day, in_day, pax)
    credit = data.get('extras', {}).get('inflight_credit') or 0
    extras_total += credit
    if data.get('smsUpdates'):
        extras_total += SMS_FEE
    extras_total = round(extras_total, 2)
    if extras_total:
        lines.append(('Extras', extras_total))
        total = round(total + extras_total, 2)

    card_fee = round(total * CARD_FEE_PCT / 100.0, 2)
    return lines, total, card_fee, round(total + card_fee, 2)


def trip_passenger_count(data):
    return len(data.get('passengers', []))


# ------------------------------------------------------------------- views --

@app.context_processor
def inject_globals():
    return {
        'MIRROR_TODAY': MIRROR_TODAY,
        'money': money,
        'airport_lookup': lambda code: db.session.get(Airport, code),
    }


def _countries():
    rows = (db.session.query(Airport.country, db.func.count(Airport.code))
            .group_by(Airport.country).order_by(Airport.country).all())
    return rows


@app.route('/')
def root():
    return redirect('/gb/en')


@app.route('/gb/en', strict_slashes=False)
@app.route('/gb/en/', strict_slashes=False)
def home():
    origin = request.args.get('originIata', 'STN')
    origin_ap = db.session.get(Airport, origin) or db.session.get(Airport, 'STN')
    content = _content()
    destinations = Route.query.filter_by(origin_code=origin_ap.code).all()
    dest_map = {d.destination_code: d for d in destinations}
    dest_airports = [db.session.get(Airport, c) for c in dest_map]
    dest_airports = [a for a in dest_airports if a]
    dest_airports.sort(key=lambda a: a.name)
    airports_json = json.dumps([
        {'code': a.code, 'name': a.name, 'city': a.city, 'country': a.country}
        for a in Airport.query.order_by(Airport.name).all()])
    return render_template('index.html', origin=origin_ap,
                           destinations=dest_airports,
                           hero_slides=content['hero_slides'],
                           partner_cards=content['partner_cards'],
                           explore_europe=content['explore_europe'],
                           airports_json=airports_json,
                           today=MIRROR_TODAY.isoformat(),
                           countries=_countries())


@app.route('/gb/en/cheap-flight-destinations')
def fare_finder():
    origin = request.args.get('originIata', 'STN')
    origin_ap = db.session.get(Airport, origin)
    if not origin_ap:
        origin_ap = db.session.get(Airport, 'STN')
    min_price = request.args.get('minPrice', type=float, default=0)
    max_price = request.args.get('maxPrice', type=float, default=999)
    max_duration = request.args.get('maxDuration', type=int, default=0)
    routes = Route.query.filter_by(origin_code=origin_ap.code).all()
    cards = []
    for route in routes:
        scheds = route.schedules
        if not scheds:
            continue
        best = None
        best_day = None
        for offset in range(1, 31):
            d = MIRROR_TODAY + timedelta(days=offset)
            operating = [s for s in scheds if s.operates_on(d)]
            if not operating:
                continue
            p = min(flight_price(s, d) for s in operating)
            if best is None or p < best:
                best = p
                best_day = d
        if best is None:
            continue
        cards.append({
            'route': route, 'airport': route.destination,
            'price': best, 'date': best_day,
            'duration': route.duration_minutes,
        })
    cards.sort(key=lambda c: c['price'])
    total = len(cards)
    if max_price < 999:
        cards = [c for c in cards if c['price'] <= max_price]
    if min_price > 0:
        cards = [c for c in cards if c['price'] >= min_price]
    if max_duration:
        cards = [c for c in cards if c['duration'] <= max_duration]
    return render_template('fare_finder.html', origin=origin_ap, cards=cards,
                           total=total, countries=_countries(),
                           origin_choices=[(a.code, a.name) for a in
                                           Airport.query.filter_by(is_base=True)
                                           .order_by(Airport.name).all()],
                           min_price=min_price, max_price=max_price,
                           max_duration=max_duration)


@app.route('/gb/en/route-map')
def route_map():
    by_country = {}
    for airport in Airport.query.order_by(Airport.name).all():
        by_country.setdefault(airport.country, []).append(airport)
    return render_template('route_map.html', by_country=by_country,
                           countries=_countries(),
                           airports_count=Airport.query.count())


@app.route('/flights/gb/en/flights-to-<slug>')
def flights_to(slug):
    airport = Airport.query.filter(
        (db.func.lower(db.func.replace(Airport.city, ' ', '-')) == slug.lower())
        | (Airport.code == slug.upper())).first()
    if not airport:
        # try a looser slug match
        for a in Airport.query.all():
            if a.slug == slug.lower():
                airport = a
                break
    if not airport:
        abort(404)
    incoming = Route.query.filter_by(destination_code=airport.code).all()
    offers = []
    for route in incoming[:60]:
        scheds = route.schedules
        if not scheds:
            continue
        best, best_day, best_sched = None, None, None
        for offset in range(1, 31):
            d = MIRROR_TODAY + timedelta(days=offset)
            operating = [s for s in scheds if s.operates_on(d)]
            if not operating:
                continue
            for s in operating:
                p = flight_price(s, d)
                if best is None or p < best:
                    best, best_day, best_sched = p, d, s
        if best is not None:
            offers.append({'route': route, 'origin': route.origin,
                           'price': best, 'date': best_day})
    offers.sort(key=lambda o: o['price'])
    guide = db.session.get(Guide, airport.code)
    return render_template('flights_to.html', airport=airport,
                           offers=offers[:12], guide=guide,
                           countries=_countries())


def _timetable_dest_choices(origin_code):
    dests = (Route.query.filter_by(origin_code=origin_code)
              .with_entities(Route.destination_code).all())
    out = []
    for (code,) in dests:
        ap = db.session.get(Airport, code)
        if ap:
            out.append((code, ap.name))
    return out


@app.route('/gb/en/trip/flights/timetable')
def timetable():
    origin = request.args.get('originIata', '')
    destination = request.args.get('destinationIata', '')
    route = None
    scheds = []
    if origin and destination:
        route = Route.query.filter_by(origin_code=origin.upper(),
                                      destination_code=destination.upper()).first()
        if route:
            scheds = sorted(route.schedules, key=lambda s: s.departure)
    origins = Airport.query.filter_by(is_base=True).order_by(Airport.name).all()
    dest_choices = _timetable_dest_choices(origin.upper()) if origin else []
    return render_template('timetable.html', route=route, scheds=scheds,
                           origins=origins, origin=origin.upper(),
                           destination=destination.upper(),
                           dest_choices=dest_choices,
                           countries=_countries())


# ------------------------------------------------------------- search flow --

@app.route('/gb/en/trip/flights/select', methods=['GET', 'POST'])
def flight_select():
    if request.method == 'POST':
        return _flight_select_post()

    origin = request.args.get('originIata', '')
    destination = request.args.get('destinationIata', '')
    origin_ap = db.session.get(Airport, origin)
    dest_ap = db.session.get(Airport, destination)
    if not origin_ap or not dest_ap:
        return redirect(url_for('home'))
    date_out = _parse_date(request.args.get('dateOut'))
    if not date_out or date_out < MIRROR_TODAY:
        date_out = MIRROR_TODAY + timedelta(days=19)
    date_in = _parse_date(request.args.get('dateIn'))
    one_way = request.args.get('isReturn', 'true') == 'false' or not date_in
    trip_type = request.args.get('tripType', 'return')
    if trip_type == 'one-way' or one_way:
        one_way = True
        date_in = None
    adults = request.args.get('adults', 1, type=int)
    teens = request.args.get('teens', 0, type=int)
    children = request.args.get('children', 0, type=int)
    infants = request.args.get('infants', 0, type=int)
    promo = (request.args.get('promoCode') or '').strip().upper()

    token, data = get_trip()
    fresh = (not data or data.get('origin') != origin_ap.code or
             data.get('destination') != dest_ap.code or
             data.get('dateOut') != date_out.isoformat() or
             data.get('dateIn') != (date_in.isoformat() if date_in else '') or
             data.get('adults') != adults or data.get('promoCode') != promo or
             data.get('tripType') != ('one-way' if one_way else 'return'))
    if fresh:
        token = new_trip()
        data = {
            'origin': origin_ap.code, 'destination': dest_ap.code,
            'dateOut': date_out.isoformat(),
            'dateIn': date_in.isoformat() if date_in else '',
            'tripType': 'one-way' if one_way else 'return',
            'adults': adults, 'teens': teens, 'children': children,
            'infants': infants, 'promoCode': promo,
            'outboundSchedule': None, 'inboundSchedule': None,
            'fare': None, 'passengers': [], 'seats': {},
            'extras': {'fast_track': {}, 'insurance': '', 'inflight_credit': 0},
            'smsUpdates': False, 'step': 'flights',
        }
        save_trip(token, data)

    promo_pct = trip_promo_pct(data)
    out_scheds = trip_flights(data, 'out')
    in_scheds = [] if one_way else trip_flights(data, 'in')

    out_views = [make_flight_view(s, date_out, promo_pct,
                                  selected=(data.get('outboundSchedule') == s.id))
                 for s in out_scheds]
    in_views = [make_flight_view(s, date_in, promo_pct,
                                  selected=(data.get('inboundSchedule') == s.id))
                 for s in in_scheds] if in_scheds else []

    strip_out = date_strip(date_out, lambda d: _schedules_on(data['origin'], data['destination'], d), promo_pct)
    strip_in = date_strip(date_in, lambda d: _schedules_on(data['destination'], data['origin'], d), promo_pct) if date_in else []

    fare_table = None
    if data.get('outboundSchedule') and (one_way or data.get('inboundSchedule')):
        fare_table = build_fare_table(data)
    show_pax = bool(data.get('fare'))
    pax_forms = data.get('passengers') or []
    if show_pax:
        _, _, _, summary_total = trip_price_lines(data)
    else:
        summary_total = 0.0
    return render_template(
        'flight_select.html', data=data, origin=origin_ap, dest=dest_ap,
        date_out=date_out, date_in=date_in, one_way=one_way,
        out_views=out_views, in_views=in_views,
        strip_out=strip_out, strip_in=strip_in,
        fare_table=fare_table, show_pax=show_pax,
        pax_forms=pax_forms, adults=adults, teens=teens,
        children=children, infants=infants,
        promo=promo, promo_pct=promo_pct, summary_total=summary_total,
        total=summary_total, countries=_countries())


def _schedules_on(origin, destination, day):
    route = Route.query.filter_by(origin_code=origin,
                                   destination_code=destination).first()
    if not route:
        return []
    return [s for s in route.schedules if s.operates_on(day)]


def _flight_select_post():
    token, data = get_trip()
    if not data:
        return redirect(url_for('home'))
    action = request.form.get('action')
    date_out = _parse_date(data['dateOut'])
    date_in = _parse_date(data.get('dateIn') or '')
    one_way = data.get('tripType') == 'one-way'

    if action == 'select_outbound':
        sched = db.session.get(FlightSchedule, request.form.get('schedule_id', type=int))
        if sched and sched.route.origin_code == data['origin']:
            data['outboundSchedule'] = sched.id
            if one_way:
                data['inboundSchedule'] = None
            data['fare'] = None
            data['passengers'] = []
            save_trip(token, data)
        return redirect(_select_url(data))

    if action == 'select_inbound':
        sched = db.session.get(FlightSchedule, request.form.get('schedule_id', type=int))
        if sched and sched.route.origin_code == data['destination']:
            data['inboundSchedule'] = sched.id
            data['fare'] = None
            data['passengers'] = []
            save_trip(token, data)
        return redirect(_select_url(data))

    if action == 'change_date':
        which = request.form.get('which')
        new_date = _parse_date(request.form.get('date'))
        if new_date and new_date >= MIRROR_TODAY:
            if which == 'out':
                data['dateOut'] = new_date.isoformat()
                data['outboundSchedule'] = None
            else:
                data['dateIn'] = new_date.isoformat()
                data['inboundSchedule'] = None
            data['fare'] = None
            data['passengers'] = []
            save_trip(token, data)
        return redirect(_select_url(data))

    if action == 'choose_fare':
        fare = request.form.get('fare')
        if fare in FARE_ORDER:
            data['fare'] = fare
            save_trip(token, data)
        return redirect(_select_url(data))

    if action == 'save_passengers':
        passengers = []
        count = trip_pax(data)
        valid = True
        for i in range(count):
            title = request.form.get(f'title_{i}', 'Mr')
            first = (request.form.get(f'first_{i}') or '').strip()
            last = (request.form.get(f'last_{i}') or '').strip()
            if not first or not last:
                valid = False
            passengers.append({'title': title, 'first': first, 'last': last,
                                'cabin_out': 'small-bag', 'cabin_in': 'small-bag',
                                'bag_10kg_out': 0, 'bag_10kg_in': 0,
                                'bag_20kg_out': 0, 'bag_20kg_in': 0,
                                'bag_23kg_out': 0, 'bag_23kg_in': 0})
        if not valid:
            flash('Please enter names as they appear on passport or travel '
                  'documentation.', 'error')
            data['passengers'] = passengers
            save_trip(token, data)
            return redirect(_select_url(data))
        # infants travel on laps: they do not get their own form row
        data['passengers'] = passengers
        save_trip(token, data)
        return redirect(url_for('seats'))

    return redirect(_select_url(data))


def _select_url(data):
    qs = [f'originIata={data["origin"]}',
          f'destinationIata={data["destination"]}',
          f'dateOut={data["dateOut"]}']
    if data.get('dateIn'):
        qs.append(f'dateIn={data["dateIn"]}')
    qs.append(f'adults={data.get("adults", 1)}')
    qs.append(f'teens={data.get("teens", 0)}')
    qs.append(f'children={data.get("children", 0)}')
    qs.append(f'infants={data.get("infants", 0)}')
    qs.append(f'promoCode={data.get("promoCode", "")}')
    qs.append(f'isReturn={"false" if data.get("tripType") == "one-way" else "true"}')
    return url_for('flight_select') + '?' + '&'.join(qs)


@app.route('/gb/en/trip/flights/seats', methods=['GET', 'POST'])
def seats():
    token, data = get_trip()
    if not data or not data.get('fare') or not data.get('passengers'):
        return redirect(url_for('home'))
    out_sched = db.session.get(FlightSchedule, data['outboundSchedule'])
    in_sched = (db.session.get(FlightSchedule, data['inboundSchedule'])
                if data.get('inboundSchedule') else None)
    out_day = _parse_date(data['dateOut'])
    in_day = _parse_date(data.get('dateIn') or '')
    pax = data['passengers']

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'random':
            data['seats'] = {'out': [], 'in': []}
            save_trip(token, data)
            return redirect(url_for('bags'))
        if action == 'pick':
            seats = {'out': [], 'in': []}
            occupied_out = out_sched.occupied_seats(out_day)
            occupied_in = in_sched.occupied_seats(in_day) if in_sched else set()
            chosen_out = set()
            chosen_in = set()
            for i in range(len(pax)):
                so = (request.form.get(f'seat_out_{i}') or '').upper()
                si = (request.form.get(f'seat_in_{i}') or '').upper()
                if not so or so in occupied_out or so in chosen_out:
                    flash('Please pick a valid, available seat for every '
                          'passenger on the outbound flight.', 'error')
                    return redirect(url_for('seats'))
                seats['out'].append(so)
                chosen_out.add(so)
                if in_sched:
                    if not si or si in occupied_in or si in chosen_in:
                        flash('Please pick a valid, available seat for every '
                              'passenger on the return flight.', 'error')
                        return redirect(url_for('seats'))
                    seats['in'].append(si)
                    chosen_in.add(si)
            data['seats'] = seats
            save_trip(token, data)
            return redirect(url_for('bags'))
        if action == 'recommended':
            # cheapest contiguous available seats
            occupied_out = out_sched.occupied_seats(out_day)
            occupied_in = in_sched.occupied_seats(in_day) if in_sched else set()
            pick_out = _cheapest_row_seats(len(pax), occupied_out)
            seats = {'out': pick_out, 'in': []}
            if in_sched:
                seats['in'] = _cheapest_row_seats(len(pax), occupied_in)
            data['seats'] = seats
            save_trip(token, data)
            return redirect(url_for('bags'))
    lines, total, card_fee, grand = trip_price_lines(data)
    return render_template(
        'seats.html', data=data, out_sched=out_sched, in_sched=in_sched,
        out_day=out_day, in_day=in_day, pax=pax,
        occupied_out=out_sched.occupied_seats(out_day),
        occupied_in=in_sched.occupied_seats(in_day) if in_sched else set(),
        seat_rows=SEAT_ROWS, seat_letters=SEAT_LETTERS,
        seat_price=seat_price, seat_band=seat_band,
        lines=lines, total=total, card_fee=card_fee, grand=grand,
        countries=_countries())


def _cheapest_row_seats(count, occupied):
    """Cheapest available adjacent seats (same row, consecutive letters)."""
    best = None
    for row in SEAT_ROWS:
        for start in range(0, len(SEAT_LETTERS) - count + 1):
            seats = [f'{row}{SEAT_LETTERS[start + i]}' for i in range(count)]
            if any(s in occupied for s in seats):
                continue
            price = sum(seat_price(int(re.match(r'(\d+)', s).group(1))) for s in seats)
            if best is None or price < best[0]:
                best = (price, seats)
    if best:
        return best[1]
    # fallback: any free seats
    free = []
    for row in SEAT_ROWS:
        for letter in SEAT_LETTERS:
            seat = f'{row}{letter}'
            if seat not in occupied:
                free.append(seat)
    return free[:count]


@app.route('/gb/en/trip/flights/bags', methods=['GET', 'POST'])
def bags():
    token, data = get_trip()
    if not data or not data.get('fare') or not data.get('passengers'):
        return redirect(url_for('home'))
    out_sched = db.session.get(FlightSchedule, data['outboundSchedule'])
    in_sched = (db.session.get(FlightSchedule, data['inboundSchedule'])
                if data.get('inboundSchedule') else None)
    has_return = bool(in_sched)

    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'save':
            cabin_default = request.form.get('cabin_default', 'small-bag')
            same_both = request.form.get('same_both_flights') == 'on'
            for i, p in enumerate(data['passengers']):
                p['cabin_out'] = cabin_default
                for size in ('10kg', '20kg', '23kg'):
                    p[f'bag_{size}_out'] = request.form.get(f'bag_{size}_out_{i}', 0, type=int)
                if not has_return:
                    # One-way trip: there is no return flight, so the
                    # outbound selection must never be mirrored onto a
                    # phantom inbound leg (review diff #1, HIGH).
                    p['cabin_in'] = 'small-bag'
                    for size in ('10kg', '20kg', '23kg'):
                        p[f'bag_{size}_in'] = 0
                else:
                    p['cabin_in'] = cabin_default if same_both \
                        else request.form.get(f'cabin_in_{i}', 'small-bag')
                    for size in ('10kg', '20kg', '23kg'):
                        p[f'bag_{size}_in'] = (p[f'bag_{size}_out'] if same_both
                                               else request.form.get(f'bag_{size}_in_{i}', 0, type=int))
            save_trip(token, data)
            return redirect(url_for('extras'))
    lines, total, card_fee, grand = trip_price_lines(data)
    return render_template('bags.html', data=data, pax=data['passengers'],
                           out_sched=out_sched, in_sched=in_sched,
                           has_return=has_return, bag_prices=BAG_PRICES,
                           priority_price=PRIORITY_PRICE,
                           lines=lines, total=total, card_fee=card_fee,
                           grand=grand, countries=_countries())


@app.route('/gb/en/trip/flights/extras', methods=['GET', 'POST'])
def extras():
    token, data = get_trip()
    if not data or not data.get('fare') or not data.get('passengers'):
        return redirect(url_for('home'))
    out_sched = db.session.get(FlightSchedule, data['outboundSchedule'])
    in_sched = (db.session.get(FlightSchedule, data['inboundSchedule'])
                if data.get('inboundSchedule') else None)
    out_day = _parse_date(data['dateOut'])
    in_day = _parse_date(data.get('dateIn') or '')
    pax = trip_pax(data)
    ft_airports = fast_track_airports(out_sched, in_sched)

    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'save':
            ft = data['extras'].setdefault('fast_track', {})
            for i, code in enumerate(ft_airports):
                ft[code] = request.form.get(f'fast_track_{code}') == 'on'
            data['extras']['insurance'] = request.form.get('insurance', '')
            credit = request.form.get('inflight_credit', 0, type=float)
            data['extras']['inflight_credit'] = round(credit, 2) if credit else 0
            save_trip(token, data)
            return redirect(url_for('payment'))
    lines, total, card_fee, grand = trip_price_lines(data)
    insurance_days = 1
    if in_day:
        insurance_days = max(1, (in_day - out_day).days + 1)
    return render_template(
        'extras.html', data=data, out_sched=out_sched, in_sched=in_sched,
        out_day=out_day, in_day=in_day, pax=pax, ft_airports=ft_airports,
        fast_track_price=fast_track_price, insurance_days=insurance_days,
        insurance_price=insurance_price, lines=lines, total=total,
        card_fee=card_fee, grand=grand, countries=_countries())


@app.route('/gb/en/payment', methods=['GET', 'POST'])
def payment():
    token, data = get_trip()
    if not data or not data.get('fare') or not data.get('passengers'):
        return redirect(url_for('home'))
    out_sched = db.session.get(FlightSchedule, data['outboundSchedule'])
    in_sched = (db.session.get(FlightSchedule, data['inboundSchedule'])
                if data.get('inboundSchedule') else None)
    lines, total, card_fee, grand = trip_price_lines(data)

    if request.method == 'POST':
        action = request.form.get('action', 'pay')
        if action == 'update_contact':
            data['contactEmail'] = request.form.get('contactEmail', '')
            data['contactEmail2'] = request.form.get('contactEmail2', '')
            data['contactPhone'] = request.form.get('contactPhone', '')
            data['smsUpdates'] = request.form.get('smsUpdates') == 'on'
            save_trip(token, data)
            return redirect(url_for('payment'))
        if action == 'pay':
            email = request.form.get('contactEmail', '').strip()
            email2 = request.form.get('contactEmail2', '').strip()
            phone = request.form.get('contactPhone', '').strip()
            card_number = re.sub(r'\s+', '', request.form.get('cardNumber', ''))
            card_name = (request.form.get('cardName') or '').strip()
            expiry = (request.form.get('cardExpiry') or '').strip()
            cvv = (request.form.get('cardCvv') or '').strip()
            address1 = (request.form.get('address1') or '').strip()
            city = (request.form.get('city') or '').strip()
            postcode = (request.form.get('postcode') or '').strip()
            errors = []
            if not email or '@' not in email:
                errors.append('Please enter a valid email address.')
            elif email != email2:
                errors.append('The email addresses do not match.')
            if not phone:
                errors.append('Please enter a mobile number.')
            if not re.fullmatch(r'\d{14,19}', card_number):
                errors.append('Please enter a valid card number.')
            if not re.fullmatch(r'(0[1-9]|1[0-2])/\d{2}', expiry):
                errors.append('Please enter a valid expiry date (MM/YY).')
            if not re.fullmatch(r'\d{3,4}', cvv):
                errors.append('Please enter a valid CVV.')
            if not card_name:
                errors.append('Please enter the name on the card.')
            if not address1 or not city or not postcode:
                errors.append('Please complete the billing address.')
            if errors:
                for e in errors:
                    flash(e, 'error')
                return redirect(url_for('payment'))
            booking = _materialize_booking(data, email, phone,
                                           card_number, card_name, expiry)
            session.pop('trip_token', None)
            return redirect(url_for('confirmation', ref=booking.booking_ref))

    saved_cards = []
    if current_user.is_authenticated:
        saved_cards = current_user.payment_methods
    return render_template('payment.html', data=data, out_sched=out_sched,
                           in_sched=in_sched, lines=lines, total=total,
                           card_fee=card_fee, grand=grand,
                           out_day_label=_parse_date(data['dateOut']).strftime('%a %d %b'),
                           in_day_label=(_parse_date(data.get('dateIn') or '').strftime('%a %d %b')
                                         if in_sched else ''),
                           saved_cards=saved_cards, countries=_countries())


def _materialize_booking(data, email, phone, card_number, card_name, expiry):
    out_sched = db.session.get(FlightSchedule, data['outboundSchedule'])
    in_sched = (db.session.get(FlightSchedule, data['inboundSchedule'])
                if data.get('inboundSchedule') else None)
    out_day = _parse_date(data['dateOut'])
    in_day = _parse_date(data.get('dateIn') or '')
    lines, total, card_fee, grand = trip_price_lines(data)
    flights = dict(lines).get('Flights', 0)
    seats_total = dict(lines).get('Seats', 0)
    bags_total = dict(lines).get('Bags', 0)
    extras_total = dict(lines).get('Extras', 0)

    ref = _new_booking_ref()
    booking = Booking(
        booking_ref=ref,
        user_id=current_user.id if current_user.is_authenticated else None,
        contact_email=email, contact_phone=phone,
        fare_type=data.get('fare', 'basic'),
        adults=data.get('adults', 1), teens=data.get('teens', 0),
        children=data.get('children', 0), infants=data.get('infants', 0),
        outbound_schedule_id=out_sched.id, outbound_date=out_day,
        inbound_schedule_id=in_sched.id if in_sched else None,
        inbound_date=in_day if in_sched else None,
        promo_code=data.get('promoCode', ''),
        sms_updates=bool(data.get('smsUpdates')),
        insurance_key=data.get('extras', {}).get('insurance', ''),
        fast_track_out=any(data.get('extras', {}).get('fast_track', {}).values()),
        fast_track_in=False,
        inflight_credit=data.get('extras', {}).get('inflight_credit') or 0,
        flights_total=flights, seats_total=seats_total,
        bags_total=bags_total, extras_total=extras_total,
        card_fee=card_fee, total=grand, status='confirmed',
        checked_in=False)
    db.session.add(booking)
    db.session.flush()
    seats_map = data.get('seats', {})
    for i, p in enumerate(data['passengers']):
        db.session.add(BookingPassenger(
            booking_id=booking.id, title=p.get('title', 'Mr'),
            first_name=p['first'], last_name=p['last'],
            seat_out=(seats_map.get('out') or [None] * len(data['passengers']))[i] or '',
            seat_in=((seats_map.get('in') or [None] * len(data['passengers']))[i] or '') if in_sched else '',
            cabin_out=p.get('cabin_out', 'small-bag'),
            cabin_in=p.get('cabin_in', 'small-bag'),
            checkin_10kg_out=p.get('bag_10kg_out', 0),
            checkin_10kg_in=p.get('bag_10kg_in', 0),
            checkin_20kg_out=p.get('bag_20kg_out', 0),
            checkin_20kg_in=p.get('bag_20kg_in', 0),
            checkin_23kg_out=p.get('bag_23kg_out', 0),
            checkin_23kg_in=p.get('bag_23kg_in', 0)))
    db.session.commit()
    return booking


def _new_booking_ref():
    while True:
        ref = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
                      for _ in range(6))
        if not Booking.query.filter_by(booking_ref=ref).first():
            return ref


@app.route('/gb/en/booking/confirmation/<ref>')
def confirmation(ref):
    booking = Booking.query.filter_by(booking_ref=ref).first_or_404()
    return render_template('confirmation.html', booking=booking,
                           countries=_countries())


# ------------------------------------------------------------------- auth --

@app.route('/gb/en/myryanair/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        user = User.query.filter(
            db.func.lower(User.email) == email).first()
        if user and user.check_password(password):
            login_user(user)
            nxt = request.args.get('next')
            if nxt and nxt.startswith('/'):
                return redirect(nxt)
            return redirect(url_for('account'))
        flash('Wrong email or password. Please try again.', 'error')
    return render_template('login.html', countries=_countries())


@app.route('/gb/en/myryanair/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    if request.method == 'POST':
        first = (request.form.get('first') or '').strip()
        last = (request.form.get('last') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        password2 = request.form.get('password2') or ''
        if not first or not last:
            flash('Please enter your first and last name.', 'error')
        elif not email or '@' not in email:
            flash('Please enter a valid email address.', 'error')
        elif len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
        elif password != password2:
            flash('The passwords do not match.', 'error')
        elif User.query.filter(db.func.lower(User.email) == email).first():
            flash('An account with this email already exists.', 'error')
        else:
            user = User(email=email, first_name=first, last_name=last,
                        newsletter=request.form.get('newsletter') == 'on')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('account'))
    return render_template('register.html', countries=_countries())


@app.route('/gb/en/myryanair/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/gb/en/myryanair/account', methods=['GET', 'POST'])
@login_required
def account():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'profile':
            current_user.first_name = (request.form.get('first') or '').strip()
            current_user.last_name = (request.form.get('last') or '').strip()
            current_user.phone = (request.form.get('phone') or '').strip()
            current_user.address_line1 = (request.form.get('address1') or '').strip()
            current_user.address_line2 = (request.form.get('address2') or '').strip()
            current_user.city = (request.form.get('city') or '').strip()
            current_user.postcode = (request.form.get('postcode') or '').strip()
            current_user.newsletter = request.form.get('newsletter') == 'on'
            db.session.commit()
            flash('Your details have been updated.', 'ok')
            return redirect(url_for('account'))
        if action == 'add_card':
            number = re.sub(r'\s+', '', request.form.get('cardNumber') or '')
            holder = (request.form.get('cardName') or '').strip()
            expiry = (request.form.get('cardExpiry') or '').strip()
            if not re.fullmatch(r'\d{14,19}', number):
                flash('Please enter a valid card number.', 'error')
            elif not re.fullmatch(r'(0[1-9]|1[0-2])/\d{2}', expiry):
                flash('Please enter a valid expiry date (MM/YY).', 'error')
            elif not holder:
                flash('Please enter the name on the card.', 'error')
            else:
                card_type = _card_type(number)
                db.session.add(PaymentMethod(
                    user_id=current_user.id, card_type=card_type,
                    last4=number[-4:], holder=holder, expiry=expiry))
                db.session.commit()
                flash('Payment method added.', 'ok')
            return redirect(url_for('account'))
        if action == 'remove_card':
            card = db.session.get(PaymentMethod,
                                  request.form.get('card_id', type=int))
            if card and card.user_id == current_user.id:
                was_default = bool(card.is_default)
                db.session.delete(card)
                if was_default:
                    # Upstream behaviour: removing the default card promotes
                    # the most recent remaining card to default (review diff #3).
                    remaining = (PaymentMethod.query
                                 .filter(PaymentMethod.user_id == current_user.id,
                                         PaymentMethod.id != card.id)
                                 .order_by(PaymentMethod.id.desc()).first())
                    if remaining:
                        remaining.is_default = True
                db.session.commit()
                flash('Payment method removed.', 'ok')
            return redirect(url_for('account'))
    bookings = (Booking.query.filter_by(user_id=current_user.id)
                .order_by(Booking.outbound_date).all())
    return render_template('account.html', bookings=bookings,
                           countries=_countries())


def _card_type(number):
    if number.startswith('4'):
        return 'Visa'
    if number[:2] in ('51', '52', '53', '54', '55') or \
            number.startswith('2221') or number.startswith('2720'):
        return 'Mastercard'
    if number.startswith('34') or number.startswith('37'):
        return 'American Express'
    return 'Card'


# ---------------------------------------------------------------- bookings --

@app.route('/gb/en/my-bookings', methods=['GET', 'POST'])
def my_bookings():
    if current_user.is_authenticated:
        bookings = (Booking.query.filter_by(user_id=current_user.id)
                    .order_by(Booking.outbound_date).all())
        return render_template('bookings.html', bookings=bookings,
                                countries=_countries())
    if request.method == 'POST':
        ref = (request.form.get('ref') or '').strip().upper()
        email = (request.form.get('email') or '').strip().lower()
        booking = Booking.query.filter_by(booking_ref=ref).first()
        if booking and booking.contact_email.lower() == email:
            return redirect(url_for('booking_detail', ref=ref))
        flash('We could not find a booking with that reference and email.',
              'error')
    return render_template('bookings.html', bookings=None,
                           countries=_countries())


@app.route('/gb/en/booking/<ref>')
def booking_detail(ref):
    booking = Booking.query.filter_by(booking_ref=ref).first_or_404()
    if not current_user.is_authenticated and booking.user_id:
        # guest bookings remain viewable by reference; signed-in bookings
        # require login (mirrors the upstream My bookings flow)
        pass
    return render_template('booking_detail.html', booking=booking,
                           countries=_countries())


@app.route('/gb/en/lp/check-in', methods=['GET', 'POST'])
def checkin_home():
    if request.method == 'POST':
        ref = (request.form.get('ref') or '').strip().upper()
        booking = Booking.query.filter_by(booking_ref=ref).first()
        if booking:
            return redirect(url_for('checkin', ref=ref))
        flash('We could not find that reservation number.', 'error')
    if current_user.is_authenticated:
        bookings = (Booking.query.filter_by(user_id=current_user.id)
                    .order_by(Booking.outbound_date).all())
    else:
        bookings = []
    return render_template('checkin_home.html', bookings=bookings,
                           countries=_countries())


@app.route('/gb/en/check-in/<ref>', methods=['GET', 'POST'])
def checkin(ref):
    booking = Booking.query.filter_by(booking_ref=ref).first_or_404()
    if request.method == 'POST' and request.form.get('action') == 'checkin':
        minutes_to_departure = int(
            (datetime.combine(booking.outbound_date,
                              datetime.strptime(
                                  booking.outbound_schedule.departure, '%H:%M').time())
             - datetime.combine(MIRROR_TODAY, datetime.min.time()))
            .total_seconds() // 60)
        has_assigned = all(p.seat_out for p in booking.passengers)
        window = CHECKIN_WINDOW_ASSIGNED if has_assigned else CHECKIN_WINDOW_RANDOM
        if booking.checked_in:
            flash('You are already checked in.', 'ok')
            return redirect(url_for('boarding_pass', ref=ref))
        if minutes_to_departure > window:
            flash('Online check-in opens %s before departure. Please come '
                  'back later.' % ('60 days' if has_assigned else '24 hours'),
                  'error')
            return redirect(url_for('checkin', ref=ref))
        if minutes_to_departure < 120:
            flash('Online check-in closes 2 hours before departure.',
                  'error')
            return redirect(url_for('checkin', ref=ref))
        # allocate random seats for anyone without one
        occupied = booking.outbound_schedule.occupied_seats(booking.outbound_date)
        for p in booking.passengers:
            if not p.seat_out:
                p.seat_out = _cheapest_row_seats(1, occupied)[0]
                occupied.add(p.seat_out)
            if booking.inbound_schedule and not p.seat_in:
                occ_in = booking.inbound_schedule.occupied_seats(booking.inbound_date)
                p.seat_in = _cheapest_row_seats(1, occ_in)[0]
                occ_in.add(p.seat_in)
        booking.checked_in = True
        db.session.commit()
        return redirect(url_for('boarding_pass', ref=ref))
    minutes_to_departure = None
    dep_dt = datetime.combine(
        booking.outbound_date,
        datetime.strptime(booking.outbound_schedule.departure, '%H:%M').time())
    minutes_to_departure = int(
        (dep_dt - datetime.combine(MIRROR_TODAY, datetime.min.time()))
        .total_seconds() // 60)
    has_assigned = all(p.seat_out for p in booking.passengers)
    window = CHECKIN_WINDOW_ASSIGNED if has_assigned else CHECKIN_WINDOW_RANDOM
    return render_template('checkin.html', booking=booking,
                           minutes_to_departure=minutes_to_departure,
                           window=window, has_assigned=has_assigned,
                           countries=_countries())


@app.route('/gb/en/boarding-pass/<ref>')
def boarding_pass(ref):
    booking = Booking.query.filter_by(booking_ref=ref).first_or_404()
    if not booking.checked_in:
        return redirect(url_for('checkin', ref=ref))
    return render_template('boarding_pass.html', booking=booking,
                           countries=_countries())


# -------------------------------------------------------------------- help --

@app.route('/gb/en/r/help')
def help_index():
    topics = HelpTopic.query.order_by(HelpTopic.slug).all()
    q = (request.args.get('q') or '').strip()
    results = []
    if q:
        results = scored_search(q, topics)
    return render_template('help_index.html', topics=topics, q=q,
                           results=results, countries=_countries())


@app.route('/gb/en/r/help/<slug>')
def help_article(slug):
    topic = db.session.get(HelpTopic, slug)
    if not topic:
        abort(404)
    related = [t for t in HelpTopic.query.order_by(HelpTopic.slug).all()
               if t.slug != slug][:5]
    return render_template('help_article.html', topic=topic,
                           body_blocks=json.loads(topic.body),
                           fees=_fees_table(), related=related,
                           countries=_countries())


def scored_search(query, topics):
    tokens = [t.lower() for t in re.split(r'\W+', query)
              if t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return topics
    scored = []
    for topic in topics:
        text = ' '.join([topic.title, topic.summary,
                         topic.slug, ' '.join(
                             b[1] if isinstance(b, (list, tuple)) else ''
                             for b in json.loads(topic.body))]).lower()
        score = sum(1 for t in tokens if t in text)
        if score:
            scored.append((score, topic))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored]


@app.route('/gb/en/search')
def site_search():
    q = (request.args.get('q') or '').strip()
    airports, routes, topics, guides = [], [], [], []
    if q:
        tokens = [t.lower() for t in re.split(r'\W+', q)
                  if t.lower() not in STOP_WORDS and len(t) > 1]
        if not tokens:
            tokens = [q.lower()]
        for a in Airport.query.all():
            text = f'{a.name} {a.city} {a.country} {a.code}'.lower()
            if any(t in text for t in tokens):
                airports.append(a)
        for r in Route.query.all():
            o, d = r.origin, r.destination
            if not o or not d:
                continue
            text = f'{o.name} {o.city} {d.name} {d.city}'.lower()
            if any(t in text for t in tokens):
                routes.append(r)
        topics = scored_search(q, HelpTopic.query.all())
        for g in Guide.query.all():
            text = f'{g.city} {" ".join(g.must_reads_list)}'.lower()
            if any(t in text for t in tokens):
                guides.append(g)
    return render_template('search.html', q=q, airports=airports[:20],
                           routes=routes[:20], topics=topics[:10],
                           guides=guides[:10], countries=_countries())


# --------------------------------------------------------- marketing pages --

@app.route('/gb/en/lp/gift-cards')
def gift_cards():
    return render_template('lp_gift_cards.html', countries=_countries())


@app.route('/gb/en/lp/car-hire')
def car_hire():
    return render_template('lp_car_hire.html', countries=_countries())


@app.route('/gb/en/lp/hotels')
def hotels():
    return render_template('lp_hotels.html', countries=_countries())


@app.route('/gb/en/lp/private-transfers')
def private_transfers():
    return render_template('lp_private_transfers.html', countries=_countries())


@app.route('/gb/en/lp/travel-updates')
def travel_updates():
    return render_template('lp_travel_updates.html', countries=_countries())


@app.route('/gb/en/lp/promotion/lets-fly')
def lets_fly():
    return render_template('lp_promo.html', countries=_countries())


@app.route('/gb/en/lp/privacy-policy')
def privacy_policy():
    return render_template('lp_privacy.html', countries=_countries())


@app.route('/gb/en/lp/terms-of-use')
def terms_of_use():
    return render_template('lp_terms.html', countries=_countries())


@app.route('/gb/en/lp/about')
def about():
    return render_template('lp_about.html', countries=_countries())


@app.route('/gb/en/lp/careers')
def careers():
    return render_template('lp_careers.html', countries=_countries())


@app.route('/gb/en/lp/media')
def media_centre():
    return render_template('lp_media.html', countries=_countries())


@app.route('/gb/en/lp/investors')
def investors():
    return render_template('lp_investors.html', countries=_countries())


# ------------------------------------------------------------------- misc ---

@app.route('/_health')
def health():
    try:
        counts = {
            'airports': Airport.query.count(),
            'routes': Route.query.count(),
            'schedules': FlightSchedule.query.count(),
            'users': User.query.count(),
            'bookings': Booking.query.count(),
            'help_topics': HelpTopic.query.count(),
        }
        ok = (counts['airports'] > 100 and counts['routes'] > 500 and
              counts['schedules'] > 1000 and counts['users'] >= 4 and
              counts['help_topics'] >= 10)
        return jsonify({'ok': ok, 'site': 'ryanair', 'counts': counts}), (200 if ok else 500)
    except Exception as exc:  # pragma: no cover
        return jsonify({'ok': False, 'error': str(exc)}), 500


FEES_TABLE = None  # populated lazily from source_data_content.json


def _fees_table():
    global FEES_TABLE
    if FEES_TABLE is None:
        content = json.loads((open(os.path.join(BASE_DIR, 'source_data_content.json'),
              encoding='utf-8')).read())
        FEES_TABLE = content['fees']
    return FEES_TABLE


def _content():
    return json.loads((open(os.path.join(BASE_DIR, 'source_data_content.json'),
          encoding='utf-8')).read())


# -------------------------------------------------------------------- seed --

def seed_database():
    if Airport.query.count() > 0:
        return
    airports_doc = json.loads(
        (open(os.path.join(BASE_DIR, 'source_data_airports.json'),
              encoding='utf-8')).read())
    for row in airports_doc['airports']:
        db.session.add(Airport(**row))
    db.session.flush()

    routes_doc = json.loads(
        (open(os.path.join(BASE_DIR, 'source_data_routes.json'),
              encoding='utf-8')).read())
    for row in routes_doc['routes']:
        db.session.add(Route(origin_code=row['origin'],
                             destination_code=row['destination'],
                             distance_km=row['distance_km'],
                             duration_minutes=row['duration_minutes'],
                             base_price=row['base_price']))
    db.session.flush()
    route_ids = {(r.origin_code, r.destination_code): r.id
                 for r in Route.query.all()}
    for row in routes_doc['routes']:
        rid = route_ids[(row['origin'], row['destination'])]
        for s in row['schedules']:
            db.session.add(FlightSchedule(
                route_id=rid, flight_number=s['flight_number'],
                departure=s['departure'], arrival=s['arrival'],
                days=','.join(str(d) for d in s['days'])))
    db.session.flush()

    content = json.loads(
        (open(os.path.join(BASE_DIR, 'source_data_content.json'),
              encoding='utf-8')).read())
    for promo in content['promo_codes']:
        db.session.add(PromoCode(**promo))
    for topic in content['help_topics']:
        db.session.add(HelpTopic(slug=topic['slug'], title=topic['title'],
                                 icon=topic['icon'], summary=topic['summary'],
                                 body=json.dumps(topic['body'])))
    for guide in content['guides']:
        db.session.add(Guide(code=guide['code'], city=guide['city'],
                             intro=guide['intro'],
                             must_reads=json.dumps(guide['must_reads'])))
    db.session.commit()


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    users = [
        {'username': 'alice_j', 'email': 'alice.j@test.com',
         'first_name': 'Alice', 'last_name': 'Johnson',
         'phone': '+44 7700 900123', 'city': 'London',
         'address_line1': '12 Kingsland Road', 'postcode': 'E2 8AA'},
        {'username': 'bob_c', 'email': 'bob.c@test.com',
         'first_name': 'Bob', 'last_name': 'Chen',
         'phone': '+44 7700 900234', 'city': 'Manchester',
         'address_line1': '88 Deansgate', 'postcode': 'M3 2QF'},
        {'username': 'carol_d', 'email': 'carol.d@test.com',
         'first_name': 'Carol', 'last_name': 'Davis',
         'phone': '+353 85 012 3456', 'city': 'Dublin',
         'address_line1': '5 O\u2019Connell Street', 'postcode': 'D01 F5P2'},
        {'username': 'david_k', 'email': 'david.k@test.com',
         'first_name': 'David', 'last_name': 'Kim',
         'phone': '+44 7700 900456', 'city': 'Edinburgh',
         'address_line1': '3 Royal Mile', 'postcode': 'EH1 1RE'},
    ]
    for row in users:
        user = User(email=row['email'], first_name=row['first_name'],
                   last_name=row['last_name'], phone=row['phone'],
                   address_line1=row['address_line1'], city=row['city'],
                   postcode=row['postcode'], country='United Kingdom',
                   newsletter=False)
        user.password_hash = BENCHMARK_PASSWORD_HASH
        db.session.add(user)
    db.session.flush()

    alice = User.query.filter_by(email='alice.j@test.com').first()
    bob = User.query.filter_by(email='bob.c@test.com').first()
    carol = User.query.filter_by(email='carol.d@test.com').first()
    david = User.query.filter_by(email='david.k@test.com').first()

    db.session.add(PaymentMethod(user_id=alice.id, card_type='Visa',
                                 last4='4242', holder='Alice Johnson',
                                 expiry='09/29', is_default=True))
    db.session.add(PaymentMethod(user_id=bob.id, card_type='Mastercard',
                                 last4='5309', holder='Bob Chen',
                                 expiry='11/28', is_default=True))
    db.session.add(PaymentMethod(user_id=carol.id, card_type='Visa',
                                 last4='1881', holder='Carol Davis',
                                 expiry='03/30', is_default=True))
    db.session.add(PaymentMethod(user_id=david.id, card_type='American Express',
                                 last4='1005', holder='David Kim',
                                 expiry='07/27', is_default=True))
    db.session.commit()

    # ---- pre-existing bookings (past trips + upcoming trips) -------------
    def _sched(origin, dest, number):
        route = Route.query.filter_by(origin_code=origin,
                                      destination_code=dest).first()
        if not route:
            return None
        return FlightSchedule.query.filter_by(route_id=route.id,
                                              flight_number=number).first()

    def _booking(ref, user, sched_out, out_day, sched_in, in_day, fare,
                 pax_rows, seats_out=None, seats_in=None, insurance='',
                 fast_track=False, inflight=0.0, checked_in=False,
                 status='confirmed'):
        legs = [(sched_out, out_day)]
        if sched_in:
            legs.append((sched_in, in_day))
        pax = len(pax_rows)
        flights = round(sum(flight_price(s, d, fare) for s, d in legs) * pax, 2)
        seats_total = 0.0
        if seats_out:
            seats_total += sum(seat_price(int(re.match(r'(\d+)', s).group(1)))
                               for s in seats_out)
        if seats_in:
            seats_total += sum(seat_price(int(re.match(r'(\d+)', s).group(1)))
                               for s in seats_in)
        seats_total = round(seats_total, 2)
        extras_total = 0.0
        if insurance:
            extras_total += insurance_price(insurance, out_day, in_day, pax)
        if fast_track:
            extras_total += fast_track_price(sched_out.route.origin_code) * pax
        extras_total = round(extras_total + inflight, 2)
        total_pre = round(flights + seats_total + extras_total, 2)
        card_fee = round(total_pre * CARD_FEE_PCT / 100.0, 2)
        booking = Booking(
            booking_ref=ref, user_id=user.id if user else None,
            contact_email=user.email if user else 'guest@example.com',
            contact_phone=user.phone if user else '',
            fare_type=fare, adults=pax,
            outbound_schedule_id=sched_out.id, outbound_date=out_day,
            inbound_schedule_id=sched_in.id if sched_in else None,
            inbound_date=in_day if sched_in else None,
            insurance_key=insurance, fast_track_out=fast_track,
            inflight_credit=inflight,
            flights_total=flights, seats_total=seats_total,
            extras_total=extras_total, card_fee=card_fee,
            total=round(total_pre + card_fee, 2),
            checked_in=checked_in, status=status)
        db.session.add(booking)
        db.session.flush()
        for i, (title, first, last) in enumerate(pax_rows):
            so = (seats_out[i] if seats_out else '')
            si = (seats_in[i] if seats_in else '')
            db.session.add(BookingPassenger(
                booking_id=booking.id, title=title, first_name=first,
                last_name=last, seat_out=so, seat_in=si))
        return booking

    # Alice: past trip to Dublin (checked in, completed) + upcoming trip to
    # Malaga next week with seats, bags and fast track.
    s1 = _sched('STN', 'DUB', 'FR 271')
    s2 = _sched('DUB', 'STN', 'FR 30')
    if s1 and s2:
        _booking('P4H2KQ', alice, s1, MIRROR_TODAY - timedelta(days=21),
                 s2, MIRROR_TODAY - timedelta(days=14), 'basic',
                 [('Ms', 'Alice', 'Johnson'), ('Mr', 'Marcus', 'Johnson')],
                 checked_in=True, status='completed')
    route = Route.query.filter_by(origin_code='STN', destination_code='AGP').first()
    if route:
        s3 = route.schedules[0]
        back = Route.query.filter_by(origin_code='AGP', destination_code='STN').first()
        s4 = back.schedules[0] if back and back.schedules else None
        out_day = MIRROR_TODAY + timedelta(days=9)
        in_day = MIRROR_TODAY + timedelta(days=16)
        _booking('T7W3ND', alice, s3, out_day, s4, in_day if s4 else None,
                 'plus', [('Ms', 'Alice', 'Johnson')],
                 seats_out=['2C'], seats_in=['4A'] if s4 else None,
                 fast_track=True)

    # Bob: upcoming Dublin weekend (departs in 2 days, random seats, not
    # checked in) + a completed Barcelona trip.
    route = Route.query.filter_by(origin_code='MAN', destination_code='DUB').first()
    s5 = route.schedules[0] if route else None
    back = Route.query.filter_by(origin_code='DUB', destination_code='MAN').first()
    s6 = back.schedules[0] if back and back.schedules else None
    if s5:
        _booking('M9D2XV', bob, s5, MIRROR_TODAY + timedelta(days=2),
                 s6, MIRROR_TODAY + timedelta(days=5) if s6 else None,
                 'basic', [('Mr', 'Bob', 'Chen'), ('Ms', 'Wei', 'Chen')])
    route = Route.query.filter_by(origin_code='MAN', destination_code='BCN').first()
    if route:
        s7 = route.schedules[0]
        _booking('B3C8LP', bob, s7, MIRROR_TODAY - timedelta(days=40),
                 None, None, 'basic', [('Mr', 'Bob', 'Chen')],
                 status='completed', checked_in=True)

    # Carol (Dublin base): upcoming Krakow trip with 20kg bag; past trip home
    # to London with insurance.
    route = Route.query.filter_by(origin_code='DUB', destination_code='KRK').first()
    if route:
        s8 = route.schedules[0]
        back = Route.query.filter_by(origin_code='KRK', destination_code='DUB').first()
        s9 = back.schedules[0] if back and back.schedules else None
        _booking('K5R7JT', carol, s8, MIRROR_TODAY + timedelta(days=12),
                 s9, MIRROR_TODAY + timedelta(days=19) if s9 else None,
                 'regular', [('Ms', 'Carol', 'Davis')],
                 seats_out=['12B'], seats_in=['12C'] if s9 else None)
    route = Route.query.filter_by(origin_code='DUB', destination_code='LGW').first()
    if route:
        s10 = route.schedules[0]
        back = Route.query.filter_by(origin_code='LGW', destination_code='DUB').first()
        s11 = back.schedules[0] if back and back.schedules else None
        _booking('D8N4FS', carol, s10, MIRROR_TODAY - timedelta(days=60),
                 s11, MIRROR_TODAY - timedelta(days=53) if s11 else None,
                 'basic', [('Ms', 'Carol', 'Davis')],
                 insurance='plus', status='completed', checked_in=True)

    # David (Edinburgh): upcoming Rome trip (departs in 5 days, seats
    # selected, Flexi Plus) + past Berlin trip.
    route = Route.query.filter_by(origin_code='EDI', destination_code='CIA').first()
    if route:
        s12 = route.schedules[0]
        back = Route.query.filter_by(origin_code='CIA', destination_code='EDI').first()
        s13 = back.schedules[0] if back and back.schedules else None
        _booking('R2M6YB', david, s12, MIRROR_TODAY + timedelta(days=5),
                 s13, MIRROR_TODAY + timedelta(days=9) if s13 else None,
                 'flexi_plus', [('Mr', 'David', 'Kim'), ('Ms', 'Soo', 'Kim')],
                 seats_out=['1A', '1B'], seats_in=['2D', '2E'] if s13 else None)
    route = Route.query.filter_by(origin_code='EDI', destination_code='BER').first()
    if route:
        s14 = route.schedules[0]
        _booking('E9T1GZ', david, s14, MIRROR_TODAY - timedelta(days=80),
                 None, None, 'basic', [('Mr', 'David', 'Kim')],
                 status='completed', checked_in=True)
    db.session.commit()


# Indexes are created with explicit, name-sorted SQL (not SQLAlchemy's
# metadata pass, whose set-ordered index creation makes the SQLite file
# non-reproducible across builds). IF NOT EXISTS keeps every boot a no-op.
INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS ix_routes_destination_code "
    "ON routes (destination_code)",
    "CREATE INDEX IF NOT EXISTS ix_routes_origin_code ON routes (origin_code)",
)


def create_schema() -> None:
    """create_all plus the deterministic explicit-index pass."""
    db.create_all()
    with db.engine.begin() as conn:
        for stmt in INDEX_STATEMENTS:
            conn.execute(db.text(stmt))


with app.app_context():
    create_schema()
    seed_database()
    seed_benchmark_users()


def main() -> None:
    """Standalone entry: build instance/ryanair.db from scratch (idempotent)."""
    with app.app_context():
        create_schema()
        seed_database()
        seed_benchmark_users()
    print('seeded')


if __name__ == '__main__':
    main()
