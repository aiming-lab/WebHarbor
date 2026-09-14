"""PhET Interactive Simulations mirror.

Mirrors the structure of https://phet.colorado.edu/ for WebHarbor agent
evaluation: a Flask + SQLite app that serves a deterministic snapshot of
the PhET simulation catalog (browse, filter, search, translations,
teacher activities, account-gated saves).
"""
import json
import os
import re
from datetime import date, datetime
from pathlib import Path

from flask import (
    Flask, abort, flash, jsonify, redirect, render_template, request,
    session, url_for,
)
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import or_

import catalog_data
from _health import health as _health_payload


BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "instance"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "phet_simulations.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "phet-simulations-dev-secret-key-do-not-use-in-prod"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["JSON_SORT_KEYS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
csrf = CSRFProtect(app)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="teacher")
    institution = db.Column(db.String(200))
    country = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    saved = db.relationship(
        "SavedSimulation", backref="user", lazy="dynamic",
        cascade="all, delete-orphan",
    )


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    icon = db.Column(db.String(40))
    color = db.Column(db.String(20))
    description = db.Column(db.Text)


class GradeLevel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    age_range = db.Column(db.String(40))
    sort_order = db.Column(db.Integer, default=0)


class Language(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    native_name = db.Column(db.String(80), nullable=False)
    sim_count = db.Column(db.Integer, default=0)
    is_rtl = db.Column(db.Boolean, default=False)


class Simulation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    short_description = db.Column(db.String(300), nullable=False)
    overview = db.Column(db.Text, nullable=False)
    subjects_json = db.Column(db.Text, default="[]")
    grades_json = db.Column(db.Text, default="[]")
    topics_json = db.Column(db.Text, default="[]")
    languages_json = db.Column(db.Text, default='["en"]')
    version = db.Column(db.String(20), default="1.0.0")
    is_html5 = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=False)
    thumbnail = db.Column(db.String(120))
    release_date = db.Column(db.Date)
    updated_date = db.Column(db.Date)
    # PhET publishes no play or download counter and no per-sim runtime, so
    # none is stored. Translation coverage is a real, published figure.
    locale_count = db.Column(db.Integer, default=1)
    related_json = db.Column(db.Text, default="[]")
    learning_goals = db.Column(db.Text, default="")
    design_team = db.Column(db.String(400), default="")
    has_teachers_guide = db.Column(db.Boolean, default=False)
    is_phet_studio = db.Column(db.Boolean, default=False)
    upstream_url = db.Column(db.String(240), default="")
    activities = db.relationship(
        "Activity", backref="simulation", lazy="dynamic",
        cascade="all, delete-orphan",
    )
    saved_by = db.relationship(
        "SavedSimulation", backref="simulation", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def subjects(self):
        return json.loads(self.subjects_json or "[]")

    def grades(self):
        return json.loads(self.grades_json or "[]")

    def topics(self):
        return json.loads(self.topics_json or "[]")

    def languages(self):
        return json.loads(self.languages_json or '["en"]')

    def related(self):
        return json.loads(self.related_json or "[]")


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sim_id = db.Column(
        db.Integer, db.ForeignKey("simulation.id"), nullable=False, index=True,
    )
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    grade_level = db.Column(db.String(40))
    duration_min = db.Column(db.Integer)
    description = db.Column(db.Text, nullable=False)
    file_type = db.Column(db.String(20), default="PDF")
    published_date = db.Column(db.Date)


class SavedSimulation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True,
    )
    sim_id = db.Column(
        db.Integer, db.ForeignKey("simulation.id"), nullable=False, index=True,
    )
    notes = db.Column(db.Text)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "sim_id"),)


@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _subject_map():
    return {s.slug: s for s in Subject.query.all()}


def _grade_map():
    return {g.slug: g for g in GradeLevel.query.order_by(GradeLevel.sort_order).all()}


def _language_map():
    return {l.code: l for l in Language.query.order_by(Language.name).all()}


def _saved_sim_ids():
    if not current_user.is_authenticated:
        return set()
    return {s.sim_id for s in current_user.saved.all()}


_THUMB_DIR = os.path.join(BASE_DIR, "static", "images", "sims")
_AVAILABLE_THUMBNAILS = frozenset(
    f[:-4] for f in os.listdir(_THUMB_DIR)
    if f.endswith(".png") and os.path.getsize(os.path.join(_THUMB_DIR, f)) > 1000
) if os.path.isdir(_THUMB_DIR) else frozenset()


@app.context_processor
def inject_globals():
    return {
        "site_title": "PhET Interactive Simulations",
        "site_tagline": "Free online math and science simulations",
        "current_year": datetime.utcnow().year,
        "primary_subjects": Subject.query.order_by(Subject.name).all(),
        "grade_levels": GradeLevel.query.order_by(GradeLevel.sort_order).all(),
        "saved_sim_ids": _saved_sim_ids(),
        "available_thumbnails": _AVAILABLE_THUMBNAILS,
    }


# ---------------------------------------------------------------------------
# Routes — public
# ---------------------------------------------------------------------------

@app.route("/_health")
def health():
    return jsonify(_health_payload())


@app.route("/")
def index():
    featured = (
        Simulation.query.filter_by(is_featured=True)
        .order_by(Simulation.title)
        .limit(8)
        .all()
    )
    new_sims = (
        Simulation.query.filter_by(is_new=True)
        .order_by(Simulation.release_date.desc())
        .limit(6)
        .all()
    )
    # Upstream publishes no popularity counter, so the third homepage rail is
    # "recently updated", which is a real published date.
    most_played = (
        Simulation.query.order_by(Simulation.updated_date.desc())
        .limit(6)
        .all()
    )
    total = Simulation.query.count()
    total_languages = Language.query.count()
    total_activities = Activity.query.count()
    return render_template(
        "index.html",
        featured=featured,
        new_sims=new_sims,
        most_played=most_played,
        total_simulations=total,
        total_languages=total_languages,
        total_activities=total_activities,
    )


@app.route("/simulations")
def simulations():
    subject = request.args.get("subject", "").strip()
    topic = request.args.get("topic", "").strip()
    grade = request.args.get("grade", "").strip()
    language = request.args.get("language", "").strip()
    release = request.args.get("release", "").strip()
    sort = request.args.get("sort", "title")
    view = request.args.get("view", "filter").strip()
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 24

    query = Simulation.query
    if subject:
        query = query.filter(Simulation.subjects_json.like(f'%"{subject}"%'))
    if topic:
        query = query.filter(Simulation.topics_json.like(f'%"{topic}"%'))
    if grade:
        query = query.filter(Simulation.grades_json.like(f'%"{grade}"%'))
    if language:
        query = query.filter(Simulation.languages_json.like(f'%"{language}"%'))
    if release == "new":
        query = query.filter_by(is_new=True)
    elif release == "updated":
        # "Recently updated" in this snapshot = released in 2024 or later.
        query = query.filter(Simulation.release_date >= date(2024, 1, 1))

    if sort == "newest":
        query = query.order_by(Simulation.release_date.desc())
    elif sort == "translations":
        query = query.order_by(Simulation.locale_count.desc(), Simulation.title)
    elif sort == "updated":
        query = query.order_by(Simulation.updated_date.desc(), Simulation.title)
    else:
        query = query.order_by(Simulation.title)

    total = query.count()
    sims = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = max((total + per_page - 1) // per_page, 1)

    any_filter_active = bool(
        subject or topic or grade or language or release or sort != "title"
    )
    view_tab = view if view in ("browse", "filter", "customize") else "filter"

    customizable = []
    if view_tab == "customize":
        customizable = (
            Simulation.query.filter_by(is_phet_studio=True)
            .order_by(Simulation.title)
            .all()
        )

    sims_by_subject = {}
    if view_tab == "browse":
        ordered = ['physics', 'math', 'chemistry', 'earth-science', 'biology']
        for slug in ordered:
            sims_by_subject[slug] = (
                Simulation.query
                .filter(Simulation.subjects_json.like(f'%"{slug}"%'))
                .order_by(Simulation.title)
                .limit(7)
                .all()
            )

    return render_template(
        "simulations.html",
        sims=sims,
        total=total,
        page=page,
        total_pages=total_pages,
        subject=subject,
        topic=topic,
        topics=TOPICS_SEED,
        customizable=customizable,
        grade=grade,
        language=language,
        release=release,
        sort=sort,
        view_tab=view_tab,
        languages=Language.query.order_by(Language.name).all(),
        any_filter_active=any_filter_active,
        sims_by_subject=sims_by_subject,
    )


@app.route("/simulations/category/<slug>")
def simulations_by_subject(slug):
    subject = Subject.query.filter_by(slug=slug).first_or_404()
    sims = (
        Simulation.query.filter(Simulation.subjects_json.like(f'%"{slug}"%'))
        .order_by(Simulation.title)
        .all()
    )
    return render_template(
        "category.html", subject=subject, sims=sims,
    )


@app.route("/simulation/<slug>")
def simulation_detail(slug):
    # Read-only: GET must never mutate the DB.
    sim = Simulation.query.filter_by(slug=slug).first_or_404()

    subjects_full = [
        s for s in Subject.query.filter(Subject.slug.in_(sim.subjects())).all()
    ]
    grades_full = [
        g for g in GradeLevel.query.filter(GradeLevel.slug.in_(sim.grades())).all()
    ]
    langs_full = [
        l for l in Language.query.filter(Language.code.in_(sim.languages())).all()
    ]

    # Upstream publishes an explicit relatedSimulations list per sim; use it and
    # keep its order. Fall back to same-subject titles only when it is empty.
    related_slugs = sim.related()
    related = []
    if related_slugs:
        found = {
            s.slug: s for s in
            Simulation.query.filter(Simulation.slug.in_(related_slugs)).all()
        }
        related = [found[s] for s in related_slugs if s in found]
    if not related:
        related = (
            Simulation.query.filter(Simulation.id != sim.id)
            .filter(
                or_(*[
                    Simulation.subjects_json.like(f'%"{s}"%') for s in sim.subjects()
                ])
            )
            .order_by(Simulation.title)
            .limit(6)
            .all()
        )
    activities = sim.activities.order_by(Activity.published_date.desc()).all()

    saved_row = (
        SavedSimulation.query.filter_by(user_id=current_user.id, sim_id=sim.id).first()
        if current_user.is_authenticated
        else None
    )
    is_saved = saved_row is not None
    saved_note = saved_row.notes if saved_row else ""

    return render_template(
        "simulation_detail.html",
        sim=sim,
        subjects=subjects_full,
        grades=grades_full,
        languages=langs_full,
        related=related,
        activities=activities,
        is_saved=is_saved,
        saved_note=saved_note,
    )


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    sims = []
    if q:
        # Match every whitespace-separated token independently so multi-word
        # queries such as "build atom" still reach "Build an Atom".
        tokens = [tok for tok in re.split(r"\W+", q) if tok]
        query = Simulation.query
        for tok in tokens or [q]:
            pattern = f"%{tok}%"
            query = query.filter(
                or_(
                    Simulation.title.ilike(pattern),
                    Simulation.short_description.ilike(pattern),
                    Simulation.overview.ilike(pattern),
                    Simulation.topics_json.ilike(pattern),
                )
            )
        sims = query.order_by(Simulation.title).all()
    return render_template("search.html", query=q, sims=sims, total=len(sims))


@app.route("/translations")
def translations():
    langs = (
        Language.query.order_by(Language.sim_count.desc(), Language.name)
        .all()
    )
    return render_template("translations.html", languages=langs)


@app.route("/translations/<code>")
def translation_detail(code):
    lang = Language.query.filter_by(code=code).first_or_404()
    sims = (
        Simulation.query.filter(Simulation.languages_json.like(f'%"{code}"%'))
        .order_by(Simulation.title)
        .all()
    )
    return render_template(
        "translation_detail.html", language=lang, sims=sims,
    )


@app.route("/teachers")
def teachers():
    featured = (
        Activity.query.order_by(Activity.published_date.desc(), Activity.title)
        .limit(6)
        .all()
    )
    return render_template("teachers.html", featured_activities=featured)


@app.route("/teachers/activities")
def activities():
    grade = request.args.get("grade", "")
    query = Activity.query
    if grade:
        query = query.filter_by(grade_level=grade)
    items = query.order_by(Activity.published_date.desc()).all()
    return render_template("activities.html", activities=items, grade=grade)


@app.route("/teachers/activity/<int:activity_id>")
def activity_detail(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    return render_template("activity_detail.html", activity=activity)


@app.route("/about")
def about():
    stats = {
        "simulations": Simulation.query.count(),
        "languages": Language.query.count(),
        "subjects": Subject.query.count(),
        "activities": Activity.query.count(),
    }
    return render_template("about.html", stats=stats)


@app.route("/accessibility")
def accessibility():
    return render_template("accessibility.html")


# ---------------------------------------------------------------------------
# Routes — auth
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        institution = request.form.get("institution", "").strip()
        country = request.form.get("country", "").strip()

        if not EMAIL_RE.match(email):
            flash("Please enter a valid email address.", "error")
        elif len(name) < 2:
            flash("Please enter your full name.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(
                email=email,
                name=name,
                password_hash=bcrypt.generate_password_hash(password).decode(),
                institution=institution,
                country=country,
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to PhET! Your account is ready.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(request.args.get("next") or url_for("account"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    saved_rows = (
        SavedSimulation.query.filter_by(user_id=current_user.id)
        .order_by(SavedSimulation.saved_at.desc())
        .all()
    )
    return render_template("account.html", saved_rows=saved_rows)


@app.route("/api/save-sim", methods=["POST"])
@login_required
def api_save_sim():
    data = request.get_json(silent=True) or request.form
    sim_id = data.get("sim_id")
    notes = (data.get("notes") or "").strip()
    if not sim_id:
        return jsonify({"ok": False, "error": "missing sim_id"}), 400
    sim = Simulation.query.get(int(sim_id))
    if not sim:
        return jsonify({"ok": False, "error": "unknown simulation"}), 404
    existing = SavedSimulation.query.filter_by(
        user_id=current_user.id, sim_id=sim.id,
    ).first()
    if existing:
        existing.notes = notes or existing.notes
    else:
        db.session.add(
            SavedSimulation(
                user_id=current_user.id, sim_id=sim.id, notes=notes,
            )
        )
    db.session.commit()
    return jsonify({"ok": True, "saved": True, "sim_id": sim.id})


@app.route("/api/unsave-sim", methods=["POST"])
@login_required
def api_unsave_sim():
    data = request.get_json(silent=True) or request.form
    sim_id = data.get("sim_id")
    if not sim_id:
        return jsonify({"ok": False, "error": "missing sim_id"}), 400
    row = SavedSimulation.query.filter_by(
        user_id=current_user.id, sim_id=int(sim_id),
    ).first()
    if row:
        db.session.delete(row)
        db.session.commit()
    return jsonify({"ok": True, "saved": False, "sim_id": int(sim_id)})


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

# Catalogue constants now come from catalog_data.py, which is harvested from
# phet.colorado.edu rather than generated. See that module's docstring.
SUBJECTS_SEED = catalog_data.SUBJECTS
TOPICS_SEED = catalog_data.TOPICS
GRADES_SEED = catalog_data.GRADES
LANGUAGES_SEED = catalog_data.LANGUAGES
SIMULATIONS_SEED = catalog_data.SIMULATIONS

# Teacher lesson plans on the real site are submitted by named educators. This
# mirror does not reproduce them: the rows below are benchmark fixtures with
# synthetic authors, deliberately not attributed to real PhET contributors, and
# each one points at a simulation that genuinely exists upstream.
ACTIVITIES_SEED = [
    # (sim_slug, title, author, grade, duration_min, description)
    ("forces-and-motion-basics", "Net Force Investigation", "R. Alvarez (benchmark fixture)",
     "high", 40, "Students predict, observe and explain motion under balanced and "
     "unbalanced forces using applied force and friction."),
    ("build-an-atom", "Atomic Structure Lab", "M. Okafor (benchmark fixture)",
     "middle", 60, "Build atoms of the first ten elements, identify subatomic "
     "particles and explore how proton count determines the element."),
    ("balancing-chemical-equations", "Coefficient Practice", "S. Lindqvist (benchmark fixture)",
     "high", 60, "Balance equations of increasing difficulty and connect coefficients "
     "to conservation of mass."),
    ("natural-selection", "Selection Pressure Lab", "D. Ferreira (benchmark fixture)",
     "high", 35, "Vary selection agents and mutations, then describe which traits "
     "change survivability in each environment."),
    ("energy-skate-park", "Conservation of Energy", "H. Nakamura (benchmark fixture)",
     "high", 35, "Track kinetic, potential and thermal energy around a track and "
     "explain conservation of mechanical energy."),
    ("circuit-construction-kit-dc", "Series and Parallel", "T. Bagchi (benchmark fixture)",
     "high", 55, "Build series and parallel circuits, measure current and voltage, "
     "and compare the two topologies."),
    ("gravity-and-orbits", "Modeling the Solar System", "L. Moreau (benchmark fixture)",
     "middle", 50, "Relate the Sun, Earth, Moon and space station through gravity, "
     "orbits and relative distance."),
    ("states-of-matter", "Phase Change Inquiry", "P. Novak (benchmark fixture)",
     "middle", 60, "Heat and cool substances and connect molecular motion to solid, "
     "liquid and gas phases."),
    ("ph-scale", "Acids and Bases in the Kitchen", "A. Haddad (benchmark fixture)",
     "middle", 40, "Measure the pH of household liquids and relate the scale to "
     "acid and base strength."),
    ("graphing-lines", "Slope-Intercept Form", "C. Villanueva (benchmark fixture)",
     "middle", 60, "Move between slope-intercept and point-slope form and predict "
     "how each parameter moves the line."),
    ("fractions-intro", "Equivalent Fractions Game", "J. Whitfield (benchmark fixture)",
     "elementary", 50, "Build equivalent fractions with shapes and number lines, "
     "then compare the results."),
    ("density", "Identify the Mystery Block", "K. Solberg (benchmark fixture)",
     "middle", 55, "Use mass and volume measurements to identify unknown blocks by "
     "their density."),
    ("wave-interference", "Boundary Identification", "N. Erdmann (benchmark fixture)",
     "high", 40, "Compare reflection and transmission at boundaries for water, sound "
     "and light waves."),
    ("projectile-motion", "Launch Angle Study", "F. Castellano (benchmark fixture)",
     "high", 50, "Vary launch angle, speed and drag, then predict range and flight "
     "time for each configuration."),
]


# Benchmark-only accounts on a .test domain. These are fixtures for the
# environment, not mirrored upstream data.
BENCHMARK_USERS = [
    ("teacher@phet.test", "Ada Lovelace", "phet-teacher-pass",
     "teacher", "Cherry Creek High School", "United States"),
    ("student@phet.test", "Carl Sagan", "phet-student-pass",
     "student", "Ithaca High School", "United States"),
    ("research@phet.test", "Marie Curie", "phet-research-pass",
     "researcher", "Sorbonne University", "France"),
    ("demo@phet.test", "Demo User", "phet-demo-pass",
     "teacher", "Demo School", "Canada"),
]


def seed_subjects():
    if Subject.query.count() > 0:
        return
    for slug, name, icon, color, desc in SUBJECTS_SEED:
        db.session.add(Subject(slug=slug, name=name, icon=icon,
                               color=color, description=desc))
    db.session.commit()


def seed_grades():
    if GradeLevel.query.count() > 0:
        return
    for slug, name, age_range, sort_order in GRADES_SEED:
        db.session.add(GradeLevel(slug=slug, name=name, age_range=age_range,
                                  sort_order=sort_order))
    db.session.commit()


def seed_languages():
    if Language.query.count() > 0:
        return
    for row in LANGUAGES_SEED:
        db.session.add(Language(
            code=row["code"], name=row["name"],
            native_name=row["native_name"], is_rtl=row["is_rtl"],
            sim_count=0,
        ))
    db.session.commit()


def seed_simulations():
    if Simulation.query.count() > 0:
        return
    for row in SIMULATIONS_SEED:
        db.session.add(Simulation(
            slug=row["slug"],
            title=row["title"],
            short_description=row["description"][:300],
            overview=row["description"],
            learning_goals=row["learning_goals"],
            subjects_json=json.dumps(row["subjects"]),
            grades_json=json.dumps(row["grades"]),
            # the filter facet ids plus the topic strip shown upstream
            topics_json=json.dumps(row["topics"] + row["detail_topics"]),
            languages_json=json.dumps(row["locales"]),
            related_json=json.dumps(row["related"]),
            version=row["version"],
            is_html5=True,
            # upstream has no editorial "featured" rail; the mirror marks the
            # twelve simulations upstream flags as new so the homepage has a
            # deterministic, source-backed selection.
            is_featured=row["is_new"],
            is_new=row["is_new"],
            thumbnail=f"{row['slug']}.png",
            release_date=date.fromisoformat(row["released"]),
            updated_date=date.fromisoformat(row["updated"]),
            locale_count=len(row["locales"]),
            design_team=row["design_team"][:400],
            has_teachers_guide=row["teachers_guide"],
            is_phet_studio=row["is_phet_studio"],
            upstream_url=row["upstream_page"],
        ))
    db.session.commit()

    counts = {}
    for sim in Simulation.query.all():
        for code in sim.languages():
            counts[code] = counts.get(code, 0) + 1
    for lang in Language.query.all():
        lang.sim_count = counts.get(lang.code, 0)
    db.session.commit()


def seed_activities():
    if Activity.query.count() > 0:
        return
    for sim_slug, title, author, grade, duration, description in ACTIVITIES_SEED:
        sim = Simulation.query.filter_by(slug=sim_slug).first()
        if sim is None:
            continue
        db.session.add(Activity(
            sim_id=sim.id, title=title, author=author,
            grade_level=grade, duration_min=duration, description=description,
            file_type="PDF", published_date=sim.updated_date,
        ))
    db.session.commit()


def seed_benchmark_users():
    if User.query.count() > 0:
        return
    for email, name, password, role, institution, country in BENCHMARK_USERS:
        db.session.add(User(
            email=email,
            name=name,
            password_hash=bcrypt.generate_password_hash(password).decode(),
            role=role,
            institution=institution,
            country=country,
        ))
    db.session.commit()

    # Pre-populate saved sims for the demo teacher so the account page is
    # non-empty when an agent inspects it after login.
    teacher = User.query.filter_by(email="teacher@phet.test").first()
    if teacher:
        for slug in ("forces-and-motion-basics", "build-an-atom",
                     "ph-scale", "natural-selection"):
            sim = Simulation.query.filter_by(slug=slug).first()
            if sim:
                db.session.add(SavedSimulation(
                    user_id=teacher.id, sim_id=sim.id,
                    notes=f"Use for {sim.title} unit opener.",
                ))
        db.session.commit()


def seed_all():
    seed_subjects()
    seed_grades()
    seed_languages()
    seed_simulations()
    seed_activities()
    seed_benchmark_users()


with app.app_context():
    db.create_all()
    seed_all()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 40029))
    app.run(host="0.0.0.0", port=port, debug=False)
