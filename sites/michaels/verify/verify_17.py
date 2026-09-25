#!/usr/bin/env python3
"""Verify Michaels--17.

Carol heard the single (non-multipack) Level 3 Gallery Wrapped Heavy Duty Canvas is for serious painters. Using only its product page: does the description confirm archival-quality natural cotton and gesso priming? What is the largest size sold and its exact price? Which aisle at Parkway Supercenter stocks it? Then add the largest size to Carol's cart (carol.d@test.com / TestPass123!) and report the new cart subtotal.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_any, contains_phrase, final_answer, navigated_product,
                        navigated_search, run_verifier)

TASK_ID = "Michaels--17"
L3_SLUG = "level-3-gallery-wrapped-heavy-duty-canvas-by-artist-s-loft-10472532"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the L3 PDP (pre and post sign-in) + cart
    judge.check("searched_l3", navigated_search(traj, "Level 3"),
                "required: a Level 3 search")
    judge.check("visited_l3_pdp", navigated_product(traj, L3_SLUG),
                f"required: /product/{L3_SLUG}")
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    # answer: description confirmation + largest price + aisle + new subtotal
    judge.check("answer_cotton", contains_any(answer, ["archival", "natural cotton"]),
                "expected: description confirms archival-quality natural cotton")
    judge.check("answer_gesso", contains_phrase(answer, "gesso"),
                "expected: description confirms gesso priming")
    judge.check("answer_largest_price", contains_amount(answer, 109.99),
                "expected largest size (48x48) price $109.99")
    judge.check("answer_aisle", contains_phrase(answer, "Aisle 14"),
                "expected Aisle 14 at Parkway Supercenter")
    judge.check("answer_new_subtotal", contains_amount(answer, 154.40),
                "expected new subtotal $154.40")
    # DB after-state: one cart row added (carol, product 294, 48x48, qty 1)
    before = {(r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"])
              for r in __import__("verify_lib").cart_of_raw(initial_db)}
    added = [r for r in __import__("verify_lib").cart_of_raw(after_db)
             if (r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"]) not in before]
    judge.check("added_cart_row",
                len(added) == 1 and added[0]["user_id"] == 3 and
                added[0]["product_id"] == 294 and added[0]["variant_sku"] == "10472520" and
                added[0]["color"] == '48" x 48"' and added[0]["qty"] == 1,
                f"expected one added cart row (user 3, product 294, 48x48); found={added!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("cart_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
