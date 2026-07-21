#!/usr/bin/env python3
"""Deterministic verifier for Target--14 (stateful: remove a named wish-list item).

Sign in as alice.j@test.com, remove the named Starbucks ground coffee from the
wish list, and report which items remain on it.

Ground truth (frozen here, never read from tasks.jsonl):
  SKU TGT12954143 (Starbucks Medium Roast Ground Coffee — Colombia).
  alice.j starts with 4 wish-list rows -> 3 remain.

The task names the item explicitly. An earlier version said "remove an item"
and graded on whether the agent asked which one — CONTRIBUTING rejects tasks
that presuppose a human in the loop, so the ambiguity was removed and the
grading moved onto the database instead.

Removing the WRONG item is the failure this is built to catch: the count would
still be 3 and a text-only check would pass it.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, navigated_to,
                        contains_any, resolve_db, wishlist_skus,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"
SKU = "TGT12954143"


def main():
    a = parse_args()
    j = Judge("Target--14", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("opened_wishlist", navigated_to(t, "/account/wishlist"),
            f"visited={navigated_to(t, '/account/wishlist')}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    before = wishlist_skus(initial, EMAIL)
    now = wishlist_skus(after, EMAIL)

    j.check("db_readable", before is not None and now is not None,
            f"before={before} after={now}")

    if before is not None and now is not None:
        j.check("named_item_removed", SKU not in now, f"wishlist after={now}")
        # Only that one may be gone — removing a different item would leave the
        # same count and slip past a count-only check.
        removed = set(before) - set(now)
        j.check("only_named_item_removed", removed == {SKU},
                f"removed={removed or 'nothing'} (expected exactly {{{SKU}}})")
        j.check("nothing_added", not set(now) - set(before),
                f"added={set(now)-set(before)}")
        # Naming what remains requires reading the list; the account page's
        # "Wishlist items N" tile would have satisfied a count question.
        remaining_terms = [["katie"], ["cinnamon toast crunch", "cinnamon"],
                           ["organic mini sandwich", "cheddar cheese crackers"]]
        named = sum(1 for terms in remaining_terms if contains_any(fa, terms))
        j.check("answer_names_remaining_items", named >= 2,
                f"named {named}/3 remaining items: final={fa!r}")
        j.check("did_not_claim_removed_item_remains",
                not contains_any(fa, ["starbucks"]),
                f"answer still lists the removed item: final={fa!r}")
    else:
        for name in ("named_item_removed", "only_named_item_removed",
                     "nothing_added", "answer_names_remaining_items",
                     "did_not_claim_removed_item_remains"):
            j.check(name, False, "DB unavailable")

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "a wish list that no longer lists the Starbucks ground coffee",
                                      "the wish list after the removal")
        j.check("screenshot_shows_wishlist", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_wishlist", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
