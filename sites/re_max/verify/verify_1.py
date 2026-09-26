#!/usr/bin/env python3
"""verify_1.py — deterministic verifier for task REMAX--1.

Redmond Condo <$700k 2+bd: sort by price, open BOTH matches; each one's
open-house status/day/window, plus the cheaper one's price per square foot
and parking spaces.

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
    mentions_near, nav_ldp, nav_srp, run_verifier)

TASK_ID = "REMAX--1"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: filtered Redmond SRP + BOTH matching detail pages
    judge.check("nav_redmond_srp_filtered",
                nav_srp(traj, "wa", "redmond", home_type="Condo",
                        price_max="700000", beds="2"),
                "required: /wa/redmond-real-estate with home_type=Condo, "
                "price_max=700000, beds=2")
    judge.check("nav_ldp_6439_139th", nav_ldp(traj, 401),
                "required: listing detail for 6439 139th Ave NE Apt 19 (id 401)")
    judge.check("nav_ldp_7525_old_redmond", nav_ldp(traj, 397),
                "required: listing detail for 7525 Old Redmond Rd # 403 (id 397)")
    # ground truth (frozen seed): 6439 139th Ave NE Apt 19 — open house
    # Sunday September 27th 3-5pm, $446/sqft, 1 parking space;
    # 7525 Old Redmond Rd # 403 — no open house scheduled
    judge.check("answer_cheaper_oh_day",
                mentions_near(answer, "139th", "September 27th"),
                "must state the cheaper condo's open-house day (September 27th, "
                "bound to 6439 139th Ave NE Apt 19)")
    judge.check("answer_cheaper_oh_time",
                mentions_near(answer, "139th", "3-5pm"),
                "must state the cheaper condo's open-house window (3-5pm, bound to "
                "6439 139th Ave NE Apt 19)")
    judge.check("answer_cheaper_ppsf", contains_amount(answer, 446),
                "must quote the cheaper condo's $446 per square foot")
    judge.check("answer_cheaper_parking", contains_count(answer, 1),
                "must state the cheaper condo has 1 parking space")
    judge.check("answer_other_no_oh",
                mentions_near(answer, "7525", "no open house") or
                mentions_near(answer, "Old Redmond", "no open house"),
                "must state 7525 Old Redmond Rd # 403 has no open house (bound to it)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
