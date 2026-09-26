#!/usr/bin/env python3
"""verify_9.py — deterministic verifier for task Parkers--9.

Sign in as bob; remove the most expensive car from the shortlist, report the remaining cars and their combined price; then find and save the cheapest car listed on Parkers.

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

TASK_ID = "Parkers--9"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_sign_in", navigated_sign_in(traj),
                "required: sign-in page")
    judge.check("nav_shortlist", navigated_shortlist(traj),
                "required: shortlist page visit")
    judge.check("nav_c4s_cheapest", navigated_c4s_search(traj, sort="price-asc"),
                "required: all-cars search sorted by price ascending")
    judge.check("nav_listing_detail", navigated_listing_detail(traj, 959),
                "required: open the cheapest listing (Fiat Panda 2004/04, id 959)")
    judge.check("answer_removed", contains_amount(answer, 2395),
                "the removed car is the £2,395 Fiat Panda (2011/11)")
    judge.check("answer_remaining",
                contains_amount(answer, 1695) and contains_amount(answer, 1990)
                and contains_amount(answer, 2295),
                "remaining cars: Honda Jazz £1,695, Mazda 6 £1,990, Fiat Panda £2,295")
    judge.check("answer_combined", contains_amount(answer, 5980),
                "combined price is £5,980")
    judge.check("answer_cheapest", contains_amount(answer, 1295),
                "cheapest car overall is the Fiat Panda (2004/04) at £1,295")
    judge.check("answer_cheapest_mileage", contains_count(answer, 87000),
                "the cheapest car has 87,000 miles")
    judge.check("nav_saved_valuations",
                navigated_to_path(traj, "/my-parkers/saved-valuations"),
                "required: saved-valuations page (final counts check)")
    judge.check("answer_shortlist_count", contains_count(answer, 4),
                "the shortlist now contains 4 cars")
    judge.check("answer_saved_valuations", contains_count(answer, 1),
                "the account holds 1 saved valuation")
    # DB after-state: bob's shortlist loses 954 and gains 959; nothing else changes
    before = shortlist_listing_ids(initial_db, "bob.c@test.com")
    after = shortlist_listing_ids(after_db, "bob.c@test.com")
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    judge.check("bob_shortlist_added", added == [959], f"expected +[959], got +{added}")
    judge.check("bob_shortlist_removed", removed == [954], f"expected -[954], got -{removed}")
    judge.check("only_shortlist_changed",
                rows_of(after_db, "users") == rows_of(initial_db, "users")
                and rows_of(after_db, "saved_valuations") == rows_of(initial_db, "saved_valuations")
                and rows_of(after_db, "owner_reviews") == rows_of(initial_db, "owner_reviews"),
                "no other table may change")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
