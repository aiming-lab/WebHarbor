#!/usr/bin/env python3
"""CarMax.com mirror — Flask application.

Full inventory search, vehicle detail, research, comparison, saved cars,
sell-my-car appraisal, financing pre-qualification, reserve & test drive
booking, checkout, MaxCare warranty, stores, articles, FAQ, customer
reviews.
"""
import json
import os
import re
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from sqlalchemy import func
from wtforms import (BooleanField, FloatField, HiddenField, IntegerField,
                     PasswordField, RadioField, SelectField, StringField,
                     TextAreaField)
from wtforms.validators import (DataRequired, Email, EqualTo, Length,
                                NumberRange, Optional, Regexp)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'carmax-mirror-webharbor-key'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'carmax.db')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to access your CarMax account.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)


# =============================================================================
# Models
# =============================================================================

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), default='')
    last_name = db.Column(db.String(80), default='')
    phone = db.Column(db.String(30), default='')
    zip_code = db.Column(db.String(10), default='')
    address_line1 = db.Column(db.String(200), default='')
    address_line2 = db.Column(db.String(200), default='')
    city = db.Column(db.String(80), default='')
    state = db.Column(db.String(2), default='')
    home_store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=True)

    pre_qual_active = db.Column(db.Boolean, default=False)
    pre_qual_monthly_max = db.Column(db.Float, default=0.0)
    pre_qual_term_months = db.Column(db.Integer, default=72)
    pre_qual_apr = db.Column(db.Float, default=0.0)
    pre_qual_down_payment = db.Column(db.Float, default=2000.0)
    pre_qual_credit_tier = db.Column(db.String(20), default='')
    pre_qual_expires_at = db.Column(db.Date, nullable=True)

    annual_income = db.Column(db.Integer, default=0)
    employment_status = db.Column(db.String(40), default='')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    saved_vehicles = db.relationship('SavedVehicle', backref='user', lazy=True,
                                     cascade='all, delete-orphan')
    reservations = db.relationship('Reservation', backref='user', lazy=True,
                                   cascade='all, delete-orphan')
    test_drives = db.relationship('TestDrive', backref='user', lazy=True,
                                  cascade='all, delete-orphan')
    appraisals = db.relationship('Appraisal', backref='user', lazy=True,
                                 cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='user', lazy=True,
                             cascade='all, delete-orphan',
                             foreign_keys='Order.user_id')
    reviews = db.relationship('Review', backref='user', lazy=True,
                              cascade='all, delete-orphan')
    comparisons = db.relationship('Comparison', backref='user', lazy=True,
                                  cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        try:
            return bcrypt.check_password_hash(self.password_hash, pw)
        except Exception:
            return False

    @property
    def full_name(self):
        n = f'{self.first_name} {self.last_name}'.strip()
        return n or (self.email.split('@')[0] if self.email else 'CarMax customer')

    @property
    def pre_qual_is_valid(self):
        return bool(self.pre_qual_active and self.pre_qual_expires_at
                    and self.pre_qual_expires_at >= date(2026, 5, 14))


class Store(db.Model):
    __tablename__ = 'stores'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    street = db.Column(db.String(200), default='')
    city = db.Column(db.String(80), nullable=False, index=True)
    state = db.Column(db.String(2), nullable=False, index=True)
    zip_code = db.Column(db.String(10), default='')
    phone = db.Column(db.String(30), default='')
    hours_weekday = db.Column(db.String(40), default='10:00 AM - 9:00 PM')
    hours_saturday = db.Column(db.String(40), default='9:00 AM - 9:00 PM')
    hours_sunday = db.Column(db.String(40), default='12:00 PM - 7:00 PM')
    has_appraisal = db.Column(db.Boolean, default=True)
    has_express_pickup = db.Column(db.Boolean, default=True)
    has_service = db.Column(db.Boolean, default=True)
    has_home_delivery = db.Column(db.Boolean, default=True)
    latitude = db.Column(db.Float, default=0.0)
    longitude = db.Column(db.Float, default=0.0)
    image = db.Column(db.String(255), default='/static/images/stores/storefront_default.jpg')

    vehicles = db.relationship('Vehicle', backref='store', lazy=True)

    @property
    def location_label(self):
        return f'{self.city}, {self.state}'


class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    id = db.Column(db.Integer, primary_key=True)
    stock_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    vin = db.Column(db.String(20), default='')

    year = db.Column(db.Integer, nullable=False, index=True)
    make = db.Column(db.String(40), nullable=False, index=True)
    make_slug = db.Column(db.String(40), nullable=False, index=True)
    model = db.Column(db.String(60), nullable=False, index=True)
    model_slug = db.Column(db.String(60), nullable=False, index=True)
    trim = db.Column(db.String(60), default='', index=True)
    trim_slug = db.Column(db.String(60), default='', index=True)
    body_style = db.Column(db.String(30), default='Sedan', index=True)

    exterior_color = db.Column(db.String(40), default='')
    interior_color = db.Column(db.String(40), default='')

    mileage = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False, index=True)
    list_price = db.Column(db.Float, default=0.0)

    engine_text = db.Column(db.String(80), default='')
    engine_displacement = db.Column(db.Float, default=0.0)
    horsepower = db.Column(db.Integer, default=0)
    torque = db.Column(db.Integer, default=0)
    transmission = db.Column(db.String(30), default='Automatic')
    drive_type = db.Column(db.String(10), default='FWD')
    fuel_type = db.Column(db.String(30), default='Gasoline', index=True)

    mpg_city = db.Column(db.Integer, default=0)
    mpg_highway = db.Column(db.Integer, default=0)
    mpg_combined = db.Column(db.Integer, default=0)

    seating_capacity = db.Column(db.Integer, default=5)
    cargo_volume = db.Column(db.Float, default=0.0)
    wheelbase = db.Column(db.Float, default=0.0)
    overall_length = db.Column(db.Float, default=0.0)
    width = db.Column(db.Float, default=0.0)
    height = db.Column(db.Float, default=0.0)
    fuel_capacity = db.Column(db.Float, default=0.0)

    features = db.Column(db.Text, default='[]')
    description = db.Column(db.Text, default='')

    image = db.Column(db.String(255), default='')
    gallery_images = db.Column(db.Text, default='[]')

    customer_rating = db.Column(db.Float, default=4.4)
    customer_rating_count = db.Column(db.Integer, default=0)
    repairpal_rating = db.Column(db.Float, default=4.0)

    is_certified = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_no_haggle = db.Column(db.Boolean, default=True)
    is_new_arrival = db.Column(db.Boolean, default=False)
    is_price_drop = db.Column(db.Boolean, default=False)

    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    transfer_fee = db.Column(db.Float, default=0.0)

    days_on_lot = db.Column(db.Integer, default=14)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def title(self):
        parts = [str(self.year), self.make, self.model]
        if self.trim:
            parts.append(self.trim)
        return ' '.join(parts)

    @property
    def short_title(self):
        return f'{self.year} {self.make} {self.model}'

    @property
    def headline_price(self):
        return f'${int(self.price):,}'

    @property
    def mileage_label(self):
        return f'{self.mileage:,} mi'

    def get_features(self):
        try:
            return json.loads(self.features or '[]')
        except Exception:
            return []

    def get_gallery(self):
        try:
            paths = json.loads(self.gallery_images or '[]')
            return [p for p in paths if p]
        except Exception:
            return []

    def all_images(self):
        gallery = self.get_gallery()
        if self.image and self.image not in gallery:
            return [self.image] + gallery
        return gallery or ([self.image] if self.image else [])

    def has_feature(self, feat):
        f = feat.lower()
        return any(f == g.lower() for g in self.get_features())

    def estimated_monthly_payment(self, term_months=72, apr=0.0699, down=2000):
        return estimated_payment(self.price, term_months, apr, down)

    def savings(self):
        if self.list_price and self.list_price > self.price:
            return self.list_price - self.price
        return 0.0


class SavedVehicle(db.Model):
    __tablename__ = 'saved_vehicles'
    __table_args__ = (db.UniqueConstraint('user_id', 'vehicle_id',
                                          name='uq_saved_user_vehicle'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.String(200), default='')

    vehicle = db.relationship('Vehicle', lazy='joined')


class Comparison(db.Model):
    __tablename__ = 'comparisons'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_key = db.Column(db.String(64), default='', index=True)
    name = db.Column(db.String(80), default='My comparison')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('ComparisonItem', backref='comparison', lazy=True,
                            cascade='all, delete-orphan')


class ComparisonItem(db.Model):
    __tablename__ = 'comparison_items'
    __table_args__ = (db.UniqueConstraint('comparison_id', 'vehicle_id',
                                          name='uq_compare_item'),)
    id = db.Column(db.Integer, primary_key=True)
    comparison_id = db.Column(db.Integer, db.ForeignKey('comparisons.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    vehicle = db.relationship('Vehicle', lazy='joined')


class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    status = db.Column(db.String(20), default='active')
    appointment_date = db.Column(db.Date, nullable=True)
    expires_at = db.Column(db.Date, nullable=False)
    transfer_required = db.Column(db.Boolean, default=False)
    transfer_fee = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    vehicle = db.relationship('Vehicle', lazy='joined')
    store = db.relationship('Store', lazy='joined')


class TestDrive(db.Model):
    __tablename__ = 'test_drives'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    location_type = db.Column(db.String(20), default='in_store')
    scheduled_date = db.Column(db.Date, nullable=False)
    scheduled_time = db.Column(db.String(10), default='10:00 AM')
    status = db.Column(db.String(20), default='confirmed')
    notes = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    vehicle = db.relationship('Vehicle', lazy='joined')
    store = db.relationship('Store', lazy='joined')


class Appraisal(db.Model):
    __tablename__ = 'appraisals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    year = db.Column(db.Integer, nullable=False)
    make = db.Column(db.String(40), nullable=False)
    model = db.Column(db.String(60), nullable=False)
    trim = db.Column(db.String(60), default='')
    mileage = db.Column(db.Integer, nullable=False)
    condition = db.Column(db.String(20), default='good')
    exterior_color = db.Column(db.String(40), default='')
    license_plate = db.Column(db.String(20), default='')
    license_state = db.Column(db.String(2), default='')
    vin = db.Column(db.String(20), default='')
    zip_code = db.Column(db.String(10), default='')
    has_accidents = db.Column(db.Boolean, default=False)
    owner_count = db.Column(db.Integer, default=1)
    offer_amount = db.Column(db.Float, nullable=False)
    offer_valid_until = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='active')
    contact_email = db.Column(db.String(120), default='')
    contact_phone = db.Column(db.String(30), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def vehicle_label(self):
        parts = [str(self.year), self.make, self.model]
        if self.trim:
            parts.append(self.trim)
        return ' '.join(parts)


class FinancePreQual(db.Model):
    __tablename__ = 'finance_prequals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    annual_income = db.Column(db.Integer, nullable=False)
    employment_status = db.Column(db.String(40), nullable=False)
    monthly_payment_max = db.Column(db.Float, nullable=False)
    down_payment = db.Column(db.Float, default=2000)
    term_months = db.Column(db.Integer, default=72)
    estimated_apr = db.Column(db.Float, nullable=False)
    credit_tier = db.Column(db.String(20), default='good')
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.Date, nullable=False)


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='processing')
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    subtotal = db.Column(db.Float, default=0)
    transfer_fee = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    title_fee = db.Column(db.Float, default=99)
    registration_fee = db.Column(db.Float, default=55)
    total = db.Column(db.Float, default=0)
    maxcare_plan = db.Column(db.String(40), default='')
    maxcare_price = db.Column(db.Float, default=0)
    payment_method = db.Column(db.String(30), default='carmax_auto_finance')
    payment_last4 = db.Column(db.String(4), default='')
    payment_apr = db.Column(db.Float, default=0)
    payment_term_months = db.Column(db.Integer, default=72)
    monthly_payment = db.Column(db.Float, default=0)
    down_payment = db.Column(db.Float, default=0)
    trade_in_appraisal_id = db.Column(db.Integer, db.ForeignKey('appraisals.id'), nullable=True)
    trade_in_value = db.Column(db.Float, default=0)
    pickup_or_delivery = db.Column(db.String(20), default='pickup')
    delivery_address = db.Column(db.String(200), default='')
    pickup_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    vehicle = db.relationship('Vehicle', lazy='joined')
    store = db.relationship('Store', lazy='joined')
    trade_in_appraisal = db.relationship('Appraisal', lazy='joined',
                                         foreign_keys=[trade_in_appraisal_id])


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    make_slug = db.Column(db.String(40), nullable=False, index=True)
    model_slug = db.Column(db.String(60), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(120), default='')
    body = db.Column(db.Text, default='')
    reviewer_name = db.Column(db.String(80), default='Verified buyer')
    location = db.Column(db.String(80), default='')
    helpful_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(40), default='research', index=True)
    author = db.Column(db.String(80), default='CarMax Editorial')
    summary = db.Column(db.String(500), default='')
    body = db.Column(db.Text, default='')
    hero_image = db.Column(db.String(255), default='')
    published_at = db.Column(db.Date, nullable=False)
    is_featured = db.Column(db.Boolean, default=False)


@login_manager.user_loader
def load_user(uid):
    try:
        return db.session.get(User, int(uid))
    except Exception:
        return None


# =============================================================================
# Forms
# =============================================================================

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Keep me signed in')


class RegisterForm(FlaskForm):
    first_name = StringField('First name', validators=[DataRequired(), Length(max=80)])
    last_name = StringField('Last name', validators=[DataRequired(), Length(max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[Optional(), Length(max=30)])
    zip_code = StringField('ZIP code', validators=[Optional(), Length(max=10)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField('Confirm password',
                            validators=[DataRequired(), EqualTo('password')])


class AccountEditForm(FlaskForm):
    first_name = StringField('First name', validators=[DataRequired(), Length(max=80)])
    last_name = StringField('Last name', validators=[DataRequired(), Length(max=80)])
    phone = StringField('Phone', validators=[Optional(), Length(max=30)])
    address_line1 = StringField('Street address', validators=[Optional(), Length(max=200)])
    address_line2 = StringField('Apt / Unit', validators=[Optional(), Length(max=200)])
    city = StringField('City', validators=[Optional(), Length(max=80)])
    state = StringField('State', validators=[Optional(), Length(max=2)])
    zip_code = StringField('ZIP', validators=[Optional(), Length(max=10)])


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current password', validators=[DataRequired()])
    new_password = PasswordField('New password',
                                 validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField('Confirm new password',
                            validators=[DataRequired(), EqualTo('new_password')])


class SellMyCarForm(FlaskForm):
    year = IntegerField('Year', validators=[DataRequired(), NumberRange(min=1985, max=2027)])
    make = StringField('Make', validators=[DataRequired(), Length(max=40)])
    model = StringField('Model', validators=[DataRequired(), Length(max=60)])
    trim = StringField('Trim', validators=[Optional(), Length(max=60)])
    mileage = IntegerField('Mileage',
                           validators=[DataRequired(), NumberRange(min=0, max=400000)])
    condition = SelectField('Condition', choices=[
        ('excellent', 'Excellent'), ('good', 'Good'),
        ('fair', 'Fair'), ('poor', 'Poor'),
    ], default='good')
    exterior_color = StringField('Exterior color', validators=[Optional(), Length(max=40)])
    license_plate = StringField('License plate', validators=[Optional(), Length(max=20)])
    license_state = StringField('License state', validators=[Optional(), Length(max=2)])
    vin = StringField('VIN', validators=[Optional(), Length(max=20)])
    zip_code = StringField('ZIP', validators=[DataRequired(), Length(max=10)])
    has_accidents = BooleanField('Reported accidents')
    owner_count = IntegerField('Number of owners',
                               validators=[Optional(), NumberRange(min=1, max=10)],
                               default=1)
    contact_email = StringField('Email', validators=[Optional(), Email()])
    contact_phone = StringField('Phone', validators=[Optional(), Length(max=30)])


class PreQualForm(FlaskForm):
    annual_income = IntegerField('Annual income (pre-tax)',
                                 validators=[DataRequired(), NumberRange(min=0, max=10000000)])
    employment_status = SelectField('Employment status', choices=[
        ('employed_full_time', 'Employed (full-time)'),
        ('employed_part_time', 'Employed (part-time)'),
        ('self_employed', 'Self-employed'),
        ('retired', 'Retired'),
        ('student', 'Student'),
        ('other', 'Other'),
    ], default='employed_full_time')
    monthly_payment_max = FloatField('Max monthly payment ($)',
                                     validators=[DataRequired(), NumberRange(min=100, max=5000)])
    down_payment = FloatField('Down payment ($)',
                              validators=[Optional(), NumberRange(min=0)], default=2000)
    term_months = SelectField('Loan term', choices=[
        ('36', '36 months'), ('48', '48 months'), ('60', '60 months'),
        ('66', '66 months'), ('72', '72 months'),
    ], default='72')
    credit_tier = SelectField('Credit profile', choices=[
        ('excellent', 'Excellent (720+)'),
        ('good', 'Good (660-719)'),
        ('fair', 'Fair (620-659)'),
        ('building', 'Building credit (<620)'),
    ], default='good')


class ReserveForm(FlaskForm):
    store_id = HiddenField()
    appointment_date = StringField('Appointment date', validators=[Optional()])


class TestDriveForm(FlaskForm):
    store_id = HiddenField()
    location_type = SelectField('Where', choices=[
        ('in_store', 'At a CarMax store'),
        ('at_home', 'At my address'),
    ], default='in_store')
    scheduled_date = StringField('Date (YYYY-MM-DD)', validators=[DataRequired()])
    scheduled_time = SelectField('Time', choices=[
        ('10:00 AM', '10:00 AM'), ('12:00 PM', '12:00 PM'),
        ('2:00 PM', '2:00 PM'), ('4:00 PM', '4:00 PM'),
        ('6:00 PM', '6:00 PM'),
    ], default='10:00 AM')
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])


class CheckoutForm(FlaskForm):
    pickup_or_delivery = RadioField('Receive your car', choices=[
        ('pickup', 'Pick up at store'),
        ('home_delivery', 'Home delivery'),
    ], default='pickup')
    delivery_address = StringField('Delivery address',
                                   validators=[Optional(), Length(max=200)])
    payment_method = RadioField('Payment method', choices=[
        ('carmax_auto_finance', 'CarMax Auto Finance'),
        ('external_loan', 'External lender'),
        ('cash', 'Cash / cashiers check'),
    ], default='carmax_auto_finance')
    card_last4 = StringField('Card / loan last 4',
                             validators=[Optional(), Length(min=4, max=4),
                                         Regexp(r'^\d{4}$', message='4 digits')])
    apr = FloatField('APR (%)', validators=[Optional(), NumberRange(min=0, max=29.99)],
                     default=6.99)
    term_months = SelectField('Term', choices=[
        ('36', '36 months'), ('48', '48 months'), ('60', '60 months'),
        ('66', '66 months'), ('72', '72 months'),
    ], default='72')
    down_payment = FloatField('Down payment ($)',
                              validators=[Optional(), NumberRange(min=0)], default=2000)
    trade_in_appraisal_id = HiddenField()
    maxcare_plan = SelectField('MaxCare extended warranty', choices=[
        ('', 'No MaxCare'),
        ('silver', 'Silver - 36 mo / 50,000 mi ($1,495)'),
        ('gold',   'Gold - 48 mo / 75,000 mi ($1,895)'),
        ('platinum', 'Platinum - 60 mo / 100,000 mi ($2,395)'),
    ], default='')


class ReviewForm(FlaskForm):
    rating = SelectField('Rating',
                         choices=[(str(i), f'{i} stars') for i in range(5, 0, -1)],
                         default='5')
    title = StringField('Headline', validators=[DataRequired(), Length(max=120)])
    body = TextAreaField('Your review',
                         validators=[DataRequired(), Length(min=20)])
    location = StringField('Your city, state',
                           validators=[Optional(), Length(max=80)])


# =============================================================================
# Helpers
# =============================================================================

_TOKEN_RE = re.compile(r'[a-z0-9]+')
MAXCARE_PRICES = {'silver': 1495, 'gold': 1895, 'platinum': 2395}
MAXCARE_LABELS = {
    'silver':   'Silver - 36 mo / 50,000 mi',
    'gold':     'Gold - 48 mo / 75,000 mi',
    'platinum': 'Platinum - 60 mo / 100,000 mi',
}


def tokenize(s):
    if not s:
        return []
    return _TOKEN_RE.findall(s.lower())


def slugify(s):
    s = (s or '').lower().strip()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s


def score_vehicle_match(v, tokens):
    if not tokens:
        return 0
    text_high = ' '.join([v.make or '', v.model or '', str(v.year or '')]).lower()
    text_med = ' '.join([v.trim or '', v.body_style or '', v.exterior_color or '']).lower()
    text_low = ' '.join([v.interior_color or '', v.transmission or '', v.drive_type or '',
                         v.fuel_type or '', v.engine_text or '', v.description or '',
                         ' '.join(v.get_features() or [])]).lower()
    score = 0
    for t in tokens:
        if t in text_high:
            score += 5
        elif t in text_med:
            score += 3
        elif t in text_low:
            score += 1
    if v.is_featured:
        score += 0.1
    return score


def _apply_filters(q, filters):
    if not filters:
        return q
    if filters.get('make'):
        q = q.filter(Vehicle.make_slug == slugify(filters['make']))
    if filters.get('model'):
        q = q.filter(Vehicle.model_slug == slugify(filters['model']))
    if filters.get('trim'):
        q = q.filter(Vehicle.trim_slug == slugify(filters['trim']))
    if filters.get('year_min'):
        q = q.filter(Vehicle.year >= int(filters['year_min']))
    if filters.get('year_max'):
        q = q.filter(Vehicle.year <= int(filters['year_max']))
    if filters.get('year'):
        q = q.filter(Vehicle.year == int(filters['year']))
    if filters.get('price_min'):
        q = q.filter(Vehicle.price >= float(filters['price_min']))
    if filters.get('price_max'):
        q = q.filter(Vehicle.price <= float(filters['price_max']))
    if filters.get('mileage_max'):
        q = q.filter(Vehicle.mileage <= int(filters['mileage_max']))
    if filters.get('body_style'):
        q = q.filter(Vehicle.body_style.ilike(filters['body_style']))
    if filters.get('transmission'):
        q = q.filter(Vehicle.transmission.ilike(filters['transmission']))
    if filters.get('drive_type'):
        q = q.filter(Vehicle.drive_type == filters['drive_type'].upper())
    if filters.get('fuel_type'):
        q = q.filter(Vehicle.fuel_type.ilike(filters['fuel_type']))
    if filters.get('exterior_color'):
        q = q.filter(Vehicle.exterior_color.ilike(filters['exterior_color']))
    if filters.get('store_id'):
        try:
            q = q.filter(Vehicle.store_id == int(filters['store_id']))
        except (TypeError, ValueError):
            pass
    if filters.get('state'):
        q = q.join(Store).filter(Store.state == filters['state'].upper())
    if filters.get('feature'):
        feat = filters['feature']
        q = q.filter(Vehicle.features.ilike('%"' + feat + '"%'))
    if filters.get('certified'):
        q = q.filter(Vehicle.is_certified.is_(True))
    if filters.get('featured'):
        q = q.filter(Vehicle.is_featured.is_(True))
    if filters.get('new_arrival'):
        q = q.filter(Vehicle.is_new_arrival.is_(True))
    if filters.get('price_drop'):
        q = q.filter(Vehicle.is_price_drop.is_(True))
    return q


def search_vehicles(query=None, filters=None, sort='best_match',
                    page=1, per_page=24):
    q = _apply_filters(Vehicle.query, filters)
    tokens = tokenize(query or '')
    items = q.all()
    if tokens:
        scored = [(score_vehicle_match(v, tokens), v) for v in items]
        scored = [(s, v) for s, v in scored if s > 0]
        if sort == 'price_low':
            scored.sort(key=lambda x: (x[1].price, -x[0]))
        elif sort == 'price_high':
            scored.sort(key=lambda x: (-x[1].price, -x[0]))
        elif sort == 'mileage_low':
            scored.sort(key=lambda x: (x[1].mileage, -x[0]))
        elif sort == 'newest':
            scored.sort(key=lambda x: (-x[1].year, -x[0]))
        else:
            scored.sort(key=lambda x: (-x[0], x[1].price))
        items = [v for _, v in scored]
    else:
        if sort == 'price_low':
            items.sort(key=lambda v: v.price)
        elif sort == 'price_high':
            items.sort(key=lambda v: -v.price)
        elif sort == 'mileage_low':
            items.sort(key=lambda v: v.mileage)
        elif sort == 'newest':
            items.sort(key=lambda v: (-v.year, v.mileage))
        else:
            items.sort(key=lambda v: (-int(v.is_featured), v.mileage, v.price))
    total = len(items)
    start = (page - 1) * per_page
    return items[start:start + per_page], total


def estimated_payment(price, term_months=72, apr=0.0699, down=2000):
    principal = max(float(price) - float(down), 0)
    if principal <= 0:
        return 0.0
    if not apr or apr <= 0:
        return principal / max(term_months, 1)
    r = float(apr) / 12
    n = int(term_months)
    return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def estimated_payment_to_principal(monthly, term_months, apr):
    if monthly <= 0:
        return 0
    if apr <= 0:
        return monthly * term_months
    r = apr / 12
    n = int(term_months)
    return monthly * ((1 + r) ** n - 1) / (r * (1 + r) ** n)


def estimate_credit_apr(credit_tier, term_months=72):
    base = {'excellent': 5.49, 'good': 7.49,
            'fair': 11.99, 'building': 17.99}.get(credit_tier, 7.99)
    if int(term_months) >= 72:
        base += 0.5
    elif int(term_months) >= 66:
        base += 0.25
    return round(base, 2)


def make_appraisal_offer(year, make, model, trim, mileage, condition,
                         has_accidents=False):
    similar = Vehicle.query.filter(
        Vehicle.year == int(year),
        Vehicle.make.ilike(make),
        Vehicle.model.ilike(model),
    ).all()
    if similar:
        anchor = sum(v.price for v in similar) / len(similar)
    else:
        msrp_guess = 28000
        age = max(2026 - int(year), 0)
        anchor = msrp_guess * (0.82 ** age)
    expected_miles = max(1, (2026 - int(year))) * 12000
    mileage_factor = 1.0 - max(0, (int(mileage) - expected_miles)) / 200000
    mileage_factor = max(0.55, min(1.05, mileage_factor))
    cond_mult = {'excellent': 0.92, 'good': 0.85,
                 'fair': 0.74, 'poor': 0.58}.get(condition, 0.85)
    accident_mult = 0.92 if has_accidents else 1.0
    offer = anchor * cond_mult * mileage_factor * accident_mult
    return round(offer / 50) * 50


def gen_order_number():
    base = Order.query.count() + 1
    return f'CMX-2026-{base:06d}'


def _get_or_create_comparison(create=True):
    if current_user.is_authenticated:
        comp = (Comparison.query.filter_by(user_id=current_user.id)
                .order_by(Comparison.id.desc()).first())
        if not comp and create:
            comp = Comparison(user_id=current_user.id, name='My comparison')
            db.session.add(comp)
            db.session.commit()
        return comp
    sk = session.get('compare_sk')
    if not sk:
        sk = os.urandom(16).hex()
        session['compare_sk'] = sk
    comp = Comparison.query.filter_by(session_key=sk).first()
    if not comp and create:
        comp = Comparison(session_key=sk, name='My comparison')
        db.session.add(comp)
        db.session.commit()
    return comp


# =============================================================================
# Context processors / template filters
# =============================================================================

@app.context_processor
def inject_globals():
    saved_count = 0
    if current_user.is_authenticated:
        saved_count = SavedVehicle.query.filter_by(user_id=current_user.id).count()
    comp = _get_or_create_comparison(create=False)
    compare_count = (ComparisonItem.query.filter_by(comparison_id=comp.id).count()
                     if comp else 0)
    return {
        'current_user': current_user,
        'saved_count': saved_count,
        'compare_count': compare_count,
        'csrf_token': generate_csrf,
        'current_year': 2026,
        'BRAND_PHONE': '(800) 519-1511',
        'BRAND_NAME': 'CarMax',
    }


@app.template_filter('money')
def filter_money(v):
    try:
        return f'${int(round(float(v))):,}'
    except Exception:
        return '$0'


@app.template_filter('miles')
def filter_miles(v):
    try:
        return f'{int(v):,} mi'
    except Exception:
        return '-'


@app.template_filter('plus_money')
def filter_plus_money(v):
    try:
        v = int(round(float(v)))
        sign = '+' if v >= 0 else '-'
        return f'{sign}${abs(v):,}'
    except Exception:
        return ''


@app.template_filter('star_row')
def filter_star_row(rating):
    try:
        r = max(0, min(5, int(round(float(rating)))))
    except Exception:
        r = 0
    return '*' * r + '.' * (5 - r)


# =============================================================================
# Routes - home, search, browse
# =============================================================================

@app.route('/')
def index():
    featured = (Vehicle.query.filter_by(is_featured=True)
                .order_by(Vehicle.price.asc()).limit(8).all())
    new_arrivals = (Vehicle.query.filter_by(is_new_arrival=True)
                    .order_by(Vehicle.added_at.desc()).limit(8).all())
    popular_makes = (db.session.query(Vehicle.make, Vehicle.make_slug,
                                      func.count(Vehicle.id).label('n'))
                     .group_by(Vehicle.make, Vehicle.make_slug)
                     .order_by(func.count(Vehicle.id).desc()).limit(12).all())
    body_styles = (db.session.query(Vehicle.body_style,
                                    func.count(Vehicle.id).label('n'))
                   .group_by(Vehicle.body_style)
                   .order_by(func.count(Vehicle.id).desc()).all())
    article_strip = (Article.query.filter_by(is_featured=True)
                     .order_by(Article.published_at.desc()).limit(3).all())
    return render_template('index.html',
                           featured=featured,
                           new_arrivals=new_arrivals,
                           popular_makes=popular_makes,
                           body_styles=body_styles,
                           article_strip=article_strip)


def _filters_from_args():
    a = request.args
    return {
        'make': a.get('make') or '',
        'model': a.get('model') or '',
        'trim': a.get('trim') or '',
        'year': a.get('year') or '',
        'year_min': a.get('year_min') or '',
        'year_max': a.get('year_max') or '',
        'price_min': a.get('price_min') or '',
        'price_max': a.get('price_max') or '',
        'mileage_max': a.get('mileage_max') or '',
        'body_style': a.get('body_style') or '',
        'transmission': a.get('transmission') or '',
        'drive_type': a.get('drive_type') or '',
        'fuel_type': a.get('fuel_type') or '',
        'exterior_color': a.get('exterior_color') or '',
        'store_id': a.get('store_id') or '',
        'state': a.get('state') or '',
        'feature': a.get('feature') or '',
        'certified': a.get('certified') in ('1', 'true', 'on'),
        'featured': a.get('featured') in ('1', 'true', 'on'),
        'new_arrival': a.get('new_arrival') in ('1', 'true', 'on'),
        'price_drop': a.get('price_drop') in ('1', 'true', 'on'),
    }


def _facets(filters_query):
    base = _apply_filters(Vehicle.query, filters_query)
    res = {}
    sub = base.with_entities(Vehicle.id)
    res['makes'] = (db.session.query(Vehicle.make, Vehicle.make_slug,
                                     func.count(Vehicle.id))
                    .filter(Vehicle.id.in_(sub))
                    .group_by(Vehicle.make, Vehicle.make_slug)
                    .order_by(func.count(Vehicle.id).desc()).limit(20).all())
    res['body_styles'] = (db.session.query(Vehicle.body_style,
                                           func.count(Vehicle.id))
                          .filter(Vehicle.id.in_(sub))
                          .group_by(Vehicle.body_style)
                          .order_by(func.count(Vehicle.id).desc()).all())
    res['fuel_types'] = (db.session.query(Vehicle.fuel_type,
                                          func.count(Vehicle.id))
                         .filter(Vehicle.id.in_(sub))
                         .group_by(Vehicle.fuel_type)
                         .order_by(func.count(Vehicle.id).desc()).all())
    res['drive_types'] = (db.session.query(Vehicle.drive_type,
                                           func.count(Vehicle.id))
                          .filter(Vehicle.id.in_(sub))
                          .group_by(Vehicle.drive_type)
                          .order_by(func.count(Vehicle.id).desc()).all())
    return res


def _do_search(scope_label, extra_filters=None):
    q = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'best_match')
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1
    filters = _filters_from_args()
    if extra_filters:
        filters.update(extra_filters)
    items, total = search_vehicles(query=q, filters=filters, sort=sort,
                                   page=page, per_page=24)
    facets = _facets(filters)
    return render_template('search.html',
                           items=items, total=total, page=page, per_page=24,
                           pages=(total + 23) // 24,
                           query=q, sort=sort, filters=filters,
                           facets=facets, scope_label=scope_label)


@app.route('/cars')
def cars_index():
    return _do_search('All inventory')


@app.route('/cars/<make>')
def cars_make(make):
    label = f'Used {make.replace("-", " ").title()} for sale'
    return _do_search(label, extra_filters={'make': make})


@app.route('/cars/<make>/<model>')
def cars_model(make, model):
    label = (f'Used {make.replace("-", " ").title()} '
             f'{model.replace("-", " ").title()} for sale')
    return _do_search(label, extra_filters={'make': make, 'model': model})


@app.route('/cars/<make>/<model>/<int:year>')
def cars_model_year(make, model, year):
    label = (f'Used {year} {make.replace("-", " ").title()} '
             f'{model.replace("-", " ").title()} for sale')
    return _do_search(label,
                      extra_filters={'make': make, 'model': model,
                                     'year': year})


@app.route('/cars/<make>/<model>/<trim>')
def cars_model_trim(make, model, trim):
    label = (f'Used {make.replace("-", " ").title()} '
             f'{model.replace("-", " ").title()} '
             f'{trim.replace("-", " ").title()} for sale')
    return _do_search(label,
                      extra_filters={'make': make, 'model': model,
                                     'trim': trim})


@app.route('/cars/<make>/<model>/<trim>/<int:year>')
def cars_model_trim_year(make, model, trim, year):
    label = (f'Used {year} {make.replace("-", " ").title()} '
             f'{model.replace("-", " ").title()} '
             f'{trim.replace("-", " ").title()} for sale')
    return _do_search(label,
                      extra_filters={'make': make, 'model': model,
                                     'trim': trim, 'year': year})


@app.route('/search')
def search():
    return redirect(url_for('cars_index', **request.args))


# =============================================================================
# Vehicle detail
# =============================================================================

@app.route('/vehicle/<slug>')
def vehicle_detail(slug):
    v = Vehicle.query.filter_by(slug=slug).first_or_404()
    similar = (Vehicle.query
               .filter(Vehicle.id != v.id, Vehicle.model_slug == v.model_slug)
               .order_by(func.abs(Vehicle.price - v.price)).limit(6).all())
    reviews = (Review.query.filter_by(make_slug=v.make_slug,
                                      model_slug=v.model_slug, year=v.year)
               .order_by(Review.created_at.desc()).limit(6).all())
    is_saved = False
    if current_user.is_authenticated:
        is_saved = (SavedVehicle.query
                    .filter_by(user_id=current_user.id, vehicle_id=v.id)
                    .first() is not None)
    return render_template('vehicle_detail.html',
                           vehicle=v, similar=similar, reviews=reviews,
                           is_saved=is_saved,
                           default_term=72, default_apr=0.0699,
                           default_down=2000)


@app.route('/vehicle/id/<int:vid>')
def vehicle_detail_by_id(vid):
    v = db.session.get(Vehicle, vid)
    if not v:
        abort(404)
    return redirect(url_for('vehicle_detail', slug=v.slug))


# =============================================================================
# Research
# =============================================================================

@app.route('/research')
def research_index():
    popular = (db.session.query(Vehicle.make, Vehicle.make_slug,
                                Vehicle.model, Vehicle.model_slug,
                                func.count(Vehicle.id).label('n'))
               .group_by(Vehicle.make, Vehicle.make_slug,
                         Vehicle.model, Vehicle.model_slug)
               .order_by(func.count(Vehicle.id).desc()).limit(24).all())
    makes = (db.session.query(Vehicle.make, Vehicle.make_slug,
                              func.count(Vehicle.id).label('n'))
             .group_by(Vehicle.make, Vehicle.make_slug)
             .order_by(Vehicle.make.asc()).all())
    return render_template('research_index.html', popular=popular, makes=makes)


@app.route('/research/<make>')
def research_make(make):
    make_slug = slugify(make)
    models = (db.session.query(Vehicle.make, Vehicle.make_slug,
                               Vehicle.model, Vehicle.model_slug,
                               func.count(Vehicle.id).label('n'))
              .filter(Vehicle.make_slug == make_slug)
              .group_by(Vehicle.make, Vehicle.make_slug,
                        Vehicle.model, Vehicle.model_slug)
              .order_by(Vehicle.model.asc()).all())
    if not models:
        abort(404)
    return render_template('research_make.html',
                           make_name=models[0].make, make_slug=make_slug,
                           models=models)


@app.route('/research/<make>/<model>')
def research_model(make, model):
    make_slug, model_slug = slugify(make), slugify(model)
    years = (db.session.query(Vehicle.year, func.count(Vehicle.id))
             .filter(Vehicle.make_slug == make_slug,
                     Vehicle.model_slug == model_slug)
             .group_by(Vehicle.year)
             .order_by(Vehicle.year.desc()).all())
    if not years:
        abort(404)
    sample = (Vehicle.query
              .filter(Vehicle.make_slug == make_slug,
                      Vehicle.model_slug == model_slug)
              .order_by(Vehicle.year.desc(), Vehicle.price.asc()).first())
    return render_template('research_model.html',
                           make=sample.make, model=sample.model,
                           make_slug=make_slug, model_slug=model_slug,
                           years=years, sample=sample)


@app.route('/research/<make>/<model>/<int:year>')
def research_model_year(make, model, year):
    make_slug, model_slug = slugify(make), slugify(model)
    vehicles = (Vehicle.query
                .filter(Vehicle.make_slug == make_slug,
                        Vehicle.model_slug == model_slug,
                        Vehicle.year == year).all())
    if not vehicles:
        abort(404)
    v0 = vehicles[0]
    trims = sorted({(x.trim or '-', x.trim_slug or '') for x in vehicles if x.trim})
    avg_price = sum(x.price for x in vehicles) / len(vehicles)
    min_price = min(x.price for x in vehicles)
    max_price = max(x.price for x in vehicles)
    reviews = (Review.query
               .filter_by(make_slug=make_slug, model_slug=model_slug, year=year)
               .order_by(Review.created_at.desc()).limit(8).all())
    avg_rating = (sum(r.rating for r in reviews) / len(reviews)) if reviews else v0.customer_rating
    return render_template('research_model_year.html',
                           make=v0.make, model=v0.model, year=year,
                           make_slug=make_slug, model_slug=model_slug,
                           vehicles=vehicles, trims=trims,
                           avg_price=avg_price, min_price=min_price,
                           max_price=max_price, sample=v0,
                           reviews=reviews, avg_rating=avg_rating,
                           review_count=len(reviews))


@app.route('/research/car-comparison/<makemodelyear>')
def research_comparison(makemodelyear):
    return redirect(url_for('compare_view'))


# =============================================================================
# Customer reviews
# =============================================================================

@app.route('/reviews/<make>/<model>/<int:year>', methods=['GET', 'POST'])
def reviews_page(make, model, year):
    make_slug, model_slug = slugify(make), slugify(model)
    exists = Vehicle.query.filter(Vehicle.make_slug == make_slug,
                                  Vehicle.model_slug == model_slug,
                                  Vehicle.year == year).first()
    if not exists:
        abort(404)
    form = ReviewForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('Please sign in to leave a review.', 'info')
            return redirect(url_for('login', next=request.path))
        r = Review(user_id=current_user.id,
                   make_slug=make_slug, model_slug=model_slug, year=year,
                   rating=int(form.rating.data),
                   title=form.title.data.strip(),
                   body=form.body.data.strip(),
                   location=form.location.data.strip(),
                   reviewer_name=current_user.full_name)
        db.session.add(r)
        db.session.commit()
        flash('Thanks - your review has been posted.', 'success')
        return redirect(url_for('reviews_page', make=make, model=model, year=year))
    reviews = (Review.query
               .filter_by(make_slug=make_slug, model_slug=model_slug, year=year)
               .order_by(Review.created_at.desc()).all())
    avg = (sum(r.rating for r in reviews) / len(reviews)) if reviews else 0.0
    return render_template('reviews.html',
                           make=exists.make, model=exists.model, year=year,
                           make_slug=make_slug, model_slug=model_slug,
                           reviews=reviews, avg_rating=avg, form=form)


# =============================================================================
# Compare
# =============================================================================

@app.route('/compare')
def compare_view():
    comp = _get_or_create_comparison(create=False)
    items = []
    if comp:
        items = [it.vehicle for it in
                 ComparisonItem.query.filter_by(comparison_id=comp.id)
                 .order_by(ComparisonItem.added_at.asc()).all()]
    return render_template('compare.html', items=items)


@app.route('/compare/add/<int:vehicle_id>', methods=['POST'])
def compare_add(vehicle_id):
    v = db.session.get(Vehicle, vehicle_id)
    if not v:
        abort(404)
    comp = _get_or_create_comparison(create=True)
    existing = ComparisonItem.query.filter_by(comparison_id=comp.id,
                                              vehicle_id=v.id).first()
    if existing:
        flash(f'{v.short_title} is already in your comparison.', 'info')
    else:
        cnt = ComparisonItem.query.filter_by(comparison_id=comp.id).count()
        if cnt >= 4:
            flash('You can compare up to 4 vehicles at a time.', 'warning')
        else:
            db.session.add(ComparisonItem(comparison_id=comp.id,
                                          vehicle_id=v.id))
            db.session.commit()
            flash(f'Added {v.short_title} to compare.', 'success')
    return redirect(request.referrer or url_for('compare_view'))


@app.route('/compare/remove/<int:vehicle_id>', methods=['POST'])
def compare_remove(vehicle_id):
    comp = _get_or_create_comparison(create=False)
    if comp:
        ComparisonItem.query.filter_by(comparison_id=comp.id,
                                       vehicle_id=vehicle_id).delete()
        db.session.commit()
    return redirect(request.referrer or url_for('compare_view'))


@app.route('/compare/clear', methods=['POST'])
def compare_clear():
    comp = _get_or_create_comparison(create=False)
    if comp:
        ComparisonItem.query.filter_by(comparison_id=comp.id).delete()
        db.session.commit()
    return redirect(url_for('compare_view'))


# =============================================================================
# Saved vehicles
# =============================================================================

@app.route('/saved')
@login_required
def saved_view():
    rows = (SavedVehicle.query.filter_by(user_id=current_user.id)
            .order_by(SavedVehicle.saved_at.desc()).all())
    return render_template('saved.html', rows=rows)


@app.route('/saved/add/<int:vehicle_id>', methods=['POST'])
@login_required
def saved_add(vehicle_id):
    v = db.session.get(Vehicle, vehicle_id)
    if not v:
        abort(404)
    existing = SavedVehicle.query.filter_by(user_id=current_user.id,
                                            vehicle_id=v.id).first()
    if not existing:
        db.session.add(SavedVehicle(user_id=current_user.id, vehicle_id=v.id))
        db.session.commit()
        flash(f'Saved {v.short_title}.', 'success')
    return redirect(request.referrer or url_for('vehicle_detail', slug=v.slug))


@app.route('/saved/remove/<int:vehicle_id>', methods=['POST'])
@login_required
def saved_remove(vehicle_id):
    SavedVehicle.query.filter_by(user_id=current_user.id,
                                 vehicle_id=vehicle_id).delete()
    db.session.commit()
    flash('Removed from saved.', 'info')
    return redirect(request.referrer or url_for('saved_view'))


@app.route('/saved/toggle/<int:vehicle_id>', methods=['POST'])
@login_required
def saved_toggle(vehicle_id):
    v = db.session.get(Vehicle, vehicle_id)
    if not v:
        abort(404)
    row = SavedVehicle.query.filter_by(user_id=current_user.id,
                                       vehicle_id=v.id).first()
    if row:
        db.session.delete(row)
        msg = 'Removed from saved.'
    else:
        db.session.add(SavedVehicle(user_id=current_user.id, vehicle_id=v.id))
        msg = f'Saved {v.short_title}.'
    db.session.commit()
    flash(msg, 'success')
    return redirect(request.referrer or url_for('vehicle_detail', slug=v.slug))


# =============================================================================
# Stores
# =============================================================================

@app.route('/stores')
def stores_index():
    states = (db.session.query(Store.state, func.count(Store.id).label('n'))
              .group_by(Store.state)
              .order_by(Store.state.asc()).all())
    return render_template('stores.html', states=states)


@app.route('/stores/<state_code>')
def stores_state(state_code):
    sc = state_code.upper()
    stores = Store.query.filter_by(state=sc).order_by(Store.city.asc()).all()
    if not stores:
        abort(404)
    return render_template('stores_state.html', state=sc, stores=stores)


@app.route('/store/<slug>')
def store_detail(slug):
    s = Store.query.filter_by(slug=slug).first_or_404()
    inv_count = Vehicle.query.filter_by(store_id=s.id).count()
    inventory = (Vehicle.query.filter_by(store_id=s.id)
                 .order_by(Vehicle.price.asc()).limit(12).all())
    return render_template('store_detail.html',
                           store=s, inventory=inventory, inv_count=inv_count)


# =============================================================================
# Sell-my-car / value
# =============================================================================

@app.route('/value')
def value_index():
    makes = (db.session.query(Vehicle.make, Vehicle.make_slug)
             .group_by(Vehicle.make, Vehicle.make_slug)
             .order_by(Vehicle.make.asc()).all())
    return render_template('value.html', makes=makes)


@app.route('/value/<make>/<model>')
def value_model(make, model):
    make_slug, model_slug = slugify(make), slugify(model)
    sample = (Vehicle.query
              .filter(Vehicle.make_slug == make_slug,
                      Vehicle.model_slug == model_slug)
              .order_by(Vehicle.year.desc()).first())
    if not sample:
        abort(404)
    rows = (db.session.query(Vehicle.year,
                             func.avg(Vehicle.price),
                             func.min(Vehicle.price),
                             func.max(Vehicle.price),
                             func.count(Vehicle.id))
            .filter(Vehicle.make_slug == make_slug,
                    Vehicle.model_slug == model_slug)
            .group_by(Vehicle.year)
            .order_by(Vehicle.year.desc()).all())
    return render_template('value_model.html',
                           make=sample.make, model=sample.model, rows=rows)


@app.route('/value/<make>/<model>/<int:year>')
def value_year(make, model, year):
    make_slug, model_slug = slugify(make), slugify(model)
    matches = (Vehicle.query
               .filter(Vehicle.make_slug == make_slug,
                       Vehicle.model_slug == model_slug,
                       Vehicle.year == year).all())
    if not matches:
        abort(404)
    avg = sum(v.price for v in matches) / len(matches)
    return render_template('value_year.html',
                           make=matches[0].make, model=matches[0].model,
                           year=year, avg_price=avg, count=len(matches),
                           min_price=min(v.price for v in matches),
                           max_price=max(v.price for v in matches))


@app.route('/sell-my-car', methods=['GET', 'POST'])
def sell_my_car():
    form = SellMyCarForm()
    if current_user.is_authenticated and not form.contact_email.data:
        form.contact_email.data = current_user.email
        form.contact_phone.data = current_user.phone or ''
        form.zip_code.data = current_user.zip_code or ''
    if form.validate_on_submit():
        offer = make_appraisal_offer(form.year.data, form.make.data,
                                     form.model.data, form.trim.data or '',
                                     form.mileage.data, form.condition.data,
                                     form.has_accidents.data)
        a = Appraisal(
            user_id=current_user.id if current_user.is_authenticated else None,
            year=form.year.data,
            make=form.make.data.strip(),
            model=form.model.data.strip(),
            trim=(form.trim.data or '').strip(),
            mileage=form.mileage.data,
            condition=form.condition.data,
            exterior_color=(form.exterior_color.data or '').strip(),
            license_plate=(form.license_plate.data or '').strip().upper(),
            license_state=(form.license_state.data or '').strip().upper(),
            vin=(form.vin.data or '').strip().upper(),
            zip_code=(form.zip_code.data or '').strip(),
            has_accidents=form.has_accidents.data,
            owner_count=form.owner_count.data or 1,
            contact_email=(form.contact_email.data or '').strip(),
            contact_phone=(form.contact_phone.data or '').strip(),
            offer_amount=offer,
            offer_valid_until=date(2026, 5, 14) + timedelta(days=7),
            status='active',
        )
        db.session.add(a)
        db.session.commit()
        return redirect(url_for('sell_offer', appraisal_id=a.id))
    return render_template('sell_my_car.html', form=form)


@app.route('/sell-my-car/offer/<int:appraisal_id>')
def sell_offer(appraisal_id):
    a = db.session.get(Appraisal, appraisal_id)
    if not a:
        abort(404)
    return render_template('sell_offer.html', appraisal=a)


@app.route('/sell-my-car/offer/<int:appraisal_id>/redeem', methods=['POST'])
@login_required
def sell_offer_redeem(appraisal_id):
    a = db.session.get(Appraisal, appraisal_id)
    if not a:
        abort(404)
    if a.user_id and a.user_id != current_user.id:
        abort(403)
    a.user_id = current_user.id
    a.status = 'redeemed'
    db.session.commit()
    flash(f'We scheduled redemption for your ${int(a.offer_amount):,} '
          f'offer on the {a.year} {a.make} {a.model}.', 'success')
    return redirect(url_for('account_appraisals'))


# =============================================================================
# Financing / pre-qual
# =============================================================================

@app.route('/car-financing')
def financing():
    return render_template('financing.html')


@app.route('/pre-qual/app', methods=['GET', 'POST'])
def pre_qual():
    form = PreQualForm()
    if current_user.is_authenticated:
        if not form.annual_income.data:
            form.annual_income.data = current_user.annual_income or 60000
        if not form.employment_status.data and current_user.employment_status:
            form.employment_status.data = current_user.employment_status
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            session['pending_prequal'] = {
                'annual_income': form.annual_income.data,
                'employment_status': form.employment_status.data,
                'monthly_payment_max': form.monthly_payment_max.data,
                'down_payment': form.down_payment.data or 2000,
                'term_months': int(form.term_months.data),
                'credit_tier': form.credit_tier.data,
            }
            flash('Sign in to save your pre-qualification.', 'info')
            return redirect(url_for('login', next=url_for('pre_qual')))
        apr = estimate_credit_apr(form.credit_tier.data,
                                  int(form.term_months.data))
        pq = FinancePreQual(
            user_id=current_user.id,
            annual_income=form.annual_income.data,
            employment_status=form.employment_status.data,
            monthly_payment_max=form.monthly_payment_max.data,
            down_payment=form.down_payment.data or 2000,
            term_months=int(form.term_months.data),
            estimated_apr=apr,
            credit_tier=form.credit_tier.data,
            expires_at=date(2026, 5, 14) + timedelta(days=30),
        )
        db.session.add(pq)
        current_user.pre_qual_active = True
        current_user.pre_qual_monthly_max = form.monthly_payment_max.data
        current_user.pre_qual_term_months = int(form.term_months.data)
        current_user.pre_qual_apr = apr
        current_user.pre_qual_down_payment = form.down_payment.data or 2000
        current_user.pre_qual_credit_tier = form.credit_tier.data
        current_user.pre_qual_expires_at = pq.expires_at
        current_user.annual_income = form.annual_income.data
        current_user.employment_status = form.employment_status.data
        db.session.commit()
        return redirect(url_for('pre_qual_result'))
    return render_template('pre_qual_form.html', form=form)


@app.route('/pre-qual/result')
@login_required
def pre_qual_result():
    if not current_user.pre_qual_active:
        return redirect(url_for('pre_qual'))
    max_principal = estimated_payment_to_principal(
        current_user.pre_qual_monthly_max,
        current_user.pre_qual_term_months,
        current_user.pre_qual_apr / 100.0,
    ) + current_user.pre_qual_down_payment
    affordable = (Vehicle.query
                  .filter(Vehicle.price <= max_principal)
                  .order_by(Vehicle.price.desc()).limit(12).all())
    return render_template('pre_qual_result.html',
                           max_principal=max_principal, affordable=affordable)


# =============================================================================
# Reserve & test drive
# =============================================================================

@app.route('/vehicle/<int:vehicle_id>/reserve', methods=['GET', 'POST'])
@login_required
def reserve(vehicle_id):
    v = db.session.get(Vehicle, vehicle_id)
    if not v:
        abort(404)
    form = ReserveForm()
    if request.method == 'POST' and form.validate_on_submit():
        appt = form.appointment_date.data
        try:
            appt_date = (datetime.strptime(appt, '%Y-%m-%d').date()
                         if appt else (date(2026, 5, 14) + timedelta(days=3)))
        except ValueError:
            appt_date = date(2026, 5, 14) + timedelta(days=3)
        r = Reservation(
            user_id=current_user.id, vehicle_id=v.id, store_id=v.store_id,
            appointment_date=appt_date,
            expires_at=date(2026, 5, 14) + timedelta(days=7),
            transfer_required=False, transfer_fee=v.transfer_fee or 0,
            status='active',
        )
        db.session.add(r)
        db.session.commit()
        flash(f'Reserved the {v.short_title} for 7 days. '
              f'Appointment: {appt_date}.', 'success')
        return redirect(url_for('account_reservations'))
    return render_template('reserve.html', vehicle=v, form=form)


@app.route('/vehicle/<int:vehicle_id>/test-drive', methods=['GET', 'POST'])
@login_required
def test_drive(vehicle_id):
    v = db.session.get(Vehicle, vehicle_id)
    if not v:
        abort(404)
    form = TestDriveForm()
    if request.method == 'POST' and form.validate_on_submit():
        try:
            d = datetime.strptime(form.scheduled_date.data, '%Y-%m-%d').date()
        except ValueError:
            d = date(2026, 5, 14) + timedelta(days=3)
        td = TestDrive(
            user_id=current_user.id, vehicle_id=v.id, store_id=v.store_id,
            location_type=form.location_type.data,
            scheduled_date=d, scheduled_time=form.scheduled_time.data,
            notes=form.notes.data or '', status='confirmed',
        )
        db.session.add(td)
        db.session.commit()
        flash(f'Test drive booked for {d} at {form.scheduled_time.data}.',
              'success')
        return redirect(url_for('account_test_drives'))
    return render_template('test_drive.html', vehicle=v, form=form)


# =============================================================================
# Checkout
# =============================================================================

@app.route('/vehicle/<int:vehicle_id>/checkout', methods=['GET', 'POST'])
@login_required
def checkout(vehicle_id):
    v = db.session.get(Vehicle, vehicle_id)
    if not v:
        abort(404)
    form = CheckoutForm()
    if current_user.pre_qual_active and request.method == 'GET':
        form.down_payment.data = current_user.pre_qual_down_payment
        form.apr.data = current_user.pre_qual_apr
        form.term_months.data = str(current_user.pre_qual_term_months)
    trade_options = (Appraisal.query
                     .filter_by(user_id=current_user.id, status='active')
                     .order_by(Appraisal.created_at.desc()).all())
    if form.validate_on_submit():
        subtotal = v.price
        transfer_fee = v.transfer_fee or 0
        tax = subtotal * 0.06
        title_fee = 99
        registration_fee = 55
        maxcare_price = MAXCARE_PRICES.get(form.maxcare_plan.data, 0) or 0
        trade_value = 0
        trade_appraisal_id = None
        if form.trade_in_appraisal_id.data:
            try:
                a = db.session.get(Appraisal, int(form.trade_in_appraisal_id.data))
                if a and a.user_id == current_user.id and a.status == 'active':
                    trade_value = a.offer_amount
                    trade_appraisal_id = a.id
                    a.status = 'redeemed'
            except (TypeError, ValueError):
                pass
        total = (subtotal + transfer_fee + tax + title_fee + registration_fee
                 + maxcare_price - trade_value)
        down = form.down_payment.data or 0
        if form.payment_method.data == 'cash':
            monthly = 0
        else:
            apr = (form.apr.data or 6.99) / 100.0
            monthly = estimated_payment(total - down,
                                        term_months=int(form.term_months.data),
                                        apr=apr, down=0)
        order = Order(
            order_number=gen_order_number(),
            user_id=current_user.id,
            vehicle_id=v.id, store_id=v.store_id,
            subtotal=subtotal, transfer_fee=transfer_fee, tax=tax,
            title_fee=title_fee, registration_fee=registration_fee,
            total=total,
            maxcare_plan=form.maxcare_plan.data or '',
            maxcare_price=maxcare_price,
            payment_method=form.payment_method.data,
            payment_last4=form.card_last4.data or '',
            payment_apr=form.apr.data or 0,
            payment_term_months=int(form.term_months.data),
            monthly_payment=monthly,
            down_payment=down,
            trade_in_appraisal_id=trade_appraisal_id,
            trade_in_value=trade_value,
            pickup_or_delivery=form.pickup_or_delivery.data,
            delivery_address=form.delivery_address.data or '',
            pickup_date=date(2026, 5, 14) + timedelta(days=3),
            status='processing',
        )
        db.session.add(order)
        db.session.commit()
        flash(f'Order placed: {order.order_number}', 'success')
        return redirect(url_for('order_confirmation',
                                order_number=order.order_number))
    preview = {
        'subtotal': v.price,
        'transfer_fee': v.transfer_fee or 0,
        'tax_estimate': v.price * 0.06,
        'title_fee': 99,
        'registration_fee': 55,
    }
    preview['total_before_warranty'] = sum([
        preview['subtotal'], preview['transfer_fee'], preview['tax_estimate'],
        preview['title_fee'], preview['registration_fee'],
    ])
    return render_template('checkout.html', vehicle=v, form=form,
                           preview=preview, trade_options=trade_options,
                           maxcare_prices=MAXCARE_PRICES,
                           maxcare_labels=MAXCARE_LABELS)


@app.route('/order/<order_number>')
@login_required
def order_confirmation(order_number):
    o = Order.query.filter_by(order_number=order_number,
                              user_id=current_user.id).first()
    if not o:
        abort(404)
    return render_template('order_confirmation.html', order=o)


# =============================================================================
# Account
# =============================================================================

@app.route('/account')
@login_required
def account():
    saved_n = SavedVehicle.query.filter_by(user_id=current_user.id).count()
    reservations_n = Reservation.query.filter_by(
        user_id=current_user.id, status='active').count()
    test_drives_n = TestDrive.query.filter_by(
        user_id=current_user.id, status='confirmed').count()
    appraisals_n = Appraisal.query.filter_by(
        user_id=current_user.id, status='active').count()
    orders_n = Order.query.filter_by(user_id=current_user.id).count()
    recent_saved = (SavedVehicle.query.filter_by(user_id=current_user.id)
                    .order_by(SavedVehicle.saved_at.desc()).limit(4).all())
    return render_template('account.html',
                           saved_n=saved_n,
                           reservations_n=reservations_n,
                           test_drives_n=test_drives_n,
                           appraisals_n=appraisals_n,
                           orders_n=orders_n,
                           recent_saved=recent_saved)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    form = AccountEditForm(obj=current_user)
    if form.validate_on_submit():
        for field in ['first_name', 'last_name', 'phone', 'address_line1',
                      'address_line2', 'city', 'state', 'zip_code']:
            setattr(current_user, field, getattr(form, field).data or '')
        current_user.state = (current_user.state or '').upper()[:2]
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('account'))
    return render_template('account_edit.html', form=form)


@app.route('/account/change-password', methods=['GET', 'POST'])
@login_required
def account_change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Password updated.', 'success')
            return redirect(url_for('account'))
    return render_template('account_change_password.html', form=form)


@app.route('/account/orders')
@login_required
def account_orders():
    orders = (Order.query.filter_by(user_id=current_user.id)
              .order_by(Order.created_at.desc()).all())
    return render_template('account_orders.html', orders=orders)


@app.route('/account/reservations')
@login_required
def account_reservations():
    rows = (Reservation.query.filter_by(user_id=current_user.id)
            .order_by(Reservation.created_at.desc()).all())
    return render_template('account_reservations.html', rows=rows)


@app.route('/account/test-drives')
@login_required
def account_test_drives():
    rows = (TestDrive.query.filter_by(user_id=current_user.id)
            .order_by(TestDrive.scheduled_date.desc()).all())
    return render_template('account_test_drives.html', rows=rows)


@app.route('/account/appraisals')
@login_required
def account_appraisals():
    rows = (Appraisal.query.filter_by(user_id=current_user.id)
            .order_by(Appraisal.created_at.desc()).all())
    return render_template('account_appraisals.html', rows=rows)


@app.route('/account/reservations/<int:reservation_id>/cancel', methods=['POST'])
@login_required
def reservation_cancel(reservation_id):
    r = db.session.get(Reservation, reservation_id)
    if not r or r.user_id != current_user.id:
        abort(404)
    r.status = 'cancelled'
    db.session.commit()
    flash('Reservation cancelled.', 'info')
    return redirect(url_for('account_reservations'))


@app.route('/account/test-drives/<int:td_id>/cancel', methods=['POST'])
@login_required
def test_drive_cancel(td_id):
    r = db.session.get(TestDrive, td_id)
    if not r or r.user_id != current_user.id:
        abort(404)
    r.status = 'cancelled'
    db.session.commit()
    flash('Test drive cancelled.', 'info')
    return redirect(url_for('account_test_drives'))


# =============================================================================
# Articles & FAQ & MaxCare
# =============================================================================

@app.route('/articles')
def articles_index():
    cat = request.args.get('category', '').strip()
    q = Article.query
    if cat:
        q = q.filter(Article.category == cat)
    posts = q.order_by(Article.published_at.desc()).all()
    cats = (db.session.query(Article.category, func.count(Article.id))
            .group_by(Article.category).all())
    return render_template('articles_index.html',
                           posts=posts, cats=cats, current_cat=cat)


@app.route('/articles/<slug>')
def article_detail(slug):
    a = Article.query.filter_by(slug=slug).first_or_404()
    related = (Article.query.filter(Article.category == a.category,
                                    Article.id != a.id)
               .order_by(Article.published_at.desc()).limit(4).all())
    return render_template('article_detail.html', article=a, related=related)


FAQ_DATA = {
    'finding-a-car': [
        ('how-can-i-find-out-when-cars-i-like-are-added-to-carmax-inventory',
         'How can I find out when cars I like are added to inventory?',
         'Save vehicles you like to your CarMax account. We will email you '
         'when similar matches arrive, and you can also adjust your search '
         'to email alerts on new listings that meet your criteria.'),
        ('how-many-vehicles-does-carmax-have',
         'How many vehicles does CarMax have?',
         'CarMax maintains a nationwide inventory of approximately 50,000 '
         'used vehicles across more than 240 stores.'),
        ('what-is-carmax-certified',
         'What is CarMax Certified?',
         'Every car we sell is CarMax Certified - it has been through our '
         '125+ point inspection, has no flood or frame damage, and has no '
         'salvage history.'),
    ],
    'selling-a-car': [
        ('can-i-get-both-an-online-and-in-store-appraisal',
         'Can I get both an online and in-store appraisal?',
         'Yes - you can start your appraisal online with an instant offer '
         'in under two minutes, then bring your car to a store for in-person '
         'verification. The price is the same whether you sell outright or '
         'trade in.'),
        ('how-long-is-my-appraisal-offer-good-for',
         'How long is my appraisal offer good for?',
         'Your written offer is valid for 7 days from the day we make it.'),
    ],
    'financing': [
        ('what-is-pre-qualification',
         'What is pre-qualification?',
         'Pre-qualification is a soft credit inquiry that gives you '
         'personalized monthly payment terms without impacting your credit '
         'score. It takes about 5 minutes and is valid for 30 days.'),
        ('does-carmax-finance-first-time-buyers',
         'Does CarMax finance first-time buyers?',
         'Yes, CarMax has finance sources to accommodate most credit '
         'profiles, including first-time buyers.'),
    ],
    'warranty-and-returns': [
        ('what-is-the-30-day-return-policy',
         'What is the 30-day return policy?',
         'You may return your vehicle within 10 days for any reason for a '
         'full refund, and every vehicle comes with a 30-day limited '
         'warranty (60-day in CT/MN/RI, 90-day in MA/NJ/NY).'),
        ('what-does-maxcare-cover',
         'What does MaxCare cover?',
         'MaxCare extended service plans cover repairs, with deductible-per-'
         'visit pricing. Plans run up to 60 months and include 24/7 roadside '
         'assistance, rental reimbursement up to $40/day, and nationwide '
         'coverage in the U.S. and Canada.'),
    ],
}


@app.route('/faq')
def faq_index():
    return render_template('faq.html', categories=FAQ_DATA)


@app.route('/faq/<category>')
def faq_category(category):
    items = FAQ_DATA.get(category)
    if not items:
        abort(404)
    return render_template('faq_category.html',
                           category=category, items=items)


@app.route('/faq/<category>/<slug>')
def faq_detail(category, slug):
    items = FAQ_DATA.get(category) or []
    found = next(((s, q, a) for (s, q, a) in items if s == slug), None)
    if not found:
        abort(404)
    return render_template('faq_detail.html',
                           category=category, q_slug=found[0],
                           question=found[1], answer=found[2])


@app.route('/car-buying-process/maxcare-service-plans')
def maxcare_plans():
    return render_template('maxcare.html',
                           prices=MAXCARE_PRICES,
                           labels=MAXCARE_LABELS)


# =============================================================================
# Auth
# =============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    form = LoginForm()
    next_url = request.args.get('next') or url_for('account')
    if form.validate_on_submit():
        u = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if u and u.check_password(form.password.data):
            login_user(u, remember=form.remember.data)
            flash(f'Welcome back, {u.full_name}!', 'success')
            return redirect(next_url)
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form, next_url=next_url)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash('That email is already registered. Please sign in.', 'warning')
            return redirect(url_for('login'))
        u = User(email=email,
                 first_name=form.first_name.data.strip(),
                 last_name=form.last_name.data.strip(),
                 phone=(form.phone.data or '').strip(),
                 zip_code=(form.zip_code.data or '').strip())
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash('Welcome to CarMax!', 'success')
        return redirect(url_for('account'))
    return render_template('register.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('index'))


# =============================================================================
# Health & errors
# =============================================================================

@app.route('/_health')
def health():
    return jsonify({'ok': True, 'site': 'carmax',
                    'vehicles': Vehicle.query.count(),
                    'stores': Store.query.count(),
                    'users': User.query.count()})


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# =============================================================================
# Bootstrap
# =============================================================================

# Map this module under the name 'app' so seed_data's deferred
# 'from app import ...' returns this same instance (not a fresh re-import
# under __name__ == '__main__').
import sys as _sys
_sys.modules.setdefault('app', _sys.modules[__name__])

from seed_data import seed_database, seed_benchmark_users  # noqa: E402

with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
