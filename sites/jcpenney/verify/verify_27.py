#!/usr/bin/env python3
"""Verify JCPenney--27."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--27"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_frye_product",
                       "/p/frye-and-co-womens-miranda-stacked-heel-riding-boots/ppr5008625370")
    check_visited_path(judge, traj, "visited_liotta_product",
                       "/p/pop-womens-liotta-flat-heel-motorcycle-boots/ppr5008672778")
    # Frozen ground truth (seed DB): Frye and Co. Miranda Stacked Heel Riding Boots —
    # $140.00 ($140.00 - $160.00), rating 4.0, 2 reviews; Pop Liotta Flat Heel
    # Motorcycle Boots — $52.50, no rating yet (0 reviews). Frye is rated higher;
    # price difference of the displayed sale prices: $87.50.
    judge.check("answer_frye_higher", contains_phrase(answer, "Frye"),
                "expected the Frye and Co. Miranda boots named as rated higher")
    judge.check("answer_frye_rating", contains_amount(answer, 4.0),
                "expected Frye's average rating 4.0")
    judge.check("answer_frye_reviews", contains_count(answer, 2),
                "expected Frye's 2 reviews")
    judge.check("answer_liotta_no_rating", contains_any(answer, ["no rating", "no reviews", "0 reviews",
                                                                 "unrated", "not rated", "no stars"]),
                "expected the Liotta boots reported with no rating / 0 reviews")
    judge.check("answer_price_difference", contains_amount(answer, 87.50),
                "expected the price difference $87.50 ($140.00 vs $52.50)")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
