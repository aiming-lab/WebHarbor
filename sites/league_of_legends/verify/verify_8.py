#!/usr/bin/env python3
"""Verify League of Legends--8: Yunara's Passive ability description."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_phrase,
                        final_answer, navigated_champion, run_verifier)

TASK_ID = "League of Legends--8"
# Frozen ground truth (seed DB, Yunara abilities, slot P):
# Vow of the First Lands — "Yunara's Critical Strikes deal bonus magic damage."
SLUG = "yunara"
PASSIVE_NAME = "Vow of the First Lands"
KEY_FACTS = ["critical strikes", "bonus magic damage"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_yunara_champion_page", navigated_champion(traj, SLUG),
                "required: /champions/yunara/")
    judge.check("answer_passive_name", contains_phrase(answer, PASSIVE_NAME),
                f"expected the passive name {PASSIVE_NAME!r}")
    missing = [f for f in KEY_FACTS if not contains_phrase(answer, f)]
    judge.check("answer_passive_description", not missing,
                f"expected the on-page description facts {KEY_FACTS!r}; missing={missing!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
