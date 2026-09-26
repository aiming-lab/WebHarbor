#!/usr/bin/env python3
"""verify_14.py — deterministic verifier for task Parkers--14.

Using the car tax pages: standard annual petrol rate, what electric cars pay per year, first-year rate for 131-150 g/km; then the Fiesta Zetec 1.0T EcoBoost 100PS annual car tax.

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
    navigated_specs, navigated_specs_any, navigated_specs_gen, navigated_valuation_chain,
    run_verifier, shortlist_listing_ids, added_rows, removed_rows, rows_of,
    user_by_email)

TASK_ID = "Parkers--14"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_cartax_hub", navigated_cartax_hub(traj),
                "required: the car tax page with the rates table")
    judge.check("nav_fiesta_tax",
                navigated_cartax_gen(traj, "ford", "fiesta", "hatchback-2017")
                or navigated_specs(traj, "ford", "fiesta", "hatchback-2017",
                                   ["zetec-10t-ecoboost-100ps-3d"]),
                "required: Fiesta per-car tax (car-tax page or Zetec spec page)")
    # A-4 fixed: the rates table is now the live 2026/27 tax year
    # (£200 standard / £10 EV first-year then standard / £560 for 131-150),
    # matching the per-car values and the live upstream rates page.
    judge.check("answer_standard_rate", contains_amount(answer, 200),
                "standard annual rate for a petrol car is £200")
    judge.check("answer_ev_rate",
                contains_count(answer, 10)
                and (contains_amount(answer, 200) or contains_phrase(answer, "standard")),
                "electric cars pay a £10 first-year rate then the standard rate")
    judge.check("answer_first_year_131_150", contains_amount(answer, 560),
                "first-year rate for 131-150 g/km is £560")
    judge.check("answer_fiesta_tax", contains_amount(answer, 200),
                "the Fiesta Zetec 1.0T EcoBoost 100PS pays £200 a year")
    judge.check("nav_bmw_tax",
                navigated_cartax_gen(traj, "bmw", "3-series", "saloon-2012"),
                "required: 3 Series Saloon (2012 - 2019) car-tax page (320d)")
    judge.check("answer_320d_tax", contains_amount(answer, 20),
                "the BMW 320d EfficientDynamics Plus pays £20 a year")
    judge.check("nav_bmw_insurance",
                navigated_insurance(traj, "bmw", "3-series", "saloon-2012"),
                "required: 3 Series Saloon (2012 - 2019) insurance-groups page")
    judge.check("answer_320d_group", contains_count(answer, 27),
                "the 320d EfficientDynamics Plus sits in insurance group 27")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
