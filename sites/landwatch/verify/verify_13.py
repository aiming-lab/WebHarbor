#!/usr/bin/env python3
"""Verify LandWatch--13 — the Texas waterfront premium check.

Ground truth (frozen seed): the Texas land-for-sale page's Property Types
filter leads to the Texas waterfront results (/texas-land-for-sale/
waterfront-property) with 27 listings; sorted Price: High to Low the most
expensive is '2,856 acre Brazos River Ranch' at $39,041,450 for 2,359
Acres. With the waterfront filter cleared, the most expensive land listing
in all of Texas is 'Blake Ranch' at $56,997,000 (Montgomery County). Blake
Ranch costs more and is not a waterfront property.
"""
import re

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_count,
                        contains_money, contains_phrase, final_answer, norm,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "LandWatch--13"
WATERFRONT = "/texas-land-for-sale/waterfront-property"
TEXAS = "/texas-land-for-sale"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the waterfront results and the full state page, both sorted
    judge.check("visited_texas_waterfront_sorted",
                navigated_to_path_with_params(traj, WATERFRONT, {"sort": "price-high"}),
                f"expected {WATERFRONT} with sort=price-high")
    judge.check("visited_texas_sorted",
                navigated_to_path_with_params(traj, TEXAS, {"sort": "price-high"}),
                f"expected {TEXAS} with sort=price-high")
    # waterfront leg
    judge.check("answer_waterfront_total", contains_count(answer, 27),
                "expected 27 Texas waterfront listings")
    judge.check("answer_waterfront_most_expensive_title",
                contains_phrase(answer, "Brazos River Ranch"),
                "expected the most expensive waterfront '2,856 acre Brazos River Ranch'")
    judge.check("answer_waterfront_most_expensive_price",
                contains_money(answer, 39041450),
                "expected the most expensive waterfront at $39,041,450")
    judge.check("answer_waterfront_most_expensive_acres",
                contains_acres(answer, 2359),
                "expected the most expensive waterfront at 2,359 Acres")
    # statewide leg
    judge.check("answer_statewide_most_expensive_title",
                contains_phrase(answer, "Blake Ranch"),
                "expected the statewide most expensive 'Blake Ranch'")
    judge.check("answer_statewide_most_expensive_price",
                contains_money(answer, 56997000),
                "expected Blake Ranch at $56,997,000")
    # comparison: Blake Ranch costs more; the statewide champion is not waterfront
    judge.check("answer_blake_costs_more",
                bool(re.search(r"blake ranch[^.;]{0,120}"
                               r"(?:costs? more|more expensive|higher price|pricier|"
                               r"bigger price|larger price)", norm(answer))),
                "expected the answer to state that Blake Ranch costs more")
    judge.check("answer_statewide_champion_not_waterfront",
                bool(re.search(r"(?:not|isn'?t|n't)[^.;]{0,60}waterfront", norm(answer))
                     or re.search(r"non-?waterfront", norm(answer))),
                "expected the statewide champion to be stated as not waterfront")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
