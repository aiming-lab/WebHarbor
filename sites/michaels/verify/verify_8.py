#!/usr/bin/env python3
"""Verify Michaels--8.

Michaels sells canvas multipacks: a 5 Pack of 16" x 20" Super Value Canvas and a 10 Pack of 8" x 10" Super Value Canvas, both by Artist's Loft®. Work out which pack gives more canvas area per dollar and show the math briefly. Then add the better-value pack to Alice's cart (alice.j@test.com / TestPass123!) without checking out, and report which pack won.
"""
from verify_lib import (Judge, cart_qty_change, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_any, contains_phrase, final_answer, navigated_product,
                        navigated_search, run_verifier, winner_named)

TASK_ID = "Michaels--8"
PACK5_SLUG = "5-pack-16-x-20-super-value-canvas-by-artist-s-loft-10131611"
PACK10_SLUG = "10-pack-8-x-10-super-value-canvas-by-artist-s-loft-10131568"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: both multipack PDPs + sign-in + cart
    judge.check("searched_canvas", navigated_search(traj, "Super Value Canvas"),
                "required: a Super Value Canvas search")
    judge.check("visited_pack5_pdp", navigated_product(traj, PACK5_SLUG),
                f"required: /product/{PACK5_SLUG}")
    judge.check("visited_pack10_pdp", navigated_product(traj, PACK10_SLUG),
                f"required: /product/{PACK10_SLUG}")
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    # answer: the winner + the math + the new subtotal
    judge.check("answer_winner_5pack", winner_named(answer, "5 Pack", "10 Pack"),
                "expected: the 5 Pack reported as the winner (tied to a comparative "
                "claim), and no claim that the 10 Pack gives more / wins")
    judge.check("answer_math_5pack", contains_amount(answer, 1600) or
                contains_phrase(answer, "1,600") or contains_any(answer, ["123", "123.2"]),
                "expected the 5 Pack area math (1,600 sq in or 123.2 sq in/$)")
    judge.check("answer_math_10pack", contains_amount(answer, 800) or
                contains_any(answer, ["61.6", "62"]),
                "expected the 10 Pack area math (800 sq in or 61.6 sq in/$)")
    judge.check("answer_new_subtotal", contains_amount(answer, 70.33),
                "expected new cart subtotal $70.33")
    # DB after-state: alice's 5 Pack row qty 1 -> 2, nothing else
    change = cart_qty_change(after_db, initial_db, user_id=1, product_id=106, variant_sku="")
    judge.check("pack5_qty_2", change == (1, 2),
                f"expected 5 Pack qty 1 -> 2; observed={change!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("cart_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
