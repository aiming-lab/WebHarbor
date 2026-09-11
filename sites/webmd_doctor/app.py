"""WebMD Doctor (doctor.webmd.com, branded "WebMD Care") local mirror for WebHarbor.

Every doctor, practice, hospital, address, phone number, NPI and review is
synthetic. Only the site chrome (layout, colours, icons) mirrors upstream.
"""
from __future__ import annotations

import math
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlencode, urlsplit

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
INSTANCE_DIR = BASE_DIR / "instance"
DB_PATH = INSTANCE_DIR / "webmd_doctor.db"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config.update(
    SECRET_KEY=os.environ.get("WEBMD_DOCTOR_SECRET_KEY", "webharbor-webmd-doctor-dev-key"),
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{DB_PATH}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    WTF_CSRF_TIME_LIMIT=7200,
    MAX_CONTENT_LENGTH=256 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, _record) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = None

SEED_VERSION = "webmd-doctor-v1"
SITE_NAME = "WebMD Care"
PAGE_SIZE = 10
REVIEW_PAGE_SIZE = 5
DEFAULT_DISTANCE = 40
DISTANCE_OPTIONS = (5, 10, 25, 50, 100)
EXPERIENCE_STOPS = ("min", "5", "15", "20", "25", "30", "max")
ANCHOR_LABEL = "Newark, DE 19711"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
MIN_REVIEW_LENGTH = 20
MAX_REVIEW_LENGTH = 2000

PERSPECTIVE_CRITERIA = (
    "Explained conditions and treatments",
    "Answered my questions",
    "Provided follow-up as needed",
    "Gave a thorough Exam",
    "Gave clear instructions",
    "Staff was courteous",
    "Flexible scheduling",
)
DOCTOR_POLL_QUESTIONS = (
    "Was {name}'s check in process easy?",
    "Do you feel {name} listened to your medical concerns?",
    "Did {name} follow-up with you after your initial visit?",
    "Would you recommend {name} to other patients?",
    "Does {name} offer telehealth / virtual visit options?",
)
HOSPITAL_POLL_QUESTIONS = (
    "Would you recommend this hospital to other patients?",
    "Did the doctors at this hospital listen to your medical concerns?",
    "Did doctors from this hospital follow-up with you after your initial visit?",
    "Did the hospital give you clear instructions for recovering at home afterwards?",
    "Were the facilities at this hospital kept clean?",
)
PRACTICE_POLL_QUESTIONS = (
    "Would you recommend this practice to other patients?",
    "Did the doctors at this practice listen to your medical concerns?",
    "Did doctors from this practice follow-up with you after your initial visit?",
    "Did the practice give you clear instructions for recovering at home afterwards?",
    "Were the facilities at this practice kept clean?",
)
# Fixed appointment grid (fidelity: upstream shows a rolling 4-day grid; the
# mirror is pinned to the reference date so every run sees the same slots).
BOOKING_DAYS = (
    ("THU", "SEP 10", date(2026, 9, 10), "Thu, Sep 10"),
    ("FRI", "SEP 11", date(2026, 9, 11), "Fri, Sep 11"),
    ("MON", "SEP 14", date(2026, 9, 14), "Mon, Sep 14"),
    ("TUE", "SEP 15", date(2026, 9, 15), "Tue, Sep 15"),
)
BOOKING_SLOTS = ("9:00 AM", "9:30 AM", "10:00 AM", "10:30 AM", "11:00 AM")
PATIENT_TYPES = ("New Patient", "Returning Patient")
AWARD_CLASSES = {
    "elite": ("Elite", "WebMD Elite Choice award", "WebMD Elite Choice"),
    "patient": ("Patient", "WebMD Patient's Choice award", "WebMD Patient's Choice"),
    "provider": ("Provider", "Medscape Provider Choice award", "Medscape Provider Choice"),
}
AWARD_LINE_BY_CLASS = {value[0]: value[1] for value in AWARD_CLASSES.values()}
BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
SORT_OPTIONS = (
    ("bestmatch", "Best Match"),
    ("distance", "Distance"),
    ("avg_rating", "Average Rating"),
    ("num_rating", "Number of Ratings"),
)
HUB_SORT_OPTIONS = (
    ("bestmatch", "Best Match"),
    ("avg_rating", "Average Rating"),
    ("num_rating", "Number of Ratings"),
)


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class PollMixin:
    poll_q1_yes = db.Column(db.Integer, nullable=False, default=0)
    poll_q1_no = db.Column(db.Integer, nullable=False, default=0)
    poll_q2_yes = db.Column(db.Integer, nullable=False, default=0)
    poll_q2_no = db.Column(db.Integer, nullable=False, default=0)
    poll_q3_yes = db.Column(db.Integer, nullable=False, default=0)
    poll_q3_no = db.Column(db.Integer, nullable=False, default=0)
    poll_q4_yes = db.Column(db.Integer, nullable=False, default=0)
    poll_q4_no = db.Column(db.Integer, nullable=False, default=0)
    poll_q5_yes = db.Column(db.Integer, nullable=False, default=0)
    poll_q5_no = db.Column(db.Integer, nullable=False, default=0)

    def poll_rows(self, questions, name: str = ""):
        rows = []
        for index, question in enumerate(questions, start=1):
            rows.append(
                {
                    "question": question.format(name=name),
                    "yes": getattr(self, f"poll_q{index}_yes"),
                    "no": getattr(self, f"poll_q{index}_no"),
                }
            )
        return rows


class HoursMixin:
    mon_open = db.Column(db.String(16))
    mon_close = db.Column(db.String(16))
    tue_open = db.Column(db.String(16))
    tue_close = db.Column(db.String(16))
    wed_open = db.Column(db.String(16))
    wed_close = db.Column(db.String(16))
    thu_open = db.Column(db.String(16))
    thu_close = db.Column(db.String(16))
    fri_open = db.Column(db.String(16))
    fri_close = db.Column(db.String(16))
    sat_open = db.Column(db.String(16))
    sat_close = db.Column(db.String(16))
    sun_open = db.Column(db.String(16))
    sun_close = db.Column(db.String(16))

    def hours_rows(self):
        rows = []
        for key, label in zip(DAY_KEYS, DAY_LABELS):
            opens = getattr(self, f"{key}_open")
            closes = getattr(self, f"{key}_close")
            rows.append({"day": label, "text": f"{opens} - {closes}" if opens and closes else "Closed"})
        return rows


class Specialty(db.Model):
    __tablename__ = "specialties"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(80), nullable=False, unique=True)
    singular = db.Column(db.String(80), nullable=False)
    plural = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    board_name = db.Column(db.String(120), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)


class Condition(db.Model):
    __tablename__ = "conditions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    specialty_id = db.Column(db.Integer, db.ForeignKey("specialties.id"), nullable=False)
    specialty = db.relationship("Specialty")


class Procedure(db.Model):
    __tablename__ = "procedures"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    specialty_id = db.Column(db.Integer, db.ForeignKey("specialties.id"), nullable=False)
    specialty = db.relationship("Specialty")


class ExpertiseArea(db.Model):
    __tablename__ = "expertise_areas"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    specialty_id = db.Column(db.Integer, db.ForeignKey("specialties.id"), nullable=False)


class Insurer(db.Model):
    __tablename__ = "insurers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(80), nullable=False, unique=True)
    plans = db.relationship("InsurancePlan", back_populates="insurer", order_by="InsurancePlan.id")


class InsurancePlan(db.Model):
    __tablename__ = "insurance_plans"
    id = db.Column(db.Integer, primary_key=True)
    insurer_id = db.Column(db.Integer, db.ForeignKey("insurers.id"), nullable=False)
    plan_type = db.Column(db.String(40), nullable=False, default="")
    insurer = db.relationship("Insurer", back_populates="plans")

    @property
    def label(self) -> str:
        return f"{self.insurer.name} {self.plan_type}".strip()


class City(db.Model):
    __tablename__ = "cities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    state_name = db.Column(db.String(40), nullable=False)
    state_slug = db.Column(db.String(40), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    zips = db.relationship("CityZip", back_populates="city", order_by="CityZip.zip")

    @property
    def label(self) -> str:
        return f"{self.name}, {self.state}"


class CityZip(db.Model):
    __tablename__ = "city_zips"
    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=False)
    zip = db.Column(db.String(5), nullable=False, unique=True)
    city = db.relationship("City", back_populates="zips")


class Hospital(PollMixin, db.Model):
    __tablename__ = "hospitals"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(140), nullable=False, unique=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=False)
    street = db.Column(db.String(120), nullable=False)
    zip = db.Column(db.String(5), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    website = db.Column(db.String(120), nullable=False)
    overview_text = db.Column(db.Text, nullable=False)
    avg_rating = db.Column(db.Float)
    ratings_count = db.Column(db.Integer, nullable=False, default=0)
    city = db.relationship("City")
    doctors = db.relationship("Doctor", back_populates="hospital", order_by="Doctor.last_name")


class Practice(PollMixin, HoursMixin, db.Model):
    __tablename__ = "practices"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(140), nullable=False, unique=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=False)
    street = db.Column(db.String(120), nullable=False)
    zip = db.Column(db.String(5), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    website = db.Column(db.String(120), nullable=False)
    overview_text = db.Column(db.Text, nullable=False)
    avg_rating = db.Column(db.Float)
    ratings_count = db.Column(db.Integer, nullable=False, default=0)
    city = db.relationship("City")
    locations = db.relationship("Location", back_populates="practice", order_by="Location.id")


class Doctor(PollMixin, db.Model):
    __tablename__ = "doctors"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    prefix = db.Column(db.String(8), nullable=False, default="Dr.")
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    degree = db.Column(db.String(8), nullable=False)
    gender = db.Column(db.String(1), nullable=False)
    profile_type = db.Column(db.String(10), nullable=False)
    primary_specialty_id = db.Column(db.Integer, db.ForeignKey("specialties.id"), nullable=False)
    secondary_specialty_id = db.Column(db.Integer, db.ForeignKey("specialties.id"))
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"))
    avg_rating = db.Column(db.Float)
    ratings_count = db.Column(db.Integer, nullable=False, default=0)
    text_review_count = db.Column(db.Integer, nullable=False, default=0)
    years_experience = db.Column(db.Integer, nullable=False)
    graduation_year = db.Column(db.Integer, nullable=False)
    medical_school = db.Column(db.String(120), nullable=False)
    accepting_new_patients = db.Column(db.Boolean, nullable=False, default=True)
    virtual_visit = db.Column(db.Boolean, nullable=False, default=False)
    npi = db.Column(db.String(10), nullable=False, unique=True)
    overview_text = db.Column(db.Text, nullable=False)
    bio_html = db.Column(db.Text)
    avg_wait_minutes = db.Column(db.Integer)
    callout_label = db.Column(db.String(80))
    video_poster_file = db.Column(db.String(160))
    next_available_label = db.Column(db.String(40))
    website_url = db.Column(db.String(160))

    primary_specialty = db.relationship("Specialty", foreign_keys=[primary_specialty_id])
    secondary_specialty = db.relationship("Specialty", foreign_keys=[secondary_specialty_id])
    hospital = db.relationship("Hospital", back_populates="doctors")
    locations = db.relationship(
        "Location", back_populates="doctor", order_by="desc(Location.is_primary), Location.id"
    )
    conditions = db.relationship("DoctorCondition", order_by="DoctorCondition.position")
    procedures = db.relationship("DoctorProcedure", order_by="DoctorProcedure.position")
    expertise = db.relationship("DoctorExpertise", order_by="DoctorExpertise.position")
    insurances = db.relationship("DoctorInsurance", order_by="DoctorInsurance.plan_id")
    reviews = db.relationship("Review", order_by="desc(Review.review_date), Review.id")
    perspectives = db.relationship("DoctorPerspective", order_by="DoctorPerspective.criterion")
    certifications = db.relationship("Certification", order_by="Certification.id")
    licenses = db.relationship("License", order_by="License.id")
    education = db.relationship("Education", order_by="Education.id")
    awards = db.relationship("Award", order_by="Award.id")
    languages = db.relationship("DoctorLanguage", order_by="DoctorLanguage.position")

    @property
    def is_enhanced(self) -> bool:
        return self.profile_type == "Enhanced"

    @property
    def display_name(self) -> str:
        prefix = f"{self.prefix} " if self.prefix else ""
        return f"{prefix}{self.first_name} {self.last_name}, {self.degree}"

    @property
    def short_name(self) -> str:
        prefix = f"{self.prefix} " if self.prefix else ""
        return f"{prefix}{self.last_name}"

    @property
    def full_name(self) -> str:
        prefix = f"{self.prefix} " if self.prefix else ""
        return f"{prefix}{self.first_name} {self.last_name}"

    @property
    def pronoun(self) -> str:
        return {"m": "he", "f": "she"}.get(self.gender, "they")

    @property
    def possessive(self) -> str:
        return {"m": "his", "f": "her"}.get(self.gender, "their")

    @property
    def primary_location(self):
        for location in self.locations:
            if location.is_primary:
                return location
        return self.locations[0] if self.locations else None

    @property
    def other_location_count(self) -> int:
        return max(len(self.locations) - 1, 0)

    @property
    def avatar_path(self) -> str:
        return f"images/avatars/{self.slug}.png"

    @property
    def featured_review(self):
        for review in self.reviews:
            if review.is_featured:
                return review
        return None

    @property
    def card_snippet(self) -> str:
        review = self.featured_review
        text = review.text if review is not None else self.overview_text
        return snippet(text, 150)

    @property
    def award_lines(self) -> list[str]:
        return [AWARD_LINE_BY_CLASS[award.award_class] for award in self.awards]

    @property
    def language_names(self) -> list[str]:
        return [row.language for row in self.languages]

    @property
    def specialty_names(self) -> list[str]:
        names = [self.primary_specialty.name]
        if self.secondary_specialty is not None:
            names.append(self.secondary_specialty.name)
        return names

    def education_rows(self, kind: str):
        return [row for row in self.education if row.kind == kind]

    def insurer_names(self) -> list[str]:
        seen: list[str] = []
        for row in self.insurances:
            name = row.plan.insurer.name
            if name not in seen:
                seen.append(name)
        return seen

    def perspective_summary(self):
        ordered = sorted(self.perspectives, key=lambda row: (-row.did_well, row.criterion))
        return [PERSPECTIVE_CRITERIA[row.criterion - 1] for row in ordered[:4]]


class Location(HoursMixin, db.Model):
    __tablename__ = "locations"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    practice_id = db.Column(db.Integer, db.ForeignKey("practices.id"), nullable=False)
    name = db.Column(db.String(140), nullable=False)
    street = db.Column(db.String(120), nullable=False)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=False)
    zip = db.Column(db.String(5), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    medicare = db.Column(db.Boolean, nullable=False, default=False)
    medicaid = db.Column(db.Boolean, nullable=False, default=False)
    new_patients = db.Column(db.Boolean, nullable=False, default=True)
    doctor = db.relationship("Doctor", back_populates="locations")
    practice = db.relationship("Practice", back_populates="locations")
    city = db.relationship("City")

    @property
    def address_line(self) -> str:
        return f"{self.street}, {self.city.name}, {self.city.state}, {self.zip}"

    @property
    def short_address(self) -> str:
        return f"{self.street}, {self.city.name}, {self.city.state} {self.zip}"


class DoctorCondition(db.Model):
    __tablename__ = "doctor_conditions"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    condition_id = db.Column(db.Integer, db.ForeignKey("conditions.id"), nullable=False)
    tier = db.Column(db.String(16), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    condition = db.relationship("Condition")
    __table_args__ = (db.UniqueConstraint("doctor_id", "condition_id"),)


class DoctorProcedure(db.Model):
    __tablename__ = "doctor_procedures"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    procedure_id = db.Column(db.Integer, db.ForeignKey("procedures.id"), nullable=False)
    tier = db.Column(db.String(16), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    procedure = db.relationship("Procedure")
    __table_args__ = (db.UniqueConstraint("doctor_id", "procedure_id"),)


class DoctorExpertise(db.Model):
    __tablename__ = "doctor_expertise"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    area_id = db.Column(db.Integer, db.ForeignKey("expertise_areas.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    area = db.relationship("ExpertiseArea")
    __table_args__ = (db.UniqueConstraint("doctor_id", "area_id"),)


class DoctorInsurance(db.Model):
    __tablename__ = "doctor_insurances"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("insurance_plans.id"), nullable=False)
    is_verified = db.Column(db.Boolean, nullable=False, default=True)
    plan = db.relationship("InsurancePlan")
    __table_args__ = (db.UniqueConstraint("doctor_id", "plan_id"),)


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    review_date = db.Column(db.Date, nullable=False)
    helpful_count = db.Column(db.Integer, nullable=False, default=0)
    c1 = db.Column(db.Integer, nullable=False, default=1)
    c2 = db.Column(db.Integer, nullable=False, default=1)
    c3 = db.Column(db.Integer, nullable=False, default=1)
    c4 = db.Column(db.Integer, nullable=False, default=1)
    c5 = db.Column(db.Integer, nullable=False, default=1)
    c6 = db.Column(db.Integer, nullable=False, default=1)
    c7 = db.Column(db.Integer, nullable=False, default=1)
    wait_bucket = db.Column(db.String(24), nullable=False, default="")
    is_featured = db.Column(db.Boolean, nullable=False, default=False)

    @property
    def date_label(self) -> str:
        return f"{self.review_date.strftime('%B')} {self.review_date.day}, {self.review_date.year}"

    def criteria_rows(self):
        return [
            (label, getattr(self, f"c{index}") == 1)
            for index, label in enumerate(PERSPECTIVE_CRITERIA, start=1)
        ]


class DoctorPerspective(db.Model):
    __tablename__ = "doctor_perspectives"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    criterion = db.Column(db.Integer, nullable=False)
    did_well = db.Column(db.Integer, nullable=False, default=0)
    needs_improvement = db.Column(db.Integer, nullable=False, default=0)
    __table_args__ = (db.UniqueConstraint("doctor_id", "criterion"),)

    @property
    def label(self) -> str:
        return PERSPECTIVE_CRITERIA[self.criterion - 1]

    @property
    def did_well_percent(self) -> int:
        total = self.did_well + self.needs_improvement
        return int(round(100 * self.did_well / total)) if total else 0


class Certification(db.Model):
    __tablename__ = "certifications"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    issuer = db.Column(db.String(120), nullable=False)
    cert_type = db.Column(db.String(120), nullable=False)
    year = db.Column(db.Integer, nullable=False)


class License(db.Model):
    __tablename__ = "licenses"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    license_type = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(40), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Active")


class Education(db.Model):
    __tablename__ = "education"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    kind = db.Column(db.String(24), nullable=False)
    institution = db.Column(db.String(140), nullable=False)
    year = db.Column(db.Integer, nullable=False)


class Award(db.Model):
    __tablename__ = "awards"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    award_class = db.Column(db.String(16), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    doctor = db.relationship("Doctor", overlaps="awards")


class DoctorLanguage(db.Model):
    __tablename__ = "doctor_languages"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    language = db.Column(db.String(40), nullable=False)
    position = db.Column(db.Integer, nullable=False)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    dob = db.Column(db.Date)
    display_name = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)


class SavedProvider(db.Model):
    __tablename__ = "saved_providers"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    saved_at = db.Column(db.DateTime, nullable=False)
    doctor = db.relationship("Doctor")
    __table_args__ = (db.UniqueConstraint("user_id", "doctor_id"),)


class AppointmentRequest(db.Model):
    __tablename__ = "appointment_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    patient_type = db.Column(db.String(24), nullable=False)
    slot_date = db.Column(db.Date, nullable=False)
    slot_time = db.Column(db.String(12), nullable=False)
    reference = db.Column(db.String(12), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False)
    doctor = db.relationship("Doctor")
    location = db.relationship("Location")

    @property
    def slot_label(self) -> str:
        for _abbr, _short, day, label in BOOKING_DAYS:
            if day == self.slot_date:
                return f"{label} @ {self.slot_time}"
        return f"{self.slot_date.strftime('%a, %b')} {self.slot_date.day} @ {self.slot_time}"


class UserReview(db.Model):
    __tablename__ = "user_reviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    c1 = db.Column(db.Integer, nullable=False, default=1)
    c2 = db.Column(db.Integer, nullable=False, default=1)
    c3 = db.Column(db.Integer, nullable=False, default=1)
    c4 = db.Column(db.Integer, nullable=False, default=1)
    c5 = db.Column(db.Integer, nullable=False, default=1)
    c6 = db.Column(db.Integer, nullable=False, default=1)
    c7 = db.Column(db.Integer, nullable=False, default=1)
    text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(24), nullable=False, default="Pending review")
    created_at = db.Column(db.DateTime, nullable=False)


class SeedMetadata(db.Model):
    __tablename__ = "seed_metadata"
    key = db.Column(db.String(40), primary_key=True)
    value = db.Column(db.String(80), nullable=False)


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def snippet(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + " ..."


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def confirmation_reference(row_id: int, doctor_id: int, office_index: int, slot_date: date, slot_time: str) -> str:
    """Eight base-32 characters packed from the whole booking row with fixed constants (no randomness).

    40 bits: row id (23) | doctor id (10) | office index within the doctor's Locations list (2) |
    booking-grid day and time slot (5), then one odd-multiplier affine step, which is a bijection
    on 40 bits.  The packing is injective for row ids below 2**23 and doctor ids below 2**10, so
    two rows in one database never share a reference and the same row id booked for another
    doctor, office or slot yields a different string.
    """
    day_index = next((i for i, (_a, _s, day, _l) in enumerate(BOOKING_DAYS) if day == slot_date), 0)
    slot_index = BOOKING_SLOTS.index(slot_time) if slot_time in BOOKING_SLOTS else 0
    packed = ((row_id % 2**23) << 17) | ((doctor_id % 2**10) << 7) | ((office_index % 4) << 5) | (day_index * len(BOOKING_SLOTS) + slot_index)
    value = (packed * 0x5A7B3A2B7E15 + 0x2C9F19E37) % (2**40)
    chars = []
    for _ in range(8):
        chars.append(BASE32_ALPHABET[value % 32])
        value //= 32
    return "WMD-" + "".join(reversed(chars))


def office_index(doctor: Doctor, location: Location) -> int:
    """Position of `location` in the doctor's Locations list (primary office first)."""
    return [row.id for row in doctor.locations].index(location.id)


def safe_next(raw: str | None) -> str | None:
    """Return a same-origin relative path (with query) or ``None``."""
    if not raw or len(raw) > 2048 or any(ord(char) < 32 for char in raw):
        return None
    decoded = raw
    for _ in range(3):
        expanded = unquote(decoded)
        if expanded == decoded:
            break
        decoded = expanded
    if decoded.startswith("//") or "\\" in decoded:
        return None
    parsed = urlsplit(decoded)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return None
    return parsed.path + (("?" + parsed.query) if parsed.query else "")


def single_arg(name: str, default: str = "") -> str:
    values = request.args.getlist(name)
    return values[0].strip() if values else default


def int_arg(name: str, default: int, minimum: int = 1, maximum: int = 10**6) -> int:
    raw = single_arg(name, "")
    if not raw.isdigit():
        return default
    return min(max(int(raw), minimum), maximum)


def bool_arg(name: str) -> bool:
    return single_arg(name, "").lower() in ("true", "1", "yes", "on")


def paginate(items: list, page: int, size: int = PAGE_SIZE):
    total = len(items)
    pages = max(1, math.ceil(total / size))
    page = min(max(page, 1), pages)
    start = (page - 1) * size
    return {
        "rows": items[start:start + size],
        "page": page,
        "pages": pages,
        "total": total,
        "start": start + 1 if total else 0,
        "end": min(start + size, total),
        "numbers": page_numbers(page, pages),
    }


def page_numbers(page: int, pages: int) -> list:
    if pages <= 7:
        return list(range(1, pages + 1))
    numbers = {1, 2, pages - 1, pages, page - 1, page, page + 1}
    ordered = sorted(n for n in numbers if 1 <= n <= pages)
    result = []
    previous = 0
    for number in ordered:
        if number - previous > 1:
            result.append(None)
        result.append(number)
        previous = number
    return result


def anchor_city() -> City:
    return City.query.filter_by(slug="newark", state="DE").one()


def location_choices() -> list[dict]:
    choices = []
    for city in City.query.order_by(City.state, City.name).all():
        for row in city.zips:
            choices.append({"label": f"{city.name}, {city.state} {row.zip}", "zip": row.zip})
    return choices


def resolve_location(loc: str, zc: str = "", city_name: str = "", state: str = "") -> dict:
    """Resolve the location input to a seeded city; unknown input falls back to the anchor."""
    anchor = anchor_city()
    raw = (loc or "").strip()
    zip_code = zc.strip()
    if not zip_code:
        match = re.search(r"\b(\d{5})\b", raw)
        if match:
            zip_code = match.group(1)
    if zip_code:
        row = CityZip.query.filter_by(zip=zip_code).first()
        if row is not None:
            return {"city": row.city, "zip": row.zip, "label": f"{row.city.name}, {row.city.state} {row.zip}", "fallback": False, "input": raw}
    name = city_name.strip()
    state_code = state.strip().upper()
    if not name and raw:
        parts = [part.strip() for part in re.split(r"[,]", raw) if part.strip()]
        if parts:
            name = parts[0]
            if len(parts) > 1:
                state_code = parts[1].split()[0].upper() if parts[1].split() else ""
    if name:
        query = City.query.filter(db.func.lower(City.name) == name.lower())
        if state_code:
            query = query.filter(City.state == state_code)
        city = query.order_by(City.id).first()
        if city is not None:
            first_zip = city.zips[0].zip if city.zips else ""
            return {"city": city, "zip": first_zip, "label": f"{city.name}, {city.state} {first_zip}".strip(), "fallback": False, "input": raw}
    if not raw and not zip_code and not name:
        return {"city": anchor, "zip": "19711", "label": ANCHOR_LABEL, "fallback": False, "input": raw}
    return {"city": anchor, "zip": "19711", "label": ANCHOR_LABEL, "fallback": True, "input": raw or zip_code or name}


def search_vocabulary() -> list[tuple[str, str, object]]:
    """(lower-cased term, kind, value) sorted longest first for the query parser."""
    entries: list[tuple[str, str, object]] = []
    for specialty in Specialty.query.order_by(Specialty.id).all():
        for term in (specialty.name, specialty.singular, specialty.plural):
            entries.append((term.lower(), "sids", specialty.id))
    for condition in Condition.query.order_by(Condition.id).all():
        entries.append((condition.name.lower(), "cid", condition.id))
    for procedure in Procedure.query.order_by(Procedure.id).all():
        entries.append((procedure.name.lower(), "pid", procedure.id))
    for insurer in Insurer.query.order_by(Insurer.id).all():
        entries.append((insurer.name.lower(), "insuranceid", insurer.id))
    for term, value in (("female", "f"), ("male", "m"), ("non-binary", "n"), ("nonbinary", "n")):
        entries.append((term, "gender", value))
    for term in ("virtual", "telehealth", "video visit"):
        entries.append((term, "isvirtualvisit", True))
    entries.sort(key=lambda entry: (-len(entry[0]), entry[0]))
    return entries


def resolve_query(q: str) -> dict:
    """Deterministic longest-match-first parse of the search term (no fuzziness)."""
    resolved: dict = {"sids": None, "cid": None, "pid": None, "insuranceid": None, "gender": None, "isvirtualvisit": False, "matched": []}
    text = " " + re.sub(r"\s+", " ", (q or "").lower()).strip() + " "
    for term, kind, value in search_vocabulary():
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        match = re.search(pattern, text)
        if match is None:
            continue
        if kind == "isvirtualvisit":
            resolved["isvirtualvisit"] = True
        elif resolved[kind] is None:
            resolved[kind] = value
        resolved["matched"].append(term)
        text = text[:match.start()] + " " * (match.end() - match.start()) + text[match.end():]
    return resolved


def parse_experience(raw: str) -> tuple[int | None, int | None]:
    if not raw or "_" not in raw:
        return None, None
    low, high = raw.split("_", 1)
    if low not in EXPERIENCE_STOPS or high not in EXPERIENCE_STOPS:
        return None, None
    low_value = None if low == "min" else int(low)
    high_value = None if high == "max" else int(high)
    if low_value is not None and high_value is not None and low_value > high_value:
        return None, None
    return low_value, high_value


def read_search_params(fixed: dict | None = None) -> dict:
    """Collect the filter parameters for a results-style page."""
    fixed = fixed or {}
    q = single_arg("q", "")[:160]
    resolved = resolve_query(q)
    sids_raw = single_arg("sids", "")
    sids = int(sids_raw) if sids_raw.isdigit() else resolved["sids"]
    cid_raw = single_arg("cid", "")
    pid_raw = single_arg("pid", "")
    insurer_raw = single_arg("insuranceid", "")
    gender = single_arg("gender", "").lower()
    if gender not in ("m", "f", "n"):
        gender = resolved["gender"] or "all"
    sort = single_arg("sortby", "bestmatch")
    if sort not in {key for key, _label in SORT_OPTIONS}:
        sort = "bestmatch"
    distance = int_arg("d", DEFAULT_DISTANCE, 1, 100)
    if single_arg("d", "") and distance not in DISTANCE_OPTIONS:
        distance = DEFAULT_DISTANCE
    minrating = int_arg("minrating", 0, 1, 5) if single_arg("minrating", "").isdigit() else 0
    exp_raw = single_arg("exp", "")
    exp_min, exp_max = parse_experience(exp_raw)
    params = {
        "q": q,
        "resolved": resolved,
        "sids": fixed.get("sids", sids),
        "cid": int(cid_raw) if cid_raw.isdigit() else resolved["cid"],
        "pid": int(pid_raw) if pid_raw.isdigit() else resolved["pid"],
        "insuranceid": int(insurer_raw) if insurer_raw.isdigit() else resolved["insuranceid"],
        "gender": gender,
        "isvirtualvisit": bool_arg("isvirtualvisit") or resolved["isvirtualvisit"],
        "newpatient": bool_arg("newpatient"),
        "medicare": bool_arg("medicare"),
        "medicaid": bool_arg("medicaid"),
        "minrating": minrating,
        "d": distance,
        "exp": exp_raw if (exp_min is not None or exp_max is not None) else "",
        "exp_min": exp_min,
        "exp_max": exp_max,
        "sortby": sort,
        "page": int_arg("page", 1, 1, 10**4),
        "city_id": fixed.get("city_id"),
        "state": fixed.get("state"),
        "use_distance": fixed.get("use_distance", True),
    }
    return params


def match_score(doctor: Doctor, params: dict, condition_ids: set, procedure_ids: set, insurer_ids: set) -> int:
    score = 0
    if params["sids"] is not None:
        if doctor.primary_specialty_id == params["sids"]:
            score += 3
        elif doctor.secondary_specialty_id == params["sids"]:
            score += 2
    if params["cid"] is not None and params["cid"] in condition_ids:
        score += 1
    if params["pid"] is not None and params["pid"] in procedure_ids:
        score += 1
    if params["insuranceid"] is not None and params["insuranceid"] in insurer_ids:
        score += 1
    return score


def rank(rows: list[dict], sortby: str) -> list[dict]:
    """Pure ordering of matched rows. Nulls (unrated) sort last under every sort."""
    def rating_key(row):
        rating = row["doctor"].avg_rating
        return (0, -rating) if rating is not None else (1, 0.0)

    if sortby == "distance":
        key = lambda row: (row["distance"], row["doctor"].id)
    elif sortby == "avg_rating":
        key = lambda row: (rating_key(row), row["doctor"].id)
    elif sortby == "num_rating":
        key = lambda row: (-row["doctor"].ratings_count, row["doctor"].id)
    else:
        key = lambda row: (-row["score"], rating_key(row), -row["doctor"].ratings_count, row["doctor"].id)
    return sorted(rows, key=key)


def search_doctors(params: dict, center: City) -> list[dict]:
    """Apply the conjunctive filters, compute distance + match score, return ranked rows."""
    query = Doctor.query
    if params["sids"] is not None:
        query = query.filter(db.or_(Doctor.primary_specialty_id == params["sids"], Doctor.secondary_specialty_id == params["sids"]))
    if params["gender"] in ("m", "f", "n"):
        query = query.filter(Doctor.gender == params["gender"])
    if params["isvirtualvisit"]:
        query = query.filter(Doctor.virtual_visit.is_(True))
    if params["newpatient"]:
        query = query.filter(Doctor.accepting_new_patients.is_(True))
    if params["minrating"]:
        query = query.filter(Doctor.avg_rating.isnot(None), Doctor.avg_rating >= params["minrating"])
    if params["exp_min"] is not None:
        query = query.filter(Doctor.years_experience >= params["exp_min"])
    if params["exp_max"] is not None:
        query = query.filter(Doctor.years_experience <= params["exp_max"])
    if params["cid"] is not None:
        query = query.filter(Doctor.conditions.any(DoctorCondition.condition_id == params["cid"]))
    if params["pid"] is not None:
        query = query.filter(Doctor.procedures.any(DoctorProcedure.procedure_id == params["pid"]))
    if params["insuranceid"] is not None:
        query = query.filter(Doctor.insurances.any(DoctorInsurance.plan.has(InsurancePlan.insurer_id == params["insuranceid"])))
    primary = Location.is_primary.is_(True)
    location_filters = [primary]
    if params["medicare"]:
        location_filters.append(Location.medicare.is_(True))
    if params["medicaid"]:
        location_filters.append(Location.medicaid.is_(True))
    if params["city_id"] is not None:
        location_filters.append(Location.city_id == params["city_id"])
    if params["state"]:
        location_filters.append(Location.city.has(City.state == params["state"]))
    query = query.filter(Doctor.locations.any(db.and_(*location_filters)))
    rows = []
    for doctor in query.order_by(Doctor.id).all():
        location = doctor.primary_location
        distance = haversine_miles(center.lat, center.lon, location.lat, location.lon)
        if params["use_distance"] and distance > params["d"]:
            continue
        condition_ids = {row.condition_id for row in doctor.conditions} if params["cid"] is not None else set()
        procedure_ids = {row.procedure_id for row in doctor.procedures} if params["pid"] is not None else set()
        insurer_ids = {row.plan.insurer_id for row in doctor.insurances} if params["insuranceid"] is not None else set()
        rows.append({
            "doctor": doctor,
            "distance": distance,
            "score": match_score(doctor, params, condition_ids, procedure_ids, insurer_ids),
        })
    return rank(rows, params["sortby"])


def filter_query_string(params: dict, **overrides) -> str:
    """Rebuild the query string for filter/sort/pagination links."""
    values = {
        "q": params["q"],
        "loc": params.get("loc_label", ""),
        "sortby": params["sortby"] if params["sortby"] != "bestmatch" else "",
        "minrating": params["minrating"] or "",
        "newpatient": "true" if params["newpatient"] else "",
        "insuranceid": params["insuranceid"] or "",
        "medicare": "true" if params["medicare"] else "",
        "medicaid": "true" if params["medicaid"] else "",
        "d": params["d"] if params["use_distance"] and params["d"] != DEFAULT_DISTANCE else "",
        "exp": params["exp"],
        "gender": params["gender"] if params["gender"] != "all" else "",
        "isvirtualvisit": "true" if params["isvirtualvisit"] else "",
        "cid": params["cid"] or "",
        "pid": params["pid"] or "",
        "page": "",
    }
    if params.get("sids_explicit"):
        values["sids"] = params["sids"]
    values.update(overrides)
    clean = {key: value for key, value in values.items() if value not in ("", None, False)}
    return urlencode(clean)


def search_heading_term(params: dict) -> str:
    if params["sids"] is not None:
        specialty = db.session.get(Specialty, params["sids"])
        if specialty is not None:
            return specialty.singular
    if params["cid"] is not None:
        condition = db.session.get(Condition, params["cid"])
        if condition is not None:
            return condition.name
    if params["pid"] is not None:
        procedure = db.session.get(Procedure, params["pid"])
        if procedure is not None:
            return procedure.name
    if params["insuranceid"] is not None:
        insurer = db.session.get(Insurer, params["insuranceid"])
        if insurer is not None:
            return f"Providers accepting {insurer.name}"
    return params["q"].strip() or "All Providers"


def unmatched_search_text(params: dict) -> str:
    """The typed search text when none of it resolved to a seeded vocabulary term."""
    text = params["q"].strip()
    if not text or params.get("resolved") is None or params["resolved"]["matched"]:
        return ""
    if any(params[key] is not None for key in ("sids", "cid", "pid", "insuranceid")):
        return ""
    return text


def filter_bar_context(params: dict, *, show_distance: bool = True) -> dict:
    return {
        "params": params,
        "insurers": Insurer.query.order_by(Insurer.name).all(),
        "sort_options": SORT_OPTIONS,
        "distance_options": DISTANCE_OPTIONS,
        "experience_stops": EXPERIENCE_STOPS,
        "show_distance": show_distance,
        "qs": lambda **overrides: filter_query_string(params, **overrides),
    }


def saved_doctor_ids() -> set[int]:
    if not current_user.is_authenticated:
        return set()
    return {row.doctor_id for row in SavedProvider.query.filter_by(user_id=current_user.id).all()}


def hub_sorted(items: list, sortby: str, minrating: int) -> list:
    if minrating:
        items = [item for item in items if item.avg_rating is not None and item.avg_rating >= minrating]

    def rating_key(item):
        return (0, -item.avg_rating) if item.avg_rating is not None else (1, 0.0)

    if sortby == "avg_rating":
        return sorted(items, key=lambda item: (rating_key(item), item.id))
    if sortby == "num_rating":
        return sorted(items, key=lambda item: (-item.ratings_count, item.id))
    return sorted(items, key=lambda item: (item.name.lower(), item.id))


def states_with_counts(rows: list) -> list[dict]:
    """rows: (state, state_name, state_slug) tuples with duplicates -> ordered unique with counts."""
    counts: dict = {}
    for state, state_name, state_slug in rows:
        entry = counts.setdefault(state, {"state": state, "name": state_name, "slug": state_slug, "count": 0})
        entry["count"] += 1
    return sorted(counts.values(), key=lambda entry: entry["name"])


def specialties_for_menu():
    return Specialty.query.order_by(Specialty.display_order, Specialty.name).all()


@app.context_processor
def inject_globals():
    return {
        "site_name": SITE_NAME,
        "menu_specialties": specialties_for_menu(),
        "anchor_label": ANCHOR_LABEL,
        "location_choices": location_choices(),
        "sort_options": SORT_OPTIONS,
        "hub_sort_options": HUB_SORT_OPTIONS,
        "perspective_criteria": PERSPECTIVE_CRITERIA,
        "award_classes": AWARD_CLASSES,
        "current_year": 2026,
    }


@app.template_filter("stars")
def stars_filter(value):
    """Return a list of 'full' / 'half' / 'empty' for a 1dp rating."""
    if value is None:
        return ["off"] * 5
    result = []
    for index in range(1, 6):
        if value >= index - 0.25:
            result.append("full")
        elif value >= index - 0.75:
            result.append("half")
        else:
            result.append("off")
    return result


@app.template_filter("rating1")
def rating1_filter(value):
    return "0" if value is None else f"{value:.1f}"


@app.template_filter("miles")
def miles_filter(value):
    return f"{value:.2f} miles"


@app.template_filter("plural_word")
def plural_word_filter(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


# --------------------------------------------------------------------------- #
# Public pages
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    specialties = specialties_for_menu()
    top_doctors = (
        Doctor.query.filter(Doctor.avg_rating.isnot(None))
        .order_by(Doctor.avg_rating.desc(), Doctor.ratings_count.desc(), Doctor.id)
        .limit(3)
        .all()
    )
    typeahead = {
        "specialty": [{"label": s.singular, "href": url_for("results", q=s.singular)} for s in specialties],
        "condition": [{"label": c.name, "href": url_for("results", q=c.name)} for c in Condition.query.order_by(Condition.name).all()],
        "practice": [{"label": p.name, "href": url_for("practice_detail", slug=p.slug)} for p in Practice.query.order_by(Practice.name).all()],
    }
    preset_chips = [
        ("Cardiologist", url_for("results", q="Cardiologist")),
        ("Dermatologists who treat children", url_for("results", q="Dermatologist", cid=Condition.query.filter_by(slug="eczema").first().id if Condition.query.filter_by(slug="eczema").first() else None)),
        ("Female OBGYNs", url_for("results", q="Obstetrics & Gynecology", gender="f")),
        ("Neurologists who take UnitedHealthcare", url_for("results", q="Neurologist UnitedHealthcare")),
    ]
    return render_template(
        "index.html",
        specialties=specialties,
        top_doctors=top_doctors,
        typeahead=typeahead,
        preset_chips=preset_chips,
        saved_ids=saved_doctor_ids(),
    )


@app.route("/results")
def results():
    params = read_search_params()
    params["sids_explicit"] = single_arg("sids", "").isdigit()
    loc = resolve_location(single_arg("loc", ""), single_arg("zc", ""), single_arg("city", ""), single_arg("state", ""))
    params["loc_label"] = loc["label"]
    unmatched_q = unmatched_search_text(params)
    rows = [] if unmatched_q else search_doctors(params, loc["city"])  # nothing resolved -> upstream-style empty state
    page = paginate(rows, params["page"])
    term = search_heading_term(params)
    return render_template(
        "results.html",
        params=params,
        loc=loc,
        page=page,
        term=term,
        unmatched_q=unmatched_q,
        heading_place=loc["label"],
        filter_bar=filter_bar_context(params, show_distance=True),
        saved_ids=saved_doctor_ids(),
        base_path=url_for("results"),
        page_qs=lambda n: filter_query_string(params, page=n),
    )


def doctor_or_404(slug: str) -> Doctor:
    doctor = Doctor.query.filter_by(slug=slug).first()
    if doctor is None:
        abort(404)
    return doctor


@app.route("/doctor/<slug>-locations")
@app.route("/doctor/<slug>-reviews")
@app.route("/doctor/<slug>-insurance")
def doctor_tab_alias(slug: str):
    doctor_or_404(slug)
    return redirect(url_for("doctor_profile", slug=slug), code=301)


@app.route("/doctor/<slug>-overview")
def doctor_profile(slug: str):
    doctor = doctor_or_404(slug)
    primary = doctor.primary_location
    reviews_page = paginate(list(doctor.reviews), int_arg("rpage", 1, 1, 10**4), REVIEW_PAGE_SIZE)
    if doctor.is_enhanced:
        rail_title = "Other Providers at This Practice"
        colleagues = practice_colleagues(doctor, primary.practice_id, limit=10)
    else:
        if doctor.hospital is not None:
            rail_title = f"Other Providers at {doctor.hospital.name}"
            colleagues = [d for d in doctor.hospital.doctors if d.id != doctor.id][:10]
        else:
            rail_title = "Other Providers at This Practice"
            colleagues = practice_colleagues(doctor, primary.practice_id, limit=10)
    nearby_cities = [
        city for city in City.query.order_by(City.state, City.name).all() if city.id != primary.city_id
    ]
    user_review = None
    is_saved = False
    if current_user.is_authenticated:
        user_review = UserReview.query.filter_by(user_id=current_user.id, doctor_id=doctor.id).order_by(UserReview.id.desc()).first()
        is_saved = SavedProvider.query.filter_by(user_id=current_user.id, doctor_id=doctor.id).first() is not None
    top_conditions = doctor.conditions[:5]
    more_conditions = doctor.conditions[5:]
    top_procedures = doctor.procedures[:5]
    more_procedures = doctor.procedures[5:]
    insurer_names = doctor.insurer_names()
    return render_template(
        "doctor.html",
        doctor=doctor,
        primary=primary,
        reviews_page=reviews_page,
        rail_title=rail_title,
        colleagues=colleagues,
        nearby_cities=nearby_cities,
        user_review=user_review,
        is_saved=is_saved,
        top_conditions=top_conditions,
        more_conditions=more_conditions,
        top_procedures=top_procedures,
        more_procedures=more_procedures,
        insurer_names=insurer_names,
        booking_days=BOOKING_DAYS,
        booking_slots=BOOKING_SLOTS,
        poll_rows=doctor.poll_rows(DOCTOR_POLL_QUESTIONS, doctor.short_name),
        fellowships=doctor.education_rows("Fellowship"),
        residencies=doctor.education_rows("Residency"),
        schools=doctor.education_rows("Medical School"),
        base_path=url_for("doctor_profile", slug=slug),
        page_qs=lambda n: urlencode({"rpage": n}),
    )


def practice_colleagues(doctor: Doctor, practice_id: int, limit: int) -> list[Doctor]:
    rows = (
        Location.query.filter(Location.practice_id == practice_id, Location.doctor_id != doctor.id)
        .order_by(Location.doctor_id)
        .all()
    )
    seen: list[Doctor] = []
    for row in rows:
        if row.doctor not in seen:
            seen.append(row.doctor)
    seen.sort(key=lambda d: (d.last_name, d.first_name, d.id))
    return seen[:limit]


@app.route("/doctor/<slug>/bookappointment", methods=["GET", "POST"])
def book_appointment(slug: str):
    doctor = doctor_or_404(slug)
    if not doctor.is_enhanced:
        abort(404)
    if not current_user.is_authenticated:
        return redirect(url_for("login", next=url_for("book_appointment", slug=slug)))
    errors: list[str] = []
    form = {
        "patient_type": request.form.get("patient_type", "").strip(),
        "location_id": request.form.get("location_id", "").strip(),
        "slot": request.form.get("slot", "").strip(),
    }
    if request.method == "POST":
        location = None
        if form["location_id"].isdigit():
            location = next((row for row in doctor.locations if row.id == int(form["location_id"])), None)
        if location is None:
            errors.append("Choose one of the provider's locations.")
        if form["patient_type"] not in PATIENT_TYPES:
            errors.append("Tell us whether this appointment is for a new or returning patient.")
        slot_date = slot_time = None
        if "|" in form["slot"]:
            raw_date, raw_time = form["slot"].split("|", 1)
            for _abbr, _short, day, _label in BOOKING_DAYS:
                if day.isoformat() == raw_date and raw_time in BOOKING_SLOTS:
                    slot_date, slot_time = day, raw_time
        if slot_date is None:
            errors.append("Pick an appointment time from the calendar.")
        if not errors:
            booking = AppointmentRequest(
                user_id=current_user.id,
                doctor_id=doctor.id,
                location_id=location.id,
                patient_type=form["patient_type"],
                slot_date=slot_date,
                slot_time=slot_time,
                reference="pending",
                created_at=datetime.now(),
            )
            db.session.add(booking)
            db.session.flush()
            booking.reference = confirmation_reference(booking.id, doctor.id, office_index(doctor, location), slot_date, slot_time)
            db.session.commit()
            return render_template("book_confirm.html", doctor=doctor, booking=booking)
    return render_template(
        "book.html",
        doctor=doctor,
        errors=errors,
        form=form,
        booking_days=BOOKING_DAYS,
        booking_slots=BOOKING_SLOTS,
        patient_types=PATIENT_TYPES,
    )


@app.route("/doctor/<slug>/save", methods=["POST"])
def save_provider(slug: str):
    doctor = doctor_or_404(slug)
    if not current_user.is_authenticated:
        return redirect(url_for("login", next=url_for("doctor_profile", slug=slug)))
    target = safe_next(request.form.get("next")) or url_for("doctor_profile", slug=slug)
    existing = SavedProvider.query.filter_by(user_id=current_user.id, doctor_id=doctor.id).first()
    if existing is not None:
        db.session.delete(existing)
        db.session.commit()
        flash(f"{doctor.full_name} was removed from your saved providers.", "info")
    else:
        db.session.add(SavedProvider(user_id=current_user.id, doctor_id=doctor.id, saved_at=datetime.now()))
        db.session.commit()
        flash(f"{doctor.full_name} was saved to your providers.", "success")
    return redirect(target)


@app.route("/doctor/<slug>/review", methods=["POST"])
def submit_review(slug: str):
    doctor = doctor_or_404(slug)
    if not current_user.is_authenticated:
        return redirect(url_for("login", next=url_for("doctor_profile", slug=slug) + "#reviews"))
    errors: list[str] = []
    rating_raw = request.form.get("rating", "").strip()
    rating = int(rating_raw) if rating_raw.isdigit() else 0
    if rating < 1 or rating > 5:
        errors.append("Select a star rating from 1 to 5.")
    text = re.sub(r"\s+", " ", request.form.get("text", "")).strip()
    if len(text) < MIN_REVIEW_LENGTH:
        errors.append(f"Your review must be at least {MIN_REVIEW_LENGTH} characters.")
    if len(text) > MAX_REVIEW_LENGTH:
        errors.append(f"Your review must be {MAX_REVIEW_LENGTH} characters or fewer.")
    criteria: dict[str, int] = {}
    for index in range(1, 8):
        value = request.form.get(f"c{index}", "").strip()
        if value not in ("1", "0"):
            errors.append(f"Rate the provider on: {PERSPECTIVE_CRITERIA[index - 1]}.")
        else:
            criteria[f"c{index}"] = int(value)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("doctor_profile", slug=slug) + "#reviews")
    review = UserReview(
        user_id=current_user.id,
        doctor_id=doctor.id,
        rating=rating,
        text=text,
        status="Pending review",
        created_at=datetime.now(),
        **criteria,
    )
    db.session.add(review)
    db.session.commit()
    flash("Thanks — your review is pending", "success")
    return redirect(url_for("doctor_profile", slug=slug) + "#reviews")


@app.route("/providers")
def providers_alias():
    return redirect(url_for("specialty_index"), code=301)


@app.route("/providers/specialty")
def specialty_index():
    specialties = Specialty.query.order_by(Specialty.name).all()
    return render_template("specialty_index.html", specialties=specialties)


def specialty_or_404(spec: str) -> Specialty:
    specialty = Specialty.query.filter_by(slug=spec).first()
    if specialty is None:
        abort(404)
    return specialty


def specialty_doctor_rows(specialty: Specialty):
    query = (
        db.session.query(City.state, City.state_name, City.state_slug, City.name, City.slug, City.id)
        .select_from(Doctor)
        .join(Location, db.and_(Location.doctor_id == Doctor.id, Location.is_primary.is_(True)))
        .join(City, Location.city_id == City.id)
        .filter(Doctor.primary_specialty_id == specialty.id)
    )
    return query.all()


STRIP_RADIUS_MILES = 25.0  # "Highest Rated ... near Newark" strip: the 25-mile ring, not the 40-mile search default


def highest_rated_near_anchor(specialty: Specialty, anchor: City, limit: int, radius: float = STRIP_RADIUS_MILES) -> list[Doctor]:
    """Top-rated doctors of a specialty whose primary office is within `radius` miles of the anchor."""
    rated = (
        Doctor.query.filter(Doctor.primary_specialty_id == specialty.id, Doctor.avg_rating.isnot(None))
        .order_by(Doctor.avg_rating.desc(), Doctor.ratings_count.desc(), Doctor.id)
        .all()
    )
    nearby = []
    for doctor in rated:
        location = doctor.primary_location
        if haversine_miles(anchor.lat, anchor.lon, location.lat, location.lon) <= radius:
            nearby.append(doctor)
        if len(nearby) == limit:
            break
    return nearby


@app.route("/providers/specialty/<spec>")
def specialty_landing(spec: str):
    specialty = specialty_or_404(spec)
    rows = specialty_doctor_rows(specialty)
    states = states_with_counts([(r[0], r[1], r[2]) for r in rows])
    cities: dict = {}
    for state, _sn, state_slug, city_name, city_slug, _cid in rows:
        entry = cities.setdefault((state, city_name), {"state": state, "state_slug": state_slug, "name": city_name, "slug": city_slug, "count": 0})
        entry["count"] += 1
    city_chips = sorted(cities.values(), key=lambda entry: entry["name"])
    anchor = anchor_city()
    highest_rated = highest_rated_near_anchor(specialty, anchor, limit=5)
    rated = [d for d in Doctor.query.filter(Doctor.primary_specialty_id == specialty.id, Doctor.avg_rating.isnot(None)).all()]
    average_rating = round(sum(d.avg_rating for d in rated) / len(rated), 1) if rated else None
    total_ratings = sum(d.ratings_count for d in rated)
    conditions = Condition.query.filter_by(specialty_id=specialty.id).order_by(Condition.id).all()
    procedures = Procedure.query.filter_by(specialty_id=specialty.id).order_by(Procedure.id).all()
    return render_template(
        "specialty_landing.html",
        specialty=specialty,
        states=states,
        city_chips=city_chips,
        highest_rated=highest_rated,
        total=len(rows),
        average_rating=average_rating,
        total_ratings=total_ratings,
        conditions=conditions,
        procedures=procedures,
        anchor=anchor,
        saved_ids=saved_doctor_ids(),
    )


@app.route("/providers/specialty/<spec>/<state>")
def specialty_state(spec: str, state: str):
    specialty = specialty_or_404(spec)
    city = City.query.filter_by(state_slug=state).order_by(City.id).first()
    if city is None:
        abort(404)
    rows = specialty_doctor_rows(specialty)
    state_rows = [r for r in rows if r[2] == state]
    cities: dict = {}
    for _st, _sn, _ss, city_name, city_slug, _cid in state_rows:
        entry = cities.setdefault(city_name, {"name": city_name, "slug": city_slug, "count": 0})
        entry["count"] += 1
    params = read_search_params({"sids": specialty.id, "state": city.state, "use_distance": False})
    params["loc_label"] = ""
    ranked = search_doctors(params, anchor_city())
    page = paginate(ranked, params["page"])
    return render_template(
        "specialty_state.html",
        specialty=specialty,
        state_code=city.state,
        state_name=city.state_name,
        state_slug=state,
        cities=sorted(cities.values(), key=lambda entry: entry["name"]),
        page=page,
        params=params,
        filter_bar=filter_bar_context(params, show_distance=False),
        saved_ids=saved_doctor_ids(),
        base_path=url_for("specialty_state", spec=spec, state=state),
        total=len(state_rows),
        page_qs=lambda n: filter_query_string(params, page=n),
    )


@app.route("/providers/specialty/<spec>/<state>/<city>")
def specialty_city(spec: str, state: str, city: str):
    specialty = specialty_or_404(spec)
    city_row = City.query.filter_by(state_slug=state, slug=city).first()
    if city_row is None:
        abort(404)
    params = read_search_params({"sids": specialty.id, "city_id": city_row.id, "use_distance": True})
    params["loc_label"] = ""
    ranked = search_doctors(params, city_row)
    page = paginate(ranked, params["page"])
    conditions = Condition.query.filter_by(specialty_id=specialty.id).order_by(Condition.id).limit(3).all()
    procedures = Procedure.query.filter_by(specialty_id=specialty.id).order_by(Procedure.id).limit(3).all()
    all_rows = search_doctors(read_search_params({"sids": specialty.id, "city_id": city_row.id, "use_distance": False}) | {"page": 1}, city_row)
    experience = [row["doctor"].years_experience for row in all_rows]
    average_experience = round(sum(experience) / len(experience)) if experience else 0
    total_reviews = sum(row["doctor"].ratings_count for row in all_rows)
    accepting = sum(1 for row in all_rows if row["doctor"].accepting_new_patients)
    return render_template(
        "specialty_city.html",
        specialty=specialty,
        city=city_row,
        page=page,
        params=params,
        filter_bar=filter_bar_context(params, show_distance=True),
        saved_ids=saved_doctor_ids(),
        base_path=url_for("specialty_city", spec=spec, state=state, city=city),
        related_specialties=[row for row in specialties_for_menu() if row.id != specialty.id],
        all_conditions=Condition.query.filter_by(specialty_id=specialty.id).order_by(Condition.id).all(),
        all_procedures=Procedure.query.filter_by(specialty_id=specialty.id).order_by(Procedure.id).all(),
        page_qs=lambda n: filter_query_string(params, page=n),
        total=len(all_rows),
        average_experience=average_experience,
        total_reviews=total_reviews,
        accepting=accepting,
        conditions=conditions,
        procedures=procedures,
    )


HUB_CARE_TYPES = (
    ("Cardiology", "cardiovascular-disease"), ("Gastroenterology", "gastroenterology"), ("Neurology", "neurology"),
    ("Orthopedics", "orthopedic-surgery"), ("Psychiatry", "psychiatry"),
)


def hub_counts(kind: str, items: list) -> dict:
    counts = {}
    for item in items:
        if kind == "hospitals":
            doctors = item.doctors
        else:
            doctors = list({loc.doctor_id: loc.doctor for loc in item.locations}.values())
        counts[item.id] = {"physicians": len(doctors), "specialties": len({d.primary_specialty_id for d in doctors})}
    return counts


def hub_page(kind: str, state_slug: str | None):
    model = Hospital if kind == "hospitals" else Practice
    items = model.query.all()
    states = states_with_counts([(item.city.state, item.city.state_name, item.city.state_slug) for item in items])
    if state_slug is None:
        anchor = anchor_city()
        in_state = [item for item in items if item.city.state == anchor.state]
        top_items = hub_sorted(in_state, "avg_rating", 0)[:4]
        return render_template(
            "hub_index.html",
            kind=kind,
            title="Hospitals" if kind == "hospitals" else "Group Practices",
            states=states,
            total=len(items),
            anchor=anchor,
            top_items=top_items,
            counts=hub_counts(kind, top_items),
            care_types=HUB_CARE_TYPES,
        )
    city = City.query.filter_by(state_slug=state_slug).order_by(City.id).first()
    if city is None:
        abort(404)
    state_name, state_code = city.state_name, city.state
    items = [item for item in items if item.city.state == state_code]
    name_filter = single_arg("name", "").strip()[:80]
    if name_filter:
        items = [item for item in items if name_filter.lower() in item.name.lower()]
    sortby = single_arg("sortby", "bestmatch")
    if sortby not in {key for key, _label in HUB_SORT_OPTIONS}:
        sortby = "bestmatch"
    minrating = int_arg("minrating", 0, 1, 5) if single_arg("minrating", "").isdigit() else 0
    ordered = hub_sorted(items, sortby, minrating)
    page = paginate(ordered, int_arg("page", 1, 1, 10**4))
    counts = hub_counts(kind, page["rows"])
    return render_template(
        "hub_list.html",
        name_filter=name_filter,
        kind=kind,
        title="Hospitals" if kind == "hospitals" else "Group Practices",
        noun="Hospital" if kind == "hospitals" else "Group Practice",
        state_name=state_name,
        state_code=state_code,
        state_slug=state_slug,
        states=states,
        page=page,
        counts=counts,
        sortby=sortby,
        minrating=minrating,
        city_count=len({item.city_id for item in items}),
        total=len(items),
        base_path=url_for(f"{kind}_state", state=state_slug),
        page_qs=lambda n: urlencode({k: v for k, v in (("name", name_filter), ("sortby", sortby if sortby != "bestmatch" else ""), ("minrating", minrating or ""), ("page", n)) if v not in ("", None)}),
    )


@app.route("/hospitals")
def hospitals_index():
    return hub_page("hospitals", None)


@app.route("/hospitals/<state>")
def hospitals_state(state: str):
    return hub_page("hospitals", state)


@app.route("/grouppractices")
def grouppractices_index():
    return hub_page("grouppractices", None)


@app.route("/grouppractices/<state>")
def grouppractices_state(state: str):
    return hub_page("grouppractices", state)


def specialty_counts(doctors: list[Doctor]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for doctor in doctors:
        counts[doctor.primary_specialty.name] = counts.get(doctor.primary_specialty.name, 0) + 1
    return sorted(counts.items())


@app.route("/hospital/<slug>")
def hospital_detail(slug: str):
    hospital = Hospital.query.filter_by(slug=slug).first()
    if hospital is None:
        abort(404)
    doctors = sorted(hospital.doctors, key=lambda d: (d.last_name.lower(), d.first_name.lower(), d.id))
    specialty_filter = single_arg("specialty", "")
    specialty_options = sorted({d.primary_specialty for d in doctors}, key=lambda s: s.name)
    if specialty_filter not in {s.slug for s in specialty_options}:
        specialty_filter = ""
    listed = [d for d in doctors if not specialty_filter or d.primary_specialty.slug == specialty_filter]
    page = paginate(listed, int_arg("pagenumber", 1, 1, 10**4))
    return render_template(
        "hospital.html",
        hospital=hospital,
        page=page,
        specialty_filter=specialty_filter,
        specialty_options=specialty_options,
        doctors=doctors,
        specialty_rows=specialty_counts(doctors),
        poll_rows=hospital.poll_rows(HOSPITAL_POLL_QUESTIONS),
        top_specialties=[name for name, _count in sorted(specialty_counts(doctors), key=lambda row: (-row[1], row[0]))[:4]],
        award_count=sum(len(d.awards) for d in doctors),
        base_path=url_for("hospital_detail", slug=slug),
        page_qs=lambda n: urlencode({k: v for k, v in (("specialty", specialty_filter), ("pagenumber", n)) if v}),
    )


@app.route("/practice/<slug>")
def practice_detail(slug: str):
    practice = Practice.query.filter_by(slug=slug).first()
    if practice is None:
        abort(404)
    by_id: dict[int, Doctor] = {}
    for location in practice.locations:
        by_id.setdefault(location.doctor_id, location.doctor)
    doctors = sorted(by_id.values(), key=lambda d: (d.last_name.lower(), d.first_name.lower(), d.id))
    page = paginate(doctors, int_arg("pagenumber", 1, 1, 10**4))
    insurers: list[str] = []
    for doctor in doctors:
        for name in doctor.insurer_names():
            if name not in insurers:
                insurers.append(name)
    insurers.sort()
    primary_locations = [loc for loc in practice.locations if loc.is_primary]
    flags = {
        "medicare": any(loc.medicare for loc in primary_locations),
        "medicaid": any(loc.medicaid for loc in primary_locations),
        "new_patients": any(loc.new_patients for loc in primary_locations),
    }
    return render_template(
        "practice.html",
        practice=practice,
        page=page,
        doctors=doctors,
        specialty_rows=specialty_counts(doctors),
        insurers=insurers,
        flags=flags,
        poll_rows=practice.poll_rows(PRACTICE_POLL_QUESTIONS),
        top_specialties=[name for name, _count in sorted(specialty_counts(doctors), key=lambda row: (-row[1], row[0]))[:3]],
        base_path=url_for("practice_detail", slug=slug),
        page_qs=lambda n: urlencode({"pagenumber": n}),
    )


@app.route("/choice-awards")
def choice_awards():
    counts = {key: Award.query.filter_by(award_class=value[0]).count() for key, value in AWARD_CLASSES.items()}
    return render_template("awards.html", counts=counts)


@app.route("/choice-awards/awardrecipients")
def award_recipients():
    award_class = single_arg("award-class", "patient").lower()
    if award_class not in AWARD_CLASSES:
        award_class = "patient"
    class_name, line, title = AWARD_CLASSES[award_class]
    awards = Award.query.filter_by(award_class=class_name).all()
    doctors = sorted({award.doctor_id: award.doctor for award in awards}.values(), key=lambda d: (d.last_name.lower(), d.first_name.lower(), d.id))
    state_options = states_with_counts([(d.primary_location.city.state, d.primary_location.city.state_name, d.primary_location.city.state_slug) for d in doctors])
    state_filter = single_arg("state", "")
    if state_filter not in {s["slug"] for s in state_options}:
        state_filter = ""
    if state_filter:
        doctors = [d for d in doctors if d.primary_location.city.state_slug == state_filter]
    doctors.sort(key=lambda d: (d.primary_location.city.state_name, d.last_name.lower(), d.first_name.lower(), d.id))
    page = paginate(doctors, int_arg("page", 1, 1, 10**4))
    years = {award.doctor_id: award.year for award in awards}
    return render_template(
        "award_recipients.html",
        award_class=award_class,
        class_title=title,
        award_line=line,
        page=page,
        years=years,
        state_options=state_options,
        state_filter=state_filter,
        saved_ids=saved_doctor_ids(),
        base_path=url_for("award_recipients"),
        page_qs=lambda n: urlencode({k: v for k, v in (("award-class", award_class), ("state", state_filter), ("page", n)) if v}),
    )


@app.route("/reviews-guidelines")
def reviews_guidelines():
    return render_template("guidelines.html")


# --------------------------------------------------------------------------- #
# Auth + account
# --------------------------------------------------------------------------- #
@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = safe_next(request.args.get("next"))
    errors: list[str] = []
    email = ""
    if current_user.is_authenticated and request.method == "GET":
        return redirect(next_url or url_for("index"))
    if request.method == "POST":
        next_url = safe_next(request.form.get("next")) or next_url
        email = request.form.get("email", "").strip().lower()[:160]
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first() if email else None
        if user is None or not check_password_hash(user.password_hash, password):
            errors.append("The email or password you entered is incorrect.")
        else:
            login_user(user, remember=request.form.get("remember") == "on")
            return redirect(next_url or url_for("index"))
    return render_template("login.html", errors=errors, email=email, next_url=next_url)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    next_url = safe_next(request.args.get("next"))
    errors: list[str] = []
    form = {"email": "", "dob": ""}
    if request.method == "POST":
        next_url = safe_next(request.form.get("next")) or next_url
        form["email"] = request.form.get("email", "").strip().lower()[:160]
        form["dob"] = request.form.get("dob", "").strip()
        password = request.form.get("password", "")
        if not EMAIL_PATTERN.match(form["email"]):
            errors.append("Enter a valid email address.")
        if len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f"Your password must be at least {MIN_PASSWORD_LENGTH} characters.")
        if len(password) > 256:
            errors.append("Your password must be 256 characters or fewer.")
        dob = None
        if form["dob"]:
            try:
                dob = datetime.strptime(form["dob"], "%m/%d/%Y").date() if "/" in form["dob"] else date.fromisoformat(form["dob"])
            except ValueError:
                errors.append("Enter your date of birth as YYYY-MM-DD.")
        if not errors:
            user = User(
                email=form["email"],
                password_hash=generate_password_hash(password),
                dob=dob,
                display_name=form["email"].split("@", 1)[0],
                created_at=datetime.now(),
            )
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                errors.append("An account with that email already exists. Log in instead.")
            else:
                login_user(user)
                return redirect(next_url or url_for("index"))
    return render_template("signup.html", errors=errors, form=form, next_url=next_url)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/account/saved")
@login_required
def account_saved():
    rows = (
        SavedProvider.query.filter_by(user_id=current_user.id)
        .order_by(SavedProvider.saved_at.desc(), SavedProvider.id.desc())
        .all()
    )
    return render_template("account_saved.html", rows=rows, saved_ids={row.doctor_id for row in rows})


@app.route("/account/saved/<slug>/remove", methods=["POST"])
@login_required
def account_saved_remove(slug: str):
    doctor = doctor_or_404(slug)
    row = SavedProvider.query.filter_by(user_id=current_user.id, doctor_id=doctor.id).first()
    if row is not None:
        db.session.delete(row)
        db.session.commit()
        flash(f"{doctor.full_name} was removed from your saved providers.", "info")
    return redirect(url_for("account_saved"))


@app.route("/account/appointments")
@login_required
def account_appointments():
    rows = (
        AppointmentRequest.query.filter_by(user_id=current_user.id)
        .order_by(AppointmentRequest.created_at.desc(), AppointmentRequest.id.desc())
        .all()
    )
    return render_template("account_appointments.html", rows=rows)


@app.route("/health")
def health():
    marker = db.session.get(SeedMetadata, "version")
    counts = {
        "doctors": Doctor.query.count(),
        "specialties": Specialty.query.count(),
        "hospitals": Hospital.query.count(),
        "practices": Practice.query.count(),
        "users": User.query.count(),
    }
    ready = counts["doctors"] > 0 and marker is not None and marker.value == SEED_VERSION
    return jsonify({"ok": ready, "site": "webmd_doctor", "seed_version": marker.value if marker else None, **counts}), (200 if ready else 503)


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_error):  # pragma: no cover - defensive
    db.session.rollback()
    return render_template("500.html"), 500


def bootstrap_site() -> None:
    from seed_data import ensure_seed_database

    with app.app_context():
        db.create_all()
        ensure_seed_database()


# `python app.py` loads this file as __main__; register it under its import
# name too so seed_data's `from app import ...` reuses this module instead of
# building a second Flask app + SQLAlchemy instance.
sys.modules.setdefault("app", sys.modules[__name__])

if os.environ.get("WEBSYN_SKIP_BOOTSTRAP") != "1":
    bootstrap_site()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
