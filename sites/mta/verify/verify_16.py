#!/usr/bin/env python3
"""Verify MTA--16.

Create a new MTA account (pat.gonzalez@example.net, pat_g, Pat Gonzalez,
PatStr0ng!2026), add the E train and the Metro-North Harlem Line to favorite
services, subscribe to E line service alerts, and report the OMNY card
serial number shown on the account page.

Frozen ground truth (seed DB): register derives omny_serial as
"OMNY-" + sha1(email)[:8].upper() — for pat.gonzalez@example.net that is
OMNY-5155F7F3. After the task the users table gains exactly this user with
favorites {(subway, E), (rail, Metro-North Harlem Line)} and one alert
subscription (subway, E).
"""
from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                        check_trajectory_identity, contains_phrase, final_answer,
                        navigated_to_path, run_verifier, rows_of, user_by_email,
                        user_favorites, user_subscriptions)

TASK_ID = "MTA--16"
EMAIL = "pat.gonzalez@example.net"
USERNAME = "pat_g"
DISPLAY = "Pat Gonzalez"
OMNY_SERIAL = "OMNY-5155F7F3"
EXPECTED_FAVORITES = [("rail", "Metro-North Harlem Line"), ("subway", "E")]
EXPECTED_SUBSCRIPTIONS = [("subway", "E")]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_register", navigated_to_path(traj, "/account/register"),
                "required: /account/register")
    judge.check("visited_favorites", navigated_to_path(traj, "/account/favorites"),
                "required: /account/favorites")
    judge.check("visited_subscriptions", navigated_to_path(traj, "/account/subscriptions"),
                "required: /account/subscriptions")
    judge.check("answer_omny_serial", contains_phrase(answer, OMNY_SERIAL.lower()),
                f"the OMNY card serial is {OMNY_SERIAL}")
    added = added_rows(after_db, initial_db, "users", "id")
    judge.check("one_user_added", len(added) == 1, f"added users={[r['email'] for r in added]!r}")
    if added:
        u = added[0]
        judge.check("added_user_email", (u["email"] or "").lower() == EMAIL, f"email={u['email']!r}")
        judge.check("added_user_username", u["username"] == USERNAME, f"username={u['username']!r}")
        judge.check("added_user_display", (u["display_name"] or "") == DISPLAY,
                    f"display_name={u['display_name']!r}")
        judge.check("added_user_omny_serial", u["omny_serial"] == OMNY_SERIAL,
                    f"omny_serial={u['omny_serial']!r}")
        favs = user_favorites(after_db, u["id"])
        subs = user_subscriptions(after_db, u["id"])
        judge.check("added_user_favorites", favs == EXPECTED_FAVORITES,
                    f"favorites={favs!r}, expected {EXPECTED_FAVORITES!r}")
        judge.check("added_user_subscriptions", subs == EXPECTED_SUBSCRIPTIONS,
                    f"subscriptions={subs!r}, expected {EXPECTED_SUBSCRIPTIONS!r}")
    # no other user's rows changed
    before_users = {r["email"] for r in rows_of(initial_db, "users")}
    after_users = {r["email"] for r in rows_of(after_db, "users")}
    judge.check("only_new_user_added", after_users - before_users == {EMAIL},
                f"new emails: {after_users - before_users}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("users", "favorites", "alert_subscriptions"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
