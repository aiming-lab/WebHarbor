#!/usr/bin/env python3
"""Verify JCPenney--22."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--22"


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_all,
                        contains_phrase, final_answer, run_verifier, stable_password_hash,
                        table_delta)

TASK_ID = "JCPenney--22"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_profile", "/account/dashboard/profile")
    check_visited_path(judge, traj, "visited_signin_again", "/signin")
    # Frozen ground truth: the wrong-password flash reads "The email or password you
    # entered is incorrect. Please try again."; the new password is pinned by the task
    # (AutumnWalk45!) so carol's row must carry exactly its frozen hash afterwards.
    judge.check("answer_old_password_error",
                contains_phrase(answer, "email or password you entered is incorrect"),
                "expected the exact sign-in error message")
    judge.check("answer_old_password_fails",
                contains_any(answer, ["no longer", "does not work", "doesn't work", "did not work",
                                      "didn't work", "old password", "rejected"]),
                "expected the answer to state the old password no longer works")
    judge.check("answer_new_password_works",
                contains_any(answer, ["Hello, Carol", "AutumnWalk45!"]) and
                (contains_phrase(answer, "sign") or contains_phrase(answer, "dashboard")),
                "expected the report that the new password signs in (dashboard shows Hello, Carol)")
    check_only_tables_changed(judge, initial_db, after_db, ("users",))
    delta = table_delta(initial_db, after_db, "users")
    judge.check("users_delta_one_changed",
                len(delta["changed"]) == 1 and not delta["added"] and not delta["removed"],
                f"users delta: changed={len(delta['changed'])}, added={len(delta['added'])}, "
                f"removed={len(delta['removed'])}")
    if delta["changed"]:
        before_row, after_row = delta["changed"][0]
        cols = [r["name"] for r in __import__("verify_lib").db_query(initial_db, "PRAGMA table_info(users)")]
        before, after = dict(zip(cols, before_row)), dict(zip(cols, after_row))
        judge.check("changed_user_is_carol",
                    before.get("email") == "carol.d@test.com",
                    f"changed user email={before.get('email')!r}")
        judge.check("password_hash_updated",
                    after.get("password_hash") == stable_password_hash("AutumnWalk45!"),
                    "expected carol's password hash to be the frozen AutumnWalk45! hash")
        judge.check("only_password_hash_changed",
                    {k: v for k, v in after.items() if k != "password_hash"}
                    == {k: v for k, v in before.items() if k != "password_hash"},
                    "no user column other than password_hash may change")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
