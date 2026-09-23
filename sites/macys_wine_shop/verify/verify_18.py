#!/usr/bin/env python3
"""Verify MacysWineShop--18: age gate: Yes without a state"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--18"

def _has_action(traj, selector_fragment):
    for step in traj.get("steps") or []:
        if not isinstance(step, dict):
            continue
        params = step.get("params") or {}
        if selector_fragment in str(params.get("selector") or ""):
            return True
    return False


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("clicked_age_gate_yes", _has_action(traj, "age-yes"),
                "required: a click on the age gate's Yes button")
    # Frozen ground truth: "You must select your state to continue."
    judge.check("answer_state_error", contains_phrase(answer, "You must select your state to continue"),
                "expected the exact error: 'You must select your state to continue.'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
