#!/usr/bin/env python3
"""WebMD mirror — Flask application.

Routes + SQLAlchemy models for an offline mirror of webmd.com. Runtime data
comes entirely from instance/webmd.db (seeded from instance_seed/webmd.db at
boot). No JSON read at request time.

Determinism: the site clock is pinned to BENCHMARK_TODAY (2025-01-10). No
func.random() and no real clocks are used anywhere a page renders.
"""
import os
import re
from datetime import datetime, date

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from sqlalchemy import or_, func
from sqlalchemy.orm import selectinload

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'webmd-mirror-secret-key'
# DB path is overridable so seed-regeneration tooling can write
# instance_seed/ instead of the runtime instance/. Default = runtime DB.
DB_PATH = os.environ.get('WEBMD_DB_PATH',
                         os.path.join(BASE_DIR, 'instance', 'webmd.db'))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your account.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

# Frozen benchmark date: keeps "today", trending, and dates deterministic.
BENCHMARK_TODAY = date(2025, 1, 10)

STOPWORDS = {'a', 'an', 'the', 'of', 'to', 'in', 'on', 'for', 'and', 'or',
             'is', 'are', 'be', 'with', 'as', 'by', 'at', 'from', 'what',
             'how', 'your', 'you'}

LETTERS = [chr(c) for c in range(ord('A'), ord('Z') + 1)]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime,
                           default=lambda: datetime(2025, 1, 10, 9, 0, 0))

    saved_articles = db.relationship('SavedArticle', backref='user',
                                     lazy=True, cascade='all, delete-orphan')
    reading_history = db.relationship('ReadingHistory', backref='user',
                                      lazy=True, cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Section(db.Model):
    __tablename__ = 'sections'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    blurb = db.Column(db.String(255), default='')

    articles = db.relationship('Article', backref='section', lazy=True)


class Author(db.Model):
    __tablename__ = 'authors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    role = db.Column(db.String(40), nullable=False)  # writer|medical reviewer
    credentials = db.Column(db.String(120), default='')
    bio = db.Column(db.Text, default='')
    image = db.Column(db.String(200), default='')

    articles = db.relationship('Article', backref='author', lazy=True,
                               foreign_keys='Article.author_id')
    reviewed_articles = db.relationship('Article', backref='reviewer',
                                        lazy=True,
                                        foreign_keys='Article.reviewer_id')


class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'),
                           nullable=False)
    subcategory = db.Column(db.String(80), default='', index=True)
    summary = db.Column(db.Text, default='')
    body_html = db.Column(db.Text, default='')
    author_id = db.Column(db.Integer, db.ForeignKey('authors.id'),
                          nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('authors.id'),
                            nullable=False)
    published_date = db.Column(db.Date, nullable=False)
    reviewed_date = db.Column(db.Date, nullable=False)
    image = db.Column(db.String(200), default='')

    saved_by = db.relationship('SavedArticle', backref='article', lazy=True,
                               cascade='all, delete-orphan')


class Drug(db.Model):
    __tablename__ = 'drugs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    generic_name = db.Column(db.String(200), default='')
    brand_names = db.Column(db.String(255), default='')
    drug_class = db.Column(db.String(200), default='')
    category = db.Column(db.String(80), default='', index=True)
    uses = db.Column(db.Text, default='')
    dosage = db.Column(db.Text, default='')
    side_effects_common = db.Column(db.Text, default='')
    side_effects_serious = db.Column(db.Text, default='')
    interactions = db.Column(db.Text, default='')
    warnings = db.Column(db.Text, default='')
    image = db.Column(db.String(200), default='')


condition_symptoms = db.Table(
    'condition_symptoms',
    db.Column('condition_id', db.Integer, db.ForeignKey('conditions.id'),
              primary_key=True),
    db.Column('symptom_id', db.Integer, db.ForeignKey('symptoms.id'),
              primary_key=True),
)


class Condition(db.Model):
    __tablename__ = 'conditions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    letter = db.Column(db.String(1), nullable=False, index=True)
    overview = db.Column(db.Text, default='')
    symptoms = db.Column(db.Text, default='')
    causes = db.Column(db.Text, default='')
    treatments = db.Column(db.Text, default='')
    related_drug_slugs = db.Column(db.Text, default='')  # comma-separated
    image = db.Column(db.String(200), default='')

    symptom_links = db.relationship('Symptom', secondary=condition_symptoms,
                                    backref='conditions', lazy=True)

    def related_drugs(self):
        slugs = [s for s in (self.related_drug_slugs or '').split(',') if s]
        if not slugs:
            return []
        rows = Drug.query.filter(Drug.slug.in_(slugs)).all()
        by_slug = {d.slug: d for d in rows}
        return [by_slug[s] for s in slugs if s in by_slug]


class Symptom(db.Model):
    __tablename__ = 'symptoms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)


class SavedArticle(db.Model):
    __tablename__ = 'saved_articles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'),
                           nullable=False)
    created_at = db.Column(db.DateTime,
                           default=lambda: datetime(2025, 1, 10, 12, 0, 0))


class ReadingHistory(db.Model):
    __tablename__ = 'reading_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'),
                           nullable=False)
    created_at = db.Column(db.DateTime,
                           default=lambda: datetime(2025, 1, 10, 12, 0, 0))

    article = db.relationship('Article', lazy=True)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

class RegisterForm(FlaskForm):
    name = StringField('Full Name',
                       validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password',
                             validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm Password',
                            validators=[DataRequired(), EqualTo('password')])


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class PasswordChangeForm(FlaskForm):
    current_password = PasswordField('Current Password',
                                     validators=[DataRequired()])
    new_password = PasswordField('New Password',
                                 validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm New Password',
                            validators=[DataRequired(),
                                        EqualTo('new_password')])


# ---------------------------------------------------------------------------
# Search (scored token overlap, not strict AND)
# ---------------------------------------------------------------------------

def _tokens(q):
    return [t for t in re.findall(r'[a-z0-9]+', q.lower())
            if t not in STOPWORDS and len(t) >= 2]


def _score(tokens, name, haystack):
    name = name.lower()
    score = 0
    for t in tokens:
        if name == t:
            score += 6
        elif name.startswith(t):
            score += 4
        elif t in name:
            score += 3
        elif t in haystack:
            score += 1
    return score


def search_all(q):
    """Return (articles, drugs, conditions) lists ordered by score."""
    tokens = _tokens(q)
    if not tokens:
        return [], [], []
    like = f'%{tokens[0]}%'
    min_req = max(1, len(tokens) // 2)

    art_rows = Article.query.filter(or_(
        Article.title.ilike(like), Article.summary.ilike(like),
        Article.body_html.ilike(like),
        *[Article.title.ilike(f'%{t}%') for t in tokens[1:]],
    )).limit(80).all()
    arts = []
    for a in art_rows:
        hay = ' '.join([a.title, a.summary or '', a.subcategory or '',
                        a.body_html or '']).lower()
        s = _score(tokens, a.title, hay)
        if s >= min_req:
            arts.append((s, a))

    drug_rows = Drug.query.filter(or_(
        Drug.name.ilike(like), Drug.generic_name.ilike(like),
        Drug.brand_names.ilike(like), Drug.uses.ilike(like),
        *[Drug.name.ilike(f'%{t}%') for t in tokens[1:]],
        *[Drug.brand_names.ilike(f'%{t}%') for t in tokens[1:]],
    )).limit(60).all()
    drugs = []
    for d in drug_rows:
        hay = ' '.join([d.name, d.generic_name or '', d.brand_names or '',
                        d.drug_class or '', d.uses or '']).lower()
        s = _score(tokens, d.name, hay)
        if s >= min_req:
            drugs.append((s, d))

    cond_rows = Condition.query.filter(or_(
        Condition.name.ilike(like), Condition.overview.ilike(like),
        Condition.symptoms.ilike(like),
        *[Condition.name.ilike(f'%{t}%') for t in tokens[1:]],
    )).limit(60).all()
    conds = []
    for c in cond_rows:
        hay = ' '.join([c.name, c.overview or '', c.symptoms or '',
                        c.causes or '', c.treatments or '']).lower()
        s = _score(tokens, c.name, hay)
        if s >= min_req:
            conds.append((s, c))

    arts.sort(key=lambda x: (-x[0], x[1].title))
    drugs.sort(key=lambda x: (-x[0], x[1].name))
    conds.sort(key=lambda x: (-x[0], x[1].name))
    return ([a for _, a in arts], [d for _, d in drugs],
            [c for _, c in conds])


def _record_history(article):
    if current_user.is_authenticated:
        db.session.add(ReadingHistory(
            user_id=current_user.id, article_id=article.id,
            created_at=datetime(BENCHMARK_TODAY.year, BENCHMARK_TODAY.month,
                                BENCHMARK_TODAY.day, 12, 0, 0)))
        db.session.commit()


# ---------------------------------------------------------------------------
# Routes — core browsing
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    # Deterministic homepage: hero = newest news article; trending = a fixed
    # ordering (reviewed_date desc, then title). No randomness anywhere.
    hero = (Article.query.join(Section)
            .filter(Section.slug == 'news')
            .order_by(Article.published_date.desc(), Article.title)
            .first())
    sections = Section.query.order_by(Section.id).all()
    section_cards = []
    for s in sections:
        top = (Article.query.filter_by(section_id=s.id)
               .filter(Article.id != (hero.id if hero else -1))
               .order_by(Article.published_date.desc(), Article.title)
               .limit(3).all())
        section_cards.append((s, top))
    trending = (Article.query
                .filter(Article.id != (hero.id if hero else -1))
                .order_by(Article.reviewed_date.desc(), Article.title)
                .limit(6).all())
    return render_template('index.html', hero=hero,
                           section_cards=section_cards, trending=trending)


@app.route('/section/<slug>')
def section_view(slug):
    section = Section.query.filter_by(slug=slug).first_or_404()
    subcat = request.args.get('topic', '').strip()
    q = Article.query.filter_by(section_id=section.id)
    if subcat:
        q = q.filter(Article.subcategory == subcat)
    articles = q.order_by(Article.published_date.desc(),
                          Article.title).all()
    subcats = [r[0] for r in db.session.query(Article.subcategory)
               .filter(Article.section_id == section.id)
               .distinct().order_by(Article.subcategory).all()]
    return render_template('section.html', section=section,
                           articles=articles, subcats=subcats,
                           active_subcat=subcat)


@app.route('/articles/<slug>')
def article_detail(slug):
    article = Article.query.filter_by(slug=slug).first_or_404()
    _record_history(article)
    is_saved = False
    if current_user.is_authenticated:
        is_saved = SavedArticle.query.filter_by(
            user_id=current_user.id,
            article_id=article.id).first() is not None
    related = (Article.query
               .filter(Article.section_id == article.section_id,
                       Article.id != article.id)
               .order_by(Article.published_date.desc(), Article.title)
               .limit(4).all())
    return render_template('article_detail.html', article=article,
                           is_saved=is_saved, related=related)


@app.route('/authors/<slug>')
def author_detail(slug):
    author = Author.query.filter_by(slug=slug).first_or_404()
    written = (Article.query.filter_by(author_id=author.id)
               .order_by(Article.published_date.desc(), Article.title).all())
    reviewed = (Article.query.filter_by(reviewer_id=author.id)
                .order_by(Article.published_date.desc(),
                          Article.title).all())
    return render_template('author_detail.html', author=author,
                           written=written, reviewed=reviewed)


# ---------------------------------------------------------------------------
# Routes — drugs
# ---------------------------------------------------------------------------

@app.route('/drugs')
@app.route('/drugs/<letter>')
def drugs_index(letter=None):
    category = request.args.get('category', '').strip()
    q = Drug.query
    if letter:
        letter = letter.upper()
        if letter not in LETTERS:
            abort(404)
        q = q.filter(Drug.name.ilike(f'{letter}%'))
    if category:
        q = q.filter(Drug.category == category)
    drugs = q.order_by(Drug.name).all()
    active_letters = {r[0] for r in db.session.query(
        func.upper(func.substr(Drug.name, 1, 1))).distinct().all()}
    categories = [r[0] for r in db.session.query(Drug.category)
                  .distinct().order_by(Drug.category).all()]
    return render_template('drugs_index.html', drugs=drugs,
                           letters=LETTERS, active_letters=active_letters,
                           current_letter=letter, categories=categories,
                           active_category=category)


@app.route('/drug/<slug>')
def drug_detail(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    conditions = (Condition.query
                  .filter(Condition.related_drug_slugs
                          .ilike(f'%{drug.slug}%'))
                  .order_by(Condition.name).all())
    conditions = [c for c in conditions
                  if drug.slug in (c.related_drug_slugs or '').split(',')]
    same_category = (Drug.query
                     .filter(Drug.category == drug.category,
                             Drug.id != drug.id)
                     .order_by(Drug.name).limit(6).all())
    return render_template('drug_detail.html', drug=drug,
                           conditions=conditions,
                           same_category=same_category)


# ---------------------------------------------------------------------------
# Routes — conditions & symptom checker
# ---------------------------------------------------------------------------

@app.route('/conditions')
@app.route('/conditions/<letter>')
def conditions_index(letter=None):
    q = Condition.query
    if letter:
        letter = letter.upper()
        if letter not in LETTERS:
            abort(404)
        q = q.filter(Condition.letter == letter)
    conditions = q.order_by(Condition.name).all()
    active_letters = {r[0] for r in db.session.query(Condition.letter).all()}
    return render_template('conditions_index.html', conditions=conditions,
                           letters=LETTERS, active_letters=active_letters,
                           current_letter=letter)


@app.route('/condition/<slug>')
def condition_detail(slug):
    condition = Condition.query.filter_by(slug=slug).first_or_404()
    related_drugs = condition.related_drugs()
    related_articles = []
    tokens = _tokens(condition.name)
    if tokens:
        related_articles = (Article.query
                            .filter(or_(*[Article.title.ilike(f'%{t}%')
                                          for t in tokens]))
                            .order_by(Article.title).limit(4).all())
    return render_template('condition_detail.html', condition=condition,
                           related_drugs=related_drugs,
                           related_articles=related_articles)


@app.route('/symptom-checker', methods=['GET', 'POST'])
def symptom_checker():
    all_symptoms = Symptom.query.order_by(Symptom.name).all()
    if request.method == 'POST':
        picked_slugs = request.form.getlist('symptoms')
        picked = (Symptom.query.filter(Symptom.slug.in_(picked_slugs))
                  .order_by(Symptom.name).all())
        if not picked:
            flash('Select at least one symptom to check.', 'error')
            return redirect(url_for('symptom_checker'))
        picked_ids = {s.id for s in picked}
        results = []
        conds = (Condition.query
                 .options(selectinload(Condition.symptom_links))
                 .order_by(Condition.name).all())
        for cond in conds:
            cond_ids = {s.id for s in cond.symptom_links}
            overlap = picked_ids & cond_ids
            if overlap:
                results.append({
                    'condition': cond,
                    'matched': sorted(
                        (s for s in cond.symptom_links if s.id in overlap),
                        key=lambda s: s.name),
                    'match_count': len(overlap),
                    'total': len(cond_ids),
                })
        results.sort(key=lambda r: (-r['match_count'], r['condition'].name))
        return render_template('symptom_results.html', picked=picked,
                               results=results)
    return render_template('symptom_checker.html', symptoms=all_symptoms)


# ---------------------------------------------------------------------------
# Routes — search
# ---------------------------------------------------------------------------

@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return render_template('search.html', q='', articles=[], drugs=[],
                               conditions=[], total=0)
    articles, drugs, conditions = search_all(q)
    total = len(articles) + len(drugs) + len(conditions)
    return render_template('search.html', q=q, articles=articles,
                           drugs=drugs, conditions=conditions, total=total)


# ---------------------------------------------------------------------------
# Routes — auth & account
# ---------------------------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash('That email is already registered.', 'error')
        else:
            u = User(email=form.email.data.lower(),
                     name=form.name.data.strip())
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.commit()
            login_user(u)
            flash('Welcome to WebMD!', 'success')
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(
            email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    form = PasswordChangeForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'error')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Your password has been updated.', 'success')
            return redirect(url_for('account'))
    return render_template('account.html', form=form)


@app.route('/account/saved')
@login_required
def account_saved():
    saved = (SavedArticle.query.filter_by(user_id=current_user.id)
             .order_by(SavedArticle.created_at.desc(),
                       SavedArticle.id.desc())
             .all())
    return render_template('account_saved.html', saved=saved)


@app.route('/account/history')
@login_required
def account_history():
    history = (ReadingHistory.query.filter_by(user_id=current_user.id)
               .order_by(ReadingHistory.created_at.desc(),
                         ReadingHistory.id.desc())
               .limit(40).all())
    return render_template('account_history.html', history=history)


@app.route('/articles/<int:article_id>/save', methods=['POST'])
@login_required
def toggle_save(article_id):
    article = db.session.get(Article, article_id)
    if not article:
        abort(404)
    existing = SavedArticle.query.filter_by(
        user_id=current_user.id, article_id=article.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash(f'Removed "{article.title}" from your saved articles.', 'info')
    else:
        db.session.add(SavedArticle(user_id=current_user.id,
                                    article_id=article.id))
        db.session.commit()
        flash(f'Saved "{article.title}" to your articles.', 'success')
    return redirect(request.referrer
                    or url_for('article_detail', slug=article.slug))


# ---------------------------------------------------------------------------
# Health, errors, globals
# ---------------------------------------------------------------------------

@app.route('/_health')
def health():
    return {'ok': True, 'site': 'webmd',
            'articles': Article.query.count(),
            'drugs': Drug.query.count(),
            'conditions': Condition.query.count()}


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


@app.context_processor
def inject_globals():
    # Frozen to 2025 so the footer year matches BENCHMARK_TODAY and the site
    # is deterministic across runs.
    return {'current_year': 2025, 'benchmark_today': BENCHMARK_TODAY}


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

from seed_data import seed_database, seed_benchmark_users  # noqa: E402

with app.app_context():
    db.create_all()
    seed_database(db, Section, Article, Drug, Condition, Symptom, Author,
                  condition_symptoms)
    seed_benchmark_users(db, User, bcrypt, Article, SavedArticle,
                         ReadingHistory, BENCHMARK_TODAY)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
