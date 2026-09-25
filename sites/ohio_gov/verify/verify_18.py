#!/usr/bin/env python3
"""Verify the current task: browser evidence, requested facts and exact state."""
from verify_lib import (SEED_USERS, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_any,
                        contains_count, contains_phrase, entered_identity, final_answer,
                        run_verifier, saved_slugs, user_by_email)

TASK_ID = "Ohio.gov--18"
CAROL_ID = SEED_USERS["carol.d@test.com"][0]
NEW_PHONE = "(513) 555-0200"
NEW_CITY = "Cleveland"
UNCHANGED_FIELDS = ("username", "email", "display_name", "first_name", "last_name",
                    "address_line1", "state", "zip")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "carol.d@test.com")
    # navigation gates: profile edit + account confirmation
    check_visited_path(judge, traj, "visited_account_edit", "/account/edit")
    check_visited_path(judge, traj, "visited_account", "/account")
    judge.check("entered_new_phone", entered_identity(traj, NEW_PHONE),
                f"expected {NEW_PHONE!r} in an input step")
    # DB after-state: exactly the phone + city delta on carol's row
    before = user_by_email(initial_db, "carol.d@test.com")
    after = user_by_email(after_db, "carol.d@test.com")
    judge.check("phone_updated", (after["phone"] or "") == NEW_PHONE,
                f"phone={after['phone']!r}")
    judge.check("city_updated", (after["city"] or "") == NEW_CITY,
                f"city={after['city']!r}")
    judge.check("other_fields_unchanged",
                all((before[f] or "") == (after[f] or "") for f in UNCHANGED_FIELDS),
                "all other profile fields must keep their seed values")
    judge.check("saved_count_unchanged",
                saved_slugs(after_db, CAROL_ID) == saved_slugs(initial_db, CAROL_ID),
                "carol's saved resources must be untouched")
    judge.check("no_complaints_created",
                not [r for r in __import__("verify_lib").db_query(
                    after_db, "SELECT * FROM scam_reports WHERE user_id = ?", (CAROL_ID,))],
                "no consumer complaint exists for carol")
    check_only_tables_changed(judge, initial_db, after_db, ("users",))
    # answer: phone, city, saved count, complaint
    judge.check("answer_phone", contains_phrase(answer, "(513) 555-0200")
                or contains_phrase(answer, "513) 555-0200") or contains_phrase(answer, "513-555-0200"),
                "expected phone: (513) 555-0200")
    judge.check("answer_city", contains_phrase(answer, "cleveland"),
                "expected city: Cleveland")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
