#!/usr/bin/env python3
"""Verify the Blitz leaderboard #3 report in Chess.com--0."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--0"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the task names /leaderboard/live (Blitz leaderboard page 1).
    check_visited_path(judge, traj, "visited_blitz_leaderboard", "/leaderboard/live")
    # Frozen ground truth (seed DB, blitz rank 3): username Sina-Movahed, rating 3334, won 4761.
    judge.check("answer_rank3_username", contains_phrase(answer, "Sina-Movahed"),
                "expected 'Sina-Movahed'")
    judge.check("answer_rank3_rating", contains_count(answer, 3334), "expected rating 3334")
    judge.check("answer_rank3_won", contains_count(answer, 4761), "expected won 4761")
    # Read-only task: every table row-identical before/after.
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
