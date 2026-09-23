#!/usr/bin/env python3
"""Verify MacysWineShop--26: wine club case option compositions"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--26"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_wine_club_page", "/pages/wine-club")
    judge.check("switched_club_tabs",
                any("club-tab" in str((step.get("params") or {}).get("selector") or "")
                    for step in traj.get("steps") or [] if isinstance(step, dict)),
                "required: clicking the All Reds / All Whites club tabs")
    # Frozen ground truth: Mixed = 12 unique wines, 1 bottle each; All Reds =
    # 6 unique red wines, 2 bottles each; All Whites = 6 unique white wines, 2 bottles each.
    judge.check("answer_mixed_composition",
                contains_phrase(answer, "12 unique") and contains_any(answer, ["1 bottle", "1 bottles"]),
                "expected Mixed: 12 unique wines, 1 bottle each")
    judge.check("answer_reds_composition",
                contains_phrase(answer, "6 unique") and contains_phrase(answer, "red")
                and contains_any(answer, ["2 bottle", "2 bottles"]),
                "expected All Reds: 6 unique red wines, 2 bottles each")
    judge.check("answer_whites_composition",
                contains_phrase(answer, "6 unique") and contains_phrase(answer, "white")
                and contains_any(answer, ["2 bottle", "2 bottles"]),
                "expected All Whites: 6 unique white wines, 2 bottles each")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
