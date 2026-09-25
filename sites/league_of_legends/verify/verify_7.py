#!/usr/bin/env python3
"""Verify League of Legends--7: cross-patch detective (26.19 x 26.16) -> favorite.

Honest chain (20 atomic actions): Patch Notes nav -> open 26.19 -> back ->
open 26.16 -> back -> Champions nav -> fill q='Poppy' -> Apply -> open Poppy ->
back -> fill q='Nasus' -> Apply -> open Nasus -> Sign in to Favorite -> fill
email -> fill password -> submit -> Add to Favorites -> My Account -> answer.

Frozen ground truth (seed DB):
  * Patch 26.19 champion sections: Aatrox, Aphelios, Aurora, Draven, Elise,
    Fiora, Kha'Zix, Lillia, Lucian, Master Yi, Nasus, Nocturne, Poppy, Rumble,
    Ryze, Vi, Volibear.
  * Patch 26.16 champion sections: Azir, Bel'Veth, Camille, Gwen, Kennen, Nasus,
    Poppy. Intersection with 26.19: Nasus and Poppy.
  * Nasus (Fighter/Tank, Medium, id 90); Poppy (Tank/Fighter, Medium, id 101).
  * 26.16 Nasus Q - Siphoning Strike: 'Stacks: 3, increased to 12 on champions /
    large minions / monsters => 4, increased to 10 on champions / large
    minions / monsters'.
  * bob_c (id 2) gains exactly one favorite row (Nasus, champion id 90)
    -> 6 favorites total.
"""
from verify_lib import (bound_phrase, champion_named, check_favorites_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_count,
                        final_answer, navigated_champion, navigated_patch_notes,
                        navigated_to_path, navigated_to_path_any, phrases_in_order,
                        run_verifier)

TASK_ID = "League of Legends--7"
EMAIL = "bob.c@test.com"
NASUS = (2, 90, "2026-09-22")
PATCH_2619 = "/news/game-updates/league-of-legends-patch-26-19-notes/"
PATCH_2616 = "/news/game-updates/league-of-legends-patch-26-16-notes/"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_patch_notes_listing", navigated_patch_notes(traj),
                "required: /patch-notes")
    judge.check("visited_patch_2619", navigated_to_path(traj, PATCH_2619),
                f"required: {PATCH_2619}")
    judge.check("visited_patch_2616", navigated_to_path(traj, PATCH_2616),
                f"required: {PATCH_2616}")
    judge.check("visited_nasus_page", navigated_champion(traj, "nasus"),
                "required: /champions/nasus/")
    judge.check("visited_poppy_page", navigated_champion(traj, "poppy"),
                "required: /champions/poppy/")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_favorites",
                navigated_to_path_any(traj, ["/account", "/account/favorites"]),
                "required: /account or /account/favorites")

    judge.check("answer_identifies_nasus", champion_named(answer, "Nasus"),
                "expected Nasus identified as adjusted in both patches")
    judge.check("answer_identifies_poppy", champion_named(answer, "Poppy"),
                "expected Poppy identified as adjusted in both patches")
    judge.check("answer_nasus_roles",
                bound_phrase(answer, "Fighter", "Nasus", ["Poppy"], mode="after", allow_misbound=True) and
                bound_phrase(answer, "Tank", "Nasus", ["Poppy"], mode="after", allow_misbound=True),
                "expected Nasus's roles Fighter/Tank attached to Nasus")
    judge.check("answer_poppy_roles",
                bound_phrase(answer, "Tank", "Poppy", ["Nasus"], mode="after", allow_misbound=True) and
                bound_phrase(answer, "Fighter", "Poppy", ["Nasus"], mode="after", allow_misbound=True),
                "expected Poppy's roles Tank/Fighter attached to Poppy")
    judge.check("answer_both_medium",
                bound_phrase(answer, "Medium", "Nasus", ["Poppy"], mode="after", allow_misbound=True) and
                bound_phrase(answer, "Medium", "Poppy", ["Nasus"], mode="after", allow_misbound=True),
                "expected both champions rated Medium difficulty")
    judge.check("answer_q_ability", bound_phrase(answer, "Siphoning Strike", "Nasus", ["Poppy"], mode="after"),
                "expected Nasus's Q 'Siphoning Strike' attached to Nasus")
    judge.check("answer_stack_values",
                contains_count(answer, 3) and contains_count(answer, 12)
                and contains_count(answer, 4) and contains_count(answer, 10),
                "expected the stack values 3->12 and 4->10 quoted")
    judge.check("answer_stack_pairs_in_order",
                phrases_in_order(answer, ["3", "12"]) and phrases_in_order(answer, ["4", "10"]),
                "expected each base stack quoted before its increased-to value")
    judge.check("answer_stack_ladder_order",
                phrases_in_order(answer, ["3", "4"]),
                "expected the old base (3) quoted before the new base (4)")
    judge.check("answer_added_nasus", champion_named(answer, "Nasus"),
                "expected Nasus named as the added pick")
    judge.check("answer_new_total_6", contains_count(answer, 6),
                "expected the account's new total of 6 favorites")

    check_favorites_delta(judge, initial_db, after_db, added=[NASUS])
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
