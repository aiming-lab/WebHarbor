#!/usr/bin/env python3
"""Verify the MagnusCarlsen profile report in Chess.com--5."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--5"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the member profile page (any URL-case of the username).
    judge.check("visited_magnus_profile",
                any(u.casefold().rstrip("/").endswith("/member/magnuscarlsen")
                    for u in __import__("verify_lib").site_urls(traj)),
                "required_path=/member/MagnusCarlsen (case-insensitive)")
    # Frozen ground truth: full name 'Magnus Carlsen', 317377 followers, Rapid rating 2941.
    judge.check("answer_full_name", contains_phrase(answer, "Magnus Carlsen"), "expected 'Magnus Carlsen'")
    judge.check("answer_followers", contains_amount(answer, 317377), "expected 317,377 followers")
    judge.check("answer_rapid_rating", contains_count(answer, 2941), "expected Rapid 2941")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
