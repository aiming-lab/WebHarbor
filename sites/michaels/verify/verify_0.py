#!/usr/bin/env python3
"""Verify Michaels--0.

Alice is restocking her studio and needs two 16" x 20" canvases. Compare the single (non-multipack) Artist's Loft® Level 3 Gallery Wrapped Heavy Duty Canvas with the Level 1 Back Stapled Canvas at that size, including price and rating. Buy two of the cheaper 16" x 20" canvas for Alice (alice.j@test.com / TestPass123!) with the online 30% off promo code from the Savings page, shipping to her home address, paying with her saved Visa ending 4242. Keep the items already in the cart as part of this order. Report the order number and the order total.
"""
from verify_lib import (Judge, added_order_matching, check_answer_order_matches_added_order,
                        check_only_tables_changed, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_count, contains_phrase,
                        final_answer, navigated_confirmation, navigated_product, navigated_search,
                        order_items_of, run_verifier)

TASK_ID = "Michaels--0"
L3_SLUG = "level-3-gallery-wrapped-heavy-duty-canvas-by-artist-s-loft-10472532"
L1_SLUG = "level-1-back-stapled-canvas-by-artist-s-loft-10672808"
ORDER_NUMBER = "MI26092301003"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: both comparison PDPs, sign-in, the cheaper product re-visited,
    # cart with promo, checkout, confirmation
    judge.check("searched_canvas", navigated_search(traj, "canvas"),
                "required: /search?q=...canvas")
    judge.check("visited_l3_pdp", navigated_product(traj, L3_SLUG),
                f"required: /product/{L3_SLUG}")
    judge.check("visited_l1_pdp", navigated_product(traj, L1_SLUG),
                f"required: /product/{L1_SLUG}")
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    check_visited_path(judge, traj, "visited_checkout", "/checkout")
    judge.check("visited_confirmation", navigated_confirmation(traj, ORDER_NUMBER),
                f"required: /order/confirmation/{ORDER_NUMBER}")
    # answer: comparison facts + order number + total
    judge.check("answer_l1_cheaper", contains_phrase(answer, "Level 1") and
                contains_amount(answer, 15.99),
                "expected: Level 1 Back Stapled named as the cheaper 16x20 at $15.99")
    judge.check("answer_l3_price", contains_amount(answer, 32.99),
                "expected: Level 3 16x20 price $32.99 in the comparison")
    judge.check("answer_order_total", contains_amount(answer, 68.30),
                "expected order total $68.30")
    # DB after-state: exactly one order added with the task's math, its items,
    # and the seed cart consumed
    added = added_order_matching(after_db, initial_db,
                                 order_number=ORDER_NUMBER, user_id=1, status="Processing",
                                 delivery_method="Ship",
                                 address_line="1420 Rainier Ave S, Seattle, WA 98144",
                                 card_brand="Visa", card_last4="4242",
                                 subtotal=89.32, discount=26.80, shipping=0.0,
                                 tax=5.78, total=68.30, promo_code="GETMY30")
    judge.check("added_order_row", added is not None, f"expected added order row; found={added!r}")
    check_answer_order_matches_added_order(judge, answer, added, "order")
    items = order_items_of(after_db, added["id"]) if added else []
    judge.check("added_order_items",
                len(items) == 4 and contains_count(" ".join(i["name"] for i in items),
                                                   0) is False and
                any("Level 1 Back Stapled" in i["name"] and i["qty"] == 2 and i["unit_price"] == 15.99
                    and i["variant_sku"] == "10672550" for i in items),
                f"expected 4 order items incl. 2x Level 1 Back Stapled 16x20; found={items!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("cart_items", "orders", "order_items"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
