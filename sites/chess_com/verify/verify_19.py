#!/usr/bin/env python3
"""Verify the Daily Puzzle report in Chess.com--19."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--19"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the daily puzzle page (either route).
    vl = __import__("verify_lib")
    judge.check("visited_daily_puzzle",
                vl.navigated_to_path(traj, "/daily") or vl.navigated_to_path(traj, "/puzzles/daily"),
                "required /daily or /puzzles/daily")
    # Frozen ground truth: 2026-09-22, title 'Discover Your Gift', goal 'Win material'.
    judge.check("answer_date", contains_date(answer, "2026-09-22"), "expected Sep 22, 2026")
    judge.check("answer_title", contains_phrase(answer, "Discover Your Gift"),
                "expected 'Discover Your Gift'")
    judge.check("answer_goal", contains_phrase(answer, "Win material"), "expected 'Win material'")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
