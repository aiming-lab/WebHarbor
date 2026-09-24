"""Medicare.gov mirror — Flask app.

A frozen-snapshot mirror of https://www.medicare.gov/ (captured 2026-09-23):
the "What's covered?" coverage database (165 real upstream items), 2026
Medicare costs tables, the care-compare provider directory (real harvested
providers across 10 categories), the DME supplier directory + equipment
taxonomy, the publications catalog, a simplified plan finder, the contact
surfaces, and the signed-in MyMedicare area (claims, premiums, messages,
account settings, replacement card).

All content rows come from the tracked source snapshot materialized by
seed_data.py (see .build-generated-seed). Heavy imagery ships in the pinned
asset bundle (see asset_inventory.json).
"""
from __future__ import annotations

import json
import os
import re
import secrets
import hmac
from urllib.parse import urlsplit
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# The Dockerfile and /reset wipe the instance directory; recreate it before
# SQLAlchemy opens its sqlite file (same fix as imgur / google_shopping).
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
DB_PATH = os.environ.get("MEDICARE_GOV_DB_PATH") or f"sqlite:///{BASE_DIR}/instance/medicare_gov.db"
app.config["SQLALCHEMY_DATABASE_URI"] = DB_PATH
app.config["SECRET_KEY"] = os.environ.get("MEDICARE_GOV_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = ""


def local_path(value, fallback="/"):
    parts = urlsplit(value or "")
    if (parts.scheme or parts.netloc or not (value or "").startswith("/")
            or value.startswith("//") or "\\" in value or any(ord(c) < 32 for c in value)):
        return fallback
    return value


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token
app.jinja_env.globals["local_path"] = local_path


@app.before_request
def protect_forms():
    if request.method == "POST" and app.config.get("CSRF_ENABLED", True):
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(expected, supplied):
            abort(400, "Invalid form token. Reload the form and try again.")

# The snapshot instant this mirror freezes. All "due in N days" /
# "past-due" behaviours are computed against this constant, never the wall
# clock, so every reset serves the same deterministic state.
MIRROR_REFERENCE_DATE = date(2026, 9, 23)

US_STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY AS GU MP PR VI".split())

STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "it", "by", "with", "my", "me", "this", "that", "what", "how",
    "does", "do", "i", "you", "your", "cover", "covered", "covers",
}

PROVIDER_TYPE_LABELS = {
    "Physician": "Doctors & clinicians",
    "GroupPractice": "Doctors & clinicians",
    "Hospital": "Hospitals",
    "NursingHome": "Nursing homes including rehab services",
    "HomeHealth": "Home health services",
    "Hospice": "Hospice care",
    "DialysisFacility": "Dialysis facilities",
    "InpatientRehabilitation": "Inpatient rehabilitation facilities",
    "LongTermCare": "Long-term care hospitals",
    "CommunityHealthCenter": "Community health centers",
}

PROVIDER_TYPE_ORDER = [
    "Physician", "Hospital", "NursingHome", "HomeHealth", "Hospice",
    "InpatientRehabilitation", "LongTermCare", "DialysisFacility",
    "CommunityHealthCenter",
]

RATING_LABELS = {
    "1": "1 star", "2": "2 stars", "3": "3 stars", "4": "4 stars",
    "5": "5 stars", "Not Available": "Not yet rated",
}


def stars(rating):
    """Map a raw rating value to (int, label) for template star rows."""
    raw = str(rating or "Not Available")
    value = int(raw) if raw.isdigit() else 0
    label = RATING_LABELS.get(raw, "Not yet rated")
    return value, label


# ---------------------------------------------------------------------------
# models
#
# NOTE: no column uses index=True. SQLAlchemy creates column indexes in a
# set-iteration order that varies per process, which breaks the byte-
# reproducible seed this site builds at image build time (see
# tests/test_seed_determinism.py). The tables are small enough (max ~5k
# rows) that full scans are fine without secondary indexes.
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    medicare_number = db.Column(db.String(20), nullable=False)
    part_a_effective = db.Column(db.String(40))
    part_b_effective = db.Column(db.String(40))
    phone = db.Column(db.String(30))
    is_benchmark = db.Column(db.Boolean, default=False)

    addresses = db.relationship("MailingAddress", backref="user",
                                 order_by="MailingAddress.id", lazy=True)
    claims = db.relationship("Claim", backref="user", order_by="Claim.id", lazy=True)
    messages = db.relationship("Message", backref="user", order_by="Message.id", lazy=True)

    def get_id(self):
        return str(self.id)

    @property
    def current_address(self):
        for addr in self.addresses:
            if addr.is_current:
                return addr
        return self.addresses[0] if self.addresses else None


class MailingAddress(db.Model):
    __tablename__ = "mailing_addresses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    line1 = db.Column(db.String(160), nullable=False)
    line2 = db.Column(db.String(160))
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(4), nullable=False)
    zip = db.Column(db.String(12), nullable=False)
    is_current = db.Column(db.Boolean, default=False)
    effective_date = db.Column(db.String(40))


class Claim(db.Model):
    __tablename__ = "claims"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    service_date = db.Column(db.String(40), nullable=False)
    provider_name = db.Column(db.String(160), nullable=False)
    provider_city = db.Column(db.String(120))
    category = db.Column(db.String(80))
    description = db.Column(db.String(240), nullable=False)
    billed = db.Column(db.String(20), nullable=False)
    medicare_paid = db.Column(db.String(20), nullable=False)
    you_owed = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(40), default="Processed")


class PremiumBill(db.Model):
    __tablename__ = "premium_bills"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    plan = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.String(20), nullable=False)
    due_date = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), default="Due")
    paid_date = db.Column(db.String(40))
    method = db.Column(db.String(60))


class PaymentMethod(db.Model):
    __tablename__ = "payment_methods"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    label = db.Column(db.String(80), nullable=False)
    is_default = db.Column(db.Boolean, default=False)


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    received_at = db.Column(db.String(40), nullable=False)
    is_read = db.Column(db.Boolean, default=False)


class LoginEvent(db.Model):
    __tablename__ = "login_events"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    when = db.Column(db.String(40), nullable=False)
    method = db.Column(db.String(40), nullable=False)
    device = db.Column(db.String(160), nullable=False)


class CardRequest(db.Model):
    __tablename__ = "card_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reason = db.Column(db.String(80), nullable=False)
    requested_at = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(40), default="Mailing in 7-10 days")


class CoverageItem(db.Model):
    __tablename__ = "coverage_items"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), unique=True, nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    summary = db.Column(db.String(400))
    cost_summary = db.Column(db.String(400))
    description_html = db.Column(db.Text)
    details_html = db.Column(db.Text)
    eligible_html = db.Column(db.Text)
    costs_html = db.Column(db.Text)
    how_often_html = db.Column(db.Text)
    facility_html = db.Column(db.Text)
    provider_reqs_html = db.Column(db.Text)
    keywords = db.Column(db.Text)
    covered_by = db.Column(db.String(60))
    is_preventive = db.Column(db.Boolean, default=False)
    letter = db.Column(db.String(2))

    @property
    def frequency(self):
        text = strip_tags(self.how_often_html or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:120]


class CoverageTopic(db.Model):
    __tablename__ = "coverage_topics"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    blurb = db.Column(db.String(300))
    item_slugs = db.Column(db.Text, nullable=False)
    position = db.Column(db.Integer, nullable=False)


class Provider(db.Model):
    __tablename__ = "providers"
    id = db.Column(db.Integer, primary_key=True)
    provider_type = db.Column(db.String(40), nullable=False)
    provider_id = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    address1 = db.Column(db.String(200))
    address2 = db.Column(db.String(200))
    city = db.Column(db.String(80))
    state = db.Column(db.String(4))
    zip = db.Column(db.String(12))
    phone = db.Column(db.String(30))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    distance = db.Column(db.Float)
    search_city = db.Column(db.String(80))
    specialties = db.Column(db.Text)
    detail = db.Column(db.Text)

    @property
    def specialty_list(self):
        return json.loads(self.specialties or "[]")

    @property
    def detail_map(self):
        return json.loads(self.detail or "{}")


class ProviderCity(db.Model):
    __tablename__ = "provider_cities"
    id = db.Column(db.Integer, primary_key=True)
    search_query = db.Column("search_query", db.String(80), unique=True, nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(4), nullable=False)
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)


class DmeSupplier(db.Model):
    __tablename__ = "dme_suppliers"
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    address1 = db.Column(db.String(200))
    address2 = db.Column(db.String(200))
    city = db.Column(db.String(80))
    state = db.Column(db.String(4))
    zip = db.Column(db.String(12))
    phone = db.Column(db.String(30))
    medicare_assignment = db.Column(db.Boolean, default=True)
    specialties = db.Column(db.Text)
    supplies = db.Column(db.Text)

    @property
    def supply_list(self):
        return json.loads(self.supplies or "[]")

    @property
    def specialty_list(self):
        return json.loads(self.specialties or "[]")


class DmeZipRow(db.Model):
    __tablename__ = "dme_zip_rows"
    id = db.Column(db.Integer, primary_key=True)
    zip = db.Column(db.String(6), nullable=False)
    supplier_id = db.Column(db.String(80), nullable=False)
    distance = db.Column(db.Float)
    rank = db.Column(db.Integer, nullable=False)


class DmeZip(db.Model):
    __tablename__ = "dme_zips"
    zip = db.Column(db.String(6), primary_key=True)
    city = db.Column(db.String(80))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)


class EquipmentCategory(db.Model):
    __tablename__ = "equipment_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(400))
    aliases = db.Column(db.Text)
    letter = db.Column(db.String(2))

    @property
    def alias_list(self):
        return json.loads(self.aliases or "[]")


class Publication(db.Model):
    __tablename__ = "publications"
    id = db.Column(db.Integer, primary_key=True)
    product_number = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(240), nullable=False)
    category = db.Column(db.String(80))
    language = db.Column(db.String(40), default="English")
    summary = db.Column(db.Text)
    thumb = db.Column(db.String(120))
    pdf_file = db.Column(db.String(160))
    orderable = db.Column(db.Boolean, default=True)


class PubOrder(db.Model):
    __tablename__ = "pub_orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    publication_id = db.Column(db.Integer, db.ForeignKey("publications.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    format = db.Column(db.String(40), default="Standard Print")
    ship_line1 = db.Column(db.String(200))
    ship_city = db.Column(db.String(80))
    ship_state = db.Column(db.String(4))
    ship_zip = db.Column(db.String(12))
    created_at = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(40), default="Processing")

    publication = db.relationship("Publication", lazy=True)


class Plan(db.Model):
    __tablename__ = "plans"
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    county = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(4), nullable=False)
    plan_type = db.Column(db.String(40), nullable=False)  # Medicare Advantage / Medicare drug plan
    name = db.Column(db.String(160), nullable=False)
    insurer = db.Column(db.String(120), nullable=False)
    plan_kind = db.Column(db.String(30))  # HMO / PPO / PDP
    premium = db.Column(db.String(30), nullable=False)
    deductible = db.Column(db.String(30))
    oop_max = db.Column(db.String(30))
    rating = db.Column(db.String(10))
    benefits = db.Column(db.Text)

    @property
    def benefit_list(self):
        return json.loads(self.benefits or "[]")


class CountyZip(db.Model):
    __tablename__ = "county_zips"
    id = db.Column(db.Integer, primary_key=True)
    zip = db.Column(db.String(6), nullable=False)
    county = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(4), nullable=False)


class CostAmount(db.Model):
    __tablename__ = "cost_amounts"
    id = db.Column(db.Integer, primary_key=True)
    part = db.Column(db.String(20), nullable=False)     # Part A / Part B / Part D ...
    item = db.Column(db.String(120), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.String(120), nullable=False)
    note = db.Column(db.Text)


class ContentPage(db.Model):
    __tablename__ = "content_pages"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    intro = db.Column(db.Text)
    body_html = db.Column(db.Text)
    sections = db.Column(db.Text)  # JSON [{heading, body}]

    @property
    def section_list(self):
        return json.loads(self.sections or "[]")


class SubscriberEmail(db.Model):
    __tablename__ = "subscriber_emails"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.String(40), nullable=False)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def strip_tags(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment or "")).strip()


def tokenize(text: str) -> list[str]:
    return [
        t for t in re.findall(r"[a-z0-9']+", (text or "").lower())
        if t not in STOP_WORDS and len(t) > 1
    ]


def scored_search(rows, query, text_of, limit=40):
    """Token-overlap scoring; never a strict AND match.

    Rows whose *title* contains more query tokens rank above rows that only
    match the keywords/summary, so the natural item surfaces first — the
    upstream coverage search behaves the same way.
    """
    q_tokens = tokenize(query)
    if not q_tokens:
        return rows[:limit]
    scored = []
    for row in rows:
        hay = set(tokenize(text_of(row)))
        if not hay:
            continue
        hits = sum(1 for t in q_tokens if t in hay)
        if not hits:
            continue
        title = getattr(row, "title", "") or ""
        title_tokens = set(tokenize(title))
        title_hits = sum(1 for t in q_tokens if t in title_tokens)
        scored.append((title_hits / len(q_tokens), hits / len(q_tokens), row))
    scored.sort(key=lambda triple: (-triple[0], -triple[1]))
    return [row for _, _, row in scored[:limit]]


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.template_filter("display_text")
def display_text(value):
    # Repair double-escaped punctuation in the captured editorial blocks only.
    return re.sub(r"\\u(201[89cd34]|00a0)", lambda m: chr(int(m[1], 16)), str(value or ""))


@app.template_filter("strip_tags")
def _strip_tags_filter(value):
    return strip_tags(value)


@app.context_processor
def inject_globals():
    return {
        "reference_date": MIRROR_REFERENCE_DATE,
        "provider_type_labels": PROVIDER_TYPE_LABELS,
    }


# ---------------------------------------------------------------------------
# public content routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/_health")
def health():
    return {"ok": True, "site": "medicare_gov"}


@app.route("/basics")
def basics_landing():
    cards = [
        {"title": "Get started with Medicare",
         "text": "Learn about Medicare eligibility, when you can sign up, and the steps to take.",
         "cta": "Get started", "href": url_for("content_page", slug="get-started-with-medicare")},
        {"title": "Medicare costs",
         "text": "Find out what you'll pay for Part A, Part B, and other coverage in 2026.",
         "cta": "Check costs", "href": url_for("costs_page")},
        {"title": "Your Medicare rights",
         "text": "Know your rights and protections when you have Medicare.",
         "cta": "Check your rights", "href": url_for("content_page", slug="your-medicare-rights")},
        {"title": "Reporting fraud & abuse",
         "text": "Learn how to spot and report Medicare fraud and abuse.",
         "cta": "Report fraud & abuse", "href": url_for("content_page", slug="reporting-medicare-fraud-and-abuse")},
        {"title": "End-Stage Renal Disease",
         "text": "Get Medicare coverage information if you have End-Stage Renal Disease (ESRD).",
         "cta": "Learn about ESRD", "href": url_for("content_page", slug="end-stage-renal-disease")},
        {"title": "Reporting a death",
         "text": "Find out how to report a death to Medicare and what happens to coverage.",
         "cta": "Find out how", "href": url_for("content_page", slug="report-a-death")},
    ]
    return render_template("basics_landing.html", cards=cards)


@app.route("/basics/costs/medicare-costs")
def costs_page():
    costs = {}
    for row in CostAmount.query.all():
        costs.setdefault(row.part, []).append(row)
    irmaa_rows = [r for r in costs.get("IRMAA", [])]
    irmaa_rows.sort(key=lambda r: r.id)
    return render_template("costs.html", costs=costs, irmaa=irmaa_rows)


@app.route("/basics/<path:slug>")
def content_page(slug):
    page = ContentPage.query.filter_by(slug=slug).first()
    if page is None:
        abort(404)
    return render_template("content_page.html", page=page)


@app.route("/health-drug-plans")
def health_drug_plans():
    cards = [
        {"title": "Medicare Advantage & other health plans",
         "text": "Learn about Medicare Advantage Plans (Part C), how they work, and other Medicare health plan options.",
         "cta": "Learn about Medicare Advantage", "href": url_for("plan_landing")},
        {"title": "Medicare Supplement Insurance (Medigap)",
         "text": "Find out how Medigap policies help pay some of the health care costs Original Medicare doesn't cover, and find policies in your area.",
         "cta": "Find a Medigap policy", "href": url_for("plan_landing")},
        {"title": "How Medicare works with other coverage",
         "text": "Find out who pays first when you have other insurance, like from an employer or union, COBRA, or Medicaid.",
         "cta": "Learn about coordination of benefits", "href": url_for("publications_search", q="How Medicare Works with Other Insurance")},
        {"title": "Drug coverage (Part D)",
         "text": "Learn about Medicare drug coverage, costs, and how to join a Medicare drug plan.",
         "cta": "Find drug plans", "href": url_for("plan_landing")},
    ]
    return render_template("hdp_landing.html", cards=cards)


@app.route("/providers-services")
def providers_services():
    cards = [
        {"title": "What Original Medicare covers",
         "text": "Find out what services Original Medicare (Part A and Part B) covers and what you pay.",
         "cta": "See what's covered", "href": url_for("coverage_home")},
        {"title": "Getting care in a disaster or emergency",
         "text": "Learn how you get care from Medicare when you have an emergency or a disaster happens.",
         "cta": "Learn about emergency care", "href": url_for("coverage_search", q="emergency")},
        {"title": "Claims, appeals, and complaints",
         "text": "Learn how to check your Medicare claims, file an appeal, or make a complaint.",
         "cta": "Learn about claims & appeals", "href": url_for("content_page", slug="your-medicare-rights/your-protections")},
    ]
    return render_template("providers_landing.html", cards=cards)


@app.route("/sitemap")
def sitemap():
    return render_template("sitemap.html")


@app.route("/talk-to-someone")
def talk_to_someone():
    page = ContentPage.query.filter_by(slug="talk-to-someone").first()
    blocks = page.section_list.get("blocks", []) if page else []
    return render_template("talk_to_someone.html", page_blocks=blocks)


# ---------------------------------------------------------------------------
# coverage database
# ---------------------------------------------------------------------------

@app.route("/coverage")
def coverage_home():
    topics = CoverageTopic.query.order_by(CoverageTopic.position).all()
    return render_template("coverage_landing.html", topics=topics)


@app.route("/coverage/find-alphabetically")
def coverage_alpha():
    letter = (request.args.get("letter") or "A").upper()[:1]
    items = CoverageItem.query.filter_by(letter=letter).order_by(CoverageItem.title).all()
    letters = [
        row[0] for row in db.session.query(CoverageItem.letter).distinct().all()
    ]
    letters = sorted({l for l in letters if l})
    return render_template("coverage_alpha.html", letter=letter, letters=letters, items=items)


@app.route("/coverage/popular-topics")
def coverage_popular():
    topics = CoverageTopic.query.order_by(CoverageTopic.position).all()
    by_slug = {item.slug: item for item in CoverageItem.query.all()}
    groups = []
    for topic in topics:
        members = []
        for entry in json.loads(topic.item_slugs):
            item = by_slug.get(entry.get("slug"))
            if item is not None:
                members.append({"label": entry.get("label") or item.title, "item": item})
        groups.append({"topic": topic, "members": members})
    return render_template("coverage_popular.html", groups=groups)


@app.route("/coverage/search")
def coverage_search():
    query = (request.args.get("q") or "").strip()
    items = []
    if query:
        rows = CoverageItem.query.all()
        items = scored_search(rows, query, lambda r: f"{r.title} {r.summary} {r.keywords}")
    return render_template("coverage_search.html", query=query, items=items)


@app.route("/coverage/<slug>")
def coverage_detail(slug):
    item = CoverageItem.query.filter_by(slug=slug).first()
    if item is None:
        abort(404)
    related = CoverageItem.query.filter(CoverageItem.id != item.id).filter(
        CoverageItem.covered_by == item.covered_by).limit(4).all()
    return render_template("coverage_detail.html", item=item, related=related)


# ---------------------------------------------------------------------------
# provider directory (care-compare)
# ---------------------------------------------------------------------------

@app.route("/care-compare/")
@app.route("/care-compare")
def care_compare_home():
    return render_template("care_compare_home.html")


@app.route("/care-compare/providers/<kind>")
def care_compare_type(kind):
    provider_type = {
        "physicians": "Physician",
        "hospitals": "Hospital",
        "nursing-homes": "NursingHome",
        "home-health": "HomeHealth",
        "hospice": "Hospice",
        "inpatient-rehab": "InpatientRehabilitation",
        "long-term-care": "LongTermCare",
        "dialysis": "DialysisFacility",
        "community-centers": "CommunityHealthCenter",
    }.get(kind)
    if provider_type is None:
        abort(404)
    cities = ProviderCity.query.order_by(ProviderCity.id).all()
    return render_template(
        "care_compare_type.html", kind=kind, provider_type=provider_type,
        label=PROVIDER_TYPE_LABELS.get(provider_type, ""), cities=cities)


@app.route("/care-compare/search")
def care_compare_search():
    provider_type = request.args.get("type", "Physician")
    location = (request.args.get("loc") or "").strip()
    keyword = (request.args.get("q") or "").strip()
    if provider_type not in PROVIDER_TYPE_LABELS:
        provider_type = "Physician"
    sort = request.args.get("sort", "closest")
    if sort not in {"closest", "name"}:
        sort = "closest"
    page = max(1, request.args.get("page", 1, type=int))
    providers = []
    city = None
    total = 0
    if location:
        city = ProviderCity.query.filter(ProviderCity.search_query == location).first()
        if city is None:
            city = ProviderCity.query.filter(ProviderCity.city == location).first()
        if city is None:
            # accept "City, ST"
            parts = [p.strip() for p in location.split(",")]
            if len(parts) == 2:
                city = ProviderCity.query.filter(
                    ProviderCity.city.ilike(parts[0]),
                    ProviderCity.state == parts[1].upper()).first()
        if city is not None:
            rows = Provider.query.filter_by(
                provider_type=provider_type, search_city=city.search_query).all()
            if provider_type == "Physician":
                rows += Provider.query.filter_by(
                    provider_type="GroupPractice", search_city=city.search_query).all()
            if keyword:
                needle = keyword.lower()
                rows = [
                    r for r in rows
                    if needle in r.name.lower()
                    or any(needle in s.lower() for s in r.specialty_list)
                    or (r.detail_map.get("group") or "").lower().find(needle) >= 0
                ]
            rows.sort(key=lambda r: ((r.distance if r.distance is not None else 999), r.name.casefold()))
            if sort == "name":
                rows.sort(key=lambda r: r.name.casefold())
            total = len(rows)
            page = min(page, max(1, (total + 59) // 60))
            providers = rows[(page-1)*60:page*60]
    return render_template(
        "care_compare_search.html", provider_type=provider_type,
        location=location, keyword=keyword, providers=providers,
        total=total, city=city, sort=sort, page=page, pages=max(1, (total+59)//60))


@app.route("/care-compare/provider/<int:provider_row_id>")
def provider_detail(provider_row_id):
    provider = db.session.get(Provider, provider_row_id)
    if provider is None:
        abort(404)
    return render_template("provider_detail.html", provider=provider,
                           label=PROVIDER_TYPE_LABELS.get(provider.provider_type, ""))


# ---------------------------------------------------------------------------
# DME supplier directory
# ---------------------------------------------------------------------------

@app.route("/medical-equipment-suppliers/")
@app.route("/medical-equipment-suppliers")
def dme_home():
    letters = sorted({row[0] for row in db.session.query(EquipmentCategory.letter).distinct().all() if row[0]})
    return render_template("dme_home.html", letters=letters)


@app.route("/medical-equipment-suppliers/directory")
def dme_directory():
    letter = (request.args.get("letter") or "A").upper()[:1]
    cats = EquipmentCategory.query.filter_by(letter=letter).order_by(EquipmentCategory.name).all()
    letters = sorted({row[0] for row in db.session.query(EquipmentCategory.letter).distinct().all() if row[0]})
    return render_template("dme_directory.html", letter=letter, letters=letters, cats=cats)


@app.route("/medical-equipment-suppliers/results")
def dme_results():
    location = (request.args.get("location") or "").strip()
    equipment = (request.args.get("equipment") or "").strip()
    suppliers = []
    total = 0
    zc = None
    if location:
        zc = db.session.get(DmeZip, location[:5])
        if zc is None:
            return render_template("dme_results.html", location=location,
                                   equipment=equipment, suppliers=[], total=0,
                                   zip_known=False)
        rows = (DmeZipRow.query.filter_by(zip=location[:5])
                .order_by(DmeZipRow.rank).all())
        for row in rows:
            sup = DmeSupplier.query.filter_by(supplier_id=row.supplier_id).first()
            if sup is None:
                continue
            if equipment:
                needle = equipment.lower()
                if not any(needle in supply.lower() for supply in sup.supply_list):
                    continue
            sup._distance = row.distance
            suppliers.append(sup)
        total = len(suppliers)
    return render_template("dme_results.html", location=location,
                           equipment=equipment, suppliers=suppliers,
                           total=total, zip_known=True)


# ---------------------------------------------------------------------------
# plan finder (simplified plan compare)
# ---------------------------------------------------------------------------

@app.route("/plan-compare/")
@app.route("/plan-compare")
def plan_landing():
    return render_template("plan_landing.html")


@app.route("/plan-compare/search", methods=["GET", "POST"])
def plan_search():
    zip_code = (request.values.get("zip") or "").strip()
    if zip_code and not re.fullmatch(r"\d{5}", zip_code):
        abort(400, "Enter a 5-digit ZIP code.")
    plan_choice = request.values.get("plan_choice") or request.values.get("type") or "health"
    county_name = request.values.get("county") or ""
    county_zip = CountyZip.query.filter_by(zip=zip_code).first() if zip_code else None
    counties = []
    plans = []
    if county_zip is not None:
        same_county = CountyZip.query.filter_by(zip=zip_code).all()
        counties = sorted({(c.county, c.state) for c in same_county})
        target = county_zip.county
        if county_name:
            if (county_name, county_zip.state) not in counties:
                abort(400, "Choose a county for this ZIP code.")
            target = county_name
        want_type = ("Medicare drug plan" if plan_choice == "drug"
                     else "Medicare Advantage")
        plans = Plan.query.filter_by(county=target, state=county_zip.state, plan_type=want_type).all()
        plans.sort(key=lambda p: (-float(p.rating or 0), p.name.casefold()))
    return render_template(
        "plan_results.html", zip_code=zip_code, plan_choice=plan_choice,
        county=county_zip.county if county_zip else "",
        counties=counties, plans=plans, county_known=county_zip is not None)


@app.route("/plan-compare/plan/<int:plan_id>")
def plan_detail(plan_id):
    plan = db.session.get(Plan, plan_id)
    if plan is None:
        abort(404)
    return render_template("plan_detail.html", plan=plan)


# ---------------------------------------------------------------------------
# publications
# ---------------------------------------------------------------------------

@app.route("/publications")
def publications_home():
    featured = Publication.query.filter_by(product_number="10050").first()
    popular_nums = ["11389", "11579", "02154", "12026"]
    popular = [Publication.query.filter_by(product_number=n).first() for n in popular_nums]
    popular = [p for p in popular if p]
    categories = sorted({row[0] for row in db.session.query(Publication.category).distinct().all() if row[0]})
    languages = sorted({row[0] for row in db.session.query(Publication.language).distinct().all() if row[0]})
    return render_template("publications_home.html", featured=featured,
                           popular=popular, categories=categories, languages=languages)


@app.route("/publications/search")
def publications_search():
    category = request.args.get("category") or ""
    language = request.args.get("language") or "English"
    query = (request.args.get("q") or "").strip()
    rows = Publication.query.order_by(Publication.title).all()
    if category:
        rows = [r for r in rows if r.category == category]
    if language:
        rows = [r for r in rows if r.language == language]
    if query:
        rows = scored_search(rows, query, lambda r: f"{r.title} {r.summary} {r.product_number}")
    categories = sorted({row[0] for row in db.session.query(Publication.category).distinct().all() if row[0]})
    languages = sorted({row[0] for row in db.session.query(Publication.language).distinct().all() if row[0]})
    return render_template("publications_search.html", rows=rows,
                           category=category, language=language, query=query,
                           categories=categories, languages=languages)


@app.route("/publication-ordering/<product_number>", methods=["GET", "POST"])
def publication_order(product_number):
    pub = Publication.query.filter_by(product_number=product_number).first()
    if pub is None:
        abort(404)
    if request.method == "POST":
        # the orderable flag is enforced, not cosmetic: a product marked "isn't
        # available to order" never creates a PubOrder row (audit finding)
        if not pub.orderable:
            flash("This product isn't available to order right now.")
            return redirect(url_for("publication_order", product_number=product_number))
        try:
            quantity = int(request.form.get("quantity", "1"))
        except ValueError:
            abort(400, "Choose a quantity from 1 to 5.")
        format_ = request.form.get("format", "Standard Print")
        if not 1 <= quantity <= 5 or format_ not in {"Standard Print", "Large Print", "Braille"}:
            abort(400, "Choose a valid quantity and print format.")
        address = current_user.current_address if current_user.is_authenticated else None
        fields = {key: (getattr(address, key) if address else request.form.get(key, "")).strip()
                  for key in ("line1", "city", "state", "zip")}
        fields["state"] = fields["state"].upper()
        if (len(fields["line1"]) < 4 or not fields["city"] or fields["state"] not in US_STATES
                or not re.fullmatch(r"\d{5}(?:-\d{4})?", fields["zip"])):
            abort(400, "Enter a complete US mailing address.")
        order = PubOrder(user_id=current_user.id if current_user.is_authenticated else None,
                         publication_id=pub.id, quantity=quantity, format=format_,
                         ship_line1=fields["line1"], ship_city=fields["city"],
                         ship_state=fields["state"], ship_zip=fields["zip"],
                         created_at=MIRROR_REFERENCE_DATE.isoformat())
        db.session.add(order)
        db.session.commit()
        session["publication_orders"] = (session.get("publication_orders", []) + [order.id])[-30:]
        return redirect(url_for("publication_confirmation", order_id=order.id))
    if not pub.orderable:
        # no order form for products marked "isn't available to order"
        flash("This product isn't available to order right now.")
        return redirect(url_for("publications_search", q=pub.title))
    return render_template("pub_order.html", pub=pub)



@app.route("/publication-orders/<int:order_id>")
def publication_confirmation(order_id):
    order = db.session.get(PubOrder, order_id)
    if order is None or not (
        (order.user_id is not None and current_user.is_authenticated and order.user_id == current_user.id)
        or (order.user_id is None and order.id in session.get("publication_orders", []))
    ):
        abort(404)
    return render_template("pub_order_confirm.html", pub=order.publication, order=order)

# ---------------------------------------------------------------------------
# email signup
# ---------------------------------------------------------------------------

@app.route("/signup/email", methods=["POST"])
def email_signup():
    email = (request.form.get("email") or "").strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        flash("Please enter a valid email address.")
        next_url = request.form.get("next") or url_for("home")
        return redirect(local_path(next_url))
    if not SubscriberEmail.query.filter_by(email=email).first():
        db.session.add(SubscriberEmail(email=email, created_at=MIRROR_REFERENCE_DATE.isoformat()))
        db.session.commit()
    return render_template("email_signup_confirm.html", email=email)


# ---------------------------------------------------------------------------
# auth + account area
# ---------------------------------------------------------------------------

@app.route("/account/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user is None:
            user = User.query.filter(db.func.lower(User.username) == email).first()
        if user is not None and check_password_hash(user.password_hash, password):
            login_user(user)
            db.session.add(LoginEvent(
                user_id=user.id, when=MIRROR_REFERENCE_DATE.isoformat(),
                method="Medicare.gov account",
                device=request.form.get("device", "Chrome on Windows")))
            db.session.commit()
            return redirect(url_for("dashboard"))
        flash("That email/username and password combination isn't right. Try again.")
    return render_template("login.html")


@app.route("/account/identity/<partner>")
def identity_partner(partner):
    if partner not in {"id-me", "clear", "login-gov"}:
        abort(404)
    return render_template("identity_partner.html", partner=partner)


@app.route("/account/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/my/dashboard")
@login_required
def dashboard():
    unread = Message.query.filter_by(user_id=current_user.id, is_read=False).count()
    due_bills = PremiumBill.query.filter_by(user_id=current_user.id, status="Due").all()
    return render_template("my/dashboard.html", unread=unread, due_bills=due_bills)


@app.route("/my/claims")
@login_required
def claims():
    rows = Claim.query.filter_by(user_id=current_user.id).order_by(Claim.id).all()
    return render_template("my/claims.html", claims=rows)


@app.route("/my/claims/<int:claim_id>")
@login_required
def claim_detail(claim_id):
    claim = db.session.get(Claim, claim_id)
    if claim is None or claim.user_id != current_user.id:
        abort(404)
    return render_template("my/claim_detail.html", claim=claim)


@app.route("/my/premiums")
@login_required
def premiums():
    bills = PremiumBill.query.filter_by(user_id=current_user.id).order_by(PremiumBill.due_date).all()
    methods = PaymentMethod.query.filter_by(user_id=current_user.id).order_by(PaymentMethod.is_default.desc(), PaymentMethod.id).all()
    return render_template("my/premiums.html", bills=bills, methods=methods)


@app.route("/my/premiums/pay/<int:bill_id>", methods=["POST"])
@login_required
def premium_pay(bill_id):
    bill = db.session.get(PremiumBill, bill_id)
    if bill is None or bill.user_id != current_user.id:
        abort(404)
    if bill.status != "Due":
        flash("This premium has already been paid.")
        return redirect(url_for("premiums"))
    method = request.form.get("method")
    method_row = PaymentMethod.query.filter_by(user_id=current_user.id, label=method).first()
    if method_row is None:
        flash("Choose a payment method.")
        return redirect(url_for("premiums"))
    bill.status = "Paid"
    bill.paid_date = MIRROR_REFERENCE_DATE.isoformat()
    bill.method = method
    db.session.commit()
    return redirect(url_for("premiums"))


@app.route("/my/messages")
@login_required
def messages():
    rows = Message.query.filter_by(user_id=current_user.id).order_by(Message.id).all()
    return render_template("my/messages.html", messages=rows)


@app.route("/my/messages/<int:message_id>")
@login_required
def message_detail(message_id):
    msg = db.session.get(Message, message_id)
    if msg is None or msg.user_id != current_user.id:
        abort(404)
    if not msg.is_read:
        msg.is_read = True
        db.session.commit()
    return render_template("my/message_detail.html", msg=msg)


@app.route("/my/account-settings")
@login_required
def account_settings():
    events = LoginEvent.query.filter_by(user_id=current_user.id).order_by(LoginEvent.id).all()
    requests_ = CardRequest.query.filter_by(user_id=current_user.id).order_by(CardRequest.id).all()
    return render_template("my/account_settings.html", events=events, card_requests=requests_)


@app.route("/my/account-settings/change-address", methods=["POST"])
@login_required
def change_address():
    line1 = (request.form.get("line1") or "").strip()
    line2 = (request.form.get("line2") or "").strip()
    city = (request.form.get("city") or "").strip()
    state = (request.form.get("state") or "").strip().upper()
    zip_code = (request.form.get("zip") or "").strip()
    errors = []
    if len(line1) < 4:
        errors.append("Enter a street address.")
    if not city:
        errors.append("Enter a city.")
    if state not in US_STATES:
        errors.append("Enter a 2-letter state.")
    if not re.match(r"^\d{5}(-\d{4})?$", zip_code):
        errors.append("Enter a 5-digit ZIP code.")
    if errors:
        for err in errors:
            flash(err)
        return redirect(url_for("account_settings"))
    for addr in current_user.addresses:
        addr.is_current = False
    db.session.add(MailingAddress(
        user_id=current_user.id, line1=line1, line2=line2 or None,
        city=city, state=state, zip=zip_code, is_current=True,
        effective_date=MIRROR_REFERENCE_DATE.isoformat()))
    db.session.commit()
    flash("Your mailing address has been updated.")
    return redirect(url_for("account_settings"))


@app.route("/my/account-settings/get-my-medicare-card", methods=["GET", "POST"])
@login_required
def replace_card():
    if request.method == "POST":
        reason = request.form.get("reason", "")
        if reason not in {"lost", "damaged", "stolen", "name-change", "address-change"}:
            flash("Choose a reason for your replacement card.")
            return redirect(url_for("replace_card"))
        if reason == "name-change":
            new_name = (request.form.get("new_name") or "").strip()
            if len(new_name) < 3:
                flash("Enter the name as it appears on your Social Security card.")
                return redirect(url_for("replace_card"))
        req = CardRequest(
            user_id=current_user.id, reason=reason,
            requested_at=MIRROR_REFERENCE_DATE.isoformat(),
            status="Mailing in 7-10 days")
        db.session.add(req)
        db.session.commit()
        return render_template("my/card_confirm.html", req=req)
    return render_template("my/card.html")


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------

def seed_database():
    from seed_data import seed_database as _seed
    _seed()


with app.app_context():
    db.create_all()
    seed_database()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
