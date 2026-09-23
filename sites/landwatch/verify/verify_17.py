#!/usr/bin/env python3
"""Verify LandWatch--17 — Homepage category tile carousel labels + counts.

Ground truth (frozen seed): Land for Sale '436 Land Properties', Farms and
Ranches '233 Farms and Ranches Properties', Hunting Land '176 Hunting Land
Properties', Homesites '53 Homesites Properties'.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase,
                        final_answer, run_verifier)

TASK_ID = "LandWatch--17"
TILES = [("Land for Sale", 436), ("Farms and Ranches", 233),
         ("Hunting Land", 176), ("Homesites", 53)]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_homepage", "/")
    for label, count in TILES:
        key = label.lower().replace(" ", "_")
        judge.check(f"answer_tile_label_{key}", contains_phrase(answer, label),
                    f"expected the tile label {label!r}")
        judge.check(f"answer_tile_count_{key}", contains_count(answer, count),
                    f"expected the {label} tile to show {count}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
