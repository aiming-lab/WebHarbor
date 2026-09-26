#!/usr/bin/env python3
"""verify_18.py — deterministic verifier for task REMAX--18.

Three remembered Austin homes (Calistoga Way, Wickersham Lane, Alegria Road)
found via the site's search, each listing page opened and reported, then a
tour request on the Calistoga Way home as a guest with the name, email and
phone given in the task.

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
    mentions_near, nav_ldp, nav_search_query, run_verifier)

TASK_ID = "REMAX--18"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: site searches for all three homes + all three listing
    # pages + the tour form carrying the guest identity
    judge.check("nav_search_calistoga",
                nav_search_query(traj, ["calistoga"]),
                "required: site search for Calistoga")
    judge.check("nav_search_wickersham",
                nav_search_query(traj, ["wickersham"]),
                "required: site search for Wickersham")
    judge.check("nav_search_alegria",
                nav_search_query(traj, ["alegria"]),
                "required: site search for Alegria")
    judge.check("nav_ldp_calistoga", nav_ldp(traj, 286),
                "required: listing detail for 12609 Calistoga Way (id 286)")
    judge.check("nav_ldp_wickersham", nav_ldp(traj, 287),
                "required: listing detail for 2450 Wickersham Ln Apt 1402 (id 287)")
    judge.check("nav_ldp_alegria", nav_ldp(traj, 281),
                "required: listing detail for 1914 Alegria Rd (id 281)")
    judge.check("entered_guest_name",
                entered_identity(traj, "Pat Rivera"),
                "required: tour form filled with Pat Rivera")
    judge.check("entered_guest_email",
                entered_identity(traj, "calistoga.tour@example.com"),
                "required: tour form filled with calistoga.tour@example.com")
    judge.check("entered_guest_phone",
                entered_identity(traj, "(512) 555-0184"),
                "required: tour form filled with (512) 555-0184")
    # ground truth (frozen seed): Calistoga Way $850,000, 5 bd / 4 ba,
    # $236/sqft, $100.50 monthly HOA, open house Saturday September 26th
    # 11-1am (upstream quirk preserved); Wickersham Ln $177/sqft, $351
    # monthly HOA; Alegria Rd $1,085,000, open house Saturday September
    # 26th 11-1pm
    judge.check("answer_calistoga_price", contains_amount(answer, 850000),
                "must quote the Calistoga Way price $850,000")
    judge.check("answer_calistoga_beds", contains_count(answer, 5),
                "must state the Calistoga Way 5 bedrooms")
    judge.check("answer_calistoga_baths", contains_count(answer, 4),
                "must state the Calistoga Way 4 bathrooms")
    judge.check("answer_calistoga_ppsf", contains_amount(answer, 236),
                "must quote the Calistoga Way $236 per square foot")
    judge.check("answer_calistoga_hoa", contains_amount(answer, 100.50),
                "must quote the Calistoga Way $100.50 monthly HOA fee")
    judge.check("answer_calistoga_oh",
                mentions_near(answer, "Calistoga", "11-1am"),
                "must state the Calistoga Way open-house window 11-1am (bound to Calistoga)")
    judge.check("answer_wickersham_ppsf", contains_amount(answer, 177),
                "must quote the Wickersham Lane $177 per square foot")
    judge.check("answer_wickersham_hoa", contains_amount(answer, 351),
                "must quote the Wickersham Lane $351 monthly HOA fee")
    judge.check("answer_alegria_price", contains_amount(answer, 1085000),
                "must quote the Alegria Road $1,085,000 price")
    judge.check("answer_alegria_oh",
                mentions_near(answer, "Alegria", "11-1pm"),
                "must state the Alegria Road open-house window 11-1pm (bound to Alegria)")
    judge.check("answer_confirmation",
                contains_any_phrase(answer, ["tour request sent", "confirm",
                                             "sent", "will confirm"]),
                "must report the tour confirmation")
    # DB after-state: exactly one new tour inquiry for listing 286
    check_seed_contract(judge, initial_db)
    check_only_tables_changed(judge, initial_db, after_db, ["inquiries"])
    new_inq = added_rows(after_db, initial_db, "inquiries", "id")
    judge.check("exactly_one_new_inquiry", len(new_inq) == 1,
                f"new inquiries: {new_inq}")
    if new_inq:
        r = new_inq[0]
        judge.check("inquiry_listing_286", r["listing_id"] == 286,
                    f"listing_id={r['listing_id']}")
        judge.check("inquiry_kind_tour", r["kind"] == "tour", f"kind={r['kind']}")
        judge.check("inquiry_email",
                   (r["email"] or "").lower() == "calistoga.tour@example.com",
                    f"email={r['email']}")
        judge.check("inquiry_name", (r["name"] or "").lower() == "pat rivera",
                    f"name={r['name']}")
        judge.check("inquiry_phone",
                   (r["phone"] or "").replace(" ", "") == "(512)555-0184",
                    f"phone={r['phone']}")
        judge.check("inquiry_user_guest", r["user_id"] is None,
                    f"user_id={r['user_id']} (guest submission expected)")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
