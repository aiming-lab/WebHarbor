#!/usr/bin/env python3
"""verify_8.py — deterministic verifier for task REMAX--8.

Every rental <=$2,000 with 3+ bedrooms: open each page, report the most
recently built one (address, rent, match count), then ask about its
availability as a guest with the email given in the task.

Ground truth below is HARDCODED (frozen against the shipped seed DB); it never
appears in tasks.jsonl. Navigation gates encode the honest on-site path the
task text implies; a correct answer without that navigation is a shortcut and
fails. See verify_lib.py for the shared contract.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_lib import (  # noqa: E402
    Judge, added_rows, check_only_tables_changed, check_seed_contract,
    check_trajectory_identity, contains_amount, contains_any_phrase,
    contains_count, contains_phrase, entered_identity, final_answer,
    nav_rental_detail, nav_rentals_table, run_verifier)

TASK_ID = "REMAX--8"

# the 15 rentals with price <= 2000 and beds >= 3 (frozen seed)
MATCH_RENTAL_IDS = (2, 4, 26, 27, 28, 30, 37, 38, 39, 46, 51, 67, 79, 82, 90)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: rentals table + every matching rental's detail page +
    # the contact form actually carrying the guest email
    judge.check("nav_rentals_table", nav_rentals_table(traj),
                "required: /new-rentals rentals table")
    missing = [rid for rid in MATCH_RENTAL_IDS if not nav_rental_detail(traj, rid)]
    judge.check("nav_all_matching_rentals", not missing,
                f"required: detail pages of all 15 matching rentals; missing: {missing}")
    judge.check("nav_rental_217_bay_pine", nav_rental_detail(traj, 2),
                "required: rental detail for 217 Bay Pine Dr (id 2)")
    judge.check("entered_guest_email",
                entered_identity(traj, "renter.family@example.com"),
                "required: contact form filled with renter.family@example.com")
    # ground truth (frozen seed): 15 rentals match; the most recently built
    # (among those disclosing a build year) is 217 Bay Pine Dr, Madison AL,
    # $1,850/mo, built 2024
    judge.check("answer_match_count", contains_count(answer, 15),
                "must state 15 rentals matched")
    judge.check("answer_newest_address",
                contains_any_phrase(answer, ["217 Bay Pine", "Bay Pine Dr"]),
                "must name 217 Bay Pine Dr as the most recently built")
    judge.check("answer_newest_city", contains_phrase(answer, "Madison"),
                "must state Madison")
    judge.check("answer_newest_rent", contains_amount(answer, 1850),
                "must quote the $1,850 monthly rent")
    judge.check("answer_confirmation",
                contains_any_phrase(answer, ["contact you", "will contact",
                                             "sent", "thank you"]),
                "must report the site's confirmation")
    # DB after-state: exactly one new inquiry (listing contact) for rental 2
    check_seed_contract(judge, initial_db)
    check_only_tables_changed(judge, initial_db, after_db, ["inquiries"])
    new_inq = added_rows(after_db, initial_db, "inquiries", "id")
    judge.check("exactly_one_new_inquiry", len(new_inq) == 1,
                f"new inquiries: {new_inq}")
    if new_inq:
        r = new_inq[0]
        judge.check("inquiry_rental_2", r["rental_id"] == 2,
                    f"rental_id={r['rental_id']}")
        judge.check("inquiry_kind_listing", r["kind"] == "listing",
                    f"kind={r['kind']}")
        judge.check("inquiry_email",
                   (r["email"] or "").lower() == "renter.family@example.com",
                    f"email={r['email']}")
        judge.check("inquiry_user_guest", r["user_id"] is None,
                    f"user_id={r['user_id']} (guest submission expected)")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
