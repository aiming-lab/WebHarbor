#!/usr/bin/env python3
"""Verify LandWatch--23 — Boerne, Texas results page.

Ground truth (frozen seed): 4 listings; the first is 'Sisterdale Farms' at
$19,400,000.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money,
                        contains_phrase, final_answer, navigated_to, run_verifier)

TASK_ID = "LandWatch--23"
CITY_PATH = "/texas-land-for-sale/boerne"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("located_boerne", navigated_to(traj, "boerne"),
                "expected a location lookup for Boerne")
    check_visited_path(judge, traj, "visited_boerne_results_page", CITY_PATH)
    judge.check("answer_total_listings", contains_count(answer, 4),
                "expected 4 listings in the results heading")
    judge.check("answer_first_title", contains_phrase(answer, "Sisterdale Farms"),
                "expected the first listing 'Sisterdale Farms'")
    judge.check("answer_first_price", contains_money(answer, 19400000),
                "expected the first listing price $19,400,000")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
