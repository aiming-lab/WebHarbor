#!/usr/bin/env python3
"""Verify Michaels--14.

Bob's twins want the National Geographic Metal Detector Starter Kit and the
Snap Circuits Explorer 100 Experiments for their birthday. Michaels is running
a Buy One Get One 50% off mix & match promo on these. Add both to Bob's cart
(bob.c@test.com) and report the BOGO discount line and the new order total
shown in the cart summary.

Frozen ground truth (seed DB): Metal Detector $50.99 + Snap Circuits $33.74
(both promo_type b1g1_50). Bob's seed cart $23.96 + $84.73 = $108.69
subtotal; BOGO 50% discount = 50% of the cheaper unit $33.74 = $16.87;
$91.82 >= $49 -> free shipping; tax 9.25% = $8.49; order total $100.31.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        final_answer, navigated_product, navigated_search, run_verifier)

TASK_ID = "Michaels--14"
MD_SLUG = "national-geographic-metal-detector-starter-kit-10758215"
SC_SLUG = "snap-circuits-explorer-100-experiments-10567231"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: both PDPs + sign-in + cart
    judge.check("searched_metal_detector", navigated_search(traj, "Metal Detector"),
                "required: a metal detector search")
    judge.check("searched_snap_circuits", navigated_search(traj, "Snap Circuits"),
                "required: a snap circuits search")
    judge.check("visited_md_pdp", navigated_product(traj, MD_SLUG),
                f"required: /product/{MD_SLUG}")
    judge.check("visited_sc_pdp", navigated_product(traj, SC_SLUG),
                f"required: /product/{SC_SLUG}")
    check_signed_in_as(judge, traj, "bob.c@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    # answer: BOGO discount + new order total
    judge.check("answer_bogo_discount", contains_amount(answer, 16.87),
                "expected BOGO discount $16.87")
    judge.check("answer_new_total", contains_amount(answer, 100.31),
                "expected new order total $100.31")
    # DB after-state: two cart rows added (bob, products 307 + 329)
    before = {(r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"])
              for r in __import__("verify_lib").cart_of_raw(initial_db)}
    added = [r for r in __import__("verify_lib").cart_of_raw(after_db)
             if (r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"]) not in before]
    judge.check("added_cart_rows",
                len(added) == 2 and {r["product_id"] for r in added} == {307, 329} and
                all(r["user_id"] == 2 and r["qty"] == 1 for r in added),
                f"expected two added cart rows (user 2, products 307+329); found={added!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("cart_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
