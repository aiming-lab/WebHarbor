#!/usr/bin/env python3
"""verify_13.py — deterministic verifier for task Parkers--13.

Open the best family SUVs 2026 guide: report the #1 pick and two further SUVs; then the cheapest Audi Q3 listed for sale.

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

TASK_ID = "Parkers--13"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_guide", navigated_guide(traj, "family-suvs"),
                "required: the best family SUVs 2026 guide")
    judge.check("nav_q3_listings",
                navigated_c4s_search(traj, make="audi", model="q3")
                or navigated_c4s_search(traj, make="audi"),
                "required: Audi (Q3) cars-for-sale search")
    judge.check("answer_number_one", contains_phrase(answer, "renault scenic e-tech"),
                "the #1 pick is the Renault Scenic E-Tech")
    judge.check("answer_two_more",
                sum(1 for p in ("audi q3", "skoda elroq", "nissan qashqai", "skoda karoq",
                                "cupra terramar", "hyundai tucson", "kia sportage",
                                "dacia bigster", "mg hs")
                    if contains_phrase(answer, p)) >= 2,
                "two further recommended SUVs must be named")
    judge.check("answer_one_to_avoid", contains_phrase(answer, "skywell be11"),
                "the guide's one to avoid is the Skywell BE11")
    judge.check("nav_q3_review", navigated_review(traj, "audi", "q3"),
                "required: Audi Q3 expert review (rating)")
    judge.check("answer_q3_rating", contains_count(answer, 4),
                "the Q3's review rating is 4")
    judge.check("answer_cheapest_q3", contains_amount(answer, 5795),
                "cheapest Audi Q3 is £5,795 (2013/13)")
    judge.check("nav_q3_cartax",
                navigated_cartax_gen(traj, "audi", "q3", "sportback-2025"),
                "required: current Q3 car-tax page")
    judge.check("answer_q3_tax", contains_amount(answer, 200),
                "a current Q3 pays £200 in annual road tax")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
