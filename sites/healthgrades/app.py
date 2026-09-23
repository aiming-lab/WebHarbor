#!/usr/bin/env python3
"""Healthgrades mirror — Flask application with full CRUD."""
import json
import os
import random
import re
from datetime import datetime, timedelta
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
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, SelectField, DateField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange
from sqlalchemy import func

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'healthgrades-mirror-dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'healthgrades.db')}"
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
    city = db.Column(db.String(100), default='')
    state = db.Column(db.String(50), default='')
    zip_code = db.Column(db.String(20), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)


class Specialty(db.Model):
    __tablename__ = 'specialties'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)


class Doctor(db.Model):
    __tablename__ = 'doctors'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(150), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    specialty_slug = db.Column(db.String(120), index=True)
    specialty_name = db.Column(db.String(150), default='')
    description = db.Column(db.Text, default='')
    image = db.Column(db.String(500), default='')
    npi = db.Column(db.String(20), default='')
    street_address = db.Column(db.String(200), default='')
    city = db.Column(db.String(100), default='', index=True)
    state = db.Column(db.String(10), default='', index=True)
    zip_code = db.Column(db.String(20), default='')
    latitude = db.Column(db.Float, default=0.0)
    longitude = db.Column(db.Float, default=0.0)
    hospital_names = db.Column(db.Text, default='[]')  # JSON list of strings
    education = db.Column(db.Text, default='[]')  # JSON list of strings
    service_name = db.Column(db.String(150), default='')
    rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    upstream_url = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    author_name = db.Column(db.String(120), default='Patient')
    rating = db.Column(db.Integer, default=5)
    body = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctor = db.relationship('Doctor')


class SavedDoctor(db.Model):
    __tablename__ = 'saved_doctors'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctor = db.relationship('Doctor')


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    patient_name = db.Column(db.String(120), default='')
    reason = db.Column(db.String(300), default='')
    preferred_date = db.Column(db.String(20), default='')
    status = db.Column(db.String(30), default='requested')  # requested, confirmed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctor = db.relationship('Doctor')


# ----- Login -----

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_globals():
    top_specialties = Specialty.query.order_by(Specialty.name).limit(12).all()
    return {
        'top_specialties': top_specialties,
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
    city = StringField('City', validators=[Optional()])
    state = StringField('State', validators=[Optional()])
    zip_code = StringField('ZIP Code', validators=[Optional()])


class ReviewForm(FlaskForm):
    rating = IntegerField('Rating', validators=[DataRequired(), NumberRange(min=1, max=5)])
    body = TextAreaField('Review', validators=[DataRequired()])


class AppointmentForm(FlaskForm):
    patient_name = StringField('Your Name', validators=[DataRequired()])
    reason = StringField('Reason for Visit', validators=[DataRequired()])
    preferred_date = DateField('Preferred Date', validators=[DataRequired()], format='%Y-%m-%d')


# ----- Routes: browse -----

@app.route('/')
def index():
    featured = Doctor.query.order_by(Doctor.id).limit(12).all()
    top_rated = Doctor.query.filter(Doctor.review_count > 0).order_by(Doctor.rating.desc(), Doctor.id).limit(8).all()
    return render_template('index.html', featured=featured, top_rated=top_rated)


@app.route('/specialty/<slug>')
def specialty_page(slug):
    specialty = Specialty.query.filter_by(slug=slug).first_or_404()
    sort_key = request.args.get('sort', '')
    q = Doctor.query.filter_by(specialty_slug=slug)
    if sort_key == 'rating':
        q = q.order_by(Doctor.rating.desc(), Doctor.id)
    elif sort_key == 'reviews':
        q = q.order_by(Doctor.review_count.desc(), Doctor.id)
    else:
        q = q.order_by(Doctor.name.asc(), Doctor.id)
    doctors = q.all()
    return render_template('specialty.html', specialty=specialty, doctors=doctors, current_sort=sort_key)


@app.route('/specialties')
def specialties_index():
    specialties = Specialty.query.order_by(Specialty.name).all()
    return render_template('specialties.html', specialties=specialties)


@app.route('/doctor/<slug>')
def doctor_detail(slug):
    doctor = Doctor.query.filter_by(slug=slug).first_or_404()
    reviews = Review.query.filter_by(doctor_id=doctor.id).order_by(Review.created_at.desc()).all()
    related = Doctor.query.filter(
        Doctor.specialty_slug == doctor.specialty_slug,
        Doctor.id != doctor.id
    ).order_by(Doctor.id).limit(4).all()
    is_saved = False
    if current_user.is_authenticated:
        is_saved = SavedDoctor.query.filter_by(user_id=current_user.id, doctor_id=doctor.id).first() is not None
    return render_template('doctor_detail.html', doctor=doctor, reviews=reviews, related=related,
                            is_saved=is_saved, review_form=ReviewForm(), appt_form=AppointmentForm())


STOPWORDS = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with',
             'and', 'or', 'is', 'are', 'from', 'as', 'this', 'that', 'dr', 'doctor'}


def _score_doctor(doctor, tokens):
    raw = ' '.join([
        doctor.name or '', doctor.specialty_name or '', doctor.description or '',
        doctor.city or '', doctor.state or '', doctor.service_name or '',
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
    candidates = Doctor.query.all()
    if q:
        tokens = [t for t in re.findall(r'[a-z0-9]+', q.lower())
                  if t and t not in STOPWORDS and len(t) >= 2]
        if tokens:
            min_required = 1 if len(tokens) <= 2 else (len(tokens) // 2) + 1
            scored = []
            for d in candidates:
                s = _score_doctor(d, tokens)
                if s >= min_required:
                    scored.append((s, d))
            results = [item for _, item in sorted(scored, key=lambda x: (-x[0], x[1].name.casefold(), x[1].id))]
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
            flash('Account created — welcome to Healthgrades.', 'success')
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
    appointments = Appointment.query.filter_by(user_id=current_user.id).order_by(Appointment.created_at.desc()).all()
    saved = SavedDoctor.query.filter_by(user_id=current_user.id).order_by(SavedDoctor.saved_at.desc()).all()
    return render_template('account.html', appointments=appointments, saved=saved)


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
def saved_doctors():
    saved = SavedDoctor.query.filter_by(user_id=current_user.id).order_by(SavedDoctor.saved_at.desc()).all()
    return render_template('saved_doctors.html', saved=saved)


# ----- Routes: save / review / appointment -----

@app.route('/doctor/<slug>/save', methods=['POST'])
@login_required
def save_doctor(slug):
    doctor = Doctor.query.filter_by(slug=slug).first_or_404()
    existing = SavedDoctor.query.filter_by(user_id=current_user.id, doctor_id=doctor.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        saved = False
    else:
        db.session.add(SavedDoctor(user_id=current_user.id, doctor_id=doctor.id))
        db.session.commit()
        saved = True
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'saved': saved})
    return redirect(url_for('doctor_detail', slug=slug))


@app.route('/doctor/<slug>/review', methods=['POST'])
@login_required
def add_review(slug):
    doctor = Doctor.query.filter_by(slug=slug).first_or_404()
    form = ReviewForm()
    if form.validate_on_submit():
        db.session.add(Review(
            doctor_id=doctor.id, author_name=current_user.name,
            rating=form.rating.data, body=form.body.data,
        ))
        # The archived reviews are a sample; retain the upstream aggregate.
        previous_count = doctor.review_count
        doctor.rating = ((doctor.rating * previous_count + form.rating.data)
                           / (previous_count + 1))
        doctor.review_count = previous_count + 1
        db.session.commit()
        flash('Thanks for sharing your experience!', 'success')
    return redirect(url_for('doctor_detail', slug=slug))


@app.route('/doctor/<slug>/request-appointment', methods=['POST'])
@login_required
def request_appointment(slug):
    doctor = Doctor.query.filter_by(slug=slug).first_or_404()
    form = AppointmentForm()
    if form.validate_on_submit():
        db.session.add(Appointment(
            user_id=current_user.id, doctor_id=doctor.id,
            patient_name=form.patient_name.data, reason=form.reason.data,
            preferred_date=form.preferred_date.data.isoformat(),
        ))
        db.session.commit()
        flash(f'Appointment request sent to {doctor.name}.', 'success')
    if form.errors:
        flash('Please provide a name, reason and valid preferred date.', 'error')
    return redirect(url_for('doctor_detail', slug=slug))


@app.route('/account/appointments/<int:appt_id>/cancel', methods=['POST'])
@login_required
def cancel_appointment(appt_id):
    appt = Appointment.query.filter_by(id=appt_id, user_id=current_user.id).first_or_404()
    appt.status = 'cancelled'
    db.session.commit()
    flash('Appointment request cancelled.', 'info')
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
    return {'ok': True, 'site': 'healthgrades'}


# ----- Seed Data -----

def seed_database():
    if Doctor.query.count() > 0:
        return
    from seed_data import run_seed
    run_seed(db, Specialty, Doctor, Review)


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    from seed_data import run_seed_users
    run_seed_users(db, User, SavedDoctor, Appointment, Doctor)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
