#!/usr/bin/env python3
"""Verify Megabus--17.

Carol's contact details have changed. Sign in as carol.d@test.com (password TestPass123!), update her surname to Davies and mobile number to 555-202-7788, and confirm the name and phone number saved on her profile.
"""
from verify_lib import (check_only_tables_changed, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_phrase, final_answer, navigated_to,
                        run_verifier, user_by_email)

TASK_ID = "Megabus--17"
EMAIL = "carol.d@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    check_visited_path(judge, traj, "visited_profile", "/account-management/profile")
    judge.check("answer_new_name", contains_phrase(answer, "Carol Davies"),
                "expected the updated name 'Carol Davies' as shown on the account page")
    judge.check("answer_new_phone", contains_phrase(answer, "555-202-7788"),
                "expected the phone '555-202-7788' as shown on the account page")
    u = user_by_email(after_db, EMAIL)
    judge.check("db_last_name_updated", u is not None and u["last_name"] == "Davies",
                f"last_name={u['last_name'] if u else None!r}")
    judge.check("db_phone_updated", u is not None and (u["phone"] or "") == "555-202-7788",
                f"phone={u['phone'] if u else None!r}")
    judge.check("db_first_name_unchanged", u is not None and u["first_name"] == "Carol",
                f"first_name={u['first_name'] if u else None!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("users",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
