#!/usr/bin/env python3
"""Verify LandWatch--3 — two budget tracks: Texas $1M+ vs Undeveloped $50-99K.

Ground truth (frozen seed): Texas land at $1,000,000 and up, sorted Price:
Low to High, shows 81 listings; the three cheapest are 'East Texas Poultry
Farm LOCATED NEAR COOKVILLE TEXAS' at $1,050,000 (Titus County), 'Gorgeous
42 Acres' at $1,050,000 (Parker County), and 'Carlton Longleaf Tract' at
$1,072,500 (Trinity County). Undeveloped Land in the $50,000 - $99,999 band,
sorted the same way, shows 3 listings; the cheapest is 'Jaz Meadows 2-Acre
Homesites' at $77,500 in Navarro County. The undeveloped track's cheapest
property costs less.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_any, contains_count,
                        contains_money, contains_phrase, final_answer,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "LandWatch--3"
TX_FILTER = "/texas-land-for-sale/price-over-1000000"
UNDEV_FILTER = "/undeveloped-land/price-50000-99999"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: both filtered pages with the cheapest-first sort applied
    judge.check("visited_texas_million_filter_sorted",
                navigated_to_path_with_params(traj, TX_FILTER, {"sort": "price-low"}),
                f"expected {TX_FILTER} with sort=price-low")
    judge.check("visited_undeveloped_budget_filter_sorted",
                navigated_to_path_with_params(traj, UNDEV_FILTER, {"sort": "price-low"}),
                f"expected {UNDEV_FILTER} with sort=price-low")
    # Texas leg
    judge.check("answer_texas_total", contains_count(answer, 81),
                "expected 81 listings on the Texas $1M+ page")
    judge.check("answer_tx_cheapest_title",
                contains_phrase(answer, "East Texas Poultry Farm"),
                "expected the cheapest 'East Texas Poultry Farm'")
    judge.check("answer_tx_cheapest_price", contains_money(answer, 1050000),
                "expected the cheapest at $1,050,000")
    judge.check("answer_tx_cheapest_county", contains_phrase(answer, "Titus"),
                "expected Titus County for the cheapest")
    judge.check("answer_tx_second_title", contains_phrase(answer, "Gorgeous 42 Acres"),
                "expected the second-cheapest 'Gorgeous 42 Acres'")
    judge.check("answer_tx_second_county", contains_phrase(answer, "Parker"),
                "expected Parker County for the second-cheapest")
    judge.check("answer_tx_third_title", contains_phrase(answer, "Carlton Longleaf Tract"),
                "expected the third-cheapest 'Carlton Longleaf Tract'")
    judge.check("answer_tx_third_price", contains_money(answer, 1072500),
                "expected the third-cheapest at $1,072,500")
    judge.check("answer_tx_third_county", contains_phrase(answer, "Trinity"),
                "expected Trinity County for the third-cheapest")
    # Undeveloped leg
    judge.check("answer_undeveloped_total", contains_count(answer, 3),
                "expected 3 listings in the undeveloped $50-99K band")
    judge.check("answer_undev_cheapest_title", contains_phrase(answer, "Jaz Meadows"),
                "expected the cheapest 'Jaz Meadows 2-Acre Homesites'")
    judge.check("answer_undev_cheapest_price", contains_money(answer, 77500),
                "expected the cheapest at $77,500")
    judge.check("answer_undev_cheapest_county", contains_phrase(answer, "Navarro"),
                "expected Navarro County for the cheapest")
    # comparison: the undeveloped track's cheapest costs less
    judge.check("answer_picks_cheaper_track",
                contains_any(answer, ["costs less", "cheaper", "less expensive",
                                       "lower price", "least expensive"]),
                "expected the answer to name the cheaper track")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
