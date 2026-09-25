"""Ohio.gov mirror — SQLAlchemy models.

Split from app.py so seed_data.py can import the models without a circular
import (importing app.py from seed_data would re-run the app bootstrap and
double-seed the database).
"""
import json
from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

# The upstream pages show copy with no wall-clock values; the seed pins this
# reference so seeded rows are deterministic and never touch the real clock.
MIRROR_REFERENCE_DATE = datetime(2026, 9, 17, 12, 0, 0)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(128))
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    phone = db.Column(db.String(32))
    address_line1 = db.Column(db.String(255))
    city = db.Column(db.String(96))
    state = db.Column(db.String(32), default="Ohio")
    zip = db.Column(db.String(16))
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


# Canonical social-network names for the State Directory. The scraped data
# snapshot stores each link as {label, href} (label = "Medical Board on X");
# the directory template consumes {url, net}. The network is detected from the
# link's host first (labels vary: "on Youtube", "Attorney General YouTube",
# "Treasurer's YouTube", ...) and falls back to the label's trailing token,
# normalized for the scraped casing variants (Youtube -> YouTube,
# "Linked In" -> LinkedIn) so every entry renders its brand icon instead of
# degrading to the generic fa-link.
_NETWORK_DOMAINS = (
    ("x.com", "X"),
    ("twitter.com", "X"),
    ("facebook.com", "Facebook"),
    ("youtube.com", "YouTube"),
    ("youtu.be", "YouTube"),
    ("linkedin.com", "LinkedIn"),
    ("instagram.com", "Instagram"),
    ("flickr.com", "Flickr"),
    ("vimeo.com", "Vimeo"),
    ("pinterest.com", "Pinterest"),
)
_NETWORK_ALIASES = {"Youtube": "YouTube", "Linked In": "LinkedIn"}


class Agency(db.Model):
    __tablename__ = "agencies"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    url = db.Column(db.String(512))
    contact_method = db.Column(db.String(64))
    contact_url = db.Column(db.String(512))
    socials_json = db.Column(db.Text)

    @property
    def socials(self):
        """Return the scraped links as {url, net} dicts with canonical network
        names, matching what the State Directory template renders."""
        out = []
        for s in json.loads(self.socials_json or "[]"):
            href = s.get("href") or ""
            net = ""
            low = href.lower()
            for domain, canon in _NETWORK_DOMAINS:
                if domain in low:
                    net = canon
                    break
            if not net:
                label = (s.get("label") or "").strip()
                if " on " in label:
                    label = label.rsplit(" on ", 1)[-1].strip()
                net = _NETWORK_ALIASES.get(label, label)
            out.append({"url": href, "net": net})
        return out


class TopicHub(db.Model):
    __tablename__ = "topic_hubs"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False)  # full path e.g. residents/topic-hubs/top-services
    title = db.Column(db.String(255), nullable=False)
    audience = db.Column(db.String(32))
    parent_title = db.Column(db.String(255))
    description = db.Column(db.Text)


class Resource(db.Model):
    __tablename__ = "resources"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    audience = db.Column(db.String(32))
    summary = db.Column(db.Text)
    body_html = db.Column(db.Text)
    body_text = db.Column(db.Text)
    launch_url = db.Column(db.String(512))
    published = db.Column(db.String(64))
    related_agencies_json = db.Column(db.Text)
    image = db.Column(db.String(512))
    search_summary = db.Column(db.Text)
    search_date = db.Column(db.String(64))
    categories_json = db.Column(db.Text)

    @property
    def related_agencies(self):
        return json.loads(self.related_agencies_json or "[]")

    @property
    def categories(self):
        return json.loads(self.categories_json or "[]")

    @property
    def path(self):
        return f"/{self.audience}/resources/{self.slug}"


class NewsArticle(db.Model):
    __tablename__ = "news_articles"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(512), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    published = db.Column(db.String(64))
    source = db.Column(db.String(255))
    body_html = db.Column(db.Text)
    image = db.Column(db.String(512))
    summary = db.Column(db.Text)
    position = db.Column(db.Integer)

    @property
    def path(self):
        return f"/news-and-events/all-news/{self.slug}"


class License(db.Model):
    __tablename__ = "licenses"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    url = db.Column(db.String(512))
    agency = db.Column(db.String(255))
    agency_url = db.Column(db.String(512))
    contact_label = db.Column(db.String(128))
    contact_url = db.Column(db.String(512))


class PhoneEntry(db.Model):
    __tablename__ = "phone_entries"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(32))
    agency = db.Column(db.String(255))


class FAQCategory(db.Model):
    __tablename__ = "faq_categories"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(128), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    image = db.Column(db.String(512))


class FAQ(db.Model):
    __tablename__ = "faqs"
    id = db.Column(db.Integer, primary_key=True)
    category_slug = db.Column(db.String(128), nullable=False)
    position = db.Column(db.Integer)
    question = db.Column(db.Text, nullable=False)
    answer_html = db.Column(db.Text)


class SavedResource(db.Model):
    __tablename__ = "saved_resources"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    resource_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class AlertItem(db.Model):
    __tablename__ = "alert_items"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body_html = db.Column(db.Text)
    severity = db.Column(db.String(32), default="information")
    published = db.Column(db.String(64))
    position = db.Column(db.Integer)


class AlertSubscription(db.Model):
    __tablename__ = "alert_subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    email = db.Column(db.String(255), nullable=False)
    alert_type = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class TravelGuideRequest(db.Model):
    __tablename__ = "travel_guide_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    address_line1 = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(96), nullable=False)
    state = db.Column(db.String(32), nullable=False)
    zip = db.Column(db.String(16), nullable=False)
    format = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class ScamReport(db.Model):
    __tablename__ = "scam_reports"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    phone = db.Column(db.String(32))
    scam_type = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.String(32))
    occurred_on = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class AssistantQuery(db.Model):
    __tablename__ = "assistant_queries"
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATE)


class SiteContent(db.Model):
    """Captured landing content, materialized at build time."""
    __tablename__ = 'site_content'
    name = db.Column(db.String(80), primary_key=True)
    payload = db.Column(db.Text, nullable=False)
