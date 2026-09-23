#!/usr/bin/env python3
"""Verify LandWatch--7 — Houston Region scouting + the strongest Texas county.

Ground truth (frozen seed): the Houston Region results page (from the Texas
page's Region Map filter) shows 5 listings; the first is 'Kountze
Countryside Retreat' at $510,600 for 74 Acres. In the Texas page's County
filter group, Parker County leads with 19 listings; Parker County sorted
Price: High to Low tops out at '2,856 acre Brazos River Ranch' for
$39,041,450.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_count,
                        contains_money, contains_phrase, final_answer,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "LandWatch--7"
HOUSTON_REGION = "/texas-land-for-sale/houston-region"
PARKER = "/texas-land-for-sale/parker-county"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates
    check_visited_path(judge, traj, "visited_houston_region", HOUSTON_REGION)
    check_visited_path(judge, traj, "visited_texas_state_page", "/texas-land-for-sale")
    judge.check("visited_parker_sorted_by_price",
                navigated_to_path_with_params(traj, PARKER, {"sort": "price-high"}),
                f"expected {PARKER} with sort=price-high")
    # Houston Region leg
    judge.check("answer_region_count", contains_count(answer, 5),
                "expected 5 listings in the Houston Region")
    judge.check("answer_region_first_title",
                contains_phrase(answer, "Kountze Countryside Retreat"),
                "expected the first listing 'Kountze Countryside Retreat'")
    judge.check("answer_region_first_price", contains_money(answer, 510600),
                "expected the first listing at $510,600")
    judge.check("answer_region_first_acres", contains_acres(answer, 74),
                "expected the first listing at 74 Acres")
    # county drill-down leg
    judge.check("answer_top_county_named", contains_phrase(answer, "Parker"),
                "expected Parker County to be named the county with the most listings")
    judge.check("answer_top_county_count", contains_count(answer, 19),
                "expected Parker County's 19 listings")
    judge.check("answer_county_most_expensive_title",
                contains_phrase(answer, "Brazos River Ranch"),
                "expected the most expensive '2,856 acre Brazos River Ranch'")
    judge.check("answer_county_most_expensive_price", contains_money(answer, 39041450),
                "expected the most expensive at $39,041,450")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
