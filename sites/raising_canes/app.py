#!/usr/bin/env python3
"""Raising Cane's mirror — Flask application.

Mirrors raisingcanes.com and its real ordering / merch / careers / locations
properties: menu browsing with nutrition and allergen data (official upstream
PDF), the Olo-style order-ahead chain (restaurant picker, product customization
with quantities and drink choices, cart, pickup/curbside checkout, gift-card
and Caniac Club offer redemption, confirmation with order number), the Cane's
Gear shop (collections, variants, cart, checkout with free shipping over $50),
location finder over the real 996-restaurant network with per-day dine-in and
drive-thru hours, gift-card balance check, Caniac Club accounts, careers search
over real openings, FAQ, news and promotions. All data is real, captured from
the upstream properties (see source_data.json provenance).
"""
import json
import os
import re
from datetime import date, datetime

from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import func

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config['SECRET_KEY'] = 'webharbor-raising-canes-dev-key'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'raising_canes.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

csrf = CSRFProtect(app)
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to access your account.'
login_manager.login_message_category = 'info'

app.jinja_env.filters['from_json'] = json.loads

# Deterministic reference date: upstream data was captured 2026-09-24 and all
# seeded dates (news, orders, gift cards) are pinned relative to it.
MIRROR_REFERENCE_DATE = date(2026, 9, 24)

STOP_WORDS = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or',
              'is', 'it', 'by', 'with', 'my', 'your', 'our'}

FOOD_TAX_RATE = 0.0825          # real rate served by the upstream Olo vendor
GEAR_FREE_SHIPPING_THRESHOLD = 50.00
GEAR_FLAT_SHIPPING = 6.95


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), default='')
    created_at = db.Column(db.DateTime, default=datetime(2026, 1, 15))

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)


class Address(db.Model):
    __tablename__ = 'addresses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    label = db.Column(db.String(60), default='Home')
    line1 = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    is_default = db.Column(db.Boolean, default=False)


class PaymentCard(db.Model):
    __tablename__ = 'payment_cards'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    label = db.Column(db.String(60), default='Personal')
    brand = db.Column(db.String(30), nullable=False)
    last4 = db.Column(db.String(4), nullable=False)
    exp_month = db.Column(db.Integer, nullable=False)
    exp_year = db.Column(db.Integer, nullable=False)
    is_default = db.Column(db.Boolean, default=False)


class MenuCategory(db.Model):
    __tablename__ = 'menu_categories'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, default='')
    sort = db.Column(db.Integer, default=0)


class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(140), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('menu_categories.id'), nullable=False)
    description = db.Column(db.Text, default='')
    base_calories = db.Column(db.Integer)
    max_calories = db.Column(db.Integer)
    base_price = db.Column(db.Float)           # single-unit price when sold per unit
    image = db.Column(db.String(200), default='')
    sort = db.Column(db.Integer, default=0)

    category = db.relationship('MenuCategory', backref='items')

    def calorie_label(self):
        if self.base_calories is None:
            return ''
        if self.max_calories and self.max_calories != self.base_calories:
            return f"{self.base_calories} - {self.max_calories} Cal"
        return f"{self.base_calories} Cal"


class MenuOptionGroup(db.Model):
    __tablename__ = 'menu_option_groups'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    mandatory = db.Column(db.Boolean, default=True)
    multi = db.Column(db.Boolean, default=False)   # allow multiple selections
    quantity_label = db.Column(db.String(40))       # shown only for this quantity choice
    sort = db.Column(db.Integer, default=0)

    options = db.relationship('MenuOption', backref='group',
                              order_by='MenuOption.sort', lazy=True)


class MenuOption(db.Model):
    __tablename__ = 'menu_options'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('menu_option_groups.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    price_delta = db.Column(db.Float, default=0.0)
    sort = db.Column(db.Integer, default=0)


class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    name = db.Column(db.String(120), default="Raising Cane's Chicken Fingers")
    street = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(30), default='')
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    dine_in_hours = db.Column(db.Text, default='{}')
    drive_thru_hours = db.Column(db.Text, default='{}')
    amenities = db.Column(db.String(200), default='')
    offers = db.Column(db.String(120), default='')
    description = db.Column(db.Text, default='')

    def amenity_list(self):
        return [a for a in (self.amenities or '').split('|') if a]

    def offer_list(self):
        return [o for o in (self.offers or '').split('|') if o]

    def dine_hours(self):
        return json.loads(self.dine_in_hours or '{}')

    def drive_hours(self):
        return json.loads(self.drive_thru_hours or '{}')

    def address_line(self):
        return f"{self.street}, {self.city}, {self.state} {self.zip_code}"


class FavoriteLocation(db.Model):
    __tablename__ = 'favorite_locations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)


class GearProduct(db.Model):
    __tablename__ = 'gear_products'
    id = db.Column(db.Integer, primary_key=True)
    handle = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    product_type = db.Column(db.String(60), default='')
    collection = db.Column(db.String(80), default='')     # primary collection name
    price = db.Column(db.Float, nullable=False)          # lowest variant price
    description = db.Column(db.Text, default='')
    tags = db.Column(db.String(300), default='')
    image_main = db.Column(db.String(200), default='')
    image_alt = db.Column(db.String(200), default='')
    new_item = db.Column(db.Boolean, default=False)
    sort = db.Column(db.Integer, default=0)

    variants = db.relationship('GearVariant', backref='product',
                               order_by='GearVariant.price', lazy=True)

    def tag_list(self):
        return [t for t in (self.tags or '').split('|') if t]


class GearVariant(db.Model):
    __tablename__ = 'gear_variants'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('gear_products.id'), nullable=False)
    title = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    sku = db.Column(db.String(40), default='')
    available = db.Column(db.Boolean, default=True)


class FoodOrder(db.Model):
    __tablename__ = 'food_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    pickup_mode = db.Column(db.String(20), default='Pickup')   # Pickup / Curbside
    pickup_date = db.Column(db.String(20), default='')
    pickup_time = db.Column(db.String(20), default='')
    contact_name = db.Column(db.String(120), default='')
    contact_phone = db.Column(db.String(30), default='')
    payment_method = db.Column(db.String(60), default='')
    gift_card_number = db.Column(db.String(30), default='')
    caniac_offer = db.Column(db.String(80), default='')
    subtotal = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default='Placed')
    placed_at = db.Column(db.DateTime, default=datetime(2026, 9, 20, 12, 0))
    points_earned = db.Column(db.Integer, default=0)

    location = db.relationship('Location')
    items = db.relationship('FoodOrderItem', backref='order', lazy=True)


class FoodOrderItem(db.Model):
    __tablename__ = 'food_order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('food_orders.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)
    quantity_label = db.Column(db.String(40), default='1')
    selections = db.Column(db.Text, default='[]')   # JSON list of chosen option names
    line_total = db.Column(db.Float, default=0.0)

    menu_item = db.relationship('MenuItem')

    def selection_list(self):
        return json.loads(self.selections or '[]')


class GearOrder(db.Model):
    __tablename__ = 'gear_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    email = db.Column(db.String(120), default='')
    ship_name = db.Column(db.String(120), default='')
    ship_line1 = db.Column(db.String(200), default='')
    ship_city = db.Column(db.String(100), default='')
    ship_state = db.Column(db.String(50), default='')
    ship_zip = db.Column(db.String(20), default='')
    payment_method = db.Column(db.String(60), default='')
    subtotal = db.Column(db.Float, default=0.0)
    shipping = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    placed_at = db.Column(db.DateTime, default=datetime(2026, 9, 18, 10, 0))

    items = db.relationship('GearOrderItem', backref='order', lazy=True)


class GearOrderItem(db.Model):
    __tablename__ = 'gear_order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('gear_orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('gear_products.id'), nullable=False)
    variant_title = db.Column(db.String(80), default='Default Title')
    qty = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0.0)

    product = db.relationship('GearProduct')


class GiftCard(db.Model):
    __tablename__ = 'gift_cards'
    id = db.Column(db.Integer, primary_key=True)
    card_number = db.Column(db.String(20), unique=True, nullable=False)
    pin = db.Column(db.String(8), nullable=False)
    balance = db.Column(db.Float, nullable=False, default=0.0)
    initial_balance = db.Column(db.Float, nullable=False, default=0.0)
    owner_email = db.Column(db.String(120), default='')


class CaniacCard(db.Model):
    __tablename__ = 'caniac_cards'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    card_number = db.Column(db.String(20), unique=True, nullable=False)
    points = db.Column(db.Integer, default=0)
    member_since = db.Column(db.DateTime, default=datetime(2024, 3, 1))


class CaniacOffer(db.Model):
    __tablename__ = 'caniac_offers'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    discount_type = db.Column(db.String(20), default='percent')   # percent / dollars / free_item
    value = db.Column(db.Float, default=0.0)
    min_spend = db.Column(db.Float, default=0.0)
    active = db.Column(db.Boolean, default=True)


class UserOffer(db.Model):
    __tablename__ = 'user_offers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    offer_id = db.Column(db.Integer, db.ForeignKey('caniac_offers.id'), nullable=False)
    redeemed = db.Column(db.Boolean, default=False)
    redeemed_order = db.Column(db.String(30), default='')

    offer = db.relationship('CaniacOffer')


class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(40), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(80), default='')
    employment_type = db.Column(db.String(60), default='')
    street = db.Column(db.String(200), default='')
    city = db.Column(db.String(100), default='')
    state = db.Column(db.String(60), default='')
    state_abbr = db.Column(db.String(4), default='')
    zip_code = db.Column(db.String(20), default='')
    apply_url = db.Column(db.String(300), default='')


class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    published = db.Column(db.String(20), default='')
    category = db.Column(db.String(60), default="What's Happening")
    featured = db.Column(db.Boolean, default=False)
    image = db.Column(db.String(200), default='')


class Promotion(db.Model):
    __tablename__ = 'promotions'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    active = db.Column(db.Boolean, default=True)


class FaqEntry(db.Model):
    __tablename__ = 'faq_entries'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(80), nullable=False)
    question = db.Column(db.String(400), nullable=False)
    answer = db.Column(db.Text, nullable=False)


class NutritionRow(db.Model):
    __tablename__ = 'nutrition_rows'
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(60), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    serving = db.Column(db.String(60), default='')
    calories = db.Column(db.String(20), default='')
    total_fat = db.Column(db.String(20), default='')
    sat_fat = db.Column(db.String(20), default='')
    trans_fat = db.Column(db.String(20), default='')
    cholesterol = db.Column(db.String(20), default='')
    sodium = db.Column(db.String(20), default='')
    total_carbs = db.Column(db.String(20), default='')
    fiber = db.Column(db.String(20), default='')
    sugars = db.Column(db.String(20), default='')
    protein = db.Column(db.String(20), default='')
    allergens = db.Column(db.String(20), default='')


class ContactSubmission(db.Model):
    __tablename__ = 'contact_submissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), default='')
    email = db.Column(db.String(120), default='')
    topic = db.Column(db.String(80), default='')
    message = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime(2026, 9, 24, 9, 0))


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def scored_search(query, rows, fields):
    tokens = [t.lower() for t in re.split(r'\W+', query or '')
              if t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return rows
    results = []
    for row in rows:
        text = ' '.join(str(getattr(row, f, '') or '') for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            results.append((row, score))
    results.sort(key=lambda pair: (-pair[1], getattr(pair[0], 'id', 0)))
    return [r for r, _ in results]


def money(value):
    return f"${value:,.2f}"


app.jinja_env.filters['money'] = money


# ---------------------------------------------------------------------------
# Auth plumbing
# ---------------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Site-wide context
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    return {
        'MIRROR_REFERENCE_DATE': MIRROR_REFERENCE_DATE,
        'nav_categories': MenuCategory.query.order_by(MenuCategory.sort).all(),
    }


# ---------------------------------------------------------------------------
# Public content routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    combos = (MenuItem.query.join(MenuCategory)
              .filter(MenuCategory.slug == 'combos').order_by(MenuItem.sort).all())
    tailgates = (MenuItem.query.join(MenuCategory)
                 .filter(MenuCategory.slug == 'tailgates').order_by(MenuItem.sort).all())
    featured = Article.query.filter_by(featured=True).order_by(Article.id).all()
    return render_template('index.html', combos=combos, tailgates=tailgates,
                           featured=featured)


@app.route('/menu/')
def menu_page():
    categories = MenuCategory.query.order_by(MenuCategory.sort).all()
    return render_template('menu.html', categories=categories)


@app.route('/menu/<slug>')
def menu_item(slug):
    item = MenuItem.query.filter_by(slug=slug).first_or_404()
    groups = (MenuOptionGroup.query.filter_by(item_id=item.id)
              .order_by(MenuOptionGroup.sort).all())
    base_name = item.name.replace('®', '').replace('™', '').strip()
    nutrition = NutritionRow.query.filter(NutritionRow.item_name == base_name).first()
    if not nutrition and base_name.lower().startswith('the '):
        nutrition = NutritionRow.query.filter(
            NutritionRow.item_name == base_name[4:].strip()).first()
    return render_template('menu_item.html', item=item, groups=groups,
                           nutrition=nutrition)


@app.route('/allergens/')
def allergens():
    sections = {}
    rows = NutritionRow.query.order_by(NutritionRow.id).all()
    for row in rows:
        sections.setdefault(row.section, []).append(row)
    return render_template('allergens.html', sections=sections)


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    items, locations, gear, jobs, faqs = [], [], [], [], []
    if q:
        items = scored_search(q, MenuItem.query.all(), ['name', 'description'])
        locations = scored_search(q, Location.query.all(),
                                  ['street', 'city', 'state', 'zip_code'])[:12]
        gear = scored_search(q, GearProduct.query.all(), ['title', 'description', 'tags'])[:12]
        jobs = scored_search(q, Job.query.all(), ['title', 'city', 'state', 'department'])[:12]
        faqs = scored_search(q, FaqEntry.query.all(), ['question', 'answer'])[:8]
    return render_template('search.html', q=q, items=items, locations=locations,
                           gear=gear, jobs=jobs, faqs=faqs)


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

@app.route('/locations/')
def locations_page():
    q = request.args.get('q', '').strip()
    state = request.args.get('state', '').strip()
    service = request.args.get('service', '').strip()
    rows = Location.query
    if q:
        like = f"%{q}%"
        rows = rows.filter((Location.city.ilike(like)) | (Location.state.ilike(like))
                           | (Location.state == q.upper()) | (Location.zip_code.ilike(like))
                           | (Location.street.ilike(like)))
        # prefer city/state matches over incidental street-name matches
        rows = rows.order_by(
            db.case((Location.city == q, 0),
                    (Location.state == q.upper(), 0),
                    else_=1),
            Location.state, Location.city, Location.street)
    if state:
        rows = rows.filter(Location.state == state.upper())
    if service:
        rows = rows.filter(Location.amenities.ilike(f"%{service}%"))
    found = rows.order_by(Location.state, Location.city, Location.street).all()
    states = sorted({s for (s,) in db.session.query(Location.state).distinct()})
    fav_ids = set()
    if current_user.is_authenticated:
        fav_ids = {f.location_id for f in
                   FavoriteLocation.query.filter_by(user_id=current_user.id).all()}
    return render_template('locations.html', locations=found[:60], total=len(found),
                           states=states, q=q, state=state, service=service,
                           fav_ids=fav_ids)


@app.route('/locations/<slug>')
def location_detail(slug):
    loc = Location.query.filter_by(slug=slug).first_or_404()
    is_fav = False
    if current_user.is_authenticated:
        is_fav = FavoriteLocation.query.filter_by(
            user_id=current_user.id, location_id=loc.id).first() is not None
    return render_template('location_detail.html', loc=loc, is_fav=is_fav)


@app.route('/locations/<slug>/favorite', methods=['POST'])
@login_required
def toggle_favorite(slug):
    loc = Location.query.filter_by(slug=slug).first_or_404()
    fav = FavoriteLocation.query.filter_by(
        user_id=current_user.id, location_id=loc.id).first()
    if fav:
        db.session.delete(fav)
        flash('Removed from your favorite restaurants.', 'info')
    else:
        db.session.add(FavoriteLocation(user_id=current_user.id, location_id=loc.id))
        flash('Added to your favorite restaurants.', 'success')
    db.session.commit()
    return redirect(request.form.get('next') or url_for('location_detail', slug=slug))


# ---------------------------------------------------------------------------
# Order-ahead chain
# ---------------------------------------------------------------------------

def _cart_lines():
    cart = session.get('food_cart', [])
    lines = []
    for entry in cart:
        item = db.session.get(MenuItem, entry.get('item_id'))
        if not item:
            continue
        qty_price = entry.get('line_total', 0.0)
        lines.append({
            'entry': entry,
            'item': item,
            'quantity_label': entry.get('quantity_label', '1'),
            'selections': entry.get('selections', []),
            'line_total': qty_price,
        })
    return lines


def _cart_subtotal(lines):
    return round(sum(l['line_total'] for l in lines), 2)


@app.route('/order/')
def order_start():
    q = request.args.get('q', '').strip()
    found = []
    if q:
        like = f"%{q}%"
        found = (Location.query
                 .filter((Location.city.ilike(like)) | (Location.state.ilike(like))
                         | (Location.state == q.upper()) | (Location.zip_code.ilike(like))
                         | (Location.street.ilike(like)))
                 .order_by(Location.state, Location.city).limit(40).all())
    return render_template('order_start.html', locations=found, q=q)


@app.route('/order/location/<slug>')
def order_location_menu(slug):
    loc = Location.query.filter_by(slug=slug).first_or_404()
    categories = MenuCategory.query.order_by(MenuCategory.sort).all()
    return render_template('order_menu.html', loc=loc, categories=categories)


@app.route('/order/location/<slug>/item/<int:item_id>', methods=['GET', 'POST'])
def order_item(slug, item_id):
    loc = Location.query.filter_by(slug=slug).first_or_404()
    item = db.session.get(MenuItem, item_id) or abort(404)
    all_groups = (MenuOptionGroup.query.filter_by(item_id=item.id)
                  .order_by(MenuOptionGroup.sort).all())

    # quantity selector group (options carry the per-quantity price)
    qty_group = next((g for g in all_groups if g.name == 'Quantity'
                      and g.quantity_label is None), None)
    always_groups = [g for g in all_groups if g.quantity_label is None
                     and g.name != 'Quantity']

    qty = request.values.get('qty', '')
    qty_option = None
    if qty_group:
        qty_option = next((o for o in qty_group.options if o.name == qty), None)
    nested_groups = [g for g in all_groups if g.quantity_label == qty] if qty else []

    error = None
    if request.method == 'POST':
        if qty_group and not qty_option:
            error = 'Please choose a quantity first.'
            return render_template('order_item.html', loc=loc, item=item,
                                   qty_group=qty_group, qty=qty,
                                   nested_groups=[], always_groups=always_groups,
                                   error=error)
        selections = []
        if qty_option is not None:
            line_total = qty_option.price_delta or 0.0
        else:
            line_total = item.base_price or 0.0
        missing = []
        for group in nested_groups + always_groups:
            if group.multi:
                picked = request.form.getlist(f'group_{group.id}')
            else:
                picked = [request.form.get(f'group_{group.id}', '')]
            picked = [p for p in picked if p]
            if not picked and group.mandatory:
                missing.append(group.name)
            for p in picked:
                opt = MenuOption.query.filter_by(group_id=group.id, name=p).first()
                if opt:
                    line_total += opt.price_delta or 0.0
                    selections.append(opt.name)
        if missing:
            error = 'Please choose: ' + ', '.join(missing)
        else:
            cart = session.get('food_cart', [])
            cart.append({
                'item_id': item.id,
                'quantity_label': qty_option.name if qty_option else '1',
                'selections': selections,
                'line_total': round(line_total, 2),
                'location_slug': slug,
            })
            session['food_cart'] = cart
            session['order_location'] = slug
            flash(f"{item.name} ({qty_option.name if qty_option else '1'}) added to your order.", 'success')
            return redirect(url_for('order_cart'))

    return render_template('order_item.html', loc=loc, item=item,
                           qty_group=qty_group, qty=qty,
                           nested_groups=nested_groups,
                           always_groups=always_groups, error=error)


@app.route('/order/cart')
def order_cart():
    lines = _cart_lines()
    subtotal = _cart_subtotal(lines)
    loc = None
    slug = session.get('order_location')
    if slug:
        loc = Location.query.filter_by(slug=slug).first()
    return render_template('order_cart.html', lines=lines, subtotal=subtotal,
                           loc=loc, tax_rate=FOOD_TAX_RATE)


@app.route('/order/cart/remove', methods=['POST'])
def order_cart_remove():
    index = int(request.form.get('index', -1))
    cart = session.get('food_cart', [])
    if 0 <= index < len(cart):
        removed = cart.pop(index)
        session['food_cart'] = cart
        item = db.session.get(MenuItem, removed.get('item_id'))
        flash(f"Removed {item.name if item else 'item'} from your order.", 'info')
    return redirect(url_for('order_cart'))


@app.route('/order/cart/clear', methods=['POST'])
def order_cart_clear():
    session['food_cart'] = []
    flash('Your order has been cleared.', 'info')
    return redirect(url_for('order_cart'))


@app.route('/order/checkout', methods=['GET', 'POST'])
def order_checkout():
    lines = _cart_lines()
    if not lines:
        flash('Your order is empty — add something from a restaurant menu first.', 'info')
        return redirect(url_for('order_start'))
    slug = session.get('order_location')
    loc = Location.query.filter_by(slug=slug).first()
    subtotal = _cart_subtotal(lines)

    # Caniac offer
    offer_error = None
    offer = None
    offer_code = request.form.get('caniac_offer', '') if request.method == 'POST' else session.get('caniac_offer', '')
    if offer_code:
        offer = CaniacOffer.query.filter_by(code=offer_code, active=True).first()
        if not offer:
            offer_error = f'Offer code "{offer_code}" is not valid.'
        elif current_user.is_authenticated:
            claimed = UserOffer.query.filter_by(
                user_id=current_user.id, offer_id=offer.id, redeemed=False).first()
            if not claimed:
                offer_error = f'Offer code "{offer_code}" is not on your account.'
                offer = None
        elif offer.min_spend and subtotal < offer.min_spend:
            offer_error = f'Offer "{offer.title}" requires a minimum spend of {money(offer.min_spend)}.'

    discount = 0.0
    if offer:
        if offer.discount_type == 'percent':
            discount = round(subtotal * offer.value / 100.0, 2)
        elif offer.discount_type == 'dollars':
            discount = min(offer.value, subtotal)
        elif offer.discount_type == 'free_item':
            discount = min(offer.value, subtotal)
    tax = round((subtotal - discount) * FOOD_TAX_RATE, 2)
    total = round(subtotal - discount + tax, 2)

    if request.method == 'POST':
        required = ['contact_name', 'contact_phone', 'pickup_time']
        missing = [f for f in required if not request.form.get(f, '').strip()]
        payment = request.form.get('payment_method', '')
        gift_number = request.form.get('gift_card_number', '').strip()
        if payment == 'Gift Card':
            gc = GiftCard.query.filter_by(card_number=gift_number).first() if gift_number else None
            if not gc:
                missing.append('valid gift card number')
            elif gc.balance < total:
                offer_error = (f'Gift card {gift_number} has a balance of '
                               f'{money(gc.balance)} — not enough for this order.')
        if missing or offer_error:
            error = 'Please provide: ' + ', '.join(missing) if missing else offer_error
            return render_template('order_checkout.html', lines=lines, loc=loc,
                                   subtotal=subtotal, discount=discount, tax=tax,
                                   total=total, offer=offer, offer_error=offer_error,
                                   error=error, form=request.form,
                                   saved_cards=_saved_cards())
        order_number = _next_order_number('RC')
        order = FoodOrder(
            order_number=order_number,
            user_id=current_user.id if current_user.is_authenticated else None,
            location_id=loc.id if loc else Location.query.first().id,
            pickup_mode=request.form.get('pickup_mode', 'Pickup'),
            pickup_date=request.form.get('pickup_date', ''),
            pickup_time=request.form.get('pickup_time', ''),
            contact_name=request.form.get('contact_name', ''),
            contact_phone=request.form.get('contact_phone', ''),
            payment_method=payment,
            gift_card_number=gift_number if payment == 'Gift Card' else '',
            caniac_offer=offer.code if offer else '',
            subtotal=subtotal,
            discount=discount,
            tax=tax,
            total=total,
            status='Placed',
            placed_at=datetime(2026, 9, 24, 12, 0),
            points_earned=int(total),
        )
        # order.id is None until flush; add items through the relationship
        order.items = [FoodOrderItem(
            item_id=line['item'].id,
            quantity_label=line['quantity_label'],
            selections=json.dumps(line['selections']),
            line_total=line['line_total'],
        ) for line in lines]
        if payment == 'Gift Card' and gift_number:
            gc = GiftCard.query.filter_by(card_number=gift_number).first()
            if gc:
                gc.balance = round(gc.balance - total, 2)
        if offer and current_user.is_authenticated:
            claimed = UserOffer.query.filter_by(
                user_id=current_user.id, offer_id=offer.id, redeemed=False).first()
            if claimed:
                claimed.redeemed = True
                claimed.redeemed_order = order_number
        if current_user.is_authenticated:
            card = CaniacCard.query.filter_by(user_id=current_user.id).first()
            if card:
                card.points += order.points_earned
        db.session.add(order)
        db.session.commit()
        session['food_cart'] = []
        session.pop('caniac_offer', None)
        return redirect(url_for('order_confirmation', order_number=order_number))

    return render_template('order_checkout.html', lines=lines, loc=loc,
                           subtotal=subtotal, discount=discount, tax=tax,
                           total=total, offer=offer, offer_error=offer_error,
                           error=None, form={}, saved_cards=_saved_cards())


def _saved_cards():
    if not current_user.is_authenticated:
        return []
    return PaymentCard.query.filter_by(user_id=current_user.id).all()


def _next_order_number(prefix):
    row = db.session.query(func.max(FoodOrder.id)).select_from(FoodOrder).first()
    next_id = (row[0] or 0) + 1
    return f"{prefix}-{100234 + next_id}"


@app.route('/order/confirmation/<order_number>')
def order_confirmation(order_number):
    order = FoodOrder.query.filter_by(order_number=order_number).first_or_404()
    return render_template('order_confirmation.html', order=order)


@app.route('/orders')
@login_required
def order_history():
    orders = (FoodOrder.query.filter_by(user_id=current_user.id)
              .order_by(FoodOrder.placed_at.desc()).all())
    return render_template('order_history.html', orders=orders)


@app.route('/orders/<order_number>')
@login_required
def order_detail(order_number):
    order = FoodOrder.query.filter_by(order_number=order_number,
                                      user_id=current_user.id).first_or_404()
    return render_template('order_detail.html', order=order)


@app.route('/orders/<order_number>/cancel', methods=['POST'])
@login_required
def order_cancel(order_number):
    order = FoodOrder.query.filter_by(order_number=order_number,
                                      user_id=current_user.id).first_or_404()
    if order.status == 'Cancelled':
        flash(f'Order {order.order_number} is already cancelled.', 'info')
        return redirect(url_for('order_detail', order_number=order_number))
    order.status = 'Cancelled'
    # refund a gift-card payment in full, like the upstream platform does
    if order.gift_card_number:
        gc = GiftCard.query.filter_by(card_number=order.gift_card_number).first()
        if gc:
            gc.balance = round(gc.balance + order.total, 2)
    if current_user.is_authenticated:
        card = CaniacCard.query.filter_by(user_id=current_user.id).first()
        if card and order.points_earned:
            card.points = max(0, card.points - order.points_earned)
    db.session.commit()
    flash(f'Order {order.order_number} has been cancelled.', 'success')
    return redirect(url_for('order_detail', order_number=order_number))


@app.route('/orders/<order_number>/reorder', methods=['POST'])
@login_required
def reorder(order_number):
    order = FoodOrder.query.filter_by(order_number=order_number,
                                      user_id=current_user.id).first_or_404()
    cart = []
    for it in order.items:
        cart.append({
            'item_id': it.item_id,
            'quantity_label': it.quantity_label,
            'selections': it.selection_list(),
            'line_total': it.line_total,
            'location_slug': order.location.slug,
        })
    session['food_cart'] = cart
    session['order_location'] = order.location.slug
    flash(f'Items from order {order.order_number} were added back to your cart.', 'success')
    return redirect(url_for('order_cart'))


# ---------------------------------------------------------------------------
# Gear shop
# ---------------------------------------------------------------------------

GEAR_COLLECTIONS = ['Apparel', 'Headwear', 'Accessories', 'Plush', 'Gift Card']


@app.route('/gear/')
def gear_home():
    products = GearProduct.query.order_by(GearProduct.sort).all()
    counts = {}
    for coll in GEAR_COLLECTIONS:
        counts[coll] = GearProduct.query.filter_by(collection=coll).count()
    return render_template('gear_home.html', products=products[:24],
                           collections=GEAR_COLLECTIONS, counts=counts)


@app.route('/gear/collection/<name>')
def gear_collection(name):
    rows = GearProduct.query.filter_by(collection=name)
    sort = request.args.get('sort', 'featured')
    if sort == 'price_asc':
        rows = rows.order_by(GearProduct.price)
    elif sort == 'price_desc':
        rows = rows.order_by(GearProduct.price.desc())
    elif sort == 'name':
        rows = rows.order_by(GearProduct.title)
    else:
        rows = rows.order_by(GearProduct.sort)
    return render_template('gear_collection.html', collection=name,
                           products=rows.all(), sort=sort,
                           collections=GEAR_COLLECTIONS)


@app.route('/gear/product/<handle>')
def gear_product(handle):
    product = GearProduct.query.filter_by(handle=handle).first_or_404()
    return render_template('gear_product.html', product=product)


def _gear_variant_price(product, variant_title):
    """Resolve the catalog price for a (product, variant) pair.

    Multi-variant products (e.g. gift cards in $5..$100 denominations) must
    charge the selected variant's price, never the product's minimum variant
    price. Unknown variant titles fall back to the product's base price.
    """
    variant = GearVariant.query.filter_by(product_id=product.id,
                                           title=variant_title).first()
    return variant.price if variant else product.price


def _gear_cart_lines():
    cart = session.get('gear_cart', [])
    lines = []
    for entry in cart:
        product = db.session.get(GearProduct, entry.get('product_id'))
        if product:
            variant = entry.get('variant', 'Default Title')
            lines.append({'entry': entry, 'product': product,
                          'variant': variant,
                          'qty': entry.get('qty', 1),
                          'price': _gear_variant_price(product, variant)})
    return lines


@app.route('/gear/cart', methods=['GET', 'POST'])
def gear_cart():
    if request.method == 'POST':
        product = GearProduct.query.filter_by(
            handle=request.form.get('handle', '')).first()
        if not product:
            abort(404)
        variant = request.form.get('variant', '') or 'Default Title'
        price = _gear_variant_price(product, variant)
        qty = max(1, int(request.form.get('qty', 1)))
        cart = session.get('gear_cart', [])
        for entry in cart:
            if entry['product_id'] == product.id and entry['variant'] == variant:
                entry['qty'] += qty
                break
        else:
            cart.append({'product_id': product.id, 'variant': variant,
                         'qty': qty, 'price': price})
        session['gear_cart'] = cart
        flash(f"{product.title} added to your cart.", 'success')
        return redirect(url_for('gear_cart'))
    lines = _gear_cart_lines()
    subtotal = round(sum(l['price'] * l['qty'] for l in lines), 2)
    shipping = 0.0 if (subtotal >= GEAR_FREE_SHIPPING_THRESHOLD or not lines) else GEAR_FLAT_SHIPPING
    return render_template('gear_cart.html', lines=lines, subtotal=subtotal,
                           shipping=shipping,
                           total=round(subtotal + shipping, 2),
                           free_threshold=GEAR_FREE_SHIPPING_THRESHOLD)


@app.route('/gear/cart/remove', methods=['POST'])
def gear_cart_remove():
    index = int(request.form.get('index', -1))
    cart = session.get('gear_cart', [])
    if 0 <= index < len(cart):
        cart.pop(index)
        session['gear_cart'] = cart
        flash('Item removed from your cart.', 'info')
    return redirect(url_for('gear_cart'))


@app.route('/gear/checkout', methods=['GET', 'POST'])
def gear_checkout():
    lines = _gear_cart_lines()
    if not lines:
        flash('Your gear cart is empty.', 'info')
        return redirect(url_for('gear_home'))
    subtotal = round(sum(l['price'] * l['qty'] for l in lines), 2)
    shipping = 0.0 if subtotal >= GEAR_FREE_SHIPPING_THRESHOLD else GEAR_FLAT_SHIPPING
    total = round(subtotal + shipping, 2)
    if request.method == 'POST':
        required = ['ship_name', 'ship_line1', 'ship_city', 'ship_state',
                   'ship_zip', 'email']
        missing = [f for f in required if not request.form.get(f, '').strip()]
        if missing:
            return render_template('gear_checkout.html', lines=lines,
                                   subtotal=subtotal, shipping=shipping,
                                   total=total, error='Please provide: ' + ', '.join(missing),
                                   form=request.form,
                                   free_threshold=GEAR_FREE_SHIPPING_THRESHOLD)
        order_number = _next_gear_order_number()
        order = GearOrder(
            order_number=order_number,
            user_id=current_user.id if current_user.is_authenticated else None,
            email=request.form.get('email', ''),
            ship_name=request.form.get('ship_name', ''),
            ship_line1=request.form.get('ship_line1', ''),
            ship_city=request.form.get('ship_city', ''),
            ship_state=request.form.get('ship_state', ''),
            ship_zip=request.form.get('ship_zip', ''),
            payment_method=request.form.get('payment_method', 'Visa'),
            subtotal=subtotal, shipping=shipping, total=total,
        )
        order.items = [GearOrderItem(product_id=l['product'].id,
                                     variant_title=l['variant'],
                                     qty=l['qty'], price=l['price'])
                       for l in lines]
        db.session.add(order)
        db.session.commit()
        session['gear_cart'] = []
        return redirect(url_for('gear_confirmation', order_number=order_number))
    return render_template('gear_checkout.html', lines=lines, subtotal=subtotal,
                           shipping=shipping, total=total, error=None, form={},
                           free_threshold=GEAR_FREE_SHIPPING_THRESHOLD)


def _next_gear_order_number():
    row = db.session.query(func.max(GearOrder.id)).select_from(GearOrder).first()
    next_id = (row[0] or 0) + 1
    return f"GEAR-{4501 + next_id}"


@app.route('/gear/confirmation/<order_number>')
def gear_confirmation(order_number):
    order = GearOrder.query.filter_by(order_number=order_number).first_or_404()
    return render_template('gear_confirmation.html', order=order)


# ---------------------------------------------------------------------------
# Gift cards
# ---------------------------------------------------------------------------

@app.route('/gift-cards/')
def gift_cards():
    designs = GearProduct.query.filter_by(collection='Gift Card').order_by(GearProduct.sort).all()
    return render_template('gift_cards.html', designs=designs)


@app.route('/gift-cards/check', methods=['GET', 'POST'])
def gift_card_check():
    result = None
    error = None
    if request.method == 'POST':
        number = re.sub(r'\s', '', request.form.get('card_number', ''))
        pin = request.form.get('pin', '').strip()
        if not number or not pin:
            error = 'Please enter both the gift card number and PIN.'
        else:
            gc = GiftCard.query.filter_by(card_number=number).first()
            if not gc or gc.pin != pin:
                error = ('We could not find that gift card. Please check the '
                         'number and PIN and try again.')
            else:
                result = gc
    return render_template('gift_card_check.html', result=result, error=error)


# ---------------------------------------------------------------------------
# Caniac Club
# ---------------------------------------------------------------------------

@app.route('/caniac-club/')
def caniac_club():
    card = None
    offers = []
    claimed = []
    if current_user.is_authenticated:
        card = CaniacCard.query.filter_by(user_id=current_user.id).first()
        claimed = (UserOffer.query.filter_by(user_id=current_user.id)
                   .order_by(UserOffer.id).all())
    active = CaniacOffer.query.filter_by(active=True).order_by(CaniacOffer.id).all()
    return render_template('caniac_club.html', card=card, offers=active,
                           claimed=claimed)


@app.route('/caniac-club/register', methods=['POST'])
@login_required
def caniac_register():
    number = re.sub(r'\s', '', request.form.get('card_number', ''))
    if not number:
        flash('Please enter the card number from your Caniac Club card.', 'error')
        return redirect(url_for('caniac_club'))
    existing = CaniacCard.query.filter_by(card_number=number).first()
    if existing and existing.user_id != current_user.id:
        flash('That card is already registered to another account.', 'error')
        return redirect(url_for('caniac_club'))
    card = CaniacCard.query.filter_by(user_id=current_user.id).first()
    if card:
        # attach the new card to the existing account, keeping earned points
        card.card_number = number
        flash('Your new Caniac Club card has been attached to your account.', 'success')
    else:
        db.session.add(CaniacCard(user_id=current_user.id, card_number=number,
                                   points=0))
        flash('Your Caniac Club card is registered — welcome to the Club!', 'success')
    db.session.commit()
    return redirect(url_for('caniac_club'))


# ---------------------------------------------------------------------------
# Careers
# ---------------------------------------------------------------------------

@app.route('/careers/')
def careers():
    q = request.args.get('q', '').strip()
    state = request.args.get('state', '').strip()
    job_type = request.args.get('type', '').strip()
    department = request.args.get('department', '').strip()
    rows = Job.query
    if q:
        like = f"%{q}%"
        rows = rows.filter(Job.title.ilike(like) | Job.city.ilike(like)
                           | Job.street.ilike(like) | Job.state.ilike(like))
    if state:
        rows = rows.filter(Job.state_abbr == state.upper())
    if job_type:
        rows = rows.filter(Job.employment_type.ilike(f"%{job_type}%"))
    if department:
        rows = rows.filter(Job.department == department)
    found = rows.order_by(Job.id).all()
    states = sorted({s for (s,) in db.session.query(Job.state_abbr).distinct() if s})
    departments = sorted({d for (d,) in db.session.query(Job.department).distinct() if d})
    return render_template('careers.html', jobs=found[:60], total=len(found),
                           states=states, departments=departments, q=q,
                           state=state, job_type=job_type, department=department)


@app.route('/careers/<reference>')
def job_detail(reference):
    job = Job.query.filter_by(reference=reference).first_or_404()
    return render_template('job_detail.html', job=job)


# ---------------------------------------------------------------------------
# Content pages
# ---------------------------------------------------------------------------

@app.route('/faq/')
def faq():
    category = request.args.get('category', '').strip()
    q = request.args.get('q', '').strip()
    rows = FaqEntry.query
    if category:
        rows = rows.filter_by(category=category)
    if q:
        rows = scored_search(q, rows.all(), ['question', 'answer'])
    else:
        rows = rows.order_by(FaqEntry.id).all()
    categories = sorted({c for (c,) in db.session.query(FaqEntry.category).distinct()})
    return render_template('faq.html', entries=rows, categories=categories,
                           category=category, q=q)


@app.route('/news/')
def news():
    articles = Article.query.order_by(Article.id).all()
    return render_template('news.html', articles=articles)


@app.route('/news/<slug>')
def news_article(slug):
    article = Article.query.filter_by(slug=slug).first()
    if not article:
        article = Article.query.filter(Article.title.ilike(
            f"%{slug.replace('-', ' ')}%")).first_or_404()
    return render_template('news_article.html', article=article)


@app.route('/promotions/')
def promotions():
    promos = Promotion.query.filter_by(active=True).order_by(Promotion.id).all()
    return render_template('promotions.html', promos=promos)


@app.route('/who-we-are/')
def who_we_are():
    return render_template('who_we_are.html')


@app.route('/why-the-dog/')
def why_the_dog():
    return render_template('why_the_dog.html')


@app.route('/food-preparation/')
def food_preparation():
    items = MenuItem.query.order_by(MenuItem.sort).all()
    return render_template('food_preparation.html', items=items)


@app.route('/contact-us/', methods=['GET', 'POST'])
def contact_us():
    if request.method == 'POST':
        required = ['name', 'email', 'topic', 'message']
        missing = [f for f in required if not request.form.get(f, '').strip()]
        if missing:
            return render_template('contact_us.html', error='Please fill in: ' + ', '.join(missing),
                                   form=request.form)
        db.session.add(ContactSubmission(
            name=request.form.get('name', ''), email=request.form.get('email', ''),
            topic=request.form.get('topic', ''), message=request.form.get('message', '')))
        db.session.commit()
        flash('Thanks for reaching out! A Cane’s Crewmember will follow up soon.', 'success')
        return redirect(url_for('contact_us'))
    return render_template('contact_us.html', error=None, form={})


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email', '').strip().lower()).first()
        if user and user.check_password(request.form.get('password', '')):
            login_user(user)
            flash('Welcome back!', 'success')
            return redirect(request.args.get('next') or url_for('account'))
        return render_template('login.html', error='Invalid email or password.')
    return render_template('login.html', error=None)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        if not email or not name or len(password) < 8:
            return render_template('register.html',
                                   error='Please provide a name, email and a password of at least 8 characters.')
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='That email is already registered.')
        user = User(email=email, name=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Welcome to Raising Cane’s! Your account is ready.', 'success')
        return redirect(url_for('account'))
    return render_template('register.html', error=None)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('index'))


@app.route('/account')
@login_required
def account():
    addresses = Address.query.filter_by(user_id=current_user.id).all()
    cards = PaymentCard.query.filter_by(user_id=current_user.id).all()
    caniac = CaniacCard.query.filter_by(user_id=current_user.id).first()
    gift_cards = GiftCard.query.filter_by(owner_email=current_user.email).all()
    orders = FoodOrder.query.filter_by(user_id=current_user.id).order_by(FoodOrder.placed_at.desc()).all()
    gear_orders = GearOrder.query.filter_by(user_id=current_user.id).order_by(GearOrder.placed_at.desc()).all()
    return render_template('account.html', addresses=addresses, cards=cards,
                           caniac=caniac, gift_cards=gift_cards,
                           orders=orders, gear_orders=gear_orders)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name)
        current_user.phone = request.form.get('phone', current_user.phone)
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('account'))
    return render_template('account_edit.html')


@app.route('/account/addresses/add', methods=['POST'])
@login_required
def account_address_add():
    line1 = request.form.get('line1', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip().upper()
    zip_code = request.form.get('zip_code', '').strip()
    if not (line1 and city and state and zip_code):
        flash('Please provide a street, city, state and ZIP.', 'error')
        return redirect(url_for('account'))
    db.session.add(Address(user_id=current_user.id,
                           label=request.form.get('label', 'Home'),
                           line1=line1, city=city, state=state, zip_code=zip_code))
    db.session.commit()
    flash('Address added.', 'success')
    return redirect(url_for('account'))


@app.route('/account/favorites')
@login_required
def account_favorites():
    favs = (FavoriteLocation.query.filter_by(user_id=current_user.id).all())
    locations = [Location.query.get(f.location_id) for f in favs]
    return render_template('account_favorites.html', locations=locations)


@app.route('/_health')
def health():
    return {'ok': True, 'site': 'raising_canes'}


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('500.html'), 500


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

# Indexes are created with explicit, name-sorted SQL (not SQLAlchemy's
# metadata pass, whose set-ordered index creation makes the SQLite file
# non-reproducible across builds). IF NOT EXISTS keeps every boot a no-op.
INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS ix_addresses_user_id ON addresses (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_articles_slug ON articles (slug)",
    "CREATE INDEX IF NOT EXISTS ix_caniac_cards_user_id ON caniac_cards (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_faq_entries_category ON faq_entries (category)",
    "CREATE INDEX IF NOT EXISTS ix_favorite_locations_location_id ON favorite_locations (location_id)",
    "CREATE INDEX IF NOT EXISTS ix_favorite_locations_user_id ON favorite_locations (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_food_order_items_order_id ON food_order_items (order_id)",
    "CREATE INDEX IF NOT EXISTS ix_food_orders_user_id ON food_orders (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_gear_order_items_order_id ON gear_order_items (order_id)",
    "CREATE INDEX IF NOT EXISTS ix_gear_orders_user_id ON gear_orders (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_gear_variants_product_id ON gear_variants (product_id)",
    "CREATE INDEX IF NOT EXISTS ix_gift_cards_card_number ON gift_cards (card_number)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_city ON jobs (city)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_reference ON jobs (reference)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_state ON jobs (state)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_state_abbr ON jobs (state_abbr)",
    "CREATE INDEX IF NOT EXISTS ix_locations_city ON locations (city)",
    "CREATE INDEX IF NOT EXISTS ix_locations_slug ON locations (slug)",
    "CREATE INDEX IF NOT EXISTS ix_locations_state ON locations (state)",
    "CREATE INDEX IF NOT EXISTS ix_locations_zip_code ON locations (zip_code)",
    "CREATE INDEX IF NOT EXISTS ix_menu_items_slug ON menu_items (slug)",
    "CREATE INDEX IF NOT EXISTS ix_menu_option_groups_item_id ON menu_option_groups (item_id)",
    "CREATE INDEX IF NOT EXISTS ix_menu_options_group_id ON menu_options (group_id)",
    "CREATE INDEX IF NOT EXISTS ix_payment_cards_user_id ON payment_cards (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_user_offers_user_id ON user_offers (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)",
)

def seed_database():
    if MenuCategory.query.count() > 0:
        return
    from seed_data import run_seed
    run_seed(db, MenuCategory, MenuItem, MenuOptionGroup, MenuOption,
             NutritionRow, Location, GearProduct, GearVariant, Job, FaqEntry,
             Article, Promotion, CaniacOffer, GiftCard)


def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    from seed_data import run_seed_users
    run_seed_users(db, User, Address, PaymentCard, CaniacCard, UserOffer,
                   FavoriteLocation, FoodOrder, FoodOrderItem, GearOrder,
                   GearOrderItem, GiftCard, Location, MenuItem, GearProduct,
                   CaniacOffer, bcrypt)


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
