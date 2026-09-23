#!/usr/bin/env python3
"""Verify MacysWineShop--29: wine 101: storage temperatures"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--29"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_blog_index", "/blogs/wine-101")
    check_visited_path(judge, traj, "visited_article",
                       "/blogs/wine-101/a-guide-to-wine-storage-temperatures")
    # Frozen ground truth: title "A Guide to Wine Storage Temperatures"; best
    # place = a wine cellar or wine storage fridge; other factors = light
    # exposure, humidity, bottle position.
    judge.check("answer_article_title", contains_phrase(answer, "A Guide to Wine Storage Temperatures"),
                "expected the article title 'A Guide to Wine Storage Temperatures'")
    judge.check("answer_best_place",
                contains_phrase(answer, "wine cellar") and contains_phrase(answer, "wine storage fridge"),
                "expected the best place: a wine cellar or wine storage fridge")
    factors = sum(1 for f in ("light", "humidity", "bottle position") if contains_phrase(answer, f))
    judge.check("answer_other_factors", factors >= 2,
                "expected at least two other factors (light exposure, humidity, bottle position)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
