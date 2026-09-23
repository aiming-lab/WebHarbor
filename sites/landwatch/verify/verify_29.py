#!/usr/bin/env python3
"""Verify LandWatch--29 — Profile of the Find an Agent leader.

Ground truth (frozen seed): Mac A. Coalson of Coalson Real Estate — 11 Total
Listings, Price Range $1.1M - $50M, Acre Range 22.50 - 5896 ac; the first
listing in the grid is '5,888-acre W-W Ranch' at $49,985,000.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "LandWatch--29"
FIND_AGENT_PATH = "/find-agent"
PROFILE_PATH = "/profile/mac-a-coalson/32197"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_find_agent", FIND_AGENT_PATH)
    check_visited_path(judge, traj, "visited_coalson_profile", PROFILE_PATH)
    judge.check("answer_name", contains_phrase(answer, "Mac A. Coalson"),
                "expected Mac A. Coalson")
    judge.check("answer_brokerage", contains_phrase(answer, "Coalson Real Estate"),
                "expected Coalson Real Estate")
    judge.check("answer_total_listings", contains_count(answer, 11),
                "expected 11 Total Listings")
    judge.check("answer_price_range", contains_phrase(answer, "$1.1M") and
                contains_phrase(answer, "$50M"), "expected Price Range $1.1M - $50M")
    judge.check("answer_acre_range", contains_phrase(answer, "22.50") and
                (contains_phrase(answer, "5896") or contains_phrase(answer, "5,896"))
                and contains_phrase(answer, "ac"),
                "expected Acre Range 22.50 - 5896 ac")
    judge.check("answer_first_listing_title", contains_phrase(answer, "W-W Ranch"),
                "expected the first listing '5,888-acre W-W Ranch'")
    judge.check("answer_first_listing_price", contains_money(answer, 49985000),
                "expected the first listing price $49,985,000")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
