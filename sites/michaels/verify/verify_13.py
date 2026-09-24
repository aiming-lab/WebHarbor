#!/usr/bin/env python3
"""Verify Michaels--13.

Carol is decorating the gym for the fall festival. On the 6" Glitter Tulle by
Celebrate It Occasions product page: list every color it comes in and the
price per roll. Add three Fuchsia rolls to Carol's cart (carol.d@test.com),
apply the online 30% off code, and report the discount amount and the new
order total shown in the cart summary.

Frozen ground truth (seed DB): 10 colors (Fuchsia, Pink, Purple, White/Gold,
Turquoise, Silver, Iridescent White, Red, Neon Orange, Neon Pink), $4.99 per
roll. Carol's seed cart $44.41 + 3 x $4.99 = $59.38 subtotal; GETMY30 30% off
= $17.81; $41.57 < $49 -> shipping $5.99; tax 9.25% = $3.85; total $51.41.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_any, contains_phrase, entered_text_containing, final_answer,
                        navigated_product, navigated_search, run_verifier)

TASK_ID = "Michaels--13"
TULLE_SLUG = "6-glitter-tulle-by-celebrate-it-occasions-10217915"
COLORS = ("Fuchsia", "Pink", "Purple", "White/Gold", "Turquoise", "Silver",
          "Iridescent White", "Red", "Neon Orange", "Neon Pink")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the tulle PDP (pre and post sign-in), cart with promo
    judge.check("searched_tulle", navigated_search(traj, "Glitter Tulle"),
                "required: a glitter tulle search")
    judge.check("visited_tulle_pdp", navigated_product(traj, TULLE_SLUG),
                f"required: /product/{TULLE_SLUG}")
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    judge.check("entered_promo_code", entered_text_containing(traj, "GETMY30"),
                "expected GETMY30 entered in an input step")
    # answer: colors + price + discount + new total
    judge.check("answer_price", contains_amount(answer, 4.99),
                "expected price per roll $4.99")
    missing = [c for c in COLORS if not contains_phrase(answer, c)]
    judge.check("answer_all_colors", not missing,
                f"expected all 10 colors; missing={missing!r}")
    judge.check("answer_discount", contains_amount(answer, 17.81),
                "expected discount $17.81")
    judge.check("answer_new_total", contains_amount(answer, 51.41),
                "expected new order total $51.41")
    # DB after-state: one cart row added (carol, product 114, Fuchsia sku 10217907, qty 3)
    before = {(r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"])
              for r in __import__("verify_lib").cart_of_raw(initial_db)}
    added = [r for r in __import__("verify_lib").cart_of_raw(after_db)
             if (r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"]) not in before]
    judge.check("added_cart_row",
                len(added) == 1 and added[0]["user_id"] == 3 and
                added[0]["product_id"] == 114 and added[0]["variant_sku"] == "10217907" and
                added[0]["color"] == "Fuchsia" and added[0]["qty"] == 3,
                f"expected one added cart row (user 3, product 114, Fuchsia, qty 3); found={added!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("cart_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
