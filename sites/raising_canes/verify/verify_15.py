#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--15.

Carol: register physical Caniac card 8823112233445566, then use her
TAILGATE-10 members-only offer ($10 off Tailgates $75+) on a 75-Finger
Tailgate for pickup tomorrow 5:30 PM at McKinney North Central
Expressway, saved Discover. $118.99 - $10.00 + 8.25% tax on $108.99
= $117.98.

Ground truth is HARDCODED below (independently verified against the live
mirror + upstream on 2026-09-24). Deterministic only: trajectory navigation,
SQLite after-state, and answer text checks. No LLM calls.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, parse_args, load_run, final_answer, navigated_to,
                        contains_order_number,
                        navigated_any, contains_all, contains_any, contains_money,
                        contains_number, resolve_db, db_query, food_orders,
                        food_order_items, new_food_orders, new_gear_orders,
                        gear_order_items, gear_orders, gift_card_balance,
                        caniac_points, user_phone, user_addresses)


def main():
    a = parse_args()
    j = Judge("Raising Cane's--15")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_login", navigated_to(t, "/login"), "agent must sign in as Carol")
    j.check("nav_caniac", navigated_to(t, "/caniac-club"),
            "agent must register the card on the Caniac Club page")
    card = db_query(after, "SELECT card_number, points FROM caniac_cards cc "
                    "JOIN users u ON u.id=cc.user_id WHERE u.email=?",
                    ("carol.d@test.com",))
    j.check("db_card_registered", card and card[0][0] == "8823112233445566",
            f"card={card}")
    j.check("nav_item_page", navigated_to(t, "/order/location/tx_mckinney_1902-north-central-expressway/item/"),
            "expected 75-Finger item page at McKinney")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "75-finger-tailgate"
                   and abs(items[0][4] - 118.99) < 0.005
                   and "Family-Style" in items[0][3])
        if (offer == "TAILGATE-10" and abs(disc - 10.00) < 0.005
                and pdate == "2026-09-25" and ptime == "5:30 PM"
                and "Discover" in pay and abs(total - 117.98) < 0.005 and item_ok):
            ok = True
            ev = [f"order={on} discount={disc:.2f} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no TAILGATE-10 order")
    j.check("answer_discount", contains_money(fa, 10.00), f"final={fa[:150]!r}")
    j.check("answer_number_total", contains_order_number(fa, "RC-") and contains_money(fa, 117.98),
            f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
