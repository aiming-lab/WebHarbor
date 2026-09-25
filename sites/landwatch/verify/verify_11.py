#!/usr/bin/env python3
"""Verify LandWatch--11 — new-buyer onboarding: register, favorite, inquire, read back.

Ground truth (frozen seed): registering new.landbuyer@test.com /
LandBuyer2026! lands on My LandWatch with the empty states 'You haven't
saved any properties yet. Tap the heart icon on any listing to save it
here.' (Favorites), 'No saved searches yet. Use the Save Search button on
any search results page.' (Saved Searches), and 'No inquiries yet. Use the
contact form on any listing page.' (My Inquiries). Favoriting the Boerne
listing '43 ac Iron Rapids Ranch' adds exactly one favorites row (pid
424029660) for the new user; sending the Prime Ohio Farmland agent a soil
question flashes 'Your message has been sent to the listing agent.' and
writes exactly one inquiries row (pid 427843237) whose message asks about
soil, with the submitter's name and email.
"""

from verify_lib import (Judge, REGISTERED_EMAIL, REGISTERED_PASSWORD_HASH,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_phrase, entered_identity,
                        expected_session_token, final_answer, normalize_text,
                        run_verifier, table_delta)

TASK_ID = "LandWatch--11"
BOERNE_RESULTS = "/texas-land-for-sale/boerne"
IRON_RAPIDS_PID = 424029660
OHIO_DETAIL = "/allen-county-ohio-farms-and-ranches-for-sale/pid/427843237"
CONFIRMATION = "Your message has been sent to the listing agent."
NEW_USER_ID = 5


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates
    check_visited_path(judge, traj, "visited_register_page", "/register")
    judge.check("entered_registration_identity",
                entered_identity(traj, REGISTERED_EMAIL),
                f"expected {REGISTERED_EMAIL!r} in an input step")
    check_visited_path(judge, traj, "visited_boerne_results", BOERNE_RESULTS)
    check_visited_path(judge, traj, "visited_ohio_farmland_detail", OHIO_DETAIL)
    check_visited_path(judge, traj, "visited_account_page", "/account")
    # exactly the allowed tables changed
    check_only_tables_changed(judge, initial_db, after_db,
                              {"sessions", "users", "favorites", "inquiries"})
    # users delta: exactly the one new registration with the frozen hash
    users = table_delta(initial_db, after_db, "users")
    judge.check("exactly_one_user_added",
                users["removed"] == [] and len(users["added"]) == 1
                and users["changed"] == [],
                f"users delta={users!r}")
    new_user_id = NEW_USER_ID
    if users["added"]:
        row = users["added"][0]
        # row: id, email, password_hash, name, phone, created_at, is_benchmark
        judge.check("registered_email", row[1] == REGISTERED_EMAIL,
                    f"expected {REGISTERED_EMAIL!r}, observed {row[1]!r}")
        judge.check("registered_password_hash", row[2] == REGISTERED_PASSWORD_HASH,
                    "expected the frozen hash of LandBuyer2026!")
        judge.check("registered_not_benchmark_flag", row[6] in (0, None),
                    f"expected is_benchmark false, observed {row[6]!r}")
        new_user_id = row[0]
    # session delta: exactly the new user's deterministic session token
    sessions = table_delta(initial_db, after_db, "sessions")
    judge.check("exactly_one_session_added",
                sessions["removed"] == [] and len(sessions["added"]) == 1
                and sessions["changed"] == [],
                f"sessions delta={sessions!r}")
    if sessions["added"]:
        judge.check("session_is_new_users",
                    sessions["added"][0][0] == expected_session_token(new_user_id, REGISTERED_EMAIL)
                    and sessions["added"][0][1] == new_user_id,
                    f"expected the new user's session token, observed {sessions['added'][0]!r}")
    # favorites delta: exactly the Boerne listing saved by the new user
    favorites = table_delta(initial_db, after_db, "favorites")
    judge.check("exactly_one_favorite_added",
                favorites["removed"] == [] and favorites["changed"] == []
                and len(favorites["added"]) == 1,
                f"favorites delta={favorites!r}")
    if favorites["added"]:
        row = favorites["added"][0]
        judge.check("favorite_belongs_to_new_user", row[1] == new_user_id,
                    f"expected user_id {new_user_id}, observed {row[1]!r}")
        judge.check("favorite_is_iron_rapids", row[2] == IRON_RAPIDS_PID,
                    f"expected pid {IRON_RAPIDS_PID} ('43 ac Iron Rapids Ranch'), observed {row[2]!r}")
    # inquiries delta: exactly one soil question on Prime Ohio Farmland
    inquiries = table_delta(initial_db, after_db, "inquiries")
    judge.check("exactly_one_inquiry_added",
                inquiries["removed"] == [] and len(inquiries["added"]) == 1
                and inquiries["changed"] == [],
                f"inquiries delta={inquiries!r}")
    if inquiries["added"]:
        row = inquiries["added"][0]
        # row: id, user_id, pid, name, email, phone, message, created_at
        judge.check("inquiry_belongs_to_new_user", row[1] == new_user_id,
                    f"expected user_id {new_user_id}, observed {row[1]!r}")
        judge.check("inquiry_for_ohio_farmland", row[2] == 427843237,
                    f"expected pid 427843237, observed {row[2]!r}")
        judge.check("inquiry_message_asks_about_soil",
                    bool(normalize_text(row[6])) and "soil" in normalize_text(row[6]),
                    f"expected a message about soil quality, observed {row[6]!r}")
        judge.check("inquiry_email_present", "@" in (row[4] or ""),
                    f"expected a valid submitter email, observed {row[4]!r}")
    # answer gates
    judge.check("answer_heading", contains_phrase(answer, "My LandWatch"),
                "expected the 'My LandWatch' heading")
    judge.check("answer_favorites_empty_state",
                contains_phrase(answer, "haven't saved any properties")
                and contains_phrase(answer, "heart icon"),
                "expected the Favorites empty-state text")
    judge.check("answer_searches_empty_state",
                contains_phrase(answer, "No saved searches yet")
                and contains_phrase(answer, "Save Search button"),
                "expected the Saved Searches empty-state text")
    judge.check("answer_inquiries_empty_state",
                contains_phrase(answer, "No inquiries yet")
                and contains_phrase(answer, "contact form"),
                "expected the My Inquiries empty-state text")
    judge.check("answer_names_saved_property",
                contains_phrase(answer, "43 ac Iron Rapids Ranch"),
                "expected the saved property '43 ac Iron Rapids Ranch'")
    judge.check("answer_confirmation", contains_phrase(answer, CONFIRMATION),
                f"expected the confirmation {CONFIRMATION!r}")
    judge.check("answer_echoes_soil_question", contains_phrase(answer, "soil"),
                "expected the read-back inquiry record to mention soil")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
