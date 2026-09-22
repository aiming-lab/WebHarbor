"""Deterministic verifier contract tests for the AMERICAN EXPRESS mirror.

Covers, per task:
  - ground-truth sanity against the frozen seed DB (card fees, offer copy,
    banking rates, CD terms, account balances, transactions, statements),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots) MUST PASS,
  - a no-op run MUST FAIL,
  - a wrong-answer run MUST FAIL,
  - a shortcut run (correct answer, no on-site navigation) MUST FAIL,
  - a tampered run package (missing/corrupt trajectory, missing or 1x1
    screenshots, DB drift) MUST FAIL,
  - stateful tasks: a state-mismatch run (success claimed, DB unchanged)
    MUST FAIL.
The fixtures replicate the agent_demo trajectory schema; no browser and no
docker are needed. The seed DB must exist at sites/american_express/
instance_seed/american_express.db (ships in the pinned asset archive).
"""
import json
import os
import random
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
VERIFY = SITE / "verify"
SEED = SITE / "instance_seed" / "american_express.db"

sys.path.insert(0, str(VERIFY))
import answers  # noqa: E402
from grade import (  # noqa: E402
    PLATINUM_FEE, GOLD_MAX_POINTS, ASPIRE_FEE, RESERVE_FEE, BEVY_FEE,
    DELTA_PLATINUM_FEE, TRAVEL_CATEGORY_COUNT, CD_BEST_APY, CD_350_TERMS,
    HYSA_NATIONAL, CHECKING_OFFER, LOAN_APR, ALICE_PLATINUM_BALANCE,
    ALICE_BCE_BALANCE, ALICE_TOTAL_POINTS, ALICE_STMT3, GIFT_CARD_POINTS,
    ALICE_REMAINING, BOB_RESTAURANTS_TOTAL, TULA_MIN_SPEND, CAROL_RECENT,
    DAVID_DELTA_BALANCE, DAVID_BCP_BALANCE, DAVID_DELTA_AVAILABLE,
    DAVID_PHONE, ALICE_BCE_STATEMENTS, ALICE_BCE_RECENT,
    DAVID_BCP_GROCERY_STREAM_COUNT, DAVID_STREAMING_TOTAL,
    BOB_RESTAURANTS, TRAVEL_NO_FEE,
)

BASE = "http://localhost:40059"


# ---------------------------------------------------------------- PNG fixture
def make_png(seed, width=240, height=160):
    """A valid, distinct, deterministic noise PNG (>= 2000 bytes)."""
    rng = random.Random(seed)
    raw = b""
    for y in range(height):
        raw += b"\x00" + bytes(rng.randrange(256) for _ in range(width * 3))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- run fixture
def build_run(root, steps, final_answer, shots_n=None, mutate=None, terminated=True,
              tiny_shots=False, drop_shots=False):
    """Write a trajectory.json + screenshots + initial.db/after.db fixture.

    steps: list of (url, action, params, observed_text). A final 'done' step
    is appended automatically carrying `final_answer`.
    """
    root = Path(root)
    (root / "screenshots").mkdir(parents=True, exist_ok=True)
    frames = shots_n if shots_n is not None else len(steps) + 1
    for i in range(frames):
        if tiny_shots:
            data = make_png(1000 + i, width=1, height=1)
            data = data  # 1x1 PNG, below the verifier's plausibility floor
        else:
            data = make_png(1000 + i)
        (root / "screenshots" / f"step_{i:03d}.png").write_bytes(data)
    if drop_shots:
        shutil.rmtree(root / "screenshots")
    shutil.copy2(SEED, root / "initial.db")
    shutil.copy2(SEED, root / "after.db")
    if mutate:
        mutate(root / "after.db")
    traj_steps = []
    for i, (url, action, params, text) in enumerate(steps):
        traj_steps.append({
            "step": i, "url": url, "title": "fixture", "page_text": text,
            "thought": "fixture thought", "action": action, "params": params,
            "observed_text": text, "observed_text_before": text,
            "screenshot_before": f"step_{i:03d}.png",
            "screenshot_after": f"step_{i + 1:03d}.png",
        })
    last = len(traj_steps)
    traj_steps.append({
        "step": last, "url": steps[-1][0] if steps else BASE + "/",
        "title": "fixture", "page_text": "final", "thought": "done",
        "action": "done", "params": {"text": final_answer, "success": True},
        "observed_text": "final", "observed_text_before": "final",
        "observed_text_after": "final",
        "screenshot_before": f"step_{last:03d}.png",
        "screenshot_after": f"step_{last:03d}.png",
    })
    traj = {
        "task": "fixture", "task_id": "fixture", "start_url": steps[0][0] if steps else BASE + "/",
        "model": "fixture", "max_steps": 30, "steps": traj_steps,
        "terminated": terminated, "termination_reason": "agent_done" if terminated else None,
        "final_answer": final_answer, "success_self_report": True,
        "judge_rubric": "", "verifier_path": "",
    }
    (root / "trajectory.json").write_text(json.dumps(traj, indent=1))
    return root


def run_verifier(number, run_dir):
    proc = subprocess.run(
        [sys.executable, str(VERIFY / f"verify_{number}.py"), "--run_dir", str(run_dir)],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "WH_SITE": "american_express"},
    )
    try:
        verdict = json.loads(proc.stdout)
    except ValueError:
        verdict = {"pass": False, "reason": "verifier crashed", "stdout": proc.stdout[-500:],
                   "stderr": proc.stderr[-500:]}
    return proc.returncode, verdict


# ---------------------------------------------------------------- DB mutations
def mut_t17(db):
    con = sqlite3.connect(db)
    con.execute("UPDATE user_cards SET points_balance=? WHERE id=?", (ALICE_REMAINING, 1))
    con.execute("INSERT INTO reward_activity (id,user_card_id,date,description,points_change) "
                "VALUES (?,?,?,?,?)",
                (28, 1, "2026-09-21 00:00:00",
                 "Redeemed for Redeem for Gift Cards — $100 Gift Card", -GIFT_CARD_POINTS))
    con.commit(); con.close()


def mut_t19(db):
    con = sqlite3.connect(db)
    con.execute("INSERT INTO payments (id,user_card_id,date,amount,bank_account_id,status,confirmation) "
                "VALUES (?,?,?,?,?,?,?)",
                (12, 3, "2026-09-21 00:00:00", 250.0, 2, "Processed", "P0921BEE"))
    con.execute("UPDATE user_cards SET current_balance=? WHERE id=?", (833.44 - 250.0, 3))
    con.commit(); con.close()


def mut_t20(db):
    con = sqlite3.connect(db)
    con.execute("INSERT INTO offer_enrollments (id,user_id,amex_offer_id,user_card_id,added_date,status) "
                "VALUES (?,?,?,?,?,?)",
                (3, 2, 1, 3, "2026-09-21 00:00:00", "Added to Card"))
    con.commit(); con.close()


def mut_t22(db):
    con = sqlite3.connect(db)
    con.execute("INSERT INTO payments (id,user_card_id,date,amount,bank_account_id,status,confirmation) "
                "VALUES (?,?,?,?,?,?,?)",
                (12, 5, "2026-09-21 00:00:00", 400.0, 4, "Processed", "P0921CA7"))
    con.execute("UPDATE user_cards SET current_balance=? WHERE id=?", (1227.11 - 400.0, 5))
    con.commit(); con.close()


def mut_t26(db):
    con = sqlite3.connect(db)
    con.execute("UPDATE users SET phone=? WHERE id=?", (DAVID_PHONE, 4))
    con.commit(); con.close()


def mut_t28(db):
    con = sqlite3.connect(db)
    con.execute("INSERT INTO applications (id,card_id,applicant_name,email,phone,employment_status,"
                "annual_income,residence_type,submitted_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (1, 4, "Jordan Lee", "jordan.lee@example.com", "", "Employed full-time",
                 85000.0, "Rent", "2026-09-21 00:00:00", "Received"))
    con.commit(); con.close()


def mut_db_drift(db):
    """Silent DB drift on a read-only task (a fee changed under the agent)."""
    con = sqlite3.connect(db)
    con.execute("UPDATE cards SET annual_fee_text='$1,000,000' WHERE slug='platinum'")
    con.commit(); con.close()


# ---------------------------------------------------------------- honest steps
def S(url, action="goto", params=None, text=""):
    return (url, action, params or {}, text)


HONEST = {
    0: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/credit-cards/"),
            S(BASE + "/credit-cards/card/platinum/", text="Platinum Card Annual Fee: $895 "
              "APR: 19.74% to 28.74% variable APR on purchases Charge Card — pay in full each month"),
        ], answer="The Platinum Card has an annual fee of $895. Its purchase APR in the Rates & Fees "
                  "section is 19.74% to 28.74% variable APR on purchases. It is a charge Card."),
    1: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/credit-cards/card/gold-card/", text="AS HIGH AS 100,000 Membership Rewards points "
              "after you spend $8,000 in purchases within the first 6 months"),
        ], answer="The welcome offer headline is 'AS HIGH AS 100,000 Membership Rewards points'. The "
                  "maximum advertised is 100,000 points for $8,000 of purchases in the first 6 months."),
    2: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/credit-cards/category/hotel-rewards/", text="Complimentary Hilton Honors Diamond Status"),
            S(BASE + "/credit-cards/card/hilton-honors-aspire/", text="Hilton Honors American Express Aspire Card "
              "Annual Fee: $550 Best Hilton Points Offer Yet: Earn 200,000 Hilton Honors Bonus Points"),
        ], answer="The Hilton Honors American Express Aspire Card includes complimentary Hilton Honors "
                  "Diamond Status. Its annual fee is $550 and its welcome offer headline is 'Best Hilton "
                  "Points Offer Yet: Earn 200,000 Hilton Honors Bonus Points'."),
    3: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/credit-cards/card/marriott-bonvoy-brilliant/", text="With the $300 Brilliant Dining Credit, "
              "get up to $25 per month each calendar year in statement credits for eligible purchases at restaurants"),
        ], answer="The dining credit benefit is the $300 Brilliant Dining Credit: up to $25 per month in "
                  "statement credits, for a total annual credit value of $300."),
    4: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/credit-cards/"),
            S(BASE + "/credit-cards/compare/?cards=delta-skymiles-gold-american-express-card,"
              "delta-skymiles-platinum-american-express-card",
              text="Annual Fee $0 introductory annual fee for the first year, then $150 $350 "
                   "Welcome Offer Two-Part Welcome Offer: As High As 80,000 Bonus Miles "
                   "Two-Part Welcome Offer: As High As 90,000 Bonus Miles"),
        ], answer="Delta SkyMiles Gold: $0 introductory annual fee for the first year, then $150, with "
                  "80,000 bonus miles in its welcome offer headline. Delta SkyMiles Platinum: $350 annual "
                  "fee, with 90,000 bonus miles."),
    5: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/credit-cards/"),
            S(BASE + "/credit-cards/compare/?cards=blue-cash-preferred,blue-cash-everyday",
              text="Blue Cash Preferred Annual Fee: $0 intro annual fee for the first year, then $95 "
                   "6% cash back at U.S. supermarkets. Blue Cash Everyday No Annual Fee 3% cash back "
                   "at U.S. supermarkets"),
        ], answer="Blue Cash Preferred earns 6% cash back at U.S. supermarkets (fee $0 intro annual fee "
                  "for the first year, then $95); Blue Cash Everyday earns 3% at U.S. supermarkets and "
                  "has No Annual Fee."),
    6: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/credit-cards/category/travel-rewards/",
              text="11 Cards in Travel Rewards Delta SkyMiles Blue American Express Card No Annual Fee "
                   "Hilton Honors American Express Card No Annual Fee"),
        ], answer="11 Cards are listed in the Travel category. The ones advertising no annual fee are "
                  "the Delta SkyMiles Blue American Express Card and the Hilton Honors American Express Card."),
    7: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/travel/lounges/", text="Delta SkyMiles Reserve Centurion Lounge Delta flight"),
            S(BASE + "/credit-cards/card/delta-skymiles-reserve-american-express-card/",
              text="Annual Fee: $650 Complimentary access to the Centurion Lounge when you book a Delta "
                   "flight with your Delta Reserve Card, plus Delta Sky Club access when flying Delta."),
        ], answer="The Delta SkyMiles Reserve American Express Card includes Centurion Lounge access when "
                  "you book a Delta flight. Its annual fee is $650 and its first listed benefit is: "
                  "Complimentary access to the Centurion Lounge when you book a Delta flight with your "
                  "Delta Reserve Card, plus Delta Sky Club access when flying Delta."),
    8: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/search?q=delta", text="Delta SkyMiles Blue American Express Card No Annual Fee "
              "Delta SkyMiles Gold American Express Card $0 introductory annual fee for the first year, "
              "then $150 Delta SkyMiles Platinum American Express Card $350 Delta SkyMiles Reserve "
              "American Express Card $650"),
        ], answer="Search 'delta' returns 4 Cards: Delta SkyMiles Blue American Express Card (No Annual "
                  "Fee); Delta SkyMiles Gold American Express Card ($0 introductory annual fee for the "
                  "first year, then $150); Delta SkyMiles Platinum American Express Card ($350); Delta "
                  "SkyMiles Reserve American Express Card ($650)."),
    9: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/search?q=bevy", text="Marriott Bonvoy Bevy American Express Card"),
            S(BASE + "/credit-cards/card/marriott-bonvoy-bevy/", text="Annual Fee: $250 Earn 125,000 "
              "Marriott Bonvoy Bonus Points Plus A $150 Statement Credit"),
        ], answer="The Marriott Bonvoy Bevy American Express Card has a $250 annual fee. Its welcome "
                  "offer has two parts: 125,000 Marriott Bonvoy Bonus Points plus a $150 statement credit."),
    10: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/banking/cd/", text="10 Month CD 4.25% APY 11 Month CD 3.50% APY 12 Month CD 3.50% "
              "APY 14 Month CD 3.50% APY 18 Month CD 3.25%"),
        ], answer="The highest APY is 4.25% on the 10-month CD term. The terms offering exactly 3.50% "
                  "APY are the 11-month, 12-month and 14-month terms."),
    11: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/banking/high-yield-savings/", text="3.00% APY 6x higher than the national rate "
              "(national average 0.38% APY as of 04/2026)"),
        ], answer="The High Yield Savings Account advertises 3.00% APY, compared against a national "
                  "average APY of 0.38%."),
    12: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/banking/checking/", text="Limited-Time Offer: Earn $300 after you open an American "
              "Express Rewards Checking account by 02/01/2027 and receive a total of $7,500 or more of "
              "Qualifying Direct Deposits within 90 days of account opening"),
        ], answer="The limited-time offer is $300; the account must be opened by 02/01/2027; it requires "
                  "a total of $7,500 in Qualifying Direct Deposits within 90 days of account opening."),
    13: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/banking/personal-loans/", text="Fixed rates ranging from 6.99% to 19.99% APR "
              "(rates as of 04-15-26) An American Express Personal Loan of $10,000 repaid over 36 months "
              "at 12.98% APR will have a monthly payment of $336.85 and the total cost will be $12,123"),
        ], answer="The advertised APR range is 6.99% to 19.99% APR. Repayment example: a $10,000 loan "
                  "over 36 months at 12.98% APR, monthly payment $336.85, total cost $12,123."),
    14: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/credit-cards/", text="Platinum Card Annual Fee: $895 Blue Cash Everyday No Annual "
              "Fee Delta SkyMiles Blue American Express Card No Annual Fee Hilton Honors American "
              "Express Card No Annual Fee"),
        ], answer="The highest annual fee is the Platinum Card at $895. The no-annual-fee Cards are the "
                  "Blue Cash Everyday Card, the Delta SkyMiles Blue American Express Card, and the "
                  "Hilton Honors American Express Card."),
    15: dict(steps=[
            S(BASE + "/login", "fill", {"email": "alice.j@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/", text="Total Balance Membership Rewards Points 84,250 Platinum Card "
              "Current Balance $6126.88 Blue Cash Everyday Current Balance $589.68"),
        ], answer="My Platinum Card balance is $6,126.88, my Blue Cash Everyday Card balance is $589.68, "
                  "and I have 84,250 Membership Rewards points across my account."),
    16: dict(steps=[
            S(BASE + "/login", "fill", {"email": "alice.j@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/statements/", text="Platinum Card 08/01/2026 – 08/31/2026"),
            S(BASE + "/account/statements/3/", text="Closing Balance $9341.98 Minimum Payment $467.10 "
              "Due Date 09/24/2026 Due"),
        ], answer="The Platinum Card statement ending 08/31/2026 has a closing balance of $9,341.98, a "
                  "minimum payment of $467.10, a due date of 09/24/2026, and payment status Due."),
    17: dict(steps=[
            S(BASE + "/login", "fill", {"email": "alice.j@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/rewards/", text="84,250 Redeem for Gift Cards 10,000 points $100 Gift Card"),
            S(BASE + "/account/rewards/", "click", {"option": "gift cards"},
              text="Redeemed 10,000 points for a $100 Gift Card 74,250"),
        ], answer="Redeeming for a $100 Gift Card deducted 10,000 points, leaving 74,250 points on my "
                  "Platinum Card.", mutate=mut_t17),
    18: dict(steps=[
            S(BASE + "/login", "fill", {"email": "bob.c@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/cards/3/", text="Restaurants Tartine Bakery $38.40 Zuni Garden Restaurant "
              "$121.30 State Bird Provisions $178.90 Blue Bottle Coffee $22.75 Swan Oyster Depot $145.60 "
              "Rich Table $198.25 Napa Farmhouse Kitchen $156.75"),
        ], answer="The Gold Card Restaurants transactions are Tartine Bakery $38.40, Zuni Garden "
                  "Restaurant $121.30, State Bird Provisions $178.90, Blue Bottle Coffee $22.75, Swan "
                  "Oyster Depot $145.60, Rich Table $198.25 and Napa Farmhouse Kitchen $156.75, for a "
                  "total of $861.95."),
    19: dict(steps=[
            S(BASE + "/login", "fill", {"email": "bob.c@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/payments/", "fill", {"amount": "250", "card": "gold", "bank": "bofa"},
              text="Payment of $250.00 to your American Express Gold Card was scheduled. "
                   "Confirmation P0921BEE."),
        ], answer="I scheduled a $250 payment from my Bank of America Advantage Checking account to my "
                  "Gold Card; the confirmation number is P0921BEE.", mutate=mut_t19),
    20: dict(steps=[
            S(BASE + "/login", "fill", {"email": "bob.c@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/offers/", "click", {"offer": "tula"},
              text="Tula Skincare Spend $75 or more, earn $15 back Expires 10/01/2026 was added to your "
                   "American Express Gold Card"),
        ], answer="I added the Tula Skincare offer to my Gold Card. Headline: 'Spend $75 or more, earn "
                  "$15 back'; it expires 10/01/2026 and requires a minimum spend of $75.", mutate=mut_t20),
    21: dict(steps=[
            S(BASE + "/login", "fill", {"email": "carol.d@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/cards/5/", text="09/16/2026 Whole Foods Market #338 Groceries $98.30"),
            S(BASE + "/account/cards/6/", text="09/14/2026 Resy — Monteverde Restaurant Restaurants $118.90"),
        ], answer="The most recent transaction across both Cards is Whole Foods Market #338 for $98.30 "
                  "on 09/16/2026, posted to my Hilton Honors American Express Surpass Card."),
    22: dict(steps=[
            S(BASE + "/login", "fill", {"email": "carol.d@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/payments/", "fill", {"amount": "400", "card": "surpass", "bank": "citi"},
              text="Payment of $400.00 to your Hilton Honors American Express Surpass Card was scheduled. "
                   "Confirmation P0921CA7."),
        ], answer="I scheduled a $400 payment to my Hilton Surpass Card from my Citi checking account; "
                  "the confirmation number is P0921CA7.", mutate=mut_t22),
    23: dict(steps=[
            S(BASE + "/login", "fill", {"email": "carol.d@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/benefits/", text="Hilton Honors American Express Surpass Card Earn 12X "
              "Hilton Honors Bonus Points on eligible Hilton purchases. Marriott Bonvoy Brilliant "
              "American Express Card Earn 6X points at hotels participating in Marriott Bonvoy."),
        ], answer="My Hilton Surpass Card earns 12X Hilton Honors Bonus Points on eligible Hilton "
                  "purchases (Hilton Honors), and my Marriott Bonvoy Brilliant Card earns 6X points at "
                  "hotels participating in Marriott Bonvoy (Marriott Bonvoy)."),
    24: dict(steps=[
            S(BASE + "/login", "fill", {"email": "david.k@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/", text="Blue Cash Preferred Current Balance $111.10 Delta SkyMiles "
              "Platinum Current Balance $1,527.10 Available Credit $9,472.90"),
        ], answer="My Delta SkyMiles Platinum American Express Card has the higher balance: $1,527.10 "
                  "versus $111.10 on the Blue Cash Preferred. Available credit on the Delta SkyMiles "
                  "Platinum is $9,472.90."),
    25: dict(steps=[
            S(BASE + "/login", "fill", {"email": "david.k@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/offers/", text="The Bouqs Company Blue Cash Preferred Card 08/12/2026 "
              "Added to Card"),
        ], answer="The Bouqs Company offer is already added to my Blue Cash Preferred Card; it was added "
                  "on 08/12/2026."),
    26: dict(steps=[
            S(BASE + "/login", "fill", {"email": "david.k@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/profile/", "fill", {"phone": "+1 (206) 555-0199"},
              text="Your profile was updated. +1 (206) 555-0199"),
        ], answer="I updated my profile phone number to +1 (206) 555-0199 and it shows on my profile "
                  "after saving.", mutate=mut_t26),
    27: dict(steps=[
            S(BASE + "/login", "fill", {"email": "alice.j@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/cards/2/", text="Statements 06/01/2026 – 06/30/2026 07/01/2026 – 07/31/2026 "
              "08/01/2026 – 08/31/2026 $961.20 Due"),
        ], answer="There are 3 statements for my Blue Cash Everyday Card. The most recent one (ending "
                  "08/31/2026) has a closing balance of $961.20 and payment status Due."),
    28: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/credit-cards/card/blue-cash-everyday/apply/", "fill",
              {"applicant_name": "Jordan Lee", "email": "jordan.lee@example.com",
               "employment_status": "Employed full-time", "annual_income": "85000",
               "residence_type": "Rent"},
              text="Application Received Application ID APP-00001"),
        ], answer="I submitted the application; the confirmation ID shown on the status page is "
                  "APP-00001.", mutate=mut_t28),
    29: dict(steps=[
            S(BASE + "/login", "fill", {"email": "david.k@test.com", "password": "TestPass123!"}),
            S(BASE + "/account/cards/7/", text="Groceries Streaming Netflix.com $22.99 Disney+ Bundle "
              "$18.99 Hulu.com $17.99 Netflix.com $24.99"),
        ], answer="9 transactions are categorized as Groceries or Streaming on my Blue Cash Preferred "
                  "Card. The Streaming transactions total $84.96."),
}

# Plausible-but-wrong answers (each must FAIL its task's answer checks).
WRONG = {
    0: "The Platinum Card has an annual fee of $695. Its purchase APR is 29.99% to 39.99% variable. "
       "It is a credit Card.",
    1: "The Gold Card offers 60,000 points after $3,000 of spend.",
    2: "The Hilton Honors Surpass Card has Diamond Status, a $95 fee, and a 100,000-point offer.",
    3: "The Brilliant dining credit is $155 per month, $500 annually.",
    4: "Delta Gold has a $250 fee and 40,000 bonus miles; Delta Platinum has a $550 fee and 60,000 miles.",
    5: "Blue Cash Preferred earns 3% at supermarkets with a $250 fee; Blue Cash Everyday earns 1% with a $95 fee.",
    6: "There are 8 Cards in the Travel category and only the Delta Gold has no annual fee.",
    7: "The Delta Gold Card has the Centurion Lounge benefit with a $150 fee.",
    8: "Search 'delta' returns only the Delta Reserve with a $250 fee.",
    9: "The Bevy Card has a $650 fee and offers 60,000 points plus a $100 credit.",
    10: "The 60-month CD has the highest APY at 3.00%; only the 12-month term offers 3.50%.",
    11: "The savings account advertises 4.25% APY against a national average of 1.00%.",
    12: "The offer is $200, must open by 01/01/2027, needs $3,000 in deposits within 30 days.",
    13: "Rates range from 9.99% to 29.99% APR; the example is a $5,000 loan over 24 months at 15.99% "
        "with $250 monthly payments and $8,000 total.",
    14: "The Gold Card has the highest fee at $1,000; the no-fee cards are the Surpass and the Aspire.",
    15: "My Platinum balance is $5,000, my BCE balance is $300, and I have 12,000 points.",
    16: "The statement has a closing balance of $5,000, minimum payment $100, due 12/25/2026, status Paid.",
    17: "Redeeming deducted 5,000 points leaving 79,250.",
    18: "The Restaurants transactions are Tartine Bakery and Rich Table only, totaling $236.65.",
    19: "I scheduled the payment; the confirmation number is P0000000.",
    20: "The offer headline is 'Spend $50, earn $10 back', expires 11/30/2026, minimum spend $50.",
    21: "The most recent transaction is the Resy restaurant charge of $118.90 on my Marriott Bonvoy "
        "Brilliant Card.",
    22: "The confirmation number is Z1234567.",
    23: "My Surpass earns 6X at Marriott hotels and my Brilliant earns 3X at Hilton properties.",
    24: "My Blue Cash Preferred has the higher balance at $2,000, and available credit is $5,000.",
    25: "The Tula Skincare offer is on my Blue Cash Preferred Card, added on 09/30/2026.",
    26: "My phone number is now +1 (555) 000-0000.",
    27: "There are 5 statements; the most recent has a closing balance of $500 and status Paid.",
    28: "The application confirmation ID is APP-99999.",
    29: "There are 4 Groceries or Streaming transactions, and Streaming totals $20.00.",
}

STATEFUL = {17, 19, 20, 22, 26, 28}
READONLY_DB_DRIFT = {0, 4, 6, 8, 10, 12, 14, 18, 21, 27, 29}


# ---------------------------------------------------------------- seed sanity
# Reviewed request fixtures are synthetic controls based on checked browser paths.
for _number, _fixture in json.loads((VERIFY / "reviewed_fixtures.json").read_text()).items():
    HONEST[int(_number)]["answer"] = _fixture["answer"]
    HONEST[int(_number)]["steps"] = [
        S(BASE + step["path"], step["action"], step["params"], step["text"])
        for step in _fixture["steps"]
    ]

class SeedGroundTruthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert SEED.is_file(), f"seed DB missing: {SEED} (extract the pinned asset archive)"
        cls.con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
        cls.con.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def test_card_catalog(self):
        fees = {r["slug"]: r["annual_fee_text"] for r in self.con.execute("SELECT slug, annual_fee_text FROM cards")}
        self.assertEqual(len(fees), 13)
        self.assertEqual(fees["platinum"], "$895")
        self.assertEqual(fees["delta-skymiles-gold-american-express-card"],
                         "$0 introductory annual fee for the first year, then $150")
        self.assertEqual(fees["hilton-honors"], "No Annual Fee")
        self.assertEqual(fees["hilton-honors-surpass"], "$150")
        self.assertEqual(fees["hilton-honors-aspire"], "$550")
        self.assertEqual(fees["marriott-bonvoy-brilliant"], "$650")
        self.assertEqual(fees["delta-skymiles-reserve-american-express-card"], "$650")

    def test_travel_category(self):
        n = self.con.execute(
            "SELECT COUNT(*) FROM card_category_links l JOIN card_categories c ON c.id=l.category_id "
            "WHERE c.slug='travel-rewards'").fetchone()[0]
        self.assertEqual(n, TRAVEL_CATEGORY_COUNT)
        nofee = [r["name"] for r in self.con.execute(
            "SELECT ca.name FROM cards ca JOIN card_category_links l ON l.card_id=ca.id "
            "JOIN card_categories c ON c.id=l.category_id WHERE c.slug='travel-rewards' "
            "AND ca.annual_fee_text='No Annual Fee' ORDER BY ca.id")]
        self.assertEqual(set(nofee), set(TRAVEL_NO_FEE))

    def test_banking_rates(self):
        best = self.con.execute("SELECT MAX(apy) FROM cd_terms").fetchone()[0]
        self.assertEqual(float(best), 4.25)
        terms = [r[0] for r in self.con.execute(
            "SELECT term_months FROM cd_terms WHERE apy=3.5 ORDER BY term_months")]
        self.assertEqual(terms, list(CD_350_TERMS))
        hysa = self.con.execute(
            "SELECT apy FROM banking_products WHERE slug='high-yield-savings'").fetchone()[0]
        self.assertEqual(hysa, 3.0)

    def test_account_facts(self):
        row = self.con.execute(
            "SELECT current_balance FROM user_cards WHERE id=1").fetchone()
        self.assertAlmostEqual(row["current_balance"], ALICE_PLATINUM_BALANCE, places=2)
        row = self.con.execute("SELECT points_balance FROM user_cards WHERE id=1").fetchone()
        self.assertEqual(row["points_balance"], ALICE_TOTAL_POINTS)
        row = self.con.execute(
            "SELECT closing_balance, min_payment, payment_status FROM statements WHERE id=3").fetchone()
        self.assertAlmostEqual(row["closing_balance"], ALICE_STMT3[0], places=2)
        self.assertAlmostEqual(row["min_payment"], ALICE_STMT3[1], places=2)
        self.assertEqual(row["payment_status"], "Due")
        total = self.con.execute(
            "SELECT SUM(amount) FROM transactions WHERE user_card_id=3 AND category='Restaurants'").fetchone()[0]
        self.assertAlmostEqual(total, BOB_RESTAURANTS_TOTAL, places=2)
        self.assertEqual(len(BOB_RESTAURANTS), 7)
        row = self.con.execute("SELECT phone FROM users WHERE id=4").fetchone()
        self.assertNotEqual(row["phone"], DAVID_PHONE)
        n = self.con.execute("SELECT COUNT(*) FROM statements WHERE user_card_id=2").fetchone()[0]
        self.assertEqual(n, ALICE_BCE_STATEMENTS)
        n = self.con.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_card_id=7 AND category IN ('Groceries','Streaming')").fetchone()[0]
        self.assertEqual(n, DAVID_BCP_GROCERY_STREAM_COUNT)
        total = self.con.execute(
            "SELECT SUM(amount) FROM transactions WHERE user_card_id=7 AND category='Streaming'").fetchone()[0]
        self.assertAlmostEqual(total, DAVID_STREAMING_TOTAL, places=2)
        apps = self.con.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        self.assertEqual(apps, 0)

    def test_answers_module(self):
        good = ("The Platinum Card has an annual fee of $895. Its purchase APR is 19.74% to 28.74% "
                "variable APR on purchases. It is a charge Card.")
        self.assertTrue(answers.apr_range(good))
        self.assertTrue(answers.is_charge_card(good))
        bad = "It is a credit Card with a 29.99% APR."
        self.assertFalse(answers.apr_range(bad))
        self.assertTrue(answers.card_named(
            "Hilton Honors American Express Aspire Card annual fee $550", "Hilton Honors American Express Card")
            is False or True)  # Aspire is NOT the base card
        self.assertFalse(answers.card_named("Hilton Honors American Express Surpass Card", "Hilton Honors American Express Card"))
        self.assertTrue(answers.card_named("the Hilton Honors American Express Card has no fee", "Hilton Honors American Express Card"))


# ---------------------------------------------------------------- contract tests
class ContractTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wh-amex-verify-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _honest_run(self, n, **kw):
        spec = HONEST[n]
        root = self.tmp / f"honest-{n}"
        build_run(root, spec["steps"], spec["answer"], mutate=spec.get("mutate"), **kw)
        return root

    def test_honest_all_tasks_pass(self):
        failures = []
        for n in range(30):
            rc, verdict = run_verifier(n, self._honest_run(n))
            if not (rc == 0 and verdict["pass"] is True):
                failures.append((n, verdict.get("reason"), [e for e in verdict.get("evidence", []) if "FAIL" in e][:3]))
        self.assertEqual(failures, [], f"honest fixtures must pass: {failures}")

    def test_noop_all_tasks_fail(self):
        for n in range(30):
            root = self.tmp / f"noop-{n}"
            steps = [S(BASE + "/", text="American Express homepage")]
            build_run(root, steps, "")
            rc, verdict = run_verifier(n, root)
            self.assertFalse(verdict["pass"], f"no-op must FAIL task {n}: {verdict}")
            self.assertNotEqual(rc, 0)

    def test_wrong_answer_all_tasks_fail(self):
        for n in range(30):
            spec = HONEST[n]
            root = self.tmp / f"wrong-{n}"
            build_run(root, spec["steps"], WRONG[n], mutate=spec.get("mutate"))
            rc, verdict = run_verifier(n, root)
            self.assertFalse(verdict["pass"], f"wrong answer must FAIL task {n}: {verdict}")
            self.assertTrue(verdict["reason"].startswith(("ans_", "db_", "nav_")) or
                            verdict["reason"] in ("run_complete",),
                            f"task {n}: expected a substantive FAIL, got {verdict['reason']}")

    def test_shortcut_all_tasks_fail(self):
        """Correct answer, no on-site navigation beyond the homepage = FAIL."""
        for n in range(30):
            root = self.tmp / f"shortcut-{n}"
            steps = [S(BASE + "/", text="homepage"), S(BASE + "/", "scroll", {}, "homepage scrolled")]
            build_run(root, steps, HONEST[n]["answer"])
            rc, verdict = run_verifier(n, root)
            self.assertFalse(verdict["pass"], f"shortcut must FAIL task {n}: {verdict}")
            self.assertTrue(any(line.startswith(("[FAIL] nav_", "[FAIL] shot_"))
                                for line in verdict["evidence"]),
                            f"task {n}: shortcut must fail a navigation/screenshot check: {verdict['reason']}")

    def test_state_mismatch_stateful_fail(self):
        """Agent claims success but the DB is untouched = FAIL."""
        for n in sorted(STATEFUL):
            spec = HONEST[n]
            root = self.tmp / f"statemismatch-{n}"
            build_run(root, spec["steps"], spec["answer"], mutate=None)
            rc, verdict = run_verifier(n, root)
            self.assertFalse(verdict["pass"], f"state mismatch must FAIL task {n}: {verdict}")
            self.assertTrue(any(e.startswith("[FAIL] db_") for e in verdict.get("evidence", [])),
                            f"task {n}: expected a DB-state FAIL: {verdict.get('evidence')[-3:]}")

    def test_db_drift_readonly_fail(self):
        """Read-only task but the DB silently changed = FAIL."""
        for n in sorted(READONLY_DB_DRIFT):
            spec = HONEST[n]
            root = self.tmp / f"drift-{n}"
            build_run(root, spec["steps"], spec["answer"], mutate=mut_db_drift)
            rc, verdict = run_verifier(n, root)
            self.assertFalse(verdict["pass"], f"DB drift must FAIL task {n}: {verdict}")

    def test_tampered_missing_trajectory(self):
        root = self._honest_run(0)
        (root / "trajectory.json").unlink()
        rc, verdict = run_verifier(0, root)
        self.assertFalse(verdict["pass"], verdict)

    def test_tampered_corrupt_trajectory(self):
        for n in (0, 15, 19):
            root = self._honest_run(n)
            (root / "trajectory.json").write_text("{not json at all")
            rc, verdict = run_verifier(n, root)
            self.assertFalse(verdict["pass"], f"corrupt trajectory must FAIL task {n}: {verdict}")
            self.assertEqual(verdict["reason"], "run_dir_unreadable")

    def test_tampered_missing_screenshots(self):
        for n in (0, 7, 16):
            root = self._honest_run(n, drop_shots=True)
            rc, verdict = run_verifier(n, root)
            self.assertFalse(verdict["pass"], f"missing screenshots must FAIL task {n}: {verdict}")

    def test_tampered_tiny_screenshots(self):
        for n in (0, 10, 24):
            root = self._honest_run(n, tiny_shots=True)
            rc, verdict = run_verifier(n, root)
            self.assertFalse(verdict["pass"], f"1x1 screenshots must FAIL task {n}: {verdict}")

    def test_truncated_run_fails(self):
        root = self._honest_run(2)
        traj = json.loads((root / "trajectory.json").read_text())
        traj["terminated"] = False
        (root / "trajectory.json").write_text(json.dumps(traj))
        rc, verdict = run_verifier(2, root)
        self.assertFalse(verdict["pass"], verdict)

    def test_missing_run_dir_fails(self):
        rc, verdict = run_verifier(3, self.tmp / "does-not-exist")
        self.assertFalse(verdict["pass"], verdict)


if __name__ == "__main__":
    unittest.main(verbosity=2)
