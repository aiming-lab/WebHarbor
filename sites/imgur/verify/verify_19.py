#!/usr/bin/env python3
"""Verify the follow-tampacl flow in Imgur--19."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_count,
                        contains_phrase, final_answer, follow_user_pairs, run_verifier,
                        table_delta)

TASK_ID = "Imgur--19"
DAVID_EMAIL = "david.k@test.com"
DAVID_USER_ID = 990000004
TAMPACL_USER_ID = 28352345
PROFILE_PATH = "/user/tampacl"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, DAVID_EMAIL, "david_k")
    check_visited_path(judge, traj, "visited_tampacl_profile", PROFILE_PATH)
    # Navigation gate: the FOLLOWING count renders on the account settings page.
    check_visited_path(judge, traj, "visited_account_settings", "/account")
    # DB after-state: exactly one follow_user row added (david -> tampacl).
    check_only_tables_changed(judge, initial_db, after_db, {"follow_user"})
    delta = table_delta(initial_db, after_db, "follow_user")
    judge.check("exactly_one_follow_added",
                delta["removed"] == [] and len(delta["added"]) == 1 and len(delta["changed"]) == 0,
                f"follow_user delta={delta!r}")
    observed = follow_user_pairs(after_db, DAVID_USER_ID)
    judge.check("david_follows_tampacl_after_flow",
                observed == sorted(set(follow_user_pairs(initial_db, DAVID_USER_ID)) | {TAMPACL_USER_ID}),
                f"expected david's followees to gain tampacl, observed {observed!r}")
    # Frozen ground truth: the button label flips to FOLLOWING; david's seeded follow
    # count (1) grows to 2 on the account settings page.
    judge.check("answer_button_new_label", contains_phrase(answer, "FOLLOWING"),
                "expected the button's new label FOLLOWING")
    judge.check("answer_following_count", contains_count(answer, 2),
                "expected 2 FOLLOWING on the account settings page")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
