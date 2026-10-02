#!/usr/bin/env python3
"""UPS mirror — Flask application.

Mirrors https://www.ups.com/ (US, English): the home page with the tracking
widget and quick tools, the tracking experience (multi-number lookup, progress
milestones, activity feed, delivery change options), Create a Shipment, the
Calculate Time and Cost estimator backed by quotes captured from the live
wizard, Schedule a Pickup, the UPS Location Finder (Access Points, The UPS
Store, Customer Centers, Drop Boxes), domestic services and side-by-side
service comparison, business solutions and pickup option pages, the claims
flow (guest + signed-in) and the Help and Support Center with its support
articles.

All content rows come from the tracked source_data/ snapshots captured from
ups.com on 2026-09-28 (see provenance.json); the SQLite seed is materialized
deterministically at image build time (see .build-generated-seed).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
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
app.config["SECRET_KEY"] = os.environ.get("UPS_SECRET_KEY") or "webharbor-ups-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'UPS_DB_URI', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'ups.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your account.'
csrf = CSRFProtect(app)

# The mirror is a snapshot of the upstream site taken on 2026-09-28 (Monday).
MIRROR_DATE = date(2026, 9, 28)
MIRROR_DATE_ISO = "2026-09-28"

# bcrypt hash of 'TestPass123!' — frozen so the SQLite seed is byte-reproducible
# on every build (PYTHONHASHSEED=0 keeps the rest deterministic).
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$LV/cxTF9BjJ3r0X0yoIqne1gRSOzJYWD.44ZgGwnMcEk/Lww.M/0W')


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(80), nullable=False)
    is_business = db.Column(db.Boolean, default=False)
    account_number = db.Column(db.String(20))
    account_plan = db.Column(db.String(40))
    address_line1 = db.Column(db.String(160))
    city = db.Column(db.String(80))
    state = db.Column(db.String(20))
    zip = db.Column(db.String(12))

    shipments = db.relationship('Shipment', backref='owner', lazy=True,
                                foreign_keys='Shipment.user_id')
    pickups = db.relationship('PickupRequest', backref='user', lazy=True)
    claims = db.relationship('Claim', backref='user', lazy=True)

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class Service(db.Model):
    __tablename__ = 'services'
    code = db.Column(db.String(6), primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    bucket = db.Column(db.String(40))
    tagline = db.Column(db.String(160))
    commitment = db.Column(db.Text)
    guaranteed = db.Column(db.Boolean, default=False)
    days = db.Column(db.Integer)
    max_weight_lb = db.Column(db.Integer)
    max_length_in = db.Column(db.Integer)
    saturday_delivery = db.Column(db.Boolean, default=False)
    latest_pickup = db.Column(db.String(20))
    schedule_by = db.Column(db.String(20))
    delivered_by_default = db.Column(db.String(80))
    sort = db.Column(db.Integer)


class Shipment(db.Model):
    __tablename__ = 'shipments'
    __table_args__ = (
        db.Index('ix_shipments_tracking_number', 'tracking_number'),
    )
    id = db.Column(db.Integer, primary_key=True)
    tracking_number = db.Column(db.String(24), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    direction = db.Column(db.String(10), default='inbound')
    service_code = db.Column(db.String(6))
    shipper_name = db.Column(db.String(120))
    from_city = db.Column(db.String(60))
    from_state = db.Column(db.String(20))
    to_name = db.Column(db.String(120))
    to_city = db.Column(db.String(60))
    to_state = db.Column(db.String(20))
    to_zip = db.Column(db.String(12))
    weight_lb = db.Column(db.Float)
    packages = db.Column(db.Integer, default=1)
    signature = db.Column(db.String(40))
    scheduled_delivery = db.Column(db.String(12))
    status = db.Column(db.String(40), nullable=False)
    delivered_on = db.Column(db.String(12))
    delivered_time = db.Column(db.String(16))
    signed_by = db.Column(db.String(60))
    left_at = db.Column(db.String(60))
    hold_location_id = db.Column(db.String(20))
    hold_by = db.Column(db.String(12))
    is_international = db.Column(db.Boolean, default=False)
    declared_value = db.Column(db.Float)
    multi_package = db.Column(db.Boolean, default=False)
    exception_note = db.Column(db.Text)
    created_in_session = db.Column(db.Boolean, default=False)

    events = db.relationship('TrackingEvent', backref='shipment', lazy=True,
                              order_by='TrackingEvent.seq', cascade='all, delete-orphan')

    @property
    def service(self):
        return Service.query.filter_by(code=self.service_code).first()

    @property
    def service_name(self):
        return self.service.name if self.service else self.service_code

    @property
    def milestone(self):
        s = self.status
        if s == 'Label Created':
            return 'label'
        if s in ('Delivered',):
            return 'delivered'
        if s == 'Awaiting Customer Pickup':
            return 'ap'
        if s == 'Out for Delivery':
            return 'out'
        if s == 'Exception':
            return 'exception'
        return 'transit'


class TrackingEvent(db.Model):
    __tablename__ = 'tracking_events'
    __table_args__ = (
        db.Index('ix_tracking_events_shipment_id', 'shipment_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipments.id'), nullable=False)
    seq = db.Column(db.Integer, nullable=False)
    day = db.Column(db.String(12))
    time = db.Column(db.String(16))
    status = db.Column(db.String(60))
    location = db.Column(db.String(80))
    description = db.Column(db.Text)
    package_n = db.Column(db.Integer)


class Location(db.Model):
    __tablename__ = 'locations'
    __table_args__ = (
        db.Index('ix_locations_location_id', 'location_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120))
    addr1 = db.Column(db.String(160))
    city = db.Column(db.String(80))
    state = db.Column(db.String(10))
    zip = db.Column(db.String(12))
    phone = db.Column(db.String(30))
    lat = db.Column(db.String(20))
    lng = db.Column(db.String(20))
    type_code = db.Column(db.String(6))
    type = db.Column(db.String(40))
    latest_air_dropoff = db.Column(db.String(120))
    latest_ground_dropoff = db.Column(db.String(120))
    comments = db.Column(db.Text)
    special_instructions = db.Column(db.Text)
    featured_rank = db.Column(db.String(4))
    service_offerings = db.Column(db.Text)
    hours = db.Column(db.Text)

    @property
    def hours_rows(self):
        try:
            return json.loads(self.hours or '[]')
        except ValueError:
            return []

    @property
    def offerings(self):
        try:
            return json.loads(self.service_offerings or '[]')
        except ValueError:
            return []


class Fee(db.Model):
    __tablename__ = 'fees'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    fee = db.Column(db.String(120))
    per = db.Column(db.String(40))
    description = db.Column(db.Text)


class PickupRequest(db.Model):
    __tablename__ = 'pickup_requests'
    id = db.Column(db.Integer, primary_key=True)
    confirmation_number = db.Column(db.String(16), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    contact_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    company = db.Column(db.String(120))
    address_line1 = db.Column(db.String(160))
    city = db.Column(db.String(80))
    state = db.Column(db.String(10))
    zip = db.Column(db.String(12))
    phone = db.Column(db.String(30))
    pickup_date = db.Column(db.String(12))
    earliest_time = db.Column(db.String(10))
    latest_time = db.Column(db.String(10))
    packages = db.Column(db.Integer)
    weight_lb = db.Column(db.Float)
    service = db.Column(db.String(60))
    saturday = db.Column(db.Boolean, default=False)
    fee_usd = db.Column(db.Float)
    payment = db.Column(db.String(40))
    status = db.Column(db.String(30), default='Scheduled')


class Claim(db.Model):
    __tablename__ = 'claims'
    __table_args__ = (
        db.Index('ix_claims_tracking_number', 'tracking_number'),
    )
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.String(14), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    tracking_number = db.Column(db.String(24), nullable=False)
    email = db.Column(db.String(120))
    role = db.Column(db.String(20))
    problem_type = db.Column(db.String(20))
    merchandise = db.Column(db.String(260))
    item_count = db.Column(db.Integer, default=1)
    item_value = db.Column(db.Float)
    currency = db.Column(db.String(8), default='USD')
    status = db.Column(db.String(40), nullable=False)
    events = db.Column(db.Text)          # JSON: [{day, label, done}]
    filed_day = db.Column(db.String(12))
    resolution_note = db.Column(db.Text)

    @property
    def event_rows(self):
        try:
            return json.loads(self.events or '[]')
        except ValueError:
            return []


class SupportArticle(db.Model):
    __tablename__ = 'support_articles'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(60), unique=True, nullable=False)
    category = db.Column(db.String(40))
    title = db.Column(db.String(160))
    body = db.Column(db.Text)
    upstream_url = db.Column(db.String(240))


class ContentPage(db.Model):
    __tablename__ = 'content_pages'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(60), unique=True, nullable=False)
    title = db.Column(db.String(160))
    body = db.Column(db.Text)
    upstream_url = db.Column(db.String(240))


class ServiceAlert(db.Model):
    __tablename__ = 'service_alerts'
    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.String(20), unique=True)
    title = db.Column(db.String(120))
    body = db.Column(db.Text)
    link = db.Column(db.String(240))


class RateQuote(db.Model):
    """One captured service quote for a lane/weight/residential combination.

    Prices are the retail quotes the live Calculate Time and Cost wizard
    displayed on 2026-09-28 (guest, commercial origin & destination unless
    residential is set). See source_data/rates.json for provenance.
    """
    __tablename__ = 'rate_quotes'
    __table_args__ = (
        db.Index('ix_rate_quotes_lane_id', 'lane_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    lane_id = db.Column(db.String(12), nullable=False)
    weight_lb = db.Column(db.Integer, nullable=False)
    residential = db.Column(db.Boolean, default=False)
    service_code = db.Column(db.String(6), nullable=False)
    service_name = db.Column(db.String(80))
    price_usd = db.Column(db.Float)
    days_in_transit = db.Column(db.Integer)
    delivered_by = db.Column(db.String(80))
    guaranteed = db.Column(db.Boolean, default=False)
    latest_pickup = db.Column(db.String(80))
    schedule_by = db.Column(db.String(40))
    billable_weight_lb = db.Column(db.Float)
    transportation_usd = db.Column(db.Float)
    das_usd = db.Column(db.Float)
    fuel_usd = db.Column(db.Float)

    @property
    def breakdown(self):
        return {'transportation_usd': self.transportation_usd,
                'delivery_area_surcharge_usd': self.das_usd,
                'fuel_surcharge_usd': self.fuel_usd,
                'charges_per_package_usd': self.price_usd}


class Lane(db.Model):
    __tablename__ = 'lanes'
    lane_id = db.Column(db.String(12), primary_key=True)
    origin_city = db.Column(db.String(60))
    origin_zip = db.Column(db.String(12))
    dest_city = db.Column(db.String(60))
    dest_zip = db.Column(db.String(12))
    origin_lat = db.Column(db.Float)
    origin_lng = db.Column(db.Float)
    dest_lat = db.Column(db.Float)
    dest_lng = db.Column(db.Float)


class TrackingChange(db.Model):
    __tablename__ = 'tracking_changes'
    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipments.id'), nullable=False)
    change_type = db.Column(db.String(40))
    detail = db.Column(db.Text)
    request_day = db.Column(db.String(12))


class StatusMeaning(db.Model):
    __tablename__ = 'status_meanings'
    status = db.Column(db.String(60), primary_key=True)
    meaning = db.Column(db.Text)


class ZipGeocode(db.Model):
    """Origin geocodes captured for the seeded locator searches."""
    __tablename__ = 'zip_geocodes'
    zip = db.Column(db.String(12), primary_key=True)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    formatted = db.Column(db.String(120))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _load_source(name):
    with open(os.path.join(BASE_DIR, 'source_data', name), encoding='utf-8') as fh:
        return json.load(fh)


def usd(v):
    return f"${v:,.2f}"


def parse_nums(raw):
    """Split the tracking widget input into individual tracking numbers."""
    if not raw:
        return []
    out, seen = [], set()
    for chunk in raw.replace(',', '\n').replace(';', '\n').split('\n'):
        t = chunk.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:25]


def valid_tracking_format(t):
    t = t.strip()
    if len(t) == 18 and t.startswith('1Z'):
        return True
    return False


def ups_check_digit(idd):
    """UPS 1Z check digit (numeric-only payload, standard mod-10 weighting)."""
    digits = [int(c) for c in idd if c.isdigit()]
    total = 0
    for i, d in enumerate(reversed(digits)):
        total += d * (3 if (i % 2 == 1) else 1)
    return str((10 - (total % 10)) % 10)


@app.template_filter('hhmm')
def hhmm(value):
    """Render captured military times (e.g. '900', '1900') as 9:00 AM."""
    if not value:
        return ''
    v = str(value).strip()
    if ':' in v:
        return v
    if len(v) == 4 and v.isdigit():
        h, m = int(v[:2]), v[2:]
        ap = 'AM' if h < 12 else 'PM'
        h12 = h % 12 or 12
        return f"{h12}:{m} {ap}"
    if len(v) == 3 and v.isdigit():
        h, m = int(v[:1]), v[1:]
        return f"{h}:{m} AM"
    return v


SERVICE_TRACK_CODE = {'1DM': '01', '1DA': '01', '1DP': '13', '2DM': '02',
                         '2DA': '02', '3DS': '12', 'GND': '03', 'GSP': '03'}


def make_tracking_number(shipper6, service_code, serial7):
    """Real 1Z format: 1Z + 6-char shipper + 2-digit service code + 7 digits
    + mod-10 check digit (18 characters total)."""
    payload = shipper6 + SERVICE_TRACK_CODE.get(service_code, '03') + serial7
    return '1Z' + payload + ups_check_digit(payload)


# --------------------------------------------------------------------------
# Rate engine (captured quotes + linear weight interpolation, disclosed)
# --------------------------------------------------------------------------
CAPTURED_WEIGHTS = [1, 5, 15, 40]
CAPTURED_LANES = None  # populated after seeding


def _lane_for(origin_zip, dest_zip):
    """Match an origin/destination ZIP pair to a captured lane.

    Exact ZIP match first; otherwise the lane whose origin+destination ZIPs
    share the same leading ZIP3 region, else None.
    """
    lanes = {l.lane_id: l for l in Lane.query.all()}
    for lid, lane in lanes.items():
        if lane.origin_zip == origin_zip and lane.dest_zip == dest_zip:
            return lid
    for lid, lane in lanes.items():
        if (lane.origin_zip[:3] == origin_zip[:3]
                and lane.dest_zip[:3] == dest_zip[:3]):
            return lid
    return None


def _captured_quotes(lane_id, residential=False):
    return {(q.weight_lb, q.service_code): q for q in RateQuote.query.filter_by(
        lane_id=lane_id, residential=residential).all()}


def estimate_quotes(origin_zip, dest_zip, weight_lb, residential=False):
    """Return the service card list for the estimator.

    Exact captured lane+weight quotes are returned verbatim; weights between
    captured points are linearly interpolated per service (documented in
    provenance.json as the mirror's estimate model).
    """
    lane_id = _lane_for(origin_zip, dest_zip)
    if lane_id is None:
        return None, None
    captured = _captured_quotes(lane_id, residential)
    if not captured:
        return None, None
    w = max(1, min(150, int(round(weight_lb))))
    if w in CAPTURED_WEIGHTS:
        rows = [captured[(w, code)] for (cw, code) in captured if cw == w]
        interpolated = False
    else:
        lo = max([x for x in CAPTURED_WEIGHTS if x <= w] + [1])
        hi = min([x for x in CAPTURED_WEIGHTS if x >= w] + [150])
        if hi == lo:
            hi = lo
        rows, interpolated = [], True
        codes = {code for (cw, code) in captured}
        for code in sorted(codes):
            qlo = captured.get((lo, code))
            qhi = captured.get((hi, code))
            if qlo is None:
                continue
            if qhi is None or hi == lo:
                rows.append(qlo)
                continue
            frac = (w - lo) / (hi - lo)
            price = round(qlo.price_usd + (qhi.price_usd - qlo.price_usd) * frac, 2)
            days = qlo.days_in_transit
            # clone a lightweight, ORM-detached quote-like object so the
            # interpolated rows never mutate shared session state.
            import types
            q = types.SimpleNamespace(
                service_code=qlo.service_code, service_name=qlo.service_name,
                price_usd=price, days_in_transit=days,
                delivered_by=qlo.delivered_by, guaranteed=qlo.guaranteed,
                latest_pickup=qlo.latest_pickup, schedule_by=qlo.schedule_by,
                billable_weight_lb=qlo.billable_weight_lb,
                transportation_usd=qlo.transportation_usd,
                das_usd=qlo.das_usd, fuel_usd=qlo.fuel_usd,
                _interpolated=True)
            rows.append(q)
    rows = [r for r in rows if r.price_usd is not None]
    rows.sort(key=lambda r: r.price_usd)
    return rows, lane_id


def breakdown_for(lane_id, weight_lb, residential, service_code):
    """Captured per-service price breakdown (transport + DAS + fuel)."""
    q = RateQuote.query.filter_by(lane_id=lane_id, weight_lb=weight_lb,
                                   residential=residential,
                                   service_code=service_code).first()
    return q.breakdown if q else None


def pickup_fee_for(date_iso, saturday=False):
    """On-Call Pickup fee per the Retail Rate Guide (source_data/fees.json).

    Saturday On-Call Pickup carries the $6.95 Saturday Stop Charge in addition
    to the applicable Future-Day On-Call Pickup charge.
    """
    if saturday:
        return round(9.65 + 6.95, 2), ("Future-Day UPS On-Call Pickup ($9.65) "
                                       "+ Saturday Stop Charge ($6.95)")
    if date_iso == MIRROR_DATE_ISO:
        return 15.75, "Same-Day UPS On-Call Pickup"
    return 9.65, "Future-Day UPS On-Call Pickup"


def declared_value_charge(value):
    """Declared Value for Carriage charge (Retail Rate Guide)."""
    if value is None or value <= 100:
        return 0.0
    if value <= 300:
        return 5.10
    import math as _m
    hundreds = _m.ceil(value / 100.0)
    return round(hundreds * 1.70, 2)


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('The email or password you entered is incorrect. Please try again.')
            return render_template('login.html'), 401
        login_user(user)
        target = request.args.get('next')
        if target and target.startswith('/'):
            return redirect(target)
        return redirect(url_for('account'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not name or '@' not in email or len(password) < 8:
            flash('Please complete all required fields. Passwords must be at least 8 characters.')
            return render_template('register.html'), 400
        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists. Please log in instead.')
            return render_template('register.html'), 409
        user = User(email=email, name=name,
                    password_hash=bcrypt.generate_password_hash(password).decode())
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('account'))
    return render_template('register.html')


# --------------------------------------------------------------------------
# Home
# --------------------------------------------------------------------------
@app.route('/')
def index():
    alerts = ServiceAlert.query.order_by(ServiceAlert.id).all()
    articles = SupportArticle.query.filter(
        SupportArticle.category.in_(['Tracking', 'Shipping'])).limit(6).all()
    return render_template('home.html', alerts=alerts, articles=articles,
                           MIRROR_DATE=MIRROR_DATE_ISO)


# --------------------------------------------------------------------------
# Tracking
# --------------------------------------------------------------------------
@app.route('/track')
def track():
    q = request.args.get('tracknums') or request.args.get('tracknum', '')
    nums = parse_nums(q)
    results = []
    for t in nums:
        shipment = Shipment.query.filter_by(tracking_number=t).first()
        if shipment:
            results.append({'num': t, 'shipment': shipment, 'error': None})
        elif not valid_tracking_format(t):
            results.append({'num': t, 'shipment': None,
                            'error': 'The tracking number you entered is not valid. '
                                     'Please review or contact the sender to check the number.'})
        else:
            results.append({'num': t, 'shipment': None,
                            'error': 'Currently, we are not able to provide the tracking '
                                     'details. We can’t locate shipments if we haven’t '
                                     'received information from the sender.'})
    return render_template('track.html', results=results, query=q)


@app.route('/track/detail/<tracking_number>')
def track_detail(tracking_number):
    shipment = Shipment.query.filter_by(tracking_number=tracking_number).first_or_404()
    changes = TrackingChange.query.filter_by(shipment_id=shipment.id).all()
    meanings = {m.status: m.meaning
                for m in StatusMeaning.query.all()}
    meaning = None
    if shipment.status == 'Exception':
        meaning = meanings.get('Exception')
    elif shipment.status == 'Label Created':
        meaning = meanings.get('Label Created')
    elif shipment.status == 'Transferred to Post Office':
        meaning = meanings.get('Transferred to Post Office for Delivery')
    elif shipment.status == 'Awaiting Customer Pickup':
        meaning = meanings.get('Delivered to a UPS Access Point')
    hold_location = None
    if shipment.hold_location_id:
        hold_location = Location.query.filter_by(
            location_id=shipment.hold_location_id).first()
    package_groups = {}
    if shipment.multi_package:
        for ev in shipment.events:
            package_groups.setdefault(ev.package_n, []).append(ev)
    return render_template('track_detail.html', s=shipment, changes=changes,
                           meaning=meaning, hold_location=hold_location,
                           package_groups=package_groups,
                           status_meanings=meanings)


@app.route('/track/detail/<tracking_number>/change-delivery', methods=['GET', 'POST'])
def change_delivery(tracking_number):
    shipment = Shipment.query.filter_by(tracking_number=tracking_number).first_or_404()
    if shipment.status in ('Delivered',):
        flash('This shipment has already been delivered, so delivery changes are no longer available.')
        return redirect(url_for('track_detail', tracking_number=tracking_number))
    if request.method == 'POST':
        change_type = request.form.get('change_type', '')
        if change_type == 'hold':
            zip_code = request.form.get('zip', '').strip()
            points = locations_for_zip(zip_code)
            aps = [p for p in points if p['loc'].type in ('UPS Access Point', 'The UPS Store')]
            if not aps:
                flash('No UPS Access Point locations were found near that ZIP code. '
                     'Please try another ZIP code.')
                return render_template('change_delivery.html', s=shipment,
                                       access_points=[], selected_zip=zip_code)
            choice = request.form.get('location_id', '')
            chosen = next((p['loc'] for p in aps if p['loc'].location_id == choice), None)
            if not chosen:
                return render_template('change_delivery.html', s=shipment,
                                       access_points=aps, selected_zip=zip_code)
            ev = TrackingEvent(
                shipment_id=shipment.id,
                seq=(max(e.seq for e in shipment.events) + 1) if shipment.events else 1,
                day=MIRROR_DATE_ISO, time='—',
                status='Hold for Pickup Requested',
                location=f"{chosen.city}, {chosen.state}",
                description=(f"Delivery changed: the package will be held for pickup at "
                             f"{chosen.name.title()}, {chosen.addr1.title()}, {chosen.city}, "
                             f"{chosen.state} {chosen.zip}. Bring a government-issued photo ID."))
            db.session.add(ev)
            db.session.add(TrackingChange(shipment_id=shipment.id, change_type='hold',
                                          detail=chosen.location_id, request_day=MIRROR_DATE_ISO))
            shipment.hold_location_id = chosen.location_id
            shipment.hold_by = '2026-10-05'
            db.session.commit()
            flash('Hold for Pickup Confirmed. Your package will be available at the '
                  'selected UPS location once it arrives.')
            return redirect(url_for('track_detail', tracking_number=tracking_number))
        if change_type == 'address':
            new_addr = request.form.get('new_address', '').strip()
            if len(new_addr) < 8:
                flash('Please enter the complete new delivery address.')
                return render_template('change_delivery.html', s=shipment,
                                       access_points=[], selected_zip='')
            ev = TrackingEvent(
                shipment_id=shipment.id,
                seq=(max(e.seq for e in shipment.events) + 1) if shipment.events else 1,
                day=MIRROR_DATE_ISO, time='—',
                status='Deliver to Another Address Requested',
                location=f"{shipment.to_city}, {shipment.to_state}",
                description=f"Delivery changed: reroute requested to {new_addr}. "
                            f"A UPS Delivery Intercept fee of $18.00 applies "
                            f"(Web/Electronic request).")
            db.session.add(ev)
            db.session.add(TrackingChange(shipment_id=shipment.id, change_type='address',
                                          detail=new_addr, request_day=MIRROR_DATE_ISO))
            db.session.commit()
            flash('Reroute request submitted. Delivery changes requested by the shipper '
                  'may trigger a UPS Delivery Intercept fee of $18.00.')
            return redirect(url_for('track_detail', tracking_number=tracking_number))
        if change_type == 'reschedule':
            new_date = request.form.get('new_date', '').strip()
            try:
                requested = date.fromisoformat(new_date)
            except ValueError:
                requested = None
            if requested is None or requested <= date.fromisoformat(MIRROR_DATE_ISO):
                flash('Choose a valid future delivery date.')
                return render_template('change_delivery.html', s=shipment,
                                       access_points=[], selected_zip=''), 400
            ev = TrackingEvent(
                shipment_id=shipment.id,
                seq=(max(e.seq for e in shipment.events) + 1) if shipment.events else 1,
                day=MIRROR_DATE_ISO, time='—',
                status='Reschedule Delivery Requested',
                location=f"{shipment.to_city}, {shipment.to_state}",
                description=f"Delivery changed: rescheduled delivery requested for {new_date}.")
            db.session.add(ev)
            db.session.add(TrackingChange(shipment_id=shipment.id, change_type='reschedule',
                                          detail=new_date, request_day=MIRROR_DATE_ISO))
            db.session.commit()
            flash('Reschedule Delivery Confirmed.')
            return redirect(url_for('track_detail', tracking_number=tracking_number))
        flash('Please choose a delivery change option.')
    zip_code = request.values.get('zip', '')
    aps = locations_for_zip(zip_code) if zip_code else []
    aps = [p for p in aps if p['loc'].type in ('UPS Access Point', 'The UPS Store')]
    return render_template('change_delivery.html', s=shipment,
                           access_points=aps, selected_zip=zip_code)


# --------------------------------------------------------------------------
# Calculate Time and Cost
# --------------------------------------------------------------------------
@app.route('/ctc', methods=['GET', 'POST'])
def ctc():
    form = {}
    rows = None
    lane = None
    interpolated = False
    if request.method == 'POST':
        action = request.form.get('action', 'estimate')
        if action == 'clear':
            return render_template('ctc.html', form={}, rows=None)
        origin_zip = request.form.get('origin_zip', '').strip()
        dest_zip = request.form.get('dest_zip', '').strip()
        origin_city = request.form.get('origin_city', '').strip()
        dest_city = request.form.get('dest_city', '').strip()
        weight = request.form.get('weight', '').strip()
        residential = request.form.get('residential') == 'on'
        dims = {
            'length': request.form.get('length', ''),
            'width': request.form.get('width', ''),
            'height': request.form.get('height', ''),
        }
        form = {'origin_zip': origin_zip, 'dest_zip': dest_zip,
                'origin_city': origin_city, 'dest_city': dest_city,
                'weight': weight, 'residential': residential, 'dims': dims}
        errors = []
        if not (origin_zip.isdigit() and len(origin_zip) == 5):
            errors.append('Origin ZIP Code is required (5 digits).')
        if not (dest_zip.isdigit() and len(dest_zip) == 5):
            errors.append('Destination ZIP Code is required (5 digits).')
        try:
            w = float(weight)
            if not (0 < w <= 150):
                errors.append('Weight must be between 1 and 150 lbs.')
        except ValueError:
            errors.append('Package weight is required.')
        if errors:
            return render_template('ctc.html', form=form, rows=None, errors=errors)
        rows, lane = estimate_quotes(origin_zip, dest_zip, w, residential)
        if rows is None:
            return render_template('ctc.html', form=form, rows=None,
                                   errors=['We can’t provide quotes for that '
                                           'origin and destination pair. The estimator '
                                           'covers the markets captured in this mirror '
                                           '(e.g., New York, Chicago, Atlanta, San '
                                           'Francisco, Seattle, Miami, Austin, Denver, '
                                           'Boston, Philadelphia, Cincinnati).'])
        form['weight_num'] = int(round(w))
        interpolated = getattr(rows[0], '_interpolated', False) if rows else False
        # Billable weight per the UPS retail rule: max(actual, dimensional)
        # where dimensional weight = L*W*H/139 (Retail Rate and Service Guide).
        dim_lb = None
        try:
            L = float(dims.get('length') or 0)
            W = float(dims.get('width') or 0)
            H = float(dims.get('height') or 0)
            if L > 0 and W > 0 and H > 0:
                dim_lb = round(L * W * H / 139.0, 1)
        except ValueError:
            dim_lb = None
        billable_lb = round(max(w, dim_lb), 1) if dim_lb else w
        for r in rows:
            r._breakdown = breakdown_for(lane, int(round(w)), residential, r.service_code)
            if not r.billable_weight_lb:
                r.billable_weight_lb = billable_lb
    return render_template('ctc.html', form=form, rows=rows, lane=lane,
                           interpolated=interpolated)


# --------------------------------------------------------------------------
# Create a Shipment (guest wizard)
# --------------------------------------------------------------------------
SHIP_WIZARD_STEPS = ['where', 'package', 'service', 'review']


@app.route('/ship', methods=['GET', 'POST'])
def ship():
    data = session.get('ship_wizard', {})
    step = request.values.get('step') or (data.get('step') or 'where')
    if step not in SHIP_WIZARD_STEPS:
        step = 'where'
    errors = []
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'reset':
            session.pop('ship_wizard', None)
            return redirect(url_for('ship'))
        if step == 'where':
            data.update({
                'from_name': request.form.get('from_name', '').strip(),
                'from_street': request.form.get('from_street', '').strip(),
                'from_city': request.form.get('from_city', '').strip(),
                'from_state': request.form.get('from_state', '').strip(),
                'from_zip': request.form.get('from_zip', '').strip(),
                'to_name': request.form.get('to_name', '').strip(),
                'to_street': request.form.get('to_street', '').strip(),
                'to_city': request.form.get('to_city', '').strip(),
                'to_state': request.form.get('to_state', '').strip(),
                'to_zip': request.form.get('to_zip', '').strip(),
                'residential': request.form.get('residential') == 'on',
            })
            for field, label in [('from_name', 'Ship From: name'),
                                 ('from_street', 'Ship From: street address'),
                                 ('from_city', 'Ship From: city'),
                                 ('from_state', 'Ship From: state'),
                                 ('from_zip', 'Ship From: ZIP Code'),
                                 ('to_name', 'Ship To: name'),
                                 ('to_street', 'Ship To: street address'),
                                 ('to_city', 'Ship To: city'),
                                 ('to_state', 'Ship To: state'),
                                 ('to_zip', 'Ship To: ZIP Code')]:
                if not data.get(field):
                    errors.append(f'{label} is required.')
            if data.get('from_zip') and not (len(data['from_zip']) == 5 and data['from_zip'].isdigit()):
                errors.append('Ship From ZIP Code must be 5 digits.')
            if data.get('to_zip') and not (len(data['to_zip']) == 5 and data['to_zip'].isdigit()):
                errors.append('Ship To ZIP Code must be 5 digits.')
            if not errors:
                step = 'package'
        elif step == 'package':
            try:
                weight = float(request.form.get('weight', ''))
                if not (0 < weight <= 150):
                    raise ValueError
            except ValueError:
                weight = None
                errors.append('Package weight is required (up to 150 lbs).')
            data.update({
                'packaging': request.form.get('packaging', 'My Packaging'),
                'weight': weight,
                'length': request.form.get('length', ''),
                'width': request.form.get('width', ''),
                'height': request.form.get('height', ''),
                'declared_value': request.form.get('declared_value', '').strip(),
            })
            if data.get('declared_value'):
                try:
                    dv = float(data['declared_value'])
                except ValueError:
                    dv = None
                    errors.append('Declared value must be a number.')
            else:
                dv = 0.0
            data['declared_value_num'] = dv
            if data.get('packaging') == 'My Packaging':
                for f in ('length', 'width', 'height'):
                    if not data.get(f):
                        errors.append(f'Package {f} is required for My Packaging.')
            if not errors:
                step = 'service'
        elif step == 'service':
            service_code = request.form.get('service_code', '')
            svc = Service.query.filter_by(code=service_code).first()
            if not svc:
                errors.append('Please select a shipping service.')
            else:
                data['service_code'] = service_code
                data['signature'] = request.form.get('signature', '')
                step = 'review'
        elif step == 'review':
            service_code = data.get('service_code')
            svc = Service.query.filter_by(code=service_code).first() if service_code else None
            if not svc:
                errors.append('Please select a shipping service.')
                step = 'service'
            else:
                # build the shipment (real 1Z tracking-number format)
                serial = 7000000 + Shipment.query.count() + 1
                tn = make_tracking_number('5F71X9', svc.code, str(serial).zfill(7))
                while Shipment.query.filter_by(tracking_number=tn).first():
                    serial += 1
                    tn = make_tracking_number('5F71X9', svc.code, str(serial).zfill(7))
                weight = float(data.get('weight') or 1)
                days = svc.days or 3
                from datetime import timedelta
                sched = MIRROR_DATE + timedelta(days=days if days else 3)
                dv = data.get('declared_value_num') or 0.0
                shipment = Shipment(
                    tracking_number=tn,
                    user_id=current_user.id if current_user.is_authenticated else None,
                    direction='outbound',
                    service_code=svc.code,
                    shipper_name=data.get('from_name'),
                    from_city=data.get('from_city'), from_state=data.get('from_state'),
                    to_name=data.get('to_name'),
                    to_city=data.get('to_city'), to_state=data.get('to_state'),
                    to_zip=data.get('to_zip'),
                    weight_lb=weight, packages=1,
                    signature=data.get('signature') or None,
                    scheduled_delivery=sched.isoformat(),
                    status='Label Created',
                    declared_value=dv if dv else None,
                    created_in_session=True,
                )
                db.session.add(shipment)
                db.session.flush()
                db.session.add(TrackingEvent(
                    shipment_id=shipment.id, seq=1, day=MIRROR_DATE_ISO,
                    time='—', status='Label Created',
                    location=f"{data.get('from_city')}, {data.get('from_state')}",
                    description='Shipping information received by UPS. '
                                'Drop off your package at a UPS location or '
                                'hand it to a UPS driver to start its journey.'))
                db.session.commit()
                session.pop('ship_wizard', None)
                return redirect(url_for('ship_confirm', tracking_number=tn))
        data['step'] = step
        session['ship_wizard'] = data
        session.modified = True
    options = []
    if step == 'service' and data.get('from_zip') and data.get('to_zip'):
        w = float(data.get('weight') or 1)
        options, lane = estimate_quotes(data['from_zip'], data['to_zip'],
                                        w, data.get('residential', False))
        if options is None:
            errors.append('We can’t show service options for that origin and '
                           'destination pair in this mirror. Try one of the '
                           'supported markets (e.g., New York 10001, Chicago '
                           '60601, Atlanta 30301, San Francisco 94105).')
            options = []
    fees_by_name = {}
    for f in Fee.query.filter_by(category='delivery_options').all():
        fees_by_name[f.name] = f
    return render_template('ship.html', step=step, data=data, errors=errors,
                           options=options or None, fees=fees_by_name,
                           declared_value_charge=declared_value_charge)


@app.route('/ship/confirm/<tracking_number>')
def ship_confirm(tracking_number):
    shipment = Shipment.query.filter_by(tracking_number=tracking_number).first_or_404()
    svc = shipment.service
    dv_charge = declared_value_charge(shipment.declared_value or 0)
    sig_fee = 0.0
    if shipment.signature == 'Signature Required':
        sig_fee = 7.70
    elif shipment.signature == 'Adult Signature Required':
        sig_fee = 9.35
    return render_template('ship_confirm.html', s=shipment, svc=svc,
                           dv_charge=dv_charge, sig_fee=sig_fee)


# --------------------------------------------------------------------------
# Schedule a Pickup
# --------------------------------------------------------------------------
PICKUP_DATES = tuple((MIRROR_DATE + timedelta(days=i)).isoformat() for i in range(6))
PICKUP_EARLIEST_TIMES = ('8:00 AM', '9:00 AM', '10:00 AM', '11:00 AM',
                        '12:00 PM', '1:00 PM', '2:00 PM', '3:00 PM',
                        '4:00 PM', '5:00 PM')
PICKUP_LATEST_TIMES = ('12:00 PM', '1:00 PM', '2:00 PM', '3:00 PM',
                      '4:00 PM', '5:00 PM', '6:00 PM', '7:00 PM', '8:00 PM')


def pickup_schedule_errors(data):
    """Validate the same frozen schedule at review and immediately before saving."""
    errors = []
    if data.get('pickup_date') not in PICKUP_DATES:
        errors.append('Select an available pickup date.')
    earliest, latest = data.get('earliest'), data.get('latest')
    if earliest not in PICKUP_EARLIEST_TIMES or latest not in PICKUP_LATEST_TIMES:
        errors.append('Select valid earliest and latest pickup times.')
    elif datetime.strptime(latest, '%I:%M %p') <= datetime.strptime(earliest, '%I:%M %p'):
        errors.append('Latest available time must be later than earliest ready time.')
    return errors


@app.route('/pickup', methods=['GET', 'POST'])
def pickup():
    data = session.get('pickup_wizard', {})
    step = request.values.get('step') or (data.get('step') or 'location')
    errors = []
    if request.method == 'POST':
        if request.form.get('action') == 'reset':
            session.pop('pickup_wizard', None)
            return redirect(url_for('pickup'))
        if step == 'location':
            data.update({
                'company': request.form.get('company', '').strip(),
                'contact': request.form.get('contact', '').strip(),
                'street': request.form.get('street', '').strip(),
                'city': request.form.get('city', '').strip(),
                'state': request.form.get('state', '').strip(),
                'zip': request.form.get('zip', '').strip(),
                'phone': request.form.get('phone', '').strip(),
                'email': request.form.get('email', '').strip(),
                'residential': request.form.get('residential') == 'on',
            })
            for field, label in [('company', 'Company or Name'),
                                 ('street', 'Street address'),
                                 ('city', 'City'),
                                 ('state', 'State'),
                                 ('zip', 'ZIP Code'),
                                 ('phone', 'Phone number')]:
                if not data.get(field):
                    errors.append(f'{label} is required.')
            if data.get('email') and '@' not in data['email']:
                errors.append('Enter a valid email address.')
            if not errors:
                step = 'packages'
        elif step == 'packages':
            try:
                packages = int(request.form.get('packages', ''))
                if packages < 1 or packages > 99:
                    raise ValueError
            except ValueError:
                packages = None
                errors.append('Number of packages is required.')
            try:
                weight = float(request.form.get('weight', ''))
                if not (0 < weight <= 2000):
                    raise ValueError
            except ValueError:
                weight = None
                errors.append('Total weight of your pickup is required.')
            data.update({
                'packages': packages, 'weight': weight,
                'over70': request.form.get('over70') == 'on',
                'service': request.form.get('service', ''),
            })
            if not data.get('service'):
                errors.append('Select the UPS service(s) indicated by your shipping label(s).')
            if not errors:
                step = 'datetime'
        elif step == 'datetime':
            data.update({key: request.form.get(key, '')
                         for key in ('pickup_date', 'earliest', 'latest')})
            errors.extend(pickup_schedule_errors(data))
            if not errors:
                step = 'review'
        elif step == 'review':
            errors.extend(pickup_schedule_errors(data))
            if errors:
                step = 'datetime'
            else:
                saturday = data.get('pickup_date', '') in ('2026-10-03', '2026-10-10')
                fee, fee_label = pickup_fee_for(data.get('pickup_date', ''), saturday)
                confirmation = 'PK' + str(1000000 + PickupRequest.query.count() + 1)
                pr = PickupRequest(
                    confirmation_number=confirmation,
                    user_id=current_user.id if current_user.is_authenticated else None,
                    contact_name=data.get('company', ''),
                    email=data.get('email', ''),
                    company=data.get('company', ''),
                    address_line1=data.get('street', ''),
                    city=data.get('city', ''), state=data.get('state', ''), zip=data.get('zip', ''),
                    phone=data.get('phone', ''),
                    pickup_date=data.get('pickup_date', ''),
                    earliest_time=data.get('earliest', ''), latest_time=data.get('latest', ''),
                    packages=data.get('packages', 1), weight_lb=data.get('weight', 1),
                    service=data.get('service', ''),
                    saturday=saturday,
                    fee_usd=fee, payment=request.form.get('payment', 'Pay driver at pickup'),
                )
                db.session.add(pr)
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    confirmation = 'PK' + str(1000000 + PickupRequest.query.count() + 2)
                    pr.confirmation_number = confirmation
                    db.session.add(pr)
                    db.session.commit()
                session.pop('pickup_wizard', None)
                return redirect(url_for('pickup_confirm', confirmation=confirmation))
        data['step'] = step
        session['pickup_wizard'] = data
        session.modified = True
    fee_same, _ = pickup_fee_for(MIRROR_DATE_ISO)
    fee_future, _ = pickup_fee_for('2026-09-29')
    fee_saturday, _ = pickup_fee_for('2026-10-03', saturday=True)
    services = Service.query.order_by(Service.sort).all()
    return render_template('pickup.html', step=step, data=data, errors=errors,
                           services=services, fee_same=fee_same,
                           fee_future=fee_future, fee_saturday=fee_saturday,
                           MIRROR_DATE=MIRROR_DATE_ISO, pickup_dates=PICKUP_DATES,
                           earliest_times=PICKUP_EARLIEST_TIMES,
                           latest_times=PICKUP_LATEST_TIMES)


@app.route('/pickup/confirm/<confirmation>')
def pickup_confirm(confirmation):
    pr = PickupRequest.query.filter_by(confirmation_number=confirmation).first_or_404()
    return render_template('pickup_confirm.html', p=pr)


# --------------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------------
def locations_for_zip(zip_code):
    """Locations returned for a seeded locator search, ordered by distance.

    Distances are the haversine miles between the captured search geocode and
    each location's captured geocode — the same values the live locator shows.
    """
    geo = ZipGeocode.query.filter_by(zip=zip_code).first()
    if not geo:
        return []
    out = []
    for loc in Location.query.all():
        try:
            miles = haversine(geo.lat, geo.lng, float(loc.lat), float(loc.lng))
        except (TypeError, ValueError):
            continue
        if miles <= 15.05:
            out.append({'loc': loc, 'miles': miles})
    out.sort(key=lambda p: (p['miles'], p['loc'].location_id))
    return out


def haversine(lat1, lng1, lat2, lng2):
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lng1, lat2, lng2))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return round(2 * 3958.7613 * math.asin(math.sqrt(h)), 1)




@app.route('/locations')
def locations():
    zip_code = request.args.get('zip', '').strip()
    ftype = request.args.get('type', 'all')
    pts = locations_for_zip(zip_code) if zip_code and len(zip_code) == 5 else []
    if ftype != 'all':
        pts = [p for p in pts if p['loc'].type == ftype]
    known = sorted(z.zip for z in ZipGeocode.query.all())
    return render_template('locations.html', points=pts, zip=zip_code,
                           ftype=ftype, known=known,
                           types=['all', 'The UPS Store', 'UPS Access Point',
                                  'UPS Drop Box', 'Authorized Shipping Outlet',
                                  'Retail Chains'])


@app.route('/locations/<location_id>')
def location_detail(location_id):
    loc = Location.query.filter_by(location_id=location_id).first_or_404()
    return render_template('location_detail.html', l=loc)


# --------------------------------------------------------------------------
# Services
# --------------------------------------------------------------------------
@app.route('/services')
def services():
    svcs = Service.query.order_by(Service.sort).all()
    return render_template('services.html', services=svcs)


@app.route('/services/compare')
def services_compare():
    svcs = Service.query.order_by(Service.sort).all()
    return render_template('services_compare.html', services=svcs)


@app.route('/services/<code>')
def service_detail(code):
    svc = Service.query.filter_by(code=code).first_or_404()
    others = Service.query.filter(Service.code != code).order_by(Service.sort).all()
    return render_template('service_detail.html', s=svc, others=others)


# --------------------------------------------------------------------------
# Business solutions / content pages
# --------------------------------------------------------------------------
BUSINESS_PAGES = [
    ('pickup-dropoff-options', 'Pickup and Drop-off Options'),
    ('daily-pickup', 'UPS Daily Pickup'),
    ('smart-pickup', 'UPS Smart Pickup®'),
    ('day-specific-pickup', 'Day-Specific Pickup'),
    ('weekend-pickup', 'Saturday Delivery and Pickup Options'),
    ('ups-access-point', 'UPS Access Point® Locations'),
    ('business-shipping-tools', 'Business Shipping Tools'),
    ('simplify-returns', 'Customer Return Services'),
    ('ups-billing', 'Manage UPS Billing and Invoices'),
    ('quantum-view', 'Quantum View for Large Enterprises'),
    ('my-choice-business', 'UPS My Choice® for Business'),
    ('expand-internationally', 'Expand Your Business Internationally'),
    ('consulting-services', 'Consulting Services'),
    ('customized-logistics', 'UPS Customized Shipping and Logistics Services'),
]

CONTENT_KEY_TO_PAGE = {
    'pickup_dropoff_options': 'pickup-dropoff-options',
    'daily_pickup': 'daily-pickup',
    'smart_pickup': 'smart-pickup',
    'day_specific_pickup': 'day-specific-pickup',
    'weekend_pickup': 'weekend-pickup',
    'ups_access_point_program': 'ups-access-point',
    'business_shipping_tools': 'business-shipping-tools',
    'simplify_returns': 'simplify-returns',
    'ups_billing': 'ups-billing',
    'quantum_view': 'quantum-view',
    'my_choice_business': 'my-choice-business',
    'expand_internationally': 'expand-internationally',
    'consulting_services': 'consulting-services',
    'customized_logistics': 'customized-logistics',
    'international_shipping': 'international-shipping',
    'tariffs': 'tariffs',
    'order_supplies': 'order-supplies',
    'the_ups_store': 'the-ups-store',
    'store_pack_and_ship': 'store-pack-and-ship',
    'store_services': 'store-services',
    'store_print': 'store-print',
    'store_mailboxes': 'store-mailboxes',
    'service_alerts': 'service-alerts',
    'how_to_ship': 'how-to-ship',
    'services_domestic': 'services-domestic',
}

PAGE_HERO = {
    'pickup-dropoff-options': 'pickup-dropoff-packages-b-1166486-q421.jpg',
    'daily-pickup': 'ups-warehouse.png',
    'smart-pickup': 'rfid-package-car.png',
    'day-specific-pickup': 'ups-volume-growth.png',
    'weekend-pickup': 'icon-package-calendar.png',
    'ups-access-point': 'ups-location-map.png',
    'business-shipping-tools': 'intl-business-tools-glc-4q25.png',
    'simplify-returns': 'ups-package-redirect-truck.png',
    'ups-billing': 'ups-pay-bill.png',
    'quantum-view': 'us-warehouse-g1250486579-q425.png',
    'my-choice-business': 'ups-package-ontime.png',
    'expand-internationally': 'expand-buisness-g-1281476617-q123.png',
    'consulting-services': 'bearings-petbakery-1232039-4934-2q25.jpg',
    'customized-logistics': 'manufacturing-employee-paceimagery.png',
    'international-shipping': 'intl-ship-guides-services-4q25.png',
    'tariffs': 'intl-ship-guides-costs-4q25.png',
    'order-supplies': 'shipping-supplies-g-1443630430-q123-flipped.jpg',
    'how-to-ship': 'shipment-size-weight-measure-package-b-1224353-q421.jpg',
    'store-pack-and-ship': 'ups-store-pack-and-ship.png',
    'store-services': 'hb-instore-services-q22026.jpg',
    'store-print': 'tupss-printing-042026.jpg',
    'store-mailboxes': 'tupss-mailbox-q22026.png',
}

ARTICLE_HERO = {
    'understanding-tracking-status': 'ups-package-logo.png',
    'ups-delivery-notice': 'icon-package-calendar.png',
    'ups-delivery-intercept': 'ups-package-redirect-truck.png',
    'where-is-my-package': 'ups-questions-support.png',
    'how-to-return-a-package': 'ups-store.png',
    'flat-rate-shipping': 'ups-boxes-packaging.png',
    'ups-ground-saver': 'fastest-ground-g-1395474771-q323.png',
    'freight-quote': '960x540-freight-consolidation-banner.jpg',
    'manage-your-profile': 'ups-icon-account.png',
    'shipping-guides-and-resources': 'ups-articles-note.png',
    'shipping-tools': 'api-request-banner.png',
    'file-a-claim': 'ups-file-folder.png',
    'shipping-costs-and-rates': 'ups-money-manage.png',
    'signature-requirements': 'packing-shipping-regulated-item-b-1166505-q421.jpg',
    'how-to-ship-a-package': 'shipment-size-weight-measure-package-b-1224353-q421.jpg',
    'void-a-shipment': 'ups-accept-documents.png',
    'change-a-delivery': 'ups-package-dimensions-weight.png',
    'ups-my-choice': 'stay-connected-mobile-us-1-q125.jpg',
}


def _content_page(page_key):
    for source_key, page in CONTENT_KEY_TO_PAGE.items():
        if page == page_key:
            return ContentPage.query.filter_by(key=source_key).first()
    return None


@app.route('/business')
def business():
    pickup_fees = Fee.query.filter_by(category='pickup_options').all()
    saturday_fees = Fee.query.filter_by(category='saturday_options').all()
    return render_template('business.html', pages=BUSINESS_PAGES,
                           pickup_fees=pickup_fees, saturday_fees=saturday_fees)


@app.route('/business/<page_key>')
def business_page(page_key):
    if page_key not in [p for p, _ in BUSINESS_PAGES]:
        abort(404)
    page = _content_page(page_key)
    if not page:
        abort(404)
    pickup_fees = Fee.query.filter_by(category='pickup_options').all() \
        if page_key in ('pickup-dropoff-options', 'daily-pickup', 'smart-pickup',
                        'day-specific-pickup', 'weekend-pickup') else []
    saturday_fees = Fee.query.filter_by(category='saturday_options').all() \
        if page_key == 'weekend-pickup' else []
    return render_template('business_page.html', page=page,
                           pickup_fees=pickup_fees, saturday_fees=saturday_fees,
                           hero=PAGE_HERO.get(page_key),
                           page_key=page_key)


@app.route('/store')
def store():
    page = _content_page('the-ups-store')
    return render_template('store.html', page=page)


@app.route('/store/<page_key>')
def store_page(page_key):
    keys = {'pack-and-ship': 'store_pack_and_ship',
            'services': 'store_services',
            'print': 'store_print',
            'mailboxes': 'store_mailboxes'}
    if page_key not in keys:
        abort(404)
    page = ContentPage.query.filter_by(key=keys[page_key]).first_or_404()
    return render_template('business_page.html', page=page, pickup_fees=[],
                           saturday_fees=[], hero=PAGE_HERO.get(page_key),
                           page_key='store-' + page_key)


@app.route('/shipping/<page_key>')
def shipping_guide(page_key):
    keys = {'international': 'international_shipping',
            'tariffs': 'tariffs',
            'order-supplies': 'order_supplies',
            'how-to-ship': 'how_to_ship'}
    if page_key not in keys:
        abort(404)
    page = ContentPage.query.filter_by(key=keys[page_key]).first_or_404()
    return render_template('business_page.html', page=page, pickup_fees=[],
                           saturday_fees=[], hero=PAGE_HERO.get(page_key),
                           page_key='ship-' + page_key)


@app.route('/alerts')
def alerts():
    alerts = ServiceAlert.query.order_by(ServiceAlert.id).all()
    return render_template('alerts.html', alerts=alerts)


# --------------------------------------------------------------------------
# Support center + articles
# --------------------------------------------------------------------------
@app.route('/support')
def support():
    q = request.args.get('q', '').strip()
    articles = SupportArticle.query.order_by(SupportArticle.category, SupportArticle.id).all()
    if q:
        ql = q.lower()
        articles = [a for a in articles if ql in a.title.lower() or ql in (a.body or '').lower()]
    categories = {}
    for a in SupportArticle.query.order_by(SupportArticle.id).all():
        categories.setdefault(a.category, []).append(a)
    return render_template('support.html', articles=articles, categories=categories, q=q)


@app.route('/support/article/<key>')
def support_article(key):
    article = SupportArticle.query.filter_by(key=key).first_or_404()
    related = SupportArticle.query.filter(
        SupportArticle.category == article.category,
        SupportArticle.key != key).limit(4).all()
    return render_template('support_article.html', a=article, related=related,
                           hero=ARTICLE_HERO.get(key))


# --------------------------------------------------------------------------
# Claims
# --------------------------------------------------------------------------
@app.route('/claims')
def claims():
    return render_template('claims.html')


@app.route('/claims/new', methods=['GET', 'POST'])
def claim_new():
    step = request.values.get('step', 'start')
    data = session.get('claim_wizard', {})
    errors = []
    if request.method == 'POST':
        if request.form.get('action') == 'reset':
            session.pop('claim_wizard', None)
            return redirect(url_for('claim_new'))
        if step == 'start':
            tn = request.form.get('tracking_number', '').strip()
            shipment = Shipment.query.filter_by(tracking_number=tn).first()
            data['tracking_number'] = tn
            if not tn:
                errors.append('UPS Tracking Number is required.')
            elif not shipment:
                errors.append('We can’t locate that tracking number. Please review '
                              'the number and try again.')
            else:
                data['receiver'] = request.form.get('receiver', '')
                if data['receiver'] not in ('Yes', 'No'):
                    errors.append('Please tell us if you are the receiver of the package.')
                else:
                    step = 'problem'
        elif step == 'problem':
            data['problem_type'] = request.form.get('problem_type', '')
            if data['problem_type'] not in ('lost', 'damaged'):
                errors.append('Please choose the problem you are trying to report.')
            else:
                step = 'details'
        elif step == 'details':
            merch = request.form.get('merchandise', '').strip()
            count = request.form.get('item_count', '1').strip()
            value = request.form.get('item_value', '').strip()
            email = request.form.get('email', '').strip()
            data.update({'merchandise': merch, 'item_count': count,
                          'item_value': value, 'email': email})
            if len(merch) < 5:
                errors.append('Merchandise Description is required '
                              '(be as specific as possible).')
            try:
                c = int(count)
                if c < 1:
                    raise ValueError
            except ValueError:
                errors.append('Number of items must be a whole number.')
            try:
                v = float(value)
                if v <= 0:
                    raise ValueError
            except ValueError:
                errors.append('Declared item value is required.')
            if '@' not in email:
                errors.append('A contact email address is required.')
            if not errors:
                step = 'review'
        elif step == 'review':
            tn = data.get('tracking_number', '')
            shipment = Shipment.query.filter_by(tracking_number=tn).first()
            if not shipment:
                errors.append('Please start over — we can no longer locate that shipment.')
                step = 'start'
            else:
                claim_id = 'CLM' + str(4000000 + Claim.query.count() + 1)
                while Claim.query.filter_by(claim_id=claim_id).first():
                    claim_id = 'CLM' + str(4000000 + Claim.query.count() + 2)
                events = json.dumps([
                    {"day": MIRROR_DATE_ISO, "label": "Claim Reported", "done": True},
                    {"day": MIRROR_DATE_ISO, "label": "Claim Review in Progress", "done": True},
                    {"day": "", "label": "Documentation Under Review", "done": False},
                    {"day": "", "label": "Resolution", "done": False},
                ])
                claim = Claim(
                    claim_id=claim_id,
                    user_id=current_user.id if current_user.is_authenticated else None,
                    tracking_number=tn,
                    email=data.get('email', ''),
                    role='receiver' if data.get('receiver') == 'Yes' else 'shipper',
                    problem_type=data.get('problem_type', ''),
                    merchandise=data.get('merchandise', ''),
                    item_count=int(data.get('item_count') or 1),
                    item_value=float(data.get('item_value') or 0),
                    status='Claim Review in Progress',
                    events=events, filed_day=MIRROR_DATE_ISO,
                    resolution_note='Unless additional investigation is required, '
                                    'you can typically expect a resolution to your '
                                    'claim in 8 to 10 business days.')
                db.session.add(claim)
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    claim_id = 'CLM' + str(4000000 + Claim.query.count() + 2)
                    claim.claim_id = claim_id
                    db.session.add(claim)
                    db.session.commit()
                session.pop('claim_wizard', None)
                return redirect(url_for('claim_status', claim_id=claim_id))
        data['step'] = step
        session['claim_wizard'] = data
        session.modified = True
    shipment = None
    if data.get('tracking_number'):
        shipment = Shipment.query.filter_by(
            tracking_number=data['tracking_number']).first()
    return render_template('claim_new.html', step=step, data=data,
                           errors=errors, shipment=shipment)


@app.route('/claims/status/<claim_id>')
def claim_status(claim_id):
    claim = Claim.query.filter_by(claim_id=claim_id).first_or_404()
    shipment = Shipment.query.filter_by(
        tracking_number=claim.tracking_number).first()
    return render_template('claim_status.html', c=claim, s=shipment)


# --------------------------------------------------------------------------
# Account
# --------------------------------------------------------------------------
@app.route('/account')
@login_required
def account():
    shipments = Shipment.query.filter_by(user_id=current_user.id).order_by(
        Shipment.id.desc()).all()
    pickups = PickupRequest.query.filter_by(user_id=current_user.id).order_by(
        PickupRequest.id.desc()).all()
    claims = Claim.query.filter_by(user_id=current_user.id).order_by(
        Claim.id.desc()).all()
    return render_template('account.html', shipments=shipments,
                           pickups=pickups, claims=claims)


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------
@app.route('/_health')
def health_probe():
    import _health
    result = _health.health()
    result.update({
        'shipments': Shipment.query.count(),
        'tracking_events': TrackingEvent.query.count(),
        'locations': Location.query.count(),
        'rate_quotes': RateQuote.query.count(),
        'services': Service.query.count(),
        'users': User.query.count(),
        'claims': Claim.query.count(),
        'pickups': PickupRequest.query.count(),
        'articles': SupportArticle.query.count(),
    })
    return jsonify(result)


# --------------------------------------------------------------------------
# Boot
# --------------------------------------------------------------------------
def bootstrap():
    """Create tables and seed if empty (idempotent at function level)."""
    with app.app_context():
        db.create_all()
        import seed_data
        seed_data.seed_all()


if os.environ.get('WEBSYN_SKIP_BOOTSTRAP') != '1':
    bootstrap()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 40123))
    app.run(host='0.0.0.0', port=port, debug=False)
