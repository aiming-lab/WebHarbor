#!/usr/bin/env python3
"""TourRadar mirror — Flask application.

Mirrors https://www.tourradar.com/: multi-day tour marketplace with
destination/style/operator/place landing pages, scored search, tour detail
pages with day-by-day itineraries, traveler reviews, Q&A, dates & prices
with departures, a seven-step booking flow (travelers, room selection,
traveler details, travel insurance, promo codes, payment schedule, card
payment), wishlists, accounts with Tour Management, deals pages, traveler
moments and platform reviews.

Data comes from the tracked source_data_*.json snapshots captured from
tourradar.com on 2026-09-27; the SQLite seed is
materialized deterministically at image build time.
"""
import json
import math
import os
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
app.config["SECRET_KEY"] = os.environ.get("TOURRADAR_SECRET_KEY") or "webharbor-tourradar-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'TOURRADAR_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'tourradar.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your account.'
csrf = CSRFProtect(app)

# The mirror is a snapshot of the upstream site taken on 2026-09-27.
MIRROR_TODAY = date(2026, 9, 27)
MIRROR_DATE = datetime(2026, 9, 27, 12, 0, 0)
# bcrypt hash of 'TestPass123!' — frozen so the seed DB is byte-reproducible.
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')
CARD_FEE_PCT = 2.0
DEPOSIT_PCT = 10
STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
              'or', 'is', 'it', 'by', 'with', 'tour', 'tours', 'trip',
              'trips', 'travel', 'day', 'days'}
STYLE_ORDER = ['City & Culture', 'Ancient Wonders', 'Nature & Wildlife',
               'Safari', 'Hiking & Trekking', 'Adventure & Adrenaline',
               'River Cruise', 'Bicycle', 'Northern Lights',
               'Festival & Events', 'Sailing', 'Wellness & Retreats',
               'Food & Wine', 'Coach / Bus', 'Train / Rail', 'Beach',
               'Family', 'Private', 'In-Depth Cultural', 'Polar',
               'Overland Truck', 'Road Trip & Self-Drive']
DURATION_BANDS = [('1-3', 1, 3), ('4-6', 4, 6), ('7-10', 7, 10),
                  ('11-14', 11, 14), ('15-20', 15, 20), ('21+', 21, 999)]


# ------------------------------------------------------------------ models --

class Operator(db.Model):
    __tablename__ = 'operators'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    name = db.Column(db.String(160), nullable=False)
    badge = db.Column(db.String(40))
    rating = db.Column(db.Float, nullable=False, default=0.0)
    reviews_count = db.Column(db.Integer, nullable=False, default=0)
    hq = db.Column(db.String(200))
    response_rate = db.Column(db.String(20))
    response_time = db.Column(db.String(60))
    age_min = db.Column(db.Integer)
    age_max = db.Column(db.Integer)
    about = db.Column(db.Text)
    awards = db.Column(db.Text)          # JSON list of strings
    logo = db.Column(db.String(200))

    @property
    def awards_list(self):
        return json.loads(self.awards or '[]')

    @property
    def tours(self):
        return Tour.query.filter_by(operator_id=self.id).order_by(
            Tour.review_count.desc()).all()


class Destination(db.Model):
    __tablename__ = 'destinations'
    __table_args__ = (db.UniqueConstraint('kind', 'slug', name='uq_dest_kind_slug'),)
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    kind = db.Column(db.String(20), nullable=False)   # d/f/b/v/i/deal/s
    group_name = db.Column(db.String(80))             # Europe, Asia, ...
    parent_slug = db.Column(db.String(120))
    hero = db.Column(db.String(200))
    description = db.Column(db.Text)
    sections = db.Column(db.Text)                     # JSON {heading: body}
    quick_filters = db.Column(db.Text)               # JSON list of chips

    @property
    def srp_path(self):
        prefix = {'d': 'd', 'f': 'f', 'b': 'b', 'v': 'v', 'i': 'i',
                  'deal': 'deals', 's': 's'}[self.kind]
        if self.kind in ('deal', 's'):
            return f"/{prefix}/{self.slug}"
        return f"/srp/{prefix}-{self.slug}"

    @property
    def sections_dict(self):
        return json.loads(self.sections or '{}')

    @property
    def quick_filters_list(self):
        return json.loads(self.quick_filters or '[]')

    def tours_query(self):
        q = Tour.query
        if self.kind in ('d', 'b', 'v', 'i', 'deal'):
            q = q.filter(Tour.dest_slugs.contains(f'"{self.slug}"'))
        elif self.kind == 'f':
            q = q.filter_by(style=self.name)
        elif self.kind == 's':
            q = q.filter(Tour.group_type == 'Group Tour')
        return q.order_by(Tour.review_count.desc())


class Tour(db.Model):
    __tablename__ = 'tours'
    id = db.Column(db.Integer, primary_key=True)      # real upstream tour id
    name = db.Column(db.String(300), nullable=False)
    operator_id = db.Column(db.Integer, db.ForeignKey('operators.id'),
                            nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    start_city = db.Column(db.String(120))
    end_city = db.Column(db.String(120))
    start_end_note = db.Column(db.String(200))
    rating = db.Column(db.Float, nullable=False, default=0.0)
    review_count = db.Column(db.Integer, nullable=False, default=0)
    subratings = db.Column(db.Text)                    # JSON dict
    price_from = db.Column(db.Integer)                 # crossed-out "From" USD
    price_current = db.Column(db.Integer)              # current per-person USD
    discount_pct = db.Column(db.Integer)
    price_basis = db.Column(db.String(80))
    style = db.Column(db.String(60))
    attributes = db.Column(db.Text)                    # JSON [{name, tip}]
    group_min = db.Column(db.Integer)
    group_max = db.Column(db.Integer)
    min_age = db.Column(db.Integer)
    max_age = db.Column(db.Integer)
    guided_language = db.Column(db.String(40))
    group_type = db.Column(db.String(40))
    guide_type = db.Column(db.String(40))
    physical = db.Column(db.String(40))
    instant_confirm = db.Column(db.Boolean, default=False)
    intro = db.Column(db.Text)
    summary = db.Column(db.Text)                      # card review quote
    summary_author = db.Column(db.String(120))
    cities = db.Column(db.Text)                       # JSON list
    countries = db.Column(db.Text)                     # JSON list
    dest_slugs = db.Column(db.Text)                    # JSON list of slugs
    days = db.Column(db.Text)                          # JSON itinerary
    included = db.Column(db.Text)                      # JSON {cat: [items]}
    not_included = db.Column(db.Text)                  # JSON {cat: [items]}
    good_to_know = db.Column(db.Text)                  # JSON dict
    videos = db.Column(db.Text)                        # JSON list
    similar_ids = db.Column(db.Text)                   # JSON list of ids
    hero = db.Column(db.String(200))                   # card image path
    gallery = db.Column(db.Text)                       # JSON list of gallery image paths
    best_months = db.Column(db.Text)                   # JSON {month: price}
    code = db.Column(db.String(30))                    # operator tour code

    operator = db.relationship('Operator', backref='tour_list')

    @property
    def operator_name(self):
        return self.operator.name if self.operator else ''

    @property
    def style_tag(self):
        return self.style

    @property
    def review_plural(self):
        return 'review' if self.review_count == 1 else 'reviews'

    @property
    def duration_label(self):
        return f"{self.duration_days} day" + ('s' if self.duration_days != 1 else '')

    @property
    def age_label(self):
        if self.min_age and self.max_age:
            return f"Ages {self.min_age}-{self.max_age}"
        if self.min_age:
            return f"{self.min_age}+"
        return "All Ages Welcome"

    @property
    def cities_list(self):
        return json.loads(self.cities or '[]')

    @property
    def countries_list(self):
        return json.loads(self.countries or '[]')

    @property
    def days_list(self):
        return json.loads(self.days or '[]')

    @property
    def dest_slugs_list(self):
        return json.loads(self.dest_slugs or '[]')

    @property
    def attributes_list(self):
        return json.loads(self.attributes or '[]')

    @property
    def subratings_dict(self):
        return json.loads(self.subratings or '{}')

    @property
    def included_dict(self):
        return json.loads(self.included or '{}')

    @property
    def not_included_dict(self):
        return json.loads(self.not_included or '{}')

    @property
    def gtk_dict(self):
        return json.loads(self.good_to_know or '{}')

    @property
    def videos_list(self):
        return json.loads(self.videos or '[]')

    @property
    def similar(self):
        ids = json.loads(self.similar_ids or '[]')
        out = []
        for tid in ids:
            t = Tour.query.get(tid)
            if t:
                out.append(t)
        return out

    @property
    def departures(self):
        return Departure.query.filter_by(tour_id=self.id).order_by(
            Departure.start_date).all()

    @property
    def next_departure(self):
        for dep in self.departures:
            if dep.status == 'available':
                return dep
        return None

    @property
    def current_price(self):
        if self.price_current:
            return self.price_current
        return self.price_from

    @property
    def hero_url(self):
        return f"/static/images/{self.hero}" if self.hero else None

    @property
    def gallery_list(self):
        return json.loads(self.gallery or '[]')

    @property
    def gallery_main(self):
        return self.gallery_list[0] if self.gallery_list else None

    @property
    def gallery_2(self):
        return self.gallery_list[1] if len(self.gallery_list) > 1 else None

    @property
    def gallery_3(self):
        return self.gallery_list[2] if len(self.gallery_list) > 2 else None


class Departure(db.Model):
    __tablename__ = 'departures'
    id = db.Column(db.Integer, primary_key=True)
    tour_id = db.Column(db.Integer, db.ForeignKey('tours.id'), nullable=False)
    start_date = db.Column(db.String(10), nullable=False)   # ISO
    end_date = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='available')
    price = db.Column(db.Integer, nullable=False)
    was_price = db.Column(db.Integer)
    discount_pct = db.Column(db.Integer)
    guaranteed = db.Column(db.Boolean, default=False)
    instant = db.Column(db.Boolean, default=False)
    language = db.Column(db.String(40))
    basis = db.Column(db.String(80))
    spaces = db.Column(db.Integer)

    tour = db.relationship('Tour', backref='departure_list')

    @property
    def start_label(self):
        return format_date_label(self.start_date)

    @property
    def end_label(self):
        return format_date_label(self.end_date)

    @property
    def start_weekday(self):
        return weekday_name(self.start_date)

    @property
    def end_weekday(self):
        return weekday_name(self.end_date)


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    tour_id = db.Column(db.Integer, db.ForeignKey('tours.id'), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    initials = db.Column(db.String(4))
    rating = db.Column(db.Float, nullable=False)
    month = db.Column(db.String(40))           # review month, e.g. September 2026
    traveled_month = db.Column(db.String(40))
    title = db.Column(db.Text)
    body = db.Column(db.Text)
    guide_name = db.Column(db.String(120))
    reply = db.Column(db.Text)
    reply_by = db.Column(db.String(120))
    photos = db.Column(db.Text)                # JSON list of paths
    avatar = db.Column(db.String(200))

    tour = db.relationship('Tour', backref='review_list')

    @property
    def photos_list(self):
        return json.loads(self.photos or '[]')


class TourQA(db.Model):
    __tablename__ = 'tour_qa'
    id = db.Column(db.Integer, primary_key=True)
    tour_id = db.Column(db.Integer, db.ForeignKey('tours.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    asker = db.Column(db.String(120))
    asked_date = db.Column(db.String(60))
    tags = db.Column(db.Text)                  # JSON list
    answer = db.Column(db.Text)
    answer_by = db.Column(db.String(160))
    answer_date = db.Column(db.String(60))

    tour = db.relationship('Tour', backref='qa_list')

    @property
    def tag_list(self):
        return json.loads(self.tags or '[]')



class Moment(db.Model):
    __tablename__ = 'moments'
    id = db.Column(db.Integer, primary_key=True)
    tour_id = db.Column(db.Integer)
    tour_name = db.Column(db.String(300))
    author = db.Column(db.String(120))
    avatar = db.Column(db.String(200))
    image = db.Column(db.String(200))
    caption = db.Column(db.Text)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    nationality = db.Column(db.String(80))
    phone = db.Column(db.String(40))

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)


class WishlistItem(db.Model):
    __tablename__ = 'wishlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tour_id = db.Column(db.Integer, db.ForeignKey('tours.id'), nullable=False)
    created_at = db.Column(db.String(10), nullable=False)

    user = db.relationship('User', backref='wishlist_items')
    tour = db.relationship('Tour', backref='wishlist_refs')


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tour_id = db.Column(db.Integer, db.ForeignKey('tours.id'), nullable=False)
    departure_date = db.Column(db.String(10), nullable=False)
    travelers = db.Column(db.Text)          # JSON [{title, name, dob, ...}]
    room_type = db.Column(db.String(80))
    room_count = db.Column(db.Integer, default=1)
    insurance = db.Column(db.String(40))
    promo_code = db.Column(db.String(40))
    payment_schedule = db.Column(db.String(40))
    total = db.Column(db.Float, nullable=False)
    due_today = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='confirmed')
    created_at = db.Column(db.String(10), nullable=False)
    lead_email = db.Column(db.String(160))
    lead_phone = db.Column(db.String(40))

    user = db.relationship('User', backref='booking_list')
    tour = db.relationship('Tour', backref='booking_refs')

    @property
    def travelers_list(self):
        return json.loads(self.travelers or '[]')

    @property
    def departure_label(self):
        return format_date_label(self.departure_date)


class PlatformReview(db.Model):
    __tablename__ = 'platform_reviews'
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(120), nullable=False)
    initials = db.Column(db.String(4))
    rating = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(60))
    body = db.Column(db.Text)
    source = db.Column(db.String(40), default='Trustpilot')
    tour_name = db.Column(db.String(300))


class PromoCode(db.Model):
    __tablename__ = 'promo_codes'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    kind = db.Column(db.String(10), nullable=False)    # pct | amount
    value = db.Column(db.Float, nullable=False)
    min_total = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    label = db.Column(db.String(160))


# ------------------------------------------------------------- date helpers --

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December']
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
            'Saturday', 'Sunday']


def parse_iso(value):
    y, m, d = (int(x) for x in value.split('-'))
    return date(y, m, d)


def format_date_label(value):
    d = parse_iso(value)
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def weekday_name(value):
    return WEEKDAYS[parse_iso(value).weekday()]


def money(value):
    return f"US${value:,.0f}"


def money2(value):
    return f"US${value:,.2f}"


# ------------------------------------------------------------ search helper --

def tokenize(query):
    return [t.lower() for t in re.split(r'\W+', query or '')
            if t.lower() not in STOP_WORDS and len(t) > 1]


def scored_search(query, tours, fields=('name', 'intro', 'countries')):
    tokens = tokenize(query)
    if not tokens:
        return list(tours)
    results = []
    for t in tours:
        text = ' '.join(
            ' '.join(json.loads(getattr(t, f) or '[]'))
            if f in ('countries', 'cities') else (getattr(t, f) or '')
            for f in fields).lower()
        if getattr(t, 'style', None):
            text += ' ' + t.style.lower()
        text += ' ' + (t.operator_name or '').lower()
        score = sum(1 for tok in tokens if tok in text)
        if score:
            results.append((score, t))
    results.sort(key=lambda pair: (-pair[0], -pair[1].review_count or 0))
    return [t for _, t in results]


# --------------------------------------------------------- template context --

def _footer_data():
    dests = Destination.query.filter_by(kind='d').order_by(
        Destination.name).all()
    styles = Destination.query.filter_by(kind='f').order_by(
        Destination.name).all()
    ops = Operator.query.order_by(Operator.reviews_count.desc()).limit(6).all()
    return dests, styles, ops


@app.template_filter('slugify')
def _tpl_slugify(value):
    return re.sub(r"[-\s]+", '-', re.sub(r"[^\w\s-]", '', (value or '').lower())).strip('-')


@app.context_processor
def inject_globals():
    dests, styles, ops = _footer_data()
    return {
        'MIRROR_TODAY': MIRROR_TODAY,
        'money': money,
        'money2': money2,
        'footer_dests': dests,
        'footer_styles': styles,
        'footer_ops': ops,
    }


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------- utilities --

def _safe_int(name, default=None, lo=None, hi=None):
    raw = request.values.get(name)
    if raw is None or raw == '':
        return default
    try:
        v = int(raw)
    except ValueError:
        return default
    if lo is not None and v < lo:
        return default
    if hi is not None and v > hi:
        return default
    return v


def _rating_of(tour):
    return tour.rating or 0


def _apply_filters(query, args):
    """Shared SERP filtering; mutates via .filter chains."""
    price_min = _safe_int('price_min')
    price_max = _safe_int('price_max')
    if price_min is not None:
        query = query.filter(Tour.price_current >= price_min)
    if price_max is not None:
        query = query.filter(Tour.price_current <= price_max)
    dur = args.get('duration')
    if dur:
        for key, lo, hi in DURATION_BANDS:
            if key == dur:
                query = query.filter(Tour.duration_days >= lo,
                                     Tour.duration_days <= hi)
                break
    style = args.get('style')
    if style:
        query = query.filter(Tour.style == style)
    operator = args.get('operator')
    if operator:
        op = Operator.query.filter_by(slug=operator).first()
        if op:
            query = query.filter(Tour.operator_id == op.id)
    guide_type = args.get('guide_type')
    if guide_type:
        query = query.filter(Tour.guide_type == guide_type)
    group_type = args.get('group_type')
    if group_type:
        query = query.filter(Tour.group_type == group_type)
    physical = args.get('physical')
    if physical:
        query = query.filter(Tour.physical == physical)
    city = args.get('city')
    if city:
        query = query.filter(Tour.cities.contains(f'"{city}"'))
    start_city = args.get('start_city')
    if start_city:
        query = query.filter(Tour.start_city == start_city)
    end_city = args.get('end_city')
    if end_city:
        query = query.filter(Tour.end_city == end_city)
    if args.get('instant') == '1':
        query = query.filter(Tour.instant_confirm.is_(True))
    rating_min = _safe_int('rating_min')
    if rating_min is not None:
        query = query.filter(Tour.rating >= rating_min)
    age = args.get('age')
    if age == '18-35':
        query = query.filter(db.or_(Tour.min_age.is_(None), Tour.min_age <= 18))
    elif age == '36-59':
        query = query.filter(db.or_(Tour.min_age.is_(None), Tour.min_age <= 36))
    elif age == '60+':
        query = query.filter(db.or_(Tour.min_age.is_(None), Tour.min_age <= 60))
    elif age == 'family':
        query = query.filter(db.or_(Tour.min_age.is_(None), Tour.min_age <= 5))
    return query


def _sorted(q, *criteria):
    # order_by(None) clears the base ordering (review_count desc) first so the
    # requested sort actually wins.
    return q.order_by(None).order_by(*criteria)


SORTS = {
    'recommended': lambda q: _sorted(q, (Tour.review_count * (Tour.rating or 0)).desc()),
    'price_asc': lambda q: _sorted(q, Tour.price_current.asc()),
    'price_desc': lambda q: _sorted(q, Tour.price_current.desc()),
    'duration_asc': lambda q: _sorted(q, Tour.duration_days.asc()),
    'duration_desc': lambda q: _sorted(q, Tour.duration_days.desc()),
    'rating': lambda q: _sorted(q, Tour.rating.desc()),
    'reviews': lambda q: _sorted(q, Tour.review_count.desc()),
}


def _serp_response(tours_base, dest, args, title, description):
    filtered = _apply_filters(tours_base, args)
    sort = args.get('sort', 'recommended')
    filtered = SORTS.get(sort, SORTS['recommended'])(filtered)
    all_tours = filtered.all()
    page = _safe_int('page', 1, lo=1) or 1
    per_page = 12
    total = len(all_tours)
    pages = max(1, math.ceil(total / per_page))
    page = min(page, pages)
    tours = all_tours[(page - 1) * per_page: page * per_page]

    # filter facets computed from the unfiltered base for stable counts
    base_all = tours_base.all()
    cities = {}
    for t in base_all:
        for c in t.cities_list:
            cities[c] = cities.get(c, 0) + 1
    cities = sorted(cities.items(), key=lambda kv: -kv[1])[:12]
    start_cities = {}
    for t in base_all:
        if t.start_city:
            start_cities[t.start_city] = start_cities.get(t.start_city, 0) + 1
    start_cities = sorted(start_cities.items(), key=lambda kv: -kv[1])[:10]
    end_cities = {}
    for t in base_all:
        if t.end_city:
            end_cities[t.end_city] = end_cities.get(t.end_city, 0) + 1
    end_cities = sorted(end_cities.items(), key=lambda kv: -kv[1])[:10]
    styles = {}
    for t in base_all:
        if t.style:
            styles[t.style] = styles.get(t.style, 0) + 1
    operators = {}
    for t in base_all:
        operators[t.operator_name] = operators.get(t.operator_name, 0) + 1
    operators = sorted(operators.items(), key=lambda kv: -kv[1])[:10]
    styles = sorted(styles.items(), key=lambda kv: (-STYLE_ORDER.index(kv[0]) if kv[0] in STYLE_ORDER else -999, -kv[1]))

    def _qs(**overrides):
        base = {k: v for k, v in args.items() if v}
        base.update(overrides)
        return '?' + '&'.join(f"{k}={v}" for k, v in base.items()
                              if v) if base else ''

    return render_template(
        'serp.html', dest=dest, tours=tours, total=total, page=page,
        pages=pages, sort=sort, args=args, title=title,
        description=description, cities=cities, styles=styles,
        operators=operators, start_cities=start_cities,
        end_cities=end_cities, qs=_qs,
        duration_bands=DURATION_BANDS, style_order=STYLE_ORDER)


# ------------------------------------------------------------------- routes --

@app.route('/_health')
def health():
    try:
        n_tours = Tour.query.count()
        n_deps = Departure.query.count()
        ok = n_tours > 50 and n_deps > 100
        return {'ok': bool(ok), 'site': 'tourradar',
                'tours': n_tours, 'departures': n_deps}
    except Exception:
        return {'ok': False, 'site': 'tourradar'}, 500


@app.route('/')
def home():
    deals = Tour.query.filter(Tour.discount_pct > 0).order_by(
        (Tour.discount_pct * (Tour.review_count or 0)).desc()).limit(6).all()
    moments = Moment.query.order_by(Moment.id).limit(12).all()
    operators = Operator.query.order_by(Operator.reviews_count.desc()).limit(9).all()
    regions = Destination.query.filter_by(kind='d').order_by(
        Destination.group_name, Destination.name).all()
    picks = Tour.query.order_by((Tour.rating * Tour.review_count).desc()).limit(8).all()
    # slug sets used by the Popular Destinations chips so only links for
    # group/deal pages that actually exist are emitted (no dead 404 links)
    group_dest_slugs = {d.slug for d in regions}
    deal_slugs = {d.slug for d in Destination.query.filter_by(kind='deal').all()}
    return render_template('index.html', deals=deals, moments=moments,
                           operators=operators, regions=regions, picks=picks,
                           group_dest_slugs=group_dest_slugs,
                           deal_slugs=deal_slugs)


@app.route('/api/suggest')
def api_suggest():
    q = (request.args.get('q') or '').strip().lower()
    out = []
    if q:
        for d in Destination.query.filter(
                Destination.name.ilike(f'%{q}%')).order_by(
                Destination.kind).limit(8):
            out.append({'label': d.name, 'href': d.srp_path,
                        'kind': d.kind})
        for t in Tour.query.filter(Tour.name.ilike(f'%{q}%')).limit(5):
            out.append({'label': t.name, 'href': f'/t/{t.id}', 'kind': 'tour'})
    return jsonify(out)


@app.route('/search')
def search():
    q = (request.args.get('q') or '').strip()
    if not q:
        return render_template('search_results.html', q='', tours=[],
                                dests=[], operators=[], total=0)
    tours = scored_search(q, Tour.query.all())
    dests = [d for d in Destination.query.all()
             if all(tok in d.name.lower() for tok in tokenize(q))]
    ops = [o for o in Operator.query.all()
           if all(tok in o.name.lower() for tok in tokenize(q))]
    return render_template('search_results.html', q=q, tours=tours[:24],
                           dests=dests[:8], operators=ops[:6],
                           total=len(tours))


@app.route('/srp/<path:rest>')
def serp(rest):
    kind, _, slug = rest.partition('-')
    if kind not in ('d', 'f', 'b', 'v', 'i') or not slug:
        abort(404)
    dest = Destination.query.filter_by(slug=slug, kind=kind).first()
    if not dest:
        abort(404)
    base = dest.tours_query()
    return _serp_response(
        base, dest, request.args,
        f"{dest.name} Tours & Trips", dest.description or '')


@app.route('/d/<slug>')
def destination_landing(slug):
    dest = Destination.query.filter_by(slug=slug, kind='d').first()
    if not dest:
        abort(404)
    tours = dest.tours_query().limit(5).all()
    total = dest.tours_query().count()
    nearby = Destination.query.filter_by(parent_slug=slug).limit(8).all()
    experts = Operator.query.order_by(Operator.reviews_count.desc()).limit(3).all()
    return render_template('destination.html', dest=dest, tours=tours,
                           total=total, nearby=nearby, experts=experts)


@app.route('/f/<slug>')
def style_landing(slug):
    dest = Destination.query.filter_by(slug=slug, kind='f').first()
    if not dest:
        abort(404)
    tours = dest.tours_query().limit(5).all()
    total = dest.tours_query().count()
    return render_template('style_landing.html', dest=dest, tours=tours,
                           total=total)


@app.route('/b/<slug>')
def region_landing(slug):
    dest = Destination.query.filter_by(slug=slug, kind='b').first()
    if not dest:
        abort(404)
    tours = dest.tours_query().limit(5).all()
    total = dest.tours_query().count()
    children = Destination.query.filter_by(parent_slug=slug).all()
    return render_template('region_landing.html', dest=dest, tours=tours,
                           total=total, children=children)


@app.route('/v/<slug>')
def place_landing(slug):
    dest = Destination.query.filter_by(slug=slug, kind='v').first()
    if not dest:
        abort(404)
    tours = dest.tours_query().limit(5).all()
    total = dest.tours_query().count()
    return render_template('place_landing.html', dest=dest, tours=tours,
                           total=total)


@app.route('/i/<slug>')
def collection_landing(slug):
    dest = Destination.query.filter_by(slug=slug, kind='i').first()
    if not dest:
        abort(404)
    tours = dest.tours_query().limit(5).all()
    total = dest.tours_query().count()
    return render_template('collection_landing.html', dest=dest, tours=tours,
                           total=total)


@app.route('/deals/<slug>')
def deals_landing(slug):
    dest = Destination.query.filter_by(slug=slug, kind='deal').first()
    if not dest:
        abort(404)
    base = dest.tours_query().filter(Tour.discount_pct > 0)
    return _serp_response(base, dest, request.args,
                          f"{dest.name} Deals & Last Minute Specials",
                          dest.description or '')


@app.route('/s/<slug>')
def audience_landing(slug):
    dest = Destination.query.filter_by(slug=slug, kind='s').first()
    if not dest:
        abort(404)
    tours = dest.tours_query().limit(8).all()
    total = dest.tours_query().count()
    return render_template('audience_landing.html', dest=dest, tours=tours,
                           total=total)


@app.route('/sales/<slug>')
def sales_landing(slug):
    dest = Destination.query.filter_by(slug=slug, kind='deal').first()
    if not dest:
        abort(404)
    tours = Tour.query.filter(Tour.discount_pct >= 20).order_by(
        Tour.discount_pct.desc()).limit(12).all()
    return render_template('sale.html', dest=dest, tours=tours)


@app.route('/t/<int:tour_id>')
def tour_detail(tour_id):
    tour = Tour.query.get_or_404(tour_id)
    deps = tour.departures
    # seed rows are inserted in upstream display order (newest first), so
    # ascending id == newest first, matching the live site's review list
    reviews = Review.query.filter_by(tour_id=tour.id).order_by(
        Review.id.asc()).limit(8).all()
    all_reviews = Review.query.filter_by(tour_id=tour.id).count()
    qa = TourQA.query.filter_by(tour_id=tour.id).order_by(TourQA.id).limit(4).all()
    moments = Moment.query.filter_by(tour_id=tour.id).limit(6).all()
    similar = tour.similar[:6] or Tour.query.filter(
        Tour.id != tour.id).order_by(Tour.review_count.desc()).limit(6).all()
    in_wishlist = False
    if current_user.is_authenticated:
        in_wishlist = WishlistItem.query.filter_by(
            user_id=current_user.id, tour_id=tour.id).first() is not None
    return render_template('tour_detail.html', tour=tour, deps=deps,
                           reviews=reviews, all_reviews=all_reviews, qa=qa,
                           moments=moments, similar=similar,
                           in_wishlist=in_wishlist)


@app.route('/t/<int:tour_id>/reviews')
def tour_reviews(tour_id):
    tour = Tour.query.get_or_404(tour_id)
    sort = request.args.get('sort', 'recent')
    q = Review.query.filter_by(tour_id=tour.id)
    if sort == 'rating':
        reviews = q.order_by(Review.rating.desc()).all()
    elif sort == 'rating_asc':
        reviews = q.order_by(Review.rating.asc()).all()
    else:
        # "Most Recent": seed rows are inserted newest-first, so ascending
        # id renders the newest review first, matching the upstream tab
        reviews = q.order_by(Review.id.asc()).all()
    booking_done = False
    if current_user.is_authenticated:
        booking_done = Booking.query.filter_by(
            user_id=current_user.id, tour_id=tour.id,
            status='completed').first() is not None
    return render_template('tour_reviews.html', tour=tour, reviews=reviews,
                           sort=sort, booking_done=booking_done)


@app.route('/o/<slug>')
def operator_page(slug):
    op = Operator.query.filter_by(slug=slug).first()
    if not op:
        abort(404)
    tours = op.tours
    # newest first, same ordering as the tour review lists (seed rows are
    # inserted in upstream display order)
    reviews = Review.query.filter(
        Review.tour_id.in_([t.id for t in tours])).order_by(
        Review.id.asc()).limit(6).all()
    return render_template('operator.html', op=op, tours=tours[:12],
                           total_tours=len(tours), reviews=reviews)


@app.route('/operators-list')
def operators_list():
    ops = Operator.query.order_by(Operator.name).all()
    return render_template('operators_list.html', ops=ops)


@app.route('/moments')
def moments_page():
    items = Moment.query.order_by(Moment.id).limit(48).all()
    return render_template('moments.html', moments=items)


@app.route('/reviews-of-tourradar')
def platform_reviews():
    reviews = PlatformReview.query.order_by(PlatformReview.id.desc()).limit(20).all()
    return render_template('platform_reviews.html', reviews=reviews)


# ---------------------------------------------------------------- wishlist --

@app.route('/wishlist/toggle/<int:tour_id>', methods=['POST'])
def wishlist_toggle(tour_id):
    tour = Tour.query.get_or_404(tour_id)
    if not current_user.is_authenticated:
        flash('Log in or create an account to save adventures to your wishlist.')
        return redirect(url_for('login', next=f'/t/{tour_id}'))
    item = WishlistItem.query.filter_by(user_id=current_user.id,
                                         tour_id=tour_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash(f'Removed {tour.name} from your saved adventures.')
    else:
        db.session.add(WishlistItem(user_id=current_user.id, tour_id=tour_id,
                                    created_at=MIRROR_TODAY.isoformat()))
        db.session.commit()
        flash(f'Saved {tour.name} to your adventures.')
    return redirect(request.form.get('next') or f'/t/{tour_id}')


@app.route('/wishlists')
@app.route('/wishlists/new')
def wishlists():
    if not current_user.is_authenticated:
        top_dests = Destination.query.filter_by(kind='d').order_by(
            Destination.name).limit(12).all()
        top_ops = Operator.query.order_by(
            Operator.reviews_count.desc()).limit(6).all()
        return render_template('wishlist_intro.html', top_dests=top_dests,
                               top_ops=top_ops)
    items = WishlistItem.query.filter_by(user_id=current_user.id).order_by(
        WishlistItem.id.desc()).all()
    return render_template('wishlist.html', items=items)


# --------------------------------------------------------------------- auth --

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.display_name}!')
            return redirect(request.args.get('next') or '/account')
        flash('Incorrect email or password. Please try again.')
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        display = (request.form.get('display_name') or '').strip()
        if not email or '@' not in email:
            flash('Please enter a valid email address.')
        elif len(password) < 8:
            flash('Password must be at least 8 characters long.')
        elif User.query.filter_by(email=email).first():
            flash('An account with this email already exists. Log in instead.')
        else:
            base = re.sub(r'[^a-z0-9]', '', email.split('@')[0].lower()) or 'traveler'
            username = base
            n = 1
            while User.query.filter_by(username=username).first():
                n += 1
                username = f"{base}{n}"
            if not display:
                display = email.split('@')[0].title()
            user = User(email=email, username=username, display_name=display)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f'Welcome to TourRadar, {user.display_name}!')
            return redirect('/account')
    return render_template('signup.html')


@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect('/')


@app.route('/account')
@login_required
def account():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(
        Booking.id.desc()).all()
    saved = WishlistItem.query.filter_by(user_id=current_user.id).order_by(
        WishlistItem.id.desc()).all()
    return render_template('account.html', bookings=bookings, saved=saved)


@app.route('/account/profile', methods=['GET', 'POST'])
@login_required
def account_profile():
    if request.method == 'POST':
        current_user.display_name = (request.form.get('display_name') or
                                     current_user.display_name).strip()
        current_user.nationality = (request.form.get('nationality') or '').strip() or None
        current_user.phone = (request.form.get('phone') or '').strip() or None
        db.session.commit()
        flash('Profile updated.')
        return redirect('/account/profile')
    return render_template('profile.html')


# ------------------------------------------------------------------ booking --

def _room_options(tour, dep=None):
    """Room options shown at booking. The double-room price is the selected
    departure's per-person price (the upstream book-now page prices the
    chosen departure, not the From-price on the card)."""
    price = (dep.price if dep is not None and dep.price else tour.current_price) or 0
    single = round(price * 1.36) if price else 0
    return [
        {'key': 'double', 'name': 'Double Room', 'shared': 'Shared',
         'desc': "Per person in a shared room for two people. If you're "
                 "booking together, you'll be paired with your travel "
                 "partner. Solo adult travelers are matched with a fellow "
                 "guest of the same gender.",
         'price': price, 'was': tour.price_from or price},
        {'key': 'single', 'name': 'Single Room', 'shared': 'Private',
         'desc': "Enjoy the comfort and privacy of your own room.",
         'price': single, 'was': round(single * 1.36) if single else 0},
    ]


def _insurance_options(total):
    premium = round(total * 0.086, 2)
    cancellation = round(total * 0.0485, 2)
    return [
        {'key': 'premium', 'name': 'Premium Protection',
         'price': premium,
         'desc': 'Trip Cancellation, Medical and Dental, Trip Interruption, '
                 'Emergency Assistance and Transportation, Baggage Loss or '
                 'Theft, Travel Delays'},
        {'key': 'cancellation', 'name': 'Trip Cancellation Only',
         'price': cancellation,
         'desc': f'For US${cancellation:,.2f}, this reimburses prepaid '
                 'travel costs if you or your travel partners cancel due to '
                 'injury or illness, prior to your departure'},
        {'key': 'none', 'name': 'No Protection', 'price': 0,
         'desc': 'Your prepaid trip costs would be lost if you or your '
                 'travel companions can\u2019t travel or need to cut your '
                 'trip short due to illness or injuries.'},
    ]


@app.route('/book-now/<int:tour_id>', methods=['GET', 'POST'])
def book_now(tour_id):
    tour = Tour.query.get_or_404(tour_id)
    dep_date = request.values.get('date')
    dep = None
    for d in tour.departures:
        if d.start_date == dep_date and d.status == 'available':
            dep = d
            break
    if dep is None:
        dep = tour.next_departure
    if dep is None:
        return render_template('no_dates.html', tour=tour)
    n_travelers = _safe_int('travellers', 2, lo=1, hi=9) or 2
    rooms = _room_options(tour, dep)
    if request.method == 'POST':
        action = request.form.get('action', 'book')
        n_travelers = _safe_int('travelers', 2, lo=1, hi=9) or 2
        room_key = request.form.get('room_type', 'double')
        room = next((r for r in rooms if r['key'] == room_key), rooms[0])
        insurance_key = request.form.get('insurance', 'none')
        promo = (request.form.get('promo_code') or '').strip().upper()
        schedule = request.form.get('payment_schedule', 'deposit')
        # travelers
        travelers = []
        valid = True
        for i in range(n_travelers):
            first = (request.form.get(f'first_{i}') or '').strip()
            last = (request.form.get(f'last_{i}') or '').strip()
            if not first or not last:
                valid = False
            travelers.append({
                'title': request.form.get(f'title_{i}', 'Mr.'),
                'first': first, 'last': last,
                'dob': request.form.get(f'dob_{i}', ''),
                'gender': request.form.get(f'gender_{i}', ''),
                'nationality': request.form.get(f'nationality_{i}', ''),
            })
        lead_email = (request.form.get('email') or '').strip().lower()
        lead_phone = (request.form.get('phone') or '').strip()
        card_name = (request.form.get('card_name') or '').strip()
        card_number = re.sub(r'\D', '', request.form.get('card_number') or '')
        expiry = (request.form.get('expiry') or '').strip()
        cvv = (request.form.get('cvv') or '').strip()
        accept = request.form.get('accept_terms')
        errors = []
        if not valid:
            errors.append('Please provide first and last names for every traveler.')
        if '@' not in lead_email:
            errors.append('Please provide a valid contact email address.')
        if not lead_phone:
            errors.append('Please provide a contact phone number.')
        if len(card_number) < 13 or len(card_number) > 19:
            errors.append('Please enter a valid card number.')
        if not re.fullmatch(r'(0[1-9]|1[0-2])/\d{2}', expiry):
            errors.append('Please enter a valid expiry date (MM/YY).')
        if not re.fullmatch(r'\d{3,4}', cvv):
            errors.append('Please enter a valid CVV.')
        if not card_name:
            errors.append('Please provide the cardholder name.')
        if not accept:
            errors.append("Please accept the terms, conditions and the "
                          "operator's payment, cancellation and refund conditions.")

        per_person = room['price']
        subtotal = per_person * n_travelers
        discount = 0
        promo_row = None
        if promo:
            promo_row = PromoCode.query.filter_by(code=promo, active=True).first()
            if promo_row and subtotal >= (promo_row.min_total or 0):
                if promo_row.kind == 'pct':
                    discount = round(subtotal * promo_row.value / 100, 2)
                else:
                    discount = min(promo_row.value, subtotal)
            elif promo_row is None:
                errors.append(f"Promo code {promo} is not valid.")
        total = round(subtotal - discount, 2)
        if insurance_key == 'premium':
            total = round(total + _insurance_options(subtotal)[0]['price'], 2)
        elif insurance_key == 'cancellation':
            total = round(total + _insurance_options(subtotal)[1]['price'], 2)
        if errors:
            for e in errors:
                flash(e)
            return render_template('book_now.html', tour=tour, dep=dep,
                                   rooms=rooms, n=n_travelers, args={},
                                   form=request.form, errors=errors,
                                   insurance=_insurance_options(subtotal),
                                   total=total), 400
        if action == 'hold':
            flash(f"We're holding your space on {tour.name} for 48 hours. "
                  "Check your email to confirm.")
            return redirect(f'/t/{tour.id}')
        # create the booking
        ref = 'TR-' + f"{tour.id:05d}{n_travelers:02d}" + f"{(Departure.query.count() + Booking.query.count() + 1) % 10000:04d}"
        user = current_user if current_user.is_authenticated else None
        if user is None:
            email_owner = User.query.filter_by(email=lead_email).first()
            if email_owner:
                user = email_owner
        if user is None:
            base = re.sub(r'[^a-z0-9]', '', lead_email.split('@')[0].lower()) or 'guest'
            username = base
            n_ = 1
            while User.query.filter_by(username=username).first():
                n_ += 1
                username = f"{base}{n_}"
            user = User(email=lead_email, username=username,
                       display_name=lead_email.split('@')[0].title(),
                       phone=lead_phone)
            user.password_hash = BENCHMARK_PASSWORD_HASH
            db.session.add(user)
            db.session.flush()
        due_today = round(total * DEPOSIT_PCT / 100, 2) if schedule == 'deposit' else total
        if schedule == 'installments':
            due_today = round(total * DEPOSIT_PCT / 100, 2)
        booking = Booking(ref=ref, user_id=user.id, tour_id=tour.id,
                          departure_date=dep.start_date,
                          travelers=json.dumps(travelers),
                          room_type=room['name'], room_count=1,
                          insurance=insurance_key,
                          promo_code=promo if discount else None,
                          payment_schedule=schedule, total=total,
                          due_today=due_today, status='confirmed',
                          created_at=MIRROR_TODAY.isoformat(),
                          lead_email=lead_email, lead_phone=lead_phone)
        db.session.add(booking)
        db.session.commit()
        return redirect(f'/booking/{ref}')
    return render_template('book_now.html', tour=tour, dep=dep, rooms=rooms,
                           n=n_travelers, args=request.args, form={},
                           errors=[], insurance=_insurance_options(
                               (tour.current_price or 0) * n_travelers),
                           total=(tour.current_price or 0) * n_travelers)


@app.route('/booking/<ref>')
def booking_detail(ref):
    booking = Booking.query.filter_by(ref=ref).first_or_404()
    return render_template('booking_detail.html', booking=booking)


@app.route('/booking/<ref>/cancel', methods=['POST'])
@login_required
def booking_cancel(ref):
    booking = Booking.query.filter_by(ref=ref).first_or_404()
    if booking.user_id != current_user.id:
        abort(403)
    if booking.status != 'confirmed':
        flash('Only confirmed bookings can be cancelled.')
        return redirect(f'/booking/{ref}')
    booking.status = 'cancelled'
    db.session.commit()
    flash(f'Booking {ref} has been cancelled. Any payments made will be '
          'refunded per the operator\'s cancellation policy.')
    return redirect(f'/booking/{ref}')


@app.route('/t/<int:tour_id>/ask', methods=['POST'])
def tour_ask(tour_id):
    tour = Tour.query.get_or_404(tour_id)
    question = (request.form.get('question') or '').strip()
    asker = (request.form.get('asker') or '').strip()
    if len(question) < 10:
        flash('Please enter your question (at least 10 characters).')
        return redirect(f'/t/{tour_id}#ask')
    if current_user.is_authenticated:
        asker = asker or current_user.display_name
    elif not asker:
        asker = 'Traveler'
    db.session.add(TourQA(
        tour_id=tour.id, question=question, asker=asker,
        asked_date='September 27th, 2026', tags='[]',
        answer=None, answer_by=None, answer_date=None))
    db.session.commit()
    flash('Your question has been sent to the operator. Answers usually '
          'arrive within a day.')
    return redirect(f'/t/{tour_id}#ask')


@app.route('/t/<int:tour_id>/review', methods=['POST'])
@login_required
def tour_review(tour_id):
    tour = Tour.query.get_or_404(tour_id)
    completed = Booking.query.filter_by(
        user_id=current_user.id, tour_id=tour.id, status='completed').first()
    if not completed:
        flash('You can only review tours you have completed with a booking '
              'on this account.')
        return redirect(f'/t/{tour_id}')
    body = (request.form.get('body') or '').strip()
    rating = float(request.form.get('rating') or 5)
    title = (request.form.get('title') or '').strip()
    if len(body) < 20:
        flash('Please write a review of at least 20 characters.')
        return redirect(f'/t/{tour_id}/reviews')
    month = 'September 2026'
    db.session.add(Review(tour_id=tour.id, author=current_user.display_name,
                          initials=''.join(w[0] for w in
                                           current_user.display_name.split()[:2]).upper(),
                          rating=rating, month=month,
                          traveled_month=None, title=title or None, body=body))
    db.session.commit()
    flash('Thank you! Your review has been published.')
    return redirect(f'/t/{tour_id}/reviews')


# ------------------------------------------------------------ static pages --

@app.route('/about')
def about():
    return render_template('static/about.html')


@app.route('/contact')
def contact():
    return render_template('static/contact.html')


@app.route('/trust')
def trust():
    return render_template('static/trust.html')


@app.route('/cancellation-policy')
def cancellation_policy():
    return render_template('static/cancellation_policy.html')


@app.route('/terms-conditions')
def terms_conditions():
    return render_template('static/terms.html')


@app.route('/privacy')
def privacy():
    return render_template('static/privacy.html')


@app.route('/cookie-policy')
def cookie_policy():
    return render_template('static/cookie_policy.html')


@app.route('/legal-notice')
def legal_notice():
    return render_template('static/legal_notice.html')


@app.route('/careers')
def careers():
    return render_template('static/careers.html')


@app.route('/payments')
def payments():
    return render_template('static/payments.html')


@app.route('/post-booking-services')
def post_booking_services():
    return render_template('static/post_booking.html')


@app.route('/travel-insurance')
def travel_insurance():
    return render_template('static/travel_insurance.html')


@app.route('/contests')
def contests():
    return render_template('static/contests.html')


@app.route('/invite')
def invite():
    return render_template('static/invite.html')


@app.route('/agents')
def agents():
    return render_template('static/agents.html')


@app.route('/distribution-api')
def distribution_api():
    return render_template('static/distribution_api.html')


@app.route('/newsletter', methods=['POST'])
def newsletter():
    email = (request.form.get('email') or '').strip()
    if '@' in email:
        flash("You're subscribed! Check your inbox for exclusive deals.")
    else:
        flash('Please enter a valid email address.')
    return redirect(request.form.get('next') or '/')


@app.errorhandler(404)
def not_found(e):
    tours = Tour.query.order_by((Tour.discount_pct * Tour.review_count).desc()).limit(3).all()
    return render_template('404.html', tours=tours), 404


# ------------------------------------------------------------------ bootstrap

def _load_source(name):
    path = os.path.join(BASE_DIR, name)
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def seed_database():
    if Tour.query.count() > 0:
        return
    source = _load_source('source_data_tours.json')
    meta = _load_source('source_data_catalog.json')

    op_rows = meta.get('operators', [])
    op_by_name = {}
    for row in op_rows:
        op = Operator(id=row['id'], slug=row['slug'], name=row['name'],
                      badge=row.get('badge'), rating=row.get('rating', 0),
                      reviews_count=row.get('reviews_count', 0),
                      hq=row.get('hq'), response_rate=row.get('response_rate'),
                      response_time=row.get('response_time'),
                      age_min=row.get('age_min'), age_max=row.get('age_max'),
                      about=row.get('about'), awards=json.dumps(row.get('awards', [])),
                      logo=row.get('logo'))
        db.session.add(op)
        op_by_name[row['name']] = op

    for row in meta.get('destinations', []):
        db.session.add(Destination(
            id=row['id'], slug=row['slug'], name=row['name'], kind=row['kind'],
            group_name=row.get('group'), parent_slug=row.get('parent'),
            hero=row.get('hero'), description=row.get('description'),
            sections=json.dumps(row.get('sections', {}), ensure_ascii=False),
            quick_filters=json.dumps(row.get('quick_filters', []),
                                     ensure_ascii=False)))
    db.session.commit()

    for row in source:
        op = op_by_name.get(row.get('operator', ''))
        if op is None:
            op = op_by_name.get('Expat Explore Travel')
        tour = Tour(
            id=row['id'], name=row['name'], operator_id=op.id,
            duration_days=row.get('duration_days', 1),
            start_city=row.get('start_city'), end_city=row.get('end_city'),
            start_end_note=row.get('start_end_note'),
            rating=row.get('rating', 0), review_count=row.get('review_count', 0),
            subratings=json.dumps(row.get('subratings', {})),
            price_from=row.get('price_from'), price_current=row.get('price_current'),
            discount_pct=row.get('discount_pct'), price_basis=row.get('price_basis'),
            style=row.get('style'),
            attributes=json.dumps(row.get('attributes', [])),
            group_min=row.get('group_min'), group_max=row.get('group_max'),
            min_age=row.get('min_age'), max_age=row.get('max_age'),
            guided_language=row.get('guided_language'),
            group_type=row.get('group_type'), guide_type=row.get('guide_type'),
            physical=row.get('physical'),
            instant_confirm=row.get('instant_confirm', False),
            intro=row.get('intro'), summary=row.get('summary'),
            summary_author=row.get('summary_author'),
            cities=json.dumps(row.get('cities', [])),
            countries=json.dumps(row.get('countries', [])),
            dest_slugs=json.dumps(row.get('dest_slugs', [])),
            days=json.dumps(row.get('days', [])),
            included=json.dumps(row.get('included', {})),
            not_included=json.dumps(row.get('not_included', {})),
            good_to_know=json.dumps(row.get('good_to_know', {})),
            videos=json.dumps(row.get('videos', [])),
            similar_ids=json.dumps(row.get('similar', [])),
            hero=row.get('hero'),
            gallery=json.dumps(row.get('gallery', [])),
            best_months=json.dumps(row.get('best_months', {})),
            code=row.get('code'))
        db.session.add(tour)
        for dep in row.get('departures', []):
            db.session.add(Departure(
                tour_id=tour.id, start_date=dep['start'], end_date=dep['end'],
                status=dep.get('status', 'available'), price=dep['price'],
                was_price=dep.get('was'), discount_pct=dep.get('discount'),
                guaranteed=dep.get('guaranteed', False),
                instant=dep.get('instant', False),
                language=dep.get('language'), basis=dep.get('basis'),
                spaces=dep.get('spaces')))
        for rev in row.get('reviews', []):
            db.session.add(Review(
                tour_id=tour.id, author=rev.get('author', 'Traveler'),
                initials=rev.get('initials'), rating=rev.get('rating', 5),
                month=rev.get('month'), traveled_month=rev.get('traveled'),
                title=rev.get('title'), body=rev.get('body'),
                guide_name=rev.get('guide'), reply=rev.get('reply'),
                reply_by=rev.get('reply_by'), photos=json.dumps(rev.get('photos', [])),
                avatar=rev.get('avatar')))
        for qa in row.get('qa', []):
            db.session.add(TourQA(
                tour_id=tour.id, question=qa.get('question', ''),
                asker=qa.get('asker'), asked_date=qa.get('asked_date'),
                tags=json.dumps(qa.get('tags', [])),
                answer=qa.get('answer'), answer_by=qa.get('answer_by'),
                answer_date=qa.get('answer_date')))
        for mom in row.get('moments', []):
            db.session.add(Moment(
                tour_id=tour.id, tour_name=tour.name,
                author=mom.get('author'), avatar=mom.get('avatar'),
                image=mom.get('image'), caption=mom.get('caption')))
    db.session.commit()

    content = _load_source('source_data_content.json')
    for row in content.get('moments', []):
        db.session.add(Moment(tour_id=row.get('tour_id'),
                              tour_name=row.get('tour_name'),
                              author=row.get('author'),
                              avatar=row.get('avatar'),
                              image=row.get('image'),
                              caption=row.get('caption')))
    for row in content.get('platform_reviews', []):
        db.session.add(PlatformReview(
            author=row.get('author'), initials=row.get('initials'),
            rating=row.get('rating', 5), date=row.get('date'),
            body=row.get('body'), source=row.get('source', 'Trustpilot'),
            tour_name=row.get('tour_name')))
    for row in content.get('promo_codes', []):
        db.session.add(PromoCode(code=row['code'], kind=row['kind'],
                                 value=row['value'], min_total=row.get('min_total', 0),
                                 active=True, label=row.get('label')))
    db.session.commit()


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    users = [
        {'username': 'alice_j', 'email': 'alice.j@test.com', 'display': 'Alice Johnson'},
        {'username': 'bob_c', 'email': 'bob.c@test.com', 'display': 'Bob Chen'},
        {'username': 'carol_d', 'email': 'carol.d@test.com', 'display': 'Carol Davis'},
        {'username': 'david_k', 'email': 'david.k@test.com', 'display': 'David Kim'},
    ]
    created = {}
    for u in users:
        user = User(email=u['email'], username=u['username'],
                    display_name=u['display'], nationality='USA',
                    phone='+1 555 0100')
        user.password_hash = BENCHMARK_PASSWORD_HASH
        db.session.add(user)
        created[u['username']] = user
    db.session.commit()

    def _tour_by_name(pattern):
        return Tour.query.filter(Tour.name.ilike(f'%{pattern}%')).order_by(
            Tour.review_count.desc()).first()

    def _bali_tour():
        return (Tour.query.filter(Tour.cities.contains('"Bali"'))
                .order_by(Tour.review_count.desc()).first())

    def _wish(user, tour):
        if tour:
            db.session.add(WishlistItem(user_id=user.id, tour_id=tour.id,
                                        created_at='2026-08-14'))

    def _book(user, ref, tour, dep_date, room, n, status,
              insurance='none', promo=None, days_ago=0):
        if not tour:
            return
        dep = next((d for d in tour.departures if d.start_date == dep_date), None)
        base = dep.price if dep else (tour.current_price or 1000)
        total = round(base * n, 2)
        travelers = []
        first = user.display_name.split()[0]
        last = user.display_name.split()[-1]
        for i in range(n):
            travelers.append({'title': 'Mr.' if i % 2 == 0 else 'Ms.',
                              'first': first if i % 2 == 0 else 'Maria',
                              'last': last,
                              'dob': f'1990-05-1{i + 1}',
                              'gender': 'Male' if i % 2 == 0 else 'Female',
                              'nationality': 'USA'})
        booking = Booking(ref=ref, user_id=user.id, tour_id=tour.id,
                          departure_date=dep_date,
                          travelers=json.dumps(travelers), room_type=room,
                          room_count=1, insurance=insurance, promo_code=promo,
                          payment_schedule='deposit', total=total,
                          due_today=round(total * DEPOSIT_PCT / 100, 2),
                          status=status,
                          created_at=(MIRROR_TODAY - timedelta(days=days_ago)).isoformat(),
                          lead_email=user.email, lead_phone=user.phone)
        db.session.add(booking)

    # ---- Alice: two confirmed upcoming bookings (different departure
    # months, so "the one departing first" is well-defined), one completed
    # trip, and a wishlist.
    tours_all = Tour.query.order_by(Tour.review_count.desc()).all()
    upcoming = []
    for t in tours_all:
        dep = t.next_departure
        if dep:
            upcoming.append((t, dep))
    alice_books = []
    if len(upcoming) >= 2:
        alice_books = [upcoming[0], upcoming[1]]
    elif upcoming:
        alice_books = [upcoming[0]]
    if len(alice_books) >= 1:
        t, dep = alice_books[0]
        _book(created['alice_j'], 'TR-000010101', t, dep.start_date,
              'Double Room', 2, 'confirmed', insurance='premium', days_ago=6)
    if len(alice_books) >= 2:
        t, dep = alice_books[1]
        _book(created['alice_j'], 'TR-000010102', t, dep.start_date,
              'Double Room', 2, 'confirmed', days_ago=12)
    completed_tour = _tour_by_name('Egypt') or (tours_all[7] if len(tours_all) > 7 else None)
    _book(created['alice_j'], 'TR-000010103', completed_tour, '2026-07-12',
          'Double Room', 1, 'completed', days_ago=54)
    for t in tours_all[2:5]:
        _wish(created['alice_j'], t)

    # ---- Bob: wishlist with exactly one Bali tour plus three others; one
    # completed booking with a promo code.
    bali = _bali_tour()
    _wish(created['bob_c'], bali)
    others = [t for t in tours_all if t.id != (bali.id if bali else -1)][:3]
    for t in others:
        _wish(created['bob_c'], t)
    bob_tour = _tour_by_name('Morocco') or (tours_all[4] if len(tours_all) > 4 else None)
    _book(created['bob_c'], 'TR-000020301', bob_tour, '2026-08-02',
          'Single Room', 1, 'completed', promo='ESCAPE10', days_ago=40)

    # ---- Carol: one confirmed upcoming + wishlist.
    if len(upcoming) >= 3:
        t, dep = upcoming[2]
        _book(created['carol_d'], 'TR-000030401', t, dep.start_date,
              'Double Room', 2, 'confirmed', days_ago=12)
    for t in tours_all[6:8]:
        _wish(created['carol_d'], t)

    # ---- David: one completed booking (reviewable) + wishlist.
    david_tour = _tour_by_name('Peru') or (_tour_by_name('Iceland')
                                            or (tours_all[3] if len(tours_all) > 3 else None))
    _book(created['david_k'], 'TR-000040501', david_tour, '2026-05-20',
          'Double Room', 2, 'completed', days_ago=90)
    for t in tours_all[8:11]:
        _wish(created['david_k'], t)
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


def main() -> None:
    """Standalone entry: build instance/tourradar.db (idempotent)."""
    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()
    print('seeded')


if __name__ == '__main__':
    main()
