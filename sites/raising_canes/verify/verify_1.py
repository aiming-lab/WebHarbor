#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--1.

Marcus: compare per-finger price of the 25/50/75/100-Finger Tailgates,
order the best-value one with family-style sauce for pickup at the
McKinney North Central Expressway restaurant. Prices $41.99/$79.99/
$118.99/$142.99 -> per finger $1.6796/$1.5998/$1.5865/$1.4299 -> best
value is the 100-Finger Tailgate; $142.99 + 8.25% tax = $154.79.

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
    j = Judge("Raising Cane's--1")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_tailgate_pages", navigated_to(t, "/menu/100-finger-tailgate"),
            "agent must open tailgate item pages to read prices")
    j.check("nav_item_page", navigated_to(t, "/order/location/tx_mckinney_1902-north-central-expressway/item/"),
            "expected item page at McKinney")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "100-finger-tailgate"
                   and abs(items[0][4] - 142.99) < 0.005
                   and "Family-Style" in items[0][3])
        if (abs(total - 154.79) < 0.005 and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no matching 100-Finger order")
    j.check("answer_per_finger", contains_number(fa, "1.42") or contains_number(fa, "1.43"),
            f"final={fa[:200]!r}")
    j.check("answer_number", contains_order_number(fa, "RC-"), f"final={fa[:150]!r}")
    j.check("answer_total", contains_money(fa, 154.79), f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
