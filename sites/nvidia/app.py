#!/usr/bin/env python3
"""NVIDIA.com mirror — Flask app.

Models a faithful slice of nvidia.com for the WebHarbor benchmark: a product
catalog of GPUs/hardware (GeForce gaming, Studio/Professional, Data Center,
Embedded, Consumer Devices) with full spec sheets, a spec-comparison tool, a
driver finder, news, search, local demo accounts, buying information,
local wishlist, and product reviews. No orders or payments are accepted.
"""
import os
import re
import secrets
from datetime import datetime, date
from urllib.parse import urlsplit

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from wtforms import (StringField, PasswordField, TextAreaField, IntegerField,
                     SelectField, BooleanField)
from wtforms.validators import (DataRequired, Email, Length, EqualTo, Optional,
                                NumberRange)
from sqlalchemy import or_

from seed_data import (PRODUCTS, ARTICLES, DRIVERS, BENCHMARK_USERS,
                       NOTABLE_REVIEWS, BENCHMARK_ACTIVITY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
# Session signing key: environment override or a random per-process value, so a
# committed literal cannot be used to forge a session cookie (repair002, M4).
# Restarting the process invalidates existing sessions, which is expected for this
# benchmark mirror.
app.config['SECRET_KEY'] = os.environ.get('NVIDIA_SECRET_KEY') or secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = \
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'nvidia.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None
# Bound request bodies; over-large requests get the 413 handler below instead of
# being buffered into memory (repair002, M6).
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to continue.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

CATEGORIES = [
    ("GeForce Gaming", "geforce-gaming"),
    ("Studio / Professional", "studio-professional"),
    ("Data Center", "data-center"),
    ("Embedded", "embedded"),
    ("Consumer Devices", "consumer-devices"),
]
CAT_BY_SLUG = {s: n for n, s in CATEGORIES}
CAT_SLUG = {n: s for n, s in CATEGORIES}


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(120), default='')
    country = db.Column(db.String(60), default='United States')
    newsletter_opt_in = db.Column(db.Boolean, default=False)
    created = db.Column(db.DateTime, default=datetime(2026, 1, 1))

    cart_items = db.relationship('CartItem', backref='user', lazy=True,
                                 cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='user', lazy=True,
                             cascade='all, delete-orphan')
    wishlist = db.relationship('WishlistItem', backref='user', lazy=True,
                               cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='user', lazy=True,
                              cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(60), nullable=False, index=True)
    series = db.Column(db.String(80), default='')
    tagline = db.Column(db.String(240), default='')
    description = db.Column(db.Text, default='')
    price_usd = db.Column(db.Integer, nullable=True)   # null => "Contact sales"
    image = db.Column(db.String(240), default='')
    release_year = db.Column(db.Integer, nullable=True)
    in_stock = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    # spec sheet
    architecture = db.Column(db.String(60), default='')
    cuda_cores = db.Column(db.Integer, nullable=True)
    tensor_cores = db.Column(db.Integer, nullable=True)
    rt_cores = db.Column(db.Integer, nullable=True)
    memory_gb = db.Column(db.Integer, nullable=True)
    memory_type = db.Column(db.String(40), default='')
    memory_bandwidth = db.Column(db.String(40), default='')
    boost_clock_ghz = db.Column(db.Float, nullable=True)
    tdp_watts = db.Column(db.Integer, nullable=True)
    interface = db.Column(db.String(40), default='')
    recommended_psu_watts = db.Column(db.Integer, nullable=True)

    reviews = db.relationship('Review', backref='product', lazy=True,
                              cascade='all, delete-orphan')

    @property
    def category_slug(self):
        return CAT_SLUG.get(self.category, '')

    @property
    def avg_rating(self):
        rs = [r.rating for r in self.reviews]
        return round(sum(rs) / len(rs), 1) if rs else None

    @property
    def review_count(self):
        return len(self.reviews)

    @property
    def price_display(self):
        return f"${self.price_usd:,}" if self.price_usd else "Contact Sales"


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(160), default='')
    body = db.Column(db.Text, default='')
    created = db.Column(db.DateTime, default=datetime(2026, 3, 1))


class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    title = db.Column(db.String(240), nullable=False)
    category = db.Column(db.String(60), default='')
    author = db.Column(db.String(120), default='NVIDIA Newsroom')
    published = db.Column(db.Date, default=date(2026, 1, 1))
    excerpt = db.Column(db.Text, default='')
    body = db.Column(db.Text, default='')
    image = db.Column(db.String(240), default='')
    read_minutes = db.Column(db.Integer, default=4)


class Driver(db.Model):
    __tablename__ = 'drivers'
    id = db.Column(db.Integer, primary_key=True)
    product_series = db.Column(db.String(80), nullable=False, index=True)
    branch = db.Column(db.String(40), default='Game Ready')   # Game Ready / Studio
    version = db.Column(db.String(40), nullable=False)
    os = db.Column(db.String(60), default='Windows 11')
    released = db.Column(db.Date, default=date(2026, 1, 1))
    size_mb = db.Column(db.Integer, default=600)
    highlights = db.Column(db.Text, default='')
    download_count = db.Column(db.Integer, default=0)


class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product')


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created = db.Column(db.DateTime, default=datetime(2026, 4, 1))
    status = db.Column(db.String(40), default='Processing')
    total_usd = db.Column(db.Integer, default=0)
    items = db.relationship('OrderItem', backref='order', lazy=True,
                            cascade='all, delete-orphan')


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    name = db.Column(db.String(160))
    price_usd = db.Column(db.Integer)
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product')


class WishlistItem(db.Model):
    __tablename__ = 'wishlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    product = db.relationship('Product')


class NewsletterSubscriber(db.Model):
    __tablename__ = 'newsletter'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    topic = db.Column(db.String(60), default='GeForce')


SQLITE_MAX_INT = 2 ** 63 - 1


def fetch_or_404(model, pk):
    """db.session.get() with an explicit integer bound.

    SQLite cannot bind integers above 2**63-1, and passing one through the
    <int:...> converters made the ORM raise OverflowError -> HTTP 500
    (repair002, M3). Out-of-range ids are a missing row, not a server error.
    """
    if not isinstance(pk, int) or pk < 1 or pk > SQLITE_MAX_INT:
        abort(404)
    return db.session.get(model, pk) or abort(404)


@login_manager.user_loader
def load_user(uid):
    try:
        value = int(uid)
    except (TypeError, ValueError):
        return None
    if not 1 <= value <= SQLITE_MAX_INT:
        return None
    return db.session.get(User, value)


# --------------------------------------------------------------------------
# Forms
# --------------------------------------------------------------------------
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    name = StringField('Full name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm password',
                            validators=[DataRequired(), EqualTo('password')])
    newsletter_opt_in = BooleanField('Send me NVIDIA news and offers')


class AccountForm(FlaskForm):
    name = StringField('Full name', validators=[DataRequired(), Length(max=120)])
    company = StringField('Company', validators=[Optional(), Length(max=120)])
    country = StringField('Country', validators=[Optional(), Length(max=60)])
    newsletter_opt_in = BooleanField('Subscribe to the NVIDIA newsletter')


class PasswordForm(FlaskForm):
    current = PasswordField('Current password', validators=[DataRequired()])
    new = PasswordField('New password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm new password',
                            validators=[DataRequired(), EqualTo('new')])


class ReviewForm(FlaskForm):
    # An empty first option keeps the rating an explicit input: the task grades a
    # five-star review, so the field must not arrive pre-answered (repair002, M11).
    rating = SelectField('Rating', choices=[('', 'Select a rating')] + [(str(i), f'{i} stars') for i in range(5, 0, -1)],
                         validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired(), Length(max=160)])
    body = TextAreaField('Your review', validators=[DataRequired(), Length(max=2000)])


# --------------------------------------------------------------------------
# Search scoring — token overlap (NOT strict AND)
# --------------------------------------------------------------------------
def _tokenize(q):
    return [t for t in re.split(r'[^a-z0-9]+', (q or '').lower()) if t]


def _score(haystack, tokens):
    """Token overlap, with whole-number matching for numeric tokens.

    A single character (the "0" of a query such as "MLPerf Training 6.0") is not a
    meaningful token, and a numeric token must occur as a whole number instead of
    inside a longer number, so a numeric-heavy query no longer matches the whole
    catalog (audit NVIDIA--18: low). Word tokens keep substring matching, which is
    the mirror's documented token-overlap search.
    """
    if not tokens:
        return 0
    h = haystack.lower()
    score = 0
    for token in tokens:
        if len(token) < 2:
            continue
        if token.isdigit():
            if re.search(r'(?<!\d)' + re.escape(token) + r'(?!\d)', h):
                score += 1
        elif token in h:
            score += 1
    return score


def _product_hay(p):
    return ' '.join(str(x) for x in (p.name, p.category, p.series, p.tagline,
                                     p.description, p.architecture, p.memory_type))


def _article_hay(a):
    return ' '.join(str(x) for x in (a.title, a.category, a.author, a.excerpt, a.body))


# --------------------------------------------------------------------------
# Context
# --------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    # No form object is constructed here: building a FlaskForm reads request.form, which
    # raises RequestEntityTooLarge for an over-limit body and would turn the 413 handler
    # itself into a 500 (repair002, M6).
    return {'CATEGORIES': CATEGORIES, 'current_year': 2026}


# --------------------------------------------------------------------------
# Routes — browse
# --------------------------------------------------------------------------
# Dedicated hero artwork, installed from NVIDIA's own per-page media. The home hero
# and the two series heroes no longer reuse a product-card file, so no page shows the
# same image twice (audit NVIDIA--7/--12: 40-series hero reuse; NVIDIA--0/--3 and
# NVIDIA--7: the 5090 file shown twice on / and on the 50-series page).
FLAGSHIP_HERO_IMAGE = 'images/heroes/geforce-rtx-5090-hero.jpg'
FLAGSHIP_HERO_CAPTION = 'Official NVIDIA product render — GeForce RTX 5090 (hero image)'
SERIES_HEROES = {
    '50': ('images/heroes/geforce-rtx-50-series-hero.jpg',
           'Official NVIDIA marketing image — GeForce RTX 50 Series'),
    '40': ('images/heroes/geforce-rtx-40-series-hero.jpg',
           'Official NVIDIA product render — GeForce RTX 4090'),
}


@app.route('/')
def index():
    # Name order keeps this curated strip from implying a price ranking (repair002, L7).
    featured = Product.query.filter_by(is_featured=True).order_by(
        Product.name).limit(6).all()
    if not featured:
        featured = Product.query.limit(6).all()
    latest_news = Article.query.order_by(Article.published.desc()).limit(3).all()
    flagship = Product.query.filter_by(slug='geforce-rtx-5090').first()
    return render_template('index.html', featured=featured, latest_news=latest_news,
                           flagship=flagship, hero_image=FLAGSHIP_HERO_IMAGE,
                           hero_caption=FLAGSHIP_HERO_CAPTION)


@app.route('/products')
def products():
    cat = request.args.get('category', '').strip()
    series = request.args.get('series', '').strip()
    # Default ordering is neutral (name): ordering by "featured" put the
    # most-expensive Studio card first, which hinted the answer to the
    # most-memory task (repair002, L7).
    sort = request.args.get('sort', 'name')
    q = request.args.get('q', '').strip()

    query = Product.query
    cat_name = CAT_BY_SLUG.get(cat)
    if cat_name:
        query = query.filter(Product.category == cat_name)
    if series:
        query = query.filter(Product.series == series)
    items = query.all()

    tokens = _tokenize(q)
    if tokens:
        scored = [(s, p) for p in items if (s := _score(_product_hay(p), tokens)) > 0]
        scored.sort(key=lambda sp: (-sp[0], -(sp[1].price_usd or 0)))
        items = [p for _, p in scored]
    elif sort == 'price-low':
        items.sort(key=lambda p: (p.price_usd or 10**9))
    else:  # name
        items.sort(key=lambda p: p.name.casefold())

    series_list = sorted({p.series for p in Product.query.all() if p.series})
    return render_template('products.html', items=items, cat=cat, cat_name=cat_name,
                           series=series, series_list=series_list, sort=sort, q=q)


@app.route('/products/<slug>')
def product_detail(slug):
    p = Product.query.filter_by(slug=slug).first_or_404()
    related = Product.query.filter(Product.category == p.category,
                                   Product.id != p.id).limit(4).all()
    in_wishlist = False
    if current_user.is_authenticated:
        in_wishlist = WishlistItem.query.filter_by(
            user_id=current_user.id, product_id=p.id).first() is not None
    reviews = Review.query.filter_by(product_id=p.id).order_by(Review.created.desc()).all()
    return render_template('product_detail.html', p=p, related=related,
                           in_wishlist=in_wishlist, reviews=reviews,
                           review_form=ReviewForm())


@app.route('/geforce/graphics-cards/<series_slug>/')
def geforce_series(series_slug):
    if series_slug not in ('50-series', '40-series'):
        abort(404)
    generation = series_slug[:2]
    # Family grid presented in a specification order (memory tier, then CUDA cores,
    # then name). The tile order no longer encodes the catalog price ranking, and
    # the cheapest model of the family is still the last tile, so the grid does not
    # pre-sort the "least expensive" question (audit NVIDIA--3: low; this used to be
    # `order_by(Product.price_usd.desc())`).
    items = Product.query.filter_by(series=f'RTX {generation} Series').all()
    items.sort(key=lambda p: (-(p.memory_gb or 0), -(p.cuda_cores or 0), p.name.casefold()))
    hero_image, hero_caption = SERIES_HEROES[generation]
    return render_template('geforce_series.html', generation=generation, items=items,
                           hero_image=hero_image, hero_caption=hero_caption)


@app.route('/where-to-buy')
def buying_options():
    items = Product.query.order_by(Product.category, Product.name).all()
    return render_template('buying_options.html', items=items)


@app.route('/where-to-buy/<slug>')
def where_to_buy(slug):
    p = Product.query.filter_by(slug=slug).first_or_404()
    in_wishlist = current_user.is_authenticated and WishlistItem.query.filter_by(
        user_id=current_user.id, product_id=p.id).first() is not None
    return render_template('where_to_buy.html', p=p, in_wishlist=in_wishlist)


@app.route('/compare')
def compare():
    ids = request.args.getlist('product') or request.args.get('ids', '').split(',')
    ids = list(dict.fromkeys(s.strip() for s in ids if s.strip()))
    items = []
    for s in ids:
        p = Product.query.filter_by(slug=s.strip()).first()
        if p:
            items.append(p)
    all_products = Product.query.order_by(Product.name).all()
    return render_template('compare.html', items=items, all_products=all_products)


@app.route('/drivers')
def drivers():
    series = request.args.get('series', '').strip()
    branch = request.args.get('branch', '').strip()
    os_filter = request.args.get('os', '').strip()
    query = Driver.query
    if series:
        query = query.filter(Driver.product_series == series)
    if branch:
        query = query.filter(Driver.branch == branch)
    if os_filter:
        query = query.filter(Driver.os == os_filter)
    searched = bool(series or branch or os_filter)
    results = query.order_by(Driver.released.desc()).all() if searched else []
    series_list = sorted({d.product_series for d in Driver.query.all()})
    os_list = sorted({d.os for d in Driver.query.all()})
    return render_template('drivers.html', results=results, series=series,
                           branch=branch, os_filter=os_filter,
                           series_list=series_list, os_list=os_list, searched=searched)


@app.route('/drivers/<int:driver_id>')
def driver_detail(driver_id):
    d = fetch_or_404(Driver, driver_id)
    return render_template('driver_detail.html', d=d)


@app.route('/drivers/<int:driver_id>/download', methods=['POST'])
def driver_download(driver_id):
    d = fetch_or_404(Driver, driver_id)
    d.download_count += 1
    db.session.commit()
    flash(f'Local download demo recorded: {d.product_series} driver {d.version} '
          f'({d.branch}). No driver file was downloaded.', 'success')
    return redirect(url_for('driver_detail', driver_id=driver_id))


@app.route('/news')
def news():
    cat = request.args.get('category', '').strip()
    query = Article.query
    if cat:
        query = query.filter(Article.category == cat)
    items = query.order_by(Article.published.desc()).all()
    cats = sorted({a.category for a in Article.query.all() if a.category})
    return render_template('news.html', items=items, cats=cats, cat=cat)


@app.route('/news/<slug>')
def news_detail(slug):
    a = Article.query.filter_by(slug=slug).first_or_404()
    more = Article.query.filter(Article.id != a.id).order_by(
        Article.published.desc()).limit(3).all()
    return render_template('news_detail.html', a=a, more=more)


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    tokens = _tokenize(q)
    products_found, articles_found = [], []
    if tokens:
        ps = [(s, p) for p in Product.query.all()
              if (s := _score(_product_hay(p), tokens)) > 0]
        ps.sort(key=lambda sp: (-sp[0], -(sp[1].price_usd or 0)))
        products_found = [p for _, p in ps]
        asc = [(s, a) for a in Article.query.all()
               if (s := _score(_article_hay(a), tokens)) > 0]
        asc.sort(key=lambda sa: -sa[0])
        articles_found = [a for _, a in asc]
    return render_template('search.html', q=q, products=products_found,
                           articles=articles_found)


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            nxt = request.form.get('next') or request.args.get('next')
            return redirect(local_return_path(nxt, url_for('account')))
        flash('Invalid email or password.', 'error')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
        else:
            u = User(email=email, name=form.name.data.strip(),
                     newsletter_opt_in=form.newsletter_opt_in.data)
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.commit()
            login_user(u)
            flash('Your local mirror account has been created.', 'success')
            return redirect(url_for('account'))
    return render_template('register.html', form=form)


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    # POST-only: a GET/HEAD prefetch, crawler or <img> must not end the session
    # (repair002, M5). GET returns 405 by Flask's method handling.
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('index'))


# --------------------------------------------------------------------------
# Account
# --------------------------------------------------------------------------
@app.route('/account')
@login_required
def account():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(
        Order.created.desc()).all()
    return render_template('account.html', orders=orders)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    form = AccountForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data.strip()
        current_user.company = form.company.data.strip()
        current_user.country = form.country.data.strip()
        current_user.newsletter_opt_in = form.newsletter_opt_in.data
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('account'))
    return render_template('account_edit.html', form=form)


@app.route('/account/password', methods=['GET', 'POST'])
@login_required
def account_password():
    form = PasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current.data):
            flash('Current password is incorrect.', 'error')
        else:
            current_user.set_password(form.new.data)
            db.session.commit()
            flash('Your password has been changed.', 'success')
            return redirect(url_for('account'))
    return render_template('account_password.html', form=form)


@app.route('/account/wishlist')
@login_required
def wishlist():
    items = WishlistItem.query.filter_by(user_id=current_user.id).all()
    return render_template('wishlist.html', items=items)


# --------------------------------------------------------------------------
# Legacy commerce URLs — read-only redirects; POST never mutates state
# --------------------------------------------------------------------------
@app.route('/cart')
def cart():
    return redirect(url_for('buying_options'))


@app.route('/cart/add/<int:product_id>', methods=['POST'])
def cart_add(product_id):
    return render_template('commerce_retired.html'), 410


@app.route('/cart/update/<int:item_id>', methods=['POST'])
def cart_update(item_id):
    return render_template('commerce_retired.html'), 410


@app.route('/cart/remove/<int:item_id>', methods=['POST'])
def cart_remove(item_id):
    return render_template('commerce_retired.html'), 410


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'GET':
        return redirect(url_for('buying_options'))
    return render_template('commerce_retired.html'), 410


@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    order = fetch_or_404(Order, order_id)
    if order.user_id != current_user.id:
        abort(403)
    return render_template('order_detail.html', order=order)


# --------------------------------------------------------------------------
# Wishlist + reviews + newsletter (POST actions)
# --------------------------------------------------------------------------
def local_return_path(value, fallback):
    """Keep login/POST returns on this mirror, including absolute same-origin refs."""
    if not value or '\\' in value or any(ord(c) < 32 for c in value):
        return fallback
    try:
        target = urlsplit(value)
        origin = urlsplit(request.host_url)
    except ValueError:
        return fallback
    if target.netloc and (target.scheme, target.netloc) != (origin.scheme, origin.netloc):
        return fallback
    if target.scheme and target.scheme not in ('http', 'https'):
        return fallback
    if not target.path.startswith('/') or target.path.startswith('//'):
        return fallback
    return target.path + ('?' + target.query if target.query else '')


@app.route('/wishlist/toggle/<int:product_id>', methods=['POST'])
@login_required
def wishlist_toggle(product_id):
    """Compatibility toggle. Prefer /wishlist/add or /wishlist/remove: a toggle
    reverses on a duplicated submit, while the explicit endpoints are idempotent
    (repair002, M8)."""
    p = fetch_or_404(Product, product_id)
    item = WishlistItem.query.filter_by(user_id=current_user.id, product_id=p.id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash(f'Removed {p.name} from your wishlist.', 'info')
    else:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=p.id))
        db.session.commit()
        flash(f'Saved {p.name} to your wishlist.', 'success')
    return redirect(local_return_path(request.referrer, url_for('product_detail', slug=p.slug)))


@app.route('/wishlist/add/<int:product_id>', methods=['POST'])
@login_required
def wishlist_add(product_id):
    """Idempotent save: repeating the same request leaves exactly one row."""
    p = fetch_or_404(Product, product_id)
    item = WishlistItem.query.filter_by(user_id=current_user.id, product_id=p.id).first()
    if item:
        flash(f'{p.name} is already in your wishlist.', 'info')
    else:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=p.id))
        db.session.commit()
        flash(f'Saved {p.name} to your wishlist.', 'success')
    return redirect(local_return_path(request.referrer, url_for('product_detail', slug=p.slug)))


@app.route('/wishlist/remove/<int:product_id>', methods=['POST'])
@login_required
def wishlist_remove(product_id):
    """Idempotent removal: repeating the same request leaves no row."""
    p = fetch_or_404(Product, product_id)
    item = WishlistItem.query.filter_by(user_id=current_user.id, product_id=p.id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash(f'Removed {p.name} from your wishlist.', 'info')
    else:
        flash(f'{p.name} is not in your wishlist.', 'info')
    return redirect(local_return_path(request.referrer, url_for('product_detail', slug=p.slug)))


@app.route('/products/<slug>/review', methods=['POST'])
@login_required
def add_review(slug):
    p = Product.query.filter_by(slug=slug).first_or_404()
    form = ReviewForm()
    if form.validate_on_submit():
        existing = Review.query.filter_by(product_id=p.id, user_id=current_user.id).first()
        if existing:
            flash('You have already reviewed this product.', 'info')
        else:
            db.session.add(Review(product_id=p.id, user_id=current_user.id,
                                  rating=int(form.rating.data),
                                  title=form.title.data.strip(),
                                  body=form.body.data.strip(),
                                  created=datetime(2026, 6, 1)))
            db.session.commit()
            flash('Thank you — your review has been posted.', 'success')
    else:
        flash('Please complete all review fields.', 'error')
    return redirect(url_for('product_detail', slug=slug))


EMAIL_MAX_LENGTH = 120  # matches the NewsletterSubscriber.email column


@app.route('/newsletter', methods=['POST'])
def newsletter():
    email = (request.form.get('email') or '').lower().strip()
    topic = (request.form.get('topic') or 'GeForce').strip()
    if not email or '@' not in email:
        flash('Please enter a valid email address.', 'error')
    elif len(email) > EMAIL_MAX_LENGTH or len(topic) > 60:
        # SQLite does not enforce VARCHAR lengths, so bound them here (repair002, M6).
        flash(f'Please use an email address of at most {EMAIL_MAX_LENGTH} characters.', 'error')
    elif NewsletterSubscriber.query.filter_by(email=email).first():
        flash('You are already subscribed.', 'info')
    else:
        db.session.add(NewsletterSubscriber(email=email, topic=topic))
        db.session.commit()
        flash(f'Subscribed to {topic} updates. Welcome aboard!', 'success')
    return redirect(local_return_path(request.referrer, url_for('index')))


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template('500.html'), 500


@app.errorhandler(413)
def request_too_large(e):
    return render_template('413.html', limit_mb=1), 413


# --------------------------------------------------------------------------
# Seeding — each function gated as a whole for byte-identical reset
# --------------------------------------------------------------------------
def seed_catalog():
    if Product.query.count() > 0:
        return
    for p in PRODUCTS:
        db.session.add(Product(**p))
    db.session.commit()


def seed_articles():
    if Article.query.count() > 0:
        return
    for a in ARTICLES:
        db.session.add(Article(**a))
    db.session.commit()


def seed_drivers():
    if Driver.query.count() > 0:
        return
    for d in DRIVERS:
        db.session.add(Driver(**d))
    db.session.commit()


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    for u in BENCHMARK_USERS:
        user = User(email=u['email'], name=u['name'], company=u.get('company', ''),
                    country=u.get('country', 'United States'),
                    newsletter_opt_in=u.get('newsletter_opt_in', False),
                    created=datetime(2026, 1, 1))
        # Deterministic hash when the catalog pins one, so a regenerated seed is
        # byte-identical to the shipped one (bcrypt salts are random otherwise)
        # (repair002, L4).
        if u.get('password_hash'):
            user.password_hash = u['password_hash']
        else:
            user.set_password(u['password'])
        db.session.add(user)
    db.session.commit()


def seed_reviews():
    if Review.query.count() > 0:
        return
    for r in NOTABLE_REVIEWS:
        user = User.query.filter_by(email=r['user_email']).first()
        prod = Product.query.filter_by(slug=r['product_slug']).first()
        if user and prod:
            db.session.add(Review(product_id=prod.id, user_id=user.id,
                                  rating=r['rating'], title=r['title'],
                                  body=r['body'], created=datetime(2026, 3, 1)))
    db.session.commit()


def seed_benchmark_activity():
    """Pre-populate benchmark users' wishlists / orders so their account pages
    feel lived-in. Gated as a whole. Deliberately avoids tasks.jsonl targets."""
    if Order.query.count() > 0 or WishlistItem.query.count() > 0:
        return
    for act in BENCHMARK_ACTIVITY:
        user = User.query.filter_by(email=act['user_email']).first()
        if not user:
            continue
        for slug in act.get('wishlist', []):
            p = Product.query.filter_by(slug=slug).first()
            if p:
                db.session.add(WishlistItem(user_id=user.id, product_id=p.id))
        for o in act.get('orders', []):
            prods = [Product.query.filter_by(slug=s).first() for s in o['products']]
            prods = [p for p in prods if p]
            if not prods:
                continue
            total = sum(p.price_usd or 0 for p in prods)
            order = Order(user_id=user.id, status=o.get('status', 'Delivered'),
                          created=datetime(2026, 4, 1), total_usd=total)
            db.session.add(order)
            db.session.flush()
            for p in prods:
                db.session.add(OrderItem(order_id=order.id, product_id=p.id,
                                         name=p.name, price_usd=p.price_usd, quantity=1))
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_catalog()
    seed_articles()
    seed_drivers()
    seed_benchmark_users()
    seed_reviews()
    seed_benchmark_activity()


@app.route('/_health')
def health():
    return {'ok': True, 'site': 'nvidia',
            'products': Product.query.count(),
            'articles': Article.query.count()}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
