#!/usr/bin/env python3
"""Verify alice's account-page report in Google Shopping--27."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase, final_answer,
                        run_verifier)

TASK_ID = "Google Shopping--27"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Auth + navigation gates: sign in as alice, open the account page.
    check_signed_in_as(judge, traj, "alice.j@test.com", "Alice Johnson")
    check_visited_path(judge, traj, "visited_account_page", "/account")
    # Frozen ground truth (seed DB): display name 'Alice Johnson', 1 saved item, 0 tracked.
    judge.check("answer_display_name", contains_phrase(answer, "Alice Johnson"),
                "expected 'Alice Johnson'")
    judge.check("answer_saved_count", contains_count(answer, 1), "expected 1 saved item")
    judge.check("answer_tracked_count", contains_count(answer, 0), "expected 0 tracked items")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
