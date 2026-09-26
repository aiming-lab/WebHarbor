#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--13.

Carol: cheapest adult (non-youth) hat = Oak Leaf Trucker Hat $21.99
(youth hats are $19.99 but excluded). Shipped to her McKinney home
address with Discover: $21.99 + $6.95 shipping = $28.94.
NOTE: /gear/collection/Headwear currently renders 0 products (seed maps
Shopify product_type 'Hats' to collection 'Hats'); the hats are reachable
via site search. This verifier anchors on the hat + price + total and
does not require the (broken) collection page.

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
    j = Judge("Raising Cane's--13")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_login", navigated_to(t, "/login"), "agent must sign in as Carol")
    j.check("nav_hat", navigated_to(t, "/gear/product/oakleaf-trucker-hat"),
            "agent must open the Oak Leaf Trucker Hat product")
    rows = new_gear_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, email, sname, sline1, scity, sstate, szip, pay, sub, ship, total = r
        items = gear_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "oakleaf-trucker-hat"
                   and abs(items[0][4] - 21.99) < 0.005)
        if (item_ok and abs(ship - 6.95) < 0.005 and abs(total - 28.94) < 0.005
                and "Discover" in pay and "McKinney" in (scity or "")):
            ok = True
            ev = [f"order={on} total={total:.2f}"]
            break
    j.check("db_gear_order_state", ok, "; ".join(ev) or "no matching gear order")
    j.check("answer_hat", contains_all(fa, ["Oak Leaf Trucker Hat"]), f"final={fa[:200]!r}")
    j.check("answer_number_total", contains_order_number(fa, "GEAR-") and contains_money(fa, 28.94),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
