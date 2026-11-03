#!/usr/bin/env python3
"""stanford_university — a WebHarbor mirror of https://www.stanford.edu/

Flask + SQLite mirror of the Stanford University domain: the homepage
sections, the seven-school department directory with the bulletin's
150 academic units, the ExploreCourses-style course catalog (5,420 real
bulletin courses with search and department/career/term/units/WAYS
filters), the degree-programs directory (355 bulletin programs with a
compare view), the Stanford Profiles faculty directory (1,535 real CAP
profiles with search and department filters), Stanford Report news (210
real stories with category/topic filters and search), the campus events
calendar (596 real Localist events with category/date filters and
search), the 2026-27 academic calendar, the libraries directory with
captured weekly hours, and the undergraduate admission + financial aid
pages, seeded for four benchmark users with a course planner and saved
events.

Content comes from the tracked source_data/*.json snapshots captured from
stanford.edu and its public subdomains on 2026-09-30 (see provenance.json);
the SQLite seed is materialized deterministically at image build time
(PYTHONHASHSEED=0).
"""
import json
import os
import secrets
from datetime import datetime, timezone

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError
from markupsafe import Markup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# packed faculty photo assets (see Faculty.photo_url) — resolved once at boot
_FACULTY_PHOTO_DIR = os.path.join(BASE_DIR, 'static', 'images', 'upstream', 'faculty')
_FACULTY_PHOTO_ASSETS = frozenset(os.listdir(_FACULTY_PHOTO_DIR)) \
    if os.path.isdir(_FACULTY_PHOTO_DIR) else frozenset()

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("STANFORD_UNIVERSITY_SECRET_KEY") or secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'STANFORD_UNIVERSITY_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'stanford_university.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None
app.config['MAX_CONTENT_LENGTH'] = 256 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to continue.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

SITE_NAME = 'stanford_university'
UPSTREAM = 'https://www.stanford.edu/'
MIRROR_DATE = '2026-09-30'
# The frozen benchmark clock: every "upcoming"/"newest" filter compares
# against this date, never the wall clock, so pages render identically on
# every run and every day (the events snapshot was captured 2026-09-30).
BENCHMARK_NOW = datetime(2026, 9, 30, 12, 0, 0)

SCHOOLS = [
    ('doerr', 'Stanford Doerr School of Sustainability'),
    ('gsb', 'Graduate School of Business'),
    ('gse', 'Graduate School of Education'),
    ('engineering', 'School of Engineering'),
    ('hns', 'School of Humanities and Sciences'),
    ('law', 'School of Law'),
    ('medicine', 'School of Medicine'),
]
SCHOOL_NAMES = dict(SCHOOLS)

NEWS_CATEGORIES = ['University News', 'Research & Scholarship', 'On Campus',
                   'Student Experience', 'Artificial Intelligence']
PER_PAGE = 20

# ---- deterministic schema creation -------------------------------------
# SQLAlchemy's create_all() emits CREATE INDEX statements in Table.indexes
# set order; that set is keyed by object identity, so the DDL order varies
# between processes and two seed builds would not be byte-identical. We
# therefore declare no index=True columns and create the indexes here in
# sorted order, with tables created in sorted-name order as well.
SCHEMA_INDEX_DDL = (
    'CREATE INDEX IF NOT EXISTS ix_courses_subject ON courses (subject)',
    'CREATE INDEX IF NOT EXISTS ix_events_first_date ON events (first_date)',
    'CREATE INDEX IF NOT EXISTS ix_faculty_department ON faculty (department)',
    'CREATE INDEX IF NOT EXISTS ix_news_category ON news (category)',
)


def create_schema():
    """Create all tables and indexes in a deterministic order."""
    tables = [db.metadata.tables[name]
              for name in sorted(db.metadata.tables)]
    db.metadata.create_all(db.engine, tables=tables)
    from sqlalchemy import text as _sa_text
    with db.engine.begin() as conn:
        for stmt in SCHEMA_INDEX_DDL:
            conn.execute(_sa_text(stmt))


# ── models ──────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.String(32), nullable=False, default='')

    planner = db.relationship('PlannedCourse', backref='user', lazy=True,
                              order_by='PlannedCourse.position')
    saved_events = db.relationship('SavedEvent', backref='user', lazy=True,
                                   order_by='SavedEvent.position')


class Department(db.Model):
    __tablename__ = 'departments'
    code = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    school = db.Column(db.String(40), nullable=False)
    description = db.Column(db.Text)
    subject_codes = db.Column(db.Text, nullable=False, default='[]')

    @property
    def subject_code_list(self):
        return json.loads(self.subject_codes)


class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    subject = db.Column(db.String(20))
    number = db.Column(db.String(20))
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    units_min = db.Column(db.Float)
    units_max = db.Column(db.Float)
    career = db.Column(db.String(80))
    college = db.Column(db.String(200))
    grade_mode = db.Column(db.String(200))
    terms_json = db.Column(db.Text, nullable=False, default='[]')
    ways_json = db.Column(db.Text, nullable=False, default='[]')
    components_json = db.Column(db.Text, nullable=False, default='[]')
    requisites_json = db.Column(db.Text)
    departments_json = db.Column(db.Text, nullable=False, default='[]')

    @property
    def terms(self):
        return json.loads(self.terms_json)

    @property
    def ways(self):
        return json.loads(self.ways_json)

    @property
    def components(self):
        return json.loads(self.components_json)

    @property
    def requisites(self):
        if not self.requisites_json:
            return []
        value = json.loads(self.requisites_json)
        return value or []

    @property
    def departments(self):
        return json.loads(self.departments_json)

    @property
    def units_display(self):
        if self.units_min is None:
            return ''
        if self.units_max is not None and self.units_max != self.units_min:
            return f'{self.units_min:g}-{self.units_max:g}'
        return f'{self.units_min:g}'


class Program(db.Model):
    __tablename__ = 'programs'
    code = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    type = db.Column(db.String(80))
    level = db.Column(db.String(120))
    college = db.Column(db.String(200))
    description = db.Column(db.Text)
    degree_designation = db.Column(db.String(200))
    units_min = db.Column(db.Integer)
    webpage = db.Column(db.String(300))
    requirements_json = db.Column(db.Text, nullable=False, default='[]')
    departments_json = db.Column(db.Text, nullable=False, default='[]')

    @property
    def requirements(self):
        return json.loads(self.requirements_json)

    @property
    def departments(self):
        return json.loads(self.departments_json)

    @property
    def kind(self):
        t = (self.type or '')
        if 'Major' in t:
            return 'Major'
        if 'Minor' in t:
            return 'Minor'
        if 'MS' in t or 'Master' in t:
            return "Master's"
        if 'PhD' in t or 'Doctor' in t or 'PHD' in t:
            return 'Doctoral'
        if 'Coterm' in t:
            return 'Coterminal'
        return 'Program'


class Faculty(db.Model):
    __tablename__ = 'faculty'
    profile_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    department = db.Column(db.String(200))
    short_title = db.Column(db.String(400))
    titles_json = db.Column(db.Text, nullable=False, default='[]')
    bio = db.Column(db.Text)
    research_interests = db.Column(db.Text)
    education_json = db.Column(db.Text, nullable=False, default='[]')
    publications_json = db.Column(db.Text, nullable=False, default='[]')
    publication_count = db.Column(db.Integer, nullable=False, default=0)
    email = db.Column(db.String(200))
    photo = db.Column(db.String(200))

    # Faculty photos are packed per profile
    # (up to 12 per department, saved as faculty_<profile_id>.jpg); the seed
    # mirrors the upstream CDN filename in Faculty.photo, which is not on
    # disk. Map to the packed per-profile asset when present, and render no
    # image otherwise, so no profile page ever references a missing file.

    @property
    def titles(self):
        return json.loads(self.titles_json)

    @property
    def education(self):
        return json.loads(self.education_json)

    @property
    def publications(self):
        return json.loads(self.publications_json)

    @property
    def photo_url(self):
        local = f'faculty_{self.profile_id}.jpg'
        if local in _FACULTY_PHOTO_ASSETS:
            return url_for('static', filename=f'images/upstream/faculty/{local}')
        return None


class NewsArticle(db.Model):
    __tablename__ = 'news'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(400), nullable=False)
    published_ts = db.Column(db.Integer)
    category = db.Column(db.String(120))
    main_topic = db.Column(db.String(200))
    topics_json = db.Column(db.Text, nullable=False, default='[]')
    featured_unit = db.Column(db.String(300))
    writers_json = db.Column(db.Text, nullable=False, default='[]')
    description = db.Column(db.Text)
    body_json = db.Column(db.Text, nullable=False, default='[]')
    image = db.Column(db.String(200))

    @property
    def topics(self):
        return json.loads(self.topics_json)

    @property
    def writers(self):
        return json.loads(self.writers_json)

    @property
    def body(self):
        return json.loads(self.body_json)

    @property
    def published_display(self):
        if not self.published_ts:
            return ''
        dt = datetime.fromtimestamp(self.published_ts, tz=timezone.utc)
        return dt.strftime('%B %-d, %Y')

    @property
    def image_url(self):
        if self.image:
            return url_for('static', filename=f'images/upstream/news/{self.image}')
        return None


class CampusEvent(db.Model):
    __tablename__ = 'events'
    eid = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(400), nullable=False)
    description = db.Column(db.Text)
    first_date = db.Column(db.String(20))
    last_date = db.Column(db.String(20))
    location_name = db.Column(db.String(300))
    room_number = db.Column(db.String(100))
    address = db.Column(db.String(300))
    experience = db.Column(db.String(40))
    free = db.Column(db.Boolean, nullable=False, default=False)
    ticket_url = db.Column(db.String(400))
    ticket_cost = db.Column(db.String(200))
    tags_json = db.Column(db.Text, nullable=False, default='[]')
    keywords_json = db.Column(db.Text, nullable=False, default='[]')
    recurring = db.Column(db.Boolean, nullable=False, default=False)
    featured = db.Column(db.Boolean, nullable=False, default=False)
    verified = db.Column(db.Boolean, nullable=False, default=False)
    photo = db.Column(db.String(200))
    instances_json = db.Column(db.Text, nullable=False, default='[]')

    @property
    def tags(self):
        return json.loads(self.tags_json)

    @property
    def keywords(self):
        return json.loads(self.keywords_json)

    @property
    def instances(self):
        return json.loads(self.instances_json)

    @property
    def photo_url(self):
        if self.photo:
            return url_for('static', filename=f'images/upstream/events/{self.photo}')
        return None

    @property
    def month_key(self):
        return (self.first_date or '')[:7]


class CalendarEntry(db.Model):
    __tablename__ = 'calendar_entries'
    id = db.Column(db.Integer, primary_key=True)
    quarter = db.Column(db.String(80), nullable=False)
    quarter_key = db.Column(db.String(20), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    when_text = db.Column(db.String(200), nullable=False)
    what = db.Column(db.Text, nullable=False)


class Library(db.Model):
    __tablename__ = 'libraries'
    slug = db.Column(db.String(120), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(300))
    phone = db.Column(db.String(60))
    email = db.Column(db.String(200))
    about = db.Column(db.Text)
    quick_links_json = db.Column(db.Text, nullable=False, default='[]')
    research_subjects_json = db.Column(db.Text, nullable=False, default='[]')
    hours_days_json = db.Column(db.Text, nullable=False, default='[]')
    hours_rows_json = db.Column(db.Text, nullable=False, default='[]')
    photo = db.Column(db.String(200))

    @property
    def quick_links(self):
        return json.loads(self.quick_links_json)

    @property
    def research_subjects(self):
        return json.loads(self.research_subjects_json)

    @property
    def hours_days(self):
        return json.loads(self.hours_days_json)

    @property
    def hours_rows(self):
        return json.loads(self.hours_rows_json)

    @property
    def photo_url(self):
        if self.photo:
            return url_for('static', filename=f'images/upstream/libraries/{self.photo}')
        return None


class AdmissionInfo(db.Model):
    __tablename__ = 'admission_info'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(40), unique=True, nullable=False)
    value_json = db.Column(db.Text, nullable=False, default='[]')

    @property
    def value(self):
        return json.loads(self.value_json)


class PlannedCourse(db.Model):
    __tablename__ = 'planned_courses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_code = db.Column(db.String(30), db.ForeignKey('courses.code'), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    added_at = db.Column(db.String(32), nullable=False, default='')


class SavedEvent(db.Model):
    __tablename__ = 'saved_events'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_eid = db.Column(db.Integer, db.ForeignKey('events.eid'), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    added_at = db.Column(db.String(32), nullable=False, default='')


# ── auth plumbing ───────────────────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _validate_csrf_token():
    """CSRF stays enabled everywhere; helpers submit the real token."""
    token = request.form.get('csrf_token', '')
    try:
        validate_csrf(token)
    except ValidationError:
        return False
    return True


# ── helpers ──────────────────────────────────────────────────────────────────

def _school_name(key):
    return SCHOOL_NAMES.get(key, key)


def _dept_name(code):
    d = Department.query.filter_by(code=code).first()
    return d.name if d else code


def _parse_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ── view routes ──────────────────────────────────────────────────────────────

@app.route('/')
def home():
    top_news = NewsArticle.query.order_by(NewsArticle.published_ts.desc()).limit(4).all()
    upcoming = (CampusEvent.query
                .filter(CampusEvent.first_date >= '2026-10-01')
                .order_by(CampusEvent.first_date, CampusEvent.eid).limit(4).all())
    depts_count = Department.query.count()
    courses_count = Course.query.count()
    faculty_count = Faculty.query.count()
    return render_template('home.html', top_news=top_news, upcoming=upcoming,
                           depts_count=depts_count, courses_count=courses_count,
                           faculty_count=faculty_count, schools=SCHOOLS)


@app.route('/departments')
def departments():
    q = (request.args.get('q') or '').strip()
    school = request.args.get('school') or ''
    page = max(1, _parse_int(request.args.get('page'), 1))
    query = Department.query
    if q:
        like = f'%{q}%'
        query = query.filter(Department.name.ilike(like) | Department.code.ilike(like))
    if school:
        query = query.filter_by(school=school)
    total = query.count()
    rows = (query.order_by(Department.name)
            .offset((page - 1) * PER_PAGE).limit(PER_PAGE).all())
    return render_template('departments.html', departments=rows, q=q,
                           school=school, schools=SCHOOLS,
                           school_name=_school_name, total=total,
                           page=page, pages=max(1, (total + PER_PAGE - 1) // PER_PAGE))


@app.route('/departments/<code>')
def department_detail(code):
    dept = Department.query.filter_by(code=code).first_or_404()
    programs = Program.query.filter(Program.departments_json.contains(f'"{code}"')) \
        .order_by(Program.name).all()
    subject_codes = dept.subject_code_list
    courses = []
    for sc in subject_codes:
        courses.extend(Course.query.filter_by(subject=sc).order_by(Course.number).all())
    courses = courses[:60]
    faculty = Faculty.query.filter_by(department=dept.name).order_by(Faculty.last_name).all()
    return render_template('department_detail.html', dept=dept, programs=programs,
                           courses=courses, faculty=faculty[:24],
                           school_name=_school_name(dept.school))


@app.route('/programs')
def programs():
    q = (request.args.get('q') or '').strip()
    kind = request.args.get('kind') or ''
    dept = request.args.get('dept') or ''
    page = max(1, _parse_int(request.args.get('page'), 1))
    query = Program.query
    if q:
        like = f'%{q}%'
        query = query.filter(Program.name.ilike(like) | Program.code.ilike(like))
    if kind:
        query = query.filter(Program.type.ilike(f'%{kind}%'))
    if dept:
        query = query.filter(Program.departments_json.contains(f'"{dept}"'))
    total = query.count()
    rows = (query.order_by(Program.name)
            .offset((page - 1) * PER_PAGE).limit(PER_PAGE).all())
    dept_codes = sorted({c for p in Program.query.all() for c in p.departments})
    return render_template('programs.html', programs=rows, q=q, kind=kind,
                           dept=dept, dept_codes=dept_codes, total=total,
                           page=page, pages=max(1, (total + PER_PAGE - 1) // PER_PAGE))


@app.route('/programs/<code>')
def program_detail(code):
    program = Program.query.filter_by(code=code).first_or_404()
    dept_names = [(c, _dept_name(c)) for c in program.departments]
    compare = None
    compare_code = request.args.get('compare') or ''
    if compare_code and compare_code != code:
        compare = Program.query.filter_by(code=compare_code).first()
    return render_template('program_detail.html', program=program,
                           dept_names=dept_names, compare=compare,
                           comparison_options=Program.query.order_by(Program.name).all())


@app.route('/courses')
def courses():
    q = (request.args.get('q') or '').strip()
    subject = request.args.get('subject') or ''
    dept = request.args.get('dept') or ''
    career = request.args.get('career') or ''
    term = request.args.get('term') or ''
    ways = request.args.get('ways') or ''
    page = max(1, _parse_int(request.args.get('page'), 1))
    query = Course.query
    if q:
        like = f'%{q}%'
        query = query.filter(Course.code.ilike(like) | Course.title.ilike(like)
                             | Course.description.ilike(like))
    if subject:
        query = query.filter_by(subject=subject)
    if dept:
        query = query.filter(Course.departments_json.contains(f'"{dept}"'))
    if career:
        # exact match: the upstream catalog filter treats "Graduate" and
        # "Undergraduate" as distinct careers; a substring match here would
        # also hit "Undergraduate" rows when "Graduate" is selected
        query = query.filter(Course.career == career)
    if term:
        query = query.filter(Course.terms_json.contains(f'"{term}"'))
    if ways:
        query = query.filter(Course.ways_json.contains(ways))
    total = query.count()
    rows = (query.order_by(Course.code)
            .offset((page - 1) * PER_PAGE).limit(PER_PAGE).all())
    subjects = sorted({c.subject for c in Course.query.with_entities(Course.subject)})
    dept_codes = sorted({c for cr in Course.query.all() for c in cr.departments})
    return render_template('courses.html', courses=rows, q=q, subject=subject,
                           dept=dept, career=career, term=term, ways=ways,
                           subjects=subjects, dept_codes=dept_codes,
                           dept_name=_dept_name, total=total, page=page,
                           pages=max(1, (total + PER_PAGE - 1) // PER_PAGE))


@app.route('/courses/<code>')
def course_detail(code):
    course = Course.query.filter_by(code=code).first_or_404()
    dept_names = [(c, _dept_name(c)) for c in course.departments]
    prereqs = []
    for r in course.requisites:
        if isinstance(r, dict):
            label = r.get('label') or r.get('name') or ''
            if isinstance(label, dict):
                label = label.get('text') or ''
            if label:
                prereqs.append(str(label))
        elif r:
            prereqs.append(str(r))
    related = Course.query.filter_by(subject=course.subject) \
        .filter(Course.code != course.code).order_by(Course.code).limit(8).all()
    return render_template('course_detail.html', course=course,
                           dept_names=dept_names, prereqs=prereqs, related=related)


@app.route('/faculty')
def faculty():
    q = (request.args.get('q') or '').strip()
    dept = request.args.get('dept') or ''
    page = max(1, _parse_int(request.args.get('page'), 1))
    query = Faculty.query
    if q:
        like = f'%{q}%'
        # profiles.stanford.edu's directory search also matches bios (the
        # live search for "Aerospace Design Laboratory" hits its director),
        # so the mirror searches name, title, research interests and bio
        query = query.filter(Faculty.name.ilike(like) | Faculty.short_title.ilike(like)
                             | Faculty.research_interests.ilike(like)
                             | Faculty.bio.ilike(like))
    if dept:
        query = query.filter_by(department=dept)
    total = query.count()
    rows = (query.order_by(Faculty.last_name, Faculty.first_name)
            .offset((page - 1) * PER_PAGE).limit(PER_PAGE).all())
    depts = sorted({f.department for f in Faculty.query.with_entities(Faculty.department) if f.department})
    return render_template('faculty.html', faculty=rows, q=q, dept=dept,
                           depts=depts, total=total, page=page,
                           pages=max(1, (total + PER_PAGE - 1) // PER_PAGE))


@app.route('/faculty/<int:profile_id>')
def faculty_detail(profile_id):
    person = Faculty.query.filter_by(profile_id=profile_id).first_or_404()
    dept_faculty = Faculty.query.filter_by(department=person.department) \
        .filter(Faculty.profile_id != person.profile_id) \
        .order_by(Faculty.last_name).limit(6).all()
    return render_template('faculty_detail.html', person=person,
                           dept_faculty=dept_faculty)


@app.route('/news')
def news():
    q = (request.args.get('q') or '').strip()
    category = request.args.get('category') or ''
    topic = request.args.get('topic') or ''
    page = max(1, _parse_int(request.args.get('page'), 1))
    query = NewsArticle.query
    if q:
        like = f'%{q}%'
        query = query.filter(NewsArticle.title.ilike(like)
                            | NewsArticle.description.ilike(like)
                            | NewsArticle.body_json.ilike(like))
    if category:
        query = query.filter_by(category=category)
    if topic:
        query = query.filter(NewsArticle.topics_json.contains(topic))
    total = query.count()
    rows = (query.order_by(NewsArticle.published_ts.desc())
            .offset((page - 1) * PER_PAGE).limit(PER_PAGE).all())
    topics = sorted({t for a in NewsArticle.query.all() for t in a.topics})
    return render_template('news.html', articles=rows, q=q, category=category,
                           topic=topic, topics=topics,
                           categories=NEWS_CATEGORIES, total=total, page=page,
                           pages=max(1, (total + PER_PAGE - 1) // PER_PAGE))


@app.route('/news/<slug>')
def news_detail(slug):
    article = NewsArticle.query.filter_by(slug=slug).first_or_404()
    related = NewsArticle.query.filter(NewsArticle.id != article.id) \
        .filter((NewsArticle.category == article.category)
                | (NewsArticle.main_topic == article.main_topic)) \
        .order_by(NewsArticle.published_ts.desc()).limit(4).all()
    return render_template('news_detail.html', article=article, related=related)


@app.route('/events')
def events():
    q = (request.args.get('q') or '').strip()
    tag = request.args.get('tag') or ''
    month = request.args.get('month') or ''
    when = request.args.get('when') or ''
    page = max(1, _parse_int(request.args.get('page'), 1))
    query = CampusEvent.query
    if q:
        like = f'%{q}%'
        query = query.filter(CampusEvent.title.ilike(like)
                             | CampusEvent.description.ilike(like))
    if tag:
        query = query.filter(CampusEvent.tags_json.contains(tag))
    if month:
        query = query.filter(CampusEvent.first_date.ilike(f'{month}%'))
    if when == 'upcoming':
        query = query.filter(CampusEvent.first_date >= '2026-10-01')
    elif when == 'past':
        query = query.filter(CampusEvent.first_date < '2026-10-01')
    total = query.count()
    rows = (query.order_by(CampusEvent.first_date, CampusEvent.eid)
            .offset((page - 1) * PER_PAGE).limit(PER_PAGE).all())
    tags = sorted({t for e in CampusEvent.query.all() for t in e.tags})
    months = sorted({e.month_key for e in CampusEvent.query.all() if e.month_key})
    return render_template('events.html', events=rows, q=q, tag=tag, month=month,
                           when=when, tags=tags, months=months, total=total,
                           page=page, pages=max(1, (total + PER_PAGE - 1) // PER_PAGE))


@app.route('/events/<int:eid>')
def event_detail(eid):
    event = CampusEvent.query.filter_by(eid=eid).first_or_404()
    related = CampusEvent.query.filter(CampusEvent.eid != eid) \
        .filter(CampusEvent.location_name == event.location_name) \
        .order_by(CampusEvent.first_date).limit(4).all()
    if not related:
        related = CampusEvent.query.filter(CampusEvent.eid != eid) \
            .order_by(CampusEvent.first_date).limit(4).all()
    saved = False
    if current_user.is_authenticated:
        saved = SavedEvent.query.filter_by(user_id=current_user.id,
                                           event_eid=eid).first() is not None
    return render_template('event_detail.html', event=event, related=related,
                           saved=saved)


@app.route('/academic-calendar')
def academic_calendar():
    quarter = request.args.get('quarter') or 'autumn'
    quarters = ['autumn', 'winter', 'spring', 'summer']
    if quarter not in quarters:
        quarter = 'autumn'
    entries = CalendarEntry.query.filter_by(quarter_key=quarter) \
        .order_by(CalendarEntry.position).all()
    return render_template('academic_calendar.html', entries=entries,
                           quarter=quarter, quarters=quarters)


@app.route('/libraries')
def libraries():
    q = (request.args.get('q') or '').strip()
    query = Library.query
    if q:
        like = f'%{q}%'
        query = query.filter(Library.name.ilike(like)
                             | Library.location.ilike(like))
    rows = query.order_by(Library.name).all()
    return render_template('libraries.html', libraries=rows, q=q,
                           week_label='Sep 27, 2026 – Oct 03, 2026')


@app.route('/libraries/<slug>')
def library_detail(slug):
    lib = Library.query.filter_by(slug=slug).first_or_404()
    return render_template('library_detail.html', lib=lib,
                           week_label='Sep 27, 2026 – Oct 03, 2026')


@app.route('/admission')
def admission():
    info = AdmissionInfo.query.filter_by(key='admission').first()
    data = info.value if info else {}
    return render_template('admission.html', data=data)


@app.route('/admission/aid')
def admission_aid():
    info = AdmissionInfo.query.filter_by(key='admission').first()
    data = info.value if info else {}
    estimate = None
    if request.args.get('income'):
        try:
            income = int(request.args.get('income'))
            family = int(request.args.get('family') or 2)
        except ValueError:
            income = None
            family = None
        if income is not None and income >= 0 and 1 <= family <= 10:
            if income < 100000:
                tuition = 'No tuition responsibility'
                room = 'No tuition or room and board responsibility'
            elif income < 150000:
                tuition = 'No tuition responsibility'
                room = ('Room and board responsibility applies '
                        '(the no-room-and-board threshold is below $100,000)' )
            else:
                tuition = ('No automatic tuition exemption at or above $150,000; '
                          'threshold; the full net price calculator accounts for '
                          'assets and family circumstances')
                room = ('Room and board responsibility applies; the full net '
                        'price calculator accounts for assets and family circumstances')
            estimate = {
                'income': income,
                'family': family,
                'tuition': tuition,
                'room': room,
                'note': ('Estimates follow Stanford’s published need-based aid '
                         'thresholds: families earning less than $150,000 with '
                         'assets typical of that income level pay no tuition; '
                         'families earning less than $100,000 pay no tuition or '
                         'room and board. The average need-based scholarship in '
                         'the current freshman class is more than $70,000.'),
            }
    return render_template('aid.html', data=data, estimate=estimate)


# ── auth + user state ────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not _validate_csrf_token():
            abort(400)
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Signed in.', 'success')
            return redirect(request.args.get('next') or url_for('home'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
def logout():
    if not _validate_csrf_token():
        abort(400)
    logout_user()
    flash('Signed out.', 'success')
    return redirect(url_for('home'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        if not _validate_csrf_token():
            abort(400)
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        errors = []
        if len(name) < 2:
            errors.append('Please enter your full name.')
        if '@' not in email or '.' not in email.split('@')[-1] or len(email) < 5:
            errors.append('Please enter a valid email address.')
        if User.query.filter_by(email=email).first():
            errors.append('An account with that email already exists.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('signup.html', name=name, email=email)
        user = User(name=name, email=email,
                    password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
                    created_at=MIRROR_DATE)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Welcome to Stanford. Your account is ready.', 'success')
        return redirect(url_for('planner'))
    return render_template('signup.html', name='', email='')


@app.route('/planner')
@login_required
def planner():
    rows = (PlannedCourse.query.filter_by(user_id=current_user.id)
            .order_by(PlannedCourse.position).all())
    items = []
    total_min = 0.0
    total_max = 0.0
    for row in rows:
        course = Course.query.filter_by(code=row.course_code).first()
        if course:
            items.append((row, course))
            total_min += course.units_min or 0
            total_max += course.units_max or course.units_min or 0
    return render_template('planner.html', items=items,
                           total_min=total_min, total_max=total_max)


@app.route('/planner/add', methods=['POST'])
@login_required
def planner_add():
    if not _validate_csrf_token():
        abort(400)
    code = request.form.get('code') or ''
    course = Course.query.filter_by(code=code).first()
    if not course:
        abort(404)
    exists = PlannedCourse.query.filter_by(user_id=current_user.id,
                                           course_code=code).first()
    if not exists:
        pos = (PlannedCourse.query.filter_by(user_id=current_user.id)
               .with_entities(db.func.max(PlannedCourse.position)).scalar() or 0) + 1
        db.session.add(PlannedCourse(user_id=current_user.id, course_code=code,
                                     position=pos, added_at=MIRROR_DATE))
        db.session.commit()
        flash(f'Added {code} to your course planner.', 'success')
    else:
        flash(f'{code} is already in your planner.', 'info')
    return redirect(request.form.get('next') or url_for('planner'))


@app.route('/planner/remove', methods=['POST'])
@login_required
def planner_remove():
    if not _validate_csrf_token():
        abort(400)
    code = request.form.get('code') or ''
    row = PlannedCourse.query.filter_by(user_id=current_user.id,
                                        course_code=code).first()
    if row:
        db.session.delete(row)
        db.session.commit()
        flash(f'Removed {code} from your course planner.', 'success')
    else:
        flash(f'{code} is not in your planner.', 'info')
    return redirect(request.form.get('next') or url_for('planner'))


@app.route('/saved-events')
@login_required
def saved_events():
    rows = (SavedEvent.query.filter_by(user_id=current_user.id)
            .order_by(SavedEvent.position).all())
    items = []
    for row in rows:
        event = CampusEvent.query.filter_by(eid=row.event_eid).first()
        if event:
            items.append((row, event))
    return render_template('saved_events.html', items=items)


@app.route('/events/save', methods=['POST'])
@login_required
def event_save():
    if not _validate_csrf_token():
        abort(400)
    eid = _parse_int(request.form.get('eid'), 0)
    event = CampusEvent.query.filter_by(eid=eid).first()
    if not event:
        abort(404)
    exists = SavedEvent.query.filter_by(user_id=current_user.id,
                                        event_eid=eid).first()
    if not exists:
        pos = (SavedEvent.query.filter_by(user_id=current_user.id)
               .with_entities(db.func.max(SavedEvent.position)).scalar() or 0) + 1
        db.session.add(SavedEvent(user_id=current_user.id, event_eid=eid,
                                  position=pos, added_at=MIRROR_DATE))
        db.session.commit()
        flash(f'Saved "{event.title}" to your events.', 'success')
    else:
        flash('That event is already saved.', 'info')
    return redirect(request.form.get('next') or url_for('saved_events'))


@app.route('/events/unsave', methods=['POST'])
@login_required
def event_unsave():
    if not _validate_csrf_token():
        abort(400)
    eid = _parse_int(request.form.get('eid'), 0)
    row = SavedEvent.query.filter_by(user_id=current_user.id, event_eid=eid).first()
    if row:
        db.session.delete(row)
        db.session.commit()
        flash('Removed the event from your saved list.', 'success')
    else:
        flash('That event is not saved.', 'info')
    return redirect(request.form.get('next') or url_for('saved_events'))


@app.route('/_health')
def health():
    try:
        counts = {
            'departments': Department.query.count(),
            'courses': Course.query.count(),
            'programs': Program.query.count(),
            'faculty': Faculty.query.count(),
            'news': NewsArticle.query.count(),
            'events': CampusEvent.query.count(),
            'calendar': CalendarEntry.query.count(),
            'libraries': Library.query.count(),
            'users': User.query.count(),
        }
        return {'ok': all(v > 0 for v in counts.values()),
                'site': SITE_NAME, 'counts': counts}
    except Exception as exc:  # pragma: no cover
        return {'ok': False, 'site': SITE_NAME, 'error': str(exc)}


@app.errorhandler(404)
def not_found(_error):
    return render_template('404.html'), 404


# ── seeding ──────────────────────────────────────────────────────────────────

def seed_database():
    """Idempotent seed from the tracked snapshots (build-time entry point)."""
    if Department.query.count() > 0:
        return
    import seed_lib

    records = seed_lib.build_records()
    for d in records['departments']:
        db.session.add(Department(code=d['code'], name=d['name'],
                                  school=d['school'],
                                  description=d['description'],
                                  subject_codes=json.dumps(d['subject_codes'])))
    for c in records['courses']:
        db.session.add(Course(code=c['code'], subject=c['subject'],
                              number=c['number'], title=c['title'],
                              description=c['description'],
                              units_min=c['units_min'], units_max=c['units_max'],
                              career=c['career'], college=c['college'],
                              grade_mode=c['grade_mode'],
                              terms_json=json.dumps(c['terms']),
                              ways_json=json.dumps(c['ways']),
                              components_json=json.dumps(c['components']),
                              requisites_json=json.dumps(c['requisites']),
                              departments_json=json.dumps(c['departments'])))
    for p in records['programs']:
        db.session.add(Program(code=p['code'], name=p['name'], type=p['type'],
                                level=p['level'], college=p['college'],
                                description=p['description'],
                                degree_designation=p['degree_designation'],
                                units_min=p['units_min'], webpage=p['webpage'],
                                requirements_json=json.dumps(p['requirements']),
                                departments_json=json.dumps(p['departments'])))
    for f in records['faculty']:
        db.session.add(Faculty(profile_id=f['profile_id'], name=f['name'],
                                first_name=f['first_name'], last_name=f['last_name'],
                                department=f['department'],
                                short_title=f['short_title'],
                                titles_json=json.dumps(f['titles']),
                                bio=f['bio'],
                                research_interests=f['research_interests'],
                                education_json=json.dumps(f['education']),
                                publications_json=json.dumps(f['publications']),
                                publication_count=f['publication_count'],
                                email=f['email'], photo=f['photo']))
    for n in records['news']:
        db.session.add(NewsArticle(slug=n['slug'], title=n['title'],
                                    published_ts=n['published_ts'],
                                    category=n['category'],
                                    main_topic=n['main_topic'],
                                    topics_json=json.dumps(n['topics']),
                                    featured_unit=n['featured_unit'],
                                    writers_json=json.dumps(n['writers']),
                                    description=n['description'],
                                    body_json=json.dumps(n['body']),
                                    image=n['image']))
    for e in records['events']:
        db.session.add(CampusEvent(eid=e['eid'], title=e['title'],
                                   description=e['description'],
                                   first_date=e['first_date'],
                                   last_date=e['last_date'],
                                   location_name=e['location_name'],
                                   room_number=e['room_number'],
                                   address=e['address'],
                                   experience=e['experience'],
                                   free=e['free'], ticket_url=e['ticket_url'],
                                   ticket_cost=e['ticket_cost'],
                                   tags_json=json.dumps(e['tags']),
                                   keywords_json=json.dumps(e['keywords']),
                                   recurring=e['recurring'],
                                   featured=e['featured'],
                                   verified=e['verified'],
                                   photo=e['photo'],
                                   instances_json=json.dumps(e['instances'])))
    for c in records['calendar']:
        db.session.add(CalendarEntry(quarter=c['quarter'],
                                      quarter_key=c['quarter_key'],
                                      position=c['position'],
                                      when_text=c['when'], what=c['what']))
    for l in records['libraries']:
        db.session.add(Library(slug=l['slug'], name=l['name'],
                                location=l['location'], phone=l['phone'],
                                email=l['email'], about=l['about'],
                                quick_links_json=json.dumps(l['quick_links']),
                                research_subjects_json=json.dumps(l['research_subjects']),
                                hours_days_json=json.dumps(l['hours_days']),
                                hours_rows_json=json.dumps(l['hours_rows']),
                                photo=l['photo']))
    db.session.add(AdmissionInfo(
        key='admission',
        value_json=json.dumps(records['admission'])))
    db.session.commit()


def seed_benchmark_users():
    """Idempotent benchmark accounts (Alice/Bob/Carol/Dana)."""
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    import seed_lib

    by_email = {}
    for u in seed_lib.BENCHMARK_USERS:
        user = User(name=u['name'], email=u['email'],
                    password_hash=seed_lib.BENCHMARK_PASSWORD_HASH,
                    created_at=seed_lib.MIRROR_DATE)
        db.session.add(user)
        by_email[u['email']] = user
    db.session.commit()

    records = seed_lib.build_records()
    for email, course in seed_lib.planner_targets(records):
        user = by_email[email]
        pos = (PlannedCourse.query.filter_by(user_id=user.id)
               .with_entities(db.func.max(PlannedCourse.position)).scalar() or 0) + 1
        db.session.add(PlannedCourse(user_id=user.id,
                                     course_code=course['code'],
                                     position=pos, added_at=seed_lib.MIRROR_DATE))
    for email, event in seed_lib.saved_event_targets(records):
        user = by_email[email]
        pos = (SavedEvent.query.filter_by(user_id=user.id)
               .with_entities(db.func.max(SavedEvent.position)).scalar() or 0) + 1
        db.session.add(SavedEvent(user_id=user.id, event_eid=event['eid'],
                                   position=pos, added_at=seed_lib.MIRROR_DATE))
    db.session.commit()


def create_all_and_seed():
    with app.app_context():
        create_schema()
        seed_database()
        seed_benchmark_users()


if os.environ.get('STANFORD_UNIVERSITY_AUTO_SEED'):
    create_all_and_seed()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
