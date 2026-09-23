"""League of Legends mirror — Flask app (WebHarbor contributor track).

Functional mirror of https://www.leagueoflegends.com/ (snapshot 2026-09-22):
riotbar navigation, homepage hero with real splash art, the 173-champion
roster with search/role/difficulty filters, champion detail pages with
abilities and skin splashes, the News hub with category pages and paginated
article grid, full article pages (patch notes rich text included), a
patch-notes listing, the game-overview page, site-wide scored search, and a
Riot-account surface: signup, login, account dashboard with favorite
champions and bookmarked articles.

Seed data is materialized deterministically from the tracked source_data.json
by seed_data.py (see .build-generated-seed).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime
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

SITE_SLUG = "league_of_legends"
SITE_NAME = "League of Legends"
BENCHMARK_PASSWORD = "TestPass123!"
MIRROR_DATE = datetime(2026, 9, 22)
MIRROR_DATE_STR = "2026-09-22"
BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
SEED_DIR = BASE_DIR / "instance_seed"
IMAGE_DIR = BASE_DIR / "static" / "images"
RUNTIME_DB_PATH = INSTANCE_DIR / "league_of_legends.db"
SEED_DB_PATH = SEED_DIR / "league_of_legends.db"
# Test harness hook: point the app at a scratch DB (see tests/conftest.py).
DB_URI_OVERRIDE = os.environ.get("LOL_DB_PATH", "")
PASSWORD_NAMESPACE = "lol-webharbor-demo"
NAV_CATEGORIES = [
    ("game-updates", "Game Updates"),
    ("patch-notes", "Patch Notes"),
    ("dev", "Dev"),
    ("esports", "Esports"),
    ("community", "Community"),
    ("media", "Media"),
    ("merch", "Merch"),
    ("lore", "Lore"),
    ("riot_games", "Riot Games"),
    ("announcements", "Announcements"),
]
ROLES = ("Fighter", "Assassin", "Mage", "Marksman", "Support", "Tank")
DIFFICULTIES = ("Low", "Medium", "High")
REGIONS = ("NA", "EUW", "EUNE", "KR", "BR", "JP", "LAN", "LAS", "OCE", "TR", "RU")
NEWS_PAGE_SIZE = 24


def _ensure_dirs() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)


_ensure_dirs()

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config["SECRET_KEY"] = "league-of-legends-demo-session-key"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    DB_URI_OVERRIDE if DB_URI_OVERRIDE.startswith("sqlite:///")
    else f"sqlite:///{RUNTIME_DB_PATH}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to your Riot Account to continue."


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


def slugify(value: str) -> str:
    cleaned: list[str] = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    return "".join(cleaned).strip("-")


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #

class Champion(db.Model):
    __tablename__ = "champions"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    epithet = db.Column(db.String(200))
    roles = db.Column(db.String(200))
    difficulty_name = db.Column(db.String(40))
    difficulty_value = db.Column(db.Integer)
    lore = db.Column(db.Text)
    release_key = db.Column(db.Integer, nullable=False, default=0)
    portrait = db.Column(db.String(300))
    splash = db.Column(db.String(300))

    abilities = db.relationship(
        "Ability", back_populates="champion",
        order_by="Ability.sort", cascade="all, delete-orphan")
    skins = db.relationship(
        "Skin", back_populates="champion",
        order_by="Skin.num", cascade="all, delete-orphan")

    @property
    def role_list(self) -> list[str]:
        return load_json(self.roles, [])

    @property
    def primary_role(self) -> str:
        roles = self.role_list
        return roles[0] if roles else ""

    @property
    def portrait_url(self) -> str:
        return url_for("static", filename=f"images/{self.portrait}")

    @property
    def splash_url(self) -> str:
        return url_for("static", filename=f"images/{self.splash}")

    def search_blob(self) -> str:
        skin_names = " ".join(skin.name for skin in self.skins)
        return " ".join([
            self.name or "", self.epithet or "", self.roles or "",
            skin_names,
            re.sub(r"<[^>]+>", " ", self.lore or ""),
        ]).lower()


class Ability(db.Model):
    __tablename__ = "abilities"
    id = db.Column(db.Integer, primary_key=True)
    champion_id = db.Column(
        db.Integer, db.ForeignKey("champions.id"), nullable=False)
    slot = db.Column(db.String(4), nullable=False)
    slot_label = db.Column(db.String(40))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(300))
    poster = db.Column(db.String(300))
    sort = db.Column(db.Integer, nullable=False, default=0)

    champion = db.relationship("Champion", back_populates="abilities")

    @property
    def icon_url(self) -> str:
        return url_for("static", filename=f"images/{self.icon}")

    @property
    def poster_url(self) -> str:
        return url_for("static", filename=f"images/{self.poster}") if self.poster else ""


class Skin(db.Model):
    __tablename__ = "skins"
    id = db.Column(db.Integer, primary_key=True)
    champion_id = db.Column(
        db.Integer, db.ForeignKey("champions.id"), nullable=False)
    num = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    splash = db.Column(db.String(300))

    champion = db.relationship("Champion", back_populates="skins")

    @property
    def splash_url(self) -> str:
        return url_for("static", filename=f"images/{self.splash}")

    @property
    def is_base(self) -> bool:
        return self.num == 0


class ArticleCategory(db.Model):
    __tablename__ = "article_categories"
    id = db.Column(db.Integer, primary_key=True)
    machine_name = db.Column(db.String(60), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(400))

    articles = db.relationship(
        "Article", back_populates="category", lazy="dynamic")

    @property
    def path(self) -> str:
        return f"/news/{self.machine_name}/"


class Article(db.Model):
    __tablename__ = "articles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    category_id = db.Column(
        db.Integer, db.ForeignKey("article_categories.id"), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    summary = db.Column(db.Text)
    banner = db.Column(db.String(300))
    publish_date = db.Column(db.String(40), nullable=False)
    authors = db.Column(db.Text)
    tags = db.Column(db.Text)
    body_html = db.Column(db.Text)
    related = db.Column(db.Text)
    external_url = db.Column(db.String(500))
    is_patch_note = db.Column(db.Integer, nullable=False, default=0)

    category = db.relationship("ArticleCategory", back_populates="articles")

    @property
    def is_external(self) -> bool:
        return bool(self.external_url)

    @property
    def path(self) -> str:
        if self.external_url:
            return self.external_url
        return f"/news/{self.category.machine_name}/{self.slug}/"

    @property
    def banner_url(self) -> str:
        return url_for("static", filename=f"images/{self.banner}") if self.banner else ""

    @property
    def card(self) -> str:
        """Grid/card image path (banner-derived for internal articles)."""
        if not self.banner:
            return ""
        if self.banner.endswith("_banner.jpg"):
            return self.banner[:-len("_banner.jpg")] + "_card.jpg"
        return self.banner

    @property
    def card_url(self) -> str:
        return url_for("static", filename=f"images/{self.card}") if self.card else ""

    @property
    def author_list(self) -> list[str]:
        return load_json(self.authors, [])

    @property
    def tag_list(self) -> list[str]:
        return load_json(self.tags, [])

    @property
    def related_list(self) -> list[dict]:
        return load_json(self.related, [])

    @property
    def byline(self) -> str:
        authors = self.author_list
        return ", ".join(authors) if authors else "Riot Games"

    @property
    def display_date(self) -> str:
        return self.publish_date[:10]

    def search_blob(self) -> str:
        return " ".join([
            self.title or "", self.summary or "",
            self.category.title if self.category else "",
        ]).lower()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    summoner_name = db.Column(db.String(60))
    region = db.Column(db.String(10))
    password_hash = db.Column(db.String(120), nullable=False)
    joined_date = db.Column(db.String(40))

    favorites = db.relationship(
        "FavoriteChampion", back_populates="user",
        cascade="all, delete-orphan", lazy="dynamic")
    bookmarks = db.relationship(
        "BookmarkArticle", back_populates="user",
        cascade="all, delete-orphan", lazy="dynamic")

    def set_password(self, raw_password: str) -> None:
        self.password_hash = stable_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return self.password_hash == stable_password_hash(raw_password)

    def favorite_champions(self):
        return [
            row.champion for row in
            self.favorites.join(Champion, FavoriteChampion.champion_id == Champion.id)
            .order_by(Champion.name)
            .all()]

    def bookmarked_articles(self):
        return [
            row.article for row in
            self.bookmarks.join(Article, BookmarkArticle.article_id == Article.id)
            .order_by(Article.publish_date.desc())
            .all()]


class FavoriteChampion(db.Model):
    __tablename__ = "favorite_champions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    champion_id = db.Column(db.Integer, db.ForeignKey("champions.id"), nullable=False)
    added_date = db.Column(db.String(40))

    user = db.relationship("User", back_populates="favorites")
    champion = db.relationship("Champion")

    __table_args__ = (db.UniqueConstraint("user_id", "champion_id"),)


class BookmarkArticle(db.Model):
    __tablename__ = "bookmark_articles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    added_date = db.Column(db.String(40))

    user = db.relationship("User", back_populates="bookmarks")
    article = db.relationship("Article")

    __table_args__ = (db.UniqueConstraint("user_id", "article_id"),)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return User.query.get(int(user_id))


# --------------------------------------------------------------------------- #
# Template filters + globals
# --------------------------------------------------------------------------- #

@app.template_filter("safehtml")
def safehtml_filter(value: str) -> Markup:
    return Markup(value or "")


@app.template_filter("inlinehtml")
def inlinehtml_filter(value: str) -> Markup:
    return sanitize_inline_html(value)


@app.template_filter("daymonth")
def daymonth_filter(value: str) -> str:
    # "2026-09-22T18:00:00.000Z" -> "9/22/2026" (upstream card format)
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    if not match:
        return (value or "")[:10]
    year, month, day = match.groups()
    return f"{int(month)}/{int(day)}/{year}"


def sanitize_inline_html(value: str) -> Markup:
    """Allow only benign inline formatting tags from upstream copy."""
    text = value or ""
    text = re.sub(r"<(script|style|iframe|object|embed)[^>]*>.*?</\1>", "", text, flags=re.I | re.S)
    text = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^>\s]+)", "", text, flags=re.I)
    text = re.sub(r"javascript:", "", text, flags=re.I)
    allowed = {"i", "b", "em", "strong", "u", "br", "span", "p", "a"}

    def repl(match: re.Match) -> str:
        return match.group(0) if match.group(1).lower() in allowed else ""

    text = re.sub(r"</?\s*([a-zA-Z][a-zA-Z0-9]*)[^>]*>", repl, text)
    return Markup(text)


def csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = hashlib.sha1(os.urandom(16)).hexdigest()
    return session["_csrf"]


def validate_csrf() -> None:
    token = request.form.get("_csrf", "")
    if not token or token != session.get("_csrf"):
        abort(400, "Invalid request token.")


@app.before_request
def csrf_guard() -> None:
    if request.method == "POST":
        validate_csrf()


def form_string(name: str, default: str = "", limit: int = 200) -> str:
    value = (request.form.get(name) or "").strip()
    return value[:limit] if value else default


@app.context_processor
def inject_global_context() -> dict[str, Any]:
    champion_count = 0
    try:
        champion_count = Champion.query.count()
    except Exception:
        pass
    return {
        "site_name": SITE_NAME,
        "nav_categories": NAV_CATEGORIES,
        "champion_count": champion_count,
        "csrf_token": csrf_token,
        "MIRROR_DATE_STR": MIRROR_DATE_STR,
    }


# --------------------------------------------------------------------------- #
# Search (token-overlap scoring; never strict AND)
# --------------------------------------------------------------------------- #

STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "is",
    "it", "by", "with", "how", "many", "what", "which",
}


def tokenize(query: str) -> list[str]:
    tokens = re.split(r"[^a-z0-9']+", (query or "").lower())
    return [t for t in tokens if len(t) > 1 and t not in STOP_WORDS]


def score_entity(tokens: list[str], name: str, blob: str,
                  extra_fields: list[str]) -> int:
    name_lower = (name or "").lower()
    blob_lower = (blob or "").lower()
    score = 0
    for token in tokens:
        if token in name_lower:
            score += 3
        else:
            for field in extra_fields:
                if token in (field or "").lower():
                    score += 2
                    break
            else:
                if token in blob_lower:
                    score += 1
    return score


def search_champions(query: str, limit: int = 60) -> list[tuple[Champion, int]]:
    tokens = tokenize(query)
    if not tokens:
        return []
    scored: list[tuple[Champion, int]] = []
    for champion in Champion.query.all():
        score = score_entity(
            tokens, champion.name, champion.search_blob(),
            [champion.epithet, " ".join(champion.role_list)])
        if score > 0:
            scored.append((champion, score))
    scored.sort(key=lambda pair: (-pair[1], pair[0].name))
    return scored[:limit]


def search_articles(query: str, limit: int = 60) -> list[tuple[Article, int]]:
    tokens = tokenize(query)
    if not tokens:
        return []
    scored: list[tuple[Article, int]] = []
    for article in Article.query.all():
        blob = article.search_blob()
        score = score_entity(
            tokens, article.title, blob,
            [article.category.title if article.category else "",
             " ".join(article.tag_list), " ".join(article.author_list)])
        if score > 0:
            scored.append((article, score))
    scored.sort(key=lambda pair: (-pair[1], pair[0].publish_date or "", pair[0].title))
    return scored[:limit]


# --------------------------------------------------------------------------- #
# Static / informational routes
# --------------------------------------------------------------------------- #

@app.route("/_health")
def health():
    return {"ok": True, "site": SITE_SLUG}


@app.route("/")
def home():
    latest = Article.query.order_by(Article.publish_date.desc()).limit(6).all()
    return render_template("index.html", latest=latest)


@app.route("/how-to-play/")
def how_to_play():
    return render_template("how_to_play.html")


@app.route("/pbe/")
def pbe():
    return render_template("pbe.html")


# League of Legends Classic surface. The champion roster below mirrors the
# upstream /classic/champions/ listing (snapshot 2026-09-23, 68 champions in
# upstream order); each tile links to the mirror's champion detail page.
CLASSIC_CHAMPIONS = (
    ("AHRI", "ahri"), ("AKALI", "akali"), ("ALISTAR", "alistar"),
    ("AMUMU", "amumu"), ("ANIVIA", "anivia"), ("ANNIE", "annie"),
    ("ASHE", "ashe"), ("BLITZCRANK", "blitzcrank"), ("BRAND", "brand"),
    ("CHO'GATH", "chogath"), ("CORKI", "corki"), ("DR. MUNDO", "drmundo"),
    ("EVELYNN", "evelynn"), ("EZREAL", "ezreal"), ("FIDDLESTICKS", "fiddlesticks"),
    ("FIORA", "fiora"), ("GALIO", "galio"), ("GANGPLANK", "gangplank"),
    ("GAREN", "garen"), ("GRAGAS", "gragas"), ("HEIMERDINGER", "heimerdinger"),
    ("JANNA", "janna"), ("JARVAN IV", "jarvaniv"), ("JAX", "jax"),
    ("KARTHUS", "karthus"), ("KASSADIN", "kassadin"), ("KATARINA", "katarina"),
    ("KAYLE", "kayle"), ("KENNEN", "kennen"), ("KOG'MAW", "kogmaw"),
    ("LEE SIN", "leesin"), ("LEONA", "leona"), ("LULU", "lulu"),
    ("LUX", "lux"), ("MALPHITE", "malphite"), ("MALZAHAR", "malzahar"),
    ("MASTER YI", "masteryi"), ("MISS FORTUNE", "missfortune"),
    ("MORGANA", "morgana"), ("NASUS", "nasus"), ("NIDALEE", "nidalee"),
    ("NUNU & WILLUMP", "nunu"), ("OLAF", "olaf"), ("PANTHEON", "pantheon"),
    ("POPPY", "poppy"), ("RAMMUS", "rammus"), ("RYZE", "ryze"),
    ("SHACO", "shaco"), ("SHEN", "shen"), ("SHYVANA", "shyvana"),
    ("SINGED", "singed"), ("SION", "sion"), ("SIVIR", "sivir"),
    ("SKARNER", "skarner"), ("SONA", "sona"), ("SORAKA", "soraka"),
    ("TARIC", "taric"), ("TEEMO", "teemo"), ("TRISTANA", "tristana"),
    ("TRYNDAMERE", "tryndamere"), ("TWISTED FATE", "twistedfate"),
    ("TWITCH", "twitch"), ("VAYNE", "vayne"), ("VEIGAR", "veigar"),
    ("WARWICK", "warwick"), ("WUKONG", "monkeyking"), ("XIN ZHAO", "xinzhao"),
    ("ZILEAN", "zilean"),
)

CLASSIC_FAQ = (
    ("When is League Classic launching?", "July 29, 2026 at 11:00 am PT!"),
    ("How do I access League Classic?",
     "Just download Riot Client / League of Legends."),
    ("I need help accessing my account",
     "Recover your account details to get back into your account."),
    ("How do I stay up to date with the latest League Classic news?",
     'Log in at account.riotgames.com and check the box labeled '
     '"Communications from Riot Games" in the Communications Preferences panel.'),
)


@app.route("/classic/")
def classic_landing():
    return render_template("classic.html", faq=CLASSIC_FAQ)


@app.route("/classic/champions/")
def classic_champions():
    return render_template("classic_champions.html", champions=CLASSIC_CHAMPIONS)


@app.route("/signup/", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = form_string("username", limit=40).lower()
        email = form_string("email", limit=120).lower()
        display_name = form_string("display_name", limit=60)
        summoner_name = form_string("summoner_name", limit=40)
        region = form_string("region", "NA", limit=10)
        password = request.form.get("password", "")
        errors = []
        if not re.fullmatch(r"[a-z0-9_.]{3,40}", username):
            errors.append("Username must be 3-40 characters (letters, numbers, dots, underscores).")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Enter a valid email address.")
        if len(display_name) < 2:
            errors.append("Enter a display name.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if User.query.filter_by(username=username).first():
            errors.append("That username is already taken.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with that email already exists.")
        if errors:
            for error in errors:
                flash(error)
        else:
            user = User(
                username=username, email=email, display_name=display_name,
                summoner_name=summoner_name or display_name, region=region,
                password_hash=stable_password_hash(password),
                joined_date=MIRROR_DATE_STR,
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to League of Legends! Your Riot Account is ready.")
            return redirect(url_for("account"))
    return render_template("signup.html", regions=REGIONS)




def local_return(value, fallback):
    """Keep account navigation on this mirror, including encoded URL tricks."""
    from urllib.parse import unquote, urlsplit
    value = str(value or "")
    decoded = unquote(value)
    try:
        parts = urlsplit(decoded)
    except ValueError:
        return fallback
    if (decoded.startswith("/") and not decoded.startswith("//")
            and not parts.scheme and not parts.netloc and "\\" not in decoded
            and not any(ord(c) < 32 or ord(c) == 127 for c in decoded)):
        return value
    return fallback


@app.route("/login/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = form_string("username", limit=200).lower()
        password = request.form.get("password", "")
        user = User.query.filter(
            (db.func.lower(User.username) == identifier)
            | (db.func.lower(User.email) == identifier)).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Signed in to your Riot Account.")
            return redirect(local_return(request.args.get("next"), url_for("account")))
        flash("Invalid username or password.")
    return render_template("login.html")


@app.route("/logout/", methods=["POST"])
def logout():
    logout_user()
    flash("Signed out.")
    return redirect(url_for("home"))


@app.route("/account/")
@login_required
def account():
    favorites = current_user.favorite_champions()
    bookmarks = current_user.bookmarked_articles()
    return render_template(
        "account.html", favorites=favorites, bookmarks=bookmarks)


@app.route("/account/profile", methods=["GET", "POST"])
@login_required
def account_profile():
    if request.method == "POST":
        display_name = form_string("display_name", limit=60)
        summoner_name = form_string("summoner_name", limit=40)
        region = form_string("region", current_user.region or "NA", limit=10)
        errors = []
        if len(display_name) < 2:
            errors.append("Enter a display name.")
        if summoner_name and not re.fullmatch(r"[A-Za-z0-9 _]{2,16}", summoner_name):
            errors.append("Summoner name must be 2-16 characters (letters, numbers, spaces, underscores).")
        if region not in REGIONS:
            errors.append("Choose a valid region.")
        if errors:
            for error in errors:
                flash(error)
        else:
            current_user.display_name = display_name
            current_user.summoner_name = summoner_name
            current_user.region = region
            db.session.commit()
            flash("Profile updated.")
            return redirect(url_for("account"))
    return render_template("account_profile.html", regions=REGIONS)


@app.route("/account/favorites")
@login_required
def account_favorites():
    favorites = current_user.favorite_champions()
    return render_template("account_favorites.html", favorites=favorites)


@app.route("/account/bookmarks")
@login_required
def account_bookmarks():
    bookmarks = current_user.bookmarked_articles()
    return render_template("account_bookmarks.html", bookmarks=bookmarks)


# --------------------------------------------------------------------------- #
# Champions
# --------------------------------------------------------------------------- #

@app.route("/champions/")
def champions():
    query = (request.args.get("q") or "").strip()
    role = (request.args.get("role") or "").strip()
    difficulty = (request.args.get("difficulty") or "").strip()
    sort = (request.args.get("sort") or "name").strip()
    roster = Champion.query
    if role:
        roster = roster.filter(Champion.roles.contains(f'"{role}"'))
    if difficulty:
        roster = roster.filter(Champion.difficulty_name == difficulty)
    champions_all = roster.order_by(Champion.name).all()
    if query:
        tokens = tokenize(query)
        scored = []
        for champion in champions_all:
            score = score_entity(
                tokens, champion.name, champion.search_blob(),
                [champion.epithet, " ".join(champion.role_list)])
            if score > 0:
                scored.append((champion, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0].name))
        champions_all = [pair[0] for pair in scored]
    if sort == "difficulty":
        champions_all.sort(key=lambda c: (c.difficulty_value or 0, c.name))
    elif sort == "skins":
        counts = dict(db.session.query(Skin.champion_id, db.func.count(Skin.id)).group_by(Skin.champion_id).all())
        champions_all.sort(key=lambda c: (-counts.get(c.id, 0), c.name))
    favorite_ids = set()
    if current_user.is_authenticated:
        favorite_ids = {
            row.champion_id for row in current_user.favorites.all()}
    return render_template(
        "champions.html", champions=champions_all, query=query, role=role,
        difficulty=difficulty, sort=sort, roles=ROLES,
        difficulties=DIFFICULTIES, favorite_ids=favorite_ids)


@app.route("/champions/<slug>/")
def champion_detail(slug):
    champion = Champion.query.filter_by(slug=slug).first_or_404()
    abilities = Ability.query.filter_by(champion_id=champion.id).order_by(Ability.sort).all()
    skins = Skin.query.filter_by(champion_id=champion.id).order_by(Skin.num).all()
    is_favorite = False
    if current_user.is_authenticated:
        is_favorite = FavoriteChampion.query.filter_by(
            user_id=current_user.id, champion_id=champion.id).first() is not None
    return render_template(
        "champion_detail.html", champion=champion, abilities=abilities,
        skins=skins, is_favorite=is_favorite)


@app.route("/champions/<slug>/favorite", methods=["POST"])
@login_required
def champion_favorite(slug):
    champion = Champion.query.filter_by(slug=slug).first_or_404()
    existing = FavoriteChampion.query.filter_by(
        user_id=current_user.id, champion_id=champion.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash(f"Removed {champion.name} from your favorites.")
    else:
        db.session.add(FavoriteChampion(
            user_id=current_user.id, champion_id=champion.id,
            added_date=MIRROR_DATE_STR))
        db.session.commit()
        flash(f"Added {champion.name} to your favorites.")
    return redirect(local_return(request.form.get("next"), url_for("champion_detail", slug=slug)))


# --------------------------------------------------------------------------- #
# News
# --------------------------------------------------------------------------- #

def _category_or_404(machine_name: str) -> ArticleCategory:
    category = ArticleCategory.query.filter_by(machine_name=machine_name).first()
    if not category:
        abort(404)
    return category


def _paginate(items: list, page: int, size: int = NEWS_PAGE_SIZE):
    total = len(items)
    pages = max(1, (total + size - 1) // size)
    page = min(max(1, page), pages)
    return items[(page - 1) * size: page * size], page, pages, total


@app.route("/news/")
def news():
    page = max(1, request.args.get("page", 1, type=int))
    query = Article.query.order_by(
        Article.publish_date.desc(), Article.id)
    paginated = query.paginate(page=page, per_page=NEWS_PAGE_SIZE, error_out=False)
    counts = {
        cat.machine_name: cat.articles.count()
        for cat in ArticleCategory.query.all()}
    return render_template(
        "news.html", articles=paginated.items, page=page,
        pages=paginated.pages, total=paginated.total, counts=counts,
        category=None)


@app.route("/news/<machine_name>/")
def news_category(machine_name):
    if machine_name == "patch-notes":
        return redirect(url_for("patch_notes"))
    category = _category_or_404(machine_name)
    page = max(1, request.args.get("page", 1, type=int))
    query = Article.query.filter_by(category_id=category.id).order_by(
        Article.publish_date.desc(), Article.id)
    paginated = query.paginate(page=page, per_page=NEWS_PAGE_SIZE, error_out=False)
    counts = {
        cat.machine_name: cat.articles.count()
        for cat in ArticleCategory.query.all()}
    return render_template(
        "news.html", articles=paginated.items, page=page,
        pages=paginated.pages, total=paginated.total, counts=counts,
        category=category)


@app.route("/patch-notes/")
def patch_notes():
    page = max(1, request.args.get("page", 1, type=int))
    query = Article.query.filter_by(is_patch_note=1).order_by(
        Article.publish_date.desc(), Article.id)
    paginated = query.paginate(page=page, per_page=NEWS_PAGE_SIZE, error_out=False)
    return render_template(
        "patch_notes.html", articles=paginated.items, page=page,
        pages=paginated.pages, total=paginated.total)


@app.route("/news/<machine_name>/<slug>/")
def article_detail(machine_name, slug):
    category = _category_or_404(machine_name)
    article = Article.query.filter_by(slug=slug, category_id=category.id).first_or_404()
    is_bookmarked = False
    if current_user.is_authenticated:
        is_bookmarked = BookmarkArticle.query.filter_by(
            user_id=current_user.id, article_id=article.id).first() is not None
    return render_template(
        "article_detail.html", article=article, is_bookmarked=is_bookmarked)


@app.route("/news/<machine_name>/<slug>/bookmark", methods=["POST"])
@login_required
def article_bookmark(machine_name, slug):
    category = _category_or_404(machine_name)
    article = Article.query.filter_by(slug=slug, category_id=category.id).first_or_404()
    existing = BookmarkArticle.query.filter_by(
        user_id=current_user.id, article_id=article.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash("Removed this article from your bookmarks.")
    else:
        db.session.add(BookmarkArticle(
            user_id=current_user.id, article_id=article.id,
            added_date=MIRROR_DATE_STR))
        db.session.commit()
        flash("Saved this article to your bookmarks.")
    return redirect(local_return(request.form.get("next"), url_for(
        "article_detail", machine_name=machine_name, slug=slug)))


# --------------------------------------------------------------------------- #
# Site search
# --------------------------------------------------------------------------- #

@app.route("/search")
def search():
    query = (request.args.get("q") or "").strip()
    champion_results = search_champions(query)
    article_results = search_articles(query)
    return render_template(
        "search.html", query=query,
        champion_results=champion_results,
        article_results=article_results)


# --------------------------------------------------------------------------- #
# Error pages
# --------------------------------------------------------------------------- #

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


# --------------------------------------------------------------------------- #
# Idempotent bootstrap seeding (see AGENTS.md: gate every function as a whole).
# The heavy lifting lives in seed_data.py; it early-returns on a populated DB.
# --------------------------------------------------------------------------- #

BOOTSTRAP = os.environ.get("LOL_SKIP_BOOTSTRAP") != "1"

if BOOTSTRAP:
    with app.app_context():
        db.create_all()
        try:
            from seed_data import seed_benchmark_users, seed_database
            seed_database()
            seed_benchmark_users()
        except ImportError:
            pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
