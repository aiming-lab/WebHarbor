#!/usr/bin/env python3
"""Verify Ohio.gov--8.

Guest travel-guide chain: order two 2026 Ohio Travel Guides without logging
in — a Standard print guide for Rosa Parks at 12 Elm Court, Toledo, Ohio
43604 (rosa.p@example.com) and a Large print guide for Sam Rivers at
8 Harbor View Dr, Sandusky, Ohio 44870 (sam.r@example.com) — report both
confirmation messages and the three ways the home page banner says you can
get the travel guide.

Frozen ground truth: the seed has exactly one travel-guide request (Bob's);
after the task the travel_guide_requests table gains exactly two rows —
(Rosa Parks, rosa.p@example.com, 12 Elm Court, Toledo, Ohio, 43604,
"Standard print", user_id NULL) and (Sam Rivers, sam.r@example.com,
8 Harbor View Dr, Sandusky, Ohio, 44870, "Large print", user_id NULL).
The home banner subheading reads "View online, download the app, or request
a copy in the mail."
"""
from verify_lib import (added_travel_guide_requests, check_only_tables_changed,
                        check_trajectory_identity, check_visited_path, contains_phrase,
                        final_answer, input_texts, run_verifier)

TASK_ID = "Ohio.gov--8"
GUIDE_PATH = "/travel-guide"
ORDER_1 = {"full_name": "Rosa Parks", "email": "rosa.p@example.com",
           "address_line1": "12 Elm Court", "city": "Toledo", "zip": "43604",
           "format": "Standard print"}
ORDER_2 = {"full_name": "Sam Rivers", "email": "sam.r@example.com",
           "address_line1": "8 Harbor View Dr", "city": "Sandusky", "zip": "44870",
           "format": "Large print"}


def _matches(row, spec):
    return ((row["full_name"] or "") == spec["full_name"]
            and (row["email"] or "").lower() == spec["email"]
            and (row["address_line1"] or "") == spec["address_line1"]
            and (row["city"] or "") == spec["city"]
            and (row["zip"] or "") == spec["zip"]
            and (row["format"] or "") == spec["format"])


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the travel guide form (visited at least twice — two
    # orders) + the home page (banner)
    check_visited_path(judge, traj, "visited_travel_guide_form", GUIDE_PATH)
    from verify_lib import navigated_to_path_times
    judge.check("visited_travel_guide_form_twice",
                navigated_to_path_times(traj, GUIDE_PATH, 2),
                "required: the travel-guide form submitted twice (two orders)")
    check_visited_path(judge, traj, "visited_home", "/")
    # both orders must have been placed as a guest (no OHID credentials)
    joined = " ".join(input_texts(traj)).lower()
    judge.check("guest_orders_no_login_credentials",
                "testpass123" not in joined and "alice.j@" not in joined
                and "bob.c@" not in joined and "carol.d@" not in joined,
                "both orders must be placed without logging in")
    # DB after-state: exactly two new travel-guide requests with the task fields
    added = added_travel_guide_requests(after_db, initial_db)
    judge.check("two_requests_added", len(added) == 2, f"added={len(added)}")
    if len(added) == 2:
        judge.check("added_orders_match_specs",
                    any(_matches(r, ORDER_1) for r in added)
                    and any(_matches(r, ORDER_2) for r in added),
                    f"observed={[(r['full_name'], r['format']) for r in added]!r}")
        judge.check("added_orders_guest",
                    all(r["user_id"] is None for r in added),
                    f"user_ids={[r['user_id'] for r in added]!r} (guest orders)")
    check_only_tables_changed(judge, initial_db, after_db, ("travel_guide_requests",))
    # answer: both confirmation messages + the three ways
    judge.check("answer_confirmation_standard",
                contains_phrase(answer, "12 elm court"),
                "expected: the Standard print guide will be mailed to 12 Elm Court, Toledo, Ohio 43604")
    judge.check("answer_confirmation_large",
                contains_phrase(answer, "8 harbor view dr") and contains_phrase(answer, "sandusky"),
                "expected: the Large print guide will be mailed to 8 Harbor View Dr, Sandusky, Ohio 44870")
    judge.check("answer_three_ways",
                contains_phrase(answer, "view online") and contains_phrase(answer, "download the app")
                and contains_phrase(answer, "request a copy in the mail"),
                "expected: View online, download the app, or request a copy in the mail")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
