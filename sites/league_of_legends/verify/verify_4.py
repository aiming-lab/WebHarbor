#!/usr/bin/env python3
"""Verify League of Legends--4: noisy 'Ruined King' site search -> kit -> favorite.

Honest chain (16 atomic actions): search icon -> fill q='Ruined King' -> Search ->
open the first champion card (Viego) -> E panel -> back to results -> open the
highest-ranked news card -> back -> open Viego again -> Sign in to Favorite ->
fill email -> fill password -> submit -> Add to Favorites -> My Account -> answer.

Frozen ground truth (seed DB):
  * /search?q=Ruined King reports Champions (60) and News (29).
  * First champion result: Viego, epithet 'The Ruined King' (Fighter/Assassin,
    Medium). Passive "Sovereign's Domination" (possess defeated enemies' wraiths,
    heal, basic abilities + items, his R replaces theirs); E "Harrowed Path"
    (Black Mist terrain: camouflage, Move Speed, Attack Speed).
  * Highest-ranked news result: 'Ruined King: Gameplay Deep Dive'
    (id 203, category riot_games, published 2020-12-11).
  * alice_j (id 1) gains exactly one favorite row (Viego, champion id 152)
    -> 6 favorites total.
"""
from verify_lib import (bound_count, bound_date, bound_phrase,
                        champion_named, check_favorites_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_count,
                        contains_phrase_loose, final_answer, navigated_champion,
                        navigated_to_path, navigated_to_path_any,
                        navigated_search_with, run_verifier)

TASK_ID = "League of Legends--4"
EMAIL = "alice.j@test.com"
VIEGO = (1, 152, "2026-09-22")
DEEP_DIVE = "/news/riot_games/ruined-king-gameplay-deep-dive/"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_search_ruined_king",
                navigated_search_with(traj, ["ruined", "king"]),
                "required: /search with q containing 'ruined' and 'king'")
    judge.check("visited_viego_page", navigated_champion(traj, "viego"),
                "required: /champions/viego/")
    judge.check("visited_deep_dive_article", navigated_to_path(traj, DEEP_DIVE),
                f"required: {DEEP_DIVE}")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_favorites",
                navigated_to_path_any(traj, ["/account", "/account/favorites"]),
                "required: /account or /account/favorites")

    judge.check("answer_champion_cards_60",
                bound_count(answer, 60, ["champion", "champions"], ["news"]),
                "expected 60 champion cards reported, attached to the champion results")
    judge.check("answer_news_results_29",
                bound_count(answer, 29, ["news"], ["champion", "champions"]),
                "expected 29 news results reported, attached to the news results")
    judge.check("answer_viego_identified", champion_named(answer, "Viego"),
                "expected Viego identified as the first champion result")
    judge.check("answer_viego_epithet", bound_phrase(answer, "The Ruined King", "Viego", mode="after"),
                "expected Viego's epithet 'The Ruined King' attached to Viego")
    judge.check("answer_article_title",
                contains_phrase_loose(answer, "Ruined King Gameplay Deep Dive"),
                "expected 'Ruined King: Gameplay Deep Dive' as the top news result")
    judge.check("answer_article_date",
                bound_date(answer, "2020-12-11", "Ruined King Gameplay Deep Dive", ["Viego"], mode="after"),
                "expected the article's 2020-12-11 date attached to its title")
    judge.check("answer_passive_semantics",
                bound_phrase(answer, "Sovereign's Domination", "passive", ["E"], mode="after") and
                bound_phrase(answer, "wraith", "Sovereign's Domination", ["Harrowed Path"], mode="after"),
                "expected the Sovereign's Domination wraith possession attached to the passive")
    judge.check("answer_harrowed_path", bound_phrase(answer, "Harrowed Path", "E", ["passive"], mode="after"),
                "expected Viego's E 'Harrowed Path' attached to the E slot")
    judge.check("answer_added_viego", champion_named(answer, "Viego"),
                "expected Viego named as the added pick")
    judge.check("answer_new_total_6", contains_count(answer, 6),
                "expected the account's new total of 6 favorites")

    check_favorites_delta(judge, initial_db, after_db, added=[VIEGO])
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
