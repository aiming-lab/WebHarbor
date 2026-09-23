#!/usr/bin/env python3
"""Verify MacysWineShop--12: Della Flora Organic Cabernet Wine Info rows"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--12"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_della_flora_page",
                       "/products/2022-della-flora-organic-cabernet-sauvignon")
    # Frozen ground truth (Wine Info table): Winery Jenna WInes, Varietal Cabernet
    # Sauvignon, Year 2022, ABV 13.1, Country United States, Region California.
    judge.check("answer_winery", contains_phrase(answer, "Jenna WInes"),
                "expected winery 'Jenna WInes' (as shown on the page)")
    judge.check("answer_varietal", contains_phrase(answer, "Cabernet Sauvignon"),
                "expected varietal Cabernet Sauvignon")
    judge.check("answer_year", contains_count(answer, 2022),
                "expected year 2022")
    judge.check("answer_abv", contains_phrase(answer, "13.1"),
                "expected ABV 13.1")
    judge.check("answer_country", contains_phrase(answer, "United States"),
                "expected country United States")
    judge.check("answer_region", contains_phrase(answer, "California"),
                "expected region California")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
