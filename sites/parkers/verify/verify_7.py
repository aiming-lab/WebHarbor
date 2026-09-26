#!/usr/bin/env python3
"""verify_7.py — deterministic verifier for task Parkers--7.

Compare Audi A3 vs MINI Cooper practicality ratings in their verdicts; then compare luggage space on the spec pages and report the difference.

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

TASK_ID = "Parkers--7"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_a3_verdict", navigated_review_section(traj, "audi", "a3", "verdict"),
                "required: A3 review verdict")
    judge.check("nav_cooper_verdict", navigated_review_section(traj, "mini", "cooper", "verdict"),
                "required: MINI Cooper review verdict")
    judge.check("nav_a3_specs",
                navigated_specs(traj, "audi", "a3", "sportback-2020",
                                ["15-tfsi-116-s-line-5dr"])
                or navigated_specs_any(traj, "audi", "a3", "sportback-2020",
                                    ["15-tfsi-116-s-line-5dr", "15-tfsi-116-sport-4dr",
                                     "15-tfsi-150-black-edition-4dr", "15-tfsi-150-black-edition-5dr"])
                or navigated_specs_any(traj, "audi", "a3", "saloon-2020",
                                       ["15-tfsi-116-s-line-4dr", "15-tfsi-116-sport-4dr",
                                        "15-tfsi-150-black-edition-4dr"]),
                "required: an A3 spec selection")
    judge.check("nav_cooper_specs",
                navigated_specs(traj, "mini", "cooper", "hatchback-2024",
                                ["15-c-classic-3dr-auto"])
                or navigated_specs_any(traj, "mini", "cooper", "hatchback-2024",
                                    ["15-c-classic-3dr-auto", "15-c-paul-smith-edition-3dr-auto",
                                     "15-one-classic-3dr-auto", "20-s-classic-3dr-auto",
                                     "15-c-exclusive-3dr-auto", "15-c-sport-3dr-auto"]),
                "required: a MINI Cooper spec selection")
    judge.check("answer_a3_practicality", contains_count(answer, 4),
                "A3 practicality rating is 4")
    judge.check("answer_cooper_practicality", contains_count(answer, 2.2),
                "MINI Cooper practicality rating is 2.2")
    judge.check("answer_scores_higher", contains_phrase(answer, "a3"),
                "the A3 scores higher")
    judge.check("answer_by_how_much", contains_count(answer, 1.8),
                "A3 leads by 1.8")
    # luggage: variant-dependent (A3 Saloon 425 / Sportback 380; Cooper 210 / 160)
    judge.check("answer_a3_boot", contains_count(answer, 380),
                "the A3 Sportback 1.5 TFSI 116 S Line 5dr offers 380 litres")
    judge.check("answer_cooper_boot", contains_count(answer, 210),
                "the MINI 1.5 C Classic 3dr Auto offers 210 litres")
    judge.check("answer_difference", contains_count(answer, 170),
                "the luggage difference between the named versions is 170 litres")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
