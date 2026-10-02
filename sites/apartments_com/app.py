"""Apartments.com mirror — Flask app.

A rental-real-estate marketplace clone. Buildings → floor plans → units,
with neighborhood/city pages, scored search, schools, reviews, saved searches,
tour requests, side-by-side compare, and a lightweight account.

Self-contained: all paths go through BASE_DIR. No cross-site imports.
"""
import hashlib
import json
import math
import os
import re
import secrets
from datetime import date, datetime, timedelta
from functools import wraps
from urllib.parse import urlencode

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf
from sqlalchemy import or_, and_, func, select


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "apartments-com-mirror-secret-key-not-for-prod"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'apartments_com.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to save searches, favorite listings, or schedule a tour."
login_manager.login_message_category = "info"
csrf = CSRFProtect(app)


# ─── Models ────────────────────────────────────────────────────────────────────


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), default="")
    budget_max = db.Column(db.Integer, default=0)
    beds_min = db.Column(db.Integer, default=0)
    preferred_cities = db.Column(db.Text, default="[]")
    receive_alerts = db.Column(db.Boolean, default=True)
    notify_tour_confirm = db.Column(db.Boolean, default=True)
    notify_application_status = db.Column(db.Boolean, default=True)
    notify_price_drop = db.Column(db.Boolean, default=True)
    notify_new_match = db.Column(db.Boolean, default=True)
    notify_newsletter = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode("utf-8")

    def check_password(self, pw):
        from werkzeug.security import check_password_hash as wz_check
        try:
            if (self.password_hash or "").startswith("pbkdf2:"):
                return wz_check(self.password_hash, pw)
            return bcrypt.check_password_hash(self.password_hash, pw)
        except Exception:
            return False


class City(db.Model):
    __tablename__ = "cities"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(8), nullable=False)
    state_full = db.Column(db.String(40), default="")
    blurb = db.Column(db.Text, default="")
    hero_image = db.Column(db.String(250), default="")
    avg_rent_studio = db.Column(db.Integer, default=0)
    avg_rent_1br = db.Column(db.Integer, default=0)
    avg_rent_2br = db.Column(db.Integer, default=0)
    avg_rent_3br = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)


class Neighborhood(db.Model):
    __tablename__ = "neighborhoods"
    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), index=True)
    slug = db.Column(db.String(120), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    blurb = db.Column(db.Text, default="")
    walk_score = db.Column(db.Integer, default=0)
    transit_score = db.Column(db.Integer, default=0)
    bike_score = db.Column(db.Integer, default=0)
    sound_score = db.Column(db.Integer, default=0)
    avg_rent = db.Column(db.Integer, default=0)
    city = db.relationship("City", backref=db.backref("neighborhoods", lazy=True))


class Building(db.Model):
    __tablename__ = "buildings"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(80), index=True)
    state = db.Column(db.String(8), index=True)
    zip = db.Column(db.String(20), default="", index=True)
    neighborhood = db.Column(db.String(80), index=True)
    neighborhood_id = db.Column(db.Integer, db.ForeignKey("neighborhoods.id"), index=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    property_type = db.Column(db.String(40), default="Apartment", index=True)
    year_built = db.Column(db.Integer, default=0)
    total_units = db.Column(db.Integer, default=0)
    stories = db.Column(db.Integer, default=0)

    rent_min = db.Column(db.Integer, default=0, index=True)
    rent_max = db.Column(db.Integer, default=0, index=True)
    beds_min = db.Column(db.Integer, default=0, index=True)
    beds_max = db.Column(db.Integer, default=0, index=True)
    sqft_min = db.Column(db.Integer, default=0)
    sqft_max = db.Column(db.Integer, default=0)

    description = db.Column(db.Text, default="")
    hero_image = db.Column(db.String(250), default="")
    gallery_images = db.Column(db.Text, default="[]")

    walk_score = db.Column(db.Integer, default=0)
    transit_score = db.Column(db.Integer, default=0)
    bike_score = db.Column(db.Integer, default=0)
    sound_score = db.Column(db.Integer, default=0)

    pet_friendly = db.Column(db.Boolean, default=True)
    cats_allowed = db.Column(db.Boolean, default=True)
    dogs_allowed = db.Column(db.Boolean, default=True)
    dog_weight_limit = db.Column(db.Integer, default=0)
    pet_deposit = db.Column(db.Integer, default=0)
    pet_rent = db.Column(db.Integer, default=0)

    has_parking = db.Column(db.Boolean, default=False, index=True)
    parking_type = db.Column(db.String(40), default="")
    parking_fee = db.Column(db.Integer, default=0)
    has_pool = db.Column(db.Boolean, default=False, index=True)
    has_gym = db.Column(db.Boolean, default=False, index=True)
    has_doorman = db.Column(db.Boolean, default=False, index=True)
    has_elevator = db.Column(db.Boolean, default=False)
    has_rooftop = db.Column(db.Boolean, default=False, index=True)
    has_ev_charging = db.Column(db.Boolean, default=False, index=True)
    has_laundry_in_unit = db.Column(db.Boolean, default=True)
    has_concierge = db.Column(db.Boolean, default=False)
    has_business_center = db.Column(db.Boolean, default=False)
    has_dog_park = db.Column(db.Boolean, default=False)
    has_storage = db.Column(db.Boolean, default=False)
    is_furnished = db.Column(db.Boolean, default=False)
    is_student_housing = db.Column(db.Boolean, default=False, index=True)
    is_senior_housing = db.Column(db.Boolean, default=False, index=True)
    is_military_housing = db.Column(db.Boolean, default=False, index=True)
    is_luxury = db.Column(db.Boolean, default=False, index=True)

    amenities = db.Column(db.Text, default="[]")
    lease_terms = db.Column(db.Text, default="[]")
    deposit = db.Column(db.Integer, default=0)
    app_fee = db.Column(db.Integer, default=50)
    admin_fee = db.Column(db.Integer, default=200)

    property_manager = db.Column(db.String(120), default="")
    contact_phone = db.Column(db.String(40), default="")
    contact_email = db.Column(db.String(120), default="")
    tour_url = db.Column(db.String(250), default="")
    has_3d_tour = db.Column(db.Boolean, default=False)

    rating_avg = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)

    listed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_new = db.Column(db.Boolean, default=False, index=True)

    def get_gallery(self):
        try: return json.loads(self.gallery_images or "[]")
        except Exception: return []

    def get_amenities(self):
        try: return json.loads(self.amenities or "[]")
        except Exception: return []

    def get_lease_terms(self):
        try: return json.loads(self.lease_terms or "[]")
        except Exception: return []

    @property
    def rent_display(self):
        if self.rent_min == self.rent_max:
            return f"${self.rent_min:,}"
        return f"${self.rent_min:,} – ${self.rent_max:,}"

    @property
    def beds_display(self):
        if self.beds_min == 0 and self.beds_max == 0:
            return "Studio"
        if self.beds_min == 0:
            return f"Studio – {self.beds_max} bd"
        if self.beds_min == self.beds_max:
            return f"{self.beds_min} bd"
        return f"{self.beds_min} – {self.beds_max} bd"


class FloorPlan(db.Model):
    __tablename__ = "floor_plans"
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), index=True)
    slug = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    beds = db.Column(db.Integer, default=0)
    baths = db.Column(db.Float, default=1.0)
    sqft_min = db.Column(db.Integer, default=0)
    sqft_max = db.Column(db.Integer, default=0)
    rent_min = db.Column(db.Integer, default=0)
    rent_max = db.Column(db.Integer, default=0)
    available_count = db.Column(db.Integer, default=0)
    plan_image = db.Column(db.String(250), default="")
    description = db.Column(db.Text, default="")
    building = db.relationship("Building", backref=db.backref("floor_plans", lazy=True))


class Unit(db.Model):
    __tablename__ = "units"
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), index=True)
    floor_plan_id = db.Column(db.Integer, db.ForeignKey("floor_plans.id"), index=True)
    unit_number = db.Column(db.String(40), nullable=False)
    floor = db.Column(db.Integer, default=1)
    beds = db.Column(db.Integer, default=0)
    baths = db.Column(db.Float, default=1.0)
    sqft = db.Column(db.Integer, default=0)
    rent = db.Column(db.Integer, default=0, index=True)
    deposit = db.Column(db.Integer, default=0)
    available_date = db.Column(db.String(20), default="", index=True)
    lease_terms = db.Column(db.Text, default="[]")
    is_available = db.Column(db.Boolean, default=True, index=True)
    is_featured = db.Column(db.Boolean, default=False)
    view = db.Column(db.String(80), default="")
    building = db.relationship("Building", backref=db.backref("units", lazy=True))
    floor_plan = db.relationship("FloorPlan", backref=db.backref("units", lazy=True))

    def get_lease_terms(self):
        try: return json.loads(self.lease_terms or "[]")
        except Exception: return []


class School(db.Model):
    __tablename__ = "schools"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    grade_level = db.Column(db.String(40), default="")
    grades = db.Column(db.String(40), default="")
    type = db.Column(db.String(20), default="Public")
    rating = db.Column(db.Integer, default=5)
    district = db.Column(db.String(120), default="")
    city = db.Column(db.String(80), index=True)
    state = db.Column(db.String(8), index=True)
    student_count = db.Column(db.Integer, default=0)
    student_teacher_ratio = db.Column(db.Float, default=15.0)
    description = db.Column(db.Text, default="")


class BuildingSchool(db.Model):
    __tablename__ = "building_schools"
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), index=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), index=True)
    distance_mi = db.Column(db.Float, default=0.5)
    school = db.relationship("School")


class POI(db.Model):
    __tablename__ = "pois"
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), index=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(40), default="Restaurant")
    distance_mi = db.Column(db.Float, default=0.5)
    walk_min = db.Column(db.Integer, default=10)


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), index=True)
    author_name = db.Column(db.String(80), default="Verified Resident")
    rating = db.Column(db.Integer, default=5)
    rating_value = db.Column(db.Integer, default=5)
    rating_location = db.Column(db.Integer, default=5)
    rating_office_staff = db.Column(db.Integer, default=5)
    rating_maintenance = db.Column(db.Integer, default=5)
    rating_amenities = db.Column(db.Integer, default=5)
    title = db.Column(db.String(200), default="")
    body = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    helpful_count = db.Column(db.Integer, default=0)
    flagged = db.Column(db.Boolean, default=False)
    building = db.relationship("Building", backref=db.backref("reviews", lazy=True))


class SavedSearch(db.Model):
    __tablename__ = "saved_searches"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    name = db.Column(db.String(120), default="My search")
    query_string = db.Column(db.Text, default="")
    email_frequency = db.Column(db.String(20), default="daily")  # daily / weekly / instant / off
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Favorite(db.Model):
    __tablename__ = "favorites"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    building = db.relationship("Building")


class TourRequest(db.Model):
    __tablename__ = "tour_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=True)
    name = db.Column(db.String(120), default="")
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    preferred_date = db.Column(db.String(20), default="")
    preferred_time = db.Column(db.String(40), default="")
    tour_type = db.Column(db.String(40), default="In-Person")
    move_in_date = db.Column(db.String(20), default="")
    message = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    building = db.relationship("Building")
    unit = db.relationship("Unit")


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), index=True)
    name = db.Column(db.String(120), default="")
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    body = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    building = db.relationship("Building")


class Article(db.Model):
    __tablename__ = "articles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text, default="")
    body = db.Column(db.Text, default="")
    category = db.Column(db.String(80), default="Renters Guide", index=True)
    hero_image = db.Column(db.String(250), default="")
    author = db.Column(db.String(80), default="Apartments.com Editorial")
    published_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    reading_time_min = db.Column(db.Integer, default=5)


class Newsletter(db.Model):
    __tablename__ = "newsletter_subs"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PropertyLead(db.Model):
    __tablename__ = "property_leads"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), default="")
    company = db.Column(db.String(120), default="")
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    portfolio_size = db.Column(db.String(40), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── Extended models (round-2 deepening) ────────────────────────────────────


class Author(db.Model):
    __tablename__ = "authors"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(160), default="Staff writer")
    bio = db.Column(db.Text, default="")
    avatar = db.Column(db.String(250), default="")
    twitter = db.Column(db.String(80), default="")


class PropertyManagerProfile(db.Model):
    __tablename__ = "property_manager_profiles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    blurb = db.Column(db.Text, default="")
    headquarters = db.Column(db.String(120), default="")
    portfolio_size = db.Column(db.Integer, default=0)
    avg_rating = db.Column(db.Float, default=4.0)
    contact_email = db.Column(db.String(120), default="")
    contact_phone = db.Column(db.String(40), default="")
    logo = db.Column(db.String(250), default="")


class LeaseApplication(db.Model):
    __tablename__ = "lease_applications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=True)
    first_name = db.Column(db.String(60), default="")
    last_name = db.Column(db.String(60), default="")
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    date_of_birth = db.Column(db.String(20), default="")
    ssn_last_four = db.Column(db.String(8), default="")
    employer = db.Column(db.String(160), default="")
    job_title = db.Column(db.String(120), default="")
    annual_income = db.Column(db.Integer, default=0)
    employment_start = db.Column(db.String(20), default="")
    references = db.Column(db.Text, default="[]")
    co_applicant_email = db.Column(db.String(120), default="")
    pet_count = db.Column(db.Integer, default=0)
    pet_details = db.Column(db.Text, default="")
    move_in_date = db.Column(db.String(20), default="")
    lease_length = db.Column(db.String(20), default="12 months")
    additional_notes = db.Column(db.Text, default="")
    status = db.Column(db.String(30), default="submitted")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    building = db.relationship("Building")
    unit = db.relationship("Unit")


class RoommateProfile(db.Model):
    __tablename__ = "roommate_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer, default=25)
    gender = db.Column(db.String(30), default="")
    city = db.Column(db.String(80), index=True)
    state = db.Column(db.String(8))
    neighborhood = db.Column(db.String(80), default="")
    budget_min = db.Column(db.Integer, default=800)
    budget_max = db.Column(db.Integer, default=2000)
    move_in_date = db.Column(db.String(20), default="")
    occupation = db.Column(db.String(120), default="")
    has_pet = db.Column(db.Boolean, default=False)
    smoker = db.Column(db.Boolean, default=False)
    bio = db.Column(db.Text, default="")
    interests = db.Column(db.String(255), default="")
    avatar = db.Column(db.String(250), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RoommateMessage(db.Model):
    __tablename__ = "roommate_messages"
    id = db.Column(db.Integer, primary_key=True)
    sender_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    target_profile_id = db.Column(db.Integer, db.ForeignKey("roommate_profiles.id"), index=True)
    name = db.Column(db.String(120), default="")
    email = db.Column(db.String(120), default="")
    body = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class InsuranceQuote(db.Model):
    __tablename__ = "insurance_quotes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    full_name = db.Column(db.String(120), default="")
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    address = db.Column(db.String(200), default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(8), default="")
    zip = db.Column(db.String(20), default="")
    coverage_amount = db.Column(db.Integer, default=20000)
    deductible = db.Column(db.Integer, default=500)
    has_pets = db.Column(db.Boolean, default=False)
    valuables_amount = db.Column(db.Integer, default=0)
    quoted_premium = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Mover(db.Model):
    __tablename__ = "movers"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    city = db.Column(db.String(80), index=True)
    state = db.Column(db.String(8))
    rating = db.Column(db.Float, default=4.5)
    review_count = db.Column(db.Integer, default=0)
    blurb = db.Column(db.Text, default="")
    base_rate = db.Column(db.Integer, default=125)
    services = db.Column(db.Text, default="[]")
    phone = db.Column(db.String(40), default="")
    logo = db.Column(db.String(250), default="")


class MovingQuote(db.Model):
    __tablename__ = "moving_quotes"
    id = db.Column(db.Integer, primary_key=True)
    mover_id = db.Column(db.Integer, db.ForeignKey("movers.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    name = db.Column(db.String(120), default="")
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    from_zip = db.Column(db.String(20), default="")
    to_zip = db.Column(db.String(20), default="")
    move_date = db.Column(db.String(20), default="")
    home_size = db.Column(db.String(40), default="1BR Apartment")
    services = db.Column(db.Text, default="[]")
    estimated_cost = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BuildingQuestion(db.Model):
    __tablename__ = "building_questions"
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    author_name = db.Column(db.String(120), default="Prospective Resident")
    body = db.Column(db.Text, default="")
    answer = db.Column(db.Text, default="")
    answered_by = db.Column(db.String(120), default="")
    answered_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class NotifySubscribe(db.Model):
    __tablename__ = "notify_subscribes"
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    email = db.Column(db.String(120), default="")
    beds = db.Column(db.Integer, default=-1)
    max_rent = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ReviewHelpful(db.Model):
    __tablename__ = "review_helpful"
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ReviewReport(db.Model):
    __tablename__ = "review_reports"
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reason = db.Column(db.String(80), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MarketTrend(db.Model):
    __tablename__ = "market_trends"
    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), index=True)
    period = db.Column(db.String(10), default="2026-05")
    median_studio = db.Column(db.Integer, default=0)
    median_1br = db.Column(db.Integer, default=0)
    median_2br = db.Column(db.Integer, default=0)
    median_3br = db.Column(db.Integer, default=0)
    yoy_pct = db.Column(db.Float, default=0.0)
    vacancy_pct = db.Column(db.Float, default=5.5)


class GlossaryTerm(db.Model):
    __tablename__ = "glossary_terms"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    term = db.Column(db.String(120), nullable=False)
    definition = db.Column(db.Text, default="")
    related = db.Column(db.String(255), default="")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    title = db.Column(db.String(200), default="")
    body = db.Column(db.Text, default="")
    is_read = db.Column(db.Boolean, default=False)
    kind = db.Column(db.String(40), default="info")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── Login + CSRF helpers ────────────────────────────────────────────────────


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


@app.context_processor
def inject_globals():
    cmp_ids = session.get("compare", [])
    cmp_buildings = []
    if cmp_ids:
        cmp_buildings = Building.query.filter(Building.id.in_(cmp_ids)).all()
    fav_ids = set()
    unread_notifications = 0
    if current_user.is_authenticated:
        fav_ids = {f.building_id for f in Favorite.query.filter_by(user_id=current_user.id).all()}
        unread_notifications = Notification.query.filter_by(
            user_id=current_user.id, is_read=False
        ).count()
    return {
        "csrf_token": generate_csrf,
        "current_year": datetime.utcnow().year,
        "compare_buildings": cmp_buildings,
        "favorite_building_ids": fav_ids,
        "unread_notifications": unread_notifications,
        "footer_metros": FOOTER_METROS,
        "footer_amenities": FOOTER_AMENITY_LANDINGS,
        "footer_beds": FOOTER_BED_LANDINGS,
        "footer_prices": FOOTER_PRICE_LANDINGS,
    }


FOOTER_METROS = [
    ("New York, NY", "new-york-ny"), ("Los Angeles, CA", "los-angeles-ca"),
    ("Chicago, IL", "chicago-il"), ("Houston, TX", "houston-tx"),
    ("Miami, FL", "miami-fl"), ("Seattle, WA", "seattle-wa"),
    ("Austin, TX", "austin-tx"), ("San Francisco, CA", "san-francisco-ca"),
    ("Boston, MA", "boston-ma"), ("Atlanta, GA", "atlanta-ga"),
    ("Denver, CO", "denver-co"), ("Washington, DC", "washington-dc"),
]
FOOTER_AMENITY_LANDINGS = [
    ("Apartments with Pool", "apartments-with-pool"),
    ("Pet-Friendly Apartments", "pet-friendly-apartments"),
    ("Furnished Apartments", "furnished-apartments"),
    ("Luxury Apartments", "luxury-apartments"),
    ("EV Charging Available", "apartments-with-ev-charging"),
    ("Apartments with Garage", "apartments-with-garage"),
    ("In-Unit Laundry", "apartments-with-laundry"),
    ("Apartments with Balcony", "apartments-with-balcony"),
    ("Short-Term Rentals", "short-term-rentals"),
    ("Corporate Housing", "corporate-housing"),
]
FOOTER_BED_LANDINGS = [
    ("Studio Apartments", "studios"),
    ("1 Bedroom Apartments", "1-bedroom-apartments"),
    ("2 Bedroom Apartments", "2-bedroom-apartments"),
    ("3 Bedroom Apartments", "3-bedroom-apartments"),
    ("4+ Bedroom Apartments", "4-plus-bedroom-apartments"),
]
FOOTER_PRICE_LANDINGS = [
    ("Under $1,000", "apartments-under-1000"),
    ("Under $1,500", "apartments-under-1500"),
    ("Under $2,000", "apartments-under-2000"),
    ("Under $3,000", "apartments-under-3000"),
    ("Luxury $3,000+", "luxury-3000-plus"),
]


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def _score_color(score):
    if score is None: return "score-0"
    if score >= 90: return "score-90"
    if score >= 70: return "score-70"
    if score >= 50: return "score-50"
    if score >= 25: return "score-25"
    return "score-0"


app.jinja_env.filters["score_color"] = _score_color


def _parse_int(v, default=0):
    try: return int(v)
    except Exception: return default


TOUR_TYPES = {"In-Person", "Self-Guided", "Live Video"}
TOUR_TIMES = {
    "9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM",
    "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM",
}


def _is_iso_date(value):
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def _parse_search(args):
    q = (args.get("q") or "").strip()
    city = (args.get("city") or "").strip()
    state = (args.get("state") or "").strip()
    nbhd = (args.get("neighborhood") or "").strip()
    price_min = _parse_int(args.get("price_min"), 0)
    price_max = _parse_int(args.get("price_max"), 0)
    beds_options = args.getlist("beds")
    baths_min = _parse_int(args.get("baths_min"), 0)
    prop_types = args.getlist("type")
    amenities = args.getlist("amenity")
    pet_filter = (args.get("pet") or "").strip()
    lease = (args.get("lease") or "").strip()
    avail_by = (args.get("available_by") or "").strip()
    mode = (args.get("mode") or "").strip()
    sort = (args.get("sort") or "popular").strip()
    polygon = (args.get("polygon") or "").strip()
    return {
        "q": q, "city": city, "state": state, "neighborhood": nbhd,
        "price_min": price_min, "price_max": price_max,
        "beds": beds_options, "baths_min": baths_min,
        "type": prop_types, "amenity": amenities,
        "pet": pet_filter, "lease": lease,
        "available_by": avail_by, "mode": mode,
        "sort": sort, "polygon": polygon,
    }


def _matching_unit_conditions(f, building_id):
    conditions = [
        Unit.building_id == building_id,
        Unit.is_available.is_(True),
    ]
    if f["price_min"]:
        conditions.append(Unit.rent >= f["price_min"])
    if f["price_max"]:
        conditions.append(Unit.rent <= f["price_max"])
    if f["beds"]:
        bed_clauses = []
        for bed in f["beds"]:
            if bed == "studio":
                bed_clauses.append(Unit.beds == 0)
            elif bed == "4+":
                bed_clauses.append(Unit.beds >= 4)
            else:
                try:
                    bed_clauses.append(Unit.beds == int(bed))
                except (TypeError, ValueError):
                    continue
        if bed_clauses:
            conditions.append(or_(*bed_clauses))
    if f["available_by"]:
        conditions.append(Unit.available_date <= f["available_by"])
    return conditions


def _apply_filters(query, f):
    if f["q"]:
        tokens = [t for t in re.split(r"\s+", f["q"].lower()) if t]
        for t in tokens:
            like = f"%{t}%"
            query = query.filter(or_(
                func.lower(Building.name).like(like),
                func.lower(Building.address).like(like),
                func.lower(Building.city).like(like),
                func.lower(Building.state).like(like),
                func.lower(Building.zip).like(like),
                func.lower(Building.neighborhood).like(like),
                func.lower(Building.description).like(like),
            ))
    if f["city"]:
        query = query.filter(func.lower(Building.city) == f["city"].lower())
    if f["state"]:
        query = query.filter(func.upper(Building.state) == f["state"].upper())
    if f["neighborhood"]:
        query = query.filter(func.lower(Building.neighborhood) == f["neighborhood"].lower())
    unit_conditions = _matching_unit_conditions(f, Building.id)
    if f["type"]:
        query = query.filter(Building.property_type.in_(f["type"]))
    for a in f["amenity"]:
        col = {
            "pool": Building.has_pool,
            "gym": Building.has_gym,
            "doorman": Building.has_doorman,
            "rooftop": Building.has_rooftop,
            "ev_charging": Building.has_ev_charging,
            "parking": Building.has_parking,
            "dog_park": Building.has_dog_park,
            "concierge": Building.has_concierge,
            "business_center": Building.has_business_center,
            "in_unit_laundry": Building.has_laundry_in_unit,
            "elevator": Building.has_elevator,
            "storage": Building.has_storage,
            "furnished": Building.is_furnished,
        }.get(a)
        if col is not None:
            query = query.filter(col.is_(True))
    if f["pet"] == "dogs":
        query = query.filter(Building.dogs_allowed.is_(True))
    elif f["pet"] == "cats":
        query = query.filter(Building.cats_allowed.is_(True))
    elif f["pet"] == "any":
        query = query.filter(Building.pet_friendly.is_(True))
    if f["mode"] == "student":
        query = query.filter(Building.is_student_housing.is_(True))
    elif f["mode"] == "senior":
        query = query.filter(Building.is_senior_housing.is_(True))
    elif f["mode"] == "military":
        query = query.filter(Building.is_military_housing.is_(True))
    elif f["mode"] == "luxury":
        query = query.filter(Building.is_luxury.is_(True))
    query = query.filter(
        db.session.query(Unit.id).filter(*unit_conditions).exists()
    )
    if f["polygon"]:
        try:
            pts = [tuple(float(x) for x in p.split(",")) for p in f["polygon"].split(";") if "," in p]
            if len(pts) >= 3:
                lats = [p[0] for p in pts]; lngs = [p[1] for p in pts]
                query = query.filter(
                    Building.latitude >= min(lats),
                    Building.latitude <= max(lats),
                    Building.longitude >= min(lngs),
                    Building.longitude <= max(lngs),
                )
        except Exception:
            pass

    sort = f["sort"]
    matching_min_rent = select(func.min(Unit.rent)).where(
        *unit_conditions
    ).correlate(Building).scalar_subquery()
    matching_max_rent = select(func.max(Unit.rent)).where(
        *unit_conditions
    ).correlate(Building).scalar_subquery()
    if sort == "price_asc":
        query = query.order_by(matching_min_rent.asc(), Building.id.asc())
    elif sort == "price_desc":
        query = query.order_by(matching_max_rent.desc(), Building.id.asc())
    elif sort == "sqft":
        query = query.order_by(Building.sqft_max.desc(), Building.id.asc())
    elif sort == "newest":
        query = query.order_by(Building.listed_at.desc(), Building.id.asc())
    elif sort == "rating":
        query = query.order_by(Building.rating_avg.desc(), Building.id.asc())
    else:
        query = query.order_by(Building.rating_avg.desc(), Building.review_count.desc(), Building.id.asc())
    return query


# ─── Routes: home / city / neighborhood ──────────────────────────────────────


@app.route("/")
def index():
    featured_cities = City.query.filter_by(is_featured=True).order_by(City.name).limit(8).all()
    if not featured_cities:
        featured_cities = City.query.order_by(City.name).limit(8).all()
    featured_buildings = Building.query.order_by(Building.rating_avg.desc(), Building.id.asc()).limit(8).all()
    new_buildings = Building.query.filter_by(is_new=True).order_by(Building.id.asc()).limit(6).all()
    recent_articles = Article.query.order_by(Article.published_at.desc()).limit(4).all()
    return render_template(
        "index.html",
        featured_cities=featured_cities,
        featured_buildings=featured_buildings,
        new_buildings=new_buildings,
        recent_articles=recent_articles,
        total_buildings=Building.query.count(),
    )


@app.route("/cities")
def cities_index():
    all_cities = City.query.order_by(City.name).all()
    return render_template("cities_index.html", cities=all_cities)


@app.route("/<city_slug>/")
def city_page(city_slug):
    city = City.query.filter_by(slug=city_slug).first_or_404()
    buildings = Building.query.filter_by(city=city.name, state=city.state)\
        .order_by(Building.rating_avg.desc(), Building.id.asc()).limit(24).all()
    nbhds = Neighborhood.query.filter_by(city_id=city.id).order_by(Neighborhood.name).all()
    total = Building.query.filter_by(city=city.name, state=city.state).count()
    return render_template("city.html", city=city, buildings=buildings,
                           neighborhoods=nbhds, total=total)


@app.route("/<city_slug>/<nbhd_slug>/")
def neighborhood_page(city_slug, nbhd_slug):
    city = City.query.filter_by(slug=city_slug).first_or_404()
    nbhd = Neighborhood.query.filter_by(city_id=city.id, slug=nbhd_slug).first_or_404()
    buildings = Building.query.filter_by(neighborhood_id=nbhd.id)\
        .order_by(Building.rating_avg.desc()).all()
    schools = School.query.filter_by(city=city.name, state=city.state)\
        .order_by(School.rating.desc()).limit(8).all()
    return render_template("neighborhood.html", city=city, nbhd=nbhd,
                           buildings=buildings, schools=schools)


# ─── Search ──────────────────────────────────────────────────────────────────


@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        flat = []
        for key, vals in request.form.lists():
            if key == "csrf_token":
                continue
            for v in vals:
                if v:
                    flat.append((key, v))
        return redirect(url_for("search") + ("?" + urlencode(flat) if flat else ""))

    f = _parse_search(request.args)
    page = max(1, _parse_int(request.args.get("page"), 1))
    per_page = 24
    base = _apply_filters(Building.query, f)
    total = base.count()
    pages = max(1, math.ceil(total / per_page))
    buildings = base.offset((page - 1) * per_page).limit(per_page).all()
    matching_rents = {}
    for building in buildings:
        matching_rents[building.id] = db.session.query(
            func.min(Unit.rent), func.max(Unit.rent)
        ).filter(
            *_matching_unit_conditions(f, building.id)
        ).one()
    cities = City.query.order_by(City.name).all()
    view = (request.args.get("view") or "list").strip()
    return render_template("search.html",
                           buildings=buildings, total=total, page=page, pages=pages,
                           cities=cities, filters=f, view=view,
                           request_args=request.args,
                           matching_rents=matching_rents)


@app.route("/search/draw", methods=["GET", "POST"])
def search_draw():
    if request.method == "POST":
        polygon = (request.form.get("polygon") or "").strip()
        return redirect(url_for("search", polygon=polygon))
    return render_template("draw_search.html")


# ─── Building detail ────────────────────────────────────────────────────────


@app.route("/<state>/<city_slug>/<building_slug>/")
def building_detail(state, city_slug, building_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    plans = FloorPlan.query.filter_by(building_id=b.id).order_by(FloorPlan.beds, FloorPlan.rent_min).all()
    units = Unit.query.filter_by(building_id=b.id, is_available=True)\
        .order_by(Unit.beds, Unit.rent).all()
    plan_available_counts = {
        plan_id: count for plan_id, count in
        db.session.query(Unit.floor_plan_id, func.count(Unit.id))
        .filter(
            Unit.building_id == b.id,
            Unit.is_available.is_(True),
        )
        .group_by(Unit.floor_plan_id).all()
    }
    pois = POI.query.filter_by(building_id=b.id).order_by(POI.distance_mi).all()
    schools = (db.session.query(School, BuildingSchool.distance_mi)
               .join(BuildingSchool, BuildingSchool.school_id == School.id)
               .filter(BuildingSchool.building_id == b.id)
               .order_by(School.rating.desc()).all())
    reviews = Review.query.filter_by(building_id=b.id)\
        .order_by(Review.created_at.desc()).limit(8).all()
    similar = Building.query.filter(Building.city == b.city,
                                    Building.state == b.state,
                                    Building.id != b.id)\
        .order_by(Building.rating_avg.desc()).limit(4).all()
    return render_template("building.html",
                           b=b, plans=plans, units=units, pois=pois,
                           schools=schools, reviews=reviews, similar=similar,
                           plan_available_counts=plan_available_counts)


@app.route("/<state>/<city_slug>/<building_slug>/photos/")
def building_photos(state, city_slug, building_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    return render_template("building_photos.html", b=b)


@app.route("/<state>/<city_slug>/<building_slug>/reviews/")
def building_reviews(state, city_slug, building_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    reviews = Review.query.filter_by(building_id=b.id).order_by(Review.created_at.desc()).all()
    return render_template("building_reviews.html", b=b, reviews=reviews)


@app.route("/<state>/<city_slug>/<building_slug>/floorplan/<plan_slug>/")
def floor_plan_detail(state, city_slug, building_slug, plan_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    plan = FloorPlan.query.filter_by(building_id=b.id, slug=plan_slug).first_or_404()
    units = Unit.query.filter_by(
        floor_plan_id=plan.id, is_available=True
    ).order_by(Unit.unit_number).all()
    return render_template("floor_plan.html", b=b, plan=plan, units=units)


@app.route("/<state>/<city_slug>/<building_slug>/unit/<int:unit_id>/")
def unit_detail(state, city_slug, building_slug, unit_id):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    u = Unit.query.filter_by(
        id=unit_id, building_id=b.id, is_available=True
    ).first_or_404()
    return render_template("unit.html", b=b, u=u, plan=u.floor_plan)


# ─── Reviews submit ─────────────────────────────────────────────────────────


@app.route("/<state>/<city_slug>/<building_slug>/reviews/submit", methods=["POST"])
@login_required
def submit_review(state, city_slug, building_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    title = (request.form.get("title") or "").strip()
    body = (request.form.get("body") or "").strip()
    if not title or not body:
        flash("Add both a title and review before submitting.", "error")
        return redirect(url_for(
            "building_reviews", state=state, city_slug=city_slug,
            building_slug=building_slug
        ))
    r = Review(
        building_id=b.id,
        author_name=current_user.name[:80],
        rating=max(1, min(5, _parse_int(request.form.get("rating"), 5))),
        rating_value=max(1, min(5, _parse_int(request.form.get("rating_value"), 5))),
        rating_location=max(1, min(5, _parse_int(request.form.get("rating_location"), 5))),
        rating_office_staff=max(1, min(5, _parse_int(request.form.get("rating_office_staff"), 5))),
        rating_maintenance=max(1, min(5, _parse_int(request.form.get("rating_maintenance"), 5))),
        rating_amenities=max(1, min(5, _parse_int(request.form.get("rating_amenities"), 5))),
        title=title[:200],
        body=body,
        user_id=current_user.id,
    )
    db.session.add(r)
    previous_count = b.review_count or 0
    b.rating_avg = round(
        (((b.rating_avg or 0) * previous_count) + r.rating) / (previous_count + 1),
        1,
    )
    b.review_count = previous_count + 1
    db.session.commit()
    flash("Thanks for your review!", "success")
    return redirect(url_for("building_reviews", state=state, city_slug=city_slug,
                            building_slug=building_slug))


# ─── Tour requests / messaging ──────────────────────────────────────────────


@app.route("/<state>/<city_slug>/<building_slug>/tour", methods=["GET", "POST"])
def request_tour(state, city_slug, building_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    step = _parse_int(request.args.get("step"), 1)
    unit_id = _parse_int(request.args.get("unit_id"), 0) or _parse_int(request.form.get("unit_id"), 0)
    unit = None
    if unit_id:
        unit = Unit.query.filter_by(
            id=unit_id, building_id=b.id, is_available=True
        ).first()
        if unit is None:
            abort(400)
    state_key = f"tour_{b.id}"
    tour_state = session.get(state_key, {})
    if request.method == "POST":
        post_step = _parse_int(request.form.get("step"), step)
        if post_step >= 3:
            form_values = {
                "tour_type": request.form.get("tour_type") or tour_state.get("tour_type", ""),
                "preferred_date": request.form.get("preferred_date") or tour_state.get("preferred_date", ""),
                "preferred_time": request.form.get("preferred_time") or tour_state.get("preferred_time", ""),
                "name": (request.form.get("name") or "").strip(),
                "email": (request.form.get("email") or "").strip().lower(),
            }
            if (
                not all(form_values.values())
                or form_values["tour_type"] not in TOUR_TYPES
                or not _is_iso_date(form_values["preferred_date"])
                or form_values["preferred_time"] not in TOUR_TIMES
                or "@" not in form_values["email"]
            ):
                flash("Tour type, date, time, name, and email are required.", "error")
                return render_template(
                    "tour.html", b=b, unit=unit, step=3,
                    tour_state=tour_state
                )
            tr = TourRequest(
                user_id=(current_user.id if current_user.is_authenticated else None),
                building_id=b.id, unit_id=unit_id or None,
                name=form_values["name"][:120],
                email=form_values["email"][:120],
                phone=request.form.get("phone", "")[:40],
                preferred_date=form_values["preferred_date"][:20],
                preferred_time=form_values["preferred_time"][:40],
                tour_type=form_values["tour_type"][:40],
                move_in_date=request.form.get("move_in_date", "")[:20],
                message=request.form.get("message", ""),
            )
            db.session.add(tr)
            db.session.commit()
            session.pop(state_key, None)
            return render_template("tour_confirmed.html", b=b, tr=tr, unit=unit)
        for k in ("tour_type", "preferred_date", "preferred_time"):
            if request.form.get(k):
                tour_state[k] = request.form.get(k)
        if post_step == 1 and tour_state.get("tour_type") not in TOUR_TYPES:
            flash("Choose a supported tour type.", "error")
            return render_template(
                "tour.html", b=b, unit=unit, step=1, tour_state={}
            )
        if post_step == 2 and (
            not _is_iso_date(tour_state.get("preferred_date"))
            or tour_state.get("preferred_time") not in TOUR_TIMES
        ):
            flash("Choose a valid tour date and time.", "error")
            return render_template(
                "tour.html", b=b, unit=unit, step=2,
                tour_state=tour_state
            )
        session[state_key] = tour_state
        return render_template("tour.html", b=b, unit=unit,
                               step=post_step + 1, tour_state=tour_state)
    return render_template(
        "tour.html", b=b, unit=unit, step=step, tour_state=tour_state
    )


@app.route("/<state>/<city_slug>/<building_slug>/message", methods=["GET", "POST"])
def send_message(state, city_slug, building_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    if request.method == "POST":
        m = Message(
            user_id=(current_user.id if current_user.is_authenticated else None),
            building_id=b.id,
            name=request.form.get("name", "")[:120],
            email=request.form.get("email", "")[:120],
            phone=request.form.get("phone", "")[:40],
            body=request.form.get("body", ""),
        )
        db.session.add(m)
        db.session.commit()
        flash("Message sent to the property.", "success")
        return redirect(url_for("building_detail", state=state, city_slug=city_slug,
                                building_slug=building_slug))
    return render_template("message.html", b=b)


# ─── Favorites / compare / saved searches ───────────────────────────────────


@app.route("/favorite/<int:building_id>", methods=["POST"])
@login_required
def toggle_favorite(building_id):
    b = Building.query.get_or_404(building_id)
    existing = Favorite.query.filter_by(user_id=current_user.id, building_id=b.id).first()
    if existing:
        db.session.delete(existing)
        state = "removed"
    else:
        db.session.add(Favorite(user_id=current_user.id, building_id=b.id))
        state = "added"
    db.session.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"state": state})
    return redirect(request.referrer or url_for("index"))


@app.route("/favorites")
@login_required
def favorites_list():
    favs = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).all()
    return render_template("favorites.html", favs=favs)


@app.route("/compare")
def compare():
    ids = session.get("compare", [])
    buildings = Building.query.filter(Building.id.in_(ids)).all() if ids else []
    return render_template("compare.html", buildings=buildings)


@app.route("/compare/add/<int:building_id>", methods=["POST"])
def compare_add(building_id):
    Building.query.get_or_404(building_id)
    cart = session.get("compare", [])
    if building_id not in cart:
        if len(cart) >= 4:
            cart.pop(0)
        cart.append(building_id)
        session["compare"] = cart
    return redirect(request.referrer or url_for("compare"))


@app.route("/compare/remove/<int:building_id>", methods=["POST"])
def compare_remove(building_id):
    cart = session.get("compare", [])
    if building_id in cart:
        cart.remove(building_id)
        session["compare"] = cart
    return redirect(request.referrer or url_for("compare"))


@app.route("/compare/clear", methods=["POST"])
def compare_clear():
    session["compare"] = []
    return redirect(url_for("compare"))


@app.route("/saved-searches", methods=["GET"])
@login_required
def saved_searches():
    items = SavedSearch.query.filter_by(user_id=current_user.id)\
        .order_by(SavedSearch.created_at.desc()).all()
    return render_template("saved_searches.html", items=items)


@app.route("/saved-searches/save", methods=["POST"])
@login_required
def save_search():
    name = request.form.get("name", "My search")[:120] or "My search"
    qs = request.form.get("query_string", "")
    db.session.add(SavedSearch(user_id=current_user.id, name=name, query_string=qs))
    db.session.commit()
    flash("Search saved. You'll get alerts for new matches.", "success")
    return redirect(url_for("saved_searches"))


@app.route("/saved-searches/<int:sid>/delete", methods=["POST"])
@login_required
def delete_saved_search(sid):
    s = SavedSearch.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for("saved_searches"))


# ─── Auth ────────────────────────────────────────────────────────────────────


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        u = User.query.filter_by(email=email).first()
        if u and u.check_password(pw):
            login_user(u, remember=bool(request.form.get("remember")))
            next_url = request.args.get("next") or ""
            if not next_url.startswith("/") or next_url.startswith("//"):
                next_url = url_for("account")
            return redirect(next_url)
        flash("Incorrect email or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        name = (request.form.get("name") or "").strip()
        pw = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        if not email or not name or not pw:
            flash("All fields are required.", "error")
        elif pw != confirm:
            flash("Passwords don't match.", "error")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered. Try signing in.", "error")
        else:
            u = User(email=email, name=name)
            u.set_password(pw)
            db.session.add(u)
            db.session.commit()
            login_user(u)
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    tours = TourRequest.query.filter_by(user_id=current_user.id)\
        .order_by(TourRequest.created_at.desc()).all()
    messages = Message.query.filter_by(user_id=current_user.id)\
        .order_by(Message.created_at.desc()).all()
    favs = Favorite.query.filter_by(user_id=current_user.id).all()
    searches = SavedSearch.query.filter_by(user_id=current_user.id).all()
    return render_template("account.html", tours=tours, messages=messages,
                           favs=favs, searches=searches)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        current_user.name = request.form.get("name", current_user.name)[:120]
        current_user.phone = request.form.get("phone", "")[:40]
        current_user.budget_max = _parse_int(request.form.get("budget_max"), 0)
        current_user.beds_min = _parse_int(request.form.get("beds_min"), 0)
        current_user.receive_alerts = bool(request.form.get("receive_alerts"))
        db.session.commit()
        flash("Profile saved.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


# ─── Schools ─────────────────────────────────────────────────────────────────


@app.route("/schools")
def schools_index():
    rows = School.query.order_by(School.rating.desc(), School.name).limit(60).all()
    return render_template("schools_index.html", schools=rows)


@app.route("/school/<slug>")
def school_detail(slug):
    s = School.query.filter_by(slug=slug).first_or_404()
    nearby = (db.session.query(Building, BuildingSchool.distance_mi)
              .join(BuildingSchool, BuildingSchool.building_id == Building.id)
              .filter(BuildingSchool.school_id == s.id)
              .order_by(BuildingSchool.distance_mi).limit(8).all())
    return render_template("school.html", s=s, nearby=nearby)


# ─── Renters Guide articles ──────────────────────────────────────────────────


@app.route("/renters-guide")
def articles_index():
    cat = (request.args.get("category") or "").strip()
    q = Article.query
    if cat:
        q = q.filter_by(category=cat)
    items = q.order_by(Article.published_at.desc()).all()
    categories = sorted({c[0] for c in db.session.query(Article.category).distinct().all()})
    return render_template("articles_index.html", articles=items, categories=categories,
                           current_category=cat)


@app.route("/renters-guide/<slug>")
def article_detail(slug):
    a = Article.query.filter_by(slug=slug).first_or_404()
    related = Article.query.filter(Article.category == a.category, Article.id != a.id)\
        .order_by(Article.published_at.desc()).limit(4).all()
    return render_template("article.html", a=a, related=related)


# ─── Specialty housing flows ────────────────────────────────────────────────


@app.route("/student-housing")
def student_housing():
    # Every student-housing building; Building.id keeps rating ties stable.
    rows = Building.query.filter_by(is_student_housing=True)\
        .order_by(Building.rating_avg.desc(), Building.id.asc()).all()
    return render_template("specialty.html",
                           title="Student Housing",
                           subtitle="Apartments designed for college life: short leases, by-the-bed pricing, walk-to-campus.",
                           buildings=rows, mode="student", capped=False)


@app.route("/senior-housing")
def senior_housing():
    rows = Building.query.filter_by(is_senior_housing=True)\
        .order_by(Building.rating_avg.desc(), Building.id.asc()).all()
    return render_template("specialty.html",
                           title="Senior Housing",
                           subtitle="55+ communities with accessibility features and engagement programs.",
                           buildings=rows, mode="senior", capped=False)


@app.route("/military-housing")
def military_housing():
    rows = Building.query.filter_by(is_military_housing=True)\
        .order_by(Building.rating_avg.desc(), Building.id.asc()).all()
    return render_template("specialty.html",
                           title="Military Housing",
                           subtitle="On-base and nearby rentals with flexible PCS-friendly leases.",
                           buildings=rows, mode="military", capped=False)


# ─── List your property landing ─────────────────────────────────────────────


@app.route("/list-your-property", methods=["GET", "POST"])
def list_property():
    if request.method == "POST":
        lead = PropertyLead(
            name=request.form.get("name", "")[:120],
            company=request.form.get("company", "")[:120],
            email=request.form.get("email", "")[:120],
            phone=request.form.get("phone", "")[:40],
            portfolio_size=request.form.get("portfolio_size", "")[:40],
            notes=request.form.get("notes", ""),
        )
        db.session.add(lead)
        db.session.commit()
        flash("Thanks! Our team will follow up within 1 business day.", "success")
        return redirect(url_for("list_property"))
    return render_template("list_property.html")


# ─── Newsletter ─────────────────────────────────────────────────────────────


@app.route("/newsletter", methods=["POST"])
def newsletter_signup():
    email = (request.form.get("email") or "").strip().lower()
    if email and not Newsletter.query.filter_by(email=email).first():
        db.session.add(Newsletter(email=email))
        db.session.commit()
        flash("You're subscribed to weekly market updates.", "success")
    elif email:
        flash("You're already subscribed.", "info")
    return redirect(request.referrer or url_for("index"))


# ─── Static support pages ───────────────────────────────────────────────────


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/help")
def help_page():
    return render_template("help.html", topics=HELP_TOPICS)


# ─── Category landings (amenity / bed / price / property type) ──────────────


# (slug → (title, subtitle, filter_dict))
CATEGORY_LANDINGS = {
    # Amenity
    "apartments-with-pool": ("Apartments with a Pool",
        "Cool off close to home. Browse buildings with resort-style or rooftop pools.",
        {"amenity": ["pool"]}),
    "pet-friendly-apartments": ("Pet-Friendly Apartments",
        "Find buildings that welcome cats and dogs — including the breed restrictions and pet rent.",
        {"pet": "any"}),
    "furnished-apartments": ("Furnished Apartments",
        "Move-in ready with everything from sofas to silverware.",
        {"amenity": ["furnished"]}),
    "luxury-apartments": ("Luxury Apartments",
        "High-end finishes, concierge service, doorman buildings, and rooftop amenities.",
        {"mode": "luxury"}),
    "apartments-with-ev-charging": ("Apartments with EV Charging",
        "Charge your electric vehicle in the garage. Filter for Level-2 chargers and reserved EV stalls.",
        {"amenity": ["ev_charging"]}),
    "apartments-with-garage": ("Apartments with a Garage",
        "Indoor garage parking — heated, secured, and steps from the elevator.",
        {"amenity": ["parking"]}),
    "apartments-with-laundry": ("Apartments with In-Unit Laundry",
        "Skip the basement laundry. Your washer and dryer are right in your apartment.",
        {"amenity": ["in_unit_laundry"]}),
    "apartments-with-doorman": ("Apartments with a Doorman",
        "24/7 doorman service for packages, guests, and that extra layer of security.",
        {"amenity": ["doorman"]}),
    "apartments-with-rooftop": ("Apartments with a Rooftop",
        "Sweeping skyline views and outdoor lounges on the top of the building.",
        {"amenity": ["rooftop"]}),
    "apartments-with-concierge": ("Apartments with Concierge",
        "Concierge for dry cleaning, restaurant reservations, and package management.",
        {"amenity": ["concierge"]}),
    "apartments-with-balcony": ("Apartments with a Balcony",
        "Step outside for fresh air without leaving home.",
        {"amenity": ["rooftop"]}),  # nearest proxy
    "short-term-rentals": ("Short-Term Rental Apartments",
        "Flexible leases under 6 months, ideal for relocation or seasonal stays.",
        {"lease": "short"}),
    "corporate-housing": ("Corporate Housing",
        "Fully-furnished, hotel-alternative living for business travelers and remote workers.",
        {"amenity": ["furnished"]}),
    "senior-55-plus": ("55+ Senior Apartments",
        "Age-restricted communities with accessibility, programming, and aging-in-place features.",
        {"mode": "senior"}),
    "income-restricted-apartments": ("Income-Restricted Apartments",
        "Affordable housing for residents meeting AMI income guidelines.",
        {"mode": "affordable"}),
    "section-8-apartments": ("Section 8 Housing Choice Voucher",
        "Apartments that accept HCV Section 8 vouchers in the federal program.",
        {"mode": "section8"}),
    # Property type
    "apartments": ("Apartments for Rent",
        "Browse mid-rise to high-rise apartment communities nationwide.",
        {"type": ["Apartment"]}),
    "condos": ("Condos for Rent",
        "Privately-owned condos available for lease across major metros.",
        {"type": ["Condo"]}),
    "townhomes": ("Townhomes for Rent",
        "Multi-story townhome rentals — typically more space and a private entrance.",
        {"type": ["Townhouse"]}),
    "houses": ("Houses for Rent",
        "Single-family homes with yards, driveways, and the privacy of a detached dwelling.",
        {"type": ["Townhouse"]}),  # townhouse proxy
    # By bed
    "studios": ("Studio Apartments for Rent",
        "Affordable, efficient studios in every price tier.",
        {"beds": ["studio"]}),
    "1-bedroom-apartments": ("1-Bedroom Apartments for Rent",
        "The most popular floor-plan size in nearly every market.",
        {"beds": ["1"]}),
    "2-bedroom-apartments": ("2-Bedroom Apartments for Rent",
        "Great for couples, roommates, or anyone wanting a home office.",
        {"beds": ["2"]}),
    "3-bedroom-apartments": ("3-Bedroom Apartments for Rent",
        "Family-sized layouts with room for kids, guests, or a dedicated office.",
        {"beds": ["3"]}),
    "4-plus-bedroom-apartments": ("4+ Bedroom Apartments for Rent",
        "Large homes for big families or shared housing.",
        {"beds": ["4+"]}),
    # By price
    "apartments-under-1000": ("Apartments Under $1,000",
        "Budget-friendly listings that won't break the bank.",
        {"price_max": 1000}),
    "apartments-under-1500": ("Apartments Under $1,500",
        "Solid mid-market options across the country.",
        {"price_max": 1500}),
    "apartments-under-2000": ("Apartments Under $2,000",
        "More space and amenities at a still-reasonable price.",
        {"price_max": 2000}),
    "apartments-under-3000": ("Apartments Under $3,000",
        "Step-up apartments with strong amenities in major metros.",
        {"price_max": 3000}),
    "luxury-3000-plus": ("Luxury Apartments $3,000+",
        "Top-of-market apartments with the best views and finishes.",
        {"price_min": 3000, "mode": "luxury"}),
}


def _filters_to_args(filters):
    """Convert the CATEGORY_LANDINGS dict-style filter to an args MultiDict for _apply_filters."""
    from werkzeug.datastructures import MultiDict
    md = MultiDict()
    for k, v in filters.items():
        if isinstance(v, list):
            for item in v:
                md.add(k, item)
        else:
            md.add(k, v)
    return md


@app.route("/category/<slug>")
def category_landing(slug):
    if slug not in CATEGORY_LANDINGS:
        abort(404)
    title, subtitle, fdict = CATEGORY_LANDINGS[slug]
    f = _parse_search(_filters_to_args(fdict))
    page = max(1, _parse_int(request.args.get("page"), 1))
    per_page = 24
    base = _apply_filters(Building.query, f)
    total = base.count()
    pages = max(1, math.ceil(total / per_page))
    buildings = base.offset((page - 1) * per_page).limit(per_page).all()
    # Top cities for this category (re-evaluated)
    base_for_grouping = _apply_filters(Building.query, f)
    rows = (base_for_grouping.with_entities(Building.city, Building.state, func.count(Building.id))
            .group_by(Building.city, Building.state)
            .order_by(func.count(Building.id).desc())
            .limit(12).all())
    return render_template("category_landing.html",
                           slug=slug, title=title, subtitle=subtitle,
                           buildings=buildings, total=total, page=page, pages=pages,
                           top_cities=rows, filters=f,
                           qs=urlencode(list(_filters_to_args(fdict).items(multi=True))))


# Register an explicit route for each category so the URL is /<slug> not /category/<slug>.
def _make_cat_view(slug):
    def _v():
        return category_landing(slug)
    _v.__name__ = f"cat_{re.sub(r'[^a-z0-9]', '_', slug)}"
    return _v


# Defer the explicit registrations until after the city_page wildcard, by using
# distinct paths. We use a /landings/<slug> alias *plus* explicit named routes:
for _slug, _data in CATEGORY_LANDINGS.items():
    app.add_url_rule(f"/{_slug}", endpoint=f"cat_{_slug}",
                     view_func=_make_cat_view(_slug))


# ─── Metro market overview ─────────────────────────────────────────────────


@app.route("/metro/<city_slug>/overview")
def metro_overview(city_slug):
    city = City.query.filter_by(slug=city_slug).first_or_404()
    trend = MarketTrend.query.filter_by(city_id=city.id).first()
    nbhds = (Neighborhood.query.filter_by(city_id=city.id)
             .order_by(Neighborhood.avg_rent.desc()).all())
    top_buildings = (Building.query.filter_by(city=city.name, state=city.state)
                     .order_by(Building.rating_avg.desc()).limit(8).all())
    total = Building.query.filter_by(city=city.name, state=city.state).count()
    # 12-month synthetic sparkline based on city mult
    base_rent = trend.median_1br if trend else city.avg_rent_1br
    sparkline = []
    for i in range(12):
        h = int(hashlib.md5(f"{city.slug}-{i}".encode()).hexdigest()[:4], 16)
        delta = (h % 80) - 40
        sparkline.append(int(base_rent * (1.0 + 0.005 * (i - 6)) + delta))
    return render_template("metro_overview.html", city=city, trend=trend,
                           nbhds=nbhds, top_buildings=top_buildings,
                           total=total, sparkline=sparkline)


# ─── Extended neighborhood hub ───────────────────────────────────────────────


@app.route("/<city_slug>/<nbhd_slug>/hub")
def neighborhood_hub(city_slug, nbhd_slug):
    city = City.query.filter_by(slug=city_slug).first_or_404()
    nbhd = Neighborhood.query.filter_by(city_id=city.id, slug=nbhd_slug).first_or_404()
    buildings = Building.query.filter_by(neighborhood_id=nbhd.id)\
        .order_by(Building.rating_avg.desc()).all()
    pois = (POI.query.filter(POI.building_id.in_(db.session.query(Building.id)
            .filter_by(neighborhood_id=nbhd.id))).limit(30).all())
    schools = School.query.filter_by(city=city.name, state=city.state)\
        .order_by(School.rating.desc()).limit(6).all()
    similar = (Neighborhood.query.filter(Neighborhood.city_id == city.id,
                                          Neighborhood.id != nbhd.id)
               .order_by(Neighborhood.walk_score.desc()).limit(6).all())
    median_rent = nbhd.avg_rent or 0
    return render_template("neighborhood_hub.html", city=city, nbhd=nbhd,
                           buildings=buildings, pois=pois, schools=schools,
                           similar=similar, median_rent=median_rent)


# ─── Building Q&A / notify / extras ─────────────────────────────────────────


@app.route("/<state>/<city_slug>/<building_slug>/qa", methods=["GET", "POST"])
def building_qa(state, city_slug, building_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    if request.method == "POST":
        q = BuildingQuestion(
            building_id=b.id,
            user_id=(current_user.id if current_user.is_authenticated else None),
            author_name=request.form.get("author_name", "Prospective Resident")[:120] or "Prospective Resident",
            body=request.form.get("body", "")[:2000],
        )
        db.session.add(q)
        db.session.commit()
        flash("Question posted. The property manager will respond within a few days.", "success")
        return redirect(url_for("building_qa", state=state, city_slug=city_slug,
                                building_slug=building_slug))
    questions = BuildingQuestion.query.filter_by(building_id=b.id)\
        .order_by(BuildingQuestion.created_at.desc()).all()
    return render_template("building_qa.html", b=b, questions=questions)


@app.route("/<state>/<city_slug>/<building_slug>/notify", methods=["POST"])
def building_notify(state, city_slug, building_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    email = (request.form.get("email") or "").strip().lower()
    beds = _parse_int(request.form.get("beds"), -1)
    max_rent = _parse_int(request.form.get("max_rent"), 0)
    if email:
        db.session.add(NotifySubscribe(
            building_id=b.id,
            user_id=(current_user.id if current_user.is_authenticated else None),
            email=email, beds=beds, max_rent=max_rent,
        ))
        db.session.commit()
        flash(f"You'll be notified at {email} when matching units open up.", "success")
    return redirect(url_for("building_detail", state=state, city_slug=city_slug,
                            building_slug=building_slug))


# ─── Tour calendar / cancel / reschedule ────────────────────────────────────


def _generate_calendar_slots(building_slug, week_offset=0):
    """Return a 7-day × 4-slot grid of bookable slots, deterministic by slug+offset."""
    base = date(2026, 5, 27) + timedelta(days=week_offset * 7)
    h = hashlib.md5(f"{building_slug}-{week_offset}".encode()).hexdigest()
    slots = []
    times = ["09:00", "11:00", "14:00", "16:30"]
    for d in range(7):
        day = base + timedelta(days=d)
        for i, t in enumerate(times):
            taken = (int(h[(d * 4 + i) % 32], 16) % 5 == 0)
            slots.append({
                "date": day.isoformat(),
                "label": day.strftime("%a %b %d"),
                "time": t,
                "taken": taken,
            })
    return slots


@app.route("/<state>/<city_slug>/<building_slug>/tour/calendar", methods=["GET", "POST"])
def tour_calendar(state, city_slug, building_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    week = max(0, min(8, _parse_int(request.args.get("week"), 0)))
    slots = _generate_calendar_slots(b.slug, week)
    if request.method == "POST":
        slot_value = request.form.get("slot", "")
        if "|" in slot_value:
            chosen_date, chosen_time = slot_value.split("|", 1)
        else:
            chosen_date = request.form.get("date", "")[:20]
            chosen_time = request.form.get("time", "")[:20]
        tour_type = request.form.get("tour_type", "In-Person")[:40]
        valid_slots = {
            (slot["date"], slot["time"]) for slot in slots if not slot["taken"]
        }
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        if (
            (chosen_date, chosen_time) in valid_slots
            and tour_type in TOUR_TYPES
            and name
            and "@" in email
        ):
            tr = TourRequest(
                user_id=(current_user.id if current_user.is_authenticated else None),
                building_id=b.id,
                name=name[:120],
                email=email[:120],
                phone=request.form.get("phone", "")[:40],
                preferred_date=chosen_date,
                preferred_time=chosen_time,
                tour_type=tour_type,
                message=request.form.get("message", "")[:2000],
            )
            db.session.add(tr)
            db.session.commit()
            return render_template("tour_confirmed.html", b=b, tr=tr, unit=None)
        flash("Choose an available time and provide your name and email.", "error")
    return render_template("tour_calendar.html", b=b, slots=slots, week=week)


@app.route("/tours/<int:tour_id>/cancel", methods=["POST"])
@login_required
def cancel_tour(tour_id):
    tr = TourRequest.query.filter_by(id=tour_id, user_id=current_user.id).first_or_404()
    db.session.delete(tr)
    db.session.commit()
    flash("Tour cancelled.", "info")
    return redirect(url_for("account"))


@app.route("/tours/<int:tour_id>/reschedule", methods=["POST"])
@login_required
def reschedule_tour(tour_id):
    tr = TourRequest.query.filter_by(id=tour_id, user_id=current_user.id).first_or_404()
    tr.preferred_date = request.form.get("preferred_date", tr.preferred_date)[:20]
    tr.preferred_time = request.form.get("preferred_time", tr.preferred_time)[:40]
    db.session.commit()
    flash("Tour rescheduled.", "success")
    return redirect(url_for("account"))


# ─── Lease application (multi-step) ─────────────────────────────────────────


@app.route("/<state>/<city_slug>/<building_slug>/apply", methods=["GET", "POST"])
def apply_lease(state, city_slug, building_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    step = max(1, min(6, _parse_int(request.args.get("step"), 1)))
    sess_key = f"apply_{b.id}"
    state_data = session.get(sess_key, {})
    if request.method == "POST":
        post_step = _parse_int(request.form.get("step"), step)
        # accumulate everything submitted
        for key, vals in request.form.lists():
            if key in ("csrf_token", "step"):
                continue
            state_data[key] = vals[0] if len(vals) == 1 else vals
        session[sess_key] = state_data
        if post_step >= 6:
            la = LeaseApplication(
                user_id=(current_user.id if current_user.is_authenticated else None),
                building_id=b.id,
                unit_id=_parse_int(state_data.get("unit_id"), 0) or None,
                first_name=state_data.get("first_name", "")[:60],
                last_name=state_data.get("last_name", "")[:60],
                email=state_data.get("email", "")[:120],
                phone=state_data.get("phone", "")[:40],
                date_of_birth=state_data.get("date_of_birth", "")[:20],
                ssn_last_four=state_data.get("ssn_last_four", "")[:8],
                employer=state_data.get("employer", "")[:160],
                job_title=state_data.get("job_title", "")[:120],
                annual_income=_parse_int(state_data.get("annual_income"), 0),
                employment_start=state_data.get("employment_start", "")[:20],
                references=json.dumps([
                    {"name": state_data.get("ref1_name", ""), "phone": state_data.get("ref1_phone", "")},
                    {"name": state_data.get("ref2_name", ""), "phone": state_data.get("ref2_phone", "")},
                ]),
                co_applicant_email=state_data.get("co_applicant_email", "")[:120],
                pet_count=_parse_int(state_data.get("pet_count"), 0),
                pet_details=state_data.get("pet_details", "")[:500],
                move_in_date=state_data.get("move_in_date", "")[:20],
                lease_length=state_data.get("lease_length", "12 months")[:20],
                additional_notes=state_data.get("additional_notes", "")[:2000],
            )
            db.session.add(la)
            db.session.commit()
            session.pop(sess_key, None)
            return render_template("application_submitted.html", b=b, la=la)
        return redirect(url_for("apply_lease", state=state, city_slug=city_slug,
                                building_slug=building_slug, step=post_step + 1))
    return render_template("application.html", b=b, step=step, state_data=state_data)


@app.route("/<state>/<city_slug>/<building_slug>/apply/co-applicant", methods=["POST"])
def apply_co_applicant(state, city_slug, building_slug):
    b = Building.query.filter_by(slug=building_slug).first_or_404()
    co_email = (request.form.get("co_applicant_email") or "").strip().lower()
    sess_key = f"apply_{b.id}"
    state_data = session.get(sess_key, {})
    state_data["co_applicant_email"] = co_email
    session[sess_key] = state_data
    flash(f"Co-applicant invite sent to {co_email}.", "success")
    return redirect(url_for("apply_lease", state=state, city_slug=city_slug,
                            building_slug=building_slug, step=4))


# ─── Roommate finder ────────────────────────────────────────────────────────


@app.route("/roommates")
def roommates_index():
    profiles = RoommateProfile.query.order_by(RoommateProfile.created_at.desc()).limit(12).all()
    cities = sorted({p.city for p in RoommateProfile.query.with_entities(RoommateProfile.city).all() if p.city})
    return render_template("roommates_index.html", profiles=profiles, cities=cities)


@app.route("/roommates/browse")
def roommates_browse():
    qcity = (request.args.get("city") or "").strip()
    qbudget = _parse_int(request.args.get("budget_max"), 0)
    page = max(1, _parse_int(request.args.get("page"), 1))
    per_page = 18
    q = RoommateProfile.query
    if qcity:
        q = q.filter(func.lower(RoommateProfile.city) == qcity.lower())
    if qbudget:
        q = q.filter(RoommateProfile.budget_max <= qbudget)
    total = q.count()
    profiles = q.order_by(RoommateProfile.created_at.desc())\
        .offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, math.ceil(total / per_page))
    return render_template("roommates_browse.html", profiles=profiles,
                           page=page, pages=pages, total=total,
                           qcity=qcity, qbudget=qbudget)


@app.route("/roommates/profile/<int:pid>")
def roommate_detail(pid):
    p = RoommateProfile.query.get_or_404(pid)
    similar = RoommateProfile.query.filter(RoommateProfile.city == p.city,
                                            RoommateProfile.id != p.id)\
        .order_by(RoommateProfile.created_at.desc()).limit(6).all()
    return render_template("roommate_detail.html", p=p, similar=similar)


@app.route("/roommates/profile", methods=["GET", "POST"])
@login_required
def roommate_profile_edit():
    existing = RoommateProfile.query.filter_by(user_id=current_user.id).first()
    if request.method == "POST":
        if not existing:
            existing = RoommateProfile(user_id=current_user.id, name=current_user.name,
                                       city="", state="")
            db.session.add(existing)
        existing.name = request.form.get("name", existing.name)[:120]
        existing.age = _parse_int(request.form.get("age"), existing.age or 25)
        existing.gender = request.form.get("gender", "")[:30]
        existing.city = request.form.get("city", "")[:80]
        existing.state = request.form.get("state", "")[:8]
        existing.neighborhood = request.form.get("neighborhood", "")[:80]
        existing.budget_min = _parse_int(request.form.get("budget_min"), 800)
        existing.budget_max = _parse_int(request.form.get("budget_max"), 2000)
        existing.move_in_date = request.form.get("move_in_date", "")[:20]
        existing.occupation = request.form.get("occupation", "")[:120]
        existing.has_pet = bool(request.form.get("has_pet"))
        existing.smoker = bool(request.form.get("smoker"))
        existing.bio = request.form.get("bio", "")[:2000]
        existing.interests = request.form.get("interests", "")[:255]
        db.session.commit()
        flash("Roommate profile saved.", "success")
        return redirect(url_for("roommate_detail", pid=existing.id))
    return render_template("roommate_profile.html", profile=existing)


@app.route("/roommates/profile/<int:pid>/message", methods=["POST"])
def roommate_message(pid):
    p = RoommateProfile.query.get_or_404(pid)
    msg = RoommateMessage(
        sender_user_id=(current_user.id if current_user.is_authenticated else None),
        target_profile_id=p.id,
        name=request.form.get("name", "")[:120],
        email=request.form.get("email", "")[:120],
        body=request.form.get("body", "")[:2000],
    )
    db.session.add(msg)
    db.session.commit()
    flash(f"Message sent to {p.name}.", "success")
    return redirect(url_for("roommate_detail", pid=p.id))


@app.route("/roommates/profile/<int:pid>/connect", methods=["POST"])
@login_required
def roommate_connect(pid):
    p = RoommateProfile.query.get_or_404(pid)
    db.session.add(Notification(user_id=current_user.id,
                                title=f"Connection request sent to {p.name}",
                                body=f"You asked to connect with {p.name} in {p.city}.",
                                kind="roommate"))
    db.session.commit()
    flash(f"Connect request sent to {p.name}.", "success")
    return redirect(url_for("roommate_detail", pid=p.id))


# ─── Renters insurance ──────────────────────────────────────────────────────


@app.route("/renters-insurance", methods=["GET", "POST"])
def renters_insurance():
    if request.method == "POST":
        coverage = _parse_int(request.form.get("coverage_amount"), 20000)
        deductible = _parse_int(request.form.get("deductible"), 500)
        valuables = _parse_int(request.form.get("valuables_amount"), 0)
        has_pets = bool(request.form.get("has_pets"))
        # Simple linear premium model
        premium = int((coverage / 1000) * 0.55 + (valuables / 1000) * 0.40
                      + (10 if has_pets else 0) - (deductible / 200))
        premium = max(11, premium)
        q = InsuranceQuote(
            user_id=(current_user.id if current_user.is_authenticated else None),
            full_name=request.form.get("full_name", "")[:120],
            email=request.form.get("email", "")[:120],
            phone=request.form.get("phone", "")[:40],
            address=request.form.get("address", "")[:200],
            city=request.form.get("city", "")[:80],
            state=request.form.get("state", "")[:8],
            zip=request.form.get("zip", "")[:20],
            coverage_amount=coverage, deductible=deductible,
            has_pets=has_pets, valuables_amount=valuables,
            quoted_premium=premium,
        )
        db.session.add(q)
        db.session.commit()
        return render_template("insurance_quote_result.html", quote=q)
    return render_template("renters_insurance.html")


# ─── Moving services ────────────────────────────────────────────────────────


@app.route("/moving-services")
def moving_services():
    rows = Mover.query.order_by(Mover.rating.desc(), Mover.name).all()
    return render_template("moving_services.html", movers=rows)


@app.route("/movers/<slug>", methods=["GET", "POST"])
def mover_detail(slug):
    m = Mover.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        services = request.form.getlist("services")
        cost = int(m.base_rate * 3.0 + _parse_int(request.form.get("rooms"), 1) * 350
                   + (200 if "packing" in services else 0)
                   + (150 if "storage" in services else 0))
        q = MovingQuote(
            mover_id=m.id,
            user_id=(current_user.id if current_user.is_authenticated else None),
            name=request.form.get("name", "")[:120],
            email=request.form.get("email", "")[:120],
            phone=request.form.get("phone", "")[:40],
            from_zip=request.form.get("from_zip", "")[:20],
            to_zip=request.form.get("to_zip", "")[:20],
            move_date=request.form.get("move_date", "")[:20],
            home_size=request.form.get("home_size", "1BR Apartment")[:40],
            services=json.dumps(services),
            estimated_cost=cost,
        )
        db.session.add(q)
        db.session.commit()
        return render_template("moving_quote_result.html", quote=q, mover=m)
    return render_template("mover_detail.html", m=m)


# ─── Calculators ────────────────────────────────────────────────────────────


@app.route("/tools/affordability", methods=["GET", "POST"])
def calc_affordability():
    income = _parse_int(request.values.get("income"), 0)
    debts = _parse_int(request.values.get("debts"), 0)
    # 30%/40% rule
    max_30 = max(0, (income - debts) * 0.30)
    max_40 = max(0, (income - debts) * 0.40)
    return render_template("calc_affordability.html",
                           income=income, debts=debts,
                           max_30=int(max_30 / 12), max_40=int(max_40 / 12))


@app.route("/tools/rent-vs-buy", methods=["GET", "POST"])
def calc_rent_vs_buy():
    rent = _parse_int(request.values.get("rent"), 2500)
    price = _parse_int(request.values.get("price"), 500000)
    down = _parse_int(request.values.get("down"), 100000)
    years = _parse_int(request.values.get("years"), 7)
    rate = 6.75  # %
    loan = max(0, price - down)
    mo_rate = rate / 100 / 12
    n = years * 12
    mortgage = int(loan * mo_rate / (1 - (1 + mo_rate) ** (-n))) if mo_rate else 0
    taxes = int(price * 0.012 / 12)
    insurance = int(price * 0.0035 / 12)
    own_total = mortgage + taxes + insurance
    rent_total = rent * 12 * years
    own_paid = own_total * 12 * years
    return render_template("calc_rent_vs_buy.html", rent=rent, price=price, down=down,
                           years=years, mortgage=mortgage, taxes=taxes,
                           insurance=insurance, own_total=own_total,
                           rent_total=rent_total, own_paid=own_paid)


@app.route("/tools/move-in-cost", methods=["GET", "POST"])
def calc_move_in():
    rent = _parse_int(request.values.get("rent"), 0)
    deposit_x = _parse_int(request.values.get("deposit_months"), 1)
    app_fee = _parse_int(request.values.get("app_fee"), 75)
    admin = _parse_int(request.values.get("admin_fee"), 200)
    moving = _parse_int(request.values.get("moving"), 800)
    fixed_deposit = request.values.get("security_deposit", "").strip()
    deposit = _parse_int(fixed_deposit, 0) if fixed_deposit else rent * deposit_x
    if min(rent, deposit, app_fee, admin, moving, deposit_x) < 0:
        abort(400)
    total = rent + deposit + app_fee + admin + moving
    return render_template("calc_move_in.html", rent=rent, deposit=deposit,
                           fixed_deposit=fixed_deposit, deposit_months=deposit_x,
                           app_fee=app_fee, admin=admin, moving=moving, total=total)


@app.route("/tools/utility-cost", methods=["GET", "POST"])
def calc_utility():
    sqft = _parse_int(request.values.get("sqft"), 800)
    beds = _parse_int(request.values.get("beds"), 1)
    state = (request.values.get("state") or "TX").upper()
    elec = int(0.13 * sqft / 10 + 25)
    gas = int(0.04 * sqft + 18)
    water = 35 + beds * 12
    internet = 75
    total = elec + gas + water + internet
    return render_template("calc_utility.html", sqft=sqft, beds=beds, state=state,
                           elec=elec, gas=gas, water=water, internet=internet,
                           total=total)


@app.route("/tools/mortgage-preapproval", methods=["GET", "POST"])
def mortgage_preapproval():
    if request.method == "POST":
        income = _parse_int(request.form.get("income"), 0)
        credit = _parse_int(request.form.get("credit_score"), 700)
        debts = _parse_int(request.form.get("debts"), 0)
        # rough: 28%/36% DTI, 5.5x annual income, scaled by credit factor
        cred_mult = max(0.6, min(1.15, (credit - 580) / 280))
        loan_max = int(income * 5.5 * cred_mult - debts * 12)
        loan_max = max(0, loan_max)
        flash("Pre-approval estimate generated.", "success")
        return render_template("mortgage_preapproval.html",
                               submitted=True, loan_max=loan_max,
                               credit=credit, income=income, debts=debts)
    return render_template("mortgage_preapproval.html", submitted=False)


# ─── Help center hierarchy ──────────────────────────────────────────────────


HELP_TOPICS = {
    "searching": ("Searching for an Apartment",
        "How to filter, save searches, draw on a map, and get notified about new matches."),
    "touring": ("Touring an Apartment",
        "Schedule a tour, what to ask, in-person vs self-guided vs 3D, what to bring."),
    "applying": ("Applying for an Apartment",
        "Application checklist, what landlords look at, co-signers, and how long it takes."),
    "lease-signing": ("Signing a Lease",
        "Critical clauses, security deposits, addenda, e-signatures."),
    "moving-in": ("Moving In",
        "Move-in inspection, utilities, address changes, renter's insurance."),
    "renting": ("During Your Tenancy",
        "Maintenance requests, paying rent, dealing with noise issues, breaking a lease."),
    "moving-out": ("Moving Out",
        "Notice periods, end-of-lease inspection, getting your deposit back."),
    "account": ("Your Account",
        "Saved searches, alerts, favorites, password reset."),
}


@app.route("/help/<topic>")
def help_topic(topic):
    if topic not in HELP_TOPICS:
        abort(404)
    title, intro = HELP_TOPICS[topic]
    related = [k for k in HELP_TOPICS if k != topic][:4]
    return render_template("help_topic.html", topic=topic, title=title,
                           intro=intro, related=related, topics=HELP_TOPICS)


# ─── Renters guide author profile ───────────────────────────────────────────


@app.route("/renters-guide/author/<slug>")
def author_profile(slug):
    a = Author.query.filter_by(slug=slug).first_or_404()
    articles = Article.query.filter_by(author=a.name)\
        .order_by(Article.published_at.desc()).all()
    return render_template("author_profile.html", a=a, articles=articles)


# ─── Property manager profile ───────────────────────────────────────────────


@app.route("/property-manager/<slug>")
def property_manager_profile(slug):
    p = PropertyManagerProfile.query.filter_by(slug=slug).first_or_404()
    portfolio = Building.query.filter_by(property_manager=p.name)\
        .order_by(Building.rating_avg.desc()).limit(40).all()
    return render_template("property_manager.html", p=p, portfolio=portfolio)


# ─── Reviews helpful / report ───────────────────────────────────────────────


@app.route("/review/<int:rid>/helpful", methods=["POST"])
def review_helpful(rid):
    r = Review.query.get_or_404(rid)
    if current_user.is_authenticated:
        existing = ReviewHelpful.query.filter_by(
            review_id=r.id, user_id=current_user.id
        ).first()
        if not existing:
            db.session.add(ReviewHelpful(review_id=r.id, user_id=current_user.id))
            r.helpful_count = (r.helpful_count or 0) + 1
            db.session.commit()
    else:
        r.helpful_count = (r.helpful_count or 0) + 1
        db.session.commit()
    return redirect(request.referrer or url_for("index"))


@app.route("/review/<int:rid>/report", methods=["POST"])
def review_report(rid):
    r = Review.query.get_or_404(rid)
    rep = ReviewReport(
        review_id=r.id,
        user_id=(current_user.id if current_user.is_authenticated else None),
        reason=request.form.get("reason", "")[:80],
        notes=request.form.get("notes", "")[:1000],
    )
    db.session.add(rep)
    db.session.commit()
    flash("Thanks — we'll review the report.", "info")
    return redirect(request.referrer or url_for("index"))


# ─── Saved search edit / frequency ──────────────────────────────────────────


@app.route("/saved-searches/<int:sid>/edit", methods=["POST"])
@login_required
def edit_saved_search(sid):
    s = SavedSearch.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    s.name = request.form.get("name", s.name)[:120] or s.name
    s.email_frequency = request.form.get("email_frequency", "daily")[:20]
    db.session.commit()
    flash("Saved search updated.", "success")
    return redirect(url_for("saved_searches"))


# ─── Notifications inbox ────────────────────────────────────────────────────


@app.route("/notifications")
@login_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).all()
    # Mark all as read on view
    for n in items:
        n.is_read = True
    db.session.commit()
    return render_template("notifications.html", items=items)


@app.route("/account/notifications", methods=["POST"])
@login_required
def account_notifications():
    current_user.notify_tour_confirm = bool(request.form.get("notify_tour_confirm"))
    current_user.notify_application_status = bool(request.form.get("notify_application_status"))
    current_user.notify_price_drop = bool(request.form.get("notify_price_drop"))
    current_user.notify_new_match = bool(request.form.get("notify_new_match"))
    current_user.notify_newsletter = bool(request.form.get("notify_newsletter"))
    db.session.commit()
    flash("Notification preferences saved.", "success")
    return redirect(url_for("account"))


# ─── Glossary / sitemap / misc landings ─────────────────────────────────────


@app.route("/glossary")
def glossary_index():
    rows = GlossaryTerm.query.order_by(GlossaryTerm.term).all()
    letters = sorted({(t.term[:1] or "?").upper() for t in rows})
    return render_template("glossary.html", terms=rows, letters=letters)


@app.route("/glossary/<slug>")
def glossary_term(slug):
    t = GlossaryTerm.query.filter_by(slug=slug).first_or_404()
    related = [GlossaryTerm.query.filter_by(slug=s).first()
               for s in (t.related or "").split(",") if s.strip()]
    related = [r for r in related if r]
    return render_template("glossary_term.html", t=t, related=related)


@app.route("/sitemap")
def sitemap_root():
    cities = City.query.order_by(City.name).all()
    return render_template("sitemap.html", cities=cities,
                           categories=list(CATEGORY_LANDINGS.keys()),
                           help_topics=list(HELP_TOPICS.keys()))


@app.route("/sitemap/<state>")
def sitemap_state(state):
    state = state.upper()
    cities = City.query.filter_by(state=state).order_by(City.name).all()
    if not cities:
        abort(404)
    state_full = cities[0].state_full or state
    nbhds = (Neighborhood.query.join(City, Neighborhood.city_id == City.id)
             .filter(City.state == state).order_by(Neighborhood.name).all())
    return render_template("sitemap_state.html", state=state,
                           state_full=state_full, cities=cities, nbhds=nbhds)


@app.route("/careers")
def careers():
    return render_template("careers.html")


@app.route("/press")
def press():
    return render_template("press.html")


@app.route("/investors")
def investors():
    return render_template("investors.html")


@app.route("/mobile-app")
def mobile_app():
    return render_template("mobile_app.html")


# ─── Blog (Renters Guide) by-category landing ───────────────────────────────


@app.route("/blog")
@app.route("/blog/<category>")
def blog_category(category=""):
    if category:
        cat_name = category.replace("-", " ").title()
        # try common variations
        matches = Article.query.filter(func.lower(Article.category) == cat_name.lower()).all()
        if not matches:
            matches = Article.query.filter(Article.category.like(f"%{cat_name}%")).all()
        articles = matches
    else:
        cat_name = "All Posts"
        articles = Article.query.order_by(Article.published_at.desc()).limit(60).all()
    categories = sorted({c[0] for c in db.session.query(Article.category).distinct().all()})
    return render_template("blog_category.html", articles=articles,
                           categories=categories, current=cat_name)


# ─── Errors ─────────────────────────────────────────────────────────────────


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# ─── Bootstrap ──────────────────────────────────────────────────────────────


# When app.py is run as __main__ (e.g. `python3 app.py`), seed_data's
# `from app import …` would re-execute app.py as the `app` module and trigger
# `from seed_data import …` again before seed_data has finished its top-level
# imports — yielding "partially initialized module 'seed_data'". Aliasing
# the live module under the name `app` makes the import a no-op.
import sys as _sys  # noqa: E402
_sys.modules.setdefault("app", _sys.modules[__name__])

from seed_data import seed_database, seed_benchmark_users  # noqa: E402


def _normalize_seed_db_layout():
    """Re-emit CREATE INDEX statements in alpha order + VACUUM so a fresh
    rebuild produces byte-identical sqlite output. Without this, SQLAlchemy
    emits CREATE INDEX in `Table.indexes` set order — set iteration depends
    on Python `id()` allocation and varies between processes.
    """
    from sqlalchemy import text
    with db.engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND name LIKE 'ix_%'"
        )).fetchall()
        for name, _ in rows:
            conn.execute(text(f'DROP INDEX IF EXISTS "{name}"'))
        for name, sql in sorted(rows, key=lambda r: r[0]):
            if sql:
                conn.execute(text(sql))
    with db.engine.connect() as conn:
        conn.exec_driver_sql("VACUUM")


with app.app_context():
    fresh = not os.path.exists(os.path.join(BASE_DIR, "instance", "apartments_com.db"))
    db.create_all()
    seed_database()
    seed_benchmark_users()
    if fresh:
        _normalize_seed_db_layout()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


# --- perf: long-term cache for /static/ assets (added 2026-05-27) ---
@app.after_request
def _add_static_cache_headers(resp):
    try:
        if request.path.startswith('/static/'):
            resp.headers['Cache-Control'] = 'public, max-age=86400, immutable'
    except Exception:
        pass
    return resp
# --- end perf ---
