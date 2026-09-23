#!/usr/bin/env python3
"""Verify League of Legends--9: article -> champion cross (Lee Sin ASU) -> double write.

Honest chain (22 atomic actions): search icon -> fill q='Modernizing the Monk' ->
Search -> open the article -> back -> Champions nav -> fill q='Lee Sin' -> Apply ->
open Lee Sin -> W panel -> R panel -> Sign in to Favorite -> fill email ->
fill password -> submit -> Add to Favorites -> search icon -> fill q ->
Search -> open the article -> Save Article -> My Account -> answer.

Frozen ground truth (seed DB):
  * '/dev: Modernizing the Monk' (id 82, dev, 2024-04-08) — authors
    ["The ASU Team"]; ASU = Art and Sustainability Update; subject: Lee Sin.
  * /search?q=Modernizing the Monk matches exactly 2 champion cards
    (Lee Sin and Wukong) and 1 news result.
  * Lee Sin page: W 'Safeguard / Iron Will', R "Dragon's Rage".
  * bob_c (id 2) gains one favorite row (Lee Sin, champion id 71) -> 6
    favorites, and one bookmark row (article id 82) -> 5 saved articles.
"""
from verify_lib import (champion_named, check_bookmarks_delta,
                        check_favorites_delta, check_only_tables_changed,
                        check_signed_in_as, check_trajectory_identity,
                        contains_count, contains_phrase,
                        contains_phrase_loose, final_answer, navigated_champion,
                        navigated_search_with, navigated_to_path,
                        navigated_to_path_any, run_verifier)

TASK_ID = "League of Legends--9"
EMAIL = "bob.c@test.com"
LEE_SIN = (2, 71, "2026-09-22")
MONK_BM = (2, 82, "2026-09-22")
MONK = "/news/dev/dev-modernizing-the-monk/"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_monk_article", navigated_to_path(traj, MONK),
                f"required: {MONK}")
    judge.check("visited_search_monk",
                navigated_search_with(traj, ["modernizing", "monk"]),
                "required: /search with q containing 'modernizing' and 'monk'")
    judge.check("visited_leesin_page", navigated_champion(traj, "leesin"),
                "required: /champions/leesin/")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account",
                navigated_to_path(traj, "/account"),
                "required: /account")

    judge.check("answer_author_team", contains_phrase(answer, "The ASU Team"),
                "expected 'The ASU Team' named as the author")
    judge.check("answer_asu_expansion",
                contains_phrase(answer, "Art and Sustainability Update"),
                "expected ASU expanded as Art and Sustainability Update")
    judge.check("answer_champion_cards_2", contains_count(answer, 2),
                "expected 2 matching champion cards reported")
    judge.check("answer_leesin_named", champion_named(answer, "Lee Sin"),
                "expected Lee Sin named as the updated champion")
    judge.check("answer_w_ability", contains_phrase_loose(answer, "Safeguard") and
                contains_phrase_loose(answer, "Iron Will"),
                "expected the W 'Safeguard / Iron Will'")
    judge.check("answer_r_ability", contains_phrase_loose(answer, "Dragon's Rage"),
                "expected the R \"Dragon's Rage\"")
    judge.check("answer_favorites_total_6", contains_count(answer, 6),
                "expected the account's new total of 6 favorites")
    judge.check("answer_saved_total_5", contains_count(answer, 5),
                "expected the account's new total of 5 saved articles")

    check_favorites_delta(judge, initial_db, after_db, added=[LEE_SIN])
    check_bookmarks_delta(judge, initial_db, after_db, added=[MONK_BM])
    check_only_tables_changed(judge, initial_db, after_db,
                              {"favorite_champions", "bookmark_articles"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
