#!/usr/bin/env python3
"""Deterministic verifier for raising_canes task Raising Cane's--17.

Alex: every currently open Restaurant Manager job in Texas (6 jobs:
San Antonio, Cedar Park, Dallas, Katy, Houston, La Marque); the r2
task wording requires OPENING the La Marque job detail page and
reporting its street address (3001 FM 1764), its reference number
(744000151697368) and its department (Management). The Cashier opening
on Polaris Parkway in Columbus OH is reference P1-1007372-17, 'Cashier -
Late Night Shift' (shift noted in the title: Late Night).

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
    j = Judge("Raising Cane's--17")
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")

    j.check("nav_careers_search", navigated_to(t, "/careers/?q=Restaurant+Manager")
            or (navigated_to(t, "/careers/?q=Restaurant") and navigated_to(t, "state=TX")),
            "agent must search Restaurant Manager jobs in Texas")
    j.check("nav_la_marque_job", navigated_to(t, "/careers/744000151697368"),
            "agent must open the La Marque Restaurant Manager job detail")
    j.check("nav_cashier_job", navigated_to(t, "/careers/P1-1007372-17"),
            "agent must open the Polaris Parkway Cashier job")
    j.check("answer_tx_count", contains_number(fa, 6) or "six" in fa.casefold(), f"final={fa[:150]!r}")
    j.check("answer_cities", contains_all(fa, ["San Antonio", "Cedar Park", "Dallas",
                                               "Katy", "Houston", "La Marque"]),
            f"final={fa[:300]!r}")
    j.check("answer_la_marque_street", contains_all(fa, ["3001 FM 1764"]),
            f"final={fa[:200]!r}")
    j.check("answer_la_marque_reference", contains_number(fa, "744000151697368"),
            f"final={fa[:200]!r}")
    j.check("answer_la_marque_department", "management" in fa.casefold(),
            f"final={fa[:200]!r}")
    j.check("answer_reference", contains_number(fa, "1007372") and contains_number(fa, "17"), f"final={fa[:200]!r}")
    j.check("answer_shift", "late night" in fa.casefold(), f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
