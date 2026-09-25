#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--14.

Carol: graduation-themed gift card in the $25 denomination, shipped to
her McKinney home address, saved Discover.
GROUND TRUTH assumes the variant-price fix (gear product form currently
submits the product's minimum variant price regardless of the selected
denomination — see review A-2). Post-fix expectation: $25.00 + $6.95
shipping = $31.95. Until A-2 is fixed the site itself produces $11.95,
which fails this verifier — correctly, since the task is unanswerable
as intended.

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
    j = Judge("Raising Cane's--14")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_login", navigated_to(t, "/login"), "agent must sign in as Carol")
    j.check("nav_giftcard", navigated_to(t, "/gear/product/graduation-gift-card"),
            "agent must open the graduation gift card product")
    rows = new_gear_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, email, sname, sline1, scity, sstate, szip, pay, sub, ship, total = r
        items = gear_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "graduation-gift-card"
                   and items[0][2] == "$25" and abs(items[0][4] - 25.00) < 0.005)
        if (item_ok and abs(ship - 6.95) < 0.005 and abs(total - 31.95) < 0.005
                and "Discover" in pay and "McKinney" in (scity or "")):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_gear_order_state", ok, "; ".join(ev) or "no matching $25 gift-card order")
    j.check("answer_number_total", contains_order_number(fa, "GEAR-") and contains_money(fa, 31.95),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
