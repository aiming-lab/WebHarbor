#!/usr/bin/env python3
"""verify_0.py — deterministic verifier for task Parkers--0.

Value the Ford Fiesta Zetec 1.0T EcoBoost 100PS 3d on a 2019/19 plate; report private-sale and dealer ranges plus the part-exchange value, the Pro Valuation cost, and the version's official MPG.

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

TASK_ID = "Parkers--0"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: the full valuation chain for the exact derivative + year
    judge.check("nav_valuation_chain",
                navigated_valuation_chain(traj, "ford", "fiesta", "hatchback-2017",
                                          "zetec-10t-ecoboost-100ps-3d", "2019/19", deriv_id=257),
                "required: fiesta hatchback-2017 used-prices (year 2019/19, version "
                "Zetec 1.0T EcoBoost 100PS 3d) -> select-a-valuation -> free-valuation")
    # ground truth (frozen seed): private 3210-4250, dealer 4520-4790, part-ex 3470-3800
    judge.check("answer_private_range", contains_amount_range(answer, 3210, 4250),
                "private-sale range must quote £3,210 and £4,250")
    judge.check("answer_dealer_range", contains_amount_range(answer, 4520, 4790),
                "dealer range must quote £4,520 and £4,790")
    judge.check("answer_part_ex", contains_amount_range(answer, 3470, 3800),
                "part-exchange value must quote £3,470 and £3,800")
    judge.check("nav_zetec_specs",
                navigated_specs(traj, "ford", "fiesta", "hatchback-2017",
                                ["zetec-10t-ecoboost-100ps-3d"]),
                "required: Zetec 1.0T EcoBoost 100PS 3d spec page (for the MPG)")
    judge.check("answer_pro_cost", contains_count(answer, 6.99),
                "a Parkers Pro Valuation of the same car costs £6.99")
    judge.check("answer_mpg", contains_count(answer, 50.4),
                "the Zetec 1.0T EcoBoost 100PS 3d achieves 50.4 mpg")
    judge.check("nav_valuation_vid", navigated_to_path(traj, "/ford/fiesta/hatchback-2017/zetec-10t-ecoboost-100ps-3d/2392/free-valuation"),
                "required: free-valuation page for valuation id 2392")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
