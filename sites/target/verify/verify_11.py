#!/usr/bin/env python3
"""Deterministic verifier for Target--11 (stateful: full checkout).

Sign in as bob.c@test.com, add the Tide Ultra Oxi Boost detergent to the cart,
complete checkout with delivery to 123 Main St, Denver, CO 80202, and report
the order number from the confirmation page.

Ground truth: SKU TGT94640332 (Tide Ultra Oxi Boost HE Deep Cleaning
Concentrated Liquid Laundry Detergent). The order number is NOT fixed — it is allocated at checkout — so
the check is that a NEW order row exists for this user containing that SKU,
and that the number the agent reported is the one that actually landed in the
DB. That closes the obvious cheat: claiming a plausible order number without
completing the flow.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product,
                        navigated_to, contains_any, resolve_db, new_orders,
                        order_items, llm_screenshot_shows, Judge, parse_args)

EMAIL = "bob.c@test.com"
SKU = "TGT94640332"


def main():
    a = parse_args()
    j = Judge("Target--11", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("opened_product_page", visited_product(t, SKU),
            f"visited /product/{SKU}={visited_product(t, SKU)}")
    j.check("reached_confirmation", navigated_to(t, "/checkout/confirmation"),
            f"confirmation_visited={navigated_to(t, '/checkout/confirmation')}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    created = new_orders(initial, after, EMAIL)

    j.check("db_has_new_order", bool(created),
            f"new orders for {EMAIL}: {created}")

    if created:
        # Exactly one new order, and it must contain the requested product.
        j.check("exactly_one_new_order", len(created) == 1,
                f"count={len(created)}")
        number = created[0][0]
        items = order_items(after, number) or []
        j.check("order_contains_product", any(r[0] == SKU for r in items),
                f"order {number} items={items}")
        # The reported number must be the one the DB actually recorded.
        j.check("answer_reports_real_order_number", number.lower() in (fa or "").lower(),
                f"db_order={number} final={fa!r}")
        j.check("order_is_delivery", created[0][3] == "delivery",
                f"fulfillment={created[0][3]}")
    else:
        for name in ("exactly_one_new_order", "order_contains_product",
                     "answer_reports_real_order_number", "order_is_delivery"):
            j.check(name, False, "no new order was created")

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "an order confirmation with an order number",
            "the checkout confirmation page")
        j.check("screenshot_shows_confirmation", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_confirmation", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
