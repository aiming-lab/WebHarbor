#!/usr/bin/env python3
"""Verify League of Legends--21: bob adds Milio to favorites (stateful)."""
from verify_lib import (CHAMPION_IDS, SEED_USERS, check_only_tables_changed,
                        check_signed_in_as, check_trajectory_identity, contains_count,
                        final_answer, favorites_of, navigated_champion, navigated_to_path,
                        run_verifier, table_delta, user_by_email)

TASK_ID = "League of Legends--21"
EMAIL = "bob.c@test.com"
# bob_c seeds 5 favorites; after adding Milio (champion_id 84) the account has 6.
ADDED_CHAMPION_ID = CHAMPION_IDS["milio"]
EXPECTED_TOTAL = 6


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_milio_champion_page", navigated_champion(traj, "milio"),
                "required: /champions/milio/")
    judge.check("answer_total_after_add", contains_count(answer, EXPECTED_TOTAL),
                f"expected {EXPECTED_TOTAL} favorites after adding Milio")
    # state: exactly one favorite_champions row added — (bob, Milio) — nothing else
    user = user_by_email(after_db, EMAIL)
    judge.check("bob_exists_after", user is not None, "bob_c must still exist")
    bob_id = user["id"]
    delta = table_delta(initial_db, after_db, "favorite_champions")
    judge.check("favorite_added_exactly_one_row",
                len(delta["added"]) == 1 and len(delta["removed"]) == 0
                and len(delta["changed"]) == 0,
                f"expected exactly one added favorite row; delta={delta!r}")
    if delta["added"]:
        row = delta["added"][0]
        judge.check("favorite_added_is_bob_milio",
                   row[1] == bob_id and row[2] == ADDED_CHAMPION_ID,
                   f"expected (user_id={bob_id}, champion_id={ADDED_CHAMPION_ID}); got {row!r}")
    judge.check("bob_now_has_six_favorites",
                len(favorites_of(after_db, bob_id)) == EXPECTED_TOTAL,
                "bob_c must have exactly 6 favorites in the after DB")
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
