#!/usr/bin/env python3
"""Verify JCPenney--5."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--5"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_most_reviewed_product",
                       "/p/a-n-a-womens-crew-neck-long-sleeve-t-shirt/ppr5008726636")
    # Frozen ground truth (seed DB, ppid ppr5008726636): rating 3.875 rendered as 3.9,
    # 8 reviews, most recent review (2026-09-21) by BusinessCasual22 = 4 stars,
    # headline "Soft and Stretchy - DOES RUN SMALL".
    judge.check("answer_rating", contains_any(answer, ["3.9", "3.875"]),
                "expected the average rating 3.9 (3.875) as rendered on the page")
    judge.check("answer_review_count", contains_count(answer, 8),
                "expected 8 total reviews")
    judge.check("answer_recent_headline", contains_phrase(answer, "Soft and Stretchy - DOES RUN SMALL"),
                "expected the most recent review headline")
    judge.check("answer_recent_rating", contains_count(answer, 4),
                "expected the most recent reviewer's 4-star rating")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
