#!/usr/bin/env python3
"""virginia_dmv — a WebHarbor mirror of https://www.dmv.virginia.gov/

Flask + SQLite mirror of the Virginia DMV public-services site: the real
specialized license plate catalog (342 designs with upstream art), the real
DMV forms catalog (419 rows, PDF downloads for the driver/vehicle categories),
the real fee schedule (DMV 201 chart), the office locator (134 real Customer
Service Centers + DMV Selects with hours/phones/services), the newsroom
(70 real releases), the Virginia Driver's Manual study guide with the real
266-question sample knowledge-exam bank, and the DMV online-account surface
(login, dashboard, address change, registration renewal with the real fee
math, license renewal/replacement, plate purchase, record requests) plus
the Reserve-Your-Spot appointment flow.

Content comes from the tracked source_data/*.json snapshots captured from
the upstream sites on 2026-09-29 (see provenance.json); the
SQLite seed is materialized deterministically at image build time
(PYTHONHASHSEED=0, frozen bcrypt benchmark users).
"""
import hashlib
import json
import os
import pathlib
import re
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("VADMV_SECRET_KEY") or "webharbor-virginia-dmv-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'VADMV_DB_URI', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'virginia_dmv.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'account_login'
login_manager.login_message = 'Please log in to your DMV online account to continue.'
csrf = CSRFProtect(app)

# The mirror freezes the upstream as captured on 2026-09-29.
MIRROR_TODAY = date(2026, 9, 29)
SITE_NAME = "virginia_dmv"
# bcrypt hash of 'TestPass123!' — frozen so the seed DB is byte-reproducible.
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$rEWGiOxRSahnqK8KMUqknuITWJruuY8.oVTx4tp/iXzV9.Ba6BFG2')

SOURCE = os.path.join(BASE_DIR, 'source_data')


def _load(name):
    with open(os.path.join(SOURCE, name), encoding='utf-8') as f:
        return json.load(f)


# The upstream dmv-manuals backend serves the manual's figures and the exam
# bank's sign/illustration images from
# transactions.dmv.virginia.gov/dmv-manuals/manuals/images/1/<file> — 121
# unique real upstream files now mirrored under static/images/manual/ (see
# asset_inventory.json). manual_image_map.json maps every upstream-referenced
# filename (including the two upstream case-variant spellings that serve
# byte-identical art) to its mirrored canonical file.
MANUAL_IMAGE_DIR = 'static/images/manual'


def _manual_image_map():
    try:
        return _load('manual_image_map.json')
    except (OSError, ValueError):
        return {}


def _manual_image_url(filename):
    """Resolve an upstream manual image filename to the mirrored file."""
    canonical = _manual_image_map().get(filename, filename)
    if os.path.exists(os.path.join(BASE_DIR, MANUAL_IMAGE_DIR, canonical)):
        return f"/{MANUAL_IMAGE_DIR}/{canonical}"
    return None


def _rewrite_manual_images(html):
    """Point the manual HTML's upstream <img> tags at the mirrored files."""
    def repl(m):
        url = _manual_image_url(m.group(1))
        if url:
            return f'src="{url}"'
        return m.group(0)
    return re.sub(r'src="(?:https://transactions\.dmv\.virginia\.gov)?'
                  r'/dmv-manuals/manuals/images/1/([A-Za-z0-9._-]+)"',
                  repl, html)


# ------------------------------------------------------------------ models --

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    account_number = db.Column(db.String(20), nullable=False)
    street = db.Column(db.String(160))
    city = db.Column(db.String(80))
    state = db.Column(db.String(40))
    zip = db.Column(db.String(12))
    phone = db.Column(db.String(24))
    created_at = db.Column(db.String(10), nullable=False)

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def license(self):
        return UserLicense.query.filter_by(user_id=self.id).first()

    @property
    def vehicles(self):
        return Vehicle.query.filter_by(user_id=self.id).order_by(Vehicle.id).all()


class UserLicense(db.Model):
    __tablename__ = 'user_licenses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    number = db.Column(db.String(20), nullable=False)
    class_type = db.Column(db.String(24), nullable=False)
    credential_type = db.Column(db.String(60), nullable=False)
    issued = db.Column(db.String(10), nullable=False)
    expires = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(80), nullable=False)
    real_id = db.Column(db.Boolean, nullable=False, default=False)
    organ_donor = db.Column(db.Boolean, nullable=False, default=False)
    veteran = db.Column(db.Boolean, nullable=False, default=False)


class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vin = db.Column(db.String(20), nullable=False)
    plate = db.Column(db.String(12), nullable=False)
    make = db.Column(db.String(40), nullable=False)
    model = db.Column(db.String(60), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    vehicle_type = db.Column(db.String(80), nullable=False)
    weight_class = db.Column(db.String(24), nullable=False)
    registration_expires = db.Column(db.String(10), nullable=False)
    registration_years = db.Column(db.Integer, nullable=False, default=1)
    emissions_locality = db.Column(db.Boolean, nullable=False, default=False)
    electric = db.Column(db.Boolean, nullable=False, default=False)
    title_number = db.Column(db.String(20), nullable=False)
    insured = db.Column(db.Boolean, nullable=False, default=True)
    plate_design = db.Column(db.String(60), nullable=False, default='standard')


class Office(db.Model):
    __tablename__ = 'offices'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    office_type = db.Column(db.String(20), nullable=False)   # csc | dmv_select
    address = db.Column(db.String(200), nullable=False)
    hours = db.Column(db.Text, nullable=False, default='[]')
    phone = db.Column(db.String(24))
    fax = db.Column(db.String(24))
    services_available = db.Column(db.Text, nullable=False, default='[]')
    services_unavailable = db.Column(db.Text, nullable=False, default='[]')
    nearby = db.Column(db.Text, nullable=False, default='[]')

    def hours_list(self):
        return json.loads(self.hours)

    def services(self):
        return json.loads(self.services_available)

    def not_services(self):
        return json.loads(self.services_unavailable)

    def nearby_list(self):
        return json.loads(self.nearby)

    def weekday_hours(self):
        for d, t in self.hours_list():
            if 'Mon' in d:
                return t
        return "8:00 am-5:00 pm"


class Plate(db.Model):
    __tablename__ = 'plates'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(40), nullable=False, default='Other')
    image = db.Column(db.String(200), nullable=False)
    plate_fee = db.Column(db.String(20), nullable=False, default='')
    personalized_fee = db.Column(db.String(20), nullable=False, default='')
    personalization_available = db.Column(db.String(8), nullable=False, default='')
    disabled_symbol = db.Column(db.String(8), nullable=False, default='')
    char_combinations = db.Column(db.String(8), nullable=False, default='')
    requirements = db.Column(db.Text, nullable=False, default='')
    revenue_sharing = db.Column(db.Text, nullable=False, default='')
    type_codes = db.Column(db.Text, nullable=False, default='[]')

    def fee_number(self):
        m = re.match(r"\$([\d,]+)", self.plate_fee or "")
        return float(m.group(1).replace(",", "")) if m else 0.0

    def personalized_fee_number(self):
        m = re.match(r"\$([\d,]+)", self.personalized_fee or "")
        return float(m.group(1).replace(",", "")) if m else 0.0

    def image_path(self):
        return _style_image(self.image, 'plates')


class FormEntry(db.Model):
    __tablename__ = 'forms'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(240), nullable=False)
    description = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    pdf = db.Column(db.String(200), nullable=False)

    def pdf_name(self):
        return self.pdf.rsplit('/', 1)[-1]


class NewsArticle(db.Model):
    __tablename__ = 'news'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(240), nullable=False)
    published = db.Column(db.String(40), nullable=False, default='')
    image = db.Column(db.String(200), nullable=False, default='')
    paragraphs = db.Column(db.Text, nullable=False, default='[]')

    def paras(self):
        return json.loads(self.paragraphs)

    def image_path(self):
        return _style_image(self.image, 'news') if self.image else ""


class ManualSection(db.Model):
    __tablename__ = 'manual_sections'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)


class ManualSubsection(db.Model):
    __tablename__ = 'manual_subsections'
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.Integer, nullable=False)
    subsection = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False, default='')
    body_html = db.Column(db.Text, nullable=False, default='')


class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.Integer, nullable=False)
    answers = db.Column(db.Text, nullable=False)
    correct_count = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    percent = db.Column(db.Integer, nullable=False)
    passed = db.Column(db.Boolean, nullable=False)


class QuizQuestion(db.Model):
    __tablename__ = 'quiz_questions'
    id = db.Column(db.Integer, primary_key=True)
    qid = db.Column(db.String(40), nullable=False)
    section = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(60), nullable=False, default='')
    question = db.Column(db.Text, nullable=False)
    answers = db.Column(db.Text, nullable=False)    # JSON [{text,value}]
    correct = db.Column(db.String(8), nullable=False)
    feedback = db.Column(db.Text, nullable=False, default='')

    def answers_list(self):
        return json.loads(self.answers)


class Page(db.Model):
    """Upstream content page snapshot, served at its real upstream path."""
    __tablename__ = 'pages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    path = db.Column(db.String(160), unique=True, nullable=False)
    title = db.Column(db.String(220), nullable=False)
    body = db.Column(db.Text, nullable=False)      # JSON {alerts, sections}
    def data(self):
        return json.loads(self.body)


class OnlineService(db.Model):
    __tablename__ = 'online_services'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(60), nullable=False)
    label = db.Column(db.String(120), nullable=False)
    url = db.Column(db.String(240), nullable=False)


class FeeRow(db.Model):
    __tablename__ = 'fee_rows'
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(40), nullable=False)
    label = db.Column(db.String(240), nullable=False)
    value = db.Column(db.String(120), nullable=False)


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    confirmation = db.Column(db.String(16), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    office_slug = db.Column(db.String(120), nullable=False)
    service = db.Column(db.String(120), nullable=False)
    appt_date = db.Column(db.String(10), nullable=False)
    appt_time = db.Column(db.String(12), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Confirmed')
    created_at = db.Column(db.String(10), nullable=False)


class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    receipt = db.Column(db.String(16), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    summary = db.Column(db.String(240), nullable=False)
    total = db.Column(db.String(12), nullable=False)
    details = db.Column(db.Text, nullable=False, default='{}')
    created_at = db.Column(db.String(10), nullable=False)

    def info(self):
        return json.loads(self.details)


class RecordRequest(db.Model):
    __tablename__ = 'record_requests'
    id = db.Column(db.Integer, primary_key=True)
    receipt = db.Column(db.String(16), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    record_type = db.Column(db.String(20), nullable=False)   # driver | vehicle
    certified = db.Column(db.Boolean, nullable=False, default=False)
    delivery = db.Column(db.String(10), nullable=False)      # online | mail
    vehicle_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(40), nullable=False, default='Processing')
    total = db.Column(db.String(12), nullable=False)
    created_at = db.Column(db.String(10), nullable=False)


# ------------------------------------------------------------------- fees --

REG_FEES = {
    '4000_or_less': 30.75,
    '4001_6500': 35.75,
    '6501_10000': 44.75,
    'motorcycle': 24.75,
    'moped': 18.25,
    'autocycle': 21.75,
    'low_speed': 29.25,
    'trailer_1500': 18.00,
    'trailer_4000': 28.50,
    'trailer_4000_plus': 40.00,
}
EMISSIONS_FEE = 2.00
EV_HUF = 135.63
LATE_FEE = 10.00
ONLINE_DISCOUNT = 1.00
MULTIYEAR_DISCOUNT = {1: 0.0, 2: 3.0, 3: 4.0}
LICENSE_PER_YEAR = 4.00
LICENSE_YEARS = 8
LICENSE_REPLACEMENT = 20.00
REAL_ID_FEE = 10.00
ID_PER_YEAR = 2.00
RECORD_ONLINE = 8.00
RECORD_CERTIFIED_EXTRA = 5.00
RECORD_MAIL = 9.00
TITLE_FEE = 15.00
REG_CARD_REPLACEMENT = 2.00


def money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}"


def registration_fee(vehicle: Vehicle, years: int, online: bool = True):
    """The real DMV fee math for a registration renewal."""
    lines = []
    base = REG_FEES.get(vehicle.weight_class, 30.75)
    lines.append((f"{vehicle.year} {vehicle.make} {vehicle.model} — "
                  f"{vehicle.vehicle_type} registration ({years} year"
                  f"{'s' if years > 1 else ''})", base * years))
    total = base * years
    # motorcycles are exempt from the emissions inspection program
    if vehicle.emissions_locality and vehicle.weight_class not in ('motorcycle', 'moped'):
        lines.append(("Emissions inspection program fee (per year)", EMISSIONS_FEE * years))
        total += EMISSIONS_FEE * years
    if vehicle.electric:
        lines.append((f"{vehicle.year} {vehicle.make} {vehicle.model} — electric vehicle "
                      "highway use fee (per year)", EV_HUF * years))
        total += EV_HUF * years
    expired = vehicle.registration_expires < MIRROR_TODAY.isoformat()
    if expired:
        lines.append(("Late fee", LATE_FEE))
        total += LATE_FEE
    if online:
        lines.append(("Internet renewal discount (per year)", -ONLINE_DISCOUNT * years))
        total -= ONLINE_DISCOUNT * years
    disc = MULTIYEAR_DISCOUNT.get(years, 0.0)
    if disc and online:
        lines.append((f"{years}-year renewal discount", -disc))
        total -= disc
    return round(total, 2), lines, expired


# ------------------------------------------------------------------- seed --

def _seed_users():
    if User.query.count() > 0:
        return
    bench = _load('benchmark_users.json')
    for i, u in enumerate(bench['users'], start=1):
        user = User(email=u['email'], display_name=u['display_name'],
                   password_hash=BENCHMARK_PASSWORD_HASH,
                   account_number=u['account_number'],
                   street=u['street'], city=u['city'], state=u['state'],
                   zip=u['zip'], phone=u['phone'], created_at="2026-01-15")
        db.session.add(user)
        db.session.flush()
        lic = u['license']
        db.session.add(UserLicense(
            user_id=user.id, number=lic['number'], class_type=lic['class'],
            credential_type=lic['type'], issued=lic['issued'],
            expires=lic['expires'], status=lic['status'],
            real_id=lic['real_id'], organ_donor=lic['organ_donor'],
            veteran=lic['veteran']))
        for v in u['vehicles']:
            db.session.add(Vehicle(
                user_id=user.id, vin=v['vin'], plate=v['plate'],
                make=v['make'], model=v['model'], year=v['year'],
                vehicle_type=v['type'], weight_class=v['weight_class'],
                registration_expires=v['registration_expires'],
                registration_years=v['registration_years'],
                emissions_locality=v['emissions_locality'],
                electric=v['electric'], title_number=v['title_number'],
                insured=v['insured']))
    db.session.commit()


def _seed_catalog():
    if Office.query.count() > 0:
        return
    for o in _load('offices.json'):
        raw_slug = o['path'].rsplit('/', 1)[-1]
        slug = ("dmv-selects-" + raw_slug) if "dmv-selects/" in o['path'] else raw_slug
        db.session.add(Office(
            slug=slug, name=o['name'],
            office_type='csc' if o['type'] == 'customer_service_center' else 'dmv_select',
            address=o['address'], phone=o['phone'], fax=o['fax'],
            hours=json.dumps(o['hours']),
            services_available=json.dumps(o['services_available']),
            services_unavailable=json.dumps(o['services_unavailable']),
            nearby=json.dumps(o['nearby'])))
    for p in _load('plates.json'):
        db.session.add(Plate(
            slug=p['slug'], title=p['title'],
            category=(p['categories'][0].title() if p['categories'] else 'Other'),
            image=p['image'], plate_fee=p['plate_fee'],
            personalized_fee=p['personalized_fee'],
            personalization_available=p['personalization_available'],
            disabled_symbol=p['disabled_symbol'],
            char_combinations=p['char_combinations'],
            requirements=p['requirements'],
            revenue_sharing=p['revenue_sharing'],
            type_codes=json.dumps(p['type_codes'])))
    for f in _load('forms.json'):
        db.session.add(FormEntry(
            number=f['number'], title=f['title'], description=f['description'],
            language=f['language'], category=f['category'], pdf=f['pdf']))
    for n in _load('news.json'):
        db.session.add(NewsArticle(
            slug=n['slug'], title=n['title'], published=n['date'],
            image=n['image'], paragraphs=json.dumps(n['paragraphs'])))
    for s in _load('services.json'):
        db.session.add(OnlineService(
            category=s['category'], label=s['label'], url=s['url']))
    fees = _load('fees.json')
    for group, rows in fees['chart'].items():
        if isinstance(rows, dict):
            for label, value in rows.items():
                db.session.add(FeeRow(group_name=group, label=label, value=value))
    manual = _load('manual.json')
    for s in manual['sections']:
        db.session.add(ManualSection(number=int(s['id']), title=s['title']))
    for sub in manual['subsections']:
        db.session.add(ManualSubsection(
            section=sub['section'], subsection=sub['subsection'],
            title=sub['title'], body_html=sub['html']))
    for q in _load('quiz.json'):
        answers = [a for a in q['answers'] if a['text'].strip()]
        correct = str(q['correct'])
        # Upstream codes 5/6/7 designate answers by meaning, not position.
        special = {'5': 'true', '6': 'false', '7': 'all of the above'}
        if correct in special:
            matching = [a for a in answers if a['text'].strip().lower().rstrip('.') == special[correct]]
            if len(matching) != 1:
                raise ValueError(f"Unresolved answer code for question {q['id']}")
            correct = str(matching[0]['value'])
        if correct not in {str(a['value']) for a in answers}:
            raise ValueError(f"Unreachable correct answer for question {q['id']}")
        db.session.add(QuizQuestion(
            qid=q['id'], section=str(q.get('section') or ''),
            category=q['category'], question=q['question'],
            answers=json.dumps(answers), correct=correct,
            feedback=q['feedback']))
    for p in _load('pages.json'):
        db.session.add(Page(name=p['name'], path=p.get('path', '/' + p['name']),
                            title=p['title'],
                            body=json.dumps({'alerts': p['alerts'],
                                             'sections': p['sections'],
                                             'cards': p.get('cards', []),
                                             'sidebar_links': p.get('sidebar_links', [])})))
    db.session.commit()


def _seed_demo_transactions():
    """A pre-existing renewal receipt + one existing appointment per the
    benchmark fixtures (mirror-native)."""
    if Transaction.query.count() > 0 or Appointment.query.count() > 0:
        return
    alice = User.query.filter_by(email='alice.j@test.com').first()
    dana = User.query.filter_by(email='dana.k@test.com').first()
    if alice:
        db.session.add(Transaction(
            receipt="R20260114-3841", user_id=alice.id, kind="Registration Renewal",
            summary="2019 Toyota Camry — 1-year online renewal",
            total="$31.75", details='{"vehicle": "2019 Toyota Camry", "years": 1}',
            created_at="2026-01-14"))
        db.session.add(Appointment(
            confirmation="VADM9620114A", user_id=alice.id,
            name=alice.display_name, email=alice.email,
            office_slug="richmond-central", service="Driver's License Renewal",
            appt_date="2026-10-07", appt_time="10:20 AM",
            status="Confirmed", created_at="2026-09-20"))
    if dana:
        db.session.add(Appointment(
            confirmation="VADM9620114B", user_id=dana.id,
            name=dana.display_name, email=dana.email,
            office_slug="virginia-beach", service="Knowledge Exam",
            appt_date="2026-10-09", appt_time="9:00 AM",
            status="Confirmed", created_at="2026-09-21"))
    db.session.commit()


def main():
    with app.app_context():
        db.create_all()
        _seed_users()
        _seed_catalog()
        _seed_demo_transactions()


with app.app_context():
    db.create_all()
    _seed_users()
    _seed_catalog()
    _seed_demo_transactions()


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# ----------------------------------------------------------------- helpers --

def _page(name):
    return Page.query.filter_by(name=name).first()


def mirror_href(href):
    """Resolve an upstream link to a mirror route when one exists.
    Internal content pages resolve through the Page table; PDF form links
    resolve to the download route when the file is mirrored; external
    transaction URLs point at the account login. Returns None when the
    mirror has no equivalent (the template renders the label as text)."""
    if href == '/node/8996':
        href = '/vehicles/insurance-coverage'
    if not href:
        return None
    if href.startswith('/sites/default/files/forms/') and href.endswith('.pdf'):
        name = href.rsplit('/', 1)[-1]
        if os.path.exists(os.path.join(BASE_DIR, 'static', 'external_cache',
                                       'forms', name)):
            return url_for('download_form', name=name)
        return None
    # Some upstream application PDFs live directly under /sites/default/files/
    # (e.g. dl1p.pdf); the downloader stores them under external_cache/forms.
    if href.startswith('/sites/default/files/') and href.endswith('.pdf'):
        name = href.rsplit('/', 1)[-1]
        if os.path.exists(os.path.join(BASE_DIR, 'static', 'external_cache',
                                       'forms', name)):
            return url_for('download_form', name=name)
        return None
    if href == '/sites/default/files/dmv201.pdf':
        return url_for('download_fee_chart')
    if href.startswith(('https://transactions.dmv.virginia.gov',
                         'https://appointments.dmv.virginia.gov',
                         'https://viim.dmv.virginia.gov')):
        return url_for('account_login')
    if href == '/locations/dmv-selects':
        return url_for('all_locations', type='dmv_select')
    if href.startswith('/locations/'):
        slug = href.rsplit('/', 1)[-1]
        if Office.query.filter_by(slug=slug).first():
            return url_for('office_detail', slug=slug)
        if Office.query.filter_by(slug='dmv-selects-' + slug).first():
            return url_for('office_detail', slug='dmv-selects-' + slug)
        # no mirrored office at this upstream path — render as plain text
        return None
    if href.startswith('/'):
        path = href.split('?')[0].rstrip('/') or '/'
        if path == '/vehicles/license-plates/search':
            return url_for('plates_search')
        if Page.query.filter_by(path=path).first() or path == '/':
            return path
        # explicit static routes (e.g. /licenses-ids/exams/practice-exam)
        for rule in app.url_map.iter_rules():
            if '<' not in rule.rule and rule.rule == path and \
                    'GET' in rule.methods and rule.endpoint != 'static':
                return path
    return None


def _render_page(name, **ctx):
    page = _page(name)
    if page is None:
        abort(404)
    data = page.data()
    return render_template('content_page.html', page=page, data=data,
                           site_alerts=data.get('alerts', []), **ctx)


PLATE_CATEGORIES = ["Special Interest", "College", "Military", "Other"]


def _plate_image(filename):
    return f"/static/images/plates/{filename}"


def _style_image(raw, category):
    """Map an upstream /sites/default/files image URL to the mirrored file.
    The downloader preserves the upstream style tag in the filename."""
    if not raw:
        return ""
    raw = raw.split("?")[0]
    m = re.search(r"/styles/([^/]+)/public/(?:images/)?(.+)$", raw)
    if m:
        name = re.sub(r"%20", "_", m.group(2))
        name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        return _asset_or_alt(f"/static/images/{category}/{m.group(1)}__{name}")
    name = re.sub(r"%20", "_", raw.rsplit('/', 1)[-1])
    return _asset_or_alt(f"/static/images/{category}/{name}")


def _asset_or_alt(path):
    """Resolve the mirrored file for an upstream style URL. The upstream
    serves byte-identical derivatives at several style URLs (e.g. a plate's
    max_650x650 and small styles), so the mirror keeps one real file per
    unique upstream image and falls back across styles and extensions."""
    base = os.path.join(BASE_DIR, path.lstrip('/'))
    if os.path.exists(base):
        return path
    stem, ext = os.path.splitext(path)
    # same base art under another style tag
    dirn, fname = os.path.split(stem)
    art = fname.split('__', 1)[1] if '__' in fname else fname
    for cand in (f"{dirn}/max_650x650__{art}{ext}", f"{dirn}/small__{art}{ext}"):
        if os.path.exists(os.path.join(BASE_DIR, cand.lstrip('/'))):
            return cand
    # upstream GIF bytes served at a .jpg URL
    alt = f"{stem}.gif"
    if os.path.exists(os.path.join(BASE_DIR, alt.lstrip('/'))):
        return alt
    return path


def _receipt(prefix):
    """Deterministic-looking unique receipt/confirmation numbers."""
    for _ in range(20):
        n = f"{prefix}{datetime.now().strftime('%y%m%d')}-" \
            f"{hashlib.md5(os.urandom(8)).hexdigest()[:6].upper()}"
        if not Transaction.query.filter_by(receipt=n).first() and \
                not Appointment.query.filter_by(confirmation=n).first():
            return n
    abort(500)


# ----------------------------------------------------------------- routes ---

@app.context_processor
def _inject_helpers():
    return {"mirror_href": mirror_href}


@app.route('/_health')
def health():
    return jsonify(ok=True, site=SITE_NAME,
                   pages=Page.query.count(),
                   offices=Office.query.count(),
                   plates=Plate.query.count(),
                   forms=FormEntry.query.count(),
                   news=NewsArticle.query.count(),
                   quiz_questions=QuizQuestion.query.count(),
                   manual_subsections=ManualSubsection.query.count(),
                   fee_rows=FeeRow.query.count(),
                   online_services=OnlineService.query.count(),
                   users=User.query.count(),
                   vehicles=Vehicle.query.count())


@app.route('/')
def home():
    """Render the captured upstream home page (hero, quick links, sections,
    cards) from the frozen pages.json snapshot."""
    page = _page('home')
    data = page.data() if page else {'alerts': [], 'sections': [], 'cards': []}
    news = NewsArticle.query.order_by(NewsArticle.published.desc()).limit(3).all()
    return render_template('home.html', page=page, data=data, news=news,
                           site_alerts=data.get('alerts', []))


@app.route('/about')
def about():
    return _render_page('about')


@app.route('/contact-us')
def contact_us():
    return _render_page('contact-us')


@app.route('/how-do-i')
def how_do_i():
    return _render_page('how-do-i')


@app.route('/moving')
def moving():
    return _render_page('moving')


@app.route('/moving/new-virginia')
def moving_new_virginia():
    return _render_page('moving-new-virginia')


@app.route('/records')
def records():
    return _render_page('records')


@app.route('/records/request-driver-vehicle-record')
def records_request():
    return _render_page('records-request-driver-vehicle-record')


@app.route('/online-services')
def online_services():
    page = _page('online-services')
    return render_template('online_services.html', page=page,
                           data=page.data() if page else {'sections': []})


@app.route('/online-services-all')
def online_services_all():
    cats = {}
    for s in OnlineService.query.order_by(OnlineService.id).all():
        cats.setdefault(s.category, []).append(s)
    return render_template('online_services_all.html', cats=cats)


@app.route('/online-services/address-change')
def online_services_address_change():
    return _render_page('online-services-address-change')


# ------------------------------------------------------------ licenses-ids --

@app.route('/licenses-ids')
def licenses_ids():
    return _render_page('licenses-ids')


@app.route('/licenses-ids/license')
def licenses_ids_license():
    return _render_page('licenses-ids-license')


@app.route('/licenses-ids/license/applying')
def licenses_ids_license_applying():
    return _render_page('licenses-ids-license-applying')


@app.route('/licenses-ids/license/replace')
def licenses_ids_license_replace():
    return _render_page('licenses-ids-license-replace')


@app.route('/licenses-ids/learners')
def licenses_ids_learners():
    return _render_page('licenses-ids-learners')


@app.route('/licenses-ids/real-id')
def licenses_ids_real_id():
    return _render_page('licenses-ids-real-id')


@app.route('/licenses-ids/cdl')
def licenses_ids_cdl():
    return _render_page('licenses-ids-cdl')


@app.route('/licenses-ids/id-cards')
def licenses_ids_id_cards():
    return _render_page('licenses-ids-id-cards')


@app.route('/licenses-ids/motorcycle')
def licenses_ids_motorcycle():
    return _render_page('licenses-ids-motorcycle')


@app.route('/licenses-ids/exams')
def licenses_ids_exams():
    return _render_page('licenses-ids-exams')


@app.route('/licenses-ids/exams/practice-exam')
def practice_exam_landing():
    sections = ManualSection.query.order_by(ManualSection.number).all()
    counts = {}
    for s in sections:
        counts[s.number] = QuizQuestion.query.filter(
            QuizQuestion.section == str(s.number)).count()
    return render_template('practice_landing.html', sections=sections, counts=counts)


def _quiz_images():
    """qid -> [mirrored image URL] for the exam bank's picture questions."""
    try:
        raw = _load('quiz_images.json')
    except (OSError, ValueError):
        return {}
    out = {}
    for qid, files in raw.items():
        urls = [u for u in (_manual_image_url(f) for f in files) if u]
        if urls:
            out[str(qid)] = urls
    return out


@app.route('/licenses-ids/exams/practice-exam/<int:section>')
def practice_exam_section(section):
    sec = ManualSection.query.filter_by(number=section).first_or_404()
    subs = ManualSubsection.query.filter_by(section=section).order_by(
        ManualSubsection.subsection).all()
    per = 10 if section in (1, 2) else 8
    questions = QuizQuestion.query.filter_by(section=str(section)).order_by(
        QuizQuestion.id).limit(per).all()
    return render_template('practice_section.html', section=sec,
                           subsections=subs, questions=questions,
                           q_images=_quiz_images())


@app.route('/licenses-ids/exams/practice-exam/<int:section>/grade', methods=['POST'])
def practice_exam_grade(section):
    sec = ManualSection.query.filter_by(number=section).first_or_404()
    questions = QuizQuestion.query.filter_by(section=str(section)).order_by(
        QuizQuestion.id).limit(10 if section in (1, 2) else 8).all()
    picks = {q.id: request.form.get(f'q_{q.id}', '') for q in questions}
    results = []
    correct_count = 0
    for q in questions:
        pick = picks.get(q.id, '')
        ok = pick == q.correct
        correct_count += ok
        results.append({'q': q, 'pick': pick, 'ok': ok})
    pct = round(100 * correct_count / len(questions)) if questions else 0
    passed = pct >= 80
    db.session.add(QuizAttempt(section=section, answers=json.dumps(picks, sort_keys=True),
                               correct_count=correct_count, total=len(questions),
                               percent=pct, passed=passed))
    db.session.commit()
    return render_template('practice_result.html', section=sec, results=results,
                           correct=correct_count, total=len(questions),
                           pct=pct, passed=passed, q_images=_quiz_images())


# ----------------------------------------------------------------- manual --

@app.route('/drivers-manual')
def drivers_manual():
    sections = ManualSection.query.order_by(ManualSection.number).all()
    subs = ManualSubsection.query.order_by(ManualSubsection.section,
                                           ManualSubsection.subsection).all()
    by_section = {}
    for s in subs:
        by_section.setdefault(s.section, []).append(s)
    return render_template('manual_toc.html', sections=sections, by_section=by_section)


@app.route('/drivers-manual/<int:section>/<int:subsection>')
def manual_subsection(section, subsection):
    sub = ManualSubsection.query.filter_by(
        section=section, subsection=subsection).first_or_404()
    sec = ManualSection.query.filter_by(number=section).first_or_404()
    nxt = ManualSubsection.query.filter(
        ManualSubsection.id > sub.id).order_by(ManualSubsection.id).first()
    prev = ManualSubsection.query.filter(
        ManualSubsection.id < sub.id).order_by(ManualSubsection.id.desc()).first()
    body_html = _rewrite_manual_images(sub.body_html)
    return render_template('manual_sub.html', sub=sub, sec=sec, nxt=nxt, prev=prev,
                           body_html=body_html)


# ---------------------------------------------------------------- vehicles --

@app.route('/vehicles')
def vehicles():
    return _render_page('vehicles')


@app.route('/vehicles/registration')
def vehicles_registration():
    return _render_page('vehicles-registration')


@app.route('/vehicles/title')
def vehicles_title():
    return _render_page('vehicles-title')


@app.route('/vehicles/buy-sell')
def vehicles_buy_sell():
    return _render_page('vehicles-buy-sell')


@app.route('/vehicles/taxes-fees')
def vehicles_taxes_fees():
    groups = {}
    for r in FeeRow.query.order_by(FeeRow.id).all():
        groups.setdefault(r.group_name, []).append(r)
    return render_template('fees.html', groups=groups)


@app.route('/vehicles/license-plates')
def vehicles_plates_landing():
    return _render_page('vehicles-license-plates')


@app.route('/vehicles/license-plates/search')
def plates_search():
    cat = request.args.get('category', '')
    q = request.args.get('q', '').strip().lower()
    page = max(1, request.args.get('pg', 1, type=int) or 1)
    query = Plate.query
    if cat:
        query = query.filter_by(category=cat)
    if q:
        query = query.filter(Plate.title.ilike(f"%{q}%"))
    per = 10
    total = query.count()
    plates = query.order_by(Plate.title).offset((page - 1) * per).limit(per).all()
    counts = {c: Plate.query.filter_by(category=c).count() for c in PLATE_CATEGORIES}
    return render_template('plates_search.html', plates=plates, cat=cat, q=q,
                           page=page, total=total, per=per, counts=counts)


@app.route('/vehicles/license-plates/search/<slug>')
def plate_detail(slug):
    plate = Plate.query.filter_by(slug=slug).first_or_404()
    return render_template('plate_detail.html', plate=plate)


# ------------------------------------------------------------------- news --

@app.route('/news')
def news_list():
    page = max(1, request.args.get('pg', 1, type=int) or 1)
    per = 10
    query = NewsArticle.query.order_by(NewsArticle.published.desc())
    total = query.count()
    articles = query.offset((page - 1) * per).limit(per).all()
    return render_template('news_list.html', articles=articles, page=page,
                           total=total, per=per)


@app.route('/news/<slug>')
def news_article(slug):
    article = NewsArticle.query.filter_by(slug=slug).first_or_404()
    return render_template('news_article.html', article=article)


# -------------------------------------------------------------- locations --

@app.route('/all-locations')
def all_locations():
    typ = request.args.get('type', '')
    q = request.args.get('q', '').strip().lower()
    query = Office.query
    if typ:
        query = query.filter_by(office_type=typ)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Office.name.ilike(like), Office.address.ilike(like)))
    offices = query.order_by(Office.name).all()
    counts = {'csc': Office.query.filter_by(office_type='csc').count(),
              'dmv_select': Office.query.filter_by(office_type='dmv_select').count()}
    return render_template('locations.html', offices=offices, typ=typ, q=q,
                           counts=counts)


@app.route('/locations')
def locations():
    return redirect(url_for('all_locations'))


@app.route('/locations/dmv-selects/<slug>')
@app.route('/locations/<slug>')
def office_detail(slug):
    office = Office.query.filter_by(slug=slug).first()
    if office is None and not slug.startswith('dmv-selects-'):
        office = Office.query.filter_by(slug='dmv-selects-' + slug).first()
    if office is None:
        abort(404)
    nearby = []
    for n in office.nearby_list():
        rec = Office.query.filter_by(name=n.get('name', '')).first()
        nearby.append({'name': n.get('name'), 'address': n.get('address'),
                       'type': n.get('type'), 'slug': rec.slug if rec else None})
    return render_template('office_detail.html', office=office, nearby=nearby)


# ------------------------------------------------------------------ forms --

@app.route('/forms')
def forms():
    cat = request.args.get('category', '')
    lang = request.args.get('language', '')
    q = request.args.get('q', '').strip()
    page = max(1, request.args.get('pg', 1, type=int) or 1)
    query = FormEntry.query
    if cat:
        query = query.filter_by(category=cat)
    if lang:
        query = query.filter_by(language=lang)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(FormEntry.title.ilike(like),
                                    FormEntry.number.ilike(like),
                                    FormEntry.description.ilike(like)))
    per = 10
    total = query.count()
    rows = query.order_by(FormEntry.number).offset((page - 1) * per).limit(per).all()
    cats = {}
    for f in FormEntry.query.all():
        cats[f.category] = cats.get(f.category, 0) + 1
    langs = {}
    for f in FormEntry.query.all():
        langs[f.language] = langs.get(f.language, 0) + 1
    return render_template('forms.html', rows=rows, cat=cat, lang=lang, q=q,
                           page=page, total=total, per=per,
                           cats=sorted(cats.items(), key=lambda kv: -kv[1]),
                           langs=sorted(langs.items(), key=lambda kv: -kv[1]))


@app.route('/download/forms/<name>')
def download_form(name):
    if '/' in name or '..' in name or not name.endswith('.pdf'):
        abort(404)
    return send_from_directory(os.path.join(BASE_DIR, 'static', 'external_cache', 'forms'),
                               name)


@app.route('/download/dmv201.pdf')
def download_fee_chart():
    return send_from_directory(os.path.join(BASE_DIR, 'static', 'external_cache', 'forms'),
                               'dmv201.pdf', as_attachment=True)


# ------------------------------------------------------------ appointments --

APPOINTMENT_SERVICES = [
    "Driver's License Renewal",
    "Driver's License Replacement",
    "Learner's Permit",
    "Knowledge Exam",
    "Road Skills Test",
    "Motorcycle Skills Test",
    "CDL Services",
    "ID Card Renewal",
    "REAL ID",
    "Vehicle Registration / Title",
    "Disabled Parking Placard",
    "Vital Records",
    "Driver Record / Vehicle Record",
    "E-ZPass Services",
]


@app.route('/appointments')
def appointments():
    return _render_page('appointments')


@app.route('/appointments/new', methods=['GET', 'POST'])
def appointment_new():
    offices = Office.query.filter_by(office_type='csc').order_by(Office.name).all()
    step = 1
    office = service = appt_date = appt_time = None
    if request.method == 'POST':
        step = request.form.get('step', type=int)
        if step not in (2, 3):
            abort(400)
    if request.method == 'POST':
        office = Office.query.filter_by(slug=request.form.get('office', ''), office_type='csc').first()
        service = request.form.get('service', '')
        try:
            d = date.fromisoformat(request.form.get('date', ''))
        except ValueError:
            abort(400, 'Enter a valid appointment date.')
        if not office or service not in APPOINTMENT_SERVICES or d < MIRROR_TODAY or d.weekday() >= 5:
            abort(400, 'Choose a customer service center, service and a weekday appointment date.')
        # Twenty-minute benchmark slots. Integer arithmetic avoids 8:19/8:39 drift.
        slots = [f"{minute // 60 if minute // 60 <= 12 else minute // 60 - 12}:{minute % 60:02d} {'AM' if minute < 720 else 'PM'}"
                 for minute in range(480, 1020, 20)]
        appt_date = d.isoformat()
        if step == 2:
            return render_template('appointment_form.html', step=2, office=office,
                                   service=service, appt_date=appt_date, slots=slots,
                                   services=APPOINTMENT_SERVICES, offices=offices)
        appt_time = request.form.get('time', '')
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        if (appt_time not in slots or not name
                or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)):
            abort(400, 'Choose an offered time and enter your name and email.')
        confirm = _receipt('VADM')
        appt = Appointment(confirmation=confirm,
                           user_id=current_user.id if current_user.is_authenticated else None,
                           name=name, email=email, office_slug=office.slug,
                           service=service, appt_date=appt_date,
                           appt_time=appt_time, created_at=MIRROR_TODAY.isoformat())
        db.session.add(appt)
        db.session.commit()
        return render_template('appointment_confirmed.html', appt=appt, office=office)
    return render_template('appointment_form.html', step=1, offices=offices,
                           services=APPOINTMENT_SERVICES)


@app.route('/appointments/lookup', methods=['GET', 'POST'])
def appointment_lookup():
    appt = None
    if request.method == 'POST':
        confirm = request.form.get('confirmation', '').strip().upper()
        email = request.form.get('email', '').strip().lower()
        appt = Appointment.query.filter_by(confirmation=confirm).first()
        if not appt or appt.email.lower() != email:
            flash('No appointment found for that confirmation number and email.')
            appt = None
    else:
        confirm = request.args.get('confirmation', '').strip().upper()
        email = request.args.get('email', '').strip().lower()
        if confirm and email:
            appt = Appointment.query.filter_by(confirmation=confirm).first()
            if not appt or appt.email.lower() != email:
                flash('No appointment found for that confirmation number and email.')
                appt = None
    return render_template('appointment_lookup.html', appt=appt)


@app.route('/appointments/cancel', methods=['POST'])
def appointment_cancel():
    confirm = request.form.get('confirmation', '').strip().upper()
    email = request.form.get('email', '').strip().lower()
    appt = Appointment.query.filter_by(confirmation=confirm).first()
    if not appt or appt.email.lower() != email:
        flash('No appointment found for that confirmation number and email.')
        return redirect(url_for('appointment_lookup'))
    appt.status = 'Canceled'
    db.session.commit()
    flash('Your appointment has been canceled.')
    return redirect(url_for('appointment_lookup'))


# ---------------------------------------------------------------- account --

@app.route('/account/login', methods=['GET', 'POST'])
def account_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('account_dashboard'))
        flash('The DMV online account sign-in failed. Check your email and password, '
              'or select "Forgot Your Password?" to reset it.')
    return render_template('login.html')


@app.route('/account/logout')
@login_required
def account_logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/account')
@login_required
def account_dashboard():
    lics = Transaction.query.filter_by(user_id=current_user.id).order_by(
        Transaction.created_at.desc()).all()
    appts = Appointment.query.filter_by(user_id=current_user.id).all()
    return render_template('account.html', license=current_user.license,
                           vehicles=current_user.vehicles,
                           transactions=lics, appointments=appts)


@app.route('/account/address-change', methods=['GET', 'POST'])
@login_required
def account_address_change():
    if request.method == 'POST':
        street = request.form.get('street', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip().upper()
        zipc = request.form.get('zip', '').strip()
        if not (street and city and state == 'VA' and re.match(r"^\d{5}$", zipc)):
            flash('Enter a complete Virginia mailing address (street, city, VA, 5-digit ZIP).')
        else:
            current_user.street = street
            current_user.city = city
            current_user.state = state
            current_user.zip = zipc
            db.session.add(Transaction(
                receipt=_receipt('ADR'), user_id=current_user.id,
                kind='Address Change', summary=f'New address on file: {street}, {city}, VA {zipc}',
                total='$0.00', details='{"service": "Change Address"}',
                created_at=MIRROR_TODAY.isoformat()))
            db.session.commit()
            flash('Your address has been updated. Allow one business day for all '
                  'records to reflect the new address.')
    return render_template('address_change.html', user=current_user)


@app.route('/account/vehicles/<int:vid>/renew', methods=['GET', 'POST'])
@login_required
def vehicle_renew(vid):
    vehicle = Vehicle.query.get_or_404(vid)
    if vehicle.user_id != current_user.id:
        abort(403)
    preview = None
    years = request.args.get('years', type=int)
    if 'years' in request.args and years not in (1, 2, 3):
        abort(400)
    if request.method == 'POST':
        years = request.form.get('years', type=int)
        if years not in (1, 2, 3):
            abort(400)
        total, lines, expired = registration_fee(vehicle, years, online=True)
        receipt = _receipt('REG')
        db.session.add(Transaction(
            receipt=receipt, user_id=current_user.id,
            kind='Registration Renewal',
            summary=(f'{vehicle.year} {vehicle.make} {vehicle.model} — '
                      f'{years}-year online renewal'),
            total=money(total), details=json.dumps({
                'lines': [[l, money(v)] for l, v in lines],
                'vehicle': f'{vehicle.year} {vehicle.make} {vehicle.model}',
                'plate': vehicle.plate, 'years': years}),
            created_at=MIRROR_TODAY.isoformat()))
        new_exp = date.fromisoformat(vehicle.registration_expires)
        base = max(new_exp, MIRROR_TODAY)
        vehicle.registration_expires = (base.replace(
            year=base.year + years)).isoformat()
        vehicle.registration_years = years
        db.session.commit()
        return render_template('receipt.html', receipt=receipt, total=money(total),
                               lines=[(l, money(v)) for l, v in lines],
                               title='Registration Renewal — Official Internet Receipt',
                               note='Print this Official Internet Receipt and keep it with your '
                                    'registration card: it extends your current registration for up '
                                    'to 15 days from today. Your new card and decals arrive by U.S. '
                                    'mail within five days.')
    if years in (1, 2, 3):
        total, lines, expired = registration_fee(vehicle, years, online=True)
        preview = {'years': years, 'total': money(total),
                   'lines': [(l, money(v)) for l, v in lines]}
    return render_template('renew_registration.html', vehicle=vehicle,
                           preview=preview, years=years)


@app.route('/account/license/renew', methods=['GET', 'POST'])
@login_required
def license_renew():
    lic = current_user.license
    if not lic or lic.status.lower() != 'valid' or date.fromisoformat(lic.expires) < MIRROR_TODAY:
        abort(400, 'This credential requires an in-person eligibility review.')
    preview = None
    years = request.args.get('years', 0, type=int)
    if 'years' in request.args and years != 8:
        abort(400)
    real_id = request.args.get('real_id', '0') == '1'
    if request.method == 'POST':
        years = request.form.get('years', type=int)
        if years != 8:
            abort(400)
        real_id = request.form.get('real_id', '0') == '1'
        if real_id and not lic.real_id:
            abort(400, 'A first REAL ID requires a customer service center visit with documents.')
        total = LICENSE_PER_YEAR * years
        lines = [(f"Driver's license renewal ({years} year"
                  f"{'s' if years > 1 else ''} @ $4.00 per year)", total)]
        if real_id and not lic.real_id:
            lines.append(('REAL ID (one-time)', REAL_ID_FEE))
            total += REAL_ID_FEE
        receipt = _receipt('LIC')
        db.session.add(Transaction(
            receipt=receipt, user_id=current_user.id, kind="Driver's License Renewal",
            summary=f'{lic.class_type} license renewed for {years} years'
                    + (' with REAL ID' if real_id and not lic.real_id else ''),
            total=money(total),
            details=json.dumps({'lines': [[l, money(v)] for l, v in lines]}),
            created_at=MIRROR_TODAY.isoformat()))
        lic.expires = (date.fromisoformat(lic.expires).replace(
            year=date.fromisoformat(lic.expires).year + years)).isoformat()
        lic.status = 'Valid'
        if real_id:
            lic.real_id = True
        db.session.commit()
        return render_template('receipt.html', receipt=receipt, total=money(total),
                               lines=[(l, money(v)) for l, v in lines],
                               title="Driver's License Renewal — Official Internet Receipt",
                               note='Your new driver\'s license arrives by U.S. mail within 5 business '
                                    'days. Your current card remains valid until it arrives.')
    if years:
        total = LICENSE_PER_YEAR * years
        lines = [(f"Driver's license renewal ({years} year"
                  f"{'s' if years > 1 else ''} @ $4.00 per year)", total)]
        if real_id and not lic.real_id:
            lines.append(('REAL ID (one-time)', REAL_ID_FEE))
            total += REAL_ID_FEE
        preview = {'total': money(total), 'lines': [(l, money(v)) for l, v in lines]}
    return render_template('renew_license.html', lic=lic, preview=preview,
                           years=years, real_id=real_id)


@app.route('/account/license/replace', methods=['GET', 'POST'])
@login_required
def license_replace():
    lic = current_user.license
    if not lic or lic.status.lower() != 'valid' or date.fromisoformat(lic.expires) < MIRROR_TODAY:
        abort(400, 'This credential is not eligible for online replacement.')
    if request.method == 'POST':
        reason = request.form.get('reason', 'Lost or stolen')
        receipt = _receipt('REP')
        db.session.add(Transaction(
            receipt=receipt, user_id=current_user.id,
            kind="Driver's License Replacement",
            summary=f'Replacement card — {reason}',
            total=money(LICENSE_REPLACEMENT),
            details=json.dumps({'lines': [["Replacement driver's license card",
                                          money(LICENSE_REPLACEMENT)]]}),
            created_at=MIRROR_TODAY.isoformat()))
        db.session.commit()
        return render_template('receipt.html', receipt=receipt,
                               total=money(LICENSE_REPLACEMENT),
                               lines=[("Replacement driver's license card", money(LICENSE_REPLACEMENT))],
                               title="Driver's License Replacement — Official Internet Receipt",
                               note='Your replacement card arrives by U.S. mail within 5 business days.')
    return render_template('replace_license.html', lic=lic)


@app.route('/account/plates/<slug>/purchase', methods=['GET', 'POST'])
@login_required
def plate_purchase(slug):
    plate = Plate.query.filter_by(slug=slug).first_or_404()
    vehicles = current_user.vehicles
    message = ''
    available = None
    if request.method == 'POST':
        vehicle = Vehicle.query.get_or_404(request.form.get('vehicle_id', 0, type=int))
        if vehicle.user_id != current_user.id:
            abort(403)
        message = request.form.get('message', '').strip().upper()
        maxchars = int(plate.char_combinations or 6)
        if message:
            if plate.personalization_available != 'Yes':
                abort(400, 'This plate does not support personalization.')
            if len(message) > maxchars or not re.match(r"^[A-Z0-9 -]+$", message):
                available = False
            else:
                digest = hashlib.md5(message.encode()).hexdigest()
                available = int(digest[:2], 16) % 5 != 0  # 4/5 available, deterministic
        if request.form.get('confirm') == '1' and (available or not message):
            total = plate.fee_number()
            lines = [(f"{plate.title} plate fee (annually, in addition to registration)",
                      money(plate.fee_number()))]
            if message:
                total += plate.personalized_fee_number()
                lines.append(('Personalized plate fee (annually)', money(plate.personalized_fee_number())))
            receipt = _receipt('PLT')
            db.session.add(Transaction(
                receipt=receipt, user_id=current_user.id, kind='Plate Purchase',
                summary=(f'{plate.title} plate for {vehicle.year} {vehicle.make} '
                         f'{vehicle.model}' + (f' — message {message}' if message else '')),
                total=money(total),
                details=json.dumps({'lines': [[l, v] for l, v in lines]}),
                created_at=MIRROR_TODAY.isoformat()))
            vehicle.plate_design = plate.slug
            if message:
                vehicle.plate = message
            db.session.commit()
            return render_template('receipt.html', receipt=receipt, total=money(total),
                                   lines=lines, title='Plate Purchase — Official Internet Receipt',
                                   note='Your new plate arrives by U.S. mail within 7-10 business days. '
                                        'The plate fee renews with your annual registration.')
        selected = vehicle
    else:
        selected = vehicles[0] if vehicles else None
    return render_template('plate_purchase.html', plate=plate, vehicles=vehicles,
                           selected=selected, message=message, available=available)


@app.route('/account/records', methods=['GET', 'POST'])
@login_required
def account_records():
    if request.method == 'POST':
        record_type = request.form.get('record_type', 'driver')
        certified = request.form.get('certified', '0') == '1'
        delivery = request.form.get('delivery', 'online')
        if record_type not in ('driver', 'vehicle') or delivery not in ('online', 'mail'):
            abort(400)
        vehicle_id = request.form.get('vehicle_id', type=int)
        vehicle = Vehicle.query.get(vehicle_id) if vehicle_id else None
        if record_type == 'vehicle' and (vehicle is None or vehicle.user_id != current_user.id):
            flash('Select one of your vehicles to request its record.')
            return render_template('records_order.html', vehicles=current_user.vehicles,
                                   record_type=record_type, certified=certified, delivery=delivery)
        total = RECORD_ONLINE if delivery == 'online' else RECORD_MAIL
        lines = [('Driving record' if record_type == 'driver' else
                  f'Vehicle record ({vehicle.year} {vehicle.make} {vehicle.model})',
                  money(total))]
        if certified:
            lines.append(('Additional fee for certified record', money(RECORD_CERTIFIED_EXTRA)))
            total += RECORD_CERTIFIED_EXTRA
        receipt = _receipt('REC')
        db.session.add(RecordRequest(
            receipt=receipt, user_id=current_user.id, record_type=record_type,
            certified=certified, delivery=delivery,
            vehicle_id=vehicle_id if record_type == 'vehicle' else None,
            total=money(total), created_at=MIRROR_TODAY.isoformat()))
        db.session.add(Transaction(
            receipt=receipt, user_id=current_user.id,
            kind='Record Request',
            summary=('Driving record' if record_type == 'driver' else 'Vehicle record')
                    + (' (certified copy)' if certified else '')
                    + (' — view online' if delivery == 'online' else ' — mailed'),
            total=money(total),
            details=json.dumps({'lines': [[l, v] for l, v in lines]}),
            created_at=MIRROR_TODAY.isoformat()))
        db.session.commit()
        note = ('Your record is available to view for 5 days at no extra charge from '
                'this receipt.' if delivery == 'online' else
                'Your record will be mailed to the address on your driver\'s license '
                'within 5 business days.')
        return render_template('receipt.html', receipt=receipt, total=money(total),
                               lines=lines, title='Record Request — Official Internet Receipt',
                               note=note)
    return render_template('records_order.html', vehicles=current_user.vehicles,
                           record_type='driver', certified=False, delivery='online')


@app.route('/account/receipt/<receipt>')
@login_required
def receipt_view(receipt):
    txn = Transaction.query.filter_by(receipt=receipt).first_or_404()
    if txn.user_id != current_user.id:
        abort(403)
    info = txn.info()
    return render_template('receipt.html', receipt=txn.receipt,
                           total=txn.total,
                           lines=[(l, v) for l, v in info.get('lines', [])],
                           title=f"{txn.kind} — Official Internet Receipt",
                           note="This is a copy of your Official Internet receipt.")


@app.route('/<path:pagepath>')
def upstream_page(pagepath):
    """Serve any captured upstream content page at its real path."""
    path = '/' + pagepath.strip('/')
    page = Page.query.filter_by(path=path).first()
    if page is None:
        abort(404)
    data = page.data()
    return render_template('content_page.html', page=page, data=data,
                           site_alerts=data.get('alerts', []))


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    main()
