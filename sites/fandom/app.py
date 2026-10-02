"""Fandom mirror — Flask app.

Models a Fandom hub of three wikis (Marvel Cinematic Universe, Star Wars,
Genshin Impact), each with the full MediaWiki-style page archetype:
article, edit, history, diff, talk, user, recent changes, categories,
search, what-links-here, random, plus the hub homepage.

Page model:
    Wiki              = a fandom wiki (mcu / starwars / genshin)
    Article           = a page within a wiki (title, slug, latest content, infobox)
    Revision          = an immutable historical version of an article
    Category          = wiki-scoped category
    TalkPost          = a post on Talk:<article>
    WatchItem         = user watch
    Poll              = a wiki poll (votes counted from PollVote)
"""
import os
import re
import json
import random
import difflib
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify,
    session, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from sqlalchemy import or_, and_, func, desc
from sqlalchemy.orm import defer

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "instance"
DB_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "fandom-mirror-secret-key-change-in-prod-2026"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_DIR / 'fandom.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None
app.config["TEMPLATES_AUTO_RELOAD"] = True

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
csrf = CSRFProtect(app)


# =======================================================================
# MODELS
# =======================================================================

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.Text, default="")
    avatar_color = db.Column(db.String(16), default="#fa0046")
    groups = db.Column(db.String(200), default="autoconfirmed")
    joined = db.Column(db.DateTime, default=datetime.utcnow)
    home_wiki = db.Column(db.String(40), default="")

    def set_password(self, raw: str):
        self.password_hash = bcrypt.generate_password_hash(raw).decode("utf-8")

    def check_password(self, raw: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def edit_count(self) -> int:
        return Revision.query.filter_by(user_id=self.id).count()

    @property
    def group_list(self):
        return [g.strip() for g in (self.groups or "").split(",") if g.strip()]


class Wiki(db.Model):
    __tablename__ = "wikis"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    tagline = db.Column(db.String(280), default="")
    hero_image = db.Column(db.String(200), default="")
    accent = db.Column(db.String(20), default="#fa0046")
    description = db.Column(db.Text, default="")
    featured_article_slug = db.Column(db.String(160), default="")
    article_count = db.Column(db.Integer, default=0)
    page_count = db.Column(db.Integer, default=0)
    discussion_count = db.Column(db.Integer, default=0)
    members_count = db.Column(db.Integer, default=0)


class Article(db.Model):
    __tablename__ = "articles"
    id = db.Column(db.Integer, primary_key=True)
    wiki_id = db.Column(db.Integer, db.ForeignKey("wikis.id"), nullable=False, index=True)
    title = db.Column(db.String(240), nullable=False)
    slug = db.Column(db.String(240), nullable=False, index=True)
    summary = db.Column(db.Text, default="")
    content = db.Column(db.Text, default="")
    infobox_kind = db.Column(db.String(40), default="")
    infobox_json = db.Column(db.Text, default="{}")
    image = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    view_count = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    namespace = db.Column(db.String(40), default="Main")

    wiki = db.relationship("Wiki", backref="articles")
    __table_args__ = (db.UniqueConstraint("wiki_id", "slug", name="uq_wiki_slug"),)

    @property
    def infobox(self) -> dict:
        try:
            return json.loads(self.infobox_json or "{}")
        except Exception:
            return {}

    @property
    def categories(self):
        rows = ArticleCategory.query.filter_by(article_id=self.id).all()
        return [r.category for r in rows if r.category is not None]


class Revision(db.Model):
    __tablename__ = "revisions"
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    author_label = db.Column(db.String(80), default="")
    summary = db.Column(db.String(400), default="")
    content = db.Column(db.Text, default="")
    minor = db.Column(db.Boolean, default=False)
    bot = db.Column(db.Boolean, default=False)
    bytes_size = db.Column(db.Integer, default=0)
    bytes_delta = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    article = db.relationship("Article", backref="revisions")
    user = db.relationship("User", backref="revisions")


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    wiki_id = db.Column(db.Integer, db.ForeignKey("wikis.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(160), nullable=False, index=True)
    parent_slug = db.Column(db.String(160), default="")
    description = db.Column(db.Text, default="")
    wiki = db.relationship("Wiki", backref="cats")
    __table_args__ = (db.UniqueConstraint("wiki_id", "slug", name="uq_cat_slug"),)


class ArticleCategory(db.Model):
    __tablename__ = "article_categories"
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), primary_key=True)
    article = db.relationship("Article")
    category = db.relationship("Category")


class TalkPost(db.Model):
    __tablename__ = "talk_posts"
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    author_label = db.Column(db.String(80), default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("talk_posts.id"), nullable=True)
    subject = db.Column(db.String(280), default="")
    body = db.Column(db.Text, default="")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user = db.relationship("User", backref="talk_posts")
    article = db.relationship("Article", backref="talk_posts")


class WatchItem(db.Model):
    __tablename__ = "watch_items"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), primary_key=True)
    since = db.Column(db.DateTime, default=datetime.utcnow)


class Poll(db.Model):
    __tablename__ = "polls"
    id = db.Column(db.Integer, primary_key=True)
    wiki_id = db.Column(db.Integer, db.ForeignKey("wikis.id"), nullable=False)
    question = db.Column(db.String(280), nullable=False)
    options_json = db.Column(db.Text, default="[]")
    is_active = db.Column(db.Boolean, default=True)
    wiki = db.relationship("Wiki", backref="polls")

    @property
    def options(self):
        try:
            return json.loads(self.options_json)
        except Exception:
            return []

    def results(self):
        rows = (db.session.query(PollVote.choice_idx, func.count(PollVote.id))
                .filter(PollVote.poll_id == self.id)
                .group_by(PollVote.choice_idx).all())
        d = {i: 0 for i in range(len(self.options))}
        for idx, c in rows:
            d[idx] = c
        return d


class PollVote(db.Model):
    __tablename__ = "poll_votes"
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("polls.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    choice_idx = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reason = db.Column(db.String(120), default="")
    detail = db.Column(db.Text, default="")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- Phase 2 extensions ----------

class FileAsset(db.Model):
    """File: namespace records — images uploaded to a wiki."""
    __tablename__ = "files"
    id = db.Column(db.Integer, primary_key=True)
    wiki_id = db.Column(db.Integer, db.ForeignKey("wikis.id"), nullable=False, index=True)
    filename = db.Column(db.String(200), nullable=False, index=True)
    display_name = db.Column(db.String(240), default="")
    description = db.Column(db.Text, default="")
    license = db.Column(db.String(80), default="Fair use")
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    uploader_label = db.Column(db.String(80), default="")
    bytes_size = db.Column(db.Integer, default=0)
    width = db.Column(db.Integer, default=0)
    height = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    mime_type = db.Column(db.String(40), default="image/jpeg")
    wiki = db.relationship("Wiki", backref="files")
    uploader = db.relationship("User", backref="uploads")


class ForumThread(db.Model):
    """Fandom-style discussion thread (per-wiki forum)."""
    __tablename__ = "forum_threads"
    id = db.Column(db.Integer, primary_key=True)
    wiki_id = db.Column(db.Integer, db.ForeignKey("wikis.id"), nullable=False, index=True)
    category = db.Column(db.String(60), default="General")
    title = db.Column(db.String(280), nullable=False)
    slug = db.Column(db.String(280), index=True)
    body = db.Column(db.Text, default="")
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    author_label = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    view_count = db.Column(db.Integer, default=0)
    is_pinned = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    wiki = db.relationship("Wiki", backref="threads")
    author = db.relationship("User", backref="threads")


class ForumPost(db.Model):
    __tablename__ = "forum_posts"
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("forum_threads.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    author_label = db.Column(db.String(80), default="")
    body = db.Column(db.Text, default="")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    likes = db.Column(db.Integer, default=0)
    thread = db.relationship("ForumThread", backref="posts")
    author = db.relationship("User", backref="forum_posts")


class ArticleComment(db.Model):
    """Fandom article comments (distinct from talk page)."""
    __tablename__ = "article_comments"
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    author_label = db.Column(db.String(80), default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("article_comments.id"), nullable=True)
    body = db.Column(db.Text, default="")
    likes = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    article = db.relationship("Article", backref="comments")
    author = db.relationship("User", backref="article_comments")


class Notice(db.Model):
    """MediaWiki:Sitenotice — wiki-level announcement banner."""
    __tablename__ = "notices"
    id = db.Column(db.Integer, primary_key=True)
    wiki_id = db.Column(db.Integer, db.ForeignKey("wikis.id"), nullable=True)
    title = db.Column(db.String(200), default="")
    body = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    wiki = db.relationship("Wiki", backref="notices")


class UserBlock(db.Model):
    __tablename__ = "user_blocks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    blocker_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reason = db.Column(db.String(200), default="")
    duration = db.Column(db.String(40), default="indefinite")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    blocked_user = db.relationship("User", foreign_keys=[user_id])


class UserFollow(db.Model):
    __tablename__ = "user_follows"
    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    followee_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    since = db.Column(db.DateTime, default=datetime.utcnow)


class WikiSubscription(db.Model):
    __tablename__ = "wiki_subs"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    wiki_id = db.Column(db.Integer, db.ForeignKey("wikis.id"), primary_key=True)
    since = db.Column(db.DateTime, default=datetime.utcnow)


class CommentLike(db.Model):
    __tablename__ = "comment_likes"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("article_comments.id"), primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Protection(db.Model):
    __tablename__ = "protections"
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), primary_key=True)
    level = db.Column(db.String(20), default="autoconfirmed")  # autoconfirmed / sysop
    reason = db.Column(db.String(200), default="")
    set_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    set_at = db.Column(db.DateTime, default=datetime.utcnow)
    article = db.relationship("Article", backref="protection")


# =======================================================================
# HELPERS
# =======================================================================

def slugify(title: str) -> str:
    """MediaWiki-style: spaces -> underscores, preserve case."""
    s = (title or "").strip().replace(" ", "_")
    s = re.sub(r"[^\w\-_/():.]", "", s, flags=re.UNICODE)
    return s


def unslug(slug: str) -> str:
    return (slug or "").replace("_", " ")


@app.template_filter("wiki_excerpt")
def wiki_excerpt(value):
    """Display plain snippets without exposing stored wiki markup."""
    text = re.sub(r"\[\[([^]\|]+)\|([^]]+)\]\]", r"\2", value or "")
    text = re.sub(r"\[\[([^]]+)\]\]", r"\1", text)
    return text.replace("'" * 3, "").replace("'" * 2, "")


@app.template_filter("nice_title")
def nice_title(s):
    return unslug(s or "")


@app.template_filter("ago")
def ago(dt):
    if not dt:
        return ""
    delta = datetime.utcnow() - dt
    if delta.days >= 365:
        y = delta.days // 365
        return f"{y} year{'s' if y != 1 else ''} ago"
    if delta.days >= 30:
        m = delta.days // 30
        return f"{m} month{'s' if m != 1 else ''} ago"
    if delta.days >= 1:
        return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
    h = delta.seconds // 3600
    if h:
        return f"{h} hour{'s' if h != 1 else ''} ago"
    m = max(delta.seconds // 60, 1)
    return f"{m} minute{'s' if m != 1 else ''} ago"


@app.template_filter("ts")
def ts(dt):
    if not dt:
        return ""
    return dt.strftime("%H:%M, %d %B %Y")


def render_wikitext(text: str, wiki_slug: str = "", edit_url: str = "") -> str:
    """Tiny wikitext renderer used at view time."""
    if not text:
        return ""
    out = []
    in_ul = False
    in_ol = False
    lines = text.splitlines()
    para_buf = []
    wiki_row = Wiki.query.filter_by(slug=wiki_slug).first() if wiki_slug else None

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>"); in_ul = False
        if in_ol:
            out.append("</ol>"); in_ol = False

    def link_sub(m):
        inner = m.group(1)
        if "|" in inner:
            tgt, label = inner.split("|", 1)
        else:
            tgt, label = inner, inner
        tgt = tgt.strip(); label = label.strip()
        if not wiki_row:
            return f'<a class="wikilink" href="#">{label}</a>'
        href = url_for("article_view", wiki_slug=wiki_row.slug, title=slugify(tgt))
        exists = Article.query.filter_by(wiki_id=wiki_row.id, slug=slugify(tgt)).first() is not None
        cls = "wikilink" + ("" if exists else " redlink")
        return f'<a class="{cls}" href="{href}">{label}</a>'

    def inline(s: str) -> str:
        s = re.sub(r"\[\[\s*Category\s*:[^\]]+\]\]", "", s,
                   flags=re.IGNORECASE)
        s = re.sub(r"\[\[([^\]]+?)\]\]", link_sub, s)
        s = re.sub(r"'''(.+?)'''", r"<strong>\1</strong>", s)
        s = re.sub(r"''(.+?)''", r"<em>\1</em>", s)
        return s

    def flush_para():
        if para_buf:
            out.append(f"<p>{inline(' '.join(para_buf))}</p>")
            para_buf.clear()

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_para(); close_lists(); continue
        m = re.match(r"^(=+)\s*(.+?)\s*\1\s*$", line)
        if m:
            flush_para(); close_lists()
            level = len(m.group(1))
            txt = m.group(2)
            anchor = slugify(txt)
            tag = f"h{min(level+1, 6)}"
            edit_link = (
                f'<a class="edit-section" data-section="{anchor}" href="{edit_url}">[edit]</a>'
                if edit_url else ""
            )
            out.append(
                f'<{tag} id="{anchor}" class="section-heading">'
                f'<span class="heading-text">{inline(txt)}</span>'
                f'{edit_link}'
                f"</{tag}>"
            )
            continue
        if line.startswith("* "):
            flush_para()
            if not in_ul:
                close_lists(); out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(line[2:].strip())}</li>")
            continue
        if line.startswith("# "):
            flush_para()
            if not in_ol:
                close_lists(); out.append("<ol>"); in_ol = True
            out.append(f"<li>{inline(line[2:].strip())}</li>")
            continue
        para_buf.append(line.strip())

    flush_para(); close_lists()
    return "\n".join(out)


def sync_article_categories(
    article: Article, previous_content: str, new_content: str
) -> None:
    def declared_slugs(content):
        return {
            slugify(name.strip())
            for name in re.findall(
                r"\[\[\s*Category\s*:\s*([^\]|]+)(?:\|[^\]]*)?\]\]",
                content or "",
                flags=re.IGNORECASE,
            )
            if name.strip()
        }

    old_slugs = declared_slugs(previous_content)
    new_slugs = declared_slugs(new_content)
    referenced_slugs = old_slugs | new_slugs
    categories = (
        Category.query
        .filter(Category.wiki_id == article.wiki_id,
                Category.slug.in_(referenced_slugs))
        .all()
        if referenced_slugs else []
    )
    categories_by_slug = {category.slug: category for category in categories}
    existing_ids = {
        row.category_id
        for row in ArticleCategory.query.filter_by(article_id=article.id).all()
    }
    old_ids = {
        categories_by_slug[slug].id
        for slug in old_slugs if slug in categories_by_slug
    }
    new_ids = {
        categories_by_slug[slug].id
        for slug in new_slugs if slug in categories_by_slug
    }
    target_ids = (existing_ids - old_ids) | new_ids
    for category_id in existing_ids - target_ids:
        ArticleCategory.query.filter_by(
            article_id=article.id, category_id=category_id
        ).delete(synchronize_session=False)
    for category_id in target_ids - existing_ids:
        db.session.add(ArticleCategory(
            article_id=article.id,
            category_id=category_id,
        ))


def build_toc(text: str):
    toc = []
    for line in (text or "").splitlines():
        m = re.match(r"^(=+)\s*(.+?)\s*\1\s*$", line)
        if m:
            level = len(m.group(1))
            txt = m.group(2)
            toc.append((level, txt, slugify(txt)))
    return toc


@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))


@app.context_processor
def inject_globals():
    notices = []
    try:
        # Global notices (wiki_id is None) always shown; per-wiki notices added inside wiki views
        notices = Notice.query.filter(Notice.is_active == True,
                                      Notice.wiki_id == None).limit(2).all()
    except Exception:
        notices = []
    return {
        "WIKIS": supported_wikis_query().order_by(Wiki.id).all(),
        "now_year": datetime.utcnow().year,
        "site_name": "Fandom",
        "global_notices": notices,
    }


SUPPORTED_WIKI_SLUGS = ("mcu", "starwars", "genshin")


def supported_wikis_query():
    return Wiki.query.filter(Wiki.slug.in_(SUPPORTED_WIKI_SLUGS))


def published_articles_query():
    return Article.query.filter(func.trim(func.coalesce(Article.content, "")) != "")


# =======================================================================
# ROUTES — hub & auth
# =======================================================================

@app.route("/")
def hub():
    wikis = supported_wikis_query().order_by(Wiki.id).all()
    featured = []
    for w in wikis:
        a = None
        if w.featured_article_slug:
            a = published_articles_query().filter_by(
                wiki_id=w.id, slug=w.featured_article_slug).first()
        if not a:
            a = published_articles_query().filter_by(
                wiki_id=w.id, is_featured=True).first()
        if not a:
            a = published_articles_query().filter_by(wiki_id=w.id).first()
        featured.append((w, a))
    recent_changes = Revision.query.order_by(desc(Revision.timestamp)).limit(8).all()
    trending = published_articles_query().order_by(
        desc(Article.view_count)).limit(8).all()
    return render_template("hub.html", featured=featured,
                           recent_changes=recent_changes, trending=trending)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(or_(
            func.lower(User.email) == identity.lower(),
            func.lower(User.username) == identity.lower(),
        )).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(request.args.get("next") or url_for("hub"))
        flash("Invalid email/username or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not (email and username and password):
            flash("All fields are required.", "error")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("That email is already registered.", "error")
            return render_template("register.html")
        if User.query.filter_by(username=username).first():
            flash("That username is taken.", "error")
            return render_template("register.html")
        u = User(email=email, username=username, groups="autoconfirmed",
                 avatar_color=f"#{random.randint(0, 0xffffff):06x}")
        u.set_password(password)
        db.session.add(u); db.session.commit()
        login_user(u, remember=True)
        flash("Account created — welcome to Fandom!", "success")
        return redirect(url_for("hub"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("hub"))


@app.route("/account")
@login_required
def account():
    watched = (
        db.session.query(Article)
        .join(WatchItem, WatchItem.article_id == Article.id)
        .filter(WatchItem.user_id == current_user.id)
        .all()
    )
    edits = (Revision.query.filter_by(user_id=current_user.id)
             .order_by(desc(Revision.timestamp)).limit(20).all())
    return render_template("account.html", watched=watched, edits=edits)


@app.route("/search")
def search_global():
    q = request.args.get("q", "").strip()
    wiki_slug = request.args.get("wiki", "").strip()
    results = []
    if q:
        terms = [t.lower() for t in re.findall(r"\w+", q) if len(t) > 1]
        base = published_articles_query()
        if wiki_slug:
            w = supported_wikis_query().filter_by(slug=wiki_slug).first()
            if not w:
                base = base.filter(Article.id == -1)
            else:
                base = base.filter(Article.wiki_id == w.id)
        # perf: pre-filter at SQL so we don't materialize all ~1.2k articles
        # (with ~600B content each) per search. Any term must match
        # title / slug / summary / content. Python scoring then ranks.
        if terms:
            any_term = []
            for t in terms:
                like = f'%{t}%'
                any_term.append(or_(
                    Article.title.ilike(like),
                    Article.slug.ilike(like),
                    Article.summary.ilike(like),
                    Article.content.ilike(like),
                ))
            base = base.filter(or_(*any_term))
        cands = base.all()
        scored = []
        for a in cands:
            hay = f"{a.title} {a.summary} {a.content}".lower()
            score = 0
            for t in terms:
                hits = hay.count(t)
                score += hits
                if t in a.title.lower():
                    score += 8
                if t in a.slug.lower():
                    score += 4
            if score > 0:
                scored.append((score, a))
        scored.sort(key=lambda r: -r[0])
        results = [a for _, a in scored[:50]]
    return render_template("search.html", q=q, results=results, wiki_slug=wiki_slug)


# =======================================================================
# ROUTES — per-wiki
# =======================================================================

def get_wiki_or_404(wiki_slug: str) -> Wiki:
    w = supported_wikis_query().filter_by(slug=wiki_slug).first()
    if not w:
        abort(404)
    return w


@app.route("/wiki/<wiki_slug>/")
def wiki_home(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    featured = None
    if w.featured_article_slug:
        featured = published_articles_query().filter_by(
            wiki_id=w.id, slug=w.featured_article_slug).first()
    if not featured:
        featured = published_articles_query().filter_by(
            wiki_id=w.id, is_featured=True).first()
    recent = (Revision.query.join(Article)
              .filter(Article.wiki_id == w.id)
              .order_by(desc(Revision.timestamp)).limit(10).all())
    poll = Poll.query.filter_by(wiki_id=w.id, is_active=True).first()
    poll_results = poll.results() if poll else {}
    popular = (published_articles_query().filter_by(wiki_id=w.id)
               .order_by(desc(Article.view_count)).limit(8).all())
    cats = Category.query.filter_by(wiki_id=w.id, parent_slug="").limit(12).all()
    is_subscribed = False
    if current_user.is_authenticated:
        is_subscribed = WikiSubscription.query.filter_by(
            user_id=current_user.id, wiki_id=w.id).first() is not None
    return render_template("wiki_home.html", wiki=w, featured=featured,
                           recent=recent, poll=poll, poll_results=poll_results,
                           popular=popular, cats=cats,
                           is_subscribed=is_subscribed)


@app.route("/wiki/<wiki_slug>/wiki/<path:title>")
def article_view_alt(wiki_slug, title):
    return article_view(wiki_slug, title)


@app.route("/wiki/<wiki_slug>/<path:title>")
def article_view(wiki_slug, title):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    if slug.startswith("Special:"):
        sp = slug.replace("Special:", "", 1)
        if sp == "RecentChanges":
            return _special_recent_changes(w)
        if sp == "Categories":
            return _special_categories(w)
        if sp == "Search":
            return redirect(url_for("search_global", q=request.args.get("q", ""), wiki=w.slug))
        if sp == "RandomPage":
            a = (published_articles_query().filter_by(
                    wiki_id=w.id, namespace="Main")
                 .order_by(func.random()).first())
            if a:
                return redirect(url_for("article_view", wiki_slug=w.slug, title=a.slug))
            return redirect(url_for("wiki_home", wiki_slug=w.slug))
        if sp.startswith("WhatLinksHere/"):
            tgt = sp[len("WhatLinksHere/"):]
            return _special_what_links_here(w, tgt)
        if sp == "AllPages":
            return _special_all_pages(w)
        if sp == "NewPages":
            return _special_new_pages(w)
        if sp == "ActiveUsers":
            return _special_active_users(w)
        if sp == "CreatePage":
            return create_page(wiki_slug)
        abort(404)
    if slug.startswith("Category:"):
        cat_slug = slug.replace("Category:", "", 1)
        return category_view(wiki_slug, cat_slug)
    if slug.startswith("User:"):
        username = slug.replace("User:", "", 1)
        return redirect(url_for("user_profile", username=username))
    if slug.startswith("Talk:"):
        return redirect(url_for("article_talk", wiki_slug=w.slug,
                                title=slug.replace("Talk:", "", 1)))

    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first()
    if not a or not (a.content or "").strip():
        return render_template("article_missing.html", wiki=w,
                               title=unslug(slug), slug=slug,
                               unavailable=bool(a)), 404
    a.view_count = (a.view_count or 0) + 1
    db.session.commit()
    revision = None
    if "oldid" in request.args:
        revision = db.session.get(Revision, request.args.get("oldid", type=int))
        if revision is None or revision.article_id != a.id:
            abort(404)
    content = revision.content if revision else a.content
    body_html = render_wikitext(
        content, wiki_slug=w.slug,
        edit_url=url_for("article_edit", wiki_slug=w.slug, title=a.slug),
    )
    toc = build_toc(content)
    revs = (Revision.query.filter_by(article_id=a.id)
            .order_by(desc(Revision.timestamp)).limit(3).all())
    is_watching = False
    if current_user.is_authenticated:
        is_watching = WatchItem.query.filter_by(
            user_id=current_user.id, article_id=a.id).first() is not None
    return render_template("article.html", wiki=w, article=a, body_html=body_html,
                           toc=toc, recent_revisions=revs, is_watching=is_watching, revision=revision)


@app.route("/wiki/<wiki_slug>/<path:title>/edit", methods=["GET", "POST"])
@login_required
def article_edit(wiki_slug, title):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first()
    if request.method == "POST":
        new_content = request.form.get("content", "").replace("\r\n", "\n").replace("\r", "\n")
        summary = request.form.get("summary", "").strip()
        minor = bool(request.form.get("minor"))
        if not new_content.strip():
            flash("Content cannot be empty.", "error")
            return render_template("edit.html", wiki=w, article=a,
                                   title=unslug(slug), slug=slug,
                                   content=new_content, summary=summary)
        if "preview" in request.form:
            preview_html = render_wikitext(new_content, wiki_slug=w.slug)
            return render_template("edit.html", wiki=w, article=a,
                                   title=unslug(slug), slug=slug,
                                   content=new_content, summary=summary,
                                   preview_html=preview_html)
        if not a:
            a = Article(wiki_id=w.id, title=unslug(slug), slug=slug,
                        summary=new_content[:200], content=new_content)
            db.session.add(a); db.session.flush()
            prev_bytes = 0
            previous_content = ""
        else:
            previous_content = a.content or ""
            prev_bytes = len((a.content or "").encode("utf-8"))
        a.content = new_content
        if new_content.split("\n\n", 1)[0] != previous_content.split("\n\n", 1)[0]:
            a.summary = new_content.split("\n\n", 1)[0][:200]
        a.updated_at = datetime.utcnow()
        sync_article_categories(a, previous_content, new_content)
        size = len(new_content.encode("utf-8"))
        delta = size - prev_bytes
        author_label = current_user.username if current_user.is_authenticated else \
            (request.remote_addr or "0.0.0.0")
        rev = Revision(article_id=a.id,
                       user_id=current_user.id if current_user.is_authenticated else None,
                       author_label=author_label, summary=summary or "(no summary)",
                       content=new_content, minor=minor,
                       bytes_size=size, bytes_delta=delta)
        db.session.add(rev); db.session.commit()
        flash("Edit saved.", "success")
        return redirect(url_for("article_view", wiki_slug=w.slug, title=slug))
    content = a.content if a else f"== Overview ==\n\nDescribe '''{unslug(slug)}''' here.\n"
    return render_template("edit.html", wiki=w, article=a,
                           title=unslug(slug), slug=slug,
                           content=content, summary="")


@app.route("/wiki/<wiki_slug>/<path:title>/history")
def article_history(wiki_slug, title):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first()
    if not a:
        abort(404)
    revs = (Revision.query.filter_by(article_id=a.id)
            .order_by(desc(Revision.timestamp)).all())
    return render_template("history.html", wiki=w, article=a, revisions=revs)


@app.route("/wiki/<wiki_slug>/<path:title>/diff/<int:old_id>/<int:new_id>")
def article_diff(wiki_slug, title, old_id, new_id):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first()
    if not a:
        abort(404)
    old_r = Revision.query.get(old_id)
    new_r = Revision.query.get(new_id)
    if not (old_r and new_r) or old_r.article_id != a.id or new_r.article_id != a.id:
        abort(404)
    old_lines = (old_r.content or "").splitlines()
    new_lines = (new_r.content or "").splitlines()
    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    rows = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for ln in old_lines[i1:i2]:
                rows.append(("equal", ln, ln))
        elif tag == "replace":
            for k in range(max(i2-i1, j2-j1)):
                l = old_lines[i1+k] if k < i2-i1 else ""
                r = new_lines[j1+k] if k < j2-j1 else ""
                rows.append(("replace", l, r))
        elif tag == "delete":
            for ln in old_lines[i1:i2]:
                rows.append(("delete", ln, ""))
        elif tag == "insert":
            for ln in new_lines[j1:j2]:
                rows.append(("insert", "", ln))
    return render_template("diff.html", wiki=w, article=a, old_r=old_r,
                           new_r=new_r, rows=rows)


@app.route("/wiki/<wiki_slug>/<path:title>/talk", methods=["GET", "POST"])
def article_talk(wiki_slug, title):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first()
    if not a:
        abort(404)
    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Sign in to post on talk pages.", "error")
            return redirect(url_for("login", next=request.path))
        subject = request.form.get("subject", "").strip()
        body = request.form.get("body", "").strip()
        parent_id = request.form.get("parent_id")
        try:
            parent_id = int(parent_id) if parent_id else None
        except ValueError:
            parent_id = None
        if not body:
            flash("Post body required.", "error")
        else:
            post = TalkPost(article_id=a.id, user_id=current_user.id,
                            author_label=current_user.username,
                            subject=subject, body=body, parent_id=parent_id)
            db.session.add(post); db.session.commit()
            flash("Posted.", "success")
        return redirect(url_for("article_talk", wiki_slug=w.slug, title=slug))
    posts = TalkPost.query.filter_by(article_id=a.id).order_by(TalkPost.timestamp).all()
    return render_template("talk.html", wiki=w, article=a, posts=posts)


@app.route("/wiki/<wiki_slug>/<path:title>/revert/<int:rev_id>", methods=["POST"])
@login_required
def article_revert(wiki_slug, title, rev_id):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first()
    rev = Revision.query.get(rev_id)
    if not (a and rev) or rev.article_id != a.id:
        abort(404)
    previous_content = a.content or ""
    a.content = rev.content
    a.summary = (rev.content or "")[:200]
    a.updated_at = datetime.utcnow()
    sync_article_categories(a, previous_content, rev.content)
    size = len((rev.content or "").encode("utf-8"))
    new_rev = Revision(article_id=a.id, user_id=current_user.id,
                       author_label=current_user.username,
                       summary=f"Reverted to revision {rev.id} by {rev.author_label}",
                       content=rev.content, minor=False,
                       bytes_size=size, bytes_delta=0)
    db.session.add(new_rev); db.session.commit()
    flash("Reverted.", "success")
    return redirect(url_for("article_history", wiki_slug=w.slug, title=slug))


@app.route("/wiki/<wiki_slug>/<path:title>/watch", methods=["POST"])
@login_required
def article_watch(wiki_slug, title):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first_or_404()
    existing = WatchItem.query.filter_by(user_id=current_user.id, article_id=a.id).first()
    if existing:
        db.session.delete(existing); db.session.commit()
        flash("No longer watching.", "info")
    else:
        db.session.add(WatchItem(user_id=current_user.id, article_id=a.id))
        db.session.commit()
        flash("Now watching.", "success")
    return redirect(url_for("article_view", wiki_slug=w.slug, title=slug))


@app.route("/wiki/<wiki_slug>/<path:title>/report", methods=["POST"])
def article_report(wiki_slug, title):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first_or_404()
    reason = request.form.get("reason", "vandalism")
    detail = request.form.get("detail", "")
    r = Report(article_id=a.id,
               reporter_id=current_user.id if current_user.is_authenticated else None,
               reason=reason, detail=detail)
    db.session.add(r); db.session.commit()
    flash("Report submitted to wiki staff. Thank you.", "success")
    return redirect(url_for("article_view", wiki_slug=w.slug, title=slug))


# =======================================================================
# Special: pages
# =======================================================================

RECENT_CHANGES_LIMIT = 200


def _special_recent_changes(w):
    namespace = request.args.get("namespace", "")
    hide_minor = bool(request.args.get("hide_minor"))
    hide_bot = bool(request.args.get("hide_bot"))
    q = (Revision.query.join(Article)
         .filter(Article.wiki_id == w.id)
         .order_by(desc(Revision.timestamp)))
    if namespace:
        q = q.filter(Article.namespace == namespace)
    if hide_minor:
        q = q.filter(Revision.minor == False)  # noqa
    if hide_bot:
        q = q.filter(Revision.bot == False)  # noqa
    revs = q.limit(RECENT_CHANGES_LIMIT).all()
    return render_template("recent_changes.html", wiki=w, revisions=revs,
                           limit=RECENT_CHANGES_LIMIT, namespace=namespace,
                           hide_minor=hide_minor, hide_bot=hide_bot)


def _special_categories(w):
    cats = Category.query.filter_by(wiki_id=w.id).order_by(Category.name).all()
    by_parent = {}
    for c in cats:
        by_parent.setdefault(c.parent_slug or "", []).append(c)
    counts = {}
    for c in cats:
        counts[c.id] = ArticleCategory.query.filter_by(category_id=c.id).count()
    return render_template("categories.html", wiki=w, by_parent=by_parent,
                           counts=counts, cats=cats)


def category_view(wiki_slug, cat_slug):
    w = get_wiki_or_404(wiki_slug)
    c = Category.query.filter_by(wiki_id=w.id, slug=slugify(cat_slug)).first_or_404()
    arts = (db.session.query(Article)
            .join(ArticleCategory, ArticleCategory.article_id == Article.id)
            .filter(ArticleCategory.category_id == c.id)
            .order_by(Article.title).all())
    subs = Category.query.filter_by(wiki_id=w.id, parent_slug=c.slug).all()
    return render_template("category.html", wiki=w, category=c, articles=arts, subs=subs)


def _special_what_links_here(w, target: str):
    slug = slugify(target)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first()
    target_title = unslug(slug)
    pattern = f"[[{target_title}"
    candidates = (Article.query.filter_by(wiki_id=w.id)
                  .filter(Article.content.like(f"%{pattern}%")).all())
    return render_template("what_links_here.html", wiki=w,
                           target_title=target_title, target_slug=slug,
                           article=a, links_from=candidates)


def _special_all_pages(w):
    arts = (Article.query.filter_by(wiki_id=w.id, namespace="Main")
            .order_by(Article.title).all())
    return render_template("all_pages.html", wiki=w, articles=arts)


def _special_new_pages(w):
    arts = (Article.query.filter_by(wiki_id=w.id)
            .order_by(desc(Article.created_at)).limit(50).all())
    return render_template("new_pages.html", wiki=w, articles=arts)


def _special_active_users(w):
    rows = (db.session.query(User, func.count(Revision.id))
            .join(Revision, Revision.user_id == User.id)
            .join(Article, Article.id == Revision.article_id)
            .filter(Article.wiki_id == w.id)
            .group_by(User.id)
            .order_by(desc(func.count(Revision.id)))
            .limit(40).all())
    return render_template("active_users.html", wiki=w, rows=rows)


@app.route("/wiki/<wiki_slug>/create", methods=["GET", "POST"])
@login_required
def create_page(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title required.", "error")
            return render_template("create_page.html", wiki=w)
        slug = slugify(title)
        if Article.query.filter_by(wiki_id=w.id, slug=slug).first():
            flash("That page already exists.", "error")
            return redirect(url_for("article_view", wiki_slug=w.slug, title=slug))
        return redirect(url_for("article_edit", wiki_slug=w.slug, title=slug))
    return render_template("create_page.html", wiki=w)


@app.route("/wiki/<wiki_slug>/poll/<int:poll_id>/vote", methods=["POST"])
def poll_vote(wiki_slug, poll_id):
    w = get_wiki_or_404(wiki_slug)
    p = Poll.query.get_or_404(poll_id)
    if p.wiki_id != w.id:
        abort(404)
    try:
        choice = int(request.form.get("choice", "-1"))
    except ValueError:
        choice = -1
    if 0 <= choice < len(p.options):
        v = PollVote(poll_id=p.id,
                     user_id=current_user.id if current_user.is_authenticated else None,
                     choice_idx=choice)
        db.session.add(v); db.session.commit()
        flash(f"Voted for: {p.options[choice]}", "success")
    return redirect(url_for("wiki_home", wiki_slug=w.slug))


@app.route("/user/<username>")
def user_profile(username):
    u = User.query.filter_by(username=username).first_or_404()
    edits = (Revision.query.filter_by(user_id=u.id)
             .order_by(desc(Revision.timestamp)).limit(50).all())
    return render_template("user.html", user=u, edits=edits)


@app.route("/wikis")
def wiki_directory():
    return render_template("wiki_directory.html")


@app.route("/community")
def community_portal():
    return render_template("community_portal.html")


# =======================================================================
# Hub-level extras
# =======================================================================

VERTICAL_HUBS = {
    "movies": dict(label="Movies", tagline="Wikis dedicated to films",
                   slugs=["mcu", "starwars"]),
    "games":  dict(label="Games",  tagline="Game encyclopedias",
                   slugs=["genshin"]),
    "tv":     dict(label="TV",     tagline="Television wikis",
                   slugs=["mcu", "starwars"]),
    "anime":  dict(label="Anime & Manga", tagline="Anime universes",
                   slugs=["genshin"]),
    "books":  dict(label="Books",  tagline="Book and comic wikis",
                   slugs=["mcu", "starwars"]),
}

@app.route("/explore")
def explore():
    wikis = supported_wikis_query().order_by(Wiki.id).all()
    return render_template("explore.html", wikis=wikis, hubs=VERTICAL_HUBS)


@app.route("/<hub_slug>")
def vertical_hub(hub_slug):
    if hub_slug not in VERTICAL_HUBS:
        abort(404)
    spec = VERTICAL_HUBS[hub_slug]
    wikis = Wiki.query.filter(Wiki.slug.in_(spec["slugs"])).all()
    trending = (published_articles_query()
                .filter(Article.wiki_id.in_([w.id for w in wikis]))
                .order_by(desc(Article.view_count)).limit(12).all())
    return render_template("vertical_hub.html", spec=spec, hub_slug=hub_slug,
                           wikis=wikis, trending=trending)


@app.route("/start-a-wiki", methods=["GET", "POST"])
def start_a_wiki():
    if request.method == "POST":
        flash("Wiki request submitted! Our team will review and contact you within 48h.", "success")
        return redirect(url_for("hub"))
    return render_template("start_a_wiki.html")


# =======================================================================
# File: namespace
# =======================================================================

@app.route("/wiki/<wiki_slug>/Special:ListFiles")
def special_list_files(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    q = request.args.get("q", "").strip()
    base = FileAsset.query.filter_by(wiki_id=w.id)
    if q:
        like = f"%{q.lower()}%"
        base = base.filter(or_(FileAsset.filename.ilike(like),
                               FileAsset.display_name.ilike(like)))
    files = base.order_by(desc(FileAsset.uploaded_at)).limit(200).all()
    return render_template("list_files.html", wiki=w, files=files, q=q)


@app.route("/wiki/<wiki_slug>/File:<path:filename>")
def file_view(wiki_slug, filename):
    w = get_wiki_or_404(wiki_slug)
    f = FileAsset.query.filter_by(wiki_id=w.id, filename=filename).first()
    if not f:
        return render_template("file_missing.html", wiki=w, filename=filename), 404
    # File usage: articles whose `image` column references this filename
    usage = Article.query.filter_by(wiki_id=w.id, image=filename).all()
    global_usage = (Article.query.filter(Article.image == filename,
                                         Article.wiki_id != w.id).all())
    return render_template("file_view.html", wiki=w, file=f,
                           usage=usage, global_usage=global_usage)


@app.route("/wiki/<wiki_slug>/Special:Upload", methods=["GET", "POST"])
@login_required
def special_upload(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    if request.method == "POST":
        fn = request.form.get("filename", "").strip()
        desc = request.form.get("description", "").strip()
        lic = request.form.get("license", "Fair use").strip()
        if not fn:
            flash("Filename required.", "error")
        elif FileAsset.query.filter_by(wiki_id=w.id, filename=fn).first():
            flash("That filename already exists on this wiki.", "error")
        else:
            f = FileAsset(wiki_id=w.id, filename=fn,
                          display_name=fn.replace("_", " ").rsplit(".", 1)[0],
                          description=desc, license=lic,
                          uploader_id=current_user.id,
                          uploader_label=current_user.username,
                          bytes_size=request.form.get("bytes_size", 65536, type=int),
                          width=800, height=600)
            db.session.add(f); db.session.commit()
            flash(f"File uploaded: {fn}", "success")
            return redirect(url_for("file_view", wiki_slug=w.slug, filename=fn))
    return render_template("upload.html", wiki=w)


# =======================================================================
# Forum (Discussions)
# =======================================================================

@app.route("/wiki/<wiki_slug>/Forum")
def forum_index(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    cat = request.args.get("cat", "").strip()
    base = ForumThread.query.filter_by(wiki_id=w.id)
    if cat:
        base = base.filter_by(category=cat)
    threads = base.order_by(desc(ForumThread.is_pinned),
                            desc(ForumThread.updated_at)).limit(50).all()
    cats = sorted({t.category for t in ForumThread.query.filter_by(wiki_id=w.id).all()})
    return render_template("forum_index.html", wiki=w, threads=threads,
                           cats=cats, active_cat=cat)


@app.route("/wiki/<wiki_slug>/Forum/Thread/<int:thread_id>", methods=["GET", "POST"])
def forum_thread(wiki_slug, thread_id):
    w = get_wiki_or_404(wiki_slug)
    t = ForumThread.query.get_or_404(thread_id)
    if t.wiki_id != w.id:
        abort(404)
    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Sign in to post.", "error")
            return redirect(url_for("login", next=request.path))
        if t.is_locked:
            flash("Thread is locked.", "error")
            return redirect(url_for("forum_thread", wiki_slug=w.slug, thread_id=t.id))
        body = request.form.get("body", "").strip()
        if not body:
            flash("Reply body required.", "error")
        else:
            p = ForumPost(thread_id=t.id, user_id=current_user.id,
                          author_label=current_user.username, body=body)
            db.session.add(p)
            t.updated_at = datetime.utcnow()
            db.session.commit()
            flash("Reply posted.", "success")
        return redirect(url_for("forum_thread", wiki_slug=w.slug, thread_id=t.id))
    t.view_count = (t.view_count or 0) + 1
    db.session.commit()
    posts = ForumPost.query.filter_by(thread_id=t.id).order_by(ForumPost.timestamp).all()
    return render_template("forum_thread.html", wiki=w, thread=t, posts=posts)


@app.route("/wiki/<wiki_slug>/Forum/New", methods=["GET", "POST"])
@login_required
def forum_new(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        cat = request.form.get("category", "General").strip() or "General"
        if not (title and body):
            flash("Title and body required.", "error")
        else:
            t = ForumThread(wiki_id=w.id, title=title, slug=slugify(title),
                            body=body, category=cat,
                            author_id=current_user.id,
                            author_label=current_user.username)
            db.session.add(t); db.session.flush()
            # Author's body becomes first post
            db.session.add(ForumPost(thread_id=t.id, user_id=current_user.id,
                                     author_label=current_user.username, body=body))
            db.session.commit()
            flash("Thread created.", "success")
            return redirect(url_for("forum_thread", wiki_slug=w.slug, thread_id=t.id))
    return render_template("forum_new.html", wiki=w)


# =======================================================================
# Article comments
# =======================================================================

@app.route("/wiki/<wiki_slug>/<path:title>/comments", methods=["GET", "POST"])
def article_comments(wiki_slug, title):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first_or_404()
    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Sign in to comment.", "error")
            return redirect(url_for("login", next=request.path))
        body = request.form.get("body", "").strip()
        parent_id = request.form.get("parent_id")
        try:
            parent_id = int(parent_id) if parent_id else None
        except ValueError:
            parent_id = None
        if not body:
            flash("Comment body required.", "error")
        else:
            c = ArticleComment(article_id=a.id, user_id=current_user.id,
                               author_label=current_user.username,
                               parent_id=parent_id, body=body)
            db.session.add(c); db.session.commit()
            flash("Comment posted.", "success")
        return redirect(url_for("article_comments", wiki_slug=w.slug, title=slug))
    comments = (ArticleComment.query.filter_by(article_id=a.id)
                .order_by(ArticleComment.timestamp).all())
    return render_template("comments.html", wiki=w, article=a, comments=comments)


@app.route("/wiki/<wiki_slug>/comment/<int:cid>/like", methods=["POST"])
@login_required
def comment_like(wiki_slug, cid):
    c = ArticleComment.query.get_or_404(cid)
    existing = CommentLike.query.filter_by(user_id=current_user.id, comment_id=cid).first()
    if existing:
        db.session.delete(existing)
        c.likes = max(0, c.likes - 1)
        flash("Like removed.", "info")
    else:
        db.session.add(CommentLike(user_id=current_user.id, comment_id=cid))
        c.likes = (c.likes or 0) + 1
        flash("Liked!", "success")
    db.session.commit()
    a = Article.query.get(c.article_id)
    return redirect(url_for("article_comments", wiki_slug=wiki_slug, title=a.slug))


# =======================================================================
# Watchlist, follow, subscribe
# =======================================================================

@app.route("/wiki/<wiki_slug>/Special:Watchlist")
@login_required
def special_watchlist(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    items = (db.session.query(Article)
             .join(WatchItem, WatchItem.article_id == Article.id)
             .filter(WatchItem.user_id == current_user.id,
                     Article.wiki_id == w.id)
             .all())
    article_ids = [a.id for a in items]
    revs = []
    if article_ids:
        revs = (Revision.query.filter(Revision.article_id.in_(article_ids))
                .order_by(desc(Revision.timestamp)).limit(50).all())
    return render_template("watchlist.html", wiki=w, items=items, revisions=revs)


@app.route("/user/<username>/follow", methods=["POST"])
@login_required
def user_follow(username):
    u = User.query.filter_by(username=username).first_or_404()
    if u.id == current_user.id:
        flash("You cannot follow yourself.", "error")
    else:
        existing = UserFollow.query.filter_by(
            follower_id=current_user.id, followee_id=u.id).first()
        if existing:
            db.session.delete(existing)
            flash(f"Unfollowed {u.username}.", "info")
        else:
            db.session.add(UserFollow(follower_id=current_user.id, followee_id=u.id))
            flash(f"Now following {u.username}.", "success")
        db.session.commit()
    return redirect(url_for("user_profile", username=username))


@app.route("/wiki/<wiki_slug>/subscribe", methods=["POST"])
@login_required
def wiki_subscribe(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    existing = WikiSubscription.query.filter_by(
        user_id=current_user.id, wiki_id=w.id).first()
    if existing:
        db.session.delete(existing)
        flash(f"Unsubscribed from {w.name}.", "info")
    else:
        db.session.add(WikiSubscription(user_id=current_user.id, wiki_id=w.id))
        flash(f"Subscribed to {w.name} notifications.", "success")
    db.session.commit()
    return redirect(url_for("wiki_home", wiki_slug=w.slug))


# =======================================================================
# Special analytics pages
# =======================================================================

@app.route("/wiki/<wiki_slug>/Special:Statistics")
def special_statistics(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    stats = dict(
        articles=Article.query.filter_by(wiki_id=w.id, namespace="Main").count(),
        pages=Article.query.filter_by(wiki_id=w.id).count(),
        revisions=Revision.query.join(Article).filter(Article.wiki_id == w.id).count(),
        files=FileAsset.query.filter_by(wiki_id=w.id).count(),
        editors=db.session.query(func.count(func.distinct(Revision.user_id)))
                .join(Article).filter(Article.wiki_id == w.id,
                                      Revision.user_id != None).scalar() or 0,
        categories=Category.query.filter_by(wiki_id=w.id).count(),
        talk_posts=TalkPost.query.join(Article).filter(Article.wiki_id == w.id).count(),
        threads=ForumThread.query.filter_by(wiki_id=w.id).count(),
        forum_posts=ForumPost.query.join(ForumThread).filter(
            ForumThread.wiki_id == w.id).count(),
        comments=ArticleComment.query.join(Article).filter(
            Article.wiki_id == w.id).count(),
    )
    return render_template("statistics.html", wiki=w, stats=stats)


@app.route("/wiki/<wiki_slug>/Special:LongPages")
def special_long_pages(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    arts = Article.query.filter_by(wiki_id=w.id).all()
    arts.sort(key=lambda a: len((a.content or "").encode("utf-8")), reverse=True)
    return render_template("long_pages.html", wiki=w, articles=arts[:50])


@app.route("/wiki/<wiki_slug>/Special:ShortPages")
def special_short_pages(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    arts = Article.query.filter_by(wiki_id=w.id).all()
    arts.sort(key=lambda a: len((a.content or "").encode("utf-8")))
    return render_template("short_pages.html", wiki=w, articles=arts[:50])


@app.route("/wiki/<wiki_slug>/Special:MostRevisions")
def special_most_revisions(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    rows = (db.session.query(Article, func.count(Revision.id))
            .join(Revision, Revision.article_id == Article.id)
            .filter(Article.wiki_id == w.id)
            .group_by(Article.id)
            .order_by(desc(func.count(Revision.id)))
            .limit(50).all())
    return render_template("most_revisions.html", wiki=w, rows=rows)


@app.route("/wiki/<wiki_slug>/Special:OrphanedPages")
def special_orphaned(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    arts = Article.query.filter_by(wiki_id=w.id).all()
    # An article is orphaned if no other article links to it via [[Title]]
    orphans = []
    for a in arts:
        needle = f"[[{a.title}"
        linked = any(needle in (b.content or "")
                     for b in arts if b.id != a.id)
        if not linked:
            orphans.append(a)
    return render_template("orphaned.html", wiki=w, articles=orphans[:80])


@app.route("/wiki/<wiki_slug>/Special:WantedPages")
def special_wanted(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    arts = Article.query.filter_by(wiki_id=w.id).all()
    seen = {a.slug for a in arts}
    wanted = {}  # title -> count of links
    pat = re.compile(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]")
    for a in arts:
        for m in pat.finditer(a.content or ""):
            tgt = m.group(1).strip()
            if slugify(tgt) not in seen and ":" not in tgt:
                wanted[tgt] = wanted.get(tgt, 0) + 1
    rows = sorted(wanted.items(), key=lambda x: -x[1])[:80]
    return render_template("wanted.html", wiki=w, rows=rows)


@app.route("/wiki/<wiki_slug>/Special:UserContributions/<username>")
def special_user_contribs(wiki_slug, username):
    w = get_wiki_or_404(wiki_slug)
    u = User.query.filter_by(username=username).first_or_404()
    ns = request.args.get("namespace", "")
    q = (Revision.query.join(Article)
         .filter(Article.wiki_id == w.id, Revision.user_id == u.id))
    if ns:
        q = q.filter(Article.namespace == ns)
    revs = q.order_by(desc(Revision.timestamp)).limit(200).all()
    return render_template("user_contribs.html", wiki=w, user=u,
                           revisions=revs, namespace=ns)


@app.route("/wiki/<wiki_slug>/Special:UserRights/<username>")
def special_user_rights(wiki_slug, username):
    w = get_wiki_or_404(wiki_slug)
    u = User.query.filter_by(username=username).first_or_404()
    return render_template("user_rights.html", wiki=w, user=u)


@app.route("/wiki/<wiki_slug>/Special:TopEditors")
def special_top_editors(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    span = request.args.get("span", "all")
    cutoff = None
    if span == "week":
        cutoff = datetime.utcnow() - timedelta(days=7)
    elif span == "month":
        cutoff = datetime.utcnow() - timedelta(days=30)
    q = (db.session.query(User, func.count(Revision.id))
         .join(Revision, Revision.user_id == User.id)
         .join(Article, Article.id == Revision.article_id)
         .filter(Article.wiki_id == w.id))
    if cutoff:
        q = q.filter(Revision.timestamp >= cutoff)
    rows = q.group_by(User.id).order_by(desc(func.count(Revision.id))).limit(50).all()
    return render_template("top_editors.html", wiki=w, rows=rows, span=span)


@app.route("/wiki/<wiki_slug>/Special:SpecialPages")
def special_pages_index(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    return render_template("special_pages.html", wiki=w)


@app.route("/wiki/<wiki_slug>/Special:WikiActivity")
def special_wiki_activity(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    revs = (Revision.query.join(Article).filter(Article.wiki_id == w.id)
            .order_by(desc(Revision.timestamp)).limit(40).all())
    threads = (ForumThread.query.filter_by(wiki_id=w.id)
               .order_by(desc(ForumThread.updated_at)).limit(10).all())
    comments = (ArticleComment.query.join(Article)
                .filter(Article.wiki_id == w.id)
                .order_by(desc(ArticleComment.timestamp)).limit(10).all())
    return render_template("wiki_activity.html", wiki=w, revs=revs,
                           threads=threads, comments=comments)


@app.route("/wiki/<wiki_slug>/Special:Polls")
def special_polls(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    polls = Poll.query.filter_by(wiki_id=w.id).all()
    return render_template("polls_index.html", wiki=w, polls=polls)


@app.route("/wiki/<wiki_slug>/Poll/<int:poll_id>")
def poll_view(wiki_slug, poll_id):
    w = get_wiki_or_404(wiki_slug)
    p = Poll.query.get_or_404(poll_id)
    if p.wiki_id != w.id:
        abort(404)
    return render_template("poll_view.html", wiki=w, poll=p,
                           results=p.results())


@app.route("/wiki/<wiki_slug>/Help:<path:topic>")
def help_page(wiki_slug, topic):
    w = get_wiki_or_404(wiki_slug)
    topic = slugify(topic)
    return render_template("help.html", wiki=w, topic=topic)


@app.route("/wiki/<wiki_slug>/Help")
def help_index(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    return render_template("help_index.html", wiki=w)


# =======================================================================
# Admin action POSTs (read-only mockups + a few mutators)
# =======================================================================

@app.route("/wiki/<wiki_slug>/<path:title>/move", methods=["GET", "POST"])
@login_required
def article_move(wiki_slug, title):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first_or_404()
    if request.method == "POST":
        new_title = request.form.get("new_title", "").strip()
        reason = request.form.get("reason", "").strip()
        if not new_title:
            flash("New title required.", "error")
        else:
            new_slug = slugify(new_title)
            if Article.query.filter_by(wiki_id=w.id, slug=new_slug).first():
                flash("Target title already exists.", "error")
            else:
                old_title = a.title
                a.title = new_title
                a.slug = new_slug
                a.updated_at = datetime.utcnow()
                # Log move as a revision
                rev = Revision(article_id=a.id, user_id=current_user.id,
                               author_label=current_user.username,
                               summary=f"Moved from [[{old_title}]]. Reason: {reason or '(none)'}",
                               content=a.content,
                               bytes_size=len((a.content or "").encode("utf-8")),
                               bytes_delta=0)
                db.session.add(rev); db.session.commit()
                flash(f"Page moved to {new_title}.", "success")
                return redirect(url_for("article_view", wiki_slug=w.slug,
                                        title=new_slug))
    return render_template("move_page.html", wiki=w, article=a)


@app.route("/wiki/<wiki_slug>/<path:title>/protect", methods=["GET", "POST"])
@login_required
def article_protect(wiki_slug, title):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first_or_404()
    p = Protection.query.filter_by(article_id=a.id).first()
    if request.method == "POST":
        level = request.form.get("level", "autoconfirmed")
        reason = request.form.get("reason", "")
        if level == "none":
            if p:
                db.session.delete(p)
                db.session.commit()
            flash(f"Page {a.title} unprotected.", "success")
        else:
            if p:
                p.level = level
                p.reason = reason
                p.set_by_id = current_user.id
                p.set_at = datetime.utcnow()
            else:
                p = Protection(article_id=a.id, level=level,
                               reason=reason, set_by_id=current_user.id)
                db.session.add(p)
            db.session.commit()
            flash(f"{a.title} now protected at {level}.", "success")
        return redirect(url_for("article_view", wiki_slug=w.slug, title=a.slug))
    return render_template("protect_page.html", wiki=w, article=a, prot=p)


@app.route("/wiki/<wiki_slug>/<path:title>/delete", methods=["GET", "POST"])
@login_required
def article_delete(wiki_slug, title):
    w = get_wiki_or_404(wiki_slug)
    slug = slugify(title)
    a = Article.query.filter_by(wiki_id=w.id, slug=slug).first_or_404()
    if request.method == "POST":
        reason = request.form.get("reason", "")
        # Mockup: record a delete revision but keep the row
        rev = Revision(article_id=a.id, user_id=current_user.id,
                       author_label=current_user.username,
                       summary=f"[DELETE REQUEST] {reason}",
                       content=a.content, minor=False,
                       bytes_size=len((a.content or "").encode("utf-8")),
                       bytes_delta=0)
        db.session.add(rev); db.session.commit()
        flash("Delete request filed. Awaiting sysop review.", "success")
        return redirect(url_for("article_view", wiki_slug=w.slug, title=a.slug))
    return render_template("delete_page.html", wiki=w, article=a)


@app.route("/wiki/<wiki_slug>/Special:Block", methods=["GET", "POST"])
@login_required
def special_block(wiki_slug):
    w = get_wiki_or_404(wiki_slug)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        reason = request.form.get("reason", "")
        duration = request.form.get("duration", "indefinite")
        u = User.query.filter_by(username=username).first()
        if not u:
            flash("User not found.", "error")
        else:
            existing = UserBlock.query.filter_by(user_id=u.id, is_active=True).first()
            if existing:
                existing.is_active = False
                db.session.commit()
                flash(f"Unblocked {username}.", "info")
            else:
                db.session.add(UserBlock(user_id=u.id, blocker_id=current_user.id,
                                         reason=reason, duration=duration))
                db.session.commit()
                flash(f"Blocked {username} ({duration}).", "success")
        return redirect(url_for("special_block", wiki_slug=w.slug))
    blocks = UserBlock.query.filter_by(is_active=True).all()
    return render_template("block.html", wiki=w, blocks=blocks)


# Namespace browse views
NAMESPACES = ["User", "File", "Template", "Help", "Category", "MediaWiki", "Forum"]

@app.route("/wiki/<wiki_slug>/Namespace/<ns>")
def namespace_index(wiki_slug, ns):
    w = get_wiki_or_404(wiki_slug)
    if ns not in NAMESPACES:
        abort(404)
    if ns == "User":
        items = User.query.order_by(User.username).all()
    elif ns == "File":
        items = FileAsset.query.filter_by(wiki_id=w.id).order_by(FileAsset.filename).all()
    elif ns == "Category":
        items = Category.query.filter_by(wiki_id=w.id).order_by(Category.name).all()
    else:
        items = Article.query.filter_by(wiki_id=w.id, namespace=ns).order_by(Article.title).all()
    return render_template("namespace.html", wiki=w, ns=ns, items=items)


@app.errorhandler(404)
def _not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def _server_error(e):
    return render_template("500.html"), 500


@app.route("/_health")
def health():
    try:
        n = Article.query.count()
        return {"ok": True, "site": "fandom", "articles": n}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


# =======================================================================
# Bootstrap
# =======================================================================

# Make `from app import ...` resolve to *this* module regardless of whether
# app.py is run via `python app.py` (this module is __main__) or imported as
# `app`. Without this, seed_data.py's `from app import db, ...` gets a SECOND
# copy of this module with a different SQLAlchemy instance, and seeding fails
# with "current Flask app is not registered with this 'SQLAlchemy' instance".
import sys as _sys
_sys.modules.setdefault("app", _sys.modules[__name__])

from seed_data import seed_database, seed_benchmark_users  # noqa: E402
from seed_phase2 import seed_phase2_all  # noqa: E402

with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()
    seed_phase2_all()
    # perf: indexes for hot list/sort columns. Hub uses view_count DESC;
    # article lookups go via (wiki_id, slug). CREATE INDEX IF NOT EXISTS so
    # byte-id reseeds stay clean.
    from sqlalchemy import text as _text
    _conn = db.engine.connect()
    _conn.execute(_text("CREATE INDEX IF NOT EXISTS ix_articles_view_count "
                        "ON articles(view_count DESC)"))
    _conn.execute(_text("CREATE INDEX IF NOT EXISTS ix_articles_wiki_slug "
                        "ON articles(wiki_id, slug)"))
    _conn.execute(_text("CREATE INDEX IF NOT EXISTS ix_articles_wiki_view "
                        "ON articles(wiki_id, view_count DESC)"))
    _conn.commit()
    _conn.close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


# --- perf: long-term cache for /static/ assets (added 2026-05-27) ---
@app.after_request
def _add_static_cache_headers(resp):
    try:
        if request.path.startswith('/static/'):
            resp.headers['Cache-Control'] = 'public, max-age=86400, immutable'
    except Exception:
        pass
    return resp
# --- end perf ---
