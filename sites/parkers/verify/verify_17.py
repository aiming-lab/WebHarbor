#!/usr/bin/env python3
"""verify_17.py — deterministic verifier for task Parkers--17.

Value the Fiesta 1.0 EcoBoost 100 ST-Line Edition 3dr on 2023/23; then find the cheapest Fiesta listed and say whether its asking price falls inside or below the private-sale range.

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
    navigated_to_path, navigated_reg_lookup, navigated_review, navigated_review_section,
    navigated_shortlist, navigated_sign_in, navigated_site_search,
    navigated_specs, navigated_specs_gen, navigated_valuation_chain,
    run_verifier, shortlist_listing_ids, added_rows, removed_rows, rows_of,
    user_by_email)

TASK_ID = "Parkers--17"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_valuation_chain",
                navigated_valuation_chain(traj, "ford", "fiesta", "hatchback-2017",
                                          "10-ecoboost-100-st-line-edition-3dr", "2023/23", deriv_id=253),
                "required: Fiesta valuation chain for 1.0 EcoBoost 100 ST-Line "
                "Edition 3dr 2023/23")
    judge.check("nav_fiesta_listings",
                navigated_c4s_search(traj, make="ford", model="fiesta", sort="price-asc")
                or navigated_c4s_search(traj, make="ford", model="fiesta"),
                "required: Fiesta cars-for-sale search")
    judge.check("answer_private_range", contains_amount_range(answer, 7160, 9500),
                "private-sale range is £7,160 - £9,500")
    judge.check("answer_cheapest_fiesta", contains_amount(answer, 3950),
                "cheapest Fiesta listing is £3,950 (2014/14)")
    judge.check("answer_position", contains_phrase(answer, "below"),
                "£3,950 falls below the private-sale range")
    judge.check("nav_valuation_vid", navigated_to_path(traj, "/ford/fiesta/hatchback-2017/10-ecoboost-100-st-line-edition-3dr/2354/free-valuation"),
                "required: free-valuation page for valuation id 2354")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
