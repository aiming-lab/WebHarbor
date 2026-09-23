#!/usr/bin/env python3
"""Verify League of Legends--5: 'The Ruined King' champion role + difficulty."""
from verify_lib import (check_read_only, check_trajectory_identity, champion_named,
                        contains_all, contains_phrase, final_answer, navigated_champion,
                        run_verifier)

TASK_ID = "League of Legends--5"
# Frozen ground truth (seed DB, champions.epithet == "The Ruined King"):
# Viego — roles Fighter/Assassin, difficulty Medium (2/3 pips).
CHAMPION = "Viego"
SLUG = "viego"
ROLES = ["Fighter", "Assassin"]
DIFFICULTY = "Medium"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_viego_champion_page", navigated_champion(traj, SLUG),
                "required: /champions/viego/")
    judge.check("answer_champion", champion_named(answer, CHAMPION),
                "expected Viego")
    judge.check("answer_roles", contains_all(answer, ROLES),
                f"expected roles {ROLES!r}")
    judge.check("answer_difficulty", contains_phrase(answer, DIFFICULTY),
                "expected the difficulty rating 'Medium' from the champion page")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
