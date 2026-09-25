#!/usr/bin/env python3
"""Verify Ohio.gov--7.

OHID registration chain: create the maria_g account, edit the profile so the
display name is "Maria Gonzalez" and the mailing address is 250 High St,
Columbus, Ohio 43215, and confirm both appear in account settings.

Frozen ground truth: the account did not exist in the seed; after the task the
users table gains exactly one row — username maria_g, email
maria.g@test.com, display_name "Maria Gonzalez", address_line1 "250 High St",
city "Columbus", state "Ohio", zip "43215".
"""
from verify_lib import (check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_phrase, entered_identity,
                        final_answer, run_verifier, user_by_email)

TASK_ID = "Ohio.gov--7"
NEW_EMAIL = "maria.g@test.com"
NEW_USERNAME = "maria_g"
DISPLAY_NAME = "Maria Gonzalez"
ADDRESS = "250 High St"
CITY = "Columbus"
STATE = "Ohio"
ZIP = "43215"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: register + profile edit + account confirmation
    check_visited_path(judge, traj, "visited_register", "/register")
    check_visited_path(judge, traj, "visited_account_edit", "/account/edit")
    check_visited_path(judge, traj, "visited_account", "/account")
    judge.check("entered_registration_identity",
                entered_identity(traj, NEW_USERNAME) and entered_identity(traj, NEW_EMAIL),
                f"expected {NEW_USERNAME!r} and {NEW_EMAIL!r} in input steps")
    # DB after-state: exactly one new user with the exact profile fields
    from verify_lib import added_users
    added = added_users(after_db, initial_db)
    judge.check("one_user_added", len(added) == 1,
                f"added_users={[u['username'] for u in added]!r}")
    if added:
        u = added[0]
        judge.check("added_user_identity",
                   (u["username"] or "").lower() == NEW_USERNAME
                   and (u["email"] or "").lower() == NEW_EMAIL,
                   f"username={u['username']!r}, email={u['email']!r}")
        judge.check("added_user_display_name", (u["display_name"] or "") == DISPLAY_NAME,
                   f"display_name={u['display_name']!r}")
        judge.check("added_user_address",
                   (u["address_line1"] or "") == ADDRESS and (u["city"] or "") == CITY
                   and (u["state"] or "") == STATE and (u["zip"] or "") == ZIP,
                   f"address={u['address_line1']!r}, city={u['city']!r}, "
                   f"state={u['state']!r}, zip={u['zip']!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("users",))
    # answer: username + address as shown in account settings
    judge.check("answer_username", contains_phrase(answer, NEW_USERNAME),
                f"expected username {NEW_USERNAME!r}")
    judge.check("answer_address",
                contains_phrase(answer, "250 high st") and contains_phrase(answer, "43215")
                and contains_phrase(answer, "columbus"),
                "expected the address 250 High St, Columbus, Ohio 43215")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
