#!/usr/bin/env python3
"""Verify LandWatch--0 — three-location shortlist: Austin vs Harris County vs Boerne.

Ground truth (frozen seed): the Austin, TX results page shows 1 listing, the
first being '111 AC In the Heart of the Hill Country' at $6,100,000 for 111
Acres (~$54,955 per acre); the Harris County, TX page shows 1 listing, 'A
private 10-acre estate in Cypress' at $5,750,000 for 10 Acres (~$575,000 per
acre); the Boerne, TX page shows 4 listings, the first being 'Sisterdale
Farms' at $19,400,000 for 310 Acres (~$62,581 per acre). Judged on price per
acre of the first listings, Austin is the better value.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_count,
                        contains_money, contains_phrase, final_answer,
                        navigated_to, run_verifier)

TASK_ID = "LandWatch--0"
AUSTIN_PATH = "/texas-land-for-sale/austin"
HARRIS_PATH = "/texas-land-for-sale/harris-county"
BOERNE_PATH = "/texas-land-for-sale/boerne"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the three location results pages (search submit or suggest pick)
    judge.check("located_austin_via_search_or_url",
                navigated_to(traj, "q=austin") or navigated_to(traj, AUSTIN_PATH),
                "expected a location search for Austin or the Austin results page")
    judge.check("located_harris_via_search_or_url",
                navigated_to(traj, "q=harris") or navigated_to(traj, HARRIS_PATH),
                "expected a location search for Harris County or its results page")
    judge.check("located_boerne_via_search_or_url",
                navigated_to(traj, "q=boerne") or navigated_to(traj, BOERNE_PATH),
                "expected a location search for Boerne or the Boerne results page")
    check_visited_path(judge, traj, "visited_austin_results", AUSTIN_PATH)
    check_visited_path(judge, traj, "visited_harris_results", HARRIS_PATH)
    check_visited_path(judge, traj, "visited_boerne_results", BOERNE_PATH)
    # answer gates — Austin leg
    judge.check("answer_austin_total", contains_count(answer, 1),
                "expected 1 listing in the Austin results heading")
    judge.check("answer_austin_first_title",
                contains_phrase(answer, "111 AC In the Heart of the Hill Country"),
                "expected the Austin first listing '111 AC In the Heart of the Hill Country'")
    judge.check("answer_austin_first_price", contains_money(answer, 6100000),
                "expected the Austin first listing at $6,100,000")
    judge.check("answer_austin_first_acres", contains_acres(answer, 111),
                "expected the Austin first listing at 111 Acres")
    # answer gates — Harris County leg
    judge.check("answer_harris_first_title",
                contains_phrase(answer, "A private 10-acre estate in Cypress"),
                "expected the Harris County first listing 'A private 10-acre estate in Cypress'")
    judge.check("answer_harris_first_price", contains_money(answer, 5750000),
                "expected the Harris County first listing at $5,750,000")
    judge.check("answer_harris_first_acres", contains_acres(answer, 10),
                "expected the Harris County first listing at 10 Acres")
    # answer gates — Boerne leg
    judge.check("answer_boerne_total", contains_count(answer, 4),
                "expected 4 listings in the Boerne results heading")
    judge.check("answer_boerne_first_title", contains_phrase(answer, "Sisterdale Farms"),
                "expected the Boerne first listing 'Sisterdale Farms'")
    judge.check("answer_boerne_first_price", contains_money(answer, 19400000),
                "expected the Boerne first listing at $19,400,000")
    judge.check("answer_boerne_first_acres", contains_acres(answer, 310),
                "expected the Boerne first listing at 310 Acres")
    # comparison: Austin has the lowest price per acre among the first listings
    judge.check("answer_names_best_value_location", contains_phrase(answer, "Austin"),
                "expected Austin to be named the better-value location")
    judge.check("answer_judges_on_price_per_acre",
                contains_phrase(answer, "per acre") or contains_phrase(answer, "per-acre")
                or contains_phrase(answer, "/ acre") or contains_phrase(answer, "/acre"),
                "expected the value judgement to be made on price per acre")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
