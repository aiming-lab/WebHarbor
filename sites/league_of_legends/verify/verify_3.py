#!/usr/bin/env python3
"""Verify League of Legends--3: roster sorted by Newest, first five champions."""
from verify_lib import (check_read_only, check_trajectory_identity, champion_named,
                        contains_any, final_answer, navigated_champions_listing,
                        phrases_in_order, run_verifier)

TASK_ID = "League of Legends--3"
# Frozen ground truth (seed DB, sort=release: release_key desc, name asc): the first
# five champions are Naafiri, Hwei, Zaahen, Milio, Smolder.
TOP5 = ["Naafiri", "Hwei", "Zaahen", "Milio", "Smolder"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_champions_sorted_by_newest",
                navigated_champions_listing(traj, {"sort": "release"}),
                "required: /champions/?sort=release")
    judge.check("answer_names_all", all(champion_named(answer, n) for n in TOP5),
                f"expected the first five {TOP5!r}")
    judge.check("answer_names_in_order", phrases_in_order(answer, TOP5),
                "expected Naafiri, then Hwei, then Zaahen, then Milio, then Smolder, in order")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
