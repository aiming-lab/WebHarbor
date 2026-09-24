#!/usr/bin/env python3
"""Verify Instructure--23."""

import re

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--23"

from verify_lib import db_query, table_delta, demo_requests_rows

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_request_demo", "/request-demo")
    judge.check("entered_demo_form_identity",
                entered_identity(traj, "jordan.lee@test.com"),
                "expected jordan.lee@test.com among the form inputs")
    # Frozen ground truth (app.py request_demo_submit): success flash "Thanks! An
    # Instructure team member will reach out within one business day."
    judge.check("answer_success_message",
                contains_all(answer, ["Thanks", "reach out within one business day"]),
                "expected the demo request success message")
    # DB delta: exactly one demo_requests row (source Web Site) carrying the submitted
    # identity; nothing else changes.
    delta = table_delta(initial_db, after_db, "demo_requests")
    ok = (delta["removed"] == [] and delta["changed"] == [] and len(delta["added"]) == 1)
    if ok:
        cols = [r["name"] for r in db_query(after_db, "PRAGMA table_info(demo_requests)")]
        row = dict(zip(cols, delta["added"][0]))
        ok = (row["first_name"] == "Jordan" and row["last_name"] == "Lee"
              and row["email"] == "jordan.lee@test.com"
              and row["organization"] == "Summit Public Schools"
              and row["organization_type"] == "K12"
              and row["needs"] == "I want to connect with sales"
              and row["source"] == "Web Site")
    if ok:
        ok = bool(re.search('\\b(?:LMS|learning management)\\b', row["message"], re.I))
    judge.check("db_demo_request_row", ok,
                f"demo_requests delta={delta!r}, expected one Jordan Lee / Summit Public "
                f"Schools / K12 / sales row with source Web Site")
    check_only_tables_changed(judge, initial_db, after_db, ["demo_requests"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
