#!/usr/bin/env python3
"""Verify LandWatch--10 — alice.j@test.com profile update + saved preference.

Ground truth (frozen seed): saving the validated profile edit flashes
'Profile updated.' and the My LandWatch profile card shows the new phone
(512) 555-0164; alice's users row carries the new phone with her name
unchanged. Saving the Montana land-for-sale page stores the h1-derived name
'Montana Land for Sale - 1-8 of 8 Listings' with URL /montana-land-for-sale;
alice ends up with 4 saved searches (3 seeded + the new one).
"""

from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, expected_session_token,
                        final_answer, run_verifier, table_delta)

TASK_ID = "LandWatch--10"
ALICE_EMAIL = "alice.j@test.com"
NEW_PHONE = "(512) 555-0164"
MONTANA = "/montana-land-for-sale"
SAVED_NAME = "Montana Land for Sale - 1-8 of 8 Listings"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE_EMAIL)
    # navigation gates
    check_visited_path(judge, traj, "visited_account_edit", "/account/edit")
    check_visited_path(judge, traj, "visited_montana_page", MONTANA)
    check_visited_path(judge, traj, "visited_account_page", "/account")
    # exactly the allowed tables changed
    check_only_tables_changed(judge, initial_db, after_db,
                              {"sessions", "users", "saved_searches"})
    # session delta: exactly alice's deterministic session token
    sessions = table_delta(initial_db, after_db, "sessions")
    judge.check("exactly_one_session_added",
                sessions["removed"] == [] and len(sessions["added"]) == 1
                and sessions["changed"] == [],
                f"sessions delta={sessions!r}")
    if sessions["added"]:
        judge.check("session_is_alices",
                    sessions["added"][0][0] == expected_session_token(1, ALICE_EMAIL)
                    and sessions["added"][0][1] == 1,
                    f"expected alice's session token, observed {sessions['added'][0]!r}")
    # users delta: exactly alice's phone updated, name (and identity) unchanged
    users = table_delta(initial_db, after_db, "users")
    judge.check("only_alice_user_row_changed",
                users["added"] == [] and users["removed"] == []
                and len(users["changed"]) == 1,
                f"users delta={users!r}")
    if users["changed"]:
        before, after = users["changed"][0]
        judge.check("alice_phone_updated", after[4] == NEW_PHONE,
                    f"expected phone {NEW_PHONE!r}, observed {after[4]!r}")
        judge.check("alice_name_unchanged", after[3] == "Alice Johnson",
                    f"expected name 'Alice Johnson', observed {after[3]!r}")
    # saved_searches delta: exactly one row for the Montana page
    searches = table_delta(initial_db, after_db, "saved_searches")
    judge.check("exactly_one_saved_search_added",
                searches["removed"] == [] and len(searches["added"]) == 1
                and searches["changed"] == [],
                f"saved_searches delta={searches!r}")
    if searches["added"]:
        row = searches["added"][0]
        judge.check("saved_search_belongs_to_alice", row[1] == 1, f"row={row!r}")
        judge.check("saved_search_name", row[2] == SAVED_NAME,
                    f"expected {SAVED_NAME!r}, observed {row[2]!r}")
        judge.check("saved_search_url", row[3] == MONTANA,
                    f"expected url {MONTANA!r}, observed {row[3]!r}")
    # answer gates
    judge.check("answer_success_message", contains_phrase(answer, "Profile updated"),
                "expected the success message 'Profile updated.'")
    judge.check("answer_confirms_new_phone", "(512) 555-0164" in answer
                or "512-555-0164" in answer or "512 555 0164" in answer,
                "expected the new phone (512) 555-0164 in the answer")
    judge.check("answer_saved_search_name",
                contains_phrase(answer, "Montana Land for Sale")
                and contains_phrase(answer, "1-8 of 8 Listings"),
                f"expected the stored name {SAVED_NAME!r}")
    judge.check("answer_saved_search_total", contains_count(answer, 4),
                "expected the account to end up with 4 saved searches")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
