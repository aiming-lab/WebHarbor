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
from verify_lib import (bound_phrase, champion_named, check_favorites_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_count,
                        final_answer, navigated_champion,
                        navigated_champions_listing, navigated_to_path_any,
                        run_verifier)

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
    judge.check("answer_ezreal_e", bound_phrase(answer, "Arcane Shift", "Ezreal", ["Lucian"], mode="after"),
                "expected Ezreal's E 'Arcane Shift' attached to Ezreal")
    judge.check("answer_lucian_e", bound_phrase(answer, "Relentless Pursuit", "Lucian", ["Ezreal"], mode="after"),
                "expected Lucian's E 'Relentless Pursuit' attached to Lucian")
    judge.check("answer_lucian_cooldown_trigger",
                bound_phrase(answer, "Lightslinger", "Lucian", ["Ezreal"], mode="after"),
                "expected Lightslinger attached to Lucian as what reduces his E cooldown")
    judge.check("answer_ezreal_roles",
                bound_phrase(answer, "Mage", "Ezreal", ["Lucian"], mode="after") and
                bound_phrase(answer, "Marksman", "Ezreal", ["Lucian"], mode="after", allow_misbound=True),
                "expected Ezreal's roles Marksman/Mage attached to Ezreal")
    judge.check("answer_lucian_roles",
                bound_phrase(answer, "Assassin", "Lucian", ["Ezreal"], mode="after") and
                bound_phrase(answer, "Marksman", "Lucian", ["Ezreal"], mode="after", allow_misbound=True),
                "expected Lucian's roles Marksman/Assassin attached to Lucian")

    check_favorites_delta(judge, initial_db, after_db, added=[EZREAL])
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
