#!/usr/bin/env python3
"""Thumbtack mirror — Flask application.

Mirrors https://www.thumbtack.com/ (local-services marketplace): home-page
search + category tiles, per-category "near me" listings with the filter
sidebar and sort tabs, pro profiles (About / Services / Photos / Reviews /
Credentials), the request-a-quote wizard that matches a project with pros
and collects deterministic quotes, messaging threads with deterministic pro
replies, hiring + review submission, the saved-pros list, the account area,
cost-guide pages (/p/...), the /prices index, the services-near-me index and
city pages.

Data comes from the tracked source_data_*.json snapshots captured on
2026-09-26; the SQLite seed is
materialized deterministically at image build time.
"""
import hashlib
import json
import os
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
app.config["SECRET_KEY"] = os.environ.get("THUMBTACK_SECRET_KEY") or "webharbor-thumbtack-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'THUMBTACK_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'thumbtack.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your account.'
csrf = CSRFProtect(app)

# The mirror is a snapshot of the upstream site taken on 2026-09-26.
MIRROR_TODAY = datetime(2026, 9, 26, 12, 0, 0)
MIRROR_DATE = 'Sep 26, 2026'
# bcrypt hash of 'TestPass123!' (frozen so the SQLite seed is byte-reproducible)
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')
DEFAULT_ZIP = '98052'          # Redmond, WA — the captured geo
DEFAULT_CITY = 'Redmond'
DEFAULT_STATE = 'WA'
STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
              'or', 'is', 'it', 'by', 'with', 'near', 'me', 'you', 'your',
              'my', 'and', 'how', 'much', 'does', 'cost', 'do', 'i'}
RATING_WORDS = [  # upstream rating-word bands
    (5.0, 'Exceptional'), (4.8, 'Excellent'), (4.6, 'Very good'),
    (4.0, 'Great'), (3.5, 'Good'), (0.0, None),
]
PROJECT_STATUSES = ['requested', 'matched', 'hired', 'completed', 'cancelled']


def rating_word(rating: float) -> str | None:
    for floor, word in RATING_WORDS:
        if rating >= floor:
            return word
    return None


# ------------------------------------------------------------------ models --

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)          # "House Cleaning"
    plural = db.Column(db.String(120), nullable=False)       # "house cleaners"
    h1 = db.Column(db.String(160), nullable=False)           # "House cleaners near you"
    description = db.Column(db.Text, nullable=False)
    meta_group = db.Column(db.String(60), nullable=False)     # near-me group
    icon = db.Column(db.String(40), nullable=False)           # emoji label
    image = db.Column(db.String(120), nullable=False)         # hero card image
    questions = db.Column(db.Text, nullable=False)            # JSON [{q, opts}]
    quote_questions = db.Column(db.Text, nullable=False)      # JSON right-rail
    cost_slug = db.Column(db.String(120), nullable=True)       # related guide

    @property
    def question_list(self):
        return json.loads(self.questions)

    @property
    def quote_question_list(self):
        return json.loads(self.quote_questions)

    def url(self):
        return url_for('category', slug=self.slug)

    def near_me_url(self):
        return url_for('category', slug=self.slug)


class Pro(db.Model):
    __tablename__ = 'pros'
    id = db.Column(db.Integer, primary_key=True)
    service_pk = db.Column(db.String(24), unique=True, nullable=False)
    slug = db.Column(db.String(160), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'),
                            nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(4), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    review_count = db.Column(db.Integer, nullable=False)
    hires = db.Column(db.Integer, nullable=False)
    similar_jobs = db.Column(db.Integer, nullable=False)
    years_in_business = db.Column(db.Integer, nullable=False)
    employees = db.Column(db.Integer, nullable=False)
    background_checked = db.Column(db.Boolean, nullable=False)
    top_pro = db.Column(db.Boolean, nullable=False)
    top_pro_years = db.Column(db.Text, nullable=False)        # JSON [2024, 2025]
    responds_in = db.Column(db.Integer, nullable=False)       # minutes
    online_now = db.Column(db.Boolean, nullable=False)
    great_value = db.Column(db.Boolean, nullable=False)
    in_high_demand = db.Column(db.Boolean, nullable=False)
    bio = db.Column(db.Text, nullable=False)
    payment_methods = db.Column(db.Text, nullable=False)
    social_media = db.Column(db.Text, nullable=False)          # JSON [..]
    avatar = db.Column(db.String(120), nullable=False)         # images/<file>
    gallery = db.Column(db.Text, nullable=False)               # JSON [..]
    business_hours = db.Column(db.Text, nullable=False)        # JSON [[day, hours], ..]
    rating_distribution = db.Column(db.Text, nullable=False)   # JSON {"5": 98, ..}
    review_tags = db.Column(db.Text, nullable=False)           # JSON [["clean", 30], ..]
    services_offered = db.Column(db.Text, nullable=False)      # JSON [[group, [opts]], ..]
    card_quote = db.Column(db.Text, nullable=False)            # customer quote on card
    card_quote_author = db.Column(db.String(80), nullable=False)
    background_check_name = db.Column(db.String(120), nullable=True)
    credentials_zip = db.Column(db.String(12), nullable=True)

    category = db.relationship('Category', backref='pros')

    @property
    def rating_word(self):
        return rating_word(self.rating)

    @property
    def gallery_list(self):
        return json.loads(self.gallery)

    @property
    def services_offered_list(self):
        return json.loads(self.services_offered)

    @property
    def business_hours_list(self):
        return json.loads(self.business_hours)

    @property
    def social_media_list(self):
        return json.loads(self.social_media)

    @property
    def top_pro_years_list(self):
        return json.loads(self.top_pro_years)

    @property
    def review_tags_list(self):
        return json.loads(self.review_tags)

    @property
    def responds_label(self):
        """Fits after 'Responds': 'within a day' / 'in about 22 min'."""
        if self.responds_in >= 1440:
            return 'within a day'
        if self.responds_in < 60:
            return f'in about {self.responds_in} min'
        h = round(self.responds_in / 60)
        return f'in about {h} hour' + ('s' if h > 1 else '')

    @property
    def profile_path(self):
        city = re.sub(r'[^a-z0-9]+', '-', self.city.lower()).strip('-')
        return (f'/{self.state.lower()}/{city}/{self.category.slug}/'
                f'{self.slug}/service/{self.service_pk}')

    def url(self):
        return url_for('pro_profile', state=self.state.lower(), city_slug=re.sub(
            r'[^a-z0-9]+', '-', self.city.lower()).strip('-'),
            cat_slug=self.category.slug, pro_slug=self.slug,
            service_pk=self.service_pk)


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    pro_id = db.Column(db.Integer, db.ForeignKey('pros.id'), nullable=False)
    author = db.Column(db.String(80), nullable=False)
    date_str = db.Column(db.String(40), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    body = db.Column(db.Text, nullable=False)
    details = db.Column(db.String(240), nullable=True)
    hired = db.Column(db.Boolean, nullable=False)
    source = db.Column(db.String(16), nullable=False, default='upstream')

    pro = db.relationship('Pro', backref='reviews')


class CostGuide(db.Model):
    __tablename__ = 'cost_guides'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    group_name = db.Column(db.String(80), nullable=False)      # prices-page group
    avg_price = db.Column(db.Integer, nullable=True)           # "$550 National Avg. Price"
    range_low = db.Column(db.Integer, nullable=True)
    range_high = db.Column(db.Integer, nullable=True)
    low_end = db.Column(db.String(40), nullable=True)
    high_end = db.Column(db.String(40), nullable=True)
    intro = db.Column(db.Text, nullable=False)
    tables = db.Column(db.Text, nullable=False)                # JSON [{title, rows}]
    faqs = db.Column(db.Text, nullable=False)                  # JSON [[q, a], ..]
    related_category = db.Column(db.String(80), nullable=True)
    updated_str = db.Column(db.String(60), nullable=False)

    def url(self):
        return url_for('cost_guide', slug=self.slug)

    @property
    def tables_list(self):
        return json.loads(self.tables)

    @property
    def faqs_list(self):
        return json.loads(self.faqs)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    zip = db.Column(db.String(12), nullable=True)
    address = db.Column(db.String(160), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=MIRROR_TODAY)


class SavedPro(db.Model):
    __tablename__ = 'saved_pros'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pro_id = db.Column(db.Integer, db.ForeignKey('pros.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=MIRROR_TODAY)

    __table_args__ = (db.UniqueConstraint('user_id', 'pro_id'),)
    pro = db.relationship('Pro')


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'),
                            nullable=False)
    zip = db.Column(db.String(12), nullable=False)
    details = db.Column(db.Text, nullable=False)
    timeline = db.Column(db.String(60), nullable=False)
    answers = db.Column(db.Text, nullable=False)               # JSON [[q, a], ..]
    status = db.Column(db.String(20), nullable=False, default='matched')
    created_at = db.Column(db.DateTime, nullable=False, default=MIRROR_TODAY)

    user = db.relationship('User', backref='projects')
    category = db.relationship('Category', backref='projects')

    @property
    def answer_list(self):
        return json.loads(self.answers)

    @property
    def matches(self):
        return (ProjectMatch.query.filter_by(project_id=self.id)
                .order_by(ProjectMatch.responded.desc(), ProjectMatch.quote_amount)
                .all())


class ProjectMatch(db.Model):
    __tablename__ = 'project_matches'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    pro_id = db.Column(db.Integer, db.ForeignKey('pros.id'), nullable=False)
    responded = db.Column(db.Boolean, nullable=False)
    quote_amount = db.Column(db.Integer, nullable=True)
    response_note = db.Column(db.String(400), nullable=True)
    responded_min = db.Column(db.Integer, nullable=True)      # minutes after request
    hired = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (db.UniqueConstraint('project_id', 'pro_id'),)
    pro = db.relationship('Pro')


class Thread(db.Model):
    __tablename__ = 'threads'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pro_id = db.Column(db.Integer, db.ForeignKey('pros.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=MIRROR_TODAY)

    user = db.relationship('User')
    pro = db.relationship('Pro')


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('threads.id'), nullable=False)
    sender = db.Column(db.String(10), nullable=False)         # 'user' | 'pro'
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=MIRROR_TODAY)

    thread = db.relationship('Thread', backref='messages')


class Enrollment(db.Model):
    """Helper for the 'Join as a pro' funnel (pro sign-up form)."""
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    zip = db.Column(db.String(12), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=MIRROR_TODAY)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ----------------------------------------------------------------- helpers --

def det_hash(*parts) -> int:
    digest = hashlib.md5('|'.join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:12], 16)


def scored_search(query, entities, fields):
    """Token-overlap scored search (never strict AND)."""
    tokens = [t.lower() for t in re.split(r'\W+', query or '')
              if t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return entities
    results = []
    for item in entities:
        text = ' '.join(str(getattr(item, f, '') or '') for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            results.append((item, score))
    results.sort(key=lambda x: -x[1])
    return [r[0] for r in results]


def extract_city(query):
    """Pull a trailing 'in <City>' from a query -> (city or None, rest)."""
    m = re.search(r'\bin\s+([A-Za-z][A-Za-z .\'-]+?)$', (query or '').strip())
    if m:
        return m.group(1).strip().rstrip('.'), query[:m.start()].strip()
    return None, (query or '').strip()


CITY_SLUG_ALIASES = {}  # filled at seed time from pro cities


def find_city_name(slug):
    return CITY_SLUG_ALIASES.get(slug)


def pro_sort_key(sort):
    """Map the four upstream sort tabs to a key function."""
    if sort == 'highest_rated':
        return lambda p: (-p.rating, -p.review_count)
    if sort == 'most_hires':
        return lambda p: (-p.hires, -p.rating)
    if sort == 'fastest_response':
        return lambda p: (p.responds_in, -p.rating)
    # Recommended (default): Top Pro first, then rating, then response speed
    return lambda p: (not p.top_pro, -p.rating, p.responds_in)


def apply_filters(pros, args, questions):
    """Apply the category filter sidebar (radio-style single choice per q).

    The first question is the start-timeline preference, which upstream uses
    for matching priority rather than hard exclusion, so it is not applied
    here. Attribute questions hard-filter on the pro's captured service
    attributes; if the combination would empty the page, upstream-style fuzzy
    matching keeps the full list instead.
    """
    out = []
    for p in pros:
        keep = True
        for qi, q in enumerate(questions):
            if qi == 0:
                continue
            key = f'f{qi}'
            val = args.get(key)
            if not val:
                continue
            blob = ' '.join(
                ' '.join(opts) for _, opts in p.services_offered_list).lower()
            if val.lower() not in blob and val.lower() not in p.bio.lower():
                keep = False
                break
        if keep:
            out.append(p)
    return out if out else pros


def pro_quote(pro, project):
    """Deterministic quote for (project, pro) from the category cost band."""
    guide = (CostGuide.query.filter_by(slug=pro.category.cost_slug).first()
             if pro.category.cost_slug else None)
    if guide and guide.range_low is not None and guide.range_high is not None:
        span = max(guide.range_high - guide.range_low, 20)
        return guide.range_low + det_hash(project.id, pro.service_pk) % (span + 1)
    return 80 + det_hash(project.id, pro.service_pk) % 220


class ContentRecord(db.Model):
    __tablename__ = 'content_records'
    id = db.Column(db.Integer, primary_key=True)
    payload = db.Column(db.Text, nullable=False)


def seed_content():
    if db.session.get(ContentRecord, 1) is not None:
        return
    with open(os.path.join(BASE_DIR, 'source_data_content.json'), encoding='utf-8') as source:
        payload = json.dumps(json.load(source), ensure_ascii=False, sort_keys=True)
    db.session.add(ContentRecord(id=1, payload=payload))
    db.session.commit()


def load_content():
    row = db.session.get(ContentRecord, 1)
    if row is None:
        raise RuntimeError('Missing build-generated content seed')
    return json.loads(row.payload)


def pro_response_note(pro, project):
    pool = load_content()['quote_notes']
    idx = det_hash('note', pro.service_pk, project.id) % len(pool)
    return pool[idx].format(pro=pro.name)


def auto_reply(thread, user_message):
    """Deterministic pro reply for a user message (category + keyword aware)."""
    content = load_content()
    cat = thread.pro.category
    key = cat.slug if cat.slug in content['pro_replies'] else 'default'
    pool = content['pro_replies'][key]
    msg = (user_message or '').lower()
    for entry in pool.get('keyword', []):
        if any(w in msg for w in entry['when']):
            return entry['reply'].format(pro=thread.pro.name)
    fallback = pool.get('fallback') or content['pro_replies']['default']['fallback']
    n = Message.query.filter_by(thread_id=thread.id).count()
    idx = det_hash('reply', thread.id, n, user_message) % len(fallback)
    return fallback[idx].format(pro=thread.pro.name)


def seed_matches(project):
    """Create the deterministic match set for a fresh project."""
    pros = (Pro.query.filter_by(category_id=project.category_id)
            .order_by(Pro.rating.desc(), Pro.hires.desc()).all())
    chosen = pros[:5]
    for rank, pro in enumerate(chosen):
        respond = det_hash('resp', project.id, pro.service_pk) % 5 != 0
        db.session.add(ProjectMatch(
            project_id=project.id, pro_id=pro.id, responded=respond,
            quote_amount=pro_quote(pro, project) if respond else None,
            response_note=pro_response_note(pro, project) if respond else None,
            responded_min=pro.responds_in if respond else None))
    db.session.commit()


def _pro_card(pro):
    return {
        'pro': pro, 'rating_word': pro.rating_word,
        'responds_label': pro.responds_label,
    }


# ------------------------------------------------------------------- routes --

@app.route('/')
def index():
    cats = Category.query.order_by(Category.id).all()
    popular = [c for c in cats if c.meta_group == 'Home Improvement'][:6]
    groups = {}
    for c in cats:
        groups.setdefault(c.meta_group, []).append(c)
    city_links = load_content()['home_cities']
    return render_template('index.html', cats=cats, popular=popular,
                           groups=groups, city_links=city_links)


@app.route('/_health')
def health():
    return {'ok': True, 'site': 'thumbtack'}


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    city_hint, rest = extract_city(q)
    cats = scored_search(rest or q, Category.query.all(),
                         ['name', 'plural', 'description'])
    guides = scored_search(rest or q, CostGuide.query.all(),
                           ['title', 'intro'])
    pros = Pro.query.all()
    if city_hint:
        pros = [p for p in pros if p.city.lower().startswith(city_hint.lower())]
    pros = scored_search(rest or q, pros, ['name', 'bio', 'category.name'])
    return render_template('search.html', q=q, cats=cats[:12], pros=pros[:12],
                           guides=guides[:12],
                           total=len(cats) + len(pros) + len(guides))


@app.route('/k/<slug>/near-me')
def category(slug):
    cat = Category.query.filter_by(slug=slug).first_or_404()
    sort = request.args.get('sort', 'recommended')
    pros = Pro.query.filter_by(category_id=cat.id).all()
    questions = cat.question_list
    active = {f'f{i}': request.args.get(f'f{i}', '') for i in range(len(questions))}
    if any(active.values()):
        pros = apply_filters(pros, request.args, questions)
    pros = sorted(pros, key=pro_sort_key(sort))
    guides = (CostGuide.query.filter_by(slug=cat.cost_slug).all()
              if cat.cost_slug else [])
    return render_template('category.html', cat=cat, pros=pros, sort=sort,
                           questions=questions, active=active,
                           guide=guides[0] if guides else None)


@app.route('/<state>/<city_slug>/<cat_slug>/<pro_slug>/service/<service_pk>')
def pro_profile(state, city_slug, cat_slug, pro_slug, service_pk):
    pro = Pro.query.filter_by(service_pk=service_pk).first_or_404()
    reviews = (Review.query.filter_by(pro_id=pro.id)
               .order_by(Review.id).all())
    similar = (Pro.query.filter(Pro.category_id == pro.category_id,
                                Pro.id != pro.id)
               .order_by(Pro.rating.desc()).limit(3).all())
    guide = (CostGuide.query.filter_by(slug=pro.category.cost_slug).first()
             if pro.category.cost_slug else None)
    saved = (current_user.is_authenticated and
             SavedPro.query.filter_by(user_id=current_user.id,
                                      pro_id=pro.id).first() is not None)
    dist = json.loads(pro.rating_distribution)
    return render_template('pro_profile.html', pro=pro, reviews=reviews,
                           similar=similar, guide=guide, saved=saved,
                           dist=dist, quote_questions=pro.category.quote_question_list)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            dest = request.args.get('next') or request.form.get('next')
            return redirect(dest or url_for('account'))
        flash('Incorrect email or password. Please try again.')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        name = request.form.get('name', '').strip()
        zip_ = request.form.get('zip', '').strip()
        if not (email and password and name):
            flash('Please fill in all required fields.')
        elif len(password) < 8:
            flash('Password must be at least 8 characters long.')
        elif User.query.filter_by(email=email).first():
            flash('An account with that email already exists. Log in instead.')
        else:
            user = User(username=email.split('@')[0][:40], email=email,
                        display_name=name,
                        password_hash=bcrypt.generate_password_hash(
                            password).decode(), zip=zip_ or None)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('account'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/account')
@login_required
def account():
    projects = (Project.query.filter_by(user_id=current_user.id)
                .order_by(Project.id.desc()).all())
    saved = (SavedPro.query.filter_by(user_id=current_user.id)
             .order_by(SavedPro.id.desc()).all())
    threads = (Thread.query.filter_by(user_id=current_user.id)
               .order_by(Thread.updated_at.desc()).all())
    return render_template('account.html', projects=projects, saved=saved,
                           threads=threads)


@app.route('/account/profile', methods=['GET', 'POST'])
@login_required
def profile_edit():
    if request.method == 'POST':
        current_user.display_name = request.form.get('name', '').strip() or current_user.display_name
        current_user.phone = request.form.get('phone', '').strip()
        current_user.zip = request.form.get('zip', '').strip()
        current_user.address = request.form.get('address', '').strip()
        db.session.commit()
        flash('Your profile has been updated.')
        return redirect(url_for('account'))
    return render_template('profile_edit.html')


@app.route('/account/saved/toggle/<int:pro_id>', methods=['POST'])
def save_pro(pro_id):
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=request.form.get('next') or request.referrer or url_for('index')))
    existing = SavedPro.query.filter_by(user_id=current_user.id, pro_id=pro_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Removed from your saved pros.')
    else:
        db.session.add(SavedPro(user_id=current_user.id, pro_id=pro_id))
        db.session.commit()
        flash('Saved to your pros.')
    dest = request.form.get('next') or request.referrer or url_for('account_saved')
    return redirect(dest)


@app.route('/account/saved')
@login_required
def account_saved():
    saved = (SavedPro.query.filter_by(user_id=current_user.id)
             .order_by(SavedPro.id.desc()).all())
    return render_template('saved.html', saved=saved)


@app.route('/account/projects')
@login_required
def account_projects():
    projects = (Project.query.filter_by(user_id=current_user.id)
                .order_by(Project.id.desc()).all())
    return render_template('projects.html', projects=projects)


@app.route('/account/messages')
@login_required
def account_messages():
    threads = (Thread.query.filter_by(user_id=current_user.id)
               .order_by(Thread.updated_at.desc()).all())
    return render_template('messages.html', threads=threads)


@app.route('/account/messages/<int:thread_id>', methods=['GET', 'POST'])
@login_required
def thread_view(thread_id):
    thread = db.session.get(Thread, thread_id) or abort(404)
    if thread.user_id != current_user.id:
        abort(403)
    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if body:
            db.session.add(Message(thread_id=thread.id, sender='user', body=body,
                                   created_at=datetime(2026, 9, 26, 12, 30)))
            reply = auto_reply(thread, body)
            db.session.add(Message(thread_id=thread.id, sender='pro', body=reply,
                                   created_at=datetime(2026, 9, 26, 12, 32)))
            thread.updated_at = datetime(2026, 9, 26, 12, 32)
            db.session.commit()
            return redirect(url_for('thread_view', thread_id=thread.id))
    messages = Message.query.filter_by(thread_id=thread.id).order_by(Message.id).all()
    return render_template('thread.html', thread=thread, messages=messages)


@app.route('/message/<service_pk>', methods=['GET', 'POST'])
def message_pro(service_pk):
    pro = Pro.query.filter_by(service_pk=service_pk).first_or_404()
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=f'/message/{service_pk}'))
    thread = Thread.query.filter_by(user_id=current_user.id, pro_id=pro.id).first()
    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if not thread:
            thread = Thread(user_id=current_user.id, pro_id=pro.id)
            db.session.add(thread)
            db.session.flush()
        if body:
            db.session.add(Message(thread_id=thread.id, sender='user', body=body,
                                   created_at=datetime(2026, 9, 26, 12, 30)))
            reply = auto_reply(thread, body)
            db.session.add(Message(thread_id=thread.id, sender='pro', body=reply,
                                   created_at=datetime(2026, 9, 26, 12, 32)))
            thread.updated_at = datetime(2026, 9, 26, 12, 32)
            db.session.commit()
        return redirect(url_for('thread_view', thread_id=thread.id))
    return render_template('message_form.html', pro=pro, thread=thread)


@app.route('/projects/new', methods=['GET', 'POST'])
def project_new():
    cat_slug = request.args.get('category') or request.form.get('category')
    pro_pk = request.args.get('pro') or request.form.get('pro')
    cat = Category.query.filter_by(slug=cat_slug).first()
    if not cat:
        cats = Category.query.order_by(Category.id).all()
        return render_template('project_start.html', cats=cats)
    questions = cat.question_list
    if request.method == 'POST':
        answers = []
        for i, q in enumerate(questions):
            val = request.form.get(f'f{i}', '').strip()
            if val:
                answers.append([q['q'], val])
        details = request.form.get('details', '').strip()
        timeline = request.form.get('timeline', 'Flexible on timeline')
        zip_ = request.form.get('zip', '').strip()
        if not current_user.is_authenticated:
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            name = request.form.get('name', '').strip()
            existing = User.query.filter_by(email=email).first() if email else None
            if existing:
                login_user(existing)
            elif email and password and name:
                user = User(username=email.split('@')[0][:40], email=email,
                            display_name=name,
                            password_hash=bcrypt.generate_password_hash(password).decode(),
                            zip=zip_ or None)
                db.session.add(user)
                db.session.flush()
                login_user(user)
            else:
                return redirect(url_for('login', next=request.url))
        project = Project(user_id=current_user.id, category_id=cat.id,
                          zip=zip_ or current_user.zip or DEFAULT_ZIP,
                          details=details, timeline=timeline,
                          answers=json.dumps(answers), status='matched')
        db.session.add(project)
        db.session.flush()
        seed_matches(project)
        flash(f'We found {len(project.matches)} pros that match your project.')
        return redirect(url_for('project_view', project_id=project.id))
    user_zip = current_user.zip if current_user.is_authenticated else None
    return render_template('project_new.html', cat=cat, questions=questions,
                           pro_pk=pro_pk, zip=user_zip or DEFAULT_ZIP)


@app.route('/projects/<int:project_id>')
@login_required
def project_view(project_id):
    project = db.session.get(Project, project_id) or abort(404)
    if project.user_id != current_user.id:
        abort(403)
    return render_template('project.html', project=project)


@app.route('/projects/<int:project_id>/hire/<int:match_id>', methods=['POST'])
@login_required
def project_hire(project_id, match_id):
    project = db.session.get(Project, project_id) or abort(404)
    if project.user_id != current_user.id:
        abort(403)
    match = db.session.get(ProjectMatch, match_id) or abort(404)
    if match.project_id != project.id:
        abort(404)
    if project.status in ('cancelled', 'hired', 'completed'):
        flash('This project can no longer be changed.')
        return redirect(url_for('project_view', project_id=project.id))
    if not match.responded:
        flash('This pro has not responded yet, so you cannot hire them.')
        return redirect(url_for('project_view', project_id=project.id))
    for m in project.matches:
        m.hired = (m.id == match.id)
    project.status = 'hired'
    db.session.commit()
    flash(f'You hired {match.pro.name}.')
    return redirect(url_for('project_view', project_id=project.id))


@app.route('/projects/<int:project_id>/cancel', methods=['POST'])
@login_required
def project_cancel(project_id):
    project = db.session.get(Project, project_id) or abort(404)
    if project.user_id != current_user.id:
        abort(403)
    if project.status in ('hired', 'completed'):
        flash('A completed or hired project cannot be cancelled.')
        return redirect(url_for('project_view', project_id=project.id))
    project.status = 'cancelled'
    db.session.commit()
    flash('Your project has been cancelled.')
    return redirect(url_for('project_view', project_id=project.id))


@app.route('/projects/<int:project_id>/complete', methods=['POST'])
@login_required
def project_complete(project_id):
    project = db.session.get(Project, project_id) or abort(404)
    if project.user_id != current_user.id:
        abort(403)
    if project.status != 'hired':
        flash('Only hired projects can be marked complete.')
        return redirect(url_for('project_view', project_id=project.id))
    project.status = 'completed'
    db.session.commit()
    flash('Project marked complete. Consider leaving your pro a review.')
    return redirect(url_for('project_view', project_id=project.id))


@app.route('/projects/<int:project_id>/review', methods=['GET', 'POST'])
@login_required
def project_review(project_id):
    project = db.session.get(Project, project_id) or abort(404)
    if project.user_id != current_user.id:
        abort(403)
    match = next((m for m in project.matches if m.hired), None)
    if not match:
        flash('Hire a pro before leaving a review for this project.')
        return redirect(url_for('project_view', project_id=project.id))
    if project.status not in ('hired', 'completed'):
        flash('This project is not in a reviewable state.')
        return redirect(url_for('project_view', project_id=project.id))
    existing = Review.query.filter_by(pro_id=match.pro_id, source='user',
                                      details=f'project:{project.id}').first()
    if request.method == 'POST':
        if existing:
            flash('You already reviewed this project.')
            return redirect(url_for('project_view', project_id=project.id))
        rating = int(request.form.get('rating', '5'))
        body = request.form.get('body', '').strip()
        if not body:
            flash('Please write a few words about the job.')
            return render_template('review_form.html', project=project,
                                   match=match)
        db.session.add(Review(pro_id=match.pro_id,
                              author=current_user.display_name,
                              date_str=MIRROR_DATE, rating=rating, body=body,
                              details=f'project:{project.id}', hired=True,
                              source='user'))
        if project.status == 'hired':
            project.status = 'completed'
        db.session.commit()
        flash('Thanks! Your review is now live on the pro profile.')
        return redirect(url_for('project_view', project_id=project.id))
    return render_template('review_form.html', project=project, match=match,
                           existing=existing)


@app.route('/prices')
def prices():
    guides = CostGuide.query.order_by(CostGuide.id).all()
    groups = {}
    for g in guides:
        groups.setdefault(g.group_name, []).append(g)
    featured = load_content()['price_featured']
    return render_template('prices.html', groups=groups, featured=featured)


@app.route('/p/<slug>')
def cost_guide(slug):
    guide = CostGuide.query.filter_by(slug=slug).first_or_404()
    pro_cat = (Category.query.filter_by(slug=guide.related_category).first()
               if guide.related_category else None)
    pros = (Pro.query.filter_by(category_id=pro_cat.id).order_by(
        Pro.rating.desc()).limit(4).all()) if pro_cat else []
    return render_template('cost_guide.html', guide=guide, pros=pros,
                           cat=pro_cat)


@app.route('/near-me')
def near_me():
    cats = Category.query.order_by(Category.id).all()
    groups = {}
    for c in cats:
        groups.setdefault(c.meta_group, []).append(c)
    popular = load_content()['near_me_popular']
    return render_template('near_me.html', groups=groups, popular=popular)


@app.route('/<state_abbr>/<city_slug>')
def city_page(state_abbr, city_slug):
    if state_abbr.upper() not in ('WA', 'OR', 'CA', 'NY', 'TX', 'FL', 'AZ', 'CO',
                                  'MA', 'GA', 'DC', 'IL'):
        abort(404)
    name = find_city_name(city_slug)
    if not name:
        abort(404)
    pros = [p for p in Pro.query.filter_by(state=state_abbr.upper()).all()
            if p.city == name]
    cats = {p.category for p in pros}
    cats = sorted(cats, key=lambda c: c.name)
    return render_template('city.html', city=name, state=state_abbr.upper(),
                           pros=pros, cats=cats)


@app.route('/guarantee')
def guarantee():
    blocks = load_content()['guarantee_blocks']
    return render_template('guarantee.html', blocks=blocks)


@app.route('/how-it-works')
def how_it_works():
    steps = load_content()['how_it_works']
    return render_template('how_it_works.html', steps=steps)


@app.route('/pro', methods=['GET', 'POST'])
def join_pro():
    cats = Category.query.order_by(Category.id).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        zip_ = request.form.get('zip', '').strip()
        cat_id = request.form.get('category_id', '')
        if not (name and email and phone and zip_ and cat_id.isdigit()):
            flash('Please complete every field to continue.')
        else:
            db.session.add(Enrollment(name=name, email=email, phone=phone,
                                     category_id=int(cat_id), zip=zip_))
            db.session.commit()
            flash('Thanks! A Thumbtack team member will reach out shortly.')
            return redirect(url_for('index'))
    return render_template('join_pro.html', cats=cats)


# ---------------------------------------------------------------- bootstrap --

INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS ix_pros_category_id ON pros (category_id)",
    "CREATE INDEX IF NOT EXISTS ix_pros_city ON pros (city)",
    "CREATE INDEX IF NOT EXISTS ix_reviews_pro_id ON reviews (pro_id)",
)


def create_schema() -> None:
    """create_all plus the deterministic explicit-index pass."""
    db.create_all()
    with db.engine.begin() as conn:
        for stmt in INDEX_STATEMENTS:
            conn.execute(db.text(stmt))


def seed_database():
    from seed_data import build_seed
    build_seed(db)


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    content = load_content()
    for spec in content['benchmark_users']:
        db.session.add(User(username=spec['username'], email=spec['email'],
                            display_name=spec['display_name'],
                            password_hash=BENCHMARK_PASSWORD_HASH,
                            phone=spec['phone'], zip=spec['zip'],
                            address=spec['address']))
    db.session.commit()
    seed_user_activity()


def seed_user_activity():
    """Pre-existing saved pros, projects, threads for the benchmark users."""
    if Project.query.count() > 0:
        return
    content = load_content()
    for spec in content['user_activity']:
        user = User.query.filter_by(email=spec['email']).first()
        if not user:
            continue
        for pk in spec['saved_pros']:
            pro = Pro.query.filter_by(service_pk=str(pk)).first()
            if pro:
                db.session.add(SavedPro(user_id=user.id, pro_id=pro.id))
        for proj in spec['projects']:
            cat = Category.query.filter_by(slug=proj['category']).first()
            if not cat:
                continue
            project = Project(user_id=user.id, category_id=cat.id,
                              zip=proj['zip'], details=proj['details'],
                              timeline=proj['timeline'],
                              answers=json.dumps(proj['answers']),
                              status=proj['status'])
            db.session.add(project)
            db.session.flush()
            seed_matches(project)
            for hire_pk in proj.get('hired', []):
                for m in project.matches:
                    if m.pro.service_pk == str(hire_pk):
                        m.hired = True
                        if m.responded and m.quote_amount is None:
                            m.quote_amount = pro_quote(m.pro, project)
            if proj['status'] in ('hired', 'completed'):
                for m in project.matches:
                    if m.hired:
                        project.status = proj['status']
        for th in spec.get('threads', []):
            pro = Pro.query.filter_by(service_pk=str(th['pro'])).first()
            if not pro:
                continue
            thread = Thread(user_id=user.id, pro_id=pro.id)
            db.session.add(thread)
            db.session.flush()
            for i, (sender, body) in enumerate(th['messages']):
                db.session.add(Message(thread_id=thread.id, sender=sender,
                                       body=body))
    db.session.commit()


with app.app_context():
    create_schema()
    seed_content()
    seed_database()
    seed_benchmark_users()


def main() -> None:
    """Standalone entry: build instance/thumbtack.db from scratch (idempotent)."""
    with app.app_context():
        create_schema()
        seed_content()
        seed_database()
        seed_benchmark_users()
    print('seeded')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)),
            debug=False)
