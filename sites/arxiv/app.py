"""
arxiv.org mirror - Flask application.

Adaptation of the mirror-web pattern to a reference/research site:
  Entity      = Paper
  Category    = Subject Area (cs, math, physics, ...)
  Cart        = Library (saved papers for reading later)
  Order       = Download Log / Citation Export
  Wishlist    = Starred Papers
  Review      = Comment on a paper
"""
import os
import re
import json
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify,
    session, abort, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from sqlalchemy import or_, and_, func

from metadata_cleaning import clean_arxiv_metadata_text, format_arxiv_display_text

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "instance"
DB_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "arxiv-mirror-secret-key-change-in-prod-1234567890"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_DIR / 'arxiv.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None  # session-length CSRF
app.config["TEMPLATES_AUTO_RELOAD"] = True  # pick up template edits in long-running container

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
csrf = CSRFProtect(app)


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
    affiliation = db.Column(db.String(200), default="")
    bio = db.Column(db.Text, default="")
    orcid = db.Column(db.String(40), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    library_items = db.relationship("LibraryItem", backref="user", cascade="all, delete-orphan")
    starred = db.relationship("StarredPaper", backref="user", cascade="all, delete-orphan")
    exports = db.relationship("Export", backref="user", cascade="all, delete-orphan")
    comments = db.relationship("Comment", backref="user", cascade="all, delete-orphan")
    alerts = db.relationship("Alert", backref="user", cascade="all, delete-orphan")

    def set_password(self, raw: str):
        self.password_hash = bcrypt.generate_password_hash(raw).decode("utf-8")

    def check_password(self, raw: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw)


class Category(db.Model):
    """A top-level subject area (cs, math, physics, ...)"""
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    icon = db.Column(db.String(20), default="📚")
    color = db.Column(db.String(20), default="#b31b1b")
    short_name = db.Column(db.String(40), default="")
    parent_code = db.Column(db.String(40), default="")  # for grouping (e.g. astro-ph under Physics)
    description = db.Column(db.Text, default="")

    @property
    def paper_count(self):
        return Paper.query.filter(
            or_(Paper.primary_subject_code == self.code,
                Paper.primary_subject_code.like(f"{self.code}.%"))
        ).count()


class Paper(db.Model):
    """A single research paper / e-print."""
    __tablename__ = "papers"
    id = db.Column(db.Integer, primary_key=True)
    arxiv_id = db.Column(db.String(40), unique=True, nullable=False, index=True)
    title = db.Column(db.Text, nullable=False)
    abstract = db.Column(db.Text, default="")
    authors_json = db.Column(db.Text, default="[]")  # JSON list of author name strings
    subjects = db.Column(db.Text, default="")  # e.g. "Artificial Intelligence (cs.AI); Computation..."
    primary_subject = db.Column(db.String(200), default="")  # "Artificial Intelligence (cs.AI)"
    primary_subject_code = db.Column(db.String(40), default="", index=True)  # "cs.AI"
    primary_category_code = db.Column(db.String(20), default="", index=True)  # "cs"
    submitted_date = db.Column(db.String(40), default="")
    submitted_year = db.Column(db.Integer, default=0, index=True)
    submitted_month = db.Column(db.Integer, default=0)
    submitted_day = db.Column(db.Integer, default=0)
    announce_date = db.Column(db.String(40), default="")  # Date the paper was announced in listings
    comments = db.Column(db.Text, default="")  # "12 pages, 5 figures"
    journal_ref = db.Column(db.String(400), default="", index=True)
    doi = db.Column(db.String(200), default="")
    pdf_url = db.Column(db.String(400), default="")
    html_url = db.Column(db.String(400), default="")
    html_available = db.Column(db.Boolean, default=True)
    n_authors = db.Column(db.Integer, default=0, index=True)
    figures_count = db.Column(db.Integer, default=0)
    tables_count = db.Column(db.Integer, default=0)
    formulas_count = db.Column(db.Integer, default=0)
    loss_function = db.Column(db.Text, default="")
    versions_json = db.Column(db.Text, default="[]")  # JSON list of {version, date}
    # Parallel list of author affiliations, same order as authors_json. Stored
    # as JSON list of strings (may contain "" for unknown). Deterministically
    # synthesised at seed time from a hash of the author name.
    author_affiliations_json = db.Column(db.Text, default="[]")
    view_count = db.Column(db.Integer, default=0)
    download_count = db.Column(db.Integer, default=0)
    star_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    comments_rel = db.relationship("Comment", backref="paper", cascade="all, delete-orphan")
    library_items = db.relationship("LibraryItem", backref="paper", cascade="all, delete-orphan")
    starred = db.relationship("StarredPaper", backref="paper", cascade="all, delete-orphan")

    def get_authors(self) -> list:
        try:
            return json.loads(self.authors_json or "[]")
        except Exception:
            return []

    def get_author_affiliations(self) -> list:
        """Return a list of affiliation strings, aligned with get_authors().

        If the stored list is shorter than the author list, pads with
        deterministically-synthesised affiliations derived from the author
        name, so every author always has a visible affiliation.
        """
        authors = self.get_authors()
        try:
            affs = json.loads(self.author_affiliations_json or "[]")
        except Exception:
            affs = []
        if not isinstance(affs, list):
            affs = []
        # Pad / repair
        out = []
        for i, a in enumerate(authors):
            if i < len(affs) and affs[i]:
                out.append(affs[i])
            else:
                out.append(_synthesize_affiliation(a))
        return out

    def get_authors_with_affiliations(self) -> list:
        authors = self.get_authors()
        affs = self.get_author_affiliations()
        return [
            {"name": a, "affiliation": (affs[i] if i < len(affs) else "")}
            for i, a in enumerate(authors)
        ]

    @property
    def first_author(self):
        a = self.get_authors()
        return a[0] if a else ""

    @property
    def first_author_affiliation(self):
        affs = self.get_author_affiliations()
        return affs[0] if affs else ""

    @property
    def authors_display(self):
        a = self.get_authors()
        if not a:
            return ""
        if len(a) > 3:
            return ", ".join(a[:3]) + f", et al. ({len(a)} authors)"
        return ", ".join(a)

    @property
    def short_abstract(self):
        abstract = self.display_abstract
        if not abstract:
            return "Abstract not available."
        if len(abstract) > 280:
            return abstract[:280] + "…"
        return abstract

    @property
    def display_title(self):
        return format_arxiv_display_text(self.title or "")

    @property
    def display_abstract(self):
        return format_arxiv_display_text(self.abstract or "")

    @property
    def display_comments(self):
        return format_arxiv_display_text(self.comments or "")

    @property
    def display_journal_ref(self):
        return format_arxiv_display_text(self.journal_ref or "")

    @property
    def subject_list(self):
        if not self.subjects:
            return []
        return [s.strip() for s in self.subjects.split(";") if s.strip()]

    def get_versions(self) -> list:
        try:
            return json.loads(self.versions_json or "[]")
        except Exception:
            return []


class LibraryItem(db.Model):
    """A paper saved to a user's Library (the 'cart' analog)."""
    __tablename__ = "library_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    paper_id = db.Column(db.Integer, db.ForeignKey("papers.id"), nullable=False)
    folder = db.Column(db.String(100), default="Reading List")
    note = db.Column(db.Text, default="")
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "paper_id", name="_user_paper_uc"),)


class StarredPaper(db.Model):
    """A starred paper (wishlist analog)."""
    __tablename__ = "starred_papers"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    paper_id = db.Column(db.Integer, db.ForeignKey("papers.id"), nullable=False)
    starred_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "paper_id", name="_user_star_uc"),)


class Export(db.Model):
    """A citation export / bulk download (the 'order' analog)."""
    __tablename__ = "exports"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    export_id = db.Column(db.String(40), unique=True, nullable=False)
    format = db.Column(db.String(20), default="bibtex")  # bibtex, endnote, ris
    status = db.Column(db.String(20), default="ready")  # preparing, ready, cancelled
    paper_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, default="")
    items = db.relationship("ExportItem", backref="export", cascade="all, delete-orphan")


class ExportItem(db.Model):
    __tablename__ = "export_items"
    id = db.Column(db.Integer, primary_key=True)
    export_id = db.Column(db.Integer, db.ForeignKey("exports.id"), nullable=False)
    paper_id = db.Column(db.Integer, db.ForeignKey("papers.id"), nullable=False)
    paper = db.relationship("Paper")


class Comment(db.Model):
    """User comment on a paper (review analog)."""
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    paper_id = db.Column(db.Integer, db.ForeignKey("papers.id"), nullable=False)
    title = db.Column(db.String(200), default="")
    body = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=0)  # 0-5 stars (optional)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Alert(db.Model):
    """Subscription to a category for email alerts."""
    __tablename__ = "alerts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_code = db.Column(db.String(40), nullable=False)
    frequency = db.Column(db.String(20), default="weekly")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =======================================================================
# LOGIN MANAGER
# =======================================================================

@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# =======================================================================
# SEED DATA
# =======================================================================

# Deterministic stub banks for filling in missing author lists / abstracts.
_STUB_FIRST_NAMES = [
    "Alex", "Wei", "Yuki", "Maya", "Rahul", "Sofia", "Hiroshi", "Priya",
    "Elena", "Jian", "Daniel", "Anika", "Mohamed", "Chen", "Ana", "Luca",
    "Nina", "Tomas", "Ravi", "Aisha", "Keiko", "Oscar", "Jia", "Amir",
    "Lena", "Sam", "Noah", "Fatima", "Yao", "Ivan",
]
_STUB_LAST_NAMES = [
    "Chen", "Kumar", "Silva", "Okafor", "Ivanov", "Tanaka", "Kim", "Singh",
    "Garcia", "Zhou", "Muller", "Rossi", "Patel", "Schmidt", "Nguyen",
    "Larsson", "Hassan", "Andersson", "Popov", "Kowalski", "Fernandez",
    "Navarro", "Park", "Zhang", "Li", "Sato", "Johansson", "Haddad",
    "Petrov", "Bianchi",
]
_CATEGORY_BLURBS = {
    "cs.CL": ("We present a new approach to computational linguistics that "
              "combines large-scale pretraining with structured evaluation. "
              "Our method improves downstream performance on a suite of "
              "language understanding benchmarks while remaining efficient "
              "to deploy in realistic settings."),
    "cs.LG": ("We investigate a novel learning algorithm with theoretical "
              "guarantees and strong empirical performance on standard "
              "machine-learning benchmarks. Ablations show that each "
              "component contributes to the overall gains."),
    "cs.CV": ("We propose a vision model that improves recognition and "
              "generation accuracy under challenging conditions. Experiments "
              "on standard image benchmarks demonstrate consistent gains "
              "over strong baselines."),
    "cs.AI": ("We introduce an AI system that reasons over structured and "
              "unstructured inputs to produce more reliable decisions. We "
              "report improvements on multiple reasoning benchmarks."),
    "cs.SY": ("We study a control and systems problem motivated by modern "
              "cyber-physical applications. The proposed controller achieves "
              "provable stability and favourable tracking behaviour in "
              "simulation."),
    "eess.SY": ("This work addresses a systems-and-control problem with a "
                "data-driven controller synthesis pipeline, demonstrating "
                "robustness to disturbances and model uncertainty."),
    "quant-ph": ("We analyse a quantum information protocol that trades off "
                 "resource cost against fidelity. Our results shed light on "
                 "the feasibility of near-term quantum devices for this task."),
    "stat.ML": ("We develop a statistical learning method with non-asymptotic "
                "guarantees, and validate it on benchmark datasets where it "
                "matches or exceeds the state of the art."),
    "astro-ph.SR": ("We report new observations and modelling of stellar "
                    "phenomena that constrain theoretical predictions for "
                    "solar and stellar structure."),
    "astro-ph.EP": ("We present an analysis of planetary and earth-science "
                    "data, with implications for the formation and evolution "
                    "of planetary systems."),
}


def _synthesize_authors(arxiv_id: str) -> list:
    """Deterministically synthesise a 2-5 person author list from arxiv_id."""
    if not arxiv_id:
        return []
    digest = hashlib.md5(arxiv_id.encode("utf-8")).digest()
    n_authors = 2 + (digest[0] % 4)  # 2..5
    names = []
    for i in range(n_authors):
        fi = digest[(i * 2) % len(digest)] % len(_STUB_FIRST_NAMES)
        li = digest[(i * 2 + 1) % len(digest)] % len(_STUB_LAST_NAMES)
        names.append(f"{_STUB_FIRST_NAMES[fi]} {_STUB_LAST_NAMES[li]}")
    return names


_STUB_AFFILIATIONS = [
    "Massachusetts Institute of Technology",
    "Stanford University",
    "University of California, Berkeley",
    "Carnegie Mellon University",
    "ETH Zurich",
    "University of Cambridge",
    "University of Oxford",
    "Tsinghua University",
    "Peking University",
    "University of Toronto",
    "California Institute of Technology",
    "Princeton University",
    "Harvard University",
    "Cornell University",
    "University of Illinois Urbana-Champaign",
    "University of Tokyo",
    "Max Planck Institute",
    "Imperial College London",
    "National University of Singapore",
    "Seoul National University",
    "University of Michigan",
    "Columbia University",
    "Yale University",
    "University of Chicago",
    "University of Washington",
    "Georgia Institute of Technology",
    "Shanghai Jiao Tong University",
    "EPFL",
    "University of Edinburgh",
    "University of Texas at Austin",
    "New York University",
    "University of Pennsylvania",
    "KAIST",
    "Tel Aviv University",
    "University of Melbourne",
    "Technical University of Munich",
    "Johns Hopkins University",
    "University of California, Los Angeles",
    "DeepMind",
    "Google Research",
    "Microsoft Research",
    "Meta AI",
    "OpenAI",
    "IBM Research",
    "NVIDIA Research",
    "Allen Institute for AI",
]


def _synthesize_affiliation(author_name: str) -> str:
    """Deterministically derive an affiliation from an author name."""
    if not author_name:
        return "Independent Researcher"
    digest = hashlib.md5(author_name.encode("utf-8")).digest()
    idx = digest[0] % len(_STUB_AFFILIATIONS)
    return _STUB_AFFILIATIONS[idx]


def _affiliations_for_authors(authors: list) -> list:
    return [_synthesize_affiliation(a) for a in authors]


def _synthesize_abstract(title: str, subject_code: str,
                         primary_subject: str = "") -> str:
    """Build a reasonable abstract from the title + category blurb."""
    blurb = _CATEGORY_BLURBS.get(subject_code)
    if not blurb:
        parent = subject_code.split(".")[0] if "." in subject_code else subject_code
        blurb = _CATEGORY_BLURBS.get(parent,
            "This paper presents new methods and experimental results "
            "relevant to the subject area. We describe the approach, report "
            "empirical findings, and discuss implications for future work.")
    lead = title.strip().rstrip(".") if title else "This work"
    return (f"{lead}. {blurb} "
            f"Full details are available in the preprint; please refer to "
            f"the PDF for complete formal statements, proofs, and additional "
            f"experiments.")


def _clean_arxiv_metadata_text(text):
    return clean_arxiv_metadata_text(text)


def seed_database():
    """Populate the DB from categories.json + papers.json."""
    if Category.query.first() is not None:
        return  # already seeded

    # --- Categories ---
    cat_path = BASE_DIR / "categories.json"
    if cat_path.exists():
        cat_data = json.load(open(cat_path))
        primary_cats = cat_data["categories"]
        subcats = cat_data["subcategories"]
    else:
        primary_cats = {}
        subcats = {}

    descriptions = {
        "cs": "Research in computing, from the theoretical foundations of algorithms to the practice of machine learning, computer vision, and software engineering.",
        "math": "Pure and applied mathematics: algebra, geometry, topology, analysis, probability, number theory, and more.",
        "physics": "General physics research spanning applied, atomic, biological, computational, and many other subfields.",
        "astro-ph": "Astrophysics: cosmology, galaxies, high-energy phenomena, instrumentation, solar and stellar physics.",
        "cond-mat": "Condensed matter physics: materials, mesoscale systems, quantum gases, soft matter, and superconductivity.",
        "gr-qc": "General relativity and quantum cosmology.",
        "hep-ex": "High energy physics experiments — large detectors, colliders, and beyond.",
        "hep-lat": "Lattice field theory and numerical high energy physics.",
        "hep-ph": "Phenomenology linking theory to experiment in high energy physics.",
        "hep-th": "Formal theoretical developments in high energy physics.",
        "math-ph": "Mathematical physics.",
        "nlin": "Nonlinear sciences: chaos, adaptation, pattern formation, and integrable systems.",
        "nucl-ex": "Nuclear experiment.",
        "nucl-th": "Nuclear theory.",
        "quant-ph": "Quantum information, quantum computing, and the foundations of quantum mechanics.",
        "q-bio": "Quantitative biology: biomolecules, cells, genomics, neurons, populations, and more.",
        "q-fin": "Quantitative finance: pricing, portfolios, risk, trading, and statistical finance.",
        "stat": "Statistics: applications, computation, methodology, machine learning, and theory.",
        "eess": "Electrical engineering and systems science: audio, image processing, signal processing, control.",
        "econ": "Economics: econometrics, general economics, and theoretical economics.",
    }

    for code, meta in primary_cats.items():
        cat = Category(
            code=code,
            name=meta.get("name", code),
            icon=meta.get("icon", "📚"),
            color=meta.get("color", "#b31b1b"),
            short_name=meta.get("short", code),
            description=descriptions.get(code, ""),
        )
        db.session.add(cat)
    db.session.commit()
    print(f"  [+] Seeded {Category.query.count()} categories")

    # --- Papers ---
    papers_path = BASE_DIR / "papers.json"
    if not papers_path.exists():
        print("  ! papers.json not found; skipping paper seed")
        return

    raw_papers = json.load(open(papers_path))
    # Order: papers with abstracts first
    raw_papers.sort(key=lambda p: (0 if p.get("abstract") else 1, p.get("arxiv_id", "")))

    created = 0
    for rp in raw_papers:
        arxiv_id = rp.get("arxiv_id", "").strip()
        if not arxiv_id:
            continue
        if Paper.query.filter_by(arxiv_id=arxiv_id).first():
            continue
        # Parse primary subject code from the "subjects" field
        subjects = rp.get("subjects", "").strip()
        primary_subject = subjects.split(";")[0].strip() if subjects else ""
        m = re.search(r"\(([a-zA-Z\-]+(?:\.[a-zA-Z\-]+)?)\)", primary_subject)
        subject_code = m.group(1) if m else rp.get("primary_category", "")
        primary_category = subject_code.split(".")[0] if "." in subject_code else subject_code
        # Map astro-ph, cond-mat, etc
        if primary_category not in primary_cats and subject_code in primary_cats:
            primary_category = subject_code
        # Titles
        title = _clean_arxiv_metadata_text(rp.get("title", "").strip())
        if not title:
            continue
        # Parse date, falling back to arxiv-id-encoded yymm (e.g. 2604.08525 -> 2026-04)
        sub_y, sub_m, sub_d = 0, 0, 0
        date_raw = (rp.get("date") or "").strip()
        dm = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", date_raw)
        if dm:
            sub_y, sub_m, sub_d = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        else:
            idm = re.match(r"(\d{2})(\d{2})\.(\d+)", arxiv_id)
            if idm:
                yy, mm, tail = int(idm.group(1)), int(idm.group(2)), idm.group(3)
                sub_y = 2000 + yy if yy < 90 else 1900 + yy
                sub_m = mm
                # deterministic pseudo-day based on tail digits so sorting is stable
                try:
                    sub_d = max(1, min(28, int(tail[-2:]) % 28 + 1))
                except Exception:
                    sub_d = 1
        authors = rp.get("authors", []) or []
        # Backfill empty author lists with a deterministic stub so abs pages
        # never render a blank author line. Uses arxiv_id as a stable seed.
        if not authors:
            authors = _synthesize_authors(arxiv_id)
        # Parse figures, tables, formulas counts from comments
        cmt = _clean_arxiv_metadata_text(rp.get("comments", ""))
        figs = 0
        tbls = 0
        frms = 0
        fm = re.search(r"(\d+)\s*figure", cmt, re.I)
        if fm:
            figs = int(fm.group(1))
        tm = re.search(r"(\d+)\s*table", cmt, re.I)
        if tm:
            tbls = int(tm.group(1))
        frm = re.search(r"(\d+)\s*formula", cmt, re.I)
        if frm:
            frms = int(frm.group(1))
        # Versions
        versions = rp.get("versions", [])
        # Loss function from abstract
        loss_fn = ""
        abs_text = _clean_arxiv_metadata_text(rp.get("abstract", "") or "")
        # Backfill empty abstracts for high-traffic categories so the /abs
        # and listing pages always surface something meaningful.
        if not abs_text:
            abs_text = _synthesize_abstract(title, subject_code, primary_subject)
        lm = re.search(r"(sim\([^)]*\))", abs_text)
        if lm:
            loss_fn = lm.group(1)
        paper = Paper(
            arxiv_id=arxiv_id,
            title=title,
            abstract=abs_text,
            authors_json=json.dumps(authors),
            author_affiliations_json=json.dumps(_affiliations_for_authors(authors)),
            n_authors=len(authors),
            subjects=subjects,
            primary_subject=primary_subject,
            primary_subject_code=subject_code,
            primary_category_code=primary_category,
            submitted_date=(f"{sub_y:04d}-{sub_m:02d}-{sub_d:02d}"
                            if sub_y else date_raw),
            submitted_year=sub_y,
            submitted_month=sub_m,
            submitted_day=sub_d,
            announce_date=(f"{sub_y:04d}-{sub_m:02d}-{sub_d:02d}" if sub_y else ""),
            comments=cmt,
            journal_ref=rp.get("journal_ref", ""),
            doi=rp.get("doi", ""),
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
            html_url=f"https://arxiv.org/abs/{arxiv_id}",
            html_available=True,
            figures_count=figs,
            tables_count=tbls,
            formulas_count=frms,
            loss_function=loss_fn,
            versions_json=json.dumps(versions) if versions else "[]",
            view_count=random.randint(50, 5000),
            download_count=random.randint(20, 2000),
            star_count=random.randint(0, 200),
        )
        db.session.add(paper)
        created += 1
        if created % 200 == 0:
            db.session.commit()
    db.session.commit()
    print(f"  [+] Seeded {created} papers")

    # --- Demo user with some activity ---
    if not User.query.filter_by(email="demo@arxiv.local").first():
        u = User(
            email="demo@arxiv.local",
            username="demouser",
            full_name="Demo Researcher",
            affiliation="Example University",
            bio="A demo researcher exploring topics in machine learning.",
            orcid="0000-0000-0000-0000",
        )
        u.set_password("demodemo")
        db.session.add(u)
        db.session.commit()
        # Add a few library/starred items for demo flavor
        sample_papers = Paper.query.filter(Paper.abstract != "").limit(5).all()
        for i, p in enumerate(sample_papers[:3]):
            db.session.add(LibraryItem(user_id=u.id, paper_id=p.id, folder="Reading List"))
        for p in sample_papers[3:5]:
            db.session.add(StarredPaper(user_id=u.id, paper_id=p.id))
        db.session.commit()
        print("  [+] Created demo user (demo@arxiv.local / demodemo)")


# =======================================================================
# CONTEXT PROCESSORS
# =======================================================================

@app.context_processor
def inject_globals():
    library_count = 0
    if current_user.is_authenticated:
        library_count = LibraryItem.query.filter_by(user_id=current_user.id).count()

    main_cats = Category.query.order_by(Category.code).all()

    mirror_today_iso = db.session.query(func.max(Paper.submitted_date)).scalar() or ""
    mirror_today_pretty = ""
    if mirror_today_iso:
        try:
            d = datetime.strptime(mirror_today_iso, "%Y-%m-%d")
            mirror_today_pretty = d.strftime("%a, %d %b %Y")
        except Exception:
            mirror_today_pretty = mirror_today_iso

    return dict(
        library_count=library_count,
        main_categories=main_cats,
        current_year=datetime.utcnow().year,
        mirror_today=mirror_today_iso,
        mirror_today_pretty=mirror_today_pretty,
    )


# =======================================================================
# HELPERS
# =======================================================================

def get_category_or_404(code: str) -> Category:
    cat = Category.query.filter_by(code=code).first()
    if not cat:
        abort(404)
    return cat


def get_papers_for_category(code: str, page: int = 1, per_page: int = 25):
    q = Paper.query.filter(
        or_(Paper.primary_subject_code == code,
            Paper.primary_subject_code.like(f"{code}.%"),
            Paper.primary_category_code == code)
    ).order_by(Paper.arxiv_id.desc())
    total = q.count()
    papers = q.offset((page - 1) * per_page).limit(per_page).all()
    return papers, total


def new_export_id() -> str:
    return "EX" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + str(random.randint(100, 999))


# -----------------------------------------------------------------------
# Search helpers — scored relevance + filters + sorts
# -----------------------------------------------------------------------

STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with",
    "and", "or", "is", "are", "be", "by", "from", "as", "that", "this",
    "its", "it", "we", "our", "about", "how", "latest", "most", "recent",
    "paper", "papers", "article", "articles", "which", "whose", "was",
    "were", "have", "has", "had", "do", "does", "did",
}


def _score_paper(paper: "Paper", tokens: list) -> int:
    haystack = " ".join([
        (paper.title or "").lower(),
        (paper.abstract or "").lower(),
        (paper.authors_json or "").lower(),
        (paper.subjects or "").lower(),
        (paper.primary_subject or "").lower(),
        (paper.primary_subject_code or "").lower(),
        (paper.primary_category_code or "").lower(),
        (paper.journal_ref or "").lower(),
        (paper.comments or "").lower(),
        (paper.arxiv_id or "").lower(),
    ])
    return sum(1 for t in tokens if t in haystack)


def _tokenize_query(q: str) -> list:
    tokens = [t.lower() for t in re.findall(r"[a-z0-9]+", (q or "").lower())]
    return [t for t in tokens if t and t not in STOPWORDS and len(t) >= 2]


def _parse_date_str(s: str):
    """Parse 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS' etc into a date tuple (y,m,d) or None."""
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s.strip())
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", s.strip())
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _apply_paper_filters(query_obj):
    """Apply request.args structural filters to a Paper query."""
    # Primary category / subject code filter. Accept either 'category' or 'primary_category'.
    cat = (request.args.get("category") or request.args.get("primary_category") or "").strip()
    if cat:
        if "." in cat:
            # Specific subject like cs.CL
            query_obj = query_obj.filter(Paper.primary_subject_code == cat)
        else:
            query_obj = query_obj.filter(or_(
                Paper.primary_subject_code == cat,
                Paper.primary_subject_code.like(f"{cat}.%"),
                Paper.primary_category_code == cat,
            ))

    # Subject substring (legacy)
    subject = (request.args.get("subject") or "").strip()
    if subject:
        query_obj = query_obj.filter(Paper.subjects.ilike(f"%{subject}%"))

    # Year range
    year = request.args.get("year", type=int)
    if year:
        query_obj = query_obj.filter(Paper.submitted_year == year)
    year_from = request.args.get("year_from", type=int)
    if year_from:
        query_obj = query_obj.filter(Paper.submitted_year >= year_from)
    year_to = request.args.get("year_to", type=int)
    if year_to:
        query_obj = query_obj.filter(Paper.submitted_year <= year_to)

    # Month (+ year) filter
    month = request.args.get("month", type=int)
    if month:
        query_obj = query_obj.filter(Paper.submitted_month == month)

    # Absolute date range (YYYY-MM-DD)
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    if date_from:
        df = _parse_date_str(date_from)
        if df:
            query_obj = query_obj.filter(or_(
                Paper.submitted_year > df[0],
                and_(Paper.submitted_year == df[0], Paper.submitted_month > df[1]),
                and_(Paper.submitted_year == df[0],
                     Paper.submitted_month == df[1],
                     Paper.submitted_day >= df[2]),
            ))
    if date_to:
        dt = _parse_date_str(date_to)
        if dt:
            query_obj = query_obj.filter(or_(
                Paper.submitted_year < dt[0],
                and_(Paper.submitted_year == dt[0], Paper.submitted_month < dt[1]),
                and_(Paper.submitted_year == dt[0],
                     Paper.submitted_month == dt[1],
                     Paper.submitted_day <= dt[2]),
            ))

    # Last N days (relative to max announce date in DB to avoid "no recent papers" issues)
    last_days = request.args.get("last_days", type=int)
    if last_days is not None and last_days > 0:
        ref = _latest_announce_tuple()
        if ref:
            # Compute cutoff by converting to ordinal
            import datetime as _dt
            ref_date = _dt.date(*ref)
            cutoff = ref_date - timedelta(days=last_days - 1)
            query_obj = query_obj.filter(or_(
                Paper.submitted_year > cutoff.year,
                and_(Paper.submitted_year == cutoff.year,
                     Paper.submitted_month > cutoff.month),
                and_(Paper.submitted_year == cutoff.year,
                     Paper.submitted_month == cutoff.month,
                     Paper.submitted_day >= cutoff.day),
            ))

    # Minimum number of authors
    min_authors = request.args.get("min_authors", type=int)
    if min_authors is not None:
        query_obj = query_obj.filter(Paper.n_authors >= min_authors)
    max_authors = request.args.get("max_authors", type=int)
    if max_authors is not None:
        query_obj = query_obj.filter(Paper.n_authors <= max_authors)

    # Journal ref substring
    journal_ref = (request.args.get("journal_ref") or "").strip()
    if journal_ref:
        query_obj = query_obj.filter(Paper.journal_ref.ilike(f"%{journal_ref}%"))

    # Author substring (searches authors_json)
    author = (request.args.get("author") or "").strip()
    if author:
        query_obj = query_obj.filter(Paper.authors_json.ilike(f"%{author}%"))

    # HTML availability
    if request.args.get("html") == "1":
        query_obj = query_obj.filter(Paper.html_available == True)

    return query_obj


def _latest_announce_tuple():
    """Return (year, month, day) of the most recent paper in the DB."""
    p = (Paper.query
         .filter(Paper.submitted_year > 0)
         .order_by(Paper.submitted_year.desc(),
                   Paper.submitted_month.desc(),
                   Paper.submitted_day.desc())
         .first())
    if not p:
        return None
    return (p.submitted_year, p.submitted_month, p.submitted_day)


def _apply_paper_sort(results: list, sort_key: str) -> list:
    if sort_key in ("date", "newest", "submitted_desc", "recent"):
        return sorted(
            results,
            key=lambda p: (p.submitted_year, p.submitted_month, p.submitted_day, p.arxiv_id),
            reverse=True,
        )
    if sort_key in ("date_asc", "oldest", "submitted_asc"):
        return sorted(
            results,
            key=lambda p: (p.submitted_year, p.submitted_month, p.submitted_day, p.arxiv_id),
        )
    if sort_key == "views":
        return sorted(results, key=lambda p: p.view_count, reverse=True)
    if sort_key == "stars":
        return sorted(results, key=lambda p: p.star_count, reverse=True)
    return results


# =======================================================================
# ROUTES — PUBLIC PAGES
# =======================================================================

_HOMEPAGE_GROUPS = [
    ("Physics", [
        "astro-ph", "cond-mat", "gr-qc", "hep-ex", "hep-lat", "hep-ph",
        "hep-th", "math-ph", "nlin", "nucl-ex", "nucl-th", "physics", "quant-ph",
    ]),
    ("Mathematics", ["math"]),
    ("Computer Science", ["cs"]),
    ("Quantitative Biology", ["q-bio"]),
    ("Quantitative Finance", ["q-fin"]),
    ("Statistics", ["stat"]),
    ("Electrical Engineering and Systems Science", ["eess"]),
    ("Economics", ["econ"]),
]

_HOMEPAGE_ARCHIVE_NAMES = {
    "astro-ph":  "Astrophysics",
    "cond-mat":  "Condensed Matter",
    "gr-qc":     "General Relativity and Quantum Cosmology",
    "hep-ex":    "High Energy Physics - Experiment",
    "hep-lat":   "High Energy Physics - Lattice",
    "hep-ph":    "High Energy Physics - Phenomenology",
    "hep-th":    "High Energy Physics - Theory",
    "math-ph":   "Mathematical Physics",
    "nlin":      "Nonlinear Sciences",
    "nucl-ex":   "Nuclear Experiment",
    "nucl-th":   "Nuclear Theory",
    "physics":   "Physics",
    "quant-ph":  "Quantum Physics",
    "math":      "Mathematics",
    "cs":        "Computing Research Repository",
    "q-bio":     "Quantitative Biology",
    "q-fin":     "Quantitative Finance",
    "stat":      "Statistics",
    "eess":      "Electrical Engineering and Systems Science",
    "econ":      "Economics",
}


def _build_homepage_directory():
    cat_path = BASE_DIR / "categories.json"
    subs_map = {}
    if cat_path.exists():
        try:
            subs_map = json.load(open(cat_path)).get("subcategories", {})
        except Exception:
            subs_map = {}
    sub_by_archive = {}
    for sub_code, sub_name in subs_map.items():
        parent = sub_code.split(".")[0] if "." in sub_code else sub_code
        sub_by_archive.setdefault(parent, []).append((sub_code, sub_name))
    for parent in sub_by_archive:
        sub_by_archive[parent].sort(key=lambda x: x[0])

    cat_codes = {c.code for c in Category.query.all()}
    groups = []
    for header, codes in _HOMEPAGE_GROUPS:
        items = []
        for code in codes:
            if code not in cat_codes:
                continue
            items.append({
                "code": code,
                "name": _HOMEPAGE_ARCHIVE_NAMES.get(code, code),
                "subs": sub_by_archive.get(code, []),
            })
        if items:
            groups.append({"header": header, "archives": items})
    return groups


@app.route("/")
def index():
    total_papers = Paper.query.count()
    groups = _build_homepage_directory()
    return render_template(
        "index.html",
        total_papers=total_papers,
        groups=groups,
    )


@app.route("/category/<code>")
@app.route("/archive/<code>")
def category_detail(code):
    cat = get_category_or_404(code)
    page = max(1, int(request.args.get("page", 1)))
    papers, total = get_papers_for_category(code, page=page, per_page=25)
    # Subcategory aggregates
    subcat_codes = {}
    all_in_cat = Paper.query.filter(
        or_(Paper.primary_subject_code == code,
            Paper.primary_subject_code.like(f"{code}.%"),
            Paper.primary_category_code == code)
    ).all()
    for p in all_in_cat:
        k = p.primary_subject_code or code
        subcat_codes[k] = subcat_codes.get(k, 0) + 1
    sorted_subs = sorted(subcat_codes.items(), key=lambda x: -x[1])
    return render_template(
        "category.html",
        category=cat,
        papers=papers,
        total=total,
        page=page,
        per_page=25,
        subcat_counts=sorted_subs,
    )


#: Cross-listing aliases — codes that should surface papers filed under a
#: different primary subject on real arxiv.org. Extend as needed.
CATEGORY_ALIASES = {
    "cs.SY": ["eess.SY"],
    "eess.SY": ["cs.SY"],
    "cs.NA": ["math.NA"],
    "math.NA": ["cs.NA"],
    "stat.ML": ["cs.LG"],
}


@app.route("/list/<code>/<view>")
def listing(code, view):
    """arxiv-style listing: /list/cs.AI/recent or /list/cs.AI/new"""
    # Find category by code (allow subcategory codes too)
    cat_code = code.split(".")[0] if "." in code else code
    cat = Category.query.filter_by(code=cat_code).first()
    if not cat:
        # Try the alias target's parent category so e.g. cs.SY still renders
        # the eess header when the cs archive has no record of cs.SY.
        aliases = CATEGORY_ALIASES.get(code, [])
        for a in aliases:
            a_parent = a.split(".")[0] if "." in a else a
            cat = Category.query.filter_by(code=a_parent).first()
            if cat:
                break
        if not cat:
            abort(404)
    page = max(1, int(request.args.get("page", 1)))
    per_page = int(request.args.get("per_page", 25))

    # Build filter: primary/secondary code match plus any cross-listed aliases.
    alias_codes = CATEGORY_ALIASES.get(code, [])
    clauses = [
        Paper.primary_subject_code == code,
        Paper.primary_subject_code.like(f"{code}.%"),
        Paper.primary_category_code == code,
        Paper.subjects.ilike(f"%({code})%"),
    ]
    for a in alias_codes:
        clauses.append(Paper.primary_subject_code == a)
        clauses.append(Paper.subjects.ilike(f"%({a})%"))
    q = Paper.query.filter(or_(*clauses))

    # Order: prefer papers with non-empty abstract first so the listing
    # always surfaces rich content at the top, then newest-first.
    q = q.order_by(
        (Paper.abstract == "").asc(),
        Paper.submitted_year.desc(),
        Paper.submitted_month.desc(),
        Paper.submitted_day.desc(),
        Paper.arxiv_id.desc(),
    )
    total = q.count()
    papers = q.offset((page - 1) * per_page).limit(per_page).all()

    # Group papers by announce_date (submitted_y/m/d) for "/new" views so the
    # template can render a "Day, DD Mon YYYY (N new submissions)" header like
    # the real arxiv.org listing pages.
    grouped = []
    if papers:
        import datetime as _dt
        current_key = None
        current_bucket = None
        for p in papers:
            key = (p.submitted_year, p.submitted_month, p.submitted_day)
            if key != current_key:
                try:
                    d = _dt.date(key[0], key[1], key[2])
                    label = d.strftime("%a, %-d %b %Y")
                except Exception:
                    label = f"{key[0]:04d}-{key[1]:02d}-{key[2]:02d}"
                current_bucket = {"label": label, "key": key, "papers": []}
                grouped.append(current_bucket)
                current_key = key
            current_bucket["papers"].append(p)
        # Add counts
        for g in grouped:
            g["count"] = len(g["papers"])

    return render_template(
        "listing.html",
        category=cat,
        subject_code=code,
        view=view,
        papers=papers,
        grouped=grouped,
        total=total,
        page=page,
        per_page=per_page,
    )


@app.route("/abs/<arxiv_id>")
def paper_detail(arxiv_id):
    paper = Paper.query.filter_by(arxiv_id=arxiv_id).first_or_404()
    paper.view_count += 1
    db.session.commit()
    # Related: same primary category, different paper
    related = (Paper.query
               .filter(Paper.primary_category_code == paper.primary_category_code,
                       Paper.id != paper.id)
               .order_by(func.random()).limit(6).all())
    # Comments
    comments = (Comment.query.filter_by(paper_id=paper.id)
                .order_by(Comment.created_at.desc()).all())
    # Is in library / starred?
    in_library = False
    is_starred = False
    if current_user.is_authenticated:
        in_library = LibraryItem.query.filter_by(
            user_id=current_user.id, paper_id=paper.id).first() is not None
        is_starred = StarredPaper.query.filter_by(
            user_id=current_user.id, paper_id=paper.id).first() is not None
    return render_template(
        "paper.html",
        paper=paper,
        related=related,
        comments=comments,
        in_library=in_library,
        is_starred=is_starred,
    )


LOCAL_PAPERS_DIR = BASE_DIR / "static" / "papers"


@app.route("/pdf/<arxiv_id>")
def pdf_view(arxiv_id):
    paper = Paper.query.filter_by(arxiv_id=arxiv_id).first_or_404()
    paper.download_count += 1
    db.session.commit()
    local = LOCAL_PAPERS_DIR / f"{paper.arxiv_id}.pdf"
    if local.exists():
        return send_from_directory(
            LOCAL_PAPERS_DIR, f"{paper.arxiv_id}.pdf",
            mimetype="application/pdf",
        )
    return redirect(f"https://arxiv.org/pdf/{paper.arxiv_id}", code=302)


@app.route("/html/<arxiv_id>")
def html_view(arxiv_id):
    paper = Paper.query.filter_by(arxiv_id=arxiv_id).first_or_404()
    local = LOCAL_PAPERS_DIR / f"{paper.arxiv_id}.html"
    if local.exists():
        return send_from_directory(
            LOCAL_PAPERS_DIR, f"{paper.arxiv_id}.html",
            mimetype="text/html",
        )
    return redirect(f"https://arxiv.org/html/{paper.arxiv_id}", code=302)


@app.route("/e-print/<arxiv_id>")
def eprint_view(arxiv_id):
    paper = Paper.query.filter_by(arxiv_id=arxiv_id).first_or_404()
    return redirect(f"https://arxiv.org/e-print/{paper.arxiv_id}", code=302)


@app.route("/format/<arxiv_id>")
def format_view(arxiv_id):
    paper = Paper.query.filter_by(arxiv_id=arxiv_id).first_or_404()
    return redirect(f"https://arxiv.org/format/{paper.arxiv_id}", code=302)


@app.route("/category_taxonomy")
def category_taxonomy():
    # Load subcategory map from JSON
    cat_path = BASE_DIR / "categories.json"
    subs = {}
    if cat_path.exists():
        subs = json.load(open(cat_path))["subcategories"]
    # Group by parent code
    grouped = {}
    for sub_code, sub_name in subs.items():
        parent = sub_code.split(".")[0] if "." in sub_code else sub_code
        grouped.setdefault(parent, []).append((sub_code, sub_name))
    for parent in grouped:
        grouped[parent].sort()
    categories = Category.query.order_by(Category.code).all()
    return render_template("taxonomy.html", categories=categories, grouped=grouped)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/external/cornell")
def external_cornell():
    """Local stub page about Cornell University (the institution that hosts
    arXiv). Used by the /about page so agents can visit a 'Cornell website'
    without leaving the sandbox."""
    return render_template("external_cornell.html")


@app.route("/news")
def news():
    """arXiv News page — latest announcements and press."""
    items = [
        {
            "date": "2026-04-05",
            "title": "arXiv reaches 3 million submissions",
            "body": ("Today marks a major milestone for arXiv: more than three million "
                     "scholarly articles have been submitted to the archive since it was "
                     "founded in 1991. Thank you to every researcher, moderator, and "
                     "volunteer who has contributed."),
        },
        {
            "date": "2026-03-22",
            "title": "New machine learning categories announced",
            "body": ("In response to rapid growth in AI research, arXiv is introducing "
                     "two new subcategories under Computer Science (cs) to help authors "
                     "better classify foundation-model and agent research."),
        },
        {
            "date": "2026-03-01",
            "title": "HTML rendering now available for most new submissions",
            "body": ("HTML5 versions of newly submitted papers are now generated "
                     "automatically for LaTeX sources, making papers easier to read on "
                     "mobile devices and more accessible for screen readers."),
        },
        {
            "date": "2026-02-10",
            "title": "arXiv non-profit store reopened",
            "body": ("Our non-profit store is back, featuring T-shirts, mugs, and tote "
                     "bags. All proceeds support arXiv's open-access mission."),
        },
    ]
    return render_template("news.html", items=items)


@app.route("/store")
def store():
    """arXiv non-profit store — merchandise."""
    products = [
        {
            "slug": "arxiv-logo-shirt",
            "name": "arXiv Logo Shirt",
            "price": 22.00,
            "category": "Apparel",
            "description": "Classic crewneck t-shirt featuring the arXiv wordmark.",
            "styles": ["Unisex short sleeve", "Women's short sleeve",
                       "Unisex long sleeve", "Women's long sleeve"],
        },
        {
            "slug": "arxiv-forever-short-sleeve",
            "name": "arXiv Forever Short Sleeve",
            "price": 24.00,
            "category": "Apparel",
            "description": "'arXiv Forever' graphic tee — unisex short sleeve.",
            "styles": ["Unisex XS", "Unisex S", "Unisex M",
                       "Unisex L", "Unisex XL", "Unisex XXL"],
        },
        {
            "slug": "arxiv-ceramic-mug",
            "name": "arXiv Ceramic Mug",
            "price": 12.00,
            "category": "Drinkware",
            "description": "11oz ceramic mug with the arXiv logo on both sides.",
            "styles": ["White", "Black"],
        },
        {
            "slug": "arxiv-tote-bag",
            "name": "arXiv Canvas Tote Bag",
            "price": 14.00,
            "category": "Bags",
            "description": "Heavy cotton tote with the arXiv wordmark.",
            "styles": ["Natural"],
        },
        {
            "slug": "arxiv-sticker-pack",
            "name": "arXiv Sticker Pack",
            "price": 4.00,
            "category": "Stickers",
            "description": "Pack of 5 vinyl stickers.",
            "styles": ["Pack of 5"],
        },
        {
            "slug": "arxiv-hoodie",
            "name": "arXiv Hoodie",
            "price": 42.00,
            "category": "Apparel",
            "description": "Pullover hoodie with embroidered arXiv logo.",
            "styles": ["S", "M", "L", "XL", "XXL"],
        },
        {
            "slug": "arxiv-notebook",
            "name": "arXiv Dot Grid Notebook",
            "price": 10.00,
            "category": "Stationery",
            "description": "Hardcover dot-grid notebook.",
            "styles": ["A5"],
        },
    ]
    return render_template("store.html", products=products)


@app.route("/store/<slug>")
def store_item(slug):
    from flask import abort as _abort
    all_items = store.__wrapped__() if hasattr(store, "__wrapped__") else None  # not used
    # simple lookup
    for item in [
        {"slug": "arxiv-logo-shirt", "name": "arXiv Logo Shirt",
         "price": 22.00, "styles": ["Unisex short sleeve", "Women's short sleeve",
                                    "Unisex long sleeve", "Women's long sleeve"]},
        {"slug": "arxiv-forever-short-sleeve", "name": "arXiv Forever Short Sleeve",
         "price": 24.00, "styles": ["Unisex XS", "Unisex S", "Unisex M",
                                    "Unisex L", "Unisex XL", "Unisex XXL"]},
        {"slug": "arxiv-ceramic-mug", "name": "arXiv Ceramic Mug",
         "price": 12.00, "styles": ["White", "Black"]},
    ]:
        if item["slug"] == slug:
            return render_template("store_item.html", item=item)
    _abort(404)


@app.route("/blog")
def blog():
    """arXiv Blog index."""
    posts = [
        {
            "slug": "open-access-2026",
            "title": "Open Access in 2026: What's Next for arXiv",
            "date": "2026-04-02",
            "author": "arXiv Editorial Team",
            "excerpt": ("We reflect on 35 years of open access to research and share our "
                        "roadmap for the next decade of arXiv."),
            "body": ("Open access is the cornerstone of arXiv. Over the next five years, "
                     "we will expand HTML rendering, add new subject areas, and deepen our "
                     "partnerships with libraries worldwide. This post lays out the "
                     "technical and policy goals we are pursuing to keep arXiv fast, "
                     "reliable, and truly free for every researcher."),
        },
        {
            "slug": "html-rendering-launch",
            "title": "HTML Rendering Launches for All New Submissions",
            "date": "2026-03-01",
            "author": "arXiv Engineering",
            "excerpt": ("Starting today, LaTeX-based submissions are rendered to HTML5 "
                        "automatically. Here's how it works."),
            "body": ("HTML5 rendering brings arXiv papers to mobile devices and assistive "
                     "technologies for the first time. We use a custom LaTeXML pipeline."),
        },
        {
            "slug": "moderation-transparency",
            "title": "Transparency in Moderation",
            "date": "2026-02-14",
            "author": "arXiv Moderation",
            "excerpt": ("How we make moderation decisions and why we publish summary "
                        "statistics every quarter."),
            "body": ("Moderation at arXiv is a balance between scholarly rigor and open "
                     "access. This post explains our process."),
        },
    ]
    return render_template("blog.html", posts=posts)


@app.route("/blog/<slug>")
def blog_post(slug):
    posts = {
        "open-access-2026": {
            "slug": "open-access-2026",
            "title": "Open Access in 2026: What's Next for arXiv",
            "date": "2026-04-02",
            "author": "arXiv Editorial Team",
            "body": ("Open access is the cornerstone of arXiv. Over the next five years, "
                     "we will expand HTML rendering, add new subject areas, and deepen our "
                     "partnerships with libraries worldwide. This post lays out the "
                     "technical and policy goals we are pursuing to keep arXiv fast, "
                     "reliable, and truly free for every researcher."),
        },
        "html-rendering-launch": {
            "slug": "html-rendering-launch",
            "title": "HTML Rendering Launches for All New Submissions",
            "date": "2026-03-01",
            "author": "arXiv Engineering",
            "body": ("HTML5 rendering brings arXiv papers to mobile devices and assistive "
                     "technologies for the first time."),
        },
        "moderation-transparency": {
            "slug": "moderation-transparency",
            "title": "Transparency in Moderation",
            "date": "2026-02-14",
            "author": "arXiv Moderation",
            "body": ("Moderation at arXiv is a balance between scholarly rigor and open "
                     "access."),
        },
    }
    post = posts.get(slug)
    if not post:
        abort(404)
    return render_template("blog_post.html", post=post)


@app.route("/help")
def help_page():
    return render_template("help.html")


@app.route("/help/<page>")
def help_page_sub(page):
    return render_template("help.html", section=page)


@app.route("/search/")
@app.route("/search")
def search():
    q = (request.args.get("query") or request.args.get("q") or "").strip()
    field = request.args.get("searchtype", "all")
    page = max(1, int(request.args.get("page", 1)))
    per_page = 25

    # Start with all papers + structural filters
    query_obj = Paper.query
    query_obj = _apply_paper_filters(query_obj)
    candidates = query_obj.all()

    results = candidates
    if q:
        tokens = _tokenize_query(q)
        if field == "title":
            # strict substring on title when field=title, but also allow phrase-level match
            phrase = q.lower()
            results = [p for p in candidates if phrase in (p.title or "").lower()]
        elif field == "author":
            phrase = q.lower()
            results = [p for p in candidates if phrase in (p.authors_json or "").lower()]
        elif field == "abstract":
            phrase = q.lower()
            results = [p for p in candidates if phrase in (p.abstract or "").lower()]
        elif field == "id":
            phrase = q.lower()
            results = [p for p in candidates if phrase in (p.arxiv_id or "").lower()]
        elif field == "journal_ref":
            phrase = q.lower()
            results = [p for p in candidates if phrase in (p.journal_ref or "").lower()]
        else:  # all — scored relevance
            if tokens:
                min_required = max(1, len(tokens) // 2)
                scored = []
                for p in candidates:
                    s = _score_paper(p, tokens)
                    if s >= min_required:
                        scored.append((s, p))
                scored.sort(key=lambda x: -x[0])
                results = [p for _, p in scored]
            else:
                results = candidates

    # Apply sort if requested
    sort_key = request.args.get("sort", "").strip()
    results = _apply_paper_sort(results, sort_key)

    total = len(results)
    paged = results[(page - 1) * per_page: page * per_page]

    return render_template(
        "search.html",
        query=q, field=field, results=paged, total=total, page=page, per_page=per_page,
    )


@app.route("/search/advanced", methods=["GET", "POST"])
def advanced_search():
    if request.method == "POST":
        terms = (request.form.get("terms") or "").strip()
        field = (request.form.get("field") or "all").strip()
        subject = (request.form.get("subject") or request.form.get("category")
                   or "").strip()
        date_range = (request.form.get("date_range") or "").strip()
        sort_key = (request.form.get("sort") or "").strip()
        start_date = (request.form.get("start_date") or "").strip()
        end_date = (request.form.get("end_date") or "").strip()

        params = {"query": terms}
        # Forward field as the backend-native `searchtype` (advanced-search
        # dropdown uses `field`; /search reads `searchtype`). Keep `field` too
        # for compatibility with templates that echo the current selection.
        if field and field != "all":
            params["searchtype"] = field
            params["field"] = field
        if subject:
            params["category"] = subject
        # Map date_range dropdown values to last_days for /search
        if date_range:
            dr_days = {
                "past_2_days": 2,
                "past_week": 7, "week": 7,
                "past_month": 30, "month": 30,
                "past_year": 365, "year": 365,
            }.get(date_range)
            if dr_days:
                params["last_days"] = dr_days
            else:
                params["date_range"] = date_range
        if start_date:
            params["date_from"] = start_date
        if end_date:
            params["date_to"] = end_date
        # Sort: advanced form may pass "relevance" (default), "date" (newest),
        # "date_asc" (oldest), etc. Only forward meaningful sort keys.
        if sort_key and sort_key != "relevance":
            params["sort"] = sort_key
        return redirect(url_for("search", **params))

    # GET: render form. Build a list of subcategory choices so the Subject
    # dropdown can offer fine-grained options (astro-ph.EP, cs.CL, ...) in
    # addition to the main archive codes.
    subcat_path = BASE_DIR / "categories.json"
    subcategories = []
    try:
        if subcat_path.exists():
            subs = json.load(open(subcat_path)).get("subcategories", {})
            # Sort by parent archive, then subcode
            for code, name in sorted(subs.items()):
                if "." in code:
                    subcategories.append({"code": code, "name": name})
    except Exception:
        subcategories = []
    return render_template(
        "advanced_search.html",
        subcategories=subcategories,
    )


@app.route("/author/<path:name>")
def author_papers(name):
    papers = (Paper.query.filter(Paper.authors_json.ilike(f'%{name}%'))
              .order_by(Paper.arxiv_id.desc()).limit(50).all())
    return render_template("author.html", name=name, papers=papers)


# =======================================================================
# ROUTES — AUTHENTICATION
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
            flash("Welcome back!", "success")
            next_url = request.args.get("next") or url_for("account")
            return redirect(next_url)
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
        if not (email and username and password):
            flash("Email, username, and password are required.", "error")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "error")
            return render_template("register.html")
        if User.query.filter_by(username=username).first():
            flash("This username is taken.", "error")
            return render_template("register.html")
        u = User(email=email, username=username, full_name=full_name)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash("Account created. Welcome to arXiv!", "success")
        return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


# =======================================================================
# ROUTES — ACCOUNT
# =======================================================================

@app.route("/account")
@login_required
def account():
    recent_library = (LibraryItem.query.filter_by(user_id=current_user.id)
                      .order_by(LibraryItem.added_at.desc()).limit(5).all())
    recent_stars = (StarredPaper.query.filter_by(user_id=current_user.id)
                    .order_by(StarredPaper.starred_at.desc()).limit(5).all())
    exports = (Export.query.filter_by(user_id=current_user.id)
               .order_by(Export.created_at.desc()).all())
    my_comments = (Comment.query.filter_by(user_id=current_user.id)
                   .order_by(Comment.created_at.desc()).limit(10).all())
    alerts = Alert.query.filter_by(user_id=current_user.id).all()
    return render_template(
        "account.html",
        recent_library=recent_library,
        recent_stars=recent_stars,
        exports=exports,
        my_comments=my_comments,
        alerts=alerts,
    )


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        current_user.full_name = request.form.get("full_name", "").strip()
        current_user.affiliation = request.form.get("affiliation", "").strip()
        current_user.bio = request.form.get("bio", "").strip()
        current_user.orcid = request.form.get("orcid", "").strip()
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


@app.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    uid = current_user.id
    logout_user()
    user = db.session.get(User, uid)
    if user:
        db.session.delete(user)
        db.session.commit()
    flash("Your account has been deleted.", "success")
    return redirect(url_for("index"))


# =======================================================================
# ROUTES — LIBRARY (cart analog)
# =======================================================================

@app.route("/library")
@login_required
def library():
    folder = request.args.get("folder", "")
    q = LibraryItem.query.filter_by(user_id=current_user.id)
    if folder:
        q = q.filter_by(folder=folder)
    items = q.order_by(LibraryItem.added_at.desc()).all()
    folders = (db.session.query(LibraryItem.folder, func.count(LibraryItem.id))
               .filter_by(user_id=current_user.id)
               .group_by(LibraryItem.folder).all())
    return render_template("library.html", items=items, folders=folders, current_folder=folder)


@app.route("/api/library/add", methods=["POST"])
@login_required
@csrf.exempt
def api_library_add():
    data = request.get_json() or {}
    paper_id = int(data.get("paper_id", 0))
    folder = data.get("folder", "Reading List")
    paper = Paper.query.get(paper_id)
    if not paper:
        return jsonify({"success": False, "message": "Paper not found"}), 404
    existing = LibraryItem.query.filter_by(user_id=current_user.id, paper_id=paper_id).first()
    if existing:
        return jsonify({"success": True, "message": "Already in your library",
                        "library_count": LibraryItem.query.filter_by(user_id=current_user.id).count()})
    item = LibraryItem(user_id=current_user.id, paper_id=paper_id, folder=folder)
    db.session.add(item)
    db.session.commit()
    return jsonify({"success": True, "message": "Added to your library",
                    "library_count": LibraryItem.query.filter_by(user_id=current_user.id).count()})


@app.route("/api/library/remove", methods=["POST"])
@login_required
@csrf.exempt
def api_library_remove():
    data = request.get_json() or {}
    item_id = int(data.get("item_id", 0))
    item = LibraryItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify({"success": False, "message": "Not found"}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"success": True, "library_count":
                    LibraryItem.query.filter_by(user_id=current_user.id).count()})


@app.route("/api/library/update", methods=["POST"])
@login_required
@csrf.exempt
def api_library_update():
    data = request.get_json() or {}
    item_id = int(data.get("item_id", 0))
    folder = data.get("folder", "Reading List")
    note = data.get("note", "")
    item = LibraryItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify({"success": False, "message": "Not found"}), 404
    item.folder = folder
    item.note = note
    db.session.commit()
    return jsonify({"success": True})


@app.route("/library/folder/create", methods=["POST"])
@login_required
def create_folder():
    name = (request.form.get("folder_name") or "").strip()
    paper_id = request.form.get("paper_id")
    if name and paper_id:
        existing = LibraryItem.query.filter_by(user_id=current_user.id, paper_id=int(paper_id)).first()
        if existing:
            existing.folder = name
        else:
            db.session.add(LibraryItem(user_id=current_user.id, paper_id=int(paper_id), folder=name))
        db.session.commit()
    return redirect(request.referrer or url_for("library"))


@app.route("/library/folder/rename", methods=["POST"])
@login_required
def rename_folder():
    """Rename a library folder — updates all items in that folder."""
    old_name = (request.form.get("old_name") or "").strip()
    new_name = (request.form.get("new_name") or "").strip()
    if old_name and new_name and old_name != new_name:
        items = LibraryItem.query.filter_by(
            user_id=current_user.id, folder=old_name
        ).all()
        if items:
            for item in items:
                item.folder = new_name
            db.session.commit()
            flash(f'Folder renamed from "{old_name}" to "{new_name}".', "success")
        else:
            flash(f'No folder named "{old_name}" found.', "error")
    else:
        flash("Please provide both old and new folder names.", "error")
    return redirect(url_for("library"))


# =======================================================================
# ROUTES — STARRED (wishlist analog)
# =======================================================================

@app.route("/starred")
@login_required
def starred_page():
    items = (StarredPaper.query.filter_by(user_id=current_user.id)
             .order_by(StarredPaper.starred_at.desc()).all())
    return render_template("starred.html", items=items)


@app.route("/api/star/toggle", methods=["POST"])
@login_required
@csrf.exempt
def api_star_toggle():
    data = request.get_json() or {}
    paper_id = int(data.get("paper_id", 0))
    paper = Paper.query.get(paper_id)
    if not paper:
        return jsonify({"success": False}), 404
    existing = StarredPaper.query.filter_by(user_id=current_user.id, paper_id=paper_id).first()
    if existing:
        db.session.delete(existing)
        paper.star_count = max(0, paper.star_count - 1)
        action = "removed"
    else:
        db.session.add(StarredPaper(user_id=current_user.id, paper_id=paper_id))
        paper.star_count += 1
        action = "added"
    db.session.commit()
    return jsonify({"success": True, "action": action, "star_count": paper.star_count})


@app.route("/starred/remove/<int:item_id>", methods=["POST"])
@login_required
def starred_remove(item_id):
    item = StarredPaper.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Removed from starred.", "success")
    return redirect(url_for("starred_page"))


# =======================================================================
# ROUTES — EXPORTS (order analog)
# =======================================================================

@app.route("/export", methods=["GET", "POST"])
@login_required
def export_create():
    if request.method == "POST":
        fmt = request.form.get("format", "bibtex")
        source = request.form.get("source", "library")
        notes = request.form.get("notes", "")
        paper_ids = []
        if source == "library":
            items = LibraryItem.query.filter_by(user_id=current_user.id).all()
            paper_ids = [i.paper_id for i in items]
        elif source == "starred":
            items = StarredPaper.query.filter_by(user_id=current_user.id).all()
            paper_ids = [i.paper_id for i in items]
        elif source == "selected":
            ids_raw = request.form.get("paper_ids", "")
            paper_ids = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()]
        if not paper_ids:
            flash("No papers selected for export.", "error")
            return redirect(url_for("library"))
        ex = Export(
            user_id=current_user.id,
            export_id=new_export_id(),
            format=fmt,
            status="ready",
            paper_count=len(paper_ids),
            notes=notes,
        )
        db.session.add(ex)
        db.session.flush()
        for pid in paper_ids:
            db.session.add(ExportItem(export_id=ex.id, paper_id=pid))
        db.session.commit()
        flash("Export created.", "success")
        return redirect(url_for("export_detail", export_id=ex.export_id))
    # GET = show form
    library_items = LibraryItem.query.filter_by(user_id=current_user.id).all()
    starred_items = StarredPaper.query.filter_by(user_id=current_user.id).all()
    return render_template("export_create.html",
                           library_items=library_items, starred_items=starred_items)


@app.route("/export/<export_id>")
@login_required
def export_detail(export_id):
    ex = Export.query.filter_by(export_id=export_id, user_id=current_user.id).first_or_404()
    return render_template("export_detail.html", export=ex)


@app.route("/export/<export_id>/cancel", methods=["POST"])
@login_required
def export_cancel(export_id):
    ex = Export.query.filter_by(export_id=export_id, user_id=current_user.id).first_or_404()
    if ex.status == "ready":
        ex.status = "cancelled"
        db.session.commit()
        flash("Export cancelled.", "success")
    else:
        flash("Cannot cancel this export.", "error")
    return redirect(url_for("export_detail", export_id=export_id))


@app.route("/export/<export_id>/download")
@login_required
def export_download(export_id):
    ex = Export.query.filter_by(export_id=export_id, user_id=current_user.id).first_or_404()
    # Generate the text representation in-memory
    papers = [it.paper for it in ex.items if it.paper]
    if ex.format == "bibtex":
        lines = []
        for p in papers:
            key = p.arxiv_id.replace(".", "")
            lines.append("@article{arxiv" + key + ",")
            lines.append(f'  title = {{{p.title}}},')
            lines.append(f'  author = {{{" and ".join(p.get_authors())}}},')
            lines.append('  journal = {arXiv preprint arXiv:' + p.arxiv_id + '},')
            if p.submitted_date:
                lines.append(f'  year = {{{p.submitted_date[:4]}}},')
            lines.append("}")
            lines.append("")
        body = "\n".join(lines)
    elif ex.format == "ris":
        lines = []
        for p in papers:
            lines += ["TY  - JOUR", f"TI  - {p.title}"]
            for a in p.get_authors():
                lines.append(f"AU  - {a}")
            lines += [f"JO  - arXiv:{p.arxiv_id}", f"ID  - {p.arxiv_id}", "ER  - ", ""]
        body = "\n".join(lines)
    else:
        body = "\n\n".join(
            f"{p.title}\n{', '.join(p.get_authors())}\narXiv:{p.arxiv_id}" for p in papers
        )
    from flask import Response
    return Response(body, mimetype="text/plain",
                    headers={"Content-Disposition":
                             f"attachment; filename={ex.export_id}.{ex.format}"})


@app.route("/export/<export_id>/reorder", methods=["POST"])
@login_required
def export_reorder(export_id):
    ex = Export.query.filter_by(export_id=export_id, user_id=current_user.id).first_or_404()
    # Re-add the papers to library
    added = 0
    for it in ex.items:
        if not LibraryItem.query.filter_by(user_id=current_user.id, paper_id=it.paper_id).first():
            db.session.add(LibraryItem(user_id=current_user.id, paper_id=it.paper_id))
            added += 1
    db.session.commit()
    flash(f"Re-added {added} papers to your library.", "success")
    return redirect(url_for("library"))


# =======================================================================
# ROUTES — COMMENTS (review analog)
# =======================================================================

@app.route("/abs/<arxiv_id>/comment", methods=["POST"])
@login_required
def submit_comment(arxiv_id):
    paper = Paper.query.filter_by(arxiv_id=arxiv_id).first_or_404()
    title = (request.form.get("title") or "").strip()[:200]
    body = (request.form.get("body") or "").strip()
    rating = int(request.form.get("rating", 0) or 0)
    if not body:
        flash("Comment body cannot be empty.", "error")
    else:
        db.session.add(Comment(
            user_id=current_user.id, paper_id=paper.id,
            title=title, body=body, rating=max(0, min(5, rating)),
        ))
        db.session.commit()
        flash("Comment posted.", "success")
    return redirect(url_for("paper_detail", arxiv_id=arxiv_id))


@app.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    c = Comment.query.get_or_404(comment_id)
    if c.user_id != current_user.id:
        abort(403)
    paper_arxiv = c.paper.arxiv_id
    db.session.delete(c)
    db.session.commit()
    flash("Comment deleted.", "success")
    return redirect(url_for("paper_detail", arxiv_id=paper_arxiv))


# =======================================================================
# ROUTES — ALERTS
# =======================================================================

@app.route("/alerts", methods=["GET", "POST"])
@login_required
def alerts_page():
    if request.method == "POST":
        code = request.form.get("category_code", "").strip()
        freq = request.form.get("frequency", "weekly")
        if code:
            existing = Alert.query.filter_by(user_id=current_user.id, category_code=code).first()
            if existing:
                existing.frequency = freq
                existing.active = True
                flash("Alert updated.", "success")
            else:
                db.session.add(Alert(user_id=current_user.id,
                                     category_code=code, frequency=freq))
                flash("Alert created.", "success")
            db.session.commit()
        return redirect(url_for("alerts_page"))
    user_alerts = Alert.query.filter_by(user_id=current_user.id).all()
    return render_template("alerts.html", alerts=user_alerts)


@app.route("/alerts/<int:alert_id>/delete", methods=["POST"])
@login_required
def delete_alert(alert_id):
    alert = Alert.query.filter_by(id=alert_id, user_id=current_user.id).first_or_404()
    db.session.delete(alert)
    db.session.commit()
    flash("Alert removed.", "success")
    return redirect(url_for("alerts_page"))


# =======================================================================
# ROUTES — API
# =======================================================================

@app.route("/api/papers/<category_code>")
def api_papers(category_code):
    papers, total = get_papers_for_category(category_code, per_page=20)
    return jsonify({
        "category": category_code,
        "total": total,
        "papers": [{
            "arxiv_id": p.arxiv_id,
            "title": p.title,
            "authors": p.get_authors(),
            "abstract": p.short_abstract,
            "subjects": p.subjects,
            "pdf_url": p.pdf_url,
        } for p in papers],
    })


@app.route("/api/stats")
def api_stats():
    return jsonify({
        "total_papers": Paper.query.count(),
        "total_categories": Category.query.count(),
        "total_users": User.query.count(),
        "total_comments": Comment.query.count(),
    })


# =======================================================================
# ERROR HANDLERS
# =======================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Server error"), 500


# =======================================================================
# FORM-BASED (non-AJAX) routes for library + star — needed by browser agents
# =======================================================================

@app.route("/library/add/<int:paper_id>", methods=["POST"])
@login_required
def library_add_form(paper_id):
    """Form-POST equivalent of /api/library/add — redirects back."""
    paper = Paper.query.get_or_404(paper_id)
    folder = request.form.get("folder", "Reading List")
    existing = LibraryItem.query.filter_by(
        user_id=current_user.id, paper_id=paper_id).first()
    if not existing:
        db.session.add(LibraryItem(
            user_id=current_user.id, paper_id=paper_id, folder=folder))
        db.session.commit()
        flash("Added to your library.", "success")
    else:
        flash("Already in your library.", "info")
    return redirect(request.referrer or url_for("paper_detail",
                                                 arxiv_id=paper.arxiv_id))


@app.route("/library/remove/<int:item_id>", methods=["POST"])
@login_required
def library_remove_form(item_id):
    """Form-POST equivalent of /api/library/remove — redirects back."""
    item = LibraryItem.query.filter_by(
        id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Removed from library.", "success")
    return redirect(request.referrer or url_for("library"))


@app.route("/library/move/<int:item_id>", methods=["POST"])
@login_required
def library_move_folder(item_id):
    """Move a library item to a different folder via form POST."""
    item = LibraryItem.query.filter_by(
        id=item_id, user_id=current_user.id).first_or_404()
    new_folder = (request.form.get("folder") or "Reading List").strip()
    item.folder = new_folder
    db.session.commit()
    flash(f'Moved to folder "{new_folder}".', "success")
    return redirect(request.referrer or url_for("library"))


@app.route("/star/toggle/<int:paper_id>", methods=["POST"])
@login_required
def star_toggle_form(paper_id):
    """Form-POST equivalent of /api/star/toggle — redirects back."""
    paper = Paper.query.get_or_404(paper_id)
    existing = StarredPaper.query.filter_by(
        user_id=current_user.id, paper_id=paper_id).first()
    if existing:
        db.session.delete(existing)
        paper.star_count = max(0, paper.star_count - 1)
        flash("Removed from starred.", "success")
    else:
        db.session.add(StarredPaper(user_id=current_user.id, paper_id=paper_id))
        paper.star_count += 1
        flash("Added to starred.", "success")
    db.session.commit()
    return redirect(request.referrer or url_for("paper_detail",
                                                 arxiv_id=paper.arxiv_id))


# =======================================================================
# BENCHMARK SEED DATA
# =======================================================================

def seed_benchmark_users():
    """
    Create 4 benchmark users with pre-seeded library items, starred papers,
    and citation exports. Idempotent — check first user before running.
    """
    if User.query.filter_by(email="alice.j@test.com").first():
        return  # already seeded

    def _get_paper(arxiv_id: str):
        return Paper.query.filter_by(arxiv_id=arxiv_id).first()

    # ------------------------------------------------------------------
    # alice.j — NLP / ML researcher, heavy library user
    # ------------------------------------------------------------------
    alice = User(
        email="alice.j@test.com",
        username="alice_j",
        full_name="Alice Johnson",
        affiliation="MIT CSAIL",
        bio="NLP researcher focused on contrastive learning and sentence embeddings.",
        orcid="0000-0001-0001-0001",
    )
    alice.set_password("TestPass123!")
    db.session.add(alice)
    db.session.flush()

    alice_papers = [
        ("2104.08821", "Research"),   # SimCSE
        ("2011.05864", "Research"),   # Sentence Embeddings
        ("2004.04906", "Reading List"),  # DPR
        ("1905.01969", "Reading List"),  # Poly-encoder
        ("2303.08774", "To Read"),    # GPT-4 Technical Report
        ("2301.12345", "To Read"),    # NN Optimization
        ("2305.23456", "Research"),   # NN Low-Rank
        ("2309.34567", "Research"),   # Stochastic NN Opt
    ]
    for arxiv_id, folder in alice_papers:
        p = _get_paper(arxiv_id)
        if p:
            db.session.add(LibraryItem(
                user_id=alice.id, paper_id=p.id, folder=folder,
                added_at=datetime.utcnow() - timedelta(days=random.randint(1, 30))))

    alice_stars = ["2104.08821", "2011.05864", "2303.08774", "2401.00123"]
    for arxiv_id in alice_stars:
        p = _get_paper(arxiv_id)
        if p:
            db.session.add(StarredPaper(user_id=alice.id, paper_id=p.id,
                                        starred_at=datetime.utcnow() - timedelta(days=random.randint(1, 20))))

    db.session.commit()

    # Alice has a completed BibTeX export of her Research folder papers
    alice_research_ids = [
        _get_paper(aid).id for aid, folder in alice_papers
        if folder == "Research" and _get_paper(aid)
    ]
    if alice_research_ids:
        ex_alice = Export(
            user_id=alice.id,
            export_id="EX" + "20260101120000" + "001",
            format="bibtex",
            status="ready",
            paper_count=len(alice_research_ids),
            notes="Research papers export",
            created_at=datetime.utcnow() - timedelta(days=5),
        )
        db.session.add(ex_alice)
        db.session.flush()
        for pid in alice_research_ids:
            db.session.add(ExportItem(export_id=ex_alice.id, paper_id=pid))
        db.session.commit()

    # ------------------------------------------------------------------
    # bob.c — Computer Vision / Deep Learning, moderate library
    # ------------------------------------------------------------------
    bob = User(
        email="bob.c@test.com",
        username="bob_c",
        full_name="Bob Chen",
        affiliation="Stanford AI Lab",
        bio="Deep learning researcher specializing in computer vision and graph networks.",
        orcid="0000-0002-0002-0002",
    )
    bob.set_password("TestPass123!")
    db.session.add(bob)
    db.session.flush()

    bob_papers = [
        ("2303.11234", "Reading List"),  # Visual Prompting
        ("2304.22345", "Reading List"),  # Panoptic Segmentation
        ("2401.00123", "Favorites"),     # GNN Molecular
        ("2401.00456", "Favorites"),     # Scalable GNN
        ("2401.00789", "Reading List"),  # Temporal GNN
        ("2604.08209", "To Review"),     # OmniJigsaw
    ]
    for arxiv_id, folder in bob_papers:
        p = _get_paper(arxiv_id)
        if p:
            db.session.add(LibraryItem(
                user_id=bob.id, paper_id=p.id, folder=folder,
                added_at=datetime.utcnow() - timedelta(days=random.randint(1, 45))))

    bob_stars = ["2303.11234", "2401.00123", "2401.00456"]
    for arxiv_id in bob_stars:
        p = _get_paper(arxiv_id)
        if p:
            db.session.add(StarredPaper(user_id=bob.id, paper_id=p.id,
                                        starred_at=datetime.utcnow() - timedelta(days=random.randint(1, 15))))

    db.session.commit()

    # Bob has an RIS export of his Favorites
    bob_fav_ids = [
        _get_paper(aid).id for aid, folder in bob_papers
        if folder == "Favorites" and _get_paper(aid)
    ]
    if bob_fav_ids:
        ex_bob = Export(
            user_id=bob.id,
            export_id="EX" + "20260115090000" + "002",
            format="ris",
            status="ready",
            paper_count=len(bob_fav_ids),
            notes="Favorites RIS export",
            created_at=datetime.utcnow() - timedelta(days=10),
        )
        db.session.add(ex_bob)
        db.session.flush()
        for pid in bob_fav_ids:
            db.session.add(ExportItem(export_id=ex_bob.id, paper_id=pid))
        db.session.commit()

    # ------------------------------------------------------------------
    # carol.d — Statistics / ML Theory, focused reader
    # ------------------------------------------------------------------
    carol = User(
        email="carol.d@test.com",
        username="carol_d",
        full_name="Carol Davis",
        affiliation="UC Berkeley Statistics",
        bio="Statistical ML researcher. Interested in Bayesian methods and diffusion models.",
        orcid="0000-0003-0003-0003",
    )
    carol.set_password("TestPass123!")
    db.session.add(carol)
    db.session.flush()

    carol_papers = [
        ("2412.03134", "ML Theory"),   # Diffusion Noise
        ("2602.22486", "ML Theory"),   # Flow Matching
        ("2510.23199", "Reading List"), # Best Arm ID
        ("2512.12911", "Reading List"), # SVD for DNN
        ("2409.19567", "Reading List"), # math.OC paper
        ("2104.08821", "NLP"),          # SimCSE
        ("2011.05864", "NLP"),          # Sentence Embeddings
    ]
    for arxiv_id, folder in carol_papers:
        p = _get_paper(arxiv_id)
        if p:
            db.session.add(LibraryItem(
                user_id=carol.id, paper_id=p.id, folder=folder,
                added_at=datetime.utcnow() - timedelta(days=random.randint(1, 60))))

    carol_stars = ["2412.03134", "2602.22486", "2510.23199"]
    for arxiv_id in carol_stars:
        p = _get_paper(arxiv_id)
        if p:
            db.session.add(StarredPaper(user_id=carol.id, paper_id=p.id,
                                        starred_at=datetime.utcnow() - timedelta(days=random.randint(1, 25))))

    db.session.commit()

    # Carol has two ready exports (ML Theory BibTeX + NLP RIS) for disambiguation
    carol_theory_ids = [
        _get_paper(aid).id for aid, folder in carol_papers
        if folder == "ML Theory" and _get_paper(aid)
    ]
    carol_nlp_ids = [
        _get_paper(aid).id for aid, folder in carol_papers
        if folder == "NLP" and _get_paper(aid)
    ]
    if carol_nlp_ids:
        ex_carol_nlp = Export(
            user_id=carol.id,
            export_id="EX" + "20260110080000" + "003",
            format="ris",
            status="ready",
            paper_count=len(carol_nlp_ids),
            notes="NLP papers RIS",
            created_at=datetime.utcnow() - timedelta(days=15),
        )
        db.session.add(ex_carol_nlp)
        db.session.flush()
        for pid in carol_nlp_ids:
            db.session.add(ExportItem(export_id=ex_carol_nlp.id, paper_id=pid))

    if carol_theory_ids:
        ex_carol_ready = Export(
            user_id=carol.id,
            export_id="EX" + "20260120143000" + "004",
            format="bibtex",
            status="ready",
            paper_count=len(carol_theory_ids),
            notes="ML Theory papers BibTeX",
            created_at=datetime.utcnow() - timedelta(days=3),
        )
        db.session.add(ex_carol_ready)
        db.session.flush()
        for pid in carol_theory_ids:
            db.session.add(ExportItem(export_id=ex_carol_ready.id, paper_id=pid))
    db.session.commit()

    # ------------------------------------------------------------------
    # david.k — Quantum / Physics, small library
    # ------------------------------------------------------------------
    david = User(
        email="david.k@test.com",
        username="david_k",
        full_name="David Kim",
        affiliation="Caltech Physics",
        bio="Quantum information and quantum computing researcher.",
        orcid="0000-0004-0004-0004",
    )
    david.set_password("TestPass123!")
    db.session.add(david)
    db.session.flush()

    david_papers = [
        ("2312.17719", "Quantum"),    # quant-ph paper
        ("2402.17148", "Quantum"),    # quant-ph paper
        ("2410.19541", "Reading List"),  # quant-ph paper
        ("2303.08774", "Reading List"),  # GPT-4 (cross-domain interest)
        ("2401.00123", "Reading List"),  # GNN Molecular
    ]
    for arxiv_id, folder in david_papers:
        p = _get_paper(arxiv_id)
        if p:
            db.session.add(LibraryItem(
                user_id=david.id, paper_id=p.id, folder=folder,
                added_at=datetime.utcnow() - timedelta(days=random.randint(1, 30))))

    david_stars = ["2312.17719", "2402.17148"]
    for arxiv_id in david_stars:
        p = _get_paper(arxiv_id)
        if p:
            db.session.add(StarredPaper(user_id=david.id, paper_id=p.id,
                                        starred_at=datetime.utcnow() - timedelta(days=random.randint(1, 10))))

    db.session.commit()

    # David has a ready plaintext export of his starred papers
    david_star_ids = [
        _get_paper(aid).id for aid in david_stars if _get_paper(aid)
    ]
    if david_star_ids:
        ex_david = Export(
            user_id=david.id,
            export_id="EX" + "20260201110000" + "005",
            format="endnote",
            status="ready",
            paper_count=len(david_star_ids),
            notes="Starred quantum papers",
            created_at=datetime.utcnow() - timedelta(days=7),
        )
        db.session.add(ex_david)
        db.session.flush()
        for pid in david_star_ids:
            db.session.add(ExportItem(export_id=ex_david.id, paper_id=pid))
        db.session.commit()

    # ------------------------------------------------------------------
    # Alerts for disambiguation tasks
    # ------------------------------------------------------------------
    for u, alerts_list in [
        (alice, [("cs", "daily"), ("math", "weekly")]),
        (bob, [("cs", "daily"), ("physics", "weekly")]),
        (david, [("physics", "daily"), ("math", "weekly")]),
    ]:
        for cat_code, freq in alerts_list:
            db.session.add(Alert(
                user_id=u.id, category_code=cat_code, frequency=freq,
            ))
    db.session.commit()

    print("  [+] Seeded 4 benchmark users (alice/bob/carol/david)")


# =======================================================================
# MAIN
# =======================================================================

def backfill_paper_gaps():
    """Patch pre-existing Paper rows with empty authors / abstract so the
    /abs, listing, and /list/<code>/new views never render blank content.

    Safe to run every startup: only rewrites rows whose authors_json is
    empty ('[]'/''/None) or whose abstract is empty. No other fields are
    touched.
    """
    try:
        empty_author_rows = Paper.query.filter(
            or_(Paper.authors_json == "[]",
                Paper.authors_json == "",
                Paper.authors_json.is_(None))
        ).all()
        n_auth = 0
        for p in empty_author_rows:
            authors = _synthesize_authors(p.arxiv_id or "")
            if authors:
                p.authors_json = json.dumps(authors)
                p.n_authors = len(authors)
                n_auth += 1
        empty_abs_rows = Paper.query.filter(
            or_(Paper.abstract == "", Paper.abstract.is_(None))
        ).all()
        n_abs = 0
        for p in empty_abs_rows:
            text = _synthesize_abstract(p.title or "",
                                        p.primary_subject_code or "",
                                        p.primary_subject or "")
            if text:
                p.abstract = text
                n_abs += 1
        if n_auth or n_abs:
            db.session.commit()
            print(f"  [+] Backfilled {n_auth} author lists and {n_abs} abstracts")
    except Exception as e:
        db.session.rollback()
        print(f"  ! backfill_paper_gaps failed: {e}")


def normalize_paper_metadata():
    """Normalize known duplicated LaTeX/text fragments in existing DB rows."""
    try:
        changed = 0
        for paper in Paper.query.all():
            for field in ("title", "abstract", "comments"):
                current = getattr(paper, field) or ""
                cleaned = _clean_arxiv_metadata_text(current)
                if cleaned != current:
                    setattr(paper, field, cleaned)
                    changed += 1
        if changed:
            db.session.commit()
            print(f"  [+] Normalized {changed} arXiv metadata fields")
    except Exception as e:
        db.session.rollback()
        print(f"  ! normalize_paper_metadata failed: {e}")


def ensure_affiliation_column():
    """Ensure the author_affiliations_json column exists on older DBs."""
    try:
        from sqlalchemy import text
        cols = db.session.execute(text(
            "PRAGMA table_info(papers)"
        )).fetchall()
        have = {c[1] for c in cols}
        if "author_affiliations_json" not in have:
            db.session.execute(text(
                "ALTER TABLE papers ADD COLUMN "
                "author_affiliations_json TEXT DEFAULT '[]'"
            ))
            db.session.commit()
            print("  [+] Added papers.author_affiliations_json column")
    except Exception as e:
        db.session.rollback()
        print(f"  ! ensure_affiliation_column failed: {e}")


def backfill_affiliations():
    """Populate author_affiliations_json for every paper that lacks it."""
    try:
        rows = Paper.query.filter(
            or_(Paper.author_affiliations_json == "[]",
                Paper.author_affiliations_json == "",
                Paper.author_affiliations_json.is_(None))
        ).all()
        n = 0
        for p in rows:
            authors = p.get_authors()
            if not authors:
                continue
            p.author_affiliations_json = json.dumps(
                _affiliations_for_authors(authors)
            )
            n += 1
        if n:
            db.session.commit()
            print(f"  [+] Backfilled affiliations for {n} papers")
    except Exception as e:
        db.session.rollback()
        print(f"  ! backfill_affiliations failed: {e}")


with app.app_context():
    db.create_all()
    ensure_affiliation_column()
    seed_database()
    seed_benchmark_users()
    backfill_paper_gaps()
    normalize_paper_metadata()
    backfill_affiliations()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 28842))
    app.run(host="0.0.0.0", port=port, debug=False)
