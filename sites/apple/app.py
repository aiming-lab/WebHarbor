import os
import re
import json
import secrets
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, session, abort, Response
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, PasswordField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///apple_store.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='user', lazy=True)
    cart_items = db.relationship('CartItem', backref='user', lazy=True)
    wishlist_items = db.relationship('WishlistItem', backref='user', lazy=True)
    reviews = db.relationship('Review', backref='user', lazy=True)
    payment_methods = db.relationship('PaymentMethod', backref='user', lazy=True, cascade='all, delete-orphan')
    saved_addresses = db.relationship('SavedAddress', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(150), unique=True, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # iphone, mac, ipad, watch, airpods, accessories, tv, homepod, vision, audio
    subcategory = db.Column(db.String(60), default='')   # e.g. macbook-pro, macbook-air, ipad-pro, ipad-mini, airpods-pro, airpods-3, vision-pro-accessory
    subtitle = db.Column(db.String(300))
    description = db.Column(db.Text)
    slogan = db.Column(db.String(300), default='')
    price = db.Column(db.Float, nullable=False)
    monthly_price = db.Column(db.Float)
    months = db.Column(db.Integer, default=24)
    image = db.Column(db.String(300))
    hero_image = db.Column(db.String(300))
    color_options = db.Column(db.Text)   # JSON list
    storage_options = db.Column(db.Text) # JSON list (or size options for Watch)
    is_new = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    specs = db.Column(db.Text)           # JSON dict
    in_stock = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Phase 9 task-driven columns
    chip_family = db.Column(db.String(40), default='')     # e.g. M1, M2, M3, M3 Pro, M3 Max, A15, A17 Pro
    ram = db.Column(db.Integer, default=0)                 # GB
    ssd = db.Column(db.Integer, default=0)                 # GB
    screen_size = db.Column(db.Float, default=0.0)         # inches
    connectivity = db.Column(db.String(60), default='')    # Wi-Fi / Wi-Fi + Cellular / LTE / etc
    release_year = db.Column(db.Integer, default=2024)
    release_date = db.Column(db.String(40), default='')
    battery_life = db.Column(db.String(120), default='')   # "18 hours web browsing"
    weight = db.Column(db.String(60), default='')
    video_recording = db.Column(db.String(100), default='')
    processor = db.Column(db.String(80), default='')       # display processor for Apple TV / non-Mac
    gpu_cores = db.Column(db.Integer, default=0)
    cpu_cores = db.Column(db.Integer, default=0)
    feature_tags = db.Column(db.Text, default='[]')        # JSON list – kebab-case tags
    box_contents = db.Column(db.Text, default='[]')        # JSON list
    config_upgrades = db.Column(db.Text, default='{}')     # JSON dict for configurators
    tradein_value = db.Column(db.Float, default=0.0)
    tradein_eligible = db.Column(db.Boolean, default=False)
    support_url = db.Column(db.String(200), default='')
    keyboard_options = db.Column(db.Text, default='[]')    # JSON list (for Mac configurators)
    pickup_zip = db.Column(db.String(20), default='')      # nearest pickup zip
    pickup_available = db.Column(db.Boolean, default=True)

    def get_colors(self):
        try:
            return json.loads(self.color_options) if self.color_options else []
        except Exception:
            return []

    def get_storage(self):
        try:
            return json.loads(self.storage_options) if self.storage_options else []
        except Exception:
            return []

    def get_specs(self):
        try:
            return json.loads(self.specs) if self.specs else {}
        except Exception:
            return {}

    def get_feature_tags(self):
        try:
            return json.loads(self.feature_tags or '[]')
        except Exception:
            return []

    def get_box_contents(self):
        try:
            return json.loads(self.box_contents or '[]')
        except Exception:
            return []

    def get_config_upgrades(self):
        try:
            return json.loads(self.config_upgrades or '{}')
        except Exception:
            return {}

    def get_keyboard_options(self):
        try:
            return json.loads(self.keyboard_options or '[]')
        except Exception:
            return []


class SupportArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(150), unique=True, nullable=False)
    topic = db.Column(db.String(80), default='')      # e.g. apple-id, ios, iphone, mac, repair
    title = db.Column(db.String(300), nullable=False)
    summary = db.Column(db.Text, default='')
    body = db.Column(db.Text, default='')
    compat = db.Column(db.Text, default='[]')         # JSON list of compatible devices
    tags = db.Column(db.Text, default='[]')           # JSON list of kebab-case tags
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_compat(self):
        try:
            return json.loads(self.compat or '[]')
        except Exception:
            return []

    def get_tags(self):
        try:
            return json.loads(self.tags or '[]')
        except Exception:
            return []


class TradeInValue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device = db.Column(db.String(150), nullable=False)
    condition = db.Column(db.String(40), default='good')  # good, excellent, fair
    value = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    color = db.Column(db.String(50))
    storage = db.Column(db.String(50))
    memory = db.Column(db.String(80))
    unit_price = db.Column(db.Float)  # configured price (base + storage/memory deltas); fallback to product.price if None
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product', lazy=True)

    def effective_price(self):
        return self.unit_price if self.unit_price is not None else (self.product.price if self.product else 0)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(20), default='processing')  # processing, shipped, delivered, cancelled
    total = db.Column(db.Float, nullable=False)
    shipping_address = db.Column(db.String(300))
    shipping_method = db.Column(db.String(50), default='standard')
    payment_method = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)
    color = db.Column(db.String(50))
    storage = db.Column(db.String(50))
    product = db.relationship('Product', lazy=True)


class WishlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product', lazy=True)
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id'),)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    title = db.Column(db.String(200))
    body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product', lazy=True)


class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    card_type = db.Column(db.String(20), nullable=False)   # Visa, Mastercard, Amex
    last4 = db.Column(db.String(4), nullable=False)
    exp_month = db.Column(db.Integer, nullable=False)
    exp_year = db.Column(db.Integer, nullable=False)
    cardholder_name = db.Column(db.String(120), default='')
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedAddress(db.Model):
    __tablename__ = 'saved_addresses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    label = db.Column(db.String(50), default='Home')  # Home, Work, Gift, Other
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20), default='')
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

class LoginForm(FlaskForm):
    email = StringField('Apple ID (Email)', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')


class RegisterForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])


class CheckoutForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[DataRequired()])
    address = StringField('Address', validators=[DataRequired()])
    city = StringField('City', validators=[DataRequired()])
    state = StringField('State', validators=[DataRequired()])
    zip_code = StringField('ZIP Code', validators=[DataRequired()])
    shipping_method = SelectField('Shipping', choices=[
        ('standard', 'Standard Shipping - Free'),
        ('express', 'Express Shipping - $9.99'),
        ('overnight', 'Overnight Shipping - $19.99'),
    ])
    payment_method = SelectField('Payment', choices=[
        ('apple_pay', 'Apple Pay'),
        ('credit_card', 'Credit Card'),
        ('monthly', 'Monthly Installments'),
    ])


class ProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone')
    address = StringField('Address')
    city = StringField('City')
    state = StringField('State')
    zip_code = StringField('ZIP Code')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm', validators=[DataRequired(), EqualTo('new_password')])


class ReviewForm(FlaskForm):
    rating = SelectField('Rating', choices=[(str(i), f'{i} Star{"s" if i > 1 else ""}') for i in range(5, 0, -1)], validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    body = StringField('Review', validators=[DataRequired()])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Context processor - inject cart count into all templates
# ---------------------------------------------------------------------------

def load_gallery(slug):
    """Load product gallery images from JSON."""
    gallery_path = os.path.join(os.path.dirname(__file__), 'product_galleries.json')
    if os.path.exists(gallery_path):
        with open(gallery_path) as f:
            galleries = json.load(f)
        return galleries.get(slug, [])
    return []


@app.context_processor
def inject_cart_count():
    from flask_wtf.csrf import generate_csrf
    if current_user.is_authenticated:
        count = CartItem.query.filter_by(user_id=current_user.id).count()
    else:
        count = len(session.get('cart', []))
    return {'cart_count': count, 'csrf_token_value': generate_csrf()}


# ---------------------------------------------------------------------------
# Routes - Pages
# ---------------------------------------------------------------------------

@app.route('/')
def home():
    featured = Product.query.filter_by(is_featured=True).limit(12).all()
    new_products = Product.query.filter_by(is_new=True).limit(8).all()
    return render_template('index.html', featured=featured, new_products=new_products)


@app.route('/iphone')
@app.route('/iphone/')
def iphone():
    products = Product.query.filter_by(category='iphone').all()
    return render_template('iphone.html', products=products)


@app.route('/mac')
@app.route('/mac/')
def mac():
    products = Product.query.filter_by(category='mac').all()
    return render_template('mac.html', products=products)


@app.route('/ipad')
@app.route('/ipad/')
def ipad():
    products = Product.query.filter_by(category='ipad').all()
    return render_template('ipad.html', products=products)


@app.route('/watch')
@app.route('/watch/')
def watch():
    products = Product.query.filter_by(category='watch').all()
    return render_template('watch.html', products=products)


@app.route('/airpods')
@app.route('/airpods/')
def airpods():
    products = Product.query.filter_by(category='airpods').all()
    return render_template('airpods.html', products=products)


@app.route('/accessories')
@app.route('/accessories/')
def accessories():
    products = Product.query.filter_by(category='accessories').all()
    return render_template('accessories.html', products=products)


# ---------------------------------------------------------------------------
# Routes - Store / Shopping
# ---------------------------------------------------------------------------

@app.route('/shop')
@app.route('/shop/')
def shop():
    products = Product.query.all()
    categories = db.session.query(Product.category).distinct().all()
    return render_template('shop.html', products=products, categories=[c[0] for c in categories])


@app.route('/product/<slug>')
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    related = Product.query.filter_by(category=product.category).filter(Product.id != product.id).limit(4).all()
    gallery = load_gallery(slug)
    reviews = Review.query.filter_by(product_id=product.id).order_by(Review.created_at.desc()).all()
    avg_rating = db.session.query(db.func.avg(Review.rating)).filter_by(product_id=product.id).scalar()
    in_wishlist = False
    if current_user.is_authenticated:
        in_wishlist = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product.id).first() is not None
    review_form = ReviewForm()
    return render_template('product_detail.html', product=product, related=related,
                           gallery=gallery, reviews=reviews, avg_rating=avg_rating,
                           in_wishlist=in_wishlist, review_form=review_form)


# ---------------------------------------------------------------------------
# Routes - Cart
# ---------------------------------------------------------------------------

@app.route('/bag')
def bag():
    if current_user.is_authenticated:
        items = CartItem.query.filter_by(user_id=current_user.id).all()
    else:
        items = []
        for ci in session.get('cart', []):
            product = Product.query.get(ci['product_id'])
            if product:
                items.append({
                    'id': ci.get('id', 0),
                    'product': product,
                    'quantity': ci['quantity'],
                    'color': ci.get('color', ''),
                    'storage': ci.get('storage', ''),
                })
    return render_template('bag.html', items=items)


@app.route('/api/cart/add', methods=['POST'])
@csrf.exempt
def cart_add():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    color = data.get('color', '')
    storage = data.get('storage', '')

    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    if current_user.is_authenticated:
        existing = CartItem.query.filter_by(
            user_id=current_user.id, product_id=product_id,
            color=color, storage=storage
        ).first()
        if existing:
            existing.quantity += quantity
        else:
            item = CartItem(user_id=current_user.id, product_id=product_id,
                          quantity=quantity, color=color, storage=storage)
            db.session.add(item)
        db.session.commit()
        count = CartItem.query.filter_by(user_id=current_user.id).count()
    else:
        cart = session.get('cart', [])
        found = False
        for ci in cart:
            if ci['product_id'] == product_id and ci.get('color') == color and ci.get('storage') == storage:
                ci['quantity'] += quantity
                found = True
                break
        if not found:
            cart.append({'product_id': product_id, 'quantity': quantity, 'color': color, 'storage': storage})
        session['cart'] = cart
        count = len(cart)

    return jsonify({'success': True, 'cart_count': count, 'message': f'{product.name} added to bag'})


@app.route('/api/cart/update', methods=['POST'])
@csrf.exempt
def cart_update():
    data = request.get_json()
    item_id = data.get('item_id')
    quantity = data.get('quantity', 1)

    if current_user.is_authenticated:
        item = CartItem.query.get(item_id)
        if item and item.user_id == current_user.id:
            if quantity <= 0:
                db.session.delete(item)
            else:
                item.quantity = quantity
            db.session.commit()
    return jsonify({'success': True})


@app.route('/api/cart/remove', methods=['POST'])
@csrf.exempt
def cart_remove():
    data = request.get_json()
    item_id = data.get('item_id')

    if current_user.is_authenticated:
        item = CartItem.query.get(item_id)
        if item and item.user_id == current_user.id:
            db.session.delete(item)
            db.session.commit()
    else:
        cart = session.get('cart', [])
        cart = [ci for i, ci in enumerate(cart) if i != item_id]
        session['cart'] = cart

    return jsonify({'success': True})


def compute_configured_price(product, storage, memory):
    """Server-authoritative price: base + storage delta + memory delta from product.config_upgrades."""
    price = float(product.price or 0)
    try:
        upgrades = product.get_config_upgrades() or {}
    except Exception:
        upgrades = {}
    for opt in upgrades.get('storage', []) or []:
        if storage and storage in opt.get('label', ''):
            price += float(opt.get('price') or 0)
            break
    for opt in upgrades.get('memory', []) or []:
        if memory and memory == opt.get('label', ''):
            price += float(opt.get('price') or 0)
            break
    return round(price, 2)


@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def cart_add_form(product_id):
    """Non-AJAX form POST route for add-to-cart (browser agent friendly)."""
    product = Product.query.get_or_404(product_id)
    color = request.form.get('color', '')
    storage = request.form.get('storage', '')
    memory = request.form.get('memory', '')
    qty = int(request.form.get('quantity', 1))
    unit_price = compute_configured_price(product, storage, memory)
    existing = CartItem.query.filter_by(
        user_id=current_user.id, product_id=product_id,
        color=color, storage=storage, memory=memory
    ).first()
    if existing:
        existing.quantity += qty
        existing.unit_price = unit_price
    else:
        item = CartItem(user_id=current_user.id, product_id=product_id,
                        quantity=qty, color=color, storage=storage,
                        memory=memory, unit_price=unit_price)
        db.session.add(item)
    db.session.commit()
    flash(f'{product.name} added to bag.', 'success')
    return redirect(url_for('bag'))


@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def cart_remove_form(item_id):
    """Non-AJAX form POST route for remove-from-cart."""
    item = CartItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        abort(403)
    db.session.delete(item)
    db.session.commit()
    flash('Item removed from bag.', 'info')
    return redirect(url_for('bag'))


@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def cart_update_form(item_id):
    """Non-AJAX form POST route for update-cart-quantity."""
    item = CartItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        abort(403)
    qty = int(request.form.get('quantity', 1))
    if qty <= 0:
        db.session.delete(item)
    else:
        item.quantity = qty
    db.session.commit()
    return redirect(url_for('bag'))


# ---------------------------------------------------------------------------
# Routes - Auth
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            # Merge session cart into user cart
            cart = session.pop('cart', [])
            for ci in cart:
                existing = CartItem.query.filter_by(
                    user_id=user.id, product_id=ci['product_id']
                ).first()
                if existing:
                    existing.quantity += ci['quantity']
                else:
                    item = CartItem(user_id=user.id, product_id=ci['product_id'],
                                  quantity=ci['quantity'], color=ci.get('color', ''),
                                  storage=ci.get('storage', ''))
                    db.session.add(item)
            db.session.commit()
            next_page = request.args.get('next')
            flash('Signed in successfully.', 'success')
            return redirect(next_page or url_for('home'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash('An account with this email already exists.', 'error')
        else:
            user = User(
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                email=form.email.data.lower()
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created successfully!', 'success')
            return redirect(url_for('home'))
    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('home'))


@app.route('/account')
@login_required
def account():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    wishlist = WishlistItem.query.filter_by(user_id=current_user.id).all()
    return render_template('account.html', orders=orders, wishlist=wishlist)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    form = ProfileForm()
    if request.method == 'GET':
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.email.data = current_user.email
        form.phone.data = current_user.phone or ''
        form.address.data = current_user.address or ''
        form.city.data = current_user.city or ''
        form.state.data = current_user.state or ''
        form.zip_code.data = current_user.zip_code or ''
    if form.validate_on_submit():
        # Check email uniqueness
        if form.email.data.lower() != current_user.email:
            existing = User.query.filter_by(email=form.email.data.lower()).first()
            if existing:
                flash('That email is already in use.', 'error')
                return render_template('account_edit.html', form=form)
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.email = form.email.data.lower()
        current_user.phone = form.phone.data
        current_user.address = form.address.data
        current_user.city = form.city.data
        current_user.state = form.state.data
        current_user.zip_code = form.zip_code.data
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('account'))
    return render_template('account_edit.html', form=form)


@app.route('/account/password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'error')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Password changed successfully.', 'success')
            return redirect(url_for('account'))
    return render_template('change_password.html', form=form)


@app.route('/account/delete', methods=['POST'])
@login_required
def delete_account():
    uid = current_user.id
    logout_user()
    # Remove related data
    CartItem.query.filter_by(user_id=uid).delete()
    WishlistItem.query.filter_by(user_id=uid).delete()
    Review.query.filter_by(user_id=uid).delete()
    for order in Order.query.filter_by(user_id=uid).all():
        OrderItem.query.filter_by(order_id=order.id).delete()
    Order.query.filter_by(user_id=uid).delete()
    User.query.filter_by(id=uid).delete()
    db.session.commit()
    flash('Your account has been deleted.', 'info')
    return redirect(url_for('home'))


# ---------------------------------------------------------------------------
# Routes - Order Management
# ---------------------------------------------------------------------------

@app.route('/order/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        abort(403)
    if order.status not in ('processing',):
        flash('Only processing orders can be cancelled.', 'error')
        return redirect(url_for('order_detail', order_id=order.id))
    order.status = 'cancelled'
    order.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Order {order.order_number} has been cancelled.', 'success')
    return redirect(url_for('order_detail', order_id=order.id))


@app.route('/order/<int:order_id>/reorder', methods=['POST'])
@login_required
def reorder(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        abort(403)
    added = 0
    for item in order.items:
        if item.product and item.product.in_stock:
            existing = CartItem.query.filter_by(
                user_id=current_user.id, product_id=item.product_id,
                color=item.color, storage=item.storage
            ).first()
            if existing:
                existing.quantity += item.quantity
            else:
                ci = CartItem(user_id=current_user.id, product_id=item.product_id,
                             quantity=item.quantity, color=item.color, storage=item.storage)
                db.session.add(ci)
            added += 1
    db.session.commit()
    flash(f'{added} item(s) added to your bag.', 'success')
    return redirect(url_for('bag'))


@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        abort(403)
    return render_template('order_detail.html', order=order)


# ---------------------------------------------------------------------------
# Routes - Wishlist
# ---------------------------------------------------------------------------

@app.route('/api/wishlist/toggle', methods=['POST'])
@csrf.exempt
def wishlist_toggle():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Sign in required'}), 401
    data = request.get_json()
    product_id = data.get('product_id')
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    existing = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'success': True, 'in_wishlist': False, 'message': f'{product.name} removed from wishlist'})
    else:
        wi = WishlistItem(user_id=current_user.id, product_id=product_id)
        db.session.add(wi)
        db.session.commit()
        return jsonify({'success': True, 'in_wishlist': True, 'message': f'{product.name} added to wishlist'})


@app.route('/wishlist')
@login_required
def wishlist():
    items = WishlistItem.query.filter_by(user_id=current_user.id).order_by(WishlistItem.added_at.desc()).all()
    return render_template('wishlist.html', items=items)


@app.route('/wishlist/remove/<int:item_id>', methods=['POST'])
@login_required
def wishlist_remove(item_id):
    item = WishlistItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        abort(403)
    db.session.delete(item)
    db.session.commit()
    flash('Removed from wishlist.', 'info')
    return redirect(url_for('wishlist'))


# ---------------------------------------------------------------------------
# Routes - Reviews
# ---------------------------------------------------------------------------

@app.route('/product/<slug>/review', methods=['POST'])
@login_required
def submit_review(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    form = ReviewForm()
    if form.validate_on_submit():
        existing = Review.query.filter_by(user_id=current_user.id, product_id=product.id).first()
        if existing:
            existing.rating = int(form.rating.data)
            existing.title = form.title.data
            existing.body = form.body.data
        else:
            review = Review(user_id=current_user.id, product_id=product.id,
                          rating=int(form.rating.data), title=form.title.data, body=form.body.data)
            db.session.add(review)
        db.session.commit()
        flash('Review submitted.', 'success')
    return redirect(url_for('product_detail', slug=slug))


@app.route('/review/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    if review.user_id != current_user.id:
        abort(403)
    slug = review.product.slug
    db.session.delete(review)
    db.session.commit()
    flash('Review deleted.', 'info')
    return redirect(url_for('product_detail', slug=slug))


# ---------------------------------------------------------------------------
# Routes - Saved Addresses
# ---------------------------------------------------------------------------

@app.route('/account/addresses')
@login_required
def saved_addresses():
    addrs = SavedAddress.query.filter_by(user_id=current_user.id).order_by(SavedAddress.is_default.desc()).all()
    return render_template('saved_addresses.html', addresses=addrs)


@app.route('/account/addresses/add', methods=['GET', 'POST'])
@login_required
def add_address():
    if request.method == 'POST':
        label = request.form.get('label', 'Home')
        make_default = request.form.get('is_default') == '1'
        if make_default:
            SavedAddress.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
        addr = SavedAddress(
            user_id=current_user.id,
            label=label,
            first_name=request.form.get('first_name', ''),
            last_name=request.form.get('last_name', ''),
            address=request.form.get('address', ''),
            city=request.form.get('city', ''),
            state=request.form.get('state', ''),
            zip_code=request.form.get('zip_code', ''),
            phone=request.form.get('phone', ''),
            is_default=make_default,
        )
        db.session.add(addr)
        db.session.commit()
        flash('Address saved.', 'success')
        return redirect(url_for('saved_addresses'))
    return render_template('add_address.html')


@app.route('/account/addresses/<int:addr_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_address(addr_id):
    addr = SavedAddress.query.filter_by(id=addr_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        addr.label = request.form.get('label', addr.label)
        addr.first_name = request.form.get('first_name', addr.first_name)
        addr.last_name = request.form.get('last_name', addr.last_name)
        addr.address = request.form.get('address', addr.address)
        addr.city = request.form.get('city', addr.city)
        addr.state = request.form.get('state', addr.state)
        addr.zip_code = request.form.get('zip_code', addr.zip_code)
        addr.phone = request.form.get('phone', addr.phone)
        make_default = request.form.get('is_default') == '1'
        if make_default:
            SavedAddress.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
            addr.is_default = True
        db.session.commit()
        flash('Address updated.', 'success')
        return redirect(url_for('saved_addresses'))
    return render_template('add_address.html', address=addr)


@app.route('/account/addresses/<int:addr_id>/delete', methods=['POST'])
@login_required
def delete_address(addr_id):
    addr = SavedAddress.query.filter_by(id=addr_id, user_id=current_user.id).first_or_404()
    db.session.delete(addr)
    db.session.commit()
    flash('Address removed.', 'info')
    return redirect(url_for('saved_addresses'))


@app.route('/account/addresses/<int:addr_id>/set-default', methods=['POST'])
@login_required
def set_default_address(addr_id):
    SavedAddress.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
    addr = SavedAddress.query.filter_by(id=addr_id, user_id=current_user.id).first_or_404()
    addr.is_default = True
    db.session.commit()
    flash('Default address updated.', 'success')
    return redirect(url_for('saved_addresses'))


# ---------------------------------------------------------------------------
# Routes - Payment Methods
# ---------------------------------------------------------------------------

@app.route('/account/payments')
@login_required
def saved_payments():
    payments = PaymentMethod.query.filter_by(user_id=current_user.id).order_by(PaymentMethod.is_default.desc()).all()
    return render_template('saved_payments.html', payments=payments)


@app.route('/account/payments/add', methods=['GET', 'POST'])
@login_required
def add_payment():
    if request.method == 'POST':
        make_default = request.form.get('is_default') == '1'
        if make_default:
            PaymentMethod.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
        pm = PaymentMethod(
            user_id=current_user.id,
            card_type=request.form.get('card_type', 'Visa'),
            last4=request.form.get('last4', '0000')[-4:],
            exp_month=int(request.form.get('exp_month', 12)),
            exp_year=int(request.form.get('exp_year', 2027)),
            cardholder_name=request.form.get('cardholder_name', ''),
            is_default=make_default,
        )
        db.session.add(pm)
        db.session.commit()
        flash('Payment method saved.', 'success')
        return redirect(url_for('saved_payments'))
    return render_template('add_payment.html')


@app.route('/account/payments/<int:pm_id>/delete', methods=['POST'])
@login_required
def delete_payment(pm_id):
    pm = PaymentMethod.query.filter_by(id=pm_id, user_id=current_user.id).first_or_404()
    db.session.delete(pm)
    db.session.commit()
    flash('Payment method removed.', 'info')
    return redirect(url_for('saved_payments'))


@app.route('/account/payments/<int:pm_id>/set-default', methods=['POST'])
@login_required
def set_default_payment(pm_id):
    PaymentMethod.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
    pm = PaymentMethod.query.filter_by(id=pm_id, user_id=current_user.id).first_or_404()
    pm.is_default = True
    db.session.commit()
    flash('Default payment updated.', 'success')
    return redirect(url_for('saved_payments'))


# ---------------------------------------------------------------------------
# Routes - Checkout & Orders
# ---------------------------------------------------------------------------

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash('Your bag is empty.', 'info')
        return redirect(url_for('shop'))

    form = CheckoutForm()
    saved_addrs = SavedAddress.query.filter_by(user_id=current_user.id).order_by(SavedAddress.is_default.desc()).all()
    saved_payments = PaymentMethod.query.filter_by(user_id=current_user.id).order_by(PaymentMethod.is_default.desc()).all()

    # Prefill from user profile
    if request.method == 'GET':
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.email.data = current_user.email
        form.phone.data = current_user.phone or ''
        # Prefill address from default saved address if available
        default_addr = next((a for a in saved_addrs if a.is_default), saved_addrs[0] if saved_addrs else None)
        if default_addr:
            form.address.data = default_addr.address
            form.city.data = default_addr.city
            form.state.data = default_addr.state
            form.zip_code.data = default_addr.zip_code
        else:
            form.address.data = current_user.address or ''
            form.city.data = current_user.city or ''
            form.state.data = current_user.state or ''
            form.zip_code.data = current_user.zip_code or ''

    subtotal = sum(item.effective_price() * item.quantity for item in items)
    shipping_costs = {'standard': 0, 'express': 9.99, 'overnight': 19.99}

    if form.validate_on_submit():
        shipping_cost = shipping_costs.get(form.shipping_method.data, 0)
        total = subtotal + shipping_cost

        # Check for saved address/payment selection
        saved_addr_id = request.form.get('saved_address_id', type=int)
        saved_pm_id = request.form.get('saved_payment_id', type=int)

        if saved_addr_id:
            sa = SavedAddress.query.filter_by(id=saved_addr_id, user_id=current_user.id).first()
            if sa:
                shipping_address = f"{sa.address}, {sa.city}, {sa.state} {sa.zip_code}"
            else:
                shipping_address = f"{form.address.data}, {form.city.data}, {form.state.data} {form.zip_code.data}"
        else:
            shipping_address = f"{form.address.data}, {form.city.data}, {form.state.data} {form.zip_code.data}"

        if saved_pm_id:
            pm = PaymentMethod.query.filter_by(id=saved_pm_id, user_id=current_user.id).first()
            payment_label = f"{pm.card_type} ending in {pm.last4}" if pm else form.payment_method.data
        else:
            payment_label = form.payment_method.data

        order = Order(
            user_id=current_user.id,
            order_number=f"W{secrets.token_hex(5).upper()}",
            total=total,
            shipping_address=shipping_address,
            shipping_method=form.shipping_method.data,
            payment_method=payment_label,
        )
        db.session.add(order)
        db.session.flush()

        for item in items:
            oi = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.effective_price(),
                color=item.color,
                storage=item.storage,
            )
            db.session.add(oi)
            db.session.delete(item)

        # Update user address
        current_user.phone = form.phone.data
        current_user.address = form.address.data
        current_user.city = form.city.data
        current_user.state = form.state.data
        current_user.zip_code = form.zip_code.data
        db.session.commit()

        return redirect(url_for('order_confirmation', order_id=order.id))

    return render_template('checkout.html', form=form, items=items, subtotal=subtotal,
                         shipping_costs=shipping_costs, saved_addrs=saved_addrs,
                         saved_payments=saved_payments)


@app.route('/order/<int:order_id>/confirmation')
@login_required
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        abort(403)
    return render_template('order_confirmation.html', order=order)


# ---------------------------------------------------------------------------
# Routes - Search
# ---------------------------------------------------------------------------

STOPWORDS = {
    'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with',
    'and', 'or', 'is', 'are', 'be', 'by', 'from', 'as', 'that', 'this',
    'on', 'apple', 'find', 'about', 'information', 'page', 'website',
    'check', 'get', 'how', 'much', 'does', 'it', 'cost',
}


def _score_product(product, tokens):
    hay_parts = [
        (product.name or ''),
        (product.category or ''),
        (product.subcategory or ''),
        (product.subtitle or ''),
        (product.description or ''),
        (product.slogan or ''),
        (product.chip_family or ''),
        (product.processor or ''),
        (product.connectivity or ''),
        (product.feature_tags or ''),
        (product.specs or ''),
        (product.color_options or ''),
        (product.storage_options or ''),
    ]
    haystack = ' '.join(hay_parts).lower()
    return sum(1 for t in tokens if t in haystack)


def _apply_product_filters(query_obj):
    category = request.args.get('category', '').strip().lower()
    if category:
        query_obj = query_obj.filter(Product.category == category)

    subcategory = request.args.get('subcategory', '').strip().lower()
    if subcategory:
        query_obj = query_obj.filter(Product.subcategory == subcategory)

    chip = request.args.get('chip', '').strip()
    if chip:
        query_obj = query_obj.filter(Product.chip_family.ilike(f'%{chip}%'))

    min_ram = request.args.get('min_ram', type=int)
    if min_ram is not None:
        query_obj = query_obj.filter(Product.ram >= min_ram)
    min_ssd = request.args.get('min_ssd', type=int)
    if min_ssd is not None:
        query_obj = query_obj.filter(Product.ssd >= min_ssd)

    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    if min_price is not None:
        query_obj = query_obj.filter(Product.price >= min_price)
    if max_price is not None:
        query_obj = query_obj.filter(Product.price <= max_price)

    color = request.args.get('color', '').strip()
    if color:
        query_obj = query_obj.filter(Product.color_options.ilike(f'%{color}%'))

    storage = request.args.get('storage', '').strip()
    if storage:
        query_obj = query_obj.filter(Product.storage_options.ilike(f'%{storage}%'))

    connectivity = request.args.get('connectivity', '').strip()
    if connectivity:
        query_obj = query_obj.filter(Product.connectivity.ilike(f'%{connectivity}%'))

    screen_size = request.args.get('screen_size', type=float)
    if screen_size is not None:
        query_obj = query_obj.filter(Product.screen_size == screen_size)

    release_year = request.args.get('release_year', type=int)
    if release_year is not None:
        query_obj = query_obj.filter(Product.release_year == release_year)

    if request.args.get('in_stock') == '1':
        query_obj = query_obj.filter(Product.in_stock == True)
    if request.args.get('is_new') == '1':
        query_obj = query_obj.filter(Product.is_new == True)

    feature = request.args.get('feature', '').strip().lower()
    if feature:
        tokens = re.findall(r'[a-z0-9][\w-]*', feature)
        for tok in tokens:
            if tok and len(tok) >= 2:
                query_obj = query_obj.filter(Product.feature_tags.ilike(f'%{tok}%'))

    return query_obj


def _apply_sort(results, key):
    if key == 'price_asc':
        return sorted(results, key=lambda p: p.price)
    if key == 'price_desc':
        return sorted(results, key=lambda p: p.price, reverse=True)
    if key == 'newest':
        return sorted(results, key=lambda p: (p.release_year or 0, p.created_at), reverse=True)
    if key == 'screen_size':
        return sorted(results, key=lambda p: p.screen_size or 0, reverse=True)
    if key == 'name':
        return sorted(results, key=lambda p: (p.name or '').lower())
    return results


@app.route('/search')
@app.route('/search/<path:apple_query>')
def search(apple_query=''):
    q = (apple_query or request.args.get('q', '')).strip()
    query_obj = Product.query
    query_obj = _apply_product_filters(query_obj)
    candidates = query_obj.all()

    if q:
        tokens = [t.lower() for t in re.findall(r'[a-z0-9]+', q.lower())
                  if t and t not in STOPWORDS and len(t) >= 2]
        if tokens:
            min_required = max(1, len(tokens) // 2)
            scored = []
            for p in candidates:
                s = _score_product(p, tokens)
                if s >= min_required:
                    scored.append((s, p))
            scored.sort(key=lambda x: -x[0])
            results = [p for _, p in scored]
        else:
            results = candidates
    else:
        results = candidates

    # Also include matching support articles when query present
    articles = []
    if q:
        tokens = [t.lower() for t in re.findall(r'[a-z0-9]+', q.lower())
                  if t and t not in STOPWORDS and len(t) >= 2]
        if tokens:
            for art in SupportArticle.query.all():
                hay = ' '.join([
                    art.title or '', art.summary or '', art.body or '',
                    art.topic or '', art.tags or '', art.compat or ''
                ]).lower()
                if sum(1 for t in tokens if t in hay) >= max(1, len(tokens) // 2):
                    articles.append(art)

    results = _apply_sort(results, request.args.get('sort', ''))
    return render_template('search.html', query=q, results=results, articles=articles)


# ---------------------------------------------------------------------------
# Routes - Support / Trade-In / Store pickup / Music / Vision Pro
# ---------------------------------------------------------------------------

@app.route('/support')
@app.route('/support/')
def support():
    topic = request.args.get('topic', '').strip().lower()
    q = request.args.get('q', '').strip().lower()
    query_obj = SupportArticle.query
    if topic:
        query_obj = query_obj.filter(SupportArticle.topic == topic)
    articles = query_obj.all()
    if q:
        tokens = [t for t in re.findall(r'[a-z0-9]+', q) if t not in STOPWORDS and len(t) >= 2]
        def score(a):
            hay = ' '.join([a.title, a.summary, a.body, a.topic, a.tags, a.compat]).lower()
            return sum(1 for t in tokens if t in hay)
        scored = [(score(a), a) for a in articles]
        scored = [(s, a) for s, a in scored if s >= max(1, len(tokens) // 2)]
        scored.sort(key=lambda x: -x[0])
        articles = [a for _, a in scored]
    # Repair options as first-class content
    repair_options = [
        ('Mail-in repair', 'Ship your device to an Apple Repair Center.'),
        ('Carry-in repair', 'Bring your device to an Apple Store or Apple Authorized Service Provider.'),
        ('Onsite repair (business only)', 'Certain business customers get onsite repair.'),
        ('Express Replacement Service', 'Receive a replacement before sending the original.'),
    ]
    return render_template('support.html', articles=articles, topic=topic, query=q,
                           repair_options=repair_options)


@app.route('/support/article/<slug>')
def support_article(slug):
    # Support both canonical slugs and common alias slugs so URLs in
    # support docs remain resolvable even when users type variations.
    alias_map = {
        'apple-id-forgot-password':   'forgot-apple-id-password',
        'forgot-password':            'forgot-apple-id-password',
        'ios17-new-features':         'ios-17-new-features',
        'ios-17-features':            'ios-17-new-features',
        'repair':                     'apple-repair-options',
        'apple-repair':               'apple-repair-options',
        'trade-in':                   'iphone-trade-in-offers',
    }
    resolved_slug = alias_map.get(slug, slug)
    art = SupportArticle.query.filter_by(slug=resolved_slug).first()
    if not art:
        abort(404)
    return render_template('support_article.html', article=art)


@app.route('/support/repair')
@app.route('/support/repair/')
def support_repair():
    """Dedicated Apple Repair landing page listing every repair option."""
    repair_options = [
        ('Mail-in repair',
         'Ship your device to an Apple Repair Center using a prepaid box.'),
        ('Carry-in repair',
         'Bring your device to an Apple Store or Apple Authorized Service Provider.'),
        ('Onsite repair (business only)',
         'Certain business customers are eligible for onsite repair visits.'),
        ('Express Replacement Service',
         'Receive a replacement device before sending the original back.'),
        ('Self Service Repair',
         'Order Apple-genuine parts, tools, and manuals to repair eligible products yourself.'),
    ]
    # Surface the canonical repair article for deeper reading.
    repair_article = SupportArticle.query.filter_by(slug='apple-repair-options').first()
    return render_template('support_repair.html',
                           repair_options=repair_options,
                           repair_article=repair_article)


@app.route('/support/apple-id-forgot-password')
@app.route('/support/apple-id/forgot-password')
@app.route('/support/forgot-password')
def support_forgot_password():
    """Canonical landing page for the 'forgot Apple ID password' task."""
    art = SupportArticle.query.filter_by(slug='forgot-apple-id-password').first()
    if art:
        return render_template('support_article.html', article=art)
    abort(404)


@app.route('/support/article/ios-17-new-features')
def support_ios17_new_features():
    """Friendly redirect/alias for the iOS 17 features article."""
    art = SupportArticle.query.filter_by(slug='ios-17-new-features').first()
    if art:
        return render_template('support_article.html', article=art)
    abort(404)


@app.route('/trade-in')
@app.route('/trade-in/')
def trade_in():
    device = request.args.get('device', '').strip().lower()
    query_obj = TradeInValue.query
    matches = []
    if device:
        tokens = [t for t in re.findall(r'[a-z0-9]+', device) if t not in STOPWORDS and len(t) >= 2]
        for row in query_obj.all():
            hay = row.device.lower()
            if sum(1 for t in tokens if t in hay) >= max(1, len(tokens) // 2):
                matches.append(row)
    else:
        matches = query_obj.all()
    return render_template('trade_in.html', device=device, matches=matches)


@app.route('/trade-in/<device_slug>')
def trade_in_device(device_slug):
    """Direct trade-in value page for a specific device slug (e.g. iphone-11-pro-max)."""
    slug = (device_slug or '').strip().lower()
    # Map slug -> display-cased device name used in the DB.
    slug_words = [w for w in re.split(r'[-_]+', slug) if w]
    all_rows = TradeInValue.query.all()
    best = None
    best_score = 0
    for row in all_rows:
        hay_tokens = set(re.findall(r'[a-z0-9]+', row.device.lower()))
        score = sum(1 for w in slug_words if w in hay_tokens)
        if score > best_score:
            best_score = score
            best = row
    if not best or best_score < max(1, len(slug_words) // 2):
        # No direct match -> show empty state with search box preseeded.
        return render_template('trade_in.html',
                               device=slug.replace('-', ' '),
                               matches=[])
    return render_template('trade_in.html',
                           device=best.device,
                           matches=[best])


@app.route('/store/pickup')
def store_pickup():
    zip_code = request.args.get('zip', '').strip()
    product_slug = request.args.get('product', '').strip()
    pickup_date = request.args.get('date', '').strip()
    selected_store = request.args.get('store', '').strip()
    product = Product.query.filter_by(slug=product_slug).first() if product_slug else None
    nearby_stores = [
        {'name': 'Apple The Grove', 'city': 'Los Angeles', 'zip': '90036', 'distance': '0.8 miles',
         'address': '189 The Grove Drive, Los Angeles, CA 90036'},
        {'name': 'Apple Beverly Center', 'city': 'Los Angeles', 'zip': '90048', 'distance': '1.5 miles',
         'address': '8500 Beverly Blvd, Los Angeles, CA 90048'},
        {'name': 'Apple Century City', 'city': 'Los Angeles', 'zip': '90067', 'distance': '3.2 miles',
         'address': '10250 Santa Monica Blvd, Los Angeles, CA 90067'},
    ]
    # Generate a short list of available pickup dates (today .. +10 days).
    # Also allow any user-supplied YYYY-MM-DD in `date` so scheduling for
    # specific past or future dates (e.g. Jan 10, 2024) is always possible.
    from datetime import timedelta as _td
    today = datetime.utcnow().date()
    available_dates = [(today + _td(days=i)).isoformat() for i in range(11)]
    confirmed = False
    if pickup_date and selected_store:
        confirmed = True
    return render_template('store_pickup.html',
                           zip_code=zip_code, product=product,
                           nearby_stores=nearby_stores,
                           available_dates=available_dates,
                           pickup_date=pickup_date,
                           selected_store=selected_store,
                           confirmed=confirmed)


@app.route('/store/pickup/confirm', methods=['POST'])
@csrf.exempt
def store_pickup_confirm():
    """Confirm an in-store pickup for a given product, store, and date.
    Accepts any date (past or future) so tasks like 'schedule for Jan 10, 2024'
    are always fulfillable, even when that date is in the past."""
    product_slug = request.form.get('product', '').strip()
    zip_code = request.form.get('zip', '').strip()
    store_name = request.form.get('store', '').strip()
    pickup_date = request.form.get('date', '').strip()
    # Pass through GET to render the confirmation state.
    return redirect(url_for('store_pickup',
                            product=product_slug,
                            zip=zip_code,
                            store=store_name,
                            date=pickup_date))


@app.route('/music')
@app.route('/music/')
def apple_music():
    featured_artists = [
        'Taylor Swift', 'Drake', 'The Weeknd', 'Billie Eilish', 'Dua Lipa',
        'Olivia Rodrigo', 'Bad Bunny', 'Harry Styles',
    ]
    return render_template('apple_music.html', artists=featured_artists)


@app.route('/vision-pro')
@app.route('/vision-pro/')
def vision_pro():
    product = Product.query.filter_by(slug='apple-vision-pro').first()
    accessories_list = Product.query.filter_by(subcategory='vision-pro-accessory').all()
    return render_template('vision_pro.html', product=product, accessories=accessories_list)


@app.route('/configure/<slug>')
def configurator(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    return render_template('configurator.html', product=product,
                           upgrades=product.get_config_upgrades(),
                           keyboards=product.get_keyboard_options())


@app.route('/compare/<category>')
@app.route('/compare/<category>/')
def compare(category):
    """Side-by-side spec comparison page for every product in a category."""
    category = (category or '').lower()
    # canonical title + upstream category slug
    titles = {
        'mac': 'Mac', 'iphone': 'iPhone', 'ipad': 'iPad',
        'watch': 'Apple Watch', 'airpods': 'AirPods',
        'accessories': 'Accessories', 'vision': 'Apple Vision Pro',
    }
    title = titles.get(category, category.capitalize())
    products = Product.query.filter_by(category=category).order_by(Product.price.desc()).all()
    return render_template('compare.html', products=products,
                           category=category, title=title)


# ---------------------------------------------------------------------------
# API - Product data (for JS interactions)
# ---------------------------------------------------------------------------

@app.route('/api/products/<category>')
def api_products(category):
    products = Product.query.filter_by(category=category).all()
    return jsonify([{
        'id': p.id, 'name': p.name, 'slug': p.slug, 'price': p.price,
        'subtitle': p.subtitle, 'image': p.image, 'is_new': p.is_new,
        'colors': p.get_colors(), 'monthly_price': p.monthly_price,
    } for p in products])


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

def seed_database():
    """Populate database with Apple products."""
    if Product.query.first():
        return

    products = [
        # iPhone
        Product(name='iPhone 17 Pro', slug='iphone-17-pro', category='iphone',
                subtitle='All out Pro.', description='The most advanced iPhone ever with A19 Pro chip, titanium design, and a 48MP camera system with 8x optical-quality zoom.',
                price=1099.00, monthly_price=45.79, months=24, is_new=True, is_featured=True,
                image='/static/images/products/iphone_17_pro.jpg', hero_image='/static/images/hero/iphone_17_pro_hero.jpg',
                color_options=json.dumps(['Natural Titanium', 'Black Titanium', 'White Titanium', 'Sand Titanium']),
                storage_options=json.dumps(['256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'A19 Pro', 'display': '6.3" Super Retina XDR', 'camera': '48MP Main + 48MP Ultra Wide + 12MP Telephoto', 'battery': 'Up to 33 hours video playback'})),
        Product(name='iPhone 17 Pro Max', slug='iphone-17-pro-max', category='iphone',
                subtitle='The biggest Pro ever.', description='Massive 6.9-inch display, A19 Pro chip, and the longest battery life ever in an iPhone.',
                price=1199.00, monthly_price=49.95, months=24, is_new=True, is_featured=True,
                image='/static/images/products/iphone_17_pro_max.jpg', hero_image='/static/images/hero/iphone_17_pro_max_hero.jpg',
                color_options=json.dumps(['Natural Titanium', 'Black Titanium', 'White Titanium', 'Sand Titanium']),
                storage_options=json.dumps(['256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'A19 Pro', 'display': '6.9" Super Retina XDR', 'camera': '48MP Main + 48MP Ultra Wide + 12MP Telephoto', 'battery': 'Up to 39 hours video playback'})),
        Product(name='iPhone Air', slug='iphone-air', category='iphone',
                subtitle='The thinnest iPhone ever.', description='Incredibly thin and light design with the power of pro inside.',
                price=999.00, monthly_price=41.62, months=24, is_new=True, is_featured=True,
                image='/static/images/products/iphone_air.jpg', hero_image='/static/images/hero/iphone_air_hero.jpg',
                color_options=json.dumps(['Midnight', 'Starlight', 'Green', 'Blue', 'Pink']),
                storage_options=json.dumps(['128GB', '256GB', '512GB']),
                specs=json.dumps({'chip': 'A18', 'display': '6.6" Super Retina XDR', 'camera': '48MP Main + 12MP Ultra Wide', 'battery': 'Up to 30 hours video playback'})),
        Product(name='iPhone 17', slug='iphone-17', category='iphone',
                subtitle='Even more delightful. Even more durable.', description='Beautiful design with Ceramic Shield 2 and Dynamic Island.',
                price=799.00, monthly_price=33.29, months=24, is_new=True, is_featured=True,
                image='/static/images/products/iphone_17.jpg', hero_image='/static/images/hero/iphone_17_hero.jpg',
                color_options=json.dumps(['Black', 'White', 'Pink', 'Green', 'Blue']),
                storage_options=json.dumps(['128GB', '256GB', '512GB']),
                specs=json.dumps({'chip': 'A18', 'display': '6.1" Super Retina XDR', 'camera': '48MP Main + 12MP Ultra Wide', 'battery': 'Up to 28 hours video playback'})),
        Product(name='iPhone 17e', slug='iphone-17e', category='iphone',
                subtitle='Feature stacked. Value packed.', description='Everything you need in an iPhone at an amazing price.',
                price=599.00, monthly_price=24.95, months=24, is_new=True, is_featured=True,
                image='/static/images/products/iphone_17e.jpg', hero_image='/static/images/hero/iphone_17e_hero.jpg',
                color_options=json.dumps(['Black', 'White', 'Pink', 'Green']),
                storage_options=json.dumps(['128GB', '256GB']),
                specs=json.dumps({'chip': 'A18', 'display': '6.1" Super Retina XDR', 'camera': '48MP Main', 'battery': 'Up to 26 hours video playback'})),
        # Mac
        Product(name='MacBook Neo', slug='macbook-neo', category='mac',
                subtitle='Hello, Neo. The magic of Mac at a surprising price.', description='A18 Pro chip, 13-inch Liquid Retina display, up to 16 hours of battery life. Available in four stunning colors.',
                price=599.00, monthly_price=24.95, months=24, is_new=True, is_featured=True,
                image='/static/images/products/macbook_neo.jpg', hero_image='/static/images/hero/macbook_neo_hero.jpg',
                color_options=json.dumps(['Silver', 'Blush', 'Citrus', 'Indigo']),
                storage_options=json.dumps(['256GB', '512GB']),
                specs=json.dumps({'chip': 'A18 Pro', 'display': '13" Liquid Retina', 'memory': '8GB', 'battery': 'Up to 16 hours'})),
        Product(name='MacBook Pro 14"', slug='macbook-pro-14', category='mac',
                subtitle='Outrageously powerful.', description='M5 chip, stunning Liquid Retina XDR display, and all-day battery life.',
                price=1699.00, monthly_price=70.79, months=24, is_new=True, is_featured=True,
                image='/static/images/products/macbook_pro_14.jpg', hero_image='/static/images/hero/macbook_pro_14_hero.jpg',
                color_options=json.dumps(['Space Black', 'Silver']),
                storage_options=json.dumps(['512GB', '1TB', '2TB']),
                specs=json.dumps({'chip': 'M5', 'display': '14.2" Liquid Retina XDR', 'memory': '24GB', 'battery': 'Up to 22 hours'})),
        Product(name='MacBook Pro 16"', slug='macbook-pro-16', category='mac',
                subtitle='The most powerful MacBook Pro ever.', description='M5 Pro or M5 Max chip for the ultimate pro notebook.',
                price=2499.00, monthly_price=104.12, months=24, is_new=True, is_featured=False,
                image='/static/images/products/macbook_pro_16.png', hero_image='/static/images/hero/macbook_pro_16_hero.jpg',
                color_options=json.dumps(['Space Black', 'Silver']),
                storage_options=json.dumps(['512GB', '1TB', '2TB', '4TB']),
                specs=json.dumps({'chip': 'M5 Pro / M5 Max', 'display': '16.2" Liquid Retina XDR', 'memory': '36GB / 48GB', 'battery': 'Up to 24 hours'})),
        Product(name='MacBook Air 13"', slug='macbook-air-13', category='mac',
                subtitle='Lean. Mean. Icons machine.', description='M5 chip in an impossibly thin design.',
                price=1099.00, monthly_price=45.79, months=24, is_new=True, is_featured=True,
                image='/static/images/products/macbook_air_13.png', hero_image='/static/images/hero/macbook_air_13_hero.png',
                color_options=json.dumps(['Midnight', 'Starlight', 'Space Gray', 'Silver']),
                storage_options=json.dumps(['256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'M5', 'display': '13.6" Liquid Retina', 'memory': '16GB', 'battery': 'Up to 18 hours'})),
        Product(name='iMac 24"', slug='imac-24', category='mac',
                subtitle='Say hello.', description='M5 chip, stunning 24-inch 4.5K Retina display, and a colorful all-in-one design.',
                price=1299.00, monthly_price=54.12, months=24, is_new=False, is_featured=False,
                image='/static/images/products/imac.jpg', hero_image='/static/images/hero/imac_hero.jpg',
                color_options=json.dumps(['Blue', 'Green', 'Pink', 'Silver', 'Yellow', 'Orange', 'Purple']),
                storage_options=json.dumps(['256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'M5', 'display': '24" 4.5K Retina', 'memory': '16GB', 'battery': 'N/A (Desktop)'})),
        # iPad
        Product(name='iPad Air M4', slug='ipad-air-m4', category='ipad',
                subtitle='Now supercharged by M4.', description='M4 chip with 8-core CPU, Liquid Retina display, and Apple Pencil Pro support.',
                price=599.00, monthly_price=24.95, months=24, is_new=True, is_featured=True,
                image='/static/images/products/ipad_air.png', hero_image='/static/images/hero/ipad_air_hero.png',
                color_options=json.dumps(['Space Gray', 'Blue', 'Purple', 'Starlight']),
                storage_options=json.dumps(['128GB', '256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'M4', 'display': '11" or 13" Liquid Retina', 'camera': '12MP Wide', 'battery': 'Up to 10 hours'})),
        Product(name='iPad Pro M5', slug='ipad-pro-m5', category='ipad',
                subtitle='Unbelievably thin. Incredibly powerful.', description='M5 chip, Ultra Retina XDR display, and Thunderbolt connectivity.',
                price=999.00, monthly_price=41.62, months=24, is_new=True, is_featured=False,
                image='/static/images/products/ipad_pro.jpg', hero_image='/static/images/hero/ipad_pro_hero.png',
                color_options=json.dumps(['Space Black', 'Silver']),
                storage_options=json.dumps(['256GB', '512GB', '1TB', '2TB']),
                specs=json.dumps({'chip': 'M5', 'display': '11" or 13" Ultra Retina XDR', 'camera': '12MP Wide + LiDAR', 'battery': 'Up to 10 hours'})),
        Product(name='iPad 10th Gen', slug='ipad-10', category='ipad',
                subtitle='Colorful. Powerful. Wonderful.', description='A14 Bionic chip, 10.9-inch Liquid Retina display.',
                price=349.00, monthly_price=14.54, months=24, is_new=False, is_featured=False,
                image='/static/images/products/ipad_10.png', hero_image='/static/images/hero/ipad_10_hero.png',
                color_options=json.dumps(['Blue', 'Pink', 'Yellow', 'Silver']),
                storage_options=json.dumps(['64GB', '256GB']),
                specs=json.dumps({'chip': 'A14 Bionic', 'display': '10.9" Liquid Retina', 'camera': '12MP Wide', 'battery': 'Up to 10 hours'})),
        # Watch
        Product(name='Apple Watch Series 11', slug='apple-watch-series-11', category='watch',
                subtitle='The ultimate way to watch your health.', description='Hypertension notifications, sleep score, S10 chip, Always-On Retina display.',
                price=399.00, monthly_price=16.62, months=24, is_new=True, is_featured=True,
                image='/static/images/products/watch_series_11.png', hero_image='/static/images/hero/watch_series_11_hero.png',
                color_options=json.dumps(['Rose Gold', 'Silver', 'Jet Black', 'Space Gray']),
                storage_options=json.dumps(['42mm', '46mm']),
                specs=json.dumps({'chip': 'S10', 'display': 'Always-On Retina LTPO3', 'health': 'Blood oxygen, ECG, Temperature sensing', 'battery': 'Up to 24 hours'})),
        Product(name='Apple Watch Ultra 3', slug='apple-watch-ultra-3', category='watch',
                subtitle='The most capable Apple Watch ever.', description='49mm titanium case, precision dual-frequency GPS, and up to 72 hours of battery life.',
                price=799.00, monthly_price=33.29, months=24, is_new=True, is_featured=False,
                image='/static/images/products/watch_ultra.png', hero_image='/static/images/hero/watch_ultra_hero.png',
                color_options=json.dumps(['Natural Titanium', 'Black Titanium']),
                storage_options=json.dumps(['49mm']),
                specs=json.dumps({'chip': 'S10', 'display': '49mm Always-On Retina', 'health': 'Blood oxygen, ECG, Temperature, Depth gauge', 'battery': 'Up to 72 hours'})),
        # AirPods
        Product(name='AirPods Pro 3', slug='airpods-pro-3', category='airpods',
                subtitle='Intelligent hearing. Brilliant sound.', description='Active Noise Cancellation, Adaptive Audio, and a hearing health experience.',
                price=249.00, monthly_price=10.37, months=24, is_new=True, is_featured=True,
                image='/static/images/products/airpods_pro.jpg', hero_image='/static/images/hero/airpods_pro_hero.png',
                color_options=json.dumps(['White']),
                storage_options=json.dumps([]),
                specs=json.dumps({'chip': 'H3', 'anc': 'Active Noise Cancellation', 'audio': 'Personalized Spatial Audio', 'battery': 'Up to 6 hours (30 hours with case)'})),
        Product(name='AirPods Max 2', slug='airpods-max-2', category='airpods',
                subtitle='New intelligent features. Same icons sound.', description='High-fidelity audio with Active Noise Cancellation and USB-C.',
                price=549.00, monthly_price=22.87, months=24, is_new=True, is_featured=True,
                image='/static/images/products/airpods_max.png', hero_image='/static/images/hero/airpods_max_hero.png',
                color_options=json.dumps(['Midnight', 'Blue', 'Purple', 'Orange', 'Starlight']),
                storage_options=json.dumps([]),
                specs=json.dumps({'chip': 'H3', 'anc': 'Active Noise Cancellation', 'audio': 'Personalized Spatial Audio with head tracking', 'battery': 'Up to 20 hours'})),
        Product(name='AirPods 4', slug='airpods-4', category='airpods',
                subtitle='Iconic. Now in Icons.', description='Open-ear design for all-day comfort.',
                price=129.00, monthly_price=5.37, months=24, is_new=False, is_featured=False,
                image='/static/images/products/airpods_4.jpg', hero_image='/static/images/hero/airpods_4_hero.jpg',
                color_options=json.dumps(['White']),
                storage_options=json.dumps([]),
                specs=json.dumps({'chip': 'H2', 'audio': 'Personalized Spatial Audio', 'battery': 'Up to 5 hours (30 hours with case)'})),
        # Accessories
        Product(name='Apple Pencil Pro', slug='apple-pencil-pro', category='accessories',
                subtitle='Built for the most demanding workflows.', description='Apple Pencil Pro features Squeeze, barrel roll, and haptic feedback. Wireless pairing and wireless charging for effortless setup. Hover to preview before you draw.',
                price=129.00, monthly_price=5.37, months=24, is_new=False, is_featured=False,
                image='/static/images/products/apple_pencil.jpg', hero_image='/static/images/hero/apple_pencil_hero.jpg',
                color_options=json.dumps(['White']),
                storage_options=json.dumps([]),
                specs=json.dumps({'features': 'Squeeze, Barrel roll, Haptic feedback, Hover, Wireless pairing, wireless charging'})),
        Product(name='Apple Pencil (2nd generation)', slug='apple-pencil-2nd-gen', category='accessories',
                subtitle='A new sense of touch.', description='Apple Pencil 2nd generation magnetically attaches, pairs, and charges. Double-tap to switch tools.',
                price=129.00, monthly_price=5.37, months=24, is_new=False, is_featured=False,
                image='/static/images/products/apple_pencil_2.jpg', hero_image='/static/images/hero/apple_pencil_2_hero.jpg',
                color_options=json.dumps(['White']),
                storage_options=json.dumps([]),
                specs=json.dumps({'features': 'Magnetic attach, Wireless pairing, wireless charging, Double-tap gesture'})),
        Product(name='Apple Pencil (USB-C)', slug='apple-pencil-usb-c', category='accessories',
                subtitle='Write and draw with precision.', description='Apple Pencil with USB-C connector for easy pairing and charging.',
                price=79.00, monthly_price=3.29, months=24, is_new=False, is_featured=False,
                image='/static/images/products/apple_pencil_usbc.jpg', hero_image='/static/images/hero/apple_pencil_usbc_hero.jpg',
                color_options=json.dumps(['White']),
                storage_options=json.dumps([]),
                specs=json.dumps({'features': 'USB-C pairing and charging, Pixel-perfect precision, Tilt sensitivity'})),
        Product(name='Magic Keyboard for iPad', slug='magic-keyboard-ipad', category='accessories',
                subtitle='The best way to type on iPad.', description='Full-size keyboard with trackpad, backlit keys, and USB-C port.',
                price=299.00, monthly_price=12.45, months=24, is_new=False, is_featured=False,
                image='/static/images/products/magic_keyboard.png', hero_image='/static/images/hero/magic_keyboard_hero.png',
                color_options=json.dumps(['White', 'Black']),
                storage_options=json.dumps([]),
                specs=json.dumps({'features': 'Backlit keys, Trackpad, USB-C passthrough'})),
        Product(name='AirTag', slug='airtag', category='accessories',
                subtitle='Lose your knack for losing things.', description='Precision Finding with Ultra Wideband.',
                price=29.00, monthly_price=None, months=0, is_new=False, is_featured=False,
                image='/static/images/products/airtag.jpg', hero_image='/static/images/hero/airtag_hero.jpg',
                color_options=json.dumps(['Silver']),
                storage_options=json.dumps([]),
                specs=json.dumps({'features': 'Precision Finding, Replaceable battery, IP67 water resistant'})),
        # --- MacBook Air 15" (M3) ---
        Product(name='MacBook Air 15"', slug='macbook-air-15', category='mac',
                subtitle='Impressively big. Impossibly thin.',
                description='M5 chip in a 15-inch Liquid Retina display, up to 18 hours of battery life.',
                price=1299.00, monthly_price=54.12, months=24, is_new=True, is_featured=False,
                image='/static/images/products/macbook_air_15.jpg', hero_image='/static/images/hero/macbook_air_15_hero.jpg',
                color_options=json.dumps(['Midnight', 'Starlight', 'Space Gray', 'Silver']),
                storage_options=json.dumps(['256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'M5', 'display': '15.3" Liquid Retina', 'memory': '16GB', 'battery': 'Up to 18 hours'}),
                chip_family='M5', ram=16, screen_size=15.3, release_year=2025),
        Product(name='MacBook Air 13-inch M3', slug='macbook-air-13-inch-m3', category='mac', subcategory='macbook-air',
                subtitle='Lean. Mean. Icons machine.',
                description='M3 chip, 13.6-inch Liquid Retina display, up to 18 hours of battery life. Available in four stunning colors. 8GB unified memory, 256GB SSD.',
                price=1099.00, monthly_price=45.79, months=24, is_new=False, is_featured=False,
                image='/static/images/products/macbook_air_13_m3.jpg', hero_image='/static/images/hero/macbook_air_13_m3_hero.jpg',
                color_options=json.dumps(['Midnight', 'Starlight', 'Space Gray', 'Silver']),
                storage_options=json.dumps(['256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'M3', 'display': '13.6" Liquid Retina', 'memory': '8GB unified memory', 'battery': 'Up to 15 hours web browsing', 'SSD': '256GB / 512GB / 1TB'}),
                chip_family='M3', ram=8, ssd=256, screen_size=13.6, release_year=2024,
                battery_life='Up to 15 hours web browsing'),
        Product(name='MacBook Air 15-inch M3', slug='macbook-air-15-inch-m3', category='mac', subcategory='macbook-air',
                subtitle='Impressively big. Impossibly thin.',
                description='M3 chip in a 15-inch Liquid Retina display.',
                price=1299.00, monthly_price=54.12, months=24, is_new=False, is_featured=False,
                image='/static/images/products/macbook_air_15_m3.jpg', hero_image='/static/images/hero/macbook_air_15_m3_hero.jpg',
                color_options=json.dumps(['Midnight', 'Starlight', 'Space Gray', 'Silver']),
                storage_options=json.dumps(['256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'M3', 'display': '15.3" Liquid Retina', 'memory': '8GB', 'battery': 'Up to 18 hours'}),
                chip_family='M3', ram=8, screen_size=15.3, release_year=2024),
        # --- MacBook Pro M3 variants ---
        Product(name='MacBook Pro 14-inch M3', slug='macbook-pro-14-inch-m3', category='mac', subcategory='macbook-pro',
                subtitle='Mind-blowing. Head-turning.',
                description='M3 chip, 14.2-inch Liquid Retina XDR display, 18 hours of battery life. Configurable with up to 24GB unified memory, 2TB SSD.',
                price=1599.00, monthly_price=66.62, months=24, is_new=False, is_featured=False,
                image='/static/images/products/macbook_pro_14_m3.jpg', hero_image='/static/images/hero/macbook_pro_14_m3_hero.jpg',
                color_options=json.dumps(['Space Black', 'Silver']),
                storage_options=json.dumps(['512GB', '1TB', '2TB']),
                specs=json.dumps({'chip': 'M3', 'display': '14.2" Liquid Retina XDR', 'memory': '8GB / 16GB / 24GB unified memory', 'battery': 'Up to 22 hours', 'storage': '512GB / 1TB / 2TB SSD'}),
                chip_family='M3', ram=8, ssd=512, screen_size=14.2, release_year=2023,
                slogan='Mind-blowing. Head-turning.',
                config_upgrades=json.dumps({
                    'memory': ['8GB Unified Memory', '16GB Unified Memory (+$200)', '24GB Unified Memory (+$400)'],
                    'storage': ['512GB SSD', '1TB SSD (+$200)', '2TB SSD (+$400)'],
                    'Upgrade': 'Upgrade options available'
                }),
                keyboard_options=json.dumps([
                    'Backlit Magic Keyboard with Touch ID — US English',
                    'Backlit Magic Keyboard with Touch ID — British English',
                    'Backlit Magic Keyboard with Touch ID — French',
                    'Backlit Magic Keyboard with Touch ID — German',
                    'Backlit Magic Keyboard with Touch ID — Spanish',
                    'Backlit Magic Keyboard with Touch ID — Japanese',
                ])),
        Product(name='MacBook Pro 16-inch M3 Max', slug='macbook-pro-16-inch-m3-max', category='mac', subcategory='macbook-pro',
                subtitle='The most powerful MacBook Pro ever.',
                description='M3 Max chip with 16-core CPU and 40-core GPU, 64GB unified memory, 1TB SSD. Massive 16.2-inch Liquid Retina XDR display.',
                price=3499.00, monthly_price=145.79, months=24, is_new=False, is_featured=False,
                image='/static/images/products/macbook_pro_16_m3.jpg', hero_image='/static/images/hero/macbook_pro_16_m3_hero.jpg',
                color_options=json.dumps(['Space Black', 'Silver']),
                storage_options=json.dumps(['1TB', '2TB', '4TB', '8TB']),
                specs=json.dumps({'chip': 'M3 Max', 'cpu': '16-core CPU', 'gpu': '40-core GPU', 'memory': '64GB unified memory', 'storage': '1TB SSD', 'display': '16.2" Liquid Retina XDR', 'battery': 'Up to 22 hours'}),
                chip_family='M3 Max', ram=64, ssd=1000, cpu_cores=16, gpu_cores=40, screen_size=16.2, release_year=2023),
        # --- iMac M3 ---
        Product(name='iMac 24-inch M3', slug='imac-24-inch-m3', category='mac', subcategory='imac',
                subtitle='Say hello.',
                description='M3 chip, stunning 24-inch 4.5K Retina display, and a colorful all-in-one design.',
                price=1299.00, monthly_price=54.12, months=24, is_new=False, is_featured=False,
                image='/static/images/products/imac_m3.jpg', hero_image='/static/images/hero/imac_m3_hero.jpg',
                color_options=json.dumps(['Blue', 'Green', 'Pink', 'Silver', 'Yellow', 'Orange', 'Purple']),
                storage_options=json.dumps(['256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'M3', 'display': '24" 4.5K Retina', 'memory': '8GB / 16GB / 24GB', 'battery': 'N/A (Desktop)'}),
                chip_family='M3', ram=8, screen_size=24.0, release_year=2023),
        # --- Mac mini M2 Pro ---
        Product(name='Mac mini M2 Pro', slug='mac-mini-m2-pro', category='mac', subcategory='mac-mini',
                subtitle='More muscle. More hustle.',
                description='M2 Pro chip with 12-core CPU and 19-core GPU. 16GB unified memory with option for 32GB. Supports up to 16-core CPU and 19-core GPU for maximum performance.',
                price=1399.00, monthly_price=58.29, months=24, is_new=False, is_featured=False,
                image='/static/images/products/mac_mini.jpg', hero_image='/static/images/hero/mac_mini_hero.jpg',
                color_options=json.dumps(['Silver']),
                storage_options=json.dumps(['512GB', '1TB', '2TB']),
                specs=json.dumps({'chip': 'M2 Pro', 'cpu': '12-core CPU / upgrade to 16-core CPU', 'gpu': '19-core GPU', 'memory': '16GB / 32GB unified memory'}),
                chip_family='M2 Pro', ram=16, ssd=512, cpu_cores=12, gpu_cores=19, release_year=2023),
        # --- Mac product page ---
        Product(name='Mac', slug='mac', category='mac', subcategory='mac-landing',
                subtitle='If you can dream it, Mac can do it.',
                description='Explore the full Mac lineup: MacBook Air, MacBook Pro, iMac, Mac mini, Mac Studio, and Mac Pro. If you can dream it, Mac can do it.',
                price=599.00, monthly_price=24.95, months=24, is_new=False, is_featured=False,
                image='/static/images/products/mac_lineup.jpg', hero_image='/static/images/hero/mac_hero.jpg',
                color_options=json.dumps([]),
                storage_options=json.dumps([]),
                specs=json.dumps({}),
                slogan='If you can dream it, Mac can do it.'),
        # --- Older iPhones ---
        Product(name='iPhone 15 Pro', slug='iphone-15-pro', category='iphone',
                subtitle='Titanium. So strong. So light. So Pro.',
                description='A17 Pro chip, titanium design, 48MP main camera with 5x optical zoom. Available in four stunning titanium finishes.',
                price=999.00, monthly_price=41.62, months=24, is_new=False, is_featured=False,
                image='/static/images/products/iphone_15_pro.jpg', hero_image='/static/images/hero/iphone_15_pro_hero.jpg',
                color_options=json.dumps(['Natural Titanium', 'Blue Titanium', 'White Titanium', 'Black Titanium']),
                storage_options=json.dumps(['128GB', '256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'A17 Pro', 'display': '6.1" Super Retina XDR', 'camera': '48MP Main + 12MP Ultra Wide + 12MP 5x Telephoto', 'battery': 'Up to 23 hours video playback'}),
                chip_family='A17 Pro', release_year=2023, release_date='September 22, 2023'),
        Product(name='iPhone 15 Pro Max', slug='iphone-15-pro-max', category='iphone',
                subtitle='Titanium. So strong. So light. So Pro.',
                description='A17 Pro chip, titanium design, 48MP main camera system.',
                price=1199.00, monthly_price=49.95, months=24, is_new=False, is_featured=False,
                image='/static/images/products/iphone_15_pro_max.jpg', hero_image='/static/images/hero/iphone_15_pro_max_hero.jpg',
                color_options=json.dumps(['Natural Titanium', 'Blue Titanium', 'White Titanium', 'Black Titanium']),
                storage_options=json.dumps(['256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'A17 Pro', 'display': '6.7" Super Retina XDR', 'camera': '48MP Main + 12MP Ultra Wide + 12MP 5x Telephoto'}),
                chip_family='A17 Pro', release_year=2023),
        Product(name='iPhone 14 Pro', slug='iphone-14-pro', category='iphone',
                subtitle='Pro. Beyond.',
                description='A16 Bionic chip, Always-On display, Dynamic Island, and a 48MP main camera.',
                price=999.00, monthly_price=41.62, months=24, is_new=False, is_featured=False,
                image='/static/images/products/iphone_14_pro.jpg', hero_image='/static/images/hero/iphone_14_pro_hero.jpg',
                color_options=json.dumps(['Deep Purple', 'Gold', 'Silver', 'Space Black']),
                storage_options=json.dumps(['128GB', '256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'A16 Bionic', 'display': '6.1" Super Retina XDR', 'camera': '48MP Main + 12MP Ultra Wide + 12MP Telephoto'}),
                chip_family='A16', release_year=2022, release_date='September 16, 2022'),
        Product(name='iPhone 14 Pro Max', slug='iphone-14-pro-max', category='iphone',
                subtitle='Pro. Beyond.',
                description='A16 Bionic chip, 6.7-inch Always-On Super Retina XDR display, Dynamic Island, 48MP camera system.',
                price=1099.00, monthly_price=45.79, months=24, is_new=False, is_featured=False,
                image='/static/images/products/iphone_14_pro_max.jpg', hero_image='/static/images/hero/iphone_14_pro_max_hero.jpg',
                color_options=json.dumps(['Deep Purple', 'Gold', 'Silver', 'Space Black']),
                storage_options=json.dumps(['128GB', '256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'A16 Bionic', 'display': '6.7" Super Retina XDR'}),
                chip_family='A16', release_year=2022),
        Product(name='iPhone 14 Plus', slug='iphone-14-plus', category='iphone',
                subtitle='Big and bigger.',
                description='A15 Bionic chip, 6.7-inch Super Retina XDR display with the longest battery life ever in an iPhone.',
                price=899.00, monthly_price=37.45, months=24, is_new=False, is_featured=False,
                image='/static/images/products/iphone_14_plus.jpg', hero_image='/static/images/hero/iphone_14_plus_hero.jpg',
                color_options=json.dumps(['Midnight', 'Starlight', 'Blue', 'Purple', 'Red', 'Yellow']),
                storage_options=json.dumps(['128GB', '256GB', '512GB']),
                specs=json.dumps({'chip': 'A15 Bionic', 'display': '6.7" Super Retina XDR', 'camera': '12MP dual camera'}),
                chip_family='A15', release_year=2022),
        Product(name='iPhone 13 Pro', slug='iphone-13-pro', category='iphone',
                subtitle='Oh. So. Pro.',
                description='A15 Bionic chip, ProMotion, and a pro camera system.',
                price=999.00, monthly_price=41.62, months=24, is_new=False, is_featured=False,
                image='/static/images/products/iphone_13_pro.jpg', hero_image='/static/images/hero/iphone_13_pro_hero.jpg',
                color_options=json.dumps(['Sierra Blue', 'Silver', 'Gold', 'Graphite', 'Alpine Green']),
                storage_options=json.dumps(['128GB', '256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'A15 Bionic', 'display': '6.1" Super Retina XDR with ProMotion', 'camera': '12MP triple camera'}),
                chip_family='A15', release_year=2021),
        Product(name='iPhone 13 Pro Max', slug='iphone-13-pro-max', category='iphone',
                subtitle='Oh. So. Pro.',
                description='A15 Bionic chip, 6.7-inch ProMotion display, and longest battery life ever.',
                price=1099.00, monthly_price=45.79, months=24, is_new=False, is_featured=False,
                image='/static/images/products/iphone_13_pro_max.jpg', hero_image='/static/images/hero/iphone_13_pro_max_hero.jpg',
                color_options=json.dumps(['Sierra Blue', 'Silver', 'Gold', 'Graphite', 'Alpine Green']),
                storage_options=json.dumps(['128GB', '256GB', '512GB', '1TB']),
                specs=json.dumps({'chip': 'A15 Bionic', 'display': '6.7" Super Retina XDR with ProMotion'}),
                chip_family='A15', release_year=2021),
        # --- iPad Pro M4 variants ---
        Product(name='iPad Pro 13-inch M4', slug='ipad-pro-13-inch-m4', category='ipad', subcategory='ipad-pro',
                subtitle='Unbelievably thin. Incredibly powerful.',
                description='M4 chip, 13-inch Ultra Retina XDR display with ProMotion and P3 wide colour, Thunderbolt / USB 4 connector.',
                price=1299.00, monthly_price=54.12, months=24, is_new=False, is_featured=False,
                image='/static/images/products/ipad_pro_13_m4.jpg', hero_image='/static/images/hero/ipad_pro_13_m4_hero.jpg',
                color_options=json.dumps(['Space Black', 'Silver']),
                storage_options=json.dumps(['256GB', '512GB', '1TB', '2TB']),
                specs=json.dumps({'chip': 'M4', 'display': '13" Ultra Retina XDR with ProMotion', 'camera': '12MP Wide + LiDAR'}),
                chip_family='M4', release_year=2024, release_date='May 15, 2024'),
        Product(name='iPad Pro 11-inch M4', slug='ipad-pro-11-inch-m4', category='ipad', subcategory='ipad-pro',
                subtitle='Unbelievably thin. Incredibly powerful.',
                description='M4 chip, 11-inch Ultra Retina XDR display, LiDAR Scanner.',
                price=999.00, monthly_price=41.62, months=24, is_new=False, is_featured=False,
                image='/static/images/products/ipad_pro_11_m4.jpg', hero_image='/static/images/hero/ipad_pro_11_m4_hero.jpg',
                color_options=json.dumps(['Space Black', 'Silver']),
                storage_options=json.dumps(['256GB', '512GB', '1TB', '2TB']),
                specs=json.dumps({'chip': 'M4', 'display': '11" Ultra Retina XDR', 'camera': '12MP Wide + LiDAR'}),
                chip_family='M4', release_year=2024, release_date='May 15, 2024'),
        # --- iPad mini ---
        Product(name='iPad mini', slug='ipad-mini', category='ipad', subcategory='ipad-mini',
                subtitle='Mega power. Mini icons.',
                description='A17 Pro chip, 8.3-inch Liquid Retina display, Apple Pencil Pro support. 4K video recording at 60 fps.',
                price=499.00, monthly_price=20.79, months=24, is_new=False, is_featured=False,
                image='/static/images/products/ipad_mini.jpg', hero_image='/static/images/hero/ipad_mini_hero.jpg',
                color_options=json.dumps(['Space Gray', 'Blue', 'Purple', 'Starlight']),
                storage_options=json.dumps(['128GB', '256GB', '512GB']),
                specs=json.dumps({'chip': 'A17 Pro', 'display': '8.3" Liquid Retina', 'camera': '12MP Wide', 'video': '4K video recording at 60 fps'}),
                chip_family='A17 Pro', video_recording='4K video recording at 60 fps', release_year=2024),
        Product(name='iPad mini 64GB Wi-Fi + Cellular', slug='ipad-mini-64gb-wi-fi-cellular', category='ipad', subcategory='ipad-mini',
                subtitle='Mega power. Mini icons.',
                description='iPad mini with A15 Bionic chip, 64GB storage, Wi-Fi + Cellular connectivity.',
                price=649.00, monthly_price=27.04, months=24, is_new=False, is_featured=False,
                image='/static/images/products/ipad_mini.jpg', hero_image='/static/images/hero/ipad_mini_hero.jpg',
                color_options=json.dumps(['Space Gray', 'Pink', 'Purple', 'Starlight']),
                storage_options=json.dumps(['64GB', '256GB']),
                specs=json.dumps({'chip': 'A15 Bionic', 'display': '8.3" Liquid Retina', 'connectivity': 'Wi-Fi + Cellular', 'storage': '64GB'}),
                chip_family='A15', connectivity='Wi-Fi + Cellular', release_year=2021),
        # --- Apple Watch older ---
        Product(name='Apple Watch Series 9', slug='apple-watch-series-9', category='watch',
                subtitle='Smarter. Brighter. Mightier.',
                description='S9 SiP, Always-On Retina display, blood oxygen sensing, ECG, temperature sensing.',
                price=399.00, monthly_price=16.62, months=24, is_new=False, is_featured=False,
                image='/static/images/products/watch_series_9.jpg', hero_image='/static/images/hero/watch_series_9_hero.jpg',
                color_options=json.dumps(['Midnight', 'Starlight', 'Silver', 'Red', 'Pink']),
                storage_options=json.dumps(['41mm', '45mm']),
                specs=json.dumps({'chip': 'S9 SiP', 'display': 'Always-On Retina', 'health': 'Blood oxygen, ECG, Temperature sensing'}),
                chip_family='S9', release_year=2023,
                slogan='Smarter. Brighter. Mightier.'),
        Product(name='Apple Watch SE', slug='apple-watch-se', category='watch',
                subtitle='A great deal to love.',
                description='S8 SiP, Crash Detection, heart rate notifications. A smartwatch for everyone.',
                price=249.00, monthly_price=10.37, months=24, is_new=False, is_featured=False,
                image='/static/images/products/watch_se.jpg', hero_image='/static/images/hero/watch_se_hero.jpg',
                color_options=json.dumps(['Midnight', 'Starlight', 'Silver']),
                storage_options=json.dumps(['40mm', '44mm']),
                specs=json.dumps({'chip': 'S8 SiP', 'display': 'Retina', 'health': 'Heart rate, Crash Detection'}),
                chip_family='S8', release_year=2022),
        # --- Apple TV 4K ---
        Product(name='Apple TV 4K', slug='apple-tv-4k', category='tv',
                subtitle='The Icons of icons.',
                description='A15 Bionic chip powers Apple TV 4K. 128GB storage. Experience Dolby Atmos and Dolby Vision. Siri Remote with Touch-enabled clickpad, built-in Find My, and USB-C charging.',
                price=129.00, monthly_price=None, months=0, is_new=False, is_featured=False,
                image='/static/images/products/apple_tv.jpg', hero_image='/static/images/hero/apple_tv_hero.jpg',
                color_options=json.dumps(['Black']),
                storage_options=json.dumps(['64GB', '128GB']),
                specs=json.dumps({'chip': 'A15 Bionic', 'storage': '128GB', 'connectivity': 'Wi-Fi 6, Gigabit Ethernet, Thread', 'siri_remote': 'Touch-enabled clickpad, Find My, USB-C charging', 'dimensions': 'Height: 31 mm, Width: 93 mm, Depth: 93 mm'}),
                chip_family='A15 Bionic', processor='A15 Bionic',
                weight='208 grams', release_year=2022),
        # --- HomePod mini ---
        Product(name='HomePod mini', slug='homepod-mini', category='homepod',
                subtitle='Icons Icons can do.',
                description='Room-filling sound in a compact design. Siri built in.',
                price=99.00, monthly_price=None, months=0, is_new=False, is_featured=False,
                image='/static/images/products/homepod_mini.jpg', hero_image='/static/images/hero/homepod_mini_hero.jpg',
                color_options=json.dumps(['White', 'Yellow', 'Orange', 'Blue', 'Space Gray']),
                storage_options=json.dumps([]),
                specs=json.dumps({'chip': 'S5', 'audio': 'Full-range driver, two passive radiators', 'features': 'Siri, Intercom, Find My'}),
                release_year=2023),
        # --- Apple Vision Pro ---
        Product(name='Apple Vision Pro', slug='apple-vision-pro', category='vision',
                subtitle='Welcome to the era of spatial computing.',
                description='Apple Vision Pro seamlessly blends digital content with your physical space. Weighing approximately 600 grams, it features a micro-OLED display system with 23 million pixels across two displays. Built-in apps include Safari, Photos, Music, Messages, and FaceTime. Available in the United States. Released February 2, 2024.',
                price=3499.00, monthly_price=145.79, months=24, is_new=True, is_featured=False,
                image='/static/images/products/vision_pro.jpg', hero_image='/static/images/hero/vision_pro_hero.jpg',
                color_options=json.dumps(['Silver']),
                storage_options=json.dumps(['256GB', '512GB', '1TB']),
                specs=json.dumps({
                    'chip': 'M2 + R1',
                    'display': 'Micro-OLED, 23 million pixels',
                    'audio': 'Spatial Audio',
                    'sensors': 'LiDAR, TrueDepth',
                    'builtin_apps': ['Safari', 'Photos', 'Music', 'Messages', 'FaceTime',
                                     'TV', 'Mindfulness', 'Keynote', 'Numbers', 'Pages'],
                    'weight': 'Approximately 600 grams',
                }),
                chip_family='M2 + R1', weight='approximately 600 grams',
                release_year=2024, release_date='February 2, 2024'),
        # --- Vision Pro Accessories ---
        Product(name='Apple Vision Pro Travel Case', slug='vision-pro-travel-case', category='accessories', subcategory='vision-pro-accessory',
                subtitle='Carry your Vision Pro with confidence.',
                description='Hard-shell Travel Case designed specifically for Apple Vision Pro.',
                price=199.00, monthly_price=None, months=0, is_new=False, is_featured=False,
                image='/static/images/products/vision_travel_case.jpg', hero_image='/static/images/hero/vision_travel_case_hero.jpg',
                color_options=json.dumps([]),
                storage_options=json.dumps([]),
                specs=json.dumps({'features': 'Hard-shell protective case, custom fit'})),
        Product(name='Apple Vision Pro Battery Pack', slug='vision-pro-battery', category='accessories', subcategory='vision-pro-accessory',
                subtitle='Extended Battery for Vision Pro.',
                description='External Battery pack for Apple Vision Pro providing up to 2 hours of additional use.',
                price=199.00, monthly_price=None, months=0, is_new=False, is_featured=False,
                image='/static/images/products/vision_battery.jpg', hero_image='/static/images/hero/vision_battery_hero.jpg',
                color_options=json.dumps([]),
                storage_options=json.dumps([]),
                specs=json.dumps({'features': 'Battery, 2 hours extended use'})),
        Product(name='Apple Vision Pro Light Seal', slug='vision-pro-light-seal', category='accessories', subcategory='vision-pro-accessory',
                subtitle='Custom fit for your face.',
                description='Light Seal replacement for Apple Vision Pro, available in multiple sizes.',
                price=199.00, monthly_price=None, months=0, is_new=False, is_featured=False,
                image='/static/images/products/vision_light_seal.jpg', hero_image='/static/images/hero/vision_light_seal_hero.jpg',
                color_options=json.dumps([]),
                storage_options=json.dumps([]),
                specs=json.dumps({'features': 'Light Seal, multiple sizes'})),
        # --- AirPods 3rd gen variants ---
        Product(name='AirPods 3rd generation (Lightning)', slug='airpods-3-lightning', category='airpods',
                subtitle='All-new design. Spatial Audio.',
                description='AirPods 3rd generation with Lightning charging case. Spatial Audio, Adaptive EQ, sweat and water resistant.',
                price=169.00, monthly_price=7.04, months=24, is_new=False, is_featured=False,
                image='/static/images/products/airpods_3.jpg', hero_image='/static/images/hero/airpods_3_hero.jpg',
                color_options=json.dumps(['White']),
                storage_options=json.dumps([]),
                specs=json.dumps({'chip': 'H1', 'audio': 'Spatial Audio, Adaptive EQ', 'charging': 'Lightning charging case'})),
        Product(name='AirPods 3rd generation (MagSafe)', slug='airpods-3-magsafe', category='airpods',
                subtitle='All-new design. Spatial Audio.',
                description='AirPods 3rd generation with MagSafe charging case. Spatial Audio, Adaptive EQ, sweat and water resistant.',
                price=179.00, monthly_price=7.45, months=24, is_new=False, is_featured=False,
                image='/static/images/products/airpods_3_magsafe.jpg', hero_image='/static/images/hero/airpods_3_magsafe_hero.jpg',
                color_options=json.dumps(['White']),
                storage_options=json.dumps([]),
                specs=json.dumps({'chip': 'H1', 'audio': 'Spatial Audio, Adaptive EQ', 'charging': 'MagSafe charging case'})),
        # --- Smart Folio for iPad ---
        Product(name='Smart Folio for iPad Air 11-inch', slug='smart-folio-for-ipad-air-11-inch', category='accessories', subcategory='ipad-accessory',
                subtitle='A Smart Folio for every iPad Air.',
                description='Slim, lightweight Smart Folio for iPad Air 11-inch. Automatically wakes and sleeps your iPad. Available in multiple colors.',
                price=79.00, monthly_price=None, months=0, is_new=False, is_featured=False,
                image='/static/images/products/smart_folio.jpg', hero_image='/static/images/hero/smart_folio_hero.jpg',
                color_options=json.dumps(['Charcoal Gray', 'Denim', 'Sage', 'Purple']),
                storage_options=json.dumps([]),
                specs=json.dumps({'features': 'Auto wake/sleep, foldable stand, magnetic attachment'})),
        Product(name='Smart Folio for iPad Pro 13-inch M4', slug='smart-folio-for-ipad-pro-13-inch-m4', category='accessories', subcategory='ipad-accessory',
                subtitle='Designed for iPad Pro.',
                description='Smart Folio for iPad Pro 13-inch (M4). Two viewing angles, auto wake/sleep.',
                price=99.00, monthly_price=None, months=0, is_new=False, is_featured=False,
                image='/static/images/products/smart_folio_pro.jpg', hero_image='/static/images/hero/smart_folio_pro_hero.jpg',
                color_options=json.dumps(['Black', 'Denim', 'Sage']),
                storage_options=json.dumps([]),
                specs=json.dumps({'features': 'Auto wake/sleep, two viewing positions, magnetic attachment'}),
                pickup_available=True),
        Product(name='Smart Folio for iPad Pro 11-inch M4', slug='smart-folio-for-ipad-pro-11-inch-m4', category='accessories', subcategory='ipad-accessory',
                subtitle='Designed for iPad Pro.',
                description='Smart Folio for iPad Pro 11-inch (M4). Slim and lightweight.',
                price=79.00, monthly_price=None, months=0, is_new=False, is_featured=False,
                image='/static/images/products/smart_folio_pro_11.jpg', hero_image='/static/images/hero/smart_folio_pro_11_hero.jpg',
                color_options=json.dumps(['Black', 'Denim', 'Sage']),
                storage_options=json.dumps([]),
                specs=json.dumps({'features': 'Auto wake/sleep, magnetic attachment'})),
    ]

    for p in products:
        db.session.add(p)
    db.session.commit()
    print(f"Seeded {len(products)} products")

    # --- Trade-In Values ---
    trade_in_values = [
        TradeInValue(device='iPhone 15 Pro Max', condition='good', value=650.00,
                     notes='Trade in your iPhone 15 Pro Max for credit toward a new iPhone.'),
        TradeInValue(device='iPhone 15 Pro', condition='good', value=570.00,
                     notes='Trade in your iPhone 15 Pro for credit toward a new iPhone.'),
        TradeInValue(device='iPhone 14 Pro Max', condition='good', value=500.00,
                     notes='Trade in your iPhone 14 Pro Max for credit toward a new iPhone.'),
        TradeInValue(device='iPhone 14 Pro', condition='good', value=430.00,
                     notes='Trade in your iPhone 14 Pro for credit toward a new iPhone.'),
        TradeInValue(device='iPhone 13 Pro Max', condition='good', value=440.00,
                     notes='Trade in your iPhone 13 Pro Max for credit toward a new iPhone.'),
        TradeInValue(device='iPhone 13 Pro', condition='good', value=370.00,
                     notes='Trade in your iPhone 13 Pro for credit toward a new iPhone.'),
        TradeInValue(device='iPhone 12 Pro Max', condition='good', value=300.00,
                     notes='Trade in your iPhone 12 Pro Max for credit toward a new iPhone.'),
        TradeInValue(device='iPhone 12 Pro', condition='good', value=250.00,
                     notes='Trade in your iPhone 12 Pro for credit toward a new iPhone.'),
        TradeInValue(device='iPhone 11 Pro Max', condition='good', value=230.00,
                     notes='Trade in your iPhone 11 Pro Max for credit toward a new iPhone.'),
        TradeInValue(device='iPhone 11 Pro', condition='good', value=200.00,
                     notes='Trade in your iPhone 11 Pro for credit toward a new iPhone.'),
        TradeInValue(device='MacBook Pro', condition='good', value=500.00,
                     notes='Trade in your MacBook Pro for credit toward a new Mac.'),
        TradeInValue(device='MacBook Air', condition='good', value=350.00,
                     notes='Trade in your MacBook Air for credit toward a new Mac.'),
        TradeInValue(device='iPad Pro', condition='good', value=380.00,
                     notes='Trade in your iPad Pro for credit toward a new iPad.'),
        TradeInValue(device='Apple Watch', condition='good', value=120.00,
                     notes='Trade in your Apple Watch for credit toward a new Watch.'),
    ]
    for tv in trade_in_values:
        db.session.add(tv)
    db.session.commit()
    print(f"Seeded {len(trade_in_values)} trade-in values")

    # --- Support Articles ---
    support_articles = [
        SupportArticle(
            slug='ios-17-new-features', topic='ios',
            title='New features in iOS 17',
            summary='Explore StandBy, NameDrop, and other new features in iOS 17 for iPhone.',
            body='iOS 17 introduces exciting new features including StandBy mode, NameDrop for sharing contact information, Live Voicemail, Journal app, and improvements to Messages, FaceTime, and autocorrect. Compatible with iPhone 12 and later, iPhone SE (3rd generation). iOS 17 brings a more personal, intuitive experience to your iPhone.',
            compat=json.dumps(['iPhone 12', 'iPhone 12 mini', 'iPhone 12 Pro', 'iPhone 12 Pro Max', 'iPhone 13', 'iPhone 13 mini', 'iPhone 13 Pro', 'iPhone 13 Pro Max', 'iPhone 14', 'iPhone 14 Plus', 'iPhone 14 Pro', 'iPhone 14 Pro Max', 'iPhone 15', 'iPhone 15 Plus', 'iPhone 15 Pro', 'iPhone 15 Pro Max', 'iPhone SE (3rd generation)']),
            tags=json.dumps(['ios-17', 'standby', 'namedrop', 'new-features']),
        ),
        SupportArticle(
            slug='apple-repair-options', topic='repair',
            title='Apple Repair Options',
            summary='Learn about the different ways to get Apple Repair service for your device.',
            body='Apple offers several repair options: Mail-in repair — ship your device to an Apple Repair Center. Carry-in repair — bring your device to an Apple Store or Apple Authorized Service Provider. Onsite repair (business only) — certain business customers qualify for onsite repair. Express Replacement Service — receive a replacement before sending the original. Self Service Repair — order parts and tools to repair eligible products yourself.',
            tags=json.dumps(['repair', 'mail-in', 'carry-in', 'apple-repair']),
        ),
        SupportArticle(
            slug='iphone-trade-in-offers', topic='iphone',
            title='iPhone Trade-In Offers',
            summary='Get credit toward a new iPhone when you trade in your eligible device with Apple Trade In.',
            body='Apple Trade In makes it easy to get credit toward a new iPhone. Estimated trade-in values: iPhone 15 Pro Max up to $650, iPhone 14 Pro Max up to $500, iPhone 13 Pro Max up to $440, iPhone 12 Pro Max up to $300, iPhone 11 Pro Max up to $230. Values may vary based on condition. Visit apple.com/trade-in for current trade-in values.',
            tags=json.dumps(['trade-in', 'iphone', 'credit', 'upgrade']),
        ),
        SupportArticle(
            slug='forgot-apple-id-password', topic='apple-id',
            title='If you forgot your Apple ID password',
            summary='Learn how to reset your Apple ID password so you can get back into your account.',
            body='If you forgot your Apple ID password, you can reset it at iforgot.apple.com. You can also reset your password from any trusted Apple device: On iPhone or iPad, go to Settings > [Your Name] > Password & Security > Change Password. On Mac, go to Apple menu > System Settings > [Your Name] > Password & Security > Change Password. If you no longer have access to any of your trusted devices, visit iforgot.apple.com and follow the account recovery process.',
            tags=json.dumps(['apple-id', 'forgot', 'password', 'reset', 'iforgot.apple.com']),
        ),
        SupportArticle(
            slug='apple-watch-series-7-8-9-updates', topic='watch',
            title='Updates in Apple Watch Series 7, 8, and 9',
            summary='Compare the features and updates across Apple Watch Series 7, Series 8, and Series 9.',
            body='Apple Watch has evolved significantly across recent generations. Series 7 (2021): Larger, more crack-resistant display with fast charging, compatible with watchOS 8+. Series 8 (2022): Temperature sensing, Crash Detection, improved workout metrics, compatible with watchOS 9+. Series 9 (2023): S9 SiP chip, Double Tap gesture, brighter 2000-nit display, on-device Siri, precise Find My for iPhone, compatible with watchOS 10+. All three generations support ECG, blood oxygen sensing, and fall detection.',
            tags=json.dumps(['apple-watch', 'series-7', 'series-8', 'series-9', 'watchOS', 'updates']),
        ),
    ]
    for sa in support_articles:
        db.session.add(sa)
    db.session.commit()
    print(f"Seeded {len(support_articles)} support articles")


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def _get_product(name_fragment):
    """Return first product whose name contains name_fragment (case-insensitive)."""
    return Product.query.filter(Product.name.ilike(f'%{name_fragment}%')).first()


def seed_benchmark_users():
    """Seed 4 benchmark users with addresses, payment methods, orders, and cart items.
    Called AFTER expand_catalog.py. Idempotent — checks if users exist first.
    """
    if User.query.filter_by(email='alice.j@test.com').first():
        return

    from datetime import timedelta

    # ------------------------------------------------------------------
    # Create users
    # ------------------------------------------------------------------
    users_data = [
        dict(first_name='Alice', last_name='Johnson', email='alice.j@test.com',
             phone='415-555-0101', city='San Francisco', state='CA', zip_code='94103',
             address='742 Market Street'),
        dict(first_name='Bob', last_name='Chen', email='bob.c@test.com',
             phone='650-555-0102', city='Palo Alto', state='CA', zip_code='94301',
             address='350 University Avenue'),
        dict(first_name='Carol', last_name='Davis', email='carol.d@test.com',
             phone='310-555-0103', city='Los Angeles', state='CA', zip_code='90028',
             address='6801 Hollywood Boulevard'),
        dict(first_name='David', last_name='Kim', email='david.k@test.com',
             phone='212-555-0104', city='New York', state='NY', zip_code='10001',
             address='500 8th Avenue'),
    ]

    users = []
    for ud in users_data:
        u = User(
            first_name=ud['first_name'], last_name=ud['last_name'],
            email=ud['email'], phone=ud['phone'],
            address=ud['address'], city=ud['city'],
            state=ud['state'], zip_code=ud['zip_code'],
        )
        u.set_password('TestPass123!')
        db.session.add(u)
        users.append(u)
    db.session.flush()  # get IDs

    alice, bob, carol, david = users

    # ------------------------------------------------------------------
    # Saved Addresses
    # ------------------------------------------------------------------
    def mk_addr(user, label, fn, ln, addr, city, state, zip_, phone, default=False):
        a = SavedAddress(user_id=user.id, label=label, first_name=fn, last_name=ln,
                         address=addr, city=city, state=state, zip_code=zip_,
                         phone=phone, is_default=default)
        db.session.add(a)
        return a

    # Alice — home + work
    mk_addr(alice, 'Home', 'Alice', 'Johnson', '742 Market Street', 'San Francisco', 'CA', '94103', '415-555-0101', default=True)
    mk_addr(alice, 'Work', 'Alice', 'Johnson', '1 Infinite Loop', 'Cupertino', 'CA', '95014', '415-555-0101')
    mk_addr(alice, 'Gift', 'Mom', 'Johnson', '88 Pine Street', 'Seattle', 'WA', '98101', '206-555-0201')

    # Bob — home + work
    mk_addr(bob, 'Home', 'Bob', 'Chen', '350 University Avenue', 'Palo Alto', 'CA', '94301', '650-555-0102', default=True)
    mk_addr(bob, 'Work', 'Bob', 'Chen', '2550 Garcia Ave', 'Mountain View', 'CA', '94043', '650-555-0102')

    # Carol — home + gift
    mk_addr(carol, 'Home', 'Carol', 'Davis', '6801 Hollywood Boulevard', 'Los Angeles', 'CA', '90028', '310-555-0103', default=True)
    mk_addr(carol, 'Gift', 'Sarah', 'Davis', '4320 Sunset Drive', 'Austin', 'TX', '78701', '512-555-0301')
    mk_addr(carol, 'Work', 'Carol', 'Davis', '2121 Avenue of the Stars', 'Los Angeles', 'CA', '90067', '310-555-0103')

    # David — home + work + gift
    mk_addr(david, 'Home', 'David', 'Kim', '500 8th Avenue', 'New York', 'NY', '10001', '212-555-0104', default=True)
    mk_addr(david, 'Work', 'David', 'Kim', '11 Penn Plaza', 'New York', 'NY', '10001', '212-555-0104')
    mk_addr(david, 'Gift', 'Mom', 'Kim', '42 Elm Street', 'Flushing', 'NY', '11354', '718-555-0309')

    # ------------------------------------------------------------------
    # Payment Methods
    # ------------------------------------------------------------------
    def mk_pm(user, card_type, last4, exp_m, exp_y, name, default=False):
        if default:
            PaymentMethod.query.filter_by(user_id=user.id, is_default=True).update({'is_default': False})
        pm = PaymentMethod(user_id=user.id, card_type=card_type, last4=last4,
                           exp_month=exp_m, exp_year=exp_y, cardholder_name=name,
                           is_default=default)
        db.session.add(pm)
        return pm

    mk_pm(alice, 'Visa',       '4242', 12, 2027, 'Alice Johnson', default=True)
    mk_pm(alice, 'Mastercard', '5555', 3,  2026, 'Alice Johnson')
    mk_pm(alice, 'Visa',       '1234', 9,  2028, 'Alice M Johnson')

    mk_pm(bob, 'Visa',       '6789', 6, 2026, 'Bob Chen', default=True)
    mk_pm(bob, 'Amex',       '0001', 11, 2027, 'Bob Chen')

    mk_pm(carol, 'Mastercard', '3344', 8, 2027, 'Carol Davis', default=True)
    mk_pm(carol, 'Visa',       '7788', 1, 2029, 'Carol Davis')
    mk_pm(carol, 'Amex',       '9900', 5, 2026, 'Carol Davis')

    mk_pm(david, 'Visa',       '2468', 4, 2028, 'David Kim', default=True)
    mk_pm(david, 'Mastercard', '1357', 7, 2027, 'David Kim')

    db.session.flush()

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------
    def mk_order(user, status, product_name, qty, color, storage, days_ago,
                 ship_addr=None, pay='Visa ending in 4242'):
        p = _get_product(product_name)
        if not p:
            return None
        total = p.price * qty
        if ship_addr:
            addr_str = f"{ship_addr.address}, {ship_addr.city}, {ship_addr.state} {ship_addr.zip_code}"
        else:
            addr_str = f"{user.address}, {user.city}, {user.state} {user.zip_code}"
        order = Order(
            user_id=user.id,
            order_number=f"APL-{secrets.token_hex(4).upper()}",
            status=status,
            total=total,
            shipping_address=addr_str,
            shipping_method='standard',
            payment_method=pay,
            created_at=datetime.utcnow() - timedelta(days=days_ago),
            updated_at=datetime.utcnow() - timedelta(days=days_ago),
        )
        db.session.add(order)
        db.session.flush()
        oi = OrderItem(order_id=order.id, product_id=p.id, quantity=qty,
                       price=p.price, color=color, storage=storage)
        db.session.add(oi)
        return order

    alice_addrs = SavedAddress.query.filter_by(user_id=alice.id).all()
    alice_home = next((a for a in alice_addrs if a.label == 'Home'), alice_addrs[0])
    alice_work = next((a for a in alice_addrs if a.label == 'Work'), alice_addrs[0])

    mk_order(alice, 'delivered',  'iPhone 17 Pro', 1, 'Black Titanium', '256GB', 45,
             ship_addr=alice_home, pay='Visa ending in 4242')
    mk_order(alice, 'shipped',    'AirPods Pro',   1, '',               '',      8,
             ship_addr=alice_home, pay='Mastercard ending in 5555')
    mk_order(alice, 'processing', 'MacBook Air 13', 1, 'Midnight',      '256GB', 1,
             ship_addr=alice_work, pay='Visa ending in 4242')
    mk_order(alice, 'cancelled',  'Apple Watch Series 9', 1, 'Midnight', '41mm', 30,
             ship_addr=alice_home, pay='Visa ending in 4242')
    mk_order(alice, 'delivered',  'iPad Pro 11',   1, 'Space Black',    '256GB', 90,
             ship_addr=alice_home, pay='Visa ending in 1234')

    mk_order(bob, 'delivered',  'iPhone 15',        1, 'Blue', '128GB', 60, pay='Visa ending in 6789')
    mk_order(bob, 'processing', 'AirPods 4',        1, '',     '',      2,  pay='Amex ending in 0001')
    mk_order(bob, 'shipped',    'Apple Watch SE',   1, 'Midnight', '40mm', 14, pay='Visa ending in 6789')
    mk_order(bob, 'cancelled',  'HomePod mini',     1, 'Yellow', '',    20,  pay='Visa ending in 6789')

    carol_addrs = SavedAddress.query.filter_by(user_id=carol.id).all()
    carol_gift = next((a for a in carol_addrs if a.label == 'Gift'), carol_addrs[0])
    mk_order(carol, 'delivered',  'iPhone 17',        1, 'Pink',   '128GB', 50,
             ship_addr=carol_gift, pay='Mastercard ending in 3344')
    mk_order(carol, 'shipped',    'AirPods Max',      1, 'Blue',   '',      10,
             pay='Visa ending in 7788')
    mk_order(carol, 'processing', 'iPad Air',         1, 'Blue',   '256GB', 2,
             pay='Mastercard ending in 3344')
    mk_order(carol, 'delivered',  'Apple Pencil Pro', 1, '',       '',      35,
             pay='Amex ending in 9900')

    mk_order(david, 'delivered',  'MacBook Pro 16',   1, 'Space Black', '512GB', 70, pay='Visa ending in 2468')
    mk_order(david, 'delivered',  'iPhone 17 Pro Max', 1, 'Natural Titanium', '512GB', 40, pay='Visa ending in 2468')
    mk_order(david, 'shipped',    'Apple Vision Pro',  1, '',  '',      15, pay='Mastercard ending in 1357')
    mk_order(david, 'processing', 'MacBook Air 15',    1, 'Silver', '512GB', 1, pay='Visa ending in 2468')
    mk_order(david, 'cancelled',  'Mac mini',          1, 'Silver', '',     25, pay='Mastercard ending in 1357')

    # ------------------------------------------------------------------
    # Pre-seed cart for Alice
    # ------------------------------------------------------------------
    for name_frag, color, storage in [
        ('iPhone 17 Pro', 'Desert Titanium', '128GB'),
        ('AirPods Pro',   '',                ''),
    ]:
        p = _get_product(name_frag)
        if p:
            ci = CartItem(user_id=alice.id, product_id=p.id, quantity=1,
                          color=color, storage=storage)
            db.session.add(ci)

    db.session.commit()
    print("Seeded 4 benchmark users (alice, bob, carol, david) with addresses, payments, orders, and cart items.")


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
