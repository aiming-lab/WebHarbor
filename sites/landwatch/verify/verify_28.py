#!/usr/bin/env python3
"""Verify LandWatch--28 — First listing on the United States Land for Sale page.

Ground truth (frozen seed): the first /land card is 'Sisterdale Farms' —
status Available, $19,400,000, 310 Acres, Type row 'Farms and Ranches,
Recreational Property, Riverfront Property, Waterfront Property, House',
gallery 'View all 93 pictures'.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_count,
                        contains_money, contains_phrase, final_answer,
                        phrases_in_order, run_verifier)

TASK_ID = "LandWatch--28"
LAND_PATH = "/land"
DETAIL_PATH = "/kendall-county-texas-farms-and-ranches-for-sale/pid/425766087"
TYPES = ["Farms and Ranches", "Recreational Property", "Riverfront Property",
         "Waterfront Property", "House"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_us_land_page", LAND_PATH)
    check_visited_path(judge, traj, "visited_first_listing_detail", DETAIL_PATH)
    judge.check("answer_status", contains_phrase(answer, "Available"),
                "expected the listing status Available")
    judge.check("answer_price", contains_money(answer, 19400000),
                "expected $19,400,000")
    judge.check("answer_acres", contains_acres(answer, 310), "expected 310 Acres")
    judge.check("answer_types_in_order", phrases_in_order(answer, TYPES),
                f"expected the Type row in order: {', '.join(TYPES)}")
    judge.check("answer_gallery_pictures", contains_count(answer, 93),
                "expected the gallery to list 93 pictures")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
