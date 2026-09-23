#!/usr/bin/env python3
"""Verify League of Legends--16: How To Play grounding -> Marksman filter -> favorite.

Honest chain (16 atomic actions): Game Overview nav -> Champions nav ->
select role=Marksman -> Apply -> open Ashe -> R panel -> back -> open Miss
Fortune -> R panel -> Sign in to Favorite -> fill email -> fill password ->
submit -> Add to Favorites -> My Account -> answer.

Frozen ground truth (seed DB / tracked How To Play copy):
  * Baron Nashor: 'Killing Baron grants the slayer's team bonus attack damage,
    ability power, empowered recall, and greatly increases the power of nearby
    minions.'
  * Bot lane: 'Bot lane champions are the dynamite of the team. As precious
    cargo, they need to be protected early on before amassing enough gold and
    experience to carry the team to victory.'
  * Miss Fortune (Marksman/Mage, Low, 24 skins) R 'Bullet Time'; Ashe
    (Marksman/Support, Medium, 21 skins) R 'Enchanted Crystal Arrow'.
  * Miss Fortune has more skins -> she is the pick; carol_d (id 3) gains
    exactly one favorite row (Miss Fortune, champion id 85) -> 6 favorites.
"""
from verify_lib import (champion_named, check_favorites_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_count,
                        contains_phrase, contains_phrase_loose, final_answer,
                        navigated_champion, navigated_champions_listing,
                        navigated_to_path, navigated_to_path_any, run_verifier)

TASK_ID = "League of Legends--16"
EMAIL = "carol.d@test.com"
MISS_FORTUNE = (3, 85, "2026-09-22")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_how_to_play", navigated_to_path(traj, "/how-to-play"),
                "required: /how-to-play")
    judge.check("visited_roster_filtered_marksman",
                navigated_champions_listing(traj, {"role": "Marksman"}),
                "required: /champions/ with role=Marksman")
    judge.check("visited_missfortune_page", navigated_champion(traj, "missfortune"),
                "required: /champions/missfortune/")
    judge.check("visited_ashe_page", navigated_champion(traj, "ashe"),
                "required: /champions/ashe/")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_favorites",
                navigated_to_path_any(traj, ["/account", "/account/favorites"]),
                "required: /account or /account/favorites")

    judge.check("answer_baron_rewards",
                contains_phrase(answer, "bonus attack damage") and
                contains_phrase(answer, "ability power") and
                contains_phrase(answer, "empowered recall"),
                "expected Baron's bonus attack damage, ability power and empowered recall")
    judge.check("answer_baron_minions", contains_phrase(answer, "minions"),
                "expected the empowered nearby minions effect")
    judge.check("answer_dynamite_quote", contains_phrase(answer, "dynamite of the team"),
                "expected the 'dynamite of the team' phrasing")
    judge.check("answer_protection_rationale",
                contains_phrase(answer, "protected") or contains_phrase(answer, "protection"),
                "expected the early-protection rationale")
    judge.check("answer_mf_ultimate", contains_phrase_loose(answer, "Bullet Time"),
                "expected Miss Fortune's ultimate 'Bullet Time'")
    judge.check("answer_ashe_ultimate", contains_phrase_loose(answer, "Enchanted Crystal Arrow"),
                "expected Ashe's ultimate 'Enchanted Crystal Arrow'")
    judge.check("answer_mf_skins_24", contains_count(answer, 24),
                "expected Miss Fortune's 24 skins")
    judge.check("answer_ashe_skins_21", contains_count(answer, 21),
                "expected Ashe's 21 skins")
    judge.check("answer_added_missfortune", champion_named(answer, "Miss Fortune"),
                "expected Miss Fortune named as the added pick")
    judge.check("answer_new_total_6", contains_count(answer, 6),
                "expected the account's new total of 6 favorites")

    check_favorites_delta(judge, initial_db, after_db, added=[MISS_FORTUNE])
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
