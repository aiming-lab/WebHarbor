#!/usr/bin/env python3
"""MEGA--3 (stateful): Alice completes Pro I monthly checkout with default card."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, load_run, navigated_to, orders_for, parse_args,
                        plan_row, posted_billing, resolve_db)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args()
    j = Judge("MEGA--3", a.no_llm)
    t = load_run(a.run_dir)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.bind_run(t, require_answer=False, shot_url="/orders/")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_pro_i", navigated_to(t, "/plans/pro-i") or navigated_to(t, "/cart/add/pro-i"),
            "opened or added Pro I")
    j.check("nav_checkout", navigated_to(t, "/checkout") or navigated_to(t, "/orders/"),
            "checkout or order confirmation")
    plan = plan_row(after or init, "pro-i")
    j.check("db_plan", plan is not None, f"pro-i={plan!r}")
    before = orders_for(init, EMAIL) if init else None
    after_orders = orders_for(after, EMAIL) if after else None
    new = []
    if before is not None and after_orders is not None:
        before_ids = {row[0] for row in before}
        new = [row for row in after_orders if row[0] not in before_ids]
    j.check("db_new_order", len(new) == 1, f"new_orders={new!r}")
    if new:
        _oid, _num, cycle, _seats, plan_id, slug, status = new[0]
        j.check("order_plan", slug == "pro-i" or (plan and plan_id == plan[0]), f"slug={slug} plan_id={plan_id}")
        j.check("order_monthly", cycle == "monthly", f"billing={cycle}")
        j.check("order_active", status == "active", f"status={status}")
    elif posted_billing(t, "monthly"):
        j.check("order_monthly", False, "no new order to confirm monthly billing")
    j.emit()

if __name__ == "__main__":
    main()
