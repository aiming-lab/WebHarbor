#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--7.

Priya: the Baton Rouge restaurant whose drive-thru closes EARLIEST on
Friday nights is 3422 Drusilla Ln (9:00 AM - 11:00 PM Friday drive-thru;
phone (225) 924-7505). Order a 50-Finger Tailgate there for Saturday
pickup 6:00 PM: $79.99 + 8.25% tax = $86.59.

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
    j = Judge("Raising Cane's--7")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_locations_search", navigated_to(t, "/locations/?q=Baton+Rouge")
            or navigated_to(t, "/locations/?q=baton+rouge"),
            "agent must search Baton Rouge locations")
    j.check("nav_drusilla", navigated_to(t, "/locations/la_baton-rouge_3422-drusilla-ln"),
            "agent must open the Drusilla Ln location page")
    j.check("nav_item_page", navigated_to(t, "/order/location/la_baton-rouge_3422-drusilla-ln/item/"),
            "expected 50-Finger item page at Drusilla")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "50-finger-tailgate"
                   and abs(items[0][4] - 79.99) < 0.005
                   and "Family-Style" in items[0][3])
        if (pdate == "2026-09-26" and ptime == "6:00 PM"
                and cname == "Priya Patel" and cphone == "225-555-0177"
                and pay == "Pay at Restaurant" and abs(total - 86.59) < 0.005
                and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no matching order")
    j.check("answer_address", contains_all(fa, ["3422 Drusilla"]), f"final={fa[:200]!r}")
    j.check("answer_phone", contains_number(fa, "225") and contains_number(fa, "924-7505"),
            f"final={fa[:200]!r}")
    j.check("answer_hours", contains_all(fa, ["11:00 PM"]) or "11 pm" in fa.casefold()
            or "2300" in fa, f"final={fa[:200]!r}")
    j.check("answer_number_total", contains_order_number(fa, "RC-") and contains_money(fa, 86.59),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
