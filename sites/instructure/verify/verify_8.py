#!/usr/bin/env python3
"""Verify Instructure--8: Support FAQ password-reset entries -> Contact Us
follow-up submission (Maria Chen / Northgate University)."""

from verify_lib import (check_trajectory_identity, check_visited_path,
                        check_only_tables_changed, contains_all, contains_any,
                        contains_phrase, entered_identity, final_answer,
                        run_verifier, selected_option, single_added_row)

TASK_ID = "Instructure--8"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the FAQ page and the contact form.
    check_visited_path(judge, traj, "visited_support_faq",
                       "/support/canvas-support-faq")
    check_visited_path(judge, traj, "visited_contact_us_page", "/contact-us")
    judge.check("entered_contact_identity",
                entered_identity(traj, "maria.chen@test.com"),
                "expected maria.chen@test.com among the form inputs")
    judge.check("selected_org_type_higher_ed",
                selected_option(traj, "Higher Ed"),
                "the organization-type select must choose Higher Ed")
    judge.check("selected_needs_teacher",
                selected_option(traj, "I'm a teacher looking for product information"),
                "the needs select must choose the teacher product-information option")
    # Frozen ground truth (seed FAQ + app.py flash): the official reset steps
    # are the Login page "Forgot Password?" link, the "Request Password"
    # button and the reset email; the contact flash is "Thanks for reaching
    # out! We'll be in touch shortly."
    judge.check("answer_forgot_password_link",
                contains_phrase(answer, "Forgot Password"),
                "expected the Forgot Password link in the reset steps")
    judge.check("answer_request_password_button",
                contains_phrase(answer, "Request Password"),
                "expected the Request Password button in the reset steps")
    judge.check("answer_reset_email",
                contains_phrase(answer, "email"),
                "expected the reset email step mentioned")
    judge.check("answer_contact_confirmation",
                contains_all(answer, ["Thanks for reaching out", "in touch"]),
                "expected the contact confirmation message")
    # DB delta: exactly one contact_messages row with the specified identity.
    ok_msg, msg_row = single_added_row(initial_db, after_db, "contact_messages")
    judge.check("db_contact_row",
                ok_msg
                and msg_row.get("first_name") == "Maria"
                and msg_row.get("last_name") == "Chen"
                and msg_row.get("email") == "maria.chen@test.com"
                and (msg_row.get("job_title") or "").lower() == "adjunct instructor"
                and msg_row.get("phone") == "+1 555-0170"
                and msg_row.get("organization") == "Northgate University"
                and msg_row.get("organization_type") == "Higher Ed"
                and msg_row.get("needs") == "I'm a teacher looking for product information"
                and msg_row.get("source") == "Contact Us",
                "expected exactly one Maria Chen contact_messages row from Contact Us")
    check_only_tables_changed(judge, initial_db, after_db, ["contact_messages"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
