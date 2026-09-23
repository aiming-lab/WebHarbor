#!/usr/bin/env python3
"""Verify League of Legends--2: Most-skins roster sort -> top-two skin comparison.

Honest chain (17 atomic actions): Champions nav -> sort=skins -> Apply ->
open Miss Fortune -> R panel -> back -> open Lux -> R panel -> back ->
open Miss Fortune -> Sign in to Favorite -> fill email -> fill password ->
submit -> Add to Favorites -> My Account -> answer.

Frozen ground truth (seed DB):
  * Most-skins order, first five: Miss Fortune (24), Lux (23), Ahri (22),
    Akali (22), Ezreal (22).
  * Miss Fortune R "Bullet Time", 24 skins including base (non-base examples:
    Cowgirl/Secret Agent/Waterloo Miss Fortune ...).
  * Lux R "Final Spark", 23 skins including base (non-base examples:
    Sorceress/Spellthief/Commando Lux ...).
  * Miss Fortune is the pick; david_k (id 4) gains exactly one favorite row
    (Miss Fortune, champion id 85) -> 6 favorites total.
"""
from verify_lib import (champion_named, check_favorites_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_any,
                        contains_count, contains_phrase_loose, final_answer,
                        navigated_champion, navigated_champions_listing,
                        navigated_to_path_any, phrases_in_order, run_verifier)

TASK_ID = "League of Legends--2"
EMAIL = "david.k@test.com"
MISS_FORTUNE = (4, 85, "2026-09-22")
TOP_FIVE = ["Miss Fortune", "Lux", "Ahri", "Akali", "Ezreal"]
MF_NONBASE = ["Cowgirl Miss Fortune", "Waterloo Miss Fortune", "Secret Agent Miss Fortune",
              "Arcade Miss Fortune", "Candy Cane Miss Fortune", "Captain Fortune"]
LUX_NONBASE = ["Sorceress Lux", "Spellthief Lux", "Commando Lux", "Imperial Lux",
               "Steel Legion Lux", "Star Guardian Lux"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_roster_sorted_by_skins",
                navigated_champions_listing(traj, {"sort": "skins"}),
                "required: /champions/ with sort=skins")
    judge.check("visited_missfortune_page", navigated_champion(traj, "missfortune"),
                "required: /champions/missfortune/")
    judge.check("visited_lux_page", navigated_champion(traj, "lux"), "required: /champions/lux/")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_favorites",
                navigated_to_path_any(traj, ["/account", "/account/favorites"]),
                "required: /account or /account/favorites")

    judge.check("answer_top_five_in_order", phrases_in_order(answer, TOP_FIVE),
                f"expected the first five in order: {TOP_FIVE}")
    judge.check("answer_mf_ultimate", contains_phrase_loose(answer, "Bullet Time"),
                "expected Miss Fortune's ultimate 'Bullet Time'")
    judge.check("answer_lux_ultimate", contains_phrase_loose(answer, "Final Spark"),
                "expected Lux's ultimate 'Final Spark'")
    judge.check("answer_mf_skin_count_24", contains_count(answer, 24),
                "expected Miss Fortune's 24 skins")
    judge.check("answer_lux_skin_count_23", contains_count(answer, 23),
                "expected Lux's 23 skins")
    judge.check("answer_mf_nonbase_skin", contains_any(answer, MF_NONBASE),
                "expected one non-base Miss Fortune skin named")
    judge.check("answer_lux_nonbase_skin", contains_any(answer, LUX_NONBASE),
                "expected one non-base Lux skin named")
    judge.check("answer_added_missfortune", champion_named(answer, "Miss Fortune"),
                "expected Miss Fortune named as the added pick")
    judge.check("answer_new_total_6", contains_count(answer, 6),
                "expected the account's new total of 6 favorites")

    check_favorites_delta(judge, initial_db, after_db, added=[MISS_FORTUNE])
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
