"""CA.gov mirror — California State Portal.

Offline mirror of https://www.ca.gov/ for the WebHarbor benchmark. All runtime
content (departments, services, FAQs, topics, news, officials) is real ca.gov
data read from the bundled SQLite seed; page copy follows the upstream
California Design System layout. External "Launch service" / "Department
website" buttons keep their real upstream URLs, exactly like the live site.
"""
import json
import os
import re
from datetime import datetime

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__, instance_path=INSTANCE_DIR)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{INSTANCE_DIR}/california_gov.db"
app.config["SECRET_KEY"] = "webharbor-california-gov-dev-key"

db = SQLAlchemy(app)

# The upstream pages show copy with no wall-clock values; the seed pins this
# reference so seeded rows are deterministic and never touch the real clock.
MIRROR_REFERENCE_DATE = datetime(2026, 9, 22, 12, 0, 0)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Department(db.Model):
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    abbr = db.Column(db.String(64))
    description = db.Column(db.Text)
    phone = db.Column(db.String(32))
    phone_digits = db.Column(db.String(16))
    website = db.Column(db.String(512))
    more_contact = db.Column(db.String(512))
    socials_json = db.Column(db.Text)
    apps_json = db.Column(db.Text)
    logo = db.Column(db.String(255))
    last_updated = db.Column(db.String(32))
    popular_rank = db.Column(db.Integer)  # order in /departments/ landing
    directory_rank = db.Column(db.Integer)  # row order in the upstream /departments/all/ DOM
    list_name = db.Column(db.String(255))  # inverted name on /departments/list/

    @property
    def socials(self):
        return json.loads(self.socials_json or "[]")

    @property
    def short_name(self):
        """Name without the trailing parenthesized abbreviation (the form the
        upstream service pages use for their department link)."""
        return re.sub(r"\s*\([^)]*\)\s*$", "", self.name).strip()

    @property
    def apps(self):
        return json.loads(self.apps_json or "[]")

    @property
    def topic_rows(self):
        return (Topic.query.join(DepartmentTopic, DepartmentTopic.topic_id == Topic.id)
                .filter(DepartmentTopic.department_id == self.id)
                .order_by(DepartmentTopic.position).all())

    @property
    def topics(self):
        return [t.name for t in self.topic_rows]

    @property
    def faq_rows(self):
        return Faq.query.filter_by(department_id=self.id).order_by(Faq.position).all()


class Service(db.Model):
    __tablename__ = "services"
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    phone = db.Column(db.String(32))
    phone_digits = db.Column(db.String(16))
    launch_url = db.Column(db.String(512))
    contact_url = db.Column(db.String(512))
    dept_website = db.Column(db.String(512))
    image = db.Column(db.String(255))
    last_updated = db.Column(db.String(32))
    keywords_json = db.Column(db.Text)  # upstream service-page Keywords links
    directory_rank = db.Column(db.Integer)  # row order in the upstream /services/all/ DOM
    dept_rank = db.Column(db.Integer)      # order on the upstream department page
    popular_rank = db.Column(db.Integer)   # order in /services/ landing
    homepage_rank = db.Column(db.Integer)  # order in homepage pills
    homepage_label = db.Column(db.String(128))  # upstream pill label
    popular_label = db.Column(db.String(128))  # upstream /services/ landing label
    department = db.relationship("Department", backref="service_rows")

    @property
    def faq_rows(self):
        return Faq.query.filter_by(service_id=self.id).order_by(Faq.position).all()

    @property
    def topic_rows(self):
        return (Topic.query.join(ServiceTopic, ServiceTopic.topic_id == Topic.id)
                .filter(ServiceTopic.service_id == self.id)
                .order_by(ServiceTopic.position).all())

    @property
    def topics(self):
        return [t.name for t in self.topic_rows]

    @property
    def keywords(self):
        return json.loads(self.keywords_json or "[]")

    @property
    def siblings(self):
        """Upstream "Related services": the same department's other services."""
        return (Service.query.filter(Service.department_id == self.department_id,
                                      Service.id != self.id)
                .order_by(Service.name).all())


class Faq(db.Model):
    __tablename__ = "faqs"
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"))
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    position = db.Column(db.Integer, nullable=False, default=0)


class Topic(db.Model):
    __tablename__ = "topics"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), nullable=False, unique=True)
    name = db.Column(db.String(128), nullable=False)
    landing_description = db.Column(db.Text)
    description = db.Column(db.Text)
    description_html = db.Column(db.Text)  # upstream lead markup (may hold lists)
    lineart = db.Column(db.String(255))
    position = db.Column(db.Integer, nullable=False, default=0)

    @property
    def service_count(self):
        return ServiceTopic.query.filter_by(topic_id=self.id).count()

    @property
    def department_count(self):
        return DepartmentTopic.query.filter_by(topic_id=self.id).count()


class ServiceTopic(db.Model):
    __tablename__ = "service_topics"
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)


class DepartmentTopic(db.Model):
    __tablename__ = "department_topics"
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)


class TopicCard(db.Model):
    __tablename__ = "topic_cards"
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False)
    department_id = db.Column(db.Integer)
    service_id = db.Column(db.Integer)
    title = db.Column(db.String(255), nullable=False)
    blurb = db.Column(db.Text)
    image = db.Column(db.String(255))
    image_alt = db.Column(db.Text)
    position = db.Column(db.Integer, nullable=False, default=0)


class NewsItem(db.Model):
    __tablename__ = "news_items"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    display_date = db.Column(db.String(64), nullable=False)
    source_url = db.Column(db.String(512), nullable=False)
    excerpt = db.Column(db.Text)
    position = db.Column(db.Integer, nullable=False, default=0)


class Feedback(db.Model):
    __tablename__ = "feedback"
    id = db.Column(db.Integer, primary_key=True)
    page_path = db.Column(db.String(512), nullable=False)
    helpful = db.Column(db.String(8), nullable=False)
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=MIRROR_REFERENCE_DATE)


class HomePageStat(db.Model):
    __tablename__ = "homepage_stats"
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(32), nullable=False)
    value_suffix = db.Column(db.String(16), nullable=False, default="")
    unit = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)


class Official(db.Model):
    __tablename__ = "officials"
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(128))
    seal = db.Column(db.String(255), nullable=False)
    seal_alt = db.Column(db.Text)
    link_label = db.Column(db.String(128), nullable=False)
    link_url = db.Column(db.String(512), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)


# ---------------------------------------------------------------------------
# Search (scored token overlap, never strict AND)
# ---------------------------------------------------------------------------

STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
              "or", "is", "it", "by", "with", "your", "my", "how", "do", "i"}


def tokenize(query):
    return [t for t in re.split(r"\W+", (query or "").lower())
            if t and t not in STOP_WORDS and len(t) > 1]


def score_item(tokens, *fields):
    text = " ".join(f or "" for f in fields).lower()
    if not tokens:
        return 0
    words = re.split(r"\W+", text)
    score = 0
    for t in tokens:
        if t in words:
            score += 1
        else:
            # word-prefix match ("unemployment" matches "unemployed")
            if any(word.startswith(t) for word in words if len(word) > len(t)):
                score += 0.5
    return score



def rank_by_score(items, q, *fields):
    tokens = tokenize(q)
    if not tokens:
        return list(items)
    scored = [(score_item(tokens, *[getattr(item, f, "") or "" for f in fields]), item)
              for item in items]
    scored = [(s, i) for s, i in scored if s > 0]
    scored.sort(key=lambda pair: -pair[0])
    return [item for _, item in scored]


def run_search(query, limit=50):
    """Scored search across services, departments and topics."""
    tokens = tokenize(query)
    if not tokens:
        return [], 0
    results = []
    for service in Service.query.all():
        dept = service.department
        score = score_item(tokens, service.name, service.description,
                           dept.name if dept else "", service.phone or "")
        if score > 0:
            results.append({"kind": "service", "score": score, "item": service})
    for dept in Department.query.all():
        score = score_item(tokens, dept.name, dept.description, dept.abbr or "",
                           dept.phone or "")
        if score > 0:
            results.append({"kind": "department", "score": score, "item": dept})
    for topic in Topic.query.all():
        score = score_item(tokens, topic.name, topic.description)
        if score > 0:
            results.append({"kind": "topic", "score": score, "item": topic})
    results.sort(key=lambda r: -r["score"])
    total = len(results)
    return results[:limit], total


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    return {"nav_topics": Topic.query.order_by(Topic.position).all()}


def service_url(service):
    return url_for("service_detail", dept_id=service.department_id, service_id=service.id)


def department_url(department):
    return url_for("department_detail", dept_id=department.id)


def topic_url(topic):
    return url_for("topic_detail", slug=topic.slug)


app.jinja_env.globals.update(
    service_url=service_url, department_url=department_url, topic_url=topic_url)


def list_page_order(items, key):
    """Upstream list pages group by first letter (A-Z), keeping the CMS
    directory order within each letter group."""
    import itertools

    def sort_key(item):
        rank = getattr(item, "directory_rank")
        return (key(item)[0].upper(), 10 ** 9 if rank is None else rank)
    return sorted(items, key=sort_key)


TOPIC_CHECKBOX_ORDER = [
    "Assistance and social programs", "Businesses", "DMV/Auto", "Education",
    "Health and wellness", "Housing and real estate", "Immigration",
    "Jobs and unemployment", "Personal records", "Safety and emergencies",
    "State info and laws", "Taxes", "Travel and recreation",
]


def directory_filter_topics(model, join_table, filter_col):
    """Topic checkboxes for the directory pages: upstream order, the CMS topic
    number for the checkbox id (chkTopic<N>, same N as the lineart file), and
    the row counts over the full set. Disaster recovery is not listed."""
    counts = topic_counts_for(model, join_table, filter_col)
    topics = (Topic.query.order_by(Topic.position).all())
    out = []
    for t in topics:
        if t.name not in TOPIC_CHECKBOX_ORDER:
            continue
        m = re.search(r"topic(\d+)-lineart", t.lineart or "")
        out.append({"name": t.name, "num": int(m.group(1)) if m else 0,
                    "count": counts.get(t.name, 0)})
    return out


def topic_counts_for(model, join_table, filter_col):
    counts = {}
    for topic in Topic.query.all():
        counts[topic.name] = 0
    rows = db.session.query(join_table.topic_id, db.func.count(filter_col)).group_by(
        join_table.topic_id).all()
    for topic_id, count in rows:
        topic = Topic.query.get(topic_id)
        if topic:
            counts[topic.name] = count
    return counts


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    spotlight = NewsItem.query.order_by(NewsItem.position).limit(3).all()
    popular = (Service.query.filter(Service.homepage_rank.isnot(None))
               .order_by(Service.homepage_rank).all())
    officials = Official.query.order_by(Official.position).all()
    stats = HomePageStat.query.order_by(HomePageStat.position).all()
    return render_template("index.html", spotlight=spotlight, popular_services=popular,
                           officials=officials, stats=stats)


@app.route("/services/")
def services_landing():
    popular = (Service.query.filter(Service.popular_rank.isnot(None))
               .order_by(Service.popular_rank).all())
    topics = Topic.query.order_by(Topic.position).all()
    return render_template("services_landing.html", popular_services=popular, topics=topics)


@app.route("/services/all/")
def services_all():
    services = Service.query.order_by(Service.directory_rank).all()
    filter_topics = directory_filter_topics(Service, ServiceTopic, ServiceTopic.service_id)
    return render_template("services_all.html", services=services,
                           filter_topics=filter_topics)


# The upstream /services/list/ page omits this CMS-hidden service (present in
# the All services directory, absent from the alphabetical Services list).
SERVICES_LIST_HIDDEN = {1274}


@app.route("/services/list/")
def services_list():
    services = (Service.query.order_by(Service.directory_rank).all())
    services = [s for s in services if s.id not in SERVICES_LIST_HIDDEN]
    services = list_page_order(services, lambda s: s.name)
    filter_topics = directory_filter_topics(Service, ServiceTopic, ServiceTopic.service_id)
    return render_template("services_list.html", services=services,
                           filter_topics=filter_topics)


@app.route("/departments/")
def departments_landing():
    popular = (Department.query.filter(Department.popular_rank.isnot(None))
               .order_by(Department.popular_rank).all())
    return render_template("departments_landing.html", popular_departments=popular)


@app.route("/departments/all/")
def departments_all():
    departments = Department.query.order_by(Department.directory_rank).all()
    filter_topics = directory_filter_topics(Department, DepartmentTopic, DepartmentTopic.department_id)
    return render_template("departments_all.html", departments=departments,
                           filter_topics=filter_topics)


@app.route("/departments/list/")
def departments_list():
    departments = Department.query.order_by(Department.directory_rank).all()
    departments = list_page_order(departments, lambda d: d.list_name or d.name)
    filter_topics = directory_filter_topics(Department, DepartmentTopic, DepartmentTopic.department_id)
    return render_template("departments_list.html", departments=departments,
                           filter_topics=filter_topics)


@app.route("/departments/<int:dept_id>/")
def department_detail(dept_id):
    dept = Department.query.get_or_404(dept_id)
    services = (Service.query.filter_by(department_id=dept_id)
                .order_by(Service.dept_rank).all())
    return render_template("department_detail.html", dept=dept, services=services)


@app.route("/departments/<int:dept_id>/services/<int:service_id>/")
def service_detail(dept_id, service_id):
    service = Service.query.filter_by(id=service_id, department_id=dept_id).first_or_404()
    return render_template("service_detail.html", service=service)


@app.route("/topics/")
def topics_landing():
    topics = Topic.query.order_by(Topic.position).all()
    return render_template("topics_landing.html", topics=topics)


@app.route("/topics/<slug>/")
def topic_detail(slug):
    topic = Topic.query.filter_by(slug=slug).first_or_404()
    if slug == "disaster-recovery":
        # This topic keeps its own upstream page design (Do this first /
        # Disaster help), reproduced from the captured ca.gov page.
        return render_template("topic_disaster_recovery.html", topic=topic)
    cards = TopicCard.query.filter_by(topic_id=topic.id).order_by(TopicCard.position).all()
    topic_services = (Service.query.join(ServiceTopic, ServiceTopic.service_id == Service.id)
                      .filter(ServiceTopic.topic_id == topic.id)
                      .order_by(Service.directory_rank).all())
    # Topic-page checkboxes refine within the topic: the label counts are the
    # overlaps with the topic's own services, in the upstream checkbox order.
    overlap = []
    for t in Topic.query.order_by(Topic.position).all():
        if t.name not in TOPIC_CHECKBOX_ORDER:
            continue
        if t.id == topic.id:
            continue
        m = re.search(r"topic(\d+)-lineart", t.lineart or "")
        overlap.append({"name": t.name, "num": int(m.group(1)) if m else 0,
                        "count": sum(1 for s in topic_services if t.name in s.topics)})
    return render_template("topic_detail.html", topic=topic, cards=cards,
                          topic_services=topic_services, filter_topics=overlap)


@app.route("/search")
@app.route("/search/")
def search():
    q = (request.args.get("q") or "").strip()
    results, total = run_search(q)
    return render_template("search.html", q=q, results=results, total=total)


@app.route("/about-california/")
def about_california():
    return render_template("about_california.html")


@app.route("/support/")
def support():
    return render_template("support.html")


@app.route("/support/technical-help/")
def technical_help():
    return render_template("technical_help.html")


@app.route("/contact/")
def contact():
    return render_template("contact.html")


@app.route("/translate/")
def translate():
    return render_template("translate.html")


@app.route("/about/sitemap/")
def sitemap():
    return render_template("sitemap.html")


@app.route("/sitemap/")
def sitemap_redirect():
    # Upstream answers /sitemap/ with a 301 to /about/sitemap/.
    return redirect("/about/sitemap/", code=301)


@app.route("/about/about-this-website/")
def about_this_website():
    return render_template("about_this_website.html")


@app.route("/legal/<page>/")
def legal(page):
    if page not in {"conditions-of-use", "privacy-policy", "accessibility"}:
        abort(404)
    return render_template(f"legal_{page.replace('-', '_')}.html")


# Campaign / help pages reproduced from their upstream ca.gov pages.
# Upstream sub-pages that the mirror does not carry stay external links
# (same policy as Launch service / Department website buttons).
@app.route("/LAfires/")
def lafires():
    return render_template("lafires.html")


@app.route("/gasfacts/")
def gasfacts():
    return render_template("gasfacts.html")


@app.route("/immigration/")
def immigration():
    return render_template("immigration.html")


@app.route("/support/maternal-health-resources.html")
def maternal_health_resources():
    return render_template("maternal_health.html")


@app.route("/website-accessibility-certification.html")
def accessibility_certification():
    return render_template("website_accessibility_certification.html")


@app.route("/feedback/send", methods=["POST"])
def feedback_send():
    payload = request.get_json(silent=True) or request.form or {}
    helpful = "yes" if str(payload.get("helpful", "")).lower() == "yes" else "no"
    comments = str(payload.get("comments") or "")[:2000]
    page_path = str(payload.get("url") or request.referrer or "/")[:512]
    entry = Feedback(page_path=page_path, helpful=helpful, comments=comments,
                     created_at=MIRROR_REFERENCE_DATE)
    db.session.add(entry)
    db.session.commit()
    return jsonify({"message": "Thank you for your feedback!"})


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.route("/_health")
def health():
    return {
        "ok": True,
        "site": "california_gov",
        "departments": Department.query.count(),
        "services": Service.query.count(),
        "faqs": Faq.query.count(),
        "topics": Topic.query.count(),
        "topic_cards": TopicCard.query.count(),
        "news": NewsItem.query.count(),
        "feedback": Feedback.query.count(),
    }


with app.app_context():
    db.create_all()
    from seed_data import seed_database

    seed_database()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
