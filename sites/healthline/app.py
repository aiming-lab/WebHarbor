"""
Healthline mirror — Flask application.

A health-information site modeled on healthline.com:
  Entity      = Article (health article)
  Section     = top-level area (Health Conditions, Nutrition, Mental Health,
                Fitness, Drugs & Medications, Wellness)
  Condition   = Health Conditions detail entity
  Drug        = Drugs & Medications detail entity
  Author      = writer / medical reviewer (with credentials + headshot)
  SavedArticle= bookmark ("My Saved")
  ReadingHistory = articles a user has viewed

All runtime data is read from SQLAlchemy (instance_seed/healthline.db). Seed
content is defined in seed_data.py (Python data, no runtime JSON dependency).
"""
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for, flash, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from sqlalchemy import or_

import seed_data as SD

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "instance"
DB_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "healthline-mirror-secret-key-change-in-prod-1602"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_DIR / 'healthline.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."
csrf = CSRFProtect(app)

REF_DATE = SD.MIRROR_REFERENCE_DATE


# =======================================================================
# MODELS
# =======================================================================

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(200), default="")
    location = db.Column(db.String(120), default="")
    bio = db.Column(db.Text, default="")
    avatar_color = db.Column(db.String(20), default="#1EA896")
    newsletter = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: REF_DATE)

    saved = db.relationship("SavedArticle", backref="user", cascade="all, delete-orphan")
    history = db.relationship("ReadingHistory", backref="user", cascade="all, delete-orphan")

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode("utf-8")

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def initials(self):
        parts = (self.full_name or self.username or "U").split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return (self.username[:2] if self.username else "U").upper()


class Section(db.Model):
    __tablename__ = "sections"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    tagline = db.Column(db.String(250), default="")
    color = db.Column(db.String(20), default="#1EA896")
    sort_order = db.Column(db.Integer, default=100)
    subcategories_csv = db.Column(db.Text, default="")

    @property
    def subcategories(self):
        return [s for s in (self.subcategories_csv or "").split("|") if s]

    @property
    def article_count(self):
        return Article.query.filter_by(section_slug=self.slug).count()


class Author(db.Model):
    __tablename__ = "authors"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    role = db.Column(db.String(20), default="writer")  # writer | reviewer
    credentials = db.Column(db.String(120), default="")
    headshot = db.Column(db.String(300), default="")
    bio = db.Column(db.Text, default="")

    @property
    def display(self):
        return f"{self.name}, {self.credentials}" if self.credentials else self.name


class Article(db.Model):
    __tablename__ = "articles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.Text, nullable=False)
    section_slug = db.Column(db.String(60), default="", index=True)
    subcategory = db.Column(db.String(120), default="", index=True)
    image = db.Column(db.String(300), default="")
    summary = db.Column(db.Text, default="")
    body = db.Column(db.Text, default="")  # paragraphs separated by \n\n
    takeaways = db.Column(db.Text, default="")  # one per line
    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"))
    reviewer_id = db.Column(db.Integer, db.ForeignKey("authors.id"))
    read_minutes = db.Column(db.Integer, default=6)
    evidence_based = db.Column(db.Boolean, default=True)
    view_count = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=lambda: REF_DATE)

    author = db.relationship("Author", foreign_keys=[author_id])
    reviewer = db.relationship("Author", foreign_keys=[reviewer_id])
    saved_by = db.relationship("SavedArticle", backref="article", cascade="all, delete-orphan")
    history = db.relationship("ReadingHistory", backref="article", cascade="all, delete-orphan")

    def paragraphs(self):
        return [p.strip() for p in re.split(r"\n\n+", self.body or "") if p.strip()]

    def takeaway_list(self):
        return [t.strip() for t in (self.takeaways or "").splitlines() if t.strip()]

    @property
    def updated_str(self):
        if not self.updated_at:
            return ""
        delta = REF_DATE - self.updated_at
        if delta.days <= 0:
            return "Updated today"
        if delta.days == 1:
            return "Updated yesterday"
        if delta.days < 30:
            return f"Updated {delta.days} days ago"
        return "Updated on " + self.updated_at.strftime("%B %d, %Y")


class Condition(db.Model):
    __tablename__ = "conditions"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(120), default="", index=True)
    image = db.Column(db.String(300), default="")
    overview = db.Column(db.Text, default="")
    symptoms = db.Column(db.Text, default="")     # one per line
    causes = db.Column(db.Text, default="")
    treatments = db.Column(db.Text, default="")
    when_to_see_doctor = db.Column(db.Text, default="")
    reviewer_id = db.Column(db.Integer, db.ForeignKey("authors.id"))
    reviewer = db.relationship("Author")

    def _lines(self, field):
        return [x.strip() for x in (getattr(self, field) or "").splitlines() if x.strip()]

    def symptom_list(self):
        return self._lines("symptoms")

    def cause_list(self):
        return self._lines("causes")

    def treatment_list(self):
        return self._lines("treatments")


class Drug(db.Model):
    __tablename__ = "drugs"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    generic_name = db.Column(db.String(160), default="")
    drug_class = db.Column(db.String(120), default="", index=True)
    category = db.Column(db.String(120), default="", index=True)
    image = db.Column(db.String(300), default="")
    uses = db.Column(db.Text, default="")
    dosage = db.Column(db.Text, default="")
    common_side_effects = db.Column(db.Text, default="")    # one per line
    serious_side_effects = db.Column(db.Text, default="")
    interactions = db.Column(db.Text, default="")
    warnings = db.Column(db.Text, default="")
    reviewer_id = db.Column(db.Integer, db.ForeignKey("authors.id"))
    reviewer = db.relationship("Author")

    def _lines(self, field):
        return [x.strip() for x in (getattr(self, field) or "").splitlines() if x.strip()]

    def common_se_list(self):
        return self._lines("common_side_effects")

    def serious_se_list(self):
        return self._lines("serious_side_effects")

    def interaction_list(self):
        return self._lines("interactions")


class SavedArticle(db.Model):
    __tablename__ = "saved_articles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    saved_at = db.Column(db.DateTime, default=lambda: REF_DATE)
    __table_args__ = (db.UniqueConstraint("user_id", "article_id", name="_user_article_saved_uc"),)


class ReadingHistory(db.Model):
    __tablename__ = "reading_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    viewed_at = db.Column(db.DateTime, default=lambda: REF_DATE)


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# =======================================================================
# SEED
# =======================================================================

def seed_database():
    """Idempotent — gated on the whole function."""
    if Section.query.count() > 0:
        return

    # Sections
    for slug, name, tagline, color, order in SD.SECTIONS:
        db.session.add(Section(
            slug=slug, name=name, tagline=tagline, color=color, sort_order=order,
            subcategories_csv="|".join(SD.SUBCATEGORIES.get(slug, [])),
        ))

    # Authors / reviewers
    people_by_key = {}
    for key, name, role, creds, headshot, bio in SD.PEOPLE:
        a = Author(key=key, name=name, role=role, credentials=creds,
                   headshot=headshot, bio=bio)
        db.session.add(a)
        people_by_key[key] = a
    db.session.flush()

    # Articles
    for (slug, title, section_slug, subcat, image, summary, author_key,
         reviewer_key, body_paras, takeaways, read_min, evidence, days_ago) in SD.ARTICLES:
        author = people_by_key.get(author_key)
        reviewer = people_by_key.get(reviewer_key)
        db.session.add(Article(
            slug=slug, title=title, section_slug=section_slug, subcategory=subcat,
            image=image, summary=summary, body="\n\n".join(body_paras),
            takeaways="\n".join(takeaways),
            author_id=author.id if author else None,
            reviewer_id=reviewer.id if reviewer else None,
            read_minutes=read_min, evidence_based=evidence,
            view_count=1200 + (len(slug) * 37) % 48000,
            updated_at=REF_DATE - timedelta(days=days_ago),
        ))

    # Conditions
    for (slug, name, category, image, overview, symptoms, causes, treatments,
         wtsd, reviewer_key) in SD.CONDITIONS:
        reviewer = people_by_key.get(reviewer_key)
        db.session.add(Condition(
            slug=slug, name=name, category=category, image=image, overview=overview,
            symptoms="\n".join(symptoms), causes="\n".join(causes),
            treatments="\n".join(treatments), when_to_see_doctor=wtsd,
            reviewer_id=reviewer.id if reviewer else None,
        ))

    # Drugs
    for (slug, name, generic, dclass, category, image, uses, dosage, common_se,
         serious_se, interactions, warnings, reviewer_key) in SD.DRUGS:
        reviewer = people_by_key.get(reviewer_key)
        db.session.add(Drug(
            slug=slug, name=name, generic_name=generic, drug_class=dclass,
            category=category, image=image, uses=uses, dosage=dosage,
            common_side_effects="\n".join(common_se),
            serious_side_effects="\n".join(serious_se),
            interactions="\n".join(interactions), warnings=warnings,
            reviewer_id=reviewer.id if reviewer else None,
        ))

    db.session.commit()


def seed_benchmark_users():
    """Idempotent — gated on the whole function. Creates 4 users with
    pre-existing saved articles and reading history."""
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    users = {}
    for username, email, full_name, location, bio, color in SD.BENCHMARK_USERS:
        u = User(username=username, email=email, full_name=full_name,
                 location=location, bio=bio, avatar_color=color)
        u.set_password(SD.BENCHMARK_PASSWORD)
        db.session.add(u)
        users[username] = u
    db.session.flush()

    def arts(section, n):
        return (Article.query.filter_by(section_slug=section)
                .order_by(Article.slug).limit(n).all())

    # Deterministic, interest-aligned saved + history assignments per user.
    plan = {
        "alice_j": {"saved": ["nutrition", "wellness"], "history": ["nutrition"]},
        "bob_c":   {"saved": ["health-conditions", "drugs"], "history": ["health-conditions"]},
        "carol_d": {"saved": ["mental-health", "wellness"], "history": ["mental-health"]},
        "david_k": {"saved": ["fitness", "nutrition"], "history": ["fitness"]},
    }

    for username, cfg in plan.items():
        u = users[username]
        saved_arts = []
        for sec in cfg["saved"]:
            saved_arts += arts(sec, 3)
        seen = set()
        deduped = []
        for a in saved_arts:
            if a.id not in seen:
                seen.add(a.id)
                deduped.append(a)
        for i, a in enumerate(deduped[:5]):
            db.session.add(SavedArticle(user_id=u.id, article_id=a.id,
                                        saved_at=REF_DATE - timedelta(days=2 + i)))
        hist_arts = []
        for sec in cfg["history"]:
            hist_arts += arts(sec, 4)
        for i, a in enumerate(hist_arts[:4]):
            db.session.add(ReadingHistory(user_id=u.id, article_id=a.id,
                                          viewed_at=REF_DATE - timedelta(days=1, hours=i)))

    db.session.commit()


# =======================================================================
# CONTEXT PROCESSORS / HELPERS
# =======================================================================

@app.context_processor
def inject_globals():
    sections = Section.query.order_by(Section.sort_order).all()
    saved_count = 0
    if current_user.is_authenticated:
        saved_count = SavedArticle.query.filter_by(user_id=current_user.id).count()
    return dict(
        nav_sections=sections,
        section_names={s.slug: s.name for s in sections},
        saved_count=saved_count,
        current_year=REF_DATE.year,
        ref_date_str=REF_DATE.strftime("%B %d, %Y"),
    )


def get_section_or_404(slug):
    s = Section.query.filter_by(slug=slug).first()
    if not s:
        abort(404)
    return s


STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and", "or",
    "is", "are", "be", "by", "from", "as", "that", "this", "about", "into",
    "what", "who", "how", "when", "where", "which", "your", "you", "it", "its",
    "do", "does", "can", "best", "good", "health", "healthline", "article",
    "find", "get", "read", "search", "guide", "tips", "ways", "should", "need",
}


def _tokens(query):
    return [t for t in re.findall(r"[a-z0-9]+", (query or "").lower())
            if t not in STOPWORDS and len(t) >= 2]


def _article_haystack(a):
    sec = a.section_slug.replace("-", " ")
    return " ".join([
        (a.title or "").lower(),
        (a.summary or "").lower(),
        (a.body or "").lower()[:4000],
        (a.subcategory or "").lower(),
        sec,
    ])


def scored_article_search(query):
    """Scored token-overlap search across articles. Returns ranked list."""
    tokens = _tokens(query)
    if not tokens:
        return Article.query.order_by(Article.view_count.desc()).all()
    scored = []
    for a in Article.query.all():
        hay = _article_haystack(a)
        score = sum(1 for t in tokens if t in hay)
        title_l = (a.title or "").lower()
        score += sum(1 for t in tokens if t in title_l)  # title boost
        if score >= 1:
            scored.append((score, a.view_count or 0, a))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [a for _, _, a in scored]


# =======================================================================
# ROUTES — PUBLIC
# =======================================================================

@app.route("/")
def index():
    featured = Article.query.order_by(Article.view_count.desc()).limit(5).all()
    top = featured[0] if featured else None
    rest = featured[1:5]
    latest = Article.query.order_by(Article.updated_at.desc()).limit(8).all()
    sections = Section.query.order_by(Section.sort_order).all()
    section_strips = []
    for s in sections:
        items = (Article.query.filter_by(section_slug=s.slug)
                 .order_by(Article.updated_at.desc()).limit(4).all())
        if items:
            section_strips.append((s, items))
    return render_template("index.html", top=top, rest=rest, latest=latest,
                           section_strips=section_strips)


@app.route("/section/<slug>")
def section_page(slug):
    section = get_section_or_404(slug)
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 9
    sub = (request.args.get("sub") or "").strip()
    sort = request.args.get("sort", "latest")

    q = Article.query.filter_by(section_slug=slug)
    if sub:
        q = q.filter(Article.subcategory.ilike(sub))

    if sort == "popular":
        q = q.order_by(Article.view_count.desc())
    elif sort == "az":
        q = q.order_by(Article.title.asc())
    else:
        q = q.order_by(Article.updated_at.desc())

    total = q.count()
    articles = q.offset((page - 1) * per_page).limit(per_page).all()
    return render_template("section.html", section=section, articles=articles,
                           total=total, page=page, per_page=per_page,
                           sub=sub, sort=sort)


@app.route("/article/<slug>")
def article_detail(slug):
    art = Article.query.filter_by(slug=slug).first_or_404()
    art.view_count += 1
    if current_user.is_authenticated:
        existing = ReadingHistory.query.filter_by(
            user_id=current_user.id, article_id=art.id).first()
        if existing:
            existing.viewed_at = REF_DATE
        else:
            db.session.add(ReadingHistory(user_id=current_user.id, article_id=art.id,
                                          viewed_at=REF_DATE))
    db.session.commit()

    related = (Article.query.filter(Article.section_slug == art.section_slug,
                                    Article.id != art.id)
               .order_by(Article.view_count.desc()).limit(4).all())
    is_saved = False
    if current_user.is_authenticated:
        is_saved = SavedArticle.query.filter_by(
            user_id=current_user.id, article_id=art.id).first() is not None
    return render_template("article_detail.html", article=art, related=related,
                           is_saved=is_saved)


@app.route("/conditions")
def conditions_index():
    cat = (request.args.get("category") or "").strip()
    q = Condition.query
    if cat:
        q = q.filter(Condition.category.ilike(cat))
    conditions = q.order_by(Condition.name.asc()).all()
    categories = sorted({c.category for c in Condition.query.all() if c.category})
    return render_template("conditions.html", conditions=conditions,
                           categories=categories, cat=cat)


@app.route("/condition/<slug>")
def condition_detail(slug):
    cond = Condition.query.filter_by(slug=slug).first_or_404()
    related = (Article.query.filter(
        or_(Article.subcategory.ilike(cond.category),
            Article.title.ilike(f"%{cond.name.split()[0]}%")))
        .limit(4).all())
    return render_template("condition_detail.html", condition=cond, related=related)


@app.route("/drugs")
def drugs_index():
    cat = (request.args.get("category") or "").strip()
    letter = (request.args.get("letter") or "").strip().upper()
    q = Drug.query
    if cat:
        q = q.filter(Drug.category.ilike(cat))
    if letter:
        q = q.filter(Drug.name.ilike(f"{letter}%"))
    drugs = q.order_by(Drug.name.asc()).all()
    categories = sorted({d.category for d in Drug.query.all() if d.category})
    letters = sorted({d.name[0].upper() for d in Drug.query.all() if d.name})
    return render_template("drugs.html", drugs=drugs, categories=categories,
                           cat=cat, letter=letter, letters=letters)


@app.route("/drug/<slug>")
def drug_detail(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    related = (Drug.query.filter(Drug.category == drug.category, Drug.id != drug.id)
               .order_by(Drug.name.asc()).limit(4).all())
    return render_template("drug_detail.html", drug=drug, related=related)


@app.route("/author/<key>")
def author_detail(key):
    author = Author.query.filter_by(key=key).first_or_404()
    written = (Article.query.filter_by(author_id=author.id)
               .order_by(Article.updated_at.desc()).all())
    reviewed = (Article.query.filter_by(reviewer_id=author.id)
                .order_by(Article.updated_at.desc()).all())
    return render_template("author.html", author=author, written=written,
                           reviewed=reviewed)


@app.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    scope = request.args.get("type", "all")  # all | articles | conditions | drugs
    article_results = []
    condition_results = []
    drug_results = []

    if q:
        tokens = _tokens(q)
        if scope in ("all", "articles"):
            article_results = scored_article_search(q)
        if scope in ("all", "conditions"):
            for c in Condition.query.all():
                hay = " ".join([(c.name or "").lower(), (c.overview or "").lower(),
                                (c.category or "").lower(), (c.symptoms or "").lower()])
                if any(t in hay for t in tokens):
                    condition_results.append(c)
        if scope in ("all", "drugs"):
            for d in Drug.query.all():
                hay = " ".join([(d.name or "").lower(), (d.generic_name or "").lower(),
                                (d.uses or "").lower(), (d.drug_class or "").lower()])
                if any(t in hay for t in tokens):
                    drug_results.append(d)

    total = len(article_results) + len(condition_results) + len(drug_results)
    return render_template("search.html", query=q, scope=scope,
                           article_results=article_results,
                           condition_results=condition_results,
                           drug_results=drug_results, total=total)


# =======================================================================
# ROUTES — AUTH
# =======================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Signed in successfully.", "success")
            return redirect(request.args.get("next") or url_for("account"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        username = (request.form.get("username") or "").strip()
        full_name = (request.form.get("full_name") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        if not (email and username and password and full_name):
            flash("Full name, email, username, and password are all required.", "error")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("register.html")
        if User.query.filter_by(username=username).first():
            flash("That username is already taken.", "error")
            return render_template("register.html")
        u = User(email=email, username=username, full_name=full_name)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash("Account created. Welcome to Healthline.", "success")
        return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("index"))


# =======================================================================
# ROUTES — ACCOUNT
# =======================================================================

@app.route("/account")
@login_required
def account():
    saved = (SavedArticle.query.filter_by(user_id=current_user.id)
             .order_by(SavedArticle.saved_at.desc()).limit(5).all())
    history = (ReadingHistory.query.filter_by(user_id=current_user.id)
               .order_by(ReadingHistory.viewed_at.desc()).limit(8).all())
    return render_template("account.html", saved=saved, history=history)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        current_user.full_name = (request.form.get("full_name") or "").strip()
        current_user.location = (request.form.get("location") or "").strip()
        current_user.bio = (request.form.get("bio") or "").strip()
        current_user.newsletter = request.form.get("newsletter") == "on"
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        if not current_user.check_password(current):
            flash("Current password is incorrect.", "error")
        elif new != confirm:
            flash("New passwords do not match.", "error")
        elif len(new) < 6:
            flash("Password must be at least 6 characters.", "error")
        else:
            current_user.set_password(new)
            db.session.commit()
            flash("Password updated.", "success")
            return redirect(url_for("account"))
    return render_template("change_password.html")


@app.route("/saved")
@login_required
def saved_articles():
    items = (SavedArticle.query.filter_by(user_id=current_user.id)
             .order_by(SavedArticle.saved_at.desc()).all())
    return render_template("saved.html", items=items)


@app.route("/history")
@login_required
def reading_history():
    items = (ReadingHistory.query.filter_by(user_id=current_user.id)
             .order_by(ReadingHistory.viewed_at.desc()).all())
    return render_template("history.html", items=items)


@app.route("/save/<int:article_id>", methods=["POST"])
@login_required
def toggle_save(article_id):
    art = db.session.get(Article, article_id)
    if not art:
        abort(404)
    existing = SavedArticle.query.filter_by(
        user_id=current_user.id, article_id=article_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash("Removed from your saved articles.", "success")
    else:
        db.session.add(SavedArticle(user_id=current_user.id, article_id=article_id,
                                    saved_at=REF_DATE))
        db.session.commit()
        flash("Saved to your articles.", "success")
    return redirect(request.referrer or url_for("article_detail", slug=art.slug))


# =======================================================================
# STATIC INFO PAGES
# =======================================================================

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/_health")
def health():
    return {"ok": True, "site": "healthline",
            "articles": Article.query.count(),
            "conditions": Condition.query.count(),
            "drugs": Drug.query.count()}


# =======================================================================
# BOOTSTRAP
# =======================================================================

with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
