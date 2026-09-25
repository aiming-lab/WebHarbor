#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--4.

Bob: 25 of the 3 Finger Combo with no fountain drinks (-$20.00 at qty 25)
+ one jug sweet tea ($5.99), tomorrow 12:30 PM at Little York Road,
saved Visa. $247.25 - $20.00 + $5.99 = $233.24 + 8.25% tax = $252.48.

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
    j = Judge("Raising Cane's--4")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_login", navigated_to(t, "/login"), "agent must sign in as Bob")
    j.check("nav_item_page", navigated_to(t, "/order/location/tx_houston_4055-little-york-rd/item/"),
            "expected item pages at Little York")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        combo = [i for i in items if i[0] == "the-3-finger-combo"]
        jug = [i for i in items if i[0] == "jug-sweet-tea"]
        item_ok = (len(items) == 2 and len(combo) == 1 and len(jug) == 1
                   and combo[0][2] == "25" and abs(combo[0][4] - 227.25) < 0.005
                   and "No Drink" in combo[0][3] and abs(jug[0][4] - 5.99) < 0.005)
        if (pdate == "2026-09-25" and ptime == "12:30 PM" and "Visa" in pay
                and abs(total - 252.48) < 0.005 and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no matching order")
    j.check("answer_number", contains_order_number(fa, "RC-"), f"final={fa[:150]!r}")
    j.check("answer_total", contains_money(fa, 252.48), f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
