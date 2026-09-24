#!/usr/bin/env python3
"""Verify Michaels--18.

Alice's kids each want a Halloween paint-by-number kit: compare the 11" x 14"
Cat in Library Paint-by-Number Kit with the Light Up Black Cat
Paint-by-Number Acrylic Surface Kit — look at both rating and price. Add two
of the higher-rated one to Alice's cart, apply the online 30% off code, and
report the discount amount and the new order total.

Frozen ground truth (seed DB): Cat in Library $6.99, rating 4.3 (6 reviews);
Light Up Black Cat $5.99, rating 4.5 (6). The Light Up Black Cat is higher
rated. Alice's seed cart $57.34 + 2 x $5.99 = $69.32 subtotal; GETMY30 30%
off = $20.80; $48.52 < $49 -> shipping $5.99; tax 9.25% = $4.49;
total $59.00.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_phrase, entered_text_containing, final_answer,
                        navigated_product, navigated_search, run_verifier)

TASK_ID = "Michaels--18"
CAT_SLUG = "11-x-14-cat-in-library-paint-by-number-kit-by-artist-s-loft-10808381"
LUC_SLUG = "light-up-black-cat-paint-by-number-acrylic-surface-kit-by-artist-s-loft-10808372"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: both kit PDPs + sign-in + cart with promo
    judge.check("searched_pbn", navigated_search(traj, "paint-by-number"),
                "required: a paint-by-number search")
    judge.check("visited_cat_pdp", navigated_product(traj, CAT_SLUG),
                f"required: /product/{CAT_SLUG}")
    judge.check("visited_luc_pdp", navigated_product(traj, LUC_SLUG),
                f"required: /product/{LUC_SLUG}")
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    judge.check("entered_promo_code", entered_text_containing(traj, "GETMY30"),
                "expected GETMY30 entered in an input step")
    # answer: both facts + winner + discount + new total
    judge.check("answer_cat_price", contains_amount(answer, 6.99),
                "expected Cat in Library price $6.99")
    judge.check("answer_cat_rating", contains_phrase(answer, "4.3"),
                "expected Cat in Library rating 4.3")
    judge.check("answer_luc_price", contains_amount(answer, 5.99),
                "expected Light Up Black Cat price $5.99")
    judge.check("answer_luc_rating", contains_phrase(answer, "4.5"),
                "expected Light Up Black Cat rating 4.5")
    judge.check("answer_discount", contains_amount(answer, 20.80),
                "expected discount $20.80")
    judge.check("answer_new_total", contains_amount(answer, 59.00),
                "expected new order total $59.00")
    # DB after-state: one cart row added (alice, product 296, qty 2)
    before = {(r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"])
              for r in __import__("verify_lib").cart_of_raw(initial_db)}
    added = [r for r in __import__("verify_lib").cart_of_raw(after_db)
             if (r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"]) not in before]
    judge.check("added_cart_row",
                len(added) == 1 and added[0]["user_id"] == 1 and
                added[0]["product_id"] == 296 and added[0]["qty"] == 2,
                f"expected one added cart row (user 1, product 296, qty 2); found={added!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("cart_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
