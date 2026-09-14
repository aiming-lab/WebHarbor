#!/usr/bin/env python3
"""MEGA--17: Bob compares Pro Flexi vs S4 Fixed, carts Pro Flexi yearly, no purchase."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, load_run, navigated_to, orders_for, parse_args,
                        posted_billing, resolve_db)

EMAIL = "bob.c@test.com"

def main():
    a = parse_args()
    j = Judge("MEGA--17", a.no_llm)
    t = load_run(a.run_dir)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.bind_run(t, require_answer=False, shot_url="/checkout")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_flexi", navigated_to(t, "/plans/pro-flexi") or navigated_to(t, "/cart/add/pro-flexi"),
            "opened/added Pro Flexi")
    j.check("nav_s4_fixed", navigated_to(t, "/plans/s4-fixed-storage"),
            "opened the fixed S4 storage plan for comparison")
    j.check("nav_checkout", navigated_to(t, "/checkout"), "reached checkout")
    j.check("billing_yearly", posted_billing(t, "yearly"), "yearly billing selected")
    before = orders_for(init, EMAIL) if init else None
    after_orders = orders_for(after, EMAIL) if after else None
    j.check("db_no_new_order", before is not None and after_orders is not None and len(after_orders) == len(before),
            f"orders seed={None if before is None else len(before)} after={None if after_orders is None else len(after_orders)}")
    j.emit()

if __name__ == "__main__":
    main()
