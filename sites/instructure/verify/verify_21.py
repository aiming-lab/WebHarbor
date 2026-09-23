#!/usr/bin/env python3
"""Verify Instructure--21."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--21"

from verify_lib import db_query, table_delta, user_by_email

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "david.k@test.com")
    check_visited_path(judge, traj, "visited_account", "/account")
    # Frozen ground truth (seed DB): david_k starts with state California, job_title
    # Corporate Trainer; the task sets state Colorado and job title Director of
    # Learning; the flash reads "Your profile has been updated."
    judge.check("answer_confirmation", contains_phrase(answer, "profile has been updated"),
                "expected the confirmation message 'Your profile has been updated.'")
    judge.check("answer_new_state", contains_phrase(answer, "Colorado"),
                "expected the new state Colorado")
    judge.check("answer_new_job_title", contains_phrase(answer, "Director of Learning"),
                "expected the new job title Director of Learning")
    # DB delta: exactly david_k's users row changes (state + job_title), nothing else.
    david = user_by_email(initial_db, "david.k@test.com")
    delta = table_delta(initial_db, after_db, "users")
    ok_changed = (len(delta["added"]) == 0 and len(delta["removed"]) == 0
                  and len(delta["changed"]) == 1)
    if ok_changed:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(users)")]
        before = dict(zip(cols, delta["changed"][0][0]))
        after_row = dict(zip(cols, delta["changed"][0][1]))
        ok_changed = (before["id"] == david["id"]
                      and after_row["state"] == "Colorado"
                      and after_row["job_title"] == "Director of Learning"
                      and after_row["email"] == david["email"]
                      and after_row["username"] == david["username"])
    judge.check("db_profile_delta", ok_changed,
                f"users delta={delta!r}, expected david_k state=Colorado + "
                f"job_title=Director of Learning and nothing else")
    check_only_tables_changed(judge, initial_db, after_db, ["users"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
