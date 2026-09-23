#!/usr/bin/env python3
"""Verify the 'Bye bye blue light' Explore report in Google Shopping--2."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_count,
                        contains_phrase, final_answer, navigated_search_with, run_verifier)

TASK_ID = "Google Shopping--2"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the Explore click must land on the section's scored search.
    judge.check("visited_explore_search",
                navigated_search_with(traj, ["blue", "light", "glasses"]),
                "required=/search?q=<blue light glasses> (the 'Bye bye blue light' Explore query)")
    # Frozen ground truth (seed DB, feed_sections row 'Bye bye blue light'):
    # explore query 'Blue-light glasses'; scored search returns 31 of the 61 catalog rows.
    judge.check("answer_explore_query", contains_phrase(answer, "Blue-light glasses"),
                "expected the query 'Blue-light glasses'")
    judge.check("answer_result_count", contains_count(answer, 31), "expected 31 results")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
