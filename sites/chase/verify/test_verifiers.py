"""Deterministic verifier contract tests for the CHASE mirror.

Covers, per task:
  - ground-truth sanity against the frozen seed DB (row identities, counts,
    balances, statement fixtures, deterministic application reference),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots; stateful tasks carry the exact expected DB mutation) MUST PASS,
  - a no-op run (homepage only, empty answer) MUST FAIL for every task,
  - a homepage-only run with a fabricated correct-sounding answer MUST FAIL,
  - near-miss wrong answers MUST FAIL,
  - a shortcut run (correct answer, no on-site navigation) MUST FAIL,
  - tampered run packages (missing/corrupt trajectory, missing / 1x1 /
    reused screenshots, mutated after-DB on read-only tasks, missing or
    over-mutated state on stateful tasks, upstream origin, truncated run)
    MUST FAIL.
The fixtures replicate the agent_demo trajectory schema; no browser and no
docker are needed (DB snapshots come from the frozen seed).
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
SEED = SITE / "instance_seed" / "chase.db"

sys.path.insert(0, str(VERIFY))
import answers  # noqa: E402
from verify_lib import (  # noqa: E402
    affirm_money, affirm_hour, affirm_score, contains_count, contains_phone,
    affirms, contains_number, contains_date_iso_or_md, norm,
)

BASE = "http://localhost:46064"


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
def build_run(root, steps, final_answer, shots_n=None, mutate=None, terminated=True):
    """Write a trajectory.json + screenshots + initial.db/after.db fixture.

    steps: list of (url, action, params, observed_text). A final 'done' step
    is appended automatically carrying `final_answer`.
    """
    root = Path(root)
    (root / "screenshots").mkdir(parents=True, exist_ok=True)
    frames = shots_n if shots_n is not None else len(steps) + 2
    for i in range(frames):
        (root / "screenshots" / f"step_{i:03d}.png").write_bytes(make_png(1000 + i))
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
        "model": "fixture", "max_steps": 40, "steps": traj_steps,
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
        env={**os.environ, "WH_SITE": "chase"},
    )
    try:
        verdict = json.loads(proc.stdout)
    except ValueError:
        verdict = {"pass": False, "reason": "verifier crashed", "stdout": proc.stdout[-500:],
                   "stderr": proc.stderr[-500:]}
    return proc.returncode, verdict


# ---------------------------------------------------------------- DB helpers
def _seed_conn():
    con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def mut_t21(db):
    """The exact DB state a completed task-21 transfer produces."""
    con = sqlite3.connect(db)
    nid = (con.execute("SELECT MAX(id) FROM transfers").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO transfers (id,user_id,from_label,to_label,from_bank_id,
        to_bank_id,to_card_id,amount,date,status,frequency,memo)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (nid, 1, "Chase Total Checking ...5824", "Chase Savings ...3091", 1, 2,
                 None, 150.0, "2026-09-28", "scheduled", "one-time", "September savings"))
    con.commit()
    con.close()


def mut_t22(db):
    """The exact DB state a completed task-22 cancel produces."""
    con = sqlite3.connect(db)
    con.execute("UPDATE transfers SET status='canceled' WHERE id=8")
    con.commit()
    con.close()


def mut_t23(db):
    """The exact DB state a completed task-23 card payment produces."""
    con = sqlite3.connect(db)
    pid = (con.execute("SELECT MAX(id) FROM card_payments").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO card_payments (id,user_id,card_account_id,amount,date,
        from_label,status) VALUES (?,?,?,?,?,?,?)""",
                (pid, 4, 7, 200.0, "2026-09-22", "Chase Total Checking ...6642", "completed"))
    tid = (con.execute("SELECT MAX(id) FROM transactions").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO transactions (id,user_id,account_type,bank_account_id,
        card_account_id,posted,description,merchant,category,amount,pending)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (tid, 4, "checking", 7, None, "2026-09-22",
                 "Credit Card Payment to Disney® Premier Visa® Card ...3358",
                 "Chase Card Payment", "payment", 200.0, 0))
    con.execute("UPDATE bank_accounts SET balance=2110.94 WHERE id=7")
    con.execute("UPDATE card_accounts SET balance=327.31 WHERE id=7")
    con.commit()
    con.close()


def mut_t24(db):
    """The exact DB state a completed task-24 autopay-off produces."""
    con = sqlite3.connect(db)
    con.execute("UPDATE card_accounts SET autopay=0 WHERE id=3")
    con.commit()
    con.close()


def mut_t25(db):
    """The exact DB state a completed task-25 alert-add produces."""
    con = sqlite3.connect(db)
    nid = (con.execute("SELECT MAX(id) FROM alerts").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO alerts (id,user_id,alert_type,channel,enabled,threshold)
        VALUES (?,?,?,?,?,?)""", (nid, 3, "low_balance", "mobile", 1, 2500.0))
    con.commit()
    con.close()


def mut_t26(db):
    """The exact DB state a completed task-26 redemption produces."""
    con = sqlite3.connect(db)
    rid = (con.execute("SELECT MAX(id) FROM reward_redemptions").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO reward_redemptions (id,user_id,card_account_id,points,value,
        redemption_type,date,desc) VALUES (?,?,?,?,?,?,?,?)""",
                (rid, 3, 5, 25000, 250.0, "cash back", "2026-09-22", "Cash back redemption"))
    con.execute("UPDATE card_accounts SET points=103940 WHERE id=5")
    con.commit()
    con.close()


def mut_t27(db):
    """The exact DB state a completed task-27 card payment produces."""
    con = sqlite3.connect(db)
    pid = (con.execute("SELECT MAX(id) FROM card_payments").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO card_payments (id,user_id,card_account_id,amount,date,
        from_label,status) VALUES (?,?,?,?,?,?,?)""",
                (pid, 1, 2, 150.0, "2026-09-22", "Chase Total Checking ...5824", "completed"))
    tid = (con.execute("SELECT MAX(id) FROM transactions").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO transactions (id,user_id,account_type,bank_account_id,
        card_account_id,posted,description,merchant,category,amount,pending)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (tid, 1, "checking", 1, None, "2026-09-22",
                 "Credit Card Payment to Chase Sapphire Preferred® Credit Card ...7729",
                 "Chase Card Payment", "payment", 150.0, 0))
    con.execute("UPDATE bank_accounts SET balance=4037.53 WHERE id=1")
    con.execute("UPDATE card_accounts SET balance=1134.90 WHERE id=2")
    con.commit()
    con.close()


def mut_t28(db):
    """The exact DB state a completed task-28 cancel produces."""
    con = sqlite3.connect(db)
    con.execute("UPDATE transfers SET status='canceled' WHERE id=4")
    con.commit()
    con.close()


def mut_t29(db):
    """The exact DB state a completed task-29 application produces."""
    con = sqlite3.connect(db)
    nid = (con.execute("SELECT MAX(id) FROM applications").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO applications (id,user_id,card_slug,card_name,applicant_name,
        status,ref_number,submitted) VALUES (?,?,?,?,?,?,?,?)""",
                (nid, None, "doordash-rewards-mastercard", "DoorDash Rewards Mastercard®",
                 "Test User", "Received", "APP-DOO-696959", "2026-09-22"))
    con.commit()
    con.close()


def mut_readonly(db):
    """An unrelated write that read-only tasks must reject."""
    con = sqlite3.connect(db)
    con.execute("UPDATE users SET phone='(000) 000-0000' WHERE email=?", ("alice.j@test.com",))
    con.commit()
    con.close()


STATE_MUTATORS = {21: mut_t21, 22: mut_t22, 23: mut_t23, 24: mut_t24,
                  25: mut_t25, 26: mut_t26, 27: mut_t27, 28: mut_t28,
                  29: mut_t29}


# ---------------------------------------------------------------- honest steps
def S(url, action="navigate", params=None, text=""):
    return (url, action, params or {}, text)


CC = BASE + "/credit-cards"
HONEST = {
    0: dict(steps=[
            S(BASE + "/"),
            S(CC + "/card/sapphire-reserve", text="Chase Sapphire Reserve® Credit Card $795 annual fee "
              "19.49%–27.99% variable APR"),
        ], answer="The Chase Sapphire Reserve® card's annual fee is $795, and the purchase APR range "
                  "shown on its detail page is 19.49%–27.99% variable APR."),
    1: dict(steps=[
            S(BASE + "/"),
            S(CC + "/category/travel", text="17 cards shown in Travel UnitedSM Explorer Card $0 "
              "United GatewaySM Card $0 Marriott Bonvoy Bold® Credit Card $0 IHG One Rewards "
              "Traveler Credit Card $0"),
        ], answer="The travel credit cards category lists 17 personal travel cards (none of them are "
                  "business cards). The ones with no annual fee ($0 annual fee) are: UnitedSM Explorer "
                  "Card, United GatewaySM Card, Marriott Bonvoy Bold® Credit Card, IHG One Rewards "
                  "Traveler Credit Card."),
    2: dict(steps=[
            S(BASE + "/"),
            S(CC + "/compare?cards=freedom-flex,freedom-unlimited",
              text="Chase Freedom Flex® Credit Card 5% cash back on up to $1,500 in bonus categories "
                   "each quarter you activate; Chase Freedom Unlimited® Credit Card unlimited 1.5% "
                   "cash back on all purchases"),
        ], answer="Two ways the earning structures differ, per the comparison page: (1) the Chase Freedom "
                  "Flex® earns 5% cash back on up to $1,500 in quarterly bonus categories you activate, "
                  "while the Freedom Unlimited® has no quarterly bonus categories; and (2) the Freedom "
                  "Unlimited® earns unlimited 1.5% cash back on all other purchases, while the Freedom "
                  "Flex® earns only 1% on all other purchases."),
    3: dict(steps=[
            S(BASE + "/"),
            S(CC + "/card/ink-business-cash", text="Earn 5% cash back on the first $25,000 spent in "
              "combined purchases at office supply stores and on internet, cable and phone services "
              "each account anniversary year"),
        ], answer="The Ink Business Cash® Credit Card earns 5% cash back on the first $25,000 spent in "
                  "combined purchases at office supply stores and on internet, cable and phone services "
                  "each account anniversary year — so the 5% categories are office supply stores plus "
                  "internet, cable and phone services, and the anniversary-year spending cap that "
                  "applies to them is $25,000 (combined) per account anniversary year."),
    4: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/checking"),
            S(BASE + "/checking/total-checking", text="$15 or $0 Monthly Service Fee qualifying direct "
              "deposit of $500 or more"),
        ], answer="The Chase Total Checking® account has a $15 or $0 Monthly Service Fee. One qualifying "
                  "way to avoid the fee: have a qualifying direct deposit of $500 or more each statement "
                  "period."),
    5: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/checking?tab=students", text="Chase First Banking℠ kids 6–17 Chase High School "
              "Checking℠ teens 13 to 17 Chase College Checking℠ students 17–24"),
        ], answer="Under the Students & Kids tab the checking page lists: Chase First Banking℠ — designed "
                  "for kids, available for kids 6–17 years old; Chase High School Checking℠ — parent "
                  "co-owned for teens ages 13 to 17; and Chase College Checking℠ — for students 17–24 "
                  "enrolled in school."),
    6: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/savings"),
            S(BASE + "/savings/chase-savings", text="$5 or $0 Monthly Service Fee $300+ balance at the "
              "beginning of each day"),
        ], answer="Chase Savings℠ has a $5 or $0 Monthly Service Fee. One condition that waives it: keep "
                  "a $300+ balance at the beginning of each day (the page also lists $25+ Autosave, a "
                  "linked qualifying checking account, or an owner under 25)."),
    7: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/cds", text="12 months 3.50% $1,000"),
        ], answer="The CD term with the highest APY is the 12-month CD at 3.50% APY, with a $1,000 "
                  "minimum opening deposit."),
    8: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/mortgage/rates", text="30 year fixed 6.750% 6.946% $2,270 60629 Chicago, IL"),
        ], answer="For the 30 year fixed example loan: interest rate 6.750%, APR 6.946%, monthly payment "
                  "$2,270. The rate examples are based on a home in ZIP code 60629 (Chicago, IL)."),
    9: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/mortgage/calculator"),
            S(BASE + "/mortgage/calculator", action="fill",
              params={"loan_amount": "300000", "term_years": "30", "rate": "6.75"},
              text="Your estimated payment $1,945.79 monthly payment $400,485.94 total interest"),
        ], answer="The mortgage calculator shows a monthly payment of $1,945.79 and total interest of "
                  "$400,485.94 for a $300,000 loan at 6.75% over 30 years."),
    10: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/auto/rates", text="Refinancing 6.59% APR 48 months $712.69 $30,000"),
        ], answer="The advertised refinancing rate is 6.59% APR for a 48-month term; in the example "
                  "refinancing scenario (a $30,000 refinance of a 2022 car) the monthly payment is "
                  "$712.69."),
    11: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/auto/calculator"),
            S(BASE + "/auto/calculator", action="fill",
              params={"vehicle_price": "28000", "down_payment": "3000", "term_months": "60", "apr": "6.09"},
              text="Your estimated payment $484.37 monthly payment $29,062.02 total"),
        ], answer="The car payment calculator shows a monthly payment of $484.37 and a total amount "
                  "paid of $29,062.02 for a $28,000 vehicle with a $3,000 down payment over 60 months "
                  "at 6.09% APR."),
    12: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/locator?q=Seattle", text="24 locations match 'Seattle' Ballard"),
            S(BASE + "/locator/branch/300", text="Ballard 5511 22nd Ave NW Seattle, WA 98107 "
              "Phone: +1 (206) 461-2375"),
        ], answer="The locator lists 24 locations matching Seattle. The Ballard branch is at 5511 22nd "
                  "Ave NW, Seattle, WA 98107, phone +1 (206) 461-2375."),
    13: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/locator?q=Chicago", text="Madison and Halsted"),
            S(BASE + "/locator/branch/49", text="Madison and Halsted 739 W Madison St Chicago, IL 60661 "
              "Thursday 09:00 – 17:00"),
        ], answer="The Madison and Halsted branch is at 739 W Madison St, Chicago, IL 60661, phone "
                  "+1 (312) 736-3903. Its lobby hours on Thursday are 9:00 AM – 5:00 PM (09:00–17:00)."),
    14: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/education"),
            S(BASE + "/education/article/what-happens-when-you-pay-off-debt",
              text="Lower credit utilization: Your credit utilization is the amount of revolving credit "
                   "you're using compared to your total credit limit"),
        ], answer="Per the article 'What happens when you pay off debt?', one specific effect it "
                  "describes: paying off a credit card balance can lower your credit utilization, and "
                  "since utilization is a major factor in most scoring models, that may improve your "
                  "credit profile."),
    15: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/education?category=credit-scores"),
            S(BASE + "/education/article/747-credit-score",
              text="a 747 credit score is considered prime or very good by VantageScore and FICO scoring "
                   "models, respectively; payment history is the biggest factor"),
        ], answer="According to the 747 credit score guide, a 747 score falls into the 'Very good' band "
                  "for FICO (Very good: 740 to 799) and the 'Prime' band for VantageScore (Prime: 661 to "
                  "780). One factor the article says influences credit scores: your payment history — "
                  "the biggest factor in your score, including your history of paying bills on time and "
                  "in full."),
    16: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/customer-service", text="Personal banking 1-800-935-9935 Home lending "
              "1-800-848-9136"),
        ], answer="Personal banking questions: call 1-800-935-9935 (Chase Customer Service). Home "
                  "lending (mortgage) questions: call 1-800-848-9136."),
    17: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "alice.j@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account", text="Welcome back, Alice Chase Total Checking ...5824 $4,187.53 "
              "Chase Savings ...3091 $12,650.00"),
        ], answer="On Alice's accounts dashboard: her Chase Total Checking account (...5824) has an "
                  "available balance of $4,187.53, and her Chase Savings account (...3091) has "
                  "$12,650.00."),
    18: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "alice.j@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account/transactions?category=dining",
              text="Money out: $356.61 Shake Shack 32.45 2026-09-18"),
        ], answer="Filtered to the dining category, Alice's transactions page shows $356.61 of dining "
                  "spending (Money out: $356.61). The merchant with the single largest dining charge is "
                  "Shake Shack, with a $32.45 charge on 2026-09-18."),
    19: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "bob.c@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account/statements", text="Ink Business Cash® Credit Card ...9912 September 2026 "
              "$1,324.30 1,823"),
        ], answer="The most recent statement for the Ink Business Cash® Credit Card (...9912) is "
                  "September 2026 (closed Sep 01, 2026): period balance $1,324.30 and points earned "
                  "1,823."),
    20: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "carol.d@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account/credit-journey", text="781 Very Good +3 points since last month"),
        ], answer="Carol's current credit score on Credit Journey is 781, which falls into the Very Good "
                  "band, and it is up 3 points since the previous month (from 778)."),
    21: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "alice.j@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account/transfer", action="fill",
              params={"from_account": "bank:1", "to_account": "bank:2", "amount": "150",
                      "when": "2026-09-28", "frequency": "one-time", "memo": "September savings"},
              text="Transfer money"),
            S(BASE + "/account/transfers", text="September savings scheduled $150.00"),
        ], answer="The one-time transfer of $150.00 from Chase Total Checking ...5824 to Chase Savings "
                  "...3091, dated 2026-09-28 with memo 'September savings', is now confirmed on the "
                  "transfers page as a scheduled transfer.", mutate=mut_t21),
    22: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "alice.j@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account/transfers", action="click",
              params={"button": "Cancel"}, text="Freedom Unlimited automatic payment Scheduled $120.00"),
            S(BASE + "/account/transfers", text="canceled"),
        ], answer="Her scheduled monthly automatic transfer of $120.00 from Chase Total Checking ...5824 "
                  "to the Chase Freedom Unlimited® Credit Card ...4081 has been canceled — the transfers "
                  "page now shows it as canceled.", mutate=mut_t22),
    23: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "david.k@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account/pay/7", action="fill",
              params={"from_bank": "7", "amount": "200"}, text="Pay card"),
            S(BASE + "/account", text="Disney® Premier Visa® Card $327.31"),
        ], answer="The $200.00 payment from his Chase Total Checking ...6642 was sent to his Disney® "
                  "Premier Visa® Card ...3358. On the accounts dashboard the card balance is now "
                  "$327.31 (reduced from $527.31), and the checking balance is now $2,110.94.",
        mutate=mut_t23),
    24: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "bob.c@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account/autopay", action="click",
              params={"button": "Turn off automatic payments"},
              text="Chase Freedom Flex® Credit Card ...2266 Turn off automatic payments"),
            S(BASE + "/account/autopay", text="Autopay off"),
        ], answer="Automatic payments for the Chase Freedom Flex® Credit Card ...2266 are now turned "
                  "off — the automatic payments page shows the card with an 'Autopay off' badge.",
        mutate=mut_t24),
    25: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "carol.d@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account/alerts", action="fill",
              params={"alert_type": "low_balance", "channel": "mobile", "threshold": "2500"},
              text="Add an alert"),
            S(BASE + "/account/alerts", text="Low balance alert mobile push $2,500.00"),
        ], answer="The new alert now appears in her alerts list: 'Low balance alert' — mobile push "
                  "delivery, threshold $2,500.00 (or below), status active.", mutate=mut_t25),
    26: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "carol.d@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account/rewards", action="fill",
              params={"points": "25000", "redemption_type": "cash back"},
              text="Chase Sapphire Reserve® 128,940 points"),
            S(BASE + "/account/rewards", text="Redeemed 25,000 points for $250.00 in cash back"),
        ], answer="Redeeming 25,000 points from her Chase Sapphire Reserve® card ...5583 for cash back "
                  "shows a redemption value of $250.00 (25,000 points at $0.01 per point); the rewards "
                  "page confirms 'Redeemed 25,000 points for $250.00 in cash back'.", mutate=mut_t26),
    27: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "alice.j@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account", text="Freedom Unlimited $412.66 Sapphire Preferred $1,284.90"),
            S(BASE + "/account/pay/2", action="fill",
              params={"from_bank": "1", "amount": "150"}, text="Pay card"),
            S(BASE + "/account", text="Sapphire Preferred $1,134.90"),
        ], answer="The card with the higher current balance is the Chase Sapphire Preferred® Credit "
                  "Card ...7729 ($1,284.90 vs $412.66 on the Freedom Unlimited® ...4081). The "
                  "$150.00 payment from her Chase Total Checking ...5824 was sent, and the accounts "
                  "dashboard now shows the Sapphire Preferred® balance as $1,134.90.",
        mutate=mut_t27),
    28: dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "alice.j@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account/transfers", action="click",
              params={"button": "Cancel"},
              text="Autosave to savings Scheduled $250.00 2026-09-25 Chase Savings ...3091"),
            S(BASE + "/account/transfers", text="canceled"),
        ], answer="Her scheduled monthly transfer of $250.00 from Chase Total Checking ...5824 to "
                  "Chase Savings ...3091 (Autosave to savings, scheduled for Sep 25, 2026) was "
                  "canceled and now shows as Canceled on the transfers page.", mutate=mut_t28),
    29: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/credit-cards"),
            S(BASE + "/credit-cards/card/doordash-rewards-mastercard",
              text="DoorDash Rewards Mastercard® 4% cash back on DoorDash and Caviar orders"),
            S(BASE + "/credit-cards/card/doordash-rewards-mastercard/apply", action="fill",
              params={"first_name": "Test", "last_name": "User", "email": "test.user@example.com",
                      "phone": "(555) 123-4567", "income": "85000"}, text="Apply"),
            S(BASE + "/credit-cards/card/doordash-rewards-mastercard/apply",
              text="application reference number APP-DOO-696959"),
        ], answer="The card that earns cash back on DoorDash and Caviar orders is the DoorDash Rewards "
                  "Mastercard® (it earns 4% cash back on DoorDash and Caviar orders). The application "
                  "with name Test User, email test.user@example.com, phone (555) 123-4567 and income "
                  "85000 was submitted, and the confirmation page shows application reference number "
                  "APP-DOO-696959.", mutate=mut_t29),
}

# near-miss wrong answers: one key value altered per task
WRONG_ANSWERS = {
    0: "The Chase Sapphire Reserve® card's annual fee is $550, and the purchase APR range is 15.99%–22.99% variable APR.",
    1: "The travel credit cards category lists 15 personal travel cards. The ones with no annual fee are UnitedSM Explorer Card and United GatewaySM Card.",
    2: "The Freedom Flex earns 3% cash back quarterly and the Freedom Unlimited earns 2% on all purchases.",
    3: "The Ink Business Cash® earns 5% cash back at gas stations and restaurants, capped at $50,000 each year.",
    4: "The Chase Total Checking® monthly service fee is $12, avoided with a $100 direct deposit.",
    5: "Chase First Banking℠ is for kids 3–10, Chase High School Checking℠ for teens 16–19, and Chase College Checking℠ for students 20–25.",
    6: "Chase Savings℠ has a $25 monthly service fee, waived with a $3,000 daily balance.",
    7: "The CD term with the highest APY is the 24-month CD at 4.50% APY with a $5,000 minimum deposit.",
    8: "The 30 year fixed example shows a 5.75% interest rate, 5.946% APR and a $1,270 monthly payment based on ZIP 60601.",
    9: "The mortgage calculator shows a monthly payment of $2,194.57 and total interest of $350,000.00.",
    10: "The refinancing rate is 5.99% APR for 72 months with an example monthly payment of $499.00.",
    11: "The car payment calculator shows a monthly payment of $384.13 and a total of $21,000.00.",
    12: "The locator lists 19 locations matching Seattle. The Ballard branch is at 5211 24th Ave NE, Seattle, WA 98125, phone +1 (206) 555-0123.",
    13: "The Madison and Halsted branch is at 839 W Madison St, and its Thursday lobby hours are 10:00 AM to 4:00 PM.",
    14: "The article says paying off debt instantly raises your credit score by 100 points.",
    15: "A 747 score falls into the Exceptional band, and the article says your astrological sign influences credit scores.",
    16: "Call 1-800-555-1234 for personal banking and 1-800-555-5678 for home lending.",
    17: "Alice's Chase Total Checking shows $3,187.53 and her Chase Savings shows $11,650.00.",
    18: "Alice spent $256.61 on dining, and the largest dining charge was Chipotle for $29.99.",
    19: "The most recent Ink Business Cash statement shows a period balance of $999.99 and 500 points earned.",
    20: "Carol's credit score is 751, in the Good band, up 12 points since last month.",
    21: "The $99 transfer to savings dated 2026-10-15 with memo 'October savings' is confirmed as scheduled.",
    22: "Her scheduled automatic transfer was canceled and now shows as canceled on the transfers page.",
    23: "The card balance after the $200 payment is now $227.31 on the accounts dashboard.",
    24: "Automatic payments for the Chase Ink Business Cash® card ...9912 are now turned off — the page shows 'Autopay off'.",
    25: "The new large transaction alert with a $500 threshold delivered by email appears in the alerts list.",
    26: "Redeeming 25,000 points for cash back shows a redemption value of $312.50.",
    27: "I paid $150 from her checking account to the Chase Freedom Unlimited® card ...4081; its balance is now $262.66 on the dashboard.",
    28: "Her scheduled automatic payment of $120.00 to the Freedom Unlimited card, dated 2026-10-10, was canceled.",
    29: "The application reference number shown on the confirmation page is APP-DOO-111111.",
}


def _tmp():
    return Path(tempfile.mkdtemp(prefix="wh-chase-test-"))


# ---------------------------------------------------------------- test cases
class VerifierSuite(unittest.TestCase):

    # -- honest fixtures must pass for every task -------------------------
    def test_honest_fixtures_all_pass(self):
        for n in sorted(HONEST):
            with self.subTest(task=n):
                run = build_run(_tmp(), HONEST[n]["steps"], HONEST[n]["answer"],
                                mutate=HONEST[n].get("mutate"))
                rc, v = run_verifier(n, run)
                self.assertTrue(v.get("pass"), f"task {n}: {v.get('reason')} {v.get('evidence')}")

    # -- no-op runs must fail for every task -------------------------------
    def test_noop_empty_answer_fails_all(self):
        for n in sorted(HONEST):
            with self.subTest(task=n):
                run = build_run(_tmp(), [S(BASE + "/")], "")
                rc, v = run_verifier(n, run)
                self.assertFalse(v.get("pass"), f"task {n} no-op unexpectedly passed")

    def test_homepage_only_with_fabricated_answer_fails_all(self):
        for n in sorted(HONEST):
            with self.subTest(task=n):
                run = build_run(_tmp(), [S(BASE + "/")], HONEST[n]["answer"],
                                mutate=HONEST[n].get("mutate"))
                rc, v = run_verifier(n, run)
                self.assertFalse(v.get("pass"), f"task {n} shortcut unexpectedly passed")

    def test_wrong_answers_fail(self):
        for n in sorted(WRONG_ANSWERS):
            with self.subTest(task=n):
                run = build_run(_tmp(), HONEST[n]["steps"], WRONG_ANSWERS[n],
                                mutate=HONEST[n].get("mutate"))
                rc, v = run_verifier(n, run)
                self.assertFalse(v.get("pass"), f"task {n} wrong answer unexpectedly passed")

    def test_correct_answer_wrong_pages_fail(self):
        for n in sorted(HONEST):
            with self.subTest(task=n):
                # correct answer + correct mutation (if any) but only the
                # homepage was opened: navigation anchor must fail it
                run = build_run(_tmp(), [S(BASE + "/")], HONEST[n]["answer"],
                                mutate=HONEST[n].get("mutate"))
                rc, v = run_verifier(n, run)
                self.assertFalse(v.get("pass"), f"task {n} wrong-page run unexpectedly passed")

    def test_compare_url_encoded_comma_passes(self):
        # regression (chase audit): the real UI's Compare button builds the
        # comparison URL with encodeURIComponent, so the browser records
        # cards=freedom-flex%2Cfreedom-unlimited. navigated_query's contract
        # ("exact match after unquoting") must accept that form, and still
        # reject a wrong card pair.
        steps = [S(BASE + "/"),
                 S(CC + "/compare?cards=freedom-flex%2Cfreedom-unlimited",
                   text=HONEST[2]["steps"][1][3])]
        run = build_run(_tmp(), steps, HONEST[2]["answer"])
        rc, v = run_verifier(2, run)
        self.assertTrue(v.get("pass"), f"encoded-comma compare failed: {v.get('reason')}")
        wrong = [S(BASE + "/"),
                S(CC + "/compare?cards=freedom-flex%2Csapphire-reserve",
                  text=HONEST[2]["steps"][1][3])]
        run = build_run(_tmp(), wrong, HONEST[2]["answer"])
        rc, v = run_verifier(2, run)
        self.assertFalse(v.get("pass"), "wrong encoded card pair unexpectedly passed")

    def test_missing_trajectory_fails(self):
        run = build_run(_tmp(), HONEST[0]["steps"], HONEST[0]["answer"])
        os.unlink(run / "trajectory.json")
        rc, v = run_verifier(0, run)
        self.assertFalse(v.get("pass"))

    def test_corrupt_trajectory_fails(self):
        run = build_run(_tmp(), HONEST[0]["steps"], HONEST[0]["answer"])
        (run / "trajectory.json").write_text("{not json")
        rc, v = run_verifier(0, run)
        self.assertFalse(v.get("pass"))

    def test_missing_screenshots_fail(self):
        run = build_run(_tmp(), HONEST[0]["steps"], HONEST[0]["answer"])
        for p in (run / "screenshots").glob("*.png"):
            os.unlink(p)
        rc, v = run_verifier(0, run)
        self.assertFalse(v.get("pass"))

    def test_tiny_screenshots_fail(self):
        run = build_run(_tmp(), HONEST[0]["steps"], HONEST[0]["answer"])
        tiny = make_png(1, 8, 8)
        for p in (run / "screenshots").glob("*.png"):
            p.write_bytes(tiny)
        rc, v = run_verifier(0, run)
        self.assertFalse(v.get("pass"))

    def test_identical_frames_fail(self):
        run = build_run(_tmp(), HONEST[2]["steps"], HONEST[2]["answer"])
        same = make_png(7, 240, 160)
        for p in (run / "screenshots").glob("*.png"):
            p.write_bytes(same)
        rc, v = run_verifier(2, run)
        self.assertFalse(v.get("pass"))

    def test_readonly_db_tamper_fails(self):
        for n in sorted(set(HONEST) - set(STATE_MUTATORS)):
            with self.subTest(task=n):
                run = build_run(_tmp(), HONEST[n]["steps"], HONEST[n]["answer"],
                                mutate=mut_readonly)
                rc, v = run_verifier(n, run)
                self.assertFalse(v.get("pass"), f"task {n} DB tamper unexpectedly passed")

    def test_stateful_missing_mutation_fails(self):
        for n, mut in sorted(STATE_MUTATORS.items()):
            with self.subTest(task=n):
                # correct pages + correct answer, but the DB never changed
                run = build_run(_tmp(), HONEST[n]["steps"], HONEST[n]["answer"])
                rc, v = run_verifier(n, run)
                self.assertFalse(v.get("pass"), f"task {n} missing mutation unexpectedly passed")

    def test_stateful_extra_mutation_fails(self):
        for n, mut in sorted(STATE_MUTATORS.items()):
            with self.subTest(task=n):
                def both(db):
                    mut(db)
                    mut_readonly(db)
                run = build_run(_tmp(), HONEST[n]["steps"], HONEST[n]["answer"], mutate=both)
                rc, v = run_verifier(n, run)
                self.assertFalse(v.get("pass"), f"task {n} extra mutation unexpectedly passed")

    def test_upstream_origin_fails(self):
        run = build_run(_tmp(), [S("https://www.chase.com/credit-cards/card/sapphire-reserve",
                                   text="Chase Sapphire Reserve $795")], HONEST[0]["answer"])
        rc, v = run_verifier(0, run)
        self.assertFalse(v.get("pass"))
        self.assertEqual(v.get("reason"), "nav_origin_local")

    def test_truncated_run_fails(self):
        run = build_run(_tmp(), HONEST[0]["steps"], "", terminated=False)
        rc, v = run_verifier(0, run)
        self.assertFalse(v.get("pass"))

    def test_t23_wrong_card_payment_fails(self):
        """A payment that hits the wrong card/amount must fail even with the
        right-looking answer."""
        def wrong(db):
            con = sqlite3.connect(db)
            pid = (con.execute("SELECT MAX(id) FROM card_payments").fetchone()[0] or 0) + 1
            con.execute("""INSERT INTO card_payments (id,user_id,card_account_id,amount,date,
                from_label,status) VALUES (?,?,?,?,?,?,?)""",
                        (pid, 4, 8, 200.0, "2026-09-22", "Chase Total Checking ...6642", "completed"))
            con.execute("UPDATE bank_accounts SET balance=2110.94 WHERE id=7")
            con.execute("UPDATE card_accounts SET balance=0 WHERE id=8")
            con.commit()
            con.close()
        run = build_run(_tmp(), HONEST[23]["steps"], HONEST[23]["answer"], mutate=wrong)
        rc, v = run_verifier(23, run)
        self.assertFalse(v.get("pass"))

    def test_t29_wrong_card_application_fails(self):
        """An application for the wrong card (or wrong applicant) must fail."""
        def wrong(db):
            con = sqlite3.connect(db)
            nid = (con.execute("SELECT MAX(id) FROM applications").fetchone()[0] or 0) + 1
            con.execute("""INSERT INTO applications (id,user_id,card_slug,card_name,applicant_name,
                status,ref_number,submitted) VALUES (?,?,?,?,?,?,?,?)""",
                        (nid, None, "freedom-flex", "Chase Freedom Flex® Credit Card",
                         "Test User", "Received", "APP-FRE-829152", "2026-09-22"))
            con.commit()
            con.close()
        run = build_run(_tmp(), HONEST[29]["steps"], HONEST[29]["answer"], mutate=wrong)
        rc, v = run_verifier(29, run)
        self.assertFalse(v.get("pass"))

    def test_t27_t28_clarification_only_fails(self):
        """The rejected ask-which-one genre must fail: right pages, but the
        answer is only a clarifying question and no state change happened."""
        clar27 = dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "alice.j@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account", text="Freedom Unlimited $412.66 Sapphire Preferred $1,284.90"),
        ], answer="Alice has two credit cards with different balances: the Chase Freedom "
                  "Unlimited® ...4081 ($412.66) and the Chase Sapphire Preferred® ...7729 "
                  "($1,284.90). Which card would you like to pay down, and how much would "
                  "you like to pay?")
        clar28 = dict(steps=[
            S(BASE + "/logon", action="fill",
              params={"email": "alice.j@test.com", "password": "TestPass123!"}, text="Sign in"),
            S(BASE + "/account/transfers", text="Autosave to savings Scheduled $250.00; "
              "Freedom Unlimited automatic payment Scheduled $120.00"),
        ], answer="Alice has two upcoming scheduled transfers: a $250.00 monthly autosave to "
                  "Chase Savings ...3091 and a $120.00 automatic payment to the Freedom "
                  "Unlimited card ...4081. Which one would you like to cancel?")
        for n, spec in ((27, clar27), (28, clar28)):
            with self.subTest(task=n):
                run = build_run(_tmp(), spec["steps"], spec["answer"])
                rc, v = run_verifier(n, run)
                self.assertFalse(v.get("pass"),
                                 f"task {n} clarification-only run unexpectedly passed")

    def test_t27_wrong_card_payment_fails(self):
        """A $150 payment that hits the lower-balance card must fail even with
        a matching-looking answer (wrong card named, wrong new balance)."""
        def wrong_card(db):
            con = sqlite3.connect(db)
            pid = (con.execute("SELECT MAX(id) FROM card_payments").fetchone()[0] or 0) + 1
            con.execute("""INSERT INTO card_payments (id,user_id,card_account_id,amount,date,
                from_label,status) VALUES (?,?,?,?,?,?,?)""",
                        (pid, 1, 1, 150.0, "2026-09-22", "Chase Total Checking ...5824", "completed"))
            con.execute("UPDATE bank_accounts SET balance=4037.53 WHERE id=1")
            con.execute("UPDATE card_accounts SET balance=262.66 WHERE id=1")
            con.commit()
            con.close()
        run = build_run(_tmp(), HONEST[27]["steps"],
                        "The $150 payment went to the Chase Freedom Unlimited® card ...4081; "
                        "its balance is now $262.66 on the accounts dashboard.",
                        mutate=wrong_card)
        rc, v = run_verifier(27, run)
        self.assertFalse(v.get("pass"))

    def test_t27_wrong_amount_payment_fails(self):
        """A payment of the wrong amount to the right card must fail."""
        def wrong_amount(db):
            con = sqlite3.connect(db)
            pid = (con.execute("SELECT MAX(id) FROM card_payments").fetchone()[0] or 0) + 1
            con.execute("""INSERT INTO card_payments (id,user_id,card_account_id,amount,date,
                from_label,status) VALUES (?,?,?,?,?,?,?)""",
                        (pid, 1, 2, 100.0, "2026-09-22", "Chase Total Checking ...5824", "completed"))
            con.execute("UPDATE bank_accounts SET balance=4087.53 WHERE id=1")
            con.execute("UPDATE card_accounts SET balance=1184.90 WHERE id=2")
            con.commit()
            con.close()
        run = build_run(_tmp(), HONEST[27]["steps"],
                        "I paid $100 from her Chase Total Checking account to the Chase Sapphire "
                        "Preferred® card ...7729; its balance is now $1,184.90 on the dashboard.",
                        mutate=wrong_amount)
        rc, v = run_verifier(27, run)
        self.assertFalse(v.get("pass"))

    def test_t28_wrong_transfer_canceled_fails(self):
        """Canceling the other scheduled transfer (the card payment) must
        fail, and so must canceling both (over-mutation)."""
        def wrong_transfer(db):
            con = sqlite3.connect(db)
            con.execute("UPDATE transfers SET status='canceled' WHERE id=8")
            con.commit()
            con.close()
        run = build_run(_tmp(), HONEST[28]["steps"],
                        "Her scheduled automatic payment of $120.00 to the Freedom Unlimited "
                        "card dated 2026-10-10 was canceled.", mutate=wrong_transfer)
        rc, v = run_verifier(28, run)
        self.assertFalse(v.get("pass"))

        def both_transfers(db):
            con = sqlite3.connect(db)
            con.execute("UPDATE transfers SET status='canceled' WHERE id IN (4, 8)")
            con.commit()
            con.close()
        run = build_run(_tmp(), HONEST[28]["steps"], HONEST[28]["answer"], mutate=both_transfers)
        rc, v = run_verifier(28, run)
        self.assertFalse(v.get("pass"))


class GroundTruthSanity(unittest.TestCase):
    """answers.py must match the frozen seed DB exactly."""

    def test_catalog_counts(self):
        con = _seed_conn()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM cards").fetchone()[0], 42)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM branches").fetchone()[0], 600)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM articles").fetchone()[0], 24)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM deposit_products").fetchone()[0], 12)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM users").fetchone()[0], 4)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 462)
        con.close()

    def test_travel_category_truth(self):
        con = _seed_conn()
        travel = [r["slug"] for r in con.execute(
            "SELECT slug FROM cards WHERE categories LIKE '%travel%'")]
        self.assertEqual(len(travel), answers.T1_COUNT)
        self.assertTrue(all("business" not in r["categories"] for r in con.execute(
            "SELECT categories FROM cards WHERE categories LIKE '%travel%'")))
        free = [r["slug"] for r in con.execute(
            "SELECT slug FROM cards WHERE categories LIKE '%travel%' AND fee_value=0")]
        self.assertEqual(sorted(free), sorted(["united-explorer", "united-gateway",
                                               "marriott-bonvoy-bold", "ihg-one-traveler"]))
        con.close()

    def test_bank_and_card_row_ids(self):
        con = _seed_conn()
        for i, (masked, email) in enumerate([("5824", "alice.j@test.com"), ("1177", "bob.c@test.com"),
                                             ("4460", "carol.d@test.com"), ("6642", "david.k@test.com")]):
            row = con.execute("SELECT id FROM bank_accounts WHERE masked=? AND user_id=?",
                              (masked, i + 1)).fetchone()
            self.assertIsNotNone(row, f"bank_accounts masked={masked} user {i+1}")
        self.assertEqual(con.execute("SELECT balance FROM bank_accounts WHERE id=1").fetchone()[0],
                         answers.T17_CHECKING)
        self.assertEqual(con.execute("SELECT balance FROM bank_accounts WHERE id=2").fetchone()[0],
                         answers.T17_SAVINGS)
        self.assertEqual(con.execute("SELECT masked FROM card_accounts WHERE id=7").fetchone()[0], "3358")
        self.assertEqual(con.execute("SELECT balance FROM card_accounts WHERE id=7").fetchone()[0],
                         answers.T23_CARD_BEFORE)
        self.assertEqual(con.execute("SELECT balance FROM bank_accounts WHERE id=7").fetchone()[0],
                         answers.T23_CHECKING_BEFORE)
        self.assertEqual(con.execute("SELECT autopay FROM card_accounts WHERE id=3").fetchone()[0] in (True, 1),
                         True)
        self.assertEqual(con.execute("SELECT points FROM card_accounts WHERE id=5").fetchone()[0],
                         answers.T26_POINTS_BEFORE)
        con.close()

    def test_alice_transfers_truth(self):
        con = _seed_conn()
        rows = {r["id"]: r["status"] for r in con.execute(
            "SELECT id, status FROM transfers WHERE user_id=1")}
        self.assertEqual(rows[answers.T22_TRANSFER_ID], "scheduled")
        self.assertEqual(sum(1 for s in rows.values() if s == "scheduled"), 2)
        r = con.execute("SELECT amount, to_label FROM transfers WHERE id=?", (answers.T22_TRANSFER_ID,)).fetchone()
        self.assertEqual(r["amount"], answers.T22_AMOUNT)
        self.assertIn("Freedom Unlimited", r["to_label"])
        con.close()

    def test_t27_higher_balance_card_truth(self):
        """T27's paid card must be the higher-balance one of Alice's two cards."""
        con = _seed_conn()
        cards = {r["id"]: r["balance"] for r in con.execute(
            "SELECT id, balance FROM card_accounts WHERE user_id=1")}
        self.assertEqual(sorted(cards), [1, 2])
        self.assertEqual(cards[answers.T27_CARD_ID], answers.T27_CARD_BEFORE)
        self.assertGreater(cards[answers.T27_CARD_ID], max(
            v for k, v in cards.items() if k != answers.T27_CARD_ID))
        self.assertAlmostEqual(
            con.execute("SELECT balance FROM bank_accounts WHERE id=?",
                        (answers.T27_BANK_ID,)).fetchone()[0], answers.T27_CHECKING_BEFORE, places=2)
        self.assertAlmostEqual(cards[1], 412.66, places=2)  # distractor: the lower-balance card
        con.close()

    def test_t28_savings_autosave_truth(self):
        """T28's canceled transfer must be the scheduled savings autosave."""
        con = _seed_conn()
        r = con.execute("SELECT amount, date, status, frequency, memo, to_label FROM transfers "
                        "WHERE id=?", (answers.T28_TRANSFER_ID,)).fetchone()
        self.assertAlmostEqual(r["amount"], answers.T28_AMOUNT, places=2)
        self.assertEqual(r["date"], answers.T28_DATE)
        self.assertEqual(r["status"], "scheduled")
        self.assertEqual(r["frequency"], "monthly")
        self.assertIn("Autosave", r["memo"])
        self.assertIn("Chase Savings", r["to_label"])
        self.assertIn("3091", r["to_label"])
        con.close()

    def test_premier_plus_tagline_upstream_wording(self):
        """The contributor fix: Premier Plus Checking tagline must carry the
        upstream wording 'for your financial goals' (was 'for the ...')."""
        con = _seed_conn()
        tagline = con.execute("SELECT tagline FROM deposit_products WHERE slug='premier-plus-checking'").fetchone()[0]
        self.assertIn("for your financial goals", tagline)
        self.assertNotIn("for the financial goals", tagline)
        con.close()

    def test_dining_transactions_truth(self):
        con = _seed_conn()
        tot = con.execute("""SELECT SUM(amount) FROM transactions WHERE user_id=1
            AND category='dining' AND amount>0""").fetchone()[0]
        self.assertAlmostEqual(tot, answers.T18_TOTAL, places=2)
        top = con.execute("""SELECT merchant, amount FROM transactions WHERE user_id=1
            AND category='dining' ORDER BY amount DESC LIMIT 1""").fetchone()
        self.assertEqual(top["merchant"], answers.T18_MAX_MERCHANT)
        self.assertAlmostEqual(top["amount"], answers.T18_MAX_AMOUNT, places=2)
        con.close()

    def test_statement_truth(self):
        con = _seed_conn()
        r = con.execute("""SELECT s.period_label, s.balance, s.points_earned FROM statements s
            JOIN card_accounts ca ON ca.id=s.card_account_id
            JOIN users u ON u.id=ca.user_id
            WHERE u.email='bob.c@test.com' AND ca.card_id=(SELECT id FROM cards WHERE slug='ink-business-cash')
            ORDER BY s.close_date DESC LIMIT 1""").fetchone()
        self.assertEqual(r["period_label"], answers.T19_PERIOD)
        self.assertAlmostEqual(r["balance"], answers.T19_BALANCE, places=2)
        self.assertEqual(r["points_earned"], answers.T19_POINTS)
        con.close()

    def test_credit_journey_truth(self):
        con = _seed_conn()
        rows = [r["score"] for r in con.execute(
            "SELECT score FROM credit_scores WHERE user_id=3 ORDER BY date")]
        self.assertEqual(rows, [768, 772, 779, 775, 778, answers.T20_SCORE])
        con.close()

    def test_branches_truth(self):
        con = _seed_conn()
        n = con.execute("SELECT COUNT(*) FROM branches WHERE lower(city)='seattle'").fetchone()[0]
        self.assertEqual(n, answers.T12_COUNT)
        b = con.execute("SELECT address1, zip, phone FROM branches WHERE id=?",
                        (answers.T12_BALLARD_ID,)).fetchone()
        self.assertEqual(b["address1"], answers.T12_BALLARD_ADDRESS)
        self.assertEqual(b["zip"], answers.T12_BALLARD_ZIP)
        self.assertIn("461-2375", b["phone"])
        m = con.execute("SELECT address1, zip FROM branches WHERE id=?",
                        (answers.T13_BRANCH_ID,)).fetchone()
        self.assertEqual(m["address1"], "739 W Madison St")
        self.assertEqual(m["zip"], "60661")
        con.close()

    def test_application_ref_determinism(self):
        import random as _random
        slug = "doordash-rewards-mastercard"
        email = "test.user@example.com"
        ref = f"APP-{slug[:3].upper()}-{_random.Random(f'{slug}{email}').randrange(100000, 999999)}"
        self.assertEqual(ref, answers.T29_REF)

    def test_cd_and_rates_truth(self):
        con = _seed_conn()
        top = con.execute("SELECT term, apy, min_deposit FROM cds ORDER BY apy DESC LIMIT 1").fetchone()
        self.assertEqual(top["term"], "12 months")
        self.assertAlmostEqual(top["apy"], answers.T7_APY, places=2)
        self.assertEqual(top["min_deposit"], answers.T7_MIN)
        r = con.execute("SELECT loan_type, rate, apr, monthly_payment, loan_amount FROM mortgage_rates "
                        "WHERE loan_type LIKE '30 year fixed%'").fetchone()
        self.assertAlmostEqual(r["rate"], answers.T8_RATE, places=3)
        self.assertAlmostEqual(r["apr"], answers.T8_APR, places=3)
        self.assertAlmostEqual(r["monthly_payment"], answers.T8_MONTHLY, places=2)
        a = con.execute("SELECT apr, term_months, example_payment FROM auto_rates "
                        "WHERE product='Refinancing'").fetchone()
        self.assertAlmostEqual(a["apr"], answers.T10_APR, places=2)
        self.assertEqual(a["term_months"], answers.T10_TERM)
        self.assertAlmostEqual(a["example_payment"], answers.T10_PAYMENT, places=2)
        con.close()


class MatcherSanity(unittest.TestCase):
    """Answer-matching helpers behave (money / phone / clock / date)."""

    def test_money_matchers(self):
        self.assertTrue(affirm_money("$4,187.53 is the balance", 4187.53))
        self.assertTrue(affirm_money("balance is 4187.53", 4187.53))
        self.assertFalse(affirm_money("the balance is $41.87", 4187.53))
        self.assertFalse(affirm_money("it is not $795", 795))       # negation-aware
        self.assertTrue(affirm_score("unlimited 1.5% cash back", 1.5))
        self.assertFalse(affirm_score("1.5x on the card", 15))

    def test_phone_matcher(self):
        self.assertTrue(contains_phone("call 1-800-935-9935 now", 8009359935))
        self.assertTrue(contains_phone("(800) 935 9935", 8009359935))
        self.assertFalse(contains_phone("call 1-800-555-1234", 8009359935))

    def test_hour_matcher(self):
        self.assertTrue(affirm_hour("Thursday 9:00 AM to 5:00 PM", 9, 0, "AM"))
        self.assertTrue(affirm_hour("Thursday 9 a.m.–5 p.m.", 9, 0, "AM"))
        self.assertTrue(affirm_hour("lobby 09:00–17:00", 9, 0, "AM"))
        self.assertTrue(affirm_hour("lobby 09:00–17:00", 17, 0, "PM"))
        self.assertFalse(affirm_hour("open 10:00 AM", 9, 0, "AM"))

    def test_date_matcher(self):
        self.assertTrue(contains_date_iso_or_md("scheduled for 2026-09-28", "2026-09-28"))
        self.assertTrue(contains_date_iso_or_md("dated September 28, 2026", "2026-09-28"))
        self.assertFalse(contains_date_iso_or_md("on September 1", "2026-09-28"))

    def test_date_forms_matcher(self):
        from verify_lib import contains_date_forms
        self.assertTrue(contains_date_forms("scheduled for 2026-09-25", "2026-09-25"))
        self.assertTrue(contains_date_forms("scheduled September 25, 2026", "2026-09-25"))
        self.assertTrue(contains_date_forms("scheduled Sep 25, 2026", "2026-09-25"))
        self.assertTrue(contains_date_forms("scheduled Sep. 25", "2026-09-25"))
        self.assertTrue(contains_date_forms("on 09/25/2026", "2026-09-25"))
        self.assertTrue(contains_date_forms("on 9/25/2026", "2026-09-25"))
        self.assertFalse(contains_date_forms("scheduled Oct 10, 2026", "2026-09-25"))
        self.assertFalse(contains_date_forms("scheduled 2026-10-10", "2026-09-25"))
        self.assertFalse(contains_date_forms("on September 26", "2026-09-25"))
        self.assertFalse(contains_date_forms("on 9/25/27", "2026-09-25"))

    def test_count_matcher(self):
        self.assertTrue(contains_count("17 cards shown", 17))
        self.assertFalse(contains_count("17 cards shown", 16))
        self.assertTrue(contains_count("twenty-four locations", 24))


if __name__ == "__main__":
    unittest.main()
