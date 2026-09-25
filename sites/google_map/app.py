"""
Google Maps Mirror - Flask application.

Entity model adapted for a maps/search site:
  Place     - restaurants, hotels, attractions, museums, parks, shops, etc.
  Category  - top-level taxonomy (mapped to nav)
  City      - each place belongs to a city; cities get browsing pages

CRUD-adapted from e-commerce primitives:
  SavedList  - user's custom place lists ("Want to go", "Favorites") ~= cart+wishlist
  SavedPlace - membership of a place in a list             ~= CartItem/WishlistItem
  Trip       - a multi-place planned trip                  ~= Order
  TripStop   - a stop in a trip with order/notes           ~= OrderItem
  Review     - user review of a place
  Photo      - user-uploaded photo for a place
  TimelineEntry - location history entries
"""
import json
import math
import os
import random
import re
import string
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, abort, session, send_from_directory)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from sqlalchemy import or_, and_, func
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DIR = Path(__file__).parent

# --------------------------------------------------------------------------
#  App factory
# --------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "google-maps-mirror-secret-key-change-in-prod"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'instance' / 'gmaps.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None

os.makedirs(BASE_DIR / "instance", exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to save places, leave reviews, and access your lists."
login_manager.login_message_category = "info"


# --------------------------------------------------------------------------
#  Gallery helpers
# --------------------------------------------------------------------------
_MANIFEST_CACHE = None

def _load_manifest():
    """Load place_galleries.json once and cache it."""
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is None:
        path = BASE_DIR / "place_galleries.json"
        try:
            _MANIFEST_CACHE = json.loads(path.read_text())
        except Exception:
            _MANIFEST_CACHE = {}
    return _MANIFEST_CACHE


_CATEGORY_SECTION_TEMPLATES = {
    "attractions": [
        ("Overview", "An unmissable attraction famous around the world for its stunning presence and cultural significance."),
        ("Visitor Experience", "Walk through the site at your own pace, snap photos from the best viewpoints, and soak in the atmosphere."),
        ("History & Meaning", "Centuries of history and countless stories live within these walls - a cornerstone of the city's identity."),
    ],
    "hotels": [
        ("Rooms & Suites", "Spacious, stylish accommodations with premium bedding, modern amenities, and thoughtful touches."),
        ("Amenities", "Relax at the spa, swim in the pool, and dine at award-winning restaurants - all without leaving the property."),
        ("Location", "Positioned in a prime part of the city with easy access to major attractions and transit."),
    ],
    "restaurants": [
        ("The Menu", "A thoughtfully curated menu featuring seasonal ingredients and signature dishes the kitchen has perfected over years."),
        ("Atmosphere", "Warm lighting, attentive service, and a dining room designed to make every meal feel memorable."),
        ("Reviews", "Consistently praised by guests for its food, hospitality, and overall experience."),
    ],
    "museums": [
        ("Collections", "Explore a world-class collection spanning multiple eras, with rotating exhibitions and permanent galleries."),
        ("Visiting", "Plan a half-day visit to take in the highlights - audio guides and docent tours are available."),
        ("Architecture", "The building itself is a work of art, designed to complement and showcase the collection within."),
    ],
    "parks": [
        ("Trails & Walks", "Miles of trails wind through diverse landscapes, perfect for morning jogs or leisurely afternoon strolls."),
        ("Recreation", "Picnic areas, playgrounds, sports courts, and open lawns invite visitors of every age."),
        ("Nature", "A green oasis filled with native flora and wildlife - a place to reconnect with nature in the heart of the city."),
    ],
    "shopping": [
        ("Stores & Brands", "From global fashion houses to beloved local boutiques, you will find everything under one roof."),
        ("Dining", "Food courts and sit-down restaurants make this a destination for all-day visits."),
        ("Experience", "Beautiful architecture, seasonal events, and engaging displays turn shopping into an experience."),
    ],
    "entertainment": [
        ("Showtime", "Live performances, headline acts, and an atmosphere that pulls you in from the moment you arrive."),
        ("Venue", "A stunning space designed with sightlines, acoustics, and energy in mind."),
        ("What to Expect", "An unforgettable night out - arrive early, stay late, and soak it all in."),
    ],
    "transit": [
        ("Getting There", "A major transportation hub connecting travelers to destinations near and far."),
        ("Facilities", "Modern amenities include shops, restaurants, lounges, and seamless connections."),
        ("History", "An architecturally significant gateway that has served the city for generations."),
    ],
}


# --------------------------------------------------------------------------
#  Models
# --------------------------------------------------------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    avatar_letter = db.Column(db.String(1), default="U")
    home_city = db.Column(db.String(128), default="")
    bio = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    saved_lists = db.relationship("SavedList", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    saved_places = db.relationship("SavedPlace", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    trips = db.relationship("Trip", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    reviews = db.relationship("Review", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    photos = db.relationship("Photo", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    timeline_entries = db.relationship("TimelineEntry", backref="user", cascade="all, delete-orphan", lazy="dynamic")


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    icon = db.Column(db.String(64), default="place")
    color = db.Column(db.String(16), default="#4285f4")
    description = db.Column(db.Text, default="")

    places = db.relationship("Place", backref="category", lazy="dynamic")


class City(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(128), nullable=False)
    country = db.Column(db.String(128), default="")
    hero_image = db.Column(db.String(255), default="")
    description = db.Column(db.Text, default="")
    lat = db.Column(db.Float, default=0.0)
    lng = db.Column(db.Float, default=0.0)

    places = db.relationship("Place", backref="city", lazy="dynamic")


class Place(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    city_id = db.Column(db.Integer, db.ForeignKey("city.id"), nullable=False)
    subtitle = db.Column(db.String(255), default="")
    description = db.Column(db.Text, default="")
    address = db.Column(db.String(255), default="")
    zip_code = db.Column(db.String(16), default="", index=True)
    state = db.Column(db.String(32), default="", index=True)
    phone = db.Column(db.String(64), default="")
    hours = db.Column(db.String(255), default="")
    hours_json = db.Column(db.Text, default="{}")  # {"mon": "9-5", ...}
    website = db.Column(db.String(255), default="")
    rating = db.Column(db.Float, default=4.5)
    review_count = db.Column(db.Integer, default=0)
    price_level = db.Column(db.String(16), default="$")
    hero_image = db.Column(db.String(255), default="")
    photos_json = db.Column(db.Text, default="[]")
    lat = db.Column(db.Float, default=0.0)
    lng = db.Column(db.Float, default=0.0)
    tags_json = db.Column(db.Text, default="[]")       # search keywords
    amenities_json = db.Column(db.Text, default="[]")  # parking, wifi, etc.
    is_24h = db.Column(db.Boolean, default=False)
    is_open_now = db.Column(db.Boolean, default=True)
    closes_at_night = db.Column(db.Boolean, default=False)  # not open 24h
    has_parking_lot = db.Column(db.Boolean, default=False)
    ev_charging = db.Column(db.Boolean, default=False)
    motorcycle_parking = db.Column(db.Boolean, default=False)
    bicycle_parking = db.Column(db.Boolean, default=False)
    subcategory = db.Column(db.String(64), default="", index=True)
    chain_brand = db.Column(db.String(128), default="", index=True)
    nearest_landmark = db.Column(db.String(255), default="")
    review_snippets_json = db.Column(db.Text, default="[]")  # list of {rating,text}
    is_featured = db.Column(db.Boolean, default=False)
    is_popular = db.Column(db.Boolean, default=False)
    parking_info = db.Column(db.String(255), default="")  # e.g. "Free parking lot", "Street parking", "Paid garage"
    delivery_available = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviews = db.relationship("Review", backref="place", cascade="all, delete-orphan", lazy="dynamic")
    photos = db.relationship("Photo", backref="place", cascade="all, delete-orphan", lazy="dynamic")

    def get_photos(self):
        try:
            return json.loads(self.photos_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def get_tags(self):
        try:
            return json.loads(self.tags_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def get_amenities(self):
        try:
            return json.loads(self.amenities_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def get_hours_dict(self):
        try:
            return json.loads(self.hours_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_review_snippets(self):
        try:
            return json.loads(self.review_snippets_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def get_gallery(self):
        """Load gallery sections.

        Strategy:
          1) If the place is in place_galleries.json (real Wikipedia places),
             return the curated sections from there.
          2) Otherwise, synthesize sections from photos_json using
             category-aware templates. Every place thus gets a rich gallery.
        """
        sections = _load_manifest().get(self.slug)
        if sections:
            return sections
        # Fallback: synthesize from photos_json
        photos = self.get_photos()
        if not photos and self.hero_image:
            photos = [self.hero_image]
        if not photos:
            return []
        cat_slug = self.category.slug if self.category else "attractions"
        templates = _CATEGORY_SECTION_TEMPLATES.get(cat_slug, _CATEGORY_SECTION_TEMPLATES["attractions"])
        sections = []
        n = max(1, len(photos) // len(templates))
        for i, (title, desc) in enumerate(templates):
            start = i * n
            end = (i + 1) * n if i < len(templates) - 1 else len(photos)
            imgs = photos[start:end] or [photos[i % len(photos)]]
            sections.append({"title": title, "desc": desc, "images": imgs})
        return sections

    @property
    def stars_full(self):
        return int(self.rating)

    @property
    def stars_half(self):
        return 1 if (self.rating - int(self.rating)) >= 0.5 else 0

    @property
    def stars_empty(self):
        return 5 - self.stars_full - self.stars_half


class SavedList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, default="")
    icon = db.Column(db.String(32), default="bookmark")
    color = db.Column(db.String(16), default="#4285f4")
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    places = db.relationship("SavedPlace", backref="saved_list", cascade="all, delete-orphan", lazy="dynamic")


class SavedPlace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    list_id = db.Column(db.Integer, db.ForeignKey("saved_list.id"), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey("place.id"), nullable=False)
    note = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    place = db.relationship("Place")


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    trip_code = db.Column(db.String(16), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(128), default="")
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(32), default="planning")  # planning, upcoming, active, completed, cancelled
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    stops = db.relationship("TripStop", backref="trip", cascade="all, delete-orphan", lazy="dynamic", order_by="TripStop.order_idx")


class TripStop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey("place.id"), nullable=False)
    order_idx = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text, default="")

    place = db.relationship("Place")


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey("place.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), default="")
    body = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey("place.id"), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TimelineEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey("place.id"), nullable=False)
    visited_at = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.Text, default="")

    place = db.relationship("Place")


class Route(db.Model):
    """Precomputed routes between notable origin/destination queries.

    Matches by `origin_query`/`destination_query` substrings, optionally
    filtered by `mode` (walking/driving/transit/bicycling).
    """
    id = db.Column(db.Integer, primary_key=True)
    origin_query = db.Column(db.String(255), nullable=False, index=True)
    destination_query = db.Column(db.String(255), nullable=False, index=True)
    origin_name = db.Column(db.String(255), default="")
    destination_name = db.Column(db.String(255), default="")
    mode = db.Column(db.String(32), default="driving", index=True)
    distance = db.Column(db.String(64), default="")      # "2.3 km" / "1.4 mi"
    distance_km = db.Column(db.Float, default=0.0)
    duration = db.Column(db.String(64), default="")      # "18 min"
    duration_min = db.Column(db.Integer, default=0)
    steps_json = db.Column(db.Text, default="[]")        # list of {instruction, distance}
    summary = db.Column(db.Text, default="")
    origin_address = db.Column(db.String(255), default="")
    destination_address = db.Column(db.String(255), default="")

    def get_steps(self):
        try:
            return json.loads(self.steps_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []


# --------------------------------------------------------------------------
#  Login / helpers
# --------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def gen_trip_code():
    return "TRIP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def ensure_default_lists(user):
    """Give every new user a default 'Want to go', 'Favorites', 'Starred'."""
    defaults = [
        ("Want to go", "bookmark", "#4285f4", "Places you'd love to visit"),
        ("Favorites", "favorite", "#ea4335", "Your all-time favorite places"),
        ("Starred places", "star", "#fbbc04", "Places you've starred for quick access"),
    ]
    for name, icon, color, desc in defaults:
        db.session.add(SavedList(
            user_id=user.id, name=name, icon=icon, color=color,
            description=desc, is_default=True,
        ))
    db.session.commit()


@app.context_processor
def inject_globals():
    categories = Category.query.order_by(Category.id).all()
    saved_count = 0
    if current_user.is_authenticated:
        saved_count = SavedPlace.query.filter_by(user_id=current_user.id).count()
    return {
        "global_categories": categories,
        "global_saved_count": saved_count,
        "current_year": datetime.utcnow().year,
    }


# --------------------------------------------------------------------------
#  Public pages
# --------------------------------------------------------------------------
@app.route("/")
def index():
    featured = Place.query.filter_by(is_featured=True).limit(12).all()
    popular = Place.query.filter_by(is_popular=True).order_by(Place.rating.desc()).limit(12).all()
    cities = City.query.order_by(City.display_name).limit(12).all()
    categories = Category.query.order_by(Category.id).all()
    return render_template(
        "index.html",
        featured=featured,
        popular=popular,
        cities=cities,
        categories=categories,
    )


@app.route("/explore")
def explore():
    categories = Category.query.order_by(Category.id).all()
    cities = City.query.order_by(City.display_name).all()
    popular = Place.query.filter_by(is_popular=True).order_by(Place.rating.desc()).limit(24).all()
    return render_template(
        "explore.html",
        categories=categories,
        cities=cities,
        popular=popular,
    )


@app.route("/category/<slug>")
def category_page(slug):
    cat = Category.query.filter_by(slug=slug).first_or_404()
    city_filter = request.args.get("city", "")
    sort = request.args.get("sort", "rating")
    min_rating = request.args.get("min_rating", type=float)

    q = Place.query.filter_by(category_id=cat.id)
    if city_filter:
        c = City.query.filter_by(slug=city_filter).first()
        if c:
            q = q.filter_by(city_id=c.id)
    if min_rating:
        q = q.filter(Place.rating >= min_rating)

    if sort == "name":
        q = q.order_by(Place.name.asc())
    elif sort == "reviews":
        q = q.order_by(Place.review_count.desc())
    else:
        q = q.order_by(Place.rating.desc(), Place.review_count.desc())

    places = q.all()
    cities = City.query.order_by(City.display_name).all()

    return render_template(
        "category.html",
        category=cat,
        places=places,
        cities=cities,
        city_filter=city_filter,
        sort=sort,
        min_rating=min_rating,
    )


@app.route("/city/<slug>")
def city_page(slug):
    city = City.query.filter_by(slug=slug).first_or_404()
    categories = Category.query.order_by(Category.id).all()
    # Group places by category
    places_by_cat = {}
    for cat in categories:
        places = Place.query.filter_by(city_id=city.id, category_id=cat.id) \
            .order_by(Place.rating.desc()).limit(6).all()
        if places:
            places_by_cat[cat] = places

    top_rated = Place.query.filter_by(city_id=city.id) \
        .order_by(Place.rating.desc(), Place.review_count.desc()).limit(12).all()

    return render_template(
        "city.html",
        city=city,
        places_by_cat=places_by_cat,
        top_rated=top_rated,
    )


@app.route("/place/<slug>")
def place_detail(slug):
    place = Place.query.filter_by(slug=slug).first_or_404()
    # Reviews
    reviews = Review.query.filter_by(place_id=place.id) \
        .order_by(Review.created_at.desc()).limit(12).all()
    # Nearby places: distance-sort within ~25 mi, diversify by category so
    # the section isn't dominated by one bucket (e.g. high-rated climbing
    # gyms drowning out everything else in LA).  Real Google Maps surfaces
    # mixed categories on a place-detail page; clicking a category chip
    # below opens a search filtered by that category near this place.
    nearby_cat = (request.args.get("nearby_category") or "").strip().lower()
    nearby = []
    if place.lat and place.lng:
        cand_q = Place.query.filter(Place.id != place.id, Place.lat != 0)
        if nearby_cat:
            cat = Category.query.filter(or_(
                Category.slug == nearby_cat,
                Category.slug == nearby_cat + "s",
                Category.name.ilike(f"%{nearby_cat}%"),
            )).first()
            if cat:
                cand_q = cand_q.filter(Place.category_id == cat.id)
        # Collect everything within 30 mi but do NOT sort by distance —
        # the agent must read each distance pill and compare to answer
        # "which is the nearest X" tasks.  Sort by rating × log(reviews)
        # so popular places surface first, mirroring real Google Maps'
        # relevance-driven ordering.
        scored = []
        for p in cand_q.limit(2000).all():
            d = _haversine_mi(place.lat, place.lng, p.lat, p.lng)
            if d <= 30:
                rel = (p.rating or 4.0) * math.log(max(p.review_count or 1, 1) + 2)
                scored.append((rel, d, p))
        scored.sort(key=lambda x: -x[0])
        if nearby_cat:
            for _, d, p in scored[:12]:
                p.distance_mi = d
                nearby.append(p)
        else:
            seen_cat = {}
            for _, d, p in scored:
                if seen_cat.get(p.category_id, 0) >= 2:
                    continue
                seen_cat[p.category_id] = seen_cat.get(p.category_id, 0) + 1
                p.distance_mi = d
                nearby.append(p)
                if len(nearby) >= 12:
                    break
    if not nearby:
        nearby = Place.query.filter(
            Place.city_id == place.city_id, Place.id != place.id,
        ).order_by(Place.rating.desc()).limit(12).all()
        for p in nearby:
            p.distance_mi = None
    # Category chips: top categories represented in 30-mi radius
    nearby_cat_chips = []
    if place.lat and place.lng:
        seen_chip = {}
        for p in (Place.query.filter(Place.id != place.id, Place.lat != 0)
                  .limit(2000).all()):
            d = _haversine_mi(place.lat, place.lng, p.lat, p.lng)
            if d <= 30 and p.category:
                seen_chip[p.category] = seen_chip.get(p.category, 0) + 1
        nearby_cat_chips = sorted(seen_chip.items(), key=lambda kv: -kv[1])[:8]
    # Is saved?
    is_saved = False
    user_lists = []
    if current_user.is_authenticated:
        is_saved = SavedPlace.query.filter_by(
            user_id=current_user.id, place_id=place.id
        ).first() is not None
        user_lists = SavedList.query.filter_by(user_id=current_user.id).all()

    return render_template(
        "place_detail.html",
        place=place,
        reviews=reviews,
        nearby=nearby,
        nearby_cat=nearby_cat,
        nearby_cat_chips=nearby_cat_chips,
        is_saved=is_saved,
        user_lists=user_lists,
    )


STOPWORDS = {
    'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'and', 'or',
    'is', 'are', 'be', 'by', 'from', 'near', 'nearby', 'closest', 'nearest',
    'find', 'show', 'me', 'any', 'some', 'that', 'this', 'my', 'i', 'll',
    'please', 'around', 'close', 'open', 'available', 'now',
}


def _tokenize(q):
    import re
    return [t for t in re.findall(r"[a-z0-9]+", (q or "").lower())
            if t not in STOPWORDS and len(t) >= 2]


def _stem_variants(token):
    """Cheap singular/plural/-ing variants of a token so 'plumbers'
    matches 'plumbing' / 'plumber'.  Returns a list with the token + 1-3
    spelling variants (lower-case).  No real stemmer to keep it offline
    + dependency-free."""
    t = token.lower()
    variants = {t}
    if t.endswith("ies") and len(t) > 4:
        variants.add(t[:-3] + "y")
    if t.endswith("es") and len(t) > 3:
        variants.add(t[:-2])
    if t.endswith("s") and len(t) > 3:
        variants.add(t[:-1])
    if t.endswith("ing") and len(t) > 5:
        variants.add(t[:-3])         # plumbing → plumb
        variants.add(t[:-3] + "er")  # plumbing → plumber
        variants.add(t[:-3] + "ers") # plumbing → plumbers
    if t.endswith("er") and len(t) > 4:
        variants.add(t[:-2] + "ing")  # plumber → plumbing
        variants.add(t[:-2] + "ers")  # plumber → plumbers
    if t.endswith("ers") and len(t) > 5:
        variants.add(t[:-3] + "ing")  # plumbers → plumbing
        variants.add(t[:-3] + "er")   # plumbers → plumber
    return list(variants)


def _score_place(place, tokens):
    if not tokens:
        return 1
    haystack_parts = [
        (place.name or "").lower(),
        (place.subtitle or "").lower(),
        (place.description or "").lower(),
        (place.address or "").lower(),
        (place.zip_code or "").lower(),
        (place.state or "").lower(),
        (place.subcategory or "").lower(),
        (place.chain_brand or "").lower(),
        (place.nearest_landmark or "").lower(),
        (place.tags_json or "").lower(),
        (place.amenities_json or "").lower(),
    ]
    city_bag = ""
    if place.city:
        city_bag = f"{place.city.display_name.lower()} {place.city.slug.lower()}"
        haystack_parts.append(city_bag)
    if place.category:
        haystack_parts.append(place.category.slug.lower())
        haystack_parts.append(place.category.name.lower())
    hay = " ".join(haystack_parts)
    name_lc = (place.name or "").lower()
    score = 0
    for t in tokens:
        # Match any singular/plural/-ing variant so "plumbers" hits
        # "plumbing" / "plumber" places (and vice versa).
        variants = _stem_variants(t)
        if any(v in hay for v in variants):
            score += 1
        if any(v in name_lc for v in variants):
            score += 2
    if city_bag:
        for t in tokens:
            for v in _stem_variants(t):
                if v in city_bag and len(v) >= 3:
                    score += 3
                    break
    return score


# ---------------------------------------------------------------------------
# Location-bias search: zip centroids, haversine, and natural-language anchor
# extraction.  This lets queries like "apple store 90028" or
# "parking near brooklyn bridge" rank results by real-world distance.
# ---------------------------------------------------------------------------

# Real US zip centroids for task-relevant zips.  Used to resolve a 5-digit zip
# in the query (or in ?near=) to a search anchor, even when no Place row sits
# inside that zip.
_ZIP_CENTROIDS = {
    "90028": (34.1016, -118.3267), "90036": (34.0721, -118.3618),
    "90048": (34.0744, -118.3779), "90067": (34.0586, -118.4180),
    "90401": (34.0149, -118.4972), "91210": (34.1469, -118.2553),
    "91423": (34.1517, -118.4496), "91105": (34.1389, -118.1631),
    "91302": (34.1567, -118.6376), "90031": (34.0743, -118.2095),
    "33139": (25.7820, -80.1340),  "33130": (25.7780, -80.1980),
    "33125": (25.7800, -80.2350),  "33176": (25.6650, -80.3960),
    "30309": (33.7918, -84.3870),  "30308": (33.7700, -84.3700),
    "30303": (33.7530, -84.3902),  "30314": (33.7540, -84.4253),
    "10001": (40.7506, -73.9971),  "10003": (40.7325, -73.9889),
    "10011": (40.7415, -74.0009),  "10019": (40.7660, -73.9820),
    "10020": (40.7600, -73.9787),  "10128": (40.7820, -73.9510),
    "11201": (40.6932, -73.9907),  "11217": (40.6816, -73.9791),
    "20024": (38.8800, -77.0200),  "20560": (38.8888, -77.0260),
    "60608": (41.8537, -87.6592),  "60611": (41.8966, -87.6240),
    "02110": (42.3580, -71.0540),  "02109": (42.3611, -71.0540),
    "02108": (42.3580, -71.0653),  "02115": (42.3422, -71.0900),
    "02116": (42.3504, -71.0729),  "02114": (42.3611, -71.0680),
    "44012": (41.5050, -82.0290),
    "80202": (39.7479, -104.9994), "80205": (39.7549, -104.9740),
    "98101": (47.6107, -122.3370), "98004": (47.6147, -122.1925),
    "98109": (47.6317, -122.3473), "98121": (47.6149, -122.3447),
    "98103": (47.6731, -122.3417), "98105": (47.6624, -122.3000),
    "98107": (47.6695, -122.3782),
    "32801": (28.5400, -81.3800),  "32803": (28.5550, -81.3450),
    "48201": (42.3470, -83.0570),  "48226": (42.3300, -83.0480),
    "48197": (42.2410, -83.6133),
    "77590": (29.3838, -94.9027),  "15108": (40.5083, -80.2042),
    "24517": (37.1232, -79.2870),  "49706": (45.4434, -84.7825),
    "01970": (42.5195, -70.8967),  "01930": (42.6159, -70.6620),
    "02360": (41.9584, -70.6673),  "01945": (42.5001, -70.8578),
    "19103": (39.9525, -75.1690),
    "94102": (37.7796, -122.4192), "94103": (37.7720, -122.4115),
    "94108": (37.7920, -122.4070),
    "70112": (29.9550, -90.0750),  "70130": (29.9450, -90.0700),
    "33602": (27.9450, -82.4570),  "33401": (26.7160, -80.0530),
    "63101": (38.6300, -90.1900),  "55401": (44.9850, -93.2700),
    "75201": (32.7830, -96.8000),  "77002": (29.7600, -95.3700),
    "78701": (30.2710, -97.7430),  "02134": (42.3550, -71.1350),
    "15212": (40.4530, -80.0080),  "15213": (40.4444, -79.9608),
}


def _haversine_mi(lat1, lng1, lat2, lng2):
    """Great-circle distance in miles between two coordinates."""
    R = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = p2 - p1
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# Natural-language patterns lifted from real Google Maps search behaviour.
_ZIP_RE = re.compile(r"\b(\d{5})\b")
_NEAR_RE = re.compile(
    r"\b(?:near(?:est)?(?:\s+to)?|close\s+to|next\s+to|by|around|in)\s+"
    r"([A-Za-z][A-Za-z0-9'\-\.& ]{2,80}?)"
    r"(?=\s*(?:\?|$|,|\.|;|with|and|for|that|in\b))",
    re.I,
)


# Full US state names → abbreviations.  When a query says "in Washington" /
# "in the state of Washington" / "Washington State", we should add a state
# filter (`state=WA`) instead of treating "Washington" as a place-name
# location anchor — otherwise the resolver would geocode to some random
# "Washington Square" in NYC.
_US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}


def _detect_state_in_query(q):
    """Return (state_code, cleaned_q) if a US state is referenced in q.
    Matches:
      - "in <state-name>", "in the state of <state-name>", "<state-name> state"
      - ", <ABBR>" / " <ABBR>" trailing 2-letter state code (e.g. "Atlanta, GA")
    Returns (None, q) if no state is detected.
    """
    if not q:
        return None, q
    qlc = q.lower()
    # Multi-word state names first (longest match wins) for natural-lang.
    sorted_states = sorted(_US_STATES.items(), key=lambda kv: -len(kv[0]))
    for name, abbr in sorted_states:
        for pat in (
            rf"\bin\s+the\s+state\s+of\s+{re.escape(name)}\b",
            rf"\b{re.escape(name)}\s+state\b",
            rf"\bin\s+{re.escape(name)}\b",
        ):
            m = re.search(pat, qlc)
            if m:
                cleaned = (q[:m.start()] + " " + q[m.end():]).strip()
                cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.")
                return abbr, cleaned
    # 2-letter state abbreviation as a trailing token (with or without
    # comma): "Atlanta, GA" / "Boston MA" / "Seattle WA". Only match
    # known state codes — don't grab arbitrary 2-letter words.
    valid_abbrs = set(_US_STATES.values())
    m = re.search(r",?\s+([A-Z]{2})\s*$", q.strip())
    if m and m.group(1) in valid_abbrs:
        abbr = m.group(1)
        cleaned = q[:m.start()].strip(" ,")
        return abbr, cleaned
    return None, q


def _resolve_anchor_term(term):
    """Resolve a free-text term to (lat, lng, label).
    Priority is chosen so semantically equivalent queries converge to
    the same anchor:
      1. 5-digit zip → centroid
      2. EXACT City match → city centroid (so "Chicago" / "in Chicago"
         both anchor on Chicago city, not a random Place containing
         the substring "chicago")
      3. EXACT Place name match → that Place
      4. Substring Place match → top-reviewed match
      5. Fuzzy City match → city centroid
    """
    term = (term or "").strip(" ,.\"'")
    if not term:
        return None
    # 1) zip
    if re.fullmatch(r"\d{5}", term):
        if term in _ZIP_CENTROIDS:
            lat, lng = _ZIP_CENTROIDS[term]
            return (lat, lng, term)
        p = Place.query.filter(Place.zip_code == term, Place.lat != 0).first()
        if p:
            return (p.lat, p.lng, term)
        return None
    slug = term.lower().replace(" ", "-")
    # 2) exact City — fixes inconsistency where "in Chicago" picked a
    #    Place containing 'chicago' as substring while bare "Chicago"
    #    picked the City centroid (different anchor → different radius
    #    filter → different result counts).
    c = (City.query
         .filter(or_(City.display_name.ilike(term),
                     City.display_name.ilike(f"{term},%"),
                     City.slug == slug))
         .first())
    if c and c.lat and c.lng:
        return (c.lat, c.lng, c.display_name)
    # 3) exact Place name
    p = (Place.query
         .filter(Place.name.ilike(term), Place.lat != 0)
         .order_by(Place.is_featured.desc(), Place.review_count.desc())
         .first())
    if p:
        return (p.lat, p.lng, p.name)
    # 4) substring Place
    p = (Place.query
         .filter(Place.name.ilike(f"%{term}%"), Place.lat != 0)
         .order_by(Place.is_featured.desc(), Place.review_count.desc())
         .first())
    if p:
        return (p.lat, p.lng, p.name)
    # 5) fuzzy City
    c = (City.query
         .filter(City.display_name.ilike(f"%{term}%"))
         .first())
    if c and c.lat and c.lng:
        return (c.lat, c.lng, c.display_name)
    return None


def _resolve_location_anchor(q, args):
    """Find a (cleaned_q, lat, lng, label) anchor for distance-bias search.
    Priority: explicit ?near= > 5-digit zip in query > 'near X' phrase > None.
    Returns (cleaned_q, None, None, None) if no anchor."""
    explicit = args.get("near", "").strip()
    if explicit:
        a = _resolve_anchor_term(explicit)
        if a:
            return q, a[0], a[1], a[2]
    if not q:
        return q, None, None, None
    m = _ZIP_RE.search(q)
    if m:
        z = m.group(1)
        a = _resolve_anchor_term(z)
        if a:
            cleaned = (q[:m.start()] + q[m.end():]).strip(" ,")
            # Important: return EMPTY cleaned (not q) when the zip is the
            # only content.  Otherwise /search re-tokenises "33139" and
            # only matches the single Place whose zip_code='33139',
            # leaking the answer for "Find X near 33139" tasks.
            return cleaned, a[0], a[1], a[2]
    m = _NEAR_RE.search(q)
    if m:
        a = _resolve_anchor_term(m.group(1))
        if a:
            cleaned = q[:m.start()].strip(" ,")
            return cleaned, a[0], a[1], a[2]
    # Bare city name anywhere in the query: scan for the longest token
    # span that exactly matches a City.display_name or City.slug.  This
    # makes "Target stores Atlanta" behave the same as "Target stores in
    # Atlanta" — both extract the city as an anchor instead of letting
    # 'atlanta' bleed through as a substring token that pulls in
    # unrelated places (e.g. Atlanta-named pizza joints).
    words = q.split()
    for span in range(min(4, len(words)), 0, -1):
        for i in range(len(words) - span + 1):
            phrase = " ".join(words[i:i + span])
            slug = phrase.lower().replace(" ", "-")
            c = (City.query
                 .filter(or_(City.display_name.ilike(phrase),
                             City.display_name.ilike(f"{phrase},%"),
                             City.slug == slug))
                 .first())
            if c and c.lat and c.lng:
                cleaned = " ".join(words[:i] + words[i + span:]).strip(" ,")
                return cleaned, c.lat, c.lng, c.display_name
    return q, None, None, None


def _apply_place_filters(query, args):
    """Apply query-param filters to a Place query."""
    city = args.get("city", "").strip()
    if city:
        c = City.query.filter(
            or_(City.slug == city.lower().replace(" ", "-"),
                City.display_name.ilike(f"%{city}%"))).first()
        if c:
            query = query.filter(Place.city_id == c.id)
    state = args.get("state", "").strip()
    if state:
        query = query.filter(Place.state.ilike(f"%{state}%"))
    zip_code = args.get("zip", "").strip()
    if zip_code:
        query = query.filter(Place.zip_code == zip_code)
    category = args.get("category", "").strip()
    if category:
        cat = Category.query.filter_by(slug=category.lower()).first()
        if cat:
            query = query.filter(Place.category_id == cat.id)
    subcategory = args.get("subcategory", "").strip()
    if subcategory:
        query = query.filter(Place.subcategory.ilike(f"%{subcategory}%"))
    chain = args.get("chain", "").strip()
    if chain:
        query = query.filter(Place.chain_brand.ilike(f"%{chain}%"))
    try:
        min_rating = float(args.get("min_rating", "") or 0)
    except ValueError:
        min_rating = 0
    if min_rating:
        query = query.filter(Place.rating >= min_rating)
    try:
        min_reviews = int(args.get("min_reviews", "") or 0)
    except ValueError:
        min_reviews = 0
    if min_reviews:
        query = query.filter(Place.review_count >= min_reviews)
    open_24h = args.get("open_24h", "")
    if open_24h in ("1", "true", "yes"):
        query = query.filter(Place.is_24h.is_(True))
    if open_24h in ("0", "false", "no"):
        query = query.filter(Place.is_24h.is_(False))
    closes_at_night = args.get("closes_at_night", "")
    if closes_at_night in ("1", "true", "yes"):
        query = query.filter(Place.closes_at_night.is_(True))
    open_now = args.get("open_now", "")
    if open_now in ("1", "true", "yes"):
        query = query.filter(Place.is_open_now.is_(True))
    # Unified "Hours" chip used by the search page filter row.
    # Mutually exclusive: open_now | 24h.
    hours = args.get("hours", "").strip().lower()
    if hours == "open_now":
        query = query.filter(Place.is_open_now.is_(True))
    elif hours in ("24h", "open_24h", "open24h"):
        query = query.filter(Place.is_24h.is_(True))
    # "Price" chip — exact match on price_level ($, $$, $$$, $$$$)
    price_level = args.get("price_level", "").strip()
    if price_level in ("$", "$$", "$$$", "$$$$"):
        query = query.filter(Place.price_level == price_level)
    has_parking_lot = args.get("has_parking_lot", "")
    if has_parking_lot in ("1", "true", "yes"):
        query = query.filter(Place.has_parking_lot.is_(True))
    ev = args.get("ev_charging", "")
    if ev in ("1", "true", "yes"):
        query = query.filter(Place.ev_charging.is_(True))
    moto = args.get("motorcycle_parking", "")
    if moto in ("1", "true", "yes"):
        query = query.filter(Place.motorcycle_parking.is_(True))
    bike = args.get("bicycle_parking", "")
    if bike in ("1", "true", "yes"):
        query = query.filter(Place.bicycle_parking.is_(True))
    tag = args.get("tag", "").strip()
    if tag:
        query = query.filter(Place.tags_json.ilike(f"%{tag.lower()}%"))
    amenity = args.get("amenity", "").strip()
    if amenity:
        query = query.filter(Place.amenities_json.ilike(f"%{amenity.lower()}%"))
    return query


def _apply_place_sort(results, sort):
    if sort == "rating":
        results.sort(key=lambda p: (-(p.rating or 0), -(p.review_count or 0)))
    elif sort == "reviews":
        results.sort(key=lambda p: -(p.review_count or 0))
    elif sort == "name":
        results.sort(key=lambda p: (p.name or "").lower())
    return results


@app.route("/search")
@app.route("/maps/search/")
@app.route("/maps/search/<path:maps_query>")
def search(maps_query=""):
    q = (maps_query or request.args.get("q", "")).strip()
    sort = request.args.get("sort", "")
    args = request.args

    # Detect a US state name in the query first ("in Washington",
    # "the state of Texas").  This adds a state filter and strips the
    # phrase from the query so the location-anchor resolver doesn't try to
    # geocode the state name to some random place.
    state_filter, q_after_state = _detect_state_in_query(q)

    # Resolve a location anchor (zip / "near X" / explicit ?near=) so we can
    # distance-bias the result list, mirroring real Google Maps behaviour.
    cleaned_q, anchor_lat, anchor_lng, anchor_label = _resolve_location_anchor(
        q_after_state, args)
    # When an anchor was extracted, search_q is whatever's LEFT in the
    # query.  If nothing's left (e.g. user typed just "33139"), search_q
    # must stay empty so we don't fall back to scoring "33139" as a
    # search token — that would only match the single Place that happens
    # to have zip_code='33139', leaking the answer for "Find X near
    # 33139" tasks.  Instead an empty search_q falls into the
    # "browse-by-anchor" branch below (top results by rating within
    # radius), which mirrors typing just a zip on real Google Maps.
    if anchor_lat is not None:
        search_q = cleaned_q  # may be ""
    else:
        search_q = q_after_state or q

    query = Place.query
    query = _apply_place_filters(query, args)
    if state_filter:
        query = query.filter(Place.state == state_filter)
    candidates = query.limit(2000).all()

    # Apply anchor radius filter EARLY (before token scoring + top-60
    # truncation) so semantically equivalent queries converge.  Without
    # this, "parking in Chicago" (no state) scored 768 places globally,
    # took top-60 by score (many non-Chicago), then radius-filtered down
    # to a handful — while "parking Chicago, IL" (state=IL filter) only
    # had ~30 candidates to begin with so its top-60 already covered all
    # of them.  Same intent → same candidate pool now.
    if anchor_lat is not None and anchor_lng is not None:
        radius_mi_pre = float(request.args.get("radius", 100))
        candidates = [
            p for p in candidates
            if p.lat and p.lng
            and _haversine_mi(anchor_lat, anchor_lng, p.lat, p.lng) <= radius_mi_pre
        ]

    tokens = _tokenize(search_q)

    if search_q and tokens:
        min_required = max(1, (len(tokens) + 1) // 2)
        scored = []
        for p in candidates:
            s = _score_place(p, tokens)
            if s >= min_required:
                scored.append((s, p))
        if not scored:
            for p in candidates:
                s = _score_place(p, tokens)
                if s >= 1:
                    scored.append((s, p))
        # Fuzzy LIKE fallback: if the tokenized scorer found nothing
        # (vague queries like "large store washington" where "large"
        # matches no haystack word), do a SQL LIKE sweep on the full
        # cleaned query and on each token across name/description/
        # address/city/subcategory.  This is real-Google-Maps fuzzy
        # behaviour — a query that doesn't perfectly match anything
        # still gets the most-relevant nearby matches.
        if not scored:
            full_lc = search_q.strip().lower()
            patterns = []
            if full_lc:
                patterns.append(f"%{full_lc}%")
            for t in tokens:
                if len(t) >= 3:
                    patterns.append(f"%{t}%")
            for p in candidates:
                hay = " ".join([
                    (p.name or ""), (p.subtitle or ""),
                    (p.description or ""), (p.address or ""),
                    (p.subcategory or ""), (p.chain_brand or ""),
                    (p.tags_json or ""), (p.amenities_json or ""),
                    (p.city.display_name if p.city else ""),
                    (p.category.name if p.category else ""),
                ]).lower()
                hits = sum(1 for pat in patterns
                           if pat.strip("%") in hay)
                if hits:
                    scored.append((hits, p))
        scored.sort(key=lambda x: (-x[0], -(x[1].rating or 0)))
        results = [p for _, p in scored][:60]
    else:
        # No tokens (state-only or zip-only query like "in Washington" or
        # "33139").  When an anchor is set, use a TIGHTER 30-mi browse
        # radius (vs the 100-mi search radius) so adjacent zips don't
        # bleed into each other — typing just a zip on real Google Maps
        # zooms to that immediate area, not a 100-mi sweep.  Then
        # rating-sort within radius.
        if anchor_lat is not None and anchor_lng is not None:
            r0 = float(request.args.get("radius", 30))
            in_area = []
            for p in candidates:
                if p.lat and p.lng:
                    d = _haversine_mi(anchor_lat, anchor_lng, p.lat, p.lng)
                    if d <= r0:
                        in_area.append(p)
            in_area.sort(key=lambda p: (-(p.rating or 0), -(p.review_count or 0)))
            results = in_area[:60]
        else:
            candidates.sort(key=lambda p: (-(p.rating or 0), -(p.review_count or 0)))
            results = candidates[:60]

    # When an anchor is set, attach distance + filter to a wide radius so
    # totally unrelated far-away results don't pollute, but DO NOT sort
    # purely by distance — that would let an agent solve every "nearest X"
    # task by clicking result #1.  Real Google Maps blends rating,
    # popularity, and distance.  We keep the existing token-score order
    # (which already factors rating); the agent must read distance pills
    # and compare to find the actual closest match.
    if anchor_lat is not None and anchor_lng is not None:
        radius_mi = float(request.args.get("radius", 100))
        kept = []
        for p in results:
            if p.lat and p.lng:
                p.distance_mi = _haversine_mi(
                    anchor_lat, anchor_lng, p.lat, p.lng)
                if p.distance_mi <= radius_mi:
                    kept.append(p)
            else:
                p.distance_mi = None
                kept.append(p)
        results = kept
        if sort == "distance":
            results.sort(key=lambda p: (
                p.distance_mi if p.distance_mi is not None else 1e9))
    else:
        for p in results:
            p.distance_mi = None

    if sort and sort != "distance":
        results = _apply_place_sort(results, sort)
    elif tokens:
        pass
    elif anchor_lat is None:
        results.sort(key=lambda p: (-(p.rating or 0), -(p.review_count or 0)))

    return render_template(
        "search.html", q=q, results=results,
        anchor_label=anchor_label, anchor_lat=anchor_lat, anchor_lng=anchor_lng,
    )


# ---------------------------------------------------------------------------
# Synthesised multi-route alternatives.  Real Google Maps offers 2-3 route
# choices per directions query (Fastest / Slightly longer / Scenic) with
# region-appropriate highway or street names; the mirror approximates this
# without a real routing engine by deriving plausible names from the
# endpoints' US state and combining with mode-aware speed models.
# ---------------------------------------------------------------------------
_REGION_HIGHWAYS = {
    "CA": ["I-5", "US-101", "I-405", "I-10", "I-110", "CA-1 (PCH)"],
    "NY": ["I-95", "I-87 (Major Deegan)", "I-278 (BQE)", "I-495 (LIE)",
           "FDR Drive", "West Side Hwy"],
    "MA": ["I-93", "I-90 (Mass Pike)", "US-1", "MA-2", "MA-3"],
    "IL": ["I-90", "I-94 (Edens)", "I-55", "I-290 (Eisenhower)",
           "Lake Shore Dr"],
    "TX": ["I-35", "I-10", "I-45", "US-290"],
    "GA": ["I-75", "I-85", "I-285", "I-20"],
    "FL": ["I-95", "I-75", "I-4", "FL-A1A"],
    "WA": ["I-5", "I-90", "WA-99", "WA-520"],
    "DC": ["I-395", "I-695", "Constitution Ave NW", "Independence Ave SW"],
    "MI": ["I-75", "I-94", "I-696"],
    "PA": ["I-376 (Parkway W)", "I-79", "I-279"],
    "VA": ["I-95", "I-66", "US-29"],
    "CO": ["I-25", "I-70", "US-285"],
    "OH": ["I-90", "I-71", "I-77"],
    "MN": ["I-94", "I-35W", "US-12"],
    "LA": ["I-10", "I-610", "US-90"],
    "default": ["I-5", "US-1", "I-95"],
}
_REGION_STREETS = {
    "NY": ["5th Ave", "Broadway", "7th Ave", "Madison Ave", "Park Ave",
           "Lexington Ave"],
    "CA": ["Sunset Blvd", "Wilshire Blvd", "Hollywood Blvd", "Beverly Blvd",
           "Santa Monica Blvd"],
    "MA": ["Beacon St", "Boylston St", "Washington St", "Tremont St"],
    "DC": ["Constitution Ave", "Independence Ave", "Pennsylvania Ave",
           "K Street"],
    "IL": ["Michigan Ave", "State St", "Wacker Dr"],
    "FL": ["Ocean Dr", "Collins Ave", "Biscayne Blvd"],
    "WA": ["Pike St", "Pine St", "Westlake Ave"],
    "TX": ["Congress Ave", "Lamar Blvd", "South 1st St"],
    "GA": ["Peachtree St", "North Ave", "Ponce de Leon Ave"],
    "MI": ["Woodward Ave", "Michigan Ave", "Jefferson Ave"],
    "default": ["Main St", "Park Ave", "Broadway"],
}
_CROSS_COUNTRY_HIGHWAYS = ["I-80 W", "I-90 W", "I-70 W", "I-40 W",
                           "Historic Route 66"]


def _state_from_endpoint(ep):
    """Best-effort US state code from an endpoint.  Coords win first
    (bbox lookup), then address parsing as a fallback for international
    / sparse-coords cases."""
    if not ep:
        return "default"
    lat, lng = ep.get("lat"), ep.get("lng")
    if lat and lng:
        s = _state_from_coords(lat, lng)
        if s != "default":
            return s
    addr = (ep.get("address") or "").upper()
    m = re.search(r",\s*([A-Z]{2})\s+\d{5}", addr) \
        or re.search(r",\s*([A-Z]{2})\s*$", addr) \
        or re.search(r"\b([A-Z]{2})\s+\d{5}", addr)
    if m:
        return m.group(1)
    return "default"


def _mode_speed_mph(mode, distance_mi):
    """Mode + distance aware travel speed (mph).  Real-world averages:
    short trips spend more time at intersections and pick-ups; long
    trips ride highways and average closer to posted speed minus stop
    overhead.  Cross-country drives include rest breaks (~60 mph avg).
    """
    if mode == "walking":
        return 3.0
    if mode == "bicycling":
        return 12.0
    if mode == "transit":
        if distance_mi < 10:
            return 18.0   # subway / city bus
        if distance_mi < 100:
            return 35.0   # commuter rail
        if distance_mi < 500:
            return 55.0   # regional rail (e.g. Amtrak Northeast)
        return 60.0       # intercity rail
    # driving (also fallback for unknown mode)
    if distance_mi < 5:
        return 22.0       # dense city
    if distance_mi < 30:
        return 32.0       # suburban / city mix
    if distance_mi < 100:
        return 50.0       # highway with city overhead
    if distance_mi < 500:
        return 60.0       # interstate
    return 60.0           # cross-country incl. rest breaks


# Approximate US-state bounding boxes for lat/lng → state inference.
# Derived from public WGS84 state extents.  Order matters when boxes
# overlap — first match wins, so put smaller / more-specific states
# (DC, RI, NJ, …) ahead of bigger neighbours.
_STATE_BBOXES = [
    ("DC", 38.79, 38.99, -77.12, -76.91),
    ("HI", 18.91, 22.24, -160.25, -154.81),
    ("AK", 51.21, 71.40, -179.15, -129.99),
    ("RI", 41.15, 42.02, -71.86, -71.12),
    ("DE", 38.45, 39.84, -75.79, -75.05),
    ("NJ", 38.93, 41.36, -75.56, -73.89),
    ("CT", 40.99, 42.05, -73.73, -71.79),
    ("MA", 41.24, 42.89, -73.51, -69.93),
    ("VT", 42.73, 45.02, -73.44, -71.46),
    ("NH", 42.69, 45.31, -72.56, -70.61),
    ("ME", 42.97, 47.46, -71.08, -66.95),
    ("NY", 40.50, 45.02, -79.76, -71.86),
    ("PA", 39.72, 42.27, -80.52, -74.69),
    ("MD", 37.91, 39.72, -79.49, -75.05),
    ("VA", 36.54, 39.47, -83.68, -75.24),
    ("WV", 37.20, 40.64, -82.64, -77.72),
    ("OH", 38.40, 41.98, -84.82, -80.52),
    ("MI", 41.70, 48.30, -90.42, -82.41),
    ("IN", 37.77, 41.76, -88.10, -84.78),
    ("IL", 36.97, 42.51, -91.51, -87.50),
    ("WI", 42.49, 47.08, -92.89, -86.81),
    ("MN", 43.50, 49.38, -97.24, -89.49),
    ("IA", 40.38, 43.50, -96.64, -90.14),
    ("MO", 35.99, 40.61, -95.77, -89.10),
    ("KY", 36.50, 39.15, -89.57, -81.96),
    ("TN", 34.98, 36.68, -90.31, -81.65),
    ("NC", 33.84, 36.59, -84.32, -75.46),
    ("SC", 32.03, 35.22, -83.35, -78.54),
    ("GA", 30.36, 35.00, -85.61, -80.84),
    ("FL", 24.50, 31.00, -87.63, -80.03),
    ("AL", 30.22, 35.01, -88.47, -84.89),
    ("MS", 30.17, 35.00, -91.66, -88.10),
    ("AR", 33.00, 36.50, -94.62, -89.64),
    ("LA", 28.92, 33.02, -94.04, -88.82),
    ("OK", 33.62, 37.00, -103.00, -94.43),
    ("TX", 25.84, 36.50, -106.65, -93.51),
    ("NM", 31.33, 37.00, -109.05, -103.00),
    ("KS", 36.99, 40.00, -102.05, -94.59),
    ("NE", 40.00, 43.00, -104.05, -95.31),
    ("SD", 42.48, 45.94, -104.06, -96.44),
    ("ND", 45.94, 49.00, -104.05, -96.55),
    ("MT", 44.36, 49.00, -116.05, -104.04),
    ("WY", 41.00, 45.01, -111.05, -104.05),
    ("CO", 36.99, 41.00, -109.06, -102.04),
    ("UT", 36.99, 42.00, -114.05, -109.05),
    ("ID", 41.99, 49.00, -117.24, -111.04),
    ("WA", 45.54, 49.00, -124.85, -116.92),
    ("OR", 41.99, 46.30, -124.57, -116.46),
    ("NV", 35.00, 42.00, -120.01, -114.04),
    ("AZ", 31.33, 37.00, -114.82, -109.05),
    ("CA", 32.50, 42.01, -124.48, -114.13),
]


def _state_from_coords(lat, lng):
    """Best-effort US state from (lat, lng).  Returns 2-letter code or
    'default' for international / unmappable points."""
    if lat is None or lng is None:
        return "default"
    for code, latlo, lathi, lnglo, lnghi in _STATE_BBOXES:
        if latlo <= lat <= lathi and lnglo <= lng <= lnghi:
            return code
    return "default"


def _state_pretty(code):
    """Render state code for human consumption ('CA' → 'California')."""
    inv = {v: k for k, v in _US_STATES.items()}
    return inv.get(code, code).title()


def _fmt_distance(mi):
    return f"{mi:.1f} mi" if mi < 100 else f"{mi:.0f} mi"


def _fmt_duration(mins):
    if mins < 60:
        return f"{mins} min"
    h, m = divmod(mins, 60)
    if h < 24:
        return f"{h} h {m} min" if m else f"{h} h"
    d, h = divmod(h, 24)
    return f"{d} d {h} h"


def _synth_steps(from_ep, to_ep, route_name, mode, distance_mi):
    """Step-by-step instruction synthesiser.  Step count + content scale
    with distance — short trips get a couple of turns; cross-country
    trips get multi-state segments mentioning intermediate states."""
    steps = [{"instruction": f"Head out from {from_ep['name']}",
              "distance": "0.0 mi"}]
    bare = route_name.replace("via ", "").split(" (")[0]
    from_st = _state_from_endpoint(from_ep)
    to_st = _state_from_endpoint(to_ep)

    if mode == "transit":
        # walk → board → ride → disembark → walk
        steps.append({"instruction": f"Walk to nearest {bare} station",
                      "distance": f"{distance_mi * 0.05:.1f} mi"})
        if distance_mi > 100:
            steps.append({"instruction": f"Board {bare} (long-haul service)",
                          "distance": f"{distance_mi * 0.85:.0f} mi"})
            steps.append({"instruction": f"Transfer at intermediate hub",
                          "distance": "0.0 mi"})
        else:
            steps.append({"instruction": f"Board {bare} line",
                          "distance": f"{distance_mi * 0.85:.1f} mi"})
        steps.append({"instruction": f"Disembark and walk to destination",
                      "distance": f"{distance_mi * 0.10:.1f} mi"})
    elif distance_mi > 500:
        # cross-country: 4-segment haul through intermediate states
        seg = distance_mi / 3
        from_pretty = _state_pretty(from_st) if from_st != "default" else "your origin"
        to_pretty = _state_pretty(to_st) if to_st != "default" else "your destination"
        steps.append({"instruction": f"Merge onto {bare} heading away from {from_pretty}",
                      "distance": f"{distance_mi * 0.05:.0f} mi"})
        steps.append({"instruction": f"Continue on {bare} for the long haul",
                      "distance": f"{seg:.0f} mi"})
        steps.append({"instruction": f"Stop for fuel / rest along the route",
                      "distance": "0.5 mi"})
        steps.append({"instruction": f"Continue on {bare}",
                      "distance": f"{seg:.0f} mi"})
        steps.append({"instruction": f"Approach {to_pretty} and follow signs to destination",
                      "distance": f"{seg:.0f} mi"})
    elif distance_mi > 30:
        steps.append({"instruction": f"Merge onto {bare}",
                      "distance": f"{distance_mi * 0.10:.1f} mi"})
        steps.append({"instruction": f"Continue on {bare}",
                      "distance": f"{distance_mi * 0.75:.1f} mi"})
        steps.append({"instruction": f"Take exit toward {to_ep['name']}",
                      "distance": f"{distance_mi * 0.15:.1f} mi"})
    else:
        steps.append({"instruction": f"Turn onto {bare}",
                      "distance": f"{distance_mi * 0.4:.1f} mi"})
        steps.append({"instruction": f"Continue {bare} toward destination",
                      "distance": f"{distance_mi * 0.5:.1f} mi"})
    steps.append({"instruction": f"Arrive at {to_ep['name']}",
                  "distance": "0.0 mi"})
    return steps


def _generate_route_alternatives(from_ep, to_ep, mode):
    """2-3 plausible route alternatives between two endpoints.  Each gets
    a slightly perturbed distance/duration and a region-flavoured name."""
    base_mi = _haversine_mi(from_ep["lat"], from_ep["lng"],
                            to_ep["lat"], to_ep["lng"])
    from_st = _state_from_endpoint(from_ep)
    to_st = _state_from_endpoint(to_ep)
    same_state = (from_st == to_st and from_st != "default")

    if mode in ("walking", "bicycling"):
        names_pool = _REGION_STREETS.get(from_st, _REGION_STREETS["default"])
    elif not same_state and base_mi > 800:
        # True cross-country only when both states differ AND distance
        # is large enough to rule out a within-state highway like
        # LAX → SFO (333 mi, both CA).
        names_pool = _CROSS_COUNTRY_HIGHWAYS
    else:
        names_pool = _REGION_HIGHWAYS.get(from_st, _REGION_HIGHWAYS["default"])

    # (multiplier, name_index) — no superlative tag.  The agent must
    # compare duration_label / distance_label across alternatives to
    # identify the shortest route; we don't pre-tag #1 as "Fastest".
    variants = [(1.00, 0), (1.12, 1), (1.30, 2)]
    alts = []
    for i, (mult, idx) in enumerate(variants):
        if idx >= len(names_pool):
            continue
        d_mi = base_mi * mult
        speed = _mode_speed_mph(mode, d_mi)
        d_min = max(1, int(round(d_mi / speed * 60)))
        name = f"via {names_pool[idx]}"
        alts.append({
            "id": chr(ord("a") + i),
            "name": name,
            "distance_mi": d_mi,
            "distance_label": _fmt_distance(d_mi),
            "duration_min": d_min,
            "duration_label": _fmt_duration(d_min),
            "tag": "",
            "steps": _synth_steps(from_ep, to_ep, name, mode, d_mi),
            "summary": f"{from_ep['name']} → {to_ep['name']} via {names_pool[idx]}",
        })
    return alts


_ZIP_AREA_RE = re.compile(r"^(\d{5})\s*\(zip\s*area\)\s*$", re.I)
_CITY_CENTER_RE = re.compile(r"^(.+?)\s*\(city\s*center\)\s*$", re.I)


def _is_specific_endpoint(term):
    """A term is 'specific' when it unambiguously names ONE location for
    /directions purposes: an exact Place name, an exact City name, or
    the 'NNNNN (zip area)' label that the picker emits when the user
    confirms they meant the zip centroid (not a place inside the zip).

    A bare 5-digit zip is NOT considered specific — the user should
    still get a picker so they can choose between "the zip area
    centroid" and a specific named place inside the zip.
    """
    term = (term or "").strip(" ,.\"'")
    if not term:
        return True
    if _ZIP_AREA_RE.match(term):
        return True
    if _CITY_CENTER_RE.match(term):
        return True
    if Place.query.filter(Place.name.ilike(term)).first():
        return True
    slug = term.lower().replace(" ", "-")
    # City match — accept exact display_name ("Boston"), comma-prefix
    # ("Miami" → "Miami, FL"), or slug ("miami-fl").  All three forms
    # resolve to one city centroid, so they're unambiguous.
    if City.query.filter(or_(City.display_name.ilike(term),
                             City.display_name.ilike(f"{term},%"),
                             City.slug == slug)).first():
        return True
    return False


def _endpoint_candidates(term, anchor_lat=None, anchor_lng=None, max_n=8):
    """Return up to max_n candidate endpoint dicts for an ambiguous term,
    ranked by distance from anchor (if provided) else by popularity.
    Each dict: {lat, lng, name, address, place_id, slug, distance_mi}."""
    term = (term or "").strip(" ,.\"'")
    if not term:
        return []

    # Term matches a US city → prepend "<City> (city center)" so the
    # user can route between city centroids ("Miami → Orlando") instead
    # of being forced to pick a specific Place inside the city.  Match
    # both bare city ("Miami") and city + state ("Miami, FL") forms.
    cc_pre = []
    cc_slug = term.lower().replace(" ", "-").rstrip(",")
    cc_city = (City.query
               .filter(or_(City.display_name.ilike(term),
                           City.display_name.ilike(f"{term},%"),
                           City.slug == cc_slug))
               .first())
    if cc_city and cc_city.lat and cc_city.lng:
        d = (_haversine_mi(anchor_lat, anchor_lng, cc_city.lat, cc_city.lng)
             if anchor_lat is not None and anchor_lng is not None else None)
        cc_pre.append({
            "lat": cc_city.lat, "lng": cc_city.lng,
            "name": f"{cc_city.display_name} (city center)",
            "address": cc_city.display_name, "place_id": None,
            "slug": cc_city.slug,
            "rating": None, "review_count": None,
            "category_name": "City", "distance_mi": d,
        })

    # Bare 5-digit zip → first candidate is the zip-area centroid (so the
    # user can route from "the 33139 area" generically), followed by top
    # named places that actually live in that zip.
    if re.fullmatch(r"\d{5}", term):
        out = []
        if term in _ZIP_CENTROIDS:
            zlat, zlng = _ZIP_CENTROIDS[term]
            d = (_haversine_mi(anchor_lat, anchor_lng, zlat, zlng)
                 if anchor_lat is not None and anchor_lng is not None else None)
            out.append({
                "lat": zlat, "lng": zlng, "name": f"{term} (zip area)",
                "address": f"ZIP {term} centroid", "place_id": None, "slug": term,
                "rating": None, "review_count": None,
                "category_name": "Area", "distance_mi": d,
            })
        in_zip = (Place.query.filter(Place.zip_code == term, Place.lat != 0)
                  .order_by(Place.is_featured.desc(), Place.review_count.desc())
                  .limit(max_n - len(out)).all())
        for p in in_zip:
            d = (_haversine_mi(anchor_lat, anchor_lng, p.lat, p.lng)
                 if anchor_lat is not None and anchor_lng is not None else None)
            out.append({
                "lat": p.lat, "lng": p.lng, "name": p.name,
                "address": p.address or "", "place_id": p.id, "slug": p.slug,
                "rating": p.rating, "review_count": p.review_count,
                "category_name": p.category.name if p.category else "",
                "distance_mi": d,
            })
        return cc_pre + out

    term_lc = term.lower()
    cat = (Category.query
           .filter(or_(Category.slug == term_lc,
                       Category.slug == term_lc + "s",
                       Category.slug.startswith(term_lc),
                       Category.name.ilike(f"%{term}%")))
           .first())
    cat_id = cat.id if cat else -1
    cands = (Place.query.filter(Place.lat != 0).filter(or_(
        Place.name.ilike(f"%{term}%"),
        Place.subcategory.ilike(f"%{term}%"),
        Place.chain_brand.ilike(f"%{term}%"),
        Place.tags_json.ilike(f"%{term_lc}%"),
        Place.category_id == cat_id,
    )).limit(500).all())
    # Token-overlap fallback: catches multi-word inputs whose word order
    # differs from the canonical name ("Pittsburgh Airport" → "Pittsburgh
    # International Airport").
    toks = set(_tokenize(term))
    if toks:
        seen = {p.id for p in cands}
        for p in (Place.query.filter(Place.lat != 0).limit(2000).all()):
            if p.id in seen:
                continue
            haystack = " ".join([
                (p.name or ""), (p.subcategory or ""),
                (p.chain_brand or ""),
                (p.category.name if p.category else ""),
                (p.category.slug if p.category else ""),
            ])
            pt = set(_tokenize(haystack))
            if len(toks & pt) >= max(1, (len(toks) + 1) // 2):
                cands.append(p)
    # Score: token-on-name first, then token-on-haystack, then rating ×
    # log(reviews).  NEVER sort by distance — that puts the "closest X to
    # Y" answer at the top and lets the agent solve by clicking #1.
    def _sk(p):
        name_lc = (p.name or "").lower()
        hay_lc = " ".join([
            (p.subcategory or "").lower(),
            (p.chain_brand or "").lower(),
            (p.category.name.lower() if p.category else ""),
            (p.category.slug.lower() if p.category else ""),
        ])
        s = 0
        for t in toks:
            if t in name_lc:
                s += 3
            elif t in hay_lc:
                s += 1
        rel = (p.rating or 4.0) * math.log(max(p.review_count or 1, 1) + 2)
        return (-s, -rel)
    cands.sort(key=_sk)
    out = []
    cap = max_n - len(cc_pre)
    for p in cands[:cap]:
        d = (_haversine_mi(anchor_lat, anchor_lng, p.lat, p.lng)
             if anchor_lat is not None and anchor_lng is not None else None)
        out.append({
            "lat": p.lat, "lng": p.lng, "name": p.name,
            "address": p.address or "", "place_id": p.id, "slug": p.slug,
            "rating": p.rating, "review_count": p.review_count,
            "category_name": p.category.name if p.category else "",
            "distance_mi": d,
        })
    return cc_pre + out


def _resolve_endpoint(term, anchor_lat=None, anchor_lng=None):
    """Resolve a free-text Directions endpoint to (lat, lng, name, address).
    Falls back through: zip → famous landmark / place name → category-keyword
    → city.  When `anchor_lat/lng` is given, ambiguous matches resolve to the
    nearest candidate, matching real Google Maps' "find the closest one"
    behaviour for queries like "apple store" with a known origin.
    Returns a dict {lat, lng, name, address, place_id?} or None.
    """
    term = (term or "").strip(" ,.\"'")
    if not term:
        return None

    # 0) "<City> (city center)" label round-trip from the picker
    cc_m = _CITY_CENTER_RE.match(term)
    if cc_m:
        city_term = cc_m.group(1).strip()
        slug = city_term.lower().replace(" ", "-")
        c = (City.query
             .filter(or_(City.display_name.ilike(city_term),
                         City.display_name.ilike(f"{city_term},%"),
                         City.slug == slug))
             .first())
        if c and c.lat and c.lng:
            return {"lat": c.lat, "lng": c.lng,
                    "name": f"{c.display_name} (city center)",
                    "address": c.display_name, "place_id": None}
        return None

    # 1) 5-digit zip — bare or "NNNNN (zip area)" label from the picker
    zip_m = _ZIP_AREA_RE.match(term)
    bare_zip = re.fullmatch(r"\d{5}", term)
    if zip_m or bare_zip:
        z = zip_m.group(1) if zip_m else term
        display_name = f"{z} (zip area)" if zip_m else z
        if z in _ZIP_CENTROIDS:
            lat, lng = _ZIP_CENTROIDS[z]
            return {"lat": lat, "lng": lng, "name": display_name,
                    "address": f"ZIP {z}", "place_id": None}
        p = (Place.query.filter(Place.zip_code == z, Place.lat != 0)
             .order_by(Place.review_count.desc()).first())
        if p:
            return {"lat": p.lat, "lng": p.lng, "name": display_name,
                    "address": f"ZIP {z} ({p.address})", "place_id": p.id}
        return None

    def _to_endpoint(p):
        return {"lat": p.lat, "lng": p.lng, "name": p.name,
                "address": p.address or "", "place_id": p.id}

    # 2a) Exact City match — when the user types "Chicago" / "Los
    #     Angeles" / "Miami" they mean the city, not "Art Institute of
    #     Chicago" or "Best Buy Miami Beach".  Resolve city BEFORE
    #     substring Place match so the route summary doesn't fabricate
    #     a specific Place that wasn't requested.  Accept three forms:
    #     exact display_name, comma-prefix ("Miami" → "Miami, FL"),
    #     and slug.
    slug = term.lower().replace(" ", "-")
    city_exact = (City.query
                  .filter(or_(City.display_name.ilike(term),
                              City.display_name.ilike(f"{term},%"),
                              City.slug == slug))
                  .first())
    if city_exact and city_exact.lat and city_exact.lng:
        return {"lat": city_exact.lat, "lng": city_exact.lng,
                "name": city_exact.display_name,
                "address": city_exact.display_name, "place_id": None}

    # 2b) Direct Place name match (single best)
    direct = (Place.query
              .filter(Place.name.ilike(term), Place.lat != 0)
              .order_by(Place.is_featured.desc(), Place.review_count.desc())
              .first())
    if direct:
        return _to_endpoint(direct)

    # 3) Substring / category keyword match — collect candidates and
    #    distance-rank against anchor when available.  Also matches against
    #    the parent Category (slug + name) so "hotel" finds places under the
    #    Hotels category whose name doesn't literally contain "hotel".
    term_lc = term.lower()
    cat_match = (Category.query
                 .filter(or_(Category.slug == term_lc,
                             Category.slug == term_lc + "s",
                             Category.slug.startswith(term_lc),
                             Category.name.ilike(f"%{term}%")))
                 .first())
    cat_id = cat_match.id if cat_match else -1
    cand_query = Place.query.filter(Place.lat != 0).filter(or_(
        Place.name.ilike(f"%{term}%"),
        Place.subcategory.ilike(f"%{term}%"),
        Place.chain_brand.ilike(f"%{term}%"),
        Place.tags_json.ilike(f"%{term_lc}%"),
        Place.category_id == cat_id,
    ))
    candidates = cand_query.limit(500).all()
    if candidates:
        # Category-keyword preference: when the query contains a
        # category-naming token ("airport", "museum", "park", "bridge",
        # "stadium"), prefer Places whose CATEGORY matches that token
        # over substring-name matches.  Avoids "Pittsburgh Airport" →
        # "Marriott SpringHill Suites Pittsburgh Airport" (a hotel) just
        # because the hotel's full name contains the substring.
        _CAT_KW = {"airport": "airports", "museum": "museums",
                   "park": "parks", "bridge": "attractions",
                   "stadium": "entertainment", "garden": "attractions",
                   "temple": "attractions", "trail": "trails"}
        for kw, cat_slug in _CAT_KW.items():
            if kw in term_lc.split():
                pref_cat = Category.query.filter_by(slug=cat_slug).first()
                if pref_cat:
                    pref_hits = [p for p in candidates if p.category_id == pref_cat.id]
                    if pref_hits:
                        # Replace candidate pool with preferred-cat hits only;
                        # subsequent sort then picks the best within that
                        # category instead of letting a hotel beat the airport
                        # by review count.
                        candidates = pref_hits
                    break
        if anchor_lat is not None and anchor_lng is not None:
            candidates.sort(key=lambda p: _haversine_mi(
                anchor_lat, anchor_lng, p.lat, p.lng))
        else:
            candidates.sort(key=lambda p: -(p.review_count or 0))
        return _to_endpoint(candidates[0])

    # 4) Token overlap with name (for multi-word inputs whose ILIKE missed)
    toks = set(_tokenize(term))
    if toks:
        scored = []
        for p in Place.query.filter(Place.lat != 0).limit(2000).all():
            pt = set(_tokenize((p.name or "") + " " + (p.subcategory or "")
                               + " " + (p.chain_brand or "")))
            overlap = len(toks & pt)
            if overlap >= max(1, (len(toks) + 1) // 2):
                scored.append((overlap, p))
        if scored:
            if anchor_lat is not None and anchor_lng is not None:
                scored.sort(key=lambda sp: (-sp[0], _haversine_mi(
                    anchor_lat, anchor_lng, sp[1].lat, sp[1].lng)))
            else:
                scored.sort(key=lambda sp: (-sp[0], -(sp[1].review_count or 0)))
            return _to_endpoint(scored[0][1])

    # 5) City fallback
    slug = term.lower().replace(" ", "-")
    c = (City.query
         .filter(or_(City.display_name.ilike(f"%{term}%"), City.slug == slug))
         .first())
    if c and c.lat and c.lng:
        return {"lat": c.lat, "lng": c.lng, "name": c.display_name,
                "address": c.display_name, "place_id": None}

    return None


def _find_route(from_q, to_q, mode=""):
    """Find best matching Route, scored by substring overlap on both ends."""
    if not from_q or not to_q:
        return None
    from_lc = from_q.lower()
    to_lc = to_q.lower()
    candidates = Route.query.all()
    if mode:
        candidates = [r for r in candidates if r.mode == mode.lower()]
    best = None
    best_score = 0
    for r in candidates:
        rof = (r.origin_query or "").lower()
        rdf = (r.destination_query or "").lower()
        ron = (r.origin_name or "").lower()
        rdn = (r.destination_name or "").lower()
        score = 0
        # origin match
        if from_lc in rof or rof in from_lc or from_lc in ron or ron in from_lc:
            score += 2
        else:
            # token overlap
            ft = set(_tokenize(from_q))
            rt = set(_tokenize(rof + " " + ron))
            if ft & rt:
                score += 1
        if to_lc in rdf or rdf in to_lc or to_lc in rdn or rdn in to_lc:
            score += 2
        else:
            tt = set(_tokenize(to_q))
            rt = set(_tokenize(rdf + " " + rdn))
            if tt & rt:
                score += 1
        if score > best_score:
            best_score = score
            best = r
    if best_score >= 2:
        return best
    return None


@app.route("/directions")
def directions():
    from_q = request.args.get("from", "").strip()
    to_q = request.args.get("to", "").strip()
    mode = request.args.get("mode", "").strip().lower()

    from_place = None
    to_place = None
    from_endpoint = None
    to_endpoint = None
    from_candidates = []
    to_candidates = []
    route = None
    distance_km = None
    duration_min = None
    steps = []
    summary = ""
    distance_label = ""
    duration_label = ""
    mode_label = mode or "driving"

    # Picker-first design: if EITHER endpoint is a generic / ambiguous
    # query, surface a candidate picker BEFORE resolving the route.  Fires
    # whether one or both sides are filled — the user must commit to a
    # specific endpoint before we draw a route.  Distance pills on the
    # picker cards are sorted by relevance (rating × log(reviews)) so the
    # "nearest X" answer isn't handed to the agent at position #1.
    if from_q and not _is_specific_endpoint(from_q):
        to_ep_for_anchor = _resolve_endpoint(to_q) if to_q else None
        from_candidates = _endpoint_candidates(
            from_q, max_n=8,
            anchor_lat=(to_ep_for_anchor or {}).get("lat"),
            anchor_lng=(to_ep_for_anchor or {}).get("lng"),
        )
        if len(from_candidates) > 1:
            return render_template(
                "directions.html",
                from_q=from_q, to_q=to_q,
                from_candidates=from_candidates,
                pick_for="from", mode=mode_label,
            )
    if to_q and not _is_specific_endpoint(to_q):
        from_ep_for_anchor = _resolve_endpoint(from_q) if from_q else None
        to_candidates = _endpoint_candidates(
            to_q, max_n=8,
            anchor_lat=(from_ep_for_anchor or {}).get("lat"),
            anchor_lng=(from_ep_for_anchor or {}).get("lng"),
        )
        if len(to_candidates) > 1:
            return render_template(
                "directions.html",
                from_q=from_q, to_q=to_q,
                from_endpoint=from_ep_for_anchor,
                to_candidates=to_candidates,
                pick_for="to", mode=mode_label,
            )

    # Both endpoints are specific (or one missing) — resolve via the
    # endpoint resolver and let the haversine + alternatives generator
    # synthesise the route.  The legacy curated Route table was dropped
    # from this flow because its fuzzy matcher silently substituted
    # wrong destinations (e.g. asking for "Times Square" while having
    # an SFO → Union Square Route entry would match on the "Square"
    # token, returning a 23-min SF-only route for a cross-country trip).
    # Coords on every Place are now realistic enough for haversine to
    # be the source of truth.
    if from_q and to_q:
        from_endpoint = _resolve_endpoint(from_q)
        to_endpoint = _resolve_endpoint(
            to_q,
            anchor_lat=(from_endpoint or {}).get("lat"),
            anchor_lng=(from_endpoint or {}).get("lng"),
        )
        if from_endpoint is None and to_endpoint is not None:
            from_endpoint = _resolve_endpoint(
                from_q, anchor_lat=to_endpoint["lat"], anchor_lng=to_endpoint["lng"])

        if from_endpoint and to_endpoint:
            if from_endpoint.get("place_id"):
                from_place = Place.query.get(from_endpoint["place_id"])
            if to_endpoint.get("place_id"):
                to_place = Place.query.get(to_endpoint["place_id"])

    # Alternatives + selected variant — synthesised when we have both
    # endpoints (whether from a Route table hit or fresh resolution).
    alternatives = []
    selected_alt = None
    selected_alt_id = (request.args.get("route") or "a").strip().lower()
    eff_mode = mode_label or "driving"
    if from_endpoint and to_endpoint:
        alternatives = _generate_route_alternatives(
            from_endpoint, to_endpoint, eff_mode)
        for a in alternatives:
            if a["id"] == selected_alt_id:
                selected_alt = a
                break
        if alternatives and not selected_alt:
            selected_alt = alternatives[0]

    if selected_alt:
        distance_km = round(selected_alt["distance_mi"] * 1.60934, 1)
        duration_min = selected_alt["duration_min"]
        distance_label = selected_alt["distance_label"]
        duration_label = selected_alt["duration_label"]
        steps = selected_alt["steps"]
        summary = selected_alt["summary"]

    return render_template(
        "directions.html",
        from_q=from_q, to_q=to_q,
        from_place=from_place, to_place=to_place,
        from_endpoint=from_endpoint, to_endpoint=to_endpoint,
        distance_km=distance_km, duration_min=duration_min,
        route=route, steps=steps, summary=summary,
        distance_label=distance_label, duration_label=duration_label,
        mode=eff_mode,
        alternatives=alternatives, selected_alt=selected_alt,
    )


@app.route("/timeline")
@login_required
def timeline():
    entries = TimelineEntry.query.filter_by(user_id=current_user.id) \
        .order_by(TimelineEntry.visited_at.desc()).limit(50).all()
    return render_template("timeline.html", entries=entries)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/settings")
def settings():
    return render_template("settings.html")


@app.route("/help")
def help_page():
    return render_template("help.html")


# --------------------------------------------------------------------------
#  Auth
# --------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            flash(f"Welcome back, {user.name}!", "success")
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if not email or not name or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")
        if password != password2:
            flash("Passwords do not match.", "error")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("register.html")

        pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        user = User(
            email=email,
            password_hash=pw_hash,
            name=name,
            avatar_letter=(name[0] if name else "U").upper(),
        )
        db.session.add(user)
        db.session.commit()
        ensure_default_lists(user)
        login_user(user)
        flash("Account created - welcome to Maps!", "success")
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


# --------------------------------------------------------------------------
#  Account / Profile
# --------------------------------------------------------------------------
@app.route("/account")
@login_required
def account():
    lists = SavedList.query.filter_by(user_id=current_user.id).all()
    recent_reviews = Review.query.filter_by(user_id=current_user.id) \
        .order_by(Review.created_at.desc()).limit(5).all()
    recent_trips = Trip.query.filter_by(user_id=current_user.id) \
        .order_by(Trip.created_at.desc()).limit(5).all()
    saved_count = SavedPlace.query.filter_by(user_id=current_user.id).count()
    trip_count = Trip.query.filter_by(user_id=current_user.id).count()
    review_count = Review.query.filter_by(user_id=current_user.id).count()
    return render_template(
        "account.html",
        lists=lists,
        recent_reviews=recent_reviews,
        recent_trips=recent_trips,
        saved_count=saved_count,
        trip_count=trip_count,
        review_count=review_count,
    )


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        current_user.name = request.form.get("name", current_user.name).strip()
        current_user.home_city = request.form.get("home_city", "").strip()
        current_user.bio = request.form.get("bio", "").strip()
        if current_user.name:
            current_user.avatar_letter = current_user.name[0].upper()
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        new2 = request.form.get("new_password2", "")
        if not bcrypt.check_password_hash(current_user.password_hash, current):
            flash("Current password is incorrect.", "error")
            return render_template("change_password.html")
        if new != new2:
            flash("New passwords do not match.", "error")
            return render_template("change_password.html")
        if len(new) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("change_password.html")
        current_user.password_hash = bcrypt.generate_password_hash(new).decode("utf-8")
        db.session.commit()
        flash("Password updated.", "success")
        return redirect(url_for("account"))
    return render_template("change_password.html")


@app.route("/account/delete", methods=["POST"])
@login_required
def account_delete():
    user = db.session.get(User, current_user.id)
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash("Your account has been deleted.", "info")
    return redirect(url_for("index"))


# --------------------------------------------------------------------------
#  Lists & Saved Places
# --------------------------------------------------------------------------
@app.route("/lists")
@login_required
def lists_page():
    lists = SavedList.query.filter_by(user_id=current_user.id).all()
    # Count places in each list
    list_counts = {l.id: SavedPlace.query.filter_by(list_id=l.id).count() for l in lists}
    return render_template("lists.html", lists=lists, list_counts=list_counts)


@app.route("/lists/new", methods=["GET", "POST"])
@login_required
def list_create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        color = request.form.get("color", "#4285f4")
        if not name:
            flash("List name is required.", "error")
            return redirect(url_for("list_create"))
        sl = SavedList(user_id=current_user.id, name=name, description=desc, color=color, icon="bookmark")
        db.session.add(sl)
        db.session.commit()
        flash(f"List '{name}' created.", "success")
        return redirect(url_for("list_detail", list_id=sl.id))
    return render_template("list_form.html", action="Create")


@app.route("/lists/<int:list_id>")
@login_required
def list_detail(list_id):
    sl = db.session.get(SavedList, list_id)
    if not sl or sl.user_id != current_user.id:
        abort(404)
    saved = SavedPlace.query.filter_by(list_id=sl.id).order_by(SavedPlace.created_at.desc()).all()
    return render_template("list_detail.html", saved_list=sl, saved=saved)


@app.route("/lists/<int:list_id>/edit", methods=["GET", "POST"])
@login_required
def list_edit(list_id):
    sl = db.session.get(SavedList, list_id)
    if not sl or sl.user_id != current_user.id:
        abort(404)
    if request.method == "POST":
        sl.name = request.form.get("name", sl.name).strip()
        sl.description = request.form.get("description", "").strip()
        sl.color = request.form.get("color", sl.color)
        db.session.commit()
        flash("List updated.", "success")
        return redirect(url_for("list_detail", list_id=sl.id))
    return render_template("list_form.html", action="Edit", saved_list=sl)


@app.route("/lists/<int:list_id>/delete", methods=["POST"])
@login_required
def list_delete(list_id):
    sl = db.session.get(SavedList, list_id)
    if not sl or sl.user_id != current_user.id:
        abort(404)
    if sl.is_default:
        flash("Default lists cannot be deleted.", "error")
        return redirect(url_for("lists_page"))
    db.session.delete(sl)
    db.session.commit()
    flash("List deleted.", "success")
    return redirect(url_for("lists_page"))


@app.route("/saved")
@login_required
def saved_page():
    """All saved places across all lists."""
    saved = SavedPlace.query.filter_by(user_id=current_user.id) \
        .order_by(SavedPlace.created_at.desc()).all()
    lists = SavedList.query.filter_by(user_id=current_user.id).all()
    return render_template("saved.html", saved=saved, lists=lists)


@app.route("/api/save", methods=["POST"])
@csrf.exempt
@login_required
def api_save_place():
    data = request.get_json(silent=True) or {}
    place_id = data.get("place_id")
    list_id = data.get("list_id")
    place = db.session.get(Place, place_id)
    if not place:
        return jsonify({"success": False, "message": "Place not found"}), 404

    # Use default list if none provided
    if not list_id:
        default = SavedList.query.filter_by(user_id=current_user.id, is_default=True).first()
        if not default:
            ensure_default_lists(current_user)
            default = SavedList.query.filter_by(user_id=current_user.id, is_default=True).first()
        list_id = default.id

    existing = SavedPlace.query.filter_by(
        user_id=current_user.id, place_id=place.id
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        count = SavedPlace.query.filter_by(user_id=current_user.id).count()
        return jsonify({"success": True, "saved": False, "saved_count": count, "message": "Removed from saved"})

    sp = SavedPlace(user_id=current_user.id, list_id=list_id, place_id=place.id)
    db.session.add(sp)
    db.session.commit()
    count = SavedPlace.query.filter_by(user_id=current_user.id).count()
    return jsonify({"success": True, "saved": True, "saved_count": count, "message": f"Saved to list"})


@app.route("/save/<int:place_id>", methods=["POST"])
@login_required
def save_place_form(place_id):
    """Form-POST equivalent of /api/save. Safe for browser agents that can't send AJAX."""
    place = db.session.get(Place, place_id)
    if not place:
        abort(404)
    list_id = request.form.get("list_id", type=int)
    if not list_id:
        default = SavedList.query.filter_by(user_id=current_user.id, is_default=True).first()
        if not default:
            ensure_default_lists(current_user)
            default = SavedList.query.filter_by(user_id=current_user.id, is_default=True).first()
        list_id = default.id if default else None

    existing = SavedPlace.query.filter_by(user_id=current_user.id, place_id=place.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash(f"Removed {place.name} from saved.", "info")
    else:
        sp = SavedPlace(user_id=current_user.id, list_id=list_id, place_id=place.id)
        db.session.add(sp)
        db.session.commit()
        flash(f"Saved {place.name}.", "success")
    return redirect(request.referrer or url_for("place_detail", slug=place.slug))


@app.route("/save-to-list/<int:place_id>", methods=["POST"])
@login_required
def save_place_to_list(place_id):
    """Save a place to a specific list (form POST). Creates SavedPlace if not already there."""
    place = db.session.get(Place, place_id)
    if not place:
        abort(404)
    list_id = request.form.get("list_id", type=int)
    if not list_id:
        flash("List not specified.", "error")
        return redirect(request.referrer or url_for("saved_page"))
    sl = db.session.get(SavedList, list_id)
    if not sl or sl.user_id != current_user.id:
        abort(404)
    existing = SavedPlace.query.filter_by(user_id=current_user.id, place_id=place.id, list_id=list_id).first()
    if not existing:
        sp = SavedPlace(user_id=current_user.id, list_id=list_id, place_id=place.id)
        db.session.add(sp)
        db.session.commit()
        flash(f"Saved {place.name} to '{sl.name}'.", "success")
    else:
        flash(f"{place.name} is already in '{sl.name}'.", "info")
    return redirect(request.referrer or url_for("list_detail", list_id=list_id))


@app.route("/saved/<int:saved_id>/remove", methods=["POST"])
@login_required
def saved_remove(saved_id):
    sp = db.session.get(SavedPlace, saved_id)
    if not sp or sp.user_id != current_user.id:
        abort(404)
    db.session.delete(sp)
    db.session.commit()
    flash("Removed from saved.", "info")
    return redirect(request.referrer or url_for("saved_page"))


# --------------------------------------------------------------------------
#  Trips
# --------------------------------------------------------------------------
@app.route("/trips")
@login_required
def trips_page():
    trips = Trip.query.filter_by(user_id=current_user.id) \
        .order_by(Trip.created_at.desc()).all()
    return render_template("trips.html", trips=trips)


@app.route("/trips/new", methods=["GET", "POST"])
@login_required
def trip_create():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        city = request.form.get("city", "").strip()
        start = request.form.get("start_date", "")
        end = request.form.get("end_date", "")
        notes = request.form.get("notes", "").strip()
        if not title:
            flash("Trip title is required.", "error")
            return redirect(url_for("trip_create"))
        trip = Trip(
            user_id=current_user.id,
            trip_code=gen_trip_code(),
            title=title,
            city=city,
            notes=notes,
            status="planning",
        )
        if start:
            try:
                trip.start_date = datetime.strptime(start, "%Y-%m-%d").date()
            except ValueError:
                pass
        if end:
            try:
                trip.end_date = datetime.strptime(end, "%Y-%m-%d").date()
            except ValueError:
                pass
        db.session.add(trip)
        db.session.commit()
        flash(f"Trip '{title}' created.", "success")
        return redirect(url_for("trip_detail", trip_id=trip.id))
    cities = City.query.order_by(City.display_name).all()
    return render_template("trip_form.html", action="Create", cities=cities)


@app.route("/trips/<int:trip_id>")
@login_required
def trip_detail(trip_id):
    trip = db.session.get(Trip, trip_id)
    if not trip or trip.user_id != current_user.id:
        abort(404)
    stops = TripStop.query.filter_by(trip_id=trip.id).order_by(TripStop.order_idx).all()
    return render_template("trip_detail.html", trip=trip, stops=stops)


@app.route("/trips/<int:trip_id>/add_stop", methods=["POST"])
@login_required
def trip_add_stop(trip_id):
    trip = db.session.get(Trip, trip_id)
    if not trip or trip.user_id != current_user.id:
        abort(404)
    place_id = request.form.get("place_id", type=int)
    notes = request.form.get("notes", "").strip()
    place = db.session.get(Place, place_id)
    if not place:
        flash("Place not found.", "error")
        return redirect(url_for("trip_detail", trip_id=trip.id))
    max_order = db.session.query(func.max(TripStop.order_idx)).filter_by(trip_id=trip.id).scalar() or 0
    stop = TripStop(trip_id=trip.id, place_id=place.id, order_idx=max_order + 1, notes=notes)
    db.session.add(stop)
    db.session.commit()
    flash(f"Added {place.name} to trip.", "success")
    return redirect(url_for("trip_detail", trip_id=trip.id))


@app.route("/trips/<int:trip_id>/cancel", methods=["POST"])
@login_required
def trip_cancel(trip_id):
    trip = db.session.get(Trip, trip_id)
    if not trip or trip.user_id != current_user.id:
        abort(404)
    if trip.status not in ("planning", "upcoming"):
        flash("Only planning/upcoming trips can be cancelled.", "error")
    else:
        trip.status = "cancelled"
        db.session.commit()
        flash("Trip cancelled.", "info")
    return redirect(url_for("trip_detail", trip_id=trip.id))


@app.route("/trips/<int:trip_id>/complete", methods=["POST"])
@login_required
def trip_complete(trip_id):
    trip = db.session.get(Trip, trip_id)
    if not trip or trip.user_id != current_user.id:
        abort(404)
    trip.status = "completed"
    db.session.commit()
    # Add all stops to timeline
    for stop in trip.stops:
        db.session.add(TimelineEntry(
            user_id=current_user.id,
            place_id=stop.place_id,
            visited_at=datetime.utcnow(),
            note=f"Visited on trip: {trip.title}",
        ))
    db.session.commit()
    flash("Trip marked as completed. Stops added to timeline.", "success")
    return redirect(url_for("trip_detail", trip_id=trip.id))


@app.route("/trips/<int:trip_id>/stop/<int:stop_id>/remove", methods=["POST"])
@login_required
def trip_stop_remove(trip_id, stop_id):
    trip = db.session.get(Trip, trip_id)
    if not trip or trip.user_id != current_user.id:
        abort(404)
    stop = db.session.get(TripStop, stop_id)
    if stop and stop.trip_id == trip.id:
        db.session.delete(stop)
        db.session.commit()
        flash("Stop removed.", "info")
    return redirect(url_for("trip_detail", trip_id=trip.id))


# --------------------------------------------------------------------------
#  Reviews
# --------------------------------------------------------------------------
@app.route("/place/<slug>/review", methods=["POST"])
@login_required
def submit_review(slug):
    place = Place.query.filter_by(slug=slug).first_or_404()
    rating = request.form.get("rating", type=int)
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    if not rating or rating < 1 or rating > 5:
        flash("Please provide a rating between 1 and 5.", "error")
    elif not body:
        flash("Please write a review.", "error")
    else:
        existing = Review.query.filter_by(user_id=current_user.id, place_id=place.id).first()
        if existing:
            existing.rating = rating
            existing.title = title
            existing.body = body
            flash("Review updated.", "success")
        else:
            r = Review(
                user_id=current_user.id, place_id=place.id,
                rating=rating, title=title, body=body,
            )
            db.session.add(r)
            flash("Review posted.", "success")
        db.session.commit()
    return redirect(url_for("place_detail", slug=slug))


@app.route("/review/<int:review_id>/delete", methods=["POST"])
@login_required
def delete_review(review_id):
    r = db.session.get(Review, review_id)
    if not r or r.user_id != current_user.id:
        abort(404)
    place_slug = r.place.slug
    db.session.delete(r)
    db.session.commit()
    flash("Review deleted.", "info")
    return redirect(url_for("place_detail", slug=place_slug))


# --------------------------------------------------------------------------
#  Photos & Timeline
# --------------------------------------------------------------------------
@app.route("/place/<slug>/checkin", methods=["POST"])
@login_required
def place_checkin(slug):
    place = Place.query.filter_by(slug=slug).first_or_404()
    note = request.form.get("note", "").strip()
    db.session.add(TimelineEntry(
        user_id=current_user.id,
        place_id=place.id,
        visited_at=datetime.utcnow(),
        note=note,
    ))
    db.session.commit()
    flash(f"Checked in at {place.name}.", "success")
    return redirect(url_for("place_detail", slug=slug))


@app.route("/timeline/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_timeline_entry(entry_id):
    e = db.session.get(TimelineEntry, entry_id)
    if not e or e.user_id != current_user.id:
        abort(404)
    db.session.delete(e)
    db.session.commit()
    flash("Timeline entry removed.", "info")
    return redirect(url_for("timeline"))


# --------------------------------------------------------------------------
#  APIs
# --------------------------------------------------------------------------
@app.route("/api/places")
@app.route("/api/places/<cat_slug>")
def api_places(cat_slug=None):
    """JSON list of places, filterable by category or city."""
    cat_slug = cat_slug or request.args.get("category")
    city_slug = request.args.get("city")
    q = Place.query
    if cat_slug:
        c = Category.query.filter_by(slug=cat_slug).first()
        if c:
            q = q.filter_by(category_id=c.id)
    if city_slug:
        c = City.query.filter_by(slug=city_slug).first()
        if c:
            q = q.filter_by(city_id=c.id)
    places = q.limit(100).all()
    return jsonify({
        "places": [{
            "id": p.id, "slug": p.slug, "name": p.name,
            "category": p.category.slug if p.category else "",
            "city": p.city.slug if p.city else "",
            "rating": p.rating, "price": p.price_level,
            "address": p.address, "lat": p.lat, "lng": p.lng,
            "image": p.hero_image,
        } for p in places],
        "count": len(places),
    })


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": [], "count": 0})
    pattern = f"%{q}%"
    results = Place.query.filter(or_(
        Place.name.ilike(pattern), Place.description.ilike(pattern)
    )).limit(10).all()
    return jsonify({
        "results": [{
            "slug": p.slug, "name": p.name, "address": p.address,
            "rating": p.rating, "category": p.category.name if p.category else "",
            "image": p.hero_image,
        } for p in results],
        "count": len(results),
    })


@app.route("/api/nearby")
@app.route("/api/nearby/<slug>")
def api_nearby(slug=None):
    """Nearby places. Either by slug (finds city) or by lat/lng coords."""
    if slug:
        place = Place.query.filter_by(slug=slug).first_or_404()
        nearby = Place.query.filter(
            Place.city_id == place.city_id,
            Place.id != place.id,
        ).order_by(Place.rating.desc()).limit(8).all()
    else:
        # By lat/lng: find the closest city and return its highest-rated places
        try:
            lat = float(request.args.get("lat", 0))
            lng = float(request.args.get("lng", 0))
        except (ValueError, TypeError):
            return jsonify({"nearby": [], "error": "invalid coordinates"}), 400
        # Closest city by simple squared-distance
        cities = City.query.all()
        if not cities:
            return jsonify({"nearby": []})
        closest = min(cities, key=lambda c: (c.lat - lat) ** 2 + (c.lng - lng) ** 2)
        nearby = Place.query.filter_by(city_id=closest.id) \
            .order_by(Place.rating.desc()).limit(8).all()
    return jsonify({
        "nearby": [{
            "slug": p.slug, "name": p.name, "rating": p.rating,
            "image": p.hero_image, "category": p.category.name if p.category else "",
        } for p in nearby]
    })


# --------------------------------------------------------------------------
#  Error handlers
# --------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# --------------------------------------------------------------------------
#  DB init / seed
# --------------------------------------------------------------------------
def seed_database():
    from seed_data import build_categories, build_cities, build_places, seed_task_data
    if Category.query.count() == 0:
        build_categories(db, Category)
    if City.query.count() == 0:
        build_cities(db, City)
    if Place.query.count() == 0:
        n = build_places(db, Place, Category, City)
        print(f"Seeded {n} places")
    if Route.query.count() == 0:
        seed_task_data(db, Place, Category, City, Route)


# --------------------------------------------------------------------------
#  Benchmark seed
# --------------------------------------------------------------------------
def seed_benchmark_users():
    """Create 4 benchmark users with saved places, lists, and trips.

    Idempotent: skips if alice.j@test.com already exists.
    Must run AFTER seed_database() so Place rows exist.
    """
    if User.query.filter_by(email="alice.j@test.com").first():
        return  # already seeded

    PW = "TestPass123!"

    def _make_user(email, name, home_city):
        pw_hash = bcrypt.generate_password_hash(PW).decode("utf-8")
        u = User(
            email=email,
            password_hash=pw_hash,
            name=name,
            avatar_letter=name[0].upper(),
            home_city=home_city,
        )
        db.session.add(u)
        db.session.flush()  # get id before commit
        ensure_default_lists(u)
        return u

    def _get_place(name_frag):
        return Place.query.filter(Place.name.ilike(f"%{name_frag}%")).first()

    def _get_place_by_slug(slug):
        return Place.query.filter_by(slug=slug).first()

    def _get_city(slug):
        return City.query.filter_by(slug=slug).first()

    def _make_trip(user, title, city_name, status, start_delta_days, end_delta_days, notes=""):
        today = datetime.utcnow().date()
        start = today + timedelta(days=start_delta_days)
        end = today + timedelta(days=end_delta_days)
        trip = Trip(
            user_id=user.id,
            trip_code=gen_trip_code(),
            title=title,
            city=city_name,
            start_date=start,
            end_date=end,
            status=status,
            notes=notes,
        )
        db.session.add(trip)
        db.session.flush()
        return trip

    def _add_stop(trip, place, order_idx, notes=""):
        if place:
            stop = TripStop(trip_id=trip.id, place_id=place.id, order_idx=order_idx, notes=notes)
            db.session.add(stop)

    def _save_place(user, saved_list, place, note=""):
        if place and saved_list:
            existing = SavedPlace.query.filter_by(user_id=user.id, place_id=place.id).first()
            if not existing:
                sp = SavedPlace(user_id=user.id, list_id=saved_list.id, place_id=place.id, note=note)
                db.session.add(sp)

    def _make_custom_list(user, name, desc, icon="bookmark", color="#4285f4"):
        sl = SavedList(user_id=user.id, name=name, description=desc, icon=icon, color=color)
        db.session.add(sl)
        db.session.flush()
        return sl

    # ----------------------------------------------------------------
    # Alice Johnson — NYC foodie, plans lots of trips
    # ----------------------------------------------------------------
    alice = _make_user("alice.j@test.com", "Alice Johnson", "New York")

    alice_wtg = SavedList.query.filter_by(user_id=alice.id, name="Want to go").first()
    alice_fav = SavedList.query.filter_by(user_id=alice.id, name="Favorites").first()
    alice_nyc = _make_custom_list(alice, "NYC Eats", "Best restaurants in New York", icon="restaurant", color="#ea4335")
    alice_intl = _make_custom_list(alice, "International Bucket List", "Places I dream of visiting", icon="flight", color="#34a853")

    # Saved places
    _save_place(alice, alice_fav, _get_place("Central Park"), "Perfect for morning runs")
    _save_place(alice, alice_fav, _get_place("Empire State Building"), "Great views")
    _save_place(alice, alice_fav, _get_place("Times Square"), "Tourist spot but fun")
    _save_place(alice, alice_nyc, _get_place("Broadway Dim Sum"), "Try the shrimp dumplings")
    _save_place(alice, alice_nyc, _get_place("5th Osteria"), "Great pasta")
    _save_place(alice, alice_nyc, _get_place("Park Osteria"), "Lovely atmosphere")
    _save_place(alice, alice_wtg, _get_place("Eiffel Tower"), "Must visit someday")
    _save_place(alice, alice_wtg, _get_place("Colosseum"), "Ancient history")
    _save_place(alice, alice_intl, _get_place("Arc de Triomphe"), "Paris bucket list")
    _save_place(alice, alice_intl, _get_place("The Louvre"), "Need at least a full day")

    # Trips
    t1 = _make_trip(alice, "Chicago Weekend", "Chicago", "planning", 14, 17, "Weekend trip with friends")
    _add_stop(t1, _get_place("Willis Tower"), 1, "Get tickets in advance")
    _add_stop(t1, _get_place("Millennium Park"), 2, "Cloud Gate photo")
    _add_stop(t1, _get_place("Art Institute of Chicago"), 3, "Need 3+ hours here")
    _add_stop(t1, _get_place("Navy Pier"), 4, "Evening walk")

    t2 = _make_trip(alice, "Paris Dream Trip", "Paris", "upcoming", 45, 52, "Long-awaited Paris trip!")
    _add_stop(t2, _get_place("Eiffel Tower"), 1, "Go at sunset")
    _add_stop(t2, _get_place("Louvre"), 2, "Book skip-the-line tickets")
    _add_stop(t2, _get_place("Arc de Triomphe"), 3, "Climb to the top")

    t3 = _make_trip(alice, "Boston Day Trip", "Boston", "completed", -10, -8, "Quick trip for a friend's birthday")
    t3.status = "completed"
    _add_stop(t3, _get_place("Freedom Trail"), 1)
    _add_stop(t3, _get_place("Fenway Park"), 2)

    # Alice's planning trip to be cancelled (for T04 tasks)
    t4 = _make_trip(alice, "San Francisco Getaway", "San Francisco", "planning", 30, 34, "Work trip extension")
    _add_stop(t4, _get_place("Golden Gate Bridge"), 1)
    _add_stop(t4, _get_place("Alcatraz"), 2)
    _add_stop(t4, _get_place("Fisherman's Wharf"), 3)

    db.session.commit()

    # ----------------------------------------------------------------
    # Bob Chen — SF tech traveler
    # ----------------------------------------------------------------
    bob = _make_user("bob.c@test.com", "Bob Chen", "San Francisco")

    bob_wtg = SavedList.query.filter_by(user_id=bob.id, name="Want to go").first()
    bob_fav = SavedList.query.filter_by(user_id=bob.id, name="Favorites").first()
    bob_foodie = _make_custom_list(bob, "Foodie Spots", "Best food finds", icon="restaurant", color="#fbbc04")
    bob_hidden = _make_custom_list(bob, "Hidden Gems", "Off-the-beaten-path places", icon="explore", color="#9c27b0")

    # Saved places
    _save_place(bob, bob_fav, _get_place("Golden Gate Bridge"), "Iconic SF")
    _save_place(bob, bob_fav, _get_place("Alcatraz Island"), "Fascinating history")
    _save_place(bob, bob_fav, _get_place("Fisherman's Wharf"), "Fresh seafood")
    _save_place(bob, bob_foodie, _get_place("Polk Sushi Counter"), "Best omakase in SF")
    _save_place(bob, bob_foodie, _get_place("Mission Taqueria"), "Authentic tacos")
    _save_place(bob, bob_foodie, _get_place("Valencia Coffee Roaster"), "Great pour-over")
    _save_place(bob, bob_hidden, _get_place("Lombard Street"), "Surprisingly charming")
    _save_place(bob, bob_wtg, _get_place("Tokyo Tower"), "Tech + culture")
    _save_place(bob, bob_wtg, _get_place("Great Wall of China"), "Bucket list")

    # Trips
    t5 = _make_trip(bob, "Tokyo Tech Tour", "Tokyo", "upcoming", 20, 27, "Checking out the tech scene")
    _add_stop(t5, _get_place("Tokyo Tower"), 1, "Evening visit")
    _add_stop(t5, _get_place_by_slug("sensoji"), 2, "Early morning before crowds")
    _add_stop(t5, _get_place("Tokyo Skytree"), 3, "Best views of Tokyo")

    t6 = _make_trip(bob, "SF Weekend Highlights", "San Francisco", "completed", -30, -28)
    t6.status = "completed"
    _add_stop(t6, _get_place("Golden Gate Bridge"), 1)
    _add_stop(t6, _get_place("Alcatraz"), 2)

    # Bob has a trip to be cancelled (for T04)
    t7 = _make_trip(bob, "Seattle Coffee Tour", "Seattle", "planning", 25, 28, "Visiting the coffee capital")
    _add_stop(t7, _get_place("Pike Place Market"), 1, "Original Starbucks!")
    _add_stop(t7, _get_place("Pine Coffee Roaster"), 2, "Best pour-over in Seattle")
    _add_stop(t7, _get_place("Space Needle"), 3, "Classic Seattle")

    db.session.commit()

    # ----------------------------------------------------------------
    # Carol Davis — Chicago explorer
    # ----------------------------------------------------------------
    carol = _make_user("carol.d@test.com", "Carol Davis", "Chicago")

    carol_wtg = SavedList.query.filter_by(user_id=carol.id, name="Want to go").first()
    carol_fav = SavedList.query.filter_by(user_id=carol.id, name="Favorites").first()
    carol_chi = _make_custom_list(carol, "Chicago Must-Sees", "Best of my city", icon="star", color="#4285f4")
    carol_italian = _make_custom_list(carol, "Italian Restaurants", "My favorite Italian spots", icon="restaurant", color="#ea4335")

    # Saved places
    _save_place(carol, carol_fav, _get_place("Millennium Park"), "My backyard")
    _save_place(carol, carol_fav, _get_place("Art Institute of Chicago"), "World class museum")
    _save_place(carol, carol_fav, _get_place("Willis Tower"), "Best views of Chicago")
    _save_place(carol, carol_chi, _get_place("Navy Pier"), "Great for out-of-towners")
    _save_place(carol, carol_chi, _get_place("Rush Brunch Spot"), "Sunday brunch tradition")
    _save_place(carol, carol_italian, _get_place("Rush Bistro"), "Solid Italian-American")
    _save_place(carol, carol_wtg, _get_place("Colosseum"), "Rome someday!")
    _save_place(carol, carol_wtg, _get_place("Sagrada Família"), "Gaudi is a genius")
    _save_place(carol, carol_wtg, _get_place("Buen Retiro Park"), "Spain bucket list")

    # Trips
    t8 = _make_trip(carol, "NYC Fall Visit", "New York", "planning", 10, 14, "Fall foliage + city")
    _add_stop(t8, _get_place("Central Park"), 1, "Peak fall colors")
    _add_stop(t8, _get_place("Empire State Building"), 2, "Observatory at sunset")
    _add_stop(t8, _get_place("Brooklyn Bridge"), 3, "Walk across")
    _add_stop(t8, _get_place("Times Square"), 4, "Obligatory tourist stop")

    t9 = _make_trip(carol, "Rome & Florence Art Trip", "Rome", "upcoming", 60, 70, "Two weeks exploring Italian art")
    _add_stop(t9, _get_place("Colosseum"), 1, "Book Gladiator's entrance")
    _add_stop(t9, _get_place("Vatican City"), 2, "Skip-the-line a must")
    _add_stop(t9, _get_place("Trevi Fountain"), 3, "Make a wish!")

    t10 = _make_trip(carol, "Chicago Summer Day Out", "Chicago", "completed", -20, -20)
    t10.status = "completed"
    _add_stop(t10, _get_place("Millennium Park"), 1)
    _add_stop(t10, _get_place("Navy Pier"), 2)

    # Carol has a planning trip to be cancelled (T04)
    t11 = _make_trip(carol, "Las Vegas Girls Trip", "Las Vegas", "planning", 40, 43, "Bachelorette party!")
    _add_stop(t11, _get_place("Bellagio Hotel"), 1, "Fountain show at night")
    _add_stop(t11, _get_place_by_slug("venetian-resort"), 2, "The Venetian is stunning")

    db.session.commit()

    # ----------------------------------------------------------------
    # David Kim — LA foodie + outdoor enthusiast
    # ----------------------------------------------------------------
    david = _make_user("david.k@test.com", "David Kim", "Los Angeles")

    david_wtg = SavedList.query.filter_by(user_id=david.id, name="Want to go").first()
    david_fav = SavedList.query.filter_by(user_id=david.id, name="Favorites").first()
    david_outdoor = _make_custom_list(david, "Outdoor Adventures", "Hikes, parks, and nature", icon="nature", color="#34a853")
    david_eats = _make_custom_list(david, "LA Eats", "Best food in Los Angeles", icon="restaurant", color="#ff5722")

    # Saved places
    _save_place(david, david_fav, _get_place("Santa Monica Pier"), "Sunsets are unreal")
    _save_place(david, david_fav, _get_place("Griffith Observatory"), "Best views of LA")
    _save_place(david, david_outdoor, _get_place("Hollywood Sign"), "Hike to the sign")
    _save_place(david, david_outdoor, _get_place("Venice Beach"), "Beach volleyball")
    _save_place(david, david_outdoor, _get_place("Grand Canyon"), "Annual pilgrimage")
    _save_place(david, david_eats, _get_place("Rodeo Tapas Bar"), "Impressive wine list")
    _save_place(david, david_eats, _get_place("Melrose Steakhouse"), "Special occasion dinner")
    _save_place(david, david_wtg, _get_place("Grand Canyon"), "This year for sure")
    _save_place(david, david_wtg, _get_place("Yosemite National Park"), "Epic scenery")

    # Trips
    t12 = _make_trip(david, "Seattle Outdoors Trip", "Seattle", "upcoming", 8, 12, "Hiking + seafood")
    _add_stop(t12, _get_place("Chihuly Garden"), 1, "Amazing glass art")
    _add_stop(t12, _get_place("Pike Place Market"), 2, "Fresh fish")
    _add_stop(t12, _get_place("Space Needle"), 3, "Classic tourist")

    t13 = _make_trip(david, "LA Weekend Staycation", "Los Angeles", "completed", -5, -3)
    t13.status = "completed"
    _add_stop(t13, _get_place("Santa Monica Pier"), 1)
    _add_stop(t13, _get_place("Griffith Observatory"), 2)

    # David has a trip to be cancelled (T04)
    t14 = _make_trip(david, "Boston Fall Tour", "Boston", "planning", 35, 39, "Checking out the East Coast fall colors")
    _add_stop(t14, _get_place("Freedom Trail"), 1)
    _add_stop(t14, _get_place("Fenway Park"), 2)
    _add_stop(t14, _get_place("Museum of Fine Arts"), 3)

    db.session.commit()
    print("Benchmark users seeded: alice.j, bob.c, carol.d, david.k")


# --------------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
