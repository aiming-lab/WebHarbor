#!/usr/bin/env python3
"""uscis — a WebHarbor mirror of https://www.uscis.gov/

Flask + SQLite mirror of the U.S. Citizenship and Immigration Services site:
the forms catalog with real downloadable PDFs, the fee calculator (G-1055
fee rows), Case Status Online, the processing-times tool, the Find a Civil
Surgeon locator, the Naturalization Eligibility Tool wizard, the field-office
locator (the real 43,301-row field_office_by_zip dataset), the newsroom
(alerts + news releases), the glossary, USCIS content pages, and the myUSCIS
account surface (login, myProgress, online appointment requests, AR-11-style
change of address).

Content comes from the tracked source_data/*.json snapshots captured from the
upstream sites on 2026-09-28 (see provenance.json); the
SQLite seed is materialized deterministically at image build time
(PYTHONHASHSEED=0, frozen bcrypt benchmark users).
"""
import csv
import json
import os
import re
from datetime import date

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                          login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("USCIS_SECRET_KEY") or "webharbor-uscis-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'USCIS_DB_URI', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'uscis.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'account_login'
login_manager.login_message = 'Please log in to access your USCIS online account.'
csrf = CSRFProtect(app)

# The mirror is a frozen snapshot of the upstream sites taken 2026-09-28.
MIRROR_TODAY = date(2026, 9, 28)
SITE_NAME = "uscis"
# bcrypt hash of 'TestPass123!' — frozen so the seed DB is byte-reproducible.
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')

SOURCE = os.path.join(BASE_DIR, 'source_data')


def _load(name):
    with open(os.path.join(SOURCE, name), encoding='utf-8') as f:
        return json.load(f)


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
    created_at = db.Column(db.String(10), nullable=False)

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)


class Page(db.Model):
    """Upstream content page (topics hubs, form pages, guidance pages)."""
    __tablename__ = 'pages'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    path = db.Column(db.String(240), unique=True, nullable=False)
    title = db.Column(db.String(220), nullable=False)
    last_reviewed = db.Column(db.String(20))
    body = db.Column(db.Text, nullable=False)      # JSON {alerts, sections, tables, links}
    def data(self):
        return json.loads(self.body)


class FormEntry(db.Model):
    """One row of the upstream 'All Forms' catalog."""
    __tablename__ = 'forms'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(240), nullable=False)
    description = db.Column(db.Text, nullable=False)
    detail_path = db.Column(db.String(120), nullable=False)
    file_online = db.Column(db.Boolean, nullable=False, default=False)
    sort = db.Column(db.Integer, nullable=False, default=0)


class FormFee(db.Model):
    """Fee-calculator record (real G-1055 fee rows per form)."""
    __tablename__ = 'form_fees'
    id = db.Column(db.Integer, primary_key=True)
    nid = db.Column(db.String(20), unique=True, nullable=False)
    label = db.Column(db.String(240), nullable=False)
    rows = db.Column(db.Text, nullable=False)      # JSON [{category, fees[]}]
    def fee_rows(self):
        return json.loads(self.rows)
    def fee_columns(self):
        return max([len(r.get('fees', [])) for r in self.fee_rows()] or [1])


class FormPage(db.Model):
    """Form detail page (edition dates, where-to-file, PDF downloads)."""
    __tablename__ = 'form_pages'
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(220), nullable=False)
    last_reviewed = db.Column(db.String(20))
    edition = db.Column(db.String(30))
    body = db.Column(db.Text, nullable=False)      # JSON {sections, tables, pdfs}
    def data(self):
        return json.loads(self.body)


class NewsItem(db.Model):
    __tablename__ = 'news'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False)     # alert | release | all
    slug = db.Column(db.String(180), unique=True, nullable=False)
    title = db.Column(db.String(240), nullable=False)
    release_date = db.Column(db.String(40))
    teaser = db.Column(db.Text)
    body = db.Column(db.Text, nullable=False)      # JSON {alerts, sections, image}
    def data(self):
        return json.loads(self.body)


class GlossaryTerm(db.Model):
    __tablename__ = 'glossary'
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(160), nullable=False)
    definition = db.Column(db.Text, nullable=False)
    sort = db.Column(db.Integer, nullable=False, default=0)


class FieldOffice(db.Model):
    __tablename__ = 'field_offices'
    id = db.Column(db.Integer, primary_key=True)
    designation = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    street = db.Column(db.String(160))
    city = db.Column(db.String(80))
    state = db.Column(db.String(40))
    zip = db.Column(db.String(12))
    district_code = db.Column(db.String(10))
    district_name = db.Column(db.String(120))
    region = db.Column(db.String(20))
    service_center = db.Column(db.String(10))


class ZipOffice(db.Model):
    """The real 43,301-row ZIP -> field-office directory."""
    __tablename__ = 'zip_offices'
    id = db.Column(db.Integer, primary_key=True)
    zip = db.Column(db.String(10), unique=True, nullable=False, index=True)
    state = db.Column(db.String(40))
    county = db.Column(db.String(80))
    city = db.Column(db.String(80))
    office_designation = db.Column(db.String(10), nullable=False)


class SurgeonSearch(db.Model):
    """Frozen civil-surgeon locator result set, per upstream ZIP query."""
    __tablename__ = 'surgeon_searches'
    id = db.Column(db.Integer, primary_key=True)
    zip = db.Column(db.String(10), unique=True, nullable=False)
    label = db.Column(db.String(80))
    lat = db.Column(db.String(20))
    lng = db.Column(db.String(20))
    results = db.Column(db.Text, nullable=False)    # JSON list of surgeon rows
    def rows(self):
        return json.loads(self.results)


def _duration_days(bound):
    units = {'days': 1, 'weeks': 7, 'months': 30.4375, 'years': 365.25}
    return float(bound['value']) * units.get(bound.get('unit_en', 'Months').lower(), 1)


class ProcessingTime(db.Model):
    """Real archived processing-times API record (form x office)."""
    __tablename__ = 'processing_times'
    id = db.Column(db.Integer, primary_key=True)
    form_name = db.Column(db.String(20), nullable=False, index=True)
    form_info = db.Column(db.String(200))
    office_code = db.Column(db.String(10), nullable=False)
    office_name = db.Column(db.String(120))
    range_json = db.Column(db.Text, nullable=False)      # JSON
    subtypes_json = db.Column(db.Text, nullable=False)   # JSON
    publication_date = db.Column(db.String(40))
    service_request_date = db.Column(db.String(40))
    snapshot_date = db.Column(db.String(20))
    def range_display(self):
        rng = json.loads(self.range_json)
        if not rng:
            return ""
        rng = sorted(rng, key=_duration_days)
        parts = [f"{r.get('value')} {r.get('unit_en', 'Months')}" for r in rng]
        return parts[0] if len(parts) == 1 else f"{parts[0]} to {parts[1]}"

    def subtypes_list(self):
        out = []
        for st in json.loads(self.subtypes_json):
            rng = st.get("range", [])
            if not rng:
                display = ""
            else:
                rng = sorted(rng, key=_duration_days)
                parts = [f"{r.get('value')} {r.get('unit_en', 'Months')}" for r in rng]
                display = parts[0] if len(parts) == 1 else f"{parts[0]} to {parts[1]}"
            out.append({"form_type": st.get("form_type"), "range_display": display,
                        "publication_date": st.get("publication_date") or self.publication_date})
        return out


class WizardState(db.Model):
    """Naturalization Eligibility Tool node (question or outcome)."""
    __tablename__ = 'wizard_states'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(400), unique=True, nullable=False)
    question = db.Column(db.String(400))
    options_json = db.Column(db.Text, nullable=False)
    outcome = db.Column(db.Boolean, nullable=False, default=False)
    text = db.Column(db.Text)
    def options(self):
        return json.loads(self.options_json)


class WizardEdge(db.Model):
    __tablename__ = 'wizard_edges'
    id = db.Column(db.Integer, primary_key=True)
    from_key = db.Column(db.String(400), nullable=False)
    option = db.Column(db.String(400), nullable=False)
    to_key = db.Column(db.String(400), nullable=False)


class Case(db.Model):
    """A seeded case visible to Case Status Online and account myProgress."""
    __tablename__ = 'cases'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    receipt = db.Column(db.String(16), unique=True, nullable=False, index=True)
    form_number = db.Column(db.String(20), nullable=False)
    form_title = db.Column(db.String(200), nullable=False)
    case_type = db.Column(db.String(200))
    office_code = db.Column(db.String(10))
    office_name = db.Column(db.String(120))
    filed_date = db.Column(db.String(20))
    current_status = db.Column(db.String(200), nullable=False)
    status_date = db.Column(db.String(20))
    history_json = db.Column(db.Text, nullable=False)   # JSON [{date, status, note}]
    def history(self):
        return json.loads(self.history_json)


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.String(60), nullable=False)
    reason_detail = db.Column(db.Text)
    office_designation = db.Column(db.String(10), nullable=False)
    office_name = db.Column(db.String(120), nullable=False)
    appt_date = db.Column(db.String(20), nullable=False)
    appt_time = db.Column(db.String(20), nullable=False)
    confirmation = db.Column(db.String(16), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Scheduled')
    booking_zip = db.Column(db.String(5))


# ------------------------------------------------------------------ helpers --

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _page_or_404(path):
    page = Page.query.filter_by(path=path).first()
    if not page:
        return None
    data = page.data()
    return dict(page=page, data=data)


NAV = [
    ("Green Card", "/green-card"),
    ("Citizenship", "/citizenship"),
    ("Working in the U.S.", "/working-in-the-united-states"),
    ("Family", "/family"),
    ("Humanitarian", "/humanitarian"),
    ("All Forms", "/forms"),
    ("Tools", "/tools"),
    ("Newsroom", "/newsroom"),
    ("About Us", "/about-us"),
]

TOOL_LINKS = [
    ("Case Status Online", "/casestatus", "Check your case status"),
    ("Case Processing Times", "/processing-times", "Check case processing times"),
    ("Fee Calculator", "/feecalculator", "Calculate your filing fees"),
    ("Find a Civil Surgeon", "/tools/find-a-civil-surgeon", "Locate a designated civil surgeon"),
    ("Naturalization Eligibility Tool", "/citizenship-resource-center/learn-about-citizenship/naturalization-eligibility-tool-0", "Check if you can apply for naturalization"),
    ("Field Office Locator", "/about-us/find-a-uscis-office/field-offices", "Find your USCIS field office"),
    ("Glossary", "/tools/glossary", "Look up immigration terms"),
    ("Schedule an Appointment", "/appointment", "Request an appointment online"),
]

RECEIPT_RE = re.compile(r"^(SRC|LIN|WAC|EAC|MSC|YSC|IOE)[0-9]{10}$")

# Local surfaces a captured upstream link may point at without breaking: every
# content Page, every FormPage, and the app's own tool/account routes. Links to
# anything else keep their verbatim upstream href instead of a dead local path.
TOOL_ROUTE_PATHS = (
    '/', '/topics', '/casestatus', '/processing-times', '/forms',
    '/forms/filing-fees', '/feecalculator', '/tools/find-a-civil-surgeon',
    '/tools/glossary', '/about-us/find-a-uscis-office/field-offices',
    '/about-us/find-a-uscis-office/field-offices/search', '/newsroom',
    '/newsroom/alerts', '/newsroom/news-releases', '/newsroom/all-news',
    '/appointment', '/appointment/view', '/appointment/new',
    '/account/login', '/account/register', '/account', '/account/address',
)


def _mirrored_paths():
    """Set of local paths the mirror actually serves (pages, form pages, and
    app routes). Cached for the process lifetime; the tables are read-only at
    request time."""
    global _MIRRORED_CACHE
    if _MIRRORED_CACHE is None:
        paths = set(TOOL_ROUTE_PATHS)
        paths.update(p[0] for p in db.session.query(Page.path).all())
        paths.update(p[0] for p in db.session.query(FormPage.path).all())
        _MIRRORED_CACHE = paths
    return _MIRRORED_CACHE


_MIRRORED_CACHE = None


# -------------------------------------------------------------------- routes --

@app.route('/_health')
def health():
    # Health reflects the configured database (USCIS_DB_URI), never a
    # filesystem artifact: a pristine checkout must report ok as long as the
    # configured database is reachable and seeded.
    ok = False
    counts = {}
    try:
        counts = {
            'pages': Page.query.count(),
            'forms': FormEntry.query.count(),
            'fees': FormFee.query.count(),
            'news': NewsItem.query.count(),
            'glossary': GlossaryTerm.query.count(),
            'offices': FieldOffice.query.count(),
            'zips': ZipOffice.query.count(),
            'surgeons': SurgeonSearch.query.count(),
            'processing_times': ProcessingTime.query.count(),
            'wizard_states': WizardState.query.count(),
            'users': User.query.count(),
            'cases': Case.query.count(),
        }
        ok = all(v > 0 for v in counts.values())
    except Exception:
        ok = False
    return jsonify({'site': SITE_NAME, 'ok': bool(ok), **counts}), 200


@app.route('/')
def home():
    page = _page_or_404('/')
    data = page['data'] if page else {"sections": [], "alerts": [], "links": [], "tables": []}
    alerts = NewsItem.query.filter_by(kind='alert').order_by(NewsItem.id.desc()).limit(4).all()
    releases = NewsItem.query.filter_by(kind='release').order_by(NewsItem.id.desc()).limit(3).all()
    return render_template('home.html', data=data, alerts=alerts, releases=releases,
                           nav=NAV, tools=TOOL_LINKS)


@app.route('/topics')
def topics():
    page = _page_or_404('/topics')
    if not page:
        abort(404)
    return render_template('content_page.html', **page, nav=NAV, tools=TOOL_LINKS, mirrored=_mirrored_paths())


@app.route('/casestatus', methods=['GET', 'POST'])
def casestatus():
    error = None
    result = None
    if request.method == 'POST':
        receipt = (request.form.get('receipt') or '').strip().upper().replace('-', '')
        if not RECEIPT_RE.match(receipt):
            error = ("My Case Status does not recognize the receipt number entered. "
                     "Please check your receipt number and try again. If you need further "
                     "assistance, please call the National Customer Service Center at "
                     "1-800-375-5283.")
        else:
            case = Case.query.filter_by(receipt=receipt).first()
            if case is None:
                error = ("My Case Status does not recognize the receipt number entered. "
                         "Please check your receipt number and try again. If you need further "
                         "assistance, please call the National Customer Service Center at "
                         "1-800-375-5283.")
            else:
                result = case
    return render_template('casestatus.html', error=error, result=result, nav=NAV, tools=TOOL_LINKS)


@app.route('/processing-times')
def processing_times():
    form = request.args.get('form', '').upper().strip()
    office = request.args.get('office', '').upper().strip()
    forms = sorted({p.form_name for p in ProcessingTime.query.all()})
    offices = []
    record = None
    if form:
        rows = ProcessingTime.query.filter_by(form_name=form).all()
        offices = sorted({(r.office_code, r.office_name or r.office_code) for r in rows})
        if office:
            record = ProcessingTime.query.filter_by(form_name=form, office_code=office).first()
            if record is None:
                abort(404)
    return render_template('processing_times.html', forms=forms, sel_form=form,
                           offices=offices, sel_office=office, record=record,
                           nav=NAV, tools=TOOL_LINKS)


@app.route('/forms')
def forms_catalog():
    q = (request.args.get('q') or '').strip().lower()
    online_only = request.args.get('online') == '1'
    page_no = max(1, request.args.get('page', 1, type=int))
    per_page = 25
    query = FormEntry.query.order_by(FormEntry.sort)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(db.func.lower(FormEntry.number).like(like),
                                    db.func.lower(FormEntry.title).like(like),
                                    db.func.lower(FormEntry.description).like(like)))
    if online_only:
        query = query.filter_by(file_online=True)
    total = query.count()
    rows = query.offset((page_no - 1) * per_page).limit(per_page).all()
    pages = (total + per_page - 1) // per_page
    return render_template('forms.html', rows=rows, q=q, online_only=online_only,
                           page_no=page_no, pages=pages, total=total, nav=NAV,
                           tools=TOOL_LINKS, mirrored=_mirrored_paths())


@app.route('/forms/filing-fees')
def filing_fees():
    fees = FormFee.query.order_by(FormFee.label).all()
    return render_template('filing_fees.html', fees=fees, nav=NAV, tools=TOOL_LINKS)


@app.route('/feecalculator', methods=['GET', 'POST'])
def feecalculator():
    nid = (request.values.get('form') or '').strip()
    record = FormFee.query.filter_by(nid=nid).first() if nid else None
    fees = FormFee.query.order_by(FormFee.label).all()
    return render_template('feecalculator.html', fees=fees, record=record, nav=NAV,
                           tools=TOOL_LINKS, mirrored=_mirrored_paths())


@app.route('/tools/find-a-civil-surgeon')
def civil_surgeon():
    zip_q = (request.args.get('zip') or '').strip()
    language = request.args.get('language', '')
    gender = request.args.get('gender', '')
    page_no = max(1, request.args.get('page', 1, type=int))
    search = None
    rows = []
    if zip_q:
        search = SurgeonSearch.query.filter_by(zip=zip_q).first()
        if search is not None:
            rows = search.rows()
            if language or gender:
                matches = []
                for row in rows:
                    contacts = [c for c in row.get('contacts_list', [])
                                if (not language or language.lower() in (c.get('languages') or '').lower())
                                and (not gender or (c.get('gender') or '').lower() == gender.lower())]
                    if contacts:
                        matches.append(dict(row, contacts_list=contacts))
                rows = matches
    per_page = 10
    start = (page_no - 1) * per_page
    page_rows = rows[start:start + per_page]
    index = Page.query.filter_by(slug='appointment-settings').one().data()['surgeon_filters']
    return render_template('civil_surgeon.html', zip_q=zip_q, language=language,
                           gender=gender, search=search, rows=page_rows,
                           total=len(rows), page_no=page_no,
                           pages=(len(rows) + per_page - 1) // per_page,
                           languages=index.get('languages', []),
                           genders=index.get('genders', []),
                           doctor_count=index.get('doctor_count'),
                           nav=NAV, tools=TOOL_LINKS)


@app.route('/tools/glossary')
def glossary():
    q = (request.args.get('q') or '').strip()
    letter = (request.args.get('letter') or '').strip().upper()
    query = GlossaryTerm.query.order_by(GlossaryTerm.sort)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(db.func.lower(GlossaryTerm.term).like(like),
                                    db.func.lower(GlossaryTerm.definition).like(like)))
    elif letter:
        query = query.filter(db.func.lower(GlossaryTerm.term).like(f"{letter.lower()}%"))
    rows = query.all()
    terms = GlossaryTerm.query.order_by(GlossaryTerm.sort).all()
    letters = sorted({t.term[0].upper() for t in terms if t.term})
    return render_template('glossary.html', rows=rows, q=q, letter=letter,
                           letters=letters, nav=NAV, tools=TOOL_LINKS)


@app.route('/about-us/find-a-uscis-office/field-offices')
def field_offices():
    zip_q = (request.args.get('zip') or '').strip()
    office = None
    if zip_q:
        row = ZipOffice.query.filter_by(zip=zip_q).first()
        if row is not None:
            office = FieldOffice.query.filter_by(designation=row.office_designation).first()
        if row is None:
            office = None
    return render_template('field_offices.html', zip_q=zip_q, zip_row=None,
                           office=office, nav=NAV, tools=TOOL_LINKS)


@app.route('/about-us/find-a-uscis-office/field-offices/search')
def field_office_search():
    zip_q = (request.args.get('zip') or '').strip()
    row = ZipOffice.query.filter_by(zip=zip_q).first() if zip_q else None
    office = None
    if row is not None:
        office = FieldOffice.query.filter_by(designation=row.office_designation).first()
    return render_template('field_offices.html', zip_q=zip_q, zip_row=row,
                           office=office, nav=NAV, tools=TOOL_LINKS)


ELIGIBILITY_PATH = '/citizenship-resource-center/learn-about-citizenship/naturalization-eligibility-tool-0'


def _wizard_start_key():
    first = (WizardState.query.filter(WizardState.outcome == False)
             .order_by(WizardState.id).first())
    return first.key if first else None


@app.route(ELIGIBILITY_PATH, methods=['GET', 'POST'])
def eligibility_tool():
    answers = []
    if request.method == 'POST':
        if request.form.get('reset'):
            key = _wizard_start_key()
        else:
            try:
                answers = json.loads(request.form.get('answers') or '[]')
            except ValueError:
                answers = []
            if not isinstance(answers, list):
                answers = []
            choice = (request.form.get('option') or '').strip()
            key = request.form.get('state_key') or ''
            edge = WizardEdge.query.filter_by(from_key=key, option=choice).first()
            if edge is None:
                abort(404)
            answers = answers + [choice]
            key = edge.to_key
    else:
        key = _wizard_start_key()
    state = WizardState.query.filter_by(key=key).first_or_404()
    return render_template('eligibility_tool.html', state=state, answers=answers,
                           nav=NAV, tools=TOOL_LINKS)


@app.route('/newsroom')
def newsroom():
    page = _page_or_404('/newsroom')
    data = page['data'] if page else {"sections": [], "alerts": [], "links": [], "tables": []}
    alerts = NewsItem.query.filter_by(kind='alert').order_by(NewsItem.id.desc()).limit(6).all()
    releases = NewsItem.query.filter_by(kind='release').order_by(NewsItem.id.desc()).limit(6).all()
    return render_template('newsroom.html', data=data, alerts=alerts, releases=releases,
                           nav=NAV, tools=TOOL_LINKS)


@app.route('/newsroom/<kind>')
def news_list(kind):
    if kind not in ('alerts', 'news-releases', 'all-news'):
        abort(404)
    kinds = {'alerts': ['alert'], 'news-releases': ['release'],
             'all-news': ['alert', 'release']}[kind]
    page_no = max(1, request.args.get('page', 1, type=int))
    per_page = 15
    query = NewsItem.query.filter(NewsItem.kind.in_(kinds)).order_by(NewsItem.id.desc())
    total = query.count()
    rows = query.offset((page_no - 1) * per_page).limit(per_page).all()
    pages = (total + per_page - 1) // per_page
    page = _page_or_404('/newsroom/' + kind)
    data = page['data'] if page else {"sections": []}
    return render_template('news_list.html', kind=kind, rows=rows, data=data,
                           page_no=page_no, pages=pages, total=total, nav=NAV, tools=TOOL_LINKS)


@app.route('/newsroom/<kind>/<slug>')
def news_detail(kind, slug):
    if kind not in ('alerts', 'news-releases', 'all-news'):
        abort(404)
    item = NewsItem.query.filter_by(slug=slug).first_or_404()
    return render_template('news_detail.html', item=item, nav=NAV, tools=TOOL_LINKS)


# ------------------------------------------------------------- myUSCIS surface

@app.route('/appointment')
def appointment_landing():
    index = Page.query.filter_by(slug='appointment-settings').one().data()
    return render_template('appointment.html', content=index, nav=NAV, tools=TOOL_LINKS)


@app.route('/appointment/view', methods=['GET', 'POST'])
def appointment_view():
    appt = None
    error = None
    if request.method == 'POST':
        confirmation = (request.form.get('confirmation') or '').strip().upper()
        zip_q = (request.form.get('zip') or '').strip()
        appt = Appointment.query.filter_by(confirmation=confirmation).first()
        owner = db.session.get(User, appt.user_id) if appt else None
        if appt is None or owner is None or (appt.booking_zip or owner.zip) != zip_q:
            appt = None
            error = ("We could not find an appointment with that confirmation number and "
                     "ZIP code. Please check the information on your appointment notice and "
                     "try again.")
    return render_template('appointment_view.html', appt=appt, error=error,
                           nav=NAV, tools=TOOL_LINKS)


@app.route('/appointment/cancel', methods=['POST'])
@login_required
def appointment_cancel():
    appt = Appointment.query.filter_by(confirmation=request.form.get('confirmation') or '',
                                       user_id=current_user.id).first()
    if appt is None:
        abort(404)
    appt.status = 'Canceled'
    db.session.commit()
    flash('Your appointment has been canceled.', 'success')
    return redirect(url_for('account_dashboard'))


@app.route('/appointment/new', methods=['GET', 'POST'])
@login_required
def appointment_new():
    step = 1
    reason = request.values.get('reason', '')
    reason_detail = request.values.get('reason_detail', '')
    zip_q = request.values.get('zip', '')
    office = None
    slots = []
    if request.method == 'POST':
        action = request.form.get('action', '')
        reasons = Page.query.filter_by(slug='appointment-settings').one().data()['reasons']
        if reason not in reasons:
            abort(400)
        if action == 'pick_reason' and reason:
            step = 2
        elif action == 'find_office' and zip_q:
            row = ZipOffice.query.filter_by(zip=zip_q).first()
            if row is None:
                step = 2
            else:
                office = FieldOffice.query.filter_by(designation=row.office_designation).first()
                step = 3
        elif action == 'pick_slot':
            designation = request.form.get('office', '')
            slot_raw = request.form.get('slot', '')
            if '|' not in slot_raw:
                abort(400)
            appt_date, appt_time = slot_raw.split('|', 1)
            office = FieldOffice.query.filter_by(designation=designation).first()
            if office is None:
                abort(404)
            row = ZipOffice.query.filter_by(zip=zip_q).first()
            if row is None or row.office_designation != designation:
                abort(400)
            if not any(x['date'] == appt_date and x['time'] == appt_time for x in _slots_for(designation)):
                flash('That appointment time is no longer available. Please choose another.', 'error')
                return redirect(url_for('appointment_new'))
            date_digits = re.sub(r'\D', '', appt_date)          # 20261005
            time_digits = re.sub(r'\D', '', appt_time)            # 0900 from '09:00 AM'
            confirmation = f"USC{designation}{date_digits[2:8]}{time_digits}"
            if Appointment.query.filter_by(confirmation=confirmation).first():
                confirmation += f"-{current_user.id}-{Appointment.query.count()+1}"
            appt = Appointment(user_id=current_user.id, reason=reason,
                                reason_detail=reason_detail,
                                office_designation=office.designation,
                                office_name=office.name, booking_zip=zip_q, appt_date=appt_date,
                                appt_time=appt_time, confirmation=confirmation)
            db.session.add(appt)
            db.session.commit()
            return redirect(url_for('appointment_confirmed', confirmation=appt.confirmation))
    if office is not None:
        slots = _slots_for(office.designation)
    reasons = Page.query.filter_by(slug='appointment-settings').one().data()['reasons']
    return render_template('appointment_new.html', step=step, reason=reason,
                           reason_detail=reason_detail, zip_q=zip_q, office=office,
                           slots=slots, reasons=reasons, nav=NAV, tools=TOOL_LINKS)


SLOT_TIMES = ("09:00 AM", "09:45 AM", "10:30 AM", "11:15 AM", "01:00 PM",
              "01:45 PM", "02:30 PM", "03:15 PM")


def _slots_for(designation):
    """Deterministic frozen slot grid per office (two weeks of weekdays)."""
    import hashlib
    slots = []
    base = date(2026, 10, 5)
    for i in range(14):
        d = date.fromordinal(base.toordinal() + i)
        if d.weekday() >= 5:
            continue
        for t in SLOT_TIMES:
            seed = f"{designation}-{d.isoformat()}-{t}"
            h = int(hashlib.sha256(seed.encode()).hexdigest()[:6], 16)
            if h % 5 == 0:
                continue  # slot unavailable
            slots.append({"date": d.isoformat(), "time": t,
                          "day": d.strftime("%A, %B %d, %Y")})
    occupied = {(a.appt_date, a.appt_time) for a in Appointment.query.filter_by(office_designation=designation, status='Scheduled').all()}
    return [slot for slot in slots if (slot['date'], slot['time']) not in occupied]


@app.route('/appointment/confirmed')
@login_required
def appointment_confirmed():
    appt = Appointment.query.filter_by(
        confirmation=request.args.get('confirmation', ''),
        user_id=current_user.id).first_or_404()
    return render_template('appointment_confirmed.html', appt=appt, nav=NAV, tools=TOOL_LINKS)


@app.route('/account/login', methods=['GET', 'POST'])
def account_login():
    if current_user.is_authenticated:
        return redirect(url_for('account_dashboard'))
    error = None
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user is None or not user.check_password(password):
            error = "The email or password you entered is incorrect. Please try again."
        else:
            login_user(user)
            return redirect(request.args.get('next') or url_for('account_dashboard'))
    return render_template('login.html', error=error, nav=NAV, tools=TOOL_LINKS)


@app.route('/account/register', methods=['GET', 'POST'])
def account_register():
    error = None
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        display_name = (request.form.get('display_name') or '').strip()
        if not email or not password or not display_name:
            error = "All fields are required."
        elif len(password) < 8:
            error = "Your password must be at least 8 characters long."
        elif User.query.filter(db.func.lower(User.email) == email).first():
            error = "An online account with that email already exists."
        else:
            user = User(email=email, display_name=display_name,
                        password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
                        account_number=f"USC{100000 + User.query.count() + 1}",
                        created_at="2026-09-28")
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('account_dashboard'))
    return render_template('register.html', error=error, nav=NAV, tools=TOOL_LINKS)


@app.route('/account/logout')
@login_required
def account_logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/account')
@login_required
def account_dashboard():
    cases = Case.query.filter_by(user_id=current_user.id).order_by(Case.id).all()
    appts = Appointment.query.filter_by(user_id=current_user.id).order_by(Appointment.id).all()
    return render_template('account.html', cases=cases, appts=appts, nav=NAV, tools=TOOL_LINKS)


@app.route('/account/address', methods=['GET', 'POST'])
@login_required
def account_address():
    saved = False
    if request.method == 'POST':
        street = (request.form.get('street') or '').strip()
        city = (request.form.get('city') or '').strip()
        state = (request.form.get('state') or '').strip()
        zip_q = (request.form.get('zip') or '').strip()
        if street and city and state and zip_q:
            current_user.street = street
            current_user.city = city
            current_user.state = state
            current_user.zip = zip_q
            db.session.commit()
            saved = True
            flash('Your address has been updated. We have recorded your change of address.', 'success')
        else:
            flash('All address fields are required.', 'error')
    return render_template('address.html', saved=saved, nav=NAV, tools=TOOL_LINKS)


@app.route('/download/<path:filename>')
def download_form(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static', 'external_cache', 'forms'),
                                filename, as_attachment=True)


# ------------------------------------------------------------- generic pages

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html', nav=NAV, tools=TOOL_LINKS), 404


@app.route('/<path:page_path>')
def content_page(page_path):
    page_path = '/' + page_path
    if page_path == '/es':
        abort(404)
    page = _page_or_404(page_path)
    if not page:
        abort(404)
    if page_path == '/forms/filing-fees/poverty-guidelines':
        # The upstream snapshot includes an orphan hidden 200%-column table.
        # Display the three region-labelled 400%-column tables reachable in
        # the upstream accordion, keeping each table beside its region.
        data = page['data']
        tables = [table for table in data['tables'] if '400%' in ' '.join(table['headers'])]
        for section, table in zip(data['sections'], tables):
            table['caption'] = section['heading']
            table['rows'] = [row for row in table['rows'] if row != table['headers']]
        data['tables'] = tables
        data['sections'] = []
    template = 'content_page.html'
    if page_path.startswith('/i-') or page_path.startswith('/n-') or \
       page_path.startswith('/g-') or page_path.startswith('/ar-'):
        form_page = FormPage.query.filter_by(path=page_path).first()
        if form_page:
            return render_template('form_detail.html', page=page, data=page['data'],
                                   form_page=form_page, form_data=form_page.data(),
                                   nav=NAV, tools=TOOL_LINKS,
                                   mirrored=_mirrored_paths())
    if page_path == '/forms':
        return redirect(url_for('forms_catalog'))
    if page_path == '/tools/glossary':
        return redirect(url_for('glossary'))
    if page_path == '/tools/find-a-civil-surgeon':
        return redirect(url_for('civil_surgeon'))
    if page_path == ELIGIBILITY_PATH:
        return redirect(url_for('eligibility_tool'))
    if page_path == '/newsroom/alerts':
        return redirect(url_for('news_list', kind='alerts'))
    if page_path == '/newsroom/news-releases':
        return redirect(url_for('news_list', kind='news-releases'))
    if page_path == '/newsroom/all-news':
        return redirect(url_for('news_list', kind='all-news'))
    return render_template(template, **page, nav=NAV, tools=TOOL_LINKS,
                           mirrored=_mirrored_paths())


# ------------------------------------------------------------------ seeding --

def seed_pages():
    if Page.query.count() > 0:
        return
    db.session.add(Page(slug='appointment-settings', path='/appointment-settings', title='Appointment service configuration', body=json.dumps(dict(_load('appointment.json'), surgeon_filters={k: _load('surgeons.json').get(k, []) for k in ('languages', 'genders', 'doctor_count')}))))
    rows = _load('pages.json')
    for r in rows:
        db.session.add(Page(slug=r['slug'], path=r['path'], title=r['title'],
                            last_reviewed=r.get('last_reviewed', ''),
                            body=json.dumps({k: r.get(k, []) for k in
                                             ('alerts', 'sections', 'tables', 'links')})))


def seed_forms():
    if FormEntry.query.count() > 0:
        return
    rows = _load('forms_catalog.json')
    for i, r in enumerate(rows):
        db.session.add(FormEntry(number=r['number'], title=r['title'],
                                 description=r['description'],
                                 detail_path=r['detail_path'],
                                 file_online=r.get('file_online', False), sort=i))


def seed_form_fees():
    if FormFee.query.count() > 0:
        return
    rows = _load('form_fees.json')
    for r in rows:
        db.session.add(FormFee(nid=r['nid'], label=r['label'], rows=json.dumps(r['rows'])))


def seed_form_pages():
    if FormPage.query.count() > 0:
        return
    rows = _load('form_pages.json')
    for r in rows:
        db.session.add(FormPage(path=r['path'], title=r['title'],
                                last_reviewed=r.get('last_reviewed', ''),
                                edition=r.get('edition', ''),
                                body=json.dumps({k: r.get(k, []) for k in
                                                 ('sections', 'tables', 'pdfs', 'alerts')})))


def seed_news():
    if NewsItem.query.count() > 0:
        return
    rows = _load('news.json')
    for r in rows:
        db.session.add(NewsItem(kind=r['kind'], slug=r['slug'], title=r['title'],
                                release_date=r.get('date', ''), teaser=r.get('teaser', ''),
                                body=json.dumps({k: r.get(k, []) for k in
                                                 ('alerts', 'sections', 'image', 'links')})))


def seed_glossary():
    if GlossaryTerm.query.count() > 0:
        return
    rows = _load('glossary.json')
    for i, r in enumerate(rows):
        db.session.add(GlossaryTerm(term=r['term'], definition=r['definition'], sort=i))


def seed_field_offices():
    if FieldOffice.query.count() > 0:
        return
    data = _load('field_offices.json')
    for r in data['offices']:
        db.session.add(FieldOffice(designation=r['designation'], name=r['name'],
                                   street=r.get('street'), city=r.get('city'),
                                   state=r.get('state'), zip=r.get('zip'),
                                   district_code=r.get('district_code'),
                                   district_name=r.get('district_name'),
                                   region=r.get('region'),
                                   service_center=r.get('service_center')))


def seed_zip_offices():
    if ZipOffice.query.count() > 0:
        return
    path = os.path.join(SOURCE, 'field_office_by_zip.csv')
    with open(path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            if row['IsRetired'].upper() == 'TRUE':
                continue
            batch.append(ZipOffice(zip=row['ZipCode'], state=row['State'],
                                   county=row['County'], city=row['City'],
                                   office_designation=row['FieldOfficeDesignation']))
            if len(batch) >= 2000:
                db.session.add_all(batch)
                db.session.flush()
                batch = []
        if batch:
            db.session.add_all(batch)


def seed_surgeons():
    if SurgeonSearch.query.count() > 0:
        return
    data = _load('surgeons.json')
    for zip_q, rec in data['zips'].items():
        db.session.add(SurgeonSearch(zip=zip_q, label=rec.get('label'),
                                    lat=rec.get('lat'), lng=rec.get('lng'),
                                    results=json.dumps(rec.get('results', []))))


def seed_processing_times():
    if ProcessingTime.query.count() > 0:
        return
    data = _load('processing_times.json')
    for r in data['records']:
        db.session.add(ProcessingTime(form_name=r['form'], form_info=r.get('form_info'),
                                      office_code=r['office_code'],
                                      office_name=r.get('office_name'),
                                      range_json=json.dumps(r.get('range', [])),
                                      subtypes_json=json.dumps(r.get('subtypes', [])),
                                      publication_date=r.get('publication_date'),
                                      service_request_date=r.get('service_request_date'),
                                      snapshot_date=r.get('snapshot_date')))


def seed_wizard():
    if WizardState.query.count() > 0:
        return
    data = _load('eligibility_wizard.json')
    for s in data['states']:
        db.session.add(WizardState(key=s['key'], question=s.get('question', ''),
                                   options_json=json.dumps(s.get('options', [])),
                                   outcome=s.get('outcome', False), text=s.get('text', '')))
    for e in data['edges']:
        db.session.add(WizardEdge(from_key=e['from'], option=e['option'], to_key=e['to']))


def seed_benchmark_users():
    if User.query.count() > 0:
        return
    rows = _load('benchmark_users.json')['users']
    for r in rows:
        user = User(email=r['email'], display_name=r['display_name'],
                   password_hash=BENCHMARK_PASSWORD_HASH,
                   account_number=r['account_number'],
                   street=r['street'], city=r['city'], state=r['state'], zip=r['zip'],
                   created_at="2026-01-15")
        db.session.add(user)
        db.session.flush()
        for c in r.get('cases', []):
            db.session.add(Case(user_id=user.id, receipt=c['receipt'],
                                form_number=c['form_number'],
                                form_title=c['form_title'],
                                case_type=c.get('case_type'),
                                office_code=c.get('office_code'),
                                office_name=c.get('office_name'),
                                filed_date=c.get('filed_date'),
                                current_status=c['current_status'],
                                status_date=c.get('status_date'),
                                history_json=json.dumps(c.get('history', []))))
        for a in r.get('appointments', []):
            db.session.add(Appointment(user_id=user.id, reason=a['reason'],
                                       reason_detail=a.get('reason_detail', ''),
                                       office_designation=a['office_designation'],
                                       office_name=a['office_name'],
                                       appt_date=a['appt_date'], appt_time=a['appt_time'],
                                       confirmation=a['confirmation'],
                                       status=a.get('status', 'Scheduled')))


def main():
    with app.app_context():
        db.create_all()
        populated = (Page, FormEntry, FormFee, FormPage, NewsItem, GlossaryTerm,
                     FieldOffice, ZipOffice, SurgeonSearch, ProcessingTime,
                     WizardState, User)
        if all(model.query.count() > 0 for model in populated):
            return
        seed_pages()
        seed_forms()
        seed_form_fees()
        seed_form_pages()
        seed_news()
        seed_glossary()
        seed_field_offices()
        seed_zip_offices()
        seed_surgeons()
        seed_processing_times()
        seed_wizard()
        seed_benchmark_users()
        db.session.commit()


# The same fully gated initializer serves imports, seeding and reset.
main()


if __name__ == '__main__':
    main()
