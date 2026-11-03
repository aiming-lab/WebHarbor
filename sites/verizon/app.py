#!/usr/bin/env python3
"""verizon — a WebHarbor mirror of https://www.verizon.com/

Flask + SQLite mirror of the Verizon wireless storefront and support
surface: the Simplicity Plan page and the Verizon Prepaid plan tiers
(real upstream pricing captured 2026-09-29), the smartphones gridwall and
device pages for 24 real devices (colors, storage, 12/24/36/48-month
financing terms, spec-compare rows, ratings), the full configure -> cart ->
checkout purchase flow with trade-in estimates, the My Verizon account
surface (bill list + per-charge bill detail, one-time payments, Auto Pay /
paper-free billing enrollment, per-line usage, plan changes, add-a-line,
order status), the store locator (885 real stores across 10 states with
per-day hours and services), and the support surface (return policy,
contact-us hours, network support, the troubleshoot wizard, trade-in
program steps + FAQ).

Upstream-sourced content comes from the tracked source_data/*.json
snapshots captured on 2026-09-29 (see provenance.json).
Benchmark accounts (users, lines, bills, usage, orders), the trade-in
estimate matrix and the troubleshoot flows are deterministic fixtures
declared in provenance.json. The SQLite seed is materialized
deterministically at image build time (PYTHONHASHSEED=0, frozen bcrypt
benchmark users).
"""
import json
import os
import random
import re
import secrets
from decimal import Decimal, InvalidOperation
from datetime import date, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                          login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("VERIZON_SECRET_KEY") or "webharbor-verizon-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'VERIZON_DB_URI', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'verizon.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'account_login'
login_manager.login_message = 'Please sign in to your My Verizon account.'
csrf = CSRFProtect(app)

# The mirror is a frozen snapshot of the upstream site taken 2026-09-29.
MIRROR_TODAY = date(2026, 9, 29)
SITE_NAME = "verizon"
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
    account_number = db.Column(db.String(24), nullable=False)
    account_kind = db.Column(db.String(20), nullable=False, default='postpaid')
    street = db.Column(db.String(160))
    city = db.Column(db.String(80))
    state = db.Column(db.String(40))
    zip = db.Column(db.String(12))
    autopay = db.Column(db.Integer, nullable=False, default=0)
    paper_free = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.String(10), nullable=False)

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)


class Cart(db.Model):
    __tablename__ = 'carts'
    id = db.Column(db.Integer, primary_key=True)
    cart_key = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    items = db.Column(db.Text, nullable=False, default='[]')


def load_cart():
    key = session.get('cart_key')
    cart = Cart.query.filter_by(cart_key=key).first() if key else None
    if cart and cart.user_id is not None and (not current_user.is_authenticated or cart.user_id != current_user.id):
        session.pop('cart_key', None)
        return []
    return json.loads(cart.items) if cart else []


def save_cart(items):
    key = session.get('cart_key')
    cart = Cart.query.filter_by(cart_key=key).first() if key else None
    if cart is None:
        key = secrets.token_hex(24)
        session['cart_key'] = key
        cart = Cart(cart_key=key)
        db.session.add(cart)
    cart.user_id = current_user.id if current_user.is_authenticated else None
    cart.items = json.dumps(items)
    db.session.commit()


class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    brand = db.Column(db.String(60), nullable=False)
    colors = db.Column(db.Text, nullable=False, default='[]')
    storage = db.Column(db.Text, nullable=False, default='[]')
    terms = db.Column(db.Text, nullable=False, default='{}')
    full_price = db.Column(db.String(20))
    rating = db.Column(db.String(10))
    reviews = db.Column(db.String(20))
    ship_window = db.Column(db.String(80))
    promo = db.Column(db.Text, nullable=False, default='[]')
    specs = db.Column(db.Text, nullable=False, default='{}')
    color_images = db.Column(db.Text, nullable=False, default='{}')
    pdp_url = db.Column(db.String(240))

    def colors_list(self):
        return json.loads(self.colors)

    def storage_list(self):
        return json.loads(self.storage)

    def terms_map(self):
        return json.loads(self.terms)

    def promo_list(self):
        return json.loads(self.promo)

    def specs_map(self):
        return json.loads(self.specs)

    def images_map(self):
        return json.loads(self.color_images)

    def hero_images(self, color=None):
        imgs = self.images_map()
        if color and color in imgs:
            return imgs[color]
        if self.colors_list() and self.colors_list()[0] in imgs:
            return imgs[self.colors_list()[0]]
        return next(iter(imgs.values()), [])


class Plan(db.Model):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False)   # simplicity | prepaid
    name = db.Column(db.String(80), nullable=False)
    monthly = db.Column(db.String(12), nullable=False)
    autopay_monthly = db.Column(db.String(12))
    first_month = db.Column(db.String(12))
    data_note = db.Column(db.String(160))
    hotspot_gb = db.Column(db.Integer)
    features = db.Column(db.Text, nullable=False, default='[]')
    blurb = db.Column(db.String(240))
    sort = db.Column(db.Integer, nullable=False, default=0)

    def features_list(self):
        return json.loads(self.features)


class Store(db.Model):
    __tablename__ = 'stores'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(24), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    business = db.Column(db.String(120))
    store_type = db.Column(db.String(60))
    retailer = db.Column(db.String(60))
    phone = db.Column(db.String(20))
    street = db.Column(db.String(160))
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(4), nullable=False)
    zip = db.Column(db.String(12))
    hours = db.Column(db.Text, nullable=False, default='{}')
    services = db.Column(db.Text, nullable=False, default='[]')
    appointments = db.Column(db.Integer, nullable=False, default=0)
    fios = db.Column(db.Integer, nullable=False, default=0)
    pickup = db.Column(db.Integer, nullable=False, default=0)
    locker = db.Column(db.Integer, nullable=False, default=0)
    cma = db.Column(db.String(120))
    image_outside = db.Column(db.String(200))
    image_inside = db.Column(db.String(200))

    def hours_map(self):
        return json.loads(self.hours)

    def services_list(self):
        return [{'LOCKER': 'Express Pickup Locker', 'INSTORE': 'In-store shopping'}.get(service, service) for service in json.loads(self.services)]

    def display_type(self):
        return ("Verizon Company Store" if self.store_type == "Store"
                else self.store_type or "Verizon Authorized Retailer")


class ContentPage(db.Model):
    __tablename__ = 'content_pages'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    title = db.Column(db.String(220), nullable=False)
    body = db.Column(db.Text, nullable=False)

    def body_text(self):
        body = re.split(r'end of navigation menu', self.body, maxsplit=1, flags=re.I)[-1]
        if self.slug == 'return_policy' and 'Planning to ship us a device' in body:
            body = 'Planning to ship us a device' + body.split('Planning to ship us a device', 1)[1]
            body = body.split('Is this bill info helpful?', 1)[0]
        return re.split(r'\n\s*-?\s*Shop\s*\n\s*-?\s*Devices\b', body, maxsplit=1, flags=re.I)[0].strip()


class Line(db.Model):
    __tablename__ = 'lines'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    nickname = db.Column(db.String(80), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')
    joined_at = db.Column(db.String(10), nullable=False)
    device = db.relationship('Device')
    plan = db.relationship('Plan')


class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    period = db.Column(db.String(20), nullable=False)      # e.g. "Aug 2026"
    due_date = db.Column(db.String(10), nullable=False)
    total = db.Column(db.String(12), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='paid')
    charges = db.Column(db.Text, nullable=False, default='[]')

    def charges_list(self):
        return json.loads(self.charges)


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=True)
    amount = db.Column(db.String(12), nullable=False)
    method = db.Column(db.String(40), nullable=False)
    confirmation = db.Column(db.String(24), nullable=False)
    paid_at = db.Column(db.String(10), nullable=False)


class Usage(db.Model):
    __tablename__ = 'usage'
    id = db.Column(db.Integer, primary_key=True)
    line_id = db.Column(db.Integer, db.ForeignKey('lines.id'), nullable=False)
    cycle = db.Column(db.String(20), nullable=False)
    data_gb = db.Column(db.String(10), nullable=False)
    data_cap_gb = db.Column(db.String(10))
    hotspot_gb = db.Column(db.String(10))
    hotspot_cap_gb = db.Column(db.String(10))
    talk_min = db.Column(db.Integer, nullable=False)
    texts = db.Column(db.Integer, nullable=False)


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    confirmation = db.Column(db.String(24), unique=True, nullable=False)
    status = db.Column(db.String(30), nullable=False, default='processing')
    placed_at = db.Column(db.String(10), nullable=False)
    delivery_by = db.Column(db.String(40))
    items = db.Column(db.Text, nullable=False, default='[]')
    total_today = db.Column(db.String(12), nullable=False)
    total_monthly = db.Column(db.String(12), nullable=False)
    name = db.Column(db.String(120))
    email = db.Column(db.String(160))
    street = db.Column(db.String(160))
    city = db.Column(db.String(80))
    state = db.Column(db.String(40))
    zip = db.Column(db.String(12))

    def items_list(self):
        return json.loads(self.items)


class TradeInQuote(db.Model):
    __tablename__ = 'trade_in_quotes'
    id = db.Column(db.Integer, primary_key=True)
    device_name = db.Column(db.String(160), nullable=False)
    condition = db.Column(db.String(40), nullable=False)
    value = db.Column(db.String(12), nullable=False)
    sort = db.Column(db.Integer, nullable=False, default=0)


class TroubleshootFlow(db.Model):
    __tablename__ = 'troubleshoot_flows'
    id = db.Column(db.Integer, primary_key=True)
    device_family = db.Column(db.String(60), nullable=False)
    issue = db.Column(db.String(120), nullable=False)
    steps = db.Column(db.Text, nullable=False)          # JSON list of steps
    resolution = db.Column(db.Text, nullable=False)
    sort = db.Column(db.Integer, nullable=False, default=0)

    def steps_list(self):
        return json.loads(self.steps)


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(24), nullable=False)
    topic = db.Column(db.String(80), nullable=False)
    appt_date = db.Column(db.String(10), nullable=False)
    appt_time = db.Column(db.String(10), nullable=False)
    confirmation = db.Column(db.String(24), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='confirmed')
    store = db.relationship('Store')


class ProtectionPlan(db.Model):
    __tablename__ = 'protection_plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    monthly = db.Column(db.String(10), nullable=False)
    blurb = db.Column(db.String(240), nullable=False)
    sort = db.Column(db.Integer, nullable=False, default=0)


class PlanRule(db.Model):
    """Upstream plan-page rules and hero copy (DB, not request-time JSON)."""
    __tablename__ = 'plan_rules'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)


class CityIndex(db.Model):
    """Upstream store-locator city index per state."""
    __tablename__ = 'city_index'
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(40), nullable=False)
    city = db.Column(db.String(80), nullable=False)


# ----------------------------------------------------------------- fixtures --

PROTECTION_PLANS = [
    {"name": "Verizon Mobile Protect", "monthly": "17.00",
     "blurb": "Screen repair, battery replacement and theft/loss coverage for your device."},
    {"name": "Verizon Mobile Protect Multi-Device", "monthly": "40.00",
     "blurb": "Covers every eligible device on your account with one monthly price."},
    {"name": "Wireless Phone Protection", "monthly": "9.00",
     "blurb": "Basic protection against loss, theft and damage."},
]

TRADE_IN_MATRIX = {
    "Apple iPhone 18 Pro": {"Mint": "760.00", "Good": "650.00", "Cracked": "210.00"},
    "Apple iPhone 18 Pro Max": {"Mint": "850.00", "Good": "730.00", "Cracked": "250.00"},
    "Apple iPhone 17e": {"Mint": "300.00", "Good": "240.00", "Cracked": "70.00"},
    "Samsung Galaxy S26 Ultra": {"Mint": "720.00", "Good": "610.00", "Cracked": "190.00"},
    "Samsung Galaxy S26": {"Mint": "470.00", "Good": "390.00", "Cracked": "120.00"},
    "Samsung Galaxy S26+": {"Mint": "580.00", "Good": "490.00", "Cracked": "160.00"},
    "Google Pixel 11 Pro": {"Mint": "540.00", "Good": "450.00", "Cracked": "140.00"},
    "Google Pixel 11": {"Mint": "380.00", "Good": "300.00", "Cracked": "90.00"},
    "Google Pixel 10a": {"Mint": "210.00", "Good": "160.00", "Cracked": "45.00"},
    "Motorola razr+ 2026": {"Mint": "410.00", "Good": "330.00", "Cracked": "100.00"},
    "Motorola moto g - 2026": {"Mint": "95.00", "Good": "70.00", "Cracked": "18.00"},
    "Motorola edge - 2026": {"Mint": "170.00", "Good": "130.00", "Cracked": "35.00"},
}

TROUBLESHOOT_FLOWS = [
    {"device_family": "Apple", "issue": "Battery drains too fast",
     "steps": ["Open Settings and check Battery health — if Maximum Capacity is below 80%, the battery needs service.",
               "Close background apps: swipe up and remove the apps you are not using.",
               "Turn on Low Power Mode from Settings > Battery and watch the drain for a day.",
               "Update iOS: go to Settings > General > Software Update."],
     "resolution": "If the drain continues with Low Power Mode on and battery health above 80%, reset network settings; still draining, the battery needs service — book a store appointment or file a device protection claim."},
    {"device_family": "Apple", "issue": "No service or cannot connect to the network",
     "steps": ["Check the coverage map for your address from the Network support page.",
               "Toggle Airplane mode on for 10 seconds, then off.",
               "Restart the phone.",
               "Check for a carrier settings update: Settings > General > About."],
     "resolution": "No bars after these steps usually means a network issue in your area — report it from Network support; if only your line is affected, swap the SIM or visit a store."},
    {"device_family": "Apple", "issue": "Screen is cracked or unresponsive",
     "steps": ["Back up your phone if the screen still responds.",
               "Check whether the crack is on a screen protector (replaceable at a store).",
               "If you have Verizon Mobile Protect, you can file a screen repair claim."],
     "resolution": "Screen repair claims are handled same-day at uBreakiFix or in-store; cracked screens without protection can be repaired at a Verizon store — book an appointment."},
    {"device_family": "Samsung", "issue": "Battery drains too fast",
     "steps": ["Open Settings > Battery and device care and check the battery status.",
               "Put unused apps to sleep.",
               "Turn on Power saving mode.",
               "Update software from Settings > Software update."],
     "resolution": "Persistent drain with a healthy battery status points to an app loop — boot into Safe mode; if the drain stops, uninstall the last-downloaded apps. Otherwise book a service appointment."},
    {"device_family": "Samsung", "issue": "No service or cannot connect to the network",
     "steps": ["Check the coverage map for your address.",
               "Toggle Airplane mode on for 10 seconds, then off.",
               "Reset network settings: Settings > General management > Reset.",
               "Restart the phone."],
     "resolution": "If the network still does not appear, the SIM or eSIM profile may be stale — swap the SIM at a Verizon store or re-download the eSIM profile from My Verizon."},
    {"device_family": "Samsung", "issue": "5G speeds are slower than expected",
     "steps": ["Confirm your plan includes 5G Ultra Wideband access.",
               "Verify the phone shows 5G UW in the status bar when you are in a coverage area.",
               "Restart the phone to re-attach to the network."],
     "resolution": "Without the 5G UW indicator you are on nationwide 5G — that is expected outside Ultra Wideband areas; check the coverage map for your exact address."},
    {"device_family": "Google", "issue": "Battery drains too fast",
     "steps": ["Open Settings > Battery and check the estimated remaining time.",
               "Turn on Battery Saver.",
               "Check for rogue apps under Battery usage.",
               "Install the latest Android update."],
     "resolution": "If one app shows outsized battery usage, force stop and reinstall it; otherwise book a service appointment — Pixel batteries are covered under warranty for the first year."},
    {"device_family": "Google", "issue": "No service or cannot connect to the network",
     "steps": ["Check the coverage map for your address.",
               "Toggle Airplane mode, then restart the phone.",
               "Reset network settings from Settings > System > Reset options."],
     "resolution": "Still no service — the eSIM profile may need a refresh: delete and re-add it in My Verizon, or swap to a physical SIM at a store."},
    {"device_family": "Motorola", "issue": "Battery drains too fast",
     "steps": ["Open the Device Help app and run the battery check.",
               "Turn on Battery saver.",
               "Reduce screen brightness and timeout.",
               "Update the phone software."],
     "resolution": "Motorola's battery check flags degraded batteries; if the check says 'Replace', the battery needs service — a store technician can order the repair."},
    {"device_family": "Motorola", "issue": "Phone will not charge",
     "steps": ["Inspect the charging port for lint or damage.",
               "Try a different cable and wall adapter.",
               "Restart the phone while plugged in.",
               "Charge with the phone powered off for 30 minutes."],
     "resolution": "If the phone still will not charge on a known-good cable, the port or battery needs service — book a store appointment; charging issues from day one may qualify for warranty replacement."},
]


BENCHMARK_USERS = [
    {
        "email": "alice.j@test.com", "display_name": "Alice Johnson",
        "account_number": "8472-0913", "account_kind": "postpaid",
        "street": "4118 Meridian Ave N", "city": "Seattle", "state": "WA", "zip": "98103",
        "lines": [
            {"nickname": "Alice", "phone": "(206) 555-0181",
             "device": "apple-iphone-18-pro", "plan": "Simplicity Plan",
             "protection": "Verizon Mobile Protect", "usage": {"data_gb": "31.4", "hotspot_gb": "9.6"}},
            {"nickname": "Mike (partner line)", "phone": "(206) 555-0182",
             "device": "samsung-galaxy-s26", "plan": "Simplicity Plan",
             "protection": None, "usage": {"data_gb": "12.2", "hotspot_gb": "1.1"}},
        ],
        "bills": ["Jul 2026", "Aug 2026", "Sep 2026"],
        "autopay": True, "paper_free": True,
    },
    {
        "email": "bob.c@test.com", "display_name": "Bob Chen",
        "account_number": "5306-7788", "account_kind": "postpaid",
        "street": "1567 116th Ave NE", "city": "Bellevue", "state": "WA", "zip": "98004",
        "lines": [
            {"nickname": "Bob", "phone": "(425) 555-0293",
             "device": "google-pixel-11-pro", "plan": "Simplicity Plan",
             "protection": "Wireless Phone Protection", "usage": {"data_gb": "18.9", "hotspot_gb": "2.4"}},
            {"nickname": "Grandma Lin", "phone": "(425) 555-0294",
             "device": "motorola-moto-g-2026", "plan": "Simplicity Plan",
             "protection": None, "usage": {"data_gb": "2.7", "hotspot_gb": "0.2"}},
        ],
        "bills": ["Jul 2026", "Aug 2026", "Sep 2026"],
        "autopay": False, "paper_free": False,
        "pending_order": {"device": "samsung-galaxy-a17-5g", "status": "In transit",
                           "delivery_by": "Arriving by Thu, Oct 1", "color": "Navy Blue", "storage": "128 GB",
                           "term": "36", "placed_at": "2026-09-25"},
    },
    {
        "email": "carol.d@test.com", "display_name": "Carol Davis",
        "account_number": "1290-4523", "account_kind": "postpaid",
        "street": "2906 S 12th St", "city": "Tacoma", "state": "WA", "zip": "98405",
        "lines": [
            {"nickname": "Carol", "phone": "(253) 555-0356",
             "device": "apple-iphone-17e", "plan": "Simplicity Plan",
             "protection": None, "usage": {"data_gb": "8.8", "hotspot_gb": "3.9"}},
            {"nickname": "Tyler", "phone": "(253) 555-0357",
             "device": "motorola-razr-2026", "plan": "Simplicity Plan",
             "protection": "Verizon Mobile Protect", "usage": {"data_gb": "22.1", "hotspot_gb": "4.8"}},
            {"nickname": "Tablet line", "phone": "(253) 555-0358",
             "device": "google-pixel-10a", "plan": "Simplicity Plan",
             "protection": None, "usage": {"data_gb": "5.5", "hotspot_gb": "0.0"}},
        ],
        "bills": ["Jul 2026", "Aug 2026", "Sep 2026"],
        "autopay": False, "paper_free": False,
    },
    {
        "email": "dana.k@test.com", "display_name": "Dana Kim",
        "account_number": "7731-6620", "account_kind": "prepaid",
        "street": "825 164th Ave NE", "city": "Redmond", "state": "WA", "zip": "98052",
        "lines": [
            {"nickname": "Dana", "phone": "(425) 555-0467",
             "device": "samsung-galaxy-s26-ultra", "plan": "Unlimited Plus",
             "protection": None, "usage": {"data_gb": "26.4", "hotspot_gb": "7.2"}},
        ],
        "bills": ["Jul 2026", "Aug 2026", "Sep 2026"],
        "autopay": True, "paper_free": True, "prepaid_months": 11,
    },
]


def _fmt_money(value):
    return f"${float(value):,.2f}"


def _monthly_for(device, term):
    terms = device.terms_map()
    return terms.get(str(term)) or terms.get(term)


def plan_caps(plan):
    """Data allowances, never the dollar price of a plan."""
    data = {'Talk & Text': '0', '15 GB': '15'}.get(plan.name)
    hotspot = '15' if plan.name == '15 GB' else str(plan.hotspot_gb or 0)
    return data, hotspot


def bill_balance(bill):
    paid = sum((Decimal(p.amount) for p in Payment.query.filter_by(bill_id=bill.id)), Decimal('0'))
    return max(Decimal('0'), Decimal(bill.total) - paid)


def owns_confirmation(record, session_key):
    if record.user_id is not None:
        return current_user.is_authenticated and current_user.id == record.user_id
    return record.confirmation in session.get(session_key, [])


# ------------------------------------------------------------------- seed --

def seed_devices():
    if Device.query.count() > 0:
        return
    for row in _load('devices.json'):
        db.session.add(Device(
            slug=row['slug'], name=row['name'], brand=row['brand'],
            colors=json.dumps(row['colors']), storage=json.dumps(row['storage']),
            terms=json.dumps(row['terms']), full_price=row['full_price'],
            rating=row['rating'], reviews=row['reviews'],
            ship_window=row.get('ship_window'), promo=json.dumps(row.get('promo') or []),
            specs=json.dumps(row.get('specs') or {}),
            color_images=json.dumps(row.get('color_images') or {}),
            pdp_url=row.get('pdp_url')))


def seed_plans():
    if Plan.query.count() > 0:
        return
    plans = _load('plans.json')
    db.session.add(Plan(kind='simplicity', name='Simplicity Plan', monthly='30.00',
                        data_note='Unlimited 5G data, one price per line',
                        hotspot_gb=10,
                        features=json.dumps(plans['simplicity']['features']),
                        blurb=plans['simplicity']['note'], sort=1))
    for i, row in enumerate(plans['prepaid']['plans']):
        db.session.add(Plan(
            kind='prepaid', name=row['name'], monthly=f"{row['base']:.2f}",
            autopay_monthly=f"{row['autopay']:.2f}",
            first_month=f"{row['first_month']:.2f}",
            data_note=row['blurb'],
            hotspot_gb=25 if row['name'] == 'Unlimited Plus' else (
                5 if row['name'] == 'Unlimited' else None),
            features=json.dumps(row['features']),
            blurb=row['blurb'], sort=i + 2))


def seed_stores():
    if Store.query.count() > 0:
        return
    for row in _load('stores.json'):
        db.session.add(Store(
            code=row['store_code'], name=row['store_name'],
            business=row['business_name'], store_type=row['store_type'],
            retailer=row['retailer'], phone=row['phone'], street=row['street'],
            city=row['city'], state=row['state'], zip=row['zip'],
            hours=json.dumps(row['hours']), services=json.dumps(row['services']),
            appointments=1 if row['appointments'] else 0,
            fios=1 if row['fios'] else 0, pickup=1 if row['pickup'] else 0,
            locker=1 if row['locker'] else 0, cma=row['cma'],
            image_outside=row['image_outside'], image_inside=row['image_inside']))


def seed_content_pages():
    if ContentPage.query.count() > 0:
        return
    pages = _load('pages.json')
    titles = {
        'return_policy': 'Verizon Return Policy - 30-day returns and exchanges',
        'contact_us': 'Contact us',
        'network': 'Explore your network',
        'trade_in': 'Verizon trade-in program',
        'support_home': 'Verizon Support',
        'troubleshoot': "Let's troubleshoot your device.",
        'home': 'Verizon home',
        'stores_home': 'Find a Verizon store',
        'plans_home': 'Simplicity Plan: Unlimited data plan for one price per line',
        'prepaid_home': 'Verizon Prepaid plans',
    }
    for key, title in titles.items():
        blob = pages.get(key)
        if not blob:
            continue
        db.session.add(ContentPage(slug=key, title=title, body=blob['text']))


def seed_support_tables():
    if ProtectionPlan.query.count() == 0:
        for i, row in enumerate(PROTECTION_PLANS):
            db.session.add(ProtectionPlan(name=row['name'], monthly=row['monthly'],
                                          blurb=row['blurb'], sort=i))
    if TradeInQuote.query.count() == 0:
        sort = 0
        for dev, conds in sorted(TRADE_IN_MATRIX.items()):
            for cond, value in conds.items():
                db.session.add(TradeInQuote(device_name=dev, condition=cond,
                                            value=value, sort=sort))
                sort += 1
    if TroubleshootFlow.query.count() == 0:
        for i, flow in enumerate(TROUBLESHOOT_FLOWS):
            db.session.add(TroubleshootFlow(
                device_family=flow['device_family'], issue=flow['issue'],
                steps=json.dumps(flow['steps']), resolution=flow['resolution'], sort=i))


def seed_plan_rules():
    if PlanRule.query.count() > 0:
        return
    plans = _load('plans.json')
    sim = plans['simplicity']
    pre = plans['prepaid']
    rows = [
        ('simplicity_note', 'Price note', sim['note']),
        ('simplicity_hero', 'Hero offer',
         json.dumps({'headline': sim['hero']['headline'],
                     'price': sim['hero']['price'],
                     'details': sim['hero']['details']})),
        ('phone_options', 'Your phone, your way',
         json.dumps(sim['phone_options'])),
        ('autopay_rule', 'Auto Pay discount', pre['autopay_rule']),
        ('loyalty_rule', 'Loyalty discounts', pre['loyalty_rule']),
        ('multiline_rule', 'Multiline discount', pre['multiline_rule']),
        ('price_lock', '3-year price lock guarantee', pre['price_lock']),
        ('prepaid_promo', 'Prepaid device promo',
         'Get iPhone 16e for $349.99, plus an additional $100 in $10/mo '
         'service credits over 10 months on any Verizon Prepaid Unlimited '
         'plan. Offer ends 9/30/26 or while supplies last.'),
    ]
    for slug, title, body in rows:
        db.session.add(PlanRule(slug=slug, title=title, body=body))


def seed_city_index():
    if CityIndex.query.count() > 0:
        return
    for state, cities in _load('store_city_index.json').items():
        for city in cities:
            db.session.add(CityIndex(state=state, city=city))


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    for idx, spec in enumerate(BENCHMARK_USERS):
        user = User(
            email=spec['email'], display_name=spec['display_name'],
            password_hash=BENCHMARK_PASSWORD_HASH,
            account_number=spec['account_number'],
            account_kind=spec['account_kind'],
            street=spec['street'], city=spec['city'], state=spec['state'],
            zip=spec['zip'], created_at="2024-11-05",
            autopay=1 if spec.get('autopay') else 0,
            paper_free=1 if spec.get('paper_free') else 0)
        db.session.add(user)
        db.session.flush()
        plan_rows = {}
        for line_spec in spec['lines']:
            device = Device.query.filter_by(slug=line_spec['device']).first()
            plan = Plan.query.filter_by(name=line_spec['plan']).first()
            line = Line(user_id=user.id, nickname=line_spec['nickname'],
                        phone_number=line_spec['phone'],
                        device_id=device.id if device else None,
                        plan_id=plan.id, status='active', joined_at='2026-03-14')
            db.session.add(line)
            db.session.flush()
            usage = line_spec['usage']
            db.session.add(Usage(
                line_id=line.id, cycle='Sep 2026', data_gb=usage['data_gb'],
                data_cap_gb=plan_caps(plan)[0],
                hotspot_gb=usage['hotspot_gb'],
                hotspot_cap_gb=plan_caps(plan)[1],
                talk_min=210 + idx * 17, texts=880 + idx * 23))
        # bills: three periods, latest unpaid for postpaid accounts
        for b, period in enumerate(spec['bills']):
            monthly = _account_monthly(spec)
            protection = _account_protection(spec)
            device_pay = _account_device_payments(spec)
            taxes = round((monthly + protection + device_pay) * 0.187, 2)
            total = round(monthly + protection + device_pay + taxes, 2)
            is_last = b == len(spec['bills']) - 1
            due = (MIRROR_TODAY + timedelta(days=14 - (len(spec['bills']) - 1 - b) * 30)).isoformat()
            charges = []
            for line_spec in spec['lines']:
                charges.append({
                    "label": f"{line_spec['plan']} — {line_spec['nickname']}",
                    "category": "plan",
                    "amount": f"{_plan_charged(line_spec['plan'], spec):.2f}"})
                device = Device.query.filter_by(slug=line_spec['device']).first()
                if device and device.full_price and float(device.full_price.replace(',', '')) > 500:
                    charges.append({
                        "label": f"Device payment — {line_spec['nickname']}",
                        "category": "device", "amount": _monthly_for(device, '36')})
                if line_spec.get('protection'):
                    charges.append({
                        "label": f"{line_spec['protection']} — {line_spec['nickname']}",
                        "category": "protection",
                        "amount": next((p['monthly'] for p in PROTECTION_PLANS
                                        if p['name'] == line_spec['protection']), '0')})
            charges.append({"label": "Taxes, surcharges and fees",
                            "category": "taxes", "amount": f"{taxes:.2f}"})
            db.session.add(Bill(
                user_id=user.id, period=period, due_date=due,
                total=f"{total:.2f}",
                status='due' if is_last else 'paid',
                charges=json.dumps(charges)))
        if spec.get('pending_order'):
            po = spec['pending_order']
            device = Device.query.filter_by(slug=po['device']).first()
            monthly_dev = float(_monthly_for(device, po['term']))
            db.session.add(Order(
                user_id=user.id, confirmation=f"VZW{200000 + idx * 7 + 31}",
                status=po['status'], placed_at=po['placed_at'],
                delivery_by=po['delivery_by'],
                items=json.dumps([{
                    "device": device.name, "slug": device.slug,
                    "color": po['color'], "storage": po['storage'],
                    "term": po['term'],
                    "monthly": f"{monthly_dev:.2f}",
                    "full": device.full_price, "plan": "Simplicity Plan",
                    "protection": None}]),
                total_today="0.00",
                total_monthly=f"{monthly_dev + 30.00:.2f}",
                name=user.display_name, email=user.email, street=user.street,
                city=user.city, state=user.state, zip=user.zip))


def _plan_monthly(plan_name):
    plan = Plan.query.filter_by(name=plan_name).first()
    if not plan:
        return 30.0
    return float(plan.monthly)


def _plan_charged(plan_name, spec):
    """Prepaid lines enrolled in Auto Pay are billed the Auto Pay price."""
    plan = Plan.query.filter_by(name=plan_name).first()
    if not plan:
        return 30.0
    if plan.kind == 'prepaid' and spec.get('autopay') and plan.autopay_monthly:
        return float(plan.autopay_monthly)
    return float(plan.monthly)


def _account_monthly(spec):
    total = 0.0
    for line_spec in spec['lines']:
        total += _plan_charged(line_spec['plan'], spec)
    return total


def _account_protection(spec):
    total = 0.0
    for line_spec in spec['lines']:
        if line_spec.get('protection'):
            total += float(next(
                (p['monthly'] for p in PROTECTION_PLANS
                 if p['name'] == line_spec['protection']), '0'))
    return total


def _account_device_payments(spec):
    total = 0.0
    for line_spec in spec['lines']:
        device = Device.query.filter_by(slug=line_spec['device']).first()
        if device and device.full_price and float(device.full_price.replace(',', '')) > 500:
            total += float(_monthly_for(device, '36'))
    return total


def main():
    """Import-and-seed entry point (deterministic, idempotent)."""
    with app.app_context():
        db.create_all()
        seed_devices()
        seed_plans()
        seed_stores()
        seed_content_pages()
        seed_support_tables()
        seed_plan_rules()
        seed_city_index()
        db.session.commit()
        seed_benchmark_users()
        db.session.commit()


# ------------------------------------------------------------------ routes --

@app.route('/_health')
def health():
    counts = {
        'devices': Device.query.count(),
        'plans': Plan.query.count(),
        'stores': Store.query.count(),
        'content_pages': ContentPage.query.count(),
        'protection_plans': ProtectionPlan.query.count(),
        'trade_in_quotes': TradeInQuote.query.count(),
        'troubleshoot_flows': TroubleshootFlow.query.count(),
        'users': User.query.count(),
        'lines': Line.query.count(),
        'bills': Bill.query.count(),
        'usage': Usage.query.count(),
        'orders': Order.query.count(),
    }
    ok = all(counts.values())
    return {'ok': bool(ok), 'site': SITE_NAME, **counts}


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _nav_stats():
    return {
        'brands': sorted({d.brand for d in Device.query}),
        'device_count': Device.query.count(),
        'store_count': Store.query.count(),
    }


@app.route('/')
def home():
    devices = Device.query.order_by(Device.id).all()
    spotlight = [d for d in devices if d.slug in (
        'apple-iphone-18-pro', 'samsung-galaxy-s26-ultra', 'google-pixel-11-pro',
        'motorola-razr-plus-2026', 'apple-iphone-17e', 'samsung-galaxy-z-fold8')]
    return render_template('home.html', spotlight=spotlight, **_nav_stats())


# ------------------------------------------------------------------- plans --

@app.route('/plans/')
@app.route('/plans/unlimited/')
def plans_simplicity():
    rule = {r.slug: r for r in PlanRule.query}
    sim = {
        'note': rule['simplicity_note'].body,
        'features': json.loads(
            Plan.query.filter_by(kind='simplicity').first().features),
        'max_lines': 12,
        'hero': json.loads(rule['simplicity_hero'].body),
        'phone_options': json.loads(rule['phone_options'].body),
    }
    lines = request.args.get('lines', 1, type=int)
    lines = max(1, min(4, lines))
    return render_template('plans_simplicity.html', sim=sim, lines=lines,
                           monthly=30 * lines, **_nav_stats())


@app.route('/prepaid/')
@app.route('/prepaid/plans/')
def plans_prepaid():
    prepaid = Plan.query.filter_by(kind='prepaid').order_by(Plan.sort).all()
    rule = {r.slug: r for r in PlanRule.query}
    rules = {
        'autopay_rule': rule['autopay_rule'].body,
        'loyalty_rule': rule['loyalty_rule'].body,
        'multiline_rule': rule['multiline_rule'].body,
        'price_lock': rule['price_lock'].body,
        'promo': rule['prepaid_promo'].body,
    }
    return render_template('plans_prepaid.html', prepaid=prepaid,
                           rules=rules, **_nav_stats())


# ----------------------------------------------------------------- devices --

@app.route('/smartphones/')
def smartphones():
    brand = request.args.get('brand', '')
    sort = request.args.get('sort', 'featured')
    query = Device.query
    if brand:
        query = query.filter_by(brand=brand)
    def _price(d):
        try:
            return float((d.full_price or '99999').replace(',', ''))
        except ValueError:
            return 99999.0
    if sort == 'price-asc':
        devices = query.order_by(Device.id).all()
        devices.sort(key=_price)
    elif sort == 'price-desc':
        devices = query.order_by(Device.id).all()
        devices.sort(key=lambda d: -_price(d))
    else:
        devices = query.order_by(Device.id).all()
    return render_template('smartphones.html', devices=devices, brand=brand,
                           sort=sort, **_nav_stats())


@app.route('/smartphones/<slug>/')
def device_detail(slug):
    device = Device.query.filter_by(slug=slug).first_or_404()
    specs = device.specs_map()
    compare_names = sorted({n for section in specs.values() for n in section})
    for name in compare_names:
        related = Device.query.filter_by(name=name).first()
        if related and related.rating:
            specs.setdefault('Reviews', {})[name] = f'{related.rating} out of 5 ({related.reviews} reviews)'
    compare = {name: {k: v.get(name) for k, v in specs.items()} for name in compare_names}
    protections = ProtectionPlan.query.order_by(ProtectionPlan.sort).all()
    tradeins = [q for q in TradeInQuote.query.order_by(TradeInQuote.sort)
                if q.device_name == device.name]
    return render_template('device_detail.html', device=device, specs=specs,
                           compare=compare, protections=protections,
                           tradeins=tradeins, **_nav_stats())


@app.route('/smartphones/<slug>/configure', methods=['GET', 'POST'])
def device_configure(slug):
    device = Device.query.filter_by(slug=slug).first_or_404()
    colors = device.colors_list()
    storage = device.storage_list() or ['Single capacity']
    terms = device.terms_map()
    if not terms and not device.full_price:
        flash('Pricing is currently unavailable for this device.')
        return redirect(url_for('device_detail', slug=slug))
    protections = ProtectionPlan.query.order_by(ProtectionPlan.sort).all()
    plans = Plan.query.order_by(Plan.sort).all()
    if request.method == 'POST':
        color = request.form.get('color') or (colors[0] if colors else 'Default')
        storage_pick = request.form.get('storage') or storage[0]
        term = request.form.get('term') or '36'
        protection = request.form.get('protection') or ''
        plan_id = request.form.get('plan') or ''
        if (color not in (colors or ['Default']) or storage_pick not in storage
                or term not in set(terms) | ({'full'} if device.full_price else set())
                or protection not in {p.name for p in protections} | {''}
                or plan_id not in {str(p.id) for p in plans} | {''}):
            flash('Choose an available color, storage, payment term and plan.')
            return redirect(url_for('device_configure', slug=slug))
        cart = load_cart()
        cart.append({'slug': slug, 'name': device.name, 'color': color,
                     'storage': storage_pick, 'term': term,
                     'monthly': _monthly_for(device, term),
                     'full': device.full_price, 'protection': protection,
                     'plan_id': plan_id, 'qty': 1})
        save_cart(cart)
        flash(f"Added {device.name} ({color}) to your cart.")
        return redirect(url_for('cart_view'))
    return render_template('device_configure.html', device=device, colors=colors,
                           storage=storage, terms=terms, protections=protections,
                           plans=plans, **_nav_stats())


@app.route('/cart/')
def cart_view():
    cart = load_cart()
    plan_names = {p.id: p.name for p in Plan.query}
    plan_monthly = {p.id: p.monthly for p in Plan.query}
    protection_map = {p.name: p.monthly for p in ProtectionPlan.query}
    total_monthly = 0.0
    total_today = 0.0
    item_monthly = []
    for item in cart:
        monthly = 0.0
        if item.get('monthly'):
            monthly += float(item['monthly'])
        if item.get('term') == 'full':
            total_today += float(item['full'].replace(',', ''))
        if item.get('protection'):
            monthly += float(protection_map.get(item['protection'], 0))
        if item.get('plan_id'):
            monthly += float(plan_monthly.get(int(item['plan_id']), 0))
        item_monthly.append(f"{monthly:.2f}")
        total_monthly += monthly
    return render_template('cart.html', cart=cart, plan_names=plan_names,
                           item_monthly=item_monthly,
                           total_monthly=f"{total_monthly:.2f}",
                           total_today=f"{total_today:.2f}", **_nav_stats())


@app.route('/cart/remove/<int:index>', methods=['POST'])
def cart_remove(index):
    cart = load_cart()
    if 0 <= index < len(cart):
        cart.pop(index)
        save_cart(cart)
        flash('Item removed from your cart.')
    return redirect(url_for('cart_view'))


@app.route('/checkout/', methods=['GET', 'POST'])
def checkout():
    cart = load_cart()
    if not cart:
        flash('Your cart is empty.')
        return redirect(url_for('smartphones'))
    if request.method == 'POST':
        if (not all(request.form.get(k, '').strip() for k in ('name', 'email', 'street', 'city', 'state', 'zip'))
                or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', request.form.get('email', ''))
                or not re.fullmatch(r'\d{5}(?:-\d{4})?', request.form.get('zip', ''))):
            flash('Enter a complete shipping address and valid email and ZIP code.')
            return redirect(url_for('checkout'))
        confirmation = 'VZW' + str(secrets.randbelow(900000000000) + 100000000000)
        protection_map = {p.name: p.monthly for p in ProtectionPlan.query}
        plan_map = {p.id: p for p in Plan.query}
        total_monthly = 0.0
        total_today = Decimal('0')
        items = []
        for item in cart:
            if item['term'] == 'full':
                total_today += Decimal(item['full'].replace(',', ''))
            device_monthly = float(item.get('monthly') or 0)
            protection_monthly = 0.0
            if item.get('protection'):
                protection_monthly = float(protection_map.get(item['protection'], 0))
            plan = plan_map.get(int(item.get('plan_id') or 0))
            plan_monthly = float(plan.monthly) if plan else 0.0
            monthly = device_monthly + protection_monthly + plan_monthly
            total_monthly += monthly
            items.append({
                'device': item['name'], 'slug': item['slug'], 'color': item['color'],
                'storage': item['storage'], 'term': item['term'],
                'monthly': f"{monthly:.2f}", 'full': item['full'],
                'protection': item.get('protection'),
                'protection_monthly': f"{protection_monthly:.2f}",
                'plan': plan.name if plan else None,
                'plan_monthly': f"{plan_monthly:.2f}"})
        order = Order(
            user_id=current_user.id if current_user.is_authenticated else None,
            confirmation=confirmation, status='processing',
            placed_at=MIRROR_TODAY.isoformat(),
            delivery_by='Ships between ' + (MIRROR_TODAY + timedelta(days=1)).strftime('%a, %b %-d')
                         + ' - ' + (MIRROR_TODAY + timedelta(days=10)).strftime('%a, %b %-d'),
            items=json.dumps(items), total_today=f'{total_today:.2f}',
            total_monthly=f"{total_monthly:.2f}",
            name=request.form.get('name'), email=request.form.get('email'),
            street=request.form.get('street'), city=request.form.get('city'),
            state=request.form.get('state'), zip=request.form.get('zip'))
        db.session.add(order)
        db.session.commit()
        save_cart([])
        session['guest_orders'] = session.get('guest_orders', []) + [confirmation]
        return redirect(url_for('order_confirmation', confirmation=confirmation))
    return render_template('checkout.html', cart=cart, **_nav_stats())


@app.route('/order/<confirmation>/')
def order_confirmation(confirmation):
    order = Order.query.filter_by(confirmation=confirmation).first_or_404()
    if not owns_confirmation(order, 'guest_orders'):
        abort(403)
    return render_template('order_confirmation.html', order=order, **_nav_stats())


# ---------------------------------------------------------------- trade-in --

@app.route('/trade-in/')
def trade_in_home():
    page = ContentPage.query.filter_by(slug='trade_in').first()
    faqs = _trade_in_faqs()
    return render_template('trade_in.html', page=page, faqs=faqs, **_nav_stats())


def _trade_in_faqs():
    return [
        ("How do I clear personal information and content from my device before trading it in?",
         "Back up your content, then sign out of your accounts and run a factory reset so "
         "no personal data remains on the device."),
        ("What types of devices can I trade in?",
         "Phones, tablets, smartwatches and other connected devices — Apple, Samsung, "
         "Google, Motorola and more."),
        ("What trade-in promotions does Verizon have right now?",
         "Promotions change often; the estimator on this page always shows the value your "
         "device qualifies for today."),
        ("How do I check my device's IMEI?",
         "Dial *#06# on the device, or check Settings > About phone."),
    ]


@app.route('/trade-in/estimate/', methods=['GET', 'POST'])
def trade_in_estimate():
    devices = sorted({q.device_name for q in TradeInQuote.query})
    conditions = ['Mint', 'Good', 'Cracked']
    quote = None
    device_name = request.form.get('device') or request.args.get('device')
    condition = request.form.get('condition') or request.args.get('condition')
    if device_name and condition:
        quote = TradeInQuote.query.filter_by(device_name=device_name,
                                            condition=condition).first()
    return render_template('trade_in_estimate.html', devices=devices,
                           conditions=conditions, quote=quote,
                           device_name=device_name, condition=condition,
                           **_nav_stats())


# ------------------------------------------------------------------ stores --

STATE_NAMES = {
    "washington": "Washington", "california": "California", "new-york": "New York",
    "texas": "Texas", "illinois": "Illinois", "florida": "Florida",
    "oregon": "Oregon", "colorado": "Colorado", "massachusetts": "Massachusetts",
    "arizona": "Arizona",
}


@app.route('/stores/')
def stores_home():
    by_state = {}
    for st in STATE_NAMES:
        by_state[st] = sorted({c.city for c in CityIndex.query.filter_by(state=st)})
    return render_template('stores_home.html', states=STATE_NAMES,
                           by_state=by_state, **_nav_stats())


def _state_abbrs():
    return {
        "washington": "WA", "california": "CA", "new-york": "NY", "texas": "TX",
        "illinois": "IL", "florida": "FL", "oregon": "OR", "colorado": "CO",
        "massachusetts": "MA", "arizona": "AZ",
    }


@app.route('/stores/<state>/')
def stores_state(state):
    state = state.lower()
    if state not in STATE_NAMES:
        abort(404)
    cities = sorted({c.city for c in CityIndex.query.filter_by(state=state)})
    abbr = _state_abbrs()[state]
    stores = Store.query.filter_by(state=abbr).order_by(Store.city, Store.name).all()
    return render_template('stores_state.html', state=state,
                           state_name=STATE_NAMES[state], cities=cities,
                           stores=stores, **_nav_stats())


@app.route('/stores/<state>/<city>/')
def stores_city(state, city):
    state = state.lower()
    if state not in STATE_NAMES:
        abort(404)
    city_label = city.replace('-', ' ').title()
    abbr = _state_abbrs()[state]
    stores = Store.query.filter_by(state=abbr, city=city_label) \
        .order_by(Store.name).all()
    return render_template('stores_city.html', state=state,
                           state_name=STATE_NAMES[state], city_slug=city,
                           city=city_label, stores=stores, **_nav_stats())


@app.route('/store/<code>/')
def store_detail(code):
    store = Store.query.filter_by(code=code).first_or_404()
    abbr_to_slug = {abbr: slug for slug, abbr in _state_abbrs().items()}
    state_slug = abbr_to_slug.get(store.state, store.state.lower())
    city_slug = store.city.lower().replace(' ', '-')
    return render_template('store_detail.html', store=store,
                           state_slug=state_slug, city_slug=city_slug,
                           **_nav_stats())


@app.route('/store/<code>/appointment/', methods=['GET', 'POST'])
def store_appointment(code):
    store = Store.query.filter_by(code=code).first_or_404()
    topics = ['New line & device purchase', 'Device trade-in',
              'Billing & payments', 'Technical support', 'Fios / Home Internet']
    if not store.appointments:
        abort(404)
    if request.method == 'POST':
        try:
            requested_date = date.fromisoformat(request.form.get('date', ''))
        except ValueError:
            requested_date = None
        if (not requested_date or requested_date < MIRROR_TODAY
                or request.form.get('time') not in ('10:00 AM', '11:00 AM', '01:00 PM', '02:00 PM', '03:00 PM')
                or request.form.get('topic') not in topics
                or not all(request.form.get(k, '').strip() for k in ('name', 'email', 'phone'))
                or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', request.form.get('email', ''))):
            flash('Choose a valid date, time and topic and enter your contact details.')
            return redirect(url_for('store_appointment', code=code))
        confirmation = 'APT' + str(secrets.randbelow(900000000000) + 100000000000)
        db.session.add(Appointment(
            store_id=store.id,
            user_id=current_user.id if current_user.is_authenticated else None,
            name=request.form.get('name'), email=request.form.get('email'),
            phone=request.form.get('phone'), topic=request.form.get('topic'),
            appt_date=request.form.get('date'), appt_time=request.form.get('time'),
            confirmation=confirmation))
        db.session.commit()
        session['guest_appointments'] = session.get('guest_appointments', []) + [confirmation]
        return redirect(url_for('appointment_confirmation', confirmation=confirmation))
    return render_template('store_appointment.html', store=store, topics=topics,
                           **_nav_stats())


@app.route('/appointment/<confirmation>/')
def appointment_confirmation(confirmation):
    appt = Appointment.query.filter_by(confirmation=confirmation).first_or_404()
    if not owns_confirmation(appt, 'guest_appointments'):
        abort(403)
    return render_template('appointment_confirmation.html', appt=appt, **_nav_stats())


# ----------------------------------------------------------------- support --

@app.route('/support/')
def support_home():
    page = ContentPage.query.filter_by(slug='support_home').first()
    return render_template('support_home.html', page=page, **_nav_stats())


@app.route('/support/<slug>/')
def support_page(slug):
    page = ContentPage.query.filter_by(slug=slug.replace('-', '_')).first_or_404()
    return render_template('support_page.html', page=page,
                           titles={
                               'return_policy': 'Return policy',
                               'contact_us': 'Contact us',
                               'network': 'Network support',
                           }, **_nav_stats())


@app.route('/support/troubleshoot/', methods=['GET', 'POST'])
def troubleshoot():
    families = sorted({f.device_family for f in TroubleshootFlow.query})
    issues = sorted({f.issue for f in TroubleshootFlow.query})
    family = request.values.get('family')
    issue = request.values.get('issue')
    flow = None
    if family and issue:
        flow = TroubleshootFlow.query.filter_by(device_family=family,
                                                issue=issue).first()
    elif issue:
        flow = TroubleshootFlow.query.filter_by(issue=issue).first()
    return render_template('troubleshoot.html', families=families, issues=issues,
                           family=family, issue=issue, flow=flow, **_nav_stats())


# ------------------------------------------------------------- my verizon --

@app.route('/account/login', methods=['GET', 'POST'])
def account_login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email', '').strip().lower()).first()
        if user and user.check_password(request.form.get('password', '')):
            login_user(user)
            return redirect(url_for('account_overview'))
        flash('Invalid email or password.')
    return render_template('login.html', **_nav_stats())


@app.route('/account/register', methods=['GET', 'POST'])
def account_register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if (not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)
                or not request.form.get('name', '').strip() or len(request.form.get('password', '')) < 8):
            flash('Enter your name, a valid email and a password of at least 8 characters.')
        elif User.query.filter_by(email=email).first():
            flash('An account with that email already exists.')
        else:
            user = User(
                email=email, display_name=request.form.get('name'),
                password_hash=bcrypt.generate_password_hash(request.form['password']).decode(),
                account_number=f"{random.randrange(10000000, 99999999)}",
                street=request.form.get('street'),
                city=request.form.get('city'), state=request.form.get('state'),
                zip=request.form.get('zip'), created_at=MIRROR_TODAY.isoformat())
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('account_overview'))
    return render_template('register.html', **_nav_stats())


@app.route('/account/logout')
@login_required
def account_logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/account/')
@login_required
def account_overview():
    lines = Line.query.filter_by(user_id=current_user.id).all()
    usages = {u.line_id: u for u in Usage.query}
    bill = Bill.query.filter_by(user_id=current_user.id) \
        .order_by(Bill.id.desc()).first()
    orders = Order.query.filter_by(user_id=current_user.id) \
        .order_by(Order.id.desc()).all()
    payments = Payment.query.filter_by(user_id=current_user.id) \
        .order_by(Payment.id.desc()).all()
    return render_template('account_overview.html', lines=lines, usages=usages,
                           bill=bill, orders=orders, payments=payments,
                           autopay=bool(current_user.autopay), **_nav_stats())


@app.route('/account/bills/')
@login_required
def account_bills():
    bills = Bill.query.filter_by(user_id=current_user.id) \
        .order_by(Bill.id.desc()).all()
    return render_template('bills.html', bills=bills, **_nav_stats())


@app.route('/account/bills/<int:bill_id>/')
@login_required
def bill_detail(bill_id):
    bill = Bill.query.filter_by(id=bill_id, user_id=current_user.id).first_or_404()
    lines = {l.id: l for l in Line.query.filter_by(user_id=current_user.id)}
    payments = Payment.query.filter_by(bill_id=bill.id).all()
    return render_template('bill_detail.html', bill=bill, lines=lines,
                           payments=payments, **_nav_stats())


@app.route('/account/pay/', methods=['GET', 'POST'])
@login_required
def account_pay():
    bill = Bill.query.filter_by(user_id=current_user.id) \
        .filter(Bill.status != 'paid').order_by(Bill.id.desc()).first()
    remaining = bill_balance(bill) if bill else Decimal('0')
    methods = ('Card ending 4242', 'Bank account (ACH ending 8891)', 'Verizon Visa Card ending 0057')
    if request.method == 'POST':
        try:
            amount = Decimal(request.form.get('amount', ''))
            valid = amount.is_finite() and amount > 0 and amount <= remaining and amount == amount.quantize(Decimal('0.01'))
        except InvalidOperation:
            valid = False
        if not bill or not valid or request.form.get('method') not in methods:
            flash('Enter a positive amount no greater than the outstanding balance and choose a payment method.')
            return redirect(url_for('account_pay'))
        confirmation = 'PMT' + str(secrets.randbelow(900000000000) + 100000000000)
        db.session.add(Payment(user_id=current_user.id, bill_id=bill.id,
            amount=f'{amount:.2f}', method=request.form['method'],
            confirmation=confirmation, paid_at=MIRROR_TODAY.isoformat()))
        bill.status = 'paid' if amount == remaining else 'partial'
        db.session.commit()
        return redirect(url_for('payment_confirmation', confirmation=confirmation))
    return render_template('pay.html', bill=bill, remaining=f'{remaining:.2f}', **_nav_stats())


@app.route('/payment/<confirmation>/')
@login_required
def payment_confirmation(confirmation):
    payment = Payment.query.filter_by(confirmation=confirmation,
                                      user_id=current_user.id).first_or_404()
    return render_template('payment_confirmation.html', payment=payment, **_nav_stats())


@app.route('/account/autopay/', methods=['GET', 'POST'])
@login_required
def account_autopay():
    if request.method == 'POST':
        current_user.autopay = 1 if request.form.get('autopay') == 'on' else 0
        current_user.paper_free = 1 if request.form.get('paper_free') == 'on' else 0
        db.session.commit()
        flash('Auto Pay and billing preferences updated.'
              if request.form.get('autopay') == 'on' or request.form.get('paper_free') == 'on'
              else 'Auto Pay has been turned off.')
        return redirect(url_for('account_overview'))
    return render_template('autopay.html', autopay=bool(current_user.autopay),
                           paper_free=bool(current_user.paper_free), **_nav_stats())


@app.route('/account/usage/')
@login_required
def account_usage():
    lines = Line.query.filter_by(user_id=current_user.id).all()
    usages = {u.line_id: u for u in Usage.query}
    return render_template('usage.html', lines=lines, usages=usages, **_nav_stats())


@app.route('/account/lines/<int:line_id>/change-plan', methods=['GET', 'POST'])
@login_required
def change_plan(line_id):
    line = Line.query.filter_by(id=line_id, user_id=current_user.id).first_or_404()
    plans = Plan.query.order_by(Plan.sort).all()
    if request.method == 'POST':
        plan = db.session.get(Plan, request.form.get('plan', type=int))
        if plan:
            line.plan_id = plan.id
            usage = Usage.query.filter_by(line_id=line.id).first()
            if usage:
                usage.data_cap_gb, usage.hotspot_cap_gb = plan_caps(plan)
            db.session.commit()
            flash(f"Plan for {line.nickname} changed to {plan.name}.")
            return redirect(url_for('account_overview'))
    return render_template('change_plan.html', line=line, plans=plans, **_nav_stats())


@app.route('/account/add-line/', methods=['GET', 'POST'])
@login_required
def add_line():
    devices = Device.query.order_by(Device.id).all()
    plans = Plan.query.order_by(Plan.sort).all()
    if request.method == 'POST':
        device = db.session.get(Device, request.form.get('device', type=int))
        plan = db.session.get(Plan, request.form.get('plan', type=int))
        nickname = request.form.get('nickname', '').strip()
        if not device or not plan or not nickname:
            flash('Choose a device, a plan and a line name.')
            return redirect(url_for('add_line'))
        line = Line(user_id=current_user.id, nickname=nickname,
                    phone_number=f"(206) 555-{random.randrange(1000, 9999)}",
                    device_id=device.id, plan_id=plan.id,
                    status='activating', joined_at=MIRROR_TODAY.isoformat())
        db.session.add(line)
        db.session.flush()
        db.session.add(Usage(line_id=line.id, cycle='Sep 2026', data_gb='0.0',
                             data_cap_gb=plan_caps(plan)[0],
                             hotspot_gb='0.0',
                             hotspot_cap_gb=plan_caps(plan)[1],
                             talk_min=0, texts=0))
        db.session.commit()
        flash(f"New line added for {nickname} with {plan.name}.")
        return redirect(url_for('account_overview'))
    return render_template('add_line.html', devices=devices, plans=plans,
                           **_nav_stats())


@app.route('/account/orders/')
@login_required
def account_orders():
    orders = Order.query.filter_by(user_id=current_user.id) \
        .order_by(Order.id.desc()).all()
    return render_template('orders.html', orders=orders, **_nav_stats())


@app.route('/account/orders/<confirmation>/')
@login_required
def account_order_detail(confirmation):
    order = Order.query.filter_by(confirmation=confirmation,
                                   user_id=current_user.id).first_or_404()
    return render_template('order_confirmation.html', order=order,
                           my_verizon=True, **_nav_stats())


@app.errorhandler(404)
def not_found(_error):
    return render_template('404.html', **_nav_stats()), 404


# Module-level seed: runs at every container boot and every /reset/verizon
# respawn; each seed function is gated, so a populated DB is a no-op.
with app.app_context():
    db.create_all()
    seed_devices()
    seed_plans()
    seed_stores()
    seed_content_pages()
    seed_support_tables()
    seed_plan_rules()
    seed_city_index()
    db.session.commit()
    seed_benchmark_users()
    db.session.commit()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 40132))
    app.run(host='0.0.0.0', port=port, debug=False)
