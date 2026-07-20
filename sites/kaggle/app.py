"""
Kaggle Mirror — Full-stack Flask application.

A deterministic offline mirror of kaggle.com for web-agent benchmarks.

Entity model (data-science competition platform):
  User           — competitor with progression tiers + performance medals
  Competition    — hosted ML challenge (prize, metric, deadline, leaderboard)
  Submission     — a leaderboard entry for a competition
  CompetitionEntry — a user joining a competition (the "register"/transaction flow)
  Dataset        — community dataset with usability score, votes, downloads
  Notebook       — public code (kernel), optionally linked to comp/dataset
  Model          — pretrained model with framework + variations
  Course         — Kaggle Learn micro-course
  Discussion     — forum thread; Comment — replies
  Vote / Bookmark — polymorphic interactions across entity types
  Follow         — social graph (user -> user)
"""
import json
import os
import re
from datetime import datetime, date
from pathlib import Path

# ----------------------------------------------------------------------------
# Pinned mirror clock. The image is built once and evaluated at any future
# point; freeze "today" so date-relative tasks ("active competitions",
# "deadline this month") behave deterministically. Chosen to sit just after
# the newest seeded timestamp so recent uploads stay "recent" and every
# historical anchor stays firmly in the past.
# ----------------------------------------------------------------------------
MIRROR_REFERENCE_DATE = datetime(2026, 6, 22, 12, 0, 0)


def mirror_now() -> datetime:
    return MIRROR_REFERENCE_DATE


def mirror_today() -> date:
    return MIRROR_REFERENCE_DATE.date()


from flask import (Flask, render_template, request, redirect, url_for, flash,
                   jsonify, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import (StringField, PasswordField, TextAreaField, SelectField,
                     HiddenField)
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional as OptionalV

from seed_data import (
    PERFORMANCE_TIERS, COMPETITION_CATEGORIES, DISCUSSION_FORUMS, ML_FRAMEWORKS,
    LICENSES, PROGRAMMING_LANGUAGES, BENCHMARK_USERS, NOTABLE_USERS, COMPETITIONS,
    LEADERBOARDS, DATASETS, NOTEBOOKS, MODELS, COURSES, DISCUSSIONS,
    DISCUSSION_COMMENTS,
)

# ----------------------------------------------------------------------------
# Flask setup
# ----------------------------------------------------------------------------
ROOT = Path(__file__).parent
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "kaggle-mirror-dev-secret-key-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{ROOT / 'instance' / 'kaggle.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
(ROOT / "instance").mkdir(exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"

TIER_COLORS = {
    "Novice": "#5ac995", "Contributor": "#00aaff", "Expert": "#95319b",
    "Master": "#f96517", "Grandmaster": "#dca917",
}
MEDAL_EMOJI = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}


@app.template_filter("fromjson")
def _fromjson_filter(value):
    try:
        if isinstance(value, (list, dict)):
            return value
        return json.loads(value)
    except Exception:
        return []


@app.template_filter("commafy")
def _commafy(value):
    try:
        return f"{int(value):,}"
    except Exception:
        return value


@app.template_filter("reltime")
def _reltime(value):
    """Human 'time ago' relative to the mirror clock."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except Exception:
            return value
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    delta = mirror_now() - value
    days = delta.days
    if days < 0:
        return "just now"
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days} days ago"
    if days < 365:
        return f"{days // 30} months ago"
    return f"{days // 365} years ago"


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
    avatar_url = db.Column(db.String(300), default="/static/images/avatars/default.png")
    location = db.Column(db.String(120), default="")
    occupation = db.Column(db.String(120), default="")
    organization = db.Column(db.String(120), default="")
    website = db.Column(db.String(200), default="")
    tier = db.Column(db.String(20), default="Novice")
    tiers_json = db.Column(db.Text, default="{}")  # per-category tiers
    points = db.Column(db.Integer, default=0)
    gold = db.Column(db.Integer, default=0)
    silver = db.Column(db.Integer, default=0)
    bronze = db.Column(db.Integer, default=0)
    comp_rank = db.Column(db.Integer, nullable=True)  # global competitions rank
    is_org = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=mirror_now)

    @property
    def tier_color(self):
        return TIER_COLORS.get(self.tier, "#888")

    @property
    def category_tiers(self):
        try:
            return json.loads(self.tiers_json or "{}")
        except Exception:
            return {}

    @property
    def total_medals(self):
        return (self.gold or 0) + (self.silver or 0) + (self.bronze or 0)


class Competition(db.Model):
    __tablename__ = "competitions"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(300), default="")
    category = db.Column(db.String(40), index=True)
    host = db.Column(db.String(160), default="Kaggle")
    owner_username = db.Column(db.String(80), default="Kaggle")
    reward = db.Column(db.String(60), default="Knowledge")
    reward_value = db.Column(db.Integer, default=0)  # USD, 0 for non-cash
    metric = db.Column(db.String(80), default="")
    num_teams = db.Column(db.Integer, default=0)
    deadline = db.Column(db.Date, nullable=True)
    tags_json = db.Column(db.Text, default="[]")
    thumbnail = db.Column(db.String(120), default="")
    description = db.Column(db.Text, default="")

    submissions = db.relationship("Submission", backref="competition",
                                  cascade="all, delete-orphan", lazy="dynamic")

    @property
    def tags(self):
        try:
            return json.loads(self.tags_json or "[]")
        except Exception:
            return []

    @property
    def is_active(self):
        return self.deadline is None or self.deadline >= mirror_today()

    @property
    def days_left(self):
        if not self.deadline:
            return None
        return (self.deadline - mirror_today()).days

    @property
    def reward_display(self):
        return self.reward


class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"), index=True)
    rank = db.Column(db.Integer)
    team_name = db.Column(db.String(160))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    score = db.Column(db.Float)
    submitted_at = db.Column(db.Date)


class CompetitionEntry(db.Model):
    """A user joining a competition — the register/transaction flow."""
    __tablename__ = "competition_entries"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"), index=True)
    team_name = db.Column(db.String(160), default="")
    accepted_rules = db.Column(db.Boolean, default=True)
    joined_at = db.Column(db.DateTime, default=mirror_now)
    competition = db.relationship("Competition")


class Dataset(db.Model):
    __tablename__ = "datasets"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(300), default="")
    owner_username = db.Column(db.String(80), default="")
    size = db.Column(db.String(40), default="")
    size_bytes = db.Column(db.BigInteger, default=0)
    file_count = db.Column(db.Integer, default=1)
    file_types = db.Column(db.String(120), default="CSV")
    usability = db.Column(db.Float, default=0.0)
    upvotes = db.Column(db.Integer, default=0)
    downloads = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    license = db.Column(db.String(120), default="")
    tags_json = db.Column(db.Text, default="[]")
    last_updated = db.Column(db.Date, nullable=True)
    thumbnail = db.Column(db.String(120), default="")
    description = db.Column(db.Text, default="")

    @property
    def tags(self):
        try:
            return json.loads(self.tags_json or "[]")
        except Exception:
            return []


class Notebook(db.Model):
    __tablename__ = "notebooks"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    author_username = db.Column(db.String(80), default="")
    language = db.Column(db.String(20), default="Python")
    votes = db.Column(db.Integer, default=0)
    comments = db.Column(db.Integer, default=0)
    medal = db.Column(db.String(10), nullable=True)
    best_score = db.Column(db.String(40), nullable=True)
    runtime = db.Column(db.String(40), default="")
    last_run = db.Column(db.Date, nullable=True)
    linked_competition = db.Column(db.String(120), nullable=True)
    linked_dataset = db.Column(db.String(120), nullable=True)
    thumbnail = db.Column(db.String(120), default="")
    tags_json = db.Column(db.Text, default="[]")
    description = db.Column(db.Text, default="")

    @property
    def tags(self):
        try:
            return json.loads(self.tags_json or "[]")
        except Exception:
            return []

    @property
    def medal_emoji(self):
        return MEDAL_EMOJI.get(self.medal, "")


class Model(db.Model):
    __tablename__ = "models"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    owner_username = db.Column(db.String(80), default="")
    framework = db.Column(db.String(40), default="")
    variations = db.Column(db.Integer, default=1)
    downloads = db.Column(db.Integer, default=0)
    upvotes = db.Column(db.Integer, default=0)
    license = db.Column(db.String(120), default="")
    tags_json = db.Column(db.Text, default="[]")
    last_updated = db.Column(db.Date, nullable=True)
    thumbnail = db.Column(db.String(120), default="")
    description = db.Column(db.Text, default="")

    @property
    def tags(self):
        try:
            return json.loads(self.tags_json or "[]")
        except Exception:
            return []


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    lessons = db.Column(db.Integer, default=0)
    hours = db.Column(db.Integer, default=0)
    level = db.Column(db.String(20), default="Beginner")
    icon = db.Column(db.String(10), default="📘")
    tags_json = db.Column(db.Text, default="[]")
    description = db.Column(db.Text, default="")
    lesson_titles_json = db.Column(db.Text, default="[]")

    @property
    def tags(self):
        try:
            return json.loads(self.tags_json or "[]")
        except Exception:
            return []

    @property
    def lesson_titles(self):
        try:
            return json.loads(self.lesson_titles_json or "[]")
        except Exception:
            return []


class Discussion(db.Model):
    __tablename__ = "discussions"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    title = db.Column(db.String(240), nullable=False)
    author_username = db.Column(db.String(80), default="")
    forum = db.Column(db.String(60), index=True)
    votes = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)
    pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=mirror_now)
    body = db.Column(db.Text, default="")

    comments = db.relationship("Comment", backref="discussion",
                               cascade="all, delete-orphan", lazy="dynamic")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    discussion_id = db.Column(db.Integer, db.ForeignKey("discussions.id"), index=True)
    author_username = db.Column(db.String(80), default="")
    body = db.Column(db.Text, default="")
    votes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=mirror_now)


class Vote(db.Model):
    """Polymorphic upvote: entity_type in {dataset, notebook, model, discussion, competition}."""
    __tablename__ = "votes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    entity_type = db.Column(db.String(20), index=True)
    entity_id = db.Column(db.Integer, index=True)
    created_at = db.Column(db.DateTime, default=mirror_now)


class Bookmark(db.Model):
    __tablename__ = "bookmarks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    entity_type = db.Column(db.String(20), index=True)
    entity_id = db.Column(db.Integer, index=True)
    created_at = db.Column(db.DateTime, default=mirror_now)


class Follow(db.Model):
    __tablename__ = "follows"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    target_username = db.Column(db.String(80), index=True)
    created_at = db.Column(db.DateTime, default=mirror_now)


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
    email = StringField("Email", validators=[DataRequired(), Email()])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=40)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password")])


class ProfileForm(FlaskForm):
    display_name = StringField("Display name", validators=[OptionalV(), Length(max=120)])
    bio = TextAreaField("Bio", validators=[OptionalV(), Length(max=600)])
    location = StringField("Location", validators=[OptionalV(), Length(max=120)])
    occupation = StringField("Occupation", validators=[OptionalV(), Length(max=120)])
    organization = StringField("Organization", validators=[OptionalV(), Length(max=120)])
    website = StringField("Website", validators=[OptionalV(), Length(max=200)])


class PasswordForm(FlaskForm):
    current = PasswordField("Current password", validators=[DataRequired()])
    new = PasswordField("New password", validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField("Confirm new password", validators=[DataRequired(), EqualTo("new")])


class JoinCompetitionForm(FlaskForm):
    team_name = StringField("Team name", validators=[DataRequired(), Length(max=120)])
    accept_rules = HiddenField()


class DiscussionForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=240)])
    forum = SelectField("Forum", choices=[(f, f) for f in DISCUSSION_FORUMS], validators=[DataRequired()])
    body = TextAreaField("Body", validators=[DataRequired(), Length(min=10)])


class CommentForm(FlaskForm):
    body = TextAreaField("Comment", validators=[DataRequired(), Length(min=1)])


# ------------------------------------------------------------
# Search scoring (token-overlap, NOT strict AND)
# ------------------------------------------------------------
STOPWORDS = {"the", "a", "an", "of", "for", "to", "and", "or", "in", "on", "with",
             "by", "is", "are", "how", "what", "best", "top", "find", "show", "me"}


def _tokenize(q: str):
    return [t for t in re.findall(r"[a-z0-9.+#-]+", (q or "").lower())
            if len(t) >= 2 and t not in STOPWORDS]


def _score(hay: str, tokens):
    if not tokens:
        return 1
    hay = hay.lower()
    return sum(1 for t in tokens if t in hay)


def _comp_hay(c):
    return " ".join([c.slug, c.title, c.subtitle or "", c.category or "",
                     c.host or "", c.metric or "", c.description or "",
                     " ".join(c.tags)])


def _dataset_hay(d):
    return " ".join([d.slug, d.title, d.subtitle or "", d.owner_username or "",
                     d.license or "", d.description or "", d.file_types or "",
                     " ".join(d.tags)])


def _notebook_hay(n):
    return " ".join([n.slug, n.title, n.author_username or "", n.language or "",
                     n.description or "", n.linked_competition or "",
                     n.linked_dataset or "", " ".join(n.tags)])


def _model_hay(m):
    return " ".join([m.slug, m.title, m.owner_username or "", m.framework or "",
                     m.license or "", m.description or "", " ".join(m.tags)])


def _user_hay(u):
    return " ".join([u.username, u.display_name or "", u.bio or "",
                     u.location or "", u.occupation or "", u.organization or "",
                     u.tier or ""])


def _discussion_hay(d):
    return " ".join([d.slug, d.title, d.author_username or "", d.forum or "",
                     d.body or ""])


# ------------------------------------------------------------
# Context helpers
# ------------------------------------------------------------
@app.context_processor
def inject_globals():
    return dict(
        current_year=mirror_now().year,
        nav_forums=DISCUSSION_FORUMS,
        comp_categories=COMPETITION_CATEGORIES,
        TIER_COLORS=TIER_COLORS,
        MEDAL_EMOJI=MEDAL_EMOJI,
    )


def user_by_name(username):
    return User.query.filter_by(username=username).first()


def has_voted(entity_type, entity_id):
    if not current_user.is_authenticated:
        return False
    return Vote.query.filter_by(user_id=current_user.id, entity_type=entity_type,
                                entity_id=entity_id).first() is not None


def has_bookmarked(entity_type, entity_id):
    if not current_user.is_authenticated:
        return False
    return Bookmark.query.filter_by(user_id=current_user.id, entity_type=entity_type,
                                    entity_id=entity_id).first() is not None


def is_following(username):
    if not current_user.is_authenticated:
        return False
    return Follow.query.filter_by(user_id=current_user.id, target_username=username).first() is not None


app.jinja_env.globals.update(
    has_voted=has_voted, has_bookmarked=has_bookmarked,
    is_following=is_following, user_by_name=user_by_name,
)


# ------------------------------------------------------------
# Homepage + static pages
# ------------------------------------------------------------
@app.route("/")
def index():
    featured = Competition.query.filter(Competition.category.in_(["Featured", "Research"])) \
        .order_by(Competition.reward_value.desc()).limit(4).all()
    active_comps = Competition.query.order_by(Competition.num_teams.desc()).limit(6).all()
    hot_datasets = Dataset.query.order_by(Dataset.upvotes.desc()).limit(6).all()
    trending_notebooks = Notebook.query.order_by(Notebook.votes.desc()).limit(4).all()
    courses = Course.query.limit(4).all()
    return render_template("index.html", featured=featured, active_comps=active_comps,
                           hot_datasets=hot_datasets, trending_notebooks=trending_notebooks,
                           courses=courses)


@app.route("/_health")
def health():
    return {"ok": True, "site": "kaggle",
            "competitions": Competition.query.count(),
            "datasets": Dataset.query.count()}


# ------------------------------------------------------------
# Competitions
# ------------------------------------------------------------
@app.route("/competitions")
def competitions_list():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()  # active | completed
    sort = request.args.get("sort", "relevance" if q else "teams")

    query = Competition.query
    if category:
        query = query.filter(Competition.category == category)
    comps = query.all()

    if status == "active":
        comps = [c for c in comps if c.is_active]
    elif status == "completed":
        comps = [c for c in comps if not c.is_active]

    tokens = _tokenize(q)
    if tokens:
        min_req = max(1, len(tokens) // 2)
        scored = [(s, c) for c in comps if (s := _score(_comp_hay(c), tokens)) >= min_req]
        scored.sort(key=lambda sc: (-sc[0], -sc[1].num_teams))
        comps = [c for _, c in scored]
    else:
        if sort == "prize":
            comps.sort(key=lambda c: -c.reward_value)
        elif sort == "deadline":
            comps.sort(key=lambda c: (c.deadline or date.max))
        elif sort == "newest":
            comps.sort(key=lambda c: -c.id)
        else:  # teams
            comps.sort(key=lambda c: -c.num_teams)

    return render_template("competitions.html", comps=comps, q=q,
                           category=category, status=status, sort=sort)


@app.route("/competitions/<slug>")
def competition_detail(slug):
    c = Competition.query.filter_by(slug=slug).first_or_404()
    leaderboard = c.submissions.order_by(Submission.rank.asc()).all()
    host_user = user_by_name(c.owner_username)
    notebooks = Notebook.query.filter_by(linked_competition=slug).order_by(Notebook.votes.desc()).all()
    entry = None
    joined = False
    if current_user.is_authenticated:
        entry = CompetitionEntry.query.filter_by(user_id=current_user.id, competition_id=c.id).first()
        joined = entry is not None
    join_form = JoinCompetitionForm()
    return render_template("competition_detail.html", c=c, leaderboard=leaderboard,
                           host_user=host_user, notebooks=notebooks, joined=joined,
                           entry=entry, join_form=join_form, tab=request.args.get("tab", "overview"))


@app.route("/competitions/<slug>/leaderboard")
def competition_leaderboard(slug):
    c = Competition.query.filter_by(slug=slug).first_or_404()
    leaderboard = c.submissions.order_by(Submission.rank.asc()).all()
    return render_template("leaderboard.html", c=c, leaderboard=leaderboard)


@app.route("/competitions/<slug>/join", methods=["POST"])
@login_required
def competition_join(slug):
    c = Competition.query.filter_by(slug=slug).first_or_404()
    if not c.is_active:
        flash("This competition has closed — you can no longer join.", "error")
        return redirect(url_for("competition_detail", slug=slug))
    form = JoinCompetitionForm()
    if form.validate_on_submit():
        existing = CompetitionEntry.query.filter_by(user_id=current_user.id, competition_id=c.id).first()
        if existing:
            flash("You have already joined this competition.", "info")
        else:
            entry = CompetitionEntry(user_id=current_user.id, competition_id=c.id,
                                     team_name=form.team_name.data.strip(), accepted_rules=True)
            db.session.add(entry)
            c.num_teams = (c.num_teams or 0) + 1
            db.session.commit()
            flash(f"You're in! Team '{entry.team_name}' joined {c.title}.", "success")
    else:
        flash("Please enter a team name and accept the rules.", "error")
    return redirect(url_for("competition_detail", slug=slug))


# ------------------------------------------------------------
# Datasets
# ------------------------------------------------------------
@app.route("/datasets")
def datasets_list():
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    file_type = request.args.get("file_type", "").strip()
    sort = request.args.get("sort", "relevance" if q else "hottest")

    datasets = Dataset.query.all()
    if tag:
        datasets = [d for d in datasets if tag in d.tags]
    if file_type:
        datasets = [d for d in datasets if file_type.lower() in (d.file_types or "").lower()]

    tokens = _tokenize(q)
    if tokens:
        min_req = max(1, len(tokens) // 2)
        scored = [(s, d) for d in datasets if (s := _score(_dataset_hay(d), tokens)) >= min_req]
        scored.sort(key=lambda sc: (-sc[0], -sc[1].upvotes))
        datasets = [d for _, d in scored]
    else:
        if sort == "votes":
            datasets.sort(key=lambda d: -d.upvotes)
        elif sort == "downloads":
            datasets.sort(key=lambda d: -d.downloads)
        elif sort == "usability":
            datasets.sort(key=lambda d: -d.usability)
        elif sort == "updated":
            datasets.sort(key=lambda d: (d.last_updated or date.min), reverse=True)
        elif sort == "size":
            datasets.sort(key=lambda d: -d.size_bytes)
        else:  # hottest
            datasets.sort(key=lambda d: -(d.upvotes + d.downloads // 20))

    all_tags = sorted({t for d in Dataset.query.all() for t in d.tags})
    return render_template("datasets.html", datasets=datasets, q=q, tag=tag,
                           file_type=file_type, sort=sort, all_tags=all_tags)


@app.route("/datasets/<slug>")
def dataset_detail(slug):
    d = Dataset.query.filter_by(slug=slug).first_or_404()
    owner = user_by_name(d.owner_username)
    notebooks = Notebook.query.filter_by(linked_dataset=slug).order_by(Notebook.votes.desc()).all()
    return render_template("dataset_detail.html", d=d, owner=owner, notebooks=notebooks)


@app.route("/datasets/<slug>/download")
def dataset_download(slug):
    d = Dataset.query.filter_by(slug=slug).first_or_404()
    d.downloads = (d.downloads or 0) + 1
    db.session.commit()
    flash(f"Download started: {d.title} ({d.size}).", "success")
    return redirect(url_for("dataset_detail", slug=slug))


# ------------------------------------------------------------
# Notebooks (Code)
# ------------------------------------------------------------
@app.route("/code")
def notebooks_list():
    q = request.args.get("q", "").strip()
    language = request.args.get("language", "").strip()
    medal = request.args.get("medal", "").strip()
    sort = request.args.get("sort", "relevance" if q else "votes")

    notebooks = Notebook.query.all()
    if language:
        notebooks = [n for n in notebooks if n.language == language]
    if medal:
        notebooks = [n for n in notebooks if n.medal == medal]

    tokens = _tokenize(q)
    if tokens:
        min_req = max(1, len(tokens) // 2)
        scored = [(s, n) for n in notebooks if (s := _score(_notebook_hay(n), tokens)) >= min_req]
        scored.sort(key=lambda sc: (-sc[0], -sc[1].votes))
        notebooks = [n for _, n in scored]
    else:
        if sort == "comments":
            notebooks.sort(key=lambda n: -n.comments)
        elif sort == "recent":
            notebooks.sort(key=lambda n: (n.last_run or date.min), reverse=True)
        else:
            notebooks.sort(key=lambda n: -n.votes)

    return render_template("notebooks.html", notebooks=notebooks, q=q,
                           language=language, medal=medal, sort=sort)


@app.route("/code/<slug>")
def notebook_detail(slug):
    n = Notebook.query.filter_by(slug=slug).first_or_404()
    author = user_by_name(n.author_username)
    comp = Competition.query.filter_by(slug=n.linked_competition).first() if n.linked_competition else None
    dataset = Dataset.query.filter_by(slug=n.linked_dataset).first() if n.linked_dataset else None
    return render_template("notebook_detail.html", n=n, author=author, comp=comp, dataset=dataset)


# ------------------------------------------------------------
# Models
# ------------------------------------------------------------
@app.route("/models")
def models_list():
    q = request.args.get("q", "").strip()
    framework = request.args.get("framework", "").strip()
    sort = request.args.get("sort", "relevance" if q else "downloads")

    models = Model.query.all()
    if framework:
        models = [m for m in models if m.framework == framework]

    tokens = _tokenize(q)
    if tokens:
        min_req = max(1, len(tokens) // 2)
        scored = [(s, m) for m in models if (s := _score(_model_hay(m), tokens)) >= min_req]
        scored.sort(key=lambda sc: (-sc[0], -sc[1].downloads))
        models = [m for _, m in scored]
    else:
        if sort == "votes":
            models.sort(key=lambda m: -m.upvotes)
        elif sort == "updated":
            models.sort(key=lambda m: (m.last_updated or date.min), reverse=True)
        else:
            models.sort(key=lambda m: -m.downloads)

    return render_template("models.html", models=models, q=q,
                           framework=framework, sort=sort, frameworks=ML_FRAMEWORKS)


@app.route("/models/<slug>")
def model_detail(slug):
    m = Model.query.filter_by(slug=slug).first_or_404()
    owner = user_by_name(m.owner_username)
    return render_template("model_detail.html", m=m, owner=owner)


# ------------------------------------------------------------
# Learn (courses)
# ------------------------------------------------------------
@app.route("/learn")
def learn():
    courses = Course.query.all()
    return render_template("learn.html", courses=courses)


@app.route("/learn/<slug>")
def course_detail(slug):
    course = Course.query.filter_by(slug=slug).first_or_404()
    return render_template("course_detail.html", course=course)


# ------------------------------------------------------------
# Discussions
# ------------------------------------------------------------
@app.route("/discussions")
def discussions_list():
    q = request.args.get("q", "").strip()
    forum = request.args.get("forum", "").strip()
    sort = request.args.get("sort", "relevance" if q else "hot")

    discussions = Discussion.query.all()
    if forum:
        discussions = [d for d in discussions if d.forum == forum]

    tokens = _tokenize(q)
    if tokens:
        min_req = max(1, len(tokens) // 2)
        scored = [(s, d) for d in discussions if (s := _score(_discussion_hay(d), tokens)) >= min_req]
        scored.sort(key=lambda sc: (-sc[0], -sc[1].votes))
        discussions = [d for _, d in scored]
    else:
        if sort == "recent":
            discussions.sort(key=lambda d: d.created_at or mirror_now(), reverse=True)
        elif sort == "comments":
            discussions.sort(key=lambda d: -d.comment_count)
        else:  # hot — pinned first, then votes
            discussions.sort(key=lambda d: (not d.pinned, -d.votes))

    return render_template("discussions.html", discussions=discussions, q=q,
                           forum=forum, sort=sort)


@app.route("/discussions/<slug>")
def discussion_detail(slug):
    d = Discussion.query.filter_by(slug=slug).first_or_404()
    author = user_by_name(d.author_username)
    comments = d.comments.order_by(Comment.votes.desc()).all()
    comment_form = CommentForm()
    return render_template("discussion_detail.html", d=d, author=author,
                           comments=comments, comment_form=comment_form)


@app.route("/discussions/new", methods=["GET", "POST"])
@login_required
def discussion_new():
    form = DiscussionForm()
    if form.validate_on_submit():
        base = re.sub(r"[^a-z0-9]+", "-", form.title.data.lower()).strip("-")[:120] or "thread"
        slug = base
        n = 2
        while Discussion.query.filter_by(slug=slug).first():
            slug = f"{base}-{n}"
            n += 1
        d = Discussion(slug=slug, title=form.title.data.strip(), forum=form.forum.data,
                       author_username=current_user.username, body=form.body.data.strip(),
                       votes=0, comment_count=0, pinned=False, created_at=mirror_now())
        db.session.add(d)
        db.session.commit()
        flash("Discussion posted.", "success")
        return redirect(url_for("discussion_detail", slug=slug))
    return render_template("discussion_new.html", form=form)


@app.route("/discussions/<slug>/comment", methods=["POST"])
@login_required
def discussion_comment(slug):
    d = Discussion.query.filter_by(slug=slug).first_or_404()
    form = CommentForm()
    if form.validate_on_submit():
        c = Comment(discussion_id=d.id, author_username=current_user.username,
                    body=form.body.data.strip(), votes=0, created_at=mirror_now())
        db.session.add(c)
        d.comment_count = (d.comment_count or 0) + 1
        db.session.commit()
        flash("Comment posted.", "success")
    else:
        flash("Comment cannot be empty.", "error")
    return redirect(url_for("discussion_detail", slug=slug))


# ------------------------------------------------------------
# Rankings + user profiles
# ------------------------------------------------------------
@app.route("/rankings")
def rankings():
    category = request.args.get("category", "competitions")
    users = User.query.filter_by(is_org=False).all()
    tier_weight = {t: i for i, t in enumerate(PERFORMANCE_TIERS)}

    def keyf(u):
        ct = u.category_tiers.get(category, u.tier)
        return (-tier_weight.get(ct, 0), -(u.points or 0))

    users.sort(key=keyf)
    return render_template("rankings.html", users=users, category=category,
                           categories=["competitions", "datasets", "notebooks", "discussions"])


@app.route("/user/<username>")
def user_profile(username):
    u = User.query.filter_by(username=username).first_or_404()
    datasets = Dataset.query.filter_by(owner_username=username).order_by(Dataset.upvotes.desc()).all()
    notebooks = Notebook.query.filter_by(author_username=username).order_by(Notebook.votes.desc()).all()
    models = Model.query.filter_by(owner_username=username).order_by(Model.downloads.desc()).all()
    discussions = Discussion.query.filter_by(author_username=username).order_by(Discussion.votes.desc()).all()
    hosted = Competition.query.filter_by(owner_username=username).all()
    follower_count = Follow.query.filter_by(target_username=username).count()
    return render_template("user_profile.html", u=u, datasets=datasets, notebooks=notebooks,
                           models=models, discussions=discussions, hosted=hosted,
                           follower_count=follower_count)


# ------------------------------------------------------------
# Global search
# ------------------------------------------------------------
@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    scope = request.args.get("type", "all")
    tokens = _tokenize(q)
    min_req = max(1, len(tokens) // 2) if tokens else 0

    def run(items, hayf, sortkey):
        if not tokens:
            return []
        scored = [(s, it) for it in items if (s := _score(hayf(it), tokens)) >= min_req]
        scored.sort(key=lambda sc: (-sc[0], sortkey(sc[1])))
        return [it for _, it in scored]

    comps = run(Competition.query.all(), _comp_hay, lambda c: -c.num_teams) if scope in ("all", "competitions") else []
    datasets = run(Dataset.query.all(), _dataset_hay, lambda d: -d.upvotes) if scope in ("all", "datasets") else []
    notebooks = run(Notebook.query.all(), _notebook_hay, lambda n: -n.votes) if scope in ("all", "code") else []
    models = run(Model.query.all(), _model_hay, lambda m: -m.downloads) if scope in ("all", "models") else []
    users = run(User.query.all(), _user_hay, lambda u: -(u.points or 0)) if scope in ("all", "users") else []
    discussions = run(Discussion.query.all(), _discussion_hay, lambda d: -d.votes) if scope in ("all", "discussions") else []

    total = len(comps) + len(datasets) + len(notebooks) + len(models) + len(users) + len(discussions)
    return render_template("search.html", q=q, scope=scope, total=total,
                           comps=comps, datasets=datasets, notebooks=notebooks,
                           models=models, users=users, discussions=discussions)


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
            user = User(
                email=email, username=username,
                password_hash=bcrypt.generate_password_hash(form.password.data).decode(),
                display_name=username, tier="Novice",
                tiers_json=json.dumps({"competitions": "Novice", "datasets": "Novice",
                                       "notebooks": "Novice", "discussions": "Novice"}),
                avatar_url="/static/images/avatars/default.png",
                created_at=mirror_now(),
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to Kaggle!", "success")
            return redirect(url_for("index"))
    return render_template("register.html", form=form)


@app.route("/logout")
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    entries = CompetitionEntry.query.filter_by(user_id=current_user.id).order_by(CompetitionEntry.joined_at.desc()).all()
    bookmarks = Bookmark.query.filter_by(user_id=current_user.id).all()
    votes = Vote.query.filter_by(user_id=current_user.id).all()
    follows = Follow.query.filter_by(user_id=current_user.id).all()
    bm = [(_resolve_entity(b.entity_type, b.entity_id), b) for b in bookmarks]
    bm = [(e, b) for e, b in bm if e is not None]
    return render_template("account.html", entries=entries, bookmarks=bm,
                           votes=votes, follows=follows)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.display_name = form.display_name.data
        current_user.bio = form.bio.data
        current_user.location = form.location.data
        current_user.occupation = form.occupation.data
        current_user.organization = form.organization.data
        current_user.website = form.website.data
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
# Interactions: vote / bookmark / follow (JSON + form fallback)
# ------------------------------------------------------------
_ENTITY_MODELS = {
    "competition": Competition, "dataset": Dataset, "notebook": Notebook,
    "model": Model, "discussion": Discussion,
}
_VOTE_FIELD = {"competition": None, "dataset": "upvotes", "notebook": "votes",
               "model": "upvotes", "discussion": "votes"}


def _resolve_entity(etype, eid):
    model = _ENTITY_MODELS.get(etype)
    if not model:
        return None
    return db.session.get(model, eid)


@app.route("/api/vote", methods=["POST"])
@login_required
def api_vote():
    etype = request.form.get("entity_type") or (request.json or {}).get("entity_type")
    eid = request.form.get("entity_id") or (request.json or {}).get("entity_id")
    try:
        eid = int(eid)
    except (TypeError, ValueError):
        return jsonify(error="bad entity_id"), 400
    if etype not in _ENTITY_MODELS:
        return jsonify(error="bad entity_type"), 400
    ent = _resolve_entity(etype, eid)
    if ent is None:
        return jsonify(error="not found"), 404
    existing = Vote.query.filter_by(user_id=current_user.id, entity_type=etype, entity_id=eid).first()
    field = _VOTE_FIELD.get(etype)
    if existing:
        db.session.delete(existing)
        if field:
            setattr(ent, field, max(0, (getattr(ent, field) or 0) - 1))
        voted = False
    else:
        db.session.add(Vote(user_id=current_user.id, entity_type=etype, entity_id=eid))
        if field:
            setattr(ent, field, (getattr(ent, field) or 0) + 1)
        voted = True
    db.session.commit()
    count = getattr(ent, field) if field else None
    if request.is_json or request.headers.get("Accept", "").startswith("application/json"):
        return jsonify(ok=True, voted=voted, count=count)
    flash("Vote recorded." if voted else "Vote removed.", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/api/bookmark", methods=["POST"])
@login_required
def api_bookmark():
    etype = request.form.get("entity_type") or (request.json or {}).get("entity_type")
    eid = request.form.get("entity_id") or (request.json or {}).get("entity_id")
    try:
        eid = int(eid)
    except (TypeError, ValueError):
        return jsonify(error="bad entity_id"), 400
    if etype not in _ENTITY_MODELS:
        return jsonify(error="bad entity_type"), 400
    if _resolve_entity(etype, eid) is None:
        return jsonify(error="not found"), 404
    existing = Bookmark.query.filter_by(user_id=current_user.id, entity_type=etype, entity_id=eid).first()
    if existing:
        db.session.delete(existing)
        bookmarked = False
    else:
        db.session.add(Bookmark(user_id=current_user.id, entity_type=etype, entity_id=eid))
        bookmarked = True
    db.session.commit()
    if request.is_json or request.headers.get("Accept", "").startswith("application/json"):
        return jsonify(ok=True, bookmarked=bookmarked)
    flash("Saved." if bookmarked else "Removed from saved.", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/api/follow", methods=["POST"])
@login_required
def api_follow():
    username = request.form.get("username") or (request.json or {}).get("username")
    target = User.query.filter_by(username=username).first()
    if target is None:
        return jsonify(error="not found"), 404
    if target.id == current_user.id:
        return jsonify(error="cannot follow yourself"), 400
    existing = Follow.query.filter_by(user_id=current_user.id, target_username=username).first()
    if existing:
        db.session.delete(existing)
        following = False
    else:
        db.session.add(Follow(user_id=current_user.id, target_username=username))
        following = True
    db.session.commit()
    if request.is_json or request.headers.get("Accept", "").startswith("application/json"):
        return jsonify(ok=True, following=following)
    flash("Followed." if following else "Unfollowed.", "success")
    return redirect(request.referrer or url_for("user_profile", username=username))


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
# Seeding (idempotent — gate every function as a whole)
# ------------------------------------------------------------
def _d(iso):
    return date.fromisoformat(iso) if iso else None


def _dt(iso):
    return datetime.fromisoformat(iso) if iso else mirror_now()


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    for u in BENCHMARK_USERS:
        db.session.add(User(
            email=u["email"], username=u["username"],
            password_hash=bcrypt.generate_password_hash(u["password"]).decode(),
            display_name=u["display_name"], bio=u["bio"], tier=u["tier"],
            tiers_json=json.dumps(u["tiers"]), points=u["points"],
            gold=u["gold"], silver=u["silver"], bronze=u["bronze"],
            location=u["location"], occupation=u["occupation"], organization=u["organization"],
            avatar_url=f"/static/images/avatars/{u['avatar']}.png",
            created_at=_dt(u["joined"]),
        ))
    db.session.commit()


def seed_users():
    if User.query.filter_by(username="psi_grandmaster").first():
        return
    for u in NOTABLE_USERS:
        db.session.add(User(
            email=f"{u['username']}@kaggle.test", username=u["username"],
            password_hash=bcrypt.generate_password_hash("TestPass123!").decode(),
            display_name=u["display_name"], bio=u["bio"], tier=u["tier"],
            tiers_json=json.dumps(u["tiers"]), points=u["points"],
            gold=u["gold"], silver=u["silver"], bronze=u["bronze"],
            comp_rank=u.get("comp_rank"),
            location=u["location"], occupation=u["occupation"], organization=u["organization"],
            avatar_url=f"/static/images/avatars/{u['avatar']}.png",
            is_org=u.get("is_org", False), created_at=_dt(u["joined"]),
        ))
    # The platform "Kaggle" host account.
    db.session.add(User(
        email="staff@kaggle.test", username="Kaggle",
        password_hash=bcrypt.generate_password_hash("TestPass123!").decode(),
        display_name="Kaggle", bio="Official Kaggle account.", tier="Grandmaster",
        tiers_json=json.dumps({"competitions": "Grandmaster", "datasets": "Grandmaster",
                               "notebooks": "Grandmaster", "discussions": "Grandmaster"}),
        points=0, gold=0, silver=0, bronze=0, is_org=True,
        avatar_url="/static/images/avatars/kaggle.png", created_at=_dt("2010-04-01"),
    ))
    db.session.commit()


def seed_competitions():
    if Competition.query.count() > 0:
        return
    for c in COMPETITIONS:
        db.session.add(Competition(
            slug=c["slug"], title=c["title"], subtitle=c["subtitle"],
            category=c["category"], host=c["host"], owner_username=c["owner"],
            reward=c["reward"], reward_value=c["reward_value"], metric=c["metric"],
            num_teams=c["num_teams"], deadline=_d(c["deadline"]),
            tags_json=json.dumps(c["tags"]), thumbnail=c["thumbnail"],
            description=c["description"],
        ))
    db.session.commit()
    for slug, rows in LEADERBOARDS.items():
        comp = Competition.query.filter_by(slug=slug).first()
        if not comp:
            continue
        for rank, team, uname, score, submitted in rows:
            u = User.query.filter_by(username=uname).first()
            db.session.add(Submission(
                competition_id=comp.id, rank=rank, team_name=team,
                user_id=u.id if u else None, score=score, submitted_at=_d(submitted),
            ))
    db.session.commit()


def seed_datasets():
    if Dataset.query.count() > 0:
        return
    for d in DATASETS:
        db.session.add(Dataset(
            slug=d["slug"], title=d["title"], subtitle=d["subtitle"],
            owner_username=d["owner"], size=d["size"], size_bytes=d["size_bytes"],
            file_count=d["file_count"], file_types=d["file_types"], usability=d["usability"],
            upvotes=d["upvotes"], downloads=d["downloads"], views=d["views"],
            license=d["license"], tags_json=json.dumps(d["tags"]),
            last_updated=_d(d["last_updated"]), thumbnail=d["thumbnail"],
            description=d["description"],
        ))
    db.session.commit()


def seed_notebooks():
    if Notebook.query.count() > 0:
        return
    for n in NOTEBOOKS:
        db.session.add(Notebook(
            slug=n["slug"], title=n["title"], author_username=n["author"],
            language=n["language"], votes=n["votes"], comments=n["comments"],
            medal=n["medal"], best_score=n["best_score"], runtime=n["runtime"],
            last_run=_d(n["last_run"]), linked_competition=n["linked_competition"],
            linked_dataset=n["linked_dataset"], thumbnail=n["thumbnail"],
            tags_json=json.dumps(n["tags"]), description=n["description"],
        ))
    db.session.commit()


def seed_models():
    if Model.query.count() > 0:
        return
    for m in MODELS:
        db.session.add(Model(
            slug=m["slug"], title=m["title"], owner_username=m["owner"],
            framework=m["framework"], variations=m["variations"], downloads=m["downloads"],
            upvotes=m["upvotes"], license=m["license"], tags_json=json.dumps(m["tags"]),
            last_updated=_d(m["last_updated"]), thumbnail=m["thumbnail"],
            description=m["description"],
        ))
    db.session.commit()


def seed_courses():
    if Course.query.count() > 0:
        return
    for c in COURSES:
        db.session.add(Course(
            slug=c["slug"], title=c["title"], lessons=c["lessons"], hours=c["hours"],
            level=c["level"], icon=c["icon"], tags_json=json.dumps(c["tags"]),
            description=c["description"], lesson_titles_json=json.dumps(c["lesson_titles"]),
        ))
    db.session.commit()


def seed_discussions():
    if Discussion.query.count() > 0:
        return
    for d in DISCUSSIONS:
        db.session.add(Discussion(
            slug=d["slug"], title=d["title"], author_username=d["author"],
            forum=d["forum"], votes=d["votes"], comment_count=d["comments"],
            pinned=d["pinned"], created_at=_dt(d["created_at"]), body=d["body"],
        ))
    db.session.commit()
    for slug, rows in DISCUSSION_COMMENTS.items():
        disc = Discussion.query.filter_by(slug=slug).first()
        if not disc:
            continue
        for uname, body, votes, created in rows:
            db.session.add(Comment(discussion_id=disc.id, author_username=uname,
                                   body=body, votes=votes, created_at=_dt(created)))
    db.session.commit()


def seed_benchmark_data():
    """Give benchmark users pre-existing saved items, joined competitions, and
    follows so their account pages feel populated. Gated as a whole for
    idempotency. Deliberately avoids every tasks.jsonl target so the benchmark
    tasks stay valid (e.g. alice does NOT pre-join 'llm-prompt-recovery')."""
    alice = User.query.filter_by(email="alice.j@test.com").first()
    if not alice:
        return
    if Bookmark.query.filter_by(user_id=alice.id).first():
        return  # already seeded

    def bk(u, etype, slug, model):
        ent = model.query.filter_by(slug=slug).first()
        if u and ent:
            db.session.add(Bookmark(user_id=u.id, entity_type=etype, entity_id=ent.id))

    def join(u, slug, team):
        c = Competition.query.filter_by(slug=slug).first()
        if u and c:
            db.session.add(CompetitionEntry(user_id=u.id, competition_id=c.id,
                                            team_name=team, accepted_rules=True,
                                            joined_at=mirror_now()))

    bob = User.query.filter_by(email="bob.c@test.com").first()
    carol = User.query.filter_by(email="carol.d@test.com").first()

    bk(alice, "notebook", "co2-emissions-trends-eda", Notebook)
    bk(alice, "dataset", "spotify-tracks-audio-features", Dataset)
    join(alice, "titanic-survival", "alicejdata")
    db.session.add(Follow(user_id=alice.id, target_username="datasmith_io"))

    bk(bob, "dataset", "student-performance-factors", Dataset)
    join(bob, "handwritten-digit-recognizer", "bobsmith_ml")

    bk(carol, "model", "resnet50-chestxray", Model)
    db.session.add(Follow(user_id=carol.id, target_username="kenji_cv"))
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_benchmark_users()
    seed_users()
    seed_competitions()
    seed_datasets()
    seed_notebooks()
    seed_models()
    seed_courses()
    seed_discussions()
    seed_benchmark_data()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
