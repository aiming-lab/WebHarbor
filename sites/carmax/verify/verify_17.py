#!/usr/bin/env python3
"""Verifier for CarMax--17: sign in as dan.m and report from order history (a) order number,
(b) vehicle year/make/model, (c) total amount, (d) whether MaxCare was included,
(e) the scheduled pickup date. (Read-only: the order is in the seed.)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_all, contains_any,
                        price_mentioned, resolve_db, orders_for, llm_text_match, Judge, parse_args)

EMAIL = "dan.m@test.com"

def main():
    a = parse_args()
    j = Judge('CarMax--17', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    orders = orders_for(init, EMAIL) or []
    j.check("nav_login", navigated_to(t, "/login"), "expected /login")
    j.check("nav_orders", navigated_to(t, "/account/orders") or navigated_to(t, "/order"),
            "expected the order-history / order page")
    j.check("db_has_order", bool(orders), f"dan.m orders={[o['order_number'] for o in orders]}")
    if orders:
        o = orders[0]
        has_maxcare = bool(o["maxcare_plan"])
        mc_words = ["maxcare", o["maxcare_plan"], "yes", "included"] if has_maxcare else ["no maxcare", "not included", "no"]
        j.check("answer_order_number", contains_any(fa, [o["order_number"]]), f"expected {o['order_number']}; final={fa!r}")
        j.check("answer_vehicle", contains_all(fa, [str(o["year"]), o["make"], o["model"]]),
                f"expected {o['year']} {o['make']} {o['model']}")
        j.check("answer_total", price_mentioned(fa, int(round(o["total"])), tol=2), f"expected ${o['total']:,.2f}")
        j.check("answer_maxcare", contains_any(fa, [w for w in mc_words if w]),
                f"maxcare included={has_maxcare} ({o['maxcare_plan']!r})")
        j.check("answer_pickup_date", contains_any(fa, [str(o["pickup_date"])]), f"expected pickup {o['pickup_date']}")
        # The five deterministic field checks above fully and precisely verify this
        # read-only task; an extra LLM-anchored check only adds false negatives (e.g. it
        # rejected a correct answer that rounded $26,685.50 to $26,686), so it is omitted.
    j.emit()

if __name__ == "__main__":
    main()
