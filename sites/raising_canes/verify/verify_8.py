#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--8.

Jordan: 21 Houston restaurants offer Curbside Pickup (Locations search
'Houston' + Curbside Pickup filter). Order one Box Combo for curbside
pickup today 6:30 PM at Little York Road: $11.89 + 8.25% = $12.87.

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
    j = Judge("Raising Cane's--8")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_locations_filter", navigated_to(t, "/locations/?q=Houston")
            and navigated_to(t, "service=Curbside+Pickup"),
            "agent must filter Houston locations by Curbside Pickup")
    j.check("nav_item_page", navigated_to(t, "/order/location/tx_houston_4055-little-york-rd/item/"),
            "expected Box Combo item page at Little York")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "the-box-combo"
                   and items[0][2] == "1" and abs(items[0][4] - 11.89) < 0.005)
        if (mode == "Curbside" and pdate == "2026-09-24" and ptime == "6:30 PM"
                and cname == "Jordan Ellis" and cphone == "832-555-0146"
                and pay == "Pay at Restaurant" and abs(total - 12.87) < 0.005
                and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no matching order")
    j.check("answer_count", contains_number(fa, 21), f"final={fa[:150]!r}")
    j.check("answer_number_total", contains_order_number(fa, "RC-") and contains_money(fa, 12.87),
            f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
