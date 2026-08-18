#!/usr/bin/env python3
"""Wine Access mirror - Flask application."""
import json
import os
import re
from datetime import datetime

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFERENCE_DATE = datetime(2026, 5, 20, 9, 0, 0)

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-wineaccess-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'wineaccess.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to manage your cellar, cart, and orders."

STOP_WORDS = {
    "the", "a", "an", "and", "or", "for", "of", "in", "on", "to",
    "with", "wine", "wines",
}


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), default="")
    address_line1 = db.Column(db.String(180), default="")
    address_line2 = db.Column(db.String(180), default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(40), default="")
    zip_code = db.Column(db.String(20), default="")
    favorite_variety = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=lambda: REFERENCE_DATE)

    cart_items = db.relationship("CartItem", backref="user", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", backref="user", cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="user", cascade="all, delete-orphan")
    payment_methods = db.relationship("PaymentMethod", backref="user", cascade="all, delete-orphan")
    memberships = db.relationship("ClubMembership", backref="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def first_name(self):
        return self.display_name.split()[0]


class Wine(db.Model):
    __tablename__ = "wines"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    name = db.Column(db.String(260), nullable=False)
    vintage = db.Column(db.Integer, nullable=False)
    winery = db.Column(db.String(120), nullable=False)
    wine_type = db.Column(db.String(40), index=True)
    variety = db.Column(db.String(80), index=True)
    region = db.Column(db.String(120), index=True)
    country = db.Column(db.String(80), default="United States")
    appellation = db.Column(db.String(140), default="")
    price = db.Column(db.Float, nullable=False)
    list_price = db.Column(db.Float, default=0.0)
    case_price = db.Column(db.Float, default=0.0)
    rating = db.Column(db.Float, default=4.6)
    score = db.Column(db.Integer, default=92)
    reviewer = db.Column(db.String(80), default="Wine Access")
    inventory = db.Column(db.Integer, default=48)
    availability = db.Column(db.String(40), default="Ships Immediately")
    limited_offer = db.Column(db.Boolean, default=False)
    expert_pick = db.Column(db.Boolean, default=False)
    club_eligible = db.Column(db.Boolean, default=True)
    image = db.Column(db.String(260), default="")
    teaser = db.Column(db.String(240), default="")
    tasting_notes = db.Column(db.Text, default="")
    story = db.Column(db.Text, default="")
    pairings_json = db.Column(db.Text, default="[]")
    specs_json = db.Column(db.Text, default="{}")

    reviews = db.relationship("Review", backref="wine", cascade="all, delete-orphan")
    cart_items = db.relationship("CartItem", backref="wine", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", backref="wine", cascade="all, delete-orphan")

    @property
    def discount_percent(self):
        if not self.list_price or self.list_price <= self.price:
            return 0
        return round((self.list_price - self.price) / self.list_price * 100)

    @property
    def pairings(self):
        return json.loads(self.pairings_json or "[]")

    @property
    def specs(self):
        return json.loads(self.specs_json or "{}")

    @property
    def display_price(self):
        return f"${self.price:,.0f}" if self.price >= 100 else f"${self.price:,.2f}"


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    wine_id = db.Column(db.Integer, db.ForeignKey("wines.id"), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Integer, default=5)
    title = db.Column(db.String(160), default="")
    body = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: REFERENCE_DATE)


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    wine_id = db.Column(db.Integer, db.ForeignKey("wines.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)


class WishlistItem(db.Model):
    __tablename__ = "wishlist_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    wine_id = db.Column(db.Integer, db.ForeignKey("wines.id"), nullable=False)
    note = db.Column(db.String(180), default="")


class PaymentMethod(db.Model):
    __tablename__ = "payment_methods"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    cardholder = db.Column(db.String(120), nullable=False)
    brand = db.Column(db.String(40), nullable=False)
    last4 = db.Column(db.String(4), nullable=False)
    exp_month = db.Column(db.Integer, nullable=False)
    exp_year = db.Column(db.Integer, nullable=False)
    is_default = db.Column(db.Boolean, default=False)


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    order_number = db.Column(db.String(30), unique=True, nullable=False)
    status = db.Column(db.String(40), default="Processing")
    placed_at = db.Column(db.DateTime, default=lambda: REFERENCE_DATE)
    subtotal = db.Column(db.Float, default=0.0)
    shipping = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    tracking_number = db.Column(db.String(80), default="")
    ship_to = db.Column(db.String(260), default="")

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    wine_id = db.Column(db.Integer, db.ForeignKey("wines.id"), nullable=False)
    wine_name = db.Column(db.String(260), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, nullable=False)


class Club(db.Model):
    __tablename__ = "clubs"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(140), nullable=False)
    tagline = db.Column(db.String(180), default="")
    bottles = db.Column(db.Integer, default=4)
    frequency = db.Column(db.String(80), default="Quarterly")
    price_per_shipment = db.Column(db.Float, default=120.0)
    description = db.Column(db.Text, default="")
    image = db.Column(db.String(260), default="")


class ClubMembership(db.Model):
    __tablename__ = "club_memberships"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False)
    status = db.Column(db.String(40), default="Active")
    next_ship_date = db.Column(db.String(40), default="June 18, 2026")

    club = db.relationship("Club")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    cart_count = 0
    saved_count = 0
    if current_user.is_authenticated:
        cart_count = sum(item.quantity for item in current_user.cart_items)
        saved_count = len(current_user.wishlist_items)
    return {
        "cart_count": cart_count,
        "saved_count": saved_count,
        "types": ["Red", "White", "Rose", "Sparkling", "Sweet", "Fortified"],
        "varieties": [
            "Cabernet Sauvignon", "Pinot Noir", "Chardonnay", "Sauvignon Blanc",
            "Red Blend", "Syrah", "Zinfandel", "Malbec",
        ],
    }


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def tokens_for(query):
    aliases = {"french": "france", "italian": "italy", "american": "united", "californian": "california"}
    return [
        aliases.get(token, token)
        for token in re.split(r"\W+", (query or "").lower())
        if len(token) > 2 and token not in STOP_WORDS
    ]


def scored_search(query, base_query=None):
    wines = list(base_query or Wine.query.all())
    tokens = tokens_for(query)
    if not tokens:
        return wines
    scored = []
    for wine in wines:
        haystack = " ".join(
            [
                wine.name, wine.winery, wine.wine_type or "", wine.variety or "",
                wine.region or "", wine.country or "", wine.appellation or "",
                wine.teaser or "", wine.tasting_notes or "",
            ]
        ).lower()
        score = sum(2 if token in wine.name.lower() else 1 for token in tokens if token in haystack)
        if score:
            scored.append((score, wine))
    scored.sort(key=lambda item: (-item[0], item[1].price, item[1].name))
    return [wine for _, wine in scored]


def filtered_wines():
    wines = Wine.query
    wine_type = request.args.get("type", "").strip()
    variety = request.args.get("variety", "").strip()
    region = request.args.get("region", "").strip()
    max_price = request.args.get("max_price", "").strip()
    availability = request.args.get("availability", "").strip()
    if wine_type:
        wines = wines.filter(Wine.wine_type.ilike(wine_type))
    if variety:
        wines = wines.filter(Wine.variety.ilike(variety))
    if region:
        wines = wines.filter(or_(Wine.region.ilike(f"%{region}%"), Wine.country.ilike(f"%{region}%")))
    if max_price:
        try:
            wines = wines.filter(Wine.price <= float(max_price))
        except ValueError:
            pass
    if availability:
        wines = wines.filter(Wine.availability.ilike(f"%{availability}%"))
    return wines


@app.route("/")
def index():
    wines = Wine.query.order_by(Wine.score.desc(), Wine.name.asc()).limit(4).all()
    collections = Wine.query.order_by(Wine.id).limit(3).all()
    return render_template(
        "index.html",
        wines=wines,
        collections=collections,
    )


@app.route("/store/")
@app.route("/store/is_offer/true/", defaults={"category": "is_offer/true"})
@app.route("/store/<path:category>/")
def store(category=None):
    query_text = request.args.get("q", "").strip()
    wines_query = filtered_wines()
    if category:
        if category.rstrip("/") == "is_offer/true":
            wines_query = wines_query.filter_by(limited_offer=True)
        category_map = {
            "red-wine": ("wine_type", "Red"),
            "white-wine": ("wine_type", "White"),
            "rose": ("wine_type", "Rose"),
            "sparkling": ("wine_type", "Sparkling"),
            "dessert-fortified": ("wine_type", "Fortified"),
            "sake": ("variety", "Sake"),
            "varietals/cabernet-sauvignon": ("variety", "Cabernet Sauvignon"),
            "varietals/pinot-noir": ("variety", "Pinot Noir"),
            "varietals/chardonnay": ("variety", "Chardonnay"),
            "varietals/sauvignon-blanc": ("variety", "Sauvignon Blanc"),
            "regions/united-states": ("country", "United States"),
            "regions/france": ("country", "France"),
            "regions/italy": ("country", "Italy"),
        }
        field, value = category_map.get(category.rstrip("/"), ("", ""))
        if field:
            wines_query = wines_query.filter(getattr(Wine, field).ilike(value))
    wines = scored_search(query_text, wines_query.all()) if query_text else wines_query.all()
    sort = request.args.get("sort", "newest")
    if sort == "price_low":
        wines.sort(key=lambda wine: wine.price)
    elif sort == "price_high":
        wines.sort(key=lambda wine: -wine.price)
    elif sort == "score":
        wines.sort(key=lambda wine: (-wine.score, wine.price))
    else:
        wines.sort(key=lambda wine: (-wine.limited_offer, -wine.vintage, wine.name))
    return render_template(
        "store.html",
        wines=wines,
        query_text=query_text,
        category=category,
        sort=sort,
        selected=request.args,
    )


@app.route("/search")
def search():
    args = request.args.to_dict()
    args.setdefault("q", request.args.get("q", ""))
    return redirect(url_for("store", **args))


@app.route("/catalog/<slug>/")
@app.route("/wine/<slug>")
def wine_detail(slug):
    wine = Wine.query.filter_by(slug=slug).first_or_404()
    related = (
        Wine.query.filter(Wine.id != wine.id)
        .filter(or_(Wine.variety == wine.variety, Wine.region == wine.region))
        .order_by(Wine.score.desc())
        .limit(4)
        .all()
    )
    in_saved = False
    if current_user.is_authenticated:
        in_saved = WishlistItem.query.filter_by(user_id=current_user.id, wine_id=wine.id).first() is not None
    return render_template("detail.html", wine=wine, related=related, in_saved=in_saved)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Welcome back to Wine Access.", "success")
            return redirect(request.args.get("next") or url_for("account"))
        flash("Email or password did not match.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        display_name = request.form.get("display_name", "").strip()
        if not display_name or "@" not in email or len(password) < 8:
            flash("Please provide a name, valid email, and password with at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account already exists for that email.", "error")
        else:
            username = slugify(email.split("@")[0])
            user = User(username=username, email=email, display_name=display_name)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Your Wine Access account is ready.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        current_user.display_name = request.form.get("display_name", current_user.display_name).strip()
        current_user.phone = request.form.get("phone", "").strip()
        current_user.address_line1 = request.form.get("address_line1", "").strip()
        current_user.address_line2 = request.form.get("address_line2", "").strip()
        current_user.city = request.form.get("city", "").strip()
        current_user.state = request.form.get("state", "").strip()
        current_user.zip_code = request.form.get("zip_code", "").strip()
        current_user.favorite_variety = request.form.get("favorite_variety", "").strip()
        db.session.commit()
        flash("Account details updated.", "success")
        return redirect(url_for("account"))
    return render_template("account.html")


@app.route("/saved")
@login_required
def saved():
    return render_template("saved.html", items=current_user.wishlist_items)


@app.post("/saved/add/<int:wine_id>")
@login_required
def add_saved(wine_id):
    wine = db.session.get(Wine, wine_id) or abort(404)
    if not WishlistItem.query.filter_by(user_id=current_user.id, wine_id=wine.id).first():
        db.session.add(WishlistItem(user_id=current_user.id, wine_id=wine.id))
        db.session.commit()
        flash(f"Saved {wine.name} to your cellar list.", "success")
    return redirect(request.referrer or url_for("wine_detail", slug=wine.slug))


@app.post("/saved/remove/<int:wine_id>")
@login_required
def remove_saved(wine_id):
    item = WishlistItem.query.filter_by(user_id=current_user.id, wine_id=wine_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash("Removed wine from your saved list.", "info")
    return redirect(request.referrer or url_for("saved"))


@app.post("/cart/add/<int:wine_id>")
@login_required
def add_cart(wine_id):
    wine = db.session.get(Wine, wine_id) or abort(404)
    quantity = max(1, min(24, int(request.form.get("quantity", 1) or 1)))
    item = CartItem.query.filter_by(user_id=current_user.id, wine_id=wine.id).first()
    if item:
        item.quantity = min(24, item.quantity + quantity)
    else:
        db.session.add(CartItem(user_id=current_user.id, wine_id=wine.id, quantity=quantity))
    db.session.commit()
    flash(f"Added {quantity} bottle(s) to your cart.", "success")
    return redirect(request.form.get("next") or url_for("cart"))


@app.route("/cart", methods=["GET", "POST"])
@login_required
def cart():
    if request.method == "POST":
        for item in list(current_user.cart_items):
            raw = request.form.get(f"qty_{item.id}", str(item.quantity))
            try:
                qty = int(raw)
            except ValueError:
                qty = item.quantity
            if qty <= 0:
                db.session.delete(item)
            else:
                item.quantity = min(qty, 24)
        db.session.commit()
        flash("Cart updated.", "success")
        return redirect(url_for("cart"))
    return render_template("cart.html", totals=cart_totals())


@app.post("/cart/remove/<int:item_id>")
@login_required
def remove_cart_item(item_id):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Removed item from cart.", "info")
    return redirect(url_for("cart"))


def cart_totals():
    subtotal = sum(item.quantity * item.wine.price for item in current_user.cart_items)
    shipping = 0 if subtotal >= 150 or subtotal == 0 else 19.95
    tax = round(subtotal * 0.0825, 2)
    total = round(subtotal + shipping + tax, 2)
    return {"subtotal": subtotal, "shipping": shipping, "tax": tax, "total": total}


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    if not current_user.cart_items:
        flash("Your cart is empty.", "info")
        return redirect(url_for("store"))
    totals = cart_totals()
    if request.method == "POST":
        required = ["address_line1", "city", "state", "zip_code", "card_last4"]
        missing = [field for field in required if not request.form.get(field, "").strip()]
        if missing:
            flash("Shipping address and payment details are required.", "error")
            return render_template("checkout.html", totals=totals)
        order = Order(
            user_id=current_user.id,
            order_number=f"WA-{REFERENCE_DATE.strftime('%y%m%d')}-{current_user.id}{Order.query.count()+1:03d}",
            status="Processing",
            placed_at=REFERENCE_DATE,
            subtotal=totals["subtotal"],
            shipping=totals["shipping"],
            tax=totals["tax"],
            total=totals["total"],
            tracking_number="Pending cellar release",
            ship_to=", ".join(
                [
                    request.form.get("address_line1", "").strip(),
                    request.form.get("city", "").strip(),
                    request.form.get("state", "").strip(),
                    request.form.get("zip_code", "").strip(),
                ]
            ),
        )
        db.session.add(order)
        db.session.flush()
        for item in list(current_user.cart_items):
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    wine_id=item.wine.id,
                    wine_name=item.wine.name,
                    quantity=item.quantity,
                    unit_price=item.wine.price,
                )
            )
            item.wine.inventory = max(0, item.wine.inventory - item.quantity)
            db.session.delete(item)
        db.session.commit()
        flash("Order placed. Your Wine Access shipment is being prepared.", "success")
        return redirect(url_for("order_detail", order_number=order.order_number))
    return render_template("checkout.html", totals=totals)


@app.route("/orders")
@login_required
def orders():
    return render_template("orders.html", orders=current_user.orders)


@app.route("/orders/<order_number>")
@login_required
def order_detail(order_number):
    order = Order.query.filter_by(user_id=current_user.id, order_number=order_number).first_or_404()
    return render_template("order_detail.html", order=order)


@app.route("/club/")
def club():
    clubs = Club.query.all()
    return render_template("club.html", clubs=clubs)


@app.route("/club/<slug>/")
def club_detail(slug):
    club_obj = Club.query.filter_by(slug=slug).first_or_404()
    related_clubs = Club.query.filter(Club.id != club_obj.id).order_by(Club.id).all()
    is_member = False
    if current_user.is_authenticated:
        is_member = (
            ClubMembership.query.filter_by(user_id=current_user.id, club_id=club_obj.id)
            .first()
            is not None
        )
    return render_template(
        "club_detail.html",
        club=club_obj,
        related_clubs=related_clubs,
        is_member=is_member,
    )


@app.route("/gifting/")
@app.route("/wine-club/gifting/")
def gifting():
    clubs = Club.query.all()
    return render_template("gifting.html", clubs=clubs)


@app.route("/podcast/")
def podcast():
    episodes = [
        {
            "number": "Episode 44",
            "date": "January 1, 2026",
            "title": "Season Three: Better Questions, Better Bottles",
            "wine": "2023 Domaine des Cinq Chemins Grolleau Gris Loire Valley",
        },
        {
            "number": "Episode 35",
            "date": "February 8, 2024",
            "title": "Building a Dream Cellar at Home",
            "wine": "2021 Massican Winery Annia White Wine Napa Valley",
        },
        {
            "number": "Episode 16",
            "date": "March 18, 2021",
            "title": "Wine, Family, and a Championship Mindset",
            "wine": "2018 Radio Silence Napa Valley Cabernet Sauvignon",
        },
    ]
    return render_template("podcast.html", episodes=episodes)


@app.route("/wine-team/")
def experts():
    experts = [
        {
            "name": "Laura Koffer",
            "role": "Advanced Sommelier",
            "quote": "I seek out iconic wines from classic regions, but I also look for a story and a connection beyond the sensory experience.",
            "image": "expert_laura.webp",
        },
        {
            "name": "Eduardo Dingler",
            "role": "Wine Judge, Sake Ambassador and Sommelier",
            "quote": "My favorite wines unfold in the glass over time, creating the kind of lasting memories great bottles are made for.",
            "image": "expert_eduardo.webp",
        },
        {
            "name": "Amanda McCrossin",
            "role": "Host of Wine Access Unfiltered",
            "quote": "Setting is my most important criterion for wine selection, but I am never opposed to opening something special on a Tuesday.",
            "image": "expert_amanda.webp",
        },
        {
            "name": "Vincent Morrow MS",
            "role": "Master Sommelier",
            "quote": "My favorite wines demonstrate authenticity: where they are grown, who produces them, and the moment in which they are enjoyed.",
            "image": "expert_vincent.webp",
        },
    ]
    wines = Wine.query.filter_by(expert_pick=True).order_by(Wine.score.desc()).limit(4).all()
    return render_template("experts.html", experts=experts, wines=wines)


@app.post("/club/join/<slug>")
@login_required
def join_club(slug):
    club_obj = Club.query.filter_by(slug=slug).first_or_404()
    existing = ClubMembership.query.filter_by(user_id=current_user.id, club_id=club_obj.id).first()
    if not existing:
        db.session.add(ClubMembership(user_id=current_user.id, club_id=club_obj.id))
        db.session.commit()
        flash(f"You joined {club_obj.name}.", "success")
    else:
        flash("You are already a member of that club.", "info")
    return redirect(url_for("account"))


@app.route("/contact-us/")
def contact():
    return render_template("contact.html")


@app.route("/where-we-ship/")
def where_we_ship():
    return render_template("where_we_ship.html")


@app.route("/_health")
def health():
    return {"ok": True, "site": "wineaccess", "wines": Wine.query.count()}


from seed_data import seed_benchmark_users, seed_database  # noqa: E402

with app.app_context():
    db.create_all()
    seed_database(db, Wine, Review, Club, slugify)
    seed_benchmark_users(
        db,
        User,
        Wine,
        CartItem,
        WishlistItem,
        PaymentMethod,
        Order,
        OrderItem,
        Club,
        ClubMembership,
        bcrypt,
        REFERENCE_DATE,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
