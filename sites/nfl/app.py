"""NFL.com mirror — Flask app (WebHarbor contributor track).

Functional mirror of https://www.nfl.com/ (snapshot 2026-09-24):
live scoreboard ribbon and week-by-week scores/schedules for the 2026 regular
season, game centers with quarter scores, standings, all 32 club pages with
full rosters, the player directory with scored search, player pages with
season/career stats and game logs, the newsroom (82 real articles), the video
hub, league stat leaderboards (11 categories), the Week 3 injury report, the
September transaction log, NFL+ subscription plans with a full checkout chain,
account personalization (favorite team), site-wide scored search, and the
upstream chrome (utility bar, scores ribbon, mega nav, footer).

Seed data is materialized deterministically from the tracked source_data/
snapshots by seed_data.py (see .build-generated-seed).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Running `python app.py` executes this file as __main__ while seed_data.py
# imports it again as `app`; alias the module early so both names share one
# Flask/SQLAlchemy instance.
if __name__ == "__main__":
    sys.modules.setdefault("app", sys.modules[__name__])

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup

SITE_SLUG = "nfl"
SITE_NAME = "NFL"
BENCHMARK_PASSWORD = "TestPass123!"
MIRROR_DATE = datetime(2026, 9, 24)
BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
SEED_DIR = BASE_DIR / "instance_seed"
IMAGE_DIR = BASE_DIR / "static" / "images"
RUNTIME_DB_PATH = INSTANCE_DIR / "nfl.db"
SEED_DB_PATH = SEED_DIR / "nfl.db"
DB_URI_OVERRIDE = os.environ.get("NFL_DB_PATH", "")
PASSWORD_NAMESPACE = "nfl-webharbor-demo"
CURRENT_WEEK = 3
SEASON = 2026
STAT_CATEGORIES = (
    ("passing", "Passing"),
    ("rushing", "Rushing"),
    ("receiving", "Receiving"),
    ("tackles", "Tackles"),
    ("interceptions", "Interceptions"),
    ("fumbles", "Fumbles"),
    ("kickoffs", "Kickoffs"),
    ("kickoff_returns", "Kickoff Returns"),
    ("punting", "Punting"),
    ("punt_returns", "Punt Returns"),
    ("field_goals", "Field Goals"),
)
POSITIONS = (
    "QB", "RB", "FB", "WR", "TE", "OT", "G", "C", "OG", "OL", "LS",
    "DE", "DT", "NT", "DL", "LB", "OLB", "ILB", "EDGE",
    "CB", "S", "SAF", "DB", "K", "P", "KR", "PR",
)
ROSTER_STATUSES = ("ACT", "RES", "RSV", "NON", "INJ", "PRA", "SUS", "EXE", "DEV", "RSN", "CUT", "UDF", "FUT", "RET")
STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "is",
    "it", "by", "with", "vs", "versus", "nfl", "com",
}


def _ensure_dirs() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


_ensure_dirs()

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config["SECRET_KEY"] = "nfl-demo-session-key"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    DB_URI_OVERRIDE if DB_URI_OVERRIDE.startswith("sqlite:///")
    else f"sqlite:///{RUNTIME_DB_PATH}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to your NFL.com account to continue."


def stable_password_hash(raw_password: str) -> str:
    digest = hashlib.sha256()
    digest.update(f"{PASSWORD_NAMESPACE}:{raw_password}".encode("utf-8"))
    return digest.hexdigest()


def load_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def quarter_scores(raw: str | None) -> list[int]:
    """Parse a JSON quarter column (e.g. "[3, 7, 7, 10, 0]") into the
    per-quarter integers the game-center table renders, padded to the five
    quarter slots (4 quarters + OT). The column is JSON text: iterating it
    directly would slice characters, not quarters (r2 review finding F1)."""
    vals = load_json(raw, [])
    if not isinstance(vals, list):
        vals = []
    scores = [int(v) for v in vals if isinstance(v, (int, float))][:5]
    return scores + [0] * (5 - len(scores))


def slugify(value: str) -> str:
    cleaned: list[str] = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    return "".join(cleaned).strip("-")


def scored_search(query: str, items: list, fields: list[str]) -> list:
    """Token-overlap relevance scoring; never a strict AND."""
    tokens = [
        t for t in re.split(r"\W+", query.lower())
        if t not in STOP_WORDS and len(t) > 1
    ]
    if not tokens:
        return items
    scored = []
    for item in items:
        text = " ".join(
            str(getattr(item, f, "") or "") for f in fields
        ).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            scored.append((item, score))

    def sort_key(pair):
        item, score = pair
        identity = getattr(item, "id", None)
        if identity is None:
            identity = getattr(item, "abbr", None) or str(item)
        return (-score, str(identity))

    scored.sort(key=sort_key)
    return [item for item, _ in scored]


def eastern_kickoff(raw_time: str) -> datetime | None:
    """Convert an upstream UTC kickoff ("...Z") to US Eastern time.

    NFL.com renders every game day, date and time in the Eastern timezone,
    but the upstream feed stores the UTC instant (its ``date`` field is the
    UTC calendar day). Day/date must therefore be derived from the Eastern
    conversion, or prime-time kickoffs (>= 8pm ET) display the UTC day, one
    day late, contradicting the TNF/SNF/MNF badges. The offset itself is
    DST-aware: EDT (UTC-4) from the second Sunday of March to the first
    Sunday of November, EST (UTC-5) otherwise, so post-DST kickoffs do not
    run an hour late. Transition instants are the 02:00 local marks
    (07:00Z in March, 06:00Z in November).
    """
    if not raw_time:
        return None
    try:
        kickoff = datetime.strptime(raw_time, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    year = kickoff.year
    march_1 = datetime(year, 3, 1)
    november_1 = datetime(year, 11, 1)
    dst_start = march_1 + timedelta(days=(6 - march_1.weekday()) % 7 + 7, hours=7)
    dst_end = november_1 + timedelta(days=(6 - november_1.weekday()) % 7, hours=6)
    offset = 4 if dst_start <= kickoff < dst_end else 5
    return kickoff - timedelta(hours=offset)


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #

class Team(db.Model):
    __tablename__ = "teams"

    abbr = db.Column(db.String(4), primary_key=True)
    full_name = db.Column(db.String(60), nullable=False)
    logo_file = db.Column(db.String(80), default="", nullable=False)
    location = db.Column(db.String(40), nullable=False)
    nickname = db.Column(db.String(40), nullable=False)
    conference = db.Column(db.String(4), nullable=False)
    division = db.Column(db.String(30), nullable=False)
    primary_color = db.Column(db.String(10), default="#013369", nullable=False)
    secondary_color = db.Column(db.String(10), default="#D50A0A", nullable=False)
    established = db.Column(db.Integer, default=0, nullable=False)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    wins = db.Column(db.Integer, default=0, nullable=False)
    losses = db.Column(db.Integer, default=0, nullable=False)
    ties = db.Column(db.Integer, default=0, nullable=False)
    pct = db.Column(db.String(6), default="0.000", nullable=False)
    points_for = db.Column(db.Integer, default=0, nullable=False)
    points_against = db.Column(db.Integer, default=0, nullable=False)
    division_rank = db.Column(db.Integer, default=0, nullable=False)
    head_coach = db.Column(db.String(60), default="", nullable=False)
    stadium = db.Column(db.String(80), default="", nullable=False)
    owners = db.Column(db.String(120), default="", nullable=False)

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.losses}" + (f"-{self.ties}" if self.ties else "")

    @property
    def logo(self) -> str:
        return f"/static/images/{self.logo_file or f'logos/{self.abbr}.svg'}"

    @property
    def record_long(self) -> str:
        return (
            f"{self.wins} win{'s' if self.wins != 1 else ''}, "
            f"{self.losses} loss{'es' if self.losses != 1 else ''}, "
            f"{self.ties} tie{'s' if self.ties != 1 else ''}"
        )

    @property
    def division_ordinal(self) -> str:
        return {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(self.division_rank, "")


class Player(db.Model):
    __tablename__ = "players"
    __table_args__ = (db.Index("ix_players_team_pos", "team_abbr", "pos"),)

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    team_abbr = db.Column(db.String(4), db.ForeignKey("teams.abbr"), nullable=False)
    number = db.Column(db.String(4), default="", nullable=False)
    pos = db.Column(db.String(6), default="", nullable=False)
    status = db.Column(db.String(6), default="ACT", nullable=False)
    height_in = db.Column(db.Integer, default=0, nullable=False)
    weight = db.Column(db.Integer, default=0, nullable=False)
    experience = db.Column(db.String(4), default="", nullable=False)
    college = db.Column(db.String(60), default="", nullable=False)
    has_headshot = db.Column(db.Boolean, default=False, nullable=False)
    featured = db.Column(db.Boolean, default=False, nullable=False)
    arms = db.Column(db.String(12), default="", nullable=False)
    hands = db.Column(db.String(12), default="", nullable=False)
    age = db.Column(db.Integer, default=0, nullable=False)
    hometown = db.Column(db.String(80), default="", nullable=False)
    recent_games = db.Column(db.Text, default="", nullable=False)
    career = db.Column(db.Text, default="", nullable=False)

    @property
    def team(self):
        return Team.query.filter_by(abbr=self.team_abbr).first()

    @property
    def height_display(self) -> str:
        if not self.height_in:
            return ""
        inches = int(self.height_in)
        return f"{inches // 12}-{inches % 12}"

    @property
    def headshot(self) -> str:
        return f"/static/images/players/{self.slug}.png"

    @property
    def experience_display(self) -> str:
        if not self.experience:
            return ""
        if self.experience == "R":
            return "Rookie"
        return f"{self.experience} Year{'s' if self.experience != '1' else ''}"

    def stat_table(self, raw: str) -> list[list[str]]:
        rows = [r.split("\t") for r in load_json(raw, []) if r]
        return rows


class Game(db.Model):
    __tablename__ = "games"
    __table_args__ = (db.Index("ix_games_week", "week", "date"),)

    id = db.Column(db.String(40), primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    week = db.Column(db.Integer, nullable=False)
    date = db.Column(db.String(12), default="", nullable=False)
    time = db.Column(db.String(24), default="", nullable=False)
    category = db.Column(db.String(8), default="", nullable=False)
    home_abbr = db.Column(db.String(4), db.ForeignKey("teams.abbr"), nullable=False)
    away_abbr = db.Column(db.String(4), db.ForeignKey("teams.abbr"), nullable=False)
    venue = db.Column(db.String(80), default="", nullable=False)
    venue_city = db.Column(db.String(60), default="", nullable=False)
    international = db.Column(db.Boolean, default=False, nullable=False)
    networks = db.Column(db.Text, default="", nullable=False)
    status = db.Column(db.String(12), default="SCHEDULED", nullable=False)
    home_score = db.Column(db.Integer, default=0, nullable=False)
    away_score = db.Column(db.Integer, default=0, nullable=False)
    home_quarters = db.Column(db.Text, default="", nullable=False)
    away_quarters = db.Column(db.Text, default="", nullable=False)
    attendance = db.Column(db.Integer, default=0, nullable=False)
    weather = db.Column(db.String(120), default="", nullable=False)

    @property
    def home(self):
        return Team.query.filter_by(abbr=self.home_abbr).first()

    @property
    def away(self):
        return Team.query.filter_by(abbr=self.away_abbr).first()

    @property
    def home_quarter_scores(self) -> list[int]:
        """Per-quarter points parsed from the JSON column (padded to 5)."""
        return quarter_scores(self.home_quarters)

    @property
    def away_quarter_scores(self) -> list[int]:
        return quarter_scores(self.away_quarters)

    @property
    def network_display(self) -> str:
        nets = load_json(self.networks, [])
        if not nets:
            return ""
        primary = nets[0]
        alias = {
            "PRIME": "Prime Video", "NBC": "NBC", "CBS": "CBS", "FOX": "FOX",
            "ESPN": "ESPN", "ABC": "ABC", "NFLN": "NFL Network",
            "NFL NETWORK": "NFL Network", "TELEMUNDO": "Telemundo",
            "UNIVERSO": "Universo", "ESPN DEPORTES": "ESPN Deportes",
            "ESPN DEPORTES ": "ESPN Deportes", "NFLGP": "NFL Game Pass",
        }
        return alias.get(primary, primary.title())

    @property
    def eastern(self) -> datetime | None:
        """Kickoff in the Eastern timezone NFL.com displays (see helper)."""
        return eastern_kickoff(self.time)

    @property
    def day_display(self) -> str:
        et = self.eastern
        if et is None:
            return "DATE TBD"
        label = et.strftime("%a").upper()
        if self.international:
            label = "INTL " + label
        return label

    @property
    def time_display(self) -> str:
        et = self.eastern
        if et is None:
            return ""
        return et.strftime("%-I:%M").lstrip("0") + et.strftime("%p").lower()

    @property
    def date_display(self) -> str:
        et = self.eastern
        if et is None:
            return ""
        return et.strftime("%B %-d").upper()

    @property
    def winner(self) -> str | None:
        if not self.status.startswith("FINAL"):
            return None
        if self.home_score > self.away_score:
            return self.home_abbr
        if self.away_score > self.home_score:
            return self.away_abbr
        return None


class NewsArticle(db.Model):
    __tablename__ = "news"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    body = db.Column(db.Text, default="", nullable=False)
    section = db.Column(db.String(60), default="", nullable=False)
    author = db.Column(db.String(80), default="NFL.com Staff", nullable=False)
    published = db.Column(db.DateTime, nullable=False)
    image_id = db.Column(db.String(40), default="", nullable=False)
    keywords = db.Column(db.Text, default="", nullable=False)

    @property
    def image(self) -> str:
        return f"/static/images/news/{self.image_id}.jpg"

    @property
    def published_display(self) -> str:
        return self.published.strftime("%b %-d, %Y at %-I:%M %p").replace("AM", "a.m.").replace("PM", "p.m.")

    @property
    def paragraphs(self) -> list[str]:
        return [p.strip() for p in self.body.split("\n") if p.strip()]


class Video(db.Model):
    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    category = db.Column(db.String(60), default="Latest Buzz", nullable=False)
    image_id = db.Column(db.String(40), default="", nullable=False)
    channel = db.Column(db.String(40), default="latest-buzz", nullable=False)

    @property
    def image(self) -> str:
        return f"/static/images/videos/{self.image_id}.jpg"


class StatLeader(db.Model):
    __tablename__ = "stat_leaders"
    __table_args__ = (db.Index("ix_stat_leaders_cat", "category", "rank"),)

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(20), nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    player_name = db.Column(db.String(80), nullable=False)
    team_abbr = db.Column(db.String(4), nullable=False)
    player_slug = db.Column(db.String(80), default="", nullable=False)
    stats = db.Column(db.Text, default="{}", nullable=False)

    @property
    def stat_map(self) -> dict:
        return load_json(self.stats, {})


class Injury(db.Model):
    __tablename__ = "injuries"

    id = db.Column(db.Integer, primary_key=True)
    game_date = db.Column(db.String(40), default="", nullable=False)
    matchup = db.Column(db.String(80), default="", nullable=False)
    team = db.Column(db.String(40), default="", nullable=False)
    player = db.Column(db.String(80), nullable=False)
    position = db.Column(db.String(8), default="", nullable=False)
    injury = db.Column(db.String(80), default="", nullable=False)
    practice_status = db.Column(db.String(80), default="", nullable=False)
    game_status = db.Column(db.String(20), default="", nullable=False)


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(20), nullable=False)
    team = db.Column(db.String(40), default="", nullable=False)
    to_team = db.Column(db.String(40), default="", nullable=False)
    date = db.Column(db.String(10), default="", nullable=False)
    name = db.Column(db.String(80), nullable=False)
    position = db.Column(db.String(8), default="", nullable=False)
    transaction = db.Column(db.String(120), default="", nullable=False)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(64), nullable=False)
    display_name = db.Column(db.String(60), nullable=False)
    username = db.Column(db.String(40), default="", nullable=False)
    favorite_team = db.Column(db.String(4), default="", nullable=False)
    newsletter = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_DATE, nullable=False)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = stable_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return hmac.compare_digest(self.password_hash, stable_password_hash(raw_password))

    @property
    def subscription(self) -> "Subscription | None":
        return Subscription.query.filter_by(user_id=self.id, status="active").order_by(Subscription.id.desc()).first()


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    plan_code = db.Column(db.String(40), nullable=False)
    plan_title = db.Column(db.String(80), nullable=False)
    cycle = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(12), default="active", nullable=False)
    started_at = db.Column(db.DateTime, default=MIRROR_DATE, nullable=False)
    renews_at = db.Column(db.DateTime, nullable=False)


class PlusOrder(db.Model):
    __tablename__ = "plus_orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    order_ref = db.Column(db.String(20), unique=True, nullable=False)
    plan_code = db.Column(db.String(40), nullable=False)
    plan_title = db.Column(db.String(80), nullable=False)
    cycle = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    tax = db.Column(db.Float, default=0.0, nullable=False)
    total = db.Column(db.Float, nullable=False)
    card_last4 = db.Column(db.String(4), nullable=False)
    cardholder = db.Column(db.String(80), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_DATE, nullable=False)
    status = db.Column(db.String(12), default="complete", nullable=False)


class NewsletterSignup(db.Model):
    __tablename__ = "newsletter_signups"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    team_abbr = db.Column(db.String(4), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_DATE, nullable=False)


@login_manager.user_loader
def load_user(user_id: int) -> User | None:
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------------- #
# Template helpers / shared context
# --------------------------------------------------------------------------- #

@app.context_processor
def inject_chrome() -> dict:
    ribbon_games = (
        Game.query.filter_by(week=CURRENT_WEEK)
        .order_by(Game.date, Game.time)
        .all()
    )
    news_headlines = NewsArticle.query.order_by(NewsArticle.published.desc()).limit(6).all()
    return {
        "ribbon_games": ribbon_games,
        "chrome_headlines": news_headlines,
        "all_teams": Team.query.order_by(Team.conference, Team.full_name).all(),
        "stat_categories": STAT_CATEGORIES,
        "current_week": CURRENT_WEEK,
    }


@app.template_filter("ordinal")
def ordinal(value: int) -> str:
    value = int(value)
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def game_slug(away: Team, home: Team, week: int) -> str:
    return f"{slugify(away.nickname)}-at-{slugify(home.nickname)}-2026-reg-{week}"


def parse_card(number: str) -> dict:
    digits = re.sub(r"\D", "", number or "")
    brand = ""
    if digits.startswith("4"):
        brand = "Visa"
    elif digits[:2] in {"51", "52", "53", "54", "55"}:
        brand = "Mastercard"
    elif digits.startswith("34") or digits.startswith("37"):
        brand = "American Express"
    elif digits[:2] in {"60", "65"} or digits.startswith("6011"):
        brand = "Discover"
    valid_len = 15 if brand == "American Express" else 16
    return {
        "digits": digits,
        "brand": brand,
        "last4": digits[-4:] if len(digits) >= 4 else "",
        "valid": len(digits) == valid_len and brand != "",
    }


def luhn_ok(digits: str) -> bool:
    if not digits.isdigit():
        return False
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


# --------------------------------------------------------------------------- #
# Public routes
# --------------------------------------------------------------------------- #


# Mutating forms use per-session CSRF tokens; redirects stay on this site.
def csrf_token():
    import secrets
    from flask import session
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def protect_forms():
    import hmac
    from flask import session
    if request.method == "POST":
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(expected, supplied):
            abort(400, "Invalid form token. Reload the page and try again.")


def safe_redirect_target(value, fallback):
    from urllib.parse import urlsplit
    value = value or ""
    parts = urlsplit(value)
    if (value.startswith("/") and not value.startswith("//") and
            "\\" not in value and not parts.netloc and not parts.scheme and
            not any(ord(c) < 32 for c in value)):
        return value
    return fallback


@app.route("/")
def index():
    top_story = NewsArticle.query.order_by(NewsArticle.published.desc()).first()
    headlines = (
        NewsArticle.query.order_by(NewsArticle.published.desc())
        .offset(1).limit(7).all()
    )
    videos = Video.query.order_by(Video.id).limit(6).all()
    week_games = (
        Game.query.filter_by(week=CURRENT_WEEK)
        .order_by(Game.date, Game.time).all()
    )
    divisions = {}
    for t in Team.query.order_by(Team.conference, Team.division, Team.division_rank).all():
        divisions.setdefault((t.conference, t.division), []).append(t)
    fav = current_user.favorite_team if current_user.is_authenticated else ""
    fav_team = Team.query.filter_by(abbr=fav).first() if fav else None
    fav_game = None
    if fav_team:
        fav_game = (
            Game.query.filter_by(week=CURRENT_WEEK)
            .filter((Game.home_abbr == fav) | (Game.away_abbr == fav))
            .first()
        )
    return render_template(
        "index.html",
        top_story=top_story,
        headlines=headlines,
        videos=videos,
        week_games=week_games,
        divisions=divisions,
        fav_team=fav_team,
        fav_game=fav_game,
    )


@app.route("/scores/")
@app.route("/scores/2026/REG<int:week>/")
def scores(week: int | None = None):
    week = week if week is not None else CURRENT_WEEK
    if not 1 <= int(week) <= 18:
        abort(404)
    games = (
        Game.query.filter_by(week=int(week))
        .order_by(Game.date, Game.time).all()
    )
    return render_template("scores.html", week=int(week), games=games)


@app.route("/games/<slug>/")
def game_detail(slug: str):
    game = Game.query.filter_by(slug=slug).first_or_404()
    home, away = game.home, game.away
    glance = []
    for label, hval, aval in (
        ("POINTS PER GAME", round(home.points_for / max(home.wins + home.losses + home.ties, 1)),
         round(away.points_for / max(away.wins + away.losses + away.ties, 1))),
        ("TOTAL POINTS", home.points_for, away.points_for),
        ("POINTS ALLOWED", home.points_against, away.points_against),
    ):
        glance.append({"label": label, "home": hval, "away": aval})
    glance.sort(key=lambda row: -(row["home"] + row["away"]))
    for row in glance:
        if row["home"] > row["away"]:
            row["home_leads"] = True
        elif row["away"] > row["home"]:
            row["away_leads"] = True

    def leaders(team_abbr: str) -> list[dict]:
        out = []
        for cat, label in (("passing", "PASSING"), ("rushing", "RUSHING"), ("receiving", "RECEIVING")):
            row = (
                StatLeader.query.filter_by(category=cat, team_abbr=team_abbr)
                .order_by(StatLeader.rank).first()
            )
            if row:
                out.append({"label": label, "leader": row})
        return out

    home_injuries = Injury.query.filter(Injury.matchup.contains(home.nickname)).filter_by(team=home.nickname).all()
    away_injuries = Injury.query.filter(Injury.matchup.contains(away.nickname)).filter_by(team=away.nickname).all()
    return render_template(
        "game.html",
        game=game,
        home=home,
        away=away,
        glance=glance,
        home_leaders=leaders(home.abbr),
        away_leaders=leaders(away.abbr),
        home_injuries=home_injuries,
        away_injuries=away_injuries,
    )


@app.route("/standings/")
def standings():
    divisions: dict[tuple, list] = {}
    for t in Team.query.order_by(Team.conference, Team.division, Team.division_rank).all():
        divisions.setdefault((t.conference, t.division), []).append(t)
    afc = sorted(
        Team.query.filter_by(conference="AFC").all(),
        key=lambda t: (-t.wins, -t.points_for),
    )
    nfc = sorted(
        Team.query.filter_by(conference="NFC").all(),
        key=lambda t: (-t.wins, -t.points_for),
    )
    return render_template("standings.html", divisions=divisions, afc=afc, nfc=nfc)


@app.route("/teams/")
def teams():
    afc = {}
    nfc = {}
    for t in Team.query.order_by(Team.full_name).all():
        (afc if t.conference == "AFC" else nfc).setdefault(t.division, []).append(t)
    return render_template("teams.html", afc=afc, nfc=nfc)


@app.route("/teams/<slug>/")
def team_detail(slug: str):
    team = Team.query.filter_by(slug=slug).first_or_404()
    played = (
        Game.query.filter(Game.status.like("FINAL%"))
        .filter((Game.home_abbr == team.abbr) | (Game.away_abbr == team.abbr))
        .order_by(Game.week).all()
    )
    upcoming = (
        Game.query.filter_by(status="SCHEDULED")
        .filter((Game.home_abbr == team.abbr) | (Game.away_abbr == team.abbr))
        .order_by(Game.week).limit(5).all()
    )
    news = NewsArticle.query.filter(NewsArticle.keywords.contains(team.nickname)).order_by(
        NewsArticle.published.desc()).limit(4).all()
    videos = Video.query.filter(Video.description.contains(team.nickname)).limit(3).all()
    return render_template(
        "team.html", team=team, played=played, upcoming=upcoming,
        news=news, videos=videos,
    )


@app.route("/teams/<slug>/roster/")
def team_roster(slug: str):
    team = Team.query.filter_by(slug=slug).first_or_404()
    pos = request.args.get("position", "")
    status = request.args.get("status", "")
    query = Player.query.filter_by(team_abbr=team.abbr)
    if pos:
        query = query.filter_by(pos=pos.upper())
    if status:
        query = query.filter_by(status=status.upper())
    players = query.order_by(Player.pos, Player.number).all()
    counts = {}
    for p in Player.query.filter_by(team_abbr=team.abbr).all():
        counts[p.pos] = counts.get(p.pos, 0) + 1
    return render_template(
        "roster.html", team=team, players=players, pos=pos, status=status,
        counts=sorted(counts.items()),
    )


@app.route("/teams/<slug>/schedule/")
def team_schedule(slug: str):
    team = Team.query.filter_by(slug=slug).first_or_404()
    games = (
        Game.query.filter((Game.home_abbr == team.abbr) | (Game.away_abbr == team.abbr))
        .order_by(Game.week).all()
    )
    return render_template("team_schedule.html", team=team, games=games)


@app.route("/players/")
@app.route("/players/active/all")
def players_directory():
    q = request.args.get("query", "").strip()
    pos = request.args.get("position", "")
    team = request.args.get("team", "")
    query = Player.query
    if pos:
        query = query.filter_by(pos=pos.upper())
    if team:
        query = query.filter_by(team_abbr=team.upper())
    all_players = query.order_by(Player.name).all()
    results = scored_search(q, all_players, ["name", "college", "pos"]) if q else all_players
    return render_template(
        "players.html", results=results[:80], total=len(results),
        q=q, pos=pos, team=team,
    )


@app.route("/players/<slug>/")
def player_detail(slug: str):
    player = Player.query.filter_by(slug=slug).first_or_404()
    team = player.team
    related = []
    if team:
        related = (
            NewsArticle.query.filter(NewsArticle.keywords.contains(player.name))
            .order_by(NewsArticle.published.desc()).limit(3).all()
        )
    recent = [r.split("\t") for r in load_json(player.recent_games, []) if r and r != "HEADER"]
    career = [r.split("\t") for r in load_json(player.career, []) if r and r != "HEADER"]
    return render_template(
        "player.html", player=player, team=team,
        related=related, recent=recent, career=career,
    )


@app.route("/news/")
def news_index():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 12
    total = NewsArticle.query.count()
    articles = (
        NewsArticle.query.order_by(NewsArticle.published.desc())
        .offset((page - 1) * per_page).limit(per_page).all()
    )
    return render_template(
        "news.html", articles=articles, page=page,
        pages=(total + per_page - 1) // per_page, total=total,
    )


@app.route("/news/<slug>/")
def article_detail(slug: str):
    article = NewsArticle.query.filter_by(slug=slug).first_or_404()
    related = (
        NewsArticle.query.filter(NewsArticle.id != article.id)
        .order_by(NewsArticle.published.desc()).limit(4).all()
    )
    return render_template("article.html", article=article, related=related)


@app.route("/videos/")
@app.route("/videos/channel/<channel>/")
def videos_index(channel: str = "latest-buzz"):
    channel_names = {
        "latest-buzz": "Latest Buzz",
        "game-highlights": "Game Highlights",
        "the-insiders": "The Insiders",
        "good-morning-football": "Good Morning Football",
    }
    if channel not in channel_names:
        abort(404)
    vids = Video.query.filter_by(channel=channel).order_by(Video.id).all()
    return render_template(
        "videos.html", videos=vids, channel=channel,
        channel_name=channel_names[channel],
        channel_names=channel_names,
    )


@app.route("/videos/<slug>/")
def video_detail(slug: str):
    if slug.startswith("channel"):
        return redirect(url_for("videos_index"))
    video = Video.query.filter_by(slug=slug).first_or_404()
    related = Video.query.filter(Video.id != video.id).filter_by(channel=video.channel).limit(6).all()
    return render_template("video.html", video=video, related=related)


@app.route("/stats/")
def stats_landing():
    featured = {}
    for cat, label in STAT_CATEGORIES[:3]:
        featured[cat] = StatLeader.query.filter_by(category=cat).order_by(StatLeader.rank).limit(5).all()
    return render_template("stats.html", featured=featured)


@app.route("/stats/<category>/")
def stats_category(category: str):
    if category not in dict(STAT_CATEGORIES):
        abort(404)
    leaders = StatLeader.query.filter_by(category=category).order_by(StatLeader.rank).all()
    if not leaders:
        abort(404)
    columns = list(leaders[0].stat_map.keys())
    return render_template(
        "stats_category.html", category=category,
        label=dict(STAT_CATEGORIES)[category],
        leaders=leaders, columns=columns,
    )


@app.route("/injuries/")
def injuries():
    rows = Injury.query.order_by(Injury.id).all()
    by_matchup: dict[str, list] = {}
    for r in rows:
        by_matchup.setdefault(r.matchup, []).append(r)
    matchups = [
        {"matchup": m, "game_date": rows_[0].game_date, "rows": rows_}
        for m, rows_ in by_matchup.items()
    ]
    return render_template("injuries.html", matchups=matchups)


@app.route("/transactions/")
def transactions():
    cat = request.args.get("category", "Signings")
    cats = ["Trades", "Signings", "Reserve List", "Waivers", "Terminations", "Other"]
    if cat not in cats:
        cat = "Signings"
    rows = Transaction.query.filter_by(category=cat).order_by(Transaction.id).all()
    return render_template("transactions.html", rows=rows, cat=cat, cats=cats)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    players, teams, news, vids = [], [], [], []
    if q:
        players = scored_search(q, Player.query.all(), ["name", "college", "pos"])[:8]
        teams = scored_search(q, Team.query.all(), ["full_name", "location", "nickname", "abbr"])[:8]
        news = scored_search(q, NewsArticle.query.all(), ["title", "description", "body"])[:8]
        vids = scored_search(q, Video.query.all(), ["title", "description"])[:6]
    return render_template(
        "search.html", q=q, players=players, teams=teams, news=news, videos=vids,
    )


# --------------------------------------------------------------------------- #
# NFL+ plans and the subscription checkout chain
# --------------------------------------------------------------------------- #

PLUS_PLANS = {
    "nfl_plus_monthly": {
        "code": "nfl_plus_monthly", "title": "NFL+ Monthly", "grant": "NFL+",
        "cycle": "month", "amount": 6.99,
        "blurb": "Live local and prime-time games on mobile, live out-of-market preseason games, live game audio, and NFL Network.",
    },
    "nfl_plus_annual": {
        "code": "nfl_plus_annual", "title": "NFL+ Annual", "grant": "NFL+",
        "cycle": "year", "amount": 49.99,
        "blurb": "Everything in NFL+ Monthly, billed once per year.",
    },
    "nfl_plus_premium_monthly": {
        "code": "nfl_plus_premium_monthly", "title": "NFL+ Premium Monthly", "grant": "NFL_PLUS_PREMIUM",
        "cycle": "month", "amount": 14.99,
        "blurb": "NFL RedZone, full game replays, condensed games, Coaches Film, and everything in NFL+.",
    },
    "nfl_plus_premium_annual": {
        "code": "nfl_plus_premium_annual", "title": "NFL+ Premium Annual", "grant": "NFL_PLUS_PREMIUM",
        "cycle": "year", "amount": 99.99,
        "blurb": "Everything in NFL+ Premium, billed once per year.",
    },
}


@app.route("/plus/")
def plus():
    return render_template("plus.html", plans=PLUS_PLANS)


@app.route("/plus/subscribe/<code>/", methods=["GET", "POST"])
def plus_subscribe(code: str):
    plan = PLUS_PLANS.get(code)
    if not plan:
        abort(404)
    if request.method == "GET" and not current_user.is_authenticated:
        return render_template("subscribe_auth.html", plan=plan)
    if request.method == "POST" and not current_user.is_authenticated:
        flash("Please sign in or create an account before checkout.")
        return render_template("subscribe_auth.html", plan=plan)

    if request.method == "POST":
        cardholder = request.form.get("cardholder", "").strip()
        number = request.form.get("card_number", "").strip()
        exp_month = request.form.get("exp_month", "").strip()
        exp_year = request.form.get("exp_year", "").strip()
        cvv = request.form.get("cvv", "").strip()
        card = parse_card(number)
        errors = []
        if len(cardholder) < 3:
            errors.append("Enter the name on the card.")
        if not card["valid"]:
            errors.append("Enter a valid Visa, Mastercard, American Express, or Discover card number.")
        elif not luhn_ok(card["digits"]):
            errors.append("That card number failed validation.")
        if not (exp_month.isdigit() and 1 <= int(exp_month) <= 12):
            errors.append("Enter a valid expiration month (1-12).")
        if not (exp_year.isdigit() and len(exp_year) in (2, 4)):
            errors.append("Enter a valid expiration year.")
        if exp_year.isdigit() and len(exp_year) in (2, 4) and exp_month.isdigit():
            year = int(exp_year) + (2000 if len(exp_year) == 2 else 0)
            if (year, int(exp_month)) < (MIRROR_DATE.year, MIRROR_DATE.month):
                errors.append("This card has expired.")
        if not (cvv.isdigit() and 3 <= len(cvv) <= 4):
            errors.append("Enter the 3- or 4-digit security code.")
        if errors:
            for e in errors:
                flash(e)
            return render_template("subscribe.html", plan=plan, form=request.form)

        existing = current_user.subscription
        if existing:
            existing.status = "cancelled"

        amount = plan["amount"]
        tax = round(amount * 0.0895, 2)
        total = round(amount + tax, 2)
        ref = "NFL-" + hashlib.sha256(
            f"{current_user.id}:{code}:{MIRROR_DATE}".encode()
        ).hexdigest()[:6].upper()
        original_ref = ref
        suffix = 2
        while PlusOrder.query.filter_by(order_ref=ref).first():
            ref = f"{original_ref}-{suffix}"
            suffix += 1
        order = PlusOrder(
            user_id=current_user.id,
            order_ref=ref,
            plan_code=code,
            plan_title=plan["title"],
            cycle=plan["cycle"],
            amount=amount,
            tax=tax,
            total=total,
            card_last4=card["last4"],
            cardholder=cardholder,
        )
        if plan["cycle"] == "year":
            renews = MIRROR_DATE + timedelta(days=365)
        else:
            renews = MIRROR_DATE + timedelta(days=30)
        sub = Subscription(
            user_id=current_user.id,
            plan_code=code,
            plan_title=plan["title"],
            cycle=plan["cycle"],
            amount=amount,
            renews_at=renews,
        )
        db.session.add(order)
        db.session.add(sub)
        db.session.commit()
        return redirect(url_for("plus_confirm", ref=ref))

    return render_template("subscribe.html", plan=plan, form={})


@app.route("/plus/confirmation/<ref>/")
@login_required
def plus_confirm(ref: str):
    order = PlusOrder.query.filter_by(order_ref=ref, user_id=current_user.id).first_or_404()
    return render_template("subscribe_confirm.html", order=order, plan=PLUS_PLANS[order.plan_code])


@app.route("/account/cancel-subscription/", methods=["POST"])
@login_required
def cancel_subscription():
    sub = current_user.subscription
    if sub:
        sub.status = "cancelled"
        db.session.commit()
        flash("Your NFL+ subscription was cancelled. Access continues until the end of the billing period.")
    return redirect(url_for("account"))


# --------------------------------------------------------------------------- #
# Auth & account
# --------------------------------------------------------------------------- #

@app.route("/account/signup/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        display = request.form.get("display_name", "").strip()
        favorite = request.form.get("favorite_team", "").strip().upper()
        errors = []
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if not display:
            errors.append("Enter your name.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with that email already exists. Sign in instead.")
        if errors:
            for e in errors:
                flash(e)
            return render_template("register.html", form=request.form)
        user = User(
            email=email,
            display_name=display,
            username=email.split("@")[0],
            favorite_team=favorite if Team.query.filter_by(abbr=favorite).first() else "",
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome to NFL.com.")
        return redirect(safe_redirect_target(request.args.get("next"), url_for("account")))
    return render_template("register.html", form={})


@app.route("/account/signin/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Email or password is incorrect.")
            return render_template("login.html", form=request.form)
        login_user(user)
        return redirect(safe_redirect_target(request.args.get("next"), url_for("account")))
    return render_template("login.html", form={})


@app.route("/account/signout/", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/account/")
@login_required
def account():
    orders = PlusOrder.query.filter_by(user_id=current_user.id).order_by(PlusOrder.created_at.desc()).all()
    sub = current_user.subscription
    return render_template("account.html", sub=sub, orders=orders)


@app.route("/account/edit/", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        display = request.form.get("display_name", "").strip()
        favorite = request.form.get("favorite_team", "").strip().upper()
        newsletter = request.form.get("newsletter") == "on"
        password = request.form.get("new_password", "")
        if not display:
            flash("Display name cannot be empty.")
        else:
            current_user.display_name = display
            if favorite and Team.query.filter_by(abbr=favorite).first():
                current_user.favorite_team = favorite
            else:
                current_user.favorite_team = ""
            current_user.newsletter = newsletter
            if password:
                if len(password) < 8:
                    flash("New password must be at least 8 characters.")
                    return redirect(url_for("account_edit"))
                current_user.set_password(password)
            db.session.commit()
            flash("Profile updated.")
            return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/newsletter/", methods=["POST"])
def newsletter():
    email = request.form.get("email", "").strip().lower()
    team_abbr = request.form.get("team", "").strip().upper()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        flash("Enter a valid email address to sign up for the newsletter.")
        return redirect(url_for("index"))
    db.session.add(NewsletterSignup(
        email=email,
        team_abbr=team_abbr if Team.query.filter_by(abbr=team_abbr).first() else "",
    ))
    db.session.commit()
    flash("You're signed up for the NFL newsletter.")
    return redirect(url_for("index"))


# --------------------------------------------------------------------------- #
# Health + errors
# --------------------------------------------------------------------------- #

@app.route("/_health")
def health():
    return {
        "ok": True,
        "site": SITE_SLUG,
        "teams": Team.query.count(),
        "players": Player.query.count(),
        "games": Game.query.count(),
        "news": NewsArticle.query.count(),
    }


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #

def create_schema() -> None:
    """Create tables + indexes deterministically (see jcpenney rationale)."""
    detached: list[tuple[str, object]] = []
    for table in db.metadata.sorted_tables:
        for index in list(table.indexes):
            detached.append((table.name, index))
            table.indexes.discard(index)
    try:
        db.create_all()
        from sqlalchemy import inspect
        from sqlalchemy.schema import CreateIndex
        inspector = inspect(db.engine)
        existing = {
            (table_name, index["name"])
            for table_name in inspector.get_table_names()
            for index in inspector.get_indexes(table_name)
        }
        with db.engine.begin() as connection:
            for table_name, index in sorted(detached, key=lambda pair: (pair[0], pair[1].name)):
                if (table_name, index.name) not in existing:
                    connection.execute(CreateIndex(index))
    finally:
        for table_name, index in detached:
            table = db.metadata.tables[table_name]
            if index not in table.indexes:
                table.indexes.add(index)


BOOTSTRAP = os.environ.get("WEBSYN_SKIP_BOOTSTRAP") != "1"

if BOOTSTRAP:
    with app.app_context():
        create_schema()
        try:
            from seed_data import seed_database, seed_benchmark_users
            seed_database()
            seed_benchmark_users()
        except ImportError:
            pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 43083))
    app.run(host="0.0.0.0", port=port, debug=False)
