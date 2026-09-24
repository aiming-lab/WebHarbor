#!/usr/bin/env python3
"""Verify Megabus--17.

Log in as Carol Davis; update the account to last name Davies and add mobile
555-202-7788; report exactly how the name and phone number now appear on the
account page. Then sign out and sign back in, reopen the profile page, and
confirm the saved details are still Davies and 555-202-7788.

Frozen ground truth (seed DB): carol.d@test.com (user id 3, Carol Davis).
After the update the users row must read first_name='Carol',
last_name='Davies', phone='555-202-7788'; the account page displays
"Carol Davies" and "555-202-7788". The sign-out/sign-in round trip writes
nothing to the DB; only the users row may change. The login page must have
been visited at least twice (initial sign-in + sign back in). The logout link
itself is a redirecting GET, so the logout URL never appears in a browser
trajectory; the twice-visited login page plus the re-opened profile page are
the round-trip evidence.
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
    judge.check("signed_out_and_back_in",
                navigated_to(traj, "/account-management/login", times=2),
                "required: the login page visited at least twice (sign in + sign back in)")
    judge.check("answer_new_name", contains_phrase(answer, "Carol Davies"),
                "expected the updated name 'Carol Davies' as shown on the account page")
    judge.check("answer_new_phone", contains_phrase(answer, "555-202-7788"),
                "expected the phone '555-202-7788' as shown on the account page")
    judge.check("answer_confirms_persistence",
                (contains_phrase(answer, "still") or contains_phrase(answer, "persisted")
                 or contains_phrase(answer, "after signing back in")
                 or contains_phrase(answer, "remained")),
                "expected the answer to confirm the details persisted after signing back in")
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
