#!/usr/bin/env python3
"""Verify the Deals-page >=70% count + most frequent merchant in Google Shopping--18."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, run_verifier)

TASK_ID = "Google Shopping--18"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the Deals page grid carries the discount badges to count.
    check_visited_path(judge, traj, "visited_deals_page", "/deals")
    # Frozen ground truth (seed DB): 12 discounted rows carry >= 70%; the merchant that
    # appears most often on the whole Deals grid is Fashion Nova (6 cards).
    judge.check("answer_count_70_or_more", contains_count(answer, 12),
                "expected 12 products at 70% or more")
    judge.check("answer_most_frequent_merchant", contains_phrase(answer, "Fashion Nova"),
                "expected Fashion Nova as the most frequent merchant")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
