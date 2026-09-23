#!/usr/bin/env python3
"""Verify the Firouzja2003 profile report in Chess.com--6."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--6"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_firouzja_profile",
                any(u.casefold().rstrip("/").endswith("/member/firouzja2003")
                    for u in __import__("verify_lib").site_urls(traj)),
                "required_path=/member/Firouzja2003 (case-insensitive)")
    # Frozen ground truth: country France, 32264 followers.
    judge.check("answer_country", contains_phrase(answer, "France"), "expected 'France'")
    judge.check("answer_followers", contains_amount(answer, 32264), "expected 32,264 followers")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
