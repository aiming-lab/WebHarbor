#!/usr/bin/env python3
"""Coursera.org mirror — Flask application."""
import os, json, re, random, hashlib
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort, g)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_bcrypt import Bcrypt
from wtforms import StringField, PasswordField, TextAreaField, SelectField, FloatField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'coursera-mirror-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'coursera.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to continue.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _slugify_instructor(name):
    """Convert 'Gautam Kaul' -> 'gautam-kaul' (deterministic, URL-safe)."""
    if not name:
        return ''
    s = re.sub(r'[^a-zA-Z0-9\s]', '', name)
    s = re.sub(r'\s+', '-', s.strip().lower())
    return s

# ─── Models ───────────────────────────────────────────────────────────────────

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    enrollments = db.relationship('Enrollment', backref='user', lazy=True, cascade='all, delete-orphan')
    saved_courses = db.relationship('SavedCourse', backref='user', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Partner(db.Model):
    __tablename__ = 'partners'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    country = db.Column(db.String(80), default='United States')
    partner_type = db.Column(db.String(30), default='university')  # university|company|institution
    short_name = db.Column(db.String(80), default='')
    website = db.Column(db.String(200), default='')

    courses = db.relationship('Course', backref='partner', lazy=True)


class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(300), unique=True, nullable=False, index=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('partners.id'), nullable=True)
    course_type = db.Column(db.String(40), default='Course')
    # Course|Specialization|Guided Project|Professional Certificate|Degree
    level = db.Column(db.String(30), default='Beginner')
    # Beginner|Intermediate|Advanced|Mixed
    category = db.Column(db.String(100), default='')
    subcategory = db.Column(db.String(100), default='')
    duration_text = db.Column(db.String(80), default='Approx. 10 hours')
    duration_weeks = db.Column(db.Float, default=4.0)   # for filtering
    duration_hours = db.Column(db.Float, default=10.0)  # for < N hours filter
    rating = db.Column(db.Float, default=4.6)
    review_count = db.Column(db.Integer, default=1000)
    enrolled_count = db.Column(db.Integer, default=50000)
    is_free = db.Column(db.Boolean, default=False)
    has_certificate = db.Column(db.Boolean, default=True)
    credit_eligible = db.Column(db.Boolean, default=False)
    instructor = db.Column(db.String(200), default='')
    instructor_title = db.Column(db.String(200), default='')
    description = db.Column(db.Text, default='')
    what_you_learn = db.Column(db.Text, default='[]')   # JSON list
    skills = db.Column(db.Text, default='[]')            # JSON list
    feature_tags = db.Column(db.Text, default='[]')      # JSON list
    is_featured = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=False)
    sort_date = db.Column(db.String(20), default='2024-01-01')
    # For degrees
    degree_type = db.Column(db.String(40), default='')  # Bachelor|Master|MasterAdvancedStudy
    application_deadline = db.Column(db.String(40), default='')  # e.g. 'March 15, 2026' (degrees only)
    # Course color (for CSS thumbnails)
    color_class = db.Column(db.String(20), default='cat-cs')
    # Learner testimonials shown prominently on course page
    # JSON list of {quote, name, role, date}
    testimonials_json = db.Column(db.Text, default='[]')

    enrollments = db.relationship('Enrollment', backref='course', lazy=True, cascade='all, delete-orphan')
    saved_by = db.relationship('SavedCourse', backref='course', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='course', lazy=True, cascade='all, delete-orphan')
    modules = db.relationship('CourseModule', backref='course', lazy=True, order_by='CourseModule.week_number', cascade='all, delete-orphan')
    sub_courses = db.relationship('SubCourse', foreign_keys='SubCourse.specialization_id',
                                   backref='specialization', lazy=True, order_by='SubCourse.order_index',
                                   cascade='all, delete-orphan')

    def get_skills(self):
        try:
            return json.loads(self.skills or '[]')
        except Exception:
            return []

    def get_what_you_learn(self):
        try:
            return json.loads(self.what_you_learn or '[]')
        except Exception:
            return []

    def get_feature_tags(self):
        try:
            return json.loads(self.feature_tags or '[]')
        except Exception:
            return []

    def get_testimonials(self):
        try:
            v = json.loads(self.testimonials_json or '[]')
            if isinstance(v, list):
                return v
        except Exception:
            pass
        return []

    def instructor_slug(self):
        return _slugify_instructor(self.instructor or '')

    def enrolled_display(self):
        n = self.enrolled_count or 0
        if n >= 1_000_000:
            return f'{n/1_000_000:.1f}M'
        if n >= 1_000:
            return f'{int(n/1000)}K'
        return str(n)


class CourseModule(db.Model):
    __tablename__ = 'course_modules'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    week_number = db.Column(db.Integer, default=1)
    title = db.Column(db.String(300), default='')
    description = db.Column(db.Text, default='')
    videos_count = db.Column(db.Integer, default=4)
    readings_count = db.Column(db.Integer, default=3)
    quizzes_count = db.Column(db.Integer, default=1)
    video_titles = db.Column(db.Text, default='[]')  # JSON list of individual video titles

    def get_video_titles(self):
        try:
            titles = json.loads(self.video_titles or '[]')
            if isinstance(titles, list):
                return titles
        except Exception:
            pass
        return []


class SubCourse(db.Model):
    __tablename__ = 'sub_courses'
    id = db.Column(db.Integer, primary_key=True)
    specialization_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    order_index = db.Column(db.Integer, default=0)
    title = db.Column(db.String(300), default='')
    description = db.Column(db.Text, default='')
    duration_text = db.Column(db.String(80), default='Approx. 8 hours')


class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    progress = db.Column(db.Integer, default=0)


class SavedCourse(db.Model):
    __tablename__ = 'saved_courses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    rating = db.Column(db.Float, default=5.0)
    body = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── Forms ────────────────────────────────────────────────────────────────────

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])

class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(2, 100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(8, 100)])
    confirm = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])

class ProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(2, 100)])
    email = StringField('Email', validators=[DataRequired(), Email()])

class PasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(8, 100)])
    confirm = PasswordField('Confirm', validators=[DataRequired(), EqualTo('new_password')])

class ReviewForm(FlaskForm):
    rating = FloatField('Rating', validators=[DataRequired(), NumberRange(1, 5)])
    body = TextAreaField('Review', validators=[DataRequired(), Length(10, 2000)])

# ─── Search helpers ───────────────────────────────────────────────────────────

STOPWORDS = {
    # Articles / prepositions / conjunctions / aux verbs
    'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for',
    'with', 'and', 'or', 'is', 'are', 'be', 'by', 'from', 'that',
    'this', 'it', 'as', 'we', 'our', 'about', 'how', 'what', 'which',
    'who', 'when', 'where', 'why',
    # Generic "course-ware" words
    'course', 'courses', 'learn', 'learning', 'class', 'classes',
    'online', 'free', 'paid', 'study', 'studies',
    # Filter-dimension words — these belong in URL filters, not in
    # full-text search, otherwise typing "Beginner Spanish Specialization"
    # matches every Beginner Specialization in any subject.
    'beginner', 'intermediate', 'advanced', 'mixed',
    'specialization', 'specializations',
    'certificate', 'certificates', 'professional',
    'guided', 'project', 'projects',
    'degree', 'degrees', 'bachelor', 'master',
    # English / language adjectives that don't disambiguate content
    'level', 'levels', 'rating', 'ratings',
}

# IDF (inverse document frequency) cache, populated lazily on first
# search. Rebuilt automatically when the catalog grows past 110 % of
# the size at last build, so seed expansion stays consistent.
_IDF_CACHE = {'token_df': {}, 'total': 0, 'built_at': 0}

def _build_idf():
    import math
    courses = Course.query.all()
    df = {}
    for c in courses:
        # Mirror the haystack fields used by _score_course
        text = ' '.join([
            (c.title or ''), (c.description or ''),
            (c.skills or ''), (c.feature_tags or ''),
            (c.instructor or ''), (c.partner.name if c.partner else ''),
        ]).lower()
        for w in set(re.findall(r'[a-z0-9\+\#]+', text)):
            df[w] = df.get(w, 0) + 1
    _IDF_CACHE['token_df'] = df
    _IDF_CACHE['total'] = len(courses)
    _IDF_CACHE['built_at'] = len(courses)

def _idf(token):
    import math
    if _IDF_CACHE['total'] == 0:
        return 1.0
    df = _IDF_CACHE['token_df'].get(token, 0)
    # Standard IDF + 1 smoothing; higher = rarer = more discriminative
    return math.log((_IDF_CACHE['total'] + 1) / (df + 1)) + 1.0

_WORD_RE = re.compile(r'[a-z0-9\+\#]+')

def _is_known_word(token):
    """A token is a 'known word' if it appears as a complete word in
    the IDF corpus (any course's title/body). Real complete words like
    'java', 'python', 'spanish' are known. Partial / typo tokens like
    'healthca' or 'phys' are NOT known."""
    return _IDF_CACHE['token_df'].get(token, 0) > 0

def _word_match(token, words):
    """Match strength for `token` against a set of words:
       1.0  exact word-boundary hit                 ('java'  in {java,…})
       0.6  prefix hit, token is NOT a known word   ('healthca' → healthcare)
       0.0  no match.
    Prefix matching only fires when the user typed an incomplete word
    that doesn't itself exist in the corpus — so 'java' never silently
    matches 'javascript' (java IS a known word; user meant java, not
    something it's a prefix of)."""
    if token in words:
        return 1.0
    if len(token) >= 3 and not _is_known_word(token):
        for w in words:
            if w.startswith(token) and len(w) > len(token):
                return 0.6
    return 0.0

def _score_course(c, tokens):
    """IDF-weighted match score with WORD-BOUNDARY + PREFIX matching.
    Title hits weigh 3×, body hits 1×. Rare tokens dominate."""
    title_words = set(_WORD_RE.findall((c.title or '').lower()))
    body_words  = set(_WORD_RE.findall(' '.join([
        (c.description or '').lower(),
        (c.skills or '').lower(),
        (c.feature_tags or '').lower(),
        (c.instructor or '').lower(),
        (c.partner.name if c.partner else '').lower(),
    ])))
    # NOTE: category / subcategory / course_type / level are filter
    # dimensions, NOT search content.
    score = 0.0
    for t in tokens:
        idf = _idf(t)
        m_title = _word_match(t, title_words)
        m_body  = _word_match(t, body_words) if not m_title else 0.0
        if m_title:
            score += idf * 3.0 * m_title
        elif m_body:
            score += idf * m_body
    return score

def search_courses(q='', level=None, course_type=None, duration=None,
                   min_rating=None, free=None, credit=None, certificate=None,
                   category=None, sort='popular'):
    query = Course.query
    text_relevance = {}   # course.id → text_score, drives sort tie-break

    # Text scoring
    if q and q.strip():
        raw_tokens = re.findall(r'[a-z0-9\+\#]+', q.lower())
        tokens = [t for t in raw_tokens if t not in STOPWORDS and len(t) >= 2]
        if not tokens:
            # Query was 100 % stop-words / filter words. Treat as
            # "no text query" — let URL filters do the work.
            courses = query.all()
        else:
            # (Re)build IDF if catalog grew significantly
            if (_IDF_CACHE['total'] == 0 or
                Course.query.count() > _IDF_CACHE['built_at'] * 1.1):
                _build_idf()
            all_courses = query.all()
            # Pick the rarest GATE token from those that actually exist
            # in the corpus (df > 0) OR that have a prefix expansion
            # landing on a real word. Tokens that are pure typos /
            # filler ("subject", "today", "curriculum") have df=0 and
            # no useful prefix — they should NOT gate the search,
            # otherwise "Physical Science and Engineering subject"
            # returns 0 just because no course text contains "subject".
            def _has_any_corpus_hit(t):
                if _IDF_CACHE['token_df'].get(t, 0) > 0:
                    return True
                if len(t) >= 3 and not _is_known_word(t):
                    for w in _IDF_CACHE['token_df'].keys():
                        if w.startswith(t) and len(w) > len(t):
                            return True
                return False
            # Gate must have df ≥ 2: tokens that appear in only ONE
            # course are noise (e.g. "today" might appear once in a
            # Modern Art description) — using them as the gate would
            # return only that one course.
            gate_candidates = [t for t in tokens
                               if _IDF_CACHE['token_df'].get(t, 0) >= 2]
            if not gate_candidates:
                # No high-quality gate token. Fall back to any df>0 token
                # then to any prefix-matchable token, then drop the gate.
                gate_candidates = [t for t in tokens
                                   if _IDF_CACHE['token_df'].get(t, 0) > 0]
            if not gate_candidates:
                gate_candidates = [t for t in tokens if _has_any_corpus_hit(t)]
            # Drop OOV-no-hit tokens from scoring too (they contribute 0).
            tokens = [t for t in tokens if _has_any_corpus_hit(t)] or tokens
            # Hard requirement: the RAREST gate token must appear in
            # title or body. This is what stops "Beginner Spanish
            # Specialization" from matching every Beginner Specialization
            # — Spanish is the rare token, and a Python course doesn't
            # contain it.
            if not gate_candidates:
                # No discriminative token at all (entire query meaningless).
                return []
            rarest = max(gate_candidates, key=_idf)
            scored = []
            for c in all_courses:
                s = _score_course(c, tokens)
                if s <= 0:
                    continue
                title_w = set(_WORD_RE.findall((c.title or '').lower()))
                body_w  = set(_WORD_RE.findall(' '.join([
                    (c.description or '').lower(),
                    (c.skills or '').lower(),
                    (c.feature_tags or '').lower(),
                    (c.instructor or '').lower(),
                    (c.partner.name if c.partner else '').lower(),
                ])))
                # Rarest token must hit (exact or as a prefix of an
                # existing word). This is what stops `q=spanish` from
                # matching Beginner Python Specialization.
                if (_word_match(rarest, title_w) == 0.0 and
                    _word_match(rarest, body_w)  == 0.0):
                    continue
                scored.append((s, c))
                text_relevance[c.id] = s
            scored.sort(key=lambda x: -x[0])
            if not scored:
                return []
            courses = [c for _, c in scored]
    else:
        courses = query.all()

    # Filters
    if level:
        courses = [c for c in courses if c.level and c.level.lower() == level.lower()]
    if course_type:
        courses = [c for c in courses if c.course_type and
                   c.course_type.lower() == course_type.lower()]
    if duration:
        if duration == '1-4_weeks':
            courses = [c for c in courses if c.duration_weeks and c.duration_weeks <= 4]
        elif duration == '1-3_months':
            courses = [c for c in courses if c.duration_weeks and 4 < c.duration_weeks <= 13]
        elif duration == '3-6_months':
            courses = [c for c in courses if c.duration_weeks and 13 < c.duration_weeks <= 26]
        elif duration == '6plus_months':
            courses = [c for c in courses if c.duration_weeks and 26 < c.duration_weeks < 52]
        elif duration == '1-4_years' or duration == '1-4 Years':
            # Matches specializations / degrees running one year or more
            courses = [c for c in courses if c.duration_weeks and c.duration_weeks >= 52]
        elif duration == 'less_2_hours':
            courses = [c for c in courses if c.duration_hours and c.duration_hours < 2]
    if min_rating:
        try:
            mr = float(min_rating)
            courses = [c for c in courses if c.rating and c.rating >= mr]
        except (ValueError, TypeError):
            pass
    if free == '1' or free is True:
        courses = [c for c in courses if c.is_free]
    if credit == '1' or credit is True:
        courses = [c for c in courses if c.credit_eligible]
    if certificate == '1' or certificate is True:
        courses = [c for c in courses if c.has_certificate]
    if category:
        courses = [c for c in courses if category.lower() in (c.category or '').lower()]

    # Sort
    # Key insight: when there's a text query, relevance is the PRIMARY
    # sort key — the chosen `sort` becomes a tiebreaker among similarly-
    # relevant results. Otherwise typing "spanish" returns Python
    # courses just because they have higher enrolled_count.
    if text_relevance:
        if sort == 'newest':
            tie = lambda c: c.sort_date or '2000-01-01'
            courses.sort(key=lambda c: (-text_relevance.get(c.id, 0), tie(c)),
                         reverse=False)
            # `newest` wants tie DESC, but reverse flips both — handle separately
            courses.sort(key=lambda c: (text_relevance.get(c.id, 0),
                                        c.sort_date or '2000-01-01'),
                         reverse=True)
        elif sort == 'rating':
            courses.sort(key=lambda c: (text_relevance.get(c.id, 0),
                                        c.rating or 0),
                         reverse=True)
        else:   # 'popular' (default) or unknown
            courses.sort(key=lambda c: (text_relevance.get(c.id, 0),
                                        c.enrolled_count or 0),
                         reverse=True)
    else:
        if sort == 'newest':
            courses.sort(key=lambda c: c.sort_date or '2000-01-01', reverse=True)
        elif sort == 'rating':
            courses.sort(key=lambda c: c.rating or 0, reverse=True)
        elif sort == 'popular':
            courses.sort(key=lambda c: c.enrolled_count or 0, reverse=True)

    return courses

# ─── Login loader ─────────────────────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ─── Context processor ───────────────────────────────────────────────────────

# ─── Image asset helpers ──────────────────────────────────────────────────────

_IMG_MANIFEST_CACHE = None
_IMG_DIR = os.path.join(BASE_DIR, 'static', 'images')
_COURSE_TAGS_CACHE = None

# Maps the human-readable category name stored on Course.category to the
# slug used in static/images/_course_image_tags.json.
_CATEGORY_NAME_TO_SLUG = {
    'Computer Science': 'computer-science',
    'Data Science': 'data-science',
    'Information Technology': 'information-technology',
    'Business': 'business',
    'Language Learning': 'language-learning',
    'Math and Logic': 'math-logic',
    'Physical Science and Engineering': 'physical-science',
    'Social Sciences': 'social-sciences',
    'Arts and Humanities': 'arts-humanities',
    'Health': 'health',
    'Personal Development': 'personal-development',
}

def _img_manifest():
    """Lazy-load static/images/_manifest.json. Returns dict with keys
    `logo, hero_home, hero, partners, courses, categories, instructors,
     badges, social, plus_logo`. Empty dict if not present."""
    global _IMG_MANIFEST_CACHE
    if _IMG_MANIFEST_CACHE is None:
        path = os.path.join(_IMG_DIR, '_manifest.json')
        try:
            with open(path) as f:
                _IMG_MANIFEST_CACHE = json.load(f)
        except (OSError, ValueError):
            _IMG_MANIFEST_CACHE = {}
    return _IMG_MANIFEST_CACHE

def _course_image_tags():
    """Lazy-load static/images/_course_image_tags.json — the per-image topic
    tags used to pick a visually appropriate course thumbnail. Empty dict if
    not present."""
    global _COURSE_TAGS_CACHE
    if _COURSE_TAGS_CACHE is None:
        path = os.path.join(_IMG_DIR, '_course_image_tags.json')
        try:
            with open(path) as f:
                _COURSE_TAGS_CACHE = json.load(f)
        except (OSError, ValueError):
            _COURSE_TAGS_CACHE = {}
    return _COURSE_TAGS_CACHE

def _stable_pick(seed, items):
    """Deterministically pick one item from the pool by hashing `seed`."""
    if not items:
        return None
    h = int(hashlib.md5(str(seed).encode('utf-8')).hexdigest()[:8], 16)
    return items[h % len(items)]

def _slugify_partner(name):
    s = (name or '').lower()
    # Normalise common partner-name patterns to match scraper slugs
    s = s.replace('university of ', '').replace('the ', '')
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    aliases = {
        'university-michigan':'michigan', 'michigan-ann-arbor':'michigan',
        'colorado-system':'colorado-boulder', 'colorado':'colorado-boulder',
        'pennsylvania-state-university':'pennsylvania', 'pennsylvania':'pennsylvania',
        'penn':'pennsylvania', 'upenn':'pennsylvania',
        'illinois-urbana-champaign':'illinois', 'illinois':'illinois',
        'imperial-college':'imperial-college-london',
        'johns-hopkins-university':'johns-hopkins',
        'deeplearning':'deeplearning-ai',
        'amazon-web-services':'aws', 'amazon':'aws',
        'meta-platforms':'meta', 'facebook':'meta',
        'l-or-al':'loreal', 'l-oreal':'loreal',
        'tata-consultancy-services':'tata',
        'pricewaterhousecoopers':'pwc',
    }
    return aliases.get(s, s)

def _course_image_pool(category_name, partner_slug=None):
    """Build the list of course images appropriate for a course in the given
    category and from the given partner. Two filters are applied:

    1. Partner filter — an image carrying a `partner_lock` is only eligible
       when its lock equals `partner_slug`. This stops, e.g., the IBM badge
       from being shown on a Google course. Images locked to a brand that
       isn't a partner in our DB (Pittsburgh, Deloitte, INFOSEC, Packt, …)
       are effectively excluded from every course.
    2. Category filter — within partner-eligible images, prefer those whose
       tags include the course's category slug; only fall back to
       topic-neutral (`tags == ['generic']`) images when no category-specific
       image qualifies."""
    tags_map = _course_image_tags()
    full_pool = _img_manifest().get('courses') or []
    if not tags_map:
        return full_pool
    def _entry(rel):
        return tags_map.get(rel) or {}
    partner_ok = [rel for rel in full_pool
                  if _entry(rel).get('partner_lock') in (None, partner_slug)]
    if not partner_ok:
        partner_ok = full_pool
    cat_slug = _CATEGORY_NAME_TO_SLUG.get(category_name or '')
    specific = []
    if cat_slug:
        specific = [rel for rel in partner_ok
                    if cat_slug in (_entry(rel).get('tags') or [])]
    if specific:
        return specific
    pure_generic = [rel for rel in partner_ok
                    if _entry(rel).get('tags') == ['generic']]
    return pure_generic or partner_ok

def course_thumb(c):
    """Return a static-relative path like 'images/courses/0042.jpg' for a course.

    Resolution order (most preferred first):
      1. `images/courses/real/<slug>.jpg` — a real Coursera thumbnail scraped
         by fetch_real_thumbs.py. The actual photographic course card.
      2. The curated stock pool (filtered by partner_lock + category) — picks
         a topically appropriate image that doesn't carry a conflicting brand.
      3. `images/courses/gen/<slug>.png` — a generated text card, used only
         when neither a real image nor any topically-acceptable stock image
         is available."""
    slug = getattr(c, 'slug', None)
    if slug:
        real_rel = f'courses/real/{slug}.jpg'
        if os.path.exists(os.path.join(_IMG_DIR, real_rel)):
            return 'images/' + real_rel
    partner = getattr(c, 'partner', None)
    partner_slug = getattr(partner, 'slug', None) if partner else None
    pool = _course_image_pool(getattr(c, 'category', None), partner_slug)
    pick = _stable_pick(slug or getattr(c, 'id', 0), pool)
    if pick:
        return 'images/' + pick
    if slug:
        gen_rel = f'courses/gen/{slug}.png'
        if os.path.exists(os.path.join(_IMG_DIR, gen_rel)):
            return 'images/' + gen_rel
    return None

def partner_logo(p):
    """Return a static-relative path for a partner's logo, or None.
    Accepts a Partner object, dict {'slug','name'}, or string name."""
    if not p:
        return None
    if isinstance(p, dict):
        slug = p.get('slug') or _slugify_partner(p.get('name', ''))
        name = p.get('name', '')
    elif isinstance(p, str):
        name = p
        slug = _slugify_partner(p)
    else:
        name = getattr(p, 'name', '') or ''
        slug = getattr(p, 'slug', None) or _slugify_partner(name)
    partners = _img_manifest().get('partners') or {}
    rel = partners.get(slug) or partners.get(_slugify_partner(name))
    return ('images/' + rel) if rel else None

def instructor_photo(name_or_slug):
    if not name_or_slug:
        return None
    slug = _slugify_instructor(name_or_slug) if ' ' in str(name_or_slug) else name_or_slug
    pool = _img_manifest().get('instructors') or {}
    rel = pool.get(slug)
    if not rel:
        # deterministic fallback: pick from available pool
        rel = _stable_pick(slug, list(pool.values()))
    return ('images/' + rel) if rel else None

def category_image(slug):
    rel = (_img_manifest().get('categories') or {}).get(slug)
    return ('images/' + rel) if rel else None

def hero_image(key):
    rel = (_img_manifest().get('hero') or {}).get(key)
    return ('images/' + rel) if rel else None

def static_image(rel_path):
    """Helper to build a full static url from a manifest-relative path."""
    if not rel_path:
        return None
    return rel_path if rel_path.startswith('images/') else 'images/' + rel_path


@app.context_processor
def inject_globals():
    saved_ids = set()
    enrolled_ids = set()
    if current_user.is_authenticated:
        saved_ids = {s.course_id for s in current_user.saved_courses}
        enrolled_ids = {e.course_id for e in current_user.enrollments}
    categories = [
        ('computer-science', 'Computer Science'),
        ('data-science', 'Data Science'),
        ('business', 'Business'),
        ('information-technology', 'Information Technology'),
        ('language-learning', 'Language Learning'),
        ('math-logic', 'Math and Logic'),
        ('physical-science', 'Physical Science and Engineering'),
        ('social-sciences', 'Social Sciences'),
        ('arts-humanities', 'Arts and Humanities'),
        ('health', 'Health'),
        ('personal-development', 'Personal Development'),
    ]
    m = _img_manifest()
    return dict(saved_ids=saved_ids, enrolled_ids=enrolled_ids,
                nav_categories=categories,
                course_thumb=course_thumb,
                partner_logo=partner_logo,
                instructor_photo=instructor_photo,
                category_image=category_image,
                hero_image=hero_image,
                site_logo=('images/' + m['logo']) if m.get('logo') else None,
                hero_home=('images/' + m['hero_home']) if m.get('hero_home') else None,
                plus_logo=('images/' + m['plus_logo']) if m.get('plus_logo') else None,
                app_store_badge=('images/' + (m.get('badges') or {}).get('app_store','')) if (m.get('badges') or {}).get('app_store') else None,
                play_store_badge=('images/' + (m.get('badges') or {}).get('google_play','')) if (m.get('badges') or {}).get('google_play') else None,
                social_icons={k:'images/'+v for k,v in (m.get('social') or {}).items()},
                )

# ─── Routes: Static pages ─────────────────────────────────────────────────────

@app.route('/')
def index():
    featured = Course.query.filter_by(is_featured=True).limit(12).all()
    free_courses = Course.query.filter_by(is_free=True).limit(6).all()
    new_courses = Course.query.filter_by(is_new=True).order_by(
        Course.sort_date.desc()).limit(8).all()
    return render_template('index.html', featured=featured,
                           free_courses=free_courses, new_courses=new_courses)

@app.route('/coursera-plus')
def coursera_plus():
    return render_template('coursera_plus.html')

@app.route('/business')
def business():
    return render_template('business.html')

@app.route('/for-teams')
@app.route('/teams')
def for_teams():
    return render_template('for_teams.html')


@app.route('/instructor/<slug>')
def instructor_profile(slug):
    """Instructor profile page: shows all courses taught by an instructor."""
    # Find all courses whose instructor slug matches
    all_courses = Course.query.filter(Course.instructor != '').all()
    matches = [c for c in all_courses if _slugify_instructor(c.instructor) == slug]
    if not matches:
        abort(404)
    # Use the first course's instructor details as the canonical name/title
    name = matches[0].instructor
    title = matches[0].instructor_title or ''
    # Try to extract affiliation from title (e.g. "Professor of Finance, University of Michigan")
    affiliation = ''
    if ',' in title:
        affiliation = title.split(',', 1)[1].strip()
    # Sort courses by enrolled count desc
    matches.sort(key=lambda c: -(c.enrolled_count or 0))
    return render_template('instructor.html', name=name, title=title,
                           affiliation=affiliation, courses=matches,
                           slug=slug)

@app.route('/partners')
def partners():
    country = request.args.get('country', '')
    ptype = request.args.get('type', '')
    q = Partner.query
    if country:
        q = q.filter(Partner.country.ilike(f'%{country}%'))
    if ptype:
        q = q.filter_by(partner_type=ptype)
    all_partners = q.order_by(Partner.name).all()
    countries = db.session.query(Partner.country).distinct().order_by(Partner.country).all()
    countries = [c[0] for c in countries if c[0]]
    return render_template('partners.html', partners=all_partners,
                           countries=countries, country=country, ptype=ptype)

@app.route('/degrees')
def degrees():
    dtype = request.args.get('type', '')
    q = Course.query.filter_by(course_type='Degree')
    if dtype:
        q = q.filter(Course.degree_type.ilike(f'%{dtype}%'))
    all_degrees = q.order_by(Course.title).all()
    return render_template('degrees.html', degrees=all_degrees, dtype=dtype)

@app.route('/professional-certificates')
def professional_certificates():
    certs = Course.query.filter_by(course_type='Professional Certificate').all()
    return render_template('professional_certificates.html', courses=certs)

@app.route('/browse/<category_slug>')
def browse(category_slug):
    cat_map = {
        'computer-science': 'Computer Science',
        'data-science': 'Data Science',
        'business': 'Business',
        'information-technology': 'Information Technology',
        'language-learning': 'Language Learning',
        'math-logic': 'Math and Logic',
        'physical-science': 'Physical Science and Engineering',
        'social-sciences': 'Social Sciences',
        'arts-humanities': 'Arts and Humanities',
        'health': 'Health',
        'personal-development': 'Personal Development',
    }
    cat_name = cat_map.get(category_slug, category_slug.replace('-', ' ').title())
    courses = Course.query.filter(
        Course.category.ilike(f'%{cat_name}%')
    ).order_by(Course.enrolled_count.desc()).all()
    return render_template('browse.html', courses=courses, category_name=cat_name,
                           category_slug=category_slug)

# ─── Routes: Search ───────────────────────────────────────────────────────────

@app.route('/search')
def search():
    q = (request.args.get('q') or request.args.get('query') or '').strip()
    level = request.args.get('level', '')
    course_type = request.args.get('type', '')
    duration = request.args.get('duration', '')
    min_rating = request.args.get('min_rating', '')
    free = request.args.get('free', '')
    credit = request.args.get('credit', '')
    certificate = request.args.get('certificate', '')
    category = request.args.get('category', '')
    sort = request.args.get('sort', 'popular')

    results = search_courses(q=q, level=level, course_type=course_type,
                             duration=duration, min_rating=min_rating,
                             free=free, credit=credit, certificate=certificate,
                             category=category, sort=sort)
    return render_template('search.html', results=results, q=q, level=level,
                           course_type=course_type, duration=duration,
                           min_rating=min_rating, free=free, credit=credit,
                           certificate=certificate, category=category, sort=sort,
                           total=len(results))

# ─── Routes: Course detail ────────────────────────────────────────────────────

@app.route('/learn/<slug>')
def course_detail(slug):
    course = Course.query.filter_by(slug=slug).first_or_404()
    reviews = Review.query.filter_by(course_id=course.id).order_by(
        Review.created_at.desc()).limit(10).all()
    sub_courses = SubCourse.query.filter_by(
        specialization_id=course.id).order_by(SubCourse.order_index).all()
    related = Course.query.filter(
        Course.category == course.category,
        Course.id != course.id
    ).limit(4).all()
    is_enrolled = False
    is_saved = False
    if current_user.is_authenticated:
        is_enrolled = Enrollment.query.filter_by(
            user_id=current_user.id, course_id=course.id).first() is not None
        is_saved = SavedCourse.query.filter_by(
            user_id=current_user.id, course_id=course.id).first() is not None
    review_form = ReviewForm()
    # Generate review rating breakdown based on average rating
    avg = course.rating or 4.5
    if avg >= 4.7:
        breakdown = {'5': 65, '4': 22, '3': 8, '2': 3, '1': 2}
    elif avg >= 4.4:
        breakdown = {'5': 55, '4': 28, '3': 10, '2': 4, '1': 3}
    elif avg >= 4.0:
        breakdown = {'5': 45, '4': 30, '3': 15, '2': 6, '1': 4}
    else:
        breakdown = {'5': 30, '4': 30, '3': 20, '2': 12, '1': 8}
    return render_template('course_detail.html', course=course, reviews=reviews,
                           sub_courses=sub_courses, related=related,
                           is_enrolled=is_enrolled, is_saved=is_saved,
                           review_form=review_form, rating_breakdown=breakdown)

# ─── Routes: Auth ─────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html', form=form)
        user = User(name=form.name.data.strip(), email=email)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# ─── Routes: Account ─────────────────────────────────────────────────────────

@app.route('/account')
@login_required
def account():
    enrollments = Enrollment.query.filter_by(
        user_id=current_user.id).order_by(Enrollment.enrolled_at.desc()).all()
    return render_template('account.html', enrollments=enrollments)

@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != current_user.id:
            flash('Email already in use.', 'danger')
        else:
            current_user.name = form.name.data.strip()
            current_user.email = email
            db.session.commit()
            flash('Profile updated.', 'success')
            return redirect(url_for('account'))
    return render_template('account_edit.html', form=form)

@app.route('/account/password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = PasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Password updated.', 'success')
            return redirect(url_for('account'))
    return render_template('change_password.html', form=form)

@app.route('/account/delete', methods=['POST'])
@login_required
def account_delete():
    user = db.session.get(User, current_user.id)
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash('Account deleted.', 'info')
    return redirect(url_for('index'))

@app.route('/wishlist')
@login_required
def wishlist():
    saved = SavedCourse.query.filter_by(
        user_id=current_user.id).order_by(SavedCourse.saved_at.desc()).all()
    return render_template('wishlist.html', saved=saved)

# ─── Routes: Reviews ──────────────────────────────────────────────────────────

@app.route('/learn/<slug>/review', methods=['POST'])
@login_required
def submit_review(slug):
    course = Course.query.filter_by(slug=slug).first_or_404()
    form = ReviewForm()
    if form.validate_on_submit():
        existing = Review.query.filter_by(
            user_id=current_user.id, course_id=course.id).first()
        if existing:
            existing.rating = form.rating.data
            existing.body = form.body.data
        else:
            r = Review(user_id=current_user.id, course_id=course.id,
                       rating=form.rating.data, body=form.body.data)
            db.session.add(r)
        db.session.commit()
        flash('Review submitted.', 'success')
    return redirect(url_for('course_detail', slug=slug))

@app.route('/review/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    r = db.session.get(Review, review_id)
    if r and r.user_id == current_user.id:
        db.session.delete(r)
        db.session.commit()
        flash('Review deleted.', 'info')
    return redirect(request.referrer or url_for('account'))

# ─── API Routes ───────────────────────────────────────────────────────────────

@app.route('/api/enroll', methods=['POST'])
@csrf.exempt
@login_required
def api_enroll():
    # Support both JSON (legacy) and form POST (agent-compatible)
    if request.is_json:
        data = request.get_json() or {}
        course_id = data.get('course_id')
    else:
        try:
            course_id = int(request.form.get('course_id'))
        except (TypeError, ValueError):
            course_id = None
    course = db.session.get(Course, course_id)
    if not course:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Course not found'}), 404
        flash('Course not found.', 'danger')
        return redirect(request.referrer or url_for('index'))
    existing = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course_id).first()
    if not existing:
        e = Enrollment(user_id=current_user.id, course_id=course_id)
        db.session.add(e)
        db.session.commit()
    if request.is_json:
        return jsonify({'success': True, 'message': f'Enrolled in {course.title}',
                        'enrolled': True})
    flash(f'Successfully enrolled in {course.title}!', 'success')
    return redirect(url_for('course_detail', slug=course.slug))


@app.route('/enroll/<int:course_id>', methods=['POST'])
@login_required
def enroll_form(course_id):
    """Form-POST enroll — agent-compatible (no AJAX required)."""
    course = Course.query.get_or_404(course_id)
    existing = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course_id).first()
    if not existing:
        db.session.add(Enrollment(user_id=current_user.id, course_id=course_id))
        db.session.commit()
        flash(f'Successfully enrolled in {course.title}!', 'success')
    else:
        flash(f'You are already enrolled in {course.title}.', 'info')
    return redirect(url_for('course_detail', slug=course.slug))


@app.route('/api/wishlist/toggle', methods=['POST'])
@csrf.exempt
@login_required
def api_wishlist_toggle():
    # Support both JSON (legacy) and form POST (agent-compatible)
    if request.is_json:
        data = request.get_json() or {}
        course_id = data.get('course_id')
    else:
        try:
            course_id = int(request.form.get('course_id'))
        except (TypeError, ValueError):
            course_id = None
    course = db.session.get(Course, course_id)
    if not course:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Not found'}), 404
        flash('Course not found.', 'danger')
        return redirect(request.referrer or url_for('index'))
    existing = SavedCourse.query.filter_by(
        user_id=current_user.id, course_id=course_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        if request.is_json:
            return jsonify({'success': True, 'saved': False,
                            'message': 'Removed from saved courses'})
        flash(f'Removed {course.title} from saved courses.', 'info')
        return redirect(request.referrer or url_for('wishlist'))
    db.session.add(SavedCourse(user_id=current_user.id, course_id=course_id))
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True, 'saved': True,
                        'message': 'Saved to your list'})
    flash(f'Saved {course.title} to your list!', 'success')
    return redirect(request.referrer or url_for('wishlist'))


@app.route('/wishlist/save/<int:course_id>', methods=['POST'])
@login_required
def wishlist_save_form(course_id):
    """Form-POST save — agent-compatible."""
    course = Course.query.get_or_404(course_id)
    if not SavedCourse.query.filter_by(user_id=current_user.id, course_id=course_id).first():
        db.session.add(SavedCourse(user_id=current_user.id, course_id=course_id))
        db.session.commit()
        flash(f'Saved {course.title} to your list!', 'success')
    else:
        flash(f'{course.title} is already in your saved courses.', 'info')
    return redirect(url_for('course_detail', slug=course.slug))


@app.route('/wishlist/remove/<int:course_id>', methods=['POST'])
@login_required
def wishlist_remove_form(course_id):
    """Form-POST remove from wishlist — agent-compatible."""
    course = Course.query.get_or_404(course_id)
    existing = SavedCourse.query.filter_by(
        user_id=current_user.id, course_id=course_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash(f'Removed {course.title} from saved courses.', 'info')
    return redirect(request.referrer or url_for('wishlist'))

@app.route('/api/courses/<category>')
@csrf.exempt
def api_courses_by_category(category):
    courses = Course.query.filter(
        Course.category.ilike(f'%{category}%')).limit(20).all()
    return jsonify([{
        'id': c.id, 'title': c.title, 'slug': c.slug,
        'rating': c.rating, 'level': c.level,
        'course_type': c.course_type,
    } for c in courses])

# ─── Error handlers ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# ─── Seed data ────────────────────────────────────────────────────────────────

CATEGORY_COLORS = {
    'Computer Science': 'cat-cs',
    'Data Science': 'cat-ds',
    'Business': 'cat-biz',
    'Information Technology': 'cat-it',
    'Language Learning': 'cat-lang',
    'Math and Logic': 'cat-math',
    'Physical Science and Engineering': 'cat-eng',
    'Social Sciences': 'cat-soc',
    'Arts and Humanities': 'cat-arts',
    'Health': 'cat-health',
    'Personal Development': 'cat-pd',
}

def _color(cat):
    return CATEGORY_COLORS.get(cat, 'cat-cs')

def seed_database():
    if Partner.query.count() > 0:
        return

    # ── Partners ──────────────────────────────────────────────────────────────
    partners_data = [
        ('Stanford University', 'stanford', 'United States', 'university', 'Stanford'),
        ('Google', 'google', 'United States', 'company', 'Google'),
        ('IBM', 'ibm', 'United States', 'company', 'IBM'),
        ('Yale University', 'yale', 'United States', 'university', 'Yale'),
        ('Duke University', 'duke', 'United States', 'university', 'Duke'),
        ('University of Michigan', 'umich', 'United States', 'university', 'UMich'),
        ('Johns Hopkins University', 'jhu', 'United States', 'university', 'JHU'),
        ('Deeplearning.AI', 'deeplearningai', 'United States', 'company', 'DeepLearning.AI'),
        ('University of Maryland', 'umd', 'United States', 'university', 'UMD'),
        ('Technical University of Munich', 'tum', 'Germany', 'university', 'TUM'),
        ('The Museum of Modern Art', 'moma', 'United States', 'institution', 'MoMA'),
        ('University of Melbourne', 'umelbourne', 'Australia', 'university', 'UMelbourne'),
        ('Macquarie University', 'macquarie', 'Australia', 'university', 'Macquarie'),
        ('University of Sydney', 'usyd', 'Australia', 'university', 'USyd'),
        ('UNSW Sydney', 'unsw', 'Australia', 'university', 'UNSW'),
        ('Deakin University', 'deakin', 'Australia', 'university', 'Deakin'),
        ('Monash University', 'monash', 'Australia', 'university', 'Monash'),
        ('Australian National University', 'anu', 'Australia', 'university', 'ANU'),
        ('University of Illinois Urbana-Champaign', 'uiuc', 'United States', 'university', 'UIUC'),
        ('University of California, Davis', 'ucdavis', 'United States', 'university', 'UC Davis'),
        ('University of California, San Diego', 'ucsd', 'United States', 'university', 'UCSD'),
        ('University of California, Irvine', 'uci', 'United States', 'university', 'UC Irvine'),
        ('Columbia University', 'columbia', 'United States', 'university', 'Columbia'),
        ('Meta', 'meta', 'United States', 'company', 'Meta'),
        ('Microsoft', 'microsoft', 'United States', 'company', 'Microsoft'),
        ('Amazon Web Services', 'aws', 'United States', 'company', 'AWS'),
        ('Salesforce', 'salesforce', 'United States', 'company', 'Salesforce'),
        ('Rice University', 'rice', 'United States', 'university', 'Rice'),
        ('Vanderbilt University', 'vanderbilt', 'United States', 'university', 'Vanderbilt'),
        ('University at Buffalo', 'ubuffalo', 'United States', 'university', 'UBuffalo'),
        ('University of Minnesota', 'umn', 'United States', 'university', 'UMN'),
        ('University of Colorado Boulder', 'cuboulder', 'United States', 'university', 'CU Boulder'),
        ('Georgia Institute of Technology', 'gatech', 'United States', 'university', 'Georgia Tech'),
        ('Arizona State University', 'asu', 'United States', 'university', 'ASU'),
        ('Princeton University', 'princeton', 'United States', 'university', 'Princeton'),
        ('University of Toronto', 'utoronto', 'Canada', 'university', 'UToronto'),
        ('University of Pennsylvania', 'upenn', 'United States', 'university', 'UPenn'),
        ('University of Florida', 'ufl', 'United States', 'university', 'UFL'),
        ('University of London', 'ulondon', 'United Kingdom', 'university', 'ULondon'),
        ('Commonwealth Bank', 'commbank', 'Australia', 'company', 'CommBank'),
        ('PwC', 'pwc', 'Australia', 'company', 'PwC'),
        ('EIT Digital', 'eitdigital', 'Germany', 'institution', 'EIT Digital'),
        ('Macquarie Bank', 'macquariebank', 'Australia', 'company', 'Macquarie Bank'),
        ('University of Western Australia', 'uwa', 'Australia', 'university', 'UWA'),
        ('RMIT University', 'rmit', 'Australia', 'university', 'RMIT'),
        ('University of Queensland', 'uq', 'Australia', 'university', 'UQ'),
        ('University of Adelaide', 'uadelaide', 'Australia', 'university', 'UAdl'),
        ('Atlassian', 'atlassian', 'Australia', 'company', 'Atlassian'),
    ]
    pid = {}
    for name, slug, country, ptype, short in partners_data:
        p = Partner(name=name, slug=slug, country=country,
                    partner_type=ptype, short_name=short)
        db.session.add(p)
        db.session.flush()
        pid[slug] = p.id
    db.session.commit()

    # ── Helper ────────────────────────────────────────────────────────────────
    def add_course(title, slug, partner_slug, course_type, level, category,
                   duration_text, duration_weeks, duration_hours,
                   rating, review_count, enrolled_count,
                   is_free, has_certificate, credit_eligible,
                   instructor, instructor_title, description,
                   skills, what_you_learn, feature_tags,
                   is_featured=False, is_new=False, sort_date='2024-01-01',
                   degree_type='', subcategory=''):
        c = Course(
            title=title, slug=slug,
            partner_id=pid.get(partner_slug),
            course_type=course_type, level=level,
            category=category, subcategory=subcategory,
            duration_text=duration_text,
            duration_weeks=duration_weeks, duration_hours=duration_hours,
            rating=rating, review_count=review_count,
            enrolled_count=enrolled_count,
            is_free=is_free, has_certificate=has_certificate,
            credit_eligible=credit_eligible,
            instructor=instructor, instructor_title=instructor_title,
            description=description,
            skills=json.dumps(skills),
            what_you_learn=json.dumps(what_you_learn),
            feature_tags=json.dumps(feature_tags),
            is_featured=is_featured, is_new=is_new, sort_date=sort_date,
            degree_type=degree_type,
            color_class=_color(category),
        )
        db.session.add(c)
        db.session.flush()
        return c

    def add_modules(course, module_list):
        for w, entry in enumerate(module_list, 1):
            # 5-tuple: (title, desc, vids, reads, quizzes)
            # 6-tuple: (title, desc, vids, reads, quizzes, video_titles_list)
            if len(entry) == 6:
                title, desc, vids, reads, quizzes, vtitles = entry
                vt_json = json.dumps(vtitles)
            else:
                title, desc, vids, reads, quizzes = entry
                vt_json = '[]'
            m = CourseModule(course_id=course.id, week_number=w, title=title,
                             description=desc, videos_count=vids,
                             readings_count=reads, quizzes_count=quizzes,
                             video_titles=vt_json)
            db.session.add(m)

    def add_sub_courses(spec, titles):
        for i, (title, desc, dur) in enumerate(titles):
            s = SubCourse(specialization_id=spec.id, order_index=i+1,
                          title=title, description=desc, duration_text=dur)
            db.session.add(s)

    # ─────────────────────────────────────────────────────────────────────────
    # Task 15: Introduction to Mathematical Thinking (Stanford)
    c = add_course(
        'Introduction to Mathematical Thinking', 'introduction-to-mathematical-thinking',
        'stanford', 'Course', 'Beginner', 'Math and Logic',
        'Approx. 38 hours', 9.5, 38.0, 4.8, 22000, 750000,
        False, True, False,
        'Dr. Keith Devlin', 'Professor, Stanford University',
        'Learn how to think the way mathematicians do — a powerful cognitive process developed over thousands of years.',
        ['Mathematical Thinking', 'Logic', 'Number Theory', 'Proof Writing', 'Abstract Reasoning'],
        ['Understand mathematical proofs', 'Apply logical reasoning', 'Analyse number theory concepts',
         'Write formal mathematical arguments'],
        ['mathematics', 'logic', 'proof', 'number-theory', 'stanford'],
        True, False, '2023-09-01',
    )
    add_modules(c, [
        ('Introductory Material', 'Course orientation and getting started.', 3, 2, 1),
        ('Analysis of Language — The Mathematics of Everyday Language', 'Language, logic, and communication.', 5, 3, 2),
        ('Analysis of Language — Logical Connectives', 'Conjunctions, disjunctions, conditionals.', 4, 2, 1),
        ('What is a Number?', 'Natural numbers, integers, rationals, reals.', 5, 3, 2),
        ('Mathematical Reasoning in the Real World', 'Apply mathematical thinking to real problems.', 4, 3, 1),
        ('Proofs', 'Direct and indirect proofs, induction.', 6, 4, 2),
    ])

    # Task 16: Introduction to Finance: The Basics
    c = add_course(
        'Introduction to Finance: The Basics', 'introduction-to-finance-the-basics',
        'umich', 'Course', 'Beginner', 'Business',
        'Approx. 14 hours', 3.5, 14.0, 4.7, 15000, 300000,
        False, True, False,
        'Gautam Kaul', 'Professor of Finance, University of Michigan',
        'This course is the foundation of Finance. It introduces students to the three fundamental principles of finance.',
        ['Finance', 'Financial Analysis', 'Time Value of Money', 'Net Present Value', 'Risk and Return'],
        ['Understand key finance principles', 'Calculate time value of money', 'Evaluate investment decisions',
         'Understand risk and return tradeoffs'],
        ['finance', 'basics', 'beginner', 'investment', 'npv'],
        True, False, '2023-06-01',
    )
    add_modules(c, [
        ('The Three Pillars of Finance', 'Foundations and principles.', 5, 3, 1),
        ('The Time Value of Money', 'PV, FV, annuities, perpetuities.', 6, 4, 2),
        ('Stocks, Bonds, and Valuation', 'Asset valuation techniques.', 5, 3, 2),
        ('Risk and Return', 'Portfolio theory and the CAPM.', 4, 3, 1),
    ])

    # Task 19: Introduction to Psychology (Yale)
    c = add_course(
        'Introduction to Psychology', 'introduction-to-psychology',
        'yale', 'Course', 'Beginner', 'Social Sciences',
        'Approx. 14 hours', 3.5, 14.0, 4.9, 38000, 1200000,
        True, True, False,
        'Paul Bloom', 'Professor of Psychology, Yale University',
        'What are people most afraid of? What do our dreams mean? Are we natural-born racists? What makes us happy?',
        ['Psychology', 'Cognitive Psychology', 'Social Psychology', 'Behavioral Science', 'Mental Health'],
        ['Understand major psychological theories', 'Analyse human behaviour', 'Evaluate psychological research',
         'Apply psychology to everyday life'],
        ['psychology', 'beginner', 'free', 'yale', 'social-science', 'behaviour', 'cognitive'],
        True, False, '2023-01-01',
    )
    add_modules(c, [
        ('Introduction: What is Psychology?', 'Overview and history.', 4, 2, 1),
        ('Brain', 'Neuroscience and brain function.', 5, 3, 1),
        ('Development', 'Child development and learning.', 4, 2, 1),
        ('Mind', 'Consciousness, memory, and thought.', 5, 3, 2),
        ('Self and Others', 'Social and personality psychology.', 4, 2, 1),
        ('Good Life', 'Happiness and well-being.', 3, 2, 1),
    ])

    # Task 30: Modern Art & Ideas (MoMA)
    c = add_course(
        'Modern Art & Ideas', 'modern-art-ideas',
        'moma', 'Course', 'Beginner', 'Arts and Humanities',
        'Approx. 8 hours', 2.0, 8.0, 4.7, 8000, 200000,
        True, True, False,
        'MoMA Educators', 'The Museum of Modern Art',
        "Explore works in MoMA's collection and learn to interpret and discuss modern and contemporary art.",
        ['Art History', 'Visual Analysis', 'Modern Art', 'Art Criticism', 'Contemporary Art'],
        ['Analyse modern artworks', 'Understand art movements', 'Discuss art with confidence',
         'Explore MoMA collection highlights'],
        ['art', 'modern', 'moma', 'free', 'visual-art', 'museum', 'humanities'],
        False, False, '2023-04-01',
    )
    add_modules(c, [
        ('Looking at Art', 'How to observe and describe artworks.', 3, 2, 1),
        ('Materials and Techniques', 'How artists make art.', 4, 2, 1),
        ('Art in Society', 'Art and its cultural context.', 3, 2, 1),
        ('Themes in Modern Art', 'Identity, environment, abstraction.', 4, 3, 1),
    ])

    # Task 31: Exploring Quantum Physics (UMD)
    c = add_course(
        'Exploring Quantum Physics', 'exploring-quantum-physics',
        'umd', 'Course', 'Intermediate', 'Physical Science and Engineering',
        'Approx. 30 hours', 7.5, 30.0, 4.6, 6500, 150000,
        False, True, True,
        'Charles Clark', 'Professor of Physics, University of Maryland',
        'Explore Schrödinger equation solutions, measurement postulate, wave-particle duality, and basic quantum mechanics.',
        ['Quantum Mechanics', 'Wave Functions', 'Schrödinger Equation', 'Quantum States', 'Physics'],
        ['Solve the Schrödinger equation', 'Understand wave-particle duality',
         'Apply quantum measurement postulate', 'Describe quantum phenomena'],
        ['quantum', 'physics', 'umd', 'intermediate', 'wave-function', 'schrodinger'],
        False, False, '2023-02-01',
    )
    add_modules(c, [
        ('From Classical to Quantum', 'Introduction and historical background.', 4, 3, 1),
        ('The Schrödinger Equation', 'Formulating and solving the equation.', 5, 3, 2),
        ('Wave Functions and Probability', 'Normalisation and expectation values.', 5, 3, 2),
        ('Quantum Measurement', 'The measurement postulate.', 4, 2, 1),
        ('Applications', 'Particle in a box, harmonic oscillator.', 5, 3, 2),
    ])

    # Task 34: Essentials of Global Health (Yale)
    c = add_course(
        'Essentials of Global Health', 'essentials-of-global-health',
        'yale', 'Course', 'Beginner', 'Health',
        'Approx. 33 hours', 8.0, 33.0, 4.8, 25000, 700000,
        False, True, False,
        'Richard Skolnik', 'Lecturer in Global Affairs, Yale University',
        'A comprehensive introduction to global health that examines the key concepts, issues, and challenges.',
        ['Global Health', 'Public Health', 'Health Policy', 'Epidemiology', 'Health Systems'],
        ['Understand global health challenges', 'Analyse health systems worldwide',
         'Evaluate global health interventions', 'Apply health policy concepts'],
        ['global-health', 'public-health', 'yale', 'health-policy', 'beginner'],
        False, False, '2023-05-01',
    )
    add_modules(c, [
        ('Defining and Measuring Global Health', 'Concepts and metrics.', 5, 3, 1),
        ('The Determinants of Health', 'Social and environmental factors.', 4, 3, 1),
        ('Health Systems', 'Structure and function of health systems.', 5, 4, 2),
        ('Communicable Diseases', 'HIV, TB, malaria and more.', 6, 3, 2),
        ('Non-Communicable Diseases', 'Cancer, diabetes, heart disease.', 5, 3, 1),
        ('Health Equity and Policy', 'Addressing disparities.', 4, 3, 1),
    ])

    # Task 39: Space Safety (TUM)
    c = add_course(
        'Space Safety', 'space-safety',
        'tum', 'Course', 'Beginner', 'Physical Science and Engineering',
        'Approx. 15 hours', 4.0, 15.0, 4.5, 3500, 80000,
        False, True, False,
        'Prof. Ulrich Walter', 'Professor of Space Technology, TUM',
        'Learn about space safety issues including space debris, space environment, and astronaut safety.',
        ['Space Safety', 'Space Debris', 'Space Environment', 'Orbital Mechanics', 'Risk Assessment'],
        ['Identify major space safety challenges', 'Understand space debris mitigation',
         'Analyse radiation environments', 'Evaluate astronaut safety protocols'],
        ['space', 'safety', 'tum', 'debris', 'orbital', 'astronaut', 'engineering'],
        False, False, '2024-01-15',
    )
    add_modules(c, [
        ('Introduction to Space Safety',
         'Overview of space safety domain.',
         4, 3, 1,
         ['Welcome to Space Safety',
          'A Short History of Space Mishaps',
          'The Space Environment as a Hazard',
          'Course Roadmap and Assessment Overview']),
        ('Space Debris',
         'Origins, tracking, and mitigation of orbital debris.',
         7, 4, 2,
         ['Where Space Debris Comes From',
          'The Kessler Syndrome Explained',
          'Tracking Debris from the Ground',
          'On-Orbit Conjunction Assessment',
          'Active Debris Removal Concepts',
          'Post-Mission Disposal Guidelines',
          'Future Outlook for Orbital Sustainability']),
        ('Space Weather and Radiation',
         'Solar events, radiation belts.',
         5, 3, 1,
         ['The Sun as a Driver of Space Weather',
          'Solar Wind, CMEs, and Flares',
          'Earth\u2019s Magnetosphere and Radiation Belts',
          'Radiation Effects on Crew and Hardware',
          'Forecasting and Mitigation Strategies']),
        ('Astronaut Safety',
         'Life support and extravehicular activities.',
         5, 3, 2,
         ['Crew Health Risks in Microgravity',
          'Life-Support System Architecture',
          'EVA Operations and Suit Safety',
          'Emergency Procedures and Abort Modes',
          'Long-Duration Mission Considerations']),
    ])

    # Task 25: Relativity for beginners (Stanford)
    c = add_course(
        "Understanding Einstein: The Special Theory of Relativity",
        'understanding-einstein-special-relativity',
        'stanford', 'Course', 'Beginner', 'Physical Science and Engineering',
        'Approx. 18 hours', 4.5, 18.0, 4.8, 14000, 350000,
        False, True, False,
        'Larry Randles Lagerstrom', 'Instructor, Stanford University',
        'In this course we will seek to understand Einstein, especially the Special Theory of Relativity.',
        ['Special Relativity', 'Space-Time', 'Physics', 'Einstein', 'Relativity'],
        ['Understand special relativity', 'Analyse space-time diagrams',
         'Calculate time dilation and length contraction', 'Understand E=mc²'],
        ['relativity', 'einstein', 'physics', 'stanford', 'beginner', 'space-time'],
        False, False, '2023-08-01',
    )
    add_modules(c, [
        ('Introduction and Pre-Requisites', 'Setting the stage.', 3, 2, 1),
        ('The Principle of Relativity', 'Galilean relativity and its limits.', 4, 3, 1),
        ('Special Theory of Relativity', 'Postulates and their consequences.', 5, 4, 2),
        ('Space-Time Diagrams', 'Visualising relativistic effects.', 4, 3, 2),
        ('Time Dilation and Length Contraction', 'Core results.', 5, 3, 1),
        ('Mass-Energy Equivalence', 'E=mc² and applications.', 4, 3, 1),
    ])

    # Task 35: Sustainable Agriculture
    c = add_course(
        'Sustainable Agricultural Land Management', 'sustainable-agricultural-land-management',
        'ufl', 'Course', 'Beginner', 'Physical Science and Engineering',
        'Approx. 12 hours', 4.0, 12.0, 4.6, 5500, 120000,
        False, True, False,
        'Ann Wilkie', 'Professor, University of Florida',
        'Learn sustainable practices for agricultural land management including soil health, water conservation, and agroforestry.',
        ['Sustainable Agriculture', 'Soil Science', 'Water Management', 'Agroforestry', 'Land Use'],
        ['Implement sustainable farming practices', 'Manage soil health',
         'Conserve water in agriculture', 'Apply agroforestry principles'],
        ['sustainable', 'agriculture', 'soil', 'land-management', 'beginner', 'farming'],
        False, False, '2023-11-01',
    )
    add_modules(c, [
        ('Foundations of Sustainable Agriculture', 'Core principles and history.', 4, 3, 1),
        ('Soil Health and Management', 'Soil biology, composting, cover crops.', 5, 3, 2),
        ('Water Conservation', 'Irrigation efficiency and watershed management.', 4, 3, 1),
        ('Agroforestry Systems', 'Integrating trees and crops.', 4, 2, 1),
    ])

    # Task 9/23: AI Ethics (< 20 hours)
    c = add_course(
        'AI, Empathy & Ethics', 'ai-empathy-ethics',
        'ucsc' if 'ucsc' in pid else 'ucsantacruz' if 'ucsantacruz' in pid else 'stanford',
        'Course', 'Beginner', 'Computer Science',
        'Approx. 14 hours', 3.5, 14.0, 4.7, 7500, 180000,
        False, True, False,
        'Kathi Fisler', 'Professor of Computer Science',
        'Explore ethical questions and societal implications of artificial intelligence and machine learning.',
        ['AI Ethics', 'Machine Learning Ethics', 'Bias in AI', 'Fairness', 'Responsible AI'],
        ['Identify ethical issues in AI systems', 'Evaluate fairness in machine learning',
         'Apply ethical frameworks to AI design', 'Analyse bias and discrimination in AI'],
        ['ai-ethics', 'ethics', 'artificial-intelligence', 'bias', 'fairness', 'beginner'],
        False, False, '2024-02-01',
    )

    c2 = add_course(
        'Ethics of Artificial Intelligence', 'ethics-of-artificial-intelligence',
        'princeton', 'Course', 'Beginner', 'Computer Science',
        'Approx. 18 hours', 4.5, 18.0, 4.8, 9200, 220000,
        False, True, False,
        'Sandra Wachter', 'Professor of Technology and Regulation',
        'This course covers ethical considerations of AI including privacy, accountability, transparency, and fairness.',
        ['AI Ethics', 'Privacy', 'Algorithmic Accountability', 'Responsible AI', 'Technology Ethics'],
        ['Understand AI ethical principles', 'Analyse privacy risks',
         'Evaluate accountability mechanisms', 'Design responsible AI systems'],
        ['ai-ethics', 'ethics', 'artificial-intelligence', 'privacy', 'transparency', 'less-20-hours'],
        False, True, '2024-03-01',
    )

    # Task 0: 3D Printing (Beginner, 1-3 months, university)
    c = add_course(
        '3D Printing Revolution', '3d-printing-revolution',
        'uiuc', 'Course', 'Beginner', 'Physical Science and Engineering',
        '1-3 Months', 6.0, 30.0, 4.6, 8000, 180000,
        False, True, False,
        'Vishal Singh', 'Professor, University of Illinois',
        'Understand the technologies, applications, and implications of 3D printing and additive manufacturing.',
        ['3D Printing', 'Additive Manufacturing', 'CAD Design', 'Prototyping', 'Manufacturing'],
        ['Understand 3D printing technologies', 'Design parts for additive manufacturing',
         'Evaluate application domains', 'Analyse industry impact'],
        ['3d-printing', 'additive-manufacturing', 'beginner', 'university', '1-3-months'],
        False, False, '2023-07-01',
    )

    c = add_course(
        '3D Printing Applications', '3d-printing-applications',
        'uci', 'Course', 'Beginner', 'Physical Science and Engineering',
        '1-3 Months', 5.0, 25.0, 4.5, 6000, 120000,
        False, True, False,
        'Timothy Scott', 'Professor, UC Irvine',
        'Explore real-world applications of 3D printing in medicine, aerospace, architecture, and consumer goods.',
        ['3D Printing', 'Bioprinting', 'Aerospace Manufacturing', 'Design for Additive Manufacturing'],
        ['Apply 3D printing to real problems', 'Understand bioprinting', 'Design for manufacturing'],
        ['3d-printing', 'applications', 'beginner', '1-3-months'],
        False, False, '2023-09-01',
    )

    # Task 1: Python (Beginner)
    c = add_course(
        'Python for Everybody', 'python-for-everybody',
        'umich', 'Course', 'Beginner', 'Computer Science',
        'Approx. 19 hours', 4.8, 19.0, 4.8, 450000, 4500000,
        False, True, False,
        'Charles Severance', 'Clinical Professor, University of Michigan',
        'This course aims to teach everyone the basics of programming computers using Python. Built for absolute beginners — no prior coding background needed.',
        ['Python Programming', 'Data Structures', 'Networked Data', 'Databases', 'Visualization'],
        ['Install Python and start programming', 'Write Python functions and loops',
         'Manipulate files and data', 'Use Python for web scraping'],
        ['python', 'programming', 'beginner', 'no-experience', 'basics', 'fundamentals'],
        True, False, '2023-01-01',
    )

    c = add_course(
        'Programming for Everybody (Getting Started with Python)', 'programming-for-everybody',
        'umich', 'Course', 'Beginner', 'Computer Science',
        'Approx. 19 hours', 4.8, 19.0, 4.8, 400000, 3800000,
        True, True, False,
        'Charles Severance', 'Clinical Professor, University of Michigan',
        'This course aims to teach everyone the basics of programming using Python. No prior experience needed.',
        ['Python', 'Programming Basics', 'Variables', 'Conditionals', 'Functions'],
        ['Write basic Python programs', 'Understand variables and expressions',
         'Use conditionals and loops', 'Debug simple programs'],
        ['python', 'beginner', 'no-experience', 'free', 'programming-basics'],
        True, False, '2023-01-01',
    )

    # Task 2: Spanish Specialization (Beginner)
    spec_spanish = add_course(
        'Learn Spanish: Basic Spanish Vocabulary Specialization',
        'learn-spanish-basic-vocabulary-specialization',
        'ucdavis', 'Specialization', 'Beginner', 'Language Learning',
        '3 - 6 Months', 16.0, 70.0, 4.8, 25000, 600000,
        False, True, False,
        'University of California, Davis Instructors', 'UC Davis Language Program',
        'Master basic Spanish vocabulary and grammar through five hands-on courses.',
        ['Spanish', 'Spanish Grammar', 'Spanish Vocabulary', 'Conversational Spanish'],
        ['Communicate in basic Spanish', 'Use essential vocabulary', 'Form simple sentences',
         'Understand Spanish culture'],
        ['spanish', 'specialization', 'beginner', 'language', 'vocabulary'],
        True, False, '2023-03-01',
    )
    add_sub_courses(spec_spanish, [
        ('Spanish Vocabulary: Meeting People', 'Greetings, introductions, and small talk.', 'Approx. 10 hours'),
        ('Spanish Vocabulary: Around Town', 'Directions, transportation, and places.', 'Approx. 10 hours'),
        ('Spanish Vocabulary: At Home', 'Home, family, and daily routines.', 'Approx. 10 hours'),
        ('Spanish Vocabulary: At Work', 'Professional contexts and work vocabulary.', 'Approx. 10 hours'),
        ('Spanish Vocabulary: Nature and Environment', 'Outdoor vocabulary and descriptions.', 'Approx. 10 hours'),
    ])

    # Task 3: Python Data Science (newest sort)
    c = add_course(
        'Python for Data Science, AI & Development', 'python-for-data-science-ai-development',
        'ibm', 'Course', 'Beginner', 'Data Science',
        'Approx. 25 hours', 6.3, 25.0, 4.6, 42000, 1200000,
        False, True, False,
        'Joseph Santarcangelo', 'Data Scientist at IBM',
        'Learn Python for Data Science and AI. No prior programming experience required.',
        ['Python', 'Data Analysis', 'Numpy', 'Pandas', 'Machine Learning'],
        ['Use Python for data science', 'Work with NumPy and Pandas', 'Create visualizations',
         'Apply Python to AI development'],
        ['python', 'data-science', 'ai', 'ibm', 'beginner', 'pandas', 'numpy'],
        False, True, '2024-04-01',
    )

    c = add_course(
        'Python Data Science Fundamentals', 'python-data-science-fundamentals',
        'ibm', 'Course', 'Beginner', 'Data Science',
        'Approx. 18 hours', 4.5, 18.0, 4.7, 18000, 450000,
        False, True, False,
        'Alex Aklson', 'Data Scientist, IBM',
        'Build a strong foundation in Python for data science analysis and visualization.',
        ['Python', 'Data Science', 'Pandas', 'Data Visualization', 'Jupyter'],
        ['Set up Jupyter notebooks', 'Manipulate data with Pandas', 'Create visualizations',
         'Apply statistical methods'],
        ['python', 'data-science', 'fundamentals', 'beginner', 'ibm'],
        False, True, '2024-05-01',
    )

    c = add_course(
        'Applied Data Science with Python Specialization', 'applied-data-science-python',
        'umich', 'Specialization', 'Intermediate', 'Data Science',
        '5 Months', 21.7, 90.0, 4.5, 55000, 800000,
        False, True, False,
        'Christopher Brooks', 'Lecturer, University of Michigan',
        'Gain new skills and applied insights with Python. Includes text mining, social network analysis, and machine learning.',
        ['Python', 'Data Science', 'Machine Learning', 'Text Mining', 'Social Network Analysis'],
        ['Apply Python to data science', 'Build machine learning models', 'Analyse text data',
         'Work with social network data'],
        ['python', 'data-science', 'applied', 'intermediate', 'michigan', 'specialization'],
        False, True, '2024-03-15',
    )

    # Task 4: Business Process Management (rating 4.7)
    c = add_course(
        'Business Process Management', 'business-process-management',
        'uq' if 'uq' in pid else 'vanderbilt',
        'Course', 'Beginner', 'Business',
        'Approx. 17 hours', 4.3, 17.0, 4.7, 12000, 350000,
        False, True, False,
        'Marcello La Rosa', 'Professor, University of Queensland',
        'Business processes are the lifeblood of an organization. Learn how to model, analyze, and improve them.',
        ['Business Process Management', 'Process Modeling', 'BPMN', 'Process Analysis', 'Workflow'],
        ['Model business processes with BPMN', 'Analyze process performance',
         'Improve and optimize workflows', 'Implement process management'],
        ['business-process', 'bpm', 'workflow', 'bpmn', 'beginner', 'management'],
        False, False, '2023-06-15',
    )

    # Task 5: C++ Specialization (Beginner)
    spec_cpp = add_course(
        'Coding for Everyone: C and C++ Specialization', 'coding-everyone-c-cpp',
        'ucsd', 'Specialization', 'Beginner', 'Computer Science',
        '4 Months', 17.4, 70.0, 4.6, 15000, 320000,
        False, True, False,
        'Idil Akin', 'Instructor, UC San Diego',
        'Master the fundamentals of C and C++ programming from scratch. No prior experience needed.',
        ['C Programming', 'C++ Programming', 'Object-Oriented Programming', 'Data Structures'],
        ['Write C programs', 'Use C++ classes and objects', 'Implement data structures',
         'Build real-world applications'],
        ['cpp', 'c-plus-plus', 'c-programming', 'beginner', 'specialization', 'coding'],
        False, False, '2023-07-01',
    )
    add_sub_courses(spec_cpp, [
        ('C for Everyone: Programming Fundamentals', 'Variables, types, control flow.', 'Approx. 14 hours'),
        ('C for Everyone: Structured Programming', 'Functions, arrays, pointers.', 'Approx. 14 hours'),
        ('C++ for C Programmers, Part A', 'Classes, templates, STL.', 'Approx. 16 hours'),
        ('C++ for C Programmers, Part B', 'Advanced OOP and design patterns.', 'Approx. 14 hours'),
    ])

    # Task 6: AI for Healthcare
    c = add_course(
        'AI for Medicine Specialization', 'ai-for-medicine',
        'deeplearningai', 'Specialization', 'Intermediate', 'Health',
        '3 Months', 13.0, 50.0, 4.7, 28000, 450000,
        False, True, False,
        'Andrew Ng', 'Founder, DeepLearning.AI',
        'Apply AI to medicine: diagnose diseases from medical images, predict patient outcomes, and understand medical text.',
        ['Medical AI', 'Computer Vision', 'NLP for Medicine', 'Clinical Data', 'Disease Diagnosis'],
        ['Build AI models for medical imaging', 'Predict patient outcomes',
         'Process clinical text', 'Evaluate medical AI systems'],
        ['ai', 'medicine', 'healthcare', 'deep-learning', 'medical-imaging', 'intermediate'],
        True, False, '2023-05-01',
    )

    c2 = add_course(
        'Artificial Intelligence for Healthcare', 'artificial-intelligence-healthcare',
        'stanford', 'Course', 'Intermediate', 'Health',
        'Approx. 20 hours', 5.0, 20.0, 4.6, 12000, 200000,
        False, True, False,
        'Nigam Shah', 'Professor of Biomedical Informatics, Stanford University',
        'Learn how AI is transforming healthcare including clinical decision support, genomics, and medical imaging.',
        ['Healthcare AI', 'Clinical Informatics', 'Medical Imaging AI', 'Genomics', 'EHR Analytics'],
        ['Apply machine learning to clinical data', 'Understand AI regulations in healthcare',
         'Build clinical NLP models', 'Evaluate AI safety in medicine'],
        ['ai', 'healthcare', 'clinical', 'stanford', 'medical', 'intermediate'],
        False, False, '2023-09-01',
    )
    add_modules(c2, [
        ('Introduction to AI in Healthcare', 'Overview of AI applications in medicine and clinical workflows.', 4, 3, 1),
        ('Medical Imaging with AI', 'Apply deep learning to radiology and pathology images.', 5, 3, 2),
        ('Clinical NLP and EHR Analytics', 'Process clinical notes and electronic health records with NLP.', 4, 3, 1),
        ('AI Ethics and Regulation in Medicine', 'Understand regulations, safety, and ethical considerations.', 3, 2, 1),
    ])

    # Task 7: Reinforcement Learning (Intermediate)
    spec_rl = add_course(
        'Reinforcement Learning Specialization', 'reinforcement-learning-specialization',
        'ualberta' if 'ualberta' in pid else 'umich',
        'Specialization', 'Intermediate', 'Computer Science',
        '4 Months', 17.4, 70.0, 4.7, 18000, 250000,
        False, True, False,
        'Martha White', 'Associate Professor, University of Alberta',
        'Learn the fundamentals of reinforcement learning and how to apply RL to real-world problems.',
        ['Reinforcement Learning', 'Q-Learning', 'Policy Gradient', 'Actor-Critic', 'MDP'],
        ['Implement RL algorithms', 'Solve MDPs', 'Apply policy gradient methods',
         'Build deep RL agents'],
        ['reinforcement-learning', 'rl', 'intermediate', 'q-learning', 'policy-gradient'],
        False, False, '2023-04-01',
    )

    c = add_course(
        'Fundamentals of Reinforcement Learning', 'fundamentals-reinforcement-learning',
        'umich', 'Course', 'Intermediate', 'Computer Science',
        'Approx. 14 hours', 3.5, 14.0, 4.8, 12000, 180000,
        False, True, False,
        'Adam White', 'Assistant Professor, University of Alberta',
        'Explore key principles of reinforcement learning including k-armed bandits, Markov decision processes, and dynamic programming.',
        ['Reinforcement Learning', 'Markov Decision Processes', 'Dynamic Programming', 'Value Functions'],
        ['Understand RL fundamentals', 'Implement k-armed bandit algorithms',
         'Solve MDPs with dynamic programming', 'Apply temporal difference learning'],
        ['reinforcement-learning', 'rl', 'intermediate', 'mdp', 'td-learning'],
        False, False, '2023-06-01',
    )

    # Task 8: R for Data Science (Free)
    c = add_course(
        'R Programming', 'r-programming',
        'jhu', 'Course', 'Beginner', 'Data Science',
        'Approx. 57 hours', 4.0, 57.0, 4.5, 85000, 1200000,
        True, True, False,
        'Roger D. Peng', 'Associate Professor, Johns Hopkins University',
        'In this course you will learn how to program in R and how to use R for effective data analysis.',
        ['R Programming', 'Data Analysis', 'Statistical Computing', 'Data Visualization', 'RStudio'],
        ['Write R programs', 'Manipulate and clean data', 'Create statistical summaries',
         'Build data visualizations'],
        ['r-programming', 'r', 'data-science', 'free', 'beginner', 'statistics', 'r-for-data-science'],
        False, False, '2023-02-01',
    )

    c = add_course(
        'R for Data Science and Machine Learning', 'r-data-science-machine-learning',
        'jhu', 'Course', 'Beginner', 'Data Science',
        'Approx. 20 hours', 5.0, 20.0, 4.6, 22000, 380000,
        True, True, False,
        'Brian Caffo', 'Professor, Johns Hopkins University',
        'Learn R for data science including data manipulation, visualization, and machine learning.',
        ['R', 'Data Science', 'Machine Learning', 'ggplot2', 'caret', 'tidyverse'],
        ['Use tidyverse for data wrangling', 'Build ML models in R',
         'Create publications-quality charts', 'Apply R to real datasets'],
        ['r', 'data-science', 'machine-learning', 'free', 'beginner', 'r-for-data-science', 'ggplot'],
        False, False, '2023-08-01',
    )

    # Task 10: Intro to AI (Beginner)
    c = add_course(
        'AI For Everyone', 'ai-for-everyone',
        'deeplearningai', 'Course', 'Beginner', 'Computer Science',
        'Approx. 6 hours', 1.5, 6.0, 4.8, 95000, 2300000,
        False, True, False,
        'Andrew Ng', 'CEO/Founder Landing AI, Founder deeplearning.ai',
        'AI is not only for engineers. This non-technical course teaches you what AI can and cannot do.',
        ['Artificial Intelligence', 'Machine Learning Strategy', 'AI Ethics', 'AI Projects', 'Deep Learning'],
        ['Understand AI capabilities and limitations', 'Build an AI strategy',
         'Navigate AI ethics', 'Identify AI opportunities in your organization'],
        ['ai', 'artificial-intelligence', 'beginner', 'non-technical', 'deeplearning', 'strategy'],
        True, False, '2023-01-01',
    )

    c = add_course(
        'Introduction to Artificial Intelligence (AI)', 'intro-artificial-intelligence',
        'ibm', 'Course', 'Beginner', 'Computer Science',
        'Approx. 9 hours', 2.3, 9.0, 4.7, 45000, 900000,
        False, True, False,
        'Rav Ahuja', 'Director of Offerings, IBM',
        'A gentle introduction to AI: what it is, why it matters, where it is used.',
        ['Artificial Intelligence', 'Machine Learning Basics', 'Natural Language Processing', 'Computer Vision'],
        ['Define artificial intelligence', 'Explain machine learning basics',
         'Identify AI use cases', 'Understand AI tools and applications'],
        ['ai', 'artificial-intelligence', 'beginner', 'introduction', 'ibm', 'intro'],
        False, False, '2023-03-01',
    )

    # Task 11: Project Management Specialization (university)
    spec_pm = add_course(
        'Engineering Project Management Specialization', 'engineering-project-management-specialization',
        'rice', 'Specialization', 'Beginner', 'Business',
        '5 Months', 21.7, 80.0, 4.7, 12000, 180000,
        False, True, False,
        'Rob Stone', 'Adjunct Professor, Rice University',
        'Learn project management principles and practices for engineering and technical projects.',
        ['Project Management', 'Risk Management', 'Scheduling', 'Stakeholder Management', 'Agile'],
        ['Plan and schedule projects', 'Manage project risks', 'Lead project teams',
         'Apply agile methodologies'],
        ['project-management', 'engineering', 'university', 'specialization', 'agile', 'scheduling'],
        False, False, '2023-05-01',
    )
    add_sub_courses(spec_pm, [
        ('Initiating and Planning Projects', 'Scope, schedule, and budget planning.', 'Approx. 14 hours'),
        ('Budgeting and Scheduling Projects', 'Earned value, scheduling techniques.', 'Approx. 16 hours'),
        ('Managing Project Risks and Changes', 'Risk identification and mitigation.', 'Approx. 14 hours'),
        ('Project Management Project', 'Capstone project applying all skills.', 'Approx. 16 hours'),
    ])

    # Task 12: Java basics (course not specialization)
    c = add_course(
        'Object Oriented Programming in Java', 'object-oriented-programming-java',
        'ucsd', 'Course', 'Beginner', 'Computer Science',
        'Approx. 42 hours', 10.5, 42.0, 4.6, 28000, 600000,
        False, True, False,
        'Leo Porter', 'Associate Teaching Professor, UC San Diego',
        'Learn the fundamentals of object-oriented programming in Java, the world\'s most popular programming language.',
        ['Java', 'Object-Oriented Programming', 'Data Structures', 'Algorithms', 'Classes'],
        ['Write Java programs', 'Create classes and objects', 'Implement interfaces',
         'Use Java collections'],
        ['java', 'object-oriented', 'programming', 'beginner', 'oop', 'basics', 'fundamentals'],
        False, False, '2023-04-01',
    )

    c = add_course(
        'Java Programming Basics', 'java-programming-basics',
        'ucsd', 'Course', 'Beginner', 'Computer Science',
        'Approx. 15 hours', 3.8, 15.0, 4.5, 15000, 320000,
        False, True, False,
        'Christine Alvarado', 'Teaching Professor, UC San Diego',
        'Get started with Java programming: variables, types, expressions, conditions, and loops.',
        ['Java', 'Programming Basics', 'Variables', 'Loops', 'Arrays'],
        ['Write basic Java programs', 'Understand variables and types',
         'Use loops and conditionals', 'Debug Java code'],
        ['java', 'basics', 'beginner', 'programming', 'java-basics'],
        False, False, '2023-06-01',
    )

    # Task 13: Python Specialization (skills)
    spec_py = add_course(
        'Python 3 Programming Specialization', 'python-3-programming-specialization',
        'umich', 'Specialization', 'Beginner', 'Computer Science',
        '5 Months', 21.7, 85.0, 4.8, 68000, 1100000,
        False, True, False,
        'Paul Resnick', 'Associate Professor, University of Michigan',
        'This specialization teaches the fundamentals of programming in Python 3.',
        ['Python', 'Functions', 'Files and Dictionaries', 'Data Collection', 'Classes'],
        ['Write Python 3 programs', 'Use files and dictionaries',
         'Scrape web data', 'Use classes and inheritance'],
        ['python', 'python3', 'specialization', 'beginner', 'programming', 'umich'],
        True, False, '2023-02-01',
    )
    add_sub_courses(spec_py, [
        ('Python Basics', 'Expressions, types, conditionals.', 'Approx. 19 hours'),
        ('Python Functions, Files, and Dictionaries', 'Functions and file I/O.', 'Approx. 19 hours'),
        ('Data Collection and Processing with Python', 'Web APIs and data processing.', 'Approx. 19 hours'),
        ('Python Classes and Inheritance', 'OOP with Python.', 'Approx. 19 hours'),
        ('Python Project: pillow, tesseract, and opencv', 'Image processing project.', 'Approx. 16 hours'),
    ])

    # Task 14: Project Management with Agile modules
    c = add_course(
        'Introduction to Project Management', 'introduction-to-project-management',
        'umelbourne', 'Course', 'Beginner', 'Business',
        'Approx. 10 hours', 2.5, 10.0, 4.7, 35000, 800000,
        False, True, False,
        'Margaret Tan', 'Senior Lecturer, University of Melbourne',
        'Learn the fundamentals of project management including planning, scheduling, risk management, and agile methods.',
        ['Project Management', 'Agile', 'Scrum', 'Risk Management', 'Scheduling'],
        ['Plan a project from start to finish', 'Apply agile methodologies',
         'Manage project risks', 'Use project management tools'],
        ['project-management', 'beginner', 'agile', 'scrum', 'introductory', 'scheduling'],
        False, False, '2023-07-01',
    )
    add_modules(c, [
        ('Introduction to Project Management', 'Overview and frameworks.', 3, 2, 1),
        ('Project Planning and Scheduling', 'WBS, Gantt charts, critical path.', 4, 3, 2),
        ('Agile Project Management', 'Scrum, sprints, and agile practices.', 5, 3, 2),
        ('Risk Management', 'Identifying and mitigating project risks.', 4, 2, 1),
    ])

    # Task 17: Machine Learning (Credit Eligible)
    c = add_course(
        'Machine Learning Specialization', 'machine-learning-specialization',
        'stanford', 'Specialization', 'Beginner', 'Data Science',
        '3 Months', 13.0, 50.0, 4.9, 150000, 2800000,
        False, True, True,
        'Andrew Ng', 'Adjunct Professor, Stanford University',
        'Build ML models with NumPy & scikit-learn, build & train neural networks with TensorFlow.',
        ['Machine Learning', 'Neural Networks', 'Decision Trees', 'Regression', 'Clustering'],
        ['Build supervised learning models', 'Train neural networks', 'Apply unsupervised learning',
         'Use best ML practices'],
        ['machine-learning', 'stanford', 'neural-networks', 'scikit-learn', 'credit-eligible'],
        True, False, '2023-01-01',
    )

    c = add_course(
        'Machine Learning with Python', 'machine-learning-python',
        'ibm', 'Course', 'Intermediate', 'Data Science',
        'Approx. 25 hours', 6.3, 25.0, 4.7, 68000, 950000,
        False, True, True,
        'Saeed Aghabozorgi', 'Senior Data Scientist, IBM',
        'This course dives into the basics of machine learning using Python, including regression, classification, and clustering.',
        ['Machine Learning', 'Python', 'Regression', 'Classification', 'Clustering', 'scikit-learn'],
        ['Apply ML algorithms', 'Build regression models', 'Implement classification',
         'Use scikit-learn'],
        ['machine-learning', 'python', 'ibm', 'intermediate', 'credit-eligible', 'supervised'],
        False, False, '2023-04-01',
    )

    # Task 18: JavaScript (Beginner, Certificate)
    c = add_course(
        'HTML, CSS, and Javascript for Web Developers', 'html-css-javascript-web-developers',
        'jhu', 'Course', 'Beginner', 'Computer Science',
        'Approx. 40 hours', 10.0, 40.0, 4.7, 35000, 750000,
        False, True, False,
        'Yaakov Chaikin', 'Adjunct Professor, Johns Hopkins University',
        'Do you realize that the only functionality of a web application that the user directly interacts with is through the web browser?',
        ['HTML', 'CSS', 'JavaScript', 'Web Development', 'Bootstrap'],
        ['Build web pages with HTML', 'Style with CSS and Bootstrap',
         'Add interactivity with JavaScript', 'Create dynamic web applications'],
        ['javascript', 'html', 'css', 'web-development', 'beginner', 'certificate', 'frontend'],
        False, False, '2023-03-01',
    )

    c = add_course(
        'JavaScript Algorithms and Data Structures', 'javascript-algorithms-data-structures',
        'meta', 'Professional Certificate', 'Beginner', 'Computer Science',
        '6 Months', 26.0, 100.0, 4.8, 22000, 400000,
        False, True, False,
        'Meta Technical Team', 'Meta Instructors',
        'Learn JavaScript programming language including data structures, algorithms, and modern JS features.',
        ['JavaScript', 'ES6', 'Data Structures', 'Algorithms', 'Functional Programming'],
        ['Master JavaScript fundamentals', 'Use ES6+ features',
         'Implement data structures', 'Write efficient algorithms'],
        ['javascript', 'algorithms', 'data-structures', 'beginner', 'meta', 'certificate', 'js'],
        False, False, '2023-06-01',
    )

    # Task 20: Blockchain (Intermediate, 1-4 weeks)
    c = add_course(
        'Blockchain Basics', 'blockchain-basics',
        'ubuffalo', 'Course', 'Intermediate', 'Computer Science',
        '1-4 Weeks', 2.0, 10.0, 4.6, 18000, 350000,
        False, True, False,
        'Bina Ramamurthy', 'Associate Professor, University at Buffalo',
        'A foundational course for understanding the components that make up the Bitcoin, Blockchain technology.',
        ['Blockchain', 'Bitcoin', 'Smart Contracts', 'Ethereum', 'Consensus Mechanisms'],
        ['Understand blockchain technology', 'Explain Bitcoin architecture',
         'Describe smart contracts', 'Analyse consensus mechanisms'],
        ['blockchain', 'basics', 'intermediate', 'bitcoin', 'ethereum', '1-4-weeks', 'technology'],
        False, False, '2023-05-01',
    )

    c = add_course(
        'Blockchain Technology', 'blockchain-technology',
        'ubuffalo', 'Course', 'Intermediate', 'Computer Science',
        '1-4 Weeks', 3.0, 12.0, 4.5, 12000, 200000,
        False, True, False,
        'Bina Ramamurthy', 'Associate Professor, University at Buffalo',
        'Explore the technical underpinnings of blockchain technology and how it enables trustless systems.',
        ['Blockchain Technology', 'Distributed Ledger', 'Cryptography', 'Smart Contracts', 'DApps'],
        ['Explain distributed ledger technology', 'Implement basic smart contracts',
         'Design blockchain solutions', 'Evaluate security tradeoffs'],
        ['blockchain', 'technology', 'intermediate', 'distributed-ledger', '1-4-weeks'],
        False, False, '2023-07-01',
    )

    # Task 21: Digital Marketing (Beginner)
    c = add_course(
        'Fundamentals of Digital Marketing', 'fundamentals-digital-marketing',
        'google', 'Course', 'Beginner', 'Business',
        'Approx. 40 hours', 10.0, 40.0, 4.7, 40000, 900000,
        True, True, False,
        'Google Career Certificates', 'Google',
        'Learn the fundamentals of digital marketing with this free course accredited by IAB Europe.',
        ['Digital Marketing', 'SEO', 'SEM', 'Social Media Marketing', 'Analytics'],
        ['Create a digital marketing strategy', 'Optimize for search engines',
         'Run social media campaigns', 'Use Google Analytics'],
        ['digital-marketing', 'marketing', 'beginner', 'google', 'free', 'seo', 'social-media'],
        False, False, '2023-03-01',
    )

    c = add_course(
        'Digital Marketing Specialization', 'digital-marketing-specialization',
        'uiuc', 'Specialization', 'Beginner', 'Business',
        '8 Months', 34.7, 130.0, 4.7, 30000, 600000,
        False, True, False,
        'Aric Rindfleisch', 'Professor, University of Illinois',
        'The Digital Marketing Specialization from University of Illinois covers digital marketing channels, tools, and strategies.',
        ['Digital Marketing', 'Content Marketing', 'Social Media', 'Email Marketing', 'Marketing Analytics'],
        ['Design a digital marketing strategy', 'Create content campaigns',
         'Manage social media', 'Analyse marketing data'],
        ['digital-marketing', 'specialization', 'beginner', 'uiuc', 'content', 'social-media'],
        False, False, '2023-01-01',
    )

    # Task 22: Human Resource Specialization
    spec_hr = add_course(
        'Human Resource Management: HR for People Managers Specialization',
        'human-resource-management-specialization',
        'umn', 'Specialization', 'Beginner', 'Business',
        '6 Months', 26.0, 100.0, 4.7, 22000, 450000,
        False, True, False,
        'John W. Budd', 'Professor, University of Minnesota',
        'Master human resource management: recruiting, performance management, and compensation.',
        ['Human Resources', 'Talent Acquisition', 'Performance Management', 'Compensation', 'Employee Relations'],
        ['Hire and develop employees', 'Design performance management systems',
         'Create compensation structures', 'Manage employee relations'],
        ['human-resource', 'hr', 'people-management', 'specialization', 'beginner', 'talent', 'recruitment'],
        False, False, '2023-04-01',
    )
    add_sub_courses(spec_hr, [
        ('Preparing to Manage Human Resources', 'Foundations of HR management.', 'Approx. 10 hours'),
        ('Recruiting, Hiring, and Onboarding Employees', 'The full hiring lifecycle.', 'Approx. 10 hours'),
        ('Managing Employee Performance', 'Performance evaluation and improvement.', 'Approx. 10 hours'),
        ('Managing Employee Compensation', 'Salary structures and benefits.', 'Approx. 10 hours'),
        ('Human Resources Management Capstone: HR for People Managers', 'Integrative capstone.', 'Approx. 12 hours'),
    ])

    # Task 24: Sustainability (Physical Science category)
    c = add_course(
        'Sustainable Development and Its Complexity', 'sustainable-development-complexity',
        'toronto' if 'toronto' in pid else 'utoronto',
        'Course', 'Beginner', 'Physical Science and Engineering',
        'Approx. 12 hours', 3.0, 12.0, 4.7, 14000, 300000,
        False, True, False,
        'Lucie Bhatt', 'Professor, University of Toronto',
        'Learn about sustainable development from a systems perspective, covering energy, climate, and social equity.',
        ['Sustainability', 'Sustainable Development', 'Climate Change', 'Systems Thinking', 'SDGs'],
        ['Understand sustainability concepts', 'Analyse complex systems',
         'Apply systems thinking to sustainability', 'Evaluate SDG progress'],
        ['sustainability', 'sustainable-development', 'climate', 'physical-science', 'beginner'],
        False, False, '2023-08-01',
        subcategory='Physical Science and Engineering',
    )

    c = add_course(
        'Sustainability and Development', 'sustainability-and-development',
        'umich', 'Course', 'Beginner', 'Physical Science and Engineering',
        'Approx. 14 hours', 3.5, 14.0, 4.6, 18000, 400000,
        False, True, False,
        'Jonathan Overpeck', 'Professor, University of Michigan',
        'Explore solutions to global sustainability challenges including energy, food, water, and urban systems.',
        ['Sustainability', 'Climate Change', 'Energy Policy', 'Environmental Science', 'SDGs'],
        ['Describe sustainability challenges', 'Evaluate energy solutions',
         'Analyse food and water systems', 'Understand urban sustainability'],
        ['sustainability', 'development', 'environment', 'physical-science', 'beginner', 'climate'],
        False, False, '2023-06-01',
        subcategory='Physical Science and Engineering',
    )
    add_modules(c, [
        ('Foundations of Sustainability', 'Course orientation: defining sustainability, the three pillars (environment, economy, society), and the planetary boundaries framework.', 5, 3, 1),
        ('Measuring Sustainability', 'Carbon footprint, ecological footprint, sustainability indicators, and how to measure progress against the SDGs.', 6, 4, 2),
        ('Energy Systems and Climate', 'Fossil fuels, renewables, and the transition to a low-carbon energy system.', 5, 3, 2),
        ('Food, Water, and Land', 'Agriculture, freshwater scarcity, and sustainable land use practices.', 5, 3, 1),
        ('Urban Sustainability', 'Cities as engines of sustainable development: transport, buildings, and waste systems.', 4, 2, 1),
        ('Pathways to the SDGs', 'Putting it all together: policy levers, finance, and individual action.', 4, 3, 2),
    ])

    # Task 26: Renewable Energy Specialization
    spec_re = add_course(
        'Renewable Energy and Green Building Entrepreneurship Specialization',
        'renewable-energy-green-building-specialization',
        'duke', 'Specialization', 'Beginner', 'Physical Science and Engineering',
        '4 Months', 17.4, 60.0, 4.6, 8500, 120000,
        False, True, False,
        'Bruce Usher', 'Professor, Columbia University',
        'Explore the economics and technology of renewable energy and green building. Ideal for future entrepreneurs.',
        ['Renewable Energy', 'Solar Energy', 'Wind Energy', 'Green Building', 'Energy Entrepreneurship'],
        ['Understand renewable energy technologies', 'Evaluate green building practices',
         'Develop energy business plans', 'Analyse energy markets'],
        ['renewable-energy', 'solar', 'wind', 'green-building', 'specialization', 'entrepreneurship'],
        False, False, '2023-05-01',
    )
    add_sub_courses(spec_re, [
        ('Solar Energy Basics', 'Photovoltaics and solar thermal systems.', 'Approx. 12 hours'),
        ('Wind Energy', 'Wind turbines and wind power systems.', 'Approx. 12 hours'),
        ('Batteries and the Future of Energy Storage', 'Battery technology and storage.', 'Approx. 12 hours'),
        ('Economics of Renewable Energy', 'Market analysis and business models.', 'Approx. 12 hours'),
        ('Renewable Energy Futures', 'Forward-looking survey of grid integration, hydrogen, ocean energy and policy pathways for a 100% renewable future.', 'Approx. 15 hours'),
    ])

    # Task 27: Data Visualization Specialization with project
    spec_dv = add_course(
        'Data Visualization with Tableau Specialization', 'data-visualization-tableau-specialization',
        'ucdavis', 'Specialization', 'Beginner', 'Data Science',
        '5 Months', 21.7, 80.0, 4.6, 18000, 350000,
        False, True, False,
        'Suk Brar', 'Instructor, UC Davis',
        'Learn to create compelling data visualizations with Tableau. Build a portfolio of data visualization projects.',
        ['Tableau', 'Data Visualization', 'Dashboard Design', 'Visual Analytics', 'Storytelling with Data'],
        ['Create Tableau dashboards', 'Design effective visualizations',
         'Tell stories with data', 'Build an analytics portfolio'],
        ['data-visualization', 'tableau', 'specialization', 'beginner', 'dashboard', 'project'],
        False, False, '2023-07-01',
    )
    add_sub_courses(spec_dv, [
        ('Fundamentals of Visualization with Tableau', 'Introduction to Tableau.', 'Approx. 14 hours'),
        ('Essential Design Principles for Tableau', 'Visual design best practices.', 'Approx. 14 hours'),
        ('Visual Analytics with Tableau', 'Advanced analytics features.', 'Approx. 14 hours'),
        ('Creating Dashboards and Storytelling with Tableau', 'Building interactive dashboards.', 'Approx. 14 hours'),
        ('Data Visualization with Tableau Project', 'Capstone project applying all skills.', 'Approx. 14 hours'),
    ])

    # Task 28: Guided Project Astrophysics (Advanced)
    c = add_course(
        'Analyzing Astrophysics Data with Python', 'analyzing-astrophysics-data-python',
        'jhu', 'Guided Project', 'Advanced', 'Physical Science and Engineering',
        'Less Than 2 Hours', 0.5, 1.5, 4.5, 2000, 25000,
        False, False, False,
        'Dr. Nathan Anderson', 'Research Scientist, JHU',
        'In this guided project, you will analyze real astrophysics datasets using Python, matplotlib, and astropy.',
        ['Astrophysics', 'Python', 'astropy', 'Data Analysis', 'matplotlib'],
        ['Load and process astrophysics data', 'Create astronomical plots',
         'Apply statistical methods to observational data', 'Use astropy library'],
        ['astrophysics', 'guided-project', 'advanced', 'python', 'astronomy', 'data-analysis'],
        False, False, '2024-01-01',
    )

    c = add_course(
        'Astrophysics: Exploring Exoplanets', 'astrophysics-exploring-exoplanets',
        'anu', 'Course', 'Intermediate', 'Physical Science and Engineering',
        'Approx. 21 hours', 5.3, 21.0, 4.8, 12000, 200000,
        False, True, False,
        'Paul Francis', 'Research Fellow, ANU',
        'Explore the science of exoplanets — planets outside our solar system.',
        ['Astrophysics', 'Exoplanets', 'Spectroscopy', 'Orbital Mechanics', 'Astronomy'],
        ['Understand exoplanet detection methods', 'Analyse light curves',
         'Calculate orbital parameters', 'Evaluate habitability'],
        ['astrophysics', 'exoplanets', 'astronomy', 'intermediate'],
        False, False, '2023-09-01',
    )

    # Task 32: Data Analysis (Beginner)
    c = add_course(
        'Data Analysis with Python', 'data-analysis-python',
        'ibm', 'Course', 'Beginner', 'Data Science',
        'Approx. 15 hours', 3.8, 15.0, 4.7, 45000, 800000,
        False, True, False,
        'Joseph Santarcangelo', 'Data Scientist, IBM',
        'Learn how to analyze data using Python. Topics include data preparation, simple statistical analysis, data visualization.',
        ['Data Analysis', 'Python', 'Pandas', 'NumPy', 'Matplotlib'],
        ['Load and prepare datasets', 'Perform exploratory data analysis',
         'Create visualizations', 'Build regression models'],
        ['data-analysis', 'python', 'beginner', 'pandas', 'numpy', 'ibm'],
        False, False, '2023-04-01',
    )

    c = add_course(
        'Introduction to Data Analytics', 'introduction-to-data-analytics',
        'ibm', 'Course', 'Beginner', 'Data Science',
        'Approx. 11 hours', 2.8, 11.0, 4.6, 38000, 650000,
        False, True, False,
        'Hima Vasudevan', 'Data Scientist, IBM',
        'Start your journey to become a Data Analyst. Learn about the data analysis process and the role of a data analyst.',
        ['Data Analytics', 'Excel', 'SQL', 'Python', 'Data Visualization'],
        ['Describe the data analysis process', 'Use Excel for data analysis',
         'Write basic SQL queries', 'Create simple visualizations'],
        ['data-analysis', 'analytics', 'beginner', 'introduction', 'ibm', 'excel', 'sql'],
        False, False, '2023-06-01',
    )

    # Task 33: IoT (Beginner, high rating)
    c = add_course(
        'Introduction to the Internet of Things and Embedded Systems',
        'introduction-internet-things-embedded-systems',
        'uci', 'Course', 'Beginner', 'Computer Science',
        'Approx. 15 hours', 3.8, 15.0, 4.6, 22000, 500000,
        False, True, False,
        'Ian Harris', 'Professor, UC Irvine',
        'The Internet of Things (IoT) refers to the connection of everyday objects to the internet.',
        ['Internet of Things', 'Embedded Systems', 'Arduino', 'Sensors', 'Networking'],
        ['Explain IoT concepts', 'Program Arduino microcontrollers',
         'Connect IoT devices to the internet', 'Design IoT systems'],
        ['iot', 'internet-of-things', 'embedded', 'beginner', 'arduino', 'sensors'],
        False, False, '2023-03-01',
    )

    c = add_course(
        'IoT (Internet of Things) Wireless & Cloud Computing Emerging Technologies',
        'iot-wireless-cloud-computing',
        'ubuffalo', 'Course', 'Beginner', 'Computer Science',
        'Approx. 17 hours', 4.3, 17.0, 4.7, 14000, 280000,
        False, True, False,
        'Amanpreet Kapoor', 'Assistant Professor, University at Buffalo',
        'Explore the Internet of Things from wireless communication to cloud computing integration.',
        ['IoT', 'Wireless Communication', 'Cloud Computing', 'Sensors', 'Edge Computing'],
        ['Design IoT architectures', 'Configure wireless IoT protocols',
         'Integrate IoT with cloud platforms', 'Process IoT data'],
        ['iot', 'internet-of-things', 'wireless', 'cloud', 'beginner', 'emerging-technology'],
        False, False, '2023-07-01',
    )

    # Task 36: Degrees (Master of Advanced Study in Engineering)
    c = add_course(
        'Master of Applied Data Science', 'master-applied-data-science',
        'umich', 'Degree', 'Advanced', 'Data Science',
        '12-36 Months', 52.0 * 4, 52.0 * 4 * 10, 4.8, 500, 5000,
        False, False, False,
        'Various Faculty', 'University of Michigan MADS Faculty',
        'The Master of Applied Data Science is a fully online degree from the University of Michigan.',
        ['Data Science', 'Machine Learning', 'Big Data', 'Statistical Modeling', 'Data Engineering'],
        ['Master data science techniques', 'Build production ML systems', 'Lead data science projects'],
        ['degree', 'master', 'data-science', 'online', 'michigan'],
        False, False, '2023-01-01',
        degree_type='Master',
    )

    c = add_course(
        'Master of Computer Science', 'master-computer-science-uiuc',
        'uiuc', 'Degree', 'Advanced', 'Computer Science',
        '12-24 Months', 52.0 * 2, 52.0 * 2 * 10, 4.9, 600, 8000,
        False, False, False,
        'Various Faculty', 'UIUC CS Faculty',
        'Earn a Master of Computer Science from University of Illinois Urbana-Champaign fully online.',
        ['Computer Science', 'Algorithms', 'Machine Learning', 'Distributed Systems', 'Data Engineering'],
        ['Master computer science fundamentals', 'Specialize in CS subfields', 'Complete a capstone project'],
        ['degree', 'master', 'computer-science', 'uiuc', 'online'],
        False, False, '2023-01-01',
        degree_type='Master',
    )

    c = add_course(
        'Master of Advanced Study in Engineering', 'master-advanced-study-engineering-ucberkeley',
        'columbia', 'Degree', 'Advanced', 'Physical Science and Engineering',
        '12-24 Months', 52.0 * 2, 52.0 * 2 * 10, 4.7, 200, 2000,
        False, False, False,
        'Various Faculty', 'Columbia Engineering Faculty',
        'The Master of Science in Engineering program provides advanced training in engineering disciplines.',
        ['Engineering', 'Systems Engineering', 'Project Management', 'Technical Leadership'],
        ['Apply advanced engineering principles', 'Lead engineering teams', 'Complete engineering research'],
        ['degree', 'master', 'engineering', 'advanced-study', 'mas'],
        False, False, '2023-01-01',
        degree_type='MasterAdvancedStudy',
    )
    c.application_deadline = 'May 15, 2026'

    c = add_course(
        'Master of Advanced Study in Engineering Sciences', 'mas-engineering-sciences',
        'rice', 'Degree', 'Advanced', 'Physical Science and Engineering',
        '18-24 Months', 52.0 * 2, 52.0 * 2 * 10, 4.6, 150, 1500,
        False, False, False,
        'Various Faculty', 'Rice University Faculty',
        'Rice University\'s online Master of Advanced Study covers engineering sciences with flexible scheduling.',
        ['Engineering Sciences', 'Applied Mathematics', 'Systems Design', 'Data Analysis'],
        ['Complete advanced engineering coursework', 'Conduct engineering analysis', 'Apply in professional context'],
        ['degree', 'master', 'advanced-study', 'engineering', 'mas', 'rice'],
        False, False, '2023-01-01',
        degree_type='MasterAdvancedStudy',
    )
    c.application_deadline = 'March 31, 2026'

    # Task 41: Bachelor's degrees
    c = add_course(
        'BSc Computer Science', 'bsc-computer-science-ulondon',
        'ulondon', 'Degree', 'Mixed', 'Computer Science',
        '36-72 Months', 52.0 * 6, 52.0 * 6 * 10, 4.7, 3000, 30000,
        False, False, False,
        'Various Faculty', 'University of London Faculty',
        'An internationally recognised online Bachelor\'s degree in Computer Science.',
        ['Computer Science', 'Programming', 'Algorithms', 'Databases', 'Software Engineering'],
        ['Earn a BSc in Computer Science', 'Master programming fundamentals', 'Build software systems'],
        ['degree', 'bachelor', 'computer-science', 'bsc', 'online', 'ulondon'],
        False, False, '2023-01-01',
        degree_type='Bachelor',
    )

    c = add_course(
        'Bachelor of Science in Business Administration', 'bsba-north-texas',
        'asu', 'Degree', 'Mixed', 'Business',
        '48-72 Months', 52.0 * 6, 52.0 * 6 * 10, 4.5, 2000, 15000,
        False, False, False,
        'Various Faculty', 'Arizona State University',
        'Earn a Bachelor\'s of Science in Business Administration from Arizona State University online.',
        ['Business Administration', 'Management', 'Marketing', 'Finance', 'Operations'],
        ['Develop business management skills', 'Understand financial management', 'Lead organisations'],
        ['degree', 'bachelor', 'business', 'bsba', 'asu', 'online'],
        False, False, '2023-01-01',
        degree_type='Bachelor',
    )

    c = add_course(
        'Bachelor of Applied Arts and Sciences', 'baas-utexas',
        'asu', 'Degree', 'Mixed', 'Social Sciences',
        '48-72 Months', 52.0 * 6, 52.0 * 6 * 10, 4.4, 1500, 12000,
        False, False, False,
        'Various Faculty', 'University of North Texas',
        'A flexible Bachelor of Applied Arts and Sciences designed for working adults.',
        ['Liberal Arts', 'Applied Sciences', 'Communication', 'Social Sciences', 'Interdisciplinary'],
        ['Complete a flexible bachelor\'s degree', 'Apply interdisciplinary knowledge', 'Advance your career'],
        ['degree', 'bachelor', 'arts', 'sciences', 'baas', 'online'],
        False, False, '2023-01-01',
        degree_type='Bachelor',
    )

    c = add_course(
        'Bachelor of Science in Data Science', 'bsds-arizona',
        'arizona' if 'arizona' in pid else 'asu',
        'Degree', 'Mixed', 'Data Science',
        '48-72 Months', 52.0 * 6, 52.0 * 6 * 10, 4.6, 1200, 10000,
        False, False, False,
        'Various Faculty', 'Arizona State University',
        'Earn a BS in Data Science to build skills in statistical analysis, programming, and machine learning.',
        ['Data Science', 'Statistics', 'Machine Learning', 'Data Engineering', 'Python'],
        ['Apply data science methods', 'Build ML models', 'Communicate with data'],
        ['degree', 'bachelor', 'data-science', 'bs', 'online', 'asu'],
        False, False, '2023-01-01',
        degree_type='Bachelor',
    )

    # Additional courses for broader category coverage ─────────────────────────

    # Machine Learning (for Task 17 extra results)
    c = add_course(
        'Deep Learning Specialization', 'deep-learning-specialization',
        'deeplearningai', 'Specialization', 'Intermediate', 'Data Science',
        '5 Months', 21.7, 85.0, 4.9, 220000, 3500000,
        False, True, True,
        'Andrew Ng', 'Founder, DeepLearning.AI',
        'Build neural networks and lead successful machine learning projects.',
        ['Deep Learning', 'Neural Networks', 'CNNs', 'RNNs', 'TensorFlow'],
        ['Build deep neural networks', 'Train and optimize models',
         'Apply CNNs to vision tasks', 'Build sequence models'],
        ['deep-learning', 'neural-networks', 'tensorflow', 'credit-eligible', 'intermediate'],
        True, False, '2023-01-01',
    )

    # Coursera Plus featured courses
    for title, slug, partner, cat, level, tags, rating, enrolled, is_feat, is_new, sdate in [
        ('Google Data Analytics Professional Certificate', 'google-data-analytics', 'google',
         'Data Science', 'Beginner', ['data-analytics', 'google', 'certificate', 'spreadsheets'], 4.8, 1200000, True, False, '2023-01-01'),
        ('Google Project Management: Professional Certificate', 'google-project-management', 'google',
         'Business', 'Beginner', ['project-management', 'google', 'certificate', 'agile'], 4.8, 1100000, True, False, '2023-01-01'),
        ('IBM Data Science Professional Certificate', 'ibm-data-science', 'ibm',
         'Data Science', 'Beginner', ['data-science', 'ibm', 'certificate', 'machine-learning'], 4.6, 550000, True, False, '2023-01-01'),
        ('Meta Front-End Developer Professional Certificate', 'meta-front-end-developer', 'meta',
         'Computer Science', 'Beginner', ['front-end', 'react', 'meta', 'certificate', 'javascript'], 4.7, 280000, True, False, '2023-01-01'),
        ('Google UX Design Professional Certificate', 'google-ux-design', 'google',
         'Business', 'Beginner', ['ux-design', 'google', 'design', 'figma'], 4.8, 380000, True, False, '2023-01-01'),
        ('Microsoft Azure Fundamentals AZ-900 Exam Prep', 'microsoft-azure-fundamentals', 'microsoft',
         'Information Technology', 'Beginner', ['azure', 'cloud', 'microsoft', 'certification', 'credit-eligible'], 4.7, 220000, False, True, '2024-03-01'),
        ('AWS Cloud Technical Essentials', 'aws-cloud-technical-essentials', 'aws',
         'Information Technology', 'Beginner', ['aws', 'cloud', 'amazon', 'credit-eligible'], 4.7, 180000, False, True, '2024-02-01'),
        ('Introduction to Generative AI', 'introduction-to-generative-ai', 'google',
         'Computer Science', 'Beginner', ['generative-ai', 'google', 'llm', 'ai', 'free'], 4.6, 850000, True, True, '2024-04-01'),
        ('What is Data Science?', 'what-is-data-science', 'ibm',
         'Data Science', 'Beginner', ['data-science', 'introduction', 'beginner', 'free'], 4.7, 750000, False, False, '2023-01-01'),
        ('The Science of Well-Being', 'the-science-of-well-being', 'yale',
         'Personal Development', 'Beginner', ['well-being', 'happiness', 'yale', 'free', 'psychology'], 4.9, 4000000, True, False, '2023-01-01'),
        ('Learning How to Learn', 'learning-how-to-learn', 'ucsd',
         'Personal Development', 'Beginner', ['learning', 'productivity', 'free', 'memory', 'science-of-learning'], 4.8, 2800000, True, False, '2023-01-01'),
        ('Financial Markets', 'financial-markets', 'yale',
         'Business', 'Beginner', ['finance', 'financial-markets', 'yale', 'stocks', 'bonds', 'free'], 4.8, 1600000, True, False, '2023-01-01'),
    ]:
        is_free_course = 'free' in tags
        add_course(
            title, slug, partner, 'Course', level, cat,
            'Approx. 10 hours', 2.5, 10.0,
            rating, int(rating * 10000), enrolled,
            is_free_course, True, 'credit-eligible' in tags,
            'Course Instructors', partner.title(),
            f'{title} — a popular Coursera course.',
            tags, [f'Gain skills in {t}' for t in tags[:3]], tags,
            is_feat, is_new, sdate,
        )

    db.session.commit()
    print(f"Seeded {Course.query.count()} courses, {Partner.query.count()} partners")


# ─── Benchmark users seed ─────────────────────────────────────────────────────

def seed_benchmark_users():
    """Idempotent. Creates 4 benchmark users with enrollments, saved courses,
    and reviews. Safe to call multiple times — skips if users already exist."""
    if User.query.filter_by(email='alice.j@test.com').first():
        return  # already seeded

    def _get_course(slug_fragment):
        return Course.query.filter(Course.slug.ilike(f'%{slug_fragment}%')).first()

    def _get_course_title(title_fragment):
        return Course.query.filter(Course.title.ilike(f'%{title_fragment}%')).first()

    # ── User definitions ──────────────────────────────────────────────────────
    users_data = [
        ('Alice Johnson', 'alice.j@test.com', 'TestPass123!'),
        ('Bob Chen', 'bob.c@test.com', 'TestPass123!'),
        ('Carol Davis', 'carol.d@test.com', 'TestPass123!'),
        ('David Kim', 'david.k@test.com', 'TestPass123!'),
    ]
    users = {}
    for name, email, pw in users_data:
        u = User(name=name, email=email)
        u.set_password(pw)
        db.session.add(u)
        db.session.flush()
        users[email] = u

    # ── Alice: Python + Data Science focus, beginner ──────────────────────────
    alice = users['alice.j@test.com']

    # Enrollments
    alice_enrolled_slugs = [
        'python-for-everybody',
        'python-for-data-science-ai-development',
        'data-analysis-python',
        'introduction-to-data-analytics',
        'machine-learning-specialization',
    ]
    alice_enrolled_ids = []
    for sl in alice_enrolled_slugs:
        c = _get_course(sl)
        if c:
            e = Enrollment(user_id=alice.id, course_id=c.id, progress=random.randint(10, 80))
            db.session.add(e)
            alice_enrolled_ids.append(c.id)

    # Saved courses
    alice_saved_slugs = [
        'deep-learning-specialization',
        'machine-learning-python',
        'python-3-programming-specialization',
        'introduction-generative-ai',
        'supervised-machine',
    ]
    for sl in alice_saved_slugs:
        c = _get_course(sl)
        if c and c.id not in alice_enrolled_ids:
            db.session.add(SavedCourse(user_id=alice.id, course_id=c.id))

    # Reviews for enrolled courses
    alice_reviews = [
        ('python-for-everybody', 5.0, 'Excellent course for beginners. Clear explanations and great exercises.'),
        ('data-analysis-python', 4.5, 'Very practical. The pandas sections were especially useful for my work.'),
        ('machine-learning-specialization', 5.0, 'Andrew Ng is a fantastic teacher. Best ML course available online.'),
    ]
    for slug_frag, rating, body in alice_reviews:
        c = _get_course(slug_frag)
        if c:
            db.session.add(Review(user_id=alice.id, course_id=c.id,
                                  rating=rating, body=body,
                                  created_at=datetime.utcnow() - timedelta(days=random.randint(10, 90))))

    # ── Bob: Web Dev + JavaScript focus, intermediate ─────────────────────────
    bob = users['bob.c@test.com']

    bob_enrolled_slugs = [
        'html-css-javascript',
        'javascript-algorithms',
        'programming-javascript',
        'meta-front-end',
        'object-oriented-programming-java',
    ]
    bob_enrolled_ids = []
    for sl in bob_enrolled_slugs:
        c = _get_course(sl)
        if c:
            e = Enrollment(user_id=bob.id, course_id=c.id, progress=random.randint(20, 95))
            db.session.add(e)
            bob_enrolled_ids.append(c.id)

    bob_saved_slugs = [
        'react' if _get_course('react') else 'javascript-algorithms',
        'python-for-everybody',
        'introduction-generative-ai',
        'introduction-to-project-management',
        'google-ux-design',
    ]
    for sl in bob_saved_slugs:
        c = _get_course(sl)
        if c and c.id not in bob_enrolled_ids:
            db.session.add(SavedCourse(user_id=bob.id, course_id=c.id))

    bob_reviews = [
        ('html-css-javascript', 4.5, 'Great foundation course. Covers HTML, CSS and JS in a balanced way.'),
        ('meta-front-end', 5.0, 'Meta certificate is well-recognized. The React sections are outstanding.'),
    ]
    for slug_frag, rating, body in bob_reviews:
        c = _get_course(slug_frag)
        if c:
            db.session.add(Review(user_id=bob.id, course_id=c.id,
                                  rating=rating, body=body,
                                  created_at=datetime.utcnow() - timedelta(days=random.randint(5, 60))))

    # ── Carol: Business + Project Management + HR focus, beginner ────────────
    carol = users['carol.d@test.com']

    carol_enrolled_slugs = [
        'introduction-to-project-management',
        'google-project-management',
        'business-process-management',
        'introduction-to-finance-the-basics',
        'fundamentals-digital-marketing',
    ]
    carol_enrolled_ids = []
    for sl in carol_enrolled_slugs:
        c = _get_course(sl)
        if c:
            e = Enrollment(user_id=carol.id, course_id=c.id, progress=random.randint(30, 100))
            db.session.add(e)
            carol_enrolled_ids.append(c.id)

    carol_saved_slugs = [
        'human-resource-management-specialization',
        'engineering-project-management-specialization',
        'digital-marketing-specialization',
        'google-ux-design',
        'agile-project-management',
    ]
    for sl in carol_saved_slugs:
        c = _get_course(sl)
        if c and c.id not in carol_enrolled_ids:
            db.session.add(SavedCourse(user_id=carol.id, course_id=c.id))

    carol_reviews = [
        ('introduction-to-project-management', 5.0, 'Perfect for aspiring project managers. Great real-world examples.'),
        ('fundamentals-digital-marketing', 4.5, 'Good overview of digital marketing. Free and comprehensive.'),
        ('introduction-to-finance-the-basics', 4.0, 'Solid finance fundamentals. A bit theoretical but well taught.'),
    ]
    for slug_frag, rating, body in carol_reviews:
        c = _get_course(slug_frag)
        if c:
            db.session.add(Review(user_id=carol.id, course_id=c.id,
                                  rating=rating, body=body,
                                  created_at=datetime.utcnow() - timedelta(days=random.randint(15, 120))))

    # ── David: AI/ML + Advanced topics focus, intermediate/advanced ───────────
    david = users['david.k@test.com']

    david_enrolled_slugs = [
        'machine-learning-specialization',
        'deep-learning-specialization',
        'ai-for-medicine',
        'reinforcement-learning-specialization',
        'machine-learning-python',
    ]
    david_enrolled_ids = []
    for sl in david_enrolled_slugs:
        c = _get_course(sl)
        if c:
            e = Enrollment(user_id=david.id, course_id=c.id, progress=random.randint(40, 100))
            db.session.add(e)
            david_enrolled_ids.append(c.id)

    david_saved_slugs = [
        'artificial-intelligence-healthcare',
        'applied-data-science-python',
        'fundamentals-reinforcement-learning',
        'trustworthy-ai',
        'introduction-generative-ai',
    ]
    for sl in david_saved_slugs:
        c = _get_course(sl)
        if c and c.id not in david_enrolled_ids:
            db.session.add(SavedCourse(user_id=david.id, course_id=c.id))

    david_reviews = [
        ('machine-learning-specialization', 5.0, 'The best ML course I have taken. Andrew Ng explains complex concepts clearly.'),
        ('deep-learning-specialization', 5.0, 'Excellent deep dive into neural networks. Highly recommended for ML practitioners.'),
        ('ai-for-medicine', 4.5, 'Fascinating application of AI. The medical imaging sections are exceptional.'),
        ('reinforcement-learning-specialization', 4.0, 'Challenging but rewarding. Good balance of theory and practice.'),
    ]
    for slug_frag, rating, body in david_reviews:
        c = _get_course(slug_frag)
        if c:
            db.session.add(Review(user_id=david.id, course_id=c.id,
                                  rating=rating, body=body,
                                  created_at=datetime.utcnow() - timedelta(days=random.randint(5, 180))))

    db.session.commit()
    print(f"Seeded benchmark users: {[u.email for u in users.values()]}")



def run_startup_migrations():
    """Idempotent schema + data migrations run at startup."""
    import sqlite3 as _sqlite3
    db_path = os.path.join(BASE_DIR, 'instance', 'coursera.db')
    if not os.path.exists(db_path):
        return
    conn = _sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cols = {r[1] for r in cur.execute("PRAGMA table_info(courses)").fetchall()}
        if 'testimonials_json' not in cols:
            cur.execute("ALTER TABLE courses ADD COLUMN testimonials_json TEXT DEFAULT '[]'")
            conn.commit()
            print("  + courses.testimonials_json")
        cols = {r[1] for r in cur.execute("PRAGMA table_info(partners)").fetchall()}
        # country already exists — no-op, defensive check
    finally:
        conn.close()


def seed_testimonials_and_extras():
    """Seed testimonials for priority specializations, add Canva partner,
    and ensure instructor fields are consistent. Idempotent."""
    # Add Canva as an Australian partner if missing
    if not Partner.query.filter_by(slug='canva').first():
        db.session.add(Partner(name='Canva', slug='canva', country='Australia',
                               partner_type='company', short_name='Canva'))
        db.session.commit()

    # Seed testimonials for Specializations (and Professional Certificates)
    # that currently have no testimonials. We synthesize 3 per course using the
    # existing Review rows so everything is self-consistent and on-page.
    targets = Course.query.filter(
        Course.course_type.in_(['Specialization', 'Professional Certificate', 'Course'])
    ).all()
    updated = 0
    for c in targets:
        existing = c.get_testimonials()
        if existing:
            continue
        # Pull up to 3 real reviews from the DB for this course
        rows = Review.query.filter_by(course_id=c.id).order_by(
            Review.rating.desc()).limit(3).all()
        testimonials = []
        for r in rows:
            user = User.query.get(r.user_id)
            if not user:
                continue
            date_str = r.created_at.strftime('%b %Y') if r.created_at else ''
            testimonials.append({
                'quote': r.body,
                'name': user.name,
                'role': 'Learner',
                'date': date_str,
            })
        # If there aren't enough reviews, synthesize based on course title
        if len(testimonials) < 2:
            fallback_names = [
                ('Priya Sharma', 'Software Engineer'),
                ('Marcus Chen', 'Data Analyst'),
                ('Elena Rossi', 'Project Lead'),
            ]
            fallback_quotes = [
                f"{c.title} gave me a clear, practical foundation. I finished the program confident I could apply these skills at work.",
                f"A well-structured {(c.course_type or 'course').lower()}. The assignments in {c.title} pushed me to think, and the instructor feedback was excellent.",
                f"I recommend {c.title} to anyone starting out in {(c.category or 'this field').lower()} — the pace is steady and the examples are real-world.",
            ]
            for i in range(min(3, 3 - len(testimonials))):
                testimonials.append({
                    'quote': fallback_quotes[i],
                    'name': fallback_names[i][0],
                    'role': fallback_names[i][1],
                    'date': ['Nov 2025', 'Oct 2025', 'Sep 2025'][i],
                })
        c.testimonials_json = json.dumps(testimonials[:3])
        updated += 1
    if updated:
        db.session.commit()
        print(f"  + seeded testimonials on {updated} courses")

    # Ensure Gautam Kaul teaches more than one course (Task 16).
    # If only one course exists for him, add a second so "other courses" is answerable.
    kaul_courses = Course.query.filter(Course.instructor.like('%Gautam Kaul%')).all()
    if len(kaul_courses) < 2:
        umich = Partner.query.filter_by(slug='umich').first()
        new_slug = 'finance-for-non-finance-professionals'
        if not Course.query.filter_by(slug=new_slug).first():
            c2 = Course(
                title='Finance for Non-Finance Professionals',
                slug=new_slug,
                partner_id=umich.id if umich else None,
                course_type='Course',
                level='Beginner',
                category='Business',
                subcategory='Finance',
                duration_text='Approx. 9 hours',
                duration_weeks=2.0, duration_hours=9.0,
                rating=4.7, review_count=9800, enrolled_count=210000,
                is_free=False, has_certificate=True, credit_eligible=False,
                instructor='Gautam Kaul',
                instructor_title='Professor of Finance, University of Michigan',
                description=(
                    'A concise primer for professionals without a finance background. '
                    'Covers core principles of valuation, risk, and capital markets.'),
                skills=json.dumps(['Finance', 'Valuation', 'Risk', 'Capital Markets']),
                what_you_learn=json.dumps([
                    'Explain time value of money',
                    'Assess financial risk',
                    'Interpret corporate finance decisions',
                ]),
                feature_tags=json.dumps(['finance', 'non-finance', 'beginner', 'umich']),
                is_featured=False, is_new=False,
                sort_date='2024-08-01',
                color_class='cat-biz',
                testimonials_json=json.dumps([]),
            )
            db.session.add(c2)
            db.session.flush()
            # Backfill modules so this course matches the rest of the catalog.
            for w, (title, desc, vids, reads, quizzes) in enumerate([
                ('Time Value of Money', 'Discounting, compounding, and the mechanics of valuing future cash flows.', 4, 2, 1),
                ('Risk and Return', 'How risk is priced, the role of diversification, and CAPM intuition.', 4, 2, 1),
                ('Corporate Finance Decisions', 'NPV, IRR, capital budgeting and how firms allocate capital.', 4, 2, 1),
            ], 1):
                db.session.add(CourseModule(course_id=c2.id, week_number=w,
                    title=title, description=desc,
                    videos_count=vids, readings_count=reads, quizzes_count=quizzes,
                    video_titles=json.dumps([f'Lesson {w}.1: {title}', f'Lesson {w}.2: Worked examples'])))
            db.session.commit()
            print("  + added Gautam Kaul second course")


with app.app_context():
    # Schema migration must run BEFORE ORM queries hit the new column.
    # (sqlite `ALTER TABLE ... ADD COLUMN` on an existing DB.)
    # db.create_all() is a no-op for existing tables so run migration first
    # but we need the file to exist. Let create_all build fresh dbs; then
    # migrate; then seed.
    db.create_all()
    run_startup_migrations()
    seed_database()
    seed_benchmark_users()
    seed_testimonials_and_extras()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
