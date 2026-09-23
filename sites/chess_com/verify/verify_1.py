#!/usr/bin/env python3
"""Verify the Blitz x Bullet top-3 overlap + Bullet #1 rating in Chess.com--1."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--1"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: both leaderboards the task compares.
    check_visited_path(judge, traj, "visited_blitz_leaderboard", "/leaderboard/live")
    check_visited_path(judge, traj, "visited_bullet_leaderboard", "/leaderboard/live/bullet")
    # Frozen ground truth: top-3 blitz = Hikaru/MagnusCarlsen/Sina-Movahed, top-3 bullet =
    # ArkadiiKhromaev/Hikaru/GMBrewChess -> the only overlap is Hikaru; bullet #1 rating 3602.
    judge.check("answer_overlap_username", contains_phrase(answer, "Hikaru"), "expected 'Hikaru'")
    judge.check("answer_bullet_top1_rating", contains_count(answer, 3602), "expected 3602")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
