#!/usr/bin/env python3
"""Verify the top-10 US players count on the Blitz leaderboard in Chess.com--2."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--2"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_blitz_leaderboard", "/leaderboard/live")
    # Frozen ground truth: US players (country_id 2) among blitz top-10 = Hikaru (#1), HansOnTwitch (#6) -> 2.
    judge.check("answer_us_count", contains_count(answer, 2), "expected 2 US players")
    judge.check("answer_us_usernames", contains_phrase(answer, "Hikaru") and contains_phrase(answer, "HansOnTwitch"),
                "expected Hikaru and HansOnTwitch")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
