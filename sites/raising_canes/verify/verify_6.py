#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--6.

Alice: reorder her most recent order (RC-100236: Caniac Combo x1 No Slaw
Large Coke $16.89 + Texas Toast x25 $34.50) for curbside pickup tomorrow
1:30 PM at the same Little York restaurant, saved Visa.
$51.39 + 8.25% tax = $55.63.

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
    j = Judge("Raising Cane's--6")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_login", navigated_to(t, "/login"), "agent must sign in as Alice")
    j.check("nav_order_detail", navigated_to(t, "/orders/RC-100236"),
            "agent must open the most recent order detail")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        caniac = [i for i in items if i[0] == "the-caniac-combo"]
        toast = [i for i in items if i[0] == "texas-toast"]
        item_ok = (len(items) == 2 and len(caniac) == 1 and len(toast) == 1
                   and caniac[0][2] == "1" and abs(caniac[0][4] - 16.89) < 0.005
                   and "No Slaw (NSL)" in caniac[0][3] and "Large Coke" in caniac[0][3]
                   and toast[0][2] == "25" and abs(toast[0][4] - 34.50) < 0.005)
        if (mode == "Curbside" and pdate == "2026-09-25" and ptime == "1:30 PM"
                and "Visa" in pay and abs(total - 55.63) < 0.005 and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no matching reorder")
    j.check("answer_number", contains_order_number(fa, "RC-"), f"final={fa[:150]!r}")
    j.check("answer_total", contains_money(fa, 55.63), f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
