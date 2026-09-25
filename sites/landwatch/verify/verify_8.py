#!/usr/bin/env python3
"""Verify LandWatch--8 — vetting the busiest land broker (Mac A. Coalson).

Ground truth (frozen seed): the Find an Agent directory's busiest broker is
Mac A. Coalson of Coalson Real Estate, based in Weatherford, TX, with 11
Total Listings, a $1.1M - $50M price range, and a 22.50 - 5896 ac acre range.
The first listing in his grid is '5,888-acre W-W Ranch' (Palo Pinto County,
TX): status Available, $49,985,000, 5,896 Acres, Type row 'Farms and
Ranches, Recreational Property, Hunting Property, House'.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_all,
                        contains_count, contains_money, contains_phrase, final_answer,
                        run_verifier)

TASK_ID = "LandWatch--8"
FIND_AGENT = "/find-agent"
COALSON_PROFILE = "/profile/mac-a-coalson/32197"
WW_DETAIL = "/palo-pinto-county-texas-farms-and-ranches-for-sale/pid/419682125"
WW_TYPES = ["Farms and Ranches", "Recreational Property", "Hunting Property", "House"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: directory -> profile -> first listing detail
    check_visited_path(judge, traj, "visited_find_agent", FIND_AGENT)
    check_visited_path(judge, traj, "visited_coalson_profile", COALSON_PROFILE)
    check_visited_path(judge, traj, "visited_first_listing_detail", WW_DETAIL)
    # broker profile facts
    judge.check("answer_agent_name", contains_phrase(answer, "Mac A. Coalson"),
                "expected the busiest agent Mac A. Coalson")
    judge.check("answer_agent_brokerage", contains_phrase(answer, "Coalson Real Estate"),
                "expected the brokerage Coalson Real Estate")
    judge.check("answer_agent_total_listings", contains_count(answer, 11),
                "expected 11 Total Listings")
    judge.check("answer_agent_price_range_floor",
                contains_phrase(answer, "1.1M") or contains_money(answer, 1050000),
                "expected the $1.1M price-range floor")
    judge.check("answer_agent_price_range_ceiling",
                contains_phrase(answer, "50M") or contains_money(answer, 49985000),
                "expected the $50M price-range ceiling")
    judge.check("answer_agent_acre_range",
                contains_phrase(answer, "22.50") and contains_phrase(answer, "5896"),
                "expected the 22.50 - 5896 ac acre range")
    judge.check("answer_agent_base", contains_phrase(answer, "Weatherford"),
                "expected the agent based in Weatherford")
    # first listing detail facts
    judge.check("answer_first_listing_title", contains_phrase(answer, "W-W Ranch"),
                "expected the first listing '5,888-acre W-W Ranch'")
    judge.check("answer_first_listing_status", contains_phrase(answer, "Available"),
                "expected the listing status Available")
    judge.check("answer_first_listing_price", contains_money(answer, 49985000),
                "expected the listing at $49,985,000")
    judge.check("answer_first_listing_acres", contains_acres(answer, 5896),
                "expected the listing at 5,896 Acres")
    judge.check("answer_first_listing_type_row", contains_all(answer, WW_TYPES),
                f"expected the full Type row {WW_TYPES!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
