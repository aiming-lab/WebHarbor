#!/usr/bin/env python3
"""Verify League of Legends--6: Mel's Available Skins carousel."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_count,
                        contains_phrase, final_answer, navigated_champion, run_verifier)

TASK_ID = "League of Legends--6"
# Frozen ground truth (seed DB, Mel skins ordered by num): 3 skins.
SLUG = "mel"
SKIN_COUNT = 3
SKINS = ["Mel", "Arcane Councilor Mel", "Prestige Winterblessed Mel"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_mel_champion_page", navigated_champion(traj, SLUG),
                "required: /champions/mel/")
    judge.check("answer_skin_count", contains_count(answer, SKIN_COUNT),
                f"expected {SKIN_COUNT} skins in the carousel")
    missing = [s for s in SKINS if not contains_phrase(answer, s)]
    judge.check("answer_skin_names", not missing,
                f"expected skin names {SKINS!r}; missing={missing!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
