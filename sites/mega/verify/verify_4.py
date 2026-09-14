#!/usr/bin/env python3
"""MEGA--4: compare Pro II vs Business Pro users; cart Business Pro; no purchase."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms_any, final_answer, llm_text_match, load_run,
                        navigated_to, orders_for, parse_args, plan_row, resolve_db)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args()
    j = Judge("MEGA--4", a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ref = init or after
    j.bind_run(t, shot_url="/checkout")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_pro_ii", navigated_to(t, "/plans/pro-ii"), "opened Pro II")
    j.check("nav_business_pro", navigated_to(t, "/plans/business-pro"), "opened Business Pro")
    j.check("nav_checkout", navigated_to(t, "/checkout") or navigated_to(t, "/cart/add/business-pro"),
            "added Business Pro / reached checkout")
    pro_ii = plan_row(ref, "pro-ii")
    biz = plan_row(ref, "business-pro")
    j.check("db_users_business_more",
            pro_ii is not None and biz is not None and biz[4] > pro_ii[4],
            f"pro_ii_users={None if not pro_ii else pro_ii[4]} business={None if not biz else biz[4]}")
    j.check("answer_business_pro", affirms_any(fa, ["business pro"]), f"final={fa!r}")
    j.check("answer_five_users", affirms_any(fa, ["5", "five"]), f"final={fa!r}")
    before = orders_for(init, EMAIL) if init else None
    after_orders = orders_for(after, EMAIL) if after else None
    j.check("db_no_new_order", before is not None and after_orders is not None and len(after_orders) == len(before),
            f"orders seed={None if before is None else len(before)} after={None if after_orders is None else len(after_orders)}")
    ok, ev = llm_text_match(fa, "Business Pro includes more users (5) than Pro II (1).",
                            "Which plan includes more users, Pro II or Business Pro?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
