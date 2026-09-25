"""Imgur mirror — Flask app.

A frozen-snapshot mirror of https://imgur.com/ (captured 2026-09-22): the
Most Viral / User Submitted feeds, gallery post pages with real upstream
imagery, tags, search, member profiles, the signed-in surfaces (votes,
favorites, follows, comments) and the upload / meme-generator flows.

All content rows come from the tracked source snapshot built by seed_data.py
(see .build-generated-seed). Heavy media ships in the pinned asset bundle
(see asset_inventory.json + .requires-images).
"""
from __future__ import annotations

import os
import re
import random as _random
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

def local_redirect(target, fallback="/"):
    """Keep user-provided return locations on this mirror."""
    target = str(target or "")
    parsed = urlsplit(target)
    if not target.startswith("/") or target.startswith("//") or "\\" in target or parsed.netloc or parsed.scheme:
        target = fallback
    return redirect(target)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# The Dockerfile and /reset wipe the instance directory; recreate it before
# SQLAlchemy opens its sqlite file (same fix as google_shopping).
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
# Tests point the app at a scratch copy of the seed; production always uses
# the instance database recreated from instance_seed/ at container boot.
DB_PATH = os.environ.get("IMGUR_DB_PATH") or f"sqlite:///{BASE_DIR}/instance/imgur.db"
app.config["SQLALCHEMY_DATABASE_URI"] = DB_PATH
app.config["SECRET_KEY"] = "webharbor-imgur-dev-key"
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

db = SQLAlchemy(app)

# The snapshot instant this mirror freezes. All "7h" / "2d" relative stamps and
# "today" behaviours are computed against this constant, never the wall clock.
MIRROR_REFERENCE_DATE = datetime(2026, 9, 22, 22, 0, 0, tzinfo=timezone.utc)

STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "it", "by", "with", "my", "me", "this", "that",
}

REPUTATION_TIERS = [
    (20_000_000, "Immortal"),
    (8_000_000, "Legendary"),
    (3_000_000, "Glorious"),
    (1_500_000, "Renowned"),
    (500_000, "Exalted"),
    (250_000, "Idolized"),
    (100_000, "Trusted"),
    (40_000, "Accepted"),
    (15_000, "Liked"),
    (5_000, "Neutral"),
    (2, "Low"),
    (-999_999_999, "Dark Lord"),
]

PLATFORM_LABELS = {
    "android": "Android",
    "ios": "iPhone",
    "web": "Web",
    "desktop": "Web",
    "mobile": "Mobile",
}

SORT_LABELS = {
    "time": "newest",
    "viral": "relevance",
    "top": "highest scoring",
    "rising": "highest scoring",
}

DATE_WINDOWS = {
    "all": "all time",
    "day": "today",
    "week": "this week",
    "month": "this month",
    "year": "this year",
}


def reputation_name(points: int) -> str:
    for threshold, name in REPUTATION_TIERS:
        if points >= threshold:
            return name
    return "Dark Lord"


def tier_points(name: str) -> int:
    for threshold, candidate in REPUTATION_TIERS:
        if candidate == name:
            return threshold
    return 0


# --------------------------------------------------------------------------
# models
# --------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(200), unique=True)
    password_hash = db.Column(db.String(300))
    avatar = db.Column(db.String(300), nullable=False)
    bio = db.Column(db.Text, default="")
    reputation = db.Column(db.Integer, default=0)
    reputation_name = db.Column(db.String(40), default="Neutral")
    created_at = db.Column(db.DateTime, nullable=False)
    is_benchmark = db.Column(db.Boolean, default=False)

    posts = db.relationship("Post", backref="author", lazy="dynamic")
    comments = db.relationship("Comment", backref="author", lazy="dynamic")

    # -- helpers ------------------------------------------------------------
    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def follow_count(self) -> int:
        return FollowUser.query.filter_by(followee_id=self.id).count()

    def is_following(self, username: str) -> bool:
        other = User.query.filter_by(username=username).first()
        if not other or other.id == self.id:
            return False
        return db.session.query(FollowUser).filter_by(
            follower_id=self.id, followee_id=other.id).first() is not None


class Post(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.String(20), primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    seo_title = db.Column(db.String(500), nullable=False, default="")
    description = db.Column(db.Text, default="")
    view_count = db.Column(db.Integer, default=0)
    upvote_count = db.Column(db.Integer, default=0)
    downvote_count = db.Column(db.Integer, default=0)
    point_count = db.Column(db.Integer, default=0)
    image_count = db.Column(db.Integer, default=1)
    comment_count = db.Column(db.Integer, default=0)
    favorite_count = db.Column(db.Integer, default=0)
    virality = db.Column(db.Float, default=0.0)
    score = db.Column(db.Float, default=0.0)
    is_album = db.Column(db.Boolean, default=False)
    in_most_viral = db.Column(db.Boolean, default=False)
    in_top_week = db.Column(db.Boolean, default=False)
    in_user_sub = db.Column(db.Boolean, default=False)
    platform = db.Column(db.String(20), default="web")
    created_at = db.Column(db.DateTime, nullable=False)

    media = db.relationship("Media", backref="post", order_by="Media.position",
                            lazy="joined")
    tags = db.relationship("Tag", secondary="post_tags", backref="posts",
                           order_by="Tag.name", lazy="joined")
    accolades = db.relationship("Accolade", backref="post", lazy="joined")

    # -- helpers ------------------------------------------------------------
    @property
    def cover(self):
        return self.media[0] if self.media else None

    @property
    def author_username(self) -> str:
        return self.author.username if self.author else ""

    def votes(self, value: int) -> int:
        return db.session.query(func.count(Vote.id)).filter_by(
            post_id=self.id, value=value).scalar() or 0

    def session_vote(self) -> int:
        user = current_user()
        if not user:
            return 0
        row = db.session.query(Vote).filter_by(
            user_id=user.id, post_id=self.id).first()
        return row.value if row else 0

    def display_points(self) -> int:
        return self.point_count + self.session_vote()

    def route_slug(self) -> str:
        if self.seo_title:
            return f"{self.seo_title}-{self.id}"
        return self.id


class Media(db.Model):
    __tablename__ = "media"
    id = db.Column(db.String(20), primary_key=True)
    post_id = db.Column(db.String(20), db.ForeignKey("posts.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    mime_type = db.Column(db.String(40), nullable=False)
    type = db.Column(db.String(10), nullable=False, default="image")
    ext = db.Column(db.String(10), nullable=False, default="jpg")
    feed_path = db.Column(db.String(300), nullable=False)
    detail_path = db.Column(db.String(300), nullable=False)
    poster_path = db.Column(db.String(300), default="")
    width = db.Column(db.Integer, default=0)
    height = db.Column(db.Integer, default=0)
    size = db.Column(db.Integer, default=0)
    is_animated = db.Column(db.Boolean, default=False)
    has_sound = db.Column(db.Boolean, default=False)
    duration = db.Column(db.Float, default=0.0)


class Tag(db.Model):
    __tablename__ = "tags"
    name = db.Column(db.String(60), primary_key=True)
    display_name = db.Column(db.String(60), nullable=False)
    followers = db.Column(db.Integer, default=0)
    total_items = db.Column(db.Integer, default=0)
    accent = db.Column(db.String(10), default="50535A")
    background_path = db.Column(db.String(300), default="")
    description = db.Column(db.Text, default="")
    is_featured = db.Column(db.Boolean, default=False)
    position = db.Column(db.Integer, default=0)


post_tags = db.Table(
    "post_tags",
    db.Column("post_id", db.String(20), db.ForeignKey("posts.id"), primary_key=True),
    db.Column("tag_name", db.String(60), db.ForeignKey("tags.name"), primary_key=True),
)


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.String(20), db.ForeignKey("posts.id"), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    text = db.Column(db.Text, nullable=False, default="")
    upvote_count = db.Column(db.Integer, default=0)
    downvote_count = db.Column(db.Integer, default=0)
    point_count = db.Column(db.Integer, default=0)
    platform = db.Column(db.String(20), default="web")
    created_at = db.Column(db.DateTime, nullable=False)

    post = db.relationship("Post", backref="all_comments")
    image_path = db.Column(db.String(300), default="")
    children = db.relationship("Comment", backref=db.backref("parent", remote_side=[id]),
                               lazy="joined")

    @property
    def is_image(self) -> bool:
        """Imgur renders comment bodies that are a bare i.imgur.com URL as the image."""
        text = (self.text or "").strip()
        return bool(re.fullmatch(r"https://i\.imgur\.com/[A-Za-z0-9]+\.(?:jpg|jpeg|png|gif|webp)", text))

    def session_vote(self) -> int:
        user = current_user()
        if not user:
            return 0
        row = db.session.query(CommentVote).filter_by(
            user_id=user.id, comment_id=self.id).first()
        return row.value if row else 0

    def display_points(self) -> int:
        return self.point_count + self.session_vote()


class Trophy(db.Model):
    __tablename__ = "trophies"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    image_path = db.Column(db.String(300), nullable=False, default="")
    awarded_at = db.Column(db.DateTime)


class Accolade(db.Model):
    __tablename__ = "accolades"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.String(20), db.ForeignKey("posts.id"), nullable=False)
    name = db.Column(db.String(60), nullable=False)
    image_path = db.Column(db.String(300), nullable=False, default="")
    count = db.Column(db.Integer, default=1)


class Vote(db.Model):
    __tablename__ = "votes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.String(20), db.ForeignKey("posts.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="uq_vote"),)


class CommentVote(db.Model):
    __tablename__ = "comment_votes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "comment_id", name="uq_comment_vote"),)


class Favorite(db.Model):
    __tablename__ = "favorites"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.String(20), db.ForeignKey("posts.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="uq_favorite"),)
    post = db.relationship("Post")


class FollowUser(db.Model):
    __tablename__ = "follow_user"
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    followee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    __table_args__ = (db.UniqueConstraint("follower_id", "followee_id", name="uq_follow"),)


class FollowTag(db.Model):
    __tablename__ = "follow_tag"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tag_name = db.Column(db.String(60), db.ForeignKey("tags.name"), nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "tag_name", name="uq_follow_tag"),)


class MemeTemplate(db.Model):
    __tablename__ = "meme_templates"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    image_path = db.Column(db.String(300), nullable=False)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db.session.get(User, uid)


def relative_time(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    delta = MIRROR_REFERENCE_DATE - moment
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return "now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 31:
        return f"{days}d"
    months = days // 30
    if months < 12:
        return f"{months}mo"
    return f"{max(1, days // 365)}y"


def format_count(value: int) -> str:
    if value >= 1000:
        if value >= 100000:
            return f"{round(value / 1000)}K"
        return f"{value / 1000:.1f}".rstrip("0").rstrip(".") + "K"
    return str(value)


def tokenize(query: str) -> list[str]:
    return [t for t in re.split(r"\W+", query.lower())
            if t and t not in STOP_WORDS]


def scored_posts(query: str, queryset=None):
    """Token-overlap scored search across title, description and tags."""
    tokens = tokenize(query)
    if not tokens:
        return []
    rows = queryset if queryset is not None else Post.query
    scored = []
    for post in rows.all():
        text = f"{post.title} {post.description}".lower()
        tag_text = " ".join(t.name for t in post.tags).lower()
        score = sum(1 for t in tokens if t in text or t in tag_text)
        if score:
            scored.append((post, score))
    scored.sort(key=lambda pair: (-pair[1], -pair[0].score, pair[0].created_at))
    return [post for post, _ in scored]


def window_start(window: str) -> datetime | None:
    """Naive UTC cutoff (DB datetimes are stored naive)."""
    base = MIRROR_REFERENCE_DATE.replace(tzinfo=None)
    if window == "day":
        return base - timedelta(days=1)
    if window == "week":
        return base - timedelta(days=7)
    if window == "month":
        return base - timedelta(days=31)
    if window == "year":
        return base - timedelta(days=365)
    return None


def feed_posts(section: str, sort: str, page: int, per_page: int = 60):
    query = Post.query.filter_by(in_most_viral=(section == "hot"))
    if section == "user_sub":
        query = Post.query.filter_by(in_user_sub=True)
    if sort == "popular":
        query = query.order_by(Post.virality.desc(), Post.created_at.desc())
    elif sort == "rising":
        query = query.order_by(Post.score.desc(), Post.created_at.desc())
    else:  # newest
        query = query.order_by(Post.created_at.desc(), Post.id)
    return query.offset((page - 1) * per_page).limit(per_page).all()


def gallery_slug(post: Post) -> str:
    return f"/gallery/{post.route_slug()}"


def format_commas(value: int) -> str:
    return f"{value:,}"


def register_template_filters() -> None:
    app.jinja_env.filters["count"] = format_count
    app.jinja_env.filters["commas"] = format_commas
    app.jinja_env.filters["ago"] = relative_time

    from flask import url_for as _url_for

    @app.template_filter("asset")
    def asset_filter(path: str) -> str:
        """Resolve a stored media path to a URL.

        Static assets (the shipped bundle) resolve through the static route;
        runtime uploads live under instance/uploads/ and are served by the
        /media/uploads route so /reset wipes them with the rest of the
        runtime state.
        """
        if path.startswith("instance/uploads/"):
            return "/media/uploads/" + path[len("instance/uploads/"):]
        if path.startswith("static/"):
            path = path[len("static/"):]
        return _url_for("static", filename=path)


# --------------------------------------------------------------------------
# routes
# --------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    user = current_user()
    featured_tags = Tag.query.filter_by(is_featured=True).order_by(Tag.position).all()
    trend_tags = Tag.query.filter_by(is_featured=False).order_by(
        Tag.position).limit(6).all()
    return {
        "session_user": user,
        "featured_tags": featured_tags,
        "trend_tags": trend_tags,
        "PLATFORM_LABELS": PLATFORM_LABELS,
        "welcome_message": "Your cat’s favorite website.",
        # template global so avatar renders can fall back for users whose stored
        # avatar path is empty (the seed's [deleted] placeholder user)
        "default_avatar_for": default_avatar_for,
    }


@app.route("/")
def index():
    section = request.args.get("section", "hot")
    if section not in ("hot", "user_sub"):
        section = "hot"
    sort = request.args.get("sort", "newest")
    if sort not in ("newest", "popular", "rising"):
        sort = "newest"
    try:
        page = max(1, int(request.args.get("page", 1) or 1))
    except ValueError:
        abort(400)
    posts = feed_posts(section, sort, page)
    return render_template("index.html", posts=posts, section=section,
                           sort=sort, page=page)


@app.route("/gallery/<path:slug>")
def gallery(slug):
    post = resolve_post(slug)
    if not post:
        abort(404)
    sort = request.args.get("sort", "best")
    if sort not in ("best", "new"):
        sort = "best"
    comments = post_comment_tree(post, sort)
    sidebar = Post.query.filter_by(in_most_viral=True).order_by(
        Post.created_at.desc()).limit(20).all()
    sidebar = [p for p in sidebar if p.id != post.id][:3]
    user = current_user()
    faved = bool(user and db.session.query(Favorite).filter_by(
        user_id=user.id, post_id=post.id).first())
    return render_template("gallery.html", post=post, comments=comments,
                           sort=sort, sidebar=sidebar, faved=faved,
                           next_post=next_in_feed(post),
                           following=bool(user and user.is_following(post.author.username)),
                           platform_label=PLATFORM_LABELS.get(post.platform, "Web"))


def next_in_feed(post: Post) -> Post | None:
    """The next post in the Most Viral ordering (wraps to the first)."""
    rows = Post.query.filter_by(in_most_viral=True).order_by(
        Post.score.desc(), Post.id).all()
    for index, row in enumerate(rows):
        if row.id == post.id:
            return rows[(index + 1) % len(rows)] if len(rows) > 1 else None
    return rows[0] if rows else None


def resolve_post(slug: str) -> Post | None:
    slug = slug.strip("/")
    post = db.session.get(Post, slug)
    if post:
        return post
    # The benchmark seed carries 4-character post ids (bmk1..bmk9, the demo
    # accounts' own posts) alongside the upstream-style 5-7 character ones, so
    # the trailing id group must accept 4 characters as well.
    match = re.match(r"^(.*)-([A-Za-z0-9]{4,8})$", slug)
    if match:
        post = db.session.get(Post, match.group(2))
        if post:
            return post
    return Post.query.filter_by(seo_title=slug).first()


def post_comment_tree(post: Post, sort: str):
    rows = Comment.query.filter_by(post_id=post.id).order_by(
        Comment.point_count.desc() if sort == "best" else Comment.created_at.desc(),
        Comment.id).all()
    children: dict[int, list] = {}
    tops = []
    for row in rows:
        if row.parent_id:
            children.setdefault(row.parent_id, []).append(row)
        else:
            tops.append(row)
    for row in rows:
        row.replies = sorted(children.get(row.id, []),
                             key=lambda r: (-r.point_count, r.id))
    return tops


@app.route("/gallery/<path:slug>/comment/<int:cid>")
def gallery_comment(slug, cid):
    post = resolve_post(slug)
    if not post:
        abort(404)
    comment = db.session.get(Comment, cid)
    if not comment or comment.post_id != post.id:
        abort(404)
    comments = post_comment_tree(post, request.args.get("sort", "best"))
    user = current_user()
    faved = bool(user and db.session.query(Favorite).filter_by(
        user_id=user.id, post_id=post.id).first())
    return render_template("gallery.html", post=post, comments=comments,
                           sort=request.args.get("sort", "best"),
                           sidebar=[], faved=faved, focus_comment=cid,
                           following=bool(user and user.is_following(post.author.username)),
                           platform_label=PLATFORM_LABELS.get(post.platform, "Web"))


@app.route("/t/<tag>")
def tag_page(tag):
    tag_row = db.session.get(Tag, tag)
    if not tag_row:
        abort(404)
    sort = request.args.get("sort", "viral")
    if sort not in ("viral", "time"):
        sort = "viral"
    query = Post.query.filter(Post.tags.any(name=tag))
    if sort == "time":
        posts = query.order_by(Post.created_at.desc()).limit(80).all()
    else:
        posts = query.order_by(Post.virality.desc(), Post.created_at.desc()).limit(80).all()
    user = current_user()
    following = bool(user and db.session.query(FollowTag).filter_by(
        user_id=user.id, tag_name=tag).first())
    return render_template("tag.html", tag=tag_row, posts=posts, sort=sort,
                           following=following)


@app.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    sort = request.args.get("sort", "viral")
    if sort not in ("time", "viral", "top"):
        sort = "viral"
    window = request.args.get("date", "all")
    if window not in DATE_WINDOWS:
        window = "all"
    results = []
    if q:
        results = scored_posts(q)
        start = window_start(window)
        if start:
            results = [p for p in results if p.created_at >= start]
        if sort == "time":
            results.sort(key=lambda p: p.created_at, reverse=True)
        elif sort == "top":
            results.sort(key=lambda p: p.point_count, reverse=True)
        else:
            pass  # scored relevance order (viral)
    tag_matches = [t for t in Tag.query.all() if q and q.lower() in t.name]
    user_matches = User.query.filter(
        User.username.ilike(f"%{q}%")).limit(12).all() if q else []
    sort_label = SORT_LABELS.get(sort, "highest scoring")
    return render_template("search.html", q=q, sort=sort, window=window,
                           results=results, tag_matches=tag_matches,
                           user_matches=user_matches, sort_label=sort_label,
                           window_label=DATE_WINDOWS[window])


@app.route("/suggest")
def suggest():
    q = (request.args.get("q") or "").strip().lower()
    tags = []
    posts = []
    users = []
    if q:
        tags = Tag.query.filter(Tag.name.ilike(f"%{q}%")).order_by(
            Tag.total_items.desc()).limit(4).all()
        posts = scored_posts(q)[:3]
        users = User.query.filter(User.username.ilike(f"%{q}%")).limit(3).all()
    return render_template("_suggest.html", q=q, tags=tags, posts=posts, users=users)


@app.route("/user/<username>")
@app.route("/user/<username>/<ignored>")
def user_page(username, ignored=None):
    user = User.query.filter(func.lower(User.username) == username.lower()).first()
    if not user:
        abort(404)
    tab = request.args.get("tab", "posts")
    if tab not in ("posts", "favorites", "comments", "about"):
        tab = "posts"
    posts = user.posts.order_by(Post.created_at.desc()).limit(60).all()
    favorites = (db.session.query(Favorite).filter_by(user_id=user.id)
                 .order_by(Favorite.created_at.desc()).limit(60).all())
    fav_posts = [f.post for f in favorites if f.post]
    comments = user.comments.order_by(Comment.created_at.desc()).limit(40).all()
    trophies = Trophy.query.filter_by(user_id=user.id).order_by(Trophy.awarded_at).all()
    viewer = current_user()
    following = bool(viewer and viewer.is_following(user.username))
    return render_template("user.html", profile=user, tab=tab, posts=posts,
                           fav_posts=fav_posts, comments=comments,
                           trophies=trophies, following=following)


@app.route("/random")
def random_post():
    row = Post.query.filter_by(in_most_viral=True).order_by(Post.virality.desc()).limit(60).all()
    if not row:
        abort(404)
    return redirect(url_for("gallery", slug=_random.choice(row).route_slug()))


# --------------------------------------------------------------------------
# auth
# --------------------------------------------------------------------------

@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        handle = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter(
            (func.lower(User.username) == handle.lower())
            | (func.lower(User.email) == handle.lower())).first() if handle else None
        if not user or not user.check_password(password):
            flash("Invalid username or password.", "error")
            return render_template("signin.html"), 401
        session["uid"] = user.id
        return local_redirect(request.args.get("next"))
    return render_template("signin.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        retype = request.form.get("retype_password") or ""
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,60}", username):
            flash("Username must be 3-60 letters, numbers, . _ or -", "error")
            return render_template("register.html"), 400
        if User.query.filter(func.lower(User.username) == username.lower()).first():
            flash("That username is taken.", "error")
            return render_template("register.html"), 400
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Enter a valid email address.", "error")
            return render_template("register.html"), 400
        if User.query.filter(func.lower(User.email) == email).first():
            flash("An account with that email already exists.", "error")
            return render_template("register.html"), 400
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html"), 400
        if password != retype:
            flash("Passwords do not match.", "error")
            return render_template("register.html"), 400
        avatar = default_avatar_for(username)
        user = User(username=username, email=email,
                    password_hash=generate_password_hash(password),
                    avatar=avatar, bio="", reputation=0,
                    reputation_name="Neutral",
                    created_at=MIRROR_REFERENCE_DATE.replace(tzinfo=None),
                    is_benchmark=False)
        db.session.add(user)
        db.session.commit()
        session["uid"] = user.id
        return redirect("/")
    return render_template("register.html")


DEFAULT_AVATARS = [
    "static/images/avatars/default_alien.png",
    "static/images/avatars/default_banana.png",
    "static/images/avatars/default_doge.png",
    "static/images/avatars/default_robot.png",
    "static/images/avatars/default_ufo.png",
    "static/images/avatars/default_yarn.png",
]


def default_avatar_for(username: str) -> str:
    idx = sum(ord(c) for c in username.lower()) % len(DEFAULT_AVATARS)
    return DEFAULT_AVATARS[idx]


def new_post_id(prefix: str) -> str:
    """Short imgur-style post id (7 chars: prefix + 6 base36 digits)."""
    import hashlib
    seed = f"{MIRROR_REFERENCE_DATE.isoformat()}{time.time_ns()}{prefix}"
    while True:
        digest = hashlib.sha256(seed.encode()).hexdigest()
        value = int(digest[:12], 16)
        alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        chars = []
        for _ in range(6):
            value, rem = divmod(value, 62)
            chars.append(alphabet[rem])
        candidate = f"{prefix}{''.join(chars)}"
        if not db.session.get(Post, candidate):
            return candidate
        seed = candidate


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("uid", None)
    return redirect("/")


# --------------------------------------------------------------------------
# signed-in state actions
# --------------------------------------------------------------------------

def require_user():
    user = current_user()
    if not user:
        abort(401)
    return user


@app.route("/vote/<post_id>", methods=["POST"])
def vote_post(post_id):
    user = current_user()
    if not user:
        return jsonify(ok=False, error="signin required"), 401
    post = db.session.get(Post, post_id)
    if not post:
        abort(404)
    value = request.form.get("value")
    if value is None:
        payload = request.get_json(silent=True) or {}
        value = payload.get("value", 0)
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 0
    if value not in (-1, 0, 1):
        value = 0
    row = db.session.query(Vote).filter_by(user_id=user.id, post_id=post.id).first()
    if row and value == row.value:
        value = 0
    if row:
        if value == 0:
            db.session.delete(row)
        else:
            row.value = value
    elif value:
        db.session.add(Vote(user_id=user.id, post_id=post.id, value=value))
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify(ok=True, value=value, points=post.display_points())
    return local_redirect(request.form.get("back"), f"/gallery/{post.route_slug()}")


@app.route("/favorite/<post_id>", methods=["POST"])
def favorite_post(post_id):
    user = current_user()
    if not user:
        return jsonify(ok=False, error="signin required"), 401
    post = db.session.get(Post, post_id)
    if not post:
        abort(404)
    row = db.session.query(Favorite).filter_by(user_id=user.id, post_id=post.id).first()
    if row:
        db.session.delete(row)
        saved = False
    else:
        db.session.add(Favorite(user_id=user.id, post_id=post.id,
                                created_at=MIRROR_REFERENCE_DATE.replace(tzinfo=None)))
        saved = True
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify(ok=True, saved=saved)
    return local_redirect(request.form.get("back"), f"/gallery/{post.route_slug()}")


@app.route("/vote/comment/<int:comment_id>", methods=["POST"])
def vote_comment(comment_id):
    user = current_user()
    if not user:
        return jsonify(ok=False, error="signin required"), 401
    comment = db.session.get(Comment, comment_id)
    if not comment:
        abort(404)
    value = int(request.form.get("value") or 0)
    if value not in (-1, 1):
        value = 0
    row = db.session.query(CommentVote).filter_by(
        user_id=user.id, comment_id=comment.id).first()
    if row and value == row.value:
        value = 0
    if row:
        if value == 0:
            db.session.delete(row)
        else:
            row.value = value
    elif value:
        db.session.add(CommentVote(user_id=user.id, comment_id=comment.id, value=value))
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify(ok=True, value=value, points=comment.display_points())
    return local_redirect(request.form.get("back"), f"/gallery/{comment.post.route_slug()}")


@app.route("/comment", methods=["POST"])
def add_comment():
    user = current_user()
    if not user:
        flash("Sign in to leave a comment.", "error")
        return redirect("/signin")
    post_id = request.form.get("post_id") or ""
    try:
        parent_id = int(request.form.get("parent_id") or 0)
    except ValueError:
        abort(400)
    text = (request.form.get("comment") or "").strip()
    post = db.session.get(Post, post_id)
    if not post:
        abort(404)
    if parent_id:
        parent = db.session.get(Comment, parent_id)
        if not parent or parent.post_id != post.id:
            abort(400)
    if not text:
        flash("Write a comment first.", "error")
        return redirect(f"/gallery/{post.route_slug()}")
    comment = Comment(post_id=post.id, parent_id=parent_id or None, author_id=user.id,
                      text=text[:2000], upvote_count=0, downvote_count=0,
                      point_count=0, platform="web",
                      created_at=MIRROR_REFERENCE_DATE.replace(tzinfo=None))
    db.session.add(comment)
    post.comment_count = (post.comment_count or 0) + 1
    db.session.commit()
    return local_redirect(request.form.get("back"), f"/gallery/{post.route_slug()}")


@app.route("/follow/user/<username>", methods=["POST"])
def follow_user(username):
    user = current_user()
    if not user:
        flash("Sign in to follow members.", "error")
        return redirect("/signin")
    target = User.query.filter(func.lower(User.username) == username.lower()).first()
    if not target or target.id == user.id:
        abort(404)
    row = db.session.query(FollowUser).filter_by(
        follower_id=user.id, followee_id=target.id).first()
    if row:
        db.session.delete(row)
        following = False
    else:
        db.session.add(FollowUser(follower_id=user.id, followee_id=target.id))
        following = True
    db.session.commit()
    return local_redirect(request.form.get("back"), f"/user/{target.username}")


@app.route("/follow/tag/<tag>", methods=["POST"])
def follow_tag(tag):
    user = current_user()
    if not user:
        flash("Sign in to follow tags.", "error")
        return redirect("/signin")
    if not db.session.get(Tag, tag):
        abort(404)
    row = db.session.query(FollowTag).filter_by(user_id=user.id, tag_name=tag).first()
    if row:
        db.session.delete(row)
        following = False
    else:
        db.session.add(FollowTag(user_id=user.id, tag_name=tag))
        following = True
    db.session.commit()
    return local_redirect(request.form.get("back"), f"/t/{tag}")


# --------------------------------------------------------------------------
# account settings
# --------------------------------------------------------------------------

@app.route("/account", methods=["GET", "POST"])
def account():
    user = current_user()
    if not user:
        return redirect("/signin")
    if request.method == "POST":
        action = request.form.get("action", "profile")
        if action == "profile":
            bio = (request.form.get("bio") or "").strip()
            user.bio = bio[:500]
        elif action == "email":
            email = (request.form.get("email") or "").strip().lower()
            if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                flash("Enter a valid email address.", "error")
                return redirect("/account")
            if email and User.query.filter(
                    func.lower(User.email) == email, User.id != user.id).first():
                flash("An account with that email already exists.", "error")
                return redirect("/account")
            user.email = email or user.email
        elif action == "password":
            old = request.form.get("current_password") or ""
            new = request.form.get("new_password") or ""
            if not user.check_password(old):
                flash("Current password is incorrect.", "error")
                return redirect("/account")
            if len(new) < 6:
                flash("New password must be at least 6 characters.", "error")
                return redirect("/account")
            user.password_hash = generate_password_hash(new)
        db.session.commit()
        flash("Saved.", "success")
        return redirect("/account")
    favorites = db.session.query(Favorite).filter_by(user_id=user.id).count()
    follows = db.session.query(FollowUser).filter_by(follower_id=user.id).count()
    return render_template("account.html", profile=user,
                           favorite_count=favorites, follow_count=follows)


# --------------------------------------------------------------------------
# upload + meme generator
# --------------------------------------------------------------------------

def save_upload_image(file_storage) -> tuple[str, int, int]:
    from PIL import Image
    import hashlib
    upload_dir = os.path.join(BASE_DIR, "instance", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    data = file_storage.read()
    digest = hashlib.sha256(data).hexdigest()[:12]
    ext = "png" if file_storage.filename.lower().endswith(".png") else "jpg"
    name = f"{digest}.{ext}"
    path = os.path.join(upload_dir, name)
    with open(path, "wb") as handle:
        handle.write(data)
    width = height = 0
    try:
        with Image.open(path) as img:
            width, height = img.size
    except Exception:
        pass
    return f"instance/uploads/{name}", width, height


@app.route("/upload", methods=["GET", "POST"])
def upload():
    user = current_user()
    if request.method == "POST":
        if not user:
            flash("Sign in to post.", "error")
            return redirect("/signin")
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        url = (request.form.get("url") or "").strip()
        file = request.files.get("image")
        path = width = height = None
        if file and file.filename:
            path, width, height = save_upload_image(file)
        elif url:
            media_id = None
            # upstream-style i.imgur.com URL: ID(_d).ext
            match = re.search(r"/([A-Za-z0-9]{5,8})(?:_d)?\.(?:jpg|jpeg|png|webp|gif)", url)
            if match:
                media_id = match.group(1)
            else:
                # a mirror-served media path: /static/images/posts/ID_(feed|detail|poster).ext
                match = re.search(r"/static/images/posts/([A-Za-z0-9]+?)(?:_(?:feed|detail|poster))?\.(?:webp|jpg|jpeg|png|gif)", url)
                if match:
                    media_id = match.group(1)
                else:
                    # a mirror upload path: /media/uploads/name.jpg
                    match = re.search(r"/media/uploads/([A-Za-z0-9_.-]+)\.(jpg|jpeg|png|webp|gif)", url)
                    if match:
                        upload = os.path.join(BASE_DIR, "instance", "uploads",
                                              f"{match.group(1)}.{match.group(2)}")
                        if os.path.exists(upload):
                            path = f"instance/uploads/{match.group(1)}.{match.group(2)}"
                            width = height = 0
                        else:
                            path = None
                        media_id = None
            if media_id:
                media = db.session.query(Media).filter(Media.id == media_id).first()
                if media is None:
                    # benchmark-native posts keep their upstream file names;
                    # resolve pasted mirror URLs by file name as well
                    stem = url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
                    media = db.session.query(Media).filter(
                        (Media.detail_path.endswith("/" + stem))
                        | (Media.feed_path.endswith("/" + stem))).first()
                if media:
                    path = media.detail_path
                    width, height = media.width, media.height
                else:
                    path = None
            elif url and not path and "media/uploads" not in url and "/static/images/" not in url:
                flash("Paste an imgur image URL.", "error")
                return redirect("/upload")
            elif url and path is None:
                flash("That image could not be found.", "error")
                return redirect("/upload")
        if not path:
            flash("Choose a photo or video, or paste an image URL.", "error")
            return redirect("/upload")
        if not title:
            flash("Add a title to publish the post.", "error")
            return redirect("/upload")
        post = Post(
            id=new_post_id("u"),
            author_id=user.id, title=title[:500],
            seo_title=re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80],
            description=description, view_count=0, upvote_count=0,
            downvote_count=0, point_count=0, image_count=1, comment_count=0,
            favorite_count=0, virality=0.0, score=0.0, is_album=False,
            in_most_viral=False, in_top_week=False, in_user_sub=True,
            platform="web", created_at=MIRROR_REFERENCE_DATE.replace(tzinfo=None))
        db.session.add(post)
        db.session.flush()
        media = Media(id=post.id, post_id=post.id, position=0,
                      mime_type="image/jpeg" if path.endswith(("jpg", "jpeg")) else "image/png",
                      type="image", ext=path.rsplit(".", 1)[-1],
                      feed_path=path, detail_path=path,
                      width=width, height=height, size=0)
        db.session.add(media)
        db.session.commit()
        return redirect(f"/gallery/{post.route_slug()}")
    return render_template("upload.html")


@app.route("/meme-generator", methods=["GET", "POST"])
def meme_generator():
    user = current_user()
    if request.method == "POST":
        if not user:
            flash("Sign in to post.", "error")
            return redirect("/signin")
        template_id = request.form.get("template")
        top_text = (request.form.get("top_text") or "").strip().upper()[:80]
        bottom_text = (request.form.get("bottom_text") or "").strip().upper()[:80]
        try:
            template = db.session.get(MemeTemplate, int(template_id)) if template_id else None
        except ValueError:
            abort(400)
        if not template:
            flash("Pick a template first.", "error")
            return redirect("/meme-generator")
        if not top_text and not bottom_text:
            flash("Add top or bottom text for the meme.", "error")
            return redirect("/meme-generator")
        from meme_compose import compose_meme
        rel_path, width, height = compose_meme(BASE_DIR, template.image_path,
                                               top_text, bottom_text)
        title = (request.form.get("title") or "").strip() or f"{template.name} meme"
        post = Post(
            id=new_post_id("m"),
            author_id=user.id, title=title[:500],
            seo_title=re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80],
            description=f"{template.name}\n{top_text}\n{bottom_text}", view_count=0, upvote_count=0, downvote_count=0,
            point_count=0, image_count=1, comment_count=0, favorite_count=0,
            virality=0.0, score=0.0, is_album=False, in_most_viral=False,
            in_top_week=False, in_user_sub=True, platform="web",
            created_at=MIRROR_REFERENCE_DATE.replace(tzinfo=None))
        db.session.add(post)
        db.session.flush()
        media = Media(id=post.id, post_id=post.id, position=0,
                      mime_type="image/jpeg", type="image", ext="jpg",
                      feed_path=rel_path, detail_path=rel_path,
                      width=width, height=height, size=0)
        db.session.add(media)
        db.session.commit()
        return redirect(f"/gallery/{post.route_slug()}")
    templates = MemeTemplate.query.order_by(MemeTemplate.id).all()
    return render_template("meme_generator.html", templates=templates)


# --------------------------------------------------------------------------
# static pages
# --------------------------------------------------------------------------

@app.route("/media/uploads/<path:name>")
def upload_media(name):
    directory = os.path.join(BASE_DIR, "instance", "uploads")
    return send_from_directory(directory, name)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/rules")
def rules():
    return render_template("rules.html")


@app.route("/tos")
def tos():
    return render_template("tos.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/arcade")
def arcade():
    return render_template("arcade.html")


@app.route("/_health")
def health():
    try:
        posts = Post.query.count()
        users = User.query.count()
        comments = Comment.query.count()
        tags = Tag.query.count()
        media = Media.query.count()
        broken = [m.id for m in Media.query.all()
                  if not os.path.exists(os.path.join(BASE_DIR, m.detail_path))]
        return {
            "ok": not broken,
            "site": "imgur",
            "posts": posts,
            "users": users,
            "comments": comments,
            "tags": tags,
            "media": media,
            "broken_media": broken[:10],
        }
    except Exception as error:  # pragma: no cover
        return {"ok": False, "site": "imgur", "error": str(error)}, 500


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


# --------------------------------------------------------------------------
# bootstrap
# --------------------------------------------------------------------------

def seed_database():
    from seed_data import seed_database as _seed
    _seed()


with app.app_context():
    db.create_all()
    seed_database()

register_template_filters()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
