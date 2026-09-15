#!/usr/bin/env python3
"""Booking.com mirror — Flask app with real scraped content."""
import os
import json
import random
import secrets
from datetime import datetime, timedelta, date
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    jsonify, session, abort, g
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, IntegerField, TextAreaField, SelectField, DateField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional as OptValidator, NumberRange
from sqlalchemy import func, or_, and_

BASE_DIR = Path(__file__).parent
INSTANCE = BASE_DIR / 'instance'
INSTANCE.mkdir(exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'booking-mirror-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{INSTANCE}/booking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)


# =====================================================================
# MODELS
# =====================================================================

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    phone = db.Column(db.String(30))
    country = db.Column(db.String(80))
    city = db.Column(db.String(80))
    address = db.Column(db.String(200))
    postal_code = db.Column(db.String(20))
    genius_level = db.Column(db.Integer, default=1)  # 1-3, loyalty tier
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship('Booking', backref='user', lazy=True, cascade='all, delete-orphan')
    cart_items = db.relationship('CartItem', backref='user', lazy=True, cascade='all, delete-orphan')
    saved = db.relationship('SavedProperty', backref='user', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='user', lazy=True, cascade='all, delete-orphan')
    payment_methods = db.relationship('PaymentMethod', backref='user', lazy=True, cascade='all, delete-orphan')

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.email.split('@')[0]


class City(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    display = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    country = db.Column(db.String(100), nullable=False)
    country_code = db.Column(db.String(5))
    description = db.Column(db.Text)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    properties_count = db.Column(db.Integer, default=0)
    average_rating = db.Column(db.Float, default=8.0)
    hero_image = db.Column(db.String(300))
    gallery_json = db.Column(db.Text)  # JSON list of image paths

    # Nearest beach reference point — used for sort=distance_beach on /search.
    # Every city must have a defined nearest-beach point (real booking.com
    # offers this sort universally; for inland cities the distance is just
    # large). See BEACH_SEED in this file.
    nearest_beach_name = db.Column(db.String(120))
    nearest_beach_lat = db.Column(db.Float)
    nearest_beach_lng = db.Column(db.Float)

    properties = db.relationship('Property', backref='city', lazy=True)

    def get_gallery(self):
        if self.gallery_json:
            return json.loads(self.gallery_json)
        return []


class DestCategory(db.Model):
    """Trip type / destination category (Beach, City, Ski, etc.)"""
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))


class PropertyType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))


class Property(db.Model):
    """A stay / hotel / accommodation."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(250), unique=True, nullable=False, index=True)
    property_type = db.Column(db.String(50), default='Hotel')
    stars = db.Column(db.Integer, default=4)
    neighborhood = db.Column(db.String(120))
    city_id = db.Column(db.Integer, db.ForeignKey('city.id'), nullable=False)
    dest_category = db.Column(db.String(50))  # city-breaks, beach, ski, etc.
    address = db.Column(db.String(250))
    description = db.Column(db.Text)
    short_desc = db.Column(db.String(500))

    price_per_night = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(5), default='USD')
    brand = db.Column(db.String(60), default='Independent')  # Hilton, Marriott, Accor, IHG, Hyatt, Independent, etc.

    rating = db.Column(db.Float, default=8.5)
    review_count = db.Column(db.Integer, default=0)
    rating_label = db.Column(db.String(30), default='Very Good')  # Superb, Excellent, etc.

    image = db.Column(db.String(300))           # Main image
    gallery_json = db.Column(db.Text)           # JSON array of image paths
    amenities_json = db.Column(db.Text)         # JSON list of amenities
    room_types_json = db.Column(db.Text)        # JSON list of room types
    review_scores_json = db.Column(db.Text)     # JSON dict of sub-score categories

    is_featured = db.Column(db.Boolean, default=False)
    is_genius_deal = db.Column(db.Boolean, default=False)
    discount_percent = db.Column(db.Integer, default=0)
    free_cancellation = db.Column(db.Boolean, default=True)
    breakfast_included = db.Column(db.Boolean, default=False)
    distance_from_center = db.Column(db.Float, default=1.5)  # km

    # Task-driven amenity flags (denormalised from amenities_json for fast filtering)
    has_wifi = db.Column(db.Boolean, default=True)
    has_pool = db.Column(db.Boolean, default=False)
    has_parking = db.Column(db.Boolean, default=False)
    has_gym = db.Column(db.Boolean, default=False)
    has_spa = db.Column(db.Boolean, default=False)
    has_airport_shuttle = db.Column(db.Boolean, default=False)
    has_pet_friendly = db.Column(db.Boolean, default=False)
    has_air_conditioning = db.Column(db.Boolean, default=True)
    has_bicycle_rental = db.Column(db.Boolean, default=False)
    has_restaurant = db.Column(db.Boolean, default=False)
    has_beach_access = db.Column(db.Boolean, default=False)

    max_guests = db.Column(db.Integer, default=4)
    landmark_tags = db.Column(db.Text)  # JSON list of nearby landmark tokens

    # Geographic coordinates (used for "X.X miles from <landmark>" on search cards)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviews = db.relationship('Review', backref='property', lazy=True, cascade='all, delete-orphan')

    def get_gallery(self):
        if self.gallery_json:
            return json.loads(self.gallery_json)
        return []

    def get_amenities(self):
        if self.amenities_json:
            return json.loads(self.amenities_json)
        return []

    def get_rooms(self):
        if self.room_types_json:
            return json.loads(self.room_types_json)
        return []

    def get_review_scores(self):
        """Return a dict of review sub-score categories.

        If `review_scores_json` isn't populated, deterministically synthesise a
        plausible breakdown from the overall rating so templates always have
        something to render.
        """
        if self.review_scores_json:
            try:
                data = json.loads(self.review_scores_json)
                if isinstance(data, dict) and data:
                    return data
            except Exception:
                pass
        # Synthesise from overall rating — deterministic per-property
        base = self.rating or 8.5
        seed = (self.id or 0) * 101 + 7
        def _tweak(offset):
            # returns rating shifted by offset +/- small jitter in [-0.35, 0.35]
            rng = ((seed + offset * 13) % 71) / 100.0  # 0.00..0.70
            jitter = rng - 0.35
            val = base + offset + jitter
            # clamp to 0..10 and round to 1 decimal
            if val < 0:
                val = 0.0
            if val > 10:
                val = 10.0
            return round(val, 1)
        return {
            'Cleanliness': _tweak(0.3),
            'Comfort': _tweak(0.1),
            'Staff': _tweak(0.4),
            'Facilities': _tweak(-0.2),
            'Location': _tweak(0.2),
            'Value for money': _tweak(-0.3),
            'Free WiFi': _tweak(0.1),
        }

    def get_landmark_tags(self):
        if self.landmark_tags:
            try:
                return json.loads(self.landmark_tags)
            except Exception:
                return []
        return []

    @property
    def discounted_price(self):
        if self.discount_percent:
            return round(self.price_per_night * (100 - self.discount_percent) / 100, 2)
        return self.price_per_night


class Landmark(db.Model):
    """Well-known landmarks / POIs / metros / neighborhoods that users may
    type into the search box. Used to resolve a search query to a (lat, lng)
    reference point so we can show 'X.X miles from <landmark>' on every
    result card, exactly like real booking.com."""
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False, index=True)  # canonical display name
    aliases_json = db.Column(db.Text)  # JSON list of alternative names users may type
    city_id = db.Column(db.Integer, db.ForeignKey('city.id'), nullable=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    subway_access = db.Column(db.Boolean, default=False)
    kind = db.Column(db.String(40), default='landmark')  # landmark / metro / neighborhood / poi

    def aliases(self):
        if self.aliases_json:
            try:
                return json.loads(self.aliases_json)
            except Exception:
                return []
        return []


class CartItem(db.Model):
    """Booking cart - pending reservations before checkout."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    adults = db.Column(db.Integer, default=2)
    children = db.Column(db.Integer, default=0)
    rooms = db.Column(db.Integer, default=1)
    room_type = db.Column(db.String(100), default='Standard Double Room')
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def nights(self):
        return max(1, (self.check_out - self.check_in).days)

    @property
    def total(self):
        return round(self.property.discounted_price * self.nights * self.rooms, 2)

    property = db.relationship('Property')


class Booking(db.Model):
    """Confirmed reservation."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    booking_number = db.Column(db.String(30), unique=True, nullable=False)
    status = db.Column(db.String(30), default='confirmed')  # confirmed, cancelled, completed
    total = db.Column(db.Float, nullable=False)
    nights = db.Column(db.Integer, default=1)
    guest_first_name = db.Column(db.String(80))
    guest_last_name = db.Column(db.String(80))
    guest_email = db.Column(db.String(120))
    guest_phone = db.Column(db.String(30))
    guest_country = db.Column(db.String(80))
    special_requests = db.Column(db.Text)
    payment_method = db.Column(db.String(50), default='Credit Card')
    card_last4 = db.Column(db.String(4))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('BookingItem', backref='booking', lazy=True, cascade='all, delete-orphan')


class BookingItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    adults = db.Column(db.Integer, default=2)
    children = db.Column(db.Integer, default=0)
    rooms = db.Column(db.Integer, default=1)
    room_type = db.Column(db.String(100))
    price_per_night = db.Column(db.Float)
    subtotal = db.Column(db.Float)

    property = db.relationship('Property')


class SavedProperty(db.Model):
    """Wishlist / saved properties."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    list_name = db.Column(db.String(100), default='My next trip')
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)

    property = db.relationship('Property')


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    title = db.Column(db.String(150))
    body_positive = db.Column(db.Text)
    body_negative = db.Column(db.Text)
    traveller_type = db.Column(db.String(40))  # Couple, Family, Business, Solo
    stay_length = db.Column(db.Integer, default=2)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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


# =====================================================================
# FORMS
# =====================================================================

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    first_name = StringField('First name', validators=[DataRequired()])
    last_name = StringField('Last name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm password', validators=[DataRequired(), EqualTo('password')])


class ProfileForm(FlaskForm):
    first_name = StringField('First name', validators=[DataRequired()])
    last_name = StringField('Last name', validators=[DataRequired()])
    phone = StringField('Phone', validators=[OptValidator()])
    country = StringField('Country', validators=[OptValidator()])
    city = StringField('City', validators=[OptValidator()])
    address = StringField('Address', validators=[OptValidator()])
    postal_code = StringField('Postal code', validators=[OptValidator()])


class PasswordChangeForm(FlaskForm):
    current_password = PasswordField('Current password', validators=[DataRequired()])
    new_password = PasswordField('New password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm new password', validators=[DataRequired(), EqualTo('new_password')])


class CheckoutForm(FlaskForm):
    first_name = StringField('First name', validators=[DataRequired()])
    last_name = StringField('Last name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[DataRequired()])
    country = StringField('Country', validators=[DataRequired()])
    special_requests = TextAreaField('Special requests', validators=[OptValidator()])
    saved_payment_id = IntegerField('Saved payment', validators=[OptValidator()])
    card_number = StringField('Card number', validators=[OptValidator(), Length(min=0, max=19)])
    card_name = StringField('Name on card', validators=[OptValidator()])
    card_exp = StringField('Expiry', validators=[OptValidator()])
    card_cvv = StringField('CVV', validators=[OptValidator(), Length(min=0, max=4)])


class ReviewForm(FlaskForm):
    rating = SelectField('Rating', choices=[(str(i), f'{i}/10') for i in range(1, 11)], validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired(), Length(max=150)])
    body_positive = TextAreaField('What did you like?', validators=[OptValidator()])
    body_negative = TextAreaField('What could have been better?', validators=[OptValidator()])
    traveller_type = SelectField('Traveller type', choices=[
        ('Couple', 'Couple'), ('Family', 'Family'),
        ('Business', 'Business'), ('Solo', 'Solo'), ('Group', 'Group of friends')
    ])


# =====================================================================
# HELPERS
# =====================================================================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def derive_amenity_flags(amenities_list):
    """Map an amenities list (or iterable of strings) to boolean flags
    used by the Property model's filtering columns."""
    text = ' '.join(a.lower() for a in (amenities_list or []))
    return {
        'has_wifi': ('wifi' in text) or ('wi-fi' in text) or ('internet' in text),
        'has_pool': ('pool' in text) or ('swimming' in text),
        'has_parking': 'parking' in text,
        'has_gym': ('gym' in text) or ('fitness' in text),
        'has_spa': ('spa' in text) or ('wellness' in text),
        'has_airport_shuttle': ('airport shuttle' in text) or ('shuttle' in text),
        'has_pet_friendly': ('pet' in text),
        'has_air_conditioning': ('air conditioning' in text) or ('ac' in text and 'pack' not in text),
        'has_bicycle_rental': ('bicycle' in text) or ('bike' in text),
        'has_restaurant': 'restaurant' in text,
        'has_beach_access': ('beach' in text) or ('beachfront' in text) or ('sea view' in text),
    }


def rating_label_for(score):
    if score >= 9.0:
        return 'Exceptional'
    if score >= 8.5:
        return 'Superb'
    if score >= 8.0:
        return 'Very Good'
    if score >= 7.0:
        return 'Good'
    if score >= 6.0:
        return 'Pleasant'
    return 'Review Score'


def slugify(text):
    import re
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '-', s)
    return s[:200]


# Static currency conversion rates (1 USD = ...)
CURRENCY_RATES = {
    'USD': 1.0,
    'EUR': 0.92,
    'GBP': 0.79,
    'CNY': 7.2,
    'JPY': 151.3,
}
CURRENCY_SYMBOLS = {
    'USD': '$',
    'EUR': '\u20ac',
    'GBP': '\u00a3',
    'CNY': '\u00a5',
    'JPY': '\u00a5',
}


@app.context_processor
def inject_global():
    cart_count = 0
    saved_count = 0
    if current_user.is_authenticated:
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
        saved_count = SavedProperty.query.filter_by(user_id=current_user.id).count()
    from flask_wtf.csrf import generate_csrf
    # Currency selector — allow ?currency=CNY on any page or session flag
    cur_req = (request.args.get('currency') or '').upper()
    if cur_req in CURRENCY_RATES:
        session['currency'] = cur_req
    currency_code = session.get('currency', 'USD')
    if currency_code not in CURRENCY_RATES:
        currency_code = 'USD'
    return {
        'cart_count': cart_count,
        'saved_count': saved_count,
        'current_year': datetime.now().year,
        'csrf_token_value': generate_csrf(),
        'currency_code': currency_code,
        'currency_rate': CURRENCY_RATES[currency_code],
        'currency_symbol': CURRENCY_SYMBOLS[currency_code],
        'currency_rates': CURRENCY_RATES,
    }


@app.route('/set-currency', methods=['GET', 'POST'])
def set_currency():
    code = (request.values.get('currency') or 'USD').upper()
    if code in CURRENCY_RATES:
        session['currency'] = code
    return redirect(request.referrer or url_for('index'))


# =====================================================================
# ROUTES — STATIC PAGES
# =====================================================================

@app.route('/')
def index():
    featured = Property.query.filter_by(is_featured=True).order_by(Property.rating.desc()).limit(6).all()
    trending_cities = City.query.order_by(City.average_rating.desc()).limit(8).all()
    genius_deals = Property.query.filter_by(is_genius_deal=True).order_by(Property.discount_percent.desc()).limit(4).all()
    all_cities = City.query.all()
    dest_categories = DestCategory.query.all()
    property_types = PropertyType.query.all()
    return render_template(
        'index.html',
        featured=featured,
        trending_cities=trending_cities,
        genius_deals=genius_deals,
        all_cities=all_cities,
        dest_categories=dest_categories,
        property_types=property_types,
    )


@app.route('/stays')
def stays():
    page = request.args.get('page', 1, type=int)
    per_page = 18
    query = Property.query
    # Filters
    city_slug = request.args.get('city')
    prop_type = request.args.get('type')
    min_stars = request.args.get('stars', type=int)
    max_price = request.args.get('max_price', type=float)
    if city_slug:
        city = City.query.filter_by(slug=city_slug).first()
        if city:
            query = query.filter_by(city_id=city.id)
    if prop_type:
        query = query.filter(Property.property_type.ilike(f'%{prop_type}%'))
    if min_stars:
        query = query.filter(Property.stars >= min_stars)
    if max_price:
        query = query.filter(Property.price_per_night <= max_price)
    sort = request.args.get('sort', 'rating')
    if sort == 'price_low':
        query = query.order_by(Property.price_per_night.asc())
    elif sort == 'price_high':
        query = query.order_by(Property.price_per_night.desc())
    elif sort == 'stars':
        query = query.order_by(Property.stars.desc())
    else:
        query = query.order_by(Property.rating.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    all_cities = City.query.all()
    return render_template('stays.html', pagination=pagination, properties=pagination.items,
                           all_cities=all_cities, selected_city=city_slug)


@app.route('/flights')
def flights():
    cities = City.query.all()
    return render_template('flights.html', cities=cities)


@app.route('/car-rentals')
def car_rentals():
    cities = City.query.all()
    return render_template('car_rentals.html', cities=cities)


@app.route('/attractions')
def attractions():
    cities = City.query.all()
    return render_template('attractions.html', cities=cities)


@app.route('/airport-taxis')
def airport_taxis():
    return render_template('airport_taxis.html')


@app.route('/city/<slug>')
def city_page(slug):
    city = City.query.filter_by(slug=slug).first_or_404()
    properties = Property.query.filter_by(city_id=city.id).order_by(Property.rating.desc()).limit(12).all()
    all_cities = City.query.filter(City.id != city.id).limit(6).all()
    return render_template('city.html', city=city, properties=properties, other_cities=all_cities)


@app.route('/destinations')
def destinations():
    cities = City.query.order_by(City.properties_count.desc()).all()
    return render_template('destinations.html', cities=cities)


@app.route('/category/<slug>')
def category_page(slug):
    cat = DestCategory.query.filter_by(slug=slug).first_or_404()
    properties = Property.query.filter_by(dest_category=slug).order_by(Property.rating.desc()).limit(24).all()
    return render_template('category.html', category=cat, properties=properties)


@app.route('/property-type/<slug>')
def property_type_page(slug):
    pt = PropertyType.query.filter_by(slug=slug).first_or_404()
    # Match by property_type field (match name's singular word)
    # e.g. slug='hotels' → name='Hotels' → match 'Hotel'
    singular = pt.name.rstrip('s')
    properties = Property.query.filter(Property.property_type.ilike(f'%{singular}%')).order_by(Property.rating.desc()).limit(24).all()
    return render_template('property_type.html', type=pt, properties=properties)


@app.route('/property/<slug>')
def property_detail(slug):
    prop = Property.query.filter_by(slug=slug).first_or_404()
    reviews = Review.query.filter_by(property_id=prop.id).order_by(Review.created_at.desc()).limit(10).all()
    similar = Property.query.filter(
        Property.city_id == prop.city_id,
        Property.id != prop.id
    ).order_by(Property.rating.desc()).limit(4).all()
    # Rating breakdowns
    avg_rating = db.session.query(func.avg(Review.rating)).filter_by(property_id=prop.id).scalar()
    if not avg_rating:
        avg_rating = prop.rating
    # Default check-in/out dates — honour ?checkin=&checkout= query so the
    # dates chosen on search/index propagate into the detail & reserve forms.
    tomorrow = date.today() + timedelta(days=1)
    day_after = date.today() + timedelta(days=3)
    default_checkin = tomorrow.isoformat()
    default_checkout = day_after.isoformat()
    q_ci = (request.args.get('checkin') or '').strip()
    q_co = (request.args.get('checkout') or '').strip()
    try:
        if q_ci:
            datetime.strptime(q_ci, '%Y-%m-%d')
            default_checkin = q_ci
    except ValueError:
        pass
    try:
        if q_co:
            datetime.strptime(q_co, '%Y-%m-%d')
            default_checkout = q_co
    except ValueError:
        pass
    is_saved = False
    if current_user.is_authenticated:
        is_saved = SavedProperty.query.filter_by(
            user_id=current_user.id, property_id=prop.id
        ).first() is not None
    review_scores = prop.get_review_scores()
    review_scores_high = {k: v for k, v in review_scores.items() if v >= 9.0}
    review_scores_low = {k: v for k, v in review_scores.items() if v < 9.0}
    return render_template(
        'property_detail.html',
        property=prop,
        reviews=reviews,
        similar=similar,
        avg_rating=round(avg_rating, 1),
        default_checkin=default_checkin,
        default_checkout=default_checkout,
        is_saved=is_saved,
        review_scores=review_scores,
        review_scores_high=review_scores_high,
        review_scores_low=review_scores_low,
    )


def _bool_param(name):
    v = request.args.get(name)
    if v is None or v == '':
        return None
    return str(v).lower() in ('1', 'true', 'yes', 'on')


# ---------------------------------------------------------------------------
# Geographic helpers — used for "X.X miles from <landmark>" on search cards
# ---------------------------------------------------------------------------

import math as _math

# Cities are considered "beach-relevant" — meaning the search-results sort
# dropdown surfaces a "Distance From Beach" option, and per-card beach-distance
# lines are drawn — only when the city's seeded nearest beach is within this
# many miles of the city centroid. Real booking.com hides the option entirely
# for inland searches; we mirror that behaviour. Tunable.
BEACH_RELEVANCE_THRESHOLD_MILES = 10.0


def haversine_miles(lat1, lng1, lat2, lng2):
    """Great-circle distance in miles between two (lat, lng) points."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    R_MILES = 3958.7613
    phi1 = _math.radians(lat1)
    phi2 = _math.radians(lat2)
    dphi = _math.radians(lat2 - lat1)
    dlmb = _math.radians(lng2 - lng1)
    a = _math.sin(dphi / 2) ** 2 + _math.cos(phi1) * _math.cos(phi2) * _math.sin(dlmb / 2) ** 2
    c = 2 * _math.atan2(_math.sqrt(a), _math.sqrt(1 - a))
    return R_MILES * c


def resolve_query_geopoint(query_text):
    """Best-effort resolve a free-form search string to a reference point.

    Returns a dict {lat, lng, name, subway_access, kind} or None if nothing
    matches. Order of preference:
      1. Exact city match (case-insensitive on display, key, or slug, plus
         a few common aliases like "nyc"). Whole-city queries return kind
         'city' so the caller can suppress the per-card "X miles from ..."
         line — that line is only meaningful for landmark/POI searches.
      2. Exact landmark name / alias match (case-insensitive).
      3. Substring landmark match — only when the query is at least 6
         characters AND is NOT itself a known city name. Without this guard,
         "singapore" would substring-match "National University of
         Singapore", which is the bug we are guarding against.
      4. None — caller suppresses the miles line.
    """
    if not query_text:
        return None
    q = query_text.strip()
    if not q:
        return None
    q_lower = q.lower()

    # ---- 1) Exact city match ------------------------------------------------
    # Build city set keyed by (display lower, key lower, slug lower) plus a
    # tiny alias dict for very common shorthands.
    CITY_ALIASES = {
        'nyc': 'new york',
        'ny': 'new york',
        'new york city': 'new york',
        'sg': 'singapore',
        'la': 'los angeles',
        'hk': 'hong kong',
        'hong-kong': 'hong kong',
    }
    alias_target = CITY_ALIASES.get(q_lower)
    city_query = q_lower if alias_target is None else alias_target

    city = City.query.filter(
        or_(func.lower(City.display) == city_query,
            func.lower(City.key) == city_query,
            func.lower(City.slug) == city_query)
    ).first()
    if city and city.lat is not None and city.lng is not None:
        return {'lat': city.lat, 'lng': city.lng, 'name': city.display,
                'subway_access': False, 'kind': 'city'}

    # Pre-compute the lower-cased set of known city names so the substring
    # guard below can cheaply reject city-name queries.
    all_cities = City.query.all()
    city_name_set = set()
    for c in all_cities:
        if c.display:
            city_name_set.add(c.display.strip().lower())
        if c.key:
            city_name_set.add(c.key.strip().lower())
        if c.slug:
            city_name_set.add(c.slug.strip().lower().replace('-', ' '))
            city_name_set.add(c.slug.strip().lower())
    # Alias targets (e.g. "new york") count as city names too.
    city_name_set.update(v.lower() for v in CITY_ALIASES.values())
    city_name_set.update(k.lower() for k in CITY_ALIASES.keys())

    # ---- 2) Exact landmark / alias match ------------------------------------
    lm = Landmark.query.filter(func.lower(Landmark.name) == q_lower).first()
    if lm:
        return {'lat': lm.lat, 'lng': lm.lng, 'name': lm.name,
                'subway_access': bool(lm.subway_access), 'kind': lm.kind}
    # exact alias match
    all_lms = Landmark.query.all()
    for cand in all_lms:
        for alias in cand.aliases():
            if alias and alias.strip().lower() == q_lower:
                return {'lat': cand.lat, 'lng': cand.lng, 'name': cand.name,
                        'subway_access': bool(cand.subway_access),
                        'kind': cand.kind}

    # ---- 3) Substring landmark match (guarded) ------------------------------
    # Skip entirely if the query is itself a city name OR is too short.
    if len(q_lower) >= 6 and q_lower not in city_name_set:
        candidates = []
        for cand in all_lms:
            name_lc = cand.name.lower()
            if q_lower in name_lc or name_lc in q_lower:
                candidates.append(cand)
                continue
            for alias in cand.aliases():
                a_lc = (alias or '').strip().lower()
                if a_lc and (q_lower in a_lc or a_lc in q_lower):
                    candidates.append(cand)
                    break
        if candidates:
            # prefer the longest landmark name (most specific)
            best = max(candidates, key=lambda x: len(x.name))
            return {'lat': best.lat, 'lng': best.lng, 'name': best.name,
                    'subway_access': bool(best.subway_access),
                    'kind': best.kind}

    # ---- 4) Nothing matched -------------------------------------------------
    return None


def _resolve_search_city(query_text, city_id=None, city_slug=None):
    """Best-effort resolve a /search request to an owning City row.

    Used to determine beach-relevance for the search context.

    Resolution order:
      1. Explicit city_id / city_slug arg
      2. Exact city match on the free-text query
      3. Landmark match → its owning city (foreign key) or, if missing,
         the geographically nearest city
      4. None
    """
    # 1) explicit
    if city_id:
        c = City.query.get(city_id)
        if c:
            return c
    if city_slug:
        c = City.query.filter_by(slug=city_slug).first()
        if c:
            return c

    if not query_text:
        return None
    q = query_text.strip()
    if not q:
        return None
    q_lower = q.lower()

    CITY_ALIASES = {
        'nyc': 'new york', 'ny': 'new york', 'new york city': 'new york',
        'sg': 'singapore', 'la': 'los angeles', 'hk': 'hong kong',
        'hong-kong': 'hong kong',
    }
    alias_target = CITY_ALIASES.get(q_lower)
    city_query = q_lower if alias_target is None else alias_target

    # 2) exact city match
    c = City.query.filter(
        or_(func.lower(City.display) == city_query,
            func.lower(City.key) == city_query,
            func.lower(City.slug) == city_query)
    ).first()
    if c:
        return c

    # 3) landmark → owning city
    lm = Landmark.query.filter(func.lower(Landmark.name) == q_lower).first()
    if lm is None:
        # alias / substring fallback
        all_lms = Landmark.query.all()
        for cand in all_lms:
            for alias in cand.aliases():
                if alias and alias.strip().lower() == q_lower:
                    lm = cand; break
            if lm:
                break
        if lm is None and len(q_lower) >= 6:
            cands = []
            for cand in all_lms:
                name_lc = cand.name.lower()
                if q_lower in name_lc or name_lc in q_lower:
                    cands.append(cand)
                    continue
                for alias in cand.aliases():
                    a_lc = (alias or '').strip().lower()
                    if a_lc and (q_lower in a_lc or a_lc in q_lower):
                        cands.append(cand); break
            if cands:
                lm = max(cands, key=lambda x: len(x.name))

    if lm is not None:
        if lm.city_id:
            c = City.query.get(lm.city_id)
            if c:
                return c
        # fallback: nearest city by haversine
        all_cities = City.query.all()
        best = None
        best_d = None
        for c in all_cities:
            if c.lat is None or c.lng is None:
                continue
            d = haversine_miles(lm.lat, lm.lng, c.lat, c.lng)
            if d is None:
                continue
            if best_d is None or d < best_d:
                best_d = d; best = c
        return best

    return None


def _is_beach_relevant_city(city):
    """Return True iff city has a defined nearest beach within the threshold."""
    if city is None:
        return False
    if (city.lat is None or city.lng is None
            or city.nearest_beach_lat is None
            or city.nearest_beach_lng is None):
        return False
    d = haversine_miles(city.lat, city.lng,
                        city.nearest_beach_lat, city.nearest_beach_lng)
    if d is None:
        return False
    return d <= BEACH_RELEVANCE_THRESHOLD_MILES


@app.route('/search')
@app.route('/searchresults.html')
def search():
    q = (request.args.get('q') or request.args.get('ss') or '').strip()
    dest = (request.args.get('dest') or request.args.get('destination') or '').strip()
    near = (request.args.get('near') or '').strip()
    city_id = request.args.get('city_id', type=int)
    city_slug = (request.args.get('city') or '').strip()
    country = (request.args.get('country') or '').strip()
    checkin = request.args.get('checkin', '')
    checkout = request.args.get('checkout', '')
    adults = request.args.get('adults', 2, type=int)
    children = request.args.get('children', 0, type=int)
    rooms = request.args.get('rooms', 1, type=int)

    min_rating = request.args.get('min_rating', type=float)
    min_stars = request.args.get('min_stars', type=int)
    max_price = request.args.get('max_price', type=float)
    min_price = request.args.get('min_price', type=float)
    prop_type = (request.args.get('property_type') or request.args.get('type') or '').strip()
    sort = (request.args.get('sort') or '').strip()

    # ---- Empty-destination guard ----
    # Real booking.com requires the user to enter (or pick) a destination — an
    # empty form submission yields no results. We mirror that here: if the
    # user did not provide ANY destination-resolution param (q / dest / near /
    # country / city_id / city_slug), render the search page in an explicit
    # empty-state with zero results, instead of returning the entire 360-row
    # catalog.
    if not (q or dest or near or country or city_id or city_slug):
        return render_template('search.html',
                               query='', results=[],
                               all_cities=City.query.all(),
                               checkin=checkin, checkout=checkout,
                               adults=adults, rooms=rooms,
                               brand_counts=[],
                               miles_label_name=None,
                               miles_label_subway=False,
                               show_beach_sort=False,
                               sort='',
                               empty_destination=True)

    # ----- Beach-relevance gating -----
    # Real booking.com only surfaces "Distance From Beach" as a sort option
    # when the search context is genuinely coastal — i.e. the search resolves
    # to a city (or to a landmark whose owning city) whose seeded nearest
    # beach is within BEACH_RELEVANCE_THRESHOLD_MILES of the city centroid.
    # For inland searches (Paris, Vienna, Mexico City, Ohio …) the option is
    # hidden and the per-card beach-distance line is suppressed. If a user
    # forces ?sort=distance_beach for an inland search we silently fall back
    # to the default sort.
    _resolved_city_for_beach = _resolve_search_city(
        q or dest or near or country, city_id=city_id, city_slug=city_slug)
    show_beach_sort = _is_beach_relevant_city(_resolved_city_for_beach)
    if sort == 'distance_beach' and not show_beach_sort:
        sort = ''  # graceful fallback to default sort

    # Boolean amenity filters
    free_cancellation = _bool_param('free_cancellation')
    breakfast = _bool_param('breakfast')
    wifi = _bool_param('wifi')
    pool = _bool_param('pool')
    parking = _bool_param('parking')
    gym = _bool_param('gym') or _bool_param('fitness')
    spa = _bool_param('spa')
    airport_shuttle = _bool_param('airport_shuttle')
    pet_friendly = _bool_param('pet_friendly')
    air_conditioning = _bool_param('air_conditioning')
    bicycle = _bool_param('bicycle')
    deals = _bool_param('deals')
    brand = (request.args.get('brand') or '').strip()

    query = Property.query.join(City, Property.city_id == City.id)

    # --- Destination / city / country / keyword matching ---
    term = dest or q
    # Track whether the term resolved to a known city / landmark / alias. When
    # it does, the property pool is filtered to that city — a hotel-name
    # substring match (Property.name LIKE %term%) must NEVER override a
    # successful city/alias/landmark resolution. Otherwise "nus" → resolves to
    # National University of Singapore but pulls in "The Mulia Nusa Dua" (Bali)
    # and "Venustiano Carranza" (Mexico City) just because their names contain
    # the substring "nus". Free-text terms like "ocean view" still fall through
    # to the substring matcher below.
    resolved_geo_term = False
    if city_id:
        query = query.filter(Property.city_id == city_id)
    elif city_slug:
        city_obj = City.query.filter_by(slug=city_slug).first()
        if city_obj:
            query = query.filter(Property.city_id == city_obj.id)
    elif term:
        # Try to resolve the term to a known city / landmark / alias first.
        # Only fall back to free-text substring search if the resolver returns
        # nothing.
        resolved_city = _resolve_search_city(term)
        if resolved_city is not None:
            query = query.filter(Property.city_id == resolved_city.id)
            resolved_geo_term = True
        else:
            t = f'%{term}%'
            query = query.filter(
                or_(
                    City.display.ilike(t),
                    City.country.ilike(t),
                    City.description.ilike(t),
                    Property.name.ilike(t),
                    Property.neighborhood.ilike(t),
                    Property.description.ilike(t),
                    Property.landmark_tags.ilike(t),
                )
            )

    if country:
        query = query.filter(City.country.ilike(f'%{country}%'))

    if near:
        n = f'%{near}%'
        query = query.filter(
            or_(
                Property.landmark_tags.ilike(n),
                Property.description.ilike(n),
                Property.neighborhood.ilike(n),
                Property.name.ilike(n),
            )
        )

    if prop_type:
        query = query.filter(Property.property_type.ilike(f'%{prop_type}%'))
    if min_rating is not None:
        query = query.filter(Property.rating >= min_rating)
    if min_stars is not None:
        query = query.filter(Property.stars >= min_stars)
    if max_price is not None:
        query = query.filter(Property.price_per_night <= max_price)
    if min_price is not None:
        query = query.filter(Property.price_per_night >= min_price)

    # guests: 2 adults + 2 rooms etc.
    guests = adults + children
    if guests > 2:
        query = query.filter(Property.max_guests >= guests)

    if free_cancellation:
        query = query.filter(Property.free_cancellation.is_(True))
    if breakfast:
        query = query.filter(Property.breakfast_included.is_(True))
    if wifi:
        query = query.filter(Property.has_wifi.is_(True))
    if pool:
        query = query.filter(Property.has_pool.is_(True))
    if parking:
        query = query.filter(Property.has_parking.is_(True))
    if gym:
        query = query.filter(Property.has_gym.is_(True))
    if spa:
        query = query.filter(Property.has_spa.is_(True))
    if airport_shuttle:
        query = query.filter(Property.has_airport_shuttle.is_(True))
    if pet_friendly:
        query = query.filter(Property.has_pet_friendly.is_(True))
    if air_conditioning:
        query = query.filter(Property.has_air_conditioning.is_(True))
    if bicycle:
        query = query.filter(Property.has_bicycle_rental.is_(True))
    if deals:
        query = query.filter(Property.discount_percent > 0)
    if brand:
        query = query.filter(Property.brand == brand)

    # --- Sorting ---
    if sort == 'price_asc' or sort == 'price_low':
        # Sort by effective (discounted) price
        query = query.order_by(
            (Property.price_per_night * (100 - Property.discount_percent) / 100).asc()
        )
    elif sort == 'price_desc' or sort == 'price_high':
        query = query.order_by(Property.price_per_night.desc())
    elif sort in ('rating', 'review_score', 'review_score_desc', 'best_reviewed'):
        query = query.order_by(Property.rating.desc(), Property.review_count.desc())
    elif sort == 'stars':
        query = query.order_by(Property.stars.desc(), Property.rating.desc())
    elif sort == 'distance':
        query = query.order_by(Property.distance_from_center.asc())
    elif sort == 'distance_beach':
        # Defer ordering to Python — beach point is per-city and we want to
        # compute haversine miles from each property to its city's nearest
        # beach. We still apply the upper limit AFTER sorting in Python.
        query = query.order_by(Property.rating.desc(), Property.review_count.desc())
    else:
        # default: relevance-ish → rating desc with review weight
        query = query.order_by(Property.rating.desc(), Property.review_count.desc())

    if sort == 'distance_beach':
        # Pull a wider candidate pool then sort by distance-from-beach in Python.
        candidates = query.limit(200).all()
        for prop in candidates:
            city = prop.city
            if (city is not None
                    and prop.lat is not None and prop.lng is not None
                    and city.nearest_beach_lat is not None
                    and city.nearest_beach_lng is not None):
                d = haversine_miles(prop.lat, prop.lng,
                                    city.nearest_beach_lat,
                                    city.nearest_beach_lng)
                prop.miles_from_beach = round(max(0.0, d), 1) if d is not None else None
                prop.beach_name = city.nearest_beach_name
            else:
                prop.miles_from_beach = None
                prop.beach_name = None
        # Sort: defined distances first (ascending), then undefined at end.
        candidates.sort(key=lambda p: (p.miles_from_beach is None,
                                       p.miles_from_beach if p.miles_from_beach is not None else 0.0))
        results = candidates[:60]
    else:
        results = query.limit(60).all()

    # Default (empty query, no filters) → show a rating-sorted snapshot
    if not (term or city_id or city_slug or near or country) and not results:
        results = Property.query.order_by(Property.rating.desc()).limit(20).all()

    all_cities = City.query.all()

    # Brand counts (group-by on the un-filtered-by-brand result set so
    # "currently displayed brands" match what the user sees).
    # We compute counts by re-running the pre-brand query.
    brand_count_query = Property.query.join(City, Property.city_id == City.id)
    # re-apply all non-brand filters by using same `term` / city filters
    if city_id:
        brand_count_query = brand_count_query.filter(Property.city_id == city_id)
    elif city_slug:
        city_obj2 = City.query.filter_by(slug=city_slug).first()
        if city_obj2:
            brand_count_query = brand_count_query.filter(Property.city_id == city_obj2.id)
    elif term:
        # Mirror the main-query rule: city/alias/landmark resolution wins
        # over substring match.
        resolved_city2 = _resolve_search_city(term)
        if resolved_city2 is not None:
            brand_count_query = brand_count_query.filter(Property.city_id == resolved_city2.id)
        else:
            t2 = f'%{term}%'
            brand_count_query = brand_count_query.filter(
                or_(
                    City.display.ilike(t2),
                    City.country.ilike(t2),
                    Property.name.ilike(t2),
                    Property.neighborhood.ilike(t2),
                    Property.description.ilike(t2),
                    Property.landmark_tags.ilike(t2),
                )
            )
    if country:
        brand_count_query = brand_count_query.filter(City.country.ilike(f'%{country}%'))

    brand_counts_rows = (
        brand_count_query
        .with_entities(Property.brand, func.count(Property.id))
        .group_by(Property.brand)
        .order_by(func.count(Property.id).desc())
        .all()
    )
    brand_counts = [(b, c) for (b, c) in brand_counts_rows if b]

    # ----- Compute "X.X miles from <landmark>" per result card -----
    # Resolve user's free-form query string to a reference geopoint.
    # Real booking.com only shows the per-card "X miles from <landmark>"
    # line for *landmark / POI* searches. For whole-city / region queries
    # ("Singapore", "Tokyo") it omits that line entirely — saying a hotel
    # in Singapore is "3 miles from Singapore" is not informative.
    miles_query_text = q or dest or near or city_slug or country
    geo = resolve_query_geopoint(miles_query_text)

    # Only show the miles line when we resolved to an actual landmark/POI.
    show_miles_line = bool(geo) and geo.get('kind') != 'city'
    miles_label_name = geo['name'] if show_miles_line else None
    miles_label_subway = bool(geo['subway_access']) if show_miles_line else False
    if show_miles_line:
        for prop in results:
            if prop.lat is not None and prop.lng is not None:
                d = haversine_miles(prop.lat, prop.lng, geo['lat'], geo['lng'])
                if d is not None:
                    # Round to 1 decimal place; clamp tiny negative-to-zero
                    prop.miles_from_query = round(max(0.0, d), 1)
                else:
                    prop.miles_from_query = None
            else:
                prop.miles_from_query = None
        # When the user's query resolved to a landmark/POI (not a whole city)
        # and no explicit sort was requested, sort the result cards by
        # ascending distance from that landmark — matches real booking.com,
        # which surfaces "closest to <landmark>" first for landmark searches.
        if not sort:
            results.sort(key=lambda p: (
                p.miles_from_query is None,
                p.miles_from_query if p.miles_from_query is not None else 0.0))
    else:
        for prop in results:
            prop.miles_from_query = None

    # When sort != distance_beach, ensure miles_from_beach attr is defined
    # (so templates can safely test it without AttributeError).
    if sort != 'distance_beach':
        for prop in results:
            if not hasattr(prop, 'miles_from_beach'):
                prop.miles_from_beach = None
            if not hasattr(prop, 'beach_name'):
                prop.beach_name = None

    return render_template('search.html',
                           query=q or dest or near, results=results,
                           all_cities=all_cities,
                           checkin=checkin, checkout=checkout,
                           adults=adults, rooms=rooms,
                           brand_counts=brand_counts,
                           miles_label_name=miles_label_name,
                           miles_label_subway=miles_label_subway,
                           show_beach_sort=show_beach_sort,
                           sort=sort)


# =====================================================================
# AUTH ROUTES
# =====================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=True)
            flash('Welcome back!', 'success')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('index'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash('That email is already registered.', 'danger')
        else:
            hashed = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            user = User(
                email=form.email.data.lower(),
                password_hash=hashed,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
            )
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            flash('Your account has been created. Welcome to Booking!', 'success')
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('index'))


# =====================================================================
# ACCOUNT ROUTES
# =====================================================================

@app.route('/account')
@login_required
def account():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).limit(5).all()
    saved = SavedProperty.query.filter_by(user_id=current_user.id).order_by(SavedProperty.saved_at.desc()).limit(4).all()
    reviews = Review.query.filter_by(user_id=current_user.id).order_by(Review.created_at.desc()).limit(3).all()
    total_bookings = Booking.query.filter_by(user_id=current_user.id).count()
    return render_template('account.html', bookings=bookings, saved=saved, reviews=reviews, total_bookings=total_bookings)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        form.populate_obj(current_user)
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('account'))
    return render_template('account_edit.html', form=form)


@app.route('/account/password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = PasswordChangeForm()
    if form.validate_on_submit():
        if not bcrypt.check_password_hash(current_user.password_hash, form.current_password.data):
            flash('Current password is incorrect.', 'danger')
        else:
            current_user.password_hash = bcrypt.generate_password_hash(form.new_password.data).decode('utf-8')
            db.session.commit()
            flash('Password changed.', 'success')
            return redirect(url_for('account'))
    return render_template('change_password.html', form=form)


@app.route('/account/delete', methods=['POST'])
@login_required
def account_delete():
    uid = current_user.id
    logout_user()
    user = db.session.get(User, uid)
    db.session.delete(user)
    db.session.commit()
    flash('Account deleted.', 'info')
    return redirect(url_for('index'))


@app.route('/account/bookings')
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template('bookings.html', bookings=bookings)


# =====================================================================
# CART / BOOKING ROUTES
# =====================================================================

@app.route('/bag')
@login_required
def bag():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    subtotal = sum(i.total for i in items)
    taxes = round(subtotal * 0.12, 2)
    total = round(subtotal + taxes, 2)
    return render_template('bag.html', items=items, subtotal=subtotal, taxes=taxes, total=total)


@app.route('/api/cart/add', methods=['POST'])
@csrf.exempt
@login_required
def api_cart_add():
    data = request.get_json() or {}
    pid = data.get('property_id')
    prop = db.session.get(Property, pid) if pid else None
    if not prop:
        return jsonify({'success': False, 'message': 'Property not found'}), 404
    check_in = data.get('check_in') or (date.today() + timedelta(days=1)).isoformat()
    check_out = data.get('check_out') or (date.today() + timedelta(days=3)).isoformat()
    try:
        ci = datetime.strptime(check_in, '%Y-%m-%d').date()
        co = datetime.strptime(check_out, '%Y-%m-%d').date()
    except ValueError:
        ci = date.today() + timedelta(days=1)
        co = date.today() + timedelta(days=3)
    if co <= ci:
        co = ci + timedelta(days=1)
    item = CartItem(
        user_id=current_user.id,
        property_id=prop.id,
        check_in=ci,
        check_out=co,
        adults=data.get('adults', 2),
        children=data.get('children', 0),
        rooms=data.get('rooms', 1),
        room_type=data.get('room_type', 'Standard Double Room'),
    )
    db.session.add(item)
    db.session.commit()
    count = CartItem.query.filter_by(user_id=current_user.id).count()
    return jsonify({
        'success': True,
        'cart_count': count,
        'message': f'{prop.name} added to your bag.'
    })


@app.route('/api/cart/update', methods=['POST'])
@csrf.exempt
@login_required
def api_cart_update():
    data = request.get_json() or {}
    item = db.session.get(CartItem, data.get('item_id'))
    if not item or item.user_id != current_user.id:
        return jsonify({'success': False}), 404
    if 'rooms' in data:
        item.rooms = max(1, int(data['rooms']))
    if 'adults' in data:
        item.adults = max(1, int(data['adults']))
    if 'check_in' in data:
        try:
            item.check_in = datetime.strptime(data['check_in'], '%Y-%m-%d').date()
        except Exception:
            pass
    if 'check_out' in data:
        try:
            item.check_out = datetime.strptime(data['check_out'], '%Y-%m-%d').date()
        except Exception:
            pass
    db.session.commit()
    return jsonify({'success': True, 'total': item.total, 'nights': item.nights})


@app.route('/api/cart/remove', methods=['POST'])
@csrf.exempt
@login_required
def api_cart_remove():
    data = request.get_json() or {}
    item = db.session.get(CartItem, data.get('item_id'))
    if item and item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
    count = CartItem.query.filter_by(user_id=current_user.id).count()
    return jsonify({'success': True, 'cart_count': count})


# =====================================================================
# FORM-BASED CART / SAVED ROUTES (non-AJAX fallbacks for agents)
# =====================================================================

@app.route('/cart/add/<int:property_id>', methods=['POST'])
@login_required
def cart_add_form(property_id):
    """Form-POST alternative to /api/cart/add (agent-friendly)."""
    prop = db.session.get(Property, property_id)
    if not prop:
        abort(404)
    # Dates preferentially come from the POST form, but also accept query-
    # string fallbacks (e.g. /cart/add/7?checkin=2024-01-22&checkout=2024-01-25)
    # so agents that post without a date field still propagate search dates.
    check_in_str = (request.form.get('check_in')
                    or request.form.get('checkin')
                    or request.values.get('checkin')
                    or request.values.get('check_in') or '')
    check_out_str = (request.form.get('check_out')
                     or request.form.get('checkout')
                     or request.values.get('checkout')
                     or request.values.get('check_out') or '')
    try:
        ci = datetime.strptime(check_in_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        ci = date.today() + timedelta(days=1)
    try:
        co = datetime.strptime(check_out_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        co = date.today() + timedelta(days=3)
    if co <= ci:
        co = ci + timedelta(days=2)
    adults = int(request.form.get('adults', 2))
    children = int(request.form.get('children', 0))
    rooms = int(request.form.get('rooms', 1))
    room_type = request.form.get('room_type', 'Standard Double Room')
    item = CartItem(
        user_id=current_user.id,
        property_id=prop.id,
        check_in=ci,
        check_out=co,
        adults=adults,
        children=children,
        rooms=rooms,
        room_type=room_type,
    )
    db.session.add(item)
    db.session.commit()
    flash(f'{prop.name} added to your bag.', 'success')
    redirect_to = request.form.get('next') or url_for('bag')
    return redirect(redirect_to)


@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def cart_remove_form(item_id):
    """Form-POST remove from cart."""
    item = db.session.get(CartItem, item_id)
    if item and item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Item removed from your bag.', 'info')
    return redirect(url_for('bag'))


@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def cart_update_form(item_id):
    """Form-POST update cart item dates/guests."""
    item = db.session.get(CartItem, item_id)
    if not item or item.user_id != current_user.id:
        abort(404)
    check_in_str = request.form.get('check_in', '')
    check_out_str = request.form.get('check_out', '')
    try:
        item.check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        pass
    try:
        item.check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        pass
    if item.check_out <= item.check_in:
        item.check_out = item.check_in + timedelta(days=1)
    if request.form.get('rooms'):
        item.rooms = max(1, int(request.form.get('rooms', 1)))
    if request.form.get('adults'):
        item.adults = max(1, int(request.form.get('adults', 2)))
    if request.form.get('room_type'):
        item.room_type = request.form.get('room_type')
    db.session.commit()
    flash('Bag updated.', 'success')
    return redirect(url_for('bag'))


@app.route('/saved/add/<int:property_id>', methods=['POST'])
@login_required
def saved_add_form(property_id):
    """Form-POST add to saved (agent-friendly)."""
    prop = db.session.get(Property, property_id)
    if not prop:
        abort(404)
    existing = SavedProperty.query.filter_by(
        user_id=current_user.id, property_id=property_id
    ).first()
    if not existing:
        db.session.add(SavedProperty(user_id=current_user.id, property_id=property_id))
        db.session.commit()
        flash(f'{prop.name} saved to your wishlist.', 'success')
    else:
        flash(f'{prop.name} is already in your saved list.', 'info')
    redirect_to = request.form.get('next') or url_for('saved')
    return redirect(redirect_to)


@app.route('/saved/toggle/<int:property_id>', methods=['POST'])
@login_required
def saved_toggle_form(property_id):
    """Form-POST toggle saved (agent-friendly)."""
    existing = SavedProperty.query.filter_by(
        user_id=current_user.id, property_id=property_id
    ).first()
    prop = db.session.get(Property, property_id)
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Removed from saved.', 'info')
    else:
        if prop:
            db.session.add(SavedProperty(user_id=current_user.id, property_id=property_id))
            db.session.commit()
            flash(f'{prop.name} saved.', 'success')
    return redirect(request.form.get('next') or url_for('saved'))


# =====================================================================
# PAYMENT METHODS ROUTES
# =====================================================================

@app.route('/account/payments')
@login_required
def payment_methods():
    methods = PaymentMethod.query.filter_by(user_id=current_user.id).order_by(
        PaymentMethod.is_default.desc(), PaymentMethod.created_at.asc()
    ).all()
    return render_template('payment_methods.html', methods=methods)


@app.route('/account/payments/add', methods=['GET', 'POST'])
@login_required
def payment_method_add():
    if request.method == 'POST':
        card_number = request.form.get('card_number', '').replace(' ', '')
        card_type = request.form.get('card_type', 'Visa')
        cardholder_name = request.form.get('cardholder_name', '')
        card_exp = request.form.get('card_exp', '12/28')
        try:
            exp_parts = card_exp.split('/')
            exp_month = int(exp_parts[0])
            exp_year = int('20' + exp_parts[1]) if len(exp_parts[1]) == 2 else int(exp_parts[1])
        except Exception:
            exp_month, exp_year = 12, 2028
        last4 = card_number[-4:] if len(card_number) >= 4 else '0000'
        is_default = not PaymentMethod.query.filter_by(user_id=current_user.id).first()
        pm = PaymentMethod(
            user_id=current_user.id,
            card_type=card_type,
            last4=last4,
            exp_month=exp_month,
            exp_year=exp_year,
            cardholder_name=cardholder_name,
            is_default=is_default,
        )
        db.session.add(pm)
        db.session.commit()
        flash('Payment method added.', 'success')
        return redirect(url_for('payment_methods'))
    return render_template('payment_method_add.html')


@app.route('/account/payments/<int:pm_id>/delete', methods=['POST'])
@login_required
def payment_method_delete(pm_id):
    pm = db.session.get(PaymentMethod, pm_id)
    if pm and pm.user_id == current_user.id:
        db.session.delete(pm)
        db.session.commit()
        flash('Payment method removed.', 'info')
    return redirect(url_for('payment_methods'))


@app.route('/account/payments/<int:pm_id>/set-default', methods=['POST'])
@login_required
def payment_method_set_default(pm_id):
    pm = db.session.get(PaymentMethod, pm_id)
    if pm and pm.user_id == current_user.id:
        PaymentMethod.query.filter_by(user_id=current_user.id).update({'is_default': False})
        pm.is_default = True
        db.session.commit()
        flash('Default payment method updated.', 'success')
    return redirect(url_for('payment_methods'))


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash('Your bag is empty.', 'warning')
        return redirect(url_for('stays'))
    subtotal = sum(i.total for i in items)
    taxes = round(subtotal * 0.12, 2)
    total = round(subtotal + taxes, 2)

    saved_payments = PaymentMethod.query.filter_by(user_id=current_user.id).order_by(
        PaymentMethod.is_default.desc()
    ).all()

    form = CheckoutForm(
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        email=current_user.email,
        phone=current_user.phone,
        country=current_user.country,
    )

    if form.validate_on_submit():
        # Determine card last4 from saved payment or form
        saved_pm_id = form.saved_payment_id.data
        card_last4 = ''
        payment_label = 'Credit Card'
        if saved_pm_id:
            pm = db.session.get(PaymentMethod, saved_pm_id)
            if pm and pm.user_id == current_user.id:
                card_last4 = pm.last4
                payment_label = f'{pm.card_type} ending {pm.last4}'
        if not card_last4 and form.card_number.data:
            card_last4 = (form.card_number.data or '')[-4:]

        booking_number = 'BKN-' + secrets.token_hex(5).upper()
        total_nights = sum(i.nights for i in items)
        booking = Booking(
            user_id=current_user.id,
            booking_number=booking_number,
            total=total,
            nights=total_nights,
            guest_first_name=form.first_name.data,
            guest_last_name=form.last_name.data,
            guest_email=form.email.data,
            guest_phone=form.phone.data,
            guest_country=form.country.data,
            special_requests=form.special_requests.data,
            payment_method=payment_label,
            card_last4=card_last4,
        )
        db.session.add(booking)
        db.session.flush()
        for ci in items:
            bi = BookingItem(
                booking_id=booking.id,
                property_id=ci.property_id,
                check_in=ci.check_in,
                check_out=ci.check_out,
                adults=ci.adults,
                children=ci.children,
                rooms=ci.rooms,
                room_type=ci.room_type,
                price_per_night=ci.property.discounted_price,
                subtotal=ci.total,
            )
            db.session.add(bi)
            db.session.delete(ci)
        db.session.commit()
        flash('Booking confirmed! Check your email for details.', 'success')
        return redirect(url_for('booking_confirmation', booking_id=booking.id))

    return render_template('checkout.html', items=items, form=form,
                           subtotal=subtotal, taxes=taxes, total=total,
                           saved_payments=saved_payments)


@app.route('/booking/confirmation/<int:booking_id>')
@login_required
def booking_confirmation(booking_id):
    """Public-facing 'Booking confirmed' page shown after successful checkout."""
    booking = db.session.get(Booking, booking_id)
    if not booking or booking.user_id != current_user.id:
        abort(404)
    return render_template('booking_detail.html', booking=booking, is_confirmation=True)


@app.route('/booking/<int:booking_id>')
@login_required
def booking_detail(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking or booking.user_id != current_user.id:
        abort(404)
    return render_template('booking_detail.html', booking=booking, is_confirmation=False)


@app.route('/booking/<int:booking_id>/cancel', methods=['POST'])
@login_required
def booking_cancel(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking or booking.user_id != current_user.id:
        abort(404)
    if booking.status == 'confirmed':
        booking.status = 'cancelled'
        db.session.commit()
        flash('Booking cancelled.', 'info')
    return redirect(url_for('booking_detail', booking_id=booking_id))


@app.route('/booking/<int:booking_id>/rebook', methods=['POST'])
@login_required
def booking_rebook(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking or booking.user_id != current_user.id:
        abort(404)
    added = 0
    for bi in booking.items:
        new_ci = date.today() + timedelta(days=14)
        new_co = new_ci + timedelta(days=(bi.check_out - bi.check_in).days)
        item = CartItem(
            user_id=current_user.id,
            property_id=bi.property_id,
            check_in=new_ci,
            check_out=new_co,
            adults=bi.adults,
            children=bi.children,
            rooms=bi.rooms,
            room_type=bi.room_type,
        )
        db.session.add(item)
        added += 1
    db.session.commit()
    flash(f'{added} item(s) added to your bag.', 'success')
    return redirect(url_for('bag'))


# =====================================================================
# SAVED / WISHLIST ROUTES
# =====================================================================

@app.route('/saved')
@login_required
def saved():
    items = SavedProperty.query.filter_by(user_id=current_user.id).order_by(SavedProperty.saved_at.desc()).all()
    return render_template('saved.html', items=items)


@app.route('/api/saved/toggle', methods=['POST'])
@csrf.exempt
@login_required
def api_saved_toggle():
    data = request.get_json() or {}
    pid = data.get('property_id')
    existing = SavedProperty.query.filter_by(
        user_id=current_user.id, property_id=pid
    ).first()
    if existing:
        db.session.delete(existing)
        action = 'removed'
    else:
        db.session.add(SavedProperty(user_id=current_user.id, property_id=pid))
        action = 'added'
    db.session.commit()
    count = SavedProperty.query.filter_by(user_id=current_user.id).count()
    return jsonify({'success': True, 'action': action, 'saved_count': count})


@app.route('/saved/remove/<int:item_id>', methods=['POST'])
@login_required
def saved_remove(item_id):
    item = db.session.get(SavedProperty, item_id)
    if item and item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Removed from saved.', 'info')
    return redirect(url_for('saved'))


@app.route('/saved/rename-list', methods=['POST'])
@login_required
def saved_rename_list():
    """Rename a saved-property list — updates all items with that list_name."""
    old_name = (request.form.get('old_name') or '').strip()
    new_name = (request.form.get('new_name') or '').strip()
    if old_name and new_name and old_name != new_name:
        items = SavedProperty.query.filter_by(
            user_id=current_user.id, list_name=old_name
        ).all()
        if items:
            for item in items:
                item.list_name = new_name
            db.session.commit()
            flash(f'List renamed from "{old_name}" to "{new_name}".', 'success')
        else:
            flash(f'No list named "{old_name}" found.', 'error')
    else:
        flash('Please provide both old and new list names.', 'error')
    return redirect(url_for('saved'))


# =====================================================================
# REVIEWS
# =====================================================================

@app.route('/property/<slug>/review', methods=['GET', 'POST'])
@login_required
def submit_review(slug):
    prop = Property.query.filter_by(slug=slug).first_or_404()
    form = ReviewForm()
    if form.validate_on_submit():
        review = Review(
            user_id=current_user.id,
            property_id=prop.id,
            rating=float(form.rating.data),
            title=form.title.data,
            body_positive=form.body_positive.data,
            body_negative=form.body_negative.data,
            traveller_type=form.traveller_type.data,
        )
        db.session.add(review)
        # Update property rating
        reviews = Review.query.filter_by(property_id=prop.id).all()
        if reviews:
            prop.rating = round(sum(r.rating for r in reviews + [review]) / (len(reviews) + 1), 1)
            prop.review_count = len(reviews) + 1
            prop.rating_label = rating_label_for(prop.rating)
        db.session.commit()
        flash('Thanks for your review!', 'success')
        return redirect(url_for('property_detail', slug=slug))
    return render_template('review_form.html', form=form, property=prop)


@app.route('/review/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    review = db.session.get(Review, review_id)
    if review and review.user_id == current_user.id:
        prop = review.property
        db.session.delete(review)
        db.session.commit()
        # Recalculate
        reviews = Review.query.filter_by(property_id=prop.id).all()
        if reviews:
            prop.rating = round(sum(r.rating for r in reviews) / len(reviews), 1)
            prop.review_count = len(reviews)
        db.session.commit()
        flash('Review deleted.', 'info')
    return redirect(request.referrer or url_for('account'))


# =====================================================================
# API
# =====================================================================

@app.route('/api/properties/<city_slug>')
def api_properties_by_city(city_slug):
    city = City.query.filter_by(slug=city_slug).first_or_404()
    props = Property.query.filter_by(city_id=city.id).limit(20).all()
    return jsonify([
        {
            'id': p.id, 'name': p.name, 'slug': p.slug,
            'price': p.price_per_night, 'rating': p.rating,
            'stars': p.stars, 'image': p.image,
        } for p in props
    ])


@app.route('/api/cities')
def api_cities():
    cities = City.query.all()
    return jsonify([
        {'id': c.id, 'display': c.display, 'slug': c.slug, 'country': c.country}
        for c in cities
    ])


# =====================================================================
# STATIC PAGES
# =====================================================================

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/help')
def help_page():
    return render_template('help.html')


# =====================================================================
# TRAVEL ARTICLES (static Jinja data — editorial inspiration)
# =====================================================================

TRAVEL_ARTICLES = [
    {
        'slug': 'top-5-european-cities-food-lovers',
        'title': 'Top 5 European Cities for Food Lovers',
        'excerpt': 'From pasta in Rome to tapas in Barcelona — a five-city pilgrimage for devoted eaters.',
        'category': 'Food & Drink',
        'author': 'Emma Williams',
        'read_time': '7 min read',
        'image': '/static/images/gallery/paris/paris_1.jpg',
        'places': ['Paris', 'Rome', 'Lisbon', 'Barcelona', 'Vienna'],
        'body': (
            'If you measure travel in meals rather than miles, Europe is the planet\u2019s most generous stage. '
            'Begin in **Paris**, where morning queues outside Du Pain et des Id\u00e9es prove that pastry is a civic religion; '
            'lunch on a jambon-beurre from a corner boulangerie in the Marais before dinner at a bistro near the Louvre. '
            'From there, take an overnight train to **Rome**, whose trattorias in Trastevere still serve cacio e pepe on paper-lined tables.\n\n'
            'Fly south-west to **Lisbon** for pastel de nata at Manteigaria and grilled sardines along the Tejo. '
            'Next stop **Barcelona**, where the Bar del Pla near the Picasso Museum turns tapas into architecture. '
            'End the trip in **Vienna**, where the cafe-house tradition, a UNESCO-listed way of life, insists you linger over a Melange and a slice of Sachertorte. '
            'Five cities, five appetites, one unforgettable week.'
        ),
    },
    {
        'slug': 'asia-on-a-budget',
        'title': 'Asia on a Budget: 10 Nights Under $60 a Day',
        'excerpt': 'Hostels, street food and sleeper trains: how Bali, Bangkok and Ho Chi Minh City stretch your money further.',
        'category': 'Budget Travel',
        'author': 'Kenji Tanaka',
        'read_time': '9 min read',
        'image': '/static/images/gallery/bali/bali_1.jpg',
        'places': ['Bali', 'Bangkok', 'Singapore'],
        'body': (
            'Kick off in **Bali**, where air-conditioned guesthouses in Ubud cost less than a London pub meal and warungs serve plate after plate of nasi campur for a handful of rupiah. '
            'A low-cost flight lands you in **Bangkok**, where night markets at Chatuchak and the riverside hawker stalls around Tha Tien will ruin you for home cooking forever.\n\n'
            'Before you leave South-East Asia, splurge one night in **Singapore** on a capsule hotel in Chinatown and a hawker centre dinner at Maxwell. '
            'Yes, Singapore is pricey, but a plate of Hainanese chicken rice there is both the best $5 and the best meal of the trip.'
        ),
    },
    {
        'slug': 'romantic-city-breaks',
        'title': 'Seven Romantic City Breaks for Couples',
        'excerpt': 'Where to steal a long weekend with someone special — Paris, Venice, and five more whispered favourites.',
        'category': 'City Breaks',
        'author': 'Sophie Martin',
        'read_time': '6 min read',
        'image': '/static/images/gallery/paris/paris_2.jpg',
        'places': ['Paris', 'Rome', 'Vienna', 'Amsterdam'],
        'body': (
            '**Paris** remains the benchmark: wander Montmartre at dusk, share a carafe of red in a Left Bank bistro, then walk home along the Seine. '
            'But we\u2019d argue **Rome** is just as romantic if you skip the Colosseum queue and eat in Trastevere instead. '
            '**Vienna** and its Secessionist palaces are underrated; **Amsterdam**, explored by bike along the canals, is storybook winter territory.\n\n'
            'Whichever you choose, book a hotel with a balcony and a morning pastry on the pillow.'
        ),
    },
    {
        'slug': 'beach-getaways-winter-sun',
        'title': 'Winter Sun: Five Beach Getaways That Won\u2019t Break the Bank',
        'excerpt': 'Swap the January greys for turquoise waters in Bali, the Maldives and beyond.',
        'category': 'Beach',
        'author': 'Carlos Silva',
        'read_time': '5 min read',
        'image': '/static/images/gallery/maldives/maldives_1.jpg',
        'places': ['Bali', 'Maldives', 'Lisbon'],
        'body': (
            'When the northern hemisphere shivers, head south. **Bali**\u2019s Seminyak and Canggu beaches have fierce surf and an even fiercer brunch scene. '
            'The **Maldives**, though famous for overwater bungalows, is also home to surprisingly affordable guesthouses on Maafushi and Ukulhas.\n\n'
            'If long-haul flights aren\u2019t your thing, **Lisbon**\u2019s Costa da Caparica offers 30 km of Atlantic sand 20 minutes from the city centre \u2014 surfboards, grilled sardines, and the best winter sunshine in Europe.'
        ),
    },
    {
        'slug': 'family-friendly-city-holidays',
        'title': 'Family-Friendly City Holidays That Keep Everyone Happy',
        'excerpt': 'Six cities with enough museums, parks and kid-friendly hotels to dodge a back-seat revolt.',
        'category': 'Family',
        'author': 'Emma Williams',
        'read_time': '8 min read',
        'image': '/static/images/gallery/london/london_1.jpg',
        'places': ['London', 'Amsterdam', 'Barcelona', 'Singapore'],
        'body': (
            '**London** tops the list: the Natural History Museum is free, Hyde Park has pedal boats, and most mid-range hotels offer family rooms. '
            '**Amsterdam** rewards small travellers with NEMO and canal boat trips. '
            '**Barcelona**\u2019s Ciutadella Park and the Aquarium keep toddlers busy between tapas. '
            'Long-haul? **Singapore**, with its Gardens by the Bay and spotless public transport, is the platonic ideal of a family-friendly capital.'
        ),
    },
    {
        'slug': 'slow-travel-japan',
        'title': 'Slow Travel in Japan: Kyoto, Sapporo and Beyond',
        'excerpt': 'Ditch the bullet train for a rail-pass ramble across Honshu and Hokkaido.',
        'category': 'Adventure',
        'author': 'Kenji Tanaka',
        'read_time': '10 min read',
        'image': '/static/images/gallery/tokyo/tokyo_1.jpg',
        'places': ['Tokyo', 'Sapporo', 'Osaka'],
        'body': (
            'Start in **Tokyo** for three days \u2014 Tsukiji for breakfast, Shimokitazawa for vintage, Shinjuku for lights. '
            'Then take the overnight sleeper to **Sapporo** for ramen and, in winter, the Snow Festival. '
            'Loop back through **Osaka** for takoyaki and a nightcap in Dotonbori. '
            'A seven-day Japan Rail Pass makes this trip roughly half the price you\u2019d expect.'
        ),
    },
    {
        'slug': 'landmark-hotels-with-a-view',
        'title': 'Five Landmark Hotels With Killer City Views',
        'excerpt': 'From a Shard-facing suite in London to rooftop pools in Dubai and Singapore.',
        'category': 'Luxury',
        'author': 'Sophie Martin',
        'read_time': '6 min read',
        'image': '/static/images/gallery/nyc/nyc_1.jpg',
        'places': ['London', 'Dubai', 'Singapore', 'New York', 'Hong Kong'],
        'body': (
            '**London** first: any high-floor room across the river from the Shard will do. '
            'In **Dubai**, the Burj-facing side of Downtown hotels is the view to book. '
            '**Singapore**\u2019s Marina Bay Sands needs no introduction. '
            '**New York** delivers via midtown rooftops; **Hong Kong** from Kowloon looking across the harbour. '
            'Pay for the view \u2014 you\u2019ll remember it longer than the room.'
        ),
    },
]


@app.route('/articles')
def articles_index():
    return render_template('articles.html', articles=TRAVEL_ARTICLES)


@app.route('/articles/<slug>')
def article_detail(slug):
    article = next((a for a in TRAVEL_ARTICLES if a['slug'] == slug), None)
    if not article:
        abort(404)
    # Related: up to 3 other articles sharing any place tag
    related = [a for a in TRAVEL_ARTICLES
               if a['slug'] != slug
               and set(a['places']).intersection(article['places'])][:3]
    return render_template('article_detail.html', article=article, related=related)


@app.route('/genius')
def genius():
    return render_template('genius.html')


@app.route('/deals')
def deals():
    offers = Property.query.filter(Property.discount_percent > 0).order_by(Property.discount_percent.desc()).limit(24).all()
    return render_template('deals.html', offers=offers)


# =====================================================================
# ERROR HANDLERS
# =====================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# =====================================================================
# SEED
# =====================================================================

def seed_database():
    from seed_data import (
        CITY_INFO, DESTINATION_CATEGORIES, PROPERTY_TYPES,
        EXTRA_HOTELS, TRENDING_DESTINATIONS, AMENITIES,
        build_hotel_description, get_hotel_data, get_image_map
    )

    # Don't re-seed if already present
    if Property.query.first():
        return

    # --- Categories ---
    for cat in DESTINATION_CATEGORIES:
        db.session.add(DestCategory(**cat))
    for pt in PROPERTY_TYPES:
        db.session.add(PropertyType(**pt))

    # --- Cities with images ---
    image_map = get_image_map()
    city_objs = {}
    for key, info in CITY_INFO.items():
        imgs = image_map.get('cities', {}).get(key, [])
        gallery_imgs = image_map.get('gallery', {}).get(key, [])
        c = City(
            key=key,
            display=info['display'],
            slug=info['slug'],
            country=info['country'],
            country_code=info['country_code'],
            description=info['description'],
            lat=info['lat'],
            lng=info['lng'],
            properties_count=info['properties_count'],
            average_rating=info['average_rating'],
            hero_image=imgs[0] if imgs else '',
            gallery_json=json.dumps(gallery_imgs[:12]),
        )
        db.session.add(c)
        city_objs[key] = c
    db.session.flush()

    # --- Properties ---
    scraped = get_hotel_data()['hotels']
    all_props = list(scraped) + EXTRA_HOTELS

    # Create a default user for reviews
    default_user = User(
        email='demo@booking.example',
        password_hash=bcrypt.generate_password_hash('demo1234').decode('utf-8'),
        first_name='Demo',
        last_name='User',
    )
    db.session.add(default_user)

    # Reviewers pool
    reviewer_names = [
        ('Sophie', 'Martin', 'sophie.m@test.com'),
        ('Kenji', 'Tanaka', 'kenji.t@test.com'),
        ('Emma', 'Williams', 'emma.w@test.com'),
        ('Carlos', 'Silva', 'carlos.s@test.com'),
        ('Priya', 'Sharma', 'priya.s@test.com'),
        ('Lars', 'Andersen', 'lars.a@test.com'),
        ('Mei', 'Chen', 'mei.c@test.com'),
    ]
    reviewers = []
    for fn, ln, em in reviewer_names:
        u = User(
            email=em,
            password_hash=bcrypt.generate_password_hash('test1234').decode('utf-8'),
            first_name=fn, last_name=ln,
        )
        db.session.add(u)
        reviewers.append(u)
    db.session.flush()

    dest_cat_slugs = [c['slug'] for c in DESTINATION_CATEGORIES]
    review_templates = [
        ('Exceptional stay!', 'Stunning views, great service, perfect location.', ''),
        ('Lovely place', 'Clean, comfortable and close to everything.', 'Breakfast could be better.'),
        ('Perfect for a city break', 'Excellent staff. Beautiful property. Highly recommend.', ''),
        ('Romantic getaway', 'Everything we hoped for. Will come back again.', 'Room was a bit small.'),
        ('Great value', 'Good price for the location. Nice amenities.', 'WiFi was slow in the room.'),
        ('Amazing experience', 'Truly unforgettable. The staff went above and beyond.', ''),
        ('Worth every penny', 'Luxurious, well-kept and welcoming.', 'The parking is pricey.'),
        ('Fabulous!', 'Prime location, stunning decor, very friendly staff.', ''),
        ('Relaxing stay', 'Peaceful, comfortable, had everything we needed.', ''),
        ('Business trip win', 'Quiet, productive, excellent room. Great breakfast.', ''),
    ]
    traveller_types = ['Couple', 'Family', 'Business', 'Solo', 'Group']

    # Dedup by name+city
    seen = set()
    slugs_taken = set()

    for h in all_props:
        city_key = h.get('city_key')
        city = city_objs.get(city_key)
        if not city:
            continue
        name = h['name']
        key = (name.lower(), city_key)
        if key in seen:
            continue
        seen.add(key)

        stars = h.get('stars', random.randint(3, 5))
        prop_type = h.get('type', 'Hotel')
        neighborhood = h.get('neighborhood', city.display)

        # Unique slug
        base_slug = slugify(f"{name}-{city.display}")
        slug = base_slug
        n = 2
        while slug in slugs_taken:
            slug = f"{base_slug}-{n}"
            n += 1
        slugs_taken.add(slug)

        # Price based on stars and city
        base_price = {1: 35, 2: 55, 3: 85, 4: 145, 5: 280}.get(stars, 120)
        city_multiplier = {
            'maldives': 3.5, 'nyc': 1.8, 'paris': 1.6, 'london': 1.7,
            'tokyo': 1.4, 'dubai': 1.5, 'singapore': 1.3, 'hongkong': 1.3,
            'bali': 0.7, 'bangkok': 0.6,
        }.get(city_key, 1.0)
        price = round(base_price * city_multiplier * random.uniform(0.85, 1.25), 0)

        # Rating
        rating = round(random.uniform(7.8, 9.6), 1)

        # Amenities
        amenities = random.sample(AMENITIES, random.randint(8, 14))
        if stars == 5:
            for a in ['Swimming pool', 'Spa & wellness', 'Fitness center', 'Restaurant']:
                if a not in amenities:
                    amenities.append(a)

        # Gallery - use city gallery images
        city_gallery = image_map.get('gallery', {}).get(city_key, [])
        random.shuffle(city_gallery)
        prop_gallery = city_gallery[:random.randint(8, 14)]

        # Main image - first from gallery
        main_image = prop_gallery[0] if prop_gallery else (city.hero_image or '/static/images/placeholder.jpg')

        # Room types
        room_types = [
            {'name': 'Standard Double Room', 'price': price, 'sleeps': 2, 'beds': '1 double bed'},
            {'name': 'Deluxe Queen Room', 'price': round(price * 1.25, 0), 'sleeps': 2, 'beds': '1 queen bed'},
            {'name': 'Superior Twin Room', 'price': round(price * 1.35, 0), 'sleeps': 2, 'beds': '2 single beds'},
            {'name': 'Family Room', 'price': round(price * 1.65, 0), 'sleeps': 4, 'beds': '1 double + 2 singles'},
        ]
        if stars >= 4:
            room_types.append({'name': 'Executive Suite', 'price': round(price * 2.2, 0), 'sleeps': 3, 'beds': '1 king bed + sofa bed'})
        if stars == 5:
            room_types.append({'name': 'Presidential Suite', 'price': round(price * 4.5, 0), 'sleeps': 4, 'beds': '1 king bed + 2 singles'})

        # Random dest category
        dest_cat = random.choice(dest_cat_slugs)
        if city_key in ('maldives', 'bali'):
            dest_cat = 'beach'
        elif stars == 5:
            dest_cat = 'luxury'
        elif city_key in ('nyc', 'paris', 'london', 'tokyo', 'rome', 'barcelona'):
            dest_cat = 'city-breaks'

        discount_pct = 0
        is_genius = False
        if random.random() < 0.35:
            discount_pct = random.choice([10, 15, 20, 25, 30])
        if random.random() < 0.4:
            is_genius = True

        is_featured = random.random() < 0.4

        description = build_hotel_description(name, city.display, stars, prop_type, amenities)
        short = description.split('.')[0] + '.'

        flags = derive_amenity_flags(amenities)
        max_g = max(4, 2 + stars)  # larger stars → bigger suites

        # Brand assignment — based on property name hints, falls back to deterministic pool
        name_l = name.lower()
        brand = 'Independent'
        if 'hilton' in name_l or 'doubletree' in name_l or 'conrad' in name_l or 'waldorf' in name_l:
            brand = 'Hilton'
        elif 'marriott' in name_l or 'ritz' in name_l or 'sheraton' in name_l or 'westin' in name_l or 'bulgari' in name_l or 'aloft' in name_l or 'courtyard' in name_l:
            brand = 'Marriott'
        elif 'ibis' in name_l or 'accor' in name_l or 'sofitel' in name_l or 'novotel' in name_l or 'mercure' in name_l or 'pullman' in name_l or 'raffles' in name_l:
            brand = 'Accor'
        elif 'holiday inn' in name_l or 'intercontinental' in name_l or 'crowne plaza' in name_l or 'kimpton' in name_l or 'indigo' in name_l:
            brand = 'IHG'
        elif 'hyatt' in name_l or 'andaz' in name_l:
            brand = 'Hyatt'
        elif 'wyndham' in name_l or 'ramada' in name_l or 'days inn' in name_l or 'la quinta' in name_l:
            brand = 'Wyndham'
        elif 'best western' in name_l:
            brand = 'Best Western'
        elif 'four seasons' in name_l or 'mandarin oriental' in name_l or 'aman' in name_l or 'peninsula' in name_l or 'shangri-la' in name_l or 'shangri la' in name_l:
            brand = 'Luxury Collection'
        else:
            # Deterministic pseudo-random brand assignment for variety
            brand_pool = ['Hilton', 'Marriott', 'Accor', 'IHG', 'Hyatt', 'Wyndham', 'Best Western', 'Independent', 'Independent', 'Independent']
            brand = brand_pool[(abs(hash(name)) % len(brand_pool))]

        prop = Property(
            name=name,
            slug=slug,
            property_type=prop_type,
            stars=stars,
            neighborhood=neighborhood,
            city_id=city.id,
            dest_category=dest_cat,
            address=f"{neighborhood}, {city.display}, {city.country}",
            description=description,
            short_desc=short,
            price_per_night=price,
            brand=brand,
            rating=rating,
            rating_label=rating_label_for(rating),
            review_count=random.randint(120, 3400),
            image=main_image,
            gallery_json=json.dumps(prop_gallery),
            amenities_json=json.dumps(amenities),
            room_types_json=json.dumps(room_types),
            is_featured=is_featured,
            is_genius_deal=is_genius,
            discount_percent=discount_pct,
            free_cancellation=random.random() > 0.2,
            breakfast_included=random.random() > 0.5,
            distance_from_center=round(random.uniform(0.3, 6.5), 1),
            max_guests=max_g,
            landmark_tags=json.dumps([]),
            **flags,
        )
        db.session.add(prop)
        db.session.flush()

        # Add 3-6 reviews per property
        for _ in range(random.randint(3, 6)):
            reviewer = random.choice(reviewers)
            template = random.choice(review_templates)
            review = Review(
                user_id=reviewer.id,
                property_id=prop.id,
                rating=round(random.uniform(7.5, 10.0), 1),
                title=template[0],
                body_positive=template[1],
                body_negative=template[2],
                traveller_type=random.choice(traveller_types),
                stay_length=random.randint(1, 7),
                created_at=datetime.utcnow() - timedelta(days=random.randint(5, 365)),
            )
            db.session.add(review)

    db.session.commit()
    print(f"Seeded: {City.query.count()} cities, {Property.query.count()} properties, {Review.query.count()} reviews")

    # --- Post-seed: ensure amenity combos for tasks ---
    _ensure_amenity_combos()


def _ensure_amenity_combos():
    """Make targeted amenity-flag fixes so filter combos return enough results."""

    def _ensure_flags(city_key, flags, min_count=3):
        city = City.query.filter_by(key=city_key).first()
        if not city:
            return
        q = Property.query.filter_by(city_id=city.id)
        for flag_name, flag_val in flags.items():
            q = q.filter(getattr(Property, flag_name) == flag_val)
        current = q.count()
        if current >= min_count:
            return
        candidates = Property.query.filter_by(city_id=city.id).all()
        random.shuffle(candidates)
        needed = min_count - current
        for prop in candidates:
            if needed <= 0:
                break
            already_matches = all(getattr(prop, k) == v for k, v in flags.items())
            if already_matches:
                continue
            for k, v in flags.items():
                setattr(prop, k, v)
            needed -= 1

    # Mexico City: discount_percent > 0
    city = City.query.filter_by(key='mexicocity').first()
    if city:
        props = Property.query.filter_by(city_id=city.id).filter(Property.discount_percent == 0).limit(3).all()
        for p in props:
            p.discount_percent = random.choice([10, 15, 20])
            p.is_genius_deal = True

    # Varanasi: breakfast near Kashi Vishwanath
    _ensure_flags('varanasi', {'breakfast_included': True}, min_count=3)
    # Also set landmark_tags so "near Kashi Vishwanath" search works
    city = City.query.filter_by(key='varanasi').first()
    if city:
        for p in Property.query.filter_by(city_id=city.id).all():
            tags = json.loads(p.landmark_tags or '[]')
            if 'Kashi Vishwanath' not in tags:
                tags.append('Kashi Vishwanath')
                p.landmark_tags = json.dumps(tags)

    # Chicago: 9+ rating, free cancel, gym (downtown)
    city = City.query.filter_by(key='chicago').first()
    if city:
        props = Property.query.filter_by(city_id=city.id).all()
        count = 0
        for p in props:
            if count >= 3:
                break
            p.rating = max(p.rating, 9.1)
            p.rating_label = rating_label_for(p.rating)
            p.free_cancellation = True
            p.has_gym = True
            count += 1

    # Paris: pool + WiFi (near Louvre)
    _ensure_flags('paris', {'has_pool': True, 'has_wifi': True}, min_count=3)
    # Set Louvre landmark tags for Paris properties near Louvre
    city = City.query.filter_by(key='paris').first()
    if city:
        louvre_props = Property.query.filter_by(city_id=city.id).filter(
            or_(Property.neighborhood.ilike('%louvre%'), Property.name.ilike('%louvre%'))
        ).all()
        for p in louvre_props:
            p.has_pool = True
            p.has_wifi = True
            tags = json.loads(p.landmark_tags or '[]')
            if 'Louvre' not in tags:
                tags.append('Louvre')
                p.landmark_tags = json.dumps(tags)
        # Ensure at least 3 properties have Louvre tag + pool + WiFi
        if len(louvre_props) < 3:
            for p in Property.query.filter_by(city_id=city.id).limit(3).all():
                tags = json.loads(p.landmark_tags or '[]')
                if 'Louvre' not in tags:
                    tags.append('Louvre')
                    p.landmark_tags = json.dumps(tags)
                p.has_pool = True
                p.has_wifi = True

    # Paris: 9+ WiFi breakfast
    city = City.query.filter_by(key='paris').first()
    if city:
        props = Property.query.filter_by(city_id=city.id).all()
        count = sum(1 for p in props if p.rating >= 9.0 and p.has_wifi and p.breakfast_included)
        needed = 3 - count
        for p in props:
            if needed <= 0:
                break
            if not (p.rating >= 9.0 and p.has_wifi and p.breakfast_included):
                p.rating = max(p.rating, 9.1)
                p.rating_label = rating_label_for(p.rating)
                p.has_wifi = True
                p.breakfast_included = True
                needed -= 1

    # Rome: 5-star (at least 3)
    city = City.query.filter_by(key='rome').first()
    if city:
        five_star = Property.query.filter_by(city_id=city.id, stars=5).count()
        if five_star < 3:
            for p in Property.query.filter_by(city_id=city.id).filter(Property.stars < 5).limit(3 - five_star).all():
                p.stars = 5

    # Sydney: 8+ WiFi parking
    _ensure_flags('sydney', {'has_wifi': True, 'has_parking': True}, min_count=3)
    for p in Property.query.join(City).filter(City.key == 'sydney', Property.has_wifi.is_(True), Property.has_parking.is_(True)).all():
        if p.rating < 8.0:
            p.rating = 8.2
            p.rating_label = rating_label_for(p.rating)

    # Amsterdam: 9+ bicycle
    city = City.query.filter_by(key='amsterdam').first()
    if city:
        props = Property.query.filter_by(city_id=city.id).all()
        count = sum(1 for p in props if p.rating >= 9.0 and p.has_bicycle_rental)
        needed = 3 - count
        for p in props:
            if needed <= 0:
                break
            p.rating = max(p.rating, 9.2)
            p.rating_label = rating_label_for(p.rating)
            p.has_bicycle_rental = True
            needed -= 1

    # Barcelona: WiFi + breakfast
    _ensure_flags('barcelona', {'has_wifi': True, 'breakfast_included': True}, min_count=3)

    # Lisbon: airport shuttle + 8.5+ + breakfast
    city = City.query.filter_by(key='lisbon').first()
    if city:
        props = Property.query.filter_by(city_id=city.id).all()
        count = 0
        for p in props:
            if count >= 3:
                break
            p.has_airport_shuttle = True
            p.breakfast_included = True
            p.rating = max(p.rating, 8.6)
            p.rating_label = rating_label_for(p.rating)
            count += 1

    # Melbourne: parking + WiFi
    _ensure_flags('melbourne', {'has_parking': True, 'has_wifi': True}, min_count=3)

    # Sapporo (Hokkaido): 9+
    city = City.query.filter_by(key='sapporo').first()
    if city:
        props = Property.query.filter_by(city_id=city.id).all()
        count = 0
        for p in props:
            if count >= 3:
                break
            p.rating = max(p.rating, 9.2)
            p.rating_label = rating_label_for(p.rating)
            count += 1

    # Los Angeles: breakfast + airport shuttle
    _ensure_flags('losangeles', {'breakfast_included': True, 'has_airport_shuttle': True}, min_count=3)

    # Bali: WiFi + AC
    _ensure_flags('bali', {'has_wifi': True, 'has_air_conditioning': True}, min_count=3)

    # Rome: 7+ rating + free cancellation + breakfast
    city = City.query.filter_by(key='rome').first()
    if city:
        props = Property.query.filter_by(city_id=city.id).all()
        count = sum(1 for p in props if p.rating >= 7.0 and p.free_cancellation and p.breakfast_included)
        needed = 3 - count
        for p in props:
            if needed <= 0:
                break
            if not (p.rating >= 7.0 and p.free_cancellation and p.breakfast_included):
                p.rating = max(p.rating, 7.5)
                p.rating_label = rating_label_for(p.rating)
                p.free_cancellation = True
                p.breakfast_included = True
                needed -= 1

    # Tokyo: 9+ spa
    city = City.query.filter_by(key='tokyo').first()
    if city:
        props = Property.query.filter_by(city_id=city.id).all()
        count = sum(1 for p in props if p.rating >= 9.0 and p.has_spa)
        needed = 3 - count
        for p in props:
            if needed <= 0:
                break
            p.rating = max(p.rating, 9.1)
            p.rating_label = rating_label_for(p.rating)
            p.has_spa = True
            needed -= 1

    # London: breakfast + gym/fitness
    _ensure_flags('london', {'breakfast_included': True, 'has_gym': True}, min_count=3)

    # Sydney: pool + airport shuttle
    _ensure_flags('sydney', {'has_pool': True, 'has_airport_shuttle': True}, min_count=3)

    # Vienna: parking + breakfast + 8+
    city = City.query.filter_by(key='vienna').first()
    if city:
        props = Property.query.filter_by(city_id=city.id).all()
        count = sum(1 for p in props if p.rating >= 8.0 and p.has_parking and p.breakfast_included)
        needed = 3 - count
        for p in props:
            if needed <= 0:
                break
            p.rating = max(p.rating, 8.2)
            p.rating_label = rating_label_for(p.rating)
            p.has_parking = True
            p.breakfast_included = True
            needed -= 1

    # Toronto: pet friendly + parking
    _ensure_flags('toronto', {'has_pet_friendly': True, 'has_parking': True}, min_count=3)

    # Rio de Janeiro: ensure Brand diversity with differing counts
    city = City.query.filter_by(key='rio').first() or City.query.filter_by(key='riodejaneiro').first()
    if city:
        rio_props = Property.query.filter_by(city_id=city.id).order_by(Property.id.asc()).all()
        # Assign brands so counts differ: e.g. Hilton=4, Marriott=3, Accor=2, IHG=1, Independent=rest
        plan = (['Hilton'] * 4 + ['Marriott'] * 3 + ['Accor'] * 2 + ['IHG'] * 1)
        for i, p in enumerate(rio_props):
            if i < len(plan):
                p.brand = plan[i]
            elif p.brand in (None, ''):
                p.brand = 'Independent'

    # Singapore: near NUS landmark tags
    city = City.query.filter_by(key='singapore').first()
    if city:
        nus_props = Property.query.filter_by(city_id=city.id).filter(
            Property.neighborhood.ilike('%National University of Singapore%')
        ).all()
        for p in nus_props:
            tags = json.loads(p.landmark_tags or '[]')
            if 'National University of Singapore' not in tags:
                tags.append('National University of Singapore')
                p.landmark_tags = json.dumps(tags)

    db.session.commit()
    print("  [+] Ensured amenity combos for task filters")


# =====================================================================
# BENCHMARK USERS SEED
# =====================================================================

def seed_benchmark_users():
    """Seed 4 benchmark users with full profiles, payment methods,
    pre-seeded bookings, and cart items. Idempotent."""
    # Check idempotency: if Sophie already has payment methods, skip
    sophie_check = User.query.filter_by(email='sophie.m@test.com').first()
    if sophie_check and PaymentMethod.query.filter_by(user_id=sophie_check.id).first():
        return  # already fully seeded

    PASS = 'TestPass123!'

    def _make_user(email, fn, ln, phone, country, city, address, postal, genius):
        existing = User.query.filter_by(email=email).first()
        if existing:
            existing.phone = phone
            existing.country = country
            existing.city = city
            existing.address = address
            existing.postal_code = postal
            existing.genius_level = genius
            existing.password_hash = bcrypt.generate_password_hash(PASS).decode('utf-8')
            return existing
        return User(
            email=email,
            password_hash=bcrypt.generate_password_hash(PASS).decode('utf-8'),
            first_name=fn,
            last_name=ln,
            phone=phone,
            country=country,
            city=city,
            address=address,
            postal_code=postal,
            genius_level=genius,
        )

    # --- 1. Sophie Martin — Frequent traveller, Genius level 3
    sophie = _make_user(
        'sophie.m@test.com', 'Sophie', 'Martin',
        '+33 6 12 34 56 78', 'France', 'Paris',
        '14 Rue de Rivoli, 75001 Paris', '75001', 3
    )
    if not sophie.id:
        db.session.add(sophie)
    db.session.flush()

    # Payment methods
    db.session.add(PaymentMethod(
        user_id=sophie.id, card_type='Visa', last4='4242',
        exp_month=9, exp_year=2027, cardholder_name='Sophie Martin', is_default=True))
    db.session.add(PaymentMethod(
        user_id=sophie.id, card_type='Mastercard', last4='5555',
        exp_month=3, exp_year=2026, cardholder_name='Sophie Martin', is_default=False))
    db.session.add(PaymentMethod(
        user_id=sophie.id, card_type='Amex', last4='3782',
        exp_month=11, exp_year=2028, cardholder_name='S. Martin', is_default=False))

    # Bookings — find Paris hotels
    paris_city = City.query.filter_by(key='paris').first()
    paris_props = Property.query.filter_by(city_id=paris_city.id).order_by(
        Property.rating.desc()).limit(5).all() if paris_city else []
    london_city = City.query.filter_by(key='london').first()
    london_props = Property.query.filter_by(city_id=london_city.id).order_by(
        Property.rating.desc()).limit(3).all() if london_city else []
    tokyo_city = City.query.filter_by(key='tokyo').first()
    tokyo_props = Property.query.filter_by(city_id=tokyo_city.id).order_by(
        Property.rating.desc()).limit(2).all() if tokyo_city else []

    if paris_props:
        p = paris_props[0]
        bk = Booking(
            user_id=sophie.id,
            booking_number='BKN-SOPH01',
            status='confirmed',
            total=round(p.discounted_price * 3 * 1.12, 2),
            nights=3,
            guest_first_name='Sophie', guest_last_name='Martin',
            guest_email='sophie.m@test.com', guest_phone='+33 6 12 34 56 78',
            guest_country='France',
            payment_method='Visa ending 4242',
            card_last4='4242',
            created_at=datetime.utcnow() - timedelta(days=60),
        )
        db.session.add(bk)
        db.session.flush()
        db.session.add(BookingItem(
            booking_id=bk.id, property_id=p.id,
            check_in=date.today() + timedelta(days=30),
            check_out=date.today() + timedelta(days=33),
            adults=2, children=0, rooms=1,
            room_type='Deluxe Queen Room',
            price_per_night=p.discounted_price,
            subtotal=round(p.discounted_price * 3, 2),
        ))

    if paris_props and len(paris_props) > 1:
        p2 = paris_props[1]
        bk2 = Booking(
            user_id=sophie.id,
            booking_number='BKN-SOPH02',
            status='cancelled',
            total=round(p2.discounted_price * 2 * 1.12, 2),
            nights=2,
            guest_first_name='Sophie', guest_last_name='Martin',
            guest_email='sophie.m@test.com', guest_phone='+33 6 12 34 56 78',
            guest_country='France',
            payment_method='Mastercard ending 5555',
            card_last4='5555',
            created_at=datetime.utcnow() - timedelta(days=120),
        )
        db.session.add(bk2)
        db.session.flush()
        db.session.add(BookingItem(
            booking_id=bk2.id, property_id=p2.id,
            check_in=date.today() - timedelta(days=80),
            check_out=date.today() - timedelta(days=78),
            adults=2, children=0, rooms=1, room_type='Standard Double Room',
            price_per_night=p2.discounted_price,
            subtotal=round(p2.discounted_price * 2, 2),
        ))

    if london_props:
        lp = london_props[0]
        bk3 = Booking(
            user_id=sophie.id,
            booking_number='BKN-SOPH03',
            status='confirmed',
            total=round(lp.discounted_price * 4 * 1.12, 2),
            nights=4,
            guest_first_name='Sophie', guest_last_name='Martin',
            guest_email='sophie.m@test.com', guest_phone='+33 6 12 34 56 78',
            guest_country='France',
            payment_method='Amex ending 3782',
            card_last4='3782',
            created_at=datetime.utcnow() - timedelta(days=10),
        )
        db.session.add(bk3)
        db.session.flush()
        db.session.add(BookingItem(
            booking_id=bk3.id, property_id=lp.id,
            check_in=date.today() + timedelta(days=60),
            check_out=date.today() + timedelta(days=64),
            adults=2, children=0, rooms=1, room_type='Executive Suite',
            price_per_night=lp.discounted_price,
            subtotal=round(lp.discounted_price * 4, 2),
        ))

    # Cart items for Sophie
    if tokyo_props:
        db.session.add(CartItem(
            user_id=sophie.id,
            property_id=tokyo_props[0].id,
            check_in=date.today() + timedelta(days=90),
            check_out=date.today() + timedelta(days=95),
            adults=2, children=0, rooms=1,
            room_type='Deluxe Queen Room',
        ))

    # Saved properties
    if paris_props and len(paris_props) > 2:
        db.session.add(SavedProperty(
            user_id=sophie.id, property_id=paris_props[2].id,
            list_name='Paris favourites'))
    if london_props and len(london_props) > 1:
        db.session.add(SavedProperty(
            user_id=sophie.id, property_id=london_props[1].id,
            list_name='My next trip'))

    # --- 2. Kenji Tanaka — Budget traveller
    kenji = _make_user(
        'kenji.t@test.com', 'Kenji', 'Tanaka',
        '+81 90 1234 5678', 'Japan', 'Tokyo',
        '3-1 Shinjuku, Tokyo 160-0022', '160-0022', 1
    )
    if not kenji.id:
        db.session.add(kenji)
    db.session.flush()

    db.session.add(PaymentMethod(
        user_id=kenji.id, card_type='Visa', last4='1111',
        exp_month=6, exp_year=2026, cardholder_name='Kenji Tanaka', is_default=True))
    db.session.add(PaymentMethod(
        user_id=kenji.id, card_type='Mastercard', last4='2222',
        exp_month=12, exp_year=2027, cardholder_name='Kenji Tanaka', is_default=False))

    bali_city = City.query.filter_by(key='bali').first()
    bangkok_city = City.query.filter_by(key='bangkok').first()
    bali_props = Property.query.filter_by(city_id=bali_city.id).order_by(
        Property.price_per_night.asc()).limit(5).all() if bali_city else []
    bangkok_props = Property.query.filter_by(city_id=bangkok_city.id).order_by(
        Property.price_per_night.asc()).limit(3).all() if bangkok_city else []

    if bali_props:
        bp = bali_props[0]
        bk_k1 = Booking(
            user_id=kenji.id,
            booking_number='BKN-KENJ01',
            status='confirmed',
            total=round(bp.discounted_price * 5 * 1.12, 2),
            nights=5,
            guest_first_name='Kenji', guest_last_name='Tanaka',
            guest_email='kenji.t@test.com', guest_phone='+81 90 1234 5678',
            guest_country='Japan',
            payment_method='Visa ending 1111',
            card_last4='1111',
            created_at=datetime.utcnow() - timedelta(days=30),
        )
        db.session.add(bk_k1)
        db.session.flush()
        db.session.add(BookingItem(
            booking_id=bk_k1.id, property_id=bp.id,
            check_in=date.today() + timedelta(days=14),
            check_out=date.today() + timedelta(days=19),
            adults=1, children=0, rooms=1, room_type='Standard Double Room',
            price_per_night=bp.discounted_price,
            subtotal=round(bp.discounted_price * 5, 2),
        ))

    if bangkok_props:
        bkk = bangkok_props[0]
        bk_k2 = Booking(
            user_id=kenji.id,
            booking_number='BKN-KENJ02',
            status='cancelled',
            total=round(bkk.discounted_price * 3 * 1.12, 2),
            nights=3,
            guest_first_name='Kenji', guest_last_name='Tanaka',
            guest_email='kenji.t@test.com', guest_phone='+81 90 1234 5678',
            guest_country='Japan',
            payment_method='Visa ending 1111',
            card_last4='1111',
            created_at=datetime.utcnow() - timedelta(days=90),
        )
        db.session.add(bk_k2)
        db.session.flush()
        db.session.add(BookingItem(
            booking_id=bk_k2.id, property_id=bkk.id,
            check_in=date.today() - timedelta(days=70),
            check_out=date.today() - timedelta(days=67),
            adults=1, children=0, rooms=1, room_type='Standard Double Room',
            price_per_night=bkk.discounted_price,
            subtotal=round(bkk.discounted_price * 3, 2),
        ))

    # Cart item for Kenji
    if bali_props and len(bali_props) > 1:
        db.session.add(CartItem(
            user_id=kenji.id,
            property_id=bali_props[1].id,
            check_in=date.today() + timedelta(days=45),
            check_out=date.today() + timedelta(days=48),
            adults=1, children=0, rooms=1,
            room_type='Standard Double Room',
        ))

    if bali_props and len(bali_props) > 2:
        db.session.add(SavedProperty(
            user_id=kenji.id, property_id=bali_props[2].id,
            list_name='Budget picks'))
    if bangkok_props and len(bangkok_props) > 1:
        db.session.add(SavedProperty(
            user_id=kenji.id, property_id=bangkok_props[1].id,
            list_name='Southeast Asia'))

    # --- 3. Emma Williams — Family traveller
    emma = _make_user(
        'emma.w@test.com', 'Emma', 'Williams',
        '+44 7700 900123', 'United Kingdom', 'London',
        '42 Baker Street, London W1U 6TJ', 'W1U 6TJ', 2
    )
    if not emma.id:
        db.session.add(emma)
    db.session.flush()

    db.session.add(PaymentMethod(
        user_id=emma.id, card_type='Visa', last4='3333',
        exp_month=8, exp_year=2027, cardholder_name='Emma Williams', is_default=True))
    db.session.add(PaymentMethod(
        user_id=emma.id, card_type='Visa', last4='4444',
        exp_month=2, exp_year=2026, cardholder_name='Emma Williams', is_default=False))
    db.session.add(PaymentMethod(
        user_id=emma.id, card_type='Mastercard', last4='6666',
        exp_month=5, exp_year=2029, cardholder_name='Tom Williams', is_default=False))

    barcelona_city = City.query.filter_by(key='barcelona').first()
    amsterdam_city = City.query.filter_by(key='amsterdam').first()
    rome_city = City.query.filter_by(key='rome').first()
    barcelona_props = Property.query.filter_by(city_id=barcelona_city.id).filter(
        Property.max_guests >= 4).order_by(Property.rating.desc()).limit(5).all() if barcelona_city else []
    amsterdam_props = Property.query.filter_by(city_id=amsterdam_city.id).order_by(
        Property.rating.desc()).limit(3).all() if amsterdam_city else []
    rome_props = Property.query.filter_by(city_id=rome_city.id).order_by(
        Property.rating.desc()).limit(3).all() if rome_city else []

    if barcelona_props:
        bp2 = barcelona_props[0]
        bk_e1 = Booking(
            user_id=emma.id,
            booking_number='BKN-EMMA01',
            status='confirmed',
            total=round(bp2.discounted_price * 7 * 1.12, 2),
            nights=7,
            guest_first_name='Emma', guest_last_name='Williams',
            guest_email='emma.w@test.com', guest_phone='+44 7700 900123',
            guest_country='United Kingdom',
            payment_method='Visa ending 3333',
            card_last4='3333',
            created_at=datetime.utcnow() - timedelta(days=45),
        )
        db.session.add(bk_e1)
        db.session.flush()
        db.session.add(BookingItem(
            booking_id=bk_e1.id, property_id=bp2.id,
            check_in=date.today() + timedelta(days=75),
            check_out=date.today() + timedelta(days=82),
            adults=2, children=2, rooms=1, room_type='Family Room',
            price_per_night=bp2.discounted_price,
            subtotal=round(bp2.discounted_price * 7, 2),
        ))

    if amsterdam_props:
        ap = amsterdam_props[0]
        bk_e2 = Booking(
            user_id=emma.id,
            booking_number='BKN-EMMA02',
            status='confirmed',
            total=round(ap.discounted_price * 4 * 1.12, 2),
            nights=4,
            guest_first_name='Emma', guest_last_name='Williams',
            guest_email='emma.w@test.com', guest_phone='+44 7700 900123',
            guest_country='United Kingdom',
            payment_method='Mastercard ending 6666',
            card_last4='6666',
            created_at=datetime.utcnow() - timedelta(days=200),
        )
        db.session.add(bk_e2)
        db.session.flush()
        db.session.add(BookingItem(
            booking_id=bk_e2.id, property_id=ap.id,
            check_in=date.today() - timedelta(days=170),
            check_out=date.today() - timedelta(days=166),
            adults=2, children=2, rooms=2, room_type='Superior Twin Room',
            price_per_night=ap.discounted_price,
            subtotal=round(ap.discounted_price * 4 * 2, 2),
        ))

    # Cart item for Emma
    if rome_props:
        db.session.add(CartItem(
            user_id=emma.id,
            property_id=rome_props[0].id,
            check_in=date.today() + timedelta(days=120),
            check_out=date.today() + timedelta(days=127),
            adults=2, children=2, rooms=1,
            room_type='Family Room',
        ))

    if barcelona_props and len(barcelona_props) > 1:
        db.session.add(SavedProperty(
            user_id=emma.id, property_id=barcelona_props[1].id,
            list_name='Family holidays'))
    if rome_props and len(rome_props) > 1:
        db.session.add(SavedProperty(
            user_id=emma.id, property_id=rome_props[1].id,
            list_name='Italy trip'))

    # --- 4. Carlos Silva — Business traveller
    carlos = _make_user(
        'carlos.s@test.com', 'Carlos', 'Silva',
        '+1 212 555 0199', 'United States', 'New York',
        '350 Fifth Avenue, New York NY 10118', '10118', 2
    )
    if not carlos.id:
        db.session.add(carlos)
    db.session.flush()

    db.session.add(PaymentMethod(
        user_id=carlos.id, card_type='Amex', last4='7777',
        exp_month=1, exp_year=2029, cardholder_name='Carlos Silva', is_default=True))
    db.session.add(PaymentMethod(
        user_id=carlos.id, card_type='Visa', last4='8888',
        exp_month=7, exp_year=2027, cardholder_name='Carlos Silva', is_default=False))

    chicago_city = City.query.filter_by(key='chicago').first()
    singapore_city = City.query.filter_by(key='singapore').first()
    nyc_city = City.query.filter_by(key='nyc').first()
    chicago_props = Property.query.filter_by(city_id=chicago_city.id).order_by(
        Property.rating.desc()).limit(3).all() if chicago_city else []
    singapore_props = Property.query.filter_by(city_id=singapore_city.id).order_by(
        Property.rating.desc()).limit(3).all() if singapore_city else []
    nyc_props = Property.query.filter_by(city_id=nyc_city.id).order_by(
        Property.rating.desc()).limit(3).all() if nyc_city else []

    if chicago_props:
        cp = chicago_props[0]
        bk_c1 = Booking(
            user_id=carlos.id,
            booking_number='BKN-CARL01',
            status='confirmed',
            total=round(cp.discounted_price * 2 * 1.12, 2),
            nights=2,
            guest_first_name='Carlos', guest_last_name='Silva',
            guest_email='carlos.s@test.com', guest_phone='+1 212 555 0199',
            guest_country='United States',
            special_requests='Early check-in if possible. Quiet room preferred.',
            payment_method='Amex ending 7777',
            card_last4='7777',
            created_at=datetime.utcnow() - timedelta(days=5),
        )
        db.session.add(bk_c1)
        db.session.flush()
        db.session.add(BookingItem(
            booking_id=bk_c1.id, property_id=cp.id,
            check_in=date.today() + timedelta(days=7),
            check_out=date.today() + timedelta(days=9),
            adults=1, children=0, rooms=1, room_type='Executive Suite',
            price_per_night=cp.discounted_price,
            subtotal=round(cp.discounted_price * 2, 2),
        ))

    if singapore_props:
        sp = singapore_props[0]
        bk_c2 = Booking(
            user_id=carlos.id,
            booking_number='BKN-CARL02',
            status='cancelled',
            total=round(sp.discounted_price * 3 * 1.12, 2),
            nights=3,
            guest_first_name='Carlos', guest_last_name='Silva',
            guest_email='carlos.s@test.com', guest_phone='+1 212 555 0199',
            guest_country='United States',
            payment_method='Visa ending 8888',
            card_last4='8888',
            created_at=datetime.utcnow() - timedelta(days=150),
        )
        db.session.add(bk_c2)
        db.session.flush()
        db.session.add(BookingItem(
            booking_id=bk_c2.id, property_id=sp.id,
            check_in=date.today() - timedelta(days=130),
            check_out=date.today() - timedelta(days=127),
            adults=1, children=0, rooms=1, room_type='Standard Double Room',
            price_per_night=sp.discounted_price,
            subtotal=round(sp.discounted_price * 3, 2),
        ))

    if chicago_props and len(chicago_props) > 1:
        bk_c3 = Booking(
            user_id=carlos.id,
            booking_number='BKN-CARL03',
            status='confirmed',
            total=round(chicago_props[1].discounted_price * 1 * 1.12, 2),
            nights=1,
            guest_first_name='Carlos', guest_last_name='Silva',
            guest_email='carlos.s@test.com', guest_phone='+1 212 555 0199',
            guest_country='United States',
            payment_method='Amex ending 7777',
            card_last4='7777',
            created_at=datetime.utcnow() - timedelta(days=2),
        )
        db.session.add(bk_c3)
        db.session.flush()
        db.session.add(BookingItem(
            booking_id=bk_c3.id, property_id=chicago_props[1].id,
            check_in=date.today() + timedelta(days=20),
            check_out=date.today() + timedelta(days=21),
            adults=1, children=0, rooms=1, room_type='Standard Double Room',
            price_per_night=chicago_props[1].discounted_price,
            subtotal=round(chicago_props[1].discounted_price, 2),
        ))

    if singapore_props and len(singapore_props) > 1:
        db.session.add(SavedProperty(
            user_id=carlos.id, property_id=singapore_props[1].id,
            list_name='Business trips'))
    if nyc_props:
        db.session.add(SavedProperty(
            user_id=carlos.id, property_id=nyc_props[0].id,
            list_name='NYC stays'))

    db.session.commit()
    print(f"[+] Seeded benchmark users: Sophie, Kenji, Emma, Carlos")


def _migrate_schema():
    """Lightweight schema migrations for columns added after initial rollout."""
    from sqlalchemy import text, inspect
    try:
        insp = inspect(db.engine)
        if 'property' in insp.get_table_names():
            cols = {c['name'] for c in insp.get_columns('property')}
            if 'review_scores_json' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE property ADD COLUMN review_scores_json TEXT'))
            if 'lat' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE property ADD COLUMN lat FLOAT'))
            if 'lng' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE property ADD COLUMN lng FLOAT'))
        # City: add nearest_beach_* columns if missing (used by sort=distance_beach)
        if 'city' in insp.get_table_names():
            ccols = {c['name'] for c in insp.get_columns('city')}
            if 'nearest_beach_name' not in ccols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE city ADD COLUMN nearest_beach_name VARCHAR(120)'))
            if 'nearest_beach_lat' not in ccols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE city ADD COLUMN nearest_beach_lat FLOAT'))
            if 'nearest_beach_lng' not in ccols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE city ADD COLUMN nearest_beach_lng FLOAT'))
        # Populate review_scores_json for properties that don't have it yet
        missing = Property.query.filter(
            or_(Property.review_scores_json.is_(None), Property.review_scores_json == '')
        ).all()
        for p in missing:
            p.review_scores_json = json.dumps(p.get_review_scores())
        if missing:
            db.session.commit()
            print(f"[migrate] populated review_scores_json for {len(missing)} properties")

        # Backfill property lat/lng from city centroid + deterministic jitter
        # so every search result can show a "X.X miles from <landmark>" line.
        no_geo = Property.query.filter(
            or_(Property.lat.is_(None), Property.lng.is_(None))
        ).all()
        if no_geo:
            for p in no_geo:
                city = p.city
                if city is None or city.lat is None or city.lng is None:
                    continue
                rng = random.Random((p.id or 0) * 9301 + 49297)
                p.lat = city.lat + (rng.random() - 0.5) * 0.08
                p.lng = city.lng + (rng.random() - 0.5) * 0.08
            db.session.commit()
            print(f"[migrate] backfilled lat/lng for {len(no_geo)} properties")

        # Seed landmark table if empty
        if Landmark.query.count() == 0:
            _seed_landmarks()

        # Backfill nearest-beach columns for any city missing them. Idempotent.
        try:
            missing_beach = City.query.filter(
                or_(City.nearest_beach_lat.is_(None),
                    City.nearest_beach_lng.is_(None),
                    City.nearest_beach_name.is_(None),
                    City.nearest_beach_name == '')
            ).count()
            if missing_beach:
                _seed_beaches()
        except Exception as _e2:
            print(f"[migrate] beach seed warning: {_e2}")
    except Exception as _e:
        # best-effort — never crash on migrate
        print(f"[migrate] warning: {_e}")


# ---------------------------------------------------------------------------
# Landmark seed data (canonical names + lat/lng + subway flag).
# Mirrors migrate_landmarks_and_coords.py and is run on app start so a fresh
# image always has these even if the migration script wasn't separately run.
# ---------------------------------------------------------------------------
LANDMARK_SEED = [
    ('nus', 'National University of Singapore',
     ['NUS', 'University of Singapore'], 'singapore', 1.2966, 103.7764, False, 'landmark'),
    ('nus-subway', 'National University of Singapore Subway Access',
     ['NUS subway', 'NUS MRT', 'Kent Ridge MRT'], 'singapore', 1.2937, 103.7847, True, 'metro'),
    ('marina-bay-sands', 'Marina Bay Sands', ['MBS', 'Marina Bay'], 'singapore', 1.2834, 103.8607, False, 'landmark'),
    ('gardens-by-the-bay', 'Gardens by the Bay', ['Supertree Grove'], 'singapore', 1.2816, 103.8636, False, 'landmark'),
    ('orchard-road', 'Orchard Road', ['Orchard'], 'singapore', 1.3048, 103.8318, True, 'neighborhood'),
    ('changi-airport', 'Changi Airport', ['SIN airport', 'Singapore Airport'], 'singapore', 1.3644, 103.9915, True, 'poi'),
    ('sentosa-island', 'Sentosa Island', ['Sentosa'], 'singapore', 1.2494, 103.8303, False, 'landmark'),
    ('times-square', 'Times Square', ['Times Sq'], 'nyc', 40.7580, -73.9855, True, 'landmark'),
    ('central-park', 'Central Park', [], 'nyc', 40.7829, -73.9654, True, 'landmark'),
    ('empire-state', 'Empire State Building', ['Empire State'], 'nyc', 40.7484, -73.9857, True, 'landmark'),
    ('statue-of-liberty', 'Statue of Liberty', ['Liberty Island'], 'nyc', 40.6892, -74.0445, False, 'landmark'),
    ('grand-central', 'Grand Central Terminal', ['Grand Central Station'], 'nyc', 40.7527, -73.9772, True, 'metro'),
    ('brooklyn-bridge', 'Brooklyn Bridge', [], 'nyc', 40.7061, -73.9969, True, 'landmark'),
    ('madison-square-garden', 'Madison Square Garden', ['MSG'], 'nyc', 40.7505, -73.9934, True, 'landmark'),
    ('eiffel-tower', 'Eiffel Tower', ['Tour Eiffel'], 'paris', 48.8584, 2.2945, True, 'landmark'),
    ('louvre', 'Louvre Museum', ['Musee du Louvre', 'The Louvre'], 'paris', 48.8606, 2.3376, True, 'landmark'),
    ('notre-dame', 'Notre Dame Cathedral', ['Notre-Dame de Paris'], 'paris', 48.8530, 2.3499, True, 'landmark'),
    ('arc-de-triomphe', 'Arc de Triomphe', [], 'paris', 48.8738, 2.2950, True, 'landmark'),
    ('champs-elysees', 'Champs-Élysées', ['Champs Elysees'], 'paris', 48.8698, 2.3076, True, 'neighborhood'),
    ('montmartre', 'Montmartre', ['Sacre Coeur'], 'paris', 48.8867, 2.3431, True, 'neighborhood'),
    ('big-ben', 'Big Ben', ['Elizabeth Tower'], 'london', 51.5007, -0.1246, True, 'landmark'),
    ('tower-of-london', 'Tower of London', [], 'london', 51.5081, -0.0759, True, 'landmark'),
    ('buckingham-palace', 'Buckingham Palace', [], 'london', 51.5014, -0.1419, True, 'landmark'),
    ('london-eye', 'London Eye', [], 'london', 51.5033, -0.1196, True, 'landmark'),
    ('british-museum', 'British Museum', [], 'london', 51.5194, -0.1270, True, 'landmark'),
    ('kings-cross', "King's Cross Station", ['Kings Cross'], 'london', 51.5308, -0.1238, True, 'metro'),
    ('shibuya-crossing', 'Shibuya Crossing', ['Shibuya Scramble'], 'tokyo', 35.6595, 139.7005, True, 'landmark'),
    ('shibuya', 'Shibuya', [], 'tokyo', 35.6580, 139.7016, True, 'neighborhood'),
    ('tokyo-tower', 'Tokyo Tower', [], 'tokyo', 35.6586, 139.7454, True, 'landmark'),
    ('tokyo-skytree', 'Tokyo Skytree', ['Skytree'], 'tokyo', 35.7101, 139.8107, True, 'landmark'),
    ('shinjuku-station', 'Shinjuku Station', ['Shinjuku'], 'tokyo', 35.6896, 139.7006, True, 'metro'),
    ('akihabara', 'Akihabara', ['Akiba'], 'tokyo', 35.7022, 139.7745, True, 'neighborhood'),
    ('ginza', 'Ginza', [], 'tokyo', 35.6717, 139.7649, True, 'neighborhood'),
    ('colosseum', 'Colosseum', ['Colosseo'], 'rome', 41.8902, 12.4922, True, 'landmark'),
    ('vatican', 'Vatican City', ['Vatican', 'St Peters Basilica'], 'rome', 41.9029, 12.4534, True, 'landmark'),
    ('trevi-fountain', 'Trevi Fountain', ['Fontana di Trevi'], 'rome', 41.9009, 12.4833, True, 'landmark'),
    ('pantheon-rome', 'Pantheon', [], 'rome', 41.8986, 12.4769, False, 'landmark'),
    ('sagrada-familia', 'Sagrada Família', ['Sagrada Familia'], 'barcelona', 41.4036, 2.1744, True, 'landmark'),
    ('park-guell', 'Park Güell', ['Park Guell'], 'barcelona', 41.4145, 2.1527, False, 'landmark'),
    ('la-rambla', 'La Rambla', ['Las Ramblas'], 'barcelona', 41.3809, 2.1729, True, 'neighborhood'),
    ('burj-khalifa', 'Burj Khalifa', [], 'dubai', 25.1972, 55.2744, True, 'landmark'),
    ('palm-jumeirah', 'Palm Jumeirah', [], 'dubai', 25.1124, 55.1390, False, 'landmark'),
    ('dubai-mall', 'Dubai Mall', [], 'dubai', 25.1972, 55.2796, True, 'landmark'),
    ('victoria-peak', 'Victoria Peak', ['The Peak'], 'hongkong', 22.2759, 114.1455, False, 'landmark'),
    ('tsim-sha-tsui', 'Tsim Sha Tsui', ['TST'], 'hongkong', 22.2987, 114.1722, True, 'neighborhood'),
    ('grand-palace-bkk', 'Grand Palace', [], 'bangkok', 13.7500, 100.4913, False, 'landmark'),
    ('khao-san-road', 'Khao San Road', [], 'bangkok', 13.7589, 100.4977, False, 'neighborhood'),
    ('sydney-opera-house', 'Sydney Opera House', ['Opera House'], 'sydney', -33.8568, 151.2153, True, 'landmark'),
    ('bondi-beach', 'Bondi Beach', [], 'sydney', -33.8908, 151.2743, False, 'landmark'),
    ('hollywood-sign', 'Hollywood Sign', [], 'losangeles', 34.1341, -118.3215, False, 'landmark'),
    ('santa-monica-pier', 'Santa Monica Pier', [], 'losangeles', 34.0083, -118.4988, False, 'landmark'),
    ('brandenburg-gate', 'Brandenburg Gate', ['Brandenburger Tor'], 'berlin', 52.5163, 13.3777, True, 'landmark'),
    ('berlin-wall', 'Berlin Wall Memorial', ['East Side Gallery'], 'berlin', 52.5050, 13.4396, True, 'landmark'),
    ('rijksmuseum', 'Rijksmuseum', [], 'amsterdam', 52.3600, 4.8852, True, 'landmark'),
    ('anne-frank-house', 'Anne Frank House', [], 'amsterdam', 52.3752, 4.8840, True, 'landmark'),
    ('hagia-sophia', 'Hagia Sophia', [], 'istanbul', 41.0086, 28.9802, True, 'landmark'),
    ('blue-mosque', 'Blue Mosque', ['Sultan Ahmed Mosque'], 'istanbul', 41.0054, 28.9768, True, 'landmark'),
    ('st-marks-square', "St. Mark's Square", ['Piazza San Marco'], 'venice', 45.4341, 12.3388, False, 'landmark'),
    ('rialto-bridge', 'Rialto Bridge', [], 'venice', 45.4380, 12.3358, False, 'landmark'),
    ('charles-bridge', 'Charles Bridge', [], 'prague', 50.0865, 14.4114, True, 'landmark'),
    ('prague-castle', 'Prague Castle', [], 'prague', 50.0900, 14.4006, True, 'landmark'),
    ('uluwatu-temple', 'Uluwatu Temple', [], 'bali', -8.8290, 115.0849, False, 'landmark'),
    ('kuta-beach', 'Kuta Beach', [], 'bali', -8.7180, 115.1686, False, 'landmark'),
    ('male-airport', 'Velana International Airport', ['Male Airport'], 'maldives', 4.1918, 73.5290, False, 'poi'),
    ('zocalo', 'Zócalo', ['Plaza de la Constitucion'], 'mexicocity', 19.4326, -99.1332, True, 'landmark'),
    ('cn-tower', 'CN Tower', [], 'toronto', 43.6426, -79.3871, True, 'landmark'),
    ('willis-tower', 'Willis Tower', ['Sears Tower'], 'chicago', 41.8789, -87.6359, True, 'landmark'),
    ('navy-pier', 'Navy Pier', [], 'chicago', 41.8917, -87.6086, False, 'landmark'),
]


def _seed_landmarks():
    keys = {c.key: c.id for c in City.query.all()}
    n = 0
    for slug, name, aliases, city_key, lat, lng, subway, kind in LANDMARK_SEED:
        if Landmark.query.filter_by(slug=slug).first():
            continue
        db.session.add(Landmark(
            slug=slug, name=name, aliases_json=json.dumps(aliases or []),
            city_id=keys.get(city_key), lat=lat, lng=lng,
            subway_access=bool(subway), kind=kind,
        ))
        n += 1
    if n:
        db.session.commit()
        print(f"[migrate] seeded {n} landmarks")


# ---------------------------------------------------------------------------
# Nearest-beach seed data — used for sort=distance_beach on /search.
# Real booking.com exposes "Distance From Beach" as a sort option for every
# search (even for inland cities — the distance just gets larger). We seed
# the closest real beach (or a swim-relevant lakefront) for every one of
# our 33 cities. Inland cities still get a defined point so the sort is
# universal; the distance number just ends up being large, exactly like
# the upstream behaviour.
# Tuple: (city_key, beach_name, lat, lng)
# ---------------------------------------------------------------------------
BEACH_SEED = [
    ('amsterdam',  'Zandvoort Beach',          52.3700,   4.5300),
    ('bali',       'Kuta Beach',               -8.7180,  115.1686),
    ('bangkok',    'Bang Saen Beach',          13.2870,  100.9290),
    ('barcelona',  'Barceloneta Beach',        41.3784,    2.1925),
    ('berlin',     'Strandbad Wannsee',        52.4220,   13.1790),
    ('chennai',    'Marina Beach',             13.0500,   80.2824),
    ('chicago',    'Oak Street Beach',         41.9026,  -87.6271),
    ('dubai',      'Jumeirah Beach',           25.2048,   55.2708),
    ('hongkong',   'Repulse Bay Beach',        22.2370,  114.1980),
    ('istanbul',   'Caddebostan Beach',        40.9646,   29.0606),
    ('jakarta',    'Ancol Beach',              -6.1240,  106.8400),
    ('lisbon',     'Carcavelos Beach',         38.6810,   -9.3370),
    ('london',     'Brighton Beach',           50.8198,   -0.1366),
    ('losangeles', 'Santa Monica Beach',       34.0118, -118.4960),
    ('maldives',   'Bikini Beach (Maafushi)',   3.9425,   73.4905),
    ('melbourne',  'St Kilda Beach',          -37.8676,  144.9740),
    ('mexicocity', 'Acapulco Beach',           16.8531,  -99.8237),
    ('nyc',        'Coney Island Beach',       40.5755,  -73.9707),
    ('ohio',       'Headlands Beach',          41.7570,  -81.2810),
    ('paris',      'Deauville Beach',          49.3580,    0.0760),
    ('prague',     'Slapy Reservoir Beach',    49.8120,   14.4350),
    ('rio',        'Copacabana Beach',        -22.9711,  -43.1822),
    ('rome',       'Lido di Ostia',            41.7320,   12.2770),
    ('santorini',  'Red Beach',                36.3486,   25.3937),
    ('sapporo',    'Otaru Dream Beach',        43.2056,  140.9594),
    ('shenzhen',   'Dameisha Beach',           22.6086,  114.3129),
    ('singapore',  'Siloso Beach',              1.2494,  103.8303),
    ('sydney',     'Bondi Beach',             -33.8908,  151.2743),
    ('tokyo',      'Odaiba Beach',             35.6298,  139.7762),
    ('toronto',    'Woodbine Beach',           43.6627,  -79.3083),
    ('varanasi',   'Assi Ghat Bathing Steps',  25.2880,   83.0080),
    ('venice',     'Lido di Venezia Beach',    45.4087,   12.3739),
    ('vienna',     'Gänsehäufel Beach',        48.2200,   16.4380),
]


def _seed_beaches():
    """Populate City.nearest_beach_* columns from BEACH_SEED.

    Idempotent: only fills cities that have no beach yet.
    """
    by_key = {c.key: c for c in City.query.all()}
    n = 0
    for city_key, name, lat, lng in BEACH_SEED:
        c = by_key.get(city_key)
        if c is None:
            continue
        if (c.nearest_beach_lat is None or c.nearest_beach_lng is None
                or not c.nearest_beach_name):
            c.nearest_beach_name = name
            c.nearest_beach_lat = lat
            c.nearest_beach_lng = lng
            n += 1
    if n:
        db.session.commit()
        print(f"[migrate] seeded nearest beach for {n} cities")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        _migrate_schema()
        seed_database()
        seed_benchmark_users()
    port = int(os.environ.get('PORT', 28844))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # Ensure DB is created and seeded when imported (e.g. by run_tasks.py)
    with app.app_context():
        db.create_all()
        _migrate_schema()
        seed_database()
        seed_benchmark_users()
