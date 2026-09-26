"""Deterministic verifier contract tests for the 20 Raising Cane's tasks.

Covers, per task: the honest trajectory MUST PASS (research-only tasks
against a clean seed pair; stateful tasks against the seed with the exact
allowed sqlite delta); a no-op run (homepage only, empty answer, clean DB)
MUST FAIL; a wrong answer MUST FAIL; a shortcut (correct answer with
homepage-only navigation) MUST FAIL. Stateful tasks MUST FAIL on a
state-mismatch (clean DB, self-reported success). No LLM: snapshots are seed
copies mutated through sqlite, trajectories are hand-written in the
agent_demo/agent.py shape.

Honest fixtures were written from the reviewer's independent live
walkthroughs (r1: wh-rc-review-evidence/task_walks/; re-anchored for the
r2 fix @ 6a563727 from wh-raising-canes-rereview-evidence/task_walks/)
with every total re-derived from the per-quantity Olo price tables and
the 8.25% sales-tax rate.

r2 re-anchored tasks (T9/T11/T12/T16/T17) additionally carry adversarial
negatives for the pre-r2 readings: literal 13-count (T9), 4:45 PM slot
(T11), a different plush product (T12), missing points facts (T16),
missing La Marque reference/department (T17).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, RunBuilder, _acquire_seed,  # noqa: E402
                       build_run, copy_db, db_one, mutate_db, noop_run,
                       run_verifier)

CREATED = "2026-09-24 12:00:00"
STATEFUL = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 19}
RESEARCH_ONLY = sorted(set(range(20)) - STATEFUL)

# seed ids (from the deterministic seed; stable across rebuilds)
ALICE, BOB, CAROL, DAVID = 1, 2, 3, 4
LOC_LITTLE_YORK = 848
LOC_SIEGEN = 405
LOC_MCKINNEY = 887
LOC_ROSS = 793
LOC_GOLETA = 113
LOC_WESTHEIMER = 835
LOC_DRUSILLA = 401
LOC_GOVERNMENT = 402
ITEM_BOX, ITEM_3FINGER, ITEM_CANIAC, ITEM_SANDWICH, ITEM_KIDS = 1, 2, 3, 4, 5
ITEM_25F, ITEM_50F, ITEM_75F, ITEM_100F = 6, 7, 8, 9
ITEM_TOAST, ITEM_SLAW, ITEM_SAUCE = 13, 14, 15
ITEM_JUG_TEA = 18
GEAR_CREWNECK, GEAR_GIFTCARD, GEAR_OAKLEAF, GEAR_BACKPACK = 23, 6, 40, 26
GEAR_PLUSH, GEAR_BANDANA = 56, 86
DAVID_GC = "6049067bf99a74d2"


def _order_sql(order_number, user_id, loc_id, mode, pdate, ptime, cname,
               cphone, pay, sub, disc, tax, total, offer="", gcnum="",
               points=0, oid=6, status="Placed"):
    return [
        ("INSERT INTO food_orders (id, order_number, user_id, location_id, "
         "pickup_mode, pickup_date, pickup_time, contact_name, contact_phone, "
         "payment_method, gift_card_number, caniac_offer, subtotal, discount, "
         "tax, total, status, placed_at, points_earned) "
         "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
         (oid, order_number, user_id, loc_id, mode, pdate, ptime, cname, cphone,
          pay, gcnum, offer, sub, disc, tax, total, status, CREATED, points)),
    ]


def _item_sql(oid, item_id, qty_label, selections_json, line_total, ioi=11):
    return [
        ("INSERT INTO food_order_items (id, order_id, item_id, quantity_label, "
         "selections, line_total) VALUES (?,?,?,?,?,?)",
         (ioi, oid, item_id, qty_label, selections_json, line_total)),
    ]


def _gear_order_sql(order_number, user_id, sname, sline1, scity, sstate, szip,
                    pay, sub, ship, total, oid=3):
    return [
        ("INSERT INTO gear_orders (id, order_number, user_id, email, ship_name, "
         "ship_line1, ship_city, ship_state, ship_zip, payment_method, subtotal, "
         "shipping, total, placed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
         (oid, order_number, user_id, f"u{user_id}@test.com", sname, sline1, scity,
          sstate, szip, pay, sub, ship, total, CREATED)),
    ]


def _gear_item_sql(oid, product_id, variant, qty, price, goi=6):
    return [
        ("INSERT INTO gear_order_items (id, order_id, product_id, variant_title, "
         "qty, price) VALUES (?,?,?,?,?,?)",
         (goi, oid, product_id, variant, qty, price)),
    ]


# ---------------------------------------------------------------- honest fixtures

def honest_run(tmp: Path, index: int):
    """Return (run_dir, after_db_path) for the honest fixture of task `index`."""
    seed = _acquire_seed()
    tid = f"Raising Cane's--{index}"
    b = build_run(tmp, f"honest_{index:02d}", tid)
    stmts: list = []

    if index == 0:
        b.goto("/order/")
        b.fill("/order/?q=Little+York", "Little York")
        b.step("/order/?q=Little+York", "click", {"selector": "button"})
        b.step("/order/location/tx_houston_4055-little-york-rd/item/1?qty=25", "goto", {})
        b.step("/order/cart", "click", {"selector": "button"})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "click", {"selector": "button"})
        b.done("Order RC-100240 placed for curbside pickup tomorrow (2026-09-25) at "
               "5:15 PM at the Little York Road restaurant. The total on the "
               "confirmation is $329.08.")
        stmts = (_order_sql("RC-100240", None, LOC_LITTLE_YORK, "Curbside",
                            "2026-09-25", "5:15 PM", "Maya Torres", "713-555-0184",
                            "Pay at Restaurant", 304.00, 0.0, 25.08, 329.08)
                 + _item_sql(6, ITEM_BOX, "25",
                             '["No Slaw (NSL)", "Large Sweet Tea"]', 304.00))
    elif index == 1:
        for slug in ("25-finger-tailgate", "50-finger-tailgate",
                     "75-finger-tailgate", "100-finger-tailgate"):
            b.goto(f"/menu/{slug}")
        b.goto("/order/")
        b.fill("/order/?q=McKinney", "McKinney")
        b.step("/order/location/tx_mckinney_1902-north-central-expressway/item/9", "goto", {})
        b.step("/order/cart", "click", {"selector": "button"})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("Per-finger prices: 25-Finger $41.99/25 = $1.68, 50-Finger $79.99/50 = "
               "$1.60, 75-Finger $118.99/75 = $1.59, 100-Finger $142.99/100 = $1.43 — "
               "the 100-Finger Tailgate is the best value. Order RC-100240, total $154.79.")
        stmts = (_order_sql("RC-100240", None, LOC_MCKINNEY, "Pickup",
                           "2026-09-24", "5:00 PM", "Marcus", "555-0100",
                           "Pay at Restaurant", 142.99, 0.0, 11.80, 154.79)
                 + _item_sql(6, ITEM_100F, "1",
                             '["Family-Style, Large Sauce To Share"]', 142.99))
    elif index == 2:
        b.login("alice.j@test.com")
        b.goto("/caniac-club/")
        b.goto("/order/")
        b.fill("/order/?q=Siegen", "Siegen")
        b.step("/order/location/la_baton-rouge_6588-siegen-lane/item/1?qty=1", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("Alice's birthday offer (BDAY-BOX) made the Box Combo free: the final "
               "order total is $0.00, and her Caniac Club points after the order "
               "are 1275.")
        stmts = (_order_sql("RC-100240", ALICE, LOC_SIEGEN, "Pickup",
                            "2026-09-24", "12:15 PM", "Alice Johnson",
                            "(225) 555-0142", "Visa ending 4242", 11.89, 11.89,
                            0.0, 0.0, offer="BDAY-BOX")
                 + _item_sql(6, ITEM_BOX, "1", '["Regular", "Regular Sweet Tea"]', 11.89)
                 + [("UPDATE user_offers SET redeemed=1, redeemed_order='RC-100240' "
                     "WHERE user_id=? AND offer_id=1", (ALICE,))])
    elif index == 3:
        b.login("david.k@test.com")
        b.goto("/account")
        b.goto("/order/")
        b.fill("/order/?q=Westheimer", "Westheimer")
        b.step("/order/location/tx_houston_12201-westheimer-rd/item/6", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("The gift card on file had a $75.00 balance. Order RC-100240 (25-Finger "
               "Tailgate, $45.45 paid with the gift card) is placed; the remaining "
               "balance is $29.55.")
        stmts = (_order_sql("RC-100240", DAVID, LOC_WESTHEIMER, "Pickup",
                            "2026-09-24", "12:30 PM", "David Kim",
                            "(512) 555-0121", "Gift Card", 41.99, 0.0, 3.46, 45.45,
                            gcnum=DAVID_GC)
                 + _item_sql(6, ITEM_25F, "1", '["Individual Sauces"]', 41.99)
                 + [("UPDATE gift_cards SET balance=29.55 WHERE card_number=?",
                     (DAVID_GC,))])
    elif index == 4:
        b.login("bob.c@test.com")
        b.goto("/order/")
        b.fill("/order/?q=Little+York", "Little York")
        b.step("/order/location/tx_houston_4055-little-york-rd/item/2?qty=25", "goto", {})
        b.step("/order/location/tx_houston_4055-little-york-rd/item/18", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("Order RC-100240 placed (25 3 Finger Combos with no fountain drinks "
               "plus a jug of sweet tea, curbside tomorrow 12:30 PM). Total $252.48.")
        stmts = (_order_sql("RC-100240", BOB, LOC_LITTLE_YORK, "Pickup",
                            "2026-09-25", "12:30 PM", "Bob Chen",
                            "(281) 555-0177", "Visa ending 1881", 233.24, 0.0,
                            19.24, 252.48)
                 + _item_sql(6, ITEM_3FINGER, "25", '["Regular", "No Drink"]', 227.25)
                 + _item_sql(6, ITEM_JUG_TEA, "1", "[]", 5.99, ioi=12))
    elif index == 5:
        b.goto("/allergens/")
        b.goto("/order/")
        b.fill("/order/?q=Goleta", "Goleta")
        b.step("/order/location/ca_goleta_7000-hollister-ave/item/5?qty=50", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("One Kids Combo has 640 calories (nutrition page). Order RC-100240 for "
               "50 Kids Combos with milk, pickup today 3:00 PM; total $367.51.")
        stmts = (_order_sql("RC-100240", None, LOC_GOLETA, "Pickup",
                            "2026-09-24", "3:00 PM", "Ms. Rivera", "805-555-0123",
                            "Pay at Restaurant", 339.50, 0.0, 28.01, 367.51)
                 + _item_sql(6, ITEM_KIDS, "50", '["Milk"]', 339.50))
    elif index == 6:
        b.login("alice.j@test.com")
        b.goto("/account")
        b.goto("/orders/RC-100236")
        b.step("/orders/RC-100236", "click", {"selector": "button"})
        b.step("/order/cart", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("Reordered Alice's most recent order (RC-100236) for curbside pickup "
               "tomorrow 1:30 PM at the same Little York restaurant. New order "
               "RC-100240, new total $55.63.")
        stmts = (_order_sql("RC-100240", ALICE, LOC_LITTLE_YORK, "Curbside",
                            "2026-09-25", "1:30 PM", "Alice Johnson",
                            "(225) 555-0142", "Visa ending 4242", 51.39, 0.0,
                            4.24, 55.63)
                 + _item_sql(6, ITEM_CANIAC, "1",
                             '["No Slaw (NSL)", "Large Coke\\u00ae"]', 16.89)
                 + _item_sql(6, ITEM_TOAST, "25", "[]", 34.50, ioi=12))
    elif index == 7:
        b.goto("/locations/?q=Baton+Rouge")
        b.goto("/locations/la_baton-rouge_3422-drusilla-ln")
        b.goto("/order/")
        b.fill("/order/?q=Drusilla", "Drusilla")
        b.step("/order/location/la_baton-rouge_3422-drusilla-ln/item/7", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("The Baton Rouge restaurant whose drive-thru closes earliest on Friday "
               "nights is 3422 Drusilla Ln (drive-thru 9:00 AM - 11:00 PM; phone "
               "(225) 924-7505). Order RC-100240 for Saturday 6:00 PM pickup, "
               "total $86.59.")
        stmts = (_order_sql("RC-100240", None, LOC_DRUSILLA, "Pickup",
                            "2026-09-26", "6:00 PM", "Priya Patel", "225-555-0177",
                            "Pay at Restaurant", 79.99, 0.0, 6.60, 86.59)
                 + _item_sql(6, ITEM_50F, "1",
                             '["Family-Style, Large Sauce To Share"]', 79.99))
    elif index == 8:
        b.goto("/locations/?q=Houston&state=&service=Curbside+Pickup")
        b.goto("/order/")
        b.fill("/order/?q=Little+York", "Little York")
        b.step("/order/location/tx_houston_4055-little-york-rd/item/1?qty=1", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("21 Houston restaurants offer Curbside Pickup. Order RC-100240 (Box "
               "Combo, curbside today 6:30 PM at Little York Road) total $12.87.")
        stmts = (_order_sql("RC-100240", None, LOC_LITTLE_YORK, "Curbside",
                            "2026-09-24", "6:30 PM", "Jordan Ellis", "832-555-0146",
                            "Pay at Restaurant", 11.89, 0.0, 0.98, 12.87)
                 + _item_sql(6, ITEM_BOX, "1", '["Regular", "Regular Sweet Tea"]', 11.89))
    elif index == 9:
        b.goto("/locations/?q=Dallas&state=&service=Catering+Delivery")
        b.goto("/locations/tx_dallas_5201-ross-ave")
        b.goto("/order/")
        b.fill("/order/?q=Ross+Ave", "Ross Ave")
        b.step("/order/location/tx_dallas_5201-ross-ave/item/8", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("Of the restaurants in the Dallas Catering Delivery search, 12 are in "
               "Dallas, TX (the literal search shows 13 including a Waxahachie "
               "street match). The Ross Avenue restaurant's phone is (214) 515-9105. "
               "Order RC-100240 (75-Finger Tailgate, family-style sauce, pickup today "
               "5:00 PM), total $128.81.")
        stmts = (_order_sql("RC-100240", None, LOC_ROSS, "Pickup",
                            "2026-09-24", "5:00 PM", "Renee Carter", "214-555-0119",
                            "Pay at Restaurant", 118.99, 0.0, 9.82, 128.81)
                 + _item_sql(6, ITEM_75F, "1",
                             '["Family-Style, Large Sauce To Share"]', 118.99))
    elif index == 10:
        b.goto("/allergens/")
        b.goto("/order/")
        b.fill("/order/?q=Siegen", "Siegen")
        b.step("/order/location/la_baton-rouge_6588-siegen-lane/item/1?qty=1", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("Box Combo sodium 2360 mg vs Caniac Combo 3480 mg — the Box Combo is "
               "lower sodium; the calorie difference is 540. Order RC-100240 (Box "
               "Combo with Regular Sweet Tea, today 1:15 PM), total $12.87.")
        stmts = (_order_sql("RC-100240", None, LOC_SIEGEN, "Pickup",
                            "2026-09-24", "1:15 PM", "Sam Whitfield", "225-555-0162",
                            "Pay at Restaurant", 11.89, 0.0, 0.98, 12.87)
                 + _item_sql(6, ITEM_BOX, "1", '["Regular", "Regular Sweet Tea"]', 11.89))
    elif index == 11:
        b.goto("/search?q=Cane%27s+Sauce")
        b.goto("/menu/canes-sauce")
        b.goto("/allergens/")
        b.goto("/order/")
        b.fill("/order/?q=Government", "Government")
        b.step("/order/location/la_baton-rouge_5020-government-st./item/15?qty=25", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("Cane's Sauce: 190 calories per serving, allergen letters ESF. Order "
               "RC-100240 (25 servings, pickup today), total $12.18.")
        stmts = (_order_sql("RC-100240", None, LOC_GOVERNMENT, "Pickup",
                            "2026-09-24", "5:00 PM", "Dana Lopez", "225-555-0131",
                            "Pay at Restaurant", 11.25, 0.0, 0.93, 12.18)
                 + _item_sql(6, ITEM_SAUCE, "25", "[]", 11.25))
    elif index == 12:
        b.login("alice.j@test.com")
        b.goto("/gear/product/raising-canes-retro-crewneck")
        b.goto("/gear/collection/Plush")
        b.goto("/gear/product/cool-cane-plush")
        b.goto("/gear/collection/Accessories")
        b.goto("/gear/product/pet-bandana")
        b.step("/gear/cart", "goto", {})
        b.step("/gear/checkout", "goto", {})
        b.step("/gear/confirmation/GEAR-4504", "goto", {})
        b.done("Order GEAR-4504: Raising Cane's Retro Crewneck (M) $39.99, Cool Cane "
               "Barking Plush Puppy $9.99, and CANIAC Pet Bandana $4.99 to cross the "
               "free-shipping threshold. Final total $54.97 with free shipping.")
        stmts = (_gear_order_sql("GEAR-4504", ALICE, "Alice Johnson",
                                 "4321 Highland Road", "Baton Rouge", "LA", "70808",
                                 "Visa", 54.97, 0.0, 54.97)
                 + _gear_item_sql(3, GEAR_CREWNECK, "M", 1, 39.99)
                 + _gear_item_sql(3, GEAR_PLUSH, "Default Title", 1, 9.99, goi=7)
                 + _gear_item_sql(3, GEAR_BANDANA, "Default Title", 1, 4.99, goi=8))
    elif index == 13:
        b.login("carol.d@test.com")
        b.goto("/gear/collection/Headwear")
        b.goto("/search?q=hat")
        b.goto("/gear/product/oakleaf-trucker-hat")
        b.step("/gear/cart", "goto", {})
        b.step("/gear/checkout", "goto", {})
        b.step("/gear/confirmation/GEAR-4504", "goto", {})
        b.done("The cheapest adult (non-youth) hat is the Oak Leaf Trucker Hat at "
               "$21.99. Order GEAR-4504 shipped to Carol's McKinney home address, "
               "total $28.94 including $6.95 shipping.")
        stmts = (_gear_order_sql("GEAR-4504", CAROL, "Carol Davis",
                                 "1902 North Central Expressway", "McKinney", "TX",
                                 "75069", "Discover", 21.99, 6.95, 28.94)
                 + _gear_item_sql(3, GEAR_OAKLEAF, "Default Title", 1, 21.99))
    elif index == 14:
        b.login("carol.d@test.com")
        b.goto("/gift-cards/")
        b.goto("/gear/product/graduation-gift-card")
        b.step("/gear/cart", "goto", {})
        b.step("/gear/checkout", "goto", {})
        b.step("/gear/confirmation/GEAR-4504", "goto", {})
        b.done("Order GEAR-4504: Graduation Gift Card in the $25 denomination shipped "
               "to Carol's McKinney home address; total $31.95 including $6.95 "
               "shipping.")
        stmts = (_gear_order_sql("GEAR-4504", CAROL, "Carol Davis",
                                 "1902 North Central Expressway", "McKinney", "TX",
                                 "75069", "Discover", 25.00, 6.95, 31.95)
                 + _gear_item_sql(3, GEAR_GIFTCARD, "$25", 1, 25.00))
    elif index == 15:
        b.login("carol.d@test.com")
        b.goto("/caniac-club/")
        b.fill("/caniac-club/", "8823112233445566", "input[name=card_number]")
        b.goto("/order/")
        b.fill("/order/?q=McKinney", "McKinney")
        b.step("/order/location/tx_mckinney_1902-north-central-expressway/item/8", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("Card 8823112233445566 registered. Order RC-100240: 75-Finger Tailgate "
               "with the TAILGATE-10 members-only offer, discount $10.00, total "
               "$117.98.")
        stmts = (_order_sql("RC-100240", CAROL, LOC_MCKINNEY, "Pickup",
                            "2026-09-25", "5:30 PM", "Carol Davis",
                            "(214) 555-0198", "Discover ending 6011", 118.99, 10.00,
                            8.99, 117.98, offer="TAILGATE-10")
                 + _item_sql(6, ITEM_75F, "1",
                             '["Family-Style, Large Sauce To Share"]', 118.99)
                 + [("UPDATE caniac_cards SET card_number='8823112233445566' "
                     "WHERE user_id=?", (CAROL,)),
                    ("UPDATE user_offers SET redeemed=1, redeemed_order='RC-100240' "
                     "WHERE user_id=? AND offer_id=4", (CAROL,))])
    elif index == 16:
        b.login("alice.j@test.com")
        b.goto("/account")
        b.goto("/orders/RC-100236")
        b.step("/orders/RC-100236", "click", {"selector": "button"})
        b.goto("/account")
        b.done("Alice's most recent food order was RC-100236 at the Houston Little "
               "York Road restaurant, total $52.71. It has been cancelled; the "
               "cancellation returned 52 Caniac Club points and her balance "
               "afterwards is 1223.")
        stmts = [("UPDATE food_orders SET status='Cancelled' WHERE order_number=?",
                  ("RC-100236",)),
                 ("UPDATE caniac_cards SET points=1223 WHERE user_id=?", (ALICE,))]
    elif index == 17:
        b.goto("/careers/?q=Restaurant+Manager&state=TX")
        b.goto("/careers/744000151697368")
        b.goto("/careers/?q=Cashier&state=OH")
        b.goto("/careers/P1-1007372-17")
        b.done("Six Restaurant Manager jobs are currently open in Texas: San "
               "Antonio, Cedar Park, Dallas, Katy, Houston and La Marque. The La "
               "Marque opening is at 3001 FM 1764, reference 744000151697368, "
               "department Management. The Cashier opening on Polaris Parkway in "
               "Columbus, Ohio is reference P1-1007372-17, Cashier - Late Night "
               "Shift.")
        stmts = []
    elif index == 18:
        b.login("alice.j@test.com")
        b.goto("/account")
        b.goto("/account/edit")
        b.fill("/account/edit", "504-555-0187", "input[name=phone]")
        b.goto("/gear/product/caniac-backpack")
        b.step("/gear/cart", "goto", {})
        b.step("/gear/checkout", "goto", {})
        b.step("/gear/confirmation/GEAR-4504", "goto", {})
        b.done("Alice's new phone number is 504-555-0187. Gear order GEAR-4504: Caniac "
               "Backpack shipped to 500 St. Louis St, New Orleans, LA 70130, total "
               "$36.94.")
        stmts = ([("UPDATE users SET phone='504-555-0187' WHERE id=?", (ALICE,)),
                  ("INSERT INTO addresses (id, user_id, label, line1, city, state, "
                   "zip_code, is_default) VALUES (6, ?, 'NOLA', '500 St. Louis St', "
                   "'New Orleans', 'LA', '70130', 0)", (ALICE,))]
                 + _gear_order_sql("GEAR-4504", ALICE, "Alice Johnson",
                                   "500 St. Louis St", "New Orleans", "LA", "70130",
                                   "Visa", 29.99, 6.95, 36.94)
                 + _gear_item_sql(3, GEAR_BACKPACK, "Default Title", 1, 29.99))
    elif index == 19:
        b.goto("/faq/?q=corporate+phone+number")
        b.goto("/order/")
        b.fill("/order/?q=Siegen", "Siegen")
        b.step("/order/location/la_baton-rouge_6588-siegen-lane/item/3?qty=1", "goto", {})
        b.step("/order/checkout", "goto", {})
        b.step("/order/confirmation/RC-100240", "goto", {})
        b.done("The FAQ lists Restaurant Support Offices in Baton Rouge (headquarters) "
               "and Plano (Dallas-area office, phone (972) 769-3100). Order RC-100240 "
               "(Caniac Combo with Large Coke, today 2:00 PM), total $18.28.")
        stmts = (_order_sql("RC-100240", None, LOC_SIEGEN, "Pickup",
                            "2026-09-24", "2:00 PM", "R. Okafor", "225-555-0158",
                            "Pay at Restaurant", 16.89, 0.0, 1.39, 18.28)
                 + _item_sql(6, ITEM_CANIAC, "1", '["Regular", "Large Coke\\u00ae"]', 16.89))
    else:
        raise ValueError(index)

    after = mutate_db(seed, b.root / "after.db", stmts)
    copy_db(seed, b.root / "initial.db")
    return b.root, after


# ---------------------------------------------------------------- parametrized tests

def _final_answer_of(run_dir: Path) -> str:
    return json.loads((run_dir / "trajectory.json").read_text())["final_answer"]


@pytest.mark.parametrize("index", range(20))
def test_honest_pass(tmp_path, index):
    run_dir, _ = honest_run(tmp_path, index)
    out = run_verifier(index, run_dir)
    assert out["pass"], f"honest run must PASS: {out}"


@pytest.mark.parametrize("index", range(20))
def test_noop_fail(tmp_path, index):
    run_dir = noop_run(tmp_path, index)
    out = run_verifier(index, run_dir)
    assert not out["pass"], f"no-op run must FAIL: {out}"


@pytest.mark.parametrize("index", range(20))
def test_wrong_answer_fail(tmp_path, index):
    run_dir, _ = honest_run(tmp_path, index)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = ("I could not complete the task. " + traj["final_answer"][:40]
                            + " ... actually the total was $9,999.99 and the order "
                              "number was RC-999999.")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(index, run_dir)
    assert not out["pass"], f"wrong answer must FAIL: {out}"


@pytest.mark.parametrize("index", range(20))
def test_shortcut_fail(tmp_path, index):
    """Correct answer, homepage-only navigation: knowledge-shortcut must FAIL."""
    run_dir, _ = honest_run(tmp_path, index)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    for s in traj["steps"]:
        s["url"] = BASE + "/"
    traj["final_url"] = BASE + "/"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(index, run_dir)
    assert not out["pass"], f"shortcut run must FAIL: {out}"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_state_mismatch_fail(tmp_path, index):
    """Honest trajectory + answer, but the DB is unchanged (clean seed)."""
    seed = _acquire_seed()
    run_dir, _ = honest_run(tmp_path, index)
    copy_db(seed, run_dir / "after.db")  # wipe the state delta
    out = run_verifier(index, run_dir)
    assert not out["pass"], f"state-mismatch must FAIL: {out}"


def test_t9_dallas_tx_count_pass(tmp_path):
    """T9 r2 wording: the answer must report the Dallas, TX count (12)."""
    run_dir, _ = honest_run(tmp_path, 9)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = ("12 of the restaurants are in Dallas, TX. The Ross Avenue "
                            "restaurant's phone is (214) 515-9105. Order RC-100240, "
                            "total $128.81.")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(9, run_dir)
    assert out["pass"], f"Dallas-TX count answer must PASS: {out}"


def test_t9_literal_count_fail(tmp_path):
    """Pre-r2 reading: reporting the literal 13-result count (without the
    Dallas, TX count) no longer answers the re-anchored question -> FAIL."""
    run_dir, _ = honest_run(tmp_path, 9)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = ("The Dallas search with the Catering Delivery filter shows "
                            "13 restaurants. The Ross Avenue restaurant's phone is "
                            "(214) 515-9105. Order RC-100240, total $128.81.")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(9, run_dir)
    assert not out["pass"], f"literal 13-count-only answer must FAIL: {out}"
    assert out["reason"] == "answer_count"


def test_t11_old_slot_fail(tmp_path):
    """Pre-r2 anchor: an order placed at the old 4:45 PM wording (not an
    offered slot) must FAIL the re-anchored 5:00 PM requirement."""
    run_dir, _ = honest_run(tmp_path, 11)
    db = sqlite3.connect(str(run_dir / "after.db"))
    try:
        db.execute("UPDATE food_orders SET pickup_time='4:45 PM' "
                   "WHERE order_number='RC-100240'")
        db.commit()
    finally:
        db.close()
    out = run_verifier(11, run_dir)
    assert not out["pass"], f"4:45 PM order must FAIL: {out}"
    assert out["reason"] == "db_order_state"


def test_t12_wrong_plush_fail(tmp_path):
    """Pre-r2 anchor: buying a different plush puppy (30th Birthday, $12.99)
    instead of the named Cool Cane Barking Plush Puppy must FAIL."""
    run_dir, _ = honest_run(tmp_path, 12)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    for s in traj["steps"]:
        if "/gear/product/cool-cane-plush" in s.get("url", ""):
            s["url"] = s["url"].replace("/gear/product/cool-cane-plush",
                                       "/gear/product/30th-birthday-2026-plush-puppy")
    traj["final_answer"] = traj["final_answer"].replace(
        "Cool Cane Barking Plush Puppy $9.99", "30th Birthday 2026 Plush Puppy $12.99")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    db = sqlite3.connect(str(run_dir / "after.db"))
    try:
        db.execute("UPDATE gear_order_items SET product_id=8, price=12.99 "
                   "WHERE product_id=?", (GEAR_PLUSH,))
        db.commit()
    finally:
        db.close()
    out = run_verifier(12, run_dir)
    assert not out["pass"], f"wrong plush product must FAIL: {out}"


def test_t16_missing_points_fail(tmp_path):
    """Pre-r2 answer shape: number/restaurant/total reported but neither the
    returned points nor the after-balance -> FAIL (both sub-questions)."""
    run_dir, _ = honest_run(tmp_path, 16)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = ("Alice's most recent food order was RC-100236 at the "
                           "Houston Little York Road restaurant, total $52.71. It "
                           "has been cancelled.")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(16, run_dir)
    assert not out["pass"], f"answer without the points facts must FAIL: {out}"
    assert out["reason"] == "answer_points_returned"


def test_t16_no_points_rollback_fail(tmp_path):
    """Self-reported success + cancelled row, but the DB never rolled the
    points back (balance stays at the seed 1275) -> FAIL."""
    run_dir, _ = honest_run(tmp_path, 16)
    db = sqlite3.connect(str(run_dir / "after.db"))
    try:
        db.execute("UPDATE caniac_cards SET points=1275 WHERE user_id=?", (ALICE,))
        db.commit()
    finally:
        db.close()
    out = run_verifier(16, run_dir)
    assert not out["pass"], f"missing points rollback in DB must FAIL: {out}"
    assert out["reason"] == "db_points_after_cancel"


def test_t17_missing_reference_department_fail(tmp_path):
    """Pre-r2 answer shape: cities + street + cashier facts but no La Marque
    reference number / department -> FAIL."""
    run_dir, _ = honest_run(tmp_path, 17)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = ("Six Restaurant Manager jobs are currently open in Texas: "
                           "San Antonio, Cedar Park, Dallas, Katy, Houston and La "
                           "Marque. The La Marque opening is at 3001 FM 1764. The "
                           "Cashier opening on Polaris Parkway in Columbus, Ohio is "
                           "reference P1-1007372-17, Cashier - Late Night Shift.")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(17, run_dir)
    assert not out["pass"], f"missing reference/department must FAIL: {out}"
    assert out["reason"] == "answer_la_marque_reference"


def test_t17_wrong_city_fail(tmp_path):
    run_dir, _ = honest_run(tmp_path, 17)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = traj["final_answer"].replace("La Marque", "Beaumont")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(17, run_dir)
    assert not out["pass"], f"wrong city list must FAIL: {out}"
