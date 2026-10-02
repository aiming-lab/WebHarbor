#!/usr/bin/env python3
"""sec — a WebHarbor mirror of https://www.sec.gov/

Flask + SQLite mirror of the U.S. Securities and Exchange Commission's
public site: the homepage hero and quick links, EDGAR company search
(CIK lookup by name or ticker with per-company filing browsing and form
filters), the EDGAR full-text search results captured from the live
efts.sec.gov query API, litigation releases (100 captured rows with
their real detail pages and case PDFs), administrative proceedings,
trading suspensions, the newsroom (press releases, speeches &
statements, what's new), rulemaking activity, the forms index with the
real form PDFs, the investor resources hub, the live FAST Answers
captured from sec.gov/answers, and the tip / complaint / question
intake flows, seeded for four benchmark users with company watchlists.

Content comes from the tracked source_data/*.json snapshots captured
from www.sec.gov, data.sec.gov and efts.sec.gov on 2026-09-30 (see
provenance.json for the exact source of every record and the honest
declaration of the fixture blocks); the SQLite seed is materialized
deterministically at image build time (PYTHONHASHSEED=0).
"""
import json
import os
import re
import secrets
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("SEC_SECRET_KEY") or "webharbor-sec-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'SEC_DB_URI', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'sec.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to continue.'
csrf = CSRFProtect(app)

MIRROR_DATE = date(2026, 9, 30)
MIRROR_TS = '2026-09-30'
SITE_NAME = 'sec'
UPSTREAM = 'https://www.sec.gov/'
# bcrypt hash of 'TestPass123!' — frozen so the seed DB is byte-reproducible.
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')
SOURCE = os.path.join(BASE_DIR, 'source_data')


def _load(name):
    """Runtime page content is frozen in the seed, never read from source JSON."""
    content = db.session.get(PageContent, name)
    if content is None:
        raise RuntimeError(f'Missing seeded page content: {name}')
    return content.payload


# ------------------------------------------------------------- helpers --

_PDF_CACHE = None

_PDF_ROOTS = {
    'admin': 'static/external_cache/admin',
    'suspensions': 'static/external_cache/suspensions',
    'litigation': 'static/external_cache/litigation',
    'forms': 'static/external_cache/forms',
}


def _pdf_cache():
    """Set of upstream /files/... hrefs that the mirror actually serves
    from static/external_cache — captured upstream files. The upstream hrefs
    are collected from the tracked source_data records; a href is archived
    when its basename exists in the matching external_cache directory."""
    global _PDF_CACHE
    if _PDF_CACHE is None:
        _PDF_CACHE = set()
        local = {}
        for kind, root in _PDF_ROOTS.items():
            full = os.path.join(BASE_DIR, root)
            if os.path.isdir(full):
                local[kind] = {name for name in os.listdir(full)}
        hrefs = set()
        for name in ('litigation_releases.json', 'litigation_details.json',
                     'admin_proceedings.json', 'admin_details.json',
                     'trading_suspensions.json', 'forms_index.json'):
            try:
                data = _load(name)
            except (OSError, ValueError):
                continue
            stack = [data]
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    href = item.get('href') or item.get('pdf')
                    if isinstance(href, str) and href.startswith('/files/'):
                        hrefs.add(href)
                    stack.extend(item.values())
                elif isinstance(item, list):
                    stack.extend(item)
        for href in hrefs:
            name = href.rsplit('/', 1)[-1]
            for kind in ('admin', 'suspensions', 'litigation', 'forms'):
                if name in local.get(kind, set()):
                    _PDF_CACHE.add(href)
                    break
    return _PDF_CACHE


def archived(href):
    """True when the upstream /files/... href was captured and is served."""
    return href in _pdf_cache()


def file_url(href):
    """Map an upstream /files/... href to the mirror route."""
    if not href:
        return None
    return href if archived(href) else (UPSTREAM.rstrip('/') + href if
                                        href.startswith('/') else href)


def local_return(value, fallback='/'):
    value = (value or '').strip()
    parts = urlsplit(value)
    return value if value.startswith('/') and not value.startswith('//') \
        and not parts.netloc and not parts.scheme \
        and not any(c in value for c in ('\\', '\r', '\n')) else fallback


def integer(value, minimum=1, maximum=9999):
    try:
        result = int(value)
    except (ValueError, TypeError):
        abort(400, 'Enter a valid whole number.')
    if not minimum <= result <= maximum:
        abort(400, 'Value is outside the allowed range.')
    return result


def _slugify(text):
    text = re.sub(r"[^A-Za-z0-9]+", '-', (text or '')).strip('-').lower()
    return text[:80] or 'item'


app.jinja_env.filters['from_json'] = lambda value: json.loads(value or '[]')


@app.context_processor
def _template_globals():
    return {'archived_files': _pdf_cache()}


# ---------------------------------------------------------------- models --

class PageContent(db.Model):
    __tablename__ = 'page_content'
    name = db.Column(db.String(100), primary_key=True)
    payload = db.Column(db.JSON, nullable=False)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    joined = db.Column(db.String(10))


class WatchlistItem(db.Model):
    __tablename__ = 'watchlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False,
                        index=True)
    cik = db.Column(db.String(16), nullable=False)
    added_at = db.Column(db.String(10))


class Company(db.Model):
    __tablename__ = 'companies'
    cik = db.Column(db.String(16), primary_key=True)
    name = db.Column(db.Text, nullable=False)
    ticker = db.Column(db.String(16))
    tickers = db.Column(db.Text)          # pipe list
    exchanges = db.Column(db.Text)       # pipe list
    sic = db.Column(db.String(8))
    sic_description = db.Column(db.Text)
    state = db.Column(db.String(8))
    category = db.Column(db.Text)
    fiscal_year_end = db.Column(db.String(8))
    description = db.Column(db.Text)
    website = db.Column(db.String(255))
    ein = db.Column(db.String(32))

    def ticker_list(self):
        return [t for t in (self.tickers or '').split('|') if t]

    def exchange_list(self):
        return [t for t in (self.exchanges or '').split('|') if t]


class Filing(db.Model):
    __tablename__ = 'filings'
    id = db.Column(db.Integer, primary_key=True)
    cik = db.Column(db.String(16), db.ForeignKey('companies.cik'),
                    nullable=False, index=True)
    accession = db.Column(db.String(32), nullable=False)
    form = db.Column(db.String(24), nullable=False)
    filed = db.Column(db.String(10), nullable=False)
    report_date = db.Column(db.String(10))
    acceptance = db.Column(db.String(32))
    items = db.Column(db.String(64))
    primary_doc = db.Column(db.String(255))
    primary_desc = db.Column(db.String(128))
    file_num = db.Column(db.String(32))
    film_num = db.Column(db.String(32))
    size = db.Column(db.Integer)
    is_xbrl = db.Column(db.Boolean, default=False)
    doc_url = db.Column(db.String(255))

    __table_args__ = (db.UniqueConstraint('cik', 'accession', 'form',
                                          name='uq_filing'),)


class FtsDoc(db.Model):
    """One real hit captured from the live EDGAR full-text search API."""
    __tablename__ = 'fts_docs'
    id = db.Column(db.Integer, primary_key=True)
    query_term = db.Column(db.String(64), nullable=False, index=True)
    query_form = db.Column(db.String(16), nullable=False)
    hit_id = db.Column(db.String(160), nullable=False)
    score = db.Column(db.Float)
    cik = db.Column(db.String(16))
    display_name = db.Column(db.Text)
    form = db.Column(db.String(24))
    file_date = db.Column(db.String(10))
    period = db.Column(db.String(10))
    adsh = db.Column(db.String(32))
    biz_state = db.Column(db.String(8))
    sic = db.Column(db.String(8))
    file_num = db.Column(db.String(32))
    root_form = db.Column(db.String(24))
    total_value = db.Column(db.Integer)
    total_relation = db.Column(db.String(8))
    rank = db.Column(db.Integer)


class PressRelease(db.Model):
    __tablename__ = 'press_releases'
    slug = db.Column(db.String(160), primary_key=True)
    title = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(32))
    date_sort = db.Column(db.String(10), index=True)
    release_no = db.Column(db.String(24))
    body = db.Column(db.Text)            # paragraphs joined with \n\n
    related = db.Column(db.Text)         # JSON list


class LitRelease(db.Model):
    __tablename__ = 'lit_releases'
    slug = db.Column(db.String(32), primary_key=True)
    release_no = db.Column(db.String(24), nullable=False)
    date = db.Column(db.String(32), nullable=False)
    date_sort = db.Column(db.String(10), index=True)
    respondents = db.Column(db.Text, nullable=False)
    title = db.Column(db.Text)
    text = db.Column(db.Text)
    resources = db.Column(db.Text)       # JSON list of {href,label}
    last_reviewed = db.Column(db.String(64))
    year = db.Column(db.String(8))


class AdminProceeding(db.Model):
    __tablename__ = 'admin_proceedings'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32), nullable=False)
    date_sort = db.Column(db.String(10))
    respondents = db.Column(db.Text, nullable=False)
    release_no = db.Column(db.String(24))
    file_number = db.Column(db.String(24))
    slug = db.Column(db.String(32), index=True)
    title = db.Column(db.Text)
    text = db.Column(db.Text)
    resources = db.Column(db.Text)       # JSON list
    last_reviewed = db.Column(db.String(64))


class TradingSuspension(db.Model):
    __tablename__ = 'trading_suspensions'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32), nullable=False)
    date_sort = db.Column(db.String(10), index=True)
    company = db.Column(db.Text, nullable=False)
    release_no = db.Column(db.String(24))
    resources = db.Column(db.Text)       # JSON list


class Rulemaking(db.Model):
    __tablename__ = 'rulemakings'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32), nullable=False)
    date_sort = db.Column(db.String(10))
    file_no = db.Column(db.String(24))
    title = db.Column(db.Text, nullable=False)
    status_releases = db.Column(db.Text)
    status = db.Column(db.String(24), index=True)


class Speech(db.Model):
    __tablename__ = 'speeches'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), nullable=False)
    title = db.Column(db.Text, nullable=False)
    speaker = db.Column(db.Text)
    kind = db.Column(db.String(32))
    date = db.Column(db.String(32))
    date_sort = db.Column(db.String(10), index=True)
    datetime = db.Column(db.String(40))


class WhatsNew(db.Model):
    __tablename__ = 'whats_new'
    id = db.Column(db.Integer, primary_key=True)
    href = db.Column(db.String(255), nullable=False)
    title = db.Column(db.Text, nullable=False)
    kind = db.Column(db.String(48))
    date = db.Column(db.String(32))


class FormIndex(db.Model):
    __tablename__ = 'form_index'
    id = db.Column(db.Integer, primary_key=True)
    form = db.Column(db.String(24), index=True)
    title = db.Column(db.Text, nullable=False)
    pdf = db.Column(db.String(128), nullable=False)
    last_updated = db.Column(db.String(32))
    sec_number = db.Column(db.String(16))
    filed_by = db.Column(db.Text)        # pipe list
    statutes = db.Column(db.Text)        # pipe list


class FastAnswer(db.Model):
    __tablename__ = 'fast_answers'
    slug = db.Column(db.String(64), primary_key=True)
    title = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)
    modified = db.Column(db.String(24))
    origin = db.Column(db.String(16), nullable=False)   # captured | fixture


class InvestorAlert(db.Model):
    __tablename__ = 'investor_alerts'
    slug = db.Column(db.String(96), primary_key=True)
    kind = db.Column(db.String(16), nullable=False)   # alert | bulletin
    title = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(32))
    date_sort = db.Column(db.String(10), index=True)
    summary = db.Column(db.Text)
    body = db.Column(db.Text)             # paragraphs joined with \n\n
    origin = db.Column(db.String(16), nullable=False)  # captured | fixture


class Complaint(db.Model):
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(24), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128), nullable=False)
    your_role = db.Column(db.String(48), nullable=False)
    issue_type = db.Column(db.String(64), nullable=False)
    subject_firm = db.Column(db.String(160))
    subject_person = db.Column(db.String(160))
    subject_ticker = db.Column(db.String(32))
    address = db.Column(db.String(255))
    phone = db.Column(db.String(48))
    details = db.Column(db.Text)
    submitted_at = db.Column(db.String(10), nullable=False)


class Tip(db.Model):
    __tablename__ = 'tips'
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(24), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128), nullable=False)
    violation_type = db.Column(db.String(64), nullable=False)
    subject_firm = db.Column(db.String(160))
    subject_person = db.Column(db.String(160))
    subject_ticker = db.Column(db.String(32))
    market = db.Column(db.String(48))
    details = db.Column(db.Text)
    submitted_at = db.Column(db.String(10), nullable=False)


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(24), nullable=False, unique=True)
    name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128), nullable=False)
    topic = db.Column(db.String(64), nullable=False)
    question = db.Column(db.Text)
    submitted_at = db.Column(db.String(10), nullable=False)


class EmailSubscription(db.Model):
    __tablename__ = 'email_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), nullable=False, unique=True)
    name = db.Column(db.String(128))
    topics = db.Column(db.Text)          # pipe list
    submitted_at = db.Column(db.String(10), nullable=False)


# ---------------------------------------------------------------- health --

def _health():
    try:
        counts = {
            'companies': Company.query.count(),
            'filings': Filing.query.count(),
            'press_releases': PressRelease.query.count(),
            'lit_releases': LitRelease.query.count(),
            'admin_proceedings': AdminProceeding.query.count(),
            'trading_suspensions': TradingSuspension.query.count(),
            'fts_docs': FtsDoc.query.count(),
            'fast_answers': FastAnswer.query.count(),
            'investor_alerts': InvestorAlert.query.count(),
            'form_index': FormIndex.query.count(),
            'users': User.query.count(),
        }
        return {'ok': all(v > 0 for v in counts.values()),
                'site': SITE_NAME, 'counts': counts}
    except Exception as exc:  # pragma: no cover
        return {'ok': False, 'site': SITE_NAME, 'error': str(exc)}


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ------------------------------------------------------------- home page --

@app.route('/')
def home():
    home_data = _load('home.json')
    latest = PressRelease.query.order_by(PressRelease.slug.desc()).limit(3).all()
    return render_template('home.html', home=home_data, latest=latest)


# --------------------------------------------------------- EDGAR: search --

@app.route('/search-filings')
def search_filings():
    return render_template('search_filings.html')


@app.route('/search-filings/cik-lookup')
def cik_lookup():
    q = (request.args.get('company') or '').strip()
    rows = []
    if q:
        like = f"%{q}%"
        rows = (Company.query
                .filter(db.or_(Company.name.ilike(like),
                               Company.ticker.ilike(q),
                               Company.cik.ilike(f"%{q}%")))
                .order_by(Company.name.asc())
                .limit(40).all())
    return render_template('cik_lookup.html', q=q, rows=rows)


@app.route('/edgar/company/<cik>')
def company(cik):
    cik = cik.strip()
    company_row = db.session.get(Company, cik)
    if not company_row:
        abort(404)
    form = (request.args.get('type') or '').strip()
    dateb = (request.args.get('dateb') or '').strip()
    page = integer(request.args.get('page', 1), 1, 500)
    per_page = 25
    query = Filing.query.filter_by(cik=cik)
    if form:
        if form.endswith('*'):
            query = query.filter(Filing.form.ilike(form[:-1] + '%'))
        else:
            query = query.filter(Filing.form == form)
    if dateb:
        if not re.fullmatch(r'\d{8}', dateb):
            abort(400, 'Enter a valid date (YYYYMMDD).')
        query = query.filter(Filing.filed <= f"{dateb[:4]}-{dateb[4:6]}-{dateb[6:]}")
    total = query.count()
    filings = (query.order_by(Filing.filed.desc(), Filing.id.asc())
               .offset((page - 1) * per_page).limit(per_page).all())
    all_forms = sorted({f[0] for f in db.session.query(Filing.form)
                        .filter(Filing.cik == cik).distinct().all()
                        if f[0]})
    return render_template('company.html', company=company_row,
                           filings=filings, total=total, form=form,
                           dateb=dateb, page=page, per_page=per_page,
                           all_forms=sorted(set(all_forms)),
                           on_watchlist=(current_user.is_authenticated and
                                         WatchlistItem.query.filter_by(
                                             user_id=current_user.id,
                                             cik=cik).first() is not None))


@app.route('/edgar/filing/<cik>/<accession>')
def filing_detail(cik, accession):
    company_row = db.session.get(Company, cik.strip())
    if not company_row:
        abort(404)
    filing = Filing.query.filter_by(cik=cik.strip(),
                                     accession=accession).first_or_404()
    others = (Filing.query.filter_by(cik=cik.strip(), accession=accession)
              .order_by(Filing.form.asc()).all())
    return render_template('filing_detail.html', company=company_row,
                           filing=filing, variants=others)


@app.route('/edgar/filing/<cik>/<accession>/document')
def filing_document(cik, accession):
    company_row = db.session.get(Company, cik.strip())
    if not company_row:
        abort(404)
    filing = Filing.query.filter_by(cik=cik.strip(),
                                     accession=accession).first_or_404()
    return render_template('filing_document.html', company=company_row,
                           filing=filing)


@app.route('/edgar/full-text-search')
def full_text_search():
    q = (request.args.get('q') or '').strip()
    form = (request.args.get('forms') or '').strip()
    datea = (request.args.get('datea') or '').strip()
    dateb = (request.args.get('dateb') or '').strip()
    docs, total_value, total_relation = [], None, None
    if q:
        query = FtsDoc.query.filter(FtsDoc.query_term.ilike(q))
        if form:
            query = query.filter(FtsDoc.query_form == form)
        if datea:
            query = query.filter(FtsDoc.file_date >= datea)
        if dateb:
            query = query.filter(FtsDoc.file_date <= dateb)
        docs = query.order_by(FtsDoc.query_form.asc(),
                              FtsDoc.rank.asc()).limit(100).all()
        if docs:
            total_value = docs[0].total_value
            total_relation = docs[0].total_relation
        # legacy EDGAR also matches prefix queries
        if not docs:
            query = FtsDoc.query.filter(FtsDoc.query_term.ilike(q + '%'))
            if form:
                query = query.filter(FtsDoc.query_form == form)
            docs = query.order_by(FtsDoc.query_form.asc(),
                                  FtsDoc.rank.asc()).limit(100).all()
            if docs:
                total_value = docs[0].total_value
                total_relation = docs[0].total_relation
    queries = (FtsDoc.query.with_entities(FtsDoc.query_term)
               .distinct().order_by(FtsDoc.query_term.asc()).all())
    return render_template('fts.html', q=q, form=form, datea=datea,
                           dateb=dateb, docs=docs, total_value=total_value,
                           total_relation=total_relation,
                           queries=[r[0] for r in queries])


# ------------------------------------------------------ enforcement hub --

@app.route('/enforcement-litigation')
def enforcement():
    landings = [
        ('Litigation Releases', 'litigation-releases',
         'Civil actions the Commission brings in federal court.'),
        ('Administrative Proceedings', 'administrative-proceedings',
         'Orders the Commission issues in administrative proceedings.'),
        ('Trading Suspensions', 'trading-suspensions',
         'Suspensions of trading in a security, generally for up to ten days.'),
        ('Whistleblower Program', 'whistleblower-program',
         'The SEC pays monetary awards for high-quality original information.'),
    ]
    return render_template('enforcement.html', landings=landings)


def _year_of(date_text):
    m = re.search(r'(\d{4})', date_text or '')
    return m.group(1) if m else None


@app.route('/enforcement-litigation/litigation-releases')
def litigation_releases():
    q = (request.args.get('q') or '').strip()
    year = (request.args.get('year') or '').strip()
    page = integer(request.args.get('page', 1), 1, 500)
    per_page = 20
    query = LitRelease.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(LitRelease.respondents.ilike(like),
                                    LitRelease.release_no.ilike(like),
                                    LitRelease.title.ilike(like)))
    if year:
        query = query.filter(LitRelease.year == year)
    total = query.count()
    rows = (query.order_by(LitRelease.date_sort.desc(), LitRelease.slug.desc())
            .offset((page - 1) * per_page).limit(per_page).all())
    years = [r[0] for r in sorted(
        db.session.query(LitRelease.year).distinct(), reverse=True) if r[0]]
    return render_template('litigation_releases.html', rows=rows, q=q,
                           year=year, page=page, per_page=per_page,
                           total=total, years=years)


@app.route('/enforcement-litigation/litigation-releases/<slug>')
def litigation_release(slug):
    row = db.session.get(LitRelease, slug.lower())
    if not row:
        abort(404)
    return render_template('litigation_release.html', lr=row)


@app.route('/enforcement-litigation/administrative-proceedings')
def admin_proceedings():
    q = (request.args.get('q') or '').strip()
    page = integer(request.args.get('page', 1), 1, 500)
    per_page = 20
    query = AdminProceeding.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(AdminProceeding.respondents.ilike(like),
                                    AdminProceeding.release_no.ilike(like),
                                    AdminProceeding.file_number.ilike(like)))
    total = query.count()
    rows = (query.order_by(AdminProceeding.date_sort.desc(),
                           AdminProceeding.id.desc())
            .offset((page - 1) * per_page).limit(per_page).all())
    return render_template('admin_proceedings.html', rows=rows, q=q,
                           page=page, per_page=per_page, total=total)


@app.route('/enforcement-litigation/administrative-proceedings/<slug>')
def admin_proceeding(slug):
    row = AdminProceeding.query.filter_by(slug=slug.lower()).first()
    if not row:
        abort(404)
    return render_template('admin_proceeding.html', ap=row)


@app.route('/enforcement-litigation/trading-suspensions')
def trading_suspensions():
    q = (request.args.get('q') or '').strip()
    page = integer(request.args.get('page', 1), 1, 500)
    per_page = 20
    query = TradingSuspension.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(TradingSuspension.company.ilike(like),
                                    TradingSuspension.release_no.ilike(like)))
    total = query.count()
    rows = (query.order_by(TradingSuspension.date_sort.desc(),
                           TradingSuspension.id.desc())
            .offset((page - 1) * per_page).limit(per_page).all())
    return render_template('trading_suspensions.html', rows=rows, q=q,
                           page=page, per_page=per_page, total=total)


@app.route('/enforcement-litigation/whistleblower-program')
def whistleblower():
    pages = _load('site_pages.json')
    return render_template('whistleblower.html', pages=pages)


# --------------------------------------------------------------- newsroom --

@app.route('/newsroom')
def newsroom():
    latest = PressRelease.query.order_by(PressRelease.date_sort.desc(),
                                         PressRelease.slug.desc()).limit(3).all()
    speeches = Speech.query.order_by(Speech.id.asc()).limit(3).all()
    whatsnew = WhatsNew.query.order_by(WhatsNew.id.asc()).limit(6).all()
    return render_template('newsroom.html', latest=latest, speeches=speeches,
                           whatsnew=whatsnew)


@app.route('/newsroom/press-releases')
def press_releases():
    q = (request.args.get('q') or '').strip()
    page = integer(request.args.get('page', 1), 1, 500)
    per_page = 10
    query = PressRelease.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(PressRelease.title.ilike(like),
                                    PressRelease.release_no.ilike(like)))
    total = query.count()
    rows = (query.order_by(PressRelease.date_sort.desc(), PressRelease.slug.desc())
            .offset((page - 1) * per_page).limit(per_page).all())
    return render_template('press_releases.html', rows=rows, q=q, page=page,
                           per_page=per_page, total=total)


@app.route('/newsroom/press-releases/<slug>')
def press_release(slug):
    row = db.session.get(PressRelease, slug)
    if not row:
        abort(404)
    related = []
    for item in json.loads(row.related or '[]'):
        other = db.session.get(PressRelease,
                               item['href'].rsplit('/', 1)[-1])
        if other:
            related.append(other)
    return render_template('press_release.html', pr=row, related=related)


@app.route('/newsroom/speeches-statements')
def speeches():
    q = (request.args.get('q') or '').strip()
    query = Speech.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Speech.title.ilike(like),
                                    Speech.speaker.ilike(like)))
    rows = query.order_by(Speech.id.asc()).all()
    return render_template('speeches.html', rows=rows, q=q, total=len(rows))


@app.route('/newsroom/whats-new')
def whats_new():
    rows = WhatsNew.query.order_by(WhatsNew.id.asc()).limit(40).all()
    return render_template('whats_new.html', rows=rows, total=len(rows))


# ------------------------------------------------------------- rulemaking --

@app.route('/rules-regulations/rulemaking-activity')
def rulemaking():
    q = (request.args.get('q') or '').strip()
    status = (request.args.get('status') or '').strip()
    page = integer(request.args.get('page', 1), 1, 500)
    per_page = 10
    query = Rulemaking.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Rulemaking.title.ilike(like),
                                    Rulemaking.file_no.ilike(like),
                                    Rulemaking.status_releases.ilike(like)))
    if status:
        query = query.filter(Rulemaking.status == status)
    total = query.count()
    rows = (query.order_by(Rulemaking.id.asc())
            .offset((page - 1) * per_page).limit(per_page).all())
    statuses = [r[0] for r in
                db.session.query(Rulemaking.status).distinct().order_by(
                    Rulemaking.status.asc()) if r[0]]
    return render_template('rulemaking.html', rows=rows, q=q, status=status,
                           page=page, per_page=per_page, total=total,
                           statuses=statuses)


# ------------------------------------------------------------ forms index --

@app.route('/submit-filings/forms-index')
def forms_index():
    q = (request.args.get('q') or '').strip()
    filed_by = (request.args.get('filed_by') or '').strip()
    statute = (request.args.get('statute') or '').strip()
    query = FormIndex.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(FormIndex.form.ilike(like),
                                    FormIndex.title.ilike(like),
                                    FormIndex.sec_number.ilike(like)))
    if filed_by:
        query = query.filter(FormIndex.filed_by.ilike(f"%{filed_by}%"))
    if statute:
        query = query.filter(FormIndex.statutes.ilike(f"%{statute}%"))
    rows = query.order_by(FormIndex.form.asc(), FormIndex.id.asc()).all()
    facets = _load('forms_index.json')['facets']
    return render_template('forms_index.html', rows=rows, q=q,
                           filed_by=filed_by, statute=statute,
                           audiences=[f['label'] for f in
                                      facets['field_audience_target_id']],
                           statutes_facet=[f['label'] for f in
                                           facets['field_act_target_id']])


@app.route('/submit-filings/forms-index/<path:pdf>')
def form_pdf(pdf):
    path = f"static/external_cache/forms/{pdf}"
    full = os.path.normpath(os.path.join(BASE_DIR, path))
    if not full.startswith(os.path.join(BASE_DIR, 'static')) \
            or not os.path.isfile(full):
        abort(404)
    from flask import send_from_directory
    return send_from_directory(
        os.path.join(BASE_DIR, 'static', 'external_cache', 'forms'), pdf)


@app.route('/files/<path:pdf>')
def archived_file(pdf):
    """Serve the captured upstream /files/... documents (litigation PDFs,
    suspension releases, admin orders, form PDFs) at their upstream paths."""
    name = pdf.rsplit('/', 1)[-1]
    segments = [s for s in pdf.split('/') if s]
    if len(segments) >= 3 and segments[0] == 'litigation':
        kind = segments[1] if segments[1] in ('admin', 'suspensions') else 'litigation'
    elif len(segments) == 1 and ('/files/' + pdf) in _pdf_cache():
        kind = 'forms'
    else:
        kind = None
    if kind:
        directory = os.path.join(BASE_DIR, 'static', 'external_cache', kind)
        if os.path.isfile(os.path.join(directory, name)):
            from flask import send_from_directory
            return send_from_directory(directory, name)
    abort(404)


# -------------------------------------------------- investor resources --

@app.route('/resources-investors')
def resources_investors():
    pages = _load('site_pages.json')
    return render_template('resources_investors.html', pages=pages)


@app.route('/resources-investors/investor-alerts-bulletins')
def investor_alerts():
    kind = (request.args.get('kind') or '').strip()
    q = (request.args.get('q') or '').strip()
    query = InvestorAlert.query
    if kind in ('alert', 'bulletin'):
        query = query.filter(InvestorAlert.kind == kind)
    if q:
        like = f"%{q}%"
        query = query.filter(InvestorAlert.title.ilike(like))
    rows = query.order_by(InvestorAlert.date_sort.desc(),
                           InvestorAlert.slug.asc()).all()
    return render_template('investor_alerts.html', rows=rows, kind=kind,
                           q=q, total=len(rows))


@app.route('/resources-investors/investor-alerts-bulletins/<slug>')
def investor_alert(slug):
    row = db.session.get(InvestorAlert, slug)
    if not row:
        abort(404)
    return render_template('investor_alert.html', alert=row)


@app.route('/fast-answers')
def fast_answers():
    q = (request.args.get('q') or '').strip()
    query = FastAnswer.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(FastAnswer.title.ilike(like),
                                    FastAnswer.body.ilike(like)))
    rows = query.order_by(FastAnswer.title.asc()).all()
    return render_template('fast_answers.html', rows=rows, q=q,
                           total=len(rows))


@app.route('/fast-answers/<slug>')
def fast_answer(slug):
    row = db.session.get(FastAnswer, slug)
    if not row:
        abort(404)
    return render_template('fast_answer.html', answer=row)


# ------------------------------------------------------- tips & complaints --

@app.route('/submit-tip-or-complaint')
def submit_tip():
    pages = _load('site_pages.json')
    return render_template('submit_tip.html', pages=pages)


@app.route('/submit-tip-or-complaint/tcr-disclaimer')
def tcr_disclaimer():
    return render_template('tcr_disclaimer.html')


@app.route('/submit-tip-or-complaint/report-possible-securities-law-violations',
           methods=['GET', 'POST'])
def tip_form():
    if request.method == 'GET':
        return render_template('tip_form.html', form={})
    data = request.form
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    violation = (data.get('violation_type') or '').strip()
    details = (data.get('details') or '').strip()
    errors = []
    if not name:
        errors.append('Enter your full name.')
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors.append('Enter a valid email address.')
    if not violation:
        errors.append('Select the type of possible violation.')
    if len(details) < 30:
        errors.append('Describe the suspected violation in at least 30 '
                      'characters so staff can evaluate your tip.')
    if errors:
        return render_template('tip_form.html', form=data, errors=errors), 400
    reference = 'TCR-' + secrets.token_hex(4).upper()
    row = Tip(reference=reference,
              user_id=current_user.id if current_user.is_authenticated else None,
              name=name, email=email, violation_type=violation,
              subject_firm=(data.get('subject_firm') or '').strip() or None,
              subject_person=(data.get('subject_person') or '').strip() or None,
              subject_ticker=(data.get('subject_ticker') or '').strip() or None,
              market=(data.get('market') or '').strip() or None,
              details=details, submitted_at=MIRROR_TS)
    db.session.add(row)
    db.session.commit()
    return redirect(url_for('tip_confirmation', reference=reference))


@app.route('/submit-tip-or-complaint/confirmation/<reference>')
def tip_confirmation(reference):
    row = Tip.query.filter_by(reference=reference).first_or_404()
    return render_template('tip_confirmation.html', tip=row)


@app.route('/submit-tip-or-complaint/report-problem-investment-account-or-financial-professional',
           methods=['GET', 'POST'])
def complaint_form():
    if request.method == 'GET':
        return render_template('complaint_form.html', form={})
    data = request.form
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    role = (data.get('your_role') or '').strip()
    issue = (data.get('issue_type') or '').strip()
    errors = []
    if not name:
        errors.append('Enter your full name.')
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors.append('Enter a valid email address.')
    if not role:
        errors.append('Select who you are in this complaint.')
    if not issue:
        errors.append('Select the type of problem you are reporting.')
    subject_firm = (data.get('subject_firm') or '').strip()
    if not subject_firm:
        errors.append('Enter the name of the firm or individual involved.')
    if errors:
        return render_template('complaint_form.html', form=data,
                               errors=errors), 400
    reference = 'IC-' + secrets.token_hex(4).upper()
    row = Complaint(reference=reference,
                    user_id=current_user.id if current_user.is_authenticated
                    else None,
                    name=name, email=email, your_role=role, issue_type=issue,
                    subject_firm=subject_firm,
                    subject_person=(data.get('subject_person') or '').strip()
                    or None,
                    subject_ticker=(data.get('subject_ticker') or '').strip()
                    or None,
                    address=(data.get('address') or '').strip() or None,
                    phone=(data.get('phone') or '').strip() or None,
                    details=(data.get('details') or '').strip() or None,
                    submitted_at=MIRROR_TS)
    db.session.add(row)
    db.session.commit()
    return redirect(url_for('complaint_confirmation', reference=reference))


@app.route('/submit-tip-or-complaint/complaint-confirmation/<reference>')
def complaint_confirmation(reference):
    row = Complaint.query.filter_by(reference=reference).first_or_404()
    return render_template('complaint_confirmation.html', complaint=row)


@app.route('/submit-tip-or-complaint/report-problem-sec-or-self-regulatory-organization',
           methods=['GET', 'POST'])
def question_form():
    if request.method == 'GET':
        return render_template('question_form.html', form={})
    data = request.form
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    topic = (data.get('topic') or '').strip()
    question = (data.get('question') or '').strip()
    errors = []
    if not name:
        errors.append('Enter your full name.')
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors.append('Enter a valid email address.')
    if not topic:
        errors.append('Select the topic of your question.')
    if len(question) < 20:
        errors.append('Enter your question (at least 20 characters).')
    if errors:
        return render_template('question_form.html', form=data,
                               errors=errors), 400
    reference = 'Q-' + secrets.token_hex(4).upper()
    row = Question(reference=reference, name=name, email=email, topic=topic,
                   question=question, submitted_at=MIRROR_TS)
    db.session.add(row)
    db.session.commit()
    return redirect(url_for('question_confirmation', reference=reference))


@app.route('/submit-tip-or-complaint/question-confirmation/<reference>')
def question_confirmation(reference):
    row = Question.query.filter_by(reference=reference).first_or_404()
    return render_template('question_confirmation.html', question=row)


# ------------------------------------------------------------ email signup --

@app.route('/subscribe', methods=['POST'])
def subscribe():
    data = request.form
    email = (data.get('email') or '').strip()
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return render_template('subscribe_result.html', ok=False,
                               email=email), 400
    topics = [t for t in data.getlist('topics') if t]
    if EmailSubscription.query.filter_by(email=email).first():
        return render_template('subscribe_result.html', ok=True,
                               email=email, existing=True)
    row = EmailSubscription(email=email,
                            name=(data.get('name') or '').strip() or None,
                            topics='|'.join(topics), submitted_at=MIRROR_TS)
    db.session.add(row)
    db.session.commit()
    return render_template('subscribe_result.html', ok=True, email=email)


# ------------------------------------------------------------------ account --

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    data = request.form
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    password = (data.get('password') or '')
    if not name:
        return render_template('signup.html', error='Enter your full name.'), 400
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return render_template('signup.html',
                               error='Enter a valid email address.'), 400
    if len(password) < 8:
        return render_template('signup.html',
                               error='Password must be at least 8 '
                               'characters.'), 400
    if User.query.filter_by(email=email).first():
        return render_template('signup.html',
                               error='An account with that email already '
                               'exists.'), 400
    row = User(email=email, name=name,
               password_hash=bcrypt.generate_password_hash(password),
               joined=MIRROR_TS)
    db.session.add(row)
    db.session.commit()
    login_user(row)
    return redirect(url_for('account'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    data = request.form
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    row = User.query.filter_by(email=email).first()
    if not row or not bcrypt.check_password_hash(row.password_hash, password):
        return render_template('login.html',
                               error='Invalid email or password.'), 200
    login_user(row)
    target = local_return(data.get('next'), fallback=url_for('account'))
    return redirect(target)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/account')
@login_required
def account():
    watchlist = (WatchlistItem.query.filter_by(user_id=current_user.id)
                 .order_by(WatchlistItem.id.asc()).all())
    complaints = (Complaint.query.filter_by(user_id=current_user.id)
                  .order_by(Complaint.id.desc()).all())
    tips = (Tip.query.filter_by(user_id=current_user.id)
            .order_by(Tip.id.desc()).all())
    companies = {row.cik: db.session.get(Company, row.cik) for row in watchlist}
    return render_template('account.html', watchlist=watchlist,
                           companies=companies, complaints=complaints,
                           tips=tips)


@app.route('/account/watchlist/toggle', methods=['POST'])
@login_required
def watchlist_toggle():
    data = request.form
    cik = (data.get('cik') or '').strip()
    if not db.session.get(Company, cik):
        abort(400, 'Unknown company.')
    back = local_return(data.get('back'))
    existing = WatchlistItem.query.filter_by(user_id=current_user.id,
                                             cik=cik).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
    else:
        db.session.add(WatchlistItem(user_id=current_user.id, cik=cik,
                                     added_at=MIRROR_TS))
        db.session.commit()
    return redirect(back)


# ------------------------------------------------------------------- seeds --

def seed_database():
    if Company.query.count() > 0:
        return
    from seed_lib import seed_all
    seed_all(db)


def seed_benchmark_users():
    from seed_lib import seed_benchmark_users as _s
    _s(db)


def main():
    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()


with app.app_context():
    db.create_all()
    if os.environ.get('SEC_AUTO_SEED', '1') == '1':
        seed_database()
        seed_benchmark_users()
