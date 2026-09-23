#!/usr/bin/env python3
"""Verify LandWatch--0 — Austin, TX location search results page.

Ground truth (frozen seed): the Austin city page shows exactly 1 listing;
its first (and only) card is '111 AC In the Heart of the Hill Country' at
$6,100,000 for 111 Acres.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_count,
                        contains_money, contains_phrase, final_answer, navigated_to,
                        navigated_to_path, run_verifier)

TASK_ID = "LandWatch--0"
CITY_PATH = "/texas-land-for-sale/austin"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("located_austin_via_search_or_url",
                navigated_to(traj, "q=austin") or navigated_to_path(traj, CITY_PATH),
                "expected a location search for Austin or the Austin results page")
    check_visited_path(judge, traj, "visited_austin_results_page", CITY_PATH)
    judge.check("answer_total_listings", contains_count(answer, 1),
                "expected 1 listing in the results heading")
    judge.check("answer_first_title", contains_phrase(answer, "111 AC In the Heart of the Hill Country"),
                "expected the first listing title '111 AC In the Heart of the Hill Country'")
    judge.check("answer_first_price", contains_money(answer, 6100000),
                "expected the first listing price $6,100,000")
    judge.check("answer_first_acres", contains_acres(answer, 111),
                "expected the first listing acreage 111 Acres")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
