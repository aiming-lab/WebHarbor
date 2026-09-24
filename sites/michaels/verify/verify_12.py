#!/usr/bin/env python3
"""Verify Michaels--12.

David wants to show his team where their display board order stands: find his
most recent order and report its order number, current status, the item with
its color and quantity, and the card that was charged. Then start a reorder of
that display board in White and report the updated cart total.

Frozen ground truth (seed DB): david's most recent order MI2609220404001
(2026-09-22, Processing, Pickup, Visa ****4242, total $6.54): 1 x 36" x 48"
Corrugated Tri-Fold Display Board (Black) @5.99. Reorder in White -> new cart
row; david's seed cart $17.97 + $5.99 = $23.96 subtotal; shipping $5.99;
tax $2.22; cart total $32.17.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_all,
                        contains_amount, contains_phrase, final_answer, navigated_account_order,
                        navigated_product, navigated_search, run_verifier)

TASK_ID = "Michaels--12"
ORDER_NUMBER = "MI2609220404001"
BOARD_SLUG = "36-x-48-corrugated-tri-fold-display-board-10061591"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: sign-in, account, the order detail, the board PDP, cart
    check_signed_in_as(judge, traj, "david.k@test.com")
    check_visited_path(judge, traj, "visited_account", "/account")
    judge.check("visited_order_detail", navigated_account_order(traj, ORDER_NUMBER),
                f"required: /account/order/{ORDER_NUMBER}")
    judge.check("searched_board", navigated_search(traj, "Display Board"),
                "required: a display board search")
    judge.check("visited_board_pdp", navigated_product(traj, BOARD_SLUG),
                f"required: /product/{BOARD_SLUG}")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    # answer: order facts + updated cart total
    judge.check("answer_order_number", contains_phrase(answer, ORDER_NUMBER),
                f"expected order number {ORDER_NUMBER}")
    judge.check("answer_status", contains_phrase(answer, "Processing"),
                "expected status Processing")
    judge.check("answer_item", contains_phrase(answer, "Display Board") and
                contains_phrase(answer, "Black"),
                "expected the display board in Black")
    judge.check("answer_card", contains_all(answer, ["Visa", "4242"]),
                "expected Visa ****4242")
    judge.check("answer_cart_total", contains_amount(answer, 32.17),
                "expected updated cart total $32.17")
    # DB after-state: one cart row added (david, product 91, White, qty 1)
    before = {(r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"])
              for r in __import__("verify_lib").cart_of_raw(initial_db)}
    added = [r for r in __import__("verify_lib").cart_of_raw(after_db)
             if (r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"]) not in before]
    judge.check("added_cart_row",
                len(added) == 1 and added[0]["user_id"] == 4 and
                added[0]["product_id"] == 91 and added[0]["variant_sku"] == "10061591" and
                added[0]["color"] == "White" and added[0]["qty"] == 1,
                f"expected one added cart row (user 4, product 91, White); found={added!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("cart_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
