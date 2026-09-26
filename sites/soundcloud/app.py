"""SoundCloud mirror — Flask app.

Mirrors soundcloud.com (chart playlists, artist profiles, track pages with
real comment threads, scored search, likes/reposts/follows, user playlists,
listening history, Go/Go+/Next Pro subscriptions, upload flow).

All runtime data lives in the SQLite seed DB (see seed_data.py + source_data/).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime
from functools import wraps

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR}/instance/soundcloud.db"
app.config["SECRET_KEY"] = "webharbor-soundcloud-dev-key"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Frozen snapshot date: the mirror state matches upstream as of this date and
# every relative "days ago" label is computed against it, so pages are stable.
MIRROR_DATE = datetime(2026, 9, 26)

STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
              "or", "is", "it", "by", "with", "my", "your", "this", "that"}

# Deterministic password hashing (no random salt) so the seed DB is
# byte-identical on every build; this is a benchmark mirror, not production.
PASSWORD_NAMESPACE = "webharbor-soundcloud"


def stable_password_hash(raw_password: str) -> str:
    digest = hashlib.sha256()
    digest.update(f"{PASSWORD_NAMESPACE}:{raw_password}".encode("utf-8"))
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class Artist(db.Model):
    __tablename__ = "artists"
    id = db.Column(db.Integer, primary_key=True)
    permalink = db.Column(db.String(200), unique=True, nullable=False, index=True)
    username = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(255), default="")
    banner = db.Column(db.String(255), default="")
    followers = db.Column(db.Integer, default=0)
    followings = db.Column(db.Integer, default=0)
    track_count = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, default="")
    city = db.Column(db.String(120), default="")
    country_code = db.Column(db.String(8), default="")
    verified = db.Column(db.Boolean, default=False)
    pro = db.Column(db.Boolean, default=False)
    pro_unlimited = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime)

    tracks = db.relationship("Track", back_populates="artist",
                             lazy="selectin", order_by="desc(Track.plays)")
    playlists = db.relationship("Playlist", back_populates="owner", lazy="selectin")


class Track(db.Model):
    __tablename__ = "tracks"
    id = db.Column(db.Integer, primary_key=True)
    permalink = db.Column(db.String(255), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id"), nullable=False, index=True)
    duration = db.Column(db.Integer, default=0)          # milliseconds
    plays = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    reposts = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)
    genre = db.Column(db.String(120), default="")
    tag_list = db.Column(db.String(500), default="")
    description = db.Column(db.Text, default="")
    artwork = db.Column(db.String(255), default="")
    waveform = db.Column(db.Text, default="[]")
    created_at = db.Column(db.DateTime)
    display_date = db.Column(db.DateTime)
    license = db.Column(db.String(80), default="all-rights-reserved")
    label_name = db.Column(db.String(255), default="")
    publisher_artist = db.Column(db.String(255), default="")
    explicit = db.Column(db.Boolean, default=False)

    artist = db.relationship("Artist", back_populates="tracks", lazy="joined")
    comments = db.relationship("Comment", back_populates="track", lazy="selectin",
                               order_by="Comment.created_at.desc()")

    @property
    def waveform_samples(self):
        try:
            return json.loads(self.waveform or "[]")
        except (ValueError, TypeError):
            return []

    @property
    def duration_label(self):
        secs = max(1, self.duration // 1000)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    @property
    def tag_names(self):
        return [t.strip('" ') for t in re.split(r'[\s]+', self.tag_list or "") if t.strip()]


class Playlist(db.Model):
    __tablename__ = "playlists"
    id = db.Column(db.Integer, primary_key=True)
    permalink = db.Column(db.String(255), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("artists.id"), nullable=False)
    description = db.Column(db.Text, default="")
    genre = db.Column(db.String(120), default="")
    tag_list = db.Column(db.String(500), default="")
    likes = db.Column(db.Integer, default=0)
    reposts = db.Column(db.Integer, default=0)
    track_count = db.Column(db.Integer, default=0)
    duration = db.Column(db.Integer, default=0)
    is_chart = db.Column(db.Boolean, default=False, index=True)
    chart_country = db.Column(db.String(4), default="")
    display_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime)
    artwork = db.Column(db.String(255), default="")

    owner = db.relationship("Artist", back_populates="playlists", lazy="joined")
    entries = db.relationship("PlaylistTrack", back_populates="playlist",
                              lazy="selectin", order_by="PlaylistTrack.position")

    @property
    def duration_label(self):
        secs = max(1, self.duration // 1000)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    @property
    def tracks(self):
        return [e.track for e in self.entries if e.track]


class PlaylistTrack(db.Model):
    __tablename__ = "playlist_tracks"
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey("playlists.id"), nullable=False, index=True)
    track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    playlist = db.relationship("Playlist", back_populates="entries")
    track = db.relationship("Track", lazy="joined")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"), nullable=False, index=True)
    author_name = db.Column(db.String(255), nullable=False)
    author_permalink = db.Column(db.String(200), default="")
    author_avatar = db.Column(db.String(255), default="")
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime)
    timestamp_ms = db.Column(db.Integer, default=0)

    track = db.relationship("Track", back_populates="comments")

    @property
    def at_label(self):
        if not self.timestamp_ms:
            return ""
        secs = self.timestamp_ms // 1000
        m, s = divmod(secs, 60)
        return f"{m}:{s:02d}"


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    display_name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(120), default="")
    bio = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime)

    likes = db.relationship("Like", back_populates="user", lazy="selectin",
                            order_by="Like.created_at.desc()")
    reposts = db.relationship("Repost", back_populates="user", lazy="selectin")
    follows = db.relationship("Follow", back_populates="user", lazy="selectin")
    playlists = db.relationship("UserPlaylist", back_populates="user", lazy="selectin")
    history = db.relationship("PlayEvent", back_populates="user", lazy="selectin",
                              order_by="PlayEvent.played_at.desc(), PlayEvent.id.desc()")

    def set_password(self, raw):
        self.password_hash = stable_password_hash(raw)

    def check_password(self, raw):
        return hmac.compare_digest(self.password_hash, stable_password_hash(raw))


class Like(db.Model):
    __tablename__ = "likes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"), nullable=False)
    created_at = db.Column(db.DateTime)
    user = db.relationship("User", back_populates="likes")
    track = db.relationship("Track", lazy="joined")


class Repost(db.Model):
    __tablename__ = "reposts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"), nullable=False)
    created_at = db.Column(db.DateTime)
    user = db.relationship("User", back_populates="reposts")
    track = db.relationship("Track", lazy="joined")


class Follow(db.Model):
    __tablename__ = "follows"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id"), nullable=False)
    created_at = db.Column(db.DateTime)
    user = db.relationship("User", back_populates="follows")
    artist = db.relationship("Artist", lazy="joined")


class UserPlaylist(db.Model):
    __tablename__ = "user_playlists"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    permalink = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    genre = db.Column(db.String(120), default="")
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime)
    user = db.relationship("User", back_populates="playlists")
    entries = db.relationship("UserPlaylistTrack", back_populates="playlist",
                              lazy="selectin", order_by="UserPlaylistTrack.position")

    @property
    def track_count(self):
        return len(self.entries)

    @property
    def tracks(self):
        return [e.track for e in self.entries if e.track]


class UserPlaylistTrack(db.Model):
    __tablename__ = "user_playlist_tracks"
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey("user_playlists.id"), nullable=False, index=True)
    track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime)
    playlist = db.relationship("UserPlaylist", back_populates="entries")
    track = db.relationship("Track", lazy="joined")


class PlayEvent(db.Model):
    __tablename__ = "play_events"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"), nullable=False)
    played_at = db.Column(db.DateTime)
    user = db.relationship("User", back_populates="history")
    track = db.relationship("Track", lazy="joined")


class Subscription(db.Model):
    __tablename__ = "subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    plan_code = db.Column(db.String(40), nullable=False)
    plan_title = db.Column(db.String(80), nullable=False)
    cycle = db.Column(db.String(20), default="monthly")
    amount = db.Column(db.Integer, default=0)             # cents
    started_at = db.Column(db.DateTime)
    renews_at = db.Column(db.DateTime)
    card_last4 = db.Column(db.String(4), default="")
    user = db.relationship("User", lazy="joined")


PLAN_CATALOG = {
    "go": {"title": "Go", "monthly": 499, "yearly": None, "trial_days": 7,
           "blurb": "Listen ad-free offline, and access 30M+ premium tracks."},
    "go-plus": {"title": "Go+", "monthly": 1199, "yearly": None, "trial_days": 30,
                "blurb": "Everything in Go, plus the full 30M+ premium catalog in high quality."},
    "next-pro": {"title": "Next Pro", "monthly": 1599, "yearly": 9900, "trial_days": None,
                 "blurb": "For artists: advanced stats, distribution to platforms, and priority support."},
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db.session.get(User, uid)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            if request.headers.get("X-Requested-With") == "fetch":
                return jsonify({"ok": False, "error": "auth"}), 401
            return redirect(url_for("signin", next_url=request.full_path.rstrip("?")))
        return f(*args, **kwargs)
    return wrapper


def time_ago(dt):
    if not dt:
        return ""
    delta = MIRROR_DATE - dt
    days = delta.days
    if days < 0:
        days = 0
    if days == 0:
        hours = delta.seconds // 3600
        if hours <= 0:
            return "just now"
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def compact(n):
    """3-significant-digit compaction matching the upstream card stats
    (969416 -> 969K, 49930 -> 49.9K, 1453008 -> 1.45M, 75225 -> 75.2K)."""
    if n is None:
        return "0"
    n = int(n)
    for div, suffix in ((1_000_000, "M"), (1_000, "K")):
        if n >= div:
            v = n / div
            if v >= 100:
                return f"{round(v, 1):.0f}{suffix}" if v % 1 == 0 or v >= 1000 else f"{v:.0f}{suffix}"
            if v >= 10:
                return f"{v:.1f}".rstrip("0").rstrip(".") + suffix
            return f"{v:.2f}".rstrip("0").rstrip(".") + suffix
    return str(n)


def money(cents):
    return f"${cents / 100:.2f}"


def scored_search(query, items, fields, limit=60):
    tokens = [t.lower() for t in re.split(r"\W+", query or "")
              if t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return items[:limit]
    scored = []
    for item in items:
        text = " ".join((getattr(item, f) or "") for f in fields).lower()
        if not text:
            continue
        score = sum(1 for t in tokens if t in text)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: -pair[0])
    return [i for _, i in scored[:limit]]


app.jinja_env.filters["time_ago"] = time_ago
app.jinja_env.filters["compact"] = compact
app.jinja_env.filters["money"] = money
app.jinja_env.globals["current_user"] = current_user
app.jinja_env.globals["MIRROR_DATE"] = MIRROR_DATE


@app.context_processor
def inject_nav_playlists():
    """The add-to-playlist modal lives in base.html so the ＋ button works on
    every page (chart rows, artist pages, library), not just track pages. The
    per-playlist track ids let the client compute the Added/disabled state for
    whichever track opened the modal."""
    user = current_user()
    pls = []
    if user:
        for up in (UserPlaylist.query.filter_by(user_id=user.id)
                   .order_by(UserPlaylist.created_at).all()):
            pls.append({"id": up.id, "title": up.title, "count": up.track_count,
                        "track_ids": sorted(e.track_id for e in up.entries)})
    return {"nav_playlists": pls}


def base_ctx(**extra):
    ctx = {
        "q": request.args.get("q", ""),
    }
    ctx.update(extra)
    return ctx


def track_ctx(track, user):
    """Per-track flags for templates."""
    liked = False
    reposted = False
    if user:
        liked = Like.query.filter_by(user_id=user.id, track_id=track.id).first() is not None
        reposted = Repost.query.filter_by(user_id=user.id, track_id=track.id).first() is not None
    return {"liked": liked, "reposted": reposted}


def artist_by_permalink(permalink):
    artist = Artist.query.filter_by(permalink=permalink).first()
    if not artist:
        abort(404)
    return artist


def track_by_permalink(artist, slug):
    track = Track.query.filter_by(artist_id=artist.id, permalink=slug).first()
    if not track:
        abort(404)
    return track


# --------------------------------------------------------------------------- #
# Landing / discover
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    user = current_user()
    if user:
        return redirect(url_for("discover"))
    hero_tracks = db.session.query(Track).order_by(Track.plays.desc()).limit(24).all()
    chart_playlists = Playlist.query.filter_by(is_chart=True).order_by(Playlist.likes.desc()).limit(10).all()
    top_artists = Artist.query.filter(Artist.followers > 0).order_by(Artist.followers.desc()).limit(12).all()
    return render_template("index.html", hero_tracks=hero_tracks,
                           chart_playlists=chart_playlists, top_artists=top_artists)


@app.route("/discover")
def discover():
    """Home: trending sections mirroring the logged-in SoundCloud home."""
    user = current_user()
    top50 = Playlist.query.filter_by(is_chart=True, chart_country="US", permalink="all-music-genres").first()
    newhot = Playlist.query.filter_by(is_chart=True, chart_country="US", permalink="new-hot").first()
    genre_charts = Playlist.query.filter(Playlist.is_chart.is_(True),
                                         Playlist.chart_country == "US",
                                         Playlist.permalink.notin_(["all-music-genres", "new-hot"])) \
                                 .order_by(Playlist.likes.desc()).all()
    curated = Playlist.query.filter_by(is_chart=False).order_by(Playlist.likes.desc()).limit(12).all()
    trending = db.session.query(Track).order_by(Track.plays.desc()).limit(24).all()
    return render_template("discover.html", top50=top50, newhot=newhot,
                           genre_charts=genre_charts, curated=curated,
                           trending=trending, user=user)


@app.route("/charts")
def charts():
    us = Playlist.query.filter_by(is_chart=True, chart_country="US").order_by(Playlist.likes.desc()).all()
    uk = Playlist.query.filter_by(is_chart=True, chart_country="UK").order_by(Playlist.likes.desc()).all()
    return render_template("charts.html", us_charts=us, uk_charts=uk)


CHART_OWNERS = {"music-charts-us": "US", "music-charts-uk": "UK"}


@app.route("/<owner_permalink>/sets/<slug>")
def playlist_page(owner_permalink, slug):
    owner = artist_by_permalink(owner_permalink)
    pl = Playlist.query.filter_by(owner_id=owner.id, permalink=slug).first()
    if not pl:
        abort(404)
    entries = pl.entries
    return render_template("playlist.html", pl=pl, entries=entries)


@app.route("/charts/<country>/<slug>")
def chart_redirect(country, slug):
    owner = f"music-charts-{country.lower()}"
    if country.upper() in CHART_OWNERS.values():
        return redirect(f"/{owner}/sets/{slug}")
    abort(404)


# --------------------------------------------------------------------------- #
# Artist + track pages
# --------------------------------------------------------------------------- #
@app.route("/<artist_permalink>/<track_slug>")
def track_page(artist_permalink, track_slug):
    artist = artist_by_permalink(artist_permalink)
    track = track_by_permalink(artist, track_slug)
    user = current_user()
    comments = Comment.query.filter_by(track_id=track.id).order_by(Comment.created_at.desc()).limit(20).all()
    more_from_artist = Track.query.filter(Track.artist_id == artist.id,
                                          Track.id != track.id) \
                                  .order_by(Track.plays.desc()).limit(6).all()
    related = db.session.query(Track).filter(Track.id != track.id)
    if track.genre:
        related = related.filter(Track.genre == track.genre)
    related = related.order_by(Track.plays.desc()).limit(8).all()
    in_playlists = (Playlist.query.join(PlaylistTrack, PlaylistTrack.playlist_id == Playlist.id)
                    .filter(PlaylistTrack.track_id == track.id)
                    .order_by(Playlist.likes.desc()).limit(4).all())
    likers_count = track.likes
    ctx = track_ctx(track, user)
    return render_template("track.html", track=track, artist=artist, comments=comments,
                           related=related, more_from_artist=more_from_artist,
                           in_playlists=in_playlists, likers_count=likers_count,
                           **ctx)


@app.route("/<artist_permalink>")
def artist_page(artist_permalink):
    artist = artist_by_permalink(artist_permalink)
    tab = request.args.get("tab", "tracks")
    tracks = Track.query.filter_by(artist_id=artist.id).order_by(Track.plays.desc()).all()
    popular = sorted(tracks, key=lambda t: -t.plays)[:5]
    playlists = Playlist.query.filter_by(owner_id=artist.id).order_by(Playlist.likes.desc()).all()
    user = current_user()
    following = False
    if user:
        following = Follow.query.filter_by(user_id=user.id, artist_id=artist.id).first() is not None
    return render_template("artist.html", artist=artist, tab=tab, tracks=tracks,
                           popular=popular, playlists=playlists, following=following)


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
@app.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    tab = request.args.get("tab", "everything")
    results = {"tracks": [], "people": [], "playlists": [], "albums": []}
    counts = {"tracks": 0, "people": 0, "playlists": 0}
    if q:
        all_tracks = db.session.query(Track).all()
        results["tracks"] = scored_search(
            q, all_tracks, ["title", "genre", "tag_list"], limit=40)
        # extend with artist-name matches
        artist_names = scored_search(q, db.session.query(Artist).all(), ["username"], limit=15)
        artist_ids = {a.id for a in artist_names}
        extra = [t for t in all_tracks if t.artist_id in artist_ids and t not in results["tracks"]]
        results["tracks"] = (results["tracks"] + extra)[:40]
        counts["tracks"] = len(scored_search(q, all_tracks, ["title", "genre", "tag_list"], limit=10000)) \
            + sum(1 for t in extra)
        results["people"] = scored_search(
            q, db.session.query(Artist).filter(Artist.followers > 0).all(),
            ["username", "city"], limit=20)
        counts["people"] = len(scored_search(
            q, db.session.query(Artist).all(), ["username", "city"], limit=10000))
        results["playlists"] = scored_search(
            q, db.session.query(Playlist).all(), ["title", "genre", "tag_list"], limit=20)
        counts["playlists"] = len(scored_search(
            q, db.session.query(Playlist).all(), ["title", "genre", "tag_list"], limit=10000))
        if counts["tracks"] > 500:
            counts["tracks"] = 500
        if counts["people"] > 500:
            counts["people"] = 500
        if counts["playlists"] > 500:
            counts["playlists"] = 500
    return render_template("search.html", q=q, tab=tab, results=results, counts=counts)


# <path:tag> so genre/tag links containing a slash (e.g. "Hip Hop/Rap" ->
# /tags/Hip-Hop/Rap, 149 tracks + tag-list entries) resolve instead of 404ing.
@app.route("/tags/<path:tag>")
def tag_page(tag):
    tag_clean = tag.replace("-", " ").strip().lower()
    exact = db.session.query(Track).filter(
        db.func.lower(Track.genre) == tag_clean).order_by(Track.plays.desc()).all()
    tagged = db.session.query(Track).filter(
        Track.tag_list.ilike(f"%{tag_clean}%")).order_by(Track.plays.desc()).limit(60).all()
    seen = {t.id for t in exact}
    recent = [t for t in tagged if t.id not in seen]
    popular = sorted(exact + recent, key=lambda t: -t.plays)[:20]
    playlists = scored_search(tag_clean, db.session.query(Playlist).all(),
                              ["title", "tag_list", "genre"], limit=8)
    return render_template("tag.html", tag=tag, tag_clean=tag_clean,
                           recent=recent[:24], popular=popular, playlists=playlists)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@app.route("/signin", methods=["GET", "POST"])
def signin():
    next_url = request.args.get("next_url") or request.form.get("next_url") or url_for("discover")
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and user.check_password(password):
            session["uid"] = user.id
            return redirect(next_url)
        flash("That email or password doesn't match an account. Try again.")
        return render_template("signin.html", next_url=next_url), 401
    return render_template("signin.html", next_url=next_url)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        display = (request.form.get("display") or "").strip()
        age = request.form.get("age")
        if not email or "@" not in email:
            flash("Please enter a valid email address.")
            return render_template("signup.html"), 400
        if len(password) < 6:
            flash("Your password must be at least 6 characters.")
            return render_template("signup.html"), 400
        if not display:
            display = email.split("@")[0]
        if User.query.filter(db.func.lower(User.email) == email).first():
            flash("That email is already registered. Sign in instead.")
            return render_template("signup.html"), 400
        base = re.sub(r"[^a-z0-9_-]", "", display.lower().replace(" ", "-")) or "user"
        permalink = base
        n = 1
        while User.query.filter_by(username=permalink).first():
            n += 1
            permalink = f"{base}-{n}"
        user = User(username=permalink, email=email, display_name=display, created_at=MIRROR_DATE)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session["uid"] = user.id
        return redirect(url_for("discover"))
    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.pop("uid", None)
    return redirect(url_for("index"))


# --------------------------------------------------------------------------- #
# Account / library
# --------------------------------------------------------------------------- #
@app.route("/you/library")
@app.route("/you/likes")
def library_likes():
    user = current_user()
    if not user:
        return redirect(url_for("signin", next_url="/you/library"))
    likes = Like.query.filter_by(user_id=user.id).order_by(Like.created_at.desc()).all()
    playlists = UserPlaylist.query.filter_by(user_id=user.id).order_by(UserPlaylist.created_at).all()
    return render_template("library.html", view="likes", likes=likes,
                           playlists=playlists, user=user)


@app.route("/you/playlists")
def library_playlists():
    user = current_user()
    if not user:
        return redirect(url_for("signin", next_url="/you/playlists"))
    playlists = UserPlaylist.query.filter_by(user_id=user.id).order_by(UserPlaylist.created_at).all()
    return render_template("library.html", view="playlists", playlists=playlists, user=user)


@app.route("/you/following")
def library_following():
    user = current_user()
    if not user:
        return redirect(url_for("signin", next_url="/you/following"))
    follows = Follow.query.filter_by(user_id=user.id).order_by(Follow.created_at.desc()).all()
    return render_template("library.html", view="following", follows=follows, user=user)


@app.route("/you/history")
def library_history():
    user = current_user()
    if not user:
        return redirect(url_for("signin", next_url="/you/history"))
    history = (PlayEvent.query.filter_by(user_id=user.id)
               .order_by(PlayEvent.played_at.desc(), PlayEvent.id.desc()).limit(60).all())
    return render_template("library.html", view="history", history=history, user=user)


@app.route("/you/playlist/<int:pl_id>")
def user_playlist_page(pl_id):
    user = current_user()
    if not user:
        return redirect(url_for("signin"))
    pl = UserPlaylist.query.filter_by(id=pl_id, user_id=user.id).first()
    if not pl:
        abort(404)
    return render_template("user_playlist.html", pl=pl, user=user)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    user = current_user()
    if not user:
        return redirect(url_for("signin", next_url="/settings"))
    if request.method == "POST":
        display = (request.form.get("display") or "").strip()
        city = (request.form.get("city") or "").strip()
        bio = (request.form.get("bio") or "").strip()
        if not display:
            flash("Display name can't be empty.")
        else:
            user.display_name = display
            user.city = city
            user.bio = bio
            db.session.commit()
            flash("Profile updated.")
            return redirect(url_for("settings"))
    return render_template("settings.html", user=user)


# --------------------------------------------------------------------------- #
# Subscriptions
# --------------------------------------------------------------------------- #
@app.route("/upgrade")
def upgrade():
    user = current_user()
    current_sub = None
    if user:
        current_sub = Subscription.query.filter_by(user_id=user.id).order_by(Subscription.started_at.desc()).first()
    return render_template("upgrade.html", plans=PLAN_CATALOG, current_sub=current_sub)


@app.route("/upgrade/subscribe", methods=["POST"])
@login_required
def subscribe():
    user = current_user()
    plan_code = request.form.get("plan")
    cycle = request.form.get("cycle", "monthly")
    card = re.sub(r"\D", "", request.form.get("card") or "")
    if plan_code not in PLAN_CATALOG:
        flash("Unknown plan.")
        return redirect(url_for("upgrade"))
    plan = PLAN_CATALOG[plan_code]
    amount = plan.get("yearly") if cycle == "yearly" and plan.get("yearly") else plan["monthly"]
    if len(card) < 12:
        flash("Enter a valid card number (at least 12 digits).")
        return redirect(url_for("upgrade"))
    existing = Subscription.query.filter_by(user_id=user.id).order_by(Subscription.started_at.desc()).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
    started = MIRROR_DATE
    if cycle == "yearly":
        renews = datetime(started.year + 1, started.month, min(started.day, 28))
    else:
        next_month = started.month + 1
        next_year = started.year
        if next_month > 12:
            next_month = 1
            next_year += 1
        renews = datetime(next_year, next_month, min(started.day, 28))
    sub = Subscription(user_id=user.id, plan_code=plan_code, plan_title=plan["title"],
                       cycle=cycle, amount=amount, started_at=started,
                       renews_at=renews, card_last4=card[-4:])
    db.session.add(sub)
    db.session.commit()
    return redirect(url_for("upgrade_done", plan=plan_code))


@app.route("/upgrade/done")
def upgrade_done():
    user = current_user()
    if not user:
        return redirect(url_for("signin"))
    sub = Subscription.query.filter_by(user_id=user.id).order_by(Subscription.started_at.desc()).first()
    if not sub:
        abort(404)
    return render_template("upgrade_done.html", sub=sub)


# --------------------------------------------------------------------------- #
# Upload (creator flow)
# --------------------------------------------------------------------------- #
@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    user = current_user()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        genre = (request.form.get("genre") or "").strip()
        description = (request.form.get("description") or "").strip()
        tags = (request.form.get("tags") or "").strip()
        minutes = request.form.get("minutes", "3")
        seconds = request.form.get("seconds", "30")
        if not title:
            flash("Give your track a title before uploading.")
            return render_template("upload.html"), 400
        try:
            minutes = max(0, min(20, int(minutes)))
            seconds = max(0, min(59, int(seconds)))
        except ValueError:
            minutes, seconds = 3, 30
        slug = re.sub(r"[^a-z0-9-]", "", title.lower().replace(" ", "-")).strip("-") or "untitled"
        n = 1
        base = slug
        while Track.query.filter_by(permalink=slug, artist_id=user.id).first():
            n += 1
            slug = f"{base}-{n}"
        # Uploaded tracks attach to a mirror-native artist profile for the user.
        artist = Artist.query.filter_by(permalink=user.username).first()
        if not artist:
            artist = Artist(permalink=user.username, username=user.display_name,
                            avatar="", banner="", followers=0, followings=0,
                            track_count=0, description=user.bio, city=user.city,
                            created_at=MIRROR_DATE)
            db.session.add(artist)
            db.session.flush()
        artist.track_count = (artist.track_count or 0) + 1
        track = Track(permalink=slug, title=title, artist_id=artist.id,
                      duration=((minutes * 60) + seconds) * 1000,
                      plays=0, likes=0, reposts=0, comment_count=0,
                      genre=genre, tag_list=tags, description=description,
                      artwork="", waveform="[]",
                      created_at=MIRROR_DATE, display_date=MIRROR_DATE)
        db.session.add(track)
        db.session.commit()
        flash("Your track is live.")
        return redirect(f"/{artist.permalink}/{slug}")
    return render_template("upload.html", user=user)


# --------------------------------------------------------------------------- #
# State-changing actions (fetch endpoints)
# --------------------------------------------------------------------------- #
def _json_ok(**data):
    return jsonify({"ok": True, **data})


@app.route("/tracks/<int:track_id>/like", methods=["POST"])
def toggle_like(track_id):
    user = current_user()
    track = db.session.get(Track, track_id)
    if not track:
        return jsonify({"ok": False}), 404
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    existing = Like.query.filter_by(user_id=user.id, track_id=track_id).first()
    if existing:
        db.session.delete(existing)
        track.likes = max(0, track.likes - 1)
        db.session.commit()
        return _json_ok(liked=False, likes=track.likes)
    db.session.add(Like(user_id=user.id, track_id=track_id, created_at=MIRROR_DATE))
    track.likes += 1
    db.session.commit()
    return _json_ok(liked=True, likes=track.likes)


@app.route("/tracks/<int:track_id>/repost", methods=["POST"])
def toggle_repost(track_id):
    user = current_user()
    track = db.session.get(Track, track_id)
    if not track:
        return jsonify({"ok": False}), 404
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    existing = Repost.query.filter_by(user_id=user.id, track_id=track_id).first()
    if existing:
        db.session.delete(existing)
        track.reposts = max(0, track.reposts - 1)
        db.session.commit()
        return _json_ok(reposted=False, reposts=track.reposts)
    db.session.add(Repost(user_id=user.id, track_id=track_id, created_at=MIRROR_DATE))
    track.reposts += 1
    db.session.commit()
    return _json_ok(reposted=True, reposts=track.reposts)


@app.route("/tracks/<int:track_id>/comment", methods=["POST"])
def post_comment(track_id):
    user = current_user()
    track = db.session.get(Track, track_id)
    if not track:
        return jsonify({"ok": False}), 404
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    payload = request.get_json(silent=True) or {}
    body = (request.form.get("body") or payload.get("body") or "").strip()
    if not body or len(body) > 1000:
        return jsonify({"ok": False, "error": "invalid"}), 400
    at_ms = 0
    raw_at = request.form.get("at") or payload.get("at")
    if raw_at:
        m = re.match(r"^(\d+):(\d{1,2})$", raw_at)
        if m:
            at_ms = (int(m.group(1)) * 60 + int(m.group(2))) * 1000
    comment = Comment(track_id=track_id, author_name=user.display_name,
                      author_permalink=user.username, author_avatar="",
                      body=body, created_at=MIRROR_DATE, timestamp_ms=at_ms)
    db.session.add(comment)
    track.comment_count += 1
    db.session.commit()
    return _json_ok(comment_id=comment.id, at_label=comment.at_label)


@app.route("/tracks/<int:track_id>/played", methods=["POST"])
def record_play(track_id):
    """Playbar signals a stream start; records history for logged-in users."""
    track = db.session.get(Track, track_id)
    if not track:
        return jsonify({"ok": False}), 404
    user = current_user()
    if user:
        db.session.add(PlayEvent(user_id=user.id, track_id=track_id, played_at=MIRROR_DATE))
        track.plays += 1
        db.session.commit()
    return _json_ok()


@app.route("/artists/<int:artist_id>/follow", methods=["POST"])
def toggle_follow(artist_id):
    user = current_user()
    artist = db.session.get(Artist, artist_id)
    if not artist:
        return jsonify({"ok": False}), 404
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    existing = Follow.query.filter_by(user_id=user.id, artist_id=artist_id).first()
    if existing:
        db.session.delete(existing)
        artist.followers = max(0, artist.followers - 1)
        db.session.commit()
        return _json_ok(following=False, followers=artist.followers)
    db.session.add(Follow(user_id=user.id, artist_id=artist_id, created_at=MIRROR_DATE))
    artist.followers += 1
    db.session.commit()
    return _json_ok(following=True, followers=artist.followers)


@app.route("/playlists/create", methods=["POST"])
def create_playlist():
    user = current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "invalid"}), 400
    slug = re.sub(r"[^a-z0-9-]", "", title.lower().replace(" ", "-")).strip("-") or "playlist"
    n = 1
    base = slug
    while UserPlaylist.query.filter_by(user_id=user.id, permalink=slug).first():
        n += 1
        slug = f"{base}-{n}"
    pl = UserPlaylist(user_id=user.id, permalink=slug, title=title,
                      created_at=MIRROR_DATE)
    db.session.add(pl)
    db.session.commit()
    add_track = data.get("track_id")
    if add_track:
        t = db.session.get(Track, int(add_track))
        if t:
            db.session.add(UserPlaylistTrack(playlist_id=pl.id, track_id=t.id,
                                              position=1, added_at=MIRROR_DATE))
            db.session.commit()
    return _json_ok(playlist_id=pl.id, permalink=slug, title=title)


@app.route("/playlists/<int:playlist_id>/add", methods=["POST"])
def add_to_playlist(playlist_id):
    user = current_user()
    pl = UserPlaylist.query.filter_by(id=playlist_id, user_id=user.id if user else -1).first()
    if not pl:
        return jsonify({"ok": False, "error": "auth"}), 404
    data = request.get_json(silent=True) or {}
    try:
        track_id = int(data.get("track_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid"}), 400
    track = db.session.get(Track, track_id)
    if not track:
        return jsonify({"ok": False}), 404
    if any(e.track_id == track_id for e in pl.entries):
        return _json_ok(already=True, count=pl.track_count)
    pos = len(pl.entries) + 1
    db.session.add(UserPlaylistTrack(playlist_id=pl.id, track_id=track_id,
                                     position=pos, added_at=MIRROR_DATE))
    db.session.commit()
    return _json_ok(count=pl.track_count)


@app.route("/playlists/<int:playlist_id>/remove", methods=["POST"])
def remove_from_playlist(playlist_id):
    user = current_user()
    pl = UserPlaylist.query.filter_by(id=playlist_id, user_id=user.id if user else -1).first()
    if not pl:
        return jsonify({"ok": False, "error": "auth"}), 404
    data = request.get_json(silent=True) or {}
    try:
        track_id = int(data.get("track_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid"}), 400
    entry = UserPlaylistTrack.query.filter_by(playlist_id=pl.id, track_id=track_id).first()
    if entry:
        db.session.delete(entry)
        rest = UserPlaylistTrack.query.filter_by(playlist_id=pl.id) \
            .order_by(UserPlaylistTrack.position).all()
        for i, e in enumerate(rest, 1):
            e.position = i
        db.session.commit()
    return _json_ok(count=pl.track_count)


# --------------------------------------------------------------------------- #
# Health + errors
# --------------------------------------------------------------------------- #
@app.route("/_health")
def health():
    return {
        "ok": True,
        "site": "soundcloud",
        "tracks": Track.query.count(),
        "artists": Artist.query.count(),
        "playlists": Playlist.query.count(),
        "comments": Comment.query.count(),
        "users": User.query.count(),
    }


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template("500.html"), 500


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
def create_schema() -> None:
    """Create tables + indexes deterministically (index creation order would
    otherwise vary between builds and break seed byte-identity)."""
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
            from seed_data import seed_benchmark_users, seed_database
            seed_database()
            seed_benchmark_users()
        except ImportError:
            pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 40131))
    app.run(host="0.0.0.0", port=port, debug=False)
