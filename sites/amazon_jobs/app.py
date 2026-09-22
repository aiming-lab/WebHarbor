#!/usr/bin/env python3
"""Amazon Jobs (amazon.jobs) mirror — job search, categories, teams, locations,
benefits, applicant account, applications, and job alerts."""
import json
import os
import re
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
DB_PATH = os.path.join(BASE_DIR, "instance", "amazon_jobs.db")

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-amazon-jobs-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log in to manage your applications, profile, and job alerts."

# Reference date the seed data was pinned against (scrape date). Relative
# wording such as "Updated 3 days ago" stays consistent with this date.
MIRROR_REFERENCE_DATE = datetime(2026, 9, 22)

STOP_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "is", "are", "be", "by", "from", "how", "what", "which", "that",
    "this", "me", "my", "jobs", "job", "amazon", "role", "team", "work",
    "experience", "years",
}

EXPERIENCE_BUCKETS = ["Less than 1 year", "1-3 years", "4-6 years", "7+ years"]
CATEGORY_TYPES = ["Corporate", "Student Programs", "Fulfillment Center", "Remote"]
ROLE_TYPES = ["Individual Contributor", "People Manager"]
JOB_TYPES = ["Full Time", "Part Time"]
SORT_OPTIONS = {"relevant": "Most relevant", "recent": "Most recent"}

APPLICATION_STATUSES = [
    "Submitted", "Under review", "Assessment", "Interview",
    "Offer", "No longer under consideration", "Withdrawn",
]

# URL facet param -> Job attribute used for filtering.
FACET_FIELDS = {
    "category": "category_slug",
    "business_category": "team_slug",
    "country": "country_name",
    "city": "city",
    "job_type": "schedule",
    "role_type": "role_type",
    "experience": "experience",
    "category_type": "category_type",
}


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(140), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    first_name = db.Column(db.String(80), default="")
    last_name = db.Column(db.String(80), default="")
    phone = db.Column(db.String(40), default="")
    city = db.Column(db.String(90), default="")
    state = db.Column(db.String(60), default="")
    country = db.Column(db.String(80), default="")
    headline = db.Column(db.String(160), default="")
    linkedin_url = db.Column(db.String(240), default="")
    notify_recommendations = db.Column(db.Boolean, default=True)
    notify_application_updates = db.Column(db.Boolean, default=True)
    notify_newsletter = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    applications = db.relationship("Application", backref="user", lazy=True,
                                   cascade="all, delete-orphan")
    job_alerts = db.relationship("JobAlert", backref="user", lazy=True,
                                 cascade="all, delete-orphan")

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode("utf-8")

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Job(db.Model):
    __tablename__ = "jobs"
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(220), nullable=False)
    slug = db.Column(db.String(240), nullable=False)
    company_name = db.Column(db.String(160), default="")
    city = db.Column(db.String(90), default="")
    state = db.Column(db.String(90), default="")
    country_code = db.Column(db.String(8), default="")
    country_name = db.Column(db.String(80), default="")
    normalized_location = db.Column(db.String(160), default="")
    category = db.Column(db.String(120), default="", index=True)
    category_slug = db.Column(db.String(120), default="", index=True)
    team = db.Column(db.String(120), default="", index=True)
    team_slug = db.Column(db.String(120), default="", index=True)
    schedule = db.Column(db.String(30), default="Full Time")
    role_type = db.Column(db.String(40), default="Individual Contributor")
    experience = db.Column(db.String(30), default="")
    category_type = db.Column(db.String(40), default="Corporate")
    posted_date = db.Column(db.String(40), default="")
    posted_sort = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)
    updated_hours = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, default="")
    basic_qualifications = db.Column(db.Text, default="")
    preferred_qualifications = db.Column(db.Text, default="")
    description_short = db.Column(db.Text, default="")
    is_intern = db.Column(db.Boolean, default=False)

    applications = db.relationship("Application", backref="job", lazy=True)

    def location_card(self):
        """Search-card format: 'City, ST, AUS' as on amazon.jobs result tiles."""
        parts = [self.city, self.state, self.country_code]
        return ", ".join(p for p in parts if p)

    def location_sidebar(self):
        """Detail-sidebar format: 'AUS, ST, City' as on amazon.jobs job pages."""
        parts = [self.country_code, self.state, self.city]
        return ", ".join(p for p in parts if p)

    def quals_list(self, field):
        return [line.strip("-• ").strip() for line in re.split(r"\n+", field or "")
                if line.strip("-• ").strip()]

    def posted_date_label(self):
        return self.posted_date

    def updated_label(self):
        hours = self.updated_hours or 0
        if hours < 24:
            return f"(Updated about {max(hours, 1)} hour{'s' if hours != 1 else ''} ago)"
        days = hours // 24
        if days == 1:
            return "(Updated 1 day ago)"
        if days < 30:
            return f"(Updated {days} days ago)"
        months = days // 30
        return f"(Updated about {months} month{'s' if months > 1 else ''} ago)"


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    label = db.Column(db.String(140), nullable=False)
    hero_desc = db.Column(db.Text, default="")
    sections_json = db.Column(db.Text, default="[]")
    voices_json = db.Column(db.Text, default="[]")
    talent_json = db.Column(db.Text, default="{}")
    order = db.Column(db.Integer, default=0)

    def sections(self):
        return _loads(self.sections_json, [])

    def voices(self):
        return _loads(self.voices_json, [])

    def talent(self):
        return _loads(self.talent_json, {})


class Team(db.Model):
    __tablename__ = "teams"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    label = db.Column(db.String(140), nullable=False)
    hero_title = db.Column(db.String(220), default="")
    hero_desc = db.Column(db.Text, default="")
    hero_image = db.Column(db.String(240), default="")
    blocks_json = db.Column(db.Text, default="[]")
    role_grid_json = db.Column(db.Text, default="[]")
    order = db.Column(db.Integer, default=0)

    def blocks(self):
        return _loads(self.blocks_json, [])

    def role_grid(self):
        return _loads(self.role_grid_json, [])


class LocationPage(db.Model):
    __tablename__ = "location_pages"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    label = db.Column(db.String(160), nullable=False)
    region = db.Column(db.String(80), default="")
    intro = db.Column(db.Text, default="")
    order = db.Column(db.Integer, default=0)


class FaqItem(db.Model):
    __tablename__ = "faq_items"
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(120), nullable=False)
    question = db.Column(db.String(300), nullable=False)
    answer = db.Column(db.Text, default="")
    order = db.Column(db.Integer, default=0)


class BenefitSection(db.Model):
    __tablename__ = "benefit_sections"
    id = db.Column(db.Integer, primary_key=True)
    heading = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default="")
    order = db.Column(db.Integer, default=0)


class LeadershipPrinciple(db.Model):
    __tablename__ = "leadership_principles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    order = db.Column(db.Integer, default=0)


class CampaignBanner(db.Model):
    __tablename__ = "campaign_banners"
    id = db.Column(db.Integer, primary_key=True)
    heading_line1 = db.Column(db.String(200), default="")
    heading_line2 = db.Column(db.String(200), default="")
    subtext = db.Column(db.String(300), default="")
    button_text = db.Column(db.String(60), default="")
    button_link = db.Column(db.String(240), default="")
    image = db.Column(db.String(240), default="")
    image_mobile = db.Column(db.String(240), default="")
    order = db.Column(db.Integer, default=0)


class EmployeeStory(db.Model):
    __tablename__ = "employee_stories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    heading = db.Column(db.String(220), default="")
    role = db.Column(db.String(160), default="")
    team = db.Column(db.String(160), default="")
    team_slug = db.Column(db.String(120), default="")
    location = db.Column(db.String(160), default="")
    story = db.Column(db.Text, default="")
    photo = db.Column(db.String(240), default="")
    order = db.Column(db.Integer, default=0)


class ContentBlock(db.Model):
    """Long-form content for the static how-we-hire / workplace pages."""
    __tablename__ = "content_blocks"
    id = db.Column(db.Integer, primary_key=True)
    page = db.Column(db.String(60), nullable=False, index=True)
    heading = db.Column(db.String(220), default="")
    body = db.Column(db.Text, default="")
    image = db.Column(db.String(240), default="")
    order = db.Column(db.Integer, default=0)


class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    status = db.Column(db.String(60), default="Submitted")
    submitted_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)
    updated_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class JobAlert(db.Model):
    __tablename__ = "job_alerts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    query_text = db.Column(db.String(200), default="")
    location_text = db.Column(db.String(160), default="")
    frequency = db.Column(db.String(30), default="Weekly")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    def match_count(self):
        jobs = Job.query.all()
        if self.query_text:
            jobs = job_search(self.query_text, jobs)
        if self.location_text:
            tokens = [t for t in re.split(r"\W+", self.location_text.lower()) if t]
            jobs = [j for j in jobs if all(
                t in " ".join([j.normalized_location or "", j.city or ""]).lower()
                for t in tokens)]
        return len(jobs)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _loads(value, default):
    try:
        return json.loads(value or "null") or default
    except Exception:
        return default


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


def tokenize(query):
    return [
        token for token in re.split(r"\W+", (query or "").lower())
        if len(token) > 1 and token not in STOP_WORDS
    ]


# Weighted search fields: matches in these fields count strongest.
JOB_STRONG_FIELDS = ("title", "category", "team", "company_name")
JOB_MEDIUM_FIELDS = ("city", "state", "country_name", "normalized_location",
                     "description_short")
JOB_WEAK_FIELDS = ("description", "basic_qualifications", "preferred_qualifications")


# Words that name the internship role family: they must match the seeded
# is_intern flag (no Amazon job title contains the literal word 'internship').
INTERN_TOKENS = {"internship", "internships"}


def _job_token_score_exact(job, token, strong, medium, weak):
    """Score one token against the concatenated search fields."""
    if token in INTERN_TOKENS and getattr(job, "is_intern", False):
        return 3
    if token in strong:
        return 3
    if token in medium or token in weak:
        return 2
    if any(word.startswith(token) for word in strong.split()):
        return 1
    if any(word.startswith(token) for word in medium.split() + weak.split()):
        return 1
    return 0


def job_token_score(job, token):
    strong = " ".join(str(getattr(job, f, "") or "") for f in JOB_STRONG_FIELDS).lower()
    medium = " ".join(str(getattr(job, f, "") or "") for f in JOB_MEDIUM_FIELDS).lower()
    weak = " ".join(str(getattr(job, f, "") or "") for f in JOB_WEAK_FIELDS).lower()
    score = _job_token_score_exact(job, token, strong, medium, weak)
    if score:
        return score
    # Light plural retry, upstream-style: 'engineers' -> 'engineer',
    # 'internships' -> 'internship'. Fires only when the full token has no
    # match at all, so every exact-token query keeps its exact result set.
    if token.endswith("s") and len(token) >= 4:
        return _job_token_score_exact(job, token[:-1], strong, medium, weak)
    return 0


def job_search(query, jobs, min_total=3):
    """Scored job search: every token must match, and the total must show at
    least one strong hit. Token-overlap scoring, never strict AND on raw text."""
    tokens = tokenize(query)
    if not tokens:
        return list(jobs)
    ranked = []
    for job in jobs:
        scores = [job_token_score(job, t) for t in tokens]
        if all(s > 0 for s in scores) and sum(scores) >= min_total:
            ranked.append((sum(scores), job.id, job))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [job for _, __, job in ranked]


def apply_filters(jobs, active, skip=None):
    """Apply the active facet filters to a job list (optionally skipping one)."""
    out = jobs
    for param, field in FACET_FIELDS.items():
        if param == skip:
            continue
        values = active.get(param) or []
        if values:
            out = [j for j in out if getattr(j, field) in values]
    return out


def multi_arg(name):
    """Read a repeatable query param, accepting both ?x=a&x=b and ?x=a,b."""
    got = request.args.getlist(name)
    if not got:
        got = [request.args.get(name, "")]
    out = []
    for value in got:
        out.extend(v for v in (value or "").split(",") if v)
    return out


def location_match(jobs, loc_keyword):
    tokens = [t for t in re.split(r"\W+", loc_keyword.lower()) if t]
    if not tokens:
        return jobs
    return [j for j in jobs if all(
        t in " ".join([
            (j.city or ""), (j.state or ""), (j.country_name or ""),
            (j.normalized_location or ""),
        ]).lower() for t in tokens)]


@app.template_global()
def modified_query(key, value, base=None):
    """Build the URL of the current search with one param changed.

    Facet params toggle: clicking a selected option clears it. Changing a
    facet or the sort restarts from page one.
    """
    args = {k: request.args.getlist(k) for k in request.args}
    if base:
        args = {k: list(v) for k, v in base.items()}
    multi = key in FACET_FIELDS
    if multi:
        current = list(args.get(key, []))
        if value in current:
            current.remove(value)
        else:
            current.append(value)
        if current:
            args[key] = current
        else:
            args.pop(key, None)
        args.pop("offset", None)
    else:
        args[key] = [str(value)]
    pairs = []
    for k, values in args.items():
        for v in values:
            pairs.append((k, v))
    return request.path + ("?" + urlencode(pairs) if pairs else "")


@app.context_processor
def inject_globals():
    return {
        "image_url": lambda name: url_for("static", filename=f"images/{name}"),
        "icon_url": lambda name: url_for("static", filename=f"icons/{name}"),
    }


# ---------------------------------------------------------------------------
# Search (shared by /search, category, and location landing pages)
# ---------------------------------------------------------------------------

def _search_state(preset=None, allow_text=True):
    """Compute the full search view state.

    preset: dict of forced facet params (e.g. {"category": ["software-development"]})
    merged with (and taking precedence over) the request args.
    """
    preset = preset or {}

    def param_list(name, default=""):
        if name in preset:
            return list(preset[name])
        return multi_arg(name) if allow_text else []

    base_query = (request.args.get("base_query", "") if allow_text else "").strip()
    loc_keyword = (request.args.get("loc_keyword", "") if allow_text else "").strip()
    if "base_query" in preset:
        base_query = preset["base_query"]
    if "loc_keyword" in preset:
        loc_keyword = preset["loc_keyword"]
    categories = param_list("category")
    teams = param_list("business_category")
    countries = param_list("country")
    cities = param_list("city")
    job_types = param_list("job_type")
    role_types = param_list("role_type")
    experiences = param_list("experience")
    category_types = param_list("category_type")
    sort_by = request.args.get("sort_by", "relevant")
    if sort_by not in SORT_OPTIONS:
        sort_by = "relevant"
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0
    limit = 10

    jobs = Job.query.all()
    active = {k: v for k, v in {
        "category": categories, "business_category": teams, "country": countries,
        "city": cities, "job_type": job_types, "role_type": role_types,
        "experience": experiences, "category_type": category_types,
    }.items() if v}

    filtered = location_match(apply_filters(jobs, active), loc_keyword)
    matches = job_search(base_query, filtered) if base_query else filtered
    if sort_by == "recent":
        matches = sorted(matches, key=lambda j: (j.posted_sort is None, j.posted_sort),
                         reverse=True)
    total = len(matches)
    page_jobs = matches[offset:offset + limit]

    # Facet option counts: every other filter (including the text query)
    # applies; this facet's own selection is ignored, as on amazon.jobs.
    def facet_pool(skip):
        pool = location_match(apply_filters(jobs, active, skip=skip), loc_keyword)
        if base_query:
            pool = job_search(base_query, pool)
        return pool

    def count_value(pool, field, value):
        return sum(1 for j in pool if getattr(j, field) == value)

    facet_defs = []
    exp_pool = facet_pool("experience")
    facet_defs.append({
        "key": "experience", "label": "INDUSTRY EXPERIENCE",
        "options": [(opt, opt, count_value(exp_pool, "experience", opt))
                     for opt in EXPERIENCE_BUCKETS],
    })
    jt_pool = facet_pool("job_type")
    facet_defs.append({
        "key": "job_type", "label": "JOB TYPE",
        "options": [(opt, opt, count_value(jt_pool, "schedule", opt))
                     for opt in JOB_TYPES],
    })
    cat_pool = facet_pool("category")
    facet_defs.append({
        "key": "category", "label": "JOB CATEGORY",
        "options": [(c.slug, c.label, count_value(cat_pool, "category_slug", c.slug))
                     for c in Category.query.order_by(Category.order)],
    })
    country_pool = facet_pool("country")
    countries_counted = sorted({j.country_name for j in country_pool if j.country_name})
    facet_defs.append({
        "key": "country", "label": "Country/Region",
        "options": [(v, v, count_value(country_pool, "country_name", v))
                     for v in countries_counted],
    })
    city_pool = facet_pool("city")
    city_rank = {}
    for j in city_pool:
        if j.city:
            city_rank[j.city] = city_rank.get(j.city, 0) + 1
    facet_defs.append({
        "key": "city", "label": "City",
        "options": [(v, v, n) for v, n in sorted(
                city_rank.items(), key=lambda kv: (-kv[1], kv[0]))[:25]],
    })
    team_pool = facet_pool("business_category")
    facet_defs.append({
        "key": "business_category", "label": "Team",
        "options": [(t.slug, t.label, count_value(team_pool, "team_slug", t.slug))
                     for t in Team.query.order_by(Team.order)],
    })
    role_pool = facet_pool("role_type")
    facet_defs.append({
        "key": "role_type", "label": "ROLE TYPE",
        "options": [(opt, opt, count_value(role_pool, "role_type", opt))
                     for opt in ROLE_TYPES],
    })
    ctype_pool = facet_pool("category_type")
    facet_defs.append({
        "key": "category_type", "label": "CATEGORY",
        "options": [(opt, opt, count_value(ctype_pool, "category_type", opt))
                     for opt in CATEGORY_TYPES],
    })

    pages = max(1, (total + limit - 1) // limit)
    current_page = offset // limit + 1
    # windowed pagination like upstream: "« 1 2 3 4 5 … 66 »"
    window = []
    if pages <= 7:
        window = list(range(1, pages + 1))
    else:
        window = [1, 2, 3]
        if current_page not in (1, 2, 3, pages):
            window += ["…", current_page - 1, current_page, current_page + 1]
        window += ["…", pages]
        seen = set()
        deduped = []
        for p in window:
            if p == "…" and "…" in deduped:
                continue
            if p != "…" and p in seen:
                continue
            if p != "…":
                seen.add(p)
            deduped.append(p)
        window = deduped
    return {
        "base_query": base_query, "loc_keyword": loc_keyword,
        "page_jobs": page_jobs, "total": total, "offset": offset, "limit": limit,
        "pages": pages, "current_page": current_page, "page_window": window,
        "sort_by": sort_by, "sort_options": SORT_OPTIONS,
        "facets": facet_defs, "active": active,
    }


@app.route("/search")
def search():
    return render_template("search.html", **_search_state())


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    stories = EmployeeStory.query.order_by(EmployeeStory.order).all()
    hero_story = stories[0] if stories else None
    banner = CampaignBanner.query.order_by(CampaignBanner.order).first()
    return render_template("index.html", stories=stories, hero_story=hero_story,
                           banner=banner)


@app.route("/jobs/<job_id>")
@app.route("/jobs/<job_id>/<slug>")
def job_detail(job_id, slug=None):
    job = Job.query.filter_by(job_id=str(job_id)).first_or_404()
    if slug and slug != job.slug:
        return redirect(url_for("job_detail", job_id=job_id, slug=job.slug))
    pool = Job.query.filter(Job.job_id != job.job_id,
                            db.or_(Job.category_slug == job.category_slug,
                                   Job.city == job.city)).all()
    recommended = job_search(job.title, pool)[:5]
    if len(recommended) < 5:
        keep = {j.id for j in recommended}
        extra = [j for j in Job.query.filter(
            Job.job_id != job.job_id, Job.team_slug == job.team_slug).all()
            if j.id not in keep]
        recommended = (recommended + extra)[:5]
    applied = False
    if current_user.is_authenticated:
        applied = Application.query.filter_by(
            user_id=current_user.id, job_id=job.id).first() is not None
    share_url = request.host_url.rstrip("/") + url_for(
        "job_detail", job_id=job.job_id, slug=job.slug)
    return render_template("job_detail.html", job=job, recommended=recommended,
                           applied=applied, share_url=share_url)


@app.route("/job_categories")
def job_categories():
    cats = Category.query.order_by(Category.order).all()
    counts = {c.slug: Job.query.filter_by(category_slug=c.slug).count() for c in cats}
    return render_template("job_categories.html", categories=cats, counts=counts)


@app.route("/job_categories/<slug>")
def job_category_detail(slug):
    cat = Category.query.filter_by(slug=slug).first_or_404()
    count = Job.query.filter_by(category_slug=slug).count()
    state = _search_state(preset={"category": [slug]})
    return render_template(
        "job_category_detail.html", category=cat, count=count, **state)


@app.route("/business_categories")
def business_categories():
    teams = Team.query.order_by(Team.order).all()
    counts = {t.slug: Job.query.filter_by(team_slug=t.slug).count() for t in teams}
    return render_template("business_categories.html", teams=teams, counts=counts)


@app.route("/business_categories/<slug>")
def business_category_detail(slug):
    team = Team.query.filter_by(slug=slug).first_or_404()
    count = Job.query.filter_by(team_slug=slug).count()
    sample = (Job.query.filter_by(team_slug=slug)
              .order_by(Job.posted_sort.desc()).limit(5).all())
    return render_template("business_category_detail.html", team=team,
                           count=count, sample=sample)


@app.route("/locations")
def locations():
    locs = LocationPage.query.order_by(LocationPage.order).all()
    regions = {}
    for loc in locs:
        regions.setdefault(loc.region, []).append(loc)
    return render_template("locations.html", regions=regions)


@app.route("/locations/<path:slug>")
def location_detail(slug):
    loc = LocationPage.query.filter_by(slug=slug).first_or_404()
    city = loc.label.split(",")[0].strip()
    state = _search_state(preset={"loc_keyword": city})
    return render_template("location_detail.html", loc=loc, **state)


@app.route("/benefits/global")
def benefits():
    sections = BenefitSection.query.order_by(BenefitSection.order).all()
    return render_template("benefits.html", sections=sections)


@app.route("/faq")
def faq():
    items = FaqItem.query.order_by(FaqItem.order).all()
    seen = []
    for item in items:
        if item.section not in seen:
            seen.append(item.section)
    sections = [(s, [i for i in items if i.section == s]) for s in seen]
    return render_template("faq.html", sections=sections)


@app.route("/how-we-hire")
def how_we_hire():
    blocks = ContentBlock.query.filter_by(page="how_we_hire").order_by(ContentBlock.order).all()
    intro_row = ContentBlock.query.filter_by(page="how_we_hire_intro").order_by(ContentBlock.order).first()
    resources_row = ContentBlock.query.filter_by(page="how_we_hire_resources").order_by(ContentBlock.order).first()
    resources = [r for r in (resources_row.body if resources_row else "").split("\n") if r]
    return render_template("how_we_hire.html", blocks=blocks,
                           intro=intro_row.body if intro_row else "",
                           resources=resources)


@app.route("/leadership-principles")
def leadership_principles():
    principles = LeadershipPrinciple.query.order_by(LeadershipPrinciple.order).all()
    return render_template("leadership_principles.html", principles=principles)


@app.route("/inclusive-experiences")
def inclusive_experiences():
    blocks = ContentBlock.query.filter_by(page="inclusive_experiences").order_by(ContentBlock.order).all()
    return render_template("content_page.html", blocks=blocks,
                           title="Together at Amazon",
                           intro="We are committed to building a culture and workplace where all Amazonians can feel welcomed and valued.")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account_applications"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("We couldn't find an account with that email and password. "
                  "Check your spelling and try again.", "error")
            return render_template("login.html", email=email)
        login_user(user)
        target = request.args.get("next")
        if target and target.startswith("/"):
            return redirect(target)
        return redirect(url_for("account_applications"))
    return render_template("login.html", email="")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account_applications"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        if not email or "@" not in email:
            flash("Enter a valid email address.", "error")
            return render_template("register.html", form=request.form)
        if not name:
            flash("Enter your name.", "error")
            return render_template("register.html", form=request.form)
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html", form=request.form)
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists. Log in instead.", "error")
            return render_template("register.html", form=request.form)
        user = User(
            username=email.split("@")[0].replace(".", "_") or email,
            email=email, display_name=name, first_name=name.split(" ")[0],
            last_name=" ".join(name.split(" ")[1:]),
            created_at=MIRROR_REFERENCE_DATE,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("account_applications"))
    return render_template("register.html", form={})


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Applicant account
# ---------------------------------------------------------------------------

@app.route("/applicant/dashboard/applications")
@login_required
def account_applications():
    apps = (Application.query.filter_by(user_id=current_user.id)
            .order_by(Application.submitted_at.desc(), Application.id.desc()).all())
    return render_template("applications.html", applications=apps)


@app.route("/applicant/jobs/<job_id>/apply", methods=["GET", "POST"])
@login_required
def apply_job(job_id):
    job = Job.query.filter_by(job_id=str(job_id)).first_or_404()
    existing = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first()
    if request.method == "POST":
        if existing:
            flash("You already have an application for this job.", "error")
            return redirect(url_for("account_applications"))
        application = Application(
            user_id=current_user.id, job_id=job.id, status="Submitted",
            submitted_at=MIRROR_REFERENCE_DATE, updated_at=MIRROR_REFERENCE_DATE)
        db.session.add(application)
        db.session.commit()
        flash(f"Application submitted for {job.title}.", "success")
        return redirect(url_for("account_applications"))
    return render_template("apply.html", job=job, existing=existing)


@app.route("/applicant/applications/<int:application_id>/withdraw", methods=["POST"])
@login_required
def withdraw_application(application_id):
    application = Application.query.filter_by(
        id=application_id, user_id=current_user.id).first_or_404()
    if application.status in ("Withdrawn", "No longer under consideration"):
        flash("This application can no longer be changed.", "error")
        return redirect(url_for("account_applications"))
    application.status = "Withdrawn"
    application.updated_at = MIRROR_REFERENCE_DATE
    db.session.commit()
    flash("Application withdrawn.", "success")
    return redirect(url_for("account_applications"))


@app.route("/user/details")
@login_required
def profile():
    return render_template("profile.html", user=current_user)


@app.route("/user/details/edit", methods=["GET", "POST"])
@login_required
def profile_edit():
    if request.method == "POST":
        user = current_user
        user.display_name = request.form.get("display_name", "").strip() or user.display_name
        user.first_name = request.form.get("first_name", "").strip()
        user.last_name = request.form.get("last_name", "").strip()
        user.phone = request.form.get("phone", "").strip()
        user.city = request.form.get("city", "").strip()
        user.state = request.form.get("state", "").strip()
        user.country = request.form.get("country", "").strip()
        user.headline = request.form.get("headline", "").strip()
        user.linkedin_url = request.form.get("linkedin_url", "").strip()
        if not user.first_name or not user.last_name:
            flash("First and last name are required.", "error")
            return render_template("profile_edit.html", user=user)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))
    return render_template("profile_edit.html", user=current_user)


@app.route("/applicant/communication-preferences", methods=["GET", "POST"])
@login_required
def communication_preferences():
    if request.method == "POST":
        current_user.notify_recommendations = bool(request.form.get("notify_recommendations"))
        current_user.notify_application_updates = bool(request.form.get("notify_application_updates"))
        current_user.notify_newsletter = bool(request.form.get("notify_newsletter"))
        db.session.commit()
        flash("Communication preferences saved.", "success")
        return redirect(url_for("communication_preferences"))
    return render_template("communication_preferences.html", user=current_user)


@app.route("/applicant/job-alerts", methods=["GET", "POST"])
@login_required
def job_alerts():
    if request.method == "POST":
        query_text = request.form.get("query_text", "").strip()
        location_text = request.form.get("location_text", "").strip()
        frequency = request.form.get("frequency", "Weekly")
        if frequency not in ("Daily", "Weekly", "Monthly"):
            frequency = "Weekly"
        if not query_text and not location_text:
            flash("Give the alert at least a keyword or a location.", "error")
            return redirect(url_for("job_alerts"))
        alert = JobAlert(
            user_id=current_user.id, query_text=query_text,
            location_text=location_text, frequency=frequency,
            active=True, created_at=MIRROR_REFERENCE_DATE)
        db.session.add(alert)
        db.session.commit()
        flash("Job alert created.", "success")
        return redirect(url_for("job_alerts"))
    alerts = (JobAlert.query.filter_by(user_id=current_user.id)
              .order_by(JobAlert.created_at.desc(), JobAlert.id.desc()).all())
    return render_template("job_alerts.html", alerts=alerts)


@app.route("/applicant/job-alerts/<int:alert_id>/toggle", methods=["POST"])
@login_required
def job_alert_toggle(alert_id):
    alert = JobAlert.query.filter_by(id=alert_id, user_id=current_user.id).first_or_404()
    alert.active = not alert.active
    db.session.commit()
    flash("Job alert paused." if not alert.active else "Job alert resumed.", "success")
    return redirect(url_for("job_alerts"))


@app.route("/applicant/job-alerts/<int:alert_id>/delete", methods=["POST"])
@login_required
def job_alert_delete(alert_id):
    alert = JobAlert.query.filter_by(id=alert_id, user_id=current_user.id).first_or_404()
    db.session.delete(alert)
    db.session.commit()
    flash("Job alert deleted.", "success")
    return redirect(url_for("job_alerts"))


@app.route("/_health")
def health():
    return {
        "ok": True,
        "site": "amazon_jobs",
        "jobs": Job.query.count(),
        "categories": Category.query.count(),
        "teams": Team.query.count(),
        "locations": LocationPage.query.count(),
        "users": User.query.count(),
    }


with app.app_context():
    db.create_all()
    from seed_data import seed_benchmark_users, seed_database

    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
