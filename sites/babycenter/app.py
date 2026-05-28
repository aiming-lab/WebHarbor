"""BabyCenter mirror — pregnancy and baby development workflows."""
from __future__ import annotations

import os
import re
from datetime import date, timedelta
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFERENCE_DATE = date(2026, 5, 29)

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-babycenter-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'babycenter.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

STOP_WORDS = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "baby", "pregnancy"}


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
    baby_size = db.Column(db.String(80), nullable=False)
    headline = db.Column(db.String(180), nullable=False)
    baby_summary = db.Column(db.Text, nullable=False)
    body_summary = db.Column(db.Text, nullable=False)
    checklist = db.Column(db.Text, nullable=False)


class BabyMonth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, unique=True, nullable=False)
    headline = db.Column(db.String(180), nullable=False)
    milestones = db.Column(db.Text, nullable=False)
    feeding = db.Column(db.Text, nullable=False)
    sleep = db.Column(db.Text, nullable=False)


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    trimester = db.Column(db.String(40), nullable=False)
    read_minutes = db.Column(db.Integer, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)


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
    return {"current_user": current_user(), "reference_date": REFERENCE_DATE}


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


def pregnancy_week_for_due_date(due_date: date) -> int:
    days_until_due = (due_date - REFERENCE_DATE).days
    week = 40 - (days_until_due // 7)
    return max(4, min(40, week))


def baby_month_for_birthdate(birthdate: date | None) -> int | None:
    if not birthdate:
        return None
    days = (REFERENCE_DATE - birthdate).days
    return max(0, min(24, days // 30))


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
    return render_template("index.html", week=week, baby_month=baby_month, articles=articles, posts=posts)


@app.route("/pregnancy/week-by-week")
def week_index():
    trimester = request.args.get("trimester", "")
    rows = PregnancyWeek.query.order_by(PregnancyWeek.week).all()
    if trimester:
        low, high = {"first": (4, 13), "second": (14, 27), "third": (28, 40)}[trimester]
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
        cycle = int(request.form.get("cycle", "28") or 28)
        try:
            lmp = date.fromisoformat(last_period)
            due = lmp + timedelta(days=280 + (cycle - 28))
            result = {"due": due, "week": pregnancy_week_for_due_date(due)}
        except ValueError:
            flash("Enter a valid last period date.", "error")
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
    week_results = scored_search(query, PregnancyWeek.query.all(), ["headline", "baby_size", "baby_summary", "body_summary", "checklist"])[:8] if query else []
    month_results = scored_search(query, BabyMonth.query.all(), ["headline", "milestones", "feeding", "sleep"])[:8] if query else []
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
            return redirect(request.args.get("next") or url_for("account"))
        flash("Email or password did not match.", "error")
    return render_template("login.html")


@app.route("/logout")
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
    return render_template("account.html", user=user, week=week, month=month, saved=saved)


@app.route("/account/tracker", methods=["POST"])
@login_required
def update_tracker():
    user = current_user()
    user.parenting_stage = request.form.get("parenting_stage", user.parenting_stage)
    try:
        user.due_date = date.fromisoformat(request.form.get("due_date", str(user.due_date)))
        birthdate = request.form.get("baby_birthdate", "")
        user.baby_birthdate = date.fromisoformat(birthdate) if birthdate else None
        db.session.commit()
        flash("Tracker updated.", "success")
    except ValueError:
        flash("Use valid dates in YYYY-MM-DD format.", "error")
    return redirect(url_for("account"))


@app.route("/save/<item_type>/<slug>", methods=["POST"])
@login_required
def save_item(item_type, slug):
    if item_type not in {"article", "week", "month", "post"}:
        flash("Unsupported save type.", "error")
        return redirect(url_for("index"))
    existing = SavedItem.query.filter_by(user_id=current_user().id, item_type=item_type, item_slug=slug).first()
    if not existing:
        db.session.add(SavedItem(user_id=current_user().id, item_type=item_type, item_slug=slug, note=request.form.get("note", "")))
        db.session.commit()
        flash("Saved to your BabyCenter account.", "success")
    return redirect(request.referrer or url_for("account"))


@app.route("/illustration/<kind>/<slug>.svg")
def illustration(kind, slug):
    hue = abs(hash(kind + slug)) % 360
    label = slug.replace("-", " ").title()
    icon = "♡" if kind == "baby" else "✓"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 480" role="img" aria-label="{label}">
<rect width="720" height="480" fill="hsl({hue}, 64%, 95%)"/>
<circle cx="150" cy="110" r="170" fill="hsl({hue}, 68%, 62%)" opacity=".24"/>
<circle cx="580" cy="390" r="210" fill="hsl({(hue + 62) % 360}, 68%, 52%)" opacity=".18"/>
<rect x="185" y="120" width="350" height="240" rx="42" fill="white" opacity=".9"/>
<text x="360" y="238" text-anchor="middle" font-family="Arial, sans-serif" font-size="86" font-weight="800" fill="hsl({hue}, 54%, 38%)">{icon}</text>
<text x="360" y="304" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" font-weight="700" fill="#243047">{label}</text>
</svg>"""
    return app.response_class(svg, mimetype="image/svg+xml")


@app.route("/_health")
def health():
    return {"ok": True, "site": "babycenter"}


def trimester_for_week(week: int) -> str:
    if week <= 13:
        return "First trimester"
    if week <= 27:
        return "Second trimester"
    return "Third trimester"


def seed_database():
    if PregnancyWeek.query.count() > 0:
        return
    sizes = [
        "poppy seed", "sesame seed", "lentil", "blueberry", "raspberry", "green olive", "prune", "lime",
        "peach", "lemon", "apple", "avocado", "turnip", "bell pepper", "banana", "carrot", "mango",
        "ear of corn", "rutabaga", "scallion", "cauliflower", "lettuce", "coconut", "butternut squash",
        "cabbage", "eggplant", "acorn squash", "pineapple", "cantaloupe", "honeydew", "romaine head",
        "jicama", "pineapple crown", "melon", "papaya", "winter melon", "pumpkin", "watermelon",
    ]
    for idx, week in enumerate(range(4, 41)):
        trimester = trimester_for_week(week)
        size = sizes[min(idx, len(sizes) - 1)]
        db.session.add(PregnancyWeek(
            week=week,
            baby_size=size,
            headline=f"{week} weeks pregnant: your baby is about the size of a {size}",
            baby_summary=f"At week {week}, development focuses on steady growth, organ maturation, reflexes, and practice movements.",
            body_summary=f"{trimester} changes may include shifts in energy, sleep, appetite, and common symptoms. Track questions for your provider.",
            checklist=f"Review appointment notes; hydrate; plan nutritious snacks; read about {trimester.lower()} warning signs; save one article for later.",
        ))
    for month in range(0, 25):
        db.session.add(BabyMonth(
            month=month,
            headline=f"Your baby at {month} months",
            milestones=f"Month {month} milestones may include social smiles, stronger head control, rolling, sitting, crawling, first words, or early pretend play depending on age.",
            feeding=f"Feeding routines at month {month} focus on responsive cues, growth, and age-appropriate solids or milk intake.",
            sleep=f"Sleep at month {month} changes quickly. Many families track naps, bedtime rhythm, night waking, and safe sleep setup.",
        ))
    articles = [
        ("first-trimester-symptoms", "First trimester symptoms and when to call", "Pregnancy Health", "First trimester", 6, "Nausea, fatigue, spotting questions, and symptoms that deserve medical advice."),
        ("pregnancy-safe-foods", "Pregnancy-safe foods and foods to avoid", "Nutrition", "First trimester", 7, "A practical list for seafood, caffeine, deli meat, dairy, and food safety."),
        ("second-trimester-energy", "Making the most of second trimester energy", "Pregnancy Week by Week", "Second trimester", 5, "Plan appointments, registries, movement, and gentle exercise while energy often improves."),
        ("anatomy-scan-guide", "What happens at the anatomy scan", "Prenatal Testing", "Second trimester", 6, "What the ultrasound checks, what to ask, and how results are shared."),
        ("third-trimester-checklist", "Third trimester checklist", "Labor and Birth", "Third trimester", 8, "Hospital bag, birth preferences, feeding plans, car seat setup, and pediatrician choices."),
        ("signs-of-labor", "Signs of labor versus false labor", "Labor and Birth", "Third trimester", 5, "Contractions, water breaking, timing, and when to call your provider."),
        ("newborn-sleep-basics", "Newborn sleep basics", "Baby Sleep", "Postpartum", 6, "Safe sleep, day-night confusion, wake windows, and realistic expectations."),
        ("starting-solids", "Starting solids: readiness signs", "Baby Feeding", "Postpartum", 7, "Sitting support, tongue thrust, iron-rich foods, allergens, and pacing."),
        ("postpartum-recovery", "Postpartum recovery week by week", "Postpartum Health", "Postpartum", 8, "Bleeding, incision care, mood, pelvic floor, and follow-up visits."),
        ("baby-development-red-flags", "Baby development red flags to discuss", "Baby Development", "Postpartum", 6, "How to track milestones and bring concerns to pediatric visits."),
        ("building-a-registry", "Building a practical baby registry", "Gear", "Second trimester", 5, "Sleep, feeding, diapering, transport, and nice-to-have items."),
        ("choosing-childcare", "Choosing childcare before baby arrives", "Family Life", "Third trimester", 7, "Questions for centers, home daycares, nannies, and backup care."),
    ]
    for slug, title, category, trimester, minutes, summary in articles:
        db.session.add(Article(slug=slug, title=title, category=category, trimester=trimester, read_minutes=minutes, summary=summary, body=summary + " This mirror keeps guidance visible and task-grounded for browsing, saving, and tracker workflows."))
    posts = [
        ("june-2026-due-date-roll-call", "June 2026 Birth Club", "Roll call: who else is due in June?", "MayaB", 48, 1, "Share your due date, symptoms, and first appointment plans."),
        ("second-trimester-energy-tips", "Second Trimester Club", "Anyone else suddenly nesting?", "NinaR", 31, 2, "I have more energy and want realistic weekend projects."),
        ("newborn-night-wakings", "Newborn Sleep", "How are you handling night wakings?", "SamK", 64, 0, "Looking for gentle routines that still feel manageable."),
        ("starting-solids-allergens", "Starting Solids", "Introducing peanut and egg this week", "PriyaC", 22, 3, "What order did your pediatrician suggest?"),
        ("hospital-bag-minimalists", "Labor and Birth", "Minimal hospital bag list", "DevonL", 39, 4, "What did you actually use during a short stay?"),
        ("car-seat-install-check", "Gear and Registry", "Car seat install check before 36 weeks", "AnaP", 18, 5, "Our local fire station appointment is next week."),
    ]
    for slug, club, title, author, replies, days_ago, body in posts:
        db.session.add(CommunityPost(slug=slug, club=club, title=title, author=author, replies=replies, last_active=REFERENCE_DATE - timedelta(days=days_ago), body=body))
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
        db.session.add(SavedItem(user_id=user.id, item_type="article", item_slug="third-trimester-checklist", note="Benchmark saved article"))
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
