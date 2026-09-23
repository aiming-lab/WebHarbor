#!/usr/bin/env python3
"""America's Health Rankings mirror — Flask application.

Offline mirror of https://www.americashealthrankings.org/. Runtime data comes
entirely from instance/americas_health_rankings.db (seeded at boot from
instance_seed/americas_health_rankings.db). All measure values, state
rankings, report sections and articles were harvested from the live site and
are served from SQLite; no JSON files are read at request time.

Determinism: the benchmark clock is pinned to BENCHMARK_TODAY. No real
clocks or random values are used in rendered pages.
"""
import os
import re
import json
from urllib.parse import quote
from datetime import datetime, date

from flask import (Flask, render_template, request, redirect, url_for,
                  flash, abort, jsonify, Response)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_bcrypt import Bcrypt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ahr-mirror-secret-key'
DB_PATH = os.environ.get('AHR_DB_PATH',
                         os.path.join(BASE_DIR, 'instance', 'americas_health_rankings.db'))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your account.'
login_manager.login_message_category = 'info'

# Frozen benchmark date (seeded content is pinned to the harvest snapshot).
BENCHMARK_TODAY = date(2026, 9, 21)

UPSTREAM = 'https://www.americashealthrankings.org'

STOPWORDS = {'a', 'an', 'the', 'of', 'to', 'in', 'on', 'for', 'and', 'or',
             'is', 'are', 'be', 'with', 'as', 'by', 'at', 'from', 'what',
             'how', 'your', 'you', 'it', 'its', 'that', 'this'}

# Map quintile colors (harvested from the live site legend).
QUINTILE_COLORS = ['#a4d7fc', '#50adf0', '#3c81c7', '#336fa1', '#174b7b']
NO_DATA_COLOR = '#d1d1d1'

EDITIONS = [
    {'id': 284, 'label': 'Annual Report', 'value': 'annual', 'year': '2025'},
    {'id': 283, 'label': 'Health of Women & Children', 'value': 'hwc', 'year': '2025'},
    {'id': 286, 'label': 'Senior Report', 'value': 'senior', 'year': '2026'},
]
EDITION_BY_VALUE = {e['value']: e for e in EDITIONS}

# Homepage "Data Spotlight By State" measure tabs (as on the live site).
SPOTLIGHT_SLUGS = ['teen_suicide', 'Obesity', 'birthweight', 'mental_distress']


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime(2026, 1, 10, 9, 0, 0))

    bookmarks = db.relationship('Bookmark', backref='user', lazy=True,
                                 cascade='all, delete-orphan')
    history = db.relationship('ReadingHistory', backref='user', lazy=True,
                              cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Bookmark(db.Model):
    __tablename__ = 'bookmarks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)      # measure|state|report|article
    item_slug = db.Column(db.String(180), nullable=False)
    title = db.Column(db.String(255), nullable=False, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime(2026, 1, 12, 10, 0, 0))

    __table_args__ = (db.Index('ix_bookmark_user_item', 'user_id', 'kind', 'item_slug'),)


class ReadingHistory(db.Model):
    __tablename__ = 'reading_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(255), nullable=False, default='')
    visited_at = db.Column(db.DateTime, default=lambda: datetime(2026, 1, 12, 10, 0, 0))


class NewsletterSignup(db.Model):
    __tablename__ = 'newsletter_signups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime(2026, 1, 12, 10, 0, 0))


class Inquiry(db.Model):
    __tablename__ = 'inquiries'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(60), default='')
    organization = db.Column(db.String(160), default='')
    comment = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime(2026, 1, 12, 10, 0, 0))


class StateGeo(db.Model):
    __tablename__ = 'states'
    code = db.Column(db.String(4), primary_key=True)     # ALL + 50 states + DC
    name = db.Column(db.String(60), nullable=False)
    dept_website = db.Column(db.String(120), default='')
    svg = db.Column(db.String(200), default='')          # state outline asset path
    map_path = db.Column(db.Text, default='')            # choropleth path data
    map_x = db.Column(db.Float, default=0.0)             # label anchor
    map_y = db.Column(db.Float, default=0.0)
    is_us = db.Column(db.Boolean, default=False)


class StateFact(db.Model):
    __tablename__ = 'state_facts'
    id = db.Column(db.Integer, primary_key=True)
    state_code = db.Column(db.String(4), db.ForeignKey('states.code'), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)     # strength|challenge|highlight
    content = db.Column(db.Text, nullable=False, default='')
    measure_slug = db.Column(db.String(180), default='')
    measure_name = db.Column(db.String(180), default='')
    comparison_positive = db.Column(db.Boolean)
    position = db.Column(db.Integer, default=0)


class MeasureCategory(db.Model):
    __tablename__ = 'measure_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    display_order = db.Column(db.Integer, default=0)


class Measure(db.Model):
    __tablename__ = 'measures'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    metric_type_id = db.Column(db.String(20), default='')
    display_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')        # definition sentence
    unit = db.Column(db.String(200), default='')
    display_format = db.Column(db.String(20), default='Numeric')
    precision = db.Column(db.Integer, default=1)
    is_summation = db.Column(db.Boolean, default=False)
    category_id = db.Column(db.Integer, db.ForeignKey('measure_categories.id'))
    population = db.Column(db.String(80), default='')
    source_name = db.Column(db.Text, default='')
    source_years = db.Column(db.String(80), default='')
    citation = db.Column(db.Text, default='')
    latest_year = db.Column(db.String(40), default='')   # displayYear of current values
    latest_edition_id = db.Column(db.Integer)
    display_order = db.Column(db.Integer, default=0)
    about_why = db.Column(db.Text, default='')
    about_who = db.Column(db.Text, default='')
    about_works = db.Column(db.Text, default='')
    about_goals = db.Column(db.Text, default='')
    about_references = db.Column(db.Text, default='')
    appears_in = db.Column(db.Text, default='')          # JSON list of edition labels

    category = db.relationship('MeasureCategory', backref='measures', lazy=True)

    def values_for(self, state_code):
        return (MeasureValue.query.filter_by(measure_id=self.id, state_code=state_code)
                .order_by(MeasureValue.date_order.asc()).all())

    def current_values(self):
        return (MeasureValue.query.filter_by(measure_id=self.id, display_year=self.latest_year)
                .all())


class MeasureValue(db.Model):
    __tablename__ = 'measure_values'
    id = db.Column(db.Integer, primary_key=True)
    measure_id = db.Column(db.Integer, db.ForeignKey('measures.id'), nullable=False, index=True)
    state_code = db.Column(db.String(4), nullable=False, index=True)
    display_year = db.Column(db.String(40), nullable=False)
    value = db.Column(db.Float)
    value_display = db.Column(db.String(40), default='')
    rank = db.Column(db.Integer)
    source_end_date = db.Column(db.String(40), default='')
    date_order = db.Column(db.Integer, default=0)

    measure = db.relationship('Measure', backref=db.backref(
        'values', lazy='dynamic'), lazy=True)

    __table_args__ = (db.Index('ix_mval_measure_year_state', 'measure_id',
                               'display_year', 'state_code'),)


class MeasureDisparity(db.Model):
    __tablename__ = 'measure_disparities'
    id = db.Column(db.Integer, primary_key=True)
    measure_id = db.Column(db.Integer, db.ForeignKey('measures.id'), nullable=False, index=True)
    slug = db.Column(db.String(180), default='')
    display_name = db.Column(db.String(200), default='')
    metric_type_id = db.Column(db.String(20), default='')
    category = db.Column(db.String(80), default='')
    display_order = db.Column(db.Integer, default=0)


class MeasureOption(db.Model):
    """Population dropdown options (Explore Population Data)."""
    __tablename__ = 'measure_options'
    id = db.Column(db.Integer, primary_key=True)
    measure_id = db.Column(db.Integer, db.ForeignKey('measures.id'), nullable=False, index=True)
    group_label = db.Column(db.String(80), default='')
    option_label = db.Column(db.String(120), default='')
    option_value = db.Column(db.String(180), default='')
    position = db.Column(db.Integer, default=0)


class MeasureLink(db.Model):
    """Additional Measures / Related Measures links on a measure page."""
    __tablename__ = 'measure_links'
    id = db.Column(db.Integer, primary_key=True)
    measure_id = db.Column(db.Integer, db.ForeignKey('measures.id'), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)      # additional|related
    target_slug = db.Column(db.String(180), default='')
    target_name = db.Column(db.String(200), default='')
    position = db.Column(db.Integer, default=0)


class Edition(db.Model):
    __tablename__ = 'editions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    report_type_id = db.Column(db.Integer, default=1)
    year = db.Column(db.Integer, default=2025)


class MeasureEdition(db.Model):
    __tablename__ = 'measure_editions'
    id = db.Column(db.Integer, primary_key=True)
    measure_id = db.Column(db.Integer, db.ForeignKey('measures.id'), nullable=False, index=True)
    edition_id = db.Column(db.Integer, nullable=False)
    end_date = db.Column(db.String(40), default='')


class EditionMeasureState(db.Model):
    """Per-state per-edition categorized measure rows (state summary tables)."""
    __tablename__ = 'edition_measure_states'
    id = db.Column(db.Integer, primary_key=True)
    edition_id = db.Column(db.Integer, nullable=False, index=True)
    state_code = db.Column(db.String(4), nullable=False, index=True)
    measure_slug = db.Column(db.String(180), nullable=False)
    measure_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(120), default='')
    value = db.Column(db.Float)
    value_display = db.Column(db.String(40), default='')
    rank = db.Column(db.Integer)
    score = db.Column(db.Float)
    is_core = db.Column(db.String(2), default='C')
    display_order = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(200), default='')
    description = db.Column(db.Text, default='')
    is_summation = db.Column(db.Boolean, default=False)
    impact_score = db.Column(db.Float)
    contribution = db.Column(db.Float)

    __table_args__ = (db.Index('ix_ems_ed_state', 'edition_id', 'state_code'),)


class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    excerpt = db.Column(db.Text, default='')
    published = db.Column(db.String(60), default='')     # human date label
    date = db.Column(db.String(40), default='')          # ISO date
    edition_id = db.Column(db.Integer)
    menu_order = db.Column(db.Integer, default=0)
    featured = db.Column(db.Boolean, default=False)
    explorable = db.Column(db.Boolean, default=False)
    parent_slug = db.Column(db.String(180))
    attachments = db.Column(db.Text, default='[]')       # JSON download list


class ReportSection(db.Model):
    __tablename__ = 'report_sections'
    id = db.Column(db.Integer, primary_key=True)
    report_slug = db.Column(db.String(180), nullable=False, index=True)
    slug = db.Column(db.String(180), nullable=False)     # section slug ("" for main)
    title = db.Column(db.String(255), nullable=False)
    subtitle = db.Column(db.String(255), default='')
    excerpt = db.Column(db.Text, default='')
    content_html = db.Column(db.Text, default='')
    parent_slug = db.Column(db.String(180))
    menu_order = db.Column(db.Integer, default=0)
    featured = db.Column(db.Boolean, default=False)
    attachments = db.Column(db.Text, default='[]')

    __table_args__ = (db.Index('ix_rsec_report_slug', 'report_slug', 'slug'),)


class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    author_name = db.Column(db.String(255), default='')
    published = db.Column(db.String(60), default='')
    date = db.Column(db.String(40), default='')
    excerpt = db.Column(db.Text, default='')
    body_html = db.Column(db.Text, default='')
    image_url = db.Column(db.String(300), default='')
    image_alt = db.Column(db.String(255), default='')
    position = db.Column(db.Integer, default=0)


class Topic(db.Model):
    __tablename__ = 'topics'
    id = db.Column(db.Integer, primary_key=True)
    tid = db.Column(db.Integer, unique=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    href = db.Column(db.String(200), default='')
    position = db.Column(db.Integer, default=0)


class FaqItem(db.Model):
    __tablename__ = 'faq_items'
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(255), nullable=False)
    answer_html = db.Column(db.Text, default='')
    position = db.Column(db.Integer, default=0)


class StaticPage(db.Model):
    __tablename__ = 'static_pages'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(255), default='')
    html = db.Column(db.Text, default='')


class HomeBlock(db.Model):
    """Homepage CMS layout blocks (harvested from the live homepage)."""
    __tablename__ = 'home_blocks'
    id = db.Column(db.Integer, primary_key=True)
    block_type = db.Column(db.String(60), nullable=False)
    position = db.Column(db.Integer, default=0)
    data = db.Column(db.Text, default='{}')             # JSON block data

    def parsed(self):
        return json.loads(self.data or '{}')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def scored_search(query, rows, fields):
    """Token-overlap scored search (never strict AND)."""
    tokens = [t.lower() for t in re.split(r'\W+', query)
              if t.lower() not in STOPWORDS and len(t) > 1]
    if not tokens:
        return rows, tokens
    scored = []
    for row in rows:
        text = ' '.join(str(getattr(row, f, '') or '') for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1].id if hasattr(pair[1], 'id') else 0))
    return [r for _, r in scored], tokens


def quantile_bins(values):
    """Split current-edition values into 5 value-sorted quintiles (live-site legend)."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return []
    n = len(vals)
    bins = []
    for q in range(5):
        lo = vals[int(q * n / 5)]
        hi = vals[max(int((q + 1) * n / 5) - 1, int(q * n / 5))]
        if q == 4:
            hi = vals[-1]
        bins.append((lo, hi))
    out = []
    for b in bins:
        if not out or b != out[-1]:
            out.append(b)
    return out


def rank_quintile_bins(values_with_rank):
    """Legend bins grouped by rank quintiles, matching the upstream legend.

    Upstream legend labels bins by the value ranges of rank-ordered quintile
    groups (e.g. 'first quintile: ranks 5.1 to 9.2').
    """
    ranked = sorted((r, v) for r, v in values_with_rank
                    if r is not None and v is not None)
    if not ranked:
        return quantile_bins([v for _, v in values_with_rank])
    import math
    n = len(ranked)
    bins = []
    for q in range(5):
        lo_i = math.ceil(q * n / 5)
        hi_i = math.ceil((q + 1) * n / 5)
        grp = ranked[lo_i:max(hi_i, lo_i + 1)]
        if not grp:
            continue
        bins.append((grp[0][1], grp[-1][1]))
    out = []
    for b in bins:
        if not out or b != out[-1]:
            out.append(b)
    return out


def fmt_val(value, precision=1):
    if value is None:
        return '•'
    if float(value).is_integer() and abs(value) < 1e15 and precision <= 0:
        return str(int(value))
    return f"{value:.{max(precision, 0)}f}"


def record_history(url, title):
    if current_user.is_authenticated:
        db.session.add(ReadingHistory(user_id=current_user.id, url=url, title=title))


def rewrite_asset_refs(html):
    """Point harvested assets URLs at local /static/ mirrors; keep others upstream."""
    if not html:
        return html
    def repl(m):
        url = m.group(0)
        from urllib.parse import unquote, urlsplit
        path = unquote(urlsplit(url).path).lstrip('/')
        ext = path.rsplit('.', 1)[-1].lower()
        root = 'external_cache' if ext in ('pdf', 'csv', 'ppt', 'xlsx', 'zip', 'mp4') else 'images'
        return f"/static/{root}/{path}"
    return re.sub(r'https://assets\.americashealthrankings\.org/[^"\s\\<>]+', repl, html)


INTERNAL_LINK_RE = re.compile(r'https?://(?:www\.)?americashealthrankings\.org((?:/[^"\'\s<>]*)?)')
UNKNOWN_NODE_RE = re.compile(r'<span>\s*unknown node\s*</span>', re.IGNORECASE)
UNDEFINED_ATTR_RE = re.compile(r'\s+value=undefined', re.IGNORECASE)
ROOT_IMAGE_RE = re.compile(r'((?:src|href|srcset)=")/images/([^"]+)"')
NEXT_IMAGE_RE = re.compile(r'/_next/image\?url=([^"&\s]+)(?:&(?:amp;)?[^"\s]*)?')


def _unwrap_next_image(m):
    from urllib.parse import unquote
    inner = unquote(m.group(1))
    if inner.startswith('https://assets.americashealthrankings.org/'):
        return inner
    return m.group(0)


def rewrite_content(html):
    """Localize harvested HTML: asset URLs -> /static mirrors, internal
    absolute links -> relative mirror routes. Harvesting artifacts that would
    leak as visible text or malformed markup ("unknown node" placeholders left
    where upstream rendered interactive widgets, and undefined <li> value
    attributes) are dropped. Root-relative upstream image refs and the Next.js
    image-loader URLs are rewritten to the harvested static mirror first."""
    if not html:
        return html
    html = UNKNOWN_NODE_RE.sub('', html)
    html = UNDEFINED_ATTR_RE.sub('', html)
    html = NEXT_IMAGE_RE.sub(_unwrap_next_image, html)
    html = ROOT_IMAGE_RE.sub(lambda m: f'{m.group(1)}/static/images/images/{m.group(2)}"', html)
    html = rewrite_asset_refs(html)
    return INTERNAL_LINK_RE.sub(lambda m: m.group(1) or '/', html)


@app.template_filter('asset_url')
def asset_url(url):
    """Map an upstream assets URL to the local mirror path when available."""
    if not url:
        return url
    from urllib.parse import unquote, urlsplit
    path = unquote(urlsplit(url).path).lstrip('/')
    if path and '.' in path.rsplit('/', 1)[-1]:
        ext = path.rsplit('.', 1)[-1].lower()
        root = 'external_cache' if ext in ('pdf', 'csv', 'ppt', 'xlsx', 'zip', 'mp4') else 'images'
        local = f'/static/{root}/{path}'
        if os.path.isfile(os.path.join(BASE_DIR, 'static', local[len('/static/'):])):
            return local
    return url


def attachment_downloads(attachments_json):
    """Normalize report attachment JSON into download rows with local/upstream URLs."""
    items = json.loads(attachments_json or '[]')
    out = []
    for a in items:
        att = a.get('attachment') or {}
        url = att.get('url') or ''
        if not url:
            continue
        local = asset_url(url)
        exists = local.startswith('/static/') and os.path.isfile(
            os.path.join(BASE_DIR, 'static', local[len('/static/'):]))
        from urllib.parse import quote
        out.append({
            'title': a.get('title') or att.get('title') or 'Download',
            'url': quote(local, safe='/') if exists else url,
            'external': not exists,
            'filename': att.get('filename') or url.rsplit('/', 1)[-1],
            'mimetype': att.get('mimeType') or '',
            'filesize': att.get('filesize') or 0,
        })
    return out


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.template_filter('regex_first_number')
def regex_first_number(text):
    """Extract the leading number/percent from a highlight sentence."""
    m = re.search(r'(-?\d+(?:\.\d+)?)\s*(%|percent)?', text or '')
    if not m:
        return ''
    return m.group(1)


@app.template_filter('state_svg_url')
def state_svg_url(url):
    """Localize the per-state outline SVG (/images/states/<code>.svg)."""
    if not url:
        return url
    code = url.rsplit('/', 1)[-1]
    local = f'/static/images/images/states/{code}'
    if os.path.isfile(os.path.join(BASE_DIR, 'static',
                                   local[len('/static/'):])):
        return local
    return url


@app.template_filter('map_points')
def map_points(values):
    """MeasureValue rows -> chart points [{year, value, label}]."""
    return [{'year': v.display_year, 'value': v.value,
             'label': v.value_display or (str(v.value) if v.value is not None else 'N/A')}
            for v in values]


CATEGORY_COLORS = {
    'Social & Economic Factors': '#1490ff',
    'Physical Environment': '#5e9ed6',
    'Clinical Care': '#38a33c',
    'Behaviors': '#d9a521',
    'Health Outcomes': '#003c71',
    'Outcomes': '#003c71',
    'Overall': '#ffdf00',
    'Demographics': '#8e8e8e',
}


@app.context_processor
def inject_category_color():
    def category_color(name):
        return CATEGORY_COLORS.get(name or '', '#999999')
    _state_names = {s.code: s.name for s in StateGeo.query.all()}
    def state_name(code):
        return _state_names.get(code, code)
    def item_url(bookmark):
        if bookmark.kind == 'measure':
            return url_for('measure_detail', slug=bookmark.item_slug)
        if bookmark.kind == 'state':
            return url_for('state_summary', code=bookmark.item_slug)
        if bookmark.kind == 'report':
            return url_for('report_page', slug=bookmark.item_slug)
        return url_for('article_detail', slug=bookmark.item_slug)
    return {'category_color': category_color, 'state_name': state_name,
            'item_url': item_url}


@app.context_processor
def inject_globals():
    return {
        'upstream': UPSTREAM,
        'editions': EDITIONS,
        'today': BENCHMARK_TODAY,
        'quintile_color': lambda i: QUINTILE_COLORS[max(0, min(int(i), 4))],
    }


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    blocks = {b.block_type: b.parsed() for b in
              HomeBlock.query.order_by(HomeBlock.position.asc())}
    hero = blocks.get('homepage-hero', {})
    publications = blocks.get('homepage-publication-grid', {})
    reliable = blocks.get('homepage-features', {})
    reports_block = blocks.get('homepage-report-grid', {})
    video = blocks.get('homepage-video-feature', {})
    experts = blocks.get('homepage-news-grid', {})

    spotlight = []
    for slug in SPOTLIGHT_SLUGS:
        m = Measure.query.filter_by(slug=slug).first()
        if not m:
            continue
        cur = m.current_values()
        bins = rank_quintile_bins([(v.rank, v.value) for v in cur])
        colors = {}
        for v in cur:
            if v.value is None:
                colors[v.state_code] = NO_DATA_COLOR
            else:
                idx = next((i for i, (lo, hi) in enumerate(bins)
                            if lo <= v.value <= hi), len(bins) - 1)
                colors[v.state_code] = QUINTILE_COLORS[min(idx, 4)]
        us = next((v for v in cur if v.state_code == 'ALL'), None)
        spotlight.append({'measure': m, 'colors': colors, 'bins': bins,
                          'us': us})
    states_all = StateGeo.query.order_by(StateGeo.code.asc()).all()
    return render_template('index.html', hero=hero, publications=publications,
                           reliable=reliable, reports_block=reports_block,
                           video=video, experts=experts, spotlight=spotlight,
                           states_all=states_all)


@app.route('/explore/states/<code>')
def state_summary(code):
    code = (code or 'ALL').upper()
    state = StateGeo.query.get(code)
    if state is None:
        abort(404)
    edition_value = request.args.get('rank') or request.args.get('edition') or 'annual'
    edition = EDITION_BY_VALUE.get(edition_value, EDITIONS[0])
    rows = (EditionMeasureState.query
            .filter_by(state_code=code, edition_id=edition['id'])
            .order_by(EditionMeasureState.display_order.asc()).all())
    if not rows and edition['id'] != EDITIONS[0]['id']:
        edition = EDITIONS[0]
        rows = (EditionMeasureState.query
                .filter_by(state_code=code, edition_id=edition['id'])
                .order_by(EditionMeasureState.display_order.asc()).all())
    overall = next((r for r in rows if r.category == 'Overall'), None)
    # top-level category score rows (display_order multiples of 10000) + children
    top_rows = [r for r in rows
                if r.is_summation and r.category not in ('Label', 'Demographics')
                and r.display_order and r.display_order % 10000 == 0]
    demo_rows = [r for r in rows if r.category == 'Demographics']
    children = {}
    for r in rows:
        base = (r.display_order or 0) // 10000 * 10000
        if base and base != (r.display_order or 0) and r.category != 'Demographics':
            children.setdefault(base, []).append(r)
    cat_rows = top_rows
    facts = (StateFact.query.filter_by(state_code=code)
             .order_by(StateFact.id.asc()).all())
    strengths = [f for f in facts if f.kind == 'strength']
    challenges = [f for f in facts if f.kind == 'challenge']
    highlights = [f for f in facts if f.kind == 'highlight']

    featured = []
    for hl in highlights:
        m = Measure.query.filter_by(slug=hl.measure_slug).first()
        if not m and hl.measure_name:
            # harvested key-findings carry the display name only
            m = Measure.query.filter_by(display_name=hl.measure_name).first()
        if not m:
            continue
        state_series = m.values_for(code)
        us_series = m.values_for('ALL')
        cur = m.current_values()
        vals = [v.value for v in cur if v.value is not None]
        bins = quantile_bins(vals)
        colors = {}
        for v in cur:
            if v.value is None:
                colors[v.state_code] = NO_DATA_COLOR
            else:
                idx = next((i for i, (lo, hi) in enumerate(bins) if lo <= v.value <= hi),
                           len(bins) - 1)
                colors[v.state_code] = QUINTILE_COLORS[min(idx, 4)]
        featured.append({'measure': m, 'hl': hl, 'state_series': state_series,
                         'us_series': us_series, 'colors': colors, 'bins': bins})
    # Top positive / negative impact lists from the annual overall score
    ranked_contrib = [r for r in rows
                      if r.contribution is not None and r.is_core == 'C'
                      and not r.is_summation]
    ranked_contrib.sort(key=lambda r: r.contribution, reverse=True)
    top_positive = [(i + 1, r) for i, r in enumerate(ranked_contrib[:5])]
    n_contrib = len(ranked_contrib)
    top_negative = [(n_contrib - 4 + i, r)
                    for i, r in enumerate(ranked_contrib[-5:])]
    reports = Report.query.filter(Report.parent_slug.is_(None),
                                  Report.featured.is_(True)).order_by(
        Report.menu_order.asc()).all()
    state_saved = False
    if current_user.is_authenticated:
        state_saved = Bookmark.query.filter_by(
            user_id=current_user.id, kind='state', item_slug=state.code).first() is not None
    title = f"Summary of {state.name}" if not state.is_us else 'Summary of United States'
    states_all = StateGeo.query.order_by(StateGeo.code.asc()).all()
    record_history(request.path, title)
    return render_template('state_summary.html', state=state, edition=edition,
                           rows=rows, overall=overall, cat_rows=cat_rows,
                           children=children, demo_rows=demo_rows,
                           strengths=strengths, challenges=challenges,
                           highlights=highlights, featured=featured,
                           top_positive=top_positive, top_negative=top_negative,
                           reports=reports, title=title, state_saved=state_saved,
                           states_all=states_all)


@app.route('/explore/measures')
def measures_directory():
    q = (request.args.get('q') or '').strip()
    category = (request.args.get('category') or '').strip()
    subcategory = (request.args.get('subcategory') or '').strip()
    cats = MeasureCategory.query.order_by(MeasureCategory.display_order.asc(),
                                          MeasureCategory.id.asc()).all()
    tree = []
    for c in cats:
        ms = Measure.query.filter_by(category_id=c.id).order_by(
            Measure.display_name.asc()).all()
        if q or category:
            if q:
                ms, _ = scored_search(q, ms, ['display_name', 'description'])
            if category and c.name != category:
                continue
            if not ms:
                continue
        tree.append({'category': c, 'measures': ms})
    expanded = bool(q or category or subcategory)
    return render_template('measures_directory.html', tree=tree, q=q,
                           category=category, subcategory=subcategory,
                           expanded=expanded,
                           total=Measure.query.count())


@app.route('/explore/measures/<slug>')
def measure_detail(slug):
    m = Measure.query.filter_by(slug=slug).first()
    if m is None:
        abort(404)
    cur = m.current_values()
    with_data = [v for v in cur if v.value is not None and v.state_code != 'ALL']
    ranked = sorted(with_data, key=lambda v: v.rank if v.rank is not None else 999)
    top_states = ranked[:5]
    bottom_states = ranked[-5:]
    bottom_states = [b for b in bottom_states if b.rank is not None]
    us_value = next((v for v in cur if v.state_code == 'ALL'), None)
    bins = rank_quintile_bins([(v.rank, v.value) for v in cur])
    colors = {}
    for v in cur:
        if v.value is None:
            colors[v.state_code] = NO_DATA_COLOR
        else:
            idx = next((i for i, (lo, hi) in enumerate(bins)
                        if lo <= v.value <= hi), len(bins) - 1)
            colors[v.state_code] = QUINTILE_COLORS[min(idx, 4)]
    us_series = m.values_for('ALL')
    options = (MeasureOption.query.filter_by(measure_id=m.id)
               .order_by(MeasureOption.position.asc()).all())
    groups = []
    for opt in options:
        if not groups or groups[-1]['label'] != opt.group_label:
            groups.append({'label': opt.group_label, 'options': []})
        groups[-1]['options'].append(opt)
    additional = MeasureLink.query.filter_by(measure_id=m.id, kind='additional').order_by(
        MeasureLink.position.asc()).all()
    related = MeasureLink.query.filter_by(measure_id=m.id, kind='related').order_by(
        MeasureLink.position.asc()).all()
    appears = json.loads(m.appears_in or '[]')
    bookmarked = False
    if current_user.is_authenticated:
        bookmarked = Bookmark.query.filter_by(user_id=current_user.id,
                                              kind='measure', item_slug=slug).first() is not None
    record_history(request.path, f"{m.display_name} in United States")
    flagship_reports = Report.query.filter(Report.parent_slug.is_(None),
                                           Report.featured.is_(True)).order_by(
        Report.menu_order.asc()).all()
    about = {
        'why': rewrite_content(m.about_why),
        'who': rewrite_content(m.about_who),
        'works': rewrite_content(m.about_works),
        'goals': rewrite_content(m.about_goals),
        'references': rewrite_content(m.about_references),
    }
    return render_template('measure_detail.html', m=m, ranked=ranked,
                           about=about,
                           top_states=top_states, bottom_states=bottom_states,
                           us_value=us_value, bins=bins, colors=colors,
                           us_series=us_series, groups=groups,
                           additional=additional, related=related,
                           appears=appears, bookmarked=bookmarked,
                           flagship_reports=flagship_reports,
                           states=StateGeo.query.order_by(StateGeo.code.asc()).all())


@app.route('/health-topics')
def health_topics():
    topics = Topic.query.order_by(Topic.position.asc()).all()
    return render_template('health_topics.html', topics=topics)


@app.route('/publications')
def publications_hub():
    page = StaticPage.query.filter_by(key='publications').first()
    reports = (Report.query.filter(Report.parent_slug.is_(None))
               .order_by(Report.menu_order.asc()).limit(6).all())
    articles = Article.query.order_by(Article.date.desc(), Article.id.asc()).limit(6).all()
    if page:
        page.html = rewrite_content(page.html)
    return render_template('publications.html', page=page, reports=reports,
                           articles=articles)


@app.route('/publications/reports')
def reports_archive():
    reports = (Report.query.filter(Report.parent_slug.is_(None),
                                   Report.edition_id.isnot(None))
               .order_by(Report.menu_order.asc()).all())
    non_edition = (Report.query.filter(Report.parent_slug.is_(None),
                                       Report.edition_id.is_(None))
                   .order_by(Report.menu_order.asc()).all())
    return render_template('reports_archive.html', reports=reports,
                           non_edition=non_edition)


def section_url_slug(report_slug, section):
    """Live-site URL segment for a section: children carry the parent prefix."""
    if not section.parent_slug or section.parent_slug == report_slug:
        return section.slug
    return f"{section.parent_slug}-{section.slug}"


@app.route('/publications/reports/<slug>')
@app.route('/publications/reports/<slug>/<path:section>')
def report_page(slug, section=None):
    report = Report.query.filter_by(slug=slug, parent_slug=None).first()
    if report is None:
        abort(404)
    sections = (ReportSection.query.filter_by(report_slug=slug)
                .order_by(ReportSection.menu_order.asc()).all())
    url_map = {section_url_slug(slug, s): s for s in sections}
    nav = build_report_nav(slug, sections, url_map)
    current = None
    if section:
        current = url_map.get(section)
        if current is None:
            abort(404)
        downloads = attachment_downloads(current.attachments)
        title = current.title
        content = rewrite_content(current.content_html)
    else:
        current = next((s for s in sections if s.slug == slug), None)
        downloads = attachment_downloads(report.attachments)
        title = report.title
        content = rewrite_content(current.content_html) if current else ''
    crumbs = None
    if section and current is not None:
        parent = next((s for s in sections if s.slug == current.parent_slug), None) \
            if current.parent_slug else None
        crumbs = [(report.title, url_for('report_page', slug=slug))]
        if parent:
            crumbs.append((parent.title, url_for('report_page', slug=slug,
                                                 section=section_url_slug(slug, parent))))
        crumbs.append((current.title, None))
    # State summary sections render the full state measure table from the DB
    state_table = None
    if section and current is not None and current.parent_slug == 'state-summaries':
        state_table = build_state_summary_table(report, current)

    record_history(request.path, title)
    return render_template('report_page.html', report=report, nav=nav,
                           current=current, downloads=downloads, title=title,
                           content=content, section=section, crumbs=crumbs,
                           state_table=state_table)


def build_state_summary_table(report, section):
    """Full per-state measure table for report state-summary sections."""
    edition_id = report.edition_id
    if not edition_id:
        return None
    state_name = section.slug
    state = StateGeo.query.filter(
        db.func.lower(StateGeo.name) == state_name.lower(),
        StateGeo.code != 'ALL').first()
    if state is None:
        return None
    rows = (EditionMeasureState.query
            .filter_by(state_code=state.code, edition_id=edition_id)
            .order_by(EditionMeasureState.display_order.asc()).all())
    if not rows:
        return None
    downloads = []
    code = state.code.lower()
    patterns = {
        284: [f'ahr_2025annualreport-statesummaries_final-web-{state_name}.pdf',
              f'ehi2025-{state_name}.pdf'],
        286: [f'ahr_2026seniorreport-statesummaries_final-web_{state_name}.pdf'],
        283: [f'AHR_2025HWCReport-StateSummaries_{state_name.title()}.pdf'],
    }
    for fname in patterns.get(edition_id, []):
        path = os.path.join(BASE_DIR, 'static', 'external_cache', fname)
        if os.path.isfile(path):
            downloads.append({'title': 'State Summary Download'
                              if 'ehi' not in fname
                              else 'Economic Hardship Index County-Level Map Download',
                              'url': f'/static/external_cache/{quote(fname)}'})
    return {'state': state, 'rows': rows, 'downloads': downloads}


def build_report_nav(slug, sections, url_map=None):
    """Build section nav tree (parent -> children) preserving menu order.

    Top-level sections are seeded with parent_slug = <report slug> (the
    landing section carries the same slug and is skipped), so the roots live
    under by_parent[report_slug], not under None.
    """
    url_map = url_map or {}
    by_parent = {}
    for s in sections:
        if s.slug == slug:
            continue
        by_parent.setdefault(s.parent_slug, []).append(s)
    def node_for(sec):
        return {'section': sec, 'url_slug': section_url_slug(slug, sec),
                'children': [node_for(c) for c in
                             sorted(by_parent.get(sec.slug, []),
                                    key=lambda x: x.menu_order)]}
    roots = sorted(by_parent.get(slug, []), key=lambda s: s.menu_order)
    return [node_for(r) for r in roots]


@app.route('/publications/articles')
def articles_list():
    articles = Article.query.order_by(Article.date.desc(), Article.id.asc()).all()
    return render_template('articles_list.html', articles=articles)


@app.route('/publications/articles/<slug>')
def article_detail(slug):
    a = Article.query.filter_by(slug=slug).first()
    if a is None:
        abort(404)
    bookmarked = False
    if current_user.is_authenticated:
        bookmarked = Bookmark.query.filter_by(user_id=current_user.id,
                                              kind='article', item_slug=slug).first() is not None
    record_history(request.path, a.title)
    return render_template('article_detail.html', a=a, bookmarked=bookmarked,
                           body=rewrite_content(a.body_html))


@app.route('/faq')
def faq():
    items = FaqItem.query.order_by(FaqItem.position.asc()).all()
    for item in items:
        item.answer_html = rewrite_content(item.answer_html)
    return render_template('faq.html', items=items)


@app.route('/about/methodology/data-sources-and-measures')
def methodology():
    page = StaticPage.query.filter_by(key='methodology').first()
    if page:
        page.html = rewrite_content(page.html)
    return render_template('static_page.html', page=page,
                           title=page.title if page else 'Data Sources')


@app.route('/about/page/submit-an-inquiry', methods=['GET', 'POST'])
def inquiry():
    if request.method == 'POST':
        name = (request.form.get('your name') or request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip()
        confirm = (request.form.get('confirm email') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        org = (request.form.get('your organization') or '').strip()
        comment = (request.form.get('your comment') or '').strip()
        error = None
        if not name or not email or not comment:
            error = 'Please fill in your name, email and comment.'
        elif '@' not in email or '.' not in email.split('@')[-1]:
            error = 'Please enter a valid email address.'
        elif confirm and confirm != email:
            error = 'The email addresses do not match.'
        if error:
            return render_template('inquiry.html', error=error, form=request.form), 400
        db.session.add(Inquiry(name=name, email=email, phone=phone,
                               organization=org, comment=comment))
        db.session.commit()
        flash('Thank you. Your inquiry has been submitted.', 'success')
        return redirect(url_for('inquiry'))
    return render_template('inquiry.html', error=None, form={})


@app.route('/search')
def search():
    q = (request.args.get('q') or '').strip()
    page = max(int(request.args.get('page', 1)), 1)
    measures, reports, articles, states = [], [], [], []
    if q:
        measures, _ = scored_search(q, Measure.query.all(),
                                     ['display_name', 'description'])
        reports, _ = scored_search(q, Report.query.filter(Report.parent_slug.is_(None)).all(),
                                   ['title', 'excerpt'])
        articles, _ = scored_search(q, Article.query.all(),
                                    ['title', 'excerpt', 'author_name'])
        states, _ = scored_search(q, StateGeo.query.all(), ['name'])
    per_page = 10
    combined = ([('measure', m, f"{m.display_name}") for m in measures] +
                [('report', r, r.title) for r in reports] +
                [('article', a, a.title) for a in articles] +
                [('state', s, f"Explore {s.name}") for s in states])
    total = len(combined)
    start = (page - 1) * per_page
    page_items = combined[start:start + per_page]
    return render_template('search.html', q=q, items=page_items, page=page,
                           total=total, per_page=per_page,
                           pages=(total + per_page - 1) // per_page)


# ---------------------------------------------------------------------------
# Legacy upstream URL shapes kept alive via redirects (harvested report and
# article content links to these paths on americashealthrankings.org).
# ---------------------------------------------------------------------------

@app.route('/explore/annual/measure/<slug>/state/<code>')
@app.route('/explore/<edition>/measure/<slug>/state/<code>')
def legacy_annual_measure(slug, code, edition=None):
    if Measure.query.filter_by(slug=slug).first():
        return redirect(url_for('measure_detail', slug=slug))
    return redirect(url_for('measures_directory'))


@app.route('/explore/measures/<slug>/<code>')
def legacy_measure_state(slug, code):
    if Measure.query.filter_by(slug=slug).first():
        return redirect(url_for('measure_detail', slug=slug))
    state = StateGeo.query.filter_by(code=code.upper()).first()
    if state:
        return redirect(url_for('state_summary', code=state.code))
    return redirect(url_for('measures_directory'))


@app.route('/explore/<slug>')
def explore_upstream_alias(slug):
    """Upstream serves some data briefs under /explore/<slug>; the mirror
    stores the same content as reports - alias the upstream URL form."""
    if Report.query.filter_by(slug=slug).first():
        return redirect(url_for('report_page', slug=slug))
    abort(404)


@app.route('/learn/reports/<slug>')
@app.route('/learn/reports/<slug>/<path:rest>')
def legacy_learn_report(slug, rest=None):
    if not Report.query.filter_by(slug=slug).first():
        return redirect(url_for('reports_archive'))
    if rest:
        target = f'/publications/reports/{slug}/{rest}'
        section = ReportSection.query.filter_by(report_slug=slug,
                                                slug=rest.rsplit('/', 1)[-1]).first()
        if section:
            return redirect(target)
        return redirect(url_for('report_page', slug=slug))
    return redirect(url_for('report_page', slug=slug))


@app.route('/about/methodology/<page>')
def legacy_methodology(page):
    return redirect(url_for('methodology'))


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm') or ''
        if not name or not email or not password:
            return render_template('register.html',
                                   error='All fields are required.'), 400
        if '@' not in email or '.' not in email.split('@')[-1]:
            return render_template('register.html',
                                   error='Please enter a valid email address.'), 400
        if len(password) < 8:
            return render_template('register.html',
                                   error='Password must be at least 8 characters.'), 400
        if password != confirm:
            return render_template('register.html',
                                   error='Passwords do not match.'), 400
        if User.query.filter_by(email=email).first():
            return render_template('register.html',
                                   error='An account with this email already exists.'), 400
        user = User(email=email, name=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Welcome! Your account has been created.', 'success')
        return redirect(url_for('account'))
    return render_template('register.html', error=None)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            return render_template('login.html',
                                   error='Invalid email or password.'), 401
        login_user(user)
        flash('You have been logged in.', 'success')
        next_url = request.args.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('account'))
    return render_template('login.html', error=None)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/account')
@login_required
def account():
    bookmarks = Bookmark.query.filter_by(user_id=current_user.id).order_by(
        Bookmark.created_at.desc(), Bookmark.id.desc()).all()
    return render_template('account.html', bookmarks=bookmarks)


@app.route('/account/saved')
@login_required
def account_saved():
    bookmarks = Bookmark.query.filter_by(user_id=current_user.id).order_by(
        Bookmark.created_at.desc(), Bookmark.id.desc()).all()
    return render_template('account_saved.html', bookmarks=bookmarks)


@app.route('/account/history')
@login_required
def account_history():
    history = ReadingHistory.query.filter_by(user_id=current_user.id).order_by(
        ReadingHistory.visited_at.desc(), ReadingHistory.id.desc()).limit(50).all()
    return render_template('account_history.html', history=history)


@app.route('/account/bookmarks/toggle', methods=['POST'])
@login_required
def toggle_bookmark():
    kind = request.form.get('kind') or ''
    slug = request.form.get('slug') or ''
    title = request.form.get('title') or ''
    if kind not in ('measure', 'state', 'report', 'article') or not slug:
        abort(400)
    existing = Bookmark.query.filter_by(user_id=current_user.id, kind=kind,
                                        item_slug=slug).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Removed from your saved items.', 'info')
    else:
        db.session.add(Bookmark(user_id=current_user.id, kind=kind,
                                item_slug=slug, title=title))
        db.session.commit()
        flash('Saved to your account.', 'success')
    return redirect(request.form.get('next') or request.referrer or url_for('index'))


@app.route('/newsletter/signup', methods=['POST'])
def newsletter_signup():
    name = (request.form.get('name') or '').strip()
    email = (request.form.get('email') or '').strip()
    if not name or '@' not in email or '.' not in email.split('@')[-1]:
        flash('Please enter a valid name and email address.', 'error')
        return redirect(request.referrer or url_for('index'))
    db.session.add(NewsletterSignup(name=name, email=email))
    db.session.commit()
    flash('Thank you for signing up for updates.', 'success')
    return redirect(request.referrer or url_for('index'))


@app.route('/_health')
def health():
    ok = db.session.execute(db.text('SELECT 1')).scalar() == 1
    return jsonify({'ok': bool(ok), 'site': 'americas_health_rankings',
                    'measures': Measure.query.count(),
                    'states': StateGeo.query.count(),
                    'reports': Report.query.count()})


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

from seed_data import seed_database, seed_benchmark_users  # noqa: E402

with app.app_context():
    db.create_all()
    seed_database(db, StateGeo, StateFact, MeasureCategory, Measure,
                  MeasureValue, MeasureDisparity, MeasureOption,
                  MeasureLink, Edition, MeasureEdition, EditionMeasureState,
                  Report, ReportSection, Article, Topic, FaqItem,
                  StaticPage, HomeBlock)
    seed_benchmark_users(db, User, Bookmark, ReadingHistory, bcrypt)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
