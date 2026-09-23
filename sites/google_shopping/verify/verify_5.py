#!/usr/bin/env python3
"""Verify the Fashion Nova store-filter search report in Google Shopping--5."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_count,
                        contains_price, final_answer, navigated_search_with, run_verifier)

TASK_ID = "Google Shopping--5"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: scored search for 'blue light glasses' with the store filter applied.
    judge.check("visited_store_filtered_search",
                navigated_search_with(traj, ["blue", "light", "glasses"], exact_params={"store": "Fashion Nova"}),
                "required=/search?q=blue light glasses&store=Fashion Nova")
    # Frozen ground truth (seed DB): 6 Fashion Nova products match; lowest current price $2.98.
    judge.check("answer_result_count", contains_count(answer, 6), "expected 6 results")
    judge.check("answer_lowest_price", contains_price(answer, 2.98), "expected lowest price $2.98")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
