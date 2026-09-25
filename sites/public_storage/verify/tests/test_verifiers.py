"""Deterministic verifier contract tests for the 21 Public Storage tasks.

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a
clean seed pair; stateful tasks against the seed with the exact allowed
sqlite delta); a no-op run (homepage only, empty answer, clean DB) MUST FAIL;
a shortcut (correct answer with homepage-only navigation) MUST FAIL: every
task's required surface is beyond the homepage. A wrong answer MUST FAIL.
Read-only tasks MUST FAIL on a mutated after-DB; stateful tasks MUST FAIL on
a state-mismatch (no DB delta) and on a wrong delta. Package tampering
(wrong task_id, off-site URLs, missing screenshots, non-done trajectory)
MUST fail closed.

No LLM: snapshots are seed copies mutated through sqlite, trajectories are
hand-written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, PASSWORD, RunBuilder, _acquire_seed,  # noqa: E402
                       add_payment, add_reservation, add_user, build_run, copy_db,
                       db_exec, db_one, mutate_db, noop_run, run_verifier)

STATEFUL = {0, 2, 3, 4, 5, 9, 12, 16, 17, 18}
READ_ONLY = sorted(set(range(21)) - STATEFUL)

BOB_ID = 2   # seed users: 1 alice, 2 bob, 3 carol, 4 david (insertion order)
DAVID_ID = 4
BOB_RENTAL_ID = 2  # seed rentals in BENCHMARK_USERS order: alice, bob, carol, david


# ---------------------------------------------------------------- trajectory builders
def honest_traj(n: int) -> RunBuilder:
    b = RunBuilder(f"Public Storage--{n}")
    if n == 0:
        (b.goto(BASE + "/")
          .fill(BASE + "/", "78704")
          .goto(BASE + "/self-storage-search/austin-tx-78704?sz=Medium")
          .fill(BASE + "/reservation/hold/V_1534311", "10/15/2026")
          .fill(BASE + "/reservation/hold/V_1534311", "Jordan Reyes")
          .fill(BASE + "/reservation/hold/V_1534311", "jordan.reyes@example.com")
          .fill(BASE + "/reservation/hold/V_1534311", "512-555-0142")
          .goto(BASE + "/reservation/confirmation/PS-2210134")
          .answer("I held the cheapest 10'x10' within 5 miles of 78704: reservation code "
                  "PS-2210134 at 5016 E Ben White Blvd, Austin TX, 3.3 miles from the ZIP, "
                  "for $45/mo online ($90 in store; features: Ground Floor, Inside Unit, "
                  "Rollup Door, Near Door or Elevator)."))
    elif n == 1:
        (b.goto(BASE + "/size-guide")
          .goto(BASE + "/")
          .fill(BASE + "/", "Denver")
          .goto(BASE + "/self-storage-search/denver-co?sz=Large")
          .goto(BASE + "/self-storage-co-denver/2387.html")
          .goto(BASE + "/self-storage-co-denver/5227.html")
          .goto(BASE + "/self-storage-co-denver/847.html")
          .goto(BASE + "/self-storage-co-denver/1019.html")
          .answer("The comparison chart says a 10'x20' fits a 3 Bedroom home and that is "
                  "200 square feet. Denver's cheapest 10'x20' inside unit (an indoor unit "
                  "inside the facility, not an outside, drive-up, or vehicle parking "
                  "space) is at 400 W Center Ave for $205/mo online."))
    elif n == 2:
        (b.goto(BASE + "/size-guide")
          .goto(BASE + "/size-guide/vehicle-storage-unit-35-feet/vehicle-storage-unit-35-feet.html")
          .goto(BASE + "/")
          .fill(BASE + "/", "80202")
          .goto(BASE + "/self-storage-search/denver-co-80202?type=IsVehicleUnit")
          .goto(BASE + "/self-storage-co-denver/837.html")
          .fill(BASE + "/reservation/hold/V_581627", "11/01/2026")
          .fill(BASE + "/reservation/hold/V_581627", "Riley Morgan")
          .fill(BASE + "/reservation/hold/V_581627", "riley.morgan@example.com")
          .fill(BASE + "/reservation/hold/V_581627", "303-555-0164")
          .goto(BASE + "/reservation/confirmation/PS-3350218")
          .answer("The size-guide category Up to 35' covers RVs up to 35 feet; its FAQ "
                  "page says the spaces are designed specifically for storing RVs, motor "
                  "homes, campers and boats. I held the 10'x30' at 6161 West 48th Ave "
                  "for $250/mo, reservation code PS-3350218."))
    elif n == 3:
        (b.goto(BASE + "/access-reservation")
          .fill(BASE + "/access-reservation", "PS-3184265")
          .fill(BASE + "/access-reservation", "alice.j@test.com")
          .goto(BASE + "/self-storage-wa-bellevue/68.html")
          .fill(BASE + "/reservation/hold/V_83043", "10/20/2026")
          .fill(BASE + "/reservation/hold/V_83043", "Alice Johnson")
          .fill(BASE + "/reservation/hold/V_83043", "alice.j@test.com")
          .fill(BASE + "/reservation/hold/V_83043", "(206) 555-0143")
          .goto(BASE + "/reservation/confirmation/PS-4471040")
          .goto(BASE + "/access-reservation")
          .answer("I cancelled PS-3184265 (it now shows CANCELLED) and held the cheapest "
                  "5'x10' at the same facility: new reservation code PS-4471040 at $74/mo "
                  "online."))
    elif n == 4:
        (b.goto(BASE + "/lease/sign-elease")
          .fill(BASE + "/lease/sign-elease", "bob.c@test.com")
          .fill(BASE + "/lease/sign-elease", PASSWORD)
          .goto(BASE + "/myaccount")
          .goto(BASE + "/")
          .fill(BASE + "/", "12249 NE 124th Street")
          .goto(BASE + "/self-storage-wa-kirkland/200.html")
          .fill(BASE + "/reservation/hold/V_592159", "10/10/2026")
          .goto(BASE + "/reservation/confirmation/PS-5518226")
          .answer("I cancelled my current reservation and held the cheapest 5'x5' at "
                  "the Kirkland facility on 12249 NE 124th Street: new reservation code "
                  "PS-5518226 at $72/mo online."))
    elif n == 5:
        (b.goto(BASE + "/simplified/bill-pay/login")
          .fill(BASE + "/simplified/bill-pay/login", "517204")
          .fill(BASE + "/simplified/bill-pay/login", "bob.c@test.com")
          .goto(BASE + "/simplified/bill-pay")
          .fill(BASE + "/simplified/bill-pay", "4242 4242 4242 4242")
          .fill(BASE + "/simplified/bill-pay", "11/28")
          .fill(BASE + "/simplified/bill-pay", "123")
          .answer("The billed unit is a 10'x10' at 4072 N Broadway Street, monthly rate "
                  "$186.00, current balance due $186.00. I paid the full balance with my "
                  "Visa: confirmation number PS-PAY-445118, amount charged $186.00, "
                  "remaining balance $0.00, next bill date 10/01/2026, card last four "
                  "digits 4242."))
    elif n == 6:
        (b.goto(BASE + "/")
          .fill(BASE + "/", "Bellevue")
          .goto(BASE + "/self-storage-search/bellevue-wa")
          .goto(BASE + "/self-storage-wa-bellevue/68.html")
          .goto(BASE + "/self-storage-wa-bellevue/81.html")
          .answer("12465 Northup Way has more customer reviews: 744 vs 698 at 13640 Bel "
                  "Red Road, so 46 more. 12465 Northup Way's cheapest 5'x5' online rate "
                  "is $65/mo ($109 in store, promotion $1 FIRST MONTH RENT, phone "
                  "425-296-6313, 24 Hour Access / 24/7); 13640 Bel Red Road's cheapest "
                  "5'x5' is $75/mo, so 12465 Northup Way's costs less."))
    elif n == 7:
        (b.goto(BASE + "/size-guide")
          .goto(BASE + "/size-guide/10x15-storage-unit/10x15-storage-unit.html")
          .goto(BASE + "/")
          .fill(BASE + "/", "13640 Bel Red Road")
          .goto(BASE + "/self-storage-search/bellevue-wa")
          .goto(BASE + "/self-storage-wa-bellevue/81.html")
          .answer("The 10'x15' FAQ page says it holds 150 square feet, comparable to a "
                  "spare bedroom. The cheapest elevator-access 10'x15' is $199/mo online "
                  "($224 in store, promotion $1 FIRST MONTH RENT); the cheapest "
                  "ground-floor 10'x15' is $250/mo online ($282 in store, promotion $1 "
                  "FIRST MONTH RENT). The cheaper elevator unit's online price saves $25 "
                  "versus its own in-store price each month, and the ground-floor unit's "
                  "online rate is $51 more."))
    elif n == 8:
        (b.goto(BASE + "/")
          .fill(BASE + "/", "Chicago")
          .goto(BASE + "/self-storage-search/chicago-il")
          .goto(BASE + "/self-storage-il-chicago/1268.html")
          .goto(BASE + "/self-storage-il-chicago")
          .goto(BASE + "/self-storage-il-chicago/1345.html")
          .answer("The Chicago city page shows an average cost of $160, the cheapest unit "
                  "currently listed at $50, and 10 Chicago locations. The most-reviewed "
                  "Chicago facility is 3659 S Ashland Ave with 869 reviews, rated 4.7, "
                  "phone 773-920-1940. Its cheapest currently listed unit is a 5'x5' at "
                  "$65/mo online."))
    elif n == 9:
        (b.goto(BASE + "/myaccount/identity/create-account")
          .fill(BASE + "/myaccount/identity/create-account", "Maria")
          .fill(BASE + "/myaccount/identity/create-account", "Torres")
          .fill(BASE + "/myaccount/identity/create-account", "maria.torres@example.com")
          .fill(BASE + "/myaccount/identity/create-account", "312-555-0188")
          .fill(BASE + "/myaccount/identity/create-account", "SunnyDays2026!")
          .fill(BASE + "/myaccount/identity/create-account", "SunnyDays2026!")
          .goto(BASE + "/myaccount")
          .goto(BASE + "/")
          .fill(BASE + "/", "60601")
          .goto(BASE + "/self-storage-search/chicago-il-60601?sz=Medium")
          .goto(BASE + "/self-storage-il-chicago/1217.html")
          .goto(BASE + "/self-storage-il-chicago/1739.html")
          .fill(BASE + "/reservation/hold/V_1355186", "11/01/2026")
          .goto(BASE + "/reservation/confirmation/PS-6629301")
          .answer("I created the account and held the cheapest climate-controlled "
                  "10'x10' within 2 miles of 60601: reservation code PS-6629301 at "
                  "947 W Van Buren St, Chicago, for $149/mo online."))
    elif n == 10:
        (b.goto(BASE + "/blog")
          .goto(BASE + "/blog/storage-tips")
          .goto(BASE + "/blog/storage-tips/tips-for-organizing-a-storage-unit-like-a-pro.html")
          .goto(BASE + "/blog/storage-tips")
          .goto(BASE + "/blog/storage-tips/how-long-can-you-keep-clothes-in-a-storage-unit.html")
          .answer("Before tossing items into your unit you should map it out, dividing "
                  "the space into zones. Heavy items go on the bottom when stacking. "
                  "Label three sides of every bin. Keep frequently used items near the "
                  "front, and leave a small walkway down the middle. The same-category "
                  "clothes article says there isn't a specific time limit for storing "
                  "clothing; clean them (wash or dry-clean) before storing, and moisture "
                  "is one of the biggest long-term concerns. Both articles are filed "
                  "under the Storage Tips blog category."))
    elif n == 11:
        (b.goto(BASE + "/help/")
          .goto(BASE + "/help/reservations-and-holds")
          .goto(BASE + "/help/billing-and-payments")
          .goto(BASE + "/help/renting-and-move-in")
          .goto(BASE + "/help/security-and-access")
          .answer("Holding a unit costs nothing — a reservation holds the unit with no "
                  "payment and no obligation — and it lasts seven days (from the "
                  "Reservations & Holds topic). A late fee is applied when a monthly "
                  "payment is more than five days past due (from the Billing & Payments "
                  "topic). New rentals are subject to a one-time $29 administration fee, "
                  "and on move-in day you should bring a government-issued photo ID (from "
                  "the Renting & Move-In topic). Only tenants receive gate codes; report "
                  "a lost code to the property manager immediately (from the Security & "
                  "Access topic)."))
    elif n == 12:
        (b.goto(BASE + "/lease/sign-elease")
          .fill(BASE + "/lease/sign-elease", "carol.d@test.com")
          .fill(BASE + "/lease/sign-elease", PASSWORD)
          .goto(BASE + "/myaccount")
          .goto(BASE + "/myaccount/edit")
          .fill(BASE + "/myaccount/edit", "(407) 555-0777")
          .goto(BASE + "/myaccount")
          .answer("I updated the phone number to (407) 555-0777. My account number is "
                  "629145. My rental is a 10'x10' at 1313 45th Street, Orlando, at a "
                  "monthly rate of $129.00 with a current balance of $129.00. It started "
                  "05/20/2026, the next bill date is 10/01/2026, and the gate code is "
                  "#5502. My current reservation shows status HELD."))
    elif n == 13:
        (b.goto(BASE + "/storage-solutions/military-storage")
          .goto(BASE + "/")
          .fill(BASE + "/", "Charlotte")
          .goto(BASE + "/self-storage-search/charlotte-nc")
          .goto(BASE + "/self-storage-nc-charlotte/2334.html")
          .answer("The military storage page says Public Storage offers military personnel "
                  "and their families a flexible, convenient way to store belongings. The "
                  "highest-rated Charlotte facility is 1001 N Tryon St, rated 4.8 with 533 "
                  "reviews, phone 704-266-1406. Its cheapest currently listed unit is a "
                  "5'x10' at $71/mo online ($79 in store, promotion $1 FIRST MONTH RENT), "
                  "and the facility offers Drive-Up Access."))
    elif n == 14:
        (b.goto(BASE + "/self-storage/24-hour-storage")
          .goto(BASE + "/")
          .fill(BASE + "/", "724 8th St")
          .goto(BASE + "/self-storage-search/kirkland-wa")
          .goto(BASE + "/self-storage-wa-kirkland/496.html")
          .answer("The 24-hour page says 24/7 Access gives you the freedom to stop by "
                  "your unit when it works for you. Yes — the Kirkland facility at 724 8th "
                  "St offers 24 Hour Access (24/7); its access hours on Sunday are "
                  "6:00 AM - 10:00 PM. It is rated 4.8 with 500 reviews, phone "
                  "425-285-7778, and offers Climate Controlled units. Its cheapest 5'x10' "
                  "online rate is $101/mo ($169 in store, promotion NO ADMIN FEE & FREE "
                  "LOCK)."))
    elif n == 15:
        (b.goto(BASE + "/")
          .fill(BASE + "/", "98101")
          .goto(BASE + "/self-storage-search/seattle-wa-98101")
          .goto(BASE + "/self-storage-search/seattle-wa-98101?sort=price")
          .goto(BASE + "/self-storage-wa-seattle/2610.html")
          .answer("Under Recommended the first facility is 1334 Alaskan Way at 0.2 "
                  "miles. Under Lowest Price the first facility is 1200 S Dearborn St at "
                  "1.3 miles. The top three under Lowest Price in order are 1200 S "
                  "Dearborn St, 700 Fairview Ave N, and 1515 13th Ave. The cheapest unit "
                  "listed at 1200 S Dearborn St is a 5'x4' at $39/mo online."))
    elif n == 16:
        (b.goto(BASE + "/")
          .fill(BASE + "/", "32801")
          .goto(BASE + "/self-storage-search/orlando-fl-32801?sz=Small")
          .goto(BASE + "/self-storage-fl-orlando/2156.html")
          .goto(BASE + "/self-storage-fl-orlando/729.html")
          .fill(BASE + "/reservation/hold/V_629662", "10/18/2026")
          .fill(BASE + "/reservation/hold/V_629662", "Alex Brooks")
          .fill(BASE + "/reservation/hold/V_629662", "alex.brooks@example.com")
          .fill(BASE + "/reservation/hold/V_629662", "407-555-0132")
          .goto(BASE + "/reservation/confirmation/PS-7730412")
          .answer("I held the cheapest 5'x10' near 32801 at a facility rated at least "
                  "4.8: reservation code PS-7730412 at 4100 John Young Parkway, Orlando, "
                  "for $20/mo online."))
    elif n == 17:
        (b.goto(BASE + "/climate-controlled-storage")
          .goto(BASE + "/")
          .fill(BASE + "/", "98101")
          .goto(BASE + "/self-storage-search/seattle-wa-98101?sz=Medium")
          .goto(BASE + "/self-storage-wa-seattle/2050.html")
          .goto(BASE + "/self-storage-wa-seattle/5903.html")
          .fill(BASE + "/reservation/hold/V_1475417", "10/25/2026")
          .fill(BASE + "/reservation/hold/V_1475417", "Alex Rivera")
          .fill(BASE + "/reservation/hold/V_1475417", "alex.rivera@example.com")
          .fill(BASE + "/reservation/hold/V_1475417", "206-555-0177")
          .goto(BASE + "/reservation/confirmation/PS-8841523")
          .answer("The climate-controlled page says such units may keep belongings "
                  "within a set temperature or humidity range and protect them from "
                  "heat, humidity and cold. I held the cheapest climate-controlled "
                  "10'x10' within 5 miles of 98101: code PS-8841523 at 1602 15th Ave W "
                  "for $135/mo online."))
    elif n == 18:
        (b.goto(BASE + "/lease/sign-elease")
          .fill(BASE + "/lease/sign-elease", "david.k@test.com")
          .fill(BASE + "/lease/sign-elease", PASSWORD)
          .goto(BASE + "/myaccount")
          .goto(BASE + "/")
          .fill(BASE + "/", "2100 Blake Street")
          .goto(BASE + "/self-storage-co-denver/1019.html")
          .fill(BASE + "/reservation/hold/V_131464", "10/30/2026")
          .goto(BASE + "/reservation/confirmation/PS-9952634")
          .answer("I rebooked at the same facility as my cancelled reservation: new "
                  "reservation code PS-9952634 for the cheapest 10'x10' at 2100 Blake "
                  "Street, Denver, at $117/mo online."))
    elif n == 19:
        (b.goto(BASE + "/")
          .fill(BASE + "/", "1213 W 6th Street")
          .goto(BASE + "/self-storage-search/austin-tx")
          .goto(BASE + "/self-storage-tx-austin/809.html")
          .answer("The two most recent reviewers shown are Cynthia Guerrero (5 stars, "
                  "2026-09-17) and Travis Smith (5 stars, 2026-08-22). The facility's "
                  "overall rating is 4.3 with a total review count of 516, phone "
                  "512-524-9545. Its cheapest listed unit is a 5'x5' at $68/mo online "
                  "with the promotion $1 FIRST MONTH RENT."))
    elif n == 20:
        (b.goto(BASE + "/size-guide")
          .goto(BASE + "/size-guide/10x20-storage-unit/10x20-storage-unit.html")
          .goto(BASE + "/")
          .fill(BASE + "/", "13640 Bel Red Road")
          .goto(BASE + "/self-storage-search/bellevue-wa")
          .goto(BASE + "/self-storage-wa-bellevue/81.html")
          .answer("The 10'x20' FAQ page says the unit holds 200 square feet, is about "
                  "the size of a standard one-car garage, and is great for storing the "
                  "contents of a multi-bedroom home. The cheapest 10'x20' at 13640 Bel "
                  "Red Road features Ground Floor and an Outside Unit, Rollup Door "
                  "(Enclosed): in-store monthly price $552, online rate $414, promotion "
                  "2ND MONTH FREE — a monthly saving of $138. The facility lists three "
                  "10'x20' units."))
    return b


WRONG_ANSWERS = {
    0: "I held a 10'x10' at 4202 Santiago Street: code PS-0000001, $48/mo, 2.3 miles, "
       "$96 in store, drive-up features.",
    1: "The chart says 10'x25' fits a 3 Bedroom home at 250 sq ft; the cheapest inside "
       "10'x20' in Denver is at 2900 Fox St for $225/mo.",
    2: "The category is Up to 50'; the spaces store semi trucks. Code PS-0000002 at $315/mo.",
    3: "New code PS-0000003, rate $94/mo, old status HELD.",
    4: "New code PS-0000004, rate $94/mo.",
    5: "The billed unit is a 5'x5' at 1313 45th Street, $129.00/mo, balance $129.00. "
       "Confirmation PS-PAY-000001, amount $158.00, remaining $28.00, next bill "
       "11/01/2026, card 1111.",
    6: "13640 Bel Red Road has more reviews (698 vs 744), 46 more; its cheapest 5'x5' is "
       "$75, in store $96, promotion NO ADMIN FEE, phone 425-502-6796, no 24/7 access.",
    7: "The 10'x15' FAQ says 120 square feet, like a large closet. Elevator: $249 online / "
       "$281 in store / no promo; ground: $345 online / $389 in store; saves $32; ground "
       "is $96 more.",
    8: "Average cost $104; cheapest listed $12; 4 locations. Most-reviewed is 4072 N "
       "Broadway Street (521 reviews), rated 4.8, phone 312-555-0177, cheapest unit 5x5 "
       "at $109/mo.",
    9: "Code PS-0000009 at 1414 S Wabash Ave for $168/mo.",
    10: "Before tossing items in you should buy shelves; light items go on the bottom; "
        "label two sides; keep valuables near the front; leave shelves down the middle. "
        "Clothes must be stored under 30 days; iron them first; the biggest concern is "
        "sunlight. Category: moving.",
    11: "A hold costs $29 and lasts 30 days; a late fee applies after ten days; new "
        "rentals pay a $19 fee; bring a lock; all visitors receive gate codes; call the "
        "police if you lose yours.",
    12: "Account number 517204; phone (407) 555-0129; rental is a 5'x5' at 4072 N "
        "Broadway Street, $186.00/mo, balance $28.00, started 08/02/2026, next bill "
        "11/01/2026, gate code #9136, reservation CANCELLED.",
    13: "The page offers a 10% discount; the highest-rated facility is 4329 South Blvd "
        "rated 4.4, 210 reviews, phone 704-555-0123, cheapest unit 5x5 at $12/mo, $15 in "
        "store, no promo, no drive-up access.",
    14: "The 24-hour page says access means gated entry only. No 24/7 access; Sunday "
        "hours 9:00 AM - 6:00 PM; rating 4.1; 300 reviews; phone 425-555-0199; no "
        "climate control; cheapest 5'x10' $111 with $1 FIRST MONTH RENT, $120 in store.",
    15: "Recommended first: 700 Fairview Ave N at 1.2 miles; Lowest Price first: 1334 "
        "Alaskan Way at 0.2 miles; top three: 1515 13th Ave, 700 Fairview Ave N, 1200 S "
        "Dearborn St; cheapest unit 5'x5' at $65/mo.",
    16: "Code PS-0000016 at 3900 W Colonial Drive for $44.80/mo.",
    17: "Units are kept at freezing temperatures to protect from fire; code PS-0000017 "
        "at 1334 Alaskan Way for $162/mo.",
    18: "New code PS-0000018, rate $173/mo, at 2600 Sheridan Blvd.",
    19: "The most recent reviewers are Lisa Yu (4 stars, 2026-07-01) and jessica "
        "cutshall (3 stars, 2026-06-15); overall rating 4.8 with 698 reviews, phone "
        "425-502-6796; cheapest unit 10'x10' at $152/mo, promotion 50% OFF 1ST MONTH.",
    20: "The 10'x20' holds 150 square feet, like a small bedroom, great for one room of "
        "furniture. The cheapest 10'x20' is climate controlled: $414 in store, $552 "
        "online, promotion $1 FIRST MONTH RENT, saving $552; the facility lists one "
        "10'x20' unit.",
}


# ---------------------------------------------------------------- stateful DB deltas
def apply_honest_delta(n: int, db: Path) -> None:
    if n == 0:
        add_reservation(db, "PS-2210134", "V_1534311", 638, "Jordan Reyes",
                        "jordan.reyes@example.com", "512-555-0142", "10/15/2026")
    elif n == 2:
        add_reservation(db, "PS-3350218", "V_581627", 837, "Riley Morgan",
                        "riley.morgan@example.com", "303-555-0164", "11/01/2026")
    elif n == 3:
        db_exec(db, "UPDATE reservations SET status = 'cancelled' WHERE code = 'PS-3184265'")
        add_reservation(db, "PS-4471040", "V_83043", 68, "Alice Johnson",
                        "alice.j@test.com", "(206) 555-0143", "10/20/2026")
    elif n == 4:
        db_exec(db, "UPDATE reservations SET status = 'cancelled' WHERE code = 'PS-4907132'")
        add_reservation(db, "PS-5518226", "V_592159", 200, "Bob Chen",
                        "bob.c@test.com", "(312) 555-0177", "10/10/2026", user_id=BOB_ID)
    elif n == 5:
        add_payment(db, BOB_RENTAL_ID, "PS-PAY-445118", 186.0)
        db_exec(db, "UPDATE rentals SET balance_due = 0 WHERE id = ?", (BOB_RENTAL_ID,))
    elif n == 9:
        uid = add_user(db, "maria.torres@example.com", "Maria", "Torres", "312-555-0188")
        add_reservation(db, "PS-6629301", "V_1355186", 1739, "Maria Torres",
                       "maria.torres@example.com", "312-555-0188", "11/01/2026", user_id=uid)
    elif n == 12:
        db_exec(db, "UPDATE users SET phone = '(407) 555-0777' WHERE email = 'carol.d@test.com'")
    elif n == 16:
        add_reservation(db, "PS-7730412", "V_629662", 729, "Alex Brooks",
                        "alex.brooks@example.com", "407-555-0132", "10/18/2026")
    elif n == 17:
        add_reservation(db, "PS-8841523", "V_1475417", 5903, "Alex Rivera",
                        "alex.rivera@example.com", "206-555-0177", "10/25/2026")
    elif n == 18:
        add_reservation(db, "PS-9952634", "V_131464", 1019, "David Kim",
                        "david.k@test.com", "(720) 555-0162", "10/30/2026", user_id=DAVID_ID)
    else:
        raise AssertionError(f"task {n} is not stateful")


def honest_dbs(n: int, tmp: Path):
    """(initial, after) DB pair for an honest run of task n."""
    seed = _acquire_seed()
    initial = copy_db(tmp / f"seed_{n}.db")
    after = copy_db(tmp / f"after_{n}.db")
    if n in STATEFUL:
        apply_honest_delta(n, after)
    return initial, after


# ---------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def seed_path() -> Path:
    return _acquire_seed()


@pytest.fixture()
def tmpdir_path(tmp_path):
    return tmp_path


# ---------------------------------------------------------------- tests
@pytest.mark.parametrize("n", range(21))
def test_honest_run_passes(n, tmp_path, monkeypatch):
    """The honest trajectory + honest answer + exact DB delta => PASS."""
    monkeypatch.delenv("PUBLIC_STORAGE_TEST_SEED_DB", raising=False)
    run = build_run(tmp_path, f"honest_{n}", honest_traj(n))
    initial, after = honest_dbs(n, tmp_path)
    verdict = run_verifier(n, run, initial, after)
    assert verdict["pass"], json.dumps(verdict, indent=1)[:2000]


@pytest.mark.parametrize("n", range(21))
def test_noop_run_fails(n, tmp_path):
    """Homepage only, empty answer, clean DB => FAIL (no false positives)."""
    run = noop_run(tmp_path, f"Public Storage--{n}")
    initial = copy_db(tmp_path / "seed_noop.db")
    verdict = run_verifier(n, run, initial, initial)
    assert not verdict["pass"]
    assert "final_answer_nonempty" in verdict["reason"] or "required" in verdict["reason"] \
        or "visited" in verdict["reason"] or "answer" in verdict["reason"], verdict["reason"]


@pytest.mark.parametrize("n", range(21))
def test_shortcut_fails(n, tmp_path):
    """Correct answer but homepage-only navigation => FAIL (anti-shortcut)."""
    b = RunBuilder(f"Public Storage--{n}")
    b.goto(BASE + "/")
    honest_answer = honest_traj(n).traj["final_answer"]
    b.answer(honest_answer)
    run = build_run(tmp_path, f"shortcut_{n}", b)
    initial = copy_db(tmp_path / "seed_shortcut.db")
    verdict = run_verifier(n, run, initial, initial)
    assert not verdict["pass"], "a homepage-only run must never pass"
    assert "visited" in verdict["reason"] or "required" in verdict["reason"], verdict["reason"]


@pytest.mark.parametrize("n", range(21))
def test_wrong_answer_fails(n, tmp_path):
    """Honest navigation but a wrong answer => FAIL."""
    b = honest_traj(n)
    b.answer(WRONG_ANSWERS[n])
    run = build_run(tmp_path, f"wrong_{n}", b)
    initial, after = honest_dbs(n, tmp_path)
    verdict = run_verifier(n, run, initial, after)
    assert not verdict["pass"]
    assert "answer" in verdict["reason"], verdict["reason"]


@pytest.mark.parametrize("n", READ_ONLY)
def test_read_only_mutated_after_db_fails(n, tmp_path):
    """A read-only task with a mutated after-DB => FAIL."""
    run = build_run(tmp_path, f"mut_{n}", honest_traj(n))
    initial = copy_db(tmp_path / f"seed_mut_{n}.db")
    after = copy_db(tmp_path / f"after_mut_{n}.db")
    add_reservation(after, "PS-9999999", "V_83043", 68, "Mallory",
                    "mallory@example.com", "555-555-5555", "10/01/2026")
    verdict = run_verifier(n, run, initial, after)
    assert not verdict["pass"]
    assert "read_only" in verdict["reason"], verdict["reason"]


@pytest.mark.parametrize("n", sorted(STATEFUL))
def test_stateful_state_mismatch_fails(n, tmp_path):
    """Stateful task, agent claims success but the DB is unchanged => FAIL."""
    run = build_run(tmp_path, f"nodelta_{n}", honest_traj(n))
    initial = copy_db(tmp_path / f"seed_nodelta_{n}.db")
    verdict = run_verifier(n, run, initial, initial)
    assert not verdict["pass"], "a stateful task must fail when the DB did not change"
    assert ("reservation" in verdict["reason"] or "payment" in verdict["reason"]
            or "delta" in verdict["reason"] or "phone" in verdict["reason"]
            or "balance" in verdict["reason"] or "user" in verdict["reason"]), verdict["reason"]


@pytest.mark.parametrize("n", sorted(STATEFUL))
def test_stateful_wrong_delta_fails(n, tmp_path):
    """Stateful task with a wrong DB delta (wrong unit/facility/holder) => FAIL."""
    run = build_run(tmp_path, f"wrongdelta_{n}", honest_traj(n))
    initial = copy_db(tmp_path / f"seed_wd_{n}.db")
    after = copy_db(tmp_path / f"after_wd_{n}.db")
    if n == 5:
        add_payment(after, BOB_RENTAL_ID, "PS-PAY-445118", 158.0)   # wrong amount
        db_exec(after, "UPDATE rentals SET balance_due = 28 WHERE id = ?", (BOB_RENTAL_ID,))
    elif n == 12:
        db_exec(after, "UPDATE users SET phone = '(407) 555-0129' WHERE email = 'carol.d@test.com'")
    elif n == 9:
        add_user(after, "someone.else@example.com", "Someone", "Else", "555-555-5555")
        add_reservation(after, "PS-6629301", "V_349695", 1443, "Maria Torres",
                        "maria.torres@example.com", "312-555-0188", "11/01/2026")
    else:
        add_reservation(after, "PS-2210134", "V_118715", 648, "Right Name",
                        "right@example.com", "555-555-5555", "10/10/2026")
    verdict = run_verifier(n, run, initial, after)
    assert not verdict["pass"], f"wrong delta must fail for task {n}"


# ---------------------------------------------------------------- tamper cases
def test_wrong_task_id_fails(tmp_path):
    b = RunBuilder("Public Storage--0")
    b.goto(BASE + "/").answer("x" * 40)
    run = build_run(tmp_path, "wrongid", b)
    verdict = run_verifier(1, run)
    assert not verdict["pass"]
    assert "task_id" in verdict["reason"]


def test_offsite_url_fails(tmp_path):
    b = honest_traj(7)
    b.goto("https://www.publicstorage.com/self-storage-wa-bellevue/81.html")
    run = build_run(tmp_path, "offsite", b)
    verdict = run_verifier(7, run)
    assert not verdict["pass"]
    assert "same_origin" in verdict["reason"]


def test_not_terminated_fails(tmp_path):
    b = honest_traj(7)
    b.traj["terminated"] = False
    b.traj["termination_reason"] = "error"
    run = build_run(tmp_path, "notterm", b)
    verdict = run_verifier(7, run)
    assert not verdict["pass"]
    assert "terminated" in verdict["reason"]


def test_missing_screenshots_fails(tmp_path):
    run = build_run(tmp_path, "noshots", honest_traj(7))
    shots = run / "screenshots"
    for p in shots.glob("*.png"):
        p.unlink()
    verdict = run_verifier(7, run)
    assert not verdict["pass"]
    assert "screenshots" in verdict["reason"]


def test_corrupt_screenshot_fails(tmp_path):
    run = build_run(tmp_path, "badpng", honest_traj(7))
    (run / "screenshots" / "step_000.png").write_bytes(b"not a png")
    verdict = run_verifier(7, run)
    assert not verdict["pass"]
    assert "screenshots" in verdict["reason"]


def test_empty_answer_fails(tmp_path):
    b = honest_traj(7)
    b.answer("")
    run = build_run(tmp_path, "empty", b)
    verdict = run_verifier(7, run)
    assert not verdict["pass"]
    assert "final_answer_nonempty" in verdict["reason"]
