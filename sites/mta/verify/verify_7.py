#!/usr/bin/env python3
"""Verify MTA--7.

Log in as alice.j@test.com. She switches her commute from the 2 and 5 trains
to the Q line: update her favorite services and service-alert subscriptions
(keeping the LIRR Babylon Branch favorite), then confirm both lists.

Frozen ground truth (seed DB): alice's seed favorites are (subway,2),
(subway,5), (rail,Babylon Branch); subscriptions (subway,2), (subway,5).
After the task: favorites exactly {(subway,Q), (rail,Babylon Branch)};
subscriptions exactly {(subway,Q)}. Read-only for every other user/table.
"""
from verify_lib import (SEED_USERS, check_only_tables_changed, check_seed_contract,
                        check_trajectory_identity, contains_phrase, final_answer,
                        navigated_to_path, run_verifier, user_by_email, user_favorites,
                        user_subscriptions)

TASK_ID = "MTA--7"
EMAIL = "alice.j@test.com"
EXPECTED_FAVORITES = [("rail", "Babylon Branch"), ("subway", "Q")]
EXPECTED_SUBSCRIPTIONS = [("subway", "Q")]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_login", navigated_to_path(traj, "/account/login"),
                "required: /account/login")
    judge.check("visited_favorites", navigated_to_path(traj, "/account/favorites"),
                "required: /account/favorites")
    judge.check("visited_subscriptions", navigated_to_path(traj, "/account/subscriptions"),
                "required: /account/subscriptions")
    judge.check("answer_mentions_q", contains_phrase(answer, "q"),
                "answer must mention the Q line")
    judge.check("answer_confirms_babylon", contains_phrase(answer, "babylon"),
                "the LIRR Babylon Branch favorite is kept")
    user = user_by_email(after_db, EMAIL)
    judge.check("alice_present", user is not None, "alice.j@test.com must exist")
    if user:
        favs = user_favorites(after_db, user["id"])
        subs = user_subscriptions(after_db, user["id"])
        judge.check("favorites_exact", favs == EXPECTED_FAVORITES,
                    f"favorites={favs!r}, expected {EXPECTED_FAVORITES!r}")
        judge.check("subscriptions_exact", subs == EXPECTED_SUBSCRIPTIONS,
                    f"subscriptions={subs!r}, expected {EXPECTED_SUBSCRIPTIONS!r}")
    # other users' rows untouched
    for other_email, (uname, _, _) in SEED_USERS.items():
        if other_email == EMAIL:
            continue
        u0 = user_by_email(initial_db, other_email)
        u1 = user_by_email(after_db, other_email)
        if u0 and u1:
            judge.check(f"other_user_{uname}_favorites_unchanged",
                        user_favorites(initial_db, u0["id"]) == user_favorites(after_db, u1["id"]),
                        f"{uname} favorites changed")
            judge.check(f"other_user_{uname}_subs_unchanged",
                        user_subscriptions(initial_db, u0["id"]) == user_subscriptions(after_db, u1["id"]),
                        f"{uname} subscriptions changed")
    check_only_tables_changed(judge, initial_db, after_db, ("favorites", "alert_subscriptions"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
