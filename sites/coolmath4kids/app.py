"""Coolmath4Kids mirror — Flask app.

Mirrors https://www.coolmath4kids.com/ : math games (by topic and grade),
multi-page lessons, arithmetic quizzes with certificates, manipulatives,
and brain teasers. Account features (progress tracking, favorites,
certificates) are mirror-native.
"""
from __future__ import annotations

import json
import math
import os
import random
import re
from datetime import datetime

from flask import (Flask, abort, flash, redirect, render_template, request,
                   url_for)
from flask_bcrypt import Bcrypt
from flask_login import (AnonymousUserMixin, LoginManager, UserMixin,
                         current_user, login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MIRROR_REFERENCE_DATE = datetime(2026, 9, 26)

# Upstream /math-games grid order (captured 2026-09-26). The unfiltered
# Math Games page lists the catalog in this display order; topic and grade
# filter pages keep their own upstream position maps (topic_position /
# grade_position in the frozen seed).
ALL_GAMES_GRID_ORDER = (
    "island-chase", "tugboat-addition", "grand-prix-multiplication",
    "drag-race-division", "speedway", "tractor-multiplication",
    "minus-mission", "orbit-integers", "dirt-bike-proportions",
    "integer-warp", "dolphin-feed", "snow-sprint", "demolition-division",
    "otter-rush", "alien-addition", "meteor-multiplication",
    "swimming-otters", "canoe-puppies", "puppy-pull", "dirt-bike-fractions",
    "canoe-penguins", "jet-ski-addition", "123-tracing", "math-fisher",
    "weighing-fruits", "tortuga-racing",
)

# The upstream homepage highlights these four teasers (in this display
# order); they are not simply the first four teasers of the index.
HOMEPAGE_TEASER_SLUGS = ("penny-triangle", "toothpick-squares",
                         "handshake-puzzle", "painted-cube")

# Upstream lesson bodies occasionally reference assets by absolute upstream
# URL (e.g. equals_0.gif under /sites/default/files/). When the mirror ships
# the real asset under static/images/lessons/, the src is rewritten at
# render time so the page renders offline exactly like upstream renders
# online. Remote references with no mirrored asset (e.g. the upstream-broken
# 1_3change.gif) are left untouched, preserving upstream fidelity.
_UPSTREAM_IMAGE_LOCAL_MAP = {
    "http://www.coolmath4kids.com/sites/default/files/equals_0.gif":
        "/static/images/lessons/equals_0.gif",
}

# The captured upstream lesson bodies also carry Drupal's jQuery loader
# (<script src="/core/assets/vendor/jquery/jquery.min.js">) and per-page
# jQuery hover swappers whose target frames were not captured in the asset
# archive. The mirror renders those pages with their default frames, so the
# dead loader tags and matching inline jQuery blocks are dropped at render
# time: no 404s, no "jQuery is not defined" console errors, same visuals.
_DEAD_JQUERY_SCRIPTS = (
    re.compile(r"<script\b[^>]*src=\"/core/assets/vendor/jquery/[^\"]*\"[^>]*>\s*</script>"),
    re.compile(r"<script>(?:(?!</script>).)*?jQuery\b(?:(?!</script>).)*?</script>", re.S),
)


def localize_lesson_images(html):
    for remote, local in _UPSTREAM_IMAGE_LOCAL_MAP.items():
        if os.path.isfile(os.path.join(BASE_DIR, local.lstrip("/"))):
            html = html.replace(remote, local)
    for pattern in _DEAD_JQUERY_SCRIPTS:
        html = pattern.sub("", html)
    return html

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'coolmath4kids.db')}"
app.config["SECRET_KEY"] = "coolmath4kids-dev-secret-key"
app.config["BCRYPT_ROUNDS"] = 12

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    display_name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    favorites = db.relationship("Favorite", backref="user", cascade="all, delete-orphan")
    certificates = db.relationship("Certificate", backref="user", cascade="all, delete-orphan")
    attempts = db.relationship("QuizAttempt", backref="user", cascade="all, delete-orphan")
    plays = db.relationship("GamePlay", backref="user", cascade="all, delete-orphan")


class Game(db.Model):
    __tablename__ = "games"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    topic = db.Column(db.String(32))          # primary topic (breadcrumb + card icon)
    topics = db.Column(db.Text, default="")   # all topics this game is listed under (comma-separated)
    topic_position = db.Column(db.Text, default="{}")  # JSON {topic: position in topic page}
    grade_position = db.Column(db.Text, default="{}")  # JSON {grade: position in grade page}
    description = db.Column(db.Text, default="")
    contents = db.Column(db.String(255), default="")
    standards = db.Column(db.String(255), default="")
    players = db.Column(db.Integer)
    featured = db.Column(db.Integer)          # 0..13 on the homepage carousel, None otherwise
    related = db.Column(db.Text, default="")   # comma-separated slugs
    grades = db.Column(db.Text, default="")    # comma-separated grade slugs

    @property
    def topic_list(self):
        return [t for t in (self.topics or "").split(",") if t]


class Lesson(db.Model):
    __tablename__ = "lessons"
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(32), nullable=False, index=True)
    slug = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    order_in_topic = db.Column(db.Integer, default=0)
    pages = db.Column(db.Text, default="[]")   # JSON list of page HTML


class Teaser(db.Model):
    __tablename__ = "teasers"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    blurb = db.Column(db.String(255), default="")
    order = db.Column(db.Integer, default=0)


class Manipulative(db.Model):
    __tablename__ = "manipulatives"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    about = db.Column(db.Text, default="")
    order = db.Column(db.Integer, default=0)


class Favorite(db.Model):
    __tablename__ = "favorites"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    game_slug = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    operation = db.Column(db.String(16), nullable=False)     # Addition/Subtraction/Multiplication/Division
    range_label = db.Column(db.String(32), nullable=False)   # e.g. "0-10", "1's"
    total_questions = db.Column(db.Integer, nullable=False)
    time_per_question = db.Column(db.String(16), nullable=False)  # "30", "15", "5", "Unlimited"
    status = db.Column(db.String(16), default="in_progress")
    questions = db.Column(db.Text, default="[]")             # JSON [[a, b, answer], ...]
    answers = db.Column(db.Text, default="[]")               # JSON [int or -1, ...]
    elapsed_ms = db.Column(db.Text, default="[]")            # JSON per-question ms
    correct_count = db.Column(db.Integer, default=0)
    score_pct = db.Column(db.Float, default=0.0)
    avg_seconds = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)
    completed_at = db.Column(db.DateTime)

    certificate = db.relationship("Certificate", backref="attempt", uselist=False)


class Certificate(db.Model):
    __tablename__ = "certificates"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    attempt_id = db.Column(db.Integer, db.ForeignKey("quiz_attempts.id"))
    person_name = db.Column(db.String(25), nullable=False)
    theme = db.Column(db.String(24), nullable=False)   # mathgirl/mathboy/mathasaurusrex/mathninja/mathcat/mathlete/mathicorn
    operation = db.Column(db.String(16), nullable=False)
    range_label = db.Column(db.String(32), nullable=False)
    correct = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    issued_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class GamePlay(db.Model):
    __tablename__ = "game_plays"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    game_slug = db.Column(db.String(80), nullable=False)
    facts_total = db.Column(db.Integer, nullable=False)
    facts_correct = db.Column(db.Integer, nullable=False)
    position = db.Column(db.Integer)               # finishing place 1-4 (1 for solo games)
    duration_seconds = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class AnonymousUser(AnonymousUserMixin):
    pass


login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Static reference data (mirrors upstream site structure)
# ---------------------------------------------------------------------------

TOPICS = [
    {"slug": "addition", "name": "Addition", "tid": 1, "icon": "addition"},
    {"slug": "subtraction", "name": "Subtraction", "tid": 2, "icon": "subtraction"},
    {"slug": "multiplication", "name": "Multiplication", "tid": 3, "icon": "multiplication"},
    {"slug": "division", "name": "Division", "tid": 4, "icon": "division"},
    {"slug": "fractions", "name": "Fractions", "tid": 5, "icon": "fraction"},
]
TOPIC_BY_SLUG = {t["slug"]: t for t in TOPICS}

GRADES = [
    {"slug": "kindergarten", "name": "Kindergarten", "label": "Kindergarten Grade"},
    {"slug": "first", "name": "First", "label": "First Grade"},
    {"slug": "second", "name": "Second", "label": "Second Grade"},
    {"slug": "third", "name": "Third", "label": "Third Grade"},
    {"slug": "fourth", "name": "Fourth", "label": "Fourth Grade"},
    {"slug": "fifth", "name": "Fifth", "label": "Fifth Grade"},
    {"slug": "sixth", "name": "Sixth", "label": "Sixth Grade"},
]
GRADE_BY_SLUG = {g["slug"]: g for g in GRADES}

QUIZ_RANGES = {
    "addition": ["0-10", "0-5", "11-20", "20-50"],
    "subtraction": ["0-5", "0-10", "0-20"],
    "multiplication": ["0-10", "0-5", "6-10", "11-12", "1’s, 2’s, 5’s, 10’s",
                       "1's", "2's", "3's", "4's", "5's", "6's", "7's", "8's", "9's", "10's", "11's", "12's",
                       "Products to 100"],
    "division": ["1-10", "1-5", "6-10", "1's", "2's", "3's", "4's", "5's", "6's", "7's", "8's", "9's", "10's"],
}
QUIZ_OPERATIONS = {"addition": "Addition", "subtraction": "Subtraction",
                   "multiplication": "Multiplication", "division": "Division"}
QUIZ_SYMBOL = {"addition": "+", "subtraction": "-", "multiplication": "×", "division": "÷"}

CERTIFICATE_THEMES = [
    {"key": "mathgirl", "label": "Math Girl"},
    {"key": "mathboy", "label": "Math Boy"},
    {"key": "mathasaurusrex", "label": "Mathasaurus Rex"},
    {"key": "mathninja", "label": "Math Ninja"},
    {"key": "mathcat", "label": "Math Cat"},
    {"key": "mathlete", "label": "Mathlete"},
    {"key": "mathicorn", "label": "Mathicorn"},
]

QUIZ_FEEDBACK = [
    (100, 100, "Great Job!"),
    (90, 99, "Nice Job!"),
    (70, 89, "Pretty Good!"),
    (0, 69, "Keep Trying!"),
]


def quiz_feedback(score_pct: float) -> str:
    for lo, hi, text in QUIZ_FEEDBACK:
        if lo <= score_pct <= hi:
            return text
    return "Keep Trying!"


def generate_questions(operation: str, range_label: str, total: int) -> list:
    """Generate quiz questions using the same fact logic as the upstream tool."""
    rng = random.Random()
    questions = []
    seen = set()

    def add(a, b, answer):
        key = (a, b)
        if key in seen:
            return False
        seen.add(key)
        questions.append([a, b, answer])
        return True

    def rand(lo, hi):
        return rng.randint(lo, hi)

    attempts = 0
    while len(questions) < total and attempts < total * 400:
        attempts += 1
        if operation == "addition":
            if range_label == "0-5":
                lo, hi = 0, 5
            elif range_label == "11-20":
                lo, hi = 11, 20
            elif range_label == "20-50":
                lo, hi = 20, 50
            else:
                lo, hi = 0, 10
            s = rand(lo, hi)
            a = rand(0, s)
            add(a, s - a, s)
        elif operation == "subtraction":
            if range_label == "0-5":
                lo, hi = 0, 5
            elif range_label == "0-20":
                lo, hi = 0, 20
            else:
                lo, hi = 0, 10
            d = rand(lo, hi)
            a = d + rand(0, 10)
            add(a, d, a - d)
        elif operation == "multiplication":
            if range_label == "Products to 100":
                a = rand(2, 10)
                b = rand(2, 12)
                if a * b > 100:
                    continue
                add(a, b, a * b)
            elif range_label == "1’s, 2’s, 5’s, 10’s":
                a = rng.choice([1, 2, 5, 10])
                b = rand(0, 10)
                add(a, b, a * b)
            elif re.fullmatch(r"(\d+)'s", range_label):
                a = int(range_label[:-2])
                b = rand(0, 12)
                add(a, b, a * b)
            elif range_label == "11-12":
                a = rand(11, 12)
                b = rand(2, 12)
                add(a, b, a * b)
            elif range_label == "0-5":
                a = rand(0, 5)
                b = rand(0, 5)
                add(a, b, a * b)
            elif range_label == "6-10":
                a = rand(6, 10)
                b = rand(0, 10)
                add(a, b, a * b)
            else:  # 0-10
                a = rand(0, 10)
                b = rand(0, 10)
                add(a, b, a * b)
        elif operation == "division":
            if re.fullmatch(r"(\d+)'s", range_label):
                b = int(range_label[:-2])
                q = rand(1, 10)
                add(b * q, b, q)
            elif range_label == "1-5":
                b = rand(1, 5)
                q = rand(1, 10)
                add(b * q, b, q)
            elif range_label == "6-10":
                b = rand(6, 10)
                q = rand(1, 10)
                add(b * q, b, q)
            else:  # 1-10
                b = rand(1, 10)
                q = rand(1, 10)
                add(b * q, b, q)
    # pad if the range is too small (e.g. 30 questions from 0-5 sums)
    rng2 = random.Random(42)
    while len(questions) < total:
        a = rng2.randint(0, 10)
        b = rng2.randint(0, 10)
        questions.append([a, b, operation_answer(operation, a, b)])
    return questions[:total]


def operation_answer(operation: str, a: int, b: int) -> int:
    if operation == "addition":
        return a + b
    if operation == "subtraction":
        return a - b
    if operation == "multiplication":
        return a * b
    if operation == "division":
        return a // b
    return 0


def needs_practice(questions: list, answers: list) -> list:
    """Facts answered wrong >= 1/3 of the time with >= 3 occurrences (upstream rule)."""
    occurrences: dict[int, int] = {}
    wrongs: dict[int, int] = {}
    for (a, b, correct), ans in zip(questions, answers):
        fact = a if a <= b else b
        occurrences[fact] = occurrences.get(fact, 0) + 1
        if ans != correct:
            wrongs[fact] = wrongs.get(fact, 0) + 1
    result = []
    for fact, occ in occurrences.items():
        if occ >= 3 and wrongs.get(fact, 0) / occ >= 0.33:
            result.append(fact)
    return sorted(result)


# ---------------------------------------------------------------------------
# Search (scored token overlap — never strict AND)
# ---------------------------------------------------------------------------

STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
              "is", "it", "by", "with", "how", "what", "your", "you"}

SEARCH_INDEX = None


def build_search_index():
    rows = []
    for g in Game.query.all():
        text = " ".join([g.title, g.description or "", g.contents or "",
                         (g.topic or ""), " ".join((g.grades or "").split(","))])
        rows.append({"kind": "game", "title": g.title, "url": f"/math-games/{g.slug}",
                     "text": text, "icon": "game"})
    for l in Lesson.query.all():
        body = " ".join(re.sub(r"<[^>]+>", " ", p) for p in json.loads(l.pages or "[]"))
        text = " ".join([l.title, l.topic, "lesson lessons", body[:4000]])
        rows.append({"kind": "lesson", "title": l.title,
                     "url": f"/math-help/{l.topic}/{l.slug}", "text": text, "icon": "lesson"})
    for t in Teaser.query.all():
        rows.append({"kind": "teaser", "title": t.title, "url": f"/brain-teasers/{t.slug}",
                     "text": " ".join([t.title, t.blurb or "", "brain teaser puzzle"]), "icon": "teaser"})
    for m in Manipulative.query.all():
        rows.append({"kind": "manipulative", "title": m.title, "url": f"/manipulatives/{m.slug}",
                     "text": " ".join([m.title, m.about or "", "manipulative tool"]), "icon": "manipulative"})
    return rows


def get_search_index():
    global SEARCH_INDEX
    if SEARCH_INDEX is None:
        SEARCH_INDEX = build_search_index()
    return SEARCH_INDEX


def tokenize(query: str) -> list:
    return [t.lower() for t in re.split(r"\W+", query)
            if t.lower() not in STOP_WORDS and len(t) > 1]


def scored_search(query: str, index=None):
    tokens = tokenize(query)
    if not tokens:
        return []
    index = index if index is not None else get_search_index()
    scored = []
    for row in index:
        text = row["text"].lower()
        title = row["title"].lower()
        score = 0
        for t in tokens:
            if t in title:
                score += 3
            if t in text:
                score += 1
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["title"]))
    return [row for _, row in scored]


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    return {
        "TOPICS": TOPICS,
        "GRADES": GRADES,
        "THEME_LABELS": {t["key"]: t["label"] for t in CERTIFICATE_THEMES},
        "current_year": 2026,
    }


def game_by_slug(slug):
    return Game.query.filter_by(slug=slug).first()


def game_card(game, style="grid"):
    """Data dict for a game card tile."""
    return {
        "slug": game.slug,
        "title": game.title,
        "topic": game.topic,
        "tid": TOPIC_BY_SLUG[game.topic]["tid"] if game.topic in TOPIC_BY_SLUG else None,
    }


def related_games(game, limit=None):
    # Upstream shows every related game of the current game (e.g. six on the
    # Tortuga Racing page); the frozen seed carries the same related lists.
    slugs = [s for s in (game.related or "").split(",") if s]
    if limit is not None:
        slugs = slugs[:limit]
    out = []
    for s in slugs:
        g = game_by_slug(s)
        if g:
            out.append(g)
    return out


def lesson_sidebar(topic):
    lessons = Lesson.query.filter_by(topic=topic).order_by(Lesson.order_in_topic).all()
    games = [g for g in Game.query.order_by(Game.id).all() if topic in g.topic_list]
    return lessons, games


def teaser_row(t):
    return {"slug": t.slug, "title": t.title, "blurb": t.blurb}


# ---------------------------------------------------------------------------
# Core pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    featured = Game.query.filter(Game.featured.isnot(None)).order_by(Game.featured).all()
    manipulatives = Manipulative.query.order_by(Manipulative.order).all()
    teasers = []
    for slug in HOMEPAGE_TEASER_SLUGS:
        teaser = Teaser.query.filter_by(slug=slug).first()
        if teaser is not None:
            teasers.append(teaser)
    return render_template("index.html", featured=featured,
                           manipulatives=manipulatives, teasers=teasers)


@app.route("/math-games")
def math_games():
    games = Game.query.order_by(Game.id).all()
    order = {slug: i for i, slug in enumerate(ALL_GAMES_GRID_ORDER)}
    games.sort(key=lambda g: (order.get(g.slug, len(order)), g.id))
    return render_template("math_games.html", games=games,
                           active_topic=None, active_grade=None, heading="Math Games")


@app.route("/math-games/<ident>", endpoint="game_detail")
def math_games_view(ident):
    if ident in TOPIC_BY_SLUG:
        topic = TOPIC_BY_SLUG[ident]
        games = [g for g in Game.query.order_by(Game.id).all() if ident in g.topic_list]
        def pos(g):
            try:
                return json.loads(g.topic_position or "{}").get(ident, 999)
            except ValueError:
                return 999
        games.sort(key=pos)
        return render_template("math_games.html", games=games,
                               active_topic=ident, active_grade=None,
                               heading=f"{topic['name']} Games")
    if ident in GRADE_BY_SLUG:
        grade = GRADE_BY_SLUG[ident]
        games = [g for g in Game.query.order_by(Game.id).all()
                 if ident in (g.grades or "").split(",")]
        def gpos(g):
            try:
                return json.loads(g.grade_position or "{}").get(ident, 999)
            except ValueError:
                return 999
        games.sort(key=gpos)
        return render_template("math_games.html", games=games,
                               active_topic=None, active_grade=ident,
                               heading=f"{grade['name']} Grade Games")
    game = game_by_slug(ident)
    if game is None:
        abort(404)
    related = related_games(game)
    topic_name = TOPIC_BY_SLUG[game.topic]["name"] if game.topic in TOPIC_BY_SLUG else (game.topic or "Integers").title()
    is_favorite = False
    if current_user.is_authenticated:
        is_favorite = Favorite.query.filter_by(user_id=current_user.id, game_slug=game.slug).first() is not None
    return render_template("game_detail.html", game=game, related=related,
                           topic_name=topic_name, is_favorite=is_favorite)


@app.route("/math-games/<slug>/favorite", methods=["POST"])
@login_required
def toggle_favorite(slug):
    game = game_by_slug(slug)
    if game is None:
        abort(404)
    existing = Favorite.query.filter_by(user_id=current_user.id, game_slug=slug).first()
    if existing:
        db.session.delete(existing)
        flash(f"Removed {game.title} from your favorites.")
    else:
        db.session.add(Favorite(user_id=current_user.id, game_slug=slug))
        flash(f"Added {game.title} to your favorites.")
    db.session.commit()
    return redirect(request.form.get("next") or url_for("game_detail", ident=slug))


@app.route("/games/<slug>/result", methods=["POST"])
def game_result(slug):
    game = game_by_slug(slug)
    if game is None:
        abort(404)
    try:
        facts_total = int(request.form.get("facts_total", "0"))
        facts_correct = int(request.form.get("facts_correct", "0"))
        position = int(request.form.get("position", "1"))
        duration = float(request.form.get("duration", "0"))
    except ValueError:
        abort(400)
    if facts_total <= 0 or facts_total > 50 or facts_correct < 0 or facts_correct > facts_total:
        abort(400)
    play = GamePlay(user_id=current_user.id if current_user.is_authenticated else None,
                    game_slug=slug, facts_total=facts_total,
                    facts_correct=facts_correct, position=position,
                    duration_seconds=duration)
    db.session.add(play)
    db.session.commit()
    return {"ok": True, "play_id": play.id}


@app.route("/math-help")
def lessons_index():
    topics = []
    for t in TOPICS:
        first = Lesson.query.filter_by(topic=t["slug"]).order_by(Lesson.order_in_topic).limit(3).all()
        topics.append({**t, "first_lessons": first})
    return render_template("lessons_index.html", topics=topics)


@app.route("/math-help/<topic>")
def lessons_topic(topic):
    if topic not in TOPIC_BY_SLUG:
        abort(404)
    lessons, games = lesson_sidebar(topic)
    return render_template("lessons_topic.html", topic=TOPIC_BY_SLUG[topic],
                           lessons=lessons, games=games)


@app.route("/math-help/<topic>/<slug>")
def lesson_page(topic, slug):
    if topic not in TOPIC_BY_SLUG:
        abort(404)
    lesson = Lesson.query.filter_by(topic=topic, slug=slug).first_or_404()
    try:
        page_no = max(0, int(request.args.get("page", "0")))
    except ValueError:
        page_no = 0
    pages = json.loads(lesson.pages or "[]")
    if page_no >= len(pages):
        abort(404)
    lessons, games = lesson_sidebar(topic)
    body_html = localize_lesson_images(pages[page_no])
    return render_template("lesson_detail.html", lesson=lesson, topic=TOPIC_BY_SLUG[topic],
                           page_no=page_no, page_count=len(pages),
                           body_html=body_html, sidebar_lessons=lessons,
                           sidebar_games=games)


# ---------------------------------------------------------------------------
# Quizzes
# ---------------------------------------------------------------------------

@app.route("/quizzes")
def quizzes_index():
    return render_template("quizzes_index.html")


@app.route("/quizzes/<operation>")
def quiz_page(operation):
    if operation not in QUIZ_OPERATIONS:
        abort(404)
    op_name = QUIZ_OPERATIONS[operation]
    attempt_token = request.args.get("attempt")
    attempt = None
    if attempt_token:
        attempt = QuizAttempt.query.filter_by(token=attempt_token).first()
        if attempt is None or attempt.operation != op_name:
            attempt = None
    view = request.args.get("view")
    if attempt and attempt.status == "complete" and view == "results":
        return render_quiz_results(attempt, operation)
    if attempt and attempt.status == "complete":
        return render_quiz_results(attempt, operation)
    if attempt:
        return render_quiz_question(attempt, operation)
    return render_template("quiz_page.html", operation=operation, op_name=op_name,
                           ranges=QUIZ_RANGES[operation], symbol=QUIZ_SYMBOL[operation])


def new_attempt_token() -> str:
    while True:
        token = os.urandom(12).hex()
        if not QuizAttempt.query.filter_by(token=token).first():
            return token


@app.route("/quizzes/<operation>/start", methods=["POST"])
def quiz_start(operation):
    if operation not in QUIZ_OPERATIONS:
        abort(404)
    range_label = request.form.get("range", "")
    if range_label not in QUIZ_RANGES[operation]:
        abort(400)
    total = request.form.get("questions", "10")
    if total not in ("10", "20", "30"):
        abort(400)
    tpq = request.form.get("time", "30")
    if tpq not in ("30", "15", "5", "unlimited"):
        abort(400)
    questions = generate_questions(operation, range_label, int(total))
    attempt = QuizAttempt(token=new_attempt_token(),
                          user_id=current_user.id if current_user.is_authenticated else None,
                          operation=QUIZ_OPERATIONS[operation],
                          range_label=range_label,
                          total_questions=int(total),
                          time_per_question=("Unlimited" if tpq == "unlimited" else tpq),
                          questions=json.dumps(questions),
                          answers=json.dumps([]),
                          elapsed_ms=json.dumps([]))
    db.session.add(attempt)
    db.session.commit()
    return redirect(url_for("quiz_page", operation=operation, attempt=attempt.token))


def render_quiz_question(attempt, operation):
    questions = json.loads(attempt.questions)
    answers = json.loads(attempt.answers)
    index = len(answers)
    if index >= len(questions):
        return finish_attempt(attempt, operation, redirect_back=True)
    a, b, _ = questions[index]
    return render_template("quiz_question.html", attempt=attempt, operation=operation,
                           op_name=attempt.operation, symbol=QUIZ_SYMBOL[operation],
                           question_no=index + 1, question=[a, b],
                           time_per_question=attempt.time_per_question)


@app.route("/quizzes/<operation>/answer", methods=["POST"])
def quiz_answer(operation):
    if operation not in QUIZ_OPERATIONS:
        abort(404)
    token = request.form.get("attempt", "")
    attempt = QuizAttempt.query.filter_by(token=token).first_or_404()
    if attempt.operation != QUIZ_OPERATIONS[operation]:
        abort(400)
    if attempt.status == "complete":
        return redirect(url_for("quiz_page", operation=operation, attempt=token, view="results"))
    answers = json.loads(attempt.answers)
    elapsed = json.loads(attempt.elapsed_ms)
    raw = (request.form.get("answer") or "").strip()
    timed_out = request.form.get("timeout") == "1"
    if timed_out or not raw or not re.fullmatch(r"-?\d+", raw):
        answers.append(-1)
    else:
        answers.append(int(raw))
    try:
        elapsed.append(max(0, int(float(request.form.get("elapsed_ms", "0")))))
    except ValueError:
        elapsed.append(0)
    attempt.answers = json.dumps(answers)
    attempt.elapsed_ms = json.dumps(elapsed)
    questions = json.loads(attempt.questions)
    if len(answers) >= len(questions):
        return finish_attempt(attempt, operation, redirect_back=False)
    db.session.commit()
    return redirect(url_for("quiz_page", operation=operation, attempt=token))


def finish_attempt(attempt, operation, redirect_back=True):
    questions = json.loads(attempt.questions)
    answers = json.loads(attempt.answers)
    correct = sum(1 for (a, b, ans), got in zip(questions, answers) if got == ans)
    attempt.correct_count = correct
    attempt.score_pct = round(correct / len(questions) * 100, 1) if questions else 0
    elapsed = [e for e in json.loads(attempt.elapsed_ms) if e > 0]
    attempt.avg_seconds = round(sum(elapsed) / len(elapsed) / 1000, 1) if elapsed else 0.0
    attempt.status = "complete"
    attempt.completed_at = datetime(2026, 9, 26, 12, 0, 0)
    db.session.commit()
    return redirect(url_for("quiz_page", operation=operation, attempt=attempt.token, view="results"))


def render_quiz_results(attempt, operation):
    questions = json.loads(attempt.questions)
    answers = json.loads(attempt.answers)
    rows = []
    for (a, b, correct), got in zip(questions, answers):
        rows.append({"a": a, "b": b, "correct": correct,
                     "got": got, "symbol": QUIZ_SYMBOL[operation],
                     "right": got == correct})
    practice = needs_practice(questions, answers)
    certificate = Certificate.query.filter_by(attempt_id=attempt.id).first()
    return render_template("quiz_results.html", attempt=attempt, operation=operation,
                           rows=rows, needs_practice=practice,
                           feedback=quiz_feedback(attempt.score_pct),
                           certificate=certificate,
                           certificate_threshold=math.ceil(attempt.total_questions * 0.8),
                           themes=CERTIFICATE_THEMES)


@app.route("/quiz/<token>/certificate", methods=["POST"])
def issue_certificate(token):
    attempt = QuizAttempt.query.filter_by(token=token).first_or_404()
    if attempt.status != "complete":
        abort(400)
    if attempt.score_pct < 80:
        abort(400)
    if Certificate.query.filter_by(attempt_id=attempt.id).first():
        return redirect(url_for("quiz_page", operation=attempt.operation.lower(),
                                attempt=token, view="results"))
    name = (request.form.get("name") or "").strip()[:25]
    theme = request.form.get("theme", "")
    if not name:
        flash("Enter your name for the certificate.")
        return redirect(url_for("quiz_page", operation=attempt.operation.lower(),
                                attempt=token, view="results"))
    if theme not in {t["key"] for t in CERTIFICATE_THEMES}:
        theme = "mathgirl"
    cert = Certificate(user_id=attempt.user_id or (current_user.id if current_user.is_authenticated else None),
                       attempt_id=attempt.id, person_name=name, theme=theme,
                       operation=attempt.operation, range_label=attempt.range_label,
                       correct=attempt.correct_count, total=attempt.total_questions)
    db.session.add(cert)
    db.session.commit()
    return redirect(url_for("certificate_view", cert_id=cert.id))


@app.route("/certificate/<int:cert_id>")
def certificate_view(cert_id):
    cert = db.session.get(Certificate, cert_id) or abort(404)
    theme_label = {t["key"]: t["label"] for t in CERTIFICATE_THEMES}.get(cert.theme, cert.theme)
    return render_template("certificate.html", cert=cert, theme_label=theme_label)


# ---------------------------------------------------------------------------
# Manipulatives
# ---------------------------------------------------------------------------

@app.route("/manipulatives")
def manipulatives_index():
    items = Manipulative.query.order_by(Manipulative.order).all()
    return render_template("manipulatives_index.html", items=items)


@app.route("/manipulatives/<slug>")
def manipulative_page(slug):
    item = Manipulative.query.filter_by(slug=slug).first_or_404()
    others = Manipulative.query.filter(Manipulative.slug != slug).order_by(Manipulative.order).all()
    return render_template("manipulative_detail.html", item=item, others=others)


# ---------------------------------------------------------------------------
# Brain teasers
# ---------------------------------------------------------------------------

@app.route("/brain-teasers")
def teasers_index():
    teasers = Teaser.query.order_by(Teaser.order).all()
    return render_template("teasers_index.html", teasers=teasers)


@app.route("/brain-teasers/<slug>")
def teaser_page(slug):
    teaser = Teaser.query.filter_by(slug=slug).first_or_404()
    others = Teaser.query.filter(Teaser.slug != slug).order_by(Teaser.order).limit(3).all()
    has_hint = slug == "how-many-triangles"
    # Upstream ships most teaser solutions as PNG, but how-many-triangles'
    # solution is a JPG (no_of_triangle_solution_0.jpg); serve whichever
    # file the asset archive actually carries.
    solution_src = f"/static/images/teasers/solution/{slug}.png"
    if not os.path.isfile(os.path.join(BASE_DIR, "static", "images", "teasers", "solution", f"{slug}.png")):
        if os.path.isfile(os.path.join(BASE_DIR, "static", "images", "teasers", "solution", f"{slug}.jpg")):
            solution_src = f"/static/images/teasers/solution/{slug}.jpg"
    extra_images = []
    if slug == "handshake-puzzle":
        extra_images = ["handshake-puzzle-solution-3", "handshake-puzzle-solution-4", "handshake-puzzle-solution-5"]
    return render_template("teaser_detail.html", teaser=teaser, others=others,
                           has_hint=has_hint, extra_images=extra_images,
                           solution_src=solution_src)


# ---------------------------------------------------------------------------
# Static / footer pages
# ---------------------------------------------------------------------------

@app.route("/privacy-policy")
def privacy_policy():
    return render_template("static_page.html", title="Privacy Policy",
                           body_html="""<p>Coolmath4Kids is a math practice site for kids, teachers and parents. This mirror environment stores your quiz attempts, certificates and favorite games so you can track your progress.</p><p>We do not sell personal information. Progress data can be removed at any time by deleting your account.</p>""")


@app.route("/copyright-infringement-notice-procedure")
def copyright_notice():
    return render_template("static_page.html", title="Copyright Infringement Notice procedure",
                           body_html="""<p>If you believe your copyrighted content is on our Site without consent, please follow our Copyright Infringement Notice procedure: send a description of the work, where it appears, and your contact information.</p>""")


@app.route("/accessibility")
def accessibility():
    return render_template("static_page.html", title="Accessibility Policy",
                           body_html="""<p>Coolmath is committed to ensuring digital accessibility for everyone. We aim to meet WCAG 2.1 AA across our lessons, quizzes and games.</p>""")


@app.route("/global-privacy-policy")
def global_privacy_policy():
    return render_template("static_page.html", title="Global Privacy Policy",
                           body_html="""<p>We use first party cookies on our website to enhance your browsing experience. You can accept or reject cookies at any time from your browser settings.</p>""")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@app.route("/search")
def search():
    query = (request.args.get("q") or "").strip()
    results = scored_search(query) if query else []
    games = [r for r in results if r["kind"] == "game"]
    lessons = [r for r in results if r["kind"] == "lesson"]
    teasers = [r for r in results if r["kind"] == "teaser"]
    manips = [r for r in results if r["kind"] == "manipulative"]
    return render_template("search.html", query=query, results=results,
                           games=games, lessons=lessons, teasers=teasers,
                           manips=manips)


# ---------------------------------------------------------------------------
# Auth + account
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f"Welcome back, {user.display_name}!")
            return redirect(url_for("account"))
        flash("Invalid email or password.")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        display_name = (request.form.get("display_name") or "").strip()
        password = request.form.get("password") or ""
        error = None
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
            error = "Username must be 3-32 characters (letters, digits, dot, dash, underscore)."
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            error = "Enter a valid email address."
        elif len(display_name) < 2:
            error = "Enter your name."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif User.query.filter((User.email == email) | (User.username == username)).first():
            error = "That username or email is already registered."
        if error:
            flash(error)
            return render_template("register.html")
        user = User(username=username, email=email, display_name=display_name,
                    password_hash=bcrypt.generate_password_hash(password).decode())
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f"Welcome, {display_name}! Your progress tracker is ready.")
        return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    attempts = QuizAttempt.query.filter_by(user_id=current_user.id).order_by(QuizAttempt.id).all()
    certs = Certificate.query.filter_by(user_id=current_user.id).order_by(Certificate.id).all()
    favs = []
    for f in Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.id).all():
        g = game_by_slug(f.game_slug)
        if g:
            favs.append({"fav": f, "game": g})
    plays = GamePlay.query.filter_by(user_id=current_user.id).order_by(GamePlay.id).all()
    best = {}
    for op in QUIZ_OPERATIONS.values():
        rows = [a for a in attempts if a.operation == op and a.status == "complete"]
        if rows:
            best[op] = max(a.score_pct for a in rows)
    return render_template("account.html", attempts=attempts, certificates=certs,
                           favorites=favs, plays=plays, best_scores=best,
                           play_games={g.slug: g for g in Game.query.all()})


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()
        new_password = request.form.get("new_password") or ""
        current_password = request.form.get("current_password") or ""
        if len(display_name) < 2:
            flash("Enter your name.")
        elif not bcrypt.check_password_hash(current_user.password_hash, current_password):
            flash("Enter your current password to save changes.")
        else:
            current_user.display_name = display_name
            if new_password:
                if len(new_password) < 8:
                    flash("New password must be at least 8 characters.")
                    return render_template("account_edit.html")
                current_user.password_hash = bcrypt.generate_password_hash(new_password).decode()
            db.session.commit()
            flash("Your profile has been updated.")
            return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/account/favorites/<int:fav_id>/remove", methods=["POST"])
@login_required
def remove_favorite(fav_id):
    fav = Favorite.query.filter_by(id=fav_id, user_id=current_user.id).first_or_404()
    game = game_by_slug(fav.game_slug)
    db.session.delete(fav)
    db.session.commit()
    flash(f"Removed {game.title if game else fav.game_slug} from your favorites.")
    return redirect(url_for("account"))


# ---------------------------------------------------------------------------
# Health + errors
# ---------------------------------------------------------------------------

@app.route("/_health")
def health():
    ok = db.session.execute(db.text("SELECT 1")).scalar() == 1
    counts = {
        "games": Game.query.count(),
        "lessons": Lesson.query.count(),
        "teasers": Teaser.query.count(),
        "manipulatives": Manipulative.query.count(),
        "users": User.query.count(),
    }
    return {"ok": ok, "site": "coolmath4kids", "counts": counts}


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def seed_database():
    if Game.query.count() > 0:
        return
    from _seed_games import GAMES
    from _seed_lessons import LESSONS
    from seed_data import TEASERS, MANIPULATIVES, LESSON_ORDER

    for g in GAMES:
        db.session.add(Game(slug=g["slug"], title=g["title"], topic=g["topic"],
                            topics=",".join(g["topics"]),
                            topic_position=json.dumps(g["topic_position"]),
                            grade_position=json.dumps(g.get("grade_position", {})),
                            description=g["description"], contents=g["contents"],
                            standards=g["standards"], players=g["players"],
                            featured=g["featured"], related=",".join(g["related"]),
                            grades=",".join(g["grades"])))
    for t, slugs in LESSON_ORDER.items():
        for i, slug in enumerate(slugs):
            lesson = next((l for l in LESSONS if l["topic"] == t and l["slug"] == slug), None)
            if lesson is None:
                continue
            db.session.add(Lesson(topic=t, slug=slug, title=lesson["title"],
                                  order_in_topic=i, pages=json.dumps(lesson["pages"])))
    for i, t in enumerate(TEASERS):
        db.session.add(Teaser(slug=t["slug"], title=t["title"], blurb=t["blurb"], order=i))
    for i, m in enumerate(MANIPULATIVES):
        db.session.add(Manipulative(slug=m["slug"], title=m["title"], about=m["about"], order=i))
    db.session.commit()


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    from seed_data import seed_benchmark_data
    seed_benchmark_data(db, bcrypt, MIRROR_REFERENCE_DATE)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 40000))
    app.run(host="0.0.0.0", port=port, debug=False)
