#!/usr/bin/env python3
"""Verify the Magnus Carlsen games stats report in Chess.com--26."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--26"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_magnus_games", "/games/magnus-carlsen")
    # Frozen ground truth: 6,806 total games; As White win stat 61%.
    judge.check("answer_total_games", contains_amount(answer, 6806), "expected 6,806 games")
    judge.check("answer_white_win_percent", contains_percent(answer, 61), "expected 61% as White")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
