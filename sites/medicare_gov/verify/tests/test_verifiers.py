"""Deterministic verifier contract tests for the 15 redesigned Medicare.gov
(medicare_gov) deep tasks.

Covers, per task: the honest trajectory MUST PASS; a no-op run (homepage only,
empty answer, clean DB) MUST FAIL; a wrong answer MUST FAIL; a shortcut
(correct answer, homepage-only navigation) MUST FAIL. Read-only tasks MUST
FAIL on a mutated after-DB. Login tasks (7, 12) MUST FAIL on a missing/extra
login event, on the wrong message-read flip, and (task 12) on a missing flip.
Stateful tasks (8, 9, 10) MUST FAIL on state-mismatch (claimed success with an
unchanged DB), on the wrong state (wrong method / reason / quantity / format /
address), and on collateral deltas. Package tampering (task_id mismatch,
off-site URLs, broken screenshots, tampered seed, unavailable DB) MUST fail
closed. Task 7 additionally PASSES with the optional newest-message-opened
flip (both honest variants of the message-center step).

No docker, no LLM: snapshots are seed copies mutated through sqlite, trajectories
are hand-written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, SEED_DB, EMAILS, RunBuilder, copy_db,  # noqa: E402
                      login_statements, mutate_db, noop_run, run_verifier, USER_ID)

pytestmark = pytest.mark.skipif(not SEED_DB.is_file(),
                                reason="seed DB not built (materialize instance_seed/medicare_gov.db)")

READ_ONLY = [0, 1, 2, 3, 4, 5, 6, 11, 13, 14]
LOGIN_READ = {7: EMAILS["alice"]}
STATEFUL = {8: EMAILS["bob"], 9: EMAILS["alice"], 10: EMAILS["alice"], 12: EMAILS["alice"]}
ALL_TASKS = [f"Medicare.gov--{n}" for n in range(15)]

ALICE, BOB = EMAILS["alice"], EMAILS["bob"]


# ------------------------------------------------------------------ honest fixtures
def honest_answer(n: int) -> str:
    return {
        0: ("Acupuncture for chronic low back pain: up to 12 treatments in 90 days; if he "
            "shows improvement, an additional 8 sessions for a maximum of 20 treatments in "
            "a 12-month period; chronic means the pain has lasted 12 weeks or longer. "
            "High-risk glaucoma screening: once every 12 months. Shingles vaccine with "
            "Part D: $0 — you pay nothing."),
        1: ("2026 costs: the Part A deductible is $1,736 for each inpatient hospital "
            "benefit period and the Part B deductible is $283 for the year; inpatient "
            "hospital days 1-60 cost $0 each day after the "
            "deductible; skilled nursing facility days 21-100 cost $217 in coinsurance each "
            "day. SNF rules: he needs a qualifying inpatient hospital stay of at least 3 "
            "days in a row; an ACO approved for the SNF 3-Day Rule Waiver can replace that "
            "requirement; Part A covers up to 100 SNF days per benefit period, and the Part "
            "A deductible is not charged again for SNF care in the same benefit period."),
        2: ("The doctors & clinicians search near Boston, MA with keyword 'family practice' "
            "returned 12 results; the first (closest) is Bailey Walker Goodwin, a Family "
            "practice doctor, for the referral. Beth Israel Deaconess Medical Center: "
            "emergency services Yes; ownership type Voluntary non-profit - Private; it "
            "reports 15 patient experience measures."),
        3: ("Memorial Medical Center has the higher overall rating: 3 out of 5 (St Johns "
            "Hospital is 2 out of 5). The Houston dialysis facility with 48 stations and a "
            "late shift is Davita Omni Dialysis Center, phone (713) 665-4747."),
        4: ("12 of the nursing homes near Denver, CO have an overall rating of 5 stars, "
            "including Advanced Health Care of Aurora and Ahc of Lakewood, LLC. The "
            "closest walker supplier for ZIP 80204 is King Soopers Pharmacy #001, phone "
            "(303) 571-1943."),
        5: ("The $0 monthly premium Medicare Advantage plans for ZIP 62701 are Aetna "
            "Medicare Premier (HMO), UnitedHealthcare Dual Complete (HMO D-SNP), and "
            "Wellcare No Premium (HMO). The higher-rated drug plan is Humana Walmart "
            "Value Rx (PDP) with 4 of 5 stars. Blue Cross Medicare Classic (PPO) has a "
            "$54 monthly premium and a $7,550 in-network out-of-pocket limit."),
        6: ("The 5-star Medicare Advantage plan for ZIP 80204 is Kaiser Permanente "
            "Medicare Plus (HMO) with a $62 monthly premium. The order for 2 print copies "
            "of Medicare & You 2027 (product # 10050) in Standard Print format to 12 Elm "
            "Court, Denver, CO 80204 was received — the confirmation says the request was "
            "received and ships within 2-4 weeks."),
        7: ("The July 2026 screening colonoscopy claim: Medicare paid $1,736.00 and you "
            "may be billed $0.00. The blood sugar test strips claim: Medicare paid $77.12 "
            "and you may be billed $19.28. The newest unread message in the message "
            "center has the subject 'Reminder: Medicare Open Enrollment starts October 15'."),
        8: ("The I-MEDIC number to report Medicare Advantage or drug plan fraud is "
            "1-877-7SAFERX (1-877-772-3379). The due Part B premium of $202.90 was paid "
            "with the default method 'Bank account ending 4821', and the account mailing "
            "address is now 789 Oak Street, Oak Park, IL 60302."),
        9: ("Alice's Medicare Number is 1EG4-TE5-MK73. The account settings now show the "
            "current mailing address 45 Meadow Lane, Buffalo Grove, IL 60089. The free "
            "replacement card (reason: lost) was ordered — status: Mailing in 7-10 days, "
            "and the Medicare Number stays the same."),
        10: ("Ordered 2 copies of Medicare Coverage of Cancer Treatment Services (product "
             "# 11931) in Standard Print format and 1 copy of Choosing a Medigap Policy "
             "(product # 02110) in Large Print format. Both confirmation pages show the "
             "orders ship to 12 Sunset Terrace, Springfield, IL 62704-1234."),
        11: ("Choosing a Medigap Policy is product # 02110 in the 'Health care choices' "
             "category. The Rights and protections category lists 4 products, including "
             "Medicare Rights & Protections (# 11534). The anonymous order of 1 Standard "
             "Print copy of the guide shipped to 302 W Edwards St, Springfield, IL 62704 "
             "was received (product # 02110)."),
        12: ("The message center holds 2 unread messages. The newest one has the subject "
             "'Reminder: Medicare Open Enrollment starts October 15' and its body says "
             "Open Enrollment runs October 15 through December 7, 2026. The current due "
             "Part B premium bill is $202.90, due 2026-10-25. The Medicare Number shown in "
             "account settings is 1EG4-TE5-MK73."),
        13: ("Hospice care requires Medicare Part A; the hospice doctor and the regular "
             "doctor certify that he's terminally ill, with a life expectancy of 6 months "
             "or less. He pays nothing ($0) for hospice care from a Medicare-approved "
             "hospice, with up to a $5 copayment per prescription for outpatient drugs. "
             "The first hospice listed for Houston, TX is 1st Choice Hospice LLC, phone "
             "(936) 295-7100."),
        14: ("He gets Medicare automatically because he's already getting Social Security "
             "retirement benefits. The 2026 standard Part B monthly premium is $202.90, "
             "paid each month. The Part A deductible is $1,736 per benefit period. The "
             "Medicare TTY number is 1-877-486-2048, and Part A/B sign-up is handled by "
             "the Social Security Administration (SSA). The shingles vaccine costs $0 "
             "with Part D."),
    }[n]


def honest_steps(b: RunBuilder, n: int) -> None:
    """Navigation skeleton of the honest run for task n (agent_demo step shape)."""
    if n == 0:
        b.fill("/coverage/search?q=acupuncture", "acupuncture", "input[name=q]")
        b.step("/coverage/search?q=acupuncture", "click", {"selector": "button[type=submit]"})
        b.step("/coverage/acupuncture", "click", {"selector": ".coverage-item-card a"})
        b.fill("/coverage/search?q=glaucoma", "glaucoma", "input[name=q]")
        b.step("/coverage/search?q=glaucoma", "click", {"selector": "button[type=submit]"})
        b.step("/coverage/glaucoma-screenings", "click", {"selector": ".coverage-item-card a"})
        b.fill("/coverage/search?q=shingles", "shingles", "input[name=q]")
        b.step("/coverage/search?q=shingles", "click", {"selector": "button[type=submit]"})
        b.step("/coverage/shingles-vaccines", "click", {"selector": ".coverage-item-card a"})
    elif n == 1:
        b.step("/basics", "click", {"selector": "a"})
        b.step("/basics/costs/medicare-costs", "click", {"selector": "a"})
        b.fill("/coverage/search?q=skilled+nursing", "skilled nursing", "input[name=q]")
        b.step("/coverage/search?q=skilled+nursing", "click", {"selector": "button[type=submit]"})
        b.step("/coverage/skilled-nursing-facility-care", "click", {"selector": ".coverage-item-card a"})
    elif n == 2:
        b.fill("/care-compare/search?type=Physician&loc=Boston%2C+MA&q=family+practice",
               "Boston, MA", "input[name=loc]")
        b.step("/care-compare/search?type=Physician&loc=Boston%2C+MA&q=family+practice",
               "click", {"selector": "button[type=submit]"})
        b.fill("/care-compare/search?type=Hospital&loc=Boston%2C+MA&q=Beth+Israel+Deaconess",
               "Beth Israel Deaconess", "input[name=q]")
        b.step("/care-compare/search?type=Hospital&loc=Boston%2C+MA&q=Beth+Israel+Deaconess",
               "click", {"selector": "button[type=submit]"})
        b.step("/care-compare/provider/258", "click", {"selector": "h3 a"})
    elif n == 3:
        b.fill("/care-compare/search?type=Hospital&loc=Springfield%2C+IL&q=", "Springfield, IL",
               "input[name=loc]")
        b.step("/care-compare/search?type=Hospital&loc=Springfield%2C+IL&q=",
               "click", {"selector": "button[type=submit]"})
        b.step("/care-compare/provider/3046", "click", {"selector": "h3 a"})
        b.step("/care-compare/search?type=Hospital&loc=Springfield%2C+IL&q=",
               "click", {"selector": "a"}, url_after="/care-compare/provider/3045")
        b.step("/care-compare/provider/3045", "click", {"selector": "h3 a"})
        b.fill("/care-compare/search?type=DialysisFacility&loc=Houston%2C+TX&q=", "Houston, TX",
               "input[name=loc]")
        b.step("/care-compare/search?type=DialysisFacility&loc=Houston%2C+TX&q=",
               "click", {"selector": "button[type=submit]"})
        b.step("/care-compare/provider/1310", "click", {"selector": "h3 a"})
    elif n == 4:
        b.fill("/care-compare/search?type=NursingHome&loc=Denver%2C+CO&q=", "Denver, CO",
               "input[name=loc]")
        b.step("/care-compare/search?type=NursingHome&loc=Denver%2C+CO&q=",
               "click", {"selector": "button[type=submit]"})
        b.fill("/medical-equipment-suppliers/results?location=80204&equipment=walkers",
               "80204", "input[name=location]")
        b.step("/medical-equipment-suppliers/results?location=80204&equipment=walkers",
               "click", {"selector": "button[type=submit]"})
    elif n == 5:
        b.fill("/plan-compare/search?zip=62701&plan_choice=health", "62701", "input[name=zip]")
        b.step("/plan-compare/search?zip=62701&plan_choice=health", "click",
               {"selector": "button[type=submit]"})
        b.step("/plan-compare/search?zip=62701&plan_choice=drug", "click",
               {"selector": "select"}, url_after="/plan-compare/search?zip=62701&plan_choice=drug")
        b.step("/plan-compare/search?zip=62701&plan_choice=drug", "click",
               {"selector": "button[type=submit]"})
        b.step("/plan-compare/search?zip=62701&plan_choice=health", "click",
               {"selector": "select"}, url_after="/plan-compare/search?zip=62701&plan_choice=health")
        b.step("/plan-compare/search?zip=62701&plan_choice=health", "click",
               {"selector": "button[type=submit]"})
    elif n == 6:
        b.fill("/plan-compare/search?zip=80204&plan_choice=health", "80204", "input[name=zip]")
        b.step("/plan-compare/search?zip=80204&plan_choice=health", "click",
               {"selector": "button[type=submit]"})
        b.step("/publications", "click", {"selector": "footer a"})
        b.step("/publications/search?category=&language=English", "click",
               {"selector": "button[type=submit]"})
        b.fill("/publications/search?category=&language=English&q=Medicare+%26+You+2027",
               "Medicare & You 2027", "input[name=q]")
        b.step("/publications/search?category=&language=English&q=Medicare+%26+You+2027",
               "click", {"selector": "button[type=submit]"})
        b.step("/publication-ordering/10050", "click", {"selector": "a"})
        b.step("/publication-ordering/10050", "click", {"selector": "button"},
               url_after="/publication-ordering/10050", page_text="order confirmation")
    elif n == 7:
        b.login(ALICE)
        b.step("/my/claims", "click", {"selector": "a"})
        b.step("/my/claims/2", "click", {"selector": "a"}, page_text="claim detail")
        b.step("/my/claims", "click", {"selector": "a"}, url_after="/my/claims/3")
        b.step("/my/claims/3", "click", {"selector": "a"}, page_text="claim detail")
        b.step("/my/messages", "click", {"selector": "a"})
    elif n == 8:
        b.step("/basics", "click", {"selector": "a"})
        b.step("/basics/reporting-medicare-fraud-and-abuse", "click", {"selector": "a"})
        b.login(BOB)
        b.step("/my/premiums", "click", {"selector": "a"})
        b.step("/my/premiums", "select", {"selector": "select[name=method]"},
               url_after="/my/premiums")
        b.step("/my/premiums", "click", {"selector": "button"}, url_after="/my/premiums")
        b.step("/my/dashboard", "click", {"selector": "a"})
        b.step("/my/account-settings", "click", {"selector": "a"})
        b.step("/my/account-settings/change-address", "fill",
               {"text": "789 Oak Street", "selector": "input[name=line1]"},
               url_after="/my/account-settings")
    elif n == 9:
        b.login(ALICE)
        b.step("/my/account-settings", "click", {"selector": "a"})
        b.step("/my/account-settings/change-address", "fill",
               {"text": "45 Meadow Lane", "selector": "input[name=line1]"},
               url_after="/my/account-settings")
        b.step("/my/account-settings/get-my-medicare-card", "click", {"selector": "a"})
        b.step("/my/account-settings/get-my-medicare-card", "click", {"selector": "input[name=reason]"},
               url_after="/my/account-settings/get-my-medicare-card")
        b.step("/my/account-settings/get-my-medicare-card", "click", {"selector": "button"},
               url_after="/my/account-settings/get-my-medicare-card",
               page_text="replacement card confirmation")
    elif n == 10:
        b.login(ALICE)
        b.step("/publications", "click", {"selector": "footer a"})
        b.step("/publications/search?category=&language=English", "click",
               {"selector": "button[type=submit]"})
        b.fill("/publications/search?category=&language=English&q=Medicare+Coverage+of+Cancer+Treatment+Services",
               "Medicare Coverage of Cancer Treatment Services", "input[name=q]")
        b.step("/publication-ordering/11931", "click", {"selector": "a"})
        b.step("/publication-ordering/11931", "click", {"selector": "button"},
               url_after="/publication-ordering/11931", page_text="order confirmation")
        b.fill("/publications/search?category=&language=English&q=Choosing+a+Medigap+Policy",
               "Choosing a Medigap Policy", "input[name=q]")
        b.step("/publication-ordering/02110", "click", {"selector": "a"})
        b.step("/publication-ordering/02110", "click", {"selector": "button"},
               url_after="/publication-ordering/02110", page_text="order confirmation")
    elif n == 11:
        b.step("/publications", "click", {"selector": "footer a"})
        b.step("/publications/search?category=&language=English", "click",
               {"selector": "button[type=submit]"})
        b.fill("/publications/search?category=&language=English&q=Choosing+a+Medigap+Policy",
               "Choosing a Medigap Policy", "input[name=q]")
        b.step("/publications/search?category=&language=English&q=Choosing+a+Medigap+Policy",
               "click", {"selector": "button[type=submit]"})
        b.step("/publications/search?q=&category=Rights+and+protections&language=English",
               "select", {"selector": "select[name=category]"})
        b.step("/publications/search?q=&category=Rights+and+protections&language=English",
               "click", {"selector": "button[type=submit]"})
        b.step("/publication-ordering/02110", "click", {"selector": "a"})
        b.step("/publication-ordering/02110", "click", {"selector": "button"},
               url_after="/publication-ordering/02110", page_text="order confirmation")
    elif n == 12:
        b.login(ALICE)
        b.step("/my/messages", "click", {"selector": "a"})
        b.step("/my/messages/3", "click", {"selector": "a"}, page_text="message detail")
        b.step("/my/dashboard", "click", {"selector": "a"})
        b.step("/my/premiums", "click", {"selector": "a"})
        b.step("/my/dashboard", "click", {"selector": "a"})
        b.step("/my/account-settings", "click", {"selector": "a"})
    elif n == 13:
        b.fill("/coverage/search?q=hospice", "hospice", "input[name=q]")
        b.step("/coverage/search?q=hospice", "click", {"selector": "button[type=submit]"})
        b.step("/coverage/hospice-care", "click", {"selector": ".coverage-item-card a"})
        b.fill("/care-compare/search?type=Hospice&loc=Houston%2C+TX&q=", "Houston, TX",
               "input[name=loc]")
        b.step("/care-compare/search?type=Hospice&loc=Houston%2C+TX&q=",
               "click", {"selector": "button[type=submit]"})
        b.step("/care-compare/provider/1459", "click", {"selector": "h3 a"})
    elif n == 14:
        b.step("/basics", "click", {"selector": "a"})
        b.step("/basics/get-started-with-medicare", "click", {"selector": "a"})
        b.step("/basics", "click", {"selector": "a"}, url_after="/basics/costs/medicare-costs")
        b.step("/basics/costs/medicare-costs", "click", {"selector": "a"})
        b.step("/talk-to-someone", "click", {"selector": "footer a"})
        b.fill("/coverage/search?q=shingles", "shingles", "input[name=q]")
        b.step("/coverage/search?q=shingles", "click", {"selector": "button[type=submit]"})
        b.step("/coverage/shingles-vaccines", "click", {"selector": ".coverage-item-card a"})


def expected_after_statements(n: int):
    """The exact DB deltas an honest run of task n produces (app-verified live)."""
    if n in READ_ONLY:
        return []
    uid = USER_ID[STATEFUL[n]] if n in STATEFUL else USER_ID[LOGIN_READ[n]]
    stmts = login_statements(uid)
    if n == 8:
        return stmts + [
            ("UPDATE premium_bills SET status='Paid', paid_date='2026-09-23', "
             "method='Bank account ending 4821' WHERE id=3", ()),
            ("UPDATE mailing_addresses SET is_current=0 WHERE id=2", ()),
            ("INSERT INTO mailing_addresses (user_id, line1, line2, city, state, zip, "
             "is_current, effective_date) VALUES (2, '789 Oak Street', NULL, 'Oak Park', "
             "'IL', '60302', 1, '2026-09-23')", ()),
        ]
    if n == 9:
        return stmts + [
            ("UPDATE mailing_addresses SET is_current=0 WHERE id=1", ()),
            ("INSERT INTO mailing_addresses (user_id, line1, line2, city, state, zip, "
             "is_current, effective_date) VALUES (1, '45 Meadow Lane', NULL, 'Buffalo Grove', "
             "'IL', '60089', 1, '2026-09-23')", ()),
            ("INSERT INTO card_requests (user_id, reason, requested_at, status) "
             "VALUES (1, 'lost', '2026-09-23', 'Mailing in 7-10 days')", ()),
        ]
    if n == 10:
        return stmts + [
            ("INSERT INTO pub_orders (user_id, publication_id, quantity, format, ship_line1, "
             "ship_city, ship_state, ship_zip, created_at, status) VALUES "
             "(1, 14, 2, 'Standard Print', '12 Sunset Terrace', 'Springfield', 'IL', "
             "'62704-1234', '2026-09-23', 'Processing')", ()),
            ("INSERT INTO pub_orders (user_id, publication_id, quantity, format, ship_line1, "
             "ship_city, ship_state, ship_zip, created_at, status) VALUES "
             "(1, 55, 1, 'Large Print', '12 Sunset Terrace', 'Springfield', 'IL', "
             "'62704-1234', '2026-09-23', 'Processing')", ()),
        ]
    if n == 12:
        return stmts + [("UPDATE messages SET is_read=1 WHERE id=3", ())]
    return stmts  # task 7: login only (subject read from the list)


def honest_run(tmp: Path, n: int, *, extra_statements=None, answer: str | None = None,
               with_message_flip: bool = False):
    """(run_dir, initial.db, after.db) for the honest fixture of task n."""
    run_dir = tmp / f"run{n}"
    run_dir.mkdir(parents=True)
    initial = copy_db(tmp / f"initial_{n}.db")
    after = copy_db(tmp / f"after_{n}.db")
    stmts = expected_after_statements(n)
    if with_message_flip and n == 7:
        stmts = stmts + [("UPDATE messages SET is_read=1 WHERE id=3", ())]
    if extra_statements:
        stmts = stmts + extra_statements
    if stmts:
        mutate_db(after, stmts)
    b = RunBuilder(run_dir, f"Medicare.gov--{n}")
    honest_steps(b, n)
    b.done(answer if answer is not None else honest_answer(n))
    return b.write(), initial, after


# ------------------------------------------------------------------ per-task contract
@pytest.mark.parametrize("n", range(15))
def test_honest_pass(tmp_path, n):
    run_dir, initial, after = honest_run(tmp_path, n)
    run_verifier(n, run_dir, initial, after, expect_pass=True)


def test_task7_honest_pass_with_message_opened(tmp_path):
    """Reading the newest message (open) is the other honest variant of task 7."""
    run_dir, initial, after = honest_run(tmp_path, 7, with_message_flip=True)
    run_verifier(7, run_dir, initial, after, expect_pass=True)


@pytest.mark.parametrize("n", range(15))
def test_noop_fails(tmp_path, n):
    run_dir = noop_run(tmp_path / f"noop{n}", f"Medicare.gov--{n}")
    run_verifier(n, run_dir, copy_db(tmp_path / f"noop_initial_{n}.db"),
                 copy_db(tmp_path / f"noop_after_{n}.db"), expect_pass=False)


def wrong_answer(n: int) -> str:
    """Honest navigation, adversarially wrong facts (numbers/names flipped)."""
    text = honest_answer(n)
    swaps = {
        0: [("12 treatments in 90 days", "10 treatments in 90 days"),
            ("maximum of 20", "maximum of 24"),
            ("once every 12 months", "once every 24 months")],
        1: [("$1,736", "$1,636"), ("days 1-60 cost $0", "days 1-60 cost $50"),
            ("$217", "$307"), ("3 days in a row", "2 days in a row"),
            ("100 SNF days", "150 SNF days")],
        2: [("returned 12 results", "returned 15 results"),
            ("Bailey Walker Goodwin", "Clinton K. Pong, MD"),
            ("15 patient experience measures", "18 patient experience measures")],
        3: [("3 out of 5", "4 out of 5"), ("Davita Omni Dialysis Center", "Davita Lone Star Dialysis"),
            ("(713) 665-4747", "(713) 665-4748")],
        4: [("12 of the nursing homes", "14 of the nursing homes"),
            ("King Soopers Pharmacy #001", "Asm Llc"), ("(303) 571-1943", "(303) 571-1944")],
        5: [("Wellcare No Premium (HMO)", "Cigna TotalCare (HMO)"),
            ("4 of 5 stars", "3.5 of 5 stars"), ("$7,550", "$8,550")],
        6: [("Kaiser Permanente Medicare Plus (HMO)", "Anthem MediBlue Plus (HMO)"),
            ("$62", "$18"), ("product # 10050", "product # 10051")],
        7: [("$1,736.00", "$1,700.00"), ("$77.12", "$77.21"),
            ("Open Enrollment starts October 15", "Open Enrollment starts October 17")],
        8: [("1-877-7SAFERX", "1-877-8SAFERX"), ("$202.90", "$240.90"),
            ("789 Oak Street", "789 Oak Ave")],
        9: [("1EG4-TE5-MK73", "1EG4-TE5-MK37"), ("45 Meadow Lane", "45 Meadow Dr"),
            ("7-10 days", "5-7 days")],
        10: [("# 11931", "# 11932"), ("# 02110", "# 02111"),
             ("12 Sunset Terrace", "12 Sunset Drive")],
        11: [("# 02110", "# 02111"), ("lists 4 products", "lists 5 products"),
             ("Medicare Rights & Protections", "Medicare & You 2027")],
        12: [("2 unread messages", "3 unread messages"), ("$202.90", "$200.90"),
             ("2026-10-25", "2026-11-25"), ("1EG4-TE5-MK73", "1EG4-TE5-MK37")],
        13: [("6 months or less", "12 months or less"), ("$0)", "$100)"),
             ("1st Choice Hospice LLC", "5 Star Hospice, LLC"), ("(936) 295-7100", "(936) 295-7101")],
        14: [("$202.90", "$185.90"), ("$1,736", "$1,596"),
             ("1-877-486-2048", "1-877-486-2049")],
    }
    for old, new in swaps[n]:
        text = text.replace(old, new)
    return text


@pytest.mark.parametrize("n", range(15))
def test_wrong_answer_fails(tmp_path, n):
    run_dir, initial, after = honest_run(tmp_path, n, answer=wrong_answer(n))
    run_verifier(n, run_dir, initial, after, expect_pass=False)


@pytest.mark.parametrize("n", range(15))
def test_shortcut_fails(tmp_path, n):
    """Correct answer but homepage-only navigation — the navigation gates must FAIL it."""
    run_dir = tmp_path / f"shortcut{n}"
    run_dir.mkdir(parents=True)
    b = RunBuilder(run_dir, f"Medicare.gov--{n}")
    b.step("/", "click", {"selector": "body"})
    b.done(honest_answer(n))
    run_verifier(n, b.write(), copy_db(tmp_path / f"sc_initial_{n}.db"),
                 copy_db(tmp_path / f"sc_after_{n}.db"), expect_pass=False)


# ------------------------------------------------------------------ read-only DB mutation
@pytest.mark.parametrize("n", READ_ONLY)
def test_readonly_db_mutation_fails(tmp_path, n):
    """A read-only task whose after-DB carries ANY write must FAIL."""
    run_dir, initial, after = honest_run(
        tmp_path, n, extra_statements=[
            ("INSERT INTO subscriber_emails (email, created_at) "
             "VALUES ('sneaky@evil.example', '2026-09-23')", ())])
    run_verifier(n, run_dir, initial, after, expect_pass=False)


# ------------------------------------------------------------------ login-account tasks
def test_task7_missing_login_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 7)
    mutate_db(after, [("DELETE FROM login_events WHERE id=9", ())])
    run_verifier(7, run_dir, initial, after, expect_pass=False)


def test_task7_extra_login_fails(tmp_path):
    run_dir, initial, after = honest_run(
        tmp_path, 7, extra_statements=login_statements(USER_ID[ALICE]))
    run_verifier(7, run_dir, initial, after, expect_pass=False)


def test_task7_wrong_message_flip_fails(tmp_path):
    run_dir, initial, after = honest_run(
        tmp_path, 7, extra_statements=[("UPDATE messages SET is_read=1 WHERE id=1", ())])
    run_verifier(7, run_dir, initial, after, expect_pass=False)


def test_task12_missing_flip_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 12)
    mutate_db(after, [("UPDATE messages SET is_read=0 WHERE id=3", ())])
    run_verifier(12, run_dir, initial, after, expect_pass=False)


def test_task12_wrong_message_flip_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 12)
    mutate_db(after, [("UPDATE messages SET is_read=0 WHERE id=3", ()),
                      ("UPDATE messages SET is_read=1 WHERE id=1", ())])
    run_verifier(12, run_dir, initial, after, expect_pass=False)


def test_task12_missing_login_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 12)
    mutate_db(after, [("DELETE FROM login_events WHERE id=9", ())])
    run_verifier(12, run_dir, initial, after, expect_pass=False)


def test_task12_collateral_fails(tmp_path):
    run_dir, initial, after = honest_run(
        tmp_path, 12, extra_statements=[
            ("INSERT INTO pub_orders (user_id, publication_id, quantity, format, "
             "ship_line1, ship_city, ship_state, ship_zip, created_at, status) VALUES "
             "(1, 14, 1, 'Standard Print', '12 Sunset Terrace', 'Springfield', 'IL', "
             "'62704-1234', '2026-09-23', 'Processing')", ())])
    run_verifier(12, run_dir, initial, after, expect_pass=False)


# ------------------------------------------------------------------ stateful tasks
def test_task8_state_mismatch_fails(tmp_path):
    """Claims the payment + address change but the DB is untouched."""
    run_dir, initial, after = honest_run(tmp_path, 8)
    mutate_db(after, [
        ("UPDATE premium_bills SET status='Due', paid_date=NULL, method=NULL WHERE id=3", ()),
        ("UPDATE mailing_addresses SET is_current=1 WHERE id=2", ()),
        ("DELETE FROM mailing_addresses WHERE line1='789 Oak Street'", ()),
    ])
    run_verifier(8, run_dir, initial, after, expect_pass=False)


def test_task8_wrong_payment_method_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 8)
    mutate_db(after, [("UPDATE premium_bills SET method='Visa card ending 8419' WHERE id=3", ())])
    run_verifier(8, run_dir, initial, after, expect_pass=False)


def test_task8_other_bill_tampered_fails(tmp_path):
    run_dir, initial, after = honest_run(
        tmp_path, 8, extra_statements=[
            ("UPDATE premium_bills SET method='Something else' WHERE id=4", ())])
    run_verifier(8, run_dir, initial, after, expect_pass=False)


def test_task8_address_unchanged_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 8)
    mutate_db(after, [
        ("UPDATE mailing_addresses SET is_current=1 WHERE id=2", ()),
        ("DELETE FROM mailing_addresses WHERE line1='789 Oak Street'", ()),
    ])
    run_verifier(8, run_dir, initial, after, expect_pass=False)


def test_task8_wrong_address_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 8)
    mutate_db(after, [("UPDATE mailing_addresses SET zip='60301' WHERE line1='789 Oak Street'", ())])
    run_verifier(8, run_dir, initial, after, expect_pass=False)


def test_task8_collateral_fails(tmp_path):
    run_dir, initial, after = honest_run(
        tmp_path, 8, extra_statements=[
            ("INSERT INTO card_requests (user_id, reason, requested_at, status) "
             "VALUES (2, 'lost', '2026-09-23', 'Mailing in 7-10 days')", ())])
    run_verifier(8, run_dir, initial, after, expect_pass=False)


def test_task8_paid_alice_bill_fails(tmp_path):
    """The wrong user's bill was paid — bob's Due bill must be the one that flips."""
    run_dir, initial, after = honest_run(
        tmp_path, 8, extra_statements=[
            ("UPDATE premium_bills SET status='Paid', paid_date='2026-09-23', "
             "method='Bank account ending 4821' WHERE id=1", ())])
    run_verifier(8, run_dir, initial, after, expect_pass=False)


def test_task9_state_mismatch_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 9)
    mutate_db(after, [
        ("UPDATE mailing_addresses SET is_current=1 WHERE id=1", ()),
        ("DELETE FROM mailing_addresses WHERE line1='45 Meadow Lane'", ()),
        ("DELETE FROM card_requests WHERE id=1", ()),
    ])
    run_verifier(9, run_dir, initial, after, expect_pass=False)


def test_task9_wrong_reason_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 9)
    mutate_db(after, [("UPDATE card_requests SET reason='stolen' WHERE id=1", ())])
    run_verifier(9, run_dir, initial, after, expect_pass=False)


def test_task9_address_unchanged_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 9)
    mutate_db(after, [
        ("UPDATE mailing_addresses SET is_current=1 WHERE id=1", ()),
        ("DELETE FROM mailing_addresses WHERE line1='45 Meadow Lane'", ()),
    ])
    run_verifier(9, run_dir, initial, after, expect_pass=False)


def test_task9_collateral_fails(tmp_path):
    run_dir, initial, after = honest_run(
        tmp_path, 9, extra_statements=[
            ("UPDATE premium_bills SET status='Paid', paid_date='2026-09-23', "
             "method='Bank account ending 4821' WHERE id=1", ())])
    run_verifier(9, run_dir, initial, after, expect_pass=False)


def test_task10_state_mismatch_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 10)
    mutate_db(after, [("DELETE FROM pub_orders", ())])
    run_verifier(10, run_dir, initial, after, expect_pass=False)


def test_task10_single_order_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 10)
    mutate_db(after, [("DELETE FROM pub_orders WHERE publication_id=55", ())])
    run_verifier(10, run_dir, initial, after, expect_pass=False)


def test_task10_wrong_quantity_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 10)
    mutate_db(after, [("UPDATE pub_orders SET quantity=1 WHERE publication_id=14", ())])
    run_verifier(10, run_dir, initial, after, expect_pass=False)


def test_task10_wrong_format_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 10)
    mutate_db(after, [("UPDATE pub_orders SET format='Braille' WHERE publication_id=55", ())])
    run_verifier(10, run_dir, initial, after, expect_pass=False)


def test_task10_wrong_ship_address_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 10)
    mutate_db(after, [("UPDATE pub_orders SET ship_line1='1 Wrong Way' WHERE publication_id=14", ())])
    run_verifier(10, run_dir, initial, after, expect_pass=False)


def test_task8_sneaky_alice_address_change_fails(tmp_path):
    """Bob's own changes are right, but a write inside an allowed table to
    ANOTHER user's rows must still FAIL."""
    run_dir, initial, after = honest_run(
        tmp_path, 8, extra_statements=[
            ("UPDATE mailing_addresses SET zip='99999' WHERE id=1", ())])
    run_verifier(8, run_dir, initial, after, expect_pass=False)


def test_task9_sneaky_bob_card_request_fails(tmp_path):
    run_dir, initial, after = honest_run(
        tmp_path, 9, extra_statements=[
            ("INSERT INTO card_requests (user_id, reason, requested_at, status) "
             "VALUES (2, 'lost', '2026-09-23', 'Mailing in 7-10 days')", ())])
    run_verifier(9, run_dir, initial, after, expect_pass=False)


def test_task10_sneaky_bob_order_fails(tmp_path):
    run_dir, initial, after = honest_run(
        tmp_path, 10, extra_statements=[
            ("INSERT INTO pub_orders (user_id, publication_id, quantity, format, "
             "ship_line1, ship_city, ship_state, ship_zip, created_at, status) VALUES "
             "(2, 14, 1, 'Standard Print', '408 Westview Drive, Apt 3', 'Springfield', "
             "'IL', '62702-8811', '2026-09-23', 'Processing')", ())])
    run_verifier(10, run_dir, initial, after, expect_pass=False)


def test_task10_collateral_fails(tmp_path):
    run_dir, initial, after = honest_run(
        tmp_path, 10, extra_statements=[
            ("INSERT INTO card_requests (user_id, reason, requested_at, status) "
             "VALUES (1, 'lost', '2026-09-23', 'Mailing in 7-10 days')", ())])
    run_verifier(10, run_dir, initial, after, expect_pass=False)


# ------------------------------------------------------------------ package tampering (fail-closed)
@pytest.mark.parametrize("n", [0, 7, 8, 10, 14])
def test_task_id_mismatch_fails_closed(tmp_path, n):
    run_dir, initial, after = honest_run(tmp_path, n)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["task_id"] = "Medicare.gov--99"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    run_verifier(n, run_dir, initial, after, expect_pass=False)


@pytest.mark.parametrize("n", [1, 6, 12])
def test_offsite_url_fails(tmp_path, n):
    run_dir, initial, after = honest_run(tmp_path, n)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["steps"][0]["url"] = "https://evil.example/medicare"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    run_verifier(n, run_dir, initial, after, expect_pass=False)


@pytest.mark.parametrize("n", [2, 9, 13])
def test_broken_screenshot_fails(tmp_path, n):
    run_dir, initial, after = honest_run(tmp_path, n)
    shots = sorted((run_dir / "screenshots").glob("step_*.png"))
    shots[1].write_bytes(b"not a png")
    run_verifier(n, run_dir, initial, after, expect_pass=False)


@pytest.mark.parametrize("n", [3, 5, 11])
def test_tampered_seed_fails_closed(tmp_path, n):
    run_dir, initial, after = honest_run(tmp_path, n)
    mutate_db(initial, [("UPDATE cost_amounts SET amount='$0.01' WHERE id=4", ())])
    run_verifier(n, run_dir, initial, after, expect_pass=False)


@pytest.mark.parametrize("n", [4, 8])
def test_unavailable_after_db_fails_closed(tmp_path, n):
    run_dir, initial, after = honest_run(tmp_path, n)
    Path(after).unlink()
    verdict = json.loads(subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / f"verify_{n}.py"),
         "--run_dir", str(run_dir), "--initial_db", str(initial),
         "--after_db", str(after), "--container", "no-such-container", "--no_llm", "True"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[1])).stdout)
    assert verdict.get("pass") is False and verdict.get("infra_error") is True


@pytest.mark.parametrize("n", [0, 12])
def test_missing_final_answer_fails(tmp_path, n):
    run_dir, initial, after = honest_run(tmp_path, n, answer="")
    run_verifier(n, run_dir, initial, after, expect_pass=False)


@pytest.mark.parametrize("n", [7, 10])
def test_unsigned_in_run_fails(tmp_path, n):
    """Stateful/account task answered without entering the demo identity."""
    run_dir, initial, after = honest_run(tmp_path, n)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    for step in traj["steps"]:
        if step.get("action") == "fill" and step.get("params", {}).get("selector") == "input[name=email]":
            step["params"]["text"] = "someone.else@test.com"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    run_verifier(n, run_dir, initial, after, expect_pass=False)


# ------------------------------------------------------------------ coverage of the task set
def test_tasks_jsonl_shape():
    """15 seven-key rows (5-key member prefix + verifier_path + judge_rubric),
    no answer key, ids in order, <=100 words each, verifier paths on disk.

    The 5-key member prefix (web_name, id, ques, web, upstream_url) is the
    contributor's byte-preserved prefix; the grading-contract sync (see
    verify/append_rubrics.py) appends exactly verifier_path + judge_rubric.
    """
    tasks_file = SEED_DB.parent.parent / "tasks.jsonl"
    repo_root = Path(__file__).resolve().parents[4]
    rows = [json.loads(l) for l in tasks_file.read_text().splitlines() if l.strip()]
    assert len(rows) == 15
    for i, row in enumerate(rows):
        assert list(row.keys()) == ["web_name", "id", "ques", "web", "upstream_url",
                                    "verifier_path", "judge_rubric"]
        assert row["id"] == f"Medicare.gov--{i}"
        assert "answer" not in row
        assert len(row["ques"].split()) <= 100
        assert row["verifier_path"] == f"sites/medicare_gov/verify/verify_{i}.py"
        assert (repo_root / row["verifier_path"]).is_file(), row["verifier_path"]
        assert row["judge_rubric"].startswith("FACT CHECKPOINTS")
        assert "FAIL" in row["judge_rubric"]
