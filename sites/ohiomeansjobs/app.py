#!/usr/bin/env python3
"""OhioMeansJobs mirror — Flask application.

Mirrors https://ohiomeansjobs.ohio.gov/ (Ohio's official job portal:
audience hubs, job-search engine powered by the OhioMeansJobs board,
career tools, county job centers, news, help center) using real content
captured from the upstream site on 2026-09-24.

Route and URL patterns follow the upstream portal (`/job-seekers/...`,
`/for-employers`, `/for-students`, ...) and the upstream job board
(`Search.aspx`-style query parameters: tjt, cnme, rad, sort, pg,
omjindustry, saltyp, lv, jtype).
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlsplit
import re
from datetime import datetime

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config['SECRET_KEY'] = 'ohiomeansjobs-mirror-dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'OMJ_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'ohiomeansjobs.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'account_login'
login_manager.login_message = 'Please sign in to access your OhioMeansJobs account.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# The mirror is a snapshot of the upstream site taken on 2026-09-24.
MIRROR_TODAY = datetime(2026, 9, 24)
JOBS_PER_PAGE = 10
MAX_COVER_LETTERS = 5

# ------------------------------------------------------------------ models


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False, default='')
    last_name = db.Column(db.String(80), nullable=False, default='')
    phone = db.Column(db.String(30), default='')
    zip_code = db.Column(db.String(12), default='')
    city = db.Column(db.String(80), default='')
    military_status = db.Column(db.String(60), default='')
    employment_status = db.Column(db.String(60), default='')
    target_job_title = db.Column(db.String(120), default='')
    career_level = db.Column(db.String(60), default='')
    education = db.Column(db.String(80), default='')
    willing_relocate = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    jobid = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(160), nullable=False)
    company_slug = db.Column(db.String(180), nullable=False)
    city = db.Column(db.String(120), default='')
    job_types = db.Column(db.String(160), default='')   # 'Full-Time,Permanent'
    ref_code = db.Column(db.String(60), default='')
    description = db.Column(db.Text, default='')
    posted_date = db.Column(db.String(10), default='')  # ISO date
    industry_code = db.Column(db.String(4), default='')
    salary_band = db.Column(db.Integer, default=0)      # 1..5 (saltyp)
    education_level = db.Column(db.Integer, default=0)   # lv code
    certifications = db.Column(db.String(120), default='')
    remote = db.Column(db.Boolean, default=False)
    internship = db.Column(db.Boolean, default=False)
    apply_url = db.Column(db.String(400), default='')

    @property
    def type_list(self):
        return [t for t in (self.job_types or '').split(',') if t]

    @property
    def cert_list(self):
        return [int(c) for c in (self.certifications or '').split(',') if c]

    @property
    def days_old(self):
        try:
            posted = datetime.strptime(self.posted_date, '%Y-%m-%d')
            return (MIRROR_TODAY - posted).days
        except Exception:
            return None

    def snippet(self, length=260):
        text = re.sub(r'\s+', ' ', self.description or '').strip()
        return text[:length].rsplit(' ', 1)[0] + '…' if len(text) > length else text


class SavedJob(db.Model):
    __tablename__ = 'saved_jobs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    job = db.relationship('Job')
    __table_args__ = (db.UniqueConstraint('user_id', 'job_id', name='uq_saved_job'),)


class Application(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(40), default='Submitted')
    first_name = db.Column(db.String(80), default='')
    last_name = db.Column(db.String(80), default='')
    email = db.Column(db.String(120), default='')
    phone = db.Column(db.String(30), default='')
    cover_letter_id = db.Column(db.Integer, nullable=True)
    job = db.relationship('Job')
    __table_args__ = (db.UniqueConstraint('user_id', 'job_id', name='uq_application'),)


class SavedSearch(db.Model):
    __tablename__ = 'saved_searches'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    query_params = db.Column(db.Text, nullable=False)   # JSON dict of search args
    alerts_enabled = db.Column(db.Boolean, default=True)
    frequency = db.Column(db.String(20), default='Daily')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def params(self):
        try:
            return json.loads(self.query_params)
        except Exception:
            return {}


class CoverLetter(db.Model):
    __tablename__ = 'cover_letters'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, default='')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class Resume(db.Model):
    __tablename__ = 'resumes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(120), default='')
    summary = db.Column(db.Text, default='')
    skills = db.Column(db.Text, default='')            # comma separated
    experience = db.Column(db.Text, default='')
    active = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def skill_list(self):
        return [s.strip() for s in (self.skills or '').split(',') if s.strip()]


class CareerPlanTask(db.Model):
    __tablename__ = 'career_plan_tasks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    deadline = db.Column(db.String(12), default='')    # ISO date
    done = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class NewsItem(db.Model):
    __tablename__ = 'news_items'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    teaser = db.Column(db.String(400), default='')
    body = db.Column(db.Text, default='')              # JSON list of paragraphs
    published_date = db.Column(db.String(10), default='')
    topic = db.Column(db.String(60), default='')

    @property
    def paragraphs(self):
        try:
            return [re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)), p).replace('\\"', '"') for p in json.loads(self.body)]
        except Exception:
            return []


class JobCenter(db.Model):
    __tablename__ = 'job_centers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    county = db.Column(db.String(80), default='')
    address = db.Column(db.String(240), default='')
    slug = db.Column(db.String(180), default='')


class HelpArticle(db.Model):
    __tablename__ = 'help_articles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    section = db.Column(db.String(60), nullable=False)  # job-seeker/employers/education/common
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default='')               # JSON list of paragraphs

    @property
    def paragraphs(self):
        try:
            return [re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)), p).replace('\\"', '"') for p in json.loads(self.body)]
        except Exception:
            return []


class StateAgency(db.Model):
    __tablename__ = 'state_agencies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), default='')
    logo = db.Column(db.String(200), default='')


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), default='')
    email = db.Column(db.String(120), default='')
    subject = db.Column(db.String(200), default='')
    message = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CareerQuizResult(db.Model):
    __tablename__ = 'career_quiz_results'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    answers = db.Column(db.Text, default='')            # JSON list of trait codes
    scores = db.Column(db.Text, default='')             # JSON dict trait->count
    top_trait = db.Column(db.String(40), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ------------------------------------------------------- search & filtering

STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
              'or', 'is', 'it', 'by', 'with', 'near', 'oh', 'ohio', 'jobs',
              'job'}

INDUSTRY_NAMES = {
    '11': 'Agriculture, Forestry, Fishing, and Hunting',
    '22': 'Utilities',
    '23': 'Construction',
    '31': 'Manufacturing',
    '42': 'Wholesale Trade',
    '44': 'Retail Trade',
    '48': 'Transportation and Warehousing',
    '51': 'Information',
    '52': 'Finance and Insurance',
    '53': 'Real Estate and Rental and Leasing',
    '54': 'Professional, Scientific, and Technical Services',
    '55': 'Management of Companies and Enterprises',
    '56': 'Administrative and Support Services',
    '61': 'Educational Services',
    '62': 'Health Care and Social Assistance',
    '71': 'Arts, Entertainment, and Recreation',
    '72': 'Accommodation and Food Services',
    '81': 'Other Services',
    '92': 'Government',
}
SALARY_BAND_NAMES = {
    1: 'Entry Level Jobs (less than $30K)',
    2: 'Middle Income Jobs ($30K-$49K)',
    3: 'Upper Middle Income Jobs ($50K-$79K)',
    4: 'High Income Jobs ($80K-$99K)',
    5: 'Six Figure Jobs (more than $100K)',
}
EDUCATION_NAMES = {
    1: 'Less than high school',
    2: 'Doctoral or professional degree',
    3: "Master's degree",
    4: 'Some college, no degree',
    5: "Bachelor's degree",
    6: "Associate's degree",
    7: 'Postsecondary nondegree award',
    8: 'High school diploma or equivalent',
}
CERTIFICATION_NAMES = {
    25503: 'Certified Registered Nurse',
    24713: 'Basic Life Support',
    24612: 'Advanced Cardiac Life Support',
    25001: 'Certification in Cardiopulmonary Resuscitation',
    51586: 'Pediatric Advanced Life Support',
    25315: 'Licensed Practical Nurse',
    28389: 'Certified in Long Term Care',
    33723: "Driver's License",
    24696: 'Board Certified',
}

# Ohio city coordinates for the radius filter (real geography).
CITY_COORDS = {
    'columbus': (39.9612, -82.9988), 'cleveland': (41.4993, -81.6944),
    'cincinnati': (39.1031, -84.5120), 'akron': (41.0814, -81.5190),
    'toledo': (41.6528, -83.5379), 'dayton': (39.7589, -84.1916),
    'youngstown': (41.0998, -80.6495), 'lima': (40.7410, -84.1050),
    'canton': (40.7989, -81.3784), 'findlay': (41.0442, -83.6499),
    'westerville': (40.1262, -82.9291), 'mentor': (41.6662, -81.3396),
    'newark': (40.0581, -82.4013), 'marion': (40.5887, -83.1285),
    'dover': (40.5223, -81.4743), 'stow': (41.1595, -81.4404),
    'mount vernon': (40.3931, -82.4816), 'bowling green': (41.3748, -83.6513),
    'mansfield': (40.7584, -82.5154), 'springfield': (39.9242, -83.8088),
    'hamilton': (39.3995, -84.5613), 'kettering': (39.6895, -84.1688),
    'mason': (39.3601, -84.3100), 'beavercreek': (39.7087, -84.0641),
    'dublin': (40.0992, -83.1141), 'reynoldsburg': (39.9548, -82.8121),
    'beachwood': (41.4820, -81.5043), 'warren': (41.2376, -80.8187),
    'steubenville': (40.3698, -80.6340), 'chillicothe': (39.3331, -82.9824),
    'zanesville': (39.9403, -82.0132), 'athens': (39.3292, -82.1013),
    'salem': (40.9009, -80.8565), 'tiffin': (41.1145, -83.1777),
    'portsmouth': (38.7317, -82.9977), 'clyde': (41.3037, -82.9755),
    'gallipolis': (38.8095, -82.1660), 'wauseon': (41.2189, -84.1374),
    'cambridge': (40.0312, -81.5885), 'delaware': (40.2989, -83.0680),
    'bryan': (41.4744, -84.5522), 'van wert': (40.8689, -84.5872),
    'upper sandusky': (40.8267, -83.2810), 'millersburg': (40.5562, -81.9182),
    'wilmington': (39.4454, -83.8278), 'xenia': (39.6847, -83.9397),
    'lebanon': (39.4273, -84.2100), 'sidney': (40.2845, -84.1555),
    'fremont': (41.3439, -83.1219), 'elyria': (41.3684, -82.1076),
    'lakewood': (41.4775, -81.8046), 'parma': (41.4047, -81.7385),
    'euclid': (41.5931, -81.5194), ' lorain': (41.4528, -82.1824),
    'lorain': (41.4528, -82.1824), 'rootstown': (41.0253, -81.2348),
    'ashland': (40.8698, -82.3182), 'ashtabula': (41.8758, -80.7912),
    'hillsboro': (39.3431, -83.6117), 'logan': (39.5398, -82.4072),
    'napoleon': (41.3870, -84.6250), 'lucasville': (38.8817, -82.8419),
    'marysville': (40.2365, -83.3671), 'urbana': (40.1081, -83.7524),
    'bellefontaine': (40.3617, -83.7597), 'ironton': (38.5307, -82.6859),
    'piketon': (39.0698, -83.0088), 'bucyrus': (40.8070, -82.9743),
    'kent': (41.1537, -81.3579), 'twinsburg': (41.3045, -81.4407),
    'mayfield heights': (41.5167, -81.4523), 'middleburg heights': (41.3712, -81.8126),
    'strongsville': (41.3134, -81.8357), 'north canton': (40.8756, -81.4023),
    'massillon': (40.7967, -81.5210), 'boardman': (41.0245, -80.6640),
    'lisbon': (40.7720, -80.7676), 'wooster': (40.8051, -81.9352),
    'cadiz': (40.4995, -80.9982), 'martins ferry': (40.1001, -80.7256),
    'bellville': (40.6200, -82.5096), 'gahanna': (39.9720, -82.8550),
    'hilliard': (39.9525, -83.1582), 'grove city': (39.8709, -83.0930),
    'pickerington': (39.7645, -82.7535), 'groveport': (39.8856, -82.8777),
    'powell': (40.1589, -83.0751), 'lewis center': (40.2320, -83.0140),
    'blacklick': (39.9150, -82.8463), 'carroll': (39.7995, -82.7055),
    'circleville': (39.6006, -82.9460), 'washington court house': (39.5365, -83.4360),
    'waverly': (39.1265, -82.9850), 'mcconnelsville': (39.6495, -81.8510),
    'coldwater': (40.4817, -84.6310), 'celina': (40.5495, -84.5705),
    'defiance': (41.2870, -84.3610), 'bucyrus oh': (40.8070, -82.9743),
}

RADIUS_OPTIONS = [('Exact location only', 0), ('5 miles', 5), ('10 miles', 10),
                  ('20 miles', 20), ('30 miles', 30), ('40 miles', 40),
                  ('50 miles', 50), ('100 miles', 100), ('8000 miles', 8000)]


def _city_key(city):
    return (city or '').split(',')[0].strip().lower().rstrip('.')


def _city_coord(city):
    return CITY_COORDS.get(_city_key(city))


def _haversine(a, b):
    import math
    lat1, lon1 = a
    lat2, lon2 = b
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def tokenize(query):
    tokens = [t.lower() for t in re.split(r'\W+', query or '')]
    return [t for t in tokens if t and t not in STOP_WORDS and len(t) > 1]


def search_jobs(args):
    """Scored token-overlap search with the upstream filter surface.

    Returns (jobs, total_matches_before_city_radius) — pagination applied by
    the caller via `pg`.
    """
    tjt = (args.get('tjt') or '').strip()
    keywords = (args.get('keywords') or '').strip()
    location = (args.get('cnme') or args.get('location') or '').strip()
    radius = args.get('rad', '20')
    try:
        radius = int(float(radius))
    except (TypeError, ValueError):
        radius = 20
    sort = args.get('sort', 'date')
    industry = args.get('omjindustry') or ''
    salary = args.get('saltyp') or ''
    edu = args.get('lv') or ''
    jtype = args.get('jtype') or ''
    company = (args.get('cn') or '').strip()
    cert = args.get('cert') or ''
    remote_only = args.get('remote') in ('1', 'on', 'true')
    internship_only = args.get('internship') in ('1', 'on', 'true')

    query_text = ' '.join(t for t in (tjt, keywords) if t)
    tokens = tokenize(query_text)

    base = Job.query
    if industry:
        base = base.filter(Job.industry_code == str(industry))
    if salary:
        base = base.filter(Job.salary_band == int(salary))
    if edu:
        base = base.filter(Job.education_level == int(edu))
    if company:
        base = base.filter(Job.company.ilike(f'%{company}%'))
    if jtype:
        base = base.filter(Job.job_types.ilike(f'%{jtype}%'))
    if cert:
        base = base.filter(Job.certifications.ilike(f'%{cert}%'))
    if remote_only:
        base = base.filter(Job.remote.is_(True))
    if internship_only:
        base = base.filter(Job.internship.is_(True))

    candidates = base.all()

    # scored token overlap (title + company + description + city)
    if tokens:
        scored = []
        for job in candidates:
            text = ' '.join([job.title, job.company, job.description, job.city]).lower()
            score = sum(1 for t in tokens if t in text)
            if score:
                scored.append((job, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0].jobid))
        candidates = [job for job, _ in scored]

    # location + radius filter
    if location:
        target = _city_coord(location)
        if target:
            if radius <= 0:
                candidates = [j for j in candidates if _city_key(j.city) == _city_key(location)]
            else:
                keep = []
                for j in candidates:
                    coord = _city_coord(j.city)
                    if coord and _haversine(target, coord) <= radius:
                        keep.append(j)
                    elif not coord and _city_key(j.city) == _city_key(location):
                        keep.append(j)
                candidates = keep
        else:
            # unknown city: fall back to substring match (partial city names)
            low = location.lower()
            candidates = [j for j in candidates if low in (j.city or '').lower()]

    # sort
    if sort == 'relevance':
        pass  # already scored order when tokens present; else stable
    else:  # date (default)
        candidates.sort(key=lambda j: (j.posted_date or '', j.jobid), reverse=True)

    return candidates


def build_facets(jobs):
    """Facet counts computed over the current result set (upstream parity)."""
    industry, salary, edu, location_facet, jtype_facet, cert_facet = {}, {}, {}, {}, {}, {}
    for j in jobs:
        if j.industry_code:
            industry[j.industry_code] = industry.get(j.industry_code, 0) + 1
        if j.salary_band:
            salary[j.salary_band] = salary.get(j.salary_band, 0) + 1
        if j.education_level:
            edu[j.education_level] = edu.get(j.education_level, 0) + 1
        key = _city_key(j.city)
        if key:
            location_facet[key] = location_facet.get(key, 0) + 1
        for t in j.type_list:
            jtype_facet[t] = jtype_facet.get(t, 0) + 1
        for c in j.cert_list:
            cert_facet[c] = cert_facet.get(c, 0) + 1

    def sort_desc(d):
        return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))

    return {
        'industry': sort_desc(industry),
        'salary': sort_desc(salary),
        'education': sort_desc(edu),
        'location': sort_desc(location_facet),
        'job_type': sort_desc(jtype_facet),
        'certification': sort_desc(cert_facet),
    }


def search_url(args, **overrides):
    params = {k: v for k, v in args.items() if v not in (None, '', 'None')}
    params.update(overrides)
    params = {k: v for k, v in params.items() if v not in (None, '', 'None')}
    qs = '&'.join(f'{k}={v}' for k, v in params.items())
    return url_for('jobs_search') + ('?' + qs if qs else '')


# ------------------------------------------------------------------ routes

def valid_password(value):
    return (8 <= len(value) <= 20 and any(c.isdigit() for c in value)
            and any(c.isupper() for c in value) and any(c.islower() for c in value)
            and any(not c.isalnum() and not c.isspace() for c in value)
            and not any(c in value for c in "'@-\"<"))


def local_redirect(target, fallback):
    """Accept only paths on this mirror; browsers normalize backslashes."""
    if target and target.startswith('/') and not target.startswith('//') and '\\' not in target and not any(ord(c) < 32 for c in target):
        parts = urlsplit(target)
        if not parts.scheme and not parts.netloc:
            return target
    return fallback


@app.route('/')
def home():
    total_jobs = Job.query.count()
    over_50k = Job.query.filter(Job.salary_band >= 3).count()
    internships = Job.query.filter(Job.internship.is_(True)).count()
    recent = Job.query.order_by(Job.posted_date.desc(), Job.jobid.desc()).limit(5).all()
    news = NewsItem.query.order_by(NewsItem.published_date.desc()).limit(3).all()
    return render_template('home.html', total_jobs=total_jobs, over_50k=over_50k,
                           internships=internships, recent=recent, news=news,
                           as_of='September 21, 2026')


@app.route('/job-seekers')
def job_seekers():
    return render_template('job_seekers.html')


@app.route('/job-seekers/find-a-job')
def find_a_job():
    return render_template('find_a_job.html')


@app.route('/job-seekers/build-your-career')
def build_your_career():
    return render_template('build_your_career.html')


@app.route('/job-seekers/practice-your-skills')
def practice_your_skills():
    return render_template('practice_skills.html')


@app.route('/job-seekers/learn-about-benefits')
def learn_about_benefits():
    return render_template('learn_benefits.html')


@app.route('/jobs/search')
def jobs_search():
    args = request.args.to_dict()
    try:
        page = max(1, int(args.get('pg', '1')))
    except ValueError:
        page = 1
    jobs = search_jobs(args)
    total = len(jobs)
    start = (page - 1) * JOBS_PER_PAGE
    page_jobs = jobs[start:start + JOBS_PER_PAGE]
    facets = build_facets(jobs)
    saved_ids = set()
    applied_ids = set()
    if current_user.is_authenticated:
        saved_ids = {sj.job_id for sj in SavedJob.query.filter_by(user_id=current_user.id).all()}
        applied_ids = {a.job_id for a in Application.query.filter_by(user_id=current_user.id).all()}
    total_pages = max(1, -(-total // JOBS_PER_PAGE))
    search_params_json = json.dumps({k: v for k, v in args.items() if k != 'pg'})
    return render_template('jobs_search.html', jobs=page_jobs, total=total, page=page,
                           search_params_json=search_params_json,
                           total_pages=total_pages, facets=facets, args=args,
                           saved_ids=saved_ids, applied_ids=applied_ids,
                           industry_names=INDUSTRY_NAMES,
                           salary_names=SALARY_BAND_NAMES,
                           education_names=EDUCATION_NAMES,
                           cert_names=CERTIFICATION_NAMES,
                           radius_options=RADIUS_OPTIONS,
                           search_url=search_url)


@app.route('/jobs/view/<jobid>')
def job_detail(jobid):
    job = Job.query.filter_by(jobid=jobid).first_or_404()
    saved = applied = False
    if current_user.is_authenticated:
        saved = SavedJob.query.filter_by(user_id=current_user.id, job_id=job.id).first() is not None
        applied = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first() is not None
    similar = Job.query.filter(Job.company == job.company, Job.id != job.id).limit(3).all()
    return render_template('job_detail.html', job=job, saved=saved, applied=applied,
                           similar=similar, industry_names=INDUSTRY_NAMES,
                           salary_names=SALARY_BAND_NAMES,
                           education_names=EDUCATION_NAMES,
                           cert_names=CERTIFICATION_NAMES)


@app.route('/jobs/save/<jobid>', methods=['POST'])
@login_required
def job_save(jobid):
    job = Job.query.filter_by(jobid=jobid).first_or_404()
    existing = SavedJob.query.filter_by(user_id=current_user.id, job_id=job.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Removed from your saved jobs.', 'info')
    else:
        db.session.add(SavedJob(user_id=current_user.id, job_id=job.id))
        db.session.commit()
        flash('Job saved to your profile.', 'success')
    return redirect(local_redirect(request.referrer.removeprefix(request.host_url.rstrip('/')) if request.referrer and request.referrer.startswith(request.host_url) else None, url_for('job_detail', jobid=jobid)))


@app.route('/jobs/apply/<jobid>', methods=['GET', 'POST'])
@login_required
def job_apply(jobid):
    job = Job.query.filter_by(jobid=jobid).first_or_404()
    existing = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first()
    if existing:
        flash('You have already applied to this job.', 'info')
        return redirect(url_for('job_detail', jobid=jobid))
    letters = CoverLetter.query.filter_by(user_id=current_user.id).order_by(CoverLetter.updated_at.desc()).all()
    if request.method == 'POST':
        first = (request.form.get('first_name') or '').strip()
        last = (request.form.get('last_name') or '').strip()
        email = (request.form.get('email') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        cl = request.form.get('cover_letter_id')
        if not (first and last and '@' in email):
            flash('Please provide your first name, last name, and a valid email address.', 'danger')
            return render_template('job_apply.html', job=job, letters=letters, form=request.form)
        if cl and not any(str(letter.id) == cl for letter in letters):
            abort(400, 'Choose one of your own cover letters.')
        application = Application(user_id=current_user.id, job_id=job.id,
                                  first_name=first, last_name=last, email=email,
                                  phone=phone,
                                  cover_letter_id=int(cl) if cl and cl.isdigit() else None,
                                  status='Submitted')
        db.session.add(application)
        db.session.commit()
        return render_template('job_apply.html', job=job, letters=letters,
                               submitted=True, application=application)
    return render_template('job_apply.html', job=job, letters=letters, form={})


@app.route('/jobs/company/<slug>')
def company_profile(slug):
    company = Job.query.filter_by(company_slug=slug).first_or_404()
    jobs = Job.query.filter_by(company=company.company).order_by(Job.posted_date.desc()).all()
    return render_template('company_profile.html', company=company.company,
                           company_slug=slug, jobs=jobs,
                           industry=INDUSTRY_NAMES.get(company.industry_code, ''))


@app.route('/job-seekers/find-a-job/local-help')
def local_help():
    args_county = (request.args.get('county') or '').strip()
    centers = JobCenter.query.order_by(JobCenter.name).all()
    counties = sorted({c.county for c in centers if c.county})
    shown = [c for c in centers if not args_county or c.county == args_county]
    return render_template('local_help.html', centers=shown, counties=counties,
                           selected=args_county)


@app.route('/job-seekers/find-a-job/state-jobs')
def state_jobs():
    agencies = StateAgency.query.order_by(StateAgency.name).all()
    gov_jobs = Job.query.filter(Job.industry_code == '92').order_by(Job.posted_date.desc()).all()
    return render_template('state_jobs.html', agencies=agencies, jobs=gov_jobs[:10],
                           gov_total=len(gov_jobs))


@app.route('/job-seekers/find-a-job/career-profile-quiz')
def career_quiz_intro():
    return render_template('career_quiz.html')


@app.route('/career-quiz/start', methods=['GET', 'POST'])
def career_quiz():
    from seed_data import QUIZ_QUESTIONS, TRAIT_DESCRIPTIONS, TRAIT_CAREERS
    if request.method == 'POST':
        picks = {}
        for i, question in enumerate(QUIZ_QUESTIONS):
            raw = request.form.get(f'q{i}')
            if raw not in {'0', '0.5', '1'}:
                flash('Please answer every question to see your profile.', 'danger')
                return render_template('career_quiz_form.html', questions=QUIZ_QUESTIONS)
            try:
                picks[question['trait']] = picks.get(question['trait'], 0.0) + float(raw)
            except ValueError:
                flash('Please answer every question to see your profile.', 'danger')
                return render_template('career_quiz_form.html', questions=QUIZ_QUESTIONS)
        # every trait has 2 questions -> max 2.0 each
        ranked = sorted(picks.items(), key=lambda kv: (-kv[1], kv[0]))
        top = ranked[0][0] if ranked else 'Social'
        result = CareerQuizResult(
            user_id=current_user.id if current_user.is_authenticated else None,
            answers=json.dumps(request.form.to_dict()), scores=json.dumps(picks), top_trait=top)
        db.session.add(result)
        db.session.commit()
        return render_template('career_quiz_result.html', scores=dict(ranked), top=top,
                               descriptions=TRAIT_DESCRIPTIONS,
                               careers=TRAIT_CAREERS,
                               questions=QUIZ_QUESTIONS)
    return render_template('career_quiz_form.html', questions=QUIZ_QUESTIONS)


@app.route('/for-employers')
def for_employers():
    total_jobs = Job.query.count()
    companies = Job.query.with_entities(Job.company).distinct().count()
    return render_template('for_employers.html', total_jobs=total_jobs,
                           companies=companies,
                           employers_on_board=6492, resumes_available=1460686)


@app.route('/for-employers/resources-for-employers')
def employer_resources():
    return render_template('employer_resources.html')


@app.route('/for-students')
def for_students():
    return render_template('for_students.html')


@app.route('/news-and-events')
def news_events():
    keyword = (request.args.get('q') or '').strip()
    topic = (request.args.get('topic') or '').strip()
    date_from = (request.args.get('from') or '').strip()
    date_to = (request.args.get('to') or '').strip()
    items = NewsItem.query.order_by(NewsItem.published_date.desc()).all()
    if keyword:
        low = keyword.lower()
        items = [n for n in items if low in (n.title + ' ' + n.teaser).lower()]
    if topic:
        items = [n for n in items if n.topic == topic]
    if date_from:
        items = [n for n in items if n.published_date >= date_from]
    if date_to:
        items = [n for n in items if n.published_date <= date_to]
    topics = sorted({n.topic for n in NewsItem.query.all() if n.topic})
    return render_template('news_events.html', items=items, topics=topics,
                           keyword=keyword, topic=topic, date_from=date_from,
                           date_to=date_to)


@app.route('/news-and-events/news')
def news_index():
    return redirect(url_for('news_events'))


@app.route('/news-and-events/news/<slug>')
def news_detail(slug):
    item = NewsItem.query.filter_by(slug=slug).first_or_404()
    more = NewsItem.query.filter(NewsItem.slug != slug).order_by(
        NewsItem.published_date.desc()).limit(4).all()
    return render_template('news_detail.html', item=item, more=more)


@app.route('/news-and-events/events')
def events_page():
    return render_template('events.html')


@app.route('/help-center')
def help_center():
    sections = db.session.query(HelpArticle.section).distinct().all()
    articles = HelpArticle.query.order_by(HelpArticle.section, HelpArticle.id).all()
    return render_template('help_center.html', articles=articles,
                           sections=sorted({s for (s,) in sections}))


@app.route('/help-center/<slug>')
def help_article(slug):
    article = HelpArticle.query.filter_by(slug=slug).first_or_404()
    others = HelpArticle.query.filter(HelpArticle.id != article.id).limit(6).all()
    return render_template('help_article.html', article=article, others=others)


@app.route('/search')
def site_search():
    q = (request.args.get('q') or request.args.get('search_query') or '').strip()
    results = []
    if q:
        tokens_q = tokenize(q)
        # jobs
        for job in Job.query.all():
            text = ' '.join([job.title, job.company, job.city, job.description[:400]]).lower()
            if any(t in text for t in tokens_q):
                results.append(('job', job.title, f"{job.company} — {job.city}",
                                 url_for('job_detail', jobid=job.jobid)))
        for n in NewsItem.query.all():
            text = (n.title + ' ' + n.teaser).lower()
            if any(t in text for t in tokens_q):
                results.append(('news', n.title, n.teaser, url_for('news_detail', slug=n.slug)))
        for a in HelpArticle.query.all():
            text = (a.title + ' ' + ' '.join(a.paragraphs)).lower()
            if any(t in text for t in tokens_q):
                results.append(('help', a.title, a.section.title(), url_for('help_article', slug=a.slug)))
        for c in JobCenter.query.all():
            text = (c.name + ' ' + c.address).lower()
            if any(t in text for t in tokens_q):
                results.append(('center', c.name, c.address, url_for('local_help')))
    return render_template('site_search.html', q=q, results=results[:50])


@app.route('/contact-us', methods=['GET', 'POST'])
def contact_us():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip()
        subject = (request.form.get('subject') or '').strip()
        message = (request.form.get('message') or '').strip()
        if not (name and '@' in email and message):
            flash('Please fill in your name, a valid email, and a message.', 'danger')
            return render_template('contact_us.html', form=request.form)
        db.session.add(ContactMessage(name=name, email=email, subject=subject,
                                       message=message))
        db.session.commit()
        return render_template('contact_us.html', sent=True, form={})
    return render_template('contact_us.html', form={})


# ------------------------------------------------------------------- auth

@app.route('/account/register', methods=['GET', 'POST'])
def account_register():
    if current_user.is_authenticated:
        return redirect(url_for('account_profile'))
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm') or ''
        first = (request.form.get('first_name') or '').strip()
        last = (request.form.get('last_name') or '').strip()
        zip_code = (request.form.get('zip_code') or '').strip()
        errors = []
        if not email or '@' not in email:
            errors.append('Enter a valid email address.')
        if User.query.filter_by(email=email).first():
            errors.append('An account with that email already exists.')
        if not valid_password(password):
            errors.append('Password must be at least 8 characters and at most 20, with upper and lower case letters, a number and an allowed symbol.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('register.html', form=request.form)
        user = User(email=email, first_name=first, last_name=last, zip_code=zip_code)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Welcome to OhioMeansJobs! Your free account is ready.', 'success')
        return redirect(url_for('account_profile'))
    return render_template('register.html', form={})


@app.route('/account/login', methods=['GET', 'POST'])
def account_login():
    if current_user.is_authenticated:
        return redirect(url_for('account_profile'))
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Signed in. Welcome back!', 'success')
            nxt = request.args.get('next')
            if nxt:
                return redirect(local_redirect(nxt, url_for('account_profile')))
            return redirect(url_for('account_profile'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', form={})


@app.route('/account/logout', methods=['POST'])
@login_required
def account_logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('home'))


# ---------------------------------------------------------------- account

@app.route('/account/profile')
@login_required
def account_profile():
    saved = (SavedJob.query.filter_by(user_id=current_user.id)
             .order_by(SavedJob.saved_at.desc()).all())
    applications = (Application.query.filter_by(user_id=current_user.id)
                    .order_by(Application.applied_at.desc()).all())
    searches = (SavedSearch.query.filter_by(user_id=current_user.id)
                .order_by(SavedSearch.created_at.desc()).all())
    resume = Resume.query.filter_by(user_id=current_user.id).first()
    letters = CoverLetter.query.filter_by(user_id=current_user.id).count()
    plan_tasks = CareerPlanTask.query.filter_by(user_id=current_user.id).all()
    return render_template('account_profile.html', saved=saved, applications=applications,
                           searches=searches, resume=resume, letters=letters,
                           plan_tasks=plan_tasks,
                           open_tasks=sum(1 for t in plan_tasks if not t.done))


@app.route('/account/profile/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    if request.method == 'POST':
        current_user.first_name = (request.form.get('first_name') or '').strip()
        current_user.last_name = (request.form.get('last_name') or '').strip()
        current_user.phone = (request.form.get('phone') or '').strip()
        current_user.zip_code = (request.form.get('zip_code') or '').strip()
        current_user.city = (request.form.get('city') or '').strip()
        current_user.military_status = request.form.get('military_status') or ''
        current_user.employment_status = request.form.get('employment_status') or ''
        current_user.target_job_title = (request.form.get('target_job_title') or '').strip()
        current_user.career_level = request.form.get('career_level') or ''
        current_user.education = request.form.get('education') or ''
        current_user.willing_relocate = request.form.get('willing_relocate') == 'on'
        db.session.commit()
        flash('Your account settings were updated.', 'success')
        return redirect(url_for('account_profile'))
    return render_template('account_edit.html', user=current_user,
                           education_names=EDUCATION_NAMES)


@app.route('/account/change-password', methods=['GET', 'POST'])
@login_required
def account_change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password') or ''
        new_pw = request.form.get('new_password') or ''
        confirm = request.form.get('confirm') or ''
        if not current_user.check_password(current_pw):
            flash('Your current password is incorrect.', 'danger')
        elif not valid_password(new_pw):
            flash('Use 8 to 20 characters with upper and lower case letters, a number and an allowed symbol.', 'danger')
        elif new_pw != confirm:
            flash('New passwords do not match.', 'danger')
        else:
            current_user.set_password(new_pw)
            db.session.commit()
            flash('Your password has been changed.', 'success')
            return redirect(url_for('account_profile'))
    return render_template('change_password.html')


@app.route('/account/saved-jobs')
@login_required
def account_saved_jobs():
    saved = (SavedJob.query.filter_by(user_id=current_user.id)
             .order_by(SavedJob.saved_at.desc()).all())
    return render_template('saved_jobs.html', saved=saved)


@app.route('/account/saved-searches', methods=['GET', 'POST'])
@login_required
def account_saved_searches():
    if request.method == 'POST':
        action = request.form.get('action') or 'save'
        if action == 'delete':
            target = SavedSearch.query.filter_by(
                id=request.form.get('id'), user_id=current_user.id).first()
            if target:
                db.session.delete(target)
                db.session.commit()
                flash('Saved search deleted.', 'info')
            return redirect(url_for('account_saved_searches'))
        name = (request.form.get('name') or '').strip()
        params_json = request.form.get('params') or '{}'
        frequency = request.form.get('frequency') or 'Daily'
        alerts = request.form.get('alerts') == 'on'
        try:
            params = json.loads(params_json)
        except (ValueError, TypeError):
            abort(400, 'Invalid search parameters.')
        if not isinstance(params, dict) or any(not isinstance(v, (str, int, float)) for v in params.values()) or frequency not in {'Daily', 'Weekly', 'Monthly'}:
            abort(400, 'Invalid saved search.')
        if not name:
            flash('Give your saved search a name.', 'danger')
            return redirect(url_for('account_saved_searches'))
        if SavedSearch.query.filter_by(user_id=current_user.id, name=name).first():
            flash('You already have a saved search with that name.', 'danger')
            return redirect(url_for('account_saved_searches'))
        db.session.add(SavedSearch(user_id=current_user.id, name=name,
                                   query_params=params_json,
                                   frequency=frequency, alerts_enabled=alerts))
        db.session.commit()
        flash(f"Saved search '{name}' created.", 'success')
        return redirect(url_for('account_saved_searches'))
    searches = (SavedSearch.query.filter_by(user_id=current_user.id)
                .order_by(SavedSearch.created_at.desc()).all())
    return render_template('saved_searches.html', searches=searches,
                           frequency_options=['Daily', 'Weekly', 'Monthly'])


@app.route('/account/applications')
@login_required
def account_applications():
    applications = (Application.query.filter_by(user_id=current_user.id)
                    .order_by(Application.applied_at.desc()).all())
    return render_template('applications.html', applications=applications)


@app.route('/account/resume', methods=['GET', 'POST'])
@login_required
def account_resume():
    resume = Resume.query.filter_by(user_id=current_user.id).first()
    if request.method == 'POST':
        if not resume:
            resume = Resume(user_id=current_user.id)
            db.session.add(resume)
        resume.title = (request.form.get('title') or '').strip()
        resume.summary = (request.form.get('summary') or '').strip()
        resume.skills = (request.form.get('skills') or '').strip()
        resume.experience = (request.form.get('experience') or '').strip()
        resume.active = request.form.get('active') == 'on'
        resume.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Your resume was saved.', 'success')
        return redirect(url_for('account_resume'))
    # SkillsMatch: jobs overlapping the resume skills
    matches = []
    if resume and resume.skills:
        tokens_q = tokenize(resume.skills)
        for job in Job.query.order_by(Job.posted_date.desc()).all():
            text = ' '.join([job.title, job.description]).lower()
            score = sum(1 for t in tokens_q if t in text)
            if score >= 2:
                matches.append((job, score))
        matches.sort(key=lambda pair: -pair[1])
        matches = matches[:10]
    return render_template('resume.html', resume=resume, matches=matches)


@app.route('/account/cover-letters', methods=['GET', 'POST'])
@login_required
def account_cover_letters():
    if request.method == 'POST':
        action = request.form.get('action') or 'add'
        if action == 'delete':
            target = CoverLetter.query.filter_by(
                id=request.form.get('id'), user_id=current_user.id).first()
            if target:
                db.session.delete(target)
                db.session.commit()
                flash('Cover letter deleted.', 'info')
            return redirect(url_for('account_cover_letters'))
        name = (request.form.get('name') or '').strip()
        body = (request.form.get('body') or '').strip()
        edit_id = request.form.get('id')
        if not name or not body:
            flash('A cover letter needs a name and a body.', 'danger')
            return redirect(url_for('account_cover_letters'))
        if edit_id and edit_id.isdigit():
            letter = CoverLetter.query.filter_by(id=int(edit_id),
                                                 user_id=current_user.id).first()
            if letter:
                letter.name = name
                letter.body = body
                letter.updated_at = datetime.utcnow()
                db.session.commit()
                flash('Cover letter updated.', 'success')
                return redirect(url_for('account_cover_letters'))
        if CoverLetter.query.filter_by(user_id=current_user.id).count() >= MAX_COVER_LETTERS:
            flash(f'You can save up to {MAX_COVER_LETTERS} different cover letters.', 'danger')
            return redirect(url_for('account_cover_letters'))
        db.session.add(CoverLetter(user_id=current_user.id, name=name, body=body))
        db.session.commit()
        flash('Cover letter saved.', 'success')
        return redirect(url_for('account_cover_letters'))
    letters = CoverLetter.query.filter_by(user_id=current_user.id).order_by(
        CoverLetter.updated_at.desc()).all()
    return render_template('cover_letters.html', letters=letters,
                           max_letters=MAX_COVER_LETTERS)


@app.route('/account/career-plan', methods=['GET', 'POST'])
@login_required
def account_career_plan():
    if request.method == 'POST':
        action = request.form.get('action') or 'add'
        if action == 'toggle':
            task = CareerPlanTask.query.filter_by(
                id=request.form.get('id'), user_id=current_user.id).first()
            if task:
                task.done = not task.done
                db.session.commit()
            return redirect(url_for('account_career_plan'))
        if action == 'delete':
            task = CareerPlanTask.query.filter_by(
                id=request.form.get('id'), user_id=current_user.id).first()
            if task:
                db.session.delete(task)
                db.session.commit()
            return redirect(url_for('account_career_plan'))
        description = (request.form.get('description') or '').strip()
        deadline = (request.form.get('deadline') or '').strip()
        if description:
            db.session.add(CareerPlanTask(user_id=current_user.id,
                                          description=description, deadline=deadline))
            db.session.commit()
            flash('Task added to your career plan.', 'success')
        return redirect(url_for('account_career_plan'))
    tasks = CareerPlanTask.query.filter_by(user_id=current_user.id).order_by(
        CareerPlanTask.done, CareerPlanTask.deadline).all()
    return render_template('career_plan.html', tasks=tasks)


# ------------------------------------------------------------------ health

@app.route('/_health')
def health():
    checks = {
        'home': True,
        'jobs_search': Job.query.count() > 0,
        'job_detail': Job.query.first() is not None,
        'news': NewsItem.query.count() > 0,
        'centers': JobCenter.query.count() > 0,
        'help': HelpArticle.query.count() > 0,
        'agencies': StateAgency.query.count() > 0,
        'users': User.query.filter_by(email='alice.j@test.com').first() is not None,
    }
    ok = all(checks.values())
    return jsonify({'ok': ok, 'site': 'ohiomeansjobs', 'checks': checks,
                    'jobs': Job.query.count()}), (200 if ok else 500)


# ---------------------------------------------------------------- bootstrap

with app.app_context():
    db.create_all()
    from seed_data import seed_database, seed_benchmark_users
    seed_database(db, Job, NewsItem, JobCenter, HelpArticle, StateAgency)
    seed_benchmark_users(db, User, Job, SavedJob, Application, SavedSearch,
                         Resume, CoverLetter, CareerPlanTask)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 40090))
    app.run(host='0.0.0.0', port=port, debug=False)
