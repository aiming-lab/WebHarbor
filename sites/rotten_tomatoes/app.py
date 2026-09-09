#!/usr/bin/env python3
"""Rotten Tomatoes mirror — Flask app for WebHarbor."""
import json
import os
import re
import secrets
import unicodedata
from datetime import datetime, timezone
from copy import deepcopy
from types import SimpleNamespace
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_bcrypt import Bcrypt
from wtforms import FloatField, PasswordField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, ValidationError
from sqlalchemy import event as sqlalchemy_event, func, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARK_NOW = datetime(2026, 9, 7, 12, 0, 0)
SEEDED_REVIEW_NAMES = {
    2: 'Angel G', 3: 'Patrick V', 5: 'Patricia P', 7: 'Ricardo', 9: 'Jesus',
    10: 'Luie', 12: 'Brandon', 13: 'Lysah', 14: 'Joseph', 15: 'Sergio Z',
    16: 'Carlos', 17: 'Ryan M', 18: 'Lexie B', 19: 'Morgan P', 20: 'kassandra',
    21: 'Tyler', 22: 'Alanna T', 23: 'Chad W', 24: 'Timothy W', 25: 'Chris P',
    26: 'Del', 27: 'Marie', 28: 'Hunter',
}
SEEDED_REVIEW_IDS = frozenset(SEEDED_REVIEW_NAMES)

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config['SECRET_KEY'] = os.environ.get('ROTTEN_TOMATOES_SECRET_KEY') or secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'rotten_tomatoes.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)


@sqlalchemy_event.listens_for(Engine, 'connect')
def enable_sqlite_foreign_keys(connection, _record):
    cursor = connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to access this page.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)


# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    watchlist_items = db.relationship('WatchlistItem', backref='user', lazy=True, cascade='all, delete-orphan')
    ratings = db.relationship('UserRating', backref='user', lazy=True, cascade='all, delete-orphan')
    audience_reviews = db.relationship('AudienceReview', backref='user', lazy=True, cascade='all, delete-orphan')


class Genre(db.Model):
    __tablename__ = 'genres'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)


movie_genres = db.Table('movie_genres',
    db.Column('movie_id', db.Integer, db.ForeignKey('movies.id'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id'), primary_key=True)
)


class ContentSnapshot(db.Model):
    __tablename__ = 'content_snapshots'
    name = db.Column(db.String(32), primary_key=True)
    document = db.Column(db.JSON, nullable=False)


class Movie(db.Model):
    __tablename__ = 'movies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    runtime_minutes = db.Column(db.Integer)
    synopsis = db.Column(db.Text, default='')
    poster_image = db.Column(db.String(300), default='')
    tomatometer = db.Column(db.Integer)  # 0-100
    audience_score = db.Column(db.Integer)  # 0-100
    certified_fresh = db.Column(db.Boolean, default=False)
    pg_rating = db.Column(db.String(10))
    director_name = db.Column(db.String(120), default='')
    studio = db.Column(db.String(120), default='')
    streaming_platform = db.Column(db.String(100), default='')
    watch_offers = db.Column(db.Text)
    watch_description = db.Column(db.Text)
    available_at_home = db.Column(db.Boolean, default=False)
    consensus = db.Column(db.Text, default='')  # critics consensus
    audience_consensus = db.Column(db.Text, default='')
    box_office = db.Column(db.String(50), default='')
    release_date = db.Column(db.String(20), default='')
    in_theaters = db.Column(db.Boolean, default=False)
    producer = db.Column(db.String(500), default='')
    screenwriter = db.Column(db.String(500), default='')
    production_co = db.Column(db.String(500), default='')
    distributor = db.Column(db.String(200), default='')
    original_language = db.Column(db.String(50), default='')
    release_date_streaming = db.Column(db.String(50), default='')
    runtime_display = db.Column(db.String(20), default='')
    created_at = db.Column(db.DateTime, default=utcnow)

    genres = db.relationship('Genre', secondary=movie_genres, lazy='subquery',
                             backref=db.backref('movies', lazy=True))
    cast_members = db.relationship('MovieCast', backref='movie', lazy=True,
                                   cascade='all, delete-orphan',
                                   order_by='MovieCast.billing_order')
    critic_reviews = db.relationship('CriticReview', backref='movie', lazy=True,
                                     cascade='all, delete-orphan')
    audience_reviews = db.relationship('AudienceReview', backref='movie', lazy=True,
                                       cascade='all, delete-orphan')
    watchlist_items = db.relationship('WatchlistItem', backref='movie', lazy=True,
                                      cascade='all, delete-orphan')
    user_ratings = db.relationship('UserRating', backref='movie', lazy=True,
                                    cascade='all, delete-orphan')

    @property
    def watch_options(self):
        return json.loads(self.watch_offers) if self.watch_offers else []

    @property
    def subscription_platforms(self):
        return [value.strip() for value in (self.streaming_platform or '').split(',') if value.strip()]

    @property
    def hero_image(self):
        relative_path = f'images/hero/{self.slug}.jpg'
        if os.path.isfile(os.path.join(BASE_DIR, 'static', relative_path)):
            return f'/static/{relative_path}'
        return None

    @property
    def tomatometer_icon(self):
        if self.tomatometer is None:
            return ''
        if self.certified_fresh:
            return '🏆'
        return '🍅' if self.tomatometer >= 60 else '🟢'

    @property
    def audience_icon(self):
        return '🍿' if self.audience_score is not None else ''

    @property
    def tomatometer_status(self):
        if self.tomatometer is None:
            return 'empty'
        if self.certified_fresh:
            return 'certified-fresh'
        return 'fresh' if self.tomatometer >= 60 else 'rotten'

    @property
    def audience_status(self):
        if self.audience_score is None:
            return 'empty'
        return 'upright' if self.audience_score >= 60 else 'spilled'


class Person(db.Model):
    __tablename__ = 'persons'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(150), unique=True, nullable=False)
    bio = db.Column(db.Text, default='')
    photo = db.Column(db.String(300), default='')
    birthplace = db.Column(db.String(200), default='')
    birth_date = db.Column(db.String(20), default='')

    cast_entries = db.relationship('MovieCast', backref='person', lazy=True)

    @property
    def filmography(self):
        movies = {}
        for credit in self.cast_entries:
            if credit.movie is None:
                continue
            entry = movies.setdefault(credit.movie_id, {
                'movie': credit.movie, 'characters': [], 'roles': []})
            for key, value in (('characters', credit.character_name), ('roles', credit.role_type)):
                if value and value not in entry[key]:
                    entry[key].append(value)
        return sorted((SimpleNamespace(movie=entry['movie'],
                                       character_name=', '.join(entry['characters']),
                                       role_type=', '.join(entry['roles']))
                       for entry in movies.values()),
                      key=lambda entry: (-entry.movie.year, entry.movie.title))

    @property
    def highest_rated_movie(self):
        movies = [c.movie for c in self.cast_entries if c.movie and c.movie.tomatometer is not None]
        if not movies:
            return None
        return max(movies, key=lambda m: m.tomatometer)

    @property
    def lowest_rated_movie(self):
        movies = [c.movie for c in self.cast_entries if c.movie and c.movie.tomatometer is not None]
        if not movies:
            return None
        return min(movies, key=lambda m: m.tomatometer)


class MovieCast(db.Model):
    __tablename__ = 'movie_cast'
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey('persons.id'), nullable=False)
    character_name = db.Column(db.String(150), default='')
    role_type = db.Column(db.String(20), default='actor')  # actor, director, producer
    billing_order = db.Column(db.Integer, default=0)


class CriticReview(db.Model):
    __tablename__ = 'critic_reviews'
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    critic_name = db.Column(db.String(120), nullable=False)
    publication = db.Column(db.String(120), nullable=False)
    text = db.Column(db.Text, nullable=False)
    fresh = db.Column(db.Boolean, default=True)
    score = db.Column(db.String(20), default='')  # e.g. "8/10", "B+", "4/5"
    review_date = db.Column(db.String(20), default='')


class AudienceReview(db.Model):
    __tablename__ = 'audience_reviews'
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Float, default=3.0)  # 0.5-5.0 stars
    text = db.Column(db.Text, default='')
    review_date = db.Column(db.DateTime, default=utcnow)

    __table_args__ = (db.UniqueConstraint('movie_id', 'user_id', name='uq_user_movie_review'),)


class UserRating(db.Model):
    __tablename__ = 'user_ratings'
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Float, default=3.0)  # 0.5-5.0
    created_at = db.Column(db.DateTime, default=utcnow)

    __table_args__ = (db.UniqueConstraint('movie_id', 'user_id', name='uq_user_movie_rating'),)


class WatchlistItem(db.Model):
    __tablename__ = 'watchlist_items'
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=utcnow)

    __table_args__ = (db.UniqueConstraint('movie_id', 'user_id', name='uq_user_movie_watchlist'),)


# ──────────────────────────────────────────────
# Auth setup
# ──────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


@app.context_processor
def inject_csrf():
    return dict(csrf_token=generate_csrf)


@app.context_processor
def inject_globals():
    genres = Genre.query.order_by(Genre.name).all()
    watchlist_ids = set()
    if current_user.is_authenticated:
        watchlist_ids = {w.movie_id for w in WatchlistItem.query.filter_by(user_id=current_user.id).all()}
    return dict(all_genres=genres, user_watchlist_ids=watchlist_ids,
                header_links=_content_document('homepage').get('header_links', []),
                trending=_content_document('homepage').get('trending', []),
                audience_review_name=lambda review: SEEDED_REVIEW_NAMES.get(review.id, review.user.name))


# ──────────────────────────────────────────────
# Forms
# ──────────────────────────────────────────────

def password_byte_limit(form, field):
    if len(field.data.encode('utf-8')) > 72:
        raise ValidationError('Password must be at most 72 UTF-8 bytes.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), password_byte_limit])


class RegisterForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6), password_byte_limit])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])


class ReviewForm(FlaskForm):
    score = FloatField('Rating', validators=[DataRequired(), NumberRange(min=0.5, max=5.0)])
    text = TextAreaField('Review', validators=[DataRequired(), Length(min=10, max=2000)])


class RatingForm(FlaskForm):
    score = FloatField('Rating', validators=[DataRequired(), NumberRange(min=0.5, max=5.0)])


# ──────────────────────────────────────────────
# Search helper — scored token overlap
# ──────────────────────────────────────────────

def request_arg(name, default='', max_length=200):
    values = request.args.getlist(name)
    if len(values) > 1:
        abort(400)
    value = values[0] if values else default
    if not isinstance(value, str) or len(value) > max_length:
        abort(400)
    return value


def local_redirect_target(target, fallback):
    """Keep return navigation on this origin and return a path-only Location."""
    if not target:
        return fallback
    decoded = unquote(target)
    if ('\\' in decoded or any(ord(char) < 32 or ord(char) == 127 for char in decoded)
            or decoded.strip().startswith('//')):
        return fallback
    try:
        origin = urlsplit(request.host_url)
        destination = urlsplit(urljoin(request.url, target.strip()))
        if (destination.scheme not in ('http', 'https')
                or destination.scheme != origin.scheme
                or destination.netloc.lower() != origin.netloc.lower()
                or unquote(destination.path).startswith('//')):
            return fallback
    except ValueError:
        return fallback
    return urlunsplit(('', '', destination.path or '/', destination.query, destination.fragment))


def tokenize(text):
    """Split text into lowercase alphanumeric tokens."""
    normalized = unicodedata.normalize('NFKD', text.casefold())
    plain = ''.join(char for char in normalized if not unicodedata.combining(char))
    return re.findall(r'[a-z0-9]+', plain)


def token_overlap_score(query_tokens, target_tokens):
    """Score based on fraction of query tokens found in target."""
    if not query_tokens or not target_tokens:
        return 0.0
    target_set = set(target_tokens)
    hits = sum(1 for t in query_tokens if t in target_set)
    return hits / len(query_tokens)


def search_movies(query, limit=30):
    """Search the local title, genre and credited-person catalog."""
    if not query or not query.strip():
        return []
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    movies = Movie.query.all()
    scored = []
    for m in movies:
        genre_text = ' '.join(g.name for g in m.genres)
        people_text = ' '.join(credit.person.name for credit in m.cast_members)
        target = f"{m.title} {m.director_name or ''} {m.producer or ''} {m.screenwriter or ''} {people_text} {genre_text} {m.year}"
        target_tokens = tokenize(target)
        score = token_overlap_score(query_tokens, target_tokens)
        if score > 0:
            scored.append((score, m))

    scored.sort(key=lambda x: (-x[0], x[1].title))
    return [m for _, m in scored[:limit]]


def search_people(query, limit=20):
    """Search people by scored token overlap on name."""
    if not query or not query.strip():
        return []
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    people = Person.query.all()
    scored = []
    for p in people:
        target_tokens = tokenize(p.name)
        score = token_overlap_score(query_tokens, target_tokens)
        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: (-x[0], x[1].name))
    return [p for _, p in scored[:limit]]


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

def _content_document(name):
    """Read the immutable source snapshot from this site's seed database."""
    if name not in ('homepage', 'tv_catalog', 'feature_catalog'):
        raise ValueError('Unknown content document')
    snapshot = db.session.get(ContentSnapshot, name)
    return snapshot.document if snapshot else {}


def _home_view():
    home = deepcopy(_content_document('homepage'))
    movies = {movie.slug: movie for movie in Movie.query.all()}
    for section in home.get('sections', []):
        for item in section['items']:
            movie = movies.get(item.get('movie_slug'))
            if movie:
                # Keep local cards/details consistent. Membership and rank come
                # from the captured homepage, never a substitute score sort.
                item.update(movie_id=movie.id, title=movie.title,
                            tomatometer=movie.tomatometer,
                            audience_score=movie.audience_score,
                            certified_fresh=movie.certified_fresh)
                if not item.get('image'):
                    item['image'] = movie.poster_image
    return home


@app.route('/')
def index():
    return render_template('index.html', home=_home_view())


@app.route('/browse/home/<section_id>/')
def curated_list(section_id):
    home = _home_view()
    section = next((row for row in home.get('sections', []) if row['id'] == section_id), None)
    if section is None:
        abort(404)
    return render_template('content_list.html', section=section,
                           captured_at=home.get('captured_at', ''))


@app.route('/browse/tv/')
def browse_tv():
    rows = _content_document('tv_catalog').get('records', [])
    section = {'title': 'TV Shows', 'kind': 'posters', 'description': '', 'items': rows}
    return render_template('content_list.html', section=section, captured_at='')


@app.route('/tv/<path:media_path>')
def tv_detail(media_path):
    path = '/tv/' + media_path.rstrip('/')
    show = next((row for row in _content_document('tv_catalog').get('records', [])
                 if row['path'].rstrip('/') == path), None)
    if show is None:
        abort(404)
    return render_template('tv_detail.html', show=show)


@app.route('/news/')
def news():
    section = {'title': 'News & Features', 'kind': 'promos', 'description': '',
               'items': _content_document('feature_catalog').get('records', [])}
    return render_template('content_list.html', section=section, captured_at='')


@app.route('/news/<feature_id>')
def feature_detail(feature_id):
    feature = next((row for row in _content_document('feature_catalog').get('records', [])
                    if row['id'] == feature_id), None)
    if feature is None:
        abort(404)
    return render_template('feature_detail.html', feature=feature)


@app.route('/about')
@app.route('/help')
@app.route('/scores')
def site_information():
    return render_template('site_information.html', page=request.path.strip('/'))


@app.route('/search')
def search():
    """Search movies and people."""
    query = (request_arg('q') or request_arg('search')).strip()
    if not query:
        return render_template('search_results.html', query='', movies=[], people=[], shows=[])
    movies = search_movies(query)
    people = search_people(query)
    shows = [row for row in _content_document('tv_catalog').get('records', [])
             if token_overlap_score(tokenize(query), tokenize(row['title'])) > 0]
    return render_template('search_results.html', query=query, movies=movies, people=people, shows=shows)


@app.route('/browse/movies_in_theaters/')
def browse_in_theaters():
    """Browse movies currently in theaters."""
    return _browse_movies(Movie.query.filter_by(in_theaters=True), 'In Theaters', 'movies_in_theaters')


@app.route('/browse/movies_at_home/')
def browse_at_home():
    """Browse movies available for streaming."""
    return _browse_movies(Movie.query.filter_by(available_at_home=True), 'Streaming at Home', 'movies_at_home')


@app.route('/browse/movies/')
def browse_all():
    """Browse all movies."""
    return _browse_movies(Movie.query, 'All Movies', 'movies')


def _browse_movies(base_query, title, browse_type):
    """Common browse logic with filters."""
    # Genre filter
    genre_slug = request_arg('genre', max_length=50)
    if genre_slug:
        genre = Genre.query.filter_by(slug=genre_slug).first()
        if genre is None:
            abort(400)
        base_query = base_query.filter(Movie.genres.any(Genre.id == genre.id))

    # Certified fresh filter
    cf = request_arg('certified_fresh', max_length=5)
    if cf not in ('', 'true'):
        abort(400)
    if cf == 'true':
        base_query = base_query.filter_by(certified_fresh=True)

    # Rating filter
    pg = request_arg('rating', max_length=5)
    if pg not in ('', 'G', 'PG', 'PG-13', 'R'):
        abort(400)
    if pg:
        base_query = base_query.filter_by(pg_rating=pg)

    # Year filter
    year = request_arg('year', max_length=4)
    if year and (not year.isdigit() or not 1880 <= int(year) <= 2100):
        abort(400)
    if year:
        base_query = base_query.filter_by(year=int(year))

    # Streaming platform filter
    platform = request_arg('platform', max_length=100)
    known_platforms = sorted({value.strip() for row in db.session.query(Movie.streaming_platform).filter(
        Movie.streaming_platform != ''
    ).distinct().all() for value in row[0].split(',') if value.strip()})
    if platform and platform not in known_platforms:
        abort(400)
    if platform:
        membership = ',' + func.replace(Movie.streaming_platform, ', ', ',') + ','
        base_query = base_query.filter(func.instr(membership, ',' + platform + ',') > 0)

    # Sort
    sort = request_arg('sort', 'popular', max_length=20)
    if sort not in ('popular', 'newest', 'tomatometer', 'audience', 'a_z'):
        abort(400)
    if sort == 'newest':
        base_query = base_query.order_by(Movie.year.desc(), Movie.title, Movie.id)
    elif sort == 'tomatometer':
        base_query = base_query.order_by(Movie.tomatometer.is_(None), Movie.tomatometer.desc(), Movie.title, Movie.id)
    elif sort == 'audience':
        base_query = base_query.order_by(Movie.audience_score.is_(None), Movie.audience_score.desc(), Movie.title, Movie.id)
    elif sort == 'a_z':
        base_query = base_query.order_by(Movie.title, Movie.id)
    else:  # popular
        base_query = base_query.order_by(Movie.audience_score.is_(None), Movie.audience_score.desc(),
                                         Movie.tomatometer.is_(None), Movie.tomatometer.desc(), Movie.title, Movie.id)

    movies = base_query.all()
    # Homepage provider links refer to captured viewing offers, including rental
    # services. The existing subscription-only platform filter stays distinct.
    provider = request_arg('provider', max_length=40)
    provider_names = {'fandango': 'Fandango at Home', 'netflix': 'Netflix',
                      'amazon-prime-video-us': 'Prime Video', 'hbo-max': 'HBO Max'}
    if provider:
        if provider not in provider_names:
            abort(400)
        movies = [movie for movie in movies
                  if any(offer.get('icon') == provider for offer in movie.watch_options)]
        title = title + ' — ' + provider_names[provider]
    genres = Genre.query.order_by(Genre.name).all()
    platforms = known_platforms

    return render_template('browse.html',
                           title=title,
                           browse_type=browse_type,
                           movies=movies,
                           genres=genres,
                           platforms=platforms,
                           current_genre=genre_slug,
                           current_sort=sort,
                           current_cf=cf,
                           current_rating=pg,
                           current_year=year,
                           current_platform=platform,
                           current_provider=provider)


@app.route('/m/<slug>')
def movie_detail(slug):
    """Movie detail page."""
    movie = Movie.query.filter_by(slug=slug).first_or_404()
    return _render_movie_detail(movie)


def _render_movie_detail(movie, review_form=None, rating_form=None):
    critic_reviews = CriticReview.query.filter_by(movie_id=movie.id).order_by(CriticReview.review_date.desc()).all()
    audience_reviews = AudienceReview.query.filter_by(movie_id=movie.id).order_by(AudienceReview.review_date.desc()).all()
    cast = MovieCast.query.filter_by(movie_id=movie.id).order_by(MovieCast.billing_order).all()
    directors = [c for c in cast if c.role_type == 'director']
    actors = [c for c in cast if c.role_type == 'actor']

    # Similar movies — same primary genre
    similar = []
    if movie.genres:
        primary_genre = movie.genres[0]
        similar = Movie.query.filter(
            Movie.id != movie.id,
            Movie.genres.any(Genre.id == primary_genre.id)
        ).order_by(Movie.tomatometer.desc()).limit(6).all()

    # User's rating/watchlist status
    user_rating = None
    in_watchlist = False
    if current_user.is_authenticated:
        user_rating = UserRating.query.filter_by(
            movie_id=movie.id, user_id=current_user.id
        ).first()
        in_watchlist = WatchlistItem.query.filter_by(
            movie_id=movie.id, user_id=current_user.id
        ).first() is not None

    if review_form is None:
        review_form = ReviewForm(formdata=None)
    if rating_form is None:
        rating_form = RatingForm(formdata=None)

    return render_template('movie_detail.html',
                           movie=movie,
                           critic_reviews=critic_reviews,
                           audience_reviews=audience_reviews,
                           directors=directors,
                           actors=actors,
                           similar_movies=similar,
                           user_rating=user_rating,
                           in_watchlist=in_watchlist,
                           review_form=review_form,
                           rating_form=rating_form)


@app.route('/celebrity/<slug>')
def celebrity_detail(slug):
    """Celebrity detail page with filmography."""
    person = Person.query.filter_by(slug=slug).first_or_404()

    filmography = person.filmography
    sort = request_arg('sort', 'newest', max_length=20)
    if sort not in ('newest', 'oldest', 'critics_highest', 'critics_lowest', 'audience_highest', 'audience_lowest'):
        abort(400)
    if sort == 'oldest':
        filmography.sort(key=lambda entry: (entry.movie.year, entry.movie.title))
    elif sort in ('critics_highest', 'critics_lowest', 'audience_highest', 'audience_lowest'):
        field = 'tomatometer' if sort.startswith('critics') else 'audience_score'
        descending = sort.endswith('highest')

        def score_order(entry):
            value = getattr(entry.movie, field)
            return (value is None, -(value or 0) if descending else (value or 0), entry.movie.title)

        filmography.sort(key=score_order)

    highest = person.highest_rated_movie
    lowest = person.lowest_rated_movie

    return render_template('celebrity.html',
                           person=person,
                           filmography=filmography,
                           highest_rated=highest,
                           lowest_rated=lowest,
                           current_sort=sort)


# ── Auth routes ──

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            session.clear()
            login_user(user)
            flash('Welcome back!', 'success')
            next_page = request_arg('next', max_length=500)
            return redirect(local_redirect_target(next_page, url_for('index')))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        name = form.name.data.strip()
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('Unable to create an account with the supplied details.', 'danger')
        else:
            hashed = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            result = db.session.execute(sqlite_insert(User).values(
                email=email, password_hash=hashed, name=name
            ).on_conflict_do_nothing(index_elements=['email']))
            db.session.commit()
            if result.rowcount:
                user = User.query.filter_by(email=email).one()
                session.clear()
                login_user(user)
                flash('Account created!', 'success')
                return redirect(url_for('index'))
            flash('Unable to create an account with the supplied details.', 'danger')
    return render_template('register.html', form=form)


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ── Account / Profile routes ──

@app.route('/account')
@login_required
def account():
    rating_count = UserRating.query.filter_by(user_id=current_user.id).count()
    review_count = AudienceReview.query.filter_by(user_id=current_user.id).filter(
        AudienceReview.id.not_in(SEEDED_REVIEW_IDS)).count()
    watchlist_count = WatchlistItem.query.filter_by(user_id=current_user.id).count()
    return render_template('account.html', rating_count=rating_count,
                           review_count=review_count, watchlist_count=watchlist_count)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    if request.method == 'POST':
        new_name = request.form.get('name', '').strip()
        if 2 <= len(new_name) <= 120:
            current_user.name = new_name
            db.session.commit()
            flash('Profile updated.', 'success')
            return redirect(url_for('account'))
        else:
            flash('Name must be between 2 and 120 characters.', 'danger')
    return render_template('account_edit.html')


@app.route('/user/ratings')
@login_required
def user_ratings():
    ratings = UserRating.query.filter_by(user_id=current_user.id)\
        .order_by(UserRating.created_at.desc()).all()
    return render_template('user_ratings.html', ratings=ratings)


@app.route('/user/reviews')
@login_required
def user_reviews():
    reviews = AudienceReview.query.filter_by(user_id=current_user.id).filter(
        AudienceReview.id.not_in(SEEDED_REVIEW_IDS)).order_by(AudienceReview.review_date.desc()).all()
    return render_template('user_reviews.html', reviews=reviews)


# ── Watchlist routes ──

@app.route('/user/watchlist')
@login_required
def watchlist():
    items = WatchlistItem.query.filter_by(user_id=current_user.id).order_by(WatchlistItem.added_at.desc()).all()
    movies = [item.movie for item in items if item.movie]
    return render_template('watchlist.html', movies=movies)


@app.route('/user/watchlist/add/<int:movie_id>', methods=['POST'])
@login_required
def add_to_watchlist(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    result = db.session.execute(sqlite_insert(WatchlistItem).values(
        movie_id=movie_id, user_id=current_user.id
    ).on_conflict_do_nothing(index_elements=['movie_id', 'user_id']))
    db.session.commit()
    if result.rowcount:
        flash(f'Added "{movie.title}" to your watchlist.', 'success')
    else:
        flash(f'"{movie.title}" is already in your watchlist.', 'info')
    next_url = request.form.get('next') or request.referrer or url_for('movie_detail', slug=movie.slug)
    return redirect(local_redirect_target(next_url, url_for('movie_detail', slug=movie.slug)))


@app.route('/user/watchlist/remove/<int:movie_id>', methods=['POST'])
@login_required
def remove_from_watchlist(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    item = WatchlistItem.query.filter_by(movie_id=movie_id, user_id=current_user.id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash(f'Removed "{movie.title}" from your watchlist.', 'success')
    fallback = url_for('movie_detail', slug=movie.slug)
    return redirect(local_redirect_target(request.form.get('next'), fallback))


# ── Rating & Review routes ──

@app.route('/m/<slug>/rate', methods=['POST'])
@login_required
def rate_movie(slug):
    movie = Movie.query.filter_by(slug=slug).first_or_404()
    form = RatingForm()
    if form.validate_on_submit():
        statement = sqlite_insert(UserRating).values(
            movie_id=movie.id, user_id=current_user.id, score=form.score.data
        )
        db.session.execute(statement.on_conflict_do_update(
            index_elements=['movie_id', 'user_id'], set_={'score': statement.excluded.score}
        ))
        db.session.commit()
        flash(f'Rated "{movie.title}" {form.score.data}/5 stars.', 'success')
        return redirect(url_for('movie_detail', slug=slug))
    return _render_movie_detail(movie, rating_form=form), 422


@app.route('/m/<slug>/review', methods=['POST'])
@login_required
def review_movie(slug):
    movie = Movie.query.filter_by(slug=slug).first_or_404()
    form = ReviewForm()
    if form.validate_on_submit():
        result = db.session.execute(sqlite_insert(AudienceReview).values(
            movie_id=movie.id, user_id=current_user.id,
            score=form.score.data, text=form.text.data
        ).on_conflict_do_nothing(index_elements=['movie_id', 'user_id']))
        db.session.commit()
        if result.rowcount:
            flash('Review submitted!', 'success')
        else:
            flash('You have already reviewed this movie.', 'info')
        return redirect(url_for('movie_detail', slug=slug))
    return _render_movie_detail(movie, review_form=form), 422


@app.route('/user/reviews/delete/<int:review_id>', methods=['POST'])
@login_required
def delete_review(review_id):
    review = AudienceReview.query.get_or_404(review_id)
    if review.id in SEEDED_REVIEW_IDS or review.user_id != current_user.id:
        flash('You can only delete your own reviews.', 'danger')
        return redirect(url_for('user_reviews'))
    movie_title = review.movie.title
    db.session.delete(review)
    db.session.commit()
    flash(f'Your review for "{movie_title}" has been deleted.', 'success')
    return redirect(url_for('user_reviews'))


# ── Health check ──

@app.route('/_health')
def health():
    try:
        movie_count = Movie.query.count()
        person_count = Person.query.count()
        return jsonify({
            'ok': True,
            'site': 'rotten_tomatoes',
            'movies': movie_count,
            'persons': person_count
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ──────────────────────────────────────────────
# DB init & seed
# ──────────────────────────────────────────────

def init_db():
    """Create tables and seed data."""
    db.create_all()
    for statement in (
        'CREATE INDEX IF NOT EXISTS ix_movies_title ON movies(title)',
        'CREATE INDEX IF NOT EXISTS ix_movies_year ON movies(year)',
        'CREATE INDEX IF NOT EXISTS ix_persons_name ON persons(name)',
    ):
        db.session.execute(text(statement))
    db.session.commit()
    from seed_data import seed_all
    seed_all(db, Genre, Movie, Person, MovieCast, CriticReview, AudienceReview, User, UserRating, WatchlistItem, ContentSnapshot)


with app.app_context():
    init_db()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
