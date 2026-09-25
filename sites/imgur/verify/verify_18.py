#!/usr/bin/env python3
"""Verify the bob bio-change flow in Imgur--18."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_phrase, final_answer,
                        navigated_to_path_with_params, run_verifier, table_delta)

TASK_ID = "Imgur--18"
BOB_EMAIL = "bob.c@test.com"
BOB_USER_ID = 990000002
NEW_BIO = "Part-time keyboard enthusiast, full-time dad joke connoisseur."
SEED_BIO = "Here for the wholesome stuff. Ask me about mechanical keyboards."


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, BOB_EMAIL, "bob_c")
    # Navigation gates: account settings page (the bio form) + the public ABOUT tab.
    judge.check("visited_account_settings",
                navigated_to_path_with_params(traj, "/account", {}),
                "required /account")
    judge.check("visited_public_about_tab",
                navigated_to_path_with_params(traj, "/user/bob_c", {"tab": "about"}),
                "required /user/bob_c?tab=about")
    # DB after-state: only the users table changes; exactly bob_c's bio column flips.
    check_only_tables_changed(judge, initial_db, after_db, {"users"})
    delta = table_delta(initial_db, after_db, "users")
    changed_ids = [row[0] for row, _ in delta["changed"]]
    judge.check("exactly_bob_row_changed",
                delta["added"] == [] and delta["removed"] == [] and len(delta["changed"]) == 1
                and changed_ids == [BOB_USER_ID],
                f"users delta={delta!r}")
    if delta["changed"]:
        from verify_lib import row_dict
        before = row_dict(initial_db, "users", delta["changed"][0][0])
        after = row_dict(initial_db, "users", delta["changed"][0][1])
        only_bio = {k for k in before if before[k] != after[k]}
        judge.check("only_bio_column_changed",
                    only_bio == {"bio"} and before["bio"] == SEED_BIO and after["bio"] == NEW_BIO,
                    f"changed columns={only_bio!r}, before={before['bio']!r}, after={after['bio']!r}")
    judge.check("answer_reports_new_bio", contains_phrase(answer, NEW_BIO),
                f"expected the new bio {NEW_BIO!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
