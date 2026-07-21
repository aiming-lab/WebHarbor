#!/usr/bin/env python3
"""Deterministic verifier for Target--10 (stateful: add to cart).

Sign in as carol.d@test.com, add the ProsourceFit Extra Thick Yoga and Pilates
Mat to the cart, then report the cart subtotal.

Ground truth (frozen here, never read from tasks.jsonl):
  SKU TGT91151386 ($29.99). carol.d starts with a $378.97 subtotal, so the
  subtotal afterwards is $408.96.

The task asks for the SUBTOTAL, not the item count: the header already shows a
cart count, so a count question would have been answerable without opening the
cart at all. The subtotal is recomputed from the DB rather than hardcoded, so
the check still holds if the seed's starting cart changes.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product,
                        navigated_to, has_money, resolve_db, cart_skus, cart_for,
                        db_query, llm_screenshot_shows, Judge, parse_args)

EMAIL = "carol.d@test.com"
SKU = "TGT91151386"


def main():
    a = parse_args()
    j = Judge("Target--10", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("opened_product_page", visited_product(t, SKU),
            f"visited /product/{SKU}={visited_product(t, SKU)}")
    j.check("opened_cart", navigated_to(t, "/cart"),
            f"visited_cart={navigated_to(t, '/cart')}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    before_skus = cart_skus(initial, EMAIL)
    after_skus = cart_skus(after, EMAIL)

    j.check("db_readable", before_skus is not None and after_skus is not None,
            f"before={before_skus} after={after_skus}")

    # Subtotal = sum(price * quantity) over the after-state cart.
    subtotal_after = 0.0
    if after is not None:
        for sku, _name, qty in (cart_for(after, EMAIL) or []):
            row = db_query(after, "SELECT price FROM products WHERE sku=?", (sku,))
            if row:
                subtotal_after += row[0][0] * qty
    subtotal_after = round(subtotal_after, 2)

    if before_skus is not None and after_skus is not None:
        j.check("product_now_in_cart", SKU in after_skus,
                f"cart after={after_skus}")
        j.check("cart_grew_by_one", len(after_skus) == len(before_skus) + 1,
                f"before={len(before_skus)} after={len(after_skus)}")
        # Nothing else should have been added or removed along the way.
        j.check("no_other_cart_changes",
                set(after_skus) - set(before_skus) == {SKU} and
                not set(before_skus) - set(after_skus),
                f"added={set(after_skus)-set(before_skus)} removed={set(before_skus)-set(after_skus)}")
        j.check("answer_reports_subtotal", has_money(fa, subtotal_after),
                f"expected subtotal={subtotal_after:.2f} final={fa!r}")
    else:
        for name in ("product_now_in_cart", "cart_grew_by_one",
                     "no_other_cart_changes", "answer_reports_subtotal"):
            j.check(name, False, "DB unavailable")

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the yoga mat in the shopping cart",
                                      "the cart contents after adding the item")
        j.check("screenshot_shows_cart", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_cart", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
