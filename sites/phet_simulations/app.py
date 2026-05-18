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
    runtime_minutes = db.Column(db.Integer, default=20)
    release_date = db.Column(db.Date)
    download_count = db.Column(db.Integer, default=0)
    play_count = db.Column(db.Integer, default=0)
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
    download_count = db.Column(db.Integer, default=0)
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
    most_played = (
        Simulation.query.order_by(Simulation.play_count.desc())
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
    grade = request.args.get("grade", "").strip()
    language = request.args.get("language", "").strip()
    sort = request.args.get("sort", "title")
    view = request.args.get("view", "filter").strip()
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 24

    query = Simulation.query
    if subject:
        query = query.filter(Simulation.subjects_json.like(f'%"{subject}"%'))
    if grade:
        query = query.filter(Simulation.grades_json.like(f'%"{grade}"%'))
    if language:
        query = query.filter(Simulation.languages_json.like(f'%"{language}"%'))

    if sort == "newest":
        query = query.order_by(Simulation.release_date.desc())
    elif sort == "popular":
        query = query.order_by(Simulation.play_count.desc())
    else:
        query = query.order_by(Simulation.title)

    total = query.count()
    sims = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = max((total + per_page - 1) // per_page, 1)

    any_filter_active = bool(subject or grade or language or sort != "title")
    view_tab = view if view in ("browse", "filter", "customize") else "filter"

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
        grade=grade,
        language=language,
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
    sim = Simulation.query.filter_by(slug=slug).first_or_404()
    sim.play_count = (sim.play_count or 0) + 1
    db.session.commit()

    subjects_full = [
        s for s in Subject.query.filter(Subject.slug.in_(sim.subjects())).all()
    ]
    grades_full = [
        g for g in GradeLevel.query.filter(GradeLevel.slug.in_(sim.grades())).all()
    ]
    langs_full = [
        l for l in Language.query.filter(Language.code.in_(sim.languages())).all()
    ]

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

    is_saved = (
        current_user.is_authenticated
        and SavedSimulation.query.filter_by(
            user_id=current_user.id, sim_id=sim.id,
        ).first()
        is not None
    )

    return render_template(
        "simulation_detail.html",
        sim=sim,
        subjects=subjects_full,
        grades=grades_full,
        languages=langs_full,
        related=related,
        activities=activities,
        is_saved=is_saved,
    )


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    sims = []
    if q:
        pattern = f"%{q}%"
        sims = (
            Simulation.query.filter(
                or_(
                    Simulation.title.ilike(pattern),
                    Simulation.short_description.ilike(pattern),
                    Simulation.topics_json.ilike(pattern),
                )
            )
            .order_by(Simulation.title)
            .all()
        )
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
        Activity.query.order_by(Activity.download_count.desc())
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
    activity.download_count = (activity.download_count or 0) + 1
    db.session.commit()
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

SUBJECTS_SEED = [
    ("physics", "Physics", "atom", "#0079bf",
     "Explore motion, forces, energy, waves, and electromagnetism."),
    ("chemistry", "Chemistry", "flask", "#f5862e",
     "Build molecules, balance equations, and probe matter."),
    ("math", "Math", "function", "#6cba5c",
     "Visualize numbers, fractions, functions, and geometry."),
    ("biology", "Biology", "leaf", "#7a3e9d",
     "Study cells, genetics, evolution, and the human body."),
    ("earth-science", "Earth Science", "globe", "#c0392b",
     "Investigate Earth's systems, climate, and the solar system."),
]

GRADES_SEED = [
    ("elementary", "Elementary School", "Ages 5-10", 1),
    ("middle", "Middle School", "Ages 11-13", 2),
    ("high", "High School", "Ages 14-18", 3),
    ("university", "University", "Ages 18+", 4),
]

LANGUAGES_SEED = [
    ("en", "English", "English", False),
    ("es", "Spanish", "Espanol", False),
    ("zh-cn", "Chinese (Simplified)", "Zhongwen", False),
    ("zh-tw", "Chinese (Traditional)", "Zhongwen", False),
    ("fr", "French", "Francais", False),
    ("de", "German", "Deutsch", False),
    ("pt-br", "Portuguese (Brazilian)", "Portugues", False),
    ("ru", "Russian", "Russkiy", False),
    ("ar", "Arabic", "Al-Arabiyyah", True),
    ("ja", "Japanese", "Nihongo", False),
    ("ko", "Korean", "Hangugeo", False),
    ("it", "Italian", "Italiano", False),
    ("nl", "Dutch", "Nederlands", False),
    ("pl", "Polish", "Polski", False),
    ("sv", "Swedish", "Svenska", False),
    ("tr", "Turkish", "Turkce", False),
    ("vi", "Vietnamese", "Tieng Viet", False),
    ("hi", "Hindi", "Hindi", False),
    ("he", "Hebrew", "Ivrit", True),
    ("el", "Greek", "Ellinika", False),
    ("cs", "Czech", "Cestina", False),
    ("hu", "Hungarian", "Magyar", False),
    ("fi", "Finnish", "Suomi", False),
    ("da", "Danish", "Dansk", False),
    ("ro", "Romanian", "Romana", False),
    ("uk", "Ukrainian", "Ukrayinska", False),
    ("fa", "Persian", "Farsi", True),
    ("id", "Indonesian", "Bahasa Indonesia", False),
]


def _slug(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


SIMULATIONS_SEED = [
    # (title, subjects, grades, topics, languages_extra, featured, is_new, runtime, year, month, day, play_count)
    ("Gravity and Orbits", ["physics", "earth-science"], ["middle", "high"],
     ["gravity", "orbits", "circular motion", "satellites"],
     ["es", "fr", "de", "zh-cn", "ja", "ar", "pt-br", "ru"],
     True, False, 25, 2024, 3, 12, 482103),
    ("Forces and Motion: Basics", ["physics"], ["elementary", "middle", "high"],
     ["newton's laws", "friction", "acceleration"],
     ["es", "fr", "de", "zh-cn", "pt-br", "ru", "ja", "ko", "it", "nl"],
     True, False, 20, 2023, 9, 5, 1204567),
    ("Energy Skate Park", ["physics"], ["middle", "high", "university"],
     ["kinetic energy", "potential energy", "conservation"],
     ["es", "fr", "de", "pt-br", "ru", "zh-cn", "ja"],
     True, False, 30, 2024, 1, 18, 768922),
    ("Wave Interference", ["physics"], ["high", "university"],
     ["waves", "interference", "diffraction", "light"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 25, 2023, 11, 2, 312045),
    ("Faraday's Law", ["physics"], ["high", "university"],
     ["electromagnetism", "induction", "magnetic flux"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 20, 2023, 7, 14, 198320),
    ("Charges and Fields", ["physics"], ["high", "university"],
     ["electrostatics", "electric field", "voltage"],
     ["es", "fr", "de", "pt-br"],
     False, False, 25, 2023, 6, 22, 234110),
    ("Pendulum Lab", ["physics", "math"], ["middle", "high"],
     ["pendulum", "period", "gravity", "harmonic motion"],
     ["es", "fr", "de", "zh-cn", "ja", "ko"],
     True, False, 20, 2024, 2, 9, 521987),
    ("Projectile Motion", ["physics"], ["high", "university"],
     ["kinematics", "trajectory", "air resistance"],
     ["es", "fr", "de", "zh-cn", "pt-br", "ja"],
     False, False, 25, 2023, 10, 28, 645321),
    ("Circuit Construction Kit: DC", ["physics"], ["middle", "high", "university"],
     ["circuits", "ohm's law", "resistance", "current"],
     ["es", "fr", "de", "pt-br", "zh-cn", "ja", "ko", "ru", "it"],
     True, False, 30, 2024, 4, 1, 892341),
    ("Bending Light", ["physics"], ["middle", "high"],
     ["refraction", "snell's law", "optics"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 20, 2023, 8, 15, 167823),
    ("Color Vision", ["physics", "biology"], ["elementary", "middle"],
     ["light", "color", "vision", "wavelength"],
     ["es", "fr", "de", "ja"],
     False, False, 15, 2023, 5, 19, 198765),
    ("Coulomb's Law", ["physics"], ["high", "university"],
     ["electrostatics", "force", "charge"],
     ["es", "fr", "de"],
     False, True, 20, 2025, 1, 14, 89234),
    ("Hooke's Law", ["physics"], ["middle", "high"],
     ["springs", "elasticity", "force"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 15, 2023, 4, 7, 154322),
    ("Magnet and Compass", ["physics", "earth-science"], ["elementary", "middle"],
     ["magnetism", "compass", "field lines"],
     ["es", "fr", "de", "zh-cn", "ja", "ar"],
     False, False, 15, 2023, 3, 21, 232109),
    ("Resistance in a Wire", ["physics"], ["high"],
     ["resistance", "resistivity", "circuits"],
     ["es", "fr", "de"],
     False, False, 15, 2023, 2, 4, 87654),
    ("Quantum Wave Interference", ["physics"], ["university"],
     ["quantum mechanics", "wave-particle duality"],
     ["es", "fr", "de"],
     False, True, 35, 2025, 2, 28, 45120),

    ("Build a Molecule", ["chemistry"], ["middle", "high"],
     ["molecules", "atoms", "bonding"],
     ["es", "fr", "de", "zh-cn", "ja", "pt-br", "ru"],
     True, False, 25, 2024, 1, 22, 678901),
    ("Balancing Chemical Equations", ["chemistry"], ["middle", "high"],
     ["stoichiometry", "equations", "reactions"],
     ["es", "fr", "de", "zh-cn", "pt-br", "ko"],
     True, False, 20, 2023, 12, 6, 543210),
    ("States of Matter", ["chemistry", "physics"], ["elementary", "middle", "high"],
     ["solid", "liquid", "gas", "phase change"],
     ["es", "fr", "de", "zh-cn", "ja", "ar", "pt-br", "ru", "it"],
     True, False, 25, 2024, 2, 14, 891234),
    ("Concentration", ["chemistry"], ["high", "university"],
     ["solutions", "molarity", "dilution"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 20, 2023, 11, 9, 234567),
    ("pH Scale", ["chemistry"], ["middle", "high"],
     ["acids", "bases", "ph", "hydrogen ions"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 15, 2023, 9, 17, 312456),
    ("Beer's Law Lab", ["chemistry"], ["high", "university"],
     ["absorbance", "spectroscopy", "concentration"],
     ["es", "fr", "de"],
     False, False, 25, 2023, 8, 3, 167890),
    ("Acid-Base Solutions", ["chemistry"], ["high", "university"],
     ["acids", "bases", "equilibrium"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 25, 2023, 7, 25, 198432),
    ("Reactions and Rates", ["chemistry"], ["high", "university"],
     ["kinetics", "reactions", "activation energy"],
     ["es", "fr", "de"],
     False, False, 30, 2023, 6, 11, 145678),
    ("Molecule Polarity", ["chemistry"], ["high"],
     ["polarity", "electronegativity", "dipole"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 20, 2023, 5, 8, 123456),
    ("Isotopes and Atomic Mass", ["chemistry"], ["high", "university"],
     ["isotopes", "atomic mass", "elements"],
     ["es", "fr", "de"],
     False, False, 20, 2023, 4, 16, 98765),
    ("Build an Atom", ["chemistry", "physics"], ["middle", "high"],
     ["atoms", "protons", "neutrons", "electrons"],
     ["es", "fr", "de", "zh-cn", "ja", "ko", "ar", "ru", "pt-br"],
     True, False, 20, 2024, 3, 7, 712345),
    ("Salts and Solubility", ["chemistry"], ["high"],
     ["solubility", "salts", "saturation"],
     ["es", "fr", "de"],
     False, True, 25, 2025, 3, 4, 56789),

    ("Graphing Lines", ["math"], ["middle", "high"],
     ["linear equations", "slope", "intercept"],
     ["es", "fr", "de", "zh-cn", "ja", "ko", "ar"],
     True, False, 20, 2024, 1, 11, 567890),
    ("Area Builder", ["math"], ["elementary", "middle"],
     ["area", "perimeter", "shapes"],
     ["es", "fr", "de", "zh-cn", "ja", "pt-br"],
     False, False, 15, 2023, 10, 14, 234567),
    ("Fractions: Intro", ["math"], ["elementary", "middle"],
     ["fractions", "numerators", "denominators"],
     ["es", "fr", "de", "zh-cn", "ja", "ar", "pt-br", "ru"],
     True, False, 15, 2024, 2, 19, 689012),
    ("Function Builder", ["math"], ["middle", "high"],
     ["functions", "input output", "composition"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 25, 2023, 9, 21, 178901),
    ("Plinko Probability", ["math"], ["middle", "high", "university"],
     ["probability", "distributions", "statistics"],
     ["es", "fr", "de"],
     False, False, 20, 2023, 8, 6, 145678),
    ("Trig Tour", ["math"], ["high", "university"],
     ["trigonometry", "sine", "cosine", "unit circle"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 25, 2023, 7, 30, 123890),
    ("Vector Addition", ["math", "physics"], ["high", "university"],
     ["vectors", "components", "magnitude"],
     ["es", "fr", "de"],
     False, False, 20, 2023, 6, 8, 156789),
    ("Calculus Grapher", ["math"], ["high", "university"],
     ["derivatives", "integrals", "calculus"],
     ["es", "fr", "de"],
     False, True, 30, 2025, 1, 22, 67890),
    ("Equality Explorer", ["math"], ["elementary", "middle"],
     ["equations", "balance", "variables"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 20, 2023, 5, 12, 134567),
    ("Number Line: Integers", ["math"], ["elementary", "middle"],
     ["integers", "negative numbers", "number line"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 15, 2023, 4, 19, 98765),
    ("Make a Ten", ["math"], ["elementary"],
     ["addition", "place value", "counting"],
     ["es", "fr", "zh-cn", "ja"],
     False, False, 10, 2023, 3, 25, 78901),
    ("Estimation", ["math"], ["elementary", "middle"],
     ["estimation", "measurement", "comparison"],
     ["es", "fr", "de"],
     False, False, 15, 2023, 2, 16, 65432),

    ("Natural Selection", ["biology"], ["middle", "high", "university"],
     ["evolution", "adaptation", "selection"],
     ["es", "fr", "de", "zh-cn", "ja", "pt-br"],
     True, False, 30, 2024, 1, 27, 412567),
    ("Gene Expression Essentials", ["biology"], ["high", "university"],
     ["dna", "transcription", "translation", "proteins"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 25, 2023, 11, 23, 234890),
    ("Neuron", ["biology"], ["high", "university"],
     ["neurons", "action potential", "ion channels"],
     ["es", "fr", "de"],
     False, False, 25, 2023, 10, 5, 187654),
    ("Membrane Channels", ["biology"], ["high", "university"],
     ["membranes", "diffusion", "transport"],
     ["es", "fr", "de"],
     False, False, 20, 2023, 9, 12, 145623),
    ("Stretching DNA", ["biology", "physics"], ["high", "university"],
     ["dna", "forces", "molecular biology"],
     ["es", "fr", "de"],
     False, False, 25, 2023, 8, 28, 112345),
    ("Eating and Exercise", ["biology"], ["middle", "high"],
     ["nutrition", "metabolism", "calories"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 20, 2023, 7, 17, 167890),

    ("Plate Tectonics", ["earth-science"], ["middle", "high"],
     ["plates", "continents", "earthquakes"],
     ["es", "fr", "de", "zh-cn", "ja"],
     True, False, 25, 2024, 2, 5, 389012),
    ("Greenhouse Effect", ["earth-science", "physics"], ["middle", "high"],
     ["climate", "atmosphere", "radiation"],
     ["es", "fr", "de", "zh-cn", "pt-br"],
     True, False, 25, 2024, 3, 18, 456789),
    ("Glaciers", ["earth-science"], ["middle", "high"],
     ["glaciers", "climate", "ice"],
     ["es", "fr", "de"],
     False, False, 20, 2023, 11, 14, 123456),
    ("Density", ["earth-science", "physics"], ["elementary", "middle", "high"],
     ["density", "mass", "volume", "buoyancy"],
     ["es", "fr", "de", "zh-cn", "ja", "ar"],
     True, False, 20, 2024, 1, 30, 567823),
    ("My Solar System", ["earth-science", "physics"], ["middle", "high", "university"],
     ["gravity", "orbits", "solar system"],
     ["es", "fr", "de", "zh-cn", "ja", "ar", "pt-br"],
     True, False, 30, 2024, 4, 11, 678901),
    ("Radioactive Dating Game", ["earth-science", "physics"], ["high"],
     ["radioactivity", "half-life", "dating"],
     ["es", "fr", "de"],
     False, False, 25, 2023, 6, 23, 134567),
    ("Lunar Lander", ["earth-science", "physics"], ["middle", "high"],
     ["gravity", "thrust", "motion"],
     ["es", "fr", "de", "ja"],
     False, True, 20, 2025, 2, 17, 78901),

    # Additional biology sims
    ("Mendelian Genetics", ["biology"], ["middle", "high", "university"],
     ["genetics", "heredity", "alleles", "punnett squares"],
     ["es", "fr", "de", "zh-cn", "ja", "pt-br"],
     True, False, 30, 2024, 2, 22, 287654),
    ("DNA Replication", ["biology"], ["high", "university"],
     ["dna", "replication", "polymerase"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 25, 2023, 12, 17, 178923),
    ("Photosynthesis", ["biology"], ["elementary", "middle", "high"],
     ["photosynthesis", "chlorophyll", "plants", "light"],
     ["es", "fr", "de", "zh-cn", "ja", "ko", "pt-br"],
     True, False, 25, 2024, 3, 9, 421890),
    ("Predator-Prey Dynamics", ["biology"], ["middle", "high"],
     ["ecology", "population", "food chain"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 30, 2023, 11, 26, 198765),
    ("Cellular Respiration", ["biology", "chemistry"], ["high", "university"],
     ["respiration", "atp", "mitochondria", "energy"],
     ["es", "fr", "de"],
     False, False, 25, 2023, 10, 13, 156789),
    ("Punnett Squares", ["biology"], ["middle", "high"],
     ["genetics", "heredity", "punnett squares"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 20, 2023, 9, 8, 234156),
    ("Population Dynamics", ["biology", "math"], ["high", "university"],
     ["population", "exponential growth", "carrying capacity"],
     ["es", "fr", "de"],
     False, True, 30, 2025, 1, 8, 67890),
    ("Cell Diffusion", ["biology"], ["middle", "high"],
     ["diffusion", "membranes", "concentration"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 20, 2023, 8, 19, 132465),
    ("Enzyme Kinetics", ["biology", "chemistry"], ["high", "university"],
     ["enzymes", "catalysis", "kinetics"],
     ["es", "fr", "de"],
     False, False, 25, 2023, 7, 11, 98432),
    ("Food Web Builder", ["biology"], ["elementary", "middle"],
     ["ecology", "food web", "trophic levels"],
     ["es", "fr", "de", "zh-cn", "ja", "ar"],
     False, False, 25, 2023, 6, 4, 187234),
    ("Mitosis and Meiosis", ["biology"], ["high", "university"],
     ["cell division", "chromosomes", "mitosis", "meiosis"],
     ["es", "fr", "de"],
     False, False, 30, 2023, 5, 17, 145678),
    ("Blood Pressure Basics", ["biology"], ["middle", "high"],
     ["circulation", "heart", "blood pressure"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 20, 2023, 4, 22, 87654),
    ("Lac Operon Regulation", ["biology"], ["university"],
     ["gene regulation", "operon", "molecular biology"],
     ["es", "fr", "de"],
     False, False, 30, 2023, 3, 12, 54321),
    ("Bee Hive Activity", ["biology"], ["elementary", "middle"],
     ["pollination", "bees", "ecosystems"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 15, 2023, 2, 28, 76543),

    # Additional earth-science sims
    ("Seasons", ["earth-science"], ["elementary", "middle"],
     ["seasons", "earth tilt", "sun"],
     ["es", "fr", "de", "zh-cn", "ja", "ar"],
     True, False, 20, 2024, 1, 19, 312456),
    ("Water Cycle", ["earth-science"], ["elementary", "middle", "high"],
     ["evaporation", "condensation", "precipitation", "water cycle"],
     ["es", "fr", "de", "zh-cn", "ja", "ko", "pt-br"],
     True, False, 20, 2024, 2, 26, 398765),
    ("Volcanic Eruption", ["earth-science"], ["elementary", "middle", "high"],
     ["volcanoes", "magma", "lava", "geology"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 25, 2023, 12, 10, 234567),
    ("Earthquake Simulator", ["earth-science"], ["middle", "high"],
     ["earthquakes", "seismic waves", "magnitude"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 25, 2023, 11, 18, 198432),
    ("Tides", ["earth-science", "physics"], ["middle", "high"],
     ["tides", "gravity", "moon", "ocean"],
     ["es", "fr", "de"],
     False, False, 20, 2023, 10, 27, 167890),
    ("Climate Change Model", ["earth-science"], ["high", "university"],
     ["climate", "greenhouse gases", "temperature"],
     ["es", "fr", "de", "zh-cn", "pt-br"],
     True, True, 35, 2025, 2, 8, 89012),
    ("Ozone Layer", ["earth-science", "chemistry"], ["middle", "high"],
     ["ozone", "atmosphere", "uv radiation"],
     ["es", "fr", "de"],
     False, False, 20, 2023, 9, 14, 123456),
    ("Solar Wind", ["earth-science", "physics"], ["high", "university"],
     ["solar wind", "magnetosphere", "auroras"],
     ["es", "fr", "de"],
     False, False, 25, 2023, 8, 22, 87432),
    ("Rock Cycle", ["earth-science"], ["elementary", "middle", "high"],
     ["rocks", "minerals", "igneous", "sedimentary", "metamorphic"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 25, 2023, 7, 6, 156789),
    ("Ocean Currents", ["earth-science"], ["middle", "high"],
     ["ocean", "currents", "thermohaline"],
     ["es", "fr", "de"],
     False, False, 25, 2023, 6, 18, 112345),
    ("Mineral Hardness", ["earth-science"], ["elementary", "middle"],
     ["minerals", "mohs scale", "geology"],
     ["es", "fr", "de"],
     False, False, 15, 2023, 5, 30, 76543),
    ("Mountain Building", ["earth-science"], ["middle", "high"],
     ["tectonics", "mountains", "erosion"],
     ["es", "fr", "de"],
     False, False, 25, 2023, 4, 11, 98765),

    # More elementary-friendly sims
    ("Shapes and Patterns", ["math"], ["elementary"],
     ["shapes", "patterns", "geometry"],
     ["es", "fr", "de", "zh-cn", "ja", "ko"],
     False, False, 15, 2023, 3, 18, 134567),
    ("Counting Coins", ["math"], ["elementary"],
     ["counting", "money", "addition"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 12, 2023, 2, 23, 87654),
    ("Simple Machines", ["physics"], ["elementary", "middle"],
     ["levers", "pulleys", "wheels", "force"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 20, 2023, 4, 27, 165432),
    ("Magnet Toy", ["physics"], ["elementary"],
     ["magnets", "attraction", "repulsion"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 12, 2023, 5, 9, 98432),
    ("Weather Watcher", ["earth-science"], ["elementary"],
     ["weather", "clouds", "temperature"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 15, 2023, 6, 13, 76543),
    ("Plant Growth", ["biology"], ["elementary"],
     ["plants", "growth", "seeds"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 15, 2023, 7, 21, 54321),
    ("Animal Classification", ["biology"], ["elementary"],
     ["animals", "classification", "vertebrates"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 15, 2023, 8, 9, 87654),

    # More chemistry sims (to clear 20+ threshold)
    ("Atomic Interactions", ["chemistry", "physics"], ["high", "university"],
     ["atoms", "forces", "lennard-jones"],
     ["es", "fr", "de"],
     False, False, 20, 2023, 3, 14, 123890),
    ("Sugar and Salt Solutions", ["chemistry"], ["middle", "high"],
     ["solutions", "dissolving", "concentration"],
     ["es", "fr", "de", "zh-cn", "ja", "pt-br"],
     False, False, 20, 2023, 11, 6, 198765),
    ("Gas Properties", ["chemistry", "physics"], ["high", "university"],
     ["gases", "pressure", "temperature", "kinetic theory"],
     ["es", "fr", "de", "zh-cn"],
     True, False, 25, 2024, 1, 25, 287654),
    ("Diffusion in Gases", ["chemistry", "physics"], ["middle", "high"],
     ["diffusion", "gases", "concentration"],
     ["es", "fr", "de"],
     False, False, 20, 2023, 10, 19, 134567),
    ("Bonding Explorer", ["chemistry"], ["high"],
     ["bonding", "ionic", "covalent", "metallic"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 25, 2023, 9, 28, 156789),
    ("Reaction Quizzer", ["chemistry"], ["high", "university"],
     ["reactions", "products", "balancing"],
     ["es", "fr", "de"],
     False, False, 20, 2023, 8, 11, 87654),

    # More math sims (to clear 20+ threshold)
    ("Probability Experiments", ["math"], ["middle", "high"],
     ["probability", "experiments", "statistics"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 20, 2023, 11, 21, 167890),
    ("Coordinate Plane", ["math"], ["middle", "high"],
     ["coordinates", "graphs", "plotting"],
     ["es", "fr", "de", "zh-cn"],
     False, False, 15, 2023, 9, 30, 145678),
    ("Algebra Tiles", ["math"], ["middle", "high"],
     ["algebra", "polynomials", "factoring"],
     ["es", "fr", "de"],
     False, False, 25, 2023, 8, 17, 123456),
    ("Percent Word Problems", ["math"], ["middle"],
     ["percentages", "ratios", "word problems"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 20, 2023, 7, 9, 98432),
    ("Geometric Constructions", ["math"], ["middle", "high"],
     ["geometry", "compass", "straightedge"],
     ["es", "fr", "de"],
     False, False, 25, 2023, 6, 5, 87654),
    ("Decimal Models", ["math"], ["elementary", "middle"],
     ["decimals", "place value", "comparison"],
     ["es", "fr", "de", "zh-cn", "ja"],
     False, False, 15, 2023, 5, 14, 134567),
]


ACTIVITIES_SEED = [
    ("Forces and Motion: Basics", "Net Force Investigation",
     "Dr. Trish Loeblein", "high", 50,
     "Students predict, observe, and explain the motion of objects with "
     "balanced and unbalanced forces using friction and applied force."),
    ("Build an Atom", "Atomic Structure Lab",
     "Emily Moore", "middle", 45,
     "Build atoms of the first 10 elements, identify subatomic particles, "
     "and explore how protons determine the element."),
    ("Balancing Chemical Equations", "Coefficient Practice",
     "Yuen-Ying Carpenter", "high", 60,
     "Practice balancing combustion, synthesis, and decomposition reactions "
     "using the conservation of mass."),
    ("States of Matter", "Phase Change Inquiry",
     "Sam McKagan", "middle", 40,
     "Investigate the relationship between temperature, kinetic energy, "
     "and phase transitions for water, neon, oxygen, and argon."),
    ("Natural Selection", "Evolution of Bunnies",
     "Wendy Adams", "high", 55,
     "Model how variation, environment, and selection pressure together "
     "drive allele frequency change across generations."),
    ("Gravity and Orbits", "Modeling the Solar System",
     "Noah Finkelstein", "middle", 50,
     "Manipulate masses and distances to explore how gravitational force "
     "shapes planetary orbits in our solar system."),
    ("pH Scale", "Acids and Bases in the Kitchen",
     "Kelly Lancaster", "middle", 40,
     "Predict, measure, and rank common household solutions by pH and "
     "categorize each as acid, base, or neutral."),
    ("Plate Tectonics", "Boundary Identification",
     "Karina Hensberry", "high", 45,
     "Use animations to classify convergent, divergent, and transform "
     "boundaries and connect each to real-world geologic features."),
    ("Greenhouse Effect", "Climate Modeling Lab",
     "Trish Loeblein", "high", 60,
     "Model how atmospheric composition affects equilibrium temperature "
     "with and without greenhouse gases."),
    ("Circuit Construction Kit: DC", "Series and Parallel",
     "John De La Cruz", "high", 50,
     "Compare current and voltage in series vs parallel arrangements "
     "and verify Kirchhoff's laws empirically."),
    ("Fractions: Intro", "Equivalent Fractions Game",
     "Amanda McGarry", "elementary", 30,
     "Use bar models, number lines, and circle models to identify "
     "equivalent fractions and develop fluency."),
    ("Energy Skate Park", "Conservation of Energy",
     "Karina Hensberry", "high", 55,
     "Track potential, kinetic, thermal, and total energy as a skater "
     "moves through changing terrain."),
    ("Density", "Identify the Mystery Block",
     "Emily Moore", "middle", 35,
     "Use mass and volume measurements to identify the material of "
     "unknown solid blocks and explain buoyancy in water."),
    ("Graphing Lines", "Slope-Intercept Form",
     "Dr. Karina Hensberry", "middle", 40,
     "Investigate how m and b transform the line y = mx + b and apply "
     "this to real-world rate problems."),
]


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
        db.session.add(Subject(
            slug=slug, name=name, icon=icon, color=color, description=desc,
        ))
    db.session.commit()


def seed_grades():
    if GradeLevel.query.count() > 0:
        return
    for slug, name, age_range, sort_order in GRADES_SEED:
        db.session.add(GradeLevel(
            slug=slug, name=name, age_range=age_range, sort_order=sort_order,
        ))
    db.session.commit()


def seed_languages():
    if Language.query.count() > 0:
        return
    for code, name, native, rtl in LANGUAGES_SEED:
        db.session.add(Language(
            code=code, name=name, native_name=native, is_rtl=rtl, sim_count=0,
        ))
    db.session.commit()


def seed_simulations():
    if Simulation.query.count() > 0:
        return
    for row in SIMULATIONS_SEED:
        (title, subjects, grades, topics, extra_langs,
         featured, is_new, runtime, year, month, day, plays) = row
        slug = _slug(title)
        languages = ["en"] + list(extra_langs)
        sim = Simulation(
            slug=slug,
            title=title,
            short_description=_make_short_desc(title, topics),
            overview=_make_overview(title, topics, subjects),
            subjects_json=json.dumps(subjects),
            grades_json=json.dumps(grades),
            topics_json=json.dumps(topics),
            languages_json=json.dumps(languages),
            is_html5=True,
            is_featured=featured,
            is_new=is_new,
            thumbnail=f"{slug}.svg",
            runtime_minutes=runtime,
            release_date=date(year, month, day),
            play_count=plays,
            download_count=max(plays // 8, 1000),
        )
        db.session.add(sim)
    db.session.commit()

    # update per-language sim counts
    lang_counts = {l.code: 0 for l in Language.query.all()}
    for sim in Simulation.query.all():
        for code in sim.languages():
            if code in lang_counts:
                lang_counts[code] += 1
    for code, count in lang_counts.items():
        lang = Language.query.filter_by(code=code).first()
        if lang:
            lang.sim_count = count
    db.session.commit()


def seed_activities():
    if Activity.query.count() > 0:
        return
    for sim_title, title, author, grade, duration, desc in ACTIVITIES_SEED:
        sim = Simulation.query.filter_by(slug=_slug(sim_title)).first()
        if not sim:
            continue
        db.session.add(Activity(
            sim_id=sim.id,
            title=title,
            author=author,
            grade_level=grade,
            duration_min=duration,
            description=desc,
            file_type="PDF",
            download_count=max(duration * 137 % 9000, 350),
            published_date=date(2024, ((duration % 12) + 1), 15),
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


def _make_short_desc(title, topics):
    if not topics:
        return f"Interactive simulation: {title}."
    topic_str = ", ".join(topics[:3])
    return f"Explore {topic_str} with the interactive {title} simulation."


def _make_overview(title, topics, subjects):
    subject_names = ", ".join(s.replace("-", " ").title() for s in subjects)
    topic_list = ", ".join(topics) if topics else "core concepts"
    return (
        f"{title} is an interactive HTML5 simulation in the PhET "
        f"{subject_names} collection. Learners investigate {topic_list} "
        f"by directly manipulating model parameters and observing "
        f"real-time visual feedback. The simulation supports inquiry-"
        f"based instruction, formative assessment, and at-home practice, "
        f"and is freely available under a Creative Commons license."
    )


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
    port = int(os.environ.get("PORT", 40015))
    app.run(host="0.0.0.0", port=port, debug=False)
