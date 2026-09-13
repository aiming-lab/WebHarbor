"""Y Combinator mirror.

Original site contributed by realberry (@myberry2026) in aiming-lab/WebHarbor#31.
Reviewer pass: every runtime row now comes from `instance_seed/y_combinator.db`,
which `seed_data.py` rebuilds deterministically from the tracked, upstream-sourced
`source_data.json`. No page reads JSON at request time and no field is generated.
"""
import json
import os
import re

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'y_combinator.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'webharbor-y_combinator-dev-key'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

PAGE_SIZE = 24


# --------------------------------------------------------------- models

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    name = db.Column(db.String(100))
    password = db.Column(db.String(60), nullable=False)
    newsletter = db.Column(db.Boolean, default=False, nullable=False)


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    batch = db.Column(db.String(40))
    batch_code = db.Column(db.String(16))
    industry = db.Column(db.String(80))
    subindustry = db.Column(db.String(160))
    stage = db.Column(db.String(40))
    status = db.Column(db.String(40))
    regions = db.Column(db.Text)          # JSON list
    tags = db.Column(db.Text)             # JSON list
    one_liner = db.Column(db.Text)
    long_description = db.Column(db.Text)
    website = db.Column(db.String(300))
    year_founded = db.Column(db.Integer)
    team_size = db.Column(db.Integer)
    location = db.Column(db.String(160))
    city = db.Column(db.String(120))
    country = db.Column(db.String(80))
    top_company = db.Column(db.Boolean, default=False, nullable=False)
    is_hiring = db.Column(db.Boolean, default=False, nullable=False)
    group_partner = db.Column(db.String(120))
    linkedin_url = db.Column(db.String(300))
    twitter_url = db.Column(db.String(300))
    github_url = db.Column(db.String(300))
    crunchbase_url = db.Column(db.String(300))
    logo = db.Column(db.String(200))
    founders = db.relationship('Founder', backref='company', lazy=True,
                               order_by='Founder.id')
    news = db.relationship('CompanyNews', backref='company', lazy=True,
                           order_by='CompanyNews.position')

    @property
    def tag_list(self):
        return json.loads(self.tags) if self.tags else []

    @property
    def region_list(self):
        return json.loads(self.regions) if self.regions else []


class CompanyNews(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    title = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(500))
    date = db.Column(db.String(40))
    position = db.Column(db.Integer, default=0, nullable=False)


class Founder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    title = db.Column(db.String(120))
    bio = db.Column(db.Text)
    avatar = db.Column(db.String(200))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))


class Staff(db.Model):
    """A person on /people. Kept apart from Founder: upstream treats YC staff and
    startup founders as different collections, and the original mirror's shared
    table leaked unlinked founders into the staff directory."""
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    title = db.Column(db.String(160))
    bio = db.Column(db.Text)
    photo = db.Column(db.String(200))
    group = db.Column(db.String(120))
    group_order = db.Column(db.Integer, default=0, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)


class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.Text, nullable=False)
    published_at = db.Column(db.String(40))
    excerpt = db.Column(db.Text)
    body = db.Column(db.Text)
    reading_time = db.Column(db.Integer)
    author = db.Column(db.String(120))
    tag = db.Column(db.String(80))
    feature_image = db.Column(db.String(200))


carousel_articles = db.Table(
    'carousel_articles',
    db.Column('carousel_id', db.Integer, db.ForeignKey('library_carousel.id'), primary_key=True),
    db.Column('article_id', db.Integer, db.ForeignKey('library_article.id'), primary_key=True),
    db.Column('position', db.Integer, nullable=False, default=0),
)


class LibraryArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    description = db.Column(db.Text)
    author = db.Column(db.String(120))
    series = db.Column(db.String(120))
    created_at = db.Column(db.String(40))
    youtube_id = db.Column(db.String(40))
    view_count = db.Column(db.Integer)
    duration_seconds = db.Column(db.Integer)
    link = db.Column(db.String(300))
    thumbnail = db.Column(db.String(200))

    @property
    def duration_label(self):
        if not self.duration_seconds:
            return None
        minutes, seconds = divmod(int(self.duration_seconds), 60)
        return f"{minutes}:{seconds:02d}"


class LibraryCarousel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    articles = db.relationship('LibraryArticle', secondary=carousel_articles,
                               lazy='subquery',
                               order_by=carousel_articles.c.position)


class Bookmark(db.Model):
    """Library bookmarks — the upstream library exposes a per-user bookmark list."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('library_article.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'article_id', name='uq_bookmark'),)


class Launch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.Text, nullable=False)
    tagline = db.Column(db.Text)
    created_at = db.Column(db.String(40))
    vote_count = db.Column(db.Integer, default=0, nullable=False)
    company_name = db.Column(db.String(160))
    company_slug = db.Column(db.String(120))
    company_batch = db.Column(db.String(40))
    company_industry = db.Column(db.String(80))
    company_url = db.Column(db.String(300))
    company_tags = db.Column(db.Text)
    logo = db.Column(db.String(200))

    @property
    def tag_list(self):
        return json.loads(self.company_tags) if self.company_tags else []


class LaunchVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    launch_id = db.Column(db.Integer, db.ForeignKey('launch.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'launch_id', name='uq_launch_vote'),)


class FAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(120))
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)


class LegalDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group = db.Column(db.String(80))
    title = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(500))
    filename = db.Column(db.String(200))
    position = db.Column(db.Integer, default=0, nullable=False)


class StaticPage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)


class HomeBlock(db.Model):
    """One rendered element of the landing page, kept in the DB so no request
    handler reads a JSON file (see AGENTS.md 'Runtime data lives in the DB')."""
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(40), nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    payload = db.Column(db.Text, nullable=False)

    @property
    def data(self):
        return json.loads(self.payload)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def home_blocks(kind):
    rows = HomeBlock.query.filter_by(kind=kind).order_by(HomeBlock.position).all()
    return [r.data for r in rows]


def home_block(kind):
    rows = home_blocks(kind)
    return rows[0] if rows else None


@app.context_processor
def inject_nav():
    return {'nav_sections': NAV_SECTIONS}


NAV_SECTIONS = [
    ('About', '/about', [('What Happens at YC?', '/about'), ('Apply', '/apply'),
                         ('YC Interview Guide', '/interviews'), ('FAQ', '/faq'),
                         ('People', '/people'), ('YC Blog', '/blog')]),
    ('Companies', '/companies', [('Startup Directory', '/companies'),
                                 ('Founder Directory', '/founders'),
                                 ('Launch YC', '/launches')]),
    ('Library', '/library', []),
]
NAV_RIGHT = [
    ('Partners', '/people', []),
    ('Resources', '/library', [('Newsletter', '/subscribe'),
                               ('Requests for Startups', '/rfs'),
                               ('For Investors', '/investors'),
                               ('Verify Founders', '/verify'),
                               ('SAFE', '/safe'),
                               ('Find a Co-Founder', '/cofounder-matching')]),
    ('Startup Jobs', '/jobs', []),
]


@app.context_processor
def inject_nav_right():
    return {'nav_right': NAV_RIGHT}


# --------------------------------------------------------------- pages

@app.route('/')
def index():
    return render_template(
        'index.html',
        hero=home_block('hero') or {},
        narrative=home_blocks('narrative'),
        before_now=home_blocks('before_now'),
        about_quotes=home_blocks('about_quote'),
        featured_quote=home_block('featured_quote'),
        about_strip=home_blocks('about_strip'),
        cta_strip=home_blocks('cta_strip'),
        in_the_room=home_blocks('in_the_room'),
        partner_sections=home_blocks('partner_section'),
        knowledge_feature=home_block('knowledge_feature'),
        knowledge_thumbnails=home_blocks('knowledge_thumbnail'),
        startup_news=home_blocks('startup_news'),
        pg_essays=home_blocks('pg_essay'),
        logos=home_blocks('logo'),
    )


STOPWORDS = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'and', 'or',
             'is', 'are'}


def tokenize(query):
    return [t for t in re.findall(r'\w+', (query or '').lower()) if t not in STOPWORDS]


def paginate(items, page):
    total = len(items)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page, 1), pages)
    start = (page - 1) * PAGE_SIZE
    return items[start:start + PAGE_SIZE], {'page': page, 'pages': pages, 'total': total}


@app.route('/companies')
def companies():
    q = request.args.get('q', '').strip()
    batch = request.args.get('batch', '').strip()
    industry = request.args.get('industry', '').strip()
    stage = request.args.get('stage', '').strip()
    status = request.args.get('status', '').strip()
    hiring = request.args.get('hiring', '').strip()
    tag = request.args.get('tag', '').strip()

    query = Company.query
    if batch:
        query = query.filter(Company.batch == batch)
    if industry:
        query = query.filter(Company.industry == industry)
    if stage:
        query = query.filter(Company.stage == stage)
    if status:
        query = query.filter(Company.status == status)
    if hiring == 'true':
        query = query.filter(Company.is_hiring.is_(True))
    rows = query.order_by(Company.name).all()
    if tag:
        rows = [c for c in rows if tag in c.tag_list]

    tokens = tokenize(q)
    if tokens:
        scored = []
        for c in rows:
            haystack = ' '.join(filter(None, [
                c.name, c.one_liner, c.long_description, c.batch, c.industry,
                ' '.join(c.tag_list), c.location,
            ])).lower()
            score = sum(1 for t in tokens if t in haystack)
            if score:
                scored.append((-score, c.name.lower(), c.slug, c))
        rows = [c for _, _, _, c in sorted(scored)]

    page_rows, page_info = paginate(rows, request.args.get('page', 1, type=int))
    facets = {
        'batches': [b for (b,) in db.session.query(Company.batch).distinct()
                    .order_by(Company.batch) if b],
        'industries': [i for (i,) in db.session.query(Company.industry).distinct()
                       .order_by(Company.industry) if i],
        'stages': [s for (s,) in db.session.query(Company.stage).distinct()
                   .order_by(Company.stage) if s],
        'statuses': [s for (s,) in db.session.query(Company.status).distinct()
                     .order_by(Company.status) if s],
    }
    return render_template('companies.html', companies=page_rows, page_info=page_info,
                           q=q, current_batch=batch, current_industry=industry,
                           current_stage=stage, current_status=status,
                           current_hiring=hiring, current_tag=tag, **facets)


@app.route('/companies/<slug>')
def company_detail(slug):
    company = Company.query.filter_by(slug=slug).first_or_404()
    launches = Launch.query.filter_by(company_slug=slug).order_by(
        Launch.created_at.desc()).all()
    return render_template('company_detail.html', company=company, launches=launches)


@app.route('/founders')
def founders():
    q = request.args.get('q', '').strip()
    batch = request.args.get('batch', '').strip()
    rows = Founder.query.order_by(Founder.name).all()
    if batch:
        rows = [f for f in rows if f.company and f.company.batch == batch]
    tokens = tokenize(q)
    if tokens:
        picked = []
        for f in rows:
            haystack = ' '.join(filter(None, [
                f.name, f.title, f.bio,
                f.company.name if f.company else None,
                f.company.batch if f.company else None,
            ])).lower()
            score = sum(1 for t in tokens if t in haystack)
            if score:
                picked.append((-score, f.name.lower(), f.slug, f))
        rows = [f for _, _, _, f in sorted(picked)]
    page_rows, page_info = paginate(rows, request.args.get('page', 1, type=int))
    batches = [b for (b,) in db.session.query(Company.batch).distinct()
               .order_by(Company.batch) if b]
    return render_template('founders.html', founders=page_rows, page_info=page_info,
                           q=q, current_batch=batch, batches=batches)


@app.route('/founders/<slug>')
def founder_detail(slug):
    """Upstream redirects a founder permalink to the company profile that carries
    the founder's bio; the mirror keeps that behaviour."""
    founder = Founder.query.filter_by(slug=slug).first_or_404()
    if founder.company:
        return redirect(url_for('company_detail', slug=founder.company.slug))
    abort(404)


@app.route('/people')
def people():
    rows = Staff.query.order_by(Staff.group_order, Staff.position).all()
    sections = []
    for person in rows:
        if not sections or sections[-1]['title'] != person.group:
            sections.append({'title': person.group, 'people': []})
        sections[-1]['people'].append(person)
    return render_template('people.html', sections=sections)


@app.route('/people/<slug>')
def person_detail(slug):
    person = Staff.query.filter_by(slug=slug).first_or_404()
    return render_template('person_detail.html', person=person)


@app.route('/blog')
def blog():
    page_rows, page_info = paginate(
        BlogPost.query.order_by(BlogPost.published_at.desc()).all(),
        request.args.get('page', 1, type=int))
    return render_template('blog.html', posts=page_rows, page_info=page_info)


@app.route('/blog/<slug>')
def blog_detail(slug):
    post = BlogPost.query.filter_by(slug=slug).first_or_404()
    return render_template('blog_detail.html', post=post)


@app.route('/library')
def library():
    q = request.args.get('q', '').strip()
    if q:
        tokens = tokenize(q)
        rows = []
        for article in LibraryArticle.query.order_by(LibraryArticle.title).all():
            haystack = ' '.join(filter(None, [
                article.title, article.summary, article.description,
                article.author, article.series])).lower()
            score = sum(1 for t in tokens if t in haystack)
            if score:
                rows.append((-score, article.title.lower(), article.slug, article))
        results = [a for _, _, _, a in sorted(rows)]
        return render_template('library.html', carousels=None, results=results, q=q)
    carousels = LibraryCarousel.query.order_by(LibraryCarousel.sort_order).all()
    return render_template('library.html', carousels=carousels, results=None, q=q)


@app.route('/library/<slug>')
def library_detail(slug):
    article = LibraryArticle.query.filter_by(slug=slug).first_or_404()
    bookmarked = False
    if current_user.is_authenticated:
        bookmarked = Bookmark.query.filter_by(
            user_id=current_user.id, article_id=article.id).first() is not None
    return render_template('library_detail.html', article=article, bookmarked=bookmarked)


@app.route('/library/<slug>/bookmark', methods=['POST'])
@login_required
def toggle_bookmark(slug):
    article = LibraryArticle.query.filter_by(slug=slug).first_or_404()
    existing = Bookmark.query.filter_by(user_id=current_user.id,
                                        article_id=article.id).first()
    if existing:
        db.session.delete(existing)
        flash('Removed from your bookmarks.', 'success')
    else:
        db.session.add(Bookmark(user_id=current_user.id, article_id=article.id))
        flash('Saved to your bookmarks.', 'success')
    db.session.commit()
    return redirect(url_for('library_detail', slug=slug))


@app.route('/library/bookmarks')
@login_required
def bookmarks():
    rows = (LibraryArticle.query.join(Bookmark, Bookmark.article_id == LibraryArticle.id)
            .filter(Bookmark.user_id == current_user.id)
            .order_by(LibraryArticle.title).all())
    return render_template('bookmarks.html', articles=rows)


@app.route('/launches')
def launches():
    page_rows, page_info = paginate(
        Launch.query.order_by(Launch.created_at.desc()).all(),
        request.args.get('page', 1, type=int))
    return render_template('launches.html', launches=page_rows, page_info=page_info)


@app.route('/launches/<slug>')
def launch_detail(slug):
    launch = Launch.query.filter_by(slug=slug).first_or_404()
    company = Company.query.filter_by(slug=launch.company_slug).first()
    voted = False
    if current_user.is_authenticated:
        voted = LaunchVote.query.filter_by(
            user_id=current_user.id, launch_id=launch.id).first() is not None
    return render_template('launch_detail.html', launch=launch, company=company,
                           voted=voted)


@app.route('/launches/<slug>/vote', methods=['POST'])
@login_required
def vote_launch(slug):
    launch = Launch.query.filter_by(slug=slug).first_or_404()
    existing = LaunchVote.query.filter_by(user_id=current_user.id,
                                          launch_id=launch.id).first()
    if existing:
        db.session.delete(existing)
        launch.vote_count = max(0, launch.vote_count - 1)
        flash('Upvote removed.', 'success')
    else:
        db.session.add(LaunchVote(user_id=current_user.id, launch_id=launch.id))
        launch.vote_count = launch.vote_count + 1
        flash('Thanks for the upvote!', 'success')
    db.session.commit()
    return redirect(url_for('launch_detail', slug=slug))


@app.route('/faq')
def faq():
    rows = FAQ.query.order_by(FAQ.position).all()
    groups = []
    for row in rows:
        if not groups or groups[-1]['category'] != row.category:
            groups.append({'category': row.category, 'questions': []})
        groups[-1]['questions'].append(row)
    return render_template('faq.html', groups=groups)


@app.route('/safe')
def safe():
    groups = []
    for doc in LegalDocument.query.order_by(LegalDocument.position).all():
        if not groups or groups[-1]['name'] != doc.group:
            groups.append({'name': doc.group, 'docs': []})
        groups[-1]['docs'].append(doc)
    return render_template('safe.html', groups=groups)


@app.route('/documents')
def documents():
    return redirect(url_for('safe'))


@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Sign in to subscribe to the YC newsletter.', 'danger')
            return redirect(url_for('login'))
        current_user.newsletter = True
        db.session.commit()
        flash('You are subscribed to the YC newsletter.', 'success')
        return redirect(url_for('subscribe'))
    return render_template('subscribe.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Login unsuccessful. Please check the email and password.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        name = (request.form.get('name') or '').strip()
        if not email or not password:
            flash('Email and password are required.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('That email is already registered.', 'danger')
        else:
            db.session.add(User(email=email, name=name or None,
                                password=bcrypt.generate_password_hash(password).decode('utf-8')))
            db.session.commit()
            flash('Your account has been created. You can log in now.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/<page_slug>')
def static_page(page_slug):
    page = StaticPage.query.filter_by(slug=page_slug).first()
    if not page:
        abort(404)
    return render_template('static_page.html', page=page)


@app.errorhandler(404)
def not_found(_error):
    return render_template('404.html'), 404


# --------------------------------------------------------------- bootstrap

if not os.environ.get('WEBSYN_SKIP_BOOTSTRAP'):
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=40024)
