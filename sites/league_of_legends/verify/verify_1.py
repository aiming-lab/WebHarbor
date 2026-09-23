#!/usr/bin/env python3
"""Verify League of Legends--1: Marksman x Medium E-ability comparison -> favorite.

Honest chain (17 atomic actions): Champions nav -> role=Marksman ->
difficulty=Medium -> Apply -> open Ezreal -> E panel -> back -> open Lucian ->
E panel -> Sign in to Favorite -> fill email -> fill password -> submit ->
Add to Favorites -> My Account -> answer.

Frozen ground truth (seed DB):
  * Marksman+Medium filter shows 24 champions (Ezreal and Lucian among them).
  * Ezreal (Marksman/Mage, Medium): E "Arcane Shift" teleports to a nearby
    location and fires a homing bolt.
  * Lucian (Marksman/Assassin, Medium): E "Relentless Pursuit" is a short dash;
    Lightslinger attacks reduce its cooldown.
  * The teleport pick is Ezreal; bob_c (id 2) gains exactly one favorite row
    (Ezreal, champion id 33) -> 6 favorites total.
"""
from verify_lib import (champion_named, check_favorites_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_count,
                        contains_phrase, contains_phrase_loose, final_answer, navigated_champion,
                        navigated_champions_listing, navigated_to_path_any,
                        near_any, run_verifier)

TASK_ID = "League of Legends--1"
EMAIL = "bob.c@test.com"
EZREAL = (2, 33, "2026-09-22")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_roster_filtered_marksman_medium",
                navigated_champions_listing(traj, {"role": "Marksman", "difficulty": "Medium"}),
                "required: /champions/ with role=Marksman and difficulty=Medium")
    judge.check("visited_ezreal_page", navigated_champion(traj, "ezreal"), "required: /champions/ezreal/")
    judge.check("visited_lucian_page", navigated_champion(traj, "lucian"), "required: /champions/lucian/")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_favorites",
                navigated_to_path_any(traj, ["/account", "/account/favorites"]),
                "required: /account or /account/favorites")

    judge.check("answer_added_ezreal", champion_named(answer, "Ezreal"),
                "expected Ezreal named as the added pick")
    judge.check("answer_new_total_6", contains_count(answer, 6),
                "expected the account's new total of 6 favorites")
    judge.check("answer_ezreal_e", contains_phrase_loose(answer, "Arcane Shift"),
                "expected Ezreal's E 'Arcane Shift'")
    judge.check("answer_lucian_e", contains_phrase_loose(answer, "Relentless Pursuit"),
                "expected Lucian's E 'Relentless Pursuit'")
    judge.check("answer_lucian_cooldown_trigger", contains_phrase(answer, "Lightslinger"),
                "expected Lightslinger named as what reduces Lucian's E cooldown")
    judge.check("answer_ezreal_roles", near_any(answer, "Ezreal", ["Marksman", "Mage"]),
                "expected Ezreal's roles Marksman/Mage near his name")
    judge.check("answer_lucian_roles", near_any(answer, "Lucian", ["Marksman", "Assassin"]),
                "expected Lucian's roles Marksman/Assassin near his name")

    check_favorites_delta(judge, initial_db, after_db, added=[EZREAL])
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
