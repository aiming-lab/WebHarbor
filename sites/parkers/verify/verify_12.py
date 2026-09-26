#!/usr/bin/env python3
"""verify_12.py — deterministic verifier for task Parkers--12.

Find the Renault 5 E-Tech 2027 update news article: WLTP ranges for both battery sizes and the improvement; then the R5 E-Tech expert review's overall rating.

Ground truth below is HARDCODED (frozen against the shipped seed DB); it never
appears in tasks.jsonl. Navigation gates encode the honest on-site path the
task text implies; a correct answer without that navigation is a shortcut and
fails. See verify_lib.py for the shared contract.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_lib import (  # noqa: E402
    Judge, check_read_only, check_seed_contract, check_trajectory_identity,
    contains_amount, contains_amount_range, contains_any_phrase, contains_count,
    contains_phrase, final_answer, navigated_c4s_search, navigated_cartax_gen,
    navigated_cartax_hub, navigated_guide, navigated_insurance,
    navigated_listing_detail, navigated_news, navigated_owner_reviews,
    navigated_reg_lookup, navigated_review, navigated_review_section,
    navigated_shortlist, navigated_sign_in, navigated_site_search,
    navigated_specs, navigated_specs_gen, navigated_valuation_chain,
    run_verifier, shortlist_listing_ids, added_rows, removed_rows, rows_of,
    user_by_email)

TASK_ID = "Parkers--12"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_news", navigated_news(traj, "renault-5-e-tech-updated-for-2027"),
                "required: the Renault 5 E-Tech 2027 update news article")
    judge.check("nav_review", navigated_review(traj, "renault", "5-e-tech"),
                "required: Renault 5 E-Tech expert review")
    judge.check("answer_40kwh", contains_count(answer, 197),
                "40kWh model WLTP range is 197 miles")
    judge.check("answer_52kwh", contains_count(answer, 259),
                "52kWh model WLTP range is 259 miles")
    judge.check("answer_improvement", contains_count(answer, 11),
                "range improved by 11 miles")
    judge.check("answer_rating", contains_count(answer, 4.5),
                "R5 E-Tech expert rating is 4.5")
    judge.check("nav_ownership",
                navigated_review_section(traj, "renault", "5-e-tech", "mpg-running-costs"),
                "required: 5 E-Tech ownership cost section (running-costs fact)")
    judge.check("answer_running_costs_fact",
                contains_any_phrase(answer, ["insurance group", "mpg", "running cost",
                                             "road tax", "charging"]),
                "a running-costs fact from the ownership cost section must be reported")
    judge.check("nav_verdict", navigated_review_section(traj, "renault", "5-e-tech", "verdict"),
                "required: 5 E-Tech verdict section (reliability score)")
    judge.check("answer_reliability", contains_count(answer, 4),
                "reliability score from the verdict is 4")
    judge.check("nav_insurance",
                navigated_insurance(traj, "renault", "5-e-tech", "hatchback-2025"),
                "required: 5 E-Tech insurance-groups page")
    judge.check("answer_insurance_range",
                contains_count(answer, 18) and contains_count(answer, 23),
                "the 5 E-Tech's insurance groups run from 18 to 23")
    judge.check("nav_small_electric_guide", navigated_guide(traj, "small-electric-cars"),
                "required: best small electric cars guide (5 E-Tech rank)")
    judge.check("answer_guide_rank", contains_count(answer, 3),
                "the best small electric cars guide ranks the 5 E-Tech third")
    judge.check("nav_5etech_specs",
                navigated_specs_gen(traj, "renault", "5-e-tech", "hatchback-2025"),
                "required: 5 E-Tech specs page (cheapest price when new)")
    judge.check("answer_price_new", contains_amount(answer, 22995),
                "the cheapest 5 E-Tech version costs £22,995 when new")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
