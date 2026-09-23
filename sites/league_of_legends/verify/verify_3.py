#!/usr/bin/env python3
"""Verify League of Legends--3: darkin roster survey -> favorite the Darkin Blade.

Honest chain (21 atomic actions): Champions nav -> fill q='darkin' -> Apply ->
open Aatrox -> back -> open Kayn -> back -> open Naafiri -> back -> open Varus ->
back -> open Zaahen -> back -> open Aatrox -> Sign in to Favorite -> fill email ->
fill password -> submit -> Add to Favorites -> My Account -> answer.

Frozen ground truth (seed DB): the 'darkin' roster search returns exactly five
champion cards:
  * Aatrox   — epithet 'the Darkin Blade', Fighter, Medium, 13 skins
  * Kayn     — epithet 'the Shadow Reaper', Fighter/Assassin, High, 8 skins
  * Naafiri  — epithet 'the Hound of a Hundred Bites', Assassin/Fighter, Low, 5
  * Varus    — epithet 'the Arrow of Retribution', Marksman/Mage, Low, 16
  * Zaahen   — epithet 'The Unsundered', Fighter, Low, 2
Aatrox is 'the Darkin Blade'; carol_d (id 3) gains exactly one favorite row
(Aatrox, champion id 1) -> 6 favorites total.
"""
from verify_lib import (champion_named, check_favorites_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_count,
                        contains_phrase_loose, final_answer, navigated_champion,
                        navigated_champions_listing, navigated_to_path_any,
                        near_any, run_verifier)

TASK_ID = "League of Legends--3"
EMAIL = "carol.d@test.com"
AATROX = (3, 1, "2026-09-22")
DARKIN = [
    ("aatrox", "Aatrox", "the Darkin Blade", "Darkin Blade"),
    ("kayn", "Kayn", "the Shadow Reaper", "Shadow Reaper"),
    ("naafiri", "Naafiri", "the Hound of a Hundred Bites", "Hound of a Hundred Bites"),
    ("varus", "Varus", "the Arrow of Retribution", "Arrow of Retribution"),
    ("zaahen", "Zaahen", "The Unsundered", "Unsundered"),
]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_roster_search_darkin",
                navigated_champions_listing(traj, {"q": "darkin"}),
                "required: /champions/ with q=darkin")
    for slug, name, epithet, _ in DARKIN:
        judge.check(f"visited_{slug}_page", navigated_champion(traj, slug),
                    f"required: /champions/{slug}/")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_favorites",
                navigated_to_path_any(traj, ["/account", "/account/favorites"]),
                "required: /account or /account/favorites")

    for slug, name, epithet, short in DARKIN:
        judge.check(f"answer_names_{slug}", champion_named(answer, name),
                    f"expected {name} named")
        judge.check(f"answer_epithet_{slug}", contains_phrase_loose(answer, short),
                    f"expected {name}'s epithet {epithet!r}")
    judge.check("answer_aatrox_roles_difficulty",
                near_any(answer, "Aatrox", ["Fighter", "Medium"]),
                "expected Aatrox's Fighter role and Medium difficulty")
    judge.check("answer_kayn_difficulty_high",
                near_any(answer, "Kayn", ["High"]),
                "expected Kayn rated High difficulty")
    judge.check("answer_added_aatrox", champion_named(answer, "Aatrox"),
                "expected Aatrox named as the added pick")
    judge.check("answer_new_total_6", contains_count(answer, 6),
                "expected the account's new total of 6 favorites")

    check_favorites_delta(judge, initial_db, after_db, added=[AATROX])
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
