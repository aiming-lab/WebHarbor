#!/usr/bin/env python3
"""Verify League of Legends--29: Naafiri's Ultimate (R) name + description."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_phrase,
                        final_answer, navigated_champion, run_verifier)

TASK_ID = "League of Legends--29"
# Frozen ground truth (seed DB, Naafiri abilities, slot R):
# Hounds' Pursuit — "Naafiri and her packmates dash at a champion, dealing damage.
# Naafiri reveals nearby enemies if she scores a takedown and can recast this Ability
# once. The second cast grants a shield."
SLUG = "naafiri"
ULTIMATE = "Hounds' Pursuit"
KEY_FACTS = ["packmates", "dash at a champion", "takedown", "recast", "shield"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_naafiri_champion_page", navigated_champion(traj, SLUG),
                "required: /champions/naafiri/")
    judge.check("answer_ultimate_name", contains_phrase(answer, ULTIMATE),
                f"expected the R name {ULTIMATE!r}")
    missing = [f for f in KEY_FACTS if not contains_phrase(answer, f)]
    judge.check("answer_description", not missing,
                f"expected description facts {KEY_FACTS!r}; missing={missing!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
