#!/usr/bin/env python3
"""Verify Instructure--25."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--25"

from verify_lib import db_query, table_delta, resource_by_slug

EDISON_SLUG = "edison-high-school-case-study"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_edison_case_study",
                       "/resources/case-studies/" + EDISON_SLUG)
    check_visited_path(judge, traj, "visited_download_gate",
                       "/resources/case-studies/" + EDISON_SLUG + "/download")
    judge.check("entered_download_form_identity",
                entered_identity(traj, "priya.nair@test.com"),
                "expected priya.nair@test.com among the form inputs")
    # Frozen ground truth (app.py resource_download_submit): success flash "Thanks!
    # Your download of 'How Edison High School Turns Fees into Scholarships' is on its
    # way to your inbox."
    judge.check("answer_success_message",
                contains_all(answer, ["on its way", "inbox"]),
                "expected the download success confirmation")
    # DB delta: exactly one demo_requests row whose source is the download gate.
    res = resource_by_slug(initial_db, EDISON_SLUG)
    delta = table_delta(initial_db, after_db, "demo_requests")
    ok = (delta["removed"] == [] and delta["changed"] == [] and len(delta["added"]) == 1)
    if ok:
        cols = [r["name"] for r in db_query(after_db, "PRAGMA table_info(demo_requests)")]
        row = dict(zip(cols, delta["added"][0]))
        ok = (row["first_name"] == "Priya" and row["last_name"] == "Nair"
              and row["email"] == "priya.nair@test.com"
              and row["organization"] == "Edison High School"
              and row["organization_type"] == "K12"
              and row["needs"] == "I'm a teacher looking for product information"
              and row["source"] == "Download: " + res["title"])
    judge.check("db_download_request_row", ok,
                f"demo_requests delta={delta!r}, expected one Priya Nair download row "
                f"with source 'Download: {res['title']}'")
    check_only_tables_changed(judge, initial_db, after_db, ["demo_requests"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
