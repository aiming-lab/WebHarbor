#!/usr/bin/env python3
"""Deterministic verifier for Target--12 (stateful: add to wish list).

Sign in as alice.j@test.com, add the Colgate Total Active Prevention Whitening
Toothpaste to the wish list, then report the item shown at the BOTTOM of it.

Ground truth (frozen here, never read from tasks.jsonl):
  SKU TGT1012287965 (the toothpaste being added).
  The wish list renders newest-first, so the bottom row is the OLDEST entry:
  TGT84640745, "Organic Mini Sandwich Cheddar Cheese Crackers - 8oz/8ct".
  The newly added toothpaste lands at the TOP, not the bottom.

The task asks for the bottom item rather than a count: the account page already
prints "Wishlist items N", so a count question would have been answerable
without opening the list. Naming the bottom row requires reading it.

The wish-list route is a TOGGLE, so a double submit would silently undo the
add. Asserting the final membership plus an exact +1 delta catches that.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product,
                        navigated_to, contains_any, resolve_db, wishlist_skus,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"
SKU = "TGT1012287965"
BOTTOM_SKU = "TGT84640745"


def main():
    a = parse_args()
    j = Judge("Target--12", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("opened_product_page", visited_product(t, SKU),
            f"visited /product/{SKU}={visited_product(t, SKU)}")
    j.check("opened_wishlist", navigated_to(t, "/account/wishlist"),
            f"visited={navigated_to(t, '/account/wishlist')}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    before = wishlist_skus(initial, EMAIL)
    now = wishlist_skus(after, EMAIL)

    j.check("db_readable", before is not None and now is not None,
            f"before={before} after={now}")

    if before is not None and now is not None:
        j.check("product_on_wishlist", SKU in now, f"wishlist after={now}")
        j.check("wishlist_grew_by_one", len(now) == len(before) + 1,
                f"before={len(before)} after={len(now)} "
                f"(a toggled-twice run lands back at {len(before)})")
        j.check("nothing_else_removed", not set(before) - set(now),
                f"removed={set(before)-set(now)}")
        j.check("answer_names_bottom_item",
                contains_any(fa, ["organic mini sandwich", "cheddar cheese crackers"]),
                f"expected the oldest entry ({BOTTOM_SKU}) final={fa!r}")
        # Naming the item it just added means the list was never read.
        j.check("did_not_name_the_added_item",
                not contains_any(fa, ["colgate"]) or
                contains_any(fa, ["organic mini sandwich", "cheddar cheese crackers"]),
                f"final={fa!r}")
    else:
        for name in ("product_on_wishlist", "wishlist_grew_by_one",
                     "nothing_else_removed", "answer_names_bottom_item",
                     "did_not_name_the_added_item"):
            j.check(name, False, "DB unavailable")

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the toothpaste on the wish list",
                                      "the wish list after adding the item")
        j.check("screenshot_shows_wishlist", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_wishlist", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
