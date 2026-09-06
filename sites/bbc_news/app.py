"""
BBC News mirror - Flask application.

Adaptation of the mirror-web pattern to a news site:
  Entity     = Article (news story)
  Category   = Section (World, UK, Business, Technology, ...)
  Topic      = Tag / subject label
  Cart       = Reading List (save-for-later with folders + notes)
  Wishlist   = Bookmarks (one-click save to My News)
  Order      = Digest (exported bundle of articles as newsletter)
  Review     = Comment (with optional replies)
  Subscription = Topic alerts (email-me-when-X-updates)
"""
import os
import re
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify,
    session, abort, Response
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from sqlalchemy import or_, and_, func

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "instance"
DB_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "bbc-news-mirror-secret-key-change-in-prod-987654321"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_DIR / 'bbc_news.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."
csrf = CSRFProtect(app)


def bbc_article_share_url(article):
    if article.source_url:
        return article.source_url
    return f"https://www.bbc.com/news/articles/{article.slug}"


# =======================================================================
# MODELS
# =======================================================================

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(200), default="")
    location = db.Column(db.String(120), default="")
    bio = db.Column(db.Text, default="")
    avatar_color = db.Column(db.String(20), default="#bb1919")  # BBC red
    notification_email = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reading_list = db.relationship("ReadingListItem", backref="user", cascade="all, delete-orphan")
    bookmarks = db.relationship("Bookmark", backref="user", cascade="all, delete-orphan")
    digests = db.relationship("Digest", backref="user", cascade="all, delete-orphan")
    comments = db.relationship("Comment", backref="user", cascade="all, delete-orphan")
    subscriptions = db.relationship("TopicSubscription", backref="user", cascade="all, delete-orphan")
    history = db.relationship("ReadingHistory", backref="user", cascade="all, delete-orphan")

    def set_password(self, raw: str):
        self.password_hash = bcrypt.generate_password_hash(raw).decode("utf-8")

    def check_password(self, raw: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def initials(self):
        parts = (self.full_name or self.username or "U").split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return (self.username[:2] if self.username else "U").upper()


class Category(db.Model):
    """Top-level BBC News section: World, UK, Business, Technology, ..."""
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    subtitle = db.Column(db.String(250), default="")
    color = db.Column(db.String(20), default="#bb1919")
    icon = db.Column(db.String(20), default="")
    parent_slug = db.Column(db.String(60), default="")
    sort_order = db.Column(db.Integer, default=100)
    description = db.Column(db.Text, default="")

    articles = db.relationship("Article", backref="category", lazy="dynamic")

    @property
    def article_count(self):
        return Article.query.filter_by(category_id=self.id).count()


class Article(db.Model):
    """A single news story."""
    __tablename__ = "articles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    headline = db.Column(db.Text, nullable=False)
    subtitle = db.Column(db.Text, default="")
    summary = db.Column(db.Text, default="")
    body = db.Column(db.Text, default="")  # paragraphs separated by \n\n
    author = db.Column(db.String(200), default="BBC News")
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    hero_image = db.Column(db.String(400), default="")
    gallery_json = db.Column(db.Text, default="[]")  # JSON list of image paths
    # Full gallery payload (hero + images + sections) as served to article_detail
    # template. Migrated from scraped_data/article_galleries.json so the
    # production image doesn't need the JSON file at runtime.
    gallery_full_json = db.Column(db.Text, default="{}")
    topics_json = db.Column(db.Text, default="[]")  # JSON list of topic strings
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    reading_time = db.Column(db.Integer, default=3)  # minutes
    word_count = db.Column(db.Integer, default=0)
    view_count = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_breaking = db.Column(db.Boolean, default=False)
    is_live = db.Column(db.Boolean, default=False)
    location = db.Column(db.String(120), default="")
    source_url = db.Column(db.String(500), default="")
    # Task-driven extensions
    section_slug = db.Column(db.String(60), default="", index=True)  # denormalized primary section
    subsection = db.Column(db.String(120), default="", index=True)   # e.g., 'Football', 'Golf', 'AI'
    region = db.Column(db.String(60), default="")                    # e.g., 'UK','Europe','Asia','Africa','Middle East'
    video_url = db.Column(db.String(500), default="")                # video clip URL
    feature_tags = db.Column(db.Text, default="[]")                  # JSON list of kebab-case tags
    content_type = db.Column(db.String(20), default="article")       # 'article','video','podcast','live'

    comments_rel = db.relationship("Comment", backref="article", cascade="all, delete-orphan", lazy="dynamic")
    reading_list_items = db.relationship("ReadingListItem", backref="article", cascade="all, delete-orphan")
    bookmarks = db.relationship("Bookmark", backref="article", cascade="all, delete-orphan")
    history = db.relationship("ReadingHistory", backref="article", cascade="all, delete-orphan")

    def get_gallery(self) -> list:
        try:
            return json.loads(self.gallery_json or "[]")
        except Exception:
            return []

    def get_full_gallery(self) -> dict:
        """Return the full gallery dict (hero, images, sections) for use by
        the article_detail template. Stored on the row so we don't need the
        scraped JSON at runtime."""
        try:
            return json.loads(self.gallery_full_json or "{}")
        except Exception:
            return {}

    def get_topics(self) -> list:
        try:
            return json.loads(self.topics_json or "[]")
        except Exception:
            return []

    def get_paragraphs(self) -> list:
        body = self.body or ""
        paras = [p.strip() for p in re.split(r"\n\n+", body) if p.strip()]
        return paras

    @property
    def published_date_str(self):
        if not self.published_at:
            return ""
        now = datetime.utcnow()
        delta = now - self.published_at
        if delta.days == 0:
            hours = delta.seconds // 3600
            if hours < 1:
                mins = max(1, delta.seconds // 60)
                return f"{mins} min{'s' if mins != 1 else ''} ago"
            return f"{hours} hr{'s' if hours != 1 else ''} ago"
        if delta.days < 7:
            return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
        return self.published_at.strftime("%d %b %Y")

    @property
    def short_headline(self):
        if len(self.headline) > 100:
            return self.headline[:100] + "…"
        return self.headline

    @property
    def comment_count(self):
        return self.comments_rel.count()


class ReadingListItem(db.Model):
    """Cart analog — a saved article in a user's reading list with folder + notes."""
    __tablename__ = "reading_list_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    folder = db.Column(db.String(100), default="Read Later")
    note = db.Column(db.Text, default="")
    priority = db.Column(db.String(20), default="normal")  # normal, high, low
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    __table_args__ = (db.UniqueConstraint("user_id", "article_id", name="_user_article_rl_uc"),)


class Bookmark(db.Model):
    """Wishlist analog — a one-click 'save to My News' bookmark."""
    __tablename__ = "bookmarks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    bookmarked_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "article_id", name="_user_article_bm_uc"),)


class Digest(db.Model):
    """Order analog — an exported digest/newsletter of saved articles."""
    __tablename__ = "digests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    digest_number = db.Column(db.String(40), unique=True, nullable=False)
    title = db.Column(db.String(200), default="My News Digest")
    format = db.Column(db.String(20), default="email")  # email, pdf, text, rss
    status = db.Column(db.String(20), default="delivered")  # pending, delivered, cancelled
    article_count = db.Column(db.Integer, default=0)
    delivery_email = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, default="")

    items = db.relationship("DigestItem", backref="digest", cascade="all, delete-orphan")


class DigestItem(db.Model):
    __tablename__ = "digest_items"
    id = db.Column(db.Integer, primary_key=True)
    digest_id = db.Column(db.Integer, db.ForeignKey("digests.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    article = db.relationship("Article")


class Comment(db.Model):
    """Review analog — a user comment on an article, supports replies."""
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=True)
    body = db.Column(db.Text, nullable=False)
    like_count = db.Column(db.Integer, default=0)
    flagged = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    replies = db.relationship(
        "Comment",
        backref=db.backref("parent", remote_side=[id]),
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class TopicSubscription(db.Model):
    """Subscribe to a category or topic for email alerts."""
    __tablename__ = "topic_subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_slug = db.Column(db.String(60), default="")
    topic = db.Column(db.String(120), default="")
    frequency = db.Column(db.String(20), default="daily")  # daily, weekly, breaking_only
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ReadingHistory(db.Model):
    """Track which articles a user has read."""
    __tablename__ = "reading_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)


# =======================================================================
# LOGIN MANAGER
# =======================================================================

@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# =======================================================================
# SEED DATA
# =======================================================================

CATEGORY_META = [
    ("home",          "Home",          "#bb1919", "",         "",      10,  "The latest news, analysis, and stories from around the world"),
    ("news",          "News",          "#bb1919", "",         "",      20,  "Top stories and breaking news"),
    ("world",         "World",         "#bb1919", "",         "news",  30,  "International news and correspondent reports"),
    ("uk",            "UK",            "#bb1919", "",         "news",  40,  "News from across the United Kingdom"),
    ("politics",      "Politics",      "#bb1919", "",         "news",  50,  "Westminster, policy, and the political landscape"),
    ("business",      "Business",      "#000000", "",         "",      60,  "Markets, companies, economy, and your money"),
    ("technology",    "Technology",    "#000000", "",         "",      70,  "Tech, AI, startups, and the digital world"),
    ("science",       "Science",       "#000000", "",         "",      80,  "Space, nature, and the science of everything"),
    ("health",        "Health",        "#000000", "",         "",      90,  "Medicine, NHS, wellbeing, and disease"),
    ("entertainment", "Entertainment", "#000000", "",         "",     100,  "Film, music, celebrity, and television"),
    ("arts",          "Arts",          "#000000", "",         "",     110,  "Theatre, books, museums, and culture"),
    ("sport",         "Sport",         "#000000", "",         "",     120,  "Football, cricket, tennis, and more"),
    ("earth",         "Earth",         "#0a6b2e", "",         "",     130,  "Our changing planet, climate, and conservation"),
    ("travel",        "Travel",        "#000000", "",         "",     140,  "Destinations, guides, and travel stories"),
    ("in_pictures",   "In Pictures",   "#000000", "",         "",     150,  "Photojournalism and the visual story"),
    ("bbcverify",     "BBC Verify",    "#bb1919", "",         "news", 160,  "Fact-checking and verification"),
    ("video",         "Video",         "#000000", "",         "",     170,  "Watch the latest video news"),
    ("live",          "Live",          "#bb1919", "",         "",     180,  "Live events and breaking coverage"),
    ("culture",       "Culture",       "#000000", "",         "",     190,  "Film, books, music, and the arts"),
    ("audio",         "Audio",         "#000000", "",         "",     200,  "Podcasts, radio, and audio stories"),
    ("weather",       "Weather",       "#0a6b2e", "",         "",     210,  "Forecasts, storms, and climate alerts"),
    ("market_data",   "Market Data",   "#000000", "",         "business", 220, "Stock prices, indices, and currencies"),
    ("green_living",  "Green Living",  "#0a6b2e", "",         "earth", 230,  "Sustainable living and eco guides"),
    ("natural_wonders","Natural Wonders","#0a6b2e","",        "earth", 240,  "Wildlife, landscapes, and nature"),
    ("ai",            "Artificial Intelligence", "#000000", "", "technology", 250, "AI, machine learning, and the future"),
    ("war",           "War & Conflict", "#bb1919", "",        "world", 260,  "Reports from war zones and conflict updates"),
]

REGIONAL_SUBCATS = [
    ("africa",        "Africa",        "#bb1919", "world", 31),
    ("asia",          "Asia",          "#bb1919", "world", 32),
    ("australia",     "Australia",     "#bb1919", "world", 33),
    ("europe",        "Europe",        "#bb1919", "world", 34),
    ("latin_america", "Latin America", "#bb1919", "world", 35),
    ("middle_east",   "Middle East",   "#bb1919", "world", 36),
    ("us_canada",     "US & Canada",   "#bb1919", "world", 37),
    ("england",       "England",       "#bb1919", "uk",    41),
    ("scotland",      "Scotland",      "#bb1919", "uk",    42),
    ("wales",         "Wales",         "#bb1919", "uk",    43),
    ("northern_ireland", "N. Ireland", "#bb1919", "uk",    44),
]


def _slugify_fallback(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60] or "article"


def seed_database():
    if Category.query.first() is not None:
        return

    # --- Categories ---
    for slug, name, color, icon, parent, order, desc in CATEGORY_META:
        db.session.add(Category(
            slug=slug, name=name, color=color, icon=icon,
            parent_slug=parent, sort_order=order, description=desc,
            subtitle=desc,
        ))
    for slug, name, color, parent, order in REGIONAL_SUBCATS:
        db.session.add(Category(
            slug=slug, name=name, color=color,
            parent_slug=parent, sort_order=order,
            description=f"News from {name}",
        ))
    db.session.commit()
    print(f"  [+] Seeded {Category.query.count()} categories")

    # --- Articles ---
    art_path = BASE_DIR / "scraped_data" / "articles.json"
    gallery_path = BASE_DIR / "scraped_data" / "article_galleries.json"
    if not art_path.exists():
        print("  ! articles.json not found")
        return

    raw_articles = json.load(open(art_path))
    gallery_data = {}
    if gallery_path.exists():
        gallery_data = json.load(open(gallery_path))

    # Get category by slug
    cat_by_slug = {c.slug: c for c in Category.query.all()}

    # Pin a baseline timestamp so "x hrs ago" renders naturally
    now = datetime.utcnow()
    created = 0
    for idx, rp in enumerate(raw_articles):
        slug = rp.get("slug", "").strip()
        if not slug:
            slug = _slugify_fallback(rp.get("headline", f"article-{idx}"))
        if Article.query.filter_by(slug=slug).first():
            continue
        headline = (rp.get("headline") or "").strip()
        if not headline:
            continue

        cat_slug = rp.get("category") or ""
        if cat_slug not in cat_by_slug:
            cat_slug = "world"  # default
        category = cat_by_slug[cat_slug]

        subtitle = (rp.get("subtitle") or "").strip()[:400]
        summary = (rp.get("summary") or subtitle or "").strip()[:350]
        body = (rp.get("body") or "").strip()

        topics = rp.get("tags") or rp.get("topics") or []

        # Hero + gallery — also bake the full gallery dict (sections, etc.)
        # into gallery_full_json so the article_detail template can render
        # it without needing the source JSON at runtime.
        hero = ""
        gallery_imgs = []
        full_gallery = {}
        if slug in gallery_data:
            g = gallery_data[slug]
            hero = g.get("hero") or ""
            gallery_imgs = g.get("images", [])[:12]
            full_gallery = g

        published = now - timedelta(hours=random.randint(1, 72), minutes=random.randint(0, 59))

        art = Article(
            slug=slug,
            headline=headline,
            subtitle=subtitle,
            summary=summary,
            body=body,
            author=rp.get("author") or "BBC News",
            category_id=category.id,
            hero_image=hero,
            gallery_json=json.dumps(gallery_imgs),
            gallery_full_json=json.dumps(full_gallery),
            topics_json=json.dumps(topics),
            published_at=published,
            reading_time=rp.get("reading_time") or max(1, len(body.split()) // 200),
            word_count=rp.get("word_count") or len(body.split()),
            view_count=random.randint(500, 50000),
            is_featured=(idx < 6),
            is_breaking=(idx < 2),
            is_live=(idx == 0),
            location=rp.get("location") or "",
            source_url=rp.get("url") or "",
            section_slug=cat_slug,
        )
        db.session.add(art)
        created += 1
        if created % 50 == 0:
            db.session.commit()
    db.session.commit()
    print(f"  [+] Seeded {created} articles")

    # --- Demo user ---
    if not User.query.filter_by(email="demo@bbcnews.local").first():
        u = User(
            email="demo@bbcnews.local",
            username="newsreader",
            full_name="News Reader",
            location="London, UK",
            bio="Keeping up with the world's stories.",
        )
        u.set_password("demodemo")
        db.session.add(u)
        db.session.commit()

        sample = Article.query.limit(6).all()
        for i, a in enumerate(sample[:3]):
            db.session.add(ReadingListItem(
                user_id=u.id, article_id=a.id,
                folder="Work" if i % 2 == 0 else "Read Later",
            ))
        for a in sample[3:5]:
            db.session.add(Bookmark(user_id=u.id, article_id=a.id))
        db.session.commit()
        print(f"  [+] Created demo user (demo@bbcnews.local / demodemo)")


# =======================================================================
# BENCHMARK USER SEED
# =======================================================================

def seed_benchmark_users():
    """Create 4 benchmark users with reading list items, bookmarks, and digests.
    Idempotent — safe to call multiple times."""
    if User.query.filter_by(email="alice.j@test.com").first():
        return  # already seeded

    # Helper: get articles for a section, with fallback sections
    def _arts(primary_slug, fallbacks, count):
        arts = Article.query.filter_by(section_slug=primary_slug).limit(count).all()
        if len(arts) < count:
            for fb in fallbacks:
                extra = Article.query.filter_by(section_slug=fb).limit(count - len(arts)).all()
                seen_ids = {a.id for a in arts}
                arts += [a for a in extra if a.id not in seen_ids]
                if len(arts) >= count:
                    break
        return arts[:count]

    # ---- Alice Johnson — tech & science reader ----
    alice = User(
        email="alice.j@test.com",
        username="alice_johnson",
        full_name="Alice Johnson",
        location="London, UK",
        bio="Technology and science enthusiast.",
        avatar_color="#0057a8",
    )
    alice.set_password("TestPass123!")
    db.session.add(alice)
    db.session.flush()

    tech_arts = _arts("technology", ["science", "business"], 8)
    sci_arts = _arts("science", ["technology", "health"], 5)

    # Reading list: 4 tech + 2 science articles across two folders
    for i, a in enumerate(tech_arts[:4]):
        db.session.add(ReadingListItem(user_id=alice.id, article_id=a.id,
                                       folder="Technology", priority="high" if i < 2 else "normal"))
    for a in sci_arts[:2]:
        db.session.add(ReadingListItem(user_id=alice.id, article_id=a.id,
                                       folder="Science", priority="normal"))
    db.session.flush()

    # Bookmarks: 4 articles
    for a in tech_arts[4:6] + sci_arts[2:4]:
        db.session.add(Bookmark(user_id=alice.id, article_id=a.id))

    # Digests: 1 delivered, 1 pending
    d1 = Digest(user_id=alice.id, digest_number="D-ALICE-001",
                title="Weekly Tech Digest", format="email",
                status="delivered", article_count=min(4, len(tech_arts[:4])),
                delivery_email="alice.j@test.com")
    db.session.add(d1)
    db.session.flush()
    for a in tech_arts[:4]:
        db.session.add(DigestItem(digest_id=d1.id, article_id=a.id))

    d2 = Digest(user_id=alice.id, digest_number="D-ALICE-002",
                title="Science Roundup", format="text",
                status="pending", article_count=min(3, len(sci_arts[:3])),
                delivery_email="alice.j@test.com")
    db.session.add(d2)
    db.session.flush()
    for a in sci_arts[:3]:
        db.session.add(DigestItem(digest_id=d2.id, article_id=a.id))

    # Topic subscriptions
    db.session.add(TopicSubscription(user_id=alice.id, category_slug="technology",
                                     topic="AI", frequency="daily"))
    db.session.add(TopicSubscription(user_id=alice.id, category_slug="science",
                                     topic="Space", frequency="weekly"))

    # ---- Bob Chen — business & world reader ----
    bob = User(
        email="bob.c@test.com",
        username="bob_chen",
        full_name="Bob Chen",
        location="Manchester, UK",
        bio="Business and global news follower.",
        avatar_color="#c00000",
    )
    bob.set_password("TestPass123!")
    db.session.add(bob)
    db.session.flush()

    biz_arts = _arts("business", ["world", "politics"], 8)
    world_arts = _arts("world", ["politics", "uk"], 5)

    for i, a in enumerate(biz_arts[:5]):
        folder = "Business" if i < 3 else "World News"
        db.session.add(ReadingListItem(user_id=bob.id, article_id=a.id,
                                       folder=folder, priority="high" if i == 0 else "normal"))
    for a in world_arts[:3]:
        db.session.add(ReadingListItem(user_id=bob.id, article_id=a.id,
                                       folder="World News", priority="normal"))

    for a in biz_arts[5:7]:
        db.session.add(Bookmark(user_id=bob.id, article_id=a.id))
    for a in world_arts[3:5]:
        db.session.add(Bookmark(user_id=bob.id, article_id=a.id))
    db.session.flush()

    d3 = Digest(user_id=bob.id, digest_number="D-BOB-001",
                title="Business & Markets Weekly", format="email",
                status="delivered", article_count=min(5, len(biz_arts[:5])),
                delivery_email="bob.c@test.com")
    db.session.add(d3)
    db.session.flush()
    for a in biz_arts[:5]:
        db.session.add(DigestItem(digest_id=d3.id, article_id=a.id))

    d4 = Digest(user_id=bob.id, digest_number="D-BOB-002",
                title="World News Digest", format="pdf",
                status="delivered", article_count=min(3, len(world_arts[:3])),
                delivery_email="bob.c@test.com")
    db.session.add(d4)
    db.session.flush()
    for a in world_arts[:3]:
        db.session.add(DigestItem(digest_id=d4.id, article_id=a.id))

    db.session.add(TopicSubscription(user_id=bob.id, category_slug="business",
                                     topic="Markets", frequency="daily"))
    db.session.add(TopicSubscription(user_id=bob.id, category_slug="world",
                                     topic="", frequency="breaking_only"))

    # ---- Carol Davis — health & environment reader ----
    carol = User(
        email="carol.d@test.com",
        username="carol_davis",
        full_name="Carol Davis",
        location="Edinburgh, UK",
        bio="Health, environment, and earth science enthusiast.",
        avatar_color="#2e7d32",
    )
    carol.set_password("TestPass123!")
    db.session.add(carol)
    db.session.flush()

    health_arts = _arts("health", ["science", "uk"], 8)
    # earth may be absent in smaller DBs — fall back to science/world
    earth_arts = _arts("earth", ["science", "world"], 6)
    # ensure no overlap
    earth_ids = {a.id for a in earth_arts}
    health_uniq = [a for a in health_arts if a.id not in earth_ids]

    for i, a in enumerate(health_uniq[:4]):
        db.session.add(ReadingListItem(user_id=carol.id, article_id=a.id,
                                       folder="Health", priority="high" if i < 2 else "normal"))
    for a in earth_arts[:4]:
        db.session.add(ReadingListItem(user_id=carol.id, article_id=a.id,
                                       folder="Environment", priority="normal"))

    for a in health_uniq[4:7]:
        db.session.add(Bookmark(user_id=carol.id, article_id=a.id))
    for a in earth_arts[4:6]:
        db.session.add(Bookmark(user_id=carol.id, article_id=a.id))
    db.session.flush()

    d5 = Digest(user_id=carol.id, digest_number="D-CAROL-001",
                title="Health & Wellbeing Digest", format="email",
                status="delivered", article_count=min(4, len(health_uniq[:4])),
                delivery_email="carol.d@test.com")
    db.session.add(d5)
    db.session.flush()
    for a in health_uniq[:4]:
        db.session.add(DigestItem(digest_id=d5.id, article_id=a.id))

    d6 = Digest(user_id=carol.id, digest_number="D-CAROL-002",
                title="Climate & Earth Digest", format="rss",
                status="pending", article_count=min(4, len(earth_arts[:4])),
                delivery_email="carol.d@test.com")
    db.session.add(d6)
    db.session.flush()
    for a in earth_arts[:4]:
        db.session.add(DigestItem(digest_id=d6.id, article_id=a.id))

    db.session.add(TopicSubscription(user_id=carol.id, category_slug="health",
                                     topic="NHS", frequency="daily"))
    db.session.add(TopicSubscription(user_id=carol.id, category_slug="earth",
                                     topic="Climate Change", frequency="weekly"))

    # ---- David Kim — sport & entertainment reader ----
    david = User(
        email="david.k@test.com",
        username="david_kim",
        full_name="David Kim",
        location="Birmingham, UK",
        bio="Sports fanatic and entertainment news follower.",
        avatar_color="#6a1b9a",
    )
    david.set_password("TestPass123!")
    db.session.add(david)
    db.session.flush()

    # sport may be absent in smaller DBs — fall back to entertainment/arts
    sport_arts = _arts("sport", ["entertainment", "arts"], 8)
    ent_arts = _arts("entertainment", ["arts", "culture"], 6)
    sport_ids = {a.id for a in sport_arts}
    ent_uniq = [a for a in ent_arts if a.id not in sport_ids]
    # If no unique ent arts (all overlapped into sport_arts fallback), pull from arts directly
    if not ent_uniq:
        arts_arts = _arts("arts", ["entertainment", "culture"], 6)
        ent_uniq = [a for a in arts_arts if a.id not in sport_ids][:6]

    for i, a in enumerate(sport_arts[:5]):
        db.session.add(ReadingListItem(user_id=david.id, article_id=a.id,
                                       folder="Sport", priority="high" if i < 3 else "normal"))
    for a in ent_uniq[:3]:
        db.session.add(ReadingListItem(user_id=david.id, article_id=a.id,
                                       folder="Entertainment", priority="normal"))

    for a in sport_arts[5:7]:
        db.session.add(Bookmark(user_id=david.id, article_id=a.id))
    for a in ent_uniq[3:6]:
        db.session.add(Bookmark(user_id=david.id, article_id=a.id))
    db.session.flush()

    d7 = Digest(user_id=david.id, digest_number="D-DAVID-001",
                title="Sports Weekend Roundup", format="email",
                status="delivered", article_count=min(5, len(sport_arts[:5])),
                delivery_email="david.k@test.com")
    db.session.add(d7)
    db.session.flush()
    for a in sport_arts[:5]:
        db.session.add(DigestItem(digest_id=d7.id, article_id=a.id))

    d8 = Digest(user_id=david.id, digest_number="D-DAVID-002",
                title="Entertainment Weekly", format="email",
                status="cancelled", article_count=min(3, len(ent_uniq[:3])),
                delivery_email="david.k@test.com")
    db.session.add(d8)
    db.session.flush()
    for a in ent_uniq[:3]:
        db.session.add(DigestItem(digest_id=d8.id, article_id=a.id))

    db.session.add(TopicSubscription(user_id=david.id, category_slug="sport",
                                     topic="Football", frequency="daily"))
    db.session.add(TopicSubscription(user_id=david.id, category_slug="entertainment",
                                     topic="Film", frequency="weekly"))

    db.session.commit()
    print("  [+] Seeded 4 benchmark users (alice, bob, carol, david)")


# =======================================================================
# CONTEXT PROCESSORS
# =======================================================================

# BBC News navigation tree — mirrors the real bbc.com/news mainNavigation
# augmented with our local World/Politics hub pages so regional drill-down works.
# Paths are kept identical to our existing /news/<slug> routes.
BBC_NAV_TREE = [
    {"title": "Home", "path": "/", "slug": "home"},
    {"title": "News", "path": "/news/news", "slug": "news", "children": [
        {"title": "UK", "path": "/news/uk", "slug": "uk", "children": [
            {"title": "UK Politics", "path": "/news/politics", "slug": "politics"},
            {"title": "England", "path": "/news/england", "slug": "england"},
            {"title": "N. Ireland", "path": "/news/northern_ireland", "slug": "northern_ireland"},
            {"title": "Scotland", "path": "/news/scotland", "slug": "scotland"},
            {"title": "Wales", "path": "/news/wales", "slug": "wales"},
        ]},
        {"title": "World", "path": "/news/world", "slug": "world", "children": [
            {"title": "Africa", "path": "/news/africa", "slug": "africa"},
            {"title": "Asia", "path": "/news/asia", "slug": "asia"},
            {"title": "Australia", "path": "/news/australia", "slug": "australia"},
            {"title": "Europe", "path": "/news/europe", "slug": "europe"},
            {"title": "Latin America", "path": "/news/latin_america", "slug": "latin_america"},
            {"title": "Middle East", "path": "/news/middle_east", "slug": "middle_east"},
            {"title": "US & Canada", "path": "/news/us_canada", "slug": "us_canada"},
        ]},
        {"title": "In Pictures", "path": "/news/in_pictures", "slug": "in_pictures"},
        {"title": "BBC Verify", "path": "/news/bbcverify", "slug": "bbcverify"},
    ]},
    {"title": "Sport", "path": "/news/sport", "slug": "sport", "children": [
        {"title": "Football", "path": "/news/football", "slug": "football"},
        {"title": "Golf", "path": "/news/golf", "slug": "golf"},
        {"title": "Athletics", "path": "/news/athletics", "slug": "athletics"},
        {"title": "Horse Racing", "path": "/news/horse_racing", "slug": "horse_racing"},
        {"title": "Tennis", "path": "/news/tennis", "slug": "tennis"},
        {"title": "Cricket", "path": "/news/cricket", "slug": "cricket"},
        {"title": "Rugby", "path": "/news/rugby", "slug": "rugby"},
    ]},
    {"title": "Business", "path": "/news/business", "slug": "business", "children": [
        {"title": "Market Data", "path": "/news/market_data", "slug": "market_data"},
        {"title": "Technology of Business", "path": "/news/business?subsection=Technology+of+Business", "slug": "business_tob"},
    ]},
    {"title": "Innovation", "path": "/news/technology", "slug": "technology", "children": [
        {"title": "Technology", "path": "/news/technology", "slug": "technology"},
        {"title": "Science", "path": "/news/science", "slug": "science"},
        {"title": "Artificial Intelligence", "path": "/news/ai", "slug": "ai"},
    ]},
    {"title": "Health", "path": "/news/health", "slug": "health"},
    {"title": "Culture", "path": "/news/culture", "slug": "culture", "children": [
        {"title": "Film & TV", "path": "/news/film", "slug": "film"},
        {"title": "Music", "path": "/news/music", "slug": "music"},
        {"title": "Books", "path": "/news/books", "slug": "books"},
        {"title": "Art & Design", "path": "/news/art_design", "slug": "art_design"},
        {"title": "Style", "path": "/news/style", "slug": "style"},
        {"title": "Entertainment News", "path": "/news/entertainment", "slug": "entertainment"},
    ]},
    {"title": "Arts", "path": "/news/arts", "slug": "arts"},
    {"title": "Travel", "path": "/news/travel", "slug": "travel", "children": [
        {"title": "The SpeciaList", "path": "/news/the_specialist", "slug": "the_specialist"},
        {"title": "Destinations", "path": "/news/destinations", "slug": "destinations"},
        {"title": "World's Table", "path": "/news/worlds_table", "slug": "worlds_table"},
    ]},
    {"title": "Earth", "path": "/news/earth", "slug": "earth", "children": [
        {"title": "Natural Wonders", "path": "/news/natural_wonders", "slug": "natural_wonders"},
        {"title": "Green Living", "path": "/news/green_living", "slug": "green_living"},
    ]},
    {"title": "Audio", "path": "/news/audio", "slug": "audio", "children": [
        {"title": "Podcasts", "path": "/news/podcasts", "slug": "podcasts"},
        {"title": "New Releases", "path": "/news/new_releases", "slug": "new_releases"},
        {"title": "Radio", "path": "/news/radio", "slug": "radio"},
    ]},
    {"title": "Weather", "path": "/news/weather", "slug": "weather"},
    {"title": "Video", "path": "/news/video", "slug": "video"},
    {"title": "Live", "path": "/live", "slug": "live"},
]


def _slug_in_subtree(node, target):
    if node.get('slug') == target:
        return True
    for child in node.get('children') or []:
        if _slug_in_subtree(child, target):
            return True
    return False


def _active_path_for(request_path):
    """Return the BBC-nav slug matching the current request, for highlighting."""
    if request_path == '/':
        return 'home'
    parts = request_path.strip('/').split('/')
    if len(parts) >= 2 and parts[0] == 'news':
        return parts[1]
    if parts:
        return parts[0]
    return ''


@app.context_processor
def inject_globals():
    reading_list_count = 0
    bookmark_count = 0
    if current_user.is_authenticated:
        reading_list_count = ReadingListItem.query.filter_by(user_id=current_user.id).count()
        bookmark_count = Bookmark.query.filter_by(user_id=current_user.id).count()

    main_cats = (Category.query.filter(Category.parent_slug == "")
                 .order_by(Category.sort_order).all())
    news_subcats = (Category.query.filter(Category.parent_slug == "news")
                    .order_by(Category.sort_order).all())
    now = datetime.utcnow()
    active_slug = _active_path_for(request.path) if request else ''
    return dict(
        reading_list_count=reading_list_count,
        bookmark_count=bookmark_count,
        main_categories=main_cats,
        news_subcats=news_subcats,
        bbc_nav_tree=BBC_NAV_TREE,
        active_nav_slug=active_slug,
        current_time_str=now.strftime("%H:%M %Z").strip() or now.strftime("%H:%M GMT"),
        current_date_str=now.strftime("%A %d %B %Y"),
        current_year=now.year,
    )


# =======================================================================
# HELPERS
# =======================================================================

def get_article_or_404(slug):
    a = Article.query.filter_by(slug=slug).first()
    if not a:
        abort(404)
    return a


def get_category_or_404(slug):
    c = Category.query.filter_by(slug=slug).first()
    if not c:
        abort(404)
    return c


def articles_for_category(slug, limit=None):
    """Return all articles in a category or its children."""
    cat = Category.query.filter_by(slug=slug).first()
    if not cat:
        return []
    # Include child categories
    child_slugs = [c.slug for c in Category.query.filter_by(parent_slug=slug).all()]
    if child_slugs:
        child_ids = [c.id for c in Category.query.filter(Category.slug.in_(child_slugs + [slug])).all()]
        q = Article.query.filter(Article.category_id.in_(child_ids))
    else:
        q = Article.query.filter_by(category_id=cat.id)
    q = q.order_by(Article.published_at.desc())
    if limit:
        q = q.limit(limit)
    return q.all()


def new_digest_number():
    return "D" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + str(random.randint(100, 999))


# =======================================================================
# ROUTES — PUBLIC PAGES
# =======================================================================

@app.route("/")
def index():
    featured = Article.query.filter_by(is_featured=True).order_by(Article.published_at.desc()).limit(6).all()
    if not featured:
        featured = Article.query.order_by(Article.published_at.desc()).limit(6).all()
    top_story = featured[0] if featured else None
    secondary = featured[1:6] if len(featured) > 1 else []

    latest = Article.query.order_by(Article.published_at.desc()).limit(12).all()
    must_read = Article.query.order_by(func.random()).limit(5).all()

    # Per-category strips
    world_items = articles_for_category("world", limit=4)
    uk_items = articles_for_category("uk", limit=4)
    business_items = articles_for_category("business", limit=4)
    tech_items = articles_for_category("technology", limit=4)

    return render_template(
        "index.html",
        top_story=top_story,
        secondary=secondary,
        latest=latest,
        must_read=must_read,
        world_items=world_items,
        uk_items=uk_items,
        business_items=business_items,
        tech_items=tech_items,
    )


@app.route("/section/<slug>")
@app.route("/news/<slug>")
def section_page(slug):
    cat = get_category_or_404(slug)
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20

    # Regional categories (parent is 'world' or 'uk') also match by region/subsection
    # so that agents navigating to Africa/Asia/Europe see relevant stories even when
    # the canonical section_slug is the parent ('world').
    REGION_MAP = {
        "africa": "Africa",
        "asia": "Asia",
        "australia": "Australia",
        "europe": "Europe",
        "latin_america": "Latin America",
        "middle_east": "Middle East",
        "us_canada": "US & Canada",
        "england": "England",
        "scotland": "Scotland",
        "wales": "Wales",
        "northern_ireland": "N. Ireland",
    }
    region_name = REGION_MAP.get(slug)

    # Include child categories' articles AND articles denormalized to this slug
    child_slugs = [c.slug for c in Category.query.filter_by(parent_slug=slug).all()]
    if child_slugs:
        child_ids = [c.id for c in Category.query.filter(Category.slug.in_(child_slugs + [slug])).all()]
        conds = [
            Article.category_id.in_(child_ids),
            Article.section_slug == slug,
        ]
        if region_name:
            conds.append(Article.region == region_name)
            conds.append(Article.subsection.ilike(f"%{region_name}%"))
        q = Article.query.filter(or_(*conds))
    else:
        conds = [
            Article.category_id == cat.id,
            Article.section_slug == slug,
        ]
        if region_name:
            conds.append(Article.region == region_name)
            conds.append(Article.subsection.ilike(f"%{region_name}%"))
        q = Article.query.filter(or_(*conds))

    # Subsection/region/tag filters (optional)
    subsection = (request.args.get("subsection") or "").strip()
    if subsection:
        q = q.filter(Article.subsection.ilike(f'%{subsection}%'))
    region = (request.args.get("region") or "").strip()
    if region:
        q = q.filter(Article.region.ilike(f'%{region}%'))
    tag = (request.args.get("tag") or "").strip().lower()
    if tag:
        q = q.filter(or_(
            Article.feature_tags.ilike(f'%{tag}%'),
            Article.topics_json.ilike(f'%{tag}%'),
        ))
    content_type = (request.args.get("content_type") or "").strip()
    if content_type:
        q = q.filter(Article.content_type == content_type)

    q = q.order_by(Article.published_at.desc())

    total = q.count()
    articles = q.offset((page - 1) * per_page).limit(per_page).all()
    lead = articles[0] if articles else None
    rest = articles[1:] if len(articles) > 1 else []

    children = Category.query.filter_by(parent_slug=slug).order_by(Category.sort_order).all()

    return render_template(
        "section.html",
        category=cat,
        lead=lead,
        articles=rest,
        total=total,
        page=page,
        per_page=per_page,
        children=children,
    )


def load_article_gallery(slug):
    """Return the full gallery dict for an article slug. Reads from the
    Article.gallery_full_json column so no scraped JSON is needed at
    runtime."""
    art = Article.query.filter_by(slug=slug).first()
    if art is None:
        return {}
    return art.get_full_gallery()


@app.route("/article/<slug>")
def article_detail(slug):
    art = get_article_or_404(slug)
    art.view_count += 1
    db.session.commit()

    # Record reading history
    if current_user.is_authenticated:
        existing = ReadingHistory.query.filter_by(
            user_id=current_user.id, article_id=art.id
        ).first()
        if existing:
            existing.viewed_at = datetime.utcnow()
        else:
            db.session.add(ReadingHistory(user_id=current_user.id, article_id=art.id))
        db.session.commit()

    # Related articles in same category
    related = (Article.query.filter(
        Article.category_id == art.category_id, Article.id != art.id
    ).order_by(func.random()).limit(6).all())
    # More from author (or BBC News default)
    more_articles = (Article.query.filter(Article.id != art.id)
                     .order_by(func.random()).limit(4).all())

    comments_q = Comment.query.filter_by(
        article_id=art.id, parent_id=None
    ).order_by(Comment.created_at.desc()).all()

    in_reading_list = False
    reading_list_item = None
    is_bookmarked = False
    if current_user.is_authenticated:
        reading_list_item = ReadingListItem.query.filter_by(
            user_id=current_user.id, article_id=art.id
        ).first()
        in_reading_list = reading_list_item is not None
        is_bookmarked = Bookmark.query.filter_by(
            user_id=current_user.id, article_id=art.id
        ).first() is not None

    # Load gallery sections
    article_gallery = load_article_gallery(slug)

    return render_template(
        "article_detail.html",
        article=art,
        article_share_url=bbc_article_share_url(art),
        article_gallery=article_gallery,
        related=related,
        more_articles=more_articles,
        comments=comments_q,
        in_reading_list=in_reading_list,
        reading_list_item=reading_list_item,
        is_bookmarked=is_bookmarked,
    )


@app.route("/topic/<topic>")
def topic_page(topic):
    like_tag = f'%"{topic}"%'
    like_ft = f'%{topic.lower()}%'
    results = (Article.query.filter(or_(
            Article.topics_json.ilike(like_tag),
            Article.feature_tags.ilike(like_ft),
            Article.subsection.ilike(f'%{topic}%'),
        )).order_by(Article.published_at.desc()).limit(100).all())
    return render_template("topic.html", topic=topic, results=results)


STOPWORDS = {
    'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with',
    'and', 'or', 'is', 'are', 'be', 'by', 'from', 'as', 'that', 'this',
    'about', 'into', 'what', 'who', 'how', 'when', 'where', 'which',
    'some', 'any', 'it', 'its', 'their', 'news', 'bbc', 'article', 'story',
    'latest', 'recent', 'report', 'find', 'get', 'read', 'search',
}


def _score_article(article, tokens):
    """Score an article against search tokens. Returns # of distinct tokens matched."""
    haystack = ' '.join([
        (article.headline or '').lower(),
        (article.subtitle or '').lower(),
        (article.summary or '').lower(),
        (article.body or '').lower()[:4000],  # cap for speed
        (article.author or '').lower(),
        (article.topics_json or '').lower(),
        (article.feature_tags or '').lower(),
        (article.subsection or '').lower(),
        (article.section_slug or '').lower(),
        (article.region or '').lower(),
        (article.location or '').lower(),
    ])
    return sum(1 for t in tokens if t in haystack)


def _apply_article_filters(query_obj):
    """Apply request.args filters to an Article query."""
    section = (request.args.get("section") or "").strip().lower()
    if section:
        # Match denormalized section_slug OR category.slug (via join)
        child_slugs = {c.slug for c in Category.query.filter_by(parent_slug=section).all()}
        allowed = {section} | child_slugs
        cat_ids = [c.id for c in Category.query.filter(Category.slug.in_(allowed)).all()]
        query_obj = query_obj.filter(or_(
            Article.section_slug == section,
            Article.category_id.in_(cat_ids) if cat_ids else False,
        ))

    subsection = (request.args.get("subsection") or "").strip()
    if subsection:
        query_obj = query_obj.filter(Article.subsection.ilike(f'%{subsection}%'))

    region = (request.args.get("region") or "").strip()
    if region:
        query_obj = query_obj.filter(Article.region.ilike(f'%{region}%'))

    tag = (request.args.get("tag") or "").strip().lower()
    if tag:
        query_obj = query_obj.filter(or_(
            Article.feature_tags.ilike(f'%{tag}%'),
            Article.topics_json.ilike(f'%{tag}%'),
        ))

    content_type = (request.args.get("content_type") or "").strip()
    if content_type:
        query_obj = query_obj.filter(Article.content_type == content_type)

    since_days = request.args.get("since_days", type=int)
    if since_days is not None:
        cutoff = datetime.utcnow() - timedelta(days=since_days)
        query_obj = query_obj.filter(Article.published_at >= cutoff)

    return query_obj


def _apply_article_sort(results, sort_key):
    if sort_key in ('newest', 'date_desc', 'latest'):
        return sorted(results, key=lambda a: a.published_at or datetime.min, reverse=True)
    if sort_key in ('oldest', 'date_asc'):
        return sorted(results, key=lambda a: a.published_at or datetime.min)
    if sort_key in ('popular', 'views'):
        return sorted(results, key=lambda a: a.view_count or 0, reverse=True)
    # default: newest
    return sorted(results, key=lambda a: a.published_at or datetime.min, reverse=True)


@app.route("/search")
def search():
    q = (request.args.get("q") or request.args.get("query") or "").strip()
    scope = request.args.get("scope", "all")
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20

    query_obj = Article.query
    query_obj = _apply_article_filters(query_obj)
    candidates = query_obj.all()

    if q:
        tokens = [t.lower() for t in re.findall(r'[a-z0-9]+', q.lower())
                  if t and t not in STOPWORDS and len(t) >= 2]
        if tokens:
            min_required = max(1, len(tokens) // 2)
            scored = []
            for a in candidates:
                if scope == "headline":
                    haystack = (a.headline or '').lower()
                    s = sum(1 for t in tokens if t in haystack)
                elif scope == "body":
                    haystack = (a.body or '').lower()
                    s = sum(1 for t in tokens if t in haystack)
                else:
                    s = _score_article(a, tokens)
                if s >= min_required:
                    scored.append((s, a))
            scored.sort(key=lambda x: (-x[0],
                                       -(x[1].published_at.timestamp() if x[1].published_at else 0)))
            results = [a for _, a in scored]
        else:
            results = candidates
    else:
        results = candidates

    results = _apply_article_sort(results, request.args.get("sort", "newest"))
    total = len(results)
    start = (page - 1) * per_page
    page_results = results[start:start + per_page]

    return render_template(
        "search.html",
        query=q, scope=scope, results=page_results, total=total,
        page=page, per_page=per_page,
    )


@app.route("/latest")
def latest_page():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 25
    q = Article.query.order_by(Article.published_at.desc())
    total = q.count()
    articles = q.offset((page - 1) * per_page).limit(per_page).all()
    return render_template("latest.html", articles=articles, total=total, page=page, per_page=per_page)


@app.route("/live")
def live_page():
    live_articles = Article.query.filter_by(is_live=True).all()
    breaking = Article.query.filter_by(is_breaking=True).order_by(Article.published_at.desc()).limit(10).all()
    return render_template("live.html", live=live_articles, breaking=breaking)


@app.route("/weather")
def weather_alias():
    return redirect(url_for("section_page", slug="weather"))


@app.route("/audio")
def audio_alias():
    return redirect(url_for("section_page", slug="audio"))


@app.route("/culture")
def culture_alias():
    return redirect(url_for("section_page", slug="culture"))


@app.route("/sport")
def sport_alias():
    return redirect(url_for("section_page", slug="sport"))


@app.route("/about")
def about_page():
    return render_template("about.html")


@app.route("/help")
def help_page():
    return render_template("help.html")


@app.route("/contact")
def contact_page():
    return render_template("contact.html")


# =======================================================================
# ROUTES — AUTH
# =======================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Signed in successfully.", "success")
            next_url = request.args.get("next") or url_for("account")
            return redirect(next_url)
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        username = (request.form.get("username") or "").strip()
        full_name = (request.form.get("full_name") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        if not (email and username and password):
            flash("Email, username, and password are all required.", "error")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("register.html")
        if User.query.filter_by(username=username).first():
            flash("That username is already taken.", "error")
            return render_template("register.html")
        u = User(email=email, username=username, full_name=full_name)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash("Account created. Welcome to BBC News.", "success")
        return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("index"))


# =======================================================================
# ROUTES — ACCOUNT
# =======================================================================

@app.route("/account")
@login_required
def account():
    recent_rl = (ReadingListItem.query.filter_by(user_id=current_user.id)
                 .order_by(ReadingListItem.added_at.desc()).limit(5).all())
    recent_bm = (Bookmark.query.filter_by(user_id=current_user.id)
                 .order_by(Bookmark.bookmarked_at.desc()).limit(5).all())
    digests = (Digest.query.filter_by(user_id=current_user.id)
               .order_by(Digest.created_at.desc()).all())
    my_comments = (Comment.query.filter_by(user_id=current_user.id)
                   .order_by(Comment.created_at.desc()).limit(10).all())
    subs = TopicSubscription.query.filter_by(user_id=current_user.id).all()
    history = (ReadingHistory.query.filter_by(user_id=current_user.id)
               .order_by(ReadingHistory.viewed_at.desc()).limit(10).all())
    return render_template(
        "account.html",
        recent_rl=recent_rl,
        recent_bm=recent_bm,
        digests=digests,
        my_comments=my_comments,
        subs=subs,
        history=history,
    )


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        current_user.full_name = request.form.get("full_name", "").strip()
        current_user.location = request.form.get("location", "").strip()
        current_user.bio = request.form.get("bio", "").strip()
        current_user.notification_email = request.form.get("notification_email") == "on"
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        if not current_user.check_password(current):
            flash("Current password is incorrect.", "error")
        elif new != confirm:
            flash("New passwords do not match.", "error")
        elif len(new) < 6:
            flash("Password must be at least 6 characters.", "error")
        else:
            current_user.set_password(new)
            db.session.commit()
            flash("Password updated.", "success")
            return redirect(url_for("account"))
    return render_template("change_password.html")


@app.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    uid = current_user.id
    logout_user()
    user = db.session.get(User, uid)
    if user:
        db.session.delete(user)
        db.session.commit()
    flash("Your account has been deleted.", "success")
    return redirect(url_for("index"))


@app.route("/history")
@login_required
def history_page():
    items = (ReadingHistory.query.filter_by(user_id=current_user.id)
             .order_by(ReadingHistory.viewed_at.desc()).limit(100).all())
    return render_template("history.html", items=items)


@app.route("/history/clear", methods=["POST"])
@login_required
def clear_history():
    ReadingHistory.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash("Reading history cleared.", "success")
    return redirect(url_for("history_page"))


# =======================================================================
# ROUTES — READING LIST (cart analog)
# =======================================================================

@app.route("/reading-list")
@login_required
def reading_list():
    folder = request.args.get("folder", "")
    q = ReadingListItem.query.filter_by(user_id=current_user.id)
    if folder:
        q = q.filter_by(folder=folder)
    items = q.order_by(ReadingListItem.added_at.desc()).all()
    folders = (db.session.query(ReadingListItem.folder, func.count(ReadingListItem.id))
               .filter_by(user_id=current_user.id)
               .group_by(ReadingListItem.folder).all())
    return render_template("reading_list.html", items=items, folders=folders, current_folder=folder)


@app.route("/api/reading-list/add", methods=["POST"])
@login_required
@csrf.exempt
def api_reading_list_add():
    # Accept both JSON (legacy AJAX) and form POST (CDP browser agent)
    if request.content_type and "application/json" in request.content_type:
        data = request.get_json() or {}
    else:
        data = request.form
    article_id = int(data.get("article_id", 0))
    folder = (data.get("folder") or "Read Later")[:100]
    note = (data.get("note") or "")[:500]
    art = Article.query.get(article_id)
    if not art:
        if request.content_type and "application/json" in request.content_type:
            return jsonify({"success": False, "message": "Article not found"}), 404
        flash("Article not found.", "error")
        return redirect(request.referrer or url_for("reading_list"))
    existing = ReadingListItem.query.filter_by(
        user_id=current_user.id, article_id=article_id
    ).first()
    if existing:
        existing.folder = folder
        if note:
            existing.note = note
        db.session.commit()
        if request.content_type and "application/json" in request.content_type:
            return jsonify({
                "success": True,
                "message": "Reading list updated",
                "reading_list_count": ReadingListItem.query.filter_by(user_id=current_user.id).count(),
            })
        flash("Reading list updated.", "success")
        return redirect(request.referrer or url_for("reading_list"))
    item = ReadingListItem(
        user_id=current_user.id, article_id=article_id, folder=folder, note=note,
    )
    db.session.add(item)
    db.session.commit()
    if request.content_type and "application/json" in request.content_type:
        return jsonify({
            "success": True,
            "message": "Added to your reading list",
            "reading_list_count": ReadingListItem.query.filter_by(user_id=current_user.id).count(),
        })
    flash("Added to your reading list.", "success")
    return redirect(request.referrer or url_for("reading_list"))


@app.route("/api/reading-list/remove", methods=["POST"])
@login_required
@csrf.exempt
def api_reading_list_remove():
    # Accept both JSON (legacy AJAX) and form POST (CDP browser agent)
    if request.content_type and "application/json" in request.content_type:
        data = request.get_json() or {}
    else:
        data = request.form
    item_id = int(data.get("item_id", 0))
    item = ReadingListItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        if request.content_type and "application/json" in request.content_type:
            return jsonify({"success": False, "message": "Not found"}), 404
        flash("Item not found.", "error")
        return redirect(url_for("reading_list"))
    db.session.delete(item)
    db.session.commit()
    if request.content_type and "application/json" in request.content_type:
        return jsonify({
            "success": True,
            "reading_list_count": ReadingListItem.query.filter_by(user_id=current_user.id).count(),
        })
    flash("Removed from reading list.", "success")
    return redirect(url_for("reading_list"))


@app.route("/reading-list/item/<int:item_id>/update", methods=["POST"])
@login_required
def reading_list_update_item(item_id):
    """Form POST: update folder and/or priority of a reading list item."""
    item = ReadingListItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    folder = (request.form.get("folder") or "").strip()[:100]
    priority = (request.form.get("priority") or "").strip()
    if folder:
        item.folder = folder
    if priority in ("high", "normal", "low"):
        item.priority = priority
    db.session.commit()
    flash("Reading list item updated.", "success")
    return redirect(url_for("reading_list"))


@app.route("/api/reading-list/mark-read", methods=["POST"])
@login_required
@csrf.exempt
def api_reading_list_mark_read():
    data = request.get_json() or {}
    item_id = int(data.get("item_id", 0))
    item = ReadingListItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify({"success": False}), 404
    item.read = not item.read
    db.session.commit()
    return jsonify({"success": True, "read": item.read})


@app.route("/reading-list/folder/create", methods=["POST"])
@login_required
def reading_list_folder_create():
    folder = (request.form.get("folder") or "").strip()[:100]
    article_id = request.form.get("article_id", type=int)
    if folder and article_id:
        existing = ReadingListItem.query.filter_by(
            user_id=current_user.id, article_id=article_id
        ).first()
        if existing:
            existing.folder = folder
        else:
            db.session.add(ReadingListItem(
                user_id=current_user.id, article_id=article_id, folder=folder,
            ))
        db.session.commit()
        flash(f"Saved to '{folder}'.", "success")
    return redirect(request.referrer or url_for("reading_list"))


# =======================================================================
# ROUTES — BOOKMARKS (wishlist analog)
# =======================================================================

@app.route("/bookmarks")
@login_required
def bookmarks_page():
    items = (Bookmark.query.filter_by(user_id=current_user.id)
             .order_by(Bookmark.bookmarked_at.desc()).all())
    return render_template("bookmarks.html", items=items)


@app.route("/api/bookmark/toggle", methods=["POST"])
@login_required
@csrf.exempt
def api_bookmark_toggle():
    # Accept both JSON (legacy AJAX) and form POST (CDP browser agent)
    if request.content_type and "application/json" in request.content_type:
        data = request.get_json() or {}
    else:
        data = request.form
    article_id = int(data.get("article_id", 0))
    art = Article.query.get(article_id)
    if not art:
        if request.content_type and "application/json" in request.content_type:
            return jsonify({"success": False}), 404
        flash("Article not found.", "error")
        return redirect(request.referrer or url_for("bookmarks_page"))
    existing = Bookmark.query.filter_by(
        user_id=current_user.id, article_id=article_id
    ).first()
    if existing:
        db.session.delete(existing)
        action = "removed"
        flash_msg = "Bookmark removed."
    else:
        db.session.add(Bookmark(user_id=current_user.id, article_id=article_id))
        action = "added"
        flash_msg = "Bookmarked."
    db.session.commit()
    count = Bookmark.query.filter_by(user_id=current_user.id).count()
    if request.content_type and "application/json" in request.content_type:
        return jsonify({"success": True, "action": action, "bookmark_count": count})
    flash(flash_msg, "success")
    return redirect(request.referrer or url_for("bookmarks_page"))


@app.route("/bookmarks/remove/<int:item_id>", methods=["POST"])
@login_required
def bookmarks_remove(item_id):
    item = Bookmark.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Bookmark removed.", "success")
    return redirect(url_for("bookmarks_page"))


# =======================================================================
# ROUTES — DIGESTS (order analog)
# =======================================================================

@app.route("/digest", methods=["GET", "POST"])
@login_required
def digest_create():
    if request.method == "POST":
        fmt = request.form.get("format", "email")
        source = request.form.get("source", "reading_list")
        title = (request.form.get("title") or "My News Digest")[:200]
        notes = request.form.get("notes", "")
        email = (request.form.get("delivery_email") or current_user.email).strip()
        article_ids = []
        if source == "reading_list":
            items = ReadingListItem.query.filter_by(user_id=current_user.id).all()
            article_ids = [i.article_id for i in items]
        elif source == "bookmarks":
            items = Bookmark.query.filter_by(user_id=current_user.id).all()
            article_ids = [i.article_id for i in items]
        elif source == "latest":
            latest = Article.query.order_by(Article.published_at.desc()).limit(10).all()
            article_ids = [a.id for a in latest]
        if not article_ids:
            flash("No articles available for digest.", "error")
            return redirect(url_for("reading_list"))
        digest = Digest(
            user_id=current_user.id,
            digest_number=new_digest_number(),
            title=title,
            format=fmt,
            status="delivered",
            article_count=len(article_ids),
            delivery_email=email,
            notes=notes,
        )
        db.session.add(digest)
        db.session.flush()
        for aid in article_ids:
            db.session.add(DigestItem(digest_id=digest.id, article_id=aid))
        db.session.commit()
        flash("Digest created.", "success")
        return redirect(url_for("digest_detail", digest_number=digest.digest_number))
    rl_items = ReadingListItem.query.filter_by(user_id=current_user.id).all()
    bm_items = Bookmark.query.filter_by(user_id=current_user.id).all()
    return render_template("digest_create.html", rl_items=rl_items, bm_items=bm_items)


@app.route("/digest/<digest_number>")
@login_required
def digest_detail(digest_number):
    digest = Digest.query.filter_by(
        digest_number=digest_number, user_id=current_user.id
    ).first_or_404()
    return render_template("digest_detail.html", digest=digest)


@app.route("/digest/<digest_number>/cancel", methods=["POST"])
@login_required
def digest_cancel(digest_number):
    digest = Digest.query.filter_by(
        digest_number=digest_number, user_id=current_user.id
    ).first_or_404()
    if digest.status in ("pending", "delivered"):
        digest.status = "cancelled"
        db.session.commit()
        flash("Digest cancelled.", "success")
    else:
        flash("Cannot cancel this digest.", "error")
    return redirect(url_for("digest_detail", digest_number=digest_number))


@app.route("/digest/<digest_number>/resend", methods=["POST"])
@login_required
def digest_resend(digest_number):
    digest = Digest.query.filter_by(
        digest_number=digest_number, user_id=current_user.id
    ).first_or_404()
    added = 0
    for it in digest.items:
        if not ReadingListItem.query.filter_by(
            user_id=current_user.id, article_id=it.article_id
        ).first():
            db.session.add(ReadingListItem(
                user_id=current_user.id, article_id=it.article_id, folder="From Digest",
            ))
            added += 1
    db.session.commit()
    flash(f"Added {added} articles to your reading list.", "success")
    return redirect(url_for("reading_list"))


@app.route("/digest/<digest_number>/download")
@login_required
def digest_download(digest_number):
    digest = Digest.query.filter_by(
        digest_number=digest_number, user_id=current_user.id
    ).first_or_404()
    articles = [it.article for it in digest.items if it.article]
    if digest.format == "email":
        body = f"{digest.title}\n{'=' * 50}\n\nDigest #{digest.digest_number}\nDelivered {digest.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        for a in articles:
            body += f"{a.headline}\n{a.summary or a.subtitle or ''}\n{a.source_url}\n\n"
    elif digest.format == "rss":
        body = '<?xml version="1.0"?>\n<rss version="2.0"><channel>\n'
        body += f"<title>{digest.title}</title>\n"
        for a in articles:
            body += f"<item><title>{a.headline}</title><link>{a.source_url}</link><description>{a.summary}</description></item>\n"
        body += "</channel></rss>"
    else:  # text/pdf fallback
        body = "\n\n".join(
            f"[{a.category.name if a.category else ''}]\n{a.headline}\n{a.summary or a.subtitle or ''}"
            for a in articles
        )
    mt = "application/rss+xml" if digest.format == "rss" else "text/plain"
    ext = "xml" if digest.format == "rss" else "txt"
    return Response(body, mimetype=mt, headers={
        "Content-Disposition": f"attachment; filename={digest.digest_number}.{ext}",
    })


# =======================================================================
# ROUTES — COMMENTS (review analog)
# =======================================================================

@app.route("/article/<slug>/comment", methods=["POST"])
@login_required
def submit_comment(slug):
    art = get_article_or_404(slug)
    body = (request.form.get("body") or "").strip()
    parent_id = request.form.get("parent_id", type=int)
    if not body:
        flash("Comment cannot be empty.", "error")
    else:
        db.session.add(Comment(
            user_id=current_user.id,
            article_id=art.id,
            body=body[:2000],
            parent_id=parent_id if parent_id else None,
        ))
        db.session.commit()
        flash("Comment posted.", "success")
    return redirect(url_for("article_detail", slug=slug))


@app.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    c = Comment.query.get_or_404(comment_id)
    if c.user_id != current_user.id:
        abort(403)
    slug = c.article.slug
    db.session.delete(c)
    db.session.commit()
    flash("Comment deleted.", "success")
    return redirect(url_for("article_detail", slug=slug))


@app.route("/api/comment/like", methods=["POST"])
@login_required
@csrf.exempt
def api_comment_like():
    data = request.get_json() or {}
    cid = int(data.get("comment_id", 0))
    c = Comment.query.get(cid)
    if not c:
        return jsonify({"success": False}), 404
    c.like_count += 1
    db.session.commit()
    return jsonify({"success": True, "like_count": c.like_count})


# =======================================================================
# ROUTES — SUBSCRIPTIONS
# =======================================================================

@app.route("/subscriptions", methods=["GET", "POST"])
@login_required
def subscriptions_page():
    if request.method == "POST":
        slug = request.form.get("category_slug", "").strip()
        topic = request.form.get("topic", "").strip()
        freq = request.form.get("frequency", "daily")
        if slug or topic:
            existing = TopicSubscription.query.filter_by(
                user_id=current_user.id, category_slug=slug, topic=topic
            ).first()
            if existing:
                existing.frequency = freq
                existing.active = True
                flash("Subscription updated.", "success")
            else:
                db.session.add(TopicSubscription(
                    user_id=current_user.id,
                    category_slug=slug,
                    topic=topic,
                    frequency=freq,
                ))
                flash("Subscribed.", "success")
            db.session.commit()
        return redirect(url_for("subscriptions_page"))
    subs = TopicSubscription.query.filter_by(user_id=current_user.id).all()
    return render_template("subscriptions.html", subs=subs)


@app.route("/subscriptions/<int:sub_id>/delete", methods=["POST"])
@login_required
def delete_subscription(sub_id):
    sub = TopicSubscription.query.filter_by(
        id=sub_id, user_id=current_user.id
    ).first_or_404()
    db.session.delete(sub)
    db.session.commit()
    flash("Subscription removed.", "success")
    return redirect(url_for("subscriptions_page"))


@app.route("/subscriptions/<int:sub_id>/update", methods=["POST"])
@login_required
def update_subscription(sub_id):
    sub = TopicSubscription.query.filter_by(
        id=sub_id, user_id=current_user.id
    ).first_or_404()
    freq = request.form.get("frequency", "").strip()
    if freq in ("daily", "weekly", "breaking_only"):
        sub.frequency = freq
        db.session.commit()
        flash("Subscription frequency updated.", "success")
    else:
        flash("Invalid frequency.", "error")
    return redirect(url_for("subscriptions_page"))


# =======================================================================
# ROUTES — API
# =======================================================================

@app.route("/api/articles/<slug>")
def api_category_articles(slug):
    cat = Category.query.filter_by(slug=slug).first_or_404()
    articles = (Article.query.filter_by(category_id=cat.id)
                .order_by(Article.published_at.desc()).limit(20).all())
    return jsonify({
        "category": cat.slug,
        "name": cat.name,
        "count": len(articles),
        "articles": [{
            "slug": a.slug,
            "headline": a.headline,
            "summary": a.summary,
            "image": a.hero_image,
            "published": a.published_at.isoformat() if a.published_at else None,
            "reading_time": a.reading_time,
        } for a in articles],
    })


@app.route("/api/stats")
def api_stats():
    return jsonify({
        "total_articles": Article.query.count(),
        "total_categories": Category.query.count(),
        "total_users": User.query.count(),
        "total_comments": Comment.query.count(),
    })


# =======================================================================
# ERROR HANDLERS
# =======================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Something went wrong"), 500


# =======================================================================
# MAIN
# =======================================================================

def _ensure_gallery_full_column():
    """Idempotent: add the gallery_full_json column to existing DBs that
    were seeded before this column was introduced."""
    import sqlite3 as _sqlite3
    db_path = os.path.join(BASE_DIR, "instance", "bbc_news.db")
    if not os.path.exists(db_path):
        return
    conn = _sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cols = {r[1] for r in cur.execute("PRAGMA table_info(articles)").fetchall()}
        if "gallery_full_json" not in cols:
            cur.execute("ALTER TABLE articles ADD COLUMN gallery_full_json TEXT DEFAULT '{}'")
            conn.commit()
    finally:
        conn.close()


with app.app_context():
    _ensure_gallery_full_column()
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 28843))
    app.run(host="0.0.0.0", port=port, debug=False)
