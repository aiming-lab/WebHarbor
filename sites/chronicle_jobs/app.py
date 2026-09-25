#!/usr/bin/env python3
"""Chronicle Jobs (jobs.chronicle.com) mirror — academic job board with
keyword/location search, position-type taxonomy browse, job detail pages,
employer hubs, jobseeker accounts (shortlist, applications, job alerts,
resume/CV), career resources, and popular-search landing pages."""
import json
import math
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlencode

from flask import (
    Flask, abort, flash, redirect, render_template, request, url_for
)
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user, logout_user
)
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "chronicle_jobs.db")

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-chronicle-jobs-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "logon"
login_manager.login_message = "Sign in to save jobs, manage alerts, and apply."

# Reference date the upstream capture was pinned against (scrape date).
MIRROR_REFERENCE_DATE = datetime(2026, 9, 22)

JOBS_PER_PAGE = 20
RADIUS_OPTIONS = [0, 5, 10, 15, 20, 50, 100]

STOP_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "is", "are", "be", "by", "from", "how", "what", "which", "that",
    "this", "me", "my", "jobs", "job", "position", "role", "work",
}

FACET_GROUPS = {
    "employment_level": "Employment Level",
    "institution_type": "Institution Type",
    "salary_band": "Salary Band",
    "employment_type": "Employment Type",
    "location": "Location",
}

COUNTRY_REGIONS = {
    "canada": "North America",
    "mexico": "North America",
    "africa": "Africa",
    "asia": "Asia",
    "asia-pacific": "Asia Pacific",
    "europe": "Europe",
    "middle-east": "Middle East",
    "oceania": "Oceania",
    "south-america": "South America",
}


def slugify(text):
    text = re.sub(r"[&/\\#,+()$~%.'\":*?<>{}]", " ", str(text or ""))
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-").strip()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

job_categories = db.Table(
    "job_categories",
    db.Column("job_id", db.Integer, db.ForeignKey("jobs.id"), primary_key=True),
    db.Column("category_id", db.Integer, db.ForeignKey("categories.id"), primary_key=True),
)

job_facets = db.Table(
    "job_facets",
    db.Column("job_id", db.Integer, db.ForeignKey("jobs.id"), primary_key=True),
    db.Column("facet_id", db.Integer, db.ForeignKey("facet_values.id"), primary_key=True),
)


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(140), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), default="")
    last_name = db.Column(db.String(80), default="")
    headline = db.Column(db.String(200), default="")
    phone = db.Column(db.String(40), default="")
    location = db.Column(db.String(140), default="")
    cv_text = db.Column(db.Text, default="")
    skills = db.Column(db.String(400), default="")
    experience = db.Column(db.Text, default="")
    education = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    saved_jobs = db.relationship("SavedJob", backref="user", lazy=True,
                                cascade="all, delete-orphan", order_by="SavedJob.saved_at.desc()")
    applications = db.relationship("Application", backref="user", lazy=True,
                                   cascade="all, delete-orphan", order_by="Application.submitted_at.desc()")
    job_alerts = db.relationship("JobAlert", backref="user", lazy=True,
                                 cascade="all, delete-orphan", order_by="JobAlert.created_at.desc()")

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode("utf-8")

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Category(db.Model):
    """Position types, disciplines, and sub-disciplines (browse taxonomy)."""
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    label = db.Column(db.String(160), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    level = db.Column(db.Integer, default=0)  # 0 position type, 1 discipline, 2 sub-discipline
    sort_order = db.Column(db.Integer, default=0)

    parent = db.relationship("Category", remote_side="Category.id", backref="children")
    jobs = db.relationship("Job", secondary=job_categories, backref="categories", lazy="dynamic")

    @property
    def job_count(self):
        return self.jobs.count()

    def ancestors(self):
        node, chain = self, []
        while node.parent is not None:
            node = node.parent
            chain.append(node)
        return list(reversed(chain))


class FacetValue(db.Model):
    """Flat facet values: employment levels, institution types, salary bands,
    employment types, and locations (states / countries / regions)."""
    __tablename__ = "facet_values"
    id = db.Column(db.Integer, primary_key=True)
    group = db.Column(db.String(40), nullable=False, index=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    label = db.Column(db.String(160), nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    jobs = db.relationship("Job", secondary=job_facets, backref="facet_values", lazy="dynamic")


class Employer(db.Model):
    __tablename__ = "employers"
    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(64), unique=True, nullable=False)
    slug = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(240), nullable=False)
    logo_path = db.Column(db.String(300), default="")
    hero_path = db.Column(db.String(300), default="")
    location = db.Column(db.String(200), default="")
    profile_sections = db.Column(db.Text, default="")  # JSON: [{title, html}]
    social_links = db.Column(db.Text, default="")      # JSON: [url]
    featured = db.Column(db.Boolean, default=False)
    has_profile = db.Column(db.Boolean, default=False)

    jobs = db.relationship("Job", backref="employer", lazy="dynamic")

    @property
    def job_count(self):
        return self.jobs.count()

    @property
    def sections(self):
        try:
            return json.loads(self.profile_sections or "[]")
        except (TypeError, ValueError):
            return []

    @property
    def social(self):
        try:
            return json.loads(self.social_links or "[]")
        except (TypeError, ValueError):
            return []


class Job(db.Model):
    __tablename__ = "jobs"
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    slug = db.Column(db.String(260), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    employer_id = db.Column(db.Integer, db.ForeignKey("employers.id"), nullable=True)
    employer_name = db.Column(db.String(240), default="", index=True)
    location_text = db.Column(db.String(400), default="")
    salary_text = db.Column(db.String(400), default="")
    posted_date = db.Column(db.DateTime, index=True)
    posted_label = db.Column(db.String(40), default="")
    valid_through = db.Column(db.DateTime, nullable=True)
    description_html = db.Column(db.Text, default="")
    snippet = db.Column(db.Text, default="")
    is_top_job = db.Column(db.Boolean, default=False)
    is_sponsored = db.Column(db.Boolean, default=False)
    is_promoted = db.Column(db.Boolean, default=False)

    saved_by = db.relationship("SavedJob", backref="job", lazy=True)
    applications = db.relationship("Application", backref="job", lazy=True)

    @property
    def detail_path(self):
        return f"/job/{self.job_id}/{self.slug}/"

    @property
    def apply_path(self):
        return f"/apply/{self.job_id}/{self.slug}"

    def facet_values_for(self, group):
        return [fv for fv in self.facet_values if fv.group == group]

    def category_chain(self):
        """Return the deepest category + its ancestors."""
        chain = []
        for cat in self.categories:
            walk = cat.ancestors() + [cat]
            chain.append(walk)
        chain.sort(key=lambda c: (-len(c), c[-1].label))
        return chain

    def search_text(self):
        return " ".join([
            self.title or "", self.employer_name or "", self.location_text or "",
            self.snippet or "", re.sub(r"<[^>]+>", " ", self.description_html or ""),
        ]).lower()


class SavedJob(db.Model):
    __tablename__ = "saved_jobs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    saved_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    cover_note = db.Column(db.Text, default="")
    submitted_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)
    status = db.Column(db.String(40), default="Applied")
    withdrawn = db.Column(db.Boolean, default=False)


class JobAlert(db.Model):
    __tablename__ = "job_alerts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    email = db.Column(db.String(140), nullable=False)
    keywords = db.Column(db.String(200), default="")
    location = db.Column(db.String(200), default="")
    radius = db.Column(db.Integer, default=20)
    frequency = db.Column(db.String(20), default="Daily")
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)
    active = db.Column(db.Boolean, default=True)

    def matching_jobs(self):
        return search_jobs(keywords=self.keywords, location_text=self.location)[0]


class Article(db.Model):
    __tablename__ = "articles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    teaser = db.Column(db.Text, default="")
    author = db.Column(db.String(160), default="")
    kicker = db.Column(db.String(80), default="")
    date_label = db.Column(db.String(60), default="")
    image_path = db.Column(db.String(300), default="")
    source_url = db.Column(db.String(400), default="")
    featured = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)


class LandingPage(db.Model):
    __tablename__ = "landing_pages"
    id = db.Column(db.Integer, primary_key=True)
    landing_id = db.Column(db.Integer, unique=True, nullable=False)
    slug = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(240), nullable=False)
    intro = db.Column(db.Text, default="")
    keywords = db.Column(db.String(200), default="")
    location = db.Column(db.String(200), default="")
    sort_order = db.Column(db.Integer, default=0)


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), default="")
    email = db.Column(db.String(140), default="")
    topic = db.Column(db.String(120), default="")
    message = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Search + facet helpers
# ---------------------------------------------------------------------------

def tokenize(query):
    return [t for t in re.split(r"\W+", (query or "").lower())
            if t not in STOP_WORDS and len(t) > 1]


def search_jobs(keywords=None, location_text=None, categories=None, facets=None,
                sort="Relevance", page=1, per_page=JOBS_PER_PAGE):
    """Scored token-overlap search over jobs, optionally restricted to a set
    of categories and/or facet values (ALL of them — chained facet URLs are
    intersections, order-independent, mirroring upstream), with Relevance /
    Date sorting and pagination."""
    query = Job.query
    for category in categories or []:
        query = query.filter(Job.categories.contains(category))
    for facet in facets or []:
        query = query.filter(Job.facet_values.contains(facet))

    keywords = (keywords or "").strip()
    location_text = (location_text or "").strip()

    if keywords or location_text:
        records = []
        for job in query.all():
            text = job.search_text()
            if keywords:
                tokens = tokenize(keywords)
                if not tokens:
                    score = 0
                else:
                    title_text = (job.title or "").lower()
                    score = sum(1 for t in tokens if t in text)
                    # title hits weigh double
                    score += sum(1 for t in tokens if t in title_text)
                if score == 0:
                    continue
            else:
                score = 0
            if location_text:
                loc = (job.location_text or "").lower()
                lt = location_text.lower()
                if lt not in loc:
                    # allow state-only match when the query names a city of that state
                    state = state_for_city(location_text)
                    if not (state and state.lower() in loc):
                        continue
                    score += 0.5
            records.append((job, score))
        if sort == "Date":
            records.sort(key=lambda r: (r[0].posted_date or datetime.min, r[1]), reverse=True)
        else:
            records.sort(key=lambda r: (r[1], r[0].posted_date or datetime.min), reverse=True)
        total = len(records)
        start = (page - 1) * per_page
        jobs = [r[0] for r in records[start:start + per_page]]
    else:
        if sort == "Date":
            query = query.order_by(Job.posted_date.desc())
        else:
            query = query.order_by(Job.is_top_job.desc(), Job.posted_date.desc())
        total = query.count()
        start = (page - 1) * per_page
        jobs = query.offset(start).limit(per_page).all()

    pages = max(1, math.ceil(total / per_page))
    return jobs, total, pages


_CITY_STATE_CACHE = {}


def state_for_city(city_name):
    """Best-effort city -> state mapping from the seeded job locations."""
    key = (city_name or "").strip().lower()
    if not key:
        return None
    if key in _CITY_STATE_CACHE:
        return _CITY_STATE_CACHE[key]
    rows = Job.query.filter(Job.location_text.ilike(f"%{city_name}%")).all()
    for row in rows:
        m = re.match(r"([^,]+),\s*([A-Za-z ]+?)\s*\((US|USA)\)", row.location_text or "")
        if m and m.group(1).strip().lower() == key:
            _CITY_STATE_CACHE[key] = m.group(2).strip()
            return _CITY_STATE_CACHE[key]
    _CITY_STATE_CACHE[key] = None
    return None


def resolve_browse_path(path_segments):
    """Resolve /jobs/<seg>/<seg>/... into (categories, facets, leftover page)."""
    categories, facets, page = [], [], 1
    for seg in path_segments:
        if seg.isdigit():
            page = int(seg)
            continue
        cat = Category.query.filter_by(slug=seg).first()
        if cat:
            categories.append(cat)
            continue
        facet = FacetValue.query.filter_by(slug=seg).first()
        if facet:
            facets.append(facet)
            continue
        abort(404)
    return categories, facets, page


def facet_counts(jobs_query):
    """Count jobs per facet value for the sidebar, computed from a query."""
    counts = {}
    for fv in FacetValue.query.all():
        counts[fv.id] = jobs_query.filter(Job.facet_values.contains(fv)).count()
    return counts


def category_counts(jobs_query):
    counts = {}
    for cat in Category.query.filter_by(level=0).all():
        counts[cat.id] = jobs_query.filter(Job.categories.contains(cat)).count()
    return counts


# Canonical ordering for chained-browse headings: position-type categories
# first (in chain order), then the flat facet groups, location last.
FACET_GROUP_ORDER = {
    "employment_level": 0,
    "institution_type": 1,
    "salary_band": 2,
    "employment_type": 3,
}


def browse_heading(categories, facets):
    """Upstream chained-browse heading: "<A> <B> jobs in <Location>" —
    e.g. /jobs/adjunct/texas/ and /jobs/texas/adjunct/ both render
    "Adjunct jobs in Texas"; a location-only page renders
    "Jobs in Texas"; /jobs/adjunct/texas/houston/ keeps the deepest
    location ("Adjunct jobs in Houston")."""
    cat_labels = [c.label for c in categories]
    other = sorted([f for f in facets if f.group != "location"],
                   key=lambda f: FACET_GROUP_ORDER.get(f.group, 99))
    locations = [f.label for f in facets if f.group == "location"]
    parts = cat_labels + [f.label for f in other]
    if locations:
        if parts:
            return " ".join(parts) + " jobs in " + locations[-1]
        return "Jobs in " + locations[-1]
    return " ".join(parts) + " jobs"


def build_pagination(path, page, pages, params=None):
    """Build the First / n / Last pagination list for a browse or search URL."""
    params = params or {}
    base = f"/jobs/{path}/" if path else "/jobs/"
    def url_for_page(n):
        q = ""
        if params:
            q = "?" + urlencode(params)
        if n <= 1:
            return base + q
        return base.rstrip("/") + f"/{n}/" + q
    # upstream style: First, a five-page window around the current page, Last
    items = []
    if pages > 1:
        items.append({"label": "First", "url": url_for_page(1), "current": page == 1})
    if pages <= 5:
        window = list(range(1, pages + 1))
    else:
        start = min(max(1, page - 2), pages - 4)
        window = list(range(start, start + 5))
    for p in window:
        items.append({"label": str(p), "url": url_for_page(p), "current": p == page})
    if pages > 5:
        items.append({"label": "Last", "url": url_for_page(pages), "current": page == pages})
    return items


@app.context_processor
def inject_globals():
    return {
        "Job": Job,
        "total_jobs": lambda: Job.query.count(),
        "position_types": lambda: Category.query.filter_by(level=0).order_by(Category.sort_order).all(),
        "employment_levels": lambda: FacetValue.query.filter_by(group="employment_level").order_by(FacetValue.sort_order).all(),
        "locations": lambda: FacetValue.query.filter_by(group="location").order_by(FacetValue.sort_order).all(),
        "institution_types": lambda: FacetValue.query.filter_by(group="institution_type").order_by(FacetValue.sort_order).all(),
        "salary_bands": lambda: FacetValue.query.filter_by(group="salary_band").order_by(FacetValue.sort_order).all(),
        "employment_types": lambda: FacetValue.query.filter_by(group="employment_type").order_by(FacetValue.sort_order).all(),
    }


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    top_jobs = Job.query.filter_by(is_top_job=True).order_by(Job.posted_date.desc()).limit(4).all()
    featured = Employer.query.filter_by(featured=True).all()
    articles = Article.query.order_by(Article.sort_order).limit(3).all()
    popular = LandingPage.query.order_by(LandingPage.sort_order).limit(4).all()
    total = Job.query.count()
    return render_template(
        "index.html", top_jobs=top_jobs, featured=featured, articles=articles,
        popular=popular, total=total)


@app.route("/jobs/", defaults={"path": ""})
@app.route("/jobs/<path:path>")
def browse_jobs(path):
    segments = [s for s in (path or "").split("/") if s]
    categories, facets, page = resolve_browse_path(segments)
    keywords = (request.args.get("Keywords") or request.args.get("keywords") or "").strip()
    location_text = (request.args.get("radialtown") or request.args.get("location") or "").strip()
    sort = request.args.get("sort", "Relevance")
    if sort not in ("Relevance", "Date"):
        sort = "Relevance"

    # Upstream chained-facet semantics (verified against jobs.chronicle.com):
    # within the position-type group the FIRST category segment wins
    # (/jobs/administrative/academic-affairs/ -> Administrative only), within
    # a flat facet group the FIRST value wins (/jobs/adjunct/post-doc/ ->
    # Adjunct only), and within the location group the LAST value wins
    # (/jobs/adjunct/texas/houston/ -> Houston refines Texas). Selections from
    # different groups all intersect, order-independent.
    segment_groups = {cat.slug: "category" for cat in categories}
    for fv in facets:
        segment_groups[fv.slug] = fv.group
    categories = categories[:1]
    kept_facets = {}
    for fv in facets:
        if fv.group == "location":
            kept_facets["location"] = fv
        else:
            kept_facets.setdefault(fv.group, fv)
    facets = list(kept_facets.values())

    base_query = Job.query
    for cat in categories:
        base_query = base_query.filter(Job.categories.contains(cat))
    for fv in facets:
        base_query = base_query.filter(Job.facet_values.contains(fv))

    jobs, total, pages = search_jobs(
        keywords=keywords, location_text=location_text,
        categories=categories, facets=facets,
        sort=sort, page=page)

    heading = None
    if keywords:
        heading = f"Found {total:,} jobs using the term '{keywords}'"
    elif categories or facets:
        heading = browse_heading(categories, facets)

    # sidebar links chain the current selection (upstream behavior): a facet
    # link replaces its own group's segment and preserves every other group
    # (e.g. on /jobs/adjunct/texas/ the Position Type links prepend
    # /jobs/<cat>/adjunct/texas/ and the Location links replace Texas)
    segments = [s for s in segments if not s.isdigit()]

    def chain_url(slug, group=None):
        if group == "category":
            rest = [slug] + [s for s in segments
                             if segment_groups.get(s) != "category"]
        else:
            rest = [s for s in segments
                    if segment_groups.get(s) != group] + [slug]
        return "/jobs/" + "/".join(rest) + "/"

    def remove_url(slug):
        rest = [s for s in segments if s != slug]
        return "/jobs/" + "/".join(rest) + "/" if rest else "/jobs/"

    def clear_categories_url():
        rest = [s for s in segments
                if s not in {c.slug for c in categories}]
        return "/jobs/" + "/".join(rest) + "/" if rest else "/jobs/"
    params = {}
    if keywords:
        params["Keywords"] = keywords
    if location_text:
        params["radialtown"] = location_text
    if sort != "Relevance":
        params["sort"] = sort
    base = f"/jobs/{path}/" if path else "/jobs/"

    # sidebar taxonomy context: when a category is selected, upstream shows
    # the selected chain plus the children of the deepest selection
    if categories:
        deepest = categories[-1]
        chain = deepest.ancestors() + [deepest]
        children = sorted(deepest.children, key=lambda c: c.label)
        sidebar_categories = [{"kind": "chain", "item": c} for c in chain] + [
            {"kind": "child", "item": c} for c in children
        ]
        top_categories = []
    else:
        sidebar_categories = []
        top_categories = Category.query.filter_by(level=0).order_by(Category.sort_order).all()

    def sort_url(target):
        q = dict(params)
        if q.get("sort") == "Relevance":
            q.pop("sort", None)
        if target != "Relevance":
            q["sort"] = target
        return base + ("?" + urlencode(q) if q else "")

    return render_template(
        "search.html", jobs=jobs, total=total, pages=pages, page=page,
        heading=heading, keywords=keywords, location_text=location_text,
        sort=sort, categories=categories, facets=facets,
        base_query=base_query, path=path,
        selected_category_ids=[c.id for c in categories],
        selected_facet_ids=[f.id for f in facets],
        sidebar_categories=sidebar_categories,
        top_categories=top_categories,
        deepest_category=categories[-1] if categories else None,
        chain_url=chain_url, remove_url=remove_url,
        clear_categories_url=clear_categories_url,
        heading_is_label=bool(heading and not keywords),
        sort_url=sort_url,
        pagination=build_pagination(path, page, pages, params))


@app.route("/searchjobs/")
def search_jobs_page():
    keywords = (request.args.get("Keywords") or request.args.get("keywords") or "").strip()
    location_text = (request.args.get("radialtown") or "").strip()
    radius = request.args.get("RadialLocation", "20")
    sort = request.args.get("sort", "Relevance")
    # upstream paginates keyword-search results with the Page query parameter
    # (jobs.chronicle.com /searchjobs/?...&Page=2); honor it so results beyond
    # the first 20 cards stay reachable through the visible paginator
    try:
        page = max(1, int(request.args.get("Page", "1")))
    except (TypeError, ValueError):
        page = 1
    jobs, total, pages = search_jobs(keywords=keywords, location_text=location_text,
                                      categories=[], facets=[], sort=sort, page=page)
    heading = f"Found {total:,} jobs using the term '{keywords}'" if keywords else None
    params = {}
    if keywords:
        params["Keywords"] = keywords
    if location_text:
        params["radialtown"] = location_text
    if sort != "Relevance":
        params["sort"] = sort

    def sort_url(target):
        q = dict(params)
        if q.get("sort") == "Relevance":
            q.pop("sort", None)
        if target != "Relevance":
            q["sort"] = target
        return "/searchjobs/" + ("?" + urlencode(q) if q else "")

    def page_url(n):
        q = dict(params)
        if n > 1:
            q["Page"] = n
        return "/searchjobs/" + ("?" + urlencode(q) if q else "")

    # upstream-style paginator: First, a five-page window, Last (page 1 omits
    # the Page parameter exactly like upstream /searchjobs/ links)
    items = []
    if pages > 1:
        items.append({"label": "First", "url": page_url(1), "current": page == 1})
    if pages <= 5:
        window = list(range(1, pages + 1))
    else:
        start = min(max(1, page - 2), pages - 4)
        window = list(range(start, start + 5))
    for p in window:
        items.append({"label": str(p), "url": page_url(p), "current": p == page})
    if pages > 5:
        items.append({"label": "Last", "url": page_url(pages), "current": page == pages})
    if not items:
        items = [{"label": "1", "url": page_url(1), "current": True}]

    return render_template(
        "search.html", jobs=jobs, total=total, pages=pages, page=page,
        heading=heading, keywords=keywords, location_text=location_text,
        sort=sort, categories=[], facets=[], base_query=Job.query, path="",
        selected_category_ids=[], selected_facet_ids=[],
        sidebar_categories=[], top_categories=Category.query.filter_by(level=0).order_by(Category.sort_order).all(),
        deepest_category=None, heading_is_label=False,
        chain_url=lambda slug, group=None: f"/jobs/{slug}/", remove_url=lambda slug: "/jobs/",
        clear_categories_url=lambda: "/jobs/", sort_url=sort_url,
        pagination=items)


@app.route("/job/<int:job_id>/<slug>/")
def job_detail(job_id, slug):
    job = Job.query.filter_by(job_id=job_id).first_or_404()
    similar = [j for j in (Job.query
              .filter(Job.id != job.id)
              .filter(Job.location_text == job.location_text)
              .order_by(Job.posted_date.desc()).limit(4).all())]
    if len(similar) < 4:
        have = {s.id for s in similar}
        # prefer the deepest category (position type last) for similarity
        deep = sorted(job.categories, key=lambda c: -c.level)
        for cat in deep:
            extra = (Job.query.filter(Job.id != job.id)
                     .filter(Job.categories.contains(cat))
                     .order_by(Job.posted_date.desc()).limit(6).all())
            for e in extra:
                if e.id not in have:
                    similar.append(e)
                    have.add(e.id)
                if len(similar) >= 4:
                    break
            if len(similar) >= 4:
                break
    prev_job = (Job.query.filter(Job.posted_date > job.posted_date)
                .order_by(Job.posted_date.asc()).first()) if job.posted_date else None
    next_job = (Job.query.filter(Job.posted_date < job.posted_date)
                .order_by(Job.posted_date.desc()).first()) if job.posted_date else None
    return render_template("job_detail.html", job=job, similar=similar[:4],
                           prev_job=prev_job, next_job=next_job)


@app.route("/job/<int:job_id>/")
def job_detail_redirect(job_id):
    job = Job.query.filter_by(job_id=job_id).first_or_404()
    return redirect(job.detail_path)


@app.route("/apply/<int:job_id>/<slug>", methods=["GET", "POST"])
def apply_job(job_id, slug):
    job = Job.query.filter_by(job_id=job_id).first_or_404()
    if not current_user.is_authenticated:
        flash("Sign in or create an account to apply for this job.", "info")
        return redirect(url_for("logon", PipelinedPage=job.detail_path))
    existing = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first()
    if request.method == "POST":
        if existing and not existing.withdrawn:
            flash("You have already applied for this job.", "info")
            return redirect(url_for("your_jobs", ActiveSection="Applications"))
        cover = request.form.get("cover", "").replace("\r\n", "\n").strip()
        if len(cover) < 20:
            flash("Please include a short cover note (at least 20 characters).", "error")
            return render_template("apply.html", job=job, cover=cover)
        if existing:
            existing.cover_note = cover
            existing.withdrawn = False
            existing.status = "Applied"
            existing.submitted_at = datetime.now()
        else:
            db.session.add(Application(user_id=current_user.id, job_id=job.id, cover_note=cover))
        db.session.commit()
        flash("Your application was submitted to the employer.", "success")
        return redirect(url_for("your_jobs", ActiveSection="Applications"))
    return render_template("apply.html", job=job, cover="", existing=existing)


@app.route("/employer/<ref>/<slug>/")
def employer_detail(ref, slug):
    employer = Employer.query.filter_by(ref=ref).first()
    if employer is None:
        # upstream links to the same hub via legacy numeric refs; fall back
        # to the slug so both URL forms resolve to the same employer
        employer = Employer.query.filter_by(slug=slug).first_or_404()
    jobs = employer.jobs.order_by(Job.posted_date.desc()).limit(6).all()
    return render_template("employer_detail.html", employer=employer, jobs=jobs)


@app.route("/employers/")
def employers_index():
    letter = request.args.get("letter", "")
    query = Employer.query.filter(Employer.has_profile | Employer.featured)
    if letter:
        query = query.filter(Employer.name.ilike(f"{letter}%"))
    employers = query.order_by(Employer.name).all()
    return render_template("employers.html", employers=employers, letter=letter)


@app.route("/career-resources/")
def career_resources():
    articles = Article.query.order_by(Article.sort_order).all()
    return render_template("career_resources.html", articles=articles)


@app.route("/career-resources/<slug>/")
def career_article(slug):
    article = Article.query.filter_by(slug=slug).first_or_404()
    return render_template("career_article.html", article=article)


@app.route("/landingpagelist/")
def landing_page_list():
    pages = LandingPage.query.order_by(LandingPage.sort_order).all()
    return render_template("landing_list.html", pages=pages)


@app.route("/landingpage/<int:landing_id>/<slug>/")
def landing_page(landing_id, slug):
    page = LandingPage.query.filter_by(landing_id=landing_id).first_or_404()
    jobs, total, pages = search_jobs(keywords=page.keywords, location_text=page.location,
                                      categories=[], facets=[])
    return render_template("landing_page.html", page=page, jobs=jobs, total=total)


@app.route("/contact-us/", methods=["GET", "POST"])
def contact_us():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        topic = request.form.get("topic", "Job seeker support").strip()
        message = request.form.get("message", "").strip()
        if not name or not email or "@" not in email or len(message) < 10:
            flash("Please provide your name, a valid email address, and a short message.", "error")
            return render_template("contact_us.html", form=request.form)
        db.session.add(ContactMessage(name=name, email=email, topic=topic, message=message))
        db.session.commit()
        flash("Thanks — the Chronicle Jobs team will get back to you by email.", "success")
        return redirect(url_for("contact_us"))
    return render_template("contact_us.html", form={})


@app.route("/jobsrss/")
def jobs_rss():
    jobs = Job.query.order_by(Job.posted_date.desc()).limit(20).all()
    xml = render_template("jobsrss.xml", jobs=jobs)
    return app.response_class(xml, mimetype="application/rss+xml")


# ---------------------------------------------------------------------------
# Account routes
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("your_jobs"))
    if request.method == "POST":
        first = request.form.get("first_name", "").strip()
        last = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not first or not last:
            flash("Please enter your first and last name.", "error")
        elif not email or "@" not in email:
            flash("Please enter a valid email address.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists. Try signing in.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            user = User(email=email, first_name=first, last_name=last)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Your account was created. Welcome to Chronicle Jobs.", "success")
            return redirect(url_for("your_jobs"))
    return render_template("register.html")


@app.route("/logon", methods=["GET", "POST"])
def logon():
    if current_user.is_authenticated:
        return redirect(url_for("your_jobs"))
    pipelined = request.values.get("PipelinedPage", "")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Signed in.", "success")
            target = pipelined or url_for("your_jobs")
            if not target.startswith("/"):
                target = url_for("your_jobs")
            return redirect(target)
        flash("That email/password combination is not recognized.", "error")
    return render_template("logon.html", PipelinedPage=pipelined)


@app.route("/logout")
def logout():
    logout_user()
    flash("Signed out.", "success")
    return redirect(url_for("index"))


@app.route("/your-jobs/", methods=["GET", "POST"])
@login_required
def your_jobs():
    if request.method == "POST":
        action = request.form.get("Action", "")
        job_id = request.form.get("JobId", "")
        try:
            job = Job.query.filter_by(job_id=int(job_id)).first()
        except (TypeError, ValueError):
            job = None
        if job and action == "ShortlistJob":
            if not SavedJob.query.filter_by(user_id=current_user.id, job_id=job.id).first():
                db.session.add(SavedJob(user_id=current_user.id, job_id=job.id))
                db.session.commit()
            flash(f"Saved: {job.title}", "success")
        elif job and action in ("RemoveShortlistedJob", "UnshortlistJob"):
            SavedJob.query.filter_by(user_id=current_user.id, job_id=job.id).delete()
            db.session.commit()
            flash(f"Removed from shortlist: {job.title}", "success")
        else:
            flash("That action could not be completed.", "error")
        return_url = request.form.get("ReturnUrl", "")
        if isinstance(return_url, str) and return_url.startswith("~"):
            return_url = return_url[1:]
        if return_url and return_url.startswith("/"):
            return redirect(return_url)
        return redirect(url_for("your_jobs", ActiveSection="ShortList"))

    section = request.args.get("ActiveSection", "ShortList")
    if section not in ("ShortList", "Applications", "JobAlerts", "Profile"):
        section = "ShortList"
    alerts = current_user.job_alerts
    applications = Application.query.filter_by(user_id=current_user.id).order_by(
        Application.submitted_at.desc()).all()
    return render_template(
        "your_jobs.html", section=section, alerts=alerts, applications=applications)


@app.route("/applications/<int:application_id>/withdraw", methods=["POST"])
@login_required
def withdraw_application(application_id):
    application = Application.query.filter_by(id=application_id, user_id=current_user.id).first_or_404()
    application.withdrawn = True
    application.status = "Withdrawn"
    db.session.commit()
    flash(f"Application withdrawn: {application.job.title}", "success")
    return redirect(url_for("your_jobs", ActiveSection="Applications"))


@app.route("/newalert", methods=["GET", "POST"])
def new_alert():
    pre_keywords = request.args.get("keywords", "")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        keywords = request.form.get("keywords", "").strip()
        location = request.form.get("location", "").strip()
        frequency = request.form.get("frequency", "Daily")
        try:
            radius = int(request.form.get("radius", 20))
        except ValueError:
            radius = 20
        if not email or "@" not in email:
            flash("Please enter a valid email address.", "error")
        elif frequency not in ("Daily", "Weekly"):
            flash("Choose how often you want to receive jobs.", "error")
        else:
            alert = JobAlert(
                user_id=current_user.id if current_user.is_authenticated else None,
                email=email, keywords=keywords, location=location,
                radius=radius, frequency=frequency)
            db.session.add(alert)
            db.session.commit()
            flash(f"Job alert created — new {frequency.lower()} jobs for this search will go to {email}.", "success")
            return redirect(url_for("alert_done", email=email))
    return render_template("new_alert.html", pre_keywords=pre_keywords,
                           frequency="Daily", radius=20)


@app.route("/alert-done/")
def alert_done():
    email = request.args.get("email", "")
    return render_template("alert_done.html", email=email)


@app.route("/alerts/<int:alert_id>/delete", methods=["POST"])
@login_required
def delete_alert(alert_id):
    alert = JobAlert.query.filter_by(id=alert_id, user_id=current_user.id).first_or_404()
    db.session.delete(alert)
    db.session.commit()
    flash("Job alert deleted.", "success")
    return redirect(url_for("your_jobs", ActiveSection="JobAlerts"))


@app.route("/profile/", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name", "").strip()
        current_user.last_name = request.form.get("last_name", "").strip()
        current_user.phone = request.form.get("phone", "").strip()
        current_user.location = request.form.get("location", "").strip()
        current_user.headline = request.form.get("headline", "").strip()
        new_password = request.form.get("new_password", "")
        if new_password:
            if len(new_password) < 8:
                flash("New password must be at least 8 characters.", "error")
                return redirect(url_for("profile"))
            current_user.set_password(new_password)
        db.session.commit()
        flash("Your profile was updated.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html")


@app.route("/profilecv/", methods=["GET", "POST"])
@login_required
def profile_cv():
    if request.method == "POST":
        # normalize CRLF: browsers submit textareas with \r\n line endings, so
        # re-saving an unedited seeded field must not rewrite its line endings
        form = {k: v.replace("\r\n", "\n") for k, v in request.form.items()}
        current_user.headline = form.get("headline", "").strip()
        current_user.location = form.get("location", "").strip()
        current_user.skills = form.get("skills", "").strip()
        current_user.experience = form.get("experience", "").strip()
        current_user.education = form.get("education", "").strip()
        current_user.cv_text = form.get("cv_text", "").strip()
        db.session.commit()
        flash("Your resume details were saved.", "success")
        return redirect(url_for("profile_cv"))
    return render_template("profile_cv.html")


# ---------------------------------------------------------------------------
# Static-ish content pages
# ---------------------------------------------------------------------------

@app.route("/about-us/")
def about_us():
    return render_template("content_page.html", title="About Us",
                           slug="about-us")


@app.route("/terms-and-conditions/")
def terms_and_conditions():
    return render_template("content_page.html", title="Terms & Conditions",
                           slug="terms-and-conditions")


@app.route("/privacy-policy/")
def privacy_policy():
    return render_template("content_page.html", title="Privacy Policy",
                           slug="privacy-policy")


@app.route("/user-agreement/")
def user_agreement():
    return render_template("content_page.html", title="User Agreement",
                           slug="user-agreement")


@app.route("/accessibility-statement/")
def accessibility_statement():
    return render_template("content_page.html", title="Accessibility Statement",
                           slug="accessibility-statement")


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.route("/_health")
def health():
    return {
        "ok": True,
        "site": "chronicle_jobs",
        "jobs": Job.query.count(),
        "categories": Category.query.count(),
        "facet_values": FacetValue.query.count(),
        "employers": Employer.query.count(),
        "articles": Article.query.count(),
        "users": User.query.count(),
    }


# `python app.py` loads this file as __main__; register it under its import name
# too so seed_data's `from app import ...` reuses this module instead of
# building a second Flask app + SQLAlchemy instance.
sys.modules.setdefault("app", sys.modules[__name__])

if os.environ.get("WEBSYN_SKIP_BOOTSTRAP") != "1":
    with app.app_context():
        db.create_all()
        from seed_data import seed_benchmark_users, seed_database

        seed_database()
        seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
