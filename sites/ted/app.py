"""TED mirror for WebHarbor."""
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from seed_data import EVENTS, PLAYLISTS, TALKS

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "ted.db"
SEED_DB_PATH = BASE_DIR / "instance_seed" / "ted.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "webharbor-ted-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
BASE_DIR.joinpath("instance").mkdir(exist_ok=True)

db = SQLAlchemy(app)


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


class SavedTalk(db.Model):
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
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False)
    status = db.Column(db.String(40), default="waitlisted")
    event = db.relationship("Event")


STOP_WORDS = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "by", "my", "is"}


def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def require_login():
    if not current_user():
        flash("Please sign in to continue.", "info")
        return redirect(url_for("login", next=request.path))
    return None


@app.context_processor
def inject_globals():
    topics = sorted({topic for talk in Talk.query.all() for topic in talk.topics})
    return {"current_user": current_user(), "nav_topics": topics[:10]}


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
        text = " ".join([talk.title, talk.speaker, talk.event, talk.description, talk.transcript, " ".join(talk.topics)]).lower()
        score = sum(1 for token in tokens if token in text)
        if score:
            ranked.append((score, talk.views, talk))
    return [talk for _, _, talk in sorted(ranked, key=lambda item: (-item[0], -item[1]))]


def seed_database():
    if Talk.query.count() > 0:
        return
    talks_by_topic = {}
    for row in TALKS:
        talk = Talk(
            source_id=row["source_id"],
            slug=row["slug"],
            title=row["title"],
            speaker=row["speaker"],
            event=row["event"],
            talk_type=row["talk_type"],
            duration_seconds=row["duration_seconds"],
            published_at=row["published_at"],
            recorded_on=row["recorded_on"],
            views=row["views"],
            image=row["image"],
            canonical_url=row["canonical_url"],
            description=row["description"],
            transcript=row["transcript"],
            topics_json=json.dumps(row["topics"]),
            recommended_json=json.dumps(row["recommended_for"]),
        )
        db.session.add(talk)
        db.session.flush()
        for topic in row["topics"]:
            talks_by_topic.setdefault(topic.lower(), []).append(talk.id)

    for row in PLAYLISTS:
        playlist = Playlist(**row)
        db.session.add(playlist)
        db.session.flush()
        topic_terms = [term.strip().lower() for term in row["topic"].split("|") if term.strip()]
        ids = []
        for term in topic_terms:
            for talk_id in talks_by_topic.get(term, []):
                if talk_id not in ids:
                    ids.append(talk_id)
        ids = ids[:8]
        if len(ids) < 4:
            ids = [talk.id for talk in Talk.query.order_by(Talk.views.desc()).limit(8)]
        for position, talk_id in enumerate(ids, start=1):
            db.session.add(PlaylistTalk(playlist_id=playlist.id, talk_id=talk_id, position=position))

    for row in EVENTS:
        db.session.add(Event(**row))
    db.session.commit()


def seed_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    users = [
        ("alice_j", "alice.j@test.com", "Alice Johnson", "Product manager", "Seattle", "AI"),
        ("bob_c", "bob.c@test.com", "Bob Chen", "Graduate student", "Boston", "science"),
        ("carol_d", "carol.d@test.com", "Carol Davis", "Workshop facilitator", "Austin", "design"),
        ("david_k", "david.k@test.com", "David Kim", "Climate researcher", "San Francisco", "climate change"),
    ]
    talks = Talk.query.order_by(Talk.views.desc()).limit(12).all()
    events = Event.query.all()
    for index, (username, email, name, role, city, topic) in enumerate(users):
        user = User(
            username=username,
            email=email,
            display_name=name,
            role=role,
            city=city,
            newsletter_topic=topic.lower(),
            password_hash=generate_password_hash("TestPass123!"),
        )
        db.session.add(user)
        db.session.flush()
        for talk in talks[index:index + 4]:
            db.session.add(SavedTalk(user_id=user.id, talk_id=talk.id, note=f"Review for {topic} discussion"))
        db.session.add(Registration(user_id=user.id, event_id=events[index % len(events)].id, status="confirmed"))
    db.session.commit()


@app.route("/")
def index():
    featured = Talk.query.order_by(Talk.published_at.desc()).limit(5).all()
    popular = Talk.query.order_by(Talk.views.desc()).limit(8).all()
    playlists = Playlist.query.all()
    return render_template("index.html", featured=featured, popular=popular, playlists=playlists)


@app.route("/talks")
def talks():
    topic = request.args.get("topic", "").lower()
    event = request.args.get("event", "")
    max_minutes = request.args.get("max_minutes", type=int)
    query = Talk.query
    if event:
        query = query.filter(Talk.event == event)
    items = query.order_by(Talk.published_at.desc()).all()
    if topic:
        items = [talk for talk in items if topic in talk.topics]
    if max_minutes:
        items = [talk for talk in items if talk.minutes <= max_minutes]
    events = [row[0] for row in db.session.query(Talk.event).distinct().order_by(Talk.event).all()]
    return render_template("talks.html", talks=items, topic=topic, event=event, max_minutes=max_minutes, events=events)


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
    talks = [talk for talk in Talk.query.order_by(Talk.views.desc()).all() if topic.lower() in talk.topics]
    return render_template("talks.html", talks=talks, topic=topic.lower(), event="", max_minutes=None, events=[])


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
        login_redirect = require_login()
        if login_redirect:
            return login_redirect
        event = Event.query.filter_by(slug=request.form.get("event_slug")).first_or_404()
        user = current_user()
        existing = Registration.query.filter_by(user_id=user.id, event_id=event.id).first()
        if not existing:
            db.session.add(Registration(user_id=user.id, event_id=event.id, status="waitlisted"))
            db.session.commit()
        flash(f"Registration saved for {event.name}.", "success")
        return redirect(url_for("account"))
    return render_template("events.html", events=Event.query.order_by(Event.month.desc()).all())


@app.route("/save/<slug>", methods=["POST"])
def save_talk(slug):
    login_redirect = require_login()
    if login_redirect:
        return login_redirect
    talk = Talk.query.filter_by(slug=slug).first_or_404()
    user = current_user()
    if not SavedTalk.query.filter_by(user_id=user.id, talk_id=talk.id).first():
        db.session.add(SavedTalk(user_id=user.id, talk_id=talk.id, note=request.form.get("note", "")))
        db.session.commit()
        flash("Talk saved.", "success")
    return redirect(request.referrer or url_for("talk_detail", slug=slug))


@app.route("/unsave/<int:saved_id>", methods=["POST"])
def unsave_talk(saved_id):
    login_redirect = require_login()
    if login_redirect:
        return login_redirect
    saved = SavedTalk.query.get_or_404(saved_id)
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
        user.display_name = request.form.get("display_name", user.display_name).strip() or user.display_name
        user.role = request.form.get("role", user.role).strip() or user.role
        user.city = request.form.get("city", user.city).strip()
        user.newsletter_topic = request.form.get("newsletter_topic", user.newsletter_topic).strip().lower()
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account"))
    saved = SavedTalk.query.filter_by(user_id=user.id).order_by(SavedTalk.saved_at.desc()).all()
    registrations = Registration.query.filter_by(user_id=user.id).all()
    return render_template("account.html", user=user, saved=saved, registrations=registrations)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, request.form.get("password", "")):
            session["user_id"] = user.id
            flash("Signed in.", "success")
            return redirect(request.args.get("next") or url_for("account"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        username = re.sub(r"[^a-z0-9_]+", "", request.form.get("username", "").lower())[:40]
        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash("That email or username already exists.", "error")
        else:
            user = User(
                email=email,
                username=username,
                display_name=request.form.get("display_name", username).strip() or username,
                password_hash=generate_password_hash(request.form.get("password", "TestPass123!")),
            )
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            flash("Account created.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("index"))


@app.route("/_health")
def health():
    return {"ok": True, "site": "ted", "talks": Talk.query.count()}


with app.app_context():
    db.create_all()
    seed_database()
    seed_users()
    if not SEED_DB_PATH.exists() and DB_PATH.exists():
        SEED_DB_PATH.parent.mkdir(exist_ok=True)
        shutil.copy2(DB_PATH, SEED_DB_PATH)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
