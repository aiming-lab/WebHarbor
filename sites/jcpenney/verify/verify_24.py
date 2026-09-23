#!/usr/bin/env python3
"""Verify JCPenney--24."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--24"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_new_trending", "/g/new-and-trending")
    # Frozen ground truth (seed DB): 55 new-arrival products; cheapest =
    # Layerings Hey Boo 2-pc. Kitchen Towel Set at $8.99 (card shows $8.99 - $16.00);
    # most expensive = Papell Boutique Womens V Neck Short Sleeve Cap Evening Gown
    # at $89.59 (card shows $89.59 - $160.00).
    judge.check("answer_product_count", contains_count(answer, 55),
                "expected 55 new-arrival products")
    judge.check("answer_cheapest", contains_all(answer, ["Hey Boo", "8.99"]),
                "expected the cheapest: Layerings Hey Boo 2-pc. Kitchen Towel Set at $8.99")
    judge.check("answer_most_expensive", contains_all(answer, ["Papell Boutique", "89.59"]),
                "expected the most expensive: Papell Boutique evening gown at $89.59")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
