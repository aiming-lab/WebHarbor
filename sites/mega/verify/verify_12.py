#!/usr/bin/env python3
"""MEGA--12: Bob adds S4 Fixed Storage (S3-compatible API) and stops at checkout."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, load_run, navigated_to, orders_for, parse_args,
                        resolve_db)

EMAIL = "bob.c@test.com"

def main():
    a = parse_args()
    j = Judge("MEGA--12", a.no_llm)
    t = load_run(a.run_dir)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.bind_run(t, require_answer=False, shot_url="/checkout")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_pricing_objectstorage", navigated_to(t, "category=objectstorage"),
            "applied the object storage pricing filter")
    j.check("nav_s4_fixed",
            navigated_to(t, "/plans/s4-fixed-storage") or navigated_to(t, "/cart/add/s4-fixed-storage"),
            "opened/added the S3-compatible S4 Fixed Storage plan")
    j.check("nav_checkout", navigated_to(t, "/checkout"), "reached checkout")
    before = orders_for(init, EMAIL) if init else None
    after_orders = orders_for(after, EMAIL) if after else None
    j.check("db_no_new_order", before is not None and after_orders is not None and len(after_orders) == len(before),
            f"orders seed={None if before is None else len(before)} after={None if after_orders is None else len(after_orders)}")
    j.emit()

if __name__ == "__main__":
    main()
