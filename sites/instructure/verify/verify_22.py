#!/usr/bin/env python3
"""Verify Instructure--22."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--22"

from verify_lib import db_query, table_delta, user_by_email, resource_by_slug

WEBINAR_SLUG = "moving-canvas-core-canvas-plus"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_webinar_detail",
                       "/resources/webinars/" + WEBINAR_SLUG)
    check_visited_path(judge, traj, "visited_account", "/account")
    # Frozen ground truth (seed DB): carol_d has NO seeded webinar registrations; the
    # registration flash reads "You're registered for 'Moving from Canvas Core to
    # Canvas Plus' - find it under your account."
    judge.check("answer_confirmation",
                contains_all(answer, ["registered", "Moving from Canvas Core to Canvas Plus"]),
                "expected the registration confirmation naming the webinar")
    # DB delta: exactly one webinar_registrations row added for carol x the webinar.
    carol = user_by_email(initial_db, "carol.d@test.com")
    res = resource_by_slug(initial_db, WEBINAR_SLUG)
    delta = table_delta(initial_db, after_db, "webinar_registrations")
    ok = (delta["removed"] == [] and delta["changed"] == [] and len(delta["added"]) == 1)
    if ok:
        cols = [r["name"] for r in db_query(after_db, "PRAGMA table_info(webinar_registrations)")]
        row = dict(zip(cols, delta["added"][0]))
        ok = row["user_id"] == carol["id"] and row["resource_id"] == res["id"]
    judge.check("db_registration_added", ok,
                f"webinar_registrations delta={delta!r}, expected one row "
                f"(user {carol['id']}, resource {res['id']})")
    check_only_tables_changed(judge, initial_db, after_db, ["webinar_registrations"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
