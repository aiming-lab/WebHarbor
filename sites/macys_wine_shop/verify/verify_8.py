#!/usr/bin/env python3
"""Verify MacysWineShop--8: most-reviewed product (Chardonnay Reserva)"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--8"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_search_for_chardonnay_reserva",
                navigated_search_with(traj, "q", ["chardonnay", "reserva"]),
                "required: a site search for chardonnay reserva")
    check_visited_path(judge, traj, "visited_ahlma_product_page",
                       "/products/2023-ahlma-chardonnay-reserva")
    # Frozen ground truth: 2023 Ahlma Chardonnay Reserva — 4.6 average, 11 reviews,
    # 100% would recommend.
    judge.check("answer_product_name", contains_phrase(answer, "Ahlma Chardonnay Reserva"),
                "expected the product '2023 Ahlma Chardonnay Reserva'")
    judge.check("answer_average_rating", contains_phrase(answer, "4.6"),
                "expected the 4.6 average rating")
    judge.check("answer_review_count", contains_count(answer, 11),
                "expected 11 reviews")
    judge.check("answer_recommend_percentage", contains_percent(answer, 100),
                "expected 100% would recommend")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
