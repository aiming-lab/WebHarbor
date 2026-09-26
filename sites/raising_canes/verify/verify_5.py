#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--5.

Teacher: confirm Kids Combo calories from the nutrition page (640 for
the national Kid's Combo), order 50 Kids Combos with milk ($339.50 +
8.25% tax = $367.51) for pickup today 3:00 PM at the Goleta Hollister
Ave restaurant, under Ms. Rivera (805-555-0123), pay at restaurant.

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
    j = Judge("Raising Cane's--5")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_nutrition", navigated_to(t, "/allergens"),
            "agent must open the nutritional information page")
    j.check("nav_item_page", navigated_to(t, "/order/location/ca_goleta_7000-hollister-ave/item/"),
            "expected Kids Combo item page at Goleta")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "the-kids-combo"
                   and items[0][2] == "50" and abs(items[0][4] - 339.50) < 0.005
                   and "Milk" in items[0][3])
        if (pdate == "2026-09-24" and ptime == "3:00 PM"
                and cname == "Ms. Rivera" and cphone == "805-555-0123"
                and pay == "Pay at Restaurant" and abs(total - 367.51) < 0.005
                and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no matching order")
    j.check("answer_calories", contains_number(fa, 640), f"final={fa[:150]!r}")
    j.check("answer_number", contains_order_number(fa, "RC-"), f"final={fa[:150]!r}")
    j.check("answer_total", contains_money(fa, 367.51), f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
