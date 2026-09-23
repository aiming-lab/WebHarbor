#!/usr/bin/env python3
"""Verify League of Legends--14: Dev category article count + most recent title."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_count,
                        contains_phrase, final_answer, navigated_category, run_verifier)

TASK_ID = "League of Legends--14"
# Frozen ground truth (seed DB, dev category): 147 articles; most recent (2026-09-08):
# 'TL;DW: Team Voice, Classic & More Dev Update'.
CATEGORY = "dev"
COUNT = 147
MOST_RECENT = "TL;DW: Team Voice, Classic & More Dev Update"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_dev_category", navigated_category(traj, CATEGORY),
                "required: /news/dev/")
    judge.check("answer_count", contains_count(answer, COUNT),
                f"expected {COUNT} articles in the Dev category")
    judge.check("answer_most_recent_title", contains_phrase(answer, MOST_RECENT),
                f"expected {MOST_RECENT!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
