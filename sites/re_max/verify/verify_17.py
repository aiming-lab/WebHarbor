#!/usr/bin/env python3
"""verify_17.py — deterministic verifier for task REMAX--17.

Arizona city stats (most listings), then the Phoenix open-house houses with
2+ baths chain (match count) and the cheapest match's listing-page facts
(address, price, every open-house window, price per square foot, year built).

Ground truth below is HARDCODED (frozen against the shipped seed DB); it never
appears in tasks.jsonl. Navigation gates encode the honest on-site path the
task text implies; a correct answer without that navigation is a shortcut and
fails. See verify_lib.py for the shared contract.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_lib import (  # noqa: E402
    Judge, check_read_only, check_trajectory_identity, contains_amount,
    contains_any_phrase, contains_count, contains_phrase, final_answer,
    nav_ldp, nav_srp, nav_state_page, run_verifier)

TASK_ID = "REMAX--17"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: the AZ state page + the filtered Phoenix SRP + the
    # cheapest match's detail page
    judge.check("nav_az_state", nav_state_page(traj, "az"),
                "required: /homes-for-sale/az state page")
    judge.check("nav_phoenix_oh_house_2bath",
                nav_srp(traj, "az", "phoenix", home_type="House",
                        baths="2", open_house="1"),
                "required: /az/phoenix-real-estate with home_type=House, "
                "baths=2, open_house=1")
    judge.check("nav_ldp_22627_31st_ave", nav_ldp(traj, 6),
                "required: listing detail for 22627 N 31st Ave (id 6)")
    # ground truth (frozen seed): Phoenix has the most AZ listings (20); 3
    # open-house houses with 2+ baths match; cheapest 22627 N 31st Ave at
    # $589,700, open houses Friday September 25th 4-7pm and Saturday
    # September 26th 10-1pm, $320/sqft, built 1993
    judge.check("answer_city", contains_phrase(answer, "Phoenix"),
                "must state Phoenix has the most listings")
    judge.check("answer_city_count", contains_count(answer, 20),
                "must state Phoenix's 20 listings")
    judge.check("answer_match_count", contains_count(answer, 3),
                "must state 3 open-house houses match")
    judge.check("answer_address",
                contains_any_phrase(answer, ["22627 N 31st", "N 31st Ave"]),
                "must name 22627 N 31st Ave")
    judge.check("answer_price", contains_amount(answer, 589700),
                "must quote the $589,700 price")
    judge.check("answer_friday_window", contains_phrase(answer, "4-7pm"),
                "must state the Friday September 25th 4-7pm window")
    judge.check("answer_saturday_window", contains_phrase(answer, "10-1pm"),
                "must state the Saturday September 26th 10-1pm window")
    judge.check("answer_ppsf", contains_amount(answer, 320),
                "must quote the $320 per square foot")
    judge.check("answer_year", contains_phrase(answer, "1993"),
                "must state the 1993 year built")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
