#!/usr/bin/env python3
"""Verify League of Legends--5: Pulsefire roster search -> difficulty refilters.

Honest chain (20 atomic actions): Champions nav -> fill q='Pulsefire' -> Apply ->
select difficulty=High -> Apply -> open Ekko -> back -> open Riven -> back ->
open Twisted Fate -> back -> select difficulty=Low -> Apply -> open Fiora ->
Sign in to Favorite -> fill email -> fill password -> submit -> Add to Favorites
-> My Account -> answer.

Frozen ground truth (seed DB): the 'Pulsefire' roster search returns exactly ten
champion cards — Caitlyn, Ekko, Ezreal, Fiora, Lucian, Pantheon, Riven, Shen,
Thresh, Twisted Fate.
  * With High difficulty: Ekko, Riven, Twisted Fate.
  * With Low difficulty: Fiora only ('Pulsefire Fiora' in her skins).
  * carol_d (id 3) gains exactly one favorite row (Fiora, champion id 35)
    -> 6 favorites total.
"""
from verify_lib import (champion_count_named, champion_named,
                        check_favorites_delta, check_only_tables_changed,
                        check_signed_in_as, check_trajectory_identity,
                        contains_count, contains_phrase_loose, final_answer,
                        navigated_champion, navigated_champions_listing,
                        navigated_to_path_any, near_any, run_verifier)

TASK_ID = "League of Legends--5"
EMAIL = "carol.d@test.com"
FIORA = (3, 35, "2026-09-22")
HOLDERS = ["Caitlyn", "Ekko", "Ezreal", "Fiora", "Lucian",
           "Pantheon", "Riven", "Shen", "Thresh", "Twisted Fate"]
HIGH_TRIO = ["Ekko", "Riven", "Twisted Fate"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_roster_search_pulsefire",
                navigated_champions_listing(traj, {"q": "Pulsefire"}),
                "required: /champions/ with q=Pulsefire")
    judge.check("visited_roster_pulsefire_high",
                navigated_champions_listing(traj, {"q": "Pulsefire", "difficulty": "High"}),
                "required: /champions/ with q=Pulsefire and difficulty=High")
    judge.check("visited_roster_pulsefire_low",
                navigated_champions_listing(traj, {"q": "Pulsefire", "difficulty": "Low"}),
                "required: /champions/ with q=Pulsefire and difficulty=Low")
    judge.check("visited_high_holder_page",
                navigated_champion(traj, ["ekko", "riven", "twistedfate"]),
                "required: one of /champions/ekko|riven|twistedfate/ (High-difficulty confirmation)")
    judge.check("visited_fiora_page", navigated_champion(traj, "fiora"),
                "required: /champions/fiora/")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_favorites",
                navigated_to_path_any(traj, ["/account", "/account/favorites"]),
                "required: /account or /account/favorites")

    judge.check("answer_holder_count_10", contains_count(answer, 10),
                "expected 10 Pulsefire holder cards reported")
    judge.check("answer_all_holders_named", champion_count_named(answer, HOLDERS) == 10,
                f"expected all ten holders named: {HOLDERS}")
    judge.check("answer_high_trio", all(champion_count_named(answer, [n]) >= 1 for n in HIGH_TRIO),
                f"expected Ekko, Riven and Twisted Fate identified as High difficulty")
    judge.check("answer_low_holder_fiora", near_any(answer, "Fiora", ["Low"], radius=200),
                "expected Fiora identified as the Low-difficulty holder")
    judge.check("answer_pulsefire_fiora_skin", contains_phrase_loose(answer, "Pulsefire Fiora"),
                "expected the skin 'Pulsefire Fiora' named from her page")
    judge.check("answer_added_fiora", champion_named(answer, "Fiora"),
                "expected Fiora named as the added pick")
    judge.check("answer_new_total_6", contains_count(answer, 6),
                "expected the account's new total of 6 favorites")

    check_favorites_delta(judge, initial_db, after_db, added=[FIORA])
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
