#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--10.

Sam: Box Combo sodium 2360 mg vs Caniac Combo sodium 3480 mg (nutrition
page); lower-sodium = Box Combo; calorie difference |1810-1270| = 540.
Order the Box Combo with a Regular Sweet Tea today 1:15 PM at Siegen
Lane: $11.89 + 8.25% tax = $12.87.

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
    j = Judge("Raising Cane's--10")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_nutrition", navigated_to(t, "/allergens"),
            "agent must open the nutritional information page")
    j.check("nav_item_page", navigated_to(t, "/order/location/la_baton-rouge_6588-siegen-lane/item/"),
            "expected Box Combo item page at Siegen Lane")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "the-box-combo"
                   and items[0][2] == "1" and abs(items[0][4] - 11.89) < 0.005
                   and "Sweet Tea" in items[0][3])
        if (pdate == "2026-09-24" and ptime == "1:15 PM"
                and cname == "Sam Whitfield" and cphone == "225-555-0162"
                and pay == "Pay at Restaurant" and abs(total - 12.87) < 0.005
                and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no matching order")
    j.check("answer_sodium", contains_number(fa, 2360) and contains_number(fa, 3480),
            f"final={fa[:200]!r}")
    j.check("answer_calorie_diff", contains_number(fa, 540), f"final={fa[:150]!r}")
    j.check("answer_total", contains_money(fa, 12.87), f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
