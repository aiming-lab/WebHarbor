#!/usr/bin/env python3
"""verify_8.py — deterministic verifier for task Parkers--8.

Sign in as alice; find a used automatic SUV under £25,000, 2019 or later, under 40,000 miles, sorted by price; save the cheapest to the shortlist; report car, price and mileage.

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
    entered_identity,
    user_by_email)

TASK_ID = "Parkers--8"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_sign_in", navigated_sign_in(traj),
                "required: sign-in page")
    judge.check("nav_entered_credentials",
                entered_identity(traj, "alice.j@test.com"),
                "required: alice's email entered")
    # every shipped listing is Used, so the condition filter is answer-irrelevant
    # on this mirror and is not required (setting it is also accepted)
    judge.check("nav_c4s_filters",
                navigated_c4s_search(traj, body="SUV",
                                     transmission="Automatic", price_max="25000",
                                     mileage_max="40000", year_min="2019", sort="price-asc"),
                "required: cars-for-sale search with the task's filter combination "
                "(SUV, Automatic, <=25,000, <=40,000 miles, >=2019, price asc)")
    judge.check("nav_listing_detail", navigated_listing_detail(traj, 740),
                "required: open the cheapest matching listing (Vauxhall Mokka X, id 740)")
    judge.check("answer_car", contains_phrase(answer, "mokka"),
                "cheapest matching SUV is the Vauxhall Mokka X (2019/19)")
    judge.check("answer_price", contains_amount(answer, 10290),
                "its price is £10,290")
    judge.check("answer_mileage", contains_count(answer, 32208),
                "its mileage is 32,208")
    # DB after-state: exactly one new shortlist row for alice (listing 740)
    before = shortlist_listing_ids(initial_db, "alice.j@test.com")
    after = shortlist_listing_ids(after_db, "alice.j@test.com")
    delta = sorted(set(after) - set(before))
    judge.check("alice_shortlist_delta", delta == [740],
                f"expected +[740], got +{delta}")
    judge.check("alice_no_removals", not (set(before) - set(after)),
                "no shortlist rows may be removed")
    check_tables = set(shortlist_listing_ids(after_db, "alice.j@test.com"))
    judge.check("only_shortlist_changed",
                rows_of(after_db, "users") == rows_of(initial_db, "users")
                and rows_of(after_db, "saved_valuations") == rows_of(initial_db, "saved_valuations")
                and rows_of(after_db, "owner_reviews") == rows_of(initial_db, "owner_reviews"),
                "no other table may change")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
