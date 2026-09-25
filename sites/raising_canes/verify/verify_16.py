#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--16.

Alice: cancel her most recent food order. Most recent = RC-100236
(placed 2026-09-20, Curbside at the Little York Road Houston
restaurant, total $52.71). After cancellation its status is Cancelled.
The r2 task wording adds two sub-questions: the cancellation returns
the order's earned points (+52 shown on the order detail page) and
Alice's Caniac Club balance drops 1275 -> 1223 (account page).

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
    j = Judge("Raising Cane's--16")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_login", navigated_to(t, "/login"), "agent must sign in as Alice")
    j.check("nav_order_detail", navigated_to(t, "/orders/RC-100236"),
            "agent must open the most recent order detail")
    j.check("nav_account", navigated_to(t, "/account"),
            "agent must open the account page for the points balance")
    rows = db_query(after, "SELECT order_number, status, total FROM food_orders "
                    "WHERE order_number='RC-100236'")
    j.check("db_cancelled", rows and rows[0][1] == "Cancelled",
            f"row={rows}")
    pts = caniac_points(after, "alice.j@test.com")
    j.check("db_points_after_cancel", pts == 1223,
            f"alice points={pts} (1275 seed - 52 returned)")
    j.check("answer_number", contains_number(fa, "100236"), f"final={fa[:150]!r}")
    j.check("answer_restaurant", contains_any(fa, ["Houston", "Little York"]),
            f"final={fa[:150]!r}")
    j.check("answer_total", contains_money(fa, 52.71), f"final={fa[:150]!r}")
    j.check("answer_points_returned",
            re.search(r"(?<![0-9.])\+?52(?![0-9.])", fa) is not None,
            f"final={fa[:150]!r} (points returned by the cancellation, not the "
            "$52.71 total)")
    j.check("answer_points_balance", contains_number(fa, 1223),
            f"final={fa[:150]!r} (Caniac Club balance afterwards)")
    j.emit()

if __name__ == "__main__":
    main()
