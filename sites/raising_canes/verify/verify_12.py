#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--12.

Alice: Retro Crewneck size M ($39.99) + the Cool Cane Barking Plush
Puppy ($9.99, handle cool-cane-plush — the r2 task names the exact
product) = $49.98 < $50 free-shipping threshold, so add the cheapest
accessory (CANIAC Pet Bandana $4.99) -> $54.97 with FREE shipping.
Gear order GEAR-4504, total $54.97.

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
    j = Judge("Raising Cane's--12")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_login", navigated_to(t, "/login"), "agent must sign in as Alice")
    j.check("nav_crewneck", navigated_to(t, "/gear/product/raising-canes-retro-crewneck"),
            "agent must open the Retro Crewneck product")
    j.check("nav_plush", navigated_to(t, "/gear/product/cool-cane-plush"),
            "agent must open the named Cool Cane Barking Plush Puppy product")
    rows = new_gear_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, email, sname, sline1, scity, sstate, szip, pay, sub, ship, total = r
        items = gear_order_items(after, on)
        has_crewneck = any(i[0] == "raising-canes-retro-crewneck" and i[2] == "M" for i in items)
        has_plush = any(i[0] == "cool-cane-plush" for i in items)
        if (has_crewneck and has_plush and abs(total - 54.97) < 0.005
                and abs(ship - 0.0) < 0.005 and "Visa" in pay):
            ok = True
            ev = [f"order={on} total={total:.2f} items={[(i[0], i[2], i[4]) for i in items]}"]
            break
    j.check("db_gear_order_state", ok, "; ".join(ev) or "no matching gear order")
    j.check("answer_items", contains_all(fa, ["Retro Crewneck"]) and
            (contains_any(fa, ["Plush Puppy", "plush"])), f"final={fa[:250]!r}")
    j.check("answer_total", contains_money(fa, 54.97), f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
