#!/usr/bin/env python3
"""Megabus mirror — Flask application.

Mirrors https://us.megabus.com/ (journey search, basket, guest checkout,
account area, manage-booking, fare finder, route/city guides, stops, help
FAQ, service alerts and the bus tracker) using real data captured from the
upstream site on 2026-09-23.
"""
import json
import os
import secrets
import re
import uuid
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from werkzeug.utils import secure_filename
from urllib.parse import urlsplit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("MEGABUS_SECRET_KEY") or secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'MEGABUS_DB_URI',
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'megabus.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'account_login'
login_manager.login_message = 'Please sign in to access your account.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# The mirror is a snapshot of the upstream site taken on 2026-09-23.
MIRROR_TODAY = date(2026, 9, 23)
BOOKING_FEE = 3.99
AMENDMENT_FEE = 7.50
SMS_FEE = 0.25


# ---------------------------------------------------------------- models --

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False, default='')
    last_name = db.Column(db.String(80), nullable=False, default='')
    phone = db.Column(db.String(30), default='')
    newsletter = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class City(db.Model):
    __tablename__ = 'cities'
    id = db.Column(db.Integer, primary_key=True)          # upstream city id
    name = db.Column(db.String(120), nullable=False)      # "New York, NY"
    state = db.Column(db.String(12), default='')          # "NY"
    slug = db.Column(db.String(140))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    @property
    def city_only(self):
        return self.name.split(',')[0].strip()


class Stop(db.Model):
    __tablename__ = 'stops'
    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey('cities.id'), nullable=False)
    carrier = db.Column(db.String(120), default='')
    name = db.Column(db.String(500), nullable=False)


class Journey(db.Model):
    __tablename__ = 'journeys'
    id = db.Column(db.String(32), primary_key=True)       # upstream journeyId (composite for connections)
    origin_city_id = db.Column(db.Integer, db.ForeignKey('cities.id'), nullable=False)
    dest_city_id = db.Column(db.Integer, db.ForeignKey('cities.id'), nullable=False)
    departure_date = db.Column(db.String(10), nullable=False)   # 2026-10-03
    dep_time = db.Column(db.String(5), nullable=False)                       # 00:25
    arr_time = db.Column(db.String(5), nullable=False)
    duration_min = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    route_name = db.Column(db.String(16), default='')
    reservable = db.Column(db.String(24), default='NONE')
    service_information = db.Column(db.String(24), default='INFORMATION')

    origin = db.relationship('City', foreign_keys=[origin_city_id])
    destination = db.relationship('City', foreign_keys=[dest_city_id])
    legs = db.relationship('JourneyLeg', backref='journey', cascade='all, delete-orphan',
                          order_by='JourneyLeg.seq')

    @property
    def duration_label(self):
        h, m = divmod(self.duration_min, 60)
        if h and m:
            return f"{h}h {m:02d}m"
        if h:
            return f"{h}h"
        return f"{m}m"

    @property
    def transfers(self):
        return max(0, len(self.legs) - 1)

    @property
    def carriers(self):
        seen, out = set(), []
        for leg in self.legs:
            if leg.carrier and leg.carrier not in seen:
                seen.add(leg.carrier)
                out.append(leg.carrier)
        return out

    @property
    def dep_label(self):
        return fmt_time(self.dep_time)

    @property
    def arr_label(self):
        return fmt_time(self.arr_time)


class JourneyLeg(db.Model):
    __tablename__ = 'journey_legs'
    id = db.Column(db.Integer, primary_key=True)
    journey_id = db.Column(db.String(32), db.ForeignKey('journeys.id'), nullable=False)
    seq = db.Column(db.Integer, nullable=False, default=0)
    carrier = db.Column(db.String(120), default='')
    carrier_icon = db.Column(db.String(160), default='')
    dep_datetime = db.Column(db.String(19), default='')
    arr_datetime = db.Column(db.String(19), default='')
    duration_min = db.Column(db.Integer, default=0)
    origin_stop = db.Column(db.String(500), default='')
    origin_stop_id = db.Column(db.String(64), default='')
    dest_stop = db.Column(db.String(500), default='')
    dest_stop_id = db.Column(db.String(64), default='')


class TravelDate(db.Model):
    """Dates on which a route direction has bookable service."""
    __tablename__ = 'travel_dates'
    id = db.Column(db.Integer, primary_key=True)
    origin_city_id = db.Column(db.Integer, nullable=False)
    dest_city_id = db.Column(db.Integer, nullable=False)
    day = db.Column(db.String(10), nullable=False)


class BasketItem(db.Model):
    __tablename__ = 'basket_items'
    id = db.Column(db.Integer, primary_key=True)
    basket_token = db.Column(db.String(64), nullable=False)
    journey_id = db.Column(db.Integer, nullable=False)
    passengers = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(10), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(80), default='')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.String(20), default='confirmed')   # confirmed | cancelled
    total = db.Column(db.Float, nullable=False, default=0.0)
    sms_updates = db.Column(db.Boolean, default=False)
    passenger_names = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_on = db.Column(db.String(10), default='')

    journeys = db.relationship('BookingJourney', backref='booking', cascade='all, delete-orphan')

    @property
    def is_upcoming(self):
        for bj in self.journeys:
            j = Journey.query.get(bj.journey_id)
            if j and j.departure_date >= MIRROR_TODAY.isoformat():
                return True
        return False


class BookingJourney(db.Model):
    __tablename__ = 'booking_journeys'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    journey_id = db.Column(db.String(32), nullable=False)
    passengers = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)


class FaqEntry(db.Model):
    __tablename__ = 'faq_entries'
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(60), nullable=False)   # help page slug
    question = db.Column(db.String(400), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    seq = db.Column(db.Integer, default=0)


class CityGuide(db.Model):
    __tablename__ = 'city_guides'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    title = db.Column(db.String(200), default='')
    page_title = db.Column(db.String(200), default='')
    hero = db.Column(db.String(300), default='')
    is_city = db.Column(db.Boolean, default=True)
    sections_json = db.Column(db.Text, default='[]')

    @property
    def sections(self):
        try:
            return json.loads(self.sections_json or '[]')
        except Exception:
            return []


class RouteGuide(db.Model):
    __tablename__ = 'route_guides'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    title = db.Column(db.String(200), default='')
    link_title = db.Column(db.String(200), default='')
    subtitle = db.Column(db.String(300), default='')
    origin_city_id = db.Column(db.Integer)
    dest_city_id = db.Column(db.Integer)
    banner = db.Column(db.String(300), default='')
    stats_json = db.Column(db.Text, default='{}')
    details = db.Column(db.Text, default='')
    faqs_json = db.Column(db.Text, default='[]')
    related_json = db.Column(db.Text, default='[]')
    seq = db.Column(db.Integer, default=0)

    @property
    def stats(self):
        try:
            return json.loads(self.stats_json or '{}')
        except Exception:
            return {}

    @property
    def faqs(self):
        try:
            return json.loads(self.faqs_json or '[]')
        except Exception:
            return []

    @property
    def related(self):
        try:
            return json.loads(self.related_json or '[]')
        except Exception:
            return []


class ServiceAlert(db.Model):
    __tablename__ = 'service_alerts'
    id = db.Column(db.Integer, primary_key=True)
    severity = db.Column(db.String(24), default='information')   # information | major | severe
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default='')
    route_name = db.Column(db.String(64), default='')
    published_on = db.Column(db.String(10), default='')


class PromoCode(db.Model):
    __tablename__ = 'promo_codes'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(24), unique=True, nullable=False)
    kind = db.Column(db.String(12), default='amount')     # amount | percent
    value = db.Column(db.Float, nullable=False)
    min_spend = db.Column(db.Float, default=0.0)
    description = db.Column(db.String(300), default='')
    active = db.Column(db.Boolean, default=True)


class BusStatus(db.Model):
    """Live-ish tracker state for journeys (snapshot values)."""
    __tablename__ = 'bus_statuses'
    id = db.Column(db.Integer, primary_key=True)
    journey_id = db.Column(db.String(32), nullable=False)
    state = db.Column(db.String(24), default='On time')    # On time | Delayed | En route
    delay_min = db.Column(db.Integer, default=0)
    current_stop = db.Column(db.String(300), default='')


class NewsletterSignup(db.Model):
    __tablename__ = 'newsletter_signups'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), default='')
    email = db.Column(db.String(120), default='')
    topic = db.Column(db.String(80), default='')
    message = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StaticPage(db.Model):
    __tablename__ = 'static_pages'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    content = db.Column(db.Text, default='')


class SavedPassenger(db.Model):
    __tablename__ = 'saved_passengers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(10), default='')
    first_name = db.Column(db.String(80), default='')
    last_name = db.Column(db.String(80), default='')
    date_of_birth = db.Column(db.String(10), default='')


# --------------------------------------------------------------- helpers --

def fmt_time(hhmm):
    """'00:25' -> '12:25am' matching the upstream card format."""
    hh, mm = hhmm.split(':')
    h = int(hh)
    suffix = 'am' if h < 12 else 'pm'
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{mm}{suffix}"


def fmt_money(v):
    return f"${v:,.2f}"


def date_label(iso):
    d = date.fromisoformat(iso)
    return d.strftime('%a ') + d.strftime('%b ').strip() + d.strftime('%d') .rstrip('0').rstrip() + 'th' \
        if False else d.strftime('%a %b ') + day_ordinal(d.day)


def day_ordinal(n):
    if 11 <= n % 100 <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


def parse_iso(iso):
    try:
        return date.fromisoformat(iso)
    except Exception:
        return None


def basket_token():
    if 'basket_token' not in session:
        session['basket_token'] = uuid.uuid4().hex
    return session['basket_token']


def get_basket():
    return BasketItem.query.filter_by(basket_token=basket_token()).order_by(BasketItem.id).all()


def basket_totals(items, promo=None, sms=False):
    fare = sum(i.unit_price * i.passengers for i in items)
    discount = 0.0
    if promo:
        if promo.kind == 'amount':
            discount = min(promo.value, fare)
        else:
            discount = round(fare * promo.value / 100.0, 2)
    fee = BOOKING_FEE if items else 0.0
    sms_cost = SMS_FEE if sms else 0.0
    total = round(fare - discount + fee + sms_cost, 2)
    return {'fare': round(fare, 2), 'discount': round(discount, 2),
            'fee': round(fee, 2), 'sms': round(sms_cost, 2), 'total': total}


def applied_promo():
    code = session.get('promo_code')
    if not code:
        return None
    return PromoCode.query.filter_by(code=code, active=True).first()


def make_reference():
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    rnd = uuid.uuid4().int
    out = []
    for i in range(6):
        out.append(alphabet[rnd % len(alphabet)])
        rnd //= len(alphabet)
    return ''.join(out)


STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or',
              'is', 'it', 'by', 'with', 'my', 'me', 'i'}


def tokenize(q):
    return [t.lower() for t in re.split(r'\W+', q)
            if t.lower() not in STOP_WORDS and len(t) > 1]


def scored_search(query, rows, fields):
    tokens = tokenize(query)
    if not tokens:
        return rows
    results = []
    for row in rows:
        text = ' '.join(getattr(row, f, '') or '' for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            results.append((row, score))
    results.sort(key=lambda x: (-x[1], getattr(x[0], 'id', 0)))
    return [r for r, _ in results]


# ------------------------------------------------------------ jinja bits --

app.jinja_env.globals.update(
    BOOKING_FEE=BOOKING_FEE, AMENDMENT_FEE=AMENDMENT_FEE, SMS_FEE=SMS_FEE)
app.jenv = app.jinja_env
app.jinja_env.filters['money'] = fmt_money
app.jinja_env.filters['timefmt'] = fmt_time
app.jinja_env.filters['datelabel'] = date_label
app.jinja_env.globals['fmt_time'] = fmt_time
app.jinja_env.globals['fmt_money'] = fmt_money
app.jinja_env.globals['date_label'] = date_label


def route_args(origin, dest, day, passengers=1):
    return (f"/journey-planner/journeys?originId={origin}&destinationId={dest}"
            f"&departureDate={day}&totalPassengers={passengers}")


app.jinja_env.globals['route_args'] = route_args


def mdlite(text):
    """Render the light markup used by the captured static-page snapshots."""
    import html as _h
    out = []
    for block in re.split(r'\n\s*\n', (text or '').strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith('### '):
            out.append(f"<h3>{_h.escape(block[4:])}</h3>")
        elif block.startswith('## '):
            head = _h.escape(block[3:])
            if head.strip():
                out.append(f"<h2>{head}</h2>")
        elif block.startswith('# '):
            out.append(f"<h1>{_h.escape(block[2:])}</h1>")
        elif block.startswith('- '):
            items = '\n'.join(
                f"<li>{_h.escape(line[2:].strip())}</li>"
                for line in block.splitlines() if line.startswith('- '))
            out.append(f"<ul>{items}</ul>")
        else:
            body = _h.escape(block).replace('\n', '<br>')
            out.append(f"<p>{body}</p>")
    return '\n'.join(out)


app.jinja_env.filters['mdlite'] = mdlite


# ---------------------------------------------------------------- routes --

def local_target(value, fallback):
    target = urlsplit(value or '')
    return value if value and value.startswith('/') and not value.startswith('//') and not target.netloc and not target.scheme and '\\' not in value else fallback


def booking_access(booking):
    return ((current_user.is_authenticated and (booking.user_id == current_user.id or (booking.user_id is None and booking.email.casefold() == current_user.email.casefold())))
            or booking.reference in session.get('verified_bookings', []))


def require_booking_access(booking):
    if not booking_access(booking):
        abort(403)


@app.route('/')
def home():
    hero_routes = [
        ('philadelphia-to-new-york', 'Philadelphia to New York bus'),
        ('washington-to-new-york', 'Washington DC to New York bus'),
        ('baltimore-to-new-york', 'Baltimore to New York bus'),
        ('pittsburgh-to-new-york', 'Pittsburgh to New York bus'),
        ('boston-to-new-york-bus', 'Boston to New York bus'),
        ('toronto-to-new-york-bus', 'Toronto to New York bus'),
        ('new-york-to-philadelphia-bus', 'New York to Philadelphia bus'),
        ('washington-to-philadelphia-bus', 'Washington to Philadelphia bus'),
        ('baltimore-to-philadelphia-bus', 'Baltimore to Philadelphia bus'),
        ('pittsburgh-to-philadelphia-bus', 'Pittsburgh to Philadelphia bus'),
        ('state-college-to-philadelphia-bus', 'State College to Philadelphia bus'),
        ('new-york-to-washington-bus', 'New York to DC bus'),
        ('philadelphia-to-washington-bus', 'Philadelphia to DC bus'),
        ('baltimore-to-washington-bus', 'Baltimore to DC bus'),
        ('richmond-to-washington-bus', 'Richmond to DC bus'),
    ]
    guides = RouteGuide.query.order_by(RouteGuide.seq).all()
    by_slug = {g.slug: g for g in guides}
    top_routes = [(slug, title, slug in by_slug) for slug, title in hero_routes]
    alerts = ServiceAlert.query.order_by(ServiceAlert.id).all()
    return render_template('index.html', top_routes=top_routes, alerts=alerts)


@app.route('/journey-planner/api/origin-cities')
def api_origin_cities():
    cities = City.query.order_by(City.name).all()
    return jsonify({'cities': [
        {'id': c.id, 'name': c.name, 'latitude': c.latitude, 'longitude': c.longitude}
        for c in cities]})


@app.route('/journey-planner/api/destination-cities')
def api_destination_cities():
    origin_id = request.args.get('originCityId', type=int)
    if not origin_id:
        return jsonify({'cities': []})
    rows = (db.session.query(TravelDate.dest_city_id.distinct().label('cid'))
            .filter(TravelDate.origin_city_id == origin_id).all())
    ids = [r.cid for r in rows]
    cities = City.query.filter(City.id.in_(ids)).order_by(City.name).all() if ids else []
    return jsonify({'cities': [
        {'id': c.id, 'name': c.name, 'latitude': c.latitude, 'longitude': c.longitude}
        for c in cities]})


@app.route('/journey-planner/journeys')
def journey_results():
    origin_id = request.args.get('originId', type=int)
    dest_id = request.args.get('destinationId', type=int)
    day = request.args.get('departureDate', '')
    passengers = request.args.get('totalPassengers', 1, type=int) or 1
    passengers = max(1, min(9, passengers))
    origin = City.query.get(origin_id) if origin_id else None
    dest = City.query.get(dest_id) if dest_id else None
    if not origin or not dest:
        return render_template('journeys_error.html', origin=origin, dest=dest,
                               day=day, passengers=passengers), 404

    day = day or (MIRROR_TODAY + timedelta(days=1)).isoformat()
    d = parse_iso(day)
    if not d:
        d = MIRROR_TODAY + timedelta(days=1)
        day = d.isoformat()

    journeys = (Journey.query
                .filter_by(origin_city_id=origin.id, dest_city_id=dest.id, departure_date=day)
                .order_by(Journey.dep_time).all())

    # date ribbon: 7 days centred on the selected date with the cheapest fare
    ribbon = []
    for off in range(-3, 4):
        rd = d + timedelta(days=off)
        if rd < MIRROR_TODAY:
            continue
        iso = rd.isoformat()
        cheapest = (db.session.query(db.func.min(Journey.price))
                    .filter(Journey.origin_city_id == origin.id,
                            Journey.dest_city_id == dest.id,
                            Journey.departure_date == iso).scalar())
        ribbon.append({'date': iso, 'label': date_label(iso),
                       'price': cheapest, 'selected': iso == day})

    carrier_filter = request.args.get('carrier', '').strip()
    carriers = []
    for j in journeys:
        for c in j.carriers:
            if c not in carriers:
                carriers.append(c)
    if carrier_filter and carrier_filter in carriers:
        journeys = [j for j in journeys if carrier_filter in j.carriers]

    return render_template('journeys.html', origin=origin, dest=dest, day=day,
                           day_label=date_label(day), passengers=passengers,
                           journeys=journeys, ribbon=ribbon, carriers=carriers,
                           carrier_filter=carrier_filter,
                           total_results=len(journeys))


@app.route('/journey-planner/basket')
def basket_page():
    items = get_basket()
    enriched = []
    for item in items:
        j = Journey.query.get(item.journey_id)
        if j:
            enriched.append({'item': item, 'journey': j})
    totals = basket_totals(items, applied_promo(), session.get('sms_updates'))
    return render_template('basket.html', entries=enriched, totals=totals,
                          promo=applied_promo())


@app.route('/journey-planner/basket/add', methods=['POST'])
def basket_add():
    journey_id = request.form.get('journey_id', '').strip()
    passengers = request.form.get('passengers', 1, type=int) or 1
    passengers = max(1, min(9, passengers))
    j = Journey.query.get(journey_id) if journey_id else None
    if not j:
        abort(404)
    # one basket entry per journey; bump passengers if re-added
    existing = BasketItem.query.filter_by(basket_token=basket_token(),
                                          journey_id=j.id).first()
    if existing:
        existing.passengers = max(1, min(9, existing.passengers + passengers))
        existing.unit_price = j.price
    else:
        db.session.add(BasketItem(basket_token=basket_token(), journey_id=j.id,
                                  passengers=passengers, unit_price=j.price))
    db.session.commit()
    return redirect(url_for('basket_page'))


@app.route('/journey-planner/basket/remove', methods=['POST'])
def basket_remove():
    item_id = request.form.get('item_id', type=int)
    BasketItem.query.filter_by(id=item_id,
                               basket_token=basket_token()).delete()
    db.session.commit()
    return redirect(url_for('basket_page'))


@app.route('/journey-planner/basket/promo', methods=['POST'])
def basket_promo():
    code = request.form.get('code', '').strip().upper()
    if not code:
        session.pop('promo_code', None)
    else:
        promo = PromoCode.query.filter_by(code=code, active=True).first()
        if promo:
            session['promo_code'] = promo.code
            flash(f'Promotion code {promo.code} applied: {promo.description}', 'success')
        else:
            flash(f'The code {code} is not valid. Check the spelling and try again.', 'error')
    return redirect(url_for('basket_page'))


@app.route('/journey-planner/basket/pay', methods=['POST'])
def basket_pay():
    if not get_basket():
        return redirect(url_for('home'))
    session['sms_updates'] = request.form.get('sms_updates') == 'on'
    return redirect(url_for('checkout_login'))


@app.route('/journey-planner/login', methods=['GET', 'POST'])
def checkout_login():
    items = get_basket()
    if not items:
        flash('Your basket is empty.', 'error')
        return redirect(url_for('home'))
    if current_user.is_authenticated:
        session['checkout_email'] = current_user.email
        return redirect(url_for('checkout_passengers'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'guest':
            session['checkout_email'] = request.form.get('email', '').strip().lower()
            return redirect(url_for('checkout_passengers'))
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            session['checkout_email'] = user.email
            return redirect(url_for('checkout_passengers'))
        flash('The email address or password is incorrect.', 'error')
    return render_template('checkout_login.html')


@app.route('/journey-planner/passenger-details', methods=['GET', 'POST'])
def checkout_passengers():
    items = get_basket()
    if not items:
        return redirect(url_for('home'))
    if request.method == 'POST':
        names = []
        for i in range(1, 10):
            fn = request.form.get(f'first_name_{i}', '').strip()
            ln = request.form.get(f'last_name_{i}', '').strip()
            if fn and ln:
                names.append(f"{fn} {ln}")
        email = request.form.get('email', '').strip().lower()
        if not names:
            flash('Enter the lead passenger\'s first and last name.', 'error')
        elif not email or '@' not in email:
            flash('Enter a valid email address for the tickets.', 'error')
        else:
            session['checkout_names'] = names
            session['checkout_email'] = email
            session['checkout_phone'] = request.form.get('phone', '').strip()
            return redirect(url_for('checkout_payment'))
    total_passengers = sum(i.passengers for i in items)
    entries = []
    for item in items:
        j = Journey.query.get(item.journey_id)
        if j:
            entries.append({'item': item, 'journey': j})
    return render_template('checkout_passengers.html', entries=entries,
                           total_passengers=total_passengers,
                           checkout_email=session.get('checkout_email', ''))


@app.route('/journey-planner/payment', methods=['GET', 'POST'])
def checkout_payment():
    items = get_basket()
    if not items:
        return redirect(url_for('home'))
    if not session.get('checkout_names') or not session.get('checkout_email'):
        return redirect(url_for('checkout_passengers'))
    form_data = {}
    if request.method == 'POST':
        card_name = request.form.get('card_name', '').strip()
        card_number = re.sub(r'\s+', '', request.form.get('card_number', ''))
        expiry = request.form.get('expiry', '').strip()
        cvv = request.form.get('cvv', '').strip()
        zip_code = request.form.get('zip', '').strip()
        errors = []
        if len(card_name) < 3:
            errors.append('Enter the name printed on the card.')
        if not re.fullmatch(r'\d{13,19}', card_number):
            errors.append('Enter a valid card number (13-19 digits).')
        if not re.fullmatch(r'(0[1-9]|1[0-2])/\d{2}', expiry):
            errors.append('Enter the expiry date as MM/YY.')
        if re.fullmatch(r'(0[1-9]|1[0-2])/\d{2}', expiry) and (2000 + int(expiry[3:]), int(expiry[:2])) < (MIRROR_TODAY.year, MIRROR_TODAY.month):
            errors.append('This card has expired.')
        if not re.fullmatch(r'\d{3,4}', cvv):
            errors.append('Enter the 3 or 4 digit security code.')
        if not zip_code:
            errors.append('Enter the billing ZIP code.')
        if errors:
            for e in errors:
                flash(e, 'error')
            form_data = {k: v for k, v in request.form.items() if k != 'csrf_token'}
        else:
            form_data = {}
            sms = session.get('sms_updates', False)
            names = session.get('checkout_names') or ['Lead Passenger']
            email = session.get('checkout_email') or 'guest@example.com'
            totals = basket_totals(items, applied_promo(), sms)
            reference = make_reference()
            booking = Booking(reference=reference, email=email,
                              last_name=names[0].split()[-1] if ' ' in names[0] else names[0],
                              user_id=current_user.id if current_user.is_authenticated else None,
                              status='confirmed', total=totals['total'],
                              sms_updates=sms,
                              passenger_names=', '.join(names),
                              created_on=MIRROR_TODAY.isoformat())
            db.session.add(booking)
            db.session.flush()
            for item in items:
                db.session.add(BookingJourney(booking_id=booking.id,
                                              journey_id=item.journey_id,
                                              passengers=item.passengers,
                                              price=round(item.unit_price * item.passengers, 2)))
            for item in items:
                db.session.delete(item)
            db.session.commit()
            session['verified_bookings'] = list(set(session.get('verified_bookings', []) + [reference]))
            session.pop('promo_code', None)
            session.pop('sms_updates', None)
            session.pop('checkout_names', None)
            session.pop('checkout_email', None)
            return redirect(url_for('checkout_confirmation', ref=reference))
    totals = basket_totals(items, applied_promo(), session.get('sms_updates'))
    entries = []
    for item in items:
        j = Journey.query.get(item.journey_id)
        if j:
            entries.append({'item': item, 'journey': j})
    return render_template('checkout_payment.html', entries=entries, totals=totals,
                           form_data=form_data)


@app.route('/journey-planner/confirmation/<ref>')
def checkout_confirmation(ref):
    booking = Booking.query.filter_by(reference=ref).first_or_404()
    require_booking_access(booking)
    entries = []
    for bj in booking.journeys:
        j = Journey.query.get(bj.journey_id)
        if j:
            entries.append({'bj': bj, 'journey': j})
    return render_template('confirmation.html', booking=booking, entries=entries)


@app.route('/journey-planner/manage-booking', methods=['GET', 'POST'])
def manage_booking():
    booking = None
    entries = []
    not_found = False
    ref = ''
    if request.method == 'POST':
        ref = request.form.get('reference', '').strip().upper()
        email_or_name = request.form.get('email', '').strip()
        booking = Booking.query.filter_by(reference=ref).first()
        if booking:
            email = email_or_name.strip().lower()
            last_name = email_or_name.strip().lower()
            if (booking.email.lower() != email and
                    booking.last_name.lower() != last_name):
                booking = None
        if not booking:
            not_found = True
    elif request.args.get('ref'):
        ref = request.args.get('ref', '').strip().upper()
        booking = Booking.query.filter_by(reference=ref).first()
        if not booking:
            not_found = True
    if booking:
        if request.method == 'POST':
            session['verified_bookings'] = list(set(session.get('verified_bookings', []) + [booking.reference]))
        require_booking_access(booking)
        for bj in booking.journeys:
            j = Journey.query.get(bj.journey_id)
            if j:
                entries.append({'bj': bj, 'journey': j})
    return render_template('manage_booking.html', booking=booking, entries=entries,
                            not_found=not_found, ref=ref)


@app.route('/journey-planner/manage-booking/cancel', methods=['POST'])
def manage_booking_cancel():
    ref = request.form.get('reference', '').strip().upper()
    booking = Booking.query.filter_by(reference=ref).first_or_404()
    require_booking_access(booking)
    if booking.status != 'confirmed':
        abort(409)
    booking.status = 'cancelled'
    db.session.commit()
    flash(f'Booking {booking.reference} was cancelled. A refund credit will be '
          'emailed to you within 5-7 business days.', 'success')
    return redirect(url_for('manage_booking', ref=booking.reference))


@app.route('/journey-planner/manage-booking/change', methods=['GET', 'POST'])
def manage_booking_change():
    ref = request.args.get('ref') or request.form.get('reference', '')
    bj_id = request.args.get('bj', type=int) or request.form.get('bj', type=int)
    booking = Booking.query.filter_by(reference=(ref or '').strip().upper()).first_or_404()
    require_booking_access(booking)
    if booking.status != 'confirmed':
        abort(409)
    bj = BookingJourney.query.get(bj_id) if bj_id else None
    if not bj or bj.booking_id != booking.id:
        abort(404)
    j = Journey.query.get(bj.journey_id)
    if not j:
        abort(404)
    if request.method == 'POST':
        new_journey_id = request.form.get('new_journey_id', '').strip()
        new_j = Journey.query.get(new_journey_id) if new_journey_id else None
        if not new_j or new_j.origin_city_id != j.origin_city_id \
                or new_j.dest_city_id != j.dest_city_id \
                or new_j.id == j.id or new_j.departure_date < MIRROR_TODAY.isoformat():
            flash('Choose a departure for the same route from the list of available days.', 'error')
        else:
            fare_delta = round(new_j.price * bj.passengers - bj.price, 2)
            fee = AMENDMENT_FEE
            bj.journey_id = new_j.id
            bj.price = round(new_j.price * bj.passengers, 2)
            booking.total = round(booking.total + fare_delta + fee, 2)
            db.session.commit()
            flash(f'Trip changed to {new_j.departure_date}. '
                  f'Fare difference {fmt_money(fare_delta)} plus a '
                  f'{fmt_money(fee)} amendment fee apply.', 'success')
            return redirect(url_for('manage_booking', ref=booking.reference))
    available = (Journey.query
                 .filter(Journey.origin_city_id == j.origin_city_id,
                         Journey.dest_city_id == j.dest_city_id,
                         Journey.id != j.id,
                         Journey.departure_date >= MIRROR_TODAY.isoformat())
                 .order_by(Journey.departure_date, Journey.dep_time).all())
    return render_template('manage_change.html', booking=booking, bj=bj, journey=j,
                           available=available)


@app.route('/journey-planner/track', methods=['GET', 'POST'])
def track_bus():
    journey = None
    status = None
    results = []
    est_arr = None
    status_map = {}
    if request.method == 'POST':
        origin_id = request.form.get('originId', type=int)
        dest_id = request.form.get('destinationId', type=int)
        day = request.form.get('departureDate', '')
        if origin_id and dest_id and day:
            results = (Journey.query.filter_by(origin_city_id=origin_id,
                                               dest_city_id=dest_id,
                                               departure_date=day)
                       .order_by(Journey.dep_time).all())
            for j in results:
                st = BusStatus.query.filter_by(journey_id=j.id).first()
                if st:
                    status_map[j.id] = st
            if results and not status_map:
                status_map[results[0].id] = None
    jid = request.args.get('journeyId', '').strip()
    if jid:
        journey = Journey.query.get(jid)
        if journey:
            status = BusStatus.query.filter_by(journey_id=journey.id).first()
            if not status:
                status = BusStatus(journey_id=journey.id, state='On time',
                                   delay_min=0, current_stop='')
            if status.delay_min:
                hh, mm = journey.arr_time.split(':')
                total = int(hh) * 60 + int(mm) + status.delay_min
                est_arr = f"{total // 60 % 24:02d}:{total % 60:02d}"
    origins = City.query.order_by(City.name).all()
    return render_template('tracker.html', origins=origins, results=results,
                           journey=journey, status=status, est_arr=est_arr,
                           status_map=status_map)


@app.route('/fare-finder')
def fare_finder():
    origins = (db.session.query(City)
               .join(TravelDate, TravelDate.origin_city_id == City.id)
               .distinct().order_by(City.name).all())
    return render_template('fare_finder.html', origins=origins)


@app.route('/fare-finder/search')
def fare_finder_search():
    origin_id = request.args.get('originId', type=int)
    edit = request.args.get('edit')
    origins = (db.session.query(City)
               .join(TravelDate, TravelDate.origin_city_id == City.id)
               .distinct().order_by(City.name).all())
    origin = City.query.get(origin_id) if origin_id else None
    # busiest single day per destination (the 'up to N departures a day' stat)
    per_date = (db.session.query(
                    Journey.dest_city_id.label('dest'),
                    db.func.count(Journey.id).label('cnt'))
                .filter(Journey.origin_city_id == (origin_id or -1))
                .group_by(Journey.dest_city_id, Journey.departure_date).subquery())
    busiest = dict((r.dest, r.cnt) for r in db.session.query(per_date))
    fares = []
    if origin:
        rows = (db.session.query(Journey.dest_city_id,
                                db.func.min(Journey.price),
                                db.func.min(Journey.duration_min))
                .filter(Journey.origin_city_id == origin.id)
                .group_by(Journey.dest_city_id).all())
        for dest_id, cheapest, fastest in sorted(rows, key=lambda r: (r[1] if r[1] is not None else 999, r[0])):
            dest = City.query.get(dest_id)
            if not dest or cheapest is None:
                continue
            fares.append({'dest': dest, 'price': cheapest,
                          'duration': fastest, 'per_day': busiest.get(dest.id, 0)})
    return render_template('fare_finder.html', origins=origins, origin=origin,
                           fares=fares, edit=edit)


@app.route('/route-guides')
def route_guides_index():
    # The upstream index links the 15 hero routes; the remaining captured
    # guides (seq >= 100) are reachable through each guide's related routes,
    # matching how upstream exposes them.
    guides = (RouteGuide.query.filter(RouteGuide.seq < 100)
              .order_by(RouteGuide.seq).all())
    return render_template('route_guides.html', guides=guides)


@app.route('/route-guides/<slug>')
def route_guide_detail(slug):
    guide = RouteGuide.query.filter_by(slug=slug).first()
    if not guide:
        abort(404)
    origin = City.query.get(guide.origin_city_id) if guide.origin_city_id else None
    dest = City.query.get(guide.dest_city_id) if guide.dest_city_id else None
    journeys = []
    if origin and dest:
        days = {r.day for r in TravelDate.query.filter_by(
            origin_city_id=origin.id, dest_city_id=dest.id).all()}
        for day in sorted(days)[:7]:
            if day >= (MIRROR_TODAY + timedelta(days=1)).isoformat():
                journeys.append({'day': day, 'label': date_label(day)})
    # Related-route chips only link guides the mirror serves (the captured
    # set covers every guide within two hops of the upstream index; the
    # deep partner-network long tail is filtered out here instead of 404ing).
    guide_slugs = {s for (s,) in db.session.query(RouteGuide.slug).all()}
    return render_template('route_guide_detail.html', guide=guide, origin=origin,
                           dest=dest, journeys=journeys, guide_slugs=guide_slugs)


@app.route('/city-guides')
def city_guides_index():
    guides = CityGuide.query.order_by(CityGuide.slug).all()
    cities = [g for g in guides if g.is_city]
    articles = [g for g in guides if not g.is_city]
    return render_template('city_guides.html', cities=cities, articles=articles)


@app.route('/city-guides/<slug>')
def city_guide_detail(slug):
    guide = CityGuide.query.filter_by(slug=slug).first()
    if not guide:
        abort(404)
    return render_template('city_guide_detail.html', guide=guide)


@app.route('/stops')
def stops_index():
    cities = City.query.order_by(City.name).all()
    stops_count = Stop.query.count()
    grouped = {}
    for c in cities:
        grouped.setdefault(c.state or '—', []).append(c)
    stops_by_city = {}
    for st in Stop.query.order_by(Stop.id).all():
        stops_by_city.setdefault(st.city_id, []).append(st.name)
    return render_template('stops.html', grouped=grouped, stops_count=stops_count,
                           stops_by_city=stops_by_city)


@app.route('/stops/<slug>')
def stop_detail(slug):
    city = City.query.filter_by(slug=slug).first_or_404()
    stops = Stop.query.filter_by(city_id=city.id).all()
    return render_template('stop_detail.html', city=city, stops=stops)


@app.route('/help')
def help_index():
    popular = FaqEntry.query.filter_by(topic='help').order_by(FaqEntry.seq).all()
    topics = [('making-reservations', 'Making reservations'),
              ('changing-reservations', 'Changing reservations'),
              ('traveling-on-the-bus', 'Traveling on the bus'),
              ('bus-routes-stops', 'Bus routes and stops'),
              ('customers-with-special-requirements', 'Customers with special requirements'),
              ('terms-and-conditions', 'Terms and conditions')]
    return render_template('help.html', popular=popular, topics=topics)


@app.route('/help/<topic>')
def help_topic(topic):
    entries = FaqEntry.query.filter_by(topic=topic).order_by(FaqEntry.seq).all()
    if not entries:
        abort(404)
    titles = {'making-reservations': 'Making reservations',
              'changing-reservations': 'Changing reservations',
              'traveling-on-the-bus': 'Traveling on the bus',
              'bus-routes-stops': 'Bus routes and stops',
              'customers-with-special-requirements': 'Customers with special requirements',
              'terms-and-conditions': 'Terms and conditions'}
    return render_template('help_topic.html', topic=topic,
                           title=titles.get(topic, topic), entries=entries)


@app.route('/help/search')
def help_search():
    q = request.args.get('q', '').strip()
    results = []
    if q:
        rows = FaqEntry.query.all()
        results = scored_search(q, rows, ['question', 'answer'])
    return render_template('help_search.html', q=q, results=results)


@app.route('/search')
def site_search():
    q = request.args.get('q', '').strip()
    faq_hits, guide_hits, city_hits, route_hits, stop_hits = [], [], [], [], []
    if q:
        faq_hits = scored_search(q, FaqEntry.query.all(), ['question', 'answer'])[:12]
        guide_hits = scored_search(q, CityGuide.query.all(), ['title', 'page_title'])[:12]
        city_hits = scored_search(q, City.query.all(), ['name'])[:12]
        route_hits = scored_search(q, RouteGuide.query.all(), ['title', 'subtitle'])[:12]
        stop_hits = scored_search(q, Stop.query.all(), ['name'])[:12]
    total = len(faq_hits) + len(guide_hits) + len(city_hits) + len(route_hits) + len(stop_hits)
    return render_template('search.html', q=q, faq_hits=faq_hits, guide_hits=guide_hits,
                           city_hits=city_hits, route_hits=route_hits,
                           stop_hits=stop_hits, total=total)


@app.route('/service-alerts')
def service_alerts():
    alerts = ServiceAlert.query.order_by(ServiceAlert.id).all()
    return render_template('service_alerts.html', alerts=alerts)


@app.route('/contact-us', methods=['GET', 'POST'])
def contact_us():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        topic = request.form.get('topic', '').strip()
        message = request.form.get('message', '').strip()
        if not name or '@' not in email or not message:
            flash('Please fill in your name, a valid email address and a message.',
                  'error')
        else:
            db.session.add(ContactMessage(name=name, email=email, topic=topic,
                                          message=message))
            db.session.commit()
            flash('Thanks! Our virtual travel assistant Chuck will reply within '
                  '2 business days.', 'success')
            return redirect(url_for('contact_us'))
    return render_template('static/contact.html')


def _static_page(slug):
    page = StaticPage.query.filter_by(slug=slug).first()
    return render_template('static/generic.html', page=page, slug=slug)


@app.route('/about-us')
def about_us():
    return _static_page('about_us')


@app.route('/terms')
def terms():
    return _static_page('terms')


@app.route('/privacy-policy')
def privacy_policy():
    return _static_page('privacy')


@app.route('/passengers-with-disabilities')
def disabilities():
    return _static_page('disabilities')


@app.route('/accessibility')
def accessibility():
    return _static_page('accessibility')


@app.route('/employment')
def employment():
    return _static_page('employment')


@app.route('/partners')
def partners():
    return _static_page('partners')


@app.route('/media')
def media():
    return _static_page('media')


@app.route('/megabus-app')
def megabus_app():
    return _static_page('megabus_app')


@app.route('/webchat')
def webchat():
    return _static_page('webchat')


@app.route('/journey-planner/map')
def route_map():
    cities = City.query.order_by(City.name).all()
    return render_template('route_map.html', cities=cities[:120])


@app.route('/newsletter/signup', methods=['POST'])
def newsletter_signup():
    email = request.form.get('email', '').strip()
    if '@' not in email:
        flash('Enter a valid email address to join the mailing list.', 'error')
    else:
        db.session.add(NewsletterSignup(email=email))
        db.session.commit()
        flash('You are on the list! Watch your inbox for megabus deals.', 'success')
    return redirect(local_target(request.form.get('next'), url_for('home')))


# --------------------------------------------------------------- account --

@app.route('/account-management/login', methods=['GET', 'POST'])
def account_login():
    next_url = local_target(request.args.get('next'), url_for('account_overview'))
    if current_user.is_authenticated:
        return redirect(next_url)
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(next_url)
        flash('The email address or password is incorrect.', 'error')
    return render_template('account_login.html', next=next_url)


@app.route('/account-management/register', methods=['GET', 'POST'])
def account_register():
    if request.method == 'POST':
        first = request.form.get('first_name', '').strip()
        last = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if not first or not last:
            flash('Enter your first and last name.', 'error')
        elif '@' not in email:
            flash('Enter a valid email address.', 'error')
        elif len(password) < 8:
            flash('Choose a password of at least 8 characters.', 'error')
        elif password != confirm:
            flash('The passwords do not match.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('An account with that email already exists. Sign in instead.', 'error')
        else:
            user = User(email=email, first_name=first, last_name=last)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('account_overview'))
    return render_template('account_register.html')


@app.route('/account-management/logout', methods=['POST'])
@login_required
def account_logout():
    logout_user()
    session.clear()
    return redirect(url_for('home'))


@app.route('/account-management')
@login_required
def account_overview():
    bookings = (Booking.query.filter_by(email=current_user.email)
                .order_by(Booking.id).all())
    upcoming, past = [], []
    for b in bookings:
        if b.status == 'cancelled':
            past.append(b)
        elif b.is_upcoming:
            upcoming.append(b)
        else:
            past.append(b)
    saved = SavedPassenger.query.filter_by(user_id=current_user.id).all()
    entries_of = {}
    for b in bookings:
        entries_of[b.id] = [(bj, Journey.query.get(bj.journey_id))
                            for bj in b.journeys]
    return render_template('account_overview.html', upcoming=upcoming, past=past,
                           saved=saved, entries_of=entries_of)


@app.route('/account-management/profile', methods=['GET', 'POST'])
@login_required
def account_profile():
    if request.method == 'POST':
        first = request.form.get('first_name', '').strip()
        last = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        if not first or not last:
            flash('First and last name are required.', 'error')
        else:
            current_user.first_name = first
            current_user.last_name = last
            current_user.phone = phone
            db.session.commit()
            flash('Your details have been updated.', 'success')
            return redirect(url_for('account_profile'))
    return render_template('account_profile.html')


@app.route('/_health')
def health():
    return {'ok': True, 'site': 'megabus'}


# ----------------------------------------------------------------- seeds --

def seed_database():
    if City.query.count() > 0:
        return
    from seed_data import run_seed
    run_seed(db, City, Stop, Journey, JourneyLeg, TravelDate, FaqEntry,
             CityGuide, RouteGuide, ServiceAlert, PromoCode, BusStatus,
             StaticPage)


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    from seed_data import run_seed_users
    run_seed_users(db, User, Booking, BookingJourney, Journey, SavedPassenger)


# Indexes are created with explicit, name-sorted SQL (not SQLAlchemy's
# metadata pass, whose set-ordered index creation makes the SQLite file
# non-reproducible across builds). IF NOT EXISTS keeps every boot a no-op.
INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS ix_basket_items_basket_token ON basket_items (basket_token)",
    "CREATE INDEX IF NOT EXISTS ix_bookings_email ON bookings (email)",
    "CREATE INDEX IF NOT EXISTS ix_bookings_reference ON bookings (reference)",
    "CREATE INDEX IF NOT EXISTS ix_bus_statuses_journey_id ON bus_statuses (journey_id)",
    "CREATE INDEX IF NOT EXISTS ix_cities_slug ON cities (slug)",
    "CREATE INDEX IF NOT EXISTS ix_faq_entries_topic ON faq_entries (topic)",
    "CREATE INDEX IF NOT EXISTS ix_journeys_departure_date ON journeys (departure_date)",
    "CREATE INDEX IF NOT EXISTS ix_journeys_dest_city_id ON journeys (dest_city_id)",
    "CREATE INDEX IF NOT EXISTS ix_journeys_origin_city_id ON journeys (origin_city_id)",
    "CREATE INDEX IF NOT EXISTS ix_saved_passengers_user_id ON saved_passengers (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_stops_city_id ON stops (city_id)",
    "CREATE INDEX IF NOT EXISTS ix_travel_dates_dest_city_id ON travel_dates (dest_city_id)",
    "CREATE INDEX IF NOT EXISTS ix_travel_dates_origin_city_id ON travel_dates (origin_city_id)",
    "CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)",
)

with app.app_context():
    db.create_all()
    with db.engine.begin() as conn:
        for stmt in INDEX_STATEMENTS:
            conn.execute(db.text(stmt))
    seed_database()
    seed_benchmark_users()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
