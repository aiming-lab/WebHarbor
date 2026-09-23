#!/usr/bin/env python3
"""Verify MacysWineShop--25: wine club Mixed case + FAQ facts"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--25"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_wine_club_page", "/pages/wine-club")
    # Frozen ground truth: case price $99.99, processing $2.95, subtotal $102.94;
    # FAQ: ongoing membership $149.99, shipments every 13 weeks, support (855) 966-2224.
    judge.check("answer_case_price", contains_money(answer, 99.99),
                "expected the Mixed intro case price $99.99")
    judge.check("answer_processing_fee", contains_money(answer, 2.95),
                "expected the processing fee $2.95")
    judge.check("answer_subtotal", contains_money(answer, 102.94),
                "expected the subtotal $102.94")
    judge.check("answer_ongoing_price", contains_money(answer, 149.99),
                "expected the ongoing membership price $149.99")
    judge.check("answer_shipment_frequency", contains_count(answer, 13),
                "expected shipments approximately every 13 weeks")
    judge.check("answer_support_phone",
                contains_phrase(answer, "855") and contains_phrase(answer, "966-2224"),
                "expected the customer support phone (855) 966-2224")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
