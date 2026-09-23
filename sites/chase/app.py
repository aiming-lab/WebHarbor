#!/usr/bin/env python3
"""Chase (chase.com) mirror — public banking product catalog (credit cards,
checking, savings, CDs), lending rates, branch locator, Education Center,
plus an authenticated online banking experience: accounts dashboard,
transactions, transfers, card payments, autopay, alerts, Ultimate Rewards,
statements and Credit Journey."""
import json
import math
import os
import random
import re
import sys
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "chase.db")

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-chase-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "logon"
login_manager.login_message = "Sign in to see your accounts, transactions and rewards."

# Reference date the snapshot was pinned against (live capture date).
MIRROR_REFERENCE_DATE = date(2026, 9, 22)
MIRROR_DATE_TEXT = "September 22, 2026"

STOP_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "is", "are", "be", "by", "from", "how", "what", "which", "that",
    "this", "chase", "account", "card", "credit", "your", "my",
}

CARD_CATEGORY_LABELS = {
    "cash-back": "Cash Back",
    "travel": "Travel",
    "rewards": "Rewards",
    "balance-transfer": "Balance Transfer",
    "credit-building": "Credit Building",
    "business": "Business",
    "no-annual-fee": "No Annual Fee",
    "intro-apr": "0% Intro APR",
    "airline": "Airline",
    "hotel": "Hotel",
}

CATEGORY_CARD_CHIPS = [
    ("all", "All Cards"), ("cash-back", "Cash Back"), ("travel", "Travel"),
    ("rewards", "Rewards"), ("business", "Business"), ("airline", "Airline"),
    ("hotel", "Hotel"), ("balance-transfer", "Balance Transfer"),
    ("credit-building", "Credit Building"), ("no-annual-fee", "No Annual Fee"),
    ("intro-apr", "0% Intro APR"),
]

TXN_CATEGORY_LABELS = {
    "groceries": "Groceries", "dining": "Dining", "gas": "Gas",
    "shopping": "Shopping", "utilities": "Utilities",
    "entertainment": "Entertainment", "travel": "Travel",
    "health": "Health", "home": "Home", "income": "Income",
    "transfer": "Transfer", "payment": "Payment",
}


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def _loads(text, default):
    try:
        return json.loads(text) if text else default
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(140), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    first_name = db.Column(db.String(80), default="")
    last_name = db.Column(db.String(80), default="")
    phone = db.Column(db.String(40), default="")
    address1 = db.Column(db.String(160), default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(20), default="")
    zip = db.Column(db.String(12), default="")
    created_at = db.Column(db.Date, default=MIRROR_REFERENCE_DATE)

    bank_accounts = db.relationship("BankAccount", backref="user", lazy=True,
                                    cascade="all, delete-orphan")
    cards = db.relationship("CreditCardAccount", backref="user", lazy=True,
                             cascade="all, delete-orphan")
    transactions = db.relationship("Transaction", backref="user", lazy=True,
                                   cascade="all, delete-orphan")
    transfers = db.relationship("Transfer", backref="user", lazy=True,
                                cascade="all, delete-orphan")
    alerts = db.relationship("Alert", backref="user", lazy=True,
                             cascade="all, delete-orphan")

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Card(db.Model):
    __tablename__ = "cards"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    network = db.Column(db.String(20), default="Visa")
    audience = db.Column(db.String(20), default="personal")
    categories = db.Column(db.Text, default="")
    tagline = db.Column(db.Text, default="")
    offer = db.Column(db.Text, default="")
    glance = db.Column(db.Text, default="")
    apr = db.Column(db.Text, default="")
    intro_apr = db.Column(db.Text, default="")
    fee_text = db.Column(db.Text, default="")
    fee_value = db.Column(db.Integer, default=0)
    card_art = db.Column(db.String(200), default="")
    pt_code = db.Column(db.String(40), default="")
    earn_rewards = db.Column(db.Text, default="")
    benefits = db.Column(db.Text, default="")
    stat_value = db.Column(db.String(40), default="")
    stat_label = db.Column(db.String(60), default="")
    order = db.Column(db.Integer, default=0)


class DepositProduct(db.Model):
    __tablename__ = "deposit_products"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    product_type = db.Column(db.String(20), nullable=False)  # checking/savings/cd
    tagline = db.Column(db.Text, default="")
    monthly_fee = db.Column(db.Float, default=0.0)
    fee_text = db.Column(db.Text, default="")
    fee_waiver = db.Column(db.Text, default="")
    min_deposit = db.Column(db.Float, default=0.0)
    apy_text = db.Column(db.Text, default="")
    features = db.Column(db.Text, default="")
    tab = db.Column(db.String(20), default="all")
    image = db.Column(db.String(200), default="")
    order = db.Column(db.Integer, default=0)


class CD(db.Model):
    __tablename__ = "cds"
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(20), nullable=False)
    apy = db.Column(db.Float, nullable=False)
    min_deposit = db.Column(db.Float, default=1000.0)


class MortgageRate(db.Model):
    __tablename__ = "mortgage_rates"
    id = db.Column(db.Integer, primary_key=True)
    loan_type = db.Column(db.String(40), nullable=False)
    rate = db.Column(db.Float, nullable=False)
    apr = db.Column(db.Float, nullable=False)
    monthly_payment = db.Column(db.Float, nullable=False)
    points = db.Column(db.Float, nullable=False)
    points_cost = db.Column(db.Float, nullable=False)
    loan_amount = db.Column(db.Float, nullable=False)
    ltv = db.Column(db.String(10), default="")
    order = db.Column(db.Integer, default=0)


class AutoRate(db.Model):
    __tablename__ = "auto_rates"
    id = db.Column(db.Integer, primary_key=True)
    product = db.Column(db.String(60), nullable=False)
    apr = db.Column(db.Float, nullable=False)
    term_months = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    example_payment = db.Column(db.Float, nullable=False)
    example_note = db.Column(db.Text, default="")
    order = db.Column(db.Integer, default=0)


class Branch(db.Model):
    __tablename__ = "branches"
    id = db.Column(db.Integer, primary_key=True)
    chase_id = db.Column(db.String(40), default="")
    name = db.Column(db.String(120), nullable=False)
    loc_type = db.Column(db.String(10), default="BRANCH")
    address1 = db.Column(db.String(160), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(4), default="")
    zip = db.Column(db.String(12), default="")
    lat = db.Column(db.Float, default=0.0)
    lng = db.Column(db.Float, default=0.0)
    phone = db.Column(db.String(40), default="")
    fax = db.Column(db.String(40), default="")
    hours = db.Column(db.Text, default="")
    drive_up = db.Column(db.Text, default="")
    services = db.Column(db.Text, default="")
    atm_24h = db.Column(db.Boolean, default=False)
    lobby_atm = db.Column(db.Boolean, default=False)
    vestibule_atm = db.Column(db.Boolean, default=False)
    search_city = db.Column(db.String(60), default="")

    @property
    def hours_dict(self):
        return _loads(self.hours, {})

    @property
    def drive_up_dict(self):
        return _loads(self.drive_up, {})

    @property
    def service_list(self):
        return _loads(self.services, [])

    def hours_label(self):
        d = self.hours_dict
        if not d:
            return "Lobby closed" if self.loc_type == "BRANCH" else "ATM available anytime"
        return ", ".join(f"{k.title()} {v[0]}–{v[1]}" for k, v in d.items())


class Article(db.Model):
    __tablename__ = "articles"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), default="")
    category_slug = db.Column(db.String(80), default="")
    minutes = db.Column(db.Integer, default=5)
    hero = db.Column(db.String(200), default="")
    insights = db.Column(db.Text, default="")
    body = db.Column(db.Text, default="")
    upstream_url = db.Column(db.String(300), default="")

    @property
    def insight_list(self):
        return _loads(self.insights, [])


class BankAccount(db.Model):
    __tablename__ = "bank_accounts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    acct_type = db.Column(db.String(20), default="checking")
    masked = db.Column(db.String(8), default="")
    balance = db.Column(db.Float, default=0.0)
    opened = db.Column(db.Date)

    @property
    def label(self):
        return f"{self.name} ({self.acct_type.title()}) ...{self.masked}"


class CreditCardAccount(db.Model):
    __tablename__ = "card_accounts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)
    masked = db.Column(db.String(8), default="")
    credit_limit = db.Column(db.Float, default=0.0)
    balance = db.Column(db.Float, default=0.0)
    points = db.Column(db.Integer, default=0)
    opened = db.Column(db.Date)
    autopay = db.Column(db.Boolean, default=False)
    payment_due = db.Column(db.Date)
    statement_balance = db.Column(db.Float, default=0.0)

    card = db.relationship("Card")

    @property
    def label(self):
        return f"...{self.masked}"

    @property
    def available(self):
        return round(self.credit_limit - self.balance, 2)


class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    account_type = db.Column(db.String(20), default="checking")  # checking/savings/card
    bank_account_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id"))
    card_account_id = db.Column(db.Integer, db.ForeignKey("card_accounts.id"))
    posted = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(200), default="")
    merchant = db.Column(db.String(160), default="")
    category = db.Column(db.String(30), default="")
    amount = db.Column(db.Float, default=0.0)  # + = debit/spend, - = credit/deposit
    pending = db.Column(db.Boolean, default=False)


class Transfer(db.Model):
    __tablename__ = "transfers"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    from_label = db.Column(db.String(160), nullable=False)
    to_label = db.Column(db.String(160), nullable=False)
    from_bank_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id"))
    to_bank_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id"))
    to_card_id = db.Column(db.Integer, db.ForeignKey("card_accounts.id"))
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="scheduled")  # scheduled/completed/canceled
    frequency = db.Column(db.String(20), default="one-time")
    memo = db.Column(db.String(200), default="")


class CardPayment(db.Model):
    __tablename__ = "card_payments"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    card_account_id = db.Column(db.Integer, db.ForeignKey("card_accounts.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    from_label = db.Column(db.String(160), default="")
    status = db.Column(db.String(20), default="completed")


class Alert(db.Model):
    __tablename__ = "alerts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    alert_type = db.Column(db.String(40), nullable=False)
    channel = db.Column(db.String(20), default="mobile")
    enabled = db.Column(db.Boolean, default=True)
    threshold = db.Column(db.Float)

    TYPE_LABELS = {
        "large_transaction": "Large transaction alert",
        "low_balance": "Low balance alert",
        "deposit_received": "Deposit received alert",
        "payment_due": "Payment due reminder",
        "card_charge": "Card charge alert",
    }

    @property
    def type_label(self):
        return self.TYPE_LABELS.get(self.alert_type, self.alert_type.replace("_", " ").title())


class RewardRedemption(db.Model):
    __tablename__ = "reward_redemptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    card_account_id = db.Column(db.Integer, db.ForeignKey("card_accounts.id"), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Float, nullable=False)
    redemption_type = db.Column(db.String(40), default="cash back")
    date = db.Column(db.Date, nullable=False)
    desc = db.Column(db.String(200), default="")


class Statement(db.Model):
    __tablename__ = "statements"
    id = db.Column(db.Integer, primary_key=True)
    card_account_id = db.Column(db.Integer, db.ForeignKey("card_accounts.id"), nullable=False)
    period_label = db.Column(db.String(40), nullable=False)
    open_date = db.Column(db.Date)
    close_date = db.Column(db.Date)
    payment_due = db.Column(db.Date)
    balance = db.Column(db.Float, default=0.0)
    points_earned = db.Column(db.Integer, default=0)


class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    card_slug = db.Column(db.String(120), nullable=False)
    card_name = db.Column(db.String(160), default="")
    applicant_name = db.Column(db.String(160), default="")
    status = db.Column(db.String(30), default="Received")
    ref_number = db.Column(db.String(40), default="")
    submitted = db.Column(db.Date)


class CreditScoreSnapshot(db.Model):
    __tablename__ = "credit_scores"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False)


class SupportArticle(db.Model):
    __tablename__ = "support_articles"
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(80), nullable=False)
    question = db.Column(db.String(300), nullable=False)
    answer = db.Column(db.Text, default="")
    order = db.Column(db.Integer, default=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def tokenize(query):
    return [t.lower() for t in re.split(r"\W+", query or "")
            if t.lower() not in STOP_WORDS and len(t) > 1]


def scored_search(query, items, fields):
    """Token-overlap scored search; never strict AND."""
    tokens = tokenize(query)
    if not tokens:
        return items
    scored = []
    for item in items:
        text = " ".join(str(getattr(item, f) or "") for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: -pair[0])
    return [item for _, item in scored]


def money(value):
    return f"${value:,.2f}" if value is not None else "$0.00"


@app.template_filter("usd2")
def usd2(value):
    return f"${value:,.2f}" if value is not None else "$0.00"


@app.template_filter("usd0")
def usd0(value):
    return f"${value:,.0f}" if value is not None else "$0.00"


def parse_money(text, default=None):
    try:
        return round(float(re.sub(r"[^0-9.]", "", str(text))), 2)
    except (ValueError, TypeError):
        return default


def card_by_slug(slug):
    return Card.query.filter_by(slug=slug).first()


def user_bank(user, acct_type):
    return next((a for a in user.bank_accounts if a.acct_type == acct_type), None)


def user_card(user, slug=None):
    if slug:
        return next((c for c in user.cards if c.card.slug == slug), None)
    return user.cards[0] if user.cards else None


def card_account_options(user):
    out = []
    for a in user.bank_accounts:
        out.append((f"bank:{a.id}", f"{a.name} ...{a.masked} ({money(a.balance)})"))
    for c in user.cards:
        out.append((f"card:{c.id}", f"{c.card.name} ...{c.masked} ({money(c.balance)} balance)"))
    return out


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    featured = Card.query.filter_by(audience="personal").order_by(Card.order).limit(4).all()
    return render_template("index.html", featured=featured)


@app.route("/credit-cards")
def credit_cards():
    cards = Card.query.order_by(Card.order).all()
    return render_template("cards_list.html", cards=cards, chips=CATEGORY_CARD_CHIPS,
                           active_cat="all")


@app.route("/credit-cards/category/<cat>")
def credit_cards_category(cat):
    if cat not in CARD_CATEGORY_LABELS:
        abort(404)
    cards = [c for c in Card.query.order_by(Card.order).all()
             if cat in (c.categories or "").split(",")]
    return render_template("cards_list.html", cards=cards, chips=CATEGORY_CARD_CHIPS,
                           active_cat=cat, category_label=CARD_CATEGORY_LABELS[cat])


@app.route("/credit-cards/compare")
def credit_cards_compare():
    slugs = [s for s in request.args.get("cards", "").split(",") if s][:3]
    cards = [c for c in (card_by_slug(s) for s in slugs) if c]
    earns = {c.id: _loads(c.earn_rewards, []) for c in cards}
    return render_template("cards_compare.html", cards=cards, earns=earns)


@app.route("/credit-cards/card/<slug>")
def credit_card_detail(slug):
    card = card_by_slug(slug)
    if not card:
        abort(404)
    related = [c for c in Card.query.filter(Card.id != card.id).all()
               if card.audience == c.audience and
               set((c.categories or "").split(",")) & set((card.categories or "").split(","))][:4]
    return render_template("card_detail.html", card=card, related=related,
                           earn=_loads(card.earn_rewards, []),
                           benefits=_loads(card.benefits, []))


@app.route("/credit-cards/card/<slug>/apply", methods=["GET", "POST"])
def credit_card_apply(slug):
    card = card_by_slug(slug)
    if not card:
        abort(404)
    if request.method == "POST":
        first = (request.form.get("first_name") or "").strip()
        last = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        income = parse_money(request.form.get("income"), None)
        errors = []
        if not first or not last:
            errors.append("Enter your first and last name.")
        if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""):
            errors.append("Enter a valid email address.")
        if not re.match(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", phone or ""):
            errors.append("Enter a valid 10-digit phone number.")
        if income is None or income < 0:
            errors.append("Enter your total annual income as a number.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("card_apply.html", card=card, form=request.form)
        ref = f"APP-{slug[:3].upper()}-{random.Random(f'{slug}{email}').randrange(100000, 999999)}"
        application = Application(
            user_id=current_user.id if current_user.is_authenticated else None,
            card_slug=slug, card_name=card.name,
            applicant_name=f"{first} {last}".strip(),
            status="Received", ref_number=ref, submitted=MIRROR_REFERENCE_DATE)
        db.session.add(application)
        db.session.commit()
        return render_template("card_apply_done.html", card=card, application=application)
    return render_template("card_apply.html", card=card, form={})


@app.route("/checking")
def checking():
    products = DepositProduct.query.filter_by(product_type="checking").order_by(DepositProduct.order).all()
    tabs = [("all", "All"), ("students", "Students & Kids"), ("premium", "Premium")]
    active = request.args.get("tab", "all")
    shown = [p for p in products if active == "all" or p.tab == active]
    feats = {p.id: _loads(p.features, []) for p in shown}
    return render_template("checking.html", products=shown, tabs=tabs, active=active, feats=feats)


@app.route("/checking/<slug>")
def checking_detail(slug):
    product = DepositProduct.query.filter_by(slug=slug, product_type="checking").first_or_404()
    others = DepositProduct.query.filter(DepositProduct.product_type == "checking",
                                         DepositProduct.slug != slug).order_by(DepositProduct.order).all()
    return render_template("deposit_detail.html", product=product,
                           features=_loads(product.features, []), others=others)


@app.route("/savings")
def savings():
    products = DepositProduct.query.filter_by(product_type="savings").order_by(DepositProduct.order).all()
    feats = {p.id: _loads(p.features, []) for p in products}
    return render_template("savings.html", products=products, feats=feats)


@app.route("/savings/<slug>")
def savings_detail(slug):
    product = DepositProduct.query.filter_by(slug=slug, product_type="savings").first_or_404()
    others = DepositProduct.query.filter(DepositProduct.product_type == "savings",
                                         DepositProduct.slug != slug).order_by(DepositProduct.order).all()
    return render_template("deposit_detail.html", product=product,
                           features=_loads(product.features, []), others=others)


@app.route("/cds")
def cds():
    terms = CD.query.order_by(CD.min_deposit, CD.id).all()
    return render_template("cds.html", terms=terms)


@app.route("/mortgage")
def mortgage():
    return render_template("mortgage.html")


@app.route("/mortgage/rates")
def mortgage_rates():
    rates = MortgageRate.query.order_by(MortgageRate.order).all()
    return render_template("mortgage_rates.html", rates=rates)


@app.route("/mortgage/calculator", methods=["GET", "POST"])
def mortgage_calculator():
    result = None
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "") for k in
                ("loan_amount", "term_years", "rate", "down_payment")}
        loan = parse_money(form.get("loan_amount"), None)
        years = parse_money(form.get("term_years"), None)
        rate = parse_money(form.get("rate"), None)
        if loan is None or loan <= 0 or loan > 10_000_000:
            flash("Enter a loan amount between $1 and $10,000,000.", "error")
        elif not years or years not in (10, 15, 20, 30):
            flash("Choose a term of 10, 15, 20 or 30 years.", "error")
        elif rate is None or not 0 < rate < 30:
            flash("Enter an interest rate between 0 and 30%.", "error")
        else:
            n = int(years) * 12
            r = rate / 100 / 12
            pay = loan * r / (1 - (1 + r) ** -n)
            total = pay * n
            result = {
                "loan": loan, "years": int(years), "rate": rate,
                "monthly": round(pay, 2), "total": round(total, 2),
                "total_interest": round(total - loan, 2),
            }
    return render_template("mortgage_calculator.html", result=result, form=form)


@app.route("/auto")
def auto():
    return render_template("auto.html")


@app.route("/auto/rates")
def auto_rates():
    rates = AutoRate.query.order_by(AutoRate.order).all()
    return render_template("auto_rates.html", rates=rates)


@app.route("/auto/calculator", methods=["GET", "POST"])
def auto_calculator():
    result = None
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "") for k in
                ("vehicle_price", "down_payment", "term_months", "apr", "trade_in")}
        price = parse_money(form.get("vehicle_price"), None)
        down = parse_money(form.get("down_payment"), 0.0) or 0.0
        trade = parse_money(form.get("trade_in"), 0.0) or 0.0
        term = parse_money(form.get("term_months"), None)
        apr = parse_money(form.get("apr"), None)
        if price is None or price <= 0 or price > 500_000:
            flash("Enter a vehicle price between $1 and $500,000.", "error")
        elif term not in (36, 48, 60, 72):
            flash("Choose a term of 36, 48, 60 or 72 months.", "error")
        elif apr is None or not 0 <= apr < 40:
            flash("Enter an APR between 0 and 40%.", "error")
        else:
            principal = max(price - down - trade, 0)
            n = int(term)
            r = apr / 100 / 12
            pay = principal * r / (1 - (1 + r) ** -n) if r else principal / n
            result = {
                "price": price, "down": down, "trade": trade, "term": n, "apr": apr,
                "financed": round(principal, 2), "monthly": round(pay, 2),
                "total": round(pay * n, 2),
            }
    return render_template("auto_calculator.html", result=result, form=form)


# ---------------------------------------------------------------------------
# Locator
# ---------------------------------------------------------------------------

@app.route("/locator")
def locator():
    q = (request.args.get("q") or "").strip()
    results = []
    searched = False
    if q:
        searched = True
        ql = q.lower()
        results = Branch.query.filter(
            db.or_(db.func.lower(Branch.city).like(f"%{ql}%"),
                   db.func.lower(Branch.state).like(f"%{ql}%"),
                   Branch.zip.like(f"{ql}%"),
                   db.func.lower(Branch.name).like(f"%{ql}%"),
                   db.func.lower(Branch.address1).like(f"%{ql}%"))).all()
        results.sort(key=lambda b: (b.loc_type != "BRANCH", b.city, b.name))
    return render_template("locator.html", q=q, results=results, searched=searched)


@app.route("/locator/branch/<int:branch_id>")
def branch_detail(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    nearby = Branch.query.filter(Branch.city == branch.city,
                                  Branch.id != branch.id).limit(6).all()
    return render_template("branch_detail.html", branch=branch, nearby=nearby)


# ---------------------------------------------------------------------------
# Education Center
# ---------------------------------------------------------------------------

@app.route("/education")
def education():
    articles = Article.query.order_by(Article.category, Article.id).all()
    active = request.args.get("category", "")
    if active:
        articles = [a for a in articles if a.category_slug == active]
    categories = [(slug, label) for slug, label in sorted(
        {(a.category_slug, a.category) for a in Article.query.all()})]
    return render_template("education.html", articles=articles, categories=categories,
                           active=active)


@app.route("/education/article/<slug>")
def article_detail(slug):
    article = Article.query.filter_by(slug=slug).first_or_404()
    related = Article.query.filter(Article.category == article.category,
                                    Article.id != article.id).limit(3).all()
    return render_template("article_detail.html", article=article, related=related)


# ---------------------------------------------------------------------------
# Customer service
# ---------------------------------------------------------------------------

@app.route("/customer-service")
def customer_service():
    topics = {}
    for a in SupportArticle.query.order_by(SupportArticle.topic, SupportArticle.order).all():
        topics.setdefault(a.topic, []).append(a)
    return render_template("customer_service.html", topics=topics)


@app.route("/credit-journey")
def credit_journey():
    return render_template("credit_journey.html")


# ---------------------------------------------------------------------------
# Site search
# ---------------------------------------------------------------------------

@app.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    card_hits, product_hits, article_hits, branch_hits = [], [], [], []
    if q:
        card_hits = scored_search(q, Card.query.all(), ["name", "tagline", "glance", "offer"])
        product_hits = scored_search(q, DepositProduct.query.all(),
                                      ["name", "tagline", "fee_waiver", "apy_text"])
        article_hits = scored_search(q, Article.query.all(), ["title", "body"])
        branch_hits = scored_search(q, Branch.query.limit(200).all(),
                                    ["name", "address1", "city"])[:10]
    total = len(card_hits) + len(product_hits) + len(article_hits) + len(branch_hits)
    return render_template("search.html", q=q, cards=card_hits[:12], products=product_hits[:8],
                           articles=article_hits[:10], branches=branch_hits[:10], total=total)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/logon", methods=["GET", "POST"])
def logon():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if not user or not user.check_password(password):
            flash("The username or password you entered is incorrect. Please try again.", "error")
            return render_template("logon.html", email=email)
        login_user(user)
        target = request.args.get("next")
        if target and target.startswith("/"):
            return redirect(target)
        return redirect(url_for("account"))
    return render_template("logon.html", email="")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        first = (request.form.get("first_name") or "").strip()
        last = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        errors = []
        if not first or not last:
            errors.append("Enter your first and last name.")
        if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Choose a password of at least 8 characters.")
        if User.query.filter(db.func.lower(User.email) == email).first():
            errors.append("An account with this email already exists.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form=request.form)
        user = User(
            username=email.split("@")[0].replace(".", "_") + "_new",
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            display_name=f"{first} {last}".strip(),
            first_name=first, last_name=last,
            created_at=MIRROR_REFERENCE_DATE)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Your Chase online profile is ready. Welcome!", "success")
        return redirect(url_for("account"))
    return render_template("register.html", form={})


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Online banking (authenticated)
# ---------------------------------------------------------------------------

@app.route("/account")
@login_required
def account():
    upcoming = Transfer.query.filter_by(user_id=current_user.id, status="scheduled").all()
    return render_template("account.html", upcoming=upcoming)


@app.route("/account/transactions")
@login_required
def account_transactions():
    txns = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.posted.desc()).all()
    acct = request.args.get("account", "")
    cat = request.args.get("category", "")
    q = (request.args.get("q") or "").strip()
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    if acct:
        if acct.startswith("bank:"):
            txns = [t for t in txns if t.bank_account_id == int(acct.split(":")[1])]
        elif acct.startswith("card:"):
            txns = [t for t in txns if t.card_account_id == int(acct.split(":")[1])]
    if cat:
        txns = [t for t in txns if t.category == cat]
    if q:
        txns = scored_search(q, txns, ["merchant", "description"])
    def parse_date(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    sd, ed = parse_date(start), parse_date(end)
    if sd:
        txns = [t for t in txns if t.posted >= sd]
    if ed:
        txns = [t for t in txns if t.posted <= ed]
    total_out = sum(t.amount for t in txns if t.amount > 0)
    total_in = sum(-t.amount for t in txns if t.amount < 0)
    return render_template("transactions.html", txns=txns[:150], q=q, cat=cat, acct=acct,
                           start=start, end=end, options=card_account_options(current_user),
                           category_labels=TXN_CATEGORY_LABELS,
                           total_out=total_out, total_in=total_in)


@app.route("/account/transfer", methods=["GET", "POST"])
@login_required
def account_transfer():
    if request.method == "POST":
        frm = request.form.get("from_account") or ""
        to = request.form.get("to_account") or ""
        amount = parse_money(request.form.get("amount"), None)
        when = request.form.get("when") or MIRROR_REFERENCE_DATE.isoformat()
        frequency = request.form.get("frequency", "one-time")
        memo = (request.form.get("memo") or "").strip()[:200]
        errors = []
        if not frm.startswith("bank:") or not (to.startswith("bank:") or to.startswith("card:")):
            errors.append("Choose both a source account and a destination.")
        if frm == to:
            errors.append("Choose two different accounts.")
        src = BankAccount.query.get(int(frm.split(":")[1])) if frm.startswith("bank:") else None
        if src is None or src.user_id != current_user.id:
            errors.append("Choose a valid source account.")
        elif amount is None or amount <= 0:
            errors.append("Enter an amount greater than $0.")
        elif amount > src.balance:
            errors.append(f"The amount exceeds your available balance of {money(src.balance)}.")
        if frequency not in ("one-time", "weekly", "monthly"):
            errors.append("Choose a valid transfer frequency.")
        try:
            when_date = datetime.strptime(when, "%Y-%m-%d").date()
        except ValueError:
            when_date, errors = None, errors + ["Enter the transfer date as YYYY-MM-DD."]
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("transfer.html", options=card_account_options(current_user),
                                   form=request.form)
        if to.startswith("bank:"):
            dst = BankAccount.query.get(int(to.split(":")[1]))
            to_label, to_bank, to_card = f"{dst.name} ...{dst.masked}", dst.id, None
        else:
            dst = CreditCardAccount.query.get(int(to.split(":")[1]))
            to_label, to_bank, to_card = f"{dst.card.name} ...{dst.masked}", None, dst.id
        transfer = Transfer(user_id=current_user.id,
                            from_label=f"{src.name} ...{src.masked}", to_label=to_label,
                            from_bank_id=src.id, to_bank_id=to_bank, to_card_id=to_card,
                            amount=amount, date=when_date,
                            status="scheduled" if when_date > MIRROR_REFERENCE_DATE else "completed",
                            frequency=frequency, memo=memo)
        db.session.add(transfer)
        if when_date <= MIRROR_REFERENCE_DATE:
            src.balance = round(src.balance - amount, 2)
            if to_bank:
                dst.balance = round(dst.balance + amount, 2)
            else:
                dst.balance = round(max(dst.balance - amount, 0), 2)
        db.session.commit()
        flash(f"Transfer of {money(amount)} from {transfer.from_label} to {to_label} is scheduled.", "success")
        return redirect(url_for("account_transfers"))
    return render_template("transfer.html", options=card_account_options(current_user),
                           form={"frequency": "one-time", "when": MIRROR_REFERENCE_DATE.isoformat()})


@app.route("/account/transfers")
@login_required
def account_transfers():
    transfers = Transfer.query.filter_by(user_id=current_user.id).order_by(Transfer.date.desc()).all()
    return render_template("transfers.html", transfers=transfers)


@app.route("/account/transfer/cancel/<int:transfer_id>", methods=["POST"])
@login_required
def transfer_cancel(transfer_id):
    transfer = Transfer.query.get_or_404(transfer_id)
    if transfer.user_id != current_user.id:
        abort(403)
    if transfer.status != "scheduled":
        flash("Only scheduled transfers can be canceled.", "error")
        return redirect(url_for("account_transfers"))
    transfer.status = "canceled"
    db.session.commit()
    flash(f"Scheduled transfer of {money(transfer.amount)} to {transfer.to_label} was canceled.", "success")
    return redirect(url_for("account_transfers"))


@app.route("/account/pay/<int:card_id>", methods=["GET", "POST"])
@login_required
def account_pay_card(card_id):
    card_acct = CreditCardAccount.query.get_or_404(card_id)
    if card_acct.user_id != current_user.id:
        abort(403)
    banks = [b for b in current_user.bank_accounts if b.acct_type == "checking"]
    if request.method == "POST":
        bank_id = parse_money(request.form.get("from_bank"), None)
        amount = parse_money(request.form.get("amount"), None)
        if bank_id is None:
            flash("Choose a checking account to pay from.", "error")
        else:
            src = BankAccount.query.get(int(bank_id))
            if src is None or src.user_id != current_user.id:
                flash("Choose a valid checking account.", "error")
            elif amount is None or amount <= 0:
                flash("Enter a payment amount greater than $0.", "error")
            elif amount > src.balance:
                flash(f"The amount exceeds your available balance of {money(src.balance)}.", "error")
            else:
                payment = CardPayment(user_id=current_user.id, card_account_id=card_acct.id,
                                      amount=amount, date=MIRROR_REFERENCE_DATE,
                                      from_label=f"{src.name} ...{src.masked}")
                db.session.add(payment)
                src.balance = round(src.balance - amount, 2)
                card_acct.balance = round(max(card_acct.balance - amount, 0), 2)
                txn = Transaction(user_id=current_user.id, account_type="checking",
                                  bank_account_id=src.id, posted=MIRROR_REFERENCE_DATE,
                                  description=f"Credit Card Payment to {card_acct.card.name} ...{card_acct.masked}",
                                  merchant="Chase Card Payment", category="payment",
                                  amount=amount)
                db.session.add(txn)
                db.session.commit()
                flash(f"Payment of {money(amount)} to {card_acct.card.name} ...{card_acct.masked} was sent.", "success")
                return redirect(url_for("account"))
    return render_template("pay_card.html", card=card_acct, banks=banks)


@app.route("/account/autopay", methods=["GET", "POST"])
@login_required
def account_autopay():
    if request.method == "POST":
        card_id = parse_money(request.form.get("card_id"), None)
        enable = request.form.get("enable") == "on"
        card_acct = CreditCardAccount.query.get(int(card_id)) if card_id else None
        if card_acct is None or card_acct.user_id != current_user.id:
            abort(403)
        card_acct.autopay = enable
        db.session.commit()
        state = "enabled" if enable else "turned off"
        flash(f"Automatic payments for {card_acct.card.name} ...{card_acct.masked} are {state}.", "success")
        return redirect(url_for("account_autopay"))
    return render_template("autopay.html", cards=current_user.cards)


@app.route("/account/alerts", methods=["GET", "POST"])
@login_required
def account_alerts():
    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "delete":
            alert = Alert.query.get_or_404(int(parse_money(request.form.get("alert_id"), 0) or 0))
            if alert.user_id != current_user.id:
                abort(403)
            db.session.delete(alert)
            db.session.commit()
            flash("Alert removed.", "success")
            return redirect(url_for("account_alerts"))
        if action == "toggle":
            alert = Alert.query.get_or_404(int(parse_money(request.form.get("alert_id"), 0) or 0))
            if alert.user_id != current_user.id:
                abort(403)
            alert.enabled = not alert.enabled
            db.session.commit()
            state = "paused" if not alert.enabled else "active"
            flash(f"{alert.type_label} is now {state}.", "success")
            return redirect(url_for("account_alerts"))
        alert_type = request.form.get("alert_type") or ""
        channel = request.form.get("channel") or "mobile"
        threshold = parse_money(request.form.get("threshold"), None)
        if alert_type not in Alert.TYPE_LABELS:
            flash("Choose a valid alert type.", "error")
        elif channel not in ("mobile", "email"):
            flash("Choose mobile or email for delivery.", "error")
        elif alert_type in ("large_transaction", "low_balance") and (threshold is None or threshold <= 0):
            flash("Enter a threshold amount greater than $0.", "error")
        else:
            db.session.add(Alert(user_id=current_user.id, alert_type=alert_type,
                                channel=channel, threshold=threshold, enabled=True))
            db.session.commit()
            flash("Alert saved.", "success")
        return redirect(url_for("account_alerts"))
    alerts = Alert.query.filter_by(user_id=current_user.id).order_by(Alert.id).all()
    return render_template("alerts.html", alerts=alerts, type_labels=Alert.TYPE_LABELS)


@app.route("/account/rewards", methods=["GET", "POST"])
@login_required
def account_rewards():
    if request.method == "POST":
        card_id = parse_money(request.form.get("card_id"), None)
        rtype = request.form.get("redemption_type") or "cash back"
        points = int(parse_money(request.form.get("points"), 0) or 0)
        card_acct = CreditCardAccount.query.get(int(card_id)) if card_id else None
        if card_acct is None or card_acct.user_id != current_user.id:
            abort(403)
        if rtype not in ("cash back", "travel", "gift card", "statement credit"):
            flash("Choose a valid redemption option.", "error")
        elif points <= 0 or points % 1000 != 0:
            flash("Enter points in whole thousands (e.g. 10,000).", "error")
        elif points > card_acct.points:
            flash(f"{card_acct.card.name} ...{card_acct.masked} only has {card_acct.points:,} points.", "error")
        else:
            rate = 0.01 if rtype in ("cash back", "statement credit") else 0.0125 if rtype == "travel" else 0.008
            value = round(points * rate, 2)
            db.session.add(RewardRedemption(user_id=current_user.id, card_account_id=card_acct.id,
                                            points=points, value=value, redemption_type=rtype,
                                            date=MIRROR_REFERENCE_DATE,
                                            desc=f"{rtype.title()} redemption"))
            card_acct.points -= points
            db.session.commit()
            flash(f"Redeemed {points:,} points for {money(value)} in {rtype}.", "success")
        return redirect(url_for("account_rewards"))
    redemptions = RewardRedemption.query.filter_by(user_id=current_user.id).order_by(RewardRedemption.date.desc()).all()
    total_points = sum(c.points for c in current_user.cards)
    return render_template("rewards.html", cards=current_user.cards, redemptions=redemptions,
                           total_points=total_points)


@app.route("/account/statements")
@login_required
def account_statements():
    statements = []
    for c in current_user.cards:
        for s in Statement.query.filter_by(card_account_id=c.id).order_by(Statement.close_date.desc()).all():
            statements.append((c, s))
    statements.sort(key=lambda pair: pair[1].close_date or date.min, reverse=True)
    return render_template("statements.html", statements=statements)


@app.route("/account/statements/<int:statement_id>")
@login_required
def account_statement_detail(statement_id):
    statement = Statement.query.get_or_404(statement_id)
    card_acct = CreditCardAccount.query.get_or_404(statement.card_account_id)
    if card_acct.user_id != current_user.id:
        abort(403)
    txns = Transaction.query.filter_by(card_account_id=card_acct.id).filter(
        Transaction.posted >= (statement.open_date or date.min),
        Transaction.posted <= (statement.close_date or date.max)).all()
    return render_template("statement_detail.html", card=card_acct, statement=statement, txns=txns)


@app.route("/account/credit-journey")
@login_required
def account_credit_journey():
    snapshots = CreditScoreSnapshot.query.filter_by(user_id=current_user.id).order_by(CreditScoreSnapshot.date).all()
    latest = snapshots[-1].score if snapshots else None
    prev = snapshots[-2].score if len(snapshots) > 1 else None
    delta = (latest - prev) if (latest is not None and prev is not None) else 0
    band = "Good"
    if latest is not None:
        if latest >= 800:
            band = "Exceptional"
        elif latest >= 740:
            band = "Very Good"
        elif latest >= 670:
            band = "Good"
        elif latest >= 580:
            band = "Fair"
        else:
            band = "Poor"
    return render_template("credit_journey_detail.html", snapshots=snapshots, latest=latest,
                           delta=delta, band=band)


@app.route("/account/profile", methods=["GET", "POST"])
@login_required
def account_profile():
    if request.method == "POST":
        first = (request.form.get("first_name") or "").strip()
        last = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        address1 = (request.form.get("address1") or "").strip()
        city = (request.form.get("city") or "").strip()
        state = (request.form.get("state") or "").strip().upper()
        zipc = (request.form.get("zip") or "").strip()
        errors = []
        if not first or not last:
            errors.append("First and last name are required.")
        if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Enter a valid email address.")
        clash = User.query.filter(db.func.lower(User.email) == email).first()
        if clash and clash.id != current_user.id:
            errors.append("Another account already uses this email.")
        if phone and not re.match(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", phone):
            errors.append("Enter a valid 10-digit phone number.")
        if state and len(state) != 2:
            errors.append("State must be a 2-letter code (e.g. NY).")
        if zipc and not re.match(r"\d{5}", zipc):
            errors.append("ZIP must be 5 digits.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("profile.html", user=current_user)
        current_user.first_name = first
        current_user.last_name = last
        current_user.display_name = f"{first} {last}".strip()
        current_user.email = email
        current_user.phone = phone
        current_user.address1 = address1
        current_user.city = city
        current_user.state = state
        current_user.zip = zipc
        db.session.commit()
        flash("Your profile was updated.", "success")
        return redirect(url_for("account_profile"))
    return render_template("profile.html", user=current_user)


# ---------------------------------------------------------------------------
# Health / errors / context
# ---------------------------------------------------------------------------

@app.route("/_health")
def health():
    return {
        "ok": True, "site": "chase",
        "cards": Card.query.count(),
        "deposit_products": DepositProduct.query.count(),
        "branches": Branch.query.count(),
        "articles": Article.query.count(),
        "users": User.query.count(),
        "transactions": Transaction.query.count(),
    }


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


@app.context_processor
def inject_globals():
    return {
        "current_year": 2026,
        "mirror_date": MIRROR_DATE_TEXT,
        "reference_date": MIRROR_REFERENCE_DATE,
        "card_categories": CARD_CATEGORY_LABELS,
    }


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

from seed_data import seed_database, seed_benchmark_users  # noqa: E402


# SQLAlchemy iterates `Table.indexes` as an identity-ordered set, so index
# creation order (and therefore the seed file bytes) would vary run to run if
# indexes were declared inline. They are created here in a fixed canonical
# order instead, which keeps `python seed_data.py` byte-reproducible.
INDEX_DDL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)",
    "CREATE INDEX IF NOT EXISTS ix_branches_city ON branches (city)",
    "CREATE INDEX IF NOT EXISTS ix_branches_state ON branches (state)",
    "CREATE INDEX IF NOT EXISTS ix_branches_zip ON branches (zip)",
    "CREATE INDEX IF NOT EXISTS ix_articles_category ON articles (category)",
    "CREATE INDEX IF NOT EXISTS ix_articles_category_slug ON articles (category_slug)",
    "CREATE INDEX IF NOT EXISTS ix_transactions_posted ON transactions (posted)",
    "CREATE INDEX IF NOT EXISTS ix_transactions_merchant ON transactions (merchant)",
    "CREATE INDEX IF NOT EXISTS ix_transactions_category ON transactions (category)",
    "CREATE INDEX IF NOT EXISTS ix_support_articles_topic ON support_articles (topic)",
)


def create_indexes():
    with db.engine.begin() as conn:
        for ddl in INDEX_DDL:
            conn.exec_driver_sql(ddl)


def bootstrap_site():
    with app.app_context():
        db.create_all()
        create_indexes()
        seed_database()
        seed_benchmark_users()


# `python app.py` loads this file as __main__; register it under its import name
# too so seed_data's `from app import ...` reuses this module instead of
# building a second Flask app + SQLAlchemy instance.
sys.modules.setdefault("app", sys.modules[__name__])

if os.environ.get("WEBSYN_SKIP_BOOTSTRAP") != "1":
    bootstrap_site()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
