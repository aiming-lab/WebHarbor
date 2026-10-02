#!/usr/bin/env python3
"""United Airlines mirror — Flask application.

Mirrors https://www.united.com/ (en/us): the home booking widget, flight
search with United's fare families (Basic Economy / United Economy /
Economy Plus / Premium Plus / United First / United Business), the booking
chain with card and award-mile payment, My Trips (lookup by confirmation
number, seat changes, bag fees, flight changes and cancellations), online
check-in with per-aircraft seat maps and boarding passes, flight status by
number and by route, the baggage hub with the checked-bag fee calculator,
the MileagePlus domain (join, sign in, dashboard with award miles +
Premier qualification progress, activity ledger), cabin experience pages,
the fleet, airport guides, the help center with scored FAQ search, and the
change/cancel policy pages.

All runtime data comes from the SQLite seed built deterministically from the
tracked source_data_*.json snapshots captured from united.com on
2026-09-28 (see scripts_dev/build_source_data.py).
"""
import hashlib
import json
import math
import os
import random
import re
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get(
    "UNITED_AIRLINES_SECRET_KEY") or "webharbor-united-airlines-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'UNITED_AIRLINES_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'united_airlines.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)


@app.template_filter('from_json')
def _from_json(value):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


@app.template_filter('nl2br')
def _nl2br(value):
    from markupsafe import Markup, escape
    return Markup(str(escape(value)).replace('\n', '<br>'))
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'mp_signin'
login_manager.login_message = 'Please sign in to access your account.'
csrf = CSRFProtect(app)

# The mirror is a snapshot of the upstream site taken on 2026-09-28.
MIRROR_TODAY = date(2026, 9, 28)
MIRROR_DATE = datetime(2026, 9, 28, 12, 0, 0)
BOOKING_HORIZON_DAYS = 330
CHECKIN_OPEN_MINUTES = 24 * 60            # check-in opens 24h before departure
CHECKIN_CLOSE_MINUTES = 60               # closes 1h before departure
# bcrypt hash of 'TestPass123!' — frozen so the SQLite seed is byte-reproducible.
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')

# United fare families in display order (real names; see the cabin pages).
FARE_FAMILIES = [
    ('BE', 'Basic Economy'),
    ('ECO', 'United Economy®'),
    ('EPU', 'Economy Plus®'),
    ('PP', 'Premium Plus®'),
    ('BUS', 'United Business® / United First®'),
]
CABIN_CODES = {'BE': 'economy', 'ECO': 'economy', 'EPU': 'economy-plus',
               'PP': 'premium-plus', 'BUS': 'business-first'}
# Award miles needed per cabin on the frozen route network (see
# source_data_content.json award charts) — handled per route at runtime.
AWARD_MILES_PER_USD = 100                 # miles needed per $1 of fare value

PREMIER_TIERS = ['Member', 'Premier Silver', 'Premier Gold',
                 'Premier Platinum', 'Premier 1K®']
MILES_EARN_RATE = {'Member': 5, 'Premier Silver': 7, 'Premier Gold': 8,
                   'Premier Platinum': 9, 'Premier 1K®': 11}

# Premier qualification thresholds + tier benefits, frozen from the
# upstream premier program pages (see source_data_content.json):
#   Silver 12 PQF + 4,000 PQP (or 5,000 PQP), Gold 24 + 8,000 (or 10,000),
#   Platinum 36 + 12,000 (or 15,000), 1K 54 + 18,000 (or 24,000).
PREMIER_QUALIFICATION = {
    'Member': (0, 0),
    'Premier Silver': (12, 4000),
    'Premier Gold': (24, 8000),
    'Premier Platinum': (36, 12000),
    'Premier 1K®': (54, 18000),
}
PREMIER_PQP_ONLY = {'Premier Silver': 5000, 'Premier Gold': 10000,
                     'Premier Platinum': 15000, 'Premier 1K®': 24000}
# Free checked bags in Economy (up to 70 lb) per Premier tier.
PREMIER_FREE_BAGS = {'Member': 0, 'Premier Silver': 1, 'Premier Gold': 2,
                     'Premier Platinum': 3, 'Premier 1K®': 3}
PREMIER_BOARDING = {'Member': 'Group 4', 'Premier Silver': 'Group 2',
                    'Premier Gold': 'Group 1', 'Premier Platinum': 'Group 1',
                    'Premier 1K®': 'Pre-board'}
PREMIER_BENEFITS = {
    'Member': ['Earn 5 award miles per $1 of fare', 'Book award travel',
               'Free standard seat selection'],
    'Premier Silver': ['Earn 7 miles per $1', 'Priority check-in and boarding (Group 2)',
                       'Complimentary Economy Plus at check-in',
                       '1 free checked bag in Economy (70 lb)'],
    'Premier Gold': ['Earn 8 miles per $1', 'Star Alliance™ Gold status',
                     'Economy Plus at booking', '2 free checked bags (70 lb each)'],
    'Premier Platinum': ['Earn 9 miles per $1', 'PlusPoints upgrades',
                         'Complimentary Premium cabin upgrade space',
                         '3 free checked bags (70 lb each)'],
    'Premier 1K®': ['Earn 11 miles per $1', 'Pre-board boarding group',
                    'More PlusPoints', '3 free checked bags (70 lb each)'],
}

STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
              'or', 'is', 'it', 'by', 'with', 'my', 'can', 'i', 'you', 'we',
              'do', 'does', 'how', 'what', 'are', 'be', 'united'}


# ------------------------------------------------------------------ models --

class Airport(db.Model):
    __tablename__ = 'airports'
    code = db.Column(db.String(3), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(40), default='')
    country = db.Column(db.String(60), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    is_hub = db.Column(db.Boolean, default=False)
    region = db.Column(db.String(30), nullable=False, default='Domestic')
    image = db.Column(db.String(160), default='')
    guide = db.Column(db.Text, default='')

    @property
    def display_name(self):
        return f'{self.city}, {self.code}'

    def distance_to(self, other):
        """Great-circle distance in km between two airports."""
        lat1, lon1, lat2, lon2 = map(math.radians,
                                     (self.latitude, self.longitude,
                                      other.latitude, other.longitude))
        a = (math.sin((lat2 - lat1) / 2) ** 2
             + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
        return 6371 * 2 * math.asin(math.sqrt(a))


class Flight(db.Model):
    """A frozen real flight (number, route, times, aircraft) from the
    upstream flight-status snapshot; the search engine serves its times for
    every date in the booking window."""
    __tablename__ = 'flights'
    id = db.Column(db.Integer, primary_key=True)
    flight_number = db.Column(db.String(8), nullable=False, index=True)
    origin_code = db.Column(db.String(3), db.ForeignKey('airports.code'),
                            nullable=False)
    dest_code = db.Column(db.String(3), db.ForeignKey('airports.code'),
                          nullable=False)
    departure = db.Column(db.String(5), nullable=False)     # HH:MM local
    arrival = db.Column(db.String(5), nullable=False)       # HH:MM local
    duration_minutes = db.Column(db.Integer, nullable=False)
    aircraft_key = db.Column(db.String(20), db.ForeignKey('aircraft.key'),
                             nullable=False)
    stops = db.Column(db.Integer, nullable=False, default=0)
    status_note = db.Column(db.String(60), default='')     # ops status label
    gate = db.Column(db.String(6), default='')
    terminal = db.Column(db.String(4), default='')

    origin = db.relationship('Airport', foreign_keys=[origin_code])
    dest = db.relationship('Airport', foreign_keys=[dest_code])
    aircraft = db.relationship('Aircraft')

    @property
    def duration_label(self):
        return f'{self.duration_minutes // 60}h {self.duration_minutes % 60:02d}m'

    def operates_on(self, day: date) -> bool:
        return self.horizon_start <= day <= self.horizon_end

    # Horizon columns default-populated at seed time.
    horizon_start = db.Column(db.Date, default=date(2026, 9, 28))
    horizon_end = db.Column(db.Date, default=date(2027, 8, 24))

    def fare_for(self, cabin: str) -> 'Fare':
        return Fare.query.filter_by(flight_id=self.id, cabin=cabin).first()

    def fares(self):
        return {f.cabin: f for f in Fare.query.filter_by(flight_id=self.id)}

    def occupied_seats(self, day: date):
        digest = hashlib.md5(f'{self.flight_number}|{day.isoformat()}|occ'
                             .encode()).hexdigest()
        rng = random.Random(int(digest[:12], 16))
        aircraft = self.aircraft
        seats = []
        # Occupancy is drawn inside the United Economy band only
        # (exit_rows = first/last economy row): the premium and Economy Plus
        # cabins of this frozen snapshot are unassigned, so a traveler can
        # always confirm the premium-cabin seat of a booked trip.
        count = rng.randint(18, int(aircraft.seat_rows * 1.6))
        for _ in range(count):
            row = rng.randint(aircraft.exit_rows[0], aircraft.exit_rows[1])
            letter = rng.choice(aircraft.seat_letters)
            seats.append(f'{row}{letter}')
        return set(seats)


class Fare(db.Model):
    __tablename__ = 'fares'
    id = db.Column(db.Integer, primary_key=True)
    flight_id = db.Column(db.Integer, db.ForeignKey('flights.id'), nullable=False)
    cabin = db.Column(db.String(4), nullable=False)        # BE/ECO/EPU/PP/BUS
    amount = db.Column(db.Float, nullable=False)           # USD per person
    miles = db.Column(db.Integer, nullable=False, default=0)  # award price
    seats_left = db.Column(db.Integer, default=9)

    flight = db.relationship('Flight', backref='fare_rows')


class Aircraft(db.Model):
    """Real United equipment from the fleet pages (SDL captures) plus the
    live amenities payload of captured flights."""
    __tablename__ = 'aircraft'
    key = db.Column(db.String(20), primary_key=True)       # e.g. 78P, 37K
    name = db.Column(db.String(60), nullable=False)       # Boeing 787-9
    description = db.Column(db.Text, default='')
    seat_rows = db.Column(db.Integer, nullable=False)
    exit_rows = db.Column(db.JSON, nullable=False)         # first/last economy row
    seat_letters = db.Column(db.JSON, nullable=False)
    first_rows = db.Column(db.Integer, default=0)
    economy_plus_rows = db.Column(db.Integer, default=0)
    premium_rows = db.Column(db.Integer, default=0)
    wifi = db.Column(db.String(40), default='')
    power = db.Column(db.String(10), default='yes')
    seat_map_config = db.Column(db.String(30), default='')
    image = db.Column(db.String(160), default='')
    seat_map_image = db.Column(db.String(160), default='')
    cabin_specs = db.Column(db.JSON, default=list)
    specs = db.Column(db.JSON, default=dict)

    def seatmap_cabins(self):
        """Ordered cabin bands for the seat map page."""
        bands = []
        letters = self.seat_letters
        if self.first_rows:
            bands.append({'name': 'United First®' if self.key.startswith(('73', '37', '19'))
                          else 'United Polaris® business class',
                          'rows': self.first_rows, 'price': 0})
        if self.premium_rows:
            bands.append({'name': 'United Premium Plus®',
                          'rows': self.premium_rows, 'price': 0})
        bands.append({'name': 'Economy Plus®', 'rows': self.economy_plus_rows,
                      'price': 'eplus'})
        start = self.first_rows + self.premium_rows + self.economy_plus_rows + 1
        bands.append({'name': 'United Economy®',
                      'rows': max(self.seat_rows - start + 1, 3), 'price': 0})
        return bands


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False, default='')
    last_name = db.Column(db.String(80), nullable=False, default='')
    mp_number = db.Column(db.String(12), unique=True)      # MileagePlus number
    award_miles = db.Column(db.Integer, default=0)
    pqf = db.Column(db.Integer, default=0)
    pqp = db.Column(db.Integer, default=0)
    tier = db.Column(db.String(20), default='Member')
    plus_points = db.Column(db.Integer, default=0)
    phone = db.Column(db.String(30), default='')
    country = db.Column(db.String(60), default='United States')
    created_at = db.Column(db.DateTime, default=MIRROR_DATE)

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def next_tier_progress(self):
        idx = PREMIER_TIERS.index(self.tier) if self.tier in PREMIER_TIERS else 0
        nxt = PREMIER_TIERS[idx + 1] if idx + 1 < len(PREMIER_TIERS) else None
        if not nxt:
            return None
        need_pqf, need_pqp = PREMIER_QUALIFICATION[nxt]
        return {'tier': nxt, 'need_pqf': need_pqf, 'need_pqp': need_pqp,
                'have_pqf': self.pqf, 'have_pqp': self.pqp}


class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=MIRROR_DATE)
    description = db.Column(db.String(160), nullable=False)
    channel = db.Column(db.String(60), default='United')
    miles = db.Column(db.Integer, default=0)
    pqp = db.Column(db.Integer, default=0)

    user = db.relationship('User', backref='activities')


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    confirmation = db.Column(db.String(6), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    contact_email = db.Column(db.String(120), nullable=False)
    contact_phone = db.Column(db.String(30), default='')
    cabin = db.Column(db.String(4), nullable=False, default='ECO')
    adults = db.Column(db.Integer, nullable=False, default=1)
    children = db.Column(db.Integer, nullable=False, default=0)
    award_booking = db.Column(db.Boolean, default=False)
    miles_redeemed = db.Column(db.Integer, default=0)
    card_last4 = db.Column(db.String(4), default='')
    card_type = db.Column(db.String(20), default='')
    total = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='confirmed')  # confirmed/canceled
    canceled_at = db.Column(db.DateTime, nullable=True)
    refund_amount = db.Column(db.Float, default=0.0)
    refund_to = db.Column(db.String(40), default='')        # card / travel credit
    created_at = db.Column(db.DateTime, default=MIRROR_DATE)

    user = db.relationship('User', backref='bookings')
    passengers = db.relationship('Passenger', backref='booking',
                                 order_by='Passenger.id')
    legs = db.relationship('BookingLeg', backref='booking',
                           order_by='BookingLeg.id')

    @property
    def route_label(self):
        if not self.legs:
            return ''
        first, last = self.legs[0], self.legs[-1]
        return f'{first.flight.origin_code}–{last.flight.dest_code}'

    @property
    def contact_name(self):
        return self.passengers[0].last_name if self.passengers else ''

    def total_bag_fees(self):
        return sum(b.fee for b in BaggageItem.query.filter_by(booking_id=self.id))


class BookingLeg(db.Model):
    __tablename__ = 'booking_legs'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    flight_id = db.Column(db.Integer, db.ForeignKey('flights.id'), nullable=False)
    travel_date = db.Column(db.Date, nullable=False)
    cabin = db.Column(db.String(4), nullable=False)
    amount = db.Column(db.Float, nullable=False)

    flight = db.relationship('Flight')


class Passenger(db.Model):
    __tablename__ = 'passengers'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(4), default='Mr')
    date_of_birth = db.Column(db.String(10), default='')
    gender = db.Column(db.String(1), default='')
    mp_number = db.Column(db.String(12), default='')
    seat = db.Column(db.String(5), default='')              # assigned at check-in
    checked_in = db.Column(db.Boolean, default=False)
    boarding_group = db.Column(db.String(3), default='')


class BaggageItem(db.Model):
    __tablename__ = 'baggage_items'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    passenger_id = db.Column(db.Integer, db.ForeignKey('passengers.id'), nullable=False)
    description = db.Column(db.String(60), default='Checked bag')  # 1st/2nd/extra
    weight_lb = db.Column(db.Integer, default=0)
    fee = db.Column(db.Float, default=0.0)

    passenger = db.relationship('Passenger', backref='bags')


class HelpArticle(db.Model):
    __tablename__ = 'help_articles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    category = db.Column(db.String(60), nullable=False)
    question = db.Column(db.String(200), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    related = db.Column(db.JSON, default=list)


class Deal(db.Model):
    __tablename__ = 'deals'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    origin_code = db.Column(db.String(3), db.ForeignKey('airports.code'))
    dest_code = db.Column(db.String(3), db.ForeignKey('airports.code'))
    summary = db.Column(db.Text, default='')
    fare_from = db.Column(db.Float, default=0.0)
    image = db.Column(db.String(160), default='')

    origin = db.relationship('Airport', foreign_keys=[origin_code])
    dest = db.relationship('Airport', foreign_keys=[dest_code])


class CabinInfo(db.Model):
    """Cabin experience pages from the upstream travel-info content."""
    __tablename__ = 'cabin_info'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    tagline = db.Column(db.String(200), default='')
    body = db.Column(db.Text, default='')
    highlights = db.Column(db.JSON, default=list)
    image = db.Column(db.String(160), default='')


class PolicyArticle(db.Model):
    """Change / cancellation / refund policy copy."""
    __tablename__ = 'policy_articles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, default='')
    facts = db.Column(db.JSON, default=list)               # table rows


# --------------------------------------------------------------- fare rules --

# Checked-bag fees (USD) frozen from the upstream checked-bags page: first
# bag $35 online / $40 at the airport, second $45 online / $50 at airport
# (post-Feb-2024 levels), extra bags $150 each, overweight/oversized $100.
BAG_FEE_TABLE = {
    'first_online': 35.0, 'first_airport': 40.0,
    'second_online': 45.0, 'second_airport': 50.0,
    'extra': 150.0,
    'overweight_51_70': 100.0, 'overweight_71_100': 200.0,
    'oversized_63_115': 200.0, 'oversized_115': 650.0,
}
BAG_WEIGHT_LIMIT = 50          # lb for Economy / Premium Plus
BAG_WEIGHT_LIMIT_PREMIER = 70 # lb for Premier members / Business / First
BAG_SIZE_LIMIT_LINEAR_IN = 62  # max 62 linear inches
BAG_MAX_WEIGHT = 100           # lb — nothing over 100 lb is accepted

# Carry-on: one personal item 9x10x17 in free; carry-on 9x14x22 in free on
# every fare (including Basic Economy since 2020 — but gate-check risk on
# full flights applies to Basic Economy groups).
CARRY_ON_MAX_IN = (9, 14, 22)
PERSONAL_ITEM_MAX_IN = (9, 10, 17)

# Change/cancel rules frozen from the upstream flight-change pages.
CHANGE_FEE_STANDARD = 0.0        # no change fee for standard economy and above
CHANGE_FEE_BASIC_ECONOMY = None  # Basic Economy: no changes permitted
SAME_DAY_CHANGE_FEE = 75.0       # same-day change fee (up to $75 by status)
SAME_DAY_STANDBY_MEMBER = 0.0    # free same-day standby for Premier members
CABIN_UPGRADE_PER_ROW_EPLUS = 29.0   # Economy Plus seat purchase floor ($29-$299)


def fare_difference(old_amount: float, new_amount: float) -> float:
    return round(max(new_amount - old_amount, 0.0), 2)


def miles_for_amount(amount: float) -> int:
    """Award miles needed to cover a fare: 100 miles per $1 of value."""
    return int(math.ceil(amount * AWARD_MILES_PER_USD / 100.0) * 100)


def base_fare_for(distance_km: int, cabin: str, seed_key: str) -> float:
    """Deterministic per-flight fare ladder anchored on real United price
    levels (short domestic hops ~$79+ Basic Economy, transcons ~$179+,
    premium cabins multiples of economy)."""
    rng = random.Random(seed_key)
    if distance_km <= 800:
        eco = 89 + (distance_km / 800) * 70          # $89–$159
    elif distance_km <= 2500:
        eco = 129 + (distance_km / 2500) * 150       # $129–$279
    elif distance_km <= 6000:
        eco = 279 + (distance_km / 6000) * 320      # $279–$599
    else:
        eco = 499 + min(distance_km / 15000, 1.0) * 300
    eco = round(eco + rng.randint(-12, 18), 0) - 0.05
    eco = max(eco, 39.05)
    multipliers = {'BE': 0.78, 'ECO': 1.0, 'EPU': 1.24,
                   'PP': 2.35, 'BUS': 4.10}
    return round(eco * multipliers[cabin], 2)


def premier_multiplier(tier: str) -> float:
    """Deterministic same-day fare adjustment per Premier tier (mirrors the
    upstream 'member-only fares' 2%-ish discounts)."""
    return {'Member': 1.0, 'Premier Silver': 0.99, 'Premier Gold': 0.98,
            'Premier Platinum': 0.97, 'Premier 1K®': 0.96}.get(tier, 1.0)


def generate_confirmation(seed: str) -> str:
    """United-style 6-character confirmation number (no 0/O/1/I)."""
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    digest = hashlib.sha256(seed.encode()).hexdigest()
    rng = random.Random(int(digest[:12], 16))
    return ''.join(rng.choice(alphabet) for _ in range(6))


def boarding_group(cabin: str, tier: str) -> str:
    """United boarding groups (real order): Pre-board (1K), Group 1
    (Premier Gold/Platinum, Polaris/First), Group 2 (Premier Silver,
    Premium Plus, Economy Plus), Groups 3-5 Economy, Basic Economy in
    Group 6 per the upstream Basic Economy page."""
    if tier in PREMIER_BOARDING:
        group = PREMIER_BOARDING[tier]
        if group == 'Pre-board' and cabin != 'BUS':
            return group
    if cabin == 'BUS':
        return 'Group 1'
    if tier == 'Premier Gold' or tier == 'Premier Platinum' or tier == 'Premier 1K®':
        return 'Group 1'
    if cabin == 'PP' or tier == 'Premier Silver':
        return 'Group 2'
    if cabin == 'EPU':
        return 'Group 2'
    return 'Group 4' if cabin == 'ECO' else 'Group 6'


# ------------------------------------------------------------ search helpers --

def scored_search(query: str, rows, fields):
    """Token-overlap ranked search used across help / deals / airports."""
    tokens = {t for t in re.split(r'[^a-z0-9]+', (query or '').lower())
              if t and t not in STOP_WORDS}
    scored = []
    for row in rows:
        text = ' '.join(getattr(row, f, '') or '' for f in fields).lower()
        overlap = sum(1 for t in tokens if t in text)
        if overlap:
            scored.append((overlap, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1].id if hasattr(pair[1], 'id') else 0))
    return [row for _, row in scored]


# ------------------------------------------------------------------- routes --

@app.route('/robots.txt')
def robots():
    return 'User-agent: *\nAllow: /\n', 200, {'Content-Type': 'text/plain'}


# --------------------------------------------------------------------- home --

@app.route('/')
def home():
    deals = Deal.query.order_by(Deal.fare_from).limit(6).all()
    hubs = Airport.query.filter_by(is_hub=True).order_by(Airport.code).all()
    return render_template('index.html', deals=deals, hubs=hubs,
                           airports=_airports_for_picker(),
                           params={'origin': '', 'destination': ''},
                           fare_cabins=FARE_FAMILIES,
                           today=MIRROR_TODAY.isoformat())


def _airports_for_picker():
    return (Airport.query.order_by(Airport.city, Airport.code).all())


@app.route('/flights/airports.json')
def airports_json():
    rows = Airport.query.order_by(Airport.city, Airport.code).all()
    return jsonify([{
        'code': a.code, 'name': a.name, 'city': a.city,
        'state': a.state, 'country': a.country,
        'display': f'{a.city} ({a.code})',
        'hub': a.is_hub,
    } for a in rows])


# ----------------------------------------------------------- flight search --

def _parse_date(value: str):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _search_flights(origin: str, dest: str, day: date):
    if not origin or not dest or origin == dest:
        return []
    rows = (Flight.query
            .filter(Flight.origin_code == origin.upper(),
                    Flight.dest_code == dest.upper())
            .order_by(Flight.departure).all())
    return [f for f in rows if f.operates_on(day)]


@app.route('/flights/search', methods=['GET', 'POST'])
def flight_search():
    airports = _airports_for_picker()
    params = {
        'origin': request.values.get('origin', '').upper(),
        'destination': request.values.get('destination', '').upper(),
        'depart': request.values.get('depart', ''),
        'return': request.values.get('return', ''),
        'adults': request.values.get('adults', '1'),
        'children': request.values.get('children', '0'),
        'cabin': request.values.get('cabin', 'ECO'),
        'trip': 'roundtrip' if request.values.get('return') else 'oneway',
        'sort': request.values.get('sort', 'departure'),
        'filter': request.values.get('filter', ''),
    }
    results = []
    day = _parse_date(params['depart'])
    error = ''
    if request.method == 'POST' or params['origin']:
        if not day:
            error = 'Please choose a valid departure date.'
        elif day < MIRROR_TODAY:
            error = 'Departure date is in the past.'
        elif day > MIRROR_TODAY + timedelta(days=BOOKING_HORIZON_DAYS):
            error = ('Flights are only bookable up to '
                     f'{MIRROR_TODAY + timedelta(days=BOOKING_HORIZON_DAYS).isoformat()}.')
        elif not db.session.get(Airport, params['origin']):
            error = f'Unknown origin airport: {params["origin"]}'
        elif not db.session.get(Airport, params['destination']):
            error = f'Unknown destination airport: {params["destination"]}'
        else:
            results = _search_flights(params['origin'], params['destination'], day)
            if params['filter'] == 'nonstop':
                results = [f for f in results if f.stops == 0]
            if params['filter'] == 'morning':
                results = [f for f in results if f.departure < '12:00']
            if params['filter'] == 'afternoon':
                results = [f for f in results if '12:00' <= f.departure < '18:00']
            if params['filter'] == 'evening':
                results = [f for f in results if f.departure >= '18:00']
            sort = params['sort']
            if sort == 'price':
                results.sort(key=lambda f: f.fares().get(params['cabin']).amount
                             if f.fares().get(params['cabin']) else 1e9)
            elif sort == 'arrival':
                results.sort(key=lambda f: f.arrival)
            elif sort == 'duration':
                results.sort(key=lambda f: f.duration_minutes)
            else:
                results.sort(key=lambda f: f.departure)
    tier = current_user.tier if current_user.is_authenticated else 'Member'
    mult = premier_multiplier(tier)
    return render_template('search_results.html', params=params,
                           airports=airports, results=results, error=error,
                           day=day, fare_cabins=FARE_FAMILIES,
                           mult=mult, today=MIRROR_TODAY.isoformat())


@app.route('/flights/select/<int:flight_id>', methods=['POST'])
def select_flight(flight_id):
    flight = db.session.get(Flight, flight_id) or abort(404)
    cabin = request.form.get('cabin', 'ECO')
    if cabin not in dict(FARE_FAMILIES):
        abort(400)
    trip = {
        'outbound_flight_id': flight_id,
        'outbound_date': request.form.get('date', ''),
        'outbound_cabin': cabin,
        'adults': int(request.form.get('adults', '1')),
        'children': int(request.form.get('children', '0')),
        'return_flight_id': None,
        'return_date': request.form.get('return', ''),
        'return_cabin': cabin,
    }
    session['cart'] = trip
    want_return = bool(request.form.get('return'))
    if want_return:
        return redirect(url_for('select_return',
                                origin=flight.dest_code,
                                destination=flight.origin_code))
    return redirect(url_for('booking_passengers'))


@app.route('/flights/select-return')
def select_return():
    trip = session.get('cart')
    if not trip:
        return redirect(url_for('home'))
    origin = request.args.get('origin', '').upper()
    destination = request.args.get('destination', '').upper()
    day = _parse_date(request.args.get('depart', trip.get('return_date')))
    results = _search_flights(origin, destination, day) if day else []
    tier = current_user.tier if current_user.is_authenticated else 'Member'
    return render_template('select_return.html', results=results,
                           origin=origin, destination=destination,
                           day=day, trip=trip,
                           fare_cabins=FARE_FAMILIES,
                           mult=premier_multiplier(tier))


@app.route('/flights/confirm-return/<int:flight_id>', methods=['POST'])
def confirm_return(flight_id):
    trip = session.get('cart')
    if not trip:
        return redirect(url_for('home'))
    trip['return_flight_id'] = flight_id
    trip['return_cabin'] = request.form.get('cabin', trip['outbound_cabin'])
    session['cart'] = trip
    return redirect(url_for('booking_passengers'))


# --------------------------------------------------------------- booking ----

def _cart_price(cart) -> float:
    total = 0.0
    count = cart['adults'] + cart['children']
    tier = current_user.tier if current_user.is_authenticated else 'Member'
    mult = premier_multiplier(tier)
    for key in ('outbound', 'return'):
        fid = cart.get(f'{key}_flight_id')
        if not fid:
            continue
        flight = db.session.get(Flight, fid)
        fare = flight.fare_for(cart[f'{key}_cabin'])
        total += round(fare.amount * mult, 2) * count
    return round(total, 2)


def _cart_miles(cart) -> int:
    total = 0
    for key in ('outbound', 'return'):
        fid = cart.get(f'{key}_flight_id')
        if not fid:
            continue
        flight = db.session.get(Flight, fid)
        fare = flight.fare_for(cart[f'{key}_cabin'])
        total += fare.miles
    count = cart['adults'] + cart['children']
    return total * count


@app.route('/booking/passengers', methods=['GET', 'POST'])
def booking_passengers():
    cart = session.get('cart')
    if not cart:
        return redirect(url_for('home'))
    flights = []
    for key in ('outbound', 'return'):
        fid = cart.get(f'{key}_flight_id')
        if fid:
            flights.append((key, db.session.get(Flight, fid),
                            cart[f'{key}_cabin'], cart[f'{key}_date']))
    pax_count = cart['adults'] + cart['children']
    price = _cart_price(cart)
    if request.method == 'POST':
        contact_email = request.form.get('contact_email', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$', contact_email):
            flash('Enter a valid contact email address.')
        else:
            travelers = []
            ok = True
            for i in range(pax_count):
                first = request.form.get(f'first_{i}', '').strip()
                last = request.form.get(f'last_{i}', '').strip()
                dob = request.form.get(f'dob_{i}', '').strip()
                gender = request.form.get(f'gender_{i}', '').strip()
                mp = request.form.get(f'mp_{i}', '').strip()
                title = request.form.get(f'title_{i}', 'Mr')
                if not re.match(r'^[A-Za-z][A-Za-z .\'-]{0,39}$', first):
                    flash(f'Enter a valid first name for traveler {i + 1}.')
                    ok = False
                    break
                if not re.match(r'^[A-Za-z][A-Za-z .\'-]{0,39}$', last):
                    flash(f'Enter a valid last name for traveler {i + 1}.')
                    ok = False
                    break
                dob_date = _parse_date(dob) if dob else None
                if dob and (not dob_date or dob_date > MIRROR_TODAY):
                    flash(f'Enter a valid date of birth for traveler {i + 1}.')
                    ok = False
                    break
                if mp and not re.match(r'^\d{6,12}$', mp):
                    flash(f'MileagePlus number must be 6-12 digits.')
                    ok = False
                    break
                travelers.append({'title': title, 'first': first, 'last': last,
                                   'dob': dob, 'gender': gender, 'mp': mp})
            if ok:
                session['travelers'] = travelers
                session['contact'] = {'email': contact_email,
                                      'phone': contact_phone}
                return redirect(url_for('booking_payment'))
    return render_template('passenger_details.html', cart=cart,
                           flights=flights, pax_count=pax_count,
                           price=price, fare_cabins=FARE_FAMILIES)


def _card_type(number: str) -> str:
    if re.match(r'^4\d{15}$', number):
        return 'Visa'
    if re.match(r'^5[1-5]\d{14}$|^2[2-7]\d{14}$', number):
        return 'Mastercard'
    if re.match(r'^3[47]\d{13}$', number):
        return 'American Express'
    if re.match(r'^6(?:011|5\d{2})\d{12}$', number):
        return 'Discover'
    return ''


@app.route('/booking/payment', methods=['GET', 'POST'])
def booking_payment():
    cart = session.get('cart')
    travelers = session.get('travelers')
    contact = session.get('contact')
    if not (cart and travelers and contact):
        return redirect(url_for('home'))
    price = _cart_price(cart)
    miles_needed = _cart_miles(cart)
    flights = []
    for key in ('outbound', 'return'):
        fid = cart.get(f'{key}_flight_id')
        if fid:
            flights.append((key, db.session.get(Flight, fid),
                            cart[f'{key}_cabin'], cart[f'{key}_date']))
    taxes = round(price * 0.075, 2)
    user = current_user if current_user.is_authenticated else None
    can_miles = bool(user and user.award_miles >= miles_needed)
    if request.method == 'POST':
        method = request.form.get('method', 'card')
        if method == 'miles':
            if not can_miles:
                flash('Not enough award miles for this trip.')
            else:
                seed = json.dumps([cart, travelers, contact],
                                  sort_keys=True, default=str)
                confirmation = generate_confirmation('ua|' + seed)
                booking = _materialize_booking(cart, travelers, contact,
                                                confirmation, award=True)
                user.award_miles -= miles_needed
                act = Activity(user_id=user.id, date=MIRROR_TODAY,
                               description=f'Award travel — {booking.route_label}',
                               channel='MileagePlus', miles=-miles_needed)
                db.session.add(act)
                db.session.commit()
                session['mytrips_auth'] = booking.confirmation
                session.pop('cart', None)
                session.pop('travelers', None)
                session.pop('contact', None)
                return redirect(url_for('confirmation', conf=confirmation))
        else:
            number = re.sub(r'[\s-]', '', request.form.get('card_number', ''))
            name = request.form.get('card_name', '').strip()
            expiry = request.form.get('card_expiry', '').strip()
            cvv = request.form.get('card_cvv', '').strip()
            ctype = _card_type(number)
            if not ctype:
                flash('Enter a valid Visa, Mastercard, Amex or Discover card number.')
            elif not re.match(r'^[A-Za-z][A-Za-z .\'-]{2,60}$', name):
                flash('Enter the name as it appears on the card.')
            elif not re.match(r'^(0[1-9]|1[0-2])\/\d{2}$', expiry):
                flash('Enter the expiration date as MM/YY.')
            else:
                month = int(expiry[:2])
                year = 2000 + int(expiry[3:])
                exp_date = date(year, month, 1)
                if exp_date <= MIRROR_TODAY:
                    flash('This card is expired.')
                elif not re.match(r'^\d{3,4}$', cvv):
                    flash('Enter the 3- or 4-digit security code.')
                else:
                    seed = json.dumps([cart, travelers, contact, number, name],
                                      sort_keys=True, default=str)
                    confirmation = generate_confirmation('ua|' + seed)
                    booking = _materialize_booking(
                        cart, travelers, contact, confirmation, award=False,
                        card_last4=number[-4:], card_type=ctype)
                    db.session.commit()
                    session['mytrips_auth'] = booking.confirmation
                    session.pop('cart', None)
                    session.pop('travelers', None)
                    session.pop('contact', None)
                    return redirect(url_for('confirmation', conf=confirmation))
    return render_template('payment.html', cart=cart, flights=flights,
                           price=price, taxes=taxes, travelers=travelers,
                           contact=contact, miles_needed=miles_needed,
                           can_miles=can_miles, user=user,
                           fare_cabins=FARE_FAMILIES)


def _materialize_booking(cart, travelers, contact, confirmation, award,
                          card_last4='', card_type=''):
    count = cart['adults'] + cart['children']
    tier = current_user.tier if current_user.is_authenticated else 'Member'
    mult = premier_multiplier(tier)
    booking = Booking(confirmation=confirmation,
                      user_id=current_user.id if current_user.is_authenticated else None,
                      contact_email=contact['email'],
                      contact_phone=contact.get('phone', ''),
                      cabin=cart['outbound_cabin'],
                      adults=cart['adults'], children=cart['children'],
                      award_booking=award,
                      miles_redeemed=_cart_miles(cart) if award else 0,
                      card_last4=card_last4, card_type=card_type,
                      total=_cart_price(cart) if not award else 0.0)
    db.session.add(booking)
    db.session.flush()
    total = 0.0
    for key in ('outbound', 'return'):
        fid = cart.get(f'{key}_flight_id')
        if not fid:
            continue
        flight = db.session.get(Flight, fid)
        fare = flight.fare_for(cart[f'{key}_cabin'])
        amount = round(fare.amount * mult, 2)
        leg = BookingLeg(booking_id=booking.id, flight_id=fid,
                          travel_date=_parse_date(cart[f'{key}_date']),
                          cabin=cart[f'{key}_cabin'], amount=amount)
        db.session.add(leg)
        total += amount * count
    booking.total = round(total, 2) if not award else 0.0
    for t in travelers:
        pax = Passenger(booking_id=booking.id, first_name=t['first'],
                        last_name=t['last'], title=t['title'],
                        date_of_birth=t['dob'], gender=t['gender'],
                        mp_number=t['mp'])
        db.session.add(pax)
    db.session.flush()
    # Award tickets earn no award miles/PQP: the fare was paid with miles
    # (base fare $0 -> 0 PQP, 0 PQF per the program page), so travelers on
    # an award booking get no flight credit. Keeps the frozen T2 end state
    # (68,450 - 42,595 = 25,855) even when the MP number is on the traveler.
    if not award:
        # Award miles + PQP credit for travelers who used their MileagePlus number.
        for t in travelers:
            if t['mp']:
                member = User.query.filter_by(mp_number=t['mp']).first()
                if member:
                    miles = int(round(total * MILES_EARN_RATE[member.tier]))
                    pqp = int(round(total))     # 1 PQP per $1 of base fare
                    member.award_miles += miles
                    member.pqp += pqp
                    member.pqf += 1
                    act = Activity(user_id=member.id, date=MIRROR_TODAY,
                                   description=(f'Flight credit — '
                                                f'{booking.route_label}'),
                                   channel='United', miles=miles, pqp=pqp)
                    db.session.add(act)
    return booking


@app.route('/booking/confirmation/<conf>')
def confirmation(conf):
    booking = Booking.query.filter_by(confirmation=conf.upper()).first()
    if not booking:
        abort(404)
    credited = None
    for pax in booking.passengers:
        if pax.mp_number:
            member = User.query.filter_by(mp_number=pax.mp_number).first()
            if member:
                credited = (int(round(booking.total
                                      * MILES_EARN_RATE[member.tier])),
                            member.tier)
                break
    return render_template('confirmation.html', booking=booking,
                           fare_cabins=FARE_FAMILIES, credited=credited)


# --------------------------------------------------------------- my trips ---

@app.route('/mytrips', methods=['GET', 'POST'])
def mytrips():
    booking = None
    not_found = False
    conf = request.values.get('confirmation', '').strip().upper()
    last = request.values.get('lastname', '').strip()
    if conf or last:
        booking = Booking.query.filter_by(confirmation=conf).first()
        if not booking:
            not_found = True
        elif booking.contact_name.lower() != last.lower():
            booking = None
            not_found = True
    if booking:
        session['mytrips_auth'] = booking.confirmation
        return redirect(url_for('trip_detail', conf=booking.confirmation))
    my_bookings = []
    if current_user.is_authenticated:
        my_bookings = (Booking.query.filter_by(user_id=current_user.id)
                       .order_by(Booking.created_at.desc()).all())
    return render_template('mytrips.html', not_found=not_found,
                           bookings=my_bookings)


def _seat_bands(aircraft):
    """Ordered cabin bands with concrete row ranges for the seat map."""
    bands = []
    start = 1
    for band in aircraft.seatmap_cabins():
        rows = max(band['rows'], 1)
        bands.append({'name': band['name'], 'start': start,
                      'end': start + rows - 1,
                      'eplus': band['price'] == 'eplus'})
        start += rows
    # stretch the last band to the aircraft's full row count
    if bands and aircraft.seat_rows > bands[-1]['end']:
        bands[-1]['end'] = aircraft.seat_rows
    return bands


def _authorized_trip(conf):
    booking = Booking.query.filter_by(confirmation=conf.upper()).first()
    if not booking:
        abort(404)
    if session.get('mytrips_auth') == booking.confirmation:
        return booking
    if current_user.is_authenticated and booking.user_id == current_user.id:
        return booking
    abort(403)


@app.route('/mytrips/<conf>', methods=['GET', 'POST'])
def trip_detail(conf):
    booking = _authorized_trip(conf)
    action = request.form.get('action', '') if request.method == 'POST' else ''
    if action == 'add_bag':
        pax = db.session.get(Passenger, int(request.form.get('passenger_id', 0)))
        which = request.form.get('which', 'first')
        if pax and pax.booking_id == booking.id:
            existing = BaggageItem.query.filter_by(passenger_id=pax.id).count()
            free = _free_bags(booking)
            if existing < free:
                fee = 0.0
            else:
                paid_index = existing - free
                fee = (BAG_FEE_TABLE['first_online'] if paid_index == 0 else
                       BAG_FEE_TABLE['second_online'] if paid_index == 1 else
                       BAG_FEE_TABLE['extra'])
            db.session.add(BaggageItem(booking_id=booking.id,
                                       passenger_id=pax.id,
                                       description=f'Checked bag {existing + 1}',
                                       weight_lb=0, fee=fee))
            db.session.commit()
            flash((f'Checked bag {existing + 1} added — free (Premier allowance).'
                   if fee == 0 else
                   f'Checked bag {existing + 1} added — ${fee:.0f} (online price).'))
    elif action == 'change_flight':
        leg_id = int(request.form.get('leg_id', 0))
        return redirect(url_for('change_flight', conf=booking.confirmation,
                                leg_id=leg_id))
    elif action == 'cancel':
        return redirect(url_for('cancel_booking', conf=booking.confirmation))
    bag_fees = booking.total_bag_fees()
    return render_template('trip_detail.html', booking=booking,
                           bag_fees=bag_fees,
                           bag_table=BAG_FEE_TABLE,
                           free_bags=_free_bags(booking),
                           weight_limit=_bag_weight_limit(booking),
                           today=MIRROR_TODAY)


def _free_bags(booking) -> int:
    """Free checked-bag allowance for this booking's traveler tier and
    cabin, per the upstream checked-bags tables."""
    if booking.cabin in ('BUS', 'PP'):
        return 2
    tier = None
    if booking.user and booking.user.tier in PREMIER_FREE_BAGS:
        tier = booking.user.tier
    for pax in booking.passengers:
        if pax.mp_number:
            member = User.query.filter_by(mp_number=pax.mp_number).first()
            if member and member.tier in PREMIER_FREE_BAGS:
                if tier is None or (PREMIER_FREE_BAGS[member.tier]
                                    > PREMIER_FREE_BAGS.get(tier, 0)):
                    tier = member.tier
    return PREMIER_FREE_BAGS.get(tier or 'Member', 0)


def _bag_weight_limit(booking) -> int:
    if booking.cabin in ('BUS',):
        return BAG_WEIGHT_LIMIT_PREMIER
    if booking.user and booking.user.tier in ('Premier Silver', 'Premier Gold',
                                              'Premier Platinum', 'Premier 1K®'):
        return BAG_WEIGHT_LIMIT_PREMIER
    return BAG_WEIGHT_LIMIT


def _planned_seats(booking, leg, form, *, auto_assign=False):
    """Validate the entire party before mutating ORM state or assigning seats."""
    aircraft = leg.flight.aircraft
    occupied = leg.flight.occupied_seats(leg.travel_date)
    occupied.difference_update(pax.seat for pax in booking.passengers)
    planned = []
    reserved = set()
    for pax in booking.passengers:
        seat = form.get(f'seat_{pax.id}', '').strip().upper() or pax.seat
        if seat:
            if (not re.fullmatch(r'[1-9][0-9]?[A-Z]', seat)
                    or seat[-1] not in aircraft.seat_letters
                    or not 1 <= int(seat[:-1]) <= aircraft.seat_rows):
                raise ValueError('That seat does not exist on this aircraft.')
            if seat in occupied:
                raise ValueError(f'Seat {seat} is already taken on this flight.')
            if seat in reserved:
                raise ValueError(f'Seat {seat} cannot be assigned to more than one traveler.')
            reserved.add(seat)
        planned.append((pax, seat))
    if auto_assign:
        # Reserve all explicit and retained choices first, including later travelers.
        available = (f'{row}{letter}'
                     for row in range(aircraft.first_rows + aircraft.premium_rows
                                      + aircraft.economy_plus_rows + 1, aircraft.seat_rows + 1)
                     for letter in aircraft.seat_letters
                     if f'{row}{letter}' not in occupied | reserved)
        for i, (pax, seat) in enumerate(planned):
            if not seat:
                seat = next(available, None)
                if seat is None:
                    raise ValueError('No available seats remain. Please contact United for assistance.')
                reserved.add(seat)
                planned[i] = (pax, seat)
    return planned


@app.route('/mytrips/<conf>/seats/<int:leg_id>', methods=['GET', 'POST'])
def seat_selection(conf, leg_id):
    booking = _authorized_trip(conf)
    leg = db.session.get(BookingLeg, leg_id)
    if not leg or leg.booking_id != booking.id:
        abort(404)
    flight = leg.flight
    aircraft = flight.aircraft
    if request.method == 'POST':
        try:
            planned = _planned_seats(booking, leg, request.form)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for('seat_selection', conf=conf, leg_id=leg_id))
        for pax, seat in planned:
            if not seat or seat == pax.seat:
                continue
            row = int(seat[:-1])
            fee = 0.0
            premium_start = aircraft.first_rows + aircraft.premium_rows + 1
            premium_end = premium_start + aircraft.economy_plus_rows
            # Economy Plus occupies rows [premium_start, premium_end) — the
            # first standard Economy row is premium_end itself
            if premium_start <= row < premium_end and booking.cabin != 'EPU':
                fee = CABIN_UPGRADE_PER_ROW_EPLUS
            pax.seat = seat
            if fee:
                flash(f'{seat} is an Economy Plus seat — ${fee:.0f} charged.')
        db.session.commit()
        return redirect(url_for('trip_detail', conf=booking.confirmation))
    occupied = flight.occupied_seats(leg.travel_date)
    for pax in booking.passengers:
        occupied.discard(pax.seat)
    bands = _seat_bands(aircraft)
    return render_template('seat_map.html', booking=booking, leg=leg,
                           aircraft=aircraft, occupied=occupied,
                           bands=bands, flight=flight,
                           eplus_fee=CABIN_UPGRADE_PER_ROW_EPLUS)


@app.route('/mytrips/<conf>/change/<int:leg_id>', methods=['GET', 'POST'])
def change_flight(conf, leg_id):
    booking = _authorized_trip(conf)
    leg = db.session.get(BookingLeg, leg_id)
    if not leg or leg.booking_id != booking.id:
        abort(404)
    if booking.cabin == 'BE':
        flash('Basic Economy tickets cannot be changed.')
        return redirect(url_for('trip_detail', conf=booking.confirmation))
    results = _search_flights(leg.flight.origin_code, leg.flight.dest_code,
                             leg.travel_date)
    results = [f for f in results if f.id != leg.flight_id]
    if request.method == 'POST':
        new_id = int(request.form.get('flight_id', 0))
        new_flight = db.session.get(Flight, new_id)
        if not new_flight:
            abort(404)
        if booking.status != 'confirmed' or new_id not in {f.id for f in results}:
            abort(400)
        fare = new_flight.fare_for(leg.cabin)
        new_amount = round(fare.amount, 2)
        diff = fare_difference(leg.amount, new_amount)
        leg.flight_id = new_flight.id
        leg.amount = new_amount
        old_total = booking.total
        booking.total = round(old_total + diff, 2)
        db.session.commit()
        flash(f'Flight changed to UA {new_flight.flight_number}. '
              + (f'Fare difference charged: ${diff:.2f}.' if diff else
                 'No fare difference.'))
        return redirect(url_for('trip_detail', conf=booking.confirmation))
    return render_template('change_flight.html', booking=booking, leg=leg,
                           results=results, fare_cabins=FARE_FAMILIES)


@app.route('/mytrips/<conf>/cancel', methods=['GET', 'POST'])
def cancel_booking(conf):
    booking = _authorized_trip(conf)
    if request.method == 'POST':
        refundable = booking.cabin != 'BE'
        refund = booking.total + booking.total_bag_fees() if refundable else 0.0
        booking.status = 'canceled'
        booking.canceled_at = MIRROR_DATE
        booking.refund_amount = round(refund, 2)
        booking.refund_to = 'card' if refundable else 'travel credit'
        if booking.user and booking.refund_amount:
            pass
        db.session.commit()
        flash(f'Booking {booking.confirmation} canceled. '
              + (f'${refund:.2f} refunded to the original payment method.'
                 if refundable else
                 'The value was saved as a future flight credit.'))
        return redirect(url_for('mytrips'))
    return render_template('cancel.html', booking=booking)


# ------------------------------------------------------------------ checkin --

@app.route('/checkin', methods=['GET', 'POST'])
def checkin():
    booking = None
    not_found = False
    not_open = False
    conf = request.values.get('confirmation', '').strip().upper()
    last = request.values.get('lastname', '').strip()
    if conf or last:
        booking = Booking.query.filter_by(confirmation=conf).first()
        if not booking or booking.contact_name.lower() != last.lower():
            booking = None
            not_found = True
        elif booking.status != 'confirmed':
            not_found = True
        else:
            first_leg = booking.legs[0] if booking.legs else None
            if not first_leg:
                not_found = True
            else:
                dep = datetime.combine(first_leg.travel_date,
                                       datetime.strptime(first_leg.flight.departure,
                                                         '%H:%M').time())
                minutes = (dep - MIRROR_DATE).total_seconds() / 60
                if minutes > CHECKIN_OPEN_MINUTES:
                    not_open = True
                    booking = None
    eligible = []
    if current_user.is_authenticated:
        now = MIRROR_DATE
        for b in Booking.query.filter_by(user_id=current_user.id,
                                         status='confirmed'):
            if not b.legs:
                continue
            first_leg = b.legs[0]
            dep = datetime.combine(first_leg.travel_date,
                                    datetime.strptime(first_leg.flight.departure,
                                                      '%H:%M').time())
            minutes = (dep - now).total_seconds() / 60
            if CHECKIN_CLOSE_MINUTES < minutes <= CHECKIN_OPEN_MINUTES:
                eligible.append(b)
    return render_template('checkin.html', booking=booking,
                           not_found=not_found, not_open=not_open,
                           eligible=eligible,
                           checkin_minutes=CHECKIN_OPEN_MINUTES)


@app.route('/checkin/<conf>', methods=['GET', 'POST'])
def checkin_flow(conf):
    booking = _authorized_trip(conf)
    if booking.status != 'confirmed':
        abort(404)
    first_leg = booking.legs[0]
    dep = datetime.combine(first_leg.travel_date,
                           datetime.strptime(first_leg.flight.departure,
                                             '%H:%M').time())
    minutes = (dep - MIRROR_DATE).total_seconds() / 60
    if not (CHECKIN_CLOSE_MINUTES < minutes <= CHECKIN_OPEN_MINUTES):
        abort(403)
    flight = first_leg.flight
    aircraft = flight.aircraft
    occupied = flight.occupied_seats(first_leg.travel_date)
    for pax in booking.passengers:
        occupied.discard(pax.seat)
    if request.method == 'POST':
        try:
            planned = _planned_seats(booking, first_leg, request.form, auto_assign=True)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for('checkin_flow', conf=booking.confirmation))
        for pax, seat in planned:
            pax.seat = seat
            pax.checked_in = True
            pax.boarding_group = boarding_group(booking.cabin, current_user.tier
                                                 if current_user.is_authenticated
                                                 else 'Member')
        db.session.commit()
        return redirect(url_for('boarding_passes', conf=booking.confirmation))
    bands = _seat_bands(aircraft)
    return render_template('checkin_seats.html', booking=booking,
                           leg=first_leg, flight=flight, aircraft=aircraft,
                           occupied=occupied, bands=bands)


@app.route('/checkin/<conf>/boarding-pass')
def boarding_passes(conf):
    booking = _authorized_trip(conf)
    if not all(p.checked_in for p in booking.passengers):
        abort(403)
    first_leg = booking.legs[0]
    gate = first_leg.flight.gate or 'C12'
    return render_template('boarding_pass.html', booking=booking,
                           leg=first_leg, gate=gate,
                           board_time=_board_time(first_leg))


def _board_time(leg):
    dep = datetime.strptime(leg.flight.departure, '%H:%M')
    board = dep - timedelta(minutes=40)
    return board.strftime('%H:%M')


# ------------------------------------------------------------- flight status --

@app.route('/flight-status')
def flight_status():
    return render_template('flight_status.html',
                           today=MIRROR_TODAY.isoformat())


@app.route('/flight-status/results')
def flight_status_results():
    mode = request.args.get('mode', 'number')
    rows = []
    flight_day = _parse_date(request.args.get('date', '')) or MIRROR_TODAY
    origin = request.args.get('origin', '').upper()
    dest = request.args.get('destination', '').upper()
    number = re.sub(r'\D', '', request.args.get('number', ''))[:4]
    if mode == 'route' and origin and dest:
        rows = _search_flights(origin, dest, flight_day)
        header = (f'{origin} to {dest} on '
                  f'{flight_day.strftime("%B %-d, %Y")}')
    elif number:
        rows = (Flight.query
                .filter(Flight.flight_number == number)
                .order_by(Flight.origin_code).all())
        header = f'Flight UA {number} on {flight_day.strftime("%B %-d, %Y")}'
    else:
        header = ''
    return render_template('flight_status_results.html', rows=rows,
                           header=header, mode=mode, day=flight_day,
                           today=MIRROR_TODAY)


# ------------------------------------------------------------------ baggage --

@app.route('/baggage')
def baggage():
    return render_template('baggage.html')


@app.route('/baggage/checked-bags')
def baggage_checked():
    return render_template('baggage_checked.html',
                           bag_table=BAG_FEE_TABLE,
                           weight_economy=BAG_WEIGHT_LIMIT,
                           weight_premier=BAG_WEIGHT_LIMIT_PREMIER)


@app.route('/baggage/carry-on')
def baggage_carryon():
    return render_template('baggage_carryon.html',
                           carry=CARRY_ON_MAX_IN, personal=PERSONAL_ITEM_MAX_IN)


@app.route('/baggage/fee-calculator', methods=['GET', 'POST'])
def baggage_calculator():
    airports = _airports_for_picker()
    result = None
    if request.method == 'POST':
        origin = db.session.get(Airport, request.form.get('origin', '').upper())
        dest = db.session.get(Airport, request.form.get('destination', '').upper())
        cabin = request.form.get('cabin', 'ECO')
        tier = request.form.get('tier', 'Member')
        bags = request.form.get('bags', 1, type=int) or 1
        where = request.form.get('where', 'online')
        if origin and dest and bags >= 1:
            weight_limit = (BAG_WEIGHT_LIMIT_PREMIER
                            if (tier != 'Member' or cabin in ('BUS',))
                            else BAG_WEIGHT_LIMIT)
            fees = []
            free = max(2 if cabin in ('BUS', 'PP') else 0, PREMIER_FREE_BAGS.get(tier, 0))
            for i in range(1, min(bags, 4) + 1):
                paid_index = i - free
                if paid_index <= 0:
                    fee = 0.0
                elif paid_index == 1:
                    fee = (BAG_FEE_TABLE['first_online'] if where == 'online'
                           else BAG_FEE_TABLE['first_airport'])
                elif paid_index == 2:
                    fee = (BAG_FEE_TABLE['second_online'] if where == 'online'
                           else BAG_FEE_TABLE['second_airport'])
                else:
                    fee = BAG_FEE_TABLE['extra']
                fees.append(fee)
            result = {
                'origin': origin, 'dest': dest, 'cabin': cabin, 'tier': tier,
                'bags': bags, 'where': where,
                'fees': fees, 'total': round(sum(fees), 2),
                'weight_limit': weight_limit,
                'domestic': origin.country == 'United States'
                            and dest.country == 'United States',
            }
    return render_template('baggage_calculator.html', airports=airports,
                           result=result, tiers=PREMIER_TIERS,
                           fare_cabins=FARE_FAMILIES)


# --------------------------------------------------------------- MileagePlus --

@app.route('/mileageplus')
def mileageplus():
    tiers = []
    for tier in PREMIER_TIERS:
        q = PREMIER_QUALIFICATION.get(tier, (0, 0))
        tiers.append({'name': tier, 'pqf': q[0], 'pqp': q[1],
                      'pqp_only': PREMIER_PQP_ONLY.get(tier, 0),
                      'benefits': PREMIER_BENEFITS.get(tier, [])})
    return render_template('mileageplus.html', tiers=tiers,
                           earn_rates=MILES_EARN_RATE)


@app.route('/mileageplus/join', methods=['GET', 'POST'])
def mp_join():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        first = request.form.get('first_name', '').strip()
        last = request.form.get('last_name', '').strip()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$', email):
            flash('Enter a valid email address.')
        elif len(password) < 8:
            flash('Password must be at least 8 characters.')
        elif not first or not last:
            flash('Enter your first and last name.')
        elif User.query.filter_by(email=email).first():
            flash('An account with this email already exists. Sign in instead.')
        else:
            digest = hashlib.sha256(email.encode()).hexdigest()
            mp_number = str(1000000000 + int(digest[:8], 16) % 899999999)[:11]
            user = User(email=email, first_name=first, last_name=last,
                        mp_number=mp_number, award_miles=0, tier='Member')
            user.set_password(password)      # runtime bcrypt; seed stays frozen
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f'Welcome to MileagePlus — your number is {mp_number}.')
            return redirect(url_for('account'))
    return render_template('mp_join.html')


@app.route('/signin', methods=['GET', 'POST'])
def mp_signin():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.first_name}.')
            return redirect(request.args.get('next') or url_for('account'))
        flash('Email or password is incorrect.')
    return render_template('mp_signin.html')


@app.route('/signout')
def mp_signout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/account')
@login_required
def account():
    progress = current_user.next_tier_progress()
    return render_template('account.html', user=current_user,
                           progress=progress,
                           tiers=PREMIER_TIERS,
                           earn_rates=MILES_EARN_RATE)


# ---------------------------------------------------------------- travel-info --

@app.route('/travel-info/cabins')
def cabins():
    rows = CabinInfo.query.order_by(CabinInfo.id).all()
    return render_template('cabins.html', cabins=rows)


@app.route('/travel-info/cabins/<slug>')
def cabin_detail(slug):
    cabin = CabinInfo.query.filter_by(slug=slug).first_or_404()
    return render_template('cabin_detail.html', cabin=cabin)


@app.route('/travel-info/fleet')
def fleet():
    rows = Aircraft.query.order_by(Aircraft.name).all()
    return render_template('fleet.html', aircraft=rows)


@app.route('/travel-info/fleet/<key>')
def fleet_detail(key):
    aircraft = db.session.get(Aircraft, key) or abort(404)
    return render_template('fleet_detail.html', aircraft=aircraft)


@app.route('/travel-info/airports')
def airports_page():
    rows = Airport.query.order_by(Airport.is_hub.desc(), Airport.city).all()
    return render_template('airports.html', airports=rows)


@app.route('/travel-info/airports/<code>')
def airport_detail(code):
    airport = db.session.get(Airport, code.upper()) or abort(404)
    return render_template('airport_detail.html', airport=airport)


@app.route('/travel-info/policies')
def policies():
    rows = PolicyArticle.query.order_by(PolicyArticle.id).all()
    return render_template('policies.html', articles=rows)


@app.route('/travel-info/policies/<slug>')
def policy_detail(slug):
    article = PolicyArticle.query.filter_by(slug=slug).first_or_404()
    return render_template('policy_detail.html', article=article)


# ----------------------------------------------------------------------- deals --

@app.route('/deals')
def deals():
    rows = Deal.query.order_by(Deal.fare_from).all()
    region = request.args.get('region', '')
    if region:
        rows = [d for d in rows if d.category.lower() == region.lower()]
    return render_template('deals.html', deals=rows, region=region)


@app.route('/deals/<slug>')
def deal_detail(slug):
    deal = Deal.query.filter_by(slug=slug).first_or_404()
    flights = []
    if deal.origin and deal.dest:
        flights = _search_flights(deal.origin.code, deal.dest.code,
                                  MIRROR_TODAY + timedelta(days=21))
    return render_template('deal_detail.html', deal=deal, flights=flights)


# ----------------------------------------------------------------------- help --

@app.route('/help')
def help_center():
    query = request.args.get('q', '').strip()
    rows = HelpArticle.query.order_by(HelpArticle.category, HelpArticle.id).all()
    if query:
        rows = scored_search(query, rows, ['question', 'answer'])
    categories = {}
    for article in HelpArticle.query.order_by(HelpArticle.category).all():
        categories.setdefault(article.category, []).append(article)
    return render_template('help.html', articles=rows, query=query,
                           categories=categories)


@app.route('/help/<slug>')
def help_article(slug):
    article = HelpArticle.query.filter_by(slug=slug).first_or_404()
    related = [HelpArticle.query.filter_by(slug=s).first()
               for s in (article.related or [])]
    related = [r for r in related if r]
    return render_template('help_article.html', article=article,
                           related=related)


# ------------------------------------------------------------------- search ---

@app.route('/search')
def site_search():
    query = request.args.get('q', '').strip()
    help_hits = scored_search(query, HelpArticle.query.all(),
                              ['question', 'answer'])[:8]
    cabin_hits = scored_search(query, CabinInfo.query.all(),
                               ['name', 'tagline', 'body'])[:6]
    policy_hits = scored_search(query, PolicyArticle.query.all(),
                                ['title', 'body'])[:6]
    airport_hits = scored_search(query, Airport.query.all(),
                                 ['city', 'code', 'name'])[:8]
    return render_template('search.html', query=query, help_hits=help_hits,
                           cabin_hits=cabin_hits, policy_hits=policy_hits,
                           airport_hits=airport_hits)


# --------------------------------------------------------------- page errors --

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------- boot --

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 40124)), debug=False)
else:  # pragma: no cover — imported by site_runner.py
    with app.app_context():
        db.create_all()
