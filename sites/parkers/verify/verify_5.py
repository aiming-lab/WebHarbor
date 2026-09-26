#!/usr/bin/env python3
"""verify_5.py — deterministic verifier for task Parkers--5.

Report the lowest insurance group for the current VW Polo and Ford Fiesta, the versions that achieve them, and which car is cheaper to insure.

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

TASK_ID = "Parkers--5"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_polo_insurance",
                navigated_insurance(traj, "volkswagen", "polo", "hatchback-2017"),
                "required: Polo insurance-groups page")
    judge.check("nav_fiesta_insurance",
                navigated_insurance(traj, "ford", "fiesta", "hatchback-2017"),
                "required: Fiesta insurance-groups page")
    judge.check("answer_polo_group", contains_count(answer, 1),
                "Polo's lowest insurance group is 1")
    judge.check("answer_polo_version",
                contains_phrase(answer, "1.0 evo 80 active") or contains_phrase(answer, "beats 1.0 65ps"),
                "Polo group-1 versions: 1.0 EVO 80 Active 5dr / Beats 1.0 65PS 5d")
    judge.check("answer_fiesta_group", contains_count(answer, 10),
                "Fiesta's lowest insurance group is 10")
    judge.check("answer_fiesta_version", contains_phrase(answer, "zetec 1.0t ecoboost 100ps"),
                "Fiesta group-10 version: Zetec 1.0T EcoBoost 100PS 3d")
    judge.check("nav_polo_listings",
                navigated_c4s_search(traj, make="volkswagen", model="polo", sort="price-asc")
                or navigated_c4s_search(traj, make="volkswagen", model="polo")
                or navigated_c4s_search(traj, make="volkswagen"),
                "required: Polo cars-for-sale search")
    judge.check("answer_cheapest_polo", contains_amount(answer, 5995),
                "the cheapest Polo currently listed is £5,995")
    judge.check("answer_cheaper", contains_phrase(answer, "polo"),
                "the Polo is cheaper to insure")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
