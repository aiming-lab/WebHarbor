#!/usr/bin/env python3
"""verify_9.py — deterministic verifier for task REMAX--9.

Louisville vs Worcester three-bedroom rentals: open each page, report which
city's cheapest three-bedroom is cheaper and by how much per month, which
rental's description mentions a basement, then schedule a tour of the
cheapest three-bedroom overall as a guest with the email given in the task.

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
    contains_phrase, entered_identity, final_answer, nav_rental_detail,
    nav_rentals_table, run_verifier)

TASK_ID = "REMAX--9"

# the six 3-bed rentals in Louisville and Worcester (frozen seed)
CITY_RENTAL_IDS = (37, 38, 39, 44, 45, 46)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: rentals table + all six city rental pages + the tour
    # form actually carrying the guest email
    judge.check("nav_rentals_table", nav_rentals_table(traj),
                "required: /new-rentals rentals table")
    missing = [rid for rid in CITY_RENTAL_IDS if not nav_rental_detail(traj, rid)]
    judge.check("nav_all_city_rentals", not missing,
                f"required: detail pages of all six Louisville/Worcester "
                f"3-bed rentals; missing: {missing}")
    judge.check("nav_rental_2110_burwell", nav_rental_detail(traj, 37),
                "required: rental detail for 2110 Burwell Ave (id 37)")
    judge.check("entered_guest_email",
                entered_identity(traj, "mover.reloc@example.com"),
                "required: tour form filled with mover.reloc@example.com")
    # ground truth (frozen seed): Louisville's cheapest 3-bed (2110 Burwell
    # Ave, $1,400) is $600/mo cheaper than Worcester's cheapest (53
    # Ellsworth St Apt 3, $2,000); 2110 Burwell Ave's description mentions
    # a basement; it is also the cheapest overall
    judge.check("answer_cheaper_city", contains_phrase(answer, "Louisville"),
                "must state Louisville has the cheaper three-bedroom")
    judge.check("answer_city_spread", contains_amount(answer, 600),
                "must state the $600 monthly difference")
    judge.check("answer_basement_home",
                contains_any_phrase(answer, ["2110 Burwell", "Burwell Ave"]),
                "must name 2110 Burwell Ave as the basement rental")
    judge.check("answer_basement_mentioned", contains_phrase(answer, "basement"),
                "must mention the basement")
    judge.check("answer_confirmation",
                contains_any_phrase(answer, ["tour request sent", "confirm",
                                             "sent", "will confirm"]),
                "must report the tour confirmation")
    # DB after-state: exactly one new tour inquiry for rental 37
    check_seed_contract(judge, initial_db)
    check_only_tables_changed(judge, initial_db, after_db, ["inquiries"])
    new_inq = added_rows(after_db, initial_db, "inquiries", "id")
    judge.check("exactly_one_new_inquiry", len(new_inq) == 1,
                f"new inquiries: {new_inq}")
    if new_inq:
        r = new_inq[0]
        judge.check("inquiry_rental_37", r["rental_id"] == 37,
                    f"rental_id={r['rental_id']}")
        judge.check("inquiry_kind_tour", r["kind"] == "tour", f"kind={r['kind']}")
        judge.check("inquiry_email",
                   (r["email"] or "").lower() == "mover.reloc@example.com",
                    f"email={r['email']}")
        judge.check("inquiry_user_guest", r["user_id"] is None,
                    f"user_id={r['user_id']} (guest submission expected)")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
