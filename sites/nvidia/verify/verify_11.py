#!/usr/bin/env python3
"""NVIDIA--11: sign in as alice, add the RTX 5080 to cart, and check out to place the order.
Deterministic-first: nav to /checkout | DB after-state: alice has a NEW order and one of her
orders contains the RTX 5080.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, orders_for, Judge, parse_args)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args(); j = Judge('NVIDIA--11', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    ao, io = orders_for(after, EMAIL), orders_for(init, EMAIL)
    j.check("nav_checkout", navigated_to(t, "/checkout"), "expected the checkout flow")
    j.check("db_order_created", ao is not None and io is not None and len(ao) > len(io),
            f"orders after={None if ao is None else len(ao)} vs initial={None if io is None else len(io)}")
    has = bool(ao) and any("geforce-rtx-5080" in [s for s, _ in o["items"]] for o in ao)
    j.check("db_order_has_5080", has, "a placed order must contain the RTX 5080")
    j.emit()

if __name__ == "__main__":
    main()
