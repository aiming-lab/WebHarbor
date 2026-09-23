#!/usr/bin/env python3
"""Verify League of Legends--7: Ambessa's five ability names in slot order."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_phrase,
                        final_answer, navigated_champion, phrases_in_order, run_verifier)

TASK_ID = "League of Legends--7"
# Frozen ground truth (seed DB, Ambessa abilities ordered by sort): Passive..R.
SLUG = "ambessa"
ABILITIES = ["Drakehound's Step", "Cunning Sweep / Sundering Slam", "Repudiation",
             "Lacerate", "Public Execution"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_ambessa_champion_page", navigated_champion(traj, SLUG),
                "required: /champions/ambessa/")
    missing = [a for a in ABILITIES if not contains_phrase(answer, a)]
    judge.check("answer_ability_names", not missing,
                f"expected {ABILITIES!r}; missing={missing!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
