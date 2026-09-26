#!/usr/bin/env python3
"""verify_3.py — deterministic verifier for task REMAX--3.

Denver vs Colorado Springs townhouses: open each of the four listing pages,
work out which gives more square footage per dollar, and report the winner's
address and city, year built, parking spaces, and the per-sqft spread to the
most expensive of the four.

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
    nav_ldp, nav_srp, run_verifier)

TASK_ID = "REMAX--3"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: both city SRPs filtered to Townhouse + all four LDPs
    judge.check("nav_denver_townhouse_srp",
                nav_srp(traj, "co", "denver", home_type="Townhouse"),
                "required: /co/denver-real-estate with home_type=Townhouse")
    judge.check("nav_cosprings_townhouse_srp",
                nav_srp(traj, "co", "colorado-springs", home_type="Townhouse"),
                "required: /co/colorado-springs-real-estate with home_type=Townhouse")
    for lid, street in ((81, "3437 W 63rd Pl"), (93, "1370 Lowell Blvd Unit 5"),
                        (65, "4867 Painted Sky VW"), (72, "3545 Clubheights Dr")):
        judge.check(f"nav_ldp_{lid}", nav_ldp(traj, lid),
                    f"required: listing detail for {street} (id {lid})")
    # ground truth (frozen seed): 4867 Painted Sky VW (Colorado Springs) at
    # $156/sqft is the winner; built 2026, 1 parking space; the most
    # expensive per sqft of the four is 3437 W 63rd Pl at $378/sqft, so the
    # spread is $222/sqft
    judge.check("answer_winner_address",
                contains_any_phrase(answer, ["4867 Painted Sky", "Painted Sky VW", "Painted Sky"]),
                "must name 4867 Painted Sky VW as the winner")
    judge.check("answer_winner_city",
                contains_any_phrase(answer, ["Colorado Springs"]),
                "must state the winner is in Colorado Springs")
    judge.check("answer_winner_ppsf", contains_amount(answer, 156),
                "must quote the winner's $156 per square foot")
    judge.check("answer_winner_year", contains_phrase(answer, "2026"),
                "must state the winner was built in 2026")
    judge.check("answer_winner_parking", contains_count(answer, 1),
                "must state the winner has 1 parking space")
    judge.check("answer_spread", contains_amount(answer, 222),
                "must state the $222 per-square-foot spread to the most expensive")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
