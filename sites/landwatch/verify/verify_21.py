#!/usr/bin/env python3
"""Verify LandWatch--21 — Montana land + Over 1,000 Acres parcel filter.

Ground truth (frozen seed): 3 matching listings — 'Montana Legacy Ranch'
11,689 Acres, '2,341 Ac Montana Creek Ranch' 3,336 Acres, 'Mullendore Ranch'
10,510 Acres.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_count,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "LandWatch--21"
FILTER_PATH = "/montana-land-for-sale/acres-over-1000"
LISTINGS = [("Montana Legacy Ranch", 11689), ("2,341 Ac Montana Creek Ranch", 3336),
            ("Mullendore Ranch", 10510)]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_montana_page", "/montana-land-for-sale")
    check_visited_path(judge, traj, "visited_acres_filter_page", FILTER_PATH)
    judge.check("answer_match_count", contains_count(answer, 3),
                "expected 3 matching listings")
    for title, acres in LISTINGS:
        key = title.lower()[:14].replace(" ", "_").replace(",", "")
        judge.check(f"answer_title_{key}", contains_phrase(answer, title),
                    f"expected the listing {title!r}")
        judge.check(f"answer_acres_{key}", contains_acres(answer, acres),
                    f"expected {acres:,} Acres for {title!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
