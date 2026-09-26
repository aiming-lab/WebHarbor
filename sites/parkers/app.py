#!/usr/bin/env python3
"""Parkers mirror — Flask application.

Mirrors https://www.parkers.co.uk/ (UK car reviews, valuations, specs and
cars-for-sale advice site) using real content captured from the upstream
site on 2026-09-24.

Route and URL patterns follow the upstream site:
  /car-reviews/  /car-reviews/<body>/  /<make>/reviews/  /<make>/<model>/review/[<section>/]
  /car-specs/  /<make>/<model>/specs/  /<make>/<model>/<gen>/specs/
  /car-valuation/  /<make>/used-prices/  /<make>/<model>/used-prices/
  /<make>/<model>/<gen>/used-prices/  .../select-a-valuation/  .../free-valuation/
  /cars-for-sale/[/used|/new|/fuel-x|/price-x|/gearbox-x|/engine-x|/seats-x]
  /<make>/for-sale/  /<make>/<model>/for-sale/  /cars-for-sale/search-results/
  /cars-for-sale/listing/<id>/
  /car-news/  /car-news/<slug>/  /best-cars/  /best-cars/<slug>/
  /car-insurance/insurance-groups/  /<make>/<model>/<gen>/insurance-groups/
  /car-tax/  /<make>/<model>/<gen>/car-tax/
  /owner-reviews/  /<make>/<model>/<gen>/owner-reviews/  /owner-reviews/submit/
  /my-parkers/... account area  /search/  /_health

Determinism: the site clock is pinned to BENCHMARK_TODAY (2026-09-24).
No random and no real clocks are used anywhere a page renders.
"""
import os
import re
from datetime import date, datetime

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                          login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from markupsafe import Markup
from sqlalchemy import or_

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config['SECRET_KEY'] = 'parkers-mirror-dev-secret-key'
DB_PATH = os.environ.get('PARKERS_DB_PATH',
                         os.path.join(BASE_DIR, 'instance', 'parkers.db'))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'account_login'
login_manager.login_message = 'Please log in to access your Parkers account.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

# Frozen benchmark date: keeps "Added today", news ordering deterministic.
BENCHMARK_TODAY = date(2026, 9, 24)

STOPWORDS = {'a', 'an', 'the', 'of', 'to', 'in', 'on', 'for', 'and', 'or',
             'is', 'are', 'be', 'with', 'as', 'by', 'at', 'from', 'what',
             'how', 'your', 'you', 'my', 'it', 'its'}

BODY_TYPES = [
    ('small-city', 'Small & City Cars'), ('hatchback', 'Hatchbacks'),
    ('saloon', 'Saloons'), ('suv', 'SUVs & Crossovers'),
    ('coupe', 'Coupes'), ('convertible-roadster', 'Convertibles'),
    ('estate', 'Estates'), ('4x4', '4x4s'), ('mpv-people-carrier', 'MPVs'),
    ('family', 'Family Cars'), ('fast-sports', 'Fast & Sports'),
    ('electric-hybrid', 'Electric & Hybrid'),
]

REVIEW_SECTIONS = [
    ('overview', 'Overview', 'Currently reading'),
    ('practicality', 'Practicality &amp; safety', ''),
    ('interior', 'Interior, tech &amp; comfort', ''),
    ('engines', 'Engines &amp; handling', ''),
    ('mpg-running-costs', 'Ownership cost', ''),
    ('verdict', 'Verdict', ''),
]


@app.template_filter('firstline')
def firstline(value):
    """First line of a captured text field. The scraper sometimes stored the
    whole at-a-glance block after the real strapline; only the first line is
    the human-legit strapline, the rest is page chrome."""
    return (value or '').split('\n', 1)[0].strip()

VALUATION_PURPOSES = ['Selling', 'Buying', 'Insurance', 'Just curious']

SORT_OPTIONS = {
    'relevance': 'Recently added',
    'price-asc': 'Price (low to high)',
    'price-desc': 'Price (high to low)',
    'mileage-asc': 'Mileage (low to high)',
    'year-desc': 'Year (newest first)',
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    postcode = db.Column(db.String(12), default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime(2026, 9, 1, 9, 0, 0))

    shortlist = db.relationship('ShortlistItem', backref='user', lazy=True,
                                cascade='all, delete-orphan', order_by='ShortlistItem.added_at')
    saved_valuations = db.relationship('SavedValuation', backref='user', lazy=True,
                                        cascade='all, delete-orphan',
                                        order_by='SavedValuation.saved_at')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Make(db.Model):
    __tablename__ = 'makes'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    logo_path = db.Column(db.String(200), default='')


class CarModel(db.Model):
    __tablename__ = 'car_models'
    id = db.Column(db.Integer, primary_key=True)
    make_id = db.Column(db.Integer, db.ForeignKey('makes.id'), nullable=False)
    slug = db.Column(db.String(100), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    body_type = db.Column(db.String(40), default='')
    headline = db.Column(db.String(255), default='')
    strapline = db.Column(db.String(255), default='')
    rating = db.Column(db.String(8))
    fuel_types = db.Column(db.String(120), default='')
    price_new_text = db.Column(db.String(120), default='')
    used_prices_text = db.Column(db.String(120), default='')
    road_tax_text = db.Column(db.String(120), default='')
    insurance_text = db.Column(db.String(120), default='')
    hero_image = db.Column(db.String(255), default='')
    gallery_json = db.Column(db.Text, default='[]')
    pros_json = db.Column(db.Text, default='[]')
    cons_json = db.Column(db.Text, default='[]')
    review_intro = db.Column(db.Text, default='')
    author = db.Column(db.String(120), default='')
    date_published = db.Column(db.String(40), default='')
    date_modified = db.Column(db.String(40), default='')
    has_review = db.Column(db.Boolean, default=False)

    make = db.relationship('Make', backref='models', lazy='joined')

    @property
    def review_intro_paras(self):
        return [p.strip() for p in (self.review_intro or '').split('\n\n') if p.strip()]

    @property
    def pros(self):
        return jload(self.pros_json, [])

    @property
    def cons(self):
        return jload(self.cons_json, [])
    sections = db.relationship('ReviewSection', backref='model', lazy=True,
                               cascade='all, delete-orphan',
                               order_by='ReviewSection.ordinal')
    rivals = db.relationship('Rival', backref='model', lazy=True,
                             cascade='all, delete-orphan')
    generations = db.relationship('Generation', backref='model', lazy=True,
                                  cascade='all, delete-orphan',
                                  order_by='Generation.year_from.desc()')
    verdict_ratings = db.relationship('ReviewRating', backref='model', lazy=True,
                                       cascade='all, delete-orphan', uselist=False)

    __table_args__ = (db.UniqueConstraint('make_id', 'slug'),)


class ReviewSection(db.Model):
    __tablename__ = 'review_sections'
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('car_models.id'), nullable=False)
    section_key = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(255), default='')
    paragraphs_json = db.Column(db.Text, default='[]')
    ordinal = db.Column(db.Integer, default=0)

    @property
    def paragraphs(self):
        return jload(self.paragraphs_json, [])


class ReviewRating(db.Model):
    __tablename__ = 'review_ratings'
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('car_models.id'), nullable=False)
    performance = db.Column(db.String(8))
    handling = db.Column(db.String(8))
    behind_wheel = db.Column(db.String(8))
    comfort = db.Column(db.String(8))
    running_costs = db.Column(db.String(8))
    green = db.Column(db.String(8))
    reliability = db.Column(db.String(8))
    equipment = db.Column(db.String(8))
    safety = db.Column(db.String(8))
    practicality = db.Column(db.String(8))


class Rival(db.Model):
    __tablename__ = 'rivals'
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('car_models.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    text = db.Column(db.String(160), default='')


class Generation(db.Model):
    __tablename__ = 'generations'
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('car_models.id'), nullable=False)
    slug = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    years_label = db.Column(db.String(80), default='')
    year_from = db.Column(db.Integer)
    year_to = db.Column(db.Integer)
    is_current = db.Column(db.Boolean, default=False)

    derivatives = db.relationship('Derivative', backref='generation', lazy=True,
                                  cascade='all, delete-orphan',
                                  order_by='Derivative.trim, Derivative.name')

    __table_args__ = (db.UniqueConstraint('model_id', 'slug'),)


class Derivative(db.Model):
    __tablename__ = 'derivatives'
    id = db.Column(db.Integer, primary_key=True)
    generation_id = db.Column(db.Integer, db.ForeignKey('generations.id'), nullable=False)
    slug = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    trim = db.Column(db.String(120), default='')
    engine_text = db.Column(db.String(120), default='')
    fuel = db.Column(db.String(60), default='')
    transmission = db.Column(db.String(60), default='')
    doors = db.Column(db.Integer)
    ps = db.Column(db.Integer)
    insurance_group = db.Column(db.Integer)
    price_new = db.Column(db.Integer)
    used_low = db.Column(db.Integer)
    used_high = db.Column(db.Integer)
    mpg = db.Column(db.String(60), default='')
    co2 = db.Column(db.String(60), default='')
    zero_sixty = db.Column(db.String(40), default='')
    top_speed = db.Column(db.String(40), default='')
    length_mm = db.Column(db.Integer)
    width_mm = db.Column(db.Integer)
    height_mm = db.Column(db.Integer)
    wheelbase_mm = db.Column(db.Integer)
    boot_litres = db.Column(db.Integer)
    seats = db.Column(db.Integer)
    tank_litres = db.Column(db.String(40), default='')
    weight_kg = db.Column(db.Integer)
    tax_cost = db.Column(db.Integer)
    spec_json = db.Column(db.Text, default='{}')
    equipment_json = db.Column(db.Text, default='[]')
    capid = db.Column(db.String(20), default='')

    valuations = db.relationship('Valuation', backref='derivative', lazy=True,
                                 cascade='all, delete-orphan',
                                 order_by='Valuation.year_plate')

    @property
    def urlslug(self):
        from urllib.parse import quote
        return quote(self.slug, safe='')

    def valuation_for_year(self, year_plate):
        return next((v for v in self.valuations if v.year_plate == year_plate), None)

    __table_args__ = (db.UniqueConstraint('generation_id', 'slug'),)


class Valuation(db.Model):
    __tablename__ = 'valuations'
    id = db.Column(db.Integer, primary_key=True)
    derivative_id = db.Column(db.Integer, db.ForeignKey('derivatives.id'), nullable=False)
    year_plate = db.Column(db.String(12), nullable=False)
    private_low = db.Column(db.Integer, nullable=False)
    private_high = db.Column(db.Integer, nullable=False)
    dealer_low = db.Column(db.Integer, nullable=False)
    dealer_high = db.Column(db.Integer, nullable=False)
    part_ex_low = db.Column(db.Integer)
    part_ex_high = db.Column(db.Integer)

    __table_args__ = (db.UniqueConstraint('derivative_id', 'year_plate'),)


class RegLookup(db.Model):
    __tablename__ = 'reg_lookups'
    id = db.Column(db.Integer, primary_key=True)
    reg = db.Column(db.String(12), unique=True, nullable=False, index=True)
    valuation_id = db.Column(db.Integer, db.ForeignKey('valuations.id'), nullable=False)
    mileage = db.Column(db.Integer)
    note = db.Column(db.String(200), default='')

    valuation = db.relationship('Valuation', lazy='joined')


class Listing(db.Model):
    __tablename__ = 'listings'

    id = db.Column(db.Integer, primary_key=True)
    make_slug = db.Column(db.String(80), nullable=False, index=True)
    model_slug = db.Column(db.String(100), nullable=False, index=True)
    gen_slug = db.Column(db.String(120), default='')
    title = db.Column(db.String(200), nullable=False)
    derivative_text = db.Column(db.String(255), default='')
    price = db.Column(db.Integer, nullable=False)
    plate_year = db.Column(db.Integer)
    year_plate = db.Column(db.String(12), default='')
    mileage = db.Column(db.Integer, default=0)
    fuel = db.Column(db.String(60), default='')
    transmission = db.Column(db.String(60), default='')
    body = db.Column(db.String(40), default='')
    doors = db.Column(db.Integer)
    seller_name = db.Column(db.String(160), default='')
    seller_type = db.Column(db.String(60), default='Franchise Dealer')
    location = db.Column(db.String(160), default='')
    added_label = db.Column(db.String(40), default='Added today')
    added_days = db.Column(db.Integer, default=0)
    image = db.Column(db.String(255), default='')
    images_json = db.Column(db.Text, default='[]')
    description = db.Column(db.Text, default='')
    features_json = db.Column(db.Text, default='[]')
    colour = db.Column(db.String(60), default='')
    condition = db.Column(db.String(20), default='Used')

    @property
    def images_list(self):
        return jload(self.images_json, [])

    @property
    def features(self):
        return jload(self.features_json, [])


class NewsArticle(db.Model):
    __tablename__ = 'news_articles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    standfirst = db.Column(db.Text, default='')
    body_json = db.Column(db.Text, default='[]')
    published = db.Column(db.String(40), default='')
    author = db.Column(db.String(120), default='')
    image = db.Column(db.String(255), default='')
    category = db.Column(db.String(80), default='Car news')

    @property
    def body(self):
        return jload(self.body_json, [])


class Guide(db.Model):
    __tablename__ = 'guides'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    body_json = db.Column(db.Text, default='[]')
    ranked_json = db.Column(db.Text, default='[]')
    image = db.Column(db.String(255), default='')

    @property
    def ranked(self):
        return jload(self.ranked_json, [])

    @property
    def ranked_count(self):
        return len(self.ranked)

    @property
    def body(self):
        return jload(self.body_json, [])


class OwnerReview(db.Model):
    __tablename__ = 'owner_reviews'
    id = db.Column(db.Integer, primary_key=True)
    make_slug = db.Column(db.String(80), nullable=False, index=True)
    model_slug = db.Column(db.String(100), nullable=False)
    gen_slug = db.Column(db.String(120), nullable=False, index=True)
    derivative_text = db.Column(db.String(255), default='')
    rating = db.Column(db.Integer)
    author = db.Column(db.String(120), default='')
    published = db.Column(db.String(40), default='')
    published_date = db.Column(db.Date)
    year_plate = db.Column(db.String(12), default='')
    bought = db.Column(db.String(120), default='')
    body_json = db.Column(db.Text, default='[]')
    recommend = db.Column(db.Boolean, default=True)
    is_seed = db.Column(db.Boolean, default=True)

    @property
    def body(self):
        return jload(self.body_json, [])


class OwnerStat(db.Model):
    __tablename__ = 'owner_stats'
    id = db.Column(db.Integer, primary_key=True)
    make_slug = db.Column(db.String(80), nullable=False)
    model_slug = db.Column(db.String(100), nullable=False)
    gen_slug = db.Column(db.String(120), nullable=False)
    total = db.Column(db.Integer)
    average = db.Column(db.String(8))
    dist_json = db.Column(db.Text, default='[]')

    __table_args__ = (db.UniqueConstraint('make_slug', 'model_slug', 'gen_slug'),)


class ShortlistItem(db.Model):
    __tablename__ = 'shortlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=lambda: datetime(2026, 9, 20, 10, 0, 0))
    listing = db.relationship('Listing', lazy='joined')


class SavedValuation(db.Model):
    __tablename__ = 'saved_valuations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    valuation_id = db.Column(db.Integer, db.ForeignKey('valuations.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=lambda: datetime(2026, 9, 20, 10, 0, 0))
    valuation = db.relationship('Valuation', lazy='joined')

    __table_args__ = (db.UniqueConstraint('user_id', 'valuation_id'),)


class TaxRate(db.Model):
    __tablename__ = 'tax_rates'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(80), nullable=False)
    band = db.Column(db.String(120), nullable=False)
    first_year = db.Column(db.Integer)
    standard = db.Column(db.Integer)
    note = db.Column(db.String(255), default='')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def jload(s, default):
    import json as _json
    try:
        return _json.loads(s) if s else default
    except Exception:
        return default


def money(n):
    try:
        return '£{:,.0f}'.format(int(n))
    except (TypeError, ValueError):
        return '—'


def token_split(q):
    return [t.lower() for t in re.split(r'\W+', q or '')
            if len(t) > 1 and t.lower() not in STOPWORDS]


def score_text(tokens, text):
    text = (text or '').lower()
    if not tokens:
        return 0
    return sum(1 for t in tokens if t in text)


def get_make(slug):
    return Make.query.filter_by(slug=slug).first()


def get_model(make, model):
    return (CarModel.query
            .join(Make, CarModel.make_id == Make.id)
            .filter(Make.slug == make, CarModel.slug == model)
            .first())


def get_generation(make, model, gen):
    m = get_model(make, model)
    if not m:
        return None
    return Generation.query.filter_by(model_id=m.id, slug=gen).first()


def model_url(m):
    return f"/{m.make.slug}/{m.slug}/"


def review_url(m):
    return f"/{m.make.slug}/{m.slug}/review/"


def listing_added_label(days):
    if days <= 0:
        return 'Added today'
    if days == 1:
        return 'Added yesterday'
    if days < 7:
        return f'Added {days} days ago'
    if days < 14:
        return 'Added 1 week ago'
    if days < 31:
        return f'Added {days // 7} weeks ago'
    return f'Added {max(1, days // 30)} month{"s" if days >= 60 else ""} ago'


def parse_year_plate(yp):
    """'2019/19' -> (2019, 19)"""
    m = re.match(r'^(\d{4})/(\d{2})$', yp or '')
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def year_plate_sort_key(yp):
    p = parse_year_plate(yp)
    if not p:
        return (0, 0)
    year, plate = p
    # UK plate letter: second half of year has plate >= 51 (e.g. /68)
    half = 1 if plate > 50 else 0
    return (year, half)


def star_count(rating):
    """Number of full stars for a rating that may be str/float/None."""
    try:
        return int(float(rating))
    except (TypeError, ValueError):
        return 0


app.jinja_env.globals.update(
    money=money, star_count=star_count, BENCHMARK_TODAY=BENCHMARK_TODAY,
    BODY_TYPES=BODY_TYPES, REVIEW_SECTIONS=REVIEW_SECTIONS,
    VALUATION_PURPOSES=VALUATION_PURPOSES, SORT_OPTIONS=SORT_OPTIONS)


# ---------------------------------------------------------------------------
# Home + reviews
# ---------------------------------------------------------------------------

@app.route('/')
def home():
    latest = (CarModel.query.filter_by(has_review=True)
              .order_by(CarModel.date_modified.desc()).limit(8).all())
    makes = Make.query.order_by(Make.name).all()
    news = NewsArticle.query.order_by(NewsArticle.published.desc()).limit(4).all()
    guides = Guide.query.limit(6).all()
    listings = (Listing.query.filter_by(condition='Used')
                .order_by(Listing.added_days, Listing.price).limit(8).all())
    total_listings = Listing.query.count()
    total_used = Listing.query.filter_by(condition='Used').count()
    return render_template('index.html', latest=latest, makes=makes, news=news,
                           guides=guides, listings=listings,
                           total_listings=total_listings, total_used=total_used)


@app.route('/car-reviews/')
def reviews_hub():
    makes = Make.query.order_by(Make.name).all()
    counts = {b: CarModel.query.filter_by(body_type=b, has_review=True).count()
              for b, _ in BODY_TYPES}
    return render_template('reviews_hub.html', makes=makes, counts=counts)


@app.route('/car-reviews/<body>/')
def body_type(body):
    if body not in dict(BODY_TYPES):
        abort(404)
    models = (CarModel.query.filter_by(body_type=body, has_review=True)
              .order_by(CarModel.rating.desc()).all())
    label = dict(BODY_TYPES)[body]
    return render_template('body_type.html', models=models, body=body,
                           label=label)


@app.route('/<make>/reviews/')
def make_reviews(make):
    mk = get_make(make)
    if not mk:
        abort(404)
    models = (CarModel.query.filter_by(make_id=mk.id, has_review=True)
              .order_by(CarModel.name).all())
    return render_template('make_reviews.html', make=mk, models=models)


@app.route('/<make>/<model>/review/')
def model_review(make, model):
    m = get_model(make, model)
    if not m:
        abort(404)
    if not m.has_review:
        abort(404)
    sections = {s.section_key: s for s in m.sections}
    overview = sections.get('overview')
    return render_template('model_review.html', m=m, sections=sections,
                           overview=overview)


@app.route('/<make>/<model>/review/<section>/')
def review_section(make, model, section):
    if section not in [k for k, _, _ in REVIEW_SECTIONS]:
        abort(404)
    m = get_model(make, model)
    if not m or not m.has_review:
        abort(404)
    sec = next((s for s in m.sections if s.section_key == section), None)
    if sec is None:
        abort(404)
    return render_template('review_section.html', m=m, sec=sec, section=section)


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------

@app.route('/car-specs/')
def specs_hub():
    makes = Make.query.order_by(Make.name).all()
    popular = (CarModel.query.filter_by(has_review=True)
               .order_by(CarModel.date_modified.desc()).limit(12).all())
    selected_make = request.args.get('make', '')
    make_models = []
    if selected_make:
        mk = Make.query.filter_by(slug=selected_make).first()
        if mk:
            make_models = (CarModel.query.filter_by(make_id=mk.id)
                           .order_by(CarModel.name).all())
    return render_template('specs_hub.html', makes=makes, popular=popular,
                           make_models=make_models)


@app.route('/<make>/<model>/specs/')
def model_specs(make, model):
    m = get_model(make, model)
    if not m:
        abort(404)
    gens = Generation.query.filter_by(model_id=m.id).order_by(Generation.year_from.desc()).all()
    return render_template('model_specs.html', m=m, gens=gens)


@app.route('/<make>/<model>/<gen>/specs/')
def gen_specs(make, model, gen):
    g = get_generation(make, model, gen)
    if not g:
        abort(404)
    derivs = g.derivatives
    sel_slug = request.args.get('deriv')
    sel = next((d for d in derivs if d.slug == sel_slug), None)
    if sel is None and derivs:
        sel = derivs[0]
    trims = {}
    for d in derivs:
        trims.setdefault(d.trim or 'Other', []).append(d)
    return render_template('gen_specs.html', m=g.model, g=g, derivs=derivs,
                           trims=trims, sel=sel)


@app.route('/<make>/<model>/<gen>/<deriv>/specs/')
def deriv_spec(make, model, gen, deriv):
    from urllib.parse import unquote
    g = get_generation(make, model, gen)
    if not g:
        abort(404)
    d = next((x for x in g.derivatives if x.slug == unquote(deriv)), None)
    if not d:
        abort(404)
    spec = jload(d.spec_json, {})
    equipment = jload(d.equipment_json, [])
    return render_template('deriv_spec.html', m=g.model, g=g, d=d,
                           spec=spec, equipment=equipment)


# ---------------------------------------------------------------------------
# Valuations
# ---------------------------------------------------------------------------

@app.route('/car-valuation/')
def valuation_hub():
    makes = Make.query.order_by(Make.name).all()
    popular_models = (CarModel.query.filter(CarModel.used_prices_text != '')
                      .order_by(CarModel.date_modified.desc()).limit(14).all())
    selected_make = request.args.get('make', '')
    make_models = []
    if selected_make:
        mk = Make.query.filter_by(slug=selected_make).first()
        if mk:
            make_models = (CarModel.query.filter_by(make_id=mk.id)
                           .order_by(CarModel.name).all())
    return render_template('valuation_hub.html', makes=makes,
                           popular_models=popular_models,
                           make_models=make_models)


@app.route('/car-valuation/lookup/', methods=['POST'])
def valuation_lookup():
    reg = (request.form.get('reg') or '').strip().upper()
    reg = re.sub(r'[^A-Z0-9]', '', reg)
    if not reg:
        return render_template('valuation_hub.html',
                               makes=Make.query.order_by(Make.name).all(),
                               popular_models=CarModel.query.limit(14).all(),
                               vrm_error='Please enter a registration.')
    hit = RegLookup.query.filter(RegLookup.reg == reg).first()
    if not hit:
        return render_template('valuation_hub.html',
                               makes=Make.query.order_by(Make.name).all(),
                               popular_models=(CarModel.query
                                               .order_by(CarModel.date_modified.desc())
                                               .limit(14).all()),
                               vrm_error='Sorry, no valuation data found',
                               vrm_reg=reg)
    v = hit.valuation
    d = v.derivative
    g = d.generation
    m = g.model
    return redirect(f"/{m.make.slug}/{m.slug}/{g.slug}/{d.slug}/{v.id}/select-a-valuation/")


@app.route('/<make>/used-prices/')
def make_used_prices(make):
    mk = get_make(make)
    if not mk:
        abort(404)
    models = (CarModel.query.filter_by(make_id=mk.id)
              .order_by(CarModel.name).all())
    return render_template('make_used_prices.html', make=mk, models=models)


@app.route('/<make>/<model>/used-prices/')
def model_used_prices(make, model):
    m = get_model(make, model)
    if not m:
        abort(404)
    gens = (Generation.query.filter_by(model_id=m.id)
            .order_by(Generation.year_from.desc()).all())
    return render_template('model_used_prices.html', m=m, gens=gens)


@app.route('/<make>/<model>/<gen>/used-prices/')
def gen_used_prices(make, model, gen):
    g = get_generation(make, model, gen)
    if not g:
        abort(404)
    derivs = g.derivatives
    # year plates available across this generation's shipped valuations
    year_map = {}
    for d in derivs:
        for v in d.valuations:
            year_map.setdefault(v.year_plate, []).append(d)
    years = sorted(year_map.keys(), key=year_plate_sort_key)
    purpose = request.args.get('purpose', 'Buying')
    if purpose not in VALUATION_PURPOSES:
        purpose = 'Buying'
    year = request.args.get('year')
    if year not in years and years:
        year = years[-1]
    versions = []
    sel_deriv = None
    if year and year in year_map:
        versions = sorted(year_map[year], key=lambda d: (d.trim or '', d.name))
        vs = request.args.get('version')
        sel_deriv = next((d for d in versions if str(d.id) == vs), None)
    return render_template('gen_used_prices.html', m=g.model, g=g,
                           years=years, year=year, versions=versions,
                           purpose=purpose, sel_deriv=sel_deriv)


@app.route('/<make>/<model>/<gen>/<deriv>/<vid>/select-a-valuation/')
def select_valuation(make, model, gen, deriv, vid):
    from urllib.parse import unquote
    g = get_generation(make, model, gen)
    if not g:
        abort(404)
    d = next((x for x in g.derivatives if x.slug == unquote(deriv)), None)
    if not d:
        abort(404)
    try:
        v = db.session.get(Valuation, int(vid))
    except ValueError:
        v = None
    if not v or v.derivative_id != d.id:
        abort(404)
    return render_template('select_valuation.html', m=g.model, g=g, d=d, v=v)


@app.route('/<make>/<model>/<gen>/<deriv>/<vid>/free-valuation/')
def free_valuation(make, model, gen, deriv, vid):
    from urllib.parse import unquote
    g = get_generation(make, model, gen)
    if not g:
        abort(404)
    d = next((x for x in g.derivatives if x.slug == unquote(deriv)), None)
    if not d:
        abort(404)
    try:
        v = db.session.get(Valuation, int(vid))
    except ValueError:
        v = None
    if not v or v.derivative_id != d.id:
        abort(404)
    featured = (Listing.query
                .filter(Listing.make_slug == g.model.make.slug,
                        Listing.model_slug == g.model.slug)
                .order_by(Listing.added_days, Listing.price).limit(8).all())
    saved_flash = False
    if current_user.is_authenticated:
        exists = (SavedValuation.query
                  .filter_by(user_id=current_user.id, valuation_id=v.id).first())
        if not exists:
            db.session.add(SavedValuation(user_id=current_user.id, valuation_id=v.id))
            db.session.commit()
            saved_flash = True
    return render_template('free_valuation.html', m=g.model, g=g, d=d, v=v,
                           featured=featured, saved_flash=saved_flash)


@app.route('/<make>/<model>/<gen>/<deriv>/<vid>/pro-valuation/')
def pro_valuation(make, model, gen, deriv, vid):
    from urllib.parse import unquote
    g = get_generation(make, model, gen)
    if not g:
        abort(404)
    d = next((x for x in g.derivatives if x.slug == unquote(deriv)), None)
    if not d:
        abort(404)
    try:
        v = db.session.get(Valuation, int(vid))
    except ValueError:
        v = None
    if not v or v.derivative_id != d.id:
        abort(404)
    return render_template('pro_valuation.html', m=g.model, g=g, d=d, v=v)


# ---------------------------------------------------------------------------
# Cars for sale
# ---------------------------------------------------------------------------

CFS_FUELS = {
    'petrol': 'Petrol', 'diesel': 'Diesel', 'electric': 'Electric',
    'petrolelectric-hybrid': 'Petrol/Electric Hybrid',
    'dieselelectric-hybrid': 'Diesel/Electric Hybrid',
    'petrol-parallel-phev': 'Petrol Parallel PHEV',
}
CFS_GEARBOXES = {'automatic': 'Automatic', 'manual': 'Manual'}


def apply_listing_filters(q, args):
    cond = args.get('condition')
    if cond in ('Used', 'New'):
        q = q.filter(Listing.condition == cond)
    make = args.get('make')
    if make:
        q = q.filter(Listing.make_slug == make)
    model = args.get('model')
    if model:
        q = q.filter(Listing.model_slug == model)
    fuel = args.get('fuel')
    if fuel:
        q = q.filter(Listing.fuel == fuel)
    trans = args.get('transmission')
    if trans:
        q = q.filter(Listing.transmission == trans)
    body = args.get('body')
    if body:
        q = q.filter(Listing.body == body)
    def _int(key):
        try:
            return int(args.get(key) or 0)
        except (TypeError, ValueError):
            return 0
    price_min = _int('price_min')
    if price_min:
        q = q.filter(Listing.price >= price_min)
    price_max = _int('price_max')
    if price_max:
        q = q.filter(Listing.price <= price_max)
    mileage_max = _int('mileage_max')
    if mileage_max:
        q = q.filter(Listing.mileage <= mileage_max)
    year_min = _int('year_min')
    if year_min:
        q = q.filter(Listing.plate_year >= year_min)
    doors = _int('doors')
    if doors:
        q = q.filter(Listing.doors == doors)
    return q


def sort_listings(q, sort):
    if sort == 'price-asc':
        return q.order_by(Listing.price, Listing.added_days)
    if sort == 'price-desc':
        return q.order_by(Listing.price.desc(), Listing.added_days)
    if sort == 'mileage-asc':
        return q.order_by(Listing.mileage, Listing.price)
    if sort == 'year-desc':
        return q.order_by(Listing.plate_year.desc(), Listing.price)
    return q.order_by(Listing.added_days, Listing.price)


@app.route('/cars-for-sale/')
def c4s_hub():
    makes = Make.query.order_by(Make.name).all()
    recent = Listing.query.order_by(Listing.added_days, Listing.price).limit(8).all()
    total = Listing.query.count()
    used = Listing.query.filter_by(condition='Used').count()
    return render_template('c4s_hub.html', makes=makes, recent=recent,
                           total=total, used=used)


@app.route('/cars-for-sale/used/')
def c4s_used():
    listings = (Listing.query.filter_by(condition='Used')
                .order_by(Listing.added_days, Listing.price).limit(24).all())
    makes = Make.query.order_by(Make.name).all()
    total = Listing.query.filter_by(condition='Used').count()
    return render_template('c4s_used.html', listings=listings, makes=makes,
                           total=total, condition='Used')


@app.route('/cars-for-sale/new/')
def c4s_new():
    listings = (Listing.query.filter_by(condition='New')
                .order_by(Listing.added_days, Listing.price).limit(24).all())
    makes = Make.query.order_by(Make.name).all()
    total = Listing.query.filter_by(condition='New').count()
    return render_template('c4s_used.html', listings=listings, makes=makes,
                           total=total, condition='New')


@app.route('/cars-for-sale/fuel-<fuel>/')
def c4s_fuel(fuel):
    label = CFS_FUELS.get(fuel)
    if not label:
        abort(404)
    listings = (Listing.query.filter(Listing.fuel == label)
                .order_by(Listing.added_days, Listing.price).limit(24).all())
    total = Listing.query.filter(Listing.fuel == label).count()
    return render_template('c4s_filter.html', listings=listings, total=total,
                           heading=f'{label} cars for sale',
                           filter_note=f'Cars for sale running on {label.lower()}')


@app.route('/cars-for-sale/gearbox-<gear>/')
def c4s_gearbox(gear):
    label = CFS_GEARBOXES.get(gear)
    if not label:
        abort(404)
    listings = (Listing.query.filter(Listing.transmission == label)
                .order_by(Listing.added_days, Listing.price).limit(24).all())
    total = Listing.query.filter(Listing.transmission == label).count()
    return render_template('c4s_filter.html', listings=listings, total=total,
                           heading=f'{label} cars for sale',
                           filter_note=f'Cars for sale with {label.lower()} gearbox')


@app.route('/cars-for-sale/price-<int:cap>/')
def c4s_price(cap):
    listings = (Listing.query.filter(Listing.price <= cap)
                .order_by(Listing.price, Listing.added_days).limit(24).all())
    total = Listing.query.filter(Listing.price <= cap).count()
    return render_template('c4s_filter.html', listings=listings, total=total,
                           heading=f'Cars for sale under {money(cap)}',
                           filter_note=f'Used cars priced under {money(cap)}')


@app.route('/cars-for-sale/engine-<int:tenths>/')
def c4s_engine(tenths):
    litres = f'{tenths // 10}.{tenths % 10}L'
    listings = (Listing.query.filter(Listing.derivative_text.like(f'%{litres}%'))
                .order_by(Listing.added_days, Listing.price).limit(24).all())
    total = Listing.query.filter(Listing.derivative_text.like(f'%{litres}%')).count()
    return render_template('c4s_filter.html', listings=listings, total=total,
                           heading=f'{litres} cars for sale',
                           filter_note=f'Cars for sale with {litres} engines')


@app.route('/cars-for-sale/seats-<int:n>/')
def c4s_seats(n):
    listings = (Listing.query.filter(Listing.doors >= 2)
                .order_by(Listing.added_days, Listing.price).limit(24).all())
    # seats filter: match derivative body copy
    listings = [l for l in listings if n in (5, 7) and
                (l.body in ('SUV', 'Estate', 'MPV') if n == 7 else True)][:24]
    total = len(listings)
    return render_template('c4s_filter.html', listings=listings, total=total,
                           heading=f'{n} seat cars for sale',
                           filter_note=f'Cars for sale with {n} seats')


@app.route('/<make>/for-sale/')
def make_for_sale(make):
    mk = get_make(make)
    if not mk:
        abort(404)
    listings = (Listing.query.filter_by(make_slug=mk.slug)
                .order_by(Listing.added_days, Listing.price).limit(24).all())
    total = Listing.query.filter_by(make_slug=mk.slug).count()
    models = (CarModel.query.filter_by(make_id=mk.id)
              .order_by(CarModel.name).all())
    return render_template('make_for_sale.html', make=mk, listings=listings,
                           total=total, models=models)


@app.route('/<make>/<model>/for-sale/')
def model_for_sale(make, model):
    m = get_model(make, model)
    if not m:
        abort(404)
    listings = (Listing.query.filter_by(make_slug=m.make.slug, model_slug=m.slug)
                .order_by(Listing.added_days, Listing.price).limit(24).all())
    total = Listing.query.filter_by(make_slug=m.make.slug, model_slug=m.slug).count()
    gens = Generation.query.filter_by(model_id=m.id).order_by(Generation.year_from.desc()).all()
    return render_template('model_for_sale.html', m=m, listings=listings,
                           total=total, gens=gens)


@app.route('/cars-for-sale/search-results/')
def c4s_search():
    args = request.args
    # accept upstream-style ?_qs= base64 state as well as friendly params
    import base64, json as _json
    qs = args.get('_qs')
    params = {k: v for k, v in args.items() if k != '_qs'}
    if qs and not params:
        try:
            pad = qs + '=' * (-len(qs) % 4)
            decoded = base64.urlsafe_b64decode(pad).decode('utf-8', 'ignore')
            m = re.search(r"NewOrUsed,'(\w+)'", decoded)
            if m:
                params['condition'] = 'Used' if m.group(1) == 'Used' else 'New'
        except Exception:
            pass
    q = Listing.query
    q = apply_listing_filters(q, params)
    sort = params.get('sort', 'relevance')
    if sort not in SORT_OPTIONS:
        sort = 'relevance'
    total = q.count()
    page = max(1, args.get('page', 1, type=int))
    per_page = 12
    listings = sort_listings(q, sort).offset((page - 1) * per_page).limit(per_page).all()
    makes = Make.query.order_by(Make.name).all()
    models = []
    if params.get('make'):
        mk = get_make(params['make'])
        if mk:
            models = CarModel.query.filter_by(make_id=mk.id).order_by(CarModel.name).all()
    return render_template('c4s_search.html', listings=listings, total=total,
                           params=params, sort=sort, page=page,
                           per_page=per_page, makes=makes, models=models,
                           fuels=sorted({f for f in CFS_FUELS.values()}))


@app.route('/cars-for-sale/listing/<int:lid>/')
def listing_detail(lid):
    l = db.session.get(Listing, lid)
    if not l:
        abort(404)
    similar = (Listing.query
               .filter(Listing.make_slug == l.make_slug,
                       Listing.model_slug == l.model_slug, Listing.id != l.id)
               .order_by(Listing.price).limit(4).all())
    in_shortlist = False
    if current_user.is_authenticated:
        in_shortlist = any(s.listing_id == l.id for s in current_user.shortlist)
    return render_template('listing_detail.html', l=l, similar=similar,
                           in_shortlist=in_shortlist)


@app.route('/cars-for-sale/listing/<int:lid>/save/', methods=['POST'])
@login_required
def listing_save(lid):
    l = db.session.get(Listing, lid)
    if not l:
        abort(404)
    next_url = request.form.get('next') or url_for('listing_detail', lid=lid)
    existing = (ShortlistItem.query
                .filter_by(user_id=current_user.id, listing_id=lid).first())
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Removed from your shortlist.', 'info')
    else:
        db.session.add(ShortlistItem(user_id=current_user.id, listing_id=lid))
        db.session.commit()
        flash('Saved to your shortlist.', 'success')
    return redirect(next_url)


# ---------------------------------------------------------------------------
# News, best cars, insurance, tax, owner reviews
# ---------------------------------------------------------------------------

@app.route('/car-news/')
def news_hub():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = 12
    q = NewsArticle.query.order_by(NewsArticle.published.desc())
    total = q.count()
    arts = q.offset((page - 1) * per_page).limit(per_page).all()
    return render_template('news_hub.html', arts=arts, total=total,
                           page=page, per_page=per_page)


@app.route('/car-news/<slug>/')
def news_article(slug):
    a = NewsArticle.query.filter_by(slug=slug).first()
    if not a:
        abort(404)
    more = (NewsArticle.query.filter(NewsArticle.id != a.id)
            .order_by(NewsArticle.published.desc()).limit(4).all())
    return render_template('news_article.html', a=a, more=more)


@app.route('/best-cars/')
def bestcars_hub():
    guides = Guide.query.order_by(Guide.slug).all()
    return render_template('bestcars_hub.html', guides=guides)


@app.route('/best-cars/<slug>/')
def bestcars_guide(slug):
    g = Guide.query.filter_by(slug=slug).first()
    if not g:
        abort(404)
    return render_template('guide.html', g=g)


@app.route('/car-insurance/insurance-groups/')
def ins_hub():
    makes = Make.query.order_by(Make.name).all()
    selected_make = request.args.get('make', '')
    make_models = []
    if selected_make:
        mk = Make.query.filter_by(slug=selected_make).first()
        if mk:
            make_models = (CarModel.query.filter_by(make_id=mk.id)
                           .order_by(CarModel.name).all())
    # cars in the cheapest insurance groups (lowest group per model <= 5)
    low_group_models = (CarModel.query
                         .join(Generation, Generation.model_id == CarModel.id)
                         .join(Derivative, Derivative.generation_id == Generation.id)
                         .filter(Derivative.insurance_group.isnot(None),
                                 Derivative.insurance_group <= 5)
                         .distinct().all())
    cheap_models = []
    for m in low_group_models:
        best = None
        best_g = None
        for g in m.generations:
            groups = [d.insurance_group for d in g.derivatives
                      if d.insurance_group is not None]
            if groups and min(groups) <= 5 and (best is None or min(groups) < best):
                best = min(groups)
                best_g = g
        if best is not None:
            cheap_models.append({'m': m, 'g': best_g, 'group': best})
    cheap_models.sort(key=lambda x: (x['group'], x['m'].make.name, x['m'].name))
    cheap_models = cheap_models[:12]
    return render_template('ins_hub.html', makes=makes,
                           make_models=make_models,
                           cheap_models=cheap_models)


@app.route('/<make>/<model>/<gen>/insurance-groups/')
def gen_insurance(make, model, gen):
    g = get_generation(make, model, gen)
    if not g:
        abort(404)
    derivs = g.derivatives
    trims = {}
    for d in derivs:
        trims.setdefault(d.trim or 'Other', []).append(d)
    return render_template('gen_insurance.html', m=g.model, g=g, trims=trims)


@app.route('/car-tax/')
def cartax_hub():
    makes = Make.query.order_by(Make.name).all()
    rates = TaxRate.query.order_by(TaxRate.id).all()
    selected_make = request.args.get('make', '')
    make_models = []
    if selected_make:
        mk = Make.query.filter_by(slug=selected_make).first()
        if mk:
            make_models = (CarModel.query.filter_by(make_id=mk.id)
                           .order_by(CarModel.name).all())
    return render_template('cartax_hub.html', makes=makes, rates=rates,
                           make_models=make_models)


@app.route('/<make>/<model>/<gen>/car-tax/')
def gen_cartax(make, model, gen):
    g = get_generation(make, model, gen)
    if not g:
        abort(404)
    derivs = g.derivatives
    return render_template('gen_cartax.html', m=g.model, g=g, derivs=derivs)


@app.route('/owner-reviews/')
def owner_hub():
    stats = OwnerStat.query.all()
    keys = {(s.make_slug, s.model_slug, s.gen_slug): s for s in stats}
    return render_template('owner_hub.html', stats=stats, keys=keys)


@app.route('/<make>/<model>/<gen>/owner-reviews/', methods=['GET', 'POST'])
def gen_owner_reviews(make, model, gen):
    g = get_generation(make, model, gen)
    if not g:
        abort(404)
    stat = (OwnerStat.query
            .filter_by(make_slug=g.model.make.slug, model_slug=g.model.slug,
                       gen_slug=g.slug).first())
    reviews = (OwnerReview.query
               .filter_by(make_slug=g.model.make.slug, model_slug=g.model.slug,
                          gen_slug=g.slug)
               .order_by(OwnerReview.published_date.desc()).all())
    if request.method == 'POST':
        rating = request.form.get('rating', type=int)
        author = (request.form.get('author') or '').strip()[:80] or 'Anonymous'
        deriv = (request.form.get('derivative') or '').strip()[:255]
        yp = (request.form.get('year_plate') or '').strip()[:12]
        bought = (request.form.get('bought') or '').strip()[:120]
        body = (request.form.get('body') or '').strip()[:4000]
        if not (rating and body and deriv):
            flash('Please provide a rating, your car version and your review.', 'error')
        else:
            paras = [p.strip() for p in re.split(r'\n+', body) if p.strip()]
            import json as _json
            rec = OwnerReview(
                make_slug=g.model.make.slug, model_slug=g.model.slug, gen_slug=g.slug,
                derivative_text=deriv, rating=min(5, max(1, rating)),
                author=author, published=BENCHMARK_TODAY.strftime('%d %B %Y'),
                published_date=BENCHMARK_TODAY, year_plate=yp, bought=bought,
                body_json=_json.dumps(paras), recommend=rating >= 4, is_seed=False)
            db.session.add(rec)
            db.session.commit()
            flash('Thank you — your owner review has been published.', 'success')
            return redirect(f"/{make}/{model}/{gen}/owner-reviews/#reviews")
    return render_template('gen_owner.html', m=g.model, g=g, stat=stat,
                           reviews=reviews)


@app.route('/owner-reviews/submit/')
def owner_submit():
    makes = Make.query.order_by(Make.name).all()
    return render_template('owner_submit.html', makes=makes)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@app.route('/search/')
def site_search():
    q = (request.args.get('q') or '').strip()
    tokens = token_split(q)
    results = {'models': [], 'news': [], 'guides': [], 'listings': []}
    counts = {}
    if tokens:
        models = CarModel.query.filter(CarModel.has_review == True).all()  # noqa: E712
        scored = []
        for m in models:
            text = f"{m.make.name} {m.name} {m.headline} {m.body_type} {m.review_intro or ''}"
            s = score_text(tokens, text)
            if s:
                scored.append((s, m))
        scored.sort(key=lambda x: (-x[0], x[1].name))
        results['models'] = [m for _, m in scored[:12]]
        news = NewsArticle.query.all()
        scored = []
        for a in news:
            s = score_text(tokens, f"{a.title} {a.standfirst}")
            if s:
                scored.append((s, a))
        scored.sort(key=lambda x: -x[0])
        results['news'] = [a for _, a in scored[:10]]
        guides = Guide.query.all()
        scored = []
        for gi in guides:
            s = score_text(tokens, gi.title)
            if s:
                scored.append((s, gi))
        scored.sort(key=lambda x: -x[0])
        results['guides'] = [gi for _, gi in scored[:8]]
        listings = Listing.query.all()
        scored = []
        for l in listings:
            s = score_text(tokens, f"{l.title} {l.derivative_text}")
            if s:
                scored.append((s, l))
        scored.sort(key=lambda x: -x[0])
        results['listings'] = [l for _, l in scored[:10]]
    counts = {k: len(v) for k, v in results.items()}
    return render_template('search_results.html', q=q, results=results,
                           counts=counts)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

@app.route('/my-parkers/login/', methods=['GET', 'POST'])
def account_login():
    if current_user.is_authenticated:
        return redirect(url_for('account_home'))
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        pw = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(pw):
            login_user(user)
            nxt = request.args.get('next')
            if nxt and nxt.startswith('/'):
                return redirect(nxt)
            return redirect(url_for('account_home'))
        flash('Email or password is incorrect.', 'error')
    return render_template('login.html')


@app.route('/my-parkers/register/', methods=['GET', 'POST'])
def account_register():
    if current_user.is_authenticated:
        return redirect(url_for('account_home'))
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        name = (request.form.get('name') or '').strip()[:80]
        pw = request.form.get('password') or ''
        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'error')
        elif len(pw) < 8:
            flash('Password must be at least 8 characters.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
        elif not name:
            flash('Please enter your name.', 'error')
        else:
            u = User(email=email, display_name=name)
            u.set_password(pw)
            db.session.add(u)
            db.session.commit()
            login_user(u)
            flash('Welcome to Parkers — your account is ready.', 'success')
            return redirect(url_for('account_home'))
    return render_template('register.html')


@app.route('/my-parkers/logout/')
@login_required
def account_logout():
    logout_user()
    return redirect('/')


@app.route('/my-parkers/')
@login_required
def account_home():
    return render_template('account.html', user=current_user)


@app.route('/my-parkers/shortlist/')
@login_required
def account_shortlist():
    items = current_user.shortlist
    return render_template('shortlist.html', items=items)


@app.route('/my-parkers/saved-valuations/')
@login_required
def account_saved_valuations():
    svs = current_user.saved_valuations
    decorated = []
    for sv in svs:
        d = sv.valuation.derivative
        g = d.generation
        decorated.append({'sv': sv, 'd': d, 'g': g, 'm': g.model})
    return render_template('saved_valuations.html', decorated=decorated)


@app.route('/my-parkers/profile/', methods=['GET', 'POST'])
@login_required
def account_profile():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()[:80]
        postcode = (request.form.get('postcode') or '').strip().upper()[:12]
        if not name:
            flash('Please enter your name.', 'error')
        else:
            current_user.display_name = name
            current_user.postcode = postcode
            db.session.commit()
            flash('Your profile has been updated.', 'success')
            return redirect(url_for('account_profile'))
    return render_template('profile.html', user=current_user)


# ---------------------------------------------------------------------------
# Static-ish pages + health + errors
# ---------------------------------------------------------------------------

@app.route('/about-us/')
def about_us():
    return render_template('about_us.html')


@app.route('/advertise/')
def advertise():
    return render_template('advertise.html')


@app.route('/terms-and-conditions/')
def terms_and_conditions():
    return render_template('terms_and_conditions.html')


@app.route('/car-advice/')
def car_advice():
    return render_template('car_advice.html')


@app.route('/contact-us/')
def contact_us():
    return render_template('contact_us.html')


@app.route('/_health')
def health():
    return jsonify({
        'ok': True,
        'site': 'parkers',
        'counts': {
            'makes': Make.query.count(),
            'models': CarModel.query.count(),
            'models_with_review': CarModel.query.filter_by(has_review=True).count(),
            'generations': Generation.query.count(),
            'derivatives': Derivative.query.count(),
            'valuations': Valuation.query.count(),
            'listings': Listing.query.count(),
            'news': NewsArticle.query.count(),
            'guides': Guide.query.count(),
            'owner_reviews': OwnerReview.query.count(),
        },
    })


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def seed_database():
    if CarModel.query.count() > 0:
        return
    from seed_data import seed_database as _seed
    _seed()


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    from seed_data import seed_benchmark_users as _seed
    _seed()


with app.app_context():
    # A fresh (empty) database gets its schema built deterministically: tables
    # first, then every secondary index in name-sorted order. SQLAlchemy issues
    # CREATE INDEX by iterating ``table.indexes`` — a set keyed by object identity
    # — so same-table indexes would otherwise swap root pages run to run and the
    # seed file bytes would not be reproducible. An existing database (the
    # runtime instance copy) is left untouched: create_all is a no-op and the
    # index normalization is skipped.
    from sqlalchemy import inspect as sa_inspect
    _schema_is_new = not sa_inspect(db.engine).get_table_names()
    if _schema_is_new:
        _deferred_indexes = []
        for _table in db.metadata.sorted_tables:
            _deferred_indexes.extend(sorted(_table.indexes, key=lambda i: i.name))
        for _index in _deferred_indexes:
            _index.table.indexes.remove(_index)
        db.create_all()
        with db.engine.begin() as _conn:
            for _index in _deferred_indexes:
                _cols = ', '.join(f'"{c.name}"' for c in _index.columns)
                _conn.exec_driver_sql(
                    f'CREATE INDEX "{_index.name}" ON "{_index.table.name}" ({_cols})')
        for _index in _deferred_indexes:
            _index.table.indexes.add(_index)
    else:
        db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 40125))
    app.run(host='0.0.0.0', port=port, debug=False)
