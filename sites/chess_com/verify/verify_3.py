#!/usr/bin/env python3
"""Verify the Rapid leaderboard rank-50 player in Chess.com--3."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--3"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_rapid_leaderboard", "/leaderboard/live/rapid")
    # Frozen ground truth: rapid rank 50 = SahibSinghKnight, rating 2695.
    judge.check("answer_rank50_username", contains_phrase(answer, "SahibSinghKnight"),
                "expected 'SahibSinghKnight'")
    judge.check("answer_rank50_rating", contains_count(answer, 2695), "expected 2695")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
