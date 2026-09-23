#!/usr/bin/env python3
"""Verify the memes-today search report in Imgur--29."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, navigated_search_with,
                        run_verifier)

TASK_ID = "Imgur--29"
FIRST_RESULT_PATH = "/gallery/purple-crayon-oc-b8eXzGz"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the memes search restricted to today (date=day), then the first
    # result opened.
    judge.check("ran_memes_search_today",
                navigated_search_with(traj, ["memes"], exact_params={"date": "day"}),
                "required /search?q=memes&date=day")
    check_visited_path(judge, traj, "visited_first_today_result", FIRST_RESULT_PATH)
    # Frozen ground truth (seed DB): the today window (mirror reference date minus one
    # day) keeps 4 of the 8 'memes' matches; the first is 'The Purple Crayon [OC]'.
    judge.check("answer_today_results_count", contains_count(answer, 4),
                "expected 4 results for today")
    judge.check("answer_first_result_title", contains_phrase(answer, "The Purple Crayon"),
                "expected the first result title 'The Purple Crayon [OC]'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
