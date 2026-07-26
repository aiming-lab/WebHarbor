#!/usr/bin/env python3
"""Google Finance mirror — Flask application.

Routes + SQLAlchemy models for an offline mirror of google.com/finance.
Runtime data comes entirely from instance/google_finance.db (restored from
instance_seed/google_finance.db at boot and on /reset). No request handler
reads a file from scraped_data/.

The market clock is frozen at _market_data.MARKET_DATE so every page, every
"N hours ago" and every task answer is identical across runs.
"""
import json
import math
import os
import re
from datetime import datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from markupsafe import Markup
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func, or_
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, Email, EqualTo, Length

import _market_data as MD

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'google-finance-mirror-secret-key'
# Overridable so the seed-regeneration tooling can build instance_seed/
# directly instead of the runtime instance/.
DB_PATH = (os.environ.get('GF_DB_PATH')
           or os.path.join(BASE_DIR, 'instance', 'google_finance.db'))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Sign in to use lists and portfolios.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

STOPWORDS = {'a', 'an', 'the', 'of', 'to', 'in', 'on', 'for', 'and', 'or',
             'is', 'are', 'be', 'with', 'as', 'by', 'at', 'from', 'stock',
             'stocks', 'share', 'shares', 'price', 'quote', 'inc', 'corp'}

REGIONS = [('us', 'US'), ('europe', 'Europe'), ('asia', 'Asia'),
           ('latam', 'Latin America'), ('currencies', 'Currencies'),
           ('crypto', 'Crypto'), ('futures', 'Futures')]

MARKET_PAGES = [
    ('most-active', 'Most active'),
    ('gainers', 'Gainers'),
    ('losers', 'Losers'),
    ('indexes', 'Market indexes'),
    ('cryptocurrencies', 'Cryptocurrencies'),
    ('currencies', 'Currencies'),
    ('futures', 'Futures'),
    ('climate-leaders', 'Climate leaders'),
]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    watchlists = db.relationship('Watchlist', backref='user', lazy=True,
                                 cascade='all, delete-orphan')
    portfolios = db.relationship('Portfolio', backref='user', lazy=True,
                                 cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Instrument(db.Model):
    __tablename__ = 'instruments'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    ticker = db.Column(db.String(24), nullable=False, index=True)
    exchange = db.Column(db.String(24), default='')
    name = db.Column(db.String(160), nullable=False)
    short_name = db.Column(db.String(60), default='')   # index-card label
    # stock | etf | index | sector | crypto | currency | future
    kind = db.Column(db.String(16), nullable=False, index=True)
    sector = db.Column(db.String(60), default='', index=True)
    industry = db.Column(db.String(120), default='')
    currency = db.Column(db.String(8), default='USD')
    region = db.Column(db.String(16), default='us', index=True)
    logo_file = db.Column(db.String(120), default='')
    profile = db.Column(db.Text, default='')
    ceo = db.Column(db.String(120), default='')
    headquarters = db.Column(db.String(160), default='')
    founded = db.Column(db.String(60), default='')
    employees = db.Column(db.String(40), default='')
    website = db.Column(db.String(160), default='')
    is_climate_leader = db.Column(db.Boolean, default=False, index=True)
    related_json = db.Column(db.Text, default='[]')

    quote = db.relationship('Quote', backref='instrument', uselist=False,
                            cascade='all, delete-orphan')
    history = db.relationship('PriceHistory', backref='instrument',
                              uselist=False, cascade='all, delete-orphan')

    @property
    def related_slugs(self):
        try:
            return json.loads(self.related_json or '[]')
        except Exception:
            return []

    @property
    def card_name(self):
        return self.short_name or self.name

    @property
    def display_symbol(self):
        return f"{self.ticker}:{self.exchange}" if self.exchange else self.ticker

    @property
    def logo_url(self):
        if self.logo_file:
            return url_for('static', filename=f'images/{self.logo_file}')
        return None


class Quote(db.Model):
    __tablename__ = 'quotes'
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                              nullable=False, unique=True)
    price = db.Column(db.Float, nullable=False)
    prev_close = db.Column(db.Float, nullable=False)
    change = db.Column(db.Float, nullable=False)
    change_pct = db.Column(db.Float, nullable=False, index=True)
    day_open = db.Column(db.Float)
    day_high = db.Column(db.Float)
    day_low = db.Column(db.Float)
    wk52_high = db.Column(db.Float)
    wk52_low = db.Column(db.Float)
    volume = db.Column(db.BigInteger, index=True)
    avg_volume = db.Column(db.BigInteger)
    shares_outstanding = db.Column(db.BigInteger)
    mkt_cap = db.Column(db.Float, index=True)
    eps = db.Column(db.Float)
    pe_ratio = db.Column(db.Float)
    beta = db.Column(db.Float)
    dividend_yield = db.Column(db.Float)
    quarterly_dividend = db.Column(db.Float)
    ex_dividend_date = db.Column(db.String(40))
    after_price = db.Column(db.Float)
    after_change = db.Column(db.Float)
    after_change_pct = db.Column(db.Float)


class PriceHistory(db.Model):
    __tablename__ = 'price_history'
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                              nullable=False, unique=True)
    daily_json = db.Column(db.Text, nullable=False)       # closes, oldest first
    volume_json = db.Column(db.Text, nullable=False)
    intraday_json = db.Column(db.Text, nullable=False)    # final session
    intraday_volume_json = db.Column(db.Text, default='[]')
    intraday5d_json = db.Column(db.Text, nullable=False)
    after_json = db.Column(db.Text, default='[]')         # post-close leg

    def closes(self):
        return json.loads(self.daily_json)

    def volumes(self):
        return json.loads(self.volume_json)

    def intraday(self):
        return json.loads(self.intraday_json)

    def intraday_volumes(self):
        return json.loads(self.intraday_volume_json or '[]')

    def intraday5d(self):
        return json.loads(self.intraday5d_json)

    def after(self):
        return json.loads(self.after_json or '[]')


class FinancialRow(db.Model):
    __tablename__ = 'financial_rows'
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                              nullable=False, index=True)
    statement = db.Column(db.String(16), nullable=False)    # income|balance|cashflow
    period_type = db.Column(db.String(12), nullable=False)   # quarterly|annual
    period_label = db.Column(db.String(20), nullable=False)
    ordinal = db.Column(db.Integer, default=0)
    items_json = db.Column(db.Text, nullable=False)

    def items(self):
        return json.loads(self.items_json)


class EarningsRow(db.Model):
    __tablename__ = 'earnings_rows'
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                              nullable=False, index=True)
    quarter = db.Column(db.String(20), nullable=False)
    report_date = db.Column(db.String(12), nullable=False)
    eps_estimate = db.Column(db.Float)
    eps_actual = db.Column(db.Float)
    revenue_estimate = db.Column(db.Float)
    revenue_actual = db.Column(db.Float)
    surprise_pct = db.Column(db.Float)


class KeyMoment(db.Model):
    """A dated event Google marks with an orange halo on the long-range chart."""
    __tablename__ = 'key_moments'
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                              nullable=False, index=True)
    moment_date = db.Column(db.String(12), nullable=False, index=True)
    kind = db.Column(db.String(16), nullable=False)      # earnings | move
    title = db.Column(db.String(200), nullable=False)


class AnalystRating(db.Model):
    __tablename__ = 'analyst_ratings'
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                              nullable=False, index=True)
    firm = db.Column(db.String(80), nullable=False)
    rating = db.Column(db.String(20), nullable=False)
    price_target = db.Column(db.Float)
    rated_on = db.Column(db.String(12))


class EtfHolding(db.Model):
    __tablename__ = 'etf_holdings'
    id = db.Column(db.Integer, primary_key=True)
    etf_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                       nullable=False, index=True)
    holding_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                           nullable=False)
    weight_pct = db.Column(db.Float, nullable=False)

    etf = db.relationship('Instrument', foreign_keys=[etf_id])
    holding = db.relationship('Instrument', foreign_keys=[holding_id])


class InstitutionalHolder(db.Model):
    """A fund or manager on a stock's Holdings tab."""
    __tablename__ = 'institutional_holders'
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                              nullable=False, index=True)
    firm = db.Column(db.String(80), nullable=False)
    pct_held = db.Column(db.Float, nullable=False)
    shares = db.Column(db.BigInteger)
    value = db.Column(db.Float)
    change_pct = db.Column(db.Float)


class Publisher(db.Model):
    __tablename__ = 'publishers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    domain = db.Column(db.String(120), unique=True, nullable=False)
    favicon_file = db.Column(db.String(160), default='')

    @property
    def favicon_url(self):
        if self.favicon_file:
            return url_for('static', filename=f'images/{self.favicon_file}')
        return None


class NewsArticle(db.Model):
    __tablename__ = 'news_articles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    headline = db.Column(db.String(300), nullable=False)
    publisher_id = db.Column(db.Integer, db.ForeignKey('publishers.id'))
    published_at = db.Column(db.DateTime, nullable=False, index=True)
    summary = db.Column(db.Text, default='')
    body = db.Column(db.Text, default='')
    scope = db.Column(db.String(16), default='company', index=True)  # market|company
    region = db.Column(db.String(16), default='us', index=True)

    publisher = db.relationship('Publisher')
    links = db.relationship('NewsLink', backref='article', lazy=True,
                            cascade='all, delete-orphan')

    def ago(self):
        return humanize_ago(self.published_at)


class NewsLink(db.Model):
    __tablename__ = 'news_links'
    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey('news_articles.id'),
                        nullable=False, index=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                              nullable=False, index=True)
    instrument = db.relationship('Instrument')


class MarketSummary(db.Model):
    __tablename__ = 'market_summaries'
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(16), nullable=False, index=True)
    headline = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=False)
    sources_count = db.Column(db.Integer, default=3)
    rank = db.Column(db.Integer, default=0)


class Watchlist(db.Model):
    __tablename__ = 'watchlists'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False,
                        index=True)
    name = db.Column(db.String(80), nullable=False)
    items = db.relationship('WatchlistItem', backref='watchlist', lazy=True,
                            cascade='all, delete-orphan')


class WatchlistItem(db.Model):
    __tablename__ = 'watchlist_items'
    id = db.Column(db.Integer, primary_key=True)
    watchlist_id = db.Column(db.Integer, db.ForeignKey('watchlists.id'),
                             nullable=False, index=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                              nullable=False)
    instrument = db.relationship('Instrument')


class Portfolio(db.Model):
    __tablename__ = 'portfolios'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False,
                        index=True)
    name = db.Column(db.String(80), nullable=False)
    cash = db.Column(db.Float, default=0.0)
    lots = db.relationship('PortfolioLot', backref='portfolio', lazy=True,
                           cascade='all, delete-orphan')

    def market_value(self):
        return sum(l.market_value() for l in self.lots) + (self.cash or 0.0)

    def cost_basis_total(self):
        return sum(l.shares * l.cost_basis for l in self.lots)

    def gain(self):
        return sum(l.gain() for l in self.lots)

    def gain_pct(self):
        cb = self.cost_basis_total()
        return (self.gain() / cb * 100) if cb else 0.0

    def day_change(self):
        return sum(l.day_change() for l in self.lots)


class PortfolioLot(db.Model):
    __tablename__ = 'portfolio_lots'
    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'),
                             nullable=False, index=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'),
                              nullable=False)
    shares = db.Column(db.Float, nullable=False)
    cost_basis = db.Column(db.Float, nullable=False)
    purchased_on = db.Column(db.String(12), default='')
    instrument = db.relationship('Instrument')

    def market_value(self):
        q = self.instrument.quote
        return self.shares * (q.price if q else 0.0)

    def gain(self):
        return self.market_value() - self.shares * self.cost_basis

    def gain_pct(self):
        base = self.shares * self.cost_basis
        return (self.gain() / base * 100) if base else 0.0

    def day_change(self):
        q = self.instrument.quote
        return self.shares * (q.change if q else 0.0)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

class RegisterForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=120)])
    username = StringField('Username',
                           validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password',
                             validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField('Confirm password',
                            validators=[DataRequired(), EqualTo('password')])


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


# ---------------------------------------------------------------------------
# Frozen-clock helpers
# ---------------------------------------------------------------------------

NOW = datetime.combine(MD.MARKET_DATE, datetime.min.time()) + timedelta(hours=20)


def humanize_ago(dt):
    """"3 hours ago" relative to the frozen market clock, never wall time."""
    mins = int((NOW - dt).total_seconds() // 60)
    if mins < 1:
        return 'just now'
    if mins < 60:
        return f'{mins} min. ago'
    hours = mins // 60
    if hours < 24:
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    days = hours // 24
    if days < 30:
        return f'{days} day{"s" if days != 1 else ""} ago'
    months = days // 30
    return f'{months} month{"s" if months != 1 else ""} ago'


# ---------------------------------------------------------------------------
# Series slicing — every range derives from one stored daily series
# ---------------------------------------------------------------------------

def series_for(inst, range_key):
    """Everything the chart needs for one range, as a single dict.

    Keys: labels, values, volumes, after (post-close leg), after_labels,
    baseline (previous close, only where Google draws the dashed line),
    and `dates` for the hover read-out.
    """
    h = inst.history
    empty = {'labels': [], 'values': [], 'volumes': [], 'after': [],
             'after_labels': [], 'baseline': None, 'dates': []}
    if not h:
        return empty

    has_volume = inst.kind in ('stock', 'etf', 'crypto')
    if range_key == '1D':
        vals = h.intraday()
        after = h.after() if inst.kind in ('stock', 'etf') else []
        stamp = MD.MARKET_DATE.strftime('%b %-d')
        # Axis ticks sit on round clock hours, not on evenly spaced sample
        # indices, so the labels read 12:00 PM / 3:00 PM the way Google's do.
        open_m, close_m, end_m = 9 * 60 + 30, 16 * 60, 20 * 60
        def minute_of(i):
            if i < len(vals):
                return open_m + (close_m - open_m) * i / max(1, len(vals) - 1)
            j = i - len(vals)
            return close_m + (end_m - close_m) * j / max(1, len(after) - 1)
        total = len(vals) + len(after)
        targets = [720, 900, 1080] if after else [660, 780, 900]
        tick_idx = [min(range(total), key=lambda i: abs(minute_of(i) - t))
                    for t in targets]
        return {
            'labels': MD.session_times(len(vals)),
            'values': vals,
            'volumes': h.intraday_volumes() if has_volume else [],
            'after': after,
            'after_labels': MD.after_hours_times(len(after)),
            'baseline': inst.quote.prev_close if inst.quote else None,
            'dates': [stamp] * total,
            'iso': [MD.MARKET_DATE.isoformat()] * total,
            'tick_idx': tick_idx,
        }

    closes, dailies = h.closes(), h.volumes()
    if range_key == '5D':
        vals = h.intraday5d()
        days = MD.CALENDAR[-5:]
        per = max(1, len(vals) // len(days))
        idx = [min(len(days) - 1, i // per) for i in range(len(vals))]
        # spread each session's volume across that session's points
        vols = ([dailies[-5 + k] // per for k in idx]
                if has_volume else [])
        # one tick per session, placed at that day's first sample
        tick_idx = [idx.index(d) for d in range(len(days)) if d in idx]
        return {'labels': [days[k].strftime('%b %-d') for k in idx],
                'values': vals, 'volumes': vols, 'after': [],
                'after_labels': [], 'baseline': closes[-6],
                'dates': [days[k].strftime('%b %-d, %Y') for k in idx],
                'iso': [days[k].isoformat() for k in idx],
                'tick_idx': tick_idx}

    n = MD.RANGE_SESSIONS.get(range_key)
    if range_key == 'YTD':
        n = MD.ytd_sessions()
    n = min(n or len(closes), len(closes))
    vals, vols, dates = closes[-n:], dailies[-n:], MD.CALENDAR[-n:]
    step = max(1, len(vals) // 260)           # keep charts readable
    vals, vols, dates = vals[::step], vols[::step], dates[::step]

    # Ticks land on the first sample of a month (or of a year on MAX), the way
    # Google labels its long ranges — evenly spaced indices give arbitrary
    # dates like "Mar 13".
    span_days = (dates[-1] - dates[0]).days
    if span_days > 1500:
        fmt, key = '%Y', lambda d: d.year
    elif span_days > 400:
        fmt, key = '%b %Y', lambda d: (d.year, (d.month - 1) // 3)
    elif span_days > 70:
        fmt, key = '%b %Y', lambda d: (d.year, d.month)
    else:
        # a one-month window spans at most two months, so label whole weeks
        fmt, key = '%b %-d', lambda d: d.isocalendar()[:2]
    firsts, seen = [], set()
    for i, d in enumerate(dates):
        k = key(d)
        if k not in seen:
            seen.add(k)
            firsts.append(i)
    if len(firsts) > 7:                       # thin out to ~6 labels
        every = max(1, round(len(firsts) / 6))
        firsts = firsts[::every]
    tick_idx = [i for i in firsts if i > 2]

    return {'labels': [d.strftime(fmt) for d in dates], 'values': vals,
            'volumes': vols if has_volume else [],
            'after': [], 'after_labels': [], 'baseline': None,
            'dates': [d.strftime('%b %-d, %Y') for d in dates],
            'iso': [d.isoformat() for d in dates], 'tick_idx': tick_idx}


MA_WINDOWS = {50: '#1a73e8', 200: '#e37400'}


def moving_averages(inst, ser, windows):
    """SMA overlays for the Indicators menu.

    Averaged over the untruncated daily closes, not the plotted (possibly
    downsampled) points, so a 200-day line really is a 200-day mean.
    """
    if not windows or not inst.history:
        return []
    closes = inst.history.closes()
    n = len(ser['values'])
    if n < 5 or len(closes) < max(windows) + n:
        return []
    step = max(1, (MD.RANGE_SESSIONS.get('MAX') or 1) and 1)
    out = []
    for w in sorted(windows):
        if w not in MA_WINDOWS:
            continue
        tail = closes[-(n * step):]
        series = []
        for k in range(n):
            end = len(closes) - n * step + k * step + 1
            window = closes[max(0, end - w):end]
            series.append(round(sum(window) / len(window), 4) if window else None)
        out.append({'label': f'{w}-day SMA', 'colour': MA_WINDOWS[w],
                    'values': series})
    return out


def moments_for(inst, ser):
    """Key moments that fall inside the plotted window, as chart indices."""
    iso = ser.get('iso') or []
    if not iso or len(set(iso)) < 2:      # 1D/5D windows are a single session
        return []
    rows = (KeyMoment.query.filter_by(instrument_id=inst.id)
            .filter(KeyMoment.moment_date >= iso[0],
                    KeyMoment.moment_date <= iso[-1])
            .order_by(KeyMoment.moment_date).all())
    out, used = [], set()
    for m in rows:
        # nearest plotted sample at or after the moment's date
        i = next((k for k, d in enumerate(iso) if d >= m.moment_date), None)
        if i is None or i in used:
            continue
        used.add(i)
        out.append({'i': i, 'title': m.title, 'kind': m.kind,
                    'date': m.moment_date})
    return out


def ranges_with_moments(inst):
    """Which range tabs get the orange dot, matching the live tab strip."""
    if inst.kind not in ('stock', 'etf'):
        return set()
    rows = [m.moment_date for m in
            KeyMoment.query.filter_by(instrument_id=inst.id).all()]
    if not rows:
        return set()
    out = set()
    for key in MD.RANGE_KEYS:
        n = MD.RANGE_SESSIONS.get(key)
        if key == 'YTD':
            n = MD.ytd_sessions()
        if not n:
            continue
        start = MD.CALENDAR[-min(n, len(MD.CALENDAR))].isoformat()
        if any(d >= start for d in rows):
            out.add(key)
    return out


RANGE_WORDS = {'1D': 'Today', '5D': '5 days', '1M': '1 month', '6M': '6 months',
               'YTD': 'Year to date', '1Y': '1 year', '5Y': '5 years',
               'MAX': 'Max'}


def range_move(inst, ser, range_key):
    """(abs change, pct change, label) across the selected range.

    Google's price header tracks the chart, not the session: switching to 1Y
    turns "+2.68% (+7.86) Today" into "+19.22% (+33.34) 1 year".
    """
    vals = ser['values']
    if len(vals) < 2:
        return None, None, RANGE_WORDS.get(range_key, range_key)
    base = ser.get('baseline') or vals[0]
    last = (ser['after'] or vals)[-1] if range_key == '1D' else vals[-1]
    if range_key == '1D' and inst.quote:
        base, last = inst.quote.prev_close, inst.quote.price
    if not base:
        return None, None, RANGE_WORDS.get(range_key, range_key)
    return (round(last - base, 4), round((last - base) / base * 100, 2),
            RANGE_WORDS.get(range_key, range_key))


def range_change(inst, range_key):
    """Percent change across the selected range."""
    ser = series_for(inst, range_key)
    return range_move(inst, ser, range_key)[1]


def sparkline(inst, n=40):
    """A short close series for list rows and cards."""
    h = inst.history
    if not h:
        return []
    vals = h.intraday()
    step = max(1, len(vals) // n)
    return vals[::step]


# ---------------------------------------------------------------------------
# Charts — rendered server-side as inline SVG
#
# Google Finance draws its charts client-side, but a browser-driving agent
# only ever sees the rendered result. Emitting the SVG from the server keeps
# the page deterministic (no animation or fetch timing to race), keeps the
# image self-contained, and means screenshots of the same URL are identical
# every run — which the reset invariant and the reviewer both depend on.
# ---------------------------------------------------------------------------

UP = '#137333'
DOWN = '#a50e0e'


def nice_ticks(lo, hi, target=6):
    """Round axis values, the way Google labels its price axis.

    Slicing the range into equal fractions gives ticks like 213.70 / 211.62;
    real charts step by 1, 2, 2.5 or 5 times a power of ten so the labels read
    as round numbers.
    """
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / max(1, target)
    mag = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= mult * mag:
            step = mult * mag
            break
    else:
        step = 10 * mag
    first = math.ceil(lo / step) * step
    out, v = [], first
    while v <= hi + step * 1e-9:
        out.append(round(v, 10))
        v += step
    return out


def pv(inst, value):
    """Format a price the way Google Finance does for this instrument kind."""
    if value is None:
        return '—'
    if inst.kind == 'currency':
        return f'{value:,.4f}'
    if inst.kind in ('index', 'sector'):
        return f'{value:,.2f}'
    return MD.fmt_price(value)


def _path_points(values, w, h, pad_top=8, pad_bottom=8):
    lo, hi = min(values), max(values)
    span = (hi - lo) or (abs(hi) * 0.01 or 1.0)
    inner = h - pad_top - pad_bottom
    n = len(values)
    return [(round(i * w / max(1, n - 1), 2),
             round(pad_top + inner - (v - lo) / span * inner, 2))
            for i, v in enumerate(values)], lo, hi


def spark_svg(inst, w=72, h=26, area=False):
    """A card sparkline. In `area` mode it also draws the dotted previous-close
    line the live index cards carry, so the fill reads as gain vs. loss rather
    than as an arbitrary shape."""
    vals = sparkline(inst, 48)
    if len(vals) < 2:
        return Markup('')
    q = inst.quote
    up = bool(q and q.change_pct >= 0)
    trend = 'up' if up else 'down'
    pad = 3 if not area else 0

    prev = q.prev_close if (area and q and q.prev_close) else None
    lo, hi = min(vals), max(vals)
    if prev:
        lo, hi = min(lo, prev), max(hi, prev)
    span = (hi - lo) or (abs(hi) * 0.01 or 1.0)
    inner = h - pad * 2

    def yv(v):
        return round(pad + inner - (v - lo) / span * inner, 2)

    n = len(vals)
    pts = [(round(i * w / (n - 1), 2), yv(v)) for i, v in enumerate(vals)]
    d = 'M' + ' L'.join(f'{x},{y}' for x, y in pts)

    body = ''
    if area:
        body = (f'<path d="{d} L{pts[-1][0]},{h} L{pts[0][0]},{h} Z" '
                f'class="spark-fill {trend}" stroke="none"/>')
        if prev:
            by = yv(prev)
            body += (f'<line class="spark-base" x1="0" y1="{by}" x2="{w}" '
                     f'y2="{by}"/>')
    return Markup(
        f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'preserveAspectRatio="none" aria-hidden="true">{body}'
        f'<path d="{d}" fill="none" class="spark-line {trend}" '
        f'stroke-width="{1.4 if not area else 1.6}" '
        f'vector-effect="non-scaling-stroke"/></svg>')


def chart_svg(inst, ser, colour_up=True, chart_type='area',
              overlays=None):
    """The main price chart, drawn to match Google Finance's own layout.

    Rendered server-side so the shape of the page is deterministic: same URL,
    same bytes, no fetch or animation timing for a screenshot to race. The
    hover crosshair is layered on top by finance.js from the same data, which
    adds interaction without changing what the page reports.
    """
    values, after = ser['values'], ser['after']
    if len(values) < 2:
        return Markup('<div class="chart-empty">No price history available.</div>')

    W, H = 1000, 280
    PAD_L, PAD_R, AXIS_H = 58, 16, 24
    PLOT_TOP, PLOT_BOT = 10, H - AXIS_H
    VOL_H = 46 if (ser.get('volumes')) else 0   # volume band along the bottom
    PRICE_BOT = PLOT_BOT - VOL_H - (4 if VOL_H else 0)
    plot_w = W - PAD_L - PAD_R

    baseline = ser.get('baseline')
    combined = values + after
    n = len(combined)
    scale_src = combined + ([baseline] if baseline else [])
    lo, hi = min(scale_src), max(scale_src)
    span = (hi - lo) or (abs(hi) * 0.01 or 1.0)
    lo -= span * 0.10
    hi += span * 0.10
    span = hi - lo

    def px(i):
        return round(PAD_L + i * plot_w / max(1, n - 1), 2)

    def py(v):
        return round(PRICE_BOT - (v - lo) / span * (PRICE_BOT - PLOT_TOP), 2)

    trend = 'up' if colour_up else 'down'

    # --- volume bars, drawn first so the price line sits above them --------
    vols = ser.get('volumes') or []
    bars = []
    if vols:
        vmax = max(vols) or 1
        bw = max(1.0, plot_w / max(1, n) * 0.62)
        prev = values[0]
        for i, v in enumerate(vols[:len(values)]):
            rising = values[i] >= prev
            prev = values[i]
            h = max(1.0, v / vmax * VOL_H)
            bars.append(f'<rect x="{px(i) - bw/2:.2f}" y="{PLOT_BOT - h:.2f}" '
                        f'width="{bw:.2f}" height="{h:.2f}" '
                        f'class="vol {"vu" if rising else "vd"}"/>')

    # --- gridlines: horizontal with left-hand price labels, vertical ticks --
    grid, ylabels = [], []
    base_y = py(baseline) if baseline else None
    ticks_v = nice_ticks(lo + span * 0.06, hi - span * 0.06)
    # Google drops the decimals when every tick is a whole number, so an index
    # axis reads 7,460 / 7,440 rather than 7,460.00 / 7,440.00.
    digits = MD.digits_for(inst.kind, values[-1])
    if all(abs(v - round(v)) < 1e-9 for v in ticks_v):
        digits = 0
    for v in ticks_v:
        y = py(v)
        grid.append(f'<line class="grid" x1="{PAD_L}" y1="{y}" '
                    f'x2="{W - PAD_R}" y2="{y}"/>')
        ylabels.append(f'<text class="ytick" x="{PAD_L - 10}" y="{y + 4}" '
                       f'text-anchor="end">{v:,.{digits}f}</text>')

    labels = ser['labels'] + ser.get('after_labels', [])
    tick_idx = ser.get('tick_idx') or [min(n - 1, int((k + 0.5) * n / 4))
                                       for k in range(4)]
    ticks, xlabels = [], []
    for i in tick_idx:
        if not 0 <= i < n:
            continue
        x = px(i)
        ticks.append(f'<line class="vgrid" x1="{x}" y1="{PLOT_TOP}" '
                     f'x2="{x}" y2="{PLOT_BOT}"/>')
        xlabels.append(f'<text class="xtick" x="{x}" y="{H - 7}" '
                       f'text-anchor="middle">{labels[i]}</text>')

    # --- regular-session path ---------------------------------------------
    pts = [(px(i), py(v)) for i, v in enumerate(values)]
    line = 'M' + ' L'.join(f'{x},{y}' for x, y in pts)
    paths = []
    if chart_type == 'area':
        area = f'{line} L{pts[-1][0]},{PLOT_BOT} L{pts[0][0]},{PLOT_BOT} Z'
        paths.append(f'<path d="{area}" fill="url(#gf-fill-{trend})" '
                     f'stroke="none"/>')
    paths += bars                      # volume sits on top of the fill
    paths.append(f'<path d="{line}" fill="none" class="series-line {trend}"/>')

    for ov in (overlays or []):
        seg, started = [], False
        for i, v in enumerate(ov['values']):
            if v is None:
                started = False
                continue
            seg.append(("M" if not started else "L") + f'{px(i)},{py(v)}')
            started = True
        if seg:
            paths.append(f'<path d="{" ".join(seg)}" fill="none" '
                         f'stroke="{ov["colour"]}" stroke-width="1.4" '
                         f'stroke-dasharray="5 3" class="ma-line"/>')

    # --- after-hours leg, grey, behind a session divider -------------------
    if after:
        j = len(values) - 1
        apts = [(px(j), py(values[-1]))] + \
               [(px(len(values) + i), py(v)) for i, v in enumerate(after)]
        aline = 'M' + ' L'.join(f'{x},{y}' for x, y in apts)
        paths.append(f'<line class="session-split" x1="{px(j)}" y1="{PLOT_TOP}" '
                     f'x2="{px(j)}" y2="{PLOT_BOT}"/>')
        paths.append(f'<path d="{aline}" fill="none" class="after-line"/>')
        dot = apts[-1]
    else:
        dot = pts[-1]

    base_el = ''
    if baseline:
        base_el = (f'<line class="baseline" x1="{PAD_L}" y1="{base_y}" '
                   f'x2="{W - PAD_R}" y2="{base_y}"/>'
                   f'<text class="ytick prev" x="{W - PAD_R - 6}" '
                   f'y="{base_y - 8}" text-anchor="end">'
                   f'Prev close {pv(inst, baseline)}</text>')

    end_dot = (f'<circle cx="{dot[0]}" cy="{dot[1]}" r="4" '
               f'class="end-dot {"after" if after else trend}"/>')

    # key moments: an amber halo with a dot, as Google marks earnings and
    # outsized sessions on the 6M-and-longer charts
    moments = ser.get('moments') or []
    halos = []
    for m in moments:
        i = m['i']
        if not 0 <= i < len(values):
            continue
        mx, my = px(i), py(values[i])
        halos.append(
            f'<g class="moment"><circle class="moment-halo" cx="{mx}" '
            f'cy="{my}" r="17"/><circle class="moment-dot" cx="{mx}" '
            f'cy="{my}" r="3.5"/><title>{m["date"]} — {m["title"]}</title></g>')

    payload = json.dumps({
        'labels': labels,
        'dates': ser.get('dates') or labels,
        'values': [round(v, 6) for v in combined],
        'volumes': [int(v) for v in vols] if vols else [],
        'split': len(values) if after else None,
        'baseline': baseline,
        'padL': PAD_L, 'padR': PAD_R, 'width': W,
        'moments': [{'i': m['i'], 'title': m['title']} for m in moments],
        'digits': MD.digits_for(inst.kind, values[-1]),
        'prefix': '' if inst.kind in ('index', 'sector', 'currency') else '$',
    }, separators=(',', ':'))

    return Markup(
        f'<div class="chart-host" data-series=\'{payload}\'>'
        f'<svg class="price-chart" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Price chart for {inst.name}">'
        # The fill fades out downwards, as on the live chart. Stop colours are
        # set in CSS so the theme and the up/down convention can swap them.
        '<defs>'
        '<linearGradient id="gf-fill-up" x1="0" y1="0" x2="0" y2="1">'
        '<stop class="g0 up" offset="0%"/><stop class="g1 up" offset="100%"/>'
        '</linearGradient>'
        '<linearGradient id="gf-fill-down" x1="0" y1="0" x2="0" y2="1">'
        '<stop class="g0 down" offset="0%"/><stop class="g1 down" offset="100%"/>'
        '</linearGradient>'
        '</defs>'
        + ''.join(grid) + ''.join(ticks) + ''.join(paths)
        + base_el + ''.join(halos) + end_dot + ''.join(ylabels)
        + ''.join(xlabels)
        + '<g class="crosshair" hidden>'
          '<line class="cross-line" x1="0" y1="10" x2="0" y2="256"/>'
          '<circle class="cross-dot" r="4.5"/></g>'
        + '</svg>'
        f'<div class="chart-readout" hidden></div>'
        f'<div class="chart-stamp" hidden></div>'
        '</div>')


def bar_chart_svg(labels, series, w=740, h=210):
    """Grouped bar chart for the Financials tab (revenue vs net income)."""
    flat = [v for _, vals, _ in series for v in vals]
    if not flat:
        return Markup('')
    hi = max(max(flat), 0)
    lo = min(min(flat), 0)
    span = (hi - lo) or 1
    pad_b, pad_r = 24, 58
    plot_h, plot_w = h - pad_b, w - pad_r
    groups = len(labels)
    gw = plot_w / max(1, groups)
    bw = gw / (len(series) + 1.6)
    zero_y = plot_h - (0 - lo) / span * (plot_h - 12) - 6

    bars, legend = [], []
    for si, (name, vals, colour) in enumerate(series):
        legend.append(f'<span class="lg"><i style="background:{colour}"></i>'
                      f'{name}</span>')
        for gi, v in enumerate(vals):
            y = plot_h - (v - lo) / span * (plot_h - 12) - 6
            top, height = min(y, zero_y), abs(zero_y - y)
            x = gi * gw + gw / 2 - (len(series) * bw) / 2 + si * bw
            bars.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw*0.86:.1f}" '
                        f'height="{max(1, height):.1f}" fill="{colour}" rx="2"/>')
    xs = [f'<text class="xtick" x="{gi*gw+gw/2:.1f}" y="{h-6}" '
          f'text-anchor="middle">{lab}</text>' for gi, lab in enumerate(labels)]
    ys = []
    for k in range(4):
        v = lo + span * (k + 1) / 5
        y = plot_h - (v - lo) / span * (plot_h - 12) - 6
        ys.append(f'<line class="grid" x1="0" y1="{y:.1f}" x2="{plot_w}" '
                  f'y2="{y:.1f}"/><text class="ytick" x="{plot_w+8}" '
                  f'y="{y+4:.1f}">{MD.fmt_big(v)}</text>')
    return Markup(
        f'<div class="bar-legend">{"".join(legend)}</div>'
        f'<svg class="bar-chart" viewBox="0 0 {w} {h}" width="100%" '
        f'height="{h}" role="img" aria-label="Financial history">'
        + ''.join(ys) + ''.join(bars) + ''.join(xs) + '</svg>')


# ---------------------------------------------------------------------------
# Search — scored token overlap, never strict AND
# ---------------------------------------------------------------------------

def _tokens(q):
    return [t.lower() for t in re.findall(r'[a-z0-9.\-=]+', q.lower())
            if t not in STOPWORDS and len(t) >= 1]


# Everyday words that map onto a GICS sector or an industry label. Without
# these, a plain-language query like "bank" only matches the one company with
# "Bank" in its registered name, which reads as a broken search.
SEARCH_ALIASES = {
    'bank': 'Financials', 'banks': 'Financials', 'banking': 'Financials',
    'finance': 'Financials', 'financial': 'Financials',
    'insurer': 'Financials', 'payments': 'Financials',
    'chip': 'Technology', 'chips': 'Technology',
    'semiconductor': 'Technology', 'semiconductors': 'Technology',
    'software': 'Technology', 'tech': 'Technology', 'cloud': 'Technology',
    'hardware': 'Technology', 'ai': 'Technology',
    'oil': 'Energy', 'gas': 'Energy', 'crude': 'Energy', 'drilling': 'Energy',
    'refiner': 'Energy', 'refining': 'Energy',
    'pharma': 'Health Care', 'pharmaceutical': 'Health Care',
    'biotech': 'Health Care', 'medical': 'Health Care',
    'hospital': 'Health Care', 'healthcare': 'Health Care',
    'retail': 'Consumer Discretionary', 'retailer': 'Consumer Discretionary',
    'automaker': 'Consumer Discretionary', 'carmaker': 'Consumer Discretionary',
    'travel': 'Consumer Discretionary', 'restaurant': 'Consumer Discretionary',
    'beverage': 'Consumer Staples', 'grocery': 'Consumer Staples',
    'household': 'Consumer Staples', 'tobacco': 'Consumer Staples',
    'airline': 'Industrials', 'aerospace': 'Industrials',
    'defense': 'Industrials', 'railroad': 'Industrials',
    'machinery': 'Industrials', 'logistics': 'Industrials',
    'utility': 'Utilities', 'utilities': 'Utilities', 'power': 'Utilities',
    'electric': 'Utilities',
    'reit': 'Real Estate', 'property': 'Real Estate',
    'realestate': 'Real Estate',
    'chemical': 'Materials', 'chemicals': 'Materials', 'mining': 'Materials',
    'miner': 'Materials', 'metals': 'Materials',
    'media': 'Communication Services', 'telecom': 'Communication Services',
    'streaming': 'Communication Services', 'social': 'Communication Services',
    'etf': 'ETF', 'fund': 'ETF', 'index': 'index', 'crypto': 'crypto',
    'currency': 'currency', 'forex': 'currency', 'futures': 'future',
}


def _score_instrument(inst, tokens):
    ticker = inst.ticker.lower()
    name = inst.name.lower()
    sector = (inst.sector or '').lower()
    hay = ' '.join([ticker, name, sector, (inst.industry or '').lower(),
                    (inst.kind or '').lower(), (inst.profile or '')[:600].lower()])
    score = 0
    for t in tokens:
        alias = SEARCH_ALIASES.get(t, '').lower()
        if ticker == t:
            score += 12
        elif ticker.startswith(t):
            score += 6
        elif name.startswith(t):
            score += 5
        elif t in name:
            score += 3
        elif alias and (alias == sector or alias == (inst.kind or '').lower()
                        or alias in (inst.industry or '').lower()):
            score += 2
        elif t in hay:
            score += 1
    return score


def search_instruments(q, limit=40):
    tokens = _tokens(q)
    if not tokens:
        return []
    scored = [(s, i) for i in Instrument.query.all()
              if (s := _score_instrument(i, tokens)) > 0]
    scored.sort(key=lambda x: (-x[0], x[1].ticker))
    return [i for _, i in scored[:limit]]


def search_news(q, limit=12):
    tokens = _tokens(q)
    if not tokens:
        return []
    clauses = [NewsArticle.headline.ilike(f'%{t}%') for t in tokens]
    clauses += [NewsArticle.summary.ilike(f'%{t}%') for t in tokens]
    return (NewsArticle.query.filter(or_(*clauses))
            .order_by(NewsArticle.published_at.desc()).limit(limit).all())


# ---------------------------------------------------------------------------
# Shared view data
# ---------------------------------------------------------------------------

def sector_index_rows():
    return (Instrument.query.filter_by(kind='sector')
            .order_by(Instrument.ticker).all())


def user_watchlists():
    if not current_user.is_authenticated:
        return []
    return (Watchlist.query.filter_by(user_id=current_user.id)
            .order_by(Watchlist.id).all())


def user_portfolios():
    if not current_user.is_authenticated:
        return []
    return (Portfolio.query.filter_by(user_id=current_user.id)
            .order_by(Portfolio.id).all())


# ---------------------------------------------------------------------------
# Routes — market pages
# ---------------------------------------------------------------------------

REGION_INDEX_TICKERS = {
    'us': ['.DJI', '.INX', '.IXIC', 'RUT', 'VIX'],
    'europe': ['DAX', 'UKX', 'PX1', 'I', 'SX5E'],
    'asia': ['NI225', '000001', 'HSI', 'SENSEX', 'NIFTY_50'],
}


def region_cards(region):
    if region in REGION_INDEX_TICKERS:
        tickers = REGION_INDEX_TICKERS[region]
        rows = Instrument.query.filter(Instrument.ticker.in_(tickers)).all()
        order = {t: i for i, t in enumerate(tickers)}
        return sorted(rows, key=lambda i: order.get(i.ticker, 99))
    if region == 'currencies':
        return (Instrument.query.filter_by(kind='currency')
                .order_by(Instrument.id).limit(6).all())
    if region == 'crypto':
        return (Instrument.query.filter_by(kind='crypto').join(Quote)
                .order_by(Quote.mkt_cap.desc()).limit(6).all())
    if region == 'futures':
        return (Instrument.query.filter_by(kind='future')
                .order_by(Instrument.id).limit(6).all())
    if region == 'latam':
        return (Instrument.query.filter_by(region='latam')
                .order_by(Instrument.id).limit(6).all())
    return []


def movers_query(kind, limit=25):
    base = Instrument.query.filter(Instrument.kind.in_(['stock', 'etf'])).join(Quote)
    if kind == 'gainers':
        return base.order_by(Quote.change_pct.desc()).limit(limit).all()
    if kind == 'losers':
        return base.order_by(Quote.change_pct.asc()).limit(limit).all()
    if kind == 'most-active':
        return base.order_by(Quote.volume.desc()).limit(limit).all()
    return []


@app.context_processor
def inject_globals():
    return {
        'market_date': MD.MARKET_DATE,
        'market_close_label': MD.MARKET_CLOSE_LABEL,
        'after_hours_label': MD.AFTER_HOURS_LABEL,
        'current_year': MD.MARKET_YEAR,
        'regions': REGIONS,
        'market_pages': MARKET_PAGES,
        'sector_indexes': sector_index_rows(),
        'nav_watchlists': user_watchlists(),
        'nav_portfolios': user_portfolios(),
        'rail_gainers': movers_query('gainers', 4),
        'rail_losers': movers_query('losers', 4),
        'rail_news': (NewsArticle.query.filter_by(scope='market')
                      .order_by(NewsArticle.published_at.desc()).limit(5).all()),
        'fmt_big': MD.fmt_big,
        'fmt_price': MD.fmt_price,
        'fmt_pct': MD.fmt_pct,
        'fmt_money_signed': MD.fmt_money_signed,
        'sparkline': sparkline,
        'pv': pv,
        'spark_svg': spark_svg,
        'chart_svg': chart_svg,
        'bar_chart_svg': bar_chart_svg,
        'range_keys': MD.RANGE_KEYS,
        'theme': current_theme(),
        'colors': current_colors(),
        'themes': THEMES,
        'color_modes': COLOR_MODES,
        'here': request.full_path.rstrip('?') or '/',
    }


@app.route('/')
def index():
    region = request.args.get('region', 'us')
    if region not in {r for r, _ in REGIONS}:
        region = 'us'
    summaries = (MarketSummary.query.filter_by(region=region)
                 .order_by(MarketSummary.rank).all())
    if not summaries:
        summaries = (MarketSummary.query.filter_by(region='us')
                     .order_by(MarketSummary.rank).all())
    # Google shows the favicons of the outlets a summary was drawn from, next
    # to the "N sites" count. Pick them deterministically per summary.
    pubs = Publisher.query.order_by(Publisher.id).all()
    sources = {}
    if pubs:
        for row in summaries:
            k = row.id * 7
            sources[row.id] = [pubs[(k + j) % len(pubs)]
                               for j in range(min(row.sources_count, 4))]
    updates = (NewsArticle.query.filter_by(scope='market')
               .order_by(NewsArticle.published_at.desc()).limit(14).all())
    movers = {'gainers': movers_query('gainers', 5),
              'losers': movers_query('losers', 5),
              'most-active': movers_query('most-active', 5)}
    return render_template('index.html', region=region,
                           cards=region_cards(region), summaries=summaries,
                           sources=sources, updates=updates, movers=movers)


@app.route('/markets/<slug>')
def markets(slug):
    titles = dict(MARKET_PAGES)
    if slug not in titles:
        abort(404)
    if slug in ('gainers', 'losers', 'most-active'):
        rows = movers_query(slug, 25)
    elif slug == 'indexes':
        rows = (Instrument.query.filter_by(kind='index')
                .order_by(Instrument.region, Instrument.id).all())
    elif slug == 'cryptocurrencies':
        rows = (Instrument.query.filter_by(kind='crypto').join(Quote)
                .order_by(Quote.mkt_cap.desc()).all())
    elif slug == 'currencies':
        rows = Instrument.query.filter_by(kind='currency').order_by(
            Instrument.id).all()
    elif slug == 'futures':
        rows = Instrument.query.filter_by(kind='future').order_by(
            Instrument.id).all()
    elif slug == 'climate-leaders':
        rows = (Instrument.query.filter_by(is_climate_leader=True)
                .order_by(Instrument.ticker).all())
    else:
        rows = []
    return render_template('markets.html', slug=slug, title=titles[slug],
                           rows=rows)


# ---------------------------------------------------------------------------
# Routes — quote
# ---------------------------------------------------------------------------

QUOTE_TABS = ['overview', 'analysis', 'earnings', 'financials', 'holdings']


def tabs_for(inst):
    if inst.kind == 'stock':
        # a stock's Holdings tab lists who owns it; an ETF's lists what it owns
        return ['overview', 'analysis', 'earnings', 'financials', 'holdings']
    if inst.kind == 'etf':
        return ['overview', 'holdings']
    return ['overview']


@app.route('/quote/<path:symbol>')
def quote(symbol):
    inst = Instrument.query.filter_by(slug=symbol).first()
    if not inst:
        inst = Instrument.query.filter(
            func.upper(Instrument.ticker) == symbol.split(':')[0].upper()).first()
    if not inst:
        abort(404)

    available = tabs_for(inst)
    tab = request.args.get('tab', 'overview').lower()
    if tab not in available:
        tab = 'overview'
    rng = request.args.get('range', '1D').upper()
    if rng not in MD.RANGE_KEYS:
        rng = '1D'

    chart_type = request.args.get('chart', 'area').lower()
    if chart_type not in ('area', 'line'):
        chart_type = 'area'
    try:
        ma = sorted({int(x) for x in request.args.get('ma', '').split(',')
                     if x.strip().isdigit()} & set(MA_WINDOWS))
    except ValueError:
        ma = []

    ser = series_for(inst, rng)
    ser['moments'] = moments_for(inst, ser)
    overlays = moving_averages(inst, ser, ma)
    related = [Instrument.query.filter_by(slug=s).first()
               for s in inst.related_slugs]
    related = [r for r in related if r and r.id != inst.id][:6]
    news = (NewsArticle.query.join(NewsLink, NewsLink.news_id == NewsArticle.id)
            .filter(NewsLink.instrument_id == inst.id)
            .order_by(NewsArticle.published_at.desc()).limit(10).all())

    move_abs, move_pct, move_label = range_move(inst, ser, rng)
    ctx = dict(inst=inst, q=inst.quote, tab=tab, tabs=available, rng=rng,
               series=ser, related=related, news=news,
               move_abs=move_abs, move_pct=move_pct, move_label=move_label,
               range_pct=move_pct, moment_ranges=ranges_with_moments(inst),
               moment_count=len(ser['moments']), chart_type=chart_type,
               ma=ma, overlays=overlays, ma_windows=sorted(MA_WINDOWS))

    if tab == 'financials':
        stmt = request.args.get('statement', 'income').lower()
        if stmt not in ('income', 'balance', 'cashflow'):
            stmt = 'income'
        period = request.args.get('period', 'quarterly').lower()
        if period not in ('quarterly', 'annual'):
            period = 'quarterly'
        rows = (FinancialRow.query
                .filter_by(instrument_id=inst.id, statement=stmt,
                           period_type=period)
                .order_by(FinancialRow.ordinal).all())
        chart = None
        if stmt == 'income' and rows:
            tail = rows[-4:]
            items = [r.items() for r in tail]
            chart = {
                'labels': [r.period_label for r in tail],
                'series': [
                    ('Revenue', [i['revenue'] for i in items], '#4285f4'),
                    ('Net income', [i['net_income'] for i in items], '#174ea6'),
                ],
            }
        ctx.update(statement=stmt, period=period, fin_rows=rows,
                   fin_chart=chart)
    elif tab == 'earnings':
        ctx['earnings'] = (EarningsRow.query.filter_by(instrument_id=inst.id)
                           .order_by(EarningsRow.report_date.desc()).all())
    elif tab == 'analysis':
        ratings = (AnalystRating.query.filter_by(instrument_id=inst.id)
                   .order_by(AnalystRating.rated_on.desc()).all())
        ctx['ratings'] = ratings
        ctx['consensus'] = MD.rating_consensus(
            [{'rating': r.rating, 'price_target': r.price_target}
             for r in ratings]) if ratings else None
    elif tab == 'holdings':
        ctx['holdings'] = (EtfHolding.query.filter_by(etf_id=inst.id)
                           .order_by(EtfHolding.weight_pct.desc()).all())
        ctx['holders'] = (InstitutionalHolder.query
                          .filter_by(instrument_id=inst.id)
                          .order_by(InstitutionalHolder.pct_held.desc()).all())
        # funds in this mirror that hold the stock, from the ETF tables
        ctx['held_by'] = (EtfHolding.query.filter_by(holding_id=inst.id)
                          .order_by(EtfHolding.weight_pct.desc()).all())

    ctx['in_lists'] = [w.id for w in user_watchlists()
                       if any(i.instrument_id == inst.id for i in w.items)]
    return render_template('quote.html', **ctx)


# ---------------------------------------------------------------------------
# Routes — search, news, tools
# ---------------------------------------------------------------------------

@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    return render_template('search.html', q=q,
                           results=search_instruments(q) if q else [],
                           news=search_news(q) if q else [])


@app.route('/autocomplete')
@csrf.exempt
def autocomplete():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    return jsonify([
        {'ticker': i.ticker, 'name': i.name, 'slug': i.slug,
         'exchange': i.exchange, 'kind': i.kind,
         'price': i.quote.price if i.quote else None,
         'change_pct': i.quote.change_pct if i.quote else None}
        for i in search_instruments(q, limit=8)])


@app.route('/news')
def news_index():
    scope = request.args.get('scope', 'all')
    qry = NewsArticle.query
    if scope in ('market', 'company'):
        qry = qry.filter_by(scope=scope)
    return render_template(
        'news_index.html', scope=scope,
        articles=qry.order_by(NewsArticle.published_at.desc()).limit(60).all())


@app.route('/news/<slug>')
def news_detail(slug):
    a = NewsArticle.query.filter_by(slug=slug).first_or_404()
    related = (NewsArticle.query
               .filter(NewsArticle.id != a.id, NewsArticle.scope == a.scope)
               .order_by(NewsArticle.published_at.desc()).limit(6).all())
    return render_template('news_detail.html', a=a, related=related)


@app.route('/currency-converter')
def currency_converter():
    pairs = Instrument.query.filter_by(kind='currency').order_by(
        Instrument.id).all()
    codes = []
    for p in pairs:
        for c in p.ticker.split('-'):
            if c not in codes:
                codes.append(c)
    src = request.args.get('from', 'USD').upper()
    dst = request.args.get('to', 'EUR').upper()
    try:
        amount = float(request.args.get('amount', '1') or 1)
    except ValueError:
        amount = 1.0
    rate = result = err = None
    if src == dst:
        rate, result = 1.0, amount
    else:
        direct = Instrument.query.filter_by(kind='currency',
                                            ticker=f'{src}-{dst}').first()
        inverse = Instrument.query.filter_by(kind='currency',
                                             ticker=f'{dst}-{src}').first()
        if direct and direct.quote:
            rate = direct.quote.price
        elif inverse and inverse.quote and inverse.quote.price:
            rate = 1.0 / inverse.quote.price
        if rate:
            result = amount * rate
        else:
            err = f'No quoted rate for {src} to {dst}.'
    return render_template('converter.html', codes=codes, src=src, dst=dst,
                           amount=amount, rate=rate, result=result, err=err,
                           pairs=pairs)


@app.route('/compare')
def compare():
    raw = request.args.get('tickers', '')
    rows = []
    for t in [x.strip() for x in raw.split(',') if x.strip()][:5]:
        inst = (Instrument.query.filter_by(slug=t).first()
                or Instrument.query.filter(
                    func.upper(Instrument.ticker) == t.upper()).first())
        if inst:
            rows.append(inst)
    return render_template('compare.html', rows=rows, raw=raw)


# ---------------------------------------------------------------------------
# Routes — auth & account
# ---------------------------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash('That email is already registered.', 'error')
        elif User.query.filter_by(username=form.username.data).first():
            flash('That username is taken.', 'error')
        else:
            u = User(email=form.email.data.lower(),
                     username=form.username.data, name=form.name.data)
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.commit()
            db.session.add(Watchlist(user_id=u.id, name='My list'))
            db.session.commit()
            login_user(u)
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        ident = form.email.data.strip().lower()
        user = (User.query.filter_by(email=ident).first()
                or User.query.filter(func.lower(User.username) == ident).first())
        if user and user.check_password(form.password.data):
            login_user(user)
            # `next` arrives as a query arg from @login_required and as a
            # hidden field when the user came via "Use another account".
            return redirect(_safe_next(request.form.get('next')
                                       or request.args.get('next')))
        flash('Wrong email or password. Try again.', 'error')
    return render_template('login.html', form=form)


# Avatar colours Google uses for accounts without a profile photo.
AVATAR_COLOURS = ['#1a73e8', '#d93025', '#188038', '#e37400', '#9334e6',
                  '#12b5cb', '#c5221f', '#1e8e3e']


def avatar_for(user):
    """A stable colour + initial per account, the way the picker renders one."""
    return {'colour': AVATAR_COLOURS[user.id % len(AVATAR_COLOURS)],
            'initial': (user.name or user.email)[0].upper()}


def _safe_next(raw):
    """Only ever redirect back inside this site."""
    if raw and raw.startswith('/') and not raw.startswith('//'):
        return raw
    return url_for('index')


@app.route('/accounts/chooser')
def account_chooser():
    """The 'Choose an account' step, mirroring accounts.google.com.

    Two sign-in paths coexist on purpose. Typing an email and password
    exercises form filling; picking a profile card exercises the click-through
    path an agent meets on any site with a federated login. The picker asks
    for no credential at all — it only lists the accounts already seeded in
    this mirror's own database.
    """
    if current_user.is_authenticated:
        return redirect(_safe_next(request.args.get('next')))
    users = User.query.order_by(User.id).all()
    return render_template('account_chooser.html', users=users,
                           avatar_for=avatar_for,
                           next_url=_safe_next(request.args.get('next')))


@app.route('/accounts/choose', methods=['POST'])
def account_choose():
    email = (request.form.get('email') or '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('That account is not available on this device.', 'error')
        return redirect(url_for('account_chooser'))
    login_user(user)
    return redirect(_safe_next(request.form.get('next')))


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/account')
@login_required
def account():
    return render_template('account.html')


# ---------------------------------------------------------------------------
# Routes — watchlists
# ---------------------------------------------------------------------------

@app.route('/lists')
@login_required
def lists_index():
    return render_template('lists.html', lists=user_watchlists())


@app.route('/lists/<int:list_id>')
@login_required
def list_detail(list_id):
    wl = Watchlist.query.filter_by(id=list_id,
                                   user_id=current_user.id).first_or_404()
    return render_template('list_detail.html', wl=wl)


@app.route('/lists/new', methods=['GET'])
@login_required
def list_new_form():
    """Standalone create-list page, the destination of the rail's + button."""
    return render_template('list_new.html')


@app.route('/lists/new', methods=['POST'])
@login_required
def list_new():
    name = (request.form.get('name') or '').strip()
    if not name:
        flash('Enter a name for the list.', 'error')
        return redirect(request.referrer or url_for('lists_index'))
    if Watchlist.query.filter_by(user_id=current_user.id, name=name).first():
        flash(f'You already have a list named "{name}".', 'error')
        return redirect(request.referrer or url_for('lists_index'))
    wl = Watchlist(user_id=current_user.id, name=name)
    db.session.add(wl)
    db.session.commit()
    flash(f'Created list "{name}".', 'success')
    return redirect(url_for('list_detail', list_id=wl.id))


@app.route('/lists/<int:list_id>/add', methods=['POST'])
@login_required
def list_add(list_id):
    wl = Watchlist.query.filter_by(id=list_id,
                                   user_id=current_user.id).first_or_404()
    slug = (request.form.get('slug') or '').strip()
    inst = (Instrument.query.filter_by(slug=slug).first()
            or Instrument.query.filter(
                func.upper(Instrument.ticker) == slug.upper()).first())
    if not inst:
        flash(f'No instrument matches "{slug}".', 'error')
    elif WatchlistItem.query.filter_by(watchlist_id=wl.id,
                                       instrument_id=inst.id).first():
        flash(f'{inst.ticker} is already in "{wl.name}".', 'info')
    else:
        db.session.add(WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id))
        db.session.commit()
        flash(f'Added {inst.ticker} to "{wl.name}".', 'success')
    return redirect(request.referrer or url_for('list_detail', list_id=wl.id))


@app.route('/lists/<int:list_id>/toggle', methods=['POST'])
@login_required
def list_toggle(list_id):
    """Add or remove one symbol from the quote page's Add-to-list menu."""
    wl = Watchlist.query.filter_by(id=list_id,
                                   user_id=current_user.id).first_or_404()
    slug = (request.form.get('slug') or '').strip()
    inst = (Instrument.query.filter_by(slug=slug).first()
            or Instrument.query.filter(
                func.upper(Instrument.ticker) == slug.upper()).first())
    if not inst:
        flash(f'No instrument matches "{slug}".', 'error')
        return redirect(request.referrer or url_for('index'))
    item = WatchlistItem.query.filter_by(watchlist_id=wl.id,
                                         instrument_id=inst.id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash(f'Removed {inst.ticker} from "{wl.name}".', 'info')
    else:
        db.session.add(WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id))
        db.session.commit()
        flash(f'Added {inst.ticker} to "{wl.name}".', 'success')
    return redirect(request.referrer or url_for('quote', symbol=inst.slug))


@app.route('/lists/<int:list_id>/remove/<int:item_id>', methods=['POST'])
@login_required
def list_remove(list_id, item_id):
    wl = Watchlist.query.filter_by(id=list_id,
                                   user_id=current_user.id).first_or_404()
    item = WatchlistItem.query.filter_by(id=item_id,
                                         watchlist_id=wl.id).first_or_404()
    ticker = item.instrument.ticker
    db.session.delete(item)
    db.session.commit()
    flash(f'Removed {ticker} from "{wl.name}".', 'info')
    return redirect(request.referrer or url_for('list_detail', list_id=wl.id))


@app.route('/lists/<int:list_id>/delete', methods=['POST'])
@login_required
def list_delete(list_id):
    wl = Watchlist.query.filter_by(id=list_id,
                                   user_id=current_user.id).first_or_404()
    name = wl.name
    db.session.delete(wl)
    db.session.commit()
    flash(f'Deleted list "{name}".', 'info')
    return redirect(url_for('lists_index'))


# ---------------------------------------------------------------------------
# Routes — portfolios
# ---------------------------------------------------------------------------

@app.route('/portfolios')
@login_required
def portfolios_index():
    return render_template('portfolios.html', portfolios=user_portfolios())


@app.route('/portfolios/<int:pid>')
@login_required
def portfolio_detail(pid):
    p = Portfolio.query.filter_by(id=pid,
                                  user_id=current_user.id).first_or_404()
    return render_template('portfolio_detail.html', p=p)


@app.route('/portfolios/new', methods=['POST'])
@login_required
def portfolio_new():
    name = (request.form.get('name') or '').strip()
    if not name:
        flash('Enter a name for the portfolio.', 'error')
        return redirect(request.referrer or url_for('portfolios_index'))
    try:
        cash = float(request.form.get('cash') or 0)
    except ValueError:
        flash('Cash must be a number.', 'error')
        return redirect(request.referrer or url_for('portfolios_index'))
    p = Portfolio(user_id=current_user.id, name=name, cash=max(0.0, cash))
    db.session.add(p)
    db.session.commit()
    flash(f'Created portfolio "{name}".', 'success')
    return redirect(url_for('portfolio_detail', pid=p.id))


@app.route('/portfolios/<int:pid>/lots/new', methods=['POST'])
@login_required
def lot_new(pid):
    p = Portfolio.query.filter_by(id=pid,
                                  user_id=current_user.id).first_or_404()
    slug = (request.form.get('slug') or '').strip()
    inst = (Instrument.query.filter_by(slug=slug).first()
            or Instrument.query.filter(
                func.upper(Instrument.ticker) == slug.upper()).first())
    if not inst or not inst.quote:
        flash(f'No instrument matches "{slug}".', 'error')
        return redirect(url_for('portfolio_detail', pid=p.id))
    try:
        shares = float(request.form.get('shares') or 0)
        cost = float(request.form.get('cost_basis') or 0)
    except ValueError:
        flash('Shares and cost basis must be numbers.', 'error')
        return redirect(url_for('portfolio_detail', pid=p.id))
    if shares <= 0:
        flash('Shares must be greater than zero.', 'error')
        return redirect(url_for('portfolio_detail', pid=p.id))
    if cost <= 0:
        cost = inst.quote.price
    db.session.add(PortfolioLot(portfolio_id=p.id, instrument_id=inst.id,
                                shares=shares, cost_basis=cost,
                                purchased_on=MD.MARKET_DATE.isoformat()))
    db.session.commit()
    flash(f'Added {shares:g} shares of {inst.ticker} to "{p.name}".', 'success')
    return redirect(url_for('portfolio_detail', pid=p.id))


@app.route('/portfolios/<int:pid>/lots/<int:lot_id>/delete', methods=['POST'])
@login_required
def lot_delete(pid, lot_id):
    p = Portfolio.query.filter_by(id=pid,
                                  user_id=current_user.id).first_or_404()
    lot = PortfolioLot.query.filter_by(id=lot_id,
                                       portfolio_id=p.id).first_or_404()
    ticker = lot.instrument.ticker
    db.session.delete(lot)
    db.session.commit()
    flash(f'Removed {ticker} from "{p.name}".', 'info')
    return redirect(url_for('portfolio_detail', pid=p.id))


@app.route('/portfolios/<int:pid>/delete', methods=['POST'])
@login_required
def portfolio_delete(pid):
    p = Portfolio.query.filter_by(id=pid,
                                  user_id=current_user.id).first_or_404()
    name = p.name
    db.session.delete(p)
    db.session.commit()
    flash(f'Deleted portfolio "{name}".', 'info')
    return redirect(url_for('portfolios_index'))


# ---------------------------------------------------------------------------
# Health & errors
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Display settings (theme, up/down colour convention)
#
# Held in cookies and applied to <html> server-side, so the first paint is
# already correct. Google offers the same two switches behind the header gear.
# ---------------------------------------------------------------------------

THEMES = {'light': 'Light', 'dark': 'Dark'}
COLOR_MODES = {'local': 'Local market (green up)',
               'intl': 'International (red up)'}


def current_theme():
    v = request.cookies.get('gf_theme', 'light')
    return v if v in THEMES else 'light'


def current_colors():
    v = request.cookies.get('gf_colors', 'local')
    return v if v in COLOR_MODES else 'local'


@app.route('/settings/theme/<value>', methods=['GET'])
def set_theme(value):
    if value not in THEMES:
        abort(404)
    resp = redirect(_safe_next(request.args.get('next')))
    resp.set_cookie('gf_theme', value, max_age=60 * 60 * 24 * 365,
                    samesite='Lax')
    return resp


@app.route('/settings/colors/<value>', methods=['GET'])
def set_colors(value):
    if value not in COLOR_MODES:
        abort(404)
    resp = redirect(_safe_next(request.args.get('next')))
    resp.set_cookie('gf_colors', value, max_age=60 * 60 * 24 * 365,
                    samesite='Lax')
    return resp


@app.route('/_health')
def health():
    return {'ok': True, 'site': 'google_finance',
            'instruments': Instrument.query.count(),
            'news': NewsArticle.query.count(),
            'market_date': MD.MARKET_DATE.isoformat()}


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

MODELS = dict(Instrument=Instrument, Quote=Quote, PriceHistory=PriceHistory,
              FinancialRow=FinancialRow, EarningsRow=EarningsRow,
              KeyMoment=KeyMoment, InstitutionalHolder=InstitutionalHolder,
              AnalystRating=AnalystRating, EtfHolding=EtfHolding,
              Publisher=Publisher, NewsArticle=NewsArticle, NewsLink=NewsLink,
              MarketSummary=MarketSummary, User=User, Watchlist=Watchlist,
              WatchlistItem=WatchlistItem, Portfolio=Portfolio,
              PortfolioLot=PortfolioLot)

from seed_data import (seed_benchmark_users, seed_market,  # noqa: E402
                       seed_news)

with app.app_context():
    db.create_all()
    seed_market(db, MODELS)
    seed_news(db, MODELS)
    seed_benchmark_users(db, MODELS, bcrypt)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
