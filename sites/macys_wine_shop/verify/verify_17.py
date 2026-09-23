#!/usr/bin/env python3
"""Verify MacysWineShop--17: age gate: click No"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--17"

def _has_action(traj, selector_fragment):
    for step in traj.get("steps") or []:
        if not isinstance(step, dict):
            continue
        params = step.get("params") or {}
        if selector_fragment in str(params.get("selector") or ""):
            return True
        if selector_fragment in str(step.get("action") or ""):
            return True
    return False


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("clicked_age_gate_no", _has_action(traj, "age-no"),
                "required: a click on the age gate's No button")
    # Frozen ground truth: the page is replaced with "Sorry, you cannot proceed."
    judge.check("answer_rejected_message", contains_phrase(answer, "Sorry, you cannot proceed"),
                "expected the exact rejection: 'Sorry, you cannot proceed.'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
