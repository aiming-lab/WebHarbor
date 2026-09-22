#!/usr/bin/env python3
"""Cboe Global Markets (cboe.com) mirror — delayed quotes with full option
chains, daily market statistics, Insights articles, Options Institute
classes/experts/courses, tradable products, market data pages, and an
authenticated account with watchlist, class registrations and saved articles."""
import json
import math
import os
import re
from datetime import datetime

from flask import (
    Flask, abort, flash, jsonify, redirect, render_template, request,
    url_for,
)
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "cboe.db")

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-cboe-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log in to manage your watchlist, class registrations, and saved articles."

# Reference date the snapshot was pinned against (live capture date).
MIRROR_REFERENCE_DATE = datetime(2026, 9, 21)
MIRROR_REFERENCE_DATE_TEXT = "September 21, 2026"

STOP_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "is", "are", "be", "by", "from", "how", "what", "which", "that",
    "this", "me", "my", "cboe", "index", "options", "market", "markets",
}


def _loads(text, default):
    try:
        return json.loads(text) if text else default
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(140), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    first_name = db.Column(db.String(80), default="")
    last_name = db.Column(db.String(80), default="")
    country = db.Column(db.String(80), default="United States")
    trader_type = db.Column(db.String(60), default="Individual investor")
    notify_market_take = db.Column(db.Boolean, default=True)
    notify_research = db.Column(db.Boolean, default=False)
    notify_products = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    watchlist_items = db.relationship("WatchlistItem", backref="user", lazy=True,
                                      cascade="all, delete-orphan")
    registrations = db.relationship("ClassRegistration", backref="user", lazy=True,
                                    cascade="all, delete-orphan")
    saved_articles = db.relationship("SavedArticle", backref="user", lazy=True,
                                      cascade="all, delete-orphan")

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode("utf-8")

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Symbol(db.Model):
    __tablename__ = "symbols"
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(16), unique=True, nullable=False)      # SPX
    display_symbol = db.Column(db.String(16), nullable=False)           # ^SPX
    name = db.Column(db.String(140), nullable=False)
    security_type = db.Column(db.String(20), default="index")
    has_options = db.Column(db.Boolean, default=True)
    order = db.Column(db.Integer, default=0)

    quote = db.relationship("Quote", backref="symbol_ref", lazy=True, uselist=False,
                            cascade="all, delete-orphan")
    intraday = db.relationship("IntradayBar", backref="symbol_ref", lazy=True,
                               cascade="all, delete-orphan",
                               order_by="IntradayBar.dt")
    options = db.relationship("OptionContract", backref="symbol_ref", lazy=True,
                              cascade="all, delete-orphan")

    def pct_label(self):
        if self.quote is None:
            return ""
        chg = self.quote.price_change or 0.0
        if chg > 0:
            return f"+{chg:.2f} (+{self.quote.price_change_percent:.2f}%)"
        if chg < 0:
            return f"{chg:.2f} ({self.quote.price_change_percent:.2f}%)"
        return f"0.00 (0.00%)"


class Quote(db.Model):
    __tablename__ = "quotes"
    id = db.Column(db.Integer, primary_key=True)
    symbol_id = db.Column(db.Integer, db.ForeignKey("symbols.id"), nullable=False)
    as_of = db.Column(db.String(40), default="")            # 2026-09-21 16:14:59 ET
    current_price = db.Column(db.Float, default=0.0)
    price_change = db.Column(db.Float, default=0.0)
    price_change_percent = db.Column(db.Float, default=0.0)
    bid = db.Column(db.Float, default=0.0)
    ask = db.Column(db.Float, default=0.0)
    open = db.Column(db.Float, default=0.0)
    high = db.Column(db.Float, default=0.0)
    low = db.Column(db.Float, default=0.0)
    close = db.Column(db.Float, default=0.0)
    prev_day_close = db.Column(db.Float, default=0.0)
    volume = db.Column(db.Integer, default=0)
    iv30 = db.Column(db.Float, default=0.0)
    iv30_change_percent = db.Column(db.Float, default=0.0)
    tick = db.Column(db.String(12), default="")
    last_trade_time = db.Column(db.String(40), default="")
    annual_high = db.Column(db.Float, default=0.0)
    annual_low = db.Column(db.Float, default=0.0)


class IntradayBar(db.Model):
    __tablename__ = "intraday_bars"
    id = db.Column(db.Integer, primary_key=True)
    symbol_id = db.Column(db.Integer, db.ForeignKey("symbols.id"), nullable=False)
    dt = db.Column(db.String(20), nullable=False)          # 2026-09-21T09:31:00
    open = db.Column(db.Float, default=0.0)
    high = db.Column(db.Float, default=0.0)
    low = db.Column(db.Float, default=0.0)
    close = db.Column(db.Float, default=0.0)
    calls_volume = db.Column(db.Integer, default=0)
    puts_volume = db.Column(db.Integer, default=0)
    total_options_volume = db.Column(db.Integer, default=0)


class OptionContract(db.Model):
    __tablename__ = "option_contracts"
    id = db.Column(db.Integer, primary_key=True)
    symbol_id = db.Column(db.Integer, db.ForeignKey("symbols.id"), nullable=False)
    code = db.Column(db.String(24), nullable=False, index=True)   # SPX261016C00200000
    root = db.Column(db.String(12), default="")                   # SPXW
    expiry = db.Column(db.String(10), nullable=False, index=True)  # 2026-10-16
    cp = db.Column(db.String(2), nullable=False, index=True)       # C / P
    strike = db.Column(db.Float, nullable=False)
    bid = db.Column(db.Float, default=0.0)
    ask = db.Column(db.Float, default=0.0)
    bid_size = db.Column(db.Float, default=0.0)
    ask_size = db.Column(db.Float, default=0.0)
    iv = db.Column(db.Float, default=0.0)
    open_interest = db.Column(db.Float, default=0.0)
    volume = db.Column(db.Float, default=0.0)
    delta = db.Column(db.Float, default=0.0)
    gamma = db.Column(db.Float, default=0.0)
    vega = db.Column(db.Float, default=0.0)
    theta = db.Column(db.Float, default=0.0)
    change = db.Column(db.Float, default=0.0)
    open = db.Column(db.Float, default=0.0)
    high = db.Column(db.Float, default=0.0)
    low = db.Column(db.Float, default=0.0)
    last_trade_price = db.Column(db.Float, default=0.0)
    last_trade_time = db.Column(db.String(40), default="")
    percent_change = db.Column(db.Float, default=0.0)
    prev_day_close = db.Column(db.Float, default=0.0)
    tick = db.Column(db.String(12), default="")


class SymbolDirectory(db.Model):
    __tablename__ = "symbol_directory"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(24), nullable=False, index=True)   # ticker
    company_name = db.Column(db.String(160), default="")


class MarketStatRatio(db.Model):
    __tablename__ = "market_stat_ratios"
    id = db.Column(db.Integer, primary_key=True)
    stat_date = db.Column(db.String(10), nullable=False, index=True)
    stat_key = db.Column(db.String(80), nullable=False)      # TOTAL PUT/CALL RATIO
    value = db.Column(db.String(12), nullable=False)


class MarketStatProduct(db.Model):
    __tablename__ = "market_stat_products"
    id = db.Column(db.Integer, primary_key=True)
    stat_date = db.Column(db.String(10), nullable=False, index=True)
    section = db.Column(db.String(80), nullable=False)   # SUM OF ALL PRODUCTS
    kind = db.Column(db.String(16), nullable=False)       # volume / open_interest
    call = db.Column(db.String(24), default="")
    put = db.Column(db.String(24), default="")
    total = db.Column(db.String(24), default="")


class ArticleCategory(db.Model):
    __tablename__ = "article_categories"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    blurb = db.Column(db.Text, default="")
    order = db.Column(db.Integer, default=0)


class Author(db.Model):
    __tablename__ = "authors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200), default="")
    bio = db.Column(db.Text, default="")
    headshot = db.Column(db.String(240), default="")


class Article(db.Model):
    __tablename__ = "articles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(240), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("article_categories.id"))
    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"))
    author_name = db.Column(db.String(120), default="")
    date = db.Column(db.String(40), default="")           # September 16, 2026
    date_sort = db.Column(db.String(12), default="")      # 2026-09-16
    summary = db.Column(db.Text, default="")
    body_json = db.Column(db.Text, default="[]")          # structured blocks
    tags_json = db.Column(db.Text, default="[]")
    body_text = db.Column(db.Text, default="")            # flat text for search

    category = db.relationship("ArticleCategory", backref="articles", lazy=True)
    author = db.relationship("Author", backref="articles", lazy=True)

    def body(self):
        return _loads(self.body_json, [])

    def tags(self):
        return _loads(self.tags_json, [])

    def excerpt(self):
        if self.summary:
            return self.summary
        for block in self.body():
            if block.get("type") == "p" and block.get("text"):
                return block["text"][:220]
        return ""


class Expert(db.Model):
    __tablename__ = "experts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200), default="")
    headshot = db.Column(db.String(240), default="")
    bio = db.Column(db.Text, default="")
    order = db.Column(db.Integer, default=0)


class OIClass(db.Model):
    __tablename__ = "oi_classes"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    series = db.Column(db.String(160), default="")
    description = db.Column(db.Text, default="")
    instructor = db.Column(db.String(120), default="")
    instructor_title = db.Column(db.String(200), default="")
    instructor_bio = db.Column(db.Text, default="")
    date = db.Column(db.String(80), default="")       # Wednesday, September 23 2026
    date_sort = db.Column(db.String(12), default="")
    time = db.Column(db.String(60), default="")       # 11:00 am (CT)
    format = db.Column(db.String(30), default="Virtual")
    level = db.Column(db.String(40), default="Foundational")
    language = db.Column(db.String(40), default="English")
    region = db.Column(db.String(60), default="North America")
    topic = db.Column(db.String(120), default="")

    registrations = db.relationship("ClassRegistration", backref="klass", lazy=True,
                                    cascade="all, delete-orphan")


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    intro = db.Column(db.Text, default="")
    hero_image = db.Column(db.String(240), default="")
    modules_json = db.Column(db.Text, default="[]")
    order = db.Column(db.Integer, default=0)

    def modules(self):
        return _loads(self.modules_json, [])


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    family = db.Column(db.String(60), default="")     # sp-500 / vix
    name = db.Column(db.String(200), nullable=False)
    eyebrow = db.Column(db.String(120), default="")   # S&P 500 INDEX OPTIONS
    hero_title = db.Column(db.String(200), default="")
    hero_desc = db.Column(db.Text, default="")
    trade_volume = db.Column(db.String(30), default="")
    trade_open_interest = db.Column(db.String(30), default="")
    trade_as_of = db.Column(db.String(40), default="")
    quote_symbol = db.Column(db.String(16), default="")
    benefits_json = db.Column(db.Text, default="[]")
    sections_json = db.Column(db.Text, default="[]")
    gth_note = db.Column(db.Text, default="")
    gth_json = db.Column(db.Text, default="[]")
    resources_json = db.Column(db.Text, default="[]")
    specs_json = db.Column(db.Text, default="[]")
    quick_links_json = db.Column(db.Text, default="[]")
    calculator = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)

    def benefits(self):
        return _loads(self.benefits_json, [])

    def sections(self):
        return _loads(self.sections_json, [])

    def gth(self):
        return _loads(self.gth_json, [])

    def resources(self):
        return _loads(self.resources_json, [])

    def specs(self):
        return _loads(self.specs_json, [])

    def quick_links(self):
        return _loads(self.quick_links_json, [])


class WatchlistItem(db.Model):
    __tablename__ = "watchlist_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    symbol_id = db.Column(db.Integer, db.ForeignKey("symbols.id"), nullable=False)
    added_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)
    symbol = db.relationship("Symbol", lazy=True)


class ClassRegistration(db.Model):
    __tablename__ = "class_registrations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("oi_classes.id"), nullable=False)
    registered_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)
    status = db.Column(db.String(30), default="Registered")


class SavedArticle(db.Model):
    __tablename__ = "saved_articles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    saved_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)
    article = db.relationship("Article", lazy=True)


class Subscriber(db.Model):
    __tablename__ = "subscribers"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(140), nullable=False)
    first_name = db.Column(db.String(80), default="")
    last_name = db.Column(db.String(80), default="")
    country = db.Column(db.String(80), default="")
    trader_type = db.Column(db.String(60), default="")
    prefs_json = db.Column(db.Text, default="[]")
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    def prefs(self):
        return _loads(self.prefs_json, [])


class HomePageCard(db.Model):
    """Homepage Market Snapshot + volume snapshot values (captured live)."""
    __tablename__ = "home_page_cards"
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(40), nullable=False)   # volume_snapshot / market_snapshot / hero
    payload_json = db.Column(db.Text, default="{}")
    order = db.Column(db.Integer, default=0)

    def payload(self):
        return _loads(self.payload_json, {})


class StaticPage(db.Model):
    """Content pages (about, hours, GTH, product list, markets pages)."""
    __tablename__ = "static_pages"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(200), default="")
    intro = db.Column(db.Text, default="")
    sections_json = db.Column(db.Text, default="[]")

    def sections(self):
        return _loads(self.sections_json, [])


class OiEventFilter(db.Model):
    """Filter taxonomy options used by the classes page dropdowns."""
    __tablename__ = "oi_event_filters"
    id = db.Column(db.Integer, primary_key=True)
    facet = db.Column(db.String(40), nullable=False)   # instructor / level / language / region / format
    value = db.Column(db.String(120), nullable=False)
    order = db.Column(db.Integer, default=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def parse_osi(code):
    """SPXW261016P00775000 -> (SPXW, 2026-10-16, P, 7750.0)"""
    m = re.match(r"^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d+)$", code)
    if not m:
        return None
    root, yy, mm, dd, cp, strike_raw = m.groups()
    expiry = f"20{yy}-{mm}-{dd}"
    strike = int(strike_raw) / 1000.0
    return root, expiry, cp, strike


def fmt_num(value, decimals=2):
    if value is None:
        return "-"
    if isinstance(value, float) and value == int(value) and abs(value) < 1e15:
        return f"{int(value):,}"
    try:
        return f"{value:,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def fmt_int(value):
    if value is None:
        return "-"
    try:
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return str(value)


def scored_search(query, rows, fields, limit=60):
    """Token-overlap scored search (never strict AND)."""
    tokens = [t.lower() for t in re.split(r"\W+", query or "")
              if t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return rows[:limit]
    scored = []
    for row in rows:
        text = " ".join(str(getattr(row, f, "") or "") for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1].id if hasattr(pair[1], "id") else 0))
    return [row for _, row in scored[:limit]]


def intraday_svg(bars, width=560, height=200, color="#2AD870"):
    """Server-rendered area chart SVG for the intraday series."""
    points = [(b.dt, b.close) for b in bars if b.close]
    if len(points) < 2:
        return ""
    values = [v for _, v in points]
    vmin, vmax = min(values), max(values)
    span = (vmax - vmin) or 1.0
    n = len(points)
    coords = []
    for i, (_, v) in enumerate(points):
        x = 2 + (i / (n - 1)) * (width - 4)
        y = height - 6 - ((v - vmin) / span) * (height - 22)
        coords.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(coords)
    area = f"2,{height - 4} {poly} {width - 2},{height - 4}"
    ticks = []
    for frac, label in [(0, points[0][0][11:16]), (0.5, ""), (1, points[-1][0][11:16])]:
        x = 2 + frac * (width - 4)
        ticks.append(f'<line x1="{x:.0f}" y1="{height - 4}" x2="{x:.0f}" y2="{height}" stroke="#0B173C" stroke-width="1"/>')
        if label:
            ticks.append(f'<text x="{x:.0f}" y="{height + 10}" font-size="9" fill="#5B6B8C" text-anchor="middle">{label}</text>')
    return Markup(
        f'<svg viewBox="0 0 {width} {height + 12}" width="100%" height="{height + 12}" role="img" aria-label="intraday chart">'
        f'<defs><linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.45"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>'
        f'</linearGradient></defs>'
        f'<polygon points="{area}" fill="url(#areaGrad)"/>'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="1.6"/>'
        f'{"".join(ticks)}</svg>'
    )


def get_symbol_or_404(ticker):
    sym = Symbol.query.filter_by(ticker=ticker.upper()).first()
    if sym is None:
        abort(404)
    return sym


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def expiry_label(value):
    """2026-09-21 -> 'Mon Sep 21 2026' (how the live chain renders expiry blocks)."""
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
        return f"{_WEEKDAYS[d.weekday()]} {_MONTHS[d.month - 1]} {d.day} {d.year}"
    except (TypeError, ValueError):
        return value


app.jinja_env.filters["fmt_num"] = fmt_num
app.jinja_env.filters["fmt_int"] = fmt_int
app.jinja_env.filters["expiry_label"] = expiry_label
app.jinja_env.globals["fmt_num"] = fmt_num
app.jinja_env.globals["fmt_int"] = fmt_int
app.jinja_env.globals["expiry_label"] = expiry_label
app.jinja_env.globals["MIRROR_REFERENCE_DATE_TEXT"] = MIRROR_REFERENCE_DATE_TEXT


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    cards = {c.section: c.payload() for c in HomePageCard.query.all()}
    vix = Symbol.query.filter_by(ticker="VIX").first()
    spx = Symbol.query.filter_by(ticker="SPX").first()
    for sym in (vix, spx):
        if sym and sym.quote:
            key = "vix_card" if sym.ticker == "VIX" else "spx_card"
            cards[key] = {
                "ticker": sym.ticker,
                "name": sym.name,
                "quote": sym.quote,
                "svg": intraday_svg(sym.intraday),
            }
    latest = Article.query.order_by(Article.date_sort.desc(), Article.id).limit(3).all()
    return render_template("index.html", cards=cards, vix=vix, spx=spx, latest=latest)


@app.route("/delayed_quotes/<ticker>")
def quote_dashboard(ticker):
    sym = get_symbol_or_404(ticker)
    q = sym.quote
    svg = intraday_svg(sym.intraday)
    return render_template("quote_dashboard.html", sym=sym, quote=q, svg=svg,
                           tab="dashboard")


@app.route("/delayed_quotes/<ticker>/chart")
def quote_charts(ticker):
    sym = get_symbol_or_404(ticker)
    q = sym.quote
    svg = intraday_svg(sym.intraday, width=900, height=300)
    return render_template("quote_charts.html", sym=sym, quote=q, svg=svg,
                           tab="charts")


@app.route("/delayed_quotes/<ticker>/metrics")
def quote_metrics(ticker):
    sym = get_symbol_or_404(ticker)
    q = sym.quote
    calls_vol = db.session.query(db.func.coalesce(db.func.sum(OptionContract.volume), 0)).filter_by(
        symbol_id=sym.id, cp="C").scalar()
    puts_vol = db.session.query(db.func.coalesce(db.func.sum(OptionContract.volume), 0)).filter_by(
        symbol_id=sym.id, cp="P").scalar()
    calls_int = db.session.query(db.func.coalesce(db.func.sum(OptionContract.open_interest), 0)).filter_by(
        symbol_id=sym.id, cp="C").scalar()
    puts_int = db.session.query(db.func.coalesce(db.func.sum(OptionContract.open_interest), 0)).filter_by(
        symbol_id=sym.id, cp="P").scalar()
    pcr = (puts_vol / calls_vol) if calls_vol else 0
    return render_template("quote_metrics.html", sym=sym, quote=q,
                           calls_vol=calls_vol, puts_vol=puts_vol,
                           calls_int=calls_int, puts_int=puts_int, pcr=pcr,
                           tab="metrics")


RANGES = {
    "all": "All",
    "ntm": "Near the Money",
    "itm": "In the Money",
    "otm": "Out of the Money",
}


@app.route("/delayed_quotes/<ticker>/quote_table")
def quote_table(ticker):
    sym = get_symbol_or_404(ticker)
    q = sym.quote
    opts = OptionContract.query.filter_by(symbol_id=sym.id)
    expiries = sorted({r[0] for r in db.session.query(OptionContract.expiry).filter_by(symbol_id=sym.id).distinct()})

    # Filters mirror the live quote tool.
    expiration = request.args.get("expiration", "")            # YYYY-MM or ''
    opt_range = request.args.get("range", "ntm")
    size = request.args.get("size", 3, type=int)
    volume_min = request.args.get("volume", "all")              # all / >0

    if expiration:
        opts = opts.filter(OptionContract.expiry.like(f"{expiration}%"))
        month_expiries = [e for e in expiries if e.startswith(expiration)]
    else:
        month_expiries = expiries

    rows = opts.all()
    by_expiry = {}
    for o in rows:
        by_expiry.setdefault(o.expiry, []).append(o)

    spot = q.current_price if q else 0.0
    table = []
    total = 0
    # The live quote tool's "Near the Money" default view shows the nearest
    # four daily expiries with 2x `size` strikes around the spot (48 records
    # with the default size of 3), so mirror that behavior for ntm.
    shown_expiries = month_expiries
    if opt_range == "ntm":
        shown_expiries = month_expiries[:4]
    for expiry in shown_expiries:
        contracts = by_expiry.get(expiry, [])
        strikes = sorted({o.strike for o in contracts})
        if opt_range == "ntm" and spot:
            close = sorted(strikes, key=lambda s: abs(s - spot))
            chosen = sorted(close[:max(size * 2, 1)])
        elif opt_range == "ntm":
            chosen = strikes[:size * 2]
        elif opt_range == "itm" and spot:
            call_itm = [s for s in strikes if s < spot]
            chosen = call_itm[-size:] if len(call_itm) > size else call_itm
        elif opt_range == "otm" and spot:
            call_otm = [s for s in strikes if s >= spot]
            chosen = call_otm[:size]
        else:
            chosen = strikes
        chosen = sorted(chosen)
        for strike in chosen:
            call = next((o for o in contracts if o.cp == "C" and o.strike == strike), None)
            put = next((o for o in contracts if o.cp == "P" and o.strike == strike), None)
            if volume_min == ">0":
                if (call is None or not call.volume) and (put is None or not put.volume):
                    continue
            table.append({
                "expiry": expiry, "strike": strike,
                "call": call, "put": put,
                "root": (call or put).root,
            })
            # "Total Records" counts contracts (call + put per row) like the
            # live quote tool (48 records for the default NTM view).
            total += 2 if (call and put) else 1

    months = sorted({e[:7] for e in expiries})
    capped = total > 3000
    return render_template(
        "quote_table.html", sym=sym, quote=q, table=table[:3000], total=total,
        months=months, expiration=expiration, opt_range=opt_range,
        size=size, volume_min=volume_min, ranges=RANGES, tab="options",
        capped=capped,
    )


@app.route("/symbol_search")
def symbol_search():
    """Typeahead used by the quote pages' symbol box."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    ql = q.lower()
    exact = Symbol.query.filter(Symbol.ticker.ilike(q)).all()
    rows = SymbolDirectory.query.filter(
        (SymbolDirectory.name.ilike(f"{ql}%")) | (SymbolDirectory.company_name.ilike(f"%{ql}%"))
    ).limit(10).all()
    results = [{"name": s.name, "company": s.company_name,
                "mirror": s.name.upper() in {t.ticker for t in exact}}
               for s in rows]
    return jsonify(results)


# ----- market statistics ---------------------------------------------------

@app.route("/markets/us/options/market-statistics/daily")
def market_statistics_daily():
    dates = sorted({r[0] for r in db.session.query(MarketStatRatio.stat_date).distinct()}, reverse=True)
    stat_date = request.args.get("dt", dates[0] if dates else "")
    ratios = MarketStatRatio.query.filter_by(stat_date=stat_date).order_by(MarketStatRatio.id).all()
    products = MarketStatProduct.query.filter_by(stat_date=stat_date).order_by(MarketStatProduct.id).all()
    sections = []
    for prod in products:
        if not sections or sections[-1]["name"] != prod.section:
            sections.append({"name": prod.section, "rows": []})
        sections[-1]["rows"].append(prod)
    return render_template("market_statistics.html", dates=dates, stat_date=stat_date,
                           ratios=ratios, sections=sections)


# ----- insights ------------------------------------------------------------

@app.route("/insights/")
@app.route("/insights")
def insights_overview():
    categories = ArticleCategory.query.order_by(ArticleCategory.order).all()
    latest = Article.query.order_by(Article.date_sort.desc(), Article.id).limit(6).all()
    tmt = Article.query.filter_by(category_id=_category_id("todays-markettake")).order_by(
        Article.date_sort.desc(), Article.id).limit(4).all()
    return render_template("insights_overview.html", categories=categories,
                           latest=latest, tmt=tmt)


def _category_id(slug):
    cat = ArticleCategory.query.filter_by(slug=slug).first()
    return cat.id if cat else None


@app.route("/insights/todays-market-take")
def insights_tmt():
    cat_id = _category_id("todaysmarkettake")
    daily = Article.query.filter_by(category_id=cat_id).order_by(
        Article.date_sort.desc(), Article.id).limit(8).all()
    author = Author.query.filter_by(name="JJ Kinahan").first()
    return render_template("insights_tmt.html", daily=daily, author=author)


@app.route("/insights/categories/<slug>/")
@app.route("/insights/categories/<slug>")
def insights_category(slug):
    cat = ArticleCategory.query.filter_by(slug=slug).first()
    if cat is None:
        abort(404)
    page = request.args.get("page", 1, type=int)
    per_page = 10
    pagination = Article.query.filter_by(category_id=cat.id).order_by(
        Article.date_sort.desc(), Article.id).paginate(page=page, per_page=per_page,
                                                       error_out=False)
    categories = ArticleCategory.query.order_by(ArticleCategory.order).all()
    return render_template("insights_category.html", cat=cat,
                           articles=pagination.items, pagination=pagination,
                           categories=categories)


@app.route("/insights/posts/<slug>/")
@app.route("/insights/posts/<slug>")
def article_detail(slug):
    article = Article.query.filter_by(slug=slug).first()
    if article is None:
        abort(404)
    related = Article.query.filter(
        Article.category_id == article.category_id, Article.id != article.id
    ).order_by(Article.date_sort.desc(), Article.id).limit(3).all()
    saved = False
    if current_user.is_authenticated:
        saved = SavedArticle.query.filter_by(user_id=current_user.id,
                                             article_id=article.id).first() is not None
    return render_template("article_detail.html", article=article, related=related,
                           saved=saved)


# ----- options institute ---------------------------------------------------

@app.route("/optionsinstitute")
def oi_home():
    classes = OIClass.query.order_by(OIClass.date_sort).limit(3).all()
    experts = Expert.query.order_by(Expert.order).limit(6).all()
    courses = Course.query.order_by(Course.order).all()
    return render_template("oi_home.html", classes=classes, experts=experts,
                           courses=courses)


@app.route("/optionsinstitute/classes")
def oi_classes():
    rows = OIClass.query.order_by(OIClass.date_sort).all()
    facets = {}
    for f in OiEventFilter.query.order_by(OiEventFilter.facet, OiEventFilter.order):
        facets.setdefault(f.facet, []).append(f.value)
    filters = {
        "instructor": request.args.get("instructor", ""),
        "level": request.args.get("level", ""),
        "language": request.args.get("language", ""),
        "region": request.args.get("region", ""),
        "format": request.args.get("format", ""),
    }
    shown = [c for c in rows if
             (not filters["instructor"] or c.instructor == filters["instructor"]) and
             (not filters["level"] or c.level == filters["level"]) and
             (not filters["language"] or c.language == filters["language"]) and
             (not filters["region"] or c.region == filters["region"]) and
             (not filters["format"] or c.format == filters["format"])]
    registered = set()
    if current_user.is_authenticated:
        registered = {r.class_id for r in ClassRegistration.query.filter_by(user_id=current_user.id)}
    return render_template("oi_classes.html", classes=shown, facets=facets,
                           filters=filters, registered=registered)


@app.route("/optionsinstitute/experts")
def oi_experts():
    experts = Expert.query.order_by(Expert.order).all()
    return render_template("oi_experts.html", experts=experts)


@app.route("/optionsinstitute/courses/<slug>/")
@app.route("/optionsinstitute/courses/<slug>")
def oi_course(slug):
    course = Course.query.filter_by(slug=slug).first()
    if course is None:
        abort(404)
    return render_template("oi_course.html", course=course)


@app.route("/optionsinstitute/defining-options")
def oi_defining():
    course = Course.query.filter_by(slug="defining-options").first()
    if course:
        return render_template("oi_course.html", course=course)
    abort(404)


# ----- tradable products ----------------------------------------------------

@app.route("/tradable-products/product-list")
def product_list():
    products = Product.query.order_by(Product.order).all()
    families = {}
    for p in products:
        families.setdefault(p.family or "other", []).append(p)
    return render_template("product_list.html", families=families)


@app.route("/tradable-products/sp-500/spx-options")
@app.route("/tradable-products/sp-500/spx-options/")
def product_spx():
    return _render_product("spx-options")


@app.route("/tradable-products/sp-500/spx-options/spx-specifications")
def product_spx_specs():
    return _render_product("spx-options", view="specs")


@app.route("/tradable-products/sp-500/xsp-options")
@app.route("/tradable-products/sp-500/xsp-options/")
def product_xsp():
    return _render_product("xsp-options")


@app.route("/tradable-products/vix/vix-options")
@app.route("/tradable-products/vix/vix-options/")
def product_vix_options():
    return _render_product("vix-options")


@app.route("/tradable-products/vix/vix-futures")
@app.route("/tradable-products/vix/vix-futures/")
def product_vix_futures():
    return _render_product("vix-futures")


def _render_product(slug, view="overview"):
    product = Product.query.filter_by(slug=slug).first()
    if product is None:
        abort(404)
    related_articles = Article.query.limit(3).all()
    return render_template("product_detail.html", p=product, view=view,
                           related=related_articles)


# ----- about / markets -----------------------------------------------------

@app.route("/about/")
@app.route("/about")
def about():
    page = StaticPage.query.filter_by(slug="about").first()
    return render_template("static_page.html", page=page, title="About Us")


@app.route("/about/hours")
def about_hours():
    page = StaticPage.query.filter_by(slug="hours").first()
    return render_template("static_page.html", page=page, title="Hours & Holidays")


@app.route("/about/global-trading-hours")
def about_gth():
    page = StaticPage.query.filter_by(slug="gth").first()
    return render_template("static_page.html", page=page, title="Global Trading Hours")


@app.route("/markets/us/options/")
@app.route("/markets/us/options")
def markets_us_options():
    page = StaticPage.query.filter_by(slug="markets-us-options").first()
    products = Product.query.order_by(Product.order).all()
    return render_template("markets_us_options.html", page=page, products=products)


# ----- search --------------------------------------------------------------

@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    articles, symbols, classes, experts, products, directory, courses = [], [], [], [], [], [], []
    if q:
        articles = scored_search(q, Article.query.all(),
                                ["title", "body_text", "author_name", "summary"])
        classes = scored_search(q, OIClass.query.all(),
                                ["title", "description", "instructor", "topic"])
        experts = scored_search(q, Expert.query.all(), ["name", "title", "bio"])
        products = scored_search(q, Product.query.all(),
                                 ["name", "hero_title", "hero_desc", "family"])
        courses = []
        for course in Course.query.order_by(Course.order).all():
            hay = " ".join([course.title, course.intro] +
                            [m.get("title", "") + " " + m.get("q", "") + " " +
                             m.get("duration", "")
                             for m in course.modules()]).lower()
            if q.lower() in hay:
                courses.append(course)
        ql = q.lower()
        symbols = Symbol.query.filter(
            (Symbol.ticker.ilike(f"%{q}%")) | (Symbol.name.ilike(f"%{q}%"))).all()
        directory = SymbolDirectory.query.filter(
            (SymbolDirectory.name.ilike(f"{ql}%")) |
            (SymbolDirectory.company_name.ilike(f"%{q}%"))).limit(12).all()
    return render_template("search.html", q=q, articles=articles, symbols=symbols,
                           classes=classes, experts=experts, products=products,
                           directory=directory, courses=courses)


# ---------------------------------------------------------------------------
# Auth + account
# ---------------------------------------------------------------------------

@app.route("/account/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            dest = request.args.get("next")
            if dest and dest.startswith("/"):
                return redirect(dest)
            return redirect(url_for("account"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/account/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        if not email or not username or not password:
            flash("Email, username, and password are required.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        elif User.query.filter_by(username=username).first():
            flash("An account with that username already exists.", "error")
        else:
            user = User(email=email, username=username,
                        display_name=display_name or username,
                        created_at=MIRROR_REFERENCE_DATE)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/account/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    watchlist = WatchlistItem.query.filter_by(user_id=current_user.id).order_by(WatchlistItem.id).all()
    regs = ClassRegistration.query.filter_by(user_id=current_user.id).order_by(ClassRegistration.id).all()
    saved = SavedArticle.query.filter_by(user_id=current_user.id).order_by(SavedArticle.id).all()
    return render_template("account.html", watchlist=watchlist, regs=regs, saved=saved)


@app.route("/account/watchlist/add", methods=["POST"])
@login_required
def watchlist_add():
    ticker = request.form.get("ticker", "").upper()
    sym = Symbol.query.filter_by(ticker=ticker).first()
    if sym is None:
        flash(f"{ticker} is not available on this mirror.", "error")
    elif WatchlistItem.query.filter_by(user_id=current_user.id, symbol_id=sym.id).first():
        flash(f"{ticker} is already on your watchlist.", "error")
    else:
        db.session.add(WatchlistItem(user_id=current_user.id, symbol_id=sym.id))
        db.session.commit()
        flash(f"{ticker} added to your watchlist.", "success")
    return redirect(request.form.get("next") or url_for("account"))


@app.route("/account/watchlist/remove", methods=["POST"])
@login_required
def watchlist_remove():
    ticker = request.form.get("ticker", "").upper()
    sym = Symbol.query.filter_by(ticker=ticker).first()
    if sym:
        item = WatchlistItem.query.filter_by(user_id=current_user.id, symbol_id=sym.id).first()
        if item:
            db.session.delete(item)
            db.session.commit()
            flash(f"{ticker} removed from your watchlist.", "success")
    return redirect(request.form.get("next") or url_for("account"))


@app.route("/account/classes/register", methods=["POST"])
@login_required
def class_register():
    class_id = request.form.get("class_id", type=int)
    klass = OIClass.query.get(class_id) if class_id else None
    if klass is None:
        flash("Class not found.", "error")
    elif ClassRegistration.query.filter_by(user_id=current_user.id, class_id=klass.id).first():
        flash("You are already registered for that class.", "error")
    else:
        db.session.add(ClassRegistration(user_id=current_user.id, class_id=klass.id))
        db.session.commit()
        flash(f"Registered for {klass.title}.", "success")
    return redirect(url_for("oi_classes"))


@app.route("/account/classes/withdraw", methods=["POST"])
@login_required
def class_withdraw():
    reg_id = request.form.get("registration_id", type=int)
    reg = ClassRegistration.query.get(reg_id) if reg_id else None
    if reg and reg.user_id == current_user.id:
        db.session.delete(reg)
        db.session.commit()
        flash("Registration withdrawn.", "success")
    return redirect(url_for("account"))


@app.route("/account/saved/toggle", methods=["POST"])
@login_required
def saved_toggle():
    slug = request.form.get("slug", "")
    article = Article.query.filter_by(slug=slug).first()
    if article is None:
        flash("Article not found.", "error")
        return redirect(url_for("insights_overview"))
    item = SavedArticle.query.filter_by(user_id=current_user.id, article_id=article.id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash("Article removed from your saved list.", "success")
    else:
        db.session.add(SavedArticle(user_id=current_user.id, article_id=article.id))
        db.session.commit()
        flash("Article saved.", "success")
    return redirect(url_for("article_detail", slug=slug))


@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email", "").strip().lower()
    if not email or "@" not in email:
        flash("Enter a valid email address to subscribe.", "error")
    else:
        prefs = request.form.getlist("prefs")
        db.session.add(Subscriber(
            email=email,
            first_name=request.form.get("first_name", ""),
            last_name=request.form.get("last_name", ""),
            country=request.form.get("country", ""),
            trader_type=request.form.get("trader_type", ""),
            prefs_json=json.dumps(prefs),
        ))
        db.session.commit()
        flash("Subscribed. Stay tuned for the next Today's Market Take.", "success")
    return redirect(request.form.get("next") or url_for("insights_tmt"))


# ---------------------------------------------------------------------------
# Health + errors
# ---------------------------------------------------------------------------

@app.route("/_health")
def health():
    return {
        "ok": True,
        "site": "cboe",
        "symbols": Symbol.query.count(),
        "option_contracts": OptionContract.query.count(),
        "intraday_bars": IntradayBar.query.count(),
        "symbol_directory": SymbolDirectory.query.count(),
        "articles": Article.query.count(),
        "experts": Expert.query.count(),
        "classes": OIClass.query.count(),
        "users": User.query.count(),
    }


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("500.html"), 500


with app.app_context():
    db.create_all()
    from seed_data import seed_benchmark_users, seed_database

    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
