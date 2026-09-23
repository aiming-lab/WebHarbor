#!/usr/bin/env python3
"""Verify Instructure--3: sign in (david) -> Business-filtered webinars hub ->
'The Case for Building an Internal University' register + save -> profile job
title update."""

from verify_lib import (check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        resource_id_by_slug, run_verifier, single_added_row,
                        single_changed_user, table_delta, user_id_by_email,
                        delta_dicts)

TASK_ID = "Instructure--3"

WEBINAR = "case-building-internal-university-employee-training-and-development"
DAVID = "david.k@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, DAVID)
    # Navigation gates: Business-filtered hub, the webinar detail, the account.
    judge.check("visited_webinars_with_business_filter",
                navigated_listing_with_filter(traj, "webinars", "org", "Business"),
                "hub=/resources/webinars filter org=Business")
    check_visited_path(judge, traj, "visited_webinar_detail",
                       "/resources/webinars/" + WEBINAR)
    check_visited_path(judge, traj, "visited_account", "/account")
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    # Frozen ground truth (app.py flashes): registration confirmation
    # "You're registered for '<title>' — find it under your account." and
    # profile confirmation "Your profile has been updated."
    judge.check("answer_webinar_named",
                contains_phrase(answer, "Internal University"),
                "expected the internal-university webinar named in the answer")
    judge.check("answer_registration_confirmation",
                contains_phrase(answer, "find it under your account"),
                "expected the registration confirmation")
    judge.check("answer_profile_confirmation",
                contains_phrase(answer, "Your profile has been updated"),
                "expected the profile update confirmation")
    # DB delta: one registration + one save for david -> the webinar, and
    # david's users row changed only in job_title ('Director of Learning').
    regs_delta = table_delta(initial_db, after_db, "webinar_registrations")
    regs_added = delta_dicts(after_db, "webinar_registrations", regs_delta)
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta)
    david_id = user_id_by_email(initial_db, DAVID)
    webinar_id = resource_id_by_slug(initial_db, WEBINAR)
    judge.check("db_registration_row",
                len(regs_added) == 1 and not regs_delta["removed"]
                and not regs_delta["changed"]
                and regs_added[0]["user_id"] == david_id
                and regs_added[0]["resource_id"] == webinar_id,
                "expected exactly one new registration row: david -> the webinar")
    judge.check("db_saved_row",
                len(saved_added) == 1 and not saved_delta["removed"]
                and not saved_delta["changed"]
                and saved_added[0]["user_id"] == david_id
                and saved_added[0]["resource_id"] == webinar_id,
                "expected exactly one new saved row: david -> the webinar")
    ok_profile, why = single_changed_user(initial_db, after_db, DAVID,
                                          {"job_title": "Director of Learning"})
    judge.check("db_profile_job_title_only", ok_profile, why)
    check_only_tables_changed(judge, initial_db, after_db,
                              ["webinar_registrations", "saved_resources", "users"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
