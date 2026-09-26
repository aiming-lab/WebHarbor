#!/usr/bin/env python3
"""verify_4.py — deterministic verifier for task Parkers--4.

Civic Saloon (2018-2020) diesels: best MPG, price when new, automatic diesel MPG; the Civic's expert rating and the SE 120PS 1.6i-DTEC 4d insurance group.

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

TASK_ID = "Parkers--4"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_civic_specs",
                navigated_specs(traj, "honda", "civic", "saloon-2018",
                                ["se-120ps-16i-dtec-4d"]),
                "required: Civic SE 120PS 1.6i-DTEC 4d spec selection")
    judge.check("nav_civic_second_diesel",
                navigated_specs_any(traj, "honda", "civic", "saloon-2018",
                                    ["ex-120ps-16i-dtec-4d", "sr-120ps-16i-dtec-4d",
                                     "ex-120ps-16i-dtec-auto-4d"]),
                "required: a second diesel Civic spec selection")
    judge.check("answer_best_diesel", contains_phrase(answer, "se 120ps 1.6i-dtec"),
                "most economical diesel Civic is the SE 120PS 1.6i-DTEC 4d")
    judge.check("answer_mpg", contains_count(answer, 64.2),
                "official MPG is 64.2")
    judge.check("answer_price_new", contains_amount(answer, 21105),
                "price when new is £21,105")
    judge.check("nav_civic_review", navigated_review(traj, "honda", "civic"),
                "required: Civic expert review (overall rating)")
    judge.check("answer_expert_rating", contains_count(answer, 4.5),
                "Parkers' expert review gives the Civic 4.5 overall")
    judge.check("nav_civic_insurance",
                navigated_insurance(traj, "honda", "civic", "saloon-2018"),
                "required: Civic Saloon (2018-2020) insurance-groups page")
    judge.check("answer_insurance_group", contains_count(answer, 18),
                "the SE 120PS 1.6i-DTEC 4d sits in insurance group 18")
    judge.check("answer_other_mpg",
                contains_count(answer, 62.8) or contains_count(answer, 54.3)
                or contains_count(answer, 64.2),
                "other diesel Civic MPG: 62.8 (EX), 54.3 (EX auto) or 64.2 (SR)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
