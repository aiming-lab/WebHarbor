#!/usr/bin/env python3
"""Verify League of Legends--2: Low difficulty roster count."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_count,
                        final_answer, navigated_champions_listing, run_verifier)

TASK_ID = "League of Legends--2"
# Frozen ground truth (seed DB): 28 champions carry difficulty_name == "Low".
LOW_COUNT = 28


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_champions_with_low_filter",
                navigated_champions_listing(traj, {"difficulty": "Low"}),
                "required: /champions/?difficulty=Low")
    judge.check("answer_count", contains_count(answer, LOW_COUNT),
                f"expected {LOW_COUNT} champions")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
