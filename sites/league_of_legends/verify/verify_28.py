#!/usr/bin/env python3
"""Verify League of Legends--28: Sona's DJ / Pentakill skin names."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_count,
                        contains_phrase, final_answer, navigated_champion, run_verifier)

TASK_ID = "League of Legends--28"
# Frozen ground truth (seed DB, Sona skins): the carousel contains exactly three
# DJ / Pentakill entries.
SLUG = "sona"
SKINS = ["DJ Sona", "Pentakill Sona", "Pentakill III: Lost Chapter Sona"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_sona_champion_page", navigated_champion(traj, SLUG),
                "required: /champions/sona/")
    # colons are punctuation noise: compare colon-stripped on both sides
    clean = answer.replace(":", " ")
    missing = [s for s in SKINS if not contains_phrase(clean, s.replace(":", " "))]
    judge.check("answer_skin_names", not missing,
                f"expected skin names {SKINS!r}; missing={missing!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
