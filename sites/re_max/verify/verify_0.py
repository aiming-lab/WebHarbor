#!/usr/bin/env python3
"""verify_0.py — deterministic verifier for task REMAX--0.

Austin House $600k-$900k 4+bd: sort by price, open the three cheapest matches;
cheapest one's year built / $-per-sqft / HOA fee / open-house status, plus the
open-house day and time window shown on each of the other two pages.

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
    contains_any_phrase, contains_phrase, final_answer, mentions_near,
    nav_ldp, nav_srp, run_verifier)

TASK_ID = "REMAX--0"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: filtered + price-sorted Austin SRP and all three
    # cheapest matches' detail pages
    judge.check("nav_austin_srp_filtered",
                nav_srp(traj, "tx", "austin", home_type="House",
                        price_min="600000", price_max="900000", beds="4"),
                "required: /tx/austin-real-estate with home_type=House, "
                "price_min=600000, price_max=900000, beds=4")
    judge.check("nav_ldp_17_chandon", nav_ldp(traj, 273),
                "required: listing detail for 17 Chandon Ln (id 273)")
    judge.check("nav_ldp_8309_pompano", nav_ldp(traj, 274),
                "required: listing detail for 8309 Pompano Cv (id 274)")
    judge.check("nav_ldp_4602_trail_crest", nav_ldp(traj, 275),
                "required: listing detail for 4602 Trail Crest Cir (id 275)")
    # ground truth (frozen seed): 17 Chandon Ln — built 2007, $251/sqft,
    # $700 quarterly HOA, open house Saturday September 26th 2-4pm;
    # 8309 Pompano Cv — open house Sunday September 27th 11:3-2pm (upstream
    # quirk preserved); 4602 Trail Crest Cir — open house Saturday
    # September 26th 11-1pm
    judge.check("answer_year_built", contains_phrase(answer, "2007"),
                "must state the home was built in 2007")
    judge.check("answer_price_per_sqft", contains_amount(answer, 251),
                "must quote $251 per square foot")
    judge.check("answer_hoa_fee", contains_amount(answer, 700),
                "must quote the $700 HOA fee")
    judge.check("answer_hoa_frequency", contains_phrase(answer, "quarterly"),
                "must state the HOA fee is quarterly")
    judge.check("answer_cheapest_oh", contains_phrase(answer, "2-4pm"),
                "must state the cheapest home's open-house window 2-4pm")
    judge.check("answer_pompano_oh_day",
                mentions_near(answer, "Pompano", "September 27th"),
                "must state 8309 Pompano Cv's open-house day (September 27th, bound to Pompano)")
    judge.check("answer_pompano_oh_time",
                mentions_near(answer, "Pompano", "11:3-2pm"),
                "must state 8309 Pompano Cv's open-house window as shown (11:3-2pm, "
                "bound to Pompano)")
    judge.check("answer_trail_crest_oh_day",
                mentions_near(answer, "Trail Crest", "September 26th"),
                "must state 4602 Trail Crest Cir's open-house day (September 26th, "
                "bound to Trail Crest)")
    judge.check("answer_trail_crest_oh_time",
                mentions_near(answer, "Trail Crest", "11-1pm"),
                "must state 4602 Trail Crest Cir's open-house window (11-1pm, "
                "bound to Trail Crest)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
