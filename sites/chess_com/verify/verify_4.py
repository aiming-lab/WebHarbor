#!/usr/bin/env python3
"""Verify the Tactics leaderboard #1/#5 report in Chess.com--4."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--4"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_tactics_leaderboard", "/leaderboard/tactics")
    # Frozen ground truth: tactics #1 = denghao (4394); #5 = petergrieco (4352).
    judge.check("answer_tactics_top1_username", contains_phrase(answer, "denghao"), "expected 'denghao'")
    judge.check("answer_tactics_top1_rating", contains_count(answer, 4394), "expected 4394")
    judge.check("answer_tactics_rank5_username", contains_phrase(answer, "petergrieco"), "expected 'petergrieco'")
    judge.check("answer_tactics_rank5_rating", contains_count(answer, 4352), "expected 4352")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
