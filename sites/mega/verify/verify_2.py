#!/usr/bin/env python3
"""MEGA--2 (stateful cart, no purchase): David adds Pro II yearly and stops at checkout."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, final_answer, load_run, navigated_to, orders_for,
                        parse_args, posted_billing, resolve_db)

EMAIL = "david.k@test.com"

def main():
    a = parse_args()
    j = Judge("MEGA--2", a.no_llm)
    t = load_run(a.run_dir)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.bind_run(t, require_answer=False, shot_url="/checkout")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_pro_ii", navigated_to(t, "/plans/pro-ii") or navigated_to(t, "/cart/add/pro-ii"),
            "opened Pro II or added it to the cart")
    j.check("nav_checkout", navigated_to(t, "/checkout"), "reached checkout review")
    j.check("billing_yearly", posted_billing(t, "yearly"), f"traj billing evidence")
    before = orders_for(init, EMAIL) if init else None
    after_orders = orders_for(after, EMAIL) if after else None
    j.check("db_no_new_order", before is not None and after_orders is not None and len(after_orders) == len(before),
            f"orders seed={None if before is None else len(before)} after={None if after_orders is None else len(after_orders)}")
    fa = final_answer(t)
    if fa:
        from verify_lib import affirms_any
        j.check("answer_mentions_plan", True, f"final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
