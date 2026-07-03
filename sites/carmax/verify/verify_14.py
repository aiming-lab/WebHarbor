#!/usr/bin/env python3
"""Verifier for CarMax--14: sign in as carol.l, identify her active appraisal, then buy a
2022 Honda CR-V applying that appraisal as a trade-in, CarMax Auto Finance, 60-month term,
$3,000 down, 6.49% APR, no MaxCare; place the order and report the order number and total.

Deterministic-first: DB after-state: carol has a NEW order for a 2022 Honda CR-V with the
trade-in value applied, no MaxCare, 60-mo/6.49%/$3000-down; her appraisal is redeemed |
answer contains the order number and total.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any, price_mentioned,
                        resolve_db, orders_for, appraisals_for, Judge, parse_args)

EMAIL = "carol.l@test.com"

def main():
    a = parse_args()
    j = Judge('CarMax--14', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    ao = orders_for(after, EMAIL) or []
    io = orders_for(init, EMAIL) or []
    new_orders = [o for o in ao if o["order_number"] not in {x["order_number"] for x in io}]
    crv = [o for o in new_orders if o["make"] == "Honda" and o["model"] == "CR-V" and o["year"] == 2022]
    j.check("nav_checkout", navigated_to(t, "/checkout") or navigated_to(t, "/vehicle"),
            "expected a /checkout flow")
    j.check("db_new_crv_order", bool(crv), f"new orders={[o['order_number'] for o in new_orders]}")
    if crv:
        o = crv[-1]
        j.check("order_trade_in_applied", (o["trade_in_value"] or 0) > 0,
                f"trade_in_value={o['trade_in_value']}")
        j.check("order_no_maxcare", (o["maxcare_plan"] or "") == "", f"maxcare_plan={o['maxcare_plan']!r}")
        j.check("order_terms", int(o["payment_term_months"] or 0) == 60 and abs((o["payment_apr"] or 0) - 6.49) < 0.01
                and abs((o["down_payment"] or 0) - 3000) < 1,
                f"term={o['payment_term_months']} apr={o['payment_apr']} down={o['down_payment']}")
        j.check("answer_order_number", contains_any(fa, [o["order_number"]]),
                f"expected {o['order_number']}; final={fa!r}")
        j.check("answer_total", price_mentioned(fa, int(round(o["total"])), tol=2),
                f"expected total ${o['total']:,.2f}")
    # appraisal should be redeemed after the trade-in
    act_after = appraisals_for(after, EMAIL, "active") or []
    j.check("appraisal_redeemed", len(act_after) == 0,
            f"carol should have 0 active appraisals after trade-in; got {act_after}")
    j.emit()

if __name__ == "__main__":
    main()
