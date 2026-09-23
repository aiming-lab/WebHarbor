"""Instructure (instructure.com) mirror — Flask app.

Mirrors the Instructure corporate site: the homepage, product and solutions
pages, the Resource Center hubs (case studies, ebooks, videos, blogs,
webinars, research, podcasts, infographics, product overviews), press
releases, in-the-news, events, careers, leadership, partners, community,
support FAQ, site search, demo request and contact forms, plus mirror
accounts with saved resources and webinar registrations.

All runtime content comes from the seeded SQLite database; heavy images live
under static/images/ (HF-managed assets).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import (BooleanField, PasswordField, SelectField, StringField,
                     TextAreaField)
from wtforms.validators import (DataRequired, Email, EqualTo, Length,
                                Optional, ValidationError)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-instructure-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "INSTRUCTURE_DB_PATH",
    f"sqlite:///{BASE_DIR}/instance/instructure.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = ""

MIRROR_REFERENCE_DATE = datetime(2026, 9, 22)

# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------

HUBS = [
    ("case-studies", "Case Studies", "case_study"),
    ("ebooks", "Ebooks & Buyer's Guides", "ebook"),
    ("videos", "Product Demos & Videos", "video"),
    ("blog", "Blogs", "blog"),
    ("webinars", "On-Demand Webinars", "webinar"),
    ("research-reports", "Research", "research_report"),
    ("podcast", "Podcasts", "podcast"),
    ("infographic", "Infographics", "infographic"),
    ("product-overviews", "Product Overviews", "product_overview"),
]

TYPE_LABEL = {
    "case_study": "Case Studies",
    "ebook": "Ebooks & Buyer's Guides",
    "video": "Product Demos & Videos",
    "blog": "Blogs",
    "webinar": "On-Demand Webinars",
    "research_report": "Research Reports",
    "podcast": "Podcasts",
    "infographic": "Infographics",
    "product_overview": "Product Overviews",
    "press_release": "Press Releases",
}


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    job_title = db.Column(db.String(120), default="")
    organization = db.Column(db.String(160), default="")
    organization_type = db.Column(db.String(60), default="")
    country = db.Column(db.String(80), default="")
    state = db.Column(db.String(80), default="")
    phone = db.Column(db.String(40), default="")
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    saved = db.relationship("SavedResource", back_populates="user",
                            cascade="all, delete-orphan")
    registrations = db.relationship("WebinarRegistration", back_populates="user",
                                   cascade="all, delete-orphan")

    def set_password(self, raw: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(raw).decode("utf-8")

    def check_password(self, raw: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_active(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return str(self.id)


class SavedResource(db.Model):
    __tablename__ = "saved_resources"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)
    user = db.relationship("User", back_populates="saved")
    resource = db.relationship("Resource")
    __table_args__ = (db.UniqueConstraint("user_id", "resource_id"),)


class WebinarRegistration(db.Model):
    __tablename__ = "webinar_registrations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)
    user = db.relationship("User", back_populates="registrations")
    resource = db.relationship("Resource")
    __table_args__ = (db.UniqueConstraint("user_id", "resource_id"),)


class Resource(db.Model):
    __tablename__ = "resources"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    type = db.Column(db.String(40), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    snippet = db.Column(db.Text, default="")
    intro = db.Column(db.Text, default="")
    body_json = db.Column(db.Text, default="")      # JSON list of {heading,text,html}
    micro_heading = db.Column(db.String(120), default="")
    card_img = db.Column(db.String(255), default="")
    logo_img = db.Column(db.String(255), default="")
    hero_img = db.Column(db.String(255), default="")
    publish_date = db.Column(db.String(60), default="")
    event_date = db.Column(db.String(60), default="")
    org_types = db.Column(db.String(255), default="")      # CSV
    product_brands = db.Column(db.String(255), default="")  # CSV
    product_sub_brands = db.Column(db.String(255), default="")  # CSV
    topics = db.Column(db.String(255), default="")         # CSV
    stage = db.Column(db.String(60), default="")
    roles = db.Column(db.String(255), default="")
    region = db.Column(db.String(60), default="")
    stat_json = db.Column(db.Text, default="")             # case-study stat bar
    media_id = db.Column(db.String(60), default="")
    transcript = db.Column(db.Text, default="")
    pdf_url = db.Column(db.String(500), default="")
    author_name = db.Column(db.String(160), default="")
    author_title = db.Column(db.String(160), default="")
    author_img = db.Column(db.String(255), default="")
    list_order = db.Column(db.Integer, default=0)
    external_url = db.Column(db.String(500), default="")

    @property
    def body_blocks(self) -> list[dict]:
        if not self.body_json:
            return []
        try:
            return json.loads(self.body_json)
        except json.JSONDecodeError:
            return []

    @property
    def body_text(self) -> str:
        return " ".join(b.get("text", "") for b in self.body_blocks)

    @property
    def stats(self) -> list[dict]:
        if not self.stat_json:
            return []
        try:
            return json.loads(self.stat_json)
        except json.JSONDecodeError:
            return []

    @property
    def org_type_list(self) -> list[str]:
        return [x for x in (self.org_types or "").split(",") if x]

    @property
    def product_list(self) -> list[str]:
        return [x for x in (self.product_sub_brands or "").split(",") if x]

    @property
    def topic_list(self) -> list[str]:
        return [x for x in (self.topics or "").split(",") if x]

    @property
    def type_label(self) -> str:
        return TYPE_LABEL.get(self.type, self.type)

    def href(self) -> str:
        # Press releases render through the /press-release/<slug> detail route
        # (press_detail); the generic /resources/<seg>/<slug> route rejects the
        # press-release segment, so search-result cards for press releases must
        # not link there (they 404ed).
        if self.type == "press_release":
            return url_for("press_detail", slug=self.slug)
        return url_for("resource_detail", seg=self.route_seg, slug=self.slug)

    @property
    def route_seg(self) -> str:
        if self.type == "press_release":
            return "press-release"
        return {
            "case_study": "case-studies",
            "ebook": "ebooks",
            "video": "videos",
            "blog": "blog",
            "webinar": "webinars",
            "research_report": "research-reports",
            "podcast": "podcast",
            "infographic": "infographic",
            "product_overview": "product-overviews",
        }.get(self.type, "other")


class Event(db.Model):
    __tablename__ = "events"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    title = db.Column(db.String(500), nullable=False)
    event_type = db.Column(db.String(40), default="In Person")
    event_date = db.Column(db.String(60), default="")
    img = db.Column(db.String(255), default="")
    external_url = db.Column(db.String(500), default="")
    region = db.Column(db.String(60), default="")
    audience = db.Column(db.String(60), default="All")
    description = db.Column(db.Text, default="")
    list_order = db.Column(db.Integer, default=0)


class NewsItem(db.Model):
    __tablename__ = "news_items"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    title = db.Column(db.String(500), nullable=False)
    outlet = db.Column(db.String(160), default="")
    news_date = db.Column(db.String(60), default="")
    region = db.Column(db.String(60), default="")
    spokesperson = db.Column(db.String(160), default="")
    external_url = db.Column(db.String(500), default="")
    list_order = db.Column(db.Integer, default=0)


class Leader(db.Model):
    __tablename__ = "leaders"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    title = db.Column(db.String(200), default="")
    bio = db.Column(db.Text, default="")
    card_img = db.Column(db.String(255), default="")
    modal_img = db.Column(db.String(255), default="")
    linkedin = db.Column(db.String(300), default="")
    list_order = db.Column(db.Integer, default=0)


class Job(db.Model):
    __tablename__ = "jobs"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    department = db.Column(db.String(120), default="")
    location = db.Column(db.String(160), default="")
    employment_type = db.Column(db.String(60), default="")
    comp = db.Column(db.String(200), default="")
    team = db.Column(db.String(120), default="")
    work_style = db.Column(db.String(80), default="")
    external_url = db.Column(db.String(500), default="")
    list_order = db.Column(db.Integer, default=0)


class Partner(db.Model):
    __tablename__ = "partners"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    logo = db.Column(db.String(255), default="")
    section = db.Column(db.String(80), default="home")
    list_order = db.Column(db.Integer, default=0)


class Testimonial(db.Model):
    __tablename__ = "testimonials"
    id = db.Column(db.Integer, primary_key=True)
    quote = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(160), default="")
    role = db.Column(db.String(200), default="")
    list_order = db.Column(db.Integer, default=0)


class FaqItem(db.Model):
    __tablename__ = "faq_items"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(120), default="")
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, default="")
    list_order = db.Column(db.Integer, default=0)


class HeroSlide(db.Model):
    __tablename__ = "hero_slides"
    id = db.Column(db.Integer, primary_key=True)
    micro = db.Column(db.String(120), default="")
    title = db.Column(db.String(500), nullable=False)
    body = db.Column(db.Text, default="")
    img = db.Column(db.String(255), default="")
    link_href = db.Column(db.String(255), default="")
    link_label = db.Column(db.String(80), default="Read more")
    list_order = db.Column(db.Integer, default=0)


class StatCard(db.Model):
    __tablename__ = "stat_cards"
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(60), nullable=False)
    label = db.Column(db.String(200), default="")
    text = db.Column(db.Text, default="")
    list_order = db.Column(db.Integer, default=0)


class DemoRequest(db.Model):
    __tablename__ = "demo_requests"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), default="")
    last_name = db.Column(db.String(120), default="")
    email = db.Column(db.String(255), default="")
    phone = db.Column(db.String(60), default="")
    job_title = db.Column(db.String(160), default="")
    organization = db.Column(db.String(200), default="")
    organization_type = db.Column(db.String(80), default="")
    country = db.Column(db.String(120), default="")
    state = db.Column(db.String(120), default="")
    needs = db.Column(db.String(200), default="")
    message = db.Column(db.Text, default="")
    source = db.Column(db.String(80), default="Web Site")
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), default="")
    last_name = db.Column(db.String(120), default="")
    email = db.Column(db.String(255), default="")
    phone = db.Column(db.String(60), default="")
    job_title = db.Column(db.String(160), default="")
    organization = db.Column(db.String(200), default="")
    organization_type = db.Column(db.String(80), default="")
    country = db.Column(db.String(120), default="")
    needs = db.Column(db.String(200), default="")
    message = db.Column(db.Text, default="")
    source = db.Column(db.String(80), default="Contact Us")
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class NewsletterSubscriber(db.Model):
    __tablename__ = "newsletter_subscribers"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


# --------------------------------------------------------------------------
# Auth plumbing
# --------------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
              "or", "is", "it", "by", "with", "your", "you", "our"}


def tokenize(query: str) -> list[str]:
    return [t.lower() for t in re.split(r"\W+", query)
            if t.lower() not in STOP_WORDS and len(t) > 1]


def scored_resources(query: str, rows: list, fields=("title", "snippet", "intro", "body_text")):
    tokens = tokenize(query)
    if not tokens:
        return rows, []
    scored = []
    for item in rows:
        text = " ".join((getattr(item, f, "") or "").lower() for f in fields)
        score = sum(1 for t in tokens if t in text)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: -pair[0])
    return [item for _, item in scored], tokens


PER_PAGE = 15

# frozen bcrypt hash so the generated seed DB is byte-reproducible
FROZEN_BCRYPT_HASH = "$2b$12$T/eVPhrLWVlTL7m2NoFgHOzD.fRe7pOnCjunUlbzGm7SDo9krOCum"

ORG_TYPE_OPTIONS = ["Business", "Government", "Higher Ed", "K12", "EdTech"]
COUNTRY_OPTIONS = ["United States", "Canada", "United Kingdom", "Australia",
                   "Germany", "France", "Netherlands", "Spain", "Italy",
                   "Brazil", "Mexico", "Japan", "South Korea", "Singapore",
                   "India", "Other"]
US_STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California",
             "Colorado", "Connecticut", "Delaware", "District of Columbia",
             "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana",
             "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland",
             "Massachusetts", "Michigan", "Minnesota", "Mississippi",
             "Missouri", "Montana", "Nebraska", "Nevada",
             "New Hampshire", "New Jersey", "New Mexico", "New York",
             "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
             "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
             "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
             "Washington", "West Virginia", "Wisconsin", "Wyoming"]
NEEDS_OPTIONS = ["General Inquiry",
                 "I'm a student/parent/teacher needing support",
                 "I'm a teacher looking for product information",
                 "I want to connect with sales"]
HEARD_OPTIONS = ["Search engine", "Online ad", "Social media",
                 "AI (ChatGPT/Gemini)", "Event/Trade show", "From a peer",
                 "Other"]
JOB_TITLES = ["Teacher", "Administrator", "IT / Technologist",
              "Curriculum Designer", "Superintendent", "Registrar",
              "Corporate Trainer", "Other"]

# filter option lists, mirroring the exposed-filter checkboxes per hub
PRODUCT_FILTERS = ["Canvas", "Canvas Career", "Canvas Catalog", "Canvas Studio",
                   "Elevate Data Quality", "Elevate Standards Alignment",
                   "IgniteAI", "Impact", "Intelligent Insights", "LearnPlatform",
                   "Mastery Assessments", "Mastery Connect", "Mastery Item Bank",
                   "Parchment Award", "Parchment Pathways", "Parchment Services"]
ORG_FILTERS = ["All", "K-12", "Higher Education", "Community College",
               "Business", "Government", "Learning Companies",
               "Vocational Education", "Further Education", "Business Schools",
               "EdTech Providers", "Other"]
TOPIC_FILTERS = ["Analytics", "Artificial Intelligence", "Assessment",
                 "Canvascon", "Channel Partner", "Competency-Based Education",
                 "EdTech Management", "Equity & Accessibility", "Evidence",
                 "InstructureCast", "InstructureCon", "LMS",
                 "Online & Hybrid Learning", "Partner Integrations + LTIs",
                 "Personalized Learning", "Privacy & Security",
                 "Product Updates", "Professional Development", "Pro Tips",
                 "Services", "Student Engagement"]
EVENT_REGION_FILTERS = ["North America", "Asia–Pacific", "Latin America",
                        "Europe", "Africa", "Middle East"]


def parse_csv_params(name: str) -> list[str]:
    raw = request.args.getlist(name) + request.args.getlist(name + "[]")
    out = []
    for v in raw:
        out.extend([p for p in v.split(",") if p])
    return out


def filter_resources(rows, products, orgs, topics, query):
    if products:
        rows = [r for r in rows
                if any(p in r.product_list for p in products)]
    if orgs:
        rows = [r for r in rows
                if any(o in r.org_type_list for o in orgs)]
    if topics:
        rows = [r for r in rows
                if any(t in r.topic_list for t in topics)]
    if query:
        rows, _ = scored_resources(query, rows)
    return rows


def resource_query(rl_type: str):
    return (Resource.query.filter_by(type=rl_type)
            .order_by(Resource.list_order, Resource.id))


def img_for(rel: str) -> str:
    """Serve HF-managed images by site-relative path."""
    if not rel:
        return ""
    if rel.startswith("/static/"):
        return rel
    return "/static/images/" + rel.lstrip("/")


app.jinja_env.globals.update(
    HUBS=HUBS, TYPE_LABEL=TYPE_LABEL,
    PRODUCT_FILTERS=PRODUCT_FILTERS, ORG_FILTERS=ORG_FILTERS,
    TOPIC_FILTERS=TOPIC_FILTERS, EVENT_REGION_FILTERS=EVENT_REGION_FILTERS,
    ORG_TYPE_OPTIONS=ORG_TYPE_OPTIONS, COUNTRY_OPTIONS=COUNTRY_OPTIONS,
    US_STATES=US_STATES, NEEDS_OPTIONS=NEEDS_OPTIONS,
    HEARD_OPTIONS=HEARD_OPTIONS, JOB_TITLES=JOB_TITLES,
    MIRROR_REFERENCE_DATE=MIRROR_REFERENCE_DATE)


@app.template_filter("img")
def img_filter(rel):
    return img_for(rel)


def _render_rich(text: str) -> str:
    """Plain-text field -> escaped paragraphs (Markup so Jinja keeps the tags)."""
    from markupsafe import Markup, escape
    if not text:
        return Markup("")
    out = []
    for chunk in re.split(r"\n{2,}|(?<=[.!?])\s{2,}", (text or "").strip()):
        chunk = chunk.strip()
        if chunk:
            out.append("<p>%s</p>" % escape(chunk))
    return Markup("".join(out))


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


app.jinja_env.filters["render_rich"] = _render_rich
app.jinja_env.filters["slugify"] = _slugify


# --------------------------------------------------------------------------
# Forms
# --------------------------------------------------------------------------

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")


class RegisterForm(FlaskForm):
    display_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField("Confirm password",
                            validators=[DataRequired(),
                                        EqualTo("password", message="Passwords must match.")])
    job_title = StringField("Job title", validators=[Length(max=120)])
    organization = StringField("Organization", validators=[Length(max=160)])

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("An account with that email already exists.")


class ProfileForm(FlaskForm):
    display_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    job_title = StringField("Job title", validators=[Length(max=120)])
    organization = StringField("Organization", validators=[Length(max=160)])
    organization_type = SelectField("Organization type", choices=[("", "- Select -")] + [(v, v) for v in ORG_TYPE_OPTIONS], validators=[Optional()])
    country = SelectField("Country", choices=[("", "- Select -")] + [(v, v) for v in COUNTRY_OPTIONS], validators=[Optional()])
    state = SelectField("State", choices=[("", "- Select -")] + [(v, v) for v in US_STATES], validators=[Optional()])
    phone = StringField("Phone", validators=[Length(max=40)])


class DemoRequestForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=120)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[Optional(), Length(max=60)])
    job_title = StringField("Job title", validators=[Length(max=160)])
    organization = StringField("Organization", validators=[DataRequired(), Length(max=200)])
    organization_type = SelectField("Organization type",
                                    choices=[("", "- Select -")] + [(v, v) for v in ORG_TYPE_OPTIONS],
                                    validators=[Optional()])
    country = SelectField("Country", choices=[("", "- Select -")] + [(v, v) for v in COUNTRY_OPTIONS],
                          validators=[Optional()])
    state = SelectField("State", choices=[("", "- Select -")] + [(v, v) for v in US_STATES],
                        validators=[Optional()])
    needs = SelectField("Which best describes your needs",
                        choices=[("", "- Select -")] + [(v, v) for v in NEEDS_OPTIONS],
                        validators=[Optional()])
    message = TextAreaField("How can we help?", validators=[DataRequired(), Length(min=10)])
    heard = SelectField("How did you hear about us",
                       choices=[("", "- None -")] + [(v, v) for v in HEARD_OPTIONS],
                       validators=[Optional()])
    consent = BooleanField("Consent", validators=[DataRequired(message="Consent is required to submit the form.")])

    def validate_organization_type(self, field):
        if not field.data:
            raise ValidationError("This field is required.")

    def validate_needs(self, field):
        if not field.data:
            raise ValidationError("This field is required.")


class ContactForm(DemoRequestForm):
    source = "Contact Us"


# --------------------------------------------------------------------------
# Routes — static marketing pages
# --------------------------------------------------------------------------

@app.route("/_health")
def health():
    counts = {
        "resources": Resource.query.count(),
        "events": Event.query.count(),
        "news": NewsItem.query.count(),
        "leaders": Leader.query.count(),
        "jobs": Job.query.count(),
        "faq": FaqItem.query.count(),
    }
    return {"ok": all(counts.values()), "site": "instructure", "counts": counts}


@app.route("/")
def index():
    return render_template(
        "index.html",
        slides=HeroSlide.query.order_by(HeroSlide.list_order, HeroSlide.id).all(),
        stats=StatCard.query.order_by(StatCard.list_order, StatCard.id).all(),
        testimonials=Testimonial.query.order_by(Testimonial.list_order, Testimonial.id).all(),
        featured=resource_query("case_study").limit(3).all(),
        partners=Partner.query.filter_by(section="home")
                       .order_by(Partner.list_order, Partner.id).all(),
        resource_carousel=(
            resource_query("research_report").limit(1).all()
            + resource_query("case_study").limit(2).all()
            + resource_query("ebook").limit(2).all()))


@app.route("/canvas")
def canvas_page():
    return render_template("products/canvas.html")


@app.route("/mastery")
def mastery_page():
    return render_template("products/mastery.html")


@app.route("/parchment")
def parchment_page():
    return render_template("products/parchment.html")


@app.route("/k12")
def k12_page():
    return render_template("solutions/k12.html",
                           case_studies=resource_query("case_study").limit(3).all())


@app.route("/higher-education")
def higher_education_page():
    return render_template("solutions/higher_education.html",
                           case_studies=resource_query("case_study").offset(3).limit(3).all())


@app.route("/business")
def business_page():
    return render_template("solutions/business.html",
                           case_studies=resource_query("case_study").offset(6).limit(3).all())


@app.route("/about")
def about_page():
    return render_template("about/about.html",
                           leaders=Leader.query.order_by(Leader.list_order, Leader.id).limit(6).all())


@app.route("/about/leadership")
def leadership_page():
    return render_template("about/leadership.html",
                           leaders=Leader.query.order_by(Leader.list_order, Leader.id).all())


@app.route("/about/careers")
def careers_page():
    jobs = Job.query.order_by(Job.list_order, Job.id).all()
    departments = sorted({j.department for j in jobs if j.department})
    locations = sorted({j.location for j in jobs if j.location})
    employments = sorted({j.employment_type for j in jobs if j.employment_type})
    return render_template("about/careers.html", jobs=jobs,
                           departments=departments, locations=locations,
                           employments=employments)


@app.route("/partners")
def partners_page():
    return render_template("partners.html",
                           partners=Partner.query.filter_by(section="home")
                           .order_by(Partner.list_order, Partner.id).all())


@app.route("/community")
def community_page():
    return render_template("community.html")


@app.route("/support/canvas-support-faq")
def support_faq_page():
    cats: dict[str, list] = {}
    for item in FaqItem.query.order_by(FaqItem.list_order, FaqItem.id):
        cats.setdefault(item.category, []).append(item)
    return render_template("support_faq.html", categories=cats)


@app.route("/why-instructure")
def why_instructure_page():
    return render_template("why_instructure.html")


@app.route("/services")
def services_page():
    return render_template("services.html")


# --------------------------------------------------------------------------
# Routes — resource hubs
# --------------------------------------------------------------------------

HUB_BY_SEG = {seg: (label, rtype) for seg, label, rtype in HUBS}


@app.route("/resources")
def resources_hub():
    per_type = {}
    for seg, label, rtype in HUBS:
        per_type[seg] = resource_query(rtype).limit(3).all()
    return render_template("resources_hub.html", per_type=per_type)


@app.route("/resources/research")
def research_hub_alias():
    """Upstream serves the Research hub at /resources/research; alias it."""
    return redirect(url_for("resource_listing", seg="research-reports"))


@app.route("/resources/<seg>")
def resource_listing(seg):
    hub = HUB_BY_SEG.get(seg)
    if not hub:
        abort(404)
    label, rtype = hub
    rows = resource_query(rtype).all()
    products = parse_csv_params("product")
    orgs = parse_csv_params("org")
    topics = parse_csv_params("topic")
    query = request.args.get("hubs_search", "").strip()
    rows = filter_resources(rows, products, orgs, topics, query)
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    total = len(rows)
    page_rows = rows[(page - 1) * PER_PAGE: page * PER_PAGE]
    total_pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    return render_template(
        "resource_listing.html", seg=seg, label=label, rows=page_rows,
        total=total, page=page, total_pages=total_pages,
        products=products, orgs=orgs, topics=topics, query=query,
        active={"product": products, "org": orgs, "topic": topics})


DETAIL_SEGMENTS = {seg for seg, _, _ in HUBS} | {"webinar", "other"}


@app.route("/resources/<seg>/<slug>")
def resource_detail(seg, slug):
    if seg not in DETAIL_SEGMENTS:
        abort(404)
    res = Resource.query.filter_by(slug=slug).first_or_404()
    return render_template("resource_detail.html", res=res,
                           related=related_resources(res))


def related_resources(res: Resource, limit: int = 3):
    q = (Resource.query.filter(Resource.id != res.id)
         .filter(Resource.type == res.type))
    if res.topics:
        first_topic = res.topic_list[0]
        q = q.filter(Resource.topics.like(f"%{first_topic}%"))
    rows = q.order_by(Resource.list_order).limit(limit).all()
    if len(rows) < limit:
        extra = (Resource.query.filter(Resource.id != res.id)
                 .filter(Resource.type == res.type)
                 .order_by(Resource.list_order)
                 .limit(limit).all())
        for r in extra:
            if r not in rows:
                rows.append(r)
    return rows[:limit]


@app.route("/events/webinar/<slug>")
@app.route("/events/webinars/<slug>")
def event_webinar_detail(slug):
    res = Resource.query.filter_by(slug=slug).first_or_404()
    return render_template("resource_detail.html", res=res,
                           related=related_resources(res))


@app.route("/node/<int:node_id>")
def node_detail(node_id):
    res = Resource.query.filter_by(slug=str(node_id)).first_or_404()
    return render_template("resource_detail.html", res=res,
                           related=related_resources(res))


@app.route("/research/<slug>")
def research_detail(slug):
    res = Resource.query.filter_by(slug=slug).first_or_404()
    return render_template("resource_detail.html", res=res,
                           related=related_resources(res))


@app.route("/resources/<seg>/<slug>/download")
def resource_download(seg, slug):
    res = Resource.query.filter_by(slug=slug).first_or_404()
    form = DemoRequestForm(prefix="gate")
    return render_template("resource_download.html", res=res, form=form)


@app.route("/resources/<seg>/<slug>/download", methods=["POST"])
def resource_download_submit(seg, slug):
    res = Resource.query.filter_by(slug=slug).first_or_404()
    form = DemoRequestForm(prefix="gate")
    if form.validate_on_submit():
        row = DemoRequest(
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=(form.phone.data or "").strip(),
            job_title=(form.job_title.data or "").strip(),
            organization=form.organization.data.strip(),
            organization_type=form.organization_type.data,
            country=form.country.data,
            state=form.state.data,
            needs=form.needs.data,
            message=form.message.data.strip(),
            source=f"Download: {res.title}",
        )
        db.session.add(row)
        db.session.commit()
        flash("Thanks! Your download of “%s” is on its way to your inbox." % res.title,
              "success")
        return redirect(url_for("resource_download_done", seg=seg, slug=slug))
    return render_template("resource_download.html", res=res, form=form)


@app.route("/resources/<seg>/<slug>/download/sent")
def resource_download_done(seg, slug):
    res = Resource.query.filter_by(slug=slug).first_or_404()
    return render_template("resource_download_done.html", res=res)


# --------------------------------------------------------------------------
# Routes — news, press releases, events
# --------------------------------------------------------------------------

@app.route("/news")
def news_listing():
    rows = NewsItem.query.order_by(NewsItem.list_order, NewsItem.id)
    topic = request.args.get("topic", "").strip()
    region = request.args.get("region", "").strip()
    product = request.args.get("product", "").strip()
    query = request.args.get("hubs_search", "").strip()
    rows = [r for r in rows if (not topic or topic in (r.spokesperson or ""))]
    if region:
        rows = [r for r in rows if r.region == region]
    if query:
        rows, _ = scored_resources(query, rows, fields=("title", "outlet", "spokesperson"))
    return render_template("news_listing.html", rows=rows,
                           topic=topic, region=region, product=product, query=query)


@app.route("/news/public-relations")
def press_listing():
    rows = resource_query("press_release")
    query = request.args.get("hubs_search", "").strip()
    if query:
        rows, _ = scored_resources(query, rows, fields=("title", "snippet", "intro"))
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    rows = list(rows)
    total = len(rows)
    page_rows = rows[(page - 1) * PER_PAGE: page * PER_PAGE]
    total_pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    return render_template("press_listing.html", rows=page_rows, total=total,
                          page=page, total_pages=total_pages, query=query)


@app.route("/press-release/<slug>")
def press_detail(slug):
    res = Resource.query.filter_by(slug=slug).first_or_404()
    return render_template("press_detail.html", res=res,
                           recent=resource_query("press_release").limit(5).all())


@app.route("/events")
def events_listing():
    rows = Event.query.order_by(Event.list_order, Event.id).all()
    time_filter = request.args.get("time", "Upcoming")
    audience = request.args.get("audience", "").strip()
    event_type = request.args.get("event_type", "").strip()
    region = request.args.get("region", "").strip()
    if audience:
        rows = [r for r in rows if r.audience == audience]
    if event_type:
        rows = [r for r in rows if r.event_type == event_type]
    if region:
        rows = [r for r in rows if r.region == region]
    if time_filter == "Past":
        rows = []
    return render_template("events_listing.html", rows=rows,
                            time_filter=time_filter, audience=audience,
                            event_type=event_type, region=region)


@app.route("/listed-event/<slug>")
def listed_event_detail(slug):
    ev = Event.query.filter_by(slug=slug).first_or_404()
    webinars = resource_query("webinar").limit(3).all()
    return render_template("listed_event.html", ev=ev, webinars=webinars)


# --------------------------------------------------------------------------
# Routes — search
# --------------------------------------------------------------------------

@app.route("/search")
def search():
    query = (request.args.get("srch") or request.args.get("keys") or "").strip()
    results = []
    if query:
        for res, kind, date in search_rows(query):
            results.append({"item": res, "kind": kind, "date": date})
    return render_template("search.html", query=query, results=results)


def search_rows(query: str, limit: int = 40):
    out = []
    res_rows, _ = scored_resources(query, Resource.query.all())
    for r in res_rows[:limit]:
        out.append((r, r.type_label, r.publish_date or r.event_date))
    news_rows, _ = scored_resources(query, NewsItem.query.all(),
                                    fields=("title", "outlet", "spokesperson"))
    for n in news_rows[:10]:
        out.append((n, "In the News", n.news_date))
    job_rows, _ = scored_resources(query, Job.query.all(),
                                    fields=("title", "department", "location"))
    for j in job_rows[:10]:
        out.append((j, "Careers", ""))
    ev_rows, _ = scored_resources(query, Event.query.all(),
                                  fields=("title", "event_type", "region"))
    for e in ev_rows[:10]:
        out.append((e, "Events", e.event_date))
    return out


# --------------------------------------------------------------------------
# Routes — forms
# --------------------------------------------------------------------------

@app.route("/request-demo")
def request_demo():
    form = DemoRequestForm()
    return render_template("request_demo.html", form=form)


@app.route("/request-demo", methods=["POST"])
def request_demo_submit():
    form = DemoRequestForm()
    if form.validate_on_submit():
        row = DemoRequest(
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=(form.phone.data or "").strip(),
            job_title=(form.job_title.data or "").strip(),
            organization=form.organization.data.strip(),
            organization_type=form.organization_type.data,
            country=form.country.data,
            state=form.state.data,
            needs=form.needs.data,
            message=form.message.data.strip(),
            source="Web Site",
        )
        db.session.add(row)
        db.session.commit()
        flash("Thanks! An Instructure team member will reach out within one business day.",
              "success")
        return redirect(url_for("request_demo"))
    return render_template("request_demo.html", form=form)


@app.route("/contact-us")
def contact_us():
    form = ContactForm()
    return render_template("contact_us.html", form=form)


@app.route("/contact-us", methods=["POST"])
def contact_us_submit():
    form = ContactForm()
    if form.validate_on_submit():
        row = ContactMessage(
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=(form.phone.data or "").strip(),
            job_title=(form.job_title.data or "").strip(),
            organization=form.organization.data.strip(),
            organization_type=form.organization_type.data,
            country=form.country.data,
            needs=form.needs.data,
            message=form.message.data.strip(),
            source="Contact Us",
        )
        db.session.add(row)
        db.session.commit()
        flash("Thanks for reaching out! We'll be in touch shortly.", "success")
        return redirect(url_for("contact_us"))
    return render_template("contact_us.html", form=form)


# --------------------------------------------------------------------------
# Routes — auth + account
# --------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Signed in as %s." % user.display_name, "success")
            nxt = request.args.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            return redirect(url_for("account"))
        flash("We couldn't find an account with that email and password.", "error")
    return render_template("login.html", form=form)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.email.data.strip().lower().split("@")[0],
            email=form.email.data.strip().lower(),
            display_name=form.display_name.data.strip(),
            job_title=(form.job_title.data or "").strip(),
            organization=(form.organization.data or "").strip(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome to Instructure! Your account is ready.", "success")
        return redirect(url_for("account"))
    return render_template("register.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been signed out.", "success")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    saved = (SavedResource.query.filter_by(user_id=current_user.id)
             .order_by(SavedResource.created_at.desc(), SavedResource.id).all())
    regs = (WebinarRegistration.query.filter_by(user_id=current_user.id)
            .order_by(WebinarRegistration.created_at.desc(),
                      WebinarRegistration.id).all())
    form = ProfileForm(obj=current_user)
    return render_template("account.html", form=form, saved=saved, regs=regs)


@app.route("/account", methods=["POST"])
@login_required
def account_update():
    form = ProfileForm()
    if form.validate_on_submit():
        current_user.display_name = form.display_name.data.strip()
        current_user.job_title = (form.job_title.data or "").strip()
        current_user.organization = (form.organization.data or "").strip()
        current_user.organization_type = form.organization_type.data
        current_user.country = form.country.data
        current_user.state = form.state.data
        current_user.phone = (form.phone.data or "").strip()
        db.session.commit()
        flash("Your profile has been updated.", "success")
        return redirect(url_for("account"))
    saved = (SavedResource.query.filter_by(user_id=current_user.id)
             .order_by(SavedResource.created_at.desc(), SavedResource.id).all())
    regs = (WebinarRegistration.query.filter_by(user_id=current_user.id)
            .order_by(WebinarRegistration.created_at.desc(),
                      WebinarRegistration.id).all())
    return render_template("account.html", form=form, saved=saved, regs=regs)


@app.route("/account/saved")
@login_required
def account_saved():
    saved = (SavedResource.query.filter_by(user_id=current_user.id)
             .order_by(SavedResource.created_at.desc(), SavedResource.id).all())
    return render_template("account_saved.html", saved=saved)


@app.route("/account/saved/<slug>/remove", methods=["POST"])
@login_required
def account_saved_remove(slug):
    res = Resource.query.filter_by(slug=slug).first_or_404()
    row = SavedResource.query.filter_by(user_id=current_user.id,
                                        resource_id=res.id).first()
    if row:
        db.session.delete(row)
        db.session.commit()
        flash("Removed “%s” from your saved resources." % res.title, "success")
    return redirect(url_for("account_saved"))


@app.route("/resources/<seg>/<slug>/save", methods=["POST"])
def save_resource(seg, slug):
    res = Resource.query.filter_by(slug=slug).first_or_404()
    if not current_user.is_authenticated:
        flash("Sign in to save resources to your account.", "error")
        return redirect(url_for("login", next=res.href()))
    row = SavedResource.query.filter_by(user_id=current_user.id,
                                        resource_id=res.id).first()
    if row:
        flash("“%s” is already in your saved resources." % res.title, "success")
    else:
        db.session.add(SavedResource(user_id=current_user.id, resource_id=res.id))
        db.session.commit()
        flash("Saved “%s” to your account." % res.title, "success")
    return redirect(request.form.get("next") or res.href())


@app.route("/resources/<seg>/<slug>/register", methods=["POST"])
def register_webinar(seg, slug):
    res = Resource.query.filter_by(slug=slug).first_or_404()
    if res.type != "webinar":
        abort(404)
    if not current_user.is_authenticated:
        flash("Sign in to register for on-demand webinars.", "error")
        return redirect(url_for("login", next=res.href()))
    row = WebinarRegistration.query.filter_by(user_id=current_user.id,
                                              resource_id=res.id).first()
    if row:
        flash("You're already registered for “%s”." % res.title, "success")
    else:
        db.session.add(WebinarRegistration(user_id=current_user.id, resource_id=res.id))
        db.session.commit()
        flash("You're registered for “%s” — find it under your account." % res.title,
              "success")
    return redirect(res.href())


@app.route("/newsletter/subscribe", methods=["POST"])
def newsletter_subscribe():
    email = (request.form.get("email") or "").strip().lower()
    if not email or "@" not in email:
        flash("Please enter a valid email address.", "error")
        return redirect(request.form.get("next") or url_for("index"))
    if not NewsletterSubscriber.query.filter_by(email=email).first():
        db.session.add(NewsletterSubscriber(email=email))
        db.session.commit()
    flash("You're on the list! Watch your inbox for the latest from the learnosphere.",
          "success")
    return redirect(request.form.get("next") or url_for("index"))


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


# --------------------------------------------------------------------------
# Simple informational pages + alias redirects
# --------------------------------------------------------------------------

@app.route("/privacy-security")
def privacy_security():
    return render_template("privacy_security.html")


@app.route("/trust-center/legal")
def trust_center_legal():
    return render_template("privacy_security.html")


@app.route("/about/ai-perspectives")
def ai_perspectives():
    return render_template("ai_perspectives.html",
                           ai_rows=(Resource.query.filter(Resource.topics.like("%Artificial Intelligence%"))
                                    .order_by(Resource.list_order).limit(6).all()))


@app.route("/sitemap")
def sitemap():
    hubs = [(seg, label) for seg, label, _ in HUBS]
    return render_template("sitemap.html", hubs=hubs,
                           types=sorted(TYPE_LABEL.items(), key=lambda kv: kv[1]))


ALIASES = {
    "/canvas/request-demo": "request_demo",
    "/canvas/login": "login",
    "/canvas/canvas-career": "canvas_page",
    "/canvas/studio": "canvas_page",
    "/canvas/catalog": "canvas_page",
    "/mastery/assessments": "mastery_page",
    "/mastery/item-bank": "mastery_page",
    "/parchment/award": "parchment_page",
    "/parchment/pathways": "parchment_page",
    "/parchment/high-school-equivalency-credentialing": "parchment_page",
    "/products/parchment/services": "services_page",
    "/learnplatform": "resources_hub",
    "/impact": "resources_hub",
    "/intelligent-insights": "resources_hub",
    "/igniteai": "resources_hub",
    "/leadership-development": "services_page",
    "/is-your-lms-future-ready": "higher_education_page",
    "/parchment/parchment-digital-badges/login": "login",
}


for _alias_path, _endpoint in ALIASES.items():
    def _make_redirect(endpoint, name):
        def _redirect_alias():
            return redirect(url_for(endpoint))
        _redirect_alias.__name__ = name
        return _redirect_alias
    # The endpoint name is derived from the alias path itself: deriving it from
    # hash(path) made the name depend on PYTHONHASHSEED, and under the runtime's
    # randomized seeds two aliases of the same endpoint (e.g. /canvas/login and
    # /parchment/parchment-digital-badges/login) could collide and abort the
    # import with "View function mapping is overwriting an existing endpoint".
    app.add_url_rule(_alias_path, view_func=_make_redirect(
        _endpoint, "alias_" + re.sub(r"[^0-9a-zA-Z_]", "_", _alias_path)))


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


# --------------------------------------------------------------------------
# Bootstrap
# --------------------------------------------------------------------------

def seed_database() -> None:
    if Resource.query.count() > 0:
        return
    from seed_data import build_seed
    build_seed(db)


def seed_benchmark_users() -> None:
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    from seed_data import BENCHMARK_USERS
    from seed_data import seed_user_data
    for spec in BENCHMARK_USERS:
        user = User(
            username=spec["username"], email=spec["email"],
            display_name=spec["display_name"], job_title=spec.get("job_title", ""),
            organization=spec.get("organization", ""),
            organization_type=spec.get("organization_type", ""),
            country=spec.get("country", ""), state=spec.get("state", ""),
            phone=spec.get("phone", ""),
            password_hash=FROZEN_BCRYPT_HASH)
        db.session.add(user)
    db.session.commit()
    seed_user_data(db, BENCHMARK_USERS, "TestPass123!")


# The runtime DB lives under instance/; make sure the directory exists before
# SQLAlchemy opens the file (a clean checkout or `rm -rf instance` would otherwise
# fail the import-time bootstrap with 'unable to open database file').
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 40089))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
