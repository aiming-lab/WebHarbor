#!/usr/bin/env python3
"""u_s_customs — a WebHarbor mirror of https://www.cbp.gov/

Flask + SQLite mirror of the U.S. Customs and Border Protection site:
traveler entry pathways (ESTA / I-94 / Trusted Traveler Programs), the
Border Wait Times app (bwt.cbp.gov snapshot), the Locate-a-Port-of-Entry
directory, the newsroom (media releases), the CBP forms catalog with real
downloadable PDFs, trade & import reference pages, and CBP careers with
real USAJOBS postings.

Content comes from the tracked source_data/*.json snapshots captured from
the upstream sites on 2026-09-28; the SQLite seed is
materialized deterministically at image build time (PYTHONHASHSEED=0).
"""
import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                          login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("US_CUSTOMS_SECRET_KEY") or "webharbor-us-customs-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'US_CUSTOMS_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'u_s_customs.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your account.'
csrf = CSRFProtect(app)

# The mirror is a frozen snapshot of the upstream site taken 2026-09-28.
MIRROR_TODAY = date(2026, 9, 28)
MIRROR_TS = "2026-09-28 12:00"
SITE_NAME = "u_s_customs"
# bcrypt hash of 'TestPass123!' — frozen so the seed DB is byte-reproducible.
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')
# ESTA application fee, asserted from the official application website.
ESTA_FEE_USD = 40.27

SOURCE = os.path.join(BASE_DIR, 'source_data')


def _load(name):
    with open(os.path.join(SOURCE, name), encoding='utf-8') as f:
        return json.load(f)


# ------------------------------------------------------------------ models --

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(80))
    passport_number = db.Column(db.String(40))
    created_at = db.Column(db.String(10), nullable=False)

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)


class Page(db.Model):
    __tablename__ = 'pages'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    upstream_path = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    nav = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)          # JSON lines
    outline_json = db.Column(db.Text, nullable=False)
    links_json = db.Column(db.Text, nullable=False)
    docs_json = db.Column(db.Text, nullable=False)
    last_modified = db.Column(db.String(40))

    @property
    def lines(self):
        return json.loads(self.body)

    @property
    def outline(self):
        return json.loads(self.outline_json)

    @property
    def links(self):
        return json.loads(self.links_json)

    @property
    def docs(self):
        return json.loads(self.docs_json)


class Crossing(db.Model):
    __tablename__ = 'crossings'
    id = db.Column(db.Integer, primary_key=True)
    port_number = db.Column(db.String(20), nullable=False, index=True)
    port_name = db.Column(db.String(120), nullable=False)
    crossing_name = db.Column(db.String(160), nullable=False)
    border = db.Column(db.String(10), nullable=False)     # canada|mexico
    hours = db.Column(db.String(80))
    port_status = db.Column(db.String(40))
    snapshot_date = db.Column(db.String(20))
    snapshot_time = db.Column(db.String(20))
    construction_notice = db.Column(db.Text)
    lanes_json = db.Column(db.Text, nullable=False)        # COV/POV/PED lanes
    graph_json = db.Column(db.Text)                        # hourly series

    @property
    def lanes(self):
        return json.loads(self.lanes_json)

    @property
    def graph(self):
        return json.loads(self.graph_json) if self.graph_json else None

    @property
    def full_name(self):
        if self.crossing_name:
            return f"{self.port_name} - {self.crossing_name}"
        return self.port_name


class Port(db.Model):
    __tablename__ = 'ports'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    state = db.Column(db.String(4), nullable=False, index=True)
    code = db.Column(db.String(10))
    address = db.Column(db.Text)
    field_office = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    fax = db.Column(db.String(40))
    director = db.Column(db.String(120))
    hours = db.Column(db.Text)
    directions = db.Column(db.Text)
    facilities = db.Column(db.Text)
    last_modified = db.Column(db.String(40))
    has_detail = db.Column(db.Boolean, nullable=False, default=False)


class NewsRelease(db.Model):
    __tablename__ = 'news_releases'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(240), unique=True, nullable=False)
    title = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(20))
    location = db.Column(db.String(120))
    category = db.Column(db.String(60))   # National|Local Media Release
    body = db.Column(db.Text)
    images_json = db.Column(db.Text)
    href = db.Column(db.String(240))

    @property
    def images(self):
        return json.loads(self.images_json) if self.images_json else []


class CbpForm(db.Model):
    __tablename__ = 'forms'
    id = db.Column(db.Integer, primary_key=True)
    catalog_key = db.Column(db.String(80), unique=True, nullable=False)
    form_number = db.Column(db.String(40), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(240))
    listed_date = db.Column(db.String(40))
    pdf_url = db.Column(db.String(300))
    file = db.Column(db.String(200))      # static/external_cache/forms/...
    sha256 = db.Column(db.String(64))
    bytes = db.Column(db.Integer)
    raw = db.Column(db.Text)


class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    control = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.Text, nullable=False)
    careers_title = db.Column(db.Text)
    org = db.Column(db.String(120))
    category = db.Column(db.String(80))
    department = db.Column(db.String(160))
    series_grade = db.Column(db.String(60))
    salary = db.Column(db.String(120))
    location = db.Column(db.String(200))
    closing = db.Column(db.String(20))
    announcement_number = db.Column(db.String(60))
    promotion_potential = db.Column(db.String(12))
    telework = db.Column(db.String(40))
    drug_test = db.Column(db.String(30))
    appointment_type = db.Column(db.String(40))
    work_schedule = db.Column(db.String(80))
    summary = db.Column(db.Text)
    duties = db.Column(db.Text)
    requirements = db.Column(db.Text)
    qualifications = db.Column(db.Text)
    open_to = db.Column(db.Text)
    url = db.Column(db.String(120))


class CareerPath(db.Model):
    __tablename__ = 'career_paths'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    events_json = db.Column(db.Text)
    jobs_json = db.Column(db.Text)


class CareerEvent(db.Model):
    __tablename__ = 'career_events'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(40))
    event = db.Column(db.String(160))
    location = db.Column(db.String(120))
    kind = db.Column(db.String(60))


class VwpCountry(db.Model):
    __tablename__ = 'vwp_countries'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)


class TtpProgram(db.Model):
    __tablename__ = 'ttp_programs'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    fee = db.Column(db.Integer, nullable=False)
    years = db.Column(db.Integer, nullable=False)
    audience = db.Column(db.String(200))
    includes_json = db.Column(db.Text)

    @property
    def includes(self):
        return json.loads(self.includes_json) if self.includes_json else []


class EnrollmentCenter(db.Model):
    __tablename__ = 'enrollment_centers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    state = db.Column(db.String(40), nullable=False)
    address = db.Column(db.Text)
    hours = db.Column(db.Text)
    contact = db.Column(db.String(160))


# ------------------------------------------------------- traveler accounts --

class EstaApplication(db.Model):
    __tablename__ = 'esta_applications'
    id = db.Column(db.Integer, primary_key=True)
    application_number = db.Column(db.String(24), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    family_name = db.Column(db.String(80), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    birth_date = db.Column(db.String(20), nullable=False)
    gender = db.Column(db.String(20))
    citizenship = db.Column(db.String(80), nullable=False)
    passport_number = db.Column(db.String(40), nullable=False)
    passport_issue_country = db.Column(db.String(80))
    passport_expiry = db.Column(db.String(20))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    address_city = db.Column(db.String(80))
    address_country = db.Column(db.String(80))
    travel_purpose = db.Column(db.String(20))
    destination_address = db.Column(db.String(200))
    status = db.Column(db.String(40), nullable=False, default='Pending')
    fee_usd = db.Column(db.Float, nullable=False, default=ESTA_FEE_USD)
    created_at = db.Column(db.String(20), nullable=False)
    expires_on = db.Column(db.String(20))
    user = db.relationship('User', backref='esta_applications')


class I94Record(db.Model):
    __tablename__ = 'i94_records'
    id = db.Column(db.Integer, primary_key=True)
    admission_number = db.Column(db.String(20), unique=True, nullable=False)
    family_name = db.Column(db.String(80), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    birth_date = db.Column(db.String(20), nullable=False)
    citizenship = db.Column(db.String(80), nullable=False)
    passport_number = db.Column(db.String(40), nullable=False, index=True)
    class_of_admission = db.Column(db.String(20), nullable=False)
    most_recent_entry = db.Column(db.String(20), nullable=False)
    admitted_until = db.Column(db.String(20), nullable=False)
    port_of_entry = db.Column(db.String(120), nullable=False)
    issued_at = db.Column(db.String(20))


class TtpApplication(db.Model):
    __tablename__ = 'ttp_applications'
    id = db.Column(db.Integer, primary_key=True)
    application_number = db.Column(db.String(24), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    program = db.Column(db.String(40), nullable=False)   # global-entry|nexus|...
    family_name = db.Column(db.String(80), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    birth_date = db.Column(db.String(20), nullable=False)
    citizenship = db.Column(db.String(80))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    passport_number = db.Column(db.String(40))
    status = db.Column(db.String(60), nullable=False,
                       default='Pending Review')
    fee_usd = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.String(20), nullable=False)
    interview_center_id = db.Column(db.Integer,
                                    db.ForeignKey('enrollment_centers.id'))
    interview_date = db.Column(db.String(20))
    interview_slot = db.Column(db.String(40))
    user = db.relationship('User', backref='ttp_applications')
    interview_center = db.relationship('EnrollmentCenter',
                                       backref='interviews')


class SavedCrossing(db.Model):
    __tablename__ = 'saved_crossings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    crossing_id = db.Column(db.Integer, db.ForeignKey('crossings.id'),
                            nullable=False)
    created_at = db.Column(db.String(20), nullable=False)
    user = db.relationship('User', backref='saved_crossings')
    crossing = db.relationship('Crossing', backref='savers')


class SavedPort(db.Model):
    __tablename__ = 'saved_ports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    port_id = db.Column(db.Integer, db.ForeignKey('ports.id'), nullable=False)
    created_at = db.Column(db.String(20), nullable=False)
    user = db.relationship('User', backref='saved_ports')
    port = db.relationship('Port', backref='savers')


class SavedJob(db.Model):
    __tablename__ = 'saved_jobs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    created_at = db.Column(db.String(20), nullable=False)
    user = db.relationship('User', backref='saved_jobs')
    job = db.relationship('Job', backref='savers')


class SavedForm(db.Model):
    __tablename__ = 'saved_forms'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    form_id = db.Column(db.Integer, db.ForeignKey('forms.id'), nullable=False)
    created_at = db.Column(db.String(20), nullable=False)
    user = db.relationship('User', backref='saved_forms')
    form = db.relationship('CbpForm', backref='savers')


# ------------------------------------------------------------------ seeding --

def _seed_gate(model, count_needed=1):
    """Whole-function gate: seed only when the table is empty."""
    return db.session.query(model).count() == 0


def seed_pages():
    if not _seed_gate(Page):
        return
    for rec in _load('pages.json'):
        db.session.add(Page(
            slug=rec['slug'], upstream_path=rec['upstream_path'],
            title=rec['title'], category=rec['category'], nav=rec['nav'],
            body=json.dumps(rec['lines'], ensure_ascii=False),
            outline_json=json.dumps(rec['outline'], ensure_ascii=False),
            links_json=json.dumps(rec['links'], ensure_ascii=False),
            docs_json=json.dumps(rec['docs'], ensure_ascii=False),
            last_modified=rec['last_modified']))
    db.session.commit()


def seed_crossings():
    if not _seed_gate(Crossing):
        return
    graphs = _load('bwt_graphs.json')
    for rec in _load('bwt_crossings.json'):
        g = graphs.get(rec['port_number'])
        db.session.add(Crossing(
            port_number=rec['port_number'], port_name=rec['port_name'],
            crossing_name=rec['crossing_name'], border=rec['border'],
            hours=rec['hours'], port_status=rec['port_status'],
            snapshot_date=rec['date'], snapshot_time=rec['time'],
            construction_notice=rec['construction_notice'],
            lanes_json=json.dumps({'commercial': rec['commercial'],
                                   'passenger': rec['passenger'],
                                   'pedestrian': rec['pedestrian']},
                                  ensure_ascii=False),
            graph_json=(json.dumps(g, ensure_ascii=False)
                        if g else None)))
    db.session.commit()


def seed_ports():
    if not _seed_gate(Port):
        return
    n = 0
    for rec in _load('ports.json'):
        slug = rec['slug'] or f"port-{n}"
        n += 1
        db.session.add(Port(
            name=rec['name'], slug=slug, state=rec['state'],
            code=rec['code'], address=rec['address'],
            field_office=rec['field_office'], phone=rec['phone'],
            fax=rec['fax'], director=rec['director'], hours=rec['hours'],
            directions=rec['directions'], facilities=rec['facilities'],
            last_modified=rec['last_modified'],
            has_detail=rec['has_detail']))
    db.session.commit()


def seed_news():
    if not _seed_gate(NewsRelease):
        return
    for rec in _load('releases.json'):
        db.session.add(NewsRelease(
            slug=rec['slug'], title=rec['title'], date=rec['date'],
            location=rec['location'], category=rec['category'],
            body=rec['body'],
            images_json=json.dumps(rec['images'], ensure_ascii=False),
            href=rec['href']))
    db.session.commit()


def seed_forms():
    if not _seed_gate(CbpForm):
        return
    for rec in _load('forms.json'):
        db.session.add(CbpForm(
            catalog_key=rec['catalog_key'],
            form_number=rec['form_number'], name=rec['name'],
            title=rec['title'], listed_date=rec['date'],
            pdf_url=rec['pdf_url'], file=rec['file'],
            sha256=rec['sha256'], bytes=rec['bytes'], raw=rec['raw']))
    db.session.commit()


def seed_jobs():
    if not _seed_gate(Job):
        return
    for rec in _load('jobs.json'):
        db.session.add(Job(**rec))
    db.session.commit()


def seed_careers():
    if _seed_gate(CareerPath):
        for rec in _load('career_paths.json'):
            db.session.add(CareerPath(
                slug=rec['slug'], title=rec['title'],
                description=rec['description'],
                events_json=json.dumps(rec['events'], ensure_ascii=False),
                jobs_json=json.dumps(rec['jobs'], ensure_ascii=False)))
        db.session.commit()
    if _seed_gate(CareerEvent):
        for rec in _load('career_events.json'):
            db.session.add(CareerEvent(date=rec['date'], event=rec['event'],
                                       location=rec.get('location', ''),
                                       kind=rec['type']))
        db.session.commit()


def seed_reference():
    if _seed_gate(VwpCountry):
        for name in _load('vwp_countries.json'):
            db.session.add(VwpCountry(name=name))
        db.session.commit()
    if _seed_gate(TtpProgram):
        for rec in _load('ttp_programs.json'):
            db.session.add(TtpProgram(
                slug=rec['slug'], name=rec['name'], fee=rec['fee'],
                years=rec['years'], audience=rec['audience'],
                includes_json=json.dumps(rec['includes'])))
        db.session.commit()
    if _seed_gate(EnrollmentCenter):
        for rec in _load('enrollment_centers.json'):
            db.session.add(EnrollmentCenter(
                name=rec['name'], state=rec['state'],
                address=rec['address'], hours=rec['hours'],
                contact=rec['contact']))
        db.session.commit()


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    users = [
        {'username': 'alice_j', 'email': 'alice.j@test.com',
         'display': 'Alice Johnson', 'country': 'Germany',
         'passport_number': 'DE29384756'},
        {'username': 'bob_c', 'email': 'bob.c@test.com',
         'display': 'Bob Chen', 'country': 'United States',
         'passport_number': 'US556677889'},
        {'username': 'carol_d', 'email': 'carol.d@test.com',
         'display': 'Carol Davis', 'country': 'United Kingdom',
         'passport_number': 'GB778812345'},
        {'username': 'dana_k', 'email': 'dana.k@test.com',
         'display': 'Dana Kim', 'country': 'South Korea',
         'passport_number': 'KR8811992'},
    ]
    created = {}
    for u in users:
        user = User(email=u['email'], username=u['username'],
                   display_name=u['display'],
                   password_hash=BENCHMARK_PASSWORD_HASH,
                   country=u['country'],
                   passport_number=u['passport_number'],
                   created_at='2026-09-01')
        db.session.add(user)
        created[u['username']] = user
    db.session.commit()

    alice = created['alice_j']
    bob = created['bob_c']
    carol = created['carol_d']
    dana = created['dana_k']

    # Alice: approved ESTA (applied 2026-08-20, valid two years)
    db.session.add(EstaApplication(
        application_number='ESTA-88291045', user_id=alice.id,
        family_name='Johnson', first_name='Alice',
        birth_date='1990-04-12', gender='Female', citizenship='Germany',
        passport_number='DE29384756', passport_issue_country='Germany',
        passport_expiry='2030-06-30', email='alice.j@test.com',
        phone='+49 30 5550123', address_city='Berlin',
        address_country='Germany', travel_purpose='Business',
        destination_address='45 Market St, San Francisco, CA',
        status='Authorization Approved', created_at='2026-08-20',
        expires_on='2028-08-20'))
    # Carol: pending ESTA (applied recently)
    db.session.add(EstaApplication(
        application_number='ESTA-88452017', user_id=carol.id,
        family_name='Davis', first_name='Carol',
        birth_date='1985-11-02', gender='Female',
        citizenship='United Kingdom', passport_number='GB778812345',
        passport_issue_country='United Kingdom',
        passport_expiry='2029-03-01', email='carol.d@test.com',
        phone='+44 20 7946 0102', address_city='London',
        address_country='United Kingdom', travel_purpose='Tourism',
        destination_address='350 Fifth Ave, New York, NY',
        status='Authorization Pending', created_at='2026-09-26',
        expires_on=None))
    # Bob: Global Entry conditionally approved, interview not yet scheduled
    db.session.add(TtpApplication(
        application_number='GE-77031188', user_id=bob.id,
        program='global-entry', family_name='Chen', first_name='Bob',
        birth_date='1988-07-19', citizenship='United States',
        email='bob.c@test.com', phone='+1 202 555 0199',
        passport_number='US556677889',
        status='Conditionally Approved — Schedule Interview',
        fee_usd=120.0, created_at='2026-09-10'))
    # Dana: Global Entry interview scheduled at LAX enrollment center
    lax = EnrollmentCenter.query.filter(
        EnrollmentCenter.name.like('%Los Angeles%')).first()
    db.session.add(TtpApplication(
        application_number='GE-77554402', user_id=dana.id,
        program='global-entry', family_name='Kim', first_name='Dana',
        birth_date='1993-02-25', citizenship='United States',
        email='dana.k@test.com', phone='+1 213 555 0143',
        passport_number='KR8811992',
        status='Interview Scheduled', fee_usd=120.0,
        created_at='2026-09-05',
        interview_center_id=lax.id if lax else None,
        interview_date='2026-10-14', interview_slot='10:00 a.m.'))

    # I-94 records for benchmark travelers (electronic arrival records)
    recs = [
        ('269745632011', 'Johnson', 'Alice', '1990-04-12', 'Germany',
         'DE29384756', 'VWP B-1', '2026-06-14', '2026-09-12',
         'Washington Dulles International Airport', 'alice'),
        ('269745641088', 'Chen', 'Bob', '1988-07-19', 'United States',
         'US556677889', 'US Citizen', '2026-09-03', '',
         'San Ysidro, California - Pedestrian', 'bob'),
        ('269745650222', 'Davis', 'Carol', '1985-11-02', 'United Kingdom',
         'GB778812345', 'VWP B-2', '2026-03-22', '2026-06-20',
         'John F. Kennedy International Airport', 'carol'),
        ('269745663901', 'Kim', 'Dana', '1993-02-25', 'South Korea',
         'KR8811992', 'F-1', '2025-08-18', 'D/S',
         'Los Angeles International Airport', 'dana'),
    ]
    for adm, fam, first, bday, cit, passp, cls, entry, until, poe, owner in recs:
        db.session.add(I94Record(
            admission_number=adm, family_name=fam, first_name=first,
            birth_date=bday, citizenship=cit, passport_number=passp,
            class_of_admission=cls, most_recent_entry=entry,
            admitted_until=until, port_of_entry=poe, issued_at=entry))

    # Watchlist fixtures. Dana's saved crossing is pinned to Otay Mesa -
    # Passenger (port_number 250601) so the account premise (a crossing
    # with a live standard passenger delay and Ready Lane delay) matches
    # the seed data (the first Otay Mesa record, 250609, reports
    # "Update Pending" on every lane).
    sysd = Crossing.query.filter_by(port_name='San Ysidro').first()
    otay = Crossing.query.filter_by(port_number='250601').first()
    blaine = Crossing.query.filter_by(port_name='Blaine').first()
    if sysd:
        db.session.add(SavedCrossing(user_id=bob.id, crossing_id=sysd.id,
                                    created_at='2026-09-12'))
    if otay:
        db.session.add(SavedCrossing(user_id=dana.id, crossing_id=otay.id,
                                     created_at='2026-09-15'))
    if blaine:
        db.session.add(SavedCrossing(user_id=alice.id, crossing_id=blaine.id,
                                     created_at='2026-09-18'))
    poe_tx = Port.query.filter(Port.name.like('San Ysidro%')).first()
    if poe_tx:
        db.session.add(SavedPort(user_id=bob.id, port_id=poe_tx.id,
                                created_at='2026-09-12'))
    bpa = Job.query.filter(Job.title.like('Border Patrol Agent%')).first()
    if bpa:
        db.session.add(SavedJob(user_id=dana.id, job_id=bpa.id,
                               created_at='2026-09-20'))
    f7501 = CbpForm.query.filter_by(form_number='7501').first()
    if f7501:
        db.session.add(SavedForm(user_id=carol.id, form_id=f7501.id,
                                 created_at='2026-09-22'))
    db.session.commit()


# ------------------------------------------------------------------ helpers --

STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut',
    'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia', 'GU': 'Guam',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana',
    'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
    'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts',
    'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico',
    'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota',
    'MP': 'Commonwealth of Northern Mariana Islands', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania',
    'PR': 'Puerto Rico', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'VI': 'U.S. Virgin Islands',
    'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin',
    'WY': 'Wyoming',
}

LANE_LABELS = {
    'Standard': 'Standard Lanes',
    'FAST': 'FAST Lanes',
    'NEXUS_SENTRI': 'NEXUS/SENTRI Lanes',
    'READY': 'Ready Lanes',
}

MODE_LABELS = {'commercial': 'Commercial Vehicle',
               'passenger': 'Passenger Vehicle',
               'pedestrian': 'Pedestrian'}


def _lane_summary(crossing, mode):
    block = crossing.lanes.get(mode, {})
    out = []
    for key in ('Standard', 'FAST', 'NEXUS_SENTRI', 'READY'):
        lane = block.get(key)
        if lane:
            out.append({'name': LANE_LABELS[key], 'status': lane['status'],
                        'delay': lane['delay'], 'open': lane['open'],
                        'updated': lane['updated']})
    return out


def _max_delay(crossing):
    best = None
    for mode in ('commercial', 'passenger', 'pedestrian'):
        for lane in _lane_summary(crossing, mode):
            if lane['delay'] is not None and (best is None or
                                              lane['delay'] > best[0]):
                best = (lane['delay'], mode, lane['name'])
    return best


def _number_for(prefix, seed_text):
    """Deterministic reference number from the form input."""
    digest = hashlib.sha256(f"{prefix}|{seed_text}".encode()).hexdigest()
    tail = digest[:7].upper()
    return f"{prefix}-{tail}"


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', **_ctx()), 404


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


@app.template_filter('mmddyyyy')
def mmddyyyy(value):
    if not value:
        return ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    return value


# -------------------------------------------------------------------- views --

@app.route('/_health')
def health():
    return jsonify(ok=True, site=SITE_NAME,
                   pages=Page.query.count(),
                   crossings=Crossing.query.count(),
                   ports=Port.query.count(),
                   releases=NewsRelease.query.count(),
                   forms=CbpForm.query.count(),
                   jobs=Job.query.count(),
                   users=User.query.count())


NAV_SECTIONS = [
    ('Travel', [
        ('U.S. Citizens/LPR', '/travel/us-citizens'),
        ('International Visitors', '/travel/international-visitors'),
        ('Trusted Traveler Programs', '/travel/trusted-traveler-programs'),
        ('Advisories and Wait Times', '/travel/advisories-wait-times'),
        ('Biometrics', '/travel/biometrics'),
    ]),
    ('Border Security', [
        ('At Ports of Entry', '/border-security/ports-entry'),
    ]),
    ('Newsroom', [
        ('Media Releases', '/newsroom/media-releases/all'),
        ('Announcements', '/newsroom/announcements'),
        ('Forms', '/newsroom/publications/forms'),
    ]),
    ('Trade', [
        ('Basic Import and Export', '/trade/basic-import-export'),
        ('Priority Trade Issues', '/trade/priority-issues'),
        ('ACE', '/trade/automated'),
        ('Informed Compliance', '/trade/rulings/informed-compliance-publications'),
    ]),
    ('Careers', [
        ('Career Paths', '/careers/career-paths'),
        ('Search Jobs', '/careers/search'),
        ('Events', '/careers/events'),
    ]),
    ('About CBP & Contact', [
        ('About CBP', '/about'),
        ('Contact Us', '/about/contact'),
        ('Locate a Port of Entry', '/contact/ports'),
    ]),
]


def _ctx(**kw):
    base = {
        'nav_sections': NAV_SECTIONS,
        'user': current_user,
        'mirror_today': MIRROR_TODAY,
    }
    base.update(kw)
    return base


def _page_or_404(slug):
    page = Page.query.filter_by(slug=slug).first()
    if not page:
        abort(404)
    return page


def _render_page(slug, extra_title=None, **extra):
    page = _page_or_404(slug)
    return render_template(
        'content_page.html', page=page, extra_title=extra_title,
        **_ctx(**extra))


@app.route('/')
def home():
    releases = (NewsRelease.query.order_by(NewsRelease.date.desc())
                .limit(3).all())
    jobs = Job.query.order_by(Job.control.desc()).limit(3).all()
    crossings = Crossing.query.count()
    return render_template('home.html', releases=releases, jobs=jobs,
                           crossings=crossings, **_ctx())


# ------------------------------------------------------------- static pages --

CONTENT_SLUGS = {
    'travel': 'travel',
    'travel/us-citizens': 'us_citizens',
    'travel/us-citizens/know-before-you-go': 'know_before_you_go',
    'travel/us-citizens/mobile-passport-control': 'mpc',
    'travel/us-citizens/canada-mexico-travel': 'canada_mexico',
    'travel/international-visitors': 'intl_visitors',
    'travel/international-visitors/know-before-you-visit':
        'know_before_you_visit',
    'travel/international-visitors/visa-waiver-program': 'vwp',
    'travel/biometrics': 'biometrics',
    'border-security/ports-entry': 'ports_entry',
    'trade': 'trade',
    'trade/basic-import-export': 'basic_import_export',
    'trade/basic-import-export/importing-car': 'importing_car',
    'trade/basic-import-export/internet-purchases': 'internet_purchases',
    'trade/basic-import-export/importer-exporter-tips':
        'importer_exporter_tips',
    'trade/priority-issues': 'priority_issues',
    'trade/priority-issues/adcvd': 'ptl_adcvd',
    'trade/priority-issues/ipr': 'ptl_ipr',
    'trade/priority-issues/import-safety': 'ptl_import_safety',
    'trade/priority-issues/textiles': 'ptl_textiles',
    'trade/priority-issues/quotas': 'ptl_quotas',
    'trade/priority-issues/revenue': 'ptl_revenue',
    'trade/priority-issues/trade-agreements': 'ptl_trade_agreements',
    'trade/automated': 'ace',
    'trade/rulings/informed-compliance-publications': 'icp',
    'newsroom': 'newsroom',
    'newsroom/announcements': 'announcements',
    'about': 'about',
    'about/contact': 'contact',
}


# Upstream section pages whose left navigation lists child pages. Rendered
# as an "In this section" list on the parent page (mirrors the upstream
# sidebar; guarantees every child page has an in-site in-link).
SECTION_CHILDREN = {
    'us_citizens': ['know_before_you_go', 'mpc', 'canada_mexico'],
}

# Mirror routes for tool pages rendered outside content_page.html.
TOOL_ROUTES = {
    'esta': '/travel/international-visitors/esta',
    'i94': '/travel/international-visitors/i-94',
    'ttp': '/travel/trusted-traveler-programs',
    'global_entry': '/travel/trusted-traveler-programs/global-entry',
    'nexus': '/travel/trusted-traveler-programs/nexus',
    'sentri': '/travel/trusted-traveler-programs/sentri',
    'fast': '/travel/trusted-traveler-programs/fast',
    'tsa_precheck': '/travel/trusted-traveler-programs/tsa-precheck',
    'advisories_wait_times': '/travel/advisories-wait-times',
    'ports_landing': '/contact/ports',
    'forms': '/newsroom/publications/forms',
}

# Upstream link paths that need an explicit alias to a mirror route.
UPSTREAM_LINK_ALIASES = {
    '/': '/',
    '/about/contact/ports': '/contact/ports',
    '/careers': '/careers',
}

_MIRROR_LINK_MAP = None


def _mirror_link_map():
    """Map every mirrored upstream path to its mirror route."""
    global _MIRROR_LINK_MAP
    if _MIRROR_LINK_MAP is None:
        routes = {slug: route for route, slug in CONTENT_SLUGS.items()}
        routes.update(TOOL_ROUTES)
        mapping = dict(UPSTREAM_LINK_ALIASES)
        for page in Page.query.all():
            route = routes.get(page.slug)
            if route and page.upstream_path:
                if not route.startswith('/'):
                    route = '/' + route
                mapping.setdefault(page.upstream_path, route)
        _MIRROR_LINK_MAP = mapping
    return _MIRROR_LINK_MAP


def _related_links(page):
    """Internal (mirror-mapped) links scraped from the upstream page,
    rewritten to relative mirror routes. Upstream-only destinations that the
    mirror does not carry are dropped rather than dead-linked."""
    routes = _mirror_link_map()
    seen, out = set(), []
    for link in page.links:
        url = link.get('url') or ''
        m = re.match(r'https?://(?:www\.)?cbp\.gov(/.*)$', url)
        if not m:
            continue
        path = m.group(1).split('?')[0].split('#')[0]
        if path != '/' and path.endswith('/'):
            path = path.rstrip('/')
        route = routes.get(path)
        if not route or route in seen:
            continue
        seen.add(route)
        out.append({'url': route, 'label': link.get('label') or url})
    return out


@app.route('/<path:page_path>')
def content_page(page_path):
    slug = CONTENT_SLUGS.get(page_path)
    if slug is None:
        abort(404)
    page = _page_or_404(slug)
    extra = {}
    if slug == 'vwp':
        extra['countries'] = VwpCountry.query.order_by(VwpCountry.name).all()
    if slug == 'priority_issues':
        routes = {slug_: '/' + route if not route.startswith('/') else route
                  for route, slug_ in CONTENT_SLUGS.items()}
        extra['children'] = [
            (routes['ptl_adcvd'],
             'Antidumping and Countervailing Duty (AD/CVD)'),
            (routes['ptl_ipr'], 'Intellectual Property Rights (IPR)'),
            (routes['ptl_import_safety'], 'Import Safety'),
            (routes['ptl_textiles'], 'Textiles/Wearing Apparel'),
            (routes['ptl_quotas'], 'Agriculture and Quota'),
            (routes['ptl_revenue'], 'Revenue'),
            (routes['ptl_trade_agreements'], 'Trade Agreements'),
        ]
    extra['related_links'] = _related_links(page)
    if slug in SECTION_CHILDREN:
        routes = {slug_: '/' + route if not route.startswith('/') else route
                  for route, slug_ in CONTENT_SLUGS.items()}
        extra['child_nav'] = [
            (routes[child], Page.query.filter_by(slug=child).first().title)
            for child in SECTION_CHILDREN[slug]
            if Page.query.filter_by(slug=child).first()]
    # Don't repeat in Related Links the routes this page already lists in
    # its dedicated sections (keeps e.g. the Priority Trade Issues page a
    # single seven-item list).
    shown = {route for route, _ in extra.get('child_nav', [])}
    shown.update(route for route, _ in extra.get('children', []))
    extra['related_links'] = [l for l in extra['related_links']
                              if l['url'] not in shown]
    return render_template('content_page.html', page=page,
                           **_ctx(**extra))


# --------------------------------------------------------------- travel tools --

@app.route('/travel/international-visitors/esta')
def esta_page():
    page = _page_or_404('esta')
    countries = VwpCountry.query.order_by(VwpCountry.name).all()
    return render_template('esta.html', page=page, countries=countries,
                           fee=ESTA_FEE_USD, **_ctx())


ESTA_STEPS = ['disclaimers', 'applicant', 'personal', 'travel',
              'eligibility', 'review', 'pay']


@app.route('/esta/apply', methods=['GET', 'POST'])
def esta_apply():
    step = request.values.get('step', 'disclaimers')
    if step not in ESTA_STEPS:
        abort(404)
    data = session.get('esta_draft') or {}
    form = {k: v.strip() for k, v in request.form.items()
            if k not in ('step', 'next', 'csrf_token')}
    if request.method == 'POST':
        data.update(form)
        session['esta_draft'] = data
        idx = ESTA_STEPS.index(step)
        nxt = request.form.get('next')
        if nxt == 'back' and idx > 0:
            return redirect(url_for('esta_apply', step=ESTA_STEPS[idx - 1]))
        if nxt == 'next' and idx < len(ESTA_STEPS) - 1:
            return redirect(url_for('esta_apply', step=ESTA_STEPS[idx + 1]))
        if nxt == 'submit':
            # finalize + pay
            citizenship = data.get('citizenship', '')
            country = VwpCountry.query.filter_by(name=citizenship).first()
            eligibility_flags = [data.get(k) for k in
                                ('q_a', 'q_b', 'q_c', 'q_d', 'q_e')]
            approved = (country is not None
                        and all(f == 'No' for f in eligibility_flags))
            app_num = _number_for('ESTA',
                                  json.dumps(data, sort_keys=True))
            status = ('Authorization Approved' if approved
                      else 'Travel Not Authorized')
            expires = (date(2028, 9, 28).isoformat() if approved else None)
            record = EstaApplication(
                application_number=app_num,
                user_id=current_user.id if current_user.is_authenticated
                else None,
                family_name=data.get('family_name', ''),
                first_name=data.get('first_name', ''),
                birth_date=data.get('birth_date', ''),
                gender=data.get('gender', ''),
                citizenship=citizenship,
                passport_number=data.get('passport_number', ''),
                passport_issue_country=data.get('passport_issue_country',
                                                citizenship),
                passport_expiry=data.get('passport_expiry', ''),
                email=data.get('email', ''),
                phone=data.get('phone', ''),
                address_city=data.get('address_city', ''),
                address_country=data.get('address_country', citizenship),
                travel_purpose=data.get('travel_purpose', ''),
                destination_address=data.get('destination_address', ''),
                status=status, created_at=MIRROR_TODAY.isoformat(),
                expires_on=expires)
            db.session.add(record)
            db.session.commit()
            session.pop('esta_draft', None)
            return redirect(url_for('esta_confirmation',
                                    application_number=app_num))
        # staying on the same step (validation-free prototype)
        return redirect(url_for('esta_apply', step=step))
    step_index = ESTA_STEPS.index(step)
    return render_template('esta_apply.html', step=step,
                           step_index=step_index, steps=ESTA_STEPS,
                           data=data, countries=VwpCountry.query.order_by(
                               VwpCountry.name).all(),
                           fee=ESTA_FEE_USD, **_ctx())


@app.route('/esta/confirmation/<application_number>')
def esta_confirmation(application_number):
    record = EstaApplication.query.filter_by(
        application_number=application_number).first_or_404()
    return render_template('esta_confirmation.html', record=record,
                           fee=ESTA_FEE_USD, **_ctx())


@app.route('/esta/check', methods=['GET', 'POST'])
def esta_check():
    record = None
    number = request.values.get('application_number', '').strip()
    passport = request.values.get('passport_number', '').strip()
    not_found = False
    if number or passport:
        q = EstaApplication.query
        if number:
            record = q.filter_by(application_number=number).first()
        elif passport:
            record = q.filter_by(passport_number=passport).first()
        not_found = record is None
    return render_template('esta_check.html', record=record,
                           number=number, passport=passport,
                           not_found=not_found, **_ctx())


@app.route('/travel/international-visitors/i-94')
def i94_page():
    page = _page_or_404('i94')
    return render_template('i94.html', page=page, **_ctx())


@app.route('/i94/request', methods=['GET', 'POST'])
def i94_request():
    record = None
    not_found = False
    form = {}
    if request.method == 'POST':
        form = {k: (v or '').strip() for k, v in request.form.items()}
        q = I94Record.query.filter_by(
            passport_number=form.get('passport_number', ''))
        rec = q.filter_by(family_name=form.get('family_name', ''),
                          first_name=form.get('first_name', ''),
                          birth_date=form.get('birth_date', '')).first()
        if rec is None:
            not_found = True
        else:
            record = rec
    return render_template('i94_request.html', record=record,
                           not_found=not_found, form=form, **_ctx())


# ------------------------------------------------------- trusted traveler ----

@app.route('/travel/trusted-traveler-programs')
def ttp_overview():
    page = _page_or_404('ttp')
    programs = TtpProgram.query.order_by(TtpProgram.id).all()
    return render_template('ttp_overview.html', page=page,
                           programs=programs, **_ctx())


@app.route('/travel/trusted-traveler-programs/<slug>')
def ttp_program(slug):
    programs = {'global-entry': 'global_entry', 'nexus': 'nexus',
                'sentri': 'sentri', 'fast': 'fast',
                'tsa-precheck': 'tsa_precheck'}
    if slug not in programs:
        abort(404)
    page = _page_or_404(programs[slug])
    program = TtpProgram.query.filter_by(slug=slug).first()
    return render_template('ttp_program.html', page=page, program=program,
                           **_ctx())


@app.route('/ttp/apply/<slug>', methods=['GET', 'POST'])
def ttp_apply(slug):
    program = TtpProgram.query.filter_by(slug=slug).first_or_404()
    if request.method == 'POST':
        data = {k: (v or '').strip() for k, v in request.form.items()
                if k not in ('csrf_token',)}
        app_num = _number_for('GE', json.dumps(data, sort_keys=True))
        record = TtpApplication(
            application_number=app_num,
            user_id=current_user.id if current_user.is_authenticated
            else None,
            program=program.slug,
            family_name=data.get('family_name', ''),
            first_name=data.get('first_name', ''),
            birth_date=data.get('birth_date', ''),
            citizenship=data.get('citizenship', ''),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            passport_number=data.get('passport_number', ''),
            status='Pending Review', fee_usd=program.fee,
            created_at=MIRROR_TODAY.isoformat())
        db.session.add(record)
        db.session.commit()
        return redirect(url_for('ttp_status', application_number=app_num))
    return render_template('ttp_apply.html', program=program, **_ctx())


@app.route('/ttp/status', methods=['GET', 'POST'])
def ttp_status_form():
    record = None
    not_found = False
    number = request.values.get('application_number', '').strip()
    if number:
        record = TtpApplication.query.filter_by(
            application_number=number).first()
        not_found = record is None
        if record is not None:
            return redirect(url_for('ttp_status',
                                    application_number=record.application_number))
    return render_template('ttp_status.html', record=record, number=number,
                           not_found=not_found, **_ctx())


@app.route('/ttp/status/<application_number>')
def ttp_status(application_number):
    record = TtpApplication.query.filter_by(
        application_number=application_number).first_or_404()
    return render_template('ttp_application.html', record=record,
                           program=TtpProgram.query.filter_by(
                               slug=record.program).first(), **_ctx())


@app.route('/ttp/schedule/<application_number>', methods=['GET', 'POST'])
def ttp_schedule(application_number):
    record = TtpApplication.query.filter_by(
        application_number=application_number).first_or_404()
    centers = EnrollmentCenter.query.order_by(EnrollmentCenter.state,
                                              EnrollmentCenter.name).all()
    if request.method == 'POST':
        center_id = request.form.get('center', '')
        idate = request.form.get('date', '')
        slot = request.form.get('slot', '')
        center = db.session.get(EnrollmentCenter, int(center_id)) if center_id \
            else None
        if not (center and idate and slot):
            flash('Select an enrollment center, a date and a time slot.')
            return redirect(url_for('ttp_schedule',
                                    application_number=application_number))
        record.interview_center_id = center.id
        record.interview_date = idate
        record.interview_slot = slot
        record.status = 'Interview Scheduled'
        db.session.commit()
        return redirect(url_for('ttp_status',
                                application_number=record.application_number))
    return render_template('ttp_schedule.html', record=record,
                           centers=centers, **_ctx())


# ----------------------------------------------------------- border waits ----

@app.route('/travel/advisories-wait-times')
def advisories_wait_times():
    page = _page_or_404('advisories_wait_times')
    crossings = Crossing.query.count()
    return render_template('advisories.html', page=page,
                           crossings=crossings, **_ctx())


@app.route('/bwt')
def bwt():
    border = request.args.get('border', 'all')
    q = request.args.get('q', '').strip().lower()
    sort = request.args.get('sort', 'name')
    page_no = max(1, request.args.get('page', 1, type=int) or 1)
    per_page = 10
    query = Crossing.query
    if border in ('canada', 'mexico'):
        query = query.filter_by(border=border)
    if q:
        query = query.filter(db.or_(
            db.func.lower(Crossing.port_name).like(f'%{q}%'),
            db.func.lower(Crossing.crossing_name).like(f'%{q}%')))
    if sort == 'delay':
        # python-side sort: max delay desc, then name
        all_rows = query.all()
        all_rows.sort(key=lambda c: (
            -(_max_delay(c)[0] if _max_delay(c) else -1),
            c.port_name, c.crossing_name))
        total = len(all_rows)
        rows = all_rows[(page_no - 1) * per_page: page_no * per_page]
    else:
        query = query.order_by(Crossing.port_name, Crossing.crossing_name)
        total = query.count()
        rows = (query.offset((page_no - 1) * per_page)
                .limit(per_page).all())
    pages_count = max(1, (total + per_page - 1) // per_page)
    return render_template('bwt.html', rows=rows, border=border, q=q,
                           sort=sort, page=page_no, pages=pages_count,
                           total=total, **_ctx())


@app.route('/bwt/crossing/<port_number>')
def bwt_crossing(port_number):
    crossing = Crossing.query.filter_by(
        port_number=port_number).first_or_404()
    return render_template('bwt_crossing.html', crossing=crossing,
                           lane_rows={
                               mode: _lane_summary(crossing, mode)
                               for mode in ('commercial', 'passenger',
                                            'pedestrian')},
                           max_delay=_max_delay(crossing), **_ctx())


# -------------------------------------------------------------------- ports --

@app.route('/contact/ports')
def ports_landing():
    page = _page_or_404('ports_landing')
    states = (db.session.query(Port.state, db.func.count(Port.id))
              .group_by(Port.state).order_by(Port.state).all())
    return render_template('ports_landing.html', page=page,
                           states=[(st, STATE_NAMES.get(st, st), n)
                                   for st, n in states], **_ctx())


@app.route('/about/contact/ports/<state>')
def ports_state(state):
    state = state.upper()
    if state not in STATE_NAMES:
        abort(404)
    ports = (Port.query.filter_by(state=state)
            .order_by(Port.name).all())
    return render_template('ports_state.html', state=state,
                           state_name=STATE_NAMES[state], ports=ports,
                           **_ctx())


@app.route('/about/contact/ports/field-office/<slug>')
def ports_field_office(slug):
    office = (Port.query.filter_by(slug=slug).first())
    if not office:
        abort(404)
    peers = Port.query.filter_by(field_office=office.field_office) \
        .order_by(Port.state, Port.name).all()
    return render_template('ports_field_office.html', office=office,
                           peers=peers, **_ctx())


@app.route('/contact/ports/<slug>')
@app.route('/about/contact/ports/port/<slug>')
def port_detail(slug):
    port = Port.query.filter_by(slug=slug).first_or_404()
    related = Port.query.filter_by(field_office=port.field_office) \
        .filter(Port.id != port.id).limit(6).all()
    return render_template('port_detail.html', port=port, related=related,
                           **_ctx())


@app.route('/contact/ports-search')
def ports_search():
    q = request.args.get('q', '').strip()
    rows = []
    if q:
        rows = Port.query.filter(db.or_(
            db.func.lower(Port.name).like(f'%{q.lower()}%'),
            Port.code == q.strip(),
            db.func.lower(Port.address).like(f'%{q.lower()}%'))) \
            .order_by(Port.state, Port.name).limit(50).all()
    return render_template('ports_search.html', q=q, rows=rows, **_ctx())


# ----------------------------------------------------------------- newsroom --

@app.route('/newsroom/media-releases/all')
def media_releases():
    category = request.args.get('category', 'all')
    q = request.args.get('q', '').strip().lower()
    page_no = max(1, request.args.get('page', 1, type=int) or 1)
    per_page = 8
    query = NewsRelease.query
    if category in ('national', 'local'):
        query = query.filter_by(category=(
            'National Media Release' if category == 'national'
            else 'Local Media Release'))
    if q:
        query = query.filter(db.or_(
            db.func.lower(NewsRelease.title).like(f'%{q}%'),
            db.func.lower(NewsRelease.body).like(f'%{q}%')))
    query = query.order_by(NewsRelease.date.desc(), NewsRelease.slug)
    total = query.count()
    rows = query.offset((page_no - 1) * per_page).limit(per_page).all()
    pages_count = max(1, (total + per_page - 1) // per_page)
    return render_template('releases.html', rows=rows, category=category,
                           q=q, page=page_no, pages=pages_count,
                           total=total, **_ctx())


@app.route('/newsroom/<kind>/<slug>')
def release_detail(kind, slug):
    if kind not in ('national-media-release', 'local-media-release'):
        abort(404)
    release = NewsRelease.query.filter_by(slug=slug).first_or_404()
    related = (NewsRelease.query.filter(NewsRelease.id != release.id)
               .order_by(NewsRelease.date.desc()).limit(4).all())
    return render_template('release_detail.html', release=release,
                           related=related, **_ctx())


# -------------------------------------------------------------------- forms --

@app.route('/newsroom/publications/forms')
def forms_catalog():
    q = request.args.get('q', '').strip().lower()
    query = CbpForm.query
    if q:
        query = query.filter(db.or_(
            db.func.lower(CbpForm.form_number).like(f'%{q}%'),
            db.func.lower(CbpForm.name).like(f'%{q}%'),
            db.func.lower(CbpForm.title).like(f'%{q}%')))
    rows = query.order_by(CbpForm.form_number).all()
    return render_template('forms.html', rows=rows, q=q, **_ctx())


@app.route('/newsroom/publications/forms/<catalog_key>')
def form_detail(catalog_key):
    form = CbpForm.query.filter_by(catalog_key=catalog_key).first_or_404()
    return render_template('form_detail.html', form=form, **_ctx())


@app.route('/forms/download/<catalog_key>')
def form_download(catalog_key):
    form = CbpForm.query.filter_by(catalog_key=catalog_key).first_or_404()
    if not form.file or not os.path.isfile(os.path.join(BASE_DIR, form.file)):
        abort(404)
    directory = os.path.join(BASE_DIR, os.path.dirname(form.file))
    filename = os.path.basename(form.file)
    return send_from_directory(directory, filename,
                               as_attachment=True,
                               download_name=filename)


# ------------------------------------------------------------------ careers --

@app.route('/careers')
def careers_home():
    paths = CareerPath.query.order_by(CareerPath.id).all()
    events = CareerEvent.query.order_by(CareerEvent.date).limit(6).all()
    jobs = Job.query.order_by(Job.control.desc()).limit(6).all()
    return render_template('careers_home.html', paths=paths, events=events,
                           jobs=jobs, **_ctx())


@app.route('/careers/career-paths')
def career_paths():
    paths = CareerPath.query.order_by(CareerPath.id).all()
    return render_template('career_paths.html', paths=paths, **_ctx())


@app.route('/careers/career-paths/<slug>')
def career_path(slug):
    path = CareerPath.query.filter_by(slug=slug).first_or_404()
    jobs = Job.query.filter(Job.careers_title.in_(
        json.loads(path.jobs_json or '[]'))).all() if path.jobs_json else []
    if not jobs:
        jobs = (Job.query.filter(Job.org == path.title).all())
    events = json.loads(path.events_json or '[]')
    return render_template('career_path.html', path=path, jobs=jobs,
                           events=events, **_ctx())


@app.route('/careers/events')
def careers_events():
    q = request.args.get('q', '').strip().lower()
    query = CareerEvent.query
    if q:
        query = query.filter(db.or_(
            db.func.lower(CareerEvent.event).like(f'%{q}%'),
            db.func.lower(CareerEvent.date).like(f'%{q}%')))
    rows = query.order_by(CareerEvent.date).all()
    return render_template('career_events.html', rows=rows, q=q, **_ctx())


@app.route('/careers/search')
def careers_search():
    q = request.args.get('q', '').strip()
    org = request.args.get('org', '')
    category = request.args.get('category', '')
    query = Job.query
    if q:
        ql = q.lower()
        # Expand the CBP acronym the way the upstream careers search does,
        # so e.g. "CBP Officer" also matches postings titled "Customs and
        # Border Protection Officer".
        expanded = ql.replace('cbp', 'customs and border protection')
        clauses = []
        for term in dict.fromkeys([ql, expanded]):
            clauses.append(db.func.lower(Job.title).like(f'%{term}%'))
            clauses.append(db.func.lower(Job.org).like(f'%{term}%'))
            clauses.append(db.func.lower(Job.location).like(f'%{term}%'))
        query = query.filter(db.or_(*clauses))
    if org:
        query = query.filter_by(org=org)
    if category:
        query = query.filter_by(category=category)
    rows = query.order_by(Job.control.desc()).limit(60).all()
    orgs = sorted({j.org for j in Job.query.all() if j.org})
    categories = sorted({j.category for j in Job.query.all() if j.category})
    return render_template('careers_search.html', rows=rows, q=q, org=org,
                           category=category, orgs=orgs, categories=categories,
                           **_ctx())


@app.route('/careers/job/<control>')
def job_detail(control):
    job = Job.query.filter_by(control=control).first_or_404()
    similar = (Job.query.filter(Job.org == job.org,
                                Job.control != control).limit(4).all()) \
        if job.org else []
    return render_template('job_detail.html', job=job, similar=similar,
                           **_ctx())


@app.route('/careers/job/<control>/save', methods=['POST'])
def job_save(control):
    job = Job.query.filter_by(control=control).first_or_404()
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=url_for('job_detail',
                                                     control=control)))
    existing = SavedJob.query.filter_by(user_id=current_user.id,
                                        job_id=job.id).first()
    if not existing:
        db.session.add(SavedJob(user_id=current_user.id, job_id=job.id,
                                created_at=MIRROR_TODAY.isoformat()))
        db.session.commit()
    return redirect(url_for('job_detail', control=control))


# ------------------------------------------------------------------ account --

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            nxt = request.args.get('next') or url_for('account')
            return redirect(nxt)
        flash('Invalid email or password.')
    return render_template('login.html', **_ctx())


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/account')
@login_required
def account():
    esta_apps = EstaApplication.query.filter_by(user_id=current_user.id) \
        .order_by(EstaApplication.created_at.desc()).all()
    ttp_apps = TtpApplication.query.filter_by(user_id=current_user.id) \
        .order_by(TtpApplication.created_at.desc()).all()
    saved = SavedCrossing.query.filter_by(user_id=current_user.id).all()
    saved_ports = SavedPort.query.filter_by(user_id=current_user.id).all()
    saved_jobs = SavedJob.query.filter_by(user_id=current_user.id).all()
    saved_forms = SavedForm.query.filter_by(user_id=current_user.id).all()
    max_delays = {s.id: _max_delay(s.crossing) for s in saved}
    return render_template('account.html', esta_apps=esta_apps,
                           ttp_apps=ttp_apps, saved=saved,
                           saved_ports=saved_ports, saved_jobs=saved_jobs,
                           saved_forms=saved_forms, max_delays=max_delays,
                           **_ctx())


@app.route('/account/saved/crossing/<int:crossing_id>', methods=['POST'])
@login_required
def save_crossing(crossing_id):
    crossing = Crossing.query.get_or_404(crossing_id)
    existing = SavedCrossing.query.filter_by(
        user_id=current_user.id, crossing_id=crossing.id).first()
    if not existing:
        db.session.add(SavedCrossing(
            user_id=current_user.id, crossing_id=crossing.id,
            created_at=MIRROR_TODAY.isoformat()))
        db.session.commit()
    return redirect(request.referrer or url_for('bwt'))


@app.route('/account/saved/port/<int:port_id>', methods=['POST'])
@login_required
def save_port(port_id):
    port = Port.query.get_or_404(port_id)
    existing = SavedPort.query.filter_by(user_id=current_user.id,
                                         port_id=port.id).first()
    if not existing:
        db.session.add(SavedPort(user_id=current_user.id, port_id=port.id,
                                 created_at=MIRROR_TODAY.isoformat()))
        db.session.commit()
    return redirect(request.referrer or url_for('ports_landing'))


@app.route('/account/saved/form/<int:form_id>', methods=['POST'])
@login_required
def save_form(form_id):
    form = CbpForm.query.get_or_404(form_id)
    existing = SavedForm.query.filter_by(user_id=current_user.id,
                                         form_id=form.id).first()
    if not existing:
        db.session.add(SavedForm(user_id=current_user.id, form_id=form.id,
                                 created_at=MIRROR_TODAY.isoformat()))
        db.session.commit()
    return redirect(request.referrer or url_for('forms_catalog'))


# ------------------------------------------------------------------- search --

@app.route('/search')
def site_search():
    q = request.args.get('q', '').strip()
    results = []
    if q:
        ql = q.lower()
        pages = Page.query.filter(db.or_(
            db.func.lower(Page.title).like(f'%{ql}%'),
            db.func.lower(Page.body).like(f'%{ql}%'))).limit(10).all()
        releases = NewsRelease.query.filter(db.or_(
            db.func.lower(NewsRelease.title).like(f'%{ql}%'),
            db.func.lower(NewsRelease.body).like(f'%{ql}%'))) \
            .limit(10).all()
        forms = CbpForm.query.filter(db.or_(
            db.func.lower(CbpForm.form_number).like(f'%{ql}%'),
            db.func.lower(CbpForm.name).like(f'%{ql}%'))).limit(10).all()
        jobs = Job.query.filter(db.func.lower(Job.title)
                                .like(f'%{ql}%')).limit(10).all()
        ports = Port.query.filter(db.func.lower(Port.name)
                                  .like(f'%{ql}%')).limit(10).all()
        crossings = Crossing.query.filter(db.or_(
            db.func.lower(Crossing.port_name).like(f'%{ql}%'),
            db.func.lower(Crossing.crossing_name).like(f'%{ql}%'))) \
            .limit(10).all()
        results = ([('Pages', pages)] + [('News Releases', releases)] +
                   [('Forms', forms)] + [('Jobs', jobs)] +
                   [('Ports of Entry', ports)] + [('Border Crossings',
                                                   crossings)])
    return render_template('search.html', q=q, results=results, **_ctx())


# -------------------------------------------------------------------- main --

def main():
    with app.app_context():
        db.create_all()
        seed_pages()
        seed_crossings()
        seed_ports()
        seed_news()
        seed_forms()
        seed_jobs()
        seed_careers()
        seed_reference()
        seed_benchmark_users()


with app.app_context():
    db.create_all()
    seed_pages()
    seed_crossings()
    seed_ports()
    seed_news()
    seed_forms()
    seed_jobs()
    seed_careers()
    seed_reference()
    seed_benchmark_users()


if __name__ == '__main__':
    # Registry slot: u_s_customs is SITES index 122 -> port 40122
    # (scripts/check_site_registry.py enforces tasks.jsonl web == this port).
    port = int(os.environ.get('PORT', 40122))
    app.run(host='0.0.0.0', port=port, debug=False)
