#!/usr/bin/env python3
"""Verify League of Legends--20: alice's favorite champions + skin counts."""
from verify_lib import (SEED_USERS, check_read_only, check_signed_in_as,
                        check_trajectory_identity, champion_named, contains_count,
                        contains_phrase, final_answer, navigated_champion,
                        navigated_to_path, run_verifier)

TASK_ID = "League of Legends--20"
# Frozen ground truth (seed DB, alice_j favorite_champions joined to champions):
# Amumu 15 skins, Draven 15, Kayle 19, Lee Sin 20, Yunara 3 — Lee Sin has the most.
EMAIL = "alice.j@test.com"
FAVORITES = [("amumu", "Amumu", 15), ("draven", "Draven", 15), ("kayle", "Kayle", 19),
             ("lee-sin", "Lee Sin", 20), ("yunara", "Yunara", 3)]
MOST = "Lee Sin"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_favorites",
                navigated_to_path(traj, "/account") or navigated_to_path(traj, "/account/favorites"),
                "required: /account (or /account/favorites)")
    judge.check("answer_favorite_count", contains_count(answer, len(FAVORITES)),
                f"expected {len(FAVORITES)} favorite champions")
    for slug, name, skins in FAVORITES:
        judge.check(f"answer_favorite_{slug}",
                    champion_named(answer, name) and contains_count(answer, skins),
                    f"expected {name!r} with {skins} skins")
    judge.check("answer_most_skins", champion_named(answer, MOST),
                f"expected {MOST!r} named as having the most skins")
    from reviewed import check_facts
    check_facts(judge, answer, [{'entity': 'Amumu', 'patterns': ['\\b15\\s+(?:skins|appearances)']}, {'entity': 'Draven', 'patterns': ['\\b15\\s+(?:skins|appearances)']}, {'entity': 'Kayle', 'patterns': ['\\b19\\s+(?:skins|appearances)']}, {'entity': 'Lee Sin', 'patterns': ['\\b20\\s+(?:skins|appearances)']}, {'entity': 'Yunara', 'patterns': ['\\b3\\s+(?:skins|appearances)']}])
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
