#!/usr/bin/env python3
"""Verify Michaels--2 (round-2 redesign).

Bob is prepping a school craft fair: his cart needs a rework — the corrugated
display board is already covered (remove it), he needs the letter S, not B
(swap in a 13" White MDF Uppercase Letter S), and the candy wafers go up to
4 bags. With the final cart set, report each remaining item with its unit
price, the new subtotal, and the new order total.

Frozen ground truth (seed DB): bob's seed cart = 13" White MDF Uppercase
Letter 'B' @6.99 + 2x 36"x48" Corrugated Tri-Fold Display Board (Black) @5.99
+ Melt Craft Vanilla Candy Wafers @4.99. After the rework the cart holds
exactly: 13" White MDF Uppercase Letter 'S' (sku 10281322, same $6.99 as B)
qty 1 + wafers qty 4. New subtotal = 6.99 + 4 x 4.99 = $26.95; shipping $5.99
(under $49); tax 9.25% = $2.49; order total $35.43 (money ground truth
unchanged from round 1 — S and B share the letter price).
"""
from verify_lib import (Judge, cart_of, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_phrase, final_answer, navigated_product, navigated_search,
                        run_verifier)

TASK_ID = "Michaels--2"
LETTER_B_SKU = "10281304"
LETTER_S_SKU = "10281322"
LETTER_SLUG = "13-white-mdf-uppercase-letter-by-make-market-10281316"
WAFERS_SKU = "10764405"
BOARD_SKU = "10044460"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: sign-in, the cart, a search for the letter, the letter PDP
    check_signed_in_as(judge, traj, "bob.c@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    judge.check("searched_for_letter",
                navigated_search(traj, "MDF") or navigated_search(traj, "letter"),
                "required: a /search?q=... visit naming the MDF letter")
    judge.check("visited_letter_pdp", navigated_product(traj, LETTER_SLUG),
                f"required: product page for {LETTER_SLUG}")
    # answer: remaining items with unit prices + new subtotal + new order total
    judge.check("answer_letter_named", contains_phrase(answer, "MDF Uppercase Letter"),
                "expected the remaining MDF letter named")
    judge.check("answer_wafers_named", contains_phrase(answer, "Candy Wafers"),
                "expected the remaining candy wafers named")
    judge.check("answer_letter_unit_price", contains_amount(answer, 6.99),
                "expected letter unit price $6.99")
    judge.check("answer_wafers_unit_price", contains_amount(answer, 4.99),
                "expected wafers unit price $4.99 per bag")
    judge.check("answer_new_subtotal", contains_amount(answer, 26.95),
                "expected new cart subtotal $26.95")
    judge.check("answer_new_order_total", contains_amount(answer, 35.43),
                "expected new order total $35.43")
    # DB after-state: board gone, B gone, S added qty 1, wafers qty 4, 2 rows
    before = cart_of(initial_db, "bob.c@test.com")
    after = cart_of(after_db, "bob.c@test.com")
    by_sku = lambda rows: {r["variant_sku"]: r for r in rows}  # noqa: E731
    b, a = by_sku(before), by_sku(after)
    judge.check("board_removed", BOARD_SKU not in a, f"cart after={sorted(a)!r}")
    judge.check("letter_b_removed", LETTER_B_SKU not in a, f"cart after={sorted(a)!r}")
    judge.check("letter_s_added", a.get(LETTER_S_SKU, {}).get("qty") == 1,
                f"S row after={a.get(LETTER_S_SKU)!r}")
    judge.check("wafers_qty_4", a.get(WAFERS_SKU, {}).get("qty") == 4,
                f"wafers row after={a.get(WAFERS_SKU)!r}")
    judge.check("two_rows_only", len(after) == 2, f"cart rows after={len(after)}")
    check_only_tables_changed(judge, initial_db, after_db, ("cart_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
