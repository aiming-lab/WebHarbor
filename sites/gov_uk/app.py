"""GOV.UK mirror — Flask app.

Mirrors the structure of www.gov.uk:
  Topic            = top-level browse category ("Money and tax", "Visas and immigration", ...)
  Subtopic         = second-level browse heading under a Topic
  GuidanceArticle  = a single guidance/news/policy page (the leaf content)
  Department       = a government organisation (HMRC, DfE, ...)
  Announcement     = press release / news story published by a Department

Expanded guidance uses authored summaries of official GOV.UK content, with
historical rates pinned to 1 April 2025. Organisation profiles and news remain
illustrative benchmark fixtures. All runtime content lives in SQLite.
The reference date is displayed in the site banner.
"""
import os
import sys
from datetime import datetime, date
from pathlib import Path

from flask import (
    Flask, render_template, request, jsonify, abort, url_for,
)
from flask_sqlalchemy import SQLAlchemy
from search_index import ranked

BASE_DIR = Path(__file__).resolve().parent

# Seed functions import models from app; standalone startup must share this module.
if __name__ == "__main__":
    sys.modules["app"] = sys.modules[__name__]
DB_DIR = BASE_DIR / "instance"
DB_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "gov-uk-mirror-dev-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_DIR / 'gov_uk.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# Mirror clock pin — GOV.UK guidance pages carry "updated 3 March 2025"
# stamps and a handful of date-relative copy ("Self Assessment deadline
# next January", "latest press releases"). Anchor 'now' so those resolve
# to the same data every run.
MIRROR_REFERENCE_DATE = datetime(2025, 4, 1, 9, 0, 0)


def mirror_now() -> datetime:
    return MIRROR_REFERENCE_DATE


# ─── Models ──────────────────────────────────────────────────────────────

class Topic(db.Model):
    __tablename__ = "topics"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    sort_order = db.Column(db.Integer, default=100)

    subtopics = db.relationship(
        "Subtopic", backref="topic", cascade="all, delete-orphan",
        order_by="Subtopic.sort_order",
    )

    @property
    def article_count(self):
        return GuidanceArticle.query.filter_by(topic_id=self.id).count()


class Subtopic(db.Model):
    __tablename__ = "subtopics"
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False, index=True)
    slug = db.Column(db.String(80), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    sort_order = db.Column(db.Integer, default=100)

    articles = db.relationship(
        "GuidanceArticle", backref="subtopic", cascade="all, delete-orphan",
        order_by="GuidanceArticle.title",
    )

    __table_args__ = (
        db.UniqueConstraint("topic_id", "slug", name="uq_subtopic_per_topic"),
    )


class Department(db.Model):
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    abbreviation = db.Column(db.String(20), default="")
    kind = db.Column(db.String(60), default="Ministerial department")
    description = db.Column(db.Text, default="")
    minister = db.Column(db.String(160), default="")
    permanent_secretary = db.Column(db.String(160), default="")
    employees = db.Column(db.Integer, default=0)
    established = db.Column(db.String(40), default="")
    website = db.Column(db.String(200), default="")

    announcements = db.relationship(
        "Announcement", backref="department", cascade="all, delete-orphan",
        order_by="Announcement.published_at.desc()",
    )


class GuidanceArticle(db.Model):
    __tablename__ = "guidance_articles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    summary = db.Column(db.Text, default="")
    body = db.Column(db.Text, default="")  # paragraphs joined with \n\n
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), index=True)
    subtopic_id = db.Column(db.Integer, db.ForeignKey("subtopics.id"), index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), index=True)
    kind = db.Column(db.String(40), default="guidance")  # guidance|form|service|policy
    audience = db.Column(db.String(80), default="Public")
    last_updated = db.Column(db.Date, default=date.today)
    first_published = db.Column(db.Date, default=date.today)

    department = db.relationship("Department", backref="articles")
    sections = db.relationship("GuidanceSection", order_by="GuidanceSection.sort_order", cascade="all, delete-orphan", back_populates="article")


class GuidanceSection(db.Model):
    """Ordered guide parts or headings, compiled into the shipped seed."""
    __tablename__ = "guidance_sections"
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("guidance_articles.id"), nullable=False)
    slug = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(240), nullable=False)
    body = db.Column(db.Text, nullable=False)  # trusted, locally authored HTML
    sort_order = db.Column(db.Integer, nullable=False)
    multipart = db.Column(db.Boolean, nullable=False, default=True)
    article = db.relationship("GuidanceArticle", back_populates="sections")
    __table_args__ = (db.UniqueConstraint("article_id", "slug"),)


class Announcement(db.Model):
    __tablename__ = "announcements"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    summary = db.Column(db.Text, default="")
    body = db.Column(db.Text, default="")
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), index=True)
    kind = db.Column(db.String(40), default="press_release")  # press_release|news_story|speech
    published_at = db.Column(db.DateTime, default=mirror_now)


# ─── Routes ──────────────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    return {
        "mirror_now": mirror_now(),
        "all_topics": Topic.query.order_by(Topic.sort_order, Topic.name).all(),
    }


@app.route("/")
def index():
    topics = Topic.query.order_by(Topic.sort_order, Topic.name).all()
    latest = (Announcement.query
              .order_by(Announcement.published_at.desc(), Announcement.id.desc())
              .limit(5).all())
    departments_count = Department.query.count()
    articles_count = GuidanceArticle.query.count()
    return render_template(
        "index.html",
        topics=topics,
        latest=latest,
        departments_count=departments_count,
        articles_count=articles_count,
    )


@app.route("/browse")
def browse():
    topics = Topic.query.order_by(Topic.sort_order, Topic.name).all()
    return render_template("browse.html", topics=topics)


@app.route("/browse/<topic_slug>")
def topic_page(topic_slug):
    topic = Topic.query.filter_by(slug=topic_slug).first_or_404()
    return render_template("topic.html", topic=topic)


@app.route("/browse/<topic_slug>/<subtopic_slug>")
def subtopic_page(topic_slug, subtopic_slug):
    topic = Topic.query.filter_by(slug=topic_slug).first_or_404()
    subtopic = Subtopic.query.filter_by(
        topic_id=topic.id, slug=subtopic_slug,
    ).first_or_404()
    return render_template("subtopic.html", topic=topic, subtopic=subtopic)


@app.route("/guidance/<slug>")
@app.route("/guidance/<slug>/<part_slug>")
def article_detail(slug, part_slug=None):
    article = GuidanceArticle.query.filter_by(slug=slug).first_or_404()
    related = (GuidanceArticle.query
               .filter(GuidanceArticle.subtopic_id == article.subtopic_id,
                       GuidanceArticle.id != article.id)
               .limit(5).all())
    sections = article.sections
    multipart = bool(sections and sections[0].multipart)
    current = next((section for section in sections if section.slug == part_slug), None) if part_slug else (sections[0] if multipart else None)
    if part_slug and (not multipart or current is None):
        abort(404)
    position = sections.index(current) if current else -1
    paragraphs = [p for p in (article.body or "").split("\n\n") if p.strip()]
    return render_template(
        "article.html",
        article=article,
        related=related,
        paragraphs=paragraphs, sections=sections, multipart=multipart, current=current,
        previous=sections[position-1] if position > 0 else None,
        following=sections[position+1] if multipart and position+1 < len(sections) else None,
    )


@app.route("/government/organisations")
def organisations():
    by_kind: dict = {}
    for d in Department.query.order_by(Department.name).all():
        by_kind.setdefault(d.kind, []).append(d)
    return render_template("organisations.html", by_kind=by_kind)


@app.route("/government/organisations/<slug>")
def organisation_detail(slug):
    dept = Department.query.filter_by(slug=slug).first_or_404()
    articles = (GuidanceArticle.query
                .filter_by(department_id=dept.id)
                .order_by(GuidanceArticle.last_updated.desc())
                .limit(20).all())
    announcements_list = (Announcement.query
                          .filter_by(department_id=dept.id)
                          .order_by(Announcement.published_at.desc(), Announcement.id.desc())
                          .limit(10).all())
    return render_template(
        "organisation.html",
        dept=dept,
        articles=articles,
        announcements=announcements_list,
    )


@app.route("/government/organisations/<slug>/about")
def organisation_about(slug):
    dept = Department.query.filter_by(slug=slug).first_or_404()
    return render_template("organisation_about.html", dept=dept)


@app.route("/government/announcements")
def announcements_index():
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        abort(400, description="Page must be a positive integer.")
    if page < 1:
        abort(400, description="Page must be a positive integer.")
    per_page = 15
    q = Announcement.query.order_by(Announcement.published_at.desc(), Announcement.id.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)
    if page > pages:
        abort(404)
    return render_template(
        "announcements.html",
        items=items, page=page, pages=pages, total=total,
    )


@app.route("/government/news/<slug>")
def announcement_detail(slug):
    announcement = Announcement.query.filter_by(slug=slug).first_or_404()
    related = GuidanceArticle.query.filter_by(department_id=announcement.department_id).order_by(GuidanceArticle.title).limit(10).all()
    return render_template("announcement.html", announcement=announcement, related=related)


@app.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    kind = request.args.get("type", "")
    department = request.args.get("department", "")
    sort = request.args.get("order", "relevance")
    kinds = {"guidance": "Guidance", "service": "Services", "news": "News and communications", "organisation": "Organisations"}
    departments = Department.query.order_by(Department.name).all()
    if kind not in ("", *kinds) or sort not in ("relevance", "updated"):
        abort(400)
    if department and department not in {d.slug for d in departments}:
        abort(400)
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        abort(400)
    if page < 1:
        abort(400)
    records = []
    for a in GuidanceArticle.query.order_by(GuidanceArticle.id).all():
        records.append(dict(title=a.title, summary=a.summary, body=a.body,
            url=url_for("article_detail", slug=a.slug), kind="service" if a.kind == "service" else "guidance",
            department=a.department.slug, publisher=a.department.name, updated=a.last_updated))
    for a in Announcement.query.order_by(Announcement.id).all():
        records.append(dict(title=a.title, summary=a.summary, body=a.body,
            url=url_for("announcement_detail", slug=a.slug), kind="news", department=a.department.slug,
            publisher=a.department.name, updated=a.published_at.date()))
    for d in departments:
        records.append(dict(title=d.name, summary=d.description, body=d.abbreviation,
            url=url_for("organisation_detail", slug=d.slug), kind="organisation", department=d.slug,
            publisher=d.name, updated=mirror_now().date()))
    from types import SimpleNamespace
    records = [SimpleNamespace(**r) for r in records]
    records = ranked(records, q, ("title", "summary", "body")) if q else records
    counts = {key: sum(r.kind == key and (not department or r.department == department) for r in records) for key in kinds}
    records = [r for r in records if (not kind or r.kind == kind) and (not department or r.department == department)]
    if sort == "updated":
        records.sort(key=lambda r: r.updated, reverse=True)
    total = len(records)
    pages = max(1, (total + 9) // 10)
    if page > pages:
        abort(404)
    def page_url(number):
        return url_for("search", q=q, type=kind, department=department, order=sort, page=number)
    return render_template("search.html", q=q, kind=kind, kinds=kinds, counts=counts,
        departments=departments, department=department, sort=sort, total=total,
        results=records[(page-1)*10:page*10], page=page, pages=pages, page_url=page_url)


@app.route("/_health")
def health():
    return jsonify({
        "ok": True, "site": "gov_uk",
        "topics": Topic.query.count(),
        "articles": GuidanceArticle.query.count(),
        "departments": Department.query.count(),
        "announcements": Announcement.query.count(),
    })


# ─── Boot ────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()
    from seed_data import seed_database
    seed_database(db)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
