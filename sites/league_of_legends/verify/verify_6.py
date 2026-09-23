#!/usr/bin/env python3
"""Verify League of Legends--6: patch detective (26.19/26.18) -> Aatrox page -> favorite.

Honest chain (18 atomic actions): Patch Notes nav -> open 26.19 -> back ->
open 26.18 -> back -> Champions nav -> fill q='Aatrox' -> Apply -> open Aatrox ->
W panel -> E panel -> Sign in to Favorite -> fill email -> fill password ->
submit -> Add to Favorites -> My Account -> answer.

Frozen ground truth (seed DB):
  * Two most recent patch notes: 'League of Legends Patch 26.19 Notes'
    (2026-09-22) and 'League of Legends Patch 26.18 Notes' (2026-09-09).
  * 26.19 Aatrox W change: 'W - Infernal Chains Cooldown: 20 / 18 / 16 / 14 / 12
    seconds => 18 / 16.5 / 15 / 13.5 / 12 seconds'.
  * Aatrox page: W 'Infernal Chains', E 'Umbral Dash' (dash with healing).
  * david_k (id 4) gains exactly one favorite row (Aatrox, champion id 1)
    -> 6 favorites total.
"""
from verify_lib import (champion_named, check_favorites_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_count,
                        contains_decimal_sequence, contains_iso_date,
                        contains_phrase, contains_phrase_loose, final_answer,
                        navigated_champion, navigated_patch_notes,
                        navigated_to_path, navigated_to_path_any, run_verifier)

TASK_ID = "League of Legends--6"
EMAIL = "david.k@test.com"
AATROX = (4, 1, "2026-09-22")
PATCH_2619 = "/news/game-updates/league-of-legends-patch-26-19-notes/"
PATCH_2618 = "/news/game-updates/league-of-legends-patch-26-18-notes/"
NEW_COOLDOWNS = ["18", "16.5", "15", "13.5", "12"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_patch_notes_listing", navigated_patch_notes(traj),
                "required: /patch-notes")
    judge.check("visited_patch_2619", navigated_to_path(traj, PATCH_2619),
                f"required: {PATCH_2619}")
    judge.check("visited_patch_2618", navigated_to_path(traj, PATCH_2618),
                f"required: {PATCH_2618}")
    judge.check("visited_aatrox_page", navigated_champion(traj, "aatrox"),
                "required: /champions/aatrox/")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_favorites",
                navigated_to_path_any(traj, ["/account", "/account/favorites"]),
                "required: /account or /account/favorites")

    judge.check("answer_patch_2619_title", contains_phrase(answer, "League of Legends Patch 26.19 Notes"),
                "expected the 26.19 patch title")
    judge.check("answer_patch_2619_date", contains_iso_date(answer, "2026-09-22"),
                "expected the 26.19 date 2026-09-22")
    judge.check("answer_patch_2618_title", contains_phrase(answer, "League of Legends Patch 26.18 Notes"),
                "expected the 26.18 patch title")
    judge.check("answer_patch_2618_date", contains_iso_date(answer, "2026-09-09"),
                "expected the 26.18 date 2026-09-09")
    judge.check("answer_old_cooldown_ladder",
                contains_count(answer, 20) and contains_count(answer, 16),
                "expected the old 20/18/16/14/12 cooldown values")
    judge.check("answer_new_cooldown_ladder",
                contains_decimal_sequence(answer, NEW_COOLDOWNS),
                "expected the new cooldown ladder 18/16.5/15/13.5/12")
    judge.check("answer_w_name", contains_phrase_loose(answer, "Infernal Chains"),
                "expected the W ability 'Infernal Chains'")
    judge.check("answer_e_name", contains_phrase_loose(answer, "Umbral Dash"),
                "expected the E ability 'Umbral Dash'")
    judge.check("answer_e_heal_semantics", contains_phrase(answer, "heal"),
                "expected the E healing effect reported")
    judge.check("answer_added_aatrox", champion_named(answer, "Aatrox"),
                "expected Aatrox named as the added pick")
    judge.check("answer_new_total_6", contains_count(answer, 6),
                "expected the account's new total of 6 favorites")

    check_favorites_delta(judge, initial_db, after_db, added=[AATROX])
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
