#!/usr/bin/env python3
"""Ticketmaster mirror — Flask application.

Mirrors https://www.ticketmaster.com/: discovery browsing across Concerts /
Sports / Arts & Theater / Family with filters, scored site search, event pages
with real ticket listings (quantity / price / ticket-type / accessible filters,
Lowest Price and Best Seats sorts), a ticket-selection panel with a face-value
+ service-fee breakdown, guest and signed-in checkout (delivery, payment,
review, confirmation with order number), artist pages with ratings and
favorites, venue pages with upcoming events, a member area (orders, profile,
payment methods, favorites), gift cards page, help centre, sell landing page
and presale codes.

All content rows come from the tracked source_data_*.json snapshots captured
from the live site on 2026-09-27; the SQLite seed is materialized deterministically at image
build time (PYTHONHASHSEED=0).
"""
import hashlib
import json
import math
import os
import re
from datetime import datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("TICKETMASTER_SECRET_KEY") or "webharbor-ticketmaster-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'TICKETMASTER_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'ticketmaster.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'signin'
login_manager.login_message = 'Please log in to access your account.'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

csrf = CSRFProtect(app)

# The mirror is a snapshot of the upstream site taken on 2026-09-27.
MIRROR_TODAY = datetime(2026, 9, 27, 12, 0, 0)
# bcrypt hash of 'TestPass123!' (frozen so the SQLite seed is byte-reproducible)
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')
SERVICE_FEE_RATE = 0.376          # calibrated from the real Reno listing ($40.60 = $29.50 face + $11.10 fee)
GENRE_MAP = {
    'concerts': 'Music',
    'sports': 'Sports',
    'arts-theater': 'Arts & Theater',
    'family': 'Family',
}
GENRE_LABELS = {
    'concerts': 'Concerts',
    'sports': 'Sports',
    'arts-theater': 'Arts, Theater & Comedy',
    'family': 'Family',
}
STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
              'or', 'is', 'it', 'by', 'with', 'vs', 'v', 'tickets', 'ticket'}


# ------------------------------------------------------------------- models --

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(60), default='')
    last_name = db.Column(db.String(60), default='')
    phone = db.Column(db.String(30), default='')
    zip = db.Column(db.String(12), default='')

    orders = db.relationship('Order', backref='user', lazy=True)
    payment_methods = db.relationship('PaymentMethod', backref='user', lazy=True)
    favorites = db.relationship('Favorite', backref='user', lazy=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class Artist(db.Model):
    __tablename__ = 'artists'
    id = db.Column(db.String(16), primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(90), nullable=False)
    image = db.Column(db.String(200))
    rating = db.Column(db.Float)
    rating_count = db.Column(db.Integer)
    category = db.Column(db.String(40))
    favorite_of = db.relationship('Favorite', backref='artist', lazy=True)

    @property
    def events(self):
        return (Event.query.filter_by(artist_id=self.id, is_add_on=False)
                .order_by(Event.date).all())


class Venue(db.Model):
    __tablename__ = 'venues'
    id = db.Column(db.String(16), primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(90), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(20))
    address = db.Column(db.String(200))
    image = db.Column(db.String(200))
    capacity = db.Column(db.Integer)

    @property
    def upcoming(self):
        # upstream venue pages list every event including parking add-ons
        return (Event.query.filter_by(venue_id=self.id)
                .order_by(Event.date, Event.name).all())


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(220), nullable=False)
    slug = db.Column(db.String(120), nullable=False)
    artist_id = db.Column(db.String(16), db.ForeignKey('artists.id'))
    artist = db.relationship('Artist', backref='event_rows', lazy=True)
    venue_id = db.Column(db.String(16), db.ForeignKey('venues.id'))
    venue = db.relationship('Venue', backref='event_rows', lazy=True)
    date = db.Column(db.String(12), nullable=False)
    time = db.Column(db.String(20))
    weekday = db.Column(db.String(12))
    category = db.Column(db.String(40), nullable=False)
    subcategory = db.Column(db.String(60))
    status = db.Column(db.String(15), default='onsale')
    image = db.Column(db.String(200))
    important_info = db.Column(db.Text)
    ticket_limit = db.Column(db.Integer, default=8)
    multi_date = db.Column(db.Boolean, default=False)
    partner = db.Column(db.Boolean, default=False)
    is_add_on = db.Column(db.Boolean, default=False)
    price_min = db.Column(db.Float)
    price_max = db.Column(db.Float)

    listings = db.relationship('TicketListing', backref='event', lazy=True,
                               order_by='TicketListing.face_value')
    presales = db.relationship('Presale', backref='event', lazy=True,
                               order_by='Presale.start')
    favorite_of = db.relationship('Favorite', backref='event', lazy=True)

    @property
    def artist_name(self):
        return self.artist.name if self.artist else self.name

    @property
    def city_state(self):
        v = self.venue
        if not v:
            return ''
        return f"{v.city}, {v.state}" if v.state else v.city

    @property
    def date_pretty(self):
        d = datetime.strptime(self.date, '%Y-%m-%d')
        return d.strftime('%a, %b %d, %Y')

    @property
    def time_line(self):
        """Friendly 'Weekday • time' line for cards (never 'None • None')."""
        wd = self.weekday or self.date_pretty.split(',')[0]
        if self.time and str(self.time).lower() != 'none':
            return f"{wd} • {self.time}"
        return wd

    @property
    def date_num(self):
        return datetime.strptime(self.date, '%Y-%m-%d').strftime('%m/%d/%y')

    @property
    def month(self):
        return datetime.strptime(self.date, '%Y-%m-%d').strftime('%b')

    @property
    def day(self):
        return datetime.strptime(self.date, '%Y-%m-%d').strftime('%d')


class TicketListing(db.Model):
    __tablename__ = 'ticket_listings'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(20), db.ForeignKey('events.id'), nullable=False)
    section = db.Column(db.String(20), nullable=False)
    section_desc = db.Column(db.String(60))
    row = db.Column(db.String(8), nullable=False)
    qty_available = db.Column(db.Integer, default=4)
    face_value = db.Column(db.Float, nullable=False)
    ticket_type = db.Column(db.String(30), default='Standard Admission')
    accessible = db.Column(db.Boolean, default=False)

    @property
    def fee(self):
        return round(self.face_value * SERVICE_FEE_RATE, 2)

    @property
    def price(self):
        return round(self.face_value + self.fee, 2)


class Presale(db.Model):
    __tablename__ = 'presales'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(20), db.ForeignKey('events.id'), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    start = db.Column(db.String(20))
    end = db.Column(db.String(20))
    code = db.Column(db.String(30))


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(16), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    event_id = db.Column(db.String(20), db.ForeignKey('events.id'), nullable=False)
    event = db.relationship('Event', backref='orders', lazy=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('ticket_listings.id'))
    listing = db.relationship('TicketListing', backref='orders', lazy=True)
    section = db.Column(db.String(20))
    section_desc = db.Column(db.String(60))
    row = db.Column(db.String(8))
    qty = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    face_total = db.Column(db.Float)
    fee_total = db.Column(db.Float)
    total = db.Column(db.Float, nullable=False)
    delivery = db.Column(db.String(40))
    card_last4 = db.Column(db.String(4))
    card_brand = db.Column(db.String(20))
    status = db.Column(db.String(20), default='confirmed')
    guest_email = db.Column(db.String(120))
    created_at = db.Column(db.String(20))
    placed_at = db.Column(db.String(20))


class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    brand = db.Column(db.String(20), nullable=False)
    last4 = db.Column(db.String(4), nullable=False)
    exp_month = db.Column(db.Integer)
    exp_year = db.Column(db.Integer)
    holder = db.Column(db.String(80))


class Favorite(db.Model):
    __tablename__ = 'favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    artist_id = db.Column(db.String(16), db.ForeignKey('artists.id'))
    event_id = db.Column(db.String(20), db.ForeignKey('events.id'))
    created_at = db.Column(db.String(20))


# ------------------------------------------------------------------ helpers --

def scored_search(query, items, fields):
    """Token-overlap scored search (never strict AND)."""
    tokens = [t.lower() for t in re.split(r'\W+', query or '')
              if t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return items
    results = []
    for item in items:
        text = ' '.join(getattr(item, f, '') or '' for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            results.append((item, score))
    results.sort(key=lambda pair: (-pair[1], pair[0].name.lower()))
    return [r[0] for r in results]


def parse_money(text):
    try:
        return float(re.sub(r'[^0-9.]', '', str(text)))
    except (TypeError, ValueError):
        return None


class ContentRecord(db.Model):
    __tablename__ = 'content_records'
    id = db.Column(db.Integer, primary_key=True)
    payload = db.Column(db.Text, nullable=False)


def seed_content():
    if db.session.get(ContentRecord, 1) is not None:
        return
    with open(os.path.join(BASE_DIR, 'source_data_content.json'), encoding='utf-8') as source:
        payload = json.dumps(json.load(source), ensure_ascii=False, sort_keys=True)
    db.session.add(ContentRecord(id=1, payload=payload))
    db.session.commit()


def load_content():
    row = db.session.get(ContentRecord, 1)
    if row is None:
        raise RuntimeError('Missing build-generated content seed')
    return json.loads(row.payload)


from werkzeug.local import LocalProxy
CONTENT = LocalProxy(load_content)


def genre_events(genre_key):
    category = GENRE_MAP.get(genre_key)
    if not category:
        return Event.query.filter_by(is_add_on=False)
    return Event.query.filter_by(category=category, is_add_on=False)


def apply_filters(query_obj, args):
    city = args.get('city', '').strip()
    date_from = args.get('date_from', '').strip()
    date_to = args.get('date_to', '').strip()
    price_max = parse_money(args.get('price_max'))
    sub = args.get('sub', '').strip()
    q = query_obj
    if city:
        q = q.join(Venue).filter(Venue.city.ilike(f'%{city}%'))
    if date_from:
        q = q.filter(Event.date >= date_from)
    if date_to:
        q = q.filter(Event.date <= date_to)
    if sub:
        q = q.filter(Event.subcategory == sub)
    if price_max:
        q = q.filter(Event.price_min <= price_max)
    return q


def event_subcategories(category):
    rows = (db.session.query(Event.subcategory, db.func.count(Event.id))
            .filter(Event.category == category, Event.is_add_on.is_(False))
            .group_by(Event.subcategory).order_by(db.func.count(Event.id).desc())
            .all())
    return [(r[0], r[1]) for r in rows if r[0]]


def event_cities(category=None):
    q = (db.session.query(Venue.city, db.func.count(Event.id))
         .join(Event, Event.venue_id == Venue.id)
         .filter(Event.is_add_on.is_(False)))
    if category:
        q = q.filter(Event.category == category)
    rows = q.group_by(Venue.city).order_by(db.func.count(Event.id).desc()).all()
    return [(r[0], r[1]) for r in rows]


def upcoming_by_artist(artist_id, limit=None):
    q = (Event.query.filter_by(artist_id=str(artist_id), is_add_on=False)
         .order_by(Event.date))
    return q.all() if limit is None else q.limit(limit).all()


def favorite_event_ids():
    if not current_user.is_authenticated:
        return set()
    return {f.event_id for f in current_user.favorites if f.event_id}


def favorite_artist_ids():
    if not current_user.is_authenticated:
        return set()
    return {f.artist_id for f in current_user.favorites if f.artist_id}


def price_band(event):
    """Human price range for cards/listings."""
    if event.price_min is None:
        return ''
    if event.price_max and event.price_max > event.price_min:
        return f"${event.price_min:.0f} - ${event.price_max:.0f}"
    return f"from ${event.price_min:.0f}"


@app.template_filter('pretty_dt')
def pretty_dt(value):
    """Render an ISO datetime ('2026-10-25T00:00:00Z' / '2026-10-25') as a
    human date, e.g. 'Sun, Oct 25, 2026'. Falls back to the raw value."""
    s = str(value or '').strip()
    try:
        d = datetime.strptime(s[:10], '%Y-%m-%d')
        return d.strftime('%a, %b %d, %Y')
    except ValueError:
        return s


@app.template_filter('urlenc')
def urlenc(value):
    from urllib.parse import quote_plus
    return quote_plus(str(value or ''))


@app.template_filter('slugify')
def slugify_filter(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value or '').lower()).strip('-')


app.jinja_env.globals.update(
    price_band=price_band,
    CONTENT=CONTENT,
    GENRE_LABELS=GENRE_LABELS,
    MIRROR_TODAY=MIRROR_TODAY,
)


# ------------------------------------------------------------------- routes --

def homepage_selection(events, limit, exclude=()):
    """Show different performers, rotating categories instead of tour dates."""
    seen = {e.artist_id or e.name.casefold() for e in exclude}
    groups = {category: [] for category in GENRE_MAP.values()}
    for event in events:
        identity = event.artist_id or event.name.casefold()
        if not event.image or identity in seen:
            continue
        seen.add(identity)
        groups.setdefault(event.category, []).append(event)
    selected = []
    while len(selected) < limit and any(groups.values()):
        for group in groups.values():
            if group and len(selected) < limit:
                selected.append(group.pop(0))
    return selected


@app.route('/')
def index():
    base = Event.query.filter_by(is_add_on=False).filter(
        Event.date >= MIRROR_TODAY.date().isoformat())
    upcoming = base.order_by(Event.date, Event.id).all()
    # Saturday/Sunday containing the snapshot day, or the next weekend.
    saturday = MIRROR_TODAY.date() + timedelta(days=(5 - MIRROR_TODAY.weekday()) % 7)
    if MIRROR_TODAY.weekday() == 6:
        saturday -= timedelta(days=7)
    sunday = saturday + timedelta(days=1)
    weekend = homepage_selection(
        [e for e in upcoming if saturday.isoformat() <= e.date <= sunday.isoformat()], 8)
    featured = homepage_selection(upcoming, 9, exclude=weekend)
    hero = featured[0] if featured else None
    highlights = featured[1:]
    popular = {}
    for genre_key, category in GENRE_MAP.items():
        popular[genre_key] = homepage_selection(
            [e for e in upcoming if e.category == category], 10)
    trending = []
    for row in CONTENT['trending_searches']:
        artist = Artist.query.get(row['artist_id'])
        if artist:
            trending.append({'label': row['label'], 'artist': artist})
    return render_template('index.html', hero=hero, highlights=highlights, weekend=weekend,
                           popular=popular, trending=trending,
                           cities=CONTENT['cities'])


@app.route('/discover/cities')
def discover_cities():
    cities = event_cities()
    tiles = CONTENT['cities']
    return render_template('cities.html', cities=cities, tiles=tiles)


@app.route('/discover/cities/<slug>')
def city_page(slug):
    """City landing page: every upcoming event hosted in that city, grouped by
    category — the target of the homepage/cities city tiles."""
    def slugify(s):
        return re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')

    city = None
    for name, _count in event_cities():
        if slugify(name) == slug:
            city = name
            break
    if city is None:
        for tile in CONTENT['cities']:
            if slugify(tile['name']) == slug:
                city = tile['name']
                break
    if city is None:
        abort(404)
    events = (Event.query.join(Venue, Event.venue_id == Venue.id)
              .filter(Venue.city == city, Event.is_add_on.is_(False))
              .order_by(Event.date).all())
    cats = {}
    for e in events:
        cats.setdefault(e.category, []).append(e)
    tiles = CONTENT['cities']
    tile = next((t for t in tiles if slugify(t['name']) == slug), None)
    return render_template('city.html', city=city, events=events, cats=cats,
                          tile=tile, tiles=tiles, total=len(events))


@app.route('/discover/<genre_key>')
def discover(genre_key):
    if genre_key == 'cities':
        return redirect(url_for('discover_cities'))
    category = GENRE_MAP.get(genre_key)
    if not category:
        abort(404)
    q = genre_events(genre_key)
    q = apply_filters(q, request.args)
    sort = request.args.get('sort', 'date')
    if sort == 'price':
        events = q.order_by(Event.price_min).all()
    else:
        events = q.order_by(Event.date).all()
    subs = event_subcategories(category)
    cities = event_cities(category)
    return render_template('discover.html', genre_key=genre_key,
                           category=category, events=events, subs=subs,
                           cities=cities, args=request.args, sort=sort)


@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'relevance')
    events, artists, venues = [], [], []
    if query:
        all_events = Event.query.filter_by(is_add_on=False).all()
        events = scored_search(query, all_events,
                               ['name', 'subcategory', 'category'])
        all_artists = Artist.query.all()
        artists = scored_search(query, all_artists, ['name'])[:8]
        all_venues = Venue.query.all()
        venues = scored_search(query, all_venues, ['name', 'city'])[:8]
        if sort == 'date':
            events = sorted(events, key=lambda e: e.date)
    else:
        events = Event.query.filter_by(is_add_on=False).order_by(Event.date).limit(20).all()
    return render_template('search.html', query=query, events=events,
                           artists=artists, venues=venues, sort=sort)


@app.route('/event/<event_id>')
def event_page(event_id):
    event = Event.query.get_or_404(event_id)
    listings = list(event.listings)
    if event.status in ('cancelled', 'postponed'):
        listings = []
    # filters
    qty = request.args.get('qty', type=int)
    price_max = parse_money(request.args.get('price_max'))
    ltype = request.args.get('type', '')
    accessible = request.args.get('accessible', '')
    sort = request.args.get('sort', 'lowest')
    if qty:
        listings = [l for l in listings if l.qty_available >= qty]
    if price_max:
        listings = [l for l in listings if l.price <= price_max]
    if ltype:
        listings = [l for l in listings if l.ticket_type == ltype]
    if accessible:
        listings = [l for l in listings if l.accessible]
    if sort == 'best':
        listings.sort(key=lambda l: (l.section_desc or '', l.row))
    elif sort == 'high':
        listings.sort(key=lambda l: -l.price)
    else:
        listings.sort(key=lambda l: l.price)
    sections = sorted({(l.section, l.section_desc or l.section) for l in event.listings})
    types = sorted({l.ticket_type for l in event.listings})
    related = (Event.query
               .filter(Event.artist_id == event.artist_id, Event.id != event.id,
                       Event.is_add_on.is_(False))
               .order_by(Event.date).limit(8).all()) if event.artist_id else []
    return render_template('event.html', event=event, listings=listings,
                           sections=sections, types=types, related=related,
                           args=request.args, qty=qty, price_max=price_max,
                           ltype=ltype, accessible=accessible, sort=sort,
                           fav_events=favorite_event_ids())


@app.route('/event/<event_id>/tickets', methods=['GET', 'POST'])
def ticket_select(event_id):
    event = Event.query.get_or_404(event_id)
    listing_id = request.values.get('listing', type=int)
    qty = request.values.get('qty', 2, type=int)
    listing = TicketListing.query.filter_by(event_id=event.id, id=listing_id).first_or_404()
    if qty < 1 or qty > min(listing.qty_available, event.ticket_limit):
        qty = 2
    subtotal = round(listing.price * qty, 2)
    face_total = round(listing.face_value * qty, 2)
    fee_total = round(listing.fee * qty, 2)
    if request.method == 'POST':
        session['draft'] = {
            'event_id': event.id,
            'listing_id': listing.id,
            'qty': qty,
            'unit_price': listing.price,
            'face_total': face_total,
            'fee_total': fee_total,
            'total': subtotal,
        }
        return redirect(url_for('checkout'))
    return render_template('ticket_select.html', event=event, listing=listing,
                           qty=qty, subtotal=subtotal, face_total=face_total,
                           fee_total=fee_total)


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    draft = session.get('draft')
    if not draft:
        return redirect(url_for('index'))
    event = Event.query.get_or_404(draft['event_id'])
    listing = TicketListing.query.get_or_404(draft['listing_id'])
    step = request.values.get('step', 'delivery')
    draft_data = {
        'event': event, 'listing': listing, 'qty': draft['qty'],
        'unit_price': draft['unit_price'], 'face_total': draft['face_total'],
        'fee_total': draft['fee_total'], 'total': draft['total'],
    }
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'delivery':
            delivery = request.form.get('delivery')
            if delivery not in ('mobile', 'eticket'):
                flash('Please choose a delivery method.')
            else:
                draft = dict(session['draft']); draft['delivery'] = delivery; session['draft'] = draft
                return redirect(url_for('checkout', step='payment'))
        elif action == 'payment':
            chosen = request.form.get('method_id', '')
            if current_user.is_authenticated and chosen and chosen != 'new':
                method_id = request.form.get('method_id', type=int)
                method = PaymentMethod.query.filter_by(
                    id=method_id, user_id=current_user.id).first()
                if not method:
                    flash('Please choose a payment method.')
                    return redirect(url_for('checkout', step='payment'))
                draft = dict(session['draft']); draft.update({'card_brand': method.brand, 'card_last4': method.last4, 'method_id': method.id}); session['draft'] = draft
                return redirect(url_for('checkout', step='review'))
            brand = request.form.get('brand', 'Visa').strip()
            number = re.sub(r'\D', '', request.form.get('number', ''))
            holder = request.form.get('holder', '').strip()
            exp_month = request.form.get('exp_month', '')
            exp_year = request.form.get('exp_year', '')
            errors = []
            if len(number) < 13 or len(number) > 19:
                errors.append('Enter a valid card number.')
            if not holder:
                errors.append('Enter the name on the card.')
            try:
                if not (1 <= int(exp_month) <= 12):
                    errors.append('Expiry month must be 1-12.')
            except ValueError:
                errors.append('Expiry month must be 1-12.')
            try:
                if int(exp_year) < 2026:
                    errors.append('The card is expired.')
            except ValueError:
                errors.append('Enter a valid expiry year.')
            if errors:
                for e in errors:
                    flash(e)
                return redirect(url_for('checkout', step='payment'))
            draft = dict(session['draft']); draft.update({'card_brand': brand, 'card_last4': number[-4:], 'guest_email': request.form.get('email', '').strip()}); session['draft'] = draft
            # offer to remember the card for signed-in buyers
            if current_user.is_authenticated and request.form.get('save_card'):
                db.session.add(PaymentMethod(user_id=current_user.id, brand=brand,
                                             last4=number[-4:], exp_month=int(exp_month),
                                             exp_year=int(exp_year), holder=holder))
                db.session.commit()
            return redirect(url_for('checkout', step='review'))
        elif action == 'place':
            order = Order(
                order_no=make_order_no(event.id),
                user_id=current_user.id if current_user.is_authenticated else None,
                event_id=event.id,
                listing_id=listing.id,
                section=listing.section,
                section_desc=listing.section_desc,
                row=listing.row,
                qty=draft['qty'],
                unit_price=draft['unit_price'],
                face_total=draft['face_total'],
                fee_total=draft['fee_total'],
                total=draft['total'],
                delivery=draft.get('delivery', 'mobile'),
                card_brand=draft.get('card_brand'),
                card_last4=draft.get('card_last4'),
                guest_email=draft.get('guest_email'),
                status='confirmed',
                created_at=now_iso(),
                placed_at=now_iso(),
            )
            listing.qty_available = max(0, listing.qty_available - draft['qty'])
            db.session.add(order)
            db.session.commit()
            session.pop('draft', None)
            session.pop('draft', None)
            return redirect(url_for('order_confirmation', order_no=order.order_no))
    methods = current_user.payment_methods if current_user.is_authenticated else []
    return render_template('checkout.html', step=step, d=draft_data,
                           methods=methods, content=CONTENT['checkout'])


def make_order_no(event_id):
    seed = f"{event_id}-{now_iso()}-{os.urandom(4).hex()}"
    return re.sub(r'[^A-Z0-9]', '', hashlib.sha1(seed.encode()).hexdigest().upper())[:14]


def now_iso():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


@app.route('/order-confirmation/<order_no>')
def order_confirmation(order_no):
    order = Order.query.filter_by(order_no=order_no).first_or_404()
    return render_template('confirmation.html', order=order)


@app.route('/artist/<artist_id>')
def artist_page(artist_id):
    artist = Artist.query.get_or_404(artist_id)
    events = upcoming_by_artist(artist.id)
    return render_template('artist.html', artist=artist, events=events,
                           fav_artists=favorite_artist_ids())


@app.route('/venue/<venue_id>')
def venue_page(venue_id):
    venue = Venue.query.get_or_404(venue_id)
    events = venue.upcoming
    cats = {}
    for e in events:
        cats.setdefault(e.category, []).append(e)
    return render_template('venue.html', venue=venue, events=events, cats=cats)


@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            nxt = request.args.get('next')
            if nxt and nxt.startswith('/'):
                return redirect(nxt)
            return redirect(url_for('member'))
        flash('Invalid email or password.')
    return render_template('signin.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        first = request.form.get('first_name', '').strip()
        last = request.form.get('last_name', '').strip()
        errors = []
        if not re.match(r'[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errors.append('Enter a valid email address.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if not first or not last:
            errors.append('Enter your first and last name.')
        if User.query.filter_by(email=email).first():
            errors.append('An account with this email already exists.')
        if errors:
            for e in errors:
                flash(e)
        else:
            user = User(email=email,
                        password_hash=bcrypt.generate_password_hash(password).decode(),
                        first_name=first, last_name=last)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('member'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/member')
@login_required
def member():
    orders = (Order.query.filter_by(user_id=current_user.id)
              .order_by(Order.placed_at.desc()).all())
    return render_template('member.html', orders=orders)


@app.route('/member/orders')
@login_required
def member_orders():
    orders = (Order.query.filter_by(user_id=current_user.id)
              .order_by(Order.placed_at.desc()).all())
    return render_template('orders.html', orders=orders)


@app.route('/member/orders/<order_no>')
@login_required
def member_order(order_no):
    order = Order.query.filter_by(order_no=order_no,
                                  user_id=current_user.id).first_or_404()
    return render_template('order_detail.html', order=order)


@app.route('/member/profile', methods=['GET', 'POST'])
@login_required
def member_profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', '').strip()
        current_user.last_name = request.form.get('last_name', '').strip()
        current_user.phone = request.form.get('phone', '').strip()
        current_user.zip = request.form.get('zip', '').strip()
        if not current_user.first_name:
            flash('First name is required.')
        else:
            db.session.commit()
            flash('Profile updated.')
            return redirect(url_for('member_profile'))
    return render_template('profile.html')


@app.route('/member/payment', methods=['GET', 'POST'])
@login_required
def member_payment():
    if request.method == 'POST':
        if request.form.get('action') == 'delete':
            method_id = request.form.get('id', type=int)
            method = PaymentMethod.query.filter_by(
                id=method_id, user_id=current_user.id).first()
            if method:
                db.session.delete(method)
                db.session.commit()
                flash('Card removed.')
            return redirect(url_for('member_payment'))
        brand = request.form.get('brand', 'Visa').strip()
        number = re.sub(r'\D', '', request.form.get('number', ''))
        holder = request.form.get('holder', '').strip()
        exp_month = request.form.get('exp_month', '')
        exp_year = request.form.get('exp_year', '')
        errors = []
        if len(number) < 13 or len(number) > 19:
            errors.append('Enter a valid card number.')
        if not holder:
            errors.append('Enter the name on the card.')
        try:
            if not (1 <= int(exp_month) <= 12):
                errors.append('Expiry month must be 1-12.')
            if int(exp_year) < 2026:
                errors.append('The card is expired.')
        except ValueError:
            errors.append('Enter a valid expiry date.')
        if errors:
            for e in errors:
                flash(e)
        else:
            method = PaymentMethod(user_id=current_user.id, brand=brand,
                                   last4=number[-4:],
                                   exp_month=int(exp_month),
                                   exp_year=int(exp_year), holder=holder)
            db.session.add(method)
            db.session.commit()
            flash('Card added.')
            return redirect(url_for('member_payment'))
    return render_template('payment.html', methods=current_user.payment_methods)


@app.route('/member/favorites')
@login_required
def member_favorites():
    favs = Favorite.query.filter_by(user_id=current_user.id).all()
    events = [f.event for f in favs if f.event]
    artists = [f.artist for f in favs if f.artist]
    return render_template('favorites.html', events=events, artists=artists)


@app.route('/favorites/toggle', methods=['POST'])
def favorites_toggle():
    kind = request.form.get('kind')
    ref = request.form.get('ref')
    if not current_user.is_authenticated:
        flash('Sign in to save your favorites.')
        return redirect(url_for('signin', next=request.form.get('next', '/')))
    existing = None
    if kind == 'event':
        existing = Favorite.query.filter_by(user_id=current_user.id,
                                            event_id=ref).first()
    elif kind == 'artist':
        existing = Favorite.query.filter_by(user_id=current_user.id,
                                             artist_id=ref).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Removed from favorites.')
    else:
        fav = Favorite(user_id=current_user.id,
                       event_id=ref if kind == 'event' else None,
                       artist_id=ref if kind == 'artist' else None,
                       created_at=now_iso())
        db.session.add(fav)
        db.session.commit()
        flash('Saved to favorites.')
    nxt = request.form.get('next', '/')
    if not nxt.startswith('/'):
        nxt = '/'
    return redirect(nxt)


@app.route('/giftcards', methods=['GET', 'POST'])
def giftcards():
    balance = None
    code = ''
    if request.method == 'POST':
        action = request.form.get('action', 'buy')
        if action == 'buy':
            amount = parse_money(request.form.get('amount'))
            email = request.form.get('email', '').strip()
            errors = []
            if not amount or amount < 25 or amount > 1000:
                errors.append('Choose an amount between $25 and $1000.')
            if not re.match(r'[^@\s]+@[^@\s]+\.[^@\s]+$', email or ''):
                errors.append('Enter a valid recipient email.')
            if errors:
                for e in errors:
                    flash(e)
            else:
                flash(f'Gift card for ${amount:.0f} will be emailed to {email}.')
                return redirect(url_for('giftcards'))
        else:
            code = request.form.get('code', '').strip().upper()
            digest = hashlib.sha1(("gc-" + code).encode()).hexdigest()
            value = int(digest[:8], 16) % 9
            balance = [25, 50, 75, 100, 125, 150, 200, 500, 1000][value]
    return render_template('giftcards.html', gc=CONTENT['gift_cards'],
                           balance=balance, code=code)


@app.route('/help')
def help_index():
    return render_template('help_index.html', topics=CONTENT['help_topics'])


@app.route('/help/<slug>')
def help_article(slug):
    for topic in CONTENT['help_topics']:
        if topic['slug'] == slug:
            return render_template('help_article.html', topic=topic,
                                   topics=CONTENT['help_topics'])
    abort(404)


@app.route('/help/contact')
def help_contact():
    return render_template('help_article.html', topic={
        'slug': 'contact-us', 'title': 'Contact Us',
        'body': CONTENT['help_topics'][-1]['body']},
        topics=CONTENT['help_topics'])


@app.route('/legal/terms')
def legal_terms():
    return render_template('legal.html', title='Terms of Use',
        body='By using this site you agree to our Terms of Use. All ticket sales are final except where prohibited by law. Ticket limits are enforced per event and per household; orders that exceed published limits may be cancelled without notice.')


@app.route('/legal/privacy')
def legal_privacy():
    return render_template('legal.html', title='Privacy Statement',
        body='We collect the information needed to process your ticket orders, including your name, email address, billing address and payment details. We use it to deliver your tickets, provide customer service and, with your consent, to send you event recommendations and presale offers.')


@app.route('/legal/dnsmpi')
def legal_dnsmpi():
    return render_template('legal.html', title='Do Not Sell or Share My Personal Information',
        body='Residents of certain states have the right to direct us not to sell or share their personal information, or to limit the use of sensitive personal information. Submit a request and we will process it within the statutory time frame.')


@app.route('/sell')
def sell():
    return render_template('sell.html')


@app.route('/vip')
def vip():
    return render_template('vip.html')


@app.route('/travel')
def travel():
    return render_template('travel.html')


@app.route('/_health')
def health():
    """End-to-end health probe: seed present, catalog browsable, routes sane."""
    try:
        counts = {
            'events': Event.query.count(),
            'artists': Artist.query.count(),
            'venues': Venue.query.count(),
            'listings': TicketListing.query.count(),
            'users': User.query.count(),
            'orders': Order.query.count(),
        }
        ok = (counts['events'] > 500 and counts['artists'] > 100 and
              counts['venues'] > 100 and counts['listings'] > 20000 and
              counts['users'] >= 4)
        return jsonify({'ok': ok, 'site': 'ticketmaster', 'counts': counts}), (200 if ok else 500)
    except Exception as error:  # pragma: no cover - probe must never crash
        return jsonify({'ok': False, 'site': 'ticketmaster', 'error': str(error)}), 500


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


# -------------------------------------------------------------- boot / seed --

def seed_database():
    if Event.query.count() > 0:
        return
    from seed_data import build_seed
    build_seed(db)


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    from seed_data import build_benchmark_users
    build_benchmark_users(db)


with app.app_context():
    db.create_all()
    seed_content()
    seed_database()
    seed_benchmark_users()


def main():
    """Standalone entry: build instance/ticketmaster.db from scratch (idempotent)."""
    with app.app_context():
        db.create_all()
        seed_content()
        seed_database()
        seed_benchmark_users()
    print('seeded')


if __name__ == '__main__':
    main()
