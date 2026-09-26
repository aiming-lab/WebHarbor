#!/usr/bin/env python3
"""RE/MAX mirror — Flask application.

Mirrors https://www.remax.com/ (property search with filters, listing detail
pages with galleries and open-house schedules, agent and office finders with
detail pages, rentals, new listings, open-house search, the advice/blog hub,
account area with favorites and saved searches, contact forms, newsletter and
listing-alert signups) using real data captured from the upstream site on
2026-09-24.

All content rows come from the tracked source_data_*.json snapshots; the
seed database is rebuilt deterministically at image build time (see
seed_data.py).
"""
import json
import os
import re
import secrets
from datetime import date, datetime

from urllib.parse import quote as url_quote

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("REMAX_SECRET_KEY") or "webharbor-remax-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'REMAX_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 're_max.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to access your account.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

# The mirror is a snapshot of the upstream site taken on 2026-09-24.
MIRROR_TODAY = date(2026, 9, 24)

HOME_TYPES = ['House', 'Townhouse', 'Condo', 'Mobile', 'Multi-Family', 'Land', 'Farm']
SORT_OPTIONS = {
    'newest': 'Newest First',
    'oldest': 'Oldest First',
    'price_desc': 'Price (High to Low)',
    'price_asc': 'Price (Low to High)',
}
STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire',
    'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina',
    'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania',
    'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee',
    'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington',
    'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
}


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------- models --

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(80), default='')
    last_name = db.Column(db.String(80), default='')
    display_name = db.Column(db.String(120), default='')
    password_hash = db.Column(db.String(128), nullable=False)
    buyer_type = db.Column(db.String(40))
    phone = db.Column(db.String(30))
    created_at = db.Column(db.String(30))
    favorites = db.relationship('Favorite', backref='user', lazy='dynamic',
                                cascade='all, delete-orphan')
    saved_searches = db.relationship('SavedSearch', backref='user', lazy='dynamic',
                                     cascade='all, delete-orphan')
    inquiries = db.relationship('Inquiry', backref='user', lazy='dynamic',
                                cascade='all, delete-orphan')

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)


class Listing(db.Model):
    __tablename__ = 'listings'
    id = db.Column(db.Integer, primary_key=True)
    mls = db.Column(db.String(30), unique=True)
    slug = db.Column(db.String(200))
    price = db.Column(db.Integer)
    beds = db.Column(db.Integer)
    baths = db.Column(db.Integer)
    sqft = db.Column(db.Integer)
    home_type = db.Column(db.String(30))
    prop_sub_type = db.Column(db.String(60))
    street = db.Column(db.String(200))
    city = db.Column(db.String(80))
    state = db.Column(db.String(4))
    zip = db.Column(db.String(12))
    status = db.Column(db.String(20), default='active')
    badges = db.Column(db.Text)          # JSON list
    broker = db.Column(db.String(160))
    agent = db.Column(db.String(120))
    agent_phone = db.Column(db.String(30))
    photo = db.Column(db.String(200))
    gallery = db.Column(db.Text)         # JSON list
    description = db.Column(db.Text)
    quick_overview = db.Column(db.Text)  # JSON list
    sections = db.Column(db.Text)        # JSON dict
    open_houses = db.Column(db.Text)     # JSON list
    presented_by = db.Column(db.Text)    # JSON dict
    listed_by_agent = db.Column(db.String(120))
    listed_by_office = db.Column(db.String(160))
    updated_label = db.Column(db.String(120))
    listed_date = db.Column(db.String(12))
    is_luxury = db.Column(db.Boolean, default=False)
    has_detail = db.Column(db.Boolean, default=False)

    def badge_list(self):
        try:
            return json.loads(self.badges or '[]')
        except Exception:
            return []

    def gallery_list(self):
        try:
            g = json.loads(self.gallery or '[]')
        except Exception:
            g = []
        return g if g else ([self.photo] if self.photo else [])

    def overview_list(self):
        try:
            return json.loads(self.quick_overview or '[]')
        except Exception:
            return []

    def sections_dict(self):
        try:
            return json.loads(self.sections or '{}')
        except Exception:
            return {}

    def open_house_list(self):
        try:
            return json.loads(self.open_houses or '[]')
        except Exception:
            return []

    def presented_by_dict(self):
        try:
            return json.loads(self.presented_by or 'null')
        except Exception:
            return None

    def price_str(self):
        return f"${self.price:,.0f}" if self.price else '—'

    def status_label(self):
        return {
            'active': 'ACTIVE', 'pending': 'PENDING', 'contingent': 'CONTINGENT',
            'coming_soon': 'COMING SOON',
        }.get(self.status, self.status.upper())

    def city_slug(self):
        return re.sub(r'[^a-z0-9]+', '-', self.city.lower()).strip('-')

    def detail_url(self):
        return url_for('listing_detail', state=self.state.lower(),
                       city=self.city_slug(), slug=self.slug, listing_id=self.id)

    def city_url(self):
        return url_for('city_srp', state=self.state.lower(), city_slug=self.city_slug())


class Rental(db.Model):
    __tablename__ = 'rentals'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200))
    street = db.Column(db.String(200))
    city = db.Column(db.String(80))
    state = db.Column(db.String(4))
    zip = db.Column(db.String(12))
    price = db.Column(db.Integer)
    beds = db.Column(db.Integer)
    baths = db.Column(db.Integer)
    sqft = db.Column(db.Integer)
    date_added = db.Column(db.String(30))
    description = db.Column(db.Text)
    photo = db.Column(db.String(200))
    gallery = db.Column(db.Text)
    quick_overview = db.Column(db.Text)
    presented_by = db.Column(db.Text)
    listed_by_agent = db.Column(db.String(120))
    listed_by_office = db.Column(db.String(160))
    has_detail = db.Column(db.Boolean, default=False)

    def gallery_list(self):
        try:
            g = json.loads(self.gallery or '[]')
        except Exception:
            g = []
        return g if g else ([self.photo] if self.photo else [])

    def overview_list(self):
        try:
            return json.loads(self.quick_overview or '[]')
        except Exception:
            return []

    def presented_by_dict(self):
        try:
            return json.loads(self.presented_by or 'null')
        except Exception:
            return None

    def price_str(self):
        return f"${self.price:,.0f}" if self.price else '—'

    def city_slug(self):
        return re.sub(r'[^a-z0-9]+', '-', self.city.lower()).strip('-')

    def detail_url(self):
        return url_for('rental_detail', slug=self.slug, rental_id=self.id)


class Agent(db.Model):
    __tablename__ = 'agents'
    id = db.Column(db.Integer, primary_key=True)
    remax_id = db.Column(db.String(30), unique=True)
    slug = db.Column(db.String(200))
    name = db.Column(db.String(120))
    title = db.Column(db.String(120))
    licensed = db.Column(db.String(80))
    city = db.Column(db.String(80))
    state = db.Column(db.String(4))
    office_name = db.Column(db.String(160))
    phone = db.Column(db.String(30))
    photo = db.Column(db.String(200))
    about = db.Column(db.Text)
    hobbies = db.Column(db.Text)
    civic = db.Column(db.Text)
    years = db.Column(db.Integer)
    license_numbers = db.Column(db.Text)
    languages = db.Column(db.Text)
    specialties = db.Column(db.Text)
    designations = db.Column(db.Text)
    website = db.Column(db.String(200))
    office_address = db.Column(db.String(200))

    def _list(self, field):
        try:
            return json.loads(getattr(self, field) or '[]')
        except Exception:
            return []

    def hobbies_list(self):
        return self._list('hobbies')

    def civic_list(self):
        return self._list('civic')

    def languages_list(self):
        return self._list('languages')

    def specialties_list(self):
        return self._list('specialties')

    def designations_list(self):
        return self._list('designations')

    def license_list(self):
        return self._list('license_numbers')

    def detail_url(self):
        return url_for('agent_detail', slug=self.slug, remax_id=self.remax_id)


class Office(db.Model):
    __tablename__ = 'offices'
    id = db.Column(db.Integer, primary_key=True)
    remax_id = db.Column(db.String(30), unique=True)
    slug = db.Column(db.String(200))
    name = db.Column(db.String(160))
    address = db.Column(db.String(240))
    city = db.Column(db.String(80))
    state = db.Column(db.String(4))
    phone = db.Column(db.String(30))
    photo = db.Column(db.String(200))
    about = db.Column(db.Text)
    website = db.Column(db.String(200))
    service_areas = db.Column(db.Text)
    languages = db.Column(db.Text)
    specialties = db.Column(db.Text)
    has_detail = db.Column(db.Boolean, default=False)

    def _list(self, field):
        try:
            return json.loads(getattr(self, field) or '[]')
        except Exception:
            return []

    def service_areas_list(self):
        return self._list('service_areas')

    def languages_list(self):
        return self._list('languages')

    def specialties_list(self):
        return self._list('specialties')

    def detail_url(self):
        return url_for('office_detail', city=(self.city or 'usa').lower().replace(' ', '-'),
                       slug=self.slug, remax_id=self.remax_id)


class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True)
    title = db.Column(db.String(240))
    image = db.Column(db.String(200))
    text = db.Column(db.Text)

    def excerpt(self, n=180):
        t = re.sub(r'\s+', ' ', (self.text or '')).strip()
        return t[:n] + '…' if len(t) > n else t


class Favorite(db.Model):
    __tablename__ = 'favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    created_at = db.Column(db.String(30))
    listing = db.relationship('Listing')


class SavedSearch(db.Model):
    __tablename__ = 'saved_searches'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(120))
    city = db.Column(db.String(80))
    state = db.Column(db.String(4))
    home_type = db.Column(db.String(30))
    min_price = db.Column(db.Integer)
    max_price = db.Column(db.Integer)
    beds = db.Column(db.Integer)
    created_at = db.Column(db.String(30))

    def url(self):
        qs = []
        if self.home_type:
            qs.append(f"home_type={url_quote(self.home_type)}")
        if self.min_price:
            qs.append(f"price_min={self.min_price}")
        if self.max_price:
            qs.append(f"price_max={self.max_price}")
        if self.beds:
            qs.append(f"beds={self.beds}")
        base = url_for('city_srp', state=(self.state or '').lower(),
                       city=re.sub(r'[^a-z0-9]+', '-', (self.city or '').lower()).strip('-'))
        return base + ('?' + '&'.join(qs) if qs else '')


class Inquiry(db.Model):
    __tablename__ = 'inquiries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'))
    rental_id = db.Column(db.Integer, db.ForeignKey('rentals.id'))
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))
    office_id = db.Column(db.Integer, db.ForeignKey('offices.id'))
    kind = db.Column(db.String(30))
    name = db.Column(db.String(120))
    email = db.Column(db.String(160))
    phone = db.Column(db.String(30))
    message = db.Column(db.Text)
    preferred_date = db.Column(db.String(40))
    created_at = db.Column(db.String(30))
    listing = db.relationship('Listing')
    rental = db.relationship('Rental')
    agent = db.relationship('Agent')
    office = db.relationship('Office')


class NewsletterSubscriber(db.Model):
    __tablename__ = 'newsletter_subscribers'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), nullable=False)
    buyer_type = db.Column(db.String(40))
    created_at = db.Column(db.String(30))


class ListingAlert(db.Model):
    __tablename__ = 'listing_alerts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    email = db.Column(db.String(160))
    city = db.Column(db.String(80))
    state = db.Column(db.String(4))
    created_at = db.Column(db.String(30))


# ---------------------------------------------------------------- helpers --

STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or',
              'is', 'it', 'by', 'with', 'near', 'me'}


def tokenize(query):
    return [t for t in re.split(r'\W+', (query or '').lower())
            if t and t not in STOP_WORDS and len(t) > 1]


def now_stamp():
    return MIRROR_TODAY.strftime('%Y-%m-%d %H:%M')


def _popular_cities_with_inventory():
    """Footer 'Popular Cities' restricted to cities the mirror actually has
    listings for, so every footer link resolves (upstream lists some cities,
    e.g. Tehachapi and Myrtle Beach, whose inventory is outside this snapshot)."""
    if 'popular' not in _CONTENT_CACHE:
        popular = []
        for city, st in _load_content().get('popular_cities', []):
            hit = (Listing.query
                   .filter(Listing.state == st.upper(),
                           db.func.lower(Listing.city) == city.lower())
                   .first())
            if hit:
                popular.append((city, st))
        _CONTENT_CACHE['popular'] = popular
    return _CONTENT_CACHE['popular']


@app.context_processor
def inject_globals():
    return {
        'STATES': STATES,
        'sort_options': SORT_OPTIONS,
        'content_popular_cities': _popular_cities_with_inventory(),
    }


def format_money(v):
    return f"${v:,.0f}" if v else ''


def city_cities(state):
    """Cities with listings in a state, ordered by count."""
    rows = (db.session.query(Listing.city, db.func.count(Listing.id))
            .filter(Listing.state == state.upper())
            .group_by(Listing.city)
            .order_by(db.func.count(Listing.id).desc(), Listing.city)
            .all())
    return rows


def state_listing_count(state):
    return Listing.query.filter_by(state=state.upper()).count()


def apply_filters(query, args):
    home_type = args.get('home_type', type=str)
    price_min = args.get('price_min', type=int)
    price_max = args.get('price_max', type=int)
    beds = args.get('beds', type=int)
    baths = args.get('baths', type=int)
    status = args.get('status', type=str)
    open_only = args.get('open_house', type=str)
    if home_type:
        query = query.filter(Listing.home_type == home_type)
    if price_min:
        query = query.filter(Listing.price >= price_min)
    if price_max:
        query = query.filter(Listing.price <= price_max)
    if beds:
        query = query.filter(Listing.beds >= beds)
    if baths:
        query = query.filter(Listing.baths >= baths)
    if status in ('active', 'pending', 'coming_soon', 'contingent'):
        query = query.filter(Listing.status == status)
    if open_only in ('1', 'true'):
        query = query.filter(Listing.open_houses != '[]')
    return query


def sort_listings(query, sort):
    if sort == 'oldest':
        return query.order_by(Listing.listed_date.asc(), Listing.id.asc())
    if sort == 'price_desc':
        return query.order_by(Listing.price.desc(), Listing.id.asc())
    if sort == 'price_asc':
        return query.order_by(Listing.price.asc(), Listing.id.asc())
    return query.order_by(Listing.listed_date.desc(), Listing.id.desc())


# ------------------------------------------------------------------ routes --

@app.route('/_health')
def health():
    try:
        n_listings = Listing.query.count()
        n_rentals = Rental.query.count()
        n_agents = Agent.query.count()
        n_offices = Office.query.count()
        n_posts = BlogPost.query.count()
        ok = n_listings > 300 and n_rentals > 50 and n_agents >= 20 and n_offices >= 15 and n_posts >= 15
        return {'ok': ok, 'site': 're_max', 'listings': n_listings,
                'rentals': n_rentals, 'agents': n_agents, 'offices': n_offices,
                'blog_posts': n_posts}
    except Exception as exc:  # pragma: no cover
        return {'ok': False, 'error': str(exc)}, 500


@app.route('/')
def index():
    near = (Listing.query.filter_by(status='active')
            .order_by(Listing.listed_date.desc(), Listing.id.desc()).limit(8).all())
    featured_office = None
    if near:
        pb = near[0].presented_by_dict()
        if pb:
            featured_office = pb
    posts = BlogPost.query.order_by(BlogPost.id).limit(3).all()
    content = _load_content()
    return render_template('index.html', near=near, posts=posts,
                           featured_office=featured_office, content=content)


_CONTENT_CACHE = {}


def _load_content():
    if 'content' not in _CONTENT_CACHE:
        path = os.path.join(BASE_DIR, 'source_data_content.json')
        try:
            with open(path, encoding='utf-8') as fh:
                _CONTENT_CACHE['content'] = json.load(fh)
        except OSError:
            _CONTENT_CACHE['content'] = {}
    return _CONTENT_CACHE['content']


@app.route('/homes-for-sale-united-states')
@app.route('/homes-for-sale')
def state_directory():
    states = (db.session.query(Listing.state, db.func.count(Listing.id))
              .group_by(Listing.state)
              .order_by(Listing.state).all())
    return render_template('state_directory.html', states=states,
                           title='Find Homes in the United States',
                           heading='Find Homes in the United States',
                           sub='Find homes in the United States by searching across popular counties, cities, zip codes, and neighborhoods.',
                           mode='sale')


@app.route('/homes-for-rent')
def rent_directory():
    states = (db.session.query(Rental.state, db.func.count(Rental.id))
              .group_by(Rental.state)
              .order_by(Rental.state).all())
    return render_template('state_directory.html', states=states,
                           title='Find Homes for Rent',
                           heading='Find Homes for Rent',
                           sub='Find rental homes by searching across popular cities and states.',
                           mode='rent')


@app.route('/homes-for-sale/<state>')
def state_page(state):
    st = state.upper()
    if st not in STATES:
        abort(404)
    cities = city_cities(st)
    if not cities:
        abort(404)
    return render_template('state_page.html', state=st, state_name=STATES[st],
                           cities=cities, total=state_listing_count(st))


@app.route('/<state>/<city>-real-estate')
def city_srp(state, city):
    return _render_city_srp(state, city)


@app.route('/homes-for-sale/<state>/<city>/city/<int:city_id>')
def city_srp_id(state, city, city_id):
    return _render_city_srp(state, city)


def _render_city_srp(state, city):
    st = state.upper()
    q = Listing.query.filter(Listing.state == st)
    city_name = city.replace('-', ' ').strip()
    exact = q.filter(db.func.lower(Listing.city) == city_name.lower())
    n = exact.count()
    if not n:
        # fuzzy: match any city containing the slug words
        like = f"%{city_name.replace('-', ' ')}%"
        exact = q.filter(db.func.lower(Listing.city).like(like))
        n = exact.count()
    if not n:
        abort(404)
    city_display = exact.first().city
    args = request.args
    sort = args.get('sort', 'newest', type=str)
    if sort not in SORT_OPTIONS:
        sort = 'newest'
    filtered = apply_filters(exact, args)
    total = filtered.count()
    listings = sort_listings(filtered, sort).limit(60).all()
    content = _load_content()
    sponsor = None
    if listings:
        pb = listings[0].presented_by_dict()
        if pb:
            sponsor = pb
    return render_template('srp.html', listings=listings, total=total,
                           city=city_display, state=st, state_name=STATES.get(st, st),
                           sort=sort, sort_label=SORT_OPTIONS[sort],
                           home_types=HOME_TYPES, args=args, sponsor=sponsor,
                           content=content)


@app.route('/search')
def global_search():
    query = request.args.get('q', '').strip()
    results = {'listings': [], 'agents': [], 'offices': [], 'posts': []}
    if query:
        tokens = tokenize(query)
        if tokens:
            listings = Listing.query.all()
            scored = []
            for l in listings:
                text = ' '.join([l.street or '', l.city or '', l.state or '',
                                 l.zip or '', l.mls or '', l.home_type or '',
                                 l.broker or '', l.agent or '',
                                 (l.description or '')[:400]]).lower()
                score = sum(1 for t in tokens if t in text)
                if score:
                    scored.append((score, l))
            scored.sort(key=lambda x: (-x[0], x[1].id))
            results['listings'] = [l for _, l in scored[:24]]
            agents = Agent.query.all()
            asc = []
            for a in agents:
                text = ' '.join([a.name or '', a.office_name or '', a.city or '',
                                 a.title or '', ' '.join(a.specialties_list()),
                                 ' '.join(a.languages_list())]).lower()
                score = sum(1 for t in tokens if t in text)
                if score:
                    asc.append((score, a))
            asc.sort(key=lambda x: (-x[0], x[1].id))
            results['agents'] = [a for _, a in asc[:12]]
            offices = Office.query.all()
            osc = []
            for o in offices:
                text = ' '.join([o.name or '', o.city or '', o.state or '',
                                 ' '.join(o.specialties_list()),
                                 ' '.join(o.service_areas_list())]).lower()
                score = sum(1 for t in tokens if t in text)
                if score:
                    osc.append((score, o))
            osc.sort(key=lambda x: (-x[0], x[1].id))
            results['offices'] = [o for _, o in osc[:12]]
            posts = BlogPost.query.all()
            psc = []
            for p in posts:
                text = ((p.title or '') + ' ' + (p.text or '')[:600]).lower()
                score = sum(1 for t in tokens if t in text)
                if score:
                    psc.append((score, p))
            psc.sort(key=lambda x: (-x[0], x[1].id))
            results['posts'] = [p for _, p in psc[:10]]
    return render_template('search.html', query=query, results=results)


@app.route('/<state>/<city>/home-details/<slug>/<int:listing_id>')
def listing_detail(state, city, slug, listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing:
        abort(404)
    similar = (Listing.query.filter(Listing.city == listing.city,
                                     Listing.state == listing.state,
                                     Listing.id != listing.id)
               .order_by(Listing.price).limit(4).all())
    is_favorite = False
    if current_user.is_authenticated:
        is_favorite = Favorite.query.filter_by(user_id=current_user.id,
                                               listing_id=listing.id).first() is not None
    return render_template('ldp.html', l=listing, similar=similar,
                           is_favorite=is_favorite,
                           mirror_today=MIRROR_TODAY)


@app.route('/rental-details/<slug>/<int:rental_id>')
def rental_detail(slug, rental_id):
    rental = db.session.get(Rental, rental_id)
    if not rental:
        abort(404)
    return render_template('rental_detail.html', r=rental)


@app.route('/new-listings')
def new_listings():
    listings = (Listing.query.order_by(Listing.listed_date.desc(), Listing.id.desc())
               .limit(40).all())
    return render_template('new_listings.html', listings=listings)


@app.route('/new-rentals')
def rentals_page():
    rentals = Rental.query.order_by(Rental.id).all()
    return render_template('rentals.html', rentals=rentals)


@app.route('/usa/en/real-estate/united-states-open-houses')
def open_house_directory():
    rows = (db.session.query(Listing.state, db.func.count(Listing.id))
            .filter(Listing.open_houses != '[]')
            .group_by(Listing.state).order_by(Listing.state).all())
    return render_template('open_house_directory.html', states=rows,
                           title='Search for Open Houses by State',
                           heading='Search for Open Houses by State',
                           sub='Find open houses in the U.S. by searching across popular counties, cities, zip codes and neighborhoods.')


@app.route('/open-houses/<state>')
def open_houses_state(state):
    st = state.upper()
    q = (Listing.query.filter(Listing.state == st, Listing.open_houses != '[]')
         .order_by(Listing.price))
    listings = q.all()
    if not listings:
        abort(404)
    return render_template('open_houses.html', listings=listings,
                           state=st, state_name=STATES.get(st, st))


@app.route('/real-estate-agents')
def agents_page():
    args = request.args
    q = Agent.query
    language = args.get('language', type=str)
    specialty = args.get('specialty', type=str)
    years = args.get('years', type=int)
    licensed = args.get('licensed', type=str)
    sort = args.get('sort', '', type=str)
    if language:
        q = q.filter(Agent.languages.like(f'%"{language}"%'))
    if specialty:
        q = q.filter(Agent.specialties.like(f'%"{specialty}"%'))
    if years:
        q = q.filter(Agent.years >= years)
    if licensed:
        q = q.filter(Agent.licensed.like(f'%{licensed}%'))
    if sort == 'name':
        agents = q.order_by(Agent.name).all()
    elif sort == 'experience':
        agents = q.order_by(Agent.years.desc()).all()
    else:
        agents = q.order_by(Agent.id).all()
    all_specialties = sorted({s for a in Agent.query.all() for s in a.specialties_list()})
    all_languages = sorted({s for a in Agent.query.all() for s in a.languages_list()})
    return render_template('agents.html', agents=agents, total=Agent.query.count(),
                           all_specialties=all_specialties,
                           all_languages=all_languages, args=args)


@app.route('/usa/en/real-estate-agents/<slug>/<remax_id>')
def agent_detail(slug, remax_id):
    agent = Agent.query.filter_by(remax_id=remax_id).first()
    if not agent:
        abort(404)
    office = Office.query.filter_by(name=agent.office_name).first()
    return render_template('agent_detail.html', a=agent, office=office)


@app.route('/real-estate-offices')
def offices_page():
    args = request.args
    q = Office.query
    language = args.get('language', type=str)
    specialty = args.get('specialty', type=str)
    sort = args.get('sort', '', type=str)
    if language:
        q = q.filter(Office.languages.like(f'%"{language}"%'))
    if specialty:
        q = q.filter(Office.specialties.like(f'%"{specialty}"%'))
    if sort == 'name':
        offices = q.order_by(Office.name).all()
    else:
        offices = q.order_by(Office.id).all()
    all_specialties = sorted({s for o in Office.query.all() for s in o.specialties_list()})
    all_languages = sorted({s for o in Office.query.all() for s in o.languages_list()})
    return render_template('offices.html', offices=offices, total=Office.query.count(),
                           all_specialties=all_specialties,
                           all_languages=all_languages, args=args)


@app.route('/usa/en/residential/office/<city>/<slug>/<remax_id>')
def office_detail(city, slug, remax_id):
    office = Office.query.filter_by(remax_id=remax_id).first()
    if not office:
        abort(404)
    office_agents = Agent.query.filter_by(office_name=office.name).all()
    office_listings = (Listing.query.filter(Listing.broker.like(f'%{office.name.replace("REMAX", "RE/MAX")}%'))
                       .limit(6).all())
    if not office_listings:
        office_listings = (Listing.query.filter_by(state=office.state)
                           .order_by(Listing.price).limit(6).all())
    return render_template('office_detail.html', o=office, agents=office_agents,
                           listings=office_listings)


@app.route('/luxury')
def luxury():
    listings = (Listing.query.filter_by(is_luxury=True)
                .order_by(Listing.price.desc()).all())
    return render_template('luxury.html', listings=listings)


@app.route('/usa/en/lifestyles/golf')
def golf_lifestyles():
    listings = (Listing.query.filter(Listing.price >= 500000)
               .order_by(Listing.price.desc()).limit(12).all())
    return render_template('golf.html', listings=listings)


@app.route('/advice')
def advice():
    posts = BlogPost.query.order_by(BlogPost.id).all()
    content = _load_content()
    return render_template('advice.html', posts=posts, content=content)


@app.route('/advice/<slug>')
def advice_post(slug):
    post = BlogPost.query.filter_by(slug=slug).first_or_404()
    others = BlogPost.query.filter(BlogPost.id != post.id).limit(4).all()
    return render_template('article.html', p=post, others=others)


# ------------------------------------------------------------------- auth --

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and user.check_password(password):
            login_user(user)
            nxt = request.args.get('next')
            if nxt and nxt.startswith('/'):
                return redirect(nxt)
            return redirect(url_for('account'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    if request.method == 'POST':
        first = request.form.get('first_name', '').strip()
        last = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if not (first and last and email and password):
            flash('All fields are required.', 'error')
        elif '@' not in email or '.' not in email:
            flash('Please enter a valid email address.', 'error')
        elif len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif User.query.filter(db.func.lower(User.email) == email).first():
            flash('An account with that email already exists.', 'error')
        else:
            username = re.sub(r'[^a-z0-9_]+', '_', email.split('@')[0].lower())
            while User.query.filter_by(username=username).first():
                username += str(secrets.randbelow(90) + 10)
            user = User(username=username, email=email, first_name=first,
                        last_name=last, display_name=f'{first} {last}',
                        buyer_type=request.form.get('buyer_type') or None,
                        created_at=now_stamp())
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Welcome to RE/MAX! Your account has been created.', 'success')
            return redirect(url_for('account'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/account')
@login_required
def account():
    favs = current_user.favorites.order_by(Favorite.id.desc()).all()
    searches = current_user.saved_searches.order_by(SavedSearch.id.desc()).all()
    inqs = current_user.inquiries.order_by(Inquiry.id.desc()).all()
    alerts = ListingAlert.query.filter_by(user_id=current_user.id).all()
    return render_template('account.html', favorites=favs, searches=searches,
                           inquiries=inqs, alerts=alerts)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    if request.method == 'POST':
        first = request.form.get('first_name', '').strip()
        last = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        buyer_type = request.form.get('buyer_type', '').strip()
        if not (first and last):
            flash('First and last name are required.', 'error')
        else:
            current_user.first_name = first
            current_user.last_name = last
            current_user.display_name = f'{first} {last}'
            current_user.phone = phone or None
            current_user.buyer_type = buyer_type or None
            db.session.commit()
            flash('Your profile has been updated.', 'success')
            return redirect(url_for('account'))
    return render_template('account_edit.html')


@app.route('/favorites')
@login_required
def favorites_page():
    favs = current_user.favorites.order_by(Favorite.id.desc()).all()
    return render_template('favorites.html', favorites=favs)


@app.route('/favorite/<int:listing_id>/toggle', methods=['POST'])
@login_required
def favorite_toggle(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing:
        abort(404)
    fav = Favorite.query.filter_by(user_id=current_user.id, listing_id=listing_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash('Removed from your favorites.', 'success')
    else:
        db.session.add(Favorite(user_id=current_user.id, listing_id=listing_id,
                                 created_at=now_stamp()))
        db.session.commit()
        flash('Saved to your favorites.', 'success')
    return redirect(request.form.get('next') or listing.detail_url())


@app.route('/saved-searches/add', methods=['POST'])
@login_required
def saved_search_add():
    name = request.form.get('name', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip().upper()
    if not (city and state):
        flash('City and state are required to save a search.', 'error')
    else:
        db.session.add(SavedSearch(
            user_id=current_user.id, name=name or f'{city}, {state}',
            city=city, state=state,
            home_type=request.form.get('home_type') or None,
            min_price=request.form.get('min_price', type=int),
            max_price=request.form.get('max_price', type=int),
            beds=request.form.get('beds', type=int),
            created_at=now_stamp()))
        db.session.commit()
        flash('Search saved to your account.', 'success')
    return redirect(request.form.get('next') or url_for('account'))


@app.route('/saved-searches/<int:sid>/delete', methods=['POST'])
@login_required
def saved_search_delete(sid):
    s = SavedSearch.query.get_or_404(sid)
    if s.user_id != current_user.id:
        abort(403)
    db.session.delete(s)
    db.session.commit()
    flash('Saved search removed.', 'success')
    return redirect(url_for('account'))


@app.route('/favorite/<int:fid>/remove', methods=['POST'])
@login_required
def favorite_remove(fid):
    f = Favorite.query.get_or_404(fid)
    if f.user_id != current_user.id:
        abort(403)
    db.session.delete(f)
    db.session.commit()
    flash('Removed from your favorites.', 'success')
    return redirect(url_for('favorites_page'))


# ------------------------------------------------------------------ forms --

@app.route('/contact/agent', methods=['POST'])
def contact_agent():
    agent_id = request.form.get('agent_id', type=int)
    agent = db.session.get(Agent, agent_id) if agent_id else None
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    message = request.form.get('message', '').strip()
    if not agent:
        flash('Select an agent to contact.', 'error')
        return redirect(request.form.get('next') or url_for('agents_page'))
    if not (name and email and '@' in email):
        flash('Please provide your name and a valid email address.', 'error')
        return redirect(request.form.get('next') or agent.detail_url())
    db.session.add(Inquiry(
        user_id=current_user.id if current_user.is_authenticated else None,
        agent_id=agent.id, kind='agent', name=name, email=email,
        phone=request.form.get('phone', '').strip() or None,
        message=message or None, created_at=now_stamp()))
    db.session.commit()
    flash(f'Thank you! Your message has been sent to {agent.name}. They will get back to you shortly.', 'success')
    return redirect(request.form.get('next') or agent.detail_url())


@app.route('/contact/listing', methods=['POST'])
def contact_listing():
    listing_id = request.form.get('listing_id', type=int)
    rental_id = request.form.get('rental_id', type=int)
    kind = request.form.get('kind', 'contact')
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    preferred = request.form.get('preferred_date', '').strip()
    listing = db.session.get(Listing, listing_id) if listing_id else None
    rental = db.session.get(Rental, rental_id) if rental_id else None
    if not listing and not rental:
        flash('Select a property first.', 'error')
        return redirect(request.form.get('next') or url_for('index'))
    if not (name and email and '@' in email):
        flash('Please provide your name and a valid email address.', 'error')
        return redirect(request.form.get('next') or (listing.detail_url() if listing else rental.detail_url()))
    db.session.add(Inquiry(
        user_id=current_user.id if current_user.is_authenticated else None,
        listing_id=listing.id if listing else None,
        rental_id=rental.id if rental else None,
        kind='tour' if kind == 'tour' else 'listing',
        name=name, email=email,
        phone=request.form.get('phone', '').strip() or None,
        message=request.form.get('message', '').strip() or None,
        preferred_date=preferred or None, created_at=now_stamp()))
    db.session.commit()
    if kind == 'tour':
        flash('Tour request sent! A RE/MAX agent will confirm your showing time shortly.', 'success')
    else:
        flash('Thank you! A RE/MAX agent will contact you about this property shortly.', 'success')
    return redirect(request.form.get('next') or (listing.detail_url() if listing else rental.detail_url()))


@app.route('/contact/office', methods=['POST'])
def contact_office():
    office_id = request.form.get('office_id', type=int)
    office = db.session.get(Office, office_id) if office_id else None
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    if not office:
        flash('Select an office to contact.', 'error')
        return redirect(request.form.get('next') or url_for('offices_page'))
    if not (name and email and '@' in email):
        flash('Please provide your name and a valid email address.', 'error')
        return redirect(request.form.get('next') or office.detail_url())
    db.session.add(Inquiry(
        user_id=current_user.id if current_user.is_authenticated else None,
        office_id=office.id, kind='office', name=name, email=email,
        phone=request.form.get('phone', '').strip() or None,
        message=request.form.get('message', '').strip() or None,
        created_at=now_stamp()))
    db.session.commit()
    flash(f'Thank you! Your message has been sent to {office.name}.', 'success')
    return redirect(request.form.get('next') or office.detail_url())


@app.route('/newsletter/subscribe', methods=['POST'])
def newsletter_subscribe():
    email = request.form.get('email', '').strip().lower()
    buyer_type = request.form.get('buyer_type', '').strip()
    if '@' not in email or '.' not in email:
        flash('Please enter a valid email address.', 'error')
    else:
        db.session.add(NewsletterSubscriber(email=email, buyer_type=buyer_type or None,
                                           created_at=now_stamp()))
        db.session.commit()
        flash('Thanks for subscribing to HomeHQ! Watch your inbox for real estate advice.', 'success')
    return redirect(request.form.get('next') or url_for('index'))


@app.route('/alerts/subscribe', methods=['POST'])
def alerts_subscribe():
    email = request.form.get('email', '').strip().lower()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip().upper()
    if '@' not in email or '.' not in email:
        flash('Please enter a valid email address to receive listing alerts.', 'error')
    else:
        db.session.add(ListingAlert(
            user_id=current_user.id if current_user.is_authenticated else None,
            email=email, city=city or None, state=state or None,
            created_at=now_stamp()))
        db.session.commit()
        flash('Listing alerts enabled! We will email you new matches.', 'success')
    return redirect(request.form.get('next') or url_for('index'))


# ------------------------------------------------------------- error pages --

@app.errorhandler(404)
def not_found(err):
    return render_template('404.html'), 404


# ------------------------------------------------------------------ bootup --

def seed_database():
    """Idempotent: builds all content tables from the tracked source snapshots."""
    if Listing.query.count() > 0:
        return
    from seed_data import run_seed_content
    run_seed_content(db, Listing, Rental, Agent, Office, BlogPost)


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    from seed_data import run_seed_users
    run_seed_users(db, User, Favorite, SavedSearch, Inquiry, ListingAlert, Listing)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
