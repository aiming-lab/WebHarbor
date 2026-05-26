"""BoardGameGeek mirror — Flask application.

Mirrors the look + feel + feature surface of boardgamegeek.com:

- Top 1000 ranked games (/browse/boardgame[/page/N])
- Hot list (/hotness)
- Game item page (/boardgame/<id>/<slug>) with description, stats, polls,
  designers, artists, publishers, categories, mechanics, expansions, ratings
- Per-game ratings/reviews page (/boardgame/<id>/<slug>/ratings)
- Per-game credits (/boardgame/<id>/<slug>/credits)
- Browse by mechanic / category / designer / artist / publisher
- Forums + threads + posts (/forums, /forum/<id>, /thread/<id>)
- GeekLists (/geeklists, /geeklist/<id>)
- User profile / collection / wishlist / plays (/user/<name>, /collection/<name>)
- Search (games / users / geeklists)
- Auth (login / register / logout)
- Rate, comment, add-to-collection, wishlist, reply-to-thread, write-review

Real data comes from sites/boardgamegeek/scraped_data/bgg.json (BGG api.geekdo.com).
Loaded by seed_data.py — idempotent.
"""
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort, jsonify, send_from_directory, Response)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from wtforms import (StringField, PasswordField, TextAreaField, HiddenField,
                     IntegerField, SelectField, BooleanField, FloatField)
from wtforms.validators import DataRequired, Length, Optional, Email, NumberRange
from sqlalchemy import or_, and_, desc, asc, func, text
from markupsafe import Markup, escape

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config['SECRET_KEY'] = 'boardgamegeek-mirror-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'boardgamegeek.db')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Sign in to access that page.'
csrf = CSRFProtect(app)


# Pinned reference "now" so that time_ago strings and join dates are stable
# across rebuilds. The byte-identical reset invariant depends on this.
MIRROR_NOW = datetime(2026, 5, 26, 12, 0, 0)


# ----- Models -----

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(200), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    real_name = db.Column(db.String(200), default='')
    country = db.Column(db.String(80), default='')
    state = db.Column(db.String(80), default='')
    city = db.Column(db.String(80), default='')
    isocountry = db.Column(db.String(8), default='')
    avatar_filename = db.Column(db.String(200), default='')
    about = db.Column(db.Text, default='')
    joined_at = db.Column(db.DateTime, default=lambda: MIRROR_NOW)
    last_login = db.Column(db.DateTime, default=lambda: MIRROR_NOW)
    geekgold = db.Column(db.Integer, default=0)
    is_supporter = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

    @property
    def display_location(self):
        bits = [self.city, self.state, self.country]
        return ', '.join(b for b in bits if b)


# Many-to-many association tables (designer/artist/publisher/category/mechanic/family).
game_designers   = db.Table('game_designers',
    db.Column('game_id',   db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('person_id', db.Integer, db.ForeignKey('people.id'), primary_key=True))
game_artists     = db.Table('game_artists',
    db.Column('game_id',   db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('person_id', db.Integer, db.ForeignKey('people.id'), primary_key=True))
game_publishers  = db.Table('game_publishers',
    db.Column('game_id',   db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('publisher_id', db.Integer, db.ForeignKey('publishers.id'), primary_key=True))
game_categories  = db.Table('game_categories',
    db.Column('game_id',   db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('categories.id'), primary_key=True))
game_mechanics   = db.Table('game_mechanics',
    db.Column('game_id',   db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('mechanic_id', db.Integer, db.ForeignKey('mechanics.id'), primary_key=True))
game_families    = db.Table('game_families',
    db.Column('game_id',   db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('family_id', db.Integer, db.ForeignKey('families.id'), primary_key=True))


class Person(db.Model):
    """Designer / artist (BGG conflates these under linkdata)."""
    __tablename__ = 'people'
    id = db.Column(db.Integer, primary_key=True)
    bgg_id = db.Column(db.Integer, unique=True, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(200), index=True)


class Publisher(db.Model):
    __tablename__ = 'publishers'
    id = db.Column(db.Integer, primary_key=True)
    bgg_id = db.Column(db.Integer, unique=True, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(200), index=True)


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    bgg_id = db.Column(db.Integer, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    slug = db.Column(db.String(120), index=True)


class Mechanic(db.Model):
    __tablename__ = 'mechanics'
    id = db.Column(db.Integer, primary_key=True)
    bgg_id = db.Column(db.Integer, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    slug = db.Column(db.String(120), index=True)


class Family(db.Model):
    """BGG 'family' groupings — Crowdfunding:Kickstarter, Components:Miniatures, etc."""
    __tablename__ = 'families'
    id = db.Column(db.Integer, primary_key=True)
    bgg_id = db.Column(db.Integer, unique=True, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(200), index=True)


class Game(db.Model):
    __tablename__ = 'games'
    id = db.Column(db.Integer, primary_key=True)
    bgg_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    name = db.Column(db.String(500), nullable=False, index=True)
    slug = db.Column(db.String(500), nullable=False, index=True)
    subtype = db.Column(db.String(40), default='boardgame')   # or boardgameexpansion
    year_published = db.Column(db.Integer, default=0, index=True)
    minplayers = db.Column(db.Integer, default=0)
    maxplayers = db.Column(db.Integer, default=0)
    minplaytime = db.Column(db.Integer, default=0)
    maxplaytime = db.Column(db.Integer, default=0)
    minage = db.Column(db.Integer, default=0)
    short_description = db.Column(db.Text, default='')
    description_html = db.Column(db.Text, default='')
    image_filename = db.Column(db.String(200), default='')
    thumb_filename = db.Column(db.String(200), default='')

    # Cached stats
    avg_rating = db.Column(db.Float, default=0.0, index=True)
    bayes_average = db.Column(db.Float, default=0.0, index=True)
    weight = db.Column(db.Float, default=0.0, index=True)
    weight_votes = db.Column(db.Integer, default=0)
    num_ratings = db.Column(db.Integer, default=0)
    num_owners = db.Column(db.Integer, default=0)
    num_wishing = db.Column(db.Integer, default=0)
    num_comments = db.Column(db.Integer, default=0)
    overall_rank = db.Column(db.Integer, default=0, index=True)
    best_player_count = db.Column(db.String(40), default='')  # e.g. '3-4'
    recommended_player_count = db.Column(db.String(40), default='')
    suggested_age = db.Column(db.String(20), default='')
    language_dependence = db.Column(db.String(200), default='')

    # Featured flag for the homepage carousel
    featured = db.Column(db.Boolean, default=False)

    designers  = db.relationship('Person',     secondary=game_designers,  backref='designed_games')
    artists    = db.relationship('Person',     secondary=game_artists,    backref='illustrated_games')
    publishers = db.relationship('Publisher',  secondary=game_publishers, backref='games')
    categories = db.relationship('Category',   secondary=game_categories, backref='games')
    mechanics  = db.relationship('Mechanic',   secondary=game_mechanics,  backref='games')
    families   = db.relationship('Family',     secondary=game_families,   backref='games')

    @property
    def players_str(self):
        if self.minplayers == self.maxplayers and self.minplayers:
            return f"{self.minplayers}"
        if self.minplayers and self.maxplayers:
            return f"{self.minplayers}–{self.maxplayers}"
        if self.minplayers:
            return f"{self.minplayers}+"
        return "—"

    @property
    def time_str(self):
        if self.minplaytime == self.maxplaytime and self.minplaytime:
            return f"{self.minplaytime} min"
        if self.minplaytime and self.maxplaytime:
            return f"{self.minplaytime}–{self.maxplaytime} min"
        if self.minplaytime:
            return f"{self.minplaytime}+ min"
        return "—"

    @property
    def weight_label(self):
        w = self.weight or 0
        if w == 0:
            return 'Unrated'
        if w < 1.5:  return 'Light'
        if w < 2.5:  return 'Medium Light'
        if w < 3.5:  return 'Medium'
        if w < 4.2:  return 'Medium Heavy'
        return 'Heavy'

    @property
    def detail_url(self):
        return url_for('game_detail', oid=self.bgg_id, slug=self.slug)


# Expansions / integrations link table (game -> game)
class GameLink(db.Model):
    __tablename__ = 'game_links'
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), index=True, nullable=False)
    other_id = db.Column(db.Integer, db.ForeignKey('games.id'), index=True, nullable=False)
    kind = db.Column(db.String(40), nullable=False, index=True)
    # kind: expansion (other is an expansion of game),
    #       integration / reimplementation / containedin / contains


class Rating(db.Model):
    """Numeric rating, optionally with a text review."""
    __tablename__ = 'ratings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False, index=True)
    value = db.Column(db.Float, nullable=False, index=True)         # 1-10
    review_html = db.Column(db.Text, default='')                    # may be empty
    created_at = db.Column(db.DateTime, default=lambda: MIRROR_NOW, index=True)
    num_thumbs = db.Column(db.Integer, default=0)                   # reviewer thumbs

    __table_args__ = (db.UniqueConstraint('user_id', 'game_id'),)

    user = db.relationship('User', backref='ratings')
    game = db.relationship('Game', backref='ratings')

    @property
    def is_review(self):
        return bool(self.review_html and self.review_html.strip())


class Collection(db.Model):
    """User's collection entry per game (own/want/wishlist/etc)."""
    __tablename__ = 'collections'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False, index=True)
    own = db.Column(db.Boolean, default=False)
    prevowned = db.Column(db.Boolean, default=False)
    want_to_play = db.Column(db.Boolean, default=False)
    want_to_buy = db.Column(db.Boolean, default=False)
    wishlist = db.Column(db.Boolean, default=False)
    wishlist_priority = db.Column(db.Integer, default=0)
    preordered = db.Column(db.Boolean, default=False)
    for_trade = db.Column(db.Boolean, default=False)
    comment = db.Column(db.Text, default='')
    acquired_on = db.Column(db.String(40), default='')
    updated_at = db.Column(db.DateTime, default=lambda: MIRROR_NOW)

    __table_args__ = (db.UniqueConstraint('user_id', 'game_id'),)
    user = db.relationship('User', backref='collection')
    game = db.relationship('Game', backref='collected_by')


class Play(db.Model):
    __tablename__ = 'plays'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False, index=True)
    played_on = db.Column(db.Date, default=lambda: MIRROR_NOW.date(), index=True)
    quantity = db.Column(db.Integer, default=1)
    length_minutes = db.Column(db.Integer, default=0)
    num_players = db.Column(db.Integer, default=0)
    location = db.Column(db.String(200), default='')
    comments = db.Column(db.Text, default='')
    incomplete = db.Column(db.Boolean, default=False)
    no_winstats = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='plays')
    game = db.relationship('Game', backref='plays')


# ----- Forums -----

class Forum(db.Model):
    __tablename__ = 'forums'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, default='')
    section = db.Column(db.String(80), index=True)        # 'general', 'reviews', 'strategy', etc.
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True, index=True)
    sort_order = db.Column(db.Integer, default=100)
    num_threads = db.Column(db.Integer, default=0)
    num_posts = db.Column(db.Integer, default=0)
    game = db.relationship('Game', backref='forums')


class Thread(db.Model):
    __tablename__ = 'threads'
    id = db.Column(db.Integer, primary_key=True)
    forum_id = db.Column(db.Integer, db.ForeignKey('forums.id'), nullable=False, index=True)
    subject = db.Column(db.String(300), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    is_pinned = db.Column(db.Boolean, default=False, index=True)
    is_locked = db.Column(db.Boolean, default=False)
    is_hot = db.Column(db.Boolean, default=False)
    num_posts = db.Column(db.Integer, default=1)
    num_views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: MIRROR_NOW, index=True)
    last_post_at = db.Column(db.DateTime, default=lambda: MIRROR_NOW, index=True)

    forum = db.relationship('Forum', backref='threads')
    author = db.relationship('User', backref='threads')


class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('threads.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    body_html = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=lambda: MIRROR_NOW, index=True)
    edited_at = db.Column(db.DateTime, nullable=True)
    thumbs = db.Column(db.Integer, default=0)

    thread = db.relationship('Thread', backref='posts')
    author = db.relationship('User', backref='posts')


# ----- GeekLists -----

class GeekList(db.Model):
    __tablename__ = 'geeklists'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False, index=True)
    description_html = db.Column(db.Text, default='')
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: MIRROR_NOW, index=True)
    num_thumbs = db.Column(db.Integer, default=0, index=True)
    num_items = db.Column(db.Integer, default=0)

    author = db.relationship('User', backref='geeklists')


class GeekListItem(db.Model):
    __tablename__ = 'geeklist_items'
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('geeklists.id'), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True, index=True)
    body_html = db.Column(db.Text, default='')
    position = db.Column(db.Integer, default=0)
    num_thumbs = db.Column(db.Integer, default=0)

    geeklist = db.relationship('GeekList', backref='items')
    game = db.relationship('Game')


# ----- Thumbs (likes on posts/reviews/geeklists) -----

class Thumb(db.Model):
    __tablename__ = 'thumbs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False, index=True)   # post|rating|geeklist|geeklist_item
    target_id = db.Column(db.Integer, nullable=False, index=True)
    __table_args__ = (db.UniqueConstraint('user_id', 'kind', 'target_id'),)


# ----- Forms -----

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(2, 80)])
    password = PasswordField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(3, 80)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(3, 200)])
    password = PasswordField('Password', validators=[DataRequired(), Length(6, 128)])
    real_name = StringField('Real name', validators=[Optional(), Length(0, 200)])
    country = StringField('Country', validators=[Optional(), Length(0, 80)])


class ProfileForm(FlaskForm):
    real_name = StringField('Real name', validators=[Optional(), Length(0, 200)])
    country = StringField('Country', validators=[Optional(), Length(0, 80)])
    state = StringField('State', validators=[Optional(), Length(0, 80)])
    city = StringField('City', validators=[Optional(), Length(0, 80)])
    about = TextAreaField('About', validators=[Optional(), Length(0, 4000)])


class RatingForm(FlaskForm):
    value = FloatField('Rating', validators=[DataRequired(), NumberRange(1, 10)])
    review = TextAreaField('Review', validators=[Optional(), Length(0, 20000)])


class CollectionForm(FlaskForm):
    own = BooleanField('Own', default=False)
    prevowned = BooleanField('Previously Owned', default=False)
    want_to_play = BooleanField('Want To Play', default=False)
    want_to_buy = BooleanField('Want To Buy', default=False)
    wishlist = BooleanField('Wishlist', default=False)
    wishlist_priority = SelectField('Priority', choices=[
        ('0','Not on wishlist'),
        ('1','Must have'),('2','Love to have'),
        ('3','Like to have'),('4','Thinking about it'),
        ('5','Dont buy this'),
    ], default='0')
    preordered = BooleanField('Pre-ordered', default=False)
    for_trade = BooleanField('For Trade', default=False)
    comment = TextAreaField('Comment', validators=[Optional(), Length(0, 4000)])
    acquired_on = StringField('Acquired on', validators=[Optional(), Length(0, 40)])


class ThreadForm(FlaskForm):
    subject = StringField('Subject', validators=[DataRequired(), Length(2, 300)])
    body = TextAreaField('Post', validators=[DataRequired(), Length(1, 20000)])


class PostForm(FlaskForm):
    body = TextAreaField('Reply', validators=[DataRequired(), Length(1, 20000)])
    parent_id = HiddenField()


class GeekListForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(3, 300)])
    description = TextAreaField('Description', validators=[Optional(), Length(0, 8000)])


class PlayForm(FlaskForm):
    played_on = StringField('Date (YYYY-MM-DD)', validators=[DataRequired(), Length(10, 10)])
    quantity = IntegerField('Quantity', validators=[Optional(), NumberRange(1, 50)], default=1)
    length_minutes = IntegerField('Length (min)', validators=[Optional(), NumberRange(0, 1200)], default=0)
    num_players = IntegerField('Players', validators=[Optional(), NumberRange(0, 20)], default=0)
    location = StringField('Location', validators=[Optional(), Length(0, 200)])
    comments = TextAreaField('Comments', validators=[Optional(), Length(0, 4000)])


# ----- Auth -----

@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# ----- Helpers -----

STOP_WORDS = {'the','a','an','in','on','at','to','for','of','and','or',
              'is','it','by','with','as','be','this','that','are','was',
              'were','from','how','what','why','we','i','you','they',
              'about','vs','game'}


def tokenize(query: str):
    return [t.lower() for t in re.split(r'\W+', query or '')
            if t.lower() not in STOP_WORDS and len(t) > 1]


def _safe_next(target: str | None, fallback: str) -> str:
    if not target:
        return fallback
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return fallback
    if not target.startswith('/'):
        return fallback
    return target


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or 'item'


def _time_ago(dt) -> str:
    if not dt:
        return ''
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    delta = MIRROR_NOW - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return 'just now'
    if secs < 3600:
        m = secs // 60
        return f"{m} minute{'s' if m != 1 else ''} ago"
    if secs < 86400:
        h = secs // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    d = secs // 86400
    if d < 30:
        return f"{d} day{'s' if d != 1 else ''} ago"
    if d < 365:
        mo = d // 30
        return f"{mo} month{'s' if mo != 1 else ''} ago"
    y = d // 365
    return f"{y} year{'s' if y != 1 else ''} ago"


@app.template_filter('time_ago')
def _tpl_time_ago(dt):
    return _time_ago(dt)


@app.template_filter('rating_color')
def _tpl_rating_color(value):
    """Hex color for a BGG-style rating chip (1-10)."""
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        v = 0
    if v >= 9.0:   return '#249563'
    if v >= 8.0:   return '#2fc482'
    if v >= 7.0:   return '#1d8acd'
    if v >= 6.0:   return '#5369a2'
    if v >= 5.0:   return '#5d69a3'
    if v >= 4.0:   return '#df4751'
    if v >= 3.0:   return '#df4751'
    if v >= 2.0:   return '#db303f'
    if v >= 1.0:   return '#8c2317'
    return '#a0a0a0'


@app.template_filter('safe_html')
def _tpl_safe_html(text):
    # We trust the seed data (it's static), so render as-is.
    return Markup(text or '')


@app.template_filter('one_decimal')
def _tpl_one_decimal(v):
    try:
        return f"{float(v):.1f}"
    except (TypeError, ValueError):
        return '—'


@app.template_filter('two_decimal')
def _tpl_two_decimal(v):
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return '—'


@app.template_filter('thousands')
def _tpl_thousands(v):
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return '0'


@app.context_processor
def inject_globals():
    return {
        'site_name': 'BoardGameGeek',
        'mirror_now': MIRROR_NOW,
        'current_year': MIRROR_NOW.year,
    }


def _scored_game_search(query: str, page: int = 1, per_page: int = 30):
    tokens = tokenize(query)
    if not tokens:
        return [], 0
    conds = []
    for t in tokens:
        like = f"%{t}%"
        conds.append(Game.name.ilike(like))
        conds.append(Game.short_description.ilike(like))
    base = Game.query.filter(or_(*conds))
    cands = base.limit(3000).all()
    scored = []
    for g in cands:
        hay_title = (g.name or '').lower()
        hay_other = (g.short_description or '').lower()
        score = 0
        for t in tokens:
            if t in hay_title:
                score += 5 + hay_title.count(t)
            if t in hay_other:
                score += hay_other.count(t)
        if g.bayes_average:
            score += min(int(g.bayes_average), 10) * 0.1
        if score > 0:
            scored.append((g, score))
    scored.sort(key=lambda x: -x[1])
    total = len(scored)
    start = (page - 1) * per_page
    items = [s[0] for s in scored[start:start + per_page]]
    return items, total


# ----- Routes: home / browse -----

@app.route('/')
def index():
    hot_games = Game.query.filter(Game.featured == True).order_by(Game.overall_rank.asc()).limit(15).all()
    if len(hot_games) < 12:
        # Fallback: top by rank
        extra = Game.query.filter(Game.overall_rank > 0).order_by(Game.overall_rank.asc()).limit(15).all()
        seen = {g.id for g in hot_games}
        for g in extra:
            if g.id not in seen:
                hot_games.append(g)
                if len(hot_games) >= 15:
                    break
    top_overall = Game.query.filter(Game.overall_rank > 0) \
        .order_by(Game.overall_rank.asc()).limit(10).all()
    recent_lists = GeekList.query.order_by(GeekList.created_at.desc()).limit(8).all()
    active_threads = Thread.query.order_by(Thread.last_post_at.desc()).limit(10).all()
    recent_reviews = Rating.query.filter(Rating.review_html != '') \
        .order_by(Rating.created_at.desc()).limit(8).all()
    return render_template('index.html',
                           hot_games=hot_games,
                           top_overall=top_overall,
                           recent_lists=recent_lists,
                           active_threads=active_threads,
                           recent_reviews=recent_reviews)


@app.route('/browse/boardgame')
@app.route('/browse/boardgame/page/<int:page>')
def browse(page=1):
    sort = request.args.get('sort', 'rank')
    direction = request.args.get('dir', 'asc')
    page = max(1, page)
    per_page = 100
    q = Game.query.filter(Game.subtype == 'boardgame')
    if sort == 'rank':
        q = q.filter(Game.overall_rank > 0)
        q = q.order_by(Game.overall_rank.asc() if direction == 'asc' else Game.overall_rank.desc())
    elif sort == 'name':
        q = q.order_by(Game.name.asc() if direction == 'asc' else Game.name.desc())
    elif sort == 'year':
        q = q.order_by(Game.year_published.desc() if direction == 'desc' else Game.year_published.asc())
    elif sort == 'average':
        q = q.order_by(Game.avg_rating.desc() if direction == 'desc' else Game.avg_rating.asc())
    elif sort == 'numvoters':
        q = q.order_by(Game.num_ratings.desc() if direction == 'desc' else Game.num_ratings.asc())
    elif sort == 'weight':
        q = q.order_by(Game.weight.desc() if direction == 'desc' else Game.weight.asc())
    else:
        q = q.order_by(Game.overall_rank.asc())
    total = q.count()
    games = q.limit(per_page).offset((page - 1) * per_page).all()
    start_rank = (page - 1) * per_page + 1
    return render_template('browse.html',
                           games=games, page=page, per_page=per_page,
                           total=total, sort=sort, direction=direction,
                           start_rank=start_rank,
                           has_next=page * per_page < total,
                           has_prev=page > 1)


@app.route('/hotness')
@app.route('/hot')
def hotness():
    games = Game.query.filter(Game.featured == True) \
        .order_by(Game.overall_rank.asc()).limit(50).all()
    if not games:
        games = Game.query.filter(Game.overall_rank > 0) \
            .order_by(Game.overall_rank.asc()).limit(50).all()
    return render_template('hotness.html', games=games)


# ----- Routes: game detail + sub-pages -----

def _get_game_or_404(oid: int, slug: str | None):
    g = Game.query.filter_by(bgg_id=oid).first()
    if not g:
        abort(404)
    # Don't enforce slug match — agents may navigate by id alone.
    return g


@app.route('/boardgame/<int:oid>')
@app.route('/boardgame/<int:oid>/<slug>')
def game_detail(oid, slug=None):
    g = _get_game_or_404(oid, slug)
    # Build expansions + integrations from GameLink
    expansions = []
    for link in GameLink.query.filter_by(game_id=g.id, kind='expansion').all():
        other = db.session.get(Game, link.other_id)
        if other:
            expansions.append(other)
    integrations = []
    for link in GameLink.query.filter_by(game_id=g.id, kind='integration').all():
        other = db.session.get(Game, link.other_id)
        if other:
            integrations.append(other)
    reviews = (Rating.query.filter_by(game_id=g.id)
               .filter(Rating.review_html != '')
               .order_by(Rating.num_thumbs.desc(), Rating.value.desc())
               .limit(5).all())
    related_forums = Forum.query.filter_by(game_id=g.id).order_by(Forum.sort_order).all()
    threads = []
    if related_forums:
        forum_ids = [f.id for f in related_forums]
        threads = (Thread.query.filter(Thread.forum_id.in_(forum_ids))
                   .order_by(Thread.last_post_at.desc()).limit(8).all())
    # Cached user state
    my_rating = None
    my_collection = None
    if current_user.is_authenticated:
        my_rating = Rating.query.filter_by(user_id=current_user.id, game_id=g.id).first()
        my_collection = Collection.query.filter_by(user_id=current_user.id, game_id=g.id).first()
    return render_template('item.html', g=g,
                           expansions=expansions, integrations=integrations,
                           reviews=reviews, related_forums=related_forums,
                           threads=threads,
                           my_rating=my_rating, my_collection=my_collection,
                           rating_form=RatingForm(),
                           collection_form=CollectionForm())


@app.route('/boardgame/<int:oid>/<slug>/ratings')
@app.route('/boardgame/<int:oid>/ratings')
def game_ratings(oid, slug=None):
    g = _get_game_or_404(oid, slug)
    sort = request.args.get('sort', 'rating')
    page = max(1, request.args.get('p', 1, type=int))
    per_page = 50
    q = Rating.query.filter_by(game_id=g.id)
    if sort == 'rating':
        q = q.order_by(Rating.value.desc(), Rating.num_thumbs.desc())
    elif sort == 'lowest':
        q = q.order_by(Rating.value.asc())
    elif sort == 'recent':
        q = q.order_by(Rating.created_at.desc())
    elif sort == 'thumbs':
        q = q.order_by(Rating.num_thumbs.desc(), Rating.value.desc())
    else:
        q = q.order_by(Rating.value.desc())
    total = q.count()
    ratings = q.limit(per_page).offset((page - 1) * per_page).all()
    # Histogram
    histogram = {i: 0 for i in range(1, 11)}
    for r in Rating.query.filter_by(game_id=g.id).all():
        bucket = max(1, min(10, int(round(r.value or 0))))
        histogram[bucket] += 1
    return render_template('ratings.html', g=g, ratings=ratings,
                           sort=sort, page=page, per_page=per_page,
                           total=total, histogram=histogram,
                           has_next=page * per_page < total,
                           has_prev=page > 1)


@app.route('/boardgame/<int:oid>/<slug>/credits')
@app.route('/boardgame/<int:oid>/credits')
def game_credits(oid, slug=None):
    g = _get_game_or_404(oid, slug)
    return render_template('credits.html', g=g)


@app.route('/boardgame/<int:oid>/<slug>/expansions')
@app.route('/boardgame/<int:oid>/expansions')
def game_expansions(oid, slug=None):
    g = _get_game_or_404(oid, slug)
    rows = []
    for link in GameLink.query.filter_by(game_id=g.id, kind='expansion').all():
        other = db.session.get(Game, link.other_id)
        if other:
            rows.append(other)
    rows.sort(key=lambda o: (o.year_published or 9999, o.name))
    return render_template('expansions.html', g=g, expansions=rows)


@app.route('/boardgame/<int:oid>/<slug>/forums')
@app.route('/boardgame/<int:oid>/forums')
def game_forums(oid, slug=None):
    g = _get_game_or_404(oid, slug)
    forums = Forum.query.filter_by(game_id=g.id).order_by(Forum.sort_order).all()
    return render_template('game_forums.html', g=g, forums=forums)


# ----- Browse by category / mechanic / designer / artist / publisher / family -----

def _browse_by(entity_query, page_url_name, header_label, slug_url=None,
               entity=None, page=1, per_page=50, sort='rank'):
    games = entity.games if entity else []
    if sort == 'rank':
        games = sorted(games, key=lambda g: (g.overall_rank or 99999, -(g.bayes_average or 0)))
    elif sort == 'average':
        games = sorted(games, key=lambda g: -(g.avg_rating or 0))
    elif sort == 'year':
        games = sorted(games, key=lambda g: -(g.year_published or 0))
    elif sort == 'name':
        games = sorted(games, key=lambda g: g.name.lower())
    total = len(games)
    start = (page - 1) * per_page
    page_items = games[start:start + per_page]
    return page_items, total


@app.route('/boardgamecategory/<int:cid>')
@app.route('/boardgamecategory/<int:cid>/<slug>')
def category_detail(cid, slug=None):
    c = Category.query.filter_by(bgg_id=cid).first_or_404()
    page = max(1, request.args.get('p', 1, type=int))
    sort = request.args.get('sort', 'rank')
    games, total = _browse_by(None, 'category_detail', 'Category',
                               entity=c, page=page, sort=sort)
    return render_template('property.html', kind='category',
                           entity=c, games=games, page=page, total=total,
                           sort=sort, has_next=page * 50 < total)


@app.route('/boardgamemechanic/<int:mid>')
@app.route('/boardgamemechanic/<int:mid>/<slug>')
def mechanic_detail(mid, slug=None):
    m = Mechanic.query.filter_by(bgg_id=mid).first_or_404()
    page = max(1, request.args.get('p', 1, type=int))
    sort = request.args.get('sort', 'rank')
    games, total = _browse_by(None, 'mechanic_detail', 'Mechanism',
                               entity=m, page=page, sort=sort)
    return render_template('property.html', kind='mechanic',
                           entity=m, games=games, page=page, total=total,
                           sort=sort, has_next=page * 50 < total)


@app.route('/boardgamedesigner/<int:pid>')
@app.route('/boardgamedesigner/<int:pid>/<slug>')
def designer_detail(pid, slug=None):
    p = Person.query.filter_by(bgg_id=pid).first_or_404()
    games = p.designed_games
    sort = request.args.get('sort', 'rank')
    if sort == 'rank':
        games = sorted(games, key=lambda g: (g.overall_rank or 99999))
    elif sort == 'year':
        games = sorted(games, key=lambda g: -(g.year_published or 0))
    elif sort == 'average':
        games = sorted(games, key=lambda g: -(g.avg_rating or 0))
    elif sort == 'name':
        games = sorted(games, key=lambda g: g.name.lower())
    return render_template('person.html', kind='designer', person=p,
                           games=games, sort=sort)


@app.route('/boardgameartist/<int:pid>')
@app.route('/boardgameartist/<int:pid>/<slug>')
def artist_detail(pid, slug=None):
    p = Person.query.filter_by(bgg_id=pid).first_or_404()
    games = p.illustrated_games
    sort = request.args.get('sort', 'rank')
    if sort == 'rank':
        games = sorted(games, key=lambda g: (g.overall_rank or 99999))
    elif sort == 'year':
        games = sorted(games, key=lambda g: -(g.year_published or 0))
    elif sort == 'average':
        games = sorted(games, key=lambda g: -(g.avg_rating or 0))
    elif sort == 'name':
        games = sorted(games, key=lambda g: g.name.lower())
    return render_template('person.html', kind='artist', person=p,
                           games=games, sort=sort)


@app.route('/boardgamepublisher/<int:pid>')
@app.route('/boardgamepublisher/<int:pid>/<slug>')
def publisher_detail(pid, slug=None):
    p = Publisher.query.filter_by(bgg_id=pid).first_or_404()
    games = p.games
    sort = request.args.get('sort', 'rank')
    if sort == 'rank':
        games = sorted(games, key=lambda g: (g.overall_rank or 99999))
    elif sort == 'year':
        games = sorted(games, key=lambda g: -(g.year_published or 0))
    elif sort == 'average':
        games = sorted(games, key=lambda g: -(g.avg_rating or 0))
    return render_template('publisher.html', publisher=p, games=games, sort=sort)


# ----- Index pages for taxonomies -----

@app.route('/boardgamecategory')
def categories_index():
    cats = Category.query.order_by(Category.name).all()
    return render_template('taxonomy_index.html', kind='category',
                           title='Board Game Categories',
                           items=cats, url_name='category_detail')


@app.route('/boardgamemechanic')
def mechanics_index():
    mechs = Mechanic.query.order_by(Mechanic.name).all()
    return render_template('taxonomy_index.html', kind='mechanic',
                           title='Board Game Mechanisms',
                           items=mechs, url_name='mechanic_detail')


@app.route('/boardgamedesigner')
def designers_index():
    q = (request.args.get('q') or '').strip()
    query = Person.query
    if q:
        query = query.filter(Person.name.ilike(f'%{q}%'))
    people = query.order_by(Person.name).all()
    return render_template('taxonomy_index.html', kind='designer',
                           title='Board Game Designers',
                           items=people, url_name='designer_detail',
                           filter_q=q)


@app.route('/boardgamepublisher')
def publishers_index():
    q = (request.args.get('q') or '').strip()
    query = Publisher.query
    if q:
        query = query.filter(Publisher.name.ilike(f'%{q}%'))
    pubs = query.order_by(Publisher.name).all()
    return render_template('taxonomy_index.html', kind='publisher',
                           title='Board Game Publishers',
                           items=pubs, url_name='publisher_detail',
                           filter_q=q)


# ----- Search -----

@app.route('/search')
def search():
    q = (request.args.get('q') or '').strip()
    tab = request.args.get('type', 'boardgame')
    page = max(1, request.args.get('p', 1, type=int))
    per_page = 30
    if not q:
        return render_template('search.html', q='', tab=tab, total=0,
                               games=[], users=[], lists=[], page=page, has_next=False)
    if tab == 'user':
        like = f"%{q}%"
        base = User.query.filter(or_(User.username.ilike(like),
                                     User.real_name.ilike(like)))
        total = base.count()
        users = base.order_by(User.username.asc()).limit(per_page).offset((page-1)*per_page).all()
        return render_template('search.html', q=q, tab=tab, total=total,
                               games=[], users=users, lists=[],
                               page=page, has_next=page * per_page < total)
    if tab == 'geeklist':
        like = f"%{q}%"
        base = GeekList.query.filter(GeekList.title.ilike(like))
        total = base.count()
        lists = base.order_by(GeekList.num_thumbs.desc()).limit(per_page).offset((page-1)*per_page).all()
        return render_template('search.html', q=q, tab=tab, total=total,
                               games=[], users=[], lists=lists,
                               page=page, has_next=page * per_page < total)
    # default: boardgame
    games, total = _scored_game_search(q, page=page, per_page=per_page)
    return render_template('search.html', q=q, tab=tab, total=total,
                           games=games, users=[], lists=[],
                           page=page, has_next=page * per_page < total)


@app.route('/geeksearch.php')
def legacy_search():
    return redirect(url_for('search', q=request.args.get('q', ''), type=request.args.get('action','boardgame')))


# ----- Forums -----

@app.route('/forums')
def forums_index():
    # Group forums by section
    sections = {}
    for f in Forum.query.filter(Forum.game_id.is_(None)).order_by(Forum.sort_order).all():
        sections.setdefault(f.section or 'General', []).append(f)
    return render_template('forums_index.html', sections=sections)


@app.route('/forum/<int:fid>')
def forum_detail(fid):
    f = db.session.get(Forum, fid) or abort(404)
    page = max(1, request.args.get('p', 1, type=int))
    per_page = 50
    q = Thread.query.filter_by(forum_id=fid) \
        .order_by(Thread.is_pinned.desc(), Thread.last_post_at.desc())
    total = q.count()
    threads = q.limit(per_page).offset((page - 1) * per_page).all()
    return render_template('forum.html', forum=f, threads=threads,
                           page=page, total=total,
                           has_next=page * per_page < total)


@app.route('/thread/<int:tid>')
def thread_detail(tid):
    t = db.session.get(Thread, tid) or abort(404)
    posts = Post.query.filter_by(thread_id=tid) \
        .order_by(Post.created_at.asc()).all()
    return render_template('thread.html', thread=t, posts=posts,
                           reply_form=PostForm())


@app.route('/thread/<int:tid>/reply', methods=['POST'])
@login_required
def thread_reply(tid):
    t = db.session.get(Thread, tid) or abort(404)
    form = PostForm()
    if form.validate_on_submit() and not t.is_locked:
        p = Post(thread_id=tid, author_id=current_user.id,
                 body_html=escape_paragraphs(form.body.data),
                 created_at=MIRROR_NOW)
        db.session.add(p)
        t.num_posts = (t.num_posts or 0) + 1
        t.last_post_at = MIRROR_NOW
        f = db.session.get(Forum, t.forum_id)
        if f:
            f.num_posts = (f.num_posts or 0) + 1
        db.session.commit()
        flash('Reply posted.', 'success')
    elif t.is_locked:
        flash('Thread is locked.', 'error')
    else:
        flash('Reply text is required.', 'error')
    return redirect(url_for('thread_detail', tid=tid) + f'#post-{Post.query.order_by(Post.id.desc()).first().id}' if Post.query.filter_by(thread_id=tid).count() else url_for('thread_detail', tid=tid))


@app.route('/forum/<int:fid>/new', methods=['GET', 'POST'])
@login_required
def thread_new(fid):
    f = db.session.get(Forum, fid) or abort(404)
    form = ThreadForm()
    if form.validate_on_submit():
        t = Thread(forum_id=fid, subject=form.subject.data.strip(),
                   author_id=current_user.id,
                   created_at=MIRROR_NOW, last_post_at=MIRROR_NOW, num_posts=1)
        db.session.add(t)
        db.session.flush()
        p = Post(thread_id=t.id, author_id=current_user.id,
                 body_html=escape_paragraphs(form.body.data),
                 created_at=MIRROR_NOW)
        db.session.add(p)
        f.num_threads = (f.num_threads or 0) + 1
        f.num_posts = (f.num_posts or 0) + 1
        db.session.commit()
        flash('Thread posted.', 'success')
        return redirect(url_for('thread_detail', tid=t.id))
    return render_template('thread_new.html', forum=f, form=form)


# ----- GeekLists -----

@app.route('/geeklists')
def geeklists_index():
    sort = request.args.get('sort', 'recent')
    page = max(1, request.args.get('p', 1, type=int))
    per_page = 20
    q = GeekList.query
    if sort == 'thumbs':
        q = q.order_by(GeekList.num_thumbs.desc())
    elif sort == 'items':
        q = q.order_by(GeekList.num_items.desc())
    else:
        q = q.order_by(GeekList.created_at.desc())
    total = q.count()
    items = q.limit(per_page).offset((page - 1) * per_page).all()
    return render_template('geeklists.html', lists=items, page=page,
                           total=total, sort=sort,
                           has_next=page * per_page < total)


@app.route('/geeklist/<int:lid>')
def geeklist_detail(lid):
    l = db.session.get(GeekList, lid) or abort(404)
    items = GeekListItem.query.filter_by(list_id=lid) \
        .order_by(GeekListItem.position.asc()).all()
    return render_template('geeklist.html', l=l, items=items)


@app.route('/geeklist/new', methods=['GET', 'POST'])
@login_required
def geeklist_new():
    form = GeekListForm()
    if form.validate_on_submit():
        l = GeekList(title=form.title.data.strip(),
                     description_html=escape_paragraphs(form.description.data or ''),
                     author_id=current_user.id, created_at=MIRROR_NOW,
                     num_items=0, num_thumbs=0)
        db.session.add(l)
        db.session.commit()
        flash('GeekList created.', 'success')
        return redirect(url_for('geeklist_detail', lid=l.id))
    return render_template('geeklist_new.html', form=form)


@app.route('/geeklist/<int:lid>/add', methods=['POST'])
@login_required
def geeklist_add_item(lid):
    l = db.session.get(GeekList, lid) or abort(404)
    if l.author_id != current_user.id:
        abort(403)
    bgg_id = request.form.get('bgg_id', type=int)
    body = request.form.get('body', '').strip()
    g = Game.query.filter_by(bgg_id=bgg_id).first()
    if not g:
        flash('Game not found.', 'error')
        return redirect(url_for('geeklist_detail', lid=lid))
    pos = (l.num_items or 0) + 1
    item = GeekListItem(list_id=lid, game_id=g.id, body_html=escape_paragraphs(body),
                        position=pos, num_thumbs=0)
    db.session.add(item)
    l.num_items = pos
    db.session.commit()
    flash('Added to list.', 'success')
    return redirect(url_for('geeklist_detail', lid=lid))


# ----- User -----

@app.route('/user/<username>')
def user_profile(username):
    u = User.query.filter_by(username=username).first_or_404()
    own = Collection.query.filter_by(user_id=u.id, own=True).count()
    want = Collection.query.filter_by(user_id=u.id, want_to_buy=True).count()
    wishlist = Collection.query.filter_by(user_id=u.id, wishlist=True).count()
    plays_count = Play.query.filter_by(user_id=u.id).count()
    rated = Rating.query.filter_by(user_id=u.id).count()
    reviews = Rating.query.filter_by(user_id=u.id).filter(Rating.review_html != '').count()
    recent_plays = Play.query.filter_by(user_id=u.id).order_by(Play.played_on.desc()).limit(5).all()
    top_rated = Rating.query.filter_by(user_id=u.id).order_by(Rating.value.desc()).limit(10).all()
    geeklists = GeekList.query.filter_by(author_id=u.id).order_by(GeekList.created_at.desc()).limit(5).all()
    return render_template('user.html', u=u,
                           own=own, want=want, wishlist=wishlist,
                           plays_count=plays_count, rated=rated, reviews=reviews,
                           recent_plays=recent_plays, top_rated=top_rated,
                           geeklists=geeklists)


@app.route('/collection/<username>')
def collection_detail(username):
    u = User.query.filter_by(username=username).first_or_404()
    status = request.args.get('status', 'own')
    sort = request.args.get('sort', 'name')
    q = Collection.query.filter_by(user_id=u.id)
    if status == 'own':
        q = q.filter_by(own=True)
    elif status == 'prevowned':
        q = q.filter_by(prevowned=True)
    elif status == 'wishlist':
        q = q.filter_by(wishlist=True)
    elif status == 'wanttoplay':
        q = q.filter_by(want_to_play=True)
    elif status == 'wanttobuy':
        q = q.filter_by(want_to_buy=True)
    elif status == 'preorder':
        q = q.filter_by(preordered=True)
    elif status == 'fortrade':
        q = q.filter_by(for_trade=True)
    elif status == 'rated':
        rated_game_ids = [r.game_id for r in Rating.query.filter_by(user_id=u.id).all()]
        q = q.filter(Collection.game_id.in_(rated_game_ids))
    entries = q.all()
    # Join with Game for sorting/display
    games_by_entry = []
    for e in entries:
        g = db.session.get(Game, e.game_id)
        if g:
            rating = Rating.query.filter_by(user_id=u.id, game_id=g.id).first()
            games_by_entry.append({'entry': e, 'game': g, 'rating': rating})
    if sort == 'name':
        games_by_entry.sort(key=lambda x: x['game'].name.lower())
    elif sort == 'rating':
        games_by_entry.sort(key=lambda x: -(x['rating'].value if x['rating'] else 0))
    elif sort == 'rank':
        games_by_entry.sort(key=lambda x: x['game'].overall_rank or 99999)
    elif sort == 'year':
        games_by_entry.sort(key=lambda x: -(x['game'].year_published or 0))
    elif sort == 'recent':
        # Most-recently-updated collection entry first.
        games_by_entry.sort(key=lambda x: x['entry'].updated_at or MIRROR_NOW, reverse=True)
    elif sort == 'acquired':
        games_by_entry.sort(key=lambda x: x['entry'].acquired_on or '', reverse=True)
    return render_template('collection.html', u=u, entries=games_by_entry,
                           status=status, sort=sort, total=len(games_by_entry))


@app.route('/plays/<username>')
def plays_detail(username):
    u = User.query.filter_by(username=username).first_or_404()
    plays = Play.query.filter_by(user_id=u.id).order_by(Play.played_on.desc()).limit(200).all()
    plays_with_game = [(p, db.session.get(Game, p.game_id)) for p in plays]
    return render_template('plays.html', u=u, plays=plays_with_game)


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    form = ProfileForm()
    if request.method == 'POST' and form.validate_on_submit():
        current_user.real_name = form.real_name.data
        current_user.country = form.country.data
        current_user.state = form.state.data
        current_user.city = form.city.data
        current_user.about = form.about.data
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('user_profile', username=current_user.username))
    form.real_name.data = current_user.real_name
    form.country.data = current_user.country
    form.state.data = current_user.state
    form.city.data = current_user.city
    form.about.data = current_user.about
    return render_template('account.html', form=form)


# ----- Rate / collection mutations -----

@app.route('/rate/<int:oid>', methods=['POST'])
@login_required
def rate(oid):
    g = Game.query.filter_by(bgg_id=oid).first_or_404()
    form = RatingForm()
    if not form.validate_on_submit():
        flash('Rating must be between 1.0 and 10.0.', 'error')
        return redirect(url_for('game_detail', oid=oid, slug=g.slug))
    r = Rating.query.filter_by(user_id=current_user.id, game_id=g.id).first()
    if not r:
        r = Rating(user_id=current_user.id, game_id=g.id,
                   value=form.value.data, review_html=escape_paragraphs(form.review.data or ''),
                   created_at=MIRROR_NOW)
        db.session.add(r)
    else:
        r.value = form.value.data
        r.review_html = escape_paragraphs(form.review.data or '')
        r.created_at = MIRROR_NOW
    # Recompute aggregate (cheap on the seeded scale)
    ratings = [x.value for x in Rating.query.filter_by(game_id=g.id).all()] + [form.value.data]
    g.num_ratings = max(g.num_ratings or 0, len(ratings))
    if ratings:
        g.avg_rating = sum(ratings) / len(ratings)
    db.session.commit()
    flash(f'You rated {g.name}: {form.value.data:.1f}.', 'success')
    return redirect(url_for('game_detail', oid=oid, slug=g.slug))


@app.route('/collection/save/<int:oid>', methods=['POST'])
@login_required
def collection_save(oid):
    g = Game.query.filter_by(bgg_id=oid).first_or_404()
    form = CollectionForm()
    if not form.validate_on_submit():
        flash('Bad form.', 'error')
        return redirect(url_for('game_detail', oid=oid, slug=g.slug))
    e = Collection.query.filter_by(user_id=current_user.id, game_id=g.id).first()
    if not e:
        e = Collection(user_id=current_user.id, game_id=g.id)
        db.session.add(e)
    e.own = form.own.data
    e.prevowned = form.prevowned.data
    e.want_to_play = form.want_to_play.data
    e.want_to_buy = form.want_to_buy.data
    e.wishlist = form.wishlist.data
    e.wishlist_priority = int(form.wishlist_priority.data or 0)
    e.preordered = form.preordered.data
    e.for_trade = form.for_trade.data
    e.comment = form.comment.data
    e.acquired_on = form.acquired_on.data
    e.updated_at = MIRROR_NOW
    db.session.commit()
    flash(f'Collection updated for {g.name}.', 'success')
    return redirect(url_for('game_detail', oid=oid, slug=g.slug))


@app.route('/collection/remove/<int:oid>', methods=['POST'])
@login_required
def collection_remove(oid):
    g = Game.query.filter_by(bgg_id=oid).first_or_404()
    e = Collection.query.filter_by(user_id=current_user.id, game_id=g.id).first()
    if e:
        db.session.delete(e)
        db.session.commit()
        flash(f'Removed {g.name} from your collection.', 'success')
    return redirect(url_for('game_detail', oid=oid, slug=g.slug))


@app.route('/plays/log/<int:oid>', methods=['POST'])
@login_required
def play_log(oid):
    g = Game.query.filter_by(bgg_id=oid).first_or_404()
    form = PlayForm()
    if not form.validate_on_submit():
        flash('Date is required (YYYY-MM-DD).', 'error')
        return redirect(url_for('game_detail', oid=oid, slug=g.slug))
    try:
        d = datetime.strptime(form.played_on.data, '%Y-%m-%d').date()
    except ValueError:
        flash('Date must be YYYY-MM-DD.', 'error')
        return redirect(url_for('game_detail', oid=oid, slug=g.slug))
    p = Play(user_id=current_user.id, game_id=g.id, played_on=d,
             quantity=form.quantity.data or 1,
             length_minutes=form.length_minutes.data or 0,
             num_players=form.num_players.data or 0,
             location=form.location.data, comments=form.comments.data)
    db.session.add(p)
    db.session.commit()
    flash(f'Logged play of {g.name}.', 'success')
    return redirect(url_for('plays_detail', username=current_user.username))


# ----- Auth -----

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        u = User.query.filter_by(username=form.username.data.strip()).first()
        if u and bcrypt.check_password_hash(u.password_hash, form.password.data):
            login_user(u)
            u.last_login = MIRROR_NOW
            db.session.commit()
            nxt = _safe_next(request.args.get('next'), url_for('user_profile', username=u.username))
            return redirect(nxt)
        flash('Invalid username or password.', 'error')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            flash('That username is already taken.', 'error')
            return render_template('register.html', form=form)
        if User.query.filter_by(email=form.email.data.strip()).first():
            flash('That email is already registered.', 'error')
            return render_template('register.html', form=form)
        u = User(username=username, email=form.email.data.strip(),
                 password_hash=bcrypt.generate_password_hash(form.password.data).decode(),
                 real_name=form.real_name.data, country=form.country.data,
                 joined_at=MIRROR_NOW, last_login=MIRROR_NOW)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash(f'Welcome, {u.username}!', 'success')
        return redirect(url_for('user_profile', username=u.username))
    return render_template('register.html', form=form)


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    msg = None
    if request.method == 'POST':
        msg = ('If an account with that email exists, a reset link is on its way. '
               '(Mirror site — no email is actually sent.)')
    return render_template('forgot.html', msg=msg)


# ----- Static pages -----

@app.route('/wiki/page/About')
def about():
    return render_template('about.html')


@app.route('/help')
def help_page():
    return render_template('help.html')


# ----- Thumbs (lightweight likes) -----

@app.route('/thumb', methods=['POST'])
@login_required
def thumb():
    kind = request.form.get('kind')
    tid = request.form.get('id', type=int)
    if kind not in ('post', 'rating', 'geeklist', 'geeklist_item') or not tid:
        abort(400)
    existing = Thumb.query.filter_by(user_id=current_user.id, kind=kind, target_id=tid).first()
    if existing:
        db.session.delete(existing)
        delta = -1
    else:
        db.session.add(Thumb(user_id=current_user.id, kind=kind, target_id=tid))
        delta = 1
    if kind == 'post':
        p = db.session.get(Post, tid)
        if p:
            p.thumbs = max(0, (p.thumbs or 0) + delta)
    elif kind == 'rating':
        r = db.session.get(Rating, tid)
        if r:
            r.num_thumbs = max(0, (r.num_thumbs or 0) + delta)
    elif kind == 'geeklist':
        l = db.session.get(GeekList, tid)
        if l:
            l.num_thumbs = max(0, (l.num_thumbs or 0) + delta)
    elif kind == 'geeklist_item':
        i = db.session.get(GeekListItem, tid)
        if i:
            i.num_thumbs = max(0, (i.num_thumbs or 0) + delta)
    db.session.commit()
    nxt = _safe_next(request.form.get('next'), url_for('index'))
    return redirect(nxt)


# ----- Health -----

@app.route('/_health')
def health():
    try:
        return jsonify({
            'ok': True, 'site': 'boardgamegeek',
            'games': Game.query.count(),
            'users': User.query.count(),
            'ratings': Rating.query.count(),
            'threads': Thread.query.count(),
            'geeklists': GeekList.query.count(),
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ----- Utilities -----

def escape_paragraphs(text: str) -> str:
    """User-submitted text: escape, then convert \\n\\n to <p> breaks, autolink URLs."""
    if not text:
        return ''
    s = str(escape(text))
    parts = re.split(r'\n\s*\n', s)
    url_re = re.compile(r'(https?://[^\s<>"]+)')
    paragraphs = []
    for para in parts:
        para = url_re.sub(r'<a href="\1" rel="nofollow">\1</a>', para)
        paragraphs.append('<p>' + para.replace('\n', '<br>') + '</p>')
    return ''.join(paragraphs)


# ----- Bootstrap -----

with app.app_context():
    db.create_all()
    try:
        from seed_data import seed_database, seed_benchmark_users
        seed_database(db, app)
        seed_benchmark_users(db, app, bcrypt)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[boardgamegeek] seed error: {e}")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
