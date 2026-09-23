#!/usr/bin/env python3
"""Verify MacysWineShop--6: 12-bottle sets, price descending, most expensive + discount"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--6"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_12b_sets_sorted_desc",
                navigated_listing_sorted(traj, "/collections/12-bottle-wine-sets", "price-descending"),
                "required: /collections/12-bottle-wine-sets?sort_by=price-descending")
    judge.check("opened_most_expensive_set_page",
                navigated_to_path(traj, "/products/celebrate-the-season-case-1"),
                "required: the most expensive set's product page (Celebrate the Season Case)")
    # Frozen ground truth: 44 sets; most expensive = Celebrate the Season Case
    # $206.30 (compare-at $254.88), 19% off.
    judge.check("answer_set_count", contains_count(answer, 44),
                "expected 44 sets in the collection")
    judge.check("answer_most_expensive_name", contains_phrase(answer, "Celebrate the Season Case"),
                "expected the most expensive set 'Celebrate the Season Case'")
    judge.check("answer_most_expensive_price", contains_money(answer, 206.30),
                "expected the most expensive set price $206.30")
    judge.check("answer_discount_percent", contains_percent(answer, 19),
                "expected the 19% discount shown on the most expensive set")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
