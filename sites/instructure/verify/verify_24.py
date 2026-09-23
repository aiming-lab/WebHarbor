#!/usr/bin/env python3
"""Verify Instructure--24."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--24"

from verify_lib import db_query, table_delta

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_contact_us", "/contact-us")
    judge.check("entered_contact_form_identity",
                entered_identity(traj, "maria.chen@test.com"),
                "expected maria.chen@test.com among the form inputs")
    # Frozen ground truth (app.py contact_us_submit): success flash "Thanks for reaching
    # out! We'll be in touch shortly."
    judge.check("answer_success_message",
                contains_all(answer, ["Thanks for reaching out", "in touch shortly"]),
                "expected the contact success message")
    # DB delta: exactly one contact_messages row (source Contact Us) carrying the
    # submitted identity; nothing else changes.
    delta = table_delta(initial_db, after_db, "contact_messages")
    ok = (delta["removed"] == [] and delta["changed"] == [] and len(delta["added"]) == 1)
    if ok:
        cols = [r["name"] for r in db_query(after_db, "PRAGMA table_info(contact_messages)")]
        row = dict(zip(cols, delta["added"][0]))
        ok = (row["first_name"] == "Maria" and row["last_name"] == "Chen"
              and row["email"] == "maria.chen@test.com"
              and row["organization"] == "Northgate University"
              and row["organization_type"] == "Higher Ed"
              and row["needs"] == "General Inquiry"
              and row["source"] == "Contact Us")
    judge.check("db_contact_message_row", ok,
                f"contact_messages delta={delta!r}, expected one Maria Chen / Northgate "
                f"University / Higher Ed / General Inquiry row")
    check_only_tables_changed(judge, initial_db, after_db, ["contact_messages"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
