#!/usr/bin/env python3
"""American Express mirror — cards, banking, rewards, offers, and account servicing."""
from __future__ import annotations

import json
import os
import re
import secrets
import hmac
from datetime import datetime
from functools import wraps

from flask import (
    Flask, abort, flash, redirect, render_template, request, session, url_for,
)
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user, logout_user,
)
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "american_express.db")

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-american-express-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log in to manage your American Express account."

STOP_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "is", "are", "be", "by", "from", "how", "what", "which", "that",
    "this", "me", "my", "card", "cards", "credit", "account", "amex",
    "american", "express", "your", "you", "can", "do", "does", "i",
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(140), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), default="")
    address_line1 = db.Column(db.String(180), default="")
    city = db.Column(db.String(90), default="")
    state = db.Column(db.String(60), default="")
    postal_code = db.Column(db.String(20), default="")
    member_since = db.Column(db.String(10), default="")
    created_at = db.Column(db.DateTime, default=datetime(2026, 1, 1))

    user_cards = db.relationship("UserCard", backref="owner", lazy=True, cascade="all, delete-orphan")
    bank_accounts = db.relationship("BankAccount", backref="owner", lazy=True, cascade="all, delete-orphan")
    enrollments = db.relationship("OfferEnrollment", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode("utf-8")

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)

    def total_points(self):
        return sum(uc.points_balance or 0 for uc in self.user_cards)


class CardCategory(db.Model):
    __tablename__ = "card_categories"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    filter_label = db.Column(db.String(80), default="")
    intro = db.Column(db.Text, default="")


class Card(db.Model):
    __tablename__ = "cards"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    short_name = db.Column(db.String(120), default="")
    product_type = db.Column(db.String(20), default="credit")  # credit | charge
    annual_fee_text = db.Column(db.String(120), default="")
    annual_fee_value = db.Column(db.Integer, default=0)
    apr_text = db.Column(db.String(160), default="")
    welcome_headline = db.Column(db.String(240), default="")
    welcome_body = db.Column(db.Text, default="")
    offer_end = db.Column(db.DateTime, nullable=True)
    rewards_summary = db.Column(db.String(120), default="")
    benefits_json = db.Column(db.Text, default="[]")
    benefit_images_json = db.Column(db.Text, default="{}")
    program = db.Column(db.String(80), default="")
    card_art = db.Column(db.String(200), default="")
    featured = db.Column(db.Boolean, default=False)

    categories = db.relationship("CardCategory", secondary="card_category_links", backref="cards", lazy=True)

    def benefits(self):
        try:
            return json.loads(self.benefits_json or "[]")
        except (ValueError, TypeError):
            return []

    def benefit_images(self):
        try:
            return json.loads(self.benefit_images_json or "{}")
        except (ValueError, TypeError):
            return {}


card_category_links = db.Table(
    "card_category_links",
    db.Column("card_id", db.Integer, db.ForeignKey("cards.id"), primary_key=True),
    db.Column("category_id", db.Integer, db.ForeignKey("card_categories.id"), primary_key=True),
)


class BankingProduct(db.Model):
    __tablename__ = "banking_products"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    short_name = db.Column(db.String(120), default="")
    category = db.Column(db.String(40), default="savings")
    apy = db.Column(db.Float, nullable=True)
    apy_text = db.Column(db.String(160), default="")
    headline = db.Column(db.String(240), default="")
    intro = db.Column(db.Text, default="")
    features_json = db.Column(db.Text, default="[]")
    image = db.Column(db.String(200), default="")

    def features(self):
        try:
            return json.loads(self.features_json or "[]")
        except (ValueError, TypeError):
            return []


class CDTerm(db.Model):
    __tablename__ = "cd_terms"
    id = db.Column(db.Integer, primary_key=True)
    term_months = db.Column(db.Integer, nullable=False)
    apy = db.Column(db.Float, nullable=False)


class AmexOffer(db.Model):
    __tablename__ = "amex_offers"
    id = db.Column(db.Integer, primary_key=True)
    merchant = db.Column(db.String(120), nullable=False)
    domain = db.Column(db.String(160), default="")
    headline = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default="")
    credit_value = db.Column(db.Float, default=0)
    expires = db.Column(db.DateTime, nullable=True)

    enrollments = db.relationship("OfferEnrollment", backref="offer", lazy=True)


class RedemptionOption(db.Model):
    __tablename__ = "redemption_options"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    points_per_unit = db.Column(db.Integer, default=10000)
    unit_label = db.Column(db.String(120), default="")
    unit_value = db.Column(db.Float, default=100.0)


class UserCard(db.Model):
    __tablename__ = "user_cards"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)
    last4 = db.Column(db.String(4), default="0000")
    opened_date = db.Column(db.DateTime, default=datetime(2024, 1, 1))
    credit_limit = db.Column(db.Float, default=0)
    current_balance = db.Column(db.Float, default=0)
    points_balance = db.Column(db.Integer, default=0)

    card = db.relationship("Card", backref="holders", lazy=True)
    transactions = db.relationship("Transaction", backref="user_card", lazy=True, cascade="all, delete-orphan")
    statements = db.relationship("Statement", backref="user_card", lazy=True, cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="user_card", lazy=True, cascade="all, delete-orphan")
    reward_activity = db.relationship("RewardActivity", backref="user_card", lazy=True, cascade="all, delete-orphan")

    def available_credit(self):
        return round((self.credit_limit or 0) - (self.current_balance or 0), 2)


class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True)
    user_card_id = db.Column(db.Integer, db.ForeignKey("user_cards.id"), nullable=False, index=True)
    date = db.Column(db.DateTime, nullable=False)
    merchant = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(60), default="Other")
    amount = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(30), default="Posted")
    points_earned = db.Column(db.Integer, default=0)
    description = db.Column(db.String(240), default="")


class Statement(db.Model):
    __tablename__ = "statements"
    id = db.Column(db.Integer, primary_key=True)
    user_card_id = db.Column(db.Integer, db.ForeignKey("user_cards.id"), nullable=False, index=True)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    opening_balance = db.Column(db.Float, default=0)
    closing_balance = db.Column(db.Float, default=0)
    min_payment = db.Column(db.Float, default=0)
    due_date = db.Column(db.DateTime, nullable=False)
    payment_status = db.Column(db.String(30), default="Paid")


class BankAccount(db.Model):
    __tablename__ = "bank_accounts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    account_type = db.Column(db.String(40), default="Checking")
    last4 = db.Column(db.String(4), default="0000")
    is_default = db.Column(db.Boolean, default=False)


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    user_card_id = db.Column(db.Integer, db.ForeignKey("user_cards.id"), nullable=False, index=True)
    date = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0)
    bank_account_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id"), nullable=True)
    status = db.Column(db.String(30), default="Processed")
    confirmation = db.Column(db.String(20), default="")

    bank_account = db.relationship("BankAccount", backref="payments", lazy=True)


class RewardActivity(db.Model):
    __tablename__ = "reward_activity"
    id = db.Column(db.Integer, primary_key=True)
    user_card_id = db.Column(db.Integer, db.ForeignKey("user_cards.id"), nullable=False, index=True)
    date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    points_change = db.Column(db.Integer, nullable=False, default=0)


class OfferEnrollment(db.Model):
    __tablename__ = "offer_enrollments"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amex_offer_id = db.Column(db.Integer, db.ForeignKey("amex_offers.id"), nullable=False)
    user_card_id = db.Column(db.Integer, db.ForeignKey("user_cards.id"), nullable=False)
    added_date = db.Column(db.DateTime, default=datetime(2026, 8, 1))
    status = db.Column(db.String(30), default="Added to Card")


class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)
    applicant_name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(140), nullable=False)
    phone = db.Column(db.String(40), default="")
    employment_status = db.Column(db.String(60), default="")
    annual_income = db.Column(db.Float, default=0)
    residence_type = db.Column(db.String(60), default="")
    submitted_at = db.Column(db.DateTime, default=datetime(2026, 9, 21))
    status = db.Column(db.String(40), default="Received")

    card = db.relationship("Card", backref="applications", lazy=True)


# ---------------------------------------------------------------------------
# Auth plumbing
# ---------------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    if uid <= 0:
        return None
    return db.session.get(User, uid)


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(24)
        session["csrf_token"] = token
    return token


@app.before_request
def protect_post_requests():
    if request.method != "POST":
        return None
    expected = session.get("csrf_token", "")
    submitted = request.form.get("csrf_token", "")
    if not expected or not hmac.compare_digest(expected, submitted):
        abort(400)
    return None


@app.context_processor
def inject_common():
    return {
        "csrf_token": csrf_token,
        "now_label": "September 2026",
    }


# ---------------------------------------------------------------------------
# Search — scored token overlap (never strict AND)
# ---------------------------------------------------------------------------

def scored_search(query, rows, fields):
    tokens = [t.lower() for t in re.split(r"\W+", query or "")
              if t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return rows
    scored = []
    for row in rows:
        text = " ".join(str(getattr(row, f, "") or "") for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1].id if hasattr(pair[1], "id") else 0))
    return [row for _, row in scored]


# ---------------------------------------------------------------------------
# Public routes — cards
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    featured = Card.query.filter_by(featured=True).order_by(Card.id).all()
    travel = Card.query.join(Card.categories).filter(CardCategory.slug == "travel-rewards").order_by(Card.id).all()
    banking = BankingProduct.query.order_by(BankingProduct.id).all()
    return render_template("index.html", featured=featured, travel_cards=travel, banking=banking)


@app.route("/credit-cards/")
def cards_index():
    filter_slug = request.args.get("filter", "all")
    if filter_slug not in ["all", "featured"] and not CardCategory.query.filter_by(slug=filter_slug).first():
        abort(404)
    cards = Card.query.order_by(Card.id).all()
    if filter_slug == "featured":
        cards = [c for c in cards if c.featured]
    elif filter_slug != "all":
        cat = CardCategory.query.filter_by(slug=filter_slug).first()
        cards = [c for c in cards if cat in c.categories]
    categories = CardCategory.query.order_by(CardCategory.id).all()
    return render_template("cards_index.html", cards=cards, categories=categories, filter_slug=filter_slug)


@app.route("/credit-cards/card/<slug>/")
def card_detail(slug):
    card = Card.query.filter_by(slug=slug).first_or_404()
    related = [c for c in Card.query.filter(Card.id != card.id).all()
               if set(c2.slug for c2 in c.categories) & set(c3.slug for c3 in card.categories)][:3]
    return render_template("card_detail.html", card=card, related=related)


@app.route("/credit-cards/category/<slug>/")
def card_category(slug):
    category = CardCategory.query.filter_by(slug=slug).first_or_404()
    cards = [c for c in Card.query.order_by(Card.id).all() if category in c.categories]
    return render_template("card_category.html", category=category, cards=cards)


@app.route("/credit-cards/compare/")
def compare_cards():
    slugs = [s for s in request.args.get("cards", "").split(",") if s]
    cards = [Card.query.filter_by(slug=s).first() for s in slugs]
    cards = [c for c in cards if c]
    if not cards or len(cards) > 3:
        return redirect(url_for("cards_index"))
    return render_template("compare.html", cards=cards)


@app.route("/credit-cards/card/<slug>/apply/", methods=["GET", "POST"])
def apply_card(slug):
    card = Card.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        name = (request.form.get("applicant_name") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        employment = (request.form.get("employment_status") or "").strip()
        income_raw = (request.form.get("annual_income") or "").strip()
        residence = (request.form.get("residence_type") or "").strip()
        errors = []
        if len(name) < 3 or len(name) > 120:
            errors.append("Enter your full legal name (3-120 characters).")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors.append("Enter a valid email address.")
        if phone and not re.match(r"^[0-9\-\+()\s]{7,20}$", phone):
            errors.append("Enter a valid phone number.")
        if employment not in ("Employed full-time", "Employed part-time", "Self-employed",
                              "Student", "Retired", "Not currently employed"):
            errors.append("Select your employment status.")
        try:
            income = round(float(income_raw), 2)
            if income < 0 or income > 10_000_000:
                errors.append("Annual income must be between $0 and $10,000,000.")
        except ValueError:
            errors.append("Annual income must be a number.")
            income = 0
        if residence not in ("Rent", "Own", "Live with family", "Other"):
            errors.append("Select your residence type.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("apply.html", card=card, form=request.form), 400
        application = Application(
            card_id=card.id, applicant_name=name, email=email, phone=phone,
            employment_status=employment, annual_income=income,
            residence_type=residence, submitted_at=datetime(2026, 9, 21),
        )
        db.session.add(application)
        db.session.commit()
        return redirect(url_for("application_status", application_id=application.id))
    return render_template("apply.html", card=card, form={})


@app.route("/credit-cards/applications/<int:application_id>/")
def application_status(application_id):
    application = db.session.get(Application, application_id)
    if not application:
        abort(404)
    return render_template("application_status.html", application=application)


# ---------------------------------------------------------------------------
# Public routes — banking
# ---------------------------------------------------------------------------

@app.route("/banking/high-yield-savings/")
def banking_hysa():
    product = BankingProduct.query.filter_by(slug="high-yield-savings").first_or_404()
    return render_template("banking_hysa.html", product=product)


@app.route("/banking/cd/")
def banking_cd():
    product = BankingProduct.query.filter_by(slug="cd").first_or_404()
    terms = CDTerm.query.order_by(CDTerm.term_months).all()
    return render_template("banking_cd.html", product=product, terms=terms)


@app.route("/banking/checking/")
def banking_checking():
    product = BankingProduct.query.filter_by(slug="checking").first_or_404()
    return render_template("banking_checking.html", product=product)


@app.route("/banking/personal-loans/")
def banking_loans():
    product = BankingProduct.query.filter_by(slug="personal-loans").first_or_404()
    return render_template("banking_loans.html", product=product)


# ---------------------------------------------------------------------------
# Public routes — benefits, offers, rewards, lounges, search
# ---------------------------------------------------------------------------

@app.route("/benefits/")
def benefits_index():
    return render_template("benefits_index.html")


@app.route("/benefits/offers/")
def offers_index():
    offers = AmexOffer.query.order_by(AmexOffer.id).all()
    return render_template("offers_index.html", offers=offers)


@app.route("/rewards/")
def rewards_index():
    options = RedemptionOption.query.order_by(RedemptionOption.id).all()
    return render_template("rewards_index.html", options=options)


@app.route("/travel/lounges/")
def lounges_index():
    lounge_cards = Card.query.join(Card.categories).filter(CardCategory.slug == "lounge-access").order_by(Card.id).all()
    return render_template("lounges_index.html", lounge_cards=lounge_cards)


@app.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    cards = banking = offers = []
    if q:
        cards = scored_search(q, Card.query.all(), ["name", "short_name", "rewards_summary", "program", "welcome_headline"])
        banking = scored_search(q, BankingProduct.query.all(), ["name", "short_name", "category", "intro"])
        offers = scored_search(q, AmexOffer.query.all(), ["merchant", "domain", "headline", "body"])
    return render_template("search.html", q=q, cards=cards, banking=banking, offers=offers)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account_home"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Incorrect User ID or password. Please try again.", "error")
            return render_template("login.html"), 401
        login_user(user)
        target = request.args.get("next") or request.form.get("next")
        if target and target.startswith("/") and not target.startswith("//"):
            return redirect(target)
        return redirect(url_for("account_home"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account_home"))
    if request.method == "POST":
        name = (request.form.get("display_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        errors = []
        if len(name) < 2 or len(name) > 80:
            errors.append("Display name must be 2-80 characters.")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors.append("Enter a valid email address.")
        if not re.match(r"^[a-z0-9_.]{3,40}$", username):
            errors.append("User ID must be 3-40 lowercase letters, digits, dots, or underscores.")
        if not (8 <= len(password) <= 72) or not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
            errors.append("Password must be 8-72 characters and include letters and numbers.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists.")
        if User.query.filter_by(username=username).first():
            errors.append("An account with this User ID already exists.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form=request.form), 400
        user = User(username=username, email=email, display_name=name,
                    password_hash=bcrypt.generate_password_hash(password).decode("utf-8"))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Your American Express account was created.", "success")
        return redirect(url_for("account_home"))
    return render_template("register.html", form={})


@app.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Account routes
# ---------------------------------------------------------------------------

@app.route("/account/")
@login_required
def account_home():
    user_cards = UserCard.query.filter_by(user_id=current_user.id).order_by(UserCard.id).all()
    total_balance = round(sum(uc.current_balance or 0 for uc in user_cards), 2)
    return render_template("account_home.html", user_cards=user_cards, total_balance=total_balance)


@app.route("/account/cards/<int:user_card_id>/")
@login_required
def account_card_detail(user_card_id):
    uc = db.session.get(UserCard, user_card_id)
    if not uc or uc.user_id != current_user.id:
        abort(404)
    transactions = (Transaction.query.filter_by(user_card_id=uc.id)
                    .order_by(Transaction.date.desc(), Transaction.id.desc()).limit(25).all())
    statements = Statement.query.filter_by(user_card_id=uc.id).order_by(Statement.period_end.desc()).all()
    return render_template("account_card.html", uc=uc, transactions=transactions, statements=statements)


@app.route("/account/statements/")
@login_required
def account_statements():
    user_cards = UserCard.query.filter_by(user_id=current_user.id).order_by(UserCard.id).all()
    statements = (Statement.query.filter(Statement.user_card_id.in_([uc.id for uc in user_cards]))
                  .order_by(Statement.period_end.desc()).all()) if user_cards else []
    return render_template("account_statements.html", statements=statements, user_cards={uc.id: uc for uc in user_cards})


@app.route("/account/statements/<int:statement_id>/")
@login_required
def account_statement_detail(statement_id):
    statement = db.session.get(Statement, statement_id)
    if not statement:
        abort(404)
    uc = statement.user_card
    if not uc or uc.user_id != current_user.id:
        abort(404)
    txns = (Transaction.query.filter_by(user_card_id=uc.id)
            .filter(Transaction.date >= statement.period_start)
            .filter(Transaction.date <= statement.period_end)
            .order_by(Transaction.date).all())
    return render_template("account_statement_detail.html", statement=statement, uc=uc, transactions=txns)


@app.route("/account/payments/", methods=["GET", "POST"])
@login_required
def account_payments():
    user_cards = UserCard.query.filter_by(user_id=current_user.id).order_by(UserCard.id).all()
    bank_accounts = BankAccount.query.filter_by(user_id=current_user.id).order_by(BankAccount.id).all()
    if request.method == "POST":
        try:
            user_card_id = int(request.form.get("user_card_id") or 0)
            amount = round(float(request.form.get("amount") or 0), 2)
            bank_account_id = int(request.form.get("bank_account_id") or 0)
        except ValueError:
            flash("Enter a valid payment amount.", "error")
            return redirect(url_for("account_payments"))
        uc = db.session.get(UserCard, user_card_id)
        bank = db.session.get(BankAccount, bank_account_id)
        if not uc or uc.user_id != current_user.id:
            flash("Select one of your Cards.", "error")
            return redirect(url_for("account_payments"))
        if not bank or bank.user_id != current_user.id:
            flash("Select one of your bank accounts.", "error")
            return redirect(url_for("account_payments"))
        if amount <= 0 or amount > 100000:
            flash("Payment amount must be greater than $0 and at most $100,000.", "error")
            return redirect(url_for("account_payments"))
        confirmation = "P" + secrets.token_hex(4).upper()[:7]
        payment = Payment(user_card_id=uc.id, date=datetime(2026, 9, 21), amount=amount,
                         bank_account_id=bank.id, status="Processed", confirmation=confirmation)
        uc.current_balance = round(max(0, (uc.current_balance or 0) - amount), 2)
        db.session.add(payment)
        db.session.commit()
        flash(f"Payment of ${amount:,.2f} to your {uc.card.name} was scheduled. Confirmation {confirmation}.", "success")
        return redirect(url_for("account_payments"))
    payments = (Payment.query.filter(Payment.user_card_id.in_([uc.id for uc in user_cards]))
                .order_by(Payment.date.desc(), Payment.id.desc()).all()) if user_cards else []
    return render_template("account_payments.html", user_cards=user_cards, bank_accounts=bank_accounts, payments=payments)


@app.route("/account/rewards/")
@login_required
def account_rewards():
    user_cards = UserCard.query.filter_by(user_id=current_user.id).order_by(UserCard.id).all()
    options = RedemptionOption.query.order_by(RedemptionOption.id).all()
    activity = (RewardActivity.query.filter(RewardActivity.user_card_id.in_([uc.id for uc in user_cards]))
                .order_by(RewardActivity.date.desc(), RewardActivity.id.desc()).all()) if user_cards else []
    return render_template("account_rewards.html", user_cards=user_cards, options=options, activity=activity)


@app.route("/account/rewards/redeem/", methods=["POST"])
@login_required
def account_rewards_redeem():
    try:
        option_id = int(request.form.get("option_id") or 0)
        user_card_id = int(request.form.get("user_card_id") or 0)
    except ValueError:
        flash("Select a redemption option.", "error")
        return redirect(url_for("account_rewards"))
    option = db.session.get(RedemptionOption, option_id)
    uc = db.session.get(UserCard, user_card_id)
    if not option or not uc or uc.user_id != current_user.id:
        flash("Select one of your Cards and a redemption option.", "error")
        return redirect(url_for("account_rewards"))
    if uc.points_balance is None or uc.points_balance < option.points_per_unit:
        flash(f"You need at least {option.points_per_unit:,} points on this Card to redeem this option.", "error")
        return redirect(url_for("account_rewards"))
    uc.points_balance -= option.points_per_unit
    activity = RewardActivity(
        user_card_id=uc.id, date=datetime(2026, 9, 21),
        description=f"Redeemed for {option.name} — {option.unit_label}",
        points_change=-option.points_per_unit,
    )
    db.session.add(activity)
    db.session.commit()
    flash(f"Redeemed {option.points_per_unit:,} points for a {option.unit_label}.", "success")
    return redirect(url_for("account_rewards"))


@app.route("/account/offers/")
@login_required
def account_offers():
    offers = AmexOffer.query.order_by(AmexOffer.id).all()
    user_cards = UserCard.query.filter_by(user_id=current_user.id).order_by(UserCard.id).all()
    enrolled = {(e.amex_offer_id, e.user_card_id) for e in
                OfferEnrollment.query.filter_by(user_id=current_user.id).all()}
    return render_template("account_offers.html", offers=offers, user_cards=user_cards, enrolled=enrolled)


@app.route("/account/offers/add/", methods=["POST"])
@login_required
def account_offers_add():
    try:
        offer_id = int(request.form.get("offer_id") or 0)
        user_card_id = int(request.form.get("user_card_id") or 0)
    except ValueError:
        flash("Select an offer and a Card.", "error")
        return redirect(url_for("account_offers"))
    offer = db.session.get(AmexOffer, offer_id)
    uc = db.session.get(UserCard, user_card_id)
    if not offer or not uc or uc.user_id != current_user.id:
        flash("Select one of your Cards.", "error")
        return redirect(url_for("account_offers"))
    if OfferEnrollment.query.filter_by(user_id=current_user.id, amex_offer_id=offer.id,
                                       user_card_id=uc.id).first():
        flash("This offer is already added to that Card.", "error")
        return redirect(url_for("account_offers"))
    enrollment = OfferEnrollment(user_id=current_user.id, amex_offer_id=offer.id,
                                  user_card_id=uc.id, added_date=datetime(2026, 9, 21))
    db.session.add(enrollment)
    db.session.commit()
    flash(f"{offer.headline} was added to your {uc.card.name}.", "success")
    return redirect(url_for("account_offers"))


@app.route("/account/benefits/")
@login_required
def account_benefits():
    user_cards = UserCard.query.filter_by(user_id=current_user.id).order_by(UserCard.id).all()
    return render_template("account_benefits.html", user_cards=user_cards)


@app.route("/account/profile/", methods=["GET", "POST"])
@login_required
def account_profile():
    if request.method == "POST":
        phone = (request.form.get("phone") or "").strip()
        address_line1 = (request.form.get("address_line1") or "").strip()
        city = (request.form.get("city") or "").strip()
        state = (request.form.get("state") or "").strip()
        postal_code = (request.form.get("postal_code") or "").strip()
        errors = []
        if phone and not re.match(r"^[0-9\-\+()\s]{7,20}$", phone):
            errors.append("Enter a valid phone number.")
        if len(address_line1) > 160:
            errors.append("Street address must be at most 160 characters.")
        if len(city) > 60:
            errors.append("City must be at most 60 characters.")
        if state and not re.match(r"^[A-Za-z ]{2,40}$", state):
            errors.append("State must be 2-40 letters.")
        if postal_code and not re.match(r"^[0-9A-Za-z\- ]{3,10}$", postal_code):
            errors.append("Enter a valid postal code.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("account_profile.html"), 400
        current_user.phone = phone
        current_user.address_line1 = address_line1
        current_user.city = city
        current_user.state = state
        current_user.postal_code = postal_code
        db.session.commit()
        flash("Your profile was updated.", "success")
        return redirect(url_for("account_profile"))
    return render_template("account_profile.html")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.route("/_health")
def health():
    return {
        "ok": True,
        "site": "american_express",
        "cards": Card.query.count(),
        "categories": CardCategory.query.count(),
        "banking_products": BankingProduct.query.count(),
        "cd_terms": CDTerm.query.count(),
        "offers": AmexOffer.query.count(),
        "redemption_options": RedemptionOption.query.count(),
        "users": User.query.count(),
        "user_cards": UserCard.query.count(),
        "transactions": Transaction.query.count(),
        "statements": Statement.query.count(),
        "payments": Payment.query.count(),
        "reward_entries": RewardActivity.query.count(),
    }


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(400)
def bad_request(error):
    return render_template("400.html"), 400


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()
    from seed_data import seed_benchmark_data, seed_database

    seed_database(db)
    seed_benchmark_data(db)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
