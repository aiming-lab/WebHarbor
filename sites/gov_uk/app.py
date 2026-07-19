"""GOV.UK mirror — Flask app.

Mirrors the structure of www.gov.uk:
  Topic            = top-level browse category ("Money and tax", "Visas and immigration", ...)
  Subtopic         = second-level browse heading under a Topic
  GuidanceArticle  = a single guidance/news/policy page (the leaf content)
  Department       = a government organisation (HMRC, DfE, ...)
  Announcement     = press release / news story published by a Department

Content here is *synthesized* in the spirit of GOV.UK guidance pages —
no upstream copy is included. Tone and structure approximate the real
site so an agent that navigates GOV.UK works against this mirror too.
"""
import os
from datetime import datetime, date
from pathlib import Path

from flask import (
    Flask, render_template, request, jsonify,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

BASE_DIR = Path(__file__).parent
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
              .order_by(Announcement.published_at.desc())
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
def article_detail(slug):
    article = GuidanceArticle.query.filter_by(slug=slug).first_or_404()
    related = (GuidanceArticle.query
               .filter(GuidanceArticle.subtopic_id == article.subtopic_id,
                       GuidanceArticle.id != article.id)
               .limit(5).all())
    paragraphs = [p for p in (article.body or "").split("\n\n") if p.strip()]
    return render_template(
        "article.html",
        article=article,
        related=related,
        paragraphs=paragraphs,
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
                          .order_by(Announcement.published_at.desc())
                          .limit(10).all())
    return render_template(
        "organisation.html",
        dept=dept,
        articles=articles,
        announcements=announcements_list,
    )


@app.route("/government/announcements")
def announcements_index():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 15
    q = Announcement.query.order_by(Announcement.published_at.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "announcements.html",
        items=items, page=page, pages=pages, total=total,
    )


@app.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    articles = []
    found_announcements = []
    departments = []
    if q:
        like = f"%{q}%"
        articles = (GuidanceArticle.query
                    .filter(or_(GuidanceArticle.title.ilike(like),
                                GuidanceArticle.summary.ilike(like),
                                GuidanceArticle.body.ilike(like)))
                    .order_by(GuidanceArticle.last_updated.desc())
                    .limit(30).all())
        found_announcements = (Announcement.query
                               .filter(or_(Announcement.title.ilike(like),
                                           Announcement.summary.ilike(like)))
                               .order_by(Announcement.published_at.desc())
                               .limit(15).all())
        departments = (Department.query
                       .filter(or_(Department.name.ilike(like),
                                   Department.description.ilike(like)))
                       .limit(10).all())
    return render_template(
        "search.html",
        q=q,
        articles=articles,
        announcements=found_announcements,
        departments=departments,
        total=len(articles) + len(found_announcements) + len(departments),
    )


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
