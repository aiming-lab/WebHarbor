#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--11.

Superfan: Cane's Sauce via site search; 190 calories per serving (1.5 oz),
allergen letters ESF (Eggs, Soy, Fish). Order 25 servings ($11.25 +
8.25% tax = $12.18) at the Government Street restaurant. The r2 task
wording anchors pickup today at 5:00 PM — an offered checkout slot —
so the placed order must carry exactly that slot.

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
    j = Judge("Raising Cane's--11")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_search", navigated_to(t, "/search"), "agent must use the site search")
    j.check("nav_sauce_item", navigated_to(t, "/menu/canes-sauce"),
            "agent must open the Cane's Sauce menu item")
    j.check("nav_nutrition", navigated_to(t, "/allergens"),
            "agent must open the nutrition page for calories/allergens")
    j.check("nav_item_page", navigated_to(t, "/order/location/la_baton-rouge_5020-government-st./item/"),
            "expected Cane's Sauce item page at Government St")
    rows = new_food_orders(after)
    ok, ev = False, []
    for r in rows:
        on, uid, loc, mode, pdate, ptime, cname, cphone, pay, gcnum, offer, sub, disc, tax, total, status = r
        items = food_order_items(after, on)
        item_ok = (len(items) == 1 and items[0][0] == "canes-sauce"
                   and items[0][2] == "25" and abs(items[0][4] - 11.25) < 0.005)
        if (cname == "Dana Lopez" and cphone == "225-555-0131"
                and ptime == "5:00 PM"
                and pay == "Pay at Restaurant" and abs(total - 12.18) < 0.005
                and item_ok):
            ok = True
            ev = [f"order={on} total={total:.2f} time={ptime}"]
            break
    j.check("db_order_state", ok, "; ".join(ev) or "no matching order")
    j.check("answer_calories", contains_number(fa, 190), f"final={fa[:150]!r}")
    j.check("answer_allergens", contains_all(fa, ["E", "S", "F"]) or "esf" in fa.casefold(),
            f"final={fa[:150]!r}")
    j.check("answer_number_total", contains_order_number(fa, "RC-") and contains_money(fa, 12.18),
            f"final={fa[:150]!r}")
    j.emit()

if __name__ == "__main__":
    main()
