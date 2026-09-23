#!/usr/bin/env python3
"""Verify LandWatch--25 — Texas county with the most listings, then most expensive there.

Ground truth (frozen seed): Parker County leads with 19 listings; sorted by
Price: High to Low the most expensive is '2,856 acre Brazos River Ranch' at
$39,041,450.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "LandWatch--25"
COUNTY_PATH = "/texas-land-for-sale/parker-county"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_texas_land_page", "/texas-land-for-sale")
    check_visited_path(judge, traj, "visited_parker_county_page", COUNTY_PATH)
    judge.check("visited_price_high_sort", any("sort=price-high" in u for u in
                [s.get("url", "") + s.get("url_after", "") for s in traj.get("steps", []) if isinstance(s, dict)]),
                "expected ?sort=price-high on the county page")
    judge.check("answer_county_name", contains_phrase(answer, "Parker County"),
                "expected Parker County")
    judge.check("answer_county_listing_count", contains_count(answer, 19),
                "expected 19 listings in Parker County")
    judge.check("answer_priciest_title", contains_phrase(answer, "2,856 acre Brazos River Ranch"),
                "expected the most expensive listing '2,856 acre Brazos River Ranch'")
    judge.check("answer_priciest_price", contains_money(answer, 39041450),
                "expected the most expensive listing price $39,041,450")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
