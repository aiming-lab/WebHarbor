#!/usr/bin/env python3
"""Verify League of Legends--0: Support role + High difficulty roster filter."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_count,
                        contains_all, champion_named, champion_count_named,
                        final_answer, navigated_champions_listing, run_verifier)

TASK_ID = "League of Legends--0"
# Frozen ground truth (seed DB, champions with roles containing "Support" and
# difficulty_name == "High"): 8 champions.
CHAMPIONS = ["Bard", "Fiddlesticks", "Heimerdinger", "Hwei", "Renata Glasc",
             "Swain", "Vel'Koz", "Xerath"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_champions_with_support_high_filter",
                navigated_champions_listing(traj, {"role": "Support", "difficulty": "High"}),
                "required: /champions/?role=Support&difficulty=High")
    judge.check("answer_count", contains_count(answer, 8), "expected 8 champions")
    named = champion_count_named(answer, CHAMPIONS)
    judge.check("answer_names_all", named == len(CHAMPIONS),
                f"expected all of {CHAMPIONS!r}; matched {named}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
