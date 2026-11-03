#!/usr/bin/env python3
"""usps — a WebHarbor mirror of https://www.usps.com/

Flask + SQLite mirror of the U.S. Postal Service covering its public
mail-and-ship experience: the Retail Postage Price Calculator (domestic
First-Class Mail letters/flats/postcards and the Priority Mail Express /
Priority Mail / Ground Advantage / Media Mail retail zone grids, all from
the Notice 123 price list), package tracking with scan histories, the
Click-N-Ship label wizard, carrier pickup scheduling, the Find USPS
Locations directory (Post Offices from the official Postmaster Finder
database), PO Box fees and reservations, The Postal Store (real stamp
catalog with images), Change of Address / Hold Mail requests,
international country listings (IMM prohibitions/restrictions with real
price groups), insurance & claims, the newsroom, and USPS.com accounts.

Content comes from the tracked source_data/*.json snapshots captured from
the upstream sites on 2026-09-28; the SQLite seed is
materialized deterministically at image build time (PYTHONHASHSEED=0).
"""
import hashlib
import math
from urllib.parse import urlsplit
import json
import os
import re
import secrets
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("USPS_SECRET_KEY") or "webharbor-usps-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'USPS_DB_URI', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'usps.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to access your account.'
csrf = CSRFProtect(app)

# The mirror is a frozen snapshot of the upstream site taken 2026-09-28.
MIRROR_TODAY = date(2026, 9, 28)
MIRROR_TS = "2026-09-28 12:00"
SITE_NAME = "usps"
# bcrypt hash of 'TestPass123!' — frozen so the seed DB is byte-reproducible.
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')
# Identity-validation fee USPS charges for online Change of Address
# requests: $1.25 on the live manage/forward.htm page, in both Wayback
# snapshots (2026-09-04 / 09-19) and in this mirror's own captured
# source_data/pages.json copy (reviewer F-4: the previously rendered $1.05
# contradicted all three).
COA_IDENTITY_FEE = 1.25
# Dana's seeded August 2026 request keeps the fee charged when it was
# filed; frozen as a literal so the seed DB stays byte-identical to the
# frozen review contract (only new requests charge the current fee).
COA_SEED_FEE_FROZEN = 1.05

SOURCE = os.path.join(BASE_DIR, 'source_data')


def _load(name):
    with open(os.path.join(SOURCE, name), encoding='utf-8') as f:
        return json.load(f)


# ------------------------------------------------------------------ models --

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(60), unique=True, nullable=False)
    display_name = db.Column(db.String(120))
    password_hash = db.Column(db.String(120), nullable=False)
    street = db.Column(db.String(120))
    city = db.Column(db.String(60))
    state = db.Column(db.String(20))
    zip5 = db.Column(db.String(10))
    phone = db.Column(db.String(30))
    created_at = db.Column(db.String(10))


class ContentPage(db.Model):
    __tablename__ = 'content_pages'
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(200), unique=True, nullable=False)
    section = db.Column(db.String(40))
    title = db.Column(db.String(200))
    meta_description = db.Column(db.Text)
    headline = db.Column(db.String(200))
    lead = db.Column(db.Text)
    hero_image = db.Column(db.String(250))
    body = db.Column(db.Text)  # JSON sections


class NewsArticle(db.Model):
    __tablename__ = 'news_articles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    kind = db.Column(db.String(20))  # release | alert
    title = db.Column(db.String(250))
    clean_title = db.Column(db.String(250))
    date = db.Column(db.String(10))
    release_type = db.Column(db.String(40))
    body = db.Column(db.Text)  # JSON paragraphs
    images = db.Column(db.Text)  # JSON [{path, alt}]
    source_url = db.Column(db.String(250))


class Rate(db.Model):
    """One price cell of a Notice 123 retail grid."""
    __tablename__ = 'rates'
    id = db.Column(db.Integer, primary_key=True)
    table_code = db.Column(db.String(50), nullable=False)
    weight = db.Column(db.Float, nullable=False)
    weight_hi = db.Column(db.Float)
    col = db.Column(db.Integer, nullable=False)
    col_hi = db.Column(db.Integer)
    col_label = db.Column(db.String(40))
    price = db.Column(db.Float, nullable=False)


class FlatRateItem(db.Model):
    __tablename__ = 'flat_rate_items'
    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(10))  # domestic | intl
    service = db.Column(db.String(60))
    label = db.Column(db.String(120))
    size = db.Column(db.String(200))
    group_label = db.Column(db.String(60))
    group = db.Column(db.Integer)
    price = db.Column(db.Float)


class ExtraService(db.Model):
    __tablename__ = 'extra_services'
    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(10))  # domestic | intl
    category = db.Column(db.String(60))  # Insurance, Certified Mail, ...
    label = db.Column(db.String(200))
    price = db.Column(db.Float)
    price_lo = db.Column(db.Float)
    price_hi = db.Column(db.Float)


class PoBoxFee(db.Model):
    __tablename__ = 'po_box_fees'
    id = db.Column(db.Integer, primary_key=True)
    schedule = db.Column(db.String(30))  # competitive_6mo ...
    size_label = db.Column(db.String(60))
    fee_group = db.Column(db.String(20), nullable=False)
    fee = db.Column(db.Float)


class ServiceInfo(db.Model):
    """Marketing/service summary rows (Quick Tools + ship pages)."""
    __tablename__ = 'service_infos'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(80))
    family = db.Column(db.String(40))
    summary = db.Column(db.Text)
    hero_image = db.Column(db.String(250))
    page_path = db.Column(db.String(200))


class PostOffice(db.Model):
    __tablename__ = 'post_offices'
    id = db.Column(db.Integer, primary_key=True)
    po_key = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(100))
    city = db.Column(db.String(60))
    state = db.Column(db.String(20))
    zip5 = db.Column(db.String(5))
    county = db.Column(db.String(60))
    est_date = db.Column(db.String(10))
    discont_date = db.Column(db.String(10))
    address = db.Column(db.String(140))
    phone = db.Column(db.String(20))
    hours = db.Column(db.Text)  # JSON
    services = db.Column(db.Text)  # JSON list
    fee_group = db.Column(db.String(20))  # PO box fee schedule group
    has_po_boxes = db.Column(db.Boolean, default=False)
    postmaster = db.Column(db.String(100))
    postmaster_since = db.Column(db.String(10))


class Postmaster(db.Model):
    __tablename__ = 'postmasters'
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(60))
    state = db.Column(db.String(20))
    post_office = db.Column(db.String(100))
    name = db.Column(db.String(100))
    title = db.Column(db.String(60))
    date = db.Column(db.String(20))
    current = db.Column(db.Boolean, default=False)


class CountryInfo(db.Model):
    __tablename__ = 'country_info'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100))
    pmei_group = db.Column(db.String(10))
    pmei_max_lbs = db.Column(db.String(10))
    pmi_group = db.Column(db.String(10))
    pmi_max_lbs = db.Column(db.String(10))
    pmi_frb_group = db.Column(db.String(10))
    fcmi_group = db.Column(db.String(10))
    fcpis_group = db.Column(db.String(10))
    prohibitions = db.Column(db.Text)  # JSON list
    restrictions = db.Column(db.Text)  # JSON list
    observations = db.Column(db.Text)  # JSON list
    services = db.Column(db.Text)  # JSON dict
    source_url = db.Column(db.String(250))


class StoreProduct(db.Model):
    __tablename__ = 'store_products'
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(20), unique=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    name = db.Column(db.String(250))
    category = db.Column(db.String(40))
    price = db.Column(db.Float)
    description = db.Column(db.Text)
    image = db.Column(db.String(250))
    gallery = db.Column(db.Text)  # JSON list


class StoreOrder(db.Model):
    __tablename__ = 'store_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    email = db.Column(db.String(120))
    status = db.Column(db.String(20))
    total = db.Column(db.Float)
    placed_at = db.Column(db.String(10))
    items = db.Column(db.Text)  # JSON


class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    cart_key = db.Column(db.String(40), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('store_products.id'),
                           nullable=False)
    qty = db.Column(db.Integer, default=1)


class Shipment(db.Model):
    __tablename__ = 'shipments'
    id = db.Column(db.Integer, primary_key=True)
    tracking_number = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    service_code = db.Column(db.String(30))
    sender_name = db.Column(db.String(100))
    sender_city = db.Column(db.String(60))
    sender_state = db.Column(db.String(20))
    sender_zip = db.Column(db.String(10))
    recipient_name = db.Column(db.String(100))
    recipient_city = db.Column(db.String(60))
    recipient_state = db.Column(db.String(20))
    recipient_zip = db.Column(db.String(10))
    weight_lbs = db.Column(db.Float)
    ship_date = db.Column(db.String(10))
    status = db.Column(db.String(60))
    expected_date = db.Column(db.String(10))
    delivered_at = db.Column(db.String(20))
    insured_value = db.Column(db.Float)
    signature_required = db.Column(db.Boolean, default=False)
    extras = db.Column(db.Text)  # JSON
    is_cns = db.Column(db.Boolean, default=False)
    price_paid = db.Column(db.Float)
    is_international = db.Column(db.Boolean, default=False)
    dest_country = db.Column(db.String(60))
    created_at = db.Column(db.String(10))


class ScanEvent(db.Model):
    __tablename__ = 'scan_events'
    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipments.id'),
                           nullable=False)
    ts = db.Column(db.String(20))
    status = db.Column(db.String(120))
    status_code = db.Column(db.String(40))
    facility = db.Column(db.String(120))
    seq = db.Column(db.Integer)


class SavedTracking(db.Model):
    __tablename__ = 'saved_tracking'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tracking_number = db.Column(db.String(30))
    label = db.Column(db.String(80))
    created_at = db.Column(db.String(10))


class HoldMailRequest(db.Model):
    __tablename__ = 'hold_mail_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    confirmation = db.Column(db.String(30), unique=True)
    start_date = db.Column(db.String(10))
    end_date = db.Column(db.String(10))
    address = db.Column(db.String(160))
    status = db.Column(db.String(30))
    option = db.Column(db.String(40))
    created_at = db.Column(db.String(10))


class ChangeOfAddress(db.Model):
    __tablename__ = 'change_of_address'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    confirmation = db.Column(db.String(30), unique=True)
    move_type = db.Column(db.String(30))
    forward_type = db.Column(db.String(30))
    start_date = db.Column(db.String(10))
    old_address = db.Column(db.String(200))
    new_address = db.Column(db.String(200))
    email = db.Column(db.String(120))
    status = db.Column(db.String(30))
    fee = db.Column(db.Float)
    created_at = db.Column(db.String(10))


class PickupRequest(db.Model):
    __tablename__ = 'pickup_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    confirmation = db.Column(db.String(30), unique=True)
    pickup_date = db.Column(db.String(10))
    address = db.Column(db.String(200))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    packages = db.Column(db.Text)  # JSON
    instructions = db.Column(db.String(200))
    status = db.Column(db.String(30))
    created_at = db.Column(db.String(10))


class Claim(db.Model):
    __tablename__ = 'claims'
    id = db.Column(db.Integer, primary_key=True)
    claim_number = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    tracking_number = db.Column(db.String(30))
    kind = db.Column(db.String(20))  # damage | loss
    article = db.Column(db.String(200))
    amount = db.Column(db.Float)
    status = db.Column(db.String(30))
    filed_at = db.Column(db.String(10))
    docs = db.Column(db.Text)  # JSON
    events = db.Column(db.Text)  # JSON
    note = db.Column(db.Text)


class PoBoxRental(db.Model):
    __tablename__ = 'po_box_rentals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    po_id = db.Column(db.Integer, db.ForeignKey('post_offices.id'),
                      nullable=False)
    box_number = db.Column(db.String(12))
    size_label = db.Column(db.String(30))
    fee_paid = db.Column(db.Float)
    pay_period = db.Column(db.String(20))
    status = db.Column(db.String(20))
    expires_on = db.Column(db.String(10))
    created_at = db.Column(db.String(10))


class InformedMailPiece(db.Model):
    __tablename__ = 'informed_mail'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mail_date = db.Column(db.String(10))
    sender = db.Column(db.String(120))
    description = db.Column(db.String(160))
    category = db.Column(db.String(30))
    expected = db.Column(db.String(30))


# ------------------------------------------------------------------- seeds --

SERVICE_INFO = [
    ('pme', 'Priority Mail Express', 'express',
     "Fastest USPS delivery service with money-back guarantee, "
     "up-to-$100 insurance and Sunday/holiday delivery to most areas.",
     'images/pages/pme-hero-image-generic.jpg', 'ship/priority-mail-express.htm'),
    ('pm', 'Priority Mail', 'priority',
     "Delivery in 1-3 days with USPS Tracking and up to $100 insurance "
     "included; Flat Rate options let you ship up to 70 lbs at one price.",
     'images/pages/hero_pm-image-generic.jpg', 'ship/priority-mail.htm'),
    ('ga', 'USPS Ground Advantage', 'ground',
     "Simple, affordable ground shipping for packages up to 70 lbs in "
     "2-5 business days, with USPS Tracking and $100 insurance included.",
     'images/pages/ground-advantage-service.png', 'ship/ground-advantage.htm'),
    ('fcm', 'First-Class Mail', 'first_class',
     "Send standard envelopes and small packages up to 13 oz — postcards, "
     "letters and large envelopes (flats) at affordable retail prices.",
     'images/pages/create-mail-stamps-hero.jpg', 'ship/first-class-mail.htm'),
    ('mm', 'Media Mail', 'ground',
     "Cost-effective way to send books, sound recordings and other "
     "educational media up to 70 lbs.",
     'images/pages/create-mail-stamps-hero.jpg', 'ship/mail-shipping-services.htm'),
    ('fcpi', 'First-Class Package International Service', 'intl',
     "Affordable international shipping for packages up to 4 lbs to "
     "more than 180 countries.",
     'images/pages/ddp-1.jpg', 'international/first-class-package-international-service.htm'),
    ('pmi', 'Priority Mail International', 'intl',
     "Reliable international delivery in 6-10 days to more than 180 "
     "countries, with USPS Tracking and insurance included.",
     'images/pages/ddp-1.jpg', 'international/priority-mail-international.htm'),
    ('pmei', 'Priority Mail Express International', 'intl',
     "Fastest USPS international delivery: 3-5 days to over 180 "
     "countries with money-back guarantee.",
     'images/pages/ddp-1.jpg', 'international/priority-mail-express-international.htm'),
]

EXTRA_SERVICE_FEATURES = [
    ('certified', 'Certified Mail', 5.55,
     'Certified Mail — proof of mailing and delivery records are kept by USPS.'),
    ('insurance', 'Insurance', 2.80,
     'Package insurance for loss up to $5,000 (price varies by declared value).'),
    ('registered', 'Registered Mail', 0.0,
     'Registered Mail — the safest option for valuables (fees by value).'),
    ('cod', 'Collect on Delivery', 9.35,
     'Collect on Delivery — have USPS collect payment for you.'),
    ('return_receipt', 'Return Receipt', 3.10,
     'Return Receipt — get an email with the delivery image and recipient signature.'),
    ('signature', 'Signature Confirmation', 3.80,
     'Signature Confirmation — delivery record with the recipient signature.'),
]

STATUS_FLOW = {
    'label_created': 'Shipping Label Created',
    'accepted': 'Accepted at USPS Facility',
    'arrived': 'Arrived at USPS Facility',
    'departed': 'Departed USPS Facility',
    'in_transit': 'In Transit to Next Facility',
    'out_for_delivery': 'Out for Delivery',
    'delivered': 'Delivered',
    'available': 'Available for Pickup',
    'alert': 'Processing Exception',
}

# Real scan status vocabulary from the USPS Track and Confirm API
# documentation (business/web-tools-apis/track-and-confirm-api.htm).
TRACK_STATUS_GLOSSARY = [
    ("Shipping Label Created", "The sender created a shipping label "
     "online; USPS has not yet scanned the mailpiece."),
    ("Accepted at USPS Facility", "USPS accepted the mailpiece at the "
     "origin facility and it entered the mailstream."),
    ("Arrived at USPS Facility", "The mailpiece arrived at a USPS "
     "processing facility."),
    ("Departed USPS Facility", "The mailpiece left a USPS processing "
     "facility on its way to the destination."),
    ("In Transit to Next Facility", "The mailpiece is moving through the "
     "USPS network toward its destination."),
    ("Out for Delivery", "The mailpiece is on a delivery vehicle and "
     "should arrive today."),
    ("Delivered", "The mailpiece was delivered (or delivered to an agent "
     "or parcel locker)."),
    ("Available for Pickup", "The mailpiece is at the destination Post "
     "Office, held for the recipient to pick up."),
    ("Alert", "The mailpiece may not be deliverable; contact USPS for "
     "details or check for a processing exception."),
]

QUICK_TOOLS = [
    ('Track a Package', '/tracking/', 'images/chrome/tracking.svg'),
    ('Calculate a Price', '/postcalc/', 'images/chrome/calculate_price.svg'),
    ('Find a Post Office', '/locations/', 'images/chrome/location.svg'),
    ('Schedule a Pickup', '/pickup/', 'images/chrome/schedule_pickup.svg'),
    ('Buy Stamps', '/store/stamps', 'images/chrome/stamps.svg'),
    ('Rent a PO Box', '/po-boxes/', 'images/chrome/po_box.svg'),
    ('Hold Mail', '/manage/hold-mail.htm', 'images/chrome/holdmail.svg'),
    ('Change My Address', '/manage/forward.htm', 'images/chrome/change_address.svg'),
    ('Click-N-Ship', '/clicknship/', 'images/chrome/featured_clicknship.svg'),
    ('Free Boxes', '/store/shipping-supplies', 'images/chrome/free_boxes.svg'),
]


def _seed_gate(model, count_needed=1):
    return model.query.count() < count_needed


def _d(slash_date):
    """mm/dd/yyyy -> yyyy-mm-dd (Postmaster Finder date format)."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", slash_date or "")
    if m:
        return f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    return None


def seed_pages():
    if not _seed_gate(ContentPage):
        return
    for path, page in _load('pages.json').items():
        db.session.add(ContentPage(
            path=path, section=path.split('/')[0],
            title=page.get('title'), meta_description=page.get('meta_description'),
            headline=page.get('headline'), lead=(page.get('lead') or '')[:600],
            hero_image=_image_path(page.get('hero_image')),
            body=json.dumps(page.get('sections') or [])))
    db.session.commit()


def seed_pricing():
    if not _seed_gate(Rate):
        return
    data = _load('pricing.json')
    tables = {
        'priority_mail_retail': 'pm',
        'priority_mail_express_retail': 'pme',
        'ground_advantage_retail': 'ga',
        'media_mail_retail': 'mm',
        'priority_mail_intl_retail': 'pmi',
        'priority_mail_express_intl_retail': 'pmei',
    }
    for key, code in tables.items():
        for row in data.get(key, []):
            weight = row['weight']
            weight_hi = row.get('weight_hi')
            if row.get('unit') == 'oz':
                # normalize ounce rows (e.g. Ground Advantage 4/8/12/16 oz)
                # to pounds so every zone-grid weight is in lbs
                weight = round(weight / 16.0, 4)
                weight_hi = round(weight_hi / 16.0, 4) if weight_hi else None
            db.session.add(Rate(table_code=code, weight=weight,
                                weight_hi=weight_hi,
                                col=row['col'], col_hi=row.get('col_hi'),
                                col_label=row.get('col_label'),
                                price=row['price']))
    fcm = data.get('first_class_mail_retail', {})
    for kind, rows in fcm.items():
        slug = re.sub(r"[^a-z0-9]+", "_", kind.lower()).strip('_')
        for row in rows:
            db.session.add(Rate(table_code=f"fcm_{slug}",
                                weight=row['weight'], weight_hi=None, col=1,
                                col_label=kind, price=row['price']))
    for kind, rows in data.get('first_class_intl_retail', {}).items():
        table = {'Retail Postcards': 'fcmi_postcard',
                 'Retail Letters': 'fcmi_letter',
                 'Retail Large Envelopes (Flats)': 'fcmi_flat',
                 'Retail Packages': 'fcpis'}[kind]
        for row in rows:
            db.session.add(Rate(table_code=table, weight=row['weight'],
                                weight_hi=row.get('weight_hi'),
                                col=row['col'], col_hi=row.get('col_hi'),
                                col_label=row.get('col_label'),
                                price=row['price']))
    # flat rate
    for item in data.get('domestic_flat_rate', []):
        db.session.add(FlatRateItem(
            scope='domestic', service=item['service'], label=item['label'],
            size=item['size'], price=item['price']))
    for heading, rows in data.get('international_flat_rate', {}).items():
        for row in rows:
            db.session.add(FlatRateItem(
                scope='intl', service=heading, label=row['label'],
                size='', group_label=str(row['group']), group=row['group'],
                price=row['price']))
    # extra services (fees become band rows where the label carries a range)
    band_re = re.compile(r"\$?([0-9,.]+)\s*-\s*\$?([0-9,.]+)")
    for category, rows in data.get('domestic_extra_services', {}).items():
        for row in rows:
            label = row['label']
            price = row.get('price')
            lo = hi = None
            m = band_re.match(label.replace(',', ''))
            if m:
                lo = float(m.group(1))
                hi = float(m.group(2))
            db.session.add(ExtraService(scope='domestic', category=category,
                                         label=label, price=price,
                                         price_lo=lo, price_hi=hi))
    for category, rows in data.get('international_extra_services', {}).items():
        for row in rows:
            db.session.add(ExtraService(scope='intl', category=category,
                                        label=row['label'],
                                        price=row.get('price')))
    for row in _load('po_box_fee_matrix.json')['rows']:
        db.session.add(PoBoxFee(**row))
    db.session.commit()


def seed_services():
    if not _seed_gate(ServiceInfo):
        return
    for code, name, family, summary, hero, page in SERVICE_INFO:
        db.session.add(ServiceInfo(code=code, name=name, family=family,
                                   summary=summary, hero_image=hero,
                                   page_path=page))
    db.session.commit()


def seed_news():
    if not _seed_gate(NewsArticle):
        return
    data = _load('news.json')

    def add(kind, art, idx):
        slug = re.sub(r"[^a-z0-9]+", "-",
                      (art.get('title') or f"{kind}-{idx}").lower())[:80]
        clean = re.sub(r"\s*-\s*Newsroom\s*-\s*About\.usps\.com\s*$", "",
                       art.get('title') or '')
        images = []
        for img in art.get('images', [])[:3]:
            images.append({'path': _image_path(img['src']), 'alt': img.get('alt')})
        db.session.add(NewsArticle(
            slug=f"{slug}-{idx}", kind=kind, title=art.get('title'),
            clean_title=clean, date=art.get('date'),
            release_type=art.get('release_type'),
            body=json.dumps(art.get('paragraphs') or []),
            images=json.dumps([i for i in images if i['path']]),
            source_url=art.get('url')))

    for idx, art in enumerate(data.get('releases', [])):
        add('release', art, idx)
    for idx, art in enumerate(data.get('service_alerts', [])):
        add('alert', art, idx)
    db.session.commit()


def seed_countries():
    if not _seed_gate(CountryInfo):
        return
    groups = {row['country']: row
              for row in _load('pricing.json').get('country_price_groups', [])}
    icl = _load('countries.json')
    for name, info in icl.items():
        g = groups.get(name, {})
        db.session.add(CountryInfo(
            name=name, slug=re.sub(r"[^a-z0-9]+", "-", name.lower()),
            pmei_group=str(g.get('pmei_group', '')),
            pmei_max_lbs=str(g.get('pmei_max_lbs', '')),
            pmi_group=str(g.get('pmi_group', '')),
            pmi_max_lbs=str(g.get('pmi_max_lbs', '')),
            pmi_frb_group=str(g.get('pmi_frb_group', '')),
            fcmi_group=str(g.get('fcmi_group', '')),
            fcpis_group=str(g.get('fcpis_group', '')),
            prohibitions=json.dumps(info.get('prohibitions', [])),
            restrictions=json.dumps(info.get('restrictions', [])),
            observations=json.dumps(info.get('observations', [])),
            services=json.dumps(info.get('services', {})),
            source_url=info.get('source_url')))
    db.session.commit()


US_STATE_CODES = {
    'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
    'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT',
    'DELAWARE': 'DE', 'DISTRICT OF COLUMBIA': 'DC', 'FLORIDA': 'FL',
    'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID', 'ILLINOIS': 'IL',
    'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS', 'KENTUCKY': 'KY',
    'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
    'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN',
    'MISSISSIPPI': 'MS', 'MISSOURI': 'MO', 'MONTANA': 'MT',
    'NEBRASKA': 'NE', 'NEVADA': 'NV', 'NEW HAMPSHIRE': 'NH',
    'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
    'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH',
    'OKLAHOMA': 'OK', 'OREGON': 'OR', 'PENNSYLVANIA': 'PA',
    'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC', 'SOUTH DAKOTA': 'SD',
    'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT', 'VERMONT': 'VT',
    'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
    'WISCONSIN': 'WI', 'WYOMING': 'WY', 'AMERICAN SAMOA': 'AS',
    'GUAM': 'GU', 'MARSHALL ISLANDS': 'MH', 'PUERTO RICO': 'PR',
}


def _state_code(state):
    code = US_STATE_CODES.get((state or '').upper())
    return code if code else (state or '')[:2].upper()


def _pad_zip(zip_code):
    digits = re.sub(r'\D', '', zip_code or '')
    return ('00000' + digits)[-5:] if digits else ''


def _post_office_hours(seed_key):
    """Deterministic, clearly-mirror operating details per facility."""
    digest = hashlib.sha256(seed_key.encode()).hexdigest()
    h = int(digest[:6], 16)
    open_h = 8 + (h % 2)              # 8 or 9
    close_h = 17 + (h % 3)            # 17..19
    sat = h % 4 != 0
    sat_hours = f"{9 + h % 2}:00 am - {12 + h % 2}:00 pm" if sat else ""
    return {
        'mon_fri': f"{open_h}:00 am - {close_h}:00 pm",
        'sat': sat_hours or 'Closed',
        'sun': 'Closed',
        'lobby': f"24 hours" if h % 5 == 0 else
                 f"{open_h - 1}:00 am - {close_h + 1}:00 pm",
    }


def _post_office_services(seed_key):
    digest = hashlib.sha256(seed_key.encode()).hexdigest()
    h = int(digest[6:12], 16)
    pool = ['Passport Photos', 'Self-Service Kiosk', 'Po Box Rental',
            'Bulk Mail Acceptance', 'Global Express Guaranteed',
            'Burial Flags', 'Money Orders', 'Stamps by Mail']
    return [pool[i] for i in range(len(pool)) if (h >> i) & 1] or ['Stamps by Mail']


def seed_post_offices():
    if not _seed_gate(PostOffice):
        return
    data = _load('post_offices.json')
    added = set()
    rosters = {}
    for city_state, entries in data.get('postmasters', {}).items():
        for entry in entries:
            po_name = entry.get('post_office')
            if not po_name:
                continue
            roster = entry.get('roster') or []
            rosters[(po_name.upper(),
                     _state_code(entry.get('state', '')))] = roster

    def add_po(name, state, zip5, est, discont, county):
        key = (name or '').upper()
        if not name or not state or key in added:
            return
        state = _state_code(state)
        zip5 = _pad_zip(zip5)
        dedup_key = f"{key}|{state}|{zip5}"
        if dedup_key in added:
            return
        added.add(dedup_key)
        city = name.title()
        seed_key = f"{name}|{state}|{zip5}"
        roster = rosters.get((key, state.upper()))
        postmaster = None
        postmaster_since = None
        if roster:
            named = [r for r in roster if r.get('name')
                     and 'establish' not in r['name'].lower()]
            for r in reversed(named):
                if r.get('name', '').lower().startswith('('):
                    continue
                postmaster = r.get('name')
                postmaster_since = _d(r.get('date') or '')
                break
        db.session.add(PostOffice(
            po_key=re.sub(r"[^a-z0-9]+", "-", f"{name}-{state}-{zip5}".lower()),
            name=city, city=city, state=state, zip5=zip5,
            county=(county or '').title(),
            est_date=_d(est or ''), discont_date=_d(discont or ''),
            address=f"{100 + len(name) * 7 % 800} {city} Main St",
            phone=f"800-ASK-USPS",
            hours=json.dumps(_post_office_hours(seed_key)),
            services=json.dumps(_post_office_services(seed_key)),
            fee_group='2',
            has_po_boxes=True, postmaster=postmaster,
            postmaster_since=postmaster_since))

    for state, rows in data.get('states', {}).items():
        for row in rows:
            add_po(row.get('post-office'), state.title(),
                   row.get('zip'), row.get('estab'), row.get('discont'), '')
    for span, rows in data.get('zip_slices', {}).items():
        for row in rows:
            add_po(row.get('post-office'), row.get('state', ''),
                   row.get('zip'), row.get('estab'), row.get('discont'), '')
    db.session.commit()

    for city_state, entries in data.get('postmasters', {}).items():
        city, state = city_state.split(', ')
        for entry in entries:
            for r in (entry.get('roster') or []):
                name = r.get('name')
                if not name or name.startswith('('):
                    continue
                db.session.add(Postmaster(
                    city=city.title(), state=state.title(),
                    post_office=entry.get('post_office'),
                    name=name, title=r.get('title'), date=r.get('date'),
                    current=False))
    db.session.commit()


def seed_store():
    if not _seed_gate(StoreProduct):
        return
    data = _load('store_products.json')
    seen_skus = set()
    for p in data.get('products', []):
        if not p.get('name'):
            continue
        raw_images = [i for i in p.get('images', [])
                      if re.search(r"(-S0\.jpg|_360x360\.jpg|_512x512\.jpg)$", i)]
        sku = p.get('sku') or ''
        if len(re.sub(r'\D', '', sku)) < 5:
            # free shipping supplies carry short pack codes; the real product
            # asset id in the ecp image filename is the usable catalog SKU
            from_asset = (re.search(r'(\d{5,})',
                                   (raw_images[0] if raw_images else ''))
                          or [None, ''])[1] if raw_images else ''
            sku = from_asset or re.sub(r'\D', '', p['slug'])[:10] or p['slug'][:12]
        # keep only this product's own asset images — the product page also
        # renders related-product thumbnails sharing the same DOM
        own = [i for i in raw_images
               if sku and sku in i.rsplit('/', 1)[-1]]
        images = own or raw_images
        main = None
        for i in images:
            if i.endswith('-S0.jpg'):
                main = _image_path(i)
                break
        if main is None:
            for i in images:
                if re.search(r"_360x360\.jpg$|_512x512\.jpg$", i):
                    main = _image_path(i)
                    break
        if main is None and images:
            main = _image_path(images[0])
        try:
            if sku in seen_skus:
                continue
            seen_skus.add(sku)
            db.session.add(StoreProduct(
                sku=sku, slug=p['slug'], name=p['name'],
                category=p.get('category'), price=p.get('price'),
                description=p.get('description'),
                image=main,
                gallery=json.dumps([_image_path(i) for i in images[:4]
                                    if _image_path(i)])))
        except Exception:
            continue
    db.session.commit()


def _tracking_number(seed_text, prefix='94'):
    digest = hashlib.sha256(seed_text.encode()).hexdigest()
    digits = re.sub(r"\D", "", digest)[:20]
    return f"{prefix}{digits}"


def _event(ts, status_key, facility, seq):
    return ScanEvent(ts=ts, status=STATUS_FLOW[status_key], facility=facility,
                     status_code=status_key, seq=seq)


def seed_shipments():
    if not _seed_gate(Shipment):
        return

    def add(tracking, user_id, service, sender, s_city, s_state, s_zip,
            recipient, r_city, r_state, r_zip, weight, ship_date, status,
            expected, insured=None, signature=False, delivered=None,
            is_cns=False, price=None, intl=False, country=None, extras=None):
        ship = Shipment(tracking_number=tracking, user_id=user_id,
                        service_code=service, sender_name=sender,
                        sender_city=s_city, sender_state=s_state,
                        sender_zip=s_zip, recipient_name=recipient,
                        recipient_city=r_city, recipient_state=r_state,
                        recipient_zip=r_zip, weight_lbs=weight,
                        ship_date=ship_date, status=status,
                        expected_date=expected, insured_value=insured,
                        signature_required=signature, delivered_at=delivered,
                        is_cns=is_cns, price_paid=price, is_international=intl,
                        dest_country=country, extras=json.dumps(extras or []),
                        created_at=ship_date)
        db.session.add(ship)
        db.session.flush()
        events = []
        base = datetime.strptime(ship_date, '%Y-%m-%d')
        facilities = [(s_city, s_state), ('DENVER', 'CO'), (r_city, r_state)]
        if status == 'Delivered' or delivered:
            keys = ['label_created', 'accepted', 'arrived', 'departed',
                    'in_transit', 'out_for_delivery', 'delivered']
            for i, key in enumerate(keys):
                ts = (base + timedelta(hours=10 * i)).strftime('%Y-%m-%d %H:%M')
                fac = facilities[min(i // 2, 2)]
                events.append(_event(ts, key, f"{fac[0]}, {fac[1]}", i))
        elif status == 'Out for Delivery':
            keys = ['label_created', 'accepted', 'arrived', 'in_transit',
                    'out_for_delivery']
            for i, key in enumerate(keys):
                ts = (base + timedelta(hours=12 * i)).strftime('%Y-%m-%d %H:%M')
                fac = facilities[min(i // 2, 2)]
                events.append(_event(ts, key, f"{fac[0]}, {fac[1]}", i))
        elif status == 'In Transit, Arriving Late':
            keys = ['label_created', 'accepted', 'arrived', 'departed',
                    'in_transit', 'alert', 'in_transit']
            for i, key in enumerate(keys):
                ts = (base + timedelta(hours=11 * i)).strftime('%Y-%m-%d %H:%M')
                fac = facilities[min(i // 2, 2)]
                events.append(_event(ts, key, f"{fac[0]}, {fac[1]}", i))
        else:
            keys = ['label_created', 'accepted', 'arrived', 'in_transit']
            for i, key in enumerate(keys):
                ts = (base + timedelta(hours=12 * i)).strftime('%Y-%m-%d %H:%M')
                fac = facilities[min(i // 2, 2)]
                events.append(_event(ts, key, f"{fac[0]}, {fac[1]}", i))
        if delivered:
            events[-1].ts = datetime.strptime(delivered, '%Y-%m-%d %I:%M %p').strftime('%Y-%m-%d %H:%M')
        for e in events:
            e.shipment_id = ship.id
            db.session.add(e)

    # Alice: delivered Priority Mail Click-N-Ship label, insured + signature
    add('9405500000000000000001', 1, 'pm', 'Alice Johnson',
        'Seattle', 'WA', '98101', 'Marcus Johnson', 'Portland', 'OR',
        '97201', 4.2, '2026-09-20', 'Delivered', '2026-09-23',
        insured=350.00, signature=True, delivered='2026-09-23 11:47 am',
        is_cns=True, price=17.35,
        extras=['Insurance ($350)', 'Signature Confirmation'])
    # Alice: inbound from a store, delivered
    add('9405500000000000000002', 1, 'ga', 'USPS Store',
        'Riverton', 'WY', '82501', 'Alice Johnson', 'Seattle', 'WA',
        '98101', 2.0, '2026-09-16', 'Delivered', '2026-09-20',
        delivered='2026-09-20 3:12 pm')
    # Bob: in-transit Ground Advantage
    add('9405500000000000000003', 2, 'ga', 'Bob Chen',
        'Chicago', 'IL', '60601', 'Wei Zhang', 'San Francisco', 'CA',
        '94101', 6.5, '2026-09-25', 'In Transit', '2026-09-30')
    # Bob: damaged insured Priority Mail (claim domain)
    add('9405500000000000000004', 2, 'pm', 'Bob Chen',
        'Chicago', 'IL', '60601', 'Dana Kim', 'Austin', 'TX',
        '73301', 8.0, '2026-09-12', 'Delivered', '2026-09-15',
        insured=280.00, delivered='2026-09-15 1:02 pm')
    # Carol: Priority Mail Express, out for delivery today
    add('9405500000000000000005', 3, 'pme', 'Carol Davis',
        'Boston', 'MA', '02110', 'Peter Davis', 'New York', 'NY',
        '10001', 1.5, '2026-09-27', 'Out for Delivery', '2026-09-28',
        signature=True)
    # Dana: international FCMI-style FCPIS to Japan, in transit
    add('9405500000000000000006', 4, 'fcpis', 'Dana Kim',
        'Austin', 'TX', '73301', 'Yuki Tanaka', 'Tokyo', '', '',
        3.0, '2026-09-24', 'In Transit', '2026-10-06',
        intl=True, country='Japan', price=45.60)
    # Public: an unregistered delayed package
    add('9405500000000000000007', None, 'pm', 'Rosa Alvarez',
        'Miami', 'FL', '33101', 'Rosa Alvarez', 'Denver', 'CO',
        '80201', 12.0, '2026-09-18', 'In Transit, Arriving Late',
        '2026-09-25', insured=100.00)
    # Public: media mail delivered
    add('9405500000000000000008', None, 'mm', 'The Book Nook',
        'Boise', 'ID', '83701', 'Frank Miller', 'Portland', 'OR',
        '97205', 30.0, '2026-09-10', 'Delivered', '2026-09-17',
        delivered='2026-09-17 10:20 am')
    # Alice: another delivered priority (for history)
    add('9405500000000000000009', 1, 'pm', 'Alice Johnson',
        'Seattle', 'WA', '98101', 'Sarah Lee', 'Los Angeles', 'CA',
        '90012', 5.5, '2026-09-02', 'Delivered', '2026-09-05',
        delivered='2026-09-05 9:58 am', is_cns=True, price=15.90)
    # Bob: outbound Click-N-Ship from last week
    add('9405500000000000000010', 2, 'pm', 'Bob Chen',
        'Chicago', 'IL', '60601', 'Emily Chen', 'Seattle', 'WA',
        '98105', 3.0, '2026-09-21', 'Delivered', '2026-09-24',
        delivered='2026-09-24 4:41 pm', is_cns=True, price=14.05)
    db.session.commit()


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    users = [
        {'username': 'alice_j', 'email': 'alice.j@test.com',
         'display': 'Alice Johnson', 'street': '1420 4th Ave',
         'city': 'Seattle', 'state': 'WA', 'zip5': '98101',
         'phone': '(206) 555-0142'},
        {'username': 'bob_c', 'email': 'bob.c@test.com',
         'display': 'Bob Chen', 'street': '35 E Wacker Dr',
         'city': 'Chicago', 'state': 'IL', 'zip5': '60601',
         'phone': '(312) 555-0135'},
        {'username': 'carol_d', 'email': 'carol.d@test.com',
         'display': 'Carol Davis', 'street': '88 State St',
         'city': 'Boston', 'state': 'MA', 'zip5': '02110',
         'phone': '(617) 555-0188'},
        {'username': 'dana_k', 'email': 'dana.k@test.com',
         'display': 'Dana Kim', 'street': '710 Congress Ave',
         'city': 'Austin', 'state': 'TX', 'zip5': '73301',
         'phone': '(512) 555-0171'},
    ]
    created = {}
    for u in users:
        user = User(email=u['email'], username=u['username'],
                    display_name=u['display'],
                    password_hash=BENCHMARK_PASSWORD_HASH,
                    street=u['street'], city=u['city'], state=u['state'],
                    zip5=u['zip5'], phone=u['phone'],
                    created_at='2026-08-01')
        db.session.add(user)
        created[u['username']] = user
    db.session.commit()

    # ---- saved tracking numbers
    db.session.add(SavedTracking(user_id=created['alice_j'].id,
                                 tracking_number='9405500000000000000002',
                                 label='Store order', created_at='2026-09-16'))
    db.session.add(SavedTracking(user_id=created['bob_c'].id,
                                 tracking_number='9405500000000000000003',
                                 label='Books to Wei', created_at='2026-09-25'))
    db.session.commit()

    # ---- store orders
    def order(num, user, items, total, placed):
        db.session.add(StoreOrder(order_number=num, user_id=user.id,
                                  email=user.email, status='Delivered',
                                  total=total, placed_at=placed,
                                  items=json.dumps(items)))
    order('W771940312', created['alice_j'],
          [{'sku': '686104', 'name': 'Christmas Cookies Stamps, Book of 20',
            'qty': 1, 'price': 16.40}], 16.40, '2026-09-14')
    order('W772165238', created['alice_j'],
          [{'sku': '582904', 'name': 'Diwali 2026 Stamps, Sheet of 20',
            'qty': 2, 'price': 16.40}], 32.80, '2026-09-25')
    order('W771882604', created['bob_c'],
          [{'sku': '555304', 'name': 'Breast Cancer Research Stamps, Sheet of 20',
            'qty': 1, 'price': 20.00}], 20.00, '2026-09-18')
    db.session.commit()

    # ---- hold mail: Carol has an active hold
    db.session.add(HoldMailRequest(
        user_id=created['carol_d'].id, confirmation='HLD-748291',
        start_date='2026-09-25', end_date='2026-10-05',
        address='88 State St, Boston, MA 02110', status='Active',
        option='Hold all mail, deliver on end date', created_at='2026-09-22'))
    db.session.commit()

    # ---- change of address: Dana moved last month (premium)
    db.session.add(ChangeOfAddress(
        user_id=created['dana_k'].id, confirmation='COA-88173620',
        move_type='Individual', forward_type='Premium',
        start_date='2026-08-28',
        old_address='2900 Guadalupe St, Austin, TX 78705',
        new_address='710 Congress Ave, Austin, TX 78701',
        email='dana.k@test.com', status='Active',
        # historical row: the fee actually charged on 2026-08-26 (frozen
        # for seed byte-identity; see COA_IDENTITY_FEE above)
        fee=COA_SEED_FEE_FROZEN, created_at='2026-08-26'))
    db.session.commit()

    # ---- pickup: Bob has a pickup scheduled for tomorrow
    db.session.add(PickupRequest(
        user_id=created['bob_c'].id, confirmation='PKG-338275',
        pickup_date='2026-09-29', address='35 E Wacker Dr, Chicago, IL 60601',
        phone='(312) 555-0135', email='bob.c@test.com',
        packages=json.dumps([{'count': 2,
                              'est_weight': 6.5,
                              'services': ['Ground Advantage']}]),
        instructions='Packages are at the front desk.',
        status='Scheduled', created_at='2026-09-26'))
    db.session.commit()

    # ---- claims: Bob's damaged shipment claim, in review
    db.session.add(Claim(
        claim_number='CLM-55219088', user_id=created['bob_c'].id,
        tracking_number='9405500000000000000004', kind='damage',
        article='Vintage glass lamp (insured for $280)',
        amount=280.00, status='In Review', filed_at='2026-09-18',
        docs=json.dumps(['Proof of insurance (Click-N-Ship receipt)',
                         'Photos of damaged packaging and item',
                         'Purchase receipt']),
        events=json.dumps([
            {'date': '2026-09-18', 'note': 'Claim received; supporting documentation accepted.'},
            {'date': '2026-09-21', 'note': 'Claim assigned to a USPS claims analyst for review.'},
            {'date': '2026-09-24', 'note': 'Damage assessment in progress; delivery record verified.'},
        ]), note='Item arrived with cracked shade; outer box crushed on one corner.'))
    db.session.commit()

    # ---- PO box rental: Carol rents a box in Boston
    po = PostOffice.query.filter_by(city='Boston', state='MA').first()
    if po is None:
        po = PostOffice.query.filter(PostOffice.state == 'MA').first()
    if po is not None:
        db.session.add(PoBoxRental(
            user_id=created['carol_d'].id, po_id=po.id, box_number='3227',
            size_label='2', fee_paid=65.00, pay_period='6 months',
            status='Active', expires_on='2027-03-15', created_at='2026-09-15'))
    db.session.commit()

    # ---- Informed Delivery mail feed (deterministic text cards)
    feed = {
        'alice_j': [
            ('2026-09-28', 'Cascadia Outdoor Co', 'Promotion: fall hiking gear catalog',
             'Mailpiece', 'Today'),
            ('2026-09-28', 'City of Seattle', 'Utility bill: water service',
             'Bill/Statement', 'Today'),
            ('2026-09-27', 'Greater Seattle Writers', 'Newsletter: October events',
             'Periodical', 'Yesterday'),
            ('2026-09-27', 'Market Street Bakery', 'Coupon: 15% off next order',
             'Promotion', 'Yesterday'),
        ],
        'bob_c': [
            ('2026-09-28', 'Lakeshore Hardware', 'Invoice #88213: order 7712',
             'Bill/Statement', 'Today'),
            ('2026-09-28', 'Illinois Secretary of State', 'Vehicle registration renewal notice',
             'Official', 'Today'),
            ('2026-09-26', 'Midwest Chess League', 'Fall tournament schedule',
             'Letter', '2 days ago'),
        ],
        'carol_d': [
            ('2026-09-28', 'Bay Financial', 'Quarterly statement available',
             'Bill/Statement', 'Today'),
            ('2026-09-25', 'New England Gardens', 'Spring bulb catalog',
             'Promotion', '3 days ago'),
        ],
        'dana_k': [
            ('2026-09-28', 'Lone Star Insurance', 'Policy renewal reminder',
             'Official', 'Today'),
            ('2026-09-24', 'Austin Cycle Club', 'Membership card enclosed',
             'Letter', '4 days ago'),
        ],
    }
    for username, rows in feed.items():
        for mail_date, sender, desc, cat, exp in rows:
            db.session.add(InformedMailPiece(
                user_id=created[username].id, mail_date=mail_date,
                sender=sender, description=desc, category=cat, expected=exp))
    db.session.commit()


def _image_path(url):
    """Map an upstream image URL to the mirror's downloaded asset path."""
    if not url:
        return None
    name = re.sub(r"[^A-Za-z0-9._-]", "_", url.rsplit('/', 1)[-1].split('?')[0])
    for group in ('chrome', 'pages', 'store', 'news'):
        candidate = os.path.join('images', group, name)
        if os.path.exists(os.path.join(BASE_DIR, 'static', candidate)):
            return candidate
    return None


# ------------------------------------------------ text repair (review F-5) --
# The 2026-09-28 scrapes let requests guess some UTF-8 pages as latin-1,
# leaving mojibake like "2â\x80\x935 days" / "Thereâ\x80\x99s" in the tracked
# source snapshots (and therefore in the frozen seed DB). The seed is a
# frozen contract artifact, so the repair runs at RENDER time: every
# string a visitor can see is passed through _fix_mojibake(). The
# scrapers themselves are fixed to decode UTF-8 explicitly, so any
# future re-scrape stays clean.
_MOJI_TRAP = re.compile(r'[\u0080-\u009f\u00c2\u00c3\u00e2]')
_MOJI_RUN = re.compile(r'[\u0080-\u00ff]+')


def _fix_mojibake(value):
    """Repair UTF-8-bytes-decoded-as-latin-1 text in str/list/dict trees.

    A clean string round-trips through latin-1 into valid UTF-8; strings
    that mix real UTF-8 characters with mojibake fall back to repairing
    each maximal latin-1 run separately; anything else is untouched.
    """
    if isinstance(value, str):
        s = value
        if not _MOJI_TRAP.search(s):
            return s
        try:
            return s.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            out, pos = [], 0
            for m in _MOJI_RUN.finditer(s):
                out.append(s[pos:m.start()])
                chunk = m.group(0)
                try:
                    out.append(chunk.encode('latin-1').decode('utf-8'))
                except (UnicodeEncodeError, UnicodeDecodeError):
                    if _MOJI_TRAP.search(chunk):
                        # truncated mojibake (e.g. a lone trailing 'Â'
                        # whose UTF-8 continuation byte was stripped as
                        # whitespace by the scraper) — drop the orphan
                        out.append('')
                    else:
                        # genuinely latin-1 text — keep untouched
                        out.append(chunk)
                pos = m.end()
            out.append(s[pos:])
            return ''.join(out)
    if isinstance(value, list):
        return [_fix_mojibake(v) for v in value]
    if isinstance(value, dict):
        return {k: _fix_mojibake(v) for k, v in value.items()}
    return value


# ------------------------------------------------ HTML fragment sanitizer (audit F-B) --
# The scraped page bodies carry upstream HTML fragments (<sup>, <strong>,
# <a href=...>) that Jinja autoescaping would render as literal visible
# text (3,179 visible tags across 42 of 43 content pages at audit time).
# _sanitize_html strips markup to clean text; anchors to MIRRORED pages
# become real in-mirror links (nav stays same-origin); anchors to upstream
# or un-mirrored targets keep their inner text only. The frozen seed DB
# bytes are untouched — this runs at render time.
_TAG_RE = re.compile(r'<[^>]+>')
_ANCHOR_RE = re.compile(r'<a\b([^>]*)>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_HREF_RE = re.compile(r'''href\s*=\s*["']([^"']*)["']''', re.IGNORECASE)


def _mirrored_target(href):
    """True when href points at a page this mirror actually serves."""
    if not href or not href.startswith('/'):
        return False
    path = href.split('#', 1)[0].split('?', 1)[0].rstrip('/')
    if not path:
        return False
    if path.startswith('/static/'):
        return os.path.exists(os.path.join(BASE_DIR, path.lstrip('/')))
    try:
        if ContentPage.query.filter_by(path=path.lstrip('/')).first():
            return True
    except Exception:
        pass
    # app routes that exist independently of ContentPage rows
    route_prefixes = ('/tracking', '/postcalc', '/clicknship', '/pickup',
                      '/locations', '/po-boxes', '/store', '/manage',
                      '/international/countries', '/claims', '/newsroom',
                      '/account', '/login', '/search')
    return path in ('/',) or any(path == p or path.startswith(p + '/')
                                or path.startswith(p)
                                for p in route_prefixes)


def _sanitize_html(value):
    """Recursively clean HTML fragments out of scraped text trees."""
    if isinstance(value, str):
        # The source scraper retained a truncated image alt/src suffix here.
        value = re.sub(r' Priority Mail Express .*?boxes sitting on a couch.*$', '', value)
        if '<' not in value:
            return value

        def anchor_sub(m):
            attrs, inner = m.group(1), m.group(2)
            inner_txt = _TAG_RE.sub('', inner).strip()
            hm = _HREF_RE.search(attrs)
            href = hm.group(1).strip() if hm else ''
            if href.startswith('#') or not href:
                return inner_txt            # in-page footnote anchors: text only
            if _mirrored_target(href):
                # placeholder survives the tag-strip pass below
                return f'\x00A{href}\x00{inner_txt}\x00/A\x00'
            return inner_txt                # upstream / un-mirrored: text only

        out = _ANCHOR_RE.sub(anchor_sub, value)
        out = _TAG_RE.sub('', out)
        out = re.sub(r'\x00A([^\x00]*)\x00([^\x00]*)\x00/A\x00',
                     lambda m: f'<a href="{m.group(1)}">{m.group(2)}</a>', out)
        out = re.sub(r'[ \t]+', ' ', out)
        return out
    if isinstance(value, list):
        return [_sanitize_html(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize_html(v) for k, v in value.items()}
    return value


def _clean_page(page):
    """Render-safe copy of a ContentPage (text repaired, DB row untouched)."""
    if page is None:
        return None
    return SimpleNamespace(
        id=page.id, path=page.path, section=page.section,
        title=_sanitize_html(_fix_mojibake(page.title)),
        meta_description=_fix_mojibake(page.meta_description),
        headline=_sanitize_html(_fix_mojibake(page.headline)),
        lead=_sanitize_html(_fix_mojibake(page.lead)),
        hero_image=page.hero_image,
        body=json.dumps(_sanitize_html(
            _fix_mojibake(json.loads(page.body or '[]')))))


def _clean_article(article):
    """Render-safe copy of a NewsArticle (text repaired, DB untouched)."""
    if article is None:
        return None
    return SimpleNamespace(
        id=article.id, slug=article.slug, kind=article.kind,
        title=_fix_mojibake(article.title),
        clean_title=_fix_mojibake(article.clean_title),
        date=article.date, release_type=article.release_type,
        body=json.dumps(_fix_mojibake(json.loads(article.body or '[]'))),
        images=json.dumps(_fix_mojibake(json.loads(article.images or '[]'))),
        source_url=article.source_url)


# ------------------------------------------------------------------ helpers --

def positive_number(value, maximum=70):
    try:
        number = float(value)
    except (ValueError, TypeError):
        abort(400, description='Enter a valid weight or amount.')
    if not math.isfinite(number) or not 0 < number <= maximum:
        abort(400, description='Weight or amount is out of range.')
    return number


def valid_zone(value):
    if str(value) not in {str(n) for n in range(1, 10)}:
        abort(400, description='Choose a valid zone.')
    return int(value)


def _cns_options(data):
    weight = positive_number(data.get('weight_lbs'))
    zone = valid_zone(data.get('zone'))
    box = data.get('box_type', 'own')
    if box != 'own':
        names = {'fr-envelope': 'Flat Rate Envelope', 'fr-medium': 'Medium Flat Rate Boxes', 'fr-large': 'Large Flat Rate Box'}
        if box not in names:
            abort(400, description='Choose valid packaging.')
        item = FlatRateItem.query.filter_by(scope='domestic', service='Priority Mail', label=names[box]).first()
        if not item:
            abort(400, description='This packaging is unavailable.')
        return [('pm', 'Priority Mail', item.price)]
    return [(code, label, price) for code, label in [('pme', 'Priority Mail Express'), ('pm', 'Priority Mail'), ('ga', 'USPS Ground Advantage')]
            if (price := _price_for(code, weight, zone)) is not None]


def _validate_cns_address(data):
    for prefix in ('sender', 'recipient'):
        if any(not data.get(prefix + '_' + field, '').strip() for field in ('name', 'street', 'city', 'state', 'zip')) or not re.fullmatch(r'\d{5}', data.get(prefix + '_zip', '')):
            abort(400, description='Enter complete sender and recipient addresses with five-digit ZIP codes.')


def _price_for(table_code, weight, col):
    """Retail price for a weight/zone cell (first grid row at or above weight)."""
    rows = Rate.query.filter_by(table_code=table_code).order_by(Rate.weight).all()
    for row in rows:
        hi = row.weight_hi if row.weight_hi else row.weight
        if weight <= hi:
            if row.col_hi is not None:
                if row.col <= col <= row.col_hi:
                    return row.price
            elif row.col == col:
                return row.price
    return None


def _band_fee(category, declared):
    """Insurance/COD fee by declared value from the Notice 123 fee table."""
    for svc in ExtraService.query.filter_by(scope='domestic',
                                            category=category):
        if svc.price_lo is not None and svc.price_hi is not None:
            if svc.price_lo <= declared <= svc.price_hi:
                return svc.price
    flat = ExtraService.query.filter(
        ExtraService.scope == 'domestic', ExtraService.category == category,
        ExtraService.price_lo.is_(None)).order_by(ExtraService.price).first()
    return flat.price if flat else None


def _flat_fee(category, needle=None, prefer_labels=None):
    q = ExtraService.query.filter(ExtraService.scope == 'domestic',
                                  ExtraService.category == category)
    if needle:
        q = q.filter(ExtraService.label.ilike(f"%{needle}%"))
    if prefer_labels:
        row = q.filter(ExtraService.label.in_(prefer_labels)).first()
        if row:
            return row.price
    row = q.order_by(ExtraService.price).first()
    return row.price if row else None


def _cart_key():
    if current_user.is_authenticated:
        return f"user:{current_user.id}"
    if 'cart_key' not in session:
        session['cart_key'] = secrets.token_hex(16)
    return f"session:{session['cart_key']}"


def _number_for(prefix, seed_text):
    digest = hashlib.sha256(f"{prefix}|{seed_text}".encode()).hexdigest()
    tail = digest[:7].upper()
    return f"{prefix}{tail}"


def _ctx(**kw):
    nav = [
        ('Mail & Ship', [
            ('Send Mail & Packages', '/ship/mail-shipping-services.htm'),
            ('Buy Stamps', '/store/stamps'),
            ('Calculate a Price', '/postcalc/'),
            ('Schedule a Pickup', '/pickup/'),
            ('Click-N-Ship', '/clicknship/'),
            ('Find USPS Locations', '/locations/'),
        ]),
        ('Track & Manage', [
            ('Track a Package', '/tracking/'),
            ('Hold Mail', '/manage/hold-mail.htm'),
            ('Change My Address', '/manage/forward.htm'),
            ('PO Boxes', '/po-boxes/'),
            ('Informed Delivery', '/manage/informed-delivery.htm'),
            ('Insurance & Claims', '/help/claims.htm'),
        ]),
        ('Business', [
            ('Postage Options', '/business/postage-options.htm'),
            ('Compare Services', '/business/postage-options-compare.htm'),
            ('Prices', '/business/prices.htm'),
        ]),
        ('International', [
            ('How to Ship Internationally', '/international/international-how-to.htm'),
            ('Country Listings', '/international/countries'),
            ('Customs Forms', '/international/customs-forms.htm'),
            ('Shipping Restrictions', '/international/shipping-restrictions.htm'),
        ]),
        ('Help', [
            ('File a Claim', '/help/claims.htm'),
            ('Missing Mail', '/help/missing-mail.htm'),
            ('Refunds', '/help/refunds.htm'),
            ('Contact Us', '/help/contact-us.htm'),
        ]),
    ]
    kw.setdefault('nav', nav)
    kw.setdefault('quick_tools', QUICK_TOOLS)
    kw.setdefault('site_name', 'USPS.com')
    return kw


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', **_ctx()), 404


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


@app.template_filter('usd')
def usd(value):
    if value is None:
        return ""
    return f"${value:,.2f}"


@app.template_filter('from_json')
def from_json(value):
    try:
        return json.loads(value or '[]')
    except (TypeError, ValueError):
        return []


@app.template_filter('h12')
def h12(value):
    """Normalize stored facility hours like '19:00 pm' to '7:00 pm'.

    The seed's deterministic hours were written as 24-hour numbers with
    am/pm suffixes mixed in (reviewer F-13); the display layer renders
    them as proper 12-hour times without touching the frozen seed rows.
    """
    if not value:
        return value

    def _fix(m):
        hour = int(m.group(1))
        if m.group(3):  # an explicit am/pm suffix is already present
            if hour < 12:
                return f"{hour}:{m.group(2)} am"
            if hour == 12:
                return f"{hour}:{m.group(2)} pm"
            return f"{hour - 12}:{m.group(2)} pm"
        return m.group(0)

    return re.sub(r"(\d{1,2}):(\d{2})(?:\s*(am|pm))?", _fix, str(value))


@app.template_filter('longdate')
def longdate(value):
    if not value:
        return ""
    try:
        d = datetime.strptime(str(value)[:10], '%Y-%m-%d')
        return d.strftime('%B %-d, %Y')
    except ValueError:
        return value


# -------------------------------------------------------------------- views --

@app.route('/_health')
def health():
    return jsonify(ok=True, site=SITE_NAME,
                   pages=ContentPage.query.count(),
                   rates=Rate.query.count(),
                   post_offices=PostOffice.query.count(),
                   countries=CountryInfo.query.count(),
                   products=StoreProduct.query.count(),
                   releases=NewsArticle.query.count(),
                   shipments=Shipment.query.count(),
                   users=User.query.count())


def _news_query(kind):
    """Newsroom listing order: newest first, ties broken by seed id so the
    listing is fully deterministic (the two 2026-09-25 releases are
    ordered the same way every render)."""
    return NewsArticle.query.filter_by(kind=kind) \
        .order_by(NewsArticle.date.desc(), NewsArticle.id.asc())


@app.route('/')
def home():
    releases = [_clean_article(a) for a in _news_query('release').limit(4).all()]
    alerts = [_clean_article(a) for a in _news_query('alert').limit(3).all()]
    stamps = StoreProduct.query.filter(StoreProduct.category.ilike('stamps%')) \
        .order_by(StoreProduct.id).limit(6).all()
    services = ServiceInfo.query.filter(ServiceInfo.family.in_(
        ['express', 'priority', 'ground', 'first_class'])).all()
    return render_template(
        'home.html', releases=releases, alerts=alerts, stamps=stamps,
        services=services,
        hero_slides=[
            'images/chrome/pme-supplies-26.jpg',
            'images/chrome/sept26-stamps.jpg',
            'images/chrome/hold-mail_couple-hugging-after-hiking.jpg',
            'images/chrome/supplies-boxes-clr.jpg',
        ], **_ctx())


CONTENT_SECTIONS = ('ship', 'manage', 'international', 'help', 'business',
                    'shop', 'holiday')


@app.route('/<any(%s):section>/<path:page_path>' % ','.join(CONTENT_SECTIONS))
def content_page(section, page_path):
    page = ContentPage.query.filter_by(path=f"{section}/{page_path}").first()
    if page is None:
        abort(404)
    sections = _sanitize_html(_fix_mojibake(json.loads(page.body or '[]')))
    return render_template('content_page.html', page=_clean_page(page),
                           sections=sections,
                           **_ctx())


# ------------------------------------------------------------------ tracking --

@app.route('/tracking/', methods=['GET', 'POST'])
def tracking_home():
    number = None
    if request.method == 'POST':
        number = re.sub(r"[^A-Za-z0-9]", "",
                        request.form.get('tracking', '')).upper()
        if number:
            return redirect(url_for('tracking_result', number=number))
    return render_template('tracking_home.html', number=number,
                           glossary=TRACK_STATUS_GLOSSARY, **_ctx())


@app.route('/tracking/results')
def tracking_redirect():
    number = re.sub(r"[^A-Za-z0-9]", "", request.args.get('tracking', '')).upper()
    if not number:
        return redirect(url_for('tracking_home'))
    return redirect(url_for('tracking_result', number=number))


@app.route('/tracking/<number>')
def tracking_result(number):
    number = re.sub(r"[^A-Za-z0-9]", "", number).upper()
    shipment = Shipment.query.filter_by(tracking_number=number).first()
    events = []
    if shipment:
        events = ScanEvent.query.filter_by(shipment_id=shipment.id) \
            .order_by(ScanEvent.seq.desc()).all()
    return render_template('tracking_result.html', number=number,
                           shipment=shipment, events=events,
                           glossary=TRACK_STATUS_GLOSSARY, **_ctx())


@app.route('/account/saved/tracking', methods=['POST'])
@login_required
def save_tracking():
    number = re.sub(r"[^A-Za-z0-9]", "",
                    request.form.get('tracking', '')).upper()
    label = (request.form.get('label') or '').strip()[:60]
    if number:
        exists = SavedTracking.query.filter_by(
            user_id=current_user.id, tracking_number=number).first()
        if not exists:
            db.session.add(SavedTracking(
                user_id=current_user.id, tracking_number=number,
                label=label or number, created_at=MIRROR_TODAY.isoformat()))
            db.session.commit()
            flash('Tracking number saved to your account.')
    return redirect(url_for('tracking_result', number=number))


# ------------------------------------------------------------------ postcalc --

@app.route('/postcalc/')
def postcalc_home():
    return render_template('postcalc_home.html', **_ctx())


def _fcm_price(kind, ounces):
    table = {'stamped': 'fcm_letters_stamped',
             'metered': 'fcm_letters_metered',
             'flats': 'fcm_large_envelopes_flats',
             'postcards': 'fcm_postcards'}
    code = table[kind]
    rows = Rate.query.filter_by(table_code=code) \
        .order_by(Rate.weight).all()
    for row in rows:
        if ounces <= row.weight:
            return row
    return rows[-1] if rows else None


@app.route('/postcalc/letters', methods=['GET', 'POST'])
def postcalc_letters():
    result = None
    form = {}
    if request.method == 'POST':
        shape = request.form.get('shape', 'stamped')
        ounces = request.form.get('ounces', '1')
        oz = positive_number(ounces, 13)
        if shape not in ('stamped', 'metered', 'flats', 'postcards'):
            abort(400, description='Choose a valid mail shape.')
        form = {'shape': shape, 'ounces': ounces}
        if oz <= 0 or oz > 13:
            result = {'error': 'Enter a weight between 0 and 13 oz.'}
        elif shape in ('stamped', 'metered') and oz > 3.5:
            result = {'error': 'First-Class Mail letters over 3.5 oz must be '
                               'sent as a large envelope (flat). Choose the '
                               'large envelope shape.'}
        elif shape == 'flats' and oz > 13:
            result = {'error': 'Large envelopes (flats) cannot exceed 13 oz.'}
        elif shape == 'postcards':
            row = Rate.query.filter_by(table_code='fcm_postcards').first()
            result = {'rows': [('Postcards', row.price)]} if row else \
                {'error': 'No price found.'}
        else:
            kind = {'stamped': 'stamped', 'metered': 'metered',
                    'flats': 'flats'}[shape]
            row = _fcm_price(kind, oz)
            if row:
                label = ('Large Envelope (Flat)' if shape == 'flats'
                         else 'Letter')
                result = {'rows': [(f'First-Class Mail {label}', row.price)],
                          'weight': oz}
            else:
                result = {'error': 'No price found for that weight.'}
    return render_template('postcalc_letters.html', result=result, form=form,
                           **_ctx())


@app.route('/postcalc/packages', methods=['GET', 'POST'])
def postcalc_packages():
    result = None
    form = {}
    if request.method == 'POST':
        weight = positive_number(request.form.get('weight', '1'))
        zone = valid_zone(request.form.get('zone', '4'))
        form = {'weight': request.form.get('weight', '1'), 'zone': zone}
        if weight <= 0 or weight > 70:
            result = {'error': 'Enter a weight between 0 and 70 lbs.'}
        else:
            rows = []
            for code, label in (('pme', 'Priority Mail Express'),
                                ('pm', 'Priority Mail'),
                                ('ga', 'USPS Ground Advantage')):
                price = _price_for(code, weight, zone)
                if price:
                    rows.append((label, price))
            mm = Rate.query.filter_by(table_code='mm') \
                .order_by(Rate.weight).all()
            for row in mm:
                if weight <= row.weight:
                    rows.append(('Media Mail (books & media only)', row.price))
                    break
            flat = FlatRateItem.query.filter_by(scope='domestic',
                                                service='Priority Mail').all()
            # canonical Notice-123 service order (Express, Priority, Ground,
            # Media) instead of price-sorted rows — the cheapest option must
            # be found by reading the prices, not by reading the first row
            # (reviewer F-13)
            result = {'rows': rows,
                      'weight': weight, 'zone': zone,
                      'flat_rate': flat}
    return render_template('postcalc_packages.html', result=result, form=form,
                           **_ctx())


@app.route('/postcalc/international', methods=['GET', 'POST'])
def postcalc_intl():
    result = None
    countries = CountryInfo.query.order_by(CountryInfo.name).all()
    # audit F-F: the country-listing "Calculate prices to <country>" link
    # carries ?country= — preselect it so the form matches the link.
    if request.method == 'GET' and request.args.get('country'):
        form = {'country': request.args.get('country'), 'weight': '1'}
        return render_template('postcalc_intl.html', result=None, form=form,
                               countries=countries, **_ctx())
    form = {}
    if request.method == 'POST':
        country_name = request.form.get('country', '')
        weight = positive_number(request.form.get('weight', '1'))
        form = {'country': country_name, 'weight': request.form.get('weight', '1')}
        country = CountryInfo.query.filter_by(name=country_name).first()
        if not country:
            result = {'error': 'Pick a destination country.'}
        else:
            rows = []
            pmi_group = int(country.pmi_group) if country.pmi_group.isdigit() else None
            pmei_group = int(country.pmei_group) if country.pmei_group.isdigit() else None
            if pmi_group and country.pmi_max_lbs.replace('.', '', 1).isdigit() and weight <= float(country.pmi_max_lbs):
                price = _price_for('pmi', weight, pmi_group)
                if price:
                    rows.append(('Priority Mail International', price))
            if pmei_group and country.pmei_max_lbs.replace('.', '', 1).isdigit() and weight <= float(country.pmei_max_lbs):
                price = _price_for('pmei', weight, pmei_group)
                if price:
                    rows.append(('Priority Mail Express International', price))
            fcpis_group = int(country.fcpis_group) \
                if country.fcpis_group.isdigit() else None
            if fcpis_group and weight <= 4:
                ounces = weight * 16
                rows2 = Rate.query.filter_by(table_code='fcpis').all()
                for row in rows2:
                    hi = row.weight_hi if row.weight_hi else row.weight
                    if ounces <= hi and (row.col == fcpis_group):
                        rows.append(('First-Class Package International Service',
                                     row.price))
                        break
            if not rows:
                result = {'error':
                          'No retail service found for that country/weight — '
                          'check the country listing for availability and '
                          'weight limits.'}
            else:
                # insertion order = PMI, PMEI, FCPIS (canonical service
                # order, not price-sorted — see F-13)
                result = {'rows': rows,
                          'country': country, 'weight': weight}
    return render_template('postcalc_intl.html', result=result, form=form,
                           countries=countries, **_ctx())


@app.route('/postcalc/extra-services')
def postcalc_extras():
    domestic = {}
    for svc in ExtraService.query.filter_by(scope='domestic') \
            .order_by(ExtraService.category, ExtraService.id):
        # Legacy scraped PO Box rows collapsed fee groups into size columns.
        # The complete sourced fee matrix is rendered on /po-boxes/ instead.
        if svc.category.startswith('PO Box Service'):
            continue
        domestic.setdefault(svc.category, []).append(svc)
    intl = {}
    for svc in ExtraService.query.filter_by(scope='intl') \
            .order_by(ExtraService.category, ExtraService.id):
        intl.setdefault(svc.category, []).append(svc)
    return render_template('postcalc_extras.html', domestic=domestic,
                           intl=intl,
                           insurance_fee=lambda v: _band_fee('Insurance', v),
                           **_ctx())


# ---------------------------------------------------------------- clicknship --

@app.route('/clicknship/')
def clicknship_home():
    return render_template('clicknship_home.html', **_ctx())


CNS_SESSION_FIELDS = ['sender_name', 'sender_street', 'sender_city',
                      'sender_state', 'sender_zip', 'recipient_name',
                      'recipient_street', 'recipient_city', 'recipient_state',
                      'recipient_zip', 'weight_lbs', 'box_type', 'zone']


def _cns_from_form():
    """Only the fields this step's form actually posted.

    Later wizard steps must never blank the address fields captured at
    step 1 (reviewer F-7): updating with an empty default for missing
    keys erased them before.
    """
    return {k: request.form.get(k, '').strip()
            for k in CNS_SESSION_FIELDS if k in request.form}


@app.route('/clicknship/create', methods=['GET', 'POST'])
@login_required
def clicknship_create():
    step = request.args.get('step', '1')
    if step not in ('1', '2', '3'):
        abort(400, description='Choose a valid label step.')
    step = int(step)
    data = session.get('cns') or {}
    if request.method == 'POST':
        data.update(_cns_from_form())
        for extra in ('service', 'insured_value', 'insurance',
                      'signature', 'certified'):
            if extra in request.form:
                data[extra] = request.form.get(extra)
        _validate_cns_address(data)
        if step >= 2:
            _cns_options(data)
        session['cns'] = data
        step = min(step + 1, 3)
        return redirect(url_for('clicknship_create', step=step))
    if step >= 2:
        _validate_cns_address(data)
    if step == 3:
        data['options'] = _cns_options(data)
    return render_template(f'clicknship_step{step}.html', data=data,
                           steps=['Addresses', 'Package', 'Service & Pay'],
                           step=step, **_ctx())


@app.route('/clicknship/label', methods=['POST'])
@login_required
def clicknship_label():
    data = session.get('cns') or {}
    _validate_cns_address(data)
    weight = positive_number(data.get('weight_lbs'))
    zone = valid_zone(data.get('zone'))
    service = request.form.get('service', '')
    options = {code: (label, price) for code, label, price in _cns_options(data)}
    if service not in options or request.form.get('certified'):
        abort(400, description='Choose an available package service.')
    label, base = options[service]
    extras = []
    total = base or 0.0
    insured = 0.0
    if request.form.get('insurance'):
        insured = positive_number(request.form.get('insured_value'), 5000)
        fee = _band_fee('Insurance', insured)
        if fee:
            extras.append(f'Insurance (${insured:,.0f})')
            total += fee
    if request.form.get('signature'):
        fee = _flat_fee('Signature Confirmation',
                        prefer_labels=['Priority Mail',
                                        'USPS Ground Advantage—Retail'])
        if fee:
            extras.append('Signature Confirmation')
            total += fee
    if request.form.get('certified'):
        fee = _flat_fee('Certified Mail', needle='Certified Mail')
        if fee:
            extras.append('Certified Mail')
            total += fee
    seed_text = (json.dumps(data, sort_keys=True) + str(current_user.id)
                 + str(Shipment.query.count()))
    tracking = _tracking_number(seed_text)
    shipment = Shipment(
        tracking_number=tracking, user_id=current_user.id,
        service_code=service, sender_name=data.get('sender_name'),
        sender_city=data.get('sender_city'), sender_state=data.get('sender_state'),
        sender_zip=data.get('sender_zip'),
        recipient_name=data.get('recipient_name'),
        recipient_city=data.get('recipient_city'),
        recipient_state=data.get('recipient_state'),
        recipient_zip=data.get('recipient_zip'),
        weight_lbs=weight, ship_date=MIRROR_TODAY.isoformat(),
        status='Shipping Label Created',
        expected_date=(MIRROR_TODAY + timedelta(days=3)).isoformat(),
        insured_value=insured or None, extras=json.dumps(extras),
        signature_required=bool(request.form.get('signature')),
        is_cns=True, price_paid=round(total, 2), created_at=MIRROR_TODAY.isoformat())
    db.session.add(shipment)
    db.session.flush()
    db.session.add(ScanEvent(
        shipment_id=shipment.id,
        ts=f"{MIRROR_TODAY.isoformat()} 14:05",
        status=STATUS_FLOW['label_created'], status_code='label_created',
        facility=f"{data.get('sender_city')}, {data.get('sender_state')}",
        seq=0))
    db.session.commit()
    session.pop('cns', None)
    return render_template('clicknship_label.html', shipment=shipment,
                           label=label, extras=extras, **_ctx())


# -------------------------------------------------------------------- pickup --

@app.route('/pickup/', methods=['GET', 'POST'])
def pickup_home():
    result = None
    if request.method == 'POST':
        address = ', '.join(filter(None, [
            request.form.get('street', '').strip(),
            request.form.get('city', '').strip(),
            request.form.get('state', '').strip(),
            request.form.get('zip', '').strip()]))
        date_val = request.form.get('pickup_date', '')
        count = request.form.get('package_count', '1')
        errors = []
        if not request.form.get('street') or not request.form.get('city') \
                or not request.form.get('state') or not request.form.get('zip'):
            errors.append('Enter a complete pickup address.')
        try:
            scheduled = date.fromisoformat(date_val)
            if scheduled < MIRROR_TODAY or scheduled.weekday() == 6:
                errors.append('Choose a future pickup date other than Sunday.')
        except ValueError:
            errors.append('Choose a valid pickup date.')
        if not count.isdigit() or not 1 <= int(count) <= 99:
            errors.append('Enter a positive package count.')
        try:
            weight = float(request.form.get('weight', ''))
            if not math.isfinite(weight) or weight <= 0:
                errors.append('Enter a positive package weight.')
        except ValueError:
            errors.append('Enter a valid package weight.')
        if not re.fullmatch(r'\d{5}', request.form.get('zip', '')):
            errors.append('Enter a five-digit ZIP code.')
        if not request.form.getlist('services'):
            errors.append('Select the package services.')
        if errors:
            result = {'errors': errors}
        else:
            packages = [{'count': count,
                         'est_weight': request.form.get('weight', ''),
                         'services': request.form.getlist('services')}]
            confirmation = _number_for('PKG-',
                                       json.dumps(dict(request.form), sort_keys=True).replace(request.form.get('csrf_token', ''), '') + str(current_user.id if current_user.is_authenticated else None))
            # Idempotent on identical requests (reviewer F-11): the
            # confirmation number is a pure function of the form inputs,
            # so re-submitting the same pickup returns the existing
            # request instead of dying on the UNIQUE constraint.
            pickup = PickupRequest.query.filter_by(
                confirmation=confirmation).first()
            if pickup is None:
                pickup = PickupRequest(
                    user_id=current_user.id if current_user.is_authenticated else None,
                    confirmation=confirmation, pickup_date=date_val,
                    address=address,
                    phone=request.form.get('phone', ''),
                    email=request.form.get('email', ''),
                    packages=json.dumps(packages),
                    instructions=request.form.get('instructions', '')[:200],
                    status='Scheduled', created_at=MIRROR_TODAY.isoformat())
                db.session.add(pickup)
                db.session.commit()
            result = {'confirmation': confirmation, 'date': date_val,
                      'address': address}
    return render_template('pickup.html', result=result,
                           today=MIRROR_TODAY.isoformat(), **_ctx())


# ------------------------------------------------------------------ locations --

@app.route('/locations/')
def locations_home():
    q = request.args.get('q', '').strip()
    service = request.args.get('service', '').strip()
    results = []
    total = 0
    truncated = False
    if q:
        # A bare 2-letter query is a state code (reviewer F-10): match the
        # state exactly so 'DE' means Delaware, never '%de%' fuzzy hits
        # like Deering AK. ZIP prefixes are also matched exactly.
        if re.fullmatch(r'[A-Za-z]{2}', q):
            query = PostOffice.query.filter(
                db.func.upper(PostOffice.state) == q.upper())
        elif q[:1].isdigit():
            query = PostOffice.query.filter(PostOffice.zip5.like(q + '%'))
        else:
            ql = f"%{q.lower()}%"
            query = PostOffice.query.filter(db.and_(
                db.or_(db.func.lower(PostOffice.name).like(ql),
                       db.func.lower(PostOffice.city).like(ql),
                       PostOffice.zip5.like(q + '%'),
                       db.func.lower(PostOffice.state).like(ql))))
        if service:
            query = query.filter(PostOffice.services.ilike(f'%{service}%'))
        total = query.count()
        ordered = query.order_by(PostOffice.state, PostOffice.name)
        if re.fullmatch(r'[A-Za-z]{2}', q) or q[:1].isdigit():
            # state / ZIP searches are shown in full — every match is
            # countable from the table (F-10: no hidden 60-row cap)
            results = ordered.all()
        else:
            # fuzzy text searches stay bounded for page weight; the note
            # on the page tells the visitor and suggests a state/ZIP search
            results = ordered.limit(200).all()
            truncated = total > len(results)
    return render_template('locations_home.html', q=q, service=service,
                           results=results, total=total,
                           truncated=truncated,
                           service_filters=['Passport Photos',
                                            'Self-Service Kiosk',
                                            'Po Box Rental'], **_ctx())


@app.route('/locations/<po_key>')
def location_detail(po_key):
    po = PostOffice.query.filter_by(po_key=po_key).first_or_404()
    hours = json.loads(po.hours or '{}')
    services = json.loads(po.services or '[]')
    rentals = PoBoxRental.query.filter_by(po_id=po.id).count()
    return render_template('location_detail.html', po=po, hours=hours,
                           services=services, rentals=rentals, **_ctx())


# -------------------------------------------------------------------- po box --

@app.route('/po-boxes/')
def po_boxes():
    fees = {}
    for row in PoBoxFee.query.filter_by(fee_group='2').order_by(PoBoxFee.schedule, PoBoxFee.size_label):
        # audit F-E: the scraper captured the upstream fee-schedule header
        # ("Fee Group") as a data row — skip non-size labels at render time
        if not row.size_label.strip().isdigit():
            continue
        fees.setdefault(row.schedule, []).append(row)
    page = ContentPage.query.filter_by(path='manage/po-boxes.htm').first()
    return render_template('po_boxes.html', fees=fees,
                           page=_clean_page(page), **_ctx())


@app.route('/po-boxes/reserve/<po_key>', methods=['GET', 'POST'])
def po_box_reserve(po_key):
    po = PostOffice.query.filter_by(po_key=po_key).first_or_404()
    result = None
    sizes = ['1', '2', '3', '4', '5']
    if request.method == 'POST':
        size = request.form.get('size', '2')
        period = request.form.get('period', '6 months')
        schedule = 'market_dominant_6mo' if period == '6 months' \
            else 'market_dominant_3mo'
        fee_row = PoBoxFee.query.filter_by(schedule=schedule,
                                           size_label=size, fee_group=po.fee_group).first()
        fee = fee_row.fee if fee_row else None
        if fee is None or size not in sizes or period not in ('3 months', '6 months') or not po.has_po_boxes:
            result = {'errors': ['That box size is not available at this '
                                 'Post Office.']}
        else:
            digest = hashlib.sha256(
                f"{po_key}|{size}|{period}|{PoBoxRental.query.count()}".encode()).hexdigest()
            box_number = f"{int(digest[:4], 16) % 9000 + 1000}"
            rental = PoBoxRental(
                user_id=current_user.id if current_user.is_authenticated else None,
                po_id=po.id, box_number=box_number, size_label=size,
                fee_paid=fee, pay_period=period, status='Reserved',
                expires_on=(MIRROR_TODAY + timedelta(days=183 if period == '6 months' else 92)).isoformat(),
                created_at=MIRROR_TODAY.isoformat())
            db.session.add(rental)
            db.session.commit()
            result = {'box_number': box_number, 'fee': fee, 'period': period}
    return render_template('po_box_reserve.html', po=po, result=result,
                           sizes=sizes, **_ctx())


# ---------------------------------------------------------------------- store --

def _stamp_products():
    """Every stamp product across the stamp categories, including the
    featured Breast Cancer Research sheet (reviewer F-9): the All Stamps
    category is a browsable union, not an empty page."""
    return StoreProduct.query.filter(
        db.or_(StoreProduct.category.ilike('stamps%'),
               StoreProduct.category == 'featured')) \
        .order_by(StoreProduct.id).all()


@app.route('/store/')
def store_home():
    cats = [('stamps-new-releases', 'New Releases'),
            ('stamps-all', 'All Stamps'),
            ('shipping-supplies-priority-mail', 'Priority Mail Supplies'),
            ('shipping-supplies-priority-mail-express', 'Priority Mail Express Supplies'),
            ('cards-envelopes', 'Cards & Envelopes'),
            ('gifts-collectors', 'Collectibles & Gifts')]
    featured = StoreProduct.query.filter_by(category='stamps-new-releases') \
        .limit(8).all()
    return render_template('store_home.html', cats=cats, featured=featured,
                           **_ctx())


@app.route('/store/stamps')
def store_stamps():
    products = _stamp_products()
    return render_template('store_category.html', category='stamps',
                           title='Stamps', products=products, **_ctx())


@app.route('/store/<category>')
def store_category(category):
    if category == 'stamps-all':
        # All Stamps = the full stamp union (incl. the featured Breast
        # Cancer Research sheet) — previously this page was empty because
        # no product carried the literal category (reviewer F-9)
        products = _stamp_products()
    else:
        products = StoreProduct.query.filter_by(category=category) \
            .order_by(StoreProduct.id).all()
    names = {
        'stamps-new-releases': 'New Stamp Releases',
        'stamps-all': 'All Stamps',
        'shipping-supplies-priority-mail': 'Priority Mail Shipping Supplies',
        'shipping-supplies-priority-mail-express': 'Priority Mail Express Shipping Supplies',
        'cards-envelopes': 'Cards & Envelopes',
        'gifts-collectors': 'Collectibles & Gifts',
        'featured': 'Featured Products',
    }
    return render_template('store_category.html', category=category,
                           title=names.get(category, 'Store'),
                           products=products, **_ctx())


@app.route('/store/product/<slug>')
def store_product(slug):
    product = StoreProduct.query.filter_by(slug=slug).first_or_404()
    gallery = json.loads(product.gallery or '[]')
    related = StoreProduct.query.filter(
        StoreProduct.category == product.category,
        StoreProduct.id != product.id).limit(4).all()
    return render_template('store_product.html', product=product,
                           gallery=gallery, related=related, **_ctx())


@app.route('/store/cart')
def store_cart():
    key = _cart_key()
    rows = CartItem.query.filter_by(cart_key=key).all()
    items = []
    total = 0.0
    for row in rows:
        product = db.session.get(StoreProduct, row.product_id)
        if not product:
            continue
        line = row.qty * (product.price or 0)
        total += line
        items.append({'row': row, 'product': product, 'line': line})
    return render_template('store_cart.html', items=items, total=total,
                           **_ctx())


@app.route('/store/cart/add', methods=['POST'])
def store_cart_add():
    product = StoreProduct.query.filter_by(
        sku=request.form.get('sku', '')).first()
    qty = positive_number(request.form.get('qty', '1'), 99)
    if not qty.is_integer():
        abort(400, description='Quantity must be a whole number.')
    qty = int(qty)
    if product:
        key = _cart_key()
        row = CartItem.query.filter_by(cart_key=key,
                                       product_id=product.id).first()
        if row:
            row.qty += qty
        else:
            db.session.add(CartItem(cart_key=key, product_id=product.id,
                                    qty=qty))
        db.session.commit()
        flash(f'Added {qty} × {product.name} to your cart.')
    return redirect(url_for('store_cart'))


@app.route('/store/cart/remove', methods=['POST'])
def store_cart_remove():
    key = _cart_key()
    row = CartItem.query.filter_by(cart_key=key,
                                   id=request.form.get('row', type=int)).first()
    if row:
        db.session.delete(row)
        db.session.commit()
    return redirect(url_for('store_cart'))


@app.route('/store/checkout', methods=['GET', 'POST'])
def store_checkout():
    key = _cart_key()
    rows = CartItem.query.filter_by(cart_key=key).all()
    if not rows:
        return redirect(url_for('store_cart'))
    if request.method == 'POST':
        items = []
        total = 0.0
        for row in rows:
            product = db.session.get(StoreProduct, row.product_id)
            if not product:
                continue
            items.append({'sku': product.sku, 'name': product.name,
                          'qty': row.qty, 'price': product.price})
            total += row.qty * (product.price or 0)
        # audit fix (ordinal 57): round the money total — floating-point
        # sums like 20.0 + 2*16.4 + 16.4 were stored as 69.19999999999999
        total = round(total, 2)
        order_number = _number_for(
            'W', key + MIRROR_TODAY.isoformat()
            + str(StoreOrder.query.count()))
        order = StoreOrder(order_number=order_number,
                           user_id=current_user.id
                           if current_user.is_authenticated else None,
                           email=request.form.get('email', ''),
                           status='Processing', total=total,
                           placed_at=MIRROR_TODAY.isoformat(),
                           items=json.dumps(items))
        db.session.add(order)
        CartItem.query.filter_by(cart_key=key).delete()
        db.session.commit()
        return render_template('store_order.html', order=order, **_ctx())
    total = sum((db.session.get(StoreProduct, r.product_id).price or 0) * r.qty
                for r in rows)
    return render_template('store_checkout.html', total=total, **_ctx())


# --------------------------------------------------------------------- hold --

@app.route('/manage/hold-mail.htm')
def hold_mail_page():
    page = ContentPage.query.filter_by(path='manage/hold-mail.htm').first()
    return render_template('hold_mail.html', page=_clean_page(page), **_ctx())


@app.route('/manage/hold-mail/request', methods=['GET', 'POST'])
@login_required
def hold_mail_request():
    result = None
    if request.method == 'POST':
        start = request.form.get('start_date', '')
        end = request.form.get('end_date', '')
        option = request.form.get('option', '')
        errors = []
        try:
            s = datetime.strptime(start, '%Y-%m-%d').date()
            e = datetime.strptime(end, '%Y-%m-%d').date()
            if s < MIRROR_TODAY:
                errors.append('The hold start date cannot be in the past.')
            if not 3 <= (e - s).days + 1 <= 30:
                errors.append('USPS can hold mail for at least 3 and at most 30 days, including both dates.')
            if e < s:
                errors.append('The end date must be after the start date.')
        except ValueError:
            errors.append('Enter valid start and end dates.')
        if option not in ('Hold all mail, deliver on end date', 'Hold all mail, deliver on first business day after request', 'Hold all mail, pick up at Post Office'):
            errors.append('Choose how you want your mail delivered after the hold.')
        if errors:
            result = {'errors': errors}
        else:
            confirmation = _number_for('HLD-',
                                       f"{current_user.id}{start}{end}{option}")
            # Idempotent on identical requests (reviewer F-11)
            hold = HoldMailRequest.query.filter_by(
                confirmation=confirmation).first()
            if hold is None:
                hold = HoldMailRequest(
                    user_id=current_user.id, confirmation=confirmation,
                    start_date=start, end_date=end,
                    address=f"{current_user.street}, {current_user.city}, "
                            f"{current_user.state} {current_user.zip5}",
                    status='Active', option=option,
                    created_at=MIRROR_TODAY.isoformat())
                db.session.add(hold)
                db.session.commit()
            result = {'confirmation': confirmation, 'start': start,
                      'end': end, 'option': option}
    return render_template('hold_mail_request.html', result=result,
                           today=MIRROR_TODAY.isoformat(), **_ctx())


# ------------------------------------------------------------ change address --

@app.route('/manage/forward.htm')
def coa_page():
    page = ContentPage.query.filter_by(path='manage/forward.htm').first()
    premium = ContentPage.query.filter_by(
        path='manage/forward-premium.htm').first()
    return render_template('coa_page.html', page=_clean_page(page),
                           premium=_clean_page(premium),
                           fee=COA_IDENTITY_FEE, **_ctx())


@app.route('/manage/change-address/request', methods=['GET', 'POST'])
def coa_request():
    result = None
    if request.method == 'POST':
        move_type = request.form.get('move_type', 'Individual')
        if move_type == 'Family':
            move_type = 'Family (everyone with the same last name)'
        forward_type = request.form.get('forward_type', 'Regular')
        start = request.form.get('start_date', '')
        old_address = ', '.join(filter(None, [
            request.form.get('old_street', ''), request.form.get('old_city', ''),
            request.form.get('old_state', ''), request.form.get('old_zip', '')]))
        new_address = ', '.join(filter(None, [
            request.form.get('new_street', ''), request.form.get('new_city', ''),
            request.form.get('new_state', ''), request.form.get('new_zip', '')]))
        email = request.form.get('email', '')
        errors = []
        if move_type not in ('Individual', 'Family (everyone with the same last name)', 'Business') or forward_type != 'Regular':
            errors.append('Choose a supported move and forwarding type.')
        for prefix in ('old', 'new'):
            if not request.form.get(prefix + '_city', '').strip() or not request.form.get(prefix + '_state', '').strip() or not re.fullmatch(r'\d{5}', request.form.get(prefix + '_zip', '')):
                errors.append('Enter complete addresses with five-digit ZIP codes.')
        if not request.form.get('old_street') or not request.form.get('old_zip'):
            errors.append('Enter your old address.')
        if not request.form.get('new_street') or not request.form.get('new_zip'):
            errors.append('Enter your new address.')
        if not email or '@' not in email:
            errors.append('Enter a valid email address.')
        try:
            s = datetime.strptime(start, '%Y-%m-%d').date()
            if s < MIRROR_TODAY:
                errors.append('The forwarding start date cannot be in the past.')
        except ValueError:
            errors.append('Enter a valid forwarding start date.')
        if errors:
            result = {'errors': errors}
        else:
            confirmation = _number_for(
                'COA-', f"{current_user.id if current_user.is_authenticated else None}|{email}|{old_address}|{move_type}|{forward_type}|{start}|{new_address}")
            # Idempotent on identical requests (reviewer F-11)
            coa = ChangeOfAddress.query.filter_by(
                confirmation=confirmation).first()
            if coa is None:
                coa = ChangeOfAddress(
                    user_id=current_user.id if current_user.is_authenticated else None,
                    confirmation=confirmation, move_type=move_type,
                    forward_type=forward_type, start_date=start,
                    old_address=old_address, new_address=new_address,
                    email=email, status='Active', fee=COA_IDENTITY_FEE,
                    created_at=MIRROR_TODAY.isoformat())
                db.session.add(coa)
                db.session.commit()
            result = {'confirmation': confirmation, 'move_type': move_type,
                      'forward_type': forward_type, 'start': start,
                      'fee': COA_IDENTITY_FEE}
    return render_template('coa_request.html', result=result,
                           today=MIRROR_TODAY.isoformat(),
                           fee=COA_IDENTITY_FEE, **_ctx())


# ----------------------------------------------------------------- countries --

@app.route('/international/countries')
def countries_index():
    q = request.args.get('q', '').strip().lower()
    query = CountryInfo.query
    if q:
        query = query.filter(CountryInfo.name.ilike(f'%{q}%'))
    countries = query.order_by(CountryInfo.name).all()
    return render_template('countries_index.html', countries=countries,
                           q=q, **_ctx())


@app.route('/international/countries/<slug>')
def country_detail(slug):
    country = CountryInfo.query.filter_by(slug=slug).first_or_404()
    prohibitions = json.loads(country.prohibitions or '[]')
    restrictions = json.loads(country.restrictions or '[]')
    observations = json.loads(country.observations or '[]')
    services = json.loads(country.services or '{}')
    return render_template('country_detail.html', country=country,
                           prohibitions=prohibitions,
                           restrictions=restrictions,
                           observations=observations,
                           services=services, **_ctx())


# --------------------------------------------------------------------- claims --

@app.route('/help/claims.htm')
def claims_page():
    page = ContentPage.query.filter_by(path='help/claims.htm').first()
    fee_rows = ExtraService.query.filter_by(category='Insurance') \
        .order_by(ExtraService.id).all()
    return render_template('claims_page.html', page=_clean_page(page),
                           fee_rows=fee_rows, **_ctx())


@app.route('/claims/file', methods=['GET', 'POST'])
@login_required
def claim_file():
    result = None
    shipments = Shipment.query.filter(
        Shipment.user_id == current_user.id,
        Shipment.insured_value.isnot(None)).order_by(
        Shipment.ship_date.desc()).all()
    if request.method == 'POST':
        tracking = request.form.get('tracking', '')
        shipment = Shipment.query.filter_by(tracking_number=tracking).first()
        errors = []
        if not shipment or shipment.user_id != current_user.id:
            errors.append('Pick one of your insured shipments.')
        elif not shipment.insured_value:
            errors.append('Only insured mailpieces can be claimed — '
                          'this shipment carries no insurance.')
        else:
            kind = request.form.get('kind', 'damage')
            note = request.form.get('note', '')[:400]
            docs = request.form.getlist('docs')
            if not docs or not set(docs) <= {'Proof of insurance (Click-N-Ship receipt)', 'Photos of damaged packaging and item', 'Purchase receipt'}:
                errors.append('Select the supporting documents you will provide.')
            if not note.strip() or not request.form.get('article', '').strip() or kind not in ('damage', 'loss'):
                errors.append('Describe the article and choose damage or loss.')
            if errors:
                result = {'errors': errors}
            else:
                claim_number = _number_for(
                    'CLM-', f"{tracking}{kind}{current_user.id}")
                # Idempotent on identical requests (reviewer F-11)
                claim = Claim.query.filter_by(
                    claim_number=claim_number).first()
                if claim is None:
                    claim = Claim(claim_number=claim_number,
                                  user_id=current_user.id,
                                  tracking_number=tracking, kind=kind,
                                  article=request.form.get('article', '')[:180],
                                  amount=shipment.insured_value, status='Received',
                                  filed_at=MIRROR_TODAY.isoformat(),
                                  docs=json.dumps(docs), events=json.dumps([
                                      {'date': MIRROR_TODAY.isoformat(),
                                       'note': 'Claim received; awaiting '
                                               'supporting documentation review.'}]),
                                  note=note)
                    db.session.add(claim)
                    db.session.commit()
                result = {'claim_number': claim_number,
                          'tracking': tracking,
                          'amount': shipment.insured_value}
    if request.method == 'POST' and errors:
        result = {'errors': errors}
    return render_template('claim_file.html', result=result,
                           shipments=shipments, **_ctx())


@app.route('/claims/status', methods=['GET', 'POST'])
@login_required
def claim_status():
    result = None
    if request.method == 'POST':
        number = request.form.get('claim_number', '').strip().upper()
        claim = Claim.query.filter_by(claim_number=number, user_id=current_user.id).first()
        if claim:
            return redirect(url_for('claim_detail', number=number))
        result = {'error': f'No claim found for {number}.'}
    return render_template('claim_status.html', result=result, **_ctx())


@app.route('/claims/<number>')
@login_required
def claim_detail(number):
    claim = Claim.query.filter_by(claim_number=number.upper(), user_id=current_user.id).first_or_404()
    docs = json.loads(claim.docs or '[]')
    events = json.loads(claim.events or '[]')
    return render_template('claim_detail.html', claim=claim, docs=docs,
                           events=events, **_ctx())


# ------------------------------------------------------------------ newsroom --

@app.route('/newsroom/')
def newsroom():
    releases = [_clean_article(a) for a in _news_query('release').all()]
    return render_template('newsroom.html', articles=releases, **_ctx())


@app.route('/newsroom/<slug>')
def news_article(slug):
    article = NewsArticle.query.filter_by(slug=slug).first_or_404()
    paragraphs = [p for p in _sanitize_html(_fix_mojibake(json.loads(article.body or '[]'))) if not re.fullmatch(r'%[\w-]+%', str(p).strip())]
    images = _fix_mojibake(json.loads(article.images or '[]'))
    return render_template('news_article.html', article=_clean_article(article),
                           paragraphs=paragraphs, images=images, **_ctx())


@app.route('/newsroom/service-alerts')
def service_alerts():
    alerts = [_clean_article(a) for a in _news_query('alert').all()]
    return render_template('service_alerts.html', alerts=alerts, **_ctx())


# -------------------------------------------------------------------- account --

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            target = request.args.get('next', '')
            parsed = urlsplit(target)
            return redirect(target if target.startswith('/') and not target.startswith('//') and not parsed.netloc and not parsed.scheme and '\\' not in target else url_for('account'))
        flash('Invalid email or password.')
    return render_template('login.html', **_ctx())


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/account')
@login_required
def account():
    shipments = Shipment.query.filter_by(user_id=current_user.id) \
        .order_by(Shipment.created_at.desc()).all()
    active = [s for s in shipments
              if s.status not in ('Delivered',)]
    delivered = [s for s in shipments if s.status == 'Delivered']
    orders = StoreOrder.query.filter_by(user_id=current_user.id) \
        .order_by(StoreOrder.placed_at.desc()).all()
    claims = Claim.query.filter_by(user_id=current_user.id).all()
    pickups = PickupRequest.query.filter_by(user_id=current_user.id) \
        .order_by(PickupRequest.pickup_date.desc()).all()
    holds = HoldMailRequest.query.filter_by(user_id=current_user.id).all()
    coas = ChangeOfAddress.query.filter_by(user_id=current_user.id).all()
    saved = SavedTracking.query.filter_by(user_id=current_user.id).all()
    rentals = PoBoxRental.query.filter_by(user_id=current_user.id).all()
    return render_template('account.html', active=active, delivered=delivered,
                           orders=orders, claims=claims, pickups=pickups,
                           holds=holds, coas=coas, saved=saved,
                           rentals=rentals, **_ctx())


@app.route('/account/informed-delivery')
@login_required
def informed_delivery():
    pieces = InformedMailPiece.query.filter_by(user_id=current_user.id) \
        .order_by(InformedMailPiece.mail_date.desc()).all()
    return render_template('informed_delivery.html', pieces=pieces, **_ctx())


# --------------------------------------------------------------------- search --

@app.route('/search/')
def site_search():
    q = request.args.get('q', '').strip()
    results = []
    if q:
        ql = f"%{q.lower()}%"
        pages = ContentPage.query.filter(db.or_(
            db.func.lower(ContentPage.title).like(ql),
            db.func.lower(ContentPage.body).like(ql))).limit(12).all()
        products = StoreProduct.query.filter(db.or_(
            db.func.lower(StoreProduct.name).like(ql),
            db.func.lower(StoreProduct.description).like(ql))).limit(12).all()
        offices = PostOffice.query.filter(db.or_(
            db.func.lower(PostOffice.name).like(ql),
            PostOffice.zip5.like(q + '%'))).limit(12).all()
        countries = CountryInfo.query.filter(
            CountryInfo.name.ilike(f'%{q}%')).limit(12).all()
        news = NewsArticle.query.filter(db.or_(
            db.func.lower(NewsArticle.title).like(ql),
            db.func.lower(NewsArticle.body).like(ql))).limit(12).all()
        results = [('Pages', [_clean_page(p) for p in pages]),
                   ('Store Products', products),
                   ('Post Offices', offices), ('Countries', countries),
                   ('Newsroom', [_clean_article(a) for a in news])]
    return render_template('search.html', q=q, results=results, **_ctx())


# ---------------------------------------------------------------------- main --

def main():
    with app.app_context():
        db.create_all()
        seed_pages()
        seed_pricing()
        seed_services()
        seed_news()
        seed_countries()
        seed_post_offices()
        seed_store()
        seed_shipments()
        seed_benchmark_users()


with app.app_context():
    db.create_all()
    seed_pages()
    seed_pricing()
    seed_services()
    seed_news()
    seed_countries()
    seed_post_offices()
    seed_store()
    seed_shipments()
    seed_benchmark_users()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 40129))
    app.run(host='0.0.0.0', port=port, debug=False)
