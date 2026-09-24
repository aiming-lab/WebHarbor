#!/usr/bin/env python3
"""Verify League of Legends--12: favorites governance (remove Trundle, then Zac).

Honest chain (16 atomic actions): Play Now -> Sign In -> fill email -> fill
password -> submit -> My Account -> Favorite Champions -> open Trundle ->
Remove from Favorites -> My Account -> Favorite Champions (4 remain) -> open
Zac -> Remove from Favorites -> My Account -> Favorite Champions (3 remain) ->
answer.

Frozen ground truth (seed DB): carol_d (id 3) starts with 5 favorites (Jarvan IV,
Rell, Trundle, Udyr, Zac). After removing Trundle: Jarvan IV, Rell, Udyr, Zac
(4). After also removing Zac: Jarvan IV, Rell, Udyr (3). Database delta:
exactly two favorite_champions rows removed for carol (Trundle id 140, Zac
id 167) and nothing else.
"""
from verify_lib import (bound_phrase, champion_named, check_favorites_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, final_answer, navigated_champion,
                        navigated_to_path, navigated_to_path_any, run_verifier,
                        state_count_segment)

TASK_ID = "League of Legends--12"
EMAIL = "carol.d@test.com"
REMOVED = [(3, 140, "2026-09-22"), (3, 167, "2026-09-22")]
REMAIN_FIRST = ["Jarvan IV", "Rell", "Udyr", "Zac"]
REMAIN_FINAL = ["Jarvan IV", "Rell", "Udyr"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_trundle_page", navigated_champion(traj, "trundle"),
                "required: /champions/trundle/ (removal)")
    judge.check("visited_zac_page", navigated_champion(traj, "zac"),
                "required: /champions/zac/ (removal)")
    judge.check("visited_favorites_verification",
                navigated_to_path(traj, "/account") and
                navigated_to_path(traj, "/account/favorites"),
                "required: /account and /account/favorites verification visits")

    judge.check("answer_removed_trundle", champion_named(answer, "Trundle"),
                "expected Trundle named as removed")
    judge.check("answer_after_first_4",
                state_count_segment(answer, 4, "Trundle", ["Zac"], must_contain=["Zac"],
                                    mode="after"),
                "expected 4 favorites attached to the after-Trundle state, with Zac still listed")
    for name in REMAIN_FIRST:
        rivals = [r for r in ("Zac",) if r != name]
        judge.check(f"answer_first_remaining_{name.split()[0].lower()}",
                    champion_named(answer, name) and
                    bound_phrase(answer, name, "Trundle", rivals, mode="after",
                                 allow_misbound=True),
                    f"expected {name} reported among the favorites remaining after the first removal")
    judge.check("answer_final_3",
                state_count_segment(answer, 3, "Zac", ["Trundle"], forbid_after=["Zac"],
                                    mode="after"),
                "expected 3 favorites attached to the after-Zac state, without Zac in its list")
    for name in REMAIN_FINAL:
        judge.check(f"answer_final_remaining_{name.split()[0].lower()}",
                    champion_named(answer, name) and
                    bound_phrase(answer, name, "Zac", ["Trundle"], mode="after",
                                 allow_misbound=True),
                    f"expected {name} reported among the final favorites")

    check_favorites_delta(judge, initial_db, after_db, removed=REMOVED)
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
