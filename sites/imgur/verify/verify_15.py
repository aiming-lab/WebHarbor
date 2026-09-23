#!/usr/bin/env python3
"""Verify the newest-sorted cat-search report in Imgur--15."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_phrase, final_answer, navigated_search_with, run_verifier)

TASK_ID = "Imgur--15"
FIRST_NEWEST_PATH = "/gallery/left-stove-on-too-long-nl2VKCM"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the cat search sorted by newest (sort=time), then the first
    # result opened.
    judge.check("ran_cat_search_newest",
                navigated_search_with(traj, ["cat"], exact_params={"sort": "time"}),
                "required /search?q=cat&sort=time")
    check_visited_path(judge, traj, "visited_first_newest_result", FIRST_NEWEST_PATH)
    # Frozen ground truth (seed DB): newest-sorted first 'cat' result is
    # 'Left the stove on too long...' (nl2VKCM) by SaltyInternetPirate.
    judge.check("answer_first_newest_title",
                contains_phrase(answer, "Left the stove on too long"),
                "expected the first result title 'Left the stove on too long...'")
    judge.check("answer_first_newest_author", contains_phrase(answer, "SaltyInternetPirate"),
                "expected the author 'SaltyInternetPirate'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
