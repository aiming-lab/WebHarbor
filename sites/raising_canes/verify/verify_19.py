#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--19.

Researcher: FAQ lists Restaurant Support Offices in Baton Rouge
(Headquarters, 100 North St. Suite 802) and Plano (Dallas-Area Support
Office, 6800 Bishop Road, phone (972) 769-3100). Then order a Caniac
Combo with a Large Coke for pickup today 2:00 PM at Siegen Lane under
R. Okafor: $16.89 + 8.25% tax = $18.28.

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
    j = Judge("Raising Cane's--19")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_faq", navigated_to(t, "/faq"), "agent must search the FAQ")
    j.check("answer_cities", contains_all(fa, ["Baton Rouge", "Plano"]),
            f"final={fa[:200]!r}")
    j.check("answer_dallas_phone", contains_number(fa, "769-3100"), f"final={fa[:200]!r}")
    j.check("nav_item_page", navigated_to(t, "/order/location/la_baton-rouge_6588-siegen-lane/item/"),
            "expected Caniac Combo item page at Siegen Lane")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "the-caniac-combo"
                   and items[0][2] == "1" and abs(items[0][4] - 16.89) < 0.005
                   and "Large Coke" in items[0][3])
        if (pdate == "2026-09-24" and ptime == "2:00 PM"
                and cname == "R. Okafor" and cphone == "225-555-0158"
                and pay == "Pay at Restaurant" and abs(total - 18.28) < 0.005
                and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no matching order")
    j.check("answer_number_total", contains_order_number(fa, "RC-") and contains_money(fa, 18.28),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
