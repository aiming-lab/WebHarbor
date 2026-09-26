#!/usr/bin/env python3
"""verify_18.py — deterministic verifier for task Parkers--18.

Find the newest Dacia Sandero; value its cheapest version on a 2023/73 plate; report the exact version name and private-sale range.

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

TASK_ID = "Parkers--18"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_valuation_chain",
                navigated_valuation_chain(traj, "dacia", "sandero", "hatchback-2021",
                                          "10-sce-access-5dr", "2023/73", deriv_id=190),
                "required: Sandero valuation chain for 1.0 SCe Access 5dr 2023/73")
    judge.check("answer_version", contains_phrase(answer, "1.0 sce access 5dr"),
                "the exact version is the 1.0 SCe Access 5dr")
    judge.check("answer_private_range", contains_amount_range(answer, 2850, 3770),
                "private-sale range is £2,850 - £3,770")
    judge.check("answer_dealer_range", contains_amount_range(answer, 4020, 4260),
                "dealer range is £4,020 - £4,260")
    judge.check("answer_part_ex", contains_amount_range(answer, 3080, 3380),
                "part-exchange value is £3,080 - £3,380")
    judge.check("nav_sandero_listings",
                navigated_c4s_search(traj, make="dacia", model="sandero", sort="price-asc")
                or navigated_c4s_search(traj, make="dacia", model="sandero")
                or navigated_c4s_search(traj, make="dacia"),
                "required: Sandero cars-for-sale search")
    judge.check("answer_cheapest_sandero", contains_amount(answer, 3250),
                "the cheapest Sandero currently listed is £3,250")
    judge.check("answer_position", contains_phrase(answer, "inside"),
                "£3,250 falls inside the £2,850 - £3,770 private-sale range")
    judge.check("nav_valuation_vid", navigated_to_path(traj, "/dacia/sandero/hatchback-2021/10-sce-access-5dr/1749/free-valuation"),
                "required: free-valuation page for valuation id 1749")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
