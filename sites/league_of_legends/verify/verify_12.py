#!/usr/bin/env python3
"""Verify League of Legends--12: Aatrox change in Patch 26.19 + new cooldown ladder."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_decimal_sequence,
                        contains_phrase, final_answer, navigated_article, run_verifier)

TASK_ID = "League of Legends--12"
# Frozen ground truth (seed DB, article 'league-of-legends-patch-26-19-notes'):
# Aatrox's W - Infernal Chains cooldown 20/18/16/14/12 ⇒ 18/16.5/15/13.5/12 seconds
# (his E - Umbral Dash heal ratio also changed, but the cooldown task is the W).
ARTICLE = ("game-updates", "league-of-legends-patch-26-19-notes")
ABILITY = "Infernal Chains"
NEW_COOLDOWNS = ["18", "16.5", "15", "13.5", "12"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_patch_2619_article",
                navigated_article(traj, *ARTICLE),
                "required: /news/game-updates/league-of-legends-patch-26-19-notes/")
    judge.check("answer_ability", contains_phrase(answer, ABILITY),
                f"expected the ability {ABILITY!r}")
    judge.check("answer_new_cooldowns", contains_decimal_sequence(answer, NEW_COOLDOWNS),
                f"expected the new cooldown ladder {NEW_COOLDOWNS!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
