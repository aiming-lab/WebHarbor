#!/usr/bin/env python3
"""Verify the most expensive Deals-page product in Google Shopping--19."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_percent, contains_phrase, contains_price, final_answer, run_verifier)

TASK_ID = "Google Shopping--19"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the Deals page grid must be scanned for prices.
    check_visited_path(judge, traj, "visited_deals_page", "/deals")
    # Frozen ground truth (seed DB): the most expensive discounted row is 'trench' at
    # $1,704.00 (22% OFF, Reversible).
    judge.check("answer_product_title", contains_phrase(answer, "trench"),
                "expected the exact title 'trench'")
    judge.check("answer_current_price", contains_price(answer, 1704.00), "expected $1,704.00")
    judge.check("answer_discount_pct", contains_percent(answer, 22), "expected 22% OFF")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
