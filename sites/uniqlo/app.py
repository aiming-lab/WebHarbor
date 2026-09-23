#!/usr/bin/env python3
"""UNIQLO mirror — Flask application with full CRUD."""
import json
import os
import random
import re
from datetime import datetime
from itertools import groupby

from flask import (Flask, render_template, request, redirect, url_for,
                    flash, jsonify)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                          login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_bcrypt import Bcrypt
from wtforms import StringField, PasswordField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange
from sqlalchemy import func

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'uniqlo-mirror-dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'uniqlo.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to access your account.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

app.jinja_env.filters['from_json'] = json.loads

DEPARTMENTS = [
    ('women', 'WOMEN'),
    ('men', 'MEN'),
    ('kids', 'KIDS'),
    ('baby', 'BABY'),
]


# ----- Models -----

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), default='')
    address_line1 = db.Column(db.String(200), default='')
    address_line2 = db.Column(db.String(200), default='')
    city = db.Column(db.String(100), default='')
    state = db.Column(db.String(50), default='')
    zip_code = db.Column(db.String(20), default='')
    country = db.Column(db.String(50), default='United States')
    is_member = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(20), nullable=False, index=True)
    slug = db.Column(db.String(80), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)

    __table_args__ = (db.UniqueConstraint('department', 'slug', name='uq_category_dept_slug'),)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    product_group_id = db.Column(db.String(30), unique=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    department = db.Column(db.String(20), nullable=False, index=True)
    category_slug = db.Column(db.String(80), index=True)
    category_name = db.Column(db.String(120), default='')
    description = db.Column(db.Text, default='')
    material = db.Column(db.String(255), default='')
    image = db.Column(db.String(500), default='')  # main thumbnail (relative to /static)
    gallery_images = db.Column(db.Text, default='[]')  # JSON list of relative paths
    min_price = db.Column(db.Float, default=0.0)
    max_price = db.Column(db.Float, default=0.0)
    rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    upstream_url = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    variants = db.relationship('ProductVariant', backref='product', lazy=True, cascade='all, delete-orphan')

    def colors(self):
        seen = []
        for v in self.variants:
            if v.color not in seen:
                seen.append(v.color)
        return seen

    def sizes(self):
        seen = []
        for v in self.variants:
            if v.size not in seen:
                seen.append(v.size)
        return seen


class ProductVariant(db.Model):
    __tablename__ = 'product_variants'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    sku = db.Column(db.String(60), unique=True, index=True)
    color = db.Column(db.String(80), default='')
    size = db.Column(db.String(20), default='')
    price = db.Column(db.Float, nullable=False)
    in_stock = db.Column(db.Boolean, default=True)


class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    variant = db.relationship('ProductVariant')


class WishlistItem(db.Model):
    __tablename__ = 'wishlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product')


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_number = db.Column(db.String(40), unique=True, nullable=False)
    status = db.Column(db.String(30), default='processing')
    subtotal = db.Column(db.Float, default=0)
    shipping = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    ship_name = db.Column(db.String(120), default='')
    ship_address = db.Column(db.String(200), default='')
    ship_city = db.Column(db.String(100), default='')
    ship_state = db.Column(db.String(50), default='')
    ship_zip = db.Column(db.String(20), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

    def item_count(self):
        return sum(i.quantity for i in self.items)


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    product_name = db.Column(db.String(255), default='')
    product_image = db.Column(db.String(500), default='')
    color = db.Column(db.String(80), default='')
    size = db.Column(db.String(20), default='')
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0)

    product = db.relationship('Product')


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    author_name = db.Column(db.String(120), default='Anonymous')
    rating = db.Column(db.Integer, default=5)
    title = db.Column(db.String(200), default='')
    body = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ----- Login -----

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_globals():
    cart_count = 0
    if current_user.is_authenticated:
        cart_count = db.session.query(func.sum(CartItem.quantity)).filter_by(user_id=current_user.id).scalar() or 0
    categories_by_dept = {}
    for dept, _ in DEPARTMENTS:
        categories_by_dept[dept] = Category.query.filter_by(department=dept).order_by(Category.name).all()
    return {
        'cart_count': int(cart_count),
        'departments': DEPARTMENTS,
        'categories_by_dept': categories_by_dept,
        'csrf_token_value': generate_csrf(),
    }


# ----- Forms -----

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])


class ProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    phone = StringField('Phone', validators=[Optional()])
    address_line1 = StringField('Address Line 1', validators=[Optional()])
    address_line2 = StringField('Address Line 2', validators=[Optional()])
    city = StringField('City', validators=[Optional()])
    state = StringField('State', validators=[Optional()])
    zip_code = StringField('ZIP Code', validators=[Optional()])


class CheckoutForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    address = StringField('Address', validators=[DataRequired()])
    city = StringField('City', validators=[DataRequired()])
    state = StringField('State', validators=[DataRequired()])
    zip_code = StringField('ZIP Code', validators=[DataRequired()])
    card_number = StringField('Card Number', validators=[DataRequired()])
    card_exp = StringField('Expiration', validators=[DataRequired()])
    card_cvv = StringField('CVV', validators=[DataRequired()])


class ReviewForm(FlaskForm):
    rating = IntegerField('Rating', validators=[DataRequired(), NumberRange(min=1, max=5)])
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    body = TextAreaField('Review', validators=[DataRequired()])


# ----- Routes: browse -----

@app.route('/')
def index():
    featured = Product.query.order_by(func.random()).limit(12).all()
    bestsellers = Product.query.order_by(Product.review_count.desc()).limit(8).all()
    return render_template('index.html', featured=featured, bestsellers=bestsellers)


@app.route('/<department>')
def department_page(department):
    if department not in dict(DEPARTMENTS):
        return render_template('404.html'), 404
    cats = Category.query.filter_by(department=department).order_by(Category.name).all()
    products = Product.query.filter_by(department=department).order_by(func.random()).limit(24).all()
    return render_template('department.html', department=department, categories=cats, products=products)


@app.route('/<department>/<category_slug>')
def category_page(department, category_slug):
    if department not in dict(DEPARTMENTS):
        return render_template('404.html'), 404
    cat = Category.query.filter_by(department=department, slug=category_slug).first_or_404()
    sort_key = request.args.get('sort', '')
    q = Product.query.filter_by(department=department, category_slug=category_slug)
    if sort_key == 'price_low':
        q = q.order_by(Product.min_price.asc())
    elif sort_key == 'price_high':
        q = q.order_by(Product.min_price.desc())
    elif sort_key == 'rating':
        q = q.order_by(Product.rating.desc())
    else:
        q = q.order_by(Product.name.asc())
    products = q.all()
    return render_template('category.html', department=department, category=cat,
                            products=products, current_sort=sort_key)


@app.route('/product/<slug>')
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    related = Product.query.filter(
        Product.category_slug == product.category_slug,
        Product.department == product.department,
        Product.id != product.id
    ).order_by(func.random()).limit(4).all()
    reviews = Review.query.filter_by(product_id=product.id).order_by(Review.created_at.desc()).all()
    in_wishlist = False
    if current_user.is_authenticated:
        in_wishlist = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product.id).first() is not None
    return render_template('product_detail.html', product=product, related=related,
                            reviews=reviews, in_wishlist=in_wishlist, review_form=ReviewForm())


STOPWORDS = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with',
             'and', 'or', 'is', 'are', 'from', 'as', 'this', 'that'}


def _score_product(product, tokens):
    raw = ' '.join([
        product.name or '', product.description or '', product.material or '',
        product.category_name or '', product.department or '',
    ]).lower()
    hay_tokens = set(re.findall(r'[a-z0-9]+', raw))

    def _match(t):
        if t in hay_tokens:
            return True
        if len(t) > 3:
            if t.endswith('s') and t[:-1] in hay_tokens:
                return True
            if (t + 's') in hay_tokens:
                return True
        if len(t) >= 3:
            for hw in hay_tokens:
                if hw.startswith(t):
                    return True
        return False

    return sum(1 for t in tokens if _match(t))


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    candidates = Product.query.all()
    if q:
        tokens = [t for t in re.findall(r'[a-z0-9]+', q.lower())
                  if t and t not in STOPWORDS and len(t) >= 2]
        if tokens:
            min_required = 1 if len(tokens) <= 2 else (len(tokens) // 2) + 1
            scored = []
            for p in candidates:
                s = _score_product(p, tokens)
                if s >= min_required:
                    scored.append((s, p))
            seed = abs(hash(q.lower())) % (2 ** 31)
            rng = random.Random(seed)
            scored.sort(key=lambda x: -x[0])
            results = []
            for _, group in groupby(scored, key=lambda x: x[0]):
                bucket = [p for _, p in group]
                rng.shuffle(bucket)
                results.extend(bucket)
        else:
            results = candidates
    else:
        results = []
    return render_template('search.html', query=q, results=results)


# ----- Routes: auth / account -----

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Welcome back!', 'success')
            next_url = request.args.get('next')
            if not next_url or not next_url.startswith('/') or next_url.startswith('//'):
                next_url = url_for('index')
            return redirect(next_url)
        flash('Invalid email or password.', 'error')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower().strip()).first():
            flash('An account with that email already exists.', 'error')
        else:
            user = User(name=form.name.data.strip(), email=form.email.data.lower().strip())
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created — welcome to UNIQLO.', 'success')
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('index'))


@app.route('/account')
@login_required
def account():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('account.html', orders=orders)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        form.populate_obj(current_user)
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('account'))
    return render_template('edit_profile.html', form=form)


@app.route('/account/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    return render_template('order_detail.html', order=order)


# ----- Routes: cart -----

@app.route('/cart')
@login_required
def cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    subtotal = sum(i.variant.price * i.quantity for i in items)
    return render_template('cart.html', items=items, subtotal=round(subtotal, 2))


@app.route('/cart/add/<int:variant_id>', methods=['POST'])
@csrf.exempt
@login_required
def cart_add(variant_id):
    variant = ProductVariant.query.get_or_404(variant_id)
    qty = int(request.form.get('quantity', 1))
    existing = CartItem.query.filter_by(user_id=current_user.id, variant_id=variant_id).first()
    if existing:
        existing.quantity += qty
    else:
        db.session.add(CartItem(user_id=current_user.id, variant_id=variant_id, quantity=qty))
    db.session.commit()
    flash(f'Added {variant.product.name} to your cart.', 'success')
    return redirect(url_for('cart'))


@app.route('/api/cart/update', methods=['POST'])
@csrf.exempt
@login_required
def cart_update():
    data = request.get_json() or {}
    item = CartItem.query.filter_by(id=data.get('item_id'), user_id=current_user.id).first()
    if not item:
        return jsonify({'success': False}), 404
    qty = int(data.get('quantity', 1))
    if qty <= 0:
        db.session.delete(item)
    else:
        item.quantity = qty
    db.session.commit()
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    subtotal = sum(i.variant.price * i.quantity for i in items)
    return jsonify({'success': True, 'cart_count': sum(i.quantity for i in items), 'subtotal': round(subtotal, 2)})


@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@csrf.exempt
@login_required
def cart_remove(item_id):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash('Item removed from cart.', 'info')
    return redirect(url_for('cart'))


# ----- Routes: wishlist -----

@app.route('/wishlist')
@login_required
def wishlist():
    items = WishlistItem.query.filter_by(user_id=current_user.id).order_by(WishlistItem.added_at.desc()).all()
    return render_template('wishlist.html', items=items)


@app.route('/wishlist/toggle/<int:product_id>', methods=['POST'])
@csrf.exempt
@login_required
def wishlist_toggle(product_id):
    existing = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        added = False
    else:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=product_id))
        db.session.commit()
        added = True
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'added': added})
    return redirect(request.referrer or url_for('index'))


# ----- Routes: checkout -----

@app.route('/checkout', methods=['GET', 'POST'])
@csrf.exempt
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash('Your cart is empty.', 'info')
        return redirect(url_for('cart'))
    form = CheckoutForm()
    subtotal = sum(i.variant.price * i.quantity for i in items)
    shipping = 0.0 if subtotal >= 99 else 4.99
    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + shipping + tax, 2)
    if form.validate_on_submit():
        order = Order(
            user_id=current_user.id,
            order_number=f'UQ{random.randint(10**9, 10**10 - 1)}',
            status='processing', subtotal=round(subtotal, 2), shipping=shipping, tax=tax, total=total,
            ship_name=form.name.data, ship_address=form.address.data, ship_city=form.city.data,
            ship_state=form.state.data, ship_zip=form.zip_code.data,
        )
        db.session.add(order)
        db.session.flush()
        for i in items:
            db.session.add(OrderItem(
                order_id=order.id, product_id=i.variant.product_id,
                product_name=i.variant.product.name, product_image=i.variant.product.image,
                color=i.variant.color, size=i.variant.size, quantity=i.quantity, price=i.variant.price,
            ))
            db.session.delete(i)
        db.session.commit()
        flash('Order placed — thank you for shopping with UNIQLO.', 'success')
        return redirect(url_for('order_detail', order_id=order.id))
    return render_template('checkout.html', form=form, items=items, subtotal=round(subtotal, 2),
                            shipping=shipping, tax=tax, total=total)


# ----- Routes: reviews -----

@app.route('/product/<slug>/review', methods=['POST'])
@csrf.exempt
@login_required
def add_review(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    form = ReviewForm()
    if form.validate_on_submit():
        db.session.add(Review(
            product_id=product.id, author_name=current_user.name,
            rating=form.rating.data, title=form.title.data, body=form.body.data,
        ))
        product.review_count = Review.query.filter_by(product_id=product.id).count() + 1
        agg = db.session.query(func.avg(Review.rating)).filter_by(product_id=product.id).scalar() or form.rating.data
        product.rating = round(float(agg), 1)
        db.session.commit()
        flash('Thanks for your review!', 'success')
    return redirect(url_for('product_detail', slug=slug))


# ----- Errors -----

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template('500.html'), 500


@app.route('/_health')
def health():
    return {'ok': True, 'site': 'uniqlo'}


# ----- Seed Data -----

def seed_database():
    if Product.query.count() > 0:
        return
    from seed_data import run_seed
    run_seed(db, Category, Product, ProductVariant, Review)


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    from seed_data import run_seed_users
    run_seed_users(db, User, CartItem, WishlistItem, Order, OrderItem, ProductVariant, Product)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
