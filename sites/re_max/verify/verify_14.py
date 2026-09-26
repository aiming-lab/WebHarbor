#!/usr/bin/env python3
"""verify_14.py — deterministic verifier for task REMAX--14.

Seller-concessions article facts, the first-time-buyer cross-reference from
its More-from list (median sales price), and the Naples under-$500k
2+bed/2+bath filter chain (match count + cheapest match's price, address,
year built, price per square foot).

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
    nav_article, nav_ldp, nav_srp, run_verifier)

TASK_ID = "REMAX--14"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: both articles + the filtered Naples SRP + the cheapest
    # match's detail page
    judge.check("nav_article_concessions",
                nav_article(traj, "seller-concessions-2026"),
                "required: /advice/seller-concessions-2026")
    judge.check("nav_article_first_time_buyer",
                nav_article(traj, "buying-a-home-in-august-2026-as-a-first-time-buyer"),
                "required: /advice/buying-a-home-in-august-2026-as-a-first-time-buyer")
    judge.check("nav_naples_srp_filtered",
                nav_srp(traj, "fl", "naples", price_max="500000",
                        beds="2", baths="2"),
                "required: /fl/naples-real-estate with price_max=500000, "
                "beds=2, baths=2")
    judge.check("nav_ldp_315_saint_andrews", nav_ldp(traj, 142),
                "required: listing detail for 315 Saint Andrews Blvd Apt D31 (id 142)")
    # ground truth (frozen seed): conventional caps 2% to 9%; FHA and USDA
    # cap at 6%; concessions cannot cover the down payment; the first-time
    # buyer article cites a $450,000 median sales price; Naples chain: 5
    # matches, cheapest 315 Saint Andrews Blvd Apt D31 at $220,000, built
    # 1977, $195/sqft
    judge.check("answer_conventional_range",
                contains_phrase(answer, "2% to 9%"),
                "must state the 2% to 9% conventional range")
    judge.check("answer_fha_usda", contains_phrase(answer, "6%"),
                "must state FHA and USDA cap at 6%")
    judge.check("answer_down_payment",
                contains_any_phrase(answer, ["cannot cover the down payment",
                                             "can't cover the down payment",
                                             "barred from covering a down payment",
                                             "not cover the down payment"]),
                "must state concessions cannot cover the down payment")
    judge.check("answer_median_price", contains_amount(answer, 450000),
                "must quote the $450,000 median sales price")
    judge.check("answer_naples_count", contains_count(answer, 5),
                "must state 5 Naples matches")
    judge.check("answer_cheapest_price", contains_amount(answer, 220000),
                "must quote the cheapest match's $220,000")
    judge.check("answer_cheapest_address",
                contains_any_phrase(answer, ["315 Saint Andrews", "Saint Andrews Blvd"]),
                "must name 315 Saint Andrews Blvd Apt D31")
    judge.check("answer_cheapest_year", contains_phrase(answer, "1977"),
                "must state the cheapest match was built in 1977")
    judge.check("answer_cheapest_ppsf", contains_amount(answer, 195),
                "must quote the cheapest match's $195 per square foot")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
