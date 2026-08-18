#!/usr/bin/env python3
"""Bandcamp mirror - Flask app with music discovery, merch, and fan flows."""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta

from flask import abort, flash, redirect, render_template, request, url_for, Flask
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "bandcamp.db")
MIRROR_REFERENCE_NOW = datetime(2026, 5, 1, 12, 0, 0)
STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "for",
    "in",
    "on",
    "with",
    "to",
    "by",
    "at",
    "from",
    "my",
    "your",
    "their",
    "is",
    "it",
    "this",
    "that",
    "all",
}

os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__, instance_path=INSTANCE_DIR)
app.config["SECRET_KEY"] = "webharbor-bandcamp-dev-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log in to access your Bandcamp fan account."
login_manager.login_message_category = "info"

album_tags = db.Table(
    "album_tags",
    db.Column("album_id", db.Integer, db.ForeignKey("albums.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.Text, default="")
    city = db.Column(db.String(80), default="")
    country = db.Column(db.String(80), default="United States")
    address_line1 = db.Column(db.String(200), default="")
    postal_code = db.Column(db.String(30), default="")
    favorite_format = db.Column(db.String(40), default="digital")
    favorite_scene_id = db.Column(db.Integer, db.ForeignKey("scenes.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    favorite_scene = db.relationship("Scene", foreign_keys=[favorite_scene_id])
    cart_items = db.relationship("CartItem", backref="user", cascade="all, delete-orphan", lazy=True)
    wishlist_items = db.relationship("WishlistItem", backref="user", cascade="all, delete-orphan", lazy=True)
    orders = db.relationship("Order", backref="user", cascade="all, delete-orphan", lazy=True)
    collection_items = db.relationship(
        "FanCollectionItem", backref="user", cascade="all, delete-orphan", lazy=True
    )
    comments = db.relationship("FanComment", backref="user", cascade="all, delete-orphan", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def first_name(self) -> str:
        return self.display_name.split(" ")[0]


class Genre(db.Model):
    __tablename__ = "genres"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    accent_color = db.Column(db.String(20), default="#0f5ea8")

    artists = db.relationship("Artist", backref="primary_genre", lazy=True)
    albums = db.relationship("Album", backref="primary_genre", lazy=True)


class Scene(db.Model):
    __tablename__ = "scenes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    country = db.Column(db.String(80), default="")
    description = db.Column(db.Text, default="")

    artists = db.relationship("Artist", backref="scene", lazy=True)
    albums = db.relationship("Album", backref="scene", lazy=True)


class Label(db.Model):
    __tablename__ = "labels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    location = db.Column(db.String(120), default="")
    description = db.Column(db.Text, default="")

    artists = db.relationship("Artist", backref="label", lazy=True)
    albums = db.relationship("Album", backref="label", lazy=True)


class Artist(db.Model):
    __tablename__ = "artists"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    location = db.Column(db.String(120), default="")
    bio = db.Column(db.Text, default="")
    headline = db.Column(db.String(180), default="")
    formed_year = db.Column(db.Integer, default=2018)
    follow_count = db.Column(db.Integer, default=0)
    avatar_image = db.Column(db.String(255), default="")
    hero_image = db.Column(db.String(255), default="")
    scene_id = db.Column(db.Integer, db.ForeignKey("scenes.id"), nullable=False)
    label_id = db.Column(db.Integer, db.ForeignKey("labels.id"), nullable=False)
    primary_genre_id = db.Column(db.Integer, db.ForeignKey("genres.id"), nullable=False)

    albums = db.relationship("Album", backref="artist", cascade="all, delete-orphan", lazy=True)
    merch_items = db.relationship("MerchItem", backref="artist", cascade="all, delete-orphan", lazy=True)


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)

    albums = db.relationship("Album", secondary=album_tags, back_populates="tags", lazy=True)


class Album(db.Model):
    __tablename__ = "albums"

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id"), nullable=False)
    label_id = db.Column(db.Integer, db.ForeignKey("labels.id"), nullable=False)
    primary_genre_id = db.Column(db.Integer, db.ForeignKey("genres.id"), nullable=False)
    scene_id = db.Column(db.Integer, db.ForeignKey("scenes.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    story = db.Column(db.Text, default="")
    cover_image = db.Column(db.String(255), default="")
    header_image = db.Column(db.String(255), default="")
    price = db.Column(db.Float, default=8.0)
    release_date = db.Column(db.Date, nullable=False)
    track_count = db.Column(db.Integer, default=0)
    duration_seconds = db.Column(db.Integer, default=0)
    fan_count = db.Column(db.Integer, default=0)
    catalog_no = db.Column(db.String(40), default="")
    is_featured = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=False)
    is_editorial = db.Column(db.Boolean, default=False)

    tracks = db.relationship("Track", backref="album", cascade="all, delete-orphan", lazy=True)
    variants = db.relationship("FormatVariant", backref="album", cascade="all, delete-orphan", lazy=True)
    comments = db.relationship("FanComment", backref="album", cascade="all, delete-orphan", lazy=True)
    merch_items = db.relationship("MerchItem", backref="album", lazy=True)
    tags = db.relationship("Tag", secondary=album_tags, back_populates="albums", lazy=True)

    def price_from(self) -> float:
        prices = [variant.price for variant in self.variants]
        return min(prices) if prices else self.price

    def format_kinds(self) -> list[str]:
        return [variant.kind for variant in self.variants]

    def variant_for_kind(self, kind: str) -> "FormatVariant | None":
        for variant in self.variants:
            if variant.kind == kind:
                return variant
        return None

    def primary_tag_names(self) -> list[str]:
        return [tag.name for tag in self.tags[:4]]

    def focus_track(self) -> "Track | None":
        for track in self.tracks:
            if track.is_focus_track:
                return track
        return self.tracks[0] if self.tracks else None


class Track(db.Model):
    __tablename__ = "tracks"

    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    track_number = db.Column(db.Integer, nullable=False)
    duration_seconds = db.Column(db.Integer, default=180)
    preview_hook = db.Column(db.String(255), default="")
    lyrics_excerpt = db.Column(db.Text, default="")
    is_focus_track = db.Column(db.Boolean, default=False)

    comments = db.relationship("FanComment", backref="track", lazy=True)


class MerchItem(db.Model):
    __tablename__ = "merch_items"

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id"), nullable=False)
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id"))
    title = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    item_type = db.Column(db.String(50), default="shirt")
    description = db.Column(db.Text, default="")
    short_blurb = db.Column(db.String(200), default="")
    image = db.Column(db.String(255), default="")
    price = db.Column(db.Float, default=20.0)
    inventory = db.Column(db.Integer, default=100)
    release_date = db.Column(db.Date, nullable=False)
    is_featured = db.Column(db.Boolean, default=False)

    variants = db.relationship("FormatVariant", backref="merch_item", cascade="all, delete-orphan", lazy=True)


class FormatVariant(db.Model):
    __tablename__ = "format_variants"

    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id"))
    merch_item_id = db.Column(db.Integer, db.ForeignKey("merch_items.id"))
    kind = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    option_a = db.Column(db.String(80), default="")
    option_b = db.Column(db.String(80), default="")
    price = db.Column(db.Float, default=0.0)
    inventory = db.Column(db.Integer, default=9999)
    sku = db.Column(db.String(80), unique=True, nullable=False)
    shipping_note = db.Column(db.String(160), default="")
    edition_note = db.Column(db.String(200), default="")
    is_default = db.Column(db.Boolean, default=False)

    def label_text(self) -> str:
        extras = [piece for piece in [self.option_a, self.option_b] if piece]
        return f"{self.name} / {' / '.join(extras)}" if extras else self.name


class FanComment(db.Model):
    __tablename__ = "fan_comments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id"))
    track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"))
    headline = db.Column(db.String(140), default="")
    body = db.Column(db.Text, default="")
    rating = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WishlistItem(db.Model):
    __tablename__ = "wishlist_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id"))
    merch_item_id = db.Column(db.Integer, db.ForeignKey("merch_items.id"))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    album = db.relationship("Album")
    merch_item = db.relationship("MerchItem")

    def title(self) -> str:
        return self.album.title if self.album else self.merch_item.title

    def image_path(self) -> str:
        return self.album.cover_image if self.album else self.merch_item.image

    def artist_name(self) -> str:
        return self.album.artist.name if self.album else self.merch_item.artist.name


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id"))
    merch_item_id = db.Column(db.Integer, db.ForeignKey("merch_items.id"))
    format_variant_id = db.Column(db.Integer, db.ForeignKey("format_variants.id"))
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    album = db.relationship("Album")
    merch_item = db.relationship("MerchItem")
    format_variant = db.relationship("FormatVariant")

    def subject(self) -> Album | MerchItem:
        return self.album if self.album else self.merch_item

    def title(self) -> str:
        return self.subject().title

    def artist_name(self) -> str:
        return self.subject().artist.name

    def image_path(self) -> str:
        target = self.subject()
        return target.cover_image if isinstance(target, Album) else target.image

    def variant_label(self) -> str:
        return self.format_variant.label_text() if self.format_variant else "Standard"

    def unit_price(self) -> float:
        return self.format_variant.price if self.format_variant else self.subject().price

    def line_total(self) -> float:
        return self.unit_price() * self.quantity


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    order_number = db.Column(db.String(60), unique=True, nullable=False)
    status = db.Column(db.String(40), default="completed")
    subtotal = db.Column(db.Float, default=0.0)
    shipping = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    shipping_name = db.Column(db.String(140), default="")
    shipping_line1 = db.Column(db.String(200), default="")
    shipping_city = db.Column(db.String(120), default="")
    shipping_country = db.Column(db.String(120), default="")
    payment_label = db.Column(db.String(120), default="")
    note = db.Column(db.String(240), default="")
    placed_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan", lazy=True)

    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id"))
    merch_item_id = db.Column(db.Integer, db.ForeignKey("merch_items.id"))
    format_variant_id = db.Column(db.Integer, db.ForeignKey("format_variants.id"))
    title = db.Column(db.String(200), nullable=False)
    artist_name = db.Column(db.String(140), default="")
    image_path = db.Column(db.String(255), default="")
    variant_label = db.Column(db.String(160), default="")
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0.0)

    album = db.relationship("Album")
    merch_item = db.relationship("MerchItem")
    format_variant = db.relationship("FormatVariant")

    def line_total(self) -> float:
        return self.quantity * self.unit_price


class FanCollectionItem(db.Model):
    __tablename__ = "fan_collection_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id"), nullable=False)
    format_variant_id = db.Column(db.Integer, db.ForeignKey("format_variants.id"))
    favorite_track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"))
    acquired_via = db.Column(db.String(80), default="purchase")
    notes = db.Column(db.String(240), default="")
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    album = db.relationship("Album")
    format_variant = db.relationship("FormatVariant")
    favorite_track = db.relationship("Track")


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return re.sub(r"-{2,}", "-", value).strip("-")


def safe_next_url(raw: str | None) -> str | None:
    if not raw or raw.startswith("//") or not raw.startswith("/"):
        return None
    return raw


def money(amount: float) -> str:
    return f"${amount:,.2f}"


def compact_date(value: date | datetime) -> str:
    if isinstance(value, datetime):
        return value.strftime("%b %d, %Y")
    return value.strftime("%b %d, %Y")


def long_date(value: date | datetime) -> str:
    if isinstance(value, datetime):
        return value.strftime("%B %d, %Y")
    return value.strftime("%B %d, %Y")


def duration_label(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.split(r"[^a-z0-9]+", (text or "").lower())
        if token and token not in STOP_WORDS and len(token) > 1
    ]


def scored_search(query: str, items: list, text_builder) -> list:
    terms = tokenize(query)
    if not terms:
        return items
    lowered_query = query.lower().strip()
    scored: list[tuple[int, object]] = []
    for item in items:
        haystack = text_builder(item).lower()
        score = 10 if lowered_query and lowered_query in haystack else 0
        for term in terms:
            if re.search(rf"\b{re.escape(term)}\b", haystack):
                score += 4
            elif term in haystack:
                score += 2
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


def album_blob(album: Album) -> str:
    return " ".join(
        [
            album.title,
            album.artist.name,
            album.primary_genre.name,
            album.scene.name,
            album.label.name,
            " ".join(tag.name for tag in album.tags),
            " ".join(track.title for track in album.tracks[:3]),
            album.description,
            album.story,
        ]
    )


def artist_blob(artist: Artist) -> str:
    return " ".join([artist.name, artist.primary_genre.name, artist.location, artist.bio, artist.label.name])


def track_blob(track: Track) -> str:
    return " ".join(
        [track.title, track.album.title, track.album.artist.name, track.album.primary_genre.name, track.preview_hook]
    )


def merch_blob(merch: MerchItem) -> str:
    return " ".join(
        [
            merch.title,
            merch.artist.name,
            merch.item_type,
            merch.short_blurb,
            merch.description,
            " ".join(variant.label_text() for variant in merch.variants),
        ]
    )


def get_cart_items() -> list[CartItem]:
    if not current_user.is_authenticated:
        return []
    return (
        CartItem.query.filter_by(user_id=current_user.id)
        .order_by(CartItem.added_at.desc(), CartItem.id.desc())
        .all()
    )


def cart_summary(items: list[CartItem]) -> dict[str, float]:
    subtotal = round(sum(item.line_total() for item in items), 2)
    shipping = 0.0 if subtotal >= 45 or subtotal == 0 else 6.5
    tax = round(subtotal * 0.0825, 2)
    total = round(subtotal + shipping + tax, 2)
    return {"subtotal": subtotal, "shipping": shipping, "tax": tax, "total": total}


def latest_support_items(limit: int = 8) -> list[OrderItem]:
    return (
        OrderItem.query.join(Order)
        .order_by(Order.placed_at.desc(), OrderItem.id.desc())
        .limit(limit)
        .all()
    )


def generate_order_number() -> str:
    next_id = (db.session.query(db.func.count(Order.id)).scalar() or 0) + 1
    return f"BC-20260501-{next_id:04d}"


def add_collection_item(user: User, album: Album, variant: FormatVariant | None, note: str = "") -> None:
    existing = FanCollectionItem.query.filter_by(user_id=user.id, album_id=album.id).first()
    if existing:
        return
    focus_track = album.focus_track()
    db.session.add(
        FanCollectionItem(
            user_id=user.id,
            album_id=album.id,
            format_variant_id=variant.id if variant else None,
            favorite_track_id=focus_track.id if focus_track else None,
            acquired_via="purchase",
            notes=note,
            added_at=MIRROR_REFERENCE_NOW,
        )
    )


@app.template_filter("money")
def money_filter(value: float) -> str:
    return money(value)


@app.template_filter("duration")
def duration_filter(value: int) -> str:
    return duration_label(value)


@app.template_filter("longdate")
def longdate_filter(value: date | datetime) -> str:
    return long_date(value)


@app.template_filter("compactdate")
def compactdate_filter(value: date | datetime) -> str:
    return compact_date(value)


@app.context_processor
def inject_globals():
    genres = Genre.query.order_by(Genre.name.asc()).limit(12).all()
    format_nav = [
        ("all", "All"),
        ("digital", "Digital"),
        ("vinyl", "Vinyl"),
        ("cassette", "Cassette"),
        ("cd", "CD"),
        ("shirt", "Merch"),
    ]
    if current_user.is_authenticated:
        cart_count = sum(item.quantity for item in get_cart_items())
        wishlist_count = WishlistItem.query.filter_by(user_id=current_user.id).count()
    else:
        cart_count = 0
        wishlist_count = 0
    return {
        "genre_nav": genres,
        "format_nav": format_nav,
        "cart_count": cart_count,
        "wishlist_count": wishlist_count,
    }


@app.route("/")
def index():
    return render_template(
        "index.html",
        featured_albums=Album.query.filter_by(is_featured=True).order_by(Album.release_date.desc()).limit(6).all(),
        new_releases=Album.query.order_by(Album.release_date.desc()).limit(10).all(),
        editorial=Album.query.filter_by(is_editorial=True).order_by(Album.release_date.desc()).limit(4).all(),
        featured_merch=MerchItem.query.filter_by(is_featured=True).order_by(MerchItem.release_date.desc()).limit(8).all(),
        scenes=Scene.query.order_by(Scene.name.asc()).limit(9).all(),
        support_items=latest_support_items(9),
        support_total=round(sum(order.total for order in Order.query.all()), 2),
    )


@app.route("/discover")
def discover():
    selected_genre = request.args.get("genre", "all")
    selected_scene = request.args.get("scene", "all")
    selected_format = request.args.get("format", "all")
    selected_tag = request.args.get("tag", "all")
    sort = request.args.get("sort", "new")
    query = request.args.get("q", "").strip()
    view = request.args.get("view", "albums")

    genres = Genre.query.order_by(Genre.name.asc()).all()
    scenes = Scene.query.order_by(Scene.name.asc()).all()
    tags = Tag.query.order_by(Tag.name.asc()).limit(24).all()
    albums = Album.query.order_by(Album.release_date.desc()).all()
    merch = MerchItem.query.order_by(MerchItem.release_date.desc()).all()

    if selected_genre != "all":
        albums = [album for album in albums if album.primary_genre.slug == selected_genre]
        merch = [item for item in merch if item.artist.primary_genre.slug == selected_genre]
    if selected_scene != "all":
        albums = [album for album in albums if album.scene.slug == selected_scene]
        merch = [item for item in merch if item.artist.scene.slug == selected_scene]
    if selected_tag != "all":
        albums = [album for album in albums if any(tag.slug == selected_tag for tag in album.tags)]
    if selected_format != "all":
        albums = [album for album in albums if any(variant.kind == selected_format for variant in album.variants)]
        if selected_format in {"shirt", "hoodie", "poster", "tote", "slipmat", "pin", "zine"}:
            merch = [item for item in merch if item.item_type == selected_format]

    if query:
        albums = scored_search(query, albums, album_blob)
        merch = scored_search(query, merch, merch_blob)
    else:
        if sort == "price-low":
            albums.sort(key=lambda album: (album.price_from(), album.release_date))
            merch.sort(key=lambda item: item.price)
        elif sort == "price-high":
            albums.sort(key=lambda album: (album.price_from(), album.release_date), reverse=True)
            merch.sort(key=lambda item: item.price, reverse=True)
        elif sort == "popular":
            albums.sort(key=lambda album: (album.fan_count, album.release_date), reverse=True)
            merch.sort(key=lambda item: item.inventory)
        else:
            albums.sort(key=lambda album: (album.release_date, album.fan_count), reverse=True)
            merch.sort(key=lambda item: item.release_date, reverse=True)

    return render_template(
        "discover.html",
        albums=albums[:30],
        merch_items=merch[:30],
        featured_album=albums[0] if albums else None,
        genres=genres,
        scenes=scenes,
        tags=tags,
        selected_genre=selected_genre,
        selected_scene=selected_scene,
        selected_format=selected_format,
        selected_tag=selected_tag,
        sort=sort,
        query=query,
        view=view,
    )


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    artists = scored_search(query, Artist.query.all(), artist_blob)[:8] if query else []
    albums = scored_search(query, Album.query.all(), album_blob)[:12] if query else []
    tracks = scored_search(query, Track.query.all(), track_blob)[:10] if query else []
    merch_items = scored_search(query, MerchItem.query.all(), merch_blob)[:8] if query else []
    return render_template(
        "search.html",
        query=query,
        artists=artists,
        albums=albums,
        tracks=tracks,
        merch_items=merch_items,
    )


@app.route("/artist/<slug>")
def artist_page(slug: str):
    artist = Artist.query.filter_by(slug=slug).first_or_404()
    albums = Album.query.filter_by(artist_id=artist.id).order_by(Album.release_date.desc()).all()
    merch_items = MerchItem.query.filter_by(artist_id=artist.id).order_by(MerchItem.release_date.desc()).all()
    collection_count = FanCollectionItem.query.join(Album).filter(Album.artist_id == artist.id).count()
    return render_template(
        "artist.html",
        artist=artist,
        albums=albums,
        merch_items=merch_items,
        collection_count=collection_count,
    )


@app.route("/label/<slug>")
def label_page(slug: str):
    label = Label.query.filter_by(slug=slug).first_or_404()
    return render_template(
        "label.html",
        label=label,
        artists=Artist.query.filter_by(label_id=label.id).order_by(Artist.name.asc()).all(),
        albums=Album.query.filter_by(label_id=label.id).order_by(Album.release_date.desc()).all(),
    )


@app.route("/scene/<slug>")
def scene_page(slug: str):
    scene = Scene.query.filter_by(slug=slug).first_or_404()
    return render_template(
        "scene.html",
        scene=scene,
        artists=Artist.query.filter_by(scene_id=scene.id).order_by(Artist.name.asc()).all(),
        albums=Album.query.filter_by(scene_id=scene.id).order_by(Album.release_date.desc()).all(),
    )


@app.route("/album/<slug>")
def album_page(slug: str):
    album = Album.query.filter_by(slug=slug).first_or_404()
    related_merch = MerchItem.query.filter_by(artist_id=album.artist_id).order_by(MerchItem.release_date.desc()).limit(4).all()
    recommended = (
        Album.query.filter(
            Album.primary_genre_id == album.primary_genre_id,
            Album.artist_id != album.artist_id,
            Album.id != album.id,
        )
        .order_by(Album.release_date.desc())
        .limit(4)
        .all()
    )
    in_wishlist = current_user.is_authenticated and (
        WishlistItem.query.filter_by(user_id=current_user.id, album_id=album.id).first() is not None
    )
    return render_template(
        "album.html",
        album=album,
        related_merch=related_merch,
        recommended=recommended,
        in_wishlist=in_wishlist,
    )


@app.route("/track/<slug>")
def track_page(slug: str):
    track = Track.query.filter_by(slug=slug).first_or_404()
    return render_template("track.html", track=track, album=track.album)


@app.route("/merch/<slug>")
def merch_page(slug: str):
    merch = MerchItem.query.filter_by(slug=slug).first_or_404()
    related = (
        MerchItem.query.filter(MerchItem.artist_id == merch.artist_id, MerchItem.id != merch.id)
        .order_by(MerchItem.release_date.desc())
        .limit(4)
        .all()
    )
    in_wishlist = current_user.is_authenticated and (
        WishlistItem.query.filter_by(user_id=current_user.id, merch_item_id=merch.id).first() is not None
    )
    return render_template("merch.html", merch=merch, related=related, in_wishlist=in_wishlist)


@app.route("/compare/releases")
def compare_releases():
    featured = Album.query.filter_by(is_featured=True).order_by(Album.release_date.desc()).limit(10).all()
    left_slug = request.args.get("left")
    right_slug = request.args.get("right")
    left = Album.query.filter_by(slug=left_slug).first() if left_slug else (featured[0] if featured else None)
    right = Album.query.filter_by(slug=right_slug).first() if right_slug else (featured[1] if len(featured) > 1 else None)
    return render_template("compare.html", left=left, right=right, featured=featured)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "error")
        else:
            login_user(user)
            flash(f"Welcome back, {user.display_name}.", "success")
            return redirect(safe_next_url(request.form.get("next") or request.args.get("next")) or url_for("account"))
    return render_template("login.html", next_url=safe_next_url(request.args.get("next")))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        username = slugify(request.form.get("username", "").strip())
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        city = request.form.get("city", "").strip()
        favorite_format = request.form.get("favorite_format", "digital")
        if not display_name or not username or not email or not password:
            flash("Name, username, email, and password are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "error")
        elif User.query.filter_by(username=username).first():
            flash("That username is already taken.", "error")
        else:
            user = User(
                display_name=display_name,
                username=username,
                email=email,
                city=city,
                favorite_format=favorite_format,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Your fan account is ready.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    return render_template(
        "account.html",
        orders=Order.query.filter_by(user_id=current_user.id).order_by(Order.placed_at.desc()).limit(5).all(),
        collection_count=FanCollectionItem.query.filter_by(user_id=current_user.id).count(),
        wishlist_count=WishlistItem.query.filter_by(user_id=current_user.id).count(),
        cart_count=CartItem.query.filter_by(user_id=current_user.id).count(),
        scenes=Scene.query.order_by(Scene.name.asc()).all(),
    )


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    scenes = Scene.query.order_by(Scene.name.asc()).all()
    if request.method == "POST":
        current_user.display_name = request.form.get("display_name", "").strip() or current_user.display_name
        current_user.bio = request.form.get("bio", "").strip()
        current_user.city = request.form.get("city", "").strip()
        current_user.country = request.form.get("country", "").strip() or "United States"
        current_user.address_line1 = request.form.get("address_line1", "").strip()
        current_user.postal_code = request.form.get("postal_code", "").strip()
        current_user.favorite_format = request.form.get("favorite_format", "digital")
        scene = Scene.query.filter_by(slug=request.form.get("favorite_scene", "")).first()
        current_user.favorite_scene_id = scene.id if scene else None
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html", scenes=scenes)


@app.route("/wishlist")
@login_required
def wishlist():
    return render_template(
        "wishlist.html",
        items=WishlistItem.query.filter_by(user_id=current_user.id).order_by(WishlistItem.added_at.desc()).all(),
    )


@app.route("/wishlist/add", methods=["POST"])
@login_required
def wishlist_add():
    album_id = request.form.get("album_id", type=int)
    merch_id = request.form.get("merch_id", type=int)
    if not album_id and not merch_id:
        flash("Nothing was selected to save.", "error")
        return redirect(request.referrer or url_for("discover"))
    existing = WishlistItem.query.filter_by(user_id=current_user.id, album_id=album_id, merch_item_id=merch_id).first()
    if existing:
        flash("That item is already in your wishlist.", "info")
    else:
        db.session.add(WishlistItem(user_id=current_user.id, album_id=album_id, merch_item_id=merch_id))
        db.session.commit()
        flash("Saved to your wishlist.", "success")
    return redirect(request.referrer or url_for("wishlist"))


@app.route("/wishlist/remove/<int:item_id>", methods=["POST"])
@login_required
def wishlist_remove(item_id: int):
    item = WishlistItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Removed from your wishlist.", "info")
    return redirect(url_for("wishlist"))


@app.route("/cart")
@login_required
def cart():
    items = get_cart_items()
    return render_template("cart.html", items=items, summary=cart_summary(items))


@app.route("/cart/add", methods=["POST"])
@login_required
def cart_add():
    album_id = request.form.get("album_id", type=int)
    merch_id = request.form.get("merch_id", type=int)
    variant_id = request.form.get("variant_id", type=int)
    quantity = max(1, request.form.get("quantity", type=int) or 1)
    variant = db.session.get(FormatVariant, variant_id) if variant_id else None

    if album_id:
        album = db.session.get(Album, album_id)
        if not album:
            abort(404)
        if variant and variant.album_id != album.id:
            flash("Selected format is not available for that album.", "error")
            return redirect(request.referrer or url_for("album_page", slug=album.slug))
        subject_album_id = album.id
        subject_merch_id = None
        subject_title = album.title
    elif merch_id:
        merch = db.session.get(MerchItem, merch_id)
        if not merch:
            abort(404)
        if variant and variant.merch_item_id != merch.id:
            flash("Selected variant is not available for that merch item.", "error")
            return redirect(request.referrer or url_for("merch_page", slug=merch.slug))
        subject_album_id = None
        subject_merch_id = merch.id
        subject_title = merch.title
    else:
        flash("No product was selected.", "error")
        return redirect(url_for("cart"))

    if variant and variant.inventory < quantity:
        flash("That variant does not have enough stock left.", "error")
        return redirect(request.referrer or url_for("cart"))

    existing = CartItem.query.filter_by(
        user_id=current_user.id,
        album_id=subject_album_id,
        merch_item_id=subject_merch_id,
        format_variant_id=variant.id if variant else None,
    ).first()
    if existing:
        existing.quantity += quantity
    else:
        db.session.add(
            CartItem(
                user_id=current_user.id,
                album_id=subject_album_id,
                merch_item_id=subject_merch_id,
                format_variant_id=variant.id if variant else None,
                quantity=quantity,
            )
        )
    db.session.commit()
    flash(f"Added {subject_title} to your cart.", "success")
    if request.form.get("next") == "checkout":
        return redirect(url_for("checkout"))
    return redirect(request.referrer or url_for("cart"))


@app.route("/cart/update/<int:item_id>", methods=["POST"])
@login_required
def cart_update(item_id: int):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    quantity = max(1, request.form.get("quantity", type=int) or 1)
    if item.format_variant and item.format_variant.inventory < quantity:
        flash("Not enough stock for that quantity.", "error")
    else:
        item.quantity = quantity
        db.session.commit()
        flash("Cart updated.", "success")
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def cart_remove(item_id: int):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Removed from your cart.", "info")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items = get_cart_items()
    if not items:
        flash("Your cart is empty.", "info")
        return redirect(url_for("cart"))
    summary = cart_summary(items)
    if request.method == "POST":
        shipping_name = request.form.get("shipping_name", "").strip()
        shipping_line1 = request.form.get("shipping_line1", "").strip()
        shipping_city = request.form.get("shipping_city", "").strip()
        shipping_country = request.form.get("shipping_country", "").strip()
        payment_label = request.form.get("payment_label", "").strip()
        note = request.form.get("note", "").strip()
        if not all([shipping_name, shipping_line1, shipping_city, shipping_country, payment_label]):
            flash("Shipping and payment fields are required.", "error")
        else:
            order = Order(
                user_id=current_user.id,
                order_number=generate_order_number(),
                status="paid",
                subtotal=summary["subtotal"],
                shipping=summary["shipping"],
                tax=summary["tax"],
                total=summary["total"],
                shipping_name=shipping_name,
                shipping_line1=shipping_line1,
                shipping_city=shipping_city,
                shipping_country=shipping_country,
                payment_label=payment_label,
                note=note,
                placed_at=MIRROR_REFERENCE_NOW + timedelta(minutes=(Order.query.count() + 1)),
            )
            db.session.add(order)
            db.session.flush()
            for item in items:
                db.session.add(
                    OrderItem(
                        order_id=order.id,
                        album_id=item.album_id,
                        merch_item_id=item.merch_item_id,
                        format_variant_id=item.format_variant_id,
                        title=item.title(),
                        artist_name=item.artist_name(),
                        image_path=item.image_path(),
                        variant_label=item.variant_label(),
                        quantity=item.quantity,
                        unit_price=item.unit_price(),
                    )
                )
                if item.album:
                    add_collection_item(current_user, item.album, item.format_variant, note="Added from checkout")
                    item.album.fan_count += item.quantity
                if item.format_variant and item.format_variant.inventory < 9999:
                    item.format_variant.inventory = max(0, item.format_variant.inventory - item.quantity)
                elif item.merch_item:
                    item.merch_item.inventory = max(0, item.merch_item.inventory - item.quantity)
                db.session.delete(item)
            current_user.address_line1 = shipping_line1
            current_user.city = shipping_city
            current_user.country = shipping_country
            db.session.commit()
            flash("Mock checkout complete. No payment was processed.", "success")
            return redirect(url_for("order_detail", order_number=order.order_number))
    return render_template("checkout.html", items=items, summary=summary)


@app.route("/collection")
@login_required
def collection():
    return render_template(
        "collection.html",
        items=FanCollectionItem.query.filter_by(user_id=current_user.id).order_by(FanCollectionItem.added_at.desc()).all(),
    )


@app.route("/orders")
@login_required
def orders():
    return render_template(
        "orders.html",
        orders=Order.query.filter_by(user_id=current_user.id).order_by(Order.placed_at.desc()).all(),
    )


@app.route("/orders/<order_number>")
@login_required
def order_detail(order_number: str):
    return render_template(
        "order_detail.html",
        order=Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404(),
    )


@app.route("/album/<slug>/comment", methods=["POST"])
@login_required
def album_comment(slug: str):
    album = Album.query.filter_by(slug=slug).first_or_404()
    body = request.form.get("body", "").strip()
    if not body:
        flash("Write a comment before posting.", "error")
    else:
        db.session.add(
            FanComment(
                user_id=current_user.id,
                album_id=album.id,
                headline=request.form.get("headline", "").strip(),
                body=body,
                rating=min(5, max(1, request.form.get("rating", type=int) or 5)),
            )
        )
        db.session.commit()
        flash("Comment added to the release page.", "success")
    return redirect(url_for("album_page", slug=slug))


@app.route("/_health")
def health():
    return {"ok": True, "site": "bandcamp"}


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_error):
    return render_template("500.html"), 500


def seed_database() -> None:
    if Artist.query.count() > 0:
        return
    from seed_data import run_seed

    run_seed(
        db=db,
        base_dir=BASE_DIR,
        mirror_reference_now=MIRROR_REFERENCE_NOW,
        models={
            "Genre": Genre,
            "Scene": Scene,
            "Label": Label,
            "Artist": Artist,
            "Album": Album,
            "Track": Track,
            "Tag": Tag,
            "MerchItem": MerchItem,
            "FormatVariant": FormatVariant,
            "FanComment": FanComment,
        },
    )


def seed_benchmark_users() -> None:
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    users_data = [
        {
            "username": "alice_j",
            "email": "alice.j@test.com",
            "display_name": "Alice Johnson",
            "city": "Seattle",
            "country": "United States",
            "favorite_format": "vinyl",
            "favorite_scene_slug": "berlin-germany",
            "bio": "Collects ambient and dub techno 12-inches.",
            "address_line1": "128 Lake Union Ave",
            "postal_code": "98109",
        },
        {
            "username": "bob_c",
            "email": "bob.c@test.com",
            "display_name": "Bob Chen",
            "city": "Chicago",
            "country": "United States",
            "favorite_format": "digital",
            "favorite_scene_slug": "detroit-united-states",
            "bio": "Hip-hop fan chasing sharp lyric sheets and live bootlegs.",
            "address_line1": "77 Fulton Market",
            "postal_code": "60607",
        },
        {
            "username": "carol_d",
            "email": "carol.d@test.com",
            "display_name": "Carol Davis",
            "city": "Brooklyn",
            "country": "United States",
            "favorite_format": "cassette",
            "favorite_scene_slug": "tokyo-japan",
            "bio": "Tags every purchase with the scene where she found it.",
            "address_line1": "55 Bergen St",
            "postal_code": "11201",
        },
        {
            "username": "david_k",
            "email": "david.k@test.com",
            "display_name": "David Kim",
            "city": "Portland",
            "country": "United States",
            "favorite_format": "shirt",
            "favorite_scene_slug": "melbourne-australia",
            "bio": "Merch-heavy collector who buys a tote with almost every record.",
            "address_line1": "204 Burnside St",
            "postal_code": "97209",
        },
    ]

    created_users: dict[str, User] = {}
    for data in users_data:
        scene = Scene.query.filter_by(slug=data["favorite_scene_slug"]).first()
        user = User(
            username=data["username"],
            email=data["email"],
            display_name=data["display_name"],
            city=data["city"],
            country=data["country"],
            favorite_format=data["favorite_format"],
            favorite_scene_id=scene.id if scene else None,
            bio=data["bio"],
            address_line1=data["address_line1"],
            postal_code=data["postal_code"],
        )
        user.set_password("TestPass123!")
        db.session.add(user)
        db.session.flush()
        created_users[data["username"]] = user

    def album_by_slug(slug: str) -> Album:
        album = Album.query.filter_by(slug=slug).first()
        if not album:
            raise LookupError(f"Missing album seed: {slug}")
        return album

    def merch_by_slug(slug: str) -> MerchItem:
        merch = MerchItem.query.filter_by(slug=slug).first()
        if not merch:
            raise LookupError(f"Missing merch seed: {slug}")
        return merch

    def variant_for_album(slug: str, kind: str) -> FormatVariant:
        variant = FormatVariant.query.join(Album).filter(Album.slug == slug, FormatVariant.kind == kind).first()
        if not variant:
            raise LookupError(f"Missing album variant: {slug} / {kind}")
        return variant

    def variant_for_merch(slug: str, needle: str) -> FormatVariant:
        variant = (
            FormatVariant.query.join(MerchItem)
            .filter(MerchItem.slug == slug, FormatVariant.name.ilike(f"%{needle}%"))
            .first()
        )
        if not variant:
            variant = (
                FormatVariant.query.join(MerchItem)
                .filter(MerchItem.slug == slug, FormatVariant.option_a.ilike(f"%{needle}%"))
                .first()
            )
        if not variant:
            raise LookupError(f"Missing merch variant: {slug} / {needle}")
        return variant

    def make_order(
        user: User,
        order_number: str,
        status: str,
        placed_at: datetime,
        shipping_name: str,
        shipping_line1: str,
        shipping_city: str,
        shipping_country: str,
        payment_label: str,
        items_spec: list[tuple[str, str, str, int]],
    ) -> None:
        order = Order(
            user_id=user.id,
            order_number=order_number,
            status=status,
            shipping_name=shipping_name,
            shipping_line1=shipping_line1,
            shipping_city=shipping_city,
            shipping_country=shipping_country,
            payment_label=payment_label,
            placed_at=placed_at,
            note="Deterministic benchmark seed order.",
        )
        db.session.add(order)
        db.session.flush()

        subtotal = 0.0
        for kind, slug, variant_key, qty in items_spec:
            if kind == "album":
                album = album_by_slug(slug)
                variant = variant_for_album(slug, variant_key)
                db.session.add(
                    OrderItem(
                        order_id=order.id,
                        album_id=album.id,
                        format_variant_id=variant.id,
                        title=album.title,
                        artist_name=album.artist.name,
                        image_path=album.cover_image,
                        variant_label=variant.label_text(),
                        quantity=qty,
                        unit_price=variant.price,
                    )
                )
                add_collection_item(user, album, variant, note="Seeded library item")
                album.fan_count += qty
                subtotal += variant.price * qty
            else:
                merch = merch_by_slug(slug)
                variant = variant_for_merch(slug, variant_key)
                db.session.add(
                    OrderItem(
                        order_id=order.id,
                        merch_item_id=merch.id,
                        format_variant_id=variant.id,
                        title=merch.title,
                        artist_name=merch.artist.name,
                        image_path=merch.image,
                        variant_label=variant.label_text(),
                        quantity=qty,
                        unit_price=variant.price,
                    )
                )
                subtotal += variant.price * qty

        order.subtotal = round(subtotal, 2)
        order.shipping = 0.0 if subtotal >= 45 else 6.5
        order.tax = round(order.subtotal * 0.0825, 2)
        order.total = round(order.subtotal + order.shipping + order.tax, 2)

    alice = created_users["alice_j"]
    bob = created_users["bob_c"]
    carol = created_users["carol_d"]
    david = created_users["david_k"]

    def add_cart_seed(user: User, specs: list[tuple[str, str, str, int]]) -> None:
        for kind, slug, variant_key, qty in specs:
            if kind == "album":
                album = album_by_slug(slug)
                variant = variant_for_album(slug, variant_key)
                db.session.add(
                    CartItem(user_id=user.id, album_id=album.id, format_variant_id=variant.id, quantity=qty)
                )
            else:
                merch = merch_by_slug(slug)
                variant = variant_for_merch(slug, variant_key)
                db.session.add(
                    CartItem(user_id=user.id, merch_item_id=merch.id, format_variant_id=variant.id, quantity=qty)
                )

    def add_wishlist_seed(user: User, album_slugs: list[str], merch_slugs: list[str]) -> None:
        for slug in album_slugs:
            db.session.add(WishlistItem(user_id=user.id, album_id=album_by_slug(slug).id))
        for slug in merch_slugs:
            db.session.add(WishlistItem(user_id=user.id, merch_item_id=merch_by_slug(slug).id))

    add_cart_seed(
        alice,
        [("album", "tidal-memory", "vinyl", 1), ("album", "between-stations", "cassette", 1), ("merch", "neon-harbor-studio-tee", "M", 1)],
    )
    add_cart_seed(
        bob,
        [("album", "signal-debt", "digital", 1), ("merch", "cinder-plaza-blueprint-fever-poster", "Signed", 1)],
    )
    add_cart_seed(
        carol,
        [("album", "riverlights", "vinyl", 1), ("merch", "soft-locale-drift-hoodie", "L", 1)],
    )
    add_cart_seed(
        david,
        [("merch", "salt-meadow-field-notes-tote", "Natural", 1), ("album", "elastic-hearts", "cd", 1)],
    )

    add_wishlist_seed(alice, ["static-bloom", "blue-hour-broadcast", "resin-language"], ["velvet-avenue-night-shift-poster"])
    add_wishlist_seed(bob, ["iron-sleep", "machine-prayer"], ["ashen-circuit-grid-slipmat", "mono-shrine-fault-choir-zine"])
    add_wishlist_seed(carol, ["riverlights", "paper-signal", "harbor-burn"], ["glass-choir-stairwell-tee"])
    add_wishlist_seed(david, ["elastic-hearts", "sleep-maps"], ["soft-locale-drift-hoodie", "salt-meadow-field-notes-tote"])

    make_order(
        alice,
        "BC-20260414-0001",
        "delivered",
        MIRROR_REFERENCE_NOW - timedelta(days=17),
        "Alice Johnson",
        "128 Lake Union Ave",
        "Seattle",
        "United States",
        "Visa ending in 4242",
        [("album", "blue-hour-broadcast", "vinyl", 1), ("merch", "velvet-avenue-night-shift-poster", "Signed", 1)],
    )
    make_order(
        alice,
        "BC-20260426-0002",
        "processing",
        MIRROR_REFERENCE_NOW - timedelta(days=5),
        "Alice Johnson",
        "128 Lake Union Ave",
        "Seattle",
        "United States",
        "Visa ending in 1177",
        [("album", "tidal-memory", "digital", 1)],
    )
    make_order(
        bob,
        "BC-20260409-0003",
        "delivered",
        MIRROR_REFERENCE_NOW - timedelta(days=22),
        "Bob Chen",
        "77 Fulton Market",
        "Chicago",
        "United States",
        "Mastercard ending in 7788",
        [("album", "signal-debt", "digital", 1), ("album", "resin-language", "cassette", 1)],
    )
    make_order(
        carol,
        "BC-20260421-0004",
        "delivered",
        MIRROR_REFERENCE_NOW - timedelta(days=10),
        "Carol Davis",
        "55 Bergen St",
        "Brooklyn",
        "United States",
        "Visa ending in 9901",
        [("album", "between-stations", "cassette", 1), ("merch", "soft-locale-drift-hoodie", "M", 1)],
    )
    make_order(
        david,
        "BC-20260428-0005",
        "shipped",
        MIRROR_REFERENCE_NOW - timedelta(days=3),
        "David Kim",
        "204 Burnside St",
        "Portland",
        "United States",
        "Amex ending in 3401",
        [("album", "elastic-hearts", "cd", 1), ("merch", "salt-meadow-field-notes-tote", "Natural", 1)],
    )

    for username, album_slug, headline, body in [
        ("alice_j", "tidal-memory", "Most replayed this month", "The dub bassline on side B makes the whole release feel tidal."),
        ("bob_c", "signal-debt", "Sharp sequencing", "Track order is ruthless in the best possible way."),
        ("carol_d", "between-stations", "Commuter ambient", "Feels like catching the last Yamanote line with the windows fogged over."),
        ("david_k", "riverlights", "Warm and tactile", "The lyric sheet tucked into the LP package is a lovely touch."),
    ]:
        db.session.add(
            FanComment(
                user_id=created_users[username].id,
                album_id=album_by_slug(album_slug).id,
                headline=headline,
                body=body,
                rating=5,
                created_at=MIRROR_REFERENCE_NOW - timedelta(days=2),
            )
        )

    db.session.commit()


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 40016))
    app.run(host="0.0.0.0", port=port, debug=False)
