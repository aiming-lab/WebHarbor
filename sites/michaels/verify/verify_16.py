#!/usr/bin/env python3
"""Verify Michaels--16.

Bob is upgrading his craft room and comparing Cricut bundles: compare the
Cricut Joy 2 in Jade Green & Essential Bundle with the Cricut Explore 5 in
Teal & Essential Bundle — report each price and rating. Then add the one with
the higher rating to Bob's cart and report the new cart subtotal.

Frozen ground truth (seed DB): Cricut Joy 2 $139.00, rating 4.7 (129
reviews); Cricut Explore 5 $249.00, rating 4.2 (116). The Joy 2 has the
higher rating. Bob's seed cart $23.96 + $139.00 = new subtotal $162.96.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_all,
                        contains_amount, contains_phrase, final_answer, navigated_product,
                        navigated_search, run_verifier)

TASK_ID = "Michaels--16"
JOY_SLUG = "cricut-joy-2-in-jade-green-essential-bundle-10815288"
EXPLORE_SLUG = "cricut-explore-5-in-teal-essential-bundle-with-digital-content-10816737"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: both bundle PDPs + sign-in + cart
    judge.check("searched_cricut", navigated_search(traj, "Cricut"),
                "required: a Cricut search")
    judge.check("visited_joy_pdp", navigated_product(traj, JOY_SLUG),
                f"required: /product/{JOY_SLUG}")
    judge.check("visited_explore_pdp", navigated_product(traj, EXPLORE_SLUG),
                f"required: /product/{EXPLORE_SLUG}")
    check_signed_in_as(judge, traj, "bob.c@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    # answer: both prices + ratings + winner + new subtotal
    judge.check("answer_joy_price", contains_amount(answer, 139.00),
                "expected Joy 2 price $139.00")
    judge.check("answer_joy_rating", contains_phrase(answer, "4.7"),
                "expected Joy 2 rating 4.7")
    judge.check("answer_explore_price", contains_amount(answer, 249.00),
                "expected Explore 5 price $249.00")
    judge.check("answer_explore_rating", contains_phrase(answer, "4.2"),
                "expected Explore 5 rating 4.2")
    judge.check("answer_joy_added", contains_all(answer, ["Joy", "added"]) or
                contains_phrase(answer, "Joy 2"),
                "expected: the Joy 2 (higher rating) added")
    judge.check("answer_new_subtotal", contains_amount(answer, 162.96),
                "expected new cart subtotal $162.96")
    # DB after-state: one cart row added (bob, product 218, qty 1)
    before = {(r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"])
              for r in __import__("verify_lib").cart_of_raw(initial_db)}
    added = [r for r in __import__("verify_lib").cart_of_raw(after_db)
             if (r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"]) not in before]
    judge.check("added_cart_row",
                len(added) == 1 and added[0]["user_id"] == 2 and
                added[0]["product_id"] == 218 and added[0]["qty"] == 1,
                f"expected one added cart row (user 2, product 218); found={added!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("cart_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
