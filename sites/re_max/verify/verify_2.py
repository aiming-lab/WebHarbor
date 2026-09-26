#!/usr/bin/env python3
"""verify_2.py — deterministic verifier for task REMAX--2.

Redmond newest-built home: report presenting office, price per sqft, parking spaces.

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
    contains_any_phrase, contains_phrase, final_answer, nav_ldp, nav_srp_any,
    run_verifier, site_urls)

TASK_ID = "REMAX--2"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: Redmond SRP + a real scan of Redmond detail pages
    # (year built is only disclosed on detail pages, so the honest path opens
    # many of them) + the newest-built listing's detail page
    judge.check("nav_redmond_srp", nav_srp_any(traj, "wa", "redmond"),
                "required: /wa/redmond-real-estate")
    ldp_visits = sum(1 for u in site_urls(traj)
                     if "/wa/redmond/home-details/" in u)
    judge.check("nav_redmond_ldp_scan", ldp_visits >= 10,
                f"required: >= 10 Redmond home-details visits, saw {ldp_visits}")
    judge.check("nav_ldp_16530_ne_99th", nav_ldp(traj, 403),
                "required: listing detail for 16530 NE 99th St (id 403)")
    # ground truth (frozen seed): built 2026; REMAX Eastside Brokers Inc;
    # $727/sqft; 3 parking spaces
    judge.check("answer_office",
                contains_any_phrase(answer, ["Eastside Brokers", "REMAX Eastside"]),
                "must name REMAX Eastside Brokers Inc as the presenting office")
    judge.check("answer_price_per_sqft", contains_amount(answer, 727),
                "must quote $727 per square foot")
    judge.check("answer_parking", contains_phrase(answer, "3 parking"),
                "must state 3 parking spaces")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
