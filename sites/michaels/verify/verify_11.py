#!/usr/bin/env python3
"""Verify Michaels--11.

David is styling a wedding arch on a tight budget and wants filler bushes he can pick up today. Find the cheapest floral item available for Store Pickup, add three of them to his cart (david.k@test.com / TestPass123!), and report the item name, its price each, and the new cart subtotal. Leave the order unplaced.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_phrase, final_answer, navigated_product, navigated_shop,
                        run_verifier)

TASK_ID = "Michaels--11"
DAHLIA_SLUG = "15-mauve-pale-pink-dahlia-mix-bush-by-ashland-10811002"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the floral listing with pickup filter + price sort, the
    # winner's PDP, sign-in, cart
    judge.check("visited_floral_listing", navigated_shop(traj, "floral"),
                "required: /shop/floral")
    judge.check("filtered_pickup", navigated_shop(traj, "floral", params={"availability": "pickup"}),
                "required: /shop/floral?availability=pickup")
    judge.check("sorted_price_low", navigated_shop(traj, "floral", params={"sort": "price_low"}),
                "required: /shop/floral?sort=price_low")
    judge.check("visited_dahlia_pdp", navigated_product(traj, DAHLIA_SLUG),
                f"required: /product/{DAHLIA_SLUG}")
    check_signed_in_as(judge, traj, "david.k@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    # answer: name + price each + new subtotal
    judge.check("answer_item_name", contains_phrase(answer, "Dahlia Mix Bush"),
                "expected the Dahlia Mix Bush named")
    judge.check("answer_price_each", contains_amount(answer, 5.19),
                "expected price each $5.19")
    judge.check("answer_new_subtotal", contains_amount(answer, 33.54),
                "expected new subtotal $33.54")
    # DB after-state: one cart row added (david, product 49, qty 3)
    before = {(r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"])
              for r in __import__("verify_lib").cart_of_raw(initial_db)}
    added = [r for r in __import__("verify_lib").cart_of_raw(after_db)
             if (r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"]) not in before]
    judge.check("added_cart_row",
                len(added) == 1 and added[0]["user_id"] == 4 and
                added[0]["product_id"] == 49 and added[0]["qty"] == 3,
                f"expected one added cart row (user 4, product 49, qty 3); found={added!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("cart_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
