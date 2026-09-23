#!/usr/bin/env python3
"""Verify Instructure--16."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--16"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_support_faq", "/support/canvas-support-faq")
    # Frozen ground truth (seed DB, faq_items "How do I reset my password?"):
    # go to Login -> "Forgot Password?" link -> enter the login information ->
    # click the "Request Password" button -> email prompting you to reset ->
    # return to the login screen to sign in.
    judge.check("answer_forgot_password_link", contains_phrase(answer, "Forgot Password"),
                "expected the 'Forgot Password?' link step")
    judge.check("answer_request_password_button", contains_phrase(answer, "Request Password"),
                "expected the 'Request Password' button step")
    judge.check("answer_email_reset_prompt",
                contains_all(answer, ["email", "reset your password"]),
                "expected the emailed password reset prompt step")
    judge.check("answer_return_to_login", contains_any(answer, ["return to the login",
                                                                 "login screen"]),
                "expected the return-to-login step")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
