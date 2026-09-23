#!/usr/bin/env python3
"""Verify JCPenney--17."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--17"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_store_locator_wa_filter",
                 navigated_listing_with_filter(traj, "/stores", "state", "WA"),
                 "required: /stores?state=WA")
    # Frozen ground truth (seed DB): 13 Washington stores; the Lynnwood store is
    # JCPenney Alderwood Mall, phone (425) 771-9555.
    judge.check("answer_wa_count", contains_count(answer, 13),
                "expected 13 Washington stores")
    judge.check("answer_lynnwood_mall", contains_phrase(answer, "Alderwood Mall"),
                "expected the Lynnwood store at Alderwood Mall")
    judge.check("answer_lynnwood_phone", contains_phrase(answer, "(425) 771-9555"),
                "expected the Lynnwood store phone (425) 771-9555")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
