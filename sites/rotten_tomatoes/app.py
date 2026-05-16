#!/usr/bin/env python3
"""Rotten Tomatoes mirror — Flask app for WebHarbor."""
import os
import re
import math
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort, g, make_response)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_bcrypt import Bcrypt
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, SelectField, FloatField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange
from sqlalchemy import or_, func, and_

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config['SECRET_KEY'] = 'rotten-tomatoes-mirror-secret-key-change-in-prod'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'rotten_tomatoes.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to access this page.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)


# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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


class Movie(db.Model):
    __tablename__ = 'movies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    runtime_minutes = db.Column(db.Integer, default=0)
    synopsis = db.Column(db.Text, default='')
    poster_image = db.Column(db.String(300), default='')
    tomatometer = db.Column(db.Integer, default=0)  # 0-100
    audience_score = db.Column(db.Integer, default=0)  # 0-100
    certified_fresh = db.Column(db.Boolean, default=False)
    pg_rating = db.Column(db.String(10), default='PG-13')
    director_name = db.Column(db.String(120), default='')
    studio = db.Column(db.String(120), default='')
    streaming_platform = db.Column(db.String(100), default='')
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    def tomatometer_icon(self):
        if self.certified_fresh:
            return '🏆'
        return '🍅' if self.tomatometer >= 60 else '🟢'

    @property
    def audience_icon(self):
        return '🍿'

    @property
    def tomatometer_status(self):
        if self.certified_fresh:
            return 'certified-fresh'
        return 'fresh' if self.tomatometer >= 60 else 'rotten'

    @property
    def audience_status(self):
        return 'upright' if self.audience_score >= 60 else 'spilled'


class Person(db.Model):
    __tablename__ = 'persons'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    slug = db.Column(db.String(150), unique=True, nullable=False, index=True)
    bio = db.Column(db.Text, default='')
    photo = db.Column(db.String(300), default='')
    birthplace = db.Column(db.String(200), default='')
    birth_date = db.Column(db.String(20), default='')

    cast_entries = db.relationship('MovieCast', backref='person', lazy=True)

    @property
    def filmography(self):
        entries = sorted(self.cast_entries, key=lambda c: c.movie.year if c.movie else 0, reverse=True)
        return entries

    @property
    def highest_rated_movie(self):
        movies = [c.movie for c in self.cast_entries if c.movie]
        if not movies:
            return None
        return max(movies, key=lambda m: m.tomatometer)

    @property
    def lowest_rated_movie(self):
        movies = [c.movie for c in self.cast_entries if c.movie]
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
    review_date = db.Column(db.DateTime, default=datetime.utcnow)


class UserRating(db.Model):
    __tablename__ = 'user_ratings'
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Float, default=3.0)  # 0.5-5.0
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('movie_id', 'user_id', name='uq_user_movie_rating'),)


class WatchlistItem(db.Model):
    __tablename__ = 'watchlist_items'
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('movie_id', 'user_id', name='uq_user_movie_watchlist'),)


# ──────────────────────────────────────────────
# Auth setup
# ──────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_csrf():
    return dict(csrf_token=generate_csrf)


@app.context_processor
def inject_globals():
    genres = Genre.query.order_by(Genre.name).all()
    watchlist_ids = set()
    if current_user.is_authenticated:
        watchlist_ids = {w.movie_id for w in WatchlistItem.query.filter_by(user_id=current_user.id).all()}
    return dict(all_genres=genres, user_watchlist_ids=watchlist_ids)


# ──────────────────────────────────────────────
# Forms
# ──────────────────────────────────────────────

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])


class ReviewForm(FlaskForm):
    score = FloatField('Rating', validators=[DataRequired(), NumberRange(min=0.5, max=5.0)])
    text = TextAreaField('Review', validators=[DataRequired(), Length(min=10, max=2000)])


class RatingForm(FlaskForm):
    score = FloatField('Rating', validators=[DataRequired(), NumberRange(min=0.5, max=5.0)])


# ──────────────────────────────────────────────
# Search helper — scored token overlap
# ──────────────────────────────────────────────

def tokenize(text):
    """Split text into lowercase alphanumeric tokens."""
    return re.findall(r'[a-z0-9]+', text.lower())


def token_overlap_score(query_tokens, target_tokens):
    """Score based on fraction of query tokens found in target."""
    if not query_tokens or not target_tokens:
        return 0.0
    target_set = set(target_tokens)
    hits = sum(1 for t in query_tokens if t in target_set)
    return hits / len(query_tokens)


def search_movies(query, limit=30):
    """Search movies by scored token overlap on title, director, genre names."""
    if not query or not query.strip():
        return []
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    movies = Movie.query.all()
    scored = []
    for m in movies:
        genre_text = ' '.join(g.name for g in m.genres)
        target = f"{m.title} {m.director_name} {genre_text} {m.year}"
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

@app.route('/')
def index():
    """Homepage with movie sections."""
    new_movies = Movie.query.filter_by(in_theaters=True).order_by(Movie.release_date.desc()).limit(12).all()
    streaming = Movie.query.filter(Movie.streaming_platform != '').order_by(func.random()).limit(12).all()
    certified = Movie.query.filter_by(certified_fresh=True).order_by(Movie.tomatometer.desc()).limit(12).all()
    # Top box office — movies in theaters sorted by box_office
    top_box = Movie.query.filter_by(in_theaters=True).order_by(Movie.box_office.desc()).limit(10).all()
    popular = Movie.query.order_by(Movie.audience_score.desc()).limit(12).all()
    return render_template('index.html',
                           new_movies=new_movies,
                           streaming_movies=streaming,
                           certified_movies=certified,
                           top_box_office=top_box,
                           popular_movies=popular)


@app.route('/search')
def search():
    """Search movies and people."""
    query = (request.args.get('q') or request.args.get('search') or '').strip()
    if not query:
        return render_template('search_results.html', query='', movies=[], people=[])
    movies = search_movies(query)
    people = search_people(query)
    return render_template('search_results.html', query=query, movies=movies, people=people)


@app.route('/browse/movies_in_theaters/')
def browse_in_theaters():
    """Browse movies currently in theaters."""
    return _browse_movies(Movie.query.filter_by(in_theaters=True), 'In Theaters', 'movies_in_theaters')


@app.route('/browse/movies_at_home/')
def browse_at_home():
    """Browse movies available for streaming."""
    return _browse_movies(Movie.query.filter(Movie.streaming_platform != ''), 'Streaming at Home', 'movies_at_home')


@app.route('/browse/movies/')
def browse_all():
    """Browse all movies."""
    return _browse_movies(Movie.query, 'All Movies', 'movies')


def _browse_movies(base_query, title, browse_type):
    """Common browse logic with filters."""
    # Genre filter
    genre_slug = request.args.get('genre', '')
    if genre_slug:
        genre = Genre.query.filter_by(slug=genre_slug).first()
        if genre:
            base_query = base_query.filter(Movie.genres.any(Genre.id == genre.id))

    # Certified fresh filter
    cf = request.args.get('certified_fresh', '')
    if cf == 'true':
        base_query = base_query.filter_by(certified_fresh=True)

    # Rating filter
    pg = request.args.get('rating', '')
    if pg in ('G', 'PG', 'PG-13', 'R'):
        base_query = base_query.filter_by(pg_rating=pg)

    # Year filter
    year = request.args.get('year', '')
    if year and year.isdigit():
        base_query = base_query.filter_by(year=int(year))

    # Streaming platform filter
    platform = request.args.get('platform', '')
    if platform:
        base_query = base_query.filter_by(streaming_platform=platform)

    # Sort
    sort = request.args.get('sort', 'popular')
    if sort == 'newest':
        base_query = base_query.order_by(Movie.year.desc(), Movie.title)
    elif sort == 'tomatometer':
        base_query = base_query.order_by(Movie.tomatometer.desc(), Movie.title)
    elif sort == 'audience':
        base_query = base_query.order_by(Movie.audience_score.desc(), Movie.title)
    elif sort == 'a_z':
        base_query = base_query.order_by(Movie.title)
    else:  # popular
        base_query = base_query.order_by(Movie.audience_score.desc(), Movie.tomatometer.desc())

    movies = base_query.all()
    genres = Genre.query.order_by(Genre.name).all()
    platforms = db.session.query(Movie.streaming_platform).filter(
        Movie.streaming_platform != ''
    ).distinct().order_by(Movie.streaming_platform).all()
    platforms = [p[0] for p in platforms]

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
                           current_platform=platform)


@app.route('/m/<slug>')
def movie_detail(slug):
    """Movie detail page."""
    movie = Movie.query.filter_by(slug=slug).first_or_404()
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

    review_form = ReviewForm()
    rating_form = RatingForm()

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

    # Get filmography sorted by year desc
    filmography = []
    for entry in person.cast_entries:
        if entry.movie:
            filmography.append(entry)
    filmography.sort(key=lambda c: c.movie.year, reverse=True)

    # Sort option
    sort = request.args.get('sort', 'newest')
    if sort == 'oldest':
        filmography.sort(key=lambda c: c.movie.year)
    elif sort == 'critics_highest':
        filmography.sort(key=lambda c: c.movie.tomatometer, reverse=True)
    elif sort == 'critics_lowest':
        filmography.sort(key=lambda c: c.movie.tomatometer)
    elif sort == 'audience_highest':
        filmography.sort(key=lambda c: c.movie.audience_score, reverse=True)
    elif sort == 'audience_lowest':
        filmography.sort(key=lambda c: c.movie.audience_score)

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
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash('Welcome back!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower()).first()
        if existing:
            flash('Email already registered.', 'danger')
        else:
            hashed = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            user = User(email=form.email.data.lower(), password_hash=hashed, name=form.name.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created!', 'success')
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ── Account / Profile routes ──

@app.route('/account')
@login_required
def account():
    rating_count = UserRating.query.filter_by(user_id=current_user.id).count()
    review_count = AudienceReview.query.filter_by(user_id=current_user.id).count()
    watchlist_count = WatchlistItem.query.filter_by(user_id=current_user.id).count()
    return render_template('account.html', rating_count=rating_count,
                           review_count=review_count, watchlist_count=watchlist_count)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    if request.method == 'POST':
        new_name = request.form.get('name', '').strip()
        if new_name and len(new_name) >= 2:
            current_user.name = new_name
            db.session.commit()
            flash('Profile updated.', 'success')
            return redirect(url_for('account'))
        else:
            flash('Name must be at least 2 characters.', 'danger')
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
    reviews = AudienceReview.query.filter_by(user_id=current_user.id)\
        .order_by(AudienceReview.review_date.desc()).all()
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
    existing = WatchlistItem.query.filter_by(movie_id=movie_id, user_id=current_user.id).first()
    if not existing:
        item = WatchlistItem(movie_id=movie_id, user_id=current_user.id)
        db.session.add(item)
        db.session.commit()
        flash(f'Added "{movie.title}" to your watchlist.', 'success')
    else:
        flash(f'"{movie.title}" is already in your watchlist.', 'info')
    next_url = request.form.get('next') or request.referrer or url_for('movie_detail', slug=movie.slug)
    return redirect(next_url)


@app.route('/user/watchlist/remove/<int:movie_id>', methods=['POST'])
@login_required
def remove_from_watchlist(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    item = WatchlistItem.query.filter_by(movie_id=movie_id, user_id=current_user.id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash(f'Removed "{movie.title}" from your watchlist.', 'success')
    referrer = request.referrer
    if referrer and '/user/watchlist' in referrer:
        return redirect(url_for('watchlist'))
    return redirect(url_for('movie_detail', slug=movie.slug))


# ── Rating & Review routes ──

@app.route('/m/<slug>/rate', methods=['POST'])
@login_required
def rate_movie(slug):
    movie = Movie.query.filter_by(slug=slug).first_or_404()
    form = RatingForm()
    if form.validate_on_submit():
        existing = UserRating.query.filter_by(movie_id=movie.id, user_id=current_user.id).first()
        if existing:
            existing.score = form.score.data
        else:
            rating = UserRating(movie_id=movie.id, user_id=current_user.id, score=form.score.data)
            db.session.add(rating)
        db.session.commit()
        flash(f'Rated "{movie.title}" {form.score.data}/5 stars.', 'success')
    return redirect(url_for('movie_detail', slug=slug))


@app.route('/m/<slug>/review', methods=['POST'])
@login_required
def review_movie(slug):
    movie = Movie.query.filter_by(slug=slug).first_or_404()
    form = ReviewForm()
    if form.validate_on_submit():
        # Check if user already reviewed
        existing = AudienceReview.query.filter_by(movie_id=movie.id, user_id=current_user.id).first()
        if existing:
            flash('You have already reviewed this movie.', 'info')
        else:
            review = AudienceReview(
                movie_id=movie.id,
                user_id=current_user.id,
                score=form.score.data,
                text=form.text.data
            )
            db.session.add(review)
            db.session.commit()
            flash('Review submitted!', 'success')
    return redirect(url_for('movie_detail', slug=slug))


@app.route('/user/reviews/delete/<int:review_id>', methods=['POST'])
@login_required
def delete_review(review_id):
    review = AudienceReview.query.get_or_404(review_id)
    if review.user_id != current_user.id:
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
    from seed_data import seed_all
    seed_all(db, Genre, Movie, Person, MovieCast, CriticReview, AudienceReview, User, UserRating, WatchlistItem)


with app.app_context():
    init_db()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
