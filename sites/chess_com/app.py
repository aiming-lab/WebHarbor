"""Chess.com mirror — Flask app.

A deterministic offline mirror of https://www.chess.com/ built for the
WebHarbor benchmark environment. Content (leaderboards, member profiles,
news articles, openings with ECO stats, lessons, master games, puzzles,
clubs, events) is captured from the live site and frozen into the seed
database by seed_data.py at build time.

Route surface mirrors the upstream site's public pages:
  /                      homepage
  /play, /play/online, /play/computer
  /puzzles (+/rated, /daily, /themes, /problem/<id>) and /daily
  /lessons (+/category/<slug>, /<slug>)
  /openings (+/<slug>)
  /watch, /events, /events/info/<slug>
  /leaderboard/live (+/bullet, /rapid), /leaderboard/tactics, /leaderboard/daily
  /member/<username>, /stats/live/<type>/<username>
  /members, /members/titled-players
  /games, /games/<player-slug>, /games/view/<id>
  /news (+?page=, /category/<slug>, /view/<slug>)
  /clubs, /club/<slug>
  /today
  /search?q=
  /login, /register, /logout, /settings
  /_health
"""
import json
import os
from datetime import datetime, timezone

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

# ------------------------------------------------------------------ constants

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 5000))

MIRROR_REFERENCE_DATE = datetime(2026, 9, 22, tzinfo=timezone.utc)

LEADERBOARD_TYPES = {
    "live": {"label": "Blitz", "title": "Blitz Leaderboard", "key": "blitz"},
    "live/bullet": {"label": "Bullet", "title": "Bullet Leaderboard", "key": "bullet"},
    "live/rapid": {"label": "Rapid", "title": "Rapid Leaderboard", "key": "rapid"},
    "tactics": {"label": "Tactics", "title": "Tactics Leaderboard", "key": "tactics"},
    "daily": {"label": "Daily", "title": "Daily Leaderboard", "key": "daily"},
}

STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
              "or", "is", "it", "by", "with", "vs"}

# ------------------------------------------------------------------ app setup

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR}/instance/chess_com.db"
app.config["SECRET_KEY"] = "webharbor-chess-com-dev-key"
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."


# ------------------------------------------------------------------ models

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(128), unique=True)
    password_hash = db.Column(db.String(128))
    name = db.Column(db.String(128))
    title = db.Column(db.String(8))
    country_code = db.Column(db.String(2))
    country_name = db.Column(db.String(64))
    country_id = db.Column(db.Integer)
    location = db.Column(db.String(128))
    avatar = db.Column(db.String(255))
    avatar_small = db.Column(db.String(255))
    flair_svg = db.Column(db.String(255))
    flair_label = db.Column(db.String(64))
    membership = db.Column(db.String(16))
    followers = db.Column(db.Integer, default=0)
    joined = db.Column(db.String(32))
    last_online = db.Column(db.String(32))
    status = db.Column(db.String(16))
    is_streamer = db.Column(db.Boolean, default=False)
    twitch_url = db.Column(db.String(255))
    league = db.Column(db.String(32))
    verified = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    is_real_member = db.Column(db.Boolean, default=False)   # harvested upstream member
    about = db.Column(db.Text)
    badges = db.Column(db.JSON, default=list)
    is_bot = db.Column(db.Boolean, default=False)
    bot_rating = db.Column(db.Integer)

    ratings = db.relationship("PlayerRating", backref="user", lazy=True,
                              order_by="PlayerRating.id")
    follows = db.relationship("Follow", backref="follower", lazy=True,
                              foreign_keys="Follow.follower_id")

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode()

    def check_password(self, password):
        return self.password_hash and bcrypt.check_password_hash(self.password_hash, password)

    @property
    def rating_summary(self):
        return {r.category: r for r in self.ratings}

    def get_id(self):
        return str(self.id)


class PlayerRating(db.Model):
    __tablename__ = "player_ratings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category = db.Column(db.String(16), nullable=False)     # blitz/bullet/rapid/daily/tactics/rush
    rating = db.Column(db.Integer)
    best_rating = db.Column(db.Integer)
    rank = db.Column(db.Integer)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)


class LeaderboardEntry(db.Model):
    __tablename__ = "leaderboard_entries"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(16), nullable=False, index=True)
    rank = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Integer)
    username = db.Column(db.String(64), nullable=False, index=True)
    chess_title = db.Column(db.String(8))
    country_name = db.Column(db.String(64))
    country_id = db.Column(db.Integer)
    avatar_url = db.Column(db.String(255))
    membership_level = db.Column(db.Integer)
    flair_svg = db.Column(db.String(255))
    flair_label = db.Column(db.String(64))
    total_games = db.Column(db.Integer)
    wins = db.Column(db.Integer)
    draws = db.Column(db.Integer)
    losses = db.Column(db.Integer)
    trend_direction = db.Column(db.Integer)
    trend_delta = db.Column(db.Integer)
    snapshot_time = db.Column(db.String(64))
    __table_args__ = (db.UniqueConstraint("category", "rank", name="uq_lb_cat_rank"),)


class LeaderboardStats(db.Model):
    """The rating-distribution sidebar the leaderboard pages render."""
    __tablename__ = "leaderboard_stats"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(16), nullable=False, index=True)
    avg_rating = db.Column(db.Float)
    player_count = db.Column(db.Integer)
    distribution = db.Column(db.JSON)


class NewsArticle(db.Model):
    __tablename__ = "news_articles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(192), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(64))
    author_title = db.Column(db.String(8))
    published = db.Column(db.String(32))
    hero_image = db.Column(db.String(255))
    excerpt = db.Column(db.Text)
    body = db.Column(db.JSON, default=list)
    inline_images = db.Column(db.JSON, default=list)
    categories = db.Column(db.JSON, default=list)
    featured = db.Column(db.Boolean, default=False)
    page = db.Column(db.Integer, default=1)


class Opening(db.Model):
    __tablename__ = "openings"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(128), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    eco = db.Column(db.String(3))
    moves = db.Column(db.String(255))
    description = db.Column(db.Text)
    sections = db.Column(db.JSON, default=list)
    popularity = db.Column(db.JSON)
    games_count = db.Column(db.Integer)
    is_variation = db.Column(db.Boolean, default=False)
    parent_slug = db.Column(db.String(128), index=True)
    sort_order = db.Column(db.Integer, default=0)


class OpeningTopPlayer(db.Model):
    __tablename__ = "opening_top_players"
    id = db.Column(db.Integer, primary_key=True)
    opening_id = db.Column(db.Integer, db.ForeignKey("openings.id"), nullable=False, index=True)
    name = db.Column(db.String(128))
    chess_title = db.Column(db.String(32))
    country_name = db.Column(db.String(64))
    games_count = db.Column(db.Integer)
    avatar_url = db.Column(db.String(255))
    member_url = db.Column(db.String(255))


class LessonCourse(db.Model):
    __tablename__ = "lesson_courses"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(128), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    author = db.Column(db.String(128))
    level = db.Column(db.Integer, default=0)
    level_label = db.Column(db.String(32))
    n_lessons = db.Column(db.Integer)
    mastery = db.Column(db.Boolean, default=False)
    image = db.Column(db.String(255))
    categories = db.Column(db.JSON, default=list)
    featured = db.Column(db.Boolean, default=False)


class Puzzle(db.Model):
    __tablename__ = "puzzles"
    id = db.Column(db.Integer, primary_key=True)
    legacy_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    title = db.Column(db.String(128))
    fen = db.Column(db.String(128), nullable=False)
    uci_moves = db.Column(db.JSON, default=list)      # [{"from": "d8", "to": "d5"}, ...]
    san_moves = db.Column(db.JSON, default=list)
    themes = db.Column(db.JSON, default=list)
    goals = db.Column(db.String(64))
    rating = db.Column(db.Integer)
    pgn = db.Column(db.Text)
    comment_count = db.Column(db.Integer)
    solved_count = db.Column(db.Integer)
    author_username = db.Column(db.String(64))
    author_title = db.Column(db.String(8))
    author_name = db.Column(db.String(128))
    is_daily = db.Column(db.Boolean, default=False)
    daily_date = db.Column(db.String(32))


class PuzzleAttempt(db.Model):
    __tablename__ = "puzzle_attempts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    puzzle_id = db.Column(db.Integer, db.ForeignKey("puzzles.id"), nullable=False)
    solved = db.Column(db.Boolean, default=False)
    used_hint = db.Column(db.Boolean, default=False)
    rating_before = db.Column(db.Integer)
    rating_after = db.Column(db.Integer)
    attempted_at = db.Column(db.String(32))
    user = db.relationship("User", backref="attempts")
    puzzle = db.relationship("Puzzle", backref="attempts")


class MasterPlayer(db.Model):
    __tablename__ = "master_players"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(128), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    image = db.Column(db.String(255))
    photo_credit = db.Column(db.String(128))
    born = db.Column(db.String(64))
    birthplace = db.Column(db.String(128))
    federation = db.Column(db.String(64))
    total_games = db.Column(db.Integer)
    as_white = db.Column(db.JSON)
    as_black = db.Column(db.JSON)


class MasterGame(db.Model):
    __tablename__ = "master_games"
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(16), unique=True, nullable=False, index=True)
    player_slug = db.Column(db.String(128), index=True)
    white = db.Column(db.String(128))
    white_rating = db.Column(db.Integer)
    black = db.Column(db.String(128))
    black_rating = db.Column(db.Integer)
    result = db.Column(db.String(16))
    opening_name = db.Column(db.String(128))
    opening_slug = db.Column(db.String(128))
    first_moves = db.Column(db.String(255))
    move_count = db.Column(db.Integer)
    year = db.Column(db.Integer)
    date = db.Column(db.String(32))
    event = db.Column(db.String(128))
    san_moves = db.Column(db.JSON, default=list)
    final_fen = db.Column(db.String(128))
    colors_known = db.Column(db.Boolean, default=False)
    has_detail = db.Column(db.Boolean, default=False)


class Club(db.Model):
    __tablename__ = "clubs"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(128), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    icon = db.Column(db.String(255))
    description = db.Column(db.Text)
    members_count = db.Column(db.Integer)
    created = db.Column(db.String(32))
    last_activity = db.Column(db.String(32))
    country_code = db.Column(db.String(2))


class ClubMembership(db.Model):
    __tablename__ = "club_memberships"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False)
    joined_at = db.Column(db.String(32))
    user = db.relationship("User", backref="club_memberships")
    club = db.relationship("Club", backref="memberships")
    __table_args__ = (db.UniqueConstraint("user_id", "club_id", name="uq_club_member"),)


class ChessEvent(db.Model):
    __tablename__ = "chess_events"
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(128), unique=True, nullable=False, index=True)
    image = db.Column(db.String(255))
    start_at = db.Column(db.String(48))
    end_at = db.Column(db.String(48))
    player_count = db.Column(db.Integer)
    round_count = db.Column(db.Integer)
    description = db.Column(db.Text)
    location = db.Column(db.String(128))
    streams = db.Column(db.JSON, default=list)
    extra = db.Column(db.JSON)


class TvSlot(db.Model):
    __tablename__ = "tv_slots"
    id = db.Column(db.Integer, primary_key=True)
    start = db.Column(db.String(32))
    end = db.Column(db.String(32))
    title = db.Column(db.String(128))
    url = db.Column(db.String(64))
    color = db.Column(db.String(16))


class TodayItem(db.Model):
    __tablename__ = "today_items"
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(16), nullable=False, index=True)   # news/lesson/video/article/blog
    title = db.Column(db.String(255))
    url = db.Column(db.String(255))
    image = db.Column(db.String(255))
    author = db.Column(db.String(64))
    published = db.Column(db.String(32))
    meta = db.Column(db.JSON)


class Follow(db.Model):
    __tablename__ = "follows"
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.String(32))
    followed = db.relationship("User", backref="followers_rel", foreign_keys=[followed_id])
    __table_args__ = (db.UniqueConstraint("follower_id", "followed_id", name="uq_follow"),)


class LessonProgress(db.Model):
    __tablename__ = "lesson_progress"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("lesson_courses.id"), nullable=False)
    lessons_done = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.String(32))
    course = db.relationship("LessonCourse", backref="progress")
    __table_args__ = (db.UniqueConstraint("user_id", "course_id", name="uq_lesson_progress"),)


class Bot(db.Model):
    __tablename__ = "bots"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    slug = db.Column(db.String(64), unique=True)
    rating = db.Column(db.Integer)
    image = db.Column(db.String(255))
    description = db.Column(db.Text)
    group_name = db.Column(db.String(64))
    sort_order = db.Column(db.Integer)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ------------------------------------------------------------------ helpers

def scored_search(query, items, fields, limit=60):
    """Token-overlap scored search (multi-word queries must work)."""
    import re as _re
    tokens = [t for t in _re.split(r"\W+", query)
              if t and t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return items[:limit]
    results = []
    for item in items:
        text = " ".join(str(getattr(item, f, "") or "") for f in fields).lower()
        score = sum(1 for t in tokens if t.lower() in text)
        if score > 0:
            results.append((score, item))
    results.sort(key=lambda pair: (-pair[0], pair[1].id))
    return [item for _, item in results[:limit]]


def fmt_date(value):
    if not value:
        return ""
    return value


@app.context_processor
def inject_globals():
    return {
        "nav_types": LEADERBOARD_TYPES,
        "current_year": "2026",
    }


def _nav_state():
    return {
        "puzzle_streak": None,
    }


# expose the shared macros module to every template
app.jinja_env.globals["macros"] = app.jinja_env.get_template("_macros.html").module


# ------------------------------------------------------------------ static-ish pages

@app.route("/")
def index():
    today_news = []
    for item in TodayItem.query.filter_by(kind="news").limit(3).all():
        slug = (item.url or "").rsplit("/", 1)[-1]
        article = NewsArticle.query.filter_by(slug=slug).first()
        if article:
            today_news.append(article)
    bots = (Bot.query.order_by(Bot.sort_order, Bot.id)
            .filter(Bot.group_name != "Engine").limit(8).all())
    daily = Puzzle.query.filter_by(is_daily=True).first()
    magnus = User.query.filter_by(username="MagnusCarlsen").first()
    hikaru = User.query.filter_by(username="Hikaru").first()
    olympiad = (ChessEvent.query.filter(ChessEvent.slug.like("%olympiad%"))
                .order_by(ChessEvent.start_at.desc()).first())
    return render_template("index.html", today_news=today_news, bots=bots,
                          daily=daily, magnus=magnus, hikaru=hikaru,
                          olympiad=olympiad)


@app.route("/play")
def play():
    totals = {c: db.session.query(db.func.coalesce(db.func.sum(LeaderboardEntry.total_games), 0))
              .filter(LeaderboardEntry.category == c).scalar() for c in ("blitz", "bullet", "rapid")}
    return render_template("play.html", total_blitz_games=totals["blitz"],
                           total_bullet_games=totals["bullet"],
                           total_rapid_games=totals["rapid"])


@app.route("/play/online")
def play_online():
    return render_template("play_online.html")


@app.route("/play/computer")
def play_computer():
    bots = Bot.query.order_by(Bot.sort_order, Bot.id).all()
    groups = []
    for bot in bots:
        key = bot.group_name or "All Bots"
        if not groups or groups[-1][0] != key:
            groups.append((key, []))
        groups[-1][1].append(bot)
    return render_template("play_computer.html", groups=groups)


@app.route("/train")
def train():
    daily = Puzzle.query.filter_by(is_daily=True).first()
    return render_template("train.html", daily=daily)


@app.route("/other")
def other():
    return render_template("other.html")


# ------------------------------------------------------------------ puzzles

@app.route("/puzzles")
@app.route("/puzzles/rated")
def puzzles():
    rated = request.path.endswith("/rated")
    daily = Puzzle.query.filter_by(is_daily=True).first()
    solved_count = 0
    streak = 0
    if current_user.is_authenticated:
        solved_count = PuzzleAttempt.query.filter_by(user_id=current_user.id, solved=True).count()
        attempts = (PuzzleAttempt.query.filter_by(user_id=current_user.id, solved=True)
                    .order_by(PuzzleAttempt.id.desc()).limit(20).all())
        streak = sum(1 for a in attempts if a.solved)
    return render_template("puzzles.html", rated=rated, daily=daily,
                           solved_count=solved_count, streak=streak)


@app.route("/daily")
@app.route("/puzzles/daily")
def daily_puzzle():
    daily = Puzzle.query.filter_by(is_daily=True).first()
    if not daily:
        abort(404)
    return render_template("puzzle_daily.html", puzzle=daily)


@app.route("/puzzles/themes")
def puzzle_themes():
    themes = {}
    for p in Puzzle.query.all():
        for t in p.themes:
            themes.setdefault(t, 0)
            themes[t] += 1
    return render_template("puzzles_themes.html", themes=sorted(themes.items()))


@app.route("/puzzles/archive")
@app.route("/daily/archive")
def puzzle_archive():
    """Daily-puzzle archive: all archived daily puzzles by date, paginated."""
    page = request.args.get("page", 1, type=int)
    per = 30
    total = Puzzle.query.count()
    puzzles = (Puzzle.query.order_by(Puzzle.daily_date.desc(), Puzzle.id.desc())
               .offset((page - 1) * per).limit(per).all())
    total_pages = max(1, -(-total // per))
    return render_template("puzzle_archive.html", puzzles=puzzles, page=page,
                           total_pages=total_pages, total=total)


@app.route("/puzzles/problem/<int:puzzle_id>")
def puzzle_detail(puzzle_id):
    puzzle = db.get_or_404(Puzzle, puzzle_id)
    solved = False
    if current_user.is_authenticated:
        solved = PuzzleAttempt.query.filter_by(user_id=current_user.id,
                                               puzzle_id=puzzle.id, solved=True).first() is not None
    return render_template("puzzle_detail.html", puzzle=puzzle, solved=solved)


@app.route("/callback/puzzles/next")
def callback_puzzles_next():
    """Serve the next unsolved puzzle for the trainer (site-like JSON callback)."""
    after = request.args.get("after", type=int, default=0)
    q = Puzzle.query
    if after:
        q = q.filter(Puzzle.id > after)
    puzzle = q.order_by(Puzzle.id).first()
    if not puzzle:
        puzzle = Puzzle.query.order_by(Puzzle.id).first()
    if not puzzle:
        return jsonify({"error": "no puzzles"}), 404
    return jsonify({
        "id": puzzle.id,
        "fen": puzzle.fen,
        "themes": puzzle.themes,
        "goals": puzzle.goals,
        "rating": puzzle.rating,
        "moves": [{"from": m["from"], "to": m["to"]} for m in puzzle.uci_moves],
    })


@app.route("/callback/puzzles/solve", methods=["POST"])
@login_required
def callback_puzzles_solve():
    data = request.get_json(silent=True) or request.form
    try:
        puzzle = db.session.get(Puzzle, int(data.get("puzzle_id", 0)))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid puzzle id"}), 400
    if not puzzle:
        return jsonify({"ok": False, "error": "unknown puzzle"}), 404
    solved = bool(data.get("solved"))
    attempt = PuzzleAttempt(user_id=current_user.id, puzzle_id=puzzle.id,
                             solved=solved, used_hint=bool(data.get("hint")),
                             attempted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    db.session.add(attempt)
    db.session.commit()
    return jsonify({"ok": True, "solved_count":
                    PuzzleAttempt.query.filter_by(user_id=current_user.id, solved=True).count()})


# ------------------------------------------------------------------ lessons

@app.route("/lessons")
def lessons():
    q = LessonCourse.query
    category = request.args.get("category")
    level = request.args.get("level", type=int)
    search = request.args.get("q", "").strip()
    if category:
        q = q.filter(LessonCourse.categories.contains([category]))
    if level is not None:
        q = q.filter_by(level=level)
    courses = q.order_by(LessonCourse.id).all()
    if search:
        courses = scored_search(search, courses, ["title", "description", "author"])
    categories = sorted({c for course in LessonCourse.query.all() for c in course.categories})
    return render_template("lessons.html", courses=courses, categories=categories,
                           active_category=category, active_level=level, search=search)


@app.route("/lessons/category/<slug>")
def lessons_category(slug):
    return redirect(url_for("lessons", category=slug))


@app.route("/lessons/<slug>")
def lesson_detail(slug):
    course = LessonCourse.query.filter_by(slug=slug).first_or_404()
    progress = None
    if current_user.is_authenticated:
        progress = LessonProgress.query.filter_by(user_id=current_user.id,
                                                  course_id=course.id).first()
    related = [c for c in LessonCourse.query.filter(
        LessonCourse.categories.contains([course.categories[0] if course.categories else "strategy"])
    ).limit(5) if c.id != course.id]
    return render_template("lesson_detail.html", course=course, progress=progress,
                           related=related[:4])


@app.route("/lessons/<slug>/complete", methods=["POST"])
@login_required
def lesson_complete(slug):
    course = LessonCourse.query.filter_by(slug=slug).first_or_404()
    progress = LessonProgress.query.filter_by(user_id=current_user.id,
                                              course_id=course.id).first()
    if not progress:
        progress = LessonProgress(user_id=current_user.id, course_id=course.id,
                                   completed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        db.session.add(progress)
    progress.lessons_done = request.form.get("lessons_done", course.n_lessons, type=int)
    db.session.commit()
    flash(f"Progress saved for {course.title}.", "success")
    return redirect(url_for("lesson_detail", slug=slug))


# ------------------------------------------------------------------ openings

@app.route("/openings")
def openings():
    families = Opening.query.filter_by(is_variation=False).order_by(Opening.sort_order, Opening.name).all()
    return render_template("openings_index.html", openings=families)


INITIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/8/RNBQKBNR w KQkq - 0 1"


def _moves_to_san(moves_str):
    """'1.e4 c5' -> ['e4', 'c5'] (for board replay)."""
    import re as _re
    if not moves_str:
        return []
    return [m for m in _re.findall(r"(?:\d+\.)?\s*([KQRBNa-hO][\w+#=\-]*)", moves_str) if m]


@app.route("/openings/<slug>")
def opening_detail(slug):
    opening = Opening.query.filter_by(slug=slug).first_or_404()
    variations = Opening.query.filter_by(parent_slug=slug).order_by(Opening.name).all()
    top_players = OpeningTopPlayer.query.filter_by(opening_id=opening.id).all()
    parent = Opening.query.filter_by(slug=opening.parent_slug).first() if opening.parent_slug else None
    san_moves = _moves_to_san(opening.moves)
    popularity_series = []
    if opening.popularity:
        data = opening.popularity.get("data", opening.popularity) if isinstance(opening.popularity, dict) else {}
        items = []
        for year in sorted(data):
            try:
                items.append((int(year), float(data[year])))
            except (TypeError, ValueError):
                continue
        if items:
            top = max(v for _, v in items) or 1.0
            popularity_series = [(y, max(4, round(100 * v / top))) for y, v in items]
    return render_template("opening_detail.html", opening=opening, variations=variations,
                           top_players=top_players, parent=parent, san_moves=san_moves,
                           start_fen=INITIAL_FEN, popularity_series=popularity_series,
                           sections=opening.sections or [])


# ------------------------------------------------------------------ watch / events

@app.route("/watch")
def watch():
    events = ChessEvent.query.order_by(ChessEvent.start_at).all()
    tv = TvSlot.query.order_by(TvSlot.start).all()
    return render_template("watch.html", events=events, tv=tv)


@app.route("/events")
def events():
    events = ChessEvent.query.order_by(ChessEvent.start_at).all()
    return render_template("events_list.html", events=events)


@app.route("/events/info/<slug>")
def event_detail(slug):
    event = ChessEvent.query.filter_by(slug=slug).first_or_404()
    return render_template("event_detail.html", event=event)


# ------------------------------------------------------------------ leaderboards

def _leaderboard_page(key):
    spec = LEADERBOARD_TYPES[key]
    page = request.args.get("page", 1, type=int)
    per = 50
    total = LeaderboardEntry.query.filter_by(category=spec["key"]).count()
    entries = (LeaderboardEntry.query.filter_by(category=spec["key"])
               .order_by(LeaderboardEntry.rank)
               .offset((page - 1) * per).limit(per).all())
    stats = LeaderboardStats.query.filter_by(category=spec["key"]).first()
    distribution_bars = []
    distribution_note = ""
    if stats and stats.distribution:
        items = sorted((int(k), int(v)) for k, v in stats.distribution.items()
                       if str(k).isdigit())
        top = max((v for _, v in items), default=1) or 1
        distribution_bars = [(b, max(4, round(100 * c / top)), c) for b, c in items]
        distribution_note = "Rating bands from {} to {}".format(
            items[0][0] if items else "", items[-1][0] if items else "")
    total_pages = max(1, -(-total // per))
    return render_template("leaderboard.html", entries=entries, spec=spec,
                           key=key, page=page, total_pages=total_pages,
                           total=total, stats=stats,
                           distribution_bars=distribution_bars,
                           distribution_note=distribution_note)


@app.route("/leaderboard")
def leaderboard_root():
    return redirect(url_for("leaderboard_live"))


@app.route("/leaderboard/live")
def leaderboard_live():
    return _leaderboard_page("live")


@app.route("/leaderboard/live/bullet")
def leaderboard_bullet():
    return _leaderboard_page("live/bullet")


@app.route("/leaderboard/live/rapid")
def leaderboard_rapid():
    return _leaderboard_page("live/rapid")


@app.route("/leaderboard/tactics")
def leaderboard_tactics():
    return _leaderboard_page("tactics")


@app.route("/leaderboard/daily")
def leaderboard_daily():
    return _leaderboard_page("daily")


# ------------------------------------------------------------------ members

@app.route("/member/<username>")
def member_profile(username):
    user = User.query.filter(db.func.lower(User.username) == username.lower()).first_or_404()
    following = False
    if current_user.is_authenticated:
        following = Follow.query.filter_by(follower_id=current_user.id,
                                           followed_id=user.id).first() is not None
    lb = {e.category: e for e in LeaderboardEntry.query.filter(
        LeaderboardEntry.username == user.username).all()}
    return render_template("member_profile.html", member=user, following=following,
                           lb_entries=lb)


@app.route("/stats/live/<type_>/<username>")
def stats_page(type_, username):
    user = User.query.filter(db.func.lower(User.username) == username.lower()).first_or_404()
    key = {"blitz": "blitz", "bullet": "bullet", "rapid": "rapid"}.get(type_, type_)
    ratings = {r.category: r for r in user.ratings}
    entry = LeaderboardEntry.query.filter_by(username=user.username, category=key).first()
    return render_template("stats_page.html", member=user, type_=type_,
                            rating=ratings.get(key), entry=entry)


@app.route("/members")
def members():
    users = User.query.filter_by(is_real_member=True).order_by(User.followers.desc()).limit(100).all()
    return render_template("members.html", users=users)


@app.route("/members/titled-players")
def titled_players():
    users = User.query.filter(User.title.in_(["GM", "IM", "FM", "WGM", "WIM", "WFM", "NM", "CM"])) \
        .filter_by(is_real_member=True).order_by(User.followers.desc()).all()
    by_title = {}
    for u in users:
        by_title.setdefault(u.title, []).append(u)
    return render_template("titled_players.html", by_title=by_title)


@app.route("/follow/<username>", methods=["POST"])
@login_required
def follow(username):
    user = User.query.filter(db.func.lower(User.username) == username.lower()).first_or_404()
    if user.id == current_user.id:
        flash("You cannot follow yourself.", "error")
        return redirect(url_for("member_profile", username=username))
    rel = Follow.query.filter_by(follower_id=current_user.id, followed_id=user.id).first()
    if rel:
        db.session.delete(rel)
        flash(f"Unfollowed {user.username}.", "success")
    else:
        db.session.add(Follow(follower_id=current_user.id, followed_id=user.id,
                             created_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))
        flash(f"Following {user.username}.", "success")
    db.session.commit()
    return redirect(url_for("member_profile", username=username))


# ------------------------------------------------------------------ games database

@app.route("/games")
def games_index():
    players = MasterPlayer.query.order_by(MasterPlayer.name).all()
    recent = MasterGame.query.order_by(MasterGame.id.desc()).limit(8).all()
    search = request.args.get("q", "").strip()
    matched = None
    if search:
        matched = scored_search(search, players, ["name", "slug"])
    return render_template("games_index.html", players=players, recent=recent,
                           matched=matched, search=search)


@app.route("/games/search")
def games_search():
    return redirect(url_for("games_index", q=request.args.get("q", "")))


@app.route("/games/<slug>")
def games_player(slug):
    player = MasterPlayer.query.filter_by(slug=slug).first_or_404()
    games = MasterGame.query.filter_by(player_slug=slug).order_by(MasterGame.year.desc()).all()
    openings = sorted({(g.opening_name, g.opening_slug) for g in games if g.opening_name})
    return render_template("games_player.html", player=player, games=games,
                           openings=openings)


@app.route("/games/view/<game_id>")
def game_detail(game_id):
    game = MasterGame.query.filter_by(game_id=game_id).first_or_404()
    return render_template("game_detail.html", game=game, start_fen=INITIAL_FEN)


# ------------------------------------------------------------------ news

@app.route("/news")
def news_index():
    page = request.args.get("page", 1, type=int)
    per = 12
    total = NewsArticle.query.count()
    articles = NewsArticle.query.order_by(NewsArticle.id.desc()) \
        .offset((page - 1) * per).limit(per).all()
    featured = articles[0] if page == 1 and articles else None
    categories = ["chess-event-coverage", "chess-players", "chess-politics",
                  "editorials", "chess-com-news", "misc"]
    return render_template("news_index.html", articles=articles, featured=featured,
                           page=page, total_pages=max(1, -(-total // per)),
                           categories=categories, search=request.args.get("q", ""))


@app.route("/news/category/<slug>")
def news_category(slug):
    page = request.args.get("page", 1, type=int)
    per = 12
    articles = NewsArticle.query.filter(NewsArticle.categories.contains([slug])) \
        .order_by(NewsArticle.id.desc()).all()
    total = len(articles)
    articles = articles[(page - 1) * per: page * per]
    categories = ["chess-event-coverage", "chess-players", "chess-politics",
                  "editorials", "chess-com-news", "misc"]
    return render_template("news_index.html", articles=articles, featured=None,
                           page=page, total_pages=max(1, -(-total // per)),
                           categories=categories, category=slug)


@app.route("/news/view/<slug>")
def news_article(slug):
    article = NewsArticle.query.filter_by(slug=slug).first_or_404()
    more = NewsArticle.query.filter(NewsArticle.id != article.id) \
        .order_by(NewsArticle.id.desc()).limit(4).all()
    return render_template("news_article.html", article=article, more=more)


# ------------------------------------------------------------------ clubs

@app.route("/clubs")
def clubs():
    search = request.args.get("q", "").strip()
    all_clubs = Club.query.order_by(Club.members_count.desc()).all()
    clubs_list = scored_search(search, all_clubs, ["name", "slug", "description"]) if search else all_clubs
    my_clubs = []
    if current_user.is_authenticated:
        my_clubs = [m.club_id for m in ClubMembership.query.filter_by(user_id=current_user.id)]
    return render_template("clubs.html", clubs=clubs_list, search=search, my_clubs=my_clubs)


@app.route("/club/<slug>")
def club_detail(slug):
    club = Club.query.filter_by(slug=slug).first_or_404()
    member = False
    if current_user.is_authenticated:
        member = ClubMembership.query.filter_by(user_id=current_user.id,
                                                club_id=club.id).first() is not None
    return render_template("club_detail.html", club=club, is_member=member)


@app.route("/club/<slug>/join", methods=["POST"])
@login_required
def club_join(slug):
    club = Club.query.filter_by(slug=slug).first_or_404()
    rel = ClubMembership.query.filter_by(user_id=current_user.id, club_id=club.id).first()
    if rel:
        db.session.delete(rel)
        flash(f"You left {club.name}.", "success")
    else:
        db.session.add(ClubMembership(user_id=current_user.id, club_id=club.id,
                                      joined_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))
        flash(f"Welcome to {club.name}!", "success")
    db.session.commit()
    return redirect(url_for("club_detail", slug=slug))


# ------------------------------------------------------------------ today

@app.route("/today")
def today():
    daily = Puzzle.query.filter_by(is_daily=True).first()
    items = {k: TodayItem.query.filter_by(kind=k).all()
             for k in ("news", "lesson", "video", "article", "blog")}
    note = (f"{MIRROR_REFERENCE_DATE:%B %d, %Y} — the daily puzzle, today's news and "
            "featured learning content.")
    return render_template("today.html", daily=daily, items=items, today_note=note)


# ------------------------------------------------------------------ search

@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    results = {}
    if q:
        results["members"] = scored_search(q, User.query.filter_by(is_real_member=True).all(),
                                          ["username", "name", "title"], limit=12)
        results["articles"] = scored_search(q, NewsArticle.query.all(),
                                            ["title", "excerpt"], limit=12)
        results["openings"] = scored_search(q, Opening.query.all(),
                                            ["name", "eco", "moves"], limit=12)
        results["lessons"] = scored_search(q, LessonCourse.query.all(),
                                           ["title", "description", "author"], limit=12)
        results["clubs"] = scored_search(q, Club.query.all(), ["name", "description"], limit=12)
        results["events"] = scored_search(q, ChessEvent.query.all(), ["name"], limit=12)
        results["master_players"] = scored_search(q, MasterPlayer.query.all(),
                                                  ["name", "slug"], limit=12)
    return render_template("search.html", q=q, results=results)


# ------------------------------------------------------------------ auth

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(or_(db.func.lower(User.username) == username.lower(),
                                     db.func.lower(User.email) == username.lower())).first()
        if user and user.password_hash and user.check_password(password):
            login_user(user)
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(request.args.get("next") or url_for("index"))
        flash("Incorrect username/email or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        errors = []
        if not (3 <= len(username) <= 25) or not username.replace("_", "").replace("-", "").isalnum():
            errors.append("Username must be 3-25 characters (letters, numbers, _ or -).")
        if "@" not in email or "." not in email:
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if not errors and User.query.filter(db.func.lower(User.username) == username.lower()).first():
            errors.append("That username is taken.")
        if not errors and User.query.filter(db.func.lower(User.email) == email.lower()).first():
            errors.append("That email is already registered.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            user = User(username=username, email=email, name=request.form.get("name", "").strip(),
                        country_code=request.form.get("country", "US").upper() or None)
            user.set_password(password)
            user.joined = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f"Welcome to Chess.com, {user.username}!", "success")
            return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            current_user.name = request.form.get("name", current_user.name).strip() or current_user.name
            current_user.location = request.form.get("location", "").strip()
            current_user.country_code = (request.form.get("country_code", "") or "").upper() or None
            current_user.about = request.form.get("about", "").strip() or None
            db.session.commit()
            flash("Profile updated.", "success")
        elif action == "password":
            old = request.form.get("old_password", "")
            new = request.form.get("new_password", "")
            if not current_user.check_password(old):
                flash("Current password is incorrect.", "error")
            elif len(new) < 8:
                flash("New password must be at least 8 characters.", "error")
            else:
                current_user.set_password(new)
                db.session.commit()
                flash("Password changed.", "success")
        return redirect(url_for("settings"))
    following = Follow.query.filter_by(follower_id=current_user.id).count()
    clubs_count = ClubMembership.query.filter_by(user_id=current_user.id).count()
    lessons_done = LessonProgress.query.filter_by(user_id=current_user.id).count()
    solved_puzzles = PuzzleAttempt.query.filter_by(user_id=current_user.id, solved=True).count()
    return render_template("settings.html", following=following,
                           clubs_count=clubs_count, lessons_done=lessons_done,
                           solved_puzzles=solved_puzzles)


# ------------------------------------------------------------------ health + errors

@app.route("/_health")
def health():
    return {"ok": True, "site": "chess_com"}


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("500.html"), 500


# ------------------------------------------------------------------ bootstrap

def seed_database():
    if NewsArticle.query.count() > 0:
        return
    from seed_data import seed_from_source
    seed_from_source(db)


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    from seed_data import seed_benchmark_users as _seed
    _seed(db, bcrypt)


if not os.environ.get("WEBSYN_SKIP_BOOTSTRAP"):
    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
