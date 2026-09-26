#!/usr/bin/env python3
"""verify_16.py — deterministic verifier for task Parkers--16.

Use Parkers' search to find the Hyundai Ioniq 5 expert review: report its overall rating, one pro and one con; then the private-sale range of the cheapest Ioniq 5 version on the newest year plate.

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

TASK_ID = "Parkers--16"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_site_search", navigated_site_search(traj, ["ioniq"]),
                "required: site search used for the Ioniq 5")
    judge.check("nav_review", navigated_review(traj, "hyundai", "ioniq-5"),
                "required: Ioniq 5 expert review")
    judge.check("nav_valuation_chain",
                navigated_valuation_chain(traj, "hyundai", "ioniq-5", "suv-2021",
                                          "125kw-advance-63-kwh-5dr-auto", "2026/76", deriv_id=367),
                "required: Ioniq 5 valuation chain for 125kW Advance 63 kWh 2026/76")
    judge.check("answer_rating", contains_count(answer, 4.1),
                "Ioniq 5 overall rating is 4.1")
    judge.check("answer_pro",
                contains_any_phrase(answer, ["roomy for people and luggage",
                                             "good to drive, great to look at",
                                             "long-range version available"]),
                "one pro must be quoted")
    judge.check("answer_con",
                contains_any_phrase(answer, ["driving range could be better",
                                             "not as comfortable as some rivals",
                                             "it feels bulky on city streets"]),
                "one con must be quoted")
    judge.check("nav_verdict",
                navigated_review_section(traj, "hyundai", "ioniq-5", "verdict"),
                "required: Ioniq 5 verdict section (reliability score)")
    judge.check("answer_reliability", contains_count(answer, 4.5),
                "reliability score from the verdict is 4.5")
    judge.check("answer_private_range", contains_amount_range(answer, 35000, 46400),
                "private-sale range for the cheapest version on 2026/76 is "
                "£35,000 - £46,400")
    judge.check("nav_valuation_vid", navigated_to_path(traj, "/hyundai/ioniq-5/suv-2021/125kw-advance-63-kwh-5dr-auto/3502/free-valuation"),
                "required: free-valuation page for valuation id 3502")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
