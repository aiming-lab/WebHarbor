#!/usr/bin/env python3
"""Kelley Blue Book mirror — Flask application with full CRUD."""
import json
import os
import random
import re
from datetime import datetime
from itertools import groupby
from urllib.parse import urlsplit

from flask import (Flask, render_template, request, redirect, url_for,
                    flash, jsonify, session, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                          login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_bcrypt import Bcrypt
from wtforms import StringField, PasswordField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, Regexp
from sqlalchemy import func

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kbb-mirror-dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'kelley_blue_book.db')}"
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


# ----- Models -----

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), default='')
    zip_code = db.Column(db.String(20), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)


class Make(db.Model):
    __tablename__ = 'makes'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)


class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(150), unique=True, nullable=False, index=True)
    make_slug = db.Column(db.String(60), index=True)
    make_name = db.Column(db.String(80), default='')
    model = db.Column(db.String(150), default='')
    model_name = db.Column(db.String(150), default='')
    year = db.Column(db.Integer, index=True)
    title = db.Column(db.String(255), default='')
    pros = db.Column(db.Text, default='[]')     # JSON list
    cons = db.Column(db.Text, default='[]')     # JSON list
    rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    min_price = db.Column(db.Float, default=0.0)
    max_price = db.Column(db.Float, default=0.0)
    spec_labels = db.Column(db.Text, default='[]')  # JSON list — trim spec column headers (varies by vehicle kind)
    image = db.Column(db.String(500), default='')
    gallery_images = db.Column(db.Text, default='[]')  # JSON list
    upstream_url = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    trims = db.relationship('VehicleTrim', backref='vehicle', lazy=True, cascade='all, delete-orphan')
    faqs = db.relationship('VehicleFAQ', backref='vehicle', lazy=True, cascade='all, delete-orphan')


class VehicleTrim(db.Model):
    __tablename__ = 'vehicle_trims'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    name = db.Column(db.String(80), default='')
    price = db.Column(db.Float, default=0.0)
    specs = db.Column(db.Text, default='[]')  # JSON list of values, aligned with vehicle.spec_labels


class VehicleFAQ(db.Model):
    __tablename__ = 'vehicle_faqs'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    question = db.Column(db.String(300), default='')
    answer = db.Column(db.Text, default='')


class SavedVehicle(db.Model):
    __tablename__ = 'saved_vehicles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)

    vehicle = db.relationship('Vehicle')


class QuoteRequest(db.Model):
    __tablename__ = 'quote_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    trim_name = db.Column(db.String(80), default='')
    zip_code = db.Column(db.String(20), default='')
    status = db.Column(db.String(30), default='pending')  # pending, contacted, closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vehicle = db.relationship('Vehicle')


# ----- Login -----

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_globals():
    top_makes = Make.query.order_by(Make.name).all()
    return {
        'top_makes': top_makes,
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
    zip_code = StringField('ZIP Code', validators=[Optional()])


class QuoteForm(FlaskForm):
    trim_name = StringField('Trim', validators=[DataRequired()])
    zip_code = StringField('ZIP Code', validators=[DataRequired(), Regexp(r'^\d{5}$', message='Enter a five-digit ZIP code.')])


# ----- Routes: browse -----

@app.route('/')
def index():
    featured = Vehicle.query.order_by(Vehicle.id).limit(12).all()
    top_rated = Vehicle.query.filter(Vehicle.review_count > 0).order_by(Vehicle.rating.desc(), Vehicle.id).limit(8).all()
    return render_template('index.html', featured=featured, top_rated=top_rated)


@app.route('/make/<slug>')
def make_page(slug):
    make = Make.query.filter_by(slug=slug).first_or_404()
    sort_key = request.args.get('sort', '')
    q = Vehicle.query.filter_by(make_slug=slug)
    if sort_key == 'price_low':
        q = q.order_by(Vehicle.min_price.is_(None), Vehicle.min_price.asc(), Vehicle.id)
    elif sort_key == 'price_high':
        q = q.order_by(Vehicle.min_price.is_(None), Vehicle.min_price.desc(), Vehicle.id)
    elif sort_key == 'rating':
        q = q.order_by(Vehicle.rating.desc(), Vehicle.id)
    else:
        q = q.order_by(Vehicle.model_name.asc(), Vehicle.id)
    vehicles = q.all()
    return render_template('make.html', make=make, vehicles=vehicles, current_sort=sort_key)


@app.route('/vehicle/<slug>')
def vehicle_detail(slug):
    vehicle = Vehicle.query.filter_by(slug=slug).first_or_404()
    related = Vehicle.query.filter(
        Vehicle.make_slug == vehicle.make_slug,
        Vehicle.id != vehicle.id
    ).order_by(Vehicle.id).limit(4).all()
    is_saved = False
    if current_user.is_authenticated:
        is_saved = SavedVehicle.query.filter_by(user_id=current_user.id, vehicle_id=vehicle.id).first() is not None
    return render_template('vehicle_detail.html', vehicle=vehicle, related=related,
                            is_saved=is_saved, quote_form=QuoteForm())


STOPWORDS = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with',
             'and', 'or', 'is', 'are', 'from', 'as', 'this', 'that'}


def _score_vehicle(vehicle, tokens):
    raw = ' '.join([
        vehicle.make_name or '', vehicle.model_name or '', str(vehicle.year or ''),
        vehicle.title or '',
    ]).lower()
    hay_tokens = set(re.findall(r'[a-z0-9]+', raw))

    def _match(t):
        if t in hay_tokens:
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
    candidates = Vehicle.query.all()
    if q:
        tokens = [t for t in re.findall(r'[a-z0-9]+', q.lower())
                  if t and t not in STOPWORDS and len(t) >= 2]
        if tokens:
            min_required = 1 if len(tokens) <= 2 else (len(tokens) // 2) + 1
            scored = []
            for v in candidates:
                s = _score_vehicle(v, tokens)
                if s >= min_required:
                    scored.append((s, v))
            results = [item for _, item in sorted(scored, key=lambda x: (-x[0], x[1].title.casefold(), x[1].id))]
        else:
            results = candidates
    else:
        results = []
    return render_template('search.html', query=q, results=results)


# ----- Routes: compare -----

@app.route('/compare')
def compare():
    slugs = request.args.get('slugs', ','.join(session.get('comparison', []))).split(',')
    vehicles = [v for slug in dict.fromkeys(slugs) if (v := Vehicle.query.filter_by(slug=slug).first())][:4]
    return render_template('compare.html', vehicles=vehicles)


@app.route('/compare/add/<slug>', methods=['POST'])
def compare_add(slug):
    vehicle = Vehicle.query.filter_by(slug=slug).first_or_404()
    selected = list(session.get('comparison', []))
    if slug not in selected:
        if len(selected) >= 4:
            flash('Compare up to four vehicles. Remove one to add another.', 'info')
        else:
            selected.append(slug)
    session['comparison'] = selected
    return redirect(url_for('compare'))


@app.route('/compare/remove/<slug>', methods=['POST'])
def compare_remove(slug):
    session['comparison'] = [s for s in session.get('comparison', []) if s != slug]
    return redirect(url_for('compare'))


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
            if not next_url or not next_url.startswith('/') or urlsplit(next_url).netloc or '\\' in next_url or any(ord(c) < 32 for c in next_url):
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
            flash('Account created — welcome to Kelley Blue Book.', 'success')
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
    quotes = QuoteRequest.query.filter_by(user_id=current_user.id).order_by(QuoteRequest.created_at.desc()).all()
    saved = SavedVehicle.query.filter_by(user_id=current_user.id).order_by(SavedVehicle.saved_at.desc()).all()
    return render_template('account.html', quotes=quotes, saved=saved)


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


@app.route('/account/saved')
@login_required
def saved_vehicles():
    saved = SavedVehicle.query.filter_by(user_id=current_user.id).order_by(SavedVehicle.saved_at.desc()).all()
    return render_template('saved_vehicles.html', saved=saved)


# ----- Routes: save / quote -----

@app.route('/vehicle/<slug>/save', methods=['POST'])
@login_required
def save_vehicle(slug):
    vehicle = Vehicle.query.filter_by(slug=slug).first_or_404()
    existing = SavedVehicle.query.filter_by(user_id=current_user.id, vehicle_id=vehicle.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        saved = False
    else:
        db.session.add(SavedVehicle(user_id=current_user.id, vehicle_id=vehicle.id))
        db.session.commit()
        saved = True
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'saved': saved})
    return redirect(url_for('vehicle_detail', slug=slug))


@app.route('/vehicle/<slug>/quote', methods=['POST'])
@login_required
def request_quote(slug):
    vehicle = Vehicle.query.filter_by(slug=slug).first_or_404()
    form = QuoteForm()
    if form.validate_on_submit() and form.trim_name.data in {t.name for t in vehicle.trims}:
        db.session.add(QuoteRequest(
            user_id=current_user.id, vehicle_id=vehicle.id,
            trim_name=form.trim_name.data, zip_code=form.zip_code.data,
        ))
        db.session.commit()
        flash(f'Price quote requested for the {vehicle.title}.', 'success')
    if form.errors or form.trim_name.data not in {t.name for t in vehicle.trims}:
        flash('Choose a listed trim and enter a five-digit ZIP code.', 'error')
    return redirect(url_for('vehicle_detail', slug=slug))


@app.route('/account/quotes/<int:quote_id>/cancel', methods=['POST'])
@login_required
def cancel_quote(quote_id):
    quote = QuoteRequest.query.filter_by(id=quote_id, user_id=current_user.id).first_or_404()
    quote.status = 'closed'
    db.session.commit()
    flash('Quote request closed.', 'info')
    return redirect(url_for('account'))


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
    return {'ok': True, 'site': 'kelley_blue_book'}


# ----- Seed Data -----

def seed_database():
    if Vehicle.query.count() > 0:
        return
    from seed_data import run_seed
    run_seed(db, Make, Vehicle, VehicleTrim, VehicleFAQ)


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    from seed_data import run_seed_users
    run_seed_users(db, User, SavedVehicle, QuoteRequest, Vehicle)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
