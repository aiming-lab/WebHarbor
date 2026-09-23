#!/usr/bin/env python3
"""Verify LandWatch--26 — alice.j@test.com edits the profile phone number.

Ground truth: saving the validated edit flashes 'Profile updated.' and the
My LandWatch profile card shows (919) 555-0139; the users table row for alice
carries the new phone with her name unchanged.
"""

from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path,
                        contains_phrase, final_answer, run_verifier,
                        table_delta, user_by_email)

TASK_ID = "LandWatch--26"
ALICE_EMAIL = "alice.j@test.com"
NEW_PHONE = "(919) 555-0139"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE_EMAIL)
    check_visited_path(judge, traj, "visited_account_edit", "/account/edit")
    check_visited_path(judge, traj, "visited_account_page", "/account")
    check_only_tables_changed(judge, initial_db, after_db, {"sessions", "users"})
    delta = table_delta(initial_db, after_db, "users")
    judge.check("only_alice_user_row_changed",
                len(delta["added"]) == 0 and len(delta["removed"]) == 0
                and len(delta["changed"]) == 1,
                f"users delta={delta!r}")
    if delta["changed"]:
        before, after = delta["changed"][0]
        judge.check("alice_phone_updated", after[4] == NEW_PHONE,
                    f"expected phone {NEW_PHONE!r}, observed {after[4]!r}")
        judge.check("alice_name_unchanged", after[3] == "Alice Johnson",
                    f"expected name 'Alice Johnson', observed {after[3]!r}")
    judge.check("answer_success_message", contains_phrase(answer, "Profile updated"),
                "expected the success message 'Profile updated.'")
    judge.check("answer_confirms_new_phone", "(919) 555-0139" in answer or
                "919-555-0139" in answer or "919 555 0139" in answer,
                "expected the new phone (919) 555-0139 in the answer")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
