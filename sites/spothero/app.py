"""SpotHero mirror — Flask app.

Mirrors https://spothero.com/ (parking reservations): search across cities,
destinations, events and airports; facility detail pages with live quotes;
guest + signed-in checkout with promo codes; account area with reservations
(cancel / extend), payment methods, favorites and profile; city / destination /
airport / stadium / monthly landing pages; FAQ hub and the static info pages.

All catalog rows come from the tracked source_data_*.json snapshots captured
from spothero.com on 2026-09-26; the
SQLite seed is deterministically generated at build time (see .build-generated-seed).
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import re
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from urllib.parse import quote as url_quote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'SPOTHERO_DB_PATH',
    'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'spothero.db'))
app.config['SECRET_KEY'] = 'webharbor-spothero-dev-key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = ''
csrf = CSRFProtect(app)

# The snapshot date the mirror is pinned to; every "today" default and every
# seeded reservation is expressed relative to this constant.
MIRROR_TODAY = datetime(2026, 9, 26)

SERVICE_FEE_RATE = 0.06
SERVICE_FEE_MIN = 0.99
EVENT_FEE_RATE = 0.085
AIRPORT_FEE_FLAT = 4.00
EVENT_RATE_MULT = 1.5

WALK_SPEED_MPS = 1.4


# --------------------------------------------------------------------- models

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(64), default='')
    last_name = db.Column(db.String(64), default='')
    phone = db.Column(db.String(32), default='')
    license_plate = db.Column(db.String(16), default='')
    vehicle = db.Column(db.String(64), default='')

    reservations = db.relationship('Reservation', backref='user', lazy=True)
    payment_methods = db.relationship('PaymentMethod', backref='user', lazy=True)
    favorites = db.relationship('Favorite', backref='user', lazy=True)

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class City(db.Model):
    __tablename__ = 'cities'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(96), unique=True, nullable=False)
    name = db.Column(db.String(96), nullable=False)
    display_name = db.Column(db.String(96), nullable=False)
    state = db.Column(db.String(8), default='')
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    timezone = db.Column(db.String(48), default='America/Chicago')
    hero_image = db.Column(db.String(255), default='')
    phone = db.Column(db.String(32), default='')
    monthly_phone = db.Column(db.String(32), default='')
    rates = db.Column(db.Text, default='[]')
    popular_destinations = db.Column(db.Text, default='[]')
    neighborhoods = db.Column(db.Text, default='[]')
    venues = db.Column(db.Text, default='[]')
    categories = db.Column(db.Text, default='[]')
    airports = db.Column(db.Text, default='[]')
    event_copy = db.Column(db.Text, default='')
    faqs = db.Column(db.Text, default='[]')

    def json_field(self, name):
        return json.loads(getattr(self, name) or '[]')


class Destination(db.Model):
    __tablename__ = 'destinations'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(128), unique=True, nullable=False)
    title = db.Column(db.String(128), nullable=False)
    city = db.Column(db.String(96), nullable=False)
    city_slug = db.Column(db.String(96), default='')
    state = db.Column(db.String(8), default='')
    street = db.Column(db.String(255), default='')
    postal = db.Column(db.String(16), default='')
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    featured = db.Column(db.Text, default='[]')
    rates = db.Column(db.Text, default='[]')
    partner_heading = db.Column(db.String(255), default='')
    partner_paras = db.Column(db.Text, default='[]')
    faqs = db.Column(db.Text, default='[]')
    popular = db.Column(db.Text, default='[]')

    def json_field(self, name):
        return json.loads(getattr(self, name) or '[]')


class Facility(db.Model):
    __tablename__ = 'facilities'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), default='')
    city = db.Column(db.String(96), default='')
    city_slug = db.Column(db.String(96), default='')
    state = db.Column(db.String(8), default='')
    street = db.Column(db.String(255), default='')
    postal = db.Column(db.String(16), default='')
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    operator = db.Column(db.String(255), default='')
    facility_type = db.Column(db.String(32), default='unknown')
    rating_avg = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    rating_dist = db.Column(db.Text, default='[0,0,0,0,0]')
    prompt_counts = db.Column(db.Text, default='[]')
    amenities = db.Column(db.Text, default='[]')
    restrictions = db.Column(db.Text, default='[]')
    getting_there = db.Column(db.Text, default='')
    redemption = db.Column(db.Text, default='[]')
    always_open = db.Column(db.Boolean, default=True)
    hours_text = db.Column(db.Text, default='[]')
    clearance_inches = db.Column(db.Integer)
    monthly_ok = db.Column(db.Boolean, default=False)
    cancellable = db.Column(db.Boolean, default=True)
    base_rate = db.Column(db.Float, default=0.0)
    daily_rate = db.Column(db.Float, default=0.0)
    increment_rate = db.Column(db.Float, default=0.0)
    monthly_rate = db.Column(db.Float)
    images = db.Column(db.Text, default='[]')
    airport_code = db.Column(db.String(8))
    airport_daily_rate = db.Column(db.Float)
    airport_facility_fee = db.Column(db.Float, default=0.0)
    airport_shuttle = db.Column(db.Boolean, default=False)
    airport_distance_m = db.Column(db.Float)
    parking_pass = db.Column(db.String(64), default='')

    def json_field(self, name):
        return json.loads(getattr(self, name) or '[]')

    @property
    def image_list(self):
        return self.json_field('images')

    @property
    def amenity_list(self):
        return self.json_field('amenities')

    def walk_from(self, lat, lng):
        """(seconds, meters) walking distance from a point."""
        if self.lat is None or self.lng is None or lat is None or lng is None:
            return None, None
        meters = haversine_m(lat, lng, self.lat, self.lng)
        return int(meters / WALK_SPEED_MPS), int(meters)


class Airport(db.Model):
    __tablename__ = 'airports'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False)
    title = db.Column(db.String(128), nullable=False)
    info_title = db.Column(db.String(255), default='')
    city = db.Column(db.String(96), default='')
    state = db.Column(db.String(8), default='')
    street = db.Column(db.String(255), default='')
    postal = db.Column(db.String(16), default='')
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    url_slug = db.Column(db.String(128), default='')
    faqs = db.Column(db.Text, default='[]')

    def json_field(self, name):
        return json.loads(getattr(self, name) or '[]')


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    venue_title = db.Column(db.String(128), default='')
    venue_city = db.Column(db.String(96), default='')
    venue_slug = db.Column(db.String(128), default='')
    starts = db.Column(db.String(64), default='')       # ISO local (naive)
    ends = db.Column(db.String(64), default='')
    window_starts = db.Column(db.String(64), default='')
    window_ends = db.Column(db.String(64), default='')
    description = db.Column(db.Text, default='')
    seo_url = db.Column(db.String(255), default='')


class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    email = db.Column(db.String(255), default='')
    phone = db.Column(db.String(32), default='')
    facility_id = db.Column(db.Integer, db.ForeignKey('facilities.id'), nullable=False)
    kind = db.Column(db.String(16), default='hourly')  # hourly|monthly|event|airport
    starts = db.Column(db.String(64), nullable=False)   # ISO local (naive)
    ends = db.Column(db.String(64))
    subtotal = db.Column(db.Float, default=0.0)
    service_fee = db.Column(db.Float, default=0.0)
    facility_fee = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    promo_code = db.Column(db.String(32), default='')
    status = db.Column(db.String(16), default='upcoming')  # upcoming|active|cancelled|past
    license_plate = db.Column(db.String(16), default='')
    vehicle = db.Column(db.String(64), default='')
    created_at = db.Column(db.String(64), default='')
    parking_pass = db.Column(db.String(64), default='Scan In/Out')

    facility = db.relationship('Facility', backref='reservations', lazy=True)

    @property
    def start_dt(self):
        return parse_dt(self.starts)

    @property
    def end_dt(self):
        return parse_dt(self.ends)


class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    brand = db.Column(db.String(32), default='Visa')
    last4 = db.Column(db.String(4), default='0000')
    exp_month = db.Column(db.Integer, default=12)
    exp_year = db.Column(db.Integer, default=2028)
    is_default = db.Column(db.Boolean, default=False)
    label = db.Column(db.String(64), default='')


class Favorite(db.Model):
    __tablename__ = 'favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey('facilities.id'), nullable=False)
    facility = db.relationship('Facility', backref='favorites', lazy=True)


class Faq(db.Model):
    __tablename__ = 'faqs'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(64), default='General')
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)


class Stadium(db.Model):
    __tablename__ = 'stadiums'
    id = db.Column(db.Integer, primary_key=True)
    league = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    team = db.Column(db.String(128), default='')
    city_slug = db.Column(db.String(96), default='')
    slug = db.Column(db.String(128), default='')


class StaticPage(db.Model):
    __tablename__ = 'static_pages'
    slug = db.Column(db.String(128), primary_key=True)
    sections = db.Column(db.Text, default='[]')

    def section_list(self):
        return json.loads(self.sections or '[]')


class PromoCode(db.Model):
    __tablename__ = 'promo_codes'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    pct = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text, default='')


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    facility_id = db.Column(db.Integer, db.ForeignKey('facilities.id'), nullable=False)
    rating = db.Column(db.Integer, default=5)
    review_date = db.Column(db.String(32), default='')
    duration = db.Column(db.String(48), default='')
    vehicle = db.Column(db.String(64), default='')
    tags = db.Column(db.Text, default='[]')

    facility = db.relationship('Facility', backref='reviews', lazy=True)


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), default='')
    email = db.Column(db.String(255), default='')
    topic = db.Column(db.String(128), default='')
    message = db.Column(db.Text, default='')
    created_at = db.Column(db.String(64), default='')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ------------------------------------------------------------------ helpers

def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse_dt(value):
    if not value:
        return None
    value = str(value).replace('T', ' ')[:16]
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def fmt_dt(dt):
    return dt.strftime('%Y-%m-%dT%H:%M') if dt else ''


def fmt_display_date(dt):
    if not dt:
        return ''
    return dt.strftime('%a, %b %-d, %Y')


def fmt_display_time(dt):
    if not dt:
        return ''
    hour = dt.hour % 12 or 12
    ampm = 'AM' if dt.hour < 12 else 'PM'
    return f'{hour}:{dt.minute:02d} {ampm}'


def fmt_money(value):
    return f'${value:,.2f}'


def fmt_short_dt(iso):
    dt = parse_dt(iso)
    if not dt:
        return iso or ''
    return dt.strftime('%b %-d, %-I:%M %p')


def walk_display(seconds, meters):
    if seconds is None:
        return '', ''
    if seconds < 60:
        dur = '<1 min'
    else:
        dur = f'{int(round(seconds / 60.0))} min'
    if meters < 528:
        dist = f'{int(round(meters * 3.28084))} ft'
    else:
        dist = f'{meters / 1609.34:.1f} mi'
    return dur, f'({dist})'


def review_count_display(count):
    if count >= 1000:
        v = count / 1000.0
        return f'{int(v)}K' if v >= 10 else f'{v:.1f}K'
    return str(count)


def tokenize(q):
    return [t for t in re.split(r'\W+', (q or '').lower()) if len(t) > 1]


def scored_search(query, rows, fields):
    tokens = tokenize(query)
    if not tokens:
        return rows
    scored = []
    for item in rows:
        text = ' '.join(str(getattr(item, f) or '') for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: -pair[0])
    return [item for _, item in scored]


def transient_quote(facility, start, end):
    hours = max(0.25, (end - start).total_seconds() / 3600.0)
    subtotal = facility.base_rate + facility.increment_rate * (hours - 1)
    subtotal = min(facility.daily_rate, subtotal)
    subtotal = round(max(subtotal, facility.base_rate), 2)
    fee = round(max(SERVICE_FEE_MIN, subtotal * SERVICE_FEE_RATE), 2)
    return subtotal, fee


def event_quote(facility):
    subtotal = round(facility.daily_rate * EVENT_RATE_MULT, 2)
    fee = round(subtotal * EVENT_FEE_RATE, 2)
    return subtotal, fee


def airport_quote(facility, start, end):
    hours = max(1.0, (end - start).total_seconds() / 3600.0)
    days = math.ceil(hours / 24.0)
    subtotal = round(facility.airport_daily_rate * days, 2)
    return subtotal, AIRPORT_FEE_FLAT, facility.airport_facility_fee or 0.0, days


def monthly_quote(facility):
    subtotal = facility.monthly_rate or 0.0
    fee = round(max(SERVICE_FEE_MIN, subtotal * SERVICE_FEE_RATE), 2)
    return subtotal, fee


def make_reservation_code():
    alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return 'SH-' + ''.join(secrets.choice(alphabet) for _ in range(6))


def default_window():
    start = MIRROR_TODAY.replace(hour=12, minute=0)
    return start, start + timedelta(hours=3)


def parse_window(starts=None, ends=None, default_hours=3):
    start = parse_dt(starts) if starts else None
    end = parse_dt(ends) if ends else None
    if start is None:
        start = MIRROR_TODAY.replace(hour=12, minute=0)
    if end is None:
        end = start + timedelta(hours=default_hours)
    if end <= start:
        end = start + timedelta(hours=default_hours)
    return start, end


def build_search_url(kind, **params):
    parts = [f'kind={url_quote(kind, safe="")}']
    for key, value in params.items():
        if value is None or value == '':
            continue
        parts.append(f'{key}={url_quote(str(value), safe="")}')
    query = '&'.join(parts)
    return url_for('search') + ('?' + query if query else '')


def modify_query(key, value):
    """Return the current URL with one query parameter added/replaced/removed."""
    args = request.args.to_dict(flat=False)
    if value is None:
        args.pop(key, None)
    else:
        args[key] = [str(value)]
    base = request.path
    qs = '&'.join(
        f'{k}={url_quote(v, safe="")}' for k, vs in args.items() for v in vs)
    return base + ('?' + qs if qs else '')


def facility_card(facility, walk_seconds, walk_meters, price, price_note='Subtotal',
                  tags=None, start=None, end=None, kind='hourly', event=None):
    dur, dist = walk_display(walk_seconds, walk_meters)
    book_kwargs = {'facility': facility.id, 'kind': kind}
    if start is not None:
        book_kwargs['starts'] = fmt_dt(start)
    if end is not None:
        book_kwargs['ends'] = fmt_dt(end)
    if event is not None:
        book_kwargs['event'] = event.id
    detail_kwargs = {}
    if start is not None:
        detail_kwargs['starts'] = fmt_dt(start)
    if end is not None:
        detail_kwargs['ends'] = fmt_dt(end)
    if kind == 'monthly':
        detail_kwargs['kind'] = 'monthly'
    return {
        'facility': facility,
        'price': price,
        'price_note': price_note,
        'walk': dur,
        'walk_dist': dist,
        'walk_meters': walk_meters or 0,
        'tags': tags or [],
        'book_url': url_for('purchase_hourly', **book_kwargs),
        'detail_url': url_for('facility_page', facility_id=facility.id,
                              slug=facility.slug or 'x', **detail_kwargs),
    }


def nearby_facilities(lat, lng, city_slug=None, limit=40, exclude=None):
    q = Facility.query
    if city_slug:
        q = q.filter(Facility.city_slug == city_slug)
    if exclude is not None:
        q = q.filter(Facility.id != exclude)
    rows = q.all()
    scored = []
    for f in rows:
        if f.lat is None or f.lng is None:
            continue
        d = haversine_m(lat, lng, f.lat, f.lng)
        scored.append((d, f))
    scored.sort(key=lambda pair: pair[0])
    return scored[:limit]


app.jinja_env.globals.update(
    fmt_money=fmt_money,
    fmt_short_dt=fmt_short_dt,
    walk_display=walk_display,
    fmt_display_date=fmt_display_date,
    fmt_display_time=fmt_display_time,
    review_count_display=review_count_display,
    modify_query=modify_query,
    MIRROR_TODAY=MIRROR_TODAY,
)


# ------------------------------------------------------------------- routes

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/_health')
def health():
    return {'ok': True, 'site': 'spothero'}


@app.route('/api/suggest')
def api_suggest():
    q = (request.args.get('q') or '').strip().lower()
    if len(q) < 2:
        return jsonify({'results': []})
    out = []
    for c in City.query.all():
        if q in c.name.lower():
            out.append({'type': 'city', 'label': f'{c.name}, {c.state}',
                        'url': build_search_url(kind='address',
                                                search_string=f'{c.name}, {c.state}, USA',
                                                latitude=c.lat, longitude=c.lng),
                        'name': c.name})
    for d in Destination.query.all():
        if q in d.title.lower() or q in d.city.lower():
            out.append({'type': 'destination', 'label': f'{d.title}, {d.city}',
                        'url': url_for('destination_page', city_slug=d.city_slug or 'search',
                                       slug=d.slug),
                        'name': d.title})
    for a in Airport.query.all():
        if q in a.title.lower() or q in a.code.lower() or q in a.city.lower():
            out.append({'type': 'airport', 'label': f'{a.title} ({a.code})',
                        'url': url_for('airport_by_code', code=a.code),
                        'name': a.title})
    for e in Event.query.filter(Event.starts >= fmt_dt(MIRROR_TODAY)).all():
        if q in e.title.lower() or q in e.venue_title.lower():
            out.append({'type': 'event',
                        'label': f'{e.title} — {e.venue_title}, {fmt_short_dt(e.starts)}',
                        'url': build_search_url(kind='event', id=e.id),
                        'name': e.title})
    for f in Facility.query.filter(Facility.title.ilike(f'%{q}%')).limit(8):
        out.append({'type': 'facility', 'label': f'{f.title} ({f.city})',
                    'url': url_for('facility_page', facility_id=f.id, slug=f.slug or 'x'),
                    'name': f.title})
    return jsonify({'results': out[:20]})


@app.route('/search')
def search():
    kind = request.args.get('kind', 'address')
    search_string = request.args.get('search_string', '')
    lat = request.args.get('latitude', type=float)
    lng = request.args.get('longitude', type=float)
    sort = request.args.get('sort', 'relevance')
    covered = request.args.get('covered') == '1'
    self_park = request.args.get('self_park') == '1'
    valet = request.args.get('valet') == '1'
    ev = request.args.get('ev') == '1'
    in_out = request.args.get('in_out') == '1'
    with_fees = request.args.get('fees') == '1'
    event_id = request.args.get('id', type=int)
    airport_code = request.args.get('airport')

    event = None
    airport = None
    cards = []
    window_label = ''
    start = end = None

    if kind == 'event':
        event = Event.query.get(event_id) if event_id else None
        if not event:
            abort(404)
        venue = Destination.query.filter_by(slug=event.venue_slug).first()
        lat = venue.lat if venue else lat
        lng = venue.lng if venue else lng
        start = parse_dt(event.window_starts)
        end = parse_dt(event.window_ends)
        window_label = 'Event parking window'
        for dist, f in nearby_facilities(lat, lng, limit=40):
            if dist > 3200:
                continue  # event parking is venue-local; never leak other cities
            if not f.daily_rate:
                continue
            if covered and 'Garage - Covered' not in f.amenity_list:
                continue
            if self_park and 'Self Park' not in f.amenity_list:
                continue
            if valet and 'Valet' not in f.amenity_list:
                continue
            if ev and 'EV Charging' not in f.amenity_list:
                continue
            if in_out and 'In & Out Allowed' not in f.amenity_list:
                continue
            subtotal, fee = event_quote(f)
            price = round(subtotal + fee, 2) if with_fees else subtotal
            cards.append(facility_card(f, int(dist / WALK_SPEED_MPS), int(dist),
                                       price, 'Subtotal',
                                       ['Official Parking'] if venue and f.city_slug == venue.city_slug else [],
                                       start=start, end=end, kind='event', event=event))
        if sort == 'price':
            cards.sort(key=lambda c: c['price'])
        elif sort == 'distance':
            cards.sort(key=lambda c: c['walk_meters'] if 'walk_meters' in c else 0)
        return render_template('search.html', kind=kind, event=event, cards=cards,
                               search_string=event.title, start=start, end=end,
                               window_label=window_label, sort=sort, with_fees=with_fees,
                               filters={'covered': covered, 'self_park': self_park,
                                        'valet': valet, 'ev': ev, 'in_out': in_out})

    if kind == 'monthly':
        start = parse_dt(request.args.get('monthly_start')) or MIRROR_TODAY
        window_label = 'Monthly parking'
        rows = Facility.query.filter(Facility.monthly_ok.is_(True))
        if search_string:
            first = search_string.split(',')[0].strip()
            filtered = rows.filter(Facility.city.ilike(f'%{first}%'))
            if filtered.first():
                rows = filtered
            else:
                # token fallback: queries like "downtown Chicago" name no
                # facility city verbatim — retry the individual words before
                # showing an empty result page.
                for tok in (t for t in re.split(r'[^A-Za-z]+', first)
                            if len(t) >= 4):
                    alt = rows.filter(Facility.city.ilike(f'%{tok}%'))
                    if alt.first():
                        rows = alt
                        break
                else:
                    rows = filtered
        if lat is not None and lng is not None:
            scored = []
            for f in rows.all():
                if f.lat is None:
                    continue
                d = haversine_m(lat, lng, f.lat, f.lng)
                if d > 8000:
                    continue
                scored.append((d, f))
            scored.sort(key=lambda pair: pair[0])
            for d, f in scored[:40]:
                if covered and 'Garage - Covered' not in f.amenity_list:
                    continue
                if self_park and 'Self Park' not in f.amenity_list:
                    continue
                if valet and 'Valet' not in f.amenity_list:
                    continue
                secs = int(d / WALK_SPEED_MPS)
                cards.append(facility_card(f, secs, int(d), f.monthly_rate or 0,
                                           'Subtotal', start=start, kind='monthly'))
        else:
            for f in rows.limit(40):
                cards.append(facility_card(f, None, None, f.monthly_rate or 0, 'Subtotal',
                                           start=start, kind='monthly'))
        if sort == 'price':
            cards.sort(key=lambda c: c['price'])
        return render_template('search.html', kind=kind, cards=cards,
                               search_string=search_string, start=start, end=None,
                               window_label=window_label, sort=sort,
                               with_fees=with_fees,
                               filters={'covered': covered, 'self_park': self_park,
                                        'valet': valet, 'ev': ev, 'in_out': in_out})

    if kind == 'airport' or airport_code:
        airport = Airport.query.filter_by(code=(airport_code or '').upper()).first()
        if not airport:
            abort(404)
        start, end = parse_window(request.args.get('starts'), request.args.get('ends'),
                                  default_hours=3)
        window_label = 'Airport parking'
        rows = Facility.query.filter_by(airport_code=airport.code).all()
        rows.sort(key=lambda f: (f.airport_distance_m or 1e9))
        for f in rows:
            if covered and 'Garage - Covered' not in f.amenity_list:
                continue
            if self_park and 'Self Park' not in f.amenity_list:
                continue
            subtotal, fee, fac_fee, days = airport_quote(f, start, end)
            total = round(subtotal + fee + fac_fee, 2)
            price = total if with_fees else subtotal
            cards.append(facility_card(f, None, None, price,
                                       f'Per Day (${f.airport_daily_rate:.2f})',
                                       start=start, end=end, kind='airport'))
        if sort == 'price':
            cards.sort(key=lambda c: c['price'])
        return render_template('search.html', kind='airport', airport=airport,
                               cards=cards, search_string=airport.title,
                               start=start, end=end, window_label=window_label,
                               sort=sort, with_fees=with_fees,
                               filters={'covered': covered, 'self_park': self_park,
                                        'valet': valet, 'ev': ev, 'in_out': in_out})

    # default: address / point search
    start, end = parse_window(request.args.get('starts'), request.args.get('ends'))
    window_label = 'Hourly / Daily parking'
    if lat is None or lng is None:
        # resolve the typed destination: matching destination, facility, or city
        first = (search_string or '').split(',')[0].strip()
        point = None
        if first:
            dest = (Destination.query
                    .filter(Destination.title.ilike(f'%{first}%'))
                    .order_by(Destination.title).first())
            if dest and dest.lat is not None:
                point = (dest.lat, dest.lng)
            if point is None:
                fac = Facility.query.filter(Facility.title.ilike(f'%{first}%')).first()
                if fac and fac.lat is not None:
                    point = (fac.lat, fac.lng)
            if point is None:
                city = City.query.filter(City.name.ilike(f'%{first}%')).first()
                if city:
                    point = (city.lat, city.lng)
        if point is None:
            city = City.query.filter_by(slug='chicago-parking').first()
            point = (city.lat, city.lng)
        lat, lng = point
    scored = []
    for f in Facility.query.filter(Facility.airport_code.is_(None)).all():
        if f.lat is None or f.lng is None:
            continue
        d = haversine_m(lat, lng, f.lat, f.lng)
        scored.append((d, f))
    scored.sort(key=lambda pair: pair[0])
    near = [pair for pair in scored if pair[0] <= 3200]
    if not near:
        near = scored[:20]
    for d, f in near[:40]:
        if covered and 'Garage - Covered' not in f.amenity_list:
            continue
        if self_park and 'Self Park' not in f.amenity_list:
            continue
        if valet and 'Valet' not in f.amenity_list:
            continue
        if ev and 'EV Charging' not in f.amenity_list:
            continue
        if in_out and 'In & Out Allowed' not in f.amenity_list:
            continue
        subtotal, fee = transient_quote(f, start, end)
        price = round(subtotal + fee, 2) if with_fees else subtotal
        tags = []
        if d < 200:
            tags.append('Shortest Walk')
        cards.append(facility_card(f, int(d / WALK_SPEED_MPS), int(d), price,
                                   'Subtotal', tags, start=start, end=end, kind='hourly'))
    if sort == 'price':
        cards.sort(key=lambda c: c['price'])
    return render_template('search.html', kind='address', cards=cards,
                           search_string=search_string, start=start, end=end,
                           window_label=window_label, sort=sort, with_fees=with_fees,
                           filters={'covered': covered, 'self_park': self_park,
                                    'valet': valet, 'ev': ev, 'in_out': in_out})


@app.route('/facility/<int:facility_id>')
@app.route('/facility/<int:facility_id>/<slug>')
def facility_page(facility_id, slug=None):
    facility = Facility.query.get(facility_id) or abort(404)
    start, end = parse_window(request.args.get('starts'), request.args.get('ends'))
    kind = request.args.get('kind', 'hourly')
    event = Event.query.get(request.args.get('event', type=int)) \
        if request.args.get('event', type=int) else None
    subtotal = fee = fac_fee = None
    total = None
    if facility.airport_code:
        kind = 'airport'
        subtotal, fee, fac_fee, days = airport_quote(facility, start, end)
        total = round(subtotal + fee + fac_fee, 2)
    elif event:
        # an event-context visit (from the event parking search) quotes the
        # same event window and event rate the search's Book Now does, so
        # both paths to checkout agree (price-path divergence fix)
        kind = 'event'
        start = parse_dt(event.window_starts)
        end = parse_dt(event.window_ends)
        subtotal, fee = event_quote(facility)
        total = round(subtotal + fee, 2)
    elif kind == 'monthly' and facility.monthly_ok:
        subtotal, fee = monthly_quote(facility)
        total = round(subtotal + fee, 2)
    else:
        kind = 'hourly'
        subtotal, fee = transient_quote(facility, start, end)
        total = round(subtotal + fee, 2)
    nearby = []
    if facility.lat and facility.lng:
        for d, f in nearby_facilities(facility.lat, facility.lng,
                                      exclude=facility.id, limit=12):
            if d > 3200:
                continue  # "nearby" means walkable, not merely closest
            if f.daily_rate:
                nearby.append((f, d))
    reviews = Review.query.filter_by(facility_id=facility.id).all()
    return render_template('facility.html', facility=facility, kind=kind,
                           start=start, end=end, subtotal=subtotal, fee=fee,
                           fac_fee=fac_fee, total=total, nearby=nearby,
                           reviews=reviews, event=event)


@app.route('/api/facility/<int:facility_id>/quote')
def facility_quote(facility_id):
    facility = Facility.query.get(facility_id) or abort(404)
    start, end = parse_window(request.args.get('starts'), request.args.get('ends'))
    kind = request.args.get('kind', 'hourly')
    if facility.airport_code:
        subtotal, fee, fac_fee, days = airport_quote(facility, start, end)
    elif kind == 'monthly':
        subtotal, fee = monthly_quote(facility)
        fac_fee = 0.0
    else:
        subtotal, fee = transient_quote(facility, start, end)
        fac_fee = 0.0
    return jsonify({'subtotal': subtotal, 'service_fee': fee,
                    'facility_fee': fac_fee,
                    'total': round(subtotal + fee + fac_fee, 2)})


@app.route('/purchase/hourly', methods=['GET', 'POST'])
def purchase_hourly():
    facility_id = request.values.get('facility', type=int)
    facility = Facility.query.get(facility_id) or abort(404)
    kind = request.values.get('kind', 'hourly')
    if facility.airport_code:
        kind = 'airport'
    start, end = parse_window(request.values.get('starts'), request.values.get('ends'))
    if kind == 'monthly' and facility.monthly_ok:
        # A monthly reservation covers one calendar month, including year rollover.
        from calendar import monthrange
        month = start.month % 12 + 1
        year = start.year + (start.month == 12)
        end = start.replace(year=year, month=month, day=min(start.day, monthrange(year, month)[1]))
    event_id = request.values.get('event', type=int)
    event = Event.query.get(event_id) if event_id else None
    if event:
        kind = 'event'
        start = parse_dt(event.window_starts)
        end = parse_dt(event.window_ends)

    promo = None
    discount = 0.0
    if kind == 'event':
        subtotal, fee = event_quote(facility)
        fac_fee = 0.0
    elif kind == 'airport':
        subtotal, fee, fac_fee, days = airport_quote(facility, start, end)
    elif kind == 'monthly' and facility.monthly_ok:
        subtotal, fee = monthly_quote(facility)
        fac_fee = 0.0
    else:
        kind = 'hourly'
        subtotal, fee = transient_quote(facility, start, end)
        fac_fee = 0.0

    promo_code_txt = (request.values.get('promo') or '').strip().upper()
    promo_error = None
    if promo_code_txt:
        promo = PromoCode.query.filter_by(code=promo_code_txt).first()
        if promo:
            discount = round(subtotal * promo.pct / 100.0, 2)
        else:
            promo_error = f'{promo_code_txt} is not a valid promo code.'
            promo_code_txt = ''

    total = round(subtotal + fee + fac_fee - discount, 2)

    if request.method == 'POST':
        email = (request.values.get('email') or '').strip().lower()
        phone = (request.values.get('phone') or '').strip()
        plate = (request.values.get('license_plate') or '').strip()
        vehicle = (request.values.get('vehicle') or '').strip()
        card_name = (request.values.get('creditCardName') or '').strip()
        errors = []
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errors.append('Enter a valid email address.')
        if not card_name:
            errors.append('Enter the name on your card.')
        if errors:
            return render_template('checkout.html', facility=facility, kind=kind,
                                   start=start, end=end, subtotal=subtotal, fee=fee,
                                   fac_fee=fac_fee, discount=discount, total=total,
                                   promo_code=promo_code_txt, promo_error=promo_error,
                                   event=event, errors=errors, email=email, phone=phone,
                                   plate=plate, vehicle=vehicle, card_name=card_name)
        code = make_reservation_code()
        reservation = Reservation(
            code=code, user_id=current_user.id if current_user.is_authenticated else None,
            email=email, phone=phone, facility_id=facility.id, kind=kind,
            starts=fmt_dt(start), ends=fmt_dt(end), subtotal=round(subtotal, 2),
            service_fee=round(fee, 2), facility_fee=round(fac_fee, 2),
            total=total, promo_code=promo.code if promo else '',
            license_plate=plate, vehicle=vehicle,
            created_at=fmt_dt(MIRROR_TODAY.replace(hour=10, minute=30)),
            parking_pass=facility.parking_pass or 'Scan In/Out')
        db.session.add(reservation)
        db.session.commit()
        return redirect(url_for('confirmation', code=code))

    return render_template('checkout.html', facility=facility, kind=kind,
                           start=start, end=end, subtotal=subtotal, fee=fee,
                           fac_fee=fac_fee, discount=discount, total=total,
                           promo_code=promo_code_txt, promo_error=promo_error,
                           event=event, errors=[],
                           email=current_user.email if current_user.is_authenticated else '',
                           phone=current_user.phone if current_user.is_authenticated else '',
                           plate=current_user.license_plate if current_user.is_authenticated else '',
                           vehicle=current_user.vehicle if current_user.is_authenticated else '',
                           card_name='')


@app.route('/purchase/monthly')
def purchase_monthly():
    return redirect(url_for('purchase_hourly', **{
        'facility': request.args.get('facility', type=int),
        'kind': 'monthly', 'starts': request.args.get('monthly_start'),
        'ends': request.args.get('monthly_start')}))


@app.route('/purchase/confirmation/<code>')
def confirmation(code):
    reservation = Reservation.query.filter_by(code=code).first() or abort(404)
    return render_template('confirmation.html', reservation=reservation)


@app.route('/reservation/<code>/qr.svg')
def reservation_qr(code):
    import io

    import segno
    buf = io.BytesIO()
    segno.make(f'SPOTHERO|{code}|CONFIRMED', error='m').save(buf, kind='svg', scale=6)
    return buf.getvalue(), 200, {'Content-Type': 'image/svg+xml'}


# ----------------------------------------------------------------- auth

@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    error = None
    if request.method == 'POST':
        email = (request.values.get('email') or '').strip().lower()
        password = request.values.get('password') or ''
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            nxt = request.values.get('next')
            if nxt and nxt.startswith('/'):
                return redirect(nxt)
            return redirect(url_for('account'))
        error = 'Invalid email or password.'
    return render_template('login.html', error=error)


@app.route('/auth/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    error = None
    form = {}
    if request.method == 'POST':
        form = {k: (request.values.get(k) or '').strip() for k in
                ('first_name', 'last_name', 'email', 'phone', 'password')}
        if not form['first_name'] or not form['last_name']:
            error = 'Enter your first and last name.'
        elif not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', form['email']):
            error = 'Enter a valid email address.'
        elif len(form['password']) < 8:
            error = 'Password must be at least 8 characters.'
        elif User.query.filter_by(email=form['email'].lower()).first():
            error = 'An account with this email already exists.'
        else:
            username = form['email'].split('@')[0].replace('.', '_')
            user = User(username=username, email=form['email'].lower(),
                        password_hash=bcrypt.generate_password_hash(form['password']),
                        first_name=form['first_name'], last_name=form['last_name'],
                        phone=form['phone'])
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('account'))
    return render_template('signup.html', error=error, form=form)


@app.route('/auth/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


# ---------------------------------------------------------------- account

@app.route('/account')
@login_required
def account():
    now = MIRROR_TODAY.replace(hour=12)
    reservations = Reservation.query.filter_by(user_id=current_user.id).all()
    upcoming = [r for r in reservations
                if r.status in ('upcoming', 'active')]
    past = [r for r in reservations if r.status == 'past']
    cancelled = [r for r in reservations if r.status == 'cancelled']
    return render_template('account.html', upcoming=upcoming, past=past,
                           cancelled=cancelled)


@app.route('/account/reservations/<code>')
@login_required
def reservation_detail(code):
    reservation = (Reservation.query.filter_by(code=code, user_id=current_user.id)
                   .first() or abort(404))
    return render_template('reservation_detail.html', reservation=reservation)


@app.route('/account/reservations/<code>/cancel', methods=['POST'])
@login_required
def reservation_cancel(code):
    reservation = (Reservation.query.filter_by(code=code, user_id=current_user.id)
                   .first() or abort(404))
    if reservation.status in ('upcoming', 'active'):
        reservation.status = 'cancelled'
        db.session.commit()
        flash('Your reservation has been canceled. Refunds are issued to the '
              'original payment method within 5-10 business days.')
    return redirect(url_for('reservation_detail', code=code))


@app.route('/account/reservations/<code>/extend', methods=['POST'])
@login_required
def reservation_extend(code):
    reservation = (Reservation.query.filter_by(code=code, user_id=current_user.id)
                   .first() or abort(404))
    hours = request.values.get('hours', type=int, default=1)
    facility = reservation.facility
    old_end = reservation.end_dt
    new_end = old_end + timedelta(hours=hours)
    if reservation.kind == 'event':
        flash('Event parking times are fixed to the event window and cannot be extended.')
        return redirect(url_for('reservation_detail', code=code))
    old_sub, _ = transient_quote(facility, reservation.start_dt, old_end)
    new_sub, _ = transient_quote(facility, reservation.start_dt, new_end)
    extra = round(new_sub - old_sub, 2)
    fee = round(max(SERVICE_FEE_MIN, extra * SERVICE_FEE_RATE), 2)
    reservation.ends = fmt_dt(new_end)
    reservation.subtotal = round(new_sub, 2)
    reservation.service_fee = round(fee, 2)
    reservation.total = round(new_sub + fee + (reservation.facility_fee or 0), 2)
    db.session.commit()
    flash(f'Reservation extended by {hours} hour(s). Additional charge: {fmt_money(extra + fee)}.')
    return redirect(url_for('reservation_detail', code=code))


@app.route('/account/payment-methods', methods=['GET', 'POST'])
@login_required
def payment_methods():
    if request.method == 'POST':
        action = request.values.get('action')
        if action == 'add':
            brand = (request.values.get('brand') or 'Visa').strip()
            number = re.sub(r'\D', '', request.values.get('number') or '')
            if len(number) < 13 or len(number) > 19 or not number.isdigit():
                flash('Enter a valid card number.')
            else:
                # first card becomes the default, later cards wait for an
                # explicit "Make default" (mirrors upstream account behavior)
                make_default = not PaymentMethod.query.filter_by(
                    user_id=current_user.id).first()
                if make_default:
                    PaymentMethod.query.filter_by(user_id=current_user.id).update(
                        {'is_default': False})
                pm = PaymentMethod(user_id=current_user.id, brand=brand,
                                   last4=number[-4:],
                                   exp_month=request.values.get('exp_month', type=int,
                                                                 default=12),
                                   exp_year=request.values.get('exp_year', type=int,
                                                               default=2028),
                                   is_default=make_default,
                                   label=(request.values.get('label') or '').strip())
                db.session.add(pm)
                db.session.commit()
                if make_default:
                    flash(f'{brand} ending in {number[-4:]} was added and set as '
                          'your default payment method.')
                else:
                    flash(f'{brand} ending in {number[-4:]} was added. Make it '
                          'your default payment method below.')
        elif action == 'delete':
            pm = PaymentMethod.query.get(request.values.get('id', type=int))
            if pm and pm.user_id == current_user.id:
                db.session.delete(pm)
                db.session.commit()
                flash('Payment method removed.')
        elif action == 'default':
            pm = PaymentMethod.query.get(request.values.get('id', type=int))
            if pm and pm.user_id == current_user.id:
                PaymentMethod.query.filter_by(user_id=current_user.id).update(
                    {'is_default': False})
                pm.is_default = True
                db.session.commit()
                flash(f'{pm.brand} ending in {pm.last4} is now your default.')
        return redirect(url_for('payment_methods'))
    methods = PaymentMethod.query.filter_by(user_id=current_user.id).all()
    return render_template('payment_methods.html', methods=methods)


@app.route('/account/favorites', methods=['GET', 'POST'])
@login_required
def favorites():
    if request.method == 'POST':
        facility_id = request.values.get('facility_id', type=int)
        existing = Favorite.query.filter_by(user_id=current_user.id,
                                            facility_id=facility_id).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
            flash('Removed from your saved spots.')
        elif facility_id:
            db.session.add(Favorite(user_id=current_user.id, facility_id=facility_id))
            db.session.commit()
            flash('Saved to your spots.')
        return redirect(request.values.get('next') or url_for('favorites'))
    rows = Favorite.query.filter_by(user_id=current_user.id).all()
    return render_template('favorites.html', favorites=rows)


@app.route('/account/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.first_name = (request.values.get('first_name') or '').strip()
        current_user.last_name = (request.values.get('last_name') or '').strip()
        current_user.phone = (request.values.get('phone') or '').strip()
        current_user.license_plate = (request.values.get('license_plate') or '').strip()
        current_user.vehicle = (request.values.get('vehicle') or '').strip()
        db.session.commit()
        flash('Your profile has been updated.')
        return redirect(url_for('profile'))
    return render_template('profile.html')


# ---------------------------------------------------------------- public pages

@app.route('/cities')
def cities_index():
    cities = City.query.order_by(City.name).all()
    return render_template('cities_index.html', cities=cities)


@app.route('/city/<slug>')
def city_page(slug):
    city = City.query.filter_by(slug=slug).first()
    if not city:
        # destination pages carry the upstream URL's city segment (e.g.
        # 'seattle'), while the city index uses the mirror's own slugs
        # ('seattle-parking'); accept both so breadcrumbs never 404
        city = City.query.filter_by(slug=f'{slug}-parking').first()
    if not city:
        abort(404)
    # only link venue/airport rows the mirror actually carries; the rest
    # fall back to their upstream hrefs so no reachable link 404s
    dest_slugs = {d.slug for d in Destination.query.with_entities(Destination.slug)}
    airport_codes = {a.code for a in Airport.query.with_entities(Airport.code)}
    return render_template('city_page.html', city=city, dest_slugs=dest_slugs,
                          airport_codes=airport_codes)


@app.route('/city/monthly/<slug>')
def city_monthly(slug):
    city = City.query.filter_by(slug=slug).first() or abort(404)
    rows = []
    for f in Facility.query.filter(Facility.city_slug == slug,
                                    Facility.monthly_ok.is_(True)).all():
        if f.monthly_rate:
            rows.append((f, f.monthly_rate))
    rows.sort(key=lambda pair: pair[1])
    return render_template('city_monthly.html', city=city, featured=rows[:5])


@app.route('/destination/<city_slug>/<slug>')
def destination_page(city_slug, slug):
    dest = Destination.query.filter_by(slug=slug).first() or abort(404)
    featured = []
    for row in dest.json_field('featured'):
        f = Facility.query.get(int(row['facility_id']))
        if f:
            featured.append({'facility': f, 'row': row})
    events = Event.query.filter(Event.venue_slug == dest.slug).order_by(Event.starts).all()
    events = [e for e in events if (parse_dt(e.starts) or MIRROR_TODAY) >= MIRROR_TODAY][:10]
    # resolve the crumb city by name (destinations carry the upstream URL's
    # city segment, city pages use the mirror's own slugs)
    city = City.query.filter_by(name=dest.city).first()
    dest_slugs = {d.slug for d in Destination.query.with_entities(Destination.slug)}
    return render_template('destination.html', dest=dest, featured=featured,
                           events=events, city_slug=(city.slug if city else dest.city_slug),
                           dest_slugs=dest_slugs)


@app.route('/airport/<path:rest>')
def airport_page(rest):
    parts = [p for p in rest.rstrip('/').split('/') if p]
    airport = None
    # accept both upstream path forms: /airport/chicago/ord-parking and the
    # canonical /airport/chicago-ord-parking (any segment may carry the code)
    for seg in reversed(parts):
        candidates = [seg.upper()]
        if seg.endswith('-parking'):
            candidates.insert(0, seg[:-8].upper())
            candidates.append(seg[:-8].split('-')[-1].upper())
        for code in candidates:
            airport = Airport.query.filter_by(code=code).first()
            if airport:
                break
        if airport:
            break
    if not airport:
        abort(404)
    spots = (Facility.query.filter_by(airport_code=airport.code).all())
    spots.sort(key=lambda f: (f.airport_distance_m or 1e9))
    return render_template('airport.html', airport=airport, spots=spots)


@app.route('/airport-code/<code>')
def airport_by_code(code):
    airport = Airport.query.filter_by(code=code.upper()).first() or abort(404)
    return redirect(url_for('airport_page', rest=airport.url_slug or
                            f"{airport.city.lower().replace(' ', '-')}/{airport.code.lower()}-parking"))


@app.route('/parking/airport-parking')
def airports_index():
    airports = Airport.query.order_by(Airport.code).all()
    return render_template('airports_index.html', airports=airports)


@app.route('/parking/stadium-parking')
def stadium_list():
    leagues = []
    by_league = {}
    for s in Stadium.query.order_by(Stadium.id).all():
        by_league.setdefault(s.league, []).append(s)
    for league, rows in by_league.items():
        leagues.append({'league': league, 'stadiums': rows})
    # only the mirrored destinations get an internal Book Now; the rest keep
    # their upstream spothero.com href so no row on this page 404s
    dest_slugs = {d.slug for d in Destination.query.with_entities(Destination.slug)}
    return render_template('stadium_list.html', stadiums=leagues,
                           dest_slugs=dest_slugs)


@app.route('/parking/monthly-parking')
def monthly_landing():
    cities = City.query.order_by(City.name).all()
    return render_template('monthly_landing.html', cities=cities)


@app.route('/faq')
def faq_page():
    faqs = Faq.query.order_by(Faq.id).all()
    categories = []
    seen = set()
    for f in faqs:
        if f.category not in seen:
            seen.add(f.category)
            categories.append(f.category)
    return render_template('faq.html', faqs=faqs, categories=categories)


STATIC_PAGES = {
    'about': 'static_page.html',
    'about/parking-guarantee': 'static_page.html',
    'about/promo-code': 'static_page.html',
    'contact': 'static_page.html',
    'press': 'static_page.html',
    'careers': 'static_page.html',
    'legal/terms-of-use': 'static_page.html',
    'legal/privacy-policy': 'static_page.html',
    'get-spothero-app': 'static_page.html',
    'solutions/commuter-benefits': 'static_page.html',
    'business': 'static_page.html',
    'sell-parking/operators': 'static_page.html',
    'sell-parking/property-managers': 'static_page.html',
    'sell-parking/independent-sellers': 'static_page.html',
    'sell-parking/airport-parking': 'static_page.html',
    'sell-parking/event-parking-partnerships': 'static_page.html',
}


@app.route('/<path:page_slug>')
def static_page(page_slug):
    template = STATIC_PAGES.get(page_slug.rstrip('/'))
    if not template:
        abort(404)
    if template == 'static_page.html':
        page = StaticPage.query.get(page_slug.rstrip('/'))
        sections = page.section_list() if page else []
        title = (sections[0]['text'] if sections and sections[0]['tag'] == 'h1'
                 else page_slug.replace('-', ' ').title())
        return render_template(template, sections=sections, title=title)
    return render_template(template)


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


# ---------------------------------------------------------------- bootstrap

def seed_database():
    if Facility.query.count() > 0:
        return
    from seed_data import run_seed
    run_seed(db, City, Destination, Facility, Airport, Event, Faq, PromoCode,
             Review, Stadium, StaticPage)


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    from seed_data import run_seed_users
    run_seed_users(db, User, Reservation, PaymentMethod, Favorite, Facility,
                   bcrypt, PromoCode)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
