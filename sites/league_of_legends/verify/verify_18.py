#!/usr/bin/env python3
"""Verify League of Legends--18: Lore category article count + all titles."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_count,
                        contains_phrase, final_answer, navigated_category, run_verifier)

TASK_ID = "League of Legends--18"
# Frozen ground truth (seed DB, lore category): 2 articles.
CATEGORY = "lore"
COUNT = 2
TITLES = ["Previously on Star Guardian", "The Council Archives Primer"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_lore_category", navigated_category(traj, CATEGORY),
                "required: /news/lore/")
    judge.check("answer_count", contains_count(answer, COUNT),
                f"expected {COUNT} articles")
    missing = [t for t in TITLES if not contains_phrase(answer, t)]
    judge.check("answer_titles_all", not missing,
                f"expected titles {TITLES!r}; missing={missing!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
