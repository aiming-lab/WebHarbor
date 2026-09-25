#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--0.

Maya: 25 Box Combos, no coleslaw, Large Sweet Tea for everyone; curbside
pickup tomorrow 5:15 PM at the Little York Road Houston restaurant, under
Maya Torres (713-555-0184), paying at the restaurant. Report order number
and total. 25 x $297.25 + $6.75 large-tea delta = $304.00 + 8.25% tax =
$329.08.

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
    j = Judge("Raising Cane's--0")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_item_page", navigated_to(t, "/order/location/tx_houston_4055-little-york-rd/item/"),
            "expected Box Combo item page at Little York")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        want = {"the-box-combo": ("25", 304.00)}
        item_ok = (len(items) == 1 and items[0][0] == "the-box-combo"
                   and items[0][2] == "25"
                   and abs(items[0][4] - 304.00) < 0.005
                   and "No Slaw (NSL)" in items[0][3] and "Large Sweet Tea" in items[0][3])
        if (mode == "Curbside" and pdate == "2026-09-25" and ptime == "5:15 PM"
                and cname == "Maya Torres" and cphone == "713-555-0184"
                and pay == "Pay at Restaurant" and abs(total - 329.08) < 0.005
                and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no matching new order row")
    j.check("answer_number", contains_order_number(fa, "RC-"), f"final={fa[:150]!r}")
    j.check("answer_total", contains_money(fa, 329.08), f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
