#!/usr/bin/env python3
"""Verify the most expensive product report in Google Shopping--9."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_phrase,
                        contains_price, final_answer, navigated_search_with, run_verifier)

TASK_ID = "Google Shopping--9"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: an (empty) scored search sorted by price high to low.
    judge.check("visited_desc_sorted_search",
                navigated_search_with(traj, [], exact_params={"sort": "price_desc"}),
                "required=/search?sort=price_desc (empty query)")
    # Frozen ground truth (seed DB): the most expensive catalog row is 'trench' at
    # $1,704.00 sold by Reversible.
    judge.check("answer_product_title", contains_phrase(answer, "trench"),
                "expected the exact title 'trench'")
    judge.check("answer_product_price", contains_price(answer, 1704.00), "expected $1,704.00")
    judge.check("answer_product_merchant", contains_phrase(answer, "Reversible"),
                "expected merchant Reversible")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
