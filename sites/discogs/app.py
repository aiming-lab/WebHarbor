"""Discogs mirror — Flask app for WebHarbor.

Models the catalogue (Release/Master/Artist/Label/Genre/Style/Format/Track),
community (User/Rating/Review/Collection/Wantlist/List), marketplace listings,
and forum threads. Data ships in instance_seed/discogs.db and is seeded from
scraped_data/releases.json via seed_data.py.
"""
import os
import re
import math
import json
import random
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort, g, make_response, send_from_directory)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_bcrypt import Bcrypt
from sqlalchemy import or_, and_, func, desc, asc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__, instance_path=INSTANCE_DIR)
app.config["SECRET_KEY"] = "discogs-webharbor-dev-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(INSTANCE_DIR, 'discogs.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."


# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────

release_genres = db.Table(
    "release_genres",
    db.Column("release_id", db.Integer, db.ForeignKey("releases.id"), primary_key=True),
    db.Column("genre_id", db.Integer, db.ForeignKey("genres.id"), primary_key=True),
)

release_styles = db.Table(
    "release_styles",
    db.Column("release_id", db.Integer, db.ForeignKey("releases.id"), primary_key=True),
    db.Column("style_id", db.Integer, db.ForeignKey("styles.id"), primary_key=True),
)

release_labels = db.Table(
    "release_labels",
    db.Column("release_id", db.Integer, db.ForeignKey("releases.id"), primary_key=True),
    db.Column("label_id", db.Integer, db.ForeignKey("labels.id"), primary_key=True),
    db.Column("catno", db.String(80), default=""),
)

release_formats = db.Table(
    "release_formats",
    db.Column("release_id", db.Integer, db.ForeignKey("releases.id"), primary_key=True),
    db.Column("format_id", db.Integer, db.ForeignKey("formats.id"), primary_key=True),
)


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False, index=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(100), default="")
    real_name = db.Column(db.String(120), default="")
    bio = db.Column(db.Text, default="")
    avatar_seed = db.Column(db.String(16), default="")
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_seller = db.Column(db.Boolean, default=False)
    seller_rating = db.Column(db.Float, default=0.0)
    seller_feedback_count = db.Column(db.Integer, default=0)

    collection_items = db.relationship("CollectionItem", backref="user", lazy="dynamic",
                                       cascade="all, delete-orphan")
    wantlist_items = db.relationship("WantlistItem", backref="user", lazy="dynamic",
                                      cascade="all, delete-orphan")
    ratings = db.relationship("Rating", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    reviews = db.relationship("Review", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    lists = db.relationship("List", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    posts = db.relationship("Post", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    threads = db.relationship("Thread", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    listings = db.relationship("Listing", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def collection_count(self):
        return self.collection_items.count()

    @property
    def wantlist_count(self):
        return self.wantlist_items.count()

    @property
    def avatar_color(self):
        s = self.avatar_seed or self.username
        h = sum(ord(c) * 31 for c in s) % 360
        return f"hsl({h}, 55%, 45%)"


class Artist(db.Model):
    __tablename__ = "artists"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    real_name = db.Column(db.String(200), default="")
    profile = db.Column(db.Text, default="")
    members = db.Column(db.Text, default="")
    sites = db.Column(db.Text, default="")
    image_path = db.Column(db.String(200), default="")
    rating = db.Column(db.Float, default=0.0)
    in_collection = db.Column(db.Integer, default=0)

    releases = db.relationship("Release", backref="artist", lazy="dynamic")


class Label(db.Model):
    __tablename__ = "labels"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    profile = db.Column(db.Text, default="")
    contact_info = db.Column(db.Text, default="")
    parent_label_id = db.Column(db.Integer, db.ForeignKey("labels.id"))
    parent_label = db.relationship("Label", remote_side=[id])


class Genre(db.Model):
    __tablename__ = "genres"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)


class Style(db.Model):
    __tablename__ = "styles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)


class Format(db.Model):
    __tablename__ = "formats"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    slug = db.Column(db.String(40), unique=True, nullable=False)


class Master(db.Model):
    __tablename__ = "masters"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id"), nullable=False, index=True)
    year = db.Column(db.Integer)
    main_release_id = db.Column(db.Integer, db.ForeignKey("releases.id"))
    artist = db.relationship("Artist", backref="masters")


class Release(db.Model):
    __tablename__ = "releases"
    id = db.Column(db.Integer, primary_key=True)
    discogs_id = db.Column(db.Integer, unique=True, index=True)
    title = db.Column(db.String(300), nullable=False, index=True)
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id"), nullable=False, index=True)
    master_id = db.Column(db.Integer, db.ForeignKey("masters.id"))
    year = db.Column(db.Integer, index=True)
    released = db.Column(db.String(40), default="")
    country = db.Column(db.String(80), default="")
    notes = db.Column(db.Text, default="")
    barcode = db.Column(db.String(80), default="")
    catno = db.Column(db.String(80), default="")
    data_quality = db.Column(db.String(40), default="Correct")
    image_path = db.Column(db.String(200), default="")
    avg_rating = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    have_count = db.Column(db.Integer, default=0)
    want_count = db.Column(db.Integer, default=0)
    lowest_price = db.Column(db.Float)
    num_for_sale = db.Column(db.Integer, default=0)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    genres = db.relationship("Genre", secondary=release_genres, backref="releases")
    styles = db.relationship("Style", secondary=release_styles, backref="releases")
    formats = db.relationship("Format", secondary=release_formats, backref="releases")
    labels = db.relationship("Label", secondary=release_labels, backref="releases")
    tracks = db.relationship("Track", backref="release", lazy="dynamic",
                              cascade="all, delete-orphan", order_by="Track.position")
    reviews = db.relationship("Review", backref="release", lazy="dynamic",
                              cascade="all, delete-orphan")
    ratings = db.relationship("Rating", backref="release", lazy="dynamic",
                              cascade="all, delete-orphan")
    listings = db.relationship("Listing", backref="release", lazy="dynamic")
    master = db.relationship("Master", foreign_keys=[master_id], backref="versions")

    @property
    def primary_format(self):
        return self.formats[0].name if self.formats else ""

    @property
    def label_str(self):
        return ", ".join(l.name for l in self.labels[:3])

    @property
    def genre_str(self):
        return ", ".join(g.name for g in self.genres)

    @property
    def style_str(self):
        return ", ".join(s.name for s in self.styles)

    @property
    def cover_url(self):
        path = f"images/release/{self.discogs_id or self.id}.jpg"
        full = os.path.join(BASE_DIR, "static", path)
        if os.path.exists(full):
            return url_for("static", filename=path)
        return url_for("static", filename="icons/no-cover.svg")


class Track(db.Model):
    __tablename__ = "tracks"
    id = db.Column(db.Integer, primary_key=True)
    release_id = db.Column(db.Integer, db.ForeignKey("releases.id"), nullable=False, index=True)
    position = db.Column(db.String(10), default="")
    title = db.Column(db.String(300), nullable=False)
    duration = db.Column(db.String(10), default="")
    artist_credit = db.Column(db.String(200), default="")


class Rating(db.Model):
    __tablename__ = "ratings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    release_id = db.Column(db.Integer, db.ForeignKey("releases.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "release_id", name="uq_rating_user_release"),)


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    release_id = db.Column(db.Integer, db.ForeignKey("releases.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer)
    helpful = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


COLLECTION_FOLDERS = ["Uncategorized", "All", "Vinyl", "CD", "Wishlist Bought"]


class CollectionItem(db.Model):
    __tablename__ = "collection_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    release_id = db.Column(db.Integer, db.ForeignKey("releases.id"), nullable=False)
    folder = db.Column(db.String(40), default="Uncategorized")
    media_condition = db.Column(db.String(40), default="Near Mint (NM or M-)")
    sleeve_condition = db.Column(db.String(40), default="Near Mint (NM or M-)")
    notes = db.Column(db.String(280), default="")
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    release = db.relationship("Release")
    __table_args__ = (db.UniqueConstraint("user_id", "release_id", name="uq_coll_user_release"),)


class WantlistItem(db.Model):
    __tablename__ = "wantlist_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    release_id = db.Column(db.Integer, db.ForeignKey("releases.id"), nullable=False)
    min_grade = db.Column(db.String(40), default="Very Good Plus (VG+)")
    notes = db.Column(db.String(280), default="")
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    release = db.relationship("Release")
    __table_args__ = (db.UniqueConstraint("user_id", "release_id", name="uq_want_user_release"),)


class List(db.Model):
    __tablename__ = "lists"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("ListItem", backref="list", lazy="dynamic",
                            cascade="all, delete-orphan", order_by="ListItem.position")


class ListItem(db.Model):
    __tablename__ = "list_items"
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey("lists.id"), nullable=False, index=True)
    release_id = db.Column(db.Integer, db.ForeignKey("releases.id"))
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id"))
    label_id = db.Column(db.Integer, db.ForeignKey("labels.id"))
    comment = db.Column(db.String(400), default="")
    position = db.Column(db.Integer, default=0)
    release = db.relationship("Release")
    artist = db.relationship("Artist")
    label = db.relationship("Label")


GRADES = ["Mint (M)", "Near Mint (NM or M-)", "Very Good Plus (VG+)",
          "Very Good (VG)", "Good Plus (G+)", "Good (G)", "Fair (F)", "Poor (P)"]


class Listing(db.Model):
    __tablename__ = "listings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    release_id = db.Column(db.Integer, db.ForeignKey("releases.id"), nullable=False, index=True)
    media_condition = db.Column(db.String(40), default="Very Good Plus (VG+)")
    sleeve_condition = db.Column(db.String(40), default="Very Good Plus (VG+)")
    comments = db.Column(db.String(600), default="")
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(8), default="USD")
    shipping_from = db.Column(db.String(80), default="United States")
    allow_offers = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default="For Sale")
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)


class Forum(db.Model):
    __tablename__ = "forums"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True, index=True)
    description = db.Column(db.String(280), default="")
    threads = db.relationship("Thread", backref="forum", lazy="dynamic",
                              cascade="all, delete-orphan")


class Thread(db.Model):
    __tablename__ = "threads"
    id = db.Column(db.Integer, primary_key=True)
    forum_id = db.Column(db.Integer, db.ForeignKey("forums.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(280), nullable=False)
    pinned = db.Column(db.Boolean, default=False)
    locked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    posts = db.relationship("Post", backref="thread", lazy="dynamic",
                            cascade="all, delete-orphan", order_by="Post.created_at")


class Post(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("threads.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def slugify(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "x"


@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))


@app.context_processor
def inject_globals():
    return {
        "csrf_token": generate_csrf,
        "now": datetime.utcnow(),
        "grades": GRADES,
        "folders": COLLECTION_FOLDERS,
    }


@app.template_filter("price")
def fmt_price(v):
    if v is None:
        return "—"
    return f"${v:,.2f}"


@app.template_filter("relative")
def relative_time(dt):
    if not dt:
        return ""
    delta = datetime.utcnow() - dt
    s = int(delta.total_seconds())
    if s < 60: return "just now"
    if s < 3600: return f"{s//60} min ago"
    if s < 86400: return f"{s//3600} hours ago"
    if s < 86400 * 30: return f"{s//86400} days ago"
    if s < 86400 * 365: return f"{s//(86400*30)} months ago"
    return f"{s//(86400*365)} years ago"


@app.template_filter("stars")
def stars_filter(rating):
    if not rating:
        return "·····"
    full = int(round(rating))
    return "★" * full + "·" * (5 - full)


def paginate(query, page, per_page=25):
    page = max(1, page)
    total = query.count()
    pages = max(1, math.ceil(total / per_page))
    page = min(page, pages)
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    # Use SimpleNamespace so .items doesn't clash with dict.items() in Jinja.
    from types import SimpleNamespace
    return SimpleNamespace(items=items, page=page, pages=pages, total=total, per_page=per_page)


def search_releases(q, genre=None, style=None, format_=None, year=None, country=None,
                    sort="relevance", page=1, per_page=25):
    qs = Release.query
    if q:
        terms = [t for t in re.split(r"\s+", q.strip()) if t]
        if terms:
            anyclause = or_(*[
                Release.title.ilike(f"%{t}%") for t in terms
            ] + [
                Artist.name.ilike(f"%{t}%") for t in terms
            ])
            qs = qs.join(Artist, Release.artist_id == Artist.id).filter(anyclause)
    if genre:
        qs = qs.join(release_genres).join(Genre).filter(Genre.slug == genre)
    if style:
        qs = qs.join(release_styles).join(Style).filter(Style.slug == style)
    if format_:
        qs = qs.join(release_formats).join(Format).filter(Format.slug == format_)
    if year:
        try:
            qs = qs.filter(Release.year == int(year))
        except ValueError:
            pass
    if country:
        qs = qs.filter(Release.country.ilike(country))
    if sort == "year_desc":
        qs = qs.order_by(Release.year.desc().nullslast())
    elif sort == "year_asc":
        qs = qs.order_by(Release.year.asc().nullslast())
    elif sort == "title":
        qs = qs.order_by(Release.title.asc())
    elif sort == "have":
        qs = qs.order_by(Release.have_count.desc())
    elif sort == "want":
        qs = qs.order_by(Release.want_count.desc())
    elif sort == "rating":
        qs = qs.order_by(Release.avg_rating.desc(), Release.rating_count.desc())
    else:
        qs = qs.order_by(Release.have_count.desc())
    return paginate(qs.distinct(), page, per_page)


# ──────────────────────────────────────────────
# Routes — public
# ──────────────────────────────────────────────

@app.route("/")
def index():
    new_arrivals = Release.query.order_by(Release.added_at.desc()).limit(8).all()
    top_rated = Release.query.filter(Release.rating_count >= 3) \
                              .order_by(Release.avg_rating.desc(), Release.rating_count.desc()) \
                              .limit(8).all()
    most_collected = Release.query.order_by(Release.have_count.desc()).limit(8).all()
    most_wanted = Release.query.order_by(Release.want_count.desc()).limit(8).all()
    recent_lists = List.query.filter_by(is_public=True).order_by(List.created_at.desc()).limit(6).all()
    forums = Forum.query.order_by(Forum.id).limit(8).all()
    return render_template("index.html",
                           new_arrivals=new_arrivals,
                           top_rated=top_rated,
                           most_collected=most_collected,
                           most_wanted=most_wanted,
                           recent_lists=recent_lists,
                           forums=forums)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    type_ = request.args.get("type", "release")
    sort = request.args.get("sort", "relevance")
    page = int(request.args.get("page", 1))
    filters = {
        "genre": request.args.get("genre"),
        "style": request.args.get("style"),
        "format_": request.args.get("format"),
        "year": request.args.get("year"),
        "country": request.args.get("country"),
    }
    results = None
    artists = labels = []
    if type_ == "artist" and q:
        terms = [t for t in re.split(r"\s+", q) if t]
        if terms:
            clause = or_(*[Artist.name.ilike(f"%{t}%") for t in terms])
            artists = Artist.query.filter(clause).order_by(Artist.in_collection.desc()).limit(50).all()
    elif type_ == "label" and q:
        terms = [t for t in re.split(r"\s+", q) if t]
        if terms:
            clause = or_(*[Label.name.ilike(f"%{t}%") for t in terms])
            labels = Label.query.filter(clause).order_by(Label.name.asc()).limit(50).all()
    else:
        results = search_releases(q, sort=sort, page=page, **filters)

    facet_genres = Genre.query.order_by(Genre.name).all()
    facet_styles = Style.query.order_by(Style.name).limit(40).all()
    facet_formats = Format.query.order_by(Format.name).all()
    return render_template("search.html",
                           q=q, type_=type_, sort=sort,
                           results=results, artists=artists, labels=labels,
                           filters=filters,
                           facet_genres=facet_genres,
                           facet_styles=facet_styles,
                           facet_formats=facet_formats)


@app.route("/release/<int:rid>")
@app.route("/release/<int:rid>/<slug>")
def release_detail(rid, slug=None):
    r = Release.query.filter_by(discogs_id=rid).first() or Release.query.get_or_404(rid)
    reviews = r.reviews.order_by(Review.helpful.desc(), Review.created_at.desc()).limit(20).all()
    rating_hist = defaultdict(int)
    for rt in r.ratings.all():
        rating_hist[rt.value] += 1
    listings = r.listings.filter_by(status="For Sale").order_by(Listing.price.asc()).limit(25).all()
    other_versions = []
    if r.master_id:
        other_versions = Release.query.filter(Release.master_id == r.master_id,
                                              Release.id != r.id).limit(12).all()
    related = Release.query.filter(Release.artist_id == r.artist_id, Release.id != r.id) \
                            .limit(8).all()
    user_state = {}
    if current_user.is_authenticated:
        user_state["in_collection"] = CollectionItem.query.filter_by(
            user_id=current_user.id, release_id=r.id).first() is not None
        user_state["in_wantlist"] = WantlistItem.query.filter_by(
            user_id=current_user.id, release_id=r.id).first() is not None
        ur = Rating.query.filter_by(user_id=current_user.id, release_id=r.id).first()
        user_state["my_rating"] = ur.value if ur else 0
    return render_template("release.html",
                           r=r, reviews=reviews, rating_hist=rating_hist,
                           listings=listings, other_versions=other_versions,
                           related=related, user_state=user_state)


@app.route("/master/<int:mid>")
def master_detail(mid):
    m = Master.query.get_or_404(mid)
    versions = Release.query.filter_by(master_id=m.id).order_by(Release.year.asc().nullslast()).all()
    return render_template("master.html", m=m, versions=versions)


@app.route("/artist/<int:aid>")
@app.route("/artist/<int:aid>/<slug>")
def artist_detail(aid, slug=None):
    a = Artist.query.get_or_404(aid)
    sort = request.args.get("sort", "year_desc")
    page = int(request.args.get("page", 1))
    q = a.releases
    if sort == "year_asc":
        q = q.order_by(Release.year.asc().nullslast())
    elif sort == "title":
        q = q.order_by(Release.title.asc())
    elif sort == "have":
        q = q.order_by(Release.have_count.desc())
    else:
        q = q.order_by(Release.year.desc().nullslast())
    pag = paginate(q, page, 24)
    return render_template("artist.html", a=a, pag=pag, sort=sort)


@app.route("/label/<int:lid>")
@app.route("/label/<int:lid>/<slug>")
def label_detail(lid, slug=None):
    l = Label.query.get_or_404(lid)
    page = int(request.args.get("page", 1))
    q = Release.query.join(release_labels).filter(release_labels.c.label_id == lid) \
                     .order_by(Release.year.desc().nullslast())
    pag = paginate(q.distinct(), page, 24)
    sublabels = Label.query.filter_by(parent_label_id=lid).order_by(Label.name).all()
    return render_template("label.html", l=l, pag=pag, sublabels=sublabels)


@app.route("/genre/<slug>")
def genre_detail(slug):
    g = Genre.query.filter_by(slug=slug).first_or_404()
    page = int(request.args.get("page", 1))
    sort = request.args.get("sort", "have")
    q = Release.query.join(release_genres).filter(release_genres.c.genre_id == g.id)
    if sort == "year_desc":
        q = q.order_by(Release.year.desc().nullslast())
    elif sort == "rating":
        q = q.order_by(Release.avg_rating.desc(), Release.rating_count.desc())
    else:
        q = q.order_by(Release.have_count.desc())
    pag = paginate(q.distinct(), page, 24)
    styles = Style.query.join(release_styles).join(Release).join(release_genres) \
                         .filter(release_genres.c.genre_id == g.id).distinct() \
                         .order_by(Style.name).all()
    return render_template("genre.html", g=g, pag=pag, sort=sort, styles=styles)


@app.route("/style/<slug>")
def style_detail(slug):
    s = Style.query.filter_by(slug=slug).first_or_404()
    page = int(request.args.get("page", 1))
    q = Release.query.join(release_styles).filter(release_styles.c.style_id == s.id) \
                     .order_by(Release.have_count.desc())
    pag = paginate(q.distinct(), page, 24)
    return render_template("style.html", s=s, pag=pag)


@app.route("/format/<slug>")
def format_detail(slug):
    f = Format.query.filter_by(slug=slug).first_or_404()
    page = int(request.args.get("page", 1))
    q = Release.query.join(release_formats).filter(release_formats.c.format_id == f.id) \
                     .order_by(Release.have_count.desc())
    pag = paginate(q.distinct(), page, 24)
    return render_template("format.html", f=f, pag=pag)


@app.route("/explore")
def explore():
    genres = Genre.query.order_by(Genre.name).all()
    formats = Format.query.order_by(Format.name).all()
    decades = sorted({(y // 10) * 10 for (y,) in
                       db.session.query(Release.year).filter(Release.year != None).all()})
    countries = sorted({c for (c,) in
                         db.session.query(Release.country).filter(Release.country != "").all()})
    return render_template("explore.html", genres=genres, formats=formats,
                           decades=decades, countries=countries[:50])


# ──────────────────────────────────────────────
# Lists
# ──────────────────────────────────────────────

@app.route("/lists")
def lists_index():
    page = int(request.args.get("page", 1))
    q = List.query.filter_by(is_public=True).order_by(List.created_at.desc())
    pag = paginate(q, page, 20)
    return render_template("lists.html", pag=pag)


@app.route("/list/<int:lid>")
def list_detail(lid):
    lst = List.query.get_or_404(lid)
    if not lst.is_public and (not current_user.is_authenticated or current_user.id != lst.user_id):
        abort(403)
    return render_template("list.html", lst=lst)


@app.route("/list/new", methods=["GET", "POST"])
@login_required
def list_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title required.", "error")
            return redirect(url_for("list_new"))
        lst = List(user_id=current_user.id,
                   title=title[:200],
                   description=request.form.get("description", "")[:2000],
                   is_public=bool(request.form.get("is_public")))
        db.session.add(lst)
        db.session.commit()
        flash(f"List '{lst.title}' created.", "success")
        return redirect(url_for("list_detail", lid=lst.id))
    return render_template("list_new.html")


@app.route("/list/<int:lid>/add", methods=["POST"])
@login_required
def list_add_item(lid):
    lst = List.query.get_or_404(lid)
    if lst.user_id != current_user.id:
        abort(403)
    rid = request.form.get("release_id", type=int)
    comment = request.form.get("comment", "").strip()[:400]
    if rid and Release.query.get(rid):
        pos = (lst.items.count() or 0) + 1
        db.session.add(ListItem(list_id=lid, release_id=rid, comment=comment, position=pos))
        db.session.commit()
        flash("Release added.", "success")
    return redirect(url_for("list_detail", lid=lid))


# ──────────────────────────────────────────────
# Marketplace
# ──────────────────────────────────────────────

@app.route("/marketplace")
def marketplace():
    page = int(request.args.get("page", 1))
    sort = request.args.get("sort", "price_asc")
    media = request.args.get("media", "")  # e.g. "Near Mint (NM or M-)"
    genre = request.args.get("genre", "")
    q = Listing.query.filter_by(status="For Sale").join(Release)
    if media:
        q = q.filter(Listing.media_condition == media)
    if genre:
        q = q.join(release_genres, Release.id == release_genres.c.release_id) \
             .join(Genre, Genre.id == release_genres.c.genre_id) \
             .filter(Genre.slug == genre)
    if sort == "price_desc":
        q = q.order_by(Listing.price.desc())
    elif sort == "newest":
        q = q.order_by(Listing.posted_at.desc())
    else:
        q = q.order_by(Listing.price.asc())
    pag = paginate(q.distinct(), page, 30)
    genres = Genre.query.order_by(Genre.name).all()
    return render_template("marketplace.html", pag=pag, sort=sort,
                           media=media, genre=genre, grades=GRADES, genres=genres)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        rid = request.form.get("release_id", type=int)
        # Allow either the public Discogs ID or the internal PK so the
        # form matches the IDs visible in URLs (/release/<discogs_id>).
        release = None
        if rid:
            release = Release.query.filter_by(discogs_id=rid).first() or Release.query.get(rid)
        if not release:
            flash("Pick a valid release.", "error")
            return redirect(url_for("sell"))
        try:
            price = float(request.form.get("price"))
        except (TypeError, ValueError):
            flash("Price must be a number.", "error")
            return redirect(url_for("sell"))
        l = Listing(user_id=current_user.id, release_id=release.id,
                    media_condition=request.form.get("media_condition", "Very Good Plus (VG+)"),
                    sleeve_condition=request.form.get("sleeve_condition", "Very Good Plus (VG+)"),
                    comments=request.form.get("comments", "")[:600],
                    price=price,
                    currency=request.form.get("currency", "USD"),
                    shipping_from=request.form.get("shipping_from", "United States"),
                    allow_offers=bool(request.form.get("allow_offers")))
        current_user.is_seller = True
        db.session.add(l)
        db.session.commit()
        release.num_for_sale = Listing.query.filter_by(release_id=release.id, status="For Sale").count()
        release.lowest_price = db.session.query(func.min(Listing.price)) \
                                          .filter(Listing.release_id == release.id,
                                                  Listing.status == "For Sale").scalar()
        db.session.commit()
        flash("Listing posted to the marketplace.", "success")
        return redirect(url_for("marketplace"))
    return render_template("sell.html")


# ──────────────────────────────────────────────
# User / collection / wantlist
# ──────────────────────────────────────────────

@app.route("/user/<username>")
def user_profile(username):
    u = User.query.filter_by(username=username).first_or_404()
    coll_n = u.collection_items.count()
    want_n = u.wantlist_items.count()
    reviews = u.reviews.order_by(Review.created_at.desc()).limit(5).all()
    lists = u.lists.filter_by(is_public=True).order_by(List.created_at.desc()).limit(6).all()
    return render_template("user.html", u=u, coll_n=coll_n, want_n=want_n,
                           reviews=reviews, lists=lists)


@app.route("/user/<username>/collection")
def user_collection(username):
    u = User.query.filter_by(username=username).first_or_404()
    folder = request.args.get("folder", "All")
    page = int(request.args.get("page", 1))
    q = u.collection_items.join(Release)
    if folder != "All":
        q = q.filter(CollectionItem.folder == folder)
    q = q.order_by(CollectionItem.added_at.desc())
    pag = paginate(q, page, 25)
    return render_template("collection.html", u=u, pag=pag, folder=folder,
                           folders=COLLECTION_FOLDERS)


@app.route("/user/<username>/wantlist")
def user_wantlist(username):
    u = User.query.filter_by(username=username).first_or_404()
    page = int(request.args.get("page", 1))
    q = u.wantlist_items.join(Release).order_by(WantlistItem.added_at.desc())
    pag = paginate(q, page, 25)
    return render_template("wantlist.html", u=u, pag=pag)


@app.route("/user/<username>/lists")
def user_lists(username):
    u = User.query.filter_by(username=username).first_or_404()
    lists = u.lists.order_by(List.created_at.desc()).all()
    return render_template("user_lists.html", u=u, lists=lists)


@app.route("/user/<username>/reviews")
def user_reviews(username):
    u = User.query.filter_by(username=username).first_or_404()
    reviews = u.reviews.order_by(Review.created_at.desc()).all()
    return render_template("user_reviews.html", u=u, reviews=reviews)


@app.route("/user/<username>/feedback")
def user_feedback(username):
    u = User.query.filter_by(username=username).first_or_404()
    return render_template("user_feedback.html", u=u)


@app.route("/collection/add", methods=["POST"])
@login_required
def collection_add():
    rid = request.form.get("release_id", type=int)
    r = Release.query.get(rid) if rid else None
    if not r:
        return redirect(request.referrer or url_for("index"))
    existing = CollectionItem.query.filter_by(user_id=current_user.id, release_id=rid).first()
    if existing:
        flash("Already in your collection.", "info")
    else:
        c = CollectionItem(user_id=current_user.id, release_id=rid,
                           folder=request.form.get("folder", "Uncategorized"),
                           media_condition=request.form.get("media_condition", "Near Mint (NM or M-)"),
                           sleeve_condition=request.form.get("sleeve_condition", "Near Mint (NM or M-)"),
                           notes=request.form.get("notes", "")[:280])
        db.session.add(c)
        r.have_count = (r.have_count or 0) + 1
        db.session.commit()
        flash("Added to your collection.", "success")
    return redirect(request.referrer or url_for("release_detail", rid=r.discogs_id or r.id))


@app.route("/collection/remove", methods=["POST"])
@login_required
def collection_remove():
    rid = request.form.get("release_id", type=int)
    c = CollectionItem.query.filter_by(user_id=current_user.id, release_id=rid).first()
    if c:
        r = Release.query.get(rid)
        if r and r.have_count > 0:
            r.have_count -= 1
        db.session.delete(c)
        db.session.commit()
        flash("Removed from collection.", "success")
    return redirect(request.referrer or url_for("user_collection", username=current_user.username))


@app.route("/wantlist/add", methods=["POST"])
@login_required
def wantlist_add():
    rid = request.form.get("release_id", type=int)
    r = Release.query.get(rid) if rid else None
    if not r:
        return redirect(request.referrer or url_for("index"))
    if WantlistItem.query.filter_by(user_id=current_user.id, release_id=rid).first():
        flash("Already in your wantlist.", "info")
    else:
        w = WantlistItem(user_id=current_user.id, release_id=rid,
                         min_grade=request.form.get("min_grade", "Very Good Plus (VG+)"),
                         notes=request.form.get("notes", "")[:280])
        db.session.add(w)
        r.want_count = (r.want_count or 0) + 1
        db.session.commit()
        flash("Added to your wantlist.", "success")
    return redirect(request.referrer or url_for("release_detail", rid=r.discogs_id or r.id))


@app.route("/wantlist/remove", methods=["POST"])
@login_required
def wantlist_remove():
    rid = request.form.get("release_id", type=int)
    w = WantlistItem.query.filter_by(user_id=current_user.id, release_id=rid).first()
    if w:
        r = Release.query.get(rid)
        if r and r.want_count > 0:
            r.want_count -= 1
        db.session.delete(w)
        db.session.commit()
        flash("Removed from wantlist.", "success")
    return redirect(request.referrer or url_for("user_wantlist", username=current_user.username))


@app.route("/rate", methods=["POST"])
@login_required
def rate():
    rid = request.form.get("release_id", type=int)
    val = request.form.get("rating", type=int)
    if not (rid and val and 1 <= val <= 5):
        flash("Bad rating.", "error")
        return redirect(request.referrer or url_for("index"))
    r = Release.query.get_or_404(rid)
    rt = Rating.query.filter_by(user_id=current_user.id, release_id=rid).first()
    if rt:
        rt.value = val
    else:
        db.session.add(Rating(user_id=current_user.id, release_id=rid, value=val))
    db.session.commit()
    agg = db.session.query(func.avg(Rating.value), func.count(Rating.id)) \
                     .filter(Rating.release_id == rid).first()
    r.avg_rating = float(agg[0] or 0.0)
    r.rating_count = int(agg[1] or 0)
    db.session.commit()
    return redirect(request.referrer or url_for("release_detail", rid=r.discogs_id or r.id))


@app.route("/review", methods=["POST"])
@login_required
def review_post():
    rid = request.form.get("release_id", type=int)
    body = request.form.get("body", "").strip()
    rating = request.form.get("rating", type=int)
    if not rid or not body:
        flash("Review body required.", "error")
        return redirect(request.referrer or url_for("index"))
    rv = Review(user_id=current_user.id, release_id=rid, body=body[:4000],
                rating=rating if rating and 1 <= rating <= 5 else None)
    db.session.add(rv)
    db.session.commit()
    flash("Review posted.", "success")
    r = Release.query.get(rid)
    return redirect(url_for("release_detail", rid=r.discogs_id or r.id))


# ──────────────────────────────────────────────
# Forums
# ──────────────────────────────────────────────

@app.route("/forum")
def forum_index():
    forums = Forum.query.order_by(Forum.id).all()
    return render_template("forum_index.html", forums=forums)


@app.route("/forum/<slug>")
def forum_view(slug):
    f = Forum.query.filter_by(slug=slug).first_or_404()
    page = int(request.args.get("page", 1))
    q = f.threads.order_by(Thread.pinned.desc(), Thread.created_at.desc())
    pag = paginate(q, page, 25)
    return render_template("forum.html", f=f, pag=pag)


@app.route("/thread/<int:tid>")
def thread_view(tid):
    t = Thread.query.get_or_404(tid)
    posts = t.posts.order_by(Post.created_at.asc()).all()
    return render_template("thread.html", t=t, posts=posts)


@app.route("/thread/<int:tid>/reply", methods=["POST"])
@login_required
def thread_reply(tid):
    t = Thread.query.get_or_404(tid)
    if t.locked:
        flash("Thread is locked.", "error")
        return redirect(url_for("thread_view", tid=tid))
    body = request.form.get("body", "").strip()
    if not body:
        flash("Empty post.", "error")
        return redirect(url_for("thread_view", tid=tid))
    p = Post(thread_id=tid, user_id=current_user.id, body=body[:4000])
    db.session.add(p)
    db.session.commit()
    return redirect(url_for("thread_view", tid=tid))


@app.route("/forum/<slug>/new", methods=["GET", "POST"])
@login_required
def thread_new(slug):
    f = Forum.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title or not body:
            flash("Title and body required.", "error")
            return redirect(url_for("thread_new", slug=slug))
        t = Thread(forum_id=f.id, user_id=current_user.id, title=title[:280])
        db.session.add(t); db.session.flush()
        db.session.add(Post(thread_id=t.id, user_id=current_user.id, body=body[:4000]))
        db.session.commit()
        return redirect(url_for("thread_view", tid=t.id))
    return render_template("thread_new.html", f=f)


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        ident = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        u = User.query.filter(or_(User.username == ident, User.email == ident.lower())).first()
        if u and bcrypt.check_password_hash(u.password_hash, pw):
            login_user(u, remember=bool(request.form.get("remember")))
            flash(f"Welcome back, {u.username}.", "success")
            return redirect(request.args.get("next") or url_for("index"))
        flash("Invalid credentials.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        if not (3 <= len(username) <= 40 and "@" in email and len(pw) >= 6):
            flash("Username 3-40 chars; valid email; password ≥6.", "error")
            return redirect(url_for("register"))
        if User.query.filter_by(username=username).first():
            flash("Username taken.", "error"); return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error"); return redirect(url_for("register"))
        u = User(username=username, email=email,
                 password_hash=bcrypt.generate_password_hash(pw).decode("utf-8"),
                 avatar_seed=username, location=request.form.get("location", "")[:100])
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash("Account created. Welcome to Discogs!", "success")
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/logout", methods=["POST", "GET"])
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        current_user.real_name = request.form.get("real_name", "")[:120]
        current_user.location = request.form.get("location", "")[:100]
        current_user.bio = request.form.get("bio", "")[:2000]
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html")


# ──────────────────────────────────────────────
# Health / errors
# ──────────────────────────────────────────────

@app.route("/_health")
def health():
    return {"ok": True, "site": "discogs",
            "releases": Release.query.count(),
            "artists": Artist.query.count()}


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


# ──────────────────────────────────────────────
# Boot
# ──────────────────────────────────────────────

with app.app_context():
    db.create_all()
    try:
        import sys as _sys
        _sys.path.insert(0, BASE_DIR)
        from seed_data import seed_database, seed_benchmark_users, seed_community
        seed_database()
        seed_benchmark_users()
        seed_community()
    except Exception as e:
        print(f"[discogs] seed warning: {e}")
        import traceback; traceback.print_exc()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
