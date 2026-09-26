#!/usr/bin/env python3
"""verify_16.py — deterministic verifier for task REMAX--16.

REMAX Collection totals, cheapest Florida and Washington luxury homes, then
the Miami >=$2M 4+bed and Seattle >=$2M price-filter chains.

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
    nav_luxury, nav_srp, run_verifier)

TASK_ID = "REMAX--16"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: the luxury page + both filtered city SRPs
    judge.check("nav_luxury", nav_luxury(traj), "required: /luxury")
    judge.check("nav_miami_srp_filtered",
                nav_srp(traj, "fl", "miami", price_min="2000000", beds="4"),
                "required: /fl/miami-real-estate with price_min=2000000, beds=4")
    judge.check("nav_seattle_srp_filtered",
                nav_srp(traj, "wa", "seattle", price_min="2000000"),
                "required: /wa/seattle-real-estate with price_min=2000000")
    # ground truth (frozen seed): 37 luxury properties; cheapest FL luxury
    # 5759 SW 42nd St (Miami) $2,350,000; cheapest WA luxury 12290 235th Pl
    # NE (Redmond) $2,050,000; Miami >=$2M 4+bd: 1 match at $2,350,000;
    # Seattle >=$2M: 2 matches, most expensive $2,595,000 (3715 Cascadia
    # Ave S)
    judge.check("answer_luxury_total", contains_count(answer, 37),
                "must state 37 luxury properties in total")
    judge.check("answer_fl_cheapest_addr",
                contains_any_phrase(answer, ["5759 SW 42nd", "SW 42nd St"]),
                "must name 5759 SW 42nd St as the cheapest FL luxury home")
    judge.check("answer_fl_cheapest_price", contains_amount(answer, 2350000),
                "must quote the $2,350,000 FL cheapest price")
    judge.check("answer_wa_cheapest_addr",
                contains_any_phrase(answer, ["12290 235th", "235th Pl NE"]),
                "must name 12290 235th Pl NE as the cheapest WA luxury home")
    judge.check("answer_wa_cheapest_price", contains_amount(answer, 2050000),
                "must quote the $2,050,000 WA cheapest price")
    judge.check("answer_miami_count", contains_count(answer, 1),
                "must state 1 Miami match at $2M+ with 4+ beds")
    judge.check("answer_miami_cheapest", contains_amount(answer, 2350000),
                "must quote the Miami cheapest match $2,350,000")
    judge.check("answer_seattle_count", contains_count(answer, 2),
                "must state 2 Seattle matches at $2M+")
    judge.check("answer_seattle_max", contains_amount(answer, 2595000),
                "must quote the Seattle most expensive $2,595,000")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
