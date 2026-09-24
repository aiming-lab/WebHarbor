#!/usr/bin/env python3
"""Verify Michaels--1.

David wants the Buy One Get One FREE mix & match frame promo: find two qualifying
Studio Decor shadow boxes or display cases he likes, add both to david.k@test.com's
cart, complete the order with store pickup and his saved Discover card, and report
the BOGO discount amount, the order number and the order total.

Frozen ground truth (seed DB): Flat White Deep Profile Shadow Box $17.49 + Mini
Helmet Display Case $12.49 (both promo_type b1g1_free). David's seed cart
(6" Glitter Tulle @4.99 + 2x 8x10 Double Mat @6.49 = $17.97). Subtotal $47.95;
BOGO free discount = cheaper unit $12.49 (mix & match, sorted desc, every 2nd
free); pickup -> no shipping; tax 9.25% of $35.46 = $3.28; total $38.74.
Order number MI26092304002 (user 04, 2nd order). Discover ****6442, pickup at
445 N Canyons Pkwy, Livermore, CA 94551 (david's home store).
"""
from verify_lib import (Judge, added_order_matching, check_answer_order_matches_added_order,
                        check_only_tables_changed, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, final_answer,
                        navigated_confirmation, navigated_product, navigated_search,
                        order_items_of, run_verifier, wrong_amount_claim_absent)

TASK_ID = "Michaels--1"
SB_SLUG = "10-x-10-flat-white-deep-profile-shadow-box-by-studio-d-cor-10739210"
CASE_SLUG = "mini-helmet-display-case-by-studio-d-cor-10403379"
ORDER_NUMBER = "MI26092304002"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: both qualifying items' PDPs, sign-in, cart, checkout, confirmation
    judge.check("searched_shadow_box", navigated_search(traj, "shadow box"),
                "required: /search?q=...shadow box")
    judge.check("searched_display_case", navigated_search(traj, "display case"),
                "required: /search?q=...display case")
    judge.check("visited_shadow_box_pdp", navigated_product(traj, SB_SLUG),
                f"required: /product/{SB_SLUG}")
    judge.check("visited_display_case_pdp", navigated_product(traj, CASE_SLUG),
                f"required: /product/{CASE_SLUG}")
    check_signed_in_as(judge, traj, "david.k@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    check_visited_path(judge, traj, "visited_checkout", "/checkout")
    judge.check("visited_confirmation", navigated_confirmation(traj, ORDER_NUMBER),
                f"required: /order/confirmation/{ORDER_NUMBER}")
    # answer: BOGO discount + order number + total
    judge.check("answer_bogo_discount", contains_amount(answer, 12.49),
                "expected BOGO discount $12.49")
    judge.check("answer_bogo_discount_claim", wrong_amount_claim_absent(answer, 12.49),
                "the BOGO discount claim must not contradict the expected $12.49")
    judge.check("answer_order_total", contains_amount(answer, 38.74),
                "expected order total $38.74")
    # DB after-state: exactly one order added with the task's math
    added = added_order_matching(after_db, initial_db,
                                 order_number=ORDER_NUMBER, user_id=4, status="Processing",
                                 delivery_method="Pickup",
                                 address_line="445 N Canyons Pkwy, Livermore, CA 94551",
                                 card_brand="Discover", card_last4="6442",
                                 subtotal=47.95, discount=12.49, shipping=0.0,
                                 tax=3.28, total=38.74, promo_code="")
    judge.check("added_order_row", added is not None, f"expected added order row; found={added!r}")
    check_answer_order_matches_added_order(judge, answer, added, "order")
    items = order_items_of(after_db, added["id"]) if added else []
    judge.check("added_order_items",
                len(items) == 4 and
                any("Shadow Box" in i["name"] and i["unit_price"] == 17.49 for i in items) and
                any("Mini Helmet Display Case" in i["name"] and i["unit_price"] == 12.49 for i in items),
                f"expected 4 order items incl. shadow box + display case; found={items!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("cart_items", "orders", "order_items"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
