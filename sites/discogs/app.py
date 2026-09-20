"""Discogs mirror — Flask app for WebHarbor.

Models the catalogue (Release/Master/Artist/Label/Genre/Style/Format/Track),
community (User/Rating/Review/Collection/Wantlist/List), marketplace listings,
and forum threads. Verified catalog data and synthetic benchmark community
state ship together in instance_seed/discogs.db.
"""
import os
import re
import math
import json
import random
import sys
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote, urljoin, urlsplit

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort, g, make_response, send_from_directory)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_bcrypt import Bcrypt
from sqlalchemy import or_, and_, func, desc, asc, case

# seed_data imports models from app. Keep the CLI entrypoint and imported module
# identical, just as the supervisor's `from app import app` launch does.
if __name__ == "__main__":
    sys.modules["app"] = sys.modules[__name__]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.environ.get("DISCOGS_INSTANCE_DIR", os.path.join(BASE_DIR, "instance"))
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

release_artists = db.Table(
    "release_artists",
    db.Column("release_id", db.Integer, db.ForeignKey("releases.id"), primary_key=True),
    db.Column("artist_id", db.Integer, db.ForeignKey("artists.id"), primary_key=True),
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
    discogs_id = db.Column(db.Integer, unique=True, index=True)
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
    discogs_id = db.Column(db.Integer, unique=True, index=True)
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
    discogs_id = db.Column(db.Integer, unique=True, index=True)
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
    artist_credit = db.Column(db.Text, default="")
    format_description = db.Column(db.Text, default="")
    source_json = db.Column(db.Text, default="")
    source_sha256 = db.Column(db.String(64), default="")
    source_captured_at = db.Column(db.String(40), default="")
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id"), nullable=False, index=True)
    master_id = db.Column(db.Integer, db.ForeignKey("masters.id"))
    year = db.Column(db.Integer, index=True)
    released = db.Column(db.String(40), default="")
    country = db.Column(db.String(80), default="")
    notes = db.Column(db.Text, default="")
    barcode = db.Column(db.String(80), default="")
    catno = db.Column(db.String(80), default="")
    data_quality = db.Column(db.String(40), default="")
    image_path = db.Column(db.String(200), default="")
    avg_rating = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    have_count = db.Column(db.Integer, default=0)
    want_count = db.Column(db.Integer, default=0)
    lowest_price = db.Column(db.Float)
    num_for_sale = db.Column(db.Integer, default=0)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    genres = db.relationship("Genre", secondary=release_genres, backref="releases")
    credited_artists = db.relationship("Artist", secondary=release_artists, backref="credited_releases")
    styles = db.relationship("Style", secondary=release_styles, backref="releases")
    formats = db.relationship("Format", secondary=release_formats, backref="releases")
    labels = db.relationship("Label", secondary=release_labels, backref="releases")
    tracks = db.relationship("Track", backref="release", lazy="dynamic",
                              cascade="all, delete-orphan", order_by="Track.id")
    reviews = db.relationship("Review", backref="release", lazy="dynamic",
                              cascade="all, delete-orphan")
    ratings = db.relationship("Rating", backref="release", lazy="dynamic",
                              cascade="all, delete-orphan")
    listings = db.relationship("Listing", backref="release", lazy="dynamic")
    master = db.relationship("Master", foreign_keys=[master_id], backref="versions")

    @property
    def primary_format(self):
        formats = self.source_data.get("formats") or []
        if formats:
            return formats[0]["name"]
        return self.formats[0].name if self.formats else ""

    @property
    def source_data(self):
        return json.loads(self.source_json) if self.source_json else {}

    @property
    def display_artist(self):
        return self.artist_credit or self.artist.name

    @property
    def artist_entries(self):
        artists_by_id = {artist.discogs_id: artist for artist in self.credited_artists
                         if artist.discogs_id is not None}
        artists_by_name = {artist.name: artist for artist in self.credited_artists}
        entries = []
        for source in self.source_data.get("artists", []):
            artist = (artists_by_id.get(source.get("id")) if source.get("id") is not None
                      else artists_by_name.get(source.get("name")))
            if artist:
                entries.append((artist, source.get("anv") or source["name"], source.get("join") or ""))
        return entries or [(self.artist, self.artist.name, "")]

    @property
    def label_entries(self):
        labels_by_id = {label.discogs_id: label for label in self.labels
                        if label.discogs_id is not None}
        labels_by_name = {label.name: label for label in self.labels}
        entries = []
        for source in self.source_data.get("labels", []):
            label = (labels_by_id.get(source.get("id")) if source.get("id") is not None
                     else labels_by_name.get(source.get("name")))
            if label:
                entries.append((label, source.get("catno") or ""))
        return entries

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
        path = self.image_path or ""
        full = os.path.join(BASE_DIR, "static", path)
        if path and os.path.isfile(full):
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
    kind = db.Column(db.String(20), default="track")
    depth = db.Column(db.Integer, default=0)


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


# "All" is the unfiltered view, not a folder. It must not appear here: the collection
# list treats folder == "All" as "do not filter", so a row actually stored with that
# folder could never be viewed as a folder again, and the template renders the tab row
# as ["All"] + COLLECTION_FOLDERS, which duplicated the tab.
COLLECTION_FOLDERS = ["Uncategorized", "Vinyl", "CD", "Wishlist Bought"]
UNFILTERED_FOLDER = "All"


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
CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CAD")


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


def nav_groups():
    """Header menu groups mirroring the live Discogs secondary navigation.

    Every destination is local. Live items without a data-backed equivalent
    map to local informational pages instead of being dropped.
    """
    def item(label, href):
        return {"label": label, "href": href}
    return [
        {"label": "Explore Discography", "align": "left", "items": [
            item("Explore All", url_for("search")),
            item("Advanced Search", url_for("search_advanced")),
            item("Most Collected", url_for("search", sort="have", type="release")),
            item("Submit a Release", "/release/add"),
            item("Submission Guidelines", "/guidelines/submissions"),
        ]},
        {"label": "Shop Music", "align": "left", "items": [
            item("Shop My Wants", url_for("shop_my_wants")),
            item("New & Upcoming", url_for("search", sort="newest")),
            item("Vinyl", url_for("marketplace", format="Vinyl")),
            item("CD", url_for("marketplace", format="CD")),
            item("Cassette", url_for("marketplace", format="Cassette")),
            item("All Formats", url_for("marketplace")),
        ]},
        {"label": "Sell Music", "align": "left", "items": [
            item("List Item For Sale", url_for("sell")),
            item("Start Selling", "/selling/resources#start"),
            item("How To Grade", "/selling/resources#grade"),
            item("How To Price", "/selling/resources#price"),
            item("How To Pack & Ship", "/selling/resources#pack"),
            item("More Seller Resources", "/selling/resources"),
            item("Seller News & Updates", "/selling/resources#updates"),
        ]},
        {"label": "Community", "align": "left", "items": [
            item("Forum", url_for("forum_index")),
            item("Groups", url_for("groups")),
            item("List Explorer", url_for("lists_index")),
            item("Discography Contributors", url_for("contributors")),
            item("Monthly Leaderboard", url_for("leaderboard")),
            item("Community Guidelines", "/guidelines/community"),
        ]},
        {"label": "Digs", "align": "right", "items": [
            item("Essentials", "/digs#essentials"),
            item("Features", "/digs#features"),
            item("Most Valuable", "/digs#most-valuable"),
            item("Collecting", "/digs#collecting"),
            item("Audio Gear", "/digs#audio-gear"),
        ]},
    ]


def footer_columns():
    """Footer columns mirroring the live Discogs footer labels with local targets."""
    def item(label, href, dialog=None):
        return {"label": label, "href": href, "dialog": dialog}
    return [
        {"title": "About", "items": [
            item("Get Started", "/about/get-started"),
            item("What is Discogs?", "/about/about"),
            item("Discography", "/about/features/discography"),
            item("Marketplace", "/about/features/music-marketplace"),
            item("Collection", "/about/features/collection"),
            item("Wantlist", "/about/features/wantlist"),
            item("Statistics", "/about/features/sales-history"),
            item("Careers", "/about/careers"),
        ]},
        {"title": "Community", "items": [
            item("Community Guidelines", "/guidelines/community"),
            item("Community Advisory", "/about/get-involved/community-advisory"),
            item("Contributor List", url_for("contributors")),
            item("Add Release", "/release/add"),
            item("Developer API", "/developers"),
            item("Help Translate", url_for("forum_view", slug="help")),
        ]},
        {"title": "Help & Resources", "items": [
            item("Help Center", "/help"),
            item("Seller Resource Center", "/selling/resources"),
            item("Submission Guidelines", "/guidelines/submissions"),
            item("Trust Center", "/about/trust"),
            item("Forum", url_for("forum_index")),
            item("System Status", "/status"),
            item("Keyboard Shortcuts", "#", dialog="shortcuts"),
        ]},
    ]


@app.context_processor
def inject_globals():
    return {
        "csrf_token": generate_csrf,
        "now": datetime.utcnow(),
        "grades": GRADES,
        "folders": COLLECTION_FOLDERS,
        "nav_groups": nav_groups(),
        "footer_columns": footer_columns(),
    }


@app.template_filter("price")
def fmt_price(v, currency="USD"):
    if v is None:
        return "—"
    return f"{currency} {v:,.2f}"


def local_return(target, fallback):
    """Keep login and form redirects inside this mirror's origin."""
    if not target or target != target.strip():
        return fallback
    decoded = unquote(target)
    if "\\" in decoded or any(ord(char) < 32 or ord(char) == 127 for char in decoded):
        return fallback
    if decoded.startswith("//"):
        return fallback
    try:
        resolved = urlsplit(urljoin(request.host_url, target))
        origin = urlsplit(request.host_url)
        if (resolved.scheme, resolved.netloc) != (origin.scheme, origin.netloc):
            return fallback
    except ValueError:
        return fallback
    return target


def return_to_page(fallback):
    return redirect(local_return(request.referrer, fallback))


@app.template_global()
def page_url(page):
    """Replace the current page without duplicating it or losing filters."""
    params = request.args.to_dict(flat=False)
    params["page"] = page
    return url_for(request.endpoint, **(request.view_args or {}), **params)


@app.template_filter("discogs_text")
def discogs_text(value):
    """Display source BBCode as plain text; Jinja still escapes all HTML."""
    text = re.sub(r"\[url(?:=[^\]]*)?\](.*?)\[/url\]", r"\1", value or "", flags=re.I | re.S)
    text = re.sub(r"\[(?:a|l|r|m)=([^\]]+)\]", r"\1", text, flags=re.I)
    text = re.sub(r"\[(/?)(?:b|i|u)\]", "", text, flags=re.I)
    def reference(match):
        kind, identity = match.group(1).lower(), int(match.group(2))
        model = {"r": Release, "m": Master, "a": Artist, "l": Label}[kind]
        entity = (Release.query.filter_by(discogs_id=identity).first()
                  if kind == "r" else db.session.get(model, identity))
        return ((getattr(entity, "title", None) or getattr(entity, "name", None))
                if entity else f"{ {'r': 'Release', 'm': 'Master', 'a': 'Artist', 'l': 'Label'}[kind]} {identity}")
    return re.sub(r"\[([ralm])(\d+)\]", reference, text, flags=re.I)


@app.template_global()
def search_url(**changes):
    params = {key: value for key, value in request.args.items()
              if key in {"q", "type", "genre", "style", "format", "year", "country", "sort",
                         "label", "catno", "barcode"}}
    params.update(changes)
    return url_for("search", **{key: value for key, value in params.items() if value is not None})


def _ago(n, unit):
    """Live Discogs writes "1 day ago", not "1 days ago"."""
    return f"{n} {unit}{'' if n == 1 else 's'} ago"


@app.template_filter("relative")
def relative_time(dt):
    if not dt:
        return ""
    delta = datetime.utcnow() - dt
    s = int(delta.total_seconds())
    if s < 60: return "just now"
    if s < 3600: return _ago(s // 60, "minute")
    if s < 86400: return _ago(s // 3600, "hour")
    if s < 86400 * 30: return _ago(s // 86400, "day")
    if s < 86400 * 365: return _ago(s // (86400 * 30), "month")
    return _ago(s // (86400 * 365), "year")


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


def release_query(q, genre=None, style=None, format_=None, year=None, country=None,
                  label=None, catno=None, barcode=None):
    """Unsorted release query for a search; shared by results and facet counts."""
    qs = Release.query
    if label:
        qs = qs.filter(Release.labels.any(Label.name.ilike(f"%{label.strip()}%")))
    if catno:
        qs = qs.filter(Release.catno.ilike(f"%{catno.strip()}%"))
    if barcode:
        qs = qs.filter(Release.barcode.ilike(f"%{barcode.strip()}%"))
    relevance = None
    if q:
        terms = [t for t in re.split(r"\s+", q.strip()) if t]
        if terms:
            matches = [or_(Release.title.ilike(f"%{t}%"), Artist.name.ilike(f"%{t}%"),
                           Release.artist_credit.ilike(f"%{t}%"),
                           Release.credited_artists.any(Artist.name.ilike(f"%{t}%")))
                       for t in terms]
            relevance = sum(case((match, 1), else_=0) for match in matches)
            qs = qs.join(Artist, Release.artist_id == Artist.id).filter(or_(*matches))
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
    return qs, relevance


def search_facets(base, limit=15):
    """Facet values with counts inside the current result set (live search sidebar)."""
    ids = db.session.query(base.order_by(None).with_entities(Release.id).distinct().subquery().c.id)

    def grouped(model, assoc, column):
        rows = db.session.query(model.name, model.slug, func.count(assoc.c.release_id)) \
            .join(assoc, model.id == getattr(assoc.c, column)) \
            .filter(assoc.c.release_id.in_(ids)) \
            .group_by(model.id).order_by(func.count(assoc.c.release_id).desc(), model.name) \
            .limit(limit).all()
        return [{"name": name, "slug": slug, "count": count} for name, slug, count in rows]

    countries = db.session.query(Release.country, func.count(Release.id)) \
        .filter(Release.id.in_(ids), Release.country != "") \
        .group_by(Release.country).order_by(func.count(Release.id).desc(), Release.country).limit(limit).all()
    years = db.session.query(Release.year, func.count(Release.id)) \
        .filter(Release.id.in_(ids), Release.year.isnot(None)) \
        .group_by(Release.year).order_by(func.count(Release.id).desc(), Release.year.desc()).limit(limit).all()
    return {
        "genre": grouped(Genre, release_genres, "genre_id"),
        "style": grouped(Style, release_styles, "style_id"),
        "format": grouped(Format, release_formats, "format_id"),
        "country": [{"name": c, "slug": c, "count": n} for c, n in countries],
        "year": [{"name": str(y), "slug": str(y), "count": n} for y, n in years],
    }


def search_releases(q, genre=None, style=None, format_=None, year=None, country=None,
                    sort="relevance", page=1, per_page=25, label=None, catno=None, barcode=None):
    qs, relevance = release_query(q, genre=genre, style=style, format_=format_, year=year,
                                  country=country, label=label, catno=catno, barcode=barcode)
    if sort == "newest":
        qs = qs.order_by(Release.added_at.desc().nullslast())
    elif sort == "year_desc":
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
        if relevance is not None:
            qs = qs.order_by(relevance.desc())
        qs = qs.order_by(Release.have_count.desc())
    return paginate(qs.order_by(Release.id).distinct(), page, per_page)


# ──────────────────────────────────────────────
# Routes — public
# ──────────────────────────────────────────────

CAROUSEL_SIZE = 14  # the live homepage carousels carry 14 cards each


def most_valuable_releases(limit=CAROUSEL_SIZE):
    """Releases ranked by the highest current USD asking price in the benchmark marketplace."""
    top_price = db.session.query(Listing.release_id.label("release_id"),
                                 func.max(Listing.price).label("top")) \
        .filter(Listing.status == "For Sale", Listing.currency == "USD") \
        .group_by(Listing.release_id).subquery()
    return Release.query.join(top_price, top_price.c.release_id == Release.id) \
        .order_by(top_price.c.top.desc(), Release.id).limit(limit).all()


def best_selling_releases(limit=CAROUSEL_SIZE):
    """Releases with the most active benchmark listings, then the most wants.

    The snapshot has no sales ledger, so the ranking is synthetic marketplace demand.
    """
    return Release.query.filter(Release.num_for_sale > 0) \
        .order_by(Release.num_for_sale.desc(), Release.want_count.desc(), Release.id) \
        .limit(limit).all()


def most_collected_releases(limit=CAROUSEL_SIZE):
    return Release.query.order_by(Release.have_count.desc(), Release.id).limit(limit).all()


@app.route("/")
def index():
    return render_template("index.html",
                           best_selling=best_selling_releases(),
                           most_valuable=most_valuable_releases(),
                           most_collected=most_collected_releases())


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    type_ = request.args.get("type", "release")
    if type_ not in ("artist", "label"):
        type_ = "release"  # the header's "All" category searches releases here
    sort = request.args.get("sort", "relevance")
    page = request.args.get("page", 1, type=int)
    filters = {
        "genre": request.args.get("genre"),
        "style": request.args.get("style"),
        "format_": request.args.get("format"),
        "year": request.args.get("year"),
        "country": request.args.get("country"),
        "label": request.args.get("label"),
        "catno": request.args.get("catno"),
        "barcode": request.args.get("barcode"),
    }
    results = None
    artists = labels = []
    entity_pagination = None
    if type_ == "artist":
        query = Artist.query
        terms = [t for t in re.split(r"\s+", q) if t]
        if terms:
            clause = or_(*[Artist.name.ilike(f"%{t}%") for t in terms])
            query = query.filter(clause)
        entity_pagination = paginate(query.order_by(Artist.in_collection.desc(), Artist.id), page, 50)
        artists = entity_pagination.items
    elif type_ == "label":
        query = Label.query
        terms = [t for t in re.split(r"\s+", q) if t]
        if terms:
            clause = or_(*[Label.name.ilike(f"%{t}%") for t in terms])
            query = query.filter(clause)
        entity_pagination = paginate(query.order_by(Label.name, Label.id), page, 50)
        labels = entity_pagination.items
    else:
        results = search_releases(q, sort=sort, page=page, **filters)

    # Live search tabs show a count per entity type; facets count inside the results.
    terms = [t for t in re.split(r"\s+", q) if t]
    base, _ = release_query(q, **filters)
    counts = {
        "release": base.order_by(None).with_entities(Release.id).distinct().count(),
        "artist": (Artist.query.filter(or_(*[Artist.name.ilike(f"%{t}%") for t in terms]))
                   if terms else Artist.query).count(),
        "label": (Label.query.filter(or_(*[Label.name.ilike(f"%{t}%") for t in terms]))
                  if terms else Label.query).count(),
    }
    facets = search_facets(base) if type_ == "release" else {}
    return render_template("search.html",
                           q=q, type_=type_, sort=sort,
                           results=results, artists=artists, labels=labels,
                           entity_pagination=entity_pagination,
                           filters=filters, counts=counts, facets=facets)


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
    usd_prices = [l.price for l in listings if l.currency == "USD"]
    sale_stats = {
        "count": len(listings),
        "low": min(usd_prices) if usd_prices else None,
        "high": max(usd_prices) if usd_prices else None,
    }
    versions_total = Release.query.filter(Release.master_id == r.master_id).count() if r.master_id else 1
    return render_template("release.html",
                           r=r, reviews=reviews, rating_hist=rating_hist,
                           listings=listings, other_versions=other_versions,
                           versions_total=versions_total, sale_stats=sale_stats,
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
    page = request.args.get("page", 1, type=int)
    q = Release.query.filter(or_(Release.artist_id == a.id,
                                Release.credited_artists.any(Artist.id == a.id)))
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
    page = request.args.get("page", 1, type=int)
    q = Release.query.join(release_labels).filter(release_labels.c.label_id == lid) \
                     .order_by(Release.year.desc().nullslast())
    pag = paginate(q.distinct(), page, 24)
    sublabels = Label.query.filter_by(parent_label_id=lid).order_by(Label.name).all()
    return render_template("label.html", l=l, pag=pag, sublabels=sublabels)


@app.route("/genre/<slug>")
def genre_detail(slug):
    g = Genre.query.filter_by(slug=slug).first_or_404()
    page = request.args.get("page", 1, type=int)
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
    page = request.args.get("page", 1, type=int)
    q = Release.query.join(release_styles).filter(release_styles.c.style_id == s.id) \
                     .order_by(Release.have_count.desc())
    pag = paginate(q.distinct(), page, 24)
    return render_template("style.html", s=s, pag=pag)


@app.route("/format/<slug>")
def format_detail(slug):
    f = Format.query.filter_by(slug=slug).first_or_404()
    page = request.args.get("page", 1, type=int)
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
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    q = List.query.filter_by(is_public=True)
    if search:
        q = q.filter(List.title.ilike(f"%{search}%"))
    pag = paginate(q.order_by(List.created_at.desc()), page, 20)
    # "Lists We Like": the fullest public lists, each with the cover of its first release.
    item_counts = db.session.query(ListItem.list_id, func.count(ListItem.id).label("n")) \
        .group_by(ListItem.list_id).subquery()
    featured = List.query.join(item_counts, item_counts.c.list_id == List.id) \
        .filter(List.is_public.is_(True)).order_by(item_counts.c.n.desc(), List.id).limit(5).all()
    return render_template("lists.html", pag=pag, search=search, featured=featured)


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
    release = None
    if rid:
        # The form asks for the public ID shown in release URLs. Retain the
        # internal-PK fallback for existing benchmark fixtures.
        release = Release.query.filter_by(discogs_id=rid).first() or Release.query.get(rid)
    if release:
        pos = (lst.items.count() or 0) + 1
        db.session.add(ListItem(list_id=lid, release_id=release.id, comment=comment, position=pos))
        db.session.commit()
        flash("Release added.", "success")
    return redirect(url_for("list_detail", lid=lid))


# ──────────────────────────────────────────────
# Marketplace
# ──────────────────────────────────────────────

@app.route("/marketplace")
def marketplace():
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "price_asc")
    media = request.args.get("media", "")  # e.g. "Near Mint (NM or M-)"
    genre = request.args.get("genre", "")
    format_ = request.args.get("format", "")  # live: /sell/list?format=Vinyl
    ships_from = request.args.get("ships_from", "")
    year = request.args.get("year", type=int)
    price_min = request.args.get("price_min", type=float)
    price_max = request.args.get("price_max", type=float)
    text = request.args.get("q", "").strip()
    currency = request.args.get("currency", "USD")
    if currency not in CURRENCIES:
        currency = "USD"
    q = Listing.query.filter_by(status="For Sale", currency=currency).join(Release)
    if media:
        q = q.filter(Listing.media_condition == media)
    if genre:
        q = q.join(release_genres, Release.id == release_genres.c.release_id) \
             .join(Genre, Genre.id == release_genres.c.genre_id) \
             .filter(Genre.slug == genre)
    if format_:
        q = q.join(release_formats, Release.id == release_formats.c.release_id) \
             .join(Format, Format.id == release_formats.c.format_id) \
             .filter(or_(Format.slug == format_, Format.name == format_))
    if ships_from:
        q = q.filter(Listing.shipping_from == ships_from)
    if year:
        q = q.filter(Release.year == year)
    if price_min is not None:
        q = q.filter(Listing.price >= price_min)
    if price_max is not None:
        q = q.filter(Listing.price < price_max)
    if text:
        terms = [t for t in re.split(r"\s+", text) if t]
        for term in terms:
            q = q.filter(or_(Release.title.ilike(f"%{term}%"), Release.artist_credit.ilike(f"%{term}%"),
                             Release.credited_artists.any(Artist.name.ilike(f"%{term}%"))))
    facets = marketplace_facets(q)
    if sort == "price_desc":
        q = q.order_by(Listing.price.desc())
    elif sort == "newest":
        q = q.order_by(Listing.posted_at.desc())
    else:
        q = q.order_by(Listing.price.asc())
    pag = paginate(q.distinct(), page, 30)
    genres = Genre.query.order_by(Genre.name).all()
    formats = Format.query.order_by(Format.name).all()
    selected = {"currency": currency, "media": media, "genre": genre, "format": format_,
                "ships_from": ships_from, "year": year, "price_min": price_min, "price_max": price_max, "q": text}
    return render_template("marketplace.html", pag=pag, sort=sort,
                           media=media, genre=genre, format_=format_, currency=currency,
                           currencies=CURRENCIES, grades=GRADES, genres=genres, formats=formats,
                           facets=facets, selected=selected)


PRICE_BUCKETS = [("Less than $5", None, 5.0), ("$5 - $10", 5.0, 10.0), ("$10 - $15", 10.0, 15.0),
                 ("$15 - $20", 15.0, 20.0), ("$20 - $40", 20.0, 40.0), ("More than $40", 40.0, None)]


def marketplace_facets(base, limit=8):
    """Facet counts inside the current marketplace result set (live sidebar)."""
    ids = db.session.query(base.order_by(None).with_entities(Listing.id).distinct().subquery().c.id)
    listing_release = db.session.query(Listing.release_id).filter(Listing.id.in_(ids))

    def rows(query):
        return [{"name": name, "count": count} for name, count in query.all()]

    ships = rows(db.session.query(Listing.shipping_from, func.count(Listing.id))
                 .filter(Listing.id.in_(ids)).group_by(Listing.shipping_from)
                 .order_by(func.count(Listing.id).desc(), Listing.shipping_from).limit(limit))
    media = rows(db.session.query(Listing.media_condition, func.count(Listing.id))
                 .filter(Listing.id.in_(ids)).group_by(Listing.media_condition)
                 .order_by(func.count(Listing.id).desc()))
    formats = [{"name": name, "slug": slug, "count": count} for name, slug, count in
               db.session.query(Format.name, Format.slug, func.count(release_formats.c.release_id))
               .join(release_formats, Format.id == release_formats.c.format_id)
               .filter(release_formats.c.release_id.in_(listing_release))
               .group_by(Format.id).order_by(func.count(release_formats.c.release_id).desc()).limit(limit).all()]
    genres = [{"name": name, "slug": slug, "count": count} for name, slug, count in
              db.session.query(Genre.name, Genre.slug, func.count(release_genres.c.release_id))
              .join(release_genres, Genre.id == release_genres.c.genre_id)
              .filter(release_genres.c.release_id.in_(listing_release))
              .group_by(Genre.id).order_by(func.count(release_genres.c.release_id).desc()).limit(limit).all()]
    years = rows(db.session.query(Release.year, func.count(Listing.id))
                 .join(Listing, Listing.release_id == Release.id)
                 .filter(Listing.id.in_(ids), Release.year.isnot(None))
                 .group_by(Release.year).order_by(func.count(Listing.id).desc(), Release.year.desc()).limit(limit))
    prices = []
    for label, low, high in PRICE_BUCKETS:
        bucket = base.order_by(None)
        if low is not None:
            bucket = bucket.filter(Listing.price >= low)
        if high is not None:
            bucket = bucket.filter(Listing.price < high)
        prices.append({"name": label, "count": bucket.with_entities(Listing.id).distinct().count(),
                       "min": low, "max": high})
    return {"ships_from": ships, "media": media, "format": formats, "genre": genres, "year": years,
            "price": prices}


@app.route("/shop/mywants")
@login_required
def shop_my_wants():
    """Live: /shop/mywants — marketplace listings for releases on the user's wantlist."""
    page = request.args.get("page", 1, type=int)
    currency = request.args.get("currency", "USD")
    if currency not in CURRENCIES:
        currency = "USD"
    q = Listing.query.filter_by(status="For Sale", currency=currency).join(Release) \
        .join(WantlistItem, WantlistItem.release_id == Release.id) \
        .filter(WantlistItem.user_id == current_user.id) \
        .order_by(Listing.price.asc())
    pag = paginate(q.distinct(), page, 30)
    return render_template("marketplace.html", pag=pag, sort="price_asc", media="", genre="",
                           format_="", currency=currency, currencies=CURRENCIES, grades=GRADES,
                           genres=Genre.query.order_by(Genre.name).all(),
                           formats=Format.query.order_by(Format.name).all(),
                           heading="Shop My Wants",
                           intro="Copies of releases on your wantlist that benchmark sellers currently offer.")


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
            price = Decimal(request.form.get("price", ""))
            if not price.is_finite() or not Decimal("0.01") <= price <= Decimal("99999999.99"):
                raise ValueError
            if price != price.quantize(Decimal("0.01")):
                raise ValueError
        except (InvalidOperation, ValueError):
            flash("Enter a price from 0.01 to 99,999,999.99 with at most two decimal places.", "error")
            return redirect(url_for("sell"))
        media = request.form.get("media_condition", "Very Good Plus (VG+)")
        sleeve = request.form.get("sleeve_condition", "Very Good Plus (VG+)")
        currency = request.form.get("currency", "USD")
        shipping_from = request.form.get("shipping_from", "").strip()
        if media not in GRADES or sleeve not in GRADES or currency not in CURRENCIES:
            flash("Choose a listed condition and currency.", "error")
            return redirect(url_for("sell"))
        if not shipping_from or len(shipping_from) > 80:
            flash("Enter a shipping location of at most 80 characters.", "error")
            return redirect(url_for("sell"))
        l = Listing(user_id=current_user.id, release_id=release.id,
                    media_condition=media, sleeve_condition=sleeve,
                    comments=request.form.get("comments", "")[:600],
                    price=float(price), currency=currency, shipping_from=shipping_from,
                    allow_offers=bool(request.form.get("allow_offers")))
        current_user.is_seller = True
        db.session.add(l)
        db.session.flush()
        release.num_for_sale = Listing.query.filter_by(release_id=release.id, status="For Sale").count()
        release.lowest_price = db.session.query(func.min(Listing.price)) \
                                          .filter(Listing.release_id == release.id,
                                                  Listing.status == "For Sale",
                                                  Listing.currency == "USD").scalar()
        db.session.commit()
        flash("Listing posted to the marketplace.", "success")
        return redirect(url_for("marketplace", currency=currency, sort="newest"))
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
    folder = request.args.get("folder", UNFILTERED_FOLDER)
    page = request.args.get("page", 1, type=int)
    q = u.collection_items.join(Release)
    if folder != UNFILTERED_FOLDER:
        q = q.filter(CollectionItem.folder == folder)
    q = q.order_by(CollectionItem.added_at.desc())
    pag = paginate(q, page, 25)
    return render_template("collection.html", u=u, pag=pag, folder=folder,
                           folders=COLLECTION_FOLDERS, unfiltered=UNFILTERED_FOLDER)


@app.route("/user/<username>/wantlist")
def user_wantlist(username):
    u = User.query.filter_by(username=username).first_or_404()
    page = request.args.get("page", 1, type=int)
    q = u.wantlist_items.join(Release).order_by(WantlistItem.added_at.desc())
    pag = paginate(q, page, 25)
    return render_template("wantlist.html", u=u, pag=pag)


@app.route("/user/<username>/lists")
def user_lists(username):
    u = User.query.filter_by(username=username).first_or_404()
    query = u.lists
    if not current_user.is_authenticated or current_user.id != u.id:
        query = query.filter_by(is_public=True)
    lists = query.order_by(List.created_at.desc()).all()
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
        return return_to_page(url_for("index"))
    folder = request.form.get("folder", "Uncategorized")
    media = request.form.get("media_condition", "Near Mint (NM or M-)")
    sleeve = request.form.get("sleeve_condition", "Near Mint (NM or M-)")
    if folder not in COLLECTION_FOLDERS or media not in GRADES or sleeve not in GRADES:
        flash("Choose a listed collection folder and condition.", "error")
        return return_to_page(url_for("release_detail", rid=r.discogs_id or r.id))
    existing = CollectionItem.query.filter_by(user_id=current_user.id, release_id=rid).first()
    if existing:
        flash("Already in your collection.", "info")
    else:
        c = CollectionItem(user_id=current_user.id, release_id=rid,
                           folder=folder, media_condition=media, sleeve_condition=sleeve,
                           notes=request.form.get("notes", "")[:280])
        db.session.add(c)
        r.have_count = (r.have_count or 0) + 1
        db.session.commit()
        flash("Added to your collection.", "success")
    return return_to_page(url_for("release_detail", rid=r.discogs_id or r.id))


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
    return return_to_page(url_for("user_collection", username=current_user.username))


@app.route("/wantlist/add", methods=["POST"])
@login_required
def wantlist_add():
    rid = request.form.get("release_id", type=int)
    r = Release.query.get(rid) if rid else None
    if not r:
        return return_to_page(url_for("index"))
    grade = request.form.get("min_grade", "Very Good Plus (VG+)")
    if grade not in GRADES:
        flash("Choose a listed minimum grade.", "error")
        return return_to_page(url_for("release_detail", rid=r.discogs_id or r.id))
    if WantlistItem.query.filter_by(user_id=current_user.id, release_id=rid).first():
        flash("Already in your wantlist.", "info")
    else:
        w = WantlistItem(user_id=current_user.id, release_id=rid,
                         min_grade=grade,
                         notes=request.form.get("notes", "")[:280])
        db.session.add(w)
        r.want_count = (r.want_count or 0) + 1
        db.session.commit()
        flash("Added to your wantlist.", "success")
    return return_to_page(url_for("release_detail", rid=r.discogs_id or r.id))


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
    return return_to_page(url_for("user_wantlist", username=current_user.username))


@app.route("/rate", methods=["POST"])
@login_required
def rate():
    rid = request.form.get("release_id", type=int)
    val = request.form.get("rating", type=int)
    if not (rid and val and 1 <= val <= 5):
        flash("Bad rating.", "error")
        return return_to_page(url_for("index"))
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
    return return_to_page(url_for("release_detail", rid=r.discogs_id or r.id))


@app.route("/review", methods=["POST"])
@login_required
def review_post():
    rid = request.form.get("release_id", type=int)
    body = request.form.get("body", "").strip()
    rating = request.form.get("rating", type=int)
    if not rid or not body:
        flash("Review body required.", "error")
        return return_to_page(url_for("index"))
    r = Release.query.get_or_404(rid)
    rv = Review(user_id=current_user.id, release_id=r.id, body=body[:4000],
                rating=rating if rating and 1 <= rating <= 5 else None)
    db.session.add(rv)
    db.session.commit()
    flash("Review posted.", "success")
    return redirect(url_for("release_detail", rid=r.discogs_id or r.id))


# ──────────────────────────────────────────────
# Forums
# ──────────────────────────────────────────────

@app.route("/forum")
def forum_index():
    forums = Forum.query.order_by(Forum.id).all()
    stats = {}
    for f in forums:
        thread_ids = db.session.query(Thread.id).filter(Thread.forum_id == f.id)
        stats[f.id] = {
            "threads": f.threads.count(),
            "posts": Post.query.filter(Post.thread_id.in_(thread_ids)).count(),
            "users": db.session.query(func.count(func.distinct(Post.user_id)))
                .filter(Post.thread_id.in_(thread_ids)).scalar() or 0,
        }
    return render_template("forum_index.html", forums=forums, stats=stats, tab="topics")


def render_thread_list(title, query, tab, intro=None):
    page = request.args.get("page", 1, type=int)
    pag = paginate(query, page, 25)
    return render_template("forum_threads.html", heading=title, pag=pag, tab=tab, intro=intro,
                           query_text=request.args.get("query", ""))


@app.route("/forum/recent")
def forum_recent():
    latest = db.session.query(Post.thread_id, func.max(Post.created_at).label("last")) \
        .group_by(Post.thread_id).subquery()
    query = Thread.query.outerjoin(latest, latest.c.thread_id == Thread.id) \
        .order_by(func.coalesce(latest.c.last, Thread.created_at).desc())
    return render_thread_list("Recent Thread Activity", query, "recent")


@app.route("/forum/search")
def forum_search():
    text = request.args.get("query", "").strip()
    query = Thread.query.order_by(Thread.created_at.desc())
    if text:
        matching = db.session.query(Post.thread_id).filter(Post.body.ilike(f"%{text}%"))
        query = query.filter(or_(Thread.title.ilike(f"%{text}%"), Thread.id.in_(matching)))
    return render_thread_list(f"Forum Search: {text}" if text else "Forum Search", query, "search")


@app.route("/forum/posted")
@login_required
def forum_posted():
    posted = db.session.query(Post.thread_id).filter(Post.user_id == current_user.id)
    query = Thread.query.filter(Thread.id.in_(posted)).order_by(Thread.created_at.desc())
    return render_thread_list("Threads You Posted In", query, "posted")


@app.route("/forum/started")
@login_required
def forum_started():
    query = Thread.query.filter(Thread.user_id == current_user.id).order_by(Thread.created_at.desc())
    return render_thread_list("Threads You Started", query, "started")


@app.route("/forum/saved")
@login_required
def forum_saved():
    return render_thread_list("Saved Threads", Thread.query.filter(False), "saved",
                              intro="Saving threads is not available in this offline mirror.")


@app.route("/forum/watched")
@login_required
def forum_watched():
    return render_thread_list("Watched Threads", Thread.query.filter(False), "watched",
                              intro="Thread notifications are not available in this offline mirror.")


@app.route("/forum/<slug>")
def forum_view(slug):
    f = Forum.query.filter_by(slug=slug).first_or_404()
    page = request.args.get("page", 1, type=int)
    q = f.threads.order_by(Thread.pinned.desc(), Thread.created_at.desc())
    pag = paginate(q, page, 25)
    return render_template("forum.html", f=f, pag=pag)


@app.route("/thread/<int:tid>")
def thread_view(tid):
    t = Thread.query.get_or_404(tid)
    posts = t.posts.order_by(Post.created_at.asc()).all()
    poster_ids = {p.user_id for p in posts}
    post_counts = dict(db.session.query(Post.user_id, func.count(Post.id))
                       .filter(Post.user_id.in_(poster_ids)).group_by(Post.user_id).all()) if poster_ids else {}
    return render_template("thread.html", t=t, posts=posts, post_counts=post_counts)


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
        if u and len(pw.encode("utf-8")) <= 72 and bcrypt.check_password_hash(u.password_hash, pw):
            login_user(u, remember=bool(request.form.get("remember")))
            flash(f"Welcome back, {u.username}.", "success")
            return redirect(local_return(request.args.get("next"), url_for("index")))
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
        valid_email = re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
        if not (re.fullmatch(r"[\w.-]{3,40}", username) and valid_email and len(email) <= 160
                and len(pw) >= 6 and len(pw.encode("utf-8")) <= 72):
            flash("Use a 3–40 character username (letters, numbers, dots, dashes or underscores), a valid email, and a password of at least 6 characters and at most 72 UTF-8 bytes.", "error")
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


@app.route("/logout", methods=["POST"])
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
# Navigation destinations mirrored from the live site
# ──────────────────────────────────────────────

@app.route("/search/advanced")
def search_advanced():
    return render_template("search_advanced.html",
                           genres=Genre.query.order_by(Genre.name).all(),
                           styles=Style.query.order_by(Style.name).all(),
                           formats=Format.query.order_by(Format.name).all())


@app.route("/digs")
def digs():
    essentials = Release.query.filter(Release.rating_count >= 1) \
        .order_by(Release.avg_rating.desc(), Release.rating_count.desc(), Release.id).limit(8).all()
    return render_template("digs.html", essentials=essentials,
                           most_valuable=most_valuable_releases(8),
                           collecting=most_collected_releases(8))


@app.route("/group")
def groups():
    return render_template("group.html", forums=Forum.query.order_by(Forum.id).all())


def community_rows():
    rows = []
    for user in User.query.order_by(User.id).all():
        counts = {
            "reviews": Review.query.filter_by(user_id=user.id).count(),
            "lists": List.query.filter_by(user_id=user.id, is_public=True).count(),
            "listings": Listing.query.filter_by(user_id=user.id, status="For Sale").count(),
            "collection": CollectionItem.query.filter_by(user_id=user.id).count(),
            "wantlist": WantlistItem.query.filter_by(user_id=user.id).count(),
        }
        counts["total"] = sum(counts.values())
        counts["user"] = user
        rows.append(counts)
    rows.sort(key=lambda row: (-row["total"], row["user"].username))
    return rows


@app.route("/stats/contributors")
def contributors():
    return render_template("community_stats.html", heading="Discography Contributors",
                           intro="Benchmark accounts ranked by their activity in this snapshot.",
                           rows=community_rows())


@app.route("/leaderboard")
def leaderboard():
    return render_template("community_stats.html", heading="Monthly Leaderboard",
                           intro="Ranking of benchmark accounts by contributions recorded in this snapshot.",
                           rows=community_rows()[:25])


@app.route("/selling/resources")
def selling_resources():
    return render_template("selling_resources.html")


INFO_PAGES = {
    "/about/get-started": {
        "title": "Get Started",
        "lead": "Discogs is a user-built database of music releases and a marketplace for buying and selling them.",
        "body": ["Create a free account to catalogue your collection, keep a wantlist, build lists, rate and review releases, post in the forum and list items for sale.",
                 "Every feature works locally in this offline mirror; nothing is sent to discogs.com."],
        "links": [("Create an account", "/register"), ("Explore the database", "/search"), ("Browse the Marketplace", "/marketplace")],
    },
    "/about/about": {
        "title": "What is Discogs?",
        "lead": "Discogs is the largest crowd-sourced music database and marketplace.",
        "body": ["This mirror contains verified release metadata and cover images captured from Discogs, plus synthetic benchmark users, collections, wantlists, lists, reviews, listings and forum posts."],
        "links": [("Explore Discography", "/explore"), ("Community forum", "/forum")],
    },
    "/about/features/discography": {
        "title": "Discography",
        "lead": "Every release page records the label, catalog number, format, country, year, genres, styles, tracklist, credits and identifiers.",
        "body": ["Use search or the Explore pages to browse by genre, style or format, and open a release to read its full details."],
        "links": [("Explore Discography", "/explore"), ("Advanced Search", "/search/advanced")],
    },
    "/about/features/music-marketplace": {
        "title": "Marketplace",
        "lead": "Buy and sell physical music with sellers around the world.",
        "body": ["Marketplace listings in this mirror come from benchmark seller accounts. Filter by format, media condition, genre and currency, and sort by price or listing date."],
        "links": [("Browse the Marketplace", "/marketplace"), ("List Item For Sale", "/sell")],
    },
    "/about/features/collection": {
        "title": "Collection",
        "lead": "Keep track of the records you own.",
        "body": ["Add a release to your collection from its release page, choose a folder and grade, and review everything from your profile."],
        "links": [("Log in", "/login")],
    },
    "/about/features/wantlist": {
        "title": "Wantlist",
        "lead": "Track the releases you are looking for.",
        "body": ["Add a release to your wantlist with a minimum grade, then use Shop My Wants to find copies offered by sellers."],
        "links": [("Shop My Wants", "/shop/mywants")],
    },
    "/about/features/sales-history": {
        "title": "Statistics",
        "lead": "Marketplace sales history and price statistics.",
        "body": ["Sales history is not part of this snapshot. Current asking prices are shown on each release page and in the Marketplace."],
        "links": [("Browse the Marketplace", "/marketplace")],
    },
    "/about/careers": {
        "title": "Careers",
        "lead": "Discogs job openings.",
        "body": ["No job listings are included in this offline mirror."],
        "links": [],
    },
    "/about/get-involved/community-advisory": {
        "title": "Community Advisory",
        "lead": "The Community Advisory Turntable gathers contributor feedback on database and marketplace changes.",
        "body": ["In this mirror, community discussion happens in the forum."],
        "links": [("Community forum", "/forum")],
    },
    "/about/trust": {
        "title": "Trust Center",
        "lead": "How Discogs protects buyers, sellers and contributors.",
        "body": ["This offline mirror stores no payment details and performs no real transactions."],
        "links": [("Community Guidelines", "/guidelines/community")],
    },
    "/about/app": {
        "title": "Discogs App",
        "lead": "Take your collection anywhere on the Discogs App.",
        "body": ["App store links are disabled in this offline mirror. Use the website to manage your collection, wantlist and lists."],
        "links": [("Log in", "/login")],
    },
    "/developers": {
        "title": "Developer API",
        "lead": "Discogs offers a REST API for release, artist, label and marketplace data.",
        "body": ["The API is not exposed by this offline mirror."],
        "links": [],
    },
    "/help": {
        "title": "Help Center",
        "lead": "Answers to common questions about the database, marketplace and your account.",
        "body": ["Questions about this mirror can be posted in the Help & Feedback forum."],
        "links": [("Help & Feedback forum", "/forum/help"), ("Seller Resource Center", "/selling/resources"),
                  ("Submission Guidelines", "/guidelines/submissions")],
    },
    "/status": {
        "title": "System Status",
        "lead": "All services on this offline mirror are operating normally.",
        "body": [],
        "links": [],
    },
    "/release/add": {
        "title": "Submit a Release",
        "lead": "Contributors add new releases to the database through the submission form.",
        "body": ["Submissions are disabled in this offline mirror because the catalog is a verified snapshot. Existing releases can still be rated, reviewed, collected and listed for sale."],
        "links": [("Submission Guidelines", "/guidelines/submissions"), ("Explore Discography", "/explore")],
    },
    "/guidelines/submissions": {
        "title": "Submission Guidelines",
        "lead": "Overview of the rules for adding and editing releases.",
        "body": ["Enter data exactly as it appears on the release, keep artist and label names consistent with existing entries, list every format detail, and cite catalog numbers and barcodes from the physical item.",
                 "This mirror is read-only for submissions; the guidelines are provided for reference."],
        "links": [("Submit a Release", "/release/add")],
    },
    "/guidelines/community": {
        "title": "Community Guidelines",
        "lead": "Be respectful, stay on topic and keep the database accurate.",
        "body": ["Forum posts, reviews and list comments should be civil and relevant to music. Marketplace disputes belong in the Marketplace forum."],
        "links": [("Community forum", "/forum")],
    },
    "/legal/cookie-settings": {
        "title": "Cookie Settings",
        "lead": "This offline mirror sets only the session cookie needed to keep you signed in.",
        "body": ["No analytics or advertising cookies are used."],
        "links": [("Cookie Policy", "/legal/cookie-policy")],
    },
    "/legal/cookie-policy": {
        "title": "Cookie and Internet Advertising Policy",
        "lead": "How cookies are used on this site.",
        "body": ["Only a session cookie is used, and it never leaves this mirror."],
        "links": [],
    },
    "/legal/terms-of-service": {
        "title": "Terms of Service",
        "lead": "Terms for using the database, marketplace and community features.",
        "body": ["This mirror is a benchmark environment; listings are synthetic and no purchases are executed."],
        "links": [],
    },
    "/legal/privacy-policy": {
        "title": "Privacy Policy",
        "lead": "What personal data is processed and why.",
        "body": ["Account details entered here stay inside this offline environment and are reset with the benchmark database."],
        "links": [],
    },
    "/legal/california-privacy-notice": {
        "title": "California Privacy Notice",
        "lead": "Additional privacy information for California residents.",
        "body": ["No personal data is sold or shared by this offline mirror."],
        "links": [],
    },
    "/legal/accessibility-statement": {
        "title": "Accessibility Statement",
        "lead": "Discogs aims to make its site usable with assistive technologies.",
        "body": ["Navigation menus, forms and carousels in this mirror are keyboard accessible and labelled for screen readers."],
        "links": [],
    },
    "/legal/impressum": {
        "title": "Impressum",
        "lead": "Legal notice.",
        "body": ["This is an offline research mirror of Discogs used for agent benchmarking; it is not operated by Discogs."],
        "links": [],
    },
}


def info_page():
    page = INFO_PAGES.get(request.path)
    if page is None:
        abort(404)
    return render_template("info.html", page=page)


for _index, _path in enumerate(INFO_PAGES):
    app.add_url_rule(_path, endpoint=f"info_page_{_index}", view_func=info_page)


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
    if os.environ.get("DISCOGS_SKIP_SEED") != "1":
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
