#!/usr/bin/env python3
"""Verify League of Legends--19: site search 'Vanguard' — news matches."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_count,
                        contains_phrase, final_answer, navigated_search_with, run_verifier)

TASK_ID = "League of Legends--19"
# Frozen ground truth (seed DB, scored search over articles): 3 matching news articles;
# the most recent (2024-08-22) is '/dev: Vanguard x LoL Retrospective'.
COUNT = 3
MOST_RECENT = "/dev: Vanguard x LoL Retrospective"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("searched_vanguard_on_site_search",
                navigated_search_with(traj, ["vanguard"]),
                "required: /search?q=Vanguard")
    judge.check("answer_count", contains_count(answer, COUNT),
                f"expected {COUNT} matching news articles")
    judge.check("answer_most_recent_title", contains_phrase(answer, "Vanguard x LoL Retrospective"),
                f"expected the title {MOST_RECENT!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
