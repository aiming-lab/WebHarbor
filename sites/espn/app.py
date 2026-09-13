#!/usr/bin/env python3
"""ESPN mirror — Flask application with sports data, news, scores, stats."""
import os
import json
import re
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort, g)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_bcrypt import Bcrypt
from wtforms import StringField, PasswordField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional
from sqlalchemy import or_, func

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Mirror clock pin ─────────────────────────────────────────────────────────
# This mirror's content (articles, finalized games, schedules, transactions)
# is frozen in 2024. WebVoyager / WebTau tasks use relative phrases like
# "yesterday", "latest", "past 2 days", "next game", "today's top headline".
# We anchor "today" to a fixed date so those phrases always resolve against
# real data, regardless of wall-clock time when the agent is run.
#
# Picked 2024-04-10 after auditing every date-bearing column AND every
# date-relative WebVoyager task. Rationale:
#
#   yesterday  (anchor − 1d = 2024-04-09):
#     · 2 NBA finalized games (Pacers@Bucks 119-114, Warriors@Nuggets 121-109)
#     · 2 NHL finalized games (Rangers@Bruins 4-2, Oilers@Knights 3-2)
#     · 1 NBA transaction
#   past 2 days  (04-08 / 04-09):  Bucks game, NBA trades / transactions
#   past 3 days  (04-07 / 04-09):  Nuggets game (04-09)
#   past week    (04-03 / 04-09):  5+ NBA transactions
#   latest articles per sport:     04-09 NBA × 4, 04-08 NHL × 1, 04-08 Soccer
#   next scheduled game:           2024-04-14 Nuggets@Lakers (Lakers next)
#   absolute references:           2023-12-25 Christmas Day NBA games (5)
#   season-end framing:            NBA reg season ends mid-April → consistent
#
# No DB row is dated AFTER the anchor except the one intentional 04-14
# scheduled game, so nothing in the seed becomes "from the future."
MIRROR_REFERENCE_DATE = datetime(2024, 4, 10, 12, 0, 0)
MIRROR_REFERENCE_DATE_LABEL = MIRROR_REFERENCE_DATE.strftime('%B %-d, %Y')


def mirror_now() -> datetime:
    """Return the pinned 'now' that all date-relative views use."""
    return MIRROR_REFERENCE_DATE


def mirror_today() -> 'datetime.date':
    """Return the pinned 'today' date."""
    return MIRROR_REFERENCE_DATE.date()


app = Flask(__name__)
app.config['SECRET_KEY'] = 'espn-mirror-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'espn.db')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to access your ESPN account.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)


# ─── Models ───────────────────────────────────────────────────────────────────

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_espn_plus = db.Column(db.Boolean, default=False)

    favorites = db.relationship('UserFavorite', backref='user', lazy=True,
                                cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)

    @property
    def first_name(self):
        return self.name.split()[0] if self.name else ''


class Sport(db.Model):
    __tablename__ = 'sports'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(100), default='')
    url_prefix = db.Column(db.String(50), default='')
    nav_order = db.Column(db.Integer, default=99)
    is_active = db.Column(db.Boolean, default=True)


class Conference(db.Model):
    __tablename__ = 'conferences'
    id = db.Column(db.Integer, primary_key=True)
    sport_slug = db.Column(db.String(50), index=True)
    name = db.Column(db.String(100), nullable=False)
    short_name = db.Column(db.String(50), default='')


class Division(db.Model):
    __tablename__ = 'divisions'
    id = db.Column(db.Integer, primary_key=True)
    conference_id = db.Column(db.Integer, db.ForeignKey('conferences.id'))
    sport_slug = db.Column(db.String(50), index=True)
    name = db.Column(db.String(100), nullable=False)


class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    sport_slug = db.Column(db.String(50), index=True)
    conference_id = db.Column(db.Integer, db.ForeignKey('conferences.id'), nullable=True)
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)  # "Lakers"
    city = db.Column(db.String(100), default='')
    full_name = db.Column(db.String(150), default='')  # "Los Angeles Lakers"
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    abbreviation = db.Column(db.String(10), default='')
    color_primary = db.Column(db.String(10), default='#552583')
    color_secondary = db.Column(db.String(10), default='#FDB927')
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    ties = db.Column(db.Integer, default=0)
    win_pct = db.Column(db.Float, default=0.0)
    games_back = db.Column(db.Float, default=0.0)
    streak = db.Column(db.String(20), default='W1')
    home_record = db.Column(db.String(10), default='0-0')
    away_record = db.Column(db.String(10), default='0-0')
    division_record = db.Column(db.String(10), default='0-0')
    conference_record = db.Column(db.String(10), default='0-0')
    points_for = db.Column(db.Float, default=0.0)
    points_against = db.Column(db.Float, default=0.0)
    power_index = db.Column(db.Float, default=50.0)
    playoff_odds = db.Column(db.Float, default=50.0)
    standing_rank = db.Column(db.Integer, default=1)
    overtime_losses = db.Column(db.Integer, default=0)  # NHL only

    conference = db.relationship('Conference', backref='teams', lazy=True)
    division = db.relationship('Division', backref='teams', lazy=True)
    players = db.relationship('Player', backref='team', lazy=True)
    home_games = db.relationship('Game', foreign_keys='Game.home_team_id',
                                  backref='home_team', lazy=True)
    away_games = db.relationship('Game', foreign_keys='Game.away_team_id',
                                  backref='away_team', lazy=True)
    transactions = db.relationship('Transaction', backref='team', lazy=True)
    depth_chart = db.relationship('DepthChartEntry', backref='team', lazy=True)


class Player(db.Model):
    __tablename__ = 'players'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    sport_slug = db.Column(db.String(50), index=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(80), default='')
    last_name = db.Column(db.String(80), default='')
    position = db.Column(db.String(50), default='')
    jersey_number = db.Column(db.String(5), default='')
    height = db.Column(db.String(10), default='')
    weight = db.Column(db.Integer, default=0)
    age = db.Column(db.Integer, default=0)
    nationality = db.Column(db.String(80), default='USA')
    college = db.Column(db.String(100), default='')
    salary = db.Column(db.Float, default=0.0)
    injury_status = db.Column(db.String(50), default='')
    injury_description = db.Column(db.String(200), default='')
    bio = db.Column(db.Text, default='')
    birth_date = db.Column(db.String(20), default='')
    experience = db.Column(db.Integer, default=0)  # years in league

    stats = db.relationship('PlayerStat', backref='player', lazy=True,
                             cascade='all, delete-orphan')
    depth_chart_entries = db.relationship('DepthChartEntry', backref='player', lazy=True)
    game_stats = db.relationship('GamePlayerStat', backref='player', lazy=True)
    transactions_ref = db.relationship('Transaction', backref='player', lazy=True)


class PlayerStat(db.Model):
    __tablename__ = 'player_stats'
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    season = db.Column(db.String(20), default='2023-24')
    stat_type = db.Column(db.String(20), default='season')  # 'season', 'career'
    games_played = db.Column(db.Integer, default=0)
    games_started = db.Column(db.Integer, default=0)
    # NBA
    points_per_game = db.Column(db.Float, default=0.0)
    rebounds_per_game = db.Column(db.Float, default=0.0)
    assists_per_game = db.Column(db.Float, default=0.0)
    steals_per_game = db.Column(db.Float, default=0.0)
    blocks_per_game = db.Column(db.Float, default=0.0)
    fg_pct = db.Column(db.Float, default=0.0)
    three_pt_pct = db.Column(db.Float, default=0.0)
    ft_pct = db.Column(db.Float, default=0.0)
    minutes_per_game = db.Column(db.Float, default=0.0)
    # Career totals (for career stat_type)
    total_points = db.Column(db.Integer, default=0)
    total_rebounds = db.Column(db.Integer, default=0)
    total_assists = db.Column(db.Integer, default=0)
    total_games = db.Column(db.Integer, default=0)
    # MLB
    batting_avg = db.Column(db.Float, default=0.0)
    home_runs = db.Column(db.Integer, default=0)
    rbi = db.Column(db.Integer, default=0)
    stolen_bases = db.Column(db.Integer, default=0)
    era = db.Column(db.Float, default=0.0)
    strikeouts = db.Column(db.Integer, default=0)
    wins_pitcher = db.Column(db.Integer, default=0)
    # NHL
    goals = db.Column(db.Integer, default=0)
    hockey_assists = db.Column(db.Integer, default=0)
    hockey_points = db.Column(db.Integer, default=0)
    plus_minus = db.Column(db.Integer, default=0)
    penalty_minutes = db.Column(db.Integer, default=0)
    # NFL
    passing_yards = db.Column(db.Integer, default=0)
    passing_tds = db.Column(db.Integer, default=0)
    rushing_yards = db.Column(db.Integer, default=0)
    rushing_tds = db.Column(db.Integer, default=0)
    receiving_yards = db.Column(db.Integer, default=0)
    receiving_tds = db.Column(db.Integer, default=0)
    receptions = db.Column(db.Integer, default=0)
    tackles = db.Column(db.Integer, default=0)
    sacks = db.Column(db.Float, default=0.0)
    # Soccer
    soccer_goals = db.Column(db.Integer, default=0)
    soccer_assists = db.Column(db.Integer, default=0)
    soccer_appearances = db.Column(db.Integer, default=0)
    yellow_cards = db.Column(db.Integer, default=0)
    red_cards = db.Column(db.Integer, default=0)


class Game(db.Model):
    __tablename__ = 'games'
    id = db.Column(db.Integer, primary_key=True)
    sport_slug = db.Column(db.String(50), index=True)
    home_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    away_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    home_score = db.Column(db.Integer, default=0)
    away_score = db.Column(db.Integer, default=0)
    date = db.Column(db.String(20), default='')  # YYYY-MM-DD
    date_display = db.Column(db.String(50), default='')
    time = db.Column(db.String(20), default='7:30 PM ET')
    status = db.Column(db.String(30), default='final')  # 'final', 'scheduled', 'live'
    period = db.Column(db.String(20), default='Final')
    network = db.Column(db.String(50), default='ESPN')
    venue = db.Column(db.String(200), default='')
    recap = db.Column(db.Text, default='')
    ticket_url = db.Column(db.String(500), default='https://www.ticketmaster.com')
    # Leaders stored as JSON
    game_leaders = db.Column(db.Text, default='{}')

    player_stats = db.relationship('GamePlayerStat', backref='game', lazy=True,
                                    cascade='all, delete-orphan')

    def get_leaders(self):
        try:
            return json.loads(self.game_leaders or '{}')
        except Exception:
            return {}


class GamePlayerStat(db.Model):
    __tablename__ = 'game_player_stats'
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    points = db.Column(db.Integer, default=0)
    rebounds = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    steals = db.Column(db.Integer, default=0)
    blocks = db.Column(db.Integer, default=0)
    minutes = db.Column(db.String(10), default='0')

    stat_team = db.relationship('Team', backref='game_player_stats', lazy=True)


class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    sport_slug = db.Column(db.String(50), index=True)
    title = db.Column(db.String(500), nullable=False)
    slug = db.Column(db.String(500), unique=True, nullable=False, index=True)
    subtitle = db.Column(db.String(500), default='')
    body = db.Column(db.Text, default='')
    author = db.Column(db.String(100), default='ESPN Staff')
    image = db.Column(db.String(300), default='')
    tags = db.Column(db.Text, default='[]')
    is_headline = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    published_date = db.Column(db.String(50), default='')

    def get_tags(self):
        try:
            return json.loads(self.tags or '[]')
        except Exception:
            return []


class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    sport_slug = db.Column(db.String(50), index=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=True)
    description = db.Column(db.Text, nullable=False)
    transaction_type = db.Column(db.String(50), default='trade')
    date = db.Column(db.String(20), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DepthChartEntry(db.Model):
    __tablename__ = 'depth_chart'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    position = db.Column(db.String(50), default='')
    position_rank = db.Column(db.Integer, default=1)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    injury_notes = db.Column(db.String(100), default='')


class PowerIndex(db.Model):
    __tablename__ = 'power_index'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    sport_slug = db.Column(db.String(50), index=True)
    season = db.Column(db.String(20), default='2023-24')
    index_value = db.Column(db.Float, default=50.0)
    playoff_odds = db.Column(db.Float, default=50.0)
    avg_point_diff = db.Column(db.Float, default=0.0)
    rank = db.Column(db.Integer, default=1)

    pi_team = db.relationship('Team', backref='power_index_data', lazy=True)


class Recruit(db.Model):
    __tablename__ = 'recruits'
    id = db.Column(db.Integer, primary_key=True)
    sport_slug = db.Column(db.String(50), index=True)
    gender = db.Column(db.String(10), default='M')
    name = db.Column(db.String(150), nullable=False)
    position = db.Column(db.String(50), default='')
    hometown = db.Column(db.String(100), default='')
    committed_to = db.Column(db.String(100), default='')
    stars = db.Column(db.Integer, default=5)
    rank = db.Column(db.Integer, default=1)
    season = db.Column(db.String(20), default='2024-25')
    class_year = db.Column(db.String(10), default='2024')


class UserFavorite(db.Model):
    __tablename__ = 'user_favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_type = db.Column(db.String(20), default='team')
    item_id = db.Column(db.Integer, default=0)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── Login ────────────────────────────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─── Context Processors ───────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    sports = Sport.query.filter_by(is_active=True).order_by(Sport.nav_order).all()
    return {
        'nav_sports': sports,
        'csrf_token_value': generate_csrf(),
        'today': mirror_today().strftime('%Y-%m-%d'),
        'mirror_today_label': MIRROR_REFERENCE_DATE_LABEL,
        'mirror_today_iso':   mirror_today().strftime('%Y-%m-%d'),
    }


# ─── Forms ────────────────────────────────────────────────────────────────────

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm Password',
                            validators=[DataRequired(), EqualTo('password')])


class ProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    phone = StringField('Phone', validators=[Optional()])


class PasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password',
                                 validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm', validators=[DataRequired(), EqualTo('new_password')])


# ─── Helpers ──────────────────────────────────────────────────────────────────

STOPWORDS = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for',
             'with', 'and', 'or', 'is', 'are', 'be', 'by', 'from', 'how',
             'many', 'do', 'does', 'what', 'who', 'which', 'all', 'teams',
             'team', 'league', 'players', 'player', 'nba', 'nfl', 'nhl', 'mlb'}


def _score_team(team, tokens):
    haystack = ' '.join([
        (team.full_name or '').lower(),
        (team.name or '').lower(),
        (team.city or '').lower(),
        (team.abbreviation or '').lower(),
        (team.sport_slug or '').lower(),
    ])
    return sum(1 for t in tokens if t in haystack)


def _score_player(player, tokens):
    haystack = ' '.join([
        (player.name or '').lower(),
        (player.first_name or '').lower(),
        (player.last_name or '').lower(),
        (player.position or '').lower(),
        (player.sport_slug or '').lower(),
    ])
    return sum(1 for t in tokens if t in haystack)


def _score_article(article, tokens):
    haystack = ' '.join([
        (article.title or '').lower(),
        (article.subtitle or '').lower(),
        (article.tags or '').lower(),
        (article.sport_slug or '').lower(),
    ])
    return sum(1 for t in tokens if t in haystack)


def get_recent_headlines(sport_slug=None, limit=5):
    q = Article.query.filter_by(is_headline=True)
    if sport_slug:
        q = q.filter_by(sport_slug=sport_slug)
    return q.order_by(Article.created_at.desc()).limit(limit).all()


def get_recent_scores(sport_slug, limit=10):
    return (Game.query
            .filter_by(sport_slug=sport_slug, status='final')
            .order_by(Game.date.desc())
            .limit(limit).all())


def get_upcoming_games(sport_slug, limit=10):
    today = mirror_today().strftime('%Y-%m-%d')
    return (Game.query
            .filter_by(sport_slug=sport_slug, status='scheduled')
            .filter(Game.date >= today)
            .order_by(Game.date)
            .limit(limit).all())


def get_standings(sport_slug):
    conferences = Conference.query.filter_by(sport_slug=sport_slug).all()
    result = []
    for conf in conferences:
        divs = Division.query.filter_by(conference_id=conf.id).all()
        if divs:
            conf_data = {'conference': conf, 'divisions': []}
            for div in divs:
                teams = (Team.query
                         .filter_by(sport_slug=sport_slug, division_id=div.id)
                         .order_by(Team.standing_rank)
                         .all())
                conf_data['divisions'].append({'division': div, 'teams': teams})
            result.append(conf_data)
        else:
            teams = (Team.query
                     .filter_by(sport_slug=sport_slug, conference_id=conf.id)
                     .order_by(Team.standing_rank)
                     .all())
            result.append({'conference': conf, 'divisions': [], 'teams': teams})
    return result


# ─── Routes: Static Pages ─────────────────────────────────────────────────────

@app.route('/')
def index():
    headlines = Article.query.filter_by(is_headline=True).order_by(
        Article.created_at.desc()).limit(8).all()
    featured = Article.query.filter_by(is_featured=True).order_by(
        Article.created_at.desc()).limit(3).all()
    sports_data = {}
    for s in ['nba', 'nfl', 'nhl', 'mlb', 'soccer']:
        sports_data[s] = {
            'scores': get_recent_scores(s, 5),
            'news': Article.query.filter_by(sport_slug=s).order_by(
                Article.created_at.desc()).limit(3).all(),
        }
    return render_template('index.html', headlines=headlines, featured=featured,
                           sports_data=sports_data)


@app.route('/espnplus')
@app.route('/espn-plus')
def espnplus():
    return render_template('espnplus.html')


# ─── Routes: Sport Sections ───────────────────────────────────────────────────

@app.route('/<sport_slug>/')
@app.route('/<sport_slug>')
def sport_home(sport_slug):
    # Normalize college sport slugs
    slug_map = {
        'college-football': 'ncaaf',
        'mens-college-basketball': 'ncaam',
        'womens-college-basketball': 'ncaaw',
        'ncaa': 'ncaam',
    }
    sport_slug = slug_map.get(sport_slug, sport_slug)
    sport = Sport.query.filter_by(slug=sport_slug).first_or_404()
    headlines = Article.query.filter_by(sport_slug=sport_slug, is_headline=True).order_by(
        Article.created_at.desc()).limit(5).all()
    articles = Article.query.filter_by(sport_slug=sport_slug).order_by(
        Article.created_at.desc()).limit(12).all()
    scores = get_recent_scores(sport_slug, 6)
    upcoming = get_upcoming_games(sport_slug, 6)
    return render_template('sport_home.html', sport=sport,
                           headlines=headlines, articles=articles,
                           scores=scores, upcoming=upcoming)


@app.route('/<sport_slug>/news')
def sport_news(sport_slug):
    slug_map = {'college-football': 'ncaaf', 'mens-college-basketball': 'ncaam',
                'womens-college-basketball': 'ncaaw'}
    sport_slug = slug_map.get(sport_slug, sport_slug)
    sport = Sport.query.filter_by(slug=sport_slug).first_or_404()
    page = request.args.get('page', 1, type=int)
    articles = (Article.query.filter_by(sport_slug=sport_slug)
                .order_by(Article.created_at.desc())
                .paginate(page=page, per_page=20, error_out=False))
    return render_template('sport_news.html', sport=sport, articles=articles)


@app.route('/<sport_slug>/scoreboard')
@app.route('/<sport_slug>/scores')
def scoreboard(sport_slug):
    slug_map = {'college-football': 'ncaaf', 'mens-college-basketball': 'ncaam',
                'womens-college-basketball': 'ncaaw'}
    sport_slug = slug_map.get(sport_slug, sport_slug)
    sport = Sport.query.filter_by(slug=sport_slug).first_or_404()
    date_str = request.args.get('date', '')
    if date_str:
        # Accept YYYYMMDD format
        if len(date_str) == 8:
            try:
                date_obj = datetime.strptime(date_str, '%Y%m%d')
                date_str = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                pass
        games = Game.query.filter_by(sport_slug=sport_slug, date=date_str).all()
        date_display = date_str
    else:
        games = (Game.query.filter_by(sport_slug=sport_slug, status='final')
                 .order_by(Game.date.desc()).limit(15).all())
        date_display = 'Recent'
    upcoming = get_upcoming_games(sport_slug, 5)
    return render_template('scoreboard.html', sport=sport, games=games,
                           upcoming=upcoming, date_display=date_display,
                           date_str=date_str)


@app.route('/scores')
def all_scores():
    date_str = request.args.get('date', '')
    sport_filter = request.args.get('sport', '')
    games_by_sport = {}
    sports = Sport.query.filter_by(is_active=True).all()
    for sp in sports:
        if sport_filter and sp.slug != sport_filter:
            continue
        if date_str:
            if len(date_str) == 8:
                try:
                    date_obj = datetime.strptime(date_str, '%Y%m%d')
                    date_str_q = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    date_str_q = date_str
            else:
                date_str_q = date_str
            games = Game.query.filter_by(sport_slug=sp.slug, date=date_str_q).all()
        else:
            games = (Game.query.filter_by(sport_slug=sp.slug, status='final')
                     .order_by(Game.date.desc()).limit(5).all())
        if games:
            games_by_sport[sp] = games
    return render_template('all_scores.html', games_by_sport=games_by_sport,
                           date_str=date_str)


@app.route('/<sport_slug>/standings')
def standings(sport_slug):
    slug_map = {'college-football': 'ncaaf', 'mens-college-basketball': 'ncaam',
                'womens-college-basketball': 'ncaaw'}
    sport_slug = slug_map.get(sport_slug, sport_slug)
    sport = Sport.query.filter_by(slug=sport_slug).first_or_404()
    standings_data = get_standings(sport_slug)
    # Flat list for division-less display
    all_teams = Team.query.filter_by(sport_slug=sport_slug).order_by(
        Team.standing_rank).all()
    return render_template('standings.html', sport=sport,
                           standings_data=standings_data, all_teams=all_teams)


@app.route('/<sport_slug>/teams')
def teams_list(sport_slug):
    slug_map = {'college-football': 'ncaaf', 'mens-college-basketball': 'ncaam',
                'womens-college-basketball': 'ncaaw'}
    sport_slug = slug_map.get(sport_slug, sport_slug)
    sport = Sport.query.filter_by(slug=sport_slug).first_or_404()
    conferences = Conference.query.filter_by(sport_slug=sport_slug).all()
    teams_by_conf = {}
    for conf in conferences:
        divs = Division.query.filter_by(conference_id=conf.id).all()
        if divs:
            conf_data = {}
            for div in divs:
                conf_data[div.name] = Team.query.filter_by(
                    sport_slug=sport_slug, division_id=div.id).order_by(
                    Team.full_name).all()
            teams_by_conf[conf.name] = conf_data
        else:
            teams_by_conf[conf.name] = {'All': Team.query.filter_by(
                sport_slug=sport_slug, conference_id=conf.id).order_by(
                Team.full_name).all()}
    all_teams = Team.query.filter_by(sport_slug=sport_slug).order_by(
        Team.full_name).all()
    return render_template('teams_list.html', sport=sport,
                           teams_by_conf=teams_by_conf, all_teams=all_teams)


@app.route('/<sport_slug>/schedule')
def sport_schedule(sport_slug):
    slug_map = {'college-football': 'ncaaf', 'mens-college-basketball': 'ncaam',
                'womens-college-basketball': 'ncaaw'}
    sport_slug = slug_map.get(sport_slug, sport_slug)
    sport = Sport.query.filter_by(slug=sport_slug).first_or_404()
    games = (Game.query.filter_by(sport_slug=sport_slug)
             .order_by(Game.date.desc()).limit(50).all())
    return render_template('schedule.html', sport=sport, games=games)


@app.route('/<sport_slug>/transactions')
def sport_transactions(sport_slug):
    slug_map = {'college-football': 'ncaaf', 'mens-college-basketball': 'ncaam',
                'womens-college-basketball': 'ncaaw'}
    sport_slug = slug_map.get(sport_slug, sport_slug)
    sport = Sport.query.filter_by(slug=sport_slug).first_or_404()
    transactions = (Transaction.query.filter_by(sport_slug=sport_slug)
                    .order_by(Transaction.created_at.desc()).limit(50).all())
    return render_template('transactions.html', sport=sport,
                           transactions=transactions)


@app.route('/nba/bpi')
def nba_bpi():
    sport = Sport.query.filter_by(slug='nba').first_or_404()
    rankings = (PowerIndex.query.filter_by(sport_slug='nba', season='2023-24')
                .order_by(PowerIndex.rank).all())
    return render_template('power_index.html', sport=sport, rankings=rankings,
                           index_name='NBA Basketball Power Index',
                           abbrev='BPI', season='2023-24')


@app.route('/nfl/fpi')
def nfl_fpi():
    sport = Sport.query.filter_by(slug='nfl').first_or_404()
    rankings = (PowerIndex.query.filter_by(sport_slug='nfl', season='2023-24')
                .order_by(PowerIndex.rank).all())
    return render_template('power_index.html', sport=sport, rankings=rankings,
                           index_name='NFL Football Power Index',
                           abbrev='FPI', season='2023-24')


@app.route('/soccer/spi')
def soccer_spi():
    sport = Sport.query.filter_by(slug='soccer').first_or_404()
    rankings = (PowerIndex.query.filter_by(sport_slug='soccer', season='2023-24')
                .order_by(PowerIndex.rank).all())
    return render_template('power_index.html', sport=sport, rankings=rankings,
                           index_name='Soccer Power Index',
                           abbrev='SPI', season='2023-24')


@app.route('/womens-college-basketball/recruiting')
@app.route('/ncaaw/recruiting')
def ncaaw_recruiting():
    sport = Sport.query.filter_by(slug='ncaaw').first_or_404()
    recruits = (Recruit.query.filter_by(sport_slug='ncaaw')
                .order_by(Recruit.rank).all())
    return render_template('recruiting.html', sport=sport, recruits=recruits,
                           gender='Women\'s')


@app.route('/mens-college-basketball/recruiting')
@app.route('/ncaam/recruiting')
def ncaam_recruiting():
    sport = Sport.query.filter_by(slug='ncaam').first_or_404()
    recruits = (Recruit.query.filter_by(sport_slug='ncaam', gender='M')
                .order_by(Recruit.rank).all())
    return render_template('recruiting.html', sport=sport, recruits=recruits,
                           gender='Men\'s')


# ─── Routes: Team Pages ───────────────────────────────────────────────────────

@app.route('/team/<sport_slug>/<team_slug>')
def team_home(sport_slug, team_slug):
    team = Team.query.filter_by(slug=team_slug).first_or_404()
    sport = Sport.query.filter_by(slug=sport_slug).first()
    recent_games = (Game.query.filter(
        (Game.home_team_id == team.id) | (Game.away_team_id == team.id),
        Game.status == 'final'
    ).order_by(Game.date.desc()).limit(5).all())
    upcoming = (Game.query.filter(
        (Game.home_team_id == team.id) | (Game.away_team_id == team.id),
        Game.status == 'scheduled'
    ).order_by(Game.date).limit(3).all())
    news = Article.query.filter(
        Article.tags.ilike(f'%{team.full_name}%')
    ).order_by(Article.created_at.desc()).limit(5).all()
    injuries = Player.query.filter_by(team_id=team.id).filter(
        Player.injury_status != '').all()
    return render_template('team_home.html', team=team, sport=sport,
                           recent_games=recent_games, upcoming=upcoming,
                           news=news, injuries=injuries)


@app.route('/team/<sport_slug>/<team_slug>/roster')
def team_roster(sport_slug, team_slug):
    team = Team.query.filter_by(slug=team_slug).first_or_404()
    sport = Sport.query.filter_by(slug=sport_slug).first()
    players = Player.query.filter_by(team_id=team.id).order_by(
        Player.position, Player.last_name).all()
    return render_template('team_roster.html', team=team, sport=sport,
                           players=players)


@app.route('/team/<sport_slug>/<team_slug>/schedule')
def team_schedule(sport_slug, team_slug):
    team = Team.query.filter_by(slug=team_slug).first_or_404()
    sport = Sport.query.filter_by(slug=sport_slug).first()
    games = (Game.query.filter(
        (Game.home_team_id == team.id) | (Game.away_team_id == team.id)
    ).order_by(Game.date.desc()).limit(40).all())
    next_game = (Game.query.filter(
        (Game.home_team_id == team.id) | (Game.away_team_id == team.id),
        Game.status == 'scheduled'
    ).order_by(Game.date).first())
    return render_template('team_schedule.html', team=team, sport=sport,
                           games=games, next_game=next_game)


@app.route('/team/<sport_slug>/<team_slug>/stats')
def team_stats(sport_slug, team_slug):
    team = Team.query.filter_by(slug=team_slug).first_or_404()
    sport = Sport.query.filter_by(slug=sport_slug).first()
    players = Player.query.filter_by(team_id=team.id).order_by(
        Player.last_name).all()
    player_season_stats = []
    for p in players:
        s = PlayerStat.query.filter_by(player_id=p.id,
                                        season='2023-24',
                                        stat_type='season').first()
        player_season_stats.append((p, s))
    total_gp = len(players)
    return render_template('team_stats.html', team=team, sport=sport,
                           player_season_stats=player_season_stats,
                           total_gp=total_gp)


@app.route('/team/<sport_slug>/<team_slug>/injuries')
def team_injuries(sport_slug, team_slug):
    team = Team.query.filter_by(slug=team_slug).first_or_404()
    sport = Sport.query.filter_by(slug=sport_slug).first()
    players = Player.query.filter_by(team_id=team.id).filter(
        Player.injury_status != '').all()
    return render_template('team_injuries.html', team=team, sport=sport,
                           players=players)


@app.route('/team/<sport_slug>/<team_slug>/transactions')
def team_transactions(sport_slug, team_slug):
    team = Team.query.filter_by(slug=team_slug).first_or_404()
    sport = Sport.query.filter_by(slug=sport_slug).first()
    transactions = (Transaction.query.filter_by(team_id=team.id)
                    .order_by(Transaction.created_at.desc()).limit(30).all())
    return render_template('team_transactions.html', team=team, sport=sport,
                           transactions=transactions)


@app.route('/team/<sport_slug>/<team_slug>/depth-chart')
def team_depth_chart(sport_slug, team_slug):
    team = Team.query.filter_by(slug=team_slug).first_or_404()
    sport = Sport.query.filter_by(slug=sport_slug).first()
    entries = (DepthChartEntry.query.filter_by(team_id=team.id)
               .order_by(DepthChartEntry.position,
                         DepthChartEntry.position_rank).all())
    # Group by position
    by_position = {}
    for entry in entries:
        if entry.position not in by_position:
            by_position[entry.position] = []
        by_position[entry.position].append(entry)
    return render_template('team_depth_chart.html', team=team, sport=sport,
                           by_position=by_position)


# ─── Routes: Player Pages ─────────────────────────────────────────────────────

@app.route('/player/<sport_slug>/<player_slug>')
def player_profile(sport_slug, player_slug):
    player = Player.query.filter_by(slug=player_slug).first_or_404()
    sport = Sport.query.filter_by(slug=sport_slug).first()
    season_stats = PlayerStat.query.filter_by(
        player_id=player.id, season='2023-24', stat_type='season').first()
    career_stats = PlayerStat.query.filter_by(
        player_id=player.id, stat_type='career').first()
    recent_games_stats = (GamePlayerStat.query.filter_by(player_id=player.id)
                          .limit(10).all())
    return render_template('player_profile.html', player=player, sport=sport,
                           season_stats=season_stats, career_stats=career_stats,
                           recent_games_stats=recent_games_stats)


@app.route('/player/<sport_slug>/<player_slug>/gamelog')
def player_gamelog(sport_slug, player_slug):
    player = Player.query.filter_by(slug=player_slug).first_or_404()
    sport = Sport.query.filter_by(slug=sport_slug).first()
    # Order by game date desc so "last N games" reads top-down.
    game_stats = (db.session.query(GamePlayerStat)
                  .join(Game, Game.id == GamePlayerStat.game_id)
                  .filter(GamePlayerStat.player_id == player.id,
                          Game.status == 'final')
                  .order_by(Game.date.desc())
                  .limit(30).all())
    # Build a per-row "opponent / result" view-model so the template can
    # show real game context (needed for soccer, but useful everywhere).
    rows = []
    for gs in game_stats:
        g = Game.query.get(gs.game_id)
        is_home = g and g.home_team_id == player.team_id
        opp = (g.away_team if is_home else g.home_team) if g else None
        team_score = (g.home_score if is_home else g.away_score) if g else None
        opp_score  = (g.away_score if is_home else g.home_score) if g else None
        result = None
        if team_score is not None and opp_score is not None:
            result = 'W' if team_score > opp_score else ('L' if team_score < opp_score else 'D')
        rows.append({
            'gs': gs, 'game': g,
            'opp': opp, 'is_home': is_home,
            'team_score': team_score, 'opp_score': opp_score,
            'result': result,
        })
    return render_template('player_gamelog.html', player=player, sport=sport,
                           game_stats=game_stats, rows=rows)


# ─── Routes: Game Pages ───────────────────────────────────────────────────────

@app.route('/game/<int:game_id>')
def game_detail(game_id):
    game = Game.query.get_or_404(game_id)
    sport = Sport.query.filter_by(slug=game.sport_slug).first()
    home_team = Team.query.get(game.home_team_id)
    away_team = Team.query.get(game.away_team_id)
    home_stats = (GamePlayerStat.query.filter_by(game_id=game.id,
                                                  team_id=home_team.id if home_team else 0)
                  .order_by(GamePlayerStat.points.desc()).all())
    away_stats = (GamePlayerStat.query.filter_by(game_id=game.id,
                                                  team_id=away_team.id if away_team else 0)
                  .order_by(GamePlayerStat.points.desc()).all())
    leaders = game.get_leaders()
    return render_template('game_detail.html', game=game, sport=sport,
                           home_team=home_team, away_team=away_team,
                           home_stats=home_stats, away_stats=away_stats,
                           leaders=leaders)


@app.route('/tickets/<int:game_id>')
def tickets(game_id):
    """Mock ticket-purchase page with deterministic price tiers."""
    game = Game.query.get_or_404(game_id)
    sport = Sport.query.filter_by(slug=game.sport_slug).first()
    home_team = Team.query.get(game.home_team_id)
    away_team = Team.query.get(game.away_team_id)
    # Deterministic tiers by game id so prices are stable across page loads.
    base = 35 + (game.id * 7) % 25
    tiers = [
        {'name': 'Upper Level',     'section': '300-Level',  'price': base},
        {'name': 'Mezzanine',       'section': '200-Level',  'price': base + 45},
        {'name': 'Lower Bowl',      'section': '100-Level',  'price': base + 120},
        {'name': 'Club Level',      'section': 'Club',       'price': base + 240},
        {'name': 'Courtside / Floor','section': 'Floor',     'price': base + 520},
    ]
    return render_template('tickets.html', game=game, sport=sport,
                           home_team=home_team, away_team=away_team,
                           tiers=tiers)


# ─── Routes: Articles ─────────────────────────────────────────────────────────

@app.route('/story/<slug>')
@app.route('/article/<slug>')
def article(slug):
    art = Article.query.filter_by(slug=slug).first_or_404()
    sport = Sport.query.filter_by(slug=art.sport_slug).first()
    related = (Article.query.filter_by(sport_slug=art.sport_slug)
               .filter(Article.id != art.id)
               .order_by(Article.created_at.desc()).limit(4).all())
    return render_template('article.html', article=art, sport=sport,
                           related=related)


# ─── Routes: Search ───────────────────────────────────────────────────────────

@app.route('/search')
@app.route('/search/_/q/<path:espn_query>')
def search(espn_query=''):
    q = (espn_query or request.args.get('q', '')).strip()
    sport_filter = request.args.get('sport', '')
    type_filter = request.args.get('type', '')  # teams, players, articles

    teams = []
    players = []
    articles_list = []

    if q:
        tokens = [t.lower() for t in re.findall(r'[a-z0-9]+', q.lower())
                  if t not in STOPWORDS and len(t) >= 2]
        min_req = max(1, len(tokens) // 2) if tokens else 1

        # Search teams
        if not type_filter or type_filter == 'teams':
            all_teams = Team.query
            if sport_filter:
                all_teams = all_teams.filter_by(sport_slug=sport_filter)
            scored_teams = [(s, t) for t in all_teams.all()
                            if (s := _score_team(t, tokens)) >= min_req]
            scored_teams.sort(key=lambda x: -x[0])
            teams = [t for _, t in scored_teams[:20]]

        # Search players
        if not type_filter or type_filter == 'players':
            all_players = Player.query
            if sport_filter:
                all_players = all_players.filter_by(sport_slug=sport_filter)
            scored_players = [(s, p) for p in all_players.all()
                              if (s := _score_player(p, tokens)) >= min_req]
            scored_players.sort(key=lambda x: -x[0])
            players = [p for _, p in scored_players[:20]]

        # Search articles
        if not type_filter or type_filter == 'articles':
            all_articles = Article.query
            if sport_filter:
                all_articles = all_articles.filter_by(sport_slug=sport_filter)
            scored_articles = [(s, a) for a in all_articles.all()
                               if (s := _score_article(a, tokens)) >= min_req]
            scored_articles.sort(key=lambda x: -x[0])
            articles_list = [a for _, a in scored_articles[:20]]

    sports = Sport.query.filter_by(is_active=True).order_by(Sport.nav_order).all()
    return render_template('search.html', query=q, teams=teams,
                           players=players, articles=articles_list,
                           sports=sports, sport_filter=sport_filter,
                           type_filter=type_filter)


# ─── Routes: Auth ─────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
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
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html', form=form)
        user = User(name=form.name.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f'Welcome to ESPN, {user.first_name}!', 'success')
        return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


# ─── Routes: Account ──────────────────────────────────────────────────────────

@app.route('/account')
@login_required
def account():
    favorites = UserFavorite.query.filter_by(user_id=current_user.id).all()
    fav_teams = []
    fav_players = []
    for fav in favorites:
        if fav.item_type == 'team':
            t = Team.query.get(fav.item_id)
            if t:
                fav_teams.append((fav.id, t))
        elif fav.item_type == 'player':
            p = Player.query.get(fav.item_id)
            if p:
                fav_players.append((fav.id, p))
    return render_template('account.html', fav_teams=fav_teams,
                           fav_players=fav_players)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.phone = form.phone.data
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('account'))
    return render_template('account_edit.html', form=form)


@app.route('/account/password', methods=['GET', 'POST'])
@login_required
def account_password():
    form = PasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return render_template('account_password.html', form=form)
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Password changed successfully.', 'success')
        return redirect(url_for('account'))
    return render_template('account_password.html', form=form)


@app.route('/account/delete', methods=['POST'])
@login_required
def account_delete():
    user = User.query.get(current_user.id)
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash('Your account has been deleted.', 'info')
    return redirect(url_for('index'))


# ─── Routes: Favorites API ────────────────────────────────────────────────────

@csrf.exempt
@app.route('/api/favorites/toggle', methods=['POST'])
def api_favorite_toggle():
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Login required'}), 401
    # Support both JSON (legacy) and form POST
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form
    item_type = data.get('type', 'team')
    item_id = int(data.get('id', 0))
    existing = UserFavorite.query.filter_by(
        user_id=current_user.id, item_type=item_type, item_id=item_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        action = 'removed'
    else:
        fav = UserFavorite(user_id=current_user.id, item_type=item_type,
                           item_id=item_id)
        db.session.add(fav)
        db.session.commit()
        action = 'added'
    # If form POST, redirect back; if JSON, return JSON
    if not request.is_json:
        next_url = data.get('next') or request.referrer or url_for('account')
        flash(f'{"Added to" if action == "added" else "Removed from"} favorites.', 'success')
        return redirect(next_url)
    return jsonify({'success': True, 'action': action})


# ─── Routes: Stats Leaders ────────────────────────────────────────────────────

@app.route('/nba/stats/leaders')
@app.route('/nba/players')
def nba_stat_leaders():
    sport = Sport.query.filter_by(slug='nba').first_or_404()
    stat = request.args.get('stat', 'points')
    season = request.args.get('season', '2023-24')
    conf_filter = request.args.get('conference', '')

    # Get all NBA player stats
    stats_q = (db.session.query(Player, PlayerStat)
               .join(PlayerStat, Player.id == PlayerStat.player_id)
               .filter(Player.sport_slug == 'nba',
                       PlayerStat.season == season,
                       PlayerStat.stat_type == 'season'))

    if conf_filter:
        stats_q = stats_q.join(Team, Player.team_id == Team.id).join(
            Conference, Team.conference_id == Conference.id).filter(
            Conference.name.ilike(f'%{conf_filter}%'))

    all_stats = stats_q.all()

    sort_map = {
        'points': lambda x: x[1].points_per_game,
        'rebounds': lambda x: x[1].rebounds_per_game,
        'assists': lambda x: x[1].assists_per_game,
        'steals': lambda x: x[1].steals_per_game,
        'blocks': lambda x: x[1].blocks_per_game,
    }
    sort_fn = sort_map.get(stat, sort_map['points'])
    all_stats.sort(key=sort_fn, reverse=True)
    leaders = all_stats[:25]

    return render_template('stat_leaders.html', sport=sport, leaders=leaders,
                           stat=stat, season=season, conf_filter=conf_filter)


@app.route('/nba/statistics')
def nba_statistics():
    return redirect(url_for('nba_stat_leaders'))


# ─── Routes: Stats Pages ──────────────────────────────────────────────────────

@app.route('/<sport_slug>/statistics')
@app.route('/<sport_slug>/stats')
def sport_stats(sport_slug):
    slug_map = {'college-football': 'ncaaf', 'mens-college-basketball': 'ncaam',
                'womens-college-basketball': 'ncaaw'}
    sport_slug = slug_map.get(sport_slug, sport_slug)
    sport = Sport.query.filter_by(slug=sport_slug).first_or_404()
    stat = request.args.get('stat', 'points')
    season = request.args.get('season', '2023-24')
    conf_filter = request.args.get('conference', '').strip()

    stats_q = (db.session.query(Player, PlayerStat)
               .join(PlayerStat, Player.id == PlayerStat.player_id)
               .filter(Player.sport_slug == sport_slug,
                       PlayerStat.season == season,
                       PlayerStat.stat_type == 'season'))
    if conf_filter:
        stats_q = (stats_q
                   .join(Team, Player.team_id == Team.id)
                   .join(Conference, Team.conference_id == Conference.id)
                   .filter(Conference.name.ilike(f'%{conf_filter}%')))
    all_stats = stats_q.all()

    if sport_slug in ('nba', 'ncaam', 'ncaaw'):
        sort_map = {'points': lambda x: x[1].points_per_game,
                    'rebounds': lambda x: x[1].rebounds_per_game,
                    'assists': lambda x: x[1].assists_per_game,
                    'steals': lambda x: x[1].steals_per_game,
                    'blocks': lambda x: x[1].blocks_per_game}
    elif sport_slug in ('nfl',):
        sort_map = {'passing': lambda x: x[1].passing_yards,
                    'rushing': lambda x: x[1].rushing_yards,
                    'receiving': lambda x: x[1].receiving_yards}
    else:
        sort_map = {'points': lambda x: x[1].points_per_game}
    sort_fn = sort_map.get(stat, next(iter(sort_map.values())))
    all_stats.sort(key=sort_fn, reverse=True)
    leaders = all_stats[:25]
    return render_template('stat_leaders.html', sport=sport, leaders=leaders,
                           stat=stat, season=season, conf_filter=conf_filter)


# ─── Seed Data ────────────────────────────────────────────────────────────────

def seed_database():
    if Sport.query.first():
        return  # Already seeded

    # ----- Sports -----
    sports_data = [
        ('NFL', 'nfl', 'National Football League', '/nfl/', 1),
        ('NBA', 'nba', 'National Basketball Association', '/nba/', 2),
        ('MLB', 'mlb', 'Major League Baseball', '/mlb/', 3),
        ('NHL', 'nhl', 'National Hockey League', '/nhl/', 4),
        ('Soccer', 'soccer', 'Soccer', '/soccer/', 5),
        ('College Football', 'ncaaf', 'College Football', '/college-football/', 6),
        ('Men\'s College Basketball', 'ncaam', "Men's College Basketball",
         '/mens-college-basketball/', 7),
        ('Women\'s College Basketball', 'ncaaw', "Women's College Basketball",
         '/womens-college-basketball/', 8),
        ('Tennis', 'tennis', 'Tennis', '/tennis/', 9),
        ('Golf', 'golf', 'Golf', '/golf/', 10),
        ('MMA', 'mma', 'MMA', '/mma/', 11),
        ('Fantasy', 'fantasy', 'Fantasy Sports', '/fantasy/', 12),
    ]
    for name, slug, display, prefix, order in sports_data:
        db.session.add(Sport(name=name, slug=slug, display_name=display,
                             url_prefix=prefix, nav_order=order))
    db.session.flush()

    from seed_data import seed_all
    seed_all(db, Conference, Division, Team, Player, PlayerStat, Game,
             GamePlayerStat, Article, Transaction, DepthChartEntry,
             PowerIndex, Recruit)
    db.session.commit()


def seed_benchmark_users():
    """Idempotent: creates 4 benchmark users with favorites seeded from DB."""
    if User.query.filter_by(email='alice.j@test.com').first():
        return  # already seeded

    # Helper to look up team/player by slug
    def _team(slug):
        return Team.query.filter_by(slug=slug).first()

    def _player(slug):
        return Player.query.filter_by(slug=slug).first()

    users_def = [
        {
            'email': 'alice.j@test.com',
            'name': 'Alice Johnson',
            'is_espn_plus': True,
            'team_slugs': ['boston-celtics', 'new-england-patriots', 'boston-red-sox'],
            'player_slugs': ['jayson-tatum', 'lebron-james'],
        },
        {
            'email': 'bob.c@test.com',
            'name': 'Bob Chen',
            'is_espn_plus': False,
            'team_slugs': ['los-angeles-lakers', 'golden-state-warriors', 'los-angeles-rams'],
            'player_slugs': ['lebron-james', 'stephen-curry', 'anthony-davis'],
        },
        {
            'email': 'carol.d@test.com',
            'name': 'Carol Davis',
            'is_espn_plus': True,
            'team_slugs': ['miami-heat', 'chicago-bulls'],
            'player_slugs': ['jimmy-butler', 'giannis-antetokounmpo'],
        },
        {
            'email': 'david.k@test.com',
            'name': 'David Kim',
            'is_espn_plus': False,
            'team_slugs': ['dallas-mavericks', 'oklahoma-city-thunder', 'denver-nuggets'],
            'player_slugs': ['luka-doncic', 'nikola-jokic', 'shai-gilgeous-alexander'],
        },
    ]

    for ud in users_def:
        user = User(email=ud['email'], name=ud['name'],
                    is_espn_plus=ud['is_espn_plus'])
        user.set_password('TestPass123!')
        db.session.add(user)
        db.session.flush()  # get user.id

        for tslug in ud['team_slugs']:
            t = _team(tslug)
            if t:
                db.session.add(UserFavorite(user_id=user.id,
                                            item_type='team', item_id=t.id))
        for pslug in ud['player_slugs']:
            p = _player(pslug)
            if p:
                db.session.add(UserFavorite(user_id=user.id,
                                            item_type='player', item_id=p.id))

    db.session.commit()


@app.before_request
def ensure_seeded():
    pass  # Seeding done at startup


# ─── Error Handlers ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
