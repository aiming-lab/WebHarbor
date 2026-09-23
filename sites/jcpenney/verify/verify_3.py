#!/usr/bin/env python3
"""Verify JCPenney--3."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--3"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_bulova_product",
                       "/p/bulova-crystal-womens-crystal-accent-two-tone-stainless-steel-bracelet-watch-98l273/ppr5007888050")
    # Frozen ground truth (seed DB, ppid ppr5007888050): sale $150.00 - $375.00,
    # rating 4.5, 8 reviews, rating breakdown 5-star=7 / 1-star=1.
    judge.check("answer_sale_price", contains_money(answer, [150.00, 375.00]),
                "expected the sale price range $150.00 - $375.00")
    judge.check("answer_rating", contains_amount(answer, 4.5),
                "expected the average star rating 4.5")
    judge.check("answer_review_count", contains_count(answer, 8),
                "expected 8 total customer reviews")
    judge.check("answer_five_star_count", contains_count(answer, 7),
                "expected 7 five-star reviews in the breakdown")
    judge.check("answer_one_star_count", contains_count(answer, 1),
                "expected 1 one-star review in the breakdown")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
