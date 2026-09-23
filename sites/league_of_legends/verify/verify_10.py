#!/usr/bin/env python3
"""Verify League of Legends--10: site search 'Pulsefire' — champion owners."""
from verify_lib import (check_read_only, check_trajectory_identity, champion_count_named,
                        final_answer, navigated_search_with, run_verifier)

TASK_ID = "League of Legends--10"
# Frozen ground truth (seed DB, skins named 'Pulsefire <champion>'): 10 owners.
OWNERS = ["Caitlyn", "Ekko", "Ezreal", "Fiora", "Lucian", "Pantheon", "Riven",
          "Shen", "Thresh", "Twisted Fate"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("searched_pulsefire_on_site_search",
                navigated_search_with(traj, ["pulsefire"]),
                "required: /search?q=Pulsefire")
    named = champion_count_named(answer, OWNERS)
    judge.check("answer_owners_all", named == len(OWNERS),
                f"expected all {len(OWNERS)} Pulsefire owners; matched {named}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
