#!/usr/bin/env python3
"""Deterministic seed for the Chase mirror.

`python seed_data.py` regenerates the reset seed DB (instance_seed/chase.db)
from the tracked _seed_*.py source snapshots alone — no scraped_data, no wall
clock, no random salt (random.Random(42) + frozen bcrypt hash), so the SQLite
artifact is byte-reproducible on every build. The same seed functions run at
every container boot and early-return on a populated DB, preserving the
byte-identical reset invariant.

Content provenance: product catalog, rates, branches and articles come from
the tracked _seed_*.py snapshots captured from chase.com (2026-09-22).
Benchmark-user banking data (accounts, transactions, transfers, alerts,
rewards, statements, credit history) is generated deterministically from
_seed_banking.py configuration.
"""
import json
import os
import random
import shutil
from datetime import date, timedelta

from _seed_banking import (ALERTS, CREDIT_HISTORY, MERCHANTS, MIRROR_DATE,
                           PASSWORD_HASH, RECURRING, REDEMPTIONS,
                           SCHEDULED_TRANSFERS, USERS)
from _seed_branches import BRANCHES
from _seed_cards import CARDS
from _seed_deposit import CHECKING, SAVINGS
from _seed_articles import ARTICLES

MIRROR = date.fromisoformat(MIRROR_DATE)
RNG_SEED = 42
WINDOW_START = MIRROR - timedelta(days=90)

SUPPORT_TOPICS = [
    ("Account access & login", [
        ("What do I do if I forgot my username or password?",
         "Select Forgot username/password on the sign-in panel at chase.com and follow the prompts. "
         "You can restore access using the email or phone number on your profile. If you are still "
         "locked out, call the personal banking line at 1-800-935-9935."),
        ("How do I change my Chase online password?",
         "After signing in, open the Profile menu and choose your security preferences. From there "
         "you can update your password, security questions and two-step delivery preferences."),
        ("Why is my account locked after too many sign-in attempts?",
         "For your protection, Chase locks online access after repeated failed attempts. Wait 24 "
         "hours or call 1-800-935-9935 to verify your identity and restore access."),
    ]),
    ("Cards", [
        ("How do I activate a new credit card?",
         "Sign in to your account, choose the new card, and select Activate card. You can also call "
         "the number on the sticker that came with your card."),
        ("How do I report a lost or stolen card?",
         "Call 1-800-935-9935 immediately, or lock your card instantly from the account dashboard "
         "under card management. Locking prevents new purchases, cash advances and balance transfers."),
        ("When will my credit card payment post?",
         "Payments submitted before the online cutoff (generally 8 PM ET) post the same business "
         "day. Payments after the cutoff or on a non-business day post the next business day."),
        ("How can I increase my credit line?",
         "Sign in, select your card, and request a credit line increase. Requests may require "
         "updated income information and can trigger a credit review."),
    ]),
    ("Payments & transfers", [
        ("How do I set up automatic payments for my credit card?",
         "Open the card in your account dashboard, choose Pay card, and set up automatic "
         "payments. You can pay the minimum due, a fixed amount, or the full statement balance from "
         "a Chase checking account."),
        ("How long do ACH transfers take?",
         "Outgoing transfers to accounts at other banks are usually delivered in 1-2 business days. "
         "Transfers between your own Chase accounts are immediate."),
        ("What is Zelle and how do I use it?",
         "Zelle lets you send and receive money with people and small businesses using just an email "
         "or U.S. mobile number. It is available in the Chase Mobile app and on chase.com."),
        ("How do I cancel a scheduled transfer?",
         "Open the Transfers page in your account, find the scheduled transfer, and choose Cancel. "
         "Transfers already in progress cannot be canceled."),
    ]),
    ("Checking & savings", [
        ("How do I avoid the monthly service fee on my checking account?",
         "Each account lists its fee-waiver rules on its product page — for example, Chase Total "
         "Checking waives the fee with a qualifying direct deposit of $500 or more, or a $1,500+ "
         "beginning daily balance."),
        ("How many ATMs does Chase have?",
         "Chase customers have access to more than 14,000 ATMs and nearly 4,700 branches nationwide."),
        ("What is the difference between available balance and current balance?",
         "Your current balance includes all posted activity. Your available balance also reflects "
         "pending holds, such as recently authorized card purchases or deposits that have not yet "
         "cleared."),
    ]),
    ("Mortgage & home lending", [
        ("How do I find today's mortgage rates?",
         "The Mortgage rates page shows example rates by loan type, refreshed each business day, "
         "along with the assumptions behind each example."),
        ("How do I request a mortgage payoff statement?",
         "Call the Home Lending customer service team at 1-800-848-9136, or send a secure message "
         "from your mortgage account."),
        ("What is a rate lock?",
         "A rate lock guarantees your interest rate for a set period, typically 30 to 60 days, while "
         "your loan is being processed so market changes do not affect your quoted rate."),
    ]),
    ("Auto loans", [
        ("How do I apply for auto financing?",
         "Apply online from the Auto page in minutes and secure your rate and financing terms for "
         "30 days. You can also shop with dealers in the Chase Preferred network."),
        ("How do I lower my monthly car payment?",
         "Options include refinancing at a lower rate, extending the term, or making a larger down "
         "payment. The Car payment calculator shows how each change affects the monthly amount."),
        ("Can I refinance a car I already own?",
         "Yes — Chase auto refinancing replaces your current loan with a new one. Customers save an "
         "average of $2,400 by refinancing with Chase."),
    ]),
    ("Alerts & security", [
        ("How do I set up account alerts?",
         "From your account dashboard choose Alerts. You can be notified by mobile push or email "
         "about large transactions, low balances, deposits received and payment due dates."),
        ("How does Chase protect me from fraud?",
         "Chase monitors accounts around the clock for unusual activity, offers card lock, and "
         "never asks for your password or one-time passcodes by phone or text."),
        ("How do I report fraud on my account?",
         "Call 1-800-935-9935 or the number on the back of your card immediately. You can also "
         "report fraud from the Security Center page on chase.com."),
    ]),
]

CD_TERMS = [
    ("6 months", 3.25, 1000), ("12 months", 3.50, 1000), ("18 months", 3.35, 1000),
    ("24 months", 3.30, 1000), ("30 months", 3.20, 1000), ("36 months", 3.15, 1000),
    ("48 months", 3.00, 1000), ("60 months", 2.95, 1000),
]


def seed_database():
    """Catalog seed — idempotent at the function level."""
    from app import (Article, AutoRate, Branch, Card, CD, DepositProduct,
                     MortgageRate, SupportArticle, db)
    if Card.query.first():
        return
    for i, c in enumerate(CARDS):
        db.session.add(Card(
            slug=c["slug"], name=c["name"], network=c["network"], audience=c["audience"],
            categories=",".join(c["categories"]), tagline=c["glance"][:300],
            offer=c["offer"], glance=c["glance"], apr=c["apr"], intro_apr=c["intro_apr"],
            fee_text=c["fee_text"], fee_value=c["fee_value"], card_art=c["card_art"],
            pt_code=c["pt_code"], earn_rewards=json.dumps(c["earn_rewards"], ensure_ascii=False),
            benefits=json.dumps(c["benefits"], ensure_ascii=False),
            stat_value=c["stat_value"], stat_label=c["stat_label"], order=i))
    order = 0
    for p in CHECKING:
        db.session.add(DepositProduct(
            slug=p["slug"], name=p["name"], product_type="checking", tagline=p["tagline"],
            monthly_fee=p["monthly_fee"], fee_text=p["fee_text"], fee_waiver=p["fee_waiver"],
            min_deposit=p["min_deposit"], features=json.dumps(p["features"], ensure_ascii=False),
            tab=p["tab"], image=p["image"], order=order))
        order += 1
    order = 0
    for p in SAVINGS:
        db.session.add(DepositProduct(
            slug=p["slug"], name=p["name"], product_type="savings", tagline=p["tagline"],
            monthly_fee=p["monthly_fee"], fee_text=p["fee_text"], fee_waiver=p["fee_waiver"],
            min_deposit=p["min_deposit"], apy_text=p["apy_text"],
            features=json.dumps(p["features"], ensure_ascii=False), tab="all",
            image=p["image"], order=order))
        order += 1
    for term, apy, minimum in CD_TERMS:
        db.session.add(CD(term=term, apy=apy, min_deposit=minimum))
    db.session.add(DepositProduct(
        slug="certificate-of-deposit", name="Chase Certificate of Deposit",
        product_type="cd",
        tagline="Get a guaranteed rate with a CD, regardless of changes in the market.",
        monthly_fee=0.0, fee_text="No monthly service fee", fee_waiver="",
        min_deposit=1000.0, apy_text="Guaranteed rate for the full term",
        features=json.dumps([
            "Choose from 6 to 60 month terms",
            "$1,000 minimum opening deposit",
            "Existing Chase checking or savings customers can open online",
            "Rates are locked for the full term",
        ]), tab="all", image="products/premier-savings-tile.jpg", order=0))
    from _seed_rates import AUTO_SNAPSHOT, MORTGAGE_SNAPSHOT
    for i, r in enumerate(MORTGAGE_SNAPSHOT["rows"]):
        db.session.add(MortgageRate(
            loan_type=r["loan_type"], rate=r["rate"], apr=r["apr"],
            monthly_payment=r["monthly_payment"], points=r["points"],
            points_cost=r["points_cost"], loan_amount=r["loan_amount"], ltv=r["ltv"], order=i))
    for i, r in enumerate(AUTO_SNAPSHOT["rows"]):
        db.session.add(AutoRate(
            product=r["product"], apr=r["apr"], term_months=r["term_months"],
            amount=r["amount"], example_payment=r["example_payment"],
            example_note=r["example_note"], order=i))
    for b in BRANCHES:
        db.session.add(Branch(
            chase_id=b["chase_id"], name=b["name"], loc_type=b["loc_type"],
            address1=b["address1"], city=b["city"], state=b["state"], zip=b["zip"],
            lat=b["lat"], lng=b["lng"], phone=b["phone"], fax=b["fax"],
            hours=json.dumps(b["hours"]) if b["hours"] else "{}",
            drive_up=json.dumps(b["drive_up"]) if b["drive_up"] else "{}",
            services=json.dumps(b["services"]), atm_24h=b["atm_24h"],
            lobby_atm=b["lobby_atm"], vestibule_atm=b["vestibule_atm"],
            search_city=b["search_city"]))
    for a in ARTICLES:
        db.session.add(Article(
            slug=a["slug"], title=a["title"], category=a["category"],
            category_slug=a["category_slug"], minutes=a["minutes"], hero=a["hero"],
            insights=json.dumps(a["insights"], ensure_ascii=False), body=a["body"],
            upstream_url=a["upstream_url"]))
    t_order = 0
    for topic, entries in SUPPORT_TOPICS:
        for q, ans in entries:
            db.session.add(SupportArticle(topic=topic, question=q, answer=ans, order=t_order))
            t_order += 1
    db.session.commit()


def seed_benchmark_users():
    """Benchmark users + their banking history — idempotent at the function level."""
    from app import (Alert, BankAccount, CardPayment, CreditCardAccount,
                     CreditScoreSnapshot, RewardRedemption, Statement, Card,
                     Transaction, Transfer, User, db)
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    rng = random.Random(RNG_SEED)

    for ui, cfg in enumerate(USERS):
        user = User(
            username=cfg["username"], email=cfg["email"], password_hash=PASSWORD_HASH,
            display_name=cfg["display_name"], first_name=cfg["first_name"],
            last_name=cfg["last_name"], phone=cfg["phone"], address1=cfg["address1"],
            city=cfg["city"], state=cfg["state"], zip=cfg["zip"], created_at=MIRROR)
        db.session.add(user)
        db.session.flush()

        banks = {}
        for acct in cfg["bank_accounts"]:
            bank = BankAccount(
                user_id=user.id, name=acct["name"], acct_type=acct["acct_type"],
                masked=acct["masked"], balance=acct["balance"],
                opened=date.fromisoformat(acct["opened"]))
            db.session.add(bank)
            banks[acct["acct_type"]] = bank
        db.session.flush()

        cards = {}
        for cc in cfg["cards"]:
            card_row = Card.query.filter_by(slug=cc["slug"]).first()
            acct = CreditCardAccount(
                user_id=user.id, card_id=card_row.id, masked=cc["masked"],
                credit_limit=cc["limit"], balance=cc["balance"], points=cc["points"],
                opened=date.fromisoformat(cc["opened"]), autopay=cc["autopay"],
                payment_due=MIRROR + timedelta(days=(6 + ui * 3)),
                statement_balance=round(cc["balance"] * 0.8, 2))
            db.session.add(acct)
            cards[cc["slug"]] = acct
        db.session.flush()

        checking = banks.get("checking")
        savings = banks.get("savings")

        # ---- transactions across the 90-day window ----
        txns = []
        card_keys = sorted(cards)
        cat_keys = sorted(MERCHANTS)
        cat_weights = [sum(w for _, _, w in MERCHANTS[c]) for c in cat_keys]
        day = WINDOW_START
        while day <= MIRROR:
            for rec in RECURRING:
                if day.day != rec["day"]:
                    continue
                if rec["account"] == "checking":
                    txns.append(dict(posted=day, merchant=rec["merchant"],
                                     category=rec["category"], amount=rec["amount"],
                                     account_type="checking", bank_id=checking.id,
                                     card_id=None))
                elif card_keys:
                    slug = card_keys[(day.toordinal() + rec["day"]) % len(card_keys)]
                    txns.append(dict(posted=day, merchant=rec["merchant"],
                                     category=rec["category"], amount=rec["amount"],
                                     account_type="card", bank_id=None,
                                     card_id=cards[slug].id))
            n_spend = rng.choices([0, 1, 2, 3], weights=[38, 34, 20, 8])[0]
            for _ in range(n_spend):
                cat = rng.choices(cat_keys, weights=cat_weights)[0]
                pool = MERCHANTS[cat]
                merchant, (lo, hi), _ = rng.choices(
                    pool, weights=[w for _, _, w in pool])[0]
                amount = round(rng.uniform(lo, hi), 2)
                if cat == "travel" and rng.random() < 0.6:
                    continue
                use_card = rng.random() < 0.62 and bool(card_keys)
                if use_card:
                    slug = rng.choice(card_keys)
                    txns.append(dict(posted=day, merchant=merchant, category=cat,
                                     amount=amount, account_type="card", bank_id=None,
                                     card_id=cards[slug].id))
                else:
                    txns.append(dict(posted=day, merchant=merchant, category=cat,
                                     amount=amount, account_type="checking",
                                     bank_id=checking.id, card_id=None))
            day += timedelta(days=1)

        # savings interest credits (monthly)
        if savings:
            m = WINDOW_START
            while m <= MIRROR:
                interest_day = m.replace(day=min(28, m.day))
                txns.append(dict(posted=interest_day, merchant="Interest Earned",
                                 category="income",
                                 amount=-round(savings.balance * 0.0008, 2),
                                 account_type="savings", bank_id=savings.id,
                                 card_id=None))
                m = m + timedelta(days=30)

        for t in txns:
            pending = (t["posted"] > MIRROR - timedelta(days=2)) and t["amount"] > 0 \
                and rng.random() < 0.5
            db.session.add(Transaction(
                user_id=user.id, account_type=t["account_type"],
                bank_account_id=t["bank_id"], card_account_id=t["card_id"],
                posted=t["posted"], description=t["merchant"], merchant=t["merchant"],
                category=t["category"], amount=t["amount"], pending=pending))
        db.session.flush()

        # ---- scheduled transfers (history + upcoming) ----
        for tr in SCHEDULED_TRANSFERS.get(cfg["username"], []):
            src = checking if tr["from"] == "checking" else savings
            if tr["to"].startswith("card:"):
                dst_card = cards[tr["to"].split(":")[1]]
                to_label = f"{dst_card.card.name} ...{dst_card.masked}"
                to_bank, to_card = None, dst_card.id
            else:
                dst = savings if tr["to"] == "savings" else checking
                to_label = f"{dst.name} ...{dst.masked}"
                to_bank, to_card = dst.id, None
            next_date = MIRROR.replace(day=min(tr["day_of_month"], 28))
            if next_date <= MIRROR:
                next_date += timedelta(days=30)
            for k in range(3):
                past = next_date - timedelta(days=30 * (k + 1))
                db.session.add(Transfer(
                    user_id=user.id, from_label=f"{src.name} ...{src.masked}",
                    to_label=to_label, from_bank_id=src.id, to_bank_id=to_bank,
                    to_card_id=to_card, amount=tr["amount"], date=past,
                    status="completed", frequency=tr["frequency"], memo=tr["memo"]))
            db.session.add(Transfer(
                user_id=user.id, from_label=f"{src.name} ...{src.masked}",
                to_label=to_label, from_bank_id=src.id, to_bank_id=to_bank,
                to_card_id=to_card, amount=tr["amount"], date=next_date,
                status="scheduled", frequency=tr["frequency"], memo=tr["memo"]))

        # ---- historical card payments ----
        for slug, acct in cards.items():
            for k in range(2):
                pay_date = MIRROR - timedelta(days=15 + k * 30)
                amount = round(acct.statement_balance * rng.uniform(0.4, 1.0), 2)
                db.session.add(CardPayment(user_id=user.id, card_account_id=acct.id,
                                           amount=amount, date=pay_date,
                                           from_label=f"{checking.name} ...{checking.masked}"))

        # ---- alerts ----
        for al in ALERTS.get(cfg["username"], []):
            db.session.add(Alert(user_id=user.id, alert_type=al["alert_type"],
                                 channel=al["channel"], threshold=al["threshold"],
                                 enabled=True))

        # ---- reward redemptions ----
        for rd in REDEMPTIONS.get(cfg["username"], []):
            db.session.add(RewardRedemption(
                user_id=user.id, card_account_id=cards[rd["card"]].id,
                points=rd["points"], value=rd["value"], redemption_type=rd["type"],
                date=date.fromisoformat(rd["date"]), desc=rd["desc"]))

        # ---- statements (six monthly periods per card) ----
        for slug, acct in cards.items():
            spend_by_period = {}
            for t in txns:
                if t.get("card_id") == acct.id and t["amount"] > 0:
                    key = (t["posted"].year, t["posted"].month)
                    spend_by_period[key] = spend_by_period.get(key, 0.0) + t["amount"]
            for k in range(6, 0, -1):
                close = MIRROR.replace(day=1) - timedelta(days=30 * (k - 1))
                close = close.replace(day=min(28, close.day))
                open_d = close - timedelta(days=29)
                key = (close.year, close.month)
                spend = round(spend_by_period.get(key, 0.0), 2)
                db.session.add(Statement(
                    card_account_id=acct.id, period_label=close.strftime("%B %Y"),
                    open_date=open_d, close_date=close,
                    payment_due=close + timedelta(days=21),
                    balance=spend, points_earned=int(spend * rng.uniform(1.0, 1.5))))

        # ---- credit score history ----
        history = CREDIT_HISTORY[cfg["username"]]
        for i, score in enumerate(history):
            db.session.add(CreditScoreSnapshot(
                user_id=user.id, score=score,
                date=MIRROR - timedelta(days=30 * (len(history) - 1 - i))))
        db.session.flush()
    db.session.commit()


def build_seed_database():
    """Regenerate instance_seed/chase.db deterministically from tracked source."""
    base = os.path.dirname(os.path.abspath(__file__))
    instance_dir = os.path.join(base, "instance")
    seed_dir = os.path.join(base, "instance_seed")
    shutil.rmtree(instance_dir, ignore_errors=True)
    os.makedirs(instance_dir, exist_ok=True)

    import app  # noqa: F401  (import-time bootstrap seeds instance/chase.db)
    from app import app as flask_app, db

    with flask_app.app_context():
        db.session.remove()
        db.engine.dispose()
    os.makedirs(seed_dir, exist_ok=True)
    seed_path = os.path.join(seed_dir, "chase.db")
    if os.path.exists(seed_path):
        os.unlink(seed_path)
    shutil.copyfile(os.path.join(instance_dir, "chase.db"), seed_path)
    return seed_path


if __name__ == "__main__":
    print(f"Seed database generated: {build_seed_database()}")
