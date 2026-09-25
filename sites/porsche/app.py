#!/usr/bin/env python3
"""Porsche (porsche.com) mirror — Flask app.

Functional mirror of https://www.porsche.com/usa/ built for the WebHarbor
offline benchmark environment:

  * Model lineup      — /usa/models/ overview with range/body/fuel filters,
                        76 real model variants (prices, hp, 0-60, equipment)
  * Model detail      — /usa/models/<range>/<series>/<slug>/ with the live
                        site's technical data tables and highlights
  * Configurator      — /configurator/ for 8 model codes: real option
                        catalogs with prices, selectable, running total,
                        saveable builds (My Porsche)
  * Porsche Finder     — /finder/ vehicle search over 442 real in-stock
                        listings (VIN, dealer, price breakdown, lease
                        estimates) with filters, sort, pagination, detail
                        pages and saved vehicles
  * Dealer search      — /usa/dealersearch/ across 218 real US Porsche
                        Centers (state browse, name/zip/city search, hours)
  * Porsche Shop       — /shop/ with 188 real products in 3 categories,
                        product pages, cart and checkout flow
  * My Porsche         — account (register/sign-in), saved vehicles,
                        saved builds, order history

All catalog rows come from the tracked source_data/ snapshots captured from
the live site; see provenance.json.
"""
import hashlib
import json
import os
import re
import secrets
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, abort, flash, jsonify, redirect, render_template,
    request, session, url_for,
)
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user, logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
INSTANCE = BASE_DIR / "instance"
INSTANCE.mkdir(exist_ok=True)

app = Flask(__name__, instance_path=str(INSTANCE))
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or "porsche-mirror-dev-secret"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
_DB_PATH = os.environ.get("WEBHARBOR_MIRROR_DB") or str(INSTANCE / "porsche.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{_DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "my_porsche_sign_in"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "error"

# The mirror runs against a frozen catalog snapshot captured on this date.
MIRROR_REFERENCE_DATE = "2026-09-24"

PORSCHE_NAV = [
    {"label": "Models", "href": "/usa/models/"},
    {"label": "Shop", "href": "/shop/"},
    {"label": "Find a Vehicle", "href": "/finder/us/en-US/search"},
    {"label": "Dealer Search", "href": "/usa/dealersearch/"},
    {"label": "My Porsche", "href": "/my-porsche/"},
]

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}

DAY_LABELS = {
    "MONDAY": "Monday", "TUESDAY": "Tuesday", "WEDNESDAY": "Wednesday",
    "THURSDAY": "Thursday", "FRIDAY": "Friday", "SATURDAY": "Saturday", "SUNDAY": "Sunday",
}


# =====================================================================
# MODELS
# =====================================================================

class ModelVariant(db.Model):
    __tablename__ = "model_variants"
    id = db.Column(db.Integer, primary_key=True)
    model_type = db.Column(db.String(16), unique=True, nullable=False, index=True)  # e.g. 992142
    model_name = db.Column(db.String(120), nullable=False)
    model_year = db.Column(db.String(8))
    body_type = db.Column(db.String(40))
    model_range = db.Column(db.String(20), index=True)
    model_series = db.Column(db.String(80))
    wheel_drive = db.Column(db.String(40))
    seats = db.Column(db.String(10))
    fuel_type = db.Column(db.String(30))
    gear_type = db.Column(db.String(40))
    price_value = db.Column(db.Integer)
    price_formatted = db.Column(db.String(40))
    hp_value = db.Column(db.Integer)
    hp_formatted = db.Column(db.String(20))
    accel_0_60 = db.Column(db.String(20))
    top_speed = db.Column(db.String(20))
    leasing_monthly = db.Column(db.String(40))
    image = db.Column(db.String(300))
    detail_slug = db.Column(db.String(120), unique=True)
    configure_code = db.Column(db.String(16), index=True)
    equipment_highlights = db.Column(db.Text, default="[]")   # JSON list
    tech_categories = db.Column(db.Text, default="[]")        # JSON list of {id,label,attributes[]}
    highlights_attributes = db.Column(db.Text, default="[]")  # JSON list
    highlights_image = db.Column(db.String(300))
    gallery = db.Column(db.Text, default="[]")                # JSON list of local paths

    @property
    def equipment(self):
        return json.loads(self.equipment_highlights or "[]")

    @property
    def tech(self):
        return json.loads(self.tech_categories or "[]")

    @property
    def highlight_attrs(self):
        return json.loads(self.highlights_attributes or "[]")

    @property
    def gallery_images(self):
        return json.loads(self.gallery or "[]")

    @property
    def range_slug(self):
        return (self.model_range or "").lower()

    @property
    def series_slug(self):
        # Audit fix: the "911 GT3 S/C" series carries a slash that would leak
        # into the URL path as an extra segment (dead link); slashes join the
        # the hyphen normalization.
        return ((self.model_series or "")
                .lower().replace(" model variants", "")
                .replace(" ", "-").replace("/", "-").lower())


class ConfiguratorOption(db.Model):
    __tablename__ = "configurator_options"
    id = db.Column(db.Integer, primary_key=True)
    model_code = db.Column(db.String(16), nullable=False, index=True)
    option_id = db.Column(db.String(24), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False, default=0)
    swatch = db.Column(db.String(300))
    __table_args__ = (db.UniqueConstraint("model_code", "option_id", name="uq_cfg_option"),)


class Vehicle(db.Model):
    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.String(12), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    full_title = db.Column(db.String(160))
    model_range = db.Column(db.String(20), index=True)
    model_generation = db.Column(db.String(40))
    condition = db.Column(db.String(16), index=True)          # new / preowned
    condition_label = db.Column(db.String(30))                # New / Pre-Owned / Certified Pre-Owned
    price = db.Column(db.Integer, index=True)
    vin = db.Column(db.String(24))
    model_year = db.Column(db.Integer, index=True)
    color = db.Column(db.String(80), index=True)
    interior_color = db.Column(db.String(160))
    transmission = db.Column(db.String(40), index=True)
    drivetrain = db.Column(db.String(40), index=True)
    fuel = db.Column(db.String(30), index=True)
    hp = db.Column(db.Integer)
    mileage = db.Column(db.Integer)
    previous_owners = db.Column(db.Integer)
    body_type = db.Column(db.String(30), index=True)
    seller_id = db.Column(db.String(12))
    partner_no = db.Column(db.String(12), index=True)
    dealer_name = db.Column(db.String(160), index=True)
    dealer_city = db.Column(db.String(80))
    dealer_zip = db.Column(db.String(12))
    dealer_street = db.Column(db.String(200))
    image = db.Column(db.String(300))
    lease_payment = db.Column(db.String(200))
    price_breakdown = db.Column(db.Text, default="[]")        # JSON list
    characteristics = db.Column(db.Text, default="[]")        # JSON list
    weight_kg = db.Column(db.Integer)
    dimensions = db.Column(db.Text, default="{}")

    @property
    def breakdown(self):
        return json.loads(self.price_breakdown or "[]")

    @property
    def chars(self):
        return json.loads(self.characteristics or "[]")

    @property
    def condition_badge(self):
        return self.condition_label or ("New" if self.condition == "new" else "Pre-Owned")


class Dealer(db.Model):
    __tablename__ = "dealers"
    id = db.Column(db.Integer, primary_key=True)
    ppn_org_id = db.Column(db.String(12), unique=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    partner_no = db.Column(db.String(16))
    street = db.Column(db.String(200))
    city = db.Column(db.String(80), index=True)
    state = db.Column(db.String(4), index=True)
    zip = db.Column(db.String(12))
    phone = db.Column(db.String(40))
    email = db.Column(db.String(160))
    homepage = db.Column(db.String(200))
    contact_hours = db.Column(db.Text, default="[]")
    service_hours = db.Column(db.Text, default="[]")
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

    @property
    def state_name(self):
        return STATE_NAMES.get(self.state, self.state)

    @property
    def contact(self):
        return json.loads(self.contact_hours or "[]")

    @property
    def service(self):
        return json.loads(self.service_hours or "[]")

    @property
    def inventory_count(self):
        return Vehicle.query.filter_by(dealer_name=self.name).count()


class ShopProduct(db.Model):
    __tablename__ = "shop_products"
    id = db.Column(db.Integer, primary_key=True)
    object_id = db.Column(db.String(24), unique=True, nullable=False)
    name = db.Column(db.String(250), nullable=False)
    sku = db.Column(db.String(24))
    slug = db.Column(db.String(250), index=True)
    shop_category = db.Column(db.String(40), index=True)
    main_category = db.Column(db.String(120))
    categories_json = db.Column(db.Text, default="[]")
    description = db.Column(db.Text)
    price_cents = db.Column(db.Integer)
    brand = db.Column(db.String(80))
    in_stock = db.Column(db.Boolean, default=True)
    images = db.Column(db.Text, default="[]")
    color = db.Column(db.Text, default="[]")
    size = db.Column(db.String(40))
    labels = db.Column(db.Text, default="[]")

    @property
    def price_display(self):
        return f"${self.price_cents / 100:,.2f}"

    @property
    def image_list(self):
        return json.loads(self.images or "[]")

    @property
    def category_list(self):
        return json.loads(self.categories_json or "[]")

    @property
    def color_list(self):
        return json.loads(self.color or "[]")

    @property
    def label_list(self):
        return json.loads(self.labels or "[]")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    created_at = db.Column(db.String(20))

    saved_vehicles = db.relationship("SavedVehicle", backref="user", lazy=True)
    saved_builds = db.relationship("SavedBuild", backref="user", lazy=True)
    orders = db.relationship("ShopOrder", backref="user", lazy=True)


class SavedVehicle(db.Model):
    __tablename__ = "saved_vehicles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    saved_on = db.Column(db.String(20))
    vehicle = db.relationship("Vehicle")


class SavedBuild(db.Model):
    __tablename__ = "saved_builds"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    build_name = db.Column(db.String(120))
    model_code = db.Column(db.String(16), nullable=False)
    model_name = db.Column(db.String(120))
    options_json = db.Column(db.Text, default="[]")   # JSON [{id,name,price}]
    total_price = db.Column(db.Integer)
    created_on = db.Column(db.String(20))

    @property
    def options(self):
        return json.loads(self.options_json or "[]")


class ShopOrder(db.Model):
    __tablename__ = "shop_orders"
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    email = db.Column(db.String(160), nullable=False)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    street = db.Column(db.String(200))
    city = db.Column(db.String(80))
    state = db.Column(db.String(4))
    zip = db.Column(db.String(12))
    subtotal_cents = db.Column(db.Integer)
    shipping_cents = db.Column(db.Integer)
    total_cents = db.Column(db.Integer)
    status = db.Column(db.String(20), default="confirmed")
    placed_on = db.Column(db.String(20))

    items = db.relationship("ShopOrderItem", backref="order", lazy=True)


class ShopOrderItem(db.Model):
    __tablename__ = "shop_order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("shop_orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("shop_products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price_cents = db.Column(db.Integer, nullable=False)
    product = db.relationship("ShopProduct")


class SiteContent(db.Model):
    __tablename__ = "site_content"
    key = db.Column(db.String(80), primary_key=True)
    content = db.Column(db.Text, nullable=False)


# =====================================================================
# HELPERS
# =====================================================================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def money(value):
    try:
        return f"${int(value):,}"
    except (TypeError, ValueError):
        return ""


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def day_label(day):
    return DAY_LABELS.get(day, day)


app.jinja_env.globals.update(money=money, day_label=day_label,
                             STATE_NAMES=STATE_NAMES, nav=PORSCHE_NAV)


# =====================================================================
# SEEDING (idempotent, gated per function)
# =====================================================================

def seed_database():
    if ModelVariant.query.count() > 0:
        return
    from seed_data import build_seed
    build_seed(db)


def seed_benchmark_users():
    if User.query.filter_by(email="casey.taylor@test.com").first():
        return
    from seed_data import build_benchmark_users
    build_benchmark_users(db, bcrypt)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


# =====================================================================
# CSRF PROTECTION (all POST forms carry the per-session token)
# =====================================================================

def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


@app.before_request
def protect_forms():
    if request.method == "POST":
        expected = session.get("csrf_token", "")
        observed = request.form.get("csrf_token", "")
        if not expected or not secrets.compare_digest(expected, observed):
            abort(400, "This form has expired. Reload the page and try again.")


# =====================================================================
# CONTEXT
# =====================================================================

@app.context_processor
def inject_globals():
    return {
        "nav": PORSCHE_NAV,
        "cart_count": len(session.get("cart", {})),
        "current_year": 2026,
        "csrf_token": csrf_token,
    }


# =====================================================================
# HOMEPAGE
# =====================================================================

@app.route("/")
def index():
    ranges = ["911", "718", "Taycan", "Panamera", "Macan", "Cayenne"]
    lineup = []
    for rng in ranges:
        model = (ModelVariant.query
                 .filter(ModelVariant.model_range == rng)
                 .order_by(ModelVariant.price_value)
                 .first())
        if model:
            lineup.append(model)
    new_arrivals = (Vehicle.query
                    .filter(Vehicle.condition == "new")
                    .order_by(Vehicle.price.desc())
                    .limit(4).all())
    vehicle_count = Vehicle.query.count()
    dealer_count = Dealer.query.count()
    return render_template(
        "index.html", lineup=lineup, new_arrivals=new_arrivals,
        vehicle_count=vehicle_count, dealer_count=dealer_count,
    )


@app.route("/_health")
def health():
    return {"ok": True, "site": "porsche"}


# =====================================================================
# MODELS
# =====================================================================

@app.route("/usa/models/")
def models_overview():
    q = ModelVariant.query
    range_f = request.args.get("range", "").strip()
    body_f = request.args.get("body", "").strip()
    fuel_f = request.args.get("fuel", "").strip()
    gear_f = request.args.get("gear", "").strip()
    if range_f:
        q = q.filter(ModelVariant.model_range == range_f)
    if body_f:
        q = q.filter(ModelVariant.body_type == body_f)
    if fuel_f:
        q = q.filter(ModelVariant.fuel_type == fuel_f)
    if gear_f:
        q = q.filter(ModelVariant.gear_type == gear_f)
    sort = request.args.get("sort", "range")
    if sort == "price-asc":
        q = q.order_by(ModelVariant.price_value)
    elif sort == "price-desc":
        q = q.order_by(ModelVariant.price_value.desc())
    elif sort == "hp-desc":
        q = q.order_by(ModelVariant.hp_value.desc())
    else:
        q = q.order_by(ModelVariant.model_range, ModelVariant.price_value)
    models = q.all()
    ranges = [r[0] for r in db.session.query(ModelVariant.model_range).distinct()
              .order_by(ModelVariant.model_range).all() if r[0]]
    bodies = [r[0] for r in db.session.query(ModelVariant.body_type).distinct()
              .order_by(ModelVariant.body_type).all() if r[0]]
    fuels = [r[0] for r in db.session.query(ModelVariant.fuel_type).distinct()
             .order_by(ModelVariant.fuel_type).all() if r[0]]
    gears = [r[0] for r in db.session.query(ModelVariant.gear_type).distinct()
             .order_by(ModelVariant.gear_type).all() if r[0]]
    return render_template(
        "models_overview.html", models=models, ranges=ranges, bodies=bodies,
        fuels=fuels, gears=gears, range_f=range_f, body_f=body_f,
        fuel_f=fuel_f, gear_f=gear_f, sort=sort,
    )


@app.route("/usa/models/<range_slug>/")
def model_range_page(range_slug):
    rng = range_slug.capitalize() if range_slug != "911" else "911"
    models = (ModelVariant.query
              .filter(ModelVariant.model_range == rng)
              .order_by(ModelVariant.price_value).all())
    if not models:
        abort(404)
    return render_template("model_range.html", models=models, rng=rng)


@app.route("/usa/models/<range_slug>/<series_slug>/<slug>/")
def model_detail(range_slug, series_slug, slug):
    model = ModelVariant.query.filter_by(detail_slug=slug).first()
    if not model:
        abort(404)
    siblings = (ModelVariant.query
                .filter(ModelVariant.model_range == model.model_range)
                .order_by(ModelVariant.price_value).all())
    configured = ConfiguratorOption.query.filter_by(model_code=model.model_type).count()
    return render_template("model_detail.html", model=model,
                           siblings=siblings, option_count=configured)


# =====================================================================
# CONFIGURATOR
# =====================================================================

@app.route("/configurator/")
def configurator_home():
    codes = [r[0] for r in db.session.query(ConfiguratorOption.model_code).distinct()
             .order_by(ConfiguratorOption.model_code).all()]
    models = []
    for code in codes:
        m = ModelVariant.query.filter_by(model_type=code).first()
        opts = ConfiguratorOption.query.filter_by(model_code=code).count()
        models.append({"code": code, "model": m, "option_count": opts})
    return render_template("configurator_home.html", models=models)


@app.route("/configurator/en-US/mode/model/<code>")
def configurator_model(code):
    model = ModelVariant.query.filter_by(model_type=code).first()
    options = (ConfiguratorOption.query
               .filter_by(model_code=code)
               .order_by(ConfiguratorOption.price, ConfiguratorOption.option_id).all())
    if not options:
        abort(404)
    selected = request.args.getlist("opt")
    sel_ids = {o.split(":")[0] for o in selected}
    chosen = [o for o in options if o.option_id in sel_ids]
    base = model.price_value if model else 0
    total = base + sum(o.price for o in chosen)
    return render_template(
        "configurator_model.html", model=model, options=options, code=code,
        chosen=chosen, total=total, base=base, selected=selected,
        selected_ids=sel_ids, build_name=request.args.get("build_name", ""),
    )


@app.route("/configurator/en-US/mode/model/<code>/save", methods=["POST"])
@login_required
def configurator_save(code):
    model = ModelVariant.query.filter_by(model_type=code).first()
    options = ConfiguratorOption.query.filter_by(model_code=code).all()
    by_id = {o.option_id: o for o in options}
    picked = request.form.getlist("opt")
    chosen = []
    for pid in picked:
        o = by_id.get(pid)
        if o:
            chosen.append({"id": o.option_id, "name": o.name, "price": o.price})
    name = request.form.get("build_name", "").strip() or f"My {code} build"
    total = (model.price_value if model else 0) + sum(c["price"] for c in chosen)
    build = SavedBuild(
        user_id=current_user.id, build_name=name, model_code=code,
        model_name=model.model_name if model else code,
        options_json=json.dumps(chosen), total_price=total,
        created_on=datetime.utcnow().strftime("%Y-%m-%d"),
    )
    db.session.add(build)
    db.session.commit()
    flash(f"Build '{name}' saved to your My Porsche profile.")
    return redirect(url_for("saved_builds"))


# =====================================================================
# FINDER
# =====================================================================

PER_PAGE = 24

SORTS = {
    "recommended": "Recommended",
    "price-asc": "Price - Low to High",
    "price-desc": "Price - High to Low",
    "mileage-asc": "Mileage - Low to High",
    "year-desc": "Model year - High to Low",
    "year-asc": "Model year - Low to High",
}


@app.route("/finder/us/en-US/search")
def finder_search():
    q = Vehicle.query
    f = {
        "condition": request.args.get("condition", ""),
        "range": request.args.get("range", ""),
        "body": request.args.get("body", ""),
        "transmission": request.args.get("transmission", ""),
        "drivetrain": request.args.get("drivetrain", ""),
        "fuel": request.args.get("fuel", ""),
        "color": request.args.get("color", ""),
        "dealer": request.args.get("dealer", ""),
        "min_price": parse_int(request.args.get("min_price", "")),
        "max_price": parse_int(request.args.get("max_price", "")),
        "min_year": parse_int(request.args.get("min_year", "")),
        "max_mileage": parse_int(request.args.get("max_mileage", "")),
    }
    if f["condition"]:
        q = q.filter(Vehicle.condition == f["condition"])
    if f["range"]:
        q = q.filter(Vehicle.model_range == f["range"])
    if f["body"]:
        q = q.filter(Vehicle.body_type == f["body"])
    if f["transmission"]:
        q = q.filter(Vehicle.transmission == f["transmission"])
    if f["drivetrain"]:
        q = q.filter(Vehicle.drivetrain == f["drivetrain"])
    if f["fuel"]:
        q = q.filter(Vehicle.fuel == f["fuel"])
    if f["color"]:
        q = q.filter(Vehicle.color.ilike(f"%{f['color']}%"))
    if f["dealer"]:
        q = q.filter(Vehicle.dealer_name.ilike(f"%{f['dealer']}%"))
    if f["min_price"]:
        q = q.filter(Vehicle.price >= f["min_price"])
    if f["max_price"]:
        q = q.filter(Vehicle.price <= f["max_price"])
    if f["min_year"]:
        q = q.filter(Vehicle.model_year >= f["min_year"])
    if f["max_mileage"]:
        q = q.filter(Vehicle.mileage <= f["max_mileage"])

    sort = request.args.get("sort", "recommended")
    order = {
        "price-asc": Vehicle.price,
        "price-desc": Vehicle.price.desc(),
        "mileage-asc": Vehicle.mileage,
        "year-desc": Vehicle.model_year.desc(),
        "year-asc": Vehicle.model_year,
    }.get(sort)
    if order is not None:
        q = q.order_by(order)
    else:
        q = q.order_by(Vehicle.condition, Vehicle.price.desc())

    page = max(1, parse_int(request.args.get("page", "1"), 1))
    total = q.count()
    items = (q.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all())
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    # Pagination URLs are built here: Jinja cannot expand **dict-comprehensions.
    clean_args = {k: v for k, v in request.args.items() if k != "page" and v}
    page_links = []
    for p in range(1, pages + 1):
        if p <= 3 or p > pages - 3 or abs(p - page) <= 2:
            page_links.append({"p": p, "href": url_for("finder_search", page=p, **clean_args),
                               "current": p == page})
        elif p == 4 and page > 5 or p == pages - 3 and page < pages - 5:
            page_links.append({"p": None, "href": None, "current": False})
    prev_url = url_for("finder_search", page=page - 1, **clean_args) if page > 1 else None
    next_url = url_for("finder_search", page=page + 1, **clean_args) if page < pages else None

    facets = {
        "ranges": [r[0] for r in db.session.query(Vehicle.model_range).distinct().all() if r[0]],
        "bodies": [r[0] for r in db.session.query(Vehicle.body_type).distinct().order_by(Vehicle.body_type).all() if r[0]],
        "transmissions": [r[0] for r in db.session.query(Vehicle.transmission).distinct().order_by(Vehicle.transmission).all() if r[0]],
        "drivetrains": [r[0] for r in db.session.query(Vehicle.drivetrain).distinct().order_by(Vehicle.drivetrain).all() if r[0]],
        "fuels": [r[0] for r in db.session.query(Vehicle.fuel).distinct().order_by(Vehicle.fuel).all() if r[0]],
        "colors": [r[0] for r in db.session.query(Vehicle.color).distinct().order_by(Vehicle.color).all() if r[0]],
        "dealers": [r[0] for r in db.session.query(Vehicle.dealer_name).distinct().order_by(Vehicle.dealer_name).all() if r[0]],
    }
    return render_template("finder_search.html", items=items, total=total,
                           page=page, pages=pages, f=f, sort=sort,
                           sorts=SORTS, facets=facets,
                           page_links=page_links, prev_url=prev_url, next_url=next_url)


@app.route("/finder/us/en-US/details/<slug>")
def vehicle_detail(slug):
    vehicle = Vehicle.query.filter_by(slug=slug).first()
    if not vehicle:
        abort(404)
    similar = (Vehicle.query
               .filter(Vehicle.model_range == vehicle.model_range,
                       Vehicle.id != vehicle.id)
               .order_by(Vehicle.price).limit(4).all())
    saved = False
    if current_user.is_authenticated:
        saved = (SavedVehicle.query
                 .filter_by(user_id=current_user.id, vehicle_id=vehicle.id)
                 .first() is not None)
    return render_template("vehicle_detail.html", v=vehicle, similar=similar,
                           saved=saved)


@app.route("/finder/us/en-US/details/<slug>/save", methods=["POST"])
@login_required
def vehicle_save(slug):
    vehicle = Vehicle.query.filter_by(slug=slug).first()
    if not vehicle:
        abort(404)
    exists = (SavedVehicle.query
              .filter_by(user_id=current_user.id, vehicle_id=vehicle.id).first())
    if not exists:
        db.session.add(SavedVehicle(
            user_id=current_user.id, vehicle_id=vehicle.id,
            saved_on=datetime.utcnow().strftime("%Y-%m-%d"),
        ))
        db.session.commit()
        flash(f"{vehicle.full_title or vehicle.name} saved to your saved vehicles.")
    else:
        flash("This vehicle is already in your saved vehicles.")
    return redirect(url_for("vehicle_detail", slug=slug))


# =====================================================================
# DEALERS
# =====================================================================

@app.route("/usa/dealersearch/")
def dealer_search():
    state = request.args.get("state", "").strip().upper()
    q_text = request.args.get("q", "").strip()
    dealers = Dealer.query
    if state:
        dealers = dealers.filter(Dealer.state == state)
    if q_text:
        like = f"%{q_text}%"
        dealers = dealers.filter(or_(
            Dealer.name.ilike(like),
            Dealer.city.ilike(like),
            Dealer.zip.ilike(like),
        ))
    dealers = dealers.order_by(Dealer.state, Dealer.city, Dealer.name).all()
    states = [r[0] for r in db.session.query(Dealer.state).distinct()
              .order_by(Dealer.state).all() if r[0]]
    counts = {r[0]: r[1] for r in db.session.query(
        Dealer.state, db.func.count(Dealer.id)).group_by(Dealer.state).all()}
    return render_template("dealer_search.html", dealers=dealers, states=states,
                           counts=counts, state=state, q=q_text)


# =====================================================================
# SHOP
# =====================================================================

SHOP_CATEGORIES = ["Vehicle Accessories", "Clothing", "Home & Lifestyle"]


def _cart_items():
    cart = session.get("cart", {})
    items = []
    subtotal = 0
    for pid, qty in cart.items():
        p = db.session.get(ShopProduct, int(pid))
        if p:
            line = p.price_cents * qty
            subtotal += line
            items.append({"product": p, "qty": qty, "line_total": line})
    return items, subtotal


@app.route("/shop/")
def shop_home():
    cats = []
    for cat in SHOP_CATEGORIES:
        products = (ShopProduct.query
                    .filter_by(shop_category=cat)
                    .order_by(ShopProduct.price_cents).limit(4).all())
        cats.append({"name": cat, "products": products,
                     "count": ShopProduct.query.filter_by(shop_category=cat).count()})
    return render_template("shop_home.html", cats=cats)


@app.route("/shop/us/en-US/c/<category_slug>")
def shop_category(category_slug):
    label = {"accessories": "Vehicle Accessories",
             "vehicle-accessories": "Vehicle Accessories",
             "clothing": "Clothing",
             "home": "Home & Lifestyle",
             "home-lifestyle": "Home & Lifestyle"}.get(category_slug)
    if not label:
        abort(404)
    slug_alias = {"Vehicle Accessories": "vehicle-accessories",
                  "Clothing": "clothing",
                  "Home & Lifestyle": "home-lifestyle"}[label]
    sort = request.args.get("sort", "featured")
    q = ShopProduct.query.filter_by(shop_category=label)
    if sort == "price-asc":
        q = q.order_by(ShopProduct.price_cents)
    elif sort == "price-desc":
        q = q.order_by(ShopProduct.price_cents.desc())
    elif sort == "name":
        q = q.order_by(ShopProduct.name)
    else:
        q = q.order_by(ShopProduct.object_id)
    products = q.all()
    brands = [r[0] for r in db.session.query(ShopProduct.brand)
              .filter_by(shop_category=label).distinct().order_by(ShopProduct.brand).all() if r[0]]
    brand_f = request.args.get("brand", "").strip()
    if brand_f:
        products = [p for p in products if p.brand == brand_f]
    return render_template("shop_category.html", products=products,
                           label=label, category_slug=slug_alias,
                           brands=brands, brand_f=brand_f, sort=sort)


@app.route("/shop/us/en-US/p/<slug>")
def shop_product(slug):
    p = ShopProduct.query.filter_by(slug=slug).first()
    if not p:
        abort(404)
    related = (ShopProduct.query
               .filter(ShopProduct.shop_category == p.shop_category,
                       ShopProduct.id != p.id)
               .order_by(ShopProduct.price_cents).limit(4).all())
    return render_template("shop_product.html", p=p, related=related)


@app.route("/shop/cart")
def shop_cart():
    items, subtotal = _cart_items()
    shipping = 999 if items and subtotal < 15000 else (0 if items else 0)
    return render_template("shop_cart.html", items=items, subtotal=subtotal,
                           shipping=shipping,
                           total=subtotal + shipping)


@app.route("/shop/cart/add", methods=["POST"])
def shop_cart_add():
    pid = parse_int(request.form.get("product_id", ""), 0)
    qty = max(1, parse_int(request.form.get("quantity", "1"), 1))
    p = db.session.get(ShopProduct, pid)
    if not p:
        abort(404)
    cart = session.get("cart", {})
    cart[str(pid)] = cart.get(str(pid), 0) + qty
    session["cart"] = cart
    flash(f"Added {p.name} to your bag.")
    return redirect(url_for("shop_cart"))


@app.route("/shop/cart/update", methods=["POST"])
def shop_cart_update():
    cart = session.get("cart", {})
    for key, value in request.form.items():
        if key.startswith("qty_"):
            pid = key[len("qty_"):]
            qty = parse_int(value, 0)
            if qty <= 0:
                cart.pop(pid, None)
            else:
                cart[pid] = qty
    session["cart"] = cart
    return redirect(url_for("shop_cart"))


@app.route("/shop/checkout", methods=["GET", "POST"])
def shop_checkout():
    items, subtotal = _cart_items()
    if not items:
        flash("Your bag is empty.")
        return redirect(url_for("shop_cart"))
    shipping = 999 if subtotal < 15000 else 0
    total = subtotal + shipping
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        first = request.form.get("first_name", "").strip()
        last = request.form.get("last_name", "").strip()
        street = request.form.get("street", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip().upper()
        zip_code = request.form.get("zip", "").strip()
        errors = []
        if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Please enter a valid email address.")
        if not (first and last):
            errors.append("First and last name are required.")
        if not street:
            errors.append("Street address is required.")
        if not city:
            errors.append("City is required.")
        if state not in STATE_NAMES:
            errors.append("Please choose a valid US state.")
        if not re.match(r"^\d{5}$", zip_code):
            errors.append("ZIP code must be 5 digits.")
        if errors:
            for e in errors:
                flash(e)
            return render_template("shop_checkout.html", items=items,
                                   subtotal=subtotal, shipping=shipping,
                                   total=total, form=request.form)
        digest = hashlib.sha256(
            f"{email}:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}".encode()
        ).hexdigest()
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        order_number = "PS" + "".join(alphabet[int(c, 16) % 32] for c in digest[:10])
        order = ShopOrder(
            order_number=order_number,
            user_id=current_user.id if current_user.is_authenticated else None,
            email=email, first_name=first, last_name=last,
            street=street, city=city, state=state, zip=zip_code,
            subtotal_cents=subtotal, shipping_cents=shipping, total_cents=total,
            placed_on=datetime.utcnow().strftime("%Y-%m-%d"),
        )
        db.session.add(order)
        db.session.flush()  # assign order.id
        for it in items:
            db.session.add(ShopOrderItem(
                order_id=order.id,
                product_id=it["product"].id, quantity=it["qty"],
                unit_price_cents=it["product"].price_cents,
            ))
        db.session.commit()
        session.pop("cart", None)
        return redirect(url_for("shop_order_confirmation", order_number=order_number))
    return render_template("shop_checkout.html", items=items, subtotal=subtotal,
                           shipping=shipping, total=total, form={})


@app.route("/shop/order/<order_number>")
def shop_order_confirmation(order_number):
    order = ShopOrder.query.filter_by(order_number=order_number).first()
    if not order:
        abort(404)
    return render_template("shop_order.html", order=order)


# =====================================================================
# MY PORSCHE (account)
# =====================================================================

@app.route("/my-porsche/")
def my_porsche():
    if current_user.is_authenticated:
        return redirect(url_for("my_porsche_profile"))
    return render_template("my_porsche.html")


@app.route("/my-porsche/sign-in", methods=["GET", "POST"])
def my_porsche_sign_in():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Welcome back to My Porsche.")
            return redirect(url_for("my_porsche_profile"))
        flash("Invalid email or password.")
    return render_template("sign_in.html")


@app.route("/my-porsche/register", methods=["GET", "POST"])
def my_porsche_register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        first = request.form.get("first_name", "").strip()
        last = request.form.get("last_name", "").strip()
        errors = []
        if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Please enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if not (first and last):
            errors.append("First and last name are required.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists.")
        if errors:
            for e in errors:
                flash(e)
            return render_template("register.html", form=request.form)
        user = User(email=email,
                    password_hash=bcrypt.generate_password_hash(password).decode(),
                    first_name=first, last_name=last,
                    created_at=datetime.utcnow().strftime("%Y-%m-%d"))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Your My Porsche account is ready.")
        return redirect(url_for("my_porsche_profile"))
    return render_template("register.html", form={})


@app.route("/my-porsche/sign-out")
@login_required
def my_porsche_sign_out():
    logout_user()
    flash("You have signed out of My Porsche.")
    return redirect(url_for("index"))


@app.route("/my-porsche/profile")
@login_required
def my_porsche_profile():
    saved = (SavedVehicle.query.filter_by(user_id=current_user.id)
             .order_by(SavedVehicle.id.desc()).all())
    builds = (SavedBuild.query.filter_by(user_id=current_user.id)
              .order_by(SavedBuild.id.desc()).all())
    orders = (ShopOrder.query.filter_by(user_id=current_user.id)
             .order_by(ShopOrder.id.desc()).all())
    return render_template("profile.html", saved=saved, builds=builds,
                           orders=orders)


@app.route("/my-porsche/saved-vehicles")
@login_required
def saved_vehicles():
    saved = (SavedVehicle.query.filter_by(user_id=current_user.id)
             .order_by(SavedVehicle.id.desc()).all())
    return render_template("saved_vehicles.html", saved=saved)


@app.route("/my-porsche/saved-builds")
@login_required
def saved_builds():
    builds = (SavedBuild.query.filter_by(user_id=current_user.id)
              .order_by(SavedBuild.id.desc()).all())
    return render_template("saved_builds.html", builds=builds)


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
