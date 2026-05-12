#!/usr/bin/env python3
"""MEGA.io mirror — encrypted storage, apps, account, checkout, and help."""
import json
import os
import re
from datetime import datetime
from functools import wraps

from flask import (
    Flask, abort, flash, redirect, render_template, request, session, url_for
)
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user, logout_user
)
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "mega.db")

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-mega-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log in to manage your MEGA account."

STOP_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "is", "are", "be", "by", "from", "how", "what", "which", "that",
    "this", "me", "my", "mega", "plan", "plans", "file", "files"
}


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(140), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), default="")
    company = db.Column(db.String(120), default="")
    role = db.Column(db.String(80), default="")
    address_line1 = db.Column(db.String(180), default="")
    address_line2 = db.Column(db.String(180), default="")
    city = db.Column(db.String(90), default="")
    state = db.Column(db.String(60), default="")
    postal_code = db.Column(db.String(20), default="")
    country = db.Column(db.String(80), default="United States")
    language = db.Column(db.String(40), default="English")
    timezone = db.Column(db.String(80), default="America/Indiana/Indianapolis")
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"), nullable=True)
    storage_used_gb = db.Column(db.Float, default=0)
    transfer_used_gb = db.Column(db.Float, default=0)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    recovery_key_saved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship("Plan", backref="users", lazy=True)
    cloud_items = db.relationship("CloudItem", backref="owner", lazy=True, cascade="all, delete-orphan")
    vault_items = db.relationship("VaultItem", backref="owner", lazy=True, cascade="all, delete-orphan")
    payment_methods = db.relationship("PaymentMethod", backref="user", lazy=True, cascade="all, delete-orphan")
    orders = db.relationship("SubscriptionOrder", backref="user", lazy=True, cascade="all, delete-orphan")
    tickets = db.relationship("SupportTicket", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode("utf-8")

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Plan(db.Model):
    __tablename__ = "plans"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    audience = db.Column(db.String(60), default="individual")
    category = db.Column(db.String(60), default="storage")
    monthly_price = db.Column(db.Float, default=0)
    yearly_price = db.Column(db.Float, default=0)
    storage_tb = db.Column(db.Float, default=0)
    transfer_tb = db.Column(db.Float, default=0)
    users_included = db.Column(db.Integer, default=1)
    vpn_devices = db.Column(db.Integer, default=0)
    pass_accounts = db.Column(db.Integer, default=0)
    s4_base_tb = db.Column(db.Float, default=0)
    active = db.Column(db.Boolean, default=True)
    popular = db.Column(db.Boolean, default=False)
    tagline = db.Column(db.String(240), default="")
    description = db.Column(db.Text, default="")
    features = db.Column(db.Text, default="[]")
    caveats = db.Column(db.Text, default="[]")
    image = db.Column(db.String(240), default="")

    def get_features(self):
        return _loads(self.features, [])

    def get_caveats(self):
        return _loads(self.caveats, [])

    def annual_savings(self):
        if not self.monthly_price:
            return 0
        return max(0, round(self.monthly_price * 12 - self.yearly_price, 2))


class ProductPage(db.Model):
    __tablename__ = "product_pages"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    section = db.Column(db.String(80), default="")
    summary = db.Column(db.String(300), default="")
    body = db.Column(db.Text, default="")
    hero_image = db.Column(db.String(240), default="")
    highlights = db.Column(db.Text, default="[]")
    faq = db.Column(db.Text, default="[]")
    nav_order = db.Column(db.Integer, default=100)

    def get_highlights(self):
        return _loads(self.highlights, [])

    def get_faq(self):
        return _loads(self.faq, [])


class Download(db.Model):
    __tablename__ = "downloads"
    id = db.Column(db.Integer, primary_key=True)
    product = db.Column(db.String(80), nullable=False, index=True)
    platform = db.Column(db.String(80), nullable=False, index=True)
    package_name = db.Column(db.String(120), nullable=False)
    version = db.Column(db.String(40), default="")
    size_mb = db.Column(db.Float, default=0)
    release_date = db.Column(db.String(20), default="")
    architecture = db.Column(db.String(60), default="")
    checksum = db.Column(db.String(80), default="")
    notes = db.Column(db.Text, default="")
    recommended = db.Column(db.Boolean, default=False)
    icon = db.Column(db.String(240), default="")


class HelpArticle(db.Model):
    __tablename__ = "help_articles"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    body = db.Column(db.Text, default="")
    applies_to = db.Column(db.String(160), default="")
    difficulty = db.Column(db.String(40), default="standard")
    updated_at = db.Column(db.String(20), default="2026-05-12")
    related_terms = db.Column(db.String(260), default="")


class CloudItem(db.Model):
    __tablename__ = "cloud_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(180), nullable=False, index=True)
    item_type = db.Column(db.String(30), default="file")
    folder = db.Column(db.String(160), default="/")
    extension = db.Column(db.String(20), default="")
    size_mb = db.Column(db.Float, default=0)
    modified_at = db.Column(db.String(20), default="")
    sync_status = db.Column(db.String(40), default="Synced")
    shared_with = db.Column(db.String(240), default="")
    share_link = db.Column(db.String(240), default="")
    favorite = db.Column(db.Boolean, default=False)
    backup_source = db.Column(db.String(120), default="")
    content_summary = db.Column(db.Text, default="")


class VaultItem(db.Model):
    __tablename__ = "vault_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(160), nullable=False, index=True)
    username = db.Column(db.String(140), default="")
    site_url = db.Column(db.String(220), default="")
    category = db.Column(db.String(60), default="Login")
    strength = db.Column(db.String(40), default="Strong")
    last_changed = db.Column(db.String(20), default="")
    two_factor = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, default="")


class PaymentMethod(db.Model):
    __tablename__ = "payment_methods"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    label = db.Column(db.String(80), default="Personal Visa")
    card_type = db.Column(db.String(40), default="Visa")
    last4 = db.Column(db.String(4), default="4242")
    exp_month = db.Column(db.Integer, default=12)
    exp_year = db.Column(db.Integer, default=2028)
    billing_country = db.Column(db.String(80), default="United States")
    is_default = db.Column(db.Boolean, default=False)


class SubscriptionOrder(db.Model):
    __tablename__ = "subscription_orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"), nullable=False)
    order_number = db.Column(db.String(40), unique=True, nullable=False)
    billing_cycle = db.Column(db.String(20), default="monthly")
    seats = db.Column(db.Integer, default=1)
    subtotal = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    status = db.Column(db.String(40), default="active")
    created_at = db.Column(db.String(20), default="")
    plan = db.relationship("Plan", lazy=True)


class SupportTicket(db.Model):
    __tablename__ = "support_tickets"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticket_number = db.Column(db.String(40), unique=True, nullable=False)
    subject = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80), default="General")
    priority = db.Column(db.String(30), default="Normal")
    status = db.Column(db.String(40), default="Open")
    message = db.Column(db.Text, default="")
    created_at = db.Column(db.String(20), default="")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def _loads(value, default):
    try:
        return json.loads(value or "null") or default
    except Exception:
        return default


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def tokenize(query):
    return [
        token for token in re.split(r"\W+", (query or "").lower())
        if len(token) > 1 and token not in STOP_WORDS
    ]


def score_text(tokens, *fields):
    haystack = " ".join(str(field or "") for field in fields).lower()
    score = 0
    for token in tokens:
        if token in haystack:
            score += 2
        elif any(word.startswith(token) for word in haystack.split()):
            score += 1
    return score


def scored_search(query, items, fields):
    tokens = tokenize(query)
    if not tokens:
        return list(items)
    ranked = []
    for item in items:
        score = score_text(tokens, *[getattr(item, field, "") for field in fields])
        if score:
            ranked.append((score, item.id, item))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [item for _, __, item in ranked]


def selected_plan():
    slug = session.get("checkout_plan")
    return Plan.query.filter_by(slug=slug, active=True).first() if slug else None


def current_cart_count():
    return 1 if selected_plan() else 0


def order_total(plan, billing_cycle, seats):
    seats = max(1, int(seats or 1))
    if billing_cycle == "yearly":
        base = plan.yearly_price
    else:
        base = plan.monthly_price
    subtotal = round(base * seats, 2)
    tax = round(subtotal * 0.07, 2)
    return subtotal, tax, round(subtotal + tax, 2)


def user_files_query():
    return CloudItem.query.filter_by(user_id=current_user.id)


def anonymous_allowed(route):
    @wraps(route)
    def wrapped(*args, **kwargs):
        return route(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {
        "nav_products": ProductPage.query.order_by(ProductPage.nav_order).limit(9).all(),
        "cart_plan": selected_plan(),
        "cart_count": current_cart_count(),
        "image_url": lambda name: url_for("static", filename=f"images/{name}"),
        "icon_url": lambda name: url_for("static", filename=f"icons/{name}"),
    }


@app.template_filter("json")
def json_filter(value):
    return _loads(value, [])


@app.template_filter("size")
def size_filter(value):
    value = float(value or 0)
    if value >= 1024:
        return f"{value / 1024:.2f} GB"
    return f"{value:.1f} MB"


@app.route("/")
def index():
    products = ProductPage.query.order_by(ProductPage.nav_order).limit(8).all()
    featured_plans = Plan.query.filter_by(active=True).order_by(Plan.popular.desc(), Plan.monthly_price).limit(4).all()
    help_articles = HelpArticle.query.order_by(HelpArticle.updated_at.desc()).limit(6).all()
    return render_template("index.html", products=products, featured_plans=featured_plans, help_articles=help_articles)


@app.route("/pricing")
def pricing():
    audience = request.args.get("audience", "")
    category = request.args.get("category", "")
    billing = request.args.get("billing", "monthly")
    plans_q = Plan.query.filter_by(active=True)
    if audience:
        plans_q = plans_q.filter_by(audience=audience)
    if category:
        plans_q = plans_q.filter_by(category=category)
    plans = plans_q.order_by(Plan.category, Plan.monthly_price, Plan.storage_tb).all()
    return render_template("pricing.html", plans=plans, audience=audience, category=category, billing=billing)


@app.route("/plans/<slug>")
def plan_detail(slug):
    plan = Plan.query.filter_by(slug=slug, active=True).first_or_404()
    alternatives = Plan.query.filter(Plan.id != plan.id, Plan.category == plan.category, Plan.active == True).limit(5).all()
    return render_template("plan_detail.html", plan=plan, alternatives=alternatives)


@app.route("/cart/add/<slug>", methods=["POST"])
def add_to_cart(slug):
    plan = Plan.query.filter_by(slug=slug, active=True).first_or_404()
    session["checkout_plan"] = plan.slug
    session["billing_cycle"] = request.form.get("billing_cycle", "monthly")
    session["seats"] = max(1, int(request.form.get("seats", 1) or 1))
    flash(f"{plan.name} is ready for checkout.", "success")
    return redirect(url_for("checkout"))


@app.route("/cart")
@login_required
def cart():
    return redirect(url_for("checkout"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    plan = selected_plan()
    if not plan:
        flash("Choose a plan before checkout.", "info")
        return redirect(url_for("pricing"))
    billing = request.form.get("billing_cycle") or session.get("billing_cycle", "monthly")
    seats = max(1, int(request.form.get("seats") or session.get("seats", 1) or 1))
    payment_id = request.form.get("payment_id", type=int)
    methods = PaymentMethod.query.filter_by(user_id=current_user.id).all()
    subtotal, tax, total = order_total(plan, billing, seats)
    if request.method == "POST":
        if not payment_id:
            flash("Select a saved payment method to complete checkout.", "error")
        else:
            order = SubscriptionOrder(
                user_id=current_user.id,
                plan_id=plan.id,
                order_number=f"MEGA-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{current_user.id}",
                billing_cycle=billing,
                seats=seats,
                subtotal=subtotal,
                tax=tax,
                total=total,
                status="active",
                created_at=datetime.utcnow().strftime("%Y-%m-%d"),
            )
            current_user.plan_id = plan.id
            db.session.add(order)
            db.session.commit()
            session.pop("checkout_plan", None)
            flash("Your MEGA subscription is active.", "success")
            return redirect(url_for("order_detail", order_number=order.order_number))
    return render_template("checkout.html", plan=plan, methods=methods, billing=billing, seats=seats, subtotal=subtotal, tax=tax, total=total)


@app.route("/orders/<order_number>")
@login_required
def order_detail(order_number):
    order = SubscriptionOrder.query.filter_by(user_id=current_user.id, order_number=order_number).first_or_404()
    return render_template("order_detail.html", order=order)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user)
            return redirect(request.args.get("next") or url_for("account"))
        flash("Email or password did not match.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if User.query.filter_by(email=email).first():
            flash("That email already has an account.", "error")
        elif request.form.get("password") != request.form.get("confirm"):
            flash("Passwords must match.", "error")
        else:
            user = User(
                username=slugify(email.split("@")[0]),
                email=email,
                display_name=request.form.get("display_name", "MEGA User"),
                recovery_key_saved=False,
            )
            user.set_password(request.form.get("password", ""))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    recent_files = user_files_query().order_by(CloudItem.modified_at.desc()).limit(6).all()
    recent_orders = SubscriptionOrder.query.filter_by(user_id=current_user.id).order_by(SubscriptionOrder.id.desc()).limit(5).all()
    tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(SupportTicket.id.desc()).limit(5).all()
    return render_template("account.html", recent_files=recent_files, recent_orders=recent_orders, tickets=tickets)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        for field in ["display_name", "phone", "company", "role", "address_line1", "address_line2", "city", "state", "postal_code", "country", "language", "timezone"]:
            setattr(current_user, field, request.form.get(field, ""))
        current_user.two_factor_enabled = bool(request.form.get("two_factor_enabled"))
        current_user.recovery_key_saved = bool(request.form.get("recovery_key_saved"))
        db.session.commit()
        flash("Account details updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/billing/payment", methods=["GET", "POST"])
@login_required
def payment_methods():
    if request.method == "POST":
        last4 = re.sub(r"\D", "", request.form.get("card_number", ""))[-4:]
        if len(last4) != 4:
            flash("Enter a card number with at least four digits.", "error")
        else:
            if request.form.get("is_default"):
                PaymentMethod.query.filter_by(user_id=current_user.id).update({"is_default": False})
            method = PaymentMethod(
                user_id=current_user.id,
                label=request.form.get("label", "New card"),
                card_type=request.form.get("card_type", "Visa"),
                last4=last4,
                exp_month=int(request.form.get("exp_month", 12)),
                exp_year=int(request.form.get("exp_year", 2029)),
                billing_country=request.form.get("billing_country", "United States"),
                is_default=bool(request.form.get("is_default")),
            )
            db.session.add(method)
            db.session.commit()
            flash("Payment method saved.", "success")
            return redirect(url_for("payment_methods"))
    methods = PaymentMethod.query.filter_by(user_id=current_user.id).all()
    return render_template("payment_methods.html", methods=methods)


@app.route("/cloud")
@app.route("/drive")
@login_required
def cloud_drive():
    q = request.args.get("q", "")
    folder = request.args.get("folder", "")
    items = user_files_query().all()
    if folder:
        items = [item for item in items if item.folder == folder]
    if q:
        items = scored_search(q, items, ["name", "folder", "extension", "content_summary", "shared_with", "backup_source"])
    else:
        items = sorted(items, key=lambda item: (item.folder, item.item_type != "folder", item.name.lower()))
    folders = sorted({item.folder for item in user_files_query().all()})
    return render_template("cloud_drive.html", items=items, folders=folders, q=q, folder=folder)


@app.route("/cloud/new-folder", methods=["POST"])
@login_required
def new_folder():
    name = request.form.get("name", "").strip()
    parent = request.form.get("folder", "/")
    if not name:
        flash("Folder name is required.", "error")
    else:
        item = CloudItem(user_id=current_user.id, name=name, slug=slugify(f"{parent}-{name}-{current_user.id}"), item_type="folder", folder=parent, modified_at=datetime.utcnow().strftime("%Y-%m-%d"), content_summary="User-created folder")
        db.session.add(item)
        db.session.commit()
        flash("Folder created.", "success")
    return redirect(url_for("cloud_drive", folder=parent))


@app.route("/cloud/upload", methods=["POST"])
@login_required
def upload_file():
    name = request.form.get("name", "").strip()
    folder = request.form.get("folder", "/")
    if not name:
        flash("File name is required.", "error")
    else:
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        item = CloudItem(
            user_id=current_user.id,
            name=name,
            slug=slugify(f"{folder}-{name}-{current_user.id}-{datetime.utcnow().timestamp()}"),
            item_type="file",
            folder=folder,
            extension=ext,
            size_mb=float(request.form.get("size_mb", 12) or 12),
            modified_at=datetime.utcnow().strftime("%Y-%m-%d"),
            sync_status="Synced",
            content_summary=request.form.get("content_summary", "Uploaded through the MEGA web client."),
        )
        db.session.add(item)
        current_user.storage_used_gb += item.size_mb / 1024
        db.session.commit()
        flash("Upload added to Cloud drive.", "success")
    return redirect(url_for("cloud_drive", folder=folder))


@app.route("/cloud/item/<slug>", methods=["GET", "POST"])
@login_required
def file_detail(slug):
    item = CloudItem.query.filter_by(user_id=current_user.id, slug=slug).first_or_404()
    if request.method == "POST":
        item.shared_with = request.form.get("shared_with", item.shared_with)
        item.favorite = bool(request.form.get("favorite"))
        if request.form.get("create_link") and not item.share_link:
            item.share_link = f"https://mega.nz/file/{item.slug[:10].upper()}#webharbor"
        db.session.commit()
        flash("Sharing settings updated.", "success")
        return redirect(url_for("file_detail", slug=item.slug))
    return render_template("file_detail.html", item=item)


@app.route("/pass")
def pass_page():
    page = ProductPage.query.filter_by(slug="pass").first_or_404()
    return render_template("product_page.html", page=page)


@app.route("/vault", methods=["GET", "POST"])
@login_required
def vault():
    if request.method == "POST":
        item = VaultItem(
            user_id=current_user.id,
            title=request.form.get("title", "").strip(),
            slug=slugify(f"{request.form.get('title', '')}-{current_user.id}-{datetime.utcnow().timestamp()}"),
            username=request.form.get("username", ""),
            site_url=request.form.get("site_url", ""),
            category=request.form.get("category", "Login"),
            strength=request.form.get("strength", "Strong"),
            last_changed=datetime.utcnow().strftime("%Y-%m-%d"),
            two_factor=bool(request.form.get("two_factor")),
            notes=request.form.get("notes", ""),
        )
        if not item.title:
            flash("Vault entry title is required.", "error")
        else:
            db.session.add(item)
            db.session.commit()
            flash("Vault entry saved.", "success")
            return redirect(url_for("vault"))
    q = request.args.get("q", "")
    items = VaultItem.query.filter_by(user_id=current_user.id).all()
    if q:
        items = scored_search(q, items, ["title", "username", "site_url", "category", "notes", "strength"])
    return render_template("vault.html", items=items, q=q)


@app.route("/downloads")
def downloads():
    product = request.args.get("product", "")
    platform = request.args.get("platform", "")
    q = Download.query
    if product:
        q = q.filter_by(product=product)
    if platform:
        q = q.filter_by(platform=platform)
    downloads_list = q.order_by(Download.product, Download.platform, Download.recommended.desc()).all()
    return render_template("downloads.html", downloads=downloads_list, product=product, platform=platform)


@app.route("/downloads/<int:download_id>")
def download_detail(download_id):
    download = Download.query.get_or_404(download_id)
    return render_template("download_detail.html", download=download)


@app.route("/help")
def help_center():
    q = request.args.get("q", "")
    category = request.args.get("category", "")
    articles = HelpArticle.query.all()
    if category:
        articles = [a for a in articles if a.category == category]
    if q:
        articles = scored_search(q, articles, ["title", "body", "applies_to", "related_terms", "category"])
    categories = sorted({a.category for a in HelpArticle.query.all()})
    return render_template("help.html", articles=articles, categories=categories, q=q, category=category)


@app.route("/help/<slug>")
def help_article(slug):
    article = HelpArticle.query.filter_by(slug=slug).first_or_404()
    related = scored_search(article.related_terms, HelpArticle.query.filter(HelpArticle.id != article.id).all(), ["title", "body", "category"])[:4]
    return render_template("help_article.html", article=article, related=related)


@app.route("/contact", methods=["GET", "POST"])
@login_required
def contact():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        if not subject or not message:
            flash("Subject and message are required.", "error")
        else:
            ticket = SupportTicket(
                user_id=current_user.id,
                ticket_number=f"MEGA-T{datetime.utcnow().strftime('%m%d%H%M%S')}{current_user.id}",
                subject=subject,
                category=request.form.get("category", "General"),
                priority=request.form.get("priority", "Normal"),
                status="Open",
                message=message,
                created_at=datetime.utcnow().strftime("%Y-%m-%d"),
            )
            db.session.add(ticket)
            db.session.commit()
            flash("Support ticket submitted.", "success")
            return redirect(url_for("ticket_detail", ticket_number=ticket.ticket_number))
    return render_template("contact.html")


@app.route("/support/tickets/<ticket_number>")
@login_required
def ticket_detail(ticket_number):
    ticket = SupportTicket.query.filter_by(user_id=current_user.id, ticket_number=ticket_number).first_or_404()
    return render_template("ticket_detail.html", ticket=ticket)


@app.route("/search")
def search():
    q = request.args.get("q", "")
    plans = scored_search(q, Plan.query.filter_by(active=True).all(), ["name", "audience", "category", "tagline", "description", "features"])[:10]
    pages = scored_search(q, ProductPage.query.all(), ["title", "section", "summary", "body", "highlights"])[:10]
    articles = scored_search(q, HelpArticle.query.all(), ["title", "body", "applies_to", "related_terms", "category"])[:10]
    downloads_found = scored_search(q, Download.query.all(), ["product", "platform", "package_name", "version", "architecture", "notes"])[:10]
    files = []
    vault_items = []
    if current_user.is_authenticated:
        files = scored_search(q, user_files_query().all(), ["name", "folder", "extension", "content_summary", "shared_with", "backup_source"])[:10]
        vault_items = scored_search(q, VaultItem.query.filter_by(user_id=current_user.id).all(), ["title", "username", "site_url", "category", "notes", "strength"])[:10]
    return render_template("search.html", q=q, plans=plans, pages=pages, articles=articles, downloads=downloads_found, files=files, vault_items=vault_items)


@app.route("/<slug>")
def product_page(slug):
    page = ProductPage.query.filter_by(slug=slug).first()
    if not page:
        abort(404)
    return render_template("product_page.html", page=page)


@app.route("/_health")
def health():
    return {"ok": True, "site": "mega", "plans": Plan.query.count(), "users": User.query.count()}


with app.app_context():
    db.create_all()
    from seed_data import seed_benchmark_users, seed_database

    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
