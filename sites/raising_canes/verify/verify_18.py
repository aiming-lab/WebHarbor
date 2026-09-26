#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--18.

Alice: update profile phone to 504-555-0187, add address 'NOLA' at
500 St. Louis St, New Orleans, LA 70130, buy the Caniac Backpack
($29.99 + $6.95 shipping = $36.94) shipped to that address with Visa.

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
    j = Judge("Raising Cane's--18")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_login", navigated_to(t, "/login"), "agent must sign in as Alice")
    phone = user_phone(after, "alice.j@test.com")
    j.check("db_phone_updated", phone == "504-555-0187", f"phone={phone}")
    addrs = user_addresses(after, "alice.j@test.com")
    nola = any(a[0] == "NOLA" and "500 St. Louis St" in a[1]
               and a[2] == "New Orleans" and a[3] == "LA" and a[4] == "70130"
               for a in addrs)
    j.check("db_address_added", nola, f"addresses={addrs}")
    j.check("nav_backpack", navigated_to(t, "/gear/product/caniac-backpack"),
            "agent must open the Caniac Backpack product")
    rows = new_gear_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, email, sname, sline1, scity, sstate, szip, pay, sub, ship, total = r
        items = gear_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "caniac-backpack"
                   and abs(items[0][4] - 29.99) < 0.005)
        if (item_ok and "500 St. Louis St" in (sline1 or "") and scity == "New Orleans"
                and abs(total - 36.94) < 0.005 and "Visa" in pay):
            ok = True
            ev = [f"order={on} total={total:.2f} ship_to={sline1}"]
            break
    j.check("db_gear_order_state", ok, "; ".join(ev) or "no backpack order to NOLA")
    j.check("answer_phone", contains_number(fa, "504-555-0187"), f"final={fa[:150]!r}")
    j.check("answer_number_total", contains_order_number(fa, "GEAR-") and contains_money(fa, 36.94),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
