#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--3.

David: check the gift card on file ($75.00), spend part of it on a
25-Finger Tailgate at the Westheimer Road Houston restaurant. $41.99 +
8.25% tax = $45.45; remaining balance $29.55.

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
    j = Judge("Raising Cane's--3")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_login", navigated_to(t, "/login"), "agent must sign in as David")
    j.check("nav_account", navigated_to(t, "/account"), "agent must read the gift card on file")
    j.check("nav_item_page", navigated_to(t, "/order/location/tx_houston_12201-westheimer-rd/item/"),
            "expected 25-Finger item page at Westheimer")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "25-finger-tailgate"
                   and abs(items[0][4] - 41.99) < 0.005)
        if (pay == "Gift Card" and gcnum and abs(total - 45.45) < 0.005 and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f} gc={gcnum}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no gift-card-paid 25-Finger order")
    bal = gift_card_balance(after, gcnum) if ok else None
    j.check("db_remaining_balance", bal is not None and abs(bal - 29.55) < 0.005,
            f"balance={bal}")
    j.check("answer_number", contains_order_number(fa, "RC-"), f"final={fa[:150]!r}")
    j.check("answer_remaining", contains_money(fa, 29.55), f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
