#!/usr/bin/env python3
"""Verify the cat-search heading + first-result report in Imgur--14."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, navigated_search_with,
                        run_verifier)

TASK_ID = "Imgur--14"
FIRST_RESULT_PATH = "/gallery/beach-time-gltaaBb"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("ran_cat_search", navigated_search_with(traj, ["cat"]),
                "required /search?q=cat")
    check_visited_path(judge, traj, "visited_first_result_gallery", FIRST_RESULT_PATH)
    # Frozen ground truth (seed DB): scored 'cat' search returns 23 results; the first
    # result is 'Beach time' (gltaaBb) with point_count 718.
    judge.check("answer_results_count", contains_count(answer, 23),
                "expected 'Found 23 results for cat'")
    judge.check("answer_first_result_title", contains_phrase(answer, "Beach time"),
                "expected the first result title 'Beach time'")
    judge.check("answer_first_result_score", contains_count(answer, 718),
                "expected 718 in the vote box of the first result")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
