#!/usr/bin/env python3
"""Verify JCPenney--0."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--0"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_boots_search_sorted_price_low",
                 navigated_search_sorted(traj, "boots", "price_low"),
                 "required: /s/boots with sortBy=price_low")
    # Frozen ground truth (seed DB, scored_search("boots") -> 8 results; price_low sort
    # orders SJB Hope (sort 104) before SJB Kinnel (sort 109) at $27.99):
    judge.check("answer_result_count", contains_count(answer, 8),
                "expected 8 results for the boots search")
    judge.check("answer_cheapest_name", contains_phrase(answer, "Hope Stacked Heel Booties"),
                "expected the cheapest: St. John's Bay Womens Hope Stacked Heel Booties")
    judge.check("answer_cheapest_brand", contains_phrase(answer, "St. John's Bay"),
                "expected brand ST. JOHN'S BAY")
    judge.check("answer_cheapest_price", contains_amount(answer, 27.99),
                "expected the cheapest price $27.99 (card shows $27.99 - $65.00)")
    judge.check("answer_second_name", contains_phrase(answer, "Kinnel Flat Heel Booties"),
                "expected the second product: St. John's Bay Womens Kinnel Flat Heel Booties")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
