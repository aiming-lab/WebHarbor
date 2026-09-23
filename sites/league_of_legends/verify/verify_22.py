#!/usr/bin/env python3
"""Verify League of Legends--22: carol removes Trundle from favorites (stateful)."""
from verify_lib import (CHAMPION_IDS, SEED_USERS, check_only_tables_changed,
                        check_signed_in_as, check_trajectory_identity, champion_named,
                        final_answer, favorites_of, navigated_champion, navigated_to_path,
                        norm, run_verifier, table_delta, user_by_email)
import re

TASK_ID = "League of Legends--22"
EMAIL = "carol.d@test.com"
REMOVED_CHAMPION_ID = CHAMPION_IDS["trundle"]
# carol_d seeds 5 favorites (Jarvan IV, Rell, Trundle, Udyr, Zac); after removing
# Trundle the remaining four are:
REMAINING = ["Jarvan IV", "Rell", "Udyr", "Zac"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_trundle_champion_page", navigated_champion(traj, "trundle"),
                "required: /champions/trundle/ (the remove control lives there)")
    missing = [n for n in REMAINING if not champion_named(answer, n)]
    judge.check("answer_remaining_names", not missing,
                f"expected remaining favorites {REMAINING!r}; missing={missing!r}")
    # Trundle may only appear in a removal context ("removed/removing Trundle"), never
    # listed as a remaining favorite.
    normalized = norm(answer)
    trundle_ok = all("remov" in normalized[max(0, m.start() - 80):m.start()]
                     for m in re.finditer(r"(?<!\w)trundle(?!\w)", normalized))
    judge.check("answer_no_trundle_as_remaining", trundle_ok,
                "Trundle may only be mentioned as removed, never listed among the "
                "remaining favorites")
    # state: exactly the (carol, Trundle) favorite row removed — nothing else
    user = user_by_email(after_db, EMAIL)
    judge.check("carol_exists_after", user is not None, "carol_d must still exist")
    carol_id = user["id"]
    delta = table_delta(initial_db, after_db, "favorite_champions")
    judge.check("favorite_removed_exactly_one_row",
                len(delta["removed"]) == 1 and len(delta["added"]) == 0
                and len(delta["changed"]) == 0,
                f"expected exactly one removed favorite row; delta={delta!r}")
    if delta["removed"]:
        row = delta["removed"][0]
        judge.check("favorite_removed_is_carol_trundle",
                   row[1] == carol_id and row[2] == REMOVED_CHAMPION_ID,
                   f"expected (user_id={carol_id}, champion_id={REMOVED_CHAMPION_ID}); got {row!r}")
    judge.check("carol_now_has_four_favorites",
                len(favorites_of(after_db, carol_id)) == 4,
                "carol_d must have exactly 4 favorites in the after DB")
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
