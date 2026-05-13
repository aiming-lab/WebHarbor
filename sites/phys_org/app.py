"""Phys.org mirror — Flask application."""
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort, jsonify)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from wtforms import StringField, PasswordField, TextAreaField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, Email
from sqlalchemy import or_, desc, func
from markupsafe import Markup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config['SECRET_KEY'] = 'phys-org-mirror-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'phys_org.db')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to continue.'
csrf = CSRFProtect(app)


# ----- Sanitize filter (for body HTML) -----

SAFE_TAGS = re.compile(
    r'<(?!/?(?:a|p|i|b|em|strong|code|pre|br|ul|ol|li|h2|h3|blockquote)\b)[^>]+>',
    re.IGNORECASE
)


@app.template_filter('sanitize')
def sanitize_html(text):
    if not text:
        return ''
    cleaned = SAFE_TAGS.sub('', text)
    return Markup(cleaned)


@app.template_filter('time_ago')
def time_ago_filter(dt):
    if not dt:
        return ''
    return _time_ago(dt)


def _time_ago(dt: datetime) -> str:
    now = datetime.utcnow()
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return f"{max(seconds, 0)}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 14:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return dt.strftime('%b %d, %Y')


# ----- Models -----

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(200), default='')
    bio = db.Column(db.Text, default='')
    location = db.Column(db.String(120), default='')
    interests = db.Column(db.String(255), default='')   # comma-separated category slugs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default='')
    sort_order = db.Column(db.Integer, default=100)

    articles = db.relationship('Article', backref='category', lazy='dynamic')

    @property
    def article_count(self):
        return Article.query.filter_by(category_id=self.id).count()


class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    subtitle = db.Column(db.String(500), default='')
    body = db.Column(db.Text, default='')               # paragraphs separated by \n\n
    author_name = db.Column(db.String(200), default='Phys.org Staff')
    source_journal = db.Column(db.String(200), default='')
    source_institution = db.Column(db.String(200), default='')
    doi_url = db.Column(db.String(500), default='')
    image_filename = db.Column(db.String(200), default='')   # under static/images/
    subsection = db.Column(db.String(120), default='')       # e.g., 'Optics & Photonics'
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    featured = db.Column(db.Boolean, default=False)

    comments = db.relationship('Comment', backref='article',
                               cascade='all, delete-orphan', lazy='dynamic')
    saves = db.relationship('SavedArticle', backref='article',
                            cascade='all, delete-orphan', lazy='dynamic')

    @property
    def comment_count(self):
        return self.comments.count()

    @property
    def save_count(self):
        return self.saves.count()

    @property
    def reading_time(self):
        wc = len((self.body or '').split())
        return max(1, wc // 220)

    def get_paragraphs(self):
        return [p.strip() for p in re.split(r"\n\n+", self.body or '') if p.strip()]

    @property
    def published_str(self):
        return _time_ago(self.published_at) if self.published_at else ''


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)
    score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='comments')
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]),
                              lazy='dynamic')

    @property
    def time_ago(self):
        return _time_ago(self.created_at)


class SavedArticle(db.Model):
    __tablename__ = 'saved_articles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False, index=True)
    note = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'article_id'),)

    user = db.relationship('User', backref='saved')


class SearchHistory(db.Model):
    __tablename__ = 'search_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    query_text = db.Column('query', db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='searches')


# ----- Forms -----

class LoginForm(FlaskForm):
    email = StringField('Email or username', validators=[DataRequired(), Length(3, 200)])
    password = PasswordField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(2, 80)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(3, 200)])
    full_name = StringField('Full name', validators=[Optional(), Length(0, 200)])
    password = PasswordField('Password', validators=[DataRequired(), Length(6, 128)])


class ProfileForm(FlaskForm):
    full_name = StringField('Full name', validators=[Optional(), Length(0, 200)])
    bio = TextAreaField('Bio', validators=[Optional(), Length(0, 2000)])
    location = StringField('Location', validators=[Optional(), Length(0, 120)])
    interests = StringField('Interests (comma separated category slugs)',
                            validators=[Optional(), Length(0, 255)])


class CommentForm(FlaskForm):
    text = TextAreaField('Comment', validators=[DataRequired(), Length(1, 2000)])
    parent_id = HiddenField()


class SaveForm(FlaskForm):
    note = StringField('Note', validators=[Optional(), Length(0, 500)])


# ----- Auth -----

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ----- Helpers -----

STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
              'or', 'is', 'it', 'by', 'with', 'as', 'be', 'this', 'that',
              'are', 'was', 'were', 'from', 'how', 'what', 'why', 'we', 'i'}


def tokenize(query: str):
    return [t.lower() for t in re.split(r'\W+', query or '')
            if t.lower() not in STOP_WORDS and len(t) > 1]


def _safe_next(target: str | None, fallback: str) -> str:
    """Return ``target`` only if it is a same-origin path on this app.

    Login and save handlers accept a `next=` parameter so the user lands
    back where they came from. Without validation, an attacker could
    pass `next=https://evil.example.com` and turn the site into an
    open-redirect gadget. We accept only relative paths that have no
    scheme/netloc, otherwise we fall back."""
    if not target:
        return fallback
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return fallback
    if not target.startswith('/'):
        return fallback
    return target


def _flatten_comments(comments, depth=0):
    result = []
    for c in comments:
        result.append({'comment': c, 'depth': depth})
        children = c.replies.order_by(Comment.created_at).all()
        result.extend(_flatten_comments(children, depth + 1))
    return result


@app.context_processor
def inject_globals():
    cats = Category.query.order_by(Category.sort_order, Category.name).all()
    return {'all_categories': cats, 'site_name': 'Phys.org Mirror'}


# ----- Routes -----

@app.route('/')
def index():
    featured = Article.query.filter_by(featured=True) \
        .order_by(desc(Article.published_at)).limit(5).all()
    latest = Article.query.order_by(desc(Article.published_at)).limit(20).all()
    cats = Category.query.order_by(Category.sort_order).all()
    by_cat = []
    for c in cats:
        items = Article.query.filter_by(category_id=c.id) \
            .order_by(desc(Article.published_at)).limit(4).all()
        if items:
            by_cat.append((c, items))
    sidebar_trending = Article.query.order_by(desc(Article.views)).limit(6).all()
    return render_template('index.html', featured=featured, latest=latest,
                           by_cat=by_cat, sidebar_trending=sidebar_trending)


@app.route('/category/<slug>')
def category(slug):
    cat = Category.query.filter_by(slug=slug).first_or_404()
    page = request.args.get('page', 1, type=int)
    sort = request.args.get('sort', 'recent')
    q = Article.query.filter_by(category_id=cat.id)
    if sort == 'popular':
        q = q.order_by(desc(Article.views), desc(Article.published_at))
    else:
        q = q.order_by(desc(Article.published_at))
    pagination = q.paginate(page=page, per_page=12, error_out=False)
    sidebar_trending = Article.query.order_by(desc(Article.views)).limit(6).all()
    return render_template('category.html', category=cat, pagination=pagination,
                           sort=sort, sidebar_trending=sidebar_trending)


@app.route('/article/<slug>')
def article_detail(slug):
    art = Article.query.filter_by(slug=slug).first_or_404()
    # Note: we deliberately do NOT increment views on GET. `views` is the
    # seeded popularity signal used by trending/popular sort and by
    # benchmark tasks (Phys.org--3, --10, --15). Mutating it on every page
    # view would let an agent's browsing order shift task answers and
    # would break /reset/<site> byte-identity. If a future task needs a
    # runtime visit counter, add a separate column for that.
    top_comments = Comment.query.filter_by(article_id=art.id, parent_id=None) \
        .order_by(Comment.created_at).all()
    comment_tree = _flatten_comments(top_comments)
    related = Article.query.filter(Article.category_id == art.category_id,
                                   Article.id != art.id) \
        .order_by(desc(Article.published_at)).limit(4).all()
    is_saved = False
    if current_user.is_authenticated:
        is_saved = SavedArticle.query.filter_by(
            user_id=current_user.id, article_id=art.id).first() is not None
    form = CommentForm()
    save_form = SaveForm()
    return render_template('article_detail.html', article=art, comment_tree=comment_tree,
                           related=related, form=form, save_form=save_form,
                           is_saved=is_saved)


@app.route('/article/<slug>/comment', methods=['POST'])
@login_required
def post_comment(slug):
    art = Article.query.filter_by(slug=slug).first_or_404()
    form = CommentForm()
    if not form.validate_on_submit():
        flash('Comment could not be posted.', 'error')
        return redirect(url_for('article_detail', slug=slug))

    parent_id = None
    raw_parent = (form.parent_id.data or '').strip()
    if raw_parent:
        try:
            candidate = int(raw_parent)
        except ValueError:
            flash('Invalid reply target.', 'error')
            return redirect(url_for('article_detail', slug=slug))
        parent = db.session.get(Comment, candidate)
        # Reject replies whose parent doesn't exist or belongs to a different
        # article — prevents cross-article reply injection via crafted forms.
        if parent is None or parent.article_id != art.id:
            flash('Invalid reply target.', 'error')
            return redirect(url_for('article_detail', slug=slug))
        parent_id = candidate

    c = Comment(text=form.text.data.strip(), user_id=current_user.id,
                article_id=art.id, parent_id=parent_id)
    db.session.add(c)
    db.session.commit()
    flash('Comment posted.', 'success')
    return redirect(url_for('article_detail', slug=slug) + f'#comment-{c.id}')


@app.route('/save/<int:article_id>', methods=['POST'])
@login_required
def save_article(article_id):
    art = Article.query.get_or_404(article_id)
    existing = SavedArticle.query.filter_by(
        user_id=current_user.id, article_id=art.id).first()
    form = SaveForm()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Removed from your saved list.', 'info')
    else:
        note = form.note.data.strip() if form.note.data else ''
        s = SavedArticle(user_id=current_user.id, article_id=art.id, note=note)
        db.session.add(s)
        db.session.commit()
        flash('Article saved.', 'success')
    next_url = _safe_next(request.form.get('next'),
                          url_for('article_detail', slug=art.slug))
    return redirect(next_url)


@app.route('/saved')
@login_required
def saved():
    items = SavedArticle.query.filter_by(user_id=current_user.id) \
        .order_by(desc(SavedArticle.created_at)).all()
    return render_template('saved.html', items=items)


@app.route('/trending')
def trending():
    page = request.args.get('page', 1, type=int)
    pagination = Article.query.order_by(desc(Article.views), desc(Article.published_at)) \
        .paginate(page=page, per_page=15, error_out=False)
    return render_template('trending.html', pagination=pagination)


@app.route('/search')
def search():
    q = (request.args.get('q') or '').strip()
    page = request.args.get('page', 1, type=int)
    cat_filter = (request.args.get('category') or '').strip()

    if not q:
        return render_template('search.html', query='', results=[], page=1,
                               total=0, has_next=False, has_prev=False,
                               selected_category=cat_filter)

    if current_user.is_authenticated:
        sh = SearchHistory(user_id=current_user.id, query_text=q)
        db.session.add(sh)
        db.session.commit()

    tokens = tokenize(q)
    if not tokens:
        return render_template('search.html', query=q, results=[], page=1,
                               total=0, has_next=False, has_prev=False,
                               selected_category=cat_filter)

    base = Article.query
    if cat_filter:
        cat = Category.query.filter_by(slug=cat_filter).first()
        if cat:
            base = base.filter(Article.category_id == cat.id)

    filters = []
    for token in tokens:
        like = f'%{token}%'
        filters.append(or_(Article.title.ilike(like),
                           Article.subtitle.ilike(like),
                           Article.body.ilike(like)))
    candidates = base.filter(or_(*filters)).limit(800).all()

    scored = []
    for art in candidates:
        blob = f"{art.title}\n{art.subtitle}\n{art.body}".lower()
        score = sum(1 for t in tokens if t in blob)
        if score > 0:
            scored.append((art, score))
    scored.sort(key=lambda x: (-x[1],
                               -(x[0].published_at.timestamp() if x[0].published_at else 0)))

    per_page = 12
    total = len(scored)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = [a for a, _ in scored[start:end]]
    return render_template('search.html', query=q, results=page_items, page=page,
                           total=total, has_next=end < total, has_prev=page > 1,
                           selected_category=cat_filter)


@app.route('/user/<username>')
def user_profile(username):
    u = User.query.filter_by(username=username).first_or_404()
    saved_count = SavedArticle.query.filter_by(user_id=u.id).count()
    comment_count = Comment.query.filter_by(user_id=u.id).count()
    recent_comments = Comment.query.filter_by(user_id=u.id) \
        .order_by(desc(Comment.created_at)).limit(10).all()
    return render_template('user.html', user=u, saved_count=saved_count,
                           comment_count=comment_count, recent_comments=recent_comments)


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data or ''
        current_user.bio = form.bio.data or ''
        current_user.location = form.location.data or ''
        current_user.interests = form.interests.data or ''
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('account'))
    history = SearchHistory.query.filter_by(user_id=current_user.id) \
        .order_by(desc(SearchHistory.created_at)).limit(20).all()
    return render_template('account.html', form=form, search_history=history)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(
            (User.email == form.email.data) | (User.username == form.email.data)
        ).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            next_page = _safe_next(request.args.get('next'),
                                   url_for('index'))
            return redirect(next_page)
        flash('Invalid email or password.', 'error')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered.', 'error')
        elif User.query.filter_by(username=form.username.data).first():
            flash('Username already taken.', 'error')
        else:
            pw = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            u = User(username=form.username.data, email=form.email.data,
                    full_name=form.full_name.data or '', password_hash=pw)
            db.session.add(u)
            db.session.commit()
            login_user(u)
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/_health')
def _health():
    return {'ok': True, 'site': 'phys_org'}


# ----- Seed bootstrap -----

from seed_data import seed_database, seed_benchmark_users   # noqa: E402

with app.app_context():
    db.create_all()
    seed_database(db, User, Category, Article, Comment, bcrypt)
    seed_benchmark_users(db, User, Category, Article, Comment, SavedArticle, SearchHistory, bcrypt)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
