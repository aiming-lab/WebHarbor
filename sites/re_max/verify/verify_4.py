#!/usr/bin/env python3
"""verify_4.py — deterministic verifier for task REMAX--4.

Bellevue open houses Sat 1pm-3pm window: cheapest qualifying home + guest tour request.

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
    contains_phrase, entered_identity, final_answer, nav_ldp, nav_srp,
    run_verifier)

TASK_ID = "REMAX--4"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: Bellevue SRP filtered to open houses + the chosen
    # listing's detail page + the tour form actually carrying the guest email
    judge.check("nav_bellevue_openhouses",
                nav_srp(traj, "wa", "bellevue", open_house="1"),
                "required: /wa/bellevue-real-estate with open_house=1")
    judge.check("nav_ldp_1003_156th", nav_ldp(traj, 372),
                "required: listing detail for 1003 156th Ave NE Unit 308 (id 372)")
    judge.check("entered_guest_email",
                entered_identity(traj, "bellevue.tour@example.com"),
                "required: tour form filled with bellevue.tour@example.com")
    # ground truth (frozen seed): 1003 156th Ave NE Unit 308 at $405,000,
    # Saturday September 26th 1-3pm
    judge.check("answer_home",
                contains_any_phrase(answer, ["1003 156th", "156th Ave NE Unit 308"]),
                "must name 1003 156th Ave NE Unit 308")
    judge.check("answer_price", contains_amount(answer, 405000),
                "must quote $405,000")
    judge.check("answer_window",
                contains_any_phrase(answer, ["1-3pm", "1pm to 3pm", "1:00", "3:00"]),
                "must state the 1-3pm open-house window")
    # DB after-state: exactly one new inquiry (tour) for listing 372
    check_seed_contract(judge, initial_db)
    check_only_tables_changed(judge, initial_db, after_db, ["inquiries"])
    new_inq = added_rows(after_db, initial_db, "inquiries", "id")
    judge.check("exactly_one_new_inquiry", len(new_inq) == 1,
                f"new inquiries: {new_inq}")
    if new_inq:
        r = new_inq[0]
        judge.check("inquiry_listing_372", r["listing_id"] == 372,
                    f"listing_id={r['listing_id']}")
        judge.check("inquiry_kind_tour", r["kind"] == "tour", f"kind={r['kind']}")
        judge.check("inquiry_email",
                   (r["email"] or "").lower() == "bellevue.tour@example.com",
                   f"email={r['email']}")
        judge.check("inquiry_user_guest", r["user_id"] is None,
                    f"user_id={r['user_id']} (guest submission expected)")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
