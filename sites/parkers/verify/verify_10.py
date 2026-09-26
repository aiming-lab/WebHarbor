#!/usr/bin/env python3
"""verify_10.py — deterministic verifier for task Parkers--10.

Read the Fiesta Hatchback (2017-2023) owner reviews: how many owners, average owner rating, one specific problem an owner mentions; then the expert review's overall rating.

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

TASK_ID = "Parkers--10"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_owner_reviews",
                navigated_owner_reviews(traj, "ford", "fiesta", "hatchback-2017"),
                "required: Fiesta Hatchback (2017-2023) owner reviews page")
    judge.check("nav_expert_review", navigated_review(traj, "ford", "fiesta"),
                "required: Fiesta expert review page")
    judge.check("answer_owner_count", contains_count(answer, 25),
                "25 owners have reviewed the Fiesta Hatchback (2017-2023)")
    judge.check("answer_average", contains_count(answer, 4),
                "average owner rating is 4 out of 5")
    judge.check("answer_expert_rating", contains_count(answer, 4),
                "expert review rating is 4 out of 5")
    # A-3 fixed: owner-review bodies are now rendered, so the problem
    # sub-question is answerable on-site (e.g. "Gearbox output bearing replaced
    # under warranty", "suspension fault, hybrid failure").
    judge.check("answer_problem",
                contains_any_phrase(answer, ["gearbox output bearing", "suspension fault",
                                             "hybrid failure", "problem", "fault",
                                             "issue", "failure", "broke"]),
                "one specific problem an owner mentions must be reported")
    judge.check("nav_verdict", navigated_review_section(traj, "ford", "fiesta", "verdict"),
                "required: Fiesta verdict section (reliability score)")
    judge.check("answer_reliability", contains_count(answer, 4),
                "reliability score from the verdict is 4")
    judge.check("nav_practicality",
                navigated_review_section(traj, "ford", "fiesta", "practicality"),
                "required: Fiesta practicality section (boot space point)")
    judge.check("answer_boot_point", contains_phrase(answer, "boot"),
                "the practicality point must mention the boot")
    judge.check("nav_zetec_specs",
                navigated_specs(traj, "ford", "fiesta", "hatchback-2017",
                                ["zetec-10t-ecoboost-100ps-3d"]),
                "required: Zetec spec page (luggage space)")
    judge.check("answer_luggage", contains_count(answer, 292),
                "the Zetec 1.0T EcoBoost 100PS 3d offers 292 litres")
    judge.check("nav_fiesta_listings",
                navigated_c4s_search(traj, make="ford", model="fiesta", sort="price-asc")
                or navigated_c4s_search(traj, make="ford", model="fiesta")
                or navigated_c4s_search(traj, make="ford"),
                "required: Fiesta cars-for-sale search")
    judge.check("answer_cheapest_fiesta", contains_amount(answer, 3950),
                "the cheapest Fiesta currently listed is £3,950")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
