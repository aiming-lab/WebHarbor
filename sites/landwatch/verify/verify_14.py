#!/usr/bin/env python3
"""Verify LandWatch--14 — Harris County, Texas results page.

Ground truth (frozen seed): 1 listing; 'A private 10-acre estate in Cypress'
at $5,750,000 for 10 Acres.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_count,
                        contains_money, contains_phrase, final_answer, navigated_to,
                        run_verifier)

TASK_ID = "LandWatch--14"
COUNTY_PATH = "/texas-land-for-sale/harris-county"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("located_harris_county",
                navigated_to(traj, "q=harris") or navigated_to(traj, "harris"),
                "expected a location lookup for Harris County")
    check_visited_path(judge, traj, "visited_harris_county_page", COUNTY_PATH)
    judge.check("answer_total_listings", contains_count(answer, 1),
                "expected 1 listing in the results heading")
    judge.check("answer_first_title", contains_phrase(answer, "A private 10-acre estate in Cypress"),
                "expected the first listing 'A private 10-acre estate in Cypress'")
    judge.check("answer_first_price", contains_money(answer, 5750000),
                "expected the first listing price $5,750,000")
    judge.check("answer_first_acres", contains_acres(answer, 10),
                "expected the first listing acreage 10 Acres")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
