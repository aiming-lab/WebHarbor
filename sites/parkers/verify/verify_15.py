#!/usr/bin/env python3
"""verify_15.py — deterministic verifier for task Parkers--15.

Browse hatchback reviews: report the top rating and at least three models that share it; then open one of their reviews and report one thing it likes about the car.

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

# Pros phrases of the eight 4.5-rated hatchbacks (frozen from the seed DB).
LIKE_PHRASES = [
    "distinctive looks", "sharp handling", "wonderful design and style throughout",
    "clever practicality features", "comfortable and easy to drive",
    "impressively responsive and efficient engine",
    "high-quality and good-looking interior", "ride and handling best in the class",
    "better than far more expensive rivals", "good ride/handling balance",
    "new physical controls are great", "strong performance", "retro styling",
    "great fun to drive", "funky interior", "classy interior", "tidy handling",
    "competitive pricing", "roomy interior and boot",
    "competitive entry-level prices", "good range of petrol engines",
    "handles well; comfortable ride", "bright and well-made interior",
    "very spacious for its size",
]


def navigated_to_path_hatchback(traj):
    from verify_lib import navigated_to_path
    return navigated_to_path(traj, "/car-reviews/hatchback")


TASK_ID = "Parkers--15"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_hatchback_class", navigated_to_path_hatchback(traj),
                "required: the hatchbacks reviews class page")
    judge.check("nav_one_review",
                any(navigated_review(traj, mk, mo) for mk, mo in
                    [("abarth", "500"), ("fiat", "grande-panda"), ("honda", "civic"),
                     ("mg", "mg4"), ("mini", "cooper-s"), ("renault", "5-e-tech"),
                     ("skoda", "fabia"), ("skoda", "kamiq")]),
                "required: open the review of one top-rated hatchback")
    judge.check("answer_top_rating", contains_count(answer, 4.5),
                "top hatchback rating is 4.5")
    judge.check("answer_three_models",
                sum(1 for p in ("abarth 500", "grande panda", "honda civic", "mg4",
                                "cooper s", "5 e-tech", "fabia", "kamiq")
                    if contains_phrase(answer, p)) >= 3,
                "at least three top-rated models must be named")
    judge.check("nav_fabia_review", navigated_review(traj, "skoda", "fabia"),
                "required: the Skoda Fabia review (the task names the Fabia)")
    judge.check("answer_one_like",
                contains_any_phrase(answer, LIKE_PHRASES),
                "one thing the review likes must be quoted")
    judge.check("nav_fabia_verdict",
                navigated_review_section(traj, "skoda", "fabia", "verdict"),
                "required: Fabia verdict section (practicality score)")
    judge.check("answer_fabia_practicality", contains_count(answer, 4),
                "the Fabia's practicality score from the verdict is 4")
    judge.check("nav_fabia_insurance",
                navigated_insurance(traj, "skoda", "fabia", "hatchback-2021"),
                "required: current Fabia insurance-groups page")
    judge.check("answer_fabia_group", contains_count(answer, 2),
                "the current Fabia's lowest insurance group is 2")
    judge.check("nav_fabia_specs",
                navigated_specs_gen(traj, "skoda", "fabia", "hatchback-2021"),
                "required: current Fabia specs page (price when new)")
    judge.check("answer_fabia_price_new", contains_amount(answer, 15720),
                "the cheapest current Fabia version costs £15,720 when new")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
