#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--2.

Alice birthday offer: free Box Combo at the Siegen Lane restaurant,
pickup today 12:15 PM, saved Visa. BDAY-BOX = $11.89 off the $11.89
Box Combo -> subtotal $11.89 - $11.89 = $0.00, tax $0.00, total $0.00.
Alice's Caniac points stay 1275 (int($0.00) earned).

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
    j = Judge("Raising Cane's--2")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_login", navigated_to(t, "/login"), "agent must sign in as Alice")
    j.check("nav_item_page", navigated_to(t, "/order/location/la_baton-rouge_6588-siegen-lane/item/"),
            "expected Box Combo item page at Siegen Lane")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "the-box-combo"
                   and abs(items[0][4] - 11.89) < 0.005)
        if (offer == "BDAY-BOX" and abs(disc - 11.89) < 0.005
                and abs(total - 0.00) < 0.005 and item_ok
                and ptime == "12:15 PM" and "Visa" in pay):
            ok = True
            ev = [f"order={on} discount={disc:.2f} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no BDAY-BOX order with $0.00 total")
    pts = caniac_points(after, "alice.j@test.com")
    j.check("db_points", pts is not None and abs(pts - 1275) < 0.5, f"points={pts}")
    j.check("answer_total", contains_money(fa, 0.00) or "$0" in fa,
            f"final={fa[:150]!r}")
    j.check("answer_points", contains_number(fa, 1275), f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
