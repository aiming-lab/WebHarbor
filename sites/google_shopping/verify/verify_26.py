#!/usr/bin/env python3
"""Verify the Jordan Lee registration flow in Google Shopping--26."""


from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_count, entered_identity, final_answer,
                        run_verifier, table_delta, user_row_by_email)

TASK_ID = "Google Shopping--26"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation + identity gates: the registration form carries the required identity,
    # and the (empty) shopping list was opened afterwards.
    check_visited_path(judge, traj, "visited_register_page", "/register")
    judge.check("entered_new_account_identity",
                entered_identity(traj, "jordan.lee@test.com", "Jordan Lee"),
                "expected 'jordan.lee@test.com' or 'Jordan Lee' in an input step; "
                f"observed_inputs={__import__('verify_lib').input_texts(traj)!r}")
    check_visited_path(judge, traj, "visited_shopping_list", "/saved")
    # Frozen ground truth: a brand-new account's shopping list is empty.
    judge.check("answer_empty_list", contains_count(answer, 0), "expected 0 items")
    # DB after-state: exactly one users row added (jordan.lee@test.com / Jordan Lee);
    # no saved or tracked rows; nothing else changed.
    delta = table_delta(initial_db, after_db, "users")
    judge.check("users_delta_exactly_jordan",
                len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"]
                and delta["added"][0][1].strip().lower() == "jordan.lee@test.com"
                and delta["added"][0][2] == "Jordan Lee",
                f"users delta={delta}")
    row = user_row_by_email(after_db, "jordan.lee@test.com")
    judge.check("registered_user_readable", bool(row), "jordan.lee@test.com must exist after the run")
    check_only_tables_changed(judge, initial_db, after_db, ("users",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
