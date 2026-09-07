"""TED mirror for WebHarbor."""
import json
import os
import re
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "ted.db"
SEED_DB_PATH = BASE_DIR / "instance_seed" / "ted.db"
SITE_PORT = 40019

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("TED_SECRET_KEY") or secrets.token_hex(32)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
BASE_DIR.joinpath("instance").mkdir(exist_ok=True)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)


@sqlalchemy_event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, _record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(120), default="Curious learner")
    city = db.Column(db.String(120), default="")
    newsletter_topic = db.Column(db.String(80), default="technology")


class Talk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.String(40), unique=True, nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    title = db.Column(db.String(260), nullable=False)
    speaker = db.Column(db.String(180), nullable=False)
    event = db.Column(db.String(120), default="")
    talk_type = db.Column(db.String(80), default="TED Talk")
    duration_seconds = db.Column(db.Integer, default=0)
    published_at = db.Column(db.String(20), default="")
    recorded_on = db.Column(db.String(20), default="")
    views = db.Column(db.Integer, default=0)
    image = db.Column(db.String(260), default="")
    canonical_url = db.Column(db.String(300), default="")
    description = db.Column(db.Text, default="")
    transcript = db.Column(db.Text, default="")
    topics_json = db.Column(db.Text, default="[]")
    recommended_json = db.Column(db.Text, default="[]")

    @property
    def topics(self):
        return json.loads(self.topics_json or "[]")

    @property
    def recommended_for(self):
        return json.loads(self.recommended_json or "[]")

    @property
    def minutes(self):
        return max(1, round((self.duration_seconds or 0) / 60))

    @property
    def views_label(self):
        if self.views >= 1_000_000:
            return f"{self.views / 1_000_000:.1f}M"
        if self.views >= 1000:
            return f"{self.views // 1000}K"
        return str(self.views)

    @property
    def exact_views_label(self):
        return f"{self.views:,}"


class SavedTalk(db.Model):
    __table_args__ = (db.UniqueConstraint("user_id", "talk_id", name="uq_saved_talk_user_talk"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    talk_id = db.Column(db.Integer, db.ForeignKey("talk.id"), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.String(240), default="")
    talk = db.relationship("Talk")


class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, default="")
    topic = db.Column(db.String(80), default="")


class PlaylistTalk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey("playlist.id"), nullable=False)
    talk_id = db.Column(db.Integer, db.ForeignKey("talk.id"), nullable=False)
    position = db.Column(db.Integer, default=0)
    talk = db.relationship("Talk")


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(180), nullable=False)
    city = db.Column(db.String(120), default="")
    month = db.Column(db.String(40), default="")
    track = db.Column(db.String(80), default="")
    capacity = db.Column(db.Integer, default=0)


class Registration(db.Model):
    __table_args__ = (db.UniqueConstraint("user_id", "event_id", name="uq_registration_user_event"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False)
    status = db.Column(db.String(40), default="waitlisted")
    event = db.relationship("Event")


STOP_WORDS = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "by", "my", "is"}
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def safe_next(target, fallback):
    if not target or "\\" in target:
        return fallback
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return fallback
    return target


def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def require_login(next_url=None):
    if not current_user():
        flash("Please sign in to continue.", "info")
        return redirect(url_for("login", next=next_url or request.path))
    return None


@app.context_processor
def inject_globals():
    return {"current_user": current_user()}


@app.template_filter("date_label")
def date_label(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%b %d, %Y")
    except Exception:
        return value


def tokenize(text):
    return [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) > 1 and t not in STOP_WORDS]


def scored_talks(query, talks):
    tokens = tokenize(query)
    if not tokens:
        return list(talks)
    ranked = []
    for talk in talks:
        text = " ".join([talk.title, talk.speaker, talk.event, talk.description, talk.transcript, " ".join(talk.topics)])
        text_tokens = set(tokenize(text))
        score = sum(
            1
            for token in tokens
            if any(
                token == candidate
                or (len(token) >= 4 and candidate.startswith(token))
                or (len(candidate) >= 4 and token.startswith(candidate))
                for candidate in text_tokens
            )
        )
        if score:
            ranked.append((score, talk.views, talk))
    return [talk for _, _, talk in sorted(ranked, key=lambda item: (-item[0], -item[1]))]


def available_topics():
    return sorted({topic for talk in Talk.query.all() for topic in talk.topics}, key=str.casefold)


def filtered_talks(topic="", event="", max_minutes=None):
    query = Talk.query
    if event:
        query = query.filter(Talk.event == event)
    if max_minutes is not None:
        query = query.filter(Talk.duration_seconds <= max_minutes * 60)
    items = query.order_by(Talk.published_at.desc(), Talk.id.asc()).all()
    if topic:
        items = [talk for talk in items if topic.casefold() in {value.casefold() for value in talk.topics}]
    return items


@app.route("/")
def index():
    featured = Talk.query.order_by(Talk.published_at.desc()).limit(5).all()
    popular = Talk.query.order_by(Talk.views.desc()).limit(8).all()
    playlists = Playlist.query.all()
    return render_template("index.html", featured=featured, popular=popular, playlists=playlists)


@app.route("/talks")
def talks():
    topic = request.args.get("topic", "").strip().lower()
    event = request.args.get("event", "").strip()
    raw_max_minutes = request.args.get("max_minutes", "").strip()
    max_minutes = None
    if raw_max_minutes:
        try:
            max_minutes = int(raw_max_minutes)
        except ValueError:
            max_minutes = None
        if max_minutes is not None and not 1 <= max_minutes <= 180:
            max_minutes = None
    items = filtered_talks(topic, event, max_minutes)
    events = [row[0] for row in db.session.query(Talk.event).distinct().order_by(Talk.event).all()]
    return render_template(
        "talks.html",
        talks=items,
        topic=topic,
        event=event,
        max_minutes=max_minutes,
        events=events,
        topics=available_topics(),
    )


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    talks = scored_talks(q, Talk.query.all()) if q else []
    return render_template("search.html", q=q, talks=talks)


@app.route("/talks/<slug>")
def talk_detail(slug):
    talk = Talk.query.filter_by(slug=slug).first_or_404()
    related = [item for item in scored_talks(" ".join(talk.topics[:2]), Talk.query.all()) if item.id != talk.id][:4]
    saved = False
    user = current_user()
    if user:
        saved = SavedTalk.query.filter_by(user_id=user.id, talk_id=talk.id).first() is not None
    return render_template("talk_detail.html", talk=talk, related=related, saved=saved)


@app.route("/topics")
def topics():
    counts = {}
    for talk in Talk.query.all():
        for topic in talk.topics:
            counts[topic] = counts.get(topic, 0) + 1
    return render_template("topics.html", counts=sorted(counts.items(), key=lambda item: (-item[1], item[0])))


@app.route("/topics/<topic>")
def topic_detail(topic):
    return redirect(url_for("talks", topic=topic.lower()))


@app.route("/playlists")
def playlists():
    items = Playlist.query.order_by(Playlist.title).all()
    return render_template("playlists.html", playlists=items)


@app.route("/playlists/<slug>")
def playlist_detail(slug):
    playlist = Playlist.query.filter_by(slug=slug).first_or_404()
    links = PlaylistTalk.query.filter_by(playlist_id=playlist.id).order_by(PlaylistTalk.position).all()
    return render_template("playlist_detail.html", playlist=playlist, links=links)


@app.route("/events", methods=["GET", "POST"])
def events():
    if request.method == "POST":
        login_redirect = require_login(url_for("events"))
        if login_redirect:
            return login_redirect
        event_slug = request.form.get("event_slug", "").strip()
        event = Event.query.filter_by(slug=event_slug).first_or_404()
        user = current_user()
        existing = Registration.query.filter_by(user_id=user.id, event_id=event.id).first()
        if not existing:
            db.session.add(Registration(user_id=user.id, event_id=event.id, status="waitlisted"))
            try:
                db.session.commit()
                flash(f"Registration saved for {event.name}.", "success")
            except IntegrityError:
                db.session.rollback()
                flash(f"You are already registered for {event.name}.", "info")
        else:
            flash(f"You are already registered for {event.name}.", "info")
        return redirect(url_for("account"))
    event_items = Event.query.all()
    event_items.sort(key=lambda item: datetime.strptime(item.month, "%B %Y"), reverse=True)
    return render_template("events.html", events=event_items)


@app.route("/save/<slug>", methods=["POST"])
def save_talk(slug):
    login_redirect = require_login(url_for("talk_detail", slug=slug))
    if login_redirect:
        return login_redirect
    talk = Talk.query.filter_by(slug=slug).first_or_404()
    user = current_user()
    existing = SavedTalk.query.filter_by(user_id=user.id, talk_id=talk.id).first()
    if not existing:
        note = request.form.get("note", "").strip()[:240]
        db.session.add(SavedTalk(user_id=user.id, talk_id=talk.id, note=note))
        try:
            db.session.commit()
            flash("Talk saved.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("This talk is already saved.", "info")
    else:
        flash("This talk is already saved.", "info")
    return redirect(safe_next(request.form.get("next"), url_for("talk_detail", slug=slug)))


@app.route("/unsave/<int:saved_id>", methods=["POST"])
def unsave_talk(saved_id):
    login_redirect = require_login(url_for("account"))
    if login_redirect:
        return login_redirect
    saved = db.get_or_404(SavedTalk, saved_id)
    if saved.user_id != current_user().id:
        abort(403)
    db.session.delete(saved)
    db.session.commit()
    flash("Saved talk removed.", "success")
    return redirect(url_for("account"))


@app.route("/account", methods=["GET", "POST"])
def account():
    login_redirect = require_login()
    if login_redirect:
        return login_redirect
    user = current_user()
    if request.method == "POST":
        user.display_name = (request.form.get("display_name", user.display_name).strip() or user.display_name)[:120]
        user.role = (request.form.get("role", user.role).strip() or user.role)[:120]
        user.city = request.form.get("city", user.city).strip()[:120]
        user.newsletter_topic = (request.form.get("newsletter_topic", user.newsletter_topic).strip().lower() or user.newsletter_topic)[:80]
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account"))
    saved = SavedTalk.query.filter_by(user_id=user.id).order_by(SavedTalk.saved_at.desc()).all()
    registrations = Registration.query.filter_by(user_id=user.id).all()
    return render_template("account.html", user=user, saved=saved, registrations=registrations)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()[:160]
        password = request.form.get("password", "")[:256]
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session["user_id"] = user.id
            flash("Signed in.", "success")
            return redirect(safe_next(request.args.get("next"), url_for("account")))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()[:160]
        username = re.sub(r"[^a-z0-9_]+", "", request.form.get("username", "").lower())[:40]
        display_name = request.form.get("display_name", "").strip()[:120]
        password = request.form.get("password", "")[:256]
        errors = []
        if not username:
            errors.append("Enter a username containing letters, numbers, or underscores.")
        if not EMAIL_PATTERN.fullmatch(email):
            errors.append("Enter a valid email address.")
        if not display_name:
            errors.append("Enter your name.")
        if len(password) < 8:
            errors.append("Password must contain at least 8 characters.")
        if email and username and User.query.filter((User.email == email) | (User.username == username)).first():
            errors.append("Unable to create an account with the supplied details.")
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("register.html"), 400
        user = User(
            email=email,
            username=username,
            display_name=display_name,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        session.clear()
        session["user_id"] = user.id
        flash("Account created.", "success")
        return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("index"))


@app.route("/_health")
def health():
    return {"ok": True, "site": "ted", "talks": Talk.query.count()}


def initialize_database():
    if not SEED_DB_PATH.exists():
        raise RuntimeError(
            f"Missing TED seed database at {SEED_DB_PATH}. Run scripts/fetch_assets.sh ted before starting the site."
        )
    if not DB_PATH.exists():
        DB_PATH.parent.mkdir(exist_ok=True)
        shutil.copy2(SEED_DB_PATH, DB_PATH)


with app.app_context():
    initialize_database()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", SITE_PORT))
    app.run(host="0.0.0.0", port=port, debug=False)
