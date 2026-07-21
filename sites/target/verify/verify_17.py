#!/usr/bin/env python3
"""Deterministic verifier for Target--17 (stateful: pickup checkout).

Sign in as bob.c@test.com, add TWO Colgate Total Active Prevention Whitening
Toothpaste to the cart, complete checkout as a store pickup order at the
Denver Stapleton store, and report the order number and pickup slot.

Ground truth (frozen here, never read from tasks.jsonl):
  SKU TGT1012287965; pickup store slug "denver-stapleton"; the task names the
  slot explicitly, so the booked window must be "9:00 AM - 11:00 AM".

Two design notes:

* The task places the order rather than stopping at the pickup step. Checkout
  state lives in the session, so a run that stops early leaves no database
  trace of which store was chosen; placing the order writes store_id onto the
  order row, which makes the store binding checkable.
* The task names the pickup time instead of letting the agent choose one.
  Every store offers the SAME five windows, so "whichever slot you picked" was
  only weakly checkable — and an agent could book the right-looking time at the
  wrong store. With the slot fixed, store and time are both exact matches.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product,
                        navigated_to, norm, resolve_db, db_query, new_orders,
                        order_items, llm_screenshot_shows, Judge, parse_args)

EMAIL = "bob.c@test.com"
SKU = "TGT1012287965"
STORE_SLUG = "denver-stapleton"
SLOT = "9:00 AM - 11:00 AM"


def main():
    a = parse_args()
    j = Judge("Target--17", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("opened_product_page", visited_product(t, SKU),
            f"visited /product/{SKU}={visited_product(t, SKU)}")
    j.check("reached_pickup_step", navigated_to(t, "/checkout/pickup"),
            f"visited={navigated_to(t, '/checkout/pickup')}")
    j.check("reached_confirmation", navigated_to(t, "/checkout/confirmation"),
            f"visited={navigated_to(t, '/checkout/confirmation')}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    created = new_orders(initial, after, EMAIL)

    j.check("db_has_new_order", bool(created), f"new orders for {EMAIL}: {created}")

    if created:
        j.check("exactly_one_new_order", len(created) == 1, f"count={len(created)}")
        number, _status, _total, fulfilment = created[0]

        j.check("order_is_pickup", fulfilment == "pickup",
                f"fulfillment={fulfilment}")

        # The store binding is the whole point — same slot labels everywhere.
        rows = db_query(after,
            "SELECT s.slug, o.pickup_slot_label FROM orders o "
            "LEFT JOIN stores s ON s.id = o.store_id WHERE o.order_number = ?", (number,))
        slug, slot_label = (rows[0] if rows else (None, None))
        j.check("pickup_store_is_denver_stapleton", slug == STORE_SLUG,
                f"order store={slug!r} (expected {STORE_SLUG!r})")

        items = order_items(after, number) or []
        row = next((r for r in items if r[0] == SKU), None)
        j.check("order_contains_product", row is not None, f"order items={items}")
        j.check("quantity_is_two", bool(row) and row[2] == 2,
                f"row={row} (expected quantity 2)")

        j.check("answer_reports_real_order_number",
                number.lower() in (fa or "").lower(),
                f"db_order={number} final={fa!r}")
        # The task dictates the window, so this is an exact match rather than
        # "any slot this store offers".
        j.check("booked_the_requested_slot",
                bool(slot_label) and norm(slot_label) == norm(SLOT),
                f"order slot={slot_label!r} (task asked for {SLOT!r})")
    else:
        for name in ("exactly_one_new_order", "order_is_pickup",
                     "pickup_store_is_denver_stapleton", "order_contains_product",
                     "quantity_is_two", "answer_reports_real_order_number",
                     "booked_the_requested_slot"):
            j.check(name, False, "no new order was created")

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "a pickup order confirmation with an order number and a pickup time",
                                      "the checkout confirmation page")
        j.check("screenshot_shows_confirmation", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_confirmation", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
