#!/usr/bin/env python3
"""Verify LandWatch--9 — Louie Swope agent profile stats.

Ground truth (frozen seed): 2 Total Listings, Price Range $19M - $21M,
Acre Range 310.00 - 844 ac, based in San Antonio, TX.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase,
                        final_answer, run_verifier)

TASK_ID = "LandWatch--9"
PROFILE_PATH = "/profile/louie-swope/1437140"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_louie_profile", PROFILE_PATH)
    judge.check("answer_total_listings", contains_count(answer, 2),
                "expected Total Listings 2")
    judge.check("answer_price_range", contains_phrase(answer, "$19M") and
                contains_phrase(answer, "$21M"), "expected Price Range $19M - $21M")
    judge.check("answer_acre_range", contains_phrase(answer, "310") and
                contains_phrase(answer, "844") and contains_phrase(answer, "ac"),
                "expected Acre Range 310.00 - 844 ac")
    judge.check("answer_city_state", contains_phrase(answer, "San Antonio") and
                contains_phrase(answer, "TX"), "expected San Antonio, TX")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
