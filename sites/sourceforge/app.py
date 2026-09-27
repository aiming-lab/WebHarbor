"""SourceForge (sourceforge.net) mirror — Flask application.

Mirrors https://sourceforge.net/ as served on 2026-09-26: the open source
software directory (browse by category / OS / license / language / status
facets with relevance-scored search and five sort orders), project summary
pages (masthead with ratings, badges, screenshots, activity, additional
details, recommended projects), the file browser with per-folder and
per-file download stats, download statistics pages (timeline / OS / map),
the review system (histogram, dimensional ratings, star filters, review
submission for logged-in users), the Allura tools (bugs / feature requests /
support requests trackers with ticket search, wiki, discussion forums with
threads, news, activity feeds), user profiles, the Top Downloaded Projects
tables, the business software directory (/software/), the about / leadership
pages, auth (register / login) and the account domain (my projects /
bookmarks / profile).

All runtime data lives in instance/sourceforge.db (see seed_data.py); heavy
imagery lives under static/images/ (HF-managed, see asset_inventory.json).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_file, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "SOURCEFORGE_DB_PATH", f"sqlite:///{BASE_DIR}/instance/sourceforge.db")
app.config["SECRET_KEY"] = "webharbor-sourceforge-dev-key"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "auth_login"
login_manager.login_message = ""

# The mirror pins "now" to the snapshot date so relative statements
# ("this week", "2 hours ago") stay deterministic.
MIRROR_NOW = datetime(2026, 9, 26, 12, 0)

PER_PAGE = 25


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    display_name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    country = db.Column(db.String(2))
    joined = db.Column(db.String(19))
    is_benchmark = db.Column(db.Boolean, default=False)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    shortname = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text)
    short_description = db.Column(db.Text)
    creation_date = db.Column(db.String(10))
    updated = db.Column(db.String(10))
    updated_display = db.Column(db.String(40))
    downloads_week = db.Column(db.Integer, default=0)
    downloads_total = db.Column(db.BigInteger, default=0)
    external_homepage = db.Column(db.String(255))
    video_url = db.Column(db.String(255))
    status = db.Column(db.String(32))
    is_mirror = db.Column(db.Boolean, default=False)
    has_icon = db.Column(db.Boolean, default=False)
    badge = db.Column(db.Boolean, default=False)
    review_count = db.Column(db.Integer, default=0)
    rating_avg = db.Column(db.Float, default=0.0)
    rating_ease = db.Column(db.Float)
    rating_features = db.Column(db.Float)
    rating_design = db.Column(db.Float)
    rating_support = db.Column(db.Float)
    stars_5 = db.Column(db.Integer, default=0)
    stars_4 = db.Column(db.Integer, default=0)
    stars_3 = db.Column(db.Integer, default=0)
    stars_2 = db.Column(db.Integer, default=0)
    stars_1 = db.Column(db.Integer, default=0)
    is_potm = db.Column(db.Boolean, default=False)  # staff/community choice
    potm_label = db.Column(db.String(32))
    is_popular = db.Column(db.Boolean, default=False)  # homepage popular projects
    tools_json = db.Column(db.Text)  # JSON list of tool mount points
    developers_json = db.Column(db.Text)  # JSON [[username, display_name]]
    labels_json = db.Column(db.Text)

    facets = db.relationship("ProjectFacet", back_populates="project",
                             lazy="joined", cascade="all, delete-orphan")
    screenshots = db.relationship("Screenshot", back_populates="project",
                                   cascade="all, delete-orphan")
    files = db.relationship("ProjectFile", back_populates="project",
                            cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="project",
                               cascade="all, delete-orphan")

    @property
    def tools(self):
        return json.loads(self.tools_json or "[]")

    @property
    def developers(self):
        return json.loads(self.developers_json or "[]")

    @property
    def facet(self):
        out = {}
        for f in self.facets:
            out.setdefault(f.kind, []).append(f.value)
        return out

    @property
    def facet_labels(self):
        out = {}
        for f in self.facets:
            out.setdefault(f.kind, {})[f.value] = f.label
        return out

    def icon_url(self, w=120):
        if self.has_icon:
            return url_for("static", filename=f"images/icons/{self.shortname}.png")
        return None

    def star_steps(self):
        avg = self.rating_avg or 0
        steps = []
        for i in range(1, 6):
            if avg >= i:
                steps.append("yellow")
            elif avg >= i - 0.5:
                steps.append("half")
            else:
                steps.append("empty")
        return steps


class ProjectFacet(db.Model):
    __tablename__ = "project_facets"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"),
                           nullable=False)
    kind = db.Column(db.String(20), nullable=False)  # topic/os/license/language/translation/environment/devstatus/audience
    value = db.Column(db.String(64), nullable=False)  # slug
    label = db.Column(db.String(128), nullable=False)  # display name

    project = db.relationship("Project", back_populates="facets")


class Screenshot(db.Model):
    __tablename__ = "screenshots"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(255))
    ordinal = db.Column(db.Integer, default=0)

    project = db.relationship("Project", back_populates="screenshots")


class ProjectFile(db.Model):
    __tablename__ = "project_files"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    path = db.Column(db.String(512), nullable=False)  # e.g. "7-Zip/26.03/7z2603-x64.exe"
    is_default = db.Column(db.Boolean, default=False)
    is_folder = db.Column(db.Boolean, default=False)
    size_bytes = db.Column(db.BigInteger)
    size_display = db.Column(db.String(20))
    modified = db.Column(db.String(19))
    downloads_week = db.Column(db.Integer, default=0)
    downloads_total = db.Column(db.BigInteger, default=0)

    project = db.relationship("Project", back_populates="files")

    @property
    def name(self):
        return self.path.rstrip("/").rsplit("/", 1)[-1]

    @property
    def parent(self):
        parts = self.path.rstrip("/").split("/")
        return "/".join(parts[:-1])

    @property
    def depth(self):
        return self.path.rstrip("/").count("/")


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    author_name = db.Column(db.String(64), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text)
    created = db.Column(db.String(10))
    helpful_count = db.Column(db.Integer, default=0)

    project = db.relationship("Project", back_populates="reviews")


class Ticket(db.Model):
    __tablename__ = "tickets"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    tracker = db.Column(db.String(32), nullable=False)  # bugs/feature-requests/support-requests/patches
    ticket_num = db.Column(db.Integer, nullable=False)
    summary = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(32), default="open")
    owner = db.Column(db.String(64))
    creator = db.Column(db.String(64))
    priority = db.Column(db.Integer)
    labels_json = db.Column(db.Text)
    created = db.Column(db.String(10))
    updated = db.Column(db.String(10))

    posts = db.relationship("TicketPost", back_populates="ticket",
                            cascade="all, delete-orphan")


class TicketPost(db.Model):
    __tablename__ = "ticket_posts"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    author = db.Column(db.String(64))
    date = db.Column(db.String(10))
    text = db.Column(db.Text)

    ticket = db.relationship("Ticket", back_populates="posts")


class Forum(db.Model):
    __tablename__ = "forums"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    shortname = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    num_topics = db.Column(db.Integer, default=0)

    threads = db.relationship("ForumThread", back_populates="forum",
                              cascade="all, delete-orphan")


class ForumThread(db.Model):
    __tablename__ = "forum_threads"
    id = db.Column(db.Integer, primary_key=True)
    forum_id = db.Column(db.Integer, db.ForeignKey("forums.id"), nullable=False)
    thread_id = db.Column(db.String(16), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    creator = db.Column(db.String(64))
    created = db.Column(db.String(40))
    posts = db.Column(db.Integer, default=1)
    views = db.Column(db.Integer, default=0)
    last_author = db.Column(db.String(64))
    last_date = db.Column(db.String(40))

    forum = db.relationship("Forum", back_populates="threads")
    messages = db.relationship("ThreadPost", back_populates="thread",
                               cascade="all, delete-orphan")

    def visible_posts(self):
        """Posts served on the thread page. Threads whose discussion pages
        were not archived render their opening post (subject + creator),
        which is how a minimal Allura thread reads."""
        posts = list(self.messages)
        if not posts:
            posts = [_SyntheticPost(self)]
        return posts


class _SyntheticPost:
    """Stand-in opening post derived from thread metadata (no fabricated
    body text: the subject line is the post)."""

    def __init__(self, thread):
        self.author = thread.creator
        self.date = thread.created
        self.text = thread.subject
        self.synthetic = True


class ThreadPost(db.Model):
    __tablename__ = "thread_posts"
    id = db.Column(db.Integer, primary_key=True)
    thread_pk = db.Column(db.Integer, db.ForeignKey("forum_threads.id"), nullable=False)
    author = db.Column(db.String(64))
    date = db.Column(db.String(10))
    text = db.Column(db.Text)

    thread = db.relationship("ForumThread", back_populates="messages")


class WikiPage(db.Model):
    __tablename__ = "wiki_pages"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    body = db.Column(db.Text)
    mod_date = db.Column(db.String(19))


class NewsPost(db.Model):
    __tablename__ = "news_posts"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text)
    author = db.Column(db.String(64))
    date = db.Column(db.String(10))


class ActivityEvent(db.Model):
    __tablename__ = "activity_events"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    actor = db.Column(db.String(64))
    actor_is_project = db.Column(db.Boolean, default=False)
    verb = db.Column(db.String(32))
    obj = db.Column(db.String(255))
    obj_url = db.Column(db.String(255))
    target = db.Column(db.String(255))
    target_url = db.Column(db.String(255))
    summary = db.Column(db.Text)
    date = db.Column(db.String(19))
    ordinal = db.Column(db.Integer, default=0)


class DownloadStat(db.Model):
    __tablename__ = "download_stats"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    count = db.Column(db.Integer, nullable=False)


class OsStat(db.Model):
    __tablename__ = "os_stats"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    label = db.Column(db.String(32), nullable=False)
    count = db.Column(db.Integer, nullable=False)


class CountryStat(db.Model):
    __tablename__ = "country_stats"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    rank = db.Column(db.Integer)
    label = db.Column(db.String(64), nullable=False)
    count = db.Column(db.Integer, nullable=False)


class BusinessProduct(db.Model):
    __tablename__ = "business_products"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    rating_avg = db.Column(db.Float, default=0.0)
    ratings_count = db.Column(db.Integer, default=0)
    category = db.Column(db.String(64), nullable=False)  # business category slug
    is_featured = db.Column(db.Boolean, default=False)


class Bookmark(db.Model):
    __tablename__ = "bookmarks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    created = db.Column(db.String(10))

    project = db.relationship("Project")


class SiteContent(db.Model):
    __tablename__ = "site_content"
    key = db.Column(db.String(64), primary_key=True)
    value_json = db.Column(db.Text, nullable=False)

    @property
    def value(self):
        return json.loads(self.value_json)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
              "or", "is", "it", "by", "with", "as", "s", "2"}


def tokenize(query):
    return [t.lower() for t in re.split(r"\W+", query or "")
            if t.lower() not in STOP_WORDS and len(t) > 1]


def scored_projects(query, base=None):
    """Token-overlap relevance search over name/summary/description."""
    tokens = tokenize(query)
    qs = base if base is not None else Project.query
    projects = qs.all()
    if not tokens:
        return projects
    scored = []
    for p in projects:
        text = " ".join([p.name or "", p.summary or "",
                         (p.short_description or "")[:400]]).lower()
        name_l = (p.name or "").lower()
        short_l = (p.shortname or "").lower()
        score = 0
        for t in tokens:
            if t in name_l:
                score += 3
            if t in short_l:
                score += 2
            if t in text:
                score += 1
        if score:
            scored.append((score, p))
    scored.sort(key=lambda pair: (-pair[0],
                                  -pair[1].downloads_week or 0,
                                  pair[1].name or ""))
    return [p for _, p in scored]


def parse_int(text, default=0):
    digits = re.sub(r"[^\d]", "", str(text or ""))
    return int(digits) if digits else default


def fmt_int(n):
    return f"{n:,}"


def fmt_compact(n):
    n = n or 0
    if n >= 1_000_000_000:
        v = n / 1_000_000_000
        return f"{v:.1f}B" if v < 10 else f"{v:.0f}B"
    if n >= 1_000_000:
        v = n / 1_000_000
        return f"{v:.1f}M" if v < 10 else f"{v:.0f}M"
    if n >= 1_000:
        v = n / 1_000
        return f"{v:.1f}K" if v < 10 else f"{v:.0f}K"
    return str(n)


def relative_date(date_str):
    if not date_str:
        return ""
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
    except ValueError:
        return date_str
    days = (MIRROR_NOW - d).days
    if days < 0:
        return date_str
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 14:
        return "1 week ago"
    if days < 31:
        return f"{days // 7} weeks ago"
    if days < 60:
        return "1 month ago"
    if days < 365:
        return f"{days // 30} months ago"
    if days < 730:
        return "1 year ago"
    return f"{days // 365} years ago"


# ---------------------------------------------------------------------------
# Upstream-faithful user links (audit fix)
#
# The forge templates linkify author/creator display names to
# /u/<username>/profile/. Deriving the username by lower-casing the display
# name produces wrong usernames for most authors (e.g. "Igor Pavlov" is
# /u/ipavlov/, not /u/igorpavlov/), and the mirror's users table only carries
# the OSS-directory population, so several upstream forum users have no row.
# The mapping below is extracted verbatim from the captured upstream pages
# (source_data/pages/*: every /u/<name>/profile/ href next to its display
# name), so profile links resolve to the same usernames upstream serves.
UPSTREAM_USER_LINKS = {
    "@ipavlov": "ipavlov", "@karlynhoz": "karlynhoz", "@kb0000001": "kb0000001",
    "AdamL": "leckronat", "Alex V": "alexandrv", "AlexS": "sov44",
    "Algrin Bolus": "algrinbolus", "Amber Jones": "amber111", "An mac": "anmac1789",
    "Andrew": "blangel", "Arav": "arav4592", "Aren Cambre": "acambre",
    "Asta Nora": "astanora", "Bella": "llb15", "Bob Smith": "chicken0895",
    "CP van Ekeris": "cvanekeris", "Carlos Nunes": "karlynhoz",
    "Carlos Scheid": "cgscheid", "Casteele M.": "casteele72",
    "Cecily Curtis": "cecilyc23", "ChDelannoy": "chdelannoy",
    "Chloe Jones": "cimanchester123", "Cristian Mattioli": "nerfer4",
    "Deyan Delchev": "ddelchev", "Dmitry Glavatskikh": "dngc99",
    "Dragon 99": "dragon99", "Ellie Jones": "ellie78", "Farahin Fauze": "farahinfauze",
    "GamerGoddessDin": "firegoddessdin", "Harry Stein": "hstein2000",
    "Igor Pavlov": "ipavlov", "Jakub Kuczys": "jackenmen", "Jamie": "ourcefan123111",
    "Janne Soukka": "jannesoukka", "John Howard": "jhphotographer",
    "Keith Schlesinger": "kirk-rs", "KrashDummy": "krashdummy", "Larry": "lar3ryca",
    "Lauren Williams": "lauren10", "Lyubomyr Shaydariv": "l-shaydariv",
    "Miko G": "mgmuana", "Morgan John Dalton": "mog666", "Neustradamus": "neustradamus",
    "Nigbir": "imbir", "Nikita": "nik1231241", "Nobody/Anonymous": "nobody",
    "Noel Reese": "oopscrunch", "Peter Dirk": "geextah", "Peter Henkel": "rohrspatz",
    "Priyanka Phadke": "priya-11", "R. Jasper": "rob-j99", "Reebig Frank": "reebigfrank",
    "Rich Scholl": "rfscholl", "Robert Barcikowski": "rbarciko", "Roy Tam": "roytam1",
    "Rui": "ruuiii", "Sam Tansy": "tansy", "Satish Godara": "satishgodara496",
    "Siddharth Sharma": "ssharma1081", "Stefan Holmes": "honestflames",
    "Tanzmusikus": "tanzmusikus", "Thomas": "thoste", "Thomas Stephens": "dantoys",
    "Tish": "itisljar", "Unglaublich": "unglaublich", "VictorVG": "viksoftru",
    "Wlodzimierz O. Kubera": "wlodzimierz", "Yovaraj Karunakaran": "yovaraj",
    "alida": "alidas", "arhfk": "asovj", "chfakht": "chfakht", "diLan A": "boomramada",
    "engin çiçek": "eskehacettddbey", "estomagado": "estomagado",
    "eugenesan": "eugenesan", "fedorauser67": "fedorauser67", "gaurav": "gau33",
    "ipavlov": "ipavlov", "james anthony lambert": "silverdollar57",
    "john": "modz2021", "kb0000001": "kb0000001", "kp jones": "kp-jones7",
    "matthijs": "tijsco", "mdadm": "mdadm", "mgs": "pol098", "mik": "gmichencigh",
    "mmortal03": "mmortal03", "orion33": "orion33", "r_x": "r_x", "rtm": "rtm",
    "shinchiro": "shinchiro", "simon": "lixu1989", "thebigfatgeek": "thebigfatgeek",
    "therube": "therube", "tsingkong": "tsingkong", "yifei zhu": "ruichuangzhu",
    "风之暇想": "fzxx",
}

# (forum id, thread id) -> (last-post author display name, date) exactly as the
# upstream thread lists render them (source_data/pages/forum*_clean.html).
# The captured seed left forum_threads.last_author/last_date empty, so this is
# the render-layer fallback that keeps the "Last Post" column upstream-faithful
# instead of printing "By None on None".
UPSTREAM_THREAD_LAST_POST = {
    ("45797", "01728b2dfb"): ("Keith Schlesinger", "Thu Aug 13, 2026 04:31 AM"),
    ("45797", "02ab9dee74"): ("r_x", "Sat Sep 05, 2026 09:40 AM"),
    ("45797", "096400c30b"): ("mgs", "Fri Sep 04, 2026 12:05 PM"),
    ("45797", "09cf00be2d"): ("Priyanka Phadke", "Thu Sep 03, 2026 09:12 AM"),
    ("45797", "0f17be73d3"): ("CP van Ekeris", "Sun Sep 20, 2026 08:33 AM"),
    ("45797", "2ed1dd3419"): ("Deyan Delchev", "Sun Jul 26, 2026 11:24 AM"),
    ("45797", "46defab8d4"): ("engin çiçek", "Sun Sep 06, 2026 08:52 PM"),
    ("45797", "514294cd69"): ("Sam Tansy", "Wed Jul 29, 2026 08:03 AM"),
    ("45797", "55adf4c747"): ("matthijs", "Wed Sep 02, 2026 03:10 PM"),
    ("45797", "55bd794c"): ("mmortal03", "Mon Aug 31, 2026 11:07 AM"),
    ("45797", "5eb1b8d5"): ("tsingkong", "Fri Sep 11, 2026 06:05 AM"),
    ("45797", "5ed712eada"): ("风之暇想", "Sat Sep 05, 2026 05:57 AM"),
    ("45797", "735fd9fc84"): ("Casteele M.", "Fri Sep 18, 2026 05:19 AM"),
    ("45797", "74d0dfdce1"): ("kp jones", "Sat Sep 19, 2026 07:30 AM"),
    ("45797", "768a550c16"): ("CP van Ekeris", "Sun Sep 20, 2026 08:30 AM"),
    ("45797", "8299d94c0e"): ("Janne Soukka", "Tue Sep 15, 2026 11:11 PM"),
    ("45797", "8915cc7c74"): ("KrashDummy", "Fri Sep 11, 2026 05:22 PM"),
    ("45797", "942820b266"): ("Igor Pavlov", "Wed Jul 22, 2026 10:34 AM"),
    ("45797", "9ed0a3f537"): ("Larry", "Thu Sep 03, 2026 05:14 PM"),
    ("45797", "b8d64839d0"): ("arhfk", "Sun Jul 19, 2026 08:27 PM"),
    ("45797", "c6812ccfa3"): ("Satish Godara", "Wed Sep 09, 2026 01:01 PM"),
    ("45797", "d62b23968a"): ("Peter Dirk", "Mon Jul 27, 2026 10:04 PM"),
    ("45797", "db6922e1d0"): ("Igor Pavlov", "Wed Sep 23, 2026 10:58 AM"),
    ("45797", "e0906b9334"): ("Tish", "Fri Aug 14, 2026 08:49 PM"),
    ("45797", "f2a6603d5c"): ("Wlodzimierz O. Kubera", "Thu Aug 13, 2026 07:04 PM"),
    ("45798", "009bb83db8"): ("Sam Tansy", "Tue Mar 10, 2026 08:36 PM"),
    ("45798", "14b45206e4"): ("Igor Pavlov", "Mon Aug 31, 2026 06:59 AM"),
    ("45798", "203e624013"): ("Igor Pavlov", "Thu May 21, 2026 05:25 AM"),
    ("45798", "3e72140a2e"): ("VictorVG", "Tue Mar 03, 2026 01:12 AM"),
    ("45798", "3f3f89774b"): ("fedorauser67", "Thu Jul 02, 2026 03:06 AM"),
    ("45798", "568c2620dc"): ("An mac", "Wed Mar 04, 2026 09:25 AM"),
    ("45798", "609e725bf4"): ("Nikita", "Tue Mar 31, 2026 11:07 AM"),
    ("45798", "64e3285d64"): ("james anthony lambert", "Sun Aug 30, 2026 08:58 PM"),
    ("45798", "7cd1100377"): ("Jamie", "Thu Aug 13, 2026 06:17 AM"),
    ("45798", "83e3e1f8bc"): ("orion33", "Mon Feb 16, 2026 12:02 PM"),
    ("45798", "8e8f91f1b5"): ("AlexS", "Wed Apr 08, 2026 02:55 PM"),
    ("45798", "914407e2ad"): ("Algrin Bolus", "Tue Mar 31, 2026 08:20 PM"),
    ("45798", "9196fad1c4"): ("Noel Reese", "Sun Feb 08, 2026 09:25 PM"),
    ("45798", "9a5c7eb9ec"): ("VictorVG", "Wed Feb 04, 2026 06:46 PM"),
    ("45798", "aadb3f765e"): ("therube", "Thu Apr 30, 2026 04:13 PM"),
    ("45798", "b56995273c"): ("Lyubomyr Shaydariv", "Wed Jul 22, 2026 05:39 PM"),
    ("45798", "be65c1f094"): ("Yovaraj Karunakaran", "Sat Apr 04, 2026 05:48 PM"),
    ("45798", "d47452f8be"): ("Dragon 99", "Fri May 01, 2026 01:51 PM"),
    ("45798", "d4bbe9cc"): ("An mac", "Sun Mar 01, 2026 06:28 AM"),
    ("45798", "d4f2f21027"): ("Morgan John Dalton", "Thu Apr 09, 2026 08:12 PM"),
    ("45798", "d7bbafd63a"): ("Igor Pavlov", "Tue Aug 04, 2026 01:03 PM"),
    ("45798", "d8f0c370e0"): ("Sam Tansy", "Wed Jul 29, 2026 08:25 AM"),
    ("45798", "dda4d8d8bd"): ("Unglaublich", "Wed May 06, 2026 06:36 PM"),
    ("45798", "e0541aa8fc"): ("Igor Pavlov", "Thu Sep 03, 2026 09:06 AM"),
    ("45798", "fe29b9d201"): ("Jakub Kuczys", "Sun Jun 14, 2026 12:35 PM"),
}


def user_href(name):
    """Resolve an author display name to the upstream /u/<username>/ slug.

    Returns None when no honest target exists, in which case templates render
    the plain display name (upstream never serves a dead profile link)."""
    if not name or not str(name).strip() or str(name).strip().lower() == "none":
        return None
    name = str(name).strip()
    hit = UPSTREAM_USER_LINKS.get(name)
    if hit:
        return hit
    normalized = name.lower().replace(" ", "")
    if User.query.filter_by(username=normalized).first():
        return normalized
    return None


def thread_last_post(fsid, thread_id, db_author, db_date):
    """(author, date) for a thread's Last Post column: DB value first, then
    the upstream-captured fallback, then None (rendered as a dash)."""
    if db_author and str(db_author).strip() and str(db_author).strip().lower() != "none":
        return db_author, db_date
    hit = UPSTREAM_THREAD_LAST_POST.get((str(fsid), str(thread_id)))
    if hit:
        return hit
    return None, None


def biz_logo(slug):
    """Filename of the product's captured logo, or None when upstream has no
    icon for the product (the card then renders the upstream default-project-icon
    placeholder instead of a broken image)."""
    if not slug:
        return None
    candidate = Path(app.static_folder) / "images" / "ui" / f"biz-{slug}.png"
    return candidate.name if candidate.is_file() else None


def file_download_exists(obj_url):
    """True when an activity-feed obj_url points at a file the mirror actually
    serves (the captured feed references three 26.03 builds that are not in the
    files table; those render as plain text instead of dead links)."""
    if not obj_url:
        return False
    m = re.match(r"/projects/([\w.\-]+)/files/(.+)/download$", str(obj_url))
    if not m:
        return True  # non-download links are rendered as-is
    p = Project.query.filter_by(shortname=m.group(1)).first()
    if not p:
        return False
    return bool(ProjectFile.query.filter_by(project_id=p.id, path=m.group(2),
                                           is_folder=False).first())


app.jinja_env.globals.update(relative_date=relative_date,
                             fmt_int=fmt_int,
                             fmt_compact=fmt_compact,
                             user_href=user_href,
                             thread_last_post=thread_last_post,
                             biz_logo=biz_logo,
                             file_download_exists=file_download_exists)


def get_content(key, default=None):
    row = db.session.get(SiteContent, key)
    return row.value if row else default


def project_or_404(shortname):
    p = Project.query.filter_by(shortname=shortname).first()
    if not p:
        abort(404)
    return p


def paginate(items, page, per_page=PER_PAGE):
    page = max(1, page)
    total = len(items)
    start = (page - 1) * per_page
    return items[start:start + per_page], total, max(1, math.ceil(total / per_page))


# ---------------------------------------------------------------------------
# Facet / directory helpers
# ---------------------------------------------------------------------------
FACET_KINDS = [
    ("os", "OS"),
    ("topic", "Category"),
    ("license", "License"),
    ("translation", "Translations"),
    ("language", "Programming Language"),
    ("devstatus", "Status"),
]

SORT_ORDERS = {
    "score": ("Relevance", lambda qs: qs),
    "popular": ("Most Popular", lambda qs: qs.order_by(Project.downloads_week.desc())),
    "update": ("Last Updated", lambda qs: qs.order_by(Project.updated.desc())),
    "name": ("Name (A-Z)", lambda qs: qs.order_by(Project.name.asc())),
    "rating": ("Rating", lambda qs: qs.order_by(Project.rating_avg.desc())),
}


def sorted_results(q, sort, qs):
    """Result list for the directory: relevance search when a query is
    present (optionally re-sorted by the requested order), or a plain
    ordered browse otherwise. The sort control stays meaningful in both
    modes, matching the upstream directory behavior."""
    if not q:
        return SORT_ORDERS.get(sort, SORT_ORDERS["popular"])[1](qs).all()
    base = scored_projects(q, qs)
    if sort == "score" or sort not in SORT_ORDERS:
        return base
    if sort == "popular":
        return sorted(base, key=lambda p: (-(p.downloads_week or 0), p.name or ""))
    if sort == "update":
        by_name = sorted(base, key=lambda p: (p.name or "").lower())
        return sorted(by_name, key=lambda p: p.updated or "", reverse=True)
    if sort == "name":
        return sorted(base, key=lambda p: (p.name or "").lower())
    if sort == "rating":
        return sorted(base, key=lambda p: (-(p.rating_avg or 0), p.name or ""))
    return base


def facet_counts(projects, kind):
    counts = {}
    for p in projects:
        seen = set()
        for f in p.facets:
            if f.kind == kind and f.value not in seen:
                seen.add(f.value)
                key = (f.value, f.label)
                counts[key] = counts.get(key, 0) + 1
    out = sorted(counts.items(), key=lambda kv: -kv[1])
    return [(slug, label, n) for (slug, label), n in out]


def apply_facets(qs, active_facets):
    """active_facets: {kind: slug} — category pages and query filters."""
    for kind, slug in active_facets.items():
        if kind == "topic" and slug:
            qs = qs.filter(Project.facets.any(kind="topic", value=slug))
        elif kind == "os" and slug:
            qs = qs.filter(Project.facets.any(kind="os", value=slug))
        elif kind == "license" and slug:
            qs = qs.filter(Project.facets.any(kind="license", value=slug))
        elif kind == "language" and slug:
            qs = qs.filter(Project.facets.any(kind="language", value=slug))
        elif kind == "translation" and slug:
            qs = qs.filter(Project.facets.any(kind="translation", value=slug))
        elif kind == "devstatus" and slug:
            qs = qs.filter(Project.facets.any(kind="devstatus", value=slug))
    return qs


# ---------------------------------------------------------------------------
# Routes — homepage and directory
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    stats = get_content("home_stats", {})
    potm = Project.query.filter_by(is_potm=True).all()
    popular = Project.query.filter_by(is_popular=True).order_by(Project.id).all()
    business_categories = get_content("business_categories", [])
    oss_categories = get_content("oss_categories", [])
    featured_business = BusinessProduct.query.filter_by(is_featured=True).limit(3).all()
    return render_template("index.html", stats=stats, potm=potm,
                           popular=popular, business_categories=business_categories,
                           oss_categories=oss_categories,
                           featured_business=featured_business)


@app.route("/directory/")
def directory():
    q = (request.args.get("q") or "").strip()
    sort = request.args.get("sort", "score" if q else "popular")
    page = parse_int(request.args.get("page"), 1)
    active = {k: request.args.get(k, "").strip() for k, _ in FACET_KINDS}
    active = {k: v for k, v in active.items() if v}

    qs = Project.query
    qs = apply_facets(qs, active)
    base = sorted_results(q, sort, qs)

    facets = {kind: facet_counts(base, kind) for kind, _ in FACET_KINDS}
    page_items, total, pages = paginate(base, page)
    return render_template("directory.html", q=q, sort=sort, page=page,
                           projects=page_items, total=total, pages=pages,
                           facets=facets, active=active,
                           title=(f"Search Results for \"{q}\"" if q else "Open Source Software"))


@app.route("/directory/<path:slug>/")
def directory_facet(slug):
    """Browse by a single facet value: /directory/windows/, /directory/games/, ..."""
    parts = [p for p in slug.split("/") if p]
    active = {}
    label = None
    kind = None
    for p in parts:
        found = False
        for k, _ in FACET_KINDS:
            row = ProjectFacet.query.filter_by(kind=k, value=p).first()
            if row:
                active[k] = p
                label = row.label
                kind = k
                found = True
                break
        if not found:
            abort(404)
    q = (request.args.get("q") or "").strip()
    sort = request.args.get("sort", "score" if q else "popular")
    page = parse_int(request.args.get("page"), 1)
    qs = Project.query
    qs = apply_facets(qs, active)
    base = sorted_results(q, sort, qs)
    facets = {k: facet_counts(base, k) for k, _ in FACET_KINDS}
    page_items, total, pages = paginate(base, page)
    heading = "Open Source Software"
    if kind == "os":
        heading = f"Open Source {label} Software"
    return render_template("directory.html", q=q, sort=sort, page=page,
                           projects=page_items, total=total, pages=pages,
                           facets=facets, active=active, label=label,
                           facet_kind=kind, heading=heading,
                           title=(f"Search Results for \"{q}\"" if q else heading))


# ---------------------------------------------------------------------------
# Routes — project pages
# ---------------------------------------------------------------------------
def _project_tabs(p):
    tabs = [("summary", f"/projects/{p.shortname}/", "Summary")]
    if "files" in p.tools or p.files:
        tabs.append(("files", f"/projects/{p.shortname}/files/", "Files"))
    tabs.append(("reviews", f"/projects/{p.shortname}/reviews/", "Reviews"))
    tabs.append(("support", f"/projects/{p.shortname}/support", "Support"))
    if "wiki" in p.tools:
        tabs.append(("wiki", f"/p/{p.shortname}/wiki/", "Wiki"))
    ticket_tabs = []
    for tracker, lbl in [("support-requests", "Support Requests"),
                         ("patches", "Patches"), ("bugs", "Bugs"),
                         ("feature-requests", "Feature Requests")]:
        if tracker in p.tools:
            ticket_tabs.append((tracker, f"/p/{p.shortname}/{tracker}/", lbl))
    if ticket_tabs:
        tabs.append(("tickets", None, "Tickets"))
    if "news" in p.tools:
        tabs.append(("news", f"/p/{p.shortname}/news/", "News"))
    if "discussion" in p.tools:
        tabs.append(("discussion", f"/p/{p.shortname}/discussion/", "Discussion"))
    return tabs, ticket_tabs


@app.route("/projects/<shortname>/")
def project_summary(shortname):
    p = project_or_404(shortname)
    tabs, ticket_tabs = _project_tabs(p)
    reviews = (Review.query.filter_by(project_id=p.id)
               .order_by(Review.created.desc()).limit(5).all())
    activity = (ActivityEvent.query.filter_by(project_id=p.id)
                .order_by(ActivityEvent.ordinal).limit(8).all())
    latest = (ProjectFile.query.filter_by(project_id=p.id, is_default=True).first()
              or ProjectFile.query.filter_by(project_id=p.id, is_folder=False)
              .order_by(ProjectFile.modified.desc()).first())
    recommended = (Project.query
                   .filter(Project.id != p.id,
                           Project.facets.any(kind="topic",
                                              value=(p.facet.get("topic") or [None])[0]))
                   .order_by(Project.downloads_week.desc()).limit(4).all()) \
        if p.facet.get("topic") else []
    related_business = get_content("related_business", {}).get(
        (p.facet.get("topic") or [""])[0], [])
    top_searches = get_content("top_searches", {}).get(p.shortname, [])
    bookmarked = False
    if current_user.is_authenticated:
        bookmarked = Bookmark.query.filter_by(user_id=current_user.id,
                                              project_id=p.id).first() is not None
    return render_template("project_summary.html", p=p, tabs=tabs,
                           ticket_tabs=ticket_tabs, reviews=reviews,
                           activity=activity, latest=latest,
                           recommended=recommended,
                           related_business=related_business,
                           top_searches=top_searches,
                           bookmarked=bookmarked)


@app.route("/p/<shortname>/")
def project_p_redirect(shortname):
    p = Project.query.filter_by(shortname=shortname).first()
    if not p:
        abort(404)
    return redirect(f"/projects/{p.shortname}/", code=301)


@app.route("/projects/<shortname>/files/", defaults={"path": ""})
@app.route("/projects/<shortname>/files/<path:path>/")
def project_files(shortname, path):
    p = project_or_404(shortname)
    tabs, ticket_tabs = _project_tabs(p)
    prefix = path.strip("/")
    children = [f for f in p.files
                if f.parent == prefix and (prefix or f.name)]
    children.sort(key=lambda f: (not f.is_folder, f.name.lower()))
    breadcrumb = []
    acc = ""
    for part in ([x for x in prefix.split("/") if x] or []):
        acc = f"{acc}/{part}" if acc else part
        breadcrumb.append((part, acc))
    latest = (ProjectFile.query.filter_by(project_id=p.id, is_default=True).first()
              or ProjectFile.query.filter_by(project_id=p.id, is_folder=False)
              .order_by(ProjectFile.modified.desc()).first())
    return render_template("project_files.html", p=p, tabs=tabs,
                           ticket_tabs=ticket_tabs, files=children,
                           path=prefix, breadcrumb=breadcrumb, latest=latest)


@app.route("/projects/<shortname>/files/latest/download")
def project_latest_download(shortname):
    p = project_or_404(shortname)
    latest = (ProjectFile.query.filter_by(project_id=p.id, is_default=True).first()
              or ProjectFile.query.filter_by(project_id=p.id, is_folder=False)
              .order_by(ProjectFile.modified.desc()).first())
    if not latest:
        abort(404)
    return redirect(f"/projects/{p.shortname}/files/{latest.path}/download",
                    code=302)


@app.route("/projects/<shortname>/files/<path:path>/download")
def project_file_download(shortname, path):
    p = project_or_404(shortname)
    f = ProjectFile.query.filter_by(project_id=p.id, path=path, is_folder=False).first()
    if not f:
        abort(404)
    # The mirror has no real binaries; the upstream download page shows the
    # file detail "download started" interstitial.
    return render_template("download_started.html", p=p, f=f)


@app.route("/projects/<shortname>/files/stats/timeline")
@app.route("/projects/<shortname>/files/<path:path>/stats/timeline")
def project_stats_timeline(shortname, path=""):
    p = project_or_404(shortname)
    stats = (DownloadStat.query.filter_by(project_id=p.id)
             .order_by(DownloadStat.date).all())
    total = sum(s.count for s in stats)
    os_stats = OsStat.query.filter_by(project_id=p.id).order_by(OsStat.count.desc()).all()
    top_os = os_stats[0] if os_stats else None
    countries = CountryStat.query.filter_by(project_id=p.id).order_by(CountryStat.rank).all()
    top_country = countries[0] if countries else None
    return render_template("stats_timeline.html", p=p, stats=stats,
                           total=total, top_os=top_os, top_country=top_country,
                           os_stats=os_stats, countries=countries, path=path)


@app.route("/projects/<shortname>/files/stats/os")
@app.route("/projects/<shortname>/files/<path:path>/stats/os")
def project_stats_os(shortname, path=""):
    p = project_or_404(shortname)
    os_stats = OsStat.query.filter_by(project_id=p.id).order_by(OsStat.count.desc()).all()
    total = sum(s.count for s in os_stats)
    stats = (DownloadStat.query.filter_by(project_id=p.id)
             .order_by(DownloadStat.date).all())
    return render_template("stats_os.html", p=p, os_stats=os_stats,
                           total=total, stats=stats, path=path)


@app.route("/projects/<shortname>/files/stats/map")
@app.route("/projects/<shortname>/files/<path:path>/stats/map")
def project_stats_map(shortname, path=""):
    p = project_or_404(shortname)
    countries = CountryStat.query.filter_by(project_id=p.id).order_by(CountryStat.rank).all()
    os_labels = [s.label for s in OsStat.query.filter_by(project_id=p.id)
                 .order_by(OsStat.count.desc()).all()]
    stats = (DownloadStat.query.filter_by(project_id=p.id)
             .order_by(DownloadStat.date).all())
    return render_template("stats_map.html", p=p, countries=countries,
                           os_labels=os_labels, stats=stats, path=path)


@app.route("/projects/<shortname>/support")
def project_support(shortname):
    p = project_or_404(shortname)
    tabs, ticket_tabs = _project_tabs(p)
    best = get_content("support_best", {}).get(p.shortname)
    return render_template("project_support.html", p=p, tabs=tabs,
                           ticket_tabs=ticket_tabs, best=best)


@app.route("/projects/<shortname>/reviews/")
def project_reviews(shortname):
    p = project_or_404(shortname)
    tabs, ticket_tabs = _project_tabs(p)
    filter_stars = request.args.get("filter-stars", "all")
    page = parse_int(request.args.get("page"), 1)
    qs = Review.query.filter_by(project_id=p.id)
    if filter_stars in ("1", "2", "3", "4", "5"):
        qs = qs.filter_by(rating=int(filter_stars))
    reviews = qs.order_by(Review.created.desc()).all()
    page_items, total, pages = paginate(reviews, page)
    highest = (Review.query.filter_by(project_id=p.id, rating=5)
               .order_by(Review.helpful_count.desc()).first())
    lowest = (Review.query.filter_by(project_id=p.id)
              .order_by(Review.rating.asc()).first())
    return render_template("project_reviews.html", p=p, tabs=tabs,
                           ticket_tabs=ticket_tabs, reviews=page_items,
                           total=total, pages=pages, page=page,
                           filter_stars=filter_stars,
                           highest=highest, lowest=lowest)


@app.route("/projects/<shortname>/reviews/new", methods=["GET", "POST"])
@login_required
def project_review_new(shortname):
    p = project_or_404(shortname)
    if request.method == "POST":
        rating = parse_int(request.form.get("rating"), 0)
        text = (request.form.get("text") or "").strip()
        ease = parse_int(request.form.get("ease"), 0)
        features = parse_int(request.form.get("features"), 0)
        design = parse_int(request.form.get("design"), 0)
        support = parse_int(request.form.get("support"), 0)
        if not (1 <= rating <= 5) or not text:
            flash("Please pick a star rating and write your review.", "error")
        elif Review.query.filter_by(project_id=p.id,
                                    author_name=current_user.username).first():
            flash("You have already reviewed this project.", "error")
        else:
            db.session.add(Review(project_id=p.id,
                                  author_name=current_user.username,
                                  rating=rating, text=text,
                                  created=MIRROR_NOW.strftime("%Y-%m-%d")))
            p.review_count += 1
            col = {5: "stars_5", 4: "stars_4", 3: "stars_3",
                   2: "stars_2", 1: "stars_1"}[rating]
            setattr(p, col, (getattr(p, col) or 0) + 1)
            p.rating_avg = round((p.stars_5 * 5 + p.stars_4 * 4 + p.stars_3 * 3 +
                                  p.stars_2 * 2 + p.stars_1) / max(1, p.review_count), 2)
            if ease:
                p.rating_ease = round((p.rating_ease or 0) + ease, 2)
            db.session.commit()
            flash("Your review has been posted.", "success")
            return redirect(f"/projects/{p.shortname}/reviews/")
    return render_template("review_new.html", p=p)


# ---------------------------------------------------------------------------
# Routes — Allura tools (tickets / wiki / discussion / news / activity)
# ---------------------------------------------------------------------------
TRACKERS = {"bugs": "Bugs", "feature-requests": "Feature Requests",
            "support-requests": "Support Requests", "patches": "Patches"}


@app.route("/p/<shortname>/_list/tickets")
def project_tickets_list(shortname):
    p = project_or_404(shortname)
    return render_template("tickets_list.html", p=p,
                           trackers=[t for t in TRACKERS if t in p.tools])


@app.route("/p/<shortname>/<tracker>/", methods=["GET"])
def tracker_browse(shortname, tracker):
    if tracker not in TRACKERS:
        abort(404)
    p = project_or_404(shortname)
    if tracker not in p.tools:
        abort(404)
    q = (request.args.get("q") or "").strip()
    status = request.args.get("status", "")
    page = parse_int(request.args.get("page"), 1)
    limit = min(250, max(25, parse_int(request.args.get("limit"), 25)))
    qs = Ticket.query.filter_by(project_id=p.id, tracker=tracker)
    if status:
        qs = qs.filter(Ticket.status == status)
    tickets = qs.order_by(Ticket.ticket_num.desc()).all()
    if q:
        tokens = tokenize(q)
        tickets = [t for t in tickets
                   if any(tok in (t.summary or "").lower() for tok in tokens)]
    total = len(tickets)
    page_items, _, pages = paginate(tickets, page, limit)
    statuses = {}
    for t in Ticket.query.filter_by(project_id=p.id, tracker=tracker).all():
        statuses[t.status] = statuses.get(t.status, 0) + 1
    return render_template("tracker.html", p=p, tracker=tracker,
                           tracker_label=TRACKERS[tracker], tickets=page_items,
                           total=total, pages=pages, page=page, q=q,
                           status=status, limit=limit, statuses=statuses)


@app.route("/p/<shortname>/<tracker>/search/")
def tracker_search(shortname, tracker):
    return tracker_browse(shortname, tracker)


@app.route("/p/<shortname>/<tracker>/new/")
def tracker_new_ticket(shortname, tracker):
    """Upstream's Create Ticket entry: anonymous visitors are sent to the
    login page (upstream behavior); logged-in users see the authorization
    notice the tracker sidebar already carries."""
    if tracker not in TRACKERS:
        abort(404)
    p = project_or_404(shortname)
    if tracker not in p.tools:
        abort(404)
    if not current_user.is_authenticated:
        return redirect("/auth/")
    return render_template("tracker_new.html", p=p, tracker=tracker,
                           tracker_label=TRACKERS[tracker])


@app.route("/p/<shortname>/<tracker>/stats/")
def tracker_stats(shortname, tracker):
    """Upstream's View Stats page: ticket counts by status, from the DB."""
    if tracker not in TRACKERS:
        abort(404)
    p = project_or_404(shortname)
    if tracker not in p.tools:
        abort(404)
    tickets = Ticket.query.filter_by(project_id=p.id, tracker=tracker).all()
    statuses = {}
    for t in tickets:
        statuses[t.status] = statuses.get(t.status, 0) + 1
    priorities = {}
    for t in tickets:
        if t.priority is not None:
            priorities[t.priority] = priorities.get(t.priority, 0) + 1
    return render_template("tracker_stats.html", p=p, tracker=tracker,
                           tracker_label=TRACKERS[tracker],
                           statuses=sorted(statuses.items(),
                                           key=lambda kv: -kv[1]),
                           priorities=sorted(priorities.items()),
                           total=len(tickets))


@app.route("/p/<shortname>/<tracker>/<int:num>/")
def tracker_ticket(shortname, tracker, num):
    if tracker not in TRACKERS:
        abort(404)
    p = project_or_404(shortname)
    t = Ticket.query.filter_by(project_id=p.id, tracker=tracker,
                               ticket_num=num).first()
    if not t:
        abort(404)
    return render_template("ticket_detail.html", p=p, tracker=tracker, t=t,
                           tracker_label=TRACKERS[tracker])


@app.route("/p/<shortname>/wiki/")
def project_wiki(shortname):
    p = project_or_404(shortname)
    if "wiki" not in p.tools:
        abort(404)
    page = WikiPage.query.filter_by(project_id=p.id, title="Home").first()
    pages = WikiPage.query.filter_by(project_id=p.id).order_by(WikiPage.title).all()
    return render_template("wiki_page.html", p=p, page=page, pages=pages,
                           wiki_home=True)


@app.route("/p/<shortname>/wiki/<title>/")
def project_wiki_page(shortname, title):
    p = project_or_404(shortname)
    if "wiki" not in p.tools:
        abort(404)
    page = WikiPage.query.filter_by(project_id=p.id, title=title).first()
    if not page:
        abort(404)
    pages = WikiPage.query.filter_by(project_id=p.id).order_by(WikiPage.title).all()
    return render_template("wiki_page.html", p=p, page=page, pages=pages)


@app.route("/p/<shortname>/wiki/browse_pages/")
def project_wiki_browse(shortname):
    """Upstream's Browse Pages list: every captured wiki page with its last
    modification date."""
    p = project_or_404(shortname)
    if "wiki" not in p.tools:
        abort(404)
    pages = WikiPage.query.filter_by(project_id=p.id).order_by(WikiPage.title).all()
    return render_template("wiki_browse.html", p=p, pages=pages)


@app.route("/p/<shortname>/discussion/")
def project_discussion(shortname):
    p = project_or_404(shortname)
    if "discussion" not in p.tools:
        abort(404)
    forums = Forum.query.filter_by(project_id=p.id).order_by(Forum.id).all()
    return render_template("discussion.html", p=p, forums=forums)


@app.route("/p/<shortname>/discussion/<fsid>/")
def forum_threads(shortname, fsid):
    p = project_or_404(shortname)
    forum = Forum.query.filter_by(project_id=p.id, shortname=fsid).first()
    if not forum:
        abort(404)
    page = parse_int(request.args.get("page"), 1)
    threads = (ForumThread.query.filter_by(forum_id=forum.id)
               .order_by(ForumThread.last_date.desc()).all())
    page_items, total, pages = paginate(threads, page)
    return render_template("forum_threads.html", p=p, forum=forum,
                           threads=page_items, total=total, pages=pages,
                           page=page)


@app.route("/p/<shortname>/discussion/<fsid>/thread/<tid>/")
def forum_thread(shortname, fsid, tid):
    p = project_or_404(shortname)
    forum = Forum.query.filter_by(project_id=p.id, shortname=fsid).first()
    if not forum:
        abort(404)
    thread = ForumThread.query.filter_by(forum_id=forum.id, thread_id=tid).first()
    if not thread:
        abort(404)
    return render_template("forum_thread.html", p=p, forum=forum, thread=thread)


@app.route("/p/<shortname>/news/")
def project_news(shortname):
    p = project_or_404(shortname)
    if "news" not in p.tools:
        abort(404)
    posts = (NewsPost.query.filter_by(project_id=p.id)
             .order_by(NewsPost.date.desc()).all())
    return render_template("news.html", p=p, posts=posts)


@app.route("/p/<shortname>/activity/")
def project_activity(shortname):
    p = project_or_404(shortname)
    events = (ActivityEvent.query.filter_by(project_id=p.id)
              .order_by(ActivityEvent.ordinal).all())
    return render_template("activity.html", p=p, events=events)


@app.route("/p/<shortname>/activity/feed")
def project_activity_feed(shortname):
    """Upstream's project activity RSS/Atom feed (the masthead RSS button)."""
    p = project_or_404(shortname)
    events = (ActivityEvent.query.filter_by(project_id=p.id)
              .order_by(ActivityEvent.ordinal.desc()).limit(30).all())
    base = request.url_root.rstrip("/")
    entries = []
    for ev in events:
        title = f"{ev.actor} {ev.verb} {ev.obj}"
        if ev.summary:
            title = ev.summary
        link = ev.obj_url if (ev.obj_url and str(ev.obj_url).startswith("/")) else f"/p/{p.shortname}/activity/"
        date = str(ev.date).split()[0] if str(ev.date).strip() else "2026-09-04"
        entries.append(
            "    <entry>\n"
            f"      <id>{base}/p/{p.shortname}/activity/#{ev.id}</id>\n"
            f"      <title>{_xml_escape(title)}</title>\n"
            f"      <updated>{date}</updated>\n"
            f"      <link href=\"{base}{link}\"/>\n"
            f"      <author><name>{_xml_escape(ev.actor)}</name></author>\n"
            "      <content type=\"text\">" + _xml_escape(title) + "</content>\n"
            "    </entry>")
    feed = (f"<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
            f"<feed xmlns=\"http://www.w3.org/2005/Atom\">\n"
            f"  <title>{_xml_escape(p.name)} Activity</title>\n"
            f"  <id>{base}/p/{p.shortname}/activity/feed</id>\n"
            f"  <link href=\"{base}/p/{p.shortname}/activity/\"/>\n"
            f"  <updated>{(str(events[0].date).split()[0] if events else '2026-09-04')}</updated>\n"
            + "\n".join(entries) + "\n</feed>\n")
    return app.response_class(feed, mimetype="application/atom+xml")


def _xml_escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# Routes — users
# ---------------------------------------------------------------------------
@app.route("/u/<username>/profile/")
def user_profile(username):
    u = User.query.filter_by(username=username).first()
    display_name = u.display_name if u else None
    joined = u.joined if u else None
    if not u:
        # Upstream serves a profile page for every user its pages link to;
        # the mirror's users table only carries the OSS-directory population.
        # For the upstream forum/ticket authors (UPSTREAM_USER_LINKS values)
        # render the same profile page from the captured display name instead
        # of a dead 404 link.
        display_name = next((dn for dn, un in UPSTREAM_USER_LINKS.items()
                             if un == username), None)
        if not display_name:
            abort(404)

        class _UpstreamAuthor:
            pass

        u = _UpstreamAuthor()
        u.username = username
        u.display_name = display_name
        u.joined = None
    projects = (Project.query
                .filter(Project.developers_json.like(f'%"{username}"%'))
                .order_by(Project.updated.desc()).all())
    return render_template("user_profile.html", u=u, projects=projects)


# ---------------------------------------------------------------------------
# Routes — site pages
# ---------------------------------------------------------------------------
@app.route("/top")
def top_projects():
    all_time = (Project.query.order_by(Project.downloads_total.desc())
                .limit(20).all())
    weekly = (Project.query.order_by(Project.downloads_week.desc())
              .limit(20).all())
    return render_template("top.html", all_time=all_time, weekly=weekly)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/about/leadership")
def leadership():
    team = get_content("leadership", [])
    return render_template("leadership.html", team=team)


@app.route("/reviews")
def reviews_hub():
    return render_template("reviews_hub.html")


@app.route("/create")
@app.route("/create/")
def create_project():
    return render_template("create.html", logged_in=current_user.is_authenticated)


@app.route("/support")
def support_page():
    return render_template("support.html")


# ---------------------------------------------------------------------------
# Routes — content pages (podcast / articles / case studies / blog)
# ---------------------------------------------------------------------------
@app.route("/podcast/")
def podcast():
    episodes = get_content("podcast_episodes", [])
    description = get_content("podcast_description", "")
    return render_template("podcast.html", episodes=episodes,
                           description=description)


@app.route("/articles/")
def articles():
    posts = get_content("articles", [])
    description = get_content("articles_description", "")
    return render_template("articles.html", posts=posts,
                           description=description)


@app.route("/software/case-studies/")
def case_studies():
    categories = get_content("business_categories", [])
    featured = BusinessProduct.query.filter_by(is_featured=True).all()
    return render_template("case_studies.html",
                           categories=categories, featured=featured)


@app.route("/software/vendors/")
def vendors():
    return render_template("vendors.html")


@app.route("/blog/")
def blog():
    posts = get_content("articles", [])
    return render_template("blog.html", posts=posts)


# ---------------------------------------------------------------------------
# Routes — business software directory
# ---------------------------------------------------------------------------
@app.route("/software/")
def software_home():
    categories = get_content("business_categories", [])
    featured = BusinessProduct.query.filter_by(is_featured=True).limit(3).all()
    top = BusinessProduct.query.order_by(BusinessProduct.ratings_count.desc()).limit(24).all()
    return render_template("software_home.html", categories=categories,
                           featured=featured, top=top)


@app.route("/software/<category>/")
def software_category(category):
    categories = get_content("business_categories", [])
    label = next((c["name"] for c in categories if c["slug"] == category), None)
    if not label:
        # Upstream project pages link "Related Business Categories" cards to
        # /software/<slug>/ pages for a few categories that carry no captured
        # product (file-compression, backup, archiving). Serve the category
        # page with an empty product list instead of a dead 404 link — the
        # same page upstream serves.
        related = set()
        for names in get_content("related_business", {}).values():
            for name in names or []:
                related.add(str(name).strip().lower().replace(" ", "-"))
        if category not in related:
            abort(404)
        label = category.replace("-", " ").title()
    products = (BusinessProduct.query.filter_by(category=category)
               .order_by(BusinessProduct.ratings_count.desc()).all())
    return render_template("software_category.html", category=category,
                           label=label, products=products,
                           categories=categories)


@app.route("/software/product/<slug>/")
def software_product(slug):
    product = BusinessProduct.query.filter_by(slug=slug).first()
    if not product:
        abort(404)
    categories = get_content("business_categories", [])
    label = next((c["name"] for c in categories if c["slug"] == product.category), "")
    return render_template("software_product.html", product=product,
                           category_label=label)


# ---------------------------------------------------------------------------
# Routes — auth + account
# ---------------------------------------------------------------------------
@app.route("/auth/", methods=["GET", "POST"])
def auth_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = (User.query.filter_by(username=username).first()
                or User.query.filter_by(email=username.lower()).first())
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            target = request.args.get("next") or "/"
            return redirect(target)
        flash("Invalid username or password.", "error")
    return render_template("auth.html")


@app.route("/user/registration/", methods=["GET", "POST"])
def auth_register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("password_confirm") or ""
        country = (request.form.get("country") or "").strip()
        errors = []
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,14}", username):
            errors.append("Username must be 3-15 characters (lowercase letters, numbers, dashes).")
        if User.query.filter_by(username=username).first():
            errors.append("That username is already taken.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Please enter a valid email address.")
        if User.query.filter_by(email=email).first():
            errors.append("That email address is already registered.")
        if len(password) < 10:
            errors.append("Password must be at least 10 characters long.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            user = User(username=username,
                        display_name=username.title(),
                        email=email,
                        password_hash=bcrypt.generate_password_hash(password).decode(),
                        country=country,
                        joined=MIRROR_NOW.strftime("%Y-%m-%d"))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to SourceForge!", "success")
            return redirect("/account/")
    return render_template("register.html")


@app.route("/logout")
def auth_logout():
    logout_user()
    return redirect("/")


COUNTRY_NAMES = {"US": "United States", "CN": "China", "GB": "United Kingdom",
                 "DE": "Germany", "FR": "France", "JP": "Japan", "IN": "India",
                 "BR": "Brazil", "CA": "Canada", "AU": "Australia"}


@app.route("/account/")
@login_required
def account_home():
    bookmarks = (Bookmark.query.filter_by(user_id=current_user.id)
                 .order_by(Bookmark.created.desc()).all())
    my_reviews = (Review.query.filter_by(author_name=current_user.username)
                  .order_by(Review.created.desc()).all())
    country_name = COUNTRY_NAMES.get(current_user.country,
                                     current_user.country or "Not set")
    return render_template("account.html", bookmarks=bookmarks,
                           reviews=my_reviews, country_name=country_name)


@app.route("/account/bookmark/<shortname>", methods=["POST"])
@login_required
def account_bookmark(shortname):
    p = project_or_404(shortname)
    existing = Bookmark.query.filter_by(user_id=current_user.id,
                                         project_id=p.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash(f"Removed {p.name} from your bookmarks.", "success")
    else:
        db.session.add(Bookmark(user_id=current_user.id, project_id=p.id,
                                created=MIRROR_NOW.strftime("%Y-%m-%d")))
        db.session.commit()
        flash(f"Added {p.name} to your bookmarks.", "success")
    return redirect(request.referrer or f"/projects/{p.shortname}/")


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        display = (request.form.get("display_name") or "").strip()
        country = (request.form.get("country") or "").strip()
        if display:
            current_user.display_name = display
        current_user.country = country or None
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect("/account/")
    return render_template("account_edit.html")


@app.route("/_health")
def health():
    try:
        count = Project.query.count()
    except Exception:
        return {"ok": False, "site": "sourceforge"}, 500
    return {"ok": True, "site": "sourceforge", "projects": count}


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
# Indexes are created with raw SQL in a fixed order: SQLAlchemy iterates
# Table.indexes (a set keyed by object identity), which would otherwise make
# the physical DB layout non-deterministic across builds.
SCHEMA_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)",
    "CREATE INDEX IF NOT EXISTS ix_projects_shortname ON projects (shortname)",
    "CREATE INDEX IF NOT EXISTS ix_project_facets_project ON project_facets (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_facet_kind_value ON project_facets (kind, value)",
    "CREATE INDEX IF NOT EXISTS ix_project_files_project ON project_files (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_reviews_project ON reviews (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_project ON tickets (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_ticket_tracker ON tickets (project_id, tracker, ticket_num)",
    "CREATE INDEX IF NOT EXISTS ix_ticket_posts_ticket ON ticket_posts (ticket_id)",
    "CREATE INDEX IF NOT EXISTS ix_forums_project ON forums (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_forum_threads_forum ON forum_threads (forum_id)",
    "CREATE INDEX IF NOT EXISTS ix_thread_posts_thread ON thread_posts (thread_pk)",
    "CREATE INDEX IF NOT EXISTS ix_wiki_pages_project ON wiki_pages (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_news_posts_project ON news_posts (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_activity_events_project ON activity_events (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_download_stats_project ON download_stats (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_os_stats_project ON os_stats (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_country_stats_project ON country_stats (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_bookmarks_user ON bookmarks (user_id)",
]


def create_schema():
    db.create_all()
    from sqlalchemy import text
    for stmt in SCHEMA_INDEXES:
        db.session.execute(text(stmt))
    db.session.commit()


if os.environ.get("WEBSYN_SKIP_BOOTSTRAP") != "1":
    with app.app_context():
        create_schema()
        from seed_data import seed_benchmark_users, seed_database  # noqa: E402
        seed_database()
        seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
