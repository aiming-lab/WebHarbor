#!/usr/bin/env python3
"""Verify MacysWineShop--27: gift card amounts + the $100 card price"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--27"

def _amount_present(answer, amount):
    return contains_money(answer, float(amount)) or contains_count(answer, amount)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_giftcard_page", "/products/giftcard")
    # Frozen ground truth: selectable amounts 25 / 50 / 75 / 100; the $100 gift
    # card is charged at $100.00.
    for amount in (25, 50, 75, 100):
        judge.check(f"answer_amount_{amount}", _amount_present(answer, amount),
                    f"expected the ${amount} gift card amount to be reported")
    judge.check("answer_100_card_price",
                contains_money(answer, 100.00) and contains_count(answer, 100),
                "expected the $100 card price $100.00")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
