#!/usr/bin/env python3
"""Verify MacysWineShop--16: guest cart: 3-bottle minimum + third bottle"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--16"

VALANDA_VARIANT_ID = 411


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_valanda_page", "/products/2021-valanda-tempranillo")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    # Frozen ground truth: "Minimum 3 Bottles Required for Checkout" note, Checkout
    # button disabled with 2 bottles, then a 3-bottle cart (total from the after-DB).
    judge.check("answer_minimum_note",
                contains_phrase(answer, "Minimum") and contains_phrase(answer, "3 Bottles Required"),
                "expected the 'Minimum 3 Bottles Required for Checkout' note")
    judge.check("answer_checkout_disabled",
                contains_any(answer, ["disabled", "not usable", "cannot", "unusable", "greyed", "grayed"]),
                "expected the Checkout button to be reported as not usable")
    # The third bottle is the agent's choice: the reported total must match the
    # after-DB cart (3 bottles => subtotal + $14.95 shipping + $2.95 processing).
    from verify_lib import table_columns
    cols = table_columns(after_db, "cart_items")
    delta = table_delta(initial_db, after_db, "cart_items")
    added = [dict(zip(cols, row)) for row in delta["added"]]
    ok_rows = (len(added) >= 1 and len(delta["removed"]) == 0
               and all(row["user_id"] is None for row in added))
    judge.check("db_guest_cart_rows", ok_rows,
                f"expected only added guest cart rows; delta={ {k: len(v) for k, v in delta.items()} }")
    bottles = 0
    subtotal = 0.0
    valanda_qty = 0
    for row in added:
        qty = int(row["quantity"])
        variant = db_query(after_db, "SELECT price, bottle_count FROM product_variants WHERE id = ?",
                           (row["variant_id"],))
        price = float(variant[0]["price"])
        bc = int(variant[0]["bottle_count"])
        bottles += qty * bc
        subtotal += qty * price
        if row["variant_id"] == VALANDA_VARIANT_ID:
            valanda_qty += qty
    judge.check("db_cart_holds_three_bottles", bottles == 3,
                f"expected the guest cart to hold exactly 3 bottles; observed {bottles}")
    judge.check("db_cart_keeps_two_valanda", valanda_qty >= 2,
                f"expected at least 2 bottles of the Valanda Tempranillo; observed {valanda_qty}")
    expected_total = round(subtotal + 14.95 + 2.95, 2)
    judge.check("answer_cart_total_matches_db", contains_money(answer, expected_total),
                f"expected the reported cart total to equal the DB-derived total ${expected_total:.2f}")
    check_only_tables_changed(judge, initial_db, after_db, {"cart_items"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
