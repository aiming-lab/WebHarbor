"""IGN mirror — Flask app for news, reviews, videos, guides, and account flows."""
import json
import os
import re
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import or_

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "instance"
DB_DIR.mkdir(exist_ok=True)

MIRROR_REFERENCE_DATE = datetime(2026, 7, 2, 12, 0, 0)
STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "for",
    "of",
    "to",
    "in",
    "on",
    "with",
    "is",
    "it",
    "by",
    "from",
    "this",
    "that",
}

NEWS_CATEGORIES = [
    ("all", "All News"),
    ("columns", "Columns"),
    ("playstation", "PlayStation"),
    ("xbox", "Xbox"),
    ("nintendo", "Nintendo"),
    ("pc", "PC"),
    ("mobile", "Mobile"),
    ("movies", "Movies"),
    ("television", "Television"),
    ("comics", "Comics"),
    ("tech", "Tech"),
]

REVIEW_CATEGORIES = [
    ("all", "All Reviews"),
    ("editors-choice", "Editor's Choice"),
    ("games", "Game Reviews"),
    ("movies", "Movie Reviews"),
    ("tv", "TV Show Reviews"),
    ("tech", "Tech Reviews"),
]

REVIEW_SORT_OPTIONS = [
    ("latest", "Sort by Latest"),
    ("score-desc", "Highest Scores"),
    ("score-asc", "Lowest Scores"),
    ("popular", "Most Popular"),
]

REVIEW_SCORE_FILTERS = [
    ("all", "All Scores"),
    ("9-plus", "9+"),
    ("8-plus", "8+"),
    ("7-plus", "7+"),
    ("under-8", "Under 8"),
]

REVIEW_GENRE_FILTERS = [
    ("all", "All Genres"),
    ("game", "Game"),
    ("movie", "Movie"),
    ("tv", "TV Show"),
    ("tech", "Tech"),
]

app = Flask(__name__, instance_path=str(DB_DIR))
app.config["SECRET_KEY"] = "ign-webharbor-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_DIR / 'ign.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log in to use your IGN account tools."
csrf = CSRFProtect(app)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    region = db.Column(db.String(80), default="United States")
    favorite_platform = db.Column(db.String(80), default="PC")
    bio = db.Column(db.Text, default="")
    avatar_color = db.Column(db.String(20), default="#bf1313")
    notification_email = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    saved_items = db.relationship("SavedItem", backref="user", cascade="all, delete-orphan")
    playlist_entries = db.relationship(
        "PlaylistEntry", backref="user", cascade="all, delete-orphan"
    )
    comments = db.relationship("Comment", backref="user", cascade="all, delete-orphan")
    alerts = db.relationship("AlertSubscription", backref="user", cascade="all, delete-orphan")
    digests = db.relationship("Digest", backref="user", cascade="all, delete-orphan")
    guide_progress = db.relationship(
        "GuideProgress", backref="user", cascade="all, delete-orphan"
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw_password)

    @property
    def initials(self) -> str:
        parts = (self.display_name or self.username).split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return (self.username[:2] or "IG").upper()


class Section(db.Model):
    __tablename__ = "sections"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, default="")
    color = db.Column(db.String(20), default="#bf1313")
    sort_order = db.Column(db.Integer, default=99)


class ContentItem(db.Model):
    __tablename__ = "content_items"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(240), unique=True, nullable=False, index=True)
    source_path = db.Column(db.String(360), unique=True, nullable=False, index=True)
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, default="")
    body_json = db.Column(db.Text, default="[]")
    section_slug = db.Column(db.String(60), index=True, nullable=False)
    content_type = db.Column(db.String(20), index=True, nullable=False)
    author = db.Column(db.String(120), default="IGN Staff")
    published_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE, index=True)
    image_path = db.Column(db.String(360), default="")
    score = db.Column(db.Integer, nullable=True)
    score_label = db.Column(db.String(80), default="")
    comments_count = db.Column(db.Integer, default=0)
    duration = db.Column(db.String(20), default="")
    platforms_json = db.Column(db.Text, default="[]")
    tags_json = db.Column(db.Text, default="[]")
    checklist_json = db.Column(db.Text, default="[]")
    is_featured = db.Column(db.Boolean, default=False)
    is_top_story = db.Column(db.Boolean, default=False)
    is_editors_choice = db.Column(db.Boolean, default=False)
    sort_rank = db.Column(db.Integer, default=0)

    saved_by = db.relationship("SavedItem", backref="item", cascade="all, delete-orphan")
    playlist_entries = db.relationship(
        "PlaylistEntry", backref="item", cascade="all, delete-orphan"
    )
    comments = db.relationship("Comment", backref="item", cascade="all, delete-orphan")
    progress_entries = db.relationship(
        "GuideProgress", backref="item", cascade="all, delete-orphan"
    )

    def _load_json_list(self, raw: str) -> list:
        try:
            value = json.loads(raw or "[]")
        except Exception:
            return []
        return value if isinstance(value, list) else []

    @property
    def body(self) -> list:
        return self._load_json_list(self.body_json)

    @property
    def platforms(self) -> list:
        return self._load_json_list(self.platforms_json)

    @property
    def tags(self) -> list:
        return self._load_json_list(self.tags_json)

    @property
    def checklist(self) -> list:
        return self._load_json_list(self.checklist_json)

    @property
    def short_description(self) -> str:
        if len(self.description) <= 180:
            return self.description
        return self.description[:177].rstrip() + "..."

    @property
    def pretty_type(self) -> str:
        return {
            "article": "News",
            "review": "Review",
            "video": "Video",
            "guide": "Guide",
        }.get(self.content_type, self.content_type.title())


class SavedItem(db.Model):
    __tablename__ = "saved_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("content_items.id"), nullable=False)
    folder = db.Column(db.String(80), default="Read Later")
    note = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    __table_args__ = (db.UniqueConstraint("user_id", "item_id", name="uq_saved_user_item"),)


class PlaylistEntry(db.Model):
    __tablename__ = "playlist_entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("content_items.id"), nullable=False)
    status = db.Column(db.String(30), default="queued")
    note = db.Column(db.Text, default="")
    position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    __table_args__ = (db.UniqueConstraint("user_id", "item_id", name="uq_playlist_user_item"),)


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("content_items.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(20), default="neutral")
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class AlertSubscription(db.Model):
    __tablename__ = "alert_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    section_slug = db.Column(db.String(60), default="")
    keyword = db.Column(db.String(120), default="")
    frequency = db.Column(db.String(40), default="daily")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class Digest(db.Model):
    __tablename__ = "digests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    digest_number = db.Column(db.String(40), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    delivery = db.Column(db.String(60), default="email")
    status = db.Column(db.String(40), default="delivered")
    item_slugs_json = db.Column(db.Text, default="[]")
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    @property
    def item_slugs(self) -> list:
        try:
            return json.loads(self.item_slugs_json or "[]")
        except Exception:
            return []


class GuideProgress(db.Model):
    __tablename__ = "guide_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("content_items.id"), nullable=False)
    checkpoint = db.Column(db.String(160), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    __table_args__ = (
        db.UniqueConstraint("user_id", "item_id", "checkpoint", name="uq_guide_checkpoint"),
    )


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.split(r"\W+", (text or "").lower())
        if len(token) > 1 and token not in STOP_WORDS
    ]


def scored_search(query: str, items: list[ContentItem]) -> list[ContentItem]:
    tokens = tokenize(query)
    if not tokens:
        return items
    scored = []
    for item in items:
        haystack = " ".join(
            [
                item.title,
                item.description,
                item.author,
                item.section_slug,
                item.content_type,
                " ".join(item.tags),
                " ".join(item.platforms),
            ]
        ).lower()
        score = sum(3 if token in item.title.lower() else 1 for token in tokens if token in haystack)
        if score > 0:
            scored.append((score, item.published_at or MIRROR_REFERENCE_DATE, item))
    scored.sort(key=lambda row: (-row[0], -row[1].timestamp()))
    return [row[2] for row in scored]


def get_sections() -> list[Section]:
    return Section.query.order_by(Section.sort_order.asc()).all()


def content_query():
    return ContentItem.query.order_by(ContentItem.published_at.desc(), ContentItem.id.asc())


def detail_url(item: ContentItem) -> str:
    if item.content_type == "video":
        return url_for("video_detail", slug=item.slug)
    if item.content_type == "guide":
        wiki_path = item.source_path.removeprefix("/wikis/")
        return url_for("guide_detail", wiki_path=wiki_path)
    return url_for("article_detail", slug=item.slug)


def section_label(slug: str) -> str:
    section = Section.query.filter_by(slug=slug).first()
    return section.name if section else slug.replace("_", " ").title()


def text_terms_filter(*terms):
    clauses = []
    for term in terms:
        pattern = f"%{term}%"
        clauses.extend(
            [
                ContentItem.title.ilike(pattern),
                ContentItem.description.ilike(pattern),
                ContentItem.tags_json.ilike(pattern),
                ContentItem.platforms_json.ilike(pattern),
            ]
        )
    return or_(*clauses)


def apply_news_category(query, category: str):
    if category in {"", "all"}:
        return query
    if category == "columns":
        return query.filter(text_terms_filter("history", "view", "future", "controversies"))
    if category == "playstation":
        return query.filter(text_terms_filter("PlayStation", "PS5", "Sony"))
    if category == "xbox":
        return query.filter(text_terms_filter("Xbox", "Microsoft"))
    if category == "nintendo":
        return query.filter(text_terms_filter("Nintendo", "Switch", "Pokémon", "Pokemon"))
    if category == "pc":
        return query.filter(text_terms_filter("PC", "RTX", "GeForce", "Steam"))
    if category == "mobile":
        return query.filter(text_terms_filter("mobile", "iOS", "Android"))
    if category == "movies":
        return query.filter_by(section_slug="movies")
    if category == "television":
        return query.filter_by(section_slug="tv")
    if category == "comics":
        return query.filter(text_terms_filter("Marvel", "comic", "comics"))
    if category == "tech":
        return query.filter(text_terms_filter("tech", "hardware", "RTX", "GeForce", "PC"))
    abort(404)


def apply_review_category(query, category: str):
    if category in {"", "all"}:
        return query
    if category == "editors-choice":
        return query.filter(or_(ContentItem.is_editors_choice.is_(True), ContentItem.score >= 8))
    if category == "games":
        return query.filter(ContentItem.section_slug.in_(["games", "reviews"]))
    if category == "movies":
        return query.filter_by(section_slug="movies")
    if category == "tv":
        return query.filter_by(section_slug="tv")
    if category == "tech":
        return query.filter(text_terms_filter("tech", "hardware", "RTX", "PC"))
    abort(404)


def apply_review_score_filter(query, score_filter: str):
    if score_filter == "all":
        return query
    if score_filter == "9-plus":
        return query.filter(ContentItem.score >= 9)
    if score_filter == "8-plus":
        return query.filter(ContentItem.score >= 8)
    if score_filter == "7-plus":
        return query.filter(ContentItem.score >= 7)
    if score_filter == "under-8":
        return query.filter(ContentItem.score < 8)
    abort(404)


def apply_review_genre_filter(query, genre_filter: str):
    if genre_filter == "all":
        return query
    if genre_filter == "game":
        return query.filter(or_(ContentItem.section_slug == "games", ContentItem.tags_json.ilike("%games%")))
    if genre_filter == "movie":
        return query.filter(or_(ContentItem.section_slug == "movies", ContentItem.tags_json.ilike("%movies%")))
    if genre_filter == "tv":
        return query.filter(or_(ContentItem.section_slug == "tv", ContentItem.tags_json.ilike("%tv%")))
    if genre_filter == "tech":
        return query.filter(or_(ContentItem.tags_json.ilike("%tech%"), ContentItem.tags_json.ilike("%hardware%")))
    abort(404)


def apply_review_sort(query, sort_key: str):
    if sort_key == "latest":
        return query.order_by(ContentItem.published_at.desc(), ContentItem.id.asc())
    if sort_key == "score-desc":
        return query.order_by(ContentItem.score.desc(), ContentItem.published_at.desc(), ContentItem.id.asc())
    if sort_key == "score-asc":
        return query.order_by(ContentItem.score.asc(), ContentItem.published_at.desc(), ContentItem.id.asc())
    if sort_key == "popular":
        return query.order_by(ContentItem.comments_count.desc(), ContentItem.published_at.desc(), ContentItem.id.asc())
    abort(404)


def make_subnav(title: str, categories: list[tuple[str, str]], active: str, endpoint: str):
    items = []
    for key, label in categories:
        href = url_for(endpoint) if key == "all" else url_for(endpoint, category=key)
        items.append({"key": key, "label": label, "href": href})
    return {"title": title, "active": active or "all", "links": items}


def first_item_by_slug(slug: str) -> ContentItem | None:
    return ContentItem.query.filter_by(slug=slug).first()


def card_from_item(item: ContentItem, eyebrow: str, body: str = "") -> dict:
    return {
        "eyebrow": eyebrow,
        "title": item.title,
        "body": body or item.short_description,
        "image": item.image_path,
        "href": detail_url(item),
        "meta": f"{item.pretty_type} · {section_label(item.section_slug)}",
    }


def fallback_image(index: int = 0) -> str:
    item = (
        ContentItem.query.filter(ContentItem.image_path != "")
        .order_by(ContentItem.sort_rank.asc(), ContentItem.id.asc())
        .offset(index)
        .first()
    )
    return item.image_path if item else ""


def is_saved(item: ContentItem) -> bool:
    if not current_user.is_authenticated:
        return False
    return SavedItem.query.filter_by(user_id=current_user.id, item_id=item.id).first() is not None


def in_playlist(item: ContentItem) -> bool:
    if not current_user.is_authenticated:
        return False
    return PlaylistEntry.query.filter_by(user_id=current_user.id, item_id=item.id).first() is not None


@app.context_processor
def inject_helpers():
    return {
        "detail_url": detail_url,
        "section_label": section_label,
        "sections": get_sections,
        "is_saved": is_saved,
        "in_playlist": in_playlist,
        "mirror_date": MIRROR_REFERENCE_DATE,
    }


@app.route("/")
def index():
    top_stories = (
        ContentItem.query.filter_by(is_top_story=True)
        .order_by(ContentItem.sort_rank.asc())
        .limit(20)
        .all()
    )
    latest = content_query().limit(12).all()
    reviews = (
        ContentItem.query.filter_by(content_type="review")
        .order_by(ContentItem.score.desc(), ContentItem.published_at.desc())
        .limit(8)
        .all()
    )
    guides = (
        ContentItem.query.filter_by(content_type="guide")
        .order_by(ContentItem.published_at.desc())
        .limit(8)
        .all()
    )
    videos = (
        ContentItem.query.filter_by(content_type="video")
        .order_by(ContentItem.published_at.desc())
        .limit(6)
        .all()
    )
    return render_template(
        "index.html",
        top_stories=top_stories,
        latest=latest,
        reviews=reviews,
        guides=guides,
        videos=videos,
    )


@app.route("/news")
@app.route("/news/<category>")
def news(category: str = "all"):
    if category not in dict(NEWS_CATEGORIES):
        abort(404)
    base_query = ContentItem.query.filter(ContentItem.content_type == "article")
    items = apply_news_category(base_query, category).order_by(ContentItem.published_at.desc()).all()
    popular = base_query.order_by(ContentItem.comments_count.desc(), ContentItem.published_at.desc()).limit(5).all()
    featured = items[0] if items else base_query.order_by(ContentItem.published_at.desc()).first()
    return render_template(
        "hub_listing.html",
        hub="news",
        title="Trending News",
        list_title="Latest News" if category == "all" else dict(NEWS_CATEGORIES)[category],
        subtitle="Current IGN news across games, entertainment, hardware, streaming, and deals.",
        items=items,
        popular=popular,
        featured=featured,
        categories=NEWS_CATEGORIES,
        active_category=category,
        subnav=make_subnav("News", NEWS_CATEGORIES, category, "news"),
    )


@app.route("/games")
@app.route("/movies")
@app.route("/tv")
@app.route("/deals")
def section_listing():
    slug = request.path.strip("/")
    items = (
        ContentItem.query.filter_by(section_slug=slug)
        .order_by(ContentItem.published_at.desc())
        .all()
    )
    return render_template(
        "listing.html",
        title=section_label(slug),
        subtitle=Section.query.filter_by(slug=slug).first().description,
        items=items,
        active_filter=slug,
    )


@app.route("/reviews")
@app.route("/reviews/<category>")
def reviews(category: str = "all"):
    if category not in dict(REVIEW_CATEGORIES):
        abort(404)
    sort_key = request.args.get("sort", "latest")
    score_filter = request.args.get("score", "all")
    genre_filter = request.args.get("genre", "all")
    show_review_scores = request.args.get("scores", "1") != "0"
    editors_choice_only = request.args.get("editors_choice", "0") == "1"
    if sort_key not in dict(REVIEW_SORT_OPTIONS):
        abort(404)
    if score_filter not in dict(REVIEW_SCORE_FILTERS):
        abort(404)
    if genre_filter not in dict(REVIEW_GENRE_FILTERS):
        abort(404)
    query = ContentItem.query.filter_by(content_type="review")
    query = apply_review_category(query, category)
    if editors_choice_only:
        query = query.filter(ContentItem.is_editors_choice.is_(True))
    query = apply_review_score_filter(query, score_filter)
    query = apply_review_genre_filter(query, genre_filter)
    items = apply_review_sort(query, sort_key).all()
    popular = (
        ContentItem.query.filter_by(content_type="review")
        .order_by(ContentItem.score.desc(), ContentItem.comments_count.desc())
        .limit(5)
        .all()
    )
    featured = items[0] if items else (popular[0] if popular else None)
    return render_template(
        "hub_listing.html",
        hub="reviews",
        title="Reviews",
        list_title=dict(REVIEW_CATEGORIES)[category],
        subtitle="IGN-style verdicts, scores, and context.",
        items=items,
        popular=popular,
        featured=featured,
        categories=REVIEW_CATEGORIES,
        active_category=category,
        sort_options=REVIEW_SORT_OPTIONS,
        score_filters=REVIEW_SCORE_FILTERS,
        genre_filters=REVIEW_GENRE_FILTERS,
        sort_key=sort_key,
        score_filter=score_filter,
        genre_filter=genre_filter,
        show_review_scores=show_review_scores,
        hide_review_scores=not show_review_scores,
        editors_choice_only=editors_choice_only,
        subnav=make_subnav("Reviews", REVIEW_CATEGORIES, category, "reviews"),
    )


@app.route("/videos")
def videos():
    items = (
        ContentItem.query.filter_by(content_type="video")
        .order_by(ContentItem.published_at.desc())
        .all()
    )
    return render_template(
        "listing.html",
        title="Videos",
        subtitle="Trailers, Daily Fix clips, podcast segments, and exclusive features.",
        items=items,
        active_filter="videos",
    )


@app.route("/maps")
def maps():
    guide_items = (
        ContentItem.query.filter_by(content_type="guide")
        .order_by(ContentItem.sort_rank.asc(), ContentItem.title.asc())
        .limit(8)
        .all()
    )
    hero = first_item_by_slug("gta-online-weekly-updates") or (guide_items[0] if guide_items else None)
    cards = []
    for label, item in zip(
        ["Open World Map", "Season Map", "Wiki Hub", "Quest Tracker"],
        guide_items[:4],
        strict=False,
    ):
        cards.append(
            card_from_item(
                item,
                label,
                "A static IGN-style map card with guide checkpoints, collectibles, and route hints.",
            )
        )
    return render_template(
        "utility_page.html",
        mode="maps",
        eyebrow="Interactive Maps",
        title="IGN Interactive Maps",
        subtitle="Track collectibles, missions, upgrades, and guide checkpoints across popular games.",
        hero={
            "title": hero.title if hero else "Interactive Maps",
            "body": "Explore game worlds with checklist-style map cards and related IGN wiki coverage.",
            "image": hero.image_path if hero else fallback_image(),
            "href": detail_url(hero) if hero else url_for("wikis"),
            "label": "Featured Map",
        },
        cards=cards,
        panels=[
            {"title": "Collectibles", "body": "Use map-style guide cards to scan for collectibles and objectives."},
            {"title": "Quest Routes", "body": "Open a guide page to read route notes and update checklist progress."},
            {"title": "Latest Wikis", "body": "Recent IGN wiki pages stay visible without requiring a separate search."},
        ],
    )


@app.route("/discover")
def discover():
    featured = (
        ContentItem.query.order_by(ContentItem.comments_count.desc(), ContentItem.published_at.desc())
        .limit(8)
        .all()
    )
    cards = [
        card_from_item(item, ["Trending", "Reviews", "Guides", "Videos"][index % 4])
        for index, item in enumerate(featured[:4])
    ]
    return render_template(
        "utility_page.html",
        mode="discover",
        eyebrow="Discover",
        title="Discover More on IGN",
        subtitle="Browse trending stories, high-score reviews, new videos, and guide hubs in one place.",
        hero={
            "title": featured[0].title if featured else "Discover IGN",
            "body": "A lightweight discovery surface modeled after IGN's dark editorial hubs.",
            "image": featured[0].image_path if featured else fallback_image(),
            "href": detail_url(featured[0]) if featured else url_for("index"),
            "label": "Now Trending",
        },
        cards=cards,
        panels=[
            {"title": "Games", "body": "Console, PC, mobile, and hardware coverage from current IGN sections."},
            {"title": "Entertainment", "body": "Movies, TV, comics, streaming, and culture stories."},
            {"title": "Watch", "body": "Trailers, show clips, Daily Fix segments, and podcast-style videos."},
        ],
    )


@app.route("/store")
def store():
    store_items = (
        ContentItem.query.filter(
            or_(
                ContentItem.section_slug == "deals",
                ContentItem.tags_json.ilike("%hardware%"),
                ContentItem.tags_json.ilike("%collector%"),
            )
        )
        .order_by(ContentItem.published_at.desc())
        .limit(6)
        .all()
    )
    cards = []
    for index, item in enumerate(store_items[:4], start=1):
        payload = card_from_item(item, f"IGN Store Pick #{index}")
        payload["price"] = ["$24.99", "$39.99", "$59.99", "$79.99"][index - 1]
        cards.append(payload)
    return render_template(
        "utility_page.html",
        mode="store",
        eyebrow="Store",
        title="IGN Store",
        subtitle="A local storefront-style mirror for gear, collectibles, deals, and gaming hardware picks.",
        hero={
            "title": "Official IGN-style gear and curated deals",
            "body": "Browse static product cards and deal-style content without a checkout workflow.",
            "image": store_items[0].image_path if store_items else fallback_image(3),
            "href": detail_url(store_items[0]) if store_items else url_for("index"),
            "label": "Storefront",
        },
        cards=cards,
        panels=[
            {"title": "Apparel", "body": "Logo gear and convention-ready accessories."},
            {"title": "Collectibles", "body": "Cards, figures, and entertainment drops surfaced like IGN deals."},
            {"title": "Hardware", "body": "Gaming PC, controller, and headset picks from seeded coverage."},
        ],
    )


@app.route("/rewards")
def rewards():
    reward_items = (
        ContentItem.query.filter(ContentItem.content_type.in_(["article", "video"]))
        .order_by(ContentItem.comments_count.desc(), ContentItem.published_at.desc())
        .limit(6)
        .all()
    )
    cards = []
    for index, item in enumerate(reward_items[:4], start=1):
        payload = card_from_item(item, f"Reward Drop {index}")
        payload["points"] = [250, 500, 750, 1000][index - 1]
        cards.append(payload)
    return render_template(
        "utility_page.html",
        mode="rewards",
        eyebrow="Rewards",
        title="IGN Rewards",
        subtitle="A static rewards hub with points, drops, and member-style cards.",
        hero={
            "title": "Claim weekly drops and member perks",
            "body": "This mirror reproduces the Rewards surface visually; redemption and account economy are not active.",
            "image": reward_items[0].image_path if reward_items else fallback_image(4),
            "href": detail_url(reward_items[0]) if reward_items else url_for("index"),
            "label": "Rewards",
        },
        cards=cards,
        panels=[
            {"title": "Daily Check-in", "body": "Earn cosmetic points by reading, watching, and saving coverage."},
            {"title": "Sweepstakes", "body": "Static prize cards mimic the IGN Rewards browsing experience."},
            {"title": "Member Status", "body": "Signed-in users keep the bottom account chip while browsing rewards."},
        ],
    )


@app.route("/privacy-policy")
def privacy_policy():
    return render_template(
        "utility_page.html",
        mode="legal",
        eyebrow="Privacy Policy",
        title="IGN Privacy Policy",
        subtitle="A local, non-binding privacy-policy mirror page matching the IGN legal reading layout.",
        hero={
            "title": "Privacy at IGN",
            "body": "Review how account, device, advertising, and content-interaction data are described.",
            "image": fallback_image(5),
            "href": "#policy",
            "label": "Legal",
        },
        cards=[],
        panels=[
            {"title": "Information We Collect", "body": "Account identifiers, profile preferences, saved content, playlist actions, comments, alert settings, and device/browser metadata may appear in the local mirror database."},
            {"title": "How Information Is Used", "body": "The WebHarbor environment uses local data to support benchmark tasks such as login, saved stories, playlist actions, and guide progress."},
            {"title": "Advertising and Analytics", "body": "This local page does not load third-party trackers; it visually mirrors the legal-policy surface for navigation tasks."},
            {"title": "Your Choices", "body": "Use local account pages to edit profile preferences or reset the site through the WebHarbor control server."},
        ],
    )


@app.route("/terms-of-use")
def terms_of_use():
    return render_template(
        "utility_page.html",
        mode="legal",
        eyebrow="Terms of Use",
        title="Ziff Davis Terms of Use",
        subtitle="A local terms page for the sidebar link that normally points to ziffdavis.com.",
        hero={
            "title": "Terms for using IGN services",
            "body": "Read a static summary-style terms surface with IGN/Ziff Davis visual treatment.",
            "image": fallback_image(6),
            "href": "#terms",
            "label": "Legal",
        },
        cards=[],
        panels=[
            {"title": "Use of Services", "body": "Content, community features, account tools, and store-style surfaces are provided here for local benchmark interaction."},
            {"title": "User Content", "body": "Comments, notes, checklist updates, and playlist entries are stored only in the local SQLite database."},
            {"title": "Purchases and Rewards", "body": "Store and Rewards pages are visual replicas. They do not process purchases, payment data, sweepstakes, or real reward redemption."},
            {"title": "Availability", "body": "The mirror can be reset at any time through WebHarbor's control server, restoring the seeded state."},
        ],
    )


@app.route("/wikis/ign-community-central/How_to_Follow_IGN")
def follow_ign():
    related = (
        ContentItem.query.order_by(ContentItem.published_at.desc(), ContentItem.id.asc())
        .limit(6)
        .all()
    )
    cards = [
        card_from_item(item, ["Follow News", "Watch Videos", "Save Guides", "Join Lists"][index % 4])
        for index, item in enumerate(related[:4])
    ]
    return render_template(
        "utility_page.html",
        mode="follow",
        eyebrow="IGN Community Central",
        title="How to Follow IGN",
        subtitle="A wiki-style community page for the sidebar More link.",
        hero={
            "title": "Follow IGN across news, reviews, videos, guides, and playlists",
            "body": "Use the local sidebar, search, and account tools to move through the same major surfaces.",
            "image": related[0].image_path if related else fallback_image(7),
            "href": url_for("index"),
            "label": "Community",
        },
        cards=cards,
        panels=[
            {"title": "1. Pick a topic", "body": "Start with News, Reviews, Guides, Videos, or Search in the left rail."},
            {"title": "2. Open a story", "body": "Detail pages expose save, playlist, comment, and guide-progress actions when relevant."},
            {"title": "3. Sign in", "body": "Use a benchmark account to keep saved stories, playlist rows, alerts, and profile changes."},
            {"title": "4. Return to top", "body": "Use the sidebar Back To Top button after scrolling long pages."},
        ],
    )


@app.route("/guides")
def guides_redirect():
    return redirect(url_for("wikis"))


@app.route("/wikis")
def wikis():
    items = (
        ContentItem.query.filter_by(content_type="guide")
        .order_by(ContentItem.sort_rank.asc(), ContentItem.title.asc())
        .all()
    )
    return render_template(
        "listing.html",
        title="Guides",
        subtitle="Walkthroughs, checklists, wiki pages, and interactive-map style helpers.",
        items=items,
        active_filter="guides",
    )


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "all").strip() or "all"
    if category not in dict(NEWS_CATEGORIES):
        abort(404)
    # When no category filter is active, search across all content types so
    # videos, guides, and reviews are also discoverable.  When a specific news
    # category is selected the query narrows to articles of that category.
    if category == "all":
        base_query = ContentItem.query
    else:
        base_query = ContentItem.query.filter_by(content_type="article")
        base_query = apply_news_category(base_query, category)
    items = base_query.order_by(ContentItem.published_at.desc()).all()
    results = scored_search(q, items)
    return render_template(
        "search.html",
        q=q,
        results=results,
        category=category,
        categories=NEWS_CATEGORIES,
    )


def lookup_item(slug: str, expected_type: str | None = None) -> ContentItem:
    item = ContentItem.query.filter_by(slug=slug).first()
    if item is None:
        item = ContentItem.query.filter_by(source_path=f"/articles/{slug}").first()
    if item is None:
        abort(404)
    if expected_type and item.content_type != expected_type:
        abort(404)
    return item


@app.route("/articles/<slug>")
def article_detail(slug: str):
    item = lookup_item(slug)
    if item.content_type == "video":
        return redirect(url_for("video_detail", slug=item.slug))
    if item.content_type == "guide":
        return redirect(detail_url(item))
    related = related_items(item)
    return render_template("detail.html", item=item, related=related)


@app.route("/videos/<slug>")
def video_detail(slug: str):
    item = lookup_item(slug, "video")
    related = related_items(item)
    return render_template("video_detail.html", item=item, related=related)


@app.route("/wikis/<path:wiki_path>")
def guide_detail(wiki_path: str):
    source_path = f"/wikis/{wiki_path}"
    item = ContentItem.query.filter_by(source_path=source_path).first()
    if item is None:
        normalized = wiki_path.replace("/", "-").replace("_", "-").lower()
        item = ContentItem.query.filter_by(slug=normalized).first()
    if item is None or item.content_type != "guide":
        abort(404)
    progress = {}
    if current_user.is_authenticated:
        rows = GuideProgress.query.filter_by(user_id=current_user.id, item_id=item.id).all()
        progress = {row.checkpoint: row.completed for row in rows}
    related = related_items(item)
    return render_template("guide_detail.html", item=item, progress=progress, related=related)


def related_items(item: ContentItem) -> list[ContentItem]:
    tokens = set(item.tags[:4])
    candidates = (
        ContentItem.query.filter(ContentItem.id != item.id)
        .order_by(ContentItem.published_at.desc())
        .limit(40)
        .all()
    )
    scored = []
    for candidate in candidates:
        overlap = len(tokens.intersection(candidate.tags))
        if candidate.section_slug == item.section_slug:
            overlap += 1
        if candidate.content_type == item.content_type:
            overlap += 1
        scored.append((overlap, candidate.published_at, candidate))
    scored.sort(key=lambda row: (-row[0], -row[1].timestamp()))
    return [row[2] for row in scored[:4]]


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Welcome back to IGN.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("account"))
        flash("Email or password did not match.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        display_name = request.form.get("display_name", "").strip() or username
        password = request.form.get("password", "")
        if not email or not username or len(password) < 8:
            flash("Provide an email, username, and password of at least 8 characters.", "error")
        elif User.query.filter(or_(User.email == email, User.username == username)).first():
            flash("That email or username is already registered.", "error")
        else:
            user = User(email=email, username=username, display_name=display_name)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Your IGN account is ready.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You are logged out.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    saved = (
        SavedItem.query.filter_by(user_id=current_user.id)
        .order_by(SavedItem.created_at.desc())
        .limit(6)
        .all()
    )
    playlist = (
        PlaylistEntry.query.filter_by(user_id=current_user.id)
        .order_by(PlaylistEntry.position.asc(), PlaylistEntry.created_at.desc())
        .limit(6)
        .all()
    )
    return render_template("account.html", saved=saved, playlist=playlist)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        current_user.display_name = request.form.get("display_name", "").strip() or current_user.display_name
        current_user.region = request.form.get("region", "").strip() or current_user.region
        current_user.favorite_platform = (
            request.form.get("favorite_platform", "").strip() or current_user.favorite_platform
        )
        current_user.bio = request.form.get("bio", "").strip()
        current_user.notification_email = bool(request.form.get("notification_email"))
        db.session.commit()
        flash("Account profile updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/saved")
@login_required
def saved():
    rows = (
        SavedItem.query.filter_by(user_id=current_user.id)
        .order_by(SavedItem.created_at.desc())
        .all()
    )
    return render_template("saved.html", rows=rows)


@app.post("/save/<int:item_id>")
@login_required
def save_item(item_id: int):
    item = db.get_or_404(ContentItem, item_id)
    row = SavedItem.query.filter_by(user_id=current_user.id, item_id=item.id).first()
    if row:
        row.folder = request.form.get("folder", row.folder) or row.folder
        row.note = request.form.get("note", row.note) or row.note
        flash("Saved item updated.", "success")
    else:
        db.session.add(
            SavedItem(
                user_id=current_user.id,
                item_id=item.id,
                folder=request.form.get("folder", "Read Later"),
                note=request.form.get("note", ""),
            )
        )
        flash("Saved to your IGN list.", "success")
    db.session.commit()
    return redirect(request.referrer or detail_url(item))


@app.post("/saved/<int:saved_id>/remove")
@login_required
def remove_saved(saved_id: int):
    row = SavedItem.query.filter_by(id=saved_id, user_id=current_user.id).first_or_404()
    db.session.delete(row)
    db.session.commit()
    flash("Removed from saved stories.", "info")
    return redirect(url_for("saved"))


@app.route("/playlist")
@login_required
def playlist():
    rows = (
        PlaylistEntry.query.filter_by(user_id=current_user.id)
        .order_by(PlaylistEntry.position.asc(), PlaylistEntry.created_at.desc())
        .all()
    )
    return render_template("playlist.html", rows=rows)


@app.post("/playlist/add/<int:item_id>")
@login_required
def add_playlist(item_id: int):
    item = db.get_or_404(ContentItem, item_id)
    row = PlaylistEntry.query.filter_by(user_id=current_user.id, item_id=item.id).first()
    if row:
        row.note = request.form.get("note", row.note) or row.note
        row.status = request.form.get("status", row.status) or row.status
        flash("Playlist entry updated.", "success")
    else:
        position = PlaylistEntry.query.filter_by(user_id=current_user.id).count() + 1
        db.session.add(
            PlaylistEntry(
                user_id=current_user.id,
                item_id=item.id,
                note=request.form.get("note", ""),
                status=request.form.get("status", "queued"),
                position=position,
            )
        )
        flash("Added to Playlist.", "success")
    db.session.commit()
    return redirect(request.referrer or detail_url(item))


@app.post("/playlist/<int:entry_id>/status")
@login_required
def update_playlist_status(entry_id: int):
    row = PlaylistEntry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    row.status = request.form.get("status", row.status)
    row.note = request.form.get("note", row.note)
    db.session.commit()
    flash("Playlist status updated.", "success")
    return redirect(url_for("playlist"))


@app.post("/playlist/<int:entry_id>/remove")
@login_required
def remove_playlist(entry_id: int):
    row = PlaylistEntry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    db.session.delete(row)
    db.session.commit()
    flash("Removed from Playlist.", "info")
    return redirect(url_for("playlist"))


@app.post("/comment/<int:item_id>")
@login_required
def add_comment(item_id: int):
    item = db.get_or_404(ContentItem, item_id)
    body = request.form.get("body", "").strip()
    if len(body) < 3:
        flash("Write a little more before posting.", "error")
    else:
        db.session.add(Comment(user_id=current_user.id, item_id=item.id, body=body))
        item.comments_count = max(item.comments_count, len(item.comments) + 1)
        db.session.commit()
        flash("Comment posted.", "success")
    return redirect(detail_url(item) + "#comments")


@app.post("/guides/<int:item_id>/progress")
@login_required
def update_guide_progress(item_id: int):
    item = db.get_or_404(ContentItem, item_id)
    if item.content_type != "guide":
        abort(400)
    checkpoint = request.form.get("checkpoint", "").strip()
    if not checkpoint:
        abort(400)
    row = GuideProgress.query.filter_by(
        user_id=current_user.id, item_id=item.id, checkpoint=checkpoint
    ).first()
    if row is None:
        row = GuideProgress(user_id=current_user.id, item_id=item.id, checkpoint=checkpoint)
        db.session.add(row)
    row.completed = bool(request.form.get("completed"))
    row.updated_at = MIRROR_REFERENCE_DATE
    db.session.commit()
    flash("Guide progress saved.", "success")
    return redirect(detail_url(item))


@app.route("/alerts", methods=["GET", "POST"])
@login_required
def alerts():
    if request.method == "POST":
        section_slug = request.form.get("section_slug", "").strip()
        keyword = request.form.get("keyword", "").strip()
        frequency = request.form.get("frequency", "daily").strip()
        if not section_slug and not keyword:
            flash("Choose a section or keyword for the alert.", "error")
        else:
            db.session.add(
                AlertSubscription(
                    user_id=current_user.id,
                    section_slug=section_slug,
                    keyword=keyword,
                    frequency=frequency,
                    active=True,
                )
            )
            db.session.commit()
            flash("Alert subscription created.", "success")
            return redirect(url_for("alerts"))
    rows = (
        AlertSubscription.query.filter_by(user_id=current_user.id)
        .order_by(AlertSubscription.created_at.desc())
        .all()
    )
    return render_template("alerts.html", rows=rows)


@app.post("/alerts/<int:alert_id>/toggle")
@login_required
def toggle_alert(alert_id: int):
    row = AlertSubscription.query.filter_by(id=alert_id, user_id=current_user.id).first_or_404()
    row.active = not row.active
    db.session.commit()
    flash("Alert status changed.", "success")
    return redirect(url_for("alerts"))


@app.route("/_health")
def health():
    return {
        "ok": True,
        "site": "ign",
        "items": ContentItem.query.count(),
        "users": User.query.count(),
    }


from seed_data import seed_benchmark_users, seed_database  # noqa: E402

with app.app_context():
    db.create_all()
    seed_database(db, Section, ContentItem)
    seed_benchmark_users(
        db,
        User,
        ContentItem,
        SavedItem,
        PlaylistEntry,
        Comment,
        AlertSubscription,
        Digest,
        GuideProgress,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
