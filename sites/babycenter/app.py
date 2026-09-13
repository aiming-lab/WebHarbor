"""BabyCenter mirror — pregnancy and baby development workflows."""
from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from functools import wraps
from urllib.parse import urlsplit

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFERENCE_DATE = date(2026, 5, 29)

# Every factual sentence on this site is a verbatim excerpt from an openly
# licensed source article, built by tools/build_corpus.py and carried with the
# exact upstream revision it came from. See source_data/README.md.
CORPUS_PATH = os.path.join(BASE_DIR, "source_data", "corpus.json")

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-babycenter-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "BABYCENTER_DATABASE_URI",
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'babycenter.db')}",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

STOP_WORDS = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "baby", "pregnancy"}

ARTICLE_IMAGES = {
    "viability-and-preterm-birth": "ultrasound.jpg",
    "how-births-are-classified": "expecting-baby.jpg",
    "what-prenatal-care-covers": "hero-pregnancy.jpg",
    "prenatal-screening-explained": "ultrasound.jpg",
    "first-second-third-trimester-screen": "ultrasound.jpg",
    "amniocentesis": "ultrasound.jpg",
    "chorionic-villus-sampling": "ultrasound.jpg",
    "the-three-trimesters": "expecting-baby.jpg",
    "fetal-growth-rate": "expecting-baby.jpg",
    "fetal-cognitive-development": "ultrasound.jpg",
    "breastfeeding-benefits": "breastfeeding.jpg",
    "infant-sleep-approaches": "baby-sleep.jpg",
}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    baby_birthdate = db.Column(db.Date)
    parenting_stage = db.Column(db.String(80), default="Pregnancy")


class PregnancyWeek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, unique=True, nullable=False)
    stage = db.Column(db.String(40), nullable=False)
    headline = db.Column(db.String(180), nullable=False)
    baby_summary = db.Column(db.Text, nullable=False)
    body_summary = db.Column(db.Text, nullable=False)
    checklist = db.Column(db.Text, nullable=False)
    attribution = db.Column(db.Text, nullable=False)


class BabyMonth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, unique=True, nullable=False)
    headline = db.Column(db.String(180), nullable=False)
    # Named after what the source article documents per age. Any of the three
    # may be absent for an age the source does not cover; the page says so
    # rather than filling the gap.
    physical = db.Column(db.Text)
    motor = db.Column(db.Text)
    communication = db.Column(db.Text)
    attribution = db.Column(db.Text, nullable=False)


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    trimester = db.Column(db.String(40), nullable=False)
    read_minutes = db.Column(db.Integer, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)
    attribution = db.Column(db.Text, nullable=False)


class CommunityPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    club = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    replies = db.Column(db.Integer, nullable=False)
    last_active = db.Column(db.Date, nullable=False)
    body = db.Column(db.Text, nullable=False)


class SavedItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    item_type = db.Column(db.String(40), nullable=False)
    item_slug = db.Column(db.String(120), nullable=False)
    note = db.Column(db.String(240), default="")


def current_user() -> User | None:
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


@app.context_processor
def inject_common():
    return {
        "current_user": current_user(),
        "reference_date": REFERENCE_DATE,
        "article_image": lambda slug: ARTICLE_IMAGES.get(slug, "mother-newborn.jpg"),
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Sign in to personalize your tracker.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def tokenize(query: str) -> list[str]:
    return [
        token
        for token in re.split(r"\W+", query.lower())
        if len(token) > 1 and token not in STOP_WORDS
    ]


def scored_search(query: str, rows, fields: list[str]):
    parts = tokenize(query)
    if not parts:
        return list(rows)
    scored = []
    for row in rows:
        text = " ".join(str(getattr(row, field, "") or "") for field in fields).lower()
        score = sum(1 for part in parts if part in text)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], getattr(item[1], "week", getattr(item[1], "month", 0))))
    return [row for _, row in scored]


def safe_next_path(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return None
    if parsed.path.startswith("//"):
        return None
    return value


def safe_referrer_path(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"", "http", "https"}:
        return None
    if parsed.netloc and parsed.netloc != request.host:
        return None
    if not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return None
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


def sourced_weeks() -> list[int]:
    return [row.week for row in PregnancyWeek.query.order_by(PregnancyWeek.week).all()]


def pregnancy_week_for_due_date(due_date: date) -> int:
    """Gestational week for a due date, snapped to the nearest sourced page.

    Not every week has an upstream fact behind it, so the tracker points at the
    closest week that does instead of inventing a page.
    """
    days_until_due = (due_date - REFERENCE_DATE).days
    week = 40 - (days_until_due // 7)
    available = sourced_weeks()
    if not available:
        return max(4, min(42, week))
    week = max(available[0], min(available[-1], week))
    return min(available, key=lambda w: (abs(w - week), w))


def baby_month_for_birthdate(birthdate: date | None) -> int | None:
    """Age in months, snapped to the nearest sourced month page."""
    if not birthdate:
        return None
    months = max(0, (REFERENCE_DATE - birthdate).days // 30)
    available = [row.month for row in BabyMonth.query.order_by(BabyMonth.month).all()]
    if not available:
        return min(24, months)
    months = max(available[0], min(available[-1], months))
    return min(available, key=lambda m: (abs(m - months), m))


@app.route("/")
def index():
    user = current_user()
    week = PregnancyWeek.query.filter_by(week=18).first()
    baby_month = BabyMonth.query.filter_by(month=6).first()
    if user:
        week = PregnancyWeek.query.filter_by(week=pregnancy_week_for_due_date(user.due_date)).first()
        month = baby_month_for_birthdate(user.baby_birthdate)
        if month is not None:
            baby_month = BabyMonth.query.filter_by(month=month).first()
    articles = Article.query.order_by(Article.id.desc()).limit(4).all()
    posts = CommunityPost.query.order_by(CommunityPost.last_active.desc()).limit(4).all()
    preferred_weeks = (4, 8, 12, 18, 24, 30, 37, 42)
    week_nav = [
        PregnancyWeek.query.filter_by(week=week_number).first()
        for week_number in preferred_weeks
    ]
    return render_template(
        "index.html",
        week=week,
        baby_month=baby_month,
        articles=articles,
        posts=posts,
        week_nav=[row for row in week_nav if row],
    )


@app.route("/pregnancy/week-by-week")
def week_index():
    trimester = request.args.get("trimester", "")
    rows = PregnancyWeek.query.order_by(PregnancyWeek.week).all()
    if trimester:
        low, high = {"first": (4, 12), "second": (13, 27), "third": (28, 42)}[trimester]
        rows = [row for row in rows if low <= row.week <= high]
    return render_template("weeks.html", weeks=rows, trimester=trimester)


@app.route("/pregnancy/week-<int:week>")
def week_detail(week):
    week_row = PregnancyWeek.query.filter_by(week=week).first_or_404()
    articles = [a for a in Article.query.all() if a.trimester == trimester_for_week(week)][:4]
    return render_template("week_detail.html", week=week_row, articles=articles)


@app.route("/baby/month-by-month")
def month_index():
    rows = BabyMonth.query.order_by(BabyMonth.month).all()
    return render_template("months.html", months=rows)


@app.route("/baby/month-<int:month>")
def month_detail(month):
    row = BabyMonth.query.filter_by(month=month).first_or_404()
    return render_template("month_detail.html", month=row)


@app.route("/due-date-calculator", methods=["GET", "POST"])
def due_date_calculator():
    result = None
    if request.method == "POST":
        last_period = request.form.get("last_period", "")
        try:
            cycle = int(request.form.get("cycle", "28") or 28)
            if not 20 <= cycle <= 45:
                raise ValueError("cycle length")
            lmp = date.fromisoformat(last_period)
            due = lmp + timedelta(days=280 + (cycle - 28))
            result = {"due": due, "week": pregnancy_week_for_due_date(due)}
        except ValueError:
            flash("Enter a valid date and a cycle length between 20 and 45 days.", "error")
    return render_template("due_date.html", result=result)


@app.route("/articles")
def articles():
    category = request.args.get("category", "")
    trimester = request.args.get("trimester", "")
    rows = Article.query.order_by(Article.title).all()
    if category:
        rows = [article for article in rows if article.category == category]
    if trimester:
        rows = [article for article in rows if article.trimester == trimester]
    categories = [row[0] for row in db.session.query(Article.category).distinct().order_by(Article.category)]
    return render_template("articles.html", articles=rows, categories=categories, category=category, trimester=trimester)


@app.route("/articles/<slug>")
def article_detail(slug):
    article = Article.query.filter_by(slug=slug).first_or_404()
    return render_template("article_detail.html", article=article)


@app.route("/community")
def community():
    club = request.args.get("club", "")
    rows = CommunityPost.query.order_by(CommunityPost.last_active.desc()).all()
    if club:
        rows = [post for post in rows if post.club == club]
    clubs = [row[0] for row in db.session.query(CommunityPost.club).distinct().order_by(CommunityPost.club)]
    return render_template("community.html", posts=rows, clubs=clubs, club=club)


@app.route("/community/<slug>")
def community_detail(slug):
    post = CommunityPost.query.filter_by(slug=slug).first_or_404()
    return render_template("community_detail.html", post=post)


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    article_results = scored_search(query, Article.query.all(), ["title", "category", "summary", "body"])[:8] if query else []
    week_results = scored_search(query, PregnancyWeek.query.all(), ["headline", "stage", "baby_summary", "body_summary", "checklist"])[:8] if query else []
    month_results = scored_search(query, BabyMonth.query.all(), ["headline", "physical", "motor", "communication"])[:8] if query else []
    post_results = scored_search(query, CommunityPost.query.all(), ["title", "club", "body"])[:8] if query else []
    return render_template("search.html", query=query, article_results=article_results, week_results=week_results, month_results=month_results, post_results=post_results)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            flash(f"Welcome back, {user.display_name}.", "success")
            return redirect(safe_next_path(request.args.get("next")) or url_for("account"))
        flash("Email or password did not match.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        due_date_value = request.form.get("due_date", "")
        errors = []
        if not 2 <= len(display_name) <= 120:
            errors.append("Enter a display name between 2 and 120 characters.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Use a password with at least 8 characters.")
        try:
            due_date = date.fromisoformat(due_date_value)
        except ValueError:
            due_date = None
            errors.append("Enter a valid due date.")
        if User.query.filter_by(email=email).first():
            errors.append("An account already uses that email address.")
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("register.html"), 400

        username_base = re.sub(r"[^a-z0-9]+", "_", email.split("@", 1)[0]).strip("_") or "member"
        username = username_base
        suffix = 2
        while User.query.filter_by(username=username).first():
            username = f"{username_base}_{suffix}"
            suffix += 1
        user = User(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=generate_password_hash(password),
            due_date=due_date,
            parenting_stage="Pregnancy",
        )
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        flash("Your BabyCenter profile is ready.", "success")
        return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Signed out.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    user = current_user()
    week = PregnancyWeek.query.filter_by(week=pregnancy_week_for_due_date(user.due_date)).first()
    month_num = baby_month_for_birthdate(user.baby_birthdate)
    month = BabyMonth.query.filter_by(month=month_num).first() if month_num is not None else None
    saved = SavedItem.query.filter_by(user_id=user.id).all()
    for item in saved:
        if item.item_type == "article":
            target = Article.query.filter_by(slug=item.item_slug).first()
            item.display_title = target.title if target else item.item_slug
        elif item.item_type == "post":
            target = CommunityPost.query.filter_by(slug=item.item_slug).first()
            item.display_title = target.title if target else item.item_slug
        elif item.item_type == "week":
            item.display_title = f"Pregnancy week {item.item_slug}"
        else:
            item.display_title = f"Baby month {item.item_slug}"
    return render_template("account.html", user=user, week=week, month=month, saved=saved)


@app.route("/account/tracker", methods=["POST"])
@login_required
def update_tracker():
    user = current_user()
    try:
        parenting_stage = request.form.get("parenting_stage", user.parenting_stage)
        if parenting_stage not in {"Pregnancy", "Planning for birth", "New baby", "Baby"}:
            raise ValueError("parenting stage")
        due_date = date.fromisoformat(request.form.get("due_date", str(user.due_date)))
        birthdate = request.form.get("baby_birthdate", "")
        parsed_birthdate = date.fromisoformat(birthdate) if birthdate else None
        if parsed_birthdate and parsed_birthdate > REFERENCE_DATE:
            raise ValueError("future birthdate")
        user.parenting_stage = parenting_stage
        user.due_date = due_date
        user.baby_birthdate = parsed_birthdate
        db.session.commit()
        flash("Tracker updated.", "success")
    except ValueError:
        db.session.rollback()
        flash("Use valid dates in YYYY-MM-DD format.", "error")
    return redirect(url_for("account"))


@app.route("/account/profile", methods=["POST"])
@login_required
def update_profile():
    display_name = request.form.get("display_name", "").strip()
    if not 2 <= len(display_name) <= 120:
        flash("Enter a display name between 2 and 120 characters.", "error")
        return redirect(url_for("account"))
    current_user().display_name = display_name
    db.session.commit()
    flash("Profile updated.", "success")
    return redirect(url_for("account"))


def saved_target_exists(item_type: str, slug: str) -> bool:
    if item_type == "article":
        return Article.query.filter_by(slug=slug).first() is not None
    if item_type == "post":
        return CommunityPost.query.filter_by(slug=slug).first() is not None
    if not slug.lstrip("-").isdigit():
        return False
    if item_type == "week":
        return PregnancyWeek.query.filter_by(week=int(slug)).first() is not None
    return BabyMonth.query.filter_by(month=int(slug)).first() is not None


@app.route("/save/<item_type>/<slug>", methods=["POST"])
@login_required
def save_item(item_type, slug):
    if item_type not in {"article", "week", "month", "post"}:
        abort(404)
    if not saved_target_exists(item_type, slug):
        # Without this the table happily stores saves for pages that do not
        # exist, which lets a wrong-but-plausible slug look like a real save.
        abort(404)
    existing = SavedItem.query.filter_by(user_id=current_user().id, item_type=item_type, item_slug=slug).first()
    if not existing:
        db.session.add(SavedItem(user_id=current_user().id, item_type=item_type, item_slug=slug, note=request.form.get("note", "")))
        db.session.commit()
        flash("Saved to your BabyCenter account.", "success")
    return redirect(safe_referrer_path(request.referrer) or url_for("account"))


@app.route("/saved/<int:item_id>/remove", methods=["POST"])
@login_required
def remove_saved_item(item_id):
    item = SavedItem.query.filter_by(id=item_id, user_id=current_user().id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Removed from saved items.", "success")
    return redirect(url_for("account"))


@app.route("/_health")
def health():
    return {"ok": True, "site": "babycenter"}


def trimester_for_week(week: int) -> str:
    if week <= 12:
        return "First trimester"
    if week <= 27:
        return "Second trimester"
    return "Third trimester"


def load_corpus() -> dict:
    """Load the sourced content corpus, failing loudly if it is absent.

    The corpus is generated by tools/build_corpus.py from the tracked source
    articles under source_data/. Booting without it would mean serving an empty
    site, so this raises instead.
    """
    if not os.path.exists(CORPUS_PATH):
        raise RuntimeError(
            f"content corpus missing at {CORPUS_PATH}; "
            "run tools/fetch_sources.py then tools/build_corpus.py"
        )
    with open(CORPUS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def format_attribution(citations: list[dict]) -> str:
    """One human-readable credit line per page, as CC BY-SA requires."""
    parts = []
    for c in citations:
        bit = c["source_title"]
        if c.get("section"):
            bit += f" \u00a7 {c['section']}"
        parts.append(f"{bit} (revision {c['revision_id']}) {c['permanent_url']}")
    return " | ".join(parts)


def seed_database():
    if PregnancyWeek.query.count() > 0:
        return
    corpus = load_corpus()

    for row in corpus["weeks"]:
        db.session.add(PregnancyWeek(
            week=row["week"],
            stage=row["stage"],
            headline=row["headline"],
            baby_summary=row["baby_summary"],
            body_summary=row["body_summary"],
            checklist=row["checklist"],
            attribution=format_attribution(row["citations"]),
        ))

    for row in corpus["months"]:
        db.session.add(BabyMonth(
            month=row["month"],
            headline=row["headline"],
            physical=row["physical"],
            motor=row["motor"],
            communication=row["communication"],
            attribution=format_attribution(row["citations"]),
        ))

    for row in corpus["articles"]:
        db.session.add(Article(
            slug=row["slug"],
            title=row["title"],
            category=row["category"],
            trimester=row["trimester"],
            read_minutes=row["read_minutes"],
            summary=row["summary"],
            body=row["body"],
            attribution=format_attribution(row["citations"]),
        ))

    # Community threads are benchmark state, not mirrored facts: they exist so
    # there is something to browse, search and reply-count against. They are
    # labelled as sample content in the UI and carry no external claims.
    posts = [
        ("june-2026-due-date-roll-call", "June 2026 Birth Club",
         "Roll call: who else is due in June?", "MayaB", 48, 1,
         "Share your due date, symptoms, and first appointment plans."),
        ("second-trimester-energy-tips", "Second Trimester Club",
         "Anyone else suddenly nesting?", "NinaR", 31, 2,
         "I have more energy and want realistic weekend projects."),
        ("newborn-night-wakings", "Newborn Sleep",
         "How are you handling night wakings?", "SamK", 64, 0,
         "Looking for gentle routines that still feel manageable."),
        ("starting-solids-allergens", "Starting Solids",
         "Introducing peanut and egg this week", "PriyaC", 22, 3,
         "What order did your pediatrician suggest?"),
        ("hospital-bag-minimalists", "Labor and Birth",
         "Minimal hospital bag list", "DevonL", 39, 4,
         "What did you actually use during a short stay?"),
        ("car-seat-install-check", "Gear and Registry",
         "Car seat install check before 36 weeks", "AnaP", 18, 5,
         "Our local fire station appointment is next week."),
    ]
    for slug, club, title, author, replies, days_ago, body in posts:
        db.session.add(CommunityPost(
            slug=slug, club=club, title=title, author=author, replies=replies,
            last_active=REFERENCE_DATE - timedelta(days=days_ago), body=body))

    db.session.commit()


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    users = [
        ("alice_j", "alice.j@test.com", "Alice Johnson", REFERENCE_DATE + timedelta(days=22 * 7), None, "Pregnancy"),
        ("bob_c", "bob.c@test.com", "Bob Chen", REFERENCE_DATE + timedelta(days=8 * 7), None, "Pregnancy"),
        ("carol_d", "carol.d@test.com", "Carol Davis", REFERENCE_DATE - timedelta(days=30), REFERENCE_DATE - timedelta(days=90), "New baby"),
        ("david_k", "david.k@test.com", "David Kim", REFERENCE_DATE - timedelta(days=210), REFERENCE_DATE - timedelta(days=210), "Baby"),
    ]
    for username, email, display_name, due_date, birthdate, stage in users:
        user = User(username=username, email=email, display_name=display_name, due_date=due_date, baby_birthdate=birthdate, parenting_stage=stage, password_hash=generate_password_hash("TestPass123!"))
        db.session.add(user)
        db.session.flush()
        db.session.add(SavedItem(user_id=user.id, item_type="article", item_slug="how-births-are-classified", note="Benchmark saved article"))
        db.session.add(SavedItem(user_id=user.id, item_type="week", item_slug=str(pregnancy_week_for_due_date(due_date)), note="Current pregnancy week"))
    db.session.commit()


with app.app_context():
    os.makedirs(app.instance_path, exist_ok=True)
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
