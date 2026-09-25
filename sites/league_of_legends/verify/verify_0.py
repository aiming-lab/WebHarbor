#!/usr/bin/env python3
"""Verify League of Legends--0: Support x High roster comparison -> favorite -> verify.

Honest chain (18 atomic actions): Champions nav -> role=Support -> difficulty=High
-> Apply -> open Hwei -> W panel -> R panel -> back -> open Renata Glasc -> W panel
-> R panel -> Sign in to Favorite -> fill email -> fill password -> submit ->
Add to Favorites -> My Account -> answer.

Frozen ground truth (seed DB):
  * Support+High filter shows 8 champions (Hwei and Renata Glasc among them).
  * Hwei (Mage/Support, High) has 4 skins; W "Subject: Serenity" (menu of utility
    spells), R "Spiraling Despair" (expanding slow-and-damage painting).
  * Renata Glasc (Support/Mage, High) has 6 skins; W "Bailout" (delays an ally's
    death), R "Hostile Takeover" (enemies go Berserk).
  * Renata Glasc has more skins -> she is the pick; alice_j (id 1) gains exactly
    one favorite row (Renata Glasc, champion id 109) -> 6 favorites total.
"""
from verify_lib import (bound_count, bound_phrase, bound_stem,
                        champion_named, check_favorites_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_count,
                        final_answer, navigated_champion,
                        navigated_champions_listing,
                        navigated_to_path_any, run_verifier)

TASK_ID = "League of Legends--0"
EMAIL = "alice.j@test.com"
RENATA = (1, 109, "2026-09-22")   # (user_id, champion_id, added_date) delta row


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_roster_filtered_support_high",
                navigated_champions_listing(traj, {"role": "Support", "difficulty": "High"}),
                "required: /champions/ with role=Support and difficulty=High")
    judge.check("visited_hwei_page", navigated_champion(traj, "hwei"), "required: /champions/hwei/")
    judge.check("visited_renata_page", navigated_champion(traj, "renata"), "required: /champions/renata/")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_favorites",
                navigated_to_path_any(traj, ["/account", "/account/favorites"]),
                "required: /account or /account/favorites")

    judge.check("answer_added_renata", champion_named(answer, "Renata Glasc"),
                "expected Renata Glasc named as the added pick")
    judge.check("answer_new_total_6", contains_count(answer, 6),
                "expected the account's new total of 6 favorites")
    judge.check("answer_hwei_skins_4", bound_count(answer, 4, "Hwei", ["Renata"]),
                "expected Hwei's 4 skins reported, attached to Hwei")
    judge.check("answer_renata_skins_6", bound_count(answer, 6, "Renata", ["Hwei"]),
                "expected Renata Glasc's 6 skins reported, attached to Renata")
    judge.check("answer_hwei_w", bound_phrase(answer, "Subject Serenity", "Hwei", ["Renata"], mode="after"),
                "expected Hwei's W 'Subject: Serenity' attached to Hwei")
    judge.check("answer_hwei_r", bound_phrase(answer, "Spiraling Despair", "Hwei", ["Renata"], mode="after"),
                "expected Hwei's R 'Spiraling Despair' attached to Hwei")
    judge.check("answer_renata_w", bound_phrase(answer, "Bailout", "Renata", ["Hwei"], mode="after"),
                "expected Renata's W 'Bailout' attached to Renata")
    judge.check("answer_renata_r", bound_phrase(answer, "Hostile Takeover", "Renata", ["Hwei"], mode="after"),
                "expected Renata's R 'Hostile Takeover' attached to Renata")
    judge.check("answer_berserk_semantics",
                bound_phrase(answer, "Berserk", "Hostile Takeover",
                             ["Subject Serenity", "Spiraling Despair", "Bailout"], mode="after"),
                "expected the Berserk effect attached to Hostile Takeover")
    judge.check("answer_death_delay_semantics",
                bound_stem(answer, "delay", "Bailout",
                           ["Hostile Takeover", "Subject Serenity", "Spiraling Despair"], mode="after"),
                "expected the death-delay effect attached to Bailout")

    check_favorites_delta(judge, initial_db, after_db, added=[RENATA])
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
