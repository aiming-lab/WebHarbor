#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--9.

Renee: Locations search 'Dallas' + Catering Delivery filter. The literal
search shows 13 restaurants, but the r2 task wording asks how many of
them are in Dallas, TX = 12 (the 13th is the Waxahachie '1600 Dallas
Hwy' street-name match). The Ross Avenue restaurant is 5201 Ross Ave,
(214) 515-9105. Order a 75-Finger Tailgate with family-style sauce
today 5:00 PM there: $118.99 + 8.25% tax = $128.81.

Ground truth is HARDCODED below (independently verified against the live
mirror + upstream on 2026-09-24/25). Deterministic only: trajectory
navigation, SQLite after-state, and answer text checks. No LLM calls.
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
    j = Judge("Raising Cane's--9")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_locations_filter", navigated_to(t, "/locations/?q=Dallas")
            and navigated_to(t, "service=Catering+Delivery"),
            "agent must filter Dallas locations by Catering Delivery")
    j.check("nav_ross", navigated_to(t, "/locations/tx_dallas_5201-ross-ave"),
            "agent must open the Ross Ave location page")
    j.check("nav_item_page", navigated_to(t, "/order/location/tx_dallas_5201-ross-ave/item/"),
            "expected 75-Finger item page at Ross Ave")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "75-finger-tailgate"
                   and abs(items[0][4] - 118.99) < 0.005
                   and "Family-Style" in items[0][3])
        if (pdate == "2026-09-24" and ptime == "5:00 PM"
                and cname == "Renee Carter" and cphone == "214-555-0119"
                and pay == "Pay at Restaurant" and abs(total - 128.81) < 0.005
                and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no matching order")
    j.check("answer_count", contains_number(fa, 12),
            f"final={fa[:150]!r} (restaurants in Dallas, TX; the literal 13-result "
            "count is the pre-r2 wording and no longer answers the question)")
    j.check("answer_phone", contains_number(fa, "515-9105"), f"final={fa[:150]!r}")
    j.check("answer_number_total", contains_order_number(fa, "RC-") and contains_money(fa, 128.81),
            f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
