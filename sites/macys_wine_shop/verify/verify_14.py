#!/usr/bin/env python3
"""Verify MacysWineShop--14 (KEEP): carol password change + revert.

Adapted unchanged in substance from the depth review's KEEP contract for the
old --23 (21 measured steps): the trajectory signs in as carol.d@test.com,
changes the account password to AutumnCellar77! (the account page confirms
each change with 'Password changed successfully.'), reverts to TestPass123!,
signs out, and signs back in with the original password. The DB after-state is
row-identical to the seed (the revert restores the password hash exactly).
"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_phrase, final_answer, input_texts,
                        run_verifier)

TASK_ID = "MacysWineShop--14"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_password_page", "/account/password")
    inputs = input_texts(traj)
    judge.check("entered_new_password",
                any("AutumnCellar77!" in v for v in inputs),
                f"expected AutumnCellar77! in an input step; observed={inputs!r}")
    judge.check("reverted_to_original_password",
                sum(1 for v in inputs if "TestPass123!" in v) >= 1,
                "expected the original password TestPass123! to be re-entered")
    # Frozen ground truth: the account page confirms each change with
    # "Password changed successfully."
    judge.check("answer_change_confirmed",
                contains_phrase(answer, "Password changed successfully"),
                "expected the account page confirmation 'Password changed successfully.'")
    # DB after-state: the revert restores the seed row exactly.
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
