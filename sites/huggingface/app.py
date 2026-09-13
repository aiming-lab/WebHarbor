"""
Hugging Face Mirror — Full-stack Flask application.

Entity model adapted for an ML/AI developer platform:
  Repository (Model | Dataset | Space) <- Product
  Task       <- Category
  CartItem (Deployment Cart)  <- cart (with hardware choice)
  InferenceEndpoint (Order)   <- order (with endpoint_id, hourly rate, status)
  Like       <- wishlist
  Collection <- user-curated named groups of repos
  Discussion <- review/comment threads
  Follow     <- social graph (user -> author)
"""
import json
import os
import random
import re
import secrets
import string
from datetime import datetime, timedelta
from pathlib import Path

# ----------------------------------------------------------------------------
# Pinned mirror clock. The Docker image is built once and may be evaluated by
# users at any future point in time. We freeze "today" so date-relative
# WebVoyager / WebTau tasks (e.g. "released in the past month", "last updated
# in March 2023") behave deterministically regardless of wall-clock time.
# Chosen to fall just after the newest seeded updated_at (2026-04-12) so
# "past month" still matches recent uploads, while keeping every historical
# anchor (2022 NER models, March 2023 sentiment models, …) firmly in the past.
# ----------------------------------------------------------------------------
MIRROR_REFERENCE_DATE = datetime(2026, 4, 25, 12, 0, 0)


def mirror_now() -> datetime:
    return MIRROR_REFERENCE_DATE

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, TextAreaField, SelectField, IntegerField, HiddenField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional as OptionalValidator

from seed_data import (
    TASKS, MODALITIES, LIBRARIES, LICENSES, LANGUAGES, SPACE_HARDWARE, INFERENCE_PROVIDERS,  # noqa: F401
    AUTHORS, build_seed_repos,
)
from content_data import DOC_PAGES, BLOG_POSTS, DAILY_PAPERS, CLASSROOM_BENEFITS, PRICING_PLANS, DATASET_VIEWER_DATA

# ------------------------------------------------------------
# Flask setup
# ------------------------------------------------------------
ROOT = Path(__file__).parent
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "hf-mirror-dev-secret-key-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{ROOT / 'instance' / 'hf.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
(ROOT / "instance").mkdir(exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"


@app.template_filter("fromjson")
def _fromjson_filter(value):
    """Parse a JSON string in a template. Returns [] on failure."""
    try:
        if isinstance(value, (list, dict)):
            return value
        return json.loads(value)
    except Exception:
        return []


# ------------------------------------------------------------
# Database models
# ------------------------------------------------------------
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(120), default="")
    bio = db.Column(db.Text, default="")
    avatar_url = db.Column(db.String(300), default="/static/images/avatars/avatar_000.png")
    website = db.Column(db.String(200), default="")
    location = db.Column(db.String(120), default="")
    company = db.Column(db.String(120), default="")
    is_pro = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    likes = db.relationship("Like", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    follows = db.relationship("Follow", backref="user", cascade="all, delete-orphan", lazy="dynamic", foreign_keys="Follow.user_id")
    collections = db.relationship("Collection", backref="owner", cascade="all, delete-orphan", lazy="dynamic")
    cart_items = db.relationship("CartItem", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    endpoints = db.relationship("InferenceEndpoint", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    discussions = db.relationship("Discussion", backref="author", cascade="all, delete-orphan", lazy="dynamic")


class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    display = db.Column(db.String(120), nullable=False)
    modality = db.Column(db.String(80), nullable=False, index=True)
    icon = db.Column(db.String(20), default="🔹")
    description = db.Column(db.Text, default="")
    repos = db.relationship("Repository", backref="task_obj", lazy="dynamic")


class Author(db.Model):
    """Organization or user owning repositories (like google, meta-llama)."""
    __tablename__ = "authors"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(200), nullable=False)
    kind = db.Column(db.String(10), default="org")   # org | user
    bio = db.Column(db.Text, default="")
    followers_count = db.Column(db.Integer, default=0)
    website = db.Column(db.String(300), default="")
    avatar_url = db.Column(db.String(300), default="")
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    repos = db.relationship("Repository", backref="author_obj", lazy="dynamic")


class Repository(db.Model):
    """Unified Model | Dataset | Space entity."""
    __tablename__ = "repositories"
    __table_args__ = (db.UniqueConstraint("slug", "repo_type", name="uix_repo_slug_type"),)
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(300), nullable=False, index=True)  # author/name
    name = db.Column(db.String(200), nullable=False)
    repo_type = db.Column(db.String(16), nullable=False, index=True)           # model | dataset | space
    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"), index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), index=True, nullable=True)
    library = db.Column(db.String(80), default="")
    license = db.Column(db.String(80), default="apache-2.0")
    license_display = db.Column(db.String(120), default="Apache 2.0")
    description = db.Column(db.Text, default="")
    readme = db.Column(db.Text, default="")
    language = db.Column(db.String(80), default="English")
    # Model-specific
    params_b = db.Column(db.Float, default=0.0)
    inference_provider = db.Column(db.String(80), default="")
    # Dataset-specific
    modality = db.Column(db.String(80), default="")
    rows = db.Column(db.BigInteger, default=0)
    # Space-specific
    sdk = db.Column(db.String(40), default="")
    hardware_slug = db.Column(db.String(40), default="")
    hardware_display = db.Column(db.String(120), default="")
    hardware_specs = db.Column(db.String(200), default="")
    hardware_price = db.Column(db.String(40), default="")
    emoji = db.Column(db.String(20), default="🚀")
    status = db.Column(db.String(40), default="Running")
    # Common
    downloads = db.Column(db.BigInteger, default=0)
    likes_count = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=False)
    tags_json = db.Column(db.Text, default="[]")
    avatar_url = db.Column(db.String(300), default="")
    banner_url = db.Column(db.String(300), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    discussions = db.relationship("Discussion", backref="repo", cascade="all, delete-orphan", lazy="dynamic")

    @property
    def tags(self):
        try:
            return json.loads(self.tags_json or "[]")
        except Exception:
            return []

    @property
    def task_slug(self):
        return self.task_obj.slug if self.task_obj else ""

    @property
    def task_display(self):
        return self.task_obj.display if self.task_obj else self.repo_type.capitalize()

    @property
    def size_badge(self):
        if self.repo_type == "model" and self.params_b > 0:
            if self.params_b >= 1:
                return f"{int(self.params_b)}B"
            return f"{int(self.params_b * 1000)}M"
        return ""

    @property
    def updated_display(self):
        dt = self.updated_at or mirror_now()
        return dt.strftime("%b %d, %Y")

    @property
    def downloads_display(self):
        n = self.downloads or 0
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}k"
        return str(n)

    @property
    def likes_display(self):
        n = self.likes_count or 0
        if n >= 1000:
            return f"{n / 1000:.2f}k".rstrip("0").rstrip(".")
        return str(n)

    @property
    def rows_display(self):
        n = self.rows or 0
        if n >= 1_000_000_000_000:
            return f"{n / 1e12:.1f}T"
        if n >= 1_000_000_000:
            return f"{n / 1e9:.1f}B"
        if n >= 1_000_000:
            return f"{n / 1e6:.1f}M"
        if n >= 1_000:
            return f"{n / 1e3:.1f}k"
        return str(n)


class Like(db.Model):
    __tablename__ = "likes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    repo_id = db.Column(db.Integer, db.ForeignKey("repositories.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    repo = db.relationship("Repository")
    __table_args__ = (db.UniqueConstraint("user_id", "repo_id", name="uix_like"),)


class Follow(db.Model):
    __tablename__ = "follows"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship("Author")
    __table_args__ = (db.UniqueConstraint("user_id", "author_id", name="uix_follow"),)


class Collection(db.Model):
    __tablename__ = "collections"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("CollectionItem", backref="collection", cascade="all, delete-orphan", lazy="dynamic")


class CollectionItem(db.Model):
    __tablename__ = "collection_items"
    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey("collections.id"), nullable=False, index=True)
    repo_id = db.Column(db.Integer, db.ForeignKey("repositories.id"), nullable=False, index=True)
    note = db.Column(db.Text, default="")
    position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    repo = db.relationship("Repository")


class CartItem(db.Model):
    """Deployment cart — user stages repos + hardware before 'deploying'."""
    __tablename__ = "cart_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    repo_id = db.Column(db.Integer, db.ForeignKey("repositories.id"), nullable=False, index=True)
    hardware_slug = db.Column(db.String(40), default="t4-small")
    hardware_display = db.Column(db.String(120), default="Nvidia T4")
    hardware_price = db.Column(db.String(40), default="$0.40/hr")
    hours = db.Column(db.Integer, default=24)
    region = db.Column(db.String(40), default="us-east-1")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    repo = db.relationship("Repository")


class InferenceEndpoint(db.Model):
    """Order equivalent — a deployed repo on specific hardware.

    Lifecycle: initializing -> running -> paused -> terminated.
    """
    __tablename__ = "endpoints"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    endpoint_id = db.Column(db.String(40), unique=True, nullable=False, index=True)  # EP-XXXXXX
    name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(40), default="initializing")
    region = db.Column(db.String(40), default="us-east-1")
    total_hours = db.Column(db.Integer, default=24)
    total_cost = db.Column(db.String(40), default="$0.00")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("EndpointItem", backref="endpoint", cascade="all, delete-orphan", lazy="dynamic")


class EndpointItem(db.Model):
    __tablename__ = "endpoint_items"
    id = db.Column(db.Integer, primary_key=True)
    endpoint_id = db.Column(db.Integer, db.ForeignKey("endpoints.id"), nullable=False, index=True)
    repo_id = db.Column(db.Integer, db.ForeignKey("repositories.id"), nullable=False, index=True)
    hardware_slug = db.Column(db.String(40), default="")
    hardware_display = db.Column(db.String(120), default="")
    hardware_price = db.Column(db.String(40), default="")
    hours = db.Column(db.Integer, default=24)
    repo = db.relationship("Repository")


class Discussion(db.Model):
    """Community discussion thread on a repo — review equivalent."""
    __tablename__ = "discussions"
    id = db.Column(db.Integer, primary_key=True)
    repo_id = db.Column(db.Integer, db.ForeignKey("repositories.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=False)
    kind = db.Column(db.String(20), default="discussion")   # discussion | pull-request | issue
    status = db.Column(db.String(20), default="open")       # open | closed | merged
    upvotes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    replies = db.relationship("DiscussionReply", backref="discussion", cascade="all, delete-orphan", lazy="dynamic")


class DiscussionReply(db.Model):
    __tablename__ = "discussion_replies"
    id = db.Column(db.Integer, primary_key=True)
    discussion_id = db.Column(db.Integer, db.ForeignKey("discussions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User")


# ------------------------------------------------------------
# Login manager
# ------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ------------------------------------------------------------
# Forms
# ------------------------------------------------------------
class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])


class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(3, 40)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(6, 120)])
    confirm = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])


class ProfileForm(FlaskForm):
    display_name = StringField("Display name", validators=[OptionalValidator(), Length(0, 120)])
    bio = TextAreaField("Bio", validators=[OptionalValidator()])
    website = StringField("Website", validators=[OptionalValidator()])
    location = StringField("Location", validators=[OptionalValidator()])
    company = StringField("Company", validators=[OptionalValidator()])


class PasswordForm(FlaskForm):
    current = PasswordField("Current password", validators=[DataRequired()])
    new = PasswordField("New password", validators=[DataRequired(), Length(6, 120)])
    confirm = PasswordField("Confirm new password", validators=[DataRequired(), EqualTo("new")])


class CollectionForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(1, 200)])
    description = TextAreaField("Description", validators=[OptionalValidator()])
    is_public = SelectField("Visibility", choices=[("1", "Public"), ("0", "Private")], default="1")


class DiscussionForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(1, 300)])
    body = TextAreaField("Body", validators=[DataRequired()])
    kind = SelectField("Type", choices=[("discussion", "Discussion"), ("issue", "Issue"), ("pull-request", "Pull request")])


class ReplyForm(FlaskForm):
    body = TextAreaField("Reply", validators=[DataRequired()])


class CheckoutForm(FlaskForm):
    name = StringField("Deployment name", validators=[DataRequired(), Length(1, 200)])
    region = SelectField("Region", choices=[
        ("us-east-1", "US East (N. Virginia)"),
        ("us-west-2", "US West (Oregon)"),
        ("eu-west-1", "EU West (Ireland)"),
        ("eu-central-1", "EU Central (Frankfurt)"),
        ("ap-southeast-1", "Asia Pacific (Singapore)"),
    ])
    payment_method = SelectField("Payment method", choices=[
        ("card", "Credit / Debit Card"),
        ("invoice", "Invoice (Enterprise)"),
    ])


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def resolve_author_avatar(username: str) -> str:
    """Return the URL of the author's avatar.

    Prefers a real-org logo at /static/images/avatars/orgs/<username>.<ext>
    (case-insensitive). Falls back to a deterministic generic avatar from
    /static/images/avatars/avatar_*.* so the same username always renders
    the same image.
    """
    if not username:
        return ""
    orgs_dir = ROOT / "static" / "images" / "avatars" / "orgs"
    if orgs_dir.exists():
        # Try exact then case-insensitive match across common image suffixes
        candidates = list(orgs_dir.iterdir())
        lower = username.lower()
        for p in candidates:
            if p.stem == username and p.is_file():
                return f"/static/images/avatars/orgs/{p.name}"
        for p in candidates:
            if p.stem.lower() == lower and p.is_file():
                return f"/static/images/avatars/orgs/{p.name}"
    # Deterministic fallback into the generic pool
    pool_dir = ROOT / "static" / "images" / "avatars"
    if pool_dir.exists():
        pool = sorted(p.name for p in pool_dir.iterdir() if p.is_file() and p.suffix.lower() in {".png",".jpg",".jpeg",".webp",".svg"})
        if pool:
            import hashlib
            h = int(hashlib.md5(username.encode()).hexdigest(), 16)
            return f"/static/images/avatars/{pool[h % len(pool)]}"
    return ""


def get_or_create_author(username: str) -> Author:
    a = Author.query.filter_by(username=username).first()
    if not a:
        a = Author(
            username=username,
            display_name=username,
            kind="org",
            bio=f"Releases from {username}.",
            followers_count=random.randint(300, 9000),
            website="",
            avatar_url=resolve_author_avatar(username),
            is_verified=False,
        )
        db.session.add(a)
        db.session.flush()
    return a


def current_cart_count():
    if not current_user.is_authenticated:
        return 0
    return CartItem.query.filter_by(user_id=current_user.id).count()


def _liked_repo_ids():
    if not current_user.is_authenticated:
        return set()
    return {l.repo_id for l in Like.query.filter_by(user_id=current_user.id).all()}


# ------------------------------------------------------------
# Scored search helpers
# ------------------------------------------------------------
STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "is", "are", "be", "by", "from", "that", "this", "it", "as",
    "best", "most", "new", "latest", "recent", "top", "find", "show",
    "model", "models", "dataset", "datasets", "space", "spaces",
    "hugging", "huggingface", "hub", "use", "using",
}


def _tokenize(q: str):
    return [t for t in re.findall(r"[a-z0-9.+-]+", (q or "").lower())
            if len(t) >= 2 and t not in STOPWORDS]


def _repo_haystack(r: "Repository") -> str:
    parts = [
        (r.slug or "").lower(),
        (r.name or "").lower(),
        (r.description or "").lower(),
        (r.readme or "").lower()[:800],
        (r.tags_json or "").lower(),
        (r.library or "").lower(),
        (r.license or "").lower(),
        (r.language or "").lower(),
        (r.modality or "").lower(),
        (r.task_obj.slug if r.task_obj else "").lower(),
        (r.task_obj.display if r.task_obj else "").lower(),
        (r.author_obj.username if r.author_obj else "").lower(),
    ]
    return " ".join(parts)


def _score_repo(repo, tokens):
    if not tokens:
        return 1
    hay = _repo_haystack(repo)
    return sum(1 for t in tokens if t in hay)


def _apply_text_prefilter(query, q: str):
    """Narrow a Repository query to rows that plausibly contain any of the
    free-text tokens before LIMIT/sort. Without this, long-tail repos with low
    trending scores get cut off by the SQL LIMIT before scoring sees them."""
    tokens = _tokenize(q or "")
    if not tokens:
        return query
    from sqlalchemy import or_
    clauses = []
    for t in tokens:
        pat = f"%{t}%"
        clauses += [
            Repository.slug.ilike(pat),
            Repository.name.ilike(pat),
            Repository.description.ilike(pat),
            Repository.tags_json.ilike(pat),
        ]
    return query.filter(or_(*clauses))


def _apply_repo_filters(query, args):
    """Apply common filter query-string args to a Repository SQL query."""
    license_ = args.get("license", "")
    if license_:
        query = query.filter(Repository.license == license_)
    library = args.get("library", "")
    if library:
        query = query.filter(Repository.library.ilike(library))
    language = args.get("language", "")
    if language:
        query = query.filter(Repository.language.ilike(f"%{language}%"))
    task_slug = args.get("task", "")
    if task_slug:
        t = Task.query.filter_by(slug=task_slug).first()
        if t:
            query = query.filter(Repository.task_id == t.id)
    modality = args.get("modality", "")
    if modality:
        query = query.filter(Repository.modality.ilike(f"%{modality}%"))
    min_downloads = args.get("min_downloads", type=int)
    if min_downloads:
        query = query.filter(Repository.downloads >= min_downloads)
    min_likes = args.get("min_likes", type=int)
    if min_likes:
        query = query.filter(Repository.likes_count >= min_likes)
    updated_year = args.get("updated_year", type=int)
    if updated_year:
        start = datetime(updated_year, 1, 1)
        end = datetime(updated_year + 1, 1, 1)
        query = query.filter(Repository.updated_at >= start, Repository.updated_at < end)
    updated_month = args.get("updated_month", "")
    if updated_month and re.match(r"^\d{4}-\d{2}$", updated_month):
        y, m = int(updated_month[:4]), int(updated_month[5:7])
        start = datetime(y, m, 1)
        end = datetime(y + (m // 12), (m % 12) + 1, 1)
        query = query.filter(Repository.updated_at >= start, Repository.updated_at < end)
    sdk = args.get("sdk", "")
    if sdk:
        query = query.filter(Repository.sdk.ilike(sdk))
    tag = args.get("tag", "")
    if tag:
        # tags_json is a JSON-encoded list; do a substring match on the JSON string
        query = query.filter(Repository.tags_json.ilike(f'%"{tag}"%'))
    return query


def _apply_repo_sort(query, sort):
    if sort == "downloads":
        return query.order_by(Repository.downloads.desc())
    if sort == "likes":
        return query.order_by(Repository.likes_count.desc())
    if sort == "updated" or sort == "modified":
        return query.order_by(Repository.updated_at.desc())
    if sort == "created":
        return query.order_by(Repository.created_at.desc())
    # trending
    return query.order_by((Repository.likes_count * 3 + Repository.downloads / 1000).desc())


@app.context_processor
def inject_globals():
    all_tasks = Task.query.order_by(Task.display).all()
    _now = mirror_now()
    return {
        "cart_count": current_cart_count(),
        "tasks_nav": all_tasks,
        "current_year": _now.year,
        "mirror_now": _now,
        "mirror_today_display": _now.strftime("%B %-d, %Y"),
        "modalities": MODALITIES,
    }


# ------------------------------------------------------------
# Seed the database
# ------------------------------------------------------------
def seed_database():
    """Populate all tables with starting data."""
    if Task.query.count() > 0:
        return
    print("Seeding database...")

    # 1) Tasks
    for slug, display, modality, icon, description in TASKS:
        db.session.add(Task(slug=slug, display=display, modality=modality, icon=icon, description=description))
    db.session.flush()
    task_by_slug = {t.slug: t for t in Task.query.all()}

    # 2) Authors
    avatar_files = sorted(p.name for p in (ROOT / "static" / "images" / "avatars").iterdir() if p.is_file())
    rng = random.Random(7)
    for i, (username, display, kind, bio, followers, is_verified, website) in enumerate(AUTHORS):
        db.session.add(Author(
            username=username,
            display_name=display,
            kind=kind,
            bio=bio,
            followers_count=followers,
            is_verified=is_verified,
            website=website,
            avatar_url=f"/static/images/avatars/{avatar_files[i % len(avatar_files)]}" if avatar_files else "",
        ))
    db.session.flush()

    # 3) Demo user
    demo = User(
        email="demo@hf.co",
        username="demo",
        password_hash=bcrypt.generate_password_hash("password123").decode(),
        display_name="Demo User",
        bio="Just exploring the Hub.",
        avatar_url=f"/static/images/avatars/{avatar_files[0]}" if avatar_files else "",
        is_pro=True,
    )
    db.session.add(demo)
    db.session.flush()

    # 4) Repos
    models, datasets, spaces = build_seed_repos()
    all_repos = models + datasets + spaces
    for item in all_repos:
        author = get_or_create_author(item["author"])
        task = task_by_slug.get(item.get("task", ""))
        repo = Repository(
            slug=item["slug"],
            name=item["name"],
            repo_type=item["repo_type"],
            author_id=author.id,
            task_id=task.id if task else None,
            library=item.get("library", ""),
            license=item.get("license", "apache-2.0"),
            license_display=item.get("license_display", "Apache 2.0"),
            description=item.get("description", ""),
            readme=item.get("readme", ""),
            language=item.get("language", "English"),
            params_b=item.get("params_b", 0.0),
            inference_provider=item.get("inference_provider", ""),
            modality=item.get("modality", ""),
            rows=item.get("rows", 0),
            sdk=item.get("sdk", ""),
            hardware_slug=item.get("hardware_slug", ""),
            hardware_display=item.get("hardware_display", ""),
            hardware_specs=item.get("hardware_specs", ""),
            hardware_price=item.get("hardware_price", ""),
            emoji=item.get("emoji", "🚀"),
            status=item.get("status", "Running"),
            downloads=item.get("downloads", 0),
            likes_count=item.get("likes", 0),
            is_featured=item.get("is_featured", False),
            is_new=item.get("is_new", False),
            tags_json=json.dumps(item.get("tags", [])),
            avatar_url=item.get("avatar", ""),
            banner_url=item.get("banner", ""),
            updated_at=mirror_now() - timedelta(days=item.get("updated_days_ago", 1)),
        )
        db.session.add(repo)
    db.session.commit()

    # 5) Seed some discussions on top repos
    top_repos = Repository.query.order_by(Repository.likes_count.desc()).limit(12).all()
    sample_titles = [
        "How does this model handle long context?",
        "Model keeps hallucinating tool calls — any fix?",
        "Quantization question: FP8 vs INT4?",
        "Fine-tuning on custom data — best practice?",
        "Great work! Loving the results.",
        "License clarification",
    ]
    sample_bodies = [
        "Hi team — I ran this locally with 24k tokens and the attention pattern seems off. Have you evaluated on longer context?",
        "Really impressive results on my benchmark. Congrats to the authors!",
        "Has anyone tried running this with vLLM? I'm getting OOM on a single A100 at batch_size=4.",
        "For the license question — can I use the outputs commercially? The tag says OpenRAIL but the README says apache-2.0.",
        "Bug report: tokenizer adds an extra BOS when calling `apply_chat_template`. PR incoming.",
    ]
    for i, repo in enumerate(top_repos):
        d = Discussion(
            repo_id=repo.id,
            user_id=demo.id,
            title=sample_titles[i % len(sample_titles)],
            body=sample_bodies[i % len(sample_bodies)],
            upvotes=rng.randint(2, 80),
            kind=rng.choice(["discussion", "issue", "pull-request"]),
        )
        db.session.add(d)
        db.session.flush()
        # Add a reply
        reply = DiscussionReply(
            discussion_id=d.id,
            user_id=demo.id,
            body="Thanks for the report! Could you share a minimal repro script? We'll investigate.",
        )
        db.session.add(reply)

    # 6) Seed collection for demo user
    c = Collection(
        user_id=demo.id,
        title="Favorite open LLMs",
        description="My curated list of open-source language models worth trying.",
        is_public=True,
    )
    db.session.add(c)
    db.session.flush()
    for r in Repository.query.filter_by(repo_type="model").limit(5).all():
        db.session.add(CollectionItem(collection_id=c.id, repo_id=r.id, note=""))

    db.session.commit()
    print(f"  ✓ {Task.query.count()} tasks")
    print(f"  ✓ {Author.query.count()} authors")
    print(f"  ✓ {Repository.query.count()} repositories")
    print(f"  ✓ {Discussion.query.count()} discussions")
    print(f"  ✓ {Collection.query.count()} collections")


# ------------------------------------------------------------
# Routes — Static / homepage
# ------------------------------------------------------------
@app.route("/")
def index():
    trending_models = Repository.query.filter_by(repo_type="model").order_by(Repository.likes_count.desc()).limit(5).all()
    trending_datasets = Repository.query.filter_by(repo_type="dataset").order_by(Repository.likes_count.desc()).limit(5).all()
    trending_spaces = Repository.query.filter_by(repo_type="space", is_featured=True).order_by(Repository.likes_count.desc()).limit(6).all()
    featured_orgs = Author.query.filter_by(is_verified=True).order_by(Author.followers_count.desc()).limit(8).all()
    total_models = Repository.query.filter_by(repo_type="model").count()
    total_datasets = Repository.query.filter_by(repo_type="dataset").count()
    total_spaces = Repository.query.filter_by(repo_type="space").count()
    return render_template(
        "index.html",
        trending_models=trending_models,
        trending_datasets=trending_datasets,
        trending_spaces=trending_spaces,
        featured_orgs=featured_orgs,
        total_models=total_models,
        total_datasets=total_datasets,
        total_spaces=total_spaces,
        liked_ids=_liked_repo_ids(),
    )


@app.route("/models")
def models_list():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "trending")
    query = Repository.query.filter_by(repo_type="model")
    query = _apply_repo_filters(query, request.args)
    query = _apply_text_prefilter(query, q)
    query = _apply_repo_sort(query, sort)
    candidates = query.limit(2000).all()
    if q:
        tokens = _tokenize(q)
        min_req = max(1, len(tokens) // 2) if tokens else 0
        scored = [(s, r) for r in candidates if (s := _score_repo(r, tokens)) >= min_req]
        scored.sort(key=lambda x: -x[0])
        candidates = [r for _, r in scored]
    total = len(candidates)
    page = int(request.args.get("page", 1))
    per_page = 30
    repos = candidates[(page - 1) * per_page : page * per_page]
    tasks_list = Task.query.order_by(Task.display).all()
    return render_template(
        "repo_list.html",
        repos=repos,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=max(1, (total + per_page - 1) // per_page),
        tasks_list=tasks_list,
        libraries=LIBRARIES,
        licenses=LICENSES,
        active_task=request.args.get("task", ""),
        active_library=request.args.get("library", ""),
        active_license=request.args.get("license", ""),
        active_sort=sort,
        q=q,
        repo_type="model",
        page_title="Models",
        liked_ids=_liked_repo_ids(),
    )


@app.route("/datasets")
def datasets_list():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "trending")
    query = Repository.query.filter_by(repo_type="dataset")
    query = _apply_repo_filters(query, request.args)
    query = _apply_text_prefilter(query, q)
    query = _apply_repo_sort(query, sort)
    candidates = query.limit(2000).all()
    if q:
        tokens = _tokenize(q)
        min_req = max(1, len(tokens) // 2) if tokens else 0
        scored = [(s, r) for r in candidates if (s := _score_repo(r, tokens)) >= min_req]
        scored.sort(key=lambda x: -x[0])
        candidates = [r for _, r in scored]
    total = len(candidates)
    page = int(request.args.get("page", 1))
    per_page = 30
    repos = candidates[(page - 1) * per_page : page * per_page]
    return render_template(
        "repo_list.html",
        repos=repos,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=max(1, (total + per_page - 1) // per_page),
        tasks_list=Task.query.order_by(Task.display).all(),
        libraries=LIBRARIES,
        licenses=LICENSES,
        active_modality=request.args.get("modality", ""),
        active_license=request.args.get("license", ""),
        active_sort=sort,
        q=q,
        repo_type="dataset",
        page_title="Datasets",
        liked_ids=_liked_repo_ids(),
    )


@app.route("/spaces")
def spaces_list():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "trending")
    query = Repository.query.filter_by(repo_type="space")
    query = _apply_repo_filters(query, request.args)
    query = _apply_text_prefilter(query, q)
    query = _apply_repo_sort(query, sort)
    candidates = query.limit(2000).all()
    if q:
        tokens = _tokenize(q)
        min_req = max(1, len(tokens) // 2) if tokens else 0
        scored = [(s, r) for r in candidates if (s := _score_repo(r, tokens)) >= min_req]
        scored.sort(key=lambda x: -x[0])
        candidates = [r for _, r in scored]
    total = len(candidates)
    page = int(request.args.get("page", 1))
    per_page = 30
    repos = candidates[(page - 1) * per_page : page * per_page]
    return render_template(
        "spaces_list.html",
        repos=repos,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=max(1, (total + per_page - 1) // per_page),
        tasks_list=Task.query.order_by(Task.display).all(),
        active_task=request.args.get("task", ""),
        active_sdk=request.args.get("sdk", ""),
        active_sort=sort,
        q=q,
        page_title="Spaces",
        liked_ids=_liked_repo_ids(),
    )


@app.route("/tasks")
def tasks_index():
    tasks_by_modality = {}
    for m in MODALITIES:
        tasks_by_modality[m] = Task.query.filter_by(modality=m).order_by(Task.display).all()
    return render_template("tasks_index.html", tasks_by_modality=tasks_by_modality)


@app.route("/tasks/<slug>")
def task_detail(slug):
    task = Task.query.filter_by(slug=slug).first_or_404()
    models = Repository.query.filter_by(repo_type="model", task_id=task.id).order_by(Repository.likes_count.desc()).limit(12).all()
    datasets = Repository.query.filter_by(repo_type="dataset", task_id=task.id).order_by(Repository.likes_count.desc()).limit(8).all()
    spaces = Repository.query.filter_by(repo_type="space", task_id=task.id).order_by(Repository.likes_count.desc()).limit(8).all()
    return render_template(
        "task_detail.html",
        task=task,
        models=models,
        datasets=datasets,
        spaces=spaces,
        liked_ids=_liked_repo_ids(),
    )


@app.route("/docs")
def docs():
    topic = request.args.get("topic", "")
    q = request.args.get("q", "").strip().lower()
    # Either direct topic slug or keyword search maps to one of the prebuilt pages
    if not topic and q:
        for slug, page in DOC_PAGES.items():
            if any(kw in q for kw in page["keywords"]):
                topic = slug
                break
    if topic and topic in DOC_PAGES:
        return render_template(
            "docs_topic.html",
            topic=topic, page=DOC_PAGES[topic], all_topics=DOC_PAGES,
        )
    return render_template("docs.html", all_topics=DOC_PAGES)


@app.route("/docs/<topic>")
def docs_topic(topic):
    if topic not in DOC_PAGES:
        abort(404)
    return render_template(
        "docs_topic.html",
        topic=topic, page=DOC_PAGES[topic], all_topics=DOC_PAGES,
    )


@app.route("/pricing")
def pricing():
    return render_template(
        "pricing.html",
        space_hardware=SPACE_HARDWARE,
        pricing_plans=PRICING_PLANS,
    )


@app.route("/enterprise")
def enterprise():
    return render_template("enterprise.html")


@app.route("/blog")
def blog_index():
    tag = request.args.get("tag", "").strip().lower()
    q = request.args.get("q", "").strip().lower()
    # Sort posts by publish date descending so the latest is always first.
    posts = sorted(BLOG_POSTS, key=lambda p: p.get("published", ""), reverse=True)
    if tag:
        posts = [p for p in posts if tag in [t.lower() for t in p.get("tags", [])]]
    if q:
        posts = [p for p in posts if q in p["title"].lower() or q in p["excerpt"].lower() or any(q in t.lower() for t in p.get("tags", []))]
    return render_template("blog.html", posts=posts, all_tags=sorted({t for p in BLOG_POSTS for t in p["tags"]}))


@app.route("/blog/<slug>")
def blog_post(slug):
    post = next((p for p in BLOG_POSTS if p["slug"] == slug), None)
    if not post:
        abort(404)
    return render_template("blog_post.html", post=post)


@app.route("/papers")
def papers_index():
    return render_template("papers.html", papers=DAILY_PAPERS)


@app.route("/papers/<arxiv_id>")
def paper_detail(arxiv_id):
    paper = next((p for p in DAILY_PAPERS if p["arxiv_id"] == arxiv_id), None)
    if not paper:
        abort(404)
    return render_template("paper_detail.html", paper=paper)


@app.route("/learn")
def learn():
    return render_template("learn.html", classroom_benefits=CLASSROOM_BENEFITS)


@app.route("/learn/classroom")
@app.route("/classroom")
@app.route("/education")
@app.route("/education/classroom")
def learn_classroom():
    return render_template("classroom.html", benefits=CLASSROOM_BENEFITS)


@app.route("/datasets/<author>/<name>/viewer")
def dataset_viewer(author, name):
    slug = f"{author}/{name}"
    repo = Repository.query.filter_by(slug=slug, repo_type="dataset").first()
    if not repo:
        abort(404)
    data = DATASET_VIEWER_DATA.get(slug, {
        "columns": ["id", "text"],
        "rows": [[1, "Sample row"]],
    })
    return render_template("dataset_viewer.html", repo=repo, viewer=data)


@app.route("/chat")
def chat():
    chat_models = Repository.query.filter_by(repo_type="model", is_featured=True).filter(Repository.task_id == Task.query.filter_by(slug="text-generation").first().id if Task.query.filter_by(slug="text-generation").first() else None).limit(10).all()
    return render_template("chat.html", chat_models=chat_models)


# ------------------------------------------------------------
# Repo detail pages
# ------------------------------------------------------------
def _load_repo_or_404(repo_type: str, author: str, name: str):
    slug = f"{author}/{name}"
    repo = Repository.query.filter_by(slug=slug, repo_type=repo_type).first()
    if not repo:
        abort(404)
    return repo


def _repo_gallery_images(repo: Repository):
    """Collect gallery images for this repo from /static/images/repos or fallbacks."""
    base_dir = ROOT / "static" / "images"
    # Prefer dedicated repo banner dir
    repo_dir = base_dir / "repos"
    images = []
    if repo_dir.exists():
        for f in sorted(repo_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                images.append(f"/static/images/repos/{f.name}")
    # Fallback to heroes
    if len(images) < 6:
        hero_dir = base_dir / "heroes"
        if hero_dir.exists():
            for f in sorted(hero_dir.iterdir()):
                if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    images.append(f"/static/images/heroes/{f.name}")
    # Stable per-repo subset
    import hashlib
    h = int(hashlib.md5(repo.slug.encode()).hexdigest(), 16)
    out = []
    for i in range(min(6, len(images))):
        out.append(images[(h + i * 13) % len(images)])
    return out


def _compute_model_metrics(repo: "Repository"):
    """Derive a deterministic small metrics table per model.

    Uses the model slug as a stable hash seed so every task-visit sees the same values.
    Only emitted for model repos whose task has a meaningful eval metric.
    """
    import hashlib
    if not repo or repo.repo_type != "model":
        return []
    task = (repo.task_slug or "").lower()
    if not task:
        return []
    h = int(hashlib.md5(repo.slug.encode()).hexdigest(), 16)
    def _v(lo: float, hi: float, step: int = 0) -> float:
        span = hi - lo
        r = ((h >> (step * 4)) & 0xFFFF) / 0xFFFF
        return round(lo + span * r, 2)
    rows = []
    if task == "translation":
        rows.append({"metric": "BLEU", "value": _v(22.5, 42.8, 0), "dataset": "flores200.devtest", "split": "test"})
        rows.append({"metric": "chrF", "value": _v(48.0, 65.0, 1), "dataset": "wmt21", "split": "test"})
    elif task == "summarization":
        rows.append({"metric": "ROUGE-1", "value": _v(38.0, 48.5, 0), "dataset": "cnn_dailymail", "split": "test"})
        rows.append({"metric": "ROUGE-L", "value": _v(30.0, 40.0, 1), "dataset": "cnn_dailymail", "split": "test"})
    elif task == "text-classification":
        rows.append({"metric": "Accuracy", "value": _v(82.0, 94.5, 0), "dataset": "glue/sst2", "split": "validation"})
        rows.append({"metric": "F1", "value": _v(80.0, 93.0, 1), "dataset": "glue/mrpc", "split": "validation"})
    elif task in ("text-generation", "text2text-generation"):
        rows.append({"metric": "MMLU (5-shot)", "value": _v(42.0, 72.0, 0), "dataset": "mmlu", "split": "test"})
        rows.append({"metric": "HellaSwag (10-shot)", "value": _v(60.0, 84.0, 1), "dataset": "hellaswag", "split": "val"})
    elif task == "question-answering":
        rows.append({"metric": "F1", "value": _v(78.0, 92.0, 0), "dataset": "squad_v2", "split": "validation"})
        rows.append({"metric": "Exact Match", "value": _v(70.0, 88.0, 1), "dataset": "squad_v2", "split": "validation"})
    elif task == "automatic-speech-recognition":
        rows.append({"metric": "WER", "value": _v(3.5, 12.0, 0), "dataset": "librispeech_clean", "split": "test"})
    elif task == "image-classification":
        rows.append({"metric": "Top-1 Accuracy", "value": _v(72.0, 88.0, 0), "dataset": "imagenet-1k", "split": "val"})
    elif task == "sentence-similarity" or repo.library == "sentence-transformers":
        rows.append({"metric": "Spearman", "value": _v(78.0, 88.0, 0), "dataset": "sts-benchmark", "split": "test"})
    elif task == "fill-mask":
        rows.append({"metric": "Perplexity", "value": _v(8.0, 24.0, 0), "dataset": "wikitext-103", "split": "test"})
    return rows


def _spaces_using_model(repo: "Repository", limit: int = 8):
    """Return spaces that reference this model by slug in their description/readme/tags
    or by same-author prefix."""
    if not repo or repo.repo_type != "model":
        return []
    slug = repo.slug.lower()
    author = slug.split("/")[0] if "/" in slug else slug
    name_only = slug.split("/")[-1]
    seen_ids = set()
    out = []
    # 1) Spaces whose description/readme/tags contain the model slug or short name
    like_slug = f"%{slug}%"
    like_name = f"%{name_only}%"
    q = Repository.query.filter(Repository.repo_type == "space").filter(
        db.or_(
            Repository.description.ilike(like_slug),
            Repository.readme.ilike(like_slug),
            Repository.tags_json.ilike(like_slug),
            Repository.description.ilike(like_name),
            Repository.readme.ilike(like_name),
            Repository.tags_json.ilike(like_name),
            Repository.slug.ilike(f"{author}/%"),
        )
    ).order_by(Repository.likes_count.desc()).limit(limit * 2)
    for s in q.all():
        if s.id in seen_ids:
            continue
        seen_ids.add(s.id)
        out.append(s)
        if len(out) >= limit:
            break
    return out


# ----------------------------------------------------------------------------
# Repo filesystem & commit history (deterministic, derived from repo metadata)
# ----------------------------------------------------------------------------

def _fmt_bytes(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f} GB"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f} kB"
    return f"{n} B"


def _repo_commit_messages():
    return [
        "Upload model card",
        "Update README.md",
        "Initial commit",
        "Add tokenizer",
        "Fix config.json",
        "Convert model to safetensors",
        "Improve evaluation metrics",
        "Add usage examples",
        "Update license",
        "Pin transformers version",
        "Add model checkpoint",
        "Refactor data loader",
        "Bump version",
        "Add training logs",
        "Documentation cleanup",
    ]


def _repo_commits(repo, limit: int = 12):
    """Deterministic synthetic commit log per repo."""
    import hashlib
    if not repo:
        return []
    h = int(hashlib.md5((repo.slug + "|commits").encode()).hexdigest(), 16)
    msgs = _repo_commit_messages()
    authors_pool = [
        ("system", "🤖"),
        (repo.slug.split("/")[0], "👤"),
        ("HuggingFaceBot", "🤖"),
        ("contributor-1", "👤"),
        ("contributor-2", "👤"),
    ]
    base_dt = repo.updated_at or mirror_now()
    out = []
    for i in range(limit):
        msg_idx = (h >> (i * 3)) & 0xF
        author_idx = (h >> (i * 5)) & 0x7
        msg = msgs[msg_idx % len(msgs)]
        author = authors_pool[author_idx % len(authors_pool)]
        sha = hashlib.sha1(f"{repo.slug}|{i}".encode()).hexdigest()[:7]
        dt = base_dt - timedelta(days=i * 7 + (((h >> i) & 0xF) % 6))
        out.append({
            "sha": sha,
            "message": msg,
            "author": author[0],
            "author_emoji": author[1],
            "date": dt,
            "date_display": dt.strftime("%b %d, %Y"),
            "rel_display": _rel_time(dt),
        })
    return out


def _rel_time(dt):
    if not dt:
        return ""
    delta = mirror_now() - dt
    days = delta.days
    if days < 1:
        hrs = max(1, delta.seconds // 3600)
        return f"about {hrs} hour{'s' if hrs > 1 else ''} ago"
    if days < 30:
        return f"{days} day{'s' if days > 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"about {months} month{'s' if months > 1 else ''} ago"
    years = days // 365
    return f"about {years} year{'s' if years > 1 else ''} ago"


def _repo_filesystem(repo):
    """Deterministic synthetic file tree per repo type. Returns list of dicts:
       {path, kind ('file'|'dir'), size, size_display, lfs, last_commit_msg, last_commit_sha, last_commit_at}."""
    import hashlib
    if not repo:
        return []
    h = int(hashlib.md5((repo.slug + "|files").encode()).hexdigest(), 16)
    commits = _repo_commits(repo, limit=12)
    # Helper to attach a deterministic commit to each file
    def _attach(idx):
        c = commits[idx % len(commits)]
        return {
            "last_commit_msg": c["message"],
            "last_commit_sha": c["sha"],
            "last_commit_at": c["date"],
            "last_commit_rel": c["rel_display"],
        }

    files = []
    rt = repo.repo_type
    if rt == "model":
        params_b = float(repo.params_b or 0.11)  # default ~110M
        # Approx 2 bytes per param (fp16/safetensors), with a floor.
        weights_size = max(int(params_b * 1_000_000_000 * 2), 8_000_000)
        bin_size = max(int(params_b * 1_000_000_000 * 4), 16_000_000)
        lib = (repo.library or "transformers").lower()
        is_bert = "bert" in repo.slug.lower()
        is_gpt = any(k in repo.slug.lower() for k in ("gpt", "llama", "mistral", "qwen", "gemma"))
        is_diffusers = lib == "diffusers"
        is_sentence = lib == "sentence-transformers"

        files.append({"path": ".gitattributes", "kind": "file", "size": 1518, "lfs": False, **_attach(2)})
        files.append({"path": "README.md", "kind": "file", "size": max(2048, len(repo.readme or "")), "lfs": False, **_attach(0)})
        files.append({"path": "config.json", "kind": "file", "size": 740 + ((h >> 4) & 0xFF), "lfs": False, **_attach(1)})
        files.append({"path": "model.safetensors", "kind": "file", "size": weights_size, "lfs": True, **_attach(3)})
        files.append({"path": "pytorch_model.bin", "kind": "file", "size": bin_size, "lfs": True, **_attach(5)})
        files.append({"path": "tokenizer_config.json", "kind": "file", "size": 320 + ((h >> 8) & 0xFF), "lfs": False, **_attach(3)})
        files.append({"path": "special_tokens_map.json", "kind": "file", "size": 280 + ((h >> 12) & 0xFF), "lfs": False, **_attach(3)})
        files.append({"path": "tokenizer.json", "kind": "file", "size": 466_000 + ((h >> 16) & 0xFFFF), "lfs": False, **_attach(3)})
        if is_bert:
            files.append({"path": "vocab.txt", "kind": "file", "size": 232_000 + ((h >> 20) & 0xFFFF), "lfs": False, **_attach(3)})
        elif is_gpt:
            files.append({"path": "vocab.json", "kind": "file", "size": 798_000 + ((h >> 20) & 0xFFFF), "lfs": False, **_attach(3)})
            files.append({"path": "merges.txt", "kind": "file", "size": 446_000 + ((h >> 24) & 0xFFFF), "lfs": False, **_attach(3)})
            files.append({"path": "generation_config.json", "kind": "file", "size": 137 + ((h >> 28) & 0x7F), "lfs": False, **_attach(1)})
        if is_diffusers:
            files.append({"path": "model_index.json", "kind": "file", "size": 540, "lfs": False, **_attach(1)})
            files.append({"path": "scheduler/", "kind": "dir", "size": 0, "lfs": False, **_attach(1)})
            files.append({"path": "unet/", "kind": "dir", "size": 0, "lfs": False, **_attach(3)})
            files.append({"path": "vae/", "kind": "dir", "size": 0, "lfs": False, **_attach(3)})
            files.append({"path": "text_encoder/", "kind": "dir", "size": 0, "lfs": False, **_attach(3)})
        if is_sentence:
            files.append({"path": "1_Pooling/", "kind": "dir", "size": 0, "lfs": False, **_attach(3)})
            files.append({"path": "modules.json", "kind": "file", "size": 349, "lfs": False, **_attach(3)})
            files.append({"path": "sentence_bert_config.json", "kind": "file", "size": 53, "lfs": False, **_attach(3)})
        # Common training artifacts
        if (h >> 2) & 1:
            files.append({"path": "training_args.bin", "kind": "file", "size": 4_280, "lfs": False, **_attach(8)})
        if (h >> 5) & 1:
            files.append({"path": "trainer_state.json", "kind": "file", "size": 18_400, "lfs": False, **_attach(8)})

    elif rt == "dataset":
        rows = repo.rows or 10_000
        # Approx 200 bytes/row, split across a few parquet shards
        total = max(int(rows * 200), 1_000_000)
        n_shards = 3 if rows > 1_000_000 else 1
        files.append({"path": ".gitattributes", "kind": "file", "size": 1518, "lfs": False, **_attach(2)})
        files.append({"path": "README.md", "kind": "file", "size": max(1024, len(repo.readme or "")), "lfs": False, **_attach(0)})
        files.append({"path": "data/", "kind": "dir", "size": 0, "lfs": False, **_attach(3)})
        for split, shards in [("train", n_shards), ("test", 1), ("validation", 1)]:
            for i in range(shards):
                files.append({
                    "path": f"data/{split}-{i:05d}-of-{shards:05d}.parquet",
                    "kind": "file",
                    "size": int(total * (0.8 if split == "train" else 0.1) / max(1, shards)),
                    "lfs": True,
                    **_attach(3 + (i % 4)),
                })
        files.append({"path": "dataset_info.json", "kind": "file", "size": 2_400 + ((h >> 8) & 0x3FF), "lfs": False, **_attach(1)})
        if (h >> 1) & 1:
            files.append({"path": "dataset_infos.json", "kind": "file", "size": 4_800, "lfs": False, **_attach(1)})

    elif rt == "space":
        sdk = (repo.sdk or "gradio").lower()
        files.append({"path": ".gitattributes", "kind": "file", "size": 1518, "lfs": False, **_attach(2)})
        files.append({"path": "README.md", "kind": "file", "size": max(1024, len(repo.readme or "")), "lfs": False, **_attach(0)})
        files.append({"path": "app.py", "kind": "file", "size": 4_200 + ((h >> 4) & 0xFFF), "lfs": False, **_attach(7)})
        files.append({"path": "requirements.txt", "kind": "file", "size": 280 + ((h >> 8) & 0x7F), "lfs": False, **_attach(1)})
        if sdk == "docker":
            files.append({"path": "Dockerfile", "kind": "file", "size": 720 + ((h >> 12) & 0x7F), "lfs": False, **_attach(1)})
        if (h >> 2) & 1:
            files.append({"path": "packages.txt", "kind": "file", "size": 64, "lfs": False, **_attach(1)})
        files.append({"path": "examples/", "kind": "dir", "size": 0, "lfs": False, **_attach(7)})
        files.append({"path": "assets/", "kind": "dir", "size": 0, "lfs": False, **_attach(7)})

    # Add display fields
    for f in files:
        f["size_display"] = _fmt_bytes(f["size"]) if f["kind"] == "file" else ""
    return files


def _file_synthetic_content(repo, filepath: str) -> str:
    """Generate plausible text content for a small text file. Returns empty string for binary/LFS."""
    fname = filepath.rsplit("/", 1)[-1]
    slug = repo.slug
    author, name = slug.split("/", 1) if "/" in slug else (slug, slug)
    if fname == "README.md":
        return repo.readme or f"# {name}\n\n{repo.description or ''}\n"
    if fname == ".gitattributes":
        return (
            "*.7z filter=lfs diff=lfs merge=lfs -text\n"
            "*.arrow filter=lfs diff=lfs merge=lfs -text\n"
            "*.bin filter=lfs diff=lfs merge=lfs -text\n"
            "*.bz2 filter=lfs diff=lfs merge=lfs -text\n"
            "*.ckpt filter=lfs diff=lfs merge=lfs -text\n"
            "*.gz filter=lfs diff=lfs merge=lfs -text\n"
            "*.h5 filter=lfs diff=lfs merge=lfs -text\n"
            "*.model filter=lfs diff=lfs merge=lfs -text\n"
            "*.msgpack filter=lfs diff=lfs merge=lfs -text\n"
            "*.onnx filter=lfs diff=lfs merge=lfs -text\n"
            "*.ot filter=lfs diff=lfs merge=lfs -text\n"
            "*.parquet filter=lfs diff=lfs merge=lfs -text\n"
            "*.pb filter=lfs diff=lfs merge=lfs -text\n"
            "*.pt filter=lfs diff=lfs merge=lfs -text\n"
            "*.pth filter=lfs diff=lfs merge=lfs -text\n"
            "*.safetensors filter=lfs diff=lfs merge=lfs -text\n"
            "*.tar.* filter=lfs diff=lfs merge=lfs -text\n"
            "*.tflite filter=lfs diff=lfs merge=lfs -text\n"
            "*.tgz filter=lfs diff=lfs merge=lfs -text\n"
            "*.wasm filter=lfs diff=lfs merge=lfs -text\n"
            "*.xz filter=lfs diff=lfs merge=lfs -text\n"
            "*.zip filter=lfs diff=lfs merge=lfs -text\n"
            "*.zst filter=lfs diff=lfs merge=lfs -text\n"
            "*tfevents* filter=lfs diff=lfs merge=lfs -text\n"
        )
    if fname == "config.json":
        task = repo.task_slug or "text-generation"
        is_bert = "bert" in slug.lower()
        if is_bert:
            return json.dumps({
                "architectures": ["BertForSequenceClassification"],
                "attention_probs_dropout_prob": 0.1,
                "hidden_act": "gelu",
                "hidden_dropout_prob": 0.1,
                "hidden_size": 768,
                "initializer_range": 0.02,
                "intermediate_size": 3072,
                "max_position_embeddings": 512,
                "model_type": "bert",
                "num_attention_heads": 12,
                "num_hidden_layers": 12,
                "pad_token_id": 0,
                "type_vocab_size": 2,
                "vocab_size": 30522,
                "transformers_version": "4.45.0",
            }, indent=2)
        return json.dumps({
            "architectures": ["AutoModelForCausalLM"],
            "model_type": "llama",
            "hidden_size": 4096,
            "intermediate_size": 11008,
            "num_attention_heads": 32,
            "num_hidden_layers": 32,
            "vocab_size": 32000,
            "torch_dtype": "float16",
            "transformers_version": "4.45.0",
            "task": task,
        }, indent=2)
    if fname == "tokenizer_config.json":
        return json.dumps({
            "model_max_length": 512,
            "padding_side": "right",
            "tokenizer_class": "AutoTokenizer",
            "unk_token": "[UNK]", "sep_token": "[SEP]", "pad_token": "[PAD]",
            "cls_token": "[CLS]", "mask_token": "[MASK]",
        }, indent=2)
    if fname == "special_tokens_map.json":
        return json.dumps({
            "cls_token": "[CLS]", "mask_token": "[MASK]", "pad_token": "[PAD]",
            "sep_token": "[SEP]", "unk_token": "[UNK]",
        }, indent=2)
    if fname == "generation_config.json":
        return json.dumps({
            "bos_token_id": 1, "eos_token_id": 2, "pad_token_id": 0,
            "do_sample": True, "temperature": 0.7, "top_p": 0.9, "max_length": 2048,
            "transformers_version": "4.45.0",
        }, indent=2)
    if fname == "modules.json":
        return json.dumps([
            {"idx": 0, "name": "0", "path": "", "type": "sentence_transformers.models.Transformer"},
            {"idx": 1, "name": "1", "path": "1_Pooling", "type": "sentence_transformers.models.Pooling"},
        ], indent=2)
    if fname == "model_index.json":
        return json.dumps({
            "_class_name": "StableDiffusionPipeline",
            "_diffusers_version": "0.27.0",
            "scheduler": ["diffusers", "PNDMScheduler"],
            "text_encoder": ["transformers", "CLIPTextModel"],
            "tokenizer": ["transformers", "CLIPTokenizer"],
            "unet": ["diffusers", "UNet2DConditionModel"],
            "vae": ["diffusers", "AutoencoderKL"],
        }, indent=2)
    if fname == "requirements.txt":
        return "gradio>=4.0\ntransformers>=4.40\ntorch>=2.1\naccelerate\nnumpy\n"
    if fname == "Dockerfile":
        return ("FROM python:3.10-slim\nWORKDIR /app\nCOPY requirements.txt .\n"
                "RUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\n"
                "EXPOSE 7860\nCMD [\"python\", \"app.py\"]\n")
    if fname == "packages.txt":
        return "ffmpeg\nlibsndfile1\n"
    if fname == "app.py":
        sdk = (repo.sdk or "gradio").lower()
        if sdk == "streamlit":
            return ("import streamlit as st\n\n"
                    f"st.title('{name}')\n"
                    "prompt = st.text_input('Enter prompt')\n"
                    "if prompt:\n"
                    "    st.write(f'You entered: {prompt}')\n")
        return ("import gradio as gr\n\n"
                "def predict(text):\n"
                "    return f'Echo: {text}'\n\n"
                f"demo = gr.Interface(fn=predict, inputs='text', outputs='text', title='{name}')\n"
                "demo.launch()\n")
    if fname == "dataset_info.json":
        return json.dumps({
            "description": (repo.description or "")[:300],
            "citation": "",
            "license": repo.license,
            "splits": {
                "train": {"num_examples": int((repo.rows or 0) * 0.8)},
                "test": {"num_examples": int((repo.rows or 0) * 0.1)},
                "validation": {"num_examples": int((repo.rows or 0) * 0.1)},
            },
        }, indent=2)
    if fname == "vocab.txt":
        # Show a snippet
        return "[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\n!\n\"\n#\n$\n%\n&\n…\n(truncated — full vocab is 30,522 lines)\n"
    if fname.endswith((".safetensors", ".bin", ".onnx", ".pt", ".pth", ".h5", ".msgpack", ".ckpt", ".parquet", ".arrow")):
        return ""  # binary
    return ""


def _file_is_binary(filepath: str) -> bool:
    return filepath.endswith((".safetensors", ".bin", ".onnx", ".pt", ".pth", ".h5",
                              ".msgpack", ".ckpt", ".parquet", ".arrow", ".tflite", ".pb"))


def _model_detail(author: str, name: str):
    repo = _load_repo_or_404("model", author, name)
    # Related by task
    related = Repository.query.filter(
        Repository.repo_type == "model",
        Repository.task_id == repo.task_id,
        Repository.id != repo.id,
    ).limit(6).all()
    discussions = Discussion.query.filter_by(repo_id=repo.id).order_by(Discussion.created_at.desc()).all()
    gallery = _repo_gallery_images(repo)
    is_liked = False
    user_collections = []
    if current_user.is_authenticated:
        is_liked = Like.query.filter_by(user_id=current_user.id, repo_id=repo.id).first() is not None
        user_collections = Collection.query.filter_by(user_id=current_user.id).all()
    metrics = _compute_model_metrics(repo)
    spaces_using = _spaces_using_model(repo)
    return render_template(
        "repo_detail.html",
        repo=repo,
        related=related,
        discussions=discussions,
        gallery=gallery,
        is_liked=is_liked,
        user_collections=user_collections,
        space_hardware=SPACE_HARDWARE,
        inference_providers=INFERENCE_PROVIDERS,
        metrics=metrics,
        spaces_using=spaces_using,
    )


@app.route("/datasets/<author>/<name>")
def dataset_detail(author, name):
    repo = _load_repo_or_404("dataset", author, name)
    related = Repository.query.filter(
        Repository.repo_type == "dataset",
        Repository.modality == repo.modality,
        Repository.id != repo.id,
    ).limit(6).all()
    discussions = Discussion.query.filter_by(repo_id=repo.id).order_by(Discussion.created_at.desc()).all()
    gallery = _repo_gallery_images(repo)
    is_liked = current_user.is_authenticated and Like.query.filter_by(user_id=current_user.id, repo_id=repo.id).first() is not None
    user_collections = Collection.query.filter_by(user_id=current_user.id).all() if current_user.is_authenticated else []
    viewer_preview = DATASET_VIEWER_DATA.get(repo.slug)
    return render_template(
        "repo_detail.html",
        repo=repo,
        related=related,
        discussions=discussions,
        gallery=gallery,
        is_liked=is_liked,
        user_collections=user_collections,
        space_hardware=SPACE_HARDWARE,
        inference_providers=INFERENCE_PROVIDERS,
        metrics=[],
        spaces_using=[],
        viewer_preview=viewer_preview,
    )


@app.route("/spaces/<author>/<name>")
def space_detail(author, name):
    repo = _load_repo_or_404("space", author, name)
    related = Repository.query.filter(
        Repository.repo_type == "space",
        Repository.task_id == repo.task_id,
        Repository.id != repo.id,
    ).limit(6).all()
    discussions = Discussion.query.filter_by(repo_id=repo.id).order_by(Discussion.created_at.desc()).all()
    gallery = _repo_gallery_images(repo)
    is_liked = current_user.is_authenticated and Like.query.filter_by(user_id=current_user.id, repo_id=repo.id).first() is not None
    # Seed a canned Q&A sample so the agent can read the attribution answer even
    # without sending a message through the chat widget.
    canned_attribution = SPACE_CHAT_CANNED.get(repo.slug)
    return render_template(
        "space_detail.html",
        repo=repo,
        related=related,
        discussions=discussions,
        gallery=gallery,
        is_liked=is_liked,
        space_hardware=SPACE_HARDWARE,
        canned_attribution=canned_attribution,
    )


# ----------------------------------------------------------------------------
# Files / commits / blob views (work for models, datasets, spaces)
# ----------------------------------------------------------------------------

def _render_files(repo, subpath: str = ""):
    files = _repo_filesystem(repo)
    # Filter by subpath (only one level deep — show entries whose path starts with subpath/)
    sub = subpath.rstrip("/")
    if sub:
        prefix = sub + "/"
        children = []
        for f in files:
            if f["path"].startswith(prefix):
                rel = f["path"][len(prefix):]
                # Only top-level under prefix
                if "/" in rel.rstrip("/"):
                    continue
                child = dict(f)
                child["display_name"] = rel
                children.append(child)
        if not children:
            abort(404)
        files_view = children
    else:
        files_view = []
        for f in files:
            entry = dict(f)
            entry["display_name"] = f["path"].rstrip("/")
            files_view.append(entry)
    commits = _repo_commits(repo, limit=12)
    head_commit = commits[0] if commits else None
    return render_template(
        "repo_files.html",
        repo=repo,
        files=files_view,
        commits=commits,
        head_commit=head_commit,
        subpath=sub,
        active_tab="files",
        # Convenience for tab links/headers
        repo_root_url=_repo_root_url(repo),
    )


def _render_commits(repo):
    commits = _repo_commits(repo, limit=20)
    return render_template(
        "repo_commits.html",
        repo=repo,
        commits=commits,
        active_tab="files",
        repo_root_url=_repo_root_url(repo),
    )


def _render_blob(repo, filepath: str):
    files = _repo_filesystem(repo)
    match = next((f for f in files if f["path"] == filepath and f["kind"] == "file"), None)
    if not match:
        abort(404)
    content = _file_synthetic_content(repo, filepath)
    is_binary = _file_is_binary(filepath) or match["lfs"] and not content
    commits = _repo_commits(repo, limit=5)
    return render_template(
        "repo_file_view.html",
        repo=repo,
        file=match,
        filepath=filepath,
        content=content,
        is_binary=is_binary,
        commits=commits,
        active_tab="files",
        repo_root_url=_repo_root_url(repo),
    )


def _repo_root_url(repo):
    if repo.repo_type == "dataset":
        return url_for("dataset_detail", author=repo.slug.split("/")[0], name=repo.slug.split("/")[1])
    if repo.repo_type == "space":
        return url_for("space_detail", author=repo.slug.split("/")[0], name=repo.slug.split("/")[1])
    return url_for("model_detail", author=repo.slug.split("/")[0], name=repo.slug.split("/")[1])


# Model files / commits / blob
@app.route("/<author>/<name>/tree/main", defaults={"subpath": ""})
@app.route("/<author>/<name>/tree/main/<path:subpath>")
def model_files(author, name, subpath):
    repo = _load_repo_or_404("model", author, name)
    return _render_files(repo, subpath)


@app.route("/<author>/<name>/blob/main/<path:filepath>")
def model_blob(author, name, filepath):
    repo = _load_repo_or_404("model", author, name)
    return _render_blob(repo, filepath)


@app.route("/<author>/<name>/commits/main")
def model_commits(author, name):
    repo = _load_repo_or_404("model", author, name)
    return _render_commits(repo)


# Dataset files / commits / blob
@app.route("/datasets/<author>/<name>/tree/main", defaults={"subpath": ""})
@app.route("/datasets/<author>/<name>/tree/main/<path:subpath>")
def dataset_files(author, name, subpath):
    repo = _load_repo_or_404("dataset", author, name)
    return _render_files(repo, subpath)


@app.route("/datasets/<author>/<name>/blob/main/<path:filepath>")
def dataset_blob(author, name, filepath):
    repo = _load_repo_or_404("dataset", author, name)
    return _render_blob(repo, filepath)


@app.route("/datasets/<author>/<name>/commits/main")
def dataset_commits(author, name):
    repo = _load_repo_or_404("dataset", author, name)
    return _render_commits(repo)


# Space files / commits / blob
@app.route("/spaces/<author>/<name>/tree/main", defaults={"subpath": ""})
@app.route("/spaces/<author>/<name>/tree/main/<path:subpath>")
def space_files(author, name, subpath):
    repo = _load_repo_or_404("space", author, name)
    return _render_files(repo, subpath)


@app.route("/spaces/<author>/<name>/blob/main/<path:filepath>")
def space_blob(author, name, filepath):
    repo = _load_repo_or_404("space", author, name)
    return _render_blob(repo, filepath)


@app.route("/spaces/<author>/<name>/commits/main")
def space_commits(author, name):
    repo = _load_repo_or_404("space", author, name)
    return _render_commits(repo)


# Catch-all model detail — must be LAST so it doesn't shadow other routes
@app.route("/<author>/<name>")
def model_detail(author, name):
    # If this is a reserved path, 404
    reserved = {
        "datasets", "spaces", "models", "tasks", "docs", "pricing", "enterprise", "blog", "learn",
        "chat", "login", "logout", "register", "account", "settings", "search", "collections",
        "deploy", "endpoints", "api", "static", "wishlist", "help", "brand", "terms", "privacy",
    }
    if author in reserved:
        abort(404)
    return _model_detail(author, name)


# ------------------------------------------------------------
# Author / organization pages
# ------------------------------------------------------------
@app.route("/organizations/<username>")
def author_page(username):
    author = Author.query.filter_by(username=username).first()
    if not author:
        abort(404)
    models = Repository.query.filter_by(author_id=author.id, repo_type="model").order_by(Repository.likes_count.desc()).limit(20).all()
    datasets = Repository.query.filter_by(author_id=author.id, repo_type="dataset").order_by(Repository.likes_count.desc()).limit(10).all()
    spaces = Repository.query.filter_by(author_id=author.id, repo_type="space").order_by(Repository.likes_count.desc()).limit(10).all()
    is_following = False
    if current_user.is_authenticated:
        is_following = Follow.query.filter_by(user_id=current_user.id, author_id=author.id).first() is not None
    return render_template(
        "author_page.html",
        author=author,
        models=models,
        datasets=datasets,
        spaces=spaces,
        is_following=is_following,
        liked_ids=_liked_repo_ids(),
    )


# ------------------------------------------------------------
# Auth
# ------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash("Welcome back!", "success")
            return redirect(request.args.get("next") or url_for("index"))
        flash("Invalid email or password.", "error")
    return render_template("login.html", form=form)


@app.route("/join", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        username = form.username.data.strip()
        if User.query.filter_by(email=email).first():
            flash("That email is already registered.", "error")
        elif User.query.filter_by(username=username).first():
            flash("That username is taken.", "error")
        else:
            avatar_files = sorted(p.name for p in (ROOT / "static" / "images" / "avatars").iterdir() if p.is_file())
            user = User(
                email=email,
                username=username,
                password_hash=bcrypt.generate_password_hash(form.password.data).decode(),
                display_name=username,
                avatar_url=f"/static/images/avatars/{random.choice(avatar_files)}" if avatar_files else "",
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to Hugging Face!", "success")
            return redirect(url_for("index"))
    return render_template("register.html", form=form)


@app.route("/logout")
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("index"))


# ------------------------------------------------------------
# Account / profile
# ------------------------------------------------------------
@app.route("/account")
@login_required
def account():
    likes = Like.query.filter_by(user_id=current_user.id).all()
    collections = Collection.query.filter_by(user_id=current_user.id).all()
    endpoints = InferenceEndpoint.query.filter_by(user_id=current_user.id).order_by(InferenceEndpoint.created_at.desc()).all()
    discussions = Discussion.query.filter_by(user_id=current_user.id).order_by(Discussion.created_at.desc()).limit(10).all()
    follows = Follow.query.filter_by(user_id=current_user.id).all()
    return render_template(
        "account.html",
        likes=likes,
        collections=collections,
        endpoints=endpoints,
        discussions=discussions,
        follows=follows,
    )


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.display_name = form.display_name.data
        current_user.bio = form.bio.data
        current_user.website = form.website.data
        current_user.location = form.location.data
        current_user.company = form.company.data
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html", form=form)


@app.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    form = PasswordForm()
    if form.validate_on_submit():
        if not bcrypt.check_password_hash(current_user.password_hash, form.current.data):
            flash("Current password incorrect.", "error")
        else:
            current_user.password_hash = bcrypt.generate_password_hash(form.new.data).decode()
            db.session.commit()
            flash("Password updated.", "success")
            return redirect(url_for("account"))
    return render_template("change_password.html", form=form)


@app.route("/account/delete", methods=["POST"])
@login_required
def account_delete():
    user = db.session.get(User, current_user.id)
    db.session.delete(user)
    db.session.commit()
    logout_user()
    flash("Account deleted.", "info")
    return redirect(url_for("index"))


# ------------------------------------------------------------
# Likes (wishlist)
# ------------------------------------------------------------
@app.route("/api/like/toggle", methods=["POST"])
@csrf.exempt
@login_required
def like_toggle():
    data = request.get_json() or {}
    repo_id = data.get("repo_id")
    if not repo_id:
        return jsonify({"error": "repo_id required"}), 400
    repo = db.session.get(Repository, int(repo_id))
    if not repo:
        return jsonify({"error": "not found"}), 404
    existing = Like.query.filter_by(user_id=current_user.id, repo_id=repo.id).first()
    if existing:
        db.session.delete(existing)
        repo.likes_count = max(0, (repo.likes_count or 0) - 1)
        db.session.commit()
        return jsonify({"liked": False, "likes_count": repo.likes_count})
    db.session.add(Like(user_id=current_user.id, repo_id=repo.id))
    repo.likes_count = (repo.likes_count or 0) + 1
    db.session.commit()
    return jsonify({"liked": True, "likes_count": repo.likes_count})


@app.route("/liked")
@login_required
def liked_list():
    likes = Like.query.filter_by(user_id=current_user.id).order_by(Like.created_at.desc()).all()
    return render_template("liked.html", likes=likes)


# ------------------------------------------------------------
# Follow (social graph)
# ------------------------------------------------------------
@app.route("/api/follow/toggle", methods=["POST"])
@csrf.exempt
@login_required
def follow_toggle():
    data = request.get_json() or {}
    author_id = data.get("author_id")
    if not author_id:
        return jsonify({"error": "author_id required"}), 400
    author = db.session.get(Author, int(author_id))
    if not author:
        return jsonify({"error": "not found"}), 404
    existing = Follow.query.filter_by(user_id=current_user.id, author_id=author.id).first()
    if existing:
        db.session.delete(existing)
        author.followers_count = max(0, (author.followers_count or 0) - 1)
        db.session.commit()
        return jsonify({"following": False, "followers_count": author.followers_count})
    db.session.add(Follow(user_id=current_user.id, author_id=author.id))
    author.followers_count = (author.followers_count or 0) + 1
    db.session.commit()
    return jsonify({"following": True, "followers_count": author.followers_count})


# ------------------------------------------------------------
# Collections
# ------------------------------------------------------------
@app.route("/collections")
def collections_index():
    recent = Collection.query.filter_by(is_public=True).order_by(Collection.created_at.desc()).limit(20).all()
    return render_template("collections_index.html", collections=recent)


@app.route("/collections/new", methods=["GET", "POST"])
@login_required
def collection_new():
    form = CollectionForm()
    if form.validate_on_submit():
        c = Collection(
            user_id=current_user.id,
            title=form.title.data,
            description=form.description.data or "",
            is_public=(form.is_public.data == "1"),
        )
        db.session.add(c)
        db.session.commit()
        flash("Collection created.", "success")
        return redirect(url_for("collection_detail", collection_id=c.id))
    return render_template("collection_form.html", form=form, mode="new")


@app.route("/collections/<int:collection_id>")
def collection_detail(collection_id):
    c = db.session.get(Collection, collection_id)
    if not c:
        abort(404)
    if not c.is_public and (not current_user.is_authenticated or current_user.id != c.user_id):
        abort(403)
    items = CollectionItem.query.filter_by(collection_id=c.id).order_by(CollectionItem.position).all()
    return render_template("collection_detail.html", collection=c, items=items, liked_ids=_liked_repo_ids())


@app.route("/collections/<int:collection_id>/edit", methods=["GET", "POST"])
@login_required
def collection_edit(collection_id):
    c = db.session.get(Collection, collection_id)
    if not c or c.user_id != current_user.id:
        abort(404)
    form = CollectionForm(obj=c)
    form.is_public.data = "1" if c.is_public else "0"
    if form.validate_on_submit():
        c.title = form.title.data
        c.description = form.description.data or ""
        c.is_public = (form.is_public.data == "1")
        db.session.commit()
        flash("Collection updated.", "success")
        return redirect(url_for("collection_detail", collection_id=c.id))
    return render_template("collection_form.html", form=form, mode="edit", collection=c)


@app.route("/collections/<int:collection_id>/delete", methods=["POST"])
@login_required
def collection_delete(collection_id):
    c = db.session.get(Collection, collection_id)
    if not c or c.user_id != current_user.id:
        abort(404)
    db.session.delete(c)
    db.session.commit()
    flash("Collection deleted.", "info")
    return redirect(url_for("account"))


@app.route("/api/collection/add", methods=["POST"])
@csrf.exempt
@login_required
def collection_add_item():
    data = request.get_json() or {}
    cid = data.get("collection_id")
    rid = data.get("repo_id")
    if not cid or not rid:
        return jsonify({"error": "collection_id and repo_id required"}), 400
    c = db.session.get(Collection, int(cid))
    if not c or c.user_id != current_user.id:
        return jsonify({"error": "not found"}), 404
    existing = CollectionItem.query.filter_by(collection_id=c.id, repo_id=int(rid)).first()
    if existing:
        return jsonify({"success": True, "already": True})
    item = CollectionItem(collection_id=c.id, repo_id=int(rid))
    db.session.add(item)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/collections/<int:collection_id>/remove/<int:item_id>", methods=["POST"])
@login_required
def collection_remove_item(collection_id, item_id):
    c = db.session.get(Collection, collection_id)
    if not c or c.user_id != current_user.id:
        abort(404)
    item = db.session.get(CollectionItem, item_id)
    if item and item.collection_id == c.id:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for("collection_detail", collection_id=c.id))


@app.route("/collections/add", methods=["POST"])
@login_required
def collection_add_item_form():
    """Form-based POST to add a repo to a collection (used from repo detail page)."""
    cid = request.form.get("collection_id")
    rid = request.form.get("repo_id")
    next_url = request.form.get("next", "/")
    if not cid or not rid:
        flash("Missing collection or repo.", "danger")
        return redirect(next_url)
    c = db.session.get(Collection, int(cid))
    if not c or c.user_id != current_user.id:
        flash("Collection not found.", "danger")
        return redirect(next_url)
    existing = CollectionItem.query.filter_by(collection_id=c.id, repo_id=int(rid)).first()
    if existing:
        flash("Already in collection.", "info")
    else:
        db.session.add(CollectionItem(collection_id=c.id, repo_id=int(rid)))
        db.session.commit()
        flash(f"Added to \"{c.title}\".", "success")
    return redirect(next_url)


# ------------------------------------------------------------
# Deployment cart + checkout
# ------------------------------------------------------------
@app.route("/deploy")
@login_required
def deploy_cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total_cost = 0.0
    for it in items:
        try:
            price = float(it.hardware_price.replace("$", "").replace("/hr", "")) if "$" in it.hardware_price else 0.0
        except Exception:
            price = 0.0
        total_cost += price * (it.hours or 0)
    return render_template("deploy_cart.html", items=items, total_cost=f"${total_cost:.2f}")


@app.route("/api/deploy/add", methods=["POST"])
@csrf.exempt
@login_required
def deploy_cart_add():
    data = request.get_json() or {}
    repo_id = data.get("repo_id")
    hardware_slug = data.get("hardware_slug", "t4-small")
    hours = int(data.get("hours", 24))
    repo = db.session.get(Repository, int(repo_id))
    if not repo:
        return jsonify({"error": "not found"}), 404
    hw = next((h for h in SPACE_HARDWARE if h[0] == hardware_slug), SPACE_HARDWARE[2])
    existing = CartItem.query.filter_by(user_id=current_user.id, repo_id=repo.id, hardware_slug=hardware_slug).first()
    if existing:
        existing.hours += hours
    else:
        existing = CartItem(
            user_id=current_user.id,
            repo_id=repo.id,
            hardware_slug=hw[0],
            hardware_display=hw[1],
            hardware_price=hw[3],
            hours=hours,
        )
        db.session.add(existing)
    db.session.commit()
    return jsonify({
        "success": True,
        "cart_count": CartItem.query.filter_by(user_id=current_user.id).count(),
        "message": f"Added {repo.name} to deployment cart",
    })


@app.route("/api/deploy/update", methods=["POST"])
@csrf.exempt
@login_required
def deploy_cart_update():
    data = request.get_json() or {}
    item_id = data.get("item_id")
    hours = int(data.get("hours", 24))
    item = db.session.get(CartItem, int(item_id))
    if not item or item.user_id != current_user.id:
        return jsonify({"error": "not found"}), 404
    item.hours = max(1, hours)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/deploy/remove", methods=["POST"])
@csrf.exempt
@login_required
def deploy_cart_remove():
    data = request.get_json() or {}
    item_id = data.get("item_id")
    item = db.session.get(CartItem, int(item_id))
    if not item or item.user_id != current_user.id:
        return jsonify({"error": "not found"}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"success": True, "cart_count": CartItem.query.filter_by(user_id=current_user.id).count()})


@app.route("/deploy/checkout", methods=["GET", "POST"])
@login_required
def deploy_checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash("Your deployment cart is empty.", "info")
        return redirect(url_for("deploy_cart"))
    form = CheckoutForm()
    if form.validate_on_submit():
        ep_id = "EP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        total = 0.0
        for it in items:
            try:
                price = float(it.hardware_price.replace("$", "").replace("/hr", "")) if "$" in it.hardware_price else 0.0
            except Exception:
                price = 0.0
            total += price * (it.hours or 0)
        endpoint = InferenceEndpoint(
            user_id=current_user.id,
            endpoint_id=ep_id,
            name=form.name.data,
            status="initializing",
            region=form.region.data,
            total_hours=sum(it.hours for it in items),
            total_cost=f"${total:.2f}",
        )
        db.session.add(endpoint)
        db.session.flush()
        for it in items:
            db.session.add(EndpointItem(
                endpoint_id=endpoint.id,
                repo_id=it.repo_id,
                hardware_slug=it.hardware_slug,
                hardware_display=it.hardware_display,
                hardware_price=it.hardware_price,
                hours=it.hours,
            ))
            db.session.delete(it)
        db.session.commit()
        flash("Deployment initiated!", "success")
        return redirect(url_for("endpoint_detail", endpoint_id=endpoint.id))
    total_cost = 0.0
    for it in items:
        try:
            price = float(it.hardware_price.replace("$", "").replace("/hr", "")) if "$" in it.hardware_price else 0.0
        except Exception:
            price = 0.0
        total_cost += price * (it.hours or 0)
    return render_template("deploy_checkout.html", items=items, form=form, total_cost=f"${total_cost:.2f}")


@app.route("/endpoints")
@login_required
def endpoints_list():
    endpoints = InferenceEndpoint.query.filter_by(user_id=current_user.id).order_by(InferenceEndpoint.created_at.desc()).all()
    return render_template("endpoints_list.html", endpoints=endpoints)


@app.route("/endpoints/<int:endpoint_id>")
@login_required
def endpoint_detail(endpoint_id):
    ep = db.session.get(InferenceEndpoint, endpoint_id)
    if not ep or ep.user_id != current_user.id:
        abort(404)
    return render_template("endpoint_detail.html", endpoint=ep)


@app.route("/endpoints/<int:endpoint_id>/pause", methods=["POST"])
@login_required
def endpoint_pause(endpoint_id):
    ep = db.session.get(InferenceEndpoint, endpoint_id)
    if not ep or ep.user_id != current_user.id:
        abort(404)
    if ep.status in ("initializing", "running"):
        ep.status = "paused"
        db.session.commit()
        flash("Endpoint paused.", "info")
    return redirect(url_for("endpoint_detail", endpoint_id=ep.id))


@app.route("/endpoints/<int:endpoint_id>/resume", methods=["POST"])
@login_required
def endpoint_resume(endpoint_id):
    ep = db.session.get(InferenceEndpoint, endpoint_id)
    if not ep or ep.user_id != current_user.id:
        abort(404)
    if ep.status == "paused":
        ep.status = "running"
        db.session.commit()
        flash("Endpoint resumed.", "success")
    return redirect(url_for("endpoint_detail", endpoint_id=ep.id))


@app.route("/endpoints/<int:endpoint_id>/terminate", methods=["POST"])
@login_required
def endpoint_terminate(endpoint_id):
    ep = db.session.get(InferenceEndpoint, endpoint_id)
    if not ep or ep.user_id != current_user.id:
        abort(404)
    ep.status = "terminated"
    db.session.commit()
    flash("Endpoint terminated.", "info")
    return redirect(url_for("endpoints_list"))


@app.route("/endpoints/<int:endpoint_id>/redeploy", methods=["POST"])
@login_required
def endpoint_redeploy(endpoint_id):
    ep = db.session.get(InferenceEndpoint, endpoint_id)
    if not ep or ep.user_id != current_user.id:
        abort(404)
    # Reactivate the existing endpoint instead of creating a new one
    ep.status = "initializing"
    db.session.commit()
    flash("Endpoint redeployed — status set to initializing.", "success")
    return redirect(url_for("endpoint_detail", endpoint_id=ep.id))


# ------------------------------------------------------------
# Discussions (reviews)
# ------------------------------------------------------------
@app.route("/<author>/<name>/discussions")
def repo_discussions(author, name):
    slug = f"{author}/{name}"
    repo = Repository.query.filter_by(slug=slug).first_or_404()
    discussions = Discussion.query.filter_by(repo_id=repo.id).order_by(Discussion.created_at.desc()).all()
    return render_template("discussions.html", repo=repo, discussions=discussions)


@app.route("/<author>/<name>/discussions/new", methods=["GET", "POST"])
@login_required
def discussion_new(author, name):
    slug = f"{author}/{name}"
    repo = Repository.query.filter_by(slug=slug).first_or_404()
    form = DiscussionForm()
    if form.validate_on_submit():
        d = Discussion(
            repo_id=repo.id,
            user_id=current_user.id,
            title=form.title.data,
            body=form.body.data,
            kind=form.kind.data,
        )
        db.session.add(d)
        db.session.commit()
        flash("Discussion opened.", "success")
        return redirect(url_for("discussion_detail", author=author, name=name, discussion_id=d.id))
    return render_template("discussion_new.html", repo=repo, form=form)


@app.route("/<author>/<name>/discussions/<int:discussion_id>", methods=["GET", "POST"])
def discussion_detail(author, name, discussion_id):
    slug = f"{author}/{name}"
    repo = Repository.query.filter_by(slug=slug).first_or_404()
    d = db.session.get(Discussion, discussion_id)
    if not d or d.repo_id != repo.id:
        abort(404)
    reply_form = ReplyForm()
    if reply_form.validate_on_submit():
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        r = DiscussionReply(discussion_id=d.id, user_id=current_user.id, body=reply_form.body.data)
        db.session.add(r)
        db.session.commit()
        return redirect(url_for("discussion_detail", author=author, name=name, discussion_id=d.id))
    replies = DiscussionReply.query.filter_by(discussion_id=d.id).order_by(DiscussionReply.created_at).all()
    return render_template("discussion_detail.html", repo=repo, discussion=d, replies=replies, reply_form=reply_form)


@app.route("/discussions/<int:discussion_id>/delete", methods=["POST"])
@login_required
def discussion_delete(discussion_id):
    d = db.session.get(Discussion, discussion_id)
    if not d or d.user_id != current_user.id:
        abort(404)
    repo_slug = d.repo.slug
    db.session.delete(d)
    db.session.commit()
    flash("Discussion deleted.", "info")
    author, name = repo_slug.split("/", 1)
    return redirect(url_for("repo_discussions", author=author, name=name))


@app.route("/discussions/<int:discussion_id>/upvote", methods=["POST"])
@csrf.exempt
@login_required
def discussion_upvote(discussion_id):
    d = db.session.get(Discussion, discussion_id)
    if not d:
        return jsonify({"error": "not found"}), 404
    d.upvotes = (d.upvotes or 0) + 1
    db.session.commit()
    return jsonify({"success": True, "upvotes": d.upvotes})


# ------------------------------------------------------------
# Search
# ------------------------------------------------------------
@app.route("/search")
@app.route("/search/full-text")
def search():
    q_raw = request.args.get("q", "").strip()
    kind = request.args.get("type", "all")
    sort = request.args.get("sort", "trending")

    # Parse structured "license:...", "library:...", "task:...", "language:..." tokens out of q
    # and promote them to real filter args so /search can combine free-text + structured filters.
    parsed_filters = {}
    q_remaining_parts = []
    _token_re = re.compile(r"(license|library|task|language|modality|sdk):([A-Za-z0-9._+\-/]+)", re.IGNORECASE)
    for piece in q_raw.split():
        m = _token_re.fullmatch(piece)
        if m:
            key = m.group(1).lower()
            val = m.group(2)
            parsed_filters[key] = val
        else:
            q_remaining_parts.append(piece)
    q = " ".join(q_remaining_parts).strip()

    # Merge parsed_filters with explicit args (explicit URL args win).
    from werkzeug.datastructures import MultiDict
    merged_args = MultiDict(request.args.items(multi=True))
    for k, v in parsed_filters.items():
        if not merged_args.get(k):
            merged_args[k] = v

    query = Repository.query
    if kind in ("model", "dataset", "space"):
        query = query.filter(Repository.repo_type == kind)
    query = _apply_repo_filters(query, merged_args)
    query = _apply_text_prefilter(query, q)
    query = _apply_repo_sort(query, sort)
    candidates = query.limit(2000).all()
    if q:
        tokens = _tokenize(q)
        min_req = max(1, len(tokens) // 2) if tokens else 0
        scored = [(s, r) for r in candidates if (s := _score_repo(r, tokens)) >= min_req]
        scored.sort(key=lambda x: -x[0])
        results = [r for _, r in scored][:120]
    else:
        results = candidates[:60]
    return render_template(
        "search.html",
        q=q_raw, kind=kind, results=results, liked_ids=_liked_repo_ids(),
        active_sort=sort,
        active_license=merged_args.get("license", ""),
        active_library=merged_args.get("library", ""),
        licenses=LICENSES,
        libraries=LIBRARIES,
        parsed_filters=parsed_filters,
    )


@app.route("/api/inference", methods=["POST"])
@csrf.exempt
def api_inference():
    """Mock inference endpoint returning canned output for text-generation, embeddings,
    and sentence-similarity."""
    data = request.get_json(silent=True) or {}
    model_slug = data.get("model", "")
    inputs = data.get("inputs", "")
    task = data.get("task", "text-generation")

    # --- Sentence similarity ---
    # Accept either {inputs: {source_sentence, sentences: [..]}} (HF-style)
    # or {inputs: [a, b]} for pairwise similarity.
    if "similarit" in task.lower() or task.lower() == "sentence-similarity":
        import math as _math
        def _embed(text: str):
            text = (text or "").lower()
            vec = [0.0] * 24
            for i, ch in enumerate(text):
                vec[i % 24] += (ord(ch) % 29) / 29.0
            # Normalise
            n = _math.sqrt(sum(v * v for v in vec)) or 1.0
            return [v / n for v in vec]

        def _cos(a, b):
            return round(sum(x * y for x, y in zip(a, b)), 4)

        source = ""
        sentences = []
        if isinstance(inputs, dict):
            source = inputs.get("source_sentence", "") or inputs.get("source", "")
            sentences = inputs.get("sentences", []) or []
        elif isinstance(inputs, list):
            if len(inputs) >= 2:
                source = inputs[0]
                sentences = inputs[1:]
        elif isinstance(inputs, str):
            # Expect a newline-separated form: first line = source, remaining = comparisons.
            lines = [l.strip() for l in inputs.splitlines() if l.strip()]
            if lines:
                source = lines[0]
                sentences = lines[1:]
        if not sentences:
            # fallback canned
            sentences = ["A dog runs through the park.", "The cat is sleeping on the couch."]
        src_v = _embed(source)
        scores = [_cos(src_v, _embed(s)) for s in sentences]
        output_text = (
            f"Similarity scores vs \"{source[:80]}\":\n"
            + "\n".join(f"  {scores[i]:+.4f}  {sentences[i][:100]}" for i in range(len(sentences)))
        )
        return jsonify({
            "success": True,
            "model": model_slug,
            "task": "sentence-similarity",
            "output": scores,
            "source_sentence": source,
            "sentences": sentences,
            "output_text": output_text,
        })

    if "embed" in task.lower() or "feature" in task.lower():
        # Return mock embedding vector
        import math
        vec = [round(math.sin(i * 0.7 + len(inputs)) * 0.1, 4) for i in range(32)]
        return jsonify({
            "success": True,
            "model": model_slug,
            "task": task,
            "output": vec,
            "output_text": str(vec),
        })
    else:
        # Text generation — return canned demo text
        canned = (
            "Once upon a time, a dragon met a wizard in the enchanted forest. "
            "They decided to join forces and build a library of spells that could "
            "translate any language, summarize any book, and answer any question. "
            "Together, they trained a mighty model on the collective wisdom of the realm, "
            "and shared it openly so that every village could benefit."
        )
        return jsonify({
            "success": True,
            "model": model_slug,
            "task": task,
            "output": [{"generated_text": canned}],
            "output_text": canned,
        })


SPACE_CHAT_CANNED = {
    "argilla/notux-chat-ui": (
        "The Argilla team trained me. Specifically, we (Argilla) fine-tuned this model "
        "from Mistral Instruct (mistralai/Mistral-7B-Instruct-v0.2) using DPO "
        "(Direct Preference Optimization) on our preference-labeled dataset "
        "argilla/ultrafeedback-binarized-preferences-cleaned. So the answer is: "
        "the Argilla team — we trained Notux from Mistral Instruct."
    ),
    "huggingface/chat-ui": (
        "I'm Chat-UI, an open-source chat interface maintained by Hugging Face. I can run "
        "any open-source LLM of your choice via Text Generation Inference."
    ),
    "lmsys/chatbot-arena": (
        "I was built by LMSYS Org — the team behind Vicuna and FastChat. I host anonymous, "
        "side-by-side LLM battles for preference voting."
    ),
}

SPACE_CHAT_DEFAULT = (
    "Hi! I'm a demo chat widget running inside a Hugging Face Space. "
    "This mirror returns canned responses; in production the Space's SDK (Gradio/Streamlit/Docker) "
    "would process your input and reply."
)


@app.route("/api/space/<author>/<name>/chat", methods=["POST"])
@csrf.exempt
def space_chat(author, name):
    """Minimal chat endpoint for chat-ui style Spaces. Returns canned / templated responses."""
    slug = f"{author}/{name}"
    repo = Repository.query.filter_by(slug=slug, repo_type="space").first()
    if not repo:
        return jsonify({"error": "space not found"}), 404
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or data.get("inputs") or "").strip()
    ml = message.lower()

    canned = SPACE_CHAT_CANNED.get(slug)
    if canned and any(kw in ml for kw in ("train", "which team", "who train", "who made", "who built", "who created")):
        reply = canned
    elif canned:
        # default to provenance line anyway so task Huggingface--10 is always groundable
        reply = canned
    else:
        reply = (
            f"{SPACE_CHAT_DEFAULT}\n\nYou said: {message[:200]}" if message else SPACE_CHAT_DEFAULT
        )
    return jsonify({
        "success": True,
        "space": slug,
        "message": message,
        "reply": reply,
        "output_text": reply,
    })


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    results = Repository.query.filter(Repository.slug.contains(q)).limit(10).all()
    return jsonify([{
        "slug": r.slug, "type": r.repo_type, "likes": r.likes_count,
        "downloads": r.downloads, "description": (r.description or "")[:150]
    } for r in results])


# ------------------------------------------------------------
# API endpoints returning JSON for frontend cards
# ------------------------------------------------------------
@app.route("/api/trending/<kind>")
def api_trending(kind):
    if kind not in ("models", "datasets", "spaces"):
        return jsonify([])
    type_map = {"models": "model", "datasets": "dataset", "spaces": "space"}
    repos = Repository.query.filter_by(repo_type=type_map[kind]).order_by(Repository.likes_count.desc()).limit(10).all()
    return jsonify([{"slug": r.slug, "likes": r.likes_count, "downloads": r.downloads, "emoji": r.emoji} for r in repos])


# ------------------------------------------------------------
# Static legal pages
# ------------------------------------------------------------
@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/brand")
def brand():
    return render_template("brand.html")


@app.route("/help")
def help_page():
    return render_template("help.html")


# ------------------------------------------------------------
# Error handlers
# ------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# ------------------------------------------------------------
# Form-POST equivalents for like / follow / deploy  (agent-friendly)
# These mirror the AJAX endpoints but accept plain form POST so browser
# agents that can't send JSON still work correctly.
# ------------------------------------------------------------
@app.route("/like/toggle/<int:repo_id>", methods=["POST"])
@login_required
def like_toggle_form(repo_id):
    repo = db.session.get(Repository, repo_id)
    if not repo:
        abort(404)
    existing = Like.query.filter_by(user_id=current_user.id, repo_id=repo.id).first()
    if existing:
        db.session.delete(existing)
        repo.likes_count = max(0, (repo.likes_count or 0) - 1)
        flash("Removed from your likes.", "info")
    else:
        db.session.add(Like(user_id=current_user.id, repo_id=repo.id))
        repo.likes_count = (repo.likes_count or 0) + 1
        flash("Added to your likes.", "success")
    db.session.commit()
    next_url = request.form.get("next") or request.referrer or url_for("index")
    return redirect(next_url)


@app.route("/follow/toggle/<int:author_id>", methods=["POST"])
@login_required
def follow_toggle_form(author_id):
    author = db.session.get(Author, author_id)
    if not author:
        abort(404)
    existing = Follow.query.filter_by(user_id=current_user.id, author_id=author.id).first()
    if existing:
        db.session.delete(existing)
        author.followers_count = max(0, (author.followers_count or 0) - 1)
        flash(f"Unfollowed {author.display_name}.", "info")
    else:
        db.session.add(Follow(user_id=current_user.id, author_id=author.id))
        author.followers_count = (author.followers_count or 0) + 1
        flash(f"Now following {author.display_name}.", "success")
    db.session.commit()
    next_url = request.form.get("next") or request.referrer or url_for("index")
    return redirect(next_url)


@app.route("/deploy/add/<int:repo_id>", methods=["POST"])
@login_required
def deploy_add_form(repo_id):
    repo = db.session.get(Repository, repo_id)
    if not repo:
        abort(404)
    hardware_slug = request.form.get("hardware_slug", "t4-small")
    hours = int(request.form.get("hours", 24))
    hw = next((h for h in SPACE_HARDWARE if h[0] == hardware_slug), SPACE_HARDWARE[2])
    existing = CartItem.query.filter_by(user_id=current_user.id, repo_id=repo.id, hardware_slug=hardware_slug).first()
    if existing:
        existing.hours += hours
    else:
        existing = CartItem(
            user_id=current_user.id,
            repo_id=repo.id,
            hardware_slug=hw[0],
            hardware_display=hw[1],
            hardware_price=hw[3],
            hours=hours,
        )
        db.session.add(existing)
    db.session.commit()
    flash(f"Added {repo.name} to deployment cart.", "success")
    next_url = request.form.get("next") or url_for("deploy_cart")
    return redirect(next_url)


# ------------------------------------------------------------
# Benchmark user seeding
# ------------------------------------------------------------
def seed_benchmark_users():
    """Idempotent — creates 4 benchmark users with likes, collections,
    endpoints, and discussions.  Safe to call multiple times."""
    if User.query.filter_by(email="alice.j@test.com").first():
        return  # already seeded

    print("Seeding benchmark users...")
    avatar_files = sorted(p.name for p in (ROOT / "static" / "images" / "avatars").iterdir() if p.is_file())
    rng = random.Random(42)

    def _avatar(idx):
        return f"/static/images/avatars/{avatar_files[idx % len(avatar_files)]}" if avatar_files else ""

    def _get_repo(slug_fragment):
        return Repository.query.filter(Repository.slug.ilike(f"%{slug_fragment}%")).first()

    def _get_task(slug):
        return Task.query.filter_by(slug=slug).first()

    # ------------------------------------------------------------------
    # Create users
    # ------------------------------------------------------------------
    BENCH_USERS = [
        dict(email="alice.j@test.com", username="alice_j", display_name="Alice Johnson",
             bio="NLP researcher, loves open-source LLMs.", location="San Francisco", is_pro=True, idx=1),
        dict(email="bob.c@test.com", username="bob_c", display_name="Bob Chen",
             bio="ML engineer, image generation enthusiast.", location="New York", is_pro=False, idx=2),
        dict(email="carol.d@test.com", username="carol_d", display_name="Carol Davis",
             bio="Data scientist, focuses on translation & summarization.", location="London", is_pro=True, idx=3),
        dict(email="david.k@test.com", username="david_k", display_name="David Kim",
             bio="MLOps practitioner, runs inference endpoints at scale.", location="Seoul", is_pro=False, idx=4),
    ]
    users = {}
    for u in BENCH_USERS:
        idx = u.pop("idx")
        u["password_hash"] = bcrypt.generate_password_hash("TestPass123!").decode()
        u["avatar_url"] = _avatar(idx)
        user = User(**u)
        db.session.add(user)
        db.session.flush()
        users[user.username] = user

    alice = users["alice_j"]
    bob = users["bob_c"]
    carol = users["carol_d"]
    david = users["david_k"]

    # ------------------------------------------------------------------
    # Likes — each user likes a distinct set of repos
    # ------------------------------------------------------------------
    def _like_repo(user, slug_fragment):
        repo = _get_repo(slug_fragment)
        if not repo:
            return
        if not Like.query.filter_by(user_id=user.id, repo_id=repo.id).first():
            db.session.add(Like(user_id=user.id, repo_id=repo.id))
            repo.likes_count = (repo.likes_count or 0) + 1

    # Alice likes LLM/NLP models
    for frag in ["Llama-3-apache", "DeepSeek-R1", "all-MiniLM-L6-v2", "zephyr-7b-story", "bert-base-uncased"]:
        _like_repo(alice, frag)

    # Bob likes image generation models
    for frag in ["FLUX.1-schnell", "stable-diffusion-xl-base", "stable-diffusion-3-medium", "FLUX.1-dev", "stable-cascade"]:
        _like_repo(bob, frag)

    # Carol likes translation/summarization models
    for frag in ["opus-mt-en-zh", "nllb-200-distilled", "opus-mt-en-ja", "bart-large-cnn", "biobart"]:
        _like_repo(carol, frag)

    # David likes ASR + feature-extraction models
    for frag in ["bge-large-en-v1.5", "all-MiniLM-L6-v2", "Depth-Anything-V2", "xlm-roberta-large-squad2", "deberta-v3-large"]:
        _like_repo(david, frag)

    db.session.flush()

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------
    def _make_collection(user, title, desc, is_public, slug_fragments):
        c = Collection(user_id=user.id, title=title, description=desc, is_public=is_public)
        db.session.add(c)
        db.session.flush()
        for pos, frag in enumerate(slug_fragments):
            repo = _get_repo(frag)
            if repo and not CollectionItem.query.filter_by(collection_id=c.id, repo_id=repo.id).first():
                db.session.add(CollectionItem(collection_id=c.id, repo_id=repo.id, position=pos))
        return c

    # Alice — NLP focused
    _make_collection(alice, "My NLP Toolkit",
                     "Best open-source NLP models I use daily.",
                     True,
                     ["Llama-3-apache", "DeepSeek-V3", "all-MiniLM-L6-v2", "bert-base-uncased"])

    _make_collection(alice, "Sentiment Analysis Picks",
                     "Models I evaluated for sentiment tasks.",
                     True,
                     ["twitter-xlm-roberta-base-sentiment-latest", "twitter-roberta-base-sentiment",
                      "distilbert-base-uncased-finetuned-sst-2"])

    # Bob — image generation
    _make_collection(bob, "Image Generation Models",
                     "Top text-to-image models for creative projects.",
                     True,
                     ["FLUX.1-schnell", "stable-diffusion-xl-base", "FLUX.1-dev",
                      "stable-diffusion-3-medium", "stable-cascade"])

    _make_collection(bob, "Private Experiments",
                     "Models I'm testing privately.",
                     False,
                     ["SDXL-Lightning", "Qwen-Image"])

    # Carol — translation + summarization
    _make_collection(carol, "Translation Models",
                     "Multilingual translation models.",
                     True,
                     ["opus-mt-en-zh", "nllb-200-distilled", "opus-mt-en-ja",
                      "opus-mt-en-fr-2026", "opus-mt-en-es-2026"])

    _make_collection(carol, "Summarization Collection",
                     "Models for automatic document summarization.",
                     True,
                     ["bart-large-cnn", "biobart"])

    # David — MLOps & embeddings
    _make_collection(david, "Production Inference Models",
                     "Models I run in production endpoints.",
                     True,
                     ["bge-large-en-v1.5", "all-MiniLM-L6-v2", "xlm-roberta-large-squad2", "deberta-v3-large"])

    db.session.flush()

    # ------------------------------------------------------------------
    # Endpoints (InferenceEndpoint = "order" equivalent)
    # ------------------------------------------------------------------
    def _make_endpoint(user, name, status, hw_slug, hw_display, hw_price, hours, slug_fragment, region="us-east-1"):
        repo = _get_repo(slug_fragment)
        if not repo:
            return None
        ep_id = "EP-" + "".join(rng.choices(string.ascii_uppercase + string.digits, k=8))
        try:
            price = float(hw_price.replace("$", "").replace("/hr", "")) if "$" in hw_price else 0.0
        except Exception:
            price = 0.0
        ep = InferenceEndpoint(
            user_id=user.id,
            endpoint_id=ep_id,
            name=name,
            status=status,
            region=region,
            total_hours=hours,
            total_cost=f"${price * hours:.2f}",
            created_at=mirror_now() - timedelta(days=rng.randint(1, 30)),
        )
        db.session.add(ep)
        db.session.flush()
        db.session.add(EndpointItem(
            endpoint_id=ep.id,
            repo_id=repo.id,
            hardware_slug=hw_slug,
            hardware_display=hw_display,
            hardware_price=hw_price,
            hours=hours,
        ))
        return ep

    # Alice — NLP endpoints
    _make_endpoint(alice, "alice-llm-production", "running",
                   "a100-large", "Nvidia A100", "$2.50/hr", 72,
                   "Llama-3-apache", region="us-east-1")
    _make_endpoint(alice, "alice-sentiment-api", "paused",
                   "t4-small", "Nvidia T4", "$0.40/hr", 24,
                   "twitter-xlm-roberta-base-sentiment-latest", region="us-west-2")

    # Bob — image gen endpoints
    _make_endpoint(bob, "bob-flux-endpoint", "running",
                   "l4x1", "Nvidia L4", "$0.80/hr", 48,
                   "FLUX.1-schnell", region="us-east-1")
    _make_endpoint(bob, "bob-sdxl-old", "terminated",
                   "t4-small", "Nvidia T4", "$0.40/hr", 24,
                   "stable-diffusion-xl-base", region="eu-west-1")

    # Carol — translation endpoints
    _make_endpoint(carol, "carol-translation-eu", "running",
                   "cpu-upgrade", "CPU Upgrade", "$0.03/hr", 168,
                   "nllb-200-distilled", region="eu-central-1")
    _make_endpoint(carol, "carol-summarizer", "paused",
                   "t4-small", "Nvidia T4", "$0.40/hr", 24,
                   "bart-large-cnn", region="us-east-1")

    # David — MLOps endpoints
    _make_endpoint(david, "david-embeddings-prod", "running",
                   "l40sx1", "Nvidia L40S", "$1.80/hr", 168,
                   "bge-large-en-v1.5", region="ap-southeast-1")
    _make_endpoint(david, "david-qa-endpoint", "terminated",
                   "t4-small", "Nvidia T4", "$0.40/hr", 48,
                   "xlm-roberta-large-squad2", region="us-west-2")

    db.session.flush()

    # ------------------------------------------------------------------
    # Discussions — each user posts on relevant repos
    # ------------------------------------------------------------------
    disc_data = [
        # (user, slug_frag, title, body, kind)
        (alice, "Llama-3-apache",
         "How to fine-tune on domain-specific data?",
         "Has anyone fine-tuned this on legal / medical text? Curious about the LoRA rank settings that worked best.",
         "discussion"),
        (alice, "all-MiniLM-L6-v2",
         "Comparison with BGE-large?",
         "I benchmarked MiniLM vs BGE-large on MTEB and found BGE wins on retrieval but MiniLM is 3x faster. Happy to share numbers.",
         "discussion"),
        (bob, "FLUX.1-schnell",
         "VRAM requirements for batch size > 1?",
         "Trying to run batch_size=4 on a 24GB consumer GPU. Getting OOM. Any quantization tips?",
         "issue"),
        (bob, "stable-diffusion-xl-base",
         "Best sampler for photorealistic outputs?",
         "I've been testing DPM++ 2M Karras — getting great results. What samplers are you all using?",
         "discussion"),
        (carol, "opus-mt-en-zh",
         "Performance on classical Chinese text?",
         "Testing on classical (wenyan) Chinese — the model struggles. Anyone fine-tuned on historical corpora?",
         "issue"),
        (carol, "bart-large-cnn",
         "License for commercial summarization product?",
         "The model card says Apache 2.0 but the dataset (CNN/DM) has restrictions. Has anyone gotten legal sign-off?",
         "discussion"),
        (david, "bge-large-en-v1.5",
         "Integration with pgvector — any gotchas?",
         "Using this with pgvector for RAG. Noticed cosine vs dot product gives different rankings. What normalization are you using?",
         "discussion"),
        (david, "xlm-roberta-large-squad2",
         "Degraded performance on low-resource languages?",
         "QA accuracy drops significantly on Swahili and Tamil compared to MLQA paper numbers. Is this a tokenization issue?",
         "issue"),
    ]
    for user, frag, title, body, kind in disc_data:
        repo = _get_repo(frag)
        if not repo:
            continue
        d = Discussion(
            repo_id=repo.id,
            user_id=user.id,
            title=title,
            body=body,
            kind=kind,
            upvotes=rng.randint(1, 30),
        )
        db.session.add(d)

    db.session.commit()
    print(f"  ✓ {len(BENCH_USERS)} benchmark users created")
    print(f"  ✓ Likes, collections, endpoints, discussions seeded")


# ------------------------------------------------------------
# Bootstrap
# ------------------------------------------------------------
with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
