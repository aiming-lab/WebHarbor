#!/usr/bin/env python3
"""Verify League of Legends--26: How To Play jungle — Baron Nashor reward sentence."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_all,
                        contains_phrase, final_answer, navigated_to_path, run_verifier)

TASK_ID = "League of Legends--26"
# Frozen ground truth (how_to_play.html, Take on the Jungle > Baron Nashor):
# "Killing Baron grants the slayer's team bonus attack damage, ability power,
# empowered recall, and greatly increases the power of nearby minions."
FACTS = ["bonus attack damage", "ability power", "empowered recall",
         "increases the power of nearby minions"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_how_to_play", navigated_to_path(traj, "/how-to-play"),
                "required: /how-to-play/")
    judge.check("answer_baron_named", contains_phrase(answer, "Baron Nashor") or contains_phrase(answer, "Killing Baron"),
                "expected the sentence to mention Baron (Nashor)")
    missing = [f for f in FACTS if not contains_phrase(answer, f)]
    judge.check("answer_baron_rewards", not missing,
                f"expected the on-page reward facts {FACTS!r}; missing={missing!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
