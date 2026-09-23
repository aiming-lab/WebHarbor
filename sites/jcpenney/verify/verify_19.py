#!/usr/bin/env python3
"""Verify JCPenney--19."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--19"


from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_phrase, final_answer,
                        run_verifier, stable_password_hash, table_delta)

TASK_ID = "JCPenney--19"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_register", "/register")
    check_visited_path(judge, traj, "visited_signin", "/signin")
    check_visited_path(judge, traj, "visited_dashboard", "/account/dashboard")
    # The registered credentials are agent-invented; the task pins the password
    # (Shopper123!), so the new user row must carry exactly that frozen hash.
    check_only_tables_changed(judge, initial_db, after_db, ("users",))
    delta = table_delta(initial_db, after_db, "users")
    judge.check("users_delta_one_added",
                len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"],
                f"users delta: added={len(delta['added'])}, removed={len(delta['removed'])}, "
                f"changed={len(delta['changed'])}")
    new_email, new_first = "", ""
    if delta["added"]:
        cols = [r["name"] for r in __import__("verify_lib").db_query(initial_db, "PRAGMA table_info(users)")]
        row = dict(zip(cols, delta["added"][0]))
        new_email = str(row.get("email", "")).lower()
        new_first = str(row.get("first_name", "")).strip()
        judge.check("new_user_email_fresh",
                    new_email not in {"alice.j@test.com", "bob.c@test.com",
                                      "carol.d@test.com", "david.k@test.com"}
                    and "@" in new_email,
                    f"new user email={new_email!r}")
        judge.check("new_user_password_pinned",
                    row.get("password_hash") == stable_password_hash("Shopper123!"),
                    "the task pins the password Shopper123! — the row hash must match")
    judge.check("answer_reports_email", bool(new_email) and new_email in answer.lower(),
                f"expected the registered email {new_email!r} in the answer")
    judge.check("answer_reports_account_name",
                bool(new_first) and __import__("verify_lib").phrases_in_order(
                    answer, ["Hello", new_first]),
                f"expected the dashboard greeting 'Hello, {new_first}' in the answer")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
